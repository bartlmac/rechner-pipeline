"""Kommutationskern: der SEPARATE Zweitkern (klassische Rechenschiene).

Bewusst ausserhalb des Zielkerns (`rechner_pipeline.kern`): der Zielkern
rechnet vollstaendig in der Thiele-/Zustandsmodell-Welt; die klassischen
Kommutationsspalten (D/N/C/M) und Barwert-Bausteine hier sind eine
ZWEITE, unabhaengig gebaute Implementierung derselben Rechnungsbasis —
ueber die Absterbeordnung l_x, waehrend der Zielkern auf
Uebergangswahrscheinlichkeiten rechnet.

**Seit ADR-013 hat dieses Paket keinen Konsumenten im Produktivpfad.**
Die Toleranz-Ueberleitung, fuer die es gebaut wurde, war der
Uebersetzungsbeleg des Backbone-Wechsels und ist erbracht. Was bleibt,
ist ein Zeuge fuer die algebraischen Eigenschaftstests
(``tests/test_kern_algebraisch.py``): Sie halten die Durchreicher
``pv_benefits``/``pv_premiums``/``net_premium`` des Zielkerns gegen
diesen Kern, damit dort nicht der Methodenrumpf gegen sich selbst
prueft.

Der Unterschied zu vorher ist wesentlich: Die Tests bauen diesen Kern
testseitig SELBST und vergleichen Skalare. Sie haengen ihn NICHT ueber
eine Schnittstelle in den Zielkern ein, die dieser ihretwegen
aufrechterhalten muesste. Damit hat der Zweitkern keinen Anspruch mehr
an den lebenden Code — und formt ihn auch nicht mehr.

Die Tafeldaten kommen aus der Rechnungsgrundlagen-Schicht des Zielkerns
(:mod:`rechner_pipeline.kern.tafeln`) — eine Wahrheit, zwei Rechenwege.

Knoten: klv
"""

from rechner_pipeline.kommutationskern.kommutation import (  # noqa: F401
    Kommutation,
    fuer,
)
