"""Vorbedingungen eines Bestands-Bundles — die EINE Pruefengine.

Stamm, Historie, Ledger, Scheiben und Config bilden zusammen einen Lauf.
Wer auf ihnen rechnet, muss sie gemeinsam pruefen: Gate P-B1
(:mod:`rechner_pipeline.gates.bestand_validate`), der Abnahmebericht und
der Abschluss-Produzent (:mod:`rechner_pipeline.bestand.cli_abschluss`)
benutzen bewusst DIESELBE Funktion. Drei Pfade mit drei eigenen
Teilpruefungen haben denselben Datenstand dreimal verschieden beurteilt —
und ausgerechnet der unumkehrbare (der Abschluss) war der nachlaessigste.

Die Engine wohnt hier und nicht im Gate, weil die Schichtenkarte
``bestand -> gates`` verbietet: der Abschluss-Produzent liegt in
``bestand`` und koennte sie im Gate nicht erreichen.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    SCHEIBEN_NAMES,
    STATUS_HISTORIE_NAMES,
    STAMM_NAMES,
    validate_portfolio,
    validate_scheiben,
    validate_stamm_journal,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import sanity_check


def pruefe_pb1_eingaenge(
    eingaben: Mapping[str, Path],
    *,
    bis: Optional[_dt.date] = None,
) -> Tuple[Dict[str, int], List[dict], List[dict]]:
    """P-B1-Engines rein lesend auf einer benannten Eingabenkonfiguration.

    Der CLI-Produzent und A-M4 benutzen bewusst dieselbe Funktion. So ist ein
    frei editierbares, passend neu gehashtes P-B1-Ledger keine Selbstaussage:
    A-M4 fuehrt Schema-, Invarianten-, Bewegungs- und optionale Sanity-Pruefung
    auf den aktuellen Bytes erneut aus.

    Rueckgabe: ``(geprueft, contract_fehler, usage_fehler)``.
    """
    erlaubt = {"portfolio", "historie", "scheiben", "ledger", "config"}
    rollen = set(eingaben)
    errors: List[dict] = []
    usage_errors: List[dict] = []
    if "portfolio" not in rollen:
        return {}, [{"code": "portfolio", "message": "Portfolio-Rolle fehlt"}], []
    if not rollen <= erlaubt:
        return {}, [{
            "code": "eingangsrollen",
            "message": f"Unbekannte P-B1-Eingangsrollen: {sorted(rollen - erlaubt)}",
        }], []

    tabellen: Dict[str, Any] = {}
    spaltenvertrag = {
        "portfolio": STAMM_NAMES,
        "historie": STATUS_HISTORIE_NAMES,
        "scheiben": SCHEIBEN_NAMES,
        "ledger": LEDGER_NAMES,
    }
    for rolle in ("portfolio", "historie", "scheiben", "ledger"):
        if rolle not in eingaben:
            continue
        try:
            tabellen[rolle] = read_portfolio(
                eingaben[rolle], expected_columns=spaltenvertrag[rolle]
            )
        except Exception as exc:  # noqa: BLE001 — Parquet-Backends variieren
            errors.append({
                "code": rolle,
                "message": f"{rolle}-Datei ist nicht als Bestand lesbar: {exc}",
            })

    portfolio = tabellen.get("portfolio")
    historie = tabellen.get("historie")
    scheiben = tabellen.get("scheiben")
    ledger = tabellen.get("ledger")
    geprueft: Dict[str, int] = {}
    if portfolio is not None:
        geprueft["portfolio_zeilen"] = int(len(portfolio))
        try:
            for meldung in validate_portfolio(portfolio):
                errors.append({"code": "portfolio", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "portfolio", "message": str(exc)})
    if portfolio is not None and historie is None and not errors:
        # Ein gefuehrter Bestand mit (zustandsgueltigen) Folgezustaenden
        # verlangt sein Journal: Ohne die Buchungen ist ein behaupteter
        # Zustand kein Beleg (ADR-011). Zustands-UNGUELTIGE Zeilen sind
        # dagegen Datenfehler und stehen bereits oben in den Contract-Fehlern
        # — sie werden nicht zur Argumentfrage umgedeutet.
        try:
            if (portfolio["status_id"] > 1).any():
                usage_errors.append({
                    "code": "missing_arg",
                    "message": "Portfolio traegt Folgezustaende (status_id > 1) "
                    "— --historie ist erforderlich: der Stammzustand muss "
                    "gegen den juengsten Journalstand geprueft werden",
                })
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "portfolio", "message": str(exc)})
    if portfolio is not None and historie is not None:
        geprueft["historie_zeilen"] = int(len(historie))
        try:
            for meldung in validate_statushistorie(portfolio, historie):
                errors.append({"code": "historie", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "historie", "message": str(exc)})
        # Deckungsgleichheit von Stamm und Journal (ADR-011): der Stammsatz
        # IST der juengste Journalstand — sonst ist der Bestand keine
        # Fuehrung, sondern eine Behauptung.
        try:
            for meldung in validate_stamm_journal(portfolio, historie):
                errors.append({"code": "fuehrung", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "fuehrung", "message": str(exc)})
    if portfolio is not None and scheiben is not None:
        geprueft["scheiben_zeilen"] = int(len(scheiben))
        try:
            for meldung in validate_scheiben(
                portfolio, scheiben, historie=historie
            ):
                errors.append({"code": "scheiben", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "scheiben", "message": str(exc)})

    if ledger is not None and scheiben is None:
        try:
            hat_erhoehungen = bool((ledger["ereignis"] == "ERH").any())
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})
            hat_erhoehungen = False
        if hat_erhoehungen:
            usage_errors.append({
                "code": "missing_arg",
                "message": "Ledger enthaelt dynamische Erhoehungen (ERH) — "
                "--scheiben ist erforderlich, sonst sind die Bestandssummen "
                "systematisch zu niedrig und die Bewegungs-Identitaet "
                "falsch-positiv verletzt",
            })

    if (
        portfolio is not None
        and ledger is not None
        and historie is not None
        and not errors
        and not usage_errors
    ):
        from rechner_pipeline.bestand.kennzahlen import (
            bewegungskonto,
            bu_bewegungskonto,
        )

        konto: List[dict] = []
        try:
            konto = bewegungskonto(
                portfolio, historie, ledger, scheiben, bis=bis
            )
            konto += bu_bewegungskonto(
                portfolio, historie, ledger, bis=bis
            )
        except Exception as exc:  # noqa: BLE001 — malformed inputs blockieren
            errors.append({"code": "ledger", "message": str(exc)})
        geprueft["bewegungsjahre"] = len(konto)
        for zeile in konto:
            for track, oks in zeile["identitaet"].items():
                for mass, ok in oks.items():
                    if not ok:
                        errors.append({
                            "code": "bewegung",
                            "message": (
                                f"Jahr {zeile['jahr']} {track}/{mass}: "
                                "Anfang + Zugang - Abgang != Endbestand"
                            ),
                        })

    if "config" in eingaben and portfolio is not None:
        try:
            config = load_config(eingaben["config"])
        except (OSError, ValueError) as exc:
            errors.append({"code": "config", "message": str(exc)})
        else:
            try:
                for meldung in config.validate():
                    errors.append({"code": "config", "message": meldung})
                for meldung in sanity_check(portfolio, config.plausibilitaet):
                    errors.append({"code": "sanity", "message": meldung})
                geprueft["sanity_baender"] = len(config.plausibilitaet)
            except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                errors.append({"code": "sanity", "message": str(exc)})
    return geprueft, errors, usage_errors
