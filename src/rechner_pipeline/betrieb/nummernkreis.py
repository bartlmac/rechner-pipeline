"""Die Nummernkreise der Fuehrung: was eine Police-Nummer des Tagesneugeschaefts sagt.

Police-Nummern des Tagesneugeschaefts tragen ihren Verkaufstag:
``nummernkreis * 10_000_000 + 5_000_000 + Fensterjahr * 100_000 +
Tag_des_Jahres * 100 + k`` (Fachkonzept Tagesbetrieb, Abschnitt 4). Der
Bereich ab 5 Mio liegt ueber dem jaehrlichen Neuzugang (ab 2 Mio; 1 bis
1 Mio gehoerte dem entfernten Batch-Erzeuger und bleibt frei, ADR-020);
mehr als 99 Vertraege an einem Tag oder ein Fenster ueber 30 Jahre sind
ein harter Fehler, kein stiller Ueberlauf.

Die Nummer ist die Identitaet der Police und damit Sache der Fuehrung
(Ebene 3; A-T1 zaehlt den Nummernkreis nicht zum Tarifwerk, ADR-031 zu
den Sichten). Deshalb steht die Arithmetik hier und nicht in der
Simulation: Das Tagesjournal liest den Verkaufstag aus der Nummer, ohne
die Welt zu fragen; das Neugeschaeft der Welt (``betrieb.neugeschaeft``)
vergibt die Nummern nach derselben Regel.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt

import numpy as np

from rechner_pipeline.bestand.config import TarifGeneration

#: police_id-Offset des Tagesneugeschaefts im Nummernkreis der Generation.
TAGES_ID_OFFSET = 5_000_000
#: Nummern je Verkaufstag (k = 1..99) und je Fensterjahr.
JE_TAG = 100
JE_JAHR = 100_000
#: Obergrenze des Nummernkreises (Generation belegt 10 Mio; der
#: jaehrliche Neuzugang endet vor 8 Mio, das Tagesneugeschaeft ab 5 Mio
#: darf also bis unter 8 Mio reichen).
ID_GRENZE = 8_000_000


class NeugeschaeftError(ValueError):
    """Config oder Tag passen nicht zum Tagesneugeschaeft (fail-fast)."""


def nummern_des_verkaufstags(
    gen: TarifGeneration, kreis: int, tag: _dt.date, anzahl: int
) -> np.ndarray:
    """Police-Nummern eines Verkaufstags im Nummernkreis ``kreis`` der
    Generation (config.nummernkreis, T22-09 — nicht ihre Position)."""
    fensterjahr = tag.year - gen.gueltig_von.year
    if anzahl >= JE_TAG:
        raise NeugeschaeftError(
            f"generation {gen.name}: {anzahl} Vertraege am {tag.isoformat()} "
            f"— der Nummernkreis traegt {JE_TAG - 1} je Tag; das Jahresziel "
            "oder die Wochentagsgewichte sind fuer einen Tagesbetrieb unplausibel"
        )
    basis = (
        kreis * 10_000_000
        + TAGES_ID_OFFSET
        + fensterjahr * JE_JAHR
        + tag.timetuple().tm_yday * JE_TAG
    )
    if basis + JE_TAG > kreis * 10_000_000 + ID_GRENZE:
        raise NeugeschaeftError(
            f"generation {gen.name}: Verkaufsfenster ab {gen.gueltig_von.isoformat()} "
            f"reicht im Jahr {tag.year} ueber den Nummernkreis des "
            "Tagesneugeschaefts hinaus (hoechstens 30 Fensterjahre)"
        )
    return basis + np.arange(1, anzahl + 1, dtype=np.int64)


def ist_tagesneugeschaeft(kreis: int, police_id: int) -> bool:
    """Liegt die Nummer im Tagesneugeschaefts-Abschnitt des Nummernkreises ``kreis``?"""
    rest = int(police_id) - kreis * 10_000_000
    return TAGES_ID_OFFSET <= rest < ID_GRENZE


def verkaufstag(gen: TarifGeneration, kreis: int, police_id: int) -> _dt.date:
    """Den Verkaufstag aus der Police-Nummer zurueckrechnen (Umkehrung).

    Die Nummer traegt Fensterjahr und Tag des Jahres; das Tagesjournal
    prueft damit, dass eine ZUG-Buchung des Tagesneugeschaefts an dem Tag
    gebucht ist, an dem die Police verkauft wurde.
    """
    rest = int(police_id) - kreis * 10_000_000 - TAGES_ID_OFFSET
    if not 0 <= rest < ID_GRENZE - TAGES_ID_OFFSET:
        raise NeugeschaeftError(
            f"police {police_id} liegt nicht im Nummernkreis des "
            f"Tagesneugeschaefts der Generation {gen.name}"
        )
    fensterjahr, rest = divmod(rest, JE_JAHR)
    tag_des_jahres, k = divmod(rest, JE_TAG)
    if k == 0 or tag_des_jahres == 0:
        raise NeugeschaeftError(
            f"police {police_id}: keine Tagesneugeschaefts-Nummer (k={k}, "
            f"Tag {tag_des_jahres})"
        )
    return _dt.date(gen.gueltig_von.year + fensterjahr, 1, 1) + _dt.timedelta(
        days=tag_des_jahres - 1
    )
