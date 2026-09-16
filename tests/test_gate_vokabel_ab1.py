"""Die Vokabel der zeichenbaren Gates kommt aus EINER Quelle.

Beim Bau der Auslieferungs-Abnahme ``A-B1`` fiel auf, dass dieselbe
Menge zweimal im Baum stand: ``zeichnung.GUELTIGE_GATES`` (massgeblich
fuer die gates-Listen der Zeichnungsordnung und fuer die CLI-Auswahl des
Entscheid-Kommandos) und ``schemas.P9_GATES`` (massgeblich fuer die
Snapshot-Validierung). Wer ein Gate nur in eine der beiden eintraegt,
bekommt eines, das die CLI annimmt und das Schema ablehnt — oder
umgekehrt.

Dazu die Regel, die ohne Test eine Absichtserklaerung bliebe: Ein
zeichenbares Gate ohne Belegvertrag koennte zwar gezeichnet werden, aber
niemand wuesste, worauf sich die Unterschrift stuetzt.

Knoten: system/entscheid
"""

from __future__ import annotations

import pytest

from rechner_pipeline.fall import FALL_SCOPES, FallFehler, belegrollen
from rechner_pipeline.models.schemas import P9_GATES
from rechner_pipeline.models.zeichnung import (
    GUELTIGE_GATES,
    SCHLUESSELKLASSEN,
    ZEICHNENDE_KLASSEN,
)


def test_beide_gate_listen_sind_dieselbe():
    """Abgeleitet, nicht abgetippt — sonst laufen sie auseinander."""
    assert P9_GATES == GUELTIGE_GATES
    assert P9_GATES is GUELTIGE_GATES, (
        "P9_GATES soll GUELTIGE_GATES sein, nicht eine gleich aussehende "
        "zweite Liste")


#: Zeichenbare Gates OHNE Belegvertrag — benannt, nicht uebersehen.
#:
#: ``A-Q1`` (Quellenabnahme) stuetzt sich nicht auf Dateirollen im Fall,
#: sondern auf den A-Box-Stand, den der Entscheid selbst pinnt: A-M4
#: verlangt spaeter einen geltenden, signierten A-Q1-Snapshot AUF
#: DIESEM Stand (gate_entscheid.py, "A-M4 nimmt denselben Stand ab, den
#: A-Q1 gesehen hat"). Die Bindung existiert also, sie laeuft nur nicht
#: ueber BELEGROLLEN.
#:
#: Hier stehen NUR begruendete Ausnahmen. Eine Liste, die Ausnahmen und
#: Versehen mischt, verliert ihre Aussage — man sieht ihr nicht mehr an,
#: ob sie waechst, weil es mehr Ausnahmen gibt oder weil jemand einen
#: Vertrag vergessen hat.
OHNE_BELEGVERTRAG = {"A-Q1"}


def test_jedes_zeichenbare_gate_hat_einen_belegvertrag():
    """Eine Unterschrift ohne Belegvertrag stuetzt sich auf nichts —
    ausser dort, wo die Bindung nachweislich anders laeuft."""
    for gate in GUELTIGE_GATES:
        if gate in OHNE_BELEGVERTRAG:
            continue
        for scope in FALL_SCOPES:
            rollen = belegrollen(gate, scope)   # wirft, wenn er fehlt
            assert isinstance(rollen, list)


def test_die_ausnahmeliste_nennt_nur_wirkliche_ausnahmen():
    """Positivkontrolle der Liste: Ein Gate, das einen Vertrag HAT, darf
    nicht darin stehen — sonst waere die Ausnahme eine Tarnung."""
    for gate in OHNE_BELEGVERTRAG:
        assert gate in GUELTIGE_GATES, gate
        with pytest.raises(FallFehler):
            belegrollen(gate, "bestand")


def test_ein_unbekanntes_gate_hat_keinen_vertrag():
    """Positivkontrolle: Der Test oben prueft wirklich etwas."""
    with pytest.raises(FallFehler, match="kein Belegrollen-Vertrag"):
        belegrollen("A-X9", "bestand")


def test_die_auslieferung_ist_zeichenbar_und_belegt():
    """A-B1 zeichnet den Akt, nicht die Zahlen: Der einzige Pflichtbeleg
    ist der Ankersatz des Pakets. Was fachlich abgenommen ist, liegt
    bereits gezeichnet IM Paket (A-M1 bis A-M4)."""
    assert "A-B1" in GUELTIGE_GATES
    assert belegrollen("A-B1", "bestand") == ["anker"]
    # Ein Tarif-Fall liefert keinen Bestand aus.
    assert belegrollen("A-B1", "tarif") == []


def test_agenten_zeichnen_keine_abnahme():
    """ADR-018, Nachtrag 2026-09-16: Die Klasse ``agent`` steht weiter
    NICHT unter den zeichnenden — was ein Agent zeichnet (den Ankersatz),
    ist kein Gate. Die Praezisierung betrifft den Text der Regel, nicht
    ihre Durchsetzung."""
    assert "agent" in SCHLUESSELKLASSEN
    assert "agent" not in ZEICHNENDE_KLASSEN
    assert set(ZEICHNENDE_KLASSEN) == {"mensch", "simulation"}
