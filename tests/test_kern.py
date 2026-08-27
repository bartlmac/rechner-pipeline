"""Der stabile KLV-Rechenkern: Referenzwerte, Parametrisierung, Contract.

Kern 3.0.0 (Beschluss 2026-08-16): die einmalige Excel-Paritaets-Abnahme
(617/617 am 2026-07-22) ist Geschichte des Uebersetzungsakts, kein
eingefrorener Kern-Referenzwert mehr — Fall-Abnahmen laufen ueber Gate O3 je Migrationsfall.
Diese Tests sichern stattdessen:

1. **Referenzwerte**: Charakterisierungs-Referenzwerte (bit-exakte ``berechne()``-
   Ergebnisse) und bekannte Skalare nageln das Kern-Verhalten fest; ein
   Diff braucht eine bewusste, fachlich begruendete Abnahme.
2. **Parametrisierung**: andere Modellpunkte (Alter, Geschlecht, Zins, Tafel)
   rechnen ohne Prozess-Substitution — die frühere ``DEFAULT``-Bindung ist weg.
3. **Contract-Konsistenz**: ``ModelPoint`` und die Bestandsschema-Sicht
   ``MODEL_POINT_FIELDS`` bleiben deckungsgleich.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    MissingMortalityTableError,
    ModelPoint,
    Rechenkern,
    TafelBereichError,
    berechne,
)
from rechner_pipeline.kern import tafeln
from rechner_pipeline.kommutationskern.kommutation import fuer
from rechner_pipeline.kern.produkte import UnbekanntesProduktError, hole
from rechner_pipeline.kern.produkte.klv import KLV, VERLAUFSWERTE_SPALTEN
from rechner_pipeline.models.bestand import MODEL_POINT_FIELDS, model_point_kwargs
REFERENZWERTE = Path(__file__).resolve().parent / "fixtures" / "kern_referenzwerte"


# --------------------------------------------------------------------------- #
# 1. Referenzwerte (eingefrorene Ergebnisse + bekannte Skalare)
# --------------------------------------------------------------------------- #


def test_scalar_values_known_references():
    scalars = berechne(KLV_DEFAULT)["scalars"]["Kalkulation"]
    assert scalars["ratzu"] == 0.05
    assert scalars["BJB"] == pytest.approx(4465.6547026924, abs=1e-8)
    assert scalars["Pxt"] == pytest.approx(0.042392046400377824, abs=1e-12)


@pytest.mark.parametrize(
    "pfad", sorted(REFERENZWERTE.glob("referenz_*.json")), ids=lambda p: p.stem
)
def test_charakterisierungs_referenzwerte_bleiben_exakt(pfad):
    """Eingefrorene berechne()-Ergebnisse weiterer Modellpunkte (bit-exakt).

    Die Referenzwerte sind kernintern (nicht extern verifiziert); sie nageln
    das Kern-Verhalten auf den sonst ungetesteten Zweigen numerisch fest —
    seit dem Backbone-Wechsel sind sie die Voll-Präzisions-Referenz des
    produktiven Pfads. Ein Diff hier ist eine Verhaltensänderung und braucht
    eine bewusste, fachlich begründete Abnahme (kern/__init__-Docstring).
    Referenzwerte anderer Produkte tragen ein ``produkt``-Feld (Registry-Dispatch).
    """
    data = json.loads(pfad.read_text(encoding="utf-8"))
    produkt = data.get("produkt", "klv")
    mp = hole(produkt).model_point_cls(**data["model_point"])
    assert berechne(mp, produkt=produkt) == data["ergebnis"]


# --------------------------------------------------------------------------- #
# 2. Parametrisierung (die fruehere DEFAULT-Bindung ist weg)
# --------------------------------------------------------------------------- #


def test_other_model_points_compute_in_process():
    mp_jung = dataclasses.replace(KLV_DEFAULT, x=30, sum_insured=50000.0)
    mp_frau = dataclasses.replace(KLV_DEFAULT, sex="F")
    bjb_default = berechne(KLV_DEFAULT)["scalars"]["Kalkulation"]["BJB"]
    bjb_jung = berechne(mp_jung)["scalars"]["Kalkulation"]["BJB"]
    bjb_frau = berechne(mp_frau)["scalars"]["Kalkulation"]["BJB"]
    assert bjb_jung != bjb_default  # anderer Vertrag -> anderer Beitrag
    assert bjb_frau != bjb_default  # andere Tafelseite -> anderer Beitrag
    assert bjb_jung < bjb_default   # juenger + kleinere Summe -> kleinerer Beitrag


def test_other_interest_basis_and_table():
    mp_2008 = dataclasses.replace(KLV_DEFAULT, zins=0.0225, tafel="DAV2008_T")
    ergebnis = berechne(mp_2008)
    assert ergebnis["scalars"]["Kalkulation"]["Bxt"] > 0
    assert len(ergebnis["tables"]["Kalkulation"]) == 51


def test_basis_caches_reuse_instanzen():
    # Kern: Tafelbasis-Cache (zinsfrei, je aufgeloestem Tafelnamen)
    a = tafeln.basis("M", "DAV1994_T")
    assert tafeln.basis("M", "DAV1994_T") is a
    assert tafeln.basis("F", "DAV1994_T") is not a
    # Zweitkern: Kommutations-Cache (je Tafel UND Zins)
    k = fuer("M", "DAV1994_T", 0.0175)
    assert fuer("M", "DAV1994_T", 0.0175) is k
    assert fuer("F", "DAV1994_T", 0.0175) is not k


def test_missing_table_fails_fast():
    with pytest.raises(MissingMortalityTableError, match="DAV9999"):
        berechne(dataclasses.replace(KLV_DEFAULT, tafel="DAV9999_T"))


def _lade_synthetisches_tafel_xml(tmp_path, monkeypatch, eintraege):
    xml = tmp_path / "tafeln.xml"
    xml.write_text(
        "<tafeln>\n  <table name=\"TEST\">\n"
        + "\n".join(eintraege)
        + "\n  </table>\n</tafeln>\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(tafeln.resources, "files", lambda _paket: tmp_path)
    return tafeln._load_tables()


def _xml_alterseintraege(qx_bei=None):
    from rechner_pipeline.kern.konventionen import MAX_ALTER

    qx_bei = qx_bei or {}
    return [
        f'    <entry age="{alter}" qx="{qx_bei.get(alter, "0.01")}" />'
        for alter in range(MAX_ALTER + 1)
    ]


def test_kern_xml_laden_akzeptiert_qx_grenzen(tmp_path, monkeypatch):
    tables, select_tables = _lade_synthetisches_tafel_xml(
        tmp_path,
        monkeypatch,
        _xml_alterseintraege({0: "0", 123: "1"}),
    )
    assert tables["TEST"][0] == 0.0
    assert tables["TEST"][123] == 1.0
    assert select_tables == {}


@pytest.mark.parametrize(
    ("roh_qx", "muster"),
    [
        ("nan", "nicht endlich"),
        ("inf", "nicht endlich"),
        ("-0.0000001", r"ausserhalb des Bereichs \[0, 1\]"),
        ("1.0000001", r"ausserhalb des Bereichs \[0, 1\]"),
    ],
)
def test_kern_xml_laden_lehnt_ungueltige_qx_ab(
    tmp_path, monkeypatch, roh_qx, muster
):
    with pytest.raises(ValueError, match=muster):
        _lade_synthetisches_tafel_xml(
            tmp_path,
            monkeypatch,
            _xml_alterseintraege({42: roh_qx}),
        )


@pytest.mark.parametrize(
    ("fall", "muster"),
    [
        ("dezimal", "nicht ganzzahlig"),
        ("doppelt", "Duplikat Alter 42"),
        ("fehlend", "Alter .*fehlen"),
        ("zusaetzlich", "zusaetzliche Alter"),
    ],
)
def test_kern_xml_laden_verlangt_exakte_eindeutige_ganzzahlalter(
    tmp_path, monkeypatch, fall, muster
):
    eintraege = _xml_alterseintraege()
    if fall == "dezimal":
        eintraege[42] = eintraege[42].replace('age="42"', 'age="42.5"')
    elif fall == "doppelt":
        eintraege[43] = eintraege[43].replace('age="43"', 'age="42"')
    elif fall == "fehlend":
        eintraege.pop(42)
    else:
        eintraege.append('    <entry age="124" qx="0.01" />')

    with pytest.raises(ValueError, match=muster):
        _lade_synthetisches_tafel_xml(tmp_path, monkeypatch, eintraege)


def test_reserve_row_shape_and_flex_phase():
    kern = Rechenkern(KLV_DEFAULT)
    row0 = kern.reserve_row(0)
    assert tuple(row0) == VERLAUFSWERTE_SPALTEN
    # Flexible Phase: ab Alter 60 UND Restlaufzeit <= 5 (x=45, n=30 -> a >= 25).
    assert kern.reserve_row(24)["flex. Phase"] == 0.0
    assert kern.reserve_row(25)["flex. Phase"] == 1.0


def test_tarif_stellschrauben_wirken():
    """Die aus Blatt-Literalen gehobenen Stellschrauben sind parametrierbar."""
    basis = berechne(KLV_DEFAULT)
    # Ratenzuschlag-Staffel je Modellpunkt:
    anders = berechne(dataclasses.replace(KLV_DEFAULT, ratzu_zw12=0.06))
    assert anders["scalars"]["Kalkulation"]["ratzu"] == 0.06
    assert anders["scalars"]["Kalkulation"]["BZB"] > basis["scalars"]["Kalkulation"]["BZB"]
    # Stornoabschlag-Deckel (Default 150 bindet am Anfang des Verlaufs):
    hoeher = berechne(dataclasses.replace(KLV_DEFAULT, stoab_max=500.0))
    assert basis["tables"]["Kalkulation"][1]["StoAb"] == 150.0
    assert hoeher["tables"]["Kalkulation"][1]["StoAb"] > 150.0
    # Zillmer-Amortisationsdauer wirkt auf die MRV-Reserve:
    zillmer = berechne(dataclasses.replace(KLV_DEFAULT, zillmer_dauer=10))
    assert (
        zillmer["tables"]["Kalkulation"][7]["kVx_MRV"]
        != basis["tables"]["Kalkulation"][7]["kVx_MRV"]
    )


def test_tafel_erschoepfung_wirft_domaenenfehler():
    """x=60, n=20 auf DAV1994_T (qx=1 ab Alter 100): sprechender Fehler —
    jenseits der Erschoepfung traegt die Tafel keine bedingten Barwerte."""
    with pytest.raises(TafelBereichError, match="erschoepft"):
        berechne(dataclasses.replace(KLV_DEFAULT, x=60, n=20, t=15))
    # x=50 erreicht hoechstens Alter 100 und bleibt berechenbar:
    ok = berechne(dataclasses.replace(KLV_DEFAULT, x=50, n=20, t=15))
    assert len(ok["tables"]["Kalkulation"]) == 51


def test_unbekanntes_produkt_fail_fast():
    with pytest.raises(UnbekanntesProduktError, match="rente"):
        berechne(KLV_DEFAULT, produkt="rente")
    assert hole("klv") is KLV


def test_unisex_tafel_wird_exakt_aufgeloest(monkeypatch):
    """Exakter Tafelname gewinnt vor dem Sex-Suffix (Unisex-faehig)."""
    monkeypatch.setitem(
        tafeln._TABLES, "TESTUNI", {a: 0.1 for a in range(0, 124)}
    )
    assert tafeln._tafel_key("M", "TESTUNI") == "TESTUNI"
    assert tafeln._tafel_key("F", "TESTUNI") == "TESTUNI"
    assert tafeln._tafel_key("M", "DAV1994_T") == "DAV1994_T_M"
    assert tafeln._tafel_key("F", "DAV1994_T") == "DAV1994_T_F"
    assert tafeln.qx_vector("F", "TESTUNI")[0] == 0.1


# --------------------------------------------------------------------------- #
# Ereignis-Anschluesse (additiv; Golden-Master-Ausgaben unberuehrt)
# --------------------------------------------------------------------------- #


def test_zustand_am_stichtag_folgt_jahreskonvention():
    kern = Rechenkern(KLV_DEFAULT)
    zeile = kern.zustand_am(125)  # 125 volle Monate -> Vertragsjahr 10
    assert zeile.jahr == 10
    assert zeile.als_blattzeile() == kern.reserve_row(10)


def test_beitragsfreistellung_operationen():
    kern = Rechenkern(KLV_DEFAULT)
    vs_bfr = kern.beitragsfreie_summe(10)
    assert vs_bfr == kern.reserve_row(10)["VS_bfr"]
    assert 0.0 < vs_bfr < KLV_DEFAULT.sum_insured
    # Bei Umwandlung bleibt die Reserve erhalten (Deckungskapital-Uebergang):
    mrv_10 = kern.reserve_row(10)["kVx_MRV"]
    assert kern.reserve_beitragsfrei(10, 10) == pytest.approx(mrv_10, rel=1e-12)
    # Zum Ablauf laeuft die beitragsfreie Reserve auf VS_bfr zu:
    assert kern.reserve_beitragsfrei(10, 30) == pytest.approx(vs_bfr, rel=1e-12)
    with pytest.raises(ValueError, match="vor Beitragsfreistellung"):
        kern.reserve_beitragsfrei(10, 5)


# --------------------------------------------------------------------------- #
# 3. Contract-Konsistenz mit dem Bestandsschema
# --------------------------------------------------------------------------- #


def test_model_point_matches_bestand_contract_fields():
    fields = [(f.name, f.type) for f in dataclasses.fields(ModelPoint)]
    assert fields == list(MODEL_POINT_FIELDS)


def test_bestand_row_constructs_model_point_directly():
    row = {
        "entry_age": 40, "sex": "F", "duration": 25, "premium_duration": 20,
        "sum_insured": 75000.0, "zahlweise": 12,
    }
    generation = {
        "zins": 0.0225, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.025,
        "gamma1": 0.0008, "gamma2": 0.00125, "gamma3": 0.0025,
        "policy_fee": 30.0, "min_alter_flex": 60, "min_rlz_flex": 5,
    }
    mp = ModelPoint(**model_point_kwargs(row, generation))
    assert mp.x == 40 and mp.sex == "F" and mp.tafel == "DAV2008_T"
    assert berechne(mp)["scalars"]["Kalkulation"]["BJB"] > 0
