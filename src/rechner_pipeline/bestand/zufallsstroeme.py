"""Register der Zufallsstroeme: EINE Stelle, an der jeder Strom seinen Wert hat.

Jede Ereignisfamilie zieht aus einem eigenen Strom
``SeedSequence([seed, STROM, police_id])`` (bzw. ``[seed, STROM, ...]``).
Zwei Familien mit demselben Wert zoegen je Police dieselbe Folge — perfekte
Abhaengigkeit statt Unabhaengigkeit, und kein Ergebnis saehe falsch aus.
Bis zur Teilkuendigung (Entscheid des Maintainers 2026-10-01) war die
Eindeutigkeit nur ein Satz in einem Docstring; jetzt ist sie eine Pruefung
beim Import: Ein doppelter Wert bricht den Import ab (fail-fast), und jedes
Modul, das einen Strom zieht, liest seinen Wert hier.

Die Werte der fuenf bestehenden Stroeme sind exakt die frueheren — jede
Aenderung verschoebe jeden Bestand. Ein neuer Strom bekommt einen NEUEN Wert;
``tests/test_herabsetzung_und_teilkuendigung.py`` haelt per AST, dass unter
``src/`` keine ``*_STREAM``-Konstante ausserhalb dieses Registers einen
eigenen Zahlenwert traegt.

Knoten: klv, bu
"""

from __future__ import annotations

from typing import Mapping

#: Name -> Wert. Der Name ist die Ereignisfamilie.
STROEME: Mapping[str, int] = {
    # Ereignis-Engine: der Hauptstrom (Tod, Storno, Beitragsfreistellung,
    # Erhoehung; BU-Uebergaenge) — feste Draw-Reihenfolge je Jahr.
    "ereignis": 424242,
    # Beitragsherabsetzung (RED): eigener Strom, damit ihr Draw keinen
    # bestehenden Bestand verschiebt.
    "herabsetzung": 606606,
    # Teilkuendigung (TKU, eigener Geschaeftsvorfall seit 2026-10-01): eigener
    # Strom aus demselben Grund; mit Rate 0 (Vorgabe) ist er latent.
    "teilkuendigung": 313131,
    # Generator des Anfangsbestands (bestand.generator).
    "neuzugang": 771177,
    # Meldeverzug des Tagesjournals (betrieb.tagesjournal).
    "meldeverzug": 552211,
    # Neugeschaeft des Tagesbetriebs (betrieb.neugeschaeft).
    "neugeschaeft": 918273,
}


class StromKollision(ValueError):
    """Zwei Ereignisfamilien teilen einen Stromwert."""


def _pruefe_eindeutig(stroeme: Mapping[str, int]) -> None:
    werte = list(stroeme.values())
    doppelt = sorted({w for w in werte if werte.count(w) > 1})
    if doppelt:
        namen = sorted(n for n, w in stroeme.items() if w in doppelt)
        raise StromKollision(
            f"Zufallsstroeme {namen} teilen die Werte {doppelt} — zwei "
            "Ereignisfamilien zoegen je Police dieselbe Folge. Ausweg: dem "
            "neuen Strom einen eigenen Wert geben")


_pruefe_eindeutig(STROEME)
