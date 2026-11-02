"""Der Zielvertrag (ADR-030): Version, Katalog, Wurzelprotokoll,
Konformitaet und der eine Anbieter (Stufe 0); die Rechnungsgrundlagen
und ihre fuenf Konsumenten (Stufe 1).

Jede Regel der Konformitaet hat hier eine Positivkontrolle: eine
absichtlich falsche Implementierung, die genau diesen Befund ausloest.
Ohne sie waere "die PLV ist konform" ein Test, der nichts findet.

Knoten: system/zielsystem, klv, bu
"""

from __future__ import annotations

import pytest

from rechner_pipeline.plv.zielsystem import PLV
from rechner_pipeline.zielsystem import anbieter, konformitaet, rechnungsgrundlagen, version, vertrag


# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #

def test_die_vertragsversion_ist_dreistellig():
    assert version.zerlege(version.VERTRAG_VERSION) == (0, 2, 0)


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


def test_in_stufe_1_beschreibt_der_vertrag_genau_die_rechnungsgrundlagen():
    """Stufe 1 traegt rechnungsgrundlagen ein, Stufe 2 bewertung. Die
    uebrigen darf niemand anbieten (Konformitaet, unten)."""
    assert dict(vertrag.PROTOKOLL_JE_FAEHIGKEIT) == {
        "rechnungsgrundlagen": rechnungsgrundlagen.Rechnungsgrundlagen,
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


@pytest.mark.parametrize("v", ["0.1.0", "0.3.0", "1.2.0", "0.0.1"])
def test_vertragsversion_muss_vertraeglich_sein(v):
    """0.1.0 ist dabei: Die PLV der Stufe 0 waere mit dem Vertrag der
    Stufe 1 nicht mehr konform, sie musste ausdruecklich nachziehen."""
    befunde = konformitaet.pruefe(_abart(vertragsversion=v))
    assert any("nicht vertraeglich" in b for b in befunde), befunde


def test_die_dritte_zahl_der_version_ist_frei():
    assert konformitaet.pruefe(_abart(vertragsversion="0.2.9")) == []


def test_faehigkeiten_muss_ein_frozenset_sein():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: set()))
    assert any("erwartet frozenset" in b for b in befunde), befunde


def test_unbekannte_faehigkeit_ist_ein_befund():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"kaffee"})))
    assert any("unbekannte Faehigkeit 'kaffee'" in b for b in befunde), befunde


def test_faehigkeit_ohne_protokoll_darf_niemand_anbieten():
    """Stufe 0: der Vertrag beschreibt kein Protokoll; ein Zielsystem, das
    trotzdem 'bewertung' anbietet, behauptet etwas, das der Vertrag nicht
    prueft."""
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"bewertung"})))
    assert any("beschreibt dafuer kein Protokoll" in b for b in befunde), befunde


def test_eine_nicht_angebotene_faehigkeit_darf_nicht_geliefert_werden():
    befunde = konformitaet.pruefe(_abart(faehigkeit=lambda self, name: object()))
    nicht_angeboten = set(vertrag.FAEHIGKEITEN) - PLV().faehigkeiten()
    assert len(nicht_angeboten) == 4
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
    assert "faehigkeit('bewertung') wirft ValueError: kaputt: bewertung, erwartet KeyError" in befunde


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
        konformitaet, "PROTOKOLL_JE_FAEHIGKEIT", MappingProxyType({"bewertung": Probe}))
    bietet = {"faehigkeiten": lambda self: frozenset({"bewertung"})}
    schlecht = konformitaet.pruefe(_abart(**bietet, faehigkeit=lambda self, n: object()))
    assert any("erfuellt das Protokoll Probe nicht" in b for b in schlecht), schlecht
    fehlt = konformitaet.pruefe(_abart(**bietet))
    assert any("liefert dafuer aber KeyError" in b for b in fehlt), fehlt
    gut = konformitaet.pruefe(_abart(
        **bietet, faehigkeit=lambda self, n: Gut() if n == "bewertung" else (_ for _ in ()).throw(KeyError(n))))
    assert gut == []


def test_die_plv_nennt_ihre_vertragsversion_selbst():
    """Kein Import der Konstante: Sonst waere die Vertraeglichkeit nie
    eine Pruefung. Die Quelle der PLV traegt die Version als Literal."""
    from pathlib import Path

    import rechner_pipeline.plv.zielsystem as modul

    quelle = Path(modul.__file__).read_text(encoding="utf-8")
    assert 'vertragsversion = "0.2.0"' in quelle
    assert "VERTRAG_VERSION" not in quelle


# --------------------------------------------------------------------------- #
# Stufe 1: Rechnungsgrundlagen — die PLV liefert, was der Kern sagt
# --------------------------------------------------------------------------- #

def _rg():
    return anbieter.zielsystem().faehigkeit("rechnungsgrundlagen")


def test_die_plv_bietet_die_rechnungsgrundlagen_an():
    assert PLV().faehigkeiten() == frozenset({"rechnungsgrundlagen"})
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


def test_der_modellpunkt_ist_der_des_kerns():
    from rechner_pipeline.kern.model_point import KLV_DEFAULT, ModelPoint
    from rechner_pipeline.kern.produkte.bu import BUModelPoint

    import dataclasses
    mp = _rg().modellpunkt("klv", dataclasses.asdict(KLV_DEFAULT))
    assert isinstance(mp, ModelPoint) and mp == KLV_DEFAULT
    bu = _rg().modellpunkt("bu", {"x": 35, "sex": "M", "n": 30, "bu_rente": 12000.0, "zins": 0.0175})
    assert isinstance(bu, BUModelPoint)
    with pytest.raises(TypeError):
        _rg().modellpunkt("klv", {"x": 1})


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

    def modellpunkt(self, produkt, felder):
        return dict(felder)

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
            raise KeyError(name)
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

    def modellpunkt(self, produkt, felder):
        raise LookupError(f"markiert: {produkt}")

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
            raise KeyError(name)
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


def test_abzugsabgleich_baut_den_modellpunkt_ueber_den_vertrag(fremdes_zielsystem):
    from rechner_pipeline.qa.abzugsabgleich import _rechne

    with pytest.raises(LookupError, match="markiert: klv"):
        _rechne({"x": 1}, 0)


def test_tafel_import_liest_und_prueft_ueber_den_vertrag(fremdes_zielsystem, monkeypatch, tmp_path):
    from rechner_pipeline.quellen import tafel_import

    monkeypatch.setattr(tafel_import, "zielsystem", anbieter.zielsystem)
    xml = tmp_path / "tafeln.xml"
    xml.write_text("<tafeln/>", encoding="utf-8")
    assert tafel_import._lade_bestehende(xml) == ({"PROBE": {0: 0.5}}, {"PROBE", "PROBE_SELECT"})
    with pytest.raises(tafel_import.TafelImportFehler, match="quelle: markiert: T"):
        tafel_import._pruefe_alterstafel("T", {0: 0.1}, quelle="quelle")
