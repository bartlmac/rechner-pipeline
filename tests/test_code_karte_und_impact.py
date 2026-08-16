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
    assert len(referenz["tests"]) == 5


def test_fremder_absolutpfad_ist_konservativ():
    ergebnis = berechne_impact(["/anderswo/projekt/modul.py"], *_repo_args())
    assert any("nicht repo-relativ" in k for k in ergebnis["konservativ"])
    assert len(ergebnis["tests"]) == 46


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
    assert len(ergebnis["tests"]) == 5
    assert "test_bestand_ereignisse.py" not in ergebnis["tests"]


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
        assert len(ergebnis["tests"]) == 46, datei


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
    assert len(ergebnis["tests"]) == 5
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
