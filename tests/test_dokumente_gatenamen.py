"""Jedes Gate, das ein Agenten- oder Team-Dokument nennt, gibt es.

Pruefrunde I (I17): Agentendateien ordneten eine Kern-Aenderung dem Gate
A-O1 zu (richtig: A-K2, ``mensch/rechenkern``; A-O1 ist der T-Box-Stand,
``mensch/architektur``), README und ONBOARDING nannten das entfallene Gate
A-K1. Ob eine Zuordnung Gegenstand -> Gate -> Rolle stimmt, ist Sprache und
gehoert nicht in einen Wortlisten-Test; mechanisch pruefbar ist nur: Jeder
Gate-Name der Form ``A-<Buchstabe><Ziffer>`` in diesen Dokumenten ist ein
zeichenbares Gate (``models.zeichnung.GUELTIGE_GATES``) oder die
Ordnungsaenderung ``A-Z1``. Ausnahmen sind historische Nennungen, die
ausdruecklich als entfallen gekennzeichnet sind — benannt, mit ``==``
gezaehlt.

Knoten: system/skills
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

REPO = Path(__file__).resolve().parents[1]
GATE_NAME = re.compile(r"\bA-[A-Z][0-9]+\b")
ORDNUNGSAENDERUNG = "A-Z1"
#: Die Dokumente, in die der Ablauf eines Falls und die Gate-Tabelle aus dem
#: README gezogen sind (ADR-027) — sie nennen Gates wie zuvor das README.
ARCHITEKTUR_DOKUMENTE = (
    "docs/architektur/ablauf-eines-falls.md",
    "docs/architektur/gate-vertrag-und-versionen.md",
)


def _dokumente(repo: Path) -> list:
    """Die Dokumente, nach denen Agenten und Team arbeiten."""
    dokumente = [repo / n for n in ("README.md", "ONBOARDING.md", "AGENTS.md",
                                    *ARCHITEKTUR_DOKUMENTE)]
    for baum in (".claude", ".agents"):
        dokumente += sorted((repo / baum / "agents").glob("*.md"))
        dokumente += sorted((repo / baum / "skills").glob("*/SKILL.md"))
    return [d for d in dokumente if d.is_file()]


def _unbekannte_gates(repo: Path) -> Counter:
    """(Dokument, Gate) -> Anzahl der Zeilen, die ein Gate nennen, das es
    nicht gibt; je Zeile mit dem Kennzeichen, ob sie es als entfallen nennt."""
    bekannt = set(GUELTIGE_GATES) | {ORDNUNGSAENDERUNG}
    funde: Counter = Counter()
    for dok in _dokumente(repo):
        for zeile in dok.read_text(encoding="utf-8").splitlines():
            for gate in GATE_NAME.findall(zeile):
                if gate not in bekannt:
                    funde[(str(dok.relative_to(repo)), gate, "entfallen" in zeile)] += 1
    return funde


#: Historische Nennungen, ausdruecklich als entfallen gekennzeichnet (in
#: derselben Zeile steht "entfallen"). ``==``: Eine weitere Nennung eines
#: Gates, das es nicht gibt, ist rot — auch eine historische, bis sie hier
#: steht.
HISTORISCH_ENTFALLEN = {
    # P9-Versionsgeschichte, Version 1.0.0: der Beleg der T-Box-Aenderung hiess
    # damals A-K1 (ADR-012: heute A-O1).
    ("docs/architektur/gate-vertrag-und-versionen.md", "A-K1", True): 1,
}


def test_jedes_genannte_gate_gibt_es():
    funde = _unbekannte_gates(REPO)
    assert funde == Counter(HISTORISCH_ENTFALLEN), funde
    assert all(entfallen for (_, _, entfallen) in HISTORISCH_ENTFALLEN)
    # Die Menge der Dokumente ist nicht leer und deckt beide Baeume.
    namen = {str(d.relative_to(REPO)) for d in _dokumente(REPO)}
    assert {"README.md", "ONBOARDING.md", "AGENTS.md", *ARCHITEKTUR_DOKUMENTE,
            ".claude/agents/rechenkern.md", ".agents/agents/rechenkern.md"} <= namen


def test_positivkontrolle(tmp_path):
    """Der Test sieht ein entfallenes Gate, unterscheidet die gekennzeichnete
    Nennung und laesst gueltige Gates und A-Z1 durch."""
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / "README.md").write_text(
        "A-K1 verlangt den Beleg\nA-K1 ist entfallen\nA-O1, A-K2, A-Z1, A-B3\n",
        encoding="utf-8")
    (tmp_path / ".claude" / "agents" / "x.md").write_text("unter A-K9\n", encoding="utf-8")
    assert _unbekannte_gates(tmp_path) == Counter({
        ("README.md", "A-K1", False): 1, ("README.md", "A-K1", True): 1,
        (".claude/agents/x.md", "A-K9", False): 1})
