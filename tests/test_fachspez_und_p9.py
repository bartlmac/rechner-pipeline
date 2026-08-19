"""Fachspez-Generator (P7), P9-Snapshot, Entscheide-CLI, Code-Index (D4).

Knoten: klv
"""

from __future__ import annotations

import ast
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
from rechner_pipeline.spez.fachspez import erzeuge_fachspez, speichere_fachspez
from rechner_pipeline.spez.validierung import speichere_spez

ZEIT = "2026-08-15T09:00:00+00:00"
PLAUSIBEL = {
    "zins": 0.0175, "tafel": "DAV2008_T", "alpha": 0.025, "beta1": 0.03,
    "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
    "stoab_max": 150.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}


@pytest.fixture()
def fall_mit_konflikt(tmp_path: Path):
    """Fall mit vollstaendiger A-Box und EINER vorlaeufig geloesten Diskrepanz."""
    f = tmp_path / "fall"
    anlegen(f)
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))

    def frag(datei, art, beta1):
        parameter = {feld: FragmentWert(
            wert=PLAUSIBEL[feld], fundstelle=f"{datei}:x")
            for feld in PFLICHT_PARAMETER}
        parameter["beta1"] = FragmentWert(wert=beta1, fundstelle=f"{datei}:beta1")
        return QuellFragment(generation="tg2012", quelle_datei=datei,
                             quelle_art=art,
                             zellen=[FragmentZelle(parameter=parameter)])

    abox = baue_abox(str(f), [frag("meldung.docx", "tarifmeldung", 0.025),
                              frag("rechner.xlsm", "tarifrechner", 0.03)],
                     register, ["test/extraktion@abc1234", "test/extraktion-b@abc1234"], ZEIT)
    [d] = abox.diskrepanzen
    loese_diskrepanz_auf(abox, d.id, 0.03, "agent (vorlaeufig)", "GM-Zweck",
                         ZEIT, vorlaeufig=True)
    speichere(abox, f)
    spez = baue_spez(abox, "klv/tg2012",
                     vorhandene_tafeln={"DAV2008_T_M", "DAV2008_T_F"})
    speichere_spez(spez, f)
    return f, abox, spez, d.id


def test_fachspez_traegt_herkunft_und_vorlaeufig_warnung(fall_mit_konflikt):
    f, abox, spez, d_id = fall_mit_konflikt
    text = erzeuge_fachspez(spez, abox)
    assert "GENERIERT aus der A-Box" in text
    assert "tarifmeldung+tarifrechner" in text          # Quellenlage
    assert "VORLAEUFIG — G-1-Entscheidung steht aus" in text
    assert "0.025 (tarifmeldung) vs. 0.03 (tarifrechner)" in text
    pfad = speichere_fachspez(spez, abox, f)
    assert pfad.read_text(encoding="utf-8") == text      # deterministisch
    assert speichere_fachspez(spez, abox, f).read_text(encoding="utf-8") == text


def test_fachspez_druckt_anmerkungen_der_abox(fall_mit_konflikt):
    """Beobachtungen ohne Schemafeld erreichen den G-1-Leser (T-Box)."""
    f, abox, spez, _ = fall_mit_konflikt
    ueberschrift = "## 11 Anmerkungen der Extraktion (ohne Schemafeld)"
    # Ohne Anmerkungen bleibt der Abschnitt stehen — Abwesenheit ist
    # selbst eine Aussage, kein weggelassener Abschnitt.
    abschnitt = erzeuge_fachspez(spez, abox).split(ueberschrift)[1]
    assert "keine" in abschnitt

    gen = abox.generationen[0]
    gen.anmerkungen.extend([
        "[meldung.docx] beta0 = 0,5 % genannt, kein Pflichtfeld",
        "[rechner.xlsm] Tafelname in Blatt 2 abweichend geschrieben",
    ])
    abschnitt = erzeuge_fachspez(spez, abox).split(ueberschrift)[1]
    for anmerkung in gen.anmerkungen:
        assert anmerkung in abschnitt
    assert "menschlich zu wuerdigen" in abschnitt


def test_p9_annahme_blockt_bei_vorlaeufigen(fall_mit_konflikt):
    from rechner_pipeline.gates.gate_entscheid import main

    f, *_ = fall_mit_konflikt
    result = main(["--fall", str(f), "--gate", "G-1",
                   "--entscheid", "angenommen", "--rolle", "mensch", "--entscheider", "Bartek",
                   "--begruendung", "ok", "--repo-root", "."])
    assert result.exit_code == 20
    assert any("vorlaeufig" in e["code"] for e in result.errors)
    # Ablehnung ist jederzeit snapshotbar:
    result = main(["--fall", str(f), "--gate", "G-1",
                   "--entscheid", "abgelehnt", "--rolle", "mensch", "--entscheider", "Bartek",
                   "--begruendung", "Zins offen", "--repo-root", "."])
    assert result.exit_code == 0
    snapshot = json.loads(
        Path(result.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["entscheider"] == "Bartek"
    assert snapshot["snapshot_sha256"]
    assert "eingang.json" in snapshot["artefakt_hashes"]
    assert "abgeleitet/abox/abox.json" in snapshot["artefakt_hashes"]
    assert snapshot["system"]["commit"] != ""


def test_entscheide_cli_finalisiert_und_p9_nimmt_an(fall_mit_konflikt, capsys):
    from rechner_pipeline.gates.gate_entscheid import main as p9
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    f, _, _, d_id = fall_mit_konflikt
    rc = entscheide([
        "--fall", str(f), "--rolle", "mensch", "--diskrepanz", d_id, "--wert", "0.025",
        "--entscheider", "Bartek",
        "--begruendung", "Meldung ist die eingereichte Fassung",
    ])
    assert rc == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert ausgabe["entschieden"] == [d_id]
    assert ausgabe["verbleibend_vorlaeufig"] == []
    abox = lade(f)
    [d] = abox.diskrepanzen
    assert d.entscheidung.vorlaeufig is False
    assert d.entscheidung.entscheider == "Bartek"
    # Die Aussage folgt der NEUEN Wahl (0.025, Meldungs-Lesart):
    assert abox.generationen[0].zellen[0].parameter["beta1"].wert == 0.025
    # Eine endgueltige Entscheidung ist nicht erneut ueberschreibbar:
    rc = entscheide([
        "--fall", str(f), "--rolle", "mensch", "--diskrepanz", d_id, "--wert", "0.03",
        "--entscheider", "X", "--begruendung", "y",
    ])
    assert rc == 1
    assert "nie ueberschrieben" in capsys.readouterr().err
    # Vorbedingung der Annahme: Gate O1 muss auf DIESEM Stand gruen sein.
    from rechner_pipeline.gates.abox_validate import main as o1

    result = p9(["--fall", str(f), "--gate", "G-1",
                 "--entscheid", "angenommen", "--rolle", "mensch",
                 "--entscheider", "Bartek",
                 "--begruendung", "Alle Diskrepanzen entschieden",
                 "--repo-root", "."])
    assert result.exit_code == 20                    # O1 fehlt noch
    assert any(e["code"] == "vorbedingung" for e in result.errors)
    assert o1(["--fall", str(f)]).exit_code == 0
    # Jetzt darf P9 annehmen:
    result = p9(["--fall", str(f), "--gate", "G-1",
                 "--entscheid", "angenommen", "--rolle", "mensch",
                 "--entscheider", "Bartek",
                 "--begruendung", "Alle Diskrepanzen entschieden",
                 "--repo-root", "."])
    assert result.exit_code == 0


def test_p9_meldungen_nennen_das_kommando_das_weiterhilft(fall_mit_konflikt, tmp_path):
    """Ein Gate meldet nicht nur, DASS etwas fehlt (Systempruefung F6).

    Drei Einstiegsfaelle, in denen ein Bediener landet — jeder muss das
    Kommando nennen, das den fehlenden Eingang herstellt.
    """
    from rechner_pipeline.gates.gate_entscheid import main
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    basis = ["--gate", "G-1", "--entscheid", "angenommen", "--rolle", "mensch",
             "--entscheider", "Bartek", "--begruendung", "ok", "--repo-root", "."]

    # (a) gar kein Arbeitsbereich -> das Anlege- UND das Registrier-Kommando
    leer = tmp_path / "kein_fall"
    result = main(["--fall", str(leer)] + basis)
    assert result.exit_code == 2
    [fehler] = result.errors
    assert "rechner_pipeline.fall anlegen" in fehler["message"]
    assert "rechner_pipeline.fall registrieren" in fehler["message"]

    # (b) Arbeitsbereich ohne A-Box -> das Merge-Kommando der Stufe 1
    ohne_abox = tmp_path / "ohne_abox"
    anlegen(ohne_abox)
    quelle = tmp_path / "rechner.xlsm"
    quelle.write_bytes(b"x")
    registrieren(ohne_abox, quelle)
    result = main(["--fall", str(ohne_abox)] + basis)
    assert result.exit_code == 20
    [fehler] = result.errors
    assert fehler["code"] == "abox"
    assert "rechner_pipeline.gates.abox_merge" in fehler["message"]
    assert f"--fall {ohne_abox}" in fehler["message"]

    # (c) A-Box entschieden, aber Gate O1 nie gelaufen -> das O1-Kommando
    f, _, _, d_id = fall_mit_konflikt
    assert entscheide([
        "--fall", str(f), "--rolle", "mensch", "--diskrepanz", d_id,
        "--wert", "0.025", "--entscheider", "Bartek",
        "--begruendung", "Meldung ist die eingereichte Fassung",
    ]) == 0
    result = main(["--fall", str(f)] + basis)
    assert result.exit_code == 20
    [fehler] = result.errors
    assert fehler["code"] == "vorbedingung"
    assert "rechner_pipeline.gates.abox_validate" in fehler["message"]
    assert f"--fall {f}" in fehler["message"]


def test_subprozess_bleibt_auf_die_p9_provenienz_beschraenkt():
    """Genau EIN Subprozess in ``src/``: die Git-Provenienz des Snapshots.

    Die Nicht-Verhandelbare "kein Netz, kein Subprozess, keine dynamische
    Ausfuehrung" gilt dem RECHEN- und BEWERTUNGSPFAD; ``_git_stand``
    rechnet nichts und bewertet nichts, es protokolliert den Systemstand
    (Systempruefung F22). Diese Ausnahme ist damit genau eine — der Test
    faengt den naechsten Einzug, und er faengt auch die Umwidmung des
    vorhandenen Aufrufs auf ein beliebiges Kommando.
    """
    src = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"

    def _importiert_subprocess(baum: ast.Module) -> bool:
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Import):
                if any(a.name.split(".")[0] == "subprocess" for a in knoten.names):
                    return True
            elif isinstance(knoten, ast.ImportFrom):
                if (knoten.module or "").split(".")[0] == "subprocess":
                    return True
        return False

    baeume = {
        str(pfad.relative_to(src)): ast.parse(pfad.read_text(encoding="utf-8"))
        for pfad in src.rglob("*.py")
    }
    assert sorted(n for n, b in baeume.items() if _importiert_subprocess(b)) == [
        "gates/gate_entscheid.py"
    ]

    baum = baeume["gates/gate_entscheid.py"]
    stellen = [
        (funktion.name, knoten.attr)
        for funktion in ast.walk(baum)
        if isinstance(funktion, ast.FunctionDef)
        for knoten in ast.walk(funktion)
        if isinstance(knoten, ast.Attribute)
        and isinstance(knoten.value, ast.Name)
        and knoten.value.id == "subprocess"
    ]
    assert stellen == [("_git_stand", "run")]

    # Nur lesende git-Aufrufe — kein beliebiges Kommando, kein Netz.
    kommandos = [
        [e.value for e in knoten.elts]
        for knoten in ast.walk(baum)
        if isinstance(knoten, ast.List) and knoten.elts
        and all(isinstance(e, ast.Constant) for e in knoten.elts)
        and knoten.elts[0].value == "git"
    ]
    assert kommandos == [
        ["git", "rev-parse", "HEAD"],
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        ["git", "status", "--porcelain"],
    ]


def test_entscheide_alle_vorlaeufigen_nach_quelle(fall_mit_konflikt, capsys):
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    f, *_ = fall_mit_konflikt
    rc = entscheide([
        "--fall", str(f), "--rolle", "mensch", "--alle-vorlaeufigen",
        "--quelle", "rechner.xlsm", "--entscheider", "Bartek",
        "--begruendung", "Fachverantwortlicher bestaetigt den Rechner-Stand",
    ])
    assert rc == 0
    abox = lade(f)
    assert all(not d.entscheidung.vorlaeufig for d in abox.diskrepanzen)
    assert abox.generationen[0].zellen[0].parameter["beta1"].wert == 0.03


def test_code_index_findet_annotationen_und_drift(tmp_path: Path):
    from rechner_pipeline.ontologie.code_index import baue_index, drift_report

    src = tmp_path / "paket"
    src.mkdir()
    (src / "a.py").write_text('"""Modul A.\n\nKnoten: klv\n"""\n', encoding="utf-8")
    (src / "b.py").write_text('"""Modul B ohne Annotation."""\n', encoding="utf-8")
    index = baue_index(src)
    assert index["knoten"] == {"klv": ["paket/a.py"]}
    assert index["module"] == {"paket/a.py": ["klv"]}
    assert index["unannotiert"] == ["paket/b.py"]
    # Beschluss 2026-08-18: ein unannotiertes Modul ist HARTER Drift
    # (kein Baustein ohne ontologischen Knoten), nicht Bestandsaufnahme.
    befunde = drift_report(index, ["klv"])
    assert any("paket/b.py: keine Knoten-Annotation" in b for b in befunde)
    assert any("Familie 'bu'" in b for b in drift_report(index, ["klv", "bu"]))


def test_code_index_des_repos_hat_keinen_drift():
    from rechner_pipeline.ontologie.code_index import baue_index, drift_report

    src = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"
    index = baue_index(src)
    assert drift_report(index, ["klv", "bu"]) == []
    # Die Ontologie-/Spez-/Gate-Schicht ist annotiert:
    assert len(index["knoten"]["klv"]) >= 8
