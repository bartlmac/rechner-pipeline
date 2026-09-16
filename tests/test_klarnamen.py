"""Keine Klarnamen in getrackten Dateien — maschinell statt als Bitte.

``AGENTS.md`` verbietet reale Namen von Team, Kunden oder Lieferanten in
getrackten Dateien und verlangt Rollenbezeichnungen. Die Regel stand
bis zum externen Review T19-06 nur in Prosa da — und wurde ueber Monate
in 44 Zeilen verletzt, ohne dass es jemandem auffiel. Eine Regel, die
niemand pruefen kann, ist eine Bitte; dieser Test macht sie zur Wache.

**Warum Hashes statt einer Namensliste.** Eine Liste realer Namen im
Repo waere selbst genau das, was die Regel verbietet — der Test wuerde
seine eigene Zusicherung brechen. Gespeichert sind darum nur
SHA-256-Praefixe der kleingeschriebenen Namen. Ein neuer Name kommt
ueber ``python -c "import hashlib;
print(hashlib.sha256('vorname'.encode()).hexdigest()[:16])"`` dazu.

**Was er NICHT ist.** Keine Sprach- oder Stilpruefung (die gehoert in
die Skills, nicht in Wortlisten-Tests): Er vergleicht Wort-Hashes,
sonst nichts. Fiktive Namen der Vorfuehrung — die abgebende
Gesellschaft, das aufnehmende Unternehmen, die Tarifgenerationen —
sind ausdruecklich erlaubt und stehen nicht in der Liste.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: SHA-256-Praefixe (16 Zeichen) kleingeschriebener realer Vor- und
#: Nachnamen aus dem Projektumfeld. Bewusst ohne Klartext.
VERBOTEN = frozenset({
    "b508f84ec91e4d4a",
    "9f2a08fde416cef2",
    "3ff5189b9532265a",
    "4603f221898a365d",
    "c0e3502dad697f45",
    "68168224c4721b50",
    "2d69120f4a37384f",
    "3fad3b3ae6cde17a",
    "35d95a6ba598d3e8",
    "3e78e1bd3445dbf3",
    "7c5d6f4e1bd59586",
    "c5c5f83055bb0d83",
    "b8f38a5e47a81aee",
})

#: Dateien, in denen echte Namen HINGEHOEREN: Urheberschaft und Lizenz.
#: Die Regel zielt auf Zuschreibungen im Fachtext ("Beschluss <Name>"),
#: nicht auf die Autorenfelder eines Pakets — dort waere eine Rolle
#: schlicht falsch. Bewusst eng: nur diese Dateien, nicht ganze Baeume.
URHEBER_DATEIEN = {"pyproject.toml", "LICENSE", "CITATION.cff"}

#: Endungen, die kein durchsuchbarer Text sind.
BINAER = {
    ".parquet", ".xlsm", ".xlsx", ".docx", ".pdf", ".png", ".jpg", ".jpeg",
    ".gif", ".ico", ".zip", ".woff", ".woff2", ".ttf", ".xml",
}

_WORT = re.compile(r"[A-Za-zÄÖÜäöüß]{4,}")


def _hash(wort: str) -> str:
    return hashlib.sha256(wort.lower().encode("utf-8")).hexdigest()[:16]


def _grundformen(wort: str) -> set[str]:
    """Das Wort und seine deutschen Flexionsformen auf die Grundform.

    Review T20-07: Fuenf Genitive ("<Name>s Entscheid") passierten die
    Wache, weil nur der exakte Wort-Hash verglichen wurde. Die Grundform
    entsteht hier durch Abstreifen der Flexionsendung — der verbotene Name
    selbst steht damit weiterhin nirgends im Repo.
    """
    formen = {wort}
    for endung in ("s", "es", "n", "ns"):
        if wort.endswith(endung) and len(wort) - len(endung) >= 4:
            formen.add(wort[: -len(endung)])
    return formen


def _getrackte_textdateien() -> list[Path]:
    roh = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, capture_output=True,
        text=True, check=True).stdout
    dateien = []
    for name in roh.split("\0"):
        if not name:
            continue
        pfad = REPO / name
        if pfad.suffix.lower() in BINAER or not pfad.is_file():
            continue
        if pfad.name in URHEBER_DATEIEN:
            continue
        dateien.append(pfad)
    return dateien


def test_keine_klarnamen_in_getrackten_dateien():
    """Rollen statt Namen — geprueft, nicht erbeten (Review-Befund T19-06)."""
    dateien = _getrackte_textdateien()
    assert len(dateien) > 100, "Dateiliste unplausibel klein — Aufruf pruefen"

    treffer: list[str] = []
    for pfad in dateien:
        try:
            text = pfad.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for nummer, zeile in enumerate(text.splitlines(), 1):
            for wort in _WORT.findall(zeile):
                if any(_hash(f) in VERBOTEN for f in _grundformen(wort)):
                    # Der Name selbst wird NICHT ausgegeben — die Meldung
                    # soll die Stelle zeigen, nicht die Regel brechen.
                    treffer.append(
                        f"{pfad.relative_to(REPO)}:{nummer} "
                        f"(Wort der Laenge {len(wort)})")
    assert not treffer, (
        "Klarnamen in getrackten Dateien — AGENTS.md verlangt Rollen "
        "(Maintainer, Verantwortlicher Aktuar, Quell-Experte, "
        "Programmleiter):\n  " + "\n  ".join(treffer[:20]))


@pytest.mark.parametrize("wort", ["maintainer", "aktuar", "programmleiter",
                                  "pfefferminzia", "baldrian"])
def test_rollen_und_fiktive_namen_sind_erlaubt(wort):
    """Zonen-Beleg: Die Wache trifft nur echte Namen.

    Ohne ihn koennte die Liste versehentlich ein Fachwort enthalten und
    die Suite bliebe trotzdem gruen, solange niemand es benutzt.
    """
    assert _hash(wort) not in VERBOTEN


def test_die_wache_findet_einen_eingeschmuggelten_namen(tmp_path):
    """Mutationsfaenger: Die Erkennung selbst muss funktionieren.

    Sonst bliebe der Test auch dann gruen, wenn Hash-Bildung oder
    Wortzerlegung kaputt waeren — ein Alarm, der nie schlaegt. Geprueft
    wird mit einem FREI ERFUNDENEN Namen, dessen Hash hier zur Laufzeit
    entsteht: Die echte Liste bleibt dafuer unangetastet, und im Repo
    steht wieder kein realer Name.
    """
    erfunden = "Wolkenschieber"
    zeile = f"Status: akzeptiert ({erfunden}, 2026-01-01)."
    verboten_probe = {_hash(erfunden)}

    gefunden = [w for w in _WORT.findall(zeile)
                if _hash(w) in verboten_probe]
    assert gefunden == [erfunden], "die Wortzerlegung trifft den Namen nicht"

    # Gegenprobe: dieselbe Zeile ohne den Namen bleibt unauffaellig.
    sauber = "Status: akzeptiert (Maintainer, 2026-01-01)."
    assert not [w for w in _WORT.findall(sauber)
                if _hash(w) in verboten_probe]

    # T20-07: Die Flexion darf die Wache nicht umgehen — der Genitiv des
    # erfundenen Namens muss auf dieselbe Grundform fallen.
    genitiv = f"{erfunden}s Entscheid vom 2026-01-01."
    gefunden = [w for w in _WORT.findall(genitiv)
                if any(_hash(f) in verboten_probe for f in _grundformen(w))]
    assert gefunden == [erfunden + "s"], "die Genitivform umgeht die Wache"
