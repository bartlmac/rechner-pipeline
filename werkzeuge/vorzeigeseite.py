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
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

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

#: Was von einem Fall auf die Seite gehoert. Alles Uebrige bleibt
#: draussen; eine Positivliste ist sicherer als eine Sperrliste.
UEBERNEHMEN = (
    ("eingang.json", "Register der gelieferten Quellen"),
    ("fall.json", "Fallmanifest mit Scope"),
    ("abgeleitet/berichte", "Berichte des Laufs"),
    # Konventionspfad der Fortschreibung (Skill migrationsfall-
    # durchfuehren; bestand.cli_fortschreibung --uebernahme schreibt
    # dorthin). Ad-hoc benannte Zwischenstaende eines Durchgangs
    # gehoeren NICHT in diese Liste.
    ("abgeleitet/bestand-nach", "Fortschreibung des uebernommenen Bestands"),
    ("abgeleitet/diagnostics", "Gate-Ledger"),
    ("entscheide", "Entscheid-Snapshots der menschlichen Gates"),
)


#: Minimale Jekyll-Konfiguration der veroeffentlichten Seite. Das Thema
#: rendert Tabellen und Code lesbar; die Artefakte werden ausdruecklich
#: NICHT von Jekyll angefasst, damit JSON und CSV unveraendert
#: herunterladbar bleiben.
JEKYLL = """theme: jekyll-theme-cayman
title: Migrationsfall — Vorfuehrung
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
    """Abbrechen, wenn ein Pfad in die Regie zeigt."""
    teile = set(pfad.resolve().parts)
    for verzeichnis in REGIE:
        if verzeichnis in teile:
            raise VeroeffentlichungFehler(
                f"{pfad} liegt unter {verzeichnis!r}. Dort stehen die "
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
    ziel = f"artefakte/{ref}"
    return ziel if ziel in kopiert else None


def _kopiere(fall: Path, ziel: Path) -> List[str]:
    """Die Positivliste in das Zielverzeichnis spiegeln."""
    kopiert: List[str] = []
    for name, _zweck in UEBERNEHMEN:
        quelle = fall / name
        if not quelle.exists():
            continue
        _pruefe_regie(quelle)
        zielpfad = ziel / "artefakte" / name
        if quelle.is_dir():
            for datei in sorted(quelle.rglob("*")):
                if not datei.is_file():
                    continue
                _pruefe_regie(datei)
                unterziel = zielpfad / datei.relative_to(quelle)
                unterziel.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(datei, unterziel)
                kopiert.append(str(unterziel.relative_to(ziel)))
        else:
            zielpfad.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(quelle, zielpfad)
            kopiert.append(str(zielpfad.relative_to(ziel)))
    return kopiert


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
        z.append("Person — hier die der Simulation.")
    else:
        z.append("Das Schlüsselmaterial liegt außerhalb des Falls, und diese")
        z.append("Seite hat es nicht: Sie prüft Schema, Selbstadressierung und")
        z.append("Dateiname jedes Snapshots, **nicht die HMAC-Signatur**. Der")
        z.append("Fingerabdruck in der Tabelle ist eine Angabe der Datei, kein")
        z.append("Nachweis einer Zeichnung. Ein Fall kann seine eigene")
        z.append("menschliche Freigabe nicht behaupten — genau deshalb nennt")
        z.append("diese Seite nichts gezeichnet, was sie nicht verifiziert hat.")
    return z


def _luecken_abschnitt(modell: Dict[str, Any]) -> List[str]:
    """Fehlendes SICHTBAR auf der Seite, nicht nur auf stderr (T20-03)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    offene = luecken(modell)
    if not offene:
        return []
    z = ["## Was diese Seite NICHT zeigt", "",
         "Der Fall trägt die folgenden Angaben nicht. Die Seite lässt sie",
         "offen, statt Vollständigkeit zu behaupten:", ""]
    for l in offene:
        z.append(f"- **{l['was']}** — {l['wirkung']} (`{l['gruppe']}.{l['feld']}`)")
    z.append("")
    return z


def _seite(fall: Path, modell: Dict[str, Any], repo: Path,
           kopiert: List[str], verlauf: Optional[str],
           unterseite: bool = False) -> str:
    stand = _systemstand(repo)
    fallinfo = modell.get("fall") or {}
    kette = modell.get("kette") or {}
    gates = kette.get("gates") or []
    entscheide = kette.get("entscheide") or []
    quellen = (modell.get("lieferung") or {}).get("quellen") or []
    a = modell.get("abnahmen") or {}
    abnahmen = a.get("aktuariell") or []
    controlling = a.get("controlling")
    umbau = modell.get("umbau") or {}
    im_artefakt = set(kopiert)
    heute = dt.date.today().isoformat()

    z: List[str] = []
    z.append(f"# Migrationsfall {fallinfo.get('name') or fall.name}")
    z.append("")
    z.append("> **Dies ist eine Vorführung, kein echter Bestand.** Die")
    z.append("> beteiligten Unternehmen sind frei erfunden, die Verträge")
    z.append("> synthetisch erzeugt. Die Entscheid-Snapshots auf dieser")
    z.append("> Seite tragen den Fingerabdruck eines **Simulationsschlüssels**,")
    z.append("> nicht den eines Verantwortlichen Aktuars. Diese Seite prüft")
    z.append("> Schema, Selbstadressierung und Dateinamen der Snapshots;")
    z.append("> ihre **Signatur verifiziert sie nicht** — dafür fehlt ihr")
    z.append("> bewusst das Schlüsselmaterial. Der Fingerabdruck ist unten")
    z.append("> ausgewiesen.")
    z.append("")
    z.extend(_luecken_abschnitt(modell))
    if unterseite:
        z.append("[← Unsere Bestandsmigrationen](../)")
        z.append("")
    if fallinfo.get("beschreibung"):
        z.append(str(fallinfo["beschreibung"]))
        z.append("")

    z.append("## Provenienz")
    z.append("")
    z.append("| | |")
    z.append("|---|---|")
    z.append(f"| Veröffentlicht | {heute} |")
    z.append(f"| Systemstand | `{stand['commit'][:12]}` auf `{stand['branch']}` |")
    z.append(f"| Arbeitsbaum sauber | {stand['sauber']} |")
    z.append(f"| Scope des Falls | {fallinfo.get('scope') or '?'} |")
    z.append("")

    z.append("## Die Lieferung")
    z.append("")
    z.append("Was das abgebende Unternehmen übergeben hat. In den Fall")
    z.append("gelangt eine Datei ausschließlich über die ausdrückliche")
    z.append("Registrierung — einen impliziten Eingangskanal gibt es nicht.")
    z.append("")
    z.append("| Datei | Bytes | SHA-256 |")
    z.append("|---|---:|---|")
    for q in quellen:
        z.append(f"| `{q.get('datei','?')}` | {q.get('bytes',0):,} "
                 f"| `{str(q.get('sha256',''))[:16]}…` |")
    z.append("")

    z.append("## Das Ergebnis")
    z.append("")
    if not (abnahmen or controlling):
        z.append("*(noch keine Berichte im Fall)*")
        z.append("")
    else:
        z.append("Was bei der Übernahme herausgekommen ist. Die Seite")
        z.append("rechnet nichts nach — jede Zahl steht so in einem")
        z.append("Artefakt, das unter `artefakte/` daneben liegt.")
        z.append("")
    if abnahmen:
        z.append("### Die aktuariellen Abnahmen")
        z.append("")
        z.append("Je Abnahme eine eigene Stichprobe und eigene Kriterien.")
        z.append("Sie prüfen denselben Bestand zu verschiedenen Zeitpunkten.")
        z.append("")
        z.append("| Abnahme | Geprüft wird | Verträge | Befunde | Urteil |")
        z.append("|---|---|---:|---:|---|")
        for t in abnahmen:
            titel, prueft = ABNAHMEN.get(
                t.get("kennung"), (t.get("titel", "?"), ""))
            name = f"{t.get('kennung')} {titel}"
            link = _artefakt_link(fall, t.get("bericht"), im_artefakt)
            if link:
                name = f"[{name}]({link})"
            z.append(f"| {name} | {prueft} | {t.get('anzahl')} "
                     f"| {t.get('fehlgeschlagen')} "
                     f"| {_urteilswort(t.get('urteil'))} |")
        z.append("")
    if controlling:
        c = controlling
        z.append("### Das Migrationscontrolling (A-M4)")
        z.append("")
        z.append("Kein Vertrag und keine Stichprobe, sondern der ganze")
        z.append(f"Bestand über zwei Stichtage ({c['stichtag_1']} und")
        z.append(f"{c['stichtag_2']}).")
        z.append("")
        z.append("| | |")
        z.append("|---|---:|")
        z.append(f"| Geprüfte Verträge | {c['anzahl']} |")
        z.append(f"| Davon bestanden | {c['bestanden']} |")
        z.append(f"| Prüflücken | {c['pruefluecken']} |")
        z.append(f"| Vollständig geprüft | "
                 f"{'ja' if c['vollstaendig_geprueft'] else 'nein'} |")
        z.append("")
        if c["pruefluecken"]:
            z.append("Eine **Prüflücke** ist ein Vertrag, dessen Wert am")
            z.append("Folgestichtag nicht nachgerechnet werden konnte. Der")
            z.append("Bestands-Scope duldet keine: Der Lauf endet dort mit")
            z.append("einem Befund, und das ist die richtige Auskunft — ein")
            z.append("geglätteter Wert wäre eine Behauptung ohne Rechnung.")
            z.append("")
    bestandslinks = [
        link for ref in a.get("bestandsberichte") or []
        for link in [_artefakt_link(fall, ref, im_artefakt)] if link
    ]
    for pfad in bestandslinks:
        z.append(f"* Bestandsbericht: [{Path(pfad).name}]({pfad})")
    if bestandslinks:
        z.append("")
    if umbau.get("vorhanden"):
        offene = umbau.get("befunde") or []
        gesamt = umbau.get("gesamt") or {}
        z.append("### Umfang des Umbaus")
        z.append("")
        z.append("Wie weit dieser Lauf das Zielsystem verändert hat.")
        z.append("")
        z.append(f"Geändert: {gesamt.get('summe','?')} Zeilen in `src/` und")
        z.append(f"`tests/` (Schranke {gesamt.get('vorgabe','?')}).")
        z.append("")
        if not offene:
            z.append("Im Rahmen der vereinbarten Schranken.")
        else:
            wort = ("eine Überschreitung" if len(offene) == 1
                    else f"{len(offene)} Überschreitungen")
            z.append(f"{wort[0].upper()}{wort[1:]}:")
            z.append("")
            for befund in offene:
                z.append(f"* {befund}")
            z.append("")
            begruendung = umbau.get("ueberschreitung_begruendet")
            if begruendung:
                z.append(f"Als Menschentscheidung begründet: „{begruendung}“")
            else:
                z.append("**Ohne Begründung.**")
        z.append("")

    z.append("## Der Lauf")
    z.append("")
    if gates:
        z.append("| Gate | Kommando | Urteil |")
        z.append("|---|---|---|")
        for g in gates:
            z.append(f"| {g['gate']} | `{g['kommando']}` | {g['status']} |")
    else:
        z.append("*(noch keine Gate-Ledger im Fall)*")
    z.append("")

    z.append("## Die menschlichen Entscheide")
    z.append("")
    if entscheide:
        z.append("| Gate | Entscheid | Entscheider | Rolle | Schlüsselklasse | Schlüssel (laut Snapshot) | Prüfstand |")
        z.append("|---|---|---|---|---|---|---|")
        for e in entscheide:
            schl = (f"`{e['schluessel_sha256']}…`"
                    if e.get("schluessel_sha256") else "*(ohne Freigabe-Eintrag)*")
            z.append(f"| {e['gate']} | {e['entscheid']} | {e['entscheider']} "
                     f"| {e['rolle']} | {e.get('schluesselklasse') or '—'} "
                     f"| {schl} | {_pruefstand(e)} |")
        z.append("")
        z.extend(_signaturhinweis(entscheide))
    else:
        z.append("*(noch keine Entscheide im Fall)*")
    z.append("")

    if verlauf:
        z.append("## Verlauf")
        z.append("")
        z.append("Der Ablauf des Laufs, aus dem Sitzungstranskript erzeugt:")
        z.append("[verlauf.md](verlauf.md).")
        z.append("")

    z.append("## Artefakte")
    z.append("")
    z.append(f"{len(kopiert)} Dateien unter `artefakte/`:")
    z.append("")
    for name, zweck in UEBERNEHMEN:
        treffer = [k for k in kopiert if k.startswith(f"artefakte/{name}")]
        if treffer:
            wort = "Datei" if len(treffer) == 1 else "Dateien"
            z.append(f"* `{name}` — {zweck} ({len(treffer)} {wort})")
    z.append("")
    return "\n".join(z) + "\n"


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
        kopiert = _kopiere(fall, ziel)
        verlauf_text = None
        if args.verlauf:
            quelle = Path(args.verlauf).resolve()
            _pruefe_regie(quelle)
            verlauf_text = quelle.read_text(encoding="utf-8")
            (ziel / "verlauf.md").write_text(verlauf_text, encoding="utf-8")
        (ziel / "index.md").write_text(
            _seite(fall, modell, Path(args.repo).resolve(), kopiert,
                   verlauf_text, unterseite=args.als_unterseite),
            encoding="utf-8")
        # Jekyll rendert die Markdown-Seiten; ohne Konfiguration nimmt
        # GitHub Pages ein Vorgabethema, das die Tabellen bricht. Als
        # Unterseite gehoert die Konfiguration der Wurzel des
        # Unternehmensauftritts (unternehmensseite.py), nicht dem Fall.
        if not args.als_unterseite:
            (ziel / "_config.yml").write_text(JEKYLL, encoding="utf-8")
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}/index.md geschrieben")
    print(f"  {len(kopiert)} Artefakte kopiert")
    if verlauf_text:
        print(f"  Verlaufsprotokoll uebernommen ({len(verlauf_text):,} Zeichen)")
    # Luecken stehen auf der Seite selbst (_luecken_abschnitt) UND setzen
    # den Exit-Code (T20-03): Wer nur den letzten Render-Schritt sieht,
    # darf einen unvollstaendigen Fall nicht fuer einen fertigen
    # Veroeffentlichungsentwurf halten. Exit 3 = geschrieben, mit Luecken.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    offene = luecken(modell)
    for l in offene:
        print(f"  LUECKE im Modell: {l.get('was')} — steht auf der Seite "
              "unter 'Was diese Seite NICHT zeigt'.", file=sys.stderr)
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
