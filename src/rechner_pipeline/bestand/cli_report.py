"""``bestand_report`` toolbox command — deterministic portfolio report (HTML).

Thin CLI wrapper over :mod:`rechner_pipeline.bestand.report` (the engine),
following the toolbox split. Read-only, NOT a gate: it writes no ledger entry
and takes no part in acceptance — it renders a Parquet portfolio into one
self-contained HTML file for a non-technical (actuarial) audience.

Usage::

    python -m rechner_pipeline.bestand.cli_report \\
        --portfolio bestand.parquet --out bericht.html \\
        [--historie historie.parquet --ledger ledger.parquet] \\
        [--scheiben scheiben.parquet] [--config bestand_klv.toml] \\
        [--bis 2035-01-01] [--stichtag 2026-01-01] \\
        [--stichtage 2005-01-01,2010-01-01] [--titel "KLV-Bestand"]

``--historie``/``--ledger`` (beide zusammen, ein ``fortschreiben``-Lauf)
schalten die Ereignis-/Abgangs-Sichten frei; ``--config`` zusaetzlich die
aktuariellen Kennzahlen, ``--bis`` (der Fortschreibungs-Horizont) die
Bestandsbewegung in Nachweisungs-Struktur, ``--stichtag`` deren Teilung in
Historie und Prognose. Ohne ``--stichtag`` gilt ``meta.referenzstichtag``
aus der Config — der Referenzstichtag ist eine Eigenschaft des Bestands,
das Flag uebersteuert ihn nur. ``--scheiben`` ist Pflicht,
sobald der Ledger dynamische Erhoehungen enthaelt.

Knoten: klv, bu
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
        prog="python -m rechner_pipeline.bestand.cli_report",
        description=(
            "Deterministischer Bestandsbericht (HTML mit Inline-Grafiken) aus "
            "einer Portfolio-Parquet-Datei. Read-only, kein Gate."
        ),
    )
    parser.add_argument("--portfolio", required=True, help="Pfad zur Parquet-Datei.")
    parser.add_argument("--out", default=None, help="Zieldatei (Default: stdout).")
    parser.add_argument(
        "--historie",
        default=None,
        help="Statushistorie-Parquet (nur zusammen mit --ledger).",
    )
    parser.add_argument(
        "--ledger",
        default=None,
        help="Ereignis-Ledger-Parquet (nur zusammen mit --historie).",
    )
    parser.add_argument(
        "--config",
        default=None,
        help=(
            "Bestand-Config (TOML) fuer die aktuariellen Kennzahlen — dieselbe, "
            "mit der Bestand und Fortschreibung erzeugt wurden."
        ),
    )
    parser.add_argument(
        "--scheiben",
        default=None,
        help="Erhoehungsscheiben-Parquet (nur zusammen mit --historie/--ledger).",
    )
    parser.add_argument(
        "--merkmale",
        default=None,
        help=(
            "Merkmalsauspraegungen-Parquet — Pflicht, sobald eine "
            "Tarifgeneration der Config in Zellen aufgeteilt ist (sonst "
            "waere die Zellwahl geraten)."
        ),
    )
    parser.add_argument(
        "--bis",
        default=None,
        help=(
            "Fortschreibungs-Horizont (ISO-Datum, dasselbe wie beim "
            "fortschreiben-Lauf) — schaltet die Bestandsbewegung in "
            "Nachweisungs-Struktur frei (nur mit --historie/--ledger)."
        ),
    )
    parser.add_argument(
        "--stichtag",
        default=None,
        help=(
            "Referenzstichtag (ISO-Datum): teilt die Nachweisungen in "
            "Historie (bis zum Stichtag) und Prognose (danach). "
            "Default: meta.referenzstichtag aus --config, falls gesetzt."
        ),
    )
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

    if (ns.historie is None) != (ns.ledger is None):
        print(
            "bestand_report: --historie und --ledger gehoeren zusammen "
            "(ein fortschreiben-Lauf)",
            file=sys.stderr,
        )
        return 2
    if ns.scheiben and not ns.historie:
        print(
            "bestand_report: --scheiben nur zusammen mit --historie/--ledger",
            file=sys.stderr,
        )
        return 2
    stichtag = None
    if ns.stichtag:
        try:
            stichtag = _dt.date.fromisoformat(ns.stichtag)
        except ValueError as exc:
            print(f"bestand_report: Ungueltiges --stichtag-Datum: {exc}", file=sys.stderr)
            return 2
    bis = None
    if ns.bis:
        if not ns.historie:
            print(
                "bestand_report: --bis nur zusammen mit --historie/--ledger",
                file=sys.stderr,
            )
            return 2
        try:
            bis = _dt.date.fromisoformat(ns.bis)
        except ValueError as exc:
            print(f"bestand_report: Ungueltiges --bis-Datum: {exc}", file=sys.stderr)
            return 2
    historie = ledger = scheiben = None
    if ns.historie:
        for name, pfad in (("Historie", ns.historie), ("Ledger", ns.ledger)):
            if not Path(pfad).is_file():
                print(f"bestand_report: {name} nicht gefunden: {pfad}", file=sys.stderr)
                return 2
        historie = read_portfolio(Path(ns.historie))
        ledger = read_portfolio(Path(ns.ledger))
        if ns.scheiben:
            if not Path(ns.scheiben).is_file():
                print(f"bestand_report: Scheiben nicht gefunden: {ns.scheiben}", file=sys.stderr)
                return 2
            scheiben = read_portfolio(Path(ns.scheiben))

    merkmale = None
    if ns.merkmale:
        if not Path(ns.merkmale).is_file():
            print(f"bestand_report: Merkmale nicht gefunden: {ns.merkmale}",
                  file=sys.stderr)
            return 2
        merkmale = read_portfolio(Path(ns.merkmale))

    config = None
    if ns.config:
        config_path = Path(ns.config)
        if not config_path.is_file():
            print(f"bestand_report: Config nicht gefunden: {config_path}", file=sys.stderr)
            return 2
        from rechner_pipeline.bestand.config import load_config

        try:
            config = load_config(config_path)
        except ValueError as exc:
            print(f"bestand_report: {exc}", file=sys.stderr)
            return 2
        fehler = config.validate()
        if fehler:
            print(f"bestand_report: Config ungueltig: {'; '.join(fehler)}", file=sys.stderr)
            return 2
        # Der Referenzstichtag ist eine Eigenschaft des Bestands: er kommt
        # aus der Config und wird per --stichtag nur uebersteuert.
        if stichtag is None:
            stichtag = config.referenzstichtag

    df = read_portfolio(portfolio_path)
    # Derselbe Wachposten wie in einzelwerte_am und Gate P-B1 — aber an der
    # CLI-Grenze, wo er auch ohne --config greift. Ohne Journal rendert
    # render_html den strukturellen Verlauf direkt aus dem Stamm und ruft
    # einzelwerte_am nie; gemessen zum Stichtag 2016: 464 statt 1.213
    # Vertraege und 37,5 statt 95,1 Mio Versicherungssumme, bei Exit 0 und
    # ohne jeden Vorbehalt im Bericht. Ein Bericht ist das, was ein Mensch
    # anschaut — er darf nicht still zu wenig zeigen.
    if historie is None or len(historie) == 0:
        folge = df["status_id"] > 1
        if bool(folge.any()):
            betroffen = sorted(df.loc[folge, "police_id"])[:5]
            print(
                f"bestand_report: {int(folge.sum())} Vertraege tragen einen "
                f"Folgezustand (status_id > 1, z. B. police {betroffen}), "
                "aber es wurde keine Historie uebergeben. Stornierte und "
                "verstorbene Vertraege kehrten als beitragspflichtig in den "
                "Bericht zurueck — --historie und --ledger mitgeben "
                "(ADR-011)",
                file=sys.stderr,
            )
            return 2
    if scheiben is not None:
        from rechner_pipeline.models.bestand import validate_scheiben

        fehler = validate_scheiben(df, scheiben, historie=historie)
        if fehler:
            print(
                f"bestand_report: Scheiben ungueltig: {'; '.join(fehler[:3])}",
                file=sys.stderr,
            )
            return 2
    try:
        html = render_html(
            df,
            stichtage=stichtage,
            titel=ns.titel,
            quelle_hash=portfolio_hash(portfolio_path),
            historie=historie,
            ledger=ledger,
            config=config,
            scheiben=scheiben,
            merkmale=merkmale,
            bis=bis,
            stichtag=stichtag,
        )
    except ValueError as exc:
        print(f"bestand_report: {exc}", file=sys.stderr)
        return 2
    if ns.out:
        out_path = Path(ns.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(html)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
