"""Gemeinsame Fallstandsbindung der Bestands-Pflichtbelege fuer A-M4.

Der Bestandsvertrag aus T6-03 umfasst genau P-B1, eine vollstaendig gepruefte
Migrationssuite und den gruenen Abnahmebericht. Dieses Hilfsmodul stellt ihre
gemeinsame Eingangs-, A-Box-, System- und Zwei-Stichtagsbindung sowie sichere
fallrelative Artefaktrollen bereit. Die fachlichen Belegvertraege werden beim
Produzenten und erneut von A-M4 validiert.

Knoten: klv, system/assurance
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from pathlib import Path
from typing import Any, Dict, List

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates._provenienz import systemstand

BESTANDS_BELEGROLLEN = ("pb1_ledger", "migrationssuite", "abnahmebericht")
_SYSTEM_FELDER = {"commit", "branch", "dirty", "quellcode_sha256"}


def sha256_datei(pfad: Path) -> str:
    """Vollstaendigen SHA-256 einer regulaeren Datei berechnen."""
    h = hashlib.sha256()
    with pfad.open("rb") as datei:
        for block in iter(lambda: datei.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


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
            f"Bestandsbindung ist nur fuer 'bestand' zulaessig, "
            f"Fall deklariert {scope!r}"
        )
    try:
        erster = _dt.date.fromisoformat(stichtag_1)
        zweiter = _dt.date.fromisoformat(stichtag_2)
    except (TypeError, ValueError) as exc:
        raise fall_mod.FallFehler(
            f"Bestands-Stichtage muessen ISO-Daten sein: {exc}"
        ) from exc
    if zweiter <= erster:
        raise fall_mod.FallFehler(
            "Bestands-Stichtag 2 muss nach Stichtag 1 liegen — die "
            "Migrationssuite prueft zwei chronologische Staende"
        )
    eingang = fall / "eingang.json"
    abox = fall / "abgeleitet" / "abox" / "abox.json"
    fehlend = [str(pfad) for pfad in (eingang, abox) if not pfad.is_file()]
    if fehlend:
        raise fall_mod.FallFehler(
            "Bestandsbindung unvollstaendig; Pflichtdatei fehlt: "
            + "; ".join(fehlend)
        )
    return {
        "scope": scope,
        "eingang_sha256": sha256_datei(eingang),
        "abox_sha256": sha256_datei(abox),
        "system": systemstand(repo_root.resolve()),
        "stichtage": [erster.isoformat(), zweiter.isoformat()],
    }


def validate_scope_bindung(bindung: Any) -> List[str]:
    """Strikten Vertrag einer persistierten Bestandsbindung pruefen."""
    felder = {"scope", "eingang_sha256", "abox_sha256", "system", "stichtage"}
    if not isinstance(bindung, dict) or set(bindung) != felder:
        return [f"scope_bindung muss exakt {sorted(felder)} enthalten"]
    fehler: List[str] = []
    if bindung.get("scope") != "bestand":
        fehler.append("scope_bindung.scope muss 'bestand' sein")
    for feld in ("eingang_sha256", "abox_sha256"):
        wert = bindung.get(feld)
        if (
            not isinstance(wert, str)
            or len(wert) != 64
            or any(zeichen not in "0123456789abcdef" for zeichen in wert)
        ):
            fehler.append(f"scope_bindung.{feld} ist kein SHA-256")
    system = bindung.get("system")
    if not isinstance(system, dict) or set(system) != _SYSTEM_FELDER:
        fehler.append(
            f"scope_bindung.system muss exakt {sorted(_SYSTEM_FELDER)} enthalten"
        )
    else:
        if any(not isinstance(wert, str) or not wert for wert in system.values()):
            fehler.append("alle scope_bindung.system-Werte muessen nichtleer sein")
        quellcode_hash = system.get("quellcode_sha256")
        if (
            not isinstance(quellcode_hash, str)
            or len(quellcode_hash) != 64
            or any(zeichen not in "0123456789abcdef" for zeichen in quellcode_hash)
        ):
            fehler.append("scope_bindung.system.quellcode_sha256 ist kein SHA-256")
    stichtage = bindung.get("stichtage")
    if not isinstance(stichtage, list) or len(stichtage) != 2:
        fehler.append("scope_bindung.stichtage muss genau zwei ISO-Daten enthalten")
    else:
        try:
            parsed = [_dt.date.fromisoformat(wert) for wert in stichtage]
            if parsed[1] <= parsed[0]:
                fehler.append("scope_bindung.stichtage sind nicht chronologisch")
        except (TypeError, ValueError):
            fehler.append("scope_bindung.stichtage enthaelt ein ungueltiges ISO-Datum")
    return fehler


def bestands_belegrollen() -> List[str]:
    """Die drei gegenueber einem Tariffall zusaetzlichen Belegrollen."""
    return list(BESTANDS_BELEGROLLEN)


def artefakt_eintrag(fall: Path, pfad: Path) -> Dict[str, str]:
    """Einen regulaeren Belegpfad innerhalb des Falls kanonisch hashen."""
    fall = fall.resolve()
    pfad = pfad.resolve()
    try:
        relativ = pfad.relative_to(fall)
    except ValueError as exc:
        raise ValueError(f"Bestands-Pflichtbeleg liegt ausserhalb des Falls: {pfad}") from exc
    if not pfad.is_file():
        raise ValueError(f"Bestands-Pflichtbeleg fehlt: {pfad}")
    return {"pfad": relativ.as_posix(), "sha256": sha256_datei(pfad)}


def pruefe_artefakt_eintrag(
    fall: Path,
    rolle: str,
    eintrag: Any,
) -> tuple[Path | None, List[str]]:
    """Fallpfad, SHA-Form und aktuelle Bytes eines Belegeintrags pruefen."""
    if not isinstance(eintrag, dict) or set(eintrag) != {"pfad", "sha256"}:
        return None, [f"{rolle} muss exakt pfad und sha256 enthalten"]
    pfad_roh = eintrag.get("pfad")
    erwartet = eintrag.get("sha256")
    if (
        not isinstance(pfad_roh, str)
        or not pfad_roh
        or Path(pfad_roh).is_absolute()
        or ".." in Path(pfad_roh).parts
    ):
        return None, [f"{rolle}.pfad ist kein sicherer Fallpfad"]
    if (
        not isinstance(erwartet, str)
        or len(erwartet) != 64
        or any(zeichen not in "0123456789abcdef" for zeichen in erwartet)
    ):
        return None, [f"{rolle}.sha256 ist kein SHA-256"]
    fall = fall.resolve()
    pfad = (fall / pfad_roh).resolve()
    try:
        relativ = pfad.relative_to(fall)
    except ValueError:
        return None, [f"{rolle}.pfad verlaesst den Fall"]
    kanonisch = relativ.as_posix()
    if pfad_roh != kanonisch:
        return None, [
            f"{rolle}.pfad ist kein kanonischer Fallpfad; erwartet {kanonisch!r}"
        ]
    if not pfad.is_file():
        return None, [f"{rolle}: {pfad_roh} fehlt"]
    gefunden = sha256_datei(pfad)
    if gefunden != erwartet:
        return None, [f"{rolle}: SHA-256 {gefunden} statt {erwartet}"]
    return pfad, []
