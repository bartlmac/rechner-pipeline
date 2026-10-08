"""Pruefung der gebauten Seite vor der Veroeffentlichung — fuenf Pruefungen
mit einem Aufruf.

Bis zum 08.10.2026 lagen diese Pruefungen nur im Arbeitsordner der
Seiten-Sitzung und liefen, wenn jemand daran dachte. Entscheid des
Maintainers (04.10.2026): Sie gehoeren nach ``werkzeuge/``, damit jede
Veroeffentlichung sie faehrt.

* ``verweise``: Jeder relative Verweis (href, src) der gerenderten Vorschau
  trifft eine Datei, jedes Sprungziel ``#x`` eine id oder einen name in
  ihr. Ein absoluter Pfad ab ``/`` gilt als tot: Die Sichtung liefert unter
  einem Pfad-Praefix aus. Ein Verweis in einem Beleg (``artefakte/``,
  ``plv/``) ist ein Hinweis: Belege erscheinen unveraendert.
* ``pages``: Was Pages anders liest als die Vorschau, steht nicht im
  Push-Baum: eine Ueberschrift, die auf eine Attributliste ``{: ...}``
  endet; Liquid ausserhalb von raw; eine Formel in ``$...$``.
* ``paket``: Jede Datei des Stands-Pakets unter ``plv/`` traegt die
  Pruefsumme, die ``stand.json`` fuer sie nennt; unter ``plv/`` liegt nichts
  ohne Eintrag; was nicht veroeffentlicht ist, sind nur die Parquet-Tabellen;
  jeder Bericht unter ``berichte/`` ist bytegleich mit einer Datei des
  Pakets.
* ``pruefsummen``: Jede hexadezimale Kennung (8 bis 64 Zeichen), die eine
  Seite anzeigt, gehoert zu einer bekannten Quelle — Datei des Falls,
  Manifest der Bereinigung, Snapshot, Lieferregister, Paket, Anker,
  Protokoll — oder ist ein Commit des Codebaums. Eine Kennung ohne Quelle
  behauptet etwas, das niemand nachschlagen kann.
* ``breite``: Auf dem Telefon (390 Pixel) ist keine Hauptseite breiter als
  der Bildschirm (:data:`HAUPTSEITEN`); was breiter ist, verschiebt sich in
  seinem eigenen Rahmen. Jede andere Seite wird mitgemessen und als Hinweis
  genannt, nicht als Befund: Am 08.10.2026 waren es 40 von 114, fast alle
  eigenstaendige Berichte der Laufzeit und Fachdokumente mit breiten
  Tabellen — der Entscheid vom 04.10.2026 gibt der Ansicht am Schreibtisch
  Vorrang. Braucht Playwright (Werkstattausruestung wie bei ``schau.py``);
  fehlt es, sagt ``alle`` das ausdruecklich, statt still zu ueberspringen.

Aufruf (``alle`` faehrt alle fuenf, Exit 1 bei einem Befund)::

    python werkzeuge/seitenpruefung.py alle --seite runs/<bau>/seite \\
        --vorschau runs/<bau>/vorschau --fall faelle/<fall> --name <kurzname> \\
        --paket <stands-paket> --anker <anker>/anker.jsonl \\
        --daten runs/<bau>/falldaten.json --repo .

Jede Pruefung einzeln: ``verweise <vorschau>``, ``pages <seite>``,
``paket <seite> <paket>``,
``pruefsummen ...`` (dieselben Angaben wie ``alle`` ohne ``--vorschau``),
``breite <vorschau> --name <kurzname>``.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple

#: Breite des Telefons in CSS-Pixeln (wie ``schau.py``, Ansicht "handy").
TELEFON = 390
#: Die Seiten, die auf dem Telefon bildschirmbreit bleiben MUESSEN —
#: Einstieg, Geschaeftsentwicklung, Migrationen und die Seiten des Falls.
HAUPTSEITEN = ("index.html", "geschaeftsentwicklung/index.html", "migrationen/index.html",
               "migrationen/{name}/index.html", "migrationen/{name}/entscheide.html")


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


# --------------------------------------------------------------------------- #
# Verweise
# --------------------------------------------------------------------------- #

def verweise(vorschau: Path) -> Tuple[List[str], str]:
    """Befunde und Zusammenfassung der Verweise einer gerenderten Vorschau.

    Folgt Verzeichnis-Symlinks: Die Vorschau verlinkt Teile der Seite als
    Symlink, und ``rglob`` folgt ihnen nicht (bis 04.10.2026 sah die
    Pruefung so 52 von 66 Seiten). Liest Attribute in doppelten und in
    einfachen Anfuehrungszeichen; bis 08.10.2026 nur doppelte, und zwei tote
    Verweise im Bericht der Migrationsabnahme blieben ungesehen. Ein Verweis
    in einem Beleg ist ein Hinweis, kein Befund: Belege des Falls und das
    Stands-Paket erscheinen Byte fuer Byte, wie sie gezeichnet wurden."""
    wurzel = Path(os.path.normpath(vorschau.absolute()))
    ids: Dict[Path, Set[str]] = {}

    def ids_von(datei: Path) -> Set[str]:
        if datei not in ids:
            text = (datei.read_text(encoding="utf-8", errors="replace")
                    if datei.suffix in (".html", ".htm", ".svg") else "")
            ids[datei] = {a or b for a, b in re.findall(
                r"""\b(?:id|name)\s*=\s*(?:"([^"]+)"|'([^']+)')""", text)}
        return ids[datei]

    seiten = sorted(Path(d) / f for d, _, fs in os.walk(wurzel, followlinks=True)
                    for f in fs if f.endswith(".html"))
    befunde: List[str] = []
    hinweise: List[str] = []
    gesamt, extern = 0, collections.Counter()
    for seite in seiten:
        rel = seite.relative_to(wurzel).as_posix()
        beleg = "artefakte" in rel.split("/") or rel.startswith("plv/")
        for a, b in re.findall(r"""\b(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)')""",
                               seite.read_text(encoding="utf-8", errors="replace")):
            ziel = html.unescape(a or b).strip()
            if not ziel or ziel.startswith(("mailto:", "javascript:", "data:")):
                continue
            if re.match(r"^[a-z][a-z0-9+.-]*:", ziel, re.I):
                extern[urllib.parse.urlparse(ziel).netloc] += 1
                continue
            gesamt += 1
            pfad, _, sprung = ziel.partition("#")
            pfad = urllib.parse.unquote(pfad.split("?")[0])
            if pfad.startswith("/"):
                (hinweise if beleg else befunde).append(f"{rel}: {ziel} — absoluter Pfad")
                continue
            z = Path(os.path.normpath(seite.parent / pfad)) if pfad else seite
            if z.is_dir():
                z = z / "index.html"
            if not z.exists():
                (hinweise if beleg else befunde).append(f"{rel}: {ziel} — kein Ziel")
                continue
            if wurzel not in z.parents and z != wurzel:
                (hinweise if beleg else befunde).append(f"{rel}: {ziel} — ausserhalb der Vorschau")
                continue
            if sprung and z.suffix in (".html", ".htm") and urllib.parse.unquote(sprung) not in ids_von(z):
                (hinweise if beleg else befunde).append(f"{rel}: {ziel} — kein Sprungziel")
    zusammen = (f"{gesamt} relative Verweise in {len(seiten)} HTML-Seiten, "
                f"{len(befunde)} Befunde; extern: {dict(sorted(extern.items()))}; "
                f"in Belegen ohne Ziel: {len(hinweise)}")
    for h in hinweise:
        zusammen += f"\n  HINWEIS {h} (Beleg, unveraendert veroeffentlicht)"
    return befunde, zusammen


# --------------------------------------------------------------------------- #
# Pages
# --------------------------------------------------------------------------- #

#: Eine Attributliste ``{: ...}`` am Ende einer Ueberschrift.
_KOPF_MIT_LISTE = re.compile(r"^#{1,6}[ \t].*\{:[^}]*\}[ \t]*$")
#: Ein raw-Block (zaehlt nicht) oder ein Liquid-Anfang ausserhalb davon.
_LIQUID = re.compile(r"\{%-?\s*raw\s*-?%\}.*?\{%-?\s*endraw\s*-?%\}|\{\{|\{%", re.S)
#: Was beim Suchen nach ``$...$`` nicht zaehlt (Codeblock, Codespan, Skript,
#: Formel in ``$$...$$``) und die Formel in ``$...$`` selbst (``formel``).
_FORMEL = re.compile(
    r"^(?P<zaun>```|~~~)[^\n]*\n.*?^(?P=zaun)[ \t]*$"
    r"|(?P<striche>`+)(?:(?!\n[ \t]*\n).)+?(?<!`)(?P=striche)(?!`)"
    r"|<script\b.*?</script>"
    r"|\$\$.+?\$\$"
    r"|(?P<formel>\$[^$\n]+?\$)",
    re.S | re.M | re.I)


def pages(seite: Path) -> Tuple[List[str], str]:
    """Befunde und Zusammenfassung dessen, was Pages anders liest als die Vorschau.

    Pages rendert mit Jekyll 3: erst Liquid, dann kramdown (Eingabe GFM). Die
    Vorschau rendert mit Python-Markdown und sieht drei Dinge nicht, die live
    anders oder gar nicht ankommen (gemessen mit dem Renderer von Pages am
    08.10.2026):

    * Eine Ueberschrift, die auf ``{: #x }`` endet. attr_list liest das als id,
      kramdown nur ``{#x}``; die Attributliste zeigt es als Text (47
      Ueberschriften bis 308e959).
    * Liquid ausserhalb von raw. ``{{`` und ``{%`` wertet Liquid aus, ein
      unvollstaendiges ``{{`` bricht den ganzen Build ab (KLV-Tarifplan).
    * Eine Formel in ``$...$``. Fuer kramdown ist das Text, Escapes,
      Hervorhebung und Typografie laufen darueber (35 von 489 Formeln).

    Fuer Ueberschriften und Formeln zaehlen Codebloecke nicht; Liquid liest
    auch sie."""
    befunde: List[str] = []
    dateien = sorted(seite.rglob("*.md"))
    for md in dateien:
        rel = md.relative_to(seite).as_posix()
        text = md.read_text(encoding="utf-8")
        im_code = False
        for nr, zeile in enumerate(text.splitlines(), 1):
            if zeile.lstrip().startswith(("```", "~~~")):
                im_code = not im_code
            elif not im_code and _KOPF_MIT_LISTE.match(zeile):
                befunde.append(f"{rel}:{nr}: {zeile.strip()} — Pages zeigt die Liste als Text, "
                               f"die id nur aus {{#...}}")
        for m in _LIQUID.finditer(text):
            if m.group(0) in ("{{", "{%"):
                befunde.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: {m.group(0)} "
                               f"ausserhalb von raw — Liquid wertet es aus oder bricht ab")
        for m in _FORMEL.finditer(text):
            if m.group("formel"):
                befunde.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}: "
                               f"{m.group('formel')[:60]} — kramdown liest $...$ als Text")
    return befunde, f"{len(dateien)} Markdown-Dateien, {len(befunde)} Befunde"


# --------------------------------------------------------------------------- #
# Paket
# --------------------------------------------------------------------------- #

def paket(seite: Path, stands_paket: Path) -> Tuple[List[str], str]:
    """Befunde und Zusammenfassung des Abgleichs ``plv/`` und ``berichte/``
    gegen ``stand.json`` des Stands-Pakets."""
    stand = json.loads((stands_paket / "stand.json").read_text(encoding="utf-8"))
    dateien: Dict[str, str] = stand.get("dateien") or {}
    plv = seite / "plv"
    befunde: List[str] = []
    gleich, nicht = 0, []
    for name, summe in sorted(dateien.items()):
        z = plv / name
        if not z.exists():
            nicht.append(name)
        elif _sha(z) == summe:
            gleich += 1
        else:
            befunde.append(f"plv/{name}: weicht von stand.json ab")
    for name in nicht:
        if not name.endswith(".parquet"):
            befunde.append(f"plv/{name}: in stand.json, aber nicht veroeffentlicht")
    if plv.is_dir():
        for p in sorted(plv.rglob("*")):
            rel = p.relative_to(plv).as_posix()
            if p.is_file() and rel not in dateien:
                befunde.append(f"plv/{rel}: ohne Eintrag in stand.json")
    berichte = seite / "berichte"
    kopien = sorted(p for p in berichte.rglob("*") if p.is_file()) if berichte.is_dir() else []
    for p in kopien:
        if dateien.get(p.name) != _sha(p):
            befunde.append(f"berichte/{p.relative_to(berichte).as_posix()}: "
                           "keine bytegleiche Datei des Pakets")
    zusammen = (f"plv/: {gleich} Dateien gleich stand.json, {len(nicht)} nicht "
                f"veroeffentlicht; berichte/: {len(kopien)} Kopien; {len(befunde)} Befunde")
    return befunde, zusammen


# --------------------------------------------------------------------------- #
# Pruefsummen
# --------------------------------------------------------------------------- #

def _hexwerte(x) -> Iterator[str]:
    if isinstance(x, dict):
        for v in x.values():
            yield from _hexwerte(v)
    elif isinstance(x, list):
        for v in x:
            yield from _hexwerte(v)
    elif isinstance(x, str) and re.fullmatch(r"[0-9a-f]{8,}", x):
        yield x


def bekannte_kennungen(seite: Path, fall: Path, name: str, stands_paket: Path,
                       anker: Path, daten: Path) -> Dict[str, str]:
    """Jede volle Kennung, die eine Quelle traegt, mit dem Namen der Quelle."""
    bekannt: Dict[str, Set[str]] = collections.defaultdict(set)
    modell = json.loads(daten.read_text(encoding="utf-8"))
    for e in ((modell.get("belegkette") or {}).get("dateien") or {}).values():
        bekannt["Datei des Falls"].add(e.get("sha256") or "")
    manifest = seite / "migrationen" / name / "artefakte" / "bereinigung.json"
    if manifest.is_file():
        m = json.loads(manifest.read_text(encoding="utf-8"))
        for e in m.get("bereinigt") or []:
            bekannt["Manifest"].update([e.get("sha256_original") or "",
                                        e.get("sha256_veroeffentlicht") or ""])
        for e in m.get("zurueckgehalten") or []:
            bekannt["Manifest"].add(e.get("sha256") or "")
    for p in sorted((fall / "entscheide").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        bekannt["Snapshot"].update([d.get("snapshot_sha256") or "", _sha(p),
                                    p.stem.split("-", 2)[-1]])
        bekannt["Angabe in einem Snapshot"].update(_hexwerte(d))
    eingang = fall / "eingang.json"
    if eingang.is_file():
        for q in json.loads(eingang.read_text(encoding="utf-8")).get("quellen") or []:
            bekannt["Lieferregister"].add(q.get("sha256") or "")
    stand = json.loads((stands_paket / "stand.json").read_text(encoding="utf-8"))
    bekannt["Paket"].update(_hexwerte(stand))
    bekannt["Paket"].update(_sha(p) for p in stands_paket.rglob("*") if p.is_file())
    for zeile in anker.read_text(encoding="utf-8").splitlines():
        if zeile.strip():
            bekannt["Anker"].update(_hexwerte(json.loads(zeile)))
    if (seite / "plv").is_dir():
        for p in sorted((seite / "plv").rglob("*.json*")):
            for zeile in p.read_text(encoding="utf-8").splitlines():
                try:
                    bekannt["Protokoll des Pakets"].update(_hexwerte(json.loads(zeile)))
                except ValueError:
                    pass
    return {w: q for q, ws in bekannt.items() for w in ws if w}


def pruefsummen(seite: Path, fall: Path, name: str, stands_paket: Path, anker: Path,
                daten: Path, repo: Path) -> Tuple[List[str], str]:
    """Befunde und Zusammenfassung: jede angezeigte Kennung mit ihrer Quelle.

    Nicht gelesen werden die Belege selbst (``migrationen/<name>/artefakte/``,
    ``plv/``, ``berichte/``: sie SIND die Quellen), Farben und Skripte."""
    alle = bekannte_kennungen(seite, fall, name, stands_paket, anker, daten)
    commits: Dict[str, bool] = {}

    def quelle(kennung: str) -> Optional[str]:
        for wert, q in alle.items():
            if wert.startswith(kennung):
                return q
        if kennung not in commits:
            commits[kennung] = subprocess.run(
                ["git", "-C", str(repo), "cat-file", "-e", kennung + "^{commit}"],
                capture_output=True).returncode == 0
        return "Commit" if commits[kennung] else None

    ausgenommen = (f"migrationen/{name}/artefakte/", "plv/", "berichte/")
    gefunden: collections.Counter = collections.Counter()
    befunde: List[str] = []
    for p in sorted(seite.rglob("*")):
        rel = p.relative_to(seite).as_posix()
        if not p.is_file() or rel.startswith(ausgenommen) or p.suffix not in (".md", ".html"):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"<(style|script)\b.*?</\1>", "", text, flags=re.S)
        text = re.sub(r"#[0-9a-fA-F]{3,8}\b", "", text)
        for k in sorted(set(re.findall(r"(?<![0-9a-zA-Z_/.-])([0-9a-f]{8,64})(?![0-9a-zA-Z_])", text))):
            if not re.search(r"[a-f]", k) or not re.search(r"[0-9]", k):
                continue   # reine Ziffern (Policennummern) oder Woerter
            q = quelle(k)
            if q:
                gefunden[q] += 1
            else:
                befunde.append(f"{rel}: {k} — ohne Quelle")
    zusammen = f"zugeordnet: {dict(sorted(gefunden.items()))}; ohne Quelle: {len(befunde)}"
    return befunde, zusammen


# --------------------------------------------------------------------------- #
# Breite auf dem Telefon
# --------------------------------------------------------------------------- #

def breite(vorschau: Path, name: str) -> Tuple[List[str], str]:
    """Befunde und Zusammenfassung der Breite je Seite auf dem Telefon.

    Befund ist eine zu breite Hauptseite und eine Hauptseite, die fehlt;
    jede andere zu breite Seite steht als Hinweis in der Zusammenfassung.
    Wirft ``ImportError``, wenn Playwright fehlt."""
    from playwright.sync_api import sync_playwright

    wurzel = Path(os.path.normpath(vorschau.absolute()))
    pflicht = [s.format(name=name) for s in HAUPTSEITEN]
    alle = sorted((Path(d) / f).relative_to(wurzel).as_posix()
                  for d, _, fs in os.walk(wurzel, followlinks=True) for f in fs if f.endswith(".html"))
    befunde = [f"{rel}: Hauptseite fehlt in der Vorschau" for rel in pflicht if rel not in alle]
    hinweise: List[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        s = browser.new_page(viewport={"width": TELEFON, "height": 844})
        for rel in alle:
            s.goto((wurzel / rel).as_uri())
            s.wait_for_load_state("networkidle")
            w = s.evaluate("document.documentElement.scrollWidth")
            if w > TELEFON:
                (befunde if rel in pflicht else hinweise).append(
                    f"{rel}: {w} Pixel breit statt {TELEFON}")
        browser.close()
    zusammen = (f"{len(alle)} Seiten bei {TELEFON} Pixeln; Hauptseiten: {len(pflicht)}, "
                f"Befunde: {len(befunde)}; breiter als das Telefon, ohne Pflicht: {len(hinweise)}")
    for h in hinweise:
        zusammen += f"\n  HINWEIS {h}"
    return befunde, zusammen


# --------------------------------------------------------------------------- #
# Aufruf
# --------------------------------------------------------------------------- #

def _melde(titel: str, ergebnis: Tuple[List[str], str]) -> int:
    befunde, zusammen = ergebnis
    print(f"{titel}: {zusammen}")
    for b in befunde[:40]:
        print(f"  BEFUND {b}")
    if len(befunde) > 40:
        print(f"  ... und {len(befunde) - 40} weitere")
    return 1 if befunde else 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    teil = p.add_subparsers(dest="pruefung", required=True)

    def gemeinsam(q: argparse.ArgumentParser) -> None:
        q.add_argument("--seite", required=True, help="Push-Baum der Seite (auftritt.py --out)")
        q.add_argument("--fall", required=True, help="Fallverzeichnis (auftritt.py --fall)")
        q.add_argument("--name", required=True, help="Kurzname des Falls (auftritt.py --name)")
        q.add_argument("--paket", required=True, help="Stands-Paket (auftritt.py --stands-paket)")
        q.add_argument("--anker", required=True, help="Ankerdatei (auftritt.py --anker)")
        q.add_argument("--daten", required=True, help="Datenmodell des Baus (falldaten.json)")
        q.add_argument("--repo", default=".", help="Codebaum, in dem Commits nachgeschlagen werden")

    q = teil.add_parser("verweise", help="Verweise und Sprungziele der Vorschau")
    q.add_argument("vorschau")
    q = teil.add_parser("pages", help="was Pages anders liest als die Vorschau")
    q.add_argument("seite")
    q = teil.add_parser("paket", help="plv/ und berichte/ gegen stand.json")
    q.add_argument("seite")
    q.add_argument("paket")
    q = teil.add_parser("pruefsummen", help="jede angezeigte Kennung mit Quelle")
    gemeinsam(q)
    q = teil.add_parser("breite", help="Breite auf dem Telefon (braucht Playwright)")
    q.add_argument("vorschau")
    q.add_argument("--name", required=True, help="Kurzname des Falls (auftritt.py --name)")
    q = teil.add_parser("alle", help="alle fuenf Pruefungen")
    gemeinsam(q)
    q.add_argument("--vorschau", required=True, help="gerenderte Vorschau (auftritt.py --vorschau)")
    args = p.parse_args(argv)

    if args.pruefung == "verweise":
        return _melde("Verweise", verweise(Path(args.vorschau)))
    if args.pruefung == "pages":
        return _melde("Pages", pages(Path(args.seite)))
    if args.pruefung == "paket":
        return _melde("Paket", paket(Path(args.seite), Path(args.paket)))
    if args.pruefung == "breite":
        try:
            return _melde("Breite", breite(Path(args.vorschau), args.name))
        except ImportError:
            print("playwright fehlt: .venv/bin/pip install playwright && "
                  ".venv/bin/playwright install chromium", file=sys.stderr)
            return 2
    summen = (Path(args.seite), Path(args.fall), args.name, Path(args.paket),
              Path(args.anker), Path(args.daten), Path(args.repo))
    if args.pruefung == "pruefsummen":
        return _melde("Pruefsummen", pruefsummen(*summen))
    rc = _melde("Verweise", verweise(Path(args.vorschau)))
    rc |= _melde("Pages", pages(Path(args.seite)))
    rc |= _melde("Paket", paket(Path(args.seite), Path(args.paket)))
    rc |= _melde("Pruefsummen", pruefsummen(*summen))
    try:
        rc |= _melde("Breite", breite(Path(args.vorschau), args.name))
    except ImportError:
        print("Breite: NICHT GEPRUEFT — playwright fehlt (.venv/bin/pip install "
              "playwright && .venv/bin/playwright install chromium)")
    print("SEITENPRUEFUNG " + ("mit Befund" if rc else "ohne Befund"))
    return rc


if __name__ == "__main__":
    sys.exit(main())
