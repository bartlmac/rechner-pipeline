"""T-Box 0.2.0 (ENTWURF): was Kern und Bestandsfuehrung laengst fuehren,
spricht jetzt auch das Vokabular — und der erste echte Versionsuebergang.

Drei Pruefgruppen:

1. **Keine zweite Wahrheit.** Wo der Code eine Menge als Konstante fuehrt
   (Ereigniscodes, Betragsarten, Status, Verfahren, Spalten des
   Zustandsextrakts), haelt ein Test die Spiegelung der T-Box mit ``==``
   gleich. Die T-Box importiert die Konstanten NICHT: Ein Import liesse das
   Vokabular still mitwandern, ohne dass die Version sich hebt — genau das
   soll ein roter Test verhindern (Rueckweg: Version heben, A-O1).
2. **Das Vokabular hat einen Fingerabdruck je Version.** Eine Aenderung am
   Vokabular ohne Versionssprung ist rot; ein Versionssprung ohne neuen
   Fingerabdruck auch.
3. **Die Konsumenten ziehen mit** (Befuellung, Merge, Kette, Coverage,
   Spez, P-K1, Fachspez) — und der Uebergang 0.1.0 -> 0.2.0 laeuft durch
   A-O1, ohne Test-Linie, auf der echten.

Knoten: klv, bu
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.ontologie import tbox
from rechner_pipeline.ontologie.abox import (
    abox_pfad,
    hebe_auf_geltende_version,
    lade,
    lade_aus_bytes,
    speichere,
    validate_abox,
)
from rechner_pipeline.ontologie.aussage import Provenienz, Zustand, belegt
from rechner_pipeline.ontologie.befuellung import (
    FragmentWert,
    FragmentZelle,
    QuellFragment,
    baue_generation,
    loese_diskrepanz_auf,
)
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.ontologie.kette import fragmente_ordner, pruefe_kette
from rechner_pipeline.ontologie.tbox import (
    ABox,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Quelle,
    Tarifgeneration,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ZEIT = "2026-10-01T08:00:00+00:00"
AKTEUR = "test/extrahiere-quellfragment@abc1234"

#: Fingerabdruck des Vokabulars je T-Box-Version. Wer das Vokabular
#: aendert, hebt die Version (Linie anhaengen, nie umschreiben) und traegt
#: hier den neuen Abdruck ein — beides im selben Diff, damit der Mensch, der
#: A-O1 zeichnet, sieht, dass sich das Vokabular bewegt hat.
VOKABULAR_ABDRUCK = {
    "0.2.0": "6c22a4abb75b2dcff3e8475f70f231c0598cb2301873b9d95994be6140ea5268",
}


# --------------------------------------------------------------------------- #
# 1 Version und Linie
# --------------------------------------------------------------------------- #

def test_version_gehoben_und_linie_angehaengt():
    assert tbox.TBOX_VERSION == "0.2.0"
    assert tbox.TBOX_VERSIONEN == ("0.1.0", "0.2.0")
    # Die Linie waechst nur am Ende; der alte Stand bleibt nachweisbar.
    assert tbox.TBOX_VERSIONEN[-1] == tbox.TBOX_VERSION


def test_vokabular_aenderung_ohne_versionssprung_ist_rot():
    """Mutationsprobe: ein Element einer beliebigen Vokabular-Konstante
    aendern -> der Abdruck weicht ab -> rot."""
    assert tbox.TBOX_VERSION in VOKABULAR_ABDRUCK, (
        f"T-Box {tbox.TBOX_VERSION} ohne Vokabular-Abdruck — neue Version "
        "hier mit ihrem Abdruck eintragen")
    assert tbox.vokabular_sha256() == VOKABULAR_ABDRUCK[tbox.TBOX_VERSION], (
        "Das Vokabular der T-Box hat sich bewegt, die Version nicht. "
        "TBOX_VERSION heben, TBOX_VERSIONEN anhaengen, den neuen Abdruck "
        f"({tbox.vokabular_sha256()}) hier eintragen — und die Aenderung "
        "geht ueber A-O1")


def test_vokabular_ist_von_beschreibungen_unabhaengig():
    """Eine Beschreibung zu verbessern ist keine Vokabular-Aenderung: Der
    Abdruck traegt Namen, Typen und Wertebereiche, keine Prosa."""
    def schluessel(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                yield k
                yield from schluessel(v)
        elif isinstance(obj, list):
            for v in obj:
                yield from schluessel(v)

    gesehen = set(schluessel(tbox.vokabular()))
    assert not gesehen & {"description", "title"}
    # ... und er traegt wirklich das Vokabular, nicht eine leere Huelle.
    assert {"geschaeftsvorfaelle", "tarifwerk", "abox_schema",
            "fragment_schema"} <= set(tbox.vokabular())


# --------------------------------------------------------------------------- #
# 2 Keine zweite Wahrheit: Spiegel gegen den Code (==)
# --------------------------------------------------------------------------- #

def test_tarifwerk_spiegelt_die_fuehrung():
    import datetime as dt

    from rechner_pipeline.bestand.config import (
        TARIFWERK_AUSFUEHRBAR,
        TarifGeneration,
    )
    from rechner_pipeline.kern.beitragsreduktion import VERFAHREN

    gen = TarifGeneration(name="x", gueltig_von=dt.date(2020, 1, 1),
                          gueltig_bis=dt.date(2021, 1, 1), max_endalter=90)
    assert tbox.TARIFWERK_MERKMALE == tuple(gen.tarifwerk())
    assert tbox.TARIFWERK_MERKMALE == tuple(TARIFWERK_AUSFUEHRBAR)
    assert tbox.HERABSETZUNGSVERFAHREN == VERFAHREN
    assert tbox.TARIFWERK_WERTE["red_verfahren"] == VERFAHREN
    for schalter in ("scheiben_mit_gamma1", "stoab_je_baustein"):
        assert tbox.TARIFWERK_WERTE[schalter] == (False, True)
    # Die Vorgabe des eigenen Geschaefts (Tarifplan KLV) ist die der Config.
    assert tbox.TARIFWERK_EIGENES_GESCHAEFT == gen.tarifwerk()


def test_produktfamilien_spiegeln_kern_und_bestand():
    import typing

    from rechner_pipeline.kern import zahlungspfad
    from rechner_pipeline.kern.produkte import bu
    from rechner_pipeline.models.bestand import (
        BU_GENERATION_FIELDS,
        GENERATION_FIELDS,
        LEISTUNGSSPALTE,
        PRODUKT_VALUES,
    )

    assert tuple(tbox.PRODUKTFAMILIEN) == PRODUKT_VALUES
    assert tbox.ABOX_FAMILIEN == typing.get_args(
        Tarifgeneration.model_fields["familie"].annotation)
    assert tbox.ZUSTAENDE_JE_FAMILIE == {
        "klv": (zahlungspfad.AKTIV, zahlungspfad.TOT),
        "bu": (bu.AKTIV, bu.BU_ZUSTAND, bu.TOT),
    }
    assert tbox.LEISTUNGSGROESSE_JE_FAMILIE == LEISTUNGSSPALTE
    assert tbox.BU_PARAMETER == BU_GENERATION_FIELDS
    assert set(tbox.RECHNUNGSGRUNDLAGEN_JE_FAMILIE["klv"]) == set(GENERATION_FIELDS)
    assert len(tbox.RECHNUNGSGRUNDLAGEN_JE_FAMILIE["klv"]) == len(GENERATION_FIELDS)


def test_vertragsstatus_spiegelt_das_datenmodell():
    from rechner_pipeline.models.bestand import (
        AKTIVE_STATUS,
        SEX_VALUES,
        STATUS_CODE_VALUES,
        TERMINALE_STATUS,
        ZAHLWEISE_VALUES,
    )

    assert tuple(tbox.VERTRAGSSTATUS) == STATUS_CODE_VALUES
    assert tbox.AKTIVE_STATUS == AKTIVE_STATUS
    assert tbox.TERMINALE_STATUS == TERMINALE_STATUS
    assert tbox.GESCHLECHTER == SEX_VALUES
    assert tbox.ZAHLWEISEN == ZAHLWEISE_VALUES


def test_geschaeftsvorfaelle_spiegeln_das_bewegungskonto():
    """Ereigniscodes, Betragsarten, Zustandswirkung und Produktbindung —
    einschliesslich der Teilkuendigung als eigenem Vorgang (ADR-023)."""
    from rechner_pipeline.models.bestand import (
        ANNAHME_ERZEUGT,
        BETRAG_ART_JE_EREIGNIS,
        EREIGNIS_OHNE_ANNAHME,
        EREIGNIS_VALUES,
        EREIGNIS_ZUSTAND,
        PRODUKT_VALUES,
        REDUKTION_EREIGNISSE,
    )

    gv = tbox.GESCHAEFTSVORFAELLE
    assert tuple(gv) == EREIGNIS_VALUES
    assert all(code == g.code for code, g in gv.items())
    assert {c: g.betragsarten for c, g in gv.items()} == BETRAG_ART_JE_EREIGNIS
    assert {c: g.zustand for c, g in gv.items() if g.zustand} == EREIGNIS_ZUSTAND
    mit_annahme = {(f, c) for c, g in gv.items() for f in g.familien
                   if c not in EREIGNIS_OHNE_ANNAHME}
    assert mit_annahme == set(ANNAHME_ERZEUGT.values())
    for code in EREIGNIS_OHNE_ANNAHME:
        assert set(gv[code].familien) == set(PRODUKT_VALUES), code
    assert tbox.ABSETZUNG_VORGAENGE == REDUKTION_EREIGNISSE


def test_die_lesart_einer_gelieferten_absetzung_spiegelt_den_zugang():
    """Die Lieferung kennt nur einen Code fuer beide Absetzungen; welcher
    Vorgang es war, sagt das Verfahren der QUELLE (ADR-023, A2). Die
    T-Box nennt den Code, das Verfahren und seine Werte; die Regel selbst
    bleibt im Datenmodell."""
    from rechner_pipeline.models.bestand import (
        TEILKUENDIGUNG_VERFAHREN,
        alt_absetzung_ist_teilkuendigung,
        reduktion_ereignis,
    )

    assert tbox.QUELL_ABSETZUNGSCODE == "RED"
    assert tbox.QUELL_ABSETZUNGSCODE in tbox.QUELL_VORGAENGE_RECHNEND
    assert tbox.QUELLVERFAHREN_WERTE["red_verfahren"] == tbox.HERABSETZUNGSVERFAHREN
    assert tbox.TEILKUENDIGUNG_VERFAHREN == TEILKUENDIGUNG_VERFAHREN
    assert {reduktion_ereignis(v) for v in tbox.HERABSETZUNGSVERFAHREN} == set(
        tbox.ABSETZUNG_VORGAENGE)
    # Vor dem Beitragsende entscheidet allein das Quellverfahren.
    for verfahren in tbox.HERABSETZUNGSVERFAHREN:
        assert alt_absetzung_ist_teilkuendigung(verfahren, 3, 10) is (
            verfahren == tbox.TEILKUENDIGUNG_VERFAHREN)


def test_vertragsvokabular_der_transformation_ist_das_der_tbox():
    """Die Zielfelder eines Bestandsabzugs waren Vokabular ausserhalb der
    T-Box (und ausserhalb ihrer Version)."""
    from rechner_pipeline.ontologie import transformation

    assert transformation.ZIEL_PFLICHT is tbox.VERTRAG_PFLICHT
    assert transformation.ZIEL_OPTIONAL is tbox.VERTRAG_OPTIONAL
    assert transformation.SEX_ZIELWERTE is tbox.GESCHLECHTER


def test_migrationsvokabular_spiegelt_zugang_und_nebentabellen():
    from rechner_pipeline.bestand.migrationszugang import FORMEN, RECHNENDE_VORFAELLE
    from rechner_pipeline.models import bestand as mb

    assert frozenset(tbox.QUELL_VORGAENGE_RECHNEND) == RECHNENDE_VORFAELLE
    assert len(tbox.QUELL_VORGAENGE_RECHNEND) == len(RECHNENDE_VORFAELLE)
    assert tbox.FORMFUNKTIONEN == FORMEN
    assert tbox.ZUSTAENDE_TA == mb.ZUSTAENDE_TA
    assert tbox.VERANKERUNGSZUSTAENDE == mb.VERANKERUNGSZUSTAENDE
    assert tbox.HERABSETZUNGSVERFAHREN == mb.RED_VERFAHREN
    spalten = {
        "verankerung": mb.VERANKERUNG_NAMES,
        "scheiben": mb.SCHEIBEN_NAMES,
        "reduktionen": mb.REDUKTIONEN_NAMES,
        "merkmale": mb.MERKMALE_NAMES,
    }
    assert set(tbox.ZUSTANDSEXTRAKT) == set(spalten)
    for tabelle, namen in spalten.items():
        assert tbox.ZUSTANDSEXTRAKT[tabelle] == tuple(
            n for n in namen if n != "police_id"), tabelle


# --------------------------------------------------------------------------- #
# 3 Tarifwerk in der A-Box
# --------------------------------------------------------------------------- #

def _prov(datei: str = "meldung.docx") -> Provenienz:
    return Provenienz(quelle_datei=datei, quelle_sha256="a" * 64,
                      fundstelle="Ziffer 6", akteur=AKTEUR, erhoben_am=ZEIT)


def _gen(**tarifwerk) -> Tarifgeneration:
    return Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[Quelle(datei="meldung.docx", sha256="a" * 64, art="tarifmeldung")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={
            f: belegt(0.01 if f not in ("tafel",) else "DAV2008_T", [_prov()])
            for f in PFLICHT_PARAMETER})],
        tarifwerk={k: belegt(v, [_prov()]) for k, v in tarifwerk.items()},
    )


def test_unbekanntes_tarifwerksmerkmal_wird_verweigert():
    with pytest.raises(ValueError, match="Tarifwerk"):
        _gen(red_verfahren_quelle="teilkuendigung")


@pytest.mark.parametrize("merkmal, wert", [
    ("red_verfahren", "irgendwie"),
    ("red_verfahren", True),
    ("stoab_je_baustein", "ja"),
    ("scheiben_mit_gamma1", 1),
])
def test_tarifwerk_ausserhalb_des_wertebereichs_ist_befund(merkmal, wert):
    abox = ABox(fall="f", generationen=[_gen(**{merkmal: wert})])
    assert any(merkmal in f and "Wertebereich" in f for f in validate_abox(abox))


def test_tarifwerk_im_wertebereich_ist_kein_befund():
    abox = ABox(fall="f", generationen=[_gen(
        red_verfahren="teilkuendigung", stoab_je_baustein=True,
        scheiben_mit_gamma1=True)])
    assert validate_abox(abox) == []


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = tmp_path / "fall"
    anlegen(f, beschreibung="Testfall")
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    return f


def _register(fall: Path) -> dict:
    return json.loads((fall / "eingang.json").read_text(encoding="utf-8"))


def _fragment(quelle: str, art: str, tarifwerk=None, nicht_belegt=()) -> QuellFragment:
    return QuellFragment(
        generation="tg2015", quelle_datei=quelle, quelle_art=art,
        zellen=[FragmentZelle(parameter={
            "zins": FragmentWert(wert=0.0125, fundstelle=f"{quelle}:zins")})],
        tarifwerk={k: FragmentWert(wert=v, fundstelle=f"{quelle}:Ziffer 6")
                   for k, v in (tarifwerk or {}).items()},
        nicht_belegt=list(nicht_belegt),
    )


def test_widersprechende_tarifwerke_werden_diskrepanz_und_aufloesbar(fall):
    meldung = _fragment("meldung.docx", "tarifmeldung",
                        {"red_verfahren": "teilkuendigung"})
    rechner = _fragment("rechner.xlsm", "tarifrechner",
                        {"red_verfahren": "prospektiv"})
    gen, diskrepanzen = baue_generation(
        "tg2015", [meldung, rechner], _register(fall),
        {0: AKTEUR, 1: AKTEUR.replace("quellfragment", "quellfragment-b")}, ZEIT)
    [d] = diskrepanzen
    assert (d.knoten, d.feld) == ("klv/tg2015/tarifwerk", "red_verfahren")
    assert gen.tarifwerk["red_verfahren"].zustand is Zustand.WIDERSPRUECHLICH
    abox = ABox(fall="f", generationen=[gen], diskrepanzen=diskrepanzen)
    assert validate_abox(abox, _register(fall)) == []
    # Ohne Diskrepanz-Objekt ist der Widerspruch ein Befund (keine stille Luecke).
    assert any("red_verfahren" in f for f in validate_abox(
        abox.model_copy(update={"diskrepanzen": []}), _register(fall)))
    abox = loese_diskrepanz_auf(
        abox, d.id, "teilkuendigung", "mensch/aktuariat",
        "Bedingungswerk Ziffer 6 geht dem Rechner vor", ZEIT)
    aussage = abox.generationen[0].tarifwerk["red_verfahren"]
    assert aussage.zustand is Zustand.BELEGT and aussage.wert == "teilkuendigung"


def test_gesucht_nicht_gefunden_im_tarifwerk_landet_im_tarifwerk(fall):
    """Ein Tarifwerksmerkmal unter ``nicht_belegt`` gehoert zur Generation,
    nicht in jede Zelle — dort waere es ein unbekannter Parameter."""
    fragment = _fragment("meldung.docx", "tarifmeldung",
                         nicht_belegt=("tarifwerk.stoab_je_baustein", "alpha"))
    gen, _ = baue_generation("tg2015", [fragment], _register(fall), {0: AKTEUR}, ZEIT)
    assert gen.tarifwerk["stoab_je_baustein"].zustand is Zustand.NICHT_BELEGT
    assert "stoab_je_baustein" not in gen.zellen[0].parameter
    assert gen.zellen[0].parameter["alpha"].zustand is Zustand.NICHT_BELEGT


def test_quellverfahren_ist_eigener_block_mit_eigenem_wertebereich(fall):
    """Wie die Quelle eine gelieferte Absetzung gemeint hat, ist eine
    Eigenschaft der Lieferung, nicht das Tarifwerk, nach dem das Ziel kuenftig
    fuehrt — beide tragen ``red_verfahren``, ohne sich zu beruehren."""
    meldung = _fragment("meldung.docx", "tarifmeldung",
                        {"red_verfahren": "prospektiv"})
    meldung.quellverfahren["red_verfahren"] = FragmentWert(
        wert="teilkuendigung", fundstelle="Auskunft der Quelle")
    gen, diskrepanzen = baue_generation(
        "tg2015", [meldung], _register(fall), {0: AKTEUR}, ZEIT)
    assert not diskrepanzen
    assert gen.tarifwerk["red_verfahren"].wert == "prospektiv"
    assert gen.quellverfahren["red_verfahren"].wert == "teilkuendigung"
    abox = ABox(fall="f", generationen=[gen.model_copy(update={
        "quellverfahren": {"red_verfahren": belegt("irgendwie", [_prov()])}})])
    assert any("quellverfahren" in f and "Wertebereich" in f
               for f in validate_abox(abox))
    with pytest.raises(ValueError, match="Quellverfahren"):
        Tarifgeneration.model_validate({
            **_gen().model_dump(mode="json"),
            "quellverfahren": {"stoab_je_baustein": {"zustand": "nicht_belegt"}}})


def test_coverage_weist_das_tarifwerk_getrennt_aus():
    gen = _gen(red_verfahren="teilkuendigung")
    bericht = coverage_bericht(ABox(fall="f", generationen=[gen]))
    [g] = bericht["generationen"]
    assert g["tarifwerk"]["red_verfahren"]["zustand"] == "belegt"
    assert g["tarifwerk"]["stoab_je_baustein"]["zustand"] == "fehlt_in_extraktion"
    assert g["tarifwerk_vollstaendig"] is False
    assert bericht["tarifwerk_vollstaendig"] is False
    # Der Pflichtumfang der Parameter bleibt davon unberuehrt (0.2.0: das
    # Tarifwerk ist ausgewiesen, nicht blockierend).
    assert g["vollstaendig"] is True
    assert g["quellverfahren"]["red_verfahren"]["zustand"] == "fehlt_in_extraktion"


# --------------------------------------------------------------------------- #
# 4 Kette: ein von Hand gesetztes Tarifwerk folgt nicht aus den Fragmenten
# --------------------------------------------------------------------------- #

def test_kette_faengt_ein_erfundenes_tarifwerk(fall):
    from rechner_pipeline.gates.abox_merge import main as merge_cli

    ordner = fragmente_ordner(fall)
    ordner.mkdir(parents=True)
    fragment = _fragment("meldung.docx", "tarifmeldung",
                         {"red_verfahren": "prospektiv"})
    (ordner / "tg2015-meldung.json").write_text(
        fragment.model_dump_json(), encoding="utf-8")
    (ordner / "akteure.json").write_text(
        json.dumps({"tg2015-meldung.json": AKTEUR}), encoding="utf-8")
    assert merge_cli(["--fall", str(fall)]).exit_code == 0
    assert pruefe_kette(fall) == []
    abox = lade(fall)
    prov = abox.generationen[0].tarifwerk["red_verfahren"].provenienz
    abox.generationen[0].tarifwerk["red_verfahren"] = belegt("teilkuendigung", prov)
    abox.generationen[0].tarifwerk["stoab_je_baustein"] = belegt(True, prov)
    speichere(abox, fall)
    befunde = pruefe_kette(fall)
    assert any("tarifwerk" in b.lower() for b in befunde), befunde


# --------------------------------------------------------------------------- #
# 5 Spez, P-K1, Fachspez
# --------------------------------------------------------------------------- #

def _spez_abox() -> ABox:
    from tests.e2e_fixture import lade_pk1_fixture

    fx = lade_pk1_fixture()
    prov = _prov()
    gen = Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[Quelle(datei="meldung.docx", sha256="a" * 64, art="tarifmeldung")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={
            f: belegt(w, [prov]) for f, w in fx.parameter.items()})],
        tarifwerk={"red_verfahren": belegt("teilkuendigung", [prov]),
                   "stoab_je_baustein": belegt(True, [prov])},
        quellverfahren={"red_verfahren": belegt("teilkuendigung", [prov])},
    )
    return ABox(fall="f", generationen=[gen])


def test_spez_projiziert_das_belegte_tarifwerk():
    from rechner_pipeline.spez.erzeugen import baue_spez
    from rechner_pipeline.spez.validierung import validate_spez

    abox = _spez_abox()
    spez = baue_spez(abox, "klv/tg2015", vorhandene_tafeln=set())
    assert spez.tarifwerk == {"red_verfahren": "teilkuendigung",
                              "stoab_je_baustein": True}
    assert spez.quellverfahren == {"red_verfahren": "teilkuendigung"}
    assert validate_spez(spez, abox) == []
    falsch = spez.model_copy(update={"quellverfahren": {"red_verfahren": "prospektiv"}})
    assert any("quellverfahren" in f for f in validate_spez(falsch, abox))
    ohne = spez.model_copy(update={"quellverfahren": {}})
    assert any("quellverfahren" in f for f in validate_spez(ohne, abox))


@pytest.mark.parametrize("tarifwerk, stichwort", [
    ({"red_verfahren": "prospektiv", "stoab_je_baustein": True}, "red_verfahren"),
    ({"red_verfahren": "teilkuendigung"}, "stoab_je_baustein"),
    ({"red_verfahren": "teilkuendigung", "stoab_je_baustein": True,
      "scheiben_mit_gamma1": False}, "scheiben_mit_gamma1"),
])
def test_pk1_haelt_das_tarifwerk_der_spez_gegen_die_abox(tarifwerk, stichwort):
    """Beide Richtungen: falscher Wert, fehlender Wert (der Kern, die
    Fuehrung rechnete sonst mit der Vorgabe des eigenen Geschaefts), und ein
    Wert, den die A-Box nicht belegt (eigene Wahrheit der Spez)."""
    from rechner_pipeline.spez.erzeugen import baue_spez
    from rechner_pipeline.spez.validierung import validate_spez

    abox = _spez_abox()
    spez = baue_spez(abox, "klv/tg2015", vorhandene_tafeln=set())
    falsch = spez.model_copy(update={"tarifwerk": tarifwerk})
    assert any(stichwort in f and "tarifwerk" in f
               for f in validate_spez(falsch, abox)), validate_spez(falsch, abox)


def test_spez_aus_ungeklaertem_tarifwerk_wird_verweigert():
    from rechner_pipeline.ontologie.merge import merge_felder
    from rechner_pipeline.spez.erzeugen import SpezFehler, baue_spez

    abox = _spez_abox()
    gemergt, [d] = merge_felder("klv/tg2015/tarifwerk", [
        {"red_verfahren": belegt("teilkuendigung", [_prov("meldung.docx")])},
        {"red_verfahren": belegt("prospektiv", [_prov("rechner.xlsm")])},
    ])
    abox.generationen[0].tarifwerk["red_verfahren"] = gemergt["red_verfahren"]
    abox.diskrepanzen.append(d)
    with pytest.raises(SpezFehler, match="red_verfahren"):
        baue_spez(abox, "klv/tg2015", vorhandene_tafeln=set())


def test_strukturvergleich_nennt_ein_abweichendes_tarifwerk():
    from rechner_pipeline.spez.erzeugen import strukturvergleich

    neu = _spez_abox().generationen[0]
    ref = neu.model_copy(update={"id": "klv/tg2012", "name": "TG2012",
                                 "tarifwerk": {
                                     "red_verfahren": belegt("prospektiv", [_prov()])}})
    urteil = strukturvergleich(neu, ref, set(), None)
    assert any("Tarifwerk" in b and "red_verfahren" in b for b in urteil.begruendung)
    # stoab_je_baustein belegt nur die neue Generation: aus einer einseitigen
    # Luecke urteilt der Vergleich nicht.
    assert urteil.geaenderte_tarifwerksmerkmale == ["red_verfahren"]


def test_fachspez_traegt_das_tarifwerk_mit_herkunft():
    from rechner_pipeline.spez.erzeugen import baue_spez
    from rechner_pipeline.spez.fachspez import erzeuge_fachspez

    abox = _spez_abox()
    text = erzeuge_fachspez(baue_spez(abox, "klv/tg2015", vorhandene_tafeln=set()), abox)
    assert "Tarifwerk" in text
    assert "teilkuendigung" in text and "Ziffer 6" in text
    # Was nicht erhoben ist, steht da — und mit der Folge, nicht leer.
    assert "scheiben_mit_gamma1" in text and "nicht erhoben" in text


# --------------------------------------------------------------------------- #
# 6 Der Uebergang: alte A-Boxen, der erste echte A-O1-Lauf
# --------------------------------------------------------------------------- #

def _als_alte_abox(abox: ABox) -> bytes:
    """Die Bytes, die der Code 0.1.0 geschrieben haette: ohne Tarifwerk,
    mit der alten Version."""
    daten = abox.model_dump(mode="json", exclude_none=True)
    daten["tbox_version"] = "0.1.0"
    for gen in daten["generationen"]:
        gen.pop("tarifwerk", None)
    return json.dumps(daten, sort_keys=True).encode()


def test_eine_abox_der_vorversion_ist_fremd():
    alt = lade_aus_bytes(_als_alte_abox(ABox(fall="f", generationen=[_gen()])))
    assert any("tbox_version" in f and "0.1.0" in f for f in validate_abox(alt))


def test_heben_erhaelt_entscheidungen_und_aendert_nur_die_version(fall):
    meldung = _fragment("meldung.docx", "tarifmeldung")
    rechner = _fragment("rechner.xlsm", "tarifrechner")
    rechner.zellen[0].parameter["zins"] = FragmentWert(wert=0.0175, fundstelle="x")
    gen, diskrepanzen = baue_generation(
        "tg2015", [meldung, rechner], _register(fall),
        {0: AKTEUR, 1: AKTEUR.replace("quellfragment", "quellfragment-b")}, ZEIT)
    abox = ABox(fall="f", generationen=[gen], diskrepanzen=diskrepanzen)
    abox = loese_diskrepanz_auf(abox, diskrepanzen[0].id, 0.0125,
                                "mensch/aktuariat", "Mitteilung geht vor", ZEIT)
    alt = lade_aus_bytes(_als_alte_abox(abox))
    neu = hebe_auf_geltende_version(alt)
    assert neu.tbox_version == tbox.TBOX_VERSION
    assert validate_abox(neu, _register(fall)) == []
    # Alles ausser der Version ist byte-gleich — die Entscheidung des
    # Aktuariats wandert unveraendert mit.
    vorher = alt.model_dump(mode="json", exclude_none=True)
    nachher = neu.model_dump(mode="json", exclude_none=True)
    vorher.pop("tbox_version"), nachher.pop("tbox_version")
    assert vorher == nachher
    assert neu.diskrepanzen[0].entscheidung.gewaehlter_wert == 0.0125


def test_heben_kennt_nur_deklarierte_uebergaenge():
    alt = ABox(fall="f", generationen=[_gen()]).model_copy(
        update={"tbox_version": "0.0.9"})
    with pytest.raises(ValueError, match="Uebergang"):
        hebe_auf_geltende_version(alt)
    aktuell = ABox(fall="f", generationen=[_gen()])
    with pytest.raises(ValueError, match="bereits"):
        hebe_auf_geltende_version(aktuell)


def test_jeder_schritt_der_linie_hat_eine_hebung():
    """Ein Versionssprung ohne Hebungsregel liesse jede A-Box der Vorversion
    ohne Ausweg ausser dem Neu-Merge — der Entscheidungen verwirft."""
    linie = tbox.TBOX_VERSIONEN
    from rechner_pipeline.ontologie.abox import HEBUNGEN

    assert set(HEBUNGEN) == set(zip(linie, linie[1:]))


@pytest.fixture()
def pk1_fall(tmp_path: Path) -> Path:
    from rechner_pipeline.gates.abox_validate import main as pq3
    from tests.e2e_fixture import bereite_pk1_fall

    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def _aenderungsbeleg(fall: Path, von: str) -> Path:
    tbox_dir = fall / "abgeleitet" / "tbox"
    tbox_dir.mkdir(parents=True, exist_ok=True)
    vermerk = tbox_dir / "aenderungsvermerk.md"
    vermerk.write_text("T-Box 0.2.0: Tarifwerk, GeVo-Katalog, Zustandsextrakt.\n",
                       encoding="utf-8")
    pfad = tbox_dir / "aenderung.json"
    pfad.write_text(json.dumps({
        "schema_version": 2, "von_version": von, "nach_version": tbox.TBOX_VERSION,
        "tbox_sha256": hashlib.sha256(Path(tbox.__file__).read_bytes()).hexdigest(),
        "artefakt": {"pfad": "abgeleitet/tbox/aenderungsvermerk.md",
                     "sha256": hashlib.sha256(vermerk.read_bytes()).hexdigest()},
        "begruendung": "Erste Erweiterung der T-Box seit 0.1.0.",
        # Schema 2 (ADR-025): das ganze Vokabular, Grundlage der Sicht.
        "vokabular": json.loads(json.dumps(tbox.vokabular(), sort_keys=True)),
        "vokabular_sha256": tbox.vokabular_sha256(), "vorher": None,
    }), encoding="utf-8")
    (tbox_dir / "stellungnahme.json").write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "red_verfahren", "wirkung": "bewertungsrelevant",
                    "begruendung": "Das Verfahren bestimmt Summe und Auszahlung "
                                   "einer Herabsetzung."}],
    }), encoding="utf-8")
    return pfad


def test_der_erste_echte_uebergang_traegt_auf_der_echten_linie(pk1_fall):
    """Ohne testlokale Linie: 0.1.0 -> 0.2.0 ist der Uebergang, den der
    Code nachweist; der Beleg passt, A-O1 nimmt an. Der Fall laeuft auf dem
    neuen Stand — seine A-Box spricht 0.2.0, P-Q3 ist gruen."""
    from rechner_pipeline.gates import gate_entscheid
    from tests.zeichnung_fixture import annahme_args

    assert lade(pk1_fall).tbox_version == "0.2.0"
    beleg = _aenderungsbeleg(pk1_fall, von="0.1.0")
    assert gate_entscheid.pruefe_tbox_aenderung(
        beleg, pk1_fall, repo_root=REPO_ROOT) == []
    ergebnis = gate_entscheid.main([
        "--fall", str(pk1_fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "IT-Verantwortung", "--begruendung", "T-Box 0.2.0",
        "--repo-root", str(REPO_ROOT), *annahme_args(pk1_fall, fuer="A-O1"),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["rolle"] == "mensch/architektur"
    assert snapshot["stand"] == {"version": "0.2.0",
                                 "tbox_sha256": hashlib.sha256(
                                     Path(tbox.__file__).read_bytes()).hexdigest()}


@pytest.mark.parametrize("von", ["0.0.9", "0.2.0", "0.1.1"])
def test_ein_erfundener_alter_stand_wird_nicht_gezeichnet(pk1_fall, von):
    from rechner_pipeline.gates import gate_entscheid

    beleg = _aenderungsbeleg(pk1_fall, von=von)
    assert gate_entscheid.pruefe_tbox_aenderung(beleg, pk1_fall, repo_root=REPO_ROOT)
