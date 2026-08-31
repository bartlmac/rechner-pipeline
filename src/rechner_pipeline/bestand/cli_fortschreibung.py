"""``bestand_fortschreibung`` toolbox command — der GeVo-Strom als ein Befehl.

Thin CLI wrapper over the Bestandsdaten engines (generator, ereignisse),
following the toolbox split like ``bestand_report``: a PRODUCER, not a gate —
it writes no ledger entry and takes no part in acceptance. It runs the full
decided workflow (ein GeVo-Strom, ein Erzeuger)::

    Basisbestand (Batch bis Referenzstichtag)  ->  Fortschreibung bis Horizont
    (Ereignisse, dynamische Erhoehungen, Neuzugang)  ->  Parquet-Tabellen

Usage::

    python -m rechner_pipeline.bestand.cli_fortschreibung \\
        --config configs/bestand_klv.toml --bis 2035-01-01 \\
        [--portfolio bestand.parquet]           # sonst: aus der Config erzeugt \\
        [--neuzugang-ab 2010-01-01] --out-dir lauf/

Outputs in ``--out-dir``: ``bestand.parquet`` (Basis; nur ohne --portfolio),
``historie.parquet``, ``ledger.parquet``, ``scheiben.parquet``,
``zugaenge.parquet`` und ``bestand_gesamt.parquet`` — der GEFUEHRTE
Gesamtbestand (ADR-011): Basis + Neuzugaenge, Statusspalten auf dem
aktuellen Zustand am Horizont; Eingang fuer Auskunft, Auswertung und
``bestand_report``.

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import (
    EreignisError,
    fortschreiben,
    mit_zugaengen,
)
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio


def _datum(raw: str, name: str) -> _dt.date:
    try:
        return _dt.date.fromisoformat(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"{name}: ungueltiges ISO-Datum: {exc}") from exc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.bestand.cli_fortschreibung",
        description=(
            "Bestand erzeugen/laden und als GeVo-Strom fortschreiben "
            "(Ereignisse, Erhoehungen, Neuzugang). Producer, kein Gate."
        ),
    )
    parser.add_argument("--config", required=True, help="Bestand-Config (TOML).")
    parser.add_argument("--bis", required=True, help="Horizont (ISO-Datum).")
    parser.add_argument(
        "--merkmale",
        default=None,
        help=(
            "Merkmalsauspraegungen-Parquet — Pflicht, sobald eine "
            "Tarifgeneration der Config in Zellen aufgeteilt ist "
            "(uebernommene Bestaende); sonst waere die Zellwahl geraten."
        ),
    )
    parser.add_argument(
        "--portfolio",
        default=None,
        help=(
            "Basisbestand-Parquet; ohne Angabe wird er aus der Config erzeugt "
            "(Batch bis --neuzugang-ab, sonst volles Gueltigkeitsfenster)."
        ),
    )
    parser.add_argument(
        "--neuzugang-ab",
        default=None,
        help="Referenzstichtag (ISO-Datum): simulierter Neuzugang danach.",
    )
    parser.add_argument("--out-dir", required=True, help="Zielverzeichnis.")
    ns = parser.parse_args(argv)

    config_path = Path(ns.config)
    if not config_path.is_file():
        print(f"bestand_fortschreibung: Config nicht gefunden: {config_path}", file=sys.stderr)
        return 2
    try:
        bis = _datum(ns.bis, "--bis")
        neuzugang_ab = _datum(ns.neuzugang_ab, "--neuzugang-ab") if ns.neuzugang_ab else None
    except argparse.ArgumentTypeError as exc:
        print(f"bestand_fortschreibung: {exc}", file=sys.stderr)
        return 2

    try:
        config = load_config(config_path)
    except ValueError as exc:
        print(f"bestand_fortschreibung: {exc}", file=sys.stderr)
        return 2
    fehler = config.validate()
    if fehler:
        print(f"bestand_fortschreibung: Config ungueltig: {'; '.join(fehler)}", file=sys.stderr)
        return 2

    out_dir = Path(ns.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        if ns.portfolio:
            portfolio_path = Path(ns.portfolio)
            if not portfolio_path.is_file():
                print(
                    f"bestand_fortschreibung: Portfolio nicht gefunden: {portfolio_path}",
                    file=sys.stderr,
                )
                return 2
            basis = read_portfolio(portfolio_path)
        else:
            basis = generate(config, bis=neuzugang_ab)
            write_portfolio(basis, out_dir / "bestand.parquet")
        merkmale = None
        if ns.merkmale:
            merkmale_path = Path(ns.merkmale)
            if not merkmale_path.is_file():
                print(
                    f"bestand_fortschreibung: Merkmale nicht gefunden: {merkmale_path}",
                    file=sys.stderr)
                return 2
            merkmale = read_portfolio(merkmale_path)
        ergebnis = fortschreiben(basis, config, bis, neuzugang_ab=neuzugang_ab,
                                 merkmale=merkmale)
        # Der Gesamtbestand ist GEFUEHRT (ADR-011): der Stammsatz traegt den
        # aktuellen Zustand am Horizont, das Journal (historie/ledger) die
        # vollstaendige Aufzeichnung. bestand.parquet bleibt der Basisbestand
        # (Ursprungszustaende am Generierungsbeginn).
        gesamt = fuehre_fort(
            mit_zugaengen(basis, ergebnis.zugaenge), ergebnis.historie
        )
    except (EreignisError, ValueError) as exc:
        print(f"bestand_fortschreibung: {exc}", file=sys.stderr)
        return 2

    write_portfolio(ergebnis.historie, out_dir / "historie.parquet")
    write_portfolio(ergebnis.ledger, out_dir / "ledger.parquet")
    write_portfolio(ergebnis.scheiben, out_dir / "scheiben.parquet")
    write_portfolio(ergebnis.zugaenge, out_dir / "zugaenge.parquet")
    write_portfolio(gesamt, out_dir / "bestand_gesamt.parquet")

    print(
        f"bestand_fortschreibung: {len(basis)} Basisvertraege, "
        f"{len(ergebnis.zugaenge)} Neuzugaenge, {len(ergebnis.ledger)} GeVos, "
        f"{len(ergebnis.scheiben)} Erhoehungsscheiben -> {out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
