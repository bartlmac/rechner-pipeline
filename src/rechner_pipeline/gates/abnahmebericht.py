"""Migrationsabnahmebericht: deterministisches HTML als G-2-Vorlage.

Die Entscheidungsvorlage der menschlichen Migrationsabnahme, aus drei
deterministischen Bausteinen:

1. Abnahmetests der Migrationssuite (``qa/migrationssuite``):
   Deckungskapital an ZWEI Stichtagen, Bruttojahresbeitrag am
   Migrationsstichtag und GeVo-Beträge dazwischen — als
   Zusammenfassung je Prüfgröße UND als vollständige
   Einzelvergleichs-Tabelle (jeder Vertrag, jeder Wert, jedes
   Residuum); Fehlschläge, Befunde, Befunde der PRÜFMENGE
   (Vollständigkeit, Duplikate) und PRÜFLÜCKEN gesondert.
2. Transformations-Tabelle (``ontologie/transformation``): das
   fachlich abzunehmende Mapping Quellfeld -> Zielfeld samt
   Begründungen und (entschiedenen) Konflikten.
3. Verweise auf die Bestandsberichte VOR und NACH der Migration —
   der visuelle Vergleich ist Teil der Abnahme.

Der Bericht RECHNET keine Fachwerte und ENTSCHEIDET nichts: Er berechnet
Residuen-, Einzel-, Vertrags- und Suiteurteile lediglich erneut aus den
persistierten atomaren Fakten und lehnt jede widerspruechliche Ableitung als
Contract-Fehler ab. Gleiche Eingaben ergeben byte-identisches HTML (keine
Zeitstempel), und das Verdikt ist ausdrücklich eine maschinelle Prüfaussage —
die Abnahme selbst ist Gate G-2 (Mensch, Entscheid-Snapshot).

Als Kommando (``python -m rechner_pipeline.gates.abnahmebericht``) ist
das Modul zugleich ein Toolbox-Gate nach dem Vertrag der übrigen Gates:
EIN JSON auf stdout, ein ``abnahmebericht.gate.json``-Ledger in den
Diagnostics-Ordner, Standard-Exit-Codes. Es NIMMT DIE MIGRATION NICHT
AB — es stellt fest, ob die deterministische Migrationssuite ohne
Fehlschlag geurteilt hat, und legt die Entscheidungsvorlage als
Fall-Artefakt mit Provenienz (Eingabe-Hashes) ab. Die Abnahme bleibt
Gate G-2 beim Menschen (``gates/gate_entscheid``); ein
Exit-Code ``0`` heißt "vollständige Vorlage ohne Abnahmehindernis", nicht
"abgenommen". Prüflücken, Zeilenverlust, Transformationsbefunde, nicht
entschiedene Konflikte oder fehlende Pflichtartefakte blockieren den grünen
Bericht und werden im HTML sowie im Ledger einzeln ausgewiesen. Was nicht
geprüft wurde oder verloren ging, wird nie als bestanden bezeichnet.

In einem als ``bestand`` deklarierten Fall sind ein gruener B1-Beleg und eine
vollstaendige Suite Pflicht. Das gruene Ledger bindet beide und den erzeugten
HTML-Abnahmebericht gemeinsam an Eingangsregister, A-Box, Systemstand und
beide Stichtage. Spec, Transformationsergebnis sowie Vor- und Nachbericht sind
zusaetzlich unter vier festen Renderer-Rollen an Fallpfad und SHA-256 gebunden.
G-2 hasht diese Dateien neu und leitet die sichtbaren Transformationsfakten aus
ihrem Inhalt ab. Ein ``tarif``-Fall verlangt die Bestandsbelege nicht.
Unabhaengig vom Scope kann ein Bericht nur gruen werden, wenn seine Quelle im
Fall registriert ist und fuer genau diesen Aufruf physisch neu gelesen wurde;
der falllose Bibliotheks- oder CLI-Renderer bleibt ausdruecklich rot und
nichtautoritativ.

Die Suite-Urteile kommen als JSON herein — genau das, was
:func:`rechner_pipeline.qa.migrationssuite.pruefe_bestand` zurückgibt
(``json.dump``-fähige Primitive). Der Zusammenbau der Prüfaufträge
(Modellpunkte aus der Spez, Erwartungswerte aus der Lieferung) bleibt
Sache des Falls; das Kommando rendert, protokolliert und urteilt.

Run via::

    python -m rechner_pipeline.gates.abnahmebericht \\
        --fall faelle/<fall> --suite <suite_ergebnis.json> \\
        --titel "Migrationsabnahme <Fall>" \\
        --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 \\
        --spec <transformationsspec.json> \\
        --transformation-ergebnis <ergebnis.json> \\
        --bestandsbericht-vor vor/index.html \\
        --bestandsbericht-nach nach/index.html \\
        [--bericht <ziel.html>] [--diagnostics-dir <dir>]

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import math
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict, List, Optional

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.gates._common import (
    Exit,
    GATE_LEDGER_SUFFIX,
    GateArgumentParser,
    GateCliContract,
    add_request_json_arg,
    begin_gate_ledger_attempt,
    build_result,
    finalize_gate_ledger,
    hash_files,
    log,
    parse_gate_args,
    run_command,
    utc_now,
)
from rechner_pipeline.gates._fall_scope import (
    artefakt_eintrag,
    bestands_belegrollen,
    pruefe_artefakt_eintrag,
    scope_bindung,
)
from rechner_pipeline.models.schemas import GateLedgerEntry
from rechner_pipeline.ontologie.transformation import (
    TransformationsSpec,
    lese_transformationsquelle,
    validate_spec,
)
from rechner_pipeline.qa.abzugsabgleich import ABS_TOL, REL_TOL

COMMAND = "abnahmebericht"
#: Kein Gate "G2": die Abnahme ist der MENSCHLICHE Gate G-2. Dieses
#: Kommando erzeugt und protokolliert dessen Vorlage — der Gate-Name
#: sagt das, damit ein Ledger-Leser die beiden nie verwechselt.
GATE = "G2-vorlage.migrationsabnahme"
GATE_VERSION = "1.10.0"
CLI_CONTRACT = GateCliContract(
    command=COMMAND,
    gate=GATE,
    gate_version=GATE_VERSION,
    diagnostics_from="fall",
)

# Die Rollen sind Teil des persistierten Beweisvertrags mit G-2. Pfadnamen in
# ``input_hashes`` sind keine Rollen: Sie duerfen deshalb weder zum Erkennen
# noch zum Vollstaendigkeitsnachweis dieser vier Eingaben verwendet werden.
RENDERER_ARTEFAKTROLLEN = (
    "spec",
    "transformation_ergebnis",
    "bestandsbericht_vor",
    "bestandsbericht_nach",
)

TRANSFORMATIONSERGEBNIS_FELDER = {
    "schema_version",
    "spec_sha256",
    "quelle_sha256",
    "quellspalten",
    "ziel_datei",
    "ziel_sha256",
    "zeilen_quelle",
    "zeilen_ziel",
    "befunde",
}


def renderer_artefaktrollen() -> List[str]:
    """Exakte Rollen der vier Pflichtartefakte des Berichtsrenderers."""
    return list(RENDERER_ARTEFAKTROLLEN)


def _pfadrollen_kollisionen(pfade: Dict[str, Path]) -> List[str]:
    """Kanonische Pfad- und Hardlink-Aliase zwischen Artefaktrollen finden.

    Ein Ausgabepfad, der eine Eingabe ueberschreibt, laesst den Produzenten
    sonst noch gruen enden, obwohl das Pflichtartefakt unmittelbar danach
    nicht mehr existiert. Verschiedene Pfadstrings reichen dafuer nicht als
    Nachweis, weil auch Symlinks und Hardlinks dieselbe Datei bezeichnen.
    """
    kandidaten = [(rolle, pfad.resolve()) for rolle, pfad in pfade.items()]
    kollisionen: List[str] = []
    for index, (rolle, pfad) in enumerate(kandidaten):
        for andere_rolle, anderer_pfad in kandidaten[index + 1:]:
            identisch = pfad == anderer_pfad
            if not identisch and pfad.exists() and anderer_pfad.exists():
                try:
                    identisch = pfad.samefile(anderer_pfad)
                except OSError:
                    identisch = False
            if identisch:
                kollisionen.append(f"{rolle} und {andere_rolle}")
    return kollisionen

_STIL = """
body { font-family: sans-serif; margin: 2em; color: #222; }
h1 { border-bottom: 2px solid #444; padding-bottom: 0.2em; }
table { border-collapse: collapse; margin: 1em 0; }
th, td { border: 1px solid #999; padding: 0.3em 0.7em; text-align: left; }
th { background: #eee; }
.gruen { color: #060; font-weight: bold; }
.rot { color: #a00; font-weight: bold; }
.hinweis { background: #ffd; border: 1px solid #cc9; padding: 0.6em; }
td.zahl { text-align: right; }
"""


def _e(text: Any) -> str:
    return html.escape(str(text))


def _gruppe(groesse: str) -> str:
    """Prüfgrößen-Gruppe einer Einzelprüfung (gevo_sto_monat_137 -> gevo_sto)."""
    if groesse.startswith("gevo_"):
        return "_".join(groesse.split("_")[:2])
    return groesse


def _pruefgroessen_zeilen(suite: Dict[str, Any]) -> List[str]:
    gruppen: Dict[str, Dict[str, float]] = {}
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            g = gruppen.setdefault(
                _gruppe(p["groesse"]), {"anzahl": 0, "ok": 0, "max_res": 0.0})
            g["anzahl"] += 1
            g["ok"] += 1 if p["ok"] else 0
            g["max_res"] = max(g["max_res"], abs(p["residuum"]))
    zeilen = []
    for name in sorted(gruppen):
        g = gruppen[name]
        zeilen.append(
            f"<tr><td>{_e(name)}</td><td class='zahl'>{g['anzahl']:.0f}</td>"
            f"<td class='zahl'>{g['ok']:.0f}</td>"
            f"<td class='zahl'>{g['max_res']:.4f}</td></tr>"
        )
    return zeilen


def _mapping_zeilen(spec: TransformationsSpec) -> List[str]:
    zeilen = []
    for f in spec.felder:
        if f.typ == "kodierung":
            detail = "; ".join(f"{k} -> {v}" for k, v in f.kodierung.items())
        elif f.typ == "berechnung":
            detail = f.berechnung
        else:
            detail = "—"
        ziel = f.ziel if f.typ != "nicht_uebernommen" else "(nicht übernommen)"
        zeilen.append(
            f"<tr><td>{_e(', '.join(f.quellen))}</td><td>{_e(ziel)}</td>"
            f"<td>{_e(f.typ)}</td><td>{_e(detail)}</td>"
            f"<td>{_e(f.begruendung)}</td></tr>"
        )
    return zeilen


def _transformation_ergebnis_fehler(daten: Any) -> List[str]:
    """Minimalen Renderer-Vertrag eines Transformationsergebnisses prüfen."""
    if not isinstance(daten, dict):
        return ["Transformationsergebnis ist kein JSON-Objekt"]
    fehler: List[str] = []
    for feld in ("zeilen_quelle", "zeilen_ziel", "befunde"):
        if feld not in daten:
            fehler.append(f"Transformationsergebnis: Feld {feld!r} fehlt")
    if fehler:
        return fehler
    for feld in ("zeilen_quelle", "zeilen_ziel"):
        wert = daten[feld]
        if type(wert) is not int or wert < 0:
            fehler.append(
                f"Transformationsergebnis.{feld} ist keine nichtnegative "
                "ganze Zahl"
            )
    befunde = daten["befunde"]
    if not isinstance(befunde, list):
        fehler.append("Transformationsergebnis.befunde ist keine Liste")
    elif any(not isinstance(befund, str) or not befund for befund in befunde):
        fehler.append(
            "Transformationsergebnis.befunde enthält einen leeren oder "
            "nichttextuellen Befund"
        )
    return fehler


def _quellspalten_fuer_spec_pruefung(
    spec: TransformationsSpec,
    transformation_ergebnis: Optional[Dict[str, Any]],
) -> List[str]:
    """Spalten fuer die strukturelle Renderer-Pruefung bestimmen.

    Im Bestands-Scope wird diese Liste spaeter zwingend durch den physischen
    Header der registrierten Quelle ersetzt. Fuer den reinen Bibliotheks-
    Renderer sorgt die aus der Spec abgeleitete Liste zumindest dafuer, dass
    Pflichtfelder, Konflikte, SHA-Form und Berechnungsaritaeten nie ungeprueft
    gerendert werden.
    """
    if isinstance(transformation_ergebnis, dict):
        deklariert = transformation_ergebnis.get("quellspalten")
        if (
            isinstance(deklariert, list)
            and all(isinstance(spalte, str) for spalte in deklariert)
        ):
            return list(deklariert)
    ergebnis: List[str] = []
    for spalte in [
        *(quelle for feld in spec.felder for quelle in feld.quellen),
        *(konflikt.quellspalte for konflikt in spec.offene_konflikte),
    ]:
        if spalte not in ergebnis:
            ergebnis.append(spalte)
    return ergebnis


def _spec_fehler(
    spec: TransformationsSpec,
    transformation_ergebnis: Optional[Dict[str, Any]],
) -> List[str]:
    """Harte Spec-Fehler auf jedem Berichtsweg ausfuehren.

    Ein wirklich offener Konflikt (``entscheidung is None``) bleibt ein
    sichtbares Abnahmehindernis, fuer das gerade der rote Bericht gebraucht
    wird. Leere Scheinentscheidungen, fehlende Entscheider und alle anderen
    Contract-Fehler werden dagegen vor dem Rendern abgelehnt.
    """
    alle_fehler = validate_spec(
        spec,
        _quellspalten_fuer_spec_pruefung(spec, transformation_ergebnis),
    )
    offene_meldungen = {
        f"offener Konflikt zu Spalte {konflikt.quellspalte!r}: "
        f"{konflikt.frage} — MENSCHLICHE Entscheidung noetig, "
        "Anwendung blockiert"
        for konflikt in spec.offene_konflikte
        if konflikt.entscheidung is None
    }
    return [meldung for meldung in alle_fehler if meldung not in offene_meldungen]


def _transformationsvertrag_fehler(
    *,
    fall: Path,
    spec_pfad: Path,
    spec: TransformationsSpec,
    ergebnis: Any,
    suite: Dict[str, Any],
) -> tuple[List[str], Optional[Path], Optional[str]]:
    """Quelle, Spec, Anwendung und B1-/Suite-Ziel lueckenlos verbinden.

    Keine Angabe des Ergebnis-JSON gilt als Beweis ihrer selbst. Quelle und
    Header werden ueber das Fallregister neu aufgeloest, die Bytes gehasht und
    mit der Spec sowie dem Ergebnis verglichen. Das Ziel wird ebenfalls neu
    gehasht und muss genau der von Suite und damit B1 gepruefte Bestand sein.
    """
    if not isinstance(ergebnis, dict) or set(ergebnis) != (
        TRANSFORMATIONSERGEBNIS_FELDER
    ):
        return ([
            "Transformationsergebnis muss exakt "
            f"{sorted(TRANSFORMATIONSERGEBNIS_FELDER)} enthalten"
        ], None, None)

    fehler = _transformation_ergebnis_fehler(ergebnis)
    if ergebnis.get("schema_version") != 1 or type(
        ergebnis.get("schema_version")
    ) is not int:
        fehler.append("Transformationsergebnis.schema_version muss 1 sein")

    spec_sha256 = sha256(spec_pfad.read_bytes()).hexdigest()
    if ergebnis.get("spec_sha256") != spec_sha256:
        fehler.append(
            "Transformationsergebnis.spec_sha256 bindet nicht die aktuelle Spec"
        )

    quellspalten = ergebnis.get("quellspalten")
    if (
        not isinstance(quellspalten, list)
        or not quellspalten
        or any(not isinstance(spalte, str) or not spalte for spalte in quellspalten)
        or len(quellspalten) != len(set(quellspalten))
    ):
        fehler.append(
            "Transformationsergebnis.quellspalten muss eine nichtleere, "
            "duplikatfreie Stringliste sein"
        )

    quelle_pfad: Optional[Path] = None
    aktuelle_quellspalten: Optional[List[str]] = None
    aktuelle_quellzeilen: Optional[int] = None
    aktuelle_quelle_sha256: Optional[str] = None
    try:
        quelle_pfad = fall_mod.eingang_datei(fall, spec.quelle_datei)
        (
            aktuelle_quelle_sha256,
            aktuelle_quellspalten,
            quellzeilen,
        ) = lese_transformationsquelle(quelle_pfad)
        aktuelle_quellzeilen = len(quellzeilen)
    except (OSError, UnicodeError, ValueError, fall_mod.FallFehler) as exc:
        fehler.append(
            "registrierte Transformationsquelle ist nicht pruefbar: "
            f"{type(exc).__name__}: {exc}"
        )

    if aktuelle_quelle_sha256 is not None:
        if spec.quelle_sha256 != aktuelle_quelle_sha256:
            fehler.append(
                "TransformationsSpec.quelle_sha256 weicht von der tatsaechlich "
                "transformierten registrierten Datei ab"
            )
        if ergebnis.get("quelle_sha256") != aktuelle_quelle_sha256:
            fehler.append(
                "Transformationsergebnis.quelle_sha256 weicht von der "
                "tatsaechlich transformierten registrierten Datei ab"
            )
    if aktuelle_quellspalten is not None:
        spec_fehler = validate_spec(spec, aktuelle_quellspalten)
        fehler.extend(f"TransformationsSpec: {meldung}" for meldung in spec_fehler)
        if quellspalten != aktuelle_quellspalten:
            fehler.append(
                "Transformationsergebnis.quellspalten weichen vom physischen "
                "Header der registrierten Transformationsquelle ab"
            )
    if (
        aktuelle_quellzeilen is not None
        and ergebnis.get("zeilen_quelle") != aktuelle_quellzeilen
    ):
        fehler.append(
            "Transformationsergebnis.zeilen_quelle weicht von der aktuellen "
            "registrierten Transformationsquelle ab"
        )
    if ergebnis.get("zeilen_ziel") != suite.get("anzahl"):
        fehler.append(
            "Transformationsergebnis.zeilen_ziel weicht von der durch B1 und "
            "Migrationssuite geprueften Bestandszeilenzahl ab"
        )

    ziel, ziel_fehler = pruefe_artefakt_eintrag(
        fall,
        "Transformationsziel",
        {
            "pfad": ergebnis.get("ziel_datei"),
            "sha256": ergebnis.get("ziel_sha256"),
        },
    )
    fehler.extend(ziel_fehler)
    ziel_sha256 = ergebnis.get("ziel_sha256") if ziel is not None else None
    if ziel_sha256 is not None and suite.get("bestand_sha256") != ziel_sha256:
        fehler.append(
            "Transformationsziel und Migrationssuite binden verschiedene "
            "Bestandsartefakte"
        )
    return fehler, ziel, ziel_sha256


def _registrierte_quellenbindung_fehler(
    *,
    fall: Path,
    spec: TransformationsSpec,
    ergebnis: Any,
) -> List[str]:
    """Quellbehauptungen gegen eine neu gelesene Fallquelle pruefen.

    Diese engere Pruefung ist auf jedem Berichtsweg erforderlich, auch wenn
    der Fall-Scope nicht den weitergehenden Bestandsvertrag mit B1 und
    Transformationsziel aktiviert. Ein vom Aufrufer gelieferter Pfad oder ein
    deklarierter Hash ist ausdruecklich kein Registrierungsnachweis.
    """
    fehler: List[str] = []
    if not isinstance(ergebnis, dict):
        return ["Transformationsergebnis ist kein JSON-Objekt"]

    try:
        quelle_pfad = fall_mod.eingang_datei(fall, spec.quelle_datei)
        quelle_sha256, quellspalten, quellzeilen = lese_transformationsquelle(
            quelle_pfad
        )
    except (OSError, UnicodeError, ValueError, fall_mod.FallFehler) as exc:
        return [
            "registrierte Transformationsquelle ist nicht pruefbar: "
            f"{type(exc).__name__}: {exc}"
        ]

    if spec.quelle_sha256 != quelle_sha256:
        fehler.append(
            "TransformationsSpec.quelle_sha256 weicht von der physisch neu "
            "gelesenen registrierten Transformationsquelle ab"
        )
    if ergebnis.get("quelle_sha256") != quelle_sha256:
        fehler.append(
            "Transformationsergebnis.quelle_sha256 weicht von der physisch "
            "neu gelesenen registrierten Transformationsquelle ab"
        )
    if ergebnis.get("quellspalten") != quellspalten:
        fehler.append(
            "Transformationsergebnis.quellspalten weichen vom physischen "
            "Header der registrierten Transformationsquelle ab"
        )
    if ergebnis.get("zeilen_quelle") != len(quellzeilen):
        fehler.append(
            "Transformationsergebnis.zeilen_quelle weicht von der physisch "
            "neu gelesenen registrierten Transformationsquelle ab"
        )
    fehler.extend(
        f"TransformationsSpec: {meldung}"
        for meldung in validate_spec(spec, quellspalten)
    )
    return fehler


def _abnahmehindernisse(
    *,
    suite: Dict[str, Any],
    spec: Optional[TransformationsSpec],
    transformation_ergebnis: Optional[Dict[str, Any]],
    bestandsbericht_vor: Optional[str],
    bestandsbericht_nach: Optional[str],
    fall: Optional[Path] = None,
) -> List[Dict[str, str]]:
    """Alle belegnahen Gründe gegen einen grünen Abnahmebericht ableiten.

    Suite-Fehlschläge und Mengenbefunde bleiben ihre etablierten Fehlerklassen.
    Diese Liste schließt die T6-05-Lücke zwischen einer für sich grünen Suite
    und einer tatsächlich vollständigen, verlustfreien Entscheidungsvorlage.
    """
    hindernisse: List[Dict[str, str]] = [
        {"code": "pruefluecke", "message": f"Prüflücke: {luecke}"}
        for luecke in suite["pruefluecken"]
    ]
    if spec is None:
        hindernisse.append({
            "code": "pflichtartefakt",
            "message": "Transformationsspecifikation fehlt",
        })
    else:
        hindernisse.extend(
            {
                "code": "offener_konflikt",
                "message": (
                    f"Konflikt zu {konflikt.quellspalte!r} ist nicht "
                    f"entschieden: {konflikt.frage}"
                ),
            }
            for konflikt in spec.offene_konflikte
            if konflikt.entscheidung is None
        )

    if transformation_ergebnis is None:
        hindernisse.append({
            "code": "pflichtartefakt",
            "message": "Transformationsergebnis fehlt",
        })
    else:
        quelle = transformation_ergebnis["zeilen_quelle"]
        ziel = transformation_ergebnis["zeilen_ziel"]
        if ziel < quelle:
            hindernisse.append({
                "code": "zeilenverlust",
                "message": (
                    f"{quelle} Quellzeilen stehen nur {ziel} transformierte "
                    f"Zeile{'n' if ziel != 1 else ''} gegenüber — "
                    "Zeilenverlust blockiert die Abnahme"
                ),
            })
        elif ziel > quelle:
            hindernisse.append({
                "code": "zeilenanzahl",
                "message": (
                    f"{quelle} Quellzeilen stehen {ziel} transformierte Zeilen "
                    "gegenüber — die Zeilenanzahl ist nicht kongruent"
                ),
            })
        hindernisse.extend(
            {"code": "transformationsbefund", "message": befund}
            for befund in transformation_ergebnis["befunde"]
        )

    if fall is None:
        hindernisse.append({
            "code": "quellenbindung",
            "message": (
                "Abnahmebericht ist ohne Fallbindung nicht autoritativ; die "
                "Transformationsquelle wurde nicht physisch ueber das "
                "Eingangsregister neu gelesen"
            ),
        })
    elif spec is not None and transformation_ergebnis is not None:
        hindernisse.extend(
            {"code": "quellenbindung", "message": meldung}
            for meldung in _registrierte_quellenbindung_fehler(
                fall=fall,
                spec=spec,
                ergebnis=transformation_ergebnis,
            )
        )

    for code, name, wert in (
        ("pflichtartefakt", "Bestandsbericht VOR der Migration", bestandsbericht_vor),
        ("pflichtartefakt", "Bestandsbericht NACH der Migration", bestandsbericht_nach),
    ):
        if not wert:
            hindernisse.append({"code": code, "message": f"{name} fehlt"})
    if (
        bestandsbericht_vor
        and bestandsbericht_nach
        and bestandsbericht_vor == bestandsbericht_nach
    ):
        hindernisse.append({
            "code": "pflichtartefakt",
            "message": "Vor- und Nachbericht müssen zwei verschiedene Artefakte sein",
        })
    return hindernisse


def _abnahme_zusammenfassung(
    *,
    suite: Dict[str, Any],
    spec: Optional[TransformationsSpec],
    transformation_ergebnis: Optional[Dict[str, Any]],
    bestandsbericht_vor: Optional[str],
    bestandsbericht_nach: Optional[str],
    fall: Optional[Path] = None,
) -> Dict[str, Any]:
    """Kanonisches Berichtsverdikt für Produzent und G-2-Prüfung."""
    hindernisse = _abnahmehindernisse(
        suite=suite,
        spec=spec,
        transformation_ergebnis=transformation_ergebnis,
        bestandsbericht_vor=bestandsbericht_vor,
        bestandsbericht_nach=bestandsbericht_nach,
        fall=fall,
    )
    return {
        "bericht_bestanden": (
            suite["suite_bestanden"]
            and not any(urteil["befunde"] for urteil in suite["vertraege"])
            and not hindernisse
        ),
        "abnahmehindernisse": hindernisse,
    }


def baue_bericht(
    *,
    titel: str,
    stichtag_1: str,
    stichtag_2: str,
    suite: Dict[str, Any],
    spec: Optional[TransformationsSpec] = None,
    transformation_ergebnis: Optional[Dict[str, Any]] = None,
    bestandsbericht_vor: Optional[str] = None,
    bestandsbericht_nach: Optional[str] = None,
    fall: Optional[Path] = None,
) -> str:
    """Nur aus einem intern konsistenten Suite-Vertrag HTML bauen.

    Ohne die erneute Ableitung koennte auch der Bibliothekspfad eine gruene
    Zusammenfassung ueber einen roten Einzelvergleich rendern. Deshalb gilt
    derselbe fail-fast Contract wie fuer das Kommando. Ohne ``fall`` bleibt
    der Renderer nutzbar, erzeugt aber ausdruecklich nur einen roten,
    nichtautoritativen Bericht. Nur die interne Neuaufloesung und das erneute
    physische Lesen der registrierten Quelle kann den Bericht begruenen.
    """
    suite_fehler = _suite_fehler(suite)
    if suite_fehler:
        raise ValueError(
            "Suite-Ergebnis verletzt den Abnahmebericht-Vertrag: "
            + "; ".join(suite_fehler)
        )
    if transformation_ergebnis is not None:
        transformation_fehler = _transformation_ergebnis_fehler(
            transformation_ergebnis
        )
        if transformation_fehler:
            raise ValueError(
                "Transformationsergebnis verletzt den Abnahmebericht-Vertrag: "
                + "; ".join(transformation_fehler)
            )
    if spec is not None:
        spec_fehler = _spec_fehler(spec, transformation_ergebnis)
        if spec_fehler:
            raise ValueError(
                "TransformationsSpec verletzt den Abnahmebericht-Vertrag: "
                + "; ".join(spec_fehler)
            )
    abnahme = _abnahme_zusammenfassung(
        suite=suite,
        spec=spec,
        transformation_ergebnis=transformation_ergebnis,
        bestandsbericht_vor=bestandsbericht_vor,
        bestandsbericht_nach=bestandsbericht_nach,
        fall=fall,
    )
    teile: List[str] = [
        "<!DOCTYPE html>", "<html lang='de'><head><meta charset='utf-8'>",
        f"<title>{_e(titel)}</title><style>{_STIL}</style></head><body>",
        f"<h1>{_e(titel)}</h1>",
        f"<p>Migrationsstichtag: <b>{_e(stichtag_1)}</b> — "
        f"Folgestichtag: <b>{_e(stichtag_2)}</b></p>",
    ]
    mengenbefunde = list(suite["mengenbefunde"])
    pruefluecken = list(suite["pruefluecken"])
    if abnahme["bericht_bestanden"]:
        teile.append(
            f"<p class='gruen'>ALLE ABNAHMETESTS BESTANDEN "
            f"({suite['bestanden']:.0f} von {suite['anzahl']:.0f} "
            "Verträgen).</p>")
    elif suite["suite_bestanden"]:
        teile.append(
            "<p class='rot'>ABNAHMEBERICHT NICHT BESTANDEN — die "
            "Migrationssuite ist bestanden, aber "
            f"{len(abnahme['abnahmehindernisse'])} Abnahmehindernis(se) "
            "blockieren die vollständige Vorlage.</p>"
        )
    else:
        teile.append(
            "<p class='rot'>ABNAHMEBERICHT NICHT BESTANDEN — "
            f"{suite['fehlgeschlagen']:.0f} von "
            f"{suite['anzahl']:.0f} Verträgen FEHLGESCHLAGEN"
            + (f", {len(mengenbefunde)} Befund(e) der Prüfmenge"
               if mengenbefunde else "") + ".</p>")
    if abnahme["abnahmehindernisse"]:
        teile.append("<h2>Abnahmehindernisse</h2><ul>")
        teile.extend(
            f"<li class='rot'>{_e(hindernis['message'])}</li>"
            for hindernis in abnahme["abnahmehindernisse"]
        )
        teile.append("</ul>")
    teile.append(
        "<p class='hinweis'>Maschinelle Prüfaussage der deterministischen "
        "Migrationssuite. Die ABNAHME ist eine menschliche Entscheidung "
        "(Gate G-2) auf Grundlage dieses Berichts.</p>")

    # Die Klammer um die Menge: geprüft ist nur, was auch drin war.
    teile.append("<h2>Prüfmenge (Vollständigkeit und Duplikate)</h2>")
    erwartet = suite["erwartete_anzahl"]
    teile.append(
        f"<p>Geprüfte Verträge: <b>{suite['anzahl']:.0f}</b> — erwartete "
        "Vertragszahl der Lieferung: <b>"
        + (f"{int(erwartet):d}" if erwartet is not None
           else "nicht angegeben") + "</b></p>")
    if mengenbefunde:
        teile.append("<table><tr><th>Befund der Prüfmenge</th></tr>")
        teile.extend(f"<tr><td class='rot'>{_e(b)}</td></tr>"
                     for b in mengenbefunde)
        teile.append("</table>")
    else:
        teile.append("<p>Keine Befunde der Prüfmenge.</p>")

    teile.append("<h2>Prüflücken (was NICHT geprüft wurde)</h2>")
    if pruefluecken:
        teile.append(
            "<p class='hinweis'>Zu diesen Größen lag kein Erwartungswert "
            "vor. Sie sind WEDER bestanden NOCH fehlgeschlagen — sie sind "
            "ungeprüft und beim Lesen des Verdikts abzuziehen.</p><ul>")
        teile.extend(f"<li>{_e(l)}</li>" for l in pruefluecken)
        teile.append("</ul>")
    else:
        teile.append("<p>Keine — jede Prüfgröße war geliefert.</p>")

    teile.append("<h2>Abnahmetests je Prüfgröße</h2>")
    teile.append("<table><tr><th>Prüfgröße</th><th>Anzahl</th><th>OK</th>"
                 "<th>max. |Residuum|</th></tr>")
    teile.extend(_pruefgroessen_zeilen(suite))
    teile.append("</table>")

    teile.append("<h2>Einzelvergleiche (alle Werte)</h2>")
    teile.append(
        "<p>Je Vertrag und Prüfgröße: der vom Zielsystem gerechnete Wert "
        "gegen den gelieferten Erwartungswert.</p>")
    teile.append("<table><tr><th>Police</th><th>Prüfgröße</th>"
                 "<th>Zielsystem</th><th>Lieferung</th><th>Residuum</th>"
                 "<th>Urteil</th></tr>")
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            marke = ("<td class='gruen'>OK</td>" if p["ok"]
                     else "<td class='rot'>FEHLER</td>")
            teile.append(
                f"<tr><td>{_e(urteil['police_id'])}</td>"
                f"<td>{_e(p['groesse'])}</td>"
                f"<td class='zahl'>{p['system']:.2f}</td>"
                f"<td class='zahl'>{p['erwartet']:.2f}</td>"
                f"<td class='zahl'>{p['residuum']:.4f}</td>{marke}</tr>")
    teile.append("</table>")

    teile.append("<h2>Fehlschläge und Befunde</h2>")
    problem_zeilen = []
    for urteil in suite["vertraege"]:
        for p in urteil["pruefungen"]:
            if not p["ok"]:
                problem_zeilen.append(
                    f"<tr><td>{_e(urteil['police_id'])}</td>"
                    f"<td>{_e(p['groesse'])}</td>"
                    f"<td class='zahl'>{p['system']:.2f}</td>"
                    f"<td class='zahl'>{p['erwartet']:.2f}</td>"
                    f"<td class='zahl'>{p['residuum']:.2f}</td></tr>")
        for befund in urteil["befunde"]:
            problem_zeilen.append(
                f"<tr><td>{_e(urteil['police_id'])}</td>"
                f"<td colspan='4'>Befund: {_e(befund)}</td></tr>")
    if problem_zeilen:
        teile.append("<table><tr><th>Police</th><th>Prüfgröße</th>"
                     "<th>Zielsystem</th><th>Lieferung</th>"
                     "<th>Residuum</th></tr>")
        teile.extend(problem_zeilen)
        teile.append("</table>")
    else:
        teile.append("<p>Keine.</p>")

    if spec is not None:
        teile.append("<h2>Transformation (fachliche Abnahme des Mappings)"
                     "</h2>")
        teile.append(
            f"<p>Quelle: {_e(spec.quelle_datei)} "
            f"(SHA-256 {_e(spec.quelle_sha256[:16])}…), "
            f"Akteur: {_e(spec.akteur)}</p>")
        teile.append("<table><tr><th>Quellspalten</th><th>Zielfeld</th>"
                     "<th>Art</th><th>Details</th><th>Begründung</th></tr>")
        teile.extend(_mapping_zeilen(spec))
        teile.append("</table>")
        if spec.offene_konflikte:
            teile.append("<h3>Konflikte und Entscheidungen</h3><ul>")
            for k in spec.offene_konflikte:
                status = (
                    f"entschieden ({_e(k.entscheider)}): {_e(k.entscheidung)}"
                    if k.entscheidung is not None else
                    "<span class='rot'>OFFEN — blockiert die Anwendung</span>")
                teile.append(
                    f"<li><b>{_e(k.quellspalte)}</b>: {_e(k.frage)} — "
                    f"{status}</li>")
            teile.append("</ul>")

    if transformation_ergebnis is not None:
        te = transformation_ergebnis
        teile.append("<h3>Transformationsergebnis (Anwendung des Mappings)"
                     "</h3>")
        befunde = list(te.get("befunde", []))
        klasse = "gruen" if not befunde else "rot"
        teile.append(
            f"<p>Quellzeilen: <b>{int(te['zeilen_quelle']):d}</b> — "
            f"transformiert: <b>{int(te['zeilen_ziel']):d}</b> — "
            f"Zeilen mit Befund (nicht ausgegeben): "
            f"<span class='{klasse}'>{len(befunde):d}</span></p>")
        if befunde:
            teile.append("<ul>")
            teile.extend(f"<li>{_e(b)}</li>" for b in befunde)
            teile.append("</ul>")

    if bestandsbericht_vor or bestandsbericht_nach:
        teile.append("<h2>Bestandsberichte (visueller Vergleich)</h2><ul>")
        if bestandsbericht_vor:
            href = bestandsbericht_vor.replace("\\", "/")
            teile.append(f"<li>VOR der Migration: <a href="
                         f"'{_e(href)}'>"
                         f"{_e(href)}</a></li>")
        if bestandsbericht_nach:
            href = bestandsbericht_nach.replace("\\", "/")
            teile.append(f"<li>NACH der Migration: <a href="
                         f"'{_e(href)}'>"
                         f"{_e(href)}</a></li>")
        teile.append("</ul>")

    teile.append("</body></html>")
    return "\n".join(teile) + "\n"


def schreibe_bericht(pfad: Path, **kwargs: Any) -> Path:
    """Bericht bauen und schreiben; gibt den Pfad zurück."""
    pfad = Path(pfad)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    # Der Bericht ist ein gehashtes Beweisartefakt. ``Path.write_text``
    # uebersetzt unter Windows LF zu CRLF und macht denselben Renderer-Vertrag
    # damit plattformabhaengig. Bytes halten die kanonischen LF unveraendert.
    pfad.write_bytes(baue_bericht(**kwargs).encode("utf-8"))
    return pfad


_BERICHT_ERZEUGUNG_FELDER = {
    "titel",
    "stichtag_1",
    "stichtag_2",
    "spec",
    "transformation_ergebnis",
    "bestandsbericht_vor",
    "bestandsbericht_nach",
}


def _bericht_erzeugung(
    *,
    titel: str,
    stichtag_1: str,
    stichtag_2: str,
    spec: Optional[TransformationsSpec],
    transformation_ergebnis: Optional[Dict[str, Any]],
    bestandsbericht_vor: Optional[str],
    bestandsbericht_nach: Optional[str],
) -> Dict[str, Any]:
    """Kanonische, JSON-faehige Eingaben des deterministischen Renderers."""
    return {
        "titel": titel,
        "stichtag_1": stichtag_1,
        "stichtag_2": stichtag_2,
        "spec": (
            json.loads(spec.model_dump_json()) if spec is not None else None
        ),
        "transformation_ergebnis": transformation_ergebnis,
        "bestandsbericht_vor": bestandsbericht_vor,
        "bestandsbericht_nach": bestandsbericht_nach,
    }


def _bericht_fehler(
    *,
    erzeugung: Any,
    suite: Dict[str, Any],
    bericht_pfad: Path,
    erwartete_stichtage: List[str],
    fall: Path,
) -> List[str]:
    """HTML aus dem persistierten Renderer-Vertrag bytegenau reproduzieren."""
    if not isinstance(erzeugung, dict) or set(erzeugung) != _BERICHT_ERZEUGUNG_FELDER:
        return [
            "Abnahmebericht-Erzeugung muss exakt die kanonischen "
            f"Renderer-Felder {sorted(_BERICHT_ERZEUGUNG_FELDER)} enthalten"
        ]
    fehler: List[str] = []
    for feld in ("titel", "stichtag_1", "stichtag_2"):
        if not isinstance(erzeugung.get(feld), str) or not erzeugung[feld]:
            fehler.append(f"Abnahmebericht-Erzeugung.{feld} muss nichtleer sein")
    if [erzeugung.get("stichtag_1"), erzeugung.get("stichtag_2")] != list(
        erwartete_stichtage
    ):
        fehler.append("Abnahmebericht-Erzeugung bindet andere Stichtage")
    for feld in ("bestandsbericht_vor", "bestandsbericht_nach"):
        if erzeugung.get(feld) is not None and not isinstance(
            erzeugung[feld], str
        ):
            fehler.append(f"Abnahmebericht-Erzeugung.{feld} ist kein String/null")

    spec: Optional[TransformationsSpec] = None
    spec_roh = erzeugung.get("spec")
    if spec_roh is not None:
        try:
            spec = TransformationsSpec.model_validate(spec_roh)
        except (TypeError, ValueError) as exc:
            fehler.append(f"Abnahmebericht-Erzeugung.spec ist ungueltig: {exc}")
    transformation = erzeugung.get("transformation_ergebnis")
    if transformation is not None and not isinstance(transformation, dict):
        fehler.append(
            "Abnahmebericht-Erzeugung.transformation_ergebnis ist kein Objekt/null"
        )
    elif transformation is not None:
        fehler.extend(_transformation_ergebnis_fehler(transformation))
    if fehler:
        return fehler
    abnahme = _abnahme_zusammenfassung(
        suite=suite,
        spec=spec,
        transformation_ergebnis=transformation,
        bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
        bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
        fall=fall,
    )
    if not abnahme["bericht_bestanden"]:
        fehler.extend(
            "Abnahmebericht ist nicht bestanden: " + hindernis["message"]
            for hindernis in abnahme["abnahmehindernisse"]
        )
        if not suite["suite_bestanden"]:
            fehler.append("Abnahmebericht ist nicht auf einer bestandenen Suite erzeugt")
        if fehler:
            return fehler
    try:
        erwartet = baue_bericht(
            titel=erzeugung["titel"],
            stichtag_1=erzeugung["stichtag_1"],
            stichtag_2=erzeugung["stichtag_2"],
            suite=suite,
            spec=spec,
            transformation_ergebnis=transformation,
            bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
            bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
            fall=fall,
        )
        # Bytes lesen, nicht Text: read_text uebersetzt CRLF/CR still nach LF
        # und laesst damit eine umkodierte Fassung als "bytegenau" durchgehen.
        gefunden = bericht_pfad.read_bytes().decode("utf-8")
    except Exception as exc:  # noqa: BLE001 — frei editierbarer Beleg blockiert
        return [f"Abnahmebericht ist nicht reproduzierbar: {exc}"]
    if gefunden != erwartet:
        return [
            "Abnahmebericht stimmt nicht bytegenau mit seiner deterministischen "
            "Erzeugung aus Suite und Renderer-Vertrag ueberein"
        ]
    return []


# --------------------------------------------------------------------------- #
# Kommando (Toolbox-Gate-Vertrag) — die Bibliotheks-API oben bleibt unberührt.
# --------------------------------------------------------------------------- #

#: Pflichtfelder eines Einzelvergleichs im Suite-Ergebnis.
_PRUEFUNG_FELDER = ("groesse", "system", "erwartet", "residuum", "ok")


def _ist_endliche_zahl(wert: Any) -> bool:
    """JSON-Zahl ohne bool und ohne NaN/Unendlichkeit."""
    if type(wert) not in (int, float):
        return False
    try:
        return math.isfinite(wert)
    except OverflowError:
        # Beliebig grosse JSON-Integer sind syntaktisch gueltig, lassen sich
        # aber weder als Suite-Float vergleichen noch im Bericht formatieren.
        return False


def _erwartete_mengenbefunde(
    vertraege: List[Dict[str, Any]], erwartete_anzahl: Optional[int]
) -> List[str]:
    """Mengenbefunde aus Anzahl und Police-IDs wie die Suite ableiten."""
    befunde: List[str] = []
    if erwartete_anzahl is not None and erwartete_anzahl != len(vertraege):
        fehlend = erwartete_anzahl - len(vertraege)
        richtung = (
            f"{fehlend} Verträge fehlen in der Prüfmenge"
            if fehlend > 0
            else f"{-fehlend} Verträge zu viel in der Prüfmenge"
        )
        befunde.append(
            f"Vollständigkeit: {len(vertraege)} geprüfte Verträge gegen "
            f"{erwartete_anzahl} erwartete — {richtung}. Prüfe die "
            "Lieferung und die Transformation (verworfene Zeilen, Filter)."
        )
    zaehler: Dict[str, int] = {}
    for urteil in vertraege:
        police_id = urteil["police_id"]
        zaehler[police_id] = zaehler.get(police_id, 0) + 1
    for police_id, anzahl in zaehler.items():
        if anzahl > 1:
            befunde.append(
                f"Policennummer {police_id!r} kommt {anzahl}-mal in der "
                "Prüfmenge vor — derselbe Vertrag wird mehrfach gezählt; "
                "die Prüfmenge ist keine Bestandsmenge."
            )
    return befunde


def _erwartete_pruefluecken(
    vertraege: List[Dict[str, Any]], erwartete_anzahl: Optional[int]
) -> List[str]:
    """Top-Level-Pruefluecken aus atomaren Vertragsluecken ableiten."""
    luecken_zaehler: Dict[str, int] = {}
    for urteil in vertraege:
        for groesse in urteil["nicht_geprueft"]:
            luecken_zaehler[groesse] = luecken_zaehler.get(groesse, 0) + 1
    pruefluecken = [
        f"{groesse}: bei {anzahl} von {len(vertraege)} Verträgen NICHT "
        "geprüft (kein gelieferter Erwartungswert oder abgebrochene Prüfung)."
        for groesse, anzahl in sorted(luecken_zaehler.items())
    ]
    if erwartete_anzahl is None:
        pruefluecken.append(
            "Vollständigkeit: keine erwartete Vertragszahl übergeben "
            "(erwartete_anzahl) — dass die Prüfmenge dem gelieferten "
            "Bestand entspricht, ist NICHT geprüft."
        )
    return pruefluecken


def _suite_fehler(daten: Any) -> List[str]:
    """Struktur- und Konsistenzfehler eines Suite-Ergebnis-JSON.

    Jede Ableitung wird von innen nach aussen neu berechnet: Residuum und
    ``ok`` aus System-/Erwartungswert, ``bestanden`` aus Einzelurteilen und
    Befunden, danach Mengenbefunde, Pruefluecken, Zaehler und Suiteurteile.
    Ein von Hand nachgebessertes ``suite_bestanden`` würde sonst eine Urkunde
    über ein Urteil erzeugen, das die Suite nie gefällt hat. Leere Liste =
    verwendbar.
    """
    if not isinstance(daten, dict):
        return ["Suite-Ergebnis ist kein JSON-Objekt"]
    fehler: List[str] = []
    for feld in ("anzahl", "bestanden", "fehlgeschlagen", "suite_bestanden",
                 "erwartete_anzahl", "mengenbefunde", "pruefluecken",
                 "vollstaendig_geprueft", "vertraege"):
        if feld not in daten:
            fehler.append(f"Feld {feld!r} fehlt")
    if fehler:
        return fehler
    for feld in ("anzahl", "bestanden", "fehlgeschlagen"):
        if type(daten[feld]) is not int:
            fehler.append(f"Feld {feld!r} ist keine ganze Zahl")
    for feld in ("suite_bestanden", "vollstaendig_geprueft"):
        if type(daten[feld]) is not bool:
            fehler.append(f"Feld {feld!r} ist kein boolescher Wert")
    for feld in ("mengenbefunde", "pruefluecken"):
        if not isinstance(daten[feld], list):
            fehler.append(f"Feld {feld!r} ist keine Liste")
        elif any(not isinstance(eintrag, str) for eintrag in daten[feld]):
            fehler.append(f"Feld {feld!r} enthält einen Nicht-String")
    # Die erwartete Vertragszahl wird im Bericht als ganze Zahl gesetzt
    # (``int(...)``) und im Ledger gefuehrt: ein falscher Typ waere dort
    # ein Absturz oder eine stille Abschneidung (4.7 -> 4) statt eines
    # benannten Contract-Bruchs.
    erwartet = daten["erwartete_anzahl"]
    if erwartet is not None and (isinstance(erwartet, bool)
                                 or not isinstance(erwartet, int)):
        fehler.append(
            "Feld 'erwartete_anzahl' ist weder eine ganze Zahl noch null")
    if fehler:
        return fehler
    vertraege = daten["vertraege"]
    if not isinstance(vertraege, list):
        return ["Feld 'vertraege' ist keine Liste"]
    if not vertraege:
        return [
            "Suite-Ergebnis ohne einen einzigen Vertrag: eine leere "
            "Prüfmenge ist keine bestandene Abnahme — prüfe Lieferung "
            "und Transformation (wurden 0 Verträge übernommen?)"
        ]
    for i, u in enumerate(vertraege):
        wo = f"vertraege[{i}]"
        if not isinstance(u, dict):
            fehler.append(f"{wo} ist kein Objekt")
            continue
        for feld in ("police_id", "bestanden", "befunde", "pruefungen",
                     "nicht_geprueft"):
            if feld not in u:
                fehler.append(f"{wo}: Feld {feld!r} fehlt")
        if "police_id" in u and (
            not isinstance(u["police_id"], str) or not u["police_id"]
        ):
            fehler.append(f"{wo}: 'police_id' ist kein nichtleerer String")
        if "bestanden" in u and type(u["bestanden"]) is not bool:
            fehler.append(f"{wo}: 'bestanden' ist kein boolescher Wert")
        for feld in ("befunde", "nicht_geprueft"):
            if feld in u and not isinstance(u[feld], list):
                fehler.append(f"{wo}: {feld!r} ist keine Liste")
            elif feld in u and any(
                not isinstance(eintrag, str) for eintrag in u[feld]
            ):
                fehler.append(f"{wo}: {feld!r} enthält einen Nicht-String")
        pruefungen = u.get("pruefungen")
        if not isinstance(pruefungen, list):
            fehler.append(f"{wo}: 'pruefungen' ist keine Liste")
            continue
        for j, p in enumerate(pruefungen):
            if not isinstance(p, dict):
                fehler.append(f"{wo}.pruefungen[{j}] ist kein Objekt")
                continue
            for feld in _PRUEFUNG_FELDER:
                if feld not in p:
                    fehler.append(
                        f"{wo}.pruefungen[{j}]: Feld {feld!r} fehlt")
            if "groesse" in p and (
                not isinstance(p["groesse"], str) or not p["groesse"]
            ):
                fehler.append(
                    f"{wo}.pruefungen[{j}]: 'groesse' ist kein "
                    "nichtleerer String"
                )
            for feld in ("system", "erwartet", "residuum"):
                wert = p.get(feld)
                if feld in p and not _ist_endliche_zahl(wert):
                    fehler.append(
                        f"{wo}.pruefungen[{j}]: {feld!r} ist keine "
                        "endliche Zahl")
            if "ok" in p and type(p["ok"]) is not bool:
                fehler.append(
                    f"{wo}.pruefungen[{j}]: 'ok' ist kein boolescher Wert"
                )
    if fehler:
        return fehler

    berechnete_vertragsurteile: List[bool] = []
    for i, urteil in enumerate(vertraege):
        wo = f"vertraege[{i}]"
        berechnete_pruefurteile: List[bool] = []
        for j, pruefung in enumerate(urteil["pruefungen"]):
            pruef_wo = f"{wo}.pruefungen[{j}]"
            residuum = pruefung["system"] - pruefung["erwartet"]
            if pruefung["residuum"] != residuum:
                fehler.append(
                    f"{pruef_wo}: 'residuum' ({pruefung['residuum']!r}) "
                    f"passt nicht zu system - erwartet ({residuum!r})"
                )
            berechnet_ok = math.isclose(
                pruefung["system"],
                pruefung["erwartet"],
                rel_tol=REL_TOL,
                abs_tol=ABS_TOL,
            )
            berechnete_pruefurteile.append(berechnet_ok)
            if pruefung["ok"] is not berechnet_ok:
                fehler.append(
                    f"{pruef_wo}: 'ok' ({pruefung['ok']!r}) passt nicht "
                    f"zum neu berechneten Vergleichsurteil ({berechnet_ok!r})"
                )
        berechnet_bestanden = (
            bool(berechnete_pruefurteile)
            and not urteil["befunde"]
            and all(berechnete_pruefurteile)
        )
        berechnete_vertragsurteile.append(berechnet_bestanden)
        if urteil["bestanden"] is not berechnet_bestanden:
            fehler.append(
                f"{wo}: 'bestanden' ({urteil['bestanden']!r}) passt nicht "
                "zu den Einzelprüfungen und Befunden "
                f"({berechnet_bestanden!r})"
            )

    n = len(vertraege)
    n_ok = sum(berechnete_vertragsurteile)
    if daten["anzahl"] != n:
        fehler.append(
            f"'anzahl' ({daten['anzahl']}) passt nicht zu {n} Urteilen")
    if daten["bestanden"] != n_ok:
        fehler.append(
            f"'bestanden' ({daten['bestanden']}) passt nicht zu {n_ok} "
            "bestandenen Urteilen")
    if daten["fehlgeschlagen"] != n - n_ok:
        fehler.append(
            f"'fehlgeschlagen' ({daten['fehlgeschlagen']}) passt nicht zu "
            f"{n - n_ok} fehlgeschlagenen Urteilen")
    erwartete_mengenbefunde = _erwartete_mengenbefunde(
        vertraege, daten["erwartete_anzahl"]
    )
    if daten["mengenbefunde"] != erwartete_mengenbefunde:
        fehler.append(
            "'mengenbefunde' passen nicht zu erwarteter Anzahl und Police-IDs"
        )
    berechnet_suite_bestanden = n_ok == n and not erwartete_mengenbefunde
    if daten["suite_bestanden"] is not berechnet_suite_bestanden:
        fehler.append(
            f"'suite_bestanden' ({daten['suite_bestanden']}) passt nicht zu "
            f"{n_ok} von {n} bestandenen Urteilen und "
            f"{len(erwartete_mengenbefunde)} Befund(en) der Prüfmenge")
    erwartete_pruefluecken = _erwartete_pruefluecken(
        vertraege, daten["erwartete_anzahl"]
    )
    if daten["pruefluecken"] != erwartete_pruefluecken:
        fehler.append(
            "'pruefluecken' passen nicht zu den ungeprüften "
            "Vertragsgrößen und der erwarteten Anzahl"
        )
    berechnet_vollstaendig = not erwartete_pruefluecken
    if daten["vollstaendig_geprueft"] is not berechnet_vollstaendig:
        fehler.append(
            f"'vollstaendig_geprueft' ({daten['vollstaendig_geprueft']}) "
            f"passt nicht zu {len(erwartete_pruefluecken)} Prüflücke(n)")
    return fehler


def _suite_zusammenfassung(suite: Dict[str, Any]) -> Dict[str, Any]:
    """Kanonische Kennzahlen ausschliesslich aus atomaren Suite-Fakten.

    Aufrufer validieren vorher mit :func:`_suite_fehler`. Die erneute
    Ableitung bleibt trotzdem zentral, damit weder der Berichtsproduzent noch
    G-2 auf frei editierbare Top-Level- oder Ledger-Zaehler vertrauen.
    """
    vertraege = suite["vertraege"]
    vertragsurteile = [
        bool(urteil["pruefungen"])
        and not urteil["befunde"]
        and all(
            math.isclose(
                pruefung["system"],
                pruefung["erwartet"],
                rel_tol=REL_TOL,
                abs_tol=ABS_TOL,
            )
            for pruefung in urteil["pruefungen"]
        )
        for urteil in vertraege
    ]
    n = len(vertraege)
    n_ok = sum(vertragsurteile)
    mengenbefunde = _erwartete_mengenbefunde(
        vertraege, suite["erwartete_anzahl"]
    )
    pruefluecken = _erwartete_pruefluecken(
        vertraege, suite["erwartete_anzahl"]
    )
    residuen = [
        abs(pruefung["system"] - pruefung["erwartet"])
        for urteil in vertraege for pruefung in urteil["pruefungen"]
    ]
    return {
        "anzahl": n,
        "erwartete_anzahl": suite["erwartete_anzahl"],
        "bestanden": n_ok,
        "fehlgeschlagen": n - n_ok,
        "suite_bestanden": n_ok == n and not mengenbefunde,
        "befunde": sum(len(urteil["befunde"]) for urteil in vertraege),
        "mengenbefunde": len(mengenbefunde),
        "pruefungen": sum(len(urteil["pruefungen"]) for urteil in vertraege),
        "max_residuum": max(residuen, default=0.0),
        "vollstaendig_geprueft": not pruefluecken,
        "pruefluecken": pruefluecken,
    }


def _bestands_suite_fehler(
    suite: Dict[str, Any],
    *,
    stichtag_1: str,
    stichtag_2: str,
    erwartetes_system: Dict[str, str],
) -> List[str]:
    """Vollstaendigkeit und Fallstand der Suite im Bestands-Scope."""
    fehler: List[str] = []
    erwartet = {
        "stichtag_1": stichtag_1,
        "stichtag_2": stichtag_2,
    }
    for feld, wert in erwartet.items():
        if suite.get(feld) != wert:
            fehler.append(f"{feld!r} muss {wert!r} binden")
    if type(suite.get("vollstaendig_geprueft")) is not bool:
        fehler.append("'vollstaendig_geprueft' muss ein boolescher Wert sein")
    elif not suite["vollstaendig_geprueft"]:
        fehler.append(
            "Bestands-Scope verlangt eine vollstaendig gepruefte "
            "Migrationssuite ohne Pruefluecken"
        )
    bestand_sha256 = suite.get("bestand_sha256")
    if (
        not isinstance(bestand_sha256, str)
        or len(bestand_sha256) != 64
        or any(zeichen not in "0123456789abcdef" for zeichen in bestand_sha256)
    ):
        fehler.append("'bestand_sha256' muss einen SHA-256 binden")
    if suite.get("system") != erwartetes_system:
        fehler.append("Migrationssuite bindet nicht den aktuellen Systemstand")
    return fehler


def _b1_fehler(
    *,
    ledger_pfad: Path,
    fall: Path,
    repo_root: Path,
    suite: Dict[str, Any],
    erwartetes_system: Dict[str, str],
) -> List[str]:
    """B1-Ledger laden, Bytes hashen und produktive B1-Engines neu fahren."""
    try:
        payload = json.loads(ledger_pfad.read_text(encoding="utf-8"))
        entry = GateLedgerEntry.from_dict(payload)
    except (OSError, UnicodeError, ValueError, TypeError) as exc:
        return [f"B1-Ledger ungueltig: {exc}"]
    fehler: List[str] = []
    erwartet = {
        "gate": bestand_validate.GATE,
        "command": "bestand_validate",
        "gate_version": bestand_validate.GATE_VERSION,
        "required": True,
        "status": "passed",
    }
    for feld, wert in erwartet.items():
        if getattr(entry, feld) != wert:
            fehler.append(f"B1-Ledger.{feld} ist {getattr(entry, feld)!r} statt {wert!r}")
    if entry.summary.get("exit_code") != 0 or entry.summary.get("all_passed") is not True:
        fehler.append("B1-Ledger traegt kein konsistentes gruenes Einzelurteil")
    if entry.summary.get("system") != erwartetes_system:
        fehler.append("B1-Ledger bindet nicht den aktuellen Systemstand")

    portfolio_input = entry.summary.get("portfolio_input")
    portfolio_sha256 = entry.summary.get("portfolio_sha256")
    if not isinstance(portfolio_input, str) or not portfolio_input:
        fehler.append("B1-Ledger.summary.portfolio_input fehlt")
    if (
        not isinstance(portfolio_sha256, str)
        or len(portfolio_sha256) != 64
        or any(zeichen not in "0123456789abcdef" for zeichen in portfolio_sha256)
    ):
        fehler.append("B1-Ledger.summary.portfolio_sha256 ist kein SHA-256")
    if isinstance(portfolio_input, str) and entry.input_hashes.get(
        portfolio_input
    ) != portfolio_sha256:
        fehler.append("B1-Ledger bindet seine benannte Portfolio-Rolle nicht")
    if portfolio_sha256 != suite.get("bestand_sha256"):
        fehler.append("B1-Ledger und Migrationssuite binden verschiedene Bestaende")

    rollen = entry.summary.get("eingangsrollen")
    erlaubte_rollen = {"portfolio", "historie", "scheiben", "ledger", "config"}
    if (
        not isinstance(rollen, dict)
        or "portfolio" not in rollen
        or not set(rollen) <= erlaubte_rollen
        or any(not isinstance(name, str) or not name for name in rollen.values())
        or len(set(rollen.values())) != len(rollen)
    ):
        fehler.append("B1-Ledger.summary.eingangsrollen ist ungueltig")
        rollen = {}
    elif set(entry.input_hashes) != set(rollen.values()):
        fehler.append("B1-Eingangsrollen und input_hashes sind nicht deckungsgleich")
    if rollen.get("portfolio") != portfolio_input:
        fehler.append("B1-Ledger benennt widerspruechliche Portfolio-Rollen")

    aktuelle_eingaben: Dict[str, Path] = {}
    portfolio_gebunden = False
    for name, erwartet_hash in entry.input_hashes.items():
        roh = Path(name)
        vorhanden = roh.resolve() if roh.is_absolute() else (repo_root / roh).resolve()
        if not vorhanden.is_file():
            fehler.append(f"B1-Eingangsartefakt {name!r} fehlt")
            continue
        gefunden = sha256(vorhanden.read_bytes()).hexdigest()
        if gefunden != erwartet_hash:
            fehler.append(f"B1-Eingangsartefakt {name!r} hat einen anderen SHA-256")
        if name == portfolio_input and gefunden == erwartet_hash == portfolio_sha256:
            portfolio_gebunden = True
        rolle = next(
            (rollenname for rollenname, rollenpfad in rollen.items()
             if rollenpfad == name),
            None,
        )
        if rolle is not None:
            aktuelle_eingaben[rolle] = vorhanden
            if rolle == "portfolio":
                try:
                    vorhanden.relative_to(fall.resolve())
                except ValueError:
                    fehler.append("B1-Portfolio-Rolle liegt ausserhalb des Falls")
    if not portfolio_gebunden:
        fehler.append(
            "B1-Ledger bindet nicht seine aktuelle Portfolio-Datei"
        )

    bis_roh = entry.summary.get("bis")
    bis: Optional[_dt.date] = None
    if bis_roh is not None:
        try:
            bis = _dt.date.fromisoformat(bis_roh)
        except (TypeError, ValueError):
            fehler.append("B1-Ledger.summary.bis ist kein ISO-Datum oder null")
    if "ledger" in rollen and ("historie" not in rollen or bis is None):
        fehler.append("B1-Ledger-Rolle ledger verlangt historie und bis")
    if "ledger" not in rollen and bis_roh is not None:
        fehler.append("B1-Ledger.summary.bis ist nur mit ledger zulaessig")

    geprueft: Dict[str, int] = {}
    if set(aktuelle_eingaben) == set(rollen):
        geprueft, b1_errors, b1_usage_errors = bestand_validate.pruefe_b1_eingaenge(
            aktuelle_eingaben,
            bis=bis,
        )
        fehler.extend(
            f"B1-Neupruefung [{befund.get('code')}]: {befund.get('message')}"
            for befund in [*b1_errors, *b1_usage_errors]
        )
        for name, wert in geprueft.items():
            if entry.summary.get(name) != wert:
                fehler.append(
                    f"B1-Ledger.summary.{name} stimmt nicht mit der "
                    "erneuten B1-Pruefung ueberein"
                )

    portfolio_zeilen = geprueft.get("portfolio_zeilen")
    if (
        type(portfolio_zeilen) is not int
        or portfolio_zeilen != suite.get("anzahl")
        or portfolio_zeilen != suite.get("erwartete_anzahl")
    ):
        fehler.append(
            "B1-Portfoliozeilen, Suite-Pruefmenge und erwartete Anzahl "
            "muessen uebereinstimmen"
        )
    return fehler


def _build_parser() -> GateArgumentParser:
    parser = GateArgumentParser(
        gate_contract=CLI_CONTRACT,
        prog="python -m rechner_pipeline.gates.abnahmebericht",
        description=(
            "Migrationsabnahmebericht rendern und protokollieren — die "
            "Entscheidungsvorlage des MENSCHLICHEN Gates G-2, keine "
            "Abnahme."
        ),
    )
    parser.add_argument(
        "--fall", default=None,
        help="Fall-Arbeitsbereich; setzt die Vorgaben fuer --bericht und "
        "--diagnostics-dir.")
    parser.add_argument(
        "--suite", default=None,
        help="JSON-Ergebnis von qa.migrationssuite.pruefe_bestand (Pflicht).")
    parser.add_argument("--titel", default=None, help="Berichtstitel (Pflicht).")
    parser.add_argument(
        "--stichtag-1", dest="stichtag_1", default=None,
        help="Migrationsstichtag, ISO-Datum (Pflicht).")
    parser.add_argument(
        "--stichtag-2", dest="stichtag_2", default=None,
        help="Folgestichtag, ISO-Datum (Pflicht).")
    parser.add_argument(
        "--spec", default=None,
        help="TransformationsSpec als JSON (Pflichtartefakt).")
    parser.add_argument(
        "--transformation-ergebnis", dest="transformation_ergebnis",
        default=None,
        help="JSON der Mapping-Anwendung (zeilen_quelle/zeilen_ziel/befunde).")
    parser.add_argument(
        "--bestandsbericht-vor", dest="bestandsbericht_vor", default=None,
        help="Bestandsbericht VOR der Migration (Pflichtartefakt).")
    parser.add_argument(
        "--bestandsbericht-nach", dest="bestandsbericht_nach", default=None,
        help="Bestandsbericht NACH der Migration (Pflichtartefakt).")
    parser.add_argument(
        "--b1-ledger", dest="b1_ledger", default=None,
        help="Gruenes B1-Ledger; im Bestands-Scope Default: "
        "<fall>/abgeleitet/diagnostics/bestand_validate.gate.json.")
    parser.add_argument(
        "--bericht", default=None,
        help="Zielpfad des HTML-Berichts (Vorgabe mit --fall: "
        "<fall>/abgeleitet/berichte/migrationsabnahme.html).")
    parser.add_argument("--repo-root", dest="repo_root", default=None)
    parser.add_argument(
        "--diagnostics-dir", dest="diagnostics_dir", default=None,
        help="Verzeichnis fuer den Gate-Ledger-Eintrag.")
    add_request_json_arg(parser)
    return parser


def main(argv: Optional[List[str]] = None):
    started_at = utc_now()
    parser = _build_parser()
    args = parse_gate_args(parser, argv)

    fall = Path(args.fall).resolve() if args.fall else None
    diagnostics_dir = (
        Path(args.diagnostics_dir) if args.diagnostics_dir
        else (fall / "abgeleitet" / "diagnostics" if fall
              else Path.cwd() / "runs" / "diagnostics")
    )

    def _begin_ledger():
        return begin_gate_ledger_attempt(
            command=COMMAND,
            gate=GATE,
            gate_version=GATE_VERSION,
            diagnostics_dir=diagnostics_dir,
            repo_root=Path(args.repo_root) if args.repo_root else None,
            started_at=started_at,
            command_line=argv if argv is not None else sys.argv[1:],
        )

    ledger_ziel = diagnostics_dir / f"{COMMAND}{GATE_LEDGER_SUFFIX}"
    vorab_artefakte = {
        name: Path(wert)
        for name, wert in (
            ("--suite", args.suite),
            ("--spec", args.spec),
            ("--transformation-ergebnis", args.transformation_ergebnis),
            ("--bestandsbericht-vor", args.bestandsbericht_vor),
            ("--bestandsbericht-nach", args.bestandsbericht_nach),
            ("--b1-ledger", args.b1_ledger),
            ("--bericht", args.bericht),
        )
        if wert
    }
    if not args.bericht and fall is not None:
        vorab_artefakte["--bericht"] = (
            fall / "abgeleitet" / "berichte" / "migrationsabnahme.html"
        )
    ledger_kollision_vorab = bool(_pfadrollen_kollisionen({
        **vorab_artefakte,
        "Gate-Ledger": ledger_ziel,
    }))
    if not ledger_kollision_vorab:
        ledger_start_fehler = _begin_ledger()
        if ledger_start_fehler is not None:
            return ledger_start_fehler

    def _finalize(result):
        if ledger_kollision_vorab:
            log(
                f"{COMMAND}: Gate-Ledger nicht geschrieben, weil sein "
                "Zielpfad mit einem Ein- oder Ausgabeartefakt kollidiert"
            )
            return result
        ledger_start_fehler = _begin_ledger()
        if ledger_start_fehler is not None:
            return ledger_start_fehler
        return finalize_gate_ledger(result)

    def _usage(message: str, *, ledger_schreiben: bool = True):
        fehler = [{"code": "usage", "message": message}]
        if not ledger_schreiben:
            # Der Ledger bleibt ungeschrieben, damit der Lauf das
            # kollidierende Artefakt nicht zerstoert. Dann kann an diesem
            # Pfad ein aelterer gruener Beleg stehen bleiben — das gehoert
            # in die Antwort auf stdout und nicht nur ins stderr-Log, sonst
            # haelt eine Automatisierung den Altbeleg fuer aktuell.
            fehler.append({
                "code": "ledger_nicht_geschrieben",
                "message": (
                    "Gate-Ledger wurde nicht geschrieben, weil sein Zielpfad "
                    "mit einem Ein- oder Ausgabeartefakt kollidiert. Eine "
                    "vorhandene Datei an diesem Pfad belegt NICHT diesen Lauf."
                ),
            })
        result = build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.USAGE,
            errors=fehler,
        )
        if not ledger_schreiben:
            log(
                f"{COMMAND}: Gate-Ledger nicht geschrieben, weil sein "
                "Zielpfad mit einem Ein- oder Ausgabeartefakt kollidiert"
            )
            return result
        return _finalize(result)

    fall_scope: Optional[str] = None
    if fall is not None and (fall / fall_mod.FALL_MANIFEST).is_file():
        try:
            fall_scope = fall_mod.lade_scope(fall)
        except fall_mod.FallFehler as exc:
            return _usage(f"ungueltiger Fall-Scope: {exc}")
    bestands_scope = fall_scope == "bestand"

    fehlende_flags = [
        name for name, wert in (
            ("--suite", args.suite), ("--titel", args.titel),
            ("--stichtag-1", args.stichtag_1),
            ("--stichtag-2", args.stichtag_2))
        if not wert
    ]
    if fehlende_flags:
        return _usage(f"erforderlich: {', '.join(fehlende_flags)}")
    if not args.bericht and fall is None:
        return _usage(
            "Zielpfad des Berichts unbestimmt: --bericht angeben oder "
            "--fall setzen (dann <fall>/abgeleitet/berichte/"
            "migrationsabnahme.html)")

    fehlende_artefakte = [
        name for name, wert in (
            ("--spec", args.spec),
            ("--transformation-ergebnis", args.transformation_ergebnis),
            ("--bestandsbericht-vor", args.bestandsbericht_vor),
            ("--bestandsbericht-nach", args.bestandsbericht_nach),
        )
        if not wert
    ]
    if fehlende_artefakte:
        return _usage(
            "Abnahmebericht verlangt die Pflichtartefakte: "
            + ", ".join(fehlende_artefakte)
        )
    if bestands_scope:
        if not args.b1_ledger:
            args.b1_ledger = str(
                fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
            )

    eingaben: Dict[str, Path] = {
        "suite": Path(args.suite),
        "spec": Path(args.spec),
        "transformation_ergebnis": Path(args.transformation_ergebnis),
        "bestandsbericht_vor": Path(args.bestandsbericht_vor),
        "bestandsbericht_nach": Path(args.bestandsbericht_nach),
    }
    if bestands_scope:
        eingaben["b1_ledger"] = Path(args.b1_ledger)
    fehlend = [str(p) for p in eingaben.values() if not p.is_file()]
    if fehlend:
        return _usage(f"Datei nicht gefunden: {'; '.join(fehlend)}")

    bericht_pfad = (
        Path(args.bericht) if args.bericht
        else fall / "abgeleitet" / "berichte" / "migrationsabnahme.html"
    )
    artefaktrollen = {
        f"--{name.replace('_', '-')}": pfad
        for name, pfad in eingaben.items()
    }
    artefaktrollen["--bericht"] = bericht_pfad
    artefaktrollen["Gate-Ledger"] = (
        diagnostics_dir / f"{COMMAND}{GATE_LEDGER_SUFFIX}"
    )
    kollisionen = _pfadrollen_kollisionen(artefaktrollen)
    if kollisionen:
        return _usage(
            "Alle Eingabe-Pflichtartefakte, --bericht und Gate-Ledger muessen "
            "auf paarweise verschiedene Dateien zeigen; Kollision: "
            + "; ".join(kollisionen),
            ledger_schreiben=not any(
                "Gate-Ledger" in kollision for kollision in kollisionen
            ),
        )
    ledger_start_fehler = _begin_ledger()
    if ledger_start_fehler is not None:
        return ledger_start_fehler
    paths = {name: str(p) for name, p in eingaben.items()}
    paths["bericht"] = str(bericht_pfad)
    if fall is not None:
        paths["fall"] = str(fall)
    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd().resolve()
    hash_basis = fall if bestands_scope else (
        repo_root if args.repo_root else None
    )
    input_hashes = hash_files(list(eingaben.values()), base=hash_basis)

    def _contract_fehler(code: str, meldungen: List[str], hinweis: str):
        gezeigt = meldungen[:20]
        if len(meldungen) > len(gezeigt):
            gezeigt.append(
                f"... und weitere {len(meldungen) - len(gezeigt)} von "
                f"{len(meldungen)}")
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.FILE_CONTRACT, paths=paths,
            input_hashes=input_hashes,
            errors=[{"code": code, "message": m} for m in gezeigt],
            repair_hints=[{"code": code, "hint": hinweis}],
        ))

    renderer_artefakte: Dict[str, Dict[str, str]] = {}
    if bestands_scope:
        assert fall is not None
        try:
            renderer_artefakte = {
                rolle: artefakt_eintrag(fall, eingaben[rolle])
                for rolle in renderer_artefaktrollen()
            }
        except ValueError as exc:
            return _contract_fehler(
                "renderer_artefakt",
                [str(exc)],
                "Alle vier Renderer-Pflichtartefakte innerhalb des Falls "
                "ablegen und den Abnahmebericht erneut erzeugen.",
            )
    else:
        # Auch der falllose Bibliotheks-/CLI-Pfad schreibt die Rollen explizit.
        # Nur im Bestands-Scope verlangt G-2 darueber hinaus sichere Fallpfade.
        for rolle in renderer_artefaktrollen():
            [(pfad, datei_hash)] = hash_files(
                [eingaben[rolle]], base=hash_basis
            ).items()
            renderer_artefakte[rolle] = {
                "pfad": pfad,
                "sha256": datei_hash,
            }

    try:
        suite = json.loads(eingaben["suite"].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _contract_fehler(
            "suite_unlesbar", [f"{type(exc).__name__}: {exc}"],
            "Suite-Ergebnis ist das JSON von "
            "qa.migrationssuite.pruefe_bestand (json.dump des Rueckgabe-"
            "Dicts); erneut erzeugen statt von Hand schreiben.")
    struktur_fehler = _suite_fehler(suite)
    if struktur_fehler:
        return _contract_fehler(
            "suite_contract", struktur_fehler,
            "Das Suite-Ergebnis stammt unveraendert aus "
            "qa.migrationssuite.pruefe_bestand; die Suite erneut laufen "
            "lassen, statt die Zusammenfassung nachzubessern.")

    spec = None
    try:
        spec = TransformationsSpec.model_validate_json(
            eingaben["spec"].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _contract_fehler(
            "spec_unlesbar", [f"{type(exc).__name__}: {exc}"],
            "Die TransformationsSpec muss dem Schema von "
            "ontologie.transformation.TransformationsSpec genuegen.")

    transformation_ergebnis = None
    gemeinsame_bindung: Optional[Dict[str, Any]] = None
    try:
        transformation_ergebnis = json.loads(
            eingaben["transformation_ergebnis"].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _contract_fehler(
            "transformation_ergebnis_unlesbar",
            [f"{type(exc).__name__}: {exc}"],
            "Erwartet ein JSON-Objekt mit zeilen_quelle, zeilen_ziel "
            "und befunde (Ausgabe von gates.transformation_anwenden.wende_an).")
    transformation_fehler = _transformation_ergebnis_fehler(
        transformation_ergebnis
    )
    if transformation_fehler:
        return _contract_fehler(
            "transformation_ergebnis_contract",
            transformation_fehler,
            "Erwartet nichtnegative ganzzahlige Zeilenanzahlen und eine "
            "Liste textueller Befunde aus gates.transformation_anwenden.wende_an.",
        )

    if not bestands_scope:
        spec_fehler = _spec_fehler(spec, transformation_ergebnis)
        if spec_fehler:
            return _contract_fehler(
                "spec_contract",
                spec_fehler,
                "TransformationsSpec vollstaendig mit validate_spec pruefen "
                "und erst danach den Bericht neu erzeugen.",
            )

    if bestands_scope:
        assert fall is not None
        try:
            gemeinsame_bindung = scope_bindung(
                fall, repo_root, args.stichtag_1, args.stichtag_2
            )
        except fall_mod.FallFehler as exc:
            return _contract_fehler(
                "scope_bindung", [str(exc)],
                "Eingang, A-Box und Scope-Deklaration vervollstaendigen.",
            )
        suite_scope_fehler = _bestands_suite_fehler(
            suite,
            stichtag_1=args.stichtag_1,
            stichtag_2=args.stichtag_2,
            erwartetes_system=gemeinsame_bindung["system"],
        )
        if suite_scope_fehler:
            return _contract_fehler(
                "suite_scope_contract",
                suite_scope_fehler,
                "Migrationssuite vollstaendig auf genau dem geprueften "
                "Bestand und den beiden Scope-Stichtagen neu ausfuehren.",
            )
        b1_fehler = _b1_fehler(
            ledger_pfad=eingaben["b1_ledger"],
            fall=fall,
            repo_root=repo_root,
            suite=suite,
            erwartetes_system=gemeinsame_bindung["system"],
        )
        if b1_fehler:
            return _contract_fehler(
                "b1_contract",
                b1_fehler,
                "Gate B1 und Migrationssuite auf demselben aktuellen "
                "Bestandsartefakt erneut ausfuehren.",
            )
        transformations_fehler, _, _ = _transformationsvertrag_fehler(
            fall=fall,
            spec_pfad=eingaben["spec"],
            spec=spec,
            ergebnis=transformation_ergebnis,
            suite=suite,
        )
        if transformations_fehler:
            return _contract_fehler(
                "transformation_contract",
                transformations_fehler,
                "TransformationsSpec und Ergebnis aus der registrierten "
                "CSV-Quelle neu erzeugen; Quellheader, Quell-, Spec- und "
                "Ziel-SHA-256 nicht von Hand uebernehmen.",
            )

    bestandsbericht_vor = (
        renderer_artefakte["bestandsbericht_vor"]["pfad"]
        if bestands_scope else args.bestandsbericht_vor
    )
    bestandsbericht_nach = (
        renderer_artefakte["bestandsbericht_nach"]["pfad"]
        if bestands_scope else args.bestandsbericht_nach
    )
    bericht_erzeugung = _bericht_erzeugung(
        titel=args.titel,
        stichtag_1=args.stichtag_1,
        stichtag_2=args.stichtag_2,
        spec=spec,
        transformation_ergebnis=transformation_ergebnis,
        bestandsbericht_vor=bestandsbericht_vor,
        bestandsbericht_nach=bestandsbericht_nach,
    )

    # Der Bericht wird auf BEIDEN Pfaden geschrieben: gerade der rote
    # Bericht ist das Beweisstueck, mit dem der Mensch entscheidet.
    schreibe_bericht(
        bericht_pfad, titel=args.titel,
        stichtag_1=args.stichtag_1, stichtag_2=args.stichtag_2,
        suite=suite, spec=spec,
        transformation_ergebnis=transformation_ergebnis,
        bestandsbericht_vor=bestandsbericht_vor,
        bestandsbericht_nach=bestandsbericht_nach,
        fall=fall,
    )
    output_hashes = hash_files([bericht_pfad], base=fall if bestands_scope else repo_root)

    summary = {
        **_suite_zusammenfassung(suite),
        **_abnahme_zusammenfassung(
            suite=suite,
            spec=spec,
            transformation_ergebnis=transformation_ergebnis,
            bestandsbericht_vor=bestandsbericht_vor,
            bestandsbericht_nach=bestandsbericht_nach,
            fall=fall,
        ),
        "mapping_tabelle": spec is not None,
        # Ausdruecklich: dieses Kommando nimmt nichts ab.
        "abnahme": "offen — Gate G-2 (Mensch, gates/gate_entscheid)",
        "bericht_erzeugung": bericht_erzeugung,
        "renderer_artefakte": renderer_artefakte,
    }
    if gemeinsame_bindung is not None:
        summary["scope_bindung"] = gemeinsame_bindung

    if summary["bericht_bestanden"]:
        if bestands_scope:
            assert fall is not None and gemeinsame_bindung is not None
            try:
                bestandsbelege = {
                    "b1_ledger": artefakt_eintrag(fall, eingaben["b1_ledger"]),
                    "migrationssuite": artefakt_eintrag(fall, eingaben["suite"]),
                    "abnahmebericht": artefakt_eintrag(fall, bericht_pfad),
                }
            except ValueError as exc:
                return _contract_fehler(
                    "scope_artefakt", [str(exc)],
                    "Alle Bestands-Pflichtartefakte innerhalb des Falls ablegen.",
                )
            if set(bestandsbelege) != set(bestands_belegrollen()):
                return _contract_fehler(
                    "bestands_belegrollen",
                    ["interne Belegrollen weichen vom Bestandsvertrag ab"],
                    "Abnahmebericht und G-2-Vertrag gemeinsam versionieren.",
                )
            summary["bestandsbelege"] = bestandsbelege
        log(f"{COMMAND}: vollstaendige Vorlage ohne Abnahmehindernis "
            f"({summary['bestanden']} von "
            f"{summary['anzahl']} Vertraegen, "
            f"0 Pruefluecken) -> {bericht_pfad}")
        return _finalize(build_result(
            command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
            exit_code=Exit.OK, paths=paths, summary=summary,
            input_hashes=input_hashes, output_hashes=output_hashes,
            diagnostics_path=str(bericht_pfad),
        ))

    errors = [
        {"code": "mengenbefund", "message": m}
        for m in suite["mengenbefunde"]
    ] + [
        {"code": "abnahmetest", "message":
         f"{u['police_id']} / {p['groesse']}: System {p['system']:.2f} "
         f"gegen Lieferung {p['erwartet']:.2f} (Residuum "
         f"{p['residuum']:.4f})"}
        for u in suite["vertraege"] for p in u["pruefungen"] if not p["ok"]
    ] + [
        {"code": "befund", "message": f"{u['police_id']}: {b}"}
        for u in suite["vertraege"] for b in u["befunde"]
    ] + list(summary["abnahmehindernisse"])
    if len(errors) > 50:
        # Der Bericht weist ALLE aus; das JSON bleibt lesbar und nennt die
        # Gesamtzahl, statt sie stillschweigend zu unterschlagen.
        errors = errors[:50] + [{
            "code": "gekuerzt",
            "message": f"... und weitere {len(errors) - 50} von "
                       f"{len(errors)}; vollstaendig im Bericht "
                       f"{bericht_pfad}",
        }]
    log(f"{COMMAND}: {summary['fehlgeschlagen']} von {summary['anzahl']} "
        f"Vertraegen fehlgeschlagen, {summary['befunde']} Befund(e), "
        f"{summary['mengenbefunde']} Befund(e) der Pruefmenge, "
        f"{len(summary['abnahmehindernisse'])} Abnahmehindernis(se) -> "
        f"{bericht_pfad}")
    return _finalize(build_result(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
        exit_code=Exit.GOLDEN_MASTER, paths=paths, summary=summary,
        input_hashes=input_hashes, output_hashes=output_hashes,
        diagnostics_path=str(bericht_pfad), errors=errors,
        repair_hints=[{
            "code": "abnahme",
            "hint": "Abweichungen, Pruefluecken und Transformationshindernisse "
            "beheben und alle vier Pflichtartefakte erneut erzeugen. Weder "
            "Erwartungswerte noch Toleranzen nachtraeglich anpassen; der "
            "Bericht unter 'bericht' weist jedes Hindernis aus.",
        }],
    ))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
