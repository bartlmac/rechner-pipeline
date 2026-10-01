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
    horizont as manifest_horizont,
    lies_manifest_bytes,
    manifest_aus_bytes,
    MANIFEST_DATEI,
    ManifestError,
    rollen_dateien,
    ROLLEN_DATEIEN,
    sha256_bytes,
)
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.bestand.ledger_bindung import (
    HERGELEITET,
    pruefe_ledger_betraege,
    pruefe_reduktionen_tarifwerk,
    pruefe_scheiben_tarifwerk,
)
from rechner_pipeline.kern.vorgangsfolge import ERH, PEX, RED, TKU
from rechner_pipeline.models.bestand import (
    REDUKTION_EREIGNISSE,
    LEDGER_NAMES,
    MERKMALE_NAMES,
    SCHEIBEN_NAMES,
    REDUKTIONEN_NAMES,
    SCHICHTEN_NAMES,
    VERANKERUNG_NAMES,
    STATUS_HISTORIE_NAMES,
    STAMM_NAMES,
    validate_ledger,
    validate_portfolio,
    validate_scheiben,
    validate_reduktionen,
    validate_schichten,
    validate_verankerung,
    validate_stamm_journal,
    validate_statushistorie,
)
from rechner_pipeline.qa.bestand import sanity_check

#: Die Rollen, die die Engine annimmt: die Rollentabelle des Erzeugers plus
#: die Config — an EINER Stelle, damit kein Konsument (Gate, Abnahmebericht,
#: Betrieb) sie abtippt (Betriebsbefund N-01). Der Abnahmebericht liest sie
#: hier, nicht aus ``bestand.manifest``: die Kanten-Ratsche (ADR-017) kennt
#: gates -> bestand.vorbedingungen, nicht gates -> bestand.manifest.
PB1_ROLLEN = frozenset(ROLLEN_DATEIEN) | {"config"}

#: Welche Datei eine P-B1-Rolle traegt — hier weitergereicht, damit
#: die gates-Schicht sie nicht abtippen und nicht selbst in die
#: Vorzeige greifen muss (ADR-017, TOOL_NACH_VORZEIGE_ERLAUBT).
PB1_ROLLEN_DATEIEN = ROLLEN_DATEIEN

#: Je Vorgangsart der Folge (``kern.vorgangsfolge.RANG``) die Tabellen, die
#: ihr Vertragsjahr tragen (Pruefrunde H, H02/H04). Jeder dieser Wege geht
#: durch :func:`vorgangsjahr_fehler` und damit durch die Jahresgrenzen des
#: Kerns; ein Test haelt die Menge Art mal Weg mit ``==`` gegen das Verhalten.
VORGANGSJAHR_WEGE: Dict[str, Tuple[str, ...]] = {
    PEX: ("historie", "ledger"),
    RED: ("reduktionen", "ledger"),
    TKU: ("reduktionen", "ledger"),
    ERH: ("scheiben", "ledger"),
}


class _Dauern:
    """Versicherungs- und Beitragsdauer eines Vertrags — alles, was die
    Jahresgrenzen des Kerns vom Modellpunkt lesen (``n``, ``t``). P-B1 prueft
    die Grenzen auch ohne Config, also ohne Rechnungsgrundlagen; liest der
    Kern dort einmal mehr, faellt das hier laut auf (AttributeError), nicht
    still."""

    __slots__ = ("n", "t")

    def __init__(self, n: int, t: int) -> None:
        self.n, self.t = int(n), int(t)


def vorgangsjahr_fehler(
    portfolio: Any,
    *,
    historie: Any = None,
    ledger: Any = None,
    reduktionen: Any = None,
    scheiben: Any = None,
) -> List[str]:
    """Die Jahresgrenzen der Vorgaenge auf JEDEM Tabellenweg — die Regel des
    Kerns (``kern.beitragsreduktion.pruefe_vorgangsjahr``), nicht nachgebaut.

    Pruefrunde H, H02/H04: Eine Beitragsfreistellung am oder nach dem
    Beitragsende (a >= t) nahmen P-B1, Abschluss, Bericht und Bewertung an;
    nur der Kern verweigerte sie, und nur, wenn der Vertrag ueber die
    Vorgangsfolge lief — also nur mit registrierter Herabsetzung oder
    Teilkuendigung. Die Folge prueft ihre Vorgaenge erst, wenn sie gebaut
    wird; ein Vertrag ohne Folge lief an der Regel vorbei. Jetzt fragt die
    Engine, durch die jeder Leser der Tabellen muss, den Kern fuer jede Zeile
    jeder Art auf jedem Weg (:data:`VORGANGSJAHR_WEGE`), unabhaengig davon, ob
    der Vertrag weitere Vorgaenge hat und ob eine Config vorliegt.

    Das Vertragsjahr einer Zeile: Historie aus ``status_date`` (vollendete
    Monate seit Versicherungsbeginn durch 12, wie die Bewertung das PEX-Jahr
    liest), Ledger ``vertragsjahr`` — ohne die Buchungen, die der Zugang
    schreibt (``models.bestand.zugangsbuchungen``: die Umbuchung eines
    beitragsfrei uebernommenen Vertrags traegt das Zugangsjahr, ihr Vorgang
    steht in der Historie; Pruefrunde I, I10) —, Reduktionstabelle ``reduktion_jahr``
    (die Art sagt das Verfahren), Scheiben ``erhoehung_jahr``. Nur die
    Kapitalversicherung kennt diese Vorgaenge; die Form der Zeilen pruefen
    die Vertraege in ``models.bestand``.
    """
    import pandas as pd

    from rechner_pipeline.bestand.fuehrung import months_between
    from rechner_pipeline.kern.beitragsreduktion import (
        BeitragsreduktionFehler,
        pruefe_vorgangsjahr,
    )
    from rechner_pipeline.models.bestand import reduktion_ereignis, zugangsbuchungen

    vertraege: Dict[int, Tuple[_Dauern, Any]] = {}
    for pid, produkt, n, t, beginn in zip(
            portfolio["police_id"], portfolio["produkt"], portfolio["duration"],
            portfolio["premium_duration"], portfolio["insurance_start"]):
        if str(produkt) == "klv":
            vertraege[int(pid)] = (_Dauern(n, t), pd.Timestamp(beginn).date())

    zeilen: List[Tuple[str, int, str, int]] = []   # (weg, police, art, jahr)
    if historie is not None:
        for pid, code, datum in zip(historie["police_id"], historie["status_code"],
                                    historie["status_date"]):
            pid = int(pid)
            if str(code) in VORGANGSJAHR_WEGE and pid in vertraege:
                jahr = months_between(vertraege[pid][1], pd.Timestamp(datum).date()) // 12
                zeilen.append(("historie", pid, str(code), jahr))
    if ledger is not None:
        # Geprueft wird das Jahr des VORGANGS, nie das einer Buchung, die einen
        # bestehenden Zustand in die Fuehrung uebernimmt (Pruefrunde I, I10):
        # Die Umbuchung eines beitragsfrei uebernommenen Vertrags steht am
        # Zugangstag und traegt das Vertragsjahr des Zugangs; das Jahr der
        # Freistellung steht in der Historie und wird dort geprueft.
        bekannt = ledger[[int(p) in vertraege for p in ledger["police_id"]]]
        vorgang = ~zugangsbuchungen(bekannt, portfolio) if len(bekannt) else []
        for pid, ereignis, jahr, ist_vorgang in zip(
                bekannt["police_id"], bekannt["ereignis"], bekannt["vertragsjahr"], vorgang):
            if str(ereignis) in VORGANGSJAHR_WEGE and ist_vorgang:
                zeilen.append(("ledger", int(pid), str(ereignis), int(jahr)))
    if reduktionen is not None:
        for pid, jahr, verfahren in zip(reduktionen["police_id"],
                                        reduktionen["reduktion_jahr"],
                                        reduktionen["verfahren"]):
            zeilen.append(("reduktionen", int(pid), reduktion_ereignis(str(verfahren)),
                           int(jahr)))
    if scheiben is not None:
        for pid, jahr in zip(scheiben["police_id"], scheiben["erhoehung_jahr"]):
            zeilen.append(("scheiben", int(pid), ERH, int(jahr)))

    fehler: List[str] = []
    for weg, pid, art, jahr in zeilen:
        if pid not in vertraege or weg not in VORGANGSJAHR_WEGE[art]:
            continue
        try:
            pruefe_vorgangsjahr(vertraege[pid][0], jahr, art)
        except BeitragsreduktionFehler as exc:
            fehler.append(f"vorgangsjahr {weg}: police {pid}: {art} — {exc}")
    return fehler



def bestandszeilen(pfad) -> int:
    """Die Zeilenzahl einer Bestandstabelle — die eine Tuer des Tools.

    Das KI-Tool spricht das Zielsystem nur ueber die gemessene
    Schnittstelle an (ADR-017, ``TOOL_NACH_VORZEIGE_ERLAUBT``), und fuer
    ``gates.abnahmebericht`` ist diese Tuer dieses Modul. Der
    A-M4-Consumer braucht die Zeilenzahl, um einen BEHAUPTETEN Zaehler an
    die gebundene Tabelle zu halten (Befund T26-04) — er liest sie
    deshalb hier statt selbst ueber ``parquet_io``.

    Wirft weiter, was das Lesen wirft: Eine Datei, die keine
    Bestandstabelle ist, ist ein Befund und kein stiller Null-Wert.
    """
    from pathlib import Path

    from rechner_pipeline.bestand.parquet_io import read_portfolio

    return int(len(read_portfolio(Path(pfad))))


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


def fortschreibung_pruefen(
    verzeichnis: Path, config: Path,
) -> Tuple[Optional[_dt.date], List[str]]:
    """P-B1 auf einem Fortschreibungslauf, wie gates.bestand_validate ihn
    faehrt: Rollen aus dem Verzeichnis, Horizont aus dem Laufmanifest,
    jede Datei und die Config an das Manifest gebunden. Rueckgabe
    (Horizont, Fehler).

    Fuer den A-M4-Konsumenten der Fuehrungsprobe (Angriffsrunde nach T27):
    Die Probe rechnete die Buchungen der Fortschreibung auf eigenen Wegen
    nach und liess dabei Nachbarfaelle offen, die P-B1 laengst prueft
    (RED-Zeilen ausserhalb des Reduktionsjahres, die Hoehe dynamischer
    Erhoehungen). Und welche Fortschreibung sie pruefte, waehlte der Beleg
    selbst — auch eine, die am Tag nach dem Stichtag endete.
    """
    verzeichnis = Path(verzeichnis)
    try:
        manifest = manifest_aus_bytes(lies_manifest_bytes(verzeichnis / MANIFEST_DATEI))
        horizont = _dt.date.fromisoformat(str(manifest["horizont"]))
    except (ManifestError, OSError, KeyError, ValueError) as exc:
        return None, [f"{verzeichnis}: kein lesbares Laufmanifest mit Horizont ({exc}) — "
                      "die Fortschreibung ist kein belegter Lauf"]
    eingaben: Dict[str, Path] = {
        rolle: verzeichnis / datei for rolle, datei in ROLLEN_DATEIEN.items()
        if (verzeichnis / datei).is_file()}
    eingaben["config"] = Path(config)
    _t, _g, fehler, usage = lies_und_pruefe_pb1(eingaben, bis=horizont, manifest=manifest)
    return horizont, [str(e.get("message")) for e in usage + fehler]


def manifest_fuer_nachrechnung(
    portfolio: Path, erwarteter_sha256: Optional[str],
) -> Tuple[Optional[Mapping[str, Any]], List[str]]:
    """Das Laufmanifest eines P-B1-Belegs fuer die A-M4-Nachrechnung.

    Das Manifest ist im Beleg keine Eingangsrolle, sondern nur
    ``summary.manifest`` = {sha256, horizont}. Wer den Beleg nachrechnet,
    braucht die Bytes: Sie liegen, wie der Produzent sie schreibt, NEBEN dem
    Portfolio, und sie muessen den Hash des Belegs tragen — sonst rechnet
    A-M4 mit einem anderen Manifest als P-B1. Rueckgabe (manifest, fehler);
    ``manifest`` ist None, wenn ein Fehler vorliegt.
    """
    pfad = Path(portfolio).parent / MANIFEST_DATEI
    try:
        roh = lies_manifest_bytes(pfad)
    except (ManifestError, OSError) as exc:
        return None, [
            f"P-B1-Beleg nennt ein Manifest, aber {pfad} ist nicht lesbar ({exc}) "
            "— das Laufmanifest gehoert neben das Portfolio"
        ]
    if sha256_bytes(roh) != erwarteter_sha256:
        return None, [
            f"P-B1-Beleg: {pfad.name} neben dem Portfolio traegt einen anderen "
            "SHA-256 als der Beleg — P-B1 auf dem aktuellen Lauf erneut fahren"
        ]
    try:
        return manifest_aus_bytes(roh), []
    except ManifestError as exc:
        return None, [f"P-B1-Manifest nicht auslegbar: {exc}"]


def lies_und_pruefe_pb1(
    eingaben: Mapping[str, Path],
    *,
    bis: Optional[_dt.date] = None,
    manifest: Optional[Mapping[str, Any]] = None,
    ohne_plausibilitaet: bool = False,
) -> Tuple[Dict[str, Any], Dict[str, int], List[dict], List[dict]]:
    """Pruefen UND die geprueften Tabellen zurueckgeben.

    Ein Ledger mit Herabsetzungen ohne Config ist ein Bedienfehler — fuer
    jeden Aufrufer. Die fruehere Ausnahme ``ohne_herleitung`` fuer den
    Bestandsbericht liess ihn verfaelschte Herabsetzungen mit Exit 0
    rendern, die P-B1 auf denselben Bytes abwies (Angriffsrunde nach T27);
    sie ist entfallen.

    ``ohne_plausibilitaet=True`` laesst mit Config die Plausibilitaets-
    baender weg und NUR sie (der Bestandsbericht, Angriffsrunde nach T27):
    Ein Bericht ueber einen Bestand ausserhalb der Baender ist gewollt;
    Buchungen, die keine registrierte Herabsetzung erzeugt, oder ein
    Anteil, den die Config nicht belegt, sind es nicht.

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

    Ein Manifest, dessen Horizont fehlt oder kein ISO-Datum ist, ist ein
    Fehler (``code`` ``manifest``, mit Ausweg) — nie ein Lauf ohne
    Horizont: Der belegte Horizont haelt Herabsetzungen und RED-Buchungen
    (``validate_reduktionen``, ``validate_ledger``), und die Wache darf
    nicht an einem unlesbaren Wert still ausfallen (Nachbesserung der
    Pruefstrecke T27, Runde C). Erst ein FEHLENDES Manifest belegt keinen
    Horizont.

    Rueckgabe: ``(tabellen, geprueft, contract_fehler, usage_fehler)``.
    ``tabellen`` traegt die Rollen, die gelesen werden konnten, und unter
    ``config`` die geparste Config, wenn eine uebergeben wurde.
    """
    erlaubt = PB1_ROLLEN
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

    # Der Horizont, gegen den Buchungen und Herabsetzungen gehalten werden,
    # ist der im Laufmanifest BELEGTE — nicht ``bis``: Der Bestandsbericht
    # und der Abschluss rufen mit einem Bewertungsdatum, das vor dem Ende
    # des Laufs liegen darf; ein Lauf ohne Manifest belegt keinen Horizont
    # (Pruefrunde T27, Runde C, RC02).
    #
    # Fail-fast (Nachbesserung der Pruefstrecke): Ein Manifest, das einen
    # Horizont nicht lesbar belegt, ist ein Fehler, kein Lauf ohne Horizont.
    # Die Funktion nimmt jede ``Mapping``-Form an — ``manifest_aus_bytes``
    # prueft den Horizont zwar schon, aber wer ein Mapping selbst baut oder
    # aendert, laeuft daran vorbei; ein stilles ``horizont = None`` schaltete
    # dann die Horizontwache an Herabsetzung und RED-Buchung aus, bei gruener
    # Meldung. Mit ``bis`` fiel der Aufruf vorher als rohe KeyError/ValueError
    # aus der Funktion statt als Befund.
    horizont: Optional[_dt.date] = None
    if manifest is not None:
        try:
            horizont = manifest_horizont(manifest)
        except (KeyError, ValueError, TypeError) as exc:
            errors.append({
                "code": "manifest",
                "message": (
                    f"Laufmanifest ohne lesbaren Horizont ({type(exc).__name__}: {exc}) — "
                    "ohne den belegten Horizont waeren Herabsetzungen und "
                    "RED-Buchungen hinter dem Laufende ungeprueft. Ausweg: den "
                    "Lauf neu fortschreiben (bestand.cli_fortschreibung schreibt "
                    "das Manifest); nicht von Hand ergaenzen"
                ),
            })
    if horizont is not None and bis is not None and horizont != bis:
        errors.append({
            "code": "manifest",
            "message": (
                f"--bis {bis.isoformat()} widerspricht dem Laufmanifest: "
                f"der Lauf wurde bis {horizont.isoformat()} simuliert. "
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
        "schichten": SCHICHTEN_NAMES,
        "verankerung": VERANKERUNG_NAMES,
        "reduktionen": REDUKTIONEN_NAMES,
    }
    # Die Schleife lief ueber eine ZWEITE, handgepflegte Rollenliste neben
    # diesem Vertrag. Eine neue Erzeugerrolle fiel damit still hindurch:
    # nicht gelesen, nicht geprueft — und die Engine meldete trotzdem
    # Erfolg (gefunden beim Einbau der Herabsetzung, Review T25-06).
    # Jetzt laeuft sie ueber die Tabelle des Erzeugers, und eine Rolle ohne
    # Spaltenvertrag ist ein harter Fehler statt einer Luecke.
    ohne_vertrag = sorted(set(ROLLEN_DATEIEN) - set(spaltenvertrag))
    if ohne_vertrag:
        raise ValueError(
            f"Rollen ohne Spaltenvertrag: {ohne_vertrag} — die Engine kann "
            "sie nicht lesen; wer dem Erzeuger eine Rolle gibt, gibt ihr "
            "hier ihren Vertrag"
        )
    for rolle in ROLLEN_DATEIEN:
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

    schichten = tabellen.get("schichten")
    verankerung = tabellen.get("verankerung")
    if portfolio is not None and verankerung is not None:
        geprueft["verankerung_zeilen"] = int(len(verankerung))
        try:
            for meldung in validate_verankerung(portfolio, verankerung):
                errors.append({"code": "verankerung", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "verankerung", "message": str(exc)})
    if portfolio is not None and schichten is not None:
        # Korrekturschicht (Freischaltung, Schritt 5): Form, Zugehoerigkeit
        # zum Stamm und zum Verankerungszeitpunkt.
        geprueft["schichten_zeilen"] = int(len(schichten))
        try:
            for meldung in validate_schichten(portfolio, schichten, verankerung):
                errors.append({"code": "schichten", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "schichten", "message": str(exc)})

    reduktionen = tabellen.get("reduktionen")
    if portfolio is not None and reduktionen is not None:
        # Herabsetzungen (Review T25-06): Form, Zugehoerigkeit zum Stamm,
        # hoechstens eine je Police und die Reihenfolge gegen die Historie.
        geprueft["reduktionen_zeilen"] = int(len(reduktionen))
        try:
            for meldung in validate_reduktionen(
                portfolio, reduktionen, historie, horizont=horizont
            ):
                errors.append({"code": "reduktionen", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "reduktionen", "message": str(exc)})

    if portfolio is not None and ledger is not None:
        # Semantik der Buchungen (T18-06) und zeilenweise Bindung an die
        # Scheiben (T18-01) — vor der Bewegungs-Identitaet, die nur
        # Jahressummen sieht.
        geprueft["ledger_zeilen"] = int(len(ledger))
        try:
            for meldung in validate_ledger(
                portfolio, ledger, historie=historie, scheiben=scheiben,
                horizont=horizont,
            ):
                errors.append({"code": "ledger", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})

    if portfolio is not None and not any(e["code"] == "portfolio" for e in errors):
        # Die Jahresgrenzen der Vorgaenge auf jedem Tabellenweg, delegiert an
        # den Kern (Pruefrunde H, H02/H04) — ohne Config pruefbar, weil sie
        # nur die Dauern des Stamms braucht.
        try:
            for meldung in vorgangsjahr_fehler(
                    portfolio, historie=historie, ledger=ledger,
                    reduktionen=reduktionen, scheiben=scheiben):
                errors.append({"code": "vorgangsjahr", "message": meldung})
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "vorgangsjahr", "message": str(exc)})

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
    if ledger is not None and reduktionen is None:
        # Dieselbe Wache fuer die Herabsetzung (Angriffsrunde 4 der
        # Pruefrunde T27): Ohne die Tabelle rechnet P-B1 jeden
        # herabgesetzten Vertrag ungekuerzt nach und meldet das richtige
        # Ledger als falsch — ein Bedienfehler, kein Befund (A27-02).
        try:
            hat_herabsetzungen = bool(ledger["ereignis"].isin(REDUKTION_EREIGNISSE).any())
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})
            hat_herabsetzungen = False
        if hat_herabsetzungen:
            usage_errors.append({
                "code": "missing_arg",
                "message": "Ledger enthaelt Herabsetzungen oder Teilkuendigungen (RED/TKU) — "
                "--reduktionen ist erforderlich, sonst rechnet die Wache "
                "jeden herabgesetzten Vertrag ungekuerzt nach",
            })
    if "config" not in eingaben:
        # Ohne Config werden die Betraege nicht hergeleitet — ein Ledger mit
        # Herabsetzungen ist dann nicht pruefbar, und PASSED waere eine
        # Behauptung (Angriffsrunde der Nacht: Auszahlung x10, Auszahlung
        # weg, Summe halbiert — alles PASSED). Wie ERH ohne --scheiben: ein
        # Bedienfehler.
        #
        # Registriert ist ein Vorgang im Ledger ODER in der Reduktionstabelle
        # (Pruefrunde G, Fund G05): Die Wache sah nur den Ledger, und ein Lauf,
        # dessen Tabelle 270 Vorgaenge registriert, deren Buchungen im Ledger
        # alle fehlen, ging ohne Config gruen durch P-B1 und den Bericht -
        # dieselben Bytes, die beide mit Config verweigern. Die
        # Vollstaendigkeit (jeder registrierte Vorgang hat seine Buchungen)
        # prueft nur die Herleitung, und die braucht die Config.
        #
        # Und auch OHNE Ledger (Pruefrunde H, H03/H05): Die Wache stand unter
        # "ledger is not None"; eine Reduktionstabelle allein ging ohne Config
        # gruen durch P-B1, obwohl Verfahren und Anteil jeder Zeile eine
        # Aussage ueber Tarifwerk und Annahmen sind, die nur die Config prueft.
        red_ohne_config = False
        if ledger is not None:
            try:
                red_ohne_config = bool(ledger["ereignis"].isin(REDUKTION_EREIGNISSE).any())
            except Exception as exc:  # noqa: BLE001 - malformed data blockiert
                errors.append({"code": "ledger", "message": str(exc)})
        registriert = reduktionen is not None and len(reduktionen) > 0
        if red_ohne_config or registriert:
            traeger = []
            if red_ohne_config:
                traeger.append("Ledger (RED/TKU)")
            if registriert:
                traeger.append(f"Reduktionstabelle ({len(reduktionen)} Zeilen)")
            usage_errors.append({
                "code": "missing_arg",
                "message": f"{' und '.join(traeger)} enthaelt Herabsetzungen oder "
                "Teilkuendigungen (RED/TKU) - --config ist erforderlich, sonst wird "
                "keine ihrer Buchungen hergeleitet und nicht geprueft, ob jeder "
                "registrierte Vorgang gebucht ist",
            })
    if ledger is not None and schichten is None:
        # Dieselbe Wache fuer die Korrekturschicht (Angriffsrunde
        # 2026-09-26): Ein Ledger, der eine absorbierte Schicht bucht, ist
        # ohne Schicht-Tabelle nicht herleitbar — das ist ein Bedienfehler,
        # kein Befund gegen den Lauf (vorher: Exit 20, "falsch gebucht").
        try:
            hat_schicht = bool((ledger["betrag_art"] == "dDK_absorption").any())
        except Exception as exc:  # noqa: BLE001 — malformed data blockiert
            errors.append({"code": "ledger", "message": str(exc)})
            hat_schicht = False
        if hat_schicht:
            usage_errors.append({
                "code": "missing_arg",
                "message": "Ledger enthaelt absorbierte Korrekturschichten "
                "(dDK_absorption) — --schichten und --verankerung sind "
                "erforderlich, sonst rechnet die Wache ohne Schicht nach",
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
                if not ohne_plausibilitaet:
                    for meldung in sanity_check(portfolio, config.plausibilitaet):
                        errors.append({"code": "sanity", "message": meldung})
                    geprueft["sanity_baender"] = len(config.plausibilitaet)
            except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                errors.append({"code": "sanity", "message": str(exc)})
            # Das gamma1 jeder Scheibe gegen das Tarifwerk ihrer Generation
            # (Freischaltung, Schritt 4): Form ohne Config oben, Wert mit
            # Config hier.
            if (
                scheiben is not None
                and not any(e["code"] in ("scheiben", "portfolio", "config") for e in errors)
            ):
                try:
                    for meldung in pruefe_scheiben_tarifwerk(
                        portfolio, scheiben, config,
                        merkmale=tabellen.get("merkmale"),
                    ):
                        errors.append({"code": "scheiben", "message": meldung})
                except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                    errors.append({"code": "scheiben", "message": str(exc)})
            # Betragsidentitaet je Buchung (T20-04): erst mit den
            # Rechnungsgrundlagen der Config ist der Kern herleitbar. Nur
            # auf formal gueltigen Zeilen — sonst meldete jede
            # Formverletzung zusaetzlich einen Herleitungsfehler. Auch auf
            # einem LEEREN Ledger (Pruefrunde I, I11): Er traegt nicht mehr
            # Buchungen als ein fehlender; die Herleitung haelt dann die
            # Tabelle gegen Tarifwerk und Annahmen und meldet jeden
            # registrierten Vorgang ohne Buchung.
            hergeleitet = False
            if (
                ledger is not None
                and not any(e["code"] in ("ledger", "portfolio", "config") for e in errors)
            ):
                hergeleitet = True
                try:
                    for meldung in pruefe_ledger_betraege(
                        portfolio, ledger, config, scheiben=scheiben,
                        historie=historie, merkmale=tabellen.get("merkmale"),
                        schichten=schichten, verankerung=verankerung,
                        reduktionen=reduktionen,
                    ):
                        errors.append({"code": "ledger", "message": meldung})
                    # Der Beleg zaehlt, was die Herleitung wirklich
                    # abgedeckt hat — abgeleitet aus der Liste des
                    # Herleiters plus den BU-Vorfaellen, nicht abgetippt.
                    # Ein Literal hier haette RED unterschlagen und ein zu
                    # kleines Testat ausgewiesen.
                    geprueft["betraege_hergeleitet"] = int(
                        ledger["ereignis"].isin(
                            set(HERGELEITET) | {"INV", "REA"}).sum())
                except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                    errors.append({"code": "ledger", "message": str(exc)})
            # Ohne Herleitung (Pruefrunde H, H03/H05; Pruefrunde I, I11): Die
            # Tabelle registrierter Vorgaenge wird trotzdem gegen Tarifwerk und
            # Annahmen gehalten — ueber DIESELBE Funktion wie auf dem
            # Ledger-Weg (dort ruft sie pruefe_ledger_betraege). Die Bindung
            # haengt an der TABELLE, nicht am Ledger: Sie laeuft hier, wann
            # immer die Herleitung nicht lief — ohne Ledger, und auch bei einem
            # Ledger mit Formfehlern. Was dann ungeprueft bleibt, sind die
            # Buchungen selbst (Betraege, Vollstaendigkeit); die Summary nennt
            # ihre Zahl, statt "all_passed" darueber zu stellen.
            if not hergeleitet and reduktionen is not None and len(reduktionen) > 0:
                geprueft["reduktionen_buchungen_ungeprueft"] = int(len(reduktionen))
                if not any(e["code"] in ("reduktionen", "portfolio", "config")
                           for e in errors):
                    try:
                        for meldung in pruefe_reduktionen_tarifwerk(
                                portfolio, reduktionen, config):
                            errors.append({"code": "reduktionen", "message": meldung})
                    except Exception as exc:  # noqa: BLE001 — malformed data blockiert
                        errors.append({"code": "reduktionen", "message": str(exc)})
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
        # Die Rollentabelle DES ERZEUGERS, nicht die des Normalfalls: Im
        # Migrationszugang traegt die Portfolio-Rolle bestand.parquet.
        # Mit der festen Tabelle suchte die Engine dort nach einer
        # bestand_gesamt.parquet und meldete "stammt nicht aus diesem
        # Lauf" fuer eine Datei, die sehr wohl daraus stammt.
        datei = rollen_dateien(str(manifest.get("erzeuger")))[rolle]
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
