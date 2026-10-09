"""Vorzeigeseite eines Migrationslaufs bauen — Beobachtungshilfe, kein Pipeline-Teil.

**Wozu.** Ein durchgefuehrter Migrationsfall soll sich zeigen lassen:
was geliefert wurde, was das System daraus gemacht hat, wo entschieden
wurde und wie der Lauf verlief. Dieses Werkzeug baut daraus eine
statische Seite (GitHub Pages).

**Woher die Zahlen kommen.** Aus dem Datenmodell der Falldarstellung
(``falldaten.py``), demselben, das auch der Fallbericht rendert. Die
Seite liest die Fall-Artefakte nicht selbst aus — zwei Leser desselben
Datenraums drifteten auseinander, und dann truegen Seite und Bericht
verschiedene Zahlen fuer denselben Lauf. Was die Seite selbst tut, ist
Veroeffentlichung: Artefakte ueber eine Positivliste kopieren, die
Regie sperren, Provenienz stempeln. Die Artefakte liegen als Belege
unter ``artefakte/`` neben der Seite; jede Zahl des Modells ist dort
nachpruefbar.

**Warum die Artefakte NICHT ins Repo gehoeren.** ADR-002: "Das Repo ist
das System, nicht der Datenraum." ``faelle/`` ist der gitignorierte
Arbeitsbereich, echte Faelle liegen ausserhalb. Eine veroeffentlichte
Seite ist kein Datenraum, sondern eine Darstellung — sie wird als
datierter Schnappschuss publiziert, nicht nach ``main`` committet. Die
QUELLE der Seite (dieses Werkzeug, die Fallbeschreibung) ist
versioniert; der Schnappschuss ist es nicht.

**Drei Dinge, die dieses Werkzeug erzwingt, statt sie zu empfehlen:**

*Es laesst die Regie nicht durch.* ``simulation/`` und ``docs-local/``
enthalten die Aufloesungen des Vorfuehrfalls — welche Fehler absichtlich
eingebaut sind und wie die Beispieldaten entstehen. Wer das
mitveroeffentlicht, verschenkt die Vorfuehrung. Das Werkzeug bricht ab,
statt zu warnen.

*Es kennzeichnet die Simulation.* Auf der Seite stehen die
Entscheid-Snapshots des Falls. Ein Aussenstehender muss auf den ersten
Blick erkennen, dass ihr Schluessel-Fingerabdruck der eines
Simulationsschluessels ist und kein Verantwortlicher Aktuar dahinter
steht. Der Fingerabdruck steht ohnehin in jedem Snapshot; die Seite
erklaert ihn.

*Es behauptet keine Signaturpruefung.* Dieses Werkzeug hat keinen
Schluesselring (T19-02). Es prueft Schema, Selbstadressierung und
Dateiname der Snapshots — nicht die HMAC-Signatur. Die Seite sagt
deshalb "Snapshot strukturell geprueft, Signatur hier nicht
verifiziert" und nennt nichts "signiert" oder "gezeichnet", was sie
nicht verifiziert hat (Review T20-02).

*Es verschweigt keine Luecke.* Fehlt dem Fall ein Pflichtabschnitt,
steht das auf der Seite selbst, und das Werkzeug endet mit Exit 3 —
geschrieben, aber unvollstaendig (Review T20-03).

*Es stempelt die Provenienz.* Welcher Systemstand, welche Lieferung mit
welchen Pruefsummen, welche Schluesselrolle. Dieselbe Disziplin, die das
Repo intern fuehrt, gilt fuer die Veroeffentlichung.

Aufruf::

    python werkzeuge/falldaten.py --fall faelle/baldrian-uebernahme \\
        --abzug <abzug-1>.csv --abzug <abzug-2>.csv --out runs/falldaten.json
    python werkzeuge/vorzeigeseite.py --fall faelle/baldrian-uebernahme \\
        --daten runs/falldaten.json --out vorzeige/ [--verlauf verlauf.md]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import bereinigung
import darstellung
import grafik

#: Verzeichnisse, aus denen NICHTS auf die Seite gelangen darf. Sie
#: tragen die Aufloesungen des Vorfuehrfalls. Die Liste MUSS alle
#: Spielleiter-Bereiche aus dev-docs/regie.md tragen — dort steht die
#: Zusicherung, die dieser Code halten muss ("die Vorzeigeseite bricht
#: ab, wenn etwas davon in die Veroeffentlichung geriete"). ``regie/``
#: fehlte bis zum externen Review T19-01 und war damit die einzige
#: Zusicherung ohne Deckung.
REGIE = ("simulation", "docs-local", "regie")

#: Dateien, die auch einzeln nie veroeffentlicht werden — der Name
#: allein genuegt, egal wo sie liegen.
REGIE_DATEIEN = ("MANIPULATIONEN.md", "NOTIZEN.md")

#: Was von einem Fall auf die Seite gehoert, sagt seit dem 03.10.2026 die
#: Belegkette (``falldaten.belegkette``): jede Datei, die eine Station
#: traegt. Vorher stand hier eine Positivliste von Ordnern, und ein neuer
#: Beleg (der Aenderungsbeleg des Kerns, der Fallauftrag, die Zugangsprobe)
#: fehlte, bis ihn jemand nachtrug. Die Regie-Sperre gilt weiter fuer jede
#: Datei; eine Datei, die sich seit der Erhebung der Kette geaendert hat,
#: bricht den Bau.


#: Minimale Jekyll-Konfiguration der veroeffentlichten Seite. Das Thema
#: rendert Tabellen und Code lesbar; die Artefakte werden ausdruecklich
#: NICHT von Jekyll angefasst, damit JSON und CSV unveraendert
#: herunterladbar bleiben.
JEKYLL = """theme: jekyll-theme-cayman
title: Migrationsfall — Vorführung
description: >-
  Vorfuehrung einer agentischen Bestandsmigration. Erfundene Unternehmen,
  synthetische Vertraege, Entscheid-Snapshots mit dem Fingerabdruck eines
  Simulationsschluessels (Signatur auf dieser Seite nicht verifiziert).
include:
  - artefakte
keep_files:
  - artefakte
"""


class VeroeffentlichungFehler(RuntimeError):
    """Etwas darf nicht auf die Seite — fail-fast statt Warnung."""


def _pruefe_regie(pfad: Path) -> None:
    """Abbrechen, wenn ein Pfad in die Regie zeigt.

    Die Spielleiter-Bereiche sind Verzeichnisse ``simulation/``,
    ``docs-local/`` und ``regie/``. Einzige Ausnahme: ``docs/simulation/``
    ist keine Regie, sondern versionierte Dokumentation (Fachkonzept des
    Tagesbetriebs, Erfahrungsannahmen) — genau dieses eine Paar ist
    ausgenommen, jedes andere Vorkommen sperrt.
    """
    teile = pfad.resolve().parts
    for i, teil in enumerate(teile):
        if teil in REGIE and not (teil == "simulation" and i > 0 and teile[i - 1] == "docs"):
            raise VeroeffentlichungFehler(
                f"{pfad} liegt unter {teil!r}. Dort stehen die "
                "Aufloesungen des Vorfuehrfalls; sie duerfen nicht "
                "veroeffentlicht werden."
            )
    if pfad.name in REGIE_DATEIEN:
        raise VeroeffentlichungFehler(
            f"{pfad.name} ist ein Regie-Dokument und wird nicht "
            "veroeffentlicht, egal wo es liegt."
        )


def _systemstand(repo: Path) -> Dict[str, str]:
    def git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=repo, capture_output=True, text=True,
                check=True).stdout.strip()
        except (OSError, subprocess.CalledProcessError):
            return "unbekannt"
    return {
        "commit": git("rev-parse", "HEAD"),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "sauber": "ja" if not git("status", "--porcelain") else "nein",
    }


def _lies_json(pfad: Path) -> Optional[Any]:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


#: Was jede aktuarielle Abnahme prueft — Beschriftung der Darstellung.
#: Die Zahlen dazu kommen aus dem Modell, die Worte bleiben hier.
ABNAHMEN = {
    "A-M1": ("Stichtagstest",
             "Übernahmezeitpunkt und nächster Vertragsstichtag"),
    "A-M2": ("Verlaufstest",
             "fünf und zehn Jahre nach der Übernahme, und der Ablauf"),
    "A-M3": ("Geschäftsvorfalltest",
             "je Vorfall die Änderung des Deckungskapitals"),
}


def _zahl(wert: Any, dez: int = 0) -> str:
    return grafik._zahl(wert, dez)


def _urteilswort(urteil: Any) -> str:
    if urteil is True:
        return "bestanden"
    if urteil is False:
        return "**nicht bestanden**"
    return "*(ohne Urteil)*"


def _artefakt_link(fall: Path, ref: Optional[str],
                   kopiert: set) -> Optional[str]:
    """Einen fallrelativen Modell-Verweis in einen Seitenlink uebersetzen.

    Das Modell LISTET Verweise nur; ob einer die Seite erreicht,
    entscheidet die Seite selbst: Die Regie-Sperre prueft auch hier
    (doppelt gehalten, weil ein Fehler die Vorfuehrung verschenkt), und
    verlinkt wird nur, was die Positivliste tatsaechlich kopiert hat —
    ein Link auf eine nicht kopierte Datei waere eine Behauptung ohne
    Artefakt daneben.
    """
    if not ref:
        return None
    _pruefe_regie(fall / ref)
    rel = ("lieferung/" + ref[len("eingang/"):]) if ref.startswith("eingang/") else ref
    for ziel in (f"artefakte/{rel}", f"artefakte/{rel}.txt", f"artefakte/{rel}.html"):
        if ziel in kopiert:
            return ziel
    return None


#: So viele Datenzeilen zeigt die Web-Vorschau einer gelieferten CSV.
VORSCHAU_ZEILEN = 100

VORSCHAU_STIL = (
    "body{margin:0;font:13px ui-monospace,monospace;color:#1b1e1c;"
    "background:#f8f8f6}main{padding:1rem;overflow-x:auto}"
    "p{font-family:system-ui}table{border-collapse:collapse}"
    "th,td{border:1px solid #cfd3cc;padding:.15rem .5rem;text-align:left;"
    "white-space:nowrap}th{background:#eceee9}")


def _csv_vorschau(quelle: Path) -> str:
    """Die ersten Zeilen einer gelieferten CSV als HTML-Ansicht.

    Die Vorschau ist ANSCHAUUNG, kein Beleg: Der Beleg bleibt das
    Register der Lieferung mit Pruefsumme. So laesst sich eine grosse
    Datei ansehen, ohne sie vollstaendig zu veroeffentlichen.
    """
    zeilen: List[List[str]] = []
    gesamt = 0
    with quelle.open(encoding="utf-8", errors="replace",
                     newline="") as datei:
        for i, zeile in enumerate(csv.reader(datei, delimiter=";")):
            gesamt = i + 1
            if i <= VORSCHAU_ZEILEN:
                zeilen.append(zeile)
    kopf, rumpf = (zeilen[0], zeilen[1:]) if zeilen else ([], [])
    z = ['<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
         f"<title>{html.escape(quelle.name)} — Vorschau</title>"
         f"<style>{VORSCHAU_STIL}</style></head><body><main>"
         f"<p><b>{html.escape(quelle.name)}</b> — Vorschau der ersten "
         f"{len(rumpf)} von {max(gesamt - 1, 0)} Datenzeilen. Der Beleg "
         "ist das Register der Lieferung mit Prüfsumme.</p>"
         "<table><thead><tr>"]
    z += [f"<th>{html.escape(t)}</th>" for t in kopf]
    z.append("</tr></thead><tbody>")
    for zeile in rumpf:
        z.append("<tr>" + "".join(
            f"<td>{html.escape(t)}</td>" for t in zeile) + "</tr>")
    z.append("</tbody></table></main></body></html>")
    return "".join(z)


BERICHT_STIL = (
    "body{margin:0;font:15px/1.55 system-ui,sans-serif;color:#1b1e1c;"
    "background:#f8f8f6}main{max-width:60rem;margin:0 auto;padding:2rem "
    "1.2rem 4rem}h1{font:600 1.7rem/1.2 Georgia,serif}"
    "h2{font:600 1.2rem/1.25 Georgia,serif;margin-top:2rem}"
    "table{border-collapse:collapse;font-size:.88rem;width:100%}"
    "th,td{border:1px solid #cfd3cc;padding:.3rem .6rem;text-align:left;"
    "vertical-align:top}th{background:#eceee9}"
    "code{font:.85em ui-monospace,monospace;background:#e7eae4;"
    "padding:.05em .3em;border-radius:3px}"
    "p.fuss{color:#5f6663;font-size:.8rem;margin-top:2.5rem}")


def _uebersetzungsbericht(modell: Dict[str, Any]) -> str:
    """Eigenstaendige Web-Ansicht der Datenuebersetzung.

    Der Uebersetzungsakt verdient einen eigenen Bericht VOR den
    Abnahmen. Solange der Fall-Lauf ihn nicht selbst als Artefakt
    erzeugt, leitet die Seite ihn aus Spezifikation und Ergebnis des
    Falls ab — dieselben Daten, eigene Darstellung; die Entscheid-
    Artefakte des Falls bleiben unangetastet.
    """
    t = modell.get("transformation") or {}
    e = html.escape
    name = str((modell.get("fall") or {}).get("name") or "?")
    z = ['<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">',
         f"<title>Übersetzungsbericht — {e(name)}</title>",
         f"<style>{BERICHT_STIL}</style></head><body><main>",
         f"<h1>Übersetzung der Daten — {e(name)}</h1>",
         f"<p><code>{e(str(t.get('quelle') or '?'))}</code> — "
         f"abgebildet auf {t.get('anzahl_zielfelder')} Zielfelder"
         + (f"; {t.get('zeilen_quelle')} Zeilen hinein, "
            f"{t.get('zeilen_ziel')} heraus" if t.get("zeilen_quelle")
            else "") + ".</p>",
         "<h2>Feldabbildung</h2><table><thead><tr><th>Quelle</th>"
         "<th>Ziel</th><th>Umsetzung</th><th>Kodierung</th>"
         "<th>Begründung</th></tr></thead><tbody>"]
    for f in t.get("felder") or []:
        quellen = ", ".join(f"<code>{e(q)}</code>"
                            for q in f.get("quellen") or [])
        art = f.get("berechnung") or (
            "Kodierung" if f.get("kodierung") else "übernommen")
        kodierung = ", ".join(
            f"{e(str(k))} → {e(str(v))}"
            for k, v in sorted((f.get("kodierung") or {}).items()))
        z.append(f"<tr><td>{quellen}</td>"
                 f"<td><code>{e(str(f.get('ziel')))}</code></td>"
                 f"<td>{e(str(art))}</td><td>{kodierung}</td>"
                 f"<td>{e(str(f.get('begruendung') or ''))}</td></tr>")
    z.append("</tbody></table>")

    nicht = t.get("nicht_uebernommen") or []
    if nicht:
        z.append(f"<h2>Ausdrücklich nicht übernommen ({len(nicht)})</h2><ul>")
        for eintrag in nicht:
            spalten = ", ".join(f"<code>{e(q)}</code>"
                                for q in eintrag.get("quellen") or [])
            grund = e(eintrag.get("begruendung") or "OHNE BEGRÜNDUNG")
            z.append(f"<li>{spalten} — {grund}</li>")
        z.append("</ul>")
    stumm = t.get("stumm_weggelassen") or []
    if stumm:
        z.append("<h2>Weder abgebildet noch verworfen</h2><p>"
                 + ", ".join(f"<code>{e(s)}</code>" for s in stumm)
                 + " — über diese Spalten hält die Spezifikation nichts "
                 "fest.</p>")
    konflikte = t.get("konflikte") or []
    if konflikte:
        z.append("<h2>Menschlich entschiedene Übersetzungsfragen "
                 f"({len(konflikte)})</h2><ul>")
        for k in konflikte:
            z.append(f"<li><code>{e(str(k.get('quellspalte')))}</code> — "
                     f"{e(str(k.get('frage') or ''))} Entscheidung: "
                     f"{e(str(k.get('entscheidung')))}</li>")
        z.append("</ul>")
    for anmerkung in t.get("anmerkungen") or []:
        z.append(f"<p>{e(str(anmerkung))}</p>")
    belege = ", ".join(f"<code>{e(Path(ref).name)}</code>"
                       for ref in t.get("gelesen_aus") or [])
    z.append(f'<p class="fuss">Abgeleitete Ansicht aus den gebundenen '
             f"Fall-Artefakten {belege} — sie liegen im Artefakt-Baum "
             "des Berichts bei.</p></main></body></html>")
    return "".join(z)


def _lieferung_ansichten(fall: Path, ziel: Path,
                         quellen: List[Dict[str, Any]],
                         kopiert: List[str]) -> Dict[str, str]:
    """Je registrierter Quelle eine anklickbare Ansicht ableiten.

    CSV-Dateien erreichen die Seite als Vorschau der ersten Zeilen;
    alles Uebrige wird unveraendert beigelegt — PDF zeigt der Browser
    direkt, Office-Dateien laedt er herunter.
    """
    aus: Dict[str, str] = {}
    for q in quellen:
        name = str(q.get("datei") or "")
        pfad = fall / "eingang" / name
        if not name or not pfad.is_file():
            continue
        _pruefe_regie(pfad)
        verzeichnis = ziel / "artefakte" / "lieferung"
        verzeichnis.mkdir(parents=True, exist_ok=True)
        # copy2 uebernimmt den Schreibschutz des unantastbaren Eingangs;
        # ein Folge-Bau muss sein eigenes Ziel trotzdem ersetzen duerfen.
        for altlast in (verzeichnis / name, verzeichnis / f"{name}.html",
                        verzeichnis / f"{name}.txt"):
            altlast.unlink(missing_ok=True)
        if pfad.suffix.lower() == ".csv":
            ansicht = verzeichnis / f"{name}.html"
            ansicht.write_text(_csv_vorschau(pfad), encoding="utf-8")
        elif pfad.suffix.lower() == ".md":
            # Eine .md unter artefakte/ wuerde Jekyll rendern und die
            # Vorschau ihren Link umschreiben. Die Originaldatei wird
            # deshalb unter .txt beigelegt: gleiche Bytes, roher Anblick.
            ansicht = verzeichnis / f"{name}.txt"
            shutil.copy2(pfad, ansicht)
        else:
            ansicht = verzeichnis / name
            shutil.copy2(pfad, ansicht)
        rel = str(ansicht.relative_to(ziel))
        kopiert.append(rel)
        aus[name] = rel
    return aus


def _kopiere(fall: Path, ziel: Path, modell: Optional[Dict[str, Any]] = None
             ) -> Tuple[List[str], Dict[str, Any]]:
    """Jede Datei, die die Belegkette einer Station zuordnet, nach
    ``artefakte/`` spiegeln — die Lieferung ausgenommen, sie kommt als
    Ansicht nach ``artefakte/lieferung/``. Markdown liegt als ``.md.txt``:
    dieselben Bytes, aber kein Seiten-Generator rendert sie als Seite.

    Dabei die Stufe :mod:`bereinigung` (Entscheid des Maintainers,
    03.10.2026): Hostpfade nach Regel durch benannte Platzhalter ersetzt und
    im Manifest ``artefakte/bereinigung.json`` ausgewiesen; ein Entscheid-
    Snapshot wird nie veraendert — ein ueberholter mit Befund bleibt
    unveroeffentlicht, ein geltender mit Befund haelt den Bau an. Zurueck:
    die kopierten Seitenpfade und der Bericht der Stufe."""
    import hashlib

    kette = ((modell or {}).get("belegkette") or {}).get("dateien") or {}
    entscheide = {e.get("snapshot_datei"): e
                  for e in ((modell or {}).get("kette") or {}).get("entscheide") or []}
    regelsatz = bereinigung.regeln(fall)
    kopiert: List[str] = []
    bericht: Dict[str, Any] = {
        "regeln": [{"platzhalter": p, "steht_fuer": b} for p, b, _ in regelsatz],
        "bereinigt": [], "zurueckgehalten": []}
    for rel, e in sorted(kette.items()):
        if not (e.get("station") or e.get("quelle_der_darstellung")) or rel.startswith("eingang/"):
            continue
        quelle = fall / rel
        if ".." in Path(rel).parts or not quelle.is_file():
            continue
        _pruefe_regie(quelle)
        daten = quelle.read_bytes()
        if hashlib.sha256(daten).hexdigest() != e.get("sha256"):
            raise VeroeffentlichungFehler(
                f"{rel} hat sich seit der Erhebung der Belegkette geaendert — "
                "das Modell mit werkzeuge/falldaten.py neu erzeugen")
        name = rel + ".txt" if rel.endswith(".md") else rel
        veroeffentlicht = daten
        if rel.startswith("entscheide/"):
            try:
                urteil = bereinigung.snapshot_urteil(rel, daten, entscheide.get(rel))
            except ValueError as exc:
                raise VeroeffentlichungFehler(str(exc)) from exc
            if urteil == "zurueckhalten":
                bericht["zurueckgehalten"].append({
                    "original": rel, "sha256": e.get("sha256"),
                    "grund": "überholter Entscheid-Snapshot mit einer vertraulichen "
                             "Angabe"})
                continue
        else:
            veroeffentlicht, ersetzt = bereinigung.bereinige(daten, regelsatz)
            if ersetzt:
                if not bereinigung.ist_text(rel):
                    raise VeroeffentlichungFehler(
                        f"{rel} traegt einen Hostpfad, ist aber kein Text — eine Ersetzung "
                        "zerbraeche das Format; die Datei zurueckhalten oder den Produzenten "
                        "beheben")
                bericht["bereinigt"].append({
                    "datei": f"artefakte/{name}", "original": rel,
                    "sha256_original": e.get("sha256"),
                    "gebunden_von": bereinigung.bindung(e),
                    "sha256_veroeffentlicht": hashlib.sha256(veroeffentlicht).hexdigest(),
                    "ersetzungen": ersetzt})
        unterziel = ziel / "artefakte" / name
        unterziel.parent.mkdir(parents=True, exist_ok=True)
        unterziel.write_bytes(veroeffentlicht)
        kopiert.append(f"artefakte/{name}")
    (ziel / "artefakte").mkdir(parents=True, exist_ok=True)
    bericht["weiterleitungen"] = _weiterleitungen(ziel / "artefakte")
    (ziel / "artefakte" / bereinigung.MANIFEST).write_bytes(
        bereinigung.manifest(bericht["bereinigt"], bericht["zurueckgehalten"], regelsatz,
                             bericht["weiterleitungen"]))
    kopiert.append(f"artefakte/{bereinigung.MANIFEST}")
    return kopiert, bericht


def _weiterleitungen(artefakte: Path) -> List[Dict[str, str]]:
    """Weiterleitungen fuer Verweise eines Belegs, die vom Fallordner aus
    geschrieben sind.

    Der Browser loest einen relativen Verweis vom Ordner des Belegs aus auf;
    der Bericht der Migrationsabnahme von Fall 3 schreibt seine Verweise auf
    die Bestandsberichte daneben aber vom Fallordner aus, sie liefen ins
    Leere. Der Beleg bleibt Byte fuer Byte. Wo ein Verweis ins Leere ginge,
    das Ziel vom Fallordner aus aber auf der Seite liegt, liegt danach eine
    Weiterleitung (:func:`bereinigung.weiterleitung`); das Manifest nennt sie,
    damit die Pruefungen sie vom Beleg unterscheiden."""
    aus: List[Dict[str, str]] = []
    for beleg in sorted(artefakte.rglob("*.html")):
        text = beleg.read_text(encoding="utf-8", errors="replace")
        for a, b in re.findall(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)')""", text):
            pfad = urllib.parse.unquote(html.unescape(a or b).strip().split("#")[0].split("?")[0])
            if not pfad or pfad.startswith("/") or re.match(r"^[a-z][a-z0-9+.-]*:", pfad, re.I):
                continue
            dort = Path(os.path.normpath(beleg.parent / pfad))
            gemeint = Path(os.path.normpath(artefakte / pfad))
            if (dort.exists() or not gemeint.is_file()
                    or artefakte not in dort.parents or artefakte not in gemeint.parents):
                continue
            ziel = Path(os.path.relpath(gemeint, dort.parent)).as_posix()
            dort.parent.mkdir(parents=True, exist_ok=True)
            dort.write_bytes(bereinigung.weiterleitung(ziel))
            aus.append({"datei": "artefakte/" + dort.relative_to(artefakte).as_posix(),
                        "ziel": ziel,
                        "verweis_aus": "artefakte/" + beleg.relative_to(artefakte).as_posix()})
    return aus


GEVO_TITEL = {"ERH": "Erhöhung", "PEX": "Beitragsfreist.",
              "RED": "Absetzung", "STO": "Rückkauf",
              "TOD": "Todesfall", "ABL": "Ablauf"}
FELD_TITEL = {"zins": "Rechnungszins", "tafel": "Sterbetafel",
              "beta1": "Inkassokostensatz"}
SCHICHT_TITEL = {"ohne_vorgeschichte": "ohne Vorgeschichte",
                 "dynamik": "mit Erhöhungsserie",
                 "beitragsfrei": "beitragsfrei gestellt",
                 "reduziert": "mit Herabsetzung"}
STATUS_TITEL = {"POL": "beitragspflichtig", "PEX": "beitragsfrei",
                "BU": "BU-Leistung"}


def _herkunft(modell: Dict[str, Any], gruppe: str) -> str:
    """Woraus ein Abschnitt gelesen wurde — das Mikromuster der Herkunft.

    Nach der dritten Zahl hoert der Leser auf zu pruefen, weil er
    gesehen hat, dass immer etwas dransteht.
    """
    quellen = (modell.get(gruppe) or {}).get("gelesen_aus") or []
    if not quellen:
        return ""
    return "<small>Gelesen aus " + ", ".join(f"`{q}`" for q in quellen) + "</small>"


def _lesart_text(feld: Any, wert: Any) -> str:
    if feld == "zins" and isinstance(wert, (int, float)) and float(wert) < 1:
        return f"{float(wert) * 100:.2f} %".replace(".", ",")
    return str(wert)

def _pruefstand(e: Dict[str, Any]) -> str:
    """Was DIESE Seite ueber einen Snapshot festgestellt hat — und was nicht.

    T19-02/T20-02: Ohne Schluesselring ist die Signatur eine Behauptung der
    Datei. Die Seite nennt nur verifizierte Snapshots "gezeichnet"; alles
    andere heisst beim Namen: strukturell geprueft, Signatur nicht
    verifiziert. Ein Snapshot mit Befund belegt nichts.
    """
    if e.get("strukturell_verifiziert") is False:
        return "**Snapshot mit Befund** — belegt nichts"
    if e.get("signatur_verifiziert") is True:
        return "Signatur verifiziert, gezeichnet"
    return "strukturell geprüft, Signatur hier nicht verifiziert"


def _signaturhinweis(entscheide: List[Dict[str, Any]]) -> List[str]:
    verifiziert = sum(1 for e in entscheide if e.get("signatur_verifiziert") is True)
    z: List[str] = []
    if verifiziert == len(entscheide):
        z.append("Alle Annahmen sind mit dem extern verwahrten Schlüssel")
        z.append("signiert und hier verifiziert; der Fingerabdruck weist die")
        z.append("**Schlüsselrolle** nach, nicht die Identität einer natürlichen")
        z.append("Person.")
    else:
        z.append("Das Schlüsselmaterial liegt außerhalb des Falls, und diese")
        z.append("Seite hat es nicht: Sie prüft Schema, Selbstadressierung und")
        z.append("Dateiname jedes Snapshots, **nicht die HMAC-Signatur**. Der")
        z.append("Fingerabdruck in der Tabelle ist eine Angabe der Datei, kein")
        z.append("Nachweis einer Zeichnung. Ein Fall kann seine eigene")
        z.append("menschliche Freigabe nicht behaupten — genau deshalb nennt")
        z.append("diese Seite nichts gezeichnet, was sie nicht verifiziert hat.")
    return z


def _luecke_satz(l: Dict[str, Any], modell: Dict[str, Any]) -> str:
    """Eine Luecke des Falls als Satz. Die des Betriebsstands (T22-05) kennt
    die Seite beim Namen; jede andere steht mit ihrer Wirkung da."""
    if l.get("gruppe") == "betrieb" and "Image-Digest" in str(l.get("feld")):
        b = modell.get("betrieb") or {}
        kern = (b.get("provenienz") or {}).get("kern_version")
        stand = darstellung.datum(b.get("stand")) if b.get("stand") else None
        return ("Für die Fortschreibung des Bestands" + (f" zum {stand}" if stand else "")
                + " haben wir die Version des Rechenkerns" + (f" ({kern})" if kern else "")
                + " und die Konfiguration festgehalten, nicht aber die technische Umgebung, "
                  "in der das Programm lief.")
    wirkung = str(l.get("wirkung") or "").strip()
    return f"Im Fall fehlt: {l.get('was')}." + (f" {wirkung}" if wirkung else "")


def _grenzen(modell: Dict[str, Any], unterseite: bool) -> str:
    """Das Kleingedruckte der Fallseite — EINE Stelle fuer alles, was die
    Zahlen einschraenkt (Maintainer 06.10.2026: verstaendlich oder weg, und
    klein statt grosser Bloecke): die Abgrenzungen des Modells als ganze
    Saetze, die Luecken des Falls und der Verweis auf den Abschlussbericht.
    Fehlendes steht damit SICHTBAR auf der Seite, nicht nur auf stderr
    (T20-03); der Bau endet bei einer Luecke weiter mit Exit 3."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    saetze = [a.get("satz") or (str(a.get("was") or "")
                                + (f" — {a['zahlen']}" if a.get("zahlen") else ""))
              for a in modell.get("abgrenzungen") or []]
    u = modell.get("umbau") or {}
    for befund in u.get("befunde") or []:
        grund = u.get("ueberschreitung_begruendet")
        saetze.append(f"Messung des Umbaus: {befund}"
                      + (f" (begründet: „{grund}“)." if grund else ", ohne Begründung."))
    saetze += [_luecke_satz(l, modell) for l in luecken(modell)]
    absaetze = [f"<p>{html.escape(s, quote=False)}</p>" for s in saetze]
    if not saetze:
        absaetze.append("<p>Die Prüfbelege weisen keine Einschränkung aus.</p>")
    bericht = [d for _, d, t in darstellung.falldokumente(modell) if t == "Abschlussbericht"]
    if unterseite and bericht:
        absaetze.append("<p>Fachliche Einschränkungen, die kein Prüfbeleg trägt — etwa eine "
                        "Datenlücke der abgebenden Gesellschaft —, stehen im "
                        f'<a href="../../{html.escape(bericht[0][:-3])}.html">Abschlussbericht</a>.</p>')
    return '<div class="kleingedruckt">' + "".join(absaetze) + "</div>"

#: Reihenfolge der Agentenrollen in der Tabelle des Aufwands: wie sie im
#: Ablauf auftreten; eine Rolle, die hier fehlt, steht danach, alphabetisch.
AUFWAND_FOLGE = ("programmleitung", "aktuariat", "architektur", "rechenkern", "betrieb")


def _hat_aufwand(modell: Dict[str, Any]) -> bool:
    auf = modell.get("aufwand") or {}
    return bool(auf.get("dauer") or auf.get("agenten"))


def _aufwand_abschnitt(modell: Dict[str, Any], link: Callable[[str], Optional[str]]) -> List[str]:
    """Dauer und Aufwand der Uebernahme, je Rolle — die Vertiefung zu den
    zwei Zeilen der Startseite (Wunsch des Maintainers 05.10.2026). Alles aus
    dem Modell (falldaten.aufwand): die Dauer an den Snapshots gemessen und
    in der Ortszeit des Hauses gezeigt, der Verbrauch aus dem Artefakt, das
    hier als Beleg verlinkt ist."""
    if not _hat_aufwand(modell):
        return []
    from zoneinfo import ZoneInfo
    from falldaten import AUFWAND_DATEI  # noqa: E402 — Nachbarwerkzeug

    auf = modell["aufwand"]
    z = ["# Dauer und Aufwand {#aufwand}", ""]
    dauer = auf.get("dauer")
    if dauer:
        ort = ZoneInfo("Europe/Berlin")
        von = dt.datetime.fromisoformat(dauer["von"]).astimezone(ort)
        bis = dt.datetime.fromisoformat(dauer["bis"]).astimezone(ort)
        minuten = int(dauer["sekunden"]) // 60
        bis_text = (f"am {bis:%d.%m.%Y} um {bis:%H:%M} Uhr" if bis.date() != von.date()
                    else f"um {bis:%H:%M} Uhr")
        z += [f"Vom ersten Fallauftrag am {von:%d.%m.%Y} um {von:%H:%M} Uhr bis zur Zugangsabnahme "
              f"{bis_text}: **{minuten // 60} h {minuten % 60} min**, Wartezeit auf Entscheide "
              "eingeschlossen — gemessen an den Entscheiden A-M6 und A-B2.", ""]
    agenten = auf.get("agenten")
    if agenten:
        je = agenten.get("je_rolle") or {}
        s = agenten["summe"]
        z += ["Den Verbrauch meldet das Modell je Antwort einer Agentenrolle; jede Antwort ist",
              "einmal gezählt. Die Zahlen umfassen den ganzen Fall, auch die Arbeit nach der",
              "Zugangsabnahme. Gelesen wird fast alles aus dem Zwischenspeicher (Cache).", "",
              "| Rolle | Antworten | erzeugt | Cache geschrieben | Cache gelesen |",
              "|---|---:|---:|---:|---:|"]
        for rolle in sorted(je, key=lambda r: (AUFWAND_FOLGE.index(r) if r in AUFWAND_FOLGE
                                               else len(AUFWAND_FOLGE), r)):
            w = je[rolle]
            z.append(f"| {rolle.capitalize()} | {_zahl(w['antworten'])} | {_zahl(w['ausgabe'])} "
                     f"| {_zahl(w['cache_schreiben'])} | {_zahl(w['cache_lesen'])} |")
        z.append(f"| **zusammen** | **{_zahl(s['antworten'])}** | **{_zahl(s['ausgabe'])}** "
                 f"| **{_zahl(s['cache_schreiben'])}** | **{_zahl(s['cache_lesen'])}** |")
        z.append("")
        beleg = link(AUFWAND_DATEI)
        if beleg:
            z += [f"Beleg: [`{Path(AUFWAND_DATEI).name}`]({beleg}).", ""]
    return z


def _bindet_satz(abschluss: Dict[str, Any], entscheide: List[Dict[str, Any]]) -> str:
    """Was der Abschluss-Entscheid bindet — gemessen (``snapshots_gebunden``
    aus falldaten.kette), nicht "alle vorangehenden" behauptet. Ein
    geltender Entscheid VOR der Abschlussabnahme, dessen Snapshot sie nicht
    bindet, wird genannt."""
    gebunden = list(abschluss.get("snapshots_gebunden") or [])
    satz = (f"Der Abschluss-Entscheid bindet {_zahl(abschluss.get('artefakte_gebunden') or 0)} "
            "Artefakte" + (", darunter die Snapshots der Entscheide " + ", ".join(gebunden)
                           if gebunden else "") + ".")
    davor = list(dict.fromkeys(
        str(e.get("gate")) for e in entscheide
        if e.get("geltend") and e.get("gate") != abschluss.get("gate")
        and str(e.get("entschieden_am")) < str(abschluss.get("entschieden_am"))))
    fehlt = [g for g in davor if g not in gebunden]
    if fehlt:
        satz += (" Nicht gebunden " + ("ist der Snapshot von " if len(fehlt) == 1
                                       else "sind die Snapshots von ")
                 + ", ".join(fehlt) + ", obwohl vor der Abschlussabnahme entschieden.")
    return satz


def _entscheide_seite(fall: Path, modell: Dict[str, Any],
                      kopiert: List[str], unterseite: bool,
                      heute: str, stand: Dict[str, Any],
                      bereinigt: Optional[Dict[str, Any]] = None) -> str:
    """Die Entscheid-Snapshots als eigene Seite.

    Sie stand im Fallbericht als Tabelle mit neun Spalten je Snapshot
    und beherrschte die Seite — dreissig Zeilen Kleingedrucktes
    zwischen zwei Abschnitten, die etwas erzaehlen. Der Inhalt ist
    richtig und gehoert zum Beleg; er gehoert nur nicht in den
    Lesefluss. Hier steht er vollstaendig, der Fallbericht verweist
    darauf.
    """
    kette = modell.get("kette") or {}
    entscheide = kette.get("entscheide") or []
    im_artefakt = set(kopiert)

    def link(ref: Optional[str]) -> Optional[str]:
        return _artefakt_link(fall, ref, im_artefakt)

    z: List[str] = []
    z.append("# Die Entscheid-Snapshots der Gates")
    z.append("")
    z.append('<nav class="kopf">'
             + ('<a href="../../">← Startseite</a>'
                '<a href="../">← Bestandsmigrationen</a>'
                '<a href="./">← Die Übernahme</a>' if unterseite
                else '<a href="index.md">← Die Übernahme</a>')
             + "</nav>")
    z.append("")
    z.append("")
    ableitbar = kette.get("finale_kette_ableitbar")
    zurueck: Dict[str, Dict[str, Any]] = {}
    if entscheide:
        if ableitbar:
            in_kette = list(dict.fromkeys(str(e.get("gate")) for e in entscheide
                                          if e.get("in_finaler_kette") and e.get("gate") != "A-M4"))
            z.append("Die **finale Entscheidkette** ist abgeleitet, nicht")
            z.append("kuratiert: Der Abschluss-Snapshot (A-M4) führt "
                     + (f"die Snapshots von {', '.join(in_kette)} als Pflichtbelege (**final**)."
                        if in_kette else "keinen Snapshot eines anderen Entscheids als Pflichtbeleg."))
            z.append("Für die übrigen Gates gilt je Gate der jüngste unversehrte")
            z.append("Entscheid (**geltend**). Frühere, im Lauf überholte")
            z.append("Entscheid-Runden bleiben erhalten — Entscheid-Snapshots werden nie entfernt.")
            abschluss = [e for e in entscheide if e.get("in_finaler_kette") and e.get("gate") == "A-M4"]
            if abschluss:
                z.append(_bindet_satz(abschluss[-1], entscheide))
            z.append("")
        zurueck = {x["original"]: x for x in (bereinigt or {}).get("zurueckgehalten") or []}
        if zurueck:
            z.append(f"{len(zurueck)} überholte{'r' if len(zurueck) == 1 else ''} Snapshot"
                     f"{'' if len(zurueck) == 1 else 's'} "
                     f"{'ist' if len(zurueck) == 1 else 'sind'} nicht veröffentlicht: "
                     "Ein Snapshot wird nie bereinigt — eine Änderung bräche seine Signatur "
                     "und die Verweise der Folgeentscheide —, und "
                     f"{'dieser trägt' if len(zurueck) == 1 else 'diese tragen'} eine vertrauliche "
                     "Angabe. Prüfsumme der Datei: "
                     # Die Pruefsumme steht hier, nicht in der Tabelle: eine
                     # lange Zelle verbreiterte die ganze Spalte ueber den Rand.
                     + "; ".join(f"{e.get('gate')} vom {str(e.get('entschieden_am'))[:10]} "
                                 f"`{zurueck[e['snapshot_datei']].get('sha256')}`"
                                 for e in sorted(entscheide, key=lambda e: str(e.get("entschieden_am")))
                                 if e.get("snapshot_datei") in zurueck) + ".")
            z.append("")
        z.append("| Gate | Entscheid | entschieden am | Status | Rolle | Snapshot | Schlüssel (laut Snapshot) | Prüfstand |")
        z.append("|---|---|---|---|---|---|---|---|")
        for e in sorted(entscheide, key=lambda e: str(e.get("entschieden_am")),
                        reverse=True):
            schl = (f"`{e['schluessel_sha256']}…`"
                    if e.get("schluessel_sha256") else "*(ohne Freigabe-Eintrag)*")
            snap = f"`{e['snapshot_sha256'][:8]}`" if e.get("snapshot_sha256") else "—"
            snaplink = link(e.get("snapshot_datei"))
            if snaplink and e.get("snapshot_sha256"):
                snap = f"[{snap}]({snaplink})"
            status = ("**final**" if e.get("in_finaler_kette")
                      else "**geltend**" if e.get("geltend")
                      else ("überholt" if ableitbar else "—"))
            if e.get("snapshot_datei") in zurueck:
                status = "überholt, nicht veröffentlicht"
            z.append(f"| <span class=\"kennung\">{e['gate']}</span> | {e['entscheid']} "
                     f"| {str(e.get('entschieden_am'))[:10]} | {status} "
                     f"| {e.get('rolle') or '—'} "
                     f"| {snap} | {schl} | {_pruefstand(e)} |")
        z.append("")
        z.extend(_signaturhinweis(entscheide))
    else:
        z.append("*(noch keine Entscheide im Fall)*")
    z.append("")
    if unterseite:
        z.append('<div class="fuss-fiktion">Fiktives Unternehmen — '
                 '<a href="../../hinter-den-kulissen/">Hinter den Kulissen</a></div>')
        z.append("")
    z.append(f"*Diese Seite wurde am {heute} aus dem Systemstand "
             f"`{stand['commit'][:12]}` erzeugt.*")
    z.append("")
    return "\n".join(z) + "\n"
def _fallname_kurz(fallinfo: Dict[str, Any], fall: Path) -> str:
    """Der Fall, wie ein Leser ihn nennt.

    "baldrian-klv-tg2015-lauf2" ist eine Verzeichniskennung; sie steht
    weiter unten bei den Belegen, wo sie hingehoert. Oben steht der Name
    der abgebenden Gesellschaft.
    """
    roh = str(fallinfo.get("name") or fall.name)
    return roh.split("-")[0].capitalize() if "-" in roh else roh


def _seiten(fall: Path, modell: Dict[str, Any], repo: Path,
           kopiert: List[str], verlauf: Optional[str],
           unterseite: bool = False,
           ansichten: Optional[Dict[str, str]] = None,
           bereinigt: Optional[Dict[str, Any]] = None) -> str:
    """Der Fallbericht — in Lesereihenfolge, nicht in Entstehungsreihenfolge.

    Ergebnis mit Massstab zuerst, dann der Widerspruch der Unterlagen als
    Vertrauensgrund, dann Pruefung, Lauf und Zeichnung, dann die
    Bestandteile, dann die Grenzen (das Kleingedruckte, die eine Stelle
    fuer Einschraenkungen und Luecken) und die Belege. Jede Zahl stammt aus dem
    Modell; jede Grafik aus dem Bausteinsatz.
    """
    ansichten = ansichten or {}
    stand = _systemstand(repo)
    # Verweise der Belegseite zurueck auf die Abschnitte der Fallseite.
    index_ref = "./" if unterseite else "index.md"
    fallinfo = modell.get("fall") or {}
    kette = modell.get("kette") or {}
    gates = kette.get("gates") or []
    entscheide = kette.get("entscheide") or []
    lieferung = modell.get("lieferung") or {}
    quellen = lieferung.get("quellen") or []
    a = modell.get("abnahmen") or {}
    abnahmen = a.get("aktuariell") or []
    controlling = a.get("controlling")
    bestand = modell.get("bestand") or {}
    param = modell.get("parameter") or {}
    verankerung = modell.get("verankerung") or {}
    umbau = modell.get("umbau") or {}
    im_artefakt = set(kopiert)
    heute = dt.date.today().isoformat()
    generation = ", ".join(str(g) for g in param.get("generationen") or [])

    def link(ref: Optional[str]) -> Optional[str]:
        return _artefakt_link(fall, ref, im_artefakt)

    # Vorab, damit die Regie-Sperre jeden Modell-Verweis prueft — auch
    # bei einem Fall ohne Abnahmen.
    berichtskacheln = darstellung.berichte(modell, link)
    #: Dieselben Berichte noch einmal, in der Reihenfolge des Wegs — die
    #: Kacheln oben wandern in die Stationen und werden dort verbraucht;
    #: unten steht der Index, damit wer einen bestimmten Bericht sucht
    #: ihn findet, ohne die Seite abzusuchen.
    alle_berichte = list(berichtskacheln)

    def _belege(*stationen: int, titel: str = "Belege dieser Station") -> List[str]:
        """Die Belege dieser Stationen — dort, wo sie entstehen.

        Sie lagen einmal alle zusammen am Fuss der Seite. Wer die
        Lieferung gelesen hatte, musste bis ans Ende blaettern, um den
        gelieferten Bestand zu oeffnen, und dort lagen acht Kacheln ohne
        Bezug nebeneinander. Jede Station nimmt ihre Belege aus dem
        Vorrat; was uebrig bleibt, steht am Schluss.
        """
        treffer = [k for k in berichtskacheln if k.get("station") in stationen]
        if not treffer:
            return []
        for k in treffer:
            berichtskacheln.remove(k)
        return [f"**{titel}**", "", grafik.kacheln(treffer), ""]

    # Die Zeile ueber dem Kopfband stand hier, als die Seite ein Bericht
    # war. Sie ist ein Verzeichnis geworden — und der Chrom-Streifen kam
    # VOR die Ueberschrift, wodurch das Kopfband auseinanderfiel.
    z: List[str] = []
    z.append(f"# Die Übernahme {_fallname_kurz(fallinfo, fall)}")
    z.append("")
    z.append('<nav class="kopf">'
             + ('<a href="../../">← Startseite</a>'
                '<a href="../">← Bestandsmigrationen</a>' if unterseite
                else '<a href="./">← Startseite</a>')
             + "</nav>")
    z.append("")
    kopf = []
    if controlling:
        kopf.append(f"Übernahme zum {darstellung.datum(controlling.get('stichtag_1'))}, "
                    f"Kontrollstichtag {darstellung.datum(controlling.get('stichtag_2'))}")
    if generation:
        kopf.append(f"Tarifgeneration {generation}")
    # Der Systemstand der Entscheide steht bei den Entscheiden, nicht in der
    # Kopfzeile: Fuer den Leser ist er Hintergrund (Maintainer 06.10.2026).
    if kopf:
        z.append(" · ".join(kopf))
        z.append("")
    # Die Seite spricht mit der Stimme des Unternehmens (Entscheid des
    # Maintainers 04.10.2026): Was ein Snapshot ueber Schluesselklasse,
    # Besetzung und Begruendung sagt, steht in ihm selbst. Was die Seite an
    # den Snapshots prueft und was nicht (T19-02), sagt die Seite der
    # Entscheide (_signaturhinweis) — nicht mehr der Kopf des Lesefluss
    # (Maintainer 06.10.2026).
    if fallinfo.get("beschreibung"):
        z.append(str(fallinfo["beschreibung"]))
        z.append("")
    if abnahmen or controlling:
        alle = list(abnahmen) + ([controlling] if controlling else [])
        # urteil ist ein Wahrheitswert (siehe _urteilswort), kein
        # Gate-Status: Ein Vergleich gegen "passed" zaehlt immer null.
        durch = [t for t in alle if t.get("urteil") is True]
        ohne = [t for t in alle if t.get("urteil") is None]
        luecken = int((controlling or {}).get("pruefluecken") or 0)
        abschluss = [e for e in entscheide
                     if e.get("gate") == "A-M4" and e.get("in_finaler_kette")]
        if ohne:
            satz = (f"{_zahl(len(durch))} von {_zahl(len(alle))} Abnahmen "
                    f"bestanden, {_zahl(len(ohne))} ohne Urteil")
        elif len(durch) == len(alle):
            satz = f"Alle {_zahl(len(alle))} Abnahmen bestanden"
        else:
            satz = (f"{_zahl(len(durch))} von {_zahl(len(alle))} Abnahmen "
                    "bestanden, die übrigen **nicht**")
        satz += (f", {_zahl(luecken)} Prüflücken" if luecken
                 else ", keine Prüflücke")
        if abschluss:
            e = abschluss[-1]
            satz += (f"; der Abschluss-Entscheid des Migrationscontrollings "
                     f"({e.get('entscheid')}) liegt vom "
                     f"{darstellung.datum(str(e.get('entschieden_am'))[:10])} vor "
                     f"und bindet {_zahl(e.get('artefakte_gebunden') or 0)} "
                     "Artefakte")
        z.append(f"**Wie es ausging.** {satz}. Was nicht glatt lief, steht")
        z.append("unten bei der Station, an der es geschah; die Zahlen dazu")
        z.append("unter [Was herauskam](#das-ergebnis).")
        z.append("")
        z.append(grafik.kennzahlenband(darstellung.kennzahl_gruppen(modell)))
        z.append("")

    s_lieferung: List[str] = []
    s_widerspruch: List[str] = []
    s_uebersetzung: List[str] = []
    s_stichprobe: List[str] = []
    s_controlling: List[str] = []
    s_bestand: List[str] = []
    s_ergebnis: List[str] = []
    s_umbau: List[str] = []
    s_anlaeufe: List[str] = []
    s_grenzen: List[str] = []
    s_belege: List[str] = []

    # ------------------------------------------ Worum es geht
    # Diese Seite ist die EINZIGE zu diesem Fall. Zuvor lagen Erzaehlung,
    # Zahlen und Belege auf dreizehn Seiten; der Leser sprang zwischen
    # ihnen hin und her und las denselben Vorgang dreimal.
    z.append("Diese Seite erzählt die Übernahme von der Lieferung bis zum")
    z.append("Zugang in die Bücher — Station für Station, und an jeder")
    z.append("Station steht alles, was zu ihr gehört: was geprüft wird,")
    z.append("was in diesem Fall geschah, die Zahlen und die Belege.")
    z.append("")
    if unterseite:
        z.append("**Woran wir uns messen.** Den Maßstab setzen")
        z.append("Aufsichtsrecht und Marktpraxis, nicht wir: jeder Betrag")
        z.append("aus dem eigenen Rechenkern nachgerechnet, jede Abweichung")
        z.append("gegen eine vorher zugesagte Toleranz gemessen, jede")
        z.append("Abnahme von einem Menschen entschieden, nicht von einem")
        z.append("Agenten. Ausführlich unter")
        z.append("[Woran sich eine Bestandsübernahme messen lassen")
        z.append("muss](../massstab.html); wie wir ihn erfüllen, unter")
        z.append("[Bestandsmigrationen](../).")
        z.append("")
    z.extend(_belege(0, titel="Die Ausgangslage"))
    # Alle dreizehn Stationen, auch die ohne Gate: Eine Luecke in der
    # Nummerierung sieht aus wie ein Fehler, und der Lauf hat zu jeder
    # Station etwas zu sagen — Anlaeufe und Urteil stehen in der
    # Gate-Kette.
    lage = darstellung.stationslage(modell)
    if any(x["urteil"] for x in lage):
        z.append("## Der Weg im Überblick {#ueberblick}")
        z.append("")
        if unterseite:
            z.append("Als Schaubild mit beiden Wegen, Tarif und Bestand:")
            z.append("[Der Prozess in dreizehn Stationen](../#prozess).")
            z.append("")
        z.append("| # | Station | Gate | Anläufe | Ergebnis |")
        z.append("|---:|---|---|---:|---|")
        for x in lage:
            gate = f"`{x['gate']}`" if x["gate"] else "—"
            versuche = _zahl(x["versuche"]) if x["versuche"] else "—"
            urteil = {"passed": "bestanden", "failed": "nicht bestanden",
                      None: "kein Gate"}.get(x["urteil"], x["urteil"])
            if x["gezeichnet"]:
                urteil += ", Entscheid liegt vor"
            titel = (f"[{x['titel']}](#{x['abschnitt']})" if x["abschnitt"]
                     else x["titel"])
            z.append(f"| {x['nummer']} | {titel} | {gate} | {versuche} "
                     f"| {urteil} |")
        z.append("")
        ohne_gate = [f"{n} ({t})" for n, t, g in darstellung.WEG_STATIONEN if not g]
        if ohne_gate:
            z.append(("Station " if len(ohne_gate) == 1 else "Stationen ")
                     + ", ".join(ohne_gate)
                     + (" ist ein Arbeitsschritt" if len(ohne_gate) == 1 else " sind Arbeitsschritte")
                     + " ohne eigene Prüfung; geprüft wird davor und danach.")
        z.append("Bei den Abnahmen zählen die Anläufe die Entscheid-Runden —")
        z.append("frühere Runden bleiben erhalten, auch wenn Korrekturen sie")
        z.append("überholt haben.")
        z.append("")
        z.append("Nach den Stationen: [Was herauskam](#das-ergebnis),"
                 + (" [Dauer und Aufwand](#aufwand)," if _hat_aufwand(modell) else ""))
        z.append("[Was sich am System änderte](#umbau), [Grenzen dieses")
        z.append("Laufs](#grenzen) und das [Verzeichnis der")
        z.append("Belege](belege.html).")
        z.append("")
    s_lieferung.append("Jeder Dateiname öffnet eine Ansicht: CSV-Dateien als Vorschau")
    s_lieferung.append("der ersten Zeilen, alles Übrige im Original.")
    s_lieferung.append("")
    s_lieferung.append("| Datei | Bytes | SHA-256 | |")
    s_lieferung.append("|---|---:|---|---|")
    for q in quellen:
        name = q.get("datei", "?")
        ansicht = ansichten.get(name)
        zelle = f"[`{name}`]({ansicht})" if ansicht else f"`{name}`"
        s_lieferung.append(f"| {zelle} | {_zahl(q.get('bytes', 0))} "
                 f"| `{str(q.get('sha256',''))[:16]}…` "
                 f"| {'Festlegung des übernehmenden Hauses' if q.get('eigenes_haus') else 'nachgefordert' if q.get('nachgereicht') else ''} |")
    s_lieferung.append("")

    # ------------------------------------------ Station 5 — der Widerspruch
    gruppen = darstellung.diskrepanz_gruppen(modell)
    echte = [g for g in gruppen if g["wertkonflikt"]]
    artefakte_namen = [g for g in gruppen if not g["wertkonflikt"]]
    nachgereicht = [q for q in quellen if q.get("nachgereicht") and not q.get("eigenes_haus")]
    if gruppen:
        s_widerspruch.append("Je Lesart ist das Quelldokument angegeben.")
        if nachgereicht:
            # Nachgereicht werden nicht nur Auskunftsschreiben, auch Tabellen
            # und Erwartungswerte — das Wort zaehlt, was es zaehlt.
            s_widerspruch.append(f"{len(nachgereicht)} Unterlagen wurden im Lauf bei der")
            s_widerspruch.append("abgebenden Gesellschaft nachgefordert und registriert; eine")
            s_widerspruch.append("Unterlage stützt eine Entscheidung erst, wenn sie registriert ist.")
        s_widerspruch.append("")
        s_widerspruch.append("| Feststellung | Tarifzellen | Lesarten (Quelle) | gewählt |")
        s_widerspruch.append("|---|---:|---|---|")
        for g in echte:
            lesarten = "; ".join(
                f"{_lesart_text(g['feld'], w)} ({q})" if q else _lesart_text(g["feld"], w)
                for w, q in g["lesarten"])
            gew = ", ".join(_lesart_text(g["feld"], w) for w in g["gewaehlt"]) or "—"
            s_widerspruch.append(f"| {FELD_TITEL.get(g['feld'], g['feld'])} | {len(g['zellen'])} "
                     f"| {lesarten} | **{gew}** |")
        s_widerspruch.append("")
        if artefakte_namen:
            s_widerspruch.append(f"Dazu {sum(len(g['zellen']) for g in artefakte_namen)} Stellen, an denen")
            s_widerspruch.append("dieselbe Größe nur in zwei Schreibweisen vorlag — kein")
            s_widerspruch.append("Wertkonflikt, aber ebenfalls festgestellt und entschieden: "
                     + ", ".join(f"{FELD_TITEL.get(g['feld'], g['feld'])} ("
                                 + " gegen ".join(str(w) for w, _ in g["lesarten"]) + ")"
                                 for g in artefakte_namen) + ".")
            s_widerspruch.append("")
        if nachgereicht:
            s_widerspruch.append("Nachgeforderte Unterlagen (registriert, Zeit in UTC): " + ", ".join(
                f"`{q.get('datei')}` ({str(q.get('registriert_am'))[:16].replace('T', ' ')})"
                for q in nachgereicht))
            s_widerspruch.append("")
        s_widerspruch.append(_herkunft(modell, "parameter"))
        s_widerspruch.append("")


    uebersetzung = modell.get("transformation") or {}
    if uebersetzung.get("vorhanden"):
        eigener = link("abgeleitet/berichte/uebersetzungsbericht.html")
        s_uebersetzung.append("Die vollständige Feldabbildung samt Begründungen zeigt der")
        s_uebersetzung.append(f"[Übersetzungsbericht]({eigener or 'uebersetzung.html'});")
        s_uebersetzung.append("hier die Eckwerte:")
        s_uebersetzung.append("")
        s_uebersetzung.append("| | |")
        s_uebersetzung.append("|---|---:|")
        if uebersetzung.get("anzahl_quellspalten"):
            s_uebersetzung.append(f"| Quellspalten | {uebersetzung['anzahl_quellspalten']} |")
        s_uebersetzung.append(f"| Zielfelder | {uebersetzung.get('anzahl_zielfelder')} |")
        if uebersetzung.get("zeilen_quelle"):
            s_uebersetzung.append(f"| Zeilen hinein / heraus | {uebersetzung['zeilen_quelle']}"
                     f" / {uebersetzung.get('zeilen_ziel')} |")
        s_uebersetzung.append(f"| ausdrücklich nicht übernommen "
                 f"| {len(uebersetzung.get('nicht_uebernommen') or [])} |")
        s_uebersetzung.append(f"| menschlich entschiedene Übersetzungsfragen "
                 f"| {len(uebersetzung.get('konflikte') or [])} |")
        s_uebersetzung.append("")
        stumm = uebersetzung.get("stumm_weggelassen") or []
        if stumm:
            s_uebersetzung.append(f"**{len(stumm)} Quellspalten sind weder abgebildet noch")
            s_uebersetzung.append("ausdrücklich verworfen** — über sie hält die")
            s_uebersetzung.append("Spezifikation nichts fest: " + ", ".join(f"`{s}`" for s in stumm))
            s_uebersetzung.append("")
        belege = [(Path(ref).name, l) for ref in uebersetzung.get("gelesen_aus") or []
                  for l in [link(ref)] if l]
        if belege:
            s_uebersetzung.append("Belege: " + " · ".join(f"[`{n}`]({l})" for n, l in belege))
            s_uebersetzung.append("")

    # --------------------------------- Station 9 — die Ziehung der Stichprobe
    # Die drei Abnahmen und das Controlling standen einmal unter EINER
    # Ueberschrift "Wie geprueft wurde" — vier Stationen, ein Anker. Wer
    # in der Uebersicht auf Station 10 klickte, landete bei Station 9.
    st = (abnahmen[0].get("stichprobe") or {}) if abnahmen else {}
    abdeckung = ((st.get("parameter") or {}).get("abdeckung") or {})
    if abdeckung:
        s_stichprobe.append(f"Geschichtet nach Vertragsverlauf, {st.get('umfang')} von "
                 f"{st.get('grundgesamtheit')} Verträgen, bewusst")
        s_stichprobe.append("disproportional — die seltenen Verläufe werden stärker geprüft")
        s_stichprobe.append("als die häufigen"
                 + (f"; Ziehungssaat `{(st.get('parameter') or {}).get('saat')}`, "
                    "damit die Ziehung reproduzierbar ist."
                    if (st.get("parameter") or {}).get("saat") else ".")
                 + " Station 10 fährt dieselbe Ziehung.")
        s_stichprobe.append("")
        s_stichprobe.append("| Schicht | im Bestand | gezogen |")
        s_stichprobe.append("|---|---:|---:|")
        for schicht, werte in abdeckung.items():
            s_stichprobe.append(f"| {SCHICHT_TITEL.get(schicht, schicht)} "
                     f"| {werte.get('vorhanden', '—')} | {werte.get('gezogen', '—')} |")
        pflicht = (st.get("parameter") or {}).get("pflichtziehung") or {}
        if pflicht.get("police_ids"):
            s_stichprobe.append(f"| Pflichtziehung: {pflicht.get('anlass') or 'benannte Policen'} "
                     f"| — | {len(pflicht['police_ids'])} |")
        s_stichprobe.append("")

    # ------------------------------------------ Station 12 — das Controlling
    if controlling:
        c = controlling
        s_controlling.append("| | |")
        s_controlling.append("|---|---:|")
        werte = (c.get("verteilung") or {}).get("anzahl_werte")
        s_controlling.append(f"| Verträge im Bestand | {_zahl(bestand.get('anzahl', 0))} |")
        s_controlling.append(f"| davon geprüft | {_zahl(c['anzahl'])} |")
        s_controlling.append(f"| davon bestanden | {_zahl(c['bestanden'])} |")
        s_controlling.append(f"| Einzelprüfungen | {_zahl(werte) if werte else '—'} |")
        s_controlling.append(f"| Prüflücken | {_zahl(c['pruefluecken'])} |")
        s_controlling.append("")
        if c["pruefluecken"]:
            s_controlling.append("Eine **Prüflücke** ist ein Vertrag, dessen Wert am")
            s_controlling.append("Folgestichtag nicht nachgerechnet werden konnte. Der")
            s_controlling.append("Bestands-Scope duldet keine: Der Lauf endet dort mit")
            s_controlling.append("einem Befund, und das ist die richtige Auskunft — ein")
            s_controlling.append("geglätteter Wert wäre eine Behauptung ohne Rechnung.")
            s_controlling.append("")

    # ------------------------------------------ Station 13 — der Bestand
    if bestand.get("vorhanden"):
        status = (bestand.get("verteilungen") or {}).get("status_code") or {}
        if status:
            s_bestand.append(grafik.gestapelt([(STATUS_TITEL.get(k, k), v)
                                       for k, v in status.items()]))
            s_bestand.append("")
        st = (abnahmen[0].get("stichprobe") or {}) if abnahmen else {}
        abdeckung = ((st.get("parameter") or {}).get("abdeckung") or {})
        schichten = [(SCHICHT_TITEL.get(k, k), int(v.get("vorhanden") or 0))
                     for k, v in abdeckung.items()]
        if schichten:
            summe = sum(w for _, w in schichten)
            s_bestand.append("Vertragsverläufe: " + ", ".join(f"{w} {t}" for t, w in schichten)
                     + (f" — zusammen {summe}, das ist der ganze Bestand."
                        if summe == bestand.get("anzahl")
                        else f" — zusammen {summe} von {bestand.get('anzahl')} (Zuordnung unvollständig)."))
            s_bestand.append("")
        vorf = bestand.get("vorfaelle_im_zeitraum") or {}
        if vorf.get("je_art"):
            eintraege = sorted(((GEVO_TITEL.get(k, k), e["anzahl"]) for k, e in vorf["je_art"].items()),
                               key=lambda p: (-p[1], p[0]))
            betraege = {GEVO_TITEL.get(k, k): e.get("betrag_summe") for k, e in vorf["je_art"].items()
                        if e.get("betrag_summe")}
            s_bestand.append(f"{vorf.get('anzahl')} Geschäftsvorfälle zwischen den Stichtagen — Anzahl")
            s_bestand.append("links, bewegter Betrag rechts. Bewegungen und Verträge werden")
            s_bestand.append("nicht addiert.")
            s_bestand.append("")
            s_bestand.append(grafik.balken(eintraege, betraege))
            s_bestand.append("")
        for probe in bestand.get("kreuzproben") or []:
            wort = "geht auf" if probe.get("stimmt") else "**geht nicht auf**"
            s_bestand.append(f"Kreuzprobe — {probe.get('was')}: {probe.get('links')} gegen "
                     f"{probe.get('rechts')}, {wort}.")
            s_bestand.append("")
        s_bestand.append(_herkunft(modell, "bestand"))
        s_bestand.append("")

    # ------------------------------------------ Was herauskam
    s_ergebnis.append("# Was herauskam {#das-ergebnis}")
    s_ergebnis.append("")
    if not (abnahmen or controlling):
        s_ergebnis.append("*(noch keine Berichte im Fall)*")
        s_ergebnis.append("")
    else:
        s_ergebnis.append("Alle Zahlen dieses Berichts stammen unverändert aus den")
        s_ergebnis.append("beigefügten Prüfartefakten (Tabellen auf Vertragsebene als Vorschau) und können dort nachgeschlagen")
        s_ergebnis.append("werden. Zu jeder Abnahme sind die zugesagte Toleranz und")
        s_ergebnis.append("die tatsächlich größte Abweichung angegeben.")
        s_ergebnis.append("")
        zeilen = darstellung.toleranz_zeilen(modell)
        if zeilen:
            s_ergebnis.append('<div class="leitgrafik">' + grafik.toleranz(zeilen) + "</div>")
            s_ergebnis.append("")
        if verankerung.get("vorhanden"):
            s_ergebnis.append(f"**Die Korrekturschicht ist nahezu leer.** Über alle "
                     f"{verankerung.get('getragen')} Verträge beträgt die Summe der")
            s_ergebnis.append(f"Verankerungs-Residuen {_zahl(verankerung.get('residuum_summe'), 2)} €, "
                     f"die größte Einzelabweichung "
                     f"{_zahl(verankerung.get('residuum_max_abs'), 2)} €. Das Zielsystem")
            s_ergebnis.append("rechnet den Bestand aus den Ursprungsparametern nach; der")
            s_ergebnis.append("gelieferte Stand geht ausschließlich in das Verankerungs-Residuum")
            s_ergebnis.append("ein.")
            s_ergebnis.append("")
        s_ergebnis.append("| Abnahme | Geprüft wird | Verträge | Werte | größte Abweichung | erlaubt | Urteil |")
        s_ergebnis.append("|---|---|---:|---:|---:|---:|---|")
        for t in abnahmen:
            titel, prueft = ABNAHMEN.get(t.get("kennung"), (t.get("titel", "?"), ""))
            name = f"{t.get('kennung')} {titel}"
            bericht = link(t.get("bericht"))
            if bericht:
                name = f"[{name}]({bericht})"
            v = t.get("verteilung") or {}
            g = t.get("grundtoleranz") or {}
            s_ergebnis.append(f"| {name} | {prueft} | {_zahl(t.get('anzahl', 0))} "
                     f"| {_zahl(v['anzahl_werte']) if v.get('anzahl_werte') else '—'} "
                     f"| {grafik.cent(v['max_abs_residuum']) if v.get('max_abs_residuum') is not None else '—'} "
                     f"| {grafik.cent(g['max_abs_residuum']) if g.get('max_abs_residuum') else '—'} "
                     f"| {_urteilswort(t.get('urteil'))} |")
        if controlling:
            name = "A-M4 Migrationscontrolling"
            abnahmelink = link("abgeleitet/berichte/migrationsabnahme.html")
            if abnahmelink:
                name = f"[{name}]({abnahmelink})"
            v = controlling.get("verteilung") or {}
            s_ergebnis.append(f"| {name} | der ganze Bestand über zwei Stichtage "
                     f"| {_zahl(controlling.get('anzahl', 0))} "
                     f"| {_zahl(v['anzahl_werte']) if v.get('anzahl_werte') else '—'} "
                     f"| {grafik.cent(v['max_abs_residuum']) if v.get('max_abs_residuum') is not None else '—'} "
                     f"| je Prüfung nach Bausteinen | {_urteilswort(controlling.get('urteil'))} |")
        s_ergebnis.append("")
        gm = param.get("golden_master") or {}
        if gm.get("vorhanden"):
            s_ergebnis.append(f"Quell-Tarifrechner nachgerechnet: {gm.get('werte_verglichen')} Werte "
                     f"verglichen, {gm.get('abweichungen')} Abweichungen"
                     + (f" — Erwartungswerte lagen für "
                        f"{int(gm.get('zellen_gesamt') or 0) - int(gm.get('zellen_ohne_erwartungswerte') or 0)} "
                        f"von {gm.get('zellen_gesamt')} Tarifzellen vor."
                        if gm.get("zellen_gesamt") else "."))
            s_ergebnis.append("")
        s_ergebnis.append(_herkunft(modell, "abnahmen"))
        s_ergebnis.append("")

    # ------------------------------------------ Der Umbau des Zielsystems
    if umbau.get("vorhanden"):
        # Der Umbau stand einmal als Unterabschnitt unter "Grenzen dieses
        # Laufs". Das war die falsche Schublade: Wie weit eine Uebernahme
        # das Zielsystem veraendert hat, ist kein Vorbehalt am Rand,
        # sondern eine der Kernaussagen — und in der Abnahmekette kommt
        # sie bisher gar nicht vor. Sie steht deshalb direkt hinter dem
        # Ergebnis, mit Zahlen statt Prosa.
        offene = umbau.get("befunde") or []
        stolper = umbau.get("stolperdraehte") or []
        gesamt = umbau.get("gesamt") or {}
        umbaubericht = link("abgeleitet/berichte/umbaubericht.html")
        s_umbau.append("# Was sich am System änderte {#umbau}")
        s_umbau.append("")
        s_umbau.append("Eine Übernahme darf unser System erweitern, nicht nebenbei")
        s_umbau.append("ersetzen. Wie weit dieser Lauf es verändert hat, wird")
        s_umbau.append("gemessen — Überschreiten ist erlaubt, Verschweigen nicht.")
        s_umbau.append("")
        summe, vorgabe = gesamt.get("summe"), gesamt.get("vorgabe")
        anteil = (f"{round(100 * summe / vorgabe)} %"
                  if isinstance(summe, int) and vorgabe else "—")
        s_umbau.append("| Kennzahl | Wert |")
        s_umbau.append("|---|---:|")
        s_umbau.append(f"| Geänderte Zeilen in `src/` und `tests/` | {_zahl(summe)} |")
        s_umbau.append(f"| Vereinbartes Änderungsbudget | {_zahl(vorgabe)} |")
        s_umbau.append(f"| Ausgeschöpft | {anteil} |")
        for name, schluessel in (("davon hinzugefügt", "plus"),
                                 ("davon entfernt", "minus")):
            if gesamt.get(schluessel) is not None:
                s_umbau.append(f"| {name} | {_zahl(gesamt[schluessel])} |")
        s_umbau.append(f"| Berührte Stolperdrähte | {_zahl(len(stolper))} |")
        s_umbau.append(f"| Befunde der Messung | {_zahl(len(offene))} |")
        if umbau.get("basis"):
            s_umbau.append(f"| Gemessen gegen Stand | `{umbau['basis']}` |")
        s_umbau.append("")
        if umbaubericht:
            s_umbau.append(f"Jede geänderte Datei mit Begründung: "
                     f"[Umbau des Zielsystems]({umbaubericht}).")
            s_umbau.append("")
        if not offene:
            s_umbau.append("Im Rahmen der vereinbarten Schranken.")
            s_umbau.append("")
        else:
            wort = "Befund" if len(offene) == 1 else "Befunde"
            s_umbau.append(f"**{len(offene)} {wort} der Messung.** Ein Befund ist entweder")
            s_umbau.append("ein gerissenes Zeilen-Budget oder ein berührter")
            s_umbau.append("Stolperdraht — eine Architektur-Stelle wie die")
            s_umbau.append("Referenzwerte des Kerns oder das Schichtgefüge, die")
            s_umbau.append("unabhängig vom Umfang anschlägt:")
            s_umbau.append("")
            for befund in offene:
                s_umbau.append(f"* {befund}")
            s_umbau.append("")
            begruendung = umbau.get("ueberschreitung_begruendet")
            if begruendung:
                s_umbau.append(f"Als bewusste Entscheidung begründet: „{begruendung}“")
            else:
                s_umbau.append("**Ohne Begründung.**")
            s_umbau.append("")
        s_umbau.append("Der Umbau ist bisher NICHT Teil der Abnahmekette: Kein Gate")
        s_umbau.append("hält ihn an, keine Zeichnung bindet ihn. Er wird gemessen")
        s_umbau.append("und ausgewiesen, mehr nicht — das ist eine offene Stelle")
        s_umbau.append("und keine Eigenschaft des Verfahrens.")
        s_umbau.append("")

    # --------------------------- Nachschlagestoff: Laeufe und Zeichnungen
    s_anlaeufe.append("## Alle Prüfläufe und ihre Ledger {#wie-es-lief}")
    s_anlaeufe.append("")
    if gates:
        laeufe = sum(int(g.get("versuch") or 1) for g in gates)
        s_anlaeufe.append(f"{len(gates)} Prüfschritte, {_zahl(laeufe)} Anläufe bis zum")
        s_anlaeufe.append("Urteil. Die Seite der Übernahme nennt je Station den Lauf, der zählt; hier")
        entscheid_gates = sum(1 for g in gates if str(g.get("gate", "")).startswith("entscheid."))
        s_anlaeufe.append(f"stehen alle, auch die {_zahl(entscheid_gates)} Entscheid-Gates, die je")
        s_anlaeufe.append("Entscheid-Runde ein eigenes Ledger schreiben.")
        s_anlaeufe.append("")
        s_anlaeufe.append("| Prüfschritt | Anläufe | Urteil | Ledger |")
        s_anlaeufe.append("|---|---:|---|---|")
        for g in gates:
            ledger = link(g.get("ledger"))
            zelle = f"[`json`]({ledger})" if ledger else "—"
            s_anlaeufe.append(f"| {g['gate']} | {g.get('versuch') or 1} | {g['status']} | {zelle} |")
        s_anlaeufe.append("")
    else:
        s_anlaeufe.append("*(noch keine Prüfschritte im Fall)*")
        s_anlaeufe.append("")
    s_anlaeufe.append("## Die Entscheid-Snapshots {#zeichnungen}")
    s_anlaeufe.append("")
    _n = len(entscheide)
    _final = sum(1 for e in entscheide if e.get("geltend") or e.get("in_finaler_kette"))
    s_anlaeufe.append(f"{_n} Entscheid-Snapshots liegen im Fall, {_final} davon geltend —")
    s_anlaeufe.append("je Gate einer; die übrigen sind Runden, die durch Korrekturen")
    s_anlaeufe.append("überholt wurden und erhalten bleiben. Je Snapshot Gate,")
    s_anlaeufe.append("Entscheid, Rolle und Prüfstand:")
    s_anlaeufe.append("[Die Entscheid-Snapshots der Gates](entscheide.html).")
    s_anlaeufe.append("")

    sys_ae = modell.get("systemaenderung") or {}
    if not umbau.get("vorhanden") and (sys_ae.get("kern") or sys_ae.get("tarifwerk")):
        # Seit der Abnahme des Stands traegt ein Fall kein Umbaubudget mehr,
        # sondern die Aenderungsbelege von Kern und Tarifwerk, die je ein
        # Mensch abnimmt. Gezeigt wird je Datei, was dazukam und wegfiel —
        # die Einzelheiten je Commit stehen im lesbaren Beleg.
        s_umbau.append("# Was sich am System änderte {#umbau}")
        s_umbau.append("")
        s_umbau.append("Eine Übernahme darf unser System erweitern, nicht nebenbei")
        s_umbau.append("ersetzen. Was sich für diesen Fall geändert hat, steht in")
        s_umbau.append("Änderungsbelegen, die je in der zuständigen Rolle abgenommen sind — gezählt")
        s_umbau.append("in Zeilen je Datei, gegen den zuletzt abgenommenen Stand.")
        s_umbau.append("")
        k_ae = sys_ae.get("kern") or {}
        if k_ae:
            sicht = link(k_ae.get("sicht"))
            s_umbau.append(f"**Rechenkern** (A-K2, Rechenkern-Verantwortung): Version "
                           f"{k_ae.get('von_version')} auf {k_ae.get('nach_version')}, "
                           f"{_zahl(len(k_ae.get('module') or []))} von "
                           f"{_zahl(k_ae.get('module_gesamt') or 0)} Teilen geändert, "
                           f"{_zahl(k_ae.get('commits') or 0)} Commits"
                           + (f" ([Änderungsbeleg]({sicht}))." if sicht else "."))
            s_umbau.append("")
            if k_ae.get("module"):
                s_umbau.append("| Datei | Zeilen hinzu | Zeilen weg |")
                s_umbau.append("|---|---:|---:|")
                for m in k_ae["module"]:
                    s_umbau.append(f"| `{m['modul']}` | {_zahl(m['hinzu'])} | {_zahl(m['weg'])} |")
                s_umbau.append("")
            regression = (abn_ae := (modell.get("abnahmen") or {}).get("kernstand") or {}).get("regression")
            if regression:
                s_umbau.append(f"{regression}." + (f" {abn_ae.get('deckung')}" if abn_ae.get("deckung") else ""))
                s_umbau.append("")
        t_ae = sys_ae.get("tarifwerk") or {}
        if t_ae:
            sicht = link(t_ae.get("sicht"))
            teile = ", ".join(f"`{t['pfad']}` (+{_zahl(t['hinzu'])}/−{_zahl(t['weg'])})"
                              for t in t_ae.get("teile") or []) or "keine Datei"
            s_umbau.append(f"**Tarifwerk** (A-T1, Verantwortlicher Aktuar): geändert {teile}; "
                           f"{_zahl(len(t_ae.get('generationen') or []))} Generationen mit "
                           "geänderten Tarifwerk-Feldern"
                           + (f" ([Änderungsbeleg]({sicht}))." if sicht else "."))
            s_umbau.append("")

    # ------------------------------------------ Grenzen des Laufs
    s_grenzen.append("# Grenzen dieses Laufs {#grenzen}")
    s_grenzen.append("")
    s_grenzen.append(_grenzen(modell, unterseite))
    s_grenzen.append("")

    # ------------------------------------------ Verzeichnis der Artefakte
    s_belege.append("# Verzeichnis der Belege")
    s_belege.append("")
    s_belege.append(f"Jeder Bericht steht bei der Station der [Übernahme]({index_ref}), an der er")
    s_belege.append("entsteht. Hier stehen alle noch einmal beisammen, für den,")
    s_belege.append("der einen bestimmten sucht.")
    s_belege.append("")
    if alle_berichte:
        s_belege.append("| Bericht | Station |")
        s_belege.append("|---|---|")
        for k in alle_berichte:
            wohin = darstellung.STATION_ABSCHNITT.get(k["station"])
            wo = k["zweck"].split(" — ")[0]
            s_belege.append(f"| [{k['titel']}]({k['href']}) "
                            f"| {f'[{wo}]({index_ref}#{wohin})' if wohin else wo} |")
        s_belege.append("")
    kette_b = modell.get("belegkette") or {}
    s_belege.append(f"{len(kopiert)} Dateien unter `artefakte/`. Welche Datei an welche "
                    "Station gehört, ist aus der Belegkette des Falls erhoben — aus "
                    "dem, was jedes Prüfprotokoll gelesen und geschrieben hat, und "
                    "aus den Prüfsummen, die jeder Entscheid bindet:")
    s_belege.append("")
    je_station_b = kette_b.get("je_station") or {}
    zurueck_b = {x["original"] for x in (bereinigt or {}).get("zurueckgehalten") or []}
    for nummer, titel, _gate in darstellung.WEG_STATIONEN:
        pfade_b = je_station_b.get(str(nummer)) or []
        anzahl = sum(1 for f in pfade_b if link(f))
        fehlt_b = sum(1 for f in pfade_b if f in zurueck_b)
        if anzahl or fehlt_b:
            s_belege.append(f"* [Station {nummer} · {titel}]({index_ref}#{darstellung.STATION_ABSCHNITT[nummer]}) "
                            f"— {anzahl} {'Datei' if anzahl == 1 else 'Dateien'}"
                            + (f", dazu {fehlt_b} nicht veröffentlicht" if fehlt_b else ""))
    ansichten_zahl = sum(1 for k in kopiert if k.startswith("artefakte/lieferung/"))
    if ansichten_zahl:
        s_belege.append(f"* `lieferung` — Ansichten der gelieferten Dateien "
                        f"({ansichten_zahl} Dateien)")
    quellen_d = sorted(f for f, e in (kette_b.get("dateien") or {}).items()
                       if e.get("quelle_der_darstellung"))
    for f in quellen_d:
        ziel_d = link(f)
        if ziel_d:
            s_belege.append(f"* [`{f}`]({ziel_d}) — gelesen von dieser Darstellung, "
                            "keiner Station der Kette zugeordnet")
    s_belege.append("")
    b_liste = (bereinigt or {}).get("bereinigt") or []
    z_liste = (bereinigt or {}).get("zurueckgehalten") or []
    if b_liste or z_liste:
        # Die Seite sagt offen, wo sie nicht die gebundenen Bytes zeigt
        # (Entscheid des Maintainers, 03.10.2026; werkzeuge/bereinigung.py).
        s_belege.append("## Bereinigt veröffentlicht {#bereinigt}")
        s_belege.append("")
    if b_liste:
        regeln_t = ", ".join(f"`{r['platzhalter']}` für {r['steht_fuer']}"
                             for r in (bereinigt or {}).get("regeln") or []
                             if any(r["platzhalter"] in x["ersetzungen"] for x in b_liste))
        ungebunden = sum(1 for x in b_liste if not x.get("gebunden_von"))
        s_belege.append(
            f"{len(b_liste)} {'Datei trägt' if len(b_liste) == 1 else 'Dateien tragen'} im Fall "
            "Pfade des Rechners, auf dem der Lauf lief. Veröffentlicht "
            f"{'ist sie' if len(b_liste) == 1 else 'sind sie'} mit benannten Platzhaltern — "
            f"{regeln_t} — und darum nicht bytegleich mit dem Original. Je Datei nennt das "
            f"[Bereinigungsmanifest](artefakte/{bereinigung.MANIFEST}) die Prüfsumme des "
            "Originals im Fall, die Entscheide, die dieses Original über seine Prüfsumme "
            "binden, die Prüfsumme der veröffentlichten Fassung und die Ersetzungen"
            + (f"; {ungebunden} der {len(b_liste)} Originale bindet kein Entscheid"
               if ungebunden else "") + ". "
            "Alle übrigen Belege unter `artefakte/` sind bytegleich mit ihren Originalen im "
            "Fall; die Ansichten der Lieferung sind Ansichten — eine CSV als Vorschau ihrer "
            "ersten Zeilen, alles Übrige bytegleich.")
        s_belege.append("")
        s_belege.append("| Datei | Original im Fall | gebunden von | veröffentlicht | ersetzt |")
        s_belege.append("|---|---|---|---|---|")
        for x in sorted(b_liste, key=lambda x: x["datei"]):
            ersetzt_t = ", ".join(f'<span class="kennung">`{p}` ×{n}</span>'
                                  for p, n in sorted(x["ersetzungen"].items()))
            gebunden_t = ", ".join(f'<span class="kennung">{g}</span>'
                                   for g in x.get("gebunden_von") or []) or "keinem Entscheid"
            s_belege.append(f"| [`{x['original']}`]({x['datei']}) "
                            f"| `{str(x['sha256_original'])[:16]}…` "
                            f"| {gebunden_t} "
                            f"| `{str(x['sha256_veroeffentlicht'])[:16]}…` | {ersetzt_t} |")
        s_belege.append("")
    for x in sorted(z_liste, key=lambda x: x["original"]):
        s_belege.append(f"Nicht veröffentlicht: `{x['original']}` — ein {x['grund']}; "
                        f"Prüfsumme der Datei `{x['sha256']}`. Ein Snapshot wird nie "
                        "bereinigt, weil eine Änderung seine Signatur und die Verweise der "
                        "Folgeentscheide bräche.")
        s_belege.append("")
    ohne = kette_b.get("ohne_station") or {}
    if ohne:
        s_belege.append(f"Nicht auf dieser Seite: {sum(ohne.values())} Dateien des Falls, "
                        "die keine Station trägt — Arbeitsunterlagen der Agenten "
                        "(Protokolle, Messungen, Übergaben) und überholte "
                        "Zwischenstände. Sie sind nicht Teil der Belegkette.")
        s_belege.append("")
    for datei, leser in sorted((kette_b.get("ausserhalb") or {}).items()):
        s_belege.append(f"Außerhalb des Falls gelesen: `{datei}` ({', '.join(leser)}) — "
                        "eine Datei des Systemstands, nicht des Falls.")
        s_belege.append("")
    s_belege.extend(s_anlaeufe)
    if verlauf:
        s_belege.append("## Der Verlauf des Laufs {#verlauf}")
        s_belege.append("")
        s_belege.append("Der Ablauf des Laufs, aus dem Sitzungstranskript erzeugt:")
        s_belege.append("[verlauf.md](verlauf.md).")
        s_belege.append("")

    # ---- EINE Seite, von A bis Z -------------------------------------
    # Der Fall lag einmal auf dreizehn Seiten: "Der Weg der Uebernahme"
    # erzaehlte die Stationen, ein Fallbericht erzaehlte sie nach, und die
    # Belege lagen am Fuss einer dritten. Jede Umsortierung hat die
    # Dopplung verschoben statt beseitigt. Die Regel steht jetzt fest
    # (dev-docs/fallseite-konzept.md): EINE STATION, EINE STELLE — wer bei
    # Station 5 steht, findet dort, was das Gate prueft, was geschah, die
    # Zahlen und die Belege, und muss nirgendwo hinspringen.
    def fuss() -> List[str]:
        f: List[str] = [""]
        if unterseite:
            f.append('<div class="fuss-fiktion">Fiktives Unternehmen — '
                     '<a href="../../hinter-den-kulissen/">Hinter den Kulissen</a></div>')
            f.append("")
        f.append(f"*Erzeugt am {heute} aus dem Systemstand "
                 f"`{stand['commit'][:12]}`.*")
        f.append("")
        return f

    def _kettenbelege(nummer: int) -> List[str]:
        """Alle Dateien der Belegkette an dieser Station, je Art eine Zeile.

        Die Kacheln darueber zeigen die Berichte mit Kennzahl; hier steht
        jede Datei, die ein Gate der Station gelesen, geschrieben oder als
        Pflichtbeleg gebunden hat — erhoben, nicht gepflegt
        (``falldaten.belegkette``)."""
        import falldaten as _fd

        kette_s = modell.get("belegkette") or {}
        dateien = kette_s.get("dateien") or {}
        pfade = (kette_s.get("je_station") or {}).get(str(nummer)) or []
        gruppen: Dict[str, List[str]] = {}
        b_rel = {x["original"] for x in (bereinigt or {}).get("bereinigt") or []}
        z_rel = {x["original"] for x in (bereinigt or {}).get("zurueckgehalten") or []}
        for f in pfade:
            href = link(f)
            titel = html.escape(str(dateien[f].get("titel") or f))
            if not href:
                if f in z_rel:
                    gruppen.setdefault(str(dateien[f].get("art")), []).append(
                        f"{titel} <small>(überholt, nicht veröffentlicht)</small>")
                continue
            zusatz = " <small>(nicht gebunden)</small>" if dateien[f].get("ungebunden") else ""
            if f in b_rel:
                zusatz += ' <small>(<a href="belege.html#bereinigt">bereinigt</a>)</small>'
            gruppen.setdefault(str(dateien[f].get("art")), []).append(
                f'<a href="{html.escape(href)}">{titel}</a>{zusatz}')
        if not gruppen:
            return []
        # Reines HTML: Markdown in einem <details> rendert nicht jeder
        # Generator, und ein Link, der als Klammertext stehen bliebe, waere
        # kein Beleg.
        teile = [f'<details class="belege"><summary>Alle {sum(len(v) for v in gruppen.values())} '
                 "Belege dieser Station, aus der Belegkette</summary><ul>"]
        for art in sorted(gruppen, key=lambda a: _fd.BELEG_ARTEN.get(a, (7, ""))[0]):
            name = html.escape(_fd.BELEG_ARTEN.get(art, (7, art))[1])
            teile.append(f"<li><b>{name}:</b> " + " · ".join(gruppen[art]) + "</li>")
        in_arbeit = (kette_s.get("in_arbeit") or {}).get(str(nummer)) or []
        if in_arbeit:
            teile.append("<li><b>In Arbeit:</b> " + html.escape(", ".join(in_arbeit)) + "</li>")
        teile.append("</ul>")
        if any(dateien[f].get("ungebunden") for f in pfade):
            teile.append("<p><small>Nicht gebunden: Kein Prüfprotokoll und kein Entscheid bindet "
                         "diese Datei über ihre Prüfsumme. Sie ist ein Erzeugnis der "
                         "deterministischen Vorverdichtung der gelieferten Quellen und steht "
                         "hier, damit die Extraktion zu sehen ist.</small></p>")
        teile.append("</details>")
        return ["".join(teile), ""]

    def _stationen(zahlen: Dict[int, List[str]]) -> List[str]:
        """Die dreizehn Stationen — Pruefung, Geschehen, Zahlen, Belege.

        Die Erzaehlung stand bis hierher in ``unternehmensseite._journey``
        und die Zahlen hier; zwei Fassungen desselben Vorgangs, die
        auseinanderliefen. Sie ist hierher gewandert, nicht kopiert
        worden.
        """
        try:
            from rechner_pipeline.gates.register import REGISTER
        except ImportError as exc:  # pragma: no cover
            raise VeroeffentlichungFehler(f"Gate-Register nicht ladbar: {exc}") from exc
        register = {g.kennung: g for g in REGISTER}
        laeufe: Dict[str, Dict[str, Any]] = {}
        for g in gates:
            k = str(g.get("gate", "")).split(".")[0]
            if k.startswith(("P-", "A-")):
                laeufe[k] = g  # der juengste Lauf je Gate
        trafo = modell.get("transformation") or {}
        betrieb = modell.get("betrieb") or {}
        gm = param.get("golden_master") or {}
        deckung = param.get("deckung") or {}
        aktuariell = {t.get("kennung"): t for t in abnahmen}
        ctrl = controlling or {}
        echte_d = [d for d in darstellung.diskrepanz_zeilen(modell)
                   if d.get("wertkonflikt")]
        dat = darstellung.datum

        def lauf_satz(kennung: str) -> str:
            g = laeufe.get(kennung)
            if not g:
                return "Im Fall nicht gelaufen."
            status = "bestanden" if g.get("status") == "passed" else str(g.get("status"))
            v = int(g.get("versuch") or 1)
            anl = f"{_zahl(v)} Anläufen" if v > 1 else "einem Anlauf"
            ledger = link(g.get("ledger"))
            return (f"{status.capitalize()} nach {anl}"
                    + (f" ([Ledger]({ledger}))." if ledger else "."))

        def entscheid_satz(kennung: str, mit_gate: bool = False) -> str:
            """Der geltende Entscheid eines Gates in einem Satz; ``mit_gate``
            nennt das Gate davor — noetig, wo eine Station mehr als einen
            Entscheid traegt."""
            alle = [e for e in entscheide if e.get("gate") == kennung]
            final = [e for e in alle if e.get("geltend") or e.get("in_finaler_kette")]
            if not alle:
                return "Kein Entscheid im Fall."
            e = final[-1] if final else alle[-1]
            snap = link(e.get("snapshot_datei"))
            ueberholt = len(alle) - 1
            t = ((f"{kennung}: " if mit_gate else "") + f"Entscheid **{e.get('entscheid')}** am "
                 f"{dat(str(e.get('entschieden_am'))[:10])}, "
                 f"Rolle {e.get('rolle') or '—'}")
            if snap:
                t += f" ([Snapshot]({snap}))"
            if ueberholt:
                t += (f"; {_zahl(ueberholt)} frühere Runde"
                      f"{'n' if ueberholt > 1 else ''} überholt")
            return t + "."

        def abnahme_satz(kennung: str) -> str:
            t = aktuariell.get(kennung)
            if not t:
                return ""
            v = t.get("verteilung") or {}
            tol = t.get("grundtoleranz") or {}
            sp = t.get("stichprobe") or {}
            umfang = ("Vollerhebung" if sp.get("vollerhebung") else
                      f"Stichprobe {_zahl(sp.get('umfang') or 0)} von "
                      f"{_zahl(sp.get('grundgesamtheit') or 0)}, {sp.get('profil') or ''}")
            return (f"{_zahl(t.get('bestanden') or 0)} von {_zahl(t.get('anzahl') or 0)} "
                    f"bestanden ({umfang}); größte Abweichung "
                    f"{grafik.cent(v.get('max_abs_residuum') or 0)} bei erlaubten "
                    f"{grafik.cent(tol.get('max_abs_residuum') or 0)}.")

        # --- Station 4: je Pflichtfeld der Zustand
        deckung_satz = ""
        if deckung.get("vorhanden"):
            zl = deckung.get("zaehler") or {}
            zustaende = ", ".join(
                f"{darstellung.DECKUNG_ZUSTAND.get(k, k.replace('_', ' '))} {_zahl(v)}"
                for k, v in sorted(zl.items()))
            deckung_satz = (
                f"Vollständigkeit wird gezählt, nicht behauptet: "
                f"{_zahl(zl.get('belegt') or 0)} von "
                f"{_zahl(deckung.get('pflicht_gesamt') or 0)} Pflichtfeldern belegt — "
                f"{_zahl(deckung.get('pflichtfelder') or 0)} Pflichtparameter aus dem "
                f"Begriffsmodell mal {_zahl(deckung.get('zellen') or 0)} Merkmalszellen "
                f"aus den Quellen; je Feld der Zustand ({zustaende}). Weil die "
                "Feldliste aus dem Begriffsmodell kommt und nicht aus dem Gefundenen, "
                "fällt auch auf, was die Extraktion ganz übersehen hätte. Geschützt "
                "ist die Feldliste, nicht die Zellenzahl: Übersehen alle Quellen "
                "dieselbe Zelle, wird die Gesamtzahl kleiner, ohne dass die Quote "
                "fällt.")
        # --- Station 5: EINE Zaehlung — Feststellungen, Zellen, Konflikte
        gruppen_w = [g for g in darstellung.diskrepanz_gruppen(modell)
                     if g["wertkonflikt"]]
        zellen_w = sorted({zelle for g in gruppen_w for zelle in g["zellen"]})
        widerspruch_satz = (
            (f"Der eine Wertkonflikt" if len(echte_d) == 1
             else f"Die {_zahl(len(echte_d))} Wertkonflikte")
            + (" fällt in " if len(echte_d) == 1 else " fallen in ")
            + (f"eine Feststellung" if len(gruppen_w) == 1
               else f"{_zahl(len(gruppen_w))} Feststellungen")
            + (" über eine Tarifzelle" if len(zellen_w) == 1
               else f" über {_zahl(len(zellen_w))} Tarifzellen")
            + "; jede hat der Verantwortliche Aktuar entschieden, mit beiden "
              "Lesarten und Begründung.")
        beispiel = ""
        if echte_d:
            d = echte_d[0]
            beispiel = f" Beispiel {d.get('feld')}: gewählt {d.get('gewaehlt')}."
        # --- Station 12: was der Abschluss-Entscheid bindet
        am4 = [e for e in entscheide
               if e.get("gate") == "A-M4" and e.get("in_finaler_kette")]
        gebunden = (" " + _bindet_satz(am4[-1], entscheide)) if am4 else ""
        cv = ctrl.get("verteilung") or {}
        ueb0 = (betrieb.get("uebernahmen") or [{}])[0]
        bst = betrieb.get("bestand") or {}

        # --- Stand des Falls (ADR-018 Nachtrag 01.10., ADR-025): Was der
        # A-M4-Snapshot je Gegenstand SAGT — woertlich, nicht hergeleitet.
        # "Im Fall abgenommen", "keine Aenderung seit Abnahme ... (Linie)"
        # oder die Ausnahme der Regression stehen so, wie der Entscheid sie
        # signiert hat; die Seite behauptet ueber den Stand nichts Eigenes.
        abn = modell.get("abnahmen") or {}
        stand_saetze = [f"{st.get('gate')} {st.get('titel')}: {st.get('anzeige')}."
                        for st in abn.get("standabnahmen") or []]
        stand_satz = ""
        if stand_saetze:
            stand_satz = ("Wie der Stand abgenommen ist, auf dem dieser Fall rechnet, hält der "
                          "Entscheid der Abschlussabnahme je Gegenstand fest: " + " ".join(stand_saetze))
        elif any(e.get("gate") == "A-M4" for e in entscheide):
            stand_satz = ("Der Entscheid der Abschlussabnahme dieses Falls nennt keine "
                          "Abnahme des Stands; er stammt aus der Zeit, bevor A-M4 sie verlangte.")
        kern = abn.get("kernstand") or {}
        kern_satz = ""
        if kern:
            kern_satz = (f"Der Rechenkern ging dabei von Version {kern.get('von_version')} auf "
                         f"{kern.get('nach_version')}: {_zahl(len(kern.get('module_geaendert') or []))} "
                         f"von {_zahl(kern.get('module') or 0)} Modulen geändert, "
                         f"{_zahl(kern.get('commits') or 0)} Commits seit der zuletzt "
                         "abgenommenen Fassung.")
        auftrag = modell.get("fallauftrag") or {}
        auftrag_satz = ""
        if auftrag.get("vorhanden"):
            auftrag_satz = (f"Der Auftrag, wie ihn die Vorlage des Vorstands festhält: "
                            f"„{str(auftrag.get('auftrag') or '').strip()}“")
        probe = modell.get("zugangsprobe") or {}
        probe_satz = ""
        if probe.get("vorhanden"):
            folge = probe.get("folgetermin") or {}
            probe_satz = (f"Vor dem Zugang fährt eine Zugangsprobe zwei Läufe auf einer Kopie "
                          f"der Ablage, mit und ohne den Eingang, vom {dat(probe.get('stichtag'))} "
                          f"bis {dat(probe.get('bis'))}: {_zahl(probe.get('vergleiche_ok') or 0)} von "
                          f"{_zahl(probe.get('vergleiche') or 0)} Vergleichen mit Sollwert stimmen"
                          + (f", {_zahl(probe.get('ohne_soll'))} weitere Werte sind ohne Sollwert "
                             "ausgewiesen" if probe.get("ohne_soll") else "")
                          + f"; {_zahl(probe.get('befunde') or 0)} Befunde."
                          + (f" Den Folgetermin {dat(folge.get('stichtag'))} deckt die Probe nicht."
                             if folge and folge.get("gedeckt") is False else "")
                          + " Über den Zugang entscheidet danach die Betriebsverantwortung (A-B2).")
        zugang_satz = ("Nach der Abschlussabnahme wird der übernommene Bestand freigeschaltet: "
                       "Er tritt zum Übernahmestichtag als Zugang in den geführten Bestand ein und "
                       "läuft von da an wie eigenes Geschäft — Tageslauf für Tageslauf fortgeschrieben, "
                       "vor jedem neuen Stand von der Wache P-B1 geprüft, zu jedem Monatsersten "
                       "abgeschlossen.")

        geschehen: Dict[int, List[str]] = {
            1: [entscheid_satz("A-M6"), auftrag_satz,
                f"{_zahl((lieferung.get('anzahl') or 0) - (lieferung.get('anzahl_eigenes_haus') or 0))} Dateien der abgebenden "
                f"Gesellschaft registriert, davon "
                f"{_zahl(sum(1 for q in lieferung.get('quellen') or [] if q.get('nachgereicht') and not q.get('eigenes_haus')))} auf Nachfrage "
                "nachgereicht"
                + (f"; dazu {_zahl(lieferung.get('anzahl_eigenes_haus'))} Festlegung"
                   f"{'en' if (lieferung.get('anzahl_eigenes_haus') or 0) > 1 else ''} des "
                   "übernehmenden Hauses, ebenso registriert"
                   if lieferung.get("anzahl_eigenes_haus") else "")
                + ". Jede mit Prüfsumme; einen impliziten Eingangskanal gibt es nicht."
                if lieferung.get("anzahl") else ""],
            2: ["Die Maschine sichert das Material und misst, wie viel Prüfstoff "
                "es hergibt; ein Modell deutet es; die Prüfung fängt die Deutung.",
                lauf_satz("P-Q1"),
                (f"Der Tarifrechner brachte gespeicherte Sollwerte mit — gegen sie "
                 f"rechnet der Rechenkern an Station 7 "
                 f"{_zahl(gm.get('werte_verglichen') or 0)} Werte nach."
                 if gm.get("werte_verglichen") else "")],
            3: [lauf_satz("P-Q2"),
                f"{_zahl(param.get('anzahl_diskrepanzen') or 0)} Diskrepanzen zwischen "
                f"den Unterlagen festgehalten, davon {_zahl(len(echte_d))} echte "
                "Wertkonflikte"
                + ("; der Rest sind Namensartefakte derselben Größe."
                   if int(param.get("anzahl_diskrepanzen") or 0) > len(echte_d) else ".")
                if "P-Q2" in laeufe else ""],
            4: [lauf_satz("P-Q3"), deckung_satz],
            5: [entscheid_satz("A-Q1"), (widerspruch_satz + beispiel) if echte_d else ""],
            6: ["Bevor gerechnet wird, wird übersetzt: Die Spalten des gelieferten "
                "Datenmodells werden auf unser Zielmodell abgebildet — jede "
                "Abbildung begründet, jede Nichtübernahme ausdrücklich erklärt.",
                f"{_zahl(trafo.get('zeilen_quelle') or 0)} gelieferte Zeilen mit "
                f"{_zahl(trafo.get('anzahl_quellspalten') or 0)} Spalten auf "
                f"{_zahl(trafo.get('anzahl_zielfelder') or 0)} Zielfelder abgebildet, "
                f"{_zahl(trafo.get('zeilen_ziel') or 0)} Verträge im Zielbestand; "
                f"{_zahl(len(trafo.get('nicht_uebernommen') or []))} Spalten bewusst "
                f"nicht übernommen, {_zahl(len(trafo.get('befunde') or []))} Befunde."
                if trafo.get("vorhanden") else ""],
            7: [lauf_satz("P-K1"),
                f"{_zahl(gm.get('werte_verglichen') or 0)} Werte gegen den "
                f"Tarifrechner verglichen, {_zahl(gm.get('abweichungen') or 0)} "
                "Abweichungen; Erwartungswerte lagen für "
                f"{_zahl(int(gm.get('zellen_gesamt') or 0) - int(gm.get('zellen_ohne_erwartungswerte') or 0))} "
                f"von {_zahl(gm.get('zellen_gesamt') or 0)} Tarifzellen vor — die "
                "übrigen Zellen deckt der aktuarielle Test."
                if "P-K1" in laeufe else "",
                (" ".join(f"Für den Vergleich mit dem Rechner rechnet der Kern mit dessen "
                          f"Lesart ({FELD_TITEL.get(feld, feld)} {_lesart_text(feld, w.get('rechner_wert'))}); "
                          f"die entschiedene Parametrierung ({_lesart_text(feld, w.get('spez_wert'))}) "
                          "prüft nicht dieser Vergleich, sondern die aktuariellen Tests."
                          for feld, w in (gm.get("gegenprobe") or {}).items())),
                stand_satz, kern_satz,
                entscheid_satz("A-K2", True) if any(e.get("gate") == "A-K2" for e in entscheide) else "",
                entscheid_satz("A-T1", True) if any(e.get("gate") == "A-T1" for e in entscheide) else ""],
            8: [lauf_satz("P-B1"),
                (f"Verankerung: {_zahl(verankerung.get('getragen') or 0)} von "
                 f"{_zahl(verankerung.get('vertraege') or 0)} Verträgen getragen, "
                 f"Restsumme {_zahl(verankerung.get('residuum_summe') or 0, 2)} €, "
                 f"größter Rest {grafik.cent(verankerung.get('residuum_max_abs') or 0)}."
                 if verankerung.get("vorhanden") else "")],
            9: [abnahme_satz("A-M1"), entscheid_satz("A-M1")],
            10: [abnahme_satz("A-M2"), entscheid_satz("A-M2")],
            11: [abnahme_satz("A-M3"), entscheid_satz("A-M3")],
            12: [f"{_zahl(ctrl.get('bestanden') or 0)} von "
                 f"{_zahl(ctrl.get('anzahl') or 0)} Verträgen bestanden, geprüft zu zwei Stichtagen "
                 f"({dat(ctrl.get('stichtag_1'))} und {dat(ctrl.get('stichtag_2'))}), "
                 f"{_zahl(cv.get('anzahl_werte') or 0)} Werte nachgerechnet, "
                 f"{_zahl(ctrl.get('pruefluecken') or 0)} Prüflücken, größte "
                 f"Abweichung {grafik.cent(cv.get('max_abs_residuum') or 0)}."
                 if ctrl.get("anzahl") else "",
                 lauf_satz("A-M4"), entscheid_satz("A-M4") + gebunden],
            13: [entscheid_satz("A-B2"), probe_satz, zugang_satz,
                 (f"Zum {dat(ueb0.get('stichtag'))} treten "
                  f"{_zahl(ueb0.get('vertraege') or 0)} Verträge als Zugang in den "
                  f"geführten Bestand ein; Stand {dat(betrieb.get('stand'))}: "
                  f"{_zahl(bst.get('in_force') or 0)} Verträge in Kraft, davon "
                  f"{_zahl(bst.get('uebernommen_in_force') or 0)} aus Übernahmen"
                  + (" ([Bestandsführung](../../geschaeftsentwicklung/))."
                     if unterseite else "."))
                 if betrieb.get("vorhanden")
                 else "*(Der geführte Bestand liegt dieser Seite nicht vor.)*",
                 # Die Freigabe des Stands nach aussen, im Fall gezeichnet.
                 entscheid_satz("A-B1", True) if any(e.get("gate") == "A-B1" for e in entscheide)
                 else ""],
        }

        aus: List[str] = []
        register_pfad = "../pruefgates.html" if unterseite else "migrationen/pruefgates.html"
        for nummer, titel, kennung in darstellung.WEG_STATIONEN:
            anker = darstellung.STATION_ABSCHNITT[nummer]
            aus += [f"## Station {nummer} · {titel} {{#{anker}}}", ""]
            # Das Gate der Station, dann die Abnahmen, die sie mittraegt —
            # soweit der Fall sie beruehrt (Entscheid, Lauf oder Abnahme
            # des Stands). Was der Fall nicht kennt, steht hier nicht.
            beruehrt = ({str(e.get("gate")) for e in entscheide}
                        | {str(g.get("gate", "")).split(".")[0] for g in gates}
                        | {str(st.get("gate")) for st in abn.get("standabnahmen") or []})
            weitere = [w for w in darstellung.STATION_WEITERE_GATES.get(nummer, ()) if w in beruehrt]
            # Was ein Gate prueft, steht EINMAL im Register (Bestandsmigrationen,
            # Pruefgates); hier nur das Kuerzel als Verweis auf seine Zeile
            # (Maintainer 06.10.2026: die Kaesten wiederholten das Register an
            # jeder Station, an Station 7 viermal).
            gate_links = [f"[`{k}` **{darstellung.GATE_TITEL.get(register[k].name, register[k].name)}**]"
                          f"({register_pfad}#{k})"
                          for k in ([kennung] if kennung else []) + weitere if k in register]
            if gate_links:
                aus += [("Gates: " if len(gate_links) > 1 else "Gate: ")
                        + ", ".join(gate_links) + ".", ""]
            text = " ".join(x for x in geschehen.get(nummer, []) if x)
            if text:
                aus += [text, ""]
            # Die Begruendung eines Entscheids steht in seinem Snapshot; die
            # Seite zitiert sie nicht (Entscheid des Maintainers 04.10.2026).
            for zeile in zahlen.get(nummer) or []:
                aus.append(zeile)
            if zahlen.get(nummer):
                aus.append("")
            aus += _belege(nummer)
            aus += _kettenbelege(nummer)
        return aus

    def kapitel(zeilen: List[str]) -> List[str]:
        """Ein Rahmenkapitel. Die Bloecke tragen ihre Ueberschrift als
        Seitentitel (``# …``) aus der Zeit, als jeder eine eigene Seite
        war; im fortlaufenden Text wird daraus ein Kapitel."""
        if not zeilen:
            return []
        inhalt = list(zeilen)
        if inhalt[0].startswith("# "):
            inhalt[0] = "#" + inhalt[0]
        return inhalt + [""]

    z += _stationen({1: s_lieferung, 5: s_widerspruch, 6: s_uebersetzung,
                     9: s_stichprobe, 12: s_controlling, 13: s_bestand})
    z += kapitel(s_ergebnis)
    z += kapitel(_aufwand_abschnitt(modell, link))
    z += kapitel(s_umbau)
    z += kapitel(s_grenzen)
    # Das Verzeichnis der Belege ist eine eigene Seite (Maintainer 06.10.2026:
    # Dateien, Pruefsummen und Ledger gehoeren nicht in den Lesefluss); die
    # Fallseite verweist darauf.
    z += ["## Verzeichnis der Belege {#belege}", "",
          "Alle Berichte und Dateien dieses Falls nach Station, alle Prüfläufe und",
          "die Entscheide: [Verzeichnis der Belege](belege.html).", ""]
    z.extend(fuss())
    b = [s_belege[0], "",
         '<nav class="kopf">'
         + ('<a href="../../">← Startseite</a>'
            '<a href="../">← Bestandsmigrationen</a>'
            '<a href="./">← Die Übernahme</a>' if unterseite
            else '<a href="index.md">← Die Übernahme</a>')
         + "</nav>", ""] + s_belege[1:]
    b.extend(fuss())
    return {"index.md": "\n".join(z) + "\n", "belege.md": "\n".join(b) + "\n"}

def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description="Vorzeigeseite eines Laufs bauen.")
    p.add_argument("--fall", required=True, help="Fall-Arbeitsbereich")
    p.add_argument("--daten", required=True,
                   help="Datenmodell der Falldarstellung "
                        "(werkzeuge/falldaten.py --out <datei>.json) — "
                        "dieselbe Datei, aus der auch der Fallbericht "
                        "gerendert wird")
    p.add_argument("--out", required=True, help="Zielverzeichnis der Seite")
    p.add_argument("--verlauf", default=None,
                   help="Verlaufsprotokoll der OPERATOR-Sitzung "
                        "(werkzeuge/verlaufsprotokoll.py --sitzung <uuid>). "
                        "Nicht --neueste nehmen: das ist womoeglich die "
                        "Sitzung, die das Werkzeug gebaut hat.")
    p.add_argument("--repo", default=".", help="Repo-Wurzel fuer den Systemstand")
    p.add_argument("--als-unterseite", action="store_true",
                   help="Fall-Seite als Teil des Unternehmensauftritts bauen "
                        "(migrationen/<fall>/): keine eigene _config.yml — "
                        "die gehoert der Wurzel — und ein Rueckverweis auf "
                        "die Migrations-Uebersicht")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2

    daten = Path(args.daten).resolve()
    modell = _lies_json(daten)
    if not isinstance(modell, dict) or "fall" not in modell:
        print(f"Kein Falldaten-Modell: {daten}", file=sys.stderr)
        return 2
    # Modell und Fall muessen zusammengehoeren: Die Seite legt die
    # Artefakte DIESES Falls als Belege neben die Zahlen des Modells —
    # stammen die Zahlen aus einem anderen Fall, belegen sie nichts.
    manifest = _lies_json(fall / "fall.json") or {}
    if (modell["fall"] or {}).get("name") != (manifest.get("name") or fall.name):
        print(f"Modell und Fall passen nicht zusammen: "
              f"{(modell['fall'] or {}).get('name')!r} gegen "
              f"{manifest.get('name')!r}. Das Modell mit "
              "werkzeuge/falldaten.py aus DIESEM Fall erzeugen.",
              file=sys.stderr)
        return 2

    ziel = Path(args.out).resolve()
    ziel.mkdir(parents=True, exist_ok=True)

    try:
        # Innerhalb des try, damit auch der Regie-Abbruch als Meldung
        # herauskommt und nicht als Traceback — er ist ein erwartetes
        # Urteil ueber die Eingabe, kein Defekt des Werkzeugs.
        _pruefe_regie(fall)
        _pruefe_regie(daten)
        kopiert, bereinigt = _kopiere(fall, ziel, modell)
        ansichten = _lieferung_ansichten(
            fall, ziel,
            (modell.get("lieferung") or {}).get("quellen") or [], kopiert)
        if ((modell.get("transformation") or {}).get("vorhanden")
                and not (fall / "abgeleitet" / "berichte"
                         / "uebersetzungsbericht.html").is_file()):
            (ziel / "uebersetzung.html").write_text(
                _uebersetzungsbericht(modell), encoding="utf-8")
        verlauf_text = None
        if args.verlauf:
            quelle = Path(args.verlauf).resolve()
            _pruefe_regie(quelle)
            verlauf_text = quelle.read_text(encoding="utf-8")
            (ziel / "verlauf.md").write_text(verlauf_text, encoding="utf-8")
        (ziel / "entscheide.md").write_text(
            _entscheide_seite(fall, modell, kopiert, args.als_unterseite,
                              dt.date.today().isoformat(),
                              _systemstand(Path(args.repo).resolve()),
                              bereinigt=bereinigt),
            encoding="utf-8")
        for name, text in _seiten(
                fall, modell, Path(args.repo).resolve(), kopiert,
                verlauf_text, unterseite=args.als_unterseite,
                ansichten=ansichten, bereinigt=bereinigt).items():
            (ziel / name).write_text(text, encoding="utf-8")
        # Jekyll rendert die Markdown-Seiten; ohne Konfiguration nimmt
        # GitHub Pages ein Vorgabethema, das die Tabellen bricht. Als
        # Unterseite gehoert die Konfiguration der Wurzel des
        # Unternehmensauftritts (unternehmensseite.py), nicht dem Fall.
        if not args.als_unterseite:
            (ziel / "_config.yml").write_text(JEKYLL, encoding="utf-8")
        # Die Wache liest jede geschriebene Datei: kein Hostpfad, kein
        # gesperrtes Wort. Was keine Regel kennt, wird nicht still ersetzt.
        funde = bereinigung.wache(ziel)
        if funde:
            raise VeroeffentlichungFehler(
                "Wache: " + "; ".join(f"{rel} traegt {m!r}" for rel, m in funde[:10])
                + (f" (und {len(funde) - 10} weitere)" if len(funde) > 10 else "")
                + " — nicht veroeffentlichen; eine Regel ergaenzen oder die Datei "
                "zurueckhalten (werkzeuge/bereinigung.py)")
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}/index.md geschrieben")
    print(f"  {len(kopiert)} Artefakte kopiert, davon {len(bereinigt['bereinigt'])} bereinigt; "
          f"{len(bereinigt['zurueckgehalten'])} zurueckgehalten (artefakte/{bereinigung.MANIFEST})")
    if verlauf_text:
        print(f"  Verlaufsprotokoll uebernommen ({len(verlauf_text):,} Zeichen)")
    # Luecken stehen auf der Seite selbst (_grenzen) UND setzen
    # den Exit-Code (T20-03): Wer nur den letzten Render-Schritt sieht,
    # darf einen unvollstaendigen Fall nicht fuer einen fertigen
    # Veroeffentlichungsentwurf halten. Exit 3 = geschrieben, mit Luecken.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    offene = luecken(modell)
    for l in offene:
        print(f"  LUECKE im Modell: {l.get('was')} — steht auf der Seite "
              "unter 'Grenzen dieses Laufs'.", file=sys.stderr)
    print()
    print("Vor der Veroeffentlichung von Hand pruefen:")
    print("  - Stehen Klarnamen im Verlaufsprotokoll?")
    print("  - Ist der Simulationshinweis oben noch zutreffend?")
    print("  - Traegt die Seite etwas, das die Vorfuehrung verrät?")
    print()
    print("Veroeffentlichen (der Mensch, bewusst — siehe werkzeuge/README.md):")
    print(f"  git worktree add /tmp/gh-pages gh-pages")
    print(f"  cp -r {ziel}/. /tmp/gh-pages/")
    print(f"  cd /tmp/gh-pages && git add -A && git commit && git push")
    return 3 if offene else 0


if __name__ == "__main__":
    raise SystemExit(main())
