"""Tagesjournal: welche Buchung an welchem Kalendertag sichtbar wird.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 3. Jeder
Geschaeftsvorfall hat zwei Daten: den **Wirkungstag** (``status_date``
des Ledgers — der Vertragstag, an dem er aktuariell wirkt, Monatserster-
Konvention) und den **Buchungstag**, an dem das Unternehmen ihn in die
Buecher nimmt. Der Ledger bleibt das Wirkungsjournal, das Gate P-B1
prueft; das Tagesjournal ist die zusaetzliche, nur-anfuegbare Tabelle
der Buchungstage — je Zeile ein Verweis auf genau eine Ledger-Zeile
(Police, Ereignis, Wirkungstag).

Der Buchungstag wird deterministisch aus dem Wirkungstag abgeleitet:

* Storno, Beitragsfreistellung, dynamische Erhoehung, Ablauf,
  Invalidisierung, Reaktivierung, Uebernahme-Buchungen: am Wirkungstag;
  faellt der auf ein Wochenende, am naechsten Werktag.
* Tod: Wirkungstag plus Meldeverzug — deterministisch gezogen aus der
  lognormalen Verteilung der Config (``[tagesbetrieb] meldeverzug_tod``,
  Median und 95-Prozent-Quantil), Seed aus Config-Seed, Police und
  Wirkungsjahr — dann auf den naechsten Werktag. Die Leistung wirkt am
  Wirkungstag, das Unternehmen erfaehrt es spaeter; der Bestand von
  gestern fuehrt solche Vertraege noch als aktiv. Das ist kein Fehler,
  das ist ein Versicherer.
* Neugeschaeft des Tagesbetriebs: Antrags- und Policierungstag ist der
  Buchungstag — der Verkaufstag, den die Police-Nummer traegt
  (:func:`rechner_pipeline.betrieb.neugeschaeft.verkaufstag`); der
  Wirkungstag (Versicherungsbeginn) liegt DANACH. Die einzige Buchung,
  deren Buchungstag vor dem Wirkungstag liegt.

Werktag heisst Montag bis Freitag; Feiertage sind bewusst nicht
modelliert (Konzept, Abschnitt 3). Die Wochentagsgewichte des Verkaufs
steuern nur das Neugeschaeft, nicht die Buchungstage.

**Bijektion.** :func:`validate_tagesjournal` haelt Tagesjournal und
Ledger gegeneinander, fuer alle Buchungen mit Buchungstag vom
Betriebsbeginn (``ab_tag``) bis zum gefuehrten Tag (``bis_tag``): jede
Journalzeile verweist auf genau eine Ledger-Zeile
mit demselben Betrag, jede faellige Ledger-Zeile hat genau eine
Journalzeile, jeder Buchungstag ist der neu abgeleitete, keine Zeile
liegt in der Zukunft, und die Buchungstage steigen in Dateireihenfolge
— die Tabelle ist nur angefuegt worden. Dieselbe Klasse wie die
ERH-Scheiben-Bindung (T18-01) und die Betragsidentitaet (T20-04): Eine
Journalzeile ohne Ledger-Gegenstueck oder ein verschobenes Datum ist
ein Befund, keine Sicht. Buchungen VOR dem Betriebsbeginn sind
Vorgeschichte: Der Ledger fuehrt sie (die Engine simuliert jeden Vertrag
ab seinem Beginn), das Tagesjournal beginnt mit dem ersten gefuehrten
Tag — es gab vorher keinen Tag, an dem jemand gebucht haette.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import math
from statistics import NormalDist
from typing import Any, Dict, List, Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig, Meldeverzug
from rechner_pipeline.betrieb.neugeschaeft import (
    NeugeschaeftError,
    ist_tagesneugeschaeft,
    verkaufstag,
)
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    TAGESJOURNAL_NAMES,
    TAGESJOURNAL_SPALTEN,
    validate_tagesjournal as _validate_vertrag,
)

#: SeedSequence-Konstante des Meldeverzugs — getrennt von Batch, jaehrlichem
#: Neuzugang (771177), Ereignis-Engine (424242) und Tagesneugeschaeft (918273).
MELDEVERZUG_STREAM = 552211

#: 95-Prozent-Quantil der Standardnormalverteilung (lognormal: p95 = median * exp(sigma * z95)).
_Z95 = NormalDist().inv_cdf(0.95)

#: Schluessel einer Ledger-Zeile im Tagesjournal.
SCHLUESSEL: Tuple[str, ...] = ("police_id", "ereignis", "status_date")


class TagesjournalError(ValueError):
    """Tagesjournal und Ledger passen nicht zusammen — fail-fast."""


# --------------------------------------------------------------------------- #
# Kalender
# --------------------------------------------------------------------------- #


def ist_werktag(tag: _dt.date) -> bool:
    return tag.weekday() < 5


def naechster_werktag(tag: _dt.date) -> _dt.date:
    """Der Tag selbst, wenn er ein Werktag ist, sonst der naechste."""
    while not ist_werktag(tag):
        tag += _dt.timedelta(days=1)
    return tag


# --------------------------------------------------------------------------- #
# Meldeverzug
# --------------------------------------------------------------------------- #


def meldeverzug_sigma(verzug: Meldeverzug) -> float:
    """Streuung der lognormalen Verteilung aus Median und 95-Prozent-Quantil."""
    return (math.log(verzug.p95_tage) - math.log(verzug.median_tage)) / _Z95


def meldeverzug_tage(config: BestandConfig, police_id: int, wirkungsjahr: int) -> int:
    """Der Meldeverzug eines Todes in Tagen — deterministisch je Police und Jahr.

    Lognormal mit Median ``median_tage`` und 95-Prozent-Quantil ``p95_tage``
    (Config), gerundet auf ganze Tage, nie negativ. Ein eigener Substream
    je (Police, Wirkungsjahr): Weder die Reihenfolge der Laeufe noch
    andere Policen veraendern den Verzug.
    """
    verzug = config.tagesbetrieb.meldeverzug_tod
    fehler = verzug.validate("meldeverzug_tod")
    if fehler:
        raise TagesjournalError("; ".join(fehler))
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(
        [config.seed, MELDEVERZUG_STREAM, int(police_id), int(wirkungsjahr)]
    )))
    z = float(rng.standard_normal())
    tage = math.exp(math.log(verzug.median_tage) + meldeverzug_sigma(verzug) * z)
    return max(0, int(round(tage)))


# --------------------------------------------------------------------------- #
# Buchungstag und Herkunft je Ledger-Zeile
# --------------------------------------------------------------------------- #


def herkunft(
    config: BestandConfig, police_id: int, ereignis: str, betrag_herkunft: str,
    tarif_generation: str,
) -> str:
    """Woher eine Buchung stammt: Tagesneugeschaeft, Uebernahme oder Fortschreibung."""
    if ereignis == "ZUG":
        index = _generationsindex(config)
        if tarif_generation in index and ist_tagesneugeschaeft(
            index[tarif_generation][0], police_id
        ):
            return "neugeschaeft"
        if betrag_herkunft == "geliefert":
            return "uebernahme"
    elif betrag_herkunft == "geliefert":
        return "uebernahme"
    return "fortschreibung"


def _generationsindex(config: BestandConfig) -> Dict[str, Tuple[int, Any]]:
    return {g.name: (i, g) for i, g in enumerate(config.generationen)}


def buchungstag(
    config: BestandConfig,
    police_id: int,
    ereignis: str,
    wirkungstag: _dt.date,
    herkunft_der_zeile: str,
    tarif_generation: str,
) -> _dt.date:
    """Der Buchungstag einer Ledger-Zeile nach den Regeln des Konzepts."""
    wirkungstag = pd.Timestamp(wirkungstag).date()
    if herkunft_der_zeile == "neugeschaeft":
        index = _generationsindex(config)
        if tarif_generation not in index:
            raise TagesjournalError(
                f"police {police_id}: Tarifgeneration {tarif_generation!r} "
                "nicht in der Config — der Verkaufstag ist nicht ableitbar"
            )
        gen_index, gen = index[tarif_generation]
        try:
            tag = verkaufstag(gen, gen_index, police_id)
        except NeugeschaeftError as exc:
            raise TagesjournalError(str(exc)) from exc
        if tag >= wirkungstag:
            raise TagesjournalError(
                f"police {police_id}: Verkaufstag {tag.isoformat()} liegt "
                f"nicht vor dem Versicherungsbeginn {wirkungstag.isoformat()}"
            )
        return tag
    if ereignis == "TOD":
        verzug = meldeverzug_tage(config, police_id, wirkungstag.year)
        return naechster_werktag(wirkungstag + _dt.timedelta(days=verzug))
    return naechster_werktag(wirkungstag)


def mit_buchungstagen(config: BestandConfig, ledger: pd.DataFrame) -> pd.DataFrame:
    """Die Sicht des Tagesjournals auf JEDE Ledger-Zeile (ohne Faelligkeitsfilter).

    Spalten wie das Tagesjournal; Reihenfolge nach Buchungstag, dann
    Schluessel. Was davon in der Tabelle steht, entscheidet der gefuehrte
    Tag (:func:`faellige_zeilen`).
    """
    fehlend = [c for c in LEDGER_NAMES if c not in ledger.columns]
    if fehlend:
        raise TagesjournalError(f"ledger: Spalten fehlen: {fehlend}")
    if len(ledger) and ledger[list(SCHLUESSEL)].duplicated().any():
        doppelt = ledger[ledger[list(SCHLUESSEL)].duplicated()].iloc[0]
        raise TagesjournalError(
            "ledger: Schluessel (police_id, ereignis, status_date) nicht "
            f"eindeutig, z. B. police {int(doppelt['police_id'])} "
            f"{doppelt['ereignis']} {pd.Timestamp(doppelt['status_date']).date()}"
        )
    zeilen: List[Dict[str, Any]] = []
    for z in ledger.itertuples(index=False):
        pid, ereignis = int(z.police_id), str(z.ereignis)
        quelle = herkunft(config, pid, ereignis, str(z.betrag_herkunft), str(z.tarif_generation))
        tag = buchungstag(config, pid, ereignis, z.status_date, quelle, str(z.tarif_generation))
        zeilen.append({
            "buchungsdatum": pd.Timestamp(tag),
            "police_id": pid,
            "ereignis": ereignis,
            "status_date": pd.Timestamp(z.status_date),
            "betrag": float(z.betrag),
            "betrag_art": str(z.betrag_art),
            "herkunft": quelle,
        })
    if not zeilen:
        return leeres_tagesjournal()
    df = pd.DataFrame(zeilen)[list(TAGESJOURNAL_NAMES)].astype(dict(TAGESJOURNAL_SPALTEN))
    return df.sort_values(
        ["buchungsdatum", "police_id", "ereignis", "status_date"], kind="stable"
    ).reset_index(drop=True)


def leeres_tagesjournal() -> pd.DataFrame:
    return pd.DataFrame({n: pd.Series(dtype=d) for n, d in TAGESJOURNAL_SPALTEN})


def faellige_zeilen(
    sicht: pd.DataFrame, bis_tag: _dt.date, ab_tag: _dt.date
) -> pd.DataFrame:
    """Alle Zeilen der Journalsicht mit Buchungstag in ``[ab_tag, bis_tag]``."""
    tage = sicht["buchungsdatum"]
    return sicht[(tage >= pd.Timestamp(ab_tag)) & (tage <= pd.Timestamp(bis_tag))].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Anfuegen und Pruefen
# --------------------------------------------------------------------------- #


def _schluessel(df: pd.DataFrame) -> pd.Index:
    return pd.MultiIndex.from_arrays(
        [df["police_id"].astype("int64"), df["ereignis"].astype(str),
         pd.to_datetime(df["status_date"])],
        names=list(SCHLUESSEL),
    )


def tagesjournal_ergaenzen(
    journal: pd.DataFrame,
    ledger: pd.DataFrame,
    config: BestandConfig,
    bis_tag: _dt.date,
    *,
    ab_tag: _dt.date,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Die bis ``bis_tag`` faelligen, noch nicht gebuchten Ledger-Zeilen anfuegen.

    ``ab_tag`` ist der Betriebsbeginn: Buchungen davor sind Vorgeschichte
    und gehoeren nicht ins Journal.

    Rueckgabe ``(journal_neu, angefuegt)``. Bestehende Zeilen werden nie
    veraendert oder umsortiert; die neuen Zeilen liegen dahinter, nach
    Buchungstag geordnet. Vorher wird das bestehende Journal gegen den
    Ledger gehalten (Bijektion bis zum letzten Buchungstag des Journals):
    Ein Journal, das schon nicht mehr zum Ledger passt, bekommt keine
    weiteren Zeilen — sonst wuerde der Befund mit jedem Tag tiefer
    vergraben.
    """
    bis_tag, ab_tag = pd.Timestamp(bis_tag).date(), pd.Timestamp(ab_tag).date()
    if bis_tag < ab_tag:
        raise TagesjournalError(
            f"tagesjournal: bis {bis_tag.isoformat()} liegt vor dem "
            f"Betriebsbeginn {ab_tag.isoformat()}"
        )
    journal = journal[list(TAGESJOURNAL_NAMES)].reset_index(drop=True) if len(journal) else leeres_tagesjournal()
    sicht = mit_buchungstagen(config, ledger)
    if len(journal):
        letzter = pd.Timestamp(journal["buchungsdatum"].max()).date()
        if letzter > bis_tag:
            raise TagesjournalError(
                f"tagesjournal: fuehrt Buchungen bis {letzter.isoformat()}, "
                f"angefuegt werden soll bis {bis_tag.isoformat()} — ein Tag "
                "wird nicht rueckwaerts gefuehrt"
            )
        fehler = _validate_vertrag(journal, sicht, ab_tag=ab_tag, bis_tag=letzter)
        if fehler:
            raise TagesjournalError(
                "tagesjournal passt nicht zum Ledger: " + "; ".join(fehler[:5])
            )
    faellig = faellige_zeilen(sicht, bis_tag, ab_tag)
    vorhanden = _schluessel(journal) if len(journal) else pd.MultiIndex.from_arrays(
        [[], [], []], names=list(SCHLUESSEL))
    neu = faellig[~_schluessel(faellig).isin(vorhanden)].reset_index(drop=True)
    if len(neu) == 0:
        return journal, neu
    zusammen = pd.concat([journal, neu], ignore_index=True)[list(TAGESJOURNAL_NAMES)]
    return zusammen.astype(dict(TAGESJOURNAL_SPALTEN)), neu


def validate_tagesjournal(
    journal: pd.DataFrame,
    ledger: pd.DataFrame,
    config: BestandConfig,
    bis_tag: _dt.date,
    *,
    ab_tag: _dt.date,
) -> List[str]:
    """Bijektion Tagesjournal <-> Ledger fuer alle Buchungen in ``[ab_tag, bis_tag]``.

    Die Ableitung der Buchungstage geschieht hier
    (:func:`mit_buchungstagen`), der Vertrag selbst liegt neben den
    uebrigen Bestandsvertraegen
    (:func:`rechner_pipeline.models.bestand.validate_tagesjournal`).
    Fehlerlisten-Idiom (leer = deckungsgleich).
    """
    try:
        sicht = mit_buchungstagen(config, ledger)
    except TagesjournalError as exc:
        return [str(exc)]
    return _validate_vertrag(journal, sicht, ab_tag=ab_tag, bis_tag=bis_tag)
