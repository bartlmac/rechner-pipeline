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
#: ausfuehren.
#:
#: Erkannt wird die AUSFUEHRUNG an ihren Bausteinen, nicht am Wortlaut:
#: geprueft wird auf dem normalisierten Text (LaTeX-Abstandsbefehle,
#: geschweifte Einzelklammern und Leerraum entfernt), und ein Befund
#: verlangt MEHRERE Bausteine desselben Themas im selben Dokument. So
#: faellt eine umformatierte oder umgeschriebene Kopie ebenfalls auf,
#: waehrend ein blosser Verweis ("die Rekursion steht in ...") nicht
#: anschlaegt. Ein Waechter gegen sinngemaesse Prosa-Wiederholung ist
#: das ausdruecklich NICHT — dagegen hilft nur das Review.
BACKBONE_AUSFUEHRUNGEN = {
    "Thiele-Rekursion": (
        [r"V_j\(s", r"V_j\+1\(s", r"p_s\\tos"], 2,
    ),
    "Residuum-Regel": (
        [r"p_s\\toss?'?\(x", r"1-\\sum_s"], 2,
    ),
    "affine Ordnungs-Transformation": (
        [r"a\+b\\cdot", r"ersteOrdnung", r"\\min\(1"], 2,
    ),
    "Diskontfaktor-Definition": (
        [r"v=\\[tdf]?frac1\{?1\+i", r"v=1/\(1\+i\)"], 1,
    ),
}


def _normalisiert(text: str) -> str:
    r"""LaTeX-Rauschen entfernen, damit Umformatierungen nicht durchrutschen.

    ``\;=\;`` und ``=``, ``V_j`` und ``V_{j}``, ``\tfrac`` und
    ``\frac`` sollen dasselbe treffen — sonst faengt der Waechter nur
    die woertliche Kopie und nicht die umformatierte.
    """
    ohne = re.sub(r"\\[;,:!> ]", "", text)          # Abstandsbefehle
    ohne = re.sub(r"\\bigl|\\bigr|\\Bigl|\\Bigr|\\left|\\right",
                  "", ohne)
    ohne = ohne.replace("{", "").replace("}", "")   # V_{j+1} -> V_j+1
    return re.sub(r"\s+", "", ohne)


def _tarifplaene() -> Dict[str, Path]:
    return {p.stem: p for p in sorted(TARIFPLAENE.glob("*.md"))
            if p.stem != "README"}


def _ohne_codeblocks(text: str) -> str:
    """Ueberschriften INNERHALB eines Code-Fence sind keine Gliederung."""
    return re.sub(r"^```.*?^```", "", text, flags=re.M | re.S)


def _abschnitte(text: str) -> List[str]:
    """Nummerierte Top-Level-Abschnitte in Reihenfolge."""
    return re.findall(r"^# (\d+) (.+)$", _ohne_codeblocks(text), re.M)


def _alle_ueberschriften(text: str) -> List[str]:
    """Alle Top-Level-Ueberschriften — auch unnummerierte (Anhaenge)."""
    return re.findall(r"^# (.+)$", _ohne_codeblocks(text), re.M)


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
    laengen = {len(g) for g in gliederungen.values()}
    kuerzeste = min(laengen)
    for name, gliederung in gliederungen.items():
        # Der GEMEINSAME Kopf ist identisch; ein migriertes Produkt darf
        # hinten anhaengen (Ausgestaltung der Korrekturmathematik,
        # Grundsatzdokumentation Abschnitt 10 Nr. 9) — aber nicht
        # dazwischenschieben oder umbenennen.
        assert gliederung[:kuerzeste] == referenz[:kuerzeste], (
            f"{name}.md weicht im gemeinsamen Teil von {referenz_name}.md "
            f"ab:\n  {name}: {gliederung[:kuerzeste]}\n"
            f"  {referenz_name}: {referenz[:kuerzeste]}"
        )
        nummern = [int(n) for n, _ in gliederung]
        assert nummern == list(range(1, len(nummern) + 1)), (
            f"{name}.md: Abschnittsnummern springen: {nummern}"
        )
        # Unnummerierte Top-Level-Ueberschriften waeren ein Parkplatz
        # fuer Prosa, die der Gliederungsvergleich nicht sieht:
        unnummeriert = [
            u for u in _alle_ueberschriften(
                (TARIFPLAENE / f"{name}.md").read_text(encoding="utf-8"))
            if not re.match(r"\d+ ", u)
        ]
        assert not unnummeriert, (
            f"{name}.md traegt unnummerierte Abschnitte {unnummeriert} — "
            "sie stehen ausserhalb der geprueften Gliederung"
        )


def test_kein_tarifplan_fuehrt_das_gemeinsame_rueckgrat_aus():
    """Der Kern der Entdopplung: Was fuer alle Produkte gilt, steht
    einmal im zentralen Dokument. Ein Tarifplan verweist darauf."""
    def _treffer(text: str, bausteine):
        norm = _normalisiert(text)
        return [b for b in bausteine if re.search(b, norm)]

    zentral = ZENTRAL.read_text(encoding="utf-8")
    for thema, (bausteine, schwelle) in BACKBONE_AUSFUEHRUNGEN.items():
        gefunden = _treffer(zentral, bausteine)
        assert len(gefunden) >= schwelle, (
            f"{thema} steht nicht (mehr) in der Grundsatzdokumentation "
            f"(nur {gefunden}) — dann ist der Waechter blind"
        )
    for name, pfad in _tarifplaene().items():
        text = pfad.read_text(encoding="utf-8")
        rueckwanderung = [
            thema for thema, (bausteine, schwelle)
            in BACKBONE_AUSFUEHRUNGEN.items()
            if len(_treffer(text, bausteine)) >= schwelle
        ]
        assert not rueckwanderung, (
            f"{name}.md fuehrt Backbone-Themen aus: {rueckwanderung} — "
            "sie gehoeren in docs/fachkonzept/grundsatzdokumentation.md, "
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


#: Dateien, die frueher eine feste Abschnittszahl behaupteten. Der Drift,
#: der den Umbau ausgeloest hat, entstand genau hier: drei Stellen
#: sprachen von einer 12-Abschnitts-Gliederung, waehrend die Dokumente
#: 13 Abschnitte trugen.
ZAHL_BEHAUPTER = (
    "src/rechner_pipeline/spez/fachspez.py",
    ".claude/skills/dokumentiere-system/SKILL.md",
    ".agents/skills/dokumentiere-system/SKILL.md",
)


@pytest.mark.parametrize("datei", ZAHL_BEHAUPTER)
def test_niemand_behauptet_eine_falsche_abschnittszahl(datei):
    """Eine Zahl, die an mehreren Orten steht, driftet. Wer die
    Gliederungslaenge doch beziffert, wird gegen die Dokumente
    geprueft — die Formulierung muss dafuer eindeutig auf die
    Tarifplan-Gliederung zeigen ("N Abschnitte" / "N-Abschnitts"),
    nicht auf einen zitierten Abschnitt eines anderen Dokuments."""
    ist = len(_abschnitte(
        _tarifplaene()["klv"].read_text(encoding="utf-8")))
    text = (REPO_ROOT / datei).read_text(encoding="utf-8")
    behauptet = re.findall(r"\b(\d+)[- ]Abschnitt(?:e|s)\b", text)
    falsch = [n for n in behauptet if int(n) != ist]
    assert not falsch, (
        f"{datei} behauptet {falsch} Abschnitte, die Tarifplaene haben "
        f"{ist} — eine der beiden Stellen ist veraltet"
    )


def test_der_abschnittszahl_waechter_ist_nicht_vakuant():
    """Kontrolle zum vorigen Test: Er muss fallen, wenn jemand eine
    falsche Zahl schreibt — und darf nicht auf zitierte Abschnitte
    anderer Dokumente anspringen ("ADR-010 Abschnitt 5")."""
    ist = len(_abschnitte(
        _tarifplaene()["klv"].read_text(encoding="utf-8")))
    muster = r"\b(\d+)[- ]Abschnitt(?:e|s)\b"
    assert re.findall(muster, f"eine {ist - 1}-Abschnitts-Gliederung")
    assert re.findall(muster, f"die Tarifplaene haben {ist} Abschnitte")
    assert not re.findall(muster, "ADR-010 Abschnitt 5 sagt dazu")
    assert not re.findall(muster, "siehe Grundsatzdokumentation Abschnitt 4")
