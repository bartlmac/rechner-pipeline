"""Monatsbericht: Zeitraum, Vertragskonto, Quelle.

Der Monatsbericht hat drei Zusicherungen, die ihn erst zu einem
Monatsbericht machen, und alle drei sind schon einmal gebrochen gewesen:

1. Er nennt keinen Zeitraum ausser seinem eigenen. Ein Bericht, der
   zwoelf Monate zeigen soll und "Geschaeftsvorfaelle 1994 bis 2026"
   ueberschrieben ist, ist keiner.
2. Sein Vertragskonto schliesst — auch dann, wenn ein Ablauf zum
   Monatsersten erst am naechsten Werktag gebucht wird. Genau dieser
   Fall (Monatserster auf einem Wochenende) riss die Rechnung auf, als
   sie aus Vorfallzaehlungen gebildet wurde.
3. Seine Bestandszahlen sind die des festgeschriebenen Abschlusses, nicht
   eine Nachrechnung. Sonst widerspricht der Bericht der Tabelle, die ihn
   verlinkt.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
import re

import pandas as pd
import pytest

from rechner_pipeline.bestand import monatsbericht as mb

STICHTAG = dt.date(2026, 9, 1)


def _abschluss(stichtag: dt.date, policen, produkt: str = "klv") -> pd.DataFrame:
    """Ein Monatsabschluss mit den Spalten, die der Bericht liest."""
    return pd.DataFrame({
        "police_id": list(policen),
        "stichtag": pd.Timestamp(stichtag),
        "produkt": produkt,
        "tarif_generation": "TG2015",
        "status_code": "POL",
        "leistung": [1000.0] * len(policen),
        "deckungskapital": [500.0] * len(policen),
        "rueckkaufswert": [480.0] * len(policen),
        "korrekturschicht": [0.0] * len(policen),
        "vs_bfr": [0.0] * len(policen),
        "jahresbeitrag": [60.0] * len(policen),
    })


def _journal(zeilen) -> pd.DataFrame:
    """Tagesjournal aus (police, ereignis, wirkt, gebucht, art, betrag)."""
    return pd.DataFrame({
        "police_id": [z[0] for z in zeilen],
        "ereignis": [z[1] for z in zeilen],
        "status_date": [pd.Timestamp(z[2]) for z in zeilen],
        "buchungsdatum": [pd.Timestamp(z[3]) for z in zeilen],
        "betrag_art": [z[4] for z in zeilen],
        "betrag": [z[5] for z in zeilen],
    })


def _raster_abschluesse(policen_je_tag):
    return {tag: _abschluss(tag, policen)
            for tag, policen in policen_je_tag.items()}


def _volles_raster(bestand=range(1, 11)):
    """Zu jedem Punkt des Rasters ein Abschluss mit demselben Bestand."""
    return {tag: _abschluss(tag, bestand)
            for tag in mb.monatsraster(STICHTAG)}


def _text(html: str) -> str:
    """Der Bericht ohne Grafiken und Auszeichnung — was ein Leser liest."""
    ohne_svg = re.sub(r"<svg.*?</svg>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", ohne_svg)


# --------------------------------------------------------------------------- #
# Raster
# --------------------------------------------------------------------------- #

def test_raster_gibt_eroeffnung_plus_zwoelf_monate():
    raster = mb.monatsraster(STICHTAG, 12)
    assert len(raster) == 13, "zwoelf Perioden brauchen dreizehn Punkte"
    assert raster[-1] == STICHTAG
    assert raster[0] == dt.date(2025, 9, 1)
    assert raster == sorted(raster)
    assert all(t.day == 1 for t in raster)


def test_raster_geht_ueber_den_jahreswechsel():
    raster = mb.monatsraster(dt.date(2026, 2, 1), 3)
    assert raster == [dt.date(2025, 11, 1), dt.date(2025, 12, 1),
                      dt.date(2026, 1, 1), dt.date(2026, 2, 1)]


# --------------------------------------------------------------------------- #
# Der Berichtszeitraum ist der Berichtszeitraum
# --------------------------------------------------------------------------- #

def test_bericht_nennt_keinen_zeitraum_ausser_seinem_eigenen():
    """Die Regression: Alte Geschaeftsvorfaelle duerfen nicht durchschlagen.

    Journal und Abschluesse tragen Geschichte bis 1994 zurueck. Im Bericht
    darf davon nichts stehen — weder als Ueberschrift noch als Achse noch
    als Summenzeile. Erlaubt sind nur die Jahre des Zeitraums und das Jahr
    des Fuehrungsstands im Kopf.
    """
    journal = _journal([
        (1, "ZUG", "1994-07-01", "1994-07-01", "VS", 1000.0),
        (2, "ZUG", "2003-05-01", "2003-05-01", "VS", 1000.0),
        (3, "ABL", "2011-01-01", "2011-01-03", "Ablaufleistung", 900.0),
        (11, "ZUG", "2026-09-01", "2026-08-20", "VS", 1000.0),
    ])
    abschluesse = _volles_raster()
    abschluesse[STICHTAG] = _abschluss(STICHTAG, list(range(1, 12)))
    html = mb.render_html(abschluesse, journal, STICHTAG,
                          stand=dt.date(2026, 9, 20))
    jahre = set(re.findall(r"\b(19\d\d|20\d\d)\b", _text(html)))
    assert jahre <= {"2025", "2026"}, f"fremde Jahre im Bericht: {sorted(jahre)}"
    # Die Grafiken sind hier nicht mitgeprueft (Schriften stehen als Pfade
    # im SVG, Koordinaten lesen sich wie Jahreszahlen). Ihre Achsen koennen
    # aber nichts anderes zeigen, weil ihre einzige Eingabe die Reihe des
    # Rasters ist -- das haelt der Test darunter fest.
    raster = {t.isoformat() for t in mb.monatsraster(STICHTAG)}
    assert {r["stichtag"] for r
            in mb.ereignisse_je_monat(journal, mb.monatsraster(STICHTAG))} <= raster
    # Und die Summentabellen zaehlen nur den Zeitraum. Ohne diese Zusicherung
    # bliebe der Test gruen, wenn die Summen ueber den ganzen Ledger liefen:
    # Die Tabelle nennt Ereignis, Anzahl und Betrag -- kein Jahr, an dem eine
    # zu weit gefasste Periode auffiele. (Mutationsprobe 2026-09-20.)
    zeitraum = mb.ereignis_summen_periode(
        journal, dt.date(2025, 9, 1), STICHTAG)
    assert {(s["ereignis"], s["anzahl"]) for s in zeitraum} == {("ZUG", 1)}, (
        "nur der Zugang zum 2026-09-01 liegt im Zeitraum; die Zugaenge von "
        "1994 und 2003 und der Ablauf von 2011 duerfen nicht mitgezaehlt werden")
    monat = mb.ereignis_summen_periode(journal, dt.date(2026, 8, 1), STICHTAG)
    assert {(s["ereignis"], s["anzahl"]) for s in monat} == {("ZUG", 1)}


def test_ueberschriften_nennen_den_monat_und_den_zeitraum():
    html = mb.render_html(_volles_raster(), _journal([]), STICHTAG)
    assert "<h2>Bestand am 2026-09-01</h2>" in html
    assert "Der Berichtsmonat: 2026-08-01 bis 2026-09-01" in html
    assert "Die letzten 12 Monate" in html


# --------------------------------------------------------------------------- #
# Das Vertragskonto
# --------------------------------------------------------------------------- #

def _konto_zeilen(html: str, ueberschrift: str):
    """Die Zeilen des Vertragskontos unter einer Ueberschrift."""
    ab = html.index(ueberschrift)
    tabelle = html[ab:html.index("</table>", ab)]
    paare = re.findall(
        r"<td>([^<]*)</td><td class='num'>([^<]*)</td>", tabelle)
    return [(name, wert) for name, wert in paare]


def test_vertragskonto_schliesst_trotz_spaet_gebuchtem_ablauf():
    """Die Mutation genau auf den blinden Fleck.

    Police 9 laeuft zum 2026-08-01 ab (ein Samstag) und wird am Montag
    gebucht. Der Abschluss zum 1.8. fuehrt sie schon nicht mehr — ein
    Ablauf tritt ein, ob er gebucht ist oder nicht. Das Journal meldet
    den Vorfall aber erst im September.

    Wer das Konto aus Vorfallzaehlungen bildet, bekommt hier einen
    Abgang zu viel und eine Differenz von eins. Das Konto muss trotzdem
    aufgehen, weil es die beiden Abschluesse abgleicht und nicht die
    Buchungen zaehlt.
    """
    raster = mb.monatsraster(STICHTAG)
    abschluesse = {t: _abschluss(t, range(1, 11)) for t in raster[:-2]}
    abschluesse[dt.date(2026, 8, 1)] = _abschluss(
        dt.date(2026, 8, 1), [p for p in range(1, 11) if p != 9])
    abschluesse[STICHTAG] = _abschluss(
        STICHTAG, [p for p in range(1, 11) if p != 9])
    journal = _journal([
        (9, "ABL", "2026-08-01", "2026-08-03", "Ablaufleistung", 900.0),
    ])
    html = mb.render_html(abschluesse, journal, STICHTAG)
    zeilen = _konto_zeilen(html, "Der Berichtsmonat")
    assert zeilen[0] == ("Bestand am 2026-08-01", "9")
    assert zeilen[-1] == ("Bestand am 2026-09-01", "9")
    # Kein Abgang: Police 9 war am 1.8. schon nicht mehr im Bestand.
    assert len(zeilen) == 2, f"unerwartete Bewegungszeilen: {zeilen}"
    assert "Abweichung" not in html


def test_vertragskonto_nennt_jeden_bewegten_vertrag_mit_seinem_vorfall():
    raster = mb.monatsraster(STICHTAG)
    abschluesse = {t: _abschluss(t, range(1, 11)) for t in raster[:-1]}
    # 11 kommt hinzu, 1 storniert, 2 laeuft ab.
    abschluesse[STICHTAG] = _abschluss(STICHTAG, [3, 4, 5, 6, 7, 8, 9, 10, 11])
    journal = _journal([
        (11, "ZUG", "2026-09-01", "2026-08-20", "VS", 1000.0),
        (11, "ZUG", "2026-09-01", "2026-08-20", "BJB", 60.0),
        (1, "STO", "2026-08-15", "2026-08-17", "RKW", 480.0),
        (2, "ABL", "2026-09-01", "2026-09-01", "Ablaufleistung", 900.0),
    ])
    html = mb.render_html(abschluesse, journal, STICHTAG)
    zeilen = _konto_zeilen(html, "Der Berichtsmonat")
    assert zeilen[0] == ("Bestand am 2026-08-01", "10")
    assert ("Neuzugang (ZUG)", "+1") in zeilen
    assert ("Storno (STO)", "−1") in zeilen
    assert ("Ablauf (ABL)", "−1") in zeilen
    assert zeilen[-1] == ("Bestand am 2026-09-01", "9")


def test_vertragskonto_ohne_eroeffnungsabschluss_erfindet_keinen():
    abschluesse = {STICHTAG: _abschluss(STICHTAG, range(1, 11))}
    html = mb.render_html(abschluesse, _journal([]), STICHTAG)
    assert "liegt kein Monatsabschluss vor" in html
    assert "Bestand am 2025-09-01" not in html


# --------------------------------------------------------------------------- #
# Die Quelle ist der Abschluss
# --------------------------------------------------------------------------- #

def test_bestandszahl_ist_die_des_abschlusses_nicht_nachgerechnet():
    """Der Abschluss gilt, auch wenn das Journal etwas anderes nahelegt.

    Das Journal kennt hier einen Zugang, den der Abschluss nicht fuehrt
    (er war am Stichtag noch nicht gebucht). Die Kopfzahl muss die des
    Abschlusses sein — sonst weicht der Bericht von der Tabelle ab, die
    ihn verlinkt.
    """
    abschluesse = _volles_raster()
    journal = _journal([
        (99, "ZUG", "2026-09-01", "2026-09-30", "VS", 1000.0),
    ])
    html = mb.render_html(abschluesse, journal, STICHTAG)
    assert "<b>Verträge in Kraft:</b> 10" in html


def test_ohne_abschluss_zum_stichtag_kein_bericht():
    raster = mb.monatsraster(STICHTAG)
    abschluesse = {t: _abschluss(t, range(1, 11)) for t in raster[:-1]}
    with pytest.raises(ValueError, match="fehlt der Monatsabschluss"):
        mb.render_html(abschluesse, _journal([]), STICHTAG)


def test_journal_ohne_buchungsdatum_wird_abgewiesen():
    """Der Ledger traegt die Spalte nicht — er darf hier nicht durchrutschen."""
    ledger = _journal([
        (1, "ZUG", "2026-09-01", "2026-09-01", "VS", 1000.0),
    ]).drop(columns=["buchungsdatum"])
    with pytest.raises(ValueError, match="buchungsdatum"):
        mb.render_html(_volles_raster(), ledger, STICHTAG)


# --------------------------------------------------------------------------- #
# Zaehlung
# --------------------------------------------------------------------------- #

def test_ereignisse_je_monat_zaehlt_vorfaelle_nicht_buchungszeilen():
    journal = _journal([
        (1, "ZUG", "2026-09-01", "2026-08-20", "VS", 1000.0),
        (1, "ZUG", "2026-09-01", "2026-08-20", "BJB", 60.0),
        (2, "ZUG", "2026-09-01", "2026-08-21", "VS", 1000.0),
    ])
    reihe = mb.ereignisse_je_monat(journal, mb.monatsraster(STICHTAG))
    assert len(reihe) == 12, "zu jeder Periode eine Zeile, zur Eroeffnung keine"
    letzte = reihe[-1]
    assert letzte["stichtag"] == "2026-09-01"
    assert letzte["ZUG"] == 2, "drei Zeilen, aber zwei Vorfaelle"
    assert letzte["zugaenge"] == 2


def test_periode_laeuft_auf_dem_sichtbarkeitstag():
    """Wirkungstag frueh, Buchungstag spaet: Der Vorfall gehoert in den
    Monat, in dem er sichtbar wurde."""
    journal = _journal([
        (1, "STO", "2026-07-20", "2026-08-03", "RKW", 480.0),
    ])
    reihe = {r["stichtag"]: r
             for r in mb.ereignisse_je_monat(journal, mb.monatsraster(STICHTAG))}
    assert reihe["2026-08-01"]["STO"] == 0, "am 1.8. war die Buchung noch nicht da"
    assert reihe["2026-09-01"]["STO"] == 1


def test_summen_trennen_die_bezugsgroessen():
    """Versicherungssumme und Jahresrente werden nie zusammengezaehlt."""
    journal = _journal([
        (1, "ZUG", "2026-08-15", "2026-08-15", "VS", 1000.0),
        (2, "ZUG", "2026-08-15", "2026-08-15", "BU_Jahresrente", 12000.0),
    ])
    summen = mb.ereignis_summen_periode(
        journal, dt.date(2026, 8, 1), STICHTAG)
    nach_art = {s["betrag_art"]: s for s in summen}
    assert nach_art["VS"]["summe_betrag"] == 1000.0
    assert nach_art["BU_Jahresrente"]["summe_betrag"] == 12000.0
    assert all(s["ereignis"] == "ZUG" for s in summen)


def test_abschluss_kennzahlen_trennen_die_versicherungsarten():
    gemischt = pd.concat([
        _abschluss(STICHTAG, [1, 2], produkt="klv"),
        _abschluss(STICHTAG, [3], produkt="bu"),
    ], ignore_index=True)
    gruppen = [{"produkt": "klv", "leistung_label": "Versicherungssumme",
                "titel": "Kapitalversicherung"},
               {"produkt": "bu", "leistung_label": "versicherte Jahresrente",
                "titel": "Berufsunfähigkeit"}]
    werte = mb.abschluss_kennzahlen(gemischt, gruppen)
    assert werte["vertraege"] == 3
    assert werte["leistung_klv"] == 2000.0
    assert werte["leistung_bu"] == 1000.0
    assert "leistung" not in werte, "keine Summe ueber nicht addierbare Groessen"
