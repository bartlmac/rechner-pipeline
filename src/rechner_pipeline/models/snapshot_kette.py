"""Die Vorgaengerkette der P9-Snapshots eines Gates — EIN Vertrag fuer beide Leser.

Das Gate (gates.gate_entscheid) liest die Kette, um die geltende Spitze
zu bestimmen, bevor es entscheidet (ADR-008). Der Betriebseingang
(betrieb.uebernahme) las bis zur Pruefrunde T27 nur EINE Datei: Schema,
Selbstadressierung, Signatur, Gate, Entscheid, Fallbindung — und
registrierte einen alten angenommenen Snapshot, obwohl eine Ablehnung mit
Vorgaengerbezug laengst die geltende Spitze war (Befund T27-05). Die
kryptografische Echtheit eines Belegs ersetzt seine Gueltigkeit nicht.

Damit beide dieselbe Antwort geben, steht die Graphpruefung hier, in
models — wie die Belegrollen und die Freigabe (ADR-021): betrieb darf
gates nicht importieren (Schichtenkarte), und eine zweite Abschrift der
Regel waere genau die Drift, die der Befund zeigt.

Knoten: system/entscheid
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple


def pruefe_snapshot_graph(
    snapshots: Mapping[str, Mapping[str, Any]],
    namen: Optional[Mapping[str, str]] = None,
) -> Tuple[List[str], List[str]]:
    """Vorgaenger-Existenz, Zyklen und die eindeutige geltende Spitze.

    ``snapshots``: Snapshot-Hash -> Snapshot-Daten (mit ``vorgaenger``).
    ``namen``: Hash -> Anzeigename fuer Meldungen (Vorgabe: der Hash).
    Rueckgabe ``(spitzen, fehler)``; ``spitzen`` sind die Hashes, auf die
    kein anderer Snapshot als Vorgaenger zeigt. Bei einer nichtleeren
    Kette muss es genau eine Spitze geben.
    """
    fehler: List[str] = []
    name = (namen or {}).get

    def _name(sha: str) -> str:
        return name(sha, sha)

    for sha, daten in snapshots.items():
        for vorgaenger in daten["vorgaenger"]:
            if vorgaenger not in snapshots:
                fehler.append(
                    f"{_name(sha)}: Vorgaenger {vorgaenger} existiert nicht"
                )
            if vorgaenger == sha:
                fehler.append(f"{_name(sha)}: Snapshot referenziert sich selbst")

    zustand: Dict[str, int] = {}

    def _besuche(sha: str) -> None:
        if zustand.get(sha) == 1:
            fehler.append(f"Vorgaengerkette enthaelt einen Zyklus bei {sha}")
            return
        if zustand.get(sha) == 2:
            return
        zustand[sha] = 1
        for vorgaenger in snapshots[sha]["vorgaenger"]:
            if vorgaenger in snapshots:
                _besuche(vorgaenger)
        zustand[sha] = 2

    for sha in snapshots:
        _besuche(sha)

    referenziert = {
        vorgaenger
        for daten in snapshots.values()
        for vorgaenger in daten["vorgaenger"]
    }
    spitzen = sorted(set(snapshots) - referenziert)
    if snapshots and len(spitzen) != 1:
        fehler.append(
            "Vorgaengerkette braucht genau eine eindeutige Spitze; "
            f"gefunden: {spitzen}"
        )
    return spitzen, fehler


def nachfolger_von(
    snapshots: Mapping[str, Mapping[str, Any]], sha: str
) -> List[str]:
    """Die Snapshots, die ``sha`` als Vorgaenger nennen (sortiert)."""
    return sorted(s for s, d in snapshots.items() if sha in d["vorgaenger"])
