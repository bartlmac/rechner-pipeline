"""BU-Beispielprodukt: Äquivalenz, Select-Semantik, Registry, Fail-fast."""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern.kommutation import (
    MissingMortalityTableError,
    select_max_dauer,
    select_tafel,
)
from rechner_pipeline.kern.produkte import PRODUKTE, hole
from rechner_pipeline.kern.produkte.bu import BU, BU_BEISPIEL, BUModelPoint
from rechner_pipeline.kern.rechenkern import berechne


@pytest.fixture(scope="module")
def produkt():
    return BU(BU_BEISPIEL)


def test_bu_ist_registriert():
    assert hole("bu") is BU
    assert set(PRODUKTE) == {"klv", "bu"}
    assert BU.model_point_cls is BUModelPoint


def test_aequivalenzprinzip_anfangsreserve_null(produkt):
    """Per Konstruktion: p * Prämienbarwert == Rente * Leistungsbarwert."""
    assert produkt.reserve_aktiv(0) == pytest.approx(0.0, abs=1e-8)
    assert produkt.nettobeitrag() == pytest.approx(
        BU_BEISPIEL.bu_rente * produkt.leistungsbarwert() / produkt.praemienbarwert(),
        rel=1e-12,
    )
    assert produkt.bruttobeitrag() == pytest.approx(
        produkt.nettobeitrag() * 1.05, rel=1e-12
    )


def test_reserven_fachlich_plausibel(produkt):
    """BU-Reserve = im Wesentlichen Rentenbarwert, weit über Aktiven-Reserve;
    am Ablauf sind beide 0."""
    assert produkt.reserve_bu(10, 0) > 50 * produkt.reserve_aktiv(10) > 0
    assert produkt.reserve_aktiv(BU_BEISPIEL.n) == 0.0
    assert produkt.reserve_bu(BU_BEISPIEL.n, 0) == 0.0


def test_select_dauer_wirkt_monoton(produkt):
    """Höhere BU-Dauer -> weniger Reaktivierungschance -> höhere Reserve
    (und jenseits der Select-Periode konstant gekappt)."""
    reserven = [produkt.reserve_bu(10, d) for d in range(0, 6)]
    assert all(a < b for a, b in zip(reserven, reserven[1:]))
    assert produkt.reserve_bu(10, 99) == reserven[-1]  # Kappung auf Select-Periode


def test_contract_shape_ueber_registry():
    ergebnis = berechne(BU_BEISPIEL, produkt="bu")
    assert set(ergebnis["scalars"]) == {"BU"}
    assert set(ergebnis["scalars"]["BU"]) == {
        "Nettobeitrag", "Bruttobeitrag", "Leistungsbarwert", "Praemienbarwert",
    }
    zeilen = ergebnis["tables"]["BU"]
    assert len(zeilen) == BU_BEISPIEL.n + 1
    assert list(zeilen[0]) == ["jahr", "V_aktiv", "V_bu"]
    assert zeilen[0]["V_aktiv"] == pytest.approx(0.0, abs=1e-8)


def test_parametrisierung_wirkt():
    guenstiger = BU(dataclasses.replace(BU_BEISPIEL, x=25))
    teurer = BU(dataclasses.replace(BU_BEISPIEL, x=45, n=20))
    basis = BU(BU_BEISPIEL)
    assert guenstiger.nettobeitrag() < basis.nettobeitrag() < teurer.nettobeitrag()
    frau = BU(dataclasses.replace(BU_BEISPIEL, sex="F"))
    assert frau.nettobeitrag() != basis.nettobeitrag()


def test_fehlende_tafeln_fail_fast():
    with pytest.raises(MissingMortalityTableError):
        BU(dataclasses.replace(BU_BEISPIEL, tafel_ri="GIBTS_NICHT"))
    with pytest.raises(MissingMortalityTableError):
        BU(dataclasses.replace(BU_BEISPIEL, tafel_i="GIBTS_NICHT_I"))
    # Jenseits der Tafel (x + n - 1 > 123): Bereichsfehler beim Rechnen.
    zu_alt = BU(dataclasses.replace(BU_BEISPIEL, x=100, n=30))
    with pytest.raises(IndexError):
        zu_alt.nettobeitrag()


def test_synthetische_tafeln_sind_konsistent():
    """Datenqualität der Beispieltafeln: vollständig, Wegzugsummen <= 1."""
    ri = select_tafel(BU_BEISPIEL.tafel_ri)
    ti = select_tafel(BU_BEISPIEL.tafel_ti)
    max_d = select_max_dauer(BU_BEISPIEL.tafel_ri)
    assert max_d == 5
    for alter in range(0, 124):
        for dauer in range(0, max_d + 1):
            summe = ri[(alter, dauer)] + ti[(alter, dauer)]
            assert 0.0 <= summe <= 1.0, (alter, dauer, summe)


def test_vorwaerts_rueckwaerts_selbsttest_auf_bu_konfiguration(produkt):
    """Der Engine-Selbsttest auf der echten BU-Konfiguration (Select-Tafeln)."""
    modell = produkt.modell
    mp = BU_BEISPIEL
    rueckwaerts = modell.barwert(
        "aktiv", mp.x, 12, zahlung_zustand=produkt._bu_rente_zahlung
    )
    v = 1.0 / (1.0 + mp.zins)
    vorwaerts = 0.0
    for jahr in range(12):
        for (zustand, dauer), masse in modell.verteilung("aktiv", mp.x, jahr).items():
            vorwaerts += (v ** jahr) * masse * produkt._bu_rente_zahlung(zustand, jahr)
    assert rueckwaerts == pytest.approx(vorwaerts, rel=1e-12)
