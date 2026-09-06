"""Abschluss: festgeschriebene Bewertungsstaende der Bestandsfuehrung (ADR-011).

Ein funktionierendes Unternehmen rechnet seine Berichte zwar jederzeit
nach, aber ein abgeschlossener Stand ist FESTGESCHRIEBEN: Der Bilanzwert
eines Stichtags darf sich nachtraeglich nicht bewegen, auch wenn der
Rechenkern sich weiterentwickelt. Dieses Modul liefert genau das fuer den
gefuehrten Bestand:

* :func:`schreibe_abschluss` friert die einzelvertraglichen
  Bewertungsergebnisse eines Stichtags ein — gerechnet ueber DIESELBE
  Strecke wie jede andere Bewertung
  (:func:`rechner_pipeline.bestand.auswertung.einzelwerte_am`; ein
  zweiter Rechenweg waere der Drift-Mechanismus, den ADR-011 beseitigt).
  Je Stichtag existiert genau EIN Abschluss; ein zweiter Versuch ist ein
  harter Fehler, kein stilles Ueberschreiben.
* :func:`pruefe_abschluss` stellt die Neuberechnung gegen den
  festgeschriebenen Stand. Abweichungen werden AUSGEWIESEN — je Police
  und Groesse, mit dem Hinweis auf einen ggf. geaenderten Kernstand —
  und ersetzen den Abschluss nie.

Jede Zeile traegt die ``kern_version``, unter der sie entstand: Der
Abschluss ist damit der Wert eines benannten Standes, nicht eine
zeitlose Behauptung.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import os
import math
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.kern import __version__ as KERN_VERSION
from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES, validate_abschluss


class AbschlussError(ValueError):
    """Abschluss-Vertrag verletzt (Doppel-Festschreibung, kaputter Stand)."""


def abschluss_pfad(ziel_dir: Path, stichtag: _dt.date) -> Path:
    """Kanonischer Ablageort: eine Datei je Stichtag, nur-anfuegbar."""
    return Path(ziel_dir) / f"abschluss_{stichtag.isoformat()}.parquet"


def _rechne(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtag: _dt.date,
    scheiben: Optional[pd.DataFrame],
    merkmale: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    zeilen = einzelwerte_am(stamm, historie, config, stichtag,
                            scheiben=scheiben, merkmale=merkmale)
    if not zeilen:
        raise AbschlussError(
            f"Abschluss {stichtag.isoformat()}: kein in-force-Bestand am "
            "Stichtag — ein leerer Abschluss ist kein Stand, sondern ein "
            "Aufruffehler"
        )
    df = pd.DataFrame([
        {
            "police_id": z["police_id"],
            "stichtag": pd.Timestamp(stichtag),
            "produkt": z["produkt"],
            "tarif_generation": z["tarif_generation"],
            "status_code": z["status"],
            "leistung": z["leistung"],
            "deckungskapital": z["deckungskapital"],
            "rueckkaufswert": z["rueckkaufswert"],
            "vs_bfr": z["vs_bfr"],
            "jahresbeitrag": z["jahresbeitrag"],
            "kern_version": KERN_VERSION,
        }
        for z in zeilen
    ])
    df = df[list(ABSCHLUSS_NAMES)]
    # Endlichkeit am Ausgang (T18-04): Was hier durchgeht, wird
    # festgeschrieben und nie ueberschrieben. Ein nichtendlicher Wert ist
    # kein Bilanzwert, sondern ein Rechen- oder Konfigurationsfehler, der
    # VOR dem Publish anhalten muss — nicht erst in der Kontrolle danach.
    befunde = validate_abschluss(df)
    if befunde:
        raise AbschlussError(
            f"Abschluss {stichtag.isoformat()}: der gerechnete Stand ist "
            "kein festschreibbarer Bilanzstand: " + "; ".join(befunde)
        )
    return df


def schreibe_abschluss(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtag: _dt.date,
    ziel_dir: Path,
    *,
    scheiben: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
) -> Path:
    """Bewertungsstand des Stichtags festschreiben (genau einmal).

    Existiert fuer den Stichtag bereits ein Abschluss, bricht der Aufruf
    hart ab — eine Korrektur eines festgeschriebenen Standes ist eine
    menschliche Entscheidung mit eigenem Vorgang, nie ein erneuter Lauf.
    """
    ziel_dir = Path(ziel_dir)
    pfad = abschluss_pfad(ziel_dir, stichtag)
    if pfad.exists():
        raise AbschlussError(
            f"Abschluss {stichtag.isoformat()} ist bereits festgeschrieben "
            f"({pfad}) — festgeschriebene Staende werden nie ueberschrieben"
        )
    df = _rechne(stamm, historie, config, stichtag, scheiben, merkmale)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    # Zwei Sicherungen, die einzeln beide zu wenig tragen und erst
    # zusammen dicht sind -- die Reihenfolge ist deshalb wesentlich.
    #
    # Zuerst der exklusive Publish: Die exists()-Pruefung oben ist eine
    # Momentaufnahme, zwischen ihr und dem Schreiben liegt die Berechnung.
    # Zwei parallele Aufrufe kamen beide durch, und os.replace
    # ueberschrieb den zuerst veroeffentlichten Stand -- beide meldeten
    # Erfolg. os.link scheitert stattdessen atomar, wenn der Zielpfad
    # schon existiert; das macht die Zusage "genau einmal" wahr, ohne
    # Lock-Infrastruktur.
    #
    # Danach der Schreibschutz: Ein festgeschriebener Stand wehrt sich
    # auch gegen die Hand -- 0444, damit ein versehentliches
    # Ueberschreiben scheitert und ein rm ohne -f nachfragt statt still
    # zu loeschen. Anlass war ein realer Verlust echter Laufdaten durch
    # ein aufraeumendes rm -r (Backlog "runs/-Schutz").
    #
    # Warum beides: Nachgemessen ueberfaehrt os.replace eine 0444-Datei
    # anstandslos und hinterlaesst sie mit 0600 -- der Schreibschutz
    # allein hielt also gegen alles ausser gegen unseren eigenen
    # Schreibpfad. Und der exklusive Publish schuetzt nur beim
    # Veroeffentlichen, nicht danach. Gegen rm -rf schuetzt ohnehin kein
    # Dateirecht; das bleibt eine Verhaltensregel: runs/ ist Wegwerf,
    # Festzuhaltendes lebt im Fall oder in einem Abschluss.
    try:
        geschrieben = write_portfolio(df, pfad, exklusiv=True)
    except FileExistsError as exc:
        raise AbschlussError(
            f"Abschluss {stichtag.isoformat()} ist bereits festgeschrieben "
            f"({pfad}) — festgeschriebene Staende werden nie ueberschrieben"
        ) from exc
    if os.name != "nt":
        Path(geschrieben).chmod(0o444)
    return geschrieben


def pruefe_abschluss(
    pfad: Path,
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    *,
    scheiben: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
) -> List[str]:
    """Neuberechnung gegen den festgeschriebenen Stand stellen.

    Rueckgabe: Befundliste (leer = deckungsgleich). Eine Abweichung bei
    geaendertem Kernstand ist ERWARTBAR und wird als solche benannt —
    sie ist ein Ausweis, kein Anlass, den Abschluss anzufassen.
    """
    fest = read_portfolio(Path(pfad))
    befunde: List[str] = []
    if list(fest.columns) != list(ABSCHLUSS_NAMES):
        return [f"abschluss: Spalten {list(fest.columns)} != {list(ABSCHLUSS_NAMES)}"]
    if len(fest) == 0:
        return ["abschluss: leer — kein festgeschriebener Stand"]
    stichtage = fest["stichtag"].unique()
    if len(stichtage) != 1:
        return [f"abschluss: mehrere Stichtage in einer Datei ({len(stichtage)})"]
    stichtag = pd.Timestamp(stichtage[0]).date()
    # Der Dateiname IST die Aussage, welchen Stichtag der Stand traegt
    # (abschluss_pfad). Weichen Name und Inhalt ab, ist die Datei kaputt und
    # nicht etwa befundfrei: Ohne diese Bindung meldet die Neuberechnung
    # "deckungsgleich", weil sie gegen den INHALTS-Stichtag rechnet.
    erwartet = abschluss_pfad(Path(pfad).parent, stichtag)
    if Path(pfad).name != erwartet.name:
        return [
            f"abschluss: Datei heisst {Path(pfad).name}, enthaelt aber den "
            f"Stichtag {stichtag.isoformat()} (erwartet {erwartet.name})"
        ]
    # Der festgeschriebene Stand selbst muss ein Bilanzstand sein — auch
    # wenn er unter einem aelteren Stand ohne diese Pruefung entstand.
    befunde.extend(validate_abschluss(fest))

    neu = _rechne(stamm, historie, config, stichtag, scheiben, merkmale)
    kern_stand_alt = sorted(set(fest["kern_version"]))
    if kern_stand_alt != [KERN_VERSION]:
        befunde.append(
            f"abschluss: festgeschrieben unter Kern {kern_stand_alt}, "
            f"Neuberechnung unter {KERN_VERSION} — Abweichungen sind "
            "erwartbar und werden ausgewiesen, der Abschluss bleibt stehen"
        )

    fest_idx = fest.set_index("police_id")
    neu_idx = neu.set_index("police_id")
    nur_fest = sorted(set(fest_idx.index) - set(neu_idx.index))
    nur_neu = sorted(set(neu_idx.index) - set(fest_idx.index))
    if nur_fest:
        befunde.append(f"abschluss: Policen nur im Abschluss: {nur_fest[:5]}")
    if nur_neu:
        befunde.append(f"abschluss: Policen nur in der Neuberechnung: {nur_neu[:5]}")

    gemeinsam = fest_idx.index.intersection(neu_idx.index)
    zahlen = ("leistung", "deckungskapital", "rueckkaufswert", "vs_bfr", "jahresbeitrag")
    for pid in gemeinsam:
        f, n = fest_idx.loc[pid], neu_idx.loc[pid]
        for sp in ("status_code", "produkt", "tarif_generation"):
            if str(f[sp]) != str(n[sp]):
                befunde.append(
                    f"abschluss police {pid}: {sp} {f[sp]} -> {n[sp]}"
                )
        for sp in zahlen:
            alt_wert, neu_wert = float(f[sp]), float(n[sp])
            # math.isclose(inf, inf) ist WAHR: ein nichtendlicher Bilanzwert
            # wuerde sich selbst decken und die Kontrolle bestaetigte einen
            # Stand, den niemand verantworten kann. Endlichkeit zuerst.
            if not math.isfinite(alt_wert) or not math.isfinite(neu_wert):
                befunde.append(
                    f"abschluss police {pid}: {sp} nichtendlich "
                    f"(festgeschrieben {alt_wert!r}, neu {neu_wert!r}) — "
                    "ein Bilanzwert ist endlich"
                )
            elif not math.isclose(alt_wert, neu_wert, rel_tol=0.0, abs_tol=0.0):
                befunde.append(
                    f"abschluss police {pid}: {sp} festgeschrieben "
                    f"{alt_wert!r}, neu {neu_wert!r}"
                )
    return befunde


def vorhandene_abschluesse(ziel_dir: Path) -> Dict[_dt.date, Path]:
    """Alle festgeschriebenen Stichtage eines Verzeichnisses, sortiert."""
    ziel_dir = Path(ziel_dir)
    if not ziel_dir.is_dir():
        return {}
    ergebnis: Dict[_dt.date, Path] = {}
    for pfad in sorted(ziel_dir.glob("abschluss_*.parquet")):
        roh = pfad.stem.removeprefix("abschluss_")
        try:
            ergebnis[_dt.date.fromisoformat(roh)] = pfad
        except ValueError as exc:
            raise AbschlussError(
                f"abschluss: Dateiname {pfad.name} traegt kein ISO-Datum"
            ) from exc
    return ergebnis
