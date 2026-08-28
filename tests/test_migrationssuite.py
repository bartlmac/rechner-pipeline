"""Migrations-Testsuite: Zwei-Stichtags-Prüfung (qa/migrationssuite).

EHRLICHKEIT ÜBER DIE ERWARTUNGSQUELLE: Die Erwartungswerte der grünen
Pfade stammen aus DEMSELBEN Kern, den die Suite rechnet (centgerundet,
wie eine reale Lieferung sie führt). Diese Tests können deshalb keinen
Rechenfehler des Kerns finden — das leisten der Golden Master und die
Fall-Referenzwerte. Geprüft wird hier das URTEIL: Toleranzgrenzen, Auswahl des
Tracks (aktiv / beitragsfrei / abgegangen / Scheiben nach ERH), die
Befundtexte der Lieferungs-Inkonsistenzen sowie Vollständigkeit,
Duplikate und ausgewiesene Prüflücken.

Wo dieses Verfahren NICHT trägt — bei der Urteilslogik selbst — steht
die Erwartung unabhängig vom Kern: Toleranzgrenzen werden aus
REL_TOL/ABS_TOL gerechnet, Leistungshöhen aus der Tarifwerk-Regel
(Summe der Versicherungssummen), und jede grüne Behauptung hat eine
Kontrolle daneben, die mit dem falschen Track oder dem falschen Betrag
fehlschlagen MUSS.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any, Dict, Optional, Tuple

import pytest

from rechner_pipeline.kern import (
    KLV_DEFAULT,
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL
from rechner_pipeline.qa.migrationssuite import (
    GEVO_ARTEN,
    TERMINAL,
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


@pytest.mark.parametrize("art", ("STO", "TOD", "ABL", "PEX"))
def test_fehlender_betrag_eines_betragsgevo_ist_konkrete_pruefluecke(
    art: str,
) -> None:
    """Zustandswirkung ersetzt nie den ausgelassenen Betragsvergleich."""
    if art == "ABL":
        monat = ABLAUF
        vertrag = _ablauf_pruefung((GeVoErwartung(art, monat),))
    elif art == "PEX":
        monat = 12 * 10
        dk2 = round(KERN.monatsreserve_beitragsfrei(monat // 12, S2), 2)
        vertrag = _pruefung(
            dk2=dk2, gevos=(GeVoErwartung(art, monat),))
    else:
        monat = S1 + 4
        vertrag = _pruefung(
            dk2_fehlt=True, gevos=(GeVoErwartung(art, monat),))
    vertrag = dataclasses.replace(
        vertrag, bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))

    ergebnis = pruefe_bestand([vertrag], erwartete_anzahl=1)

    luecke = f"gevo_{art.lower()}_monat_{monat}"
    urteil = ergebnis["vertraege"][0]
    assert urteil["bestanden"], urteil["befunde"]
    assert urteil["nicht_geprueft"] == [luecke]
    assert luecke not in [p["groesse"] for p in urteil["pruefungen"]]
    assert ergebnis["suite_bestanden"] is True
    assert ergebnis["vollstaendig_geprueft"] is False
    assert len(ergebnis["pruefluecken"]) == 1
    assert luecke in ergebnis["pruefluecken"][0]
    assert "NICHT geprüft" in ergebnis["pruefluecken"][0]


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


# --------------------------------------------------------------------------- #
# Die Toleranzgrenze selbst — Erwartung aus REL_TOL/ABS_TOL gerechnet,
# nicht aus dem Kern. Ohne diese Tests koennte die Grenze beliebig
# verschoben werden, ohne dass ein Test rot wird.
# --------------------------------------------------------------------------- #


def test_relative_toleranzgrenze_traegt_und_schneidet() -> None:
    """Knapp innerhalb besteht, knapp ausserhalb faellt — relativ.

    Zusammen mit :func:`test_absolute_untergrenze_traegt_kleine_betraege`
    klemmt dieser Test die Größenordnung von REL_TOL fest: bei rund
    36 TEUR muss die RELATIVE Schranke greifen, bei rund 3,8 TEUR die
    ABSOLUTE. Ein Aufweichen von REL_TOL um Größenordnungen (etwa
    zurück auf 5e-4) verletzt die zweite Bedingung und färbt die Suite
    rot — genau das soll es.
    """
    dk = KERN.monatsreserve(S1).vx_mrv
    assert REL_TOL * dk > ABS_TOL, "hier muss die RELATIVE Schranke greifen"
    innen = pruefe_vertrag(_pruefung(dk1=dk * (1.0 - 0.9 * REL_TOL)))
    assert innen["pruefungen"][0]["ok"]
    aussen = pruefe_vertrag(_pruefung(dk1=dk * (1.0 - 1.5 * REL_TOL)))
    assert not aussen["pruefungen"][0]["ok"]
    assert not aussen["bestanden"]


def test_absolute_untergrenze_traegt_kleine_betraege() -> None:
    """Bei kleinen Betraegen entscheidet ABS_TOL, nicht REL_TOL.

    Die Cent-Rundung der Lieferung ist ein ABSOLUTER Fehler; sie muss
    von ABS_TOL getragen werden und nicht von einer weit gespannten
    relativen Toleranz (siehe Modulkopf von ``qa/abzugsabgleich``).
    """
    monate = 13
    dk = KERN.monatsreserve(monate).vx_mrv
    assert REL_TOL * dk < ABS_TOL, "hier muss die ABSOLUTE Schranke greifen"

    def _urteil(erwartet: float) -> Dict[str, Any]:
        return pruefe_vertrag(VertragsPruefung(
            police_id="P-KLEIN", model_point=MP,
            monate_stichtag_1=monate, monate_stichtag_2=S2,
            dk_erwartet_1=erwartet,
            dk_erwartet_2=round(KERN.monatsreserve(S2).vx_mrv, 2),
        ))

    assert _urteil(dk + 0.5 * ABS_TOL)["pruefungen"][0]["ok"]
    assert not _urteil(dk + 1.5 * ABS_TOL)["pruefungen"][0]["ok"]


# --------------------------------------------------------------------------- #
# Bruttojahresbeitrag: die zweite Pruefachse (Auftrag 19.08.)
# --------------------------------------------------------------------------- #


def test_gelieferter_jahresbeitrag_wird_geprueft() -> None:
    v = dataclasses.replace(
        _pruefung(), bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))
    urteil = pruefe_vertrag(v)
    assert urteil["bestanden"], urteil["befunde"]
    assert [p["groesse"] for p in urteil["pruefungen"]] == [
        "dk_stichtag_1", "bjb_stichtag_1", "dk_stichtag_2"]
    assert urteil["nicht_geprueft"] == []
    # Kontrolle: ein anderer Jahresbeitrag darf NICHT durchgehen.
    falsch = dataclasses.replace(v, bjb_erwartet_1=v.bjb_erwartet_1 + 100.0)
    assert not pruefe_vertrag(falsch)["bestanden"]


def test_jahresbeitrag_ist_null_nach_ende_der_beitragszahlung() -> None:
    """Beitragsfrei durch Zeitablauf: die Abzuege fuehren JBRUTTO 0,00.

    Erwartung NICHT aus dem Kern, sondern aus der Lieferungssemantik
    (nachgeprueft am gelieferten Abzug: JBRUTTO ist genau dann 0,00,
    wenn ``monate >= 12 * t``). Der Kern-Jahresbeitrag des
    Grundvertrags bleibt daneben ungleich null — genau deshalb muss die
    Suite den Track kennen.
    """
    monate = 12 * KLV_DEFAULT.t + 1
    v = VertragsPruefung(
        police_id="P-BEITRAGSFREI-ZEIT", model_point=MP,
        monate_stichtag_1=monate, monate_stichtag_2=monate + 12,
        dk_erwartet_1=round(KERN.monatsreserve(monate).vx_mrv, 2),
        dk_erwartet_2=round(KERN.monatsreserve(monate + 12).vx_mrv, 2),
        bjb_erwartet_1=0.0,
    )
    assert pruefe_vertrag(v)["bestanden"]
    assert KERN.gross_annual_premium() > 0.0
    # Kontrolle: der Jahresbeitrag der Beitragsphase ist hier falsch.
    falsch = dataclasses.replace(
        v, bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))
    assert not pruefe_vertrag(falsch)["bestanden"]


def test_altersversatz_faellt_am_beitrag_auf_wo_das_deckungskapital_schweigt(
) -> None:
    """Warum der Jahresbeitrag mitgeprueft wird (Auftrag 19.08.).

    Quellsysteme koennen das Eintrittsalter nach der
    Kalenderjahresmethode fuehren; gegen das vollendete Alter des
    Zielsystems ist das ein Versatz von einem Jahr. Bei kurzer
    Beitragszahlungsdauer verschiebt dieser Versatz das
    Deckungskapital kaum — der Bruttojahresbeitrag reagiert um
    Groessenordnungen staerker. Beide Kennzahlen werden hier gerechnet
    und gegeneinander gestellt; die Aussage haengt an keiner Toleranz.
    """
    richtig = dataclasses.replace(KLV_DEFAULT, x=35, n=20, t=15)
    versetzt = dataclasses.replace(richtig, x=36)
    k_r, k_v = Rechenkern(richtig), Rechenkern(versetzt)
    dk_rel = abs(k_v.monatsreserve(S1).vx_mrv - k_r.monatsreserve(S1).vx_mrv
                 ) / k_r.monatsreserve(S1).vx_mrv
    bjb_rel = abs(k_v.gross_annual_premium() - k_r.gross_annual_premium()
                  ) / k_r.gross_annual_premium()
    assert bjb_rel > 10 * dk_rel
    # Unter der bis zum 19.08. geltenden Toleranz (5e-4) war der Versatz
    # im Deckungskapital unsichtbar, im Jahresbeitrag nicht:
    assert dk_rel < 5e-4 < bjb_rel

    # Und die Suite faellt darauf herein, solange nur das
    # Deckungskapital geliefert ist — mit Jahresbeitrag nicht:
    lieferung = dict(
        police_id="P-VERSATZ", model_point=dataclasses.asdict(versetzt),
        monate_stichtag_1=S1, monate_stichtag_2=S2,
        dk_erwartet_1=round(k_r.monatsreserve(S1).vx_mrv, 2),
        dk_erwartet_2=round(k_r.monatsreserve(S2).vx_mrv, 2),
    )
    nur_dk = pruefe_vertrag(VertragsPruefung(**lieferung))
    assert math.isclose(
        nur_dk["pruefungen"][0]["system"], nur_dk["pruefungen"][0]["erwartet"],
        rel_tol=5e-4, abs_tol=ABS_TOL), "alte Toleranz haette das gedeckt"
    mit_bjb = pruefe_vertrag(VertragsPruefung(
        **lieferung, bjb_erwartet_1=round(k_r.gross_annual_premium(), 2)))
    assert not mit_bjb["bestanden"]
    schlecht = [p["groesse"] for p in mit_bjb["pruefungen"] if not p["ok"]]
    assert "bjb_stichtag_1" in schlecht


def test_fehlender_jahresbeitrag_ist_eine_ausgewiesene_luecke() -> None:
    """Nicht geliefert heisst nicht geprueft — und wird gesagt."""
    ergebnis = pruefe_bestand([_pruefung()], erwartete_anzahl=1)
    assert ergebnis["suite_bestanden"]                 # kein Fehlschlag ...
    assert ergebnis["vollstaendig_geprueft"] is False  # ... aber auch nicht
    assert ergebnis["vertraege"][0]["nicht_geprueft"] == ["bjb_stichtag_1"]
    assert any("bjb_stichtag_1" in l and "NICHT geprüft" in l
               for l in ergebnis["pruefluecken"]), ergebnis["pruefluecken"]
    # Mit geliefertem Beitrag verschwindet die Luecke:
    voll = pruefe_bestand(
        [dataclasses.replace(
            _pruefung(), bjb_erwartet_1=round(KERN.gross_annual_premium(), 2))],
        erwartete_anzahl=1)
    assert voll["pruefluecken"] == [] and voll["vollstaendig_geprueft"]


# --------------------------------------------------------------------------- #
# Die Pruefmenge: Vollstaendigkeit und Duplikate
# --------------------------------------------------------------------------- #


def test_unvollstaendige_pruefmenge_ist_keine_bestandene_abnahme() -> None:
    ergebnis = pruefe_bestand(
        [_pruefung(), dataclasses.replace(_pruefung(), police_id="P-2")],
        erwartete_anzahl=500)
    assert ergebnis["bestanden"] == 2 and ergebnis["fehlgeschlagen"] == 0
    assert ergebnis["suite_bestanden"] is False
    assert len(ergebnis["mengenbefunde"]) == 1
    assert "498 Verträge fehlen" in ergebnis["mengenbefunde"][0]
    assert ergebnis["erwartete_anzahl"] == 500


def test_zu_viele_vertraege_sind_ebenfalls_ein_mengenbefund() -> None:
    ergebnis = pruefe_bestand(
        [_pruefung(), dataclasses.replace(_pruefung(), police_id="P-2")],
        erwartete_anzahl=1)
    assert ergebnis["suite_bestanden"] is False
    assert "1 Verträge zu viel" in ergebnis["mengenbefunde"][0]


def test_doppelte_policennummer_ist_ein_harter_befund() -> None:
    """Derselbe Vertrag dreimal ist kein dreifacher Beleg."""
    ergebnis = pruefe_bestand([_pruefung()] * 3, erwartete_anzahl=3)
    assert ergebnis["anzahl"] == 3 and ergebnis["fehlgeschlagen"] == 0
    assert ergebnis["suite_bestanden"] is False       # trotz 3 von 3 bestanden
    assert len(ergebnis["mengenbefunde"]) == 1
    assert "'P-1'" in ergebnis["mengenbefunde"][0]
    assert "3-mal" in ergebnis["mengenbefunde"][0]
    # Ohne Duplikat ist die Menge sauber:
    sauber = pruefe_bestand(
        [_pruefung(), dataclasses.replace(_pruefung(), police_id="P-2")],
        erwartete_anzahl=2)
    assert sauber["mengenbefunde"] == [] and sauber["suite_bestanden"]


def test_ohne_erwartete_anzahl_ist_die_vollstaendigkeit_eine_luecke() -> None:
    ergebnis = pruefe_bestand([_pruefung()])
    assert ergebnis["erwartete_anzahl"] is None
    assert ergebnis["mengenbefunde"] == []            # kein Befund ...
    assert any("Vollständigkeit" in l for l in ergebnis["pruefluecken"])
    assert ergebnis["vollstaendig_geprueft"] is False  # ... aber eine Luecke


# --------------------------------------------------------------------------- #
# Track-Auswahl: Erhoehungsscheiben in Leistung und Bewertung
# --------------------------------------------------------------------------- #


def test_tod_nach_erhoehung_zahlt_die_summe_beider_scheiben() -> None:
    """Leistungshoehe aus der Tarifwerk-Regel, nicht aus dem Kern.

    S^ges ist die Summe der Versicherungssummen — eine Addition, die
    dieser Test selbst ausfuehrt. Ein Kern, der die Scheibe vergaesse,
    faellt hier auf.
    """
    a, s_neu = 10, 5000.0
    vs_ges = float(KLV_DEFAULT.sum_insured) + s_neu
    gevos = (GeVoErwartung("ERH", 12 * a, s_neu),
             GeVoErwartung("TOD", 12 * a + 3, vs_ges))
    urteil = pruefe_vertrag(_pruefung(gevos=gevos, dk2_fehlt=True))
    assert urteil["bestanden"], urteil["befunde"]
    assert any(p["groesse"].startswith("gevo_tod") and p["ok"]
               for p in urteil["pruefungen"])
    # Kontrolle: ohne die Scheibe ist die Todesfallleistung zu klein.
    ohne = (gevos[0], GeVoErwartung("TOD", 12 * a + 3,
                                    float(KLV_DEFAULT.sum_insured)))
    assert not pruefe_vertrag(
        _pruefung(gevos=ohne, dk2_fehlt=True))["bestanden"]


def test_tod_nach_beitragsfreistellung_zahlt_die_beitragsfreie_summe() -> None:
    """Nach PEX ist die Todesfallleistung ``sum S^bfr``, nicht ``S^ges``.

    Tarifplan klv.md, GeVo-Katalog, Zeile TOD ("``S^ges`` bzw. nach PEX
    ``sum S^bfr``"); die Bestand-Engine bucht denselben Betrag
    (``bestand/ereignisse``: TOD zahlt ``pex_summe``, sobald der Vertrag
    beitragsfrei ist). Ein Vergleich gegen die Gesamt-VS machte aus
    dieser korrekten Lieferung einen Fehlschlag.
    """
    a0 = 10  # Jahrestag zwischen den Stichtagen (Monat 120)
    s_bfr = round(KERN.beitragsfreie_summe(a0), 2)
    gevos = (GeVoErwartung("PEX", 12 * a0, s_bfr),
             GeVoErwartung("TOD", 12 * a0 + 2, s_bfr))
    urteil = pruefe_vertrag(_pruefung(gevos=gevos, dk2_fehlt=True))
    assert urteil["bestanden"], urteil["befunde"]
    assert any(p["groesse"].startswith("gevo_tod") and p["ok"]
               for p in urteil["pruefungen"])
    # Kontrolle: die Gesamt-VS ist nach der Beitragsfreistellung NICHT
    # mehr die Todesfallleistung — und muss durchfallen.
    vs_ges = float(KLV_DEFAULT.sum_insured)
    assert abs(s_bfr - vs_ges) > 1.0
    mit_vs = (gevos[0], GeVoErwartung("TOD", 12 * a0 + 2, vs_ges))
    assert not pruefe_vertrag(
        _pruefung(gevos=mit_vs, dk2_fehlt=True))["bestanden"]


def test_tod_nach_erh_und_pex_summiert_die_beitragsfreien_summen() -> None:
    """Jede Scheibe zaehlt mit ihrer eigenen beitragsfreien Summe.

    Leistungshoehe als Addition dieses Tests (Summe ueber Grundvertrag
    und Scheibe, je ab IHREM Jahrestag), nicht als Kern-Aufruf der
    Suite.
    """
    a_erh, a_pex, s_neu = 8, 10, 5000.0
    m1, m2 = 12 * 7 + 5, 12 * 11 + 5
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, a_erh, s_neu))
    s_bfr = round(KERN.beitragsfreie_summe(a_pex)
                  + scheibe.beitragsfreie_summe(a_pex - a_erh), 2)
    gevos = (GeVoErwartung("ERH", 12 * a_erh, s_neu),
             GeVoErwartung("PEX", 12 * a_pex, s_bfr),
             GeVoErwartung("TOD", 12 * a_pex + 3, s_bfr))

    def _urteil(gevos_: Tuple[GeVoErwartung, ...]) -> Dict[str, Any]:
        return pruefe_vertrag(VertragsPruefung(
            police_id="P-ERH-PEX-TOD", model_point=MP,
            monate_stichtag_1=m1, monate_stichtag_2=m2,
            dk_erwartet_1=round(KERN.monatsreserve(m1).vx_mrv, 2),
            dk_erwartet_2=None, gevos=gevos_))

    urteil = _urteil(gevos)
    assert urteil["bestanden"], urteil["befunde"]
    # Kontrolle: nur die beitragsfreie Summe des Grundvertrags ist zu
    # klein — die Scheibe gehoert dazu.
    ohne_scheibe = round(KERN.beitragsfreie_summe(a_pex), 2)
    assert ohne_scheibe != s_bfr
    assert not _urteil(
        gevos[:2] + (GeVoErwartung("TOD", 12 * a_pex + 3, ohne_scheibe),)
    )["bestanden"]


def test_tod_bei_anfangs_beitragsfreiem_vertrag_zahlt_die_bfr_summe() -> None:
    """Auch der Anfangszustand ``beitragsfrei_seit_jahr`` traegt die Regel."""
    a0 = 5
    s_bfr = round(KERN.beitragsfreie_summe(a0), 2)
    urteil = pruefe_vertrag(_beitragsfrei_pruefung(
        a0, dk_erwartet_2=None,
        gevos=(GeVoErwartung("TOD", S1 + 3, s_bfr),)))
    assert urteil["bestanden"], urteil["befunde"]
    # Kontrolle: die Gesamt-VS faellt durch.
    assert not pruefe_vertrag(_beitragsfrei_pruefung(
        a0, dk_erwartet_2=None,
        gevos=(GeVoErwartung("TOD", S1 + 3,
                             float(KLV_DEFAULT.sum_insured)),)))["bestanden"]


# --------------------------------------------------------------------------- #
# Die Abgangsregel: TERMINAL steuert, es beschriftet nicht
# --------------------------------------------------------------------------- #


def _terminal_urteil(art: str, dk2: Optional[float]) -> Dict[str, Any]:
    """Urteil ueber einen Vertrag mit genau einem GeVo dieser Art.

    Der GeVo traegt einen korrekten Betrag, damit ausschließlich geprüft
    wird, ob die Art den Vertrag beendet.
    """
    if art == "ABL":
        return pruefe_vertrag(_ablauf_pruefung(
            (GeVoErwartung(
                "ABL", ABLAUF, float(KLV_DEFAULT.sum_insured)),),
            dk2=dk2))
    # PEX, ERH und RED wirken am Vertragsjahrestag; sie hier unterjaehrig
    # abzulegen erzeugte einen zweiten Befund und der Test bestuende aus
    # dem falschen Grund.
    monate = 12 * 10 if art in ("PEX", "ERH", "RED") else S1 + 4
    if art == "ERH":
        betrag = 5000.0
    elif art == "PEX":
        betrag = round(KERN.beitragsfreie_summe(monate // 12), 2)
    elif art == "STO":
        betrag = round(KERN.monatsreserve(monate).rkw, 2)
    elif art == "RED":
        # Die Herabsetzung traegt keinen verglichenen Betrag (O-7); was
        # sie braucht, ist der fortgefuehrte Anteil.
        return pruefe_vertrag(_pruefung(
            dk2=dk2, dk2_fehlt=dk2 is None,
            gevos=(GeVoErwartung("RED", monate, None, anteil=0.6),)))
    else:  # TOD
        betrag = float(KLV_DEFAULT.sum_insured)
    return pruefe_vertrag(_pruefung(
        dk2=dk2, dk2_fehlt=dk2 is None,
        gevos=(GeVoErwartung(art, monate, betrag),)))


@pytest.mark.parametrize("art", TERMINAL)
def test_terminale_arten_beenden_den_vertrag(art: str) -> None:
    """``TERMINAL`` IST die Abgangsregel, nicht ihre Beschriftung.

    Wird eine Art aus der Tabelle gestrichen, wird der korrekt
    abgegangene Vertrag zum Befund "kein Abgang" — dieser Test faellt
    dann. Wird eine nicht-terminale Art aufgenommen, faellt
    :func:`test_nicht_terminale_arten_beenden_den_vertrag_nicht`.
    """
    ohne_folgewert = _terminal_urteil(art, None)
    assert ohne_folgewert["bestanden"], ohne_folgewert["befunde"]
    mit_folgewert = _terminal_urteil(art, 12345.67)
    assert not mit_folgewert["bestanden"]
    assert any("abgegangen" in b for b in mit_folgewert["befunde"])


@pytest.mark.parametrize(
    "art", [a for a in GEVO_ARTEN if a not in TERMINAL])
def test_nicht_terminale_arten_beenden_den_vertrag_nicht(art: str) -> None:
    """PEX und ERH sind Statuswechsel bzw. Scheiben, kein Abgang."""
    urteil = _terminal_urteil(art, None)
    assert not urteil["bestanden"]
    assert any("keinen Abgang" in b for b in urteil["befunde"]), urteil


def test_terminaler_gevo_mit_befund_beendet_den_vertrag_nicht() -> None:
    """Ein ABL zur falschen Zeit ist kein Ablauf, also auch kein Abgang."""
    urteil = pruefe_vertrag(_pruefung(
        dk2_fehlt=True,
        gevos=(GeVoErwartung("ABL", S1 + 4,
                             float(KLV_DEFAULT.sum_insured)),)))
    assert not urteil["bestanden"]
    assert any("Versicherungsdauer" in b for b in urteil["befunde"])
    assert any("keinen Abgang" in b for b in urteil["befunde"]), urteil


def test_abgang_ist_die_pruefung_der_abbruch_ist_die_luecke() -> None:
    """Warum ``dk_stichtag_2`` nur im Abbruchpfad in ``nicht_geprueft`` steht.

    Beim abgegangenen Vertrag ist das fehlende Deckungskapital am
    Folgestichtag die gepruefte Aussage selbst (Abgang und Folgeabzug
    passen zusammen). Nach einem Abbruch ist ueber den Vertrag dagegen
    NICHTS bekannt — auch nicht, ob er abgegangen ist.
    """
    abgegangen = pruefe_bestand(
        [_pruefung(dk2_fehlt=True,
                   gevos=(GeVoErwartung(
                       "STO", S1 + 4,
                       round(KERN.monatsreserve(S1 + 4).rkw, 2)),))],
        erwartete_anzahl=1)
    urteil = abgegangen["vertraege"][0]
    assert urteil["bestanden"], urteil["befunde"]
    assert urteil["nicht_geprueft"] == ["bjb_stichtag_1"]

    kaputt = dataclasses.replace(
        _pruefung(), police_id="P-ABBRUCH", monate_stichtag_2=ABLAUF + 12)
    abbruch = pruefe_bestand([kaputt], erwartete_anzahl=1)["vertraege"][0]
    assert not abbruch["bestanden"]
    assert abbruch["nicht_geprueft"] == [
        "dk_stichtag_1", "bjb_stichtag_1", "dk_stichtag_2"]


def test_pex_nach_erhoehung_versetzt_den_jahrestag_der_scheibe() -> None:
    """Jede Scheibe zaehlt ab IHREM Jahrestag (pex_jahr - erh_jahr)."""
    a_erh, a_pex, s_neu = 8, 10, 5000.0
    # Beide Jahrestage muessen zwischen die Stichtage passen:
    m1, m2 = 12 * 7 + 5, 12 * 11 + 5
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, a_erh, s_neu))
    s_bfr = round(KERN.beitragsfreie_summe(a_pex)
                  + scheibe.beitragsfreie_summe(a_pex - a_erh), 2)
    gevos = (GeVoErwartung("ERH", 12 * a_erh, s_neu),
             GeVoErwartung("PEX", 12 * a_pex, s_bfr))
    dk2 = round(
        KERN.monatsreserve_beitragsfrei(a_pex, m2)
        + scheibe.monatsreserve_beitragsfrei(a_pex - a_erh, m2 - 12 * a_erh),
        2)

    def _urteil(gevos_: Tuple[GeVoErwartung, ...]) -> Dict[str, Any]:
        return pruefe_vertrag(VertragsPruefung(
            police_id="P-ERH-PEX", model_point=MP,
            monate_stichtag_1=m1, monate_stichtag_2=m2,
            dk_erwartet_1=round(KERN.monatsreserve(m1).vx_mrv, 2),
            dk_erwartet_2=dk2, gevos=gevos_))

    urteil = _urteil(gevos)
    assert urteil["bestanden"], urteil["befunde"]
    # Kontrolle: OHNE den Versatz (Scheibe am Jahrestag des
    # Grundvertrags bewertet) stimmt die beitragsfreie Summe nicht.
    ohne_versatz = round(KERN.beitragsfreie_summe(a_pex)
                         + scheibe.beitragsfreie_summe(a_pex), 2)
    assert ohne_versatz != s_bfr
    assert not _urteil(
        (gevos[0], GeVoErwartung("PEX", 12 * a_pex, ohne_versatz)))["bestanden"]


# --------------------------------------------------------------------------- #
# Anfangszustand: am Migrationsstichtag bereits beitragsfrei
# --------------------------------------------------------------------------- #


def _beitragsfrei_pruefung(a0: int, **override) -> VertragsPruefung:
    """Prüfauftrag eines am Migrationsstichtag beitragsfreien Vertrags.

    Die Erwartungswerte werden nur berechnet, wenn der Testfall sie
    nicht selbst setzt — sonst laege der Kern-Aufruf VOR der Prüfung,
    die er auslösen soll.
    """
    basis: Dict[str, Any] = dict(
        police_id="P-BFR", model_point=MP,
        monate_stichtag_1=S1, monate_stichtag_2=S2,
        bjb_erwartet_1=0.0, beitragsfrei_seit_jahr=a0,
    )
    basis.update(override)
    if "dk_erwartet_1" not in basis:
        basis["dk_erwartet_1"] = round(
            KERN.monatsreserve_beitragsfrei(a0, basis["monate_stichtag_1"]), 2)
    if "dk_erwartet_2" not in basis:
        basis["dk_erwartet_2"] = round(
            KERN.monatsreserve_beitragsfrei(a0, basis["monate_stichtag_2"]), 2)
    return VertragsPruefung(**basis)


def test_bereits_beitragsfreier_vertrag_laeuft_auf_dem_bfr_track() -> None:
    a0 = 5
    urteil = pruefe_vertrag(_beitragsfrei_pruefung(a0))
    assert urteil["bestanden"], urteil["befunde"]
    # Kontrolle: der beitragspflichtige Track ergibt andere Werte —
    # ein Vertrag, der als aktiv bewertet wuerde, faellt durch.
    aktiv_1 = round(KERN.monatsreserve(S1).vx_mrv, 2)
    assert aktiv_1 != round(KERN.monatsreserve_beitragsfrei(a0, S1), 2)
    assert not pruefe_vertrag(
        _beitragsfrei_pruefung(a0, dk_erwartet_1=aktiv_1))["bestanden"]
    # ... und beitragsfrei heisst: kein Jahresbeitrag.
    assert not pruefe_vertrag(_beitragsfrei_pruefung(
        a0, bjb_erwartet_1=round(KERN.gross_annual_premium(), 2)
    ))["bestanden"]


def test_beitragsfreistellung_nach_dem_stichtag_ist_kein_anfangszustand(
) -> None:
    """Der Fehler nennt den Ausweg: als PEX-GeVo liefern."""
    zu_spaet = _beitragsfrei_pruefung(
        S1 // 12 + 1, dk_erwartet_1=1.0, dk_erwartet_2=1.0)
    with pytest.raises(ValueError, match="als PEX-GeVo liefern"):
        pruefe_vertrag(zu_spaet)
    with pytest.raises(ValueError, match="kein Vertragsjahr"):
        pruefe_vertrag(_beitragsfrei_pruefung(
            0, dk_erwartet_1=1.0, dk_erwartet_2=1.0))
    # Die Suite macht daraus den Befund GENAU DIESES Vertrags:
    ergebnis = pruefe_bestand([zu_spaet], erwartete_anzahl=1)
    assert ergebnis["fehlgeschlagen"] == 1
    assert any("als PEX-GeVo liefern" in b
               for b in ergebnis["vertraege"][0]["befunde"])


def test_zweite_beitragsfreistellung_ist_ein_befund() -> None:
    urteil = pruefe_vertrag(_beitragsfrei_pruefung(
        5, gevos=(GeVoErwartung("PEX", 12 * 10, 1000.0),)))
    assert not urteil["bestanden"]
    assert any("bereits seit Jahr 5 beitragsfrei" in b
               for b in urteil["befunde"]), urteil["befunde"]


def test_erhoehung_nach_bereits_erfolgter_beitragsfreistellung_ist_befund(
) -> None:
    urteil = pruefe_vertrag(_beitragsfrei_pruefung(
        5, gevos=(GeVoErwartung("ERH", 12 * 10, 5000.0),)))
    assert not urteil["bestanden"]
    assert any("nur auf dem beitragspflichtigen Track" in b
               for b in urteil["befunde"]), urteil["befunde"]


def test_suite_schreibt_scope_bindung_nur_als_vollstaendigen_vertrag() -> None:
    system = {
        "commit": "abc1234",
        "branch": "test",
        "dirty": "nein",
        "quellcode_sha256": "b" * 64,
    }
    ergebnis = pruefe_bestand(
        [_pruefung()],
        erwartete_anzahl=1,
        stichtag_1="2026-01-01",
        stichtag_2="2027-01-01",
        bestand_sha256="a" * 64,
        system=system,
    )
    assert {
        name: ergebnis[name]
        for name in ("stichtag_1", "stichtag_2", "bestand_sha256")
    } == {
        "stichtag_1": "2026-01-01",
        "stichtag_2": "2027-01-01",
        "bestand_sha256": "a" * 64,
    }
    assert ergebnis["system"] == system
    with pytest.raises(ValueError, match="verlangt gemeinsam"):
        pruefe_bestand([_pruefung()], stichtag_1="2026-01-01")
    with pytest.raises(ValueError, match="muss nach"):
        pruefe_bestand(
            [_pruefung()], stichtag_1="2027-01-01", stichtag_2="2026-01-01",
            bestand_sha256="a" * 64,
        )
    with pytest.raises(ValueError, match="system muss exakt"):
        pruefe_bestand([_pruefung()], system={"commit": "abc"})


# --------------------------------------------------------------------------- #
# Herabsetzung (RED): geprueft wird die Zulaessigkeit, nicht der Wert
# --------------------------------------------------------------------------- #


def _red_urteil(monate: int = 12 * 10, anteil: Optional[float] = 0.6,
                vorher: Tuple[GeVoErwartung, ...] = ()) -> Dict[str, Any]:
    return pruefe_vertrag(_pruefung(
        gevos=vorher + (GeVoErwartung("RED", monate, None, anteil=anteil),)))


def test_red_weist_den_folgestichtag_als_pruefluecke_aus() -> None:
    """Der Kern kann einen herabgesetzten Vertrag nicht fortschreiben.

    Er wuerde ihn auf der urspruenglichen Summe rechnen — also auf einem
    Vertrag, den es nicht mehr gibt. Eine ausgewiesene Luecke ist
    ehrlicher als eine Zahl, die aussieht als sei sie geprueft
    (dev-docs/zahlungspfade-migrierter-vertraege.md).
    """
    urteil = _red_urteil()

    assert urteil["bestanden"], urteil["befunde"]
    assert any("dk_stichtag_2_nach_red" in luecke
               for luecke in urteil["nicht_geprueft"]), urteil["nicht_geprueft"]
    # Und der Wert wird eben NICHT als bestandene Pruefung ausgewiesen.
    assert "dk_stichtag_2" not in [p["groesse"] for p in urteil["pruefungen"]]


def test_red_am_ersten_stichtag_wird_weiter_geprueft() -> None:
    """Nur der Wert NACH der Herabsetzung faellt aus, nicht der davor."""
    urteil = _red_urteil()

    assert "dk_stichtag_1" in [p["groesse"] for p in urteil["pruefungen"]]


def test_red_unterjaehrig_ist_ein_befund() -> None:
    urteil = _red_urteil(monate=S1 + 4)

    assert not urteil["bestanden"]
    assert any("Vertragsjahrestag" in b for b in urteil["befunde"]), urteil


def test_red_nach_beitragsfreistellung_ist_ein_befund() -> None:
    """Ein beitragsfreier Vertrag hat keinen Beitrag, den man senken kann."""
    pex = GeVoErwartung("PEX", 12 * 10, round(KERN.beitragsfreie_summe(10), 2))
    urteil = _red_urteil(monate=12 * 10, vorher=(pex,))

    assert not urteil["bestanden"]
    assert any("beitragsfrei" in b for b in urteil["befunde"]), urteil


def test_red_ohne_anteil_ist_eine_luecke_kein_befund() -> None:
    """Die Lieferung ist unvollstaendig, aber der Vertrag nicht falsch."""
    urteil = _red_urteil(anteil=None)

    assert urteil["bestanden"], urteil["befunde"]
    assert any("anteil" in luecke for luecke in urteil["nicht_geprueft"])


@pytest.mark.parametrize("anteil", [-0.1, 1.5])
def test_red_mit_unmoeglichem_anteil_ist_ein_befund(anteil: float) -> None:
    urteil = _red_urteil(anteil=anteil)

    assert not urteil["bestanden"]
    assert any("[0, 1]" in b for b in urteil["befunde"]), urteil


def test_red_beendet_den_vertrag_nicht() -> None:
    """Sie ist eine Aenderung, kein Abgang — der Vertrag steht weiter."""
    urteil = _terminal_urteil("RED", None)

    assert not urteil["bestanden"]
    assert any("keinen Abgang" in b for b in urteil["befunde"]), urteil
