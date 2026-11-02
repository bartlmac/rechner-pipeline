"""Die PLV als Zielsystem: die Implementierung des Zielvertrags (ADR-030).

Objekt PLV (ADR-028), Ebene 3 (ADR-017), neben ``kern``, ``bestand`` und
``betrieb``. Dieses Paket erfuellt den Vertrag aus
``rechner_pipeline.zielsystem`` mit dem, was Kern und Bestandsfuehrung
heute schon koennen; es liegt ausserhalb von ``kern/``, weil der
abgenommene Kernstand das Paket ``kern`` bindet (A-K2).

Stufe 0: die PLV nennt sich und die Vertragsversion. Stufe 1: sie
bietet die Rechnungsgrundlagen an (``rechnungsgrundlagen.py``: Produkte,
Parametersatz mit Defaults, Modellpunkt, Tafeln). Stufe 2: die Bewertung
(``bewertung.py``: Werte eines Vertrags, Vorgangsfolge, Korrekturschicht,
Vorgangsregeln, Praemien, Verlauf, Rechenlauf).

Knoten: system/zielsystem
"""
