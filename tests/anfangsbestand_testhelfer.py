"""Die Abnahme des Anfangsbestands A-B3 fuer Tests — eine Naht, keine Abkuerzung der Pruefung.

Seit ADR-025 (Entscheid des Maintainers 2026-10-01) laeuft nach dem
Aufbaulauf einer Ablage kein Tag ohne die gezeichnete Bindung ihres
Anfangsbestands (``betrieb.anfangsbestand``). Die meisten Tests der Suite
fuehren mehrere Tage und haben einen anderen Gegenstand. Fuer sie legt
dieser Helfer — ueber die Naht ``anfangsbestand._STANDARD_ANFANGSBESTAND``,
die ``conftest`` sessionweit setzt — den Beleg ueber den ECHTEN Produzenten
an (Tabellen, Config, Code-Stand, neu gefahrene P-B1), einen gezeichneten
A-B3-Snapshot im Linienbereich neben der Ablage und die Bindung ueber das
echte ``binden`` (Kette, Signatur, Rollenregel, Stand per ``==``). Danach
prueft der Tageslauf die Bindung wie jede andere.

Gezeichnet mit dem Freigabeschluessel von ``mensch/betrieb``
(``BETRIEB_FREIGABEKEY``) — dieselbe Rolle wie A-B2, getrennt von den
Rollen des Falls. Tests, deren Gegenstand die Verweigerung ohne A-B3 ist,
setzen die Naht per ``monkeypatch`` auf None.

Knoten: system/betrieb
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List

from rechner_pipeline.models import anfangsbestand as ab
from rechner_pipeline.models import standabnahme as sa
from tests.freigabe_testschluessel import (
    AB2_ROLLE,
    BETRIEB_FREIGABEKEY,
    TESTRING,
    suitelinie_anlegen,
    suitelinie_pin,
)


def linie_neben(ablage_wurzel: Path) -> Path:
    """Der Linienbereich der Tests: neben der Ablage, einmal angelegt."""
    linie = Path(ablage_wurzel).parent / f"{Path(ablage_wurzel).name}-linie"
    # mit dem ersten Glied der Test-Linie: Die Linie ist Pflicht (ADR-025).
    return suitelinie_anlegen(linie)


def ab3_snapshot(linie: Path, *, beleg_sha256: str, stand: Dict[str, str],
                 vorgaenger: List[str], schluessel: bytes = BETRIEB_FREIGABEKEY,
                 rolle: str = AB2_ROLLE, entscheid: str = "angenommen") -> Dict[str, Any]:
    """Ein gueltiger A-B3-Snapshot (Schema 9, Scope ``linie``), wie das Gate ihn schreibt."""
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import (
        P9_GATE_VERSION,
        P9_SNAPSHOT_SCHEMA_VERSION,
        p9_snapshot_sha256,
    )

    marker = (linie / sa.LINIE_MARKER).read_bytes()
    daten: Dict[str, Any] = {
        "schema_version": P9_SNAPSHOT_SCHEMA_VERSION, "command": "gate_entscheid",
        "gate_version": P9_GATE_VERSION, "gate": "A-B3", "entscheid": entscheid,
        "entscheider": "Betriebsverantwortung", "rolle": rolle,
        "begruendung": "Anfangsbestand der Ablage geprueft (Suite)", "fall": linie.name,
        "artefakt_hashes": {sa.LINIE_MARKER: hashlib.sha256(marker).hexdigest()},
        "system": {"branch": "main", "commit": "abc1234", "dirty": "nein",
                   "quellcode_sha256": "ef" * 32},
        "vorgaenger": sorted(vorgaenger), "entschieden_am": "2026-01-01T12:00:00+00:00",
        "fall_scope": sa.LINIE_SCOPE, "pflichtbelege": {"anfangsbestand": [beleg_sha256]},
        "stand": dict(stand),
        "zeichnung": {"rolle": rolle, **suitelinie_pin(), "schluesselklasse": "mensch"},
    }
    if entscheid == "angenommen":
        daten["freigabe"] = freigabe_fuer(daten, schluessel)
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    return daten


def zeichne_ab3(linie: Path, beleg: Dict[str, Any]) -> str:
    """Den A-B3-Snapshot zum Beleg am festen Ort der Linie ablegen; Rueckgabe: sein Hash."""
    roh = (Path(linie) / ab.BELEG_RELATIV).read_bytes()
    entscheide = Path(linie) / "entscheide"
    entscheide.mkdir(exist_ok=True)
    vorher = [json.loads(p.read_text(encoding="utf-8"))["snapshot_sha256"]
              for p in sorted(entscheide.glob("A-B3-*.json"))]
    snap = ab3_snapshot(linie, beleg_sha256=hashlib.sha256(roh).hexdigest(),
                        stand=ab.stand_aus_beleg(beleg), vorgaenger=vorher)
    (entscheide / f"A-B3-{snap['snapshot_sha256']}.json").write_text(
        json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    return str(snap["snapshot_sha256"])


def schreibe_anfangsbestand(ablage: Any, zeichner: Any) -> None:
    """Die Naht: belegen, A-B3 zeichnen, binden — unter der Sperre des Tageslaufs."""
    from rechner_pipeline.betrieb import anfangsbestand as anf

    linie = linie_neben(ablage.wurzel)
    beleg = anf.belegen(ablage.wurzel, linie, zeichner, sperre_gehalten=True)
    sha = zeichne_ab3(linie, beleg)
    from rechner_pipeline.models.ordnungslinie import lade_linie

    anf.binden(ablage.wurzel, linie, zeichner, schluesselring=TESTRING,
               snapshot_sha256=sha, ordnungslinie=lade_linie(linie)[0], sperre_gehalten=True)
