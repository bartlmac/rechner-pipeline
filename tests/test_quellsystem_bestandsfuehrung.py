"""Die Bestandsfuehrung der Quelle: Verkauf, Vorfaelle, Journal.

Der erste Baldrian-Lauf hatte einen Lieferungsdefekt: KEIN Vertrag trug
mehr als EINEN Geschaeftsvorfall (165 auf 500 — keine Dynamikserie, kein
Vertrag mit Erhoehung UND Beitragsfreistellung, erst recht keiner mit
Erhoehung und Herabsetzung). Diese Tests halten fest, dass die neue
Fuehrung genau das liefert — und dass die Konventionen der Quelle
wirklich anders sind als die des Zielsystems, nicht nur behauptet.

Knoten: klv
"""

from __future__ import annotations

import collections
import datetime as dt
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.bestandsfuehrung import (  # noqa: E402
    Bestandsfuehrung,
    Police,
    Scheibe,
    lauf,
)
from quellsystem.konventionen import excel_round  # noqa: E402

SEED = 20260831
STICHTAG = dt.date(2026, 1, 1)


@pytest.fixture(scope="module")
def buch():
    return lauf(SEED, STICHTAG)


def test_derselbe_seed_ergibt_dasselbe_journal(buch):
    """Determinismus ist die Eintrittskarte fuer reproduzierbare Lieferungen."""
    nochmal = lauf(SEED, STICHTAG)
    assert [
        (b.polnr, b.datum, b.art, b.betrag, b.scheibe) for b in buch.journal
    ] == [
        (b.polnr, b.datum, b.art, b.betrag, b.scheibe) for b in nochmal.journal
    ]


def test_der_verkauf_peilt_tausend_policen_an(buch):
    """~1000 verkauft; der Bestand am Stichtag ist ERGEBNIS, keine Vorgabe."""
    verkauft = len(buch.policen)
    assert 850 <= verkauft <= 1150, verkauft
    aktiv = [p for p in buch.policen.values() if p.aktiv()]
    assert 0 < len(aktiv) < verkauft
    # Beide Zustaende der Lieferung kommen vor.
    stati = {p.vtg_status for p in aktiv}
    assert stati == {"AKT", "BFR"}


def test_der_alte_lieferungsdefekt_ist_tot(buch):
    """Mehrere Vorfaelle je Vertrag — in allen relevanten Kombinationen.

    Der Defekt: max. EIN GeVo je Vertrag. Jetzt muss es Vertraege mit
    langen Dynamikserien geben, mit Erhoehung UND Beitragsfreistellung,
    mit Erhoehung UND Herabsetzung — und mit Dynamik NACH der
    Herabsetzung (der Vertrag lebt weiter).
    """
    je = collections.Counter(
        b.polnr for b in buch.journal if b.art != "ZUG")
    assert max(je.values()) >= 5, "keine Dynamikserien — Defekt lebt"
    policen = buch.policen.values()
    erh_und_pex = sum(1 for p in policen
                      if len(p.scheiben) > 1 and p.vtg_status == "BFR")
    erh_und_red = sum(1 for p in policen
                      if len(p.scheiben) > 1 and p.herabsetzungen)
    erh_nach_red = sum(
        1 for p in policen if p.herabsetzungen
        and any(s.beginn > p.herabsetzungen[0][0] for s in p.scheiben[1:]))
    assert erh_und_pex > 50
    assert erh_und_red > 20
    assert erh_nach_red > 10


def test_vorfaelle_folgen_der_kalenderjahres_logik(buch):
    """Die Quelle bucht am 1. Januar — nicht am Vertragsjahrestag.

    Genau daraus entstehen spaeter unterjaehrige t_a der Lieferung: Der
    letzte exakte Rechenpunkt liegt am Vertragsjahrestag VOR dem Vorfall.
    """
    for b in buch.journal:
        if b.art == "ZUG":
            assert b.datum.day == 1
        else:
            assert (b.datum.month, b.datum.day) == (1, 1), b


def test_das_journal_ist_in_sich_konsistent(buch):
    """Nichts nach terminal, eine PEX je Police, Betraege centgenau."""
    terminal_ab: dict = {}
    pex_gesehen: set = set()
    for b in buch.journal:
        assert b.polnr not in terminal_ab, (
            f"Buchung {b.art} nach terminalem Vorfall fuer {b.polnr}")
        if b.art in ("STO", "TOD", "ABL"):
            terminal_ab[b.polnr] = b.datum
        if b.art == "PEX":
            assert b.polnr not in pex_gesehen, "zweite PEX je Police"
            pex_gesehen.add(b.polnr)
        assert b.betrag == excel_round(b.betrag, 2), b
        assert b.betrag >= 0.0
    zug = collections.Counter(
        b.polnr for b in buch.journal if b.art == "ZUG")
    assert set(zug.values()) == {1}, "genau ein Zugang je Police"


def test_stornoabzug_gilt_je_scheibe_nicht_je_vertrag():
    """Die Konvention ist messbar, nicht nur behauptet.

    Zwei kleine Dynamikscheiben: Die Untergrenze des Stornoabzugs (50)
    greift bei der Quelle je SCHEIBE, beim Zielsystem einmal je Vertrag.
    Der Quell-Rueckkaufswert liegt deshalb um rund zwei Untergrenzen
    UNTER dem vertragsweiten — genau die Differenz, die im
    Migrationsfall als Konventionsdifferenz (R_conv) auftauchen soll.
    """
    buch = Bestandsfuehrung(1)
    beginn = dt.date(2016, 1, 1)
    police = Police(
        polnr=1, status="Nichtraucher", tarifart="Einzel", zw=12,
        beginn=beginn,
        scheiben=[
            Scheibe(nr=0, beginn=beginn, x=40, n=20, t=20, vs=100_000.0),
            Scheibe(nr=1, beginn=dt.date(2018, 1, 1), x=42, n=18, t=18,
                    vs=5_000.0),
            Scheibe(nr=2, beginn=dt.date(2019, 1, 1), x=43, n=17, t=17,
                    vs=5_250.0),
        ],
    )
    stichtag = dt.date(2026, 1, 1)
    quelle = buch._bewertung(police, stichtag)["rkw_je_scheibe"]

    # Vertragsweite Kontrollrechnung von Hand: Reserven summieren, EINEN
    # Abzug auf den Gesamtwerten bilden.
    tarif = police.tarif
    mrv = drx = 0.0
    for s in police.scheiben:
        k = min((stichtag.year - s.beginn.year), s.n)
        zeile = s.rechnung(police.zw, tarif).verlaufszeile(k)
        mrv += zeile["kVx_MRV_H"]
        drx += zeile["kDRx_bpfl_F"]
    vs = police.gesamt_vs
    stoab_vertragsweit = min(
        tarif.stoab_max, max(tarif.stoab_min, tarif.stoab_satz * (vs - drx)))
    vertragsweit = max(0.0, mrv - stoab_vertragsweit)

    assert quelle < vertragsweit, "die Scheiben-Konvention muss KOSTEN"
    differenz = vertragsweit - quelle
    # Zwei zusaetzliche Untergrenzen (die kleinen Scheiben) minus den
    # anteiligen Satz-Abzug, den sie ohnehin truegen: grob zwei mal 50.
    assert 50.0 < differenz < 250.0, differenz
