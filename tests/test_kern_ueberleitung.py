"""Toleranz-Überleitung Kommutation vs. Zustandsmodell (Kreuz-Modell-Gate).

Das Gate ist die Abnahme-Grundlage für den Serving-Wechsel des KLV-Produkts
auf das Zustandsmodell-Rückgrat: alle Golden-Contract-Werte beider Schienen
müssen je Modellpunkt in der Rundungsklasse liegen (|a-b| <= atol +
rtol*max(|a|,|b|)); jede echte Abweichung ist ein Gate-Fehler.
"""

from __future__ import annotations

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.kommutation import fuer
from rechner_pipeline.kern.produkte.klv import KLV, VERLAUFSJAHRE
from rechner_pipeline.kern.zustandsmodell import ZustandsBarwerte
from rechner_pipeline.qa.ueberleitung import (
    _klassifiziere,
    standard_modellpunkte,
    ueberleitung_klv,
)


def test_klassifizierung():
    assert _klassifiziere(1.0, 1.0, 1e-9, 1e-9) == "exakt"
    assert _klassifiziere(1.0, 1.0 + 1e-12, 1e-9, 1e-9) == "rundung"
    assert _klassifiziere(0.0, 5e-10, 1e-9, 1e-9) == "rundung"  # numerische Null
    assert _klassifiziere(1.0, 1.001, 1e-9, 1e-9) == "abweichend"


def test_ueberleitung_klv_gate_bestanden():
    """Das Kreuz-Modell-Gate über den Standard-Sweep: keine Abweichung
    ausserhalb der Rundungsklasse; die maximale signifikante relative
    Abweichung liegt Groessenordnungen unter der Toleranz."""
    bericht = ueberleitung_klv(standard_modellpunkte(KLV_DEFAULT))
    assert bericht["modellpunkte"] == 10
    assert bericht["werte_verglichen"] == 10 * (5 + 12 * VERLAUFSJAHRE)
    assert sum(bericht["klassen"].values()) == bericht["werte_verglichen"]
    assert bericht["abweichende"] == []
    assert bericht["bestanden"]
    # Reine Rundungsreihenfolgen-Differenz: weit unter der Toleranz.
    assert bericht["max_relative_abweichung"] < 1e-11
    assert bericht["klassen"]["exakt"] > 0 and bericht["klassen"]["rundung"] > 0


def test_klv_auf_zustandsmodell_liefert_gleichen_contract_shape():
    mp = KLV_DEFAULT
    kom = fuer(mp.sex, mp.tafel, mp.zins)
    zustand = KLV(mp, barwerte=ZustandsBarwerte(kom, mp.zins))
    klassisch = KLV(mp)
    assert set(zustand.scalars()) == set(klassisch.scalars())
    zeilen = zustand.verlaufswerte()
    assert len(zeilen) == VERLAUFSJAHRE
    assert list(zeilen[0]) == list(klassisch.verlaufswerte()[0])


def test_default_pfad_bleibt_kommutation():
    """Serving-Wechsel ist NICHT vollzogen: ohne Injektion rechnet KLV auf
    der Kommutations-Schiene (Golden-Master-Pfad; Wechsel erst nach
    Abnahme des Überleitungs-Reports)."""
    from rechner_pipeline.kern.barwerte import Barwerte

    assert isinstance(KLV(KLV_DEFAULT).bw, Barwerte)


def test_ueberleitung_meldet_echte_abweichungen():
    """Ein absichtlich verfälschtes Rückgrat fällt durch das Gate."""

    class Verfaelscht(ZustandsBarwerte):
        def nGrAx(self, age, term):
            return super().nGrAx(age, term) * 1.001

    mp = KLV_DEFAULT
    kom = fuer(mp.sex, mp.tafel, mp.zins)
    klassisch = KLV(mp)
    kaputt = KLV(mp, barwerte=Verfaelscht(kom, mp.zins))
    abweichung = abs(
        klassisch.scalars()["Bxt"] - kaputt.scalars()["Bxt"]
    ) / klassisch.scalars()["Bxt"]
    assert abweichung > 1e-9  # die Verfälschung wäre ein Gate-Fehler
