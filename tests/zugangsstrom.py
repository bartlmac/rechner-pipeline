"""Testbestaende aus dem Zugangsstrom — der Ersatz fuer den Batch-Erzeuger.

Bis ADR-020 bauten siebzehn Testmodule ihren synthetischen Bestand ueber
``generator.generate(config)``: eine Ziehung ohne Geschichte, die es im
System nicht mehr gibt. Tests, die einen Stamm als EINGABE brauchen
(Fortschreibung, Bericht, Abschluss, Auswertung), bekommen ihn jetzt aus
demselben Strom, aus dem das System seine Vertraege bucht — dieselbe
Attributziehung, dieselben Policennummern, die der jaehrliche Erzeuger
im Journal als Zugang fuehren wuerde.

Kein Modul unter ``src/`` darf so etwas anbieten: Ein Stamm ohne Zugaenge
ist dort kein gueltiger Zustand. Hier ist er eine Eingabe.
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.generator import neuzugaenge


def bestand_aus_zugangsstrom(
    config: BestandConfig, bis: _dt.date | None = None
) -> pd.DataFrame:
    """Alle Vertraege, die der Zugangsstrom der Config bis ``bis`` liefert.

    ``bis`` schneidet den Strom wie ein Referenzstichtag: behalten werden
    Vertraege mit ``insurance_start < bis`` — der Stichtag selbst gehoert
    schon zum Neuzugang ``[bis, ...]`` (dovetail mit
    ``fortschreiben(neuzugang_ab=bis)``, dessen Wache eine Basis strikt
    VOR ``bis`` verlangt). Ohne ``bis``: der ganze Strom.
    """
    import datetime as _d
    fenster_von = min(g.gueltig_von for g in config.generationen)
    fenster_bis = max(g.gueltig_bis for g in config.generationen)
    if bis is None:
        return neuzugaenge(config, fenster_von, fenster_bis)
    ende = min(bis - _d.timedelta(days=1), fenster_bis)
    if ende < fenster_von:
        from rechner_pipeline.models.bestand import leerer_stamm
        return leerer_stamm()
    return neuzugaenge(config, fenster_von, ende)
