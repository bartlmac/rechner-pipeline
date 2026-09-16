"""``gate_entscheid`` — der P9-Snapshot eines menschlichen Gates.

Ein menschliches Gate (A-Q1 fachlich; A-M1, A-M2, A-M3 die drei
aktuariellen Abnahmen; A-M4 Migrationsabnahme; A-O1 T-Box-Aenderung)
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

A-M1 und A-M4 leiten ihre Pflichtbelegrollen JE GATE aus dem expliziten
Fall-Scope ab (ADR-009, fortgeschrieben durch ADR-010). A-M1 pinnt im
Bestands-Scope Testergebnis und Bericht des aktuariellen Tests (gruener
aktuartest-Ledger auf genau diesen Bytes); im Tarif-Scope ist seine
Rollenmenge leer. A-M4 braucht im Tariffall P-Q3, A-Q1, A-M1 und P-K1; ein
Bestandsfall zusaetzlich den gruenen P-B1-Beleg, die vollstaendige Suite
und den Abnahmebericht desselben Eingangs-, A-Box-, System-, Bestands-
und Zwei-Stichtagsstands. Die Reihenfolge ist erzwungen: Ein
A-M4-Entscheid ohne geltende, signierte A-M1-Annahme auf demselben Stand
ist unmoeglich (ADR-010); im Bestands-Scope gilt dasselbe fuer A-M2 und
A-M3 (Entscheidung des Auftraggebers 2026-08-31), im Tarif-Scope bleibt
es bei A-M1. Im Abnahme-Ledger verlangt A-M4 ausserdem die
vier festen Renderer-Artefaktrollen, prueft ihre aktuellen Bytes und
leitet das Berichtsverdikt aus den gebundenen Inhalten neu ab.

Run via::

    python -m rechner_pipeline.gates.gate_entscheid --fall faelle/baldrian-klv-tg2015 \\
        --gate A-Q1 --entscheid angenommen --entscheider "maintainer" \\
        --begruendung "..." --freigabe-schluessel /sicher/p9.key \
        [--repo-root .]

Knoten: klv
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import os
import sys
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.models import anker as anker_mod
from rechner_pipeline.gates._common import (
    Exit,
    GeleseneDatei,
    GateArgumentParser,
    GateCliContract,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    lies_gehasht,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.gates._fall_scope import (
    bestands_belegrollen,
    lies_artefakt_eintrag,
    pruefe_artefakt_eintrag,
    scope_bindung,
    validate_scope_bindung,
)
from rechner_pipeline.gates._provenienz import (
    O3_BELEG_GLOB,
    PRODUKTIVER_ZWEIG,
    git_stand,
    pruefe_pk1_beleg,
    systemstand,
    zweig_ist_aktuell,
)
from rechner_pipeline.models.schemas import (
    GateLedgerEntry,
    P9_AKTUARIELLE_ABNAHMEN,
    P9_FREIGABE_VERFAHREN,
    P9_GATE_VERSION,
    P9_SNAPSHOT_SCHEMA_VERSION,
    P9Snapshot,
    p9_freigabe_nachricht,
    p9_snapshot_sha256,
)

GATE_VERSION = P9_GATE_VERSION
# Umzug 2026-09-01: der Rollen-/Gate-Vertrag lebt in models.zeichnung
# (paketuebergreifend — auch ontologie.entscheide liest ihn seither).
from rechner_pipeline.models.zeichnung import (
    GATES_MIT_PFLICHTBELEGEN,
    ausserhalb_des_falls,  # noqa: E402
    GUELTIGE_GATES,
    lade_zeichnungsordnung as _models_lade_zeichnungsordnung,
    zeichnungsrolle as _models_zeichnungsrolle,
    gueltige_rollenkennung,
    zeichnung_fuer,
)
#: Die drei aktuariellen Abnahmen desselben migrierten Bestands. Sie
#: laufen ueber DENSELBEN Vertrag — je Abnahme ein Testergebnis, ein
#: Bericht und ein Ledger des ``aktuartest``-Gates — und unterscheiden
#: sich nur im Dateinamen, den das Gate aus der Abnahme bildet. Deshalb
#: prueft sie ein Zweig und nicht drei: Eine Abnahme, die anders
#: geprueft wuerde als ihre Geschwister, waere eine fachliche Aussage
#: und keine Namensvariante. Die Liste selbst gehoert zum
#: Snapshot-Vertrag (``models.schemas``) — sie hier zu wiederholen
#: hiesse, dieselbe Aussage an zwei Orten zu pflegen.
AKTUARIELLE_ABNAHMEN = P9_AKTUARIELLE_ABNAHMEN
CLI_CONTRACT = GateCliContract(
    command="gate_entscheid",
    gate="entscheid.?",
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


#: Gates, die eine Zeichnungsordnung einer Rolle zuordnen kann. "*" heisst
#: alle -- die Eskalationsrolle des Menschen. Massgeblich sind ALLE
#: zeichenbaren Gates: Eine engere Liste war ein Loch der Ordnung --
#: A-O1 liess sich zeichnen, aber keiner Rolle zuweisen (gefunden beim
#: Aufsetzen der Vier-Rollen-Regie fuer Fall-Lauf 2).
ZEICHNUNG_GATES = GUELTIGE_GATES


def _lade_zeichnungsordnung(
    raw: object, fall: Path
) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Zeichnungsordnung laden — delegiert an models.zeichnung.

    Der Vertrag (Rollen an Fingerabdruecke, Gates an Rollen, Ordnung
    ausserhalb des Falls, keine geteilten Schluessel) ist
    paketuebergreifend und lebt seit dem Vier-Rollen-Modell in
    ``models.zeichnung`` — ontologie.entscheide liest ihn ebenfalls.
    Der Alias hier bleibt, weil Gates und Tests ihn kennen.
    """
    return _models_lade_zeichnungsordnung(raw, fall)


def _zeichnungsrolle(
    ordnung: dict, schluessel_sha256: str
) -> Optional[str]:
    """Die Rolle, der dieser Fingerabdruck gehoert (models.zeichnung)."""
    return _models_zeichnungsrolle(ordnung, schluessel_sha256)

def _zeichnungsfehler(
    ordnung: Optional[dict], gate: str, schluessel_sha256: str
) -> Optional[str]:
    """Warum dieser Schluessel dieses Gate NICHT zeichnen darf (None = darf)."""
    if ordnung is None:
        return None
    rolle = _zeichnungsrolle(ordnung, schluessel_sha256)
    if rolle is None:
        return (
            "der Freigabeschluessel gehoert keiner Rolle der "
            "Zeichnungsordnung -- wer nicht in der Ordnung steht, "
            "zeichnet nicht"
        )
    gates = ordnung["rollen"][rolle].get("gates", [])
    if "*" in gates or gate in gates:
        return None
    return (
        f"die Rolle {rolle!r} ist fuer {gate} nicht zeichnungsberechtigt "
        f"(ihre Gates: {gates or 'keine'})"
    )


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


def pruefe_snapshot_ohne_schluessel(
    daten: Any, dateiname: str
) -> List[str]:
    """Was sich an einem Entscheid-Snapshot OHNE Schluessel pruefen laesst.

    Fuer Leser, die keinen Schluesselring haben duerfen — die
    Darstellungswerkzeuge der Vorfuehrung sind genau solche Leser: Sie
    zeigen Entscheide an, und Schluesselmaterial hat in einem
    Darstellungswerkzeug nichts verloren.

    Geprueft wird, was ohne Geheimnis pruefbar ist, und das ist mehr,
    als es zunaechst scheint: das Schema (:class:`P9Snapshot`), die
    Selbstadressierung (der kanonische Hash ueber alle Felder ausser
    ihm selbst) und der Dateiname, der genau diesen Hash tragen muss.
    Eine frei erfundene Datei scheitert daran, denn ihr Hash passt
    nicht zu ihrem Inhalt.

    NICHT geprueft wird die Freigabesignatur — sie braucht den
    Schluessel. Wer diese Funktion benutzt, darf einen Snapshot
    deshalb NIE als "gezeichnet" oder "signiert" ausweisen, sondern
    nur als strukturell unversehrt; die Signaturpruefung leistet
    ``pruefe_zeichnungskette`` mit Schluesselring. Der Unterschied ist
    kein Detail: Externes Review T19-02 fand genau hier eine
    kryptografische Aussage, die die Darstellungsschicht nie geprueft
    hatte.

    Rueckgabe: leere Liste = strukturell unversehrt, sonst die Befunde.
    """
    fehler = P9Snapshot.validate_payload(daten)
    if fehler:
        return fehler
    sha = daten.get("snapshot_sha256")
    erwarteter_hash = p9_snapshot_sha256(daten)
    if sha != erwarteter_hash:
        return [
            "Selbstadressierung verletzt: der Inhalt ergibt "
            f"{erwarteter_hash[:16]}…, der Snapshot behauptet "
            f"{str(sha)[:16]}…"
        ]
    erwarteter_name = _snapshot_dateiname(str(daten.get("gate")), str(sha))
    if dateiname != erwarteter_name:
        return [
            f"Dateiname {dateiname!r} passt nicht zum kanonischen "
            f"Snapshot-Hash (erwartet {erwarteter_name!r})"
        ]
    return []


#: Schema des A-O1-Belegs (Review T22-02).
TBOX_AENDERUNG_SCHEMA_VERSION = 1
_SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _semver_tuple(version: str) -> tuple:
    return tuple(int(teil) for teil in version.split("."))


def pruefe_tbox_aenderung(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    repo_root: Path | None = None,
) -> List[str]:
    """Den Beleg einer T-Box-Aenderung gegen Code und Artefakt halten.

    Der Beleg sagt, VON welcher Version NACH welcher die T-Box geht, mit
    welchem Modul-Hash der Code das belegt und welches Artefakt
    (ADR, Aenderungsvermerk) die Aenderung begruendet. Geprueft wird:
    Schema; beide Versionen semver und verschieden; die neue Version ist
    die, die der Code jetzt traegt (TBOX_VERSION); der Modul-Hash ist der
    des geladenen T-Box-Moduls; das Artefakt liegt im Fall oder im Repo
    und traegt seinen Hash. Rueckgabe: Fehlerliste (leer = in Ordnung).

    Der ALTE Stand ist im Code nachweisbar (Review T23-03): Die T-Box
    deklariert ihre Versionslinie (``TBOX_VERSIONEN``); ``von_version``
    muss der unmittelbare Vorgaenger von ``nach_version`` in dieser Linie
    sein, und die Ordnung laeuft aufwaerts — ein erfundener oder
    rueckwaerts laufender Uebergang wird nicht signiert. Der Artefakt-Pfad
    ist relativ und kanonisch und liegt im Fall oder im Repo (``repo_root``),
    nirgends sonst (Review T23-09).
    """
    from rechner_pipeline.ontologie import tbox as tbox_modul

    if not pfad.is_file():
        return ["Datei fehlt"]
    try:
        # text: die Bytes, die der Aufrufer bereits fuer den Pflichtbeleg
        # gehasht hat (Review T23-01) — nicht ein zweites Mal lesen.
        daten = json.loads(
            text if text is not None else pfad.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"nicht lesbar: {exc}"]
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if daten.get("schema_version") != TBOX_AENDERUNG_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {TBOX_AENDERUNG_SCHEMA_VERSION} sein")
    von, nach = daten.get("von_version"), daten.get("nach_version")
    semver_ok = True
    for name, wert in (("von_version", von), ("nach_version", nach)):
        if not isinstance(wert, str) or not _SEMVER.match(wert):
            fehler.append(f"{name} muss eine Version x.y.z sein")
            semver_ok = False
    if von == nach:
        fehler.append("von_version und nach_version sind gleich — keine Aenderung")
    if semver_ok and von != nach:
        if _semver_tuple(von) >= _semver_tuple(nach):
            fehler.append(
                f"von_version {von!r} liegt nicht vor nach_version {nach!r} "
                "— ein Uebergang laeuft aufwaerts"
            )
        linie = tuple(tbox_modul.TBOX_VERSIONEN)
        if nach not in linie:
            fehler.append(
                f"nach_version {nach!r} steht nicht in der Versionslinie der "
                f"T-Box {linie!r}"
            )
        elif linie.index(nach) == 0:
            fehler.append(
                f"nach_version {nach!r} ist die erste Version der T-Box-Linie "
                f"{linie!r} — ohne Vorgaenger gibt es keinen Uebergang zu zeichnen"
            )
        elif linie[linie.index(nach) - 1] != von:
            fehler.append(
                f"von_version {von!r} ist nicht der Vorgaenger von {nach!r} in "
                f"der Versionslinie {linie!r} — der alte Stand muss der im Code "
                "nachweisbare sein"
            )
    if nach != tbox_modul.TBOX_VERSION:
        fehler.append(
            f"nach_version {nach!r} ist nicht die Version, die der Code traegt "
            f"({tbox_modul.TBOX_VERSION!r}) — Beleg und Code muessen dieselbe "
            "Aenderung meinen"
        )
    modul_hash = hashlib.sha256(Path(tbox_modul.__file__).read_bytes()).hexdigest()
    if daten.get("tbox_sha256") != modul_hash:
        fehler.append("tbox_sha256 ist nicht der Hash des geladenen T-Box-Moduls")
    artefakt = daten.get("artefakt")
    if not (isinstance(artefakt, dict) and isinstance(artefakt.get("pfad"), str)
            and isinstance(artefakt.get("sha256"), str)):
        fehler.append("artefakt {pfad, sha256} fehlt")
    else:
        # Relativ, kanonisch, innerhalb von Fall oder Repo — nirgends sonst
        # (Review T23-09): ein absoluter oder hinausfuehrender Pfad liesse ein
        # Artefakt ausserhalb jeder Nachvollziehbarkeit als Rechtfertigung zu.
        pfad_roh = artefakt["pfad"]
        wurzeln = [fall] + ([repo_root] if repo_root is not None else [])
        datei: Path | None = None
        if Path(pfad_roh).is_absolute() or ".." in Path(pfad_roh).parts:
            fehler.append(
                f"artefakt {pfad_roh!r} ist kein relativer, kanonischer Pfad — "
                "erlaubt sind Pfade innerhalb des Falls oder des Repos"
            )
        else:
            for wurzel in wurzeln:
                kandidat = (wurzel / pfad_roh).resolve()
                try:
                    kandidat.relative_to(wurzel.resolve())
                except ValueError:
                    continue
                if kandidat.is_file():
                    datei = kandidat
                    break
            if datei is None:
                fehler.append(
                    f"artefakt {pfad_roh!r} nicht gefunden (innerhalb des Falls "
                    "oder des Repos)"
                )
            elif hashlib.sha256(datei.read_bytes()).hexdigest() != artefakt["sha256"]:
                fehler.append(f"artefakt {pfad_roh!r}: Hash stimmt nicht")
    if not (isinstance(daten.get("begruendung"), str) and daten["begruendung"].strip()):
        fehler.append("begruendung fehlt")
    return fehler


#: Schema der aktuariellen Stellungnahme zu einer T-Box-Aenderung
#: (Entscheid des Maintainers 2026-09-16).
STELLUNGNAHME_SCHEMA_VERSION = 1

#: Wie ein Feld wirken kann. "ohne-wirkung" ist ausdruecklich erlaubt —
#: das ist die Aussage "wir haben hingesehen und nichts gefunden", und
#: die ist etwas anderes als Schweigen.
WIRKUNGSARTEN = ("tariflich", "bewertungsrelevant", "ohne-wirkung")


def pruefe_stellungnahme_aktuariat(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    aenderung: Dict[str, object] | None = None,
) -> List[str]:
    """Die fachliche Stellungnahme zu einer T-Box-Aenderung pruefen.

    A-O1 zeichnet `mensch/architektur`: Wer verantwortet, welche Begriffe
    das Zielsystem fuehrt, verantwortet sein Datenmodell. Die Frage
    DAHINTER ist aber keine technische — ob ein Feld tarif- oder
    bewertungswirksam ist, und was verlorengeht, wenn es entfaellt,
    beantwortet das Aktuariat. Der Beleg haelt diese Antwort fest, je
    Feld und mit Begruendung.

    Geprueft wird, dass die Stellungnahme zu DIESEM Uebergang gehoert und
    dass sie zu jedem genannten Feld wirklich etwas sagt. Ein leeres
    ``felder`` waere eine Unterschrift unter nichts.
    """
    if not pfad.is_file():
        return ["Datei fehlt"]
    try:
        daten = json.loads(
            text if text is not None else pfad.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"nicht lesbar: {exc}"]
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if daten.get("schema_version") != STELLUNGNAHME_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {STELLUNGNAHME_SCHEMA_VERSION} sein")
    if aenderung is not None and daten.get("nach_version") != aenderung.get(
        "nach_version"
    ):
        fehler.append(
            f"nach_version {daten.get('nach_version')!r} weicht vom "
            f"Aenderungsbeleg ({aenderung.get('nach_version')!r}) ab — die "
            "Stellungnahme gehoert zu einer anderen T-Box-Aenderung"
        )
    if daten.get("verfasser_rolle") != "mensch/aktuariat":
        fehler.append(
            "verfasser_rolle muss 'mensch/aktuariat' sein — die fachliche "
            "Bewertung eines Feldes ist keine Aussage der IT"
        )
    felder = daten.get("felder")
    if not isinstance(felder, list) or not felder:
        fehler.append(
            "felder fehlt oder ist leer — eine Stellungnahme ohne Feld ist "
            "eine Unterschrift unter nichts"
        )
    else:
        for i, eintrag in enumerate(felder):
            if not isinstance(eintrag, dict):
                fehler.append(f"felder[{i}] ist kein Objekt")
                continue
            if not (isinstance(eintrag.get("name"), str) and eintrag["name"].strip()):
                fehler.append(f"felder[{i}]: name fehlt")
            if eintrag.get("wirkung") not in WIRKUNGSARTEN:
                fehler.append(
                    f"felder[{i}]: wirkung muss eine von {list(WIRKUNGSARTEN)} sein"
                )
            if not (
                isinstance(eintrag.get("begruendung"), str)
                and eintrag["begruendung"].strip()
            ):
                fehler.append(f"felder[{i}]: begruendung fehlt")
    return fehler


#: Schema der beiden Belege von ``A-K2.kernaenderung`` (Entscheid des
#: Maintainers 2026-09-16). Getrennt gehalten, weil sie verschiedene Dinge
#: bezeugen: Der AENDERUNGSbeleg sagt, WAS am Kern anders wurde; der
#: REGRESSIONSbeleg sagt, was das fuer den bestehenden Bestand bedeutet.
KERN_AENDERUNG_SCHEMA_VERSION = 2
KERN_REGRESSION_SCHEMA_VERSION = 1

#: Die eingefrorenen Referenzwerte des Kerns — die Regressionssicherung
#: aus dem Abnahme-Protokoll (``kern/__init__``). Ihr Sammelhash bindet
#: den Aenderungsbeleg an den Stand, den der Code wirklich traegt.
KERN_REFERENZWERTE = ("tests", "fixtures", "kern_referenzwerte")

#: Das Rechenkern-Paket. Der Beleg bindet es ueber einen Sammelhash,
#: NICHT ueber einen Import: Das Entscheid-Kommando gehoert dem KI-Tool
#: (Ebene 2), der Rechenkern der Vorzeige (Ebene 3), und das Tool greift
#: nicht in die Vorzeige (ADR-017, TOOL_NACH_VORZEIGE_ERLAUBT). Ein Hash
#: ueber die Quelldateien leistet ohnehin mehr als eine Versionsnummer:
#: Eine Version kann man hochzaehlen, ohne etwas zu aendern, und etwas
#: aendern, ohne sie hochzuzaehlen. Dieselbe Figur wie der Modul-Hash der
#: T-Box in ``pruefe_tbox_aenderung``.
KERN_PAKET = ("src", "rechner_pipeline", "kern")


def referenzwerte_hash(repo_root: Path) -> str | None:
    """Sammelhash der eingefrorenen Kern-Referenzwerte, sortiert.

    Sortiert nach Dateiname, damit der Hash nicht von der Reihenfolge des
    Dateisystems abhaengt; Name UND Inhalt gehen ein, sonst bliebe das
    Umbenennen oder Loeschen einer Datei unsichtbar.
    """
    verzeichnis = repo_root.joinpath(*KERN_REFERENZWERTE)
    if not verzeichnis.is_dir():
        return None
    sammel = hashlib.sha256()
    for datei in sorted(verzeichnis.glob("*.json"), key=lambda d: d.name):
        sammel.update(datei.name.encode("utf-8"))
        sammel.update(datei.read_bytes())
    return sammel.hexdigest()


def kern_modul_hash(repo_root: Path) -> str | None:
    """Sammelhash der Quelldateien des Rechenkerns, sortiert nach Name."""
    verzeichnis = repo_root.joinpath(*KERN_PAKET)
    if not verzeichnis.is_dir():
        return None
    sammel = hashlib.sha256()
    for datei in sorted(verzeichnis.rglob("*.py"), key=lambda d: d.as_posix()):
        sammel.update(datei.relative_to(verzeichnis).as_posix().encode("utf-8"))
        sammel.update(datei.read_bytes())
    return sammel.hexdigest()


def pruefe_kernaenderung(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    repo_root: Path | None = None,
) -> List[str]:
    """Den Beleg einer Rechenkern-Aenderung gegen den Code halten.

    Gleiche Figur wie ``pruefe_tbox_aenderung``: Der Beleg sagt, VON
    welcher Kern-Version NACH welcher es geht, welchen Sammelhash die
    eingefrorenen Referenzwerte danach tragen, welche davon sich geaendert
    haben und welches Artefakt die Aenderung begruendet.

    Der ALTE Stand ist hier nicht aus dem Code nachweisbar — der Kern
    deklariert keine Versionslinie wie die T-Box. Was nachweisbar ist und
    deshalb geprueft wird: Die NEUE Version muss die sein, die der Code
    jetzt traegt (``kern.__version__``), und der Sammelhash muss der der
    tatsaechlich vorliegenden Referenzwerte sein. Ein Beleg, der eine
    Aenderung behauptet, die der Code nicht traegt, wird nicht gezeichnet.
    """
    if not pfad.is_file():
        return ["Datei fehlt"]
    try:
        daten = json.loads(
            text if text is not None else pfad.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"nicht lesbar: {exc}"]
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if daten.get("schema_version") != KERN_AENDERUNG_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {KERN_AENDERUNG_SCHEMA_VERSION} sein")
    von, nach = daten.get("von_version"), daten.get("nach_version")
    semver_ok = True
    for name, wert in (("von_version", von), ("nach_version", nach)):
        if not isinstance(wert, str) or not _SEMVER.match(wert):
            fehler.append(f"{name} muss eine Version x.y.z sein")
            semver_ok = False
    if von == nach:
        fehler.append("von_version und nach_version sind gleich — keine Aenderung")
    if semver_ok and von != nach:
        if _semver_tuple(von) >= _semver_tuple(nach):
            fehler.append(
                f"von_version {von!r} liegt nicht vor nach_version {nach!r} "
                "— ein Uebergang laeuft aufwaerts"
            )
    wurzel = repo_root if repo_root is not None else None
    kern_ist = kern_modul_hash(wurzel) if wurzel is not None else None
    kern_soll = daten.get("kern_sha256")
    if not (isinstance(kern_soll, str) and _SHA256.match(kern_soll)):
        fehler.append("kern_sha256 fehlt oder ist kein SHA-256")
    elif kern_ist is None:
        fehler.append(
            "kern_sha256 ist nicht pruefbar — das Rechenkern-Paket "
            f"({'/'.join(KERN_PAKET)}) ist nicht erreichbar (--repo-root fehlt?)"
        )
    elif kern_soll != kern_ist:
        fehler.append(
            "kern_sha256 stimmt nicht mit dem vorliegenden Rechenkern "
            "ueberein — der Beleg behauptet eine Aenderung, die der Code "
            "nicht traegt"
        )
    ist_hash = referenzwerte_hash(wurzel) if wurzel is not None else None
    soll_hash = daten.get("referenzwerte_sha256")
    if not (isinstance(soll_hash, str) and _SHA256.match(soll_hash)):
        fehler.append("referenzwerte_sha256 fehlt oder ist kein SHA-256")
    elif ist_hash is None:
        fehler.append(
            "referenzwerte_sha256 ist nicht pruefbar — die eingefrorenen "
            f"Referenzwerte ({'/'.join(KERN_REFERENZWERTE)}) sind nicht "
            "erreichbar (--repo-root fehlt?)"
        )
    elif soll_hash != ist_hash:
        fehler.append(
            "referenzwerte_sha256 stimmt nicht mit den vorliegenden "
            "Referenzwerten ueberein — der Beleg gehoert zu einem anderen "
            "Stand des Kerns"
        )
    # Der ALTE Stand (Entscheid des Maintainers 2026-09-16): Entwicklung
    # im Fall laeuft auf einem Branch, der produktive Kern liegt auf
    # ``main``. Damit ist die Vorher-Seite nicht mehr behauptet, sondern
    # benennbar — und der Vergleich ist reproduzierbar, weil der Hash
    # inhaltsadressiert ist und der Commit dazu im Beleg steht.
    kern_alt = daten.get("kern_alt_sha256")
    if not (isinstance(kern_alt, str) and _SHA256.match(kern_alt)):
        fehler.append("kern_alt_sha256 fehlt oder ist kein SHA-256")
    elif isinstance(kern_soll, str) and kern_alt == kern_soll:
        fehler.append(
            "kern_alt_sha256 ist kern_sha256 — der Kern hat sich nicht "
            "geaendert, es gibt nichts abzunehmen"
        )
    git_beleg = daten.get("git")
    if not isinstance(git_beleg, dict):
        fehler.append("git fehlt oder ist kein Objekt")
    else:
        if git_beleg.get("dirty") != "nein":
            fehler.append(
                "git.dirty ist nicht 'nein' — eine Regression gegen "
                "uncommittete Aenderungen ist nicht reproduzierbar"
            )
        if not zweig_ist_aktuell(git_beleg):
            fehler.append(
                f"der Zweig liegt nicht auf der Spitze von "
                f"{git_beleg.get('referenz', PRODUKTIVER_ZWEIG)!r} "
                "(merge_base != referenz_commit) — die Differenz mischte "
                "die eigene Aenderung mit einer fremden"
            )
        if wurzel is not None:
            # Gegen den LEBENDEN Git-Stand halten, nicht nur gegen sich
            # selbst: Ein Beleg, der nur innerlich stimmig ist, bezeugt
            # nichts (T24-04). Geprueft wird, was die DREI vorhandenen
            # lesenden git-Aufrufe hergeben — Commit und dirty. Der
            # Merge-Base bliebe ein vierter Aufruf und damit eine zweite
            # Subprozess-Ausnahme; die gibt es hier nicht.
            jetzt = git_stand(wurzel)
            if jetzt.get("commit") == "unbekannt":
                fehler.append(
                    "der gegenwaertige Git-Stand ist nicht lesbar — der "
                    "Beleg ist nicht gegen den Arbeitsbaum haltbar"
                )
            elif git_beleg.get("aktuell") != jetzt.get("commit"):
                fehler.append(
                    f"git.aktuell {str(git_beleg.get('aktuell'))[:12]!r} ist "
                    f"nicht der gegenwaertige Commit "
                    f"({str(jetzt.get('commit'))[:12]!r}) — der Beleg "
                    "gehoert zu einem anderen Lauf"
                )
            # dirty wird NICHT gegen den lebenden Stand gehalten: Ob die
            # Regression reproduzierbar ist, entscheidet der Baum zur
            # MESSZEIT, nicht zur Unterschrift — die kann Tage spaeter
            # fallen. Der festgehaltene Wert ist der richtige; und ein
            # zwischenzeitlich veraenderter Kern faellt ohnehin ueber
            # kern_sha256 auf.
    geaendert = daten.get("geaenderte_referenzwerte")
    if not isinstance(geaendert, list) or not all(
        isinstance(x, str) for x in geaendert
    ):
        # Leer ist erlaubt: Nicht jede Kern-Aenderung verschiebt einen
        # Referenzwert. Fehlen darf die Liste aber nicht — sonst bliebe
        # offen, ob niemand hingesehen oder niemand etwas gefunden hat.
        fehler.append("geaenderte_referenzwerte fehlt oder ist keine Liste von Namen")
    if not (isinstance(daten.get("begruendung"), str) and daten["begruendung"].strip()):
        fehler.append("begruendung fehlt")
    return fehler


def pruefe_kernregression(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    aenderung: Dict[str, object] | None = None,
) -> List[str]:
    """Den Regressionsbeleg einer Kern-Aenderung pruefen.

    Entscheid des Maintainers 2026-09-16: **Ohne Regression keine Abnahme.**
    Eine Kern-Aenderung entsteht im Fall, aber der geaenderte Kern bewertet
    danach den LAUFENDEN Bestand weiter — diese Wirkung sieht sonst
    niemand. Der Beleg rechnet deshalb jeden Vertrag mit altem und neuem
    Kern durch und weist die Differenz JE VERTRAG aus.

    Geprueft wird vor allem die Vollstaendigkeit: ``vertraege_geprueft``
    muss ``vertraege_gesamt`` sein. Eine Stichprobe ist hier wertlos —
    ein Fehler, der einen von tausend Vertraegen trifft, ist genau der,
    den man sucht. Aggregate sind aus demselben Grund nicht zugelassen:
    Gegenlaeufige Abweichungen heben sich in der Summe auf.
    """
    if not pfad.is_file():
        return ["Datei fehlt"]
    try:
        daten = json.loads(
            text if text is not None else pfad.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        return [f"nicht lesbar: {exc}"]
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if daten.get("schema_version") != KERN_REGRESSION_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {KERN_REGRESSION_SCHEMA_VERSION} sein")
    if aenderung is not None:
        for feld in ("von_version", "nach_version", "kern_alt_sha256",
                     "kern_sha256"):
            if daten.get(feld) != aenderung.get(feld):
                fehler.append(
                    f"{feld} {daten.get(feld)!r} weicht vom Aenderungsbeleg "
                    f"({aenderung.get(feld)!r}) ab — die Regression gehoert "
                    "zu einem anderen Uebergang"
                )
    gesamt, geprueft = daten.get("vertraege_gesamt"), daten.get("vertraege_geprueft")
    for name, wert in (("vertraege_gesamt", gesamt), ("vertraege_geprueft", geprueft)):
        if not isinstance(wert, int) or isinstance(wert, bool) or wert < 0:
            fehler.append(f"{name} muss eine nicht-negative ganze Zahl sein")
    if isinstance(gesamt, int) and not isinstance(gesamt, bool) and gesamt <= 0:
        fehler.append(
            "vertraege_gesamt ist 0 — eine Regression ohne Bestand bezeugt nichts"
        )
    if (
        isinstance(gesamt, int)
        and isinstance(geprueft, int)
        and not isinstance(gesamt, bool)
        and not isinstance(geprueft, bool)
        and geprueft != gesamt
    ):
        fehler.append(
            f"vertraege_geprueft ({geprueft}) ist nicht vertraege_gesamt "
            f"({gesamt}) — eine Stichprobe ist keine Regression"
        )
    if not (
        isinstance(daten.get("bestand_sha256"), str)
        and _SHA256.match(daten["bestand_sha256"])
    ):
        fehler.append(
            "bestand_sha256 fehlt oder ist kein SHA-256 — ohne ihn ist nicht "
            "bestimmt, WELCHER Bestand durchgerechnet wurde"
        )
    abweichungen = daten.get("abweichungen")
    if not isinstance(abweichungen, list):
        fehler.append("abweichungen fehlt oder ist keine Liste")
    else:
        for i, eintrag in enumerate(abweichungen):
            if not isinstance(eintrag, dict):
                fehler.append(f"abweichungen[{i}] ist kein Objekt")
                continue
            fehlend = [
                f for f in ("police_id", "groesse", "vorher", "nachher", "differenz")
                if f not in eintrag
            ]
            if fehlend:
                fehler.append(f"abweichungen[{i}]: {', '.join(fehlend)} fehlt")
                continue
            vorher, nachher, diff = (
                eintrag["vorher"], eintrag["nachher"], eintrag["differenz"],
            )
            if not all(
                isinstance(w, (int, float)) and not isinstance(w, bool)
                for w in (vorher, nachher, diff)
            ):
                fehler.append(f"abweichungen[{i}]: vorher/nachher/differenz sind Zahlen")
            elif abs((nachher - vorher) - diff) > 1e-9:
                fehler.append(
                    f"abweichungen[{i}]: differenz {diff!r} ist nicht "
                    f"nachher - vorher ({nachher - vorher!r})"
                )
    return fehler


def _pruefe_g2_snapshot_semantik(
    snapshot: dict, aktueller_systemstand: Mapping[str, str]
) -> List[str]:
    """Den aus dem Scope abgeleiteten Inhalt einer Annahme pruefen.

    Das paketweite P9-Schema prueft die JSON-Form. Die fachliche Rollenmenge
    wird deshalb hier auch beim LESEN eines bestehenden Snapshots erneut aus
    dem Belegrollen-Vertrag (je Gate und Scope, ADR-009/ADR-010) abgeleitet.
    Sonst koennte ein formal gueltiger, signierter Snapshot eine Pflichtrolle
    auslassen und dennoch als gueltige P9-Historie erscheinen.

    Die Pflichtbelegmenge eines Gates WAECHST aber mit dem System: die
    Fuehrungsprobe etwa kam als A-M4-Bestandsrolle erst mit der
    Freischaltung hinzu. Ein Vorgaenger auf einem FRUEHEREN Stand wurde
    gegen den Belegrollen-Vertrag SEINES Standes gezeichnet und ist durch
    seine Signatur verankert; ihn gegen den heutigen, breiteren Vertrag zu
    messen erklaerte ihn rueckwirkend fuer unvollstaendig und verhinderte,
    dass eine neue Zeichnung ueberhaupt an ihn anknuepfen kann. Der aktuelle
    Vertrag wird deshalb NUR auf Snapshots des aktuellen Standes angewandt;
    fuer aeltere Vorgaenger buergt ihre Signatur (Neuzeichnung Fall-Lauf 2,
    2026-09-07). Ein Schlupfloch entsteht nicht: ein neuer Snapshot wird
    immer auf dem aktuellen Stand gebaut und traegt den vollen Vertrag von
    Bau an, wird hier also geprueft.
    """
    gate = snapshot.get("gate")
    if gate not in GATES_MIT_PFLICHTBELEGEN or snapshot.get("entscheid") != "angenommen":
        return []
    if snapshot.get("system") != dict(aktueller_systemstand):
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
    pk1_belege = snapshot.get("pk1_belege")
    if isinstance(pflichtbelege, dict) and isinstance(pk1_belege, dict):
        pk1_hashes = sorted(
            beleg
            for belege_der_generation in pk1_belege.values()
            if isinstance(belege_der_generation, list)
            for beleg in belege_der_generation
        )
        if pflichtbelege.get("pk1_belege") != pk1_hashes:
            fehler.append(
                "pflichtbelege['pk1_belege'] stimmt nicht mit der "
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
    aktueller_systemstand: Mapping[str, str],
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
            for meldung in _pruefe_g2_snapshot_semantik(
                daten, aktueller_systemstand
            )
        )
        sha = daten["snapshot_sha256"]
        if daten["gate"] != gate:
            fehler.append(
                f"{pfad.name}: gate {daten['gate']!r} statt erwartet {gate!r}"
            )
        if daten["fall"] != fall.name:
            fehler.append(
                f"{pfad.name}: Fallbindung {daten['fall']!r} statt "
                f"{fall.name!r}"
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
    text: str | None = None,
) -> List[str]:
    """Validate P-Q3's full ledger schema plus its gate-specific binding.

    ``text``: die Bytes, die der Aufrufer bereits fuer den Pflichtbeleg
    gehasht hat (Review T23-01) — der Ledger wird nicht ein zweites Mal
    gelesen.
    """
    from rechner_pipeline.gates import abox_validate

    try:
        payload = json.loads(
            text if text is not None else pfad.read_text(encoding="utf-8")
        )
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
    """Die im P-K1-Beleg gebundenen Dateien gegen den Jetztstand pruefen.

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
    bekannt: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[Dict[str, str]], List[str]]:
    """P-B1, Suite und Abnahmebericht auf dem aktuellen Stand neu validieren.

    ``bekannt``: nimmt den Hash des hier gelesenen Abnahmebericht-Ledgers
    auf, damit die Snapshot-Artefakthashes ihn uebernehmen statt die Datei
    neu zu lesen (Review T23-01).
    """
    from rechner_pipeline.gates import abnahmebericht

    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    if not ledger_pfad.is_file():
        return None, [
            "gruener Abnahmebericht-Beleg fehlt: abnahmebericht.gate.json"
        ]
    try:
        # Einmal lesen: der Pflichtbeleg-Hash ist der Hash dieser Bytes
        # (Review T23-01), nicht einer zweiten Lesung.
        ledger_gelesen = lies_gehasht(ledger_pfad)
        ledger = GateLedgerEntry.from_dict(ledger_gelesen.json())
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
    # Jeden Pflichtbeleg GENAU EINMAL lesen: der protokollierte Hash und die
    # inhaltliche Neupruefung unten stammen aus denselben Bytes (T23-01).
    gelesen: Dict[str, GeleseneDatei] = {}
    for rolle in rollen:
        g, artefakt_fehler = lies_artefakt_eintrag(fall, rolle, belege[rolle])
        fehler.extend(artefakt_fehler)
        if g is not None:
            pfade[rolle] = g.pfad
            gelesen[rolle] = g
            hashes[rolle] = g.sha256

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
    renderer_gelesen: Dict[str, GeleseneDatei] = {}
    for rolle in renderer_rollen:
        g, artefakt_fehler = lies_artefakt_eintrag(
            fall, rolle, renderer_belege[rolle]
        )
        fehler.extend(artefakt_fehler)
        if g is not None:
            renderer_pfade[rolle] = g.pfad
            renderer_gelesen[rolle] = g

    input_eintraege = {
        rolle: eintrag
        for rolle, eintrag in {
            "pb1_ledger": belege["pb1_ledger"],
            "migrationssuite": belege["migrationssuite"],
            "fuehrungsprobe": belege["fuehrungsprobe"],
            **renderer_belege,
        }.items()
        if isinstance(eintrag, dict)
        and set(eintrag) == {"pfad", "sha256"}
        and isinstance(eintrag.get("pfad"), str)
        and isinstance(eintrag.get("sha256"), str)
    }
    if len(input_eintraege) == 7:
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
                "Abnahmebericht-Ledger.input_hashes muss exakt P-B1, Suite, "
                "Fuehrungsprobe und alle vier Renderer-Artefaktrollen binden"
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
            for rolle in ("pb1_ledger", "migrationssuite")
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
            suite_roh = gelesen["migrationssuite"].json()
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
            spec_roh = renderer_gelesen["spec"].json()
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
            transformation = renderer_gelesen["transformation_ergebnis"].json()
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
                        spec_hash=renderer_gelesen["spec"].sha256,
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
                            bericht_text=gelesen["abnahmebericht"].text(),
                            erwartete_stichtage=stichtage,
                            fall=fall,
                        )
                    )
        if "pb1_ledger" in pfade:
            fehler.extend(
                abnahmebericht._b1_fehler(
                    ledger_pfad=pfade["pb1_ledger"],
                    ledger_text=gelesen["pb1_ledger"].text(),
                    fall=fall,
                    repo_root=repo_root,
                    suite=suite,
                    erwartetes_system=dict(system),
                )
            )
        if "fuehrungsprobe" in pfade:
            # Dieselbe Bindung wie im Abnahmebericht, auf DENSELBEN Bytes,
            # die oben gehasht wurden (Freischaltung Schritt 6; Belegidentitaet
            # Review T23-01) — nicht ein zweites Mal von der Platte.
            fehler.extend(
                abnahmebericht._fuehrungsprobe_fehler(
                    abnahmebericht._json_beleg_aus(gelesen["fuehrungsprobe"]),
                    fall=fall,
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
    hashes["abnahmebericht"] = ledger_gelesen.sha256
    if bekannt is not None:
        bekannt[str(ledger_pfad.relative_to(fall))] = ledger_gelesen.sha256
    return hashes, []


def entscheide_verzeichnis(fall: Path) -> Path:
    """Snapshots liegen NEBEN dem Eingang: nicht regenerierbar,
    ausserhalb der aufraeumbaren abgeleitet/-Zone."""
    return fall / "entscheide"


def _artefakt_hashes(
    fall: Path, ausser_gate: str = "", *, bekannt: Mapping[str, str] | None = None,
) -> Dict[str, str]:
    """Alle entscheidungsrelevanten Artefakte des Falls, gehasht —
    inklusive der registrierten Eingangsdateien selbst und der
    Entscheid-Snapshots ANDERER Gates (Kreuz-Verkettung). Die eigenen
    Gate-Snapshots laufen ueber ``vorgaenger``, nicht ueber die
    Artefaktliste — sonst waere kein Wiederholungs-Aufruf je idempotent.

    ``bekannt``: Hashes der Dateien, die dieser Lauf bereits gelesen und
    verarbeitet hat (A-Box, Eingang, Fall-Manifest, Pflicht-Ledger). Sie
    werden uebernommen, nicht neu gelesen — der Snapshot bezeugt dieselben
    Bytes, die geprueft wurden (Review T23-01). Alle uebrigen Artefakte
    sind Inventar des Fallstands und werden hier gehasht, ohne dass der
    Lauf sie verarbeitet; fuer sie gibt es keinen zweiten Lesepfad.
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
    vorhanden = dict(bekannt or {})
    hashes: Dict[str, str] = {}
    for p in kandidaten:
        if not p.is_file():
            continue
        rel = str(p.relative_to(fall))
        hashes[rel] = vorhanden.get(rel) or _sha256_datei(p)
    return hashes


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
    parser.add_argument(
        "--anker", default=None,
        help="Ankerdatei des auszuliefernden Pakets (A-B1).")
    parser.add_argument(
        "--ankersatz", default=None,
        help="SHA-256 des Ankersatzes, den diese Auslieferung zeichnet "
             "(A-B1); stand.json des Pakets nennt ihn.")
    parser.add_argument("--begruendung", default=None)
    parser.add_argument(
        "--rolle", default=None,
        help="Rollenkennung mit Ebene (ADR-018): mensch/<funktion> oder "
        "agent/<name>. Fuer eine ANNAHME wird die Rolle aus dem "
        "Freigabeschluessel ueber die Zeichnungsordnung BESTIMMT; ein "
        "gesetzter Wert muss dann uebereinstimmen. Fuer eine ABLEHNUNG "
        "ohne Schluessel ist die Kennung Pflicht (dokumentierter "
        "Zwischenstand). Agentenrollen koennen nur ablehnen.",
    )
    parser.add_argument(
        "--mandat", default=None,
        help="Datei des Mandats, unter dem eine SIMULIERTE Rolle handelt; "
        "ihr SHA-256 wandert in die Zeichnung des Snapshots (ADR-018). "
        "PFLICHT bei Schluesselklasse simulation, ohne Wirkung bei mensch.",
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
    parser.add_argument(
        "--zeichnungsordnung",
        default=None,
        help=(
            "JSON ausserhalb des Falls: welche ROLLE (Schluessel-"
            "Fingerabdruck) welches GATE zeichnen darf. Mit Ordnung wird "
            "jede Annahme UND jede Vorbedingungs-Annahme dagegen "
            "geprueft; ohne bleibt das bisherige Verhalten."
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
    ledger_gate_id = f"entscheid.{ledger_gate or '?'}"
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
    if args.rolle is not None and not gueltige_rollenkennung(args.rolle):
        return _usage(
            f"--rolle {args.rolle!r} ist keine Rollenkennung mit Ebene — "
            "erwartet mensch/<funktion> oder agent/<name> (ADR-018); "
            "die Werte 'mensch' und 'agent' ohne Ebene gelten nicht mehr"
        )
    if args.entscheid == "abgelehnt" and args.rolle is None:
        return _usage(
            "--rolle <kennung> ist fuer eine Ablehnung erforderlich "
            "(Agentenrollen dokumentieren Zwischenstaende so)"
        )
    if args.rolle is not None and args.rolle.startswith("agent/") \
            and args.entscheid == "angenommen":
        return _usage(
            f"Rolle {args.rolle!r} darf nicht annehmen — die Annahme eines "
            "menschlichen Gates ist Menschen vorbehalten (P2/P4, ADR-018); "
            "Agenten legen vor und dokumentieren Zwischenstaende als Ablehnung"
        )
    mandat_sha256: Optional[str] = None
    if args.mandat:
        mandat_pfad = Path(args.mandat)
        if not mandat_pfad.is_file():
            return _usage(f"--mandat {args.mandat!r} ist keine Datei")
        if not ausserhalb_des_falls(mandat_pfad, fall):
            # Wie Ordnung und Schluessel (ADR-018): Was der Fall selbst
            # umschreiben kann, autorisiert nichts (Review T23-09).
            return _usage(
                f"--mandat {args.mandat!r} liegt innerhalb des Falls; das "
                "Mandat muss wie die Zeichnungsordnung extern verwahrt werden"
            )
        mandat_sha256 = hashlib.sha256(mandat_pfad.read_bytes()).hexdigest()
    if not (fall / "eingang.json").is_file():
        return _usage(
            f"kein Fall-Arbeitsbereich: {fall} (anlegen mit: python -m "
            f"rechner_pipeline.fall anlegen --fall {fall}, dann je Quelle "
            f"python -m rechner_pipeline.fall registrieren --fall {fall} "
            "--datei <quelle>)"
        )

    def _sperre(code: str, message: str):
        return _finalize(build_result(
            command=ledger_command, gate=f"entscheid.{args.gate}",
            gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT,
            errors=[{"code": code, "message": message}],
            paths={"fall": str(fall)},
        ))

    entscheid_systemstand = systemstand(Path(args.repo_root).resolve())
    pk1_belege: Dict[str, List[str]] = {}
    pflichtbelege: Dict[str, List[str]] = {}
    # Hashes der in DIESEM Lauf gelesenen Dateien: die Snapshot-Artefakthashes
    # uebernehmen sie, statt validierte Dateien fuer den Snapshot neu zu lesen
    # (Review T23-01).
    bekannte_hashes: Dict[str, str] = {}
    fall_scope: Optional[str] = None
    if args.gate in GATES_MIT_PFLICHTBELEGEN:
        try:
            fall_scope, fall_json_sha256 = fall_mod.lade_scope_gehasht(fall)
            bekannte_hashes["fall.json"] = fall_json_sha256
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

    zeichnungsordnung, zeichnungsordnung_sha, zo_fehler = (
        _lade_zeichnungsordnung(args.zeichnungsordnung, fall)
    )
    if zo_fehler:
        return _usage("; ".join(zo_fehler))

    # Annahme-Sperre: eine Annahme setzt einen integeren Fall und
    # endgueltige Entscheidungen voraus — sonst wuerde ein ungeloester
    # Quellen-Widerspruch oder der Arbeitsstand eines Agenten still zur
    # abgenommenen Wahrheit (P2/P4). Die A-Box ist dafuer PFLICHT: eine
    # Sperre, die per Dateiloeschung abschaltbar waere, ist keine.
    if args.entscheid == "angenommen":
        import json as _json

        from rechner_pipeline.ontologie.abox import (
            abox_pfad,
            lade_aus_bytes,
            validate_abox,
        )

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
            # Ueber den fail-closed Lader (Review T23-02), nicht am Lader vorbei.
            abox = lade_aus_bytes(abox_roh)
        except Exception as exc:  # Ladefehler ist Befund MIT Ledger
            return _sperre("abox", f"A-Box unlesbar: {exc}")
        # eingang.json einmal lesen: Validierung, P-Q3-Abgleich und die
        # Snapshot-Artefakthashes tragen den Hash derselben Bytes (T23-01).
        eingang_gelesen = lies_gehasht(fall / "eingang.json")
        register = eingang_gelesen.json()
        bekannte_hashes["eingang.json"] = eingang_gelesen.sha256
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
        # Derselbe Byte-String wird validiert und gehasht: A-M4 darf nicht
        # versehentlich eine zwischen zwei Lesevorgaengen geaenderte A-Box
        # als den geprueften Stand protokollieren.
        abox_hash = hashlib.sha256(abox_roh).hexdigest()
        bekannte_hashes["abgeleitet/abox/abox.json"] = abox_hash
        diagnostics = fall / "abgeleitet" / "diagnostics"

        pq3_pfad = diagnostics / "abox_validate.gate.json"
        pq3_kommando = (
            "python -m rechner_pipeline.gates.abox_validate "
            f"--fall {fall} --repo-root {args.repo_root}"
        )
        if not pq3_pfad.is_file():
            return _sperre(
                "vorbedingung",
                "Annahme verweigert: Gate P-Q3 (abox_validate) ist nie "
                f"gelaufen ({pq3_pfad.name} fehlt) — nachholen mit: {pq3_kommando}",
            )
        pq3_gelesen = lies_gehasht(pq3_pfad)
        bekannte_hashes[str(pq3_pfad.relative_to(fall))] = pq3_gelesen.sha256
        pq3_fehler = _pruefe_o1_ledger(
            pq3_pfad,
            text=pq3_gelesen.text(),
            abox_hash=abox_hash,
            eingang_hash=eingang_gelesen.sha256,
        )
        if pq3_fehler:
            return _sperre(
                "vorbedingung",
                "Annahme verweigert: Gate P-Q3 (abox_validate) verletzt den "
                "Ledger-/Provenienzvertrag: "
                + "; ".join(pq3_fehler[:5])
                    + f" — Gate auf dem aktuellen Stand neu fahren: {pq3_kommando}",
                )
        if args.gate == "A-M4":
            pflichtbelege["pq3_ledger"] = [pq3_gelesen.sha256]

        if args.gate == "A-O1":
            # T-Box-Aenderung (Review T22-02): Der Beleg bindet alte und
            # neue Version, den Hash des T-Box-Moduls und das
            # Aenderungsartefakt. Ohne ihn ist A-O1 eine Zeichnung ueber
            # nichts.
            aenderung_pfad = fall / "abgeleitet" / "tbox" / "aenderung.json"
            aenderung_gelesen = (
                lies_gehasht(aenderung_pfad) if aenderung_pfad.is_file() else None
            )
            ak1_fehler = pruefe_tbox_aenderung(
                aenderung_pfad, fall,
                text=aenderung_gelesen.text() if aenderung_gelesen else None,
                repo_root=Path(args.repo_root).resolve() if args.repo_root else None,
            )
            if ak1_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-O1 braucht den Beleg der "
                    f"T-Box-Aenderung ({aenderung_pfad.relative_to(fall)}): "
                    + "; ".join(ak1_fehler[:5]),
                )
            # Zweiter Pflichtbeleg (Entscheid des Maintainers 2026-09-16):
            # die aktuarielle Stellungnahme. Die Unterschrift gehoert der
            # Architektur, die fachliche Bewertung dem Aktuariat.
            stellung_pfad = fall / "abgeleitet" / "tbox" / "stellungnahme.json"
            stellung_gelesen = (
                lies_gehasht(stellung_pfad) if stellung_pfad.is_file() else None
            )
            stellung_fehler = pruefe_stellungnahme_aktuariat(
                stellung_pfad, fall,
                text=stellung_gelesen.text() if stellung_gelesen else None,
                aenderung=json.loads(aenderung_gelesen.text()),
            )
            if stellung_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-O1 braucht die aktuarielle "
                    f"Stellungnahme ({stellung_pfad.relative_to(fall)}): "
                    + "; ".join(stellung_fehler[:5]),
                )
            pflichtbelege["tbox_aenderung"] = [aenderung_gelesen.sha256]
            pflichtbelege["stellungnahme_aktuariat"] = [stellung_gelesen.sha256]

        if args.gate == "A-K2":
            # Kern-Aenderung (Entscheid des Maintainers 2026-09-16): zwei
            # Belege an festen Orten, wie bei A-O1 — kein CLI-Flag, damit
            # der Beleg nicht dorthin zeigen kann, wo es gerade passt.
            kern_pfad = fall / "abgeleitet" / "kern" / "aenderung.json"
            regr_pfad = fall / "abgeleitet" / "kern" / "regression.json"
            kern_gelesen = lies_gehasht(kern_pfad) if kern_pfad.is_file() else None
            wurzel = Path(args.repo_root).resolve() if args.repo_root else None
            ak2_fehler = pruefe_kernaenderung(
                kern_pfad, fall,
                text=kern_gelesen.text() if kern_gelesen else None,
                repo_root=wurzel,
            )
            if ak2_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-K2 braucht den Beleg der "
                    f"Kern-Aenderung ({kern_pfad.relative_to(fall)}): "
                    + "; ".join(ak2_fehler[:5]),
                )
            aenderung_daten = json.loads(kern_gelesen.text())
            regr_gelesen = lies_gehasht(regr_pfad) if regr_pfad.is_file() else None
            regr_fehler = pruefe_kernregression(
                regr_pfad, fall,
                text=regr_gelesen.text() if regr_gelesen else None,
                aenderung=aenderung_daten,
            )
            if regr_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-K2 braucht den Regressionsbeleg "
                    f"({regr_pfad.relative_to(fall)}): "
                    + "; ".join(regr_fehler[:5])
                    + " -- ohne Regression keine Abnahme einer Kern-Aenderung "
                    "(Entscheid des Maintainers 2026-09-16)",
                )
            pflichtbelege["kernaenderung"] = [kern_gelesen.sha256]
            pflichtbelege["regression"] = [regr_gelesen.sha256]

        if args.gate == "A-B1":
            # Auslieferung (Entscheid des Maintainers 2026-09-16): Der
            # Beleg ist der ANKERSATZ des Pakets, das nach aussen geht —
            # der Satz, der ausserhalb des Pakets liegt und es bindet.
            # Was fachlich abgenommen ist, steht bereits gezeichnet IM
            # Paket (A-M1 bis A-M4); diese Abnahme zeichnet nicht die
            # Zahlen, sondern den Akt.
            if not args.anker or not args.ankersatz:
                return _sperre(
                    "usage",
                    "Annahme verweigert: A-B1 braucht --anker <datei> und "
                    "--ankersatz <sha256> — ohne den Satz zeichnete die "
                    "Auslieferung kein bestimmtes Paket",
                )
            try:
                saetze = anker_mod.lies_anker(Path(args.anker))
            except anker_mod.AnkerFehler as exc:
                return _sperre("vorbedingung", f"Annahme verweigert: {exc}")
            treffer = [z for z in saetze
                       if anker_mod.satz_hash(z) == args.ankersatz]
            if not treffer:
                return _sperre(
                    "vorbedingung",
                    f"Annahme verweigert: kein Ankersatz {args.ankersatz[:16]}… "
                    f"in {args.anker} — die Auslieferung zeichnete ein Paket, "
                    "das diese Ankerdatei nicht kennt",
                )
            satz = treffer[-1]
            if satz.get("art") != anker_mod.ART_AUSLIEFERUNG:
                return _sperre(
                    "vorbedingung",
                    f"Annahme verweigert: der Ankersatz ist als "
                    f"{satz.get('art')!r} ausgewiesen, nicht als "
                    "Auslieferung — ein Paket, das nicht nach aussen geht, "
                    "braucht keine Abnahme (und bekaeme sonst eine, die "
                    "nichts bedeutet)",
                )
            pflichtbelege["anker"] = [args.ankersatz]

        if args.gate in AKTUARIELLE_ABNAHMEN:
            # Aktuarielle Abnahme (ADR-010): Im Bestands-Scope stuetzt
            # sich der Entscheid auf das Testergebnis und den Bericht
            # des aktuariellen Tests; beide werden als Pflichtbelege
            # gepinnt und muessen vom aktuartest-Gate mit gruenem
            # Ledger auf GENAU diesen Bytes belegt sein. Im Tarif-Scope
            # gibt es keine Vertragslieferung und damit keine eigenen
            # Testartefakte (Rollenmenge leer); die P-K1-Belege sind
            # ueber artefakt_hashes ohnehin gepinnt.
            abnahme = args.gate
            # Dieselbe Namensbildung wie im aktuartest-Gate: A-M1 traegt
            # den nackten Namen, die Geschwister ihr Suffix.
            kennung = (
                "aktuartest" if abnahme == "A-M1"
                else f"aktuartest-{abnahme}"
            )
            beleg_rolle = (
                "aktuartest" if abnahme == "A-M1"
                else f"aktuartest_{abnahme.replace('-', '').lower()}"
            )
            if fall_scope == "bestand":
                berichte = fall / "abgeleitet" / "berichte"
                test_pfad = berichte / f"{kennung}.json"
                bericht_pfad = berichte / f"{kennung}.html"
                ledger_pfad = diagnostics / f"{kennung}.gate.json"
                am1_kommando = (
                    "python -m rechner_pipeline.gates.aktuartest "
                    f"--fall {fall} --abnahme {abnahme} --titel <titel>"
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
                        f"fehlt) — nachholen mit: {am1_kommando}",
                    )
                try:
                    # Ledger, Testergebnis und Bericht je einmal lesen:
                    # Pflichtbeleg-Hashes und Nachrechnung aus denselben
                    # Bytes (Review T23-01).
                    ledger_gelesen = lies_gehasht(ledger_pfad)
                    test_gelesen = lies_gehasht(test_pfad)
                    bericht_gelesen = lies_gehasht(bericht_pfad)
                    am1_ledger = ledger_gelesen.json()
                    bekannte_hashes[str(ledger_pfad.relative_to(fall))] = (
                        ledger_gelesen.sha256
                    )
                except (OSError, ValueError) as exc:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: aktuartest-Ledger unlesbar: "
                        f"{exc} — Gate neu fahren: {am1_kommando}",
                    )
                am1_fehler: List[str] = []
                if am1_ledger.get("command") != kennung:
                    am1_fehler.append(f"Ledger gehoert nicht zu {kennung}")
                erwartete_belege = {
                    f"abgeleitet/berichte/{kennung}.json":
                        test_gelesen.sha256,
                    f"abgeleitet/berichte/{kennung}.html":
                        bericht_gelesen.sha256,
                }
                ledger_belege = am1_ledger.get("summary", {}).get("belege")
                if ledger_belege != erwartete_belege:
                    am1_fehler.append(
                        "aktuartest-Ledger belegt nicht die aktuellen "
                        "Bytes von Testergebnis und Bericht"
                    )
                if am1_fehler:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: "
                        + "; ".join(am1_fehler[:5])
                        + f" — Gate auf dem aktuellen Stand neu fahren: "
                        f"{am1_kommando}",
                    )
                # Die Annahme RECHNET ihre Voraussetzungen — sie glaubt
                # sie nicht: Das Testverdikt wird aus dem Artefakt neu
                # abgeleitet und der Bericht bytegenau reproduziert. Ein
                # editierter Ledger-Status oder ein handgeschriebenes
                # Ergebnis ohne aktuellen Systemstand oeffnet die Abnahme nicht.
                from rechner_pipeline.gates import aktuartest as am1_gate

                try:
                    am1_test = test_gelesen.json()
                except (OSError, ValueError) as exc:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: Testergebnis unlesbar: "
                        f"{exc} — Gate neu fahren: {am1_kommando}",
                    )
                try:
                    am1_test_fehler = am1_gate.test_fehler(am1_test)
                except (TypeError, ValueError, KeyError, AttributeError) as exc:
                    am1_test_fehler = [
                        f"strukturell unlesbar ({type(exc).__name__}: {exc})"
                    ]
                if am1_test_fehler:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: Testergebnis verletzt den "
                        "Aktuartest-Vertrag: "
                        + "; ".join(am1_test_fehler[:5]),
                    )
                # Die Annahme glaubt dem Dateinamen nicht: Ein
                # A-M1-Ergebnis, das jemand unter dem Namen des
                # Verlaufstests ablegt, wuerde sonst den Ablauf
                # zeichnen, ohne ihn geprueft zu haben.
                gemeldete_abnahme = (
                    am1_test.get("profil", {}).get("kennung")
                    if isinstance(am1_test.get("profil"), dict) else None
                )
                if gemeldete_abnahme != abnahme:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: das Testergebnis gehoert zu "
                        f"{gemeldete_abnahme!r}, gezeichnet werden soll "
                        f"aber {abnahme} — Test der richtigen Abnahme "
                        f"fahren: {am1_kommando}",
                    )
                if am1_test.get("test_bestanden") is not True:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: der aktuarielle Test ist "
                        "nicht bestanden — eine Annahme ohne gruene "
                        "Vorlage waere ohne Grundlage (Ablehnung bleibt "
                        "moeglich)",
                    )
                if am1_test.get("system") != entscheid_systemstand:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: das Testergebnis traegt "
                        "nicht den aktuellen Systemstand — Test und "
                        f"Gate neu fahren: {am1_kommando}",
                    )
                am1_titel = (
                    am1_ledger.get("summary", {})
                    .get("bericht_erzeugung", {})
                )
                if not isinstance(am1_titel, dict):
                    am1_titel = {}
                try:
                    am1_html = am1_gate.baue_bericht(
                        titel=str(am1_titel.get("titel", "")),
                        test=am1_test,
                    )
                except (TypeError, ValueError, KeyError) as exc:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: Vorlage nicht "
                        f"reproduzierbar ({type(exc).__name__}: {exc})",
                    )
                if am1_html.encode("utf-8") != bericht_gelesen.roh:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: der Bericht ist nicht die "
                        "deterministische Wiedergabe des Testergebnisses "
                        f"— Gate neu fahren: {am1_kommando}",
                    )
                pflichtbelege[beleg_rolle] = [
                    erwartete_belege[f"abgeleitet/berichte/{kennung}.json"]
                ]
                pflichtbelege[f"{beleg_rolle}_bericht"] = [
                    erwartete_belege[f"abgeleitet/berichte/{kennung}.html"]
                ]
            erwartete_rollen = fall_mod.belegrollen(
                abnahme, fall_scope or ""
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

        if args.gate == "A-M4":
            # Die Generationen werden nicht geraten, sondern aus der A-Box
            # genommen — und JE GENERATION als eigene Zeile ausgegeben:
            # ein zusammengesetztes "klv/tg2012|klv/tg2015" waere in der
            # Shell eine Pipe und damit kein Kommando, das ein Bediener
            # uebernehmen kann. P-K1 laeuft ohnehin je Generation.
            generationen = sorted(g.id for g in abox.generationen)
            if not generationen:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: die A-Box enthaelt keine Generation - "
                    "damit existiert keine P-K1-Pruefmenge",
                )
            pk1_kommando = "\n".join(
                "python -m rechner_pipeline.gates.generation_golden "
                f"--fall {fall} --generation {generation} "
                f"--repo-root {args.repo_root}"
                for generation in generationen
            )
            beleg_dateien = sorted(diagnostics.glob(O3_BELEG_GLOB))
            if not beleg_dateien:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: kein unveraenderlicher P-K1-Beleg "
                    f"vorhanden - je A-Box-Generation nachholen mit:\n{pk1_kommando}",
                )

            geladene_belege: List[dict] = []
            beleg_fehler: List[str] = []
            for pfad in beleg_dateien:
                daten, fehler = pruefe_pk1_beleg(pfad)
                beleg_fehler.extend(fehler)
                if daten is not None and not fehler:
                    geladene_belege.append(daten)
            if beleg_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: P-K1-Belegvertrag verletzt: "
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
                    teile.append(f"P-K1-Beleg fehlt fuer {fehlend}")
                if zusaetzlich:
                    teile.append(
                        f"P-K1-Belegmenge enthaelt fremde Generationen {zusaetzlich}"
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
                        "P-K1-Eingangsartefakte abweichend fuer "
                        f"{input_abweichend}: " + "; ".join(details[:3])
                    )
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: " + "; ".join(teile)
                    + f" - P-K1 auf dem aktuellen Stand neu fahren:\n{pk1_kommando}",
                )

            pk1_belege = {
                generation: sorted(
                    beleg["beleg_sha256"]
                    for beleg in passende_belege
                    if beleg["generation"] == generation
                )
                for generation in generationen
            }
            pflichtbelege["pk1_belege"] = sorted(
                beleg_sha
                for belege_der_generation in pk1_belege.values()
                for beleg_sha in belege_der_generation
            )
            # Geltender A-Q1-Annahme-Snapshot auf DIESEM A-Box-Stand.
            schluessel_fehler = _schluessel_laden()
            if schluessel_fehler:
                return _sperre(
                    "freigabe",
                    "Annahme verweigert: externe Freigabeschluessel "
                    "ungueltig: " + "; ".join(schluessel_fehler[:5]),
                )
            verzeichnis_aq1 = entscheide_verzeichnis(fall)
            aq1_snapshots, aq1_spitzen, aq1_fehler = _lade_snapshot_kette(
                verzeichnis_aq1, "A-Q1", fall, schluesselring,
                entscheid_systemstand,
            )
            if aq1_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-Q1-Snapshot-Vertrag verletzt: "
                    + "; ".join(aq1_fehler[:5]),
                )
            aq1_spitze = (
                aq1_snapshots[aq1_spitzen[0]][1] if len(aq1_spitzen) == 1 else None
            )
            eingang_hash = _sha256_datei(fall / "eingang.json")
            passend = (
                aq1_spitze is not None
                and aq1_spitze["entscheid"] == "angenommen"
                and aq1_spitze["artefakt_hashes"].get(
                    "abgeleitet/abox/abox.json"
                ) == abox_hash
                and aq1_spitze["artefakt_hashes"].get("eingang.json")
                == eingang_hash
                and aq1_spitze["artefakt_hashes"].get("fall.json")
                == fall_json_sha256
                and aq1_spitze["system"] == entscheid_systemstand
            )
            if not passend:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: keine eindeutige, signierte A-Q1-"
                    "ANNAHME auf aktuellem Scope-, Eingangs-, A-Box- und "
                    "Systemstand "
                    "— A-M4 nimmt denselben Stand ab, den A-Q1 gesehen hat, "
                    "oder gar keinen (A-Q1 auf diesem Stand entscheiden mit: python -m "
                    "rechner_pipeline.gates.gate_entscheid --fall "
                    f"{fall} --gate A-Q1 --entscheid angenommen --rolle mensch "
                    "--entscheider <name> --begruendung <text> "
                    "--freigabe-schluessel <externe-datei>)",
                )
            assert aq1_spitze is not None
            zf = _zeichnungsfehler(
                zeichnungsordnung, "A-Q1",
                aq1_spitze.get("freigabe", {}).get("schluessel_sha256", ""),
            )
            if zf:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: die geltende A-Q1-Annahme wurde "
                    f"von einem unberechtigten Schluessel gezeichnet -- {zf}",
                )
            pflichtbelege["aq1_snapshot"] = [aq1_spitze["snapshot_sha256"]]

            # Die aktuariellen Abnahmen gehen A-M4 voraus: A-M1 immer
            # (ADR-010), im Bestands-Scope auch A-M2 und A-M3
            # (Entscheidung Auftraggeber 2026-08-31). Vorher war nur A-M1
            # Voraussetzung — ein Bestand mit richtigem Stichtagswert und
            # falscher Ablaufleistung kam also durch das Controlling. Die
            # Rueckschleife bleibt zulaessig (neue Snapshots), nur die
            # Umkehrung nicht. Im Tarif-Scope gibt es keinen Bestand,
            # dessen Verlauf oder Geschaeftsvorfaelle A-M2/A-M3 abnehmen
            # koennten — dort bleibt es bei A-M1.
            pflicht_abnahmen = ["A-M1"] + (
                ["A-M2", "A-M3"] if fall_scope == "bestand" else []
            )
            for abnahme_gate in pflicht_abnahmen:
                snapshots_a, spitzen_a, ketten_fehler_a = (
                    _lade_snapshot_kette(
                        verzeichnis_aq1, abnahme_gate, fall, schluesselring,
                        entscheid_systemstand,
                    )
                )
                if ketten_fehler_a:
                    return _sperre(
                        "vorbedingung",
                        f"Annahme verweigert: {abnahme_gate}-Snapshot-"
                        "Vertrag verletzt: "
                        + "; ".join(ketten_fehler_a[:5]),
                    )
                spitze_a = (
                    snapshots_a[spitzen_a[0]][1]
                    if len(spitzen_a) == 1 else None
                )
                passend_a = (
                    spitze_a is not None
                    and spitze_a["entscheid"] == "angenommen"
                    and spitze_a["artefakt_hashes"].get(
                        "abgeleitet/abox/abox.json"
                    ) == abox_hash
                    and spitze_a["artefakt_hashes"].get("eingang.json")
                    == eingang_hash
                    and spitze_a["artefakt_hashes"].get("fall.json")
                    == fall_json_sha256
                    and spitze_a["system"] == entscheid_systemstand
                )
                if not passend_a:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: keine eindeutige, signierte "
                        f"{abnahme_gate}-ANNAHME (aktuarielle Abnahme) auf "
                        "aktuellem Eingangs-, A-Box- und Systemstand — die "
                        "aktuariellen Abnahmen gehen A-M4 voraus (A-M1: "
                        "ADR-010; A-M2/A-M3 im Bestands-Scope: Entscheidung "
                        "2026-08-31; entscheiden mit: python -m "
                        "rechner_pipeline.gates.gate_entscheid --fall "
                        f"{fall} --gate {abnahme_gate} --entscheid angenommen "
                        "--rolle mensch --entscheider <name> --begruendung "
                        "<text> --freigabe-schluessel <externe-datei>)",
                    )
                assert spitze_a is not None
                zf = _zeichnungsfehler(
                    zeichnungsordnung, abnahme_gate,
                    spitze_a.get("freigabe", {}).get("schluessel_sha256", ""),
                )
                if zf:
                    return _sperre(
                        "vorbedingung",
                        f"Annahme verweigert: die geltende {abnahme_gate}-"
                        "Annahme wurde von einem unberechtigten Schluessel "
                        f"gezeichnet -- {zf}",
                    )
                rolle_a = f"am{abnahme_gate[-1]}_snapshot"
                pflichtbelege[rolle_a] = [spitze_a["snapshot_sha256"]]

            if fall_scope == "bestand":
                bestandsbelege, bestands_fehler = _passende_bestandsbelege(
                    diagnostics=diagnostics,
                    fall=fall,
                    eingang_sha256=eingang_hash,
                    abox_sha256=abox_hash,
                    system=entscheid_systemstand,
                    repo_root=repo_root,
                    bekannt=bekannte_hashes,
                )
                if bestands_fehler or bestandsbelege is None:
                    return _sperre(
                        "vorbedingung",
                        "Annahme verweigert: Bestandsbelege verletzen "
                        "den Beleg-/Provenienzvertrag: "
                        + "; ".join(bestands_fehler[:5])
                        + " — P-B1, vollstaendige Migrationssuite und Abnahmebericht "
                        "auf demselben Stand neu erzeugen",
                    )
                for rolle, beleg_sha256 in bestandsbelege.items():
                    pflichtbelege[rolle] = [beleg_sha256]

            erwartete_rollen = fall_mod.am4_belegrollen(fall_scope or "")
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
        verzeichnis, args.gate, fall, schluesselring, entscheid_systemstand
    )
    if ketten_fehler:
        return _sperre(
            "snapshot",
            "Entscheid verweigert: P9-Snapshot-Vertrag verletzt: "
            + "; ".join(ketten_fehler[:5]),
        )
    geltende = [bestehende[sha] for sha in spitzen]

    # Die Rolle eines Belegs wird aus dem Schluessel BESTIMMT, wo ein
    # Schluessel und eine Ordnung vorliegen; behauptet ist sie nur bei
    # einer Ablehnung ohne Schluessel (ADR-018).
    rolle = args.rolle
    if zeichnungsordnung is not None and aktiver_schluessel is not None:
        bestimmt = _zeichnungsrolle(zeichnungsordnung, aktiver_schluessel)
        if bestimmt is None and args.entscheid == "angenommen":
            return _sperre(
                "zeichnung",
                "Annahme verweigert: der Freigabeschluessel gehoert keiner "
                "Rolle der Zeichnungsordnung -- wer nicht in der Ordnung "
                "steht, zeichnet nicht",
            )
        if bestimmt is not None:
            if rolle is not None and rolle != bestimmt:
                return _usage(
                    f"--rolle {rolle!r} widerspricht der aus dem Schluessel "
                    f"bestimmten Rolle {bestimmt!r}"
                )
            rolle = bestimmt
    if rolle is None:
        # Eine Annahme ohne Ordnung kann keine Rolle bestimmen — das ist
        # die Sperre aus ADR-018, kein Bedienfehler.
        return _sperre(
            "zeichnung",
            "Annahme verweigert: --zeichnungsordnung fehlt — die zeichnende "
            "Rolle wird aus dem Freigabeschluessel ueber die Ordnung "
            "bestimmt, nicht behauptet (ADR-018)",
        )

    # Die Sperren der Rollenbindung laufen bei JEDEM Annahme-Aufruf, VOR dem
    # Idempotenz-Kurzschluss (Review T23-08): vorher liefen _zeichnungsfehler
    # und die Mandatspflicht nur beim Bau eines NEUEN Snapshots — ein
    # Wiederholungsaufruf mit anderem Schluessel, anderer Ordnung oder ohne
    # Mandat bekam "bereits_vorhanden" mit Exit 0, ohne dass seine Zeichnung
    # je geprueft wurde. Und die Zeichnung gehoert in den Vergleichsschluessel:
    # ein Aufruf unter anderer Ordnung, Klasse oder anderem Mandat ist kein
    # identischer Entscheid.
    zeichnung: Optional[Dict[str, str]] = None
    if args.entscheid == "angenommen":
        if aktiver_schluessel is None:
            return _sperre(
                "freigabe",
                "Annahme verweigert: --freigabe-schluessel <externe-datei> "
                "ist erforderlich; ein frei editierbarer Fall darf seine "
                "menschliche Freigabe nicht selbst behaupten",
            )
        if zeichnungsordnung is None:
            return _sperre(
                "zeichnung",
                "Annahme verweigert: --zeichnungsordnung fehlt — die "
                "zeichnende Rolle wird aus dem Freigabeschluessel ueber die "
                "Ordnung bestimmt, nicht behauptet (ADR-018)",
            )
        zf = _zeichnungsfehler(zeichnungsordnung, args.gate, aktiver_schluessel)
        if zf:
            return _sperre("zeichnung", f"Annahme verweigert: {zf}")
        zeichnung = zeichnung_fuer(
            zeichnungsordnung, zeichnungsordnung_sha, aktiver_schluessel,
            mandat_sha256,
        )
        # Simulation ohne Mandat ist keine Besetzung, sondern eine Luecke
        # (ADR-018; Review T22-07): Die Sperre greift VOR der Signatur —
        # und vor dem Kurzschluss (Review T23-08).
        if (
            zeichnung.get("schluesselklasse") == "simulation"
            and not zeichnung.get("mandat_sha256")
        ):
            return _sperre(
                "mandat",
                f"Annahme verweigert: die Rolle {zeichnung['rolle']!r} "
                "ist mit einem Simulationsschluessel besetzt und handelt ohne "
                "Mandat — --mandat <datei> ist bei Schluesselklasse simulation "
                "Pflicht (ADR-018)",
            )

    kern_inhalt = {
        "command": "gate_entscheid",
        "gate_version": GATE_VERSION,
        "gate": args.gate,
        "entscheid": args.entscheid,
        "entscheider": args.entscheider,
        "rolle": rolle,
        "begruendung": args.begruendung,
        # Der NAME des Falls, nicht sein Pfad. Das Feld dient der
        # Identitaet ("gehoert dieser Snapshot zu diesem Fall?"), und
        # dafuer ist ein absoluter Pfad schlecht: Er bricht, sobald der
        # Fall umzieht, und er traegt das Heimatverzeichnis des
        # Bedieners in ein signiertes und moeglicherweise
        # veroeffentlichtes Artefakt. Der Name leistet dasselbe und ist
        # neutral.
        "fall": fall.name,
        "artefakt_hashes": _artefakt_hashes(
            fall, ausser_gate=args.gate, bekannt=bekannte_hashes,
        ),
        "system": entscheid_systemstand,
    }
    # DIE Stelle, an der A-B1 seinen Ankersatz verlor: kern_inhalt ist
    # das, was signiert wird. Ein Gate, das hier fehlt, rechnet seine
    # Pflichtbelege aus und wirft sie still weg.
    if args.gate in GATES_MIT_PFLICHTBELEGEN:
        kern_inhalt["fall_scope"] = fall_scope
        kern_inhalt["pflichtbelege"] = pflichtbelege
    if args.gate == "A-M4":
        kern_inhalt["pk1_belege"] = pk1_belege
    if zeichnung is not None:
        kern_inhalt["zeichnung"] = zeichnung
    # Idempotenz gegen den GELTENDEN Snapshot: derselbe Entscheid auf
    # demselben Stand — unter derselben Rollenbindung — wird gemeldet,
    # nicht dupliziert. Ein INHALTLICH anderer Entscheid (auch: andere
    # Ordnung, Klasse, anderes Mandat) erzeugt einen neuen Snapshot, der
    # alle bisherigen pinnt (Kette).
    for pfad, daten in geltende:
        if all(daten.get(k) == v for k, v in kern_inhalt.items()):
            return _finalize(build_result(
                command=ledger_command, gate=f"entscheid.{args.gate}",
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
        # Die Rollenbindung steht bereits im Snapshot (ueber kern_inhalt) und
        # wird mitsigniert: Wer spaeter prueft, sieht nicht nur DASS
        # gezeichnet wurde, sondern als welche Rolle, unter welcher Ordnung
        # und mit welcher Schluesselklasse — Mensch oder Simulation
        # (ADR-018). Geprueft wurde sie oben, vor dem Kurzschluss.
        assert snapshot.get("zeichnung") is not None and aktiver_schluessel is not None
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
        "rolle": rolle,
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
    if args.gate == "A-M4":
        ergebnis_summary["pk1_belege"] = pk1_belege
        ergebnis_summary["fall_scope"] = fall_scope
        ergebnis_summary["pflichtbelege"] = pflichtbelege
    return _finalize(build_result(
        command=ledger_command, gate=f"entscheid.{args.gate}",
        gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"fall": str(fall), "snapshot": str(ziel)},
        summary=ergebnis_summary,
        input_hashes=dict(snapshot["artefakt_hashes"]),
        # Der Snapshot bezeugt die eben geschriebenen Bytes (Review T23-01).
        output_hashes={str(ziel): hashlib.sha256(payload).hexdigest()},
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
