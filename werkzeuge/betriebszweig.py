"""``betriebszweig`` — was der Workflow von plv-fiktion aus dem Zweig betrieb nimmt.

Weg C (Entscheid des Maintainers 09.10.2026): Der Tagesbetrieb schiebt jeden
Abend mit einem Deploy-Key in den Zweig ``betrieb`` von plv-fiktion, und nur
dorthin. Der Workflow in ``main`` baut daraus den Betriebsteil der Seite.
Zwei Pruefungen dieses Moduls laufen dort, beide halten den Bau an:

* ``zweig``: Im Zweig liegt genau, was die Routine ablegt, und nichts sonst:
  ``anker.jsonl``, ``A-B1.json`` und unter ``paket/`` die oeffentlichen
  Dateien des Stands-Pakets, flach, jede in ``stand.json`` genannt und keine
  Parquet-Tabelle. Ein Dateiname unter ``paket/`` besteht nur aus a-z, 0-9,
  ``_``, ``.`` und ``-``: Er geht als Verweis in die Seite (Entscheid des
  Maintainers 16.10.2026). Geprueft werden die Dateien, nicht die Liste in
  ``stand.json``; die nennt auch die Abschluesse unter ``abschluesse/``, die
  nicht im Zweig liegen. Jede HTML-Datei des Pakets ist ohne Skript und
  laedt nichts von aussen (``html_befunde``). Keine Datei des Pakets beginnt
  mit einem Vorspann (``---``): Pages gaebe sie sonst durch Jekyll, Liquid
  liefe, und ``permalink`` legte sie an eine Adresse ausserhalb von
  ``betrieb/``, die die Pruefung ``rahmen`` nicht sieht, weil sie vor Jekyll
  laeuft. Ohne Vorspann kopiert Jekyll die Datei unveraendert. Kein Verzeichnis ``.github`` an keiner Stelle: Ein Push
  auf ``betrieb`` startet die Workflows, die im Stand von ``betrieb`` liegen.
  Der Workflow in ``main`` kann das nicht verhindern, aber er liefert dann
  nicht aus, und der Lauf steht sichtbar rot da (ADR-029, Variante
  "Restrisiko benennen"; eine Pfadsperre per Ruleset oder eine GitHub App
  ersetzen diese Pruefung nicht, sie kommen dazu).
* ``rahmen``: Nach dem Bau ist ausserhalb von ``betrieb/`` jede Datei des
  gebauten Baums dieselbe wie im Rahmen aus ``main``, und keine ist dazu
  gekommen oder weggefallen. Automatisch aendert sich nur der Betriebsteil.

Aufruf::

    python werkzeuge/betriebszweig.py zweig <checkout des Zweigs betrieb>
    python werkzeuge/betriebszweig.py rahmen <checkout von main> <gebauter Baum>
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

#: Die Dateien in der Wurzel des Zweigs, die die Routine ablegt.
WURZEL = ("anker.jsonl", "A-B1.json")
#: Das Paket im Zweig und die Endungen seiner oeffentlichen Dateien.
PAKET = "paket"
PAKET_ENDUNGEN = (".html", ".json", ".jsonl")
#: Die Zeichen eines Dateinamens im Paket; ``unternehmensseite`` haelt jeden
#: Namen, der in einen Verweis geht, noch einmal dagegen.
DATEINAME = re.compile(r"[a-z0-9_.-]+")

# Was in keiner HTML-Datei des Pakets stehen darf (Entscheid des Maintainers
# 16.10.2026, Auftrag A-009). Gelesen wird der Text, kein geparstes Dokument:
# Ein Parser, der an einer Stelle anders liest als der Browser, saehe ein
# anderes Dokument, etwa einen Kommentar, der fuer ihn weiterlaeuft, oder
# ein Stylesheet, das fuer den Browser schon zu Ende ist. Jedes Muster trifft
# deshalb lieber zu viel als zu wenig.
_ELEMENT = re.compile(r"<(script|iframe|frame|frameset|object|embed|applet|form|base)(?![a-z0-9-])")
_EREIGNIS = re.compile(r"(?<=[\s/\"'])(on[a-z]+)\s*=")
_REFRESH = re.compile(r"http-equiv\s*=\s*[\"']?\s*refresh")
#: Jedes Attribut mit seinem Wert. Ob es eine Adresse traegt, entscheidet
#: der ganze Name (:func:`_traegt_adresse`), nicht ein Stueck davon:
#: ``imagesrcset`` traegt eine, auch wenn vor ``srcset`` kein Trennzeichen steht.
_ATTRIBUT = re.compile(r"(?<=[\s/\"'])([^\s/>=\"']+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]*))")
#: Attribute mit einer Adresse, deren Name nicht auf src, srcset oder href endet.
_ADRESS_ATTRIBUTE = ("poster", "data", "background", "action", "formaction", "ping", "manifest",
                     "to", "from", "by", "values")
_CSS_URL = re.compile(r"url\(\s*[\"']?([^\"')]*)")
#: Eine Adresse mit Schema oder ab ``//``; Steuerzeichen und Leerzeichen davor
#: uebergeht der Browser.
_VON_AUSSEN = re.compile(r"[\x00-\x20]*(?:[a-z][a-z0-9+.-]*:|[/\\]{2})")
#: Der Betriebsteil im gebauten Baum (unternehmensseite.BETRIEB_DIR).
BETRIEB_DIR = "betrieb"


def zweig(wurzel: Path) -> List[str]:
    """Befunde zum Inhalt des Zweigs betrieb (ein Checkout, ``.git`` zaehlt nicht)."""
    befunde: List[str] = []
    dateien: List[str] = []
    for p in sorted(wurzel.rglob("*")):
        rel = p.relative_to(wurzel)
        if rel.parts[0] == ".git":
            continue
        if ".github" in rel.parts:
            befunde.append(f"{rel.as_posix()}: ein Workflow-Verzeichnis im Zweig betrieb")
            continue
        if p.is_symlink():
            befunde.append(f"{rel.as_posix()}: ein Symlink")
        elif p.is_file():
            dateien.append(rel.as_posix())
    stand: Dict = {}
    try:
        stand = json.loads((wurzel / PAKET / "stand.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        befunde.append(f"{PAKET}/stand.json: nicht lesbar ({exc})")
    genannt = set((stand.get("dateien") or {}) if isinstance(stand, dict) else ())
    for name in WURZEL:
        if name not in dateien:
            befunde.append(f"{name}: fehlt")
    for rel in dateien:
        teile = rel.split("/")
        if len(teile) == 1:
            if rel not in WURZEL:
                befunde.append(f"{rel}: nicht erlaubt")
        elif teile[0] != PAKET or len(teile) != 2:
            befunde.append(f"{rel}: nicht erlaubt (das Paket liegt flach unter {PAKET}/)")
        elif not DATEINAME.fullmatch(teile[1]):
            befunde.append(f"{rel}: Dateiname mit anderen Zeichen als a-z, 0-9, _ . -")
        elif teile[1] != "stand.json" and teile[1] not in genannt:
            befunde.append(f"{rel}: steht nicht in stand.json")
        elif not teile[1].endswith(PAKET_ENDUNGEN):
            befunde.append(f"{rel}: keine oeffentliche Datei des Pakets")
        else:
            befunde += [f"{rel}: {b}" for b in _paket_datei(wurzel / rel)]
    return befunde


def _traegt_adresse(name: str) -> bool:
    """Ob ein Attribut eine Adresse traegt, die der Browser laedt oder
    aufruft: jedes, dessen Name auf src, srcset oder href endet (so auch
    imagesrcset, attributionsrc, xlink:href), und die in _ADRESS_ATTRIBUTE."""
    return name.endswith(("src", "srcset", "href")) or name in _ADRESS_ATTRIBUTE


def html_befunde(text: str) -> List[str]:
    """Was eine HTML-Datei des Pakets nicht enthalten darf.

    Skript: ein Element ``script``, ein Attribut ``on…=``, ``javascript:``.
    Elemente, die ein fremdes Dokument einbetten, etwas absenden oder die
    Adresse der Seite umstellen: iframe, frame, frameset, object, embed,
    applet, form, base; dazu meta refresh. Und jede Quelle von aussen: eine
    Adresse mit Schema oder ab ``//`` in einem Attribut, das eine Adresse
    traegt, oder in ``url(…)``. Auch ``data:`` zaehlt, denn eine solche Adresse
    kann ein Stylesheet tragen, das selbst von aussen laedt; ebenso ein
    Verweis ``<a href>`` nach aussen, weil ihn vom ``<link href>`` nur ein
    Parser unterscheiden koennte. ``@import``, ``image-set(`` und der Backslash
    sind Wege, in CSS eine Adresse ohne ``url(`` oder verkleidet zu laden.

    Elemente und Attribute werden im Rohtext gesucht und zerlegt, wie der
    Browser es tut: Aus einer Zeichenreferenz wird nie ein Tag, ein Trenner
    oder ein Anfuehrungszeichen, das einen Wert beendet. Erst im Wert eines
    Attributs werden die Zeichenreferenzen aufgeloest und Tab und
    Zeilenumbruch entfernt, wie der Browser es mit einer Adresse tut. Die
    Suche nach Teilstuecken (javascript:, meta refresh, url(…), @import)
    laeuft auf dem ganzen aufgeloesten Text; dort trifft sie hoechstens zu
    viel."""
    roh = text.lower()
    flach = re.sub(r"[\t\n\r]", "", html.unescape(text)).lower()
    befunde = [f"<{m.group(1)}>" for m in _ELEMENT.finditer(roh)]
    befunde += [f"Attribut {m.group(1)}" for m in _EREIGNIS.finditer(roh)]
    if "javascript:" in flach:
        befunde.append("javascript:")
    if _REFRESH.search(flach):
        befunde.append("meta refresh")
    for m in _ATTRIBUT.finditer(text):
        name = m.group(1).lower()
        if not _traegt_adresse(name):
            continue
        # Aufgeloest in der Schreibweise des Texts: &NewLine; ist eine
        # Zeichenreferenz, &newline; nicht.
        wert = re.sub(r"[\t\n\r]", "", html.unescape(
            next(g for g in m.groups()[1:] if g is not None))).lower()
        befunde += [f"{name}={a} (von aussen)" for a in re.split(r"[\s,;]+", wert)
                    if _VON_AUSSEN.match(a)]
    befunde += [f"url({m.group(1).strip()}) (von aussen)" for m in _CSS_URL.finditer(flach)
                if _VON_AUSSEN.match(m.group(1).strip())]
    befunde += [wort for wort in ("@import", "image-set(", "\\") if wort in flach]
    return sorted(set(befunde))


def _paket_datei(pfad: Path) -> List[str]:
    """Befunde zum Inhalt einer Datei des Pakets."""
    roh = pfad.read_bytes()
    befunde = []
    if roh.removeprefix(b"\xef\xbb\xbf").startswith(b"---"):
        befunde.append("beginnt mit einem Vorspann (---), Jekyll verarbeitete die Datei")
    if pfad.suffix != ".html":
        return befunde
    try:
        return befunde + html_befunde(roh.decode("utf-8"))
    except UnicodeDecodeError:
        return befunde + ["nicht in UTF-8"]


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def _baum(wurzel: Path) -> Dict[str, Path]:
    return {p.relative_to(wurzel).as_posix(): p for p in sorted(wurzel.rglob("*"))
            if p.is_file() and p.relative_to(wurzel).parts[0] not in (".git", BETRIEB_DIR)}


def rahmen(rahmen_baum: Path, seite: Path) -> List[str]:
    """Befunde, wenn sich ausserhalb von ``betrieb/`` etwas geaendert hat."""
    befunde: List[str] = []
    if (rahmen_baum / BETRIEB_DIR).exists():
        befunde.append(f"{BETRIEB_DIR}/ liegt schon im Rahmen; den Betriebsteil baut nur der Workflow")
    alt, neu = _baum(rahmen_baum), _baum(seite)
    for rel in sorted(set(alt) - set(neu)):
        befunde.append(f"{rel}: im Rahmen, nicht im gebauten Baum")
    for rel in sorted(set(neu) - set(alt)):
        befunde.append(f"{rel}: im gebauten Baum, nicht im Rahmen")
    for rel in sorted(set(alt) & set(neu)):
        if _sha(alt[rel]) != _sha(neu[rel]):
            befunde.append(f"{rel}: anders als im Rahmen")
    return befunde


def _zeile(befund: str) -> str:
    """Ein Befund als EINE Zeile im Protokoll des Workflows. Er traegt Namen
    und Werte aus dem Zweig; ein Steuerzeichen darin wird sichtbar
    (``\\x0a``), statt eine Zeile zu beginnen, die der Runner als Befehl
    (``::…``) laese."""
    return re.sub(r"[\x00-\x1f\x7f]", lambda m: f"\\x{ord(m.group()):02x}", befund)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/betriebszweig.py",
                                description=__doc__.splitlines()[0])
    teil = p.add_subparsers(dest="pruefung", required=True)
    q = teil.add_parser("zweig", help="was im Zweig betrieb liegen darf")
    q.add_argument("checkout")
    q = teil.add_parser("rahmen", help="ausserhalb von betrieb/ alles wie in main")
    q.add_argument("rahmen")
    q.add_argument("seite")
    args = p.parse_args(argv)
    if args.pruefung == "zweig":
        befunde, titel = zweig(Path(args.checkout)), "Zweig betrieb"
    else:
        befunde, titel = rahmen(Path(args.rahmen), Path(args.seite)), "Rahmen"
    for b in befunde:
        print(f"  BEFUND {_zeile(b)}")
    print(f"{titel}: " + ("mit Befund, nicht ausgeliefert" if befunde else "ohne Befund"))
    return 1 if befunde else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
