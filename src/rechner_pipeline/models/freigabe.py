"""Die Freigabesignatur eines P9-Snapshots: Schluesselring laden, signieren, pruefen.

Bis zum Entscheid des Maintainers vom 2026-09-22 (Befund T26-03, Weg 2 mit
Zeichnungsschicht) wohnte das alles in ``gates.gate_entscheid``, und die
Schichtenkarte laesst ``betrieb -> gates`` nicht zu: Der Betriebseingang
konnte eine Signatur nicht pruefen, "signatur_verifiziert" stand immer
auf False. Hier liegt die Mechanik einmal — das Gate signiert und prueft
damit, der Betriebseingang prueft damit — dasselbe Muster wie die
P-B1-Engine in ``bestand.vorbedingungen``: eine Regel, zwei Aufrufer.

Schluesselbytes verlassen diese Funktionen nie in Ergebnissen, Ledgern,
Snapshots oder Fehlermeldungen. Ein Schluessel innerhalb des frei
editierbaren Vertrauensraums (Fall, Ablage) machte die Signatur zur
Selbstbehauptung und wird abgewiesen.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.models.schemas import (
    P9_FREIGABE_VERFAHREN,
    p9_freigabe_nachricht,
)

FREIGABE_SCHLUESSEL_MIN_BYTES = 32


def _ist_unter(pfad: Path, wurzel: Path) -> bool:
    try:
        pfad.relative_to(wurzel)
    except ValueError:
        return False
    return True


def lade_schluesselring(
    pfade: object,
    *,
    ausserhalb: Path,
) -> Tuple[Dict[str, bytes], List[str], Optional[str]]:
    """Load an external HMAC keyring; the last key authorizes new decisions.

    Key bytes are deliberately never returned in a result, ledger, snapshot or
    error.  A path inside the freely editable case would make the signature a
    self-assertion and is therefore rejected even when it is a symlink whose
    resolved target happens to be outside the case.
    """
    if pfade is None:
        liste: List[str] = []
    elif isinstance(pfade, str):
        liste = [pfade]
    elif isinstance(pfade, list) and all(isinstance(p, str) for p in pfade):
        liste = pfade
    else:
        return {}, ["freigabe-schluessel muss ein Pfad oder eine Pfadliste sein"], None

    ring: Dict[str, bytes] = {}
    aktiv: Optional[str] = None
    fehler: List[str] = []
    aussen = ausserhalb.resolve()
    for raw in liste:
        angegeben = Path(raw)
        absolut = angegeben if angegeben.is_absolute() else Path.cwd() / angegeben
        # Sowohl der lexikalische als auch der aufgeloeste Ort muessen ausserhalb
        # des Falls liegen; damit helfen Symlinks nicht ueber die Vertrauensgrenze.
        try:
            resolved = absolut.resolve(strict=True)
        except OSError as exc:
            fehler.append(f"Freigabeschluessel nicht lesbar ({raw!r}): {exc}")
            continue
        if _ist_unter(absolut.absolute(), aussen) or _ist_unter(
            resolved, aussen
        ):
            fehler.append(
                f"Freigabeschluessel {raw!r} liegt innerhalb des Vertrauensraums (Fall bzw. Ablage); "
                "menschliche Autorisierung muss extern verwahrt werden"
            )
            continue
        if not resolved.is_file():
            fehler.append(f"Freigabeschluessel ist keine regulaere Datei: {raw!r}")
            continue
        try:
            key = resolved.read_bytes()
        except OSError as exc:
            fehler.append(f"Freigabeschluessel nicht lesbar ({raw!r}): {exc}")
            continue
        if not (FREIGABE_SCHLUESSEL_MIN_BYTES <= len(key) <= 4096):
            fehler.append(
                f"Freigabeschluessel {raw!r} muss zwischen "
                f"{FREIGABE_SCHLUESSEL_MIN_BYTES} und 4096 Byte lang sein"
            )
            continue
        if os.name != "nt":
            dateistand = resolved.stat()
            if dateistand.st_mode & 0o077:
                fehler.append(
                    f"Freigabeschluessel {raw!r} ist fuer Gruppe/Andere "
                    "lesbar; Dateirechte auf 0600 begrenzen"
                )
                continue
            if dateistand.st_nlink != 1:
                fehler.append(
                    f"Freigabeschluessel {raw!r} hat "
                    f"{dateistand.st_nlink} Hardlinks; ein externer "
                    "Schluessel darf nicht in den Fall gespiegelt sein"
                )
                continue
        key_id = hashlib.sha256(key).hexdigest()
        ring[key_id] = key
        aktiv = key_id
    return ring, fehler, aktiv


def freigabe_fuer(snapshot_ohne_freigabe: dict, key: bytes) -> Dict[str, str]:
    return {
        "verfahren": P9_FREIGABE_VERFAHREN,
        "schluessel_sha256": hashlib.sha256(key).hexdigest(),
        "signatur": hmac.new(
            key, p9_freigabe_nachricht(snapshot_ohne_freigabe), hashlib.sha256
        ).hexdigest(),
    }


def pruefe_freigabe(snapshot: dict, schluesselring: Mapping[str, bytes]) -> List[str]:
    if snapshot.get("entscheid") != "angenommen":
        return []
    freigabe = snapshot.get("freigabe")
    if not isinstance(freigabe, dict):
        return ["menschliche Annahme traegt keine Freigabesignatur"]
    key_id = freigabe.get("schluessel_sha256")
    key = schluesselring.get(key_id) if isinstance(key_id, str) else None
    if key is None:
        return [
            "Freigabesignatur verwendet einen nicht bereitgestellten "
            f"Schluessel ({key_id!r})"
        ]
    erwartet = hmac.new(
        key, p9_freigabe_nachricht(snapshot), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(erwartet, str(freigabe.get("signatur", ""))):
        return ["Freigabesignatur stimmt nicht mit dem Snapshot-Inhalt ueberein"]
    return []


