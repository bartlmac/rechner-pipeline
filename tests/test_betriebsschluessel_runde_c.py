"""Der Betrieb bekommt einen Zeugen: der Betriebsschluessel (Runde C, F2).

Kernbefund der Pruefrunde nach T27, Runde C: Der Tagesbetrieb hatte keinen
Zeugen ausser sich selbst. Wer die Ablage beschreiben konnte, schrieb
Protokoll und Eingaenge stimmig um — eine herabgestufte Zeile (RC10), eine
zweite gruene Zeile fuer denselben Tag (RC11), geglaubte Kennzahlen (RC12)
und Herkunftsangaben (RC13), ein verschwundener (RC14) oder umgeschriebener
Eingang (RC15). Dazu RC16: registriert wurde, was der Tageslauf danach jede
Nacht verweigerte.

Entscheid des Maintainers (2026-09-30): Der Betrieb bekommt einen Schluessel
EXAKT wie die Rollen der Abnahmen (ADR-018) — Schluesseldatei beim Menschen,
Fingerabdruck in der Zeichnungsordnung, HMAC-Zeichnung nach
``models.anker``. Neu ist nur die Rolle ``betrieb/tageslauf`` mit der
Schluesselklasse ``betrieb`` und leerer gates-Liste.

Wo ein Test eine ZWEITE Schicht misst (Nachrechnung, Tagesfolge), zeichnet
er seine Faelschung mit dem Test-Betriebsschluessel neu (``zeichne_neu``):
der Faelscher, der den Schluessel hat. Sonst finge schon die Signatur ihn,
und der Test sagte nichts ueber die Schicht, fuer die er steht.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import shutil
import sys
from pathlib import Path

import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from rechner_pipeline.models import anker as ak
from rechner_pipeline.models.zeichnung import (
    SCHLUESSELKLASSEN,
    ZEICHNENDE_KLASSEN,
    lade_zeichnungsordnung,
    rolle_darf_gate,
    validiere_zeichnung,
)
from tests.freigabe_testschluessel import (
    BETRIEBSKEY,
    BETRIEBSROLLE,
    TESTRING,
    betriebsordnung,
    zeichne_neu,
)
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import (
    STICHTAG,
    _beleg_neu,
    _fall,
    _kleine_config,
    uebernahmebeleg,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402


# --------------------------------------------------------------------------- #
# Hilfen
# --------------------------------------------------------------------------- #


def _rohe(ablage: Ablage) -> list:
    return [z for z in ablage.protokoll_pfad.read_text(encoding="utf-8").split("\n") if z.strip()]


def _schreibe(ablage: Ablage, rohe: list) -> None:
    ablage.protokoll_pfad.chmod(0o644)
    ablage.protokoll_pfad.write_text("\n".join(rohe) + "\n", encoding="utf-8")


def _dump(zeile: dict) -> str:
    return json.dumps(zeile, ensure_ascii=False, sort_keys=True)


def _letzte_neu(ablage: Ablage, aendern) -> None:
    """Die letzte Zeile aendern und mit dem Schluessel NEU zeichnen."""
    rohe = _rohe(ablage)
    zeile = json.loads(rohe[-1])
    aendern(zeile)
    rohe[-1] = _dump(zeichne_neu(zeile))
    _schreibe(ablage, rohe)


def _kopie(quelle: Path, ziel: Path) -> Ablage:
    shutil.copytree(quelle, ziel, symlinks=True)
    return Ablage(ziel)


def _schluessel_und_ordnung(tmp_path: Path, rolle: str, klasse: str, gates=()):
    """Ein Schluessel (0600) ausserhalb jeder Ablage und eine Ordnung, die
    ihm die Rolle gibt."""
    verzeichnis = tmp_path / "schluessel"
    verzeichnis.mkdir(exist_ok=True)
    schluessel = verzeichnis / f"{rolle.replace('/', '-')}.key"
    schluessel.write_bytes(hashlib.sha256(rolle.encode()).digest())
    schluessel.chmod(0o600)
    ordnung = verzeichnis / f"ordnung-{rolle.replace('/', '-')}.json"
    ordnung.write_text(json.dumps({"schema_version": 2, "rollen": {rolle: {
        "schluessel_sha256": hashlib.sha256(schluessel.read_bytes()).hexdigest(),
        "schluesselklasse": klasse, "gates": list(gates)}}}), encoding="utf-8")
    return schluessel, ordnung


@pytest.fixture(scope="module")
def zwei_tage(tmp_path_factory):
    """Ablage mit zwei gruenen Laeufen (31.1. und 3.2.; der 3.2. schreibt
    den Monatsabschluss zum 1.2.)."""
    ablage = _ablage(tmp_path_factory.mktemp("zwei") / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage.wurzel


@pytest.fixture()
def gefuehrt(zwei_tage, tmp_path):
    return _kopie(zwei_tage, tmp_path / "plv")


@pytest.fixture(scope="module")
def mit_eingang(tmp_path_factory):
    """Ablage mit registriertem Eingang (Stichtag 1.1.) und Laeufen am 9.1.
    und 3.2. — der Eingang tritt am 9.1. ein, der 3.2. schreibt den
    Monatsabschluss zum 1.2."""
    wurzel = tmp_path_factory.mktemp("ueb")
    fall = _fall(wurzel / "faelle")
    ablage = Ablage(wurzel / "daten")
    ablage.configs.mkdir(parents=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    ueb.eingang_anlegen(ablage.wurzel, fall, STICHTAG, schluesselring=TESTRING)
    assert tageslauf(ablage, dt.date(2026, 1, 9))[0] == EXIT_OK
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage.wurzel


@pytest.fixture()
def uebernommen(mit_eingang, tmp_path):
    return _kopie(mit_eingang, tmp_path / "daten")


# --------------------------------------------------------------------------- #
# A. Die Schluesselklasse betrieb in der Zeichnungsordnung
# --------------------------------------------------------------------------- #


def test_die_ordnung_kennt_die_betriebsrolle_und_sonst_nichts_neues(tmp_path):
    """Mutationsprobe: die Kopplung Ebene betrieb <-> Klasse betrieb oder die
    leere gates-Liste entfernen -> rot."""
    assert "betrieb" in SCHLUESSELKLASSEN and "betrieb" not in ZEICHNENDE_KLASSEN
    ablage = tmp_path / "ablage"
    ablage.mkdir()

    def lade(rollen: dict):
        pfad = tmp_path / "ordnung.json"
        pfad.write_text(json.dumps({"schema_version": 2, "rollen": rollen}), encoding="utf-8")
        return lade_zeichnungsordnung(str(pfad), ablage)

    fp = "a" * 64
    ordnung, _sha, fehler = lade({"betrieb/tageslauf": {
        "schluessel_sha256": fp, "schluesselklasse": "betrieb", "gates": []}})
    assert fehler == [] and ordnung is not None
    # Der Betrieb zeichnet Urheberschaft, nie ein Gate.
    assert not rolle_darf_gate(ordnung, "betrieb/tageslauf", "A-M4")
    for rolle, klasse, gates, stichwort in [
        ("betrieb/tageslauf", "mensch", [], "gehoeren zusammen"),
        ("betrieb/tageslauf", "agent", [], "gehoeren zusammen"),
        ("mensch/betrieb", "betrieb", [], "gehoeren zusammen"),
        ("betrieb/tageslauf", "betrieb", ["A-B1"], "nie ein Gate"),
    ]:
        _o, _s, fehler = lade({rolle: {"schluessel_sha256": fp, "schluesselklasse": klasse,
                                       "gates": gates}})
        assert any(stichwort in f for f in fehler), (rolle, klasse, fehler)
    # Kein P9-Snapshot nimmt eine Betriebszeichnung als Abnahme an.
    assert validiere_zeichnung({"rolle": "betrieb/tageslauf", "ordnung_sha256": "b" * 64,
                                "schluesselklasse": "betrieb"}, form="neu")


# --------------------------------------------------------------------------- #
# C. Jede Zeile gezeichnet, jede Zeile geprueft
# --------------------------------------------------------------------------- #


def test_jede_protokollzeile_ist_gezeichnet_und_pruefbar(gefuehrt):
    """Unabhaengige Kontrollrechnung: HMAC-SHA256 von Hand ueber die
    kanonische Zeile ohne das Signaturfeld."""
    zeilen = lies_protokoll(gefuehrt.protokoll_pfad)
    assert zeilen and all(z["schema_version"] == 3 for z in zeilen)
    for z in zeilen:
        kopf = z["zeichnung"]
        assert kopf["rolle"] == BETRIEBSROLLE and kopf["schluesselklasse"] == "betrieb"
        assert kopf["schluessel_sha256"] == hashlib.sha256(BETRIEBSKEY).hexdigest()
        rumpf = {k: v for k, v in z.items() if k != "zeichnung"}
        rumpf["zeichnung"] = {k: v for k, v in kopf.items() if k != "signatur"}
        nachricht = json.dumps(rumpf, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        assert kopf["signatur"] == hmac.new(BETRIEBSKEY, nachricht, hashlib.sha256).hexdigest()
    # Eine frische Ablage hat keinen ungezeichneten Vorlauf.
    assert "vorlauf" not in zeilen[0]


def test_eine_veraenderte_zeile_haelt_den_lauf_an(gefuehrt, tmp_path):
    """Die letzte Zeile hat keinen Nachfolger, der sie bindet — jetzt bindet
    sie ihre Signatur. Mutationsprobe: die Signaturpruefung im Leser
    entfernen -> rot."""
    rohe = _rohe(gefuehrt)
    zeile = json.loads(rohe[-1])
    zeile["image_tag"] = "umgeschrieben"
    rohe[-1] = _dump(zeile)
    _schreibe(gefuehrt, rohe)
    with pytest.raises(tl.TageslaufError, match="Signatur stimmt nicht"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))
    with pytest.raises(st.SeiteError, match="Signatur stimmt nicht"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


def test_eine_fremd_gezeichnete_zeile_ist_kein_nachweis(gefuehrt, tmp_path):
    """Eine Zeile unter einem Schluessel, den die Ordnung keiner Rolle gibt
    oder der nicht bereitgestellt ist, ist im Betrieb kein Nachweis — der
    Konsument ohne Schluessel prueft die Form und behauptet nichts."""
    rohe = _rohe(gefuehrt)
    zeile = json.loads(rohe[-1])
    fremd = hashlib.sha256(b"ein anderer betriebsschluessel").digest()
    rest = {k: v for k, v in zeile.items() if k != "zeichnung"}
    rohe[-1] = _dump({**rest, "zeichnung": ak.zeichne(rest, fremd, rolle=BETRIEBSROLLE,
                                                       klasse="betrieb")})
    _schreibe(gefuehrt, rohe)
    with pytest.raises(tl.TageslaufError, match="passen nicht zur Zeichnungsordnung"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))
    # Der Schluessel der Zeile ist nicht im Ring: "nicht pruefbar" ist ein
    # harter Befund, keine Freigabe.
    with pytest.raises(tl.TageslaufError, match="nicht pruefbar"):
        lies_protokoll(gefuehrt.protokoll_pfad, schluesselring={})
    # Ohne Ring: Form in Ordnung, keine Behauptung.
    assert len(lies_protokoll(gefuehrt.protokoll_pfad)) == len(rohe)


def test_eine_herabgestufte_zeile_ist_ein_kettenbruch(gefuehrt, tmp_path):
    """RC10: Eine Zeile mit Schema 1 hinter gezeichneten Zeilen schaltete
    Kette, Tagesfolge und Nachweis ab. Mutationsprobe: die Pruefung auf
    fallendes Schema entfernen -> rot."""
    rohe = _rohe(gefuehrt)
    letzte = json.loads(rohe[-1])
    herab = {k: v for k, v in letzte.items() if k not in ("zeichnung", "vorgaenger_sha256")}
    herab["schema_version"] = 1
    herab["bestand"] = {**herab["bestand"], "in_force": herab["bestand"]["in_force"] + 1000}
    _schreibe(gefuehrt, rohe + [_dump(herab)])
    for lesen in (lambda: lies_protokoll(gefuehrt.protokoll_pfad),     # Konsument, ohne Ring
                  lambda: tageslauf(gefuehrt, dt.date(2026, 2, 4))):
        with pytest.raises(tl.TageslaufError, match="Schema 1 hinter einer Zeile mit Schema 3"):
            lesen()
    # Dieselbe Herabstufung an Ort und Stelle (MAX: die letzte Zeile selbst).
    _schreibe(gefuehrt, rohe[:-1] + [_dump(herab)])
    with pytest.raises(tl.TageslaufError, match="Schema 1 hinter"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))


def test_eine_zweite_gruene_zeile_fuer_denselben_tag_wird_nicht_angenommen(gefuehrt, tmp_path):
    """RC11: kettenrichtig angefuegt und (Faelscher mit Schluessel) gezeichnet.
    Mutationsprobe: in pruefe_nachweis die Tagesfolge nur bei Schema >= 2 und
    ohne ``<=`` pruefen -> rot."""
    rohe = _rohe(gefuehrt)
    zweite = json.loads(rohe[-1])
    zweite["vorgaenger_sha256"] = hashlib.sha256(rohe[-1].encode("utf-8")).hexdigest()
    zweite["gefuehrt_vorher"] = zweite["heute"]
    zweite["nachgeholt"] = []
    _schreibe(gefuehrt, rohe + [_dump(zeichne_neu(zweite))])
    with pytest.raises(tl.TageslaufError, match="zwei gruene Zeilen"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))
    with pytest.raises(st.SeiteError, match="zwei gruene Zeilen"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


@pytest.mark.parametrize("feld,wert", [("in_kraft", 1016), ("zugaenge", 5000), ("leistungen", 777)])
def test_die_monatskennzahlen_werden_nachgerechnet(gefuehrt, tmp_path, feld, wert):
    """RC12, Faelscher mit Schluessel. Soll unabhaengig: in_kraft ist die
    Zeilenzahl der Abschlussdatei. Mutationsprobe: in
    _pruefe_zahlen_der_zeile die Abschlussschleife entfernen -> rot."""
    zeile = lies_protokoll(gefuehrt.protokoll_pfad)[-1]
    feb = next(a for a in zeile["abschluesse"] if a["stichtag"] == "2026-02-01")
    assert feb["in_kraft"] == len(read_portfolio(gefuehrt.abschluesse / feb["datei"]))

    def faelsche(z):
        next(a for a in z["abschluesse"] if a["stichtag"] == "2026-02-01")[feld] = wert

    _letzte_neu(gefuehrt, faelsche)
    with pytest.raises(st.SeiteError, match=rf"abschluesse\[2026-02-01\]\.{feld}"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    with pytest.raises(tl.TageslaufError, match=rf"abschluesse\[2026-02-01\]\.{feld}"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))


def test_der_konsument_rechnet_die_kennzahlen_ohne_schluessel_nach(gefuehrt, tmp_path):
    """RC12 beim Konsumenten: ``abschluesse_aus_protokoll`` ergaenzte nur
    FEHLENDE Felder. Mutationsprobe: in _gleich_oder_setzen nur setzen ->
    rot."""
    zeilen = lies_protokoll(gefuehrt.protokoll_pfad)
    for a in zeilen[-1]["abschluesse"]:
        a["in_kraft"] = 1016
    with pytest.raises(st.SeiteError, match="in_kraft 1016"):
        st.abschluesse_aus_protokoll(zeilen, abschluesse_dir=gefuehrt.abschluesse)


def test_ein_ersetzter_abschluss_wird_bemerkt(gefuehrt):
    """RC12(b): Ein festgeschriebener Abschluss wurde nach seinem Lauf nie
    wieder geprueft. Mutationsprobe: _pruefe_festgeschriebene_abschluesse
    nicht rufen -> rot (die Zeile selbst ist unveraendert)."""
    pfad = gefuehrt.abschluesse / "abschluss_2026-02-01.parquet"
    tabelle = read_portfolio(pfad)
    assert len(tabelle) == 16
    pfad.chmod(0o644)
    write_portfolio(tabelle.head(3), pfad)
    with pytest.raises(tl.TageslaufError, match="nicht der Abschluss, den das Protokoll bezeugt"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))


@pytest.mark.parametrize("feld", ["stichtag", "zeichnung", "snapshot_sha256"])
def test_die_uebernahmeangaben_folgen_aus_dem_eingang(uebernommen, tmp_path, feld):
    """RC13, Faelscher mit Schluessel: Stichtag, Zeichnung und Snapshot der
    A-M4-Annahme stehen in eingang.json. Mutationsprobe: den Feldvergleich
    gegen eingang.json entfernen -> rot."""
    wert = {"stichtag": "2025-07-01", "snapshot_sha256": "0" * 64,
            "zeichnung": {"entscheider": "Vorstand (erfunden)"}}[feld]

    def faelsche(z):
        u = z["uebernahmen"][0]
        u[feld] = {**u[feld], **wert} if isinstance(wert, dict) else wert

    _letzte_neu(uebernommen, faelsche)
    with pytest.raises(st.SeiteError, match=rf"uebernahmen\[probe-uebernahme\]\.{feld}"):
        st.stands_paket(uebernommen, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


@pytest.mark.parametrize("feld,wert", [
    ("config_sha256", "c" * 64),
    ("kern_version", "9.9.9"),
    ("verankerung", {"angewandt": True, "registriert": 999, "hinweis": "erfunden"}),
])
def test_provenienz_und_verankerung_folgen_aus_dem_stand(gefuehrt, tmp_path, feld, wert):
    """RC13, Faelscher mit Schluessel; Soll aus dem Manifest, das die Zeile
    ueber manifest_sha256 bindet. Mutationsprobe: zeile_gegen_manifest leer
    zurueckgeben -> rot (Export UND Konsument)."""
    _letzte_neu(gefuehrt, lambda z: z.__setitem__(feld, wert))
    with pytest.raises(st.SeiteError, match=feld):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    manifest = json.loads((gefuehrt.stand / "laufmanifest.json").read_text(encoding="utf-8"))
    assert feld in " ".join(tl.zeile_gegen_manifest(lies_protokoll(gefuehrt.protokoll_pfad)[-1],
                                                     manifest))


# --------------------------------------------------------------------------- #
# D. Ohne Betriebsschluessel kein Tag; nur die Klasse betrieb zeichnet
# --------------------------------------------------------------------------- #


def test_ohne_betriebsschluessel_kein_tageslauf(tmp_path, monkeypatch):
    """Mutationsprobe: in betriebszeichner still ohne Schluessel weiterlaufen
    -> rot."""
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    ablage = _ablage(tmp_path / "plv")
    with pytest.raises(tl.TageslaufError, match="ohne Betriebsschluessel kein Tageslauf.*--schluessel"):
        tageslauf(ablage, dt.date(2026, 1, 31))
    assert not ablage.protokoll_pfad.exists() and not ablage.stand.exists()
    with pytest.raises(st.SeiteError, match="ohne Betriebsschluessel kein Export"):
        st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


@pytest.mark.parametrize("rolle,klasse", [("mensch/betrieb", "mensch"), ("agent/betrieb", "agent")])
def test_ein_menschen_oder_agentenschluessel_zeichnet_keine_protokollzeile(tmp_path, rolle, klasse):
    """Mutationsprobe: verlange_betrieb nicht rufen -> rot."""
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, rolle, klasse)
    ablage = _ablage(tmp_path / "plv")
    with pytest.raises(tl.TageslaufError, match=f"Schluesselklasse '{klasse}'.*Ausweg"):
        tageslauf(ablage, dt.date(2026, 1, 31), schluessel=schluessel, zeichnungsordnung=ordnung)
    assert not ablage.protokoll_pfad.exists()


def test_der_ausdrueckliche_betriebsschluessel_zeichnet(tmp_path, monkeypatch):
    """Positivkontrolle ohne Naht: ein eigener Betriebsschluessel zeichnet,
    und die Zeile nennt seinen Fingerabdruck. Ein Schluessel in der Ablage
    wird abgewiesen."""
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, "betrieb/nachtlauf", "betrieb")
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31), schluessel=schluessel,
                     zeichnungsordnung=ordnung)[0] == EXIT_OK
    kopf = lies_protokoll(ablage.protokoll_pfad)[-1]["zeichnung"]
    assert kopf["rolle"] == "betrieb/nachtlauf"
    assert kopf["schluessel_sha256"] == hashlib.sha256(schluessel.read_bytes()).hexdigest()
    innen = ablage.wurzel / "betrieb.key"
    shutil.copyfile(schluessel, innen)
    innen.chmod(0o600)
    with pytest.raises(tl.TageslaufError, match="innerhalb des Vertrauensraums"):
        tageslauf(ablage, dt.date(2026, 2, 1), schluessel=innen, zeichnungsordnung=ordnung)


def test_die_cli_verlangt_schluessel_und_ordnung(tmp_path, capsys):
    ablage = _ablage(tmp_path / "plv")
    with pytest.raises(SystemExit) as fehler:
        tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-31"])
    assert fehler.value.code == 2
    assert "--schluessel" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Aufschaltung: eine Ablage mit ungezeichnetem Vorlauf
# --------------------------------------------------------------------------- #


def _als_altes_protokoll(ablage: Ablage, aendern=lambda i, z: None) -> list:
    """Das Protokoll in die Form vor Runde C bringen: Schema 2, ohne
    Zeichnung, Kette neu gerechnet — wie eine Ablage, die vor dem
    Betriebsschluessel gefuehrt wurde. Mit ``aendern`` zugleich die Probe
    des Pruefers (Fall A): dieselbe Herabstufung OHNE Schluessel, mit
    gefaelschten Zahlen — aus der Ablage allein nicht vom Altbestand zu
    unterscheiden."""
    neu = []
    for i, roh in enumerate(_rohe(ablage)):
        z = {k: v for k, v in json.loads(roh).items() if k not in ("zeichnung", "vorlauf")}
        z["schema_version"] = 2
        aendern(i, z)
        z["vorgaenger_sha256"] = hashlib.sha256(neu[-1].encode("utf-8")).hexdigest() if neu else ""
        neu.append(_dump(z))
    _schreibe(ablage, neu)
    return neu


def test_eine_alte_ablage_wird_aufgeschaltet_und_ihr_vorlauf_gepinnt(gefuehrt):
    """Mutationsprobe: den Vorlauf-Pin im Leser nicht vergleichen -> rot.

    Aufgeschaltet wird nur AUSDRUECKLICH (``aufschalten=True``, einmal beim
    ersten Lauf nach dem Umstieg); ein zweites Aufschalten auf ein
    gezeichnetes Protokoll wird VERWEIGERT, nicht still uebergangen — ein
    Schalter, der dauerhaft im Timer stuende, oeffnete die Herabstufung
    wieder."""
    alt = _als_altes_protokoll(gefuehrt)
    assert tageslauf(gefuehrt, dt.date(2026, 2, 4), aufschalten=True)[0] == EXIT_OK
    zeilen = lies_protokoll(gefuehrt.protokoll_pfad)
    assert [z["schema_version"] for z in zeilen] == [2] * len(alt) + [3]
    # Unabhaengig nachgerechnet: Zahl und Hash der rohen Zeilen mit Zeilenende.
    assert zeilen[-1]["vorlauf"] == {
        "zeilen": len(alt),
        "sha256": hashlib.sha256(("\n".join(alt) + "\n").encode("utf-8")).hexdigest()}
    # Ein zweites Aufschalten: verweigert, keine Zeile, Ausweg genannt.
    vorher = gefuehrt.protokoll_pfad.read_bytes()
    with pytest.raises(tl.TageslaufError, match="schon gezeichnet.*ohne --aufschalten"):
        tageslauf(gefuehrt, dt.date(2026, 2, 5), aufschalten=True)
    assert gefuehrt.protokoll_pfad.read_bytes() == vorher
    assert tageslauf(gefuehrt, dt.date(2026, 2, 5))[0] == EXIT_OK
    assert "vorlauf" not in lies_protokoll(gefuehrt.protokoll_pfad)[-1]

    # Danach den Vorlauf stimmig umschreiben (Kette der Schema-2-Zeilen
    # nachgerechnet; die erste gezeichnete Zeile nennt den neuen letzten
    # Vorlauf-Hash) -> der Pin haelt.
    rohe = _rohe(gefuehrt)
    erste = json.loads(rohe[0])
    erste["image_tag"] = "umgeschrieben"
    vorlauf = [_dump(erste)]
    for roh in rohe[1:len(alt)]:
        z = json.loads(roh)
        z["vorgaenger_sha256"] = hashlib.sha256(vorlauf[-1].encode("utf-8")).hexdigest()
        vorlauf.append(_dump(z))
    gezeichnet = json.loads(rohe[len(alt)])
    gezeichnet["vorgaenger_sha256"] = hashlib.sha256(vorlauf[-1].encode("utf-8")).hexdigest()
    rest = [_dump(zeichne_neu(gezeichnet))]
    for roh in rohe[len(alt) + 1:]:
        z = json.loads(roh)
        z["vorgaenger_sha256"] = hashlib.sha256(rest[-1].encode("utf-8")).hexdigest()
        rest.append(_dump(zeichne_neu(z)))
    _schreibe(gefuehrt, vorlauf + rest)
    with pytest.raises(tl.TageslaufError, match="Vorlauf"):
        tageslauf(gefuehrt, dt.date(2026, 2, 6))


# --------------------------------------------------------------------------- #
# E. Der Eingang: gezeichnet, gehalten, und registriert nur, was eintritt
# --------------------------------------------------------------------------- #


def test_der_eingang_ist_gezeichnet_und_eine_aenderung_faellt(uebernommen, tmp_path):
    """Mutationsprobe: in lies_uebernahme die Betriebszeichnung nicht pruefen
    -> rot."""
    kopf = uebernommen.uebernahme / "probe-uebernahme" / "eingang.json"
    daten = json.loads(kopf.read_text(encoding="utf-8"))
    assert daten["schema_version"] == 3
    assert daten["betriebszeichnung"]["rolle"] == BETRIEBSROLLE
    assert daten["zeichnung"]["signatur_verifiziert"] is True
    ring = {hashlib.sha256(BETRIEBSKEY).hexdigest(): BETRIEBSKEY}
    assert ueb.betriebszeichnung_des_eingangs_fehler(daten, ring, betriebsordnung()) is None
    daten["zeichnung"]["signatur_verifiziert"] = False
    assert "Signatur stimmt nicht" in str(
        ueb.betriebszeichnung_des_eingangs_fehler(daten, ring, betriebsordnung()))
    # Auf der Platte, beim Lesen mit Ring: der Leser verweigert.
    from rechner_pipeline.bestand.config import config_aus_text

    daten["zeichnung"]["signatur_verifiziert"] = True
    daten["stichtag"] = "2026-01-02"
    kopf.chmod(0o644)
    kopf.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="Signatur stimmt nicht"):
        ueb.lies_uebernahme(kopf.parent, config_aus_text(_kleine_config()),
                            schluesselring=ring, ordnung=betriebsordnung())


def test_ein_bezeugter_eingang_verschwindet_nicht(uebernommen):
    """RC14: gegen ALLE je bezeugten Eingaenge, nicht nur die der letzten
    Zeile. Die Zeilen hier bezeugen den Eingang; die Ablage hat ihn nicht
    mehr. Mutationsprobe: _pruefe_bezeugte_eingaenge leer lassen -> rot."""
    zeilen = lies_protokoll(uebernommen.protokoll_pfad)
    shutil.rmtree(uebernommen.uebernahme / "probe-uebernahme")
    with pytest.raises(tl.TageslaufError, match="nicht mehr in der Ablage.*Ausweg|nicht mehr in der Ablage.*wiederherstellen"):
        tl._pruefe_bezeugte_eingaenge(uebernommen, zeilen)
    # Auch wenn die letzte Zeile ihn nicht mehr nennt (Faelscher mit Schluessel):
    _letzte_neu(uebernommen, lambda z: z.__setitem__("uebernahmen", []))
    with pytest.raises(tl.TageslaufError):
        tageslauf(uebernommen, dt.date(2026, 2, 4))


def test_eine_nach_dem_eintritt_umgeschriebene_tabelle_haelt_den_lauf_an(uebernommen):
    """RC15: Versicherungssummen mal zehn, eingang.json stimmig nachgezogen.
    Mutationsprobe: in _pruefe_bezeugte_eingaenge die Tabellen nicht gegen
    eingang.json halten und den Signaturvergleich entfernen -> rot."""
    verzeichnis = uebernommen.uebernahme / "probe-uebernahme"
    tabelle = verzeichnis / "bestand.parquet"
    stamm = read_portfolio(tabelle)
    stamm["sum_insured"] = stamm["sum_insured"] * 10
    tabelle.chmod(0o644)
    write_portfolio(stamm, tabelle)
    zeilen = lies_protokoll(uebernommen.protokoll_pfad)
    with pytest.raises(tl.TageslaufError, match="bestand.parquet fehlt oder traegt nicht den Hash"):
        tl._pruefe_bezeugte_eingaenge(uebernommen, zeilen)
    kopf = verzeichnis / "eingang.json"
    kopf.chmod(0o644)
    daten = json.loads(kopf.read_text(encoding="utf-8"))
    daten["dateien"]["bestand.parquet"] = hashlib.sha256(tabelle.read_bytes()).hexdigest()
    kopf.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    with pytest.raises(tl.TageslaufError, match="eingang"):
        tageslauf(uebernommen, dt.date(2026, 2, 4))


def test_ein_ungezeichneter_neuer_eingang_tritt_nicht_ein(uebernommen, tmp_path):
    """Ein Eingang nach Schema 2 (ohne Betriebszeichnung) tritt nur ein, wenn
    eine gezeichnete Zeile ihn schon bezeugt. Mutationsprobe: die
    bezeugt-Bedingung in lies_uebernahme entfernen -> rot."""
    fall = _fall(tmp_path / "faelle", "zweiter-fall")
    ziel = ueb.eingang_anlegen(uebernommen.wurzel, fall, dt.date(2026, 2, 4),
                               schluesselring=TESTRING)
    kopf = ziel / "eingang.json"
    daten = json.loads(kopf.read_text(encoding="utf-8"))
    daten.pop("betriebszeichnung")
    daten["schema_version"] = 2
    kopf.chmod(0o644)
    kopf.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    code, zeile = tageslauf(uebernommen, dt.date(2026, 2, 4))
    assert code != EXIT_OK and (
        "weder eine gezeichnete Protokollzeile noch der gepinnte Vorlauf bezeugt ihn"
        in str(zeile["fehler"]))


def test_registriert_wird_nur_ein_tarifwerk_das_der_tageslauf_annimmt(tmp_path):
    """RC16. Soll unabhaengig: die Schalter der Config-Generation, direkt aus
    der Config gelesen, gegen die Schalter des Belegs. Mutationsprobe:
    _pruefe_tarifwerk_gegen_ablage nicht rufen -> rot."""
    import tomllib

    fall = _fall(tmp_path / "faelle")
    abweichend = {"scheiben_mit_gamma1": True, "stoab_je_baustein": True, "red_verfahren": "prospektiv"}
    uebernahmebeleg(fall / "abgeleitet" / "bestand", 3, tarifwerk=abweichend)
    _beleg_neu(fall)
    ablage = Ablage(tmp_path / "daten")
    ablage.configs.mkdir(parents=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    config = tomllib.loads(ablage.config_pfad.read_text(encoding="utf-8"))
    gen = next(g for g in config["generation"] if g["name"] == "KLV-2017")
    assert any(gen.get(k, False) != v for k, v in abweichend.items() if k != "red_verfahren")
    with pytest.raises(ueb.UebernahmeError, match="nichts registriert.*generation-zellen.toml"):
        ueb.eingang_anlegen(ablage.wurzel, fall, STICHTAG, schluesselring=TESTRING)
    assert not (ablage.uebernahme / "probe-uebernahme").exists()
    # Positivkontrolle: der passende Beleg wird registriert.
    uebernahmebeleg(fall / "abgeleitet" / "bestand", 3)
    _beleg_neu(fall)
    assert ueb.eingang_anlegen(ablage.wurzel, fall, STICHTAG, schluesselring=TESTRING).is_dir()


def test_der_konsument_behauptet_die_signatur_nicht(gefuehrt, tmp_path):
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    modell = fd.betrieb(paket, tmp_path / "anker" / ak.ANKER_DATEI)
    assert modell["protokoll_zeichnung"]["signatur"] == "nicht pruefbar"


# --------------------------------------------------------------------------- #
# F. Nachbesserung: Aufschaltung nur ausdruecklich (Probe des Pruefers, Fall A)
# --------------------------------------------------------------------------- #


def _faelsche_erste_zeile(i: int, z: dict) -> None:
    if i == 0:
        z["bestand"] = {**z["bestand"], "in_force": 999}


def test_ein_ohne_schluessel_herabgestuftes_protokoll_wird_nicht_gezeichnet(gefuehrt, tmp_path):
    """Probe des Pruefers, Fall A und D: Ohne Schluessel jede Zeichnung und
    jeden Pin entfernt, eine Zahl gefaelscht, die Kette neu verkettet. Vorher
    pinnte der naechste Tageslauf diese Geschichte als Vorlauf und zeichnete
    sie damit, und der Export nahm sie an. Jetzt: kein Lauf, keine Zeile, kein
    Paket — der Ausweg nennt beide Lesarten. Mutationsprobe: die
    Aufschaltungsregel (tageslauf.aufschaltung_fehler) immer None liefern
    lassen -> rot."""
    _als_altes_protokoll(gefuehrt, _faelsche_erste_zeile)
    vorher = gefuehrt.protokoll_pfad.read_bytes()
    with pytest.raises(tl.TageslaufError,
                       match="keine gezeichnete Zeile.*--aufschalten.*Sicherung"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))
    assert gefuehrt.protokoll_pfad.read_bytes() == vorher
    assert lies_protokoll(gefuehrt.protokoll_pfad)[0]["bestand"]["in_force"] == 999
    # Der Schreiber selbst haelt die Regel, nicht nur sein Aufrufer.
    # Mutationsprobe: die Pruefung in _anfuegen entfernen -> rot.
    with pytest.raises(tl.TageslaufError, match="keine gezeichnete Zeile"):
        tl._anfuegen(gefuehrt.protokoll_pfad, {"heute": "2026-02-04", "uebernommen": False},
                     tl.betriebszeichner(gefuehrt))
    assert gefuehrt.protokoll_pfad.read_bytes() == vorher
    with pytest.raises(st.SeiteError, match="keine gezeichnete Zeile.*--aufschalten"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert not (tmp_path / "paket").exists()
    assert not (tmp_path / "anker" / ak.ANKER_DATEI).exists()


def test_die_cli_verweigert_das_herabgestufte_protokoll(gefuehrt, tmp_path, capsys):
    """Probe des Pruefers (probe_cli.py) im Produktionspfad: Schluessel und
    Ordnung ausdruecklich uebergeben, und trotzdem Exit 2 mit Ausweg."""
    from tests.freigabe_testschluessel import betriebsargs

    _als_altes_protokoll(gefuehrt, lambda i, z: z.update(image_tag="gefaelscht") if i == 0 else None)
    vorher = gefuehrt.protokoll_pfad.read_bytes()
    assert tl.main(["--stand", str(gefuehrt.wurzel), "--heute", "2026-02-04",
                    *betriebsargs()]) == tl.EXIT_USAGE
    assert "--aufschalten" in capsys.readouterr().err
    assert gefuehrt.protokoll_pfad.read_bytes() == vorher
    assert st.main(["--stand", str(gefuehrt.wurzel), "--paket", str(tmp_path / "paket"),
                    "--anker", str(tmp_path / "anker"),
                    *betriebsargs("--betriebsschluessel")]) == 2
    assert "--aufschalten" in capsys.readouterr().err and not (tmp_path / "paket").exists()
    # Mit dem einmaligen Schalter laeuft der Tag (Altbestand) und pinnt den Vorlauf.
    assert tl.main(["--stand", str(gefuehrt.wurzel), "--heute", "2026-02-04", "--aufschalten",
                    *betriebsargs()]) == EXIT_OK
    assert "vorlauf" in lies_protokoll(gefuehrt.protokoll_pfad)[-1]
    assert tl.main(["--stand", str(gefuehrt.wurzel), "--heute", "2026-02-05", "--aufschalten",
                    *betriebsargs()]) == tl.EXIT_USAGE
    assert "schon gezeichnet" in capsys.readouterr().err


def test_eine_alte_ablage_mit_altem_eingang_wird_aufgeschaltet(uebernommen):
    """Der echte Altbestand: Protokoll UND eingang.json vor dem
    Betriebsschluessel (Schema 2, ungezeichnet). Ohne Schalter verweigert;
    mit ihm tritt der alte Eingang weiter an, weil der Vorlauf, den dieser
    Lauf pinnt, ihn bezeugt — und danach bezeugt ihn der gepinnte Vorlauf."""
    kopf = uebernommen.uebernahme / "probe-uebernahme" / "eingang.json"
    daten = json.loads(kopf.read_text(encoding="utf-8"))
    daten.pop("betriebszeichnung")
    daten["schema_version"] = 2
    kopf.chmod(0o644)
    kopf.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    alt_hash = hashlib.sha256(kopf.read_bytes()).hexdigest()
    # Der Stand eines Altbestands nennt dieselbe eingang.json im Manifest.
    manifest = (uebernommen.stand / "laufmanifest.json").resolve()
    manifest.parent.chmod(0o755)
    manifest.chmod(0o644)
    m = json.loads(manifest.read_text(encoding="utf-8"))
    for rolle, eintrag in m["eingaben"].items():
        if rolle.startswith("uebernahme:"):
            eintrag["sha256"] = alt_hash
    manifest.write_text(json.dumps(m, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    letzte_gruene = max(i for i, r in enumerate(_rohe(uebernommen)) if json.loads(r).get("uebernommen"))

    def eingang_neu(i, z):
        for u in z.get("uebernahmen") or []:
            if u.get("eingang_sha256"):
                u["eingang_sha256"] = alt_hash
        if i == letzte_gruene:
            z["manifest_sha256"] = manifest_hash

    _als_altes_protokoll(uebernommen, eingang_neu)
    zeilen = lies_protokoll(uebernommen.protokoll_pfad)
    assert tl.bezeugte_eingaenge(zeilen) == {}
    assert tl.bezeugte_eingaenge(zeilen, aufschalten=True) == {"probe-uebernahme": alt_hash}
    with pytest.raises(tl.TageslaufError, match="keine gezeichnete Zeile"):
        tageslauf(uebernommen, dt.date(2026, 2, 4))
    code, zeile = tageslauf(uebernommen, dt.date(2026, 2, 4), aufschalten=True)
    assert code == EXIT_OK, zeile.get("fehler")
    zeilen = lies_protokoll(uebernommen.protokoll_pfad)
    assert zeilen[-1]["vorlauf"]["zeilen"] == len(zeilen) - 1
    assert tl.bezeugte_eingaenge(zeilen) == {"probe-uebernahme": alt_hash}
    assert tageslauf(uebernommen, dt.date(2026, 2, 5))[0] == EXIT_OK


def test_ein_zweites_aufschalten_nach_herabstufung_faellt_am_anker(gefuehrt, tmp_path):
    """Die ehrliche Grenze: Ist ein gezeichnetes Protokoll ohne Schluessel
    wieder herabgestuft, sieht es in der Ablage aus wie ein Altbestand — wer
    dann noch einmal aufschaltet, bekommt einen Lauf. Den Bezug nach aussen
    liefert der Anker: Die Zeile, die der letzte Export verankert hat, gibt
    es nicht mehr, und der naechste Export verweigert (Kettenbruch, kein
    zweiter Aufschaltfall)."""
    st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    _als_altes_protokoll(gefuehrt, _faelsche_erste_zeile)
    assert tageslauf(gefuehrt, dt.date(2026, 2, 4), aufschalten=True)[0] == EXIT_OK
    with pytest.raises(st.SeiteError, match="Anker|verankert"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


def test_eine_leere_ablage_braucht_keinen_schalter_und_nimmt_keinen(tmp_path):
    """Erstbefuellung: nichts aufzuschalten. Der Schalter auf ein leeres
    Protokoll wird verweigert — er ist nie ein stilles No-op."""
    ablage = _ablage(tmp_path / "plv")
    with pytest.raises(tl.TageslaufError, match="nichts aufzuschalten"):
        tageslauf(ablage, dt.date(2026, 1, 31), aufschalten=True)
    assert not ablage.protokoll_pfad.exists()
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK


def test_neuaufsetzen_verweigert_ein_protokoll_ohne_gezeichnete_zeile(gefuehrt, tmp_path):
    """Neuaufsetzen archiviert die alte Ablage — ein herabgestuftes Protokoll
    wuerde damit still zur Geschichte. Ohne Schalter verweigert, nichts
    bewegt; mit ihm (Altbestand) wird aufgebaut."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    _als_altes_protokoll(gefuehrt)
    fall = _fall_mit_nebentabellen(tmp_path / "f")
    with pytest.raises(na.NeuaufsetzenError, match="keine gezeichnete Zeile.*--aufschalten"):
        na.neu_aufsetzen(gefuehrt.wurzel, fall, STICHTAG)
    assert gefuehrt.stand.exists() and not list(tmp_path.glob("plv.archiv-*"))
    assert not list(tmp_path.glob("plv.neu-*"))
    na.neu_aufsetzen(gefuehrt.wurzel, fall, STICHTAG, aufschalten=True)
    assert len(list(tmp_path.glob("plv.archiv-*"))) == 1


# --------------------------------------------------------------------------- #
# G. Nachbesserung: eine vollstaendige Endzeile ohne Umbruch bleibt (Fall C)
# --------------------------------------------------------------------------- #


def test_eine_vollstaendige_endzeile_ohne_umbruch_wird_abgeschlossen(tmp_path):
    """Nur ein Fragment, das kein vollstaendiges JSON-Objekt ist, wird
    geschnitten. Mutationsprobe: den Abschluss entfernen (immer schneiden)
    -> rot."""
    pfad = tmp_path / "protokoll.jsonl"
    voll = b'{"heute": "2026-01-01"}\n'
    letzte = b'{"heute": "2026-01-02", "uebernommen": false}'
    pfad.write_bytes(voll + letzte)
    assert tl._schneide_teilzeile(pfad) is True
    assert pfad.read_bytes() == voll + letzte + b"\n"
    assert tl._schneide_teilzeile(pfad) is False
    # Eine Liste oder ein Skalar ist keine Protokollzeile — Fragment.
    pfad.write_bytes(voll + b"[1, 2]")
    assert tl._schneide_teilzeile(pfad) is True and pfad.read_bytes() == voll


def test_eine_rote_endzeile_verschwindet_nicht_ohne_schluessel(uebernommen, tmp_path):
    """Probe des Pruefers, Fall C: rote, gezeichnete Endzeile, Umbruch ohne
    Schluessel entfernt. Vorher schnitt das Programm selbst die Zeile weg —
    der rote Lauf war ungeschehen. Jetzt bleibt sie, und der naechste Lauf
    haengt an sie an."""
    fall = _fall(tmp_path / "faelle", "zweiter-fall")
    ziel = ueb.eingang_anlegen(uebernommen.wurzel, fall, dt.date(2026, 2, 4),
                               schluesselring=TESTRING)
    kopf = ziel / "eingang.json"
    daten = json.loads(kopf.read_text(encoding="utf-8"))
    daten.pop("betriebszeichnung")
    daten["schema_version"] = 2
    kopf.chmod(0o644)
    kopf.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")
    code, _ = tageslauf(uebernommen, dt.date(2026, 2, 4))
    assert code != EXIT_OK
    rot = _rohe(uebernommen)[-1]
    roh = uebernommen.protokoll_pfad.read_bytes()
    uebernommen.protokoll_pfad.chmod(0o644)
    uebernommen.protokoll_pfad.write_bytes(roh[:-1])
    shutil.rmtree(ziel)
    assert tageslauf(uebernommen, dt.date(2026, 2, 5))[0] == EXIT_OK
    rohe = _rohe(uebernommen)
    assert rohe[-2] == rot
    assert json.loads(rohe[-1])["vorgaenger_sha256"] == hashlib.sha256(rot.encode("utf-8")).hexdigest()
    assert [z["heute"] for z in lies_protokoll(uebernommen.protokoll_pfad)
            if not z.get("uebernommen")] == ["2026-02-04"]


# --------------------------------------------------------------------------- #
# H. Nachbesserung: drei blinde Tests
# --------------------------------------------------------------------------- #


def test_anfuegen_prueft_die_kette_mit_schluessel_und_ordnung(gefuehrt):
    """_anfuegen direkt, ohne den Tageslauf davor: Eine nach der Pruefung
    veraenderte oder fremd gezeichnete letzte Zeile wird nicht durch eine
    eigene Zeichnung bestaetigt. Mutationsprobe: in _anfuegen schluesselring
    und ordnung auf None -> rot."""
    zeichner = tl.betriebszeichner(gefuehrt)
    rohe = _rohe(gefuehrt)
    zeile = json.loads(rohe[-1])
    rest = {k: v for k, v in zeile.items() if k != "zeichnung"}
    veraendert = {**zeile, "image_tag": "nach der pruefung"}
    fremd = {**rest, "zeichnung": ak.zeichne(
        rest, hashlib.sha256(b"fremder betrieb").digest(), rolle=BETRIEBSROLLE, klasse="betrieb")}
    for letzte, befund in ((veraendert, "Signatur stimmt nicht"),
                           (fremd, "passen nicht zur Zeichnungsordnung")):
        _schreibe(gefuehrt, rohe[:-1] + [_dump(letzte)])
        vorher = gefuehrt.protokoll_pfad.read_bytes()
        with pytest.raises(tl.TageslaufError, match=befund):
            tl._anfuegen(gefuehrt.protokoll_pfad,
                         {"heute": "2026-02-04", "uebernommen": False}, zeichner)
        assert gefuehrt.protokoll_pfad.read_bytes() == vorher


def test_der_leser_ohne_ring_weist_eine_menschenzeichnung_ab(gefuehrt, tmp_path):
    """Ohne Ring und Ordnung (Konsument, falldaten) prueft der Leser die FORM
    — und dazu gehoert: Protokollzeilen zeichnet nur die Klasse betrieb.
    Mutationsprobe: die Rollen-/Klassenpruefung in
    _zeichnung.betriebszeichnung_fehler abschalten -> rot."""
    rohe = _rohe(gefuehrt)
    zeile = json.loads(rohe[-1])
    rest = {k: v for k, v in zeile.items() if k != "zeichnung"}
    rohe[-1] = _dump({**rest, "zeichnung": ak.zeichne(
        rest, hashlib.sha256(b"mensch x").digest(), rolle="mensch/x", klasse="mensch")})
    _schreibe(gefuehrt, rohe)
    with pytest.raises(tl.TageslaufError, match="das zeichnet nur der Betrieb"):
        lies_protokoll(gefuehrt.protokoll_pfad)
    with pytest.raises(tl.TageslaufError, match="das zeichnet nur der Betrieb"):
        tl.lies_protokoll_text(gefuehrt.protokoll_pfad.read_text(encoding="utf-8"), "paket")


def test_cli_tageslauf_reicht_den_schluessel_ausdruecklich_weiter(tmp_path, monkeypatch, capsys):
    """Naht aus: Gezeichnet wird mit genau dem Schluessel der Flags.
    Mutationsprobe: in main die Flags nicht an tageslauf() geben -> rot."""
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, "betrieb/nachtlauf", "betrieb")
    ablage = _ablage(tmp_path / "plv")
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-31",
                    "--schluessel", str(schluessel), "--zeichnungsordnung", str(ordnung)]) == EXIT_OK
    kopf = lies_protokoll(ablage.protokoll_pfad)[-1]["zeichnung"]
    assert kopf["schluessel_sha256"] == hashlib.sha256(schluessel.read_bytes()).hexdigest()
    with pytest.raises(SystemExit) as fehler:
        tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-02-01"])
    assert fehler.value.code == 2
    err = capsys.readouterr().err
    assert "--schluessel" in err and "--zeichnungsordnung" in err


def test_cli_uebernahme_reicht_den_schluessel_ausdruecklich_weiter(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, "betrieb/nachtlauf", "betrieb")
    fall = _fall(tmp_path / "faelle")
    ablage = _ablage(tmp_path / "daten")
    grund = ["--stand", str(ablage.wurzel), "--fall", str(fall), "--stichtag", STICHTAG.isoformat()]
    with pytest.raises(SystemExit) as fehler:
        ueb.main(grund)
    assert fehler.value.code == 2
    assert "--betriebsschluessel" in capsys.readouterr().err
    assert ueb.main([*grund, "--betriebsschluessel", str(schluessel),
                     "--zeichnungsordnung", str(ordnung)]) == 0
    kopf = json.loads((ablage.uebernahme / "probe-uebernahme" / "eingang.json")
                      .read_text(encoding="utf-8"))
    assert kopf["betriebszeichnung"]["schluessel_sha256"] == hashlib.sha256(
        schluessel.read_bytes()).hexdigest()
    assert kopf["betriebszeichnung"]["rolle"] == "betrieb/nachtlauf"


def test_cli_neuaufsetzen_reicht_den_schluessel_ausdruecklich_weiter(tmp_path, monkeypatch, capsys):
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, "betrieb/nachtlauf", "betrieb")
    fall = _fall_mit_nebentabellen(tmp_path / "f")
    ablage = _ablage(tmp_path / "daten")
    grund = ["--stand", str(ablage.wurzel), "--fall", str(fall), "--stichtag", STICHTAG.isoformat(),
             "--archiv", str(tmp_path / "archiv")]
    with pytest.raises(SystemExit) as fehler:
        na.main(grund)
    assert fehler.value.code == 2
    assert "--betriebsschluessel" in capsys.readouterr().err
    assert na.main([*grund, "--betriebsschluessel", str(schluessel),
                    "--zeichnungsordnung", str(ordnung)]) == 0
    [eingang] = [p for p in Ablage(ablage.wurzel).uebernahme.iterdir() if p.is_dir()]
    kopf = json.loads((eingang / "eingang.json").read_text(encoding="utf-8"))
    assert kopf["betriebszeichnung"]["schluessel_sha256"] == hashlib.sha256(
        schluessel.read_bytes()).hexdigest()


def test_cli_seite_reicht_den_schluessel_ausdruecklich_weiter(tmp_path, monkeypatch, capsys):
    """Der Export prueft mit genau dem Schluessel von --betriebsschluessel:
    Mit dem Schluessel, der die Zeilen zeichnete, exportiert er; mit einem
    anderen (dem Test-Betriebsschluessel der Session) nicht; ohne Flag Exit 2
    mit Ausweg."""
    from tests.freigabe_testschluessel import betriebsargs

    sitzung = betriebsargs("--betriebsschluessel")
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", None)
    schluessel, ordnung = _schluessel_und_ordnung(tmp_path, "betrieb/nachtlauf", "betrieb")
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31), schluessel=schluessel,
                     zeichnungsordnung=ordnung)[0] == EXIT_OK
    grund = ["--stand", str(ablage.wurzel), "--anker", str(tmp_path / "anker")]
    assert st.main([*grund, "--paket", str(tmp_path / "p0")]) == 2
    err = capsys.readouterr().err
    assert "ohne Betriebsschluessel kein Export" in err and "--betriebsschluessel" in err
    assert st.main([*grund, "--paket", str(tmp_path / "p1"), *sitzung]) == 2
    assert "traegt keinen Nachweis" in capsys.readouterr().err
    assert not (tmp_path / "p1").exists()
    assert st.main([*grund, "--paket", str(tmp_path / "p2"), "--betriebsschluessel", str(schluessel),
                    "--zeichnungsordnung", str(ordnung)]) == 0
    assert (tmp_path / "p2" / "stand.json").is_file()


# --------------------------------------------------------------------------- #
# I. Nachbesserung: RC16 ohne Config
# --------------------------------------------------------------------------- #


def test_ohne_config_wird_nichts_registriert(tmp_path):
    """RC16 hatte eine Luecke: Ohne configs/bestand.toml in der Ablage wurde
    der Tarifwerk-Abgleich uebersprungen und registriert. Mutationsprobe:
    ohne Config wieder still zurueckkehren -> rot."""
    fall = _fall(tmp_path / "faelle")
    stand = tmp_path / "daten"
    with pytest.raises(ueb.UebernahmeError,
                       match="erst die Config nach deploy/plv/README.md ablegen, dann registrieren"):
        ueb.eingang_anlegen(stand, fall, STICHTAG, schluesselring=TESTRING)
    assert not (Ablage(stand).uebernahme / "probe-uebernahme").exists()
