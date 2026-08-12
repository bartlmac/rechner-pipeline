"""Zustandsmodell-Engine: Handrechnungen, Selbsttest, Semi-Markov, Interface."""

from __future__ import annotations

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.barwerte import Barwerte
from rechner_pipeline.kern.kommutation import fuer
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
    return Barwerte(kom, KLV_DEFAULT.zins), ZustandsBarwerte(kom, KLV_DEFAULT.zins)


def test_zustandsbarwerte_deckt_barwerte_interface(basen):
    klassisch, zustand = basen
    fehlend = [
        name for name in dir(klassisch)
        if not name.startswith("_") and not hasattr(zustand, name)
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
        produkt *= 1.0 - zustand.kom.qx_at(x + j)
    v = 1.0 / (1.0 + KLV_DEFAULT.zins)
    assert zustand.nGrEx(x, term) == pytest.approx(produkt * v ** term, rel=1e-12)


def test_zustandsbarwerte_tafelgrenze_wie_kommutation(basen):
    _, zustand = basen
    # Whole-life am hoechsten Alter rechnet; jenseits der Tafel fail-fast:
    assert zustand.Ax(MAX_ALTER) >= 0.0
    with pytest.raises(IndexError):
        zustand.nGrEx(MAX_ALTER, 1)
