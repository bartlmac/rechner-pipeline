"""Regressionstests zu den bestaetigten Findings des v0.1-Reviews.

Ein Test je Finding-Klasse; die Docstrings nennen den Befund. Zweck:
die Mutation, die das Review als unentdeckbar nachgewiesen hat, faellt
ab jetzt rot aus.

Knoten: klv
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.ontologie import (
    ABox,
    Aussage,
    Diskrepanz,
    Lesart,
    Merkmalsdimension,
    Parametrierungszelle,
    PFLICHT_PARAMETER,
    Provenienz,
    Quelle,
    Tarifgeneration,
    Zustand,
    belegt,
)
from rechner_pipeline.ontologie.abox import speichere, validate_abox
from rechner_pipeline.ontologie.befuellung import (
    BefuellungsFehler,
    FragmentWert,
    FragmentZelle,
    QuellFragment,
    baue_abox,
    baue_generation,
    loese_diskrepanz_auf,
)
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.ontologie.ids import zellen_segment
from rechner_pipeline.ontologie.merge import merge_aussagen

SHA_A = "a" * 64
SHA_B = "b" * 64
ZEIT = "2026-08-15T08:00:00+00:00"


def prov(datei="rechner.xlsm", sha=SHA_A, fundstelle="Kalkulation!$E$4"):
    return Provenienz(quelle_datei=datei, quelle_sha256=sha,
                      fundstelle=fundstelle, akteur="test", erhoben_am=ZEIT)


def _lesarten():
    return [Lesart(wert=1, provenienz=[prov()]),
            Lesart(wert=2, provenienz=[prov(sha=SHA_B, datei="m.docx")])]


# --- Finding 1: unisex-Widerspruch ist kein Sonderweg an O1 vorbei ---------


def _gen_mit_unisex_widerspruch(mit_diskrepanz: bool) -> ABox:
    gen = Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={
            "zins": belegt(0.0175, [prov()])})],
        unisex=Aussage(zustand=Zustand.WIDERSPRUECHLICH, lesarten=_lesarten(),
                       diskrepanz_id="klv/tg2015#unisex"),
    )
    abox = ABox(fall="f", generationen=[gen])
    if mit_diskrepanz:
        abox.diskrepanzen.append(Diskrepanz(
            id="klv/tg2015#unisex", knoten="klv/tg2015", feld="unisex",
            lesarten=_lesarten(),
        ))
    return abox


def test_unisex_widerspruch_referenziert_diskrepanz_korrekt():
    fehler = validate_abox(_gen_mit_unisex_widerspruch(mit_diskrepanz=True))
    assert not any("verwaist" in f for f in fehler)          # legitim, kein Befund
    fehler = validate_abox(_gen_mit_unisex_widerspruch(mit_diskrepanz=False))
    assert any("unisex" in f and "fehlt" in f for f in fehler)  # GRUEN waere gelogen


def test_unisex_unicode_ziffern_sind_befund_kein_crash():
    abox = _gen_mit_unisex_widerspruch(True)
    abox.generationen[0].unisex = belegt("U7¹", [prov()])   # U7¹
    fehler = validate_abox(abox)
    assert any("U<0..100>" in f for f in fehler)


# --- Finding 2: Zellen-Keying muss den Dimensionen entsprechen -------------


def test_fremd_gekeyte_fragmentzelle_ist_hart(tmp_path: Path):
    f = tmp_path / "fall"
    anlegen(f)
    q = tmp_path / "rechner.xlsm"; q.write_bytes(b"x"); registrieren(f, q)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))
    a = QuellFragment(
        generation="tg2015", quelle_datei="rechner.xlsm", quelle_art="tarifrechner",
        dimensionen=[Merkmalsdimension(id="tarifart", name="T",
                                       auspraegungen=["einzel", "haus"])],
        zellen=[FragmentZelle(auspraegungen={"tarifart": t},
                              parameter={"zins": FragmentWert(wert=0.01, fundstelle="x")})
                for t in ("einzel", "haus")],
    )
    b = QuellFragment(
        generation="tg2015", quelle_datei="rechner.xlsm", quelle_art="tarifrechner",
        zellen=[FragmentZelle(auspraegungen={"status": "einzel"},
                              parameter={"zins": FragmentWert(wert=0.02, fundstelle="y")})],
    )
    with pytest.raises(BefuellungsFehler, match="nicht identifizierbar"):
        baue_generation("tg2015", [a, b], register, {0: "test/extraktion@abc1234", 1: "test/extraktion-b@abc1234"}, ZEIT)


# --- Finding 3: fehlt_in_extraktion ist ein EIGENER Zaehler ----------------


def test_coverage_trennt_stillen_fall_von_aktiv_nicht_belegt():
    gen = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={
            "zins": belegt(0.0175, [prov()]),
            "alpha": Aussage(),                      # gesucht, nicht gefunden
        })],
    )
    [bericht] = coverage_bericht(ABox(fall="f", generationen=[gen]))["generationen"]
    assert bericht["zaehler"]["belegt"] == 1
    assert bericht["zaehler"]["nicht_belegt"] == 1           # alpha (aktiv)
    assert bericht["zaehler"]["fehlt_in_extraktion"] == len(PFLICHT_PARAMETER) - 2


def test_coverage_vollstaendig_ist_und_verknuepfung_ueber_generationen():
    """Mutation all()->any() in 'vollstaendig' muss rot werden."""
    voll = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={
            feld: belegt(1.0 if feld != "tafel" else "DAV2008_T", [prov()])
            for feld in PFLICHT_PARAMETER})],
    )
    leer = Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter={})],
    )
    bericht = coverage_bericht(ABox(fall="f", generationen=[voll, leer]))
    assert bericht["vollstaendig"] is False


# --- Finding 4/8: Unveraenderlichkeit + NaN ---------------------------------


def test_aussage_laesst_sich_nach_konstruktion_nicht_aushebeln():
    a = belegt(1.0, [prov()])
    with pytest.raises((TypeError, AttributeError, ValidationError)):
        a.provenienz.append(prov())                  # Tupel: kein append
    with pytest.raises(ValidationError):
        a.wert = None                                # validate_assignment
    with pytest.raises(ValidationError):
        Lesart(wert=1, provenienz=[prov()]).wert = 2  # frozen


def test_nan_ist_keine_aussage():
    with pytest.raises(ValidationError, match="nicht-endlich"):
        belegt(float("nan"), [prov()])
    with pytest.raises(ValidationError, match="nicht-endlich"):
        FragmentWert(wert=math.inf, fundstelle="x")


# --- Finding 5: Aufloesung ist atomar ---------------------------------------


def test_aufloesung_ohne_treffer_laesst_diskrepanz_unangetastet(tmp_path: Path):
    f = tmp_path / "fall"
    anlegen(f)
    q = tmp_path / "rechner.xlsm"; q.write_bytes(b"x"); registrieren(f, q)
    m = tmp_path / "m.docx"; m.write_bytes(b"y"); registrieren(f, m)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))

    def frag(datei, art, wert):
        return QuellFragment(generation="tg2012", quelle_datei=datei,
                             quelle_art=art, zellen=[FragmentZelle(parameter={
                                 "beta1": FragmentWert(wert=wert, fundstelle="x")})])

    abox = baue_abox(str(f), [frag("m.docx", "tarifmeldung", 0.025),
                              frag("rechner.xlsm", "tarifrechner", 0.03)],
                     register, ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    [d] = abox.diskrepanzen
    # Treffer-lose Diskrepanz: weder Referenz noch Adresse existiert
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg2012/zelle:x#gamma1", knoten="klv/tg2012/zelle:x",
        feld="gamma1", lesarten=_lesarten()))
    with pytest.raises(BefuellungsFehler, match="trifft nichts"):
        loese_diskrepanz_auf(abox, "klv/tg2012/zelle:x#gamma1", 1, "x", "y", ZEIT)
    assert abox.diskrepanzen[1].status == "offen"    # NICHT halb aufgeloest
    assert abox.diskrepanzen[1].entscheidung is None


def test_vorlaeufige_aufloesung_traegt_flag(tmp_path: Path):
    f = tmp_path / "fall"
    anlegen(f)
    q = tmp_path / "rechner.xlsm"; q.write_bytes(b"x"); registrieren(f, q)
    m = tmp_path / "m.docx"; m.write_bytes(b"y"); registrieren(f, m)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))

    def frag(datei, art, wert):
        return QuellFragment(generation="tg2012", quelle_datei=datei,
                             quelle_art=art, zellen=[FragmentZelle(parameter={
                                 "beta1": FragmentWert(wert=wert, fundstelle="x")})])

    abox = baue_abox(str(f), [frag("m.docx", "tarifmeldung", 0.025),
                              frag("rechner.xlsm", "tarifrechner", 0.03)],
                     register, ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    loese_diskrepanz_auf(abox, abox.diskrepanzen[0].id, 0.03,
                         "agent (vorlaeufig)", "GM-Zweck", ZEIT, vorlaeufig=True)
    assert abox.diskrepanzen[0].entscheidung.vorlaeufig is True
    # O1 weist vorlaeufige Entscheidungen aus:
    speichere(abox, f)
    from rechner_pipeline.gates.abox_validate import main
    result = main(["--fall", str(f)])
    assert result.summary["entscheidungen_vorlaeufig"] == [abox.diskrepanzen[0].id]


# --- Finding 7/29: Merge-Toleranz und Gruppen-Konsistenz --------------------


def test_merge_toleranz_ist_eng():
    """1 % Abweichung ist ein KONFLIKT (Mutation 1e-9 -> 1e-3 wird rot)."""
    a = belegt(0.03, [prov()])
    b = belegt(0.0303, [prov(sha=SHA_B, datei="m.docx")])
    ergebnis, diskrepanz = merge_aussagen("k", "beta1", [a, b])
    assert diskrepanz is not None
    # ... und ein 1e-10-Rundungsartefakt ist KEINER:
    c = belegt(0.03, [prov()])
    d = belegt(0.03 * (1 + 1e-10), [prov(sha=SHA_B, datei="m.docx")])
    ergebnis, diskrepanz = merge_aussagen("k", "beta1", [c, d])
    assert diskrepanz is None


# --- Finding 30: importiere_fuer_spez end-to-end ----------------------------


def test_importiere_fuer_spez_p1_und_kreuzprobe(tmp_path: Path):
    from rechner_pipeline.kern.konventionen import MAX_ALTER
    from rechner_pipeline.quellen.tafel_import import (
        TafelImportFehler,
        importiere_fuer_spez,
    )

    fall = tmp_path / "fall"
    anlegen(fall)
    quelle = tmp_path / "Tarifrechner_KLV_TGX.xlsm"
    quelle.write_bytes(b"workbook")
    registrieren(fall, quelle)

    vv = fall / "abgeleitet" / "vorverdichtung" / "xlsm-TGX"
    vv.mkdir(parents=True)
    zeilen = ["Tafeln;$A$3;x/y;x/y", "Tafeln;$B$3;NEU_T_M;NEU_T_M",
              "Tafeln;$C$3;NEU_T_F;NEU_T_F"]
    for i, alter in enumerate(range(0, MAX_ALTER + 1)):
        z = i + 4
        zeilen += [f"Tafeln;$A${z};{alter};{alter}",
                   f"Tafeln;$B${z};0.01;0.01", f"Tafeln;$C${z};0.02;0.02"]
    (vv / "Tafeln.csv").write_text("\n".join(zeilen), encoding="utf-8")

    spez_dir = fall / "abgeleitet" / "spez"
    spez_dir.mkdir(parents=True)
    spez = {
        "spez_version": "0.1.0", "tbox_version": "0.1.0",
        "generation": "klv/tgx", "familie": "klv",
        "backbone": "kern.klv/kommutation+zustandsmodell",
        "urteil": {"ergebnis": "parametrierung", "begruendung": ["test"]},
        "unisex": "U70",
        "zellen": [{"knoten": "klv/tgx/zelle:-", "auspraegungen": {},
                    "model_point": {"tafel": "NEU_T_U70", "zins": 0.01}}],
        "tafel_importe": ["NEU_T_M", "NEU_T_F"],
        "tafel_ableitungen": [{"name": "NEU_T_U70", "basis_m": "NEU_T_M",
                               "basis_f": "NEU_T_F", "maenneranteil": 0.7,
                               "regel": "min1_linear"}],
    }
    (spez_dir / "klv-tgx.spez.json").write_text(
        json.dumps(spez), encoding="utf-8")

    xml = tmp_path / "tafeln.xml"
    xml.write_text("<?xml version='1.0' encoding='UTF-8'?>\n<tafeln>\n</tafeln>\n",
                   encoding="utf-8")
    ergebnis = importiere_fuer_spez(fall, "klv/tgx", xml, dry_run=True)
    assert ergebnis["eingefuegt"] == [] and ergebnis["dry_run"] is True
    ergebnis = importiere_fuer_spez(fall, "klv/tgx", xml)
    assert ergebnis["eingefuegt"] == ["NEU_T_F", "NEU_T_M", "NEU_T_U70"]
    # Idempotenz + Kreuzprobe:
    ergebnis = importiere_fuer_spez(fall, "klv/tgx", xml)
    assert ergebnis["eingefuegt"] == []
    assert ergebnis["bereits_vorhanden_wertgleich"] == [
        "NEU_T_F", "NEU_T_M", "NEU_T_U70"]
    # P1: unregistrierte Quelle bricht ab
    (fall / "eingang.json").write_text(
        json.dumps({"schema_version": 1, "quellen": []}), encoding="utf-8")
    with pytest.raises(TafelImportFehler, match="Eingang-Register"):
        importiere_fuer_spez(fall, "klv/tgx", xml)


# --- Finding 9/12/28: Spez-Vorbedingungen und Rueckrichtung -----------------


def test_spez_verwirft_ungeklaerte_optionale_nicht_still():
    from rechner_pipeline.spez.erzeugen import SpezFehler, baue_spez

    parameter = {feld: belegt(1.0 if feld != "tafel" else "DAV2008_T", [prov()])
                 for feld in PFLICHT_PARAMETER}
    parameter["ratzu_zw12"] = Aussage(
        zustand=Zustand.WIDERSPRUECHLICH, lesarten=_lesarten(),
        diskrepanz_id="klv/tg2012/zelle:-#ratzu_zw12")
    gen = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
    )
    abox = ABox(fall="f", generationen=[gen])
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg2012/zelle:-#ratzu_zw12", knoten="klv/tg2012/zelle:-",
        feld="ratzu_zw12", lesarten=_lesarten()))
    with pytest.raises(SpezFehler, match="optional"):
        baue_spez(abox, "klv/tg2012", vorhandene_tafeln={"DAV2008_T_M", "DAV2008_T_F"})


def test_validate_spez_findet_geloeschtes_pflichtfeld():
    from rechner_pipeline.spez.erzeugen import baue_spez
    from rechner_pipeline.spez.validierung import validate_spez

    parameter = {feld: belegt(1.0 if feld != "tafel" else "DAV2008_T", [prov()])
                 for feld in PFLICHT_PARAMETER}
    gen = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[Quelle(datei="rechner.xlsm", sha256=SHA_A, art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
    )
    abox = ABox(fall="f", generationen=[gen])
    spez = baue_spez(abox, "klv/tg2012",
                     vorhandene_tafeln={"DAV2008_T_M", "DAV2008_T_F"})
    assert validate_spez(spez, abox) == []
    del spez.zellen[0].model_point["stoab_satz"]     # Kern-Default-Falle
    assert any("Pflichtfeld fehlt" in f for f in validate_spez(spez, abox))


# --- Finding 27/18: Gate O3 blockt ohne Tabelle und crasht nie ohne Ledger --


REPO_ROOT = Path(__file__).resolve().parents[1]
FALL = REPO_ROOT / "faelle" / "klv-tg2015"


@pytest.mark.skipif(not FALL.is_dir(), reason="kein Fall-Arbeitsbereich faelle/klv-tg2015")
def test_gate_o3_blockt_ohne_verlaufswerte(tmp_path: Path):
    import shutil

    from rechner_pipeline.gates.generation_golden import main

    kopie = tmp_path / "fall"
    shutil.copytree(FALL, kopie)
    (kopie / "abgeleitet" / "vorverdichtung" / "xlsm-TG2015"
     / "Kalkulation_table_values.csv").unlink()
    result = main(["--fall", str(kopie), "--generation", "klv/tg2015"])
    assert result.exit_code == 30
    assert any("kein Golden Master" in e["message"] for e in result.errors)
    # Der Ledger wurde geschrieben (kein alter gruener bleibt liegen):
    ledger = kopie / "abgeleitet" / "diagnostics" / "generation_golden.gate.json"
    assert json.loads(ledger.read_text(encoding="utf-8"))["status"] == "failed"


@pytest.mark.skipif(not FALL.is_dir(), reason="kein Fall-Arbeitsbereich faelle/klv-tg2015")
def test_gate_o3_blockt_manipulierte_spez(tmp_path: Path):
    """Die Spez ist Projektion: eine editierte Spez traegt keinen GM."""
    import shutil

    from rechner_pipeline.gates.generation_golden import main
    from rechner_pipeline.spez.validierung import spez_pfad

    kopie = tmp_path / "fall"
    shutil.copytree(FALL, kopie)
    pfad = spez_pfad(kopie, "klv/tg2015")
    spez = json.loads(pfad.read_text(encoding="utf-8"))
    for zelle in spez["zellen"]:
        zelle["model_point"]["beta1"] = 0.031        # eigene Wahrheit
    pfad.write_text(json.dumps(spez), encoding="utf-8")
    result = main(["--fall", str(kopie), "--generation", "klv/tg2015"])
    assert result.exit_code == 30
    assert any(e["code"] == "spez_projektion" for e in result.errors)
