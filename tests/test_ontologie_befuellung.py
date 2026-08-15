"""Stage 1: Fragment -> A-Box (deterministischer Merge) + Gate O1."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.ontologie import Zustand
from rechner_pipeline.ontologie.abox import lade, speichere
from rechner_pipeline.ontologie.befuellung import (
    BefuellungsFehler,
    FragmentWert,
    FragmentZelle,
    QuellFragment,
    baue_abox,
    baue_generation,
    loese_diskrepanz_auf,
)
from rechner_pipeline.ontologie.tbox import Merkmalsdimension

ZEIT = "2026-08-14T19:00:00+00:00"


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = tmp_path / "fall"
    anlegen(f, beschreibung="Testfall")
    for name, inhalt in (
        ("rechner.xlsm", b"rechner-bytes"),
        ("meldung.docx", b"meldung-bytes"),
    ):
        q = tmp_path / name
        q.write_bytes(inhalt)
        registrieren(f, q)
    return f


def _register(fall: Path) -> dict:
    return json.loads((fall / "eingang.json").read_text(encoding="utf-8"))


def _fragment(quelle: str, art: str, **parameter) -> QuellFragment:
    return QuellFragment(
        generation="tg2012",
        quelle_datei=quelle,
        quelle_art=art,
        zellen=[FragmentZelle(parameter={
            feld: FragmentWert(wert=wert, fundstelle=f"{quelle}:{feld}")
            for feld, wert in parameter.items()
        })],
    )


def test_uebereinstimmende_quellen_vereinen_belege(fall: Path):
    meldung = _fragment("meldung.docx", "tarifmeldung", zins=0.0175)
    rechner = _fragment("rechner.xlsm", "tarifrechner", zins=0.0175, beta1=0.03)
    gen, diskrepanzen = baue_generation(
        "tg2012", [meldung, rechner], _register(fall),
        {0: "test/agent-meldung@abc1234", 1: "test/agent-rechner@abc1234"}, ZEIT,
    )
    assert not diskrepanzen
    zins = gen.zellen[0].parameter["zins"]
    assert zins.zustand is Zustand.BELEGT and len(zins.provenienz) == 2
    # Provenienz traegt den echten Hash aus dem Eingang-Register:
    register_hashes = {q["datei"]: q["sha256"] for q in _register(fall)["quellen"]}
    assert zins.provenienz[0].quelle_sha256 == register_hashes["meldung.docx"]
    assert zins.provenienz[0].akteur == "test/agent-meldung@abc1234"


def test_widerspruch_wird_diskrepanz_nicht_overwrite(fall: Path):
    meldung = _fragment("meldung.docx", "tarifmeldung", beta1=0.025)
    rechner = _fragment("rechner.xlsm", "tarifrechner", beta1=0.03)
    gen, diskrepanzen = baue_generation(
        "tg2012", [meldung, rechner], _register(fall), {0: "test/extraktion@abc1234", 1: "test/extraktion-b@abc1234"}, ZEIT,
    )
    [d] = diskrepanzen
    assert d.status == "offen"
    assert sorted(l.wert for l in d.lesarten) == [0.025, 0.03]
    aussage = gen.zellen[0].parameter["beta1"]
    assert aussage.zustand is Zustand.WIDERSPRUECHLICH
    assert aussage.diskrepanz_id == d.id


def test_gesucht_nicht_gefunden_ist_nicht_belegt(fall: Path):
    rechner = _fragment("rechner.xlsm", "tarifrechner", zins=0.0175)
    rechner.nicht_belegt = ["stoab_satz"]
    gen, _ = baue_generation(
        "tg2012", [rechner], _register(fall), {0: "test/extraktion@abc1234"}, ZEIT,
    )
    assert gen.zellen[0].parameter["stoab_satz"].zustand is Zustand.NICHT_BELEGT
    # Nie erwaehnte Felder stehen NICHT drin (Coverage: fehlt_in_extraktion):
    assert "alpha" not in gen.zellen[0].parameter


def test_unregistrierte_quelle_ist_fail_fast(fall: Path):
    fremd = _fragment("fremd.xlsm", "tarifrechner", zins=0.01)
    with pytest.raises(BefuellungsFehler, match="nicht registriert"):
        baue_generation("tg2012", [fremd], _register(fall), {0: "test/extraktion@abc1234"}, ZEIT)


def test_dimensions_konflikt_ist_kein_merge_fall(fall: Path):
    a = _fragment("meldung.docx", "tarifmeldung", zins=0.01)
    a.dimensionen = [Merkmalsdimension(
        id="tarifart", name="Tarifart", auspraegungen=["einzel", "kollektiv"])]
    a.zellen[0].auspraegungen = {"tarifart": "einzel"}
    b = _fragment("rechner.xlsm", "tarifrechner", zins=0.01)
    b.dimensionen = [Merkmalsdimension(
        id="tarifart", name="Tarifart",
        auspraegungen=["einzel", "kollektiv", "haus"])]
    b.zellen[0].auspraegungen = {"tarifart": "einzel"}
    with pytest.raises(BefuellungsFehler, match="Merkmalsraum-Konflikte"):
        baue_generation("tg2012", [a, b], _register(fall), {0: "test/extraktion@abc1234", 1: "test/extraktion-b@abc1234"}, ZEIT)


def test_aufloesung_waehlt_lesart_und_zieht_aussage_nach(fall: Path):
    meldung = _fragment("meldung.docx", "tarifmeldung", beta1=0.025)
    rechner = _fragment("rechner.xlsm", "tarifrechner", beta1=0.03)
    abox = baue_abox(
        str(fall), [meldung, rechner], _register(fall), ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT,
    )
    [d] = abox.diskrepanzen
    with pytest.raises(BefuellungsFehler, match="keine der Lesarten"):
        loese_diskrepanz_auf(abox, d.id, 0.0275, "bartek", "Mittelwert", ZEIT)
    loese_diskrepanz_auf(
        abox, d.id, 0.025, "bartek",
        "Die Tarifmeldung ist die eingereichte Fassung", ZEIT,
    )
    assert abox.diskrepanzen[0].status == "aufgeloest"
    assert abox.diskrepanzen[0].entscheidung.entscheider == "bartek"
    aussage = abox.generationen[0].zellen[0].parameter["beta1"]
    assert aussage.zustand is Zustand.BELEGT and aussage.wert == 0.025
    # Die Provenienz der gewaehlten Lesart bleibt erhalten:
    assert aussage.provenienz[0].quelle_datei == "meldung.docx"
    with pytest.raises(BefuellungsFehler, match="bereits aufgeloest"):
        loese_diskrepanz_auf(abox, d.id, 0.03, "x", "y", ZEIT)


# --------------------------------------------------------------------------- #
# Gate O1
# --------------------------------------------------------------------------- #


def _gate(fall: Path):
    from rechner_pipeline.gates.abox_validate import main
    return main(["--fall", str(fall)])


def test_gate_gruen_bei_vollstaendiger_abox(fall: Path):
    from rechner_pipeline.ontologie.tbox import PFLICHT_PARAMETER

    voll = {
        "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
        "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
        "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
        "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
    }
    rechner = _fragment("rechner.xlsm", "tarifrechner", **voll)
    abox = baue_abox(str(fall), [rechner], _register(fall), ["test/extraktion@abc1234"], ZEIT)
    speichere(abox, fall)
    result = _gate(fall)
    assert result.exit_code == 0
    assert result.summary["vollstaendig"] is True
    assert (fall / "abgeleitet" / "abox" / "coverage.json").is_file()
    assert (fall / "abgeleitet" / "diagnostics" / "abox_validate.gate.json").is_file()


def test_gate_blockt_luecken_und_offene_diskrepanzen(fall: Path):
    meldung = _fragment("meldung.docx", "tarifmeldung", beta1=0.025)
    rechner = _fragment("rechner.xlsm", "tarifrechner", beta1=0.03)
    abox = baue_abox(
        str(fall), [meldung, rechner], _register(fall), ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT,
    )
    speichere(abox, fall)
    result = _gate(fall)
    assert result.exit_code == 20
    codes = {e["code"] for e in result.errors}
    assert "coverage" in codes            # Pflichtumfang nicht belegt
    assert "diskrepanzen_offen" in codes  # Aufloesung ist menschlich (G-1)


def test_gate_blockt_manipulierten_eingang(fall: Path):
    rechner = _fragment("rechner.xlsm", "tarifrechner", zins=0.0175)
    abox = baue_abox(str(fall), [rechner], _register(fall), ["test/extraktion@abc1234"], ZEIT)
    # A-Box behauptet einen anderen Quell-Hash als das Register:
    abox.generationen[0].quellen[0] = abox.generationen[0].quellen[0].model_copy(
        update={"sha256": "f" * 64}
    )
    speichere(abox, fall)
    result = _gate(fall)
    assert result.exit_code == 20
    assert any("registriert ist" in e["message"] for e in result.errors)


def test_gate_usage_ohne_fall(tmp_path: Path):
    from rechner_pipeline.gates.abox_validate import main

    result = main(["--diagnostics-dir", str(tmp_path / "diag")])
    assert result.exit_code == 2


def test_quellnamen_divergenz_wird_vereint_nicht_entschieden(fall: Path):
    """Quellnamen-Mappings sind Dokumentation: kosmetisch abweichende
    Formulierungen zweier Agenten bleiben beide sichtbar erhalten."""
    a = _fragment("meldung.docx", "tarifmeldung", zins=0.0175)
    a.quellnamen = {"StoAb": "parameter:stoab_satz/min/max"}
    b = _fragment("rechner.xlsm", "tarifrechner", zins=0.0175)
    b.quellnamen = {"StoAb": "parameter:stoab_satz|min|max", "k": "parameter:policy_fee"}
    gen, _ = baue_generation(
        "tg2012", [a, b], _register(fall), {0: "test/extraktion@abc1234", 1: "test/extraktion-b@abc1234"}, ZEIT,
    )
    assert gen.quellnamen["k"] == "parameter:policy_fee"
    assert set(gen.quellnamen["StoAb"].split(" | ")) == {
        "parameter:stoab_satz/min/max", "parameter:stoab_satz|min|max",
    }
