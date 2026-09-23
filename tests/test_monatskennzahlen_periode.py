"""Jeder Geschaeftsvorfall wird in genau einem Monat gezaehlt.

Die Monatskennzahlen eines Abschlusses teilen den Vorfallstrom in
Monate. Eine Einteilung, die keine Zerlegung ist, verliert stillschweigend
Vorfaelle: Sie stehen in keiner Monatszeile, und niemand vermisst sie,
weil eine fehlende Zeile wie ein ruhiger Monat aussieht.

Genau das war der Fall, bis die Periode auf den Wirkungstag gelegt und
zusaetzlich auf das Buchungsdatum geschnitten wurde. Ein Vorfall, dessen
Wirkungstag GENAU auf einen Stichtag faellt und der danach gebucht wird,
war fuer seinen eigenen Monat zu spaet gebucht und fuer den naechsten zu
frueh wirksam. Am betriebenen Bestand gemessen (2026-09-19): 2621 von
13144 Vorfaellen in keinem Monat, darunter 191 Ablaeufe, 188 Stornos und
141 Todesfaelle.

Die Achse ist deshalb der Sichtbarkeitstag ``max(status_date,
buchungsdatum)`` — der Tag, an dem ein Abschluss den Vorfall erstmals
kennt. Diese Tests halten die Zerlegungs-Eigenschaft fest, nicht das
Ergebnis eines Laufs.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from rechner_pipeline.bestand.kennzahlen import bewegungskennzahlen
from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES


def _journal(zeilen) -> pd.DataFrame:
    """Ein Tagesjournal aus (police_id, ereignis, wirkung, buchung)."""
    df = pd.DataFrame(
        [
            {
                "buchungsdatum": pd.Timestamp(buchung),
                "police_id": pid,
                "ereignis": ereignis,
                "status_date": pd.Timestamp(wirkung),
                "betrag": 1000.0,
                "betrag_art": "VS",
                "herkunft": "bestand",
            }
            for pid, ereignis, wirkung, buchung in zeilen
        ]
    )
    return df[list(TAGESJOURNAL_NAMES)]


def _monatsgitter(von: dt.date, bis: dt.date):
    """Alle Monatsersten von ``von`` bis ``bis`` einschliesslich."""
    stichtage, s = [], von
    while s <= bis:
        stichtage.append(s)
        s = (s.replace(day=28) + dt.timedelta(days=7)).replace(day=1)
    return stichtage


def test_der_spaet_gebuchte_vorfall_auf_dem_stichtag_faellt_nicht_durch():
    """Der konkrete Fall, der 2621 Vorfaelle verschluckt hat.

    Wirkung am 1.8., gebucht am 3.8.: Der Abschluss zum 1.8. kennt ihn
    nicht (zu spaet gebucht), der zum 1.9. kennt ihn. Also meldet ihn der
    Monat, der auf den 1.9. endet — und sonst keiner.
    """
    j = _journal([(1, "STO", "2026-08-01", "2026-08-03")])
    august = bewegungskennzahlen(j, dt.date(2026, 8, 1))
    september = bewegungskennzahlen(j, dt.date(2026, 9, 1))
    assert august["leistungen"] == 0, "zu spaet gebucht — der 1.8. kennt ihn nicht"
    assert september["leistungen"] == 1, (
        "der Vorfall wird zwischen dem 1.8. und dem 1.9. sichtbar und "
        "gehoert damit in die Zeile zum 1.9.")


def test_die_achse_ist_die_sichtbarkeit_nicht_die_wirkung():
    """Pinnt die Achse gegen einen Rueckbau auf den Wirkungstag.

    Zwei Vorfaelle mit DEMSELBEN Wirkungstag, verschieden gebucht: Auf
    dem Wirkungstag gezaehlt laegen beide im selben Monat. Sie liegen es
    nicht — der spaeter gebuchte wird erst spaeter sichtbar.
    """
    j = _journal([(1, "STO", "2026-08-15", "2026-08-16"),
                  (2, "STO", "2026-08-15", "2026-09-30")])
    assert bewegungskennzahlen(j, dt.date(2026, 9, 1))["leistungen"] == 1
    assert bewegungskennzahlen(j, dt.date(2026, 10, 1))["leistungen"] == 1


def test_vor_der_wirkung_gebucht_zaehlt_die_wirkung():
    """Die Gegenrichtung: Ein Zugang wird oft vor seinem Beginn gebucht.

    Sichtbar wird er trotzdem erst mit der Wirkung — vorher steht er in
    keinem Abschluss. ``max`` deckt beide Richtungen ab; ein blosser
    Wechsel auf das Buchungsdatum haette diesen Fall verschoben.
    """
    j = _journal([(1, "ZUG", "2026-09-01", "2026-08-20")])
    assert bewegungskennzahlen(j, dt.date(2026, 8, 1))["zugaenge"] == 0
    assert bewegungskennzahlen(j, dt.date(2026, 9, 1))["zugaenge"] == 1


def test_die_monate_zerlegen_den_vorfallstrom_vollstaendig():
    """Die eigentliche Klasse: Summe ueber alle Monate == alle Vorfaelle.

    Geprueft wird ueber ein zusammenhaengendes Monatsgitter mit allen
    Lagen, die es gibt — Wirkung vor, auf und nach dem Stichtag, Buchung
    frueher und spaeter. Ein Vorfall, der in keinem Monat auftaucht,
    faellt hier auf; einer, der in zweien auftaucht, auch.
    """
    zeilen = [
        (10, "ZUG", "2026-07-01", "2026-06-25"),
        (11, "ZUG", "2026-07-15", "2026-07-15"),
        (12, "STO", "2026-08-01", "2026-08-03"),
        (13, "ABL", "2026-08-01", "2026-08-01"),
        (14, "TOD", "2026-08-20", "2026-09-04"),
        (15, "ERH", "2026-09-01", "2026-08-29"),
        (16, "STO", "2026-09-01", "2026-09-01"),
        (17, "ZUG", "2026-10-01", "2026-09-20"),
    ]
    j = _journal(zeilen)
    stichtage = _monatsgitter(dt.date(2026, 6, 1), dt.date(2026, 11, 1))
    gezaehlt = sum(
        sum(bewegungskennzahlen(j, s).values()) for s in stichtage
    )
    # Alle acht sind entweder Zugang (ZUG/ERH) oder Leistung (ABL/STO/TOD)
    # — keine benannte Ausnahme dabei, damit die Summe die Zahl der
    # Vorfaelle ist und nicht eine Teilmenge davon.
    assert gezaehlt == len(zeilen), (
        f"{len(zeilen)} Vorfaelle, aber {gezaehlt} ueber alle Monate gezaehlt")


def test_ein_vorfall_bucht_zwei_zeilen_und_zaehlt_einmal():
    """Positivkontrolle der Entdoppelung: Ein Zugang bucht Summe und
    Bruttojahresbeitrag. Gezaehlt wird der Vorfall, nicht die Zeile."""
    j = _journal([(1, "ZUG", "2026-09-01", "2026-09-01"),
                  (1, "ZUG", "2026-09-01", "2026-09-01")])
    assert bewegungskennzahlen(j, dt.date(2026, 9, 1))["zugaenge"] == 1


def test_ohne_buchungsdatum_wird_abgewiesen():
    """Der Ledger traegt kein Buchungsdatum. Wer ihn hineingibt, bekommt
    eine Meldung und nicht stillschweigend die alte, lueckenhafte
    Zaehlung auf dem Wirkungstag."""
    j = _journal([(1, "ZUG", "2026-09-01", "2026-09-01")]).drop(
        columns=["buchungsdatum"])
    with pytest.raises(ValueError, match="buchungsdatum"):
        bewegungskennzahlen(j, dt.date(2026, 9, 1))
