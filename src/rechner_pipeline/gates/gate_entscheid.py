"""``gate_entscheid`` — der P9-Snapshot eines menschlichen Gates.

Ein menschliches Gate (A-Q1 fachlich; A-M1, A-M2, A-M3 die drei
aktuariellen Abnahmen; A-M4 Migrationsabnahme; A-O1 T-Box-Aenderung; A-K2
der Kernstand des Falls; A-B1, A-B2 Auslieferung und Zugang)
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
es bei A-M1. In beiden Scopes verlangt A-M4 seit dem Entscheid des
Maintainers vom 2026-10-01 die geltende A-K2-Annahme des Kernstands, auf
dem der Fall rechnet (ADR-018, Nachtrag 2026-10-01): Rolle
``mensch/rechenkern``, Belege ``abgeleitet/kern/aenderung.json`` und
``regression.json`` (bis zum Regressionswerkzeug die benannte Ausnahme
"nicht gefahren"), nachgerechnet gegen den lebenden Kern. Im
Abnahme-Ledger verlangt A-M4 ausserdem die
vier festen Renderer-Artefaktrollen, prueft ihre aktuellen Bytes und
leitet das Berichtsverdikt aus den gebundenen Inhalten neu ab.

**Linienbereich und Ordnungslinie (ADR-025).** Mit ``--linie`` allein
zeichnet das Kommando die Abnahmen des Zielsystems AUSSERHALB eines Falls
(A-K2, A-O1, A-T1 Tarifwerk, A-B3 Anfangsbestand; Scope ``linie``) — die
Erstabnahme und spaetere Aenderungen in der Entwicklung, mit derselben
Kette, Signatur und Rollenregel. Mit ``--fall`` und ``--linie`` zeichnet es
im Fall unter der Spitze der Versionslinie der Zeichnungsordnung und pinnt
ihr Glied; jede Vorbedingung liest es gegen die Ordnung, unter der sie
gezeichnet wurde. A-M4 verlangt zusaetzlich das Tarifwerk. Die Linie ist
Pflicht (Nachtrag 2026-10-01): ohne ``--linie`` kein Entscheid.

**Lebenslauf eines Falls (ADR-026).** Jede Annahme eines Falls ausser dem
Auftrag selbst setzt den geltenden Fallauftrag ``A-M6`` voraus
(:func:`fallauftrag_pruefen`, EINE Stelle) und nennt ihn signiert; nach dem
gezeichneten Fallabbruch ``A-M5`` ist im Fall nichts mehr zu entscheiden
(:func:`abbruch_im_fall`).

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
    ist_schreibrest,
    lies_gehasht,
    parse_gate_args,
    run_command,
    schreibe_exklusiv,
    utc_now,
)
from rechner_pipeline.gates._fall_scope import (
    bestands_belegrollen,
    lies_artefakt_eintrag,
    pruefe_artefakt_eintrag,
    scope_bindung,
    validate_scope_bindung,
)
from rechner_pipeline.gates import kernstand_belegen as _kernstand
from rechner_pipeline.gates import stand_belegen as _stand
from rechner_pipeline.gates import tarifwerk_belegen as _tarifwerk
from rechner_pipeline.gates._provenienz import (
    O3_BELEG_GLOB,
    git_stand,
    pruefe_pk1_beleg,
    systemstand,
    zweig_ist_aktuell,
)
from rechner_pipeline.models import anfangsbestand as _anfangsbestand
from rechner_pipeline.models import kernabnahme as _kernabnahme
from rechner_pipeline.models import ordnungslinie as _ordnungslinie
from rechner_pipeline.models import standabnahme as _standabnahme
from rechner_pipeline.models import tarifwerkabnahme as _tarifwerkabnahme
from rechner_pipeline.models.belegrollen import (
    BelegrollenFehler,
    am4_belegrollen,
    belegrollen,
)
from rechner_pipeline.models.freigabe import (
    FREIGABE_SCHLUESSEL_MIN_BYTES as _FREIGABE_SCHLUESSEL_MIN_BYTES,
    freigabe_fuer,
    lade_schluesselring,
    pruefe_freigabe,
)
from rechner_pipeline.models.freigabe import _ist_unter as _models_ist_unter
from rechner_pipeline.models.schemas import (
    GateLedgerEntry,
    P9_AKTUARIELLE_ABNAHMEN,
    P9_FREIGABE_VERFAHREN,
    P9_GATE_VERSION,
    P9_GATES_MIT_AUSNAHMEN,
    P9_GATES_MIT_STAND,
    P9_SNAPSHOT_SCHEMA_VERSION,
    P9Snapshot,
    p9_semantik_fehler,
    p9_freigabe_nachricht,
    p9_snapshot_sha256,
)

GATE_VERSION = P9_GATE_VERSION
# Umzug 2026-09-01: der Rollen-/Gate-Vertrag lebt in models.zeichnung
# (paketuebergreifend — auch ontologie.entscheide liest ihn seither).
from rechner_pipeline.models import fallauftrag as _fallauftrag  # noqa: E402
from rechner_pipeline.models.schemas import P9_LEBENSLAUF_FELDER  # noqa: E402
from rechner_pipeline.models.zeichnung import (
    ABBRUCH_GATE,
    AUFTRAG_GATE,
    FALLROLLEN_GATES,
    GATES_MIT_PFLICHTBELEGEN,
    LEBENSLAUF_GATES,
    ausserhalb_des_falls,  # noqa: E402
    GUELTIGE_GATES,
    lade_zeichnungsordnung as _models_lade_zeichnungsordnung,
    zeichnungsrolle as _models_zeichnungsrolle,
    gueltige_rollenkennung,
    zeichnende_rolle_fehler,
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
FREIGABE_SCHLUESSEL_MIN_BYTES = _FREIGABE_SCHLUESSEL_MIN_BYTES


def _sha256_datei(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _ist_unter(pfad: Path, wurzel: Path) -> bool:
    return _models_ist_unter(pfad, wurzel)


def _lade_freigabe_schluessel(
    pfade: object,
    fall: Path,
) -> Tuple[Dict[str, bytes], List[str], Optional[str]]:
    """Schluesselring laden — delegiert an ``models.freigabe`` (T26-03, Weg 2):
    dieselbe Pruefung, die der Betriebseingang faehrt. Der Fall ist der
    Vertrauensraum, in dem kein Schluessel liegen darf."""
    ring, fehler, aktiv = lade_schluesselring(pfade, ausserhalb=fall)
    return ring, [
        f.replace("freigabe-schluessel muss", "--freigabe-schluessel muss")
         .replace("innerhalb des Vertrauensraums (Fall bzw. Ablage)", "innerhalb des Falls")
        for f in fehler
    ], aktiv


def _freigabe_fuer(snapshot_ohne_freigabe: dict, key: bytes) -> Dict[str, str]:
    return freigabe_fuer(snapshot_ohne_freigabe, key)


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
    return pruefe_freigabe(snapshot, schluesselring)


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


#: Schema des A-O1-Belegs (Review T22-02; 2 seit ADR-025: mit dem ganzen
#: Vokabular und dem zuletzt abgenommenen, Grundlage der lesbaren Sicht).
TBOX_AENDERUNG_SCHEMA_VERSION = _stand.TBOX_AENDERUNG_SCHEMA_VERSION
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
    # Das Vokabular, das die Sicht zeigt, ist das des Codes — nachgerechnet,
    # nicht geglaubt (ADR-025); das zuletzt abgenommene steht mit seinem
    # Abdruck daneben.
    vokabular = json.loads(json.dumps(tbox_modul.vokabular(), sort_keys=True))
    if daten.get("vokabular") != vokabular:
        fehler.append("vokabular ist nicht das Vokabular des geladenen T-Box-Moduls")
    if daten.get("vokabular_sha256") != tbox_modul.vokabular_sha256():
        fehler.append("vokabular_sha256 ist nicht der Abdruck des Vokabulars")
    vorher = daten.get("vorher")
    if vorher is not None:
        felder = {"beleg_sha256", "snapshot_sha256", "version", "vokabular_sha256", "vokabular"}
        if not (isinstance(vorher, dict) and set(vorher) == felder
                and _stand._vokabular_sha256(vorher.get("vokabular"))
                == vorher.get("vokabular_sha256")):
            fehler.append(f"vorher traegt genau {sorted(felder)} mit stimmigem Abdruck")
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


#: Schema der beiden Belege von ``A-K2.kernaenderung``. Getrennt gehalten,
#: weil sie verschiedene Dinge bezeugen: Der AENDERUNGSbeleg sagt, WAS am
#: Kern anders wurde; der REGRESSIONSbeleg sagt, was das fuer den bestehenden
#: Bestand bedeutet. Vertrag und Produzent: ``gates.kernstand_belegen``,
#: Gegenstand und Ausnahme: ``models.kernabnahme`` (ADR-018, Nachtrag
#: 2026-10-01).
KERN_AENDERUNG_SCHEMA_VERSION = _kernstand.KERN_AENDERUNG_SCHEMA_VERSION
KERN_REGRESSION_SCHEMA_VERSION = _kernstand.KERN_REGRESSION_SCHEMA_VERSION

#: Die eingefrorenen Referenzwerte und das Rechenkern-Paket — als Pfadteile,
#: aus dem EINEN Gegenstand (``models.kernabnahme.KERNSTAND``). Das Paket
#: wird ueber einen Sammelhash gebunden, NICHT ueber einen Import: Das
#: Entscheid-Kommando gehoert dem KI-Tool (Ebene 2), der Rechenkern der
#: Vorzeige (Ebene 3), und das Tool greift nicht in die Vorzeige (ADR-017).
KERN_REFERENZWERTE = tuple(_kernabnahme.KERN_REFERENZWERTE.split("/"))
KERN_PAKET = tuple(_kernabnahme.KERN_PAKET.split("/"))
referenzwerte_hash = _kernstand.referenzwerte_hash
kern_modul_hash = _kernstand.kern_modul_hash


def pruefe_kernaenderung(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    repo_root: Path | None = None,
) -> List[str]:
    """Den Aenderungsbeleg des Kernstands gegen Code und Git halten.

    Der Beleg sagt, VON welchem zuletzt abgenommenen Kernstand (Commit und
    Version) NACH welchem es geht, was sich je Modul geaendert hat, mit
    welchen Commits, und welchen Sammelhash Kern und Referenzwerte tragen.
    Ein unveraenderter Kern ist ein gueltiger Beleg (Entscheid 2026-10-01:
    jeder Fall traegt die Abnahme seines Kernstands) — er sagt dann genau
    das.

    Geprueft wird erst Feld fuer Feld (die Meldungen nennen, was nicht
    stimmt), dann wird der GANZE Beleg nachgerechnet
    (``kernstand_belegen.nachgerechnet``): Ein Beleg, der nur in sich
    stimmig ist, bezeugt nichts (T24-04) — eine erfundene Commit-Zeile, ein
    weggelassenes Modul, ein geschoenter Diffstat fallen hier.
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
    if daten.get("art") != _kernstand.ART:
        fehler.append(f"art muss {_kernstand.ART!r} sein")
    von, nach = daten.get("von_version"), daten.get("nach_version")
    semver_ok = True
    for name, wert in (("von_version", von), ("nach_version", nach)):
        if not isinstance(wert, str) or not _SEMVER.match(wert):
            fehler.append(f"{name} muss eine Version x.y.z sein")
            semver_ok = False
    if semver_ok and _semver_tuple(von) > _semver_tuple(nach):
        fehler.append(
            f"von_version {von!r} liegt nach nach_version {nach!r} "
            "— ein Uebergang laeuft nicht abwaerts"
        )
    wurzel = repo_root
    if wurzel is not None and semver_ok:
        init = wurzel.joinpath(*KERN_PAKET, "__init__.py")
        ist_version = _kernstand.kern_version(
            init.read_text(encoding="utf-8") if init.is_file() else None)
        if ist_version != nach:
            fehler.append(
                f"nach_version {nach!r} ist nicht die Version, die der Kern "
                f"traegt ({ist_version!r})"
            )
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
            "ueberein — der Beleg behauptet einen Kern, den der Code "
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
    kern_alt = daten.get("kern_alt_sha256")
    if not (isinstance(kern_alt, str) and _SHA256.match(kern_alt)):
        fehler.append("kern_alt_sha256 fehlt oder ist kein SHA-256")
    if not isinstance(daten.get("veraendert"), bool):
        fehler.append("veraendert fehlt oder ist kein Wahrheitswert")
    if not isinstance(daten.get("module"), list):
        fehler.append("module fehlt oder ist keine Liste")
    git_beleg = daten.get("git")
    if not isinstance(git_beleg, dict):
        fehler.append("git fehlt oder ist kein Objekt")
    else:
        # Der Zweig muss den zuletzt abgenommenen Kernstand ENTHALTEN
        # (merge_base == referenz_commit): Sonst mischte die Differenz die
        # Aenderungen dieses Zweigs mit fremden.
        if not zweig_ist_aktuell(git_beleg):
            fehler.append(
                f"der lebende Stand liegt nicht auf dem zuletzt abgenommenen "
                f"Kernstand {git_beleg.get('referenz')!r} auf (merge_base != "
                "referenz_commit) — die Differenz mischte die eigene Aenderung "
                "mit einer fremden"
            )
        # dirty sperrt die qualitative Pruefung NICHT mehr (2026-10-01): Die
        # Sicht zeigt nicht committete Aenderungen ausdruecklich, und der
        # Diffstat laeuft gegen den Arbeitsbaum. Die Sperre gehoert zur
        # Regression und steht dort (pruefe_kernregression).
        if wurzel is not None:
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
    if fehler:
        return fehler
    if wurzel is None:
        return ["der Beleg ist nicht nachrechenbar — --repo-root fehlt"]
    try:
        neu = _kernstand.nachgerechnet(wurzel, daten)
    except (_kernstand.KernstandFehler, OSError) as exc:
        return [f"der Beleg ist nicht nachrechenbar: {exc}"]
    abweichend = sorted(k for k in set(neu) | set(daten) if neu.get(k) != daten.get(k))
    if abweichend:
        return [
            "der Beleg ist nicht der Kernstand zwischen dem zuletzt abgenommenen "
            f"Stand und dem Arbeitsbaum — abweichend: {abweichend}; neu erzeugen "
            "mit: python -m rechner_pipeline.gates.kernstand_belegen --fall <fall> "
            f"--repo-root <repo> --von {neu['git']['referenz']} --begruendung <text>"
        ]
    return []


def _pruefe_regressionsausnahme(
    daten: Dict[str, object], aenderung: Dict[str, object] | None
) -> List[str]:
    """Die benannte Ausnahme — genau diese Form, nichts anderes Unvollstaendiges."""
    if not _kernabnahme.REGRESSION_AUSNAHME_ERLAUBT:
        return [
            "der Regressionsbeleg ist die Ausnahme 'nicht gefahren', die Ausnahme "
            "ist aber nicht mehr erlaubt (models.kernabnahme."
            "REGRESSION_AUSNAHME_ERLAUBT) — den Regressionsproduzenten fahren"
        ]
    fehler: List[str] = []
    if set(daten) != _kernabnahme.AUSNAHME_FELDER:
        fehler.append(
            "der Ausnahmebeleg traegt genau die Felder "
            f"{sorted(_kernabnahme.AUSNAHME_FELDER)} — fehlen="
            f"{sorted(_kernabnahme.AUSNAHME_FELDER - set(daten))}, fremd="
            f"{sorted(set(daten) - _kernabnahme.AUSNAHME_FELDER)}; ein Feld mehr "
            "saehe wie ein Ergebnis aus"
        )
    if daten.get("schema_version") != KERN_REGRESSION_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {KERN_REGRESSION_SCHEMA_VERSION} sein")
    for feld, soll in (("zustand", _kernabnahme.ZUSTAND_NICHT_GEFAHREN),
                       ("grund", _kernabnahme.GRUND_NICHT_GEFAHREN),
                       ("grundlage", _kernabnahme.AUSNAHME_GRUNDLAGE)):
        if daten.get(feld) != soll:
            fehler.append(f"{feld} muss {soll!r} sein, nicht {daten.get(feld)!r}")
    if aenderung is None:
        fehler.append("die Ausnahme ist an keinen Aenderungsbeleg gebunden")
    else:
        for feld in _kernabnahme.BINDUNGSFELDER:
            if daten.get(feld) != aenderung.get(feld):
                fehler.append(
                    f"{feld} {daten.get(feld)!r} weicht vom Aenderungsbeleg "
                    f"({aenderung.get(feld)!r}) ab — die Ausnahme gehoert zu "
                    "einem anderen Uebergang"
                )
    return fehler


def pruefe_kernregression(
    pfad: Path,
    fall: Path,
    *,
    text: str | None = None,
    aenderung: Dict[str, object] | None = None,
) -> List[str]:
    """Den Regressionsbeleg des Kernstands pruefen.

    Zwei Formen, und nur diese:

    * die benannte AUSNAHME (ADR-018, Nachtrag 2026-10-01): Zustand
      ``nicht_gefahren``, Grund "Werkzeug noch nicht erstellt", gebunden an
      den Uebergang des Aenderungsbelegs — angenommen, solange
      ``models.kernabnahme.REGRESSION_AUSNAHME_ERLAUBT`` gilt;
    * das ERGEBNIS nach der Regel vom 2026-09-16: jeder Vertrag mit altem
      und neuem Kern durchgerechnet, Differenz JE VERTRAG.
      ``vertraege_geprueft`` muss ``vertraege_gesamt`` sein — eine
      Stichprobe ist hier wertlos, der Fehler, der einen von tausend
      Vertraegen trifft, ist der gesuchte; Aggregate sind aus demselben
      Grund nicht zugelassen. Und der Arbeitsbaum muss beim Belegen sauber
      gewesen sein: Eine Regression gegen uncommittete Aenderungen ist
      nicht reproduzierbar.
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
    if "zustand" in daten:
        return _pruefe_regressionsausnahme(daten, aenderung)
    fehler: List[str] = []
    if daten.get("schema_version") != KERN_REGRESSION_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {KERN_REGRESSION_SCHEMA_VERSION} sein")
    if aenderung is not None:
        for feld in _kernabnahme.BINDUNGSFELDER:
            if daten.get(feld) != aenderung.get(feld):
                fehler.append(
                    f"{feld} {daten.get(feld)!r} weicht vom Aenderungsbeleg "
                    f"({aenderung.get(feld)!r}) ab — die Regression gehoert "
                    "zu einem anderen Uebergang"
                )
        git_beleg = aenderung.get("git") if isinstance(aenderung.get("git"), dict) else {}
        if git_beleg.get("dirty") != "nein":
            fehler.append(
                "git.dirty des Aenderungsbelegs ist nicht 'nein' — eine "
                "Regression gegen uncommittete Aenderungen ist nicht "
                "reproduzierbar"
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


def _kernstand_kommando(fall: Path, repo_root: object) -> str:
    return ("python -m rechner_pipeline.gates.kernstand_belegen "
            f"--fall {fall} --repo-root {repo_root} --von <zuletzt abgenommener "
            "Kernstand> --begruendung <text>")


def kernstand_belege_pruefen(
    fall: Path, repo_root: Optional[Path]
) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    """Die beiden Belege des Kernstands an ihren festen Orten pruefen.

    Rueckgabe ``(fehler, {rolle: sha256}, ausnahmen)``. EINE Funktion fuer
    beide Leser: das Zeichnen von A-K2 und die Vorbedingung von A-M4, die
    dieselben Bytes nachrechnet, statt der A-K2-Annahme zu glauben. Die
    ``ausnahmen`` sind aus dem Regressionsbeleg ABGELEITET
    (``models.kernabnahme.ausnahmen_fuer``), nicht angegeben.
    """
    kern_pfad = fall / _kernabnahme.AENDERUNG_RELATIV
    regr_pfad = fall / _kernabnahme.REGRESSION_RELATIV
    kern_gelesen = lies_gehasht(kern_pfad) if kern_pfad.is_file() else None
    kern_fehler = pruefe_kernaenderung(
        kern_pfad, fall,
        text=kern_gelesen.text() if kern_gelesen else None,
        repo_root=repo_root,
    )
    if kern_fehler or kern_gelesen is None:
        return ([f"{_kernabnahme.AENDERUNG_RELATIV}: {f}" for f in kern_fehler]
                or [f"{_kernabnahme.AENDERUNG_RELATIV}: Datei fehlt"]), {}, {}
    regr_gelesen = lies_gehasht(regr_pfad) if regr_pfad.is_file() else None
    regr_fehler = pruefe_kernregression(
        regr_pfad, fall,
        text=regr_gelesen.text() if regr_gelesen else None,
        aenderung=json.loads(kern_gelesen.text()),
    )
    if regr_fehler or regr_gelesen is None:
        return ([f"{_kernabnahme.REGRESSION_RELATIV}: {f}" for f in regr_fehler]
                or [f"{_kernabnahme.REGRESSION_RELATIV}: Datei fehlt"]), {}, {}
    return [], {
        "kernaenderung": kern_gelesen.sha256,
        "regression": regr_gelesen.sha256,
    }, _kernabnahme.ausnahmen_fuer(json.loads(regr_gelesen.text()))


def tbox_belege_pruefen(
    fall: Path, repo_root: Optional[Path]
) -> Tuple[List[str], Dict[str, str]]:
    """Die beiden Belege einer T-Box-Aenderung an ihren festen Orten pruefen.

    Rueckgabe ``(fehler, {rolle: sha256})``. EINE Funktion fuer beide Leser:
    das Zeichnen von A-O1 und die Vorbedingung von A-M4 (Standabnahme, Weg
    a), die dieselben Bytes nachrechnet, statt der Annahme zu glauben.
    """
    aenderung_pfad = fall / _stand.TBOX_AENDERUNG_RELATIV
    aenderung_gelesen = (
        lies_gehasht(aenderung_pfad) if aenderung_pfad.is_file() else None)
    fehler = pruefe_tbox_aenderung(
        aenderung_pfad, fall,
        text=aenderung_gelesen.text() if aenderung_gelesen else None,
        repo_root=repo_root,
    )
    if fehler or aenderung_gelesen is None:
        return [f"den Beleg der T-Box-Aenderung ({_stand.TBOX_AENDERUNG_RELATIV}): "
                + "; ".join(fehler or ["Datei fehlt"])], {}
    stellung_pfad = fall / _stand.TBOX_STELLUNGNAHME_RELATIV
    stellung_gelesen = (
        lies_gehasht(stellung_pfad) if stellung_pfad.is_file() else None)
    fehler = pruefe_stellungnahme_aktuariat(
        stellung_pfad, fall,
        text=stellung_gelesen.text() if stellung_gelesen else None,
        aenderung=json.loads(aenderung_gelesen.text()),
    )
    if fehler or stellung_gelesen is None:
        return [f"die aktuarielle Stellungnahme ({_stand.TBOX_STELLUNGNAHME_RELATIV}): "
                + "; ".join(fehler or ["Datei fehlt"])], {}
    return [], {
        "tbox_aenderung": aenderung_gelesen.sha256,
        "stellungnahme_aktuariat": stellung_gelesen.sha256,
    }


TARIFWERK_AENDERUNG_SCHEMA_VERSION = _tarifwerk.TARIFWERK_AENDERUNG_SCHEMA_VERSION


def pruefe_tarifwerkaenderung(
    pfad: Path, bereich: Path, *, text: str | None = None, repo_root: Path | None = None,
) -> List[str]:
    """Den Aenderungsbeleg des Tarifwerks gegen Code und Git halten (A-T1).

    Erst die Form, dann der GANZE Beleg nachgerechnet
    (``tarifwerk_belegen.nachgerechnet``): Ein Beleg, der nur in sich stimmig
    ist, bezeugt nichts (T24-04) — ein weggelassenes Feld einer Generation,
    ein geschoenter Tarifplan, ein erfundener Commit fallen hier.
    """
    if not pfad.is_file():
        return ["Datei fehlt"]
    try:
        daten = json.loads(text if text is not None else pfad.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"nicht lesbar: {exc}"]
    if not isinstance(daten, dict):
        return ["kein JSON-Objekt"]
    fehler: List[str] = []
    if daten.get("schema_version") != TARIFWERK_AENDERUNG_SCHEMA_VERSION:
        fehler.append(f"schema_version muss {TARIFWERK_AENDERUNG_SCHEMA_VERSION} sein")
    if daten.get("art") != _tarifwerk.ART:
        fehler.append(f"art muss {_tarifwerk.ART!r} sein")
    git_beleg = daten.get("git") if isinstance(daten.get("git"), dict) else None
    if git_beleg is None:
        fehler.append("git fehlt oder ist kein Objekt")
    elif not zweig_ist_aktuell(git_beleg):
        fehler.append("der lebende Stand liegt nicht auf dem zuletzt abgenommenen Stand auf "
                      "(merge_base != referenz_commit)")
    if not (isinstance(daten.get("begruendung"), str) and daten["begruendung"].strip()):
        fehler.append("begruendung fehlt")
    if fehler:
        return fehler
    if repo_root is None:
        return ["der Beleg ist nicht nachrechenbar — --repo-root fehlt"]
    jetzt = git_stand(repo_root)
    if git_beleg.get("aktuell") != jetzt.get("commit"):
        return [f"git.aktuell {str(git_beleg.get('aktuell'))[:12]!r} ist nicht der "
                f"gegenwaertige Commit ({str(jetzt.get('commit'))[:12]!r})"]
    try:
        neu = _tarifwerk.nachgerechnet(repo_root, daten)
    except (_tarifwerkabnahme.TarifwerkFehler, OSError) as exc:
        return [f"der Beleg ist nicht nachrechenbar: {exc}"]
    abweichend = sorted(k for k in set(neu) | set(daten) if neu.get(k) != daten.get(k))
    if abweichend:
        return ["der Beleg ist nicht das Tarifwerk zwischen dem zuletzt abgenommenen Stand "
                f"und dem Arbeitsbaum — abweichend: {abweichend}; neu erzeugen mit: python -m "
                "rechner_pipeline.gates.tarifwerk_belegen --linie|--fall <bereich> --repo-root "
                f"<repo> --von {neu['git']['referenz']} --begruendung <text>"]
    return []


def tarifwerk_belege_pruefen(
    bereich: Path, repo_root: Optional[Path]
) -> Tuple[List[str], Dict[str, str]]:
    """Den Beleg des Tarifwerks am festen Ort pruefen — fuer A-T1 und A-M4."""
    pfad = bereich / _tarifwerkabnahme.AENDERUNG_RELATIV
    gelesen = lies_gehasht(pfad) if pfad.is_file() else None
    fehler = pruefe_tarifwerkaenderung(
        pfad, bereich, text=gelesen.text() if gelesen else None, repo_root=repo_root)
    if fehler or gelesen is None:
        return [f"{_tarifwerkabnahme.AENDERUNG_RELATIV}: " + "; ".join(fehler or ["Datei fehlt"])], {}
    return [], {"tarifwerk_aenderung": gelesen.sha256}


def anfangsbestand_belege_pruefen(bereich: Path) -> Tuple[List[str], Dict[str, str]]:
    """Den Beleg des Anfangsbestands am festen Ort pruefen (A-B3): Form,
    gruene P-B1, innere Ableitungen. Gegen die Ablage haelt den Stand der
    Betrieb beim Binden — das Gate sieht die Ablage nicht (ADR-025)."""
    pfad = bereich / _anfangsbestand.BELEG_RELATIV
    if not pfad.is_file():
        return [f"{_anfangsbestand.BELEG_RELATIV}: Datei fehlt — belegen mit python -m "
                "rechner_pipeline.betrieb.anfangsbestand belegen --stand <daten> --linie "
                f"{bereich} ..."], {}
    gelesen = lies_gehasht(pfad)
    try:
        beleg = gelesen.json()
    except (OSError, ValueError) as exc:
        return [f"{_anfangsbestand.BELEG_RELATIV}: nicht lesbar ({exc})"], {}
    fehler = _anfangsbestand.beleg_fehler(beleg)
    if fehler:
        return [f"{_anfangsbestand.BELEG_RELATIV}: " + "; ".join(fehler[:4])], {}
    return [], {"anfangsbestand": gelesen.sha256}


def _belege_im_fall(gate: str, fall: Path, repo_root: Optional[Path]
                    ) -> Tuple[List[str], Dict[str, str], Dict[str, str]]:
    """Die Belege des Gates am festen Ort, je Gegenstand dieselbe Gestalt —
    im Fall wie im Linienbereich."""
    if gate == "A-K2":
        return kernstand_belege_pruefen(fall, repo_root)
    if gate == "A-T1":
        fehler, shas = tarifwerk_belege_pruefen(fall, repo_root)
        return fehler, shas, {}
    if gate == "A-B3":
        fehler, shas = anfangsbestand_belege_pruefen(fall)
        return fehler, shas, {}
    fehler, shas = tbox_belege_pruefen(fall, repo_root)
    return fehler, shas, {}


def _anzeige_mit_ausnahmen(text: str, ausnahmen: Mapping[str, str]) -> str:
    """Die Anzeige eines Wegs, und woertlich, was die Abnahme NICHT deckt."""
    if ausnahmen.get("regression"):
        return f"{text}; {_kernabnahme.ANZEIGE_REGRESSION}"
    return text


def standabnahme_pruefen(
    gegenstand: "_standabnahme.Gegenstand",
    *,
    fall: Path,
    repo_root: Optional[Path],
    verzeichnis: Path,
    schluesselring: Mapping[str, bytes],
    systemstand: Mapping[str, str],
    ordnung: Optional[dict],
    fall_json_sha256: Optional[str],
    linie: Optional[list] = None,
) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, object]]]:
    """EINE Regel fuer jeden Gegenstand, den A-M4 verlangt (models.standabnahme).

    Rueckgabe ``(meldung, pin_sha256, eintrag)``: ``meldung`` ist None, wenn
    der Stand, auf dem der Fall laeuft, abgenommen ist; ``pin_sha256`` ist
    der Beleg, den A-M4 als Pflichtrolle pinnt; ``eintrag`` steht im
    A-M4-Snapshot unter ``standabnahmen``.

    (a) Hat der Fall eine Kette des Gates, gilt nur sie: eindeutige,
        signierte ANNAHME auf diesem Scope- und Systemstand, gezeichnet von
        einer berechtigten Rolle (Rollenregel), ihre Belege am festen Ort
        und gegen den lebenden Code nachgerechnet, ihr ``stand`` == der
        lebende. Eine Ablehnung im Fall laesst sich nicht umgehen.
    (b) Sonst ein Verweis am festen Ort: die Kopie eines FRUEHER
        angenommenen Snapshots — der Erstabnahme der Linie oder eines
        frueheren Falls —, Signatur ueber den Ring, dieselbe Rollenregel,
        ``stand`` == der lebende — "keine Aenderung".

    ``linie``: die Glieder der Ordnungslinie (ADR-025). Mit ihr gilt fuer
    die Rollenregel die Ordnung, unter der der Snapshot gezeichnet wurde.
    """
    gate, titel = gegenstand.gate, gegenstand.titel
    stand = _stand.lebender_stand(gate, repo_root)
    if stand is None:
        return (f"der {titel} ist nicht bestimmbar (--repo-root fehlt?)", None, None)
    kette, spitzen, ketten_fehler = _lade_snapshot_kette(
        verzeichnis, gegenstand.gate, fall, schluesselring, systemstand)
    if ketten_fehler:
        return (f"{gate}-Snapshot-Vertrag verletzt: " + "; ".join(ketten_fehler[:4]),
                None, None)
    if kette:
        spitze = kette[spitzen[0]][1] if len(spitzen) == 1 else None
        if not (
            spitze is not None
            and spitze["entscheid"] == "angenommen"
            and spitze["artefakt_hashes"].get("fall.json") == fall_json_sha256
            and spitze["system"] == systemstand
        ):
            return (f"keine eindeutige, signierte {gate}-ANNAHME des {titel}s auf "
                    "aktuellem Scope- und Systemstand im Fall — eine Kette im Fall "
                    "geht jedem Verweis vor", None, None)
        _, zf = zeichnende_rolle_fehler(spitze, gegenstand.gate, ordnung, linie=linie)
        if zf:
            return (f"die geltende {gate}-Annahme wurde von einem unberechtigten "
                    f"Schluessel gezeichnet -- {zf}", None, None)
        belegfehler, shas, ausnahmen = _belege_im_fall(gate, fall, repo_root)
        gepinnt = spitze.get("pflichtbelege") or {}
        belegfehler += [
            f"{rolle}: am festen Ort liegt nicht die Fassung, die {gate} pinnt"
            for rolle, sha in shas.items() if gepinnt.get(rolle) != [sha]]
        if not belegfehler and (spitze.get("ausnahmen") or {}) != ausnahmen:
            belegfehler.append(
                f"die {gate}-Annahme fuehrt die Ausnahmen {spitze.get('ausnahmen')!r}, "
                f"die Belege ergeben {ausnahmen!r}")
        if not belegfehler and spitze.get("stand") != stand:
            belegfehler.append(
                f"der abgenommene Stand {spitze.get('stand')!r} ist nicht der "
                f"lebende {stand!r}")
        if belegfehler:
            return (f"die Belege des {titel}s tragen die geltende {gate}-Annahme "
                    "nicht: " + "; ".join(belegfehler[:4]), None, None)
        sha = spitze["snapshot_sha256"]
        return None, sha, {
            "gate": gate, "weg": _standabnahme.ABNAHME_IM_FALL,
            "snapshot_sha256": sha, "stand": dict(stand), "ausnahmen": dict(ausnahmen),
            "anzeige": _anzeige_mit_ausnahmen(
                _standabnahme.anzeige_im_fall(gate, sha), ausnahmen),
        }
    verweis_pfad = fall / gegenstand.verweis_relativ
    if verweis_pfad.is_file():
        gelesen = lies_gehasht(verweis_pfad)
        try:
            verweis = gelesen.json()
        except (OSError, ValueError) as exc:
            return (f"{gegenstand.verweis_relativ} unlesbar: {exc}", None, None)
        fehler = _stand.verweis_fehler(verweis, gegenstand, stand)
        if not fehler:
            snap = verweis["snapshot"]
            fehler += _pruefe_freigabe(snap, schluesselring)
            _, zf = zeichnende_rolle_fehler(snap, gegenstand.gate, ordnung, linie=linie)
            if zf:
                fehler.append(f"der fruehere {gate}-Snapshot wurde von einem "
                              f"unberechtigten Schluessel gezeichnet -- {zf}")
        if fehler:
            return (f"der Verweis {gegenstand.verweis_relativ} belegt keine "
                    "unveraenderte Abnahme: " + "; ".join(fehler[:4]), None, None)
        snap = verweis["snapshot"]
        ausnahmen = dict(snap.get("ausnahmen") or {})
        return None, gelesen.sha256, {
            "gate": gate, "weg": _standabnahme.KEINE_AENDERUNG,
            "snapshot_sha256": snap["snapshot_sha256"], "herkunft": verweis["herkunft"],
            "stand": dict(stand), "ausnahmen": ausnahmen,
            "anzeige": _anzeige_mit_ausnahmen(_standabnahme.anzeige_keine_aenderung(
                snap["snapshot_sha256"], verweis["herkunft"]), ausnahmen),
        }
    vorlage = {
        "A-K2": (f"python -m rechner_pipeline.gates.kernstand_belegen --fall {fall} "
                 "--repo-root <repo> --von <zuletzt abgenommener Kernstand> --begruendung <text>"),
        "A-O1": (f"python -m rechner_pipeline.gates.stand_belegen tbox --fall {fall} "
                 "--vorher-linie <linie> --repo-root <repo> --artefakt <vermerk> "
                 "--begruendung <text> und die "
                 "aktuarielle Stellungnahme"),
        "A-T1": (f"python -m rechner_pipeline.gates.tarifwerk_belegen --fall {fall} "
                 "--repo-root <repo> --von <zuletzt abgenommener Stand> --begruendung <text>"),
    }[gate]
    wege = (f"bei unveraendertem Stand auf die geltende Abnahme verweisen: python -m "
            f"rechner_pipeline.gates.stand_belegen verweisen --fall {fall} --gate {gate} "
            f"--linie <linie> --repo-root <repo> (Erstabnahme, ADR-025; oder --snapshot "
            f"<frueherer {gate}-Snapshot>); aendert der Fall den {titel}, vorlegen mit "
            f"{vorlage}, dann {gate} im Fall zeichnen (gates.gate_entscheid --gate {gate})")
    return (f"der {titel}, auf dem der Fall laeuft, ist nicht abgenommen (ADR-018, "
            f"Nachtrag 2026-10-01; ADR-025) — {wege}", None, None)


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
    scope = snapshot.get("fall_scope")
    try:
        erwartete_rollen = belegrollen(gate, scope)
    except BelegrollenFehler as exc:
        return [f"{gate}-Scope ist ungueltig: {exc}"]
    # Die Mechanik steht in models (p9_semantik_fehler) — dieselbe
    # Funktion und derselbe Vertrag (models.belegrollen), die der
    # Betriebseingang liest (T26-03, Weg 2). Zweimal geschrieben waeren
    # es zwei Regeln.
    return p9_semantik_fehler(snapshot, erwartete_rollen=erwartete_rollen)


def _pruefe_snapshot_graph(
    snapshots: Mapping[str, Tuple[Path, dict]],
) -> Tuple[List[str], List[str]]:
    """Check predecessor existence, cycles and the unique current tip.

    Die Regel wohnt in models.snapshot_kette — der Betriebseingang liest
    dieselbe (T27-05); hier wird nur der Dateiname fuer die Meldungen
    beigesteuert.
    """
    from rechner_pipeline.models.snapshot_kette import pruefe_snapshot_graph

    return pruefe_snapshot_graph(
        {sha: daten for sha, (_pfad, daten) in snapshots.items()},
        {sha: pfad.name for sha, (pfad, _daten) in snapshots.items()},
    )


#: Was A-B2 ueber die Betriebszeichnung der Zugangsprobe sagt (Block F,
#: Nachbesserung, Pruefer-Befund 7).
BETRIEBSSIGNATUR_NICHT_VERIFIZIERT = (
    "nicht verifiziert — das Gate haelt den Betriebsschluessel nicht; es prueft "
    "Form und Rolle der Betriebszeichnung, die Signatur rechnet die Registrierung "
    "(betrieb.uebernahme) nach")


def _lade_snapshot_kette(
    verzeichnis: Path,
    gate: str,
    fall: Path,
    schluesselring: Mapping[str, bytes],
    aktueller_systemstand: Mapping[str, str],
    *,
    gelesen: Optional[Dict[Path, str]] = None,
) -> Tuple[Dict[str, Tuple[Path, dict]], List[str], List[str]]:
    """Validate schema, content address, signature and the complete DAG.

    ``gelesen``: nimmt je gelesener Datei den SHA-256 genau der Bytes auf, die
    geprueft wurden — fuer Artefakthashes ohne zweite Lesung (T23-01)."""
    snapshots: Dict[str, Tuple[Path, dict]] = {}
    fehler: List[str] = []
    for pfad in sorted(verzeichnis.glob(f"{gate}-*.json")):
        try:
            roh = pfad.read_bytes()
            daten = json.loads(roh.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            fehler.append(f"{pfad.name}: nicht als JSON lesbar: {exc}")
            continue
        if gelesen is not None:
            gelesen[pfad] = hashlib.sha256(roh).hexdigest()
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
    hashes["abnahmebericht"] = ledger_gelesen.sha256
    if bekannt is not None:
        bekannt[str(ledger_pfad.relative_to(fall))] = ledger_gelesen.sha256
    return hashes, []


def abbruch_im_fall(fall: Path) -> Optional[str]:
    """Ist der Fall abgebrochen? Der Name der A-M5-Datei, die das sagt, oder None.

    STRUKTURELL und fail-closed (ADR-026): Jede ``A-M5-*.json`` unter
    ``entscheide/``, die nicht nachweislich eine Ablehnung ist, sperrt den
    Fall — eine Annahme sowieso, eine unlesbare oder gefaelschte Datei auch.
    Die Signatur wird hier nicht verlangt: Die Sperre ist die sichere
    Richtung, und wer ``entscheide/`` beschreiben kann, kann den Fall ohnehin
    unbrauchbar machen. Freigegeben wird nie etwas auf diesem Weg.
    """
    verzeichnis = entscheide_verzeichnis(fall)
    for pfad in sorted(verzeichnis.glob(f"{ABBRUCH_GATE}-*.json")) if verzeichnis.is_dir() else []:
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return pfad.name
        if not (isinstance(daten, dict) and not P9Snapshot.validate_payload(daten)
                and daten.get("entscheid") == "abgelehnt"):
            return pfad.name
    return None


def fallauftrag_pruefen(
    fall: Path,
    *,
    schluesselring: Mapping[str, bytes],
    systemstand: Mapping[str, str],
    ordnung: Optional[dict],
    linie: Optional[list],
    bekannt: Optional[Dict[str, str]] = None,
) -> Tuple[Optional[dict], Optional[str]]:
    """Die EINE Stelle (ADR-026): der geltende Fallauftrag — oder warum keiner gilt.

    ``bekannt``: Hashes der Dateien, die dieser Lauf schon gelesen hat; was
    hier gelesen wird (Eingang, Manifest, die A-M6-Snapshots), kommt dazu —
    der Snapshot bezeugt dieselben Bytes, die geprueft wurden (T23-01).

    Jeder Abnahmepunkt eines Falls ausser dem Auftrag selbst setzt ihn voraus
    (A-Q1, A-O1/A-K2/A-T1 im Fall, A-M1 bis A-M5, A-B1, A-B2). Rueckgabe
    ``(spitze, None)`` oder ``(None, meldung)``. Verlangt wird:

    * eine eindeutige, signierte ANNAHME von A-M6 im Fall (derselbe
      Kettenleser wie fuer jedes Gate: Schema, Selbstadressierung, Graph,
      Signatur ueber den Ring);
    * gebunden an die Lieferung: ``eingang.json`` und ``fall.json`` sind die
      Bytes, die der Auftrag pinnt (dieselbe Bindung, die A-M4 an A-Q1 haelt)
      — aendert sich der Eingang, gilt der Auftrag nicht mehr;
    * gezeichnet von einer Rolle, der die Ordnung A-M6 gibt — die Rollenregel
      (``models.zeichnung.zeichnende_rolle_fehler``), mit Linie gegen die
      Ordnung, unter der gezeichnet wurde.
    """
    bekannt = bekannt if bekannt is not None else {}
    gelesen: Dict[Path, str] = {}
    kette, spitzen, fehler = _lade_snapshot_kette(
        entscheide_verzeichnis(fall), AUFTRAG_GATE, fall, schluesselring, systemstand,
        gelesen=gelesen)
    for pfad, sha in gelesen.items():
        bekannt[str(pfad.relative_to(fall))] = sha
    ausweg = (f"Ausweg: den Fall beauftragen — Vorlage mit python -m "
              f"rechner_pipeline.gates.fall_belegen auftrag --fall {fall} ..., ansehen, dann "
              f"zeichnet der Vorstand: python -m rechner_pipeline.gates.gate_entscheid --fall "
              f"{fall} --gate {AUFTRAG_GATE} --entscheid angenommen ... (ADR-026)")
    if fehler:
        return None, (f"{AUFTRAG_GATE}-Snapshot-Vertrag verletzt: " + "; ".join(fehler[:4]))
    if not kette:
        return None, ("der Fall hat keinen Fallauftrag — jeder Abnahmepunkt eines Falls setzt "
                      f"den gezeichneten Auftrag voraus; ein Fall, den niemand beauftragt hat, "
                      f"wird nicht gefuehrt. {ausweg}")
    spitze = kette[spitzen[0]][1] if len(spitzen) == 1 else None
    if spitze is None or spitze.get("entscheid") != "angenommen":
        return None, (f"der geltende Fallauftrag ist keine eindeutige Annahme (Spitzen "
                      f"{[s[:16] for s in spitzen]}) — ohne geltenden Auftrag keine Abnahme. "
                      f"{ausweg}")
    for name in ("eingang.json", "fall.json"):
        if name not in bekannt and (fall / name).is_file():
            bekannt[name] = lies_gehasht(fall / name).sha256
    jetzt = {name: bekannt.get(name) for name in ("eingang.json", "fall.json")}
    abweichend = sorted(name for name, sha in jetzt.items()
                        if spitze["artefakt_hashes"].get(name) != sha)
    if abweichend or spitze["auftrag"]["lieferung"]["eingang_sha256"] != jetzt["eingang.json"]:
        return None, (f"der Fallauftrag {spitze['snapshot_sha256'][:16]}… gilt nicht mehr: "
                      f"{', '.join(abweichend) or 'eingang.json'} ist nicht die Fassung, die er "
                      "bindet — die Lieferung hat sich geaendert, beauftragt war eine andere. "
                      f"{ausweg}")
    _, zf = zeichnende_rolle_fehler(spitze, AUFTRAG_GATE, ordnung, linie=linie)
    if zf:
        return None, (f"der geltende Fallauftrag wurde von einem unberechtigten Schluessel "
                      f"gezeichnet -- {zf}")
    return spitze, None


def _lebenslauf_vorlage(
    gate: str, fall: Path, *, ordnung: Optional[dict], linie_pfad: Optional[Path],
    systemstand: Mapping[str, str],
    schluesselring: Mapping[str, bytes],
) -> Tuple[Optional[dict], Optional[str], List[str]]:
    """Die Vorlage von A-M6 bzw. A-M5 am festen Ort, NACHGERECHNET gegen Fall,
    Eingang, Ordnung und Linie: ``(inhalt, vorlage_sha256, fehler)``."""
    from rechner_pipeline.gates import fall_belegen

    relativ = _fallauftrag.AUFTRAG_RELATIV if gate == AUFTRAG_GATE else _fallauftrag.ABBRUCH_RELATIV
    pfad = fall / relativ
    kommando = (f"python -m rechner_pipeline.gates.fall_belegen "
                f"{'auftrag' if gate == AUFTRAG_GATE else 'abbruch'} --fall {fall} ...")
    if not pfad.is_file():
        return None, None, [f"die Vorlage {relativ} fehlt — erzeugen mit: {kommando}"]
    gelesen = lies_gehasht(pfad)
    try:
        beleg = gelesen.json()
    except (OSError, ValueError) as exc:
        return None, None, [f"{relativ} unlesbar: {exc}"]
    if gate == AUFTRAG_GATE:
        fehler = _fallauftrag.auftrag_fehler(beleg)
        if fehler:
            return None, None, fehler
        if ordnung is None:
            return None, None, ["ohne Zeichnungsordnung ist nicht pruefbar, welche Rollen "
                                "simuliert handeln und wem welcher Schluessel gehoert"]
        try:
            soll = {
                "fall": fall_belegen.fall_angaben(fall),
                "lieferung": fall_belegen.lieferung(fall),
                "zielsystem": fall_belegen.zielsystem(linie_pfad),
            }
        except (fall_mod.FallFehler, OSError, ValueError, KeyError) as exc:
            return None, None, [f"die Vorlage ist nicht nachrechenbar: {exc}"]
        fehler = [f"{feld}: die Vorlage sagt {beleg[feld]!r}, nachgerechnet {wert!r}"
                  for feld, wert in soll.items() if beleg[feld] != wert]
        pl = beleg["programmleitung"]
        besetzt = {e.get("schluessel_sha256"): r for r, e in ordnung["rollen"].items()}
        if pl["schluessel_sha256"] in besetzt:
            fehler.append(f"der Schluessel der Programmleitung gehoert in der Ordnung der Rolle "
                          f"{besetzt[pl['schluessel_sha256']]!r} — die Trennung der Operatoren "
                          "waere nur behauptet")
        soll_mandate = fall_belegen.mandatsrollen(ordnung, pl["schluesselklasse"])
        if sorted(beleg["mandate"]) != soll_mandate:
            fehler.append(f"die Vorlage nennt Mandate fuer {sorted(beleg['mandate'])}, simuliert "
                          f"handeln laut Ordnung {soll_mandate}")
        return (None, None, fehler) if fehler else (beleg, gelesen.sha256, [])
    fehler = _fallauftrag.abbruch_fehler(beleg)
    if fehler:
        return None, None, fehler
    try:
        # Der Auftrag, auf dem der Abbruch steht, haelt main gegen den
        # geltenden (fallauftrag_pruefen); hier die uebrigen Angaben.
        soll_abbruch = {
            "fall": fall.name,
            "gezeichnet": fall_belegen.gezeichnet(fall),
            "stand": {"eingang_sha256": _sha256_datei(fall / "eingang.json"),
                      "system": dict(systemstand)},
        }
    except (fall_belegen.FallBelegFehler, OSError) as exc:
        return None, None, [f"die Vorlage ist nicht nachrechenbar: {exc}"]
    fehler = [f"{feld}: die Vorlage sagt {str(beleg[feld])[:80]!r}, nachgerechnet "
              f"{str(wert)[:80]!r} — Vorlage neu erzeugen: {kommando}"
              for feld, wert in soll_abbruch.items() if beleg[feld] != wert]
    am4, am4_spitzen, am4_fehler = _lade_snapshot_kette(
        entscheide_verzeichnis(fall), "A-M4", fall, schluesselring, systemstand)
    if am4_fehler:
        # Fail-closed: Wer die A-M4-Kette nicht lesen kann, weiss nicht, ob die
        # Migration abgenommen ist.
        fehler.append("die A-M4-Kette ist nicht lesbar — ob die Migration abgenommen ist, "
                      "bleibt offen: " + "; ".join(am4_fehler[:2]))
    elif len(am4_spitzen) == 1 and am4[am4_spitzen[0]][1].get("entscheid") == "angenommen":
        fehler.append("die Migration ist abgenommen (geltende A-M4-Annahme "
                      f"{am4_spitzen[0][:16]}…) — ein Abbruch danach widerriefe die Abnahme. "
                      "Ausweg: A-M4 ablehnen (neue Spitze der Kette), dann abbrechen")
    return (None, None, fehler) if fehler else (beleg, gelesen.sha256, [])


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
    kandidaten: List[Path] = [fall / "eingang.json", fall / "fall.json",
                              fall / _standabnahme.LINIE_MARKER]
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
            # Der Rest eines hart abgebrochenen atomaren Schreibens (auch der
            # Hardlink-Zwilling eines eingehaengten Snapshots) ist kein
            # Artefakt und kein Beleg (Angriffsrunde C, RC07): Mit ihm waere
            # die Wiederholung desselben Entscheids nicht mehr idempotent,
            # und jeder weitere Snapshot des Falls nennte ihn.
            if ist_schreibrest(pfad.name):
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
    parser.add_argument(
        "--linie", default=None,
        help="Linienbereich (ADR-025; Pflicht seit dem Nachtrag 2026-10-01). Allein: die "
             "Abnahme des Zielsystems ausserhalb eines Falls (A-K2, A-O1, A-T1, A-B3). "
             "Mit --fall: die Linie, deren Ordnungslinie gilt — gezeichnet wird unter "
             "ihrer Spitze, gelesen unter der Ordnung, unter der eine Abnahme gezeichnet "
             "wurde.")
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

    # Der Bereich, in dem gezeichnet wird: ein Fall, oder — mit --linie allein —
    # der Linienbereich der Erstabnahme (ADR-025). Er verhaelt sich wie ein
    # Fall (entscheide/, abgeleitet/, dieselbe Kette, derselbe Schutz), hat
    # aber keinen Eingang einer Migration.
    linie_pfad = Path(args.linie).resolve() if args.linie else None
    linie_modus = linie_pfad is not None and not args.fall
    fall = (Path(args.fall).resolve() if args.fall else linie_pfad)
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
        ("--fall oder --linie", fall), ("--gate", args.gate),
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
    if linie_modus:
        if _standabnahme.bereich_art(fall) != "linie":
            return _usage(
                f"kein Linienbereich: {fall} (anlegen mit: python -m "
                f"rechner_pipeline.gates.stand_belegen linie --linie {fall})")
        if args.gate not in _standabnahme.LINIEN_GATES:
            return _usage(
                f"{args.gate} ist im Linienbereich nicht zeichenbar — dort nur "
                f"{', '.join(_standabnahme.LINIEN_GATES)} (ADR-025)")
    elif not (fall / "eingang.json").is_file():
        return _usage(
            f"kein Fall-Arbeitsbereich: {fall} (anlegen mit: python -m "
            f"rechner_pipeline.fall anlegen --fall {fall}, dann je Quelle "
            f"python -m rechner_pipeline.fall registrieren --fall {fall} "
            "--datei <quelle>)"
        )
    elif args.gate in _standabnahme.NUR_LINIE:
        return _usage(
            f"{args.gate} gehoert keinem Fall — gezeichnet wird er im Linienbereich "
            "(--linie <linie> ohne --fall, ADR-025)")
    # Die Linie ist Pflicht (ADR-025, Nachtrag 2026-10-01): Kein Gate wird
    # ohne die Versionslinie der Ordnung gezeichnet, und keine Vorbedingung
    # wird ohne sie gelesen. Eine Wurzel, die man weglassen kann, ist keine.
    if linie_pfad is None:
        return _usage(
            "ohne --linie wird nicht gezeichnet: gezeichnet wird nur unter der Spitze der "
            "Versionslinie der Zeichnungsordnung, und jede Vorbedingung wird gegen den Stand "
            "der Ordnung gelesen, unter dem sie gezeichnet wurde (ADR-025, Nachtrag "
            "2026-10-01). Ausweg: Linienbereich anlegen (python -m "
            "rechner_pipeline.gates.stand_belegen linie --linie linie), die Ordnung eintragen "
            "(... stand_belegen ordnung --linie linie --ordnung <ordnung> --vorgaenger keiner) "
            "und --linie linie angeben — Bedienfolge in ADR-025")
    if _standabnahme.bereich_art(linie_pfad) != "linie":
        return _usage(f"--linie {linie_pfad}: kein Linienbereich")

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
    # Was die A-K2-Zeichnung NICHT deckt (ADR-018, Nachtrag 2026-10-01),
    # aus dem Regressionsbeleg abgeleitet; und je Gegenstand, auf welchem
    # Weg der Stand abgenommen ist, auf dem A-M4 gruendet.
    ak2_ausnahmen: Dict[str, str] = {}
    am4_standabnahmen: Dict[str, object] = {}
    if args.gate in GATES_MIT_PFLICHTBELEGEN and linie_modus:
        # Der Linienbereich hat keinen Fall-Scope; sein Scope ist die Linie,
        # seine Kennzeichnung steht an der Stelle von fall.json (ADR-025).
        marker = lies_gehasht(fall / _standabnahme.LINIE_MARKER)
        fall_scope, fall_json_sha256 = _standabnahme.LINIE_SCOPE, marker.sha256
        bekannte_hashes[_standabnahme.LINIE_MARKER] = marker.sha256
    elif args.gate in GATES_MIT_PFLICHTBELEGEN:
        try:
            fall_scope, fall_json_sha256 = fall_mod.lade_scope_gehasht(fall)
            bekannte_hashes["fall.json"] = fall_json_sha256
        except (fall_mod.FallFehler, BelegrollenFehler) as exc:
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

    # Die Versionslinie der Zeichnungsordnung (ADR-025; Pflicht seit dem
    # Nachtrag 2026-10-01): Gezeichnet wird nur unter ihrer Spitze, und wer eine
    # Abnahme liest, um darauf zu gruenden, haelt sie gegen die Ordnung, unter
    # der sie gezeichnet wurde. Eine Ablehnung zeichnet nichts und liest nichts,
    # worauf sie gruendet; sie geht auch auf einer Linie ohne Glied.
    ordnungsglieder, linie_fehler = _ordnungslinie.lade_linie(linie_pfad)
    if linie_fehler:
        return _sperre("ordnungslinie", "Entscheid verweigert: die Ordnungslinie ist "
                       "verletzt: " + "; ".join(linie_fehler[:4]))
    if not ordnungsglieder and args.entscheid == "angenommen":
        return _sperre(
            "ordnungslinie",
            "Annahme verweigert: die Linie hat noch keine Ordnungslinie — zuerst "
            "die Ordnung eintragen: python -m rechner_pipeline.gates.stand_belegen "
            f"ordnung --linie {linie_pfad} --ordnung <ordnung> --vorgaenger keiner "
            "(ADR-025)")

    # Der Lebenslauf des Falls (ADR-026). Nach dem gezeichneten Abbruch ist im
    # Fall nichts mehr zu entscheiden — keine Annahme, keine Ablehnung, auch
    # kein zweiter Abbruch. Und jede Annahme eines Falls ausser dem Auftrag
    # selbst setzt den geltenden Fallauftrag voraus: EINE Stelle fuer alle
    # Gates (fallauftrag_pruefen).
    auftrag_spitze: Optional[dict] = None
    lebenslauf_inhalt: Optional[dict] = None
    if not linie_modus:
        abgebrochen = abbruch_im_fall(fall)
        if abgebrochen is not None:
            return _sperre(
                "fallabbruch",
                f"Entscheid verweigert: der Fall ist abgebrochen ({abgebrochen}) — er endet "
                "dort, ohne Abnahme; danach ist im Fall nichts mehr zeichenbar (ADR-026). "
                "Ausweg: ein neuer Fall mit eigenem Auftrag")
    if args.entscheid == "angenommen" and args.gate in LEBENSLAUF_GATES:
        # Auftrag und Abbruch stehen vor bzw. neben der A-Box: Sie binden die
        # Lieferung (der Eingang muss sein Register erfuellen) und ihre
        # Vorlage, nachgerechnet gegen Fall, Ordnung und Linie.
        eingangs_fehler = fall_mod.pruefen(fall)
        if eingangs_fehler:
            return _sperre("eingang", "Annahme verweigert — Eingang verletzt das Register: "
                           + "; ".join(eingangs_fehler[:5]))
        sf = _schluessel_laden()
        if sf:
            return _sperre("freigabe", "Annahme verweigert: externe Freigabeschluessel "
                           "ungueltig: " + "; ".join(sf[:5]))
        lebenslauf_inhalt, vorlage_sha, vorlage_fehler = _lebenslauf_vorlage(
            args.gate, fall, ordnung=zeichnungsordnung, linie_pfad=linie_pfad,
            systemstand=entscheid_systemstand,
            schluesselring=schluesselring)
        if vorlage_fehler:
            return _sperre("vorbedingung", f"Annahme verweigert: {args.gate} braucht seine "
                           "Vorlage: " + "; ".join(vorlage_fehler[:5]))
        rolle_der_vorlage = "fallauftrag" if args.gate == AUFTRAG_GATE else "fallabbruch"
        pflichtbelege[rolle_der_vorlage] = [str(vorlage_sha)]
        bekannte_hashes["eingang.json"] = _sha256_datei(fall / "eingang.json")
    # Annahme-Sperre: eine Annahme setzt einen integeren Fall und
    # endgueltige Entscheidungen voraus — sonst wuerde ein ungeloester
    # Quellen-Widerspruch oder der Arbeitsstand eines Agenten still zur
    # abgenommenen Wahrheit (P2/P4). Die A-Box ist dafuer PFLICHT: eine
    # Sperre, die per Dateiloeschung abschaltbar waere, ist keine.
    if args.entscheid == "angenommen" and args.gate == "A-O1":
        # Eine Version, ein Vokabular (ADR-024, dritter Nachtrag) — EINE
        # Stelle fuer beide Wege (Linienbereich und Fall). Das Gate rechnet
        # aus den Ketten der Bereiche und dem lebenden Code; dem Feld
        # ``vorher`` des Belegs glaubt es dafuer nichts.
        regel = _stand.tbox_vokabular_fehler([fall] if linie_modus else [fall, linie_pfad])
        if regel:
            return _sperre("vorbedingung", "Annahme verweigert: " + "; ".join(regel[:3]))
    if args.entscheid == "angenommen" and linie_modus:
        # Der Linienbereich hat weder Eingang noch A-Box: Seine Abnahmen
        # stuetzen sich allein auf ihre Belege am festen Ort, nachgerechnet
        # gegen Code bzw. Beleg — derselbe Pruefer wie im Fall.
        wurzel = Path(args.repo_root).resolve() if args.repo_root else None
        belegfehler, belegshas, ak2_ausnahmen = _belege_im_fall(args.gate, fall, wurzel)
        if belegfehler:
            return _sperre("vorbedingung",
                           f"Annahme verweigert: {args.gate} braucht seine Belege: "
                           + "; ".join(belegfehler[:5]))
        for rolle, sha in belegshas.items():
            pflichtbelege[rolle] = [sha]
        erwartete_rollen = belegrollen(args.gate, _standabnahme.LINIE_SCOPE)
        if set(pflichtbelege) != set(erwartete_rollen):
            return _sperre("vorbedingung",
                           f"Annahme verweigert: Pflichtbelege fehlen="
                           f"{sorted(set(erwartete_rollen) - set(pflichtbelege))}")
        pflichtbelege = {rolle: pflichtbelege[rolle] for rolle in erwartete_rollen}
    if args.entscheid == "angenommen" and not linie_modus and args.gate not in LEBENSLAUF_GATES:
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
            # T-Box-Aenderung (Review T22-02; Entscheid 2026-09-16: zweiter
            # Beleg ist die aktuarielle Stellungnahme). Dieselbe Pruefung
            # haelt A-M4 beim Lesen der A-O1-Annahme (tbox_belege_pruefen).
            wurzel = Path(args.repo_root).resolve() if args.repo_root else None
            tbox_fehler, tbox_shas = tbox_belege_pruefen(fall, wurzel)
            if tbox_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-O1 braucht " + "; ".join(tbox_fehler[:5]),
                )
            for rolle, sha in tbox_shas.items():
                pflichtbelege[rolle] = [sha]

        if args.gate == "A-K2":
            # Kernstand (Entscheid des Maintainers 2026-09-16, formell
            # eingepflegt 2026-10-01): zwei Belege an festen Orten, wie bei
            # A-O1 — kein CLI-Flag, damit der Beleg nicht dorthin zeigen
            # kann, wo es gerade passt. Dieselbe Pruefung haelt A-M4 beim
            # Lesen der A-K2-Annahme (kernstand_belege_pruefen).
            wurzel = Path(args.repo_root).resolve() if args.repo_root else None
            kern_fehler, kern_shas, ak2_ausnahmen = kernstand_belege_pruefen(fall, wurzel)
            if kern_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: A-K2 braucht die Belege des Kernstands: "
                    + "; ".join(kern_fehler[:5])
                    + f" — Belege erzeugen mit: {_kernstand_kommando(fall, args.repo_root)}",
                )
            for rolle, sha in kern_shas.items():
                pflichtbelege[rolle] = [sha]

        if args.gate == "A-T1":
            # Tarifwerk (ADR-025): eine Aenderung, die der Fall erzwingt, zeichnet
            # mensch/aktuariat im Fall (Weg a) — derselbe Beleg und Pruefer wie
            # in der Linie; dieselbe Pruefung haelt A-M4 beim Lesen.
            wurzel = Path(args.repo_root).resolve() if args.repo_root else None
            tw_fehler, tw_shas = tarifwerk_belege_pruefen(fall, wurzel)
            if tw_fehler:
                return _sperre("vorbedingung",
                               "Annahme verweigert: A-T1 braucht den Beleg des Tarifwerks: "
                               + "; ".join(tw_fehler[:5]))
            for rolle, sha in tw_shas.items():
                pflichtbelege[rolle] = [sha]

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

        if args.gate == "A-B2":
            # Zugangsabnahme (ADR-022, Entscheid des Maintainers 2026-09-30):
            # Der Betrieb nimmt den Zugang eines abgenommenen Bestands in die
            # produktive Ablage ab. Drei Pflichtbelege, jeder mit eigener
            # Aussage — die Zugangsprobe (die Rechnung), der A-M4-Snapshot
            # (was abgenommen wurde), der Eingang (was eintreten soll). Der
            # Beleg der Probe liegt an einem FESTEN Ort im Fall, wie bei A-O1
            # und A-K2: kein Flag, das dorthin zeigt, wo es gerade passt.
            # Die Annahme RECHNET das Urteil der Probe nach, sie glaubt es
            # nicht; den Stand der Ablage bindet sie ueber den Beleg, und die
            # Registrierung haelt ihn gegen die Ablage, in die sie schreibt.
            from rechner_pipeline.models import zugangsprobe as zp_mod

            probe_pfad = fall / zp_mod.BELEG_RELATIV
            probe_kommando = (
                "python -m rechner_pipeline.betrieb.zugangsprobe --stand <ablage> "
                f"--fall {fall} --stichtag <iso> --schluessel <betriebsschluessel> "
                "--zeichnungsordnung <ordnung> --freigabe-schluessel <schluessel>")
            if not probe_pfad.is_file():
                return _sperre(
                    "vorbedingung",
                    f"Annahme verweigert: A-B2 braucht den Beleg der Zugangsprobe "
                    f"({zp_mod.BELEG_RELATIV} fehlt) — fahren mit: {probe_kommando}",
                )
            probe_gelesen = lies_gehasht(probe_pfad)
            try:
                probe = probe_gelesen.json()
            except (OSError, ValueError) as exc:
                return _sperre("vorbedingung",
                               f"Annahme verweigert: Zugangsprobe unlesbar: {exc}")
            probe_fehler = zp_mod.beleg_fehler(probe, ordnung=zeichnungsordnung)
            if isinstance(probe, dict) and probe.get("fall") != fall.name:
                probe_fehler.append(
                    f"die Probe gehoert zum Fall {probe.get('fall')!r}, nicht {fall.name!r}")
            if probe_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: der Beleg der Zugangsprobe verletzt seinen "
                    "Vertrag: " + "; ".join(probe_fehler[:5])
                    + f" — Probe neu fahren: {probe_kommando}",
                )
            if probe.get("bestanden") is not True:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: die Zugangsprobe ist nicht bestanden — der "
                    "Zugang bewirkt in der Ablage nicht, was abgenommen wurde "
                    "(Ablehnung bleibt moeglich)",
                )
            # Die Probe muss auf der GELTENDEN, angenommenen Migrationsabnahme
            # gelaufen sein — derselbe Kettenleser wie fuer jedes Gate.
            schluessel_fehler_ab2 = _schluessel_laden()
            if schluessel_fehler_ab2:
                return _sperre(
                    "freigabe",
                    "Entscheid verweigert: externe Freigabeschluessel ungueltig: "
                    + "; ".join(schluessel_fehler_ab2[:5]),
                )
            am4_kette, am4_spitzen, am4_fehler = _lade_snapshot_kette(
                entscheide_verzeichnis(fall), "A-M4", fall, schluesselring,
                entscheid_systemstand)
            am4_sha = probe["am4_snapshot_sha256"]
            if am4_fehler or am4_spitzen != [am4_sha] or (
                    am4_kette[am4_sha][1].get("entscheid") != "angenommen"):
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: die Zugangsprobe lief auf dem A-M4-Snapshot "
                    f"{am4_sha[:16]}…, geltend und angenommen ist "
                    f"{[s[:16] for s in am4_spitzen]}"
                    + (f" (Kette: {'; '.join(am4_fehler[:3])})" if am4_fehler else "")
                    + f" — die Probe auf der geltenden Migrationsabnahme fahren: {probe_kommando}",
                )
            # Das Soll der Probe muss das der GELTENDEN Abnahmen sein (Block
            # F, Nachbesserung, Pruefer-Befund 1): die Bytes von
            # aktuartest.json, die der geltende, angenommene A-M1-Snapshot
            # pinnt (den A-M4 pinnt), und die von migrationssuite.json, die
            # A-M4 pinnt — im Beleg UND am festen Ort im Fall. Dieselbe
            # Regel wie Probe und Registrierung (models.zugangsprobe).
            am4_daten = am4_kette[am4_sha][1]
            am1_kette, am1_spitzen, am1_fehler = _lade_snapshot_kette(
                entscheide_verzeichnis(fall), "A-M1", fall, schluesselring,
                entscheid_systemstand)
            am1_pin = ((am4_daten.get("pflichtbelege") or {}).get("am1_snapshot") or [None])[0]
            am1_daten = am1_kette[am1_pin][1] if am1_pin in am1_kette else None
            soll_fehler = zp_mod.soll_bindung_fehler(
                probe.get("abnahmen"), am4=am4_daten, am1=am1_daten)
            # Wer A-M4 und A-M1 gezeichnet hat, gegen die Ordnung DIESER
            # Zeichnung (Entscheid 2026-10-01): dieselbe Regel wie die
            # Vorbedingungen von A-M4 und wie Registrierung und Probe.
            for abnahme_gate, abnahme_daten in (("A-M4", am4_daten), ("A-M1", am1_daten)):
                if abnahme_daten is None:
                    continue
                _, rollen_fehler = zeichnende_rolle_fehler(
                    abnahme_daten, abnahme_gate, zeichnungsordnung, linie=ordnungsglieder)
                if rollen_fehler:
                    soll_fehler.append(f"{abnahme_gate}-Snapshot: {rollen_fehler}")
            if am1_fehler or am1_spitzen != [am1_pin] or (
                    am1_daten is not None and am1_daten.get("entscheid") != "angenommen"):
                soll_fehler.append(
                    f"der A-M1-Snapshot {str(am1_pin)[:16]}…, den A-M4 pinnt, ist nicht die "
                    f"geltende angenommene Spitze ({[x[:16] for x in am1_spitzen]}"
                    + (f"; Kette: {'; '.join(am1_fehler[:2])}" if am1_fehler else "") + ")")
            for rolle, (_, datei) in zp_mod.SOLL_BELEGE.items():
                gebunden = (probe.get("abnahmen") or {}).get(rolle) or {}
                try:
                    jetzt = lies_gehasht(fall / datei).sha256
                except OSError as exc:
                    jetzt = f"unlesbar ({exc})"
                if jetzt != gebunden.get("sha256"):
                    soll_fehler.append(
                        f"{datei} am festen Ort ist nicht die gebundene Fassung "
                        f"({str(jetzt)[:16]}… statt {str(gebunden.get('sha256'))[:16]}…)")
            if soll_fehler:
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: das Soll der Zugangsprobe ist nicht das der "
                    "geltenden Abnahmen: " + "; ".join(soll_fehler[:4])
                    + f" — die abgenommenen Belege wiederherstellen oder die Abnahmen "
                    f"neu entscheiden, dann die Probe fahren: {probe_kommando}",
                )
            pflichtbelege["zugangsprobe"] = [probe_gelesen.sha256]
            pflichtbelege["am4_snapshot"] = [am4_sha]
            pflichtbelege["eingang"] = [probe["eingang"]["sha256"]]
            erwartete_rollen = belegrollen("A-B2", fall_scope or "")
            if set(pflichtbelege) != set(erwartete_rollen):
                return _sperre(
                    "vorbedingung",
                    "Annahme verweigert: aus dem Fall-Scope abgeleitete "
                    f"Pflichtbelege unvollstaendig; fehlen="
                    f"{sorted(set(erwartete_rollen) - set(pflichtbelege))}, fremd="
                    f"{sorted(set(pflichtbelege) - set(erwartete_rollen))} — A-B2 "
                    "gibt es nur im Bestands-Scope (ein Tarif-Fall hat keinen Zugang)",
                )
            pflichtbelege = {rolle: pflichtbelege[rolle] for rolle in erwartete_rollen}

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
            erwartete_rollen = belegrollen(
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
            # Die eine Regel der Leser (models.zeichnung, Entscheid
            # 2026-10-01): Rolle aus dem Schluessel, Gate erlaubt, und das
            # Rollenfeld des Snapshots ist genau diese Rolle.
            _, zf = zeichnende_rolle_fehler(aq1_spitze, "A-Q1", zeichnungsordnung,
                                            linie=ordnungsglieder)
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
                _, zf = zeichnende_rolle_fehler(spitze_a, abnahme_gate, zeichnungsordnung,
                                                linie=ordnungsglieder)
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

            # Der Stand, auf dem der Fall laeuft, ist abgenommen (Entscheid
            # des Maintainers 2026-10-01, ADR-018 Nachtrag 2026-10-01; ADR-025):
            # EINE Regel fuer Kernstand (A-K2), T-Box-Stand (A-O1) und Tarifwerk
            # (A-T1), in jedem Scope — im Fall gezeichnet oder als "keine
            # Aenderung" gegenueber der Erstabnahme bzw. einem frueheren Fall
            # belegt.
            for gegenstand in _standabnahme.AM4_GEGENSTAENDE:
                meldung, pin, eintrag = standabnahme_pruefen(
                    gegenstand, fall=fall, repo_root=repo_root,
                    verzeichnis=verzeichnis_aq1, schluesselring=schluesselring,
                    systemstand=entscheid_systemstand, ordnung=zeichnungsordnung,
                    fall_json_sha256=fall_json_sha256, linie=ordnungsglieder,
                )
                if meldung is not None:
                    return _sperre(
                        "vorbedingung",
                        f"Annahme verweigert: {meldung}",
                    )
                pflichtbelege[gegenstand.rolle] = [pin]
                am4_standabnahmen[gegenstand.rolle] = eintrag

            erwartete_rollen = am4_belegrollen(fall_scope or "")
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

    # Jede Annahme eines Falls ausser dem Auftrag selbst setzt den geltenden
    # Fallauftrag voraus (ADR-026) — EINE Stelle fuer alle Gates, nach den
    # gate-eigenen Vorbedingungen (deren Befund ist genauer) und vor jedem
    # Schreiben.
    if args.entscheid == "angenommen" and not linie_modus and args.gate != AUFTRAG_GATE:
        sf = _schluessel_laden()
        if sf:
            return _sperre("freigabe", "Annahme verweigert: externe Freigabeschluessel "
                           "ungueltig: " + "; ".join(sf[:5]))
        if aktiver_schluessel is None:
            return _sperre(
                "freigabe",
                "Annahme verweigert: --freigabe-schluessel <externe-datei> ist "
                "erforderlich; ein frei editierbarer Fall darf seine menschliche "
                "Freigabe nicht selbst behaupten")
        if zeichnungsordnung is None:
            return _sperre(
                "zeichnung",
                "Annahme verweigert: --zeichnungsordnung fehlt — die zeichnende Rolle wird "
                "aus dem Freigabeschluessel ueber die Ordnung bestimmt, nicht behauptet "
                "(ADR-018)")
        auftrag_spitze, auftrag_meldung = fallauftrag_pruefen(
            fall, schluesselring=schluesselring, systemstand=entscheid_systemstand,
            ordnung=zeichnungsordnung, linie=ordnungsglieder, bekannt=bekannte_hashes)
        if auftrag_meldung is not None:
            return _sperre("fallauftrag", f"Annahme verweigert: {auftrag_meldung}")
        if args.gate == ABBRUCH_GATE and (lebenslauf_inhalt or {}).get(
                "fallauftrag") != auftrag_spitze["snapshot_sha256"]:
            return _sperre(
                "vorbedingung",
                "Annahme verweigert: die Vorlage des Abbruchs nennt den Fallauftrag "
                f"{str((lebenslauf_inhalt or {}).get('fallauftrag'))[:16]}…, geltend ist "
                f"{auftrag_spitze['snapshot_sha256'][:16]}… — Vorlage neu erzeugen (python -m "
                "rechner_pipeline.gates.fall_belegen abbruch ...)")

    verzeichnis = entscheide_verzeichnis(fall)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    # Die Reste eines hart abgebrochenen frueheren Laufs dieses Gates
    # wegraeumen (Angriffsrunde C, RC07) — am Anfang und fuer JEDEN Pfad,
    # auch 'bereits_vorhanden', der selbst nichts schreibt und dem kein
    # Schreiber das Aufraeumen abnimmt. Nur das Namensmuster dieses Gates
    # (.<gate>-*.json.*.tmp); die Reste anderer Gates und fremde
    # Punktdateien gehoeren anderen Laeufen. Das Ledger-Verzeichnis raeumt
    # write_gate_ledger fuer sein Ziel. Die Gates eines Falls laufen
    # nacheinander; ein gleichzeitiger Lauf desselben Gates wuerde hier
    # dessen Tempdatei treffen.
    for rest in verzeichnis.glob(f".{args.gate}-*.json.*.tmp"):
        rest.unlink(missing_ok=True)
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
    # Woher die zeichnende Rolle ihr Recht hat (ADR-026, dieselbe Regel wie
    # beim Lesen): fuer die Gates der Fall-Rollen aus dem geltenden
    # Fallauftrag, fuer jedes andere aus der Ordnung.
    rechtsordnung: Optional[dict] = zeichnungsordnung
    if args.gate in FALLROLLEN_GATES and auftrag_spitze is not None:
        rechtsordnung = _fallauftrag.rechtsordnung(auftrag_spitze["auftrag"])
    if rechtsordnung is not None and aktiver_schluessel is not None:
        bestimmt = _zeichnungsrolle(rechtsordnung, aktiver_schluessel)
        if bestimmt is None and args.entscheid == "angenommen":
            if args.gate in FALLROLLEN_GATES:
                return _sperre(
                    "zeichnung",
                    f"Annahme verweigert: {args.gate} zeichnet die Programmleitung, die der "
                    "geltende Fallauftrag benennt, mit dem Schluessel, den er ihr gibt — der "
                    "Freigabeschluessel ist ein anderer; das Recht der Fall-Rolle kommt aus "
                    "dem Auftrag, nicht aus der Ordnung (ADR-026)")
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
        zf = _zeichnungsfehler(rechtsordnung, args.gate, aktiver_schluessel)
        if zf:
            if args.gate in FALLROLLEN_GATES:
                zf += (f" — {args.gate} zeichnet die Programmleitung, die der geltende "
                       "Fallauftrag benennt, mit dem Schluessel, den er ihr gibt (ADR-026)")
            return _sperre("zeichnung", f"Annahme verweigert: {zf}")
        glied_sha: Optional[str] = None
        if ordnungsglieder:
            spitze_glied = ordnungsglieder[-1]
            if spitze_glied["ordnung_sha256"] != zeichnungsordnung_sha:
                return _sperre(
                    "ordnungslinie",
                    "Annahme verweigert: die Zeichnungsordnung dieses Aufrufs "
                    f"({str(zeichnungsordnung_sha)[:16]}) ist nicht die Spitze der "
                    f"Ordnungslinie (Glied {spitze_glied['nummer']}, "
                    f"{spitze_glied['ordnung_sha256'][:16]}) — gezeichnet wird nur unter "
                    "der Spitze. Ausweg: die Ordnung in die Linie eintragen (python -m "
                    "rechner_pipeline.gates.stand_belegen ordnung ...) oder die Ordnung der "
                    "Spitze verwenden (ADR-025)")
            glied_sha = spitze_glied["glied_sha256"]
        zeichnung = zeichnung_fuer(
            rechtsordnung, zeichnungsordnung_sha, aktiver_schluessel,
            mandat_sha256, glied_sha,
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
        # Die Mandate bindet der Fallauftrag (ADR-026): Eine simulierte Rolle
        # handelt im Fall unter GENAU dem Mandat, das der Auftrag ihr nennt.
        if (auftrag_spitze is not None
                and zeichnung.get("schluesselklasse") == "simulation"
                and auftrag_spitze["auftrag"]["mandate"].get(zeichnung["rolle"])
                != zeichnung.get("mandat_sha256")):
            return _sperre(
                "mandat",
                f"Annahme verweigert: die simulierte Rolle {zeichnung['rolle']!r} handelt "
                f"unter dem Mandat {str(zeichnung.get('mandat_sha256'))[:16]}…, der Fallauftrag "
                f"nennt ihr {str(auftrag_spitze['auftrag']['mandate'].get(zeichnung['rolle']))[:16]}"
                "… — das Mandat ist Teil des Auftrags (ADR-026). Ausweg: unter dem genannten "
                "Mandat zeichnen oder den Fall neu beauftragen")

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
        # Je Gegenstand der Weg und die woertliche Anzeige — signiert, damit
        # "keine Aenderung seit Abnahme ..." im Beleg steht, nicht nur im Ledger.
        kern_inhalt["standabnahmen"] = am4_standabnahmen
    if args.gate in P9_GATES_MIT_STAND:
        # Der Stand, den diese Abnahme abnimmt (ADR-018, Nachtrag
        # 2026-10-01): A-M4 haelt ihn per == gegen den lebenden — im Fall
        # wie ueber einen Verweis aus einem spaeteren Fall.
        abgenommen = _stand.lebender_stand(
            args.gate, Path(args.repo_root).resolve() if args.repo_root else None, fall)
        if abgenommen is None:
            return _sperre("vorbedingung",
                           f"Entscheid verweigert: der Stand von {args.gate} ist nicht "
                           "bestimmbar (--repo-root fehlt?)")
        kern_inhalt["stand"] = abgenommen
    if args.gate in P9_GATES_MIT_AUSNAHMEN:
        # Was die Zeichnung NICHT deckt, im signierten Inhalt — woertlich
        # (ADR-018, Nachtrag 2026-10-01). Eine Ablehnung deckt nichts und
        # fuehrt deshalb keine.
        kern_inhalt["ausnahmen"] = ak2_ausnahmen
    if zeichnung is not None:
        kern_inhalt["zeichnung"] = zeichnung
    if args.entscheid == "angenommen" and args.gate in P9_LEBENSLAUF_FELDER:
        # Der Inhalt des Auftrags bzw. Abbruchs, signiert (ADR-026): Wer spaeter
        # liest, wer den Fall fuehrt und unter welchen Mandaten, liest es hier.
        kern_inhalt[P9_LEBENSLAUF_FELDER[args.gate]] = lebenslauf_inhalt
    if auftrag_spitze is not None:
        # Der Abnahmepunkt nennt signiert den Auftrag, auf dem er steht.
        kern_inhalt["fallauftrag"] = auftrag_spitze["snapshot_sha256"]
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
        schreibe_exklusiv(ziel, payload)
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
    # Unter welchem Stand der Ordnung gezeichnet und gelesen wurde (ADR-025) —
    # gesagt, nicht verschwiegen, auch wenn es keine Linie gab.
    ergebnis_summary["ordnungslinie"] = (
        f"Glied {ordnungsglieder[-1]['nummer']} ({ordnungsglieder[-1]['glied_sha256'][:16]})"
        if ordnungsglieder else "leer — eine Ablehnung zeichnet nichts (ADR-025)")
    if linie_modus:
        ergebnis_summary["bereich"] = "linie"
    if "fallauftrag" in snapshot:
        ergebnis_summary["fallauftrag"] = snapshot["fallauftrag"]
    if args.gate == AUFTRAG_GATE and args.entscheid == "angenommen":
        ergebnis_summary["programmleitung"] = lebenslauf_inhalt["programmleitung"]
    if args.gate == ABBRUCH_GATE and args.entscheid == "angenommen":
        ergebnis_summary["anzeige"] = ("dieser Fall endet hier, ohne Abnahme — danach ist im "
                                       "Fall nichts mehr zeichenbar")
    if args.gate in P9_GATES_MIT_STAND and "stand" in snapshot:
        ergebnis_summary["stand"] = snapshot["stand"]
    if args.gate == "A-M4":
        ergebnis_summary["pk1_belege"] = pk1_belege
        ergebnis_summary["fall_scope"] = fall_scope
        ergebnis_summary["pflichtbelege"] = pflichtbelege
        ergebnis_summary["standabnahmen"] = am4_standabnahmen
    if args.gate == "A-K2":
        ergebnis_summary["pflichtbelege"] = pflichtbelege
        ergebnis_summary["ausnahmen"] = ak2_ausnahmen
        if ak2_ausnahmen:
            ergebnis_summary["anzeige"] = [_kernabnahme.ANZEIGE_REGRESSION]
            ergebnis_summary["deckung"] = _kernabnahme.DECKUNG_UNTER_AUSNAHME
    if args.gate == "A-B2":
        # Die Registrierung liest den Snapshot-Hash aus diesem Ledger; die
        # Belege daneben sagen dem Bediener, WELCHEN Eingang A-B2 abnimmt.
        ergebnis_summary["pflichtbelege"] = pflichtbelege
        # Was das Gate NICHT weiss (Block F, Nachbesserung, Pruefer-Befund
        # 7): Die Betriebszeichnung des Belegs rechnet nur nach, wer den
        # Betriebsschluessel haelt — das Gate prueft Form und Rolle, die
        # Registrierung die Signatur. Gesagt wird es, nicht verschwiegen.
        ergebnis_summary["betriebssignatur"] = BETRIEBSSIGNATUR_NICHT_VERIFIZIERT
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
