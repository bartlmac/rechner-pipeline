"""Vorverarbeitungsschicht (Stage 1): ein deterministischer, LLM-freier
Vorverdichter je Quelltyp.

* :mod:`.extract` + :mod:`.adapters` — Excel-Arbeitsmappen (Zellen, VBA,
  Erwartungswerte; Adapter-Naht fuer weitere Quellformate).
* :mod:`.tarifplan_staging` — DOCX-Tarifplaene (Mitteilung 143) zu
  strukturiertem JSON.
* Bestandsdaten-Profiling folgt mit dem ersten Migrationsfall.

Kein Modell sieht eine Rohquelle, zu der es kein strukturiertes Derivat
gibt (Architektur-Prinzip P10, siehe docs/architektur/).
"""
