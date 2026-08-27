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
        --stichtag 2026-01-01 [--out-dir runs/bestand/abschluesse] [--pruefen]

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
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.kern import MissingMortalityTableError
from rechner_pipeline.models.bestand import validate_scheiben


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
    lauf = Path(ns.lauf)
    out_dir = Path(ns.out_dir) if ns.out_dir else lauf / "abschluesse"
    try:
        config = load_config(Path(ns.config))
        stamm = read_portfolio(lauf / "bestand_gesamt.parquet")
        historie = read_portfolio(lauf / "historie.parquet")
        scheiben_pfad = lauf / "scheiben.parquet"
        scheiben = read_portfolio(scheiben_pfad) if scheiben_pfad.is_file() else None
        ledger_pfad = lauf / "ledger.parquet"
        ledger = read_portfolio(ledger_pfad) if ledger_pfad.is_file() else None
    except (OSError, ValueError, MissingMortalityTableError) as exc:
        print(f"bestand_abschluss: {exc}", file=sys.stderr)
        return 2

    # Ein Abschluss ist festgeschrieben und wird nie ueberschrieben. Er muss
    # deshalb DIESELBEN Vorbedingungen bestehen wie der Bericht und wie Gate
    # P-B1 — sonst beurteilen drei Pfade denselben Datenstand verschieden,
    # und ausgerechnet der unumkehrbare ist der nachlaessigste.
    fehler = config.validate()
    if fehler:
        print(
            f"bestand_abschluss: Config ungueltig: {'; '.join(fehler)}",
            file=sys.stderr,
        )
        return 2
    if (
        ledger is not None
        and scheiben is None
        and (ledger["ereignis"] == "ERH").any()
    ):
        print(
            "bestand_abschluss: Ledger enthaelt dynamische Erhoehungen (ERH), "
            f"aber {scheiben_pfad.name} fehlt — Deckungskapital und Beitrag "
            "waeren systematisch zu niedrig, und der Stand ist danach "
            "festgeschrieben",
            file=sys.stderr,
        )
        return 2
    if scheiben is not None:
        fehler = validate_scheiben(stamm, scheiben, historie=historie)
        if fehler:
            print(
                f"bestand_abschluss: Scheiben ungueltig: {'; '.join(fehler[:3])}",
                file=sys.stderr,
            )
            return 2

    if ns.pruefen:
        pfad = abschluss_pfad(out_dir, stichtag)
        if not pfad.is_file():
            print(f"bestand_abschluss: kein Abschluss unter {pfad}", file=sys.stderr)
            return 2
        try:
            befunde = pruefe_abschluss(
                pfad, stamm, historie, config, scheiben=scheiben
            )
        except (AbschlussError, ValueError) as exc:
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
    except (AbschlussError, ValueError) as exc:
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
