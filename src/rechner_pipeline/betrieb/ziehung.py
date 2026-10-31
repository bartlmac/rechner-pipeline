"""Der Tagesstrom: was die Welt dem Tagesbetrieb liefert (ADR-031).

Der Tageslauf fuehrt die Buecher; was in der simulierten Welt geschieht,
sagt ihm dieses Modul (Ebene 4, Vorzeige-Werkzeug) in EINEM Aufruf:
:func:`tagesstrom` liefert das Neugeschaeft seit dem Betriebsbeginn
(``betrieb.neugeschaeft``), die gezogenen Ereignisse aller Vertraege
(``bestand.ziehung``) und die Meldetage der Todesfaelle (der Meldeverzug;
seine Ziehung steht im Tagesjournal, weil dessen Leser sie dort binden,
der Strom ruft sie fuer jeden Tod, den die Fuehrung bucht). Die Fuehrung
(``betrieb.tageslauf``, ``betrieb.tagesjournal``) bucht damit, ohne die
Welt ein zweites Mal zu fragen; die Ratsche der Schichtenkarte nennt die
Kanten (``code_karte.VORZEIGE_NACH_WERKZEUG_ERLAUBT``).

Alles hier ist bitgleich zur Fuehrung vor ADR-031: dieselben Stroeme
(``bestand.zufallsstroeme``), dieselben Seeds, dieselbe Reihenfolge.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable, NamedTuple, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.ziehung import TOD, Ereignisliste, ziehe
# Die Ziehung des Meldeverzugs steht im Tagesjournal (die Leser des Journals
# binden sie dort); der Strom ruft sie ueber das Modul, damit auch eine
# dort ersetzte Ziehung hier gilt.
from rechner_pipeline.betrieb import tagesjournal as _tagesjournal
from rechner_pipeline.betrieb.neugeschaeft import (  # noqa: F401 — Re-Export
    NeugeschaeftError,
    neugeschaeft_zwischen,
)
from rechner_pipeline.betrieb.tagesjournal import Meldetage


class Tagesstrom(NamedTuple):
    """Was die Welt bis ``heute`` geschehen laesst: die Ereignisliste (Zugaenge
    des Neugeschaefts und Ereignisse aller Vertraege) und die Meldetage der
    Todesfaelle, die die Fuehrung buchen wird."""

    liste: Ereignisliste
    meldetage: Meldetage


def meldetage_fuer(
    config: BestandConfig, todesfaelle: Iterable[Tuple[int, int]]
) -> Meldetage:
    """Die Meldetage fuer (police_id, Wirkungsjahr)-Paare — je Paar einmal."""
    aus: Meldetage = {}
    for pid, jahr in todesfaelle:
        schluessel = (int(pid), int(jahr))
        if schluessel not in aus:
            aus[schluessel] = _tagesjournal.meldeverzug_tage(config, schluessel[0], schluessel[1])
    return aus


def tagesstrom(
    config: BestandConfig,
    basis: pd.DataFrame,
    betriebsbeginn: _dt.date,
    heute: _dt.date,
    *,
    merkmale: Optional[pd.DataFrame] = None,
    ledger_voran: Optional[pd.DataFrame] = None,
) -> Tagesstrom:
    """Der Strom des Tagesbetriebs bis ``heute``: Neugeschaeft aller
    Verkaufstage vom Betriebsbeginn bis heute, die Ereignisse des
    Basisbestands (die uebernommenen Vertraege) und des Neugeschaefts, und
    die Meldetage jedes Todes, den die Fuehrung bucht — auch der Tode, die
    eine Uebernahme mitbringt (``ledger_voran``, die dem Journal
    vorangestellten Buchungen).
    """
    zugaenge = neugeschaeft_zwischen(config, betriebsbeginn, heute)
    gesamt = (
        pd.concat([basis, zugaenge], ignore_index=True) if len(zugaenge) else basis
    )
    ereignisse = ziehe(gesamt, config, heute, merkmale=merkmale)
    tode = ereignisse[ereignisse["ereignis"] == TOD]
    paare = list(zip(tode["police_id"].astype("int64"),
                     pd.to_datetime(tode["wirkungstag"]).dt.year))
    if ledger_voran is not None and len(ledger_voran):
        voran = ledger_voran[ledger_voran["ereignis"].astype(str) == TOD]
        paare.extend(zip(voran["police_id"].astype("int64"),
                         pd.to_datetime(voran["status_date"]).dt.year))
    return Tagesstrom(Ereignisliste(zugaenge, ereignisse), meldetage_fuer(config, paare))
