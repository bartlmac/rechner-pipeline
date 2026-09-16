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


# ---------------------------------------------------------------------
# Die Klasse, die zweimal zugeschlagen hat (2026-09-16)
#
# Beim ersten Mal war es die Liste der Gates selbst — der Kommentar ueber
# P9_AKTUARIELLE_ABNAHMEN haelt es fest: "Eine vierte Liste derselben
# Gates war genau der Grund, warum A-M2 zwar entschieden, aber nicht
# gespeichert werden konnte." Beim zweiten Mal, mit A-B1, eine Ebene
# tiefer: die Liste der Gates MIT Pflichtbelegen, gefuehrt als Literal an
# sechs Stellen. A-B1 stand in keiner, und das Entscheid-Kommando
# rechnete den Ankersatz aus, ohne ihn in den signierten Inhalt zu
# schreiben.
#
# Ein Kommentar, der eine Invariante beschreibt, erzwingt sie nicht.
# ---------------------------------------------------------------------

import ast
from pathlib import Path

from rechner_pipeline.fall import BELEGROLLEN
from rechner_pipeline.models.schemas import P9Snapshot
from rechner_pipeline.models.zeichnung import (
    GATES_MIT_PFLICHTBELEGEN,
    GATES_OHNE_BELEGVERTRAG,
)

SRC = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"


def test_die_menge_deckt_sich_mit_dem_belegvertrag():
    """Die eigentliche Ratsche, und die einzige nicht-zirkulaere:

    ``GATES_MIT_PFLICHTBELEGEN`` lebt in models (das Schema darf fall
    nicht importieren), ``BELEGROLLEN`` in fall. Wer kuenftig einem Gate
    einen Belegvertrag gibt, ohne die Menge zu erweitern — oder
    umgekehrt —, faellt hier auf, nicht erst an einem stillen Snapshot.
    """
    assert set(GATES_MIT_PFLICHTBELEGEN) == set(BELEGROLLEN)


def test_die_ausnahme_steht_nur_an_einer_stelle():
    """Positivkontrolle: dieselbe Ausnahme, zweimal notiert, waere schon
    wieder die Klasse."""
    assert set(GATES_OHNE_BELEGVERTRAG) == OHNE_BELEGVERTRAG
    assert set(GATES_MIT_PFLICHTBELEGEN) | OHNE_BELEGVERTRAG == set(GUELTIGE_GATES)


def _nutzlast(gate: str) -> dict:
    # A-M4 traegt pk1_belege als eigenes Pflichtfeld; ohne es bricht die
    # Validierung vor der Scope-Pruefung ab und der Test waere blind.
    zusatz = {"pk1_belege": {}} if gate == "A-M4" else {}
    return zusatz | {
        "schema_version": 7, "command": "gate_entscheid",
        "gate_version": "1.0.0", "gate": gate, "entscheid": "abgelehnt",
        "entscheider": "Probe", "rolle": "mensch/aktuariat",
        "begruendung": "Probe", "fall": "x", "artefakt_hashes": {},
        "system": {}, "vorgaenger": None,
        "entschieden_am": "2026-09-16T10:00:00Z",
        "snapshot_sha256": "0" * 64,
        "fall_scope": "bestand", "pflichtbelege": {"irgendeine": ["a" * 64]},
    }


def test_jedes_gate_mit_pflichtbelegen_darf_sie_im_snapshot_tragen():
    """Der Test, der A-B1 gefangen haette.

    Vorher: A-B1 MIT Pflichtbelegen -> "unknown fields: ['fall_scope',
    'pflichtbelege']". Das Schema segnete genau den LEEREN Beleg ab und
    wies den vollstaendigen zurueck.
    """
    for gate in GATES_MIT_PFLICHTBELEGEN:
        unbekannt = [
            f for f in P9Snapshot.validate_payload(_nutzlast(gate))
            if "unknown" in f.lower()
        ]
        assert not unbekannt, (gate, unbekannt)


def test_der_inhalt_wird_fuer_jedes_dieser_gates_auch_geprueft():
    """Pflichtfeld ohne Inhaltspruefung ist eine halbe Zusicherung:
    A-M2/A-M3 mussten fall_scope tragen, durften aber jeden Wert tragen.
    """
    for gate in GATES_MIT_PFLICHTBELEGEN:
        nutzlast = _nutzlast(gate) | {"fall_scope": "voellig-frei-erfunden"}
        assert any(
            "fall_scope" in f for f in P9Snapshot.validate_payload(nutzlast)
        ), gate


#: Literale Gate-Tupel, die BLEIBEN duerfen, mit Grund. Alles andere in
#: diesen beiden Dateien ist ein Rueckfall in die Klasse.
ERLAUBTE_LITERALE = {
    # Die drei aktuariellen Abnahmen: eine echte fachliche Teilmenge mit
    # eigener Deklaration (P9_AKTUARIELLE_ABNAHMEN), von gate_entscheid
    # importiert statt kopiert. Keine driftende Menge.
    ("A-M1", "A-M2", "A-M3"),
    # Die Nicht-Leer-Regel gilt bewusst nicht ueberall: A-M1 darf im
    # Tarif-Scope belegfrei angenommen werden, A-B1 hat dort gar keine
    # Rollen. Die exakte Rollenmenge erzwingt der Lesepfad.
    ("A-M4", "A-O1", "A-K2"),
}


def _gate_tupel(datei: Path) -> set:
    baum = ast.parse(datei.read_text(encoding="utf-8"))
    gefunden = set()
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Tuple):
            continue
        werte = [e.value for e in knoten.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)]
        if len(werte) == len(knoten.elts) and len(werte) >= 2 and all(
            w in GUELTIGE_GATES for w in werte
        ):
            gefunden.add(tuple(werte))
    return gefunden


def test_keine_neue_abgetippte_gate_menge():
    """Der Detektor gegen den dritten Vorfall.

    Er findet jedes Tupel aus zwei oder mehr Gate-Kennungen in den beiden
    Dateien, die die Klasse zweimal getroffen hat. Waechst die Menge,
    steht entweder eine neue Ausnahme mit Begruendung in
    ERLAUBTE_LITERALE — oder jemand hat wieder abgetippt.
    """
    gefunden = set()
    for name in ("models/schemas.py", "gates/gate_entscheid.py"):
        gefunden |= _gate_tupel(SRC / name)
    assert gefunden == ERLAUBTE_LITERALE, (
        "abgetippte Gate-Mengen gefunden: "
        f"{sorted(gefunden - ERLAUBTE_LITERALE)}; verschwunden: "
        f"{sorted(ERLAUBTE_LITERALE - gefunden)}"
    )
