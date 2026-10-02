"""Beitragsherabsetzung und Teilkuendigung im simulierten Bestand der PLV.

Auftrag des Maintainers (2026-10-01): "Wir brauchen fuer PLV sowohl
Teilauszahlung als auch Herabsetzung als generierte GeVos, ohne das wirkt
das kuenstlich." Bis dahin standen beide Raten in den Configs der PLV auf
der Vorgabe 0; der Bestand, auf dem Fall 3 aufsetzt, enthielt keinen
einzigen dieser Vorgaenge, obwohl eine Migration sie in jedem gewachsenen
Bestand antrifft.

Die Annahmen (``[annahmen]`` in ``configs/bestand_klv.toml`` und
``configs/bestand_gesamt.toml``) sind Annahmen der Vorfuehrung, keine
Tarifgroessen:

* ``herabsetzung = { a = 0.008 }`` — 0,8 Prozent je Jahr der
  beitragspflichtigen Vertraege; ``red_anteil = 0.6`` ist der FORTGEFUEHRTE
  Beitragsanteil (Beitrag auf 60 Prozent gesenkt);
* ``teilkuendigung = { a = 0.005 }`` — 0,5 Prozent je Jahr der Vertraege
  vor dem Ablauf; ``tk_anteil = 0.7`` ist der FORTGEFUEHRTE Summenanteil
  (30 Prozent der Grundversicherung gekuendigt und ausgezahlt).

Geprueft wird auf dem ECHTEN Config-Bestand (Betriebsbeginn 1994-07-01,
Tagesstrom bis zum Horizont, derselbe Weg wie der Tageslauf), gegen dieselbe
Welt mit beiden Raten auf null:

* (a) Zeuge: Jeder Vertrag ohne Herabsetzung oder Teilkuendigung ist
  bitgleich; an einem betroffenen Vertrag bleibt die Folge der anderen
  Ereignisse gleich, und ihre Betraege aendern sich erst ab dem Vorgang —
  keine Ziehung eines anderen Stroms verschiebt sich.
* (b) Die Ziehungen, unabhaengig nachgerechnet: aus den beiden Stroemen des
  Registers und den Grenzen des Tarifplans KLV 7.2, ohne die Engine. Dazu
  Anzahl und Verteilung je Kalenderjahr.
* (c) Die Leser: Bewegungskonto mit geschlossener Identitaet und eigener
  Position ``veraenderung_teilkuendigung``, gegen eine Kontrollrechnung.
  Tageslauf, P-B1, Abschluss, Bericht und Seite prueft
  ``test_betrieb_plv_vorgaenge``.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text, load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.kennzahlen import bewegungskonto
from rechner_pipeline.bestand.zufallsstroeme import STROEME
from rechner_pipeline.betrieb.neugeschaeft import neugeschaeft_zwischen
from rechner_pipeline.models.bestand import leerer_stamm

REPO_ROOT = Path(__file__).resolve().parents[1]
GESAMT = REPO_ROOT / "configs" / "bestand_gesamt.toml"
KLV = REPO_ROOT / "configs" / "bestand_klv.toml"
BU = REPO_ROOT / "configs" / "bestand_bu.toml"
#: Fester Horizont: die Messung des Auftrags (2026-10-01).
HORIZONT = dt.date(2026, 10, 1)

RED_RATE, RED_ANTEIL = 0.008, 0.6
TK_RATE, TK_ANTEIL = 0.005, 0.7

_RED_ZEILE = "herabsetzung = { a = 0.008, b = 0.0 }"
_TK_ZEILE = "teilkuendigung = { a = 0.005, b = 0.0 }"


def _ohne_raten(text: str) -> str:
    """Dieselbe Config mit beiden Raten auf null — sonst Byte fuer Byte gleich."""
    assert text.count(_RED_ZEILE) == 1 and text.count(_TK_ZEILE) == 1, (
        "die Config traegt die Raten der Vorfuehrung nicht")
    return (text.replace(_RED_ZEILE, "herabsetzung = { a = 0.0, b = 0.0 }")
                .replace(_TK_ZEILE, "teilkuendigung = { a = 0.0, b = 0.0 }"))


def _welt(text: str):
    config = config_aus_text(text)
    zugaenge = neugeschaeft_zwischen(config, config.tagesbetrieb.betriebsbeginn, HORIZONT)
    return config, fortschreiben(leerer_stamm(), config, HORIZONT, zugaenge=zugaenge)


@pytest.fixture(scope="module")
def welten():
    text = GESAMT.read_text(encoding="utf-8")
    config, mit = _welt(text)
    _, ohne = _welt(_ohne_raten(text))
    return config, mit, ohne


def _vorgaenge(ledger: pd.DataFrame) -> pd.DataFrame:
    """Je Vorgang EINE Zeile (die Summenzeile), nicht je Buchung."""
    return ledger[((ledger["ereignis"] == "RED") & (ledger["betrag_art"] == "VS_herabsetzung"))
                  | ((ledger["ereignis"] == "TKU")
                     & (ledger["betrag_art"] == "VS_teilkuendigung"))]


# --------------------------------------------------------------------------- #
# Die eingetragenen Annahmen
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("pfad", [KLV, GESAMT], ids=["klv", "gesamt"])
def test_die_plv_configs_tragen_beide_vorgaenge(pfad):
    """Die Werte in der Bedeutung des Codes: ``a`` ist die Jahresrate
    (``b = 0``: keine Rechnungsgrundlage), ``red_anteil`` und ``tk_anteil``
    sind die FORTGEFUEHRTEN Anteile (``config.Annahmen``). 30 Prozent
    gekuendigt heisst ``tk_anteil = 0.7``, nicht 0.3."""
    annahmen = load_config(pfad).annahmen
    assert (annahmen.herabsetzung.a, annahmen.herabsetzung.b) == (RED_RATE, 0.0)
    assert annahmen.red_anteil == RED_ANTEIL
    assert (annahmen.teilkuendigung.a, annahmen.teilkuendigung.b) == (TK_RATE, 0.0)
    assert annahmen.tk_anteil == TK_ANTEIL
    # Die Rate wirkt als Schwelle, ohne Rechnungsgrundlage erster Ordnung.
    assert annahmen.herabsetzung(0.3) == RED_RATE
    assert annahmen.teilkuendigung(0.3) == TK_RATE


def test_die_bu_config_traegt_keinen_der_vorgaenge():
    """Das BU-Beispielprodukt kennt weder Herabsetzung noch Teilkuendigung
    (wie Storno und Beitragsfreistellung); die BU-Engine zieht sie nicht.
    Eine Rate dort waere eine Annahme ohne Wirkung — sie steht nicht da."""
    annahmen = load_config(BU).annahmen
    assert annahmen.herabsetzung.a == 0.0 and annahmen.teilkuendigung.a == 0.0
    assert annahmen.red_anteil == 0.0 and annahmen.tk_anteil == 0.0


# --------------------------------------------------------------------------- #
# (a) Zeuge: kein anderer Strom verschiebt sich
# --------------------------------------------------------------------------- #

def test_ohne_vorgang_bitgleich_mit_vorgang_nur_ab_dem_vorgang_verschieden(welten):
    """Mutationsprobe: in der Engine die Herabsetzung nur bei Rate > 0 aus
    dem Hauptstrom ziehen (``annahmen.herabsetzung.a > 0 and rng.random()
    < ...``) -> die Policen ohne Vorgang sind nicht mehr bitgleich, rot.
    Eine Aenderung, die BEIDE Welten gleich trifft, sieht dieser Vergleich
    nicht; dafuer steht der Fingerabdruck unten."""
    _, mit, ohne = welten
    pd.testing.assert_frame_equal(mit.zugaenge, ohne.zugaenge)
    pd.testing.assert_frame_equal(mit.historie, ohne.historie)
    assert len(_vorgaenge(ohne.ledger)) == 0
    vorgang = _vorgaenge(mit.ledger).groupby("police_id")["vertragsjahr"].min()
    betroffen = set(vorgang.index)

    def ohne_betroffene(df):
        return df[~df["police_id"].isin(betroffen)].reset_index(drop=True)

    pd.testing.assert_frame_equal(ohne_betroffene(mit.ledger), ohne_betroffene(ohne.ledger))
    pd.testing.assert_frame_equal(ohne_betroffene(mit.scheiben), ohne_betroffene(ohne.scheiben))

    # An den betroffenen Policen: dieselbe Folge der anderen Ereignisse,
    # dieselben Betraege vor dem Vorgangsjahr; danach bewegt sich, was von
    # der Summe abhaengt (spaetere Erhoehung, Storno, Tod, Ablauf, PEX).
    geaendert = Counter()
    for pid, j0 in vorgang.items():
        a = ohne.ledger[ohne.ledger["police_id"] == pid]
        b = mit.ledger[(mit.ledger["police_id"] == pid)
                       & ~mit.ledger["ereignis"].isin(["RED", "TKU"])]
        assert list(zip(a["ereignis"], a["vertragsjahr"], a["betrag_art"])) == \
            list(zip(b["ereignis"], b["vertragsjahr"], b["betrag_art"])), pid
        verschieden = a["betrag"].to_numpy() != b["betrag"].to_numpy()
        assert not (verschieden & (a["vertragsjahr"].to_numpy() < j0)).any(), pid
        geaendert.update(a["ereignis"].to_numpy()[verschieden])
    # Gemessen auf dem Stand des Entscheids vom 2026-10-01 (beliebig viele
    # Vorgaenge, Teilkuendigung nach der Beitragsfreistellung): 283 Policen mit
    # Vorgang (275 auf 6046922 — dazu 7 mit Teilkuendigung allein nach der
    # Beitragsfreistellung und 1 mit erstem Vorgang erst nach einem vorher
    # verworfenen); bewegt sind nur Betraege ab dem ersten Vorgang.
    assert len(betroffen) == ANZAHL_BETROFFEN
    assert dict(geaendert) == GEAENDERT


#: Policen mit Vorgang und die Betragsaenderungen ab dem Vorgang in der Welt
#: MIT Raten (Stand 2026-10-01, Vorgangsfolge; siehe Test oben).
ANZAHL_BETROFFEN = 283
GEAENDERT = {"ERH": 1198, "STO": 52, "PEX": 13, "ABL": 107, "TOD": 11}


#: Fingerabdruck der Welt OHNE die beiden Raten, gemessen auf dem Stand
#: 3773224 mit der damaligen Config (ohne jede Zeile zu Herabsetzung und
#: Teilkuendigung): Tabelle -> (SHA-256 ueber ``hash_pandas_object`` mit auf
#: sechs Stellen gerundeten Gleitkommaspalten, Zeilenzahl).
FINGERABDRUCK_OHNE_RATEN = {
    "ledger": ("1d8bf7887b130b9c686bb401f33311a79521bf03195a222920d346bddf877a12", 22192),
    "historie": ("0f4df0bbf790003da58a105d2b39a9abfa9a5b6513ce521fd67560d0eeae9868", 1882),
    "scheiben": ("be5402f1d9aca0db0c93eeacf5f14b61b4f6b0479388c76eebea5e0c896d362f", 6822),
    "zugaenge": ("126c00d5f6e42deab7726304f81449ceb91031c4b726685e921423ab0d456e8e", 3333),
}


def _fingerabdruck(df: pd.DataFrame) -> str:
    import hashlib

    d = df.copy()
    for spalte in d.columns:
        if d[spalte].dtype.kind == "f":
            d[spalte] = d[spalte].round(6)
    return hashlib.sha256(
        pd.util.hash_pandas_object(d, index=False).values.tobytes()).hexdigest()


def test_die_welt_ohne_raten_ist_die_des_vorstands(welten):
    """Der zweite Zeuge, gegen einen FESTEN Stand: Der Vergleich oben haelt
    zwei Welten derselben Engine gegeneinander und ist blind fuer eine
    Aenderung, die beide gleich trifft (gemessen: die Herabsetzung aus dem
    Hauptstrom gezogen verschiebt beide Welten gleich, der Vergleich blieb
    gruen). Die Welt ohne Raten muss deshalb bitgleich die des Stands
    3773224 sein — dieselbe Config bis auf die neuen Annahmen, die bei Rate
    null nichts bewirken.

    Bewegt sich dieser Fingerabdruck, hat sich die Fortschreibung der
    Config-Welt geaendert: Ursache benennen, nicht nachziehen.

    Mutationsprobe: wie oben (``rng`` statt ``rng_red``) -> rot."""
    _, _, ohne = welten
    ist = {name: (_fingerabdruck(getattr(ohne, name)), len(getattr(ohne, name)))
           for name in FINGERABDRUCK_OHNE_RATEN}
    assert ist == FINGERABDRUCK_OHNE_RATEN


# --------------------------------------------------------------------------- #
# (b) Die Ziehungen, unabhaengig nachgerechnet
# --------------------------------------------------------------------------- #

def _jahr_ab(start: pd.Timestamp, jahre: int) -> dt.date:
    return dt.date(start.year + jahre, start.month, 1)


def test_die_ziehungen_folgen_den_grenzen_des_tarifplans(welten):
    """Je Vertrag die beiden Stroeme aus dem Register, chronologisch, mit
    den Grenzen aus Tarifplan KLV 7.1 bis 7.3 — ohne die Engine:

    * Herabsetzung fuer ``0 < Jahr < t`` eines beitragspflichtigen Vertrags
      (nicht im Jahr der Beitragsfreistellung und nicht danach);
    * Teilkuendigung fuer ``0 < Jahr < n``, auch nach der
      Beitragsfreistellung (im Jahr der Freistellung nach ihr);
    * beliebig viele Vorgaenge je Vertrag (Entscheid 2026-10-01): JEDER
      gezogene wird gebucht.

    Abgang (Tod, Storno) und Beitragsfreistellung kommen aus dem
    Hauptstrom der Welt OHNE Raten — sie haengen nicht von den neuen
    Stroemen ab (Zeuge oben).

    Mutationsproben: die Teilkuendigung nur vor dem Beitragsende ziehen
    (``j + 1 < t`` statt ``j + 1 < n``) -> die Teilkuendigungen nach dem
    Beitragsende fehlen, rot; nach der Beitragsfreistellung nicht mehr
    ziehen -> rot; nach dem ersten Vorgang verwerfen -> rot."""
    config, mit, ohne = welten
    seed = config.seed
    stamm = mit.zugaenge.set_index("police_id")
    led = ohne.ledger
    tod_sto = led[led["ereignis"].isin(["TOD", "STO"])].groupby("police_id")["vertragsjahr"].min()
    pex = led[led["ereignis"] == "PEX"].groupby("police_id")["vertragsjahr"].min()

    erwartet = set()
    zaehler = Counter()
    for pid, row in stamm.iterrows():
        if row["produkt"] != "klv":
            continue
        n, t = int(row["duration"]), int(row["premium_duration"])
        start = pd.Timestamp(row["insurance_start"])
        rr = np.random.Generator(np.random.PCG64(
            np.random.SeedSequence([seed, STROEME["herabsetzung"], int(pid)])))
        rt = np.random.Generator(np.random.PCG64(
            np.random.SeedSequence([seed, STROEME["teilkuendigung"], int(pid)])))
        for jahr in range(1, n + 1):
            if _jahr_ab(start, jahr) > HORIZONT:
                break
            if pid in tod_sto.index and tod_sto[pid] <= jahr:
                break
            beitragsfrei = pid in pex.index and pex[pid] <= jahr
            if not beitragsfrei and jahr < t and rr.random() < RED_RATE:
                erwartet.add((int(pid), "RED", jahr))
            if jahr < n and rt.random() < TK_RATE:
                erwartet.add((int(pid), "TKU", jahr))
                zaehler["TKU nach PEX" if beitragsfrei else
                        "TKU nach t" if jahr >= t else "TKU vor t"] += 1

    v = _vorgaenge(mit.ledger)
    ist = {(int(p), str(e), int(j)) for p, e, j in
           zip(v["police_id"], v["ereignis"], v["vertragsjahr"])}
    assert ist == erwartet
    je_police = Counter(p for p, _, _ in ist)
    zaehler["Policen mit mehreren Vorgaengen"] = sum(1 for k in je_police.values() if k > 1)
    zaehler["RED"] = sum(1 for _, e, _ in ist if e == "RED")
    # Die Grenzen werden im Config-Bestand tatsaechlich getroffen — sonst
    # pruefte dieser Test sie nicht (Positivkontrolle). Gemessen 2026-10-01.
    assert dict(zaehler) == ZIEHUNGEN, dict(zaehler)
    t_je = v["police_id"].map(stamm["premium_duration"])
    red = v[v["ereignis"] == "RED"]
    assert (red["vertragsjahr"] < t_je[red.index]).all()
    # Die BU zieht keinen der beiden Vorgaenge.
    assert set(stamm.loc[sorted({p for p, _, _ in ist}), "produkt"]) == {"klv"}


#: Die Zaehler der Ziehungen in der Welt mit Raten (Stand 2026-10-01).
ZIEHUNGEN = {"TKU vor t": 108, "TKU nach t": 9, "TKU nach PEX": 9,
             "Policen mit mehreren Vorgaengen": 19, "RED": 178}


def test_vorgaenge_je_kalenderjahr_im_verhaeltnis_zum_bestand(welten):
    """Plausibilitaet: Seit 1997 traegt jedes Kalenderjahr mindestens eine
    Herabsetzung und eine Teilkuendigung, und die beobachtete Haeufigkeit
    liegt bei der Annahme. Bezugsgroessen am 1.1. (Naeherung): fuer die
    Herabsetzung die beitragspflichtigen Vertraege vor dem Beitragsende,
    fuer die Teilkuendigung alle Vertraege in Kraft. Die Quote liegt unter
    der Rate, weil beitragsfreie und schon herabgesetzte Vertraege nicht
    mehr gezaehlt werden duerfen und die Naeherung sie mitzaehlt."""
    _, mit, _ = welten
    stamm = mit.zugaenge
    klv = stamm[stamm["produkt"] == "klv"].copy()
    led = mit.ledger
    abgang = led[led["ereignis"].isin(["STO", "TOD", "ABL"])].groupby("police_id")["status_date"].min()
    pex = led[led["ereignis"] == "PEX"].groupby("police_id")["status_date"].min()
    klv["abgang"] = klv["police_id"].map(abgang)
    klv["pex"] = klv["police_id"].map(pex)
    v = _vorgaenge(led).copy()
    v["kj"] = v["status_date"].dt.year
    bp_jahre = ik_jahre = 0
    for kj in range(1997, HORIZONT.year + 1):
        stichtag = pd.Timestamp(kj, 1, 1)
        in_kraft = klv[(klv["insurance_start"] < stichtag) & ~(klv["abgang"] <= stichtag)]
        bp = in_kraft[~(in_kraft["pex"] <= stichtag)
                      & (in_kraft["payment_end"] > stichtag)]
        bp_jahre += len(bp)
        ik_jahre += len(in_kraft)
        im_jahr = Counter(v.loc[v["kj"] == kj, "ereignis"])
        assert im_jahr["RED"] >= 1 and im_jahr["TKU"] >= 1, (kj, dict(im_jahr))
    quote_red = int((v["ereignis"] == "RED").sum()) / bp_jahre
    quote_tku = int((v["ereignis"] == "TKU").sum()) / ik_jahre
    assert 0.5 * RED_RATE < quote_red <= RED_RATE, quote_red
    assert 0.5 * TK_RATE < quote_tku <= TK_RATE, quote_tku


# --------------------------------------------------------------------------- #
# (c) Bewegungskonto: eigene Position, geschlossene Identitaet
# --------------------------------------------------------------------------- #

def test_bewegungskonto_fuehrt_beide_vorgaenge_mit_geschlossener_identitaet(welten):
    """Die Teilkuendigung kuerzt in den eigenen Tarifen JEDEN Baustein
    proportional (Tarifplan KLV 7.2, Entscheid 2026-10-01): Die Summe danach
    ist f mal die Summe davor — die Kontrollrechnung je Vorgang ist deshalb
    ``-(1 - f) / f`` mal der gebuchten neuen Summe, ohne Kern und ohne das
    Konto selbst; nach der Beitragsfreistellung im beitragsfreien Bestand. Die
    Herabsetzung bewegt die Summe nach dem Kern; hier zaehlt nur, dass sie
    ausgewiesen ist und die Identitaet schliesst.

    Mutationsprobe: in ``kennzahlen.bewegungskonto`` die Position
    ``veraenderung_teilkuendigung`` aus der Identitaet nehmen -> rot."""
    _, mit, _ = welten
    bestand = mit_zugaengen(leerer_stamm(), mit.zugaenge)
    konto = bewegungskonto(bestand, mit.historie, mit.ledger, mit.scheiben, bis=HORIZONT)
    assert konto and all(z["identitaet"]["bpfl"] == {"stueck": True, "summe": True}
                         and z["identitaet"]["bfr"] == {"stueck": True, "summe": True}
                         for z in konto)
    v = _vorgaenge(mit.ledger)
    pex = mit.ledger[mit.ledger["ereignis"] == "PEX"].set_index("police_id")["status_date"]
    tku = v[v["ereignis"] == "TKU"].copy()
    tku["bfr"] = [int(p) in pex.index and d >= pex.loc[int(p)]
                  for p, d in zip(tku["police_id"], tku["status_date"])]
    assert tku["bfr"].any(), "keine Teilkuendigung nach der Beitragsfreistellung"
    jahre_mit = 0
    for zeile in konto:
        jahr = zeile["jahr"]
        im_jahr = tku[(tku["status_date"] > pd.Timestamp(jahr, 1, 1))
                      & (tku["status_date"] <= pd.Timestamp(jahr + 1, 1, 1))]
        for track, teil in (("bpfl", im_jahr[~im_jahr["bfr"]]), ("bfr", im_jahr[im_jahr["bfr"]])):
            soll = -(1.0 - TK_ANTEIL) / TK_ANTEIL * float(teil["betrag"].sum())
            ist = zeile[track]["veraenderung_teilkuendigung"]
            assert ist["stueck"] == 0
            assert ist["summe"] == pytest.approx(soll, rel=1e-9, abs=1e-6), (jahr, track)
        red = zeile["bpfl"]["veraenderung_herabsetzung"]["summe"]
        if len(im_jahr):
            jahre_mit += 1
            assert red != 0.0, jahr
    assert jahre_mit >= 25
