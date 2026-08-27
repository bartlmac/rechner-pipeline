"""Tarifplan-Struktur folgt der Code-Basis (Doku-Drift-Waechter).

Die Produktdokumentation hatte dieselbe Doppelpflege, die der Code
laengst vermeidet: Das gemeinsame Rueckgrat (Zustandsmodell,
Thiele-Rekursion, Rechnungsgrundlagen-Schicht, Numerik) stand wortgleich
in JEDEM Tarifplan. Seit dem Doku-Umbau steht es einmal in der
Grundsatzdokumentation; die Tarifplaene tragen die Ausgestaltung.

Diese Tests halten den Schnitt: Sie pruefen, dass es zu jedem
registrierten Produkt einen Tarifplan gibt und umgekehrt, dass alle
Tarifplaene dieselbe Gliederung haben, und dass kein Backbone-Thema in
einen Tarifplan zurueckwandert. Die Regel folgt der Knoten-Annotation:
Was ein Modul mit Knoten ``klv, bu`` beschreibt, gehoert ins zentrale
Dokument; was ein Modul mit genau einem Produktknoten beschreibt, in den
Tarifplan.

Knoten: klv, bu
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

import pytest

from rechner_pipeline.kern.produkte import PRODUKTE

REPO_ROOT = Path(__file__).resolve().parents[1]
TARIFPLAENE = REPO_ROOT / "docs" / "tarifplaene"
ZENTRAL = REPO_ROOT / "docs" / "fachkonzept" / "grundsatzdokumentation.md"

#: Themen des gemeinsamen Rueckgrats. Sie stehen im zentralen Dokument;
#: ein Tarifplan darf sie NENNEN und darauf verweisen, aber nicht
#: ausfuehren. Erkennungsmerkmal ist der Formelsatz bzw. die
#: Definitionsformulierung — der blosse Begriff ist erlaubt.
BACKBONE_AUSFUEHRUNGEN = {
    "Thiele-Rekursionsformel": r"V_j\(s\)\s*\\;=\\;",
    "Residuum-Regel als Definition": r"p_\{s\s*\\to\s*s\}",
    "affine Ordnungs-Transformation": r"a \+ b \\cdot",
    "Diskontfaktor-Definition": r"v\s*=\s*\\tfrac\{1\}\{1\+i\}",
}


def _tarifplaene() -> Dict[str, Path]:
    return {p.stem: p for p in sorted(TARIFPLAENE.glob("*.md"))
            if p.stem != "README"}


def _abschnitte(text: str) -> List[str]:
    return re.findall(r"^# (\d+) (.+)$", text, re.M)


def test_jedes_registrierte_produkt_hat_einen_tarifplan():
    """Code -> Doku: Ein Produkt ohne Tarifplan ist undokumentiert."""
    fehlend = sorted(set(PRODUKTE) - set(_tarifplaene()))
    assert not fehlend, (
        f"Produkte ohne Tarifplan: {fehlend} — je Produkt ein Dokument "
        f"docs/tarifplaene/<kennung>.md"
    )


def test_jeder_tarifplan_gehoert_zu_einem_registrierten_produkt():
    """Doku -> Code: Ein Tarifplan ohne Produkt beschreibt nichts."""
    fremd = sorted(set(_tarifplaene()) - set(PRODUKTE))
    assert not fremd, (
        f"Tarifplaene ohne registriertes Produkt: {fremd} "
        f"(registriert: {sorted(PRODUKTE)})"
    )


def test_alle_tarifplaene_haben_dieselbe_gliederung():
    """Die Gliederung ist fuer alle Produkte des Kerns dieselbe — das
    behaupten die Dokumente selbst, und ein neues Produkt soll sie
    uebernehmen statt eine eigene zu erfinden."""
    gliederungen = {
        name: _abschnitte(pfad.read_text(encoding="utf-8"))
        for name, pfad in _tarifplaene().items()
    }
    assert gliederungen, "keine Tarifplaene gefunden"
    referenz_name, referenz = sorted(gliederungen.items())[0]
    for name, gliederung in gliederungen.items():
        assert gliederung == referenz, (
            f"{name}.md weicht von {referenz_name}.md ab:\n"
            f"  {name}: {gliederung}\n  {referenz_name}: {referenz}"
        )
    # Luecken- und Reihenfolgetreue der Nummerierung:
    nummern = [int(n) for n, _ in referenz]
    assert nummern == list(range(1, len(nummern) + 1)), nummern


def test_kein_tarifplan_fuehrt_das_gemeinsame_rueckgrat_aus():
    """Der Kern der Entdopplung: Was fuer alle Produkte gilt, steht
    einmal im zentralen Dokument. Ein Tarifplan verweist darauf."""
    zentral = ZENTRAL.read_text(encoding="utf-8")
    for thema, muster in BACKBONE_AUSFUEHRUNGEN.items():
        assert re.search(muster, zentral), (
            f"{thema} steht nicht (mehr) in der Grundsatzdokumentation — "
            "dann ist der Waechter blind"
        )
    for name, pfad in _tarifplaene().items():
        text = pfad.read_text(encoding="utf-8")
        gefunden = [t for t, m in BACKBONE_AUSFUEHRUNGEN.items()
                    if re.search(m, text)]
        assert not gefunden, (
            f"{name}.md fuehrt Backbone-Themen aus: {gefunden} — sie "
            "gehoeren in docs/fachkonzept/grundsatzdokumentation.md, "
            "der Tarifplan verweist nur darauf"
        )


def test_jeder_tarifplan_verweist_auf_die_grundsatzdokumentation():
    """Der Verweis ersetzt die Wiederholung — fehlt er, ist die
    Bewertungsgleichung fuer den Leser des Tarifplans verschwunden."""
    for name, pfad in _tarifplaene().items():
        text = pfad.read_text(encoding="utf-8")
        assert "grundsatzdokumentation.md" in text, (
            f"{name}.md verweist nicht auf die Grundsatzdokumentation"
        )


def test_grundsatzdokumentation_deckt_die_pflichtinhalte_ab():
    """Fachkonzept 8.1 nennt die Pflichtinhalte. Was heute nicht
    gebaut ist, steht als benannter, leerer Abschnitt drin — aber es
    steht drin."""
    text = ZENTRAL.read_text(encoding="utf-8")
    for pflicht in (
        "Zustandsraum", "Notation", "Thiele", "Rechnungsgrundlagen",
        "Diskretisierung", "Rundung", "Korrekturschicht",
        "Abweichungsverzeichnis", "Versionierung",
    ):
        assert pflicht in text, f"Pflichtinhalt fehlt: {pflicht}"


@pytest.mark.parametrize("behauptung, datei", [
    ("spez/fachspez.py", "src/rechner_pipeline/spez/fachspez.py"),
    (".claude-Skill", ".claude/skills/dokumentiere-system/SKILL.md"),
    (".agents-Skill", ".agents/skills/dokumentiere-system/SKILL.md"),
])
def test_niemand_behauptet_eine_falsche_abschnittszahl(behauptung, datei):
    """Der Drift, der den Umbau ausgeloest hat: Drei Stellen sprachen von
    einer 12-Abschnitts-Gliederung, waehrend die Dokumente 13 Abschnitte
    trugen. Eine Zahl, die an mehreren Orten steht, driftet — hier wird
    sie gegen die Dokumente geprueft."""
    ist = len(_abschnitte(
        _tarifplaene()["klv"].read_text(encoding="utf-8")))
    text = (REPO_ROOT / datei).read_text(encoding="utf-8")
    falsch = [
        n for n in re.findall(r"(\d+)[- ]Abschnitt", text)
        if int(n) != ist
    ]
    assert not falsch, (
        f"{datei} behauptet {falsch} Abschnitte, die Tarifplaene haben "
        f"{ist} — eine der beiden Stellen ist veraltet"
    )
