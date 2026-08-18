"""Migrations-Testsuite: Zwei-Stichtags-Prüfung (qa/migrationssuite).

Die Erwartungswerte der grünen Pfade werden hier aus dem Kern selbst
erzeugt und centgerundet (wie eine reale Lieferung liefert) — geprüft
wird die Urteils-Mechanik: Toleranzen, GeVo-Tracks (STO/TOD/PEX und
die vertragsweite Scheiben-Bewertung nach ERH) sowie die
Konsistenz-Befunde der Lieferung.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Optional, Tuple

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.qa.migrationssuite import (
    GeVoErwartung,
    VertragsPruefung,
    pruefe_bestand,
    pruefe_vertrag,
)

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
S1, S2 = 12 * 9 + 5, 12 * 10 + 5  # Stichtage mitten im Vertragsjahr


def _pruefung(
    dk1: Optional[float] = None,
    dk2: Optional[float] = None,
    gevos: Tuple[GeVoErwartung, ...] = (),
    dk2_fehlt: bool = False,
) -> VertragsPruefung:
    """Prüfauftrag mit kern-eigenen, centgerundeten Erwartungen."""
    if dk1 is None:
        dk1 = round(KERN.monatsreserve(S1).vx_mrv, 2)
    if dk2 is None and not dk2_fehlt:
        dk2 = round(KERN.monatsreserve(S2).vx_mrv, 2)
    return VertragsPruefung(
        police_id="P-1", model_point=MP,
        monate_stichtag_1=S1, monate_stichtag_2=S2,
        dk_erwartet_1=dk1, dk_erwartet_2=dk2, gevos=gevos,
    )


def test_ohne_gevos_bestanden() -> None:
    urteil = pruefe_vertrag(_pruefung())
    assert urteil["bestanden"], urteil["befunde"]
    groessen = [p["groesse"] for p in urteil["pruefungen"]]
    assert groessen == ["dk_stichtag_1", "dk_stichtag_2"]


def test_toleranzverletzung_mit_residuum() -> None:
    urteil = pruefe_vertrag(_pruefung(dk1=round(
        KERN.monatsreserve(S1).vx_mrv, 2) + 500.0))
    assert not urteil["bestanden"]
    p = urteil["pruefungen"][0]
    assert not p["ok"] and p["residuum"] == pytest.approx(-500.0, abs=0.01)


def test_sto_terminal_mit_betragspruefung() -> None:
    m_sto = S1 + 4
    gevo = GeVoErwartung("STO", m_sto, round(KERN.monatsreserve(m_sto).rkw, 2))
    urteil = pruefe_vertrag(_pruefung(gevos=(gevo,), dk2_fehlt=True))
    assert urteil["bestanden"], urteil["befunde"]
    assert any(p["groesse"].startswith("gevo_sto") and p["ok"]
               for p in urteil["pruefungen"])


def test_terminal_mit_folgewert_ist_befund() -> None:
    gevo = GeVoErwartung("TOD", S1 + 3, float(KLV_DEFAULT.sum_insured))
    urteil = pruefe_vertrag(_pruefung(gevos=(gevo,)))
    assert not urteil["bestanden"]
    assert any("abgegangen" in b for b in urteil["befunde"])


def test_fehlender_folgewert_ohne_abgang_ist_befund() -> None:
    urteil = pruefe_vertrag(_pruefung(dk2_fehlt=True))
    assert not urteil["bestanden"]
    assert any("keinen Abgang" in b for b in urteil["befunde"])


def test_pex_track_am_folgestichtag() -> None:
    a0 = 10  # Jahrestag zwischen den Stichtagen (Monat 120)
    gevos = (GeVoErwartung("PEX", 12 * a0,
                           round(KERN.beitragsfreie_summe(a0), 2)),)
    dk2 = round(KERN.monatsreserve_beitragsfrei(a0, S2), 2)
    urteil = pruefe_vertrag(_pruefung(dk2=dk2, gevos=gevos))
    assert urteil["bestanden"], urteil["befunde"]


def test_pex_unterjaehrig_ist_befund() -> None:
    gevos = (GeVoErwartung("PEX", S1 + 2, 1000.0),)
    urteil = pruefe_vertrag(_pruefung(gevos=gevos))
    assert not urteil["bestanden"]
    assert any("Vertragsjahrestag" in b for b in urteil["befunde"])


def test_erh_wird_vertragsweit_geprueft() -> None:
    a, s_neu = 10, 5000.0
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, a, s_neu))
    dk2 = round(vertrags_monatsreserve(KERN, [(a, scheibe)], S2).vx_mrv, 2)
    gevos = (GeVoErwartung("ERH", 12 * a, s_neu),)
    urteil = pruefe_vertrag(_pruefung(dk2=dk2, gevos=gevos))
    assert urteil["bestanden"], urteil["befunde"]
    # Ohne Scheibenberuecksichtigung schluege der Vergleich fehl:
    falsch = round(KERN.monatsreserve(S2).vx_mrv, 2)
    urteil2 = pruefe_vertrag(_pruefung(dk2=falsch, gevos=gevos))
    assert not urteil2["bestanden"]


def test_erh_befunde() -> None:
    unterjaehrig = pruefe_vertrag(_pruefung(
        gevos=(GeVoErwartung("ERH", S1 + 1, 5000.0),)))
    assert any("Vertragsjahrestag" in b for b in unterjaehrig["befunde"])
    ohne_summe = pruefe_vertrag(_pruefung(
        gevos=(GeVoErwartung("ERH", 12 * 10, None),)))
    assert any("ohne Erhöhungssumme" in b for b in ohne_summe["befunde"])


def test_gevo_ausserhalb_der_stichtage_ist_befund() -> None:
    gevos = (GeVoErwartung("TOD", S1 - 1, 1.0),)
    urteil = pruefe_vertrag(_pruefung(gevos=gevos))
    assert not urteil["bestanden"]
    assert any("zwischen den Stichtagen" in b for b in urteil["befunde"])


def test_bestand_zusammenfassung() -> None:
    ergebnis = pruefe_bestand([
        _pruefung(),
        dataclasses.replace(_pruefung(dk1=1.0), police_id="P-2"),
    ])
    assert (ergebnis["anzahl"], ergebnis["bestanden"],
            ergebnis["fehlgeschlagen"]) == (2, 1, 1)
    assert not ergebnis["suite_bestanden"]
