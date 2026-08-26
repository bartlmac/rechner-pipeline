"""Aktuarieller Test: Vergleich je Vertrag am eigenen t_a (qa/aktuarieller_test).

Wie in test_migrationssuite gilt: Erwartungswerte der gruenen Pfade
stammen aus demselben Kern (centgerundet) — geprueft wird das URTEIL und
die drei ADR-010-Invarianten: Rechenpunkt-Pflicht (keine Interpolation),
keine Summation der Vergleichsgroessen (nur Residuum-Verteilung), und
Stichproben-Vollstaendigkeit als eigene Bedeutung.

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
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL
from rechner_pipeline.qa.aktuarieller_test import (
    AktuartestFehler,
    VerankerungsPruefung,
    pruefe_stichprobe,
    pruefe_verankerung,
)
from rechner_pipeline.qa.stichprobe import Stichprobe, ziehe

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA = 12 * 9  # Verankerungszeitpunkt: neunter Jahrestag (Rechenpunkt)


def _auftrag(
    police_id: str = "P1",
    monate_ta: int = TA,
    historientyp: str = "ohne_gevo",
    erwartet: Optional[Dict[str, float]] = None,
    **kwargs: Any,
) -> VerankerungsPruefung:
    if erwartet is None:
        zeile = KERN.zustand_am(monate_ta)
        erwartet = {"kVx_MRV": round(zeile.vx_mrv, 2)}
    return VerankerungsPruefung(
        police_id=police_id,
        model_point=dict(MP),
        monate_ta=monate_ta,
        historientyp=historientyp,
        erwartet=erwartet,
        **kwargs,
    )


def _stichprobe(*police_ids: str) -> Stichprobe:
    return ziehe("vollbestand", list(police_ids))


# --------------------------------------------------------------------------- #
# Die drei Invarianten
# --------------------------------------------------------------------------- #


def test_vergleich_am_rechenpunkt_ist_bitidentisch_zur_jahreszeile():
    ergebnis = pruefe_verankerung(_auftrag())
    system = ergebnis["pruefungen"][0]["system"]
    assert system == KERN.verlaufszeile(TA // 12).vx_mrv
    assert ergebnis["bestanden"]


def test_unterjaehriges_ta_ist_harter_fehler_keine_interpolation():
    with pytest.raises(AktuartestFehler, match="Rechenpunkt"):
        pruefe_verankerung(_auftrag(monate_ta=TA + 5))


def test_engine_bildet_keine_bestandssummen():
    """Das Ergebnis kennt nur Verteilungsgroessen der |Residuen| — keine
    Deckungskapital-Summe, keinen Mittelwert, keinen Median."""
    ergebnis = pruefe_stichprobe(
        [_auftrag("P1"), _auftrag("P2")], _stichprobe("P1", "P2")
    )
    verteilung = ergebnis["verteilung"]
    assert set(verteilung) == {
        "anzahl_werte", "max_abs_residuum", "summe_abs_residuum",
        "p95_abs_residuum", "p99_abs_residuum",
    }
    flach = str(sorted(ergebnis))
    assert "dk_summe" not in flach and "mittelwert" not in flach


# --------------------------------------------------------------------------- #
# Urteil je Vertrag
# --------------------------------------------------------------------------- #


def test_abweichung_wird_als_residuum_ausgewiesen():
    zeile = KERN.zustand_am(TA)
    drift = round(zeile.vx_mrv + 10 * ABS_TOL, 2)
    ergebnis = pruefe_verankerung(_auftrag(erwartet={"kVx_MRV": drift}))
    assert not ergebnis["bestanden"]
    p = ergebnis["pruefungen"][0]
    assert p["residuum"] == pytest.approx(zeile.vx_mrv - drift)
    assert "kVx_MRV" in ergebnis["befunde"][0]


def test_beitragsfreier_vertrag_am_rechenpunkt():
    a0 = 5
    erwartet = {
        "kVx_MRV": round(KERN.reserve_beitragsfrei(a0, TA // 12), 2),
        "VS_bfr": round(KERN.beitragsfreie_summe(a0), 2),
        "BJB": 0.0,
    }
    ergebnis = pruefe_verankerung(
        _auftrag(erwartet=erwartet, beitragsfrei_seit_jahr=a0)
    )
    assert ergebnis["bestanden"], ergebnis["befunde"]


def test_scheiben_werden_vertragsweit_am_rechenpunkt_gerechnet():
    jahr, vs = 5, 10_000.0
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, jahr, vs))
    m = vertrags_monatsreserve(KERN, [(jahr, scheibe)], TA)
    ergebnis = pruefe_verankerung(
        _auftrag(
            erwartet={"kVx_MRV": round(m.vx_mrv, 2)},
            scheiben=((jahr, vs),),
        )
    )
    assert ergebnis["bestanden"], ergebnis["befunde"]
    # Kontrolle: die Grundvertrags-Zeile alleine MUSS fehlschlagen.
    kontrolle = pruefe_verankerung(
        _auftrag(
            erwartet={"kVx_MRV": round(KERN.zustand_am(TA).vx_mrv, 2)},
            scheiben=((jahr, vs),),
        )
    )
    assert not kontrolle["bestanden"]


def test_engine_vertrag_faellt_hart_aus():
    with pytest.raises(AktuartestFehler, match="unbekannte Groessen"):
        pruefe_verankerung(_auftrag(erwartet={"kVx_XYZ": 1.0}))
    with pytest.raises(AktuartestFehler, match="kein Testauftrag"):
        pruefe_verankerung(_auftrag(erwartet={}))
    with pytest.raises(AktuartestFehler, match="nur kVx_MRV und RKW"):
        pruefe_verankerung(
            _auftrag(erwartet={"BJB": 100.0}, scheiben=((5, 1000.0),))
        )
    with pytest.raises(AktuartestFehler, match="Vertragsende"):
        pruefe_verankerung(_auftrag(monate_ta=12 * (KLV_DEFAULT.n + 1)))


# --------------------------------------------------------------------------- #
# Stichprobe: Vollstaendigkeit, Isolation, Clusterung, Transport
# --------------------------------------------------------------------------- #


def test_stichprobe_vollstaendig_abgearbeitet_ist_die_definition():
    """Fehlender Auftrag = Mengenbefund; Nicht-Stichprobe = kein Befund."""
    stichprobe = _stichprobe("P1", "P2")
    unvollstaendig = pruefe_stichprobe([_auftrag("P1")], stichprobe)
    assert not unvollstaendig["stichprobe_vollstaendig"]
    assert not unvollstaendig["test_bestanden"]
    assert "ohne Pruefauftrag" in unvollstaendig["mengenbefunde"][0]

    # Ein Auftrag ausserhalb der Stichprobe ist nicht belegt:
    ueberzaehlig = pruefe_stichprobe(
        [_auftrag("P1"), _auftrag("P2"), _auftrag("P3")], stichprobe
    )
    assert not ueberzaehlig["stichprobe_vollstaendig"]

    # Exakt die Stichprobe: vollstaendig, bestanden, keine Befunde.
    exakt = pruefe_stichprobe([_auftrag("P1"), _auftrag("P2")], stichprobe)
    assert exakt["stichprobe_vollstaendig"]
    assert exakt["test_bestanden"]
    assert exakt["stichprobe"]["vollerhebung"] is True


def test_kranke_lieferdaten_werden_je_vertrag_isoliert():
    kaputt = VerankerungsPruefung(
        police_id="P2",
        model_point={**MP, "x": "vierzig"},
        monate_ta=TA,
        historientyp="ohne_gevo",
        erwartet={"kVx_MRV": 1.0},
    )
    ergebnis = pruefe_stichprobe(
        [_auftrag("P1"), kaputt], _stichprobe("P1", "P2")
    )
    assert ergebnis["fehlgeschlagen"] == 1
    p2 = next(v for v in ergebnis["vertraege"] if v["police_id"] == "P2")
    assert p2["befunde"][0].startswith("daten:")
    p1 = next(v for v in ergebnis["vertraege"] if v["police_id"] == "P1")
    assert p1["bestanden"]


def test_gruppen_clustern_nach_historientyp():
    ergebnis = pruefe_stichprobe(
        [
            _auftrag("P1", historientyp="ohne_gevo"),
            _auftrag("P2", historientyp="pex", monate_ta=TA,
                     erwartet={"BJB": 0.0}, beitragsfrei_seit_jahr=4),
        ],
        _stichprobe("P1", "P2"),
    )
    assert sorted(ergebnis["gruppen"]) == ["ohne_gevo", "pex"]
    assert ergebnis["gruppen"]["pex"]["anzahl"] == 1
    assert ergebnis["gruppen"]["ohne_gevo"]["max_abs_residuum"] <= ABS_TOL


def test_transportsicherung_ist_getrennt_und_nie_teil_des_urteils():
    ergebnis = pruefe_stichprobe(
        [_auftrag("P1")],
        _stichprobe("P1"),
        transportsicherung={"bestand_sha256": "ab" * 32, "zeilen": 999},
    )
    assert ergebnis["transportsicherung"] == {
        "bestand_sha256": "ab" * 32, "zeilen": 999,
    }
    # Auch eine offensichtlich falsche Transportangabe aendert das
    # fachliche Urteil nicht — sie wird ausgewiesen, nicht verrechnet.
    assert ergebnis["test_bestanden"]


def test_doppelte_auftraege_und_leere_liste_fallen_hart_aus():
    with pytest.raises(AktuartestFehler, match="doppelte"):
        pruefe_stichprobe(
            [_auftrag("P1"), _auftrag("P1")], _stichprobe("P1")
        )
    with pytest.raises(AktuartestFehler, match="leere Auftragsliste"):
        pruefe_stichprobe([], _stichprobe("P1"))


def test_ergebnis_ist_deterministisch():
    auftraege = [_auftrag("P1"), _auftrag("P2", historientyp="dyn",
                                          scheiben=((5, 10_000.0),),
                                          erwartet={"kVx_MRV": 1.0})]
    a = pruefe_stichprobe(auftraege, _stichprobe("P1", "P2"))
    b = pruefe_stichprobe(auftraege, _stichprobe("P1", "P2"))
    assert a == b
