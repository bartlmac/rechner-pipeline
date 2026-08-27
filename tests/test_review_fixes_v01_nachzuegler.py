"""Regressionstests zum Nachzuegler-Review (P9-Haertung, Generator, Index).

Knoten: klv, system/architektur
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.ontologie import PFLICHT_PARAMETER
from rechner_pipeline.ontologie.abox import lade, speichere
from rechner_pipeline.ontologie.befuellung import (
    FragmentWert,
    FragmentZelle,
    QuellFragment,
    baue_abox,
    loese_diskrepanz_auf,
)
from rechner_pipeline.spez.erzeugen import baue_spez
from rechner_pipeline.spez.fachspez import erzeuge_fachspez
from rechner_pipeline.spez.validierung import speichere_spez

ZEIT = "2026-08-15T10:00:00+00:00"
TAFELN = {"DAV2008_T_M", "DAV2008_T_F"}
PLAUSIBEL = {
    "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
    "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
    "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}


def _fall(tmp_path: Path) -> Path:
    f = tmp_path / "fall"
    anlegen(f)
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    return f


def _register(f: Path) -> dict:
    return json.loads((f / "eingang.json").read_text(encoding="utf-8"))


def _frag(datei: str, art: str, generation: str = "tg2012", **override):
    parameter = {feld: FragmentWert(
        wert=PLAUSIBEL[feld],
        fundstelle=f"{datei}:{feld}") for feld in PFLICHT_PARAMETER}
    for feld, wert in override.items():
        parameter[feld] = FragmentWert(wert=wert, fundstelle=f"{datei}:{feld}")
    return QuellFragment(generation=generation, quelle_datei=datei,
                         quelle_art=art,
                         zellen=[FragmentZelle(parameter=parameter)])


# --- P9-Haertung: offene Diskrepanzen, fehlende A-Box, request-json --------


@pytest.mark.parametrize("gate", ["A-Q1", "A-M1", "A-M4", "A-K1"])
def test_p9_annahme_blockt_offene_diskrepanzen_fuer_jedes_gate(
    tmp_path: Path, gate: str
):
    """Der staerkere Fall als 'vorlaeufig': GAR KEINE Entscheidung.
    Ein ungeloester Quellen-Widerspruch darf durch KEIN Gate."""
    from rechner_pipeline.gates.gate_entscheid import main

    f = _fall(tmp_path)
    abox = baue_abox(str(f), [
        _frag("meldung.docx", "tarifmeldung", beta1=0.025),
        _frag("rechner.xlsm", "tarifrechner", beta1=0.03),
    ], _register(f), ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    speichere(abox, f)                                # Diskrepanz bleibt OFFEN
    result = main(["--fall", str(f), "--gate", gate,
                   "--entscheid", "angenommen", "--rolle", "mensch", "--entscheider", "X",
                   "--begruendung", "y", "--repo-root", "."])
    assert result.exit_code == 20
    assert any(e["code"] == "offen" for e in result.errors)


def test_p9_annahme_verlangt_die_abox(tmp_path: Path):
    """Die Sperre ist nicht per Dateiloeschung abschaltbar: ohne A-Box
    gibt es nichts abzunehmen."""
    from rechner_pipeline.gates.gate_entscheid import main

    f = _fall(tmp_path)
    result = main(["--fall", str(f), "--gate", "A-M4",
                   "--entscheid", "angenommen", "--rolle", "mensch", "--entscheider", "X",
                   "--begruendung", "y", "--repo-root", "."])
    assert result.exit_code == 20
    assert any(e["code"] == "abox" for e in result.errors)
    # Korrupte A-Box ist Befund MIT Ledger, kein Traceback:
    pfad = f / "abgeleitet" / "abox" / "abox.json"
    pfad.parent.mkdir(parents=True)
    pfad.write_text("{kaputt", encoding="utf-8")
    result = main(["--fall", str(f), "--gate", "A-M4",
                   "--entscheid", "angenommen", "--rolle", "mensch", "--entscheider", "X",
                   "--begruendung", "y", "--repo-root", "."])
    assert result.exit_code == 20
    assert any("unlesbar" in e["message"] for e in result.errors)


def test_p9_request_json_umgeht_keine_validierung(tmp_path: Path):
    from rechner_pipeline.gates.gate_entscheid import main

    f = _fall(tmp_path)
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "fall": str(f), "gate": "G-9", "entscheid": "vielleicht",
        "entscheider": "X", "begruendung": "y",
    }), encoding="utf-8")
    result = main(["--request-json", str(request)])
    assert result.exit_code == 2
    assert any("unbekannt" in e["message"] for e in result.errors)


def test_p9_manipulierter_eingang_blockt_annahme(tmp_path: Path):
    from rechner_pipeline.gates.gate_entscheid import main

    f = _fall(tmp_path)
    abox = baue_abox(str(f), [_frag("rechner.xlsm", "tarifrechner")],
                     _register(f), ["test/extraktion@abc1234"], ZEIT)
    speichere(abox, f)
    kopie = f / "eingang" / "rechner.xlsm"
    kopie.chmod(0o644)
    kopie.write_bytes(b"drift")
    result = main(["--fall", str(f), "--gate", "A-Q1",
                   "--entscheid", "angenommen", "--rolle", "mensch", "--entscheider", "X",
                   "--begruendung", "y", "--repo-root", "."])
    assert result.exit_code == 20
    assert any(e["code"] == "eingang" for e in result.errors)


def test_p9_idempotenz_und_vorgaenger_kette(tmp_path: Path):
    """Hash ohne Zeitstempel: derselbe Entscheid auf demselben Stand ist
    idempotent; ein neuer Entscheid pinnt die Vorgaenger (es gilt der
    Snapshot, den keiner als Vorgaenger nennt)."""
    from rechner_pipeline.gates.gate_entscheid import main

    f = _fall(tmp_path)
    abox = baue_abox(str(f), [_frag("rechner.xlsm", "tarifrechner")],
                     _register(f), ["test/extraktion@abc1234"], ZEIT)
    speichere(abox, f)
    argv = ["--fall", str(f), "--gate", "A-Q1", "--entscheid", "abgelehnt",
            "--rolle", "mensch", "--entscheider", "X",
            "--begruendung", "Zwischenstand", "--repo-root", "."]
    erster = main(argv)
    assert erster.exit_code == 0
    zweiter = main(argv)                       # identischer Entscheid
    assert zweiter.exit_code == 0
    assert zweiter.summary.get("bereits_vorhanden") is True
    snapshots = list((f / "entscheide").glob("A-Q1-*.json"))
    assert len(snapshots) == 1                 # NICHT zwei Dateien
    # Neuer, anderer Entscheid pinnt den ersten als Vorgaenger:
    dritter = main(["--fall", str(f), "--gate", "A-Q1",
                    "--entscheid", "abgelehnt", "--rolle", "mensch", "--entscheider", "X",
                    "--begruendung", "Anderer Grund", "--repo-root", "."])
    assert dritter.exit_code == 0
    neu = json.loads(Path(dritter.paths["snapshot"]).read_text(encoding="utf-8"))
    alt = json.loads(snapshots[0].read_text(encoding="utf-8"))
    assert alt["snapshot_sha256"] in neu["vorgaenger"]
    # Snapshots liegen in der NICHT regenerierbaren Zone:
    assert (f / "entscheide").is_dir()
    assert not (f / "abgeleitet" / "entscheide").exists()


def test_p9_artefakt_hashes_umfassen_eingang_spez_und_snapshots(tmp_path: Path):
    from rechner_pipeline.gates.gate_entscheid import _artefakt_hashes

    f = _fall(tmp_path)
    abox = baue_abox(str(f), [_frag("rechner.xlsm", "tarifrechner")],
                     _register(f), ["test/extraktion@abc1234"], ZEIT)
    speichere(abox, f)
    spez = baue_spez(abox, "klv/tg2012", vorhandene_tafeln=TAFELN)
    speichere_spez(spez, f)
    (f / "entscheide").mkdir()
    (f / "entscheide" / "A-Q1-alt.json").write_text("{}", encoding="utf-8")
    hashes = _artefakt_hashes(f)
    assert "eingang/rechner.xlsm" in hashes          # die Quelle selbst
    assert "abgeleitet/spez/klv-tg2012.spez.json" in hashes
    assert "entscheide/A-Q1-alt.json" in hashes       # Gate-Verkettung
    assert "abgeleitet/abox/abox.json" in hashes


# --- Adress-Aufloesung ueber mehrere Zellen/Generationen (F27) --------------


def test_adress_aufloesung_trifft_nur_die_adressierte_zelle(tmp_path: Path):
    from rechner_pipeline.ontologie import Zustand
    from rechner_pipeline.ontologie.befuellung import baue_generation
    from rechner_pipeline.ontologie.tbox import ABox, Merkmalsdimension

    f = _fall(tmp_path)

    def frag(datei, art, beta_einzel, beta_haus):
        def zelle(t, beta):
            parameter = {feld: FragmentWert(
                wert=PLAUSIBEL[feld],
                fundstelle=f"{datei}:{t}:{feld}") for feld in PFLICHT_PARAMETER}
            parameter["beta1"] = FragmentWert(wert=beta, fundstelle=f"{datei}:{t}")
            return FragmentZelle(auspraegungen={"tarifart": t},
                                 parameter=parameter)
        return QuellFragment(
            generation="tg2015", quelle_datei=datei, quelle_art=art,
            dimensionen=[Merkmalsdimension(
                id="tarifart", name="T", auspraegungen=["einzel", "haus"])],
            zellen=[zelle("einzel", beta_einzel), zelle("haus", beta_haus)],
        )

    gen, diskrepanzen = baue_generation(
        "tg2015",
        [frag("meldung.docx", "tarifmeldung", 0.025, 0.01),
         frag("rechner.xlsm", "tarifrechner", 0.03, 0.0)],
        _register(f), {0: "test/extraktion@abc1234", 1: "test/extraktion-b@abc1234"}, ZEIT,
    )
    abox = ABox(fall=str(f), generationen=[gen], diskrepanzen=diskrepanzen)
    assert len(diskrepanzen) == 2              # beide Zellen kollidieren
    ziel = "klv/tg2015/zelle:einzel#beta1"
    loese_diskrepanz_auf(abox, ziel, 0.03, "x", "y", ZEIT, vorlaeufig=True)
    einzel = next(z for z in gen.zellen if z.id == "zelle:einzel")
    haus = next(z for z in gen.zellen if z.id == "zelle:haus")
    assert einzel.parameter["beta1"].wert == 0.03
    # Die NICHT adressierte Zelle bleibt widerspruechlich:
    assert haus.parameter["beta1"].zustand is Zustand.WIDERSPRUECHLICH


# --- Fachspez: Inhalt und Robustheit (F17, F32) ------------------------------


def test_fachspez_escapet_pipes_und_prueft_abschnitte(tmp_path: Path):
    f = _fall(tmp_path)
    abox = baue_abox(str(f), [
        _frag("meldung.docx", "tarifmeldung", beta1=0.025),
        _frag("rechner.xlsm", "tarifrechner", beta1=0.03),
    ], _register(f), ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    loese_diskrepanz_auf(
        abox, abox.diskrepanzen[0].id, 0.03,
        "agent | mit Pipe", "Grund | mit Pipe\nund Umbruch", ZEIT,
        vorlaeufig=True,
    )
    spez = baue_spez(abox, "klv/tg2012", vorhandene_tafeln=TAFELN)
    text = erzeuge_fachspez(spez, abox)
    assert "agent \\| mit Pipe" in text          # Pipe escaped
    assert "\nund Umbruch" not in text           # Umbruch neutralisiert
    # Kernabschnitte mit echten Zahlen:
    register = _register(f)
    sha = register["quellen"][0]["sha256"][:16]
    assert f"`{sha}...`" in text                  # Abschnitt 1: Quellen-Hash
    assert f"Belegt: {len(PFLICHT_PARAMETER)} von {len(PFLICHT_PARAMETER)}" in text
    assert "## 10 Quellnamen-Mapping" in text
    # Diskrepanz fremder Generationen bleibt draussen (Praefix-Schutz):
    from rechner_pipeline.ontologie import Lesart, Provenienz
    from rechner_pipeline.ontologie.diskrepanz import Diskrepanz

    prov = Provenienz(quelle_datei="rechner.xlsm",
                      quelle_sha256=register["quellen"][1]["sha256"],
                      fundstelle="x", akteur="t", erhoben_am=ZEIT)
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg20121/zelle:-#zins", knoten="klv/tg20121/zelle:-",
        feld="zins",
        lesarten=[Lesart(wert=1, provenienz=[prov]),
                  Lesart(wert=2, provenienz=[prov])]))
    text = erzeuge_fachspez(spez, abox)
    assert "tg20121" not in text


# --- code_index CLI (F34) ----------------------------------------------------


def test_code_index_cli_exit_codes(tmp_path: Path, capsys):
    from rechner_pipeline.ontologie.code_index import main

    assert main(["--src", str(tmp_path / "fehlt")]) == 2
    src = tmp_path / "paket"
    src.mkdir()
    (src / "a.py").write_text('"""A.\n\nKnoten: klv\n"""\n', encoding="utf-8")
    assert main(["--src", str(src)]) == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert ausgabe["drift"] == []
    (src / "a.py").write_text('"""A ohne Annotation."""\n', encoding="utf-8")
    assert main(["--src", str(src)]) == 1        # klv ohne Modul = Drift
