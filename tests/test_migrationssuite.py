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
ABLAUF = 12 * KLV_DEFAULT.n       # Ablaufmonat des Referenzvertrags (a = n)


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


def _ablauf_pruefung(
    gevos: Tuple[GeVoErwartung, ...],
    dk2: Optional[float] = None,
    s1: int = S1,
) -> VertragsPruefung:
    """Prüfauftrag mit Folgestichtag GENAU am Ablauf (a = n)."""
    return VertragsPruefung(
        police_id="P-ABL", model_point=MP,
        monate_stichtag_1=s1, monate_stichtag_2=ABLAUF,
        dk_erwartet_1=round(KERN.monatsreserve(s1).vx_mrv, 2),
        dk_erwartet_2=dk2, gevos=gevos,
    )


def test_abl_terminal_mit_gesamtversicherungssumme() -> None:
    """ABL zahlt S^ges und beendet den Vertrag (Tarifplan, GeVo-Katalog)."""
    vs = float(KLV_DEFAULT.sum_insured)
    urteil = pruefe_vertrag(_ablauf_pruefung(
        (GeVoErwartung("ABL", ABLAUF, vs),)))
    assert urteil["bestanden"], urteil["befunde"]
    assert [p["groesse"] for p in urteil["pruefungen"]] == [
        "dk_stichtag_1", f"gevo_abl_monat_{ABLAUF}"]
    # Kontrollrechnung: ein anderer Betrag darf NICHT durchgehen.
    falsch = pruefe_vertrag(_ablauf_pruefung(
        (GeVoErwartung("ABL", ABLAUF, vs + 1000.0),)))
    assert not falsch["bestanden"]


def test_abl_summiert_die_erhoehungsscheiben() -> None:
    a, s_neu = 10, 5000.0
    gevos = (GeVoErwartung("ERH", 12 * a, s_neu),
             GeVoErwartung("ABL", ABLAUF,
                           float(KLV_DEFAULT.sum_insured) + s_neu))
    urteil = pruefe_vertrag(_ablauf_pruefung(gevos))
    assert urteil["bestanden"], urteil["befunde"]
    # Ohne die Scheibe (nur GrundVS) schlüge die Ablaufleistung fehl:
    ohne = (gevos[0], GeVoErwartung("ABL", ABLAUF,
                                    float(KLV_DEFAULT.sum_insured)))
    assert not pruefe_vertrag(_ablauf_pruefung(ohne))["bestanden"]


def test_abl_nach_pex_zahlt_die_beitragsfreie_summe() -> None:
    a0 = 15  # Beitragsfreistellung im beitragspflichtigen Track (a0 < t)
    s_bfr = round(KERN.beitragsfreie_summe(a0), 2)
    gevos = (GeVoErwartung("PEX", 12 * a0, s_bfr),
             GeVoErwartung("ABL", ABLAUF, s_bfr))
    urteil = pruefe_vertrag(_ablauf_pruefung(gevos, s1=12 * 14 + 5))
    assert urteil["bestanden"], urteil["befunde"]
    # Kontrolle: nach PEX ist NICHT mehr die GrundVS die Ablaufleistung.
    mit_vs = (gevos[0], GeVoErwartung("ABL", ABLAUF,
                                      float(KLV_DEFAULT.sum_insured)))
    assert not pruefe_vertrag(
        _ablauf_pruefung(mit_vs, s1=12 * 14 + 5))["bestanden"]


def test_abl_mit_folgewert_ist_befund() -> None:
    """Abgelaufen und trotzdem im Folgeabzug — Lieferung inkonsistent."""
    urteil = pruefe_vertrag(_ablauf_pruefung(
        (GeVoErwartung("ABL", ABLAUF, float(KLV_DEFAULT.sum_insured)),),
        dk2=12345.67))
    assert not urteil["bestanden"]
    assert any("abgegangen" in b for b in urteil["befunde"])


def test_abl_vor_dem_ablauf_ist_befund() -> None:
    urteil = pruefe_vertrag(_pruefung(
        gevos=(GeVoErwartung("ABL", S1 + 4,
                             float(KLV_DEFAULT.sum_insured)),)))
    assert not urteil["bestanden"]
    assert any("Versicherungsdauer" in b for b in urteil["befunde"])


def test_leere_pruefmenge_ist_keine_bestandene_abnahme() -> None:
    with pytest.raises(ValueError, match="leere Prüfmenge"):
        pruefe_bestand([])


def test_ausnahme_eines_vertrags_bleibt_dessen_befund() -> None:
    """Ein kranker Datensatz beendet den Lauf nicht, er wird sein Befund."""
    kaputt = dataclasses.replace(
        _pruefung(), police_id="P-2", monate_stichtag_2=ABLAUF + 12)
    ergebnis = pruefe_bestand([
        _pruefung(),
        kaputt,
        dataclasses.replace(_pruefung(), police_id="P-3"),
    ])
    assert (ergebnis["anzahl"], ergebnis["bestanden"],
            ergebnis["fehlgeschlagen"]) == (3, 2, 1)
    assert not ergebnis["suite_bestanden"]
    urteil = [u for u in ergebnis["vertraege"] if u["police_id"] == "P-2"][0]
    assert urteil["pruefungen"] == []
    assert any("ValueError" in b and "nach dem Ablauf" in b
               for b in urteil["befunde"]), urteil["befunde"]
    # Die übrigen Verträge wurden zu Ende geprüft:
    assert all(len(u["pruefungen"]) == 2 for u in ergebnis["vertraege"]
               if u["police_id"] != "P-2")


class _GeVoOhneMonat:
    """Formfehler der Anbindung (kein Lieferdatum): Attribut fehlt."""

    art = "TOD"


def test_programmierfehler_bricht_den_lauf_ab() -> None:
    """Kein blindes Fangen: was keine Lieferung erzeugen kann, fliegt."""
    with pytest.raises(AttributeError):
        pruefe_bestand([dataclasses.replace(
            _pruefung(), gevos=(_GeVoOhneMonat(),))])


def test_bestand_zusammenfassung() -> None:
    ergebnis = pruefe_bestand([
        _pruefung(),
        dataclasses.replace(_pruefung(dk1=1.0), police_id="P-2"),
    ])
    assert (ergebnis["anzahl"], ergebnis["bestanden"],
            ergebnis["fehlgeschlagen"]) == (2, 1, 1)
    assert not ergebnis["suite_bestanden"]
