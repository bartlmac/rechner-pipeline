"""Transformations-Spec: Quell-Datenmodell -> Ziel-Ontologie (Plan P5).

Die grosse Migrationsaufgabe VOR der Migration: ein gelieferter
Bestandsabzug spricht das Datenmodell des abgebenden Unternehmens
(Feldnamen, Kodierungen, Formate). Die Uebersetzung in unsere
Ontologie ist selbst ein Migrationsartefakt mit Provenienz:

* Der AGENT (Skill ``transformiere-quellbestand``) schlaegt das Mapping
  vor — das ist die semantische Leistung (er erkennt, dass "ERLSUMME"
  unsere Versicherungssumme ist). Er ERFINDET nichts: jedes Mapping
  traegt eine Begruendung, Unklarheit wird ein offener Konflikt.
* DETERMINISTISCH sind Pruefung und Anwendung (dieses Modul): jedes
  Ziel-Pflichtfeld gedeckt, jede Quellspalte gemappt oder mit Grund
  ausgelassen, Kodierungen vollstaendig, Berechnungen nur aus dem
  benannten Katalog. Ein Wert, den das Mapping nicht abbildet, ist ein
  Befund je Zeile — nie ein stiller Default (P2).
* Offene Konflikte (z. B. eine undokumentierte Spalte) blockieren die
  Anwendung, bis ein MENSCH sie entschieden hat — die Entscheidung
  wird Teil der Spec (append-only im Fall-Artefakt).

Knoten: klv
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import io
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

#: Ziel-Pflichtfelder eines transformierten Bestandsabzugs — die
#: Vertragsseite des Kern-Contracts plus Abgleichswerte. Bewusst NICHT
#: die Generation-Felder (Zins, Kosten): die kommen aus der Spez des
#: Migrationsfalls, nie aus dem Abzug.
#:
#: ``sex`` ist PFLICHT, weil der Kern es zwingend fuehrt: es steht in
#: ``models/bestand.CONTRACT_FIELDS``, ``model_point_kwargs`` liest
#: ``row["sex"]`` ohne Default, und der ModelPoint hat kein Default-
#: Geschlecht. Ein transformierter Vertrag ohne Geschlecht ist also nicht
#: rechenbar — als optionales Feld wuerde die Luecke erst im Kern
#: auffallen (KeyError), nicht in der Spec-Pruefung. Dass eine
#: Tarifgeneration unisex rechnet, aendert daran nichts: Unisex macht das
#: Geschlecht tarif-wirkungslos, nicht entbehrlich — der Bestand fuehrt es
#: weiter fuer Nachweisung, Folgebewertung und spaetere geschlechts-
#: abhaengige Generationen. Fehlt der Lieferung eine Geschlechtsspalte,
#: ist das ein Befund fuer den Menschen (A-Q1), keine stille Auslassung.
ZIEL_PFLICHT: Tuple[str, ...] = (
    "police_id", "beginn", "entry_age", "sex", "duration",
    "premium_duration", "sum_insured", "zahlweise", "status", "tarifart",
)
#: Zulaessige Zielwerte des Geschlechts. Spiegel von
#: ``models/bestand.SEX_VALUES``: die Schichtenkarte laesst die Ontologie
#: nicht auf ``models`` zugreifen, deshalb hier als eigene Konstante — die
#: Gleichheit mit der SSOT ist test-gebunden
#: (tests/test_transformation_und_abgleich.py). Notwendig, weil der Kern
#: jedes Nicht-"M" still zur Frauentafel aufloest
#: (``kern/tafeln._tafel_key``): ein durchgereichtes "W" waere kein
#: Fehler, sondern ein stiller Default (P2).
SEX_ZIELWERTE: Tuple[str, ...] = ("M", "F")

#: Optionale Zielfelder (Abgleichswerte und Herkunfts-Extras).
ZIEL_OPTIONAL: Tuple[str, ...] = (
    "vertragsjahre_am_stichtag", "brutto_jahresbeitrag",
    "brutto_zahlbeitrag", "deckungskapital", "geburtsdatum",
)


def _parse_datum(wert: str) -> _dt.date:
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(wert.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError(f"kein bekanntes Datumsformat: {wert!r}")


def _alter_aus_daten(zeile: Dict[str, Any], quellen: List[str]) -> int:
    geb, beginn = _parse_datum(zeile[quellen[0]]), _parse_datum(zeile[quellen[1]])
    alter = beginn.year - geb.year - (
        1 if (beginn.month, beginn.day) < (geb.month, geb.day) else 0)
    if not 0 <= alter <= 123:
        raise ValueError(f"berechnetes Alter {alter} unplausibel")
    return alter


def _alter_kalenderjahr(zeile: Dict[str, Any], quellen: List[str]) -> int:
    """Kalenderjahresmethode: Alter = Beginnjahr - Geburtsjahr.

    Verbreitete Konvention von Quell-Bestandsfuehrungen: das
    versicherungstechnische Eintrittsalter ist die Differenz der
    Kalenderjahre, unabhaengig davon, ob der Geburtstag im Beginnjahr
    schon erreicht war. Welche Regel eine Lieferung verwendet, ist eine
    Eigenschaft der Quelle und wird im Migrationsfall BELEGT entschieden
    (Abzugsabgleich), nie geraten.
    """
    geb, beginn = _parse_datum(zeile[quellen[0]]), _parse_datum(zeile[quellen[1]])
    alter = beginn.year - geb.year
    if not 0 <= alter <= 123:
        raise ValueError(f"berechnetes Alter {alter} unplausibel")
    return alter


def _jahre_aus_daten(zeile: Dict[str, Any], quellen: List[str]) -> int:
    von, bis = _parse_datum(zeile[quellen[0]]), _parse_datum(zeile[quellen[1]])
    jahre = bis.year - von.year - (
        1 if (bis.month, bis.day) < (von.month, von.day) else 0)
    if jahre <= 0:
        raise ValueError(f"berechnete Dauer {jahre} <= 0")
    return jahre


def _datum_iso(zeile: Dict[str, Any], quellen: List[str]) -> str:
    return _parse_datum(zeile[quellen[0]]).isoformat()


def _zahl(zeile: Dict[str, Any], quellen: List[str]) -> float:
    roh = str(zeile[quellen[0]]).strip().replace(".", "").replace(",", ".") \
        if "," in str(zeile[quellen[0]]) else str(zeile[quellen[0]]).strip()
    return float(roh)


def _ganzzahl(zeile: Dict[str, Any], quellen: List[str]) -> int:
    return int(str(zeile[quellen[0]]).strip())


#: Katalog der zulaessigen Berechnungen — der Agent WAEHLT, Code RECHNET.
#: Ein Mapping mit unbekannter Berechnung faellt in der Validierung.
BERECHNUNGEN: Dict[str, Callable[[Dict[str, Any], List[str]], Any]] = {
    "alter_aus_geburtsdatum_und_beginn": _alter_aus_daten,
    "alter_kalenderjahresmethode": _alter_kalenderjahr,
    "jahre_aus_datumsdifferenz": _jahre_aus_daten,
    "datum_nach_iso": _datum_iso,
    "zahl": _zahl,
    "ganzzahl": _ganzzahl,
}

#: Jede Katalogfunktion hat einen expliziten Operandenvertrag. Ein blosses
#: ``>= 1`` genuegt nicht: eine dritte Datumsspalte wuerde sonst deklariert,
#: von der Implementierung aber still ignoriert; null Operanden fuehrten erst
#: waehrend der Anwendung zu einem ``IndexError``.
BERECHNUNGS_ARITAETEN: Dict[str, int] = {
    "alter_aus_geburtsdatum_und_beginn": 2,
    "alter_kalenderjahresmethode": 2,
    "jahre_aus_datumsdifferenz": 2,
    "datum_nach_iso": 1,
    "zahl": 1,
    "ganzzahl": 1,
}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FeldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Zielfeld — leer NUR bei nicht_uebernommen (dort gibt es keins).
    ziel: str = ""
    typ: Literal["direkt", "kodierung", "berechnung", "nicht_uebernommen"]
    #: Quellspalten (1 bei direkt/kodierung; >=1 bei berechnung; bei
    #: nicht_uebernommen genau die ausgelassene Spalte, ziel = "").
    quellen: List[str] = Field(min_length=0)
    kodierung: Dict[str, Any] = Field(default_factory=dict)
    berechnung: str = ""
    begruendung: str = Field(min_length=1)


class OffenerKonflikt(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quellspalte: str
    frage: str = Field(min_length=1)
    #: Menschliche Entscheidung (None = offen, blockiert die Anwendung).
    entscheidung: Optional[str] = None
    entscheider: str = ""


class TransformationsSpec(BaseModel):
    """Das Mapping als Fall-Artefakt — agentenerzeugt, code-geprueft."""

    model_config = ConfigDict(extra="forbid")

    quelle_datei: str = Field(min_length=1)
    quelle_sha256: str = Field(min_length=64, max_length=64)
    akteur: str = Field(min_length=1)          # <modell>/<skill>@<git-sha>
    erhoben_am: str = Field(min_length=1)
    felder: List[FeldMapping] = Field(min_length=1)
    offene_konflikte: List[OffenerKonflikt] = Field(default_factory=list)
    anmerkungen: List[str] = Field(default_factory=list)


def validate_spec(
    spec: TransformationsSpec, quellspalten: List[str]
) -> List[str]:
    """Beidseitige Abdeckung und Katalogtreue (leer = anwendbar)."""
    fehler: List[str] = []
    if not _SHA256_RE.fullmatch(spec.quelle_sha256):
        fehler.append(
            "quelle_sha256 muss ein vollstaendiger kleingeschriebener "
            "SHA-256-Hexwert sein"
        )
    ziele = [f.ziel for f in spec.felder if f.typ != "nicht_uebernommen"]
    for pflicht in ZIEL_PFLICHT:
        if pflicht not in ziele:
            fehler.append(
                f"Zielfeld {pflicht!r} ist nicht gedeckt — jedes "
                "Pflichtfeld braucht ein Mapping"
            )
    for ziel in ziele:
        if ziel not in ZIEL_PFLICHT + ZIEL_OPTIONAL:
            fehler.append(
                f"unbekanntes Zielfeld {ziel!r} — die Ziel-Ontologie "
                "kennt es nicht (Erweiterung waere Gate A-K1)"
            )
        if ziele.count(ziel) > 1:
            fehler.append(f"Zielfeld {ziel!r} ist mehrfach gemappt")
    benutzte = {q for f in spec.felder for q in f.quellen}
    konflikt_spalten = {k.quellspalte for k in spec.offene_konflikte}
    for spalte in quellspalten:
        if spalte not in benutzte and spalte not in konflikt_spalten:
            fehler.append(
                f"Quellspalte {spalte!r} ist weder gemappt noch als "
                "nicht_uebernommen begruendet noch als Konflikt offen — "
                "keine stillen Auslassungen (P2)"
            )
    for f in spec.felder:
        if f.typ != "nicht_uebernommen" and not f.ziel:
            fehler.append(
                f"Mapping ohne Zielfeld (typ={f.typ}, quellen={f.quellen})"
            )
        if f.typ == "nicht_uebernommen" and f.ziel:
            fehler.append(
                f"nicht_uebernommen traegt ein Zielfeld {f.ziel!r} — "
                "entweder mappen oder auslassen, nicht beides"
            )
        if f.typ == "berechnung" and f.berechnung not in BERECHNUNGEN:
            fehler.append(
                f"{f.ziel}: unbekannte Berechnung {f.berechnung!r} "
                f"(Katalog: {', '.join(sorted(BERECHNUNGEN))})"
            )
        if f.typ == "berechnung" and f.berechnung in BERECHNUNGS_ARITAETEN:
            erwartet = BERECHNUNGS_ARITAETEN[f.berechnung]
            if len(f.quellen) != erwartet:
                fehler.append(
                    f"{f.ziel}: Berechnung {f.berechnung!r} braucht genau "
                    f"{erwartet} Quellspalte{'n' if erwartet != 1 else ''}"
                )
        if f.typ in ("direkt", "kodierung") and len(f.quellen) != 1:
            fehler.append(f"{f.ziel}: {f.typ} braucht genau EINE Quellspalte")
        if f.typ == "kodierung" and not f.kodierung:
            fehler.append(f"{f.ziel}: kodierung ohne Wertetabelle")
        if f.ziel == "sex" and f.typ == "kodierung":
            fremd = sorted({str(w) for w in f.kodierung.values()
                            if str(w) not in SEX_ZIELWERTE})
            if fremd:
                fehler.append(
                    f"sex: Kodierung bildet auf {fremd} ab — zulaessig sind "
                    f"nur {list(SEX_ZIELWERTE)}; der Kern loest jeden "
                    "anderen Wert still zur Frauentafel auf"
                )
        for q in f.quellen:
            if q not in quellspalten:
                fehler.append(
                    f"{f.ziel}: Quellspalte {q!r} existiert nicht in der "
                    "Lieferung"
                )
    for k in spec.offene_konflikte:
        if k.entscheidung is None:
            fehler.append(
                f"offener Konflikt zu Spalte {k.quellspalte!r}: {k.frage} "
                "— MENSCHLICHE Entscheidung noetig, Anwendung blockiert"
            )
        elif not k.entscheidung.strip():
            fehler.append(
                f"Konflikt zu Spalte {k.quellspalte!r} traegt eine leere "
                "Entscheidung — Anwendung blockiert"
            )
        elif not k.entscheider.strip():
            fehler.append(
                f"Konflikt zu Spalte {k.quellspalte!r} ist ohne nichtleeren "
                "menschlichen Entscheider markiert — Anwendung blockiert"
            )
    return fehler


def lese_transformationsquelle(
    quelle_pfad: Path,
    *,
    trenner: str = ";",
) -> Tuple[str, List[str], List[Dict[str, Any]]]:
    """SHA-256, physischen Header und Zeilen derselben CSV-Bytes lesen.

    Produzent und Abnahme verwenden bewusst denselben Parser. Andernfalls
    koennte etwa ein duplizierter Header in der Anwendung anders aufgeloest
    werden als in der nachgelagerten Beweispruefung.
    """
    quelle_pfad = Path(quelle_pfad)
    roh = quelle_pfad.read_bytes()
    try:
        text = roh.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Transformationsquelle {quelle_pfad} ist kein UTF-8-CSV: {exc}"
        ) from exc
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=trenner)
    quellspalten = list(reader.fieldnames or [])
    if not quellspalten:
        raise ValueError(
            f"Transformationsquelle {quelle_pfad} hat keinen CSV-Header"
        )
    if len(quellspalten) != len(set(quellspalten)):
        doppelt = sorted({s for s in quellspalten if quellspalten.count(s) > 1})
        raise ValueError(
            f"Transformationsquelle {quelle_pfad} hat doppelte Spalten "
            f"{doppelt}"
        )
    zeilen: List[Dict[str, Any]] = []
    for zeile in reader:
        # DictReader fuellt zu kurze Zeilen mit ``restval`` auf und sammelt
        # ueberzaehlige Felder unter ``restkey``. Beides waere ein stiller
        # Default (P2): ein fehlendes Feld erschiene als leerer Zielwert,
        # ein ueberzaehliges verschwaende spurlos.
        ueberzaehlig = zeile.pop(reader.restkey, []) if reader.restkey in zeile else []
        fehlend = [name for name, wert in zeile.items() if wert is reader.restval]
        if ueberzaehlig or fehlend:
            gefunden = len(quellspalten) + len(ueberzaehlig) - len(fehlend)
            raise ValueError(
                f"Transformationsquelle {quelle_pfad} Zeile {reader.line_num}: "
                f"{gefunden} Felder, laut Header erwartet {len(quellspalten)} "
                "— kein stilles Auffuellen und kein stiller Feldverlust"
            )
        zeilen.append(zeile)
    return hashlib.sha256(roh).hexdigest(), quellspalten, zeilen


def _wende_registrierte_datei_an(
    spec: TransformationsSpec,
    quelle_pfad: Path,
    *,
    trenner: str = ";",
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Das Mapping auf einer bereits sicher aufgeloesten Quelle anwenden.

    Diese schichtinterne Funktion ist bewusst nicht die Produzenten-API. Nur
    ``gates.transformation_anwenden.wende_an`` darf sie nach der Aufloesung
    ueber das Fallregister aufrufen. Sie liest die zu transformierenden Zeilen
    selbst; dadurch kann der Orchestrator weder andere Zeilen noch selbst
    behauptete Quellspalten unter dem Hash der Spec einschleusen. SHA-256 und
    physischer CSV-Header werden vor der ersten Zielzeile geprueft und
    ``validate_spec`` laeuft immer.

    Befunde je Zeile (unbekannter Kodierungswert, unparsbare Daten)
    brechen NICHT den Lauf, sondern werden gesammelt zurueckgegeben —
    der Aufrufer entscheidet, ob er mit Luecken weiterarbeitet. Eine
    Zeile mit Befund wird NICHT ausgegeben (keine halb transformierten
    Vertraege).
    """
    quelle_pfad = Path(quelle_pfad)
    quelle_sha256, quellspalten, zeilen = lese_transformationsquelle(
        quelle_pfad,
        trenner=trenner,
    )
    vorbedingungen: List[str] = []
    if quelle_sha256 != spec.quelle_sha256:
        vorbedingungen.append(
            "quelle_sha256 der Spec passt nicht zu den tatsaechlich "
            f"transformierten Bytes ({quelle_sha256})"
        )
    vorbedingungen.extend(validate_spec(spec, quellspalten))
    if vorbedingungen:
        raise ValueError(
            "TransformationsSpec ist fuer die tatsaechliche Quelle nicht "
            "anwendbar: " + "; ".join(vorbedingungen)
        )

    ergebnis: List[Dict[str, Any]] = []
    befunde: List[str] = []
    for i, zeile in enumerate(zeilen, start=1):
        ziel: Dict[str, Any] = {}
        fehler_in_zeile = False
        for f in spec.felder:
            if f.typ == "nicht_uebernommen":
                continue
            try:
                if f.typ == "direkt":
                    ziel[f.ziel] = zeile[f.quellen[0]]
                elif f.typ == "kodierung":
                    roh = str(zeile[f.quellen[0]]).strip()
                    if roh not in f.kodierung:
                        raise ValueError(
                            f"Wert {roh!r} fehlt in der Kodierung "
                            f"({sorted(f.kodierung)})"
                        )
                    ziel[f.ziel] = f.kodierung[roh]
                else:
                    ziel[f.ziel] = BERECHNUNGEN[f.berechnung](zeile, f.quellen)
                # Das Geschlecht ist die einzige Zielgroesse, deren falscher
                # Wert im Kern NICHT auffaellt (Nicht-"M" -> Frauentafel).
                # Deshalb hier ein Befund je Zeile statt eines stillen Werts.
                if f.ziel == "sex" and str(ziel[f.ziel]) not in SEX_ZIELWERTE:
                    raise ValueError(
                        f"Geschlecht {ziel[f.ziel]!r} ist keiner der "
                        f"Zielwerte {list(SEX_ZIELWERTE)} — Kodierung der "
                        "Spec ergaenzen, nicht durchreichen"
                    )
            except (KeyError, ValueError) as exc:
                befunde.append(f"Zeile {i}, Feld {f.ziel}: {exc}")
                fehler_in_zeile = True
        if not fehler_in_zeile:
            ergebnis.append(ziel)
    return ergebnis, befunde
