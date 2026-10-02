"""Die Nebentabellen eines Laufs, wie der Produzent sie an den Abschluss gibt.

Befund aus dem Raten-Block (2026-10-01): Herabsetzung und Teilkuendigung
hinterlassen weder im Stamm noch in der Historie eine Spur, nur in
``reduktionen``. Die In-Prozess-Tests gaben dem Abschluss nur die Scheiben
mit und bewerteten herabgesetzte und teilgekuendigte Vertraege ungekuerzt —
anders als ``cli_abschluss`` und ``tageslauf``. Seitdem verlangen
``schreibe_abschluss`` und ``pruefe_abschluss`` jede Nebentabelle ohne
Vorgabewert; dieser Helfer liefert sie aus einer Fortschreibung bzw. einem
Laufverzeichnis, damit kein Test sie sich selbst zusammenstellt.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

#: Die Nebentabellen des Abschlusses — die Schluesselwoerter von
#: ``schreibe_abschluss``/``pruefe_abschluss``/``einzelwerte_am``.
NAMEN = ("scheiben", "merkmale", "schichten", "verankerung", "reduktionen")


class LaufTupel(tuple):
    """Ein Tupel aus Fixture-Werten mit den Nebentabellen als ``neben``."""

    neben: Dict[str, Any]


def mit_neben(werte: tuple, neben: Dict[str, Any]) -> LaufTupel:
    aus = LaufTupel(werte)
    aus.neben = dict(neben)
    return aus


def aus_fortschreibung(ergebnis: Any, **weitere: Optional[Any]) -> Dict[str, Any]:
    """Aus ``ereignisse.fortschreiben``: Scheiben und Reduktionen des Laufs,
    Merkmale/Schichten/Verankerung so, wie der Aufrufer sie hineingab."""
    neben = {n: None for n in NAMEN}
    neben["scheiben"] = ergebnis.scheiben
    neben["reduktionen"] = ergebnis.reduktionen
    neben.update(weitere)
    return neben


def aus_lauf(lauf: Path) -> Dict[str, Any]:
    """Aus einem Laufverzeichnis: jede vorhandene Nebentabelle, sonst None."""
    from rechner_pipeline.bestand.parquet_io import read_portfolio

    return {n: (read_portfolio(Path(lauf) / f"{n}.parquet")
                if (Path(lauf) / f"{n}.parquet").is_file() else None)
            for n in NAMEN}
