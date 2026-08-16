"""Zustandsmodell-Engine: Handrechnungen, Selbsttest, Semi-Markov, Interface.

Knoten: klv, bu
"""

from __future__ import annotations

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kommutationskern.barwerte import Barwerte
from rechner_pipeline.kommutationskern.kommutation import fuer
from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern.konventionen import MAX_ALTER
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell, ZustandsBarwerte


def _zwei_zustaende(qx: float) -> Zustandsmodell:
    return Zustandsmodell(
        ("aktiv", "tot"), 0.0,
        lambda von, nach, alter, dauer: qx if (von, nach) == ("aktiv", "tot") else 0.0,
    )


# --------------------------------------------------------------------------- #
# Handrechnungen (2 Zustaende, Zins 0)
# --------------------------------------------------------------------------- #


def test_annuitaet_und_todesfall_gegen_handrechnung():
    modell = _zwei_zustaende(0.1)
    annuitaet = modell.barwert(
        "aktiv", 40, 3, zahlung_zustand=lambda z, j: 1.0 if z == "aktiv" else 0.0
    )
    assert annuitaet == pytest.approx(1.0 + 0.9 + 0.81, rel=1e-12)
    todesfall = modell.barwert(
        "aktiv", 40, 2, zahlung_uebergang=lambda von, nach, j: 1.0 if nach == "tot" else 0.0
    )
    assert todesfall == pytest.approx(0.1 + 0.9 * 0.1, rel=1e-12)


def test_diskontierung_wirkt_auf_zustands_und_uebergangszahlungen():
    modell = Zustandsmodell(
        ("aktiv", "tot"), 0.05,
        lambda von, nach, alter, dauer: 0.0,  # niemand stirbt
    )
    v = 1.0 / 1.05
    annuitaet = modell.barwert(
        "aktiv", 40, 3, zahlung_zustand=lambda z, j: 1.0 if z == "aktiv" else 0.0
    )
    assert annuitaet == pytest.approx(1.0 + v + v * v, rel=1e-12)


def test_vorwaerts_rueckwaerts_selbsttest():
    """Vorwaerts-Verteilung x Zahlungen == Rueckwaerts-Barwert (3 Zustaende)."""
    zustaende = ("aktiv", "krank", "tot")

    def uebergang(von, nach, alter, dauer):
        tabelle = {
            ("aktiv", "krank"): 0.15, ("aktiv", "tot"): 0.05,
            ("krank", "aktiv"): 0.30, ("krank", "tot"): 0.10,
        }
        return tabelle.get((von, nach), 0.0)

    zins = 0.03
    modell = Zustandsmodell(zustaende, zins, uebergang)
    horizont = 12

    def zz(zustand, jahr):
        return {"aktiv": 0.5, "krank": 1.0}.get(zustand, 0.0)

    def zu(von, nach, jahr):
        return 10.0 if nach == "tot" else 0.0

    rueckwaerts = modell.barwert("aktiv", 40, horizont, zz, zu)

    v = 1.0 / (1.0 + zins)
    vorwaerts = 0.0
    for jahr in range(horizont):
        verteilung = modell.verteilung("aktiv", 40, jahr)
        for (zustand, dauer), masse in verteilung.items():
            vorwaerts += (v ** jahr) * masse * zz(zustand, jahr)
            for nach, w in modell._wegzuege(zustand, 40 + jahr, dauer).items():
                if nach != zustand:
                    vorwaerts += (v ** (jahr + 1)) * masse * w * zu(zustand, nach, jahr)
    assert rueckwaerts == pytest.approx(vorwaerts, rel=1e-12)


# --------------------------------------------------------------------------- #
# Semi-Markov (Dauer-Abhaengigkeit via Zustandsraum-Erweiterung)
# --------------------------------------------------------------------------- #


def test_semi_markov_dauerabhaengige_genesung_gegen_handrechnung():
    """Genesung erst ab dem zweiten Krankheitsjahr (dauer >= 1)."""
    zustaende = ("aktiv", "krank", "tot")

    def uebergang(von, nach, alter, dauer):
        if (von, nach) == ("aktiv", "krank"):
            return 0.2
        if (von, nach) == ("aktiv", "tot"):
            return 0.05
        if (von, nach) == ("krank", "aktiv"):
            return 0.8 if dauer >= 1 else 0.0
        if (von, nach) == ("krank", "tot"):
            return 0.1
        return 0.0

    def krankengeld(zustand, jahr):
        return 1.0 if zustand == "krank" else 0.0

    semi = Zustandsmodell(zustaende, 0.0, uebergang, max_dauer=1)
    homogen = Zustandsmodell(zustaende, 0.0, uebergang, max_dauer=0)

    # Handrechnung (Zins 0, Start aktiv):
    # Jahr 1: krank 0.2; Jahr 2: 0.75*0.2 + 0.2*0.9 = 0.33 (beide Modelle).
    assert semi.barwert("aktiv", 40, 3, krankengeld) == pytest.approx(0.53, rel=1e-12)
    assert homogen.barwert("aktiv", 40, 3, krankengeld) == pytest.approx(0.53, rel=1e-12)
    # Ab Jahr 3 wirkt die Genesung (nur im Semi-Markov-Modell):
    # semi:    Jahr 3 krank = 0.5625*0.2 + 0.15*0.9 + 0.18*0.1 = 0.2655
    # homogen: Jahr 3 krank = 0.5625*0.2 + (0.15+0.18)*0.9     = 0.4095
    assert semi.barwert("aktiv", 40, 4, krankengeld) == pytest.approx(0.7955, rel=1e-12)
    assert homogen.barwert("aktiv", 40, 4, krankengeld) == pytest.approx(0.9395, rel=1e-12)


# --------------------------------------------------------------------------- #
# Fail-fast
# --------------------------------------------------------------------------- #


def test_wegzuege_ueber_eins_und_negative_sind_fehler():
    zuviel = Zustandsmodell(
        ("a", "b", "c"), 0.0,
        lambda von, nach, alter, dauer: 0.6 if von == "a" else 0.0,
    )
    with pytest.raises(ValueError, match="> 1"):
        zuviel.barwert("a", 40, 1, lambda z, j: 1.0)
    negativ = Zustandsmodell(
        ("a", "b"), 0.0, lambda von, nach, alter, dauer: -0.1
    )
    with pytest.raises(ValueError, match="< 0"):
        negativ.barwert("a", 40, 1, lambda z, j: 1.0)
    with pytest.raises(ValueError, match="Startzustand"):
        _zwei_zustaende(0.1).barwert("gibtsnicht", 40, 1)
    with pytest.raises(ValueError, match="eindeutig"):
        Zustandsmodell(("a", "a"), 0.0, lambda von, nach, alter, dauer: 0.0)


# --------------------------------------------------------------------------- #
# ZustandsBarwerte: 2-Zustands-Fall gegen die Kommutations-Schiene
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def basen():
    kom = fuer(KLV_DEFAULT.sex, KLV_DEFAULT.tafel, KLV_DEFAULT.zins)
    return Barwerte(kom, KLV_DEFAULT.zins), ZustandsBarwerte(tafeln.basis(KLV_DEFAULT.sex, KLV_DEFAULT.tafel), KLV_DEFAULT.zins)


def test_zustandsbarwerte_deckt_barwerte_interface(basen):
    klassisch, zustand = basen
    fehlend = [
        name for name in dir(klassisch)
        # "kom" ist der interne Kommutations-Handle des Zweitkerns,
        # kein Teil des aktuariellen Barwerte-Interfaces (Kern 3.0.0).
        if not name.startswith("_") and name != "kom"
        and not hasattr(zustand, name)
    ]
    assert fehlend == []


def test_zustandsbarwerte_stimmen_bis_auf_rundung(basen):
    klassisch, zustand = basen
    x = KLV_DEFAULT.x
    for a, b in (
        (klassisch.axn_k(x, 20, 1), zustand.axn_k(x, 20, 1)),
        (klassisch.axn_k(x, 30, 12), zustand.axn_k(x, 30, 12)),
        (klassisch.nGrAx(x, 30), zustand.nGrAx(x, 30)),
        (klassisch.nGrEx(x, 30), zustand.nGrEx(x, 30)),
        (klassisch.endowment_benefit_pv(x, 30), zustand.endowment_benefit_pv(x, 30)),
        (klassisch.Ax(x), zustand.Ax(x)),
        (klassisch.aex(x), zustand.aex(x)),
        (klassisch.ax_k(x, 12), zustand.ax_k(x, 12)),
        (klassisch.net_premium(x), zustand.net_premium(x)),
    ):
        assert a == pytest.approx(b, rel=1e-10)


def test_zustandsbarwerte_nGrEx_ist_reines_ueberlebensprodukt(basen):
    _, zustand = basen
    x, term = KLV_DEFAULT.x, 20
    produkt = 1.0
    for j in range(term):
        produkt *= 1.0 - zustand.basis.qx_at(x + j)
    v = 1.0 / (1.0 + KLV_DEFAULT.zins)
    assert zustand.nGrEx(x, term) == pytest.approx(produkt * v ** term, rel=1e-12)


def test_spalten_pass_ist_bitidentisch_zum_einzelaufruf(basen):
    """Der Spalten-Cache liefert exakt die Werte der Einzelrekursion:
    barwert_verlauf[j] eines Passes == barwert des Restproblems (gleiche
    Suffix-Rekursion, bit-identisch)."""
    _, zustand = basen
    modell = zustand.modell
    endalter = 80
    pass_werte = modell.barwert_verlauf(
        "aktiv", 0, endalter, zahlung_zustand=zustand._nur_aktiv
    )
    for age in (30, 45, 60, 79):
        einzeln = modell.barwert(
            "aktiv", age, endalter - age, zahlung_zustand=zustand._nur_aktiv
        )
        assert pass_werte[age] == einzeln  # bitgleich, nicht nur approx


def test_pass_cache_wird_ueber_instanzen_geteilt(basen):
    from rechner_pipeline.kommutationskern.kommutation import fuer
    from rechner_pipeline.kern.zustandsmodell import _PASS_CACHE

    _, zustand = basen
    zustand.nGrAx(45, 20)  # fuellt den Pass (Basis, "tod", 65)
    key = (zustand._basis, "tod", 65)
    assert key in _PASS_CACHE
    kom = fuer(KLV_DEFAULT.sex, KLV_DEFAULT.tafel, KLV_DEFAULT.zins)
    zweite = ZustandsBarwerte(tafeln.basis(KLV_DEFAULT.sex, KLV_DEFAULT.tafel), KLV_DEFAULT.zins)
    assert zweite._pass("tod", 65) is _PASS_CACHE[key]  # geteilt, kein Neubau


def test_zustandsbarwerte_tafelgrenze_fail_fast(basen):
    """Review-Fix: jenseits der Tafel-Erschoepfung (Dx = 0, DAV1994 ab 101)
    faellt das Zustandsmodell wie die klassische Domaene schnell — statt
    stiller bedingter Werte, wo die Kommutation ZeroDivisionError warf."""
    from rechner_pipeline.kern.tafeln import TafelBereichError

    _, zustand = basen
    # Letztes Alter mit Dx > 0 auf DAV1994_T (M): 100 — rechnet:
    assert zustand.Ax(100) > 0.0
    assert zustand.aex(100) >= 1.0
    # Tafel erschoepft (Dx = 0): sprechender Domaenenfehler:
    for aufruf in (
        lambda: zustand.Ax(105),
        lambda: zustand.aex(105),
        lambda: zustand.net_premium(105),
        lambda: zustand.nGrEx(MAX_ALTER, 1),
        lambda: zustand.axn_k(101, 5, 1),
    ):
        with pytest.raises(TafelBereichError):
            aufruf()
    # Jenseits MAX_ALTER: Bereichsfehler wie die Kommutation:
    with pytest.raises(IndexError):
        zustand.nGrEx(100, 24)  # hoechstes Alter 124


def test_start_dauer_und_verteilung_fail_fast():
    """Review-Fix: ungueltige Start-Parameter waren stille Nuller."""
    modell = _zwei_zustaende(0.1)
    with pytest.raises(ValueError, match="start_dauer"):
        modell.barwert("aktiv", 40, 3, lambda z, j: 1.0, start_dauer=3)
    with pytest.raises(ValueError, match="start_dauer"):
        modell.barwert_verlauf("aktiv", 40, 3, lambda z, j: 1.0, start_dauer=-1)
    with pytest.raises(ValueError, match="start_dauer"):
        modell.verteilung("aktiv", 40, 2, start_dauer=7)
    with pytest.raises(ValueError, match="Startzustand"):
        modell.verteilung("gibtsnicht", 40, 2)


def test_wegzuege_epsilon_fenster_wird_renormiert():
    """Review-Fix: Wegzugsummen in (1, 1+1e-12] werden renormiert statt
    still Gesamtmasse > 1 zu akzeptieren."""
    w = 0.5 + 2.5e-13
    modell = Zustandsmodell(
        ("a", "b", "c"), 0.0,
        lambda von, nach, alter, dauer: w if von == "a" else 0.0,
    )
    masse = sum(modell.verteilung("a", 40, 1).values())
    assert masse == pytest.approx(1.0, abs=1e-15)
    barwert = modell.barwert(
        "a", 40, 1, zahlung_uebergang=lambda von, nach, jahr: 1.0
    )
    assert barwert <= 1.0 + 1e-15
