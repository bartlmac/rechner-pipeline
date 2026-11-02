"""Der Zielvertrag (ADR-030): Version, Katalog, Wurzelprotokoll,
Konformitaet und der eine Anbieter (Stufe 0); die Rechnungsgrundlagen
und ihre fuenf Konsumenten (Stufe 1); die Bewertung und die drei
qa-Module als ihre ersten Konsumenten (Stufe 2a).

Jede Regel der Konformitaet hat hier eine Positivkontrolle: eine
absichtlich falsche Implementierung, die genau diesen Befund ausloest.
Ohne sie waere "die PLV ist konform" ein Test, der nichts findet.

Knoten: system/zielsystem, klv, bu
"""

from __future__ import annotations

import pytest

from rechner_pipeline.plv.zielsystem import PLV
from rechner_pipeline.zielsystem import (
    anbieter, bewertung, konformitaet, rechnungsgrundlagen, version, vertrag,
)


# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #

def test_die_vertragsversion_ist_dreistellig():
    assert version.zerlege(version.VERTRAG_VERSION) == (0, 3, 0)


@pytest.mark.parametrize("kaputt", ["1.2", "1.2.3.4", "a.b.c", "", "1.2.x", " 1.2.3"])
def test_keine_vertragsversion_ist_ein_fehler(kaputt):
    with pytest.raises(ValueError):
        version.zerlege(kaputt)


@pytest.mark.parametrize("angeboten, verlangt, erwartet", [
    ("0.1.0", "0.1.0", True),
    ("0.1.7", "0.1.0", True),      # dritte Zahl frei
    ("0.2.0", "0.1.0", False),     # andere Nebenversion: der Vertrag verlangt mehr oder weniger
    ("0.0.9", "0.1.0", False),
    ("1.1.0", "0.1.0", False),     # andere Hauptversion
])
def test_vertraeglich_heisst_gleiche_haupt_und_nebenversion(angeboten, verlangt, erwartet):
    assert version.vertraeglich(angeboten, verlangt) is erwartet


# --------------------------------------------------------------------------- #
# Katalog und Wurzelprotokoll
# --------------------------------------------------------------------------- #

def test_der_katalog_nennt_die_fuenf_gemessenen_faehigkeiten():
    assert set(vertrag.FAEHIGKEITEN) == {
        "rechnungsgrundlagen", "bestandsdaten", "bewertung", "zugang", "bestandspruefung",
    }
    assert all(beschreibung for beschreibung in vertrag.FAEHIGKEITEN.values())


def test_der_katalog_ist_unveraenderlich():
    with pytest.raises(TypeError):
        vertrag.FAEHIGKEITEN["neu"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        vertrag.PROTOKOLL_JE_FAEHIGKEIT["neu"] = object  # type: ignore[index]


def test_in_stufe_2_beschreibt_der_vertrag_rechnungsgrundlagen_und_bewertung():
    """Stufe 1 traegt rechnungsgrundlagen ein, Stufe 2 bewertung. Die
    uebrigen darf niemand anbieten (Konformitaet, unten)."""
    assert dict(vertrag.PROTOKOLL_JE_FAEHIGKEIT) == {
        "rechnungsgrundlagen": rechnungsgrundlagen.Rechnungsgrundlagen,
        "bewertung": bewertung.Bewertung,
    }
    assert set(vertrag.PROTOKOLL_JE_FAEHIGKEIT) <= set(vertrag.FAEHIGKEITEN)


def test_das_wurzelprotokoll_ist_strukturell():
    """Eine Implementierung importiert nichts aus dem Tool, sie hat nur
    die Form (wie InputAdapter fuer die Quellen)."""
    assert isinstance(PLV(), vertrag.Zielsystem)

    class Fremd:
        name = "fremd"
        vertragsversion = "0.1.0"

        def faehigkeiten(self):
            return frozenset()

        def faehigkeit(self, name):
            raise KeyError(name)

    assert isinstance(Fremd(), vertrag.Zielsystem)
    assert not isinstance(object(), vertrag.Zielsystem)


# --------------------------------------------------------------------------- #
# Konformitaet: die PLV besteht, jede Regel hat eine Positivkontrolle
# --------------------------------------------------------------------------- #

def test_die_plv_ist_konform():
    assert konformitaet.pruefe(PLV()) == []


def test_der_anbieter_liefert_die_plv_und_sie_ist_konform():
    zs = anbieter.zielsystem()
    assert isinstance(zs, PLV)
    assert zs.name == "plv"
    assert konformitaet.pruefe(zs) == []


def _abart(**aenderungen):
    """Eine PLV mit absichtlich falschen Zuegen."""
    klasse = type("Abart", (PLV,), aenderungen)
    return klasse()


def test_ohne_wurzelprotokoll_nur_ein_befund():
    befunde = konformitaet.pruefe(object())
    assert len(befunde) == 1 and "Wurzelprotokoll Zielsystem nicht" in befunde[0]


@pytest.mark.parametrize("name", ["", "PLV", "plv-1", "1plv", 7])
def test_name_muss_eine_kennung_sein(name):
    befunde = konformitaet.pruefe(_abart(name=name))
    assert any("ist keine Kennung" in b for b in befunde), befunde


@pytest.mark.parametrize("v", ["0.1", "x", None, 1])
def test_vertragsversion_muss_eine_version_sein(v):
    befunde = konformitaet.pruefe(_abart(vertragsversion=v))
    assert any("ist keine Vertragsversion" in b for b in befunde), befunde


@pytest.mark.parametrize("v", ["0.1.0", "0.2.0", "0.4.0", "1.3.0", "0.0.1"])
def test_vertragsversion_muss_vertraeglich_sein(v):
    """0.1.0 und 0.2.0 sind dabei: Die PLV der Stufen 0 und 1 waere mit dem
    Vertrag der Stufe 2 nicht mehr konform, sie musste ausdruecklich
    nachziehen."""
    befunde = konformitaet.pruefe(_abart(vertragsversion=v))
    assert any("nicht vertraeglich" in b for b in befunde), befunde


def test_die_dritte_zahl_der_version_ist_frei():
    assert konformitaet.pruefe(_abart(vertragsversion="0.3.9")) == []


def test_faehigkeiten_muss_ein_frozenset_sein():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: set()))
    assert any("erwartet frozenset" in b for b in befunde), befunde


def test_unbekannte_faehigkeit_ist_ein_befund():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"kaffee"})))
    assert any("unbekannte Faehigkeit 'kaffee'" in b for b in befunde), befunde


def test_faehigkeit_ohne_protokoll_darf_niemand_anbieten():
    """Der Vertrag beschreibt fuer 'bestandsdaten' noch kein Protokoll; ein
    Zielsystem, das die Faehigkeit trotzdem anbietet, behauptet etwas, das
    der Vertrag nicht prueft."""
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"bestandsdaten"})))
    assert any("beschreibt dafuer kein Protokoll" in b for b in befunde), befunde


def test_eine_nicht_angebotene_faehigkeit_darf_nicht_geliefert_werden():
    befunde = konformitaet.pruefe(_abart(faehigkeit=lambda self, name: object()))
    nicht_angeboten = set(vertrag.FAEHIGKEITEN) - PLV().faehigkeiten()
    assert len(nicht_angeboten) == 3
    assert sorted(b for b in befunde if "obwohl es die Faehigkeit nicht anbietet" in b) == [
        f"liefert {n!r}, obwohl es die Faehigkeit nicht anbietet"
        for n in sorted(nicht_angeboten)
    ]


# A-053, B1: eine Implementierung, die wirft, ist ein Befund, kein Absturz.

def test_faehigkeiten_das_wirft_ist_ein_befund():
    def kaputt(self):
        raise RuntimeError("kein Katalog")
    befunde = konformitaet.pruefe(_abart(faehigkeiten=kaputt))
    assert befunde == ["faehigkeiten() wirft RuntimeError: kein Katalog"]


def test_faehigkeiten_ohne_iterable_ist_ein_befund():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: None))
    assert any("faehigkeiten() wirft TypeError" in b for b in befunde), befunde


def test_faehigkeit_die_etwas_anderes_als_keyerror_wirft_ist_ein_befund():
    def kaputt(self, name):
        raise ValueError(f"kaputt: {name}")
    befunde = konformitaet.pruefe(_abart(faehigkeit=kaputt))
    assert "faehigkeit('rechnungsgrundlagen') wirft ValueError: kaputt: rechnungsgrundlagen" in befunde
    assert "faehigkeit('bestandsdaten') wirft ValueError: kaputt: bestandsdaten, erwartet KeyError" in befunde


def test_angebotene_faehigkeit_wird_gegen_ihr_protokoll_geprueft(monkeypatch):
    """Die Mechanik der Stufen 1 und 2, hier mit einem Probeprotokoll:
    Angeboten und geliefert, aber nicht in der verlangten Form -> Befund;
    angeboten, aber KeyError -> Befund; in der Form -> kein Befund."""
    from types import MappingProxyType
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class Probe(Protocol):
        def wert(self) -> int: ...

    class Gut:
        def wert(self) -> int:
            return 1

    monkeypatch.setattr(
        konformitaet, "PROTOKOLL_JE_FAEHIGKEIT", MappingProxyType({"zugang": Probe}))
    bietet = {"faehigkeiten": lambda self: frozenset({"zugang"})}
    schlecht = konformitaet.pruefe(_abart(**bietet, faehigkeit=lambda self, n: object()))
    assert any("erfuellt das Protokoll Probe nicht" in b for b in schlecht), schlecht
    fehlt = konformitaet.pruefe(_abart(**bietet))
    assert any("liefert dafuer aber KeyError" in b for b in fehlt), fehlt
    gut = konformitaet.pruefe(_abart(
        **bietet, faehigkeit=lambda self, n: Gut() if n == "zugang" else (_ for _ in ()).throw(KeyError(n))))
    assert gut == []


def test_die_plv_nennt_ihre_vertragsversion_selbst():
    """Kein Import der Konstante: Sonst waere die Vertraeglichkeit nie
    eine Pruefung. Die Quelle der PLV traegt die Version als Literal."""
    from pathlib import Path

    import rechner_pipeline.plv.zielsystem as modul

    quelle = Path(modul.__file__).read_text(encoding="utf-8")
    assert 'vertragsversion = "0.3.0"' in quelle
    assert "VERTRAG_VERSION" not in quelle


# --------------------------------------------------------------------------- #
# Stufe 1: Rechnungsgrundlagen — die PLV liefert, was der Kern sagt
# --------------------------------------------------------------------------- #

def _rg():
    return anbieter.zielsystem().faehigkeit("rechnungsgrundlagen")


def test_die_plv_bietet_die_rechnungsgrundlagen_an():
    assert PLV().faehigkeiten() == frozenset({"rechnungsgrundlagen", "bewertung"})
    assert isinstance(_rg(), rechnungsgrundlagen.Rechnungsgrundlagen)
    assert konformitaet.pruefe_rechnungsgrundlagen(_rg()) == []


def test_der_parametersatz_ist_der_modellpunkt_des_kerns():
    """Felder wie der Bestandsvertrag (MODEL_POINT_FIELDS, selbst gegen den
    Kern gehalten in test_kern.py); Defaults wie die Dataclass des Kerns,
    und als unabhaengige Kontrolle die Blattwerte des Quell-Workbooks."""
    import dataclasses

    from rechner_pipeline.kern.model_point import ModelPoint
    from rechner_pipeline.models.bestand import GENERATION_FIELDS, MODEL_POINT_FIELDS

    satz = _rg().parametersatz("klv")
    assert isinstance(satz, rechnungsgrundlagen.Parametersatz)
    assert satz.produkt == "klv"
    assert satz.felder == MODEL_POINT_FIELDS
    assert dict(satz.defaults) == {
        f.name: f.default for f in dataclasses.fields(ModelPoint) if f.default is not dataclasses.MISSING}
    assert dict(satz.defaults) == {
        "stoab_satz": 0.01, "stoab_min": 50.0, "stoab_max": 150.0, "zillmer_dauer": 5,
        "ratzu_zw2": 0.02, "ratzu_zw4": 0.03, "ratzu_zw12": 0.05}
    assert set(satz.defaults) <= set(GENERATION_FIELDS)
    with pytest.raises(TypeError):
        satz.defaults["zillmer_dauer"] = 9  # type: ignore[index]


def test_produkte_und_unbekanntes_produkt():
    assert _rg().produkte() == frozenset({"klv", "bu"})
    bu = _rg().parametersatz("bu")
    assert bu.feldnamen()[:4] == ("x", "sex", "n", "bu_rente")
    assert dict(bu.defaults)["zuschlag"] == 0.05
    with pytest.raises(KeyError):
        _rg().parametersatz("rente")


def test_die_tafeln_sind_die_des_kerns():
    from rechner_pipeline.kern import tafeln
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    assert _rg().verfuegbare_tafeln() == frozenset(tafeln.verfuegbare_tafeln())
    assert "DAV1994_T_M" in _rg().verfuegbare_tafeln()
    alter = range(0, MAX_ALTER + 1)
    gut = {a: 0.001 for a in alter}
    _rg().pruefe_alterstafel("T", gut)
    with pytest.raises(ValueError, match="fehlen"):
        _rg().pruefe_alterstafel("T", {0: 0.001})
    with pytest.raises(ValueError, match="Bereich"):
        _rg().pruefe_alterstafel("T", {**gut, 5: 1.5})
    zeilen = "".join(f'<entry age="{a}" qx="0.001"/>' for a in alter)
    select = "".join(f'<entry age="{a}" dauer="{d}" qx="0.5"/>' for a in alter for d in (0, 1))
    text = (f'<tafeln><table name="A">{zeilen}</table>'
            f'<table name="S" select_max="1">{select}</table></tafeln>')
    alterstafeln, namen = _rg().tafeln_lesen(text)
    assert set(alterstafeln) == {"A"} and alterstafeln["A"][MAX_ALTER] == 0.001
    assert namen == frozenset({"A", "S"})
    with pytest.raises(ValueError, match="doppelt"):
        _rg().tafeln_lesen(f'<tafeln><table name="A">{zeilen}</table><table name="A">{zeilen}</table></tafeln>')


# Positivkontrollen der Regeln fuer die Rechnungsgrundlagen

class _RG:
    """Eine konforme Fremdumsetzung als Ausgang fuer die Abarten."""

    def produkte(self):
        return frozenset({"p"})

    def parametersatz(self, produkt):
        if produkt != "p":
            raise KeyError(produkt)
        return rechnungsgrundlagen.Parametersatz("p", (("x", "int"), ("k", "float")), {"k": 1.0})

    def verfuegbare_tafeln(self):
        return frozenset({"T"})

    def pruefe_alterstafel(self, name, werte):
        return None

    def tafeln_lesen(self, text):
        return {}, frozenset()


def _rg_abart(**aenderungen):
    return type("RGAbart", (_RG,), aenderungen)()


def test_eine_fremde_konforme_umsetzung_besteht():
    assert konformitaet.pruefe_rechnungsgrundlagen(_RG()) == []


@pytest.mark.parametrize("aenderung, erwartet", [
    ({"produkte": lambda self: frozenset()}, "erwartet ein nicht leeres frozenset"),
    ({"produkte": lambda self: frozenset({1})}, "erwartet ein nicht leeres frozenset von str"),
    ({"produkte": lambda self: {"p"}}, "erwartet ein nicht leeres frozenset"),
    ({"produkte": lambda self: (_ for _ in ()).throw(RuntimeError("x"))}, "produkte() wirft RuntimeError"),
    ({"parametersatz": lambda self, p: {"felder": ()}}, "erwartet Parametersatz"),
    ({"parametersatz": lambda self, p: rechnungsgrundlagen.Parametersatz("q", (("x", "int"),), {})},
     "nennt das Produkt 'q'"),
    ({"parametersatz": lambda self, p: rechnungsgrundlagen.Parametersatz("p", (("x", "int"), ("x", "int")), {})},
     "Felder leer oder doppelt"),
    ({"parametersatz": lambda self, p: rechnungsgrundlagen.Parametersatz("p", (("x", "int"),), {"k": 1})},
     "Defaults ohne Feld: ['k']"),
    ({"parametersatz": lambda self, p: rechnungsgrundlagen.Parametersatz(p, (("x", "int"),), {})},
     "parametersatz('kein_produkt') liefert etwas, erwartet KeyError"),
    ({"parametersatz": lambda self, p: (_ for _ in ()).throw(ValueError(p))},
     "parametersatz('p') wirft ValueError"),
    ({"verfuegbare_tafeln": lambda self: {"T"}}, "erwartet frozenset von str"),
    ({"verfuegbare_tafeln": lambda self: frozenset({1})}, "erwartet frozenset von str"),
    ({"verfuegbare_tafeln": lambda self: (_ for _ in ()).throw(OSError("weg"))}, "verfuegbare_tafeln() wirft OSError"),
])
def test_jede_regel_der_rechnungsgrundlagen_hat_eine_positivkontrolle(aenderung, erwartet):
    befunde = konformitaet.pruefe_rechnungsgrundlagen(_rg_abart(**aenderung))
    assert any(erwartet in b for b in befunde), befunde


def test_die_faehigkeitspruefung_laeuft_in_pruefe_mit_praefix():
    class Fremd(PLV):
        def faehigkeit(self, name):
            if name == "rechnungsgrundlagen":
                return _rg_abart(produkte=lambda self: frozenset())
            return super().faehigkeit(name)
    befunde = konformitaet.pruefe(Fremd())
    assert befunde == ["rechnungsgrundlagen: produkte() liefert frozenset(), "
                       "erwartet ein nicht leeres frozenset von str"]


# --------------------------------------------------------------------------- #
# Stufe 1: die fuenf Konsumenten lesen vom Vertrag, nicht vom Kern
# --------------------------------------------------------------------------- #

class _Markiert(_RG):
    """Eine Fremdumsetzung mit Werten, die der Kern nie liefert."""

    def produkte(self):
        return frozenset({"klv", "probeprodukt"})

    def parametersatz(self, produkt):
        return rechnungsgrundlagen.Parametersatz(
            produkt, (("x", "int"),), {"zillmer_dauer": 77, "stoab_min": 1.0})

    def verfuegbare_tafeln(self):
        return frozenset({"PROBETAFEL"})

    def pruefe_alterstafel(self, name, werte):
        raise ValueError(f"markiert: {name}")

    def tafeln_lesen(self, text):
        return {"PROBE": {0: 0.5}}, frozenset({"PROBE", "PROBE_SELECT"})


@pytest.fixture
def fremdes_zielsystem(monkeypatch):
    class Fremd(PLV):
        def faehigkeit(self, name):
            if name == "rechnungsgrundlagen":
                return _Markiert()
            return super().faehigkeit(name)
    monkeypatch.setattr(anbieter, "zielsystem", lambda: Fremd())
    return Fremd()


def test_models_bestand_liest_die_defaults_vom_vertrag(fremdes_zielsystem):
    from rechner_pipeline.models.bestand import generation_field_defaults, model_point_kwargs

    assert dict(generation_field_defaults()) == {"zillmer_dauer": 77, "stoab_min": 1.0}
    zeile = {"entry_age": 30, "sex": "M", "duration": 30, "premium_duration": 30,
             "sum_insured": 1000.0, "zahlweise": 12}
    generation = {"zins": 0.01, "tafel": "T", "alpha": 0.0, "beta1": 0.0, "gamma1": 0.0,
                  "gamma2": 0.0, "gamma3": 0.0, "policy_fee": 0.0, "min_alter_flex": 60,
                  "min_rlz_flex": 5, "stoab_satz": 0.01, "stoab_max": 150.0,
                  "ratzu_zw2": 0.02, "ratzu_zw4": 0.03, "ratzu_zw12": 0.05}
    kw = model_point_kwargs(zeile, generation)
    assert kw["zillmer_dauer"] == 77 and kw["stoab_min"] == 1.0
    with pytest.raises(KeyError, match="ohne Default: stoab_satz"):
        model_point_kwargs(zeile, {k: v for k, v in generation.items() if k != "stoab_satz"})


def test_code_index_liest_die_produkte_vom_vertrag(fremdes_zielsystem):
    from rechner_pipeline.ontologie.code_index import erlaubte_wurzeln

    assert "probeprodukt" in erlaubte_wurzeln()
    assert "bu" not in erlaubte_wurzeln()


def test_spez_erzeugen_liest_die_tafeln_vom_vertrag(fremdes_zielsystem):
    from rechner_pipeline.spez.erzeugen import kern_tafeln

    assert kern_tafeln() == {"PROBETAFEL"}


def test_tafel_import_liest_und_prueft_ueber_den_vertrag(fremdes_zielsystem, monkeypatch, tmp_path):
    from rechner_pipeline.quellen import tafel_import

    xml = tmp_path / "tafeln.xml"
    xml.write_text("<tafeln/>", encoding="utf-8")
    assert tafel_import._lade_bestehende(xml) == ({"PROBE": {0: 0.5}}, {"PROBE", "PROBE_SELECT"})
    with pytest.raises(tafel_import.TafelImportFehler, match="quelle: markiert: T"):
        tafel_import._pruefe_alterstafel("T", {0: 0.1}, quelle="quelle")


# --------------------------------------------------------------------------- #
# Stufe 2a: Bewertung — die PLV liefert, was der Kern rechnet
# --------------------------------------------------------------------------- #

def _bw():
    return anbieter.zielsystem().faehigkeit("bewertung")


def _klv_felder():
    import dataclasses

    from rechner_pipeline.kern.model_point import KLV_DEFAULT

    return dataclasses.asdict(KLV_DEFAULT)


def test_die_plv_bietet_die_bewertung_an():
    assert isinstance(_bw(), bewertung.Bewertung)
    assert konformitaet.pruefe_bewertung(_bw()) == []
    regeln = _bw().vorgangsregeln()
    assert regeln.rang == {"PEX": 0, "RED": 1, "TKU": 2, "ERH": 3}
    assert regeln.teilkuendigung == "teilkuendigung" and regeln.teilkuendigung in regeln.verfahren
    assert _bw().tku_umfang("teilkuendigung", None) == "grundversicherung"
    assert _bw().tku_umfang("prospektiv", None) == "alle_bausteine"


def test_die_werte_des_vertrags_sind_die_des_kerns():
    """Kontrollrechnung direkt am Kern: jede Groesse des Vertrags ist
    bitgleich mit dem Kernaufruf, den die Pruefstrecke vorher selbst tat."""
    from rechner_pipeline.kern import (
        ModelPoint, Rechenkern, Vorgangsfolge, erhoehungs_scheibe, vertrags_monatsreserve, vorgang,
    )

    felder = _klv_felder()
    scheiben = [(3, 1000.0), (5, 500.0)]
    v = _bw().vertrag(felder, scheiben, gamma1_uebernehmen=True, stoab_je_baustein=False)
    assert v.komponenten() == 3 and v.scheiben == ((3, 1000.0), (5, 500.0))
    mp = ModelPoint(**felder)
    kern = Rechenkern(mp)
    kerne = [(j, Rechenkern(erhoehungs_scheibe(mp, j, s, gamma1_uebernehmen=True))) for j, s in scheiben]
    m = vertrags_monatsreserve(kern, kerne, 100)
    assert v.reserve(100) == bewertung.Reserve(m.vx_mrv, m.rkw)
    assert v.reserven_beitragsfrei(8, 120) == (
        kern.reserve_beitragsfrei(8, 10),
        kerne[0][1].reserve_beitragsfrei(5, 7), kerne[1][1].reserve_beitragsfrei(3, 5))
    assert v.reserven_beitragsfrei(8, 125) == (
        kern.monatsreserve_beitragsfrei(8, 125),
        kerne[0][1].monatsreserve_beitragsfrei(5, 89), kerne[1][1].monatsreserve_beitragsfrei(3, 65))
    assert v.beitragsfreie_summe(8) == kern.beitragsfreie_summe(8) + sum(
        k.beitragsfreie_summe(8 - j) for j, k in kerne)
    assert v.gesamtsumme() == 101500.0
    assert v.jahresbeitrag(100, None) == kern.gross_annual_premium() + kerne[0][1].gross_annual_premium() + kerne[1][1].gross_annual_premium()
    assert v.jahresbeitrag(100, 5) == 0.0
    # ohne Scheiben: die Reserve des Kerns selbst
    allein = _bw().vertrag(felder, gamma1_uebernehmen=False, stoab_je_baustein=True)
    assert allein.reserve(37) == bewertung.Reserve(kern.monatsreserve(37).vx_mrv, kern.monatsreserve(37).rkw)
    assert allein.mit_scheibe(3, 1000.0).komponenten() == 2
    # die Vorgangsfolge
    folge = v.folge([(10, 0.5, "teilkuendigung")], pex_jahr=None, schicht=None, tku_umfang="alle_bausteine")
    kernfolge = Vorgangsfolge(kern, kerne, [vorgang(10, 0.5, "teilkuendigung")], pex_jahr=None,
                              schicht=None, stoab_je_baustein=False, tku_umfang="alle_bausteine")
    stand, kernstand = folge.stand_am(130), kernfolge.stand_am(130)
    w, kw = stand.werte(130), kernstand.werte(130)
    assert (w.status, w.deckungskapital, w.rueckkaufswert, w.korrekturschicht, w.vs_bfr, w.vx_mrv) == (
        kw["status"], kw["deckungskapital"], kw["rueckkaufswert"], kw["korrekturschicht"], kw["vs_bfr"], kw["vx_mrv"])
    assert stand.komponenten(130) == len(kernstand.bestehend(130)) == 3
    assert stand.jahresbeitrag(130) == sum(
        k.gross_annual_premium() for j, k in kernstand.beitragskerne(130) if 130 - 12 * j < 12 * k.mp.t)
    assert stand.gesamt_vs() == kernstand.gesamt_vs()
    assert folge.hat_vorgang(10, "TKU") and not folge.hat_vorgang(10, "RED")
    vor = folge.stand_vor(10, "TKU")
    assert vor.werte(120).vx_mrv == kernfolge.stand_vor(10, "TKU").werte(120)["vx_mrv"]
    assert not vor.beitragsfrei and vor.pex_jahr is None
    danach = stand.nach_erhoehung(12, 700.0).nach_pex(15)
    kerndanach = kernstand.nach_erhoehung(12, Rechenkern(erhoehungs_scheibe(mp, 12, 700.0, gamma1_uebernehmen=True))).nach_pex(15)
    assert danach.beitragsfrei and danach.pex_jahr == 15
    assert danach.werte(200).deckungskapital == kerndanach.werte(200)["deckungskapital"]
    assert danach.vs_bfr_ohne_zuschlag() == kerndanach.vs_bfr() - sum(b.zuschlag for b in kerndanach.bausteine)
    neu = vor.nach_vorgang(10, 0.5, "teilkuendigung")
    assert neu.werte(130).vx_mrv == w.vx_mrv


def test_bausteine_stand_ergebnis_und_schichtfelder_sind_die_des_kerns():
    """Stufe 2b: was die Gates brauchen, gegen den Kern als Kontrollrechnung."""
    import dataclasses

    from rechner_pipeline.kern import ModelPoint, Rechenkern, Vertragsstand, Vorgangsfolge, erhoehungs_scheibe, vorgang
    from rechner_pipeline.kern.korrekturschicht import Schichtparameter

    felder = _klv_felder()
    mp = ModelPoint(**felder)
    sch = _bw().scheibe(felder, 4, 800.0, gamma1_uebernehmen=True)
    assert dict(sch) == dataclasses.asdict(erhoehungs_scheibe(mp, 4, 800.0, gamma1_uebernehmen=True))
    with pytest.raises(ValueError):
        _bw().scheibe(felder, 0, 800.0, gamma1_uebernehmen=True)
    eigener = {**felder, "x": 50, "n": 25, "t": 15, "sum_insured": 600.0, "gamma1": 0.0}
    v = _bw().vertrag(felder, [(3, 1000.0)], gamma1_uebernehmen=False, stoab_je_baustein=True)
    w = v.mit_baustein(5, eigener)
    assert w.komponenten() == 3 and v.komponenten() == 2
    kerne = [(3, Rechenkern(erhoehungs_scheibe(mp, 3, 1000.0, gamma1_uebernehmen=False))),
             (5, Rechenkern(ModelPoint(**eigener)))]
    stand = w.stand(schicht=None, tku_umfang="grundversicherung")
    kernstand = Vertragsstand.anfang(Rechenkern(mp), kerne, stoab_je_baustein=True,
                                     tku_umfang="grundversicherung", schicht=None)
    assert stand.werte(100).rueckkaufswert == kernstand.werte(100)["rueckkaufswert"]
    assert stand.leistung() == kernstand.leistung() == 101600.0
    assert stand.nach_pex(9).leistung() == kernstand.nach_pex(9).leistung()
    folge = w.folge([(8, 0.6, "teilkuendigung")], pex_jahr=None, schicht=None, tku_umfang="alle_bausteine")
    kernfolge = Vorgangsfolge(Rechenkern(mp), kerne, [vorgang(8, 0.6, "teilkuendigung")], pex_jahr=None,
                              schicht=None, stoab_je_baustein=True, tku_umfang="alle_bausteine")
    e, ke = folge.ergebnis(8, "TKU"), kernfolge.ergebnis(8, "TKU")
    assert (e.vs_neu, e.absorbiert, e.auszahlung) == (ke.vs_neu, ke.absorbiert, ke.auszahlung)
    assert folge.ergebnis(8, "RED") is None
    regeln = _bw().vorgangsregeln()
    assert regeln.art("teilkuendigung") == "TKU" and regeln.art("prospektiv") == "RED"
    assert regeln.schluessel(8, "teilkuendigung") == vorgang(8, 0.6, "teilkuendigung").schluessel
    assert regeln.schluessel(8, "mit_abzug") == vorgang(8, 0.6, "mit_abzug").schluessel
    assert _bw().schichtfelder() == tuple(f.name for f in dataclasses.fields(Schichtparameter))
    # beitragsfreie Summe: nur die Bausteine, die im Jahr der Freistellung bestehen
    spaet = _bw().vertrag(felder, [(3, 1000.0), (12, 500.0)], gamma1_uebernehmen=False, stoab_je_baustein=False)
    k3 = Rechenkern(erhoehungs_scheibe(mp, 3, 1000.0, gamma1_uebernehmen=False))
    assert spaet.beitragsfreie_summe(10) == Rechenkern(mp).beitragsfreie_summe(10) + sum([k3.beitragsfreie_summe(7)])


def test_die_beitragsfreie_reserve_kommt_je_baustein():
    """Die zwei Pruefstrecken summieren in verschiedener Reihenfolge, und
    auf Fall 3 unterscheiden sich die Summen in der letzten Stelle (2391
    von 5517 Faellen). Der Vertrag liefert deshalb die Bausteine; die
    Summe bleibt beim Vergleich."""
    v = _bw().vertrag(_klv_felder(), [(2, 3000.0), (4, 2500.0), (6, 1200.0)],
                      gamma1_uebernehmen=False, stoab_je_baustein=False)
    teile = v.reserven_beitragsfrei(9, 150)
    assert len(teile) == 4 and all(t > 0 for t in teile)
    a = teile[0] + sum(teile[1:])
    b = teile[0]
    for t in teile[1:]:
        b += t
    assert abs(a - b) < 1e-9       # dieselbe Groesse ...
    assert isinstance(a, float)    # ... je Strecke in ihrer eigenen Reihenfolge summiert


def test_die_ausnahmen_des_kerns_werden_in_die_des_vertrags_uebersetzt():
    from rechner_pipeline.kern.vorgangsfolge import VorgangsfolgeFehler

    with pytest.raises(bewertung.Vorgangsfehler, match="unbekannt") as info:
        _bw().tku_umfang("prospektiv", "kein_umfang")
    assert isinstance(info.value, ValueError) and isinstance(info.value.__cause__, VorgangsfolgeFehler)
    v = _bw().vertrag(_klv_felder(), gamma1_uebernehmen=False, stoab_je_baustein=False)
    with pytest.raises(bewertung.Vorgangsfehler, match="zwei Vorgaenge TKU am Jahrestag"):
        v.folge([(10, 0.5, "teilkuendigung"), (10, 0.7, "teilkuendigung")],
                pex_jahr=None, schicht=None, tku_umfang="alle_bausteine")
    with pytest.raises(bewertung.Datenfehler):
        _bw().rechne("klv", {**_klv_felder(), "tafel": "GIBT_ES_NICHT"})
    with pytest.raises(TypeError):
        _bw().schicht_aus_beleg({"unbekanntes_feld": 1})
    with pytest.raises(TypeError):
        _bw().vertrag({"x": 30}, gamma1_uebernehmen=False, stoab_je_baustein=False)


def _schichtbeleg():
    from rechner_pipeline.kern.korrekturschicht import Schichtparameter

    return Schichtparameter(
        schichttyp="hist", verankerungszustand="aktiv", verweildauer=0,
        rho=0.04, formfunktion="proportional_zur_basis", formparameter={},
        vererbend=(("aktiv", "tot"),), kohorte="t_a",
    ).als_beleg()


def test_die_schicht_ist_die_des_kerns():
    from rechner_pipeline.kern import ModelPoint
    from rechner_pipeline.kern.korrekturschicht import Schichtparameter, schichtwert_bei, zuschlag_bei_pex
    from rechner_pipeline.kern.rechenkern import Rechenkern

    beleg = _schichtbeleg()
    schicht = _bw().schicht_aus_beleg(beleg)
    assert isinstance(schicht, bewertung.Schicht) and isinstance(schicht, Schichtparameter)
    assert schicht.schichttyp == "hist" and schicht.rumpfmonate == 0
    felder = _klv_felder()
    mp = ModelPoint(**felder)
    for monate in (60, 67, 120):
        assert _bw().schichtwert(schicht, 60, felder, monate) == schichtwert_bei(schicht, 60, mp, monate)
    assert _bw().schichtwert(schicht, 60, felder, 60) != 0.0
    assert _bw().zuschlag_bei_pex((schicht, 60), felder, 8) == zuschlag_bei_pex((schicht, 60), Rechenkern(mp), 8)
    assert _bw().zuschlag_bei_pex(None, felder, 8) == 0.0
    assert _bw().schicht_traegt((schicht, 60), 59) is False
    assert _bw().schicht_traegt((schicht, 60), 60) is True
    assert _bw().ab_verankerung(60, 61) is True and _bw().ab_verankerung(60, 59) is False


def test_praemien_verlauf_und_rechenlauf_sind_die_des_kerns():
    from rechner_pipeline.kern import ModelPoint, Rechenkern, berechne

    felder = _klv_felder()
    kern = Rechenkern(ModelPoint(**felder))
    assert _bw().praemien(felder) == bewertung.Praemien(
        kern.gross_premium_rate(), kern.gross_annual_premium(),
        kern.gross_payable_premium(), kern.net_premium_rate())
    assert _bw().verlauf(felder, 3) == kern.verlaufszeile(3).als_blattzeile()
    assert _bw().rechne("klv", felder) == berechne(ModelPoint(**felder))


# Positivkontrollen der Regeln fuer die Bewertung

class _BW:
    """Eine konforme Fremdumsetzung als Ausgang fuer die Abarten."""

    def vorgangsregeln(self):
        return bewertung.Vorgangsregeln({"A": 0, "B": 1}, "b", ("a", "b"), ("alles",))

    def tku_umfang(self, red_verfahren, gewuenscht):
        if gewuenscht is not None and gewuenscht != "alles":
            raise ValueError(gewuenscht)
        return "alles"

    def vertrag(self, felder, scheiben=(), *, gamma1_uebernehmen, stoab_je_baustein):
        if not felder:
            raise TypeError("keine Felder")
        return object()

    def schichtfelder(self):
        return ("rho",)

    def scheibe(self, felder, jahr, summe, *, gamma1_uebernehmen):
        return dict(felder)

    def schicht_aus_beleg(self, beleg):
        return object()

    def schichtwert(self, schicht, monate_anker, felder, monate):
        return 0.0

    def zuschlag_bei_pex(self, schicht, felder, pex_jahr):
        return 0.0

    def schicht_traegt(self, schicht, monate):
        return schicht is not None and monate >= schicht[1]

    def ab_verankerung(self, monate_anker, monate):
        return monate >= monate_anker

    def praemien(self, felder):
        return bewertung.Praemien(0.0, 0.0, 0.0, 0.0)

    def verlauf(self, felder, k):
        return {}

    def rechne(self, produkt, felder):
        return {}


def _bw_abart(**aenderungen):
    return type("BWAbart", (_BW,), aenderungen)()


def test_eine_fremde_konforme_bewertung_besteht():
    assert isinstance(_BW(), bewertung.Bewertung)
    assert konformitaet.pruefe_bewertung(_BW()) == []


@pytest.mark.parametrize("aenderung, erwartet", [
    ({"vorgangsregeln": lambda self: {"rang": {}}}, "erwartet Vorgangsregeln"),
    ({"vorgangsregeln": lambda self: (_ for _ in ()).throw(RuntimeError("x"))}, "vorgangsregeln() wirft RuntimeError"),
    ({"vorgangsregeln": lambda self: bewertung.Vorgangsregeln({}, "b", ("a", "b"), ("alles",))}, "eindeutiger Rang"),
    ({"vorgangsregeln": lambda self: bewertung.Vorgangsregeln({"A": 0, "B": 0}, "b", ("a", "b"), ("alles",))}, "eindeutiger Rang"),
    ({"vorgangsregeln": lambda self: bewertung.Vorgangsregeln({"A": 0}, "c", ("a", "b"), ("alles",))}, "ist keines der Verfahren"),
    ({"vorgangsregeln": lambda self: bewertung.Vorgangsregeln({"A": 0}, "b", ("a", "b"), ())}, "keine Umfaenge"),
    ({"tku_umfang": lambda self, r, g: "alles"}, "tku_umfang(.., 'kein_umfang') liefert etwas"),
    ({"tku_umfang": lambda self, r, g: (_ for _ in ()).throw(KeyError(g))}, "erwartet ValueError"),
    ({"schicht_traegt": lambda self, s, m: True}, "schicht_traegt(None, 0) ist nicht False"),
    ({"ab_verankerung": lambda self, a, m: monate_frei(a, m)}, "ab_verankerung(5, 4) ist nicht False"),
    ({"ab_verankerung": lambda self, a, m: m > a}, "ab_verankerung(5, 5) ist nicht True"),
    ({"vertrag": lambda self, felder, scheiben=(), **k: object()}, "vertrag({}) liefert etwas"),
    ({"vertrag": lambda self, felder, scheiben=(), **k: (_ for _ in ()).throw(ValueError("leer"))}, "erwartet TypeError"),
])
def test_jede_regel_der_bewertung_hat_eine_positivkontrolle(aenderung, erwartet):
    befunde = konformitaet.pruefe_bewertung(_bw_abart(**aenderung))
    assert any(erwartet in b for b in befunde), befunde


def monate_frei(a, m):
    return True


# --------------------------------------------------------------------------- #
# Stufe 2a: die drei qa-Module lesen vom Vertrag, nicht vom Kern
# --------------------------------------------------------------------------- #

class _MarkierteBewertung(_BW):
    """Eine fremde Bewertung, die jeden Vertrag und jeden Rechenlauf als
    Marker verweigert: Wer sie erreicht, liest vom Vertrag."""

    def vertrag(self, felder, scheiben=(), *, gamma1_uebernehmen, stoab_je_baustein):
        raise LookupError("markiert: vertrag")

    def rechne(self, produkt, felder):
        raise LookupError(f"markiert: rechne {produkt}")

    def schichtwert(self, schicht, monate_anker, felder, monate):
        raise LookupError("markiert: schichtwert")


@pytest.fixture
def fremde_bewertung(monkeypatch):
    class Fremd(PLV):
        def faehigkeit(self, name):
            if name == "bewertung":
                return _MarkierteBewertung()
            return super().faehigkeit(name)
    monkeypatch.setattr(anbieter, "zielsystem", lambda: Fremd())
    return Fremd()


def test_migrationssuite_bewertet_ueber_den_vertrag(fremde_bewertung):
    from rechner_pipeline.qa.migrationssuite import VertragsPruefung, pruefe_vertrag

    v = VertragsPruefung(
        police_id="P", model_point=_klv_felder(), monate_stichtag_1=113, monate_stichtag_2=125,
        dk_erwartet_1=1.0, dk_erwartet_2=1.0, scheiben_mit_gamma1=False, stoab_je_baustein=False,
        tku_umfang=None, dk_am_jahrestag=False)
    with pytest.raises(LookupError, match="markiert: vertrag"):
        pruefe_vertrag(v, red_verfahren="prospektiv")


def test_aktuarieller_test_bewertet_ueber_den_vertrag(fremde_bewertung):
    from rechner_pipeline.qa import aktuarieller_test as at

    v = at.Vertragspruefung(
        police_id="P", model_point=_klv_felder(), historientyp="ohne_gevo",
        punkte=(at.Pruefpunkt(monate=120, erwartet={"kVx_MRV": 1.0}, anlass=at.ANLASS_UEBERNAHME),),
        scheiben_mit_gamma1=False, stoab_je_baustein=False, tku_umfang=None)
    with pytest.raises(LookupError, match="markiert: vertrag"):
        at._pruefe_auftrag(v)
    with pytest.raises(LookupError, match="markiert: vertrag"):
        at._system_werte(v, v.model_point, v.punkte[0], red_verfahren="prospektiv")
    with pytest.raises(LookupError, match="markiert: schichtwert"):
        at.schichtwert_bei(object(), 60, _klv_felder(), 70)


def test_abzugsabgleich_rechnet_ueber_den_vertrag(fremde_bewertung):
    from rechner_pipeline.qa.abzugsabgleich import _rechne

    with pytest.raises(LookupError, match="markiert: rechne klv"):
        _rechne(_klv_felder(), 0)
