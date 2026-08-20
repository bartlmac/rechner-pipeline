"""Fall-Scope-Bindung und unveraenderlicher Bestandsbeleg fuer G-2.

Der deklarative DAG lebt im Fall-Vertrag (:mod:`rechner_pipeline.fall`).
Dieses Gate-Hilfsmodul bindet die daraus fuer einen Bestandsfall folgenden
Artefakte an genau einen Eingangs-, A-Box-, System- und Zwei-Stichtagsstand.
Der Beleg ist inhaltsadressiert und wird nie ueberschrieben; G-2 rechnet beim
Lesen Schema, Eigenhash, Dateiname und jeden Artefakthash neu nach.

Knoten: klv, system/assurance
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates._provenienz import systemstand

SCOPE_BELEG_SCHEMA_VERSION = 1
SCOPE_BELEG_GATE = "G2-vorlage.bestands-scope"
SCOPE_BELEG_COMMAND = "abnahmebericht"
SCOPE_BELEG_GATE_VERSION = "1.1.0"
SCOPE_BELEG_GLOB = "abnahmebericht.*.beleg.json"

_SHA_RE = re.compile(r"[0-9a-f]{64}")
_SYSTEM_FELDER = {"commit", "branch", "dirty", "quellcode_sha256"}


def _sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as datei:
        for block in iter(lambda: datei.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _kanonisches_json(daten: Mapping[str, Any]) -> bytes:
    return json.dumps(
        daten, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _ist_sha256(wert: Any) -> bool:
    return isinstance(wert, str) and _SHA_RE.fullmatch(wert) is not None


def scope_bindung(
    fall: Path,
    repo_root: Path,
    stichtag_1: str,
    stichtag_2: str,
) -> Dict[str, Any]:
    """Die gemeinsame Bindung aller Bestands-Pflichtbelege berechnen."""
    fall = fall.resolve()
    scope = fall_mod.lade_scope(fall)
    if scope != "bestand":
        raise fall_mod.FallFehler(
            f"Scope-Beleg ist nur fuer 'bestand' zulaessig, Fall deklariert {scope!r}"
        )
    try:
        erster = _dt.date.fromisoformat(stichtag_1)
        zweiter = _dt.date.fromisoformat(stichtag_2)
    except (TypeError, ValueError) as exc:
        raise fall_mod.FallFehler(
            f"Scope-Stichtage muessen ISO-Daten sein: {exc}"
        ) from exc
    if zweiter <= erster:
        raise fall_mod.FallFehler(
            "Scope-Stichtag 2 muss nach Stichtag 1 liegen — die "
            "Migrationssuite prueft zwei chronologische Staende"
        )
    eingang = fall / "eingang.json"
    abox = fall / "abgeleitet" / "abox" / "abox.json"
    fehlend = [str(pfad) for pfad in (eingang, abox) if not pfad.is_file()]
    if fehlend:
        raise fall_mod.FallFehler(
            "Scope-Bindung unvollstaendig; Pflichtdatei fehlt: "
            + "; ".join(fehlend)
        )
    return {
        "scope": scope,
        "gate_dag_version": fall_mod.GATE_DAG_VERSION,
        "eingang_sha256": _sha256_datei(eingang),
        "abox_sha256": _sha256_datei(abox),
        "system": systemstand(repo_root.resolve()),
        "stichtage": [erster.isoformat(), zweiter.isoformat()],
    }


def bestands_belegrollen() -> List[str]:
    """Nur die gegenueber dem Tariffall zusaetzlichen DAG-Belegrollen."""
    tarif = set(fall_mod.g2_belegrollen("tarif"))
    return [
        rolle for rolle in fall_mod.g2_belegrollen("bestand")
        if rolle not in tarif
    ]


def artefakt_eintrag(fall: Path, pfad: Path) -> Dict[str, str]:
    """Einen regulaeren Belegpfad innerhalb des Falls kanonisch hashen."""
    fall = fall.resolve()
    pfad = pfad.resolve()
    try:
        relativ = pfad.relative_to(fall)
    except ValueError as exc:
        raise ValueError(
            f"Bestands-Pflichtartefakt liegt ausserhalb des Falls: {pfad}"
        ) from exc
    if not pfad.is_file():
        raise ValueError(f"Bestands-Pflichtartefakt fehlt: {pfad}")
    return {"pfad": relativ.as_posix(), "sha256": _sha256_datei(pfad)}


def scope_beleg_sha256(daten: Mapping[str, Any]) -> str:
    """Kanonischer Eigenhash ohne das selbstadressierende Feld."""
    kern = {key: value for key, value in daten.items() if key != "beleg_sha256"}
    return hashlib.sha256(_kanonisches_json(kern)).hexdigest()


def scope_beleg_dateiname(beleg_sha256: str) -> str:
    return f"abnahmebericht.{beleg_sha256}.beleg.json"


def _bindungs_fehler(bindung: Any) -> List[str]:
    felder = {
        "scope", "gate_dag_version", "eingang_sha256", "abox_sha256",
        "system", "stichtage",
    }
    if not isinstance(bindung, dict) or set(bindung) != felder:
        return [f"bindung muss exakt {sorted(felder)} enthalten"]
    fehler: List[str] = []
    if bindung.get("scope") != "bestand":
        fehler.append("bindung.scope muss 'bestand' sein")
    if bindung.get("gate_dag_version") != fall_mod.GATE_DAG_VERSION:
        fehler.append(
            f"bindung.gate_dag_version muss {fall_mod.GATE_DAG_VERSION!r} sein"
        )
    for feld in ("eingang_sha256", "abox_sha256"):
        if not _ist_sha256(bindung.get(feld)):
            fehler.append(f"bindung.{feld} ist kein SHA-256")
    system = bindung.get("system")
    if not isinstance(system, dict) or set(system) != _SYSTEM_FELDER:
        fehler.append(f"bindung.system muss exakt {sorted(_SYSTEM_FELDER)} enthalten")
    else:
        if any(not isinstance(wert, str) or not wert for wert in system.values()):
            fehler.append("alle bindung.system-Werte muessen nichtleer sein")
        if not _ist_sha256(system.get("quellcode_sha256")):
            fehler.append("bindung.system.quellcode_sha256 ist kein SHA-256")
    stichtage = bindung.get("stichtage")
    if not isinstance(stichtage, list) or len(stichtage) != 2:
        fehler.append("bindung.stichtage muss genau zwei ISO-Daten enthalten")
    else:
        try:
            parsed = [_dt.date.fromisoformat(wert) for wert in stichtage]
            if parsed[1] <= parsed[0]:
                fehler.append("bindung.stichtage sind nicht chronologisch")
        except (TypeError, ValueError):
            fehler.append("bindung.stichtage enthaelt ein ungueltiges ISO-Datum")
    return fehler


def validate_scope_beleg(daten: Any) -> List[str]:
    """Rohes JSON des Bestands-Scope-Belegs strikt validieren."""
    if not isinstance(daten, dict):
        return ["Scope-Beleg ist kein JSON-Objekt"]
    felder = {
        "schema_version", "command", "gate", "gate_version", "status",
        "exit_code", "bindung", "artefakte", "beleg_sha256",
    }
    fehler: List[str] = []
    if set(daten) != felder:
        fehlend = sorted(felder - set(daten))
        fremd = sorted(set(daten) - felder)
        if fehlend:
            fehler.append(f"Pflichtfelder fehlen: {fehlend}")
        if fremd:
            fehler.append(f"unbekannte Felder: {fremd}")
        return fehler
    if type(daten.get("schema_version")) is not int or daten[
        "schema_version"
    ] != SCOPE_BELEG_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {SCOPE_BELEG_SCHEMA_VERSION} sein")
    erwartet = {
        "command": SCOPE_BELEG_COMMAND,
        "gate": SCOPE_BELEG_GATE,
        "gate_version": SCOPE_BELEG_GATE_VERSION,
        "status": "passed",
        "exit_code": 0,
    }
    for feld, wert in erwartet.items():
        if daten.get(feld) != wert or type(daten.get(feld)) is not type(wert):
            fehler.append(f"{feld} muss {wert!r} sein")
    fehler.extend(_bindungs_fehler(daten.get("bindung")))
    artefakte = daten.get("artefakte")
    rollen = bestands_belegrollen()
    if not isinstance(artefakte, dict) or set(artefakte) != set(rollen):
        fehler.append(f"artefakte muss exakt die DAG-Rollen {rollen} enthalten")
    else:
        pfade: List[str] = []
        for rolle in rollen:
            eintrag = artefakte[rolle]
            if not isinstance(eintrag, dict) or set(eintrag) != {"pfad", "sha256"}:
                fehler.append(
                    f"artefakte[{rolle!r}] muss exakt pfad und sha256 enthalten"
                )
                continue
            pfad = eintrag.get("pfad")
            if (
                not isinstance(pfad, str) or not pfad
                or Path(pfad).is_absolute() or ".." in Path(pfad).parts
            ):
                fehler.append(f"artefakte[{rolle!r}].pfad ist kein sicherer Fallpfad")
            else:
                pfade.append(pfad)
            if not _ist_sha256(eintrag.get("sha256")):
                fehler.append(f"artefakte[{rolle!r}].sha256 ist kein SHA-256")
        if len(pfade) != len(set(pfade)):
            fehler.append("jede DAG-Belegrolle muss ein eigenes Artefakt binden")
    beleg_sha = daten.get("beleg_sha256")
    if not _ist_sha256(beleg_sha):
        fehler.append("beleg_sha256 ist kein SHA-256")
    elif scope_beleg_sha256(daten) != beleg_sha:
        fehler.append("beleg_sha256 stimmt nicht mit dem kanonischen Inhalt ueberein")
    return fehler


def schreibe_scope_beleg(
    diagnostics: Path,
    *,
    bindung: Mapping[str, Any],
    artefakte: Mapping[str, Mapping[str, str]],
) -> Tuple[Path, Dict[str, Any]]:
    """Einen validierten Scope-Beleg exklusiv und idempotent schreiben."""
    daten: Dict[str, Any] = {
        "schema_version": SCOPE_BELEG_SCHEMA_VERSION,
        "command": SCOPE_BELEG_COMMAND,
        "gate": SCOPE_BELEG_GATE,
        "gate_version": SCOPE_BELEG_GATE_VERSION,
        "status": "passed",
        "exit_code": 0,
        "bindung": dict(bindung),
        "artefakte": {rolle: dict(eintrag) for rolle, eintrag in artefakte.items()},
    }
    daten["beleg_sha256"] = scope_beleg_sha256(daten)
    fehler = validate_scope_beleg(daten)
    if fehler:
        raise ValueError("ungueltiger Scope-Beleg: " + "; ".join(fehler))
    diagnostics.mkdir(parents=True, exist_ok=True)
    ziel = diagnostics / scope_beleg_dateiname(daten["beleg_sha256"])
    payload = (
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        with ziel.open("xb") as datei:
            datei.write(payload)
    except FileExistsError:
        if ziel.read_bytes() != payload:
            raise ValueError(f"Scope-Beleg existiert mit anderem Inhalt: {ziel}")
    return ziel, daten


def pruefe_scope_beleg(
    pfad: Path,
    *,
    fall: Optional[Path] = None,
    erwartete_bindung: Optional[Mapping[str, Any]] = None,
    pruefe_artefakte: bool = False,
) -> Tuple[Optional[Dict[str, Any]], List[str]]:
    """Beleg lesen und optional gegen Fall sowie Jetztstand nachrechnen."""
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{pfad.name}: nicht als JSON lesbar: {exc}"]
    fehler = [f"{pfad.name}: {meldung}" for meldung in validate_scope_beleg(daten)]
    if isinstance(daten, dict) and _ist_sha256(daten.get("beleg_sha256")):
        erwartet = scope_beleg_dateiname(daten["beleg_sha256"])
        if pfad.name != erwartet:
            fehler.append(
                f"{pfad.name}: Dateiname stimmt nicht mit Beleg-Hash ueberein "
                f"(erwartet {erwartet})"
            )
    if fehler or not isinstance(daten, dict):
        return None, fehler
    if erwartete_bindung is not None and daten["bindung"] != dict(erwartete_bindung):
        fehler.append(f"{pfad.name}: Scope-Bindung weicht vom aktuellen Stand ab")
    if pruefe_artefakte:
        if fall is None:
            fehler.append(f"{pfad.name}: Artefaktpruefung braucht einen Fallpfad")
        else:
            fall = fall.resolve()
            for rolle, eintrag in daten["artefakte"].items():
                artefakt = fall / eintrag["pfad"]
                if not artefakt.is_file():
                    fehler.append(f"{pfad.name}: {rolle}: {eintrag['pfad']} fehlt")
                    continue
                gefunden = _sha256_datei(artefakt)
                if gefunden != eintrag["sha256"]:
                    fehler.append(
                        f"{pfad.name}: {rolle}: SHA-256 {gefunden} statt "
                        f"{eintrag['sha256']}"
                    )
    return (daten if not fehler else None), fehler
