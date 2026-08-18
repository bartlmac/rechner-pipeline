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
Default fuer lokale Demo-Faelle. ``examples/`` ist Demo-Material, aus
dem sich ein Demo-Fall instanziieren laesst — kein Input-Verzeichnis
des Systems.

Kommandos (ein JSON-Objekt auf stdout, Log auf stderr)::

    python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 \
        [--beschreibung TEXT]
    python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
        --datei examples/Tarifrechner_KLV_TG2012.xlsm [--als NAME]
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


class FallFehler(ValueError):
    """Fachlicher Fehler im Fall-Arbeitsbereich (kein Usage-Fehler)."""


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


def anlegen(fall: Path, beschreibung: str = "") -> Dict[str, Any]:
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
    v = verzeichnisse(fall)
    v["eingang"].mkdir(parents=True, exist_ok=True)
    v["abgeleitet"].mkdir(parents=True, exist_ok=True)
    daten = {
        "schema_version": SCHEMA_VERSION,
        "name": fall.name,
        "beschreibung": beschreibung,
        "angelegt_am": _jetzt_utc(),
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
            ergebnis = anlegen(fall, args.beschreibung)
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
