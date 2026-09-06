"""Zeichnungsordnung — der paketuebergreifende Rollen-Datenvertrag.

Die Ordnung bindet ROLLEN an Schluessel-Fingerabdruecke und GATES an
Rollen. Sie lebt ausserhalb des frei editierbaren Falls (eine Ordnung,
die der Fall selbst umschreiben kann, ordnet nichts) und wird von ZWEI
Konsumenten gelesen: den P9-Gates (``gates.gate_entscheid``) und der
endgueltigen Diskrepanz-Aufloesung (``ontologie.entscheide``) — seit
dem Vier-Rollen-Modell des zweiten Laufs entscheidet dort die fachlich
zeichnende Rolle, nicht mehr nur "der Mensch". Deshalb liegt der
Vertrag in ``models/`` (paketuebergreifend), nicht in einer der beiden
Schichten: ``ontologie -> gates`` waere eine neue Architektur-Kante.

Rollen werden aus dem SCHLUESSEL bestimmt, nie behauptet: Wer eine
Datei besitzt, deren SHA-256 die Ordnung einer Rolle zuordnet, handelt
als diese Rolle. Zwei Rollen mit demselben Fingerabdruck sind ein
Fehler — die Trennung der Operatoren waere sonst nur behauptet.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

#: Alle zeichenbaren Gates. Massgeblich fuer die gates-Listen der
#: Ordnung: Ein Gate, das man zeichnen, aber keiner Rolle geben kann,
#: waere eine Ordnung mit Loch (so geschehen mit A-K1, gefunden beim
#: Aufsetzen der Vier-Rollen-Regie fuer Fall-Lauf 2).
GUELTIGE_GATES = ("A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-K1")


def _unter(pfad: Path, wurzel: Path) -> bool:
    try:
        pfad.relative_to(wurzel)
        return True
    except ValueError:
        return False


def lade_zeichnungsordnung(
    raw: object, fall: Path
) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Zeichnungsordnung laden: welche ROLLE darf welches GATE zeichnen.

    Rueckgabe ``(ordnung, sha256, fehler)``; ohne Angabe (None) gilt das
    bisherige Verhalten des jeweiligen Konsumenten. Die Regie eines
    Falls entscheidet, ob sie die Ordnung verlangt.
    """
    if raw is None:
        return None, None, []
    if not isinstance(raw, str):
        return None, None, ["--zeichnungsordnung muss ein Pfad sein"]
    angegeben = Path(raw)
    absolut = angegeben if angegeben.is_absolute() else Path.cwd() / angegeben
    fall_resolved = fall.resolve()
    try:
        resolved = absolut.resolve(strict=True)
    except OSError as exc:
        return None, None, [f"Zeichnungsordnung nicht lesbar ({raw!r}): {exc}"]
    if _unter(absolut.absolute(), fall_resolved) or _unter(
        resolved, fall_resolved
    ):
        return None, None, [
            f"Zeichnungsordnung {raw!r} liegt innerhalb des Falls; die "
            "Rollenbindung muss extern verwahrt werden"
        ]
    try:
        daten = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, None, [f"Zeichnungsordnung nicht als JSON lesbar: {exc}"]
    fehler: List[str] = []
    if not isinstance(daten, dict) or daten.get("schema_version") != 1:
        fehler.append("Zeichnungsordnung: schema_version 1 erwartet")
        return None, None, fehler
    rollen = daten.get("rollen")
    if not isinstance(rollen, dict) or not rollen:
        return None, None, ["Zeichnungsordnung: 'rollen' fehlt oder leer"]
    gesehen: Dict[str, str] = {}
    for name, eintrag in rollen.items():
        if not isinstance(eintrag, dict):
            fehler.append(f"Zeichnungsordnung: Rolle {name!r} ist kein Objekt")
            continue
        fp = eintrag.get("schluessel_sha256")
        if not (isinstance(fp, str) and len(fp) == 64
                and all(c in "0123456789abcdef" for c in fp)):
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} ohne gueltigen "
                "schluessel_sha256 (64 Hexzeichen)"
            )
            continue
        if fp in gesehen:
            fehler.append(
                f"Zeichnungsordnung: Rollen {gesehen[fp]!r} und {name!r} "
                "teilen denselben Schluessel -- die Trennung der Operatoren "
                "waere nur behauptet"
            )
        gesehen[fp] = name
        gates = eintrag.get("gates")
        if not isinstance(gates, list) or not all(
            isinstance(g, str) and (g == "*" or g in GUELTIGE_GATES)
            for g in gates
        ):
            fehler.append(
                f"Zeichnungsordnung: Rolle {name!r} mit ungueltiger "
                f"gates-Liste (erlaubt: {list(GUELTIGE_GATES)} oder '*')"
            )
    if fehler:
        return None, None, fehler
    sha = hashlib.sha256(resolved.read_bytes()).hexdigest()
    return daten, sha, []


def zeichnungsrolle(
    ordnung: dict, schluessel_sha256: str
) -> Optional[str]:
    """Die Rolle, der dieser Fingerabdruck gehoert (None = keiner)."""
    for name, eintrag in ordnung["rollen"].items():
        if eintrag.get("schluessel_sha256") == schluessel_sha256:
            return name
    return None


def rolle_darf_gate(ordnung: dict, rolle: str, gate: str) -> bool:
    """Ob die Rolle das Gate zeichnen darf ('*' = alle)."""
    gates = ordnung["rollen"].get(rolle, {}).get("gates", [])
    return "*" in gates or gate in gates
