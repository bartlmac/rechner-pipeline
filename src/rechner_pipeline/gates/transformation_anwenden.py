"""Registrierte Transformationsquelle deterministisch anwenden.

Die Ontologie kennt den Mapping-Vertrag, darf aber architektonisch nicht auf
den Fallarbeitsbereich zugreifen. Diese schmale Orchestrierung verbindet beide
bestehenden Grenzen: Erst loest ``fall.eingang_datei`` den in der Spec
benannten Eingang samt Register- und Integritaetspruefung auf, dann wendet die
Ontologie das Mapping auf exakt diesen neu gelesenen Bytes an. Eine frei
uebergebbare Datei ist deshalb kein Erfolgsweg der Produzenten-API.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.ontologie.transformation import (
    TransformationsSpec,
    _wende_registrierte_datei_an,
)


def wende_an(
    spec: TransformationsSpec,
    fall: Path,
    *,
    trenner: str = ";",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Spec ausschliesslich auf ihrer registrierten Fallquelle anwenden."""
    quelle_pfad = fall_mod.eingang_datei(Path(fall), spec.quelle_datei)
    return _wende_registrierte_datei_an(spec, quelle_pfad, trenner=trenner)


# --------------------------------------------------------------------------- #
# Kommando
# --------------------------------------------------------------------------- #
#
# Bis hierher war dieses Modul reine Bibliothek, und der Zusammenbau
# "Spec pruefen, dann anwenden" fiel je Lauf als handgeschriebenes
# Fall-Skript an. Das alte Skript sagt es selbst: "Es gibt fuer diesen
# Zusammenbau keine fertige CLI — deshalb dieses benannte Skript statt
# Wegwerf-Code im Terminal."
#
# Es ist ein PRODUZENT, kein Gate: kein Ledger, keine Abnahme, keine
# neue Gate-Kennung. Geprueft wird sein Erzeugnis — A-M4 rechnet das
# Transformationsergebnis vollstaendig nach (abnahmebericht.py:332-441:
# Spec-Hash gegen die Dateibytes, Quellspalten gegen den physischen
# Header, Zeilenzahlen gegen die tatsaechliche Datei). Ein zweites
# pruefendes Gate daneben waere Doppelung.
#
# Es liegt in gates/, nicht in bestand/: Nur diese Schicht darf
# ontologie UND fall zugleich importieren (ontologie/code_karte.py).


def _spaltenliste(fall: Path, spec: TransformationsSpec, trenner: str) -> List[str]:
    """Die PHYSISCHEN Spalten der registrierten Quelle.

    Nicht aus dem Spaltenprofil: A-M4 vergleicht die Quellspalten mit
    dem Header der Datei einschliesslich Reihenfolge
    (abnahmebericht.py:405-412). Ein Profil ist eine zwischenzeitliche
    Beschreibung und kann davon abweichen — die Datei ist die Wahrheit.
    """
    from rechner_pipeline.ontologie.transformation import lese_transformationsquelle

    quelle = fall_mod.eingang_datei(fall, spec.quelle_datei)
    _kopf, spalten, _zeilen = lese_transformationsquelle(quelle, trenner=trenner)
    return list(spalten)


def _ergebnis_json(
    fall: Path, spec_pfad: Path, spec: TransformationsSpec,
    quellspalten: List[str], zeilen_quelle: int, zeilen_ziel: int,
    befunde: List[str], ziel: Optional[Path],
) -> Dict[str, Any]:
    """Das Transformationsergebnis mit GENAU den neun Pflichtfeldern.

    A-M4 verlangt die Feldmenge exakt (abnahmebericht.py:344-351) und
    glaubt keinem Wert, sondern rechnet jeden nach. ``ziel_datei`` und
    ``ziel_sha256`` binden den BESTAND, nicht die Zeilenausgabe dieses
    Kommandos.
    """
    import hashlib

    quelle = fall_mod.eingang_datei(fall, spec.quelle_datei)
    return {
        "schema_version": 1,
        "spec_sha256": hashlib.sha256(spec_pfad.read_bytes()).hexdigest(),
        "quelle_sha256": hashlib.sha256(quelle.read_bytes()).hexdigest(),
        "quellspalten": quellspalten,
        "ziel_datei": (
            ziel.resolve().relative_to(fall.resolve()).as_posix()
            if ziel else ""
        ),
        "ziel_sha256": (
            hashlib.sha256(ziel.read_bytes()).hexdigest()
            if ziel and ziel.is_file() else ""
        ),
        "zeilen_quelle": zeilen_quelle,
        "zeilen_ziel": zeilen_ziel,
        "befunde": list(befunde),
    }


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    import json
    import sys

    from rechner_pipeline.ontologie.transformation import (
        lese_transformationsquelle,
        validate_spec,
    )

    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.transformation_anwenden",
        description="Transformations-Spec pruefen und auf die registrierte "
                    "Quelle anwenden (Produzent, kein Gate).")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--spec", required=True,
                   help="TransformationsSpec-JSON (Agentenvorschlag)")
    p.add_argument("--anwenden", action="store_true",
                   help="nach bestandener Pruefung anwenden")
    p.add_argument("--zeilen", default=None,
                   help="Zieldatei der transformierten Zeilen (mit --anwenden)")
    p.add_argument("--ergebnis", default=None,
                   help="Zieldatei des Transformationsergebnis-JSON")
    p.add_argument("--ziel", default=None,
                   help="Bestandsartefakt, das ziel_datei/ziel_sha256 binden "
                        "(fallrelativ; NICHT die Zeilenausgabe)")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    spec_pfad = Path(args.spec).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2
    if not spec_pfad.is_file():
        print(f"Spec nicht gefunden: {spec_pfad}", file=sys.stderr)
        return 2

    spec = TransformationsSpec(**json.loads(spec_pfad.read_text(encoding="utf-8")))
    quelle = fall_mod.eingang_datei(fall, spec.quelle_datei)
    _kopf, quellspalten, quellzeilen = lese_transformationsquelle(quelle)

    fehler = validate_spec(spec, list(quellspalten))
    print(f"Spec {spec_pfad.name} gegen {len(quellspalten)} Quellspalten:")
    if fehler:
        # Die BLOCKADE ist gewolltes Verhalten (P2) und wird nicht
        # umgangen: Offene Konflikte und ungedeckte Pflichtfelder sind
        # eine fachliche Entscheidung, keine technische.
        print(f"  {len(fehler)} Befunde — die Spec ist NICHT anwendbar:")
        for f in fehler:
            print(f"    {f}")
        print()
        print("Das ist kein Werkzeugfehler. Offene Konflikte und ungedeckte")
        print("Pflichtfelder gehoeren dem Menschen vorgelegt (Gate A-Q1).")
        return 20
    print("  anwendbar (keine Befunde)")

    if not args.anwenden:
        print("\nOhne --anwenden wird nichts geschrieben.")
        return 0

    zeilen, befunde = wende_an(spec, fall)
    print(f"\nAngewendet: {len(quellzeilen)} Quellzeilen -> {len(zeilen)} Zielzeilen")
    if befunde:
        # wende_an laesst jede Zeile mit Befund WEG. Das still zu lassen
        # waere Vertragsverlust: zeilen_ziel < zeilen_quelle ohne Grund.
        print(f"  {len(befunde)} Zeilen mit Befund (nicht uebernommen):")
        for b in befunde[:10]:
            print(f"    {b}")
        if len(befunde) > 10:
            print(f"    ... und weitere {len(befunde) - 10} von {len(befunde)}")

    if args.zeilen:
        ziel_zeilen = Path(args.zeilen)
        ziel_zeilen.parent.mkdir(parents=True, exist_ok=True)
        with ziel_zeilen.open("w", encoding="utf-8") as datei:
            json.dump(zeilen, datei, indent=2, ensure_ascii=False, sort_keys=True)
            datei.write("\n")
        print(f"  Zeilen: {ziel_zeilen}")

    if args.ergebnis:
        ziel_bestand = Path(args.ziel).resolve() if args.ziel else None
        ergebnis = _ergebnis_json(
            fall, spec_pfad, spec, list(quellspalten),
            len(quellzeilen), len(zeilen), befunde, ziel_bestand)
        ziel_erg = Path(args.ergebnis)
        ziel_erg.parent.mkdir(parents=True, exist_ok=True)
        with ziel_erg.open("w", encoding="utf-8") as datei:
            json.dump(ergebnis, datei, indent=2, ensure_ascii=False,
                      sort_keys=True)
            datei.write("\n")
        print(f"  Ergebnis: {ziel_erg}")
        if not ziel_bestand:
            print("    HINWEIS: ohne --ziel bleiben ziel_datei und "
                  "ziel_sha256 leer; A-M4 verwirft das Ergebnis dann.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
