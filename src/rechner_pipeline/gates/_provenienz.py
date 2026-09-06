"""Gemeinsame System- und P-K1-Beweisprovenienz.

Ein ueberschreibbarer ``generation_golden.gate.json``-Ledger kann nicht
beweisen, dass Gate P-K1 fuer *jede* Generation einer A-Box gelaufen ist.  Der
Ledger bleibt das Prozessprotokoll des letzten Laufs; der Abnahmebeweis ist
hingegen ein deterministischer, inhaltsadressierter Beleg je Generation.
Sein Eigenhash wird beim Lesen nachgerechnet und sein Dateiname daraus
abgeleitet.  Ein erneuter identischer Lauf ist damit idempotent, ein anderer
Stand erzeugt eine neue Datei statt einen alten Beleg zu ersetzen.

Der Systemstand verbindet den vorhandenen Git-Stand mit einem SHA-256 ueber
die tatsaechlich installierten Python-/XML-Dateien des Pakets.  ``dirty=ja``
allein waere kein exakter Stand: zwei verschiedene lokale Codeaenderungen
haetten sonst denselben Wert.

Knoten: klv, system/assurance
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

O3_BELEG_SCHEMA_VERSION = 1
O3_BELEG_GATE = "P-K1.generations-golden-master"
O3_BELEG_COMMAND = "generation_golden"
O3_BELEG_GATE_VERSION = "0.2.0"
O3_BELEG_GLOB = "generation_golden.*.beleg.json"

_BELEG_FELDER = frozenset({
    "schema_version",
    "gate",
    "gate_version",
    "command",
    "status",
    "exit_code",
    "generation",
    "abox_sha256",
    "system",
    "input_hashes",
    "summary",
    "beleg_sha256",
})
_SYSTEM_FELDER = frozenset({
    "commit", "branch", "dirty", "quellcode_sha256",
})


def _ist_sha256(wert: object) -> bool:
    return (
        isinstance(wert, str)
        and re.fullmatch(r"[0-9a-f]{64}", wert) is not None
    )


def _git_stand(repo_root: Path) -> Dict[str, str]:
    """Den Git-Stand mit drei eng begrenzten, lesenden Aufrufen erfassen.

    Dies ist weiterhin die einzige Subprozess-Ausnahme im Paket.  Sie
    protokolliert nur Beweisprovenienz fuer P-K1/P9 und beeinflusst keine
    fachliche Rechnung.  Ist Git nicht verfuegbar, bleibt der Zustand mit
    ``unbekannt`` ausdruecklich benannt.
    """
    stand: Dict[str, str] = {}
    for name, argv in (
        ("commit", ["git", "rev-parse", "HEAD"]),
        ("branch", ["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        ("dirty", ["git", "status", "--porcelain"]),
    ):
        try:
            out = subprocess.run(
                argv,
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            ).stdout.strip()
        except Exception:  # noqa: BLE001 - unbekannt ist ein benannter Stand
            stand[name] = "unbekannt"
            continue
        stand[name] = ("ja" if out else "nein") if name == "dirty" else out
    return stand


def _quellcode_sha256() -> str:
    """SHA-256 des ausfuehrbaren Paketstands, pfad- und laengengetrennt."""
    paket = Path(__file__).resolve().parents[1]
    dateien = sorted(
        pfad for pfad in paket.rglob("*")
        if pfad.is_file() and pfad.suffix in {".py", ".xml"}
    )
    h = hashlib.sha256()
    for pfad in dateien:
        relativ = pfad.relative_to(paket).as_posix().encode("utf-8")
        inhalt = pfad.read_bytes()
        h.update(len(relativ).to_bytes(8, "big"))
        h.update(relativ)
        h.update(len(inhalt).to_bytes(8, "big"))
        h.update(inhalt)
    return h.hexdigest()


def systemstand(repo_root: Path) -> Dict[str, str]:
    """Den fuer P-K1 und P9 gemeinsam vergleichbaren Systemstand liefern."""
    return {**_git_stand(repo_root), "quellcode_sha256": _quellcode_sha256()}


def _beleg_hash(kern: Mapping[str, Any]) -> str:
    kanonisch = json.dumps(
        kern,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def _generation_dateiname(generation: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", generation).strip("-")
    if not name:
        raise ValueError("P-K1-Beleg: Generation ergibt keinen Dateinamen")
    return name


def pk1_beleg_dateiname(generation: str, beleg_sha256: str) -> str:
    """Den einzigen gueltigen Dateinamen eines P-K1-Belegs ableiten."""
    return (
        f"generation_golden.{_generation_dateiname(generation)}."
        f"{beleg_sha256}.beleg.json"
    )


def schreibe_pk1_beleg(
    diagnostics_dir: Path,
    *,
    gate_version: str,
    status: str,
    exit_code: int,
    generation: str,
    abox_sha256: str,
    system: Mapping[str, str],
    input_hashes: Mapping[str, str],
    summary: Mapping[str, Any],
) -> Path:
    """Einen gruenen P-K1-Beleg exklusiv und inhaltsadressiert schreiben."""
    kern: Dict[str, Any] = {
        "schema_version": O3_BELEG_SCHEMA_VERSION,
        "gate": O3_BELEG_GATE,
        "gate_version": gate_version,
        "command": O3_BELEG_COMMAND,
        "status": status,
        "exit_code": exit_code,
        "generation": generation,
        "abox_sha256": abox_sha256,
        "system": dict(system),
        "input_hashes": dict(input_hashes),
        "summary": dict(summary),
    }
    beleg_sha256 = _beleg_hash(kern)
    daten = {**kern, "beleg_sha256": beleg_sha256}
    fehler = _pruefe_o3_beleg_daten(daten)
    if fehler:
        raise ValueError("P-K1-Beleg ungueltig: " + "; ".join(fehler))

    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    ziel = diagnostics_dir / pk1_beleg_dateiname(generation, beleg_sha256)
    payload = (
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        with ziel.open("xb") as datei:
            datei.write(payload)
    except FileExistsError:
        if ziel.read_bytes() != payload:
            raise ValueError(
                f"P-K1-Beleg {ziel.name} existiert mit anderem Inhalt - "
                "ein inhaltsadressierter Beleg wird nie ueberschrieben"
            )
    return ziel


def _pruefe_o3_beleg_daten(daten: object) -> list[str]:
    fehler: list[str] = []
    if not isinstance(daten, dict):
        return ["Inhalt ist kein JSON-Objekt"]

    felder = set(daten)
    if felder != _BELEG_FELDER:
        fehlt = sorted(_BELEG_FELDER - felder)
        fremd = sorted(felder - _BELEG_FELDER)
        if fehlt:
            fehler.append(f"Pflichtfelder fehlen: {fehlt}")
        if fremd:
            fehler.append(f"unbekannte Felder: {fremd}")
    if (
        type(daten.get("schema_version")) is not int
        or daten.get("schema_version") != O3_BELEG_SCHEMA_VERSION
    ):
        fehler.append(
            f"schema_version muss {O3_BELEG_SCHEMA_VERSION} sein"
        )
    if daten.get("gate") != O3_BELEG_GATE:
        fehler.append(f"gate muss {O3_BELEG_GATE!r} sein")
    if daten.get("gate_version") != O3_BELEG_GATE_VERSION:
        fehler.append(
            f"gate_version muss {O3_BELEG_GATE_VERSION!r} sein"
        )
    if daten.get("command") != O3_BELEG_COMMAND:
        fehler.append(f"command muss {O3_BELEG_COMMAND!r} sein")
    if daten.get("status") != "passed":
        fehler.append("status muss 'passed' sein")
    exit_code = daten.get("exit_code")
    if type(exit_code) is not int or exit_code != 0:
        fehler.append("exit_code muss die ganze Zahl 0 sein")
    generation = daten.get("generation")
    if (
        not isinstance(generation, str)
        or re.fullmatch(r"[a-z0-9_]+/[a-z0-9_]+", generation) is None
    ):
        fehler.append(
            "generation muss eine Knoten-ID <familie>/<generation> sein"
        )
    if not _ist_sha256(daten.get("abox_sha256")):
        fehler.append("abox_sha256 ist kein vollstaendiger SHA-256")

    system = daten.get("system")
    if not isinstance(system, dict):
        fehler.append("system muss ein Objekt sein")
    else:
        if set(system) != _SYSTEM_FELDER:
            fehler.append(
                f"system muss exakt die Felder {sorted(_SYSTEM_FELDER)} tragen"
            )
        if any(not isinstance(wert, str) or not wert for wert in system.values()):
            fehler.append("alle Systemstand-Werte muessen nichtleer sein")
        if not _ist_sha256(system.get("quellcode_sha256")):
            fehler.append("system.quellcode_sha256 ist kein SHA-256")

    input_hashes = daten.get("input_hashes")
    if not isinstance(input_hashes, dict) or not input_hashes:
        fehler.append("input_hashes muss ein nichtleeres Objekt sein")
    else:
        for schluessel, wert in input_hashes.items():
            if not isinstance(schluessel, str) or not schluessel:
                fehler.append("input_hashes enthaelt einen leeren Pfadschluessel")
            if not _ist_sha256(wert):
                fehler.append(
                    f"input_hashes[{schluessel!r}] ist kein SHA-256"
                )
        if input_hashes.get("abgeleitet/abox/abox.json") != daten.get(
            "abox_sha256"
        ):
            fehler.append(
                "input_hashes bindet nicht dieselbe A-Box wie abox_sha256"
            )

    summary = daten.get("summary")
    if not isinstance(summary, dict):
        fehler.append("summary muss ein Objekt sein")
    else:
        if summary.get("generation") != generation:
            fehler.append("summary.generation weicht von generation ab")
        if summary.get("abox_sha256") != daten.get("abox_sha256"):
            fehler.append("summary.abox_sha256 weicht von abox_sha256 ab")
        if summary.get("system") != system:
            fehler.append("summary.system weicht vom Systemstand ab")

    beleg_sha256 = daten.get("beleg_sha256")
    if not _ist_sha256(beleg_sha256):
        fehler.append("beleg_sha256 ist kein vollstaendiger SHA-256")
    else:
        kern = {k: v for k, v in daten.items() if k != "beleg_sha256"}
        if _beleg_hash(kern) != beleg_sha256:
            fehler.append("beleg_sha256 stimmt nicht mit dem Inhalt ueberein")
    return fehler


def pruefe_pk1_beleg(pfad: Path) -> Tuple[Optional[dict], list[str]]:
    """Einen P-K1-Beleg samt Eigenhash und abgeleitetem Dateinamen pruefen."""
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{pfad.name}: nicht als JSON lesbar: {exc}"]

    fehler = _pruefe_o3_beleg_daten(daten)
    if isinstance(daten, dict):
        generation = daten.get("generation")
        beleg_sha256 = daten.get("beleg_sha256")
        if isinstance(generation, str) and _ist_sha256(beleg_sha256):
            try:
                erwartet = pk1_beleg_dateiname(generation, beleg_sha256)
            except ValueError as exc:
                fehler.append(f"Dateiname nicht ableitbar: {exc}")
            else:
                if pfad.name != erwartet:
                    fehler.append(
                        f"Dateiname {pfad.name!r} stimmt nicht mit dem "
                        f"Beleginhalt ueberein (erwartet {erwartet!r})"
                    )
    return daten if isinstance(daten, dict) else None, [
        f"{pfad.name}: {meldung}" for meldung in fehler
    ]
