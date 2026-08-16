"""Kommutationskern: der SEPARATE Zweitkern (klassische Rechenschiene).

Bewusst ausserhalb des Zielkerns (`rechner_pipeline.kern`): der Zielkern
rechnet vollstaendig in der Thiele-/Zustandsmodell-Welt; die klassischen
Kommutationsspalten (D/N/C/M) und Barwert-Bausteine hier dienen
AUSSCHLIESSLICH als unabhaengige Kreuz-Rechenschiene der Abnahme
(:mod:`rechner_pipeline.qa.ueberleitung`) — zwei Rechenwege, eine
Toleranz. Kein Produktions-Code importiert dieses Paket; die
Abhaengigkeit laeuft nur QA -> kommutationskern.

Die Tafeldaten kommen aus der Rechnungsgrundlagen-Schicht des Zielkerns
(:mod:`rechner_pipeline.kern.tafeln`) — eine Wahrheit, zwei Rechenwege.
"""

from rechner_pipeline.kommutationskern.kommutation import (  # noqa: F401
    Kommutation,
    fuer,
)
