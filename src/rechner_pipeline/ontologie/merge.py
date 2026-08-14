"""Deterministischer Merge von Quell-Fragmenten (P2 als Merge-Code).

Extraktions-Agenten liefern je Quelle ein Fragment (Feld -> Aussage,
jeweils nur mit der eigenen Provenienz). Das Zusammenfuehren ist
KEIN Agenten-Urteil, sondern dieser Code:

* beide Quellen belegen denselben Wert -> eine belegte Aussage mit
  BEIDEN Belegen (die staerkste Aussage der A-Box),
* nur eine Quelle belegt -> belegt mit einem Beleg,
* die Quellen widersprechen sich -> Zustand ``widerspruechlich`` plus
  Diskrepanz-Objekt mit beiden Lesarten — kein stiller Overwrite,
  keine Mehrheitsentscheidung,
* keine belegt -> ``nicht_belegt`` (unterscheidbar, nicht null).

Zahlenvergleich mit relativer Toleranz: Meldung und Rechner runden
verschieden (0,0008 vs. 0,08 %); ein Rundungsartefakt ist kein
fachlicher Widerspruch. Die Toleranz ist bewusst eng (1e-9 relativ)
— echte Parameterabweichungen liegen Groessenordnungen darueber.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from rechner_pipeline.ontologie.aussage import (
    Aussage,
    Lesart,
    Wert,
    Zustand,
)
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz, diskrepanz_id

RELATIVE_TOLERANZ = 1e-9


def werte_gleich(a: Wert, b: Wert, rel_tol: float = RELATIVE_TOLERANZ) -> bool:
    """Wertegleichheit; Zahlen mit relativer Toleranz, Rest exakt."""
    zahlen = (int, float)
    if isinstance(a, bool) or isinstance(b, bool):
        return a is b
    if isinstance(a, zahlen) and isinstance(b, zahlen):
        fa, fb = float(a), float(b)
        return abs(fa - fb) <= rel_tol * max(abs(fa), abs(fb), 1.0)
    return a == b


def merge_aussagen(
    knoten: str,
    feld: str,
    fragmente: List[Aussage],
) -> Tuple[Aussage, Optional[Diskrepanz]]:
    """Aussagen mehrerer Quellen zu EINER zusammenfuehren.

    Liefert die gemergte Aussage und — bei Widerspruch — das
    Diskrepanz-Objekt. Fragmente muessen je Quelle ``belegt`` oder
    ``nicht_belegt`` sein (mehrdeutig/widerspruechlich entsteht erst
    HIER; ein Agent liefert keine vorentschiedenen Konflikte).
    """
    for f in fragmente:
        if f.zustand not in (Zustand.BELEGT, Zustand.NICHT_BELEGT):
            raise ValueError(
                f"{knoten}/{feld}: Fragment im Zustand {f.zustand.value} — "
                "Konflikte entstehen im Merge, nicht im Fragment"
            )
    belegte = [f for f in fragmente if f.zustand is Zustand.BELEGT]
    if not belegte:
        return Aussage(), None

    # Lesarten nach Wertegleichheit gruppieren (deterministisch, in
    # Reihenfolge der Fragmente — die ist die Quellen-Reihenfolge).
    # Mitgliedschaft verlangt Gleichheit mit ALLEN Gruppenmitgliedern:
    # werte_gleich ist an der Toleranzgrenze nicht transitiv, und ein
    # Wert, der nur zu einem Teil der Gruppe passt, ist ein Konflikt,
    # keine Bestaetigung.
    gruppen: List[List[Aussage]] = []
    for f in belegte:
        for gruppe in gruppen:
            if all(werte_gleich(mitglied.wert, f.wert) for mitglied in gruppe):
                gruppe.append(f)
                break
        else:
            gruppen.append([f])

    if len(gruppen) == 1:
        gruppe = gruppen[0]
        konfidenzen = [f.konfidenz for f in gruppe if f.konfidenz is not None]
        return (
            Aussage(
                zustand=Zustand.BELEGT,
                wert=gruppe[0].wert,
                # Konservativ: die schwaechste Einschaetzung traegt.
                konfidenz=min(konfidenzen) if konfidenzen else None,
                provenienz=[p for f in gruppe for p in f.provenienz],
            ),
            None,
        )

    lesarten = [
        Lesart(wert=g[0].wert, provenienz=[p for f in g for p in f.provenienz])
        for g in gruppen
    ]
    d_id = diskrepanz_id(knoten, feld)
    aussage = Aussage(
        zustand=Zustand.WIDERSPRUECHLICH,
        lesarten=lesarten,
        diskrepanz_id=d_id,
    )
    diskrepanz = Diskrepanz(
        id=d_id, knoten=knoten, feld=feld, lesarten=lesarten
    )
    return aussage, diskrepanz


def merge_felder(
    knoten: str,
    fragmente_je_quelle: List[Dict[str, Aussage]],
) -> Tuple[Dict[str, Aussage], List[Diskrepanz]]:
    """Feld-Dicts mehrerer Quellen mergen (Feldmenge = Vereinigung)."""
    felder = sorted({f for frag in fragmente_je_quelle for f in frag})
    ergebnis: Dict[str, Aussage] = {}
    diskrepanzen: List[Diskrepanz] = []
    for feld in felder:
        vorhanden = [
            frag[feld] for frag in fragmente_je_quelle if feld in frag
        ]
        aussage, diskrepanz = merge_aussagen(knoten, feld, vorhanden)
        ergebnis[feld] = aussage
        if diskrepanz is not None:
            diskrepanzen.append(diskrepanz)
    return ergebnis, diskrepanzen
