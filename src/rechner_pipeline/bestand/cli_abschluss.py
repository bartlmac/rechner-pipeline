"""``bestand_abschluss`` toolbox command — Bewertungsstand festschreiben.

Producer wie ``cli_fortschreibung``: kein Gate, kein Ledger-Eintrag. Zwei
Betriebsarten:

* Festschreiben (Default): rechnet den Stichtag ueber die eine
  Bewertungsstrecke und schreibt ``abschluss_<stichtag>.parquet`` in das
  Abschluss-Verzeichnis des Laufs — genau einmal je Stichtag; ein
  vorhandener Abschluss bricht hart ab (ADR-011: festgeschriebene
  Staende werden nie ueberschrieben).
* ``--pruefen``: stellt die Neuberechnung gegen einen vorhandenen
  Abschluss und weist Abweichungen aus (Exit 3), inklusive des
  Kern-Versionshinweises, wenn der Stand sich geaendert hat.

Usage::

    python -m rechner_pipeline.bestand.cli_abschluss \\
        --config configs/bestand_gesamt.toml --lauf runs/bestand \\
        --stichtag 2026-01-01 --bis 2026-01-01 \\
        [--out-dir runs/bestand/abschluesse] [--pruefen]

Beide Betriebsarten pruefen VORHER dasselbe vollstaendige Lauf-Bundle
(Stamm, Historie, Ledger, Scheiben, Config) mit derselben Engine wie
Gate P-B1 — ``bestand.vorbedingungen.lies_und_pruefe_pb1``. Ein Abschluss
auf einer Teilmenge waere ein festgeschriebener Falschstand, den die
eigene Kontrolle bestaetigt.

Das Bundle muss sein **Laufmanifest** tragen (``laufmanifest.json``,
geschrieben von ``cli_fortschreibung``): Es belegt den simulierten
Horizont und die Bytes jeder Ausgabe. Ohne Manifest wird nichts
festgeschrieben — ``--bis`` waere sonst eine Behauptung des Aufrufers
ueber den Lauf (externes Review T18-02: ein bis 2020-01-01 simulierter
Lauf, festgeschrieben mit behauptetem ``--bis 2020-12-01``, Exit 0,
Bewegungskonto um 1,37 Mio EUR ueberzeichnet). Pflicht und fail-fast,
nicht "optional mit Vorbehalt": Ein festgeschriebener Stand traegt
keinen Vorbehalt.

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.bestand.abschluss import (
    AbschlussError,
    abschluss_pfad,
    pruefe_abschluss,
    schreibe_abschluss,
)
from rechner_pipeline.bestand.manifest import ManifestError, lies_manifest
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.kern import MissingMortalityTableError


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.bestand.cli_abschluss",
        description=(
            "Bewertungsstand eines Stichtags festschreiben oder gegen den "
            "festgeschriebenen Stand pruefen. Producer, kein Gate."
        ),
    )
    parser.add_argument("--config", required=True, help="Bestand-Config (TOML).")
    parser.add_argument(
        "--lauf", required=True,
        help="Laufverzeichnis mit bestand_gesamt.parquet, historie.parquet "
        "und scheiben.parquet.",
    )
    parser.add_argument("--stichtag", required=True, help="ISO-Datum.")
    parser.add_argument(
        "--bis", required=True,
        help="Fortschreibungs-Horizont des Laufs (ISO-Datum) — DASSELBE "
        "Datum wie beim cli_fortschreibung-Lauf. Die Bewegungs-Identitaet "
        "gilt nur fuer vollstaendig simulierte Kalenderjahre; ohne den "
        "Horizont waere sie scheinbar verletzt.",
    )
    parser.add_argument(
        "--out-dir", default=None,
        help="Abschluss-Verzeichnis (Default: <lauf>/abschluesse).",
    )
    parser.add_argument(
        "--pruefen", action="store_true",
        help="vorhandenen Abschluss gegen die Neuberechnung stellen "
        "statt festzuschreiben.",
    )
    ns = parser.parse_args(argv)

    try:
        stichtag = _dt.date.fromisoformat(ns.stichtag)
    except ValueError as exc:
        print(f"bestand_abschluss: --stichtag: {exc}", file=sys.stderr)
        return 2
    try:
        bis = _dt.date.fromisoformat(ns.bis)
    except ValueError as exc:
        print(f"bestand_abschluss: --bis: {exc}", file=sys.stderr)
        return 2
    if stichtag > bis:
        print(
            f"bestand_abschluss: Stichtag {stichtag.isoformat()} liegt hinter "
            f"dem Fortschreibungs-Horizont {bis.isoformat()} — der Lauf hat "
            "die Jahre dazwischen nie simuliert. Ein Abschluss darauf waere "
            "keine Bewertung, sondern eine Behauptung",
            file=sys.stderr,
        )
        return 2
    lauf = Path(ns.lauf)
    out_dir = Path(ns.out_dir) if ns.out_dir else lauf / "abschluesse"

    # Ein Abschluss ist festgeschrieben und wird nie ueberschrieben. Er muss
    # deshalb DASSELBE vollstaendige Lauf-Bundle bestehen wie Gate P-B1 — und
    # zwar durch DIESELBE Engine, nicht durch eine eigene Teilpruefung.
    # Vorher sperrte die CLI nur bei "scheiben is None": eine vorhandene,
    # schema-korrekte, aber LEERE Scheiben- oder Historiendatei passierte,
    # und Schreiben wie --pruefen bestaetigten einander auf demselben
    # unvollstaendigen Stand. Gemessen an einem regulaeren KLV-Lauf: leere
    # Scheiben 25 Bewegungsfehler (Deckungskapital 3.795.035,38 zu niedrig),
    # leere Historie 1.076 Fuehrungsfehler (Deckungskapital 55,7 statt
    # 35,5 Mio) — beides bisher mit Exit 0 in einem unumkehrbaren Stand.
    eingaben = {
        "portfolio": lauf / "bestand_gesamt.parquet",
        "historie": lauf / "historie.parquet",
        "ledger": lauf / "ledger.parquet",
        "scheiben": lauf / "scheiben.parquet",
        "config": Path(ns.config),
    }
    fehlend = [str(pfad) for pfad in eingaben.values() if not pfad.is_file()]
    if fehlend:
        print(
            "bestand_abschluss: unvollstaendiges Lauf-Bundle — nicht "
            f"gefunden: {', '.join(fehlend)}. Ein Abschluss verlangt den "
            "ganzen Lauf (erzeugt von bestand.cli_fortschreibung), nicht "
            "die Teilmenge, die zufaellig dasteht",
            file=sys.stderr,
        )
        return 2
    # Der Lieferschein des Erzeugers: ohne ihn ist --bis unbelegt und das
    # Bundle nicht nachweislich EIN Lauf (T18-02). Fail-fast, kein
    # Vorbehalt.
    try:
        manifest = lies_manifest(lauf)
    except ManifestError as exc:
        print(f"bestand_abschluss: {exc}", file=sys.stderr)
        return 2
    # Pruefen UND uebernehmen: Was hier geprueft wurde, wird unten
    # verarbeitet — kein zweites Lesen zwischen Urteil und Rechnung
    # (T18-03; im Nachweis wurde genau dazwischen getauscht). Die Engine
    # haelt dabei jede gelesene Datei gegen das Manifest.
    geprueft_tabellen, _, fehler, usage = lies_und_pruefe_pb1(
        eingaben, bis=bis, manifest=manifest)
    if fehler or usage:
        for eintrag in (usage + fehler)[:5]:
            print(f"bestand_abschluss: {eintrag['message']}", file=sys.stderr)
        anzahl = len(fehler) + len(usage)
        if anzahl > 5:
            print(f"bestand_abschluss: ... und {anzahl - 5} weitere",
                  file=sys.stderr)
        print(
            f"bestand_abschluss: {anzahl} Vorbedingung(en) verletzt — es "
            "wird nichts festgeschrieben. Passt --bis zum Lauf?",
            file=sys.stderr,
        )
        return 2

    # Tabellen UND Config kommen aus der Pruefung, nicht von der Platte.
    config = geprueft_tabellen["config"]
    stamm = geprueft_tabellen["portfolio"]
    historie = geprueft_tabellen["historie"]
    scheiben = geprueft_tabellen["scheiben"]

    if ns.pruefen:
        pfad = abschluss_pfad(out_dir, stichtag)
        if not pfad.is_file():
            print(f"bestand_abschluss: kein Abschluss unter {pfad}", file=sys.stderr)
            return 2
        try:
            befunde = pruefe_abschluss(
                pfad, stamm, historie, config, scheiben=scheiben
            )
        except (AbschlussError, ValueError, MissingMortalityTableError) as exc:
            print(f"bestand_abschluss: {exc}", file=sys.stderr)
            return 2
        if befunde:
            for befund in befunde:
                print(befund, file=sys.stderr)
            print(
                f"bestand_abschluss: {len(befunde)} Abweichung(en) — der "
                "Abschluss bleibt unveraendert stehen",
                file=sys.stderr,
            )
            return 3
        print(
            f"bestand_abschluss: Neuberechnung deckt den Abschluss "
            f"{stichtag.isoformat()} ({pfad})",
            file=sys.stderr,
        )
        return 0

    try:
        pfad = schreibe_abschluss(
            stamm, historie, config, stichtag, out_dir, scheiben=scheiben
        )
    except (AbschlussError, ValueError, MissingMortalityTableError) as exc:
        print(f"bestand_abschluss: {exc}", file=sys.stderr)
        return 2
    print(
        f"bestand_abschluss: Stichtag {stichtag.isoformat()} festgeschrieben "
        f"-> {pfad}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
