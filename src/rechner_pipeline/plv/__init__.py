"""Die PLV als Zielsystem: die Implementierung des Zielvertrags (ADR-030).

Objekt PLV (ADR-028), Ebene 3 (ADR-017), neben ``kern``, ``bestand`` und
``betrieb``. Dieses Paket erfuellt den Vertrag aus
``rechner_pipeline.zielsystem`` mit dem, was Kern und Bestandsfuehrung
heute schon koennen; es liegt ausserhalb von ``kern/``, weil der
abgenommene Kernstand das Paket ``kern`` bindet (A-K2).

Stufe 0: die PLV nennt sich und die Vertragsversion, bietet noch keine
Faehigkeit an. Stufe 1 bringt die Rechnungsgrundlagen, Stufe 2 die
Bewertung.

Knoten: system/zielsystem
"""
