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
import io
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.manifest import (
    ROLLEN_DATEIEN,
    horizont as manifest_horizont,
    sha256_bytes,
)
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    MERKMALE_NAMES,
    SCHEIBEN_NAMES,
    STATUS_HISTORIE_NAMES,
    STAMM_NAMES,
    validate_ledger,
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
    manifest: Optional[Mapping[str, Any]] = None,
) -> Tuple[Dict[str, int], List[dict], List[dict]]:
    """P-B1-Engines rein lesend auf einer benannten Eingabenkonfiguration.

    Sicht fuer Konsumenten, die nur das URTEIL brauchen (die Gates). Wer
    anschliessend mit den Daten WEITERRECHNET, nimmt
    :func:`lies_und_pruefe_pb1` und verwendet die zurueckgegebenen
    Tabellen — sonst entsteht die Luecke aus T18-03: zwischen Pruefung
    und zweitem Lesen laesst sich die Datei tauschen.

    Rueckgabe: ``(geprueft, contract_fehler, usage_fehler)``.
    """
    _, geprueft, fehler, usage = lies_und_pruefe_pb1(
        eingaben, bis=bis, manifest=manifest)
    return geprueft, fehler, usage


def lies_und_pruefe_pb1(
    eingaben: Mapping[str, Path],
    *,
    bis: Optional[_dt.date] = None,
    manifest: Optional[Mapping[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[str, int], List[dict], List[dict]]:
    """Pruefen UND die geprueften Tabellen zurueckgeben.

    Der CLI-Produzent und A-M4 benutzen bewusst dieselbe Funktion. So ist ein
    frei editierbares, passend neu gehashtes P-B1-Ledger keine Selbstaussage:
    A-M4 fuehrt Schema-, Invarianten-, Bewegungs- und optionale Sanity-Pruefung
    auf den aktuellen Bytes erneut aus.

    **Warum sie die Tabellen herausgibt** (externes Review T18-03): Wer
    prueft und den Konsumenten danach SELBST lesen laesst, hat nur den
    Zustand zwischen zwei Lesevorgaengen geprueft. Im Nachweis wurde
    ``scheiben.parquet`` direkt nach bestandener Pruefung atomar gegen
    eine gueltige leere Tabelle getauscht; der Abschluss lief mit Exit 0
    durch und publizierte einen um 3,8 Mio EUR zu niedrigen Stand. Die
    Reparatur ist nicht eine weitere Pruefung, sondern die Beseitigung
    des zweiten Lesevorgangs: Was geprueft wurde, wird auch verarbeitet.

    **Mit Laufmanifest** (externes Review T18-02): Ist ``manifest`` das
    Manifest des Laufs (:mod:`rechner_pipeline.bestand.manifest`), dann
    muss ``bis`` der dort belegte Horizont sein, und die Bytes JEDER
    gelesenen Rolle muessen der dort eingetragenen Summe entsprechen —
    ebenso die Config. Jede Datei wird genau einmal von der Platte
    gelesen; gehasht und geparst werden dieselben Bytes. Damit sind
    "Teile aus verschiedenen Laeufen" und "behaupteter Horizont" keine
    Frage der Plausibilitaet mehr, sondern der Identitaet.

    Rueckgabe: ``(tabellen, geprueft, contract_fehler, usage_fehler)``.
    ``tabellen`` traegt die Rollen, die gelesen werden konnten, und unter
    ``config`` die geparste Config, wenn eine uebergeben wurde.
    """
    erlaubt = {"portfolio", "historie", "scheiben", "ledger", "merkmale", "config"}
    rollen = set(eingaben)
    errors: List[dict] = []
    usage_errors: List[dict] = []
    if "portfolio" not in rollen:
        return ({}, {},
                [{"code": "portfolio", "message": "Portfolio-Rolle fehlt"}], [])
    if not rollen <= erlaubt:
        return ({}, {}, [{
            "code": "eingangsrollen",
            "message": f"Unbekannte P-B1-Eingangsrollen: {sorted(rollen - erlaubt)}",
        }], [])

    if manifest is not None and bis is not None:
        belegt = manifest_horizont(manifest)
        if belegt != bis:
            errors.append({
                "code": "manifest",
                "message": (
                    f"--bis {bis.isoformat()} widerspricht dem Laufmanifest: "
                    f"der Lauf wurde bis {belegt.isoformat()} simuliert. "
                    "Der Horizont ist eine Eigenschaft des Laufs, nicht des "
                    "Aufrufs — --bis auf den belegten Wert setzen oder den "
                    "Lauf neu fortschreiben"
                ),
            })

    tabellen: Dict[str, Any] = {}
    # SHA-256 der Bytes, die geparst wurden — fuer Konsumenten, die den
    # Stand benennen wollen (Berichtsfuss, Beleg), ohne erneut zu lesen.
    hashes: Dict[str, str] = {}
    spaltenvertrag = {
        "portfolio": STAMM_NAMES,
        "historie": STATUS_HISTORIE_NAMES,
        "scheiben": SCHEIBEN_NAMES,
        "ledger": LEDGER_NAMES,
        "merkmale": MERKMALE_NAMES,
    }
    for rolle in ("portfolio", "historie", "scheiben", "ledger", "merkmale"):
        if rolle not in eingaben:
            continue
        # Genau EIN Lesevorgang je Datei: Die Bytes, die gegen das Manifest
        # gehasht werden, sind die Bytes, die geparst werden.
        try:
            daten = Path(eingaben[rolle]).read_bytes()
        except OSError as exc:
            errors.append({
                "code": rolle,
                "message": f"{rolle}-Datei ist nicht lesbar: {exc}",
            })
            continue
        hashes[rolle] = sha256_bytes(daten)
        errors.extend(_manifest_befund(manifest, rolle, daten))
        try:
            tabellen[rolle] = read_portfolio(
                io.BytesIO(daten), expected_columns=spaltenvertrag[rolle]
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

    if portfolio is not None and ledger is not None:
        # Semantik der Buchungen (T18-06) und zeilenweise Bindung an die
        # Scheiben (T18-01) — vor der Bewegungs-Identitaet, die nur
        # Jahressummen sieht.
        geprueft["ledger_zeilen"] = int(len(ledger))
        try:
            for meldung in validate_ledger(
                portfolio, ledger, historie=historie, scheiben=scheiben
            ):
                errors.append({"code": "ledger", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})

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
            config_bytes = Path(eingaben["config"]).read_bytes()
            hashes["config"] = sha256_bytes(config_bytes)
            errors.extend(_manifest_befund(manifest, "config", config_bytes))
            config = config_aus_text(config_bytes.decode("utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            errors.append({"code": "config", "message": str(exc)})
        else:
            tabellen["config"] = config
            try:
                for meldung in config.validate():
                    errors.append({"code": "config", "message": meldung})
                for meldung in sanity_check(portfolio, config.plausibilitaet):
                    errors.append({"code": "sanity", "message": meldung})
                geprueft["sanity_baender"] = len(config.plausibilitaet)
            except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                errors.append({"code": "sanity", "message": str(exc)})
            # Betragsidentitaet je Buchung (T20-04): erst mit den
            # Rechnungsgrundlagen der Config ist der Kern herleitbar. Nur
            # auf formal gueltigen Zeilen — sonst meldete jede
            # Formverletzung zusaetzlich einen Herleitungsfehler.
            if (
                ledger is not None
                and not any(e["code"] in ("ledger", "portfolio", "config") for e in errors)
            ):
                try:
                    for meldung in pruefe_ledger_betraege(
                        portfolio, ledger, config, scheiben=scheiben,
                        historie=historie, merkmale=tabellen.get("merkmale"),
                    ):
                        errors.append({"code": "ledger", "message": meldung})
                    geprueft["betraege_hergeleitet"] = int(
                        ledger["ereignis"].isin(("ZUG", "STO", "PEX", "TOD", "ABL",
                                                 "INV", "REA")).sum())
                except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                    errors.append({"code": "ledger", "message": str(exc)})
    if manifest is not None:
        geprueft["manifest_gebunden"] = len(
            [r for r in eingaben if r in tabellen])
    tabellen["sha256"] = hashes
    return tabellen, geprueft, errors, usage_errors


def _manifest_befund(
    manifest: Optional[Mapping[str, Any]], rolle: str, daten: bytes
) -> List[dict]:
    """Die gelesenen Bytes einer Rolle gegen den Manifest-Eintrag halten."""
    if manifest is None:
        return []
    if rolle == "config":
        erwartet = manifest["config"]["sha256"]
        was = "die Config"
    else:
        datei = ROLLEN_DATEIEN[rolle]
        erwartet = manifest.get("ausgaben", {}).get(datei)
        was = datei
        if erwartet is None:
            return [{
                "code": "manifest",
                "message": f"{was} ist im Laufmanifest nicht als Ausgabe "
                "eingetragen — sie stammt nicht aus diesem Lauf",
            }]
    if sha256_bytes(daten) != erwartet:
        return [{
            "code": "manifest",
            "message": (
                f"{was} ({rolle}) hat nicht die im Laufmanifest belegte "
                "SHA-256 — die Datei ist nicht die, die der Lauf geschrieben "
                "hat (anderer Lauf oder nachtraeglich veraendert)"
            ),
        }]
    return []
