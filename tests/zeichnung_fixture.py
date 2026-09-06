"""Zeichnungsordnung und Schluessel fuer Tests — nach ADR-018.

Eine Annahme braucht seit ADR-018 eine Zeichnungsordnung (Schema 2) und
einen Schluessel, aus dem die Rolle BESTIMMT wird. Dieser Helfer legt
beides je Testfall an: eine simulierte Rolle ``mensch/verantwortlicher-
aktuar`` (Schluesselklasse ``simulation``, zeichnet alle Gates) und
optional weitere Rollen.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

VA = "mensch/verantwortlicher-aktuar"
QUELLE = "mensch/quell-aktuar"
AGENT = "agent/programmleitung"

_STANDARD_SCHLUESSEL = b"test-only-p9-authorization-key!" * 2


def schluessel_anlegen(pfad: Path, inhalt: bytes = _STANDARD_SCHLUESSEL) -> str:
    """Schluesseldatei (0600) anlegen; Rueckgabe: Fingerabdruck."""
    if not pfad.exists():
        pfad.write_bytes(inhalt)
        pfad.chmod(0o600)
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def ordnung_schreiben(pfad: Path, rollen: Dict[str, dict]) -> Path:
    pfad.write_text(json.dumps({"schema_version": 2, "rollen": rollen}),
                    encoding="utf-8")
    return pfad


def standard_ordnung(
    verzeichnis: Path,
    schluessel: Path,
    *,
    klasse: str = "simulation",
    rolle: str = VA,
    gates: Optional[List[str]] = None,
    weitere: Optional[Dict[str, dict]] = None,
) -> Path:
    """Ordnung mit einer zeichnenden Rolle fuer diesen Schluessel."""
    fp = schluessel_anlegen(schluessel)
    rollen = {rolle: {"schluessel_sha256": fp, "schluesselklasse": klasse,
                      "gates": gates if gates is not None else ["*"]}}
    rollen.update(weitere or {})
    return ordnung_schreiben(verzeichnis / "zeichnungsordnung.json", rollen)


def annahme_args(fall: Path, **kw) -> List[str]:
    """``--zeichnungsordnung ... --freigabe-schluessel ...`` fuer einen Fall.

    Ordnung und Schluessel liegen NEBEN dem Fall (ausserhalb, wie es die
    Ordnung verlangt), je Fall genau einmal angelegt.
    """
    schluessel = fall.parent / "p9-freigabe.key"
    ordnung = fall.parent / "zeichnungsordnung.json"
    if not ordnung.exists():
        standard_ordnung(fall.parent, schluessel, **kw)
    return ["--zeichnungsordnung", str(ordnung),
            "--freigabe-schluessel", str(schluessel)]
