"""``betrieb.tageslauf`` — der naechtliche Lauf der PLV (Fachkonzept Tagesbetrieb, Abschnitt 7).

Ein Kommando, idempotent und deterministisch::

    python -m rechner_pipeline.betrieb.tageslauf --stand <daten> --heute <datum>

``--stand`` ist das Datenverzeichnis der Laufzeitumgebung
(``~/apps/plv/daten``, Abschnitt 7 des Konzepts); ``--heute`` der
Kalendertag, der gefuehrt werden soll — ohne Angabe der Kalendertag des
Aufrufs (die einzige Stelle, an der der Tagesbetrieb eine Uhr liest, und
sie steht ausserhalb der Simulation: alles Weitere ist eine Funktion von
Config, Eingaengen und Kalendertag).

Was ein Lauf tut, in dieser Reihenfolge:

1. **Nachholen.** Liegt der letzte gefuehrte Tag vor ``heute - 1``, gilt
   der Lauf fuer alle fehlenden Tage. Weil der Stand eines Tages die
   deterministische Fortschreibung bis zu diesem Tag ist und das
   Tagesjournal seine Buchungstage aus dem Wirkungstag ableitet, ist der
   Stand nach dem Nachholen derselbe, als haette der Lauf jede Nacht
   stattgefunden — nur das Protokoll hat eine Zeile statt vieler, und
   die nennt die nachgeholten Tage.
2. **Neugeschaeft.** Alle Verkaufstage vom Betriebsbeginn bis heute
   (:mod:`rechner_pipeline.betrieb.neugeschaeft`) — je Tag fuer sich
   reproduzierbar.
3. **Fortschreibung bis heute.** Basisbestand (Batch bis Betriebsbeginn)
   plus Uebernahme-Eingaenge plus Neugeschaeft, EIN Lauf der bestehenden
   Engine (``bestand.ereignisse.fortschreiben``); die Buchungen der
   Uebernahmen stehen dem Journal voran wie in ``cli_fortschreibung``.
4. **Tagesjournal.** Die bis heute faelligen, noch nicht gebuchten
   Buchungen anfuegen (:mod:`rechner_pipeline.betrieb.tagesjournal`).
5. **Wache.** Die P-B1-Engine (``bestand.vorbedingungen.lies_und_pruefe_pb1``)
   auf dem NEUEN Stand mit Config, Manifest und Merkmalen — dieselbe
   Pruefung, die Gate P-B1 faehrt, ueber die Bytes, die geschrieben
   wurden. Rot heisst: Der Stand wird nicht uebernommen, der gestrige
   bleibt der gefuehrte, der Befund steht im Protokoll, Exit 3. Ein
   Bestandsfuehrungssystem, das einen roten Stand still uebernimmt, waere
   die schlechteste Variante.
6. **Monatsabschluss** fuer jeden Monatsersten in ``(letzter Tag,
   heute]``: ``bestand.abschluss.schreibe_abschluss`` mit Stichtag
   Monatserster (Konvention Monatserster; Bewertung ueber dieselbe eine
   Strecke wie jeder Abschluss, festgeschrieben 0444, genau einmal —
   ADR-011) und der Bestandsbericht des Monats. Der Horizont eines Laufs
   ist der gefuehrte Tag selbst; der Stand des Ersten enthaelt dessen
   Buchungen, deshalb entsteht der Abschluss zum Ersten im Lauf des
   Ersten — der Ultimo-Lauf koennte ihn noch nicht bewerten
   (``stichtag <= bis``). Die Erstbefuellung schreibt so auch den
   Eroeffnungsstand zum Betriebsbeginn.
7. **Tagesprotokoll**: eine JSON-Zeile je Lauf.

Der Stand wird erst uebernommen, wenn die Wache gruen ist: Der Lauf
schreibt in ein Arbeitsverzeichnis neben ``stand/``, prueft dort, und
tauscht dann atomar. Ein Absturz mitten im Lauf hinterlaesst den alten
Stand und ein Arbeitsverzeichnis, das der naechste Lauf verwirft.

Ablage unter ``--stand`` (Konzept, Abschnitt 7)::

    stand/          sechs Ausgaben + laufmanifest.json (+ merkmale.parquet)
    journal/        tagesjournal.parquet, protokoll.jsonl (nur-anfuegbar)
    abschluesse/    abschluss_<stichtag>.parquet (0444, genau einmal)
    berichte/       bestandsbericht_<stichtag>.html je Monatsabschluss
    uebernahme/     je Migrationsfall ein Eingang (Block B5)
    configs/        die Config der PLV (Kopie; Hash im Protokoll)

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.abschluss import AbschlussError, abschluss_pfad, schreibe_abschluss
from rechner_pipeline.bestand.config import BestandConfig, load_config
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.fuehrung import fuehre_fort
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.manifest import (
    MANIFEST_DATEI,
    ManifestError,
    lies_manifest,
    schreibe_manifest,
    sha256_bytes,
)
from rechner_pipeline.bestand.parquet_io import neue_datei, read_portfolio, write_portfolio
from rechner_pipeline.bestand.report import render_html
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.betrieb.neugeschaeft import NeugeschaeftError, neugeschaeft_zwischen
from rechner_pipeline.betrieb.tagesjournal import (
    TagesjournalError,
    leeres_tagesjournal,
    tagesjournal_ergaenzen,
    validate_tagesjournal,
)
from rechner_pipeline.betrieb.uebernahme import UebernahmeError, lies_uebernahmen
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    MERKMALE_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    TAGESJOURNAL_NAMES,
)

PROTOKOLL_SCHEMA_VERSION = 1
#: Benannter Zustand einer Protokollangabe, die die Umgebung nicht liefert.
NICHT_ERFASST = "nicht erfasst"
STAND_DIR = "stand"
JOURNAL_DIR = "journal"
ABSCHLUSS_DIR = "abschluesse"
BERICHT_DIR = "berichte"
CONFIG_DIR = "configs"
UEBERNAHME_DIR = "uebernahme"
TAGESJOURNAL_DATEI = "tagesjournal.parquet"
PROTOKOLL_DATEI = "protokoll.jsonl"
CONFIG_DATEI = "bestand.toml"
#: Arbeitsverzeichnis eines laufenden Tageslaufs (wird beim naechsten Lauf verworfen).
ARBEIT_DIR = "stand.neu"

#: Exit-Codes: 0 gruen und uebernommen, 2 Aufruf-/Eingangsfehler, 3 Wache rot
#: (Stand nicht uebernommen), 4 Journal- oder Abschlussfehler nach gruener
#: Wache (Stand nicht uebernommen).
EXIT_OK, EXIT_USAGE, EXIT_WACHE_ROT, EXIT_NACHLAUF = 0, 2, 3, 4


class TageslaufError(ValueError):
    """Eingang oder Ablage passen nicht zum Tagesbetrieb — fail-fast."""


# --------------------------------------------------------------------------- #
# Ablage
# --------------------------------------------------------------------------- #


class Ablage:
    """Die Verzeichnisse der Laufzeitumgebung (Konzept, Abschnitt 7)."""

    def __init__(self, wurzel: Path) -> None:
        self.wurzel = Path(wurzel)
        self.stand = self.wurzel / STAND_DIR
        self.arbeit = self.wurzel / ARBEIT_DIR
        self.journal = self.wurzel / JOURNAL_DIR
        self.abschluesse = self.wurzel / ABSCHLUSS_DIR
        self.berichte = self.wurzel / BERICHT_DIR
        self.configs = self.wurzel / CONFIG_DIR
        self.uebernahme = self.wurzel / UEBERNAHME_DIR

    @property
    def config_pfad(self) -> Path:
        return self.configs / CONFIG_DATEI

    @property
    def tagesjournal_pfad(self) -> Path:
        return self.journal / TAGESJOURNAL_DATEI

    @property
    def protokoll_pfad(self) -> Path:
        return self.journal / PROTOKOLL_DATEI


def lies_protokoll(pfad: Path) -> List[Dict[str, Any]]:
    """Alle Zeilen des Tagesprotokolls (leer, wenn es noch keines gibt)."""
    if not Path(pfad).is_file():
        return []
    zeilen: List[Dict[str, Any]] = []
    for nummer, roh in enumerate(Path(pfad).read_text(encoding="utf-8").splitlines(), 1):
        if not roh.strip():
            continue
        try:
            zeilen.append(json.loads(roh))
        except json.JSONDecodeError as exc:
            raise TageslaufError(
                f"{pfad}: Zeile {nummer} ist kein JSON ({exc}) — das Protokoll "
                "ist nur-anfuegbar; eine kaputte Zeile ist ein Befund, kein "
                "Grund zum Ueberschreiben"
            ) from exc
    return zeilen


def gefuehrter_tag(ablage: Ablage) -> Optional[_dt.date]:
    """Der letzte gruen gefuehrte Tag — aus dem Manifest des Stands.

    Das Manifest ist die Aussage des Stands ueber sich selbst (Horizont);
    das Protokoll muss dieselbe Aussage machen, sonst passen Stand und
    Nachweis nicht zusammen, und der Lauf bricht ab statt einen der
    beiden zu glauben.
    """
    if not ablage.stand.is_dir():
        return None
    try:
        manifest = lies_manifest(ablage.stand)
    except ManifestError as exc:
        raise TageslaufError(
            f"{ablage.stand}: {exc} — ein Stand ohne gueltiges Manifest ist "
            "kein gefuehrter Stand; Verzeichnis pruefen oder entfernen und "
            "die Erstbefuellung wiederholen"
        ) from exc
    tag = _dt.date.fromisoformat(str(manifest["horizont"]))
    gruene = [z for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]
    if not gruene:
        raise TageslaufError(
            f"{ablage.stand} fuehrt {tag.isoformat()}, aber das Protokoll "
            f"{ablage.protokoll_pfad} kennt keinen uebernommenen Lauf — Stand "
            "und Nachweis passen nicht zusammen"
        )
    letzte = _dt.date.fromisoformat(str(gruene[-1]["heute"]))
    if letzte != tag:
        raise TageslaufError(
            f"Stand fuehrt {tag.isoformat()}, das Protokoll {letzte.isoformat()} "
            "— Stand und Nachweis passen nicht zusammen"
        )
    return tag


def monatserste_in(von_exklusiv: _dt.date, bis_inklusiv: _dt.date) -> List[_dt.date]:
    """Alle Monatsersten in ``(von, bis]`` — die Abschluss-Stichtage eines Laufs."""
    tage: List[_dt.date] = []
    jahr, monat = von_exklusiv.year, von_exklusiv.month
    while True:
        monat += 1
        if monat == 13:
            jahr, monat = jahr + 1, 1
        kandidat = _dt.date(jahr, monat, 1)
        if kandidat > bis_inklusiv:
            break
        if kandidat > von_exklusiv:
            tage.append(kandidat)
    return tage


# --------------------------------------------------------------------------- #
# Der Lauf
# --------------------------------------------------------------------------- #


def _stand_bauen(
    config: BestandConfig, config_pfad: Path, ablage: Ablage, heute: _dt.date
) -> Tuple[Path, Dict[str, Any]]:
    """Den Stand fuer ``heute`` im Arbeitsverzeichnis erzeugen (noch nicht uebernommen)."""
    betriebsbeginn = config.tagesbetrieb.betriebsbeginn
    assert betriebsbeginn is not None
    basis = generate(config, bis=betriebsbeginn)
    ausgaben: List[Path] = []
    eingaben: Dict[str, Path] = {}
    if ablage.arbeit.exists():
        shutil.rmtree(ablage.arbeit)
    ablage.arbeit.mkdir(parents=True)
    ausgaben.append(write_portfolio(basis, ablage.arbeit / "bestand.parquet"))

    uebernahmen = lies_uebernahmen(ablage.uebernahme, config)
    merkmale = None
    historie_voran: List[pd.DataFrame] = []
    ledger_voran: List[pd.DataFrame] = []
    for ueb in uebernahmen:
        if ueb.stichtag > betriebsbeginn:
            raise TageslaufError(
                f"uebernahme {ueb.fall}: Stichtag {ueb.stichtag.isoformat()} "
                f"liegt nach dem Betriebsbeginn {betriebsbeginn.isoformat()} — "
                "ein Zugang waehrend des Betriebs ist im Tagesbetrieb nicht "
                "vorgesehen (Konzept, Abschnitt 6)"
            )
        basis = _zusammen(basis, ueb.bestand)
        historie_voran.append(ueb.historie)
        ledger_voran.append(ueb.ledger)
        if ueb.merkmale is not None and len(ueb.merkmale):
            merkmale = (
                ueb.merkmale if merkmale is None
                else pd.concat([merkmale, ueb.merkmale], ignore_index=True)
            )
        eingaben[f"uebernahme:{ueb.fall}"] = ueb.manifest_pfad

    zugaenge = neugeschaeft_zwischen(config, betriebsbeginn, heute)
    if len(zugaenge) and (zugaenge["insurance_start"] <= pd.Timestamp(betriebsbeginn)).any():
        raise TageslaufError(
            "Neugeschaeft mit Beginn am oder vor dem Betriebsbeginn — der "
            "Batch besiedelt diesen Zeitraum bereits (ein Erzeuger je Zeitfenster)"
        )
    ergebnis = fortschreiben(basis, config, heute, zugaenge=zugaenge, merkmale=merkmale)
    historie, ledger = ergebnis.historie, ergebnis.ledger
    if historie_voran:
        historie = _voran(pd.concat(historie_voran, ignore_index=True), historie,
                          ["police_id", "status_id"])
        ledger = _voran(pd.concat(ledger_voran, ignore_index=True), ledger,
                        ["police_id", "status_date"])
    gesamt = fuehre_fort(mit_zugaengen(basis, ergebnis.zugaenge), historie)

    ausgaben.append(write_portfolio(historie, ablage.arbeit / "historie.parquet"))
    ausgaben.append(write_portfolio(ledger, ablage.arbeit / "ledger.parquet"))
    ausgaben.append(write_portfolio(ergebnis.scheiben, ablage.arbeit / "scheiben.parquet"))
    ausgaben.append(write_portfolio(ergebnis.zugaenge, ablage.arbeit / "zugaenge.parquet"))
    ausgaben.append(write_portfolio(gesamt, ablage.arbeit / "bestand_gesamt.parquet"))
    if merkmale is not None:
        ausgaben.append(write_portfolio(
            merkmale[list(MERKMALE_NAMES)].reset_index(drop=True),
            ablage.arbeit / "merkmale.parquet"))
    schreibe_manifest(
        ablage.arbeit, horizont=heute, neuzugang_ab=None, config_pfad=config_pfad,
        ausgaben=ausgaben, eingaben=eingaben,
    )
    zahlen = {
        "basisvertraege": int(len(basis)),
        "uebernommene_vertraege": int(sum(len(u.bestand) for u in uebernahmen)),
        "neugeschaeft_seit_betriebsbeginn": int(len(zugaenge)),
        "gevos": int(len(ledger)),
        "erhoehungsscheiben": int(len(ergebnis.scheiben)),
        # Fall-Bezug jeder Uebernahme (Konzept, Abschnitt 6): Der Zugang
        # ist als datierter Eingang nachweisbar, nicht als anonyme Zeile.
        "uebernahmen": [
            {"fall": u.fall, "stichtag": u.stichtag.isoformat(),
             "vertraege": int(len(u.bestand)), "snapshot_sha256": u.snapshot_sha256}
            for u in uebernahmen
        ],
        "_uebernommene_policen": sorted(
            int(p) for u in uebernahmen for p in u.bestand["police_id"]),
        "_teilbestaende": {
            u.fall: sorted(int(p) for p in u.bestand["police_id"]) for u in uebernahmen
        },
    }
    return ablage.arbeit, zahlen


def _zusammen(eigen: pd.DataFrame, uebernommen: pd.DataFrame) -> pd.DataFrame:
    beide = pd.concat([eigen, uebernommen], ignore_index=True)
    doppelt = beide["police_id"][beide["police_id"].duplicated()]
    if len(doppelt):
        raise TageslaufError(
            f"police_id-Kollision zwischen eigenem und uebernommenem Bestand: "
            f"{sorted(set(doppelt))[:5]} — die Nummernkreise muessen getrennt sein"
        )
    return beide.sort_values("police_id", kind="stable").reset_index(drop=True)[list(STAMM_NAMES)]


def _voran(vorne: pd.DataFrame, hinten: pd.DataFrame, sortierung: List[str]) -> pd.DataFrame:
    beide = pd.concat([vorne, hinten], ignore_index=True)
    return beide.sort_values(sortierung, kind="stable").reset_index(drop=True)


def _wache(arbeit: Path, config_pfad: Path, heute: _dt.date) -> Tuple[Dict[str, Any], Dict[str, Any], List[dict]]:
    """P-B1-Engine ueber die geschriebenen Bytes des neuen Stands."""
    eingaben = {
        "portfolio": arbeit / "bestand_gesamt.parquet",
        "historie": arbeit / "historie.parquet",
        "ledger": arbeit / "ledger.parquet",
        "scheiben": arbeit / "scheiben.parquet",
        "config": config_pfad,
    }
    if (arbeit / "merkmale.parquet").is_file():
        eingaben["merkmale"] = arbeit / "merkmale.parquet"
    manifest = lies_manifest(arbeit)
    tabellen, geprueft, fehler, usage = lies_und_pruefe_pb1(eingaben, bis=heute, manifest=manifest)
    return tabellen, geprueft, usage + fehler


def _uebernehmen(ablage: Ablage) -> None:
    """Das Arbeitsverzeichnis atomar zum gefuehrten Stand machen."""
    alt = ablage.wurzel / (STAND_DIR + ".alt")
    if alt.exists():
        shutil.rmtree(alt)
    if ablage.stand.exists():
        os.rename(ablage.stand, alt)
    os.rename(ablage.arbeit, ablage.stand)
    if alt.exists():
        shutil.rmtree(alt)


def _teilbestand(tabellen: Dict[str, Any], policen: List[int]) -> Dict[str, Any]:
    """Die Tabellen eines uebernommenen Teilbestands — dieselben Zeilen, gefiltert.

    Kein zweiter Datenraum: Stamm, Journal, Ledger, Scheiben und Merkmale
    des Teilbestands sind die Zeilen des Gesamtstands, deren Police zum
    Eingang gehoert. Der Bericht rendert sie mit denselben Renderern wie
    den Gesamtbestand (Konzept, Abschnitt 6).
    """
    auswahl = set(policen)
    teil: Dict[str, Any] = {}
    for rolle in ("portfolio", "historie", "ledger", "scheiben", "merkmale"):
        tabelle = tabellen.get(rolle)
        teil[rolle] = (
            tabelle[tabelle["police_id"].isin(auswahl)].reset_index(drop=True)
            if tabelle is not None else None
        )
    return teil


def _bericht(
    tabellen: Dict[str, Any], config: BestandConfig, stichtag: _dt.date, heute: _dt.date,
    ziel: Path, quelle_hash: str, titel: Optional[str] = None,
) -> Path:
    html = render_html(
        tabellen["portfolio"],
        titel=titel or f"Bestandsbericht PLV zum {stichtag.isoformat()}",
        quelle_hash=quelle_hash,
        historie=tabellen["historie"],
        ledger=tabellen["ledger"],
        config=config,
        scheiben=tabellen["scheiben"],
        merkmale=tabellen.get("merkmale"),
        bis=heute,
        stichtag=stichtag,
    )
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = neue_datei(ziel.parent, ziel.name)
    try:
        tmp.write_text(html, encoding="utf-8", newline="\n")
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ziel


def _anfuegen(pfad: Path, zeile: Dict[str, Any]) -> None:
    """Eine Protokollzeile anfuegen (nur-anfuegbar, sortierte Schluessel)."""
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(zeile, ensure_ascii=False, sort_keys=True) + "\n"
    with open(pfad, "a", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _datei_hash(pfad: Path) -> Optional[str]:
    return sha256_bytes(Path(pfad).read_bytes()) if Path(pfad).is_file() else None


def tageslauf(
    ablage: Ablage,
    heute: _dt.date,
    *,
    image_digest: Optional[str] = None,
) -> Tuple[int, Dict[str, Any]]:
    """Den Tag ``heute`` fuehren (Bibliotheksform des Kommandos).

    Rueckgabe ``(exit_code, protokollzeile)``. Die Protokollzeile ist in
    jedem Fall angefuegt worden, auch bei roter Wache — das Protokoll ist
    der Nachweis, dass gelaufen wurde, nicht nur, dass es gut ging.
    """
    from rechner_pipeline.kern import __version__ as kern_version

    config_pfad = ablage.config_pfad
    if not config_pfad.is_file():
        raise TageslaufError(
            f"keine Config unter {config_pfad} — die Laufzeitumgebung traegt "
            "die Config der PLV als Kopie unter configs/ (deploy/plv/README.md)"
        )
    config = load_config(config_pfad)
    fehler = config.validate()
    if fehler:
        raise TageslaufError("Config ungueltig: " + "; ".join(fehler))
    betriebsbeginn = config.tagesbetrieb.betriebsbeginn
    if betriebsbeginn is None:
        raise TageslaufError(
            "die Config traegt keinen [tagesbetrieb] betriebsbeginn — ohne ihn "
            "gibt es keinen ersten Tag, ab dem verkauft wird"
        )
    if heute < betriebsbeginn:
        raise TageslaufError(
            f"heute {heute.isoformat()} liegt vor dem Betriebsbeginn "
            f"{betriebsbeginn.isoformat()}"
        )
    letzter = gefuehrter_tag(ablage)
    if letzter is not None and heute <= letzter:
        raise TageslaufError(
            f"der Stand fuehrt bereits {letzter.isoformat()}; heute "
            f"{heute.isoformat()} liegt nicht danach — ein Tag wird nicht "
            "zweimal und nicht rueckwaerts gefuehrt"
        )
    nachgeholt = []
    if letzter is not None:
        tag = letzter + _dt.timedelta(days=1)
        while tag < heute:
            nachgeholt.append(tag.isoformat())
            tag += _dt.timedelta(days=1)
    elif heute > betriebsbeginn:
        tag = betriebsbeginn
        while tag < heute:
            nachgeholt.append(tag.isoformat())
            tag += _dt.timedelta(days=1)

    zeile: Dict[str, Any] = {
        "schema_version": PROTOKOLL_SCHEMA_VERSION,
        "heute": heute.isoformat(),
        "gefuehrt_vorher": letzter.isoformat() if letzter else None,
        "nachgeholt": nachgeholt,
        "config_sha256": _datei_hash(config_pfad),
        "kern_version": kern_version,
        # Drei Angaben zum Image, jede mit dem benannten Zustand NICHT_ERFASST
        # statt eines leeren Felds (ein leeres Feld liest sich wie ein
        # Fehler): der Digest kommt aus .env, vom Menschen nach dem Pull
        # eingetragen — der Container kennt ihn selbst nicht (kein Netz,
        # kein Docker-Socket); Revision (Commit des Baus) und Tag traegt
        # das Image bzw. compose.yml. Ausserhalb des Containers fehlen alle.
        "image_digest": image_digest or NICHT_ERFASST,
        "image_revision": os.environ.get("PLV_IMAGE_REVISION") or NICHT_ERFASST,
        "image_tag": os.environ.get("PLV_IMAGE_TAG") or NICHT_ERFASST,
        "uebernommen": False,
    }
    exit_code = EXIT_OK
    try:
        arbeit, zahlen = _stand_bauen(config, config_pfad, ablage, heute)
        zeile.update(zahlen)
        tabellen, geprueft, befunde = _wache(arbeit, config_pfad, heute)
        zeile["pb1"] = {
            "urteil": "gruen" if not befunde else "rot",
            "geprueft": geprueft,
            "befunde": [b["message"] for b in befunde][:20],
        }
        if befunde:
            exit_code = EXIT_WACHE_ROT
            zeile.pop("_uebernommene_policen", None)
            zeile.pop("_teilbestaende", None)
        else:
            # Tagesjournal auf dem geprueften Ledger (dieselben Bytes).
            journal_alt = (
                read_portfolio(ablage.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
                if ablage.tagesjournal_pfad.is_file() else leeres_tagesjournal()
            )
            journal, neu = tagesjournal_ergaenzen(
                journal_alt, tabellen["ledger"], config, heute, ab_tag=betriebsbeginn)
            befunde_journal = validate_tagesjournal(
                journal, tabellen["ledger"], config, heute, ab_tag=betriebsbeginn)
            if befunde_journal:
                raise TagesjournalError("; ".join(befunde_journal[:5]))
            zeile["tagesjournal"] = {
                "gebucht": int(len(neu)),
                "je_ereignis": {
                    str(k): int(v) for k, v in sorted(neu["ereignis"].value_counts().items())
                } if len(neu) else {},
                "neugeschaeft": int((neu["herkunft"] == "neugeschaeft").sum()) if len(neu) else 0,
                "zeilen_gesamt": int(len(journal)),
            }
            # Bestandszahlen am gefuehrten Tag.
            from rechner_pipeline.bestand.fuehrung import bestand_am

            schnitt = bestand_am(tabellen["portfolio"], tabellen["historie"], heute)
            uebernommene = set(zeile.pop("_uebernommene_policen"))
            zeile["bestand"] = {
                "in_force": int(len(schnitt)),
                "je_produkt": {
                    str(k): int(v) for k, v in sorted(schnitt["produkt"].value_counts().items())
                },
                "uebernommen_in_force": int(schnitt["police_id"].isin(uebernommene).sum()),
                "policiert_beginn_folgt": int(
                    (tabellen["portfolio"]["insurance_start"] > pd.Timestamp(heute)).sum()),
            }
            # Monatsabschluesse fuer jeden Monatsersten im gefuehrten Fenster.
            # Festgeschrieben wird jeder; den Bestandsbericht (jederzeit neu
            # renderbar) bekommt nur der juengste — beim Nachholen vieler
            # Monate waere alles andere Rechenzeit fuer Seiten, die niemand
            # liest. Mit teilbestand_getrennt kommt je Uebernahme ein
            # Bericht ueber ihren Teilbestand dazu (Konzept, Abschnitt 6).
            manifest_hash = _datei_hash(arbeit / MANIFEST_DATEI)
            teilbestaende: Dict[str, List[int]] = zeile.pop("_teilbestaende")
            abschluesse: List[Dict[str, Any]] = []
            stichtage = monatserste_in(
                letzter or (betriebsbeginn - _dt.timedelta(days=1)), heute)
            for stichtag in stichtage:
                pfad = abschluss_pfad(ablage.abschluesse, stichtag)
                if pfad.exists():
                    abschluesse.append({"stichtag": stichtag.isoformat(), "datei": pfad.name,
                                        "neu": False})
                    continue
                geschrieben = schreibe_abschluss(
                    tabellen["portfolio"], tabellen["historie"], config, stichtag,
                    ablage.abschluesse, scheiben=tabellen["scheiben"],
                    merkmale=tabellen.get("merkmale"),
                )
                eintrag: Dict[str, Any] = {
                    "stichtag": stichtag.isoformat(), "datei": geschrieben.name,
                    "sha256": _datei_hash(geschrieben), "neu": True,
                }
                if stichtag == stichtage[-1]:
                    bericht = _bericht(
                        tabellen, config, stichtag, heute,
                        ablage.berichte / f"bestandsbericht_{stichtag.isoformat()}.html",
                        tabellen["sha256"]["portfolio"],
                    )
                    eintrag["bericht"] = bericht.name
                    if config.tagesbetrieb.teilbestand_getrennt and teilbestaende:
                        eintrag["teilbestaende"] = []
                        for fall, policen in sorted(teilbestaende.items()):
                            teil = _bericht(
                                _teilbestand(tabellen, policen), config, stichtag, heute,
                                ablage.berichte
                                / f"bestandsbericht_{stichtag.isoformat()}_teilbestand-{fall}.html",
                                tabellen["sha256"]["portfolio"],
                                titel=f"Teilbestand {fall} (uebernommen) zum {stichtag.isoformat()}",
                            )
                            eintrag["teilbestaende"].append({"fall": fall, "bericht": teil.name})
                abschluesse.append(eintrag)
            zeile["abschluesse"] = abschluesse
            # Journal schreiben, dann den Stand uebernehmen.
            ablage.journal.mkdir(parents=True, exist_ok=True)
            write_portfolio(journal, ablage.tagesjournal_pfad)
            zeile["tagesjournal"]["sha256"] = _datei_hash(ablage.tagesjournal_pfad)
            _uebernehmen(ablage)
            zeile["manifest_sha256"] = manifest_hash
            zeile["uebernommen"] = True
    except (EreignisError, NeugeschaeftError, TagesjournalError, AbschlussError,
            UebernahmeError, ManifestError, ValueError) as exc:
        zeile.pop("_uebernommene_policen", None)
        zeile.pop("_teilbestaende", None)
        zeile["fehler"] = f"{type(exc).__name__}: {exc}"
        if exit_code == EXIT_OK:
            exit_code = EXIT_NACHLAUF if "pb1" in zeile else EXIT_USAGE
    _anfuegen(ablage.protokoll_pfad, zeile)
    return exit_code, zeile


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.tageslauf",
        description="Den heutigen Tag der PLV fuehren: Neugeschaeft, Fortschreibung, "
        "Tagesjournal, Wache P-B1, Monatsabschluss, Protokoll. Idempotent, "
        "deterministisch; verpasste Tage werden nachgeholt.",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument(
        "--heute", default=None,
        help="Der zu fuehrende Kalendertag (ISO); Default: Kalendertag des Aufrufs.",
    )
    parser.add_argument(
        "--image-digest", dest="image_digest", default=None,
        help="Digest des Container-Images fuer das Protokoll (Default: "
        "Umgebungsvariable PLV_IMAGE_DIGEST).",
    )
    ns = parser.parse_args(argv)
    try:
        heute = _dt.date.fromisoformat(ns.heute) if ns.heute else _dt.date.today()
    except ValueError as exc:
        print(f"tageslauf: --heute: {exc}", file=sys.stderr)
        return EXIT_USAGE
    ablage = Ablage(Path(ns.stand))
    digest = ns.image_digest or os.environ.get("PLV_IMAGE_DIGEST") or None
    try:
        code, zeile = tageslauf(ablage, heute, image_digest=digest)
    except TageslaufError as exc:
        print(f"tageslauf: {exc}", file=sys.stderr)
        return EXIT_USAGE
    if code == EXIT_OK:
        print(
            f"tageslauf: {heute.isoformat()} gefuehrt"
            + (f" (nachgeholt: {len(zeile['nachgeholt'])} Tage)" if zeile["nachgeholt"] else "")
            + f", {zeile['tagesjournal']['gebucht']} Buchungen, "
            f"{zeile['bestand']['in_force']} Vertraege in Kraft, "
            f"{len(zeile.get('abschluesse', []))} Monatsabschluesse -> {ablage.stand}",
            file=sys.stderr,
        )
    elif code == EXIT_WACHE_ROT:
        print(
            f"tageslauf: WACHE ROT am {heute.isoformat()} — Stand nicht uebernommen, "
            f"{len(zeile['pb1']['befunde'])} Befund(e): "
            + "; ".join(zeile["pb1"]["befunde"][:3]),
            file=sys.stderr,
        )
    else:
        print(f"tageslauf: {zeile.get('fehler')} — Stand nicht uebernommen", file=sys.stderr)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
