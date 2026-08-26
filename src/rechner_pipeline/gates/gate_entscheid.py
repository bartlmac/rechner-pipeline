"""``gate_entscheid`` — der P9-Snapshot eines menschlichen Gates.

Ein menschliches Gate (G-1 fachlich, G-A aktuarielle Abnahme, G-2
Migrationsabnahme, G-T T-Box-Aenderung)
endet nicht in einer Commit-Message, sondern in einem unveraenderlichen,
inhaltsadressierten Snapshot: WER hat WAS auf WELCHEM Stand entschieden,
mit welcher Begruendung. Der Snapshot haelt die SHA-256-Hashes aller
entscheidungsrelevanten Artefakte des Falls fest (Eingang-Register,
A-Box, Spez, Coverage, Fachspez, Gate-Ledger) plus den Git-Stand des
Systems (Setup-Provenienz, P1) — der Lauf ist daraus reproduzierbar.

Die Sperre gegen stille Dauerprovisorien (P2/P4): eine ANNAHME wird
verweigert, solange die A-Box VORLAEUFIGE Diskrepanz-Aufloesungen
traegt — die fachliche Entscheidung ist genau der Zweck des Gates
(``python -m rechner_pipeline.ontologie.entscheide`` ersetzt eine
vorlaeufige Aufloesung durch die menschliche). Eine ABLEHNUNG ist
jederzeit snapshotbar.

Der Snapshot-Dateiname traegt den vollstaendigen kanonischen Hash ALLER
persistierten Felder einschliesslich Entscheidungszeit und Freigabe. Derselbe
Entscheid auf demselben Stand bleibt durch den vorherigen Inhaltsvergleich
idempotent; eine bestehende Datei wird nie ueberschrieben. Jeder Snapshot
pinnt die Hashes aller frueheren Snapshots seines Gates (``vorgaenger``).
Beim Lesen werden Existenz, Zyklen und die genau eine geltende Spitze
nachgerechnet. Abgelegt wird in ``<fall>/entscheide/`` neben dem Eingang:
Entscheidungen sind wie der Eingang NICHT regenerierbar.

Eine menschliche Annahme ist zusaetzlich mit HMAC-SHA-256 autorisiert. Das
Schluesselmaterial liegt ausserhalb des frei editierbaren Falls und wird nie
in Snapshot oder Ledger geschrieben. Damit kann der Fall seine eigene
menschliche Freigabe nicht behaupten.

G-A und G-2 leiten ihre Pflichtbelegrollen JE GATE aus dem expliziten
Fall-Scope ab (ADR-009, fortgeschrieben durch ADR-010). G-A pinnt im
Bestands-Scope Testergebnis und Bericht des aktuariellen Tests (gruener
aktuartest-Ledger auf genau diesen Bytes); im Tarif-Scope ist seine
Rollenmenge leer. G-2 braucht im Tariffall O1, G-1, G-A und O3; ein
Bestandsfall zusaetzlich den gruenen B1-Beleg, die vollstaendige Suite
und den Abnahmebericht desselben Eingangs-, A-Box-, System-, Bestands-
und Zwei-Stichtagsstands. Die Reihenfolge ist erzwungen: Ein
G-2-Entscheid ohne geltende, signierte G-A-Annahme auf demselben Stand
ist unmoeglich (ADR-010). Im Abnahme-Ledger verlangt G-2 ausserdem die
vier festen Renderer-Artefaktrollen, prueft ihre aktuellen Bytes und
leitet das Berichtsverdikt aus den gebundenen Inhalten neu ab.

Run via::

    python -m rechner_pipeline.gates.gate_entscheid --fall faelle/baldrian-klv-tg2015 \\
        --gate G-1 --entscheid angenommen --entscheider "Bartek" \\
        --begruendung "..." --freigabe-schluessel /sicher/p9.key \
        [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates._common import (
    Exit,
    GateArgumentParser,
    GateCliContract,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.gates._fall_scope import (
    bestands_belegrollen,
    pruefe_artefakt_eintrag,
    scope_bindung,
    validate_scope_bindung,
)
from rechner_pipeline.gates._provenienz import (
    O3_BELEG_GLOB,
    pruefe_o3_beleg,
    systemstand,
)
from rechner_pipeline.models.schemas import (
    GateLedgerEntry,
    P9_FREIGABE_VERFAHREN,
    P9_GATE_VERSION,
    P9_SNAPSHOT_SCHEMA_VERSION,
    P9Snapshot,
    p9_freigabe_nachricht,
    p9_snapshot_sha256,
)

GATE_VERSION = P9_GATE_VERSION
GUELTIGE_GATES = ("G-1", "G-A", "G-2", "G-T")
CLI_CONTRACT = GateCliContract(
    command="gate_entscheid",
    gate="P9.?",
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
    decision_gate_choices=GUELTIGE_GATES,
    sensitive_options=("freigabe_schluessel",),
)
FREIGABE_SCHLUESSEL_MIN_BYTES = 32


def _sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ist_unter(pfad: Path, wurzel: Path) -> bool:
    try:
        pfad.relative_to(wurzel)
    except ValueError:
        return False
    return True


def _lade_freigabe_schluessel(
    pfade: object,
    fall: Path,
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
        return {}, ["--freigabe-schluessel muss ein Pfad oder eine Pfadliste sein"], None

    ring: Dict[str, bytes] = {}
    aktiv: Optional[str] = None
    fehler: List[str] = []
    fall_resolved = fall.resolve()
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
        if _ist_unter(absolut.absolute(), fall_resolved) or _ist_unter(
            resolved, fall_resolved
        ):
            fehler.append(
                f"Freigabeschluessel {raw!r} liegt innerhalb des Falls; "
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


def _freigabe_fuer(snapshot_ohne_freigabe: dict, key: bytes) -> Dict[str, str]:
    return {
        "verfahren": P9_FREIGABE_VERFAHREN,
        "schluessel_sha256": hashlib.sha256(key).hexdigest(),
        "signatur": hmac.new(
            key, p9_freigabe_nachricht(snapshot_ohne_freigabe), hashlib.sha256
        ).hexdigest(),
    }


def _pruefe_freigabe(snapshot: dict, schluesselring: Mapping[str, bytes]) -> List[str]:
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


def _snapshot_dateiname(gate: str, snapshot_sha256: str) -> str:
    return f"{gate}-{snapshot_sha256}.json"


def _pruefe_g2_snapshot_semantik(snapshot: dict) -> List[str]:
    """Den aus dem Scope abgeleiteten Inhalt einer Annahme pruefen.

    Das paketweite P9-Schema prueft die JSON-Form. Die fachliche Rollenmenge
    wird deshalb hier auch beim LESEN eines bestehenden Snapshots erneut aus
    dem Belegrollen-Vertrag (je Gate und Scope, ADR-009/ADR-010) abgeleitet.
    Sonst koennte ein formal gueltiger, signierter Snapshot eine Pflichtrolle
    auslassen und dennoch als gueltige P9-Historie erscheinen.
    """
    gate = snapshot.get("gate")
    if gate not in ("G-A", "G-2") or snapshot.get("entscheid") != "angenommen":
        return []
    fehler: List[str] = []
    scope = snapshot.get("fall_scope")
    try:
        erwartete_rollen = fall_mod.belegrollen(gate, scope)
    except fall_mod.FallFehler as exc:
        fehler.append(f"{gate}-Scope ist ungueltig: {exc}")
        return fehler
    pflichtbelege = snapshot.get("pflichtbelege")
    if isinstance(pflichtbelege, dict) and set(pflichtbelege) != set(
        erwartete_rollen
    ):
        fehler.append(
            "pflichtbelege enthaelt nicht exakt die aus dem Scope "
            f"abgeleiteten Rollen {erwartete_rollen}"
        )
    o3_belege = snapshot.get("o3_belege")
    if isinstance(pflichtbelege, dict) and isinstance(o3_belege, dict):
        o3_hashes = sorted(
            beleg
            for belege_der_generation in o3_belege.values()
            if isinstance(belege_der_generation, list)
            for beleg in belege_der_generation
        )
        if pflichtbelege.get("o3_belege") != o3_hashes:
            fehler.append(
                "pflichtbelege['o3_belege'] stimmt nicht mit der "
                "Generationen-Belegmenge ueberein"
            )
    return fehler


def _pruefe_snapshot_graph(
    snapshots: Mapping[str, Tuple[Path, dict]],
) -> Tuple[List[str], List[str]]:
    """Check predecessor existence, cycles and the unique current tip."""
    fehler: List[str] = []
    for sha, (pfad, daten) in snapshots.items():
        for vorgaenger in daten["vorgaenger"]:
            if vorgaenger not in snapshots:
                fehler.append(
                    f"{pfad.name}: Vorgaenger {vorgaenger} existiert nicht"
                )
            if vorgaenger == sha:
                fehler.append(f"{pfad.name}: Snapshot referenziert sich selbst")

    zustand: Dict[str, int] = {}

    def _besuche(sha: str) -> None:
        if zustand.get(sha) == 1:
            fehler.append(f"Vorgaengerkette enthaelt einen Zyklus bei {sha}")
            return
        if zustand.get(sha) == 2:
            return
        zustand[sha] = 1
        for vorgaenger in snapshots[sha][1]["vorgaenger"]:
            if vorgaenger in snapshots:
                _besuche(vorgaenger)
        zustand[sha] = 2

    for sha in snapshots:
        _besuche(sha)

    referenziert = {
        vorgaenger
        for _, daten in snapshots.values()
        for vorgaenger in daten["vorgaenger"]
    }
    spitzen = sorted(set(snapshots) - referenziert)
    if snapshots and len(spitzen) != 1:
        fehler.append(
            "Vorgaengerkette braucht genau eine eindeutige Spitze; "
            f"gefunden: {spitzen}"
        )
    return spitzen, fehler


def _lade_snapshot_kette(
    verzeichnis: Path,
    gate: str,
    fall: Path,
    schluesselring: Mapping[str, bytes],
) -> Tuple[Dict[str, Tuple[Path, dict]], List[str], List[str]]:
    """Validate schema, content address, signature and the complete DAG."""
    snapshots: Dict[str, Tuple[Path, dict]] = {}
    fehler: List[str] = []
    for pfad in sorted(verzeichnis.glob(f"{gate}-*.json")):
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fehler.append(f"{pfad.name}: nicht als JSON lesbar: {exc}")
            continue
        schema_fehler = P9Snapshot.validate_payload(daten)
        if schema_fehler:
            fehler.extend(f"{pfad.name}: {meldung}" for meldung in schema_fehler)
            continue
        fehler.extend(
            f"{pfad.name}: {meldung}"
            for meldung in _pruefe_g2_snapshot_semantik(daten)
        )
        sha = daten["snapshot_sha256"]
        if daten["gate"] != gate:
            fehler.append(
                f"{pfad.name}: gate {daten['gate']!r} statt erwartet {gate!r}"
            )
        if daten["fall"] != str(fall):
            fehler.append(
                f"{pfad.name}: Fallbindung {daten['fall']!r} statt {str(fall)!r}"
            )
        erwartet = _snapshot_dateiname(gate, sha)
        if pfad.name != erwartet:
            fehler.append(
                f"{pfad.name}: Dateiname stimmt nicht mit kanonischem "
                f"Snapshot-Hash ueberein (erwartet {erwartet!r})"
            )
        if sha in snapshots:
            fehler.append(f"{pfad.name}: doppelter Snapshot-Hash {sha}")
        fehler.extend(
            f"{pfad.name}: {meldung}"
            for meldung in _pruefe_freigabe(daten, schluesselring)
        )
        snapshots[sha] = (pfad, daten)

    if fehler:
        return snapshots, [], fehler

    spitzen, graph_fehler = _pruefe_snapshot_graph(snapshots)
    fehler.extend(graph_fehler)
    return snapshots, spitzen, fehler


def _pruefe_o1_ledger(
    pfad: Path,
    *,
    abox_hash: str,
    eingang_hash: str,
) -> List[str]:
    """Validate O1's full ledger schema plus its gate-specific binding."""
    from rechner_pipeline.gates import abox_validate

    try:
        payload = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"{pfad.name}: nicht als JSON lesbar: {exc}"]
    try:
        entry = GateLedgerEntry.from_dict(payload)
    except (TypeError, ValueError) as exc:
        return [f"{pfad.name}: {exc}"]
    fehler: List[str] = []
    erwartet = {
        "gate": abox_validate.GATE,
        "command": "abox_validate",
        "gate_version": abox_validate.GATE_VERSION,
        "required": True,
        "status": "passed",
    }
    for feld, wert in erwartet.items():
        if getattr(entry, feld) != wert:
            fehler.append(
                f"{pfad.name}: {feld}={getattr(entry, feld)!r} statt {wert!r}"
            )
    erwartete_hashes = {
        "eingang.json": eingang_hash,
        "abgeleitet/abox/abox.json": abox_hash,
    }
    if entry.input_hashes != erwartete_hashes:
        fehler.append(
            f"{pfad.name}: input_hashes muessen exakt die Rollen "
            f"{sorted(erwartete_hashes)} auf dem aktuellen Stand binden"
        )
    if entry.summary.get("exit_code") != 0:
        fehler.append(f"{pfad.name}: summary.exit_code muss 0 sein")
    return fehler


def _redigiere_schluessel_argv(argv: List[str]) -> List[str]:
    redigiert: List[str] = []
    verborgen = False
    for wert in argv:
        if verborgen:
            redigiert.append("<extern-redigiert>")
            verborgen = False
        elif wert == "--freigabe-schluessel":
            redigiert.append(wert)
            verborgen = True
        elif wert.startswith("--freigabe-schluessel="):
            redigiert.append("--freigabe-schluessel=<extern-redigiert>")
        else:
            redigiert.append(wert)
    return redigiert


def _json_typ_und_wertgleich(links: object, rechts: object) -> bool:
    """JSON-Werte ohne die Python-Gleichheit von ``True`` und ``1`` pruefen."""
    if type(links) is not type(rechts):
        return False
    if isinstance(links, dict):
        return set(links) == set(rechts) and all(
            _json_typ_und_wertgleich(links[name], rechts[name])
            for name in links
        )
    if isinstance(links, list):
        return len(links) == len(rechts) and all(
            _json_typ_und_wertgleich(linker, rechter)
            for linker, rechter in zip(links, rechts)
        )
    return links == rechts


def _o3_eingangsabweichungen(
    beleg: dict,
    fall: Path,
    repo_root: Path,
) -> List[str]:
    """Die im O3-Beleg gebundenen Dateien gegen den Jetztstand pruefen.

    A-Box, Spez, Quellerwartungen und ``tafeln.xml`` koennen sich auch
    ohne neuen Commit bewegen. Ein alter gruener Beleg darf dann nicht
    weiter als passend gelten, selbst wenn A-Box- und System-SHA noch
    gleich aussehen.
    """
    abweichungen: List[str] = []
    for name, erwartet in beleg["input_hashes"].items():
        if name == "abgeleitet/abox/abox.json":
            pfad = fall / name
        else:
            kandidat = Path(name)
            pfad = kandidat if kandidat.is_absolute() else repo_root / kandidat
        if not pfad.is_file():
            abweichungen.append(f"{name}: fehlt")
            continue
        gefunden = _sha256_datei(pfad)
        if gefunden != erwartet:
            abweichungen.append(
                f"{name}: SHA-256 {gefunden} statt {erwartet}"
            )
    return abweichungen


def _passende_bestandsbelege(
    *,
    diagnostics: Path,
    fall: Path,
    eingang_sha256: str,
    abox_sha256: str,
    system: Mapping[str, str],
    repo_root: Path,
) -> Tuple[Optional[Dict[str, str]], List[str]]:
    """B1, Suite und Abnahmebericht auf dem aktuellen Stand neu validieren."""
    from rechner_pipeline.gates import abnahmebericht

    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    if not ledger_pfad.is_file():
        return None, [
            "gruener Abnahmebericht-Beleg fehlt: abnahmebericht.gate.json"
        ]
    try:
        ledger = GateLedgerEntry.from_dict(
            json.loads(ledger_pfad.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        return None, [f"Abnahmebericht-Ledger ungueltig: {exc}"]

    fehler: List[str] = []
    erwartet = {
        "gate": abnahmebericht.GATE,
        "command": abnahmebericht.COMMAND,
        "gate_version": abnahmebericht.GATE_VERSION,
        "required": True,
        "status": "passed",
    }
    for feld, wert in erwartet.items():
        if getattr(ledger, feld) != wert:
            fehler.append(
                f"Abnahmebericht-Ledger.{feld} ist "
                f"{getattr(ledger, feld)!r} statt {wert!r}"
            )
    if ledger.summary.get("exit_code") != 0:
        fehler.append("Abnahmebericht-Ledger traegt keinen gruenen Exit-Code")

    bindung = ledger.summary.get("scope_bindung")
    bindungs_fehler = validate_scope_bindung(bindung)
    fehler.extend(bindungs_fehler)
    if isinstance(bindung, dict) and not bindungs_fehler:
        aktuelle_basis = {
            "scope": "bestand",
            "eingang_sha256": eingang_sha256,
            "abox_sha256": abox_sha256,
            "system": dict(system),
        }
        for feld, wert in aktuelle_basis.items():
            if bindung.get(feld) != wert:
                fehler.append(
                    f"Abnahmebericht.scope_bindung.{feld} weicht vom "
                    "aktuellen Fallstand ab"
                )
        try:
            erwartet_bindung = scope_bindung(
                fall,
                repo_root,
                bindung["stichtage"][0],
                bindung["stichtage"][1],
            )
        except (fall_mod.FallFehler, KeyError, IndexError, TypeError) as exc:
            fehler.append(f"Abnahmebericht-Scope-Bindung ungueltig: {exc}")
        else:
            if bindung != erwartet_bindung:
                fehler.append(
                    "Abnahmebericht bindet nicht den aktuellen Eingangs-, "
                    "A-Box-, System- und Stichtagsstand"
                )

    belege = ledger.summary.get("bestandsbelege")
    rollen = bestands_belegrollen()
    if not isinstance(belege, dict) or set(belege) != set(rollen):
        fehler.append(f"Abnahmebericht muss exakt die Bestandsbelege {rollen} binden")
        return None, fehler

    pfade: Dict[str, Path] = {}
    hashes: Dict[str, str] = {}
    for rolle in rollen:
        pfad, artefakt_fehler = pruefe_artefakt_eintrag(
            fall, rolle, belege[rolle]
        )
        fehler.extend(artefakt_fehler)
        if pfad is not None:
            pfade[rolle] = pfad
            hashes[rolle] = belege[rolle]["sha256"]

    renderer_belege = ledger.summary.get("renderer_artefakte")
    renderer_rollen = abnahmebericht.renderer_artefaktrollen()
    if (
        not isinstance(renderer_belege, dict)
        or set(renderer_belege) != set(renderer_rollen)
    ):
        fehler.append(
            "Abnahmebericht muss exakt die Renderer-Artefakte "
            f"{renderer_rollen} binden"
        )
        return None, fehler

    renderer_pfade: Dict[str, Path] = {}
    for rolle in renderer_rollen:
        pfad, artefakt_fehler = pruefe_artefakt_eintrag(
            fall, rolle, renderer_belege[rolle]
        )
        fehler.extend(artefakt_fehler)
        if pfad is not None:
            renderer_pfade[rolle] = pfad

    input_eintraege = {
        rolle: eintrag
        for rolle, eintrag in {
            "b1_ledger": belege["b1_ledger"],
            "migrationssuite": belege["migrationssuite"],
            **renderer_belege,
        }.items()
        if isinstance(eintrag, dict)
        and set(eintrag) == {"pfad", "sha256"}
        and isinstance(eintrag.get("pfad"), str)
        and isinstance(eintrag.get("sha256"), str)
    }
    if len(input_eintraege) == 6:
        pfadnamen = [eintrag["pfad"] for eintrag in input_eintraege.values()]
        if len(set(pfadnamen)) != len(pfadnamen):
            fehler.append(
                "Abnahmebericht-Eingangsrollen muessen eindeutige Pfade binden"
            )
        erwartete_input_hashes = {
            eintrag["pfad"]: eintrag["sha256"]
            for eintrag in input_eintraege.values()
        }
        if ledger.input_hashes != erwartete_input_hashes:
            fehler.append(
                "Abnahmebericht-Ledger.input_hashes muss exakt B1, Suite und "
                "alle vier Renderer-Artefaktrollen binden"
            )

    bericht_eintrag = belege["abnahmebericht"]
    output_hashes = ledger.summary.get("output_hashes")
    erwartete_output_hashes: Dict[str, str] = {}
    if (
        isinstance(bericht_eintrag, dict)
        and set(bericht_eintrag) == {"pfad", "sha256"}
        and isinstance(bericht_eintrag.get("pfad"), str)
        and isinstance(bericht_eintrag.get("sha256"), str)
    ):
        erwartete_output_hashes[bericht_eintrag["pfad"]] = bericht_eintrag[
            "sha256"
        ]
    if (
        not isinstance(output_hashes, dict)
        or not erwartete_output_hashes
        or output_hashes != erwartete_output_hashes
    ):
        fehler.append(
            "Abnahmebericht-Ledger.output_hashes bindet den HTML-Bericht nicht"
        )
    if len(input_eintraege) == 6 and erwartete_output_hashes:
        rollenpfade = [
            eintrag["pfad"] for eintrag in input_eintraege.values()
        ] + list(erwartete_output_hashes)
        if len(set(rollenpfade)) != len(rollenpfade):
            fehler.append(
                "Abnahmebericht-Eingabe- und Outputrollen muessen "
                "eindeutige Pfade binden"
            )
    physische_rollen = {
        **{
            rolle: pfade[rolle]
            for rolle in ("b1_ledger", "migrationssuite")
            if rolle in pfade
        },
        **renderer_pfade,
        **(
            {"abnahmebericht": pfade["abnahmebericht"]}
            if "abnahmebericht" in pfade else {}
        ),
    }
    if len(physische_rollen) == 7:
        kollisionen = abnahmebericht._pfadrollen_kollisionen(physische_rollen)
        if kollisionen:
            fehler.append(
                "Abnahmebericht-Eingabe- und Outputrollen muessen physisch "
                "verschiedene Dateien binden; Kollision: "
                + "; ".join(kollisionen)
            )
    if "abnahmebericht" in pfade and ledger.diagnostics_path != str(
        pfade["abnahmebericht"]
    ):
        fehler.append(
            "Abnahmebericht-Ledger.diagnostics_path bindet den Bericht nicht"
        )

    suite: Optional[dict] = None
    if "migrationssuite" in pfade:
        try:
            suite_roh = json.loads(
                pfade["migrationssuite"].read_text(encoding="utf-8")
            )
            if isinstance(suite_roh, dict):
                suite = suite_roh
            else:
                fehler.append("Migrationssuite ist kein JSON-Objekt")
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fehler.append(f"Migrationssuite unlesbar: {exc}")

    erzeugung = ledger.summary.get("bericht_erzeugung")
    erzeugung_fuer_pruefung = erzeugung
    spec_roh: object = None
    spec: object = None
    transformation: object = None
    if "spec" in renderer_pfade:
        try:
            spec_roh = json.loads(
                renderer_pfade["spec"].read_text(encoding="utf-8")
            )
            spec = abnahmebericht.TransformationsSpec.model_validate(spec_roh)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            TypeError,
            ValueError,
        ) as exc:
            fehler.append(
                f"Gebundene Transformationsspecifikation ungueltig: {exc}"
            )
    if "transformation_ergebnis" in renderer_pfade:
        try:
            transformation = json.loads(
                renderer_pfade["transformation_ergebnis"].read_text(
                    encoding="utf-8"
                )
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fehler.append(f"Gebundenes Transformationsergebnis unlesbar: {exc}")
        else:
            fehler.extend(
                abnahmebericht._transformation_ergebnis_fehler(transformation)
            )

    if isinstance(erzeugung, dict):
        if not _json_typ_und_wertgleich(erzeugung.get("spec"), spec_roh):
            fehler.append(
                "Abnahmebericht-Erzeugung.spec stimmt nicht typ- und wertgenau "
                "mit der gebundenen Transformationsspecifikation ueberein"
            )
        if not _json_typ_und_wertgleich(
            erzeugung.get("transformation_ergebnis"), transformation
        ):
            fehler.append(
                "Abnahmebericht-Erzeugung.transformation_ergebnis stimmt nicht "
                "typ- und wertgenau mit dem gebundenen Transformationsergebnis "
                "ueberein"
            )
        for rolle in ("bestandsbericht_vor", "bestandsbericht_nach"):
            eintrag = renderer_belege[rolle]
            if (
                isinstance(eintrag, dict)
                and erzeugung.get(rolle) != eintrag.get("pfad")
            ):
                fehler.append(
                    f"Abnahmebericht-Erzeugung.{rolle} bindet nicht die "
                    f"Renderer-Artefaktrolle {rolle}"
                )
        erzeugung_fuer_pruefung = dict(erzeugung)
        erzeugung_fuer_pruefung["spec"] = spec_roh
        erzeugung_fuer_pruefung["transformation_ergebnis"] = transformation
        for rolle in ("bestandsbericht_vor", "bestandsbericht_nach"):
            eintrag = renderer_belege[rolle]
            if isinstance(eintrag, dict):
                erzeugung_fuer_pruefung[rolle] = eintrag.get("pfad")

    if suite is not None:
        suite_fehler = abnahmebericht._suite_fehler(suite)
        fehler.extend(suite_fehler)
        if not suite_fehler:
            if (
                isinstance(spec, abnahmebericht.TransformationsSpec)
                and isinstance(transformation, dict)
                and "spec" in renderer_pfade
            ):
                transformations_fehler, _, _ = (
                    abnahmebericht._transformationsvertrag_fehler(
                        fall=fall,
                        spec_pfad=renderer_pfade["spec"],
                        spec=spec,
                        ergebnis=transformation,
                        suite=suite,
                    )
                )
                fehler.extend(transformations_fehler)
            suite_summary = abnahmebericht._suite_zusammenfassung(suite)
            for feld, erwartet in suite_summary.items():
                gefunden = ledger.summary.get(feld)
                if type(gefunden) is not type(erwartet) or gefunden != erwartet:
                    fehler.append(
                        f"Abnahmebericht-Ledger.summary.{feld} stimmt nicht "
                        "mit der neu berechneten Migrationssuite ueberein"
                    )
            if suite_summary["suite_bestanden"] is not True:
                fehler.append("Migrationssuite ist nicht bestanden")
            if (
                spec is not None
                and isinstance(transformation, dict)
                and len(renderer_pfade) == len(renderer_rollen)
                and not abnahmebericht._transformation_ergebnis_fehler(
                    transformation
                )
            ):
                abnahme_summary = abnahmebericht._abnahme_zusammenfassung(
                    suite=suite,
                    spec=spec,
                    transformation_ergebnis=transformation,
                    bestandsbericht_vor=renderer_belege[
                        "bestandsbericht_vor"
                    ]["pfad"],
                    bestandsbericht_nach=renderer_belege[
                        "bestandsbericht_nach"
                    ]["pfad"],
                    fall=fall,
                )
                for feld, erwartet in abnahme_summary.items():
                    gefunden = ledger.summary.get(feld)
                    if not _json_typ_und_wertgleich(gefunden, erwartet):
                        fehler.append(
                            f"Abnahmebericht-Ledger.summary.{feld} stimmt nicht "
                            "mit den gebundenen Renderer-Artefakten ueberein"
                        )
        if isinstance(bindung, dict) and isinstance(
            bindung.get("stichtage"), list
        ):
            stichtage = bindung["stichtage"]
            if len(stichtage) == 2:
                fehler.extend(
                    abnahmebericht._bestands_suite_fehler(
                        suite,
                        stichtag_1=stichtage[0],
                        stichtag_2=stichtage[1],
                        erwartetes_system=dict(system),
                    )
                )
                if "abnahmebericht" in pfade:
                    fehler.extend(
                        abnahmebericht._bericht_fehler(
                            erzeugung=erzeugung_fuer_pruefung,
                            suite=suite,
                            bericht_pfad=pfade["abnahmebericht"],
                            erwartete_stichtage=stichtage,
                            fall=fall,
                        )
                    )
        if "b1_ledger" in pfade:
            fehler.extend(
                abnahmebericht._b1_fehler(
                    ledger_pfad=pfade["b1_ledger"],
                    fall=fall,
                    repo_root=repo_root,
                    suite=suite,
                    erwartetes_system=dict(system),
                )
            )
    if ledger.summary.get("suite_bestanden") is not True:
        fehler.append(
            "Abnahmebericht-Ledger ist nicht auf einer gruenen Suite erzeugt"
        )
    if ledger.summary.get("vollstaendig_geprueft") is not True:
        fehler.append("Abnahmebericht-Ledger ist nicht vollstaendig geprueft")
    if ledger.summary.get("bericht_bestanden") is not True:
        fehler.append("Abnahmebericht-Ledger traegt kein bestandenes Berichtsverdikt")
    if ledger.summary.get("abnahmehindernisse") != []:
        fehler.append("Abnahmebericht-Ledger traegt offene Abnahmehindernisse")

    if fehler:
        return None, fehler
    hashes["abnahmebericht"] = _sha256_datei(ledger_pfad)
    return hashes, []


def entscheide_verzeichnis(fall: Path) -> Path:
    """Snapshots liegen NEBEN dem Eingang: nicht regenerierbar,
    ausserhalb der aufraeumbaren abgeleitet/-Zone."""
    return fall / "entscheide"


def _artefakt_hashes(fall: Path, ausser_gate: str = "") -> Dict[str, str]:
    """Alle entscheidungsrelevanten Artefakte des Falls, gehasht —
    inklusive der registrierten Eingangsdateien selbst und der
    Entscheid-Snapshots ANDERER Gates (Kreuz-Verkettung). Die eigenen
    Gate-Snapshots laufen ueber ``vorgaenger``, nicht ueber die
    Artefaktliste — sonst waere kein Wiederholungs-Aufruf je idempotent.
    """
    kandidaten: List[Path] = [fall / "eingang.json", fall / "fall.json"]
    eingang = fall / "eingang"
    if eingang.is_dir():
        kandidaten.extend(sorted(p for p in eingang.iterdir() if p.is_file()))
    abgeleitet = fall / "abgeleitet"
    for muster in ("abox/abox.json", "abox/coverage.json"):
        kandidaten.append(abgeleitet / muster)
    for verzeichnis in (
        abgeleitet / "spez", abgeleitet / "fachspez",
        abgeleitet / "diagnostics", entscheide_verzeichnis(fall),
    ):
        if not verzeichnis.is_dir():
            continue
        for pfad in sorted(verzeichnis.iterdir()):
            if not pfad.is_file():
                continue
            # Eigene Gate-Snapshots laufen ueber die vorgaenger-Kette;
            # die gate_entscheid-Ledger sind Prozessprotokolle DIESES
            # Werkzeugs, nicht entschiedener Stand — beides wuerde jede
            # Wiederholung un-idempotent machen.
            if (ausser_gate and pfad.parent == entscheide_verzeichnis(fall)
                    and pfad.name.startswith(f"{ausser_gate}-")):
                continue
            if pfad.name.startswith("gate_entscheid"):
                continue
            kandidaten.append(pfad)
    return {
        str(p.relative_to(fall)): _sha256_datei(p)
        for p in kandidaten if p.is_file()
    }


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog="python -m rechner_pipeline.gates.gate_entscheid",
        description="P9-Snapshot eines menschlichen Gates schreiben.",
    )
    parser.add_argument("--fall", default=None)
    parser.add_argument("--gate", default=None, choices=GUELTIGE_GATES)
    parser.add_argument("--entscheid", default=None,
                        choices=["angenommen", "abgelehnt"])
    parser.add_argument("--entscheider", default=None)
    parser.add_argument("--begruendung", default=None)
    parser.add_argument(
        "--rolle", default=None, choices=["mensch", "agent"],
        help="Wer entscheidet. Agenten duerfen NUR ablehnen "
        "(dokumentierter Zwischenstand) — die Annahme eines "
            "menschlichen Gates ist Menschen vorbehalten.",
    )
    parser.add_argument(
        "--freigabe-schluessel",
        dest="freigabe_schluessel",
        action="append",
        default=None,
        help=(
            "Externe HMAC-Schluesseldatei fuer menschliche Annahmen; "
            "wiederholbar fuer historische Schluessel, der letzte signiert. "
            "Die Datei muss ausserhalb des Falls liegen und privat sein."
        ),
    )
    parser.add_argument("--repo-root", dest="repo_root", default=".")
    parser.add_argument("--diagnostics-dir", dest="diagnostics_dir", default=None)
    add_request_json_arg(parser)
    args = parse_gate_args(parser, argv)

    fall = Path(args.fall).resolve() if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )

    ledger_gate = args.gate if args.gate in GUELTIGE_GATES else None
    ledger_command = (
        f"gate_entscheid_{ledger_gate.lower().replace('-', '')}"
        if ledger_gate else "gate_entscheid"
    )
    ledger_gate_id = f"P9.{ledger_gate or '?'}"
    redigierte_command_line = _redigiere_schluessel_argv(
        list(argv if argv is not None else sys.argv[1:])
    )
    ledger_start_fehler = begin_gate_ledger_attempt(
        command=ledger_command,
        gate=ledger_gate_id,
        gate_version=GATE_VERSION,
        diagnostics_dir=diagnostics_dir,
        repo_root=Path(args.repo_root) if args.repo_root else None,
        started_at=started_at,
        command_line=redigierte_command_line,
    )
    if ledger_start_fehler is not None:
        return ledger_start_fehler

    def _finalize(result):
        return finalize_gate_ledger(result)

    def _usage(message: str):
        return _finalize(build_result(
            command=ledger_command, gate=ledger_gate_id,
            gate_version=GATE_VERSION, exit_code=Exit.USAGE,
            errors=[{"code": "usage", "message": message}],
        ))

    fehlend = [name for name, wert in (
        ("--fall", fall), ("--gate", args.gate),
        ("--entscheid", args.entscheid), ("--entscheider", args.entscheider),
        ("--begruendung", args.begruendung),
    ) if not wert]
    if fehlend:
        return _usage("erforderlich: " + ", ".join(fehlend))
    # --request-json umgeht die argparse-choices — hier hart nachpruefen.
    if args.gate not in GUELTIGE_GATES:
        return _usage(f"unbekanntes Gate {args.gate!r} (erlaubt: "
                      + ", ".join(GUELTIGE_GATES) + ")")
    if args.entscheid not in ("angenommen", "abgelehnt"):
        return _usage(f"unbekannter Entscheid {args.entscheid!r}")
    if args.rolle not in ("mensch", "agent"):
        return _usage("--rolle mensch|agent ist erforderlich (Agenten "
                      "koennen nur ablehnen)")
    if args.rolle == "agent" and args.entscheid == "angenommen":
        return _usage(
            "Rolle 'agent' darf nicht annehmen — die Annahme eines "
            "menschlichen Gates ist Menschen vorbehalten (P2/P4); "
            "Agenten dokumentieren Zwischenstaende als Ablehnung"
        )
    if not (fall / "eingang.json").is_file():
        return _usage(
            f"kein Fall-Arbeitsbereich: {fall} (anlegen mit: python -m "
            f"rechner_pipeline.fall anlegen --fall {fall}, dann je Quelle "
            f"python -m rechner_pipeline.fall registrieren --fall {fall} "
            "--datei <quelle>)"
        )

    def _sperre(code: str, message: str):
        return _finalize(build_result(
            command=ledger_command, gate=f"P9.{args.gate}",
            gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{"code": code, "message": message}],
            paths={"fall": str(fall)},
        ))

    entscheid_systemstand = systemstand(Path(args.repo_root).resolve())
    o3_belege: Dict[str, List[str]] = {}
    pflichtbelege: Dict[str, List[str]] = {}
    fall_scope: Optional[str] = None
    if args.gate in ("G-A", "G-2"):
        try:
            fall_scope = fall_mod.lade_scope(fall)
        except fall_mod.FallFehler as exc:
            return _sperre(
                "fall_scope",
                f"{args.gate} verweigert: Fall-Scope ist nicht "
                f"maschinenlesbar deklariert: {exc}",
            )
    schluesselring: Dict[str, bytes] = {}
    aktiver_schluessel: Optional[str] = None
    schluessel_geladen = False

    def _schluessel_laden() -> List[str]:
        nonlocal schluesselring, aktiver_schluessel, schluessel_geladen
        if not schluessel_geladen:
            schluesselring, fehler, aktiver_schluessel = (
                _lade_freigabe_schluessel(args.freigabe_schluessel, fall)
            )
            schluessel_geladen = True
            return fehler
        return []

    # Annahme-Sperre: eine Annahme setzt einen integeren Fall und
    # endgueltige Entscheidungen voraus — sonst wuerde ein ungeloester
    # Quellen-Widerspruch oder der Arbeitsstand eines Agenten still zur
    # abgenommenen Wahrheit (P2/P4). Die A-Box ist dafuer PFLICHT: eine
    # Sperre, die per Dateiloeschung abschaltbar waere, ist keine.
    if args.entscheid == "angenommen":
        import json as _json

        from rechner_pipeline.ontologie.abox import (
            abox_pfad,
            validate_abox,
        )
        from rechner_pipeline.ontologie.tbox import ABox

        eingangs_fehler = fall_mod.pruefen(fall)
        if eingangs_fehler:
            return _sperre("eingang", "Annahme verweigert — Eingang "
                           "verletzt das Register: "
                           + "; ".join(eingangs_fehler[:5])
                           + " (Lage zeigen mit: python -m "
                           f"rechner_pipeline.fall status --fall {fall}; eine "
                           "verlorene Kopie stellt python -m "
                           f"rechner_pipeline.fall registrieren --fall {fall} "
                           "--datei <quelle> wieder her)")
        if not abox_pfad(fall).is_file():
            return _sperre(
                "abox", f"Annahme verweigert: keine A-Box ({abox_pfad(fall)}) "
                "— ohne Stage 1 gibt es nichts abzunehmen (Fragmente je "
                "Quelle extrahieren, dann zusammenfuehren mit: python -m "
                f"rechner_pipeline.gates.abox_merge --fall {fall})",
            )
        try:
            abox_roh = abox_pfad(fall).read_bytes()
            abox = ABox.model_validate_json(abox_roh)
        except Exception as exc:  # Ladefehler ist Befund MIT Ledger
            return _sperre("abox", f"A-Box unlesbar: {exc}")
        register = _json.loads(
            (fall / "eingang.json").read_text(encoding="utf-8")
        )
        abox_fehler = validate_abox(abox, register)
        if abox_fehler:
            return _sperre("abox", "Annahme verweigert — A-Box "
                           "inkonsistent: " + "; ".join(abox_fehler[:5]))
        offene = sorted(
            d.id for d in abox.diskrepanzen if d.status == "offen"
        )
        if offene:
            return _sperre(
                "offen", "Annahme verweigert: OFFENE Diskrepanzen — "
                + ", ".join(offene)
                + " (aufloesen mit python -m "
                "rechner_pipeline.ontologie.entscheide)",
            )
        vorlaeufige = sorted(
            d.id for d in abox.diskrepanzen
            if d.entscheidung is not None and d.entscheidung.vorlaeufig
        )
        if vorlaeufige:
            return _sperre(
                "vorlaeufig", "Annahme verweigert: vorlaeufige "
                "Diskrepanz-Aufloesungen stehen aus — "
                + ", ".join(vorlaeufige)
                + " (aufloesen mit python -m "
                "rechner_pipeline.ontologie.entscheide)",
            )

        # Gate-Vorbedingungen (Systempruefung Befund 1): die Annahme
        # RECHNET ihre Voraussetzungen — sie glaubt sie nicht.
        # Derselbe Byte-String wird validiert und gehasht: G-2 darf nicht
        # versehentlich eine zwischen zwei Lesevorgaengen geaenderte A-Box
        # als den geprueften Stand protokollieren.
        abox_hash = hashlib.sha256(abox_roh).hexdigest()
        diagnostics = fall / "abgeleitet" / "diagnostics"

        o1_pfad = diagnostics / "abox_validate.gate.json"
        o1_kommando = (
            "python -m rechner_pipeline.gates.abox_validate "
            f"--fall {fall} --repo-root {args.repo_root}"
        )
        if not o1_pfad.is_file():
            return _sperre(
                "vorbedingung",
                "Annahme verweigert: Gate O1 (abox_validate) ist nie "
                f"gelaufen ({o1_pfad.name} fehlt) — nachholen mit: {o1_kommando}",
            )
        o1_fehler = _pruefe_o1_ledger(
            o1_pfad,
            abox_hash=abox_hash,
            eingang_hash=_sha256_datei(fall / "eingang.json"),
        )
        if o1_fehler:
            return _sperre(
                "vorbedingung",
                "Annahme verweigert: Gate O1 (abox_validate) verletzt den "
                "Ledger-/Provenienzvertrag: "
                + "; ".join(o1_fehler[:5])
                    + f" — Gate auf dem aktuellen Stand neu fahren: {o1_kommando}",
                )
        if args.gate == "G-2":
            pflichtbelege["o1_ledger"] = [_sha256_datei(o1_pfad)]

        if args.gate == "G-A":
            # Aktuarielle Abnahme (ADR-010): Im Bestands-Scope stuetzt
            # sich der Entscheid auf das Testergebnis und den Bericht
            # des aktuariellen Tests; beide werden als Pflichtbelege
            # gepinnt und muessen vom aktuartest-Gate mit gruenem
            # Ledger auf GENAU diesen Bytes belegt sein. Im Tarif-Scope
            # gibt es keine Vertragslieferung und damit keine eigenen
            # Testartefakte (Rollenmenge leer); die O3-Belege sind
            # ueber artefakt_hashes ohnehin gepinnt.
            if fall_scope == "bestand":
                berichte = fall / "abgeleitet" / "berichte"
                test_pfad = berichte / "aktuartest.json"
                bericht_pfad = berichte / "aktuartest.html"
                ledger_pfad = diagnostics / "aktuartest.gate.json"
                ga_kommando = (
                    "python -m rechner_pipeline.gates.aktuartest "
                    f"--fall {fall} --titel <titel>"
                )
                fehlende = [
                    pfad.name
                    for pfad in (test_pfad, bericht_pfad, ledger_pfad)
                    if not pfad.is_file()
                ]
                if fehlende:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: aktuarieller Test ohne "
                        f"vollstaendige Belege ({', '.join(fehlende)} "
                        f"fehlt) — nachholen mit: {ga_kommando}",
                    )
                try:
                    ga_ledger = json.loads(
                        ledger_pfad.read_text(encoding="utf-8")
                    )
                except (OSError, ValueError) as exc:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: aktuartest-Ledger unlesbar: "
                        f"{exc} — Gate neu fahren: {ga_kommando}",
                    )
                ga_fehler: List[str] = []
                if ga_ledger.get("command") != "aktuartest":
                    ga_fehler.append("Ledger gehoert nicht zu aktuartest")
                if ga_ledger.get("status") != "passed":
                    ga_fehler.append(
                        "aktuartest ist nicht bestanden — eine Annahme "
                        "ohne gruene Vorlage waere ohne Grundlage "
                        "(Ablehnung bleibt moeglich)"
                    )
                erwartete_belege = {
                    "abgeleitet/berichte/aktuartest.json":
                        _sha256_datei(test_pfad),
                    "abgeleitet/berichte/aktuartest.html":
                        _sha256_datei(bericht_pfad),
                }
                ledger_belege = ga_ledger.get("summary", {}).get("belege")
                if ledger_belege != erwartete_belege:
                    ga_fehler.append(
                        "aktuartest-Ledger belegt nicht die aktuellen "
                        "Bytes von Testergebnis und Bericht"
                    )
                if ga_fehler:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: "
                        + "; ".join(ga_fehler[:5])
                        + f" — Gate auf dem aktuellen Stand neu fahren: "
                        f"{ga_kommando}",
                    )
                pflichtbelege["aktuartest"] = [
                    erwartete_belege["abgeleitet/berichte/aktuartest.json"]
                ]
                pflichtbelege["aktuartest_bericht"] = [
                    erwartete_belege["abgeleitet/berichte/aktuartest.html"]
                ]
            erwartete_rollen = fall_mod.belegrollen(
                "G-A", fall_scope or ""
            )
            if set(pflichtbelege) != set(erwartete_rollen):
                fehlende_rollen = sorted(
                    set(erwartete_rollen) - set(pflichtbelege)
                )
                fremde_rollen = sorted(
                    set(pflichtbelege) - set(erwartete_rollen)
                )
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: aus dem Fall-Scope abgeleitete "
                    f"Pflichtbelege unvollstaendig; fehlen="
                    f"{fehlende_rollen}, fremd={fremde_rollen}",
                )
            pflichtbelege = {
                rolle: pflichtbelege[rolle] for rolle in erwartete_rollen
            }

        if args.gate == "G-2":
            # Die Generationen werden nicht geraten, sondern aus der A-Box
            # genommen — und JE GENERATION als eigene Zeile ausgegeben:
            # ein zusammengesetztes "klv/tg2012|klv/tg2015" waere in der
            # Shell eine Pipe und damit kein Kommando, das ein Bediener
            # uebernehmen kann. O3 laeuft ohnehin je Generation.
            generationen = sorted(g.id for g in abox.generationen)
            if not generationen:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: die A-Box enthaelt keine Generation - "
                    "damit existiert keine O3-Pruefmenge",
                )
            o3_kommando = "\n".join(
                "python -m rechner_pipeline.gates.generation_golden "
                f"--fall {fall} --generation {generation} "
                f"--repo-root {args.repo_root}"
                for generation in generationen
            )
            beleg_dateien = sorted(diagnostics.glob(O3_BELEG_GLOB))
            if not beleg_dateien:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: kein unveraenderlicher O3-Beleg "
                    f"vorhanden - je A-Box-Generation nachholen mit:\n{o3_kommando}",
                )

            geladene_belege: List[dict] = []
            beleg_fehler: List[str] = []
            for pfad in beleg_dateien:
                daten, fehler = pruefe_o3_beleg(pfad)
                beleg_fehler.extend(fehler)
                if daten is not None and not fehler:
                    geladene_belege.append(daten)
            if beleg_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: O3-Belegvertrag verletzt: "
                    + "; ".join(beleg_fehler[:5]),
                )

            repo_root = Path(args.repo_root).resolve()
            eingangsabweichungen = {
                beleg["beleg_sha256"]: _o3_eingangsabweichungen(
                    beleg, fall, repo_root
                )
                for beleg in geladene_belege
                if beleg["abox_sha256"] == abox_hash
                and beleg["system"] == entscheid_systemstand
            }
            passende_belege = [
                beleg for beleg in geladene_belege
                if beleg["abox_sha256"] == abox_hash
                and beleg["system"] == entscheid_systemstand
                and not eingangsabweichungen[beleg["beleg_sha256"]]
            ]
            belegt = {beleg["generation"] for beleg in passende_belege}
            erwartet = set(generationen)
            if belegt != erwartet:
                teile: List[str] = []
                fehlend = sorted(erwartet - belegt)
                zusaetzlich = sorted(belegt - erwartet)
                if fehlend:
                    teile.append(f"O3-Beleg fehlt fuer {fehlend}")
                if zusaetzlich:
                    teile.append(
                        f"O3-Belegmenge enthaelt fremde Generationen {zusaetzlich}"
                    )
                abox_abweichend = sorted({
                    beleg["generation"] for beleg in geladene_belege
                    if beleg["abox_sha256"] != abox_hash
                } & erwartet)
                system_abweichend = sorted({
                    beleg["generation"] for beleg in geladene_belege
                    if beleg["abox_sha256"] == abox_hash
                    and beleg["system"] != entscheid_systemstand
                } & erwartet)
                if abox_abweichend:
                    teile.append(
                        "A-Box-Stand abweichend fuer " + str(abox_abweichend)
                    )
                if system_abweichend:
                    teile.append(
                        "Systemstand abweichend fuer " + str(system_abweichend)
                    )
                input_abweichend = sorted({
                    beleg["generation"] for beleg in geladene_belege
                    if eingangsabweichungen.get(beleg["beleg_sha256"])
                } & erwartet)
                if input_abweichend:
                    details = [
                        meldung
                        for beleg in geladene_belege
                        if beleg["generation"] in input_abweichend
                        for meldung in eingangsabweichungen.get(
                            beleg["beleg_sha256"], []
                        )
                    ]
                    teile.append(
                        "O3-Eingangsartefakte abweichend fuer "
                        f"{input_abweichend}: " + "; ".join(details[:3])
                    )
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: " + "; ".join(teile)
                    + f" - O3 auf dem aktuellen Stand neu fahren:\n{o3_kommando}",
                )

            o3_belege = {
                generation: sorted(
                    beleg["beleg_sha256"]
                    for beleg in passende_belege
                    if beleg["generation"] == generation
                )
                for generation in generationen
            }
            pflichtbelege["o3_belege"] = sorted(
                beleg_sha
                for belege_der_generation in o3_belege.values()
                for beleg_sha in belege_der_generation
            )
            # Geltender G-1-Annahme-Snapshot auf DIESEM A-Box-Stand.
            schluessel_fehler = _schluessel_laden()
            if schluessel_fehler:
                return _sperre(
                    "freigabe",
                    "Annahme verweigert: externe Freigabeschluessel "
                    "ungueltig: " + "; ".join(schluessel_fehler[:5]),
                )
            verzeichnis_g1 = entscheide_verzeichnis(fall)
            g1_snapshots, g1_spitzen, g1_fehler = _lade_snapshot_kette(
                verzeichnis_g1, "G-1", fall, schluesselring
            )
            if g1_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: G-1-Snapshot-Vertrag verletzt: "
                    + "; ".join(g1_fehler[:5]),
                )
            g1_spitze = (
                g1_snapshots[g1_spitzen[0]][1] if len(g1_spitzen) == 1 else None
            )
            eingang_hash = _sha256_datei(fall / "eingang.json")
            passend = (
                g1_spitze is not None
                and g1_spitze["entscheid"] == "angenommen"
                and g1_spitze["artefakt_hashes"].get(
                    "abgeleitet/abox/abox.json"
                ) == abox_hash
                and g1_spitze["artefakt_hashes"].get("eingang.json")
                == eingang_hash
                and g1_spitze["artefakt_hashes"].get("fall.json")
                == _sha256_datei(fall / "fall.json")
                and g1_spitze["system"] == entscheid_systemstand
            )
            if not passend:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: keine eindeutige, signierte G-1-"
                    "ANNAHME auf aktuellem Scope-, Eingangs-, A-Box- und "
                    "Systemstand "
                    "— G-2 nimmt denselben Stand ab, den G-1 gesehen hat, "
                    "oder gar keinen (G-1 auf diesem Stand entscheiden mit: python -m "
                    "rechner_pipeline.gates.gate_entscheid --fall "
                    f"{fall} --gate G-1 --entscheid angenommen --rolle mensch "
                    "--entscheider <name> --begruendung <text> "
                    "--freigabe-schluessel <externe-datei>)",
                )
            assert g1_spitze is not None
            pflichtbelege["g1_snapshot"] = [g1_spitze["snapshot_sha256"]]

            # G-A geht G-2 voraus (ADR-010): Ein G-2-Entscheid ohne
            # geltende, signierte aktuarielle Abnahme auf DEMSELBEN
            # Stand ist unmoeglich. Die Rueckschleife bleibt zulaessig
            # (neue Snapshots), nur die Umkehrung nicht.
            ga_snapshots, ga_spitzen, ga_ketten_fehler = (
                _lade_snapshot_kette(
                    verzeichnis_g1, "G-A", fall, schluesselring
                )
            )
            if ga_ketten_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: G-A-Snapshot-Vertrag verletzt: "
                    + "; ".join(ga_ketten_fehler[:5]),
                )
            ga_spitze = (
                ga_snapshots[ga_spitzen[0]][1]
                if len(ga_spitzen) == 1 else None
            )
            ga_passend = (
                ga_spitze is not None
                and ga_spitze["entscheid"] == "angenommen"
                and ga_spitze["artefakt_hashes"].get(
                    "abgeleitet/abox/abox.json"
                ) == abox_hash
                and ga_spitze["artefakt_hashes"].get("eingang.json")
                == eingang_hash
                and ga_spitze["artefakt_hashes"].get("fall.json")
                == _sha256_datei(fall / "fall.json")
                and ga_spitze["system"] == entscheid_systemstand
            )
            if not ga_passend:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: keine eindeutige, signierte "
                    "G-A-ANNAHME (aktuarielle Abnahme) auf aktuellem "
                    "Eingangs-, A-Box- und Systemstand — G-A geht G-2 "
                    "voraus (ADR-010; entscheiden mit: python -m "
                    "rechner_pipeline.gates.gate_entscheid --fall "
                    f"{fall} --gate G-A --entscheid angenommen --rolle "
                    "mensch --entscheider <name> --begruendung <text> "
                    "--freigabe-schluessel <externe-datei>)",
                )
            assert ga_spitze is not None
            pflichtbelege["ga_snapshot"] = [ga_spitze["snapshot_sha256"]]

            if fall_scope == "bestand":
                bestandsbelege, bestands_fehler = _passende_bestandsbelege(
                    diagnostics=diagnostics,
                    fall=fall,
                    eingang_sha256=eingang_hash,
                    abox_sha256=abox_hash,
                    system=entscheid_systemstand,
                    repo_root=repo_root,
                )
                if bestands_fehler or bestandsbelege is None:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: Bestandsbelege verletzen "
                        "den Beleg-/Provenienzvertrag: "
                        + "; ".join(bestands_fehler[:5])
                        + " — B1, vollstaendige Migrationssuite und Abnahmebericht "
                        "auf demselben Stand neu erzeugen",
                    )
                for rolle, beleg_sha256 in bestandsbelege.items():
                    pflichtbelege[rolle] = [beleg_sha256]

            erwartete_rollen = fall_mod.g2_belegrollen(fall_scope or "")
            if set(pflichtbelege) != set(erwartete_rollen):
                fehlende_rollen = sorted(set(erwartete_rollen) - set(pflichtbelege))
                fremde_rollen = sorted(set(pflichtbelege) - set(erwartete_rollen))
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: aus dem Fall-Scope abgeleitete "
                    f"Pflichtbelege unvollstaendig; fehlen={fehlende_rollen}, "
                    f"fremd={fremde_rollen}",
                )
            pflichtbelege = {
                rolle: pflichtbelege[rolle] for rolle in erwartete_rollen
            }

    verzeichnis = entscheide_verzeichnis(fall)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    schluessel_fehler = _schluessel_laden()
    if schluessel_fehler:
        return _sperre(
            "freigabe",
            "Entscheid verweigert: externe Freigabeschluessel ungueltig: "
            + "; ".join(schluessel_fehler[:5]),
        )
    bestehende, spitzen, ketten_fehler = _lade_snapshot_kette(
        verzeichnis, args.gate, fall, schluesselring
    )
    if ketten_fehler:
        return _sperre(
            "snapshot",
            "Entscheid verweigert: P9-Snapshot-Vertrag verletzt: "
            + "; ".join(ketten_fehler[:5]),
        )
    geltende = [bestehende[sha] for sha in spitzen]

    kern_inhalt = {
        "command": "gate_entscheid",
        "gate_version": GATE_VERSION,
        "gate": args.gate,
        "entscheid": args.entscheid,
        "entscheider": args.entscheider,
        "rolle": args.rolle,
        "begruendung": args.begruendung,
        "fall": str(fall),
        "artefakt_hashes": _artefakt_hashes(fall, ausser_gate=args.gate),
        "system": entscheid_systemstand,
    }
    if args.gate in ("G-A", "G-2"):
        kern_inhalt["fall_scope"] = fall_scope
        kern_inhalt["pflichtbelege"] = pflichtbelege
    if args.gate == "G-2":
        kern_inhalt["o3_belege"] = o3_belege
    # Idempotenz gegen den GELTENDEN Snapshot: derselbe Entscheid auf
    # demselben Stand wird gemeldet, nicht dupliziert. Ein INHALTLICH
    # anderer Entscheid erzeugt einen neuen Snapshot, der alle
    # bisherigen pinnt (Kette).
    for pfad, daten in geltende:
        if all(daten.get(k) == v for k, v in kern_inhalt.items()):
            return _finalize(build_result(
                command=ledger_command, gate=f"P9.{args.gate}",
                gate_version=GATE_VERSION, exit_code=Exit.OK,
                paths={"fall": str(fall), "snapshot": str(pfad)},
                summary={"gate": args.gate, "entscheid": args.entscheid,
                         "snapshot_sha256": daten.get("snapshot_sha256"),
                         "bereits_vorhanden": True},
                input_hashes=dict(daten["artefakt_hashes"]),
                output_hashes={str(pfad): _sha256_datei(pfad)},
            ))

    vorgaenger = sorted(bestehende)
    snapshot = {
        "schema_version": P9_SNAPSHOT_SCHEMA_VERSION,
        **kern_inhalt,
        "vorgaenger": vorgaenger,
        "entschieden_am": utc_now(),
    }
    if args.entscheid == "angenommen":
        if aktiver_schluessel is None:
            return _sperre(
                "freigabe",
                "Annahme verweigert: --freigabe-schluessel <externe-datei> "
                "ist erforderlich; ein frei editierbarer Fall darf seine "
                "menschliche Freigabe nicht selbst behaupten",
            )
        snapshot["freigabe"] = _freigabe_fuer(
            snapshot, schluesselring[aktiver_schluessel]
        )
    inhalt_hash = p9_snapshot_sha256(snapshot)
    snapshot["snapshot_sha256"] = inhalt_hash
    schema_fehler = P9Snapshot.validate_payload(snapshot)
    if schema_fehler:
        return _sperre(
            "snapshot",
            "Interner P9-Snapshot verletzt sein Schema: "
            + "; ".join(schema_fehler[:5]),
        )

    ziel = verzeichnis / _snapshot_dateiname(args.gate, inhalt_hash)
    payload = (
        json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    try:
        with ziel.open("xb") as datei:
            datei.write(payload)
    except FileExistsError:
        return _usage(f"Snapshot existiert bereits: {ziel} — nie ueberschreiben")
    ergebnis_summary = {
        "gate": args.gate,
        "entscheid": args.entscheid,
        "entscheider": args.entscheider,
        "rolle": args.rolle,
        "snapshot_sha256": inhalt_hash,
        "vorgaenger": len(vorgaenger),
        "artefakte": len(snapshot["artefakt_hashes"]),
        "system_commit": snapshot["system"]["commit"][:12],
        "system_dirty": snapshot["system"]["dirty"],
    }
    if args.entscheid == "angenommen":
        ergebnis_summary["freigabe_schluessel_sha256"] = snapshot["freigabe"][
            "schluessel_sha256"
        ]
    if args.gate == "G-2":
        ergebnis_summary["o3_belege"] = o3_belege
        ergebnis_summary["fall_scope"] = fall_scope
        ergebnis_summary["pflichtbelege"] = pflichtbelege
    return _finalize(build_result(
        command=ledger_command, gate=f"P9.{args.gate}",
        gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"fall": str(fall), "snapshot": str(ziel)},
        summary=ergebnis_summary,
        input_hashes=dict(snapshot["artefakt_hashes"]),
        output_hashes={str(ziel): _sha256_datei(ziel)},
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
