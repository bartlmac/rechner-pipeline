"""Fall-Arbeitsbereich: der Ort, an dem ein Migrationsfall lebt.

Das Repo ist das System, nicht der Datenraum. Ein Fall (ein
Migrationsprojekt) lebt in einem eigenen Arbeitsbereich mit zwei strikt
getrennten Zonen:

* ``eingang/`` — die registrierten Quellen. Bei der Registrierung wird
  jede Datei inhaltsadressiert (SHA-256), schreibgeschuetzt kopiert und
  im Register ``eingang.json`` verzeichnet. Hier beginnt die
  Provenance-Kette. Diese Zone ist NICHT regenerierbar; kein Werkzeug
  dieses Repos raeumt sie auf, und eine Registrierung wird nie still
  ueberschrieben — gleicher Name mit anderem Inhalt ist ein harter
  Konflikt mit beiden Hashes in der Meldung.
* ``abgeleitet/`` — alles Regenerierbare (Vorverdichtung, generierter
  Kern, Gate-Ledger, Berichte). Darf jederzeit geloescht und aus
  Eingang + System neu erzeugt werden.

Im echten Einsatz liegt der Arbeitsbereich ausserhalb des Repos (der
Pfad ist frei waehlbar); ``faelle/`` im Repo ist nur der gitignorierte
Default fuer lokale Demo-Faelle. Fall-Quellen kommen von aussen (die
Lieferung des abgebenden Unternehmens); ``tests/fixtures/`` haelt
synthetische Quellmappen fuer Tests und Demo-Faelle.

Kommandos (ein JSON-Objekt auf stdout, Log auf stderr)::

    python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 \
        --scope tarif [--beschreibung TEXT]
    python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
        --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm [--als NAME]
    python -m rechner_pipeline.fall status --fall faelle/klv-tg2012

``assurance --fall <pfad> --quelle <name>`` faehrt die Gate-Kette auf
einem Fall: Eingang wird vor dem Lauf gegen das Register geprueft
(Integritaets-Gate), die Ausgabe-Verzeichnisse liegen unter
``abgeleitet/``.

Knoten: system/fall
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import stat
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_VERSION = 1

FALL_MANIFEST = "fall.json"
EINGANG_REGISTER = "eingang.json"

#: Der Fall deklariert seinen fachlichen Umfang einmal im nicht regenerierbaren
#: Manifest. G-2 darf daraus Pflichten ableiten; Dateiexistenz oder ein zufaellig
#: vorhandener Bestandsbericht sind kein belastbarer Scope-Entscheid.
FALL_SCOPE_SCHEMA_VERSION = 1
GATE_DAG_VERSION = "1.0.0"
FALL_SCOPES = ("tarif", "bestand")

#: Maschinenlesbarer Gate-DAG. ``belegrolle`` ist der stabile Schluessel, unter
#: dem G-2 den Nachweis pinnt. Welche Pflichten ein Scope hat, ergibt sich
#: ausschliesslich aus den aktiven Knoten und Kanten, nicht aus einer zweiten
#: handgeschriebenen Liste im Gate.
GATE_DAG: Dict[str, Any] = {
    "schema_version": 1,
    "version": GATE_DAG_VERSION,
    "ziel": "g2",
    "knoten": {
        "o1": {
            "art": "gate",
            "command": "abox_validate",
            "belegrolle": "o1_ledger",
            "scopes": ["tarif", "bestand"],
        },
        "g1": {
            "art": "menschliches_gate",
            "command": "gate_entscheid",
            "belegrolle": "g1_snapshot",
            "scopes": ["tarif", "bestand"],
        },
        "o3": {
            "art": "gate",
            "command": "generation_golden",
            "belegrolle": "o3_belege",
            "scopes": ["tarif", "bestand"],
        },
        "transformationsspec": {
            "art": "artefakt",
            "command": "ontologie.transformation.validate_spec",
            "belegrolle": "transformationsspec",
            "scopes": ["bestand"],
        },
        "transformationsergebnis": {
            "art": "artefakt",
            "command": "ontologie.transformation.wende_an",
            "belegrolle": "transformationsergebnis",
            "scopes": ["bestand"],
        },
        "b1": {
            "art": "gate",
            "command": "bestand_validate",
            "belegrolle": "b1_ledger",
            "scopes": ["bestand"],
        },
        "migrationssuite": {
            "art": "pruefergebnis",
            "command": "qa.migrationssuite.pruefe_bestand",
            "belegrolle": "migrationssuite",
            "scopes": ["bestand"],
        },
        "bestandsbericht_vor": {
            "art": "bericht",
            "command": "bestand.cli_report",
            "belegrolle": "bestandsbericht_vor",
            "scopes": ["bestand"],
        },
        "bestandsbericht_nach": {
            "art": "bericht",
            "command": "bestand.cli_report",
            "belegrolle": "bestandsbericht_nach",
            "scopes": ["bestand"],
        },
        "abnahmebericht": {
            "art": "gate",
            "command": "abnahmebericht",
            "belegrolle": "abnahmebericht",
            "scopes": ["bestand"],
        },
        "g2": {
            "art": "menschliches_gate",
            "command": "gate_entscheid",
            "belegrolle": "g2_snapshot",
            "scopes": ["tarif", "bestand"],
        },
    },
    "kanten": [
        {"von": "o1", "nach": "g1", "scopes": ["tarif", "bestand"]},
        {"von": "g1", "nach": "o3", "scopes": ["tarif", "bestand"]},
        {"von": "o3", "nach": "g2", "scopes": ["tarif", "bestand"]},
        {"von": "g1", "nach": "transformationsspec", "scopes": ["bestand"]},
        {
            "von": "transformationsspec",
            "nach": "transformationsergebnis",
            "scopes": ["bestand"],
        },
        {"von": "transformationsergebnis", "nach": "b1", "scopes": ["bestand"]},
        {"von": "b1", "nach": "migrationssuite", "scopes": ["bestand"]},
        {
            "von": "migrationssuite",
            "nach": "abnahmebericht",
            "scopes": ["bestand"],
        },
        {
            "von": "transformationsspec",
            "nach": "abnahmebericht",
            "scopes": ["bestand"],
        },
        {
            "von": "transformationsergebnis",
            "nach": "abnahmebericht",
            "scopes": ["bestand"],
        },
        {
            "von": "bestandsbericht_vor",
            "nach": "abnahmebericht",
            "scopes": ["bestand"],
        },
        {
            "von": "bestandsbericht_nach",
            "nach": "abnahmebericht",
            "scopes": ["bestand"],
        },
        {"von": "abnahmebericht", "nach": "g2", "scopes": ["bestand"]},
    ],
}


class FallFehler(ValueError):
    """Fachlicher Fehler im Fall-Arbeitsbereich (kein Usage-Fehler)."""


def scope_dokument(scope: str) -> Dict[str, Any]:
    """Kanonische Scope-Deklaration fuer ``fall.json``."""
    if scope not in FALL_SCOPES:
        raise FallFehler(
            f"unbekannter Fall-Scope {scope!r} — erlaubt: {', '.join(FALL_SCOPES)}"
        )
    return {
        "schema_version": FALL_SCOPE_SCHEMA_VERSION,
        "typ": scope,
        "gate_dag_version": GATE_DAG_VERSION,
    }


def lade_scope(fall: Path) -> str:
    """Den expliziten Fall-Scope streng aus dem Manifest laden.

    Ein Altfall ohne Deklaration wird nicht still als Tarif- oder Bestandsfall
    geraten. Er muss bewusst mit der richtigen Scope-Deklaration migriert
    werden, bevor ein menschliches Gate angenommen werden kann.
    """
    manifest = _lade_json(fall / FALL_MANIFEST, "Fall-Manifest")
    scope = manifest.get("scope")
    felder = {"schema_version", "typ", "gate_dag_version"}
    if not isinstance(scope, dict) or set(scope) != felder:
        raise FallFehler(
            "Fall-Manifest braucht scope mit exakt "
            f"{sorted(felder)}; Scope bewusst als 'tarif' oder 'bestand' "
            "deklarieren, nicht aus vorhandenen Artefakten raten"
        )
    if type(scope.get("schema_version")) is not int or scope[
        "schema_version"
    ] != FALL_SCOPE_SCHEMA_VERSION:
        raise FallFehler(
            f"scope.schema_version muss {FALL_SCOPE_SCHEMA_VERSION} sein"
        )
    typ = scope.get("typ")
    if typ not in FALL_SCOPES:
        raise FallFehler(
            f"scope.typ {typ!r} ist ungueltig — erlaubt: {', '.join(FALL_SCOPES)}"
        )
    if scope.get("gate_dag_version") != GATE_DAG_VERSION:
        raise FallFehler(
            "scope.gate_dag_version passt nicht zum Systemstand: "
            f"{scope.get('gate_dag_version')!r} statt {GATE_DAG_VERSION!r}"
        )
    return str(typ)


def validate_gate_dag(dag: Any = GATE_DAG) -> List[str]:
    """Struktur, Scope-Konsistenz und Zyklenfreiheit des Gate-DAG pruefen."""
    if not isinstance(dag, dict):
        return ["Gate-DAG ist kein Objekt"]
    fehler: List[str] = []
    kopf = {"schema_version", "version", "ziel", "knoten", "kanten"}
    if set(dag) != kopf:
        return [f"Gate-DAG muss exakt {sorted(kopf)} enthalten"]
    if type(dag.get("schema_version")) is not int or dag[
        "schema_version"
    ] != 1:
        fehler.append("Gate-DAG.schema_version muss 1 sein")
    if dag.get("version") != GATE_DAG_VERSION:
        fehler.append(f"Gate-DAG.version muss {GATE_DAG_VERSION!r} sein")
    knoten = dag.get("knoten")
    kanten = dag.get("kanten")
    if not isinstance(knoten, dict) or not knoten:
        return [*fehler, "Gate-DAG.knoten muss ein nichtleeres Objekt sein"]
    ziel = dag.get("ziel")
    if not isinstance(ziel, str) or not ziel or ziel not in knoten:
        fehler.append("Gate-DAG.ziel ist kein deklarierter Knoten")
    rollen: List[str] = []
    for name, daten in knoten.items():
        if not isinstance(name, str) or not name:
            fehler.append("Gate-DAG enthaelt einen leeren Knoten-Namen")
        if not isinstance(daten, dict) or set(daten) != {
            "art", "command", "belegrolle", "scopes"
        }:
            fehler.append(f"Knoten {name!r} hat nicht den exakten Vertrag")
            continue
        for feld in ("art", "command", "belegrolle"):
            if not isinstance(daten[feld], str) or not daten[feld]:
                fehler.append(f"Knoten {name!r}.{feld} muss nichtleer sein")
        if isinstance(daten["belegrolle"], str):
            rollen.append(daten["belegrolle"])
        scopes = daten["scopes"]
        scopes_sind_strings = (
            isinstance(scopes, list)
            and bool(scopes)
            and all(isinstance(scope, str) for scope in scopes)
        )
        if (
            not scopes_sind_strings
            or any(scope not in FALL_SCOPES for scope in scopes)
            or len(scopes) != len(set(scopes))
        ):
            fehler.append(f"Knoten {name!r}.scopes ist ungueltig")
    if len(rollen) != len(set(rollen)):
        fehler.append("Gate-DAG.belegrollen muessen eindeutig sein")
    if not isinstance(kanten, list):
        return [*fehler, "Gate-DAG.kanten muss eine Liste sein"]
    gesehen = set()
    gueltige_kanten: List[Dict[str, Any]] = []
    for i, kante in enumerate(kanten):
        if not isinstance(kante, dict) or set(kante) != {"von", "nach", "scopes"}:
            fehler.append(f"Kante {i} hat nicht den exakten Vertrag")
            continue
        von, nach = kante["von"], kante["nach"]
        if (
            not isinstance(von, str) or not von
            or not isinstance(nach, str) or not nach
            or von not in knoten or nach not in knoten or von == nach
        ):
            fehler.append(f"Kante {i} referenziert ungueltige Knoten")
            continue
        scopes = kante["scopes"]
        scopes_sind_strings = (
            isinstance(scopes, list)
            and bool(scopes)
            and all(isinstance(scope, str) for scope in scopes)
        )
        if (
            not scopes_sind_strings
            or any(scope not in FALL_SCOPES for scope in scopes)
            or len(scopes) != len(set(scopes))
        ):
            fehler.append(f"Kante {i}.scopes ist ungueltig")
            continue
        von_daten = knoten[von]
        nach_daten = knoten[nach]
        von_scopes = (
            von_daten.get("scopes", [])
            if isinstance(von_daten, dict)
            and isinstance(von_daten.get("scopes"), list)
            else []
        )
        nach_scopes = (
            nach_daten.get("scopes", [])
            if isinstance(nach_daten, dict)
            and isinstance(nach_daten.get("scopes"), list)
            else []
        )
        if any(scope not in von_scopes or scope not in nach_scopes for scope in scopes):
            fehler.append(f"Kante {i}.scopes passt nicht zu ihren Knoten")
        schluessel = (von, nach, tuple(scopes))
        if schluessel in gesehen:
            fehler.append(f"Kante {i} ist dupliziert")
        gesehen.add(schluessel)
        gueltige_kanten.append(kante)

    for scope in FALL_SCOPES:
        aktive = {
            name for name, daten in knoten.items()
            if isinstance(daten, dict)
            and isinstance(daten.get("scopes"), list)
            and scope in daten["scopes"]
        }
        nachbarn = {
            name: [
                kante["nach"] for kante in gueltige_kanten
                if scope in kante["scopes"]
                and kante["von"] == name
            ]
            for name in aktive
        }
        zustand: Dict[str, int] = {}

        def _besuche(name: str) -> None:
            if zustand.get(name) == 1:
                fehler.append(f"Gate-DAG enthaelt im Scope {scope!r} einen Zyklus")
                return
            if zustand.get(name) == 2:
                return
            zustand[name] = 1
            for ziel in nachbarn.get(name, []):
                _besuche(ziel)
            zustand[name] = 2

        for name in aktive:
            _besuche(name)

        # Jeder fuer den Scope deklarierte Knoten muss tatsaechlich in die
        # G-2-Ableitung eingehen. Sonst koennte eine spaetere DAG-Erweiterung
        # zwar eine Belegrolle deklarieren, sie aber durch eine vergessene
        # Kante unbemerkt von der Abnahme ausschliessen.
        if isinstance(ziel, str) and ziel in aktive:
            rueckwaerts = {
                name: [
                    kante["von"] for kante in gueltige_kanten
                    if scope in kante["scopes"] and kante["nach"] == name
                ]
                for name in aktive
            }
            erreicht = {ziel}
            offen = [ziel]
            while offen:
                name = offen.pop()
                for vorgaenger in rueckwaerts.get(name, []):
                    if vorgaenger not in erreicht:
                        erreicht.add(vorgaenger)
                        offen.append(vorgaenger)
            getrennt = sorted(aktive - erreicht)
            if getrennt:
                fehler.append(
                    f"Gate-DAG-Knoten im Scope {scope!r} haben keinen Pfad "
                    f"zum Ziel {ziel!r}: {getrennt}"
                )
    return fehler


def g2_pflichtknoten(scope: str) -> List[str]:
    """Transitive, topologisch stabile G-2-Vorfahren fuer *scope*.

    Die Funktion ist der einzige Ableitungspfad fuer G-2-Pflichten. Sie
    traversiert den deklarativen DAG rueckwaerts; neue Pflichtknoten werden
    dadurch nicht in mehreren Gate-Implementierungen nachgetragen.
    """
    scope_dokument(scope)
    dag_fehler = validate_gate_dag()
    if dag_fehler:
        raise FallFehler(
            "zentraler Gate-DAG ist ungueltig: " + "; ".join(dag_fehler)
        )
    knoten = GATE_DAG["knoten"]
    ziel = GATE_DAG["ziel"]
    aktiv = {
        name for name, daten in knoten.items() if scope in daten["scopes"]
    }
    kanten = [
        kante for kante in GATE_DAG["kanten"]
        if scope in kante["scopes"]
        and kante["von"] in aktiv
        and kante["nach"] in aktiv
    ]
    benoetigt = {ziel}
    offen = [ziel]
    while offen:
        nach = offen.pop()
        for kante in kanten:
            if kante["nach"] != nach or kante["von"] in benoetigt:
                continue
            benoetigt.add(kante["von"])
            offen.append(kante["von"])
    return [name for name in knoten if name in benoetigt and name != ziel]


def g2_belegrollen(scope: str) -> List[str]:
    """Stabile Belegrollen der aus dem DAG abgeleiteten Pflichtknoten."""
    return [GATE_DAG["knoten"][name]["belegrolle"]
            for name in g2_pflichtknoten(scope)]


def _pruefe_eingangsname(name: str) -> str:
    """Ein Eingangsname ist ein einfacher Dateiname — sonst ist er keiner.

    Ohne diese Pruefung wuerde ``--als`` als Pfad interpretiert: ``..``
    schreibt in die Fall-Wurzel (und zerstoert dort still das Manifest),
    ein absoluter Wert schreibt irgendwohin ins Dateisystem — beides
    unbemerkt, weil ``pruefen`` den Traversal-Namen wieder aufloest und
    die Datei ausserhalb von ``eingang/`` nicht sieht. Die Zonen-Trennung
    haengt an dieser einen Pruefung.
    """
    if not name or name in (".", ".."):
        raise FallFehler(f"unzulaessiger Eingangsname: {name!r}")
    if name != Path(name).name or "/" in name or "\\" in name:
        raise FallFehler(
            f"unzulaessiger Eingangsname: {name!r} — erlaubt ist ein "
            "einfacher Dateiname ohne Pfadanteil (kein '/', kein '..', "
            "kein absoluter Pfad); der Eingang ist eine flache Zone"
        )
    return name


def _kopiere_geschuetzt(quelle: Path, ziel: Path) -> None:
    """Quelle in den Eingang kopieren und schreibschuetzen."""
    if ziel.exists():
        ziel.chmod(ziel.stat().st_mode | stat.S_IWUSR)
        ziel.unlink()
    ziel.write_bytes(quelle.read_bytes())
    ziel.chmod(ziel.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _lade_json(pfad: Path, was: str) -> Dict[str, Any]:
    """JSON eines Fall-Artefakts laden; Defekte sind FallFehler, kein Traceback."""
    if not pfad.exists():
        raise FallFehler(
            f"kein Fall-Arbeitsbereich: {pfad} fehlt — zuerst "
            "'fall anlegen' ausfuehren"
        )
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FallFehler(f"{was} unlesbar ({pfad}): {exc}") from exc
    if not isinstance(daten, dict):
        raise FallFehler(f"{was} hat unerwartete Struktur ({pfad})")
    return daten


def _sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _jetzt_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _schreibe_json(pfad: Path, daten: Dict[str, Any]) -> None:
    pfad.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def verzeichnisse(fall: Path) -> Dict[str, Path]:
    """Die festen Orte eines Fall-Arbeitsbereichs (reine Ableitung)."""
    abgeleitet = fall / "abgeleitet"
    return {
        "eingang": fall / "eingang",
        "abgeleitet": abgeleitet,
        "info_dir": abgeleitet / "info_from_excel",
        "generated_dir": abgeleitet / "generated",
        "diagnostics_dir": abgeleitet / "diagnostics",
        "berichte_dir": abgeleitet / "berichte",
    }


def anlegen(
    fall: Path, beschreibung: str = "", scope: str = "tarif"
) -> Dict[str, Any]:
    """Arbeitsbereich anlegen; ein bestehender Fall wird nie ueberschrieben."""
    manifest = fall / FALL_MANIFEST
    register = fall / EINGANG_REGISTER
    if manifest.exists():
        if not register.exists():
            raise FallFehler(
                f"unvollstaendiger Fall: {manifest} existiert, {register} "
                "fehlt — Register von Hand ergaenzen "
                '(\'{"schema_version": 1, "quellen": []}\') oder den '
                "Arbeitsbereich verwerfen; 'anlegen' repariert nicht"
            )
        raise FallFehler(
            f"Fall existiert bereits: {manifest} — ein Arbeitsbereich wird "
            "nie ueberschrieben (neuen Pfad waehlen)"
        )
    if register.exists():
        raise FallFehler(
            f"unvollstaendiger Fall: {register} existiert (mit Provenance!), "
            f"{manifest} fehlt — 'anlegen' wuerde das Register leeren und "
            "die Herkunft der Quellen verlieren; Manifest von Hand "
            "ergaenzen oder anderen Pfad waehlen"
        )
    scope_daten = scope_dokument(scope)
    v = verzeichnisse(fall)
    v["eingang"].mkdir(parents=True, exist_ok=True)
    v["abgeleitet"].mkdir(parents=True, exist_ok=True)
    daten = {
        "schema_version": SCHEMA_VERSION,
        "name": fall.name,
        "beschreibung": beschreibung,
        "angelegt_am": _jetzt_utc(),
        "scope": scope_daten,
    }
    _schreibe_json(manifest, daten)
    _schreibe_json(fall / EINGANG_REGISTER,
                   {"schema_version": SCHEMA_VERSION, "quellen": []})
    return {"fall": str(fall), "angelegt": True, **daten}


def _lade_register(fall: Path) -> Dict[str, Any]:
    register = _lade_json(fall / EINGANG_REGISTER, "Eingangs-Register")
    if not isinstance(register.get("quellen"), list):
        raise FallFehler(
            f"Eingangs-Register ohne Liste 'quellen' ({fall / EINGANG_REGISTER})"
        )
    return register


def registrieren(
    fall: Path, datei: Path, als: Optional[str] = None
) -> Dict[str, Any]:
    """Quelle in den Eingang aufnehmen: kopieren, hashen, schreibschuetzen.

    Geprueft werden BEIDE Seiten — Register und Dateisystem —, weil sie
    auseinanderlaufen koennen und der Eingang die Zone ist, die nicht
    regenerierbar ist:

    * Registriert mit gleichem Hash und passender Kopie: ``bereits_registriert``.
    * Registriert, Kopie fehlt: ``wiederhergestellt`` (Register bleibt).
    * Registriert, Kopie weicht ab: harter Fehler (Integritaetsverletzung
      wird nicht durch einen Schreibvorgang zugedeckt).
    * Registriert mit anderem Hash: harter Konflikt, beide Hashes in der
      Meldung, kein stiller Overwrite.
    * Unregistrierte Datei gleichen Namens im Eingang: gleicher Inhalt
      wird ``nachgetragen`` (repariert das Abbruchfenster), anderer
      Inhalt ist ein harter Konflikt.
    """
    if not datei.is_file():
        raise FallFehler(f"Quelle nicht gefunden: {datei}")
    register = _lade_register(fall)
    name = _pruefe_eingangsname(als or datei.name)
    ziel = verzeichnisse(fall)["eingang"] / name
    neu_hash = _sha256(datei)
    eintrag_vorhanden = {q["datei"]: q for q in register["quellen"]}.get(name)
    kopie_hash = _sha256(ziel) if ziel.is_file() else None

    if eintrag_vorhanden is not None:
        alt_hash = eintrag_vorhanden["sha256"]
        if alt_hash != neu_hash:
            raise FallFehler(
                f"Eingangs-Konflikt fuer {name!r}: registriert ist "
                f"sha256={alt_hash}, angeboten wird sha256={neu_hash} — der "
                "Eingang wird nie still ueberschrieben. Anderen Namen (--als) "
                "waehlen oder den Konflikt als eigenen Vorgang aufloesen."
            )
        if kopie_hash == neu_hash:
            return {"fall": str(fall), "datei": name, "sha256": neu_hash,
                    "status": "bereits_registriert"}
        if kopie_hash is not None:
            raise FallFehler(
                f"Eingangs-Kopie {name!r} weicht vom Register ab "
                f"(registriert {alt_hash}, vorgefunden {kopie_hash}) — eine "
                "Integritaetsverletzung wird nicht durch erneutes "
                "Registrieren zugedeckt; 'fall status' zeigt den Befund, die "
                "Aufloesung ist ein eigener Vorgang."
            )
        _kopiere_geschuetzt(datei, ziel)
        return {"fall": str(fall), "datei": name, "sha256": neu_hash,
                "status": "wiederhergestellt"}

    if kopie_hash is not None and kopie_hash != neu_hash:
        raise FallFehler(
            f"unregistrierte Datei {name!r} liegt bereits im Eingang "
            f"(sha256={kopie_hash}) und weicht vom Angebot ab "
            f"(sha256={neu_hash}) — der Eingang wird nie still "
            "ueberschrieben; anderen Namen (--als) waehlen oder die "
            "vorhandene Datei bewusst entfernen."
        )
    if kopie_hash is None:
        _kopiere_geschuetzt(datei, ziel)
        status_wort = "registriert"
    else:
        # Kopie liegt bereits inhaltsgleich im Eingang: der Registereintrag
        # fehlt (Abbruch zwischen Kopie und Registerschreiben). Nachtragen
        # statt neu schreiben — sonst bliebe der Fall unbenutzbar.
        status_wort = "nachgetragen"
    eintrag = {
        "datei": name,
        "sha256": neu_hash,
        "bytes": datei.stat().st_size,
        "quelle_pfad": str(datei),
        "registriert_am": _jetzt_utc(),
    }
    register["quellen"] = sorted(
        [*register["quellen"], eintrag], key=lambda q: q["datei"]
    )
    _schreibe_json(fall / EINGANG_REGISTER, register)
    return {"fall": str(fall), **eintrag, "status": status_wort}


def pruefen(fall: Path) -> List[str]:
    """Integritaet des Eingangs gegen das Register (leer = in Ordnung)."""
    fehler: List[str] = []
    register = _lade_register(fall)
    eingang = verzeichnisse(fall)["eingang"]
    registriert = set()
    for q in register["quellen"]:
        registriert.add(q["datei"])
        try:
            _pruefe_eingangsname(q["datei"])
        except FallFehler as exc:
            fehler.append(f"Register: {exc}")
            continue
        pfad = eingang / q["datei"]
        if not pfad.is_file():
            fehler.append(f"eingang/{q['datei']}: registriert, aber Datei fehlt")
            continue
        ist = _sha256(pfad)
        if ist != q["sha256"]:
            fehler.append(
                f"eingang/{q['datei']}: Inhalt weicht vom Register ab "
                f"(registriert {q['sha256'][:12]}…, vorgefunden {ist[:12]}…)"
            )
    if eingang.is_dir():
        for pfad in sorted(eingang.iterdir()):
            if pfad.name in registriert and pfad.is_file():
                continue
            art = "Verzeichnis" if pfad.is_dir() else "Datei"
            fehler.append(
                f"eingang/{pfad.name}: {art} ohne Registrierung — der "
                "Eingang kennt nur registrierte Quellen und ist flach"
            )
    return fehler


def eingang_datei(fall: Path, name: str) -> Path:
    """Pfad einer registrierten Quelle — nur nach bestandener Pruefung."""
    register = _lade_register(fall)
    namen = [q["datei"] for q in register["quellen"]]
    if name not in namen:
        raise FallFehler(
            f"Quelle {name!r} ist im Fall nicht registriert "
            f"(registriert: {', '.join(namen) or '—'})"
        )
    fehler = pruefen(fall)
    if fehler:
        raise FallFehler(
            "Eingang verletzt das Register — kein Lauf auf unklarem "
            "Eingang: " + "; ".join(fehler)
        )
    return verzeichnisse(fall)["eingang"] / name


def status(fall: Path) -> Dict[str, Any]:
    """Zustand des Arbeitsbereichs als ein JSON-faehiges Objekt."""
    manifest = _lade_json(fall / FALL_MANIFEST, "Fall-Manifest")
    register = _lade_register(fall)
    fehler = pruefen(fall)
    v = verzeichnisse(fall)
    return {
        "fall": str(fall),
        "manifest": manifest,
        "quellen": register["quellen"],
        "eingang_integritaet": {"in_ordnung": not fehler, "fehler": fehler},
        "abgeleitet": {
            name: verz.exists()
            for name, verz in v.items()
            if name.endswith("_dir")
        },
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fall", description="Fall-Arbeitsbereich anlegen und fuehren."
    )
    sub = parser.add_subparsers(dest="kommando", required=True)

    p = sub.add_parser("anlegen", help="Arbeitsbereich anlegen.")
    p.add_argument("--fall", required=True, help="Pfad des Arbeitsbereichs.")
    p.add_argument("--beschreibung", default="", help="Freitext zum Fall.")
    p.add_argument(
        "--scope", choices=FALL_SCOPES, default="tarif",
        help="Fachlicher Fall-Scope: tarif (Default) oder bestand.",
    )

    p = sub.add_parser("registrieren", help="Quelle in den Eingang aufnehmen.")
    p.add_argument("--fall", required=True)
    p.add_argument("--datei", required=True, help="Zu registrierende Datei.")
    p.add_argument("--als", default=None,
                   help="Name im Eingang (Default: Dateiname).")

    p = sub.add_parser("status", help="Register, Integritaet, Verzeichnisse.")
    p.add_argument("--fall", required=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    fall = Path(args.fall)
    try:
        if args.kommando == "anlegen":
            ergebnis = anlegen(fall, args.beschreibung, args.scope)
        elif args.kommando == "registrieren":
            ergebnis = registrieren(fall, Path(args.datei), args.als)
        else:
            ergebnis = status(fall)
    except FallFehler as exc:
        print(f"fall: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"fall: Dateisystemfehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
