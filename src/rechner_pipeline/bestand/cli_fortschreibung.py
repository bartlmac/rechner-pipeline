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
        [--uebernahme faelle/<fall>/abgeleitet/bestand]   # migrierter Bestand \\
        [--neuzugang-ab 2010-01-01] --out-dir lauf/

``--uebernahme`` nimmt das Erzeugnis von ``gates.bestand_uebernehmen`` in
den Lauf: Der uebernommene Bestand wird dem eigenen VORANGESTELLT und in
DEMSELBEN Fortschreibungslauf mitgefahren — ein GeVo-Strom, ein Erzeuger,
auch nach einer Migration. Zwei getrennte Laeufe zu mischen ergaebe einen
Bestand, in dem ein Teil fortgeschrieben ist und der andere nicht; genau
daran brach die Bestandsbewegung (ADR-015). Die Buchungen der Uebernahme
(Zugang, bei beitragsfrei ankommenden Vertraegen die Umbuchung) stehen
dem Fortschreibungs-Journal voran, denn sie liegen vor dessen erstem
simulierten Jahr.

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


def _lies_uebernahme(verzeichnis: Path) -> dict:
    """Die Tabellen eines uebernommenen Bestands einlesen.

    Erwartet wird das Erzeugnis von ``gates.bestand_uebernehmen``. Fehlt
    eine der drei Pflichttabellen, ist es kein uebernommener Bestand,
    sondern ein halber — die Meldung sagt, welche.
    """
    from rechner_pipeline.models.bestand import (
        LEDGER_NAMES,
        MERKMALE_NAMES,
        STAMM_NAMES,
        STATUS_HISTORIE_NAMES,
    )

    vertraege = {
        "bestand": STAMM_NAMES,
        "historie": STATUS_HISTORIE_NAMES,
        "ledger": LEDGER_NAMES,
    }
    fehlend = [n for n in vertraege if not (verzeichnis / f"{n}.parquet").is_file()]
    if fehlend:
        raise ValueError(
            f"Uebernahme {verzeichnis}: {fehlend} fehlen — erwartet wird das "
            "Erzeugnis von gates.bestand_uebernehmen"
        )
    tabellen = {
        name: read_portfolio(verzeichnis / f"{name}.parquet", expected_columns=spalten)
        for name, spalten in vertraege.items()
    }
    merkmale_pfad = verzeichnis / "merkmale.parquet"
    tabellen["merkmale"] = (
        read_portfolio(merkmale_pfad, expected_columns=MERKMALE_NAMES)
        if merkmale_pfad.is_file() else None
    )
    return tabellen


def _mit_uebernahme(eigen, uebernommen):
    """Eigenen und uebernommenen Bestand zu EINER Basis fuegen.

    Beide gehen in denselben Fortschreibungslauf. Zwei getrennte Laeufe
    zu mischen ergaebe einen Bestand, in dem ein Teil fortgeschrieben ist
    und der andere nicht — genau daran brach die Bestandsbewegung
    (ADR-015).
    """
    import pandas as pd

    from rechner_pipeline.models.bestand import STAMM_NAMES

    beide = pd.concat([eigen, uebernommen], ignore_index=True)
    doppelt = beide["police_id"][beide["police_id"].duplicated()]
    if len(doppelt):
        raise ValueError(
            f"police_id-Kollision zwischen eigenem und uebernommenem Bestand: "
            f"{sorted(set(doppelt))[:5]} — die Nummernkreise muessen getrennt "
            "sein, sonst bezeichnet eine Nummer zwei Vertraege"
        )
    return (
        beide.sort_values("police_id", kind="stable")
        .reset_index(drop=True)[list(STAMM_NAMES)]
    )


def _voran(uebernahme, fortschreibung, sortierung):
    """Das Journal der Uebernahme dem der Fortschreibung voranstellen."""
    import pandas as pd

    beide = pd.concat([uebernahme, fortschreibung], ignore_index=True)
    return beide.sort_values(sortierung, kind="stable").reset_index(drop=True)


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
        "--uebernahme",
        default=None,
        help=(
            "Verzeichnis eines uebernommenen Bestands (Erzeugnis von "
            "gates.bestand_uebernehmen): bestand/historie/ledger.parquet, "
            "optional merkmale.parquet. Wird mitgefahren, nicht danach "
            "angeklebt."
        ),
    )
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

    # Der Referenzstichtag ist eine Eigenschaft des Bestands (Config);
    # --neuzugang-ab SOLL mit ihm uebereinstimmen -- er ist genau die
    # Grenze zwischen Batch-Erzeugung und simuliertem Neuzugang. Eine
    # Abweichung kann gewollt sein (Sonderlaeufe), faellt aber sonst
    # still auseinander: Bestand und Bericht meinen dann verschiedene
    # Grenzen. Deshalb ein Hinweis, kein Fehler.
    if (
        neuzugang_ab is not None
        and config.referenzstichtag is not None
        and neuzugang_ab != config.referenzstichtag
    ):
        print(
            "bestand_fortschreibung: HINWEIS: --neuzugang-ab "
            f"{neuzugang_ab.isoformat()} weicht vom referenzstichtag der "
            f"Config ab ({config.referenzstichtag.isoformat()}) — der "
            "Referenzstichtag ist die Grenze zwischen Batch und Neuzugang; "
            "eine Abweichung gehoert begruendet",
            file=sys.stderr,
        )

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
        uebernahme = None
        if ns.uebernahme:
            uebernahme = _lies_uebernahme(Path(ns.uebernahme))
            basis = _mit_uebernahme(basis, uebernahme["bestand"])
        merkmale = None
        if ns.merkmale:
            merkmale_path = Path(ns.merkmale)
            if not merkmale_path.is_file():
                print(
                    f"bestand_fortschreibung: Merkmale nicht gefunden: {merkmale_path}",
                    file=sys.stderr)
                return 2
            merkmale = read_portfolio(merkmale_path)
        elif uebernahme is not None:
            # Die Uebernahme bringt ihre Merkmalstabelle mit; sie extra zu
            # verlangen hiesse, dieselbe Datei zweimal zu benennen.
            merkmale = uebernahme["merkmale"]
        ergebnis = fortschreiben(basis, config, bis, neuzugang_ab=neuzugang_ab,
                                 merkmale=merkmale)
        # Das Journal der Uebernahme geht dem der Fortschreibung VORAUS:
        # Zugang und Umbuchung liegen am Bestandszugang, also vor dem
        # ersten simulierten Vertragsjahr.
        historie, ledger = ergebnis.historie, ergebnis.ledger
        if uebernahme is not None:
            historie = _voran(uebernahme["historie"], historie,
                              ["police_id", "status_id"])
            ledger = _voran(uebernahme["ledger"], ledger,
                            ["police_id", "status_date"])
        # Der Gesamtbestand ist GEFUEHRT (ADR-011): der Stammsatz traegt den
        # aktuellen Zustand am Horizont, das Journal (historie/ledger) die
        # vollstaendige Aufzeichnung. bestand.parquet bleibt der Basisbestand
        # (Ursprungszustaende am Generierungsbeginn).
        gesamt = fuehre_fort(mit_zugaengen(basis, ergebnis.zugaenge), historie)
    except (EreignisError, ValueError) as exc:
        print(f"bestand_fortschreibung: {exc}", file=sys.stderr)
        return 2

    write_portfolio(historie, out_dir / "historie.parquet")
    write_portfolio(ledger, out_dir / "ledger.parquet")
    write_portfolio(ergebnis.scheiben, out_dir / "scheiben.parquet")
    write_portfolio(ergebnis.zugaenge, out_dir / "zugaenge.parquet")
    write_portfolio(gesamt, out_dir / "bestand_gesamt.parquet")

    print(
        f"bestand_fortschreibung: {len(basis)} Basisvertraege"
        + (f" (davon {len(uebernahme['bestand'])} uebernommen)"
           if uebernahme is not None else "")
        + f", {len(ergebnis.zugaenge)} Neuzugaenge, {len(ledger)} GeVos, "
        f"{len(ergebnis.scheiben)} Erhoehungsscheiben -> {out_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
