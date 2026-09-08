"""Ein Vorfall bewegt eine Summe UND einen Beitrag (Bruttojahresbeitrag im Ledger).

Der Ledger buchte bisher nur Summen: Der Zugang die Versicherungssumme, die
Erhoehung die Erhoehungssumme, das Storno den Rueckkaufswert. Der
Bruttojahresbeitrag existierte im System, aber nur als gerechnete Groesse
der Bewertung — nicht als gebuchter Betrag. Auf der Seite stand deshalb
"Bruttojahresbeitrag: nicht im Tagesjournal", und das war die Wahrheit:
Neugeschaeft wird in Summe und Beitrag gemessen, das Journal konnte nur
das eine.

Jetzt bucht ein Zugang zwei Zeilen und eine Erhoehung ebenso: dieselbe
Police, derselbe Wirkungstag, zwei Groessen mit eigener Betragsart. Damit
traegt der Buchungsschluessel die Betragsart — ein Vorfall ist nicht mehr
eine Zeile, sondern eine Buchung mit mehreren Betraegen, wie in einer
Bestandsfuehrung ueblich.

Drei Dinge muessen dabei zusammen gelten, und jedes hat hier seinen Test:

* Der Beitrag folgt aus dem KERN dieser Police (VS mal Bxt), er wird nicht
  geliefert — P-B1 rechnet ihn nach wie jeden anderen Betrag (T20-04).
* Wer ueber den Vorfall summiert, nennt die Betragsart. Sonst liefe der
  Beitrag in die Summenbewegung, und die Bewegungs-Identitaet fiele.
* Wer Vorfaelle zaehlt, zaehlt Vorfaelle und nicht Zeilen.

Bekannte Asymmetrie: Die Abgaenge (Storno, Tod, Ablauf) und die
Beitragsfreistellung fuehren ihre Beitragswirkung noch nicht. Ein Abgang
nimmt einen Beitrag aus dem Bestand; das ist der naechste Schritt
derselben Sache und bewusst nicht Teil dieses Blocks.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.kennzahlen import bewegungskonto, ereignisse_je_jahr
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.models.bestand import BETRAG_ART_JE_EREIGNIS, validate_ledger

KLV = "configs/bestand_klv.toml"
REF = dt.date(2010, 1, 1)
BIS = dt.date(2030, 1, 1)


@pytest.fixture(scope="module")
def lauf():
    """Config, GESAMTbestand (Basis plus Neuzugaenge) und der Lauf."""
    from rechner_pipeline.bestand.ereignisse import mit_zugaengen

    config = load_config(KLV)
    basis = generate(config, bis=REF)
    erg = fortschreiben(basis, config, BIS, neuzugang_ab=REF)
    return config, mit_zugaengen(basis, erg.zugaenge), erg


# --------------------------------------------------------------------------- #
# Der Beitrag steht im Ledger
# --------------------------------------------------------------------------- #

def test_zugang_und_erhoehung_buchen_summe_und_beitrag(lauf):
    """Mutationsprobe: die BJB-Zeile in der Engine weglassen -> die Seite
    haette wieder nur eine Summe, und dieser Test faellt."""
    _, _, erg = lauf
    ledger = erg.ledger
    assert "BJB" in BETRAG_ART_JE_EREIGNIS["ZUG"]
    assert "BJB" in BETRAG_ART_JE_EREIGNIS["ERH"]
    for vorfall, summenart in (("ZUG", "VS"), ("ERH", "VS_erhoehung")):
        zeilen = ledger[ledger["ereignis"] == vorfall]
        assert len(zeilen), vorfall
        summe = zeilen[zeilen["betrag_art"] == summenart]
        beitrag = zeilen[zeilen["betrag_art"] == "BJB"]
        # Genau eine Zeile je Groesse und Vorfall:
        assert len(summe) == len(beitrag)
        assert len(summe) == zeilen[["police_id", "status_date"]].drop_duplicates().shape[0]
        # Der Beitrag ist eine andere Groesse als die Summe, nicht ihre Kopie:
        assert (beitrag["betrag"] > 0).all()
        paare = summe.merge(beitrag, on=["police_id", "status_date"],
                            suffixes=("_summe", "_beitrag"))
        assert len(paare) == len(summe)
        assert not (paare["betrag_beitrag"] == paare["betrag_summe"]).any()


def test_der_buchungsschluessel_traegt_die_betragsart(lauf):
    """Ohne die Art im Schluessel waeren die zwei Zeilen eines Vorfalls eine
    Doppelbuchung — der Ledger gaelte als nicht eindeutig.

    Mutationsprobe: betrag_art aus SCHLUESSEL nehmen -> das Tagesjournal
    verweigert den Ledger."""
    from rechner_pipeline.betrieb.tagesjournal import SCHLUESSEL

    _, basis, erg = lauf
    assert SCHLUESSEL == ("police_id", "ereignis", "status_date", "betrag_art")
    ledger = erg.ledger
    ohne_art = ledger[["police_id", "ereignis", "status_date"]]
    assert ohne_art.duplicated().any(), "ohne Art gaebe es keine zwei Zeichnungen"
    assert not ledger[list(SCHLUESSEL)].duplicated().any()
    assert validate_ledger(basis, ledger) == []


def test_p_b1_rechnet_den_gebuchten_beitrag_nach(lauf):
    """Der Beitrag wird hergeleitet, nicht geglaubt (Betragsbindung T20-04).

    Mutationsprobe: einen gebuchten Beitrag veraendern -> P-B1 findet ihn."""
    config, basis, erg = lauf
    assert pruefe_ledger_betraege(
        basis, erg.ledger, config, scheiben=erg.scheiben, historie=erg.historie) == []
    verfaelscht = erg.ledger.copy()
    ziel = verfaelscht.index[verfaelscht["betrag_art"] == "BJB"][0]
    verfaelscht.loc[ziel, "betrag"] = float(verfaelscht.loc[ziel, "betrag"]) * 1.1
    befunde = pruefe_ledger_betraege(
        basis, verfaelscht, config, scheiben=erg.scheiben, historie=erg.historie)
    assert any("nicht aus dem Kern" in b for b in befunde), befunde


# --------------------------------------------------------------------------- #
# Wer summiert, nennt die Art; wer zaehlt, zaehlt Vorfaelle
# --------------------------------------------------------------------------- #

def test_die_bewegungsrechnung_fuehrt_die_summe_nicht_den_beitrag(lauf):
    """Die Bewegungsrechnung ist eine Rechnung ueber Versicherungssummen.
    Liefe der Beitrag hinein, waere die Erhoehungsbewegung um ihn zu hoch —
    und die eingebaute Identitaet (Anfang + Zugang - Abgang = Ende) fiele.

    Mutationsprobe: den Art-Filter in kennzahlen.bewegungskonto entfernen
    -> die Identitaet bricht, und dieser Test faellt."""
    config, basis, erg = lauf
    konto = bewegungskonto(basis, erg.historie, erg.ledger, erg.scheiben, bis=BIS)
    assert konto, "kein Bewegungskonto"
    erh_summe = float(erg.ledger.loc[
        (erg.ledger["ereignis"] == "ERH")
        & (erg.ledger["betrag_art"] == "VS_erhoehung"), "betrag"].sum())
    aus_konto = sum(z["bpfl"]["zugang_erhoehung"]["summe"] for z in konto)
    assert aus_konto == pytest.approx(erh_summe)
    # Und der Beitrag ist NICHT darin:
    bjb_summe = float(erg.ledger.loc[erg.ledger["betrag_art"] == "BJB", "betrag"].sum())
    assert bjb_summe > 0
    assert aus_konto != pytest.approx(erh_summe + bjb_summe)


def test_gezaehlt_werden_vorfaelle_nicht_zeilen(lauf):
    """Ein Zugang mit Summe und Beitrag ist EIN Zugang.

    Mutationsprobe: in ereignisse_je_jahr wieder Zeilen zaehlen -> die
    Zahl der Zugaenge verdoppelt sich."""
    _, _, erg = lauf
    reihe = ereignisse_je_jahr(erg.ledger)
    gezaehlt = sum(r["ZUG"] for r in reihe)
    vorfaelle = erg.ledger[erg.ledger["ereignis"] == "ZUG"][
        ["police_id", "status_date"]].drop_duplicates()
    assert gezaehlt == len(vorfaelle)
    assert gezaehlt * 2 == int((erg.ledger["ereignis"] == "ZUG").sum())


# --------------------------------------------------------------------------- #
# Wer die Buchungen anzeigt, zeigt Verkaeufe — und die Ordnung ist der Schluessel
# --------------------------------------------------------------------------- #

def test_die_seite_meldet_verkaeufe_nicht_journalzeilen(tmp_path):
    """Die vierte Stelle derselben Bauform (Testat der merge-session): Die
    Seite zaehlte Journalzeilen. Seit ein Zugang zwei Zeilen bucht, haette
    sie doppelt so viel Neugeschaeft gemeldet, wie es Vertraege gab — eine
    Behauptung ueber Verkaeufe, die es nicht gab.

    Mutationsprobe: in seite.stand_modell wieder ueber die Zeilen zaehlen
    (size() statt der entdoppelten Vorfaelle) -> dieser Test faellt."""
    import datetime as _dt

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.betrieb.seite import stand_modell
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, _dt.date(2026, 2, 3))[0] == EXIT_OK
    modell = stand_modell(ablage)
    journal = read_portfolio(ablage.tagesjournal_pfad)
    woche_ab = pd.Timestamp(_dt.date(2026, 2, 3) - _dt.timedelta(days=6))
    neu = journal[(journal["herkunft"] == "neugeschaeft")
                  & (journal["buchungsdatum"] >= woche_ab)]
    vorfaelle = neu[["police_id", "status_date"]].drop_duplicates()
    assert len(vorfaelle) < len(neu), "ohne zwei Zeilen je Zugang prueft der Test nichts"
    assert set(neu["betrag_art"]) == {"VS", "BJB"}
    assert modell["neugeschaeft"]["woche_summe"] == len(vorfaelle)
    assert sum(modell["neugeschaeft"]["woche"].values()) == len(vorfaelle)


def test_die_ordnung_des_journals_ist_der_ganze_schluessel(lauf):
    """Das Journal wird gehasht (tagesjournal_sha256 in Protokollzeile und
    Stands-Paket). Eine Serialisierung, die nur bis zum Wirkungstag
    sortiert, erbt die Reihenfolge der zwei Zeilen eines Vorfalls vom
    Ledger, statt sie herzustellen.

    Mutationsprobe: betrag_art aus der Sortierliste nehmen -> derselbe
    Ledger in anderer Zeilenfolge ergibt ein anderes Journal."""
    from rechner_pipeline.betrieb.tagesjournal import mit_buchungstagen

    config, _, erg = lauf
    vorwaerts = mit_buchungstagen(config, erg.ledger)
    rueckwaerts = mit_buchungstagen(config, erg.ledger.iloc[::-1].reset_index(drop=True))
    pd.testing.assert_frame_equal(vorwaerts, rueckwaerts)


def test_wer_vorfaelle_meint_zaehlt_vorfaelle(tmp_path):
    """Das Inventar der Klasse (Empfehlung der merge-session): Nicht die
    Module, die RECHNEN, sind die Gefahr, sondern die, die ZAEHLEN.

    Ein Zugang bucht zwei Zeilen. Wer nach Vertraegen fragt — wie viele
    Zugaenge, wie viele Verkaeufe —, muss Vorfaelle zaehlen; wer nach
    Buchungen fragt, Zeilen. Beides gibt es, und beides muss beim Namen
    genannt sein. Geprueft an allen drei Zaehlstellen des Betriebs auf
    einem echten Lauf.

    Mutationsprobe: an einer der Stellen wieder ueber die Zeilen zaehlen
    -> die Zahl verdoppelt sich gegenueber den Vorfaellen."""
    import datetime as _dt

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.betrieb.seite import stand_modell
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, lies_protokoll, tageslauf
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, _dt.date(2026, 2, 3))[0] == EXIT_OK
    journal = read_portfolio(ablage.tagesjournal_pfad)
    vorfaelle = journal[["police_id", "ereignis", "status_date"]].drop_duplicates()
    assert len(vorfaelle) < len(journal), "ohne zwei Zeilen je Zugang prueft der Test nichts"
    zug_vorfaelle = int((vorfaelle["ereignis"] == "ZUG").sum())
    assert zug_vorfaelle * 2 == int((journal["ereignis"] == "ZUG").sum())

    # (1) Die Protokollzeile: Buchungen sind Zeilen, Ereignisse sind Vorfaelle.
    zeile = lies_protokoll(ablage.protokoll_pfad)[-1]
    tj = zeile["tagesjournal"]
    assert tj["zeilen_gesamt"] == len(journal)
    assert tj["je_ereignis"].get("ZUG", 0) <= zug_vorfaelle

    # (2) und (3) Die Seite: Wochenzahl und Ereignistafel zaehlen Vorfaelle.
    modell = stand_modell(ablage)
    assert modell["buchungen"]["je_ereignis"]["ZUG"] == zug_vorfaelle
    assert modell["neugeschaeft"]["woche_summe"] <= zug_vorfaelle
