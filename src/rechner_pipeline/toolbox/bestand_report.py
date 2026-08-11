"""``bestand_report`` toolbox command — deterministic portfolio report (HTML).

Thin CLI wrapper over :mod:`rechner_pipeline.bestand.report` (the engine),
following the toolbox split. Read-only, NOT a gate: it writes no ledger entry
and takes no part in acceptance — it renders a Parquet portfolio into one
self-contained HTML file for a non-technical (actuarial) audience.

Usage::

    python -m rechner_pipeline.toolbox.bestand_report \\
        --portfolio bestand.parquet --out bericht.html \\
        [--stichtage 2005-01-01,2010-01-01] [--titel "KLV-Bestand"]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path
from typing import List, Optional

from rechner_pipeline.bestand.parquet_io import portfolio_hash, read_portfolio
from rechner_pipeline.bestand.report import render_html


def _parse_stichtage(raw: Optional[str]) -> Optional[List[_dt.date]]:
    if not raw:
        return None
    try:
        return [_dt.date.fromisoformat(part.strip()) for part in raw.split(",") if part.strip()]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Ungueltiges Stichtags-Datum: {exc}") from exc


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.toolbox.bestand_report",
        description=(
            "Deterministischer Bestandsbericht (HTML mit Inline-Grafiken) aus "
            "einer Portfolio-Parquet-Datei. Read-only, kein Gate."
        ),
    )
    parser.add_argument("--portfolio", required=True, help="Pfad zur Parquet-Datei.")
    parser.add_argument("--out", default=None, help="Zieldatei (Default: stdout).")
    parser.add_argument(
        "--stichtage",
        default=None,
        help="Kommagetrennte ISO-Daten; Default: Jahresraster über die Vertragslaufzeiten.",
    )
    parser.add_argument("--titel", default="Bestandsbericht")
    ns = parser.parse_args(argv)

    portfolio_path = Path(ns.portfolio)
    if not portfolio_path.is_file():
        print(f"bestand_report: Portfolio nicht gefunden: {portfolio_path}", file=sys.stderr)
        return 2
    try:
        stichtage = _parse_stichtage(ns.stichtage)
    except argparse.ArgumentTypeError as exc:
        print(f"bestand_report: {exc}", file=sys.stderr)
        return 2

    df = read_portfolio(portfolio_path)
    html = render_html(
        df,
        stichtage=stichtage,
        titel=ns.titel,
        quelle_hash=portfolio_hash(portfolio_path),
    )
    if ns.out:
        out_path = Path(ns.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
