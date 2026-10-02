"""Fachspez-Generator (P7), P9-Snapshot, Entscheide-CLI, Code-Index (D4).

Hier haengt auch der Waechter ueber die EINE Subprozess-Ausnahme des
Pakets (P9-Provenienz) und die oeffentliche Zusage, die sie benennt
(ONBOARDING.md) — Regel und Zusage muessen zusammen rot werden koennen.

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


from tests.zeichnung_fixture import linie_args, entscheide_args, VA, annahme_args


def _freigabe_arg(fall: Path) -> list[str]:
    """Ordnung und Schluessel neben dem Fall (ADR-018)."""
    return annahme_args(fall)


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
    assert "VORLAEUFIG — A-Q1-Entscheidung steht aus" in text
    assert "0.025 (tarifmeldung) vs. 0.03 (tarifrechner)" in text
    pfad = speichere_fachspez(spez, abox, f)
    assert pfad.read_text(encoding="utf-8") == text      # deterministisch
    assert speichere_fachspez(spez, abox, f).read_text(encoding="utf-8") == text


def test_fachspez_druckt_anmerkungen_der_abox(fall_mit_konflikt):
    """Beobachtungen ohne Schemafeld erreichen den A-Q1-Leser (T-Box)."""
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
    result = main(["--fall", str(f), *linie_args(f), "--gate", "A-Q1",
                   "--entscheid", "angenommen", "--rolle", VA, "--entscheider", "maintainer",
                   "--begruendung", "ok", "--repo-root", "."])
    assert result.exit_code == 20
    assert any("vorlaeufig" in e["code"] for e in result.errors)
    # Ablehnung ist jederzeit snapshotbar:
    result = main(["--fall", str(f), *linie_args(f), "--gate", "A-Q1",
                   "--entscheid", "abgelehnt", "--rolle", VA, "--entscheider", "maintainer",
                   "--begruendung", "Zins offen", "--repo-root", "."])
    assert result.exit_code == 0
    snapshot = json.loads(
        Path(result.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["entscheider"] == "maintainer"
    assert snapshot["snapshot_sha256"]
    assert "eingang.json" in snapshot["artefakt_hashes"]
    assert "abgeleitet/abox/abox.json" in snapshot["artefakt_hashes"]
    assert snapshot["system"]["commit"] != ""


def test_entscheide_cli_finalisiert_und_p9_nimmt_an(fall_mit_konflikt, capsys):
    from rechner_pipeline.gates.gate_entscheid import main as p9
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    f, _, _, d_id = fall_mit_konflikt
    rc = entscheide([
        "--fall", str(f), *entscheide_args(f), "--diskrepanz", d_id, "--wert", "0.025",
        "--entscheider", "maintainer",
        "--begruendung", "Meldung ist die eingereichte Fassung",
    ])
    assert rc == 0
    ausgabe = json.loads(capsys.readouterr().out)
    assert ausgabe["entschieden"] == [d_id]
    assert ausgabe["verbleibend_vorlaeufig"] == []
    abox = lade(f)
    [d] = abox.diskrepanzen
    assert d.entscheidung.vorlaeufig is False
    assert d.entscheidung.entscheider == "maintainer"
    # Die Aussage folgt der NEUEN Wahl (0.025, Meldungs-Lesart):
    assert abox.generationen[0].zellen[0].parameter["beta1"].wert == 0.025
    # Eine endgueltige Entscheidung ist nicht erneut ueberschreibbar:
    rc = entscheide([
        "--fall", str(f), *entscheide_args(f), "--diskrepanz", d_id, "--wert", "0.03",
        "--entscheider", "X", "--begruendung", "y",
    ])
    assert rc == 1
    assert "nie ueberschrieben" in capsys.readouterr().err
    # Vorbedingung der Annahme: Gate P-Q3 muss auf DIESEM Stand gruen sein.
    from rechner_pipeline.gates.abox_validate import main as pq3

    result = p9(["--fall", str(f), "--gate", "A-Q1",
                 "--entscheid", "angenommen", "--rolle", VA,
                 "--entscheider", "maintainer",
                 "--begruendung", "Alle Diskrepanzen entschieden",
                 "--repo-root", ".", *_freigabe_arg(f)])
    assert result.exit_code == 20                    # P-Q3 fehlt noch
    assert any(e["code"] == "vorbedingung" for e in result.errors)
    assert pq3(["--fall", str(f)]).exit_code == 0
    # Jetzt darf P9 annehmen:
    result = p9(["--fall", str(f), "--gate", "A-Q1",
                 "--entscheid", "angenommen", "--rolle", VA,
                 "--entscheider", "maintainer",
                 "--begruendung", "Alle Diskrepanzen entschieden",
                 "--repo-root", ".", *_freigabe_arg(f)])
    assert result.exit_code == 0


def test_p9_meldungen_nennen_das_kommando_das_weiterhilft(fall_mit_konflikt, tmp_path):
    """Ein Gate meldet nicht nur, DASS etwas fehlt (Systempruefung F6).

    Drei Einstiegsfaelle, in denen ein Bediener landet — jeder muss das
    Kommando nennen, das den fehlenden Eingang herstellt.
    """
    from rechner_pipeline.gates.gate_entscheid import main
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    basis = ["--gate", "A-Q1", "--entscheid", "angenommen", "--rolle", VA,
             "--entscheider", "maintainer", "--begruendung", "ok", "--repo-root", "."]

    # (a) gar kein Arbeitsbereich -> das Anlege- UND das Registrier-Kommando
    leer = tmp_path / "kein_fall"
    result = main(["--fall", str(leer), *linie_args(leer)] + basis)
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
    result = main(["--fall", str(ohne_abox), *linie_args(ohne_abox)] + basis)
    assert result.exit_code == 20
    [fehler] = result.errors
    assert fehler["code"] == "abox"
    assert "rechner_pipeline.gates.abox_merge" in fehler["message"]
    assert f"--fall {ohne_abox}" in fehler["message"]

    # (c) A-Box entschieden, aber Gate P-Q3 nie gelaufen -> das P-Q3-Kommando
    f, _, _, d_id = fall_mit_konflikt
    assert entscheide([
        "--fall", str(f), *entscheide_args(f), "--diskrepanz", d_id,
        "--wert", "0.025", "--entscheider", "maintainer",
        "--begruendung", "Meldung ist die eingereichte Fassung",
    ]) == 0
    result = main(["--fall", str(f), *linie_args(f)] + basis)
    assert result.exit_code == 20
    [fehler] = result.errors
    assert fehler["code"] == "vorbedingung"
    assert "rechner_pipeline.gates.abox_validate" in fehler["message"]
    assert f"--fall {f}" in fehler["message"]


#: Prozessstart AUSSERHALB von ``subprocess`` — anderer Weg, gleiche
#: Wirkung. Exakte Attributnamen statt Praefix-Heuristik: der Waechter
#: soll scharf bleiben (``os.path``, ``os.environ`` sind kein
#: Prozessstart und duerfen ihn nicht ausloesen).
OS_PROZESSSTART = (
    "system", "popen",
    "execl", "execle", "execlp", "execlpe",
    "execv", "execve", "execvp", "execvpe",
    "spawnl", "spawnle", "spawnlp", "spawnlpe",
    "spawnv", "spawnve", "spawnvp", "spawnvpe",
    "posix_spawn", "posix_spawnp",
    "fork", "forkpty",
)


def _os_prozessstarts(baum: ast.Module) -> list:
    """Prozessstarts ueber ``os`` in einem Modul (sortiert, leer = keiner).

    Erfasst wird der Aufrufweg, nicht der Modulname: ``import os as _os``
    bindet den Alias, ``from os import system`` das Symbol direkt.
    """
    alias_namen = {"os"}
    treffer: list = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Import):
            for a in knoten.names:
                if a.name == "os" and a.asname:
                    alias_namen.add(a.asname)
        elif isinstance(knoten, ast.ImportFrom):
            if (knoten.module or "") == "os":
                treffer.extend(
                    f"os.{a.name}" for a in knoten.names
                    if a.name in OS_PROZESSSTART
                )
    for knoten in ast.walk(baum):
        if (isinstance(knoten, ast.Attribute)
                and isinstance(knoten.value, ast.Name)
                and knoten.value.id in alias_namen
                and knoten.attr in OS_PROZESSSTART):
            treffer.append(f"os.{knoten.attr}")
    return sorted(treffer)


def test_pk1_hinweis_ist_je_generation_eine_kopierbare_zeile(tmp_path: Path):
    """Ein Hinweis zum Kopieren muss sich kopieren lassen (Folgefund C11).

    Bei mehreren Generationen ergab die Zusammensetzung mit ``|`` ein
    ``--generation klv/tg2012|klv/tg2015`` — als Shell-Zeile eine Pipe,
    also gerade kein uebernehmbares Kommando. Es gibt je Generation
    eine eigene Zeile, denn P-K1 laeuft je Generation.
    """
    from rechner_pipeline.gates.abox_validate import main as pq3
    from rechner_pipeline.gates.gate_entscheid import main

    f = tmp_path / "fall"
    anlegen(f)
    for name in ("rechner.xlsm", "meldung.docx"):
        q = tmp_path / name
        q.write_bytes(name.encode())
        registrieren(f, q)
    register = json.loads((f / "eingang.json").read_text(encoding="utf-8"))

    def frag(datei, art, generation):
        parameter = {feld: FragmentWert(
            wert=PLAUSIBEL[feld], fundstelle=f"{datei}:x")
            for feld in PFLICHT_PARAMETER}
        return QuellFragment(generation=generation, quelle_datei=datei,
                             quelle_art=art,
                             zellen=[FragmentZelle(parameter=parameter)])

    abox = baue_abox(
        str(f),
        [frag("meldung.docx", "tarifmeldung", "tg2012"),
         frag("rechner.xlsm", "tarifrechner", "tg2015")],
        register, ["test/extraktion@abc1234", "test/extraktion-b@abc1234"],
        ZEIT,
    )
    speichere(abox, f)
    assert [g.id for g in abox.generationen] == ["klv/tg2012", "klv/tg2015"]
    assert pq3(["--fall", str(f)]).exit_code == 0

    result = main(["--fall", str(f), *linie_args(f), "--gate", "A-M4", "--entscheid",
                   "angenommen", "--rolle", VA, "--entscheider",
                   "maintainer", "--begruendung", "ok", "--repo-root", "."])
    assert result.exit_code == 20
    [fehler] = result.errors
    assert fehler["code"] == "vorbedingung"
    meldung = fehler["message"]
    # Keine Pipe, kein zusammengeklebtes Generations-Argument:
    assert "|" not in meldung
    zeilen = [z for z in meldung.splitlines()
              if "rechner_pipeline.gates.generation_golden" in z]
    assert len(zeilen) == 2
    for generation, zeile in zip(("klv/tg2012", "klv/tg2015"), zeilen):
        # Jede Zeile ist FÜR SICH ein vollstaendiges Kommando.
        kommando = zeile[zeile.index("python -m"):]
        assert kommando.startswith(
            "python -m rechner_pipeline.gates.generation_golden ")
        assert f"--generation {generation} " in kommando
        assert f"--fall {f} " in kommando


def test_abnahme_runbook_reicht_die_neuen_pruefgroessen_durch():
    """Die Abnahmesuite prueft Jahresbeitrag und Vollstaendigkeit NUR,
    wenn der Fall sie mitgibt — sonst weist jeder Abnahmebericht zwei
    Pruefluecken aus (Folgefund C9). Das Runbook muss beides
    durchreichen, unter den echten Feldnamen der Suite: der Test bindet
    den Skill-Text an den Code-Contract, damit weder ein erfundener Name
    noch eine Umbenennung im Code unbemerkt bleibt.
    """
    import dataclasses
    import inspect

    from rechner_pipeline.qa import migrationssuite

    felder = {
        feld.name
        for feld in dataclasses.fields(migrationssuite.VertragsPruefung)
    }
    assert "bjb_erwartet_1" in felder
    parameter = inspect.signature(migrationssuite.pruefe_bestand).parameters
    assert "erwartete_anzahl" in parameter

    repo = Path(__file__).resolve().parents[1]
    for basis in (".claude", ".agents"):
        for skill in ("pruefe-migrationscontrolling",
                      "migrationsfall-durchfuehren"):
            text = (repo / basis / "skills" / skill / "SKILL.md").read_text(
                encoding="utf-8")
            assert "bjb_erwartet_1" in text, (basis, skill)
            assert "erwartete_anzahl" in text, (basis, skill)


def test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt():
    """Genau EIN Subprozess in ``src/``: Git-Provenienz fuer P-K1 und P9.

    Die Nicht-Verhandelbare "kein Netz, kein Subprozess, keine dynamische
    Ausfuehrung" gilt dem RECHEN- und BEWERTUNGSPFAD; ``_git_stand``
    rechnet nichts und bewertet nichts, es protokolliert den Systemstand
    (Systempruefung F22). Diese Ausnahme ist damit genau eine — der Test
    faengt den naechsten Einzug, und er faengt auch die Umwidmung des
    vorhandenen Aufrufs auf ein beliebiges Kommando.

    Ein Waechter, der nur ``subprocess`` kennt, waere ein halber: derselbe
    Fremdprozess laesst sich ueber ``os.system``/``os.popen``/``os.exec*``
    /``os.spawn*``/``os.fork`` starten. Diese Wege sind hier AUSNAHMSLOS
    verboten — auch in ``gate_entscheid``, denn die eine gerechtfertigte
    Ausnahme ist der geprueft-enge ``subprocess.run`` auf drei lesende
    git-Aufrufe, kein zweiter Startweg daneben.
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
        "gates/_provenienz.py"
    ]

    baum = baeume["gates/_provenienz.py"]
    stellen = [
        (funktion.name, knoten.attr)
        for funktion in ast.walk(baum)
        if isinstance(funktion, ast.FunctionDef)
        for knoten in ast.walk(funktion)
        if isinstance(knoten, ast.Attribute)
        and isinstance(knoten.value, ast.Name)
        and knoten.value.id == "subprocess"
    ]
    assert stellen == [("_git_lesen", "run")]

    # Nur lesende git-Kommandos — abschliessend aufgezaehlt, kein beliebiges
    # Kommando, kein Netz. Die ersten drei protokollieren den Systemstand
    # (P-K1, P9), die uebrigen belegen den Kernstand fuer A-K2 (Entscheid des
    # Maintainers 2026-10-01). Was nach dem Kommando kommt, sind Daten:
    # _git_lesen weist alles ab, was mit einem Strich beginnt.
    from rechner_pipeline.gates import _provenienz

    assert _provenienz.LESENDE_KOMMANDOS == (
        ("rev-parse", "HEAD"),
        ("rev-parse", "--abbrev-ref", "HEAD"),
        ("status", "--porcelain"),
        ("status", "--porcelain", "--untracked-files=all", "--"),
        ("rev-parse", "--verify", "--quiet"),
        ("merge-base",),
        ("diff", "--numstat", "--no-renames"),
        ("log", "--no-renames", "--name-only", "--format=%x1e%H%x1f%cs%x1f%s"),
        ("ls-tree", "-r", "--name-only"),
        ("show",),
    )
    # Jeder Aufruf der Stelle nennt eine dieser Konstanten, nie ein Literal.
    aufrufe = [
        ast.unparse(knoten.args[1])
        for knoten in ast.walk(baum)
        if isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Name)
        and knoten.func.id == "_git_lesen"
    ]
    namen = {name for name, wert in vars(_provenienz).items()
             if isinstance(wert, tuple) and wert in _provenienz.LESENDE_KOMMANDOS}
    assert aufrufe and set(aufrufe) <= namen, aufrufe
    with pytest.raises(_provenienz.GitAngabeFehler):
        _provenienz._git_lesen(Path("."), ("push",))
    with pytest.raises(_provenienz.GitAngabeFehler):
        _provenienz._git_lesen(Path("."), _provenienz.GIT_DIFFSTAT, "--output=/tmp/x")

    # Kein Prozessstart am subprocess-Waechter vorbei (os.system & Co.):
    ueber_os = {
        name: starts for name, baum in baeume.items()
        if (starts := _os_prozessstarts(baum))
    }
    assert ueber_os == {}

    # Die oeffentliche Zusage muss die Ausnahme BENENNEN, statt sie zu
    # verschweigen: ein grep auf "subprocess" darf ONBOARDING.md und
    # src/ nicht gegeneinander stellen.
    onboarding = (
        Path(__file__).resolve().parents[1] / "ONBOARDING.md"
    ).read_text(encoding="utf-8")
    assert "no subprocess" in onboarding
    assert "gates/_provenienz._git_lesen" in onboarding
    assert "exactly ONE subprocess exception" in onboarding
    assert (
        "test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt"
        in onboarding
    )


def test_entscheide_alle_vorlaeufigen_nach_quelle(fall_mit_konflikt, capsys):
    from rechner_pipeline.ontologie.entscheide import main as entscheide

    f, *_ = fall_mit_konflikt
    rc = entscheide([
        "--fall", str(f), *entscheide_args(f), "--alle-vorlaeufigen",
        "--quelle", "rechner.xlsm", "--entscheider", "maintainer",
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


# --------------------------------------------------------------------------- #
# RC07 (Angriffsrunde C): ein Prozessende hinterlaesst einen Rest, keinen Beleg
# --------------------------------------------------------------------------- #

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Kindprozess: faehrt gate_entscheid unter run_command und beendet sich an
#: der benannten Stelle hart (os._exit — kein finally, kein atexit), wie
#: SIGKILL oder ein Stromausfall. 'link' = nach dem Einhaengen des Snapshots,
#: vor dem Loeschen der Tempdatei; 'ledger' = beim Ersetzen des End-Ledgers
#: (das zweite os.replace auf das Ledger dieses Kommandos).
_KIND = '''
import os, sys
from pathlib import Path

stelle = sys.argv[1]
zaehler = [0]
_unlink, _replace = Path.unlink, os.replace


def unlink(self, *a, **k):
    if stelle == "link" and self.name.startswith(".A-Q1-") and self.name.endswith(".tmp"):
        os._exit(137)
    return _unlink(self, *a, **k)


def replace(quelle, ziel, *a, **k):
    if stelle == "ledger" and Path(ziel).name == "gate_entscheid_aq1.gate.json":
        zaehler[0] += 1
        if zaehler[0] == 2:
            os._exit(137)
    return _replace(quelle, ziel, *a, **k)


Path.unlink, os.replace = unlink, replace
from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates._common import run_command
sys.exit(run_command(gate_entscheid.main, sys.argv[2:]))
'''


def _ablehnung(fall: Path) -> list[str]:
    return ["--fall", str(fall), *linie_args(fall), "--gate", "A-Q1", "--entscheid", "abgelehnt",
            "--rolle", VA, "--entscheider", "maintainer",
            "--begruendung", "Zins offen", "--repo-root", str(REPO_ROOT)]


def _hartes_prozessende(tmp_path: Path, fall: Path, stelle: str) -> int:
    import os
    import subprocess
    import sys

    kind = tmp_path / "kind.py"
    kind.write_text(_KIND, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)
    lauf = subprocess.run([sys.executable, str(kind), stelle, *_ablehnung(fall)],
                          cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    return lauf.returncode


@pytest.mark.parametrize("stelle", ["link", "ledger", "keine"])
def test_die_wiederholung_nach_hartem_prozessende_meldet_bereits_vorhanden(
        fall_mit_konflikt, tmp_path, stelle):
    """Idempotenzvertrag des Gates: derselbe Entscheid auf demselben Stand
    wird gemeldet, nicht dupliziert. Ein Prozessende zwischen os.link und
    dem Loeschen der Tempdatei (Hardlink-Zwilling des Snapshots) oder beim
    Ersetzen des End-Ledgers liess einen Punktnamen-Rest liegen, den
    _artefakt_hashes als Artefakt aufnahm: ein ZWEITER Snapshot, der den
    Rest als entscheidungsrelevant nannte — und jeder weitere Snapshot des
    Falls trug ihn mit. Positivkontrolle ('keine'): dasselbe ohne
    Prozessende — kein Rest, ein Snapshot, bereits_vorhanden.
    Mutationsprobe: _artefakt_hashes nimmt Punktreste wieder auf -> rot."""
    from rechner_pipeline.gates.gate_entscheid import main

    f, *_ = fall_mit_konflikt
    assert _hartes_prozessende(tmp_path, f, stelle) == (0 if stelle == "keine" else 137)
    reste = sorted(p.name for p in f.rglob(".*.tmp"))
    assert bool(reste) == (stelle != "keine"), (
        "Voraussetzung: das Prozessende hat einen Rest hinterlassen (Kontrolle: keinen)")
    result = main(_ablehnung(f))
    assert result.exit_code == 0, result.errors
    assert result.summary.get("bereits_vorhanden") is True, result.summary
    assert len(list((f / "entscheide").glob("A-Q1-*.json"))) == 1
    for snapshot in (f / "entscheide").glob("A-Q1-*.json"):
        genannt = json.loads(snapshot.read_text(encoding="utf-8"))["artefakt_hashes"]
        assert [k for k in genannt if Path(k).name.startswith(".")] == []
    # Nach der Wiederholung liegt nirgends im Fall ein Rest (RC07, Nachbesserung):
    # weder der Hardlink-Zwilling in entscheide/ noch die Ledger-Tempdatei.
    assert sorted(p.name for p in f.rglob(".*.tmp")) == []


@pytest.mark.parametrize("pfad", ["bereits_vorhanden", "neuer_snapshot"])
def test_ein_liegengebliebener_rest_wird_vom_naechsten_lauf_des_gates_entfernt(
        fall_mit_konflikt, pfad):
    """Ein Rest ist kein Beleg — und er bleibt nicht fuer immer liegen
    (entscheide/ darf niemand von Hand bereinigen). Der ECHTE Ablauf von
    gate_entscheid raeumt zu Beginn die Reste seiner Ziele weg — die
    Snapshots dieses Gates in entscheide/ und sein Ledger im eigenen
    Verzeichnis —, auch im Pfad 'bereits_vorhanden', der gar nichts
    schreibt (dort greift kein Schreiber-Aufraeumen). Fremde Punktdateien
    und die Reste anderer Gates bleiben. Der Test geht durch main() statt
    durch den Schreiber (blinde Bauform 'Test baut seine Eingaben selbst');
    die Reste eines echten harten Prozessendes deckt
    test_die_wiederholung_nach_hartem_prozessende..., dieser hier ergaenzt
    Kontrollnamen (fremdes Gate, fremde Punktdatei) und den Pfad 'neuer
    Snapshot'.
    Mutationsprobe: das Aufraeumen am Laufanfang entfernen -> rot
    (bereits_vorhanden); das Aufraeumen in write_gate_ledger entfernen ->
    rot (beide)."""
    from rechner_pipeline.gates.gate_entscheid import main

    f, *_ = fall_mit_konflikt
    if pfad == "bereits_vorhanden":
        assert main(_ablehnung(f)).exit_code == 0
    entscheide = f / "entscheide"
    diagnostik = f / "abgeleitet" / "diagnostics"
    entscheide.mkdir(exist_ok=True)
    diagnostik.mkdir(parents=True, exist_ok=True)
    eigene = [
        entscheide / ".A-Q1-abc.json.0123456789abcdef.tmp",
        diagnostik / ".gate_entscheid_aq1.gate.json.0123456789abcdef.tmp",
    ]
    fremde = [
        entscheide / ".A-Q2-abc.json.0123456789abcdef.tmp",
        entscheide / ".fremd.tmp",
        diagnostik / ".gate_entscheid_aq2.gate.json.0123456789abcdef.tmp",
    ]
    for p in eigene + fremde:
        p.write_bytes(b"halb")
    result = main(_ablehnung(f))
    assert result.exit_code == 0, result.errors
    assert bool(result.summary.get("bereits_vorhanden")) is (pfad == "bereits_vorhanden")
    assert [p.name for p in eigene if p.exists()] == []
    assert all(p.exists() for p in fremde)


def test_schreibe_exklusiv_raeumt_die_reste_seines_ziels(tmp_path):
    """Einheitstest der Schreiber-Ebene (den Ablauf deckt der Test davor):
    Reste dieses Ziels gehen, fremde Punktdateien und Reste anderer Ziele
    bleiben — auch beim Fehlschlag 'Ziel existiert'. Mutationsprobe: das
    Aufraeumen in schreibe_exklusiv entfernen -> rot."""
    from rechner_pipeline.gates import _common

    ziel = tmp_path / "A-Q1-abc.json"
    rest = tmp_path / ".A-Q1-abc.json.0123456789abcdef.tmp"
    anderes_ziel = tmp_path / ".A-Q1-xyz.json.0123456789abcdef.tmp"
    fremd = tmp_path / ".gitkeep"
    for p in (rest, anderes_ziel, fremd):
        p.write_bytes(b"halb")
    _common.schreibe_exklusiv(ziel, b"{}\n")
    assert ziel.read_bytes() == b"{}\n"
    assert not rest.exists()
    assert anderes_ziel.exists() and fremd.exists()
    zwilling = tmp_path / ".A-Q1-abc.json.fedcba9876543210.tmp"
    zwilling.write_bytes(b"{}\n")
    with pytest.raises(FileExistsError):
        _common.schreibe_exklusiv(ziel, b"[]\n")
    assert not zwilling.exists() and ziel.read_bytes() == b"{}\n"
