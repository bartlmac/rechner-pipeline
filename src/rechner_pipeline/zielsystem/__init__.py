"""Der Zielvertrag: was das Migrationssystem von einem Zielsystem braucht.

ADR-030. Das Tool definiert die Schnittstelle, die es von einem Zielsystem
braucht (ADR-017); dieses Paket ist diese Schnittstelle, versioniert und
mit eigenen Konformitaetspruefungen. Die PLV erfuellt den Vertrag in
``rechner_pipeline.plv``; das Tool kennt diese Implementierung an genau
einer Stelle, ``anbieter.py``.

Stufe 0 (Geruest): Versionskennung, der Katalog der fuenf Faehigkeiten,
das Wurzelprotokoll ``Zielsystem`` und die Konformitaetspruefung. Stufe 1:
das Protokoll ``Rechnungsgrundlagen`` (``rechnungsgrundlagen.py``).
Stufe 2: das Protokoll ``Bewertung`` (``bewertung.py``). Die uebrigen
Protokolle kommen mit ihren Stufen, damit der Vertrag nichts beschreibt,
was niemand erfuellt.

Knoten: system/zielsystem
"""
