"""T26-11, Folgeauftrag: das realistisch parametrierte Herabsetzungs-Fixture.

Die Befundliste hatte "die Herabsetzung HEBT die Versicherungssumme"
(+202.338) als fachliche Frage gefuehrt. Nachgemessen war es ein Artefakt
des Mechanik-Fixtures: ``rho = 0.04`` ist rund vier Millionen Mal groesser
als jede reale Korrekturschicht (baldrian: rho 1e-8 bis 1e-9,
Rundungsresiduen — der Entscheid vom 2026-09-15 meinte Cent-Betraege).
Ohne Schicht senkt die Herabsetzung. Entscheid des Maintainers
2026-09-22: das Fixture fachlich vernuenftig ausgestalten, damit die
RICHTUNG bindbar wird und die Frage bei der naechsten Pruefung nicht
wiederkommt — als ZWEITES Fixture, denn die Mechanik-Probe der Absorption
braucht weiter eine sichtbare Schicht (bei 1e-8 saehe kein Test sie).

Knoten: klv
"""

from __future__ import annotations

import pandas as pd

from rechner_pipeline.bestand.ereignisse import fortschreiben
from tests.test_bestand_uebernommen_fortschreiben import _stamm
from tests.test_herabsetzung_in_fuehrung import ANTEIL, BIS, POLICEN, _config
from tests.test_schicht_in_fuehrung import _tabellen

#: Groessenordnung des echten Falls (faelle/baldrian-klv-tg2015-lauf2,
#: 834 Vertraege): rho in 1e-8..1e-9. Hier ein Wert aus dieser Spanne.
RHO_REAL = 2.0e-8


def _welt(rho: float):
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN, rho=rho)
    erg = fortschreiben(stamm, _config(True), BIS, schichten=schichten, verankerung=verankerung)
    led = erg.ledger
    red = led[(led["ereignis"] == "RED") & (led["betrag_art"] == "VS_herabsetzung")]
    absorb = led[(led["ereignis"] == "RED") & (led["betrag_art"] == "dDK_absorption")]
    zeilen = []
    for z in red.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["vertragsjahr"])
        erh = led[(led["police_id"] == pid) & (led["ereignis"] == "ERH")
                  & (led["betrag_art"] == "VS_erhoehung") & (led["vertragsjahr"] < jahr)]
        vorher = 100_000.0 + float(erh["betrag"].sum())
        schicht = float(absorb[(absorb["police_id"] == pid)]["betrag"].sum())
        zeilen.append((pid, jahr, vorher, float(z["betrag"]), schicht))
    return zeilen


def test_mit_realistischer_schicht_senkt_die_herabsetzung_immer():
    """Bindet die RICHTUNG: bei einer Schicht in der Groessenordnung des
    echten Falls liegt die neue Gesamtsumme unter der alten — fuer jede
    Herabsetzung des Fixtures. Zusicherungen statt Skip: es gibt
    Herabsetzungen, und die absorbierte Schicht ist wirklich Cent-gross.

    Mutationsprobe: RHO_REAL auf 0.04 (das Mechanik-Fixture) -> rot; die
    Absorption in ``herabsetzen`` verdoppeln -> bei RHO_REAL bleibt es
    gruen (das ist der Punkt: die Richtung haengt nicht an der Schicht),
    beim Mechanik-Fixture unten aber rot."""
    zeilen = _welt(RHO_REAL)
    assert len(zeilen) >= 5, "Fixture ohne Herabsetzungen bezeugt nichts"
    for pid, jahr, vorher, nachher, schicht in zeilen:
        assert 0.0 < schicht < 0.05, (pid, schicht, "Schicht ist nicht Cent-gross")
        assert nachher < vorher, (pid, jahr, vorher, nachher)
    # Und die Summe ueber alle Jahre faellt — das Gegenstueck zu "+202.338".
    assert sum(n - v for _, _, v, n, _ in zeilen) < 0.0


def test_das_mechanik_fixture_hebt_und_erklaert_damit_den_alten_befund():
    """Positivkontrolle des Artefakts: Mit rho = 0.04 (Mechanik-Fixture,
    ~4 Mio x real) HEBT dieselbe Rechnung die Summe — genau die Zahl, die
    die Befundliste faelschlich als fachliche Frage fuehrte. Beide
    Fixtures zusammen halten fest: die Richtung ist eine Eigenschaft der
    Schicht-Groesse, nicht des Verfahrens."""
    zeilen = _welt(0.04)
    assert len(zeilen) >= 5
    assert all(schicht > 1000.0 for *_, schicht in zeilen), "die Mechanik-Schicht ist absichtlich gross"
    assert sum(n - v for _, _, v, n, _ in zeilen) > 0.0
