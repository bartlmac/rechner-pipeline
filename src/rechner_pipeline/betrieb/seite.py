"""Bestand heute — die interne Sicht auf den gefuehrten Stand und das Stands-Paket.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8.3. Zwei Wege,
die sich nicht ausschliessen:

* **Interne Sicht, taeglich.** Nach jedem gruenen Lauf rendert der
  Tageslauf nach ``daten/seite/index.html`` einen Abschnitt "Bestand
  heute": Kennzahlen des gefuehrten Tags, Neugeschaeft der Woche, die
  letzten Buchungen, die Monatsabschluesse — aus dem Protokoll und dem
  Tagesjournal, ohne eine einzige neue Rechnung. Ein Caddy auf dem
  Betriebsrechner liefert das Verzeichnis read-only aus.
* **Oeffentliche Sicht, gestempelt.** ``stands_paket`` exportiert den
  Stand als Paket (``stand.json`` mit Datum, Manifest-Hash, Kennzahlen,
  Abschluessen und Provenienz, dazu die Berichte des juengsten
  Abschlusses). Die Vorzeigeseite liest ihre Kennzahlen daraus
  (``werkzeuge/falldaten.py --stands-paket``) statt aus einem Fall —
  dieselbe Drift-Regel: erzeugt, nie abgetippt. Veroeffentlicht wird
  weiterhin vom Menschen; automatisch veroeffentlicht wird nichts, was
  nicht durch P-B1 ging — und ins Paket kommt nur ein uebernommener
  (gruener) Stand.

Deterministisch: dieselben Daten ergeben dieselbe Seite und dasselbe
Paket; es gibt keinen Zeitstempel ausser dem gefuehrten Tag selbst.

Run via::

    python -m rechner_pipeline.betrieb.seite --stand <daten> [--paket <ziel>]

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import html as _html
import io
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.models.anker import (
    ART_AUSLIEFERUNG,
    ART_MOMENTAUFNAHME,
    ankersatz,
    haenge_an,
    satz_hash,
    zeichne,
)
from rechner_pipeline.betrieb._loeschen import LoeschFehler, entferne_verzeichnis
from rechner_pipeline.bestand.kennzahlen import bewegungskennzahlen
from rechner_pipeline.bestand.manifest import (
    lies_manifest,
    manifest_aus_bytes,
    sha256_bytes,
)
from rechner_pipeline.bestand.parquet_io import neue_datei, read_portfolio
from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

#: Schema 3 (Review T24-04, Teil 1): das Paket traegt Protokoll, Manifest
#: UND das Tagesjournal als Belegdateien; der Konsument prueft Kette,
#: Hashes und Urteil selbst und leitet die Zahlen aus den Belegen ab,
#: statt den Feldern von ``stand.json`` zu glauben.
#:
#: Schema 2 (T22-05) trug nur Protokoll und Manifest. Damit waren die
#: protokollgespeisten Bloecke belegt, die journalgespeisten aber nicht:
#: Geschaeftsentwicklung, ``buchungen.*`` und das Neugeschaeft der Woche
#: standen als blosse Behauptung im Paket. Ein Auszug statt des vollen
#: Journals waere eine zweite Serialisierungsregel gewesen — ein Vertrag,
#: den ein Konsument aendert, statt einer, den nur der Produzent aendert
#: (abgestimmt mit vorzeige-url, 2026-09-15).
#: Schema 4 (Review T24-04, Teil 2): ``stand.json`` NENNT seinen Anker.
#: Ein Paket ohne Anker belegt nur sich selbst — die Protokollkette
#: schuetzt ihre letzte Zeile nicht, und genau aus ihr leitet stand.json
#: ab. Der Sprung macht die Kopplung sichtbar: Ein Konsument des alten
#: Schemas bekommt eine klare Meldung statt stiller Drift.
#: Schema 5: Das Paket traegt die juengsten Monatsabschluesse selbst.
#: Bis Schema 4 nannte ``stand.json`` je Abschluss eine Vertragszahl, die
#: der Konsument nicht nachrechnen konnte — der festgeschriebene Abschluss
#: lag nur in der Ablage des Erzeugers. Die Zahl war damit dieselbe Figur
#: wie ``in_force`` vor T24-04: belegt daneben stehend, tatsaechlich zu
#: glauben. Mitgeliefert werden die juengsten
#: :data:`PAKET_ABSCHLUESSE_ANZAHL`, nicht alle: Ein gefuehrter Bestand
#: hat nach Jahren hunderte, und ein Paket soll tragen, was es zeigt.
PAKET_SCHEMA_VERSION = 5
PAKET_PROTOKOLL = "protokoll.jsonl"
PAKET_MANIFEST = "laufmanifest.json"
PAKET_JOURNAL = "tagesjournal.parquet"
#: Verzeichnis der mitgelieferten Abschluesse IM Paket.
PAKET_ABSCHLUESSE_DIR = "abschluesse"
#: Zwoelf — ein Jahr Monatsabschluesse. Die Zahl ist zugleich die Grenze,
#: bis zu der ``in_kraft`` abgeleitet wird, und sie gilt auf BEIDEN
#: Seiten: Der Erzeuger haette alle Abschluesse zur Hand und wuerde sonst
#: mehr Zahlen bilden als der Konsument nachrechnen kann — der Vergleich
#: der beiden Ableitungen schluege fehl, obwohl niemand gelogen hat.
PAKET_ABSCHLUESSE_ANZAHL = 12
SEITE_DIR = "seite"
PAKET_DATEI = "stand.json"

EREIGNIS_TITEL = {
    "ZUG": "Zugang", "MIG": "Migrationszugang", "ERH": "Dynamische Erhöhung",
    "RED": "Beitragsherabsetzung", "PEX": "Beitragsfreistellung",
    "INV": "Invalidisierung", "REA": "Reaktivierung", "STO": "Storno",
    "TOD": "Tod", "ABL": "Ablauf",
}


class SeiteError(ValueError):
    """Kein uebernommener Stand — es gibt nichts zu zeigen."""


# --------------------------------------------------------------------------- #
# Das Datenmodell des Stands (dieselbe Quelle fuer Seite und Paket)
# --------------------------------------------------------------------------- #


def _gepruefte_zeilen(
    ablage, aktuelle_zeile: Optional[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    """Die Protokollzeilen und die letzte gruene — NACH dem Nachweisvertrag.

    Plus die Zeile des laufenden Tages, wenn der Tageslauf sie noch nicht
    angefuegt hat (er rendert vor dem Anfuegen, damit die Zeile die Seite
    nennt); zu diesem Zeitpunkt liegen Stand und Journal bereits so auf der
    Platte, wie die Zeile sie nennt.

    Die Pruefung steht hier, weil sie sonst nur den schuetzt, der sie
    durchlaeuft (Review T24-03, Klasse K1). ``gefuehrter_tag`` lehnte ein
    veraendertes Tagesjournal ab; Seite und Stands-Paket lasen dieselben
    Bytes danach ohne Pruefung erneut und zeigten den manipulierten Betrag.
    Die Provenienz daneben nannte weiter den Journal-Hash der Protokollzeile
    — die Seite widersprach sich selbst und merkte es nicht. Nachgemessen
    mit einem gueltig neu geschriebenen Journal: kein Abbruch, kein Hinweis.

    Es genuegt also nicht, dass irgendwo eine Wache steht. Sie muss dort
    stehen, wo die Bytes gelesen werden.

    Und sie muss DIESELBEN Bytes weiterreichen (Befund T26-10). Vorher
    prueften wir die Hashes und lasen Manifest und Journal danach erneut;
    an der Naht dazwischen passt ein ganzer Tageslauf. Die Gegenprobe des
    Gutachters hat genau dort einen zweiten, regulaeren Lauf gestartet —
    die Seite nannte danach den alten Tag und zeigte die neuen Buchungen.
    """
    from rechner_pipeline.betrieb.tageslauf import (
        TageslaufError, lies_protokoll, pruefe_nachweis,
    )

    zeilen = list(lies_protokoll(ablage.protokoll_pfad))
    if aktuelle_zeile is not None:
        zeilen.append(aktuelle_zeile)
    gruene = [z for z in zeilen if z.get("uebernommen")]
    if not gruene:
        raise SeiteError(
            f"{ablage.protokoll_pfad}: kein uebernommener Lauf — ohne gefuehrten "
            "Stand gibt es keinen Bestand heute"
        )
    try:
        gelesen = pruefe_nachweis(ablage, gruene)
    except TageslaufError as exc:
        raise SeiteError(
            f"Der Stand traegt seinen Nachweis nicht, es gibt nichts zu zeigen: {exc}"
        ) from exc
    return zeilen, gruene[-1], gelesen


def abschluesse_aus_protokoll(
    zeilen: List[Dict[str, Any]],
    journal: Optional[pd.DataFrame] = None,
    abschluesse_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Die Monatsabschluesse eines Stands aus allen gruenen Protokollzeilen.

    Je Stichtag EIN Eintrag: Die Zeile, die ihn geschrieben hat, nennt
    Datei und Hash; spaetere Zeilen nennen ihn wieder (``neu: false``) und
    ergaenzen hoechstens den Bericht.

    Oeffentlich, weil zwei Seiten dieselbe Ableitung brauchen (Review
    T24-04): Der Erzeuger baut daraus ``stand.json``, der Konsument haelt
    ``stand.json`` dagegen. Zweimal geschrieben waeren es zwei Regeln, die
    auseinanderlaufen — genau die Drift, gegen die der Beleg antritt.

    Genau deshalb nimmt sie QUELLEN entgegen und keine Ablage: Der
    Erzeuger reicht Journal und Abschlussverzeichnis seiner Ablage, der
    Konsument dieselben Dateien aus dem Paket. Eine Ablage koennte nur
    der Erzeuger stellen; die Ableitung waere dann seine allein, und der
    Konsument muesste ihr Ergebnis glauben statt es nachzubilden.

    Fehlt eine Quelle, bleiben die zugehoerigen Felder WEG — sie werden
    nicht genullt. "Nicht gerechnet" und "null Vorfaelle" sind
    verschiedene Aussagen, und nur eine davon ist hier wahr.
    """
    abschluesse: Dict[str, Dict[str, Any]] = {}
    for z in zeilen:
        if not z.get("uebernommen"):
            continue
        for a in z.get("abschluesse") or []:
            eintrag = abschluesse.setdefault(a["stichtag"], {"stichtag": a["stichtag"]})
            if a.get("neu"):
                eintrag["datei"] = a["datei"]
                eintrag["sha256"] = a.get("sha256")
            if a.get("bericht"):
                eintrag["bericht"] = a["bericht"]
            if a.get("teilbestaende"):
                eintrag["teilbestaende"] = a["teilbestaende"]
            for feld in KENNZAHL_FELDER:
                if a.get(feld) is not None:
                    eintrag[feld] = a[feld]
    liste = [abschluesse[k] for k in sorted(abschluesse)]
    _ergaenze_kennzahlen(liste, journal, abschluesse_dir)
    return liste


#: Die Zahlen der Monatszeile. Abschluesse aus Laeufen VOR ihrer
#: Einfuehrung tragen sie nicht; sie werden beim Export aus gebundenen
#: Bytes nachgerechnet, nicht behauptet.
KENNZAHL_FELDER = ("in_kraft", "zugaenge", "leistungen")
#: Die beiden Felder, die das Tagesjournal ALLEIN traegt — es reicht ueber
#: die ganze Buchungshistorie, waehrend der festgeschriebene Abschluss nur
#: fuer die juengsten Monate mitgeliefert wird.
BEWEGUNGS_FELDER = ("zugaenge", "leistungen")


def _ergaenze_kennzahlen(
    liste: List[Dict[str, Any]],
    journal: Optional[pd.DataFrame],
    abschluesse_dir: Optional[Path],
) -> None:
    """Fehlende Monatskennzahlen aus den gegebenen Quellen nachrechnen.

    Aeltere Abschluesse entstanden, bevor der Tagesbetrieb die Zahlen
    schrieb. Sie neu zu erzeugen ginge nicht — ein Abschluss ist
    festgeschrieben und wird nie zweimal geschrieben. Sie sind aber
    ABLEITBAR, aus zwei verschieden weit reichenden Quellen:

    * Das Tagesjournal traegt die ganze Buchungshistorie. Daraus kommen
      ``zugaenge`` und ``leistungen`` fuer JEDEN Eintrag der Liste.
    * ``in_kraft`` ist die Zeilenzahl des festgeschriebenen Abschlusses.
      Der liegt beim Konsumenten nur fuer die juengsten
      :data:`PAKET_ABSCHLUESSE_ANZAHL` Monate — mehr traegt das Paket
      nicht.

    Gerechnet wird mit denselben Funktionen, die der Tageslauf ruft
    (``bestand.kennzahlen``); zwei Implementierungen liefen auseinander,
    sobald jemand eine Ereignisart ergaenzt.

    Ein fehlender Abschluss laesst den Eintrag ohne ``in_kraft`` — und
    das bleibt trotzdem vergleichbar: Der Erzeuger legt genau die
    Abschluesse ins Paket, die er selbst hat, also fehlt beiden Seiten
    derselbe. Wer eine Datei nachtraeglich aus dem Paket nimmt, faellt
    eine Stufe frueher auf, weil ``dateien`` sie mit Hash nennt.
    """
    if journal is not None:
        for eintrag in liste:
            if any(f not in eintrag for f in BEWEGUNGS_FELDER):
                eintrag.update(bewegungskennzahlen(
                    journal, _dt.date.fromisoformat(eintrag["stichtag"])))
    if abschluesse_dir is None:
        return
    for eintrag in juengste_abschluesse(liste):
        if "in_kraft" in eintrag:
            continue
        pfad = Path(abschluesse_dir) / eintrag["datei"]
        if pfad.is_file():
            eintrag["in_kraft"] = int(len(read_portfolio(pfad)))


def juengste_abschluesse(liste: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Die Abschluesse, die mit dem Paket reisen — juengste zuletzt.

    EINE Auswahlregel fuer zwei Zwecke: ``stands_paket`` kopiert genau
    diese Dateien, und :func:`_ergaenze_kennzahlen` rechnet genau fuer
    diese Eintraege ``in_kraft`` nach. Zwei getrennte Regeln liefen
    auseinander, und das Ergebnis waere ein Paket, das eine Zahl nennt,
    deren Beleg es nicht mitbringt.
    """
    return [e for e in liste if e.get("datei")][-PAKET_ABSCHLUESSE_ANZAHL:]


def stand_modell(ablage, aktuelle_zeile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Datum, Kennzahlen, Neugeschaeft, Buchungen, Abschluesse, Provenienz — aus
    Protokoll, Journal und Manifest des uebernommenen Stands."""
    return stand_modell_mit_bytes(ablage, aktuelle_zeile)[0]


def stand_modell_mit_bytes(
    ablage, aktuelle_zeile: Optional[Dict[str, Any]] = None
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Wie :func:`stand_modell`, plus die GEPRUEFTEN Bytes von Manifest
    und Journal.

    Der Paket-Export braucht sie (Befund T26-10): Er legt Manifest und
    Journal als Belege ins Paket, und wenn er sie dafuer ein zweites Mal
    von der Platte liest, kann zwischen Pruefung und Kopie ein Tageslauf
    liegen — das Paket truege dann Belege einer anderen Generation als
    die Zahlen daneben."""
    zeilen, zeile, gelesen = _gepruefte_zeilen(ablage, aktuelle_zeile)
    heute = _dt.date.fromisoformat(str(zeile["heute"]))
    # Die GEPRUEFTEN Bytes, nicht ein zweiter Lesevorgang (Befund
    # T26-10): Zwischen Pruefung und Auswertung passt ein ganzer
    # Tageslauf, und die Seite nannte danach den alten Tag mit den neuen
    # Buchungen.
    manifest = (manifest_aus_bytes(gelesen["manifest"])
                if gelesen.get("manifest") is not None
                else lies_manifest(ablage.stand))
    if str(manifest["horizont"]) != heute.isoformat():
        raise SeiteError(
            f"Stand fuehrt {manifest['horizont']}, das Protokoll {heute.isoformat()} "
            "— Stand und Nachweis passen nicht zusammen"
        )
    journal_roh = gelesen.get("journal")
    journal_vorhanden = journal_roh is not None
    journal = (
        read_portfolio(io.BytesIO(journal_roh), expected_columns=TAGESJOURNAL_NAMES)
        if journal_vorhanden
        else pd.DataFrame({n: pd.Series(dtype="object") for n in TAGESJOURNAL_NAMES})
    )
    woche = neugeschaeft_der_woche(journal, heute)
    letzte = journal.tail(20).iloc[::-1]
    buchungen = [
        {
            "buchungsdatum": pd.Timestamp(z.buchungsdatum).date().isoformat(),
            "police_id": int(z.police_id),
            "ereignis": str(z.ereignis),
            "wirkungstag": pd.Timestamp(z.status_date).date().isoformat(),
            "betrag": float(z.betrag),
            "betrag_art": str(z.betrag_art),
            "herkunft": str(z.herkunft),
        }
        for z in letzte.itertuples(index=False)
    ]
    # Je Vorfall EINE Zaehlung: Wer liest, wie viele Zugaenge es gab, fragt
    # nach Vertraegen, nicht nach Buchungszeilen (ein Zugang bucht Summe und
    # Beitrag).
    je_ereignis = {
        str(k): int(v)
        for k, v in sorted(
            journal[["police_id", "ereignis", "status_date"]]
            .drop_duplicates()["ereignis"].value_counts().items()
        )
    } if len(journal) else {}
    modell = {
        "schema_version": PAKET_SCHEMA_VERSION,
        "stand": heute.isoformat(),
        "gefuehrt_seit": (
            zeilen[0]["nachgeholt"][0] if zeilen[0].get("nachgeholt") else zeilen[0]["heute"]
        ),
        "bestand": dict(zeile["bestand"]),
        "neugeschaeft": {
            "seit_betriebsbeginn": int(zeile.get("neugeschaeft_seit_betriebsbeginn", 0)),
            **woche,
        },
        "buchungen": {
            "gesamt": int(len(journal)),
            "je_ereignis": je_ereignis,
            "letzte": buchungen,
        },
        # Die leere Ersatztabelle oben traegt die uebrigen Bloecke; als
        # Kennzahlenquelle taugt sie nicht. Sie lieferte lauter Nullen,
        # und eine Null waere hier die Behauptung "kein Vorfall" statt
        # der Wahrheit "nicht gerechnet".
        "abschluesse": abschluesse_aus_protokoll(
            zeilen,
            journal=journal if journal_vorhanden else None,
            abschluesse_dir=ablage.abschluesse,
        ),
        "uebernahmen": list(zeile.get("uebernahmen") or []),
        "verankerung": dict(zeile.get("verankerung") or {}),
        "provenienz": {
            "manifest_sha256": zeile.get("manifest_sha256"),
            "config_sha256": zeile.get("config_sha256"),
            "kern_version": zeile.get("kern_version"),
            "image_digest": zeile.get("image_digest"),
            "image_revision": zeile.get("image_revision"),
            "image_tag": zeile.get("image_tag"),
            "pb1": zeile.get("pb1", {}).get("urteil"),
            "tagesjournal_sha256": (zeile.get("tagesjournal") or {}).get("sha256"),
        },
    }
    return modell, gelesen


# --------------------------------------------------------------------------- #
# Bestand heute (HTML)
# --------------------------------------------------------------------------- #

_STIL = """
body{margin:0;background:#f8f8f6;color:#1b1e1c;font:15px/1.55 system-ui,sans-serif}
main{max-width:58rem;margin:0 auto;padding:2.5rem 1.2rem 5rem}
h1{font:600 2rem/1.15 Georgia,serif;margin:0 0 .3rem}
h2{font:600 1.25rem/1.25 Georgia,serif;margin:2.2rem 0 .7rem}
.unter{color:#5f6663;margin:0 0 1.8rem}
.zahlen{display:grid;gap:1px;background:#dcdfda;border:1px solid #dcdfda;border-radius:6px;
overflow:hidden;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));margin-bottom:2rem}
.zahl{background:#fff;padding:.8rem 1rem}.zahl b{display:block;font:600 1.4rem/1.1 Georgia,serif}
.zahl span{font-size:.72rem;color:#5f6663;text-transform:uppercase;letter-spacing:.05em}
table{border-collapse:collapse;width:100%;font-size:.87rem;background:#fff;
border:1px solid #dcdfda;border-radius:6px}
th{text-align:left;font-size:.7rem;text-transform:uppercase;color:#5f6663;padding:.5rem .8rem;
border-bottom:1px solid #c1c6bf}td{padding:.4rem .8rem;border-bottom:1px solid #dcdfda}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.fuss{margin-top:2.5rem;color:#5f6663;font-size:.78rem;font-family:ui-monospace,monospace}
.banderole{background:#fff4e0;border:1px solid #e0c48a;padding:.6rem .9rem;border-radius:6px;font-size:.88rem}
ul{padding-left:1.1rem}
"""


def _e(x: Any) -> str:
    return _html.escape(str(x))


def _zahl(x: float, dez: int = 2) -> str:
    return f"{x:,.{dez}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def neugeschaeft_der_woche(
    journal: pd.DataFrame, heute: _dt.date
) -> Dict[str, Any]:
    """Das Neugeschaeft der letzten sieben Tage: je Tag und in Summe.

    Oeffentlich, weil zwei Seiten dieselbe Ableitung brauchen (Befund
    T26-09): Der Erzeuger baut daraus ``stand.json``, der Konsument haelt
    ``stand.json`` dagegen. Vorher rechnete nur der Erzeuger, und der
    Konsument uebernahm die Zahlen ungeprueft ins veroeffentlichte
    Datenmodell — ``woche_summe`` liess sich auf 1.000.000 setzen, bei
    unveraendertem Anker und unveraendertem Journal.

    Gezaehlt werden VERKAEUFE, nicht Journalzeilen: Ein Zugang bucht seit
    dem gebuchten Beitrag zwei Zeilen (Summe und Bruttojahresbeitrag).
    Ueber ``size()`` gemeldet, waere das Neugeschaeft der Woche doppelt so
    gross wie die Zahl der Vertraege.
    """
    woche_ab = pd.Timestamp(heute - _dt.timedelta(days=6))
    neu = journal[(journal["herkunft"] == "neugeschaeft")
                  & (journal["buchungsdatum"] >= woche_ab)]
    vorfaelle = neu[["police_id", "status_date", "buchungsdatum"]].drop_duplicates()
    return {
        "woche": {
            pd.Timestamp(t).date().isoformat(): int(n)
            for t, n in sorted(vorfaelle.groupby("buchungsdatum").size().items())
        },
        "woche_summe": int(len(vorfaelle)),
    }


def luecken(modell: Dict[str, Any]) -> List[Dict[str, str]]:
    """Was der Stand NICHT belegt — sichtbar auf der Seite, nicht nur im Protokoll.

    Dieselbe Ehrlichkeit wie die Fall-Seite (T20-03): Ein Stand ohne
    erfassten Image-Digest ist nicht auf sein Image rueckfuehrbar, eine
    Uebernahme ohne A-M4-Snapshot nicht auf ihre Abnahme, ein Altsnapshot
    ohne Schluesselklasse weist sie nicht aus, und vor dem ersten
    Monatsabschluss gibt es keinen festgeschriebenen Stand.
    """
    aus: List[Dict[str, str]] = []
    p = modell.get("provenienz") or {}
    if not p.get("image_digest") or p.get("image_digest") == "nicht erfasst":
        aus.append({"was": "Image-Digest des Laufs",
                    "wirkung": "Der Stand ist auf Kern-Version und Config, nicht auf ein "
                               "Container-Image rueckfuehrbar."})
    for u in modell.get("uebernahmen") or []:
        if not u.get("snapshot_sha256"):
            aus.append({"was": f"A-M4-Snapshot der Uebernahme {u.get('fall')}",
                        "wirkung": "Der Zugang ist nicht auf seine Abnahme rueckfuehrbar."})
        z = u.get("zeichnung") or {}
        if z.get("schluesselklasse", "nicht ausgewiesen") == "nicht ausgewiesen":
            aus.append({"was": f"Schluesselklasse der A-M4-Zeichnung ({u.get('fall')})",
                        "wirkung": "Der Snapshot fuehrt sie nicht (Altsnapshot) oder er "
                                   "fehlt; die Rolle steht, die Schluesselklasse nicht."})
    if not modell.get("abschluesse"):
        aus.append({"was": "Monatsabschluss",
                    "wirkung": "Noch kein festgeschriebener Bewertungsstand."})
    v = modell.get("verankerung") or {}
    if v.get("registriert") and not v.get("angewandt"):
        aus.append({"was": "Verankerung der uebernommenen Vertraege in der Fortschreibung",
                    "wirkung": str(v.get("hinweis") or "Die Verankerung ist registriert, "
                                   "geht aber nicht in Storno und Bewertung ein.")})
    return aus


def _klassenhinweis(modell: Dict[str, Any]) -> str:
    """Was die Uebernahmen ueber die Schluesselklasse ihrer A-M4-Zeichnung
    SAGEN — nichts wird behauptet, was nicht in den Eingaengen steht
    (Review T22-06: die Banderole nannte unabhaengig von den Daten einen
    Simulationsschluessel)."""
    klassen = {
        str((u.get("zeichnung") or {}).get("schluesselklasse") or "nicht ausgewiesen")
        for u in modell.get("uebernahmen") or []
    }
    if not klassen:
        return ""
    if klassen == {"simulation"}:
        return (", die Migrationsabnahmen ihrer Uebernahmen weisen sich als Zeichnung "
                "mit einem Simulationsschluessel aus")
    if klassen == {"mensch"}:
        return ", die Migrationsabnahmen ihrer Uebernahmen weisen eine menschliche Zeichnung aus"
    return (", die Migrationsabnahmen ihrer Uebernahmen weisen ihre Schluesselklasse "
            f"als {', '.join(sorted(klassen))} aus")


def rendere_html(modell: Dict[str, Any]) -> str:
    """Den Abschnitt "Bestand heute" als selbst-enthaltene Seite rendern."""
    b = modell["bestand"]
    n = modell["neugeschaeft"]
    p = modell["provenienz"]
    z: List[str] = [
        "<!doctype html>\n<html lang=\"de\">\n<head>\n<meta charset=\"utf-8\">\n",
        f"<title>Bestand heute — Stand {_e(modell['stand'])}</title>\n",
        f"<style>{_STIL}</style>\n</head>\n<body>\n<main>\n",
        "<p class=\"banderole\"><b>Dies ist eine Vorfuehrung, kein echter Bestand.</b> "
        "Die Pfefferminzia LV ist ein fiktives Unternehmen, ihre Vertraege sind "
        f"synthetisch erzeugt{_klassenhinweis(modell)}. Diese Seite verifiziert keine "
        "Signatur; sie zeigt, was Protokoll und Tagesjournal fuehren.</p>\n",
        f"<h1>Bestand heute</h1>\n<p class=\"unter\">Pfefferminzia LV, gefuehrter Stand "
        f"<b>{_e(modell['stand'])}</b> (Tagesbetrieb seit {_e(modell['gefuehrt_seit'])}) · "
        f"Manifest <code>{_e((p.get('manifest_sha256') or '')[:16])}</code> · "
        f"Wache P-B1 {_e(p.get('pb1'))}.</p>\n",
    ]
    offene = luecken(modell)
    if offene:
        z.append("<h2>Was diese Seite NICHT zeigt</h2>\n<ul>\n")
        for l in offene:
            z.append(f"<li><b>{_e(l['was'])}</b> — {_e(l['wirkung'])}</li>\n")
        z.append("</ul>\n")
    z += [
        "<div class=\"zahlen\">\n",
        f"<div class=\"zahl\"><b>{b['in_force']}</b><span>Vertraege in Kraft</span></div>\n",
    ]
    for produkt, anzahl in sorted(b.get("je_produkt", {}).items()):
        z.append(f"<div class=\"zahl\"><b>{anzahl}</b><span>{_e(produkt.upper())}</span></div>\n")
    z += [
        f"<div class=\"zahl\"><b>{b.get('uebernommen_in_force', 0)}</b><span>davon uebernommen</span></div>\n",
        f"<div class=\"zahl\"><b>{b.get('policiert_beginn_folgt', 0)}</b><span>policiert, Beginn folgt</span></div>\n",
        f"<div class=\"zahl\"><b>{n['woche_summe']}</b><span>Neugeschaeft der Woche</span></div>\n",
        f"<div class=\"zahl\"><b>{n['seit_betriebsbeginn']}</b><span>Neugeschaeft seit Betriebsbeginn</span></div>\n",
        "</div>\n",
        "<h2>Neugeschaeft der Woche</h2>\n<table><thead><tr><th>Verkaufstag</th><th>Vertraege</th></tr></thead><tbody>\n",
    ]
    for tag, anzahl in n["woche"].items():
        z.append(f"<tr><td>{_e(tag)}</td><td class=\"num\">{anzahl}</td></tr>\n")
    if not n["woche"]:
        z.append("<tr><td colspan=\"2\">kein Abschluss in den letzten sieben Tagen</td></tr>\n")
    z.append("</tbody></table>\n<h2>Letzte Buchungen</h2>\n<table><thead><tr><th>Buchungstag</th>"
             "<th>Police</th><th>Vorfall</th><th>Wirkungstag</th><th>Betrag</th><th>Herkunft</th></tr></thead><tbody>\n")
    for bu in modell["buchungen"]["letzte"]:
        z.append(
            f"<tr><td>{_e(bu['buchungsdatum'])}</td><td>{bu['police_id']}</td>"
            f"<td>{_e(EREIGNIS_TITEL.get(bu['ereignis'], bu['ereignis']))}</td>"
            f"<td>{_e(bu['wirkungstag'])}</td><td class=\"num\">{_zahl(bu['betrag'])} "
            f"({_e(bu['betrag_art'])})</td><td>{_e(bu['herkunft'])}</td></tr>\n"
        )
    z.append("</tbody></table>\n<h2>Buchungen seit Betriebsbeginn</h2>\n<table><thead><tr><th>Vorfall</th><th>Anzahl</th></tr></thead><tbody>\n")
    for ereignis, anzahl in modell["buchungen"]["je_ereignis"].items():
        z.append(f"<tr><td>{_e(EREIGNIS_TITEL.get(ereignis, ereignis))}</td><td class=\"num\">{anzahl}</td></tr>\n")
    z.append("</tbody></table>\n<h2>Monatsabschluesse</h2>\n<table><thead><tr><th>Stichtag</th><th>Abschluss</th><th>Bericht</th></tr></thead><tbody>\n")
    for a in modell["abschluesse"]:
        bericht = (
            f"<a href=\"../berichte/{_e(a['bericht'])}\">{_e(a['bericht'])}</a>" if a.get("bericht") else "—"
        )
        for t in a.get("teilbestaende") or []:
            bericht += f"<br><a href=\"../berichte/{_e(t['bericht'])}\">Teilbestand {_e(t['fall'])}</a>"
        z.append(f"<tr><td>{_e(a['stichtag'])}</td><td><code>{_e(a.get('datei', '—'))}</code> "
                 f"<small>{_e((a.get('sha256') or '')[:16])}</small></td><td>{bericht}</td></tr>\n")
    z.append("</tbody></table>\n")
    if modell["uebernahmen"]:
        z.append("<h2>Uebernahmen</h2>\n<table><thead><tr><th>Fall</th><th>Stichtag</th><th>Vertraege</th>"
                 "<th>A-M4-Snapshot</th><th>Entscheid</th><th>Rolle</th><th>Entscheider</th>"
                 "<th>Schluesselklasse</th><th>Schluessel</th></tr></thead><tbody>\n")
        for u in modell["uebernahmen"]:
            zg = u.get("zeichnung") or {}
            z.append(f"<tr><td>{_e(u['fall'])}</td><td>{_e(u['stichtag'])}</td><td class=\"num\">{u['vertraege']}</td>"
                     f"<td><small>{_e((u.get('snapshot_sha256') or 'nicht erfasst')[:16])}</small></td>"
                     f"<td>{_e(zg.get('entscheid', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('rolle', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('entscheider', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('schluesselklasse', 'nicht ausgewiesen'))}</td>"
                     f"<td><small>{_e(zg.get('schluessel_sha256', 'nicht ausgewiesen'))}</small></td></tr>\n")
        z.append("</tbody></table>\n<p class=\"fuss\">Angaben der Snapshot-Datei des Falls; "
                 "Signatur hier nicht verifiziert (kein Schluesselring, T19-02).</p>\n")
    z.append(
        f"<p class=\"fuss\">Stand {_e(modell['stand'])} · Wache P-B1: {_e(p.get('pb1'))} · Manifest {_e((p.get('manifest_sha256') or '')[:16])} · "
        f"Config {_e((p.get('config_sha256') or '')[:16])} · Kern {_e(p.get('kern_version'))} · "
        f"Image {_e(p.get('image_tag'))} / {_e(p.get('image_revision'))} / {_e(p.get('image_digest'))}. "
        "Erzeugt aus Protokoll und Tagesjournal des Tagesbetriebs; nichts hier ist gerechnet, alles ist gebucht.</p>\n"
        "</main>\n</body>\n</html>\n"
    )
    return "".join(z)


def _schreibe(ziel: Path, text: str) -> Path:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = neue_datei(ziel.parent, ziel.name)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ziel


def rendere_bestand_heute(ablage, aktuelle_zeile: Optional[Dict[str, Any]] = None) -> Path:
    """``daten/seite/index.html`` aus dem uebernommenen Stand schreiben."""
    modell = stand_modell(ablage, aktuelle_zeile)
    return _schreibe(ablage.wurzel / SEITE_DIR / "index.html", rendere_html(modell))


# --------------------------------------------------------------------------- #
# Stands-Paket
# --------------------------------------------------------------------------- #


def _unter(pfad: Path, wurzel: Path) -> bool:
    return pfad == wurzel or wurzel in pfad.parents


def paketziel_fehler(ablage, ziel: Path) -> Optional[str]:
    """Darf ``ziel`` als Stands-Paket ersetzt werden? Leer = ja.

    Review T24-07: ``stands_paket`` entfernte JEDES vorhandene Zielverzeichnis
    — ``--paket`` gleich ``--stand`` loeschte die Ablage mit Stand, Journal
    und Protokoll; ein Tippfehler auf ein fremdes Verzeichnis dessen Inhalt.
    Ein Produzent ersetzt nur, was er selbst erzeugt hat: Das Ziel liegt
    weder in der Ablage noch enthaelt es sie, und ein vorhandenes Ziel ist
    ein frueheres Paket (traegt ``stand.json``). Alles andere ist ein
    benannter Fehler, kein Loeschen.
    """
    wurzel = Path(ablage.wurzel).resolve()
    aufgeloest = Path(ziel).resolve()
    if _unter(aufgeloest, wurzel) or _unter(wurzel, aufgeloest):
        return (
            f"Stands-Paket: Ziel {ziel} ist die Ablage {ablage.wurzel}, liegt in "
            "ihr oder enthaelt sie — das Paket wuerde den Stand loeschen; ein "
            "Verzeichnis ausserhalb der Ablage waehlen"
        )
    if Path(ziel).is_symlink():
        return f"Stands-Paket: Ziel {ziel} ist ein Symlink — nur ein echtes Verzeichnis wird ersetzt"
    if Path(ziel).exists():
        if not Path(ziel).is_dir():
            return f"Stands-Paket: Ziel {ziel} ist eine Datei, kein Verzeichnis"
        if not (Path(ziel) / PAKET_DATEI).is_file():
            return (
                f"Stands-Paket: Ziel {ziel} existiert und ist kein frueheres "
                f"Stands-Paket (keine {PAKET_DATEI}) — ersetzt wird nur ein Paket; "
                "anderes Ziel waehlen oder das Verzeichnis von Hand entfernen"
            )
    return None


def ankerziel_fehler(ablage, paket_ziel: Path, anker_verzeichnis: Path) -> Optional[str]:
    """Liegt das Ankerverzeichnis ausserhalb dessen, was dieser Export
    anfasst? Leer = ja.

    Der Anker ist der einzige Bezug des Pakets nach aussen (models.anker):
    der Hash der letzten Protokollzeile, abgelegt dort, wo der schreibende
    Prozess nicht hinlangt.

    Liegt er IM PAKET, ist er keiner. Der Export ersetzt das Paket bei
    jedem Lauf und nimmt die Ankerhistorie mit — gemessen zwei Saetze vor
    dem Reexport und einer danach, obwohl die Reihe laut Vertrag nur
    wachsen darf. Und der Konsument haelt die Faelschung dann gegen ihre
    eigene Beilage: Eine konsistent von 68 auf 1068 Vertraege
    umgeschriebene Lieferung wurde angenommen (Befund T26-08).

    Liegt er in der ABLAGE, schreibt der Tagesbetrieb selbst an den Ort,
    der ihn binden soll. Beides ist dieselbe Aussage: Ein Wert, den der
    schreibende Prozess aendern kann, ist kein Anker.

    Geprueft wird mit derselben Regel wie fuer Ordnung, Schluessel und
    Mandat (``models.zeichnung.ausserhalb_von``): lexikalisch UND
    aufgeloest, damit weder ``paket/../paket/anker`` noch ein Symlink
    daran vorbeikommt.
    """
    from rechner_pipeline.models.zeichnung import ausserhalb_von

    anker = Path(anker_verzeichnis)
    for was, bereich in (("die Ablage", Path(ablage.wurzel)),
                         ("das Stands-Paket", Path(paket_ziel))):
        if not ausserhalb_von(anker, bereich, muss_existieren=False):
            return (
                f"Anker: {anker_verzeichnis} liegt in oder auf {was} "
                f"({bereich}) — ein Bezug, den der schreibende Prozess selbst "
                "anfassen kann, bindet nichts. Ein Verzeichnis ausserhalb von "
                "Ablage und Paket waehlen (Fall-Datenraum)."
            )
    return None


def _zeichnung_des_exports(
    satz: Dict[str, Any], schluessel: Path, ordnung_pfad: Optional[Path],
    ablage_wurzel: Path,
) -> Dict[str, Any]:
    """Rolle aus der Ordnung bestimmen und den Ankersatz zeichnen.

    Die Rolle wird nicht behauptet, sondern aus dem SCHLUESSEL bestimmt:
    Wer die Datei besitzt, deren Fingerabdruck die Ordnung einer Rolle
    zuordnet, handelt als diese Rolle (ADR-018). Eine Zeichnung ohne
    Ordnung waere eine Rolle, die sich selbst vergibt.
    """
    from rechner_pipeline.models.zeichnung import (
        lade_zeichnungsordnung,
        schluesselklasse,
        zeichnungsrolle,
    )

    if ordnung_pfad is None:
        raise SeiteError(
            "--schluessel verlangt --zeichnungsordnung: Die Rolle wird aus "
            "dem Schluessel BESTIMMT, nicht behauptet (ADR-018)")
    # Die Ordnung darf nicht in der ABLAGE liegen — dieselbe Regel wie
    # "nicht im Fall": Die Rollenbindung wird nicht dort verwahrt, wo der
    # Prozess schreibt, der sich auf sie beruft.
    ordnung, _sha, fehler = lade_zeichnungsordnung(
        str(ordnung_pfad), Path(ablage_wurzel))
    if fehler or ordnung is None:
        raise SeiteError("Zeichnungsordnung: " + "; ".join(fehler[:3]))
    try:
        roh = Path(schluessel).read_bytes()
    except OSError as exc:
        raise SeiteError(f"Schluessel nicht lesbar: {exc}") from exc
    fingerabdruck = hashlib.sha256(roh).hexdigest()
    rolle = zeichnungsrolle(ordnung, fingerabdruck)
    if rolle is None:
        raise SeiteError(
            f"Der Schluessel ({fingerabdruck[:16]}…) gehoert zu keiner Rolle "
            "der Zeichnungsordnung — ohne Rolle keine Zeichnung")
    return zeichne(satz, roh, rolle=rolle,
                   klasse=str(schluesselklasse(ordnung, rolle)))


def stands_paket(
    ablage, ziel: Path, *, anker_verzeichnis: Path,
    art: str = ART_MOMENTAUFNAHME,
    schluessel: Optional[Path] = None,
    zeichnungsordnung: Optional[Path] = None,
) -> Path:
    """Den Stand als Paket exportieren: ``stand.json`` plus die Berichte des
    juengsten Abschlusses und die Seite "Bestand heute".

    Das Paket ist die Quelle der Vorzeigeseite (``werkzeuge/falldaten.py
    --stands-paket``). Es traegt seine Provenienz (Manifest-, Config- und
    Journal-Hash, Kern-Version, Image), damit die Seite sagen kann, von
    welchem Stand sie spricht.

    ``art`` unterscheidet die MOMENTAUFNAHME (ein gewoehnlicher Export)
    von der AUSLIEFERUNG, bei der der Stand nach aussen sichtbar wird.
    Nur die Auslieferung braucht die menschliche Abnahme A-B1; sie kommt
    nicht von hier, sondern vom Entscheid-Kommando. Der Export selbst
    zeichnet den Ankersatz, wenn ein Schluessel gegeben ist — das ist eine
    Aussage ueber URHEBERSCHAFT, und ein Agent darf sie machen (ADR-018,
    Nachtrag 2026-09-16).

    ``anker_verzeichnis`` ist PFLICHT (Review T24-04, Teil 2): Der Export
    legt dort den Hash der letzten Protokollzeile ab und nennt den
    Ankersatz in ``stand.json``. Ohne diesen Bezug nach aussen belegt das
    Paket nur sich selbst — die Kette schuetzt ihre letzte Zeile nicht,
    und aus genau ihr leitet stand.json ab. Der Ort gehoert NICHT in die
    Ablage: Ein Wert, den der schreibende Prozess selbst aendern kann,
    ist kein Anker. Ein vorhandenes Paket wird ersetzt — es ist
    eine Momentaufnahme, kein Nachweis; der Nachweis liegt in der Ablage.
    Ersetzt wird aber NUR ein frueheres Paket ausserhalb der Ablage
    (``paketziel_fehler``, Review T24-07).
    """
    ziel = Path(ziel)
    fehler = paketziel_fehler(ablage, ziel)
    if fehler:
        raise SeiteError(fehler)
    # VOR jeder Loeschung: Ein Anker im Paket wuerde mit dem Paket
    # verschwinden, und ein Anker in der Ablage waere keiner (T26-08).
    fehler = ankerziel_fehler(ablage, ziel, anker_verzeichnis)
    if fehler:
        raise SeiteError(fehler)
    modell, gelesen = stand_modell_mit_bytes(ablage)
    if ziel.exists():
        # Die Wache ist paketziel_fehler (Ablage-Grenze, Symlink, Marker);
        # entferne_verzeichnis wiederholt Marker- und Symlink-Pruefung und
        # bindet den Namen: ersetzt wird genau das genannte Paket.
        try:
            entferne_verzeichnis(
                ziel, innerhalb=ziel.parent, name_ok=lambda n: n == ziel.name,
                marker=PAKET_DATEI, grund="frueheres Stands-Paket",
            )
        except LoeschFehler as exc:
            raise SeiteError(str(exc)) from exc
    ziel.mkdir(parents=True)
    dateien: Dict[str, str] = {}
    for a in modell["abschluesse"][-1:]:
        for name in [a.get("bericht")] + [t["bericht"] for t in a.get("teilbestaende") or []]:
            if not name:
                continue
            quelle = ablage.berichte / name
            if quelle.is_file():
                shutil.copyfile(quelle, ziel / name)
                dateien[name] = sha256_bytes((ziel / name).read_bytes())
    # Die juengsten Monatsabschluesse selbst (Schema 5). stand.json nennt
    # je Abschluss eine Vertragszahl; ohne den Abschluss daneben bliebe
    # sie zu glauben — dieselbe Figur wie in_force vor T24-04. Kopiert
    # wird genau die Auswahl, fuer die auch in_kraft abgeleitet wird.
    for a in juengste_abschluesse(modell["abschluesse"]):
        quelle = ablage.abschluesse / a["datei"]
        if not quelle.is_file():
            continue
        name = f"{PAKET_ABSCHLUESSE_DIR}/{a['datei']}"
        (ziel / PAKET_ABSCHLUESSE_DIR).mkdir(exist_ok=True)
        shutil.copyfile(quelle, ziel / name)
        dateien[name] = sha256_bytes((ziel / name).read_bytes())
    seite = ziel / "index.html"
    _schreibe(seite, rendere_html(modell))
    dateien["index.html"] = sha256_bytes(seite.read_bytes())
    # Belege: Protokoll (mit Kette) und Manifest des Stands (T22-05), dazu
    # das Tagesjournal (T24-04, Teil 1) — der Konsument haelt stand.json
    # dagegen, statt dem Wort "gruen" zu glauben, und leitet die
    # journalgespeisten Zahlen aus Zeilen ab statt aus Feldern. Ohne das
    # Journal war die halbe stand.json unbelegt: Geschaeftsentwicklung,
    # buchungen.* und das Neugeschaeft der Woche kommen von dort.
    from rechner_pipeline.bestand.manifest import MANIFEST_DATEI

    if not ablage.tagesjournal_pfad.is_file():
        raise SeiteError(
            f"{ablage.tagesjournal_pfad} fehlt — ein Stands-Paket ohne "
            "Tagesjournal belegt seine Buchungszahlen nicht"
        )
    # Manifest und Journal kommen aus den GEPRUEFTEN Bytes, nicht von der
    # Platte (Befund T26-10): Zwischen Pruefung und Kopie kann ein
    # Tageslauf liegen, und das Paket truege dann Belege einer anderen
    # Generation als die Zahlen daneben. Das Protokoll wird kopiert — es
    # ist nur anfuegbar, und seine Kette prueft der Konsument selbst.
    shutil.copyfile(ablage.protokoll_pfad, ziel / PAKET_PROTOKOLL)
    dateien[PAKET_PROTOKOLL] = sha256_bytes(
        (ziel / PAKET_PROTOKOLL).read_bytes())
    for name, roh in ((PAKET_MANIFEST, gelesen.get("manifest")),
                      (PAKET_JOURNAL, gelesen.get("journal"))):
        if roh is None:
            raise SeiteError(
                f"{name}: der gepruefte Nachweis traegt diese Bytes nicht — "
                "ein Paket ohne sie belegt seine Zahlen nicht")
        (ziel / name).write_bytes(roh)
        dateien[name] = sha256_bytes(roh)
    modell["dateien"] = dict(sorted(dateien.items()))
    modell["luecken"] = luecken(modell)
    # Der Anker: Erst den Satz bilden, dann ablegen, dann NENNEN. Genannt
    # wird sein eigener Hash — sonst genuegte einem Faelscher irgendein
    # passender Satz derselben Ablage.
    satz = ankersatz(
        ablage.protokoll_pfad, str(modell.get("stand")),
        dateien[PAKET_MANIFEST], dateien[PAKET_JOURNAL], art=art,
    )
    if schluessel is not None:
        satz["zeichnung"] = _zeichnung_des_exports(
            satz, Path(schluessel), zeichnungsordnung, ablage.wurzel)
    pfad = haenge_an(Path(anker_verzeichnis), satz)
    modell["anker"] = {
        "datei": str(pfad),
        "sha256": satz_hash(satz),
        "stand": satz["stand"],
        "art": satz["art"],
        # Der Konsument weist aus, WER gezeichnet hat — und verlangt bei
        # einer Auslieferung zusaetzlich die Abnahme A-B1.
        "zeichnung": satz.get("zeichnung"),
    }
    _schreibe(ziel / PAKET_DATEI, json.dumps(modell, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return ziel


def main(argv: Optional[List[str]] = None) -> int:
    from rechner_pipeline.betrieb.tageslauf import Ablage, TageslaufError

    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.seite",
        description="Bestand heute aus dem gefuehrten Stand rendern und als Stands-Paket exportieren.",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument("--paket", default=None, help="Zielverzeichnis des Stands-Pakets (optional).")
    parser.add_argument(
        "--auslieferung", action="store_true",
        help="Dieses Paket geht nach AUSSEN. Es braucht zusaetzlich die "
             "menschliche Abnahme A-B1 (gates.gate_entscheid --gate A-B1); "
             "ohne sie veroeffentlicht der Auftritt es nicht.")
    parser.add_argument(
        "--schluessel", default=None,
        help="Freigabeschluessel, mit dem der ANKERSATZ gezeichnet wird "
             "(Urheberschaft, keine Abnahme). Die Rolle wird aus dem "
             "Schluessel bestimmt, nicht behauptet.")
    parser.add_argument(
        "--zeichnungsordnung", default=None,
        help="Zeichnungsordnung (Pflicht mit --schluessel).")
    parser.add_argument(
        "--anker", default=None,
        help="Verzeichnis der Ankerdatei (Pflicht mit --paket). Es gehoert "
             "NICHT in die Ablage: Der Anker bindet das Paket an einen Ort, "
             "den der Tagesbetrieb nicht anfasst.")
    ns = parser.parse_args(argv)
    ablage = Ablage(Path(ns.stand))
    try:
        seite = rendere_bestand_heute(ablage)
        print(f"seite: {seite}", file=sys.stderr)
        if ns.paket and not ns.anker:
            print("seite: --paket verlangt --anker — ein Stands-Paket ohne "
                  "Bezug nach aussen belegt nur sich selbst (T24-04)",
                  file=sys.stderr)
            return 2
        if ns.paket:
            paket = stands_paket(
                ablage, Path(ns.paket), anker_verzeichnis=Path(ns.anker),
                art=(ART_AUSLIEFERUNG if ns.auslieferung
                     else ART_MOMENTAUFNAHME),
                schluessel=Path(ns.schluessel) if ns.schluessel else None,
                zeichnungsordnung=(Path(ns.zeichnungsordnung)
                                   if ns.zeichnungsordnung else None))
            print(f"seite: Stands-Paket -> {paket}", file=sys.stderr)
    except (SeiteError, TageslaufError, ValueError) as exc:
        print(f"seite: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
