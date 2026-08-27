"""Architektur-Werkzeuge: Code-Karte-Regeln, Knoten-Hierarchie, Impact.

Verankert die 1M-LOC-Mechanik: die Schichtenkarte ist nachrechenbar
(ADR-004-Regel inklusive), Knoten-Wurzeln sind validiert, jede
Testdatei ist an Knoten gebunden, und der Impact einer Aenderung ist
BERECHNET — selektiv bei sauberer Annotation, konservativ (volle
Suite) bei jeder Unsicherheit.

Knoten: system/architektur
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.ontologie.code_index import (
    baue_index,
    baue_test_bindung,
    drift_report,
    erlaubte_wurzeln,
)
from rechner_pipeline.ontologie.code_karte import baue_karte, validate
from rechner_pipeline.ontologie.impact import (
    berechne_impact,
    import_kanten_je_testmodul,
    lade_faelle_generationen,
    ladende_tests,
    normalisiere,
    verwandt,
)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"
TESTS = REPO / "tests"


# --------------------------------------------------------------------------- #
# Code-Karte: Schicht-Regeln am echten Repo und Mutations-Faenge
# --------------------------------------------------------------------------- #


def test_karte_des_repos_haelt_die_schichtregeln():
    karte = baue_karte(SRC)
    assert validate(karte) == []
    # ADR-004 explizit: kein Zielkern-Modul importiert den Zweitkern.
    zweitkern_kanten = [
        (k["von"], k["nach"]) for k in karte["kanten"]
        if k["nach"].startswith("rechner_pipeline/kommutationskern/")
        and not k["von"].startswith("rechner_pipeline/kommutationskern/")
    ]
    assert all(von.startswith("rechner_pipeline/qa/")
               for von, _ in zweitkern_kanten), zweitkern_kanten
    assert zweitkern_kanten, "Kreuz-Check-Kante qa -> Zweitkern fehlt"


def test_karte_ist_deterministisch():
    a = json.dumps(baue_karte(SRC), sort_keys=True)
    b = json.dumps(baue_karte(SRC), sort_keys=True)
    assert a == b


def _schreibe(pfad: Path, text: str) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(text, encoding="utf-8")


def _simuliere_case_insensitives_is_file(
    monkeypatch: pytest.MonkeyPatch, wurzel: Path
) -> None:
    """Nur ``is_file`` wie ein case-insensitives Dateisystem behandeln.

    Damit reproduzieren die Regressionen den macOS-Befund auch auf Linux.
    Die echten Verzeichniseintraege behalten bewusst ihre Schreibweise.
    """
    original = Path.is_file

    def case_insensitives_is_file(pfad: Path) -> bool:
        if original(pfad):
            return True
        try:
            teile = pfad.relative_to(wurzel).parts
        except ValueError:
            return False
        aktuell = wurzel
        for teil in teile:
            try:
                aktuell = next(
                    eintrag for eintrag in aktuell.iterdir()
                    if eintrag.name.casefold() == teil.casefold()
                )
            except (OSError, StopIteration):
                return False
        return original(aktuell)

    monkeypatch.setattr(Path, "is_file", case_insensitives_is_file)


def test_modulpfad_verlangt_exakte_schreibung_portabel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Der macOS-Finderfolg fuer falsch geschriebene Namen zaehlt nicht."""
    from rechner_pipeline.ontologie.code_karte import _modulpfad

    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "rechenkern.py", "class Rechenkern:\n    pass\n")
    _simuliere_case_insensitives_is_file(monkeypatch, tmp_path)

    assert _modulpfad("rechner_pipeline.kern.rechenkern", src) == (
        "rechner_pipeline/kern/rechenkern.py"
    )
    assert _modulpfad("rechner_pipeline.kern.Rechenkern", src) is None
    assert _modulpfad("rechner_pipeline.Kern.rechenkern", src) is None


def test_namenskollisionen_erzeugen_keine_phantomkanten_und_rendern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Rechenkern/rechenkern und ABox/abox bleiben Symbol/Modul-Paare."""
    from rechner_pipeline.ontologie.landkarte import als_mermaid, graph

    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "__init__.py", "Rechenkern = object\n")
    _schreibe(src / "kern" / "rechenkern.py", "Rechenkern = object\n")
    _schreibe(src / "ontologie" / "__init__.py", "ABox = object\n")
    _schreibe(src / "ontologie" / "abox.py", "ABox = object\n")
    _schreibe(
        src / "gates" / "nutzer.py",
        "from rechner_pipeline.kern import Rechenkern, rechenkern\n"
        "from rechner_pipeline.ontologie import ABox, abox\n",
    )
    _simuliere_case_insensitives_is_file(monkeypatch, tmp_path)

    karte = baue_karte(src)
    module = set(karte["module"])
    assert all(kante["nach"] in module for kante in karte["kanten"])
    assert not any(
        kante["nach"].endswith(("/Rechenkern.py", "/ABox.py"))
        for kante in karte["kanten"]
    )
    kanten = {
        (kante["von"], kante["nach"]): kante["symbole"]
        for kante in karte["kanten"]
    }
    nutzer = "rechner_pipeline/gates/nutzer.py"
    assert kanten[(nutzer, "rechner_pipeline/kern/__init__.py")] == [
        "Rechenkern"
    ]
    assert kanten[(nutzer, "rechner_pipeline/kern/rechenkern.py")] == []
    assert kanten[(nutzer, "rechner_pipeline/ontologie/__init__.py")] == [
        "ABox"
    ]
    assert kanten[(nutzer, "rechner_pipeline/ontologie/abox.py")] == []

    knoten, graph_kanten, titel = graph(karte, umfang="schichten")
    gerendert = als_mermaid(knoten, graph_kanten, titel)
    assert gerendert.startswith("%% Schichten")
    assert "flowchart TD" in gerendert


def test_karte_faengt_zweitkern_import_im_kern(tmp_path: Path):
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "boese.py",
              "from rechner_pipeline.kommutationskern.kommutation import fuer\n")
    _schreibe(src / "kommutationskern" / "kommutation.py", "fuer = None\n")
    befunde = validate(baue_karte(src))
    assert any("ADR-004" in b for b in befunde)
    assert any("darf nicht aus 'kommutationskern'" in b for b in befunde)


def test_karte_faengt_sdk_import(tmp_path: Path):
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "m.py", "import openai\n")
    assert any("SDK-Import 'openai'" in b for b in validate(baue_karte(src)))


def test_karte_faengt_unbekannte_schicht(tmp_path: Path):
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "neuland" / "m.py",
              "from rechner_pipeline.kern.tafeln import basis\n")
    _schreibe(src / "kern" / "tafeln.py", "basis = None\n")
    assert any("ohne Regel-Eintrag" in b for b in validate(baue_karte(src)))


# --------------------------------------------------------------------------- #
# Index: Wurzel-Validierung und Test-Bindungs-Pflicht
# --------------------------------------------------------------------------- #


def test_wurzeln_kommen_aus_tbox_produkten_und_system():
    wurzeln = erlaubte_wurzeln()
    assert {"klv", "bu", "system"} <= set(wurzeln)


def test_index_faengt_unbekannte_wurzel(tmp_path: Path):
    _schreibe(tmp_path / "paket" / "m.py",
              '"""M.\n\nKnoten: klx/tg2015\n"""\n')
    index = baue_index(tmp_path / "paket")
    befunde = drift_report(index, [], wurzeln=erlaubte_wurzeln())
    assert any("unbekannte Wurzel 'klx'" in b for b in befunde)
    # ... eine bekannte Wurzel mit Generations-Ebene ist dagegen frei:
    _schreibe(tmp_path / "paket" / "m.py",
              '"""M.\n\nKnoten: klv/tg2015\n"""\n')
    index = baue_index(tmp_path / "paket")
    assert drift_report(index, [], wurzeln=erlaubte_wurzeln()) == []


def test_testmodule_ohne_bindung_sind_drift(tmp_path: Path):
    tests = tmp_path / "tests"
    _schreibe(tests / "test_ungebunden.py", "def test_x():\n    pass\n")
    bindung = baue_test_bindung(tests)
    befunde = drift_report({"knoten": {}}, [], test_bindung=bindung)
    assert any("test_ungebunden.py: keine Knoten-Bindung" in b
               for b in befunde)
    _schreibe(tests / "test_ungebunden.py",
              '"""Knoten: klv\n"""\n\ndef test_x():\n    pass\n')
    bindung = baue_test_bindung(tests)
    assert drift_report({"knoten": {}}, [], test_bindung=bindung) == []


def test_repo_index_ist_drift_frei_mit_test_bindung():
    index = baue_index(SRC)
    bindung = baue_test_bindung(TESTS)
    assert drift_report(
        index, ["klv"], wurzeln=erlaubte_wurzeln(), test_bindung=bindung
    ) == []
    # Jede Testdatei traegt ihre Bindung (Grundlage der Selektion):
    assert bindung["ohne_bindung"] == []


# --------------------------------------------------------------------------- #
# Impact: Lineage-Selektion, Fallbacks, Fail-safe
# --------------------------------------------------------------------------- #


def test_lineage_verwandtschaft():
    assert verwandt("klv", "klv/tg2015")
    assert verwandt("klv/tg2015", "klv")
    assert not verwandt("klv/tg2012", "klv/tg2015")   # Geschwister
    assert not verwandt("klv", "bu")                  # fremde Familie
    assert not verwandt("klv", "klv2")                # kein Praefix-Treffer


SYNTH_INDEX = {"module": {
    "rechner_pipeline/kern/basis.py": ["klv", "bu"],
    "rechner_pipeline/daten/tg2015.py": ["klv/tg2015"],
}}
SYNTH_KARTE = {"module": {
    "rechner_pipeline/kern/basis.py": {"schicht": "kern"},
    "rechner_pipeline/daten/tg2015.py": {"schicht": "daten"},
    "rechner_pipeline/kern/helfer.py": {"schicht": "kern"},
}, "kanten": [
    {"von": "rechner_pipeline/kern/basis.py",
     "nach": "rechner_pipeline/kern/helfer.py", "symbole": []},
]}
SYNTH_TESTS = {
    "test_klv.py": ["klv"],
    "test_tg2012.py": ["klv/tg2012"],
    "test_tg2015.py": ["klv/tg2015"],
    "test_bu.py": ["bu"],
}
#: Direkt importierte Module je Test — ohne sie greift die erzwungene
#: Ladedeckung (kein selektierter Test laedt das geaenderte Modul).
SYNTH_IMPORTS = {
    "test_klv.py": ["rechner_pipeline/kern/basis.py"],
    "test_tg2012.py": [],
    "test_tg2015.py": ["rechner_pipeline/daten/tg2015.py"],
    "test_bu.py": ["rechner_pipeline/kern/basis.py"],
}


def test_impact_generation_trifft_keine_geschwister():
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/daten/tg2015.py"],
        SYNTH_INDEX, SYNTH_KARTE, SYNTH_TESTS, None, SYNTH_IMPORTS,
    )
    assert ergebnis["knoten"] == ["klv/tg2015"]
    # Familie (Vorfahr) und dieselbe Generation laufen — Geschwister
    # (tg2012) und fremde Familien (bu) NICHT:
    assert ergebnis["tests"] == ["test_klv.py", "test_tg2015.py"]
    assert ergebnis["konservativ"] == []


def test_impact_unannotiertes_modul_erbt_importeure():
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/helfer.py"],
        SYNTH_INDEX, SYNTH_KARTE, SYNTH_TESTS, None, SYNTH_IMPORTS,
    )
    # basis.py (klv, bu) importiert helfer.py -> Impact erbt klv+bu:
    assert ergebnis["knoten"] == ["bu", "klv"]
    assert ergebnis["tests"] == [
        "test_bu.py", "test_klv.py", "test_tg2012.py", "test_tg2015.py"]
    assert any("geerbt" in h for h in ergebnis["hinweise"])
    assert ergebnis["konservativ"] == []


def test_impact_ohne_zuordnung_ist_konservativ():
    karte = {"module": {
        "rechner_pipeline/insel.py": {"schicht": "insel"}}, "kanten": []}
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/insel.py"], {"module": {}}, karte,
        SYNTH_TESTS, None, SYNTH_IMPORTS,
    )
    assert ergebnis["konservativ"]
    assert ergebnis["tests"] == sorted(SYNTH_TESTS)   # volle Suite


def test_impact_globale_datei_ist_konservativ():
    ergebnis = berechne_impact(
        ["pyproject.toml"], SYNTH_INDEX, SYNTH_KARTE, SYNTH_TESTS,
    )
    assert ergebnis["konservativ"]
    assert ergebnis["tests"] == sorted(SYNTH_TESTS)


def test_impact_am_repo_bu_aenderung_laesst_klv_tests_liegen():
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/produkte/bu.py"], *_repo_args())
    assert ergebnis["knoten"] == ["bu"]
    assert "test_kern_bu.py" in ergebnis["tests"]
    assert "test_bestand_bu.py" in ergebnis["tests"]
    assert "test_kern.py" not in ergebnis["tests"]          # reine KLV
    assert "test_tafel_import.py" not in ergebnis["tests"]  # klv/tg2015
    assert ergebnis["konservativ"] == []


def test_impact_am_repo_tafeldaten_binden_an_tafelschicht():
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/tafeln.xml"], *_repo_args())
    assert ergebnis["knoten"] == ["bu", "klv"]
    assert any("Daten-Bindung" in h for h in ergebnis["hinweise"])


def test_impact_skill_aenderung_trifft_workflow_doku_test():
    ergebnis = berechne_impact(
        [".claude/skills/entwickle-im-zielsystem/SKILL.md"], *_repo_args())
    assert ergebnis["knoten"] == ["system/skills"]
    assert ergebnis["tests"] == ["test_agent_workflow_docs.py"]


def test_impact_tarifplan_ist_test_tragend():
    """Die Tarifplaene tragen die Generationen-Tabelle, die
    test_bestand_config zeichengenau gegen die Config prueft — eine
    Aenderung dort darf nicht als reine Doku durchgehen und null Tests
    auswaehlen."""
    ergebnis = berechne_impact(["docs/tarifplaene/bu.md"], *_repo_args())
    assert ergebnis["knoten"] == ["bu"]
    assert "test_bestand_config.py" in ergebnis["tests"]
    assert not any("kein Code-/Vertrags-Impact" in h
                   for h in ergebnis["hinweise"])

    klv = berechne_impact(["docs/tarifplaene/klv.md"], *_repo_args())
    assert klv["knoten"] == ["klv"]
    assert "test_bestand_config.py" in klv["tests"]


def test_impact_bindet_tarifplaene_ueber_den_dateinamen():
    """Die Bindung ist generisch: Ein drittes Produkt bringt seinen
    Tarifplan nicht stillschweigend ausserhalb der Testselektion mit
    (Review-Befund — vorher waren klv.md und bu.md einzeln
    aufgezaehlt)."""
    neu = berechne_impact(["docs/tarifplaene/rlv.md"], *_repo_args())
    assert neu["knoten"] == ["rlv"]
    assert not any("kein Code-/Vertrags-Impact" in h
                   for h in neu["hinweise"])
    # Der README des Ordners ist kein Produkt:
    readme = berechne_impact(
        ["docs/tarifplaene/README.md"], *_repo_args())
    assert readme["knoten"] == []


def test_impact_grundsatzdokumentation_ist_konservativ():
    """Die Mathematik, der die Umsetzung folgt, ist nie auf einen
    Knoten begrenzt."""
    ergebnis = berechne_impact(
        ["docs/mathematik/grundsatzdokumentation.md"], *_repo_args())
    assert ergebnis["konservativ"]


def test_impact_geloeschtes_modul_ist_konservativ():
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/geloescht.py"],
        SYNTH_INDEX, SYNTH_KARTE, SYNTH_TESTS, None, SYNTH_IMPORTS,
    )
    assert any("geloeschte oder unbekannte" in k
               for k in ergebnis["konservativ"])
    assert ergebnis["tests"] == sorted(SYNTH_TESTS)


def test_impact_faelle_hinweis_folgt_der_lineage(tmp_path: Path):
    abox = tmp_path / "fall-x" / "abgeleitet" / "abox"
    abox.mkdir(parents=True)
    (abox / "abox.json").write_text(json.dumps({
        "generationen": [{"id": "klv/tg2012"}, {"id": "klv/tg2015"}],
    }), encoding="utf-8")
    generationen = lade_faelle_generationen(tmp_path)
    assert generationen == {"fall-x": ["klv/tg2012", "klv/tg2015"]}
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/daten/tg2015.py"],
        SYNTH_INDEX, SYNTH_KARTE, SYNTH_TESTS, generationen, SYNTH_IMPORTS,
    )
    # Nur die verwandte Generation braucht ihr O3 erneut — nicht das
    # Geschwister:
    assert [f["generation"] for f in ergebnis["faelle"]] == ["klv/tg2015"]
    # fail-soft ohne Fall-Verzeichnis:
    assert lade_faelle_generationen(tmp_path / "fehlt") == {}


# --------------------------------------------------------------------------- #
# Regressionen aus dem adversarialen Review (2026-08-16)
# --------------------------------------------------------------------------- #


def _repo_args():
    return (
        baue_index(SRC), baue_karte(SRC),
        baue_test_bindung(TESTS)["bindung"], None,
        import_kanten_je_testmodul(TESTS, SRC), REPO,
    )


def test_pfadformen_liefern_dasselbe_ergebnis():
    """Review-Befund: './x', Windows-Trenner und absolute Pfade fielen
    still in den 'kein Impact'-Zweig — 0 Tests statt 5, ohne Warnung."""
    args = _repo_args()
    referenz = berechne_impact(
        ["src/rechner_pipeline/kern/produkte/bu.py"], *args)
    for form in (
        "./src/rechner_pipeline/kern/produkte/bu.py",
        "src\\rechner_pipeline\\kern\\produkte\\bu.py",
        str(REPO / "src/rechner_pipeline/kern/produkte/bu.py"),
        "  src/rechner_pipeline/kern/produkte/bu.py  ",
    ):
        ergebnis = berechne_impact([form], *args)
        assert ergebnis["tests"] == referenz["tests"], form
        assert ergebnis["konservativ"] == [], form
    # Die Referenz muss selektiv sein, sonst prueft der Vergleich nichts:
    assert 0 < len(referenz["tests"]) < len(baue_test_bindung(TESTS)["bindung"])


def test_fremder_absolutpfad_ist_konservativ():
    ergebnis = berechne_impact(["/anderswo/projekt/modul.py"], *_repo_args())
    assert any("nicht repo-relativ" in k for k in ergebnis["konservativ"])
    assert ergebnis["tests"] == sorted(baue_test_bindung(TESTS)["bindung"])


def test_normalisiere_grenzfaelle():
    assert normalisiere("./a/b.py", REPO) == "a/b.py"
    assert normalisiere("a\\b.py", REPO) == "a/b.py"
    assert normalisiere("   ", REPO) is None
    assert normalisiere("../ausserhalb.py", REPO) is None


def test_direkte_import_kante_faengt_fremde_knoten_linie():
    """Review-Befund (belegt): fall.py traegt system/fall, wird aber von
    klv-gebundenen Ontologie-Tests direkt importiert — die reine
    Lineage-Selektion liess sie liegen."""
    ergebnis = berechne_impact(["src/rechner_pipeline/fall.py"], *_repo_args())
    assert ergebnis["knoten"] == ["system/fall"]
    for name in ("test_kette_und_vorbedingungen.py",
                 "test_ontologie_befuellung.py", "test_fachspez_und_p9.py"):
        assert name in ergebnis["tests"], name
    assert any("Import-Kante selektiert" in h for h in ergebnis["hinweise"])
    # ... und die Praezision bleibt: kein Kern-/Bestandstest faellt an.
    assert "test_kern.py" not in ergebnis["tests"]


def test_import_kante_bleibt_nicht_transitiv():
    """Bewusste Grenze (ADR-005): transitive Schliessung ueber
    __init__-Re-Exports zieht jede Aenderung auf 'alles' — gemessen
    bu.py 5 -> 21 Tests. Der Showcase muss selektiv bleiben."""
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/produkte/bu.py"], *_repo_args())
    # Transitiv waeren es 21+ von 46; die Selektion bleibt eine Handvoll.
    assert len(ergebnis["tests"]) <= 10
    for rein_klv in ("test_bestand_ereignisse.py", "test_bestand_bewegung_klv.py",
                     "test_kern.py", "test_tafel_import.py"):
        assert rein_klv not in ergebnis["tests"], rein_klv


def test_konservativ_behaelt_direkt_geaenderte_testdatei():
    ergebnis = berechne_impact(
        ["pyproject.toml", "tests/test_ganz_neu.py"], *_repo_args())
    assert ergebnis["konservativ"]
    assert "test_ganz_neu.py" in ergebnis["tests"]


def test_artefakte_ohne_bindung_sind_konservativ():
    """Review-Befund: Fixtures und unbekannte src-Artefakte galten als
    'kein Impact' — eine geaenderte Anker-Fixture ergab 0 Tests."""
    for datei, muster in (
        ("tests/fixtures/kern_anker/anker_dav2008.json", "Test-Artefakt"),
        ("src/rechner_pipeline/quellen/neu.json", "ohne Daten-Bindung"),
        ("skripte/hilfs.py", "ausserhalb von src/ und tests/"),
    ):
        ergebnis = berechne_impact([datei], *_repo_args())
        assert any(muster in k for k in ergebnis["konservativ"]), datei
        assert ergebnis["tests"] == sorted(
            baue_test_bindung(TESTS)["bindung"]), datei


def test_skill_katalog_ist_an_system_skills_gebunden():
    """docs/architektur/skill-architektur.md ist test-tragend
    (test_agent_workflow_docs prueft den Katalog)."""
    ergebnis = berechne_impact(
        ["docs/architektur/skill-architektur.md"], *_repo_args())
    assert ergebnis["tests"] == ["test_agent_workflow_docs.py"]


def test_karte_faengt_dynamischen_import(tmp_path: Path):
    """Review-Befund: importlib/__import__ umging Schicht-Allowlist,
    ADR-004-Regel und SDK-Verbot vollstaendig."""
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "schmuggel.py",
              "import importlib\n"
              "m = importlib.import_module('rechner_pipeline."
              "kommutationskern.kommutation')\n"
              "s = __import__('openai')\n")
    _schreibe(src / "kommutationskern" / "kommutation.py", "fuer = None\n")
    befunde = validate(baue_karte(src))
    assert any("ADR-004" in b for b in befunde)
    assert any("SDK-Import 'openai'" in b for b in befunde)


def test_karte_meldet_unlesbaren_dynamischen_import(tmp_path: Path):
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "m.py",
              "import importlib\n"
              "def laden(name):\n"
              "    return importlib.import_module(name)\n")
    befunde = validate(baue_karte(src))
    assert any("dynamische(r) Import(e) mit berechnetem Namen" in b
               for b in befunde)


def test_sdk_verbot_greift_ueber_namensfamilien(tmp_path: Path):
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "kern" / "m.py",
              "import langchain_openai\n"
              "import langgraph_sdk\n"
              "from langchain_core.messages import X\n")
    befunde = validate(baue_karte(src))
    for name in ("langchain_openai", "langgraph_sdk", "langchain_core"):
        assert any(f"SDK-Import '{name}'" in b for b in befunde), name


def test_karte_faengt_neue_schicht_ohne_interne_kanten(tmp_path: Path):
    """Review-Befund: ein Paket ohne paketinterne Kanten war fuer die
    Regelpruefung unsichtbar."""
    src = tmp_path / "rechner_pipeline"
    _schreibe(src / "schatten" / "m.py", "import json\n")
    assert any("Schicht 'schatten' ohne Regel-Eintrag" in b
               for b in validate(baue_karte(src)))


def test_ladedeckung_wird_erzwungen():
    """Review-Befund (belegt an kern/model_point.py): die reine
    Knoten-Selektion konnte ein Modul auswaehlen, das KEIN selektierter
    Test laedt — dann bliebe schon ein Import-Bruch unsichtbar. Jetzt
    faellt dieser Fall konservativ auf die volle Suite."""
    karte = {"module": {
        "rechner_pipeline/einsam.py": {"schicht": "einsam"}}, "kanten": []}
    index = {"module": {"rechner_pipeline/einsam.py": ["bu"]}}
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/einsam.py"], index, karte,
        SYNTH_TESTS, None, SYNTH_IMPORTS,
    )
    assert any("kein selektierter Test laedt" in k
               for k in ergebnis["konservativ"])
    assert ergebnis["tests"] == sorted(SYNTH_TESTS)


def test_ladedeckung_haelt_fuer_jedes_modul_des_repos():
    """Die Garantie des Werkzeugs, am echten Repo nachgerechnet: fuer
    JEDES Modul enthaelt die Selektion mindestens einen Test, der es
    (transitiv) laedt — sonst waere die Auswahl konservativ."""
    args = _repo_args()
    karte = baue_karte(SRC)
    lader = ladende_tests(import_kanten_je_testmodul(TESTS, SRC),
                          karte["kanten"])
    ohne_deckung = []
    for modul in sorted(karte["module"]):
        if modul.endswith("__init__.py"):
            continue
        ergebnis = berechne_impact(["src/" + modul], *args)
        if ergebnis["konservativ"]:
            continue                       # volle Suite deckt ohnehin
        if not any(modul in lader.get(t, ()) for t in ergebnis["tests"]):
            ohne_deckung.append(modul)
    assert ohne_deckung == []


def test_weitere_lader_weisen_die_restluecke_aus():
    """Ehrlichkeit statt Stille: Tests, die ein geaendertes Modul laden,
    aber fachlich nicht betroffen sind, stehen im Ergebnis — ueber diese
    Kante faellt ein Verhaltens-Bruch erst in der vollen Suite auf."""
    ergebnis = berechne_impact(
        ["src/rechner_pipeline/kern/produkte/bu.py"], *_repo_args())
    assert ergebnis["konservativ"] == []
    assert "test_kern.py" in ergebnis["weitere_lader"]
    assert not set(ergebnis["tests"]) & set(ergebnis["weitere_lader"])


def test_schichtentabelle_des_skills_deckt_die_regelschichten():
    """Review-Befund: die Prosa-Schichtenkarte im Entwickler-Skill und
    die nachrechenbare Allowlist nannten verschiedene Schichtmengen."""
    from rechner_pipeline.ontologie.code_karte import SCHICHT_ERLAUBT

    text = (REPO / ".claude" / "skills" / "entwickle-im-zielsystem"
            / "SKILL.md").read_text(encoding="utf-8")
    fehlend = [
        s for s in SCHICHT_ERLAUBT
        if s != "__init__" and f"`{s}/`" not in text and f"`{s}.py`" not in text
    ]
    assert fehlend == []


# --------------------------------------------------------------------------- #
# Landkarte: der Generator der HTML-Sicht (ADR-005)
# --------------------------------------------------------------------------- #


def test_landkarte_ist_deterministisch(tmp_path: Path):
    """Gleicher Repo-Stand -> byte-identische Datei. Ohne das waere die
    Landkarte nicht diffbar und als Beleg wertlos."""
    from rechner_pipeline.ontologie.landkarte import main as landkarte

    a, b = tmp_path / "a.html", tmp_path / "b.html"
    for ziel in (a, b):
        assert landkarte(["--out", str(ziel), "--src", str(SRC),
                          "--tests", str(TESTS), "--faelle",
                          str(tmp_path / "keine")]) == 0
    assert a.read_bytes() == b.read_bytes()
    # ... und der Stand-Text ist der einzige bewusste Freiheitsgrad:
    c = tmp_path / "c.html"
    landkarte(["--out", str(c), "--src", str(SRC), "--tests", str(TESTS),
               "--faelle", str(tmp_path / "keine"), "--stand", "probe-sha"])
    assert c.read_bytes() != a.read_bytes()
    assert "probe-sha" in c.read_text(encoding="utf-8")


def test_landkarte_ist_selbsttragend(tmp_path: Path):
    """Keine externe Ressource: die Datei muss offline funktionieren
    (die Artifact-Umgebung blockt Fremdhosts ohnehin hart)."""
    import re

    from rechner_pipeline.ontologie.landkarte import main as landkarte

    ziel = tmp_path / "lk.html"
    landkarte(["--out", str(ziel), "--src", str(SRC), "--tests", str(TESTS),
               "--faelle", str(tmp_path / "keine")])
    text = ziel.read_text(encoding="utf-8")
    assert not re.search(r'(src|href)\s*=\s*["\']https?://', text)
    assert "<script src" not in text and "<link " not in text


def test_landkarte_traegt_die_echten_werkzeug_ergebnisse(tmp_path: Path):
    """Die Seite behauptet nichts Eigenes: ihre Zahlen sind die der
    Werkzeuge."""
    from rechner_pipeline.ontologie.landkarte import sammle

    daten = sammle(SRC, TESTS, tmp_path / "keine", repo_root=REPO)
    karte = baue_karte(SRC)
    assert daten["gesamt"]["module"] == len(karte["module"])
    assert daten["gesamt"]["kanten"] == len(karte["kanten"])
    assert daten["knoten"] == baue_index(SRC)["knoten"]
    assert daten["test_bindung"] == baue_test_bindung(TESTS)["bindung"]
    # Je Knoten ein Szenario plus der konservative Fall:
    titel = [s["titel"] for s in daten["szenarien"]]
    assert len(titel) == len(daten["knoten"]) + 1
    assert any("Fail-safe" in t for t in titel)
    # Das konservative Szenario zieht wirklich die volle Suite:
    fail_safe = [s for s in daten["szenarien"] if "Fail-safe" in s["titel"]][0]
    assert fail_safe["konservativ"]
    assert len(fail_safe["tests"]) == len(daten["test_bindung"])


def test_landkarte_szenario_ueberschreibbar(tmp_path: Path):
    from rechner_pipeline.ontologie.landkarte import sammle

    daten = sammle(SRC, TESTS, tmp_path / "keine",
                   ["src/rechner_pipeline/kern/produkte/bu.py"], REPO)
    [szenario] = daten["szenarien"]
    assert szenario["knoten"] == ["bu"]
    assert "test_kern_bu.py" in szenario["tests"]


def test_landkarte_meldet_fehlende_verzeichnisse(tmp_path: Path):
    from rechner_pipeline.ontologie.landkarte import main as landkarte

    assert landkarte(["--out", str(tmp_path / "x.html"),
                      "--src", str(tmp_path / "fehlt"),
                      "--tests", str(TESTS)]) == 2


def test_landkarte_vorlage_ist_teil_des_generators():
    """Die Vorlage liegt im Paket (package-data) und traegt den
    Platzhalter — sonst erzeugt der Generator eine leere Seite."""
    from rechner_pipeline.ontologie.landkarte import PLATZHALTER, VORLAGE

    assert VORLAGE.is_file()
    text = VORLAGE.read_text(encoding="utf-8")
    assert PLATZHALTER in text
    assert "<title>" in text


# --------------------------------------------------------------------------- #
# Graph-Export: das Zeichnen macht fremdes Werkzeug (Mermaid/DOT/GraphML)
# --------------------------------------------------------------------------- #


def _graph(umfang="schichten", auswahl=None):
    from rechner_pipeline.ontologie.landkarte import graph

    return graph(baue_karte(SRC), baue_index(SRC), umfang, auswahl)


def test_graph_ausschnitte_bleiben_zeichenbar():
    """Im Zielbild gibt es kein Bild 'der Codebasis'. Alle drei
    Ausschnitte wachsen mit der Struktur, nicht mit der Codemenge."""
    for umfang, auswahl in (("schichten", None), ("knoten", None),
                            ("modul", "kern"), ("modul", "bu")):
        knoten, kanten, titel = _graph(umfang, auswahl)
        assert 0 < len(knoten) <= 60, (umfang, auswahl, len(knoten))
        namen = {n for n, _ in knoten}
        for von, nach, _ in kanten:
            assert von in namen and nach in namen


def test_graph_verweigert_unlesbare_sichten():
    """Fail-fast statt Knaeuel: zu grosser Ausschnitt ist ein Fehler mit
    Ausweg in der Meldung."""
    from rechner_pipeline.ontologie.landkarte import graph

    with pytest.raises(ValueError, match="unlesbar"):
        graph(baue_karte(SRC), baue_index(SRC), "modul", "gates",
              max_knoten=5)
    with pytest.raises(ValueError, match="weder Knoten noch Schicht"):
        graph(baue_karte(SRC), baue_index(SRC), "modul", "gibtsnicht")


def test_knotensicht_erfindet_keine_familien_abhaengigkeit():
    """Ein Rueckgrat-Modul (Knoten 'klv, bu') macht KLV nicht von BU
    abhaengig — beide stehen darauf. Eine Kante entsteht nur bei einem
    echten Uebergang."""
    _, kanten, _ = _graph("knoten")
    paare = {(v, n) for v, n, _ in kanten}
    assert ("klv", "bu") not in paare
    assert ("bu", "klv") not in paare
    assert paare, "die Knotensicht sollte echte Uebergaenge zeigen"


def test_export_formate_sind_wohlgeformt_und_deterministisch():
    from xml.etree import ElementTree

    from rechner_pipeline.ontologie.landkarte import (
        als_dot, als_graphml, als_mermaid,
    )

    knoten, kanten, titel = _graph("modul", "kern")
    mermaid, dot, graphml = (f(knoten, kanten, titel)
                             for f in (als_mermaid, als_dot, als_graphml))
    # Deterministisch (gleiche Eingabe -> gleicher Text):
    assert als_mermaid(knoten, kanten, titel) == mermaid
    # Mermaid: Zeilenumbruch als <br/>, kein roher Umbruch im Label
    assert mermaid.startswith("%%") and "flowchart TD" in mermaid
    for zeile in mermaid.splitlines():
        assert zeile.count('"') % 2 == 0
    # DOT: geschlossene Klammer, ein Pfeil je Kante
    assert dot.rstrip().endswith("}") and dot.count("->") == len(kanten)
    # GraphML: wohlgeformtes XML mit passender Knoten-/Kantenzahl
    baum = ElementTree.fromstring(graphml)
    ns = "{http://graphml.graphdrawing.org/xmlns}"
    assert len(baum.findall(f".//{ns}node")) == len(knoten)
    assert len(baum.findall(f".//{ns}edge")) == len(kanten)


def test_landkarte_doku_ist_nicht_veraltet():
    """docs/architektur/landkarte.md traegt erzeugte Diagramme — diese
    Pruefung verhindert, dass die Seite etwas anderes behauptet als der
    Code sagt."""
    import re

    from rechner_pipeline.ontologie.landkarte import als_mermaid

    seite = (REPO / "docs" / "architektur" / "landkarte.md")
    bloecke = re.findall(r"```mermaid\n(.*?)```", seite.read_text("utf-8"),
                         re.DOTALL)
    erwartet = [
        als_mermaid(*_graph("schichten")),
        als_mermaid(*_graph("knoten")),
        als_mermaid(*_graph("modul", "kern")),
    ]
    assert len(bloecke) == len(erwartet), "Diagrammzahl weicht ab"
    for ist, soll in zip(bloecke, erwartet):
        assert ist.strip() == soll.strip(), (
            "landkarte.md ist veraltet — neu erzeugen mit "
            "'python -m rechner_pipeline.ontologie.landkarte --format "
            "mermaid ...'")


def test_module_ohne_knoten_sind_harter_drift(tmp_path: Path):
    """Beschluss 2026-08-18: kein Baustein ohne ontologischen Knoten.
    Ein unannotiertes Modul ist ein Befund, kein Bestandslisten-Eintrag —
    nur reine Paket-__init__ ohne Fachverhalten sind ausgenommen."""
    _schreibe(tmp_path / "paket" / "modul.py", "WERT = 1\n")
    _schreibe(tmp_path / "paket" / "__init__.py", "")
    index = baue_index(tmp_path / "paket")
    befunde = drift_report(index, [])
    assert any("modul.py: keine Knoten-Annotation" in b for b in befunde)
    assert not any("__init__.py" in b for b in befunde)
    # Annotiert -> kein Befund:
    _schreibe(tmp_path / "paket" / "modul.py",
              '"""M.\n\nKnoten: klv\n"""\nWERT = 1\n')
    assert drift_report(baue_index(tmp_path / "paket"), []) == []
