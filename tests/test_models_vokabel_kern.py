"""Die Vokabel der Nebentabellen gegen die Zustaende der Kern-Modelle (Betriebsbefund N-01).

``models.bestand`` fuehrt die Vokabel der Korrekturschicht und der
Verankerung als Literal, damit Gate, P-B1-Engine und Betriebseingang sie
ohne den Kern pruefen koennen. Der Kern ist trotzdem die Quelle:
``verankerungszustand`` ist der Startzustand der Schicht im Zustandsmodell
des Produkts, also ein Erlebenszustand der Kapitalversicherung oder der
Berufsunfaehigkeit. Laeuft die Liste dem Kern davon, faellt es hier —
nicht erst vier Schichten tiefer mit "Unbekannter Startzustand".

Knoten: klv, bu
"""

from __future__ import annotations

from rechner_pipeline.kern.produkte import bu
from rechner_pipeline.kern.zustandsmodell import ZustandsBarwerte
from rechner_pipeline.models.bestand import VERANKERUNGSZUSTAENDE, ZUSTAENDE_TA


def test_verankerungszustaende_sind_die_erlebenszustaende_der_kern_modelle():
    erleben = {ZustandsBarwerte.AKTIV, bu.AKTIV, bu.BU_ZUSTAND} - {ZustandsBarwerte.TOT, bu.TOT}
    assert set(VERANKERUNGSZUSTAENDE) == erleben
    assert ZustandsBarwerte.TOT not in VERANKERUNGSZUSTAENDE


def test_zustand_ta_spricht_die_sprache_der_uebernahme():
    """Beitragsfreiheit ist eine Eigenschaft des Modellpunkts, kein Zustand des
    Modells — deshalb zwei Vokabeln, die sich nicht ueberschneiden."""
    assert ZUSTAENDE_TA == ("beitragspflichtig", "beitragsfrei")
    assert not set(ZUSTAENDE_TA) & set(VERANKERUNGSZUSTAENDE)
