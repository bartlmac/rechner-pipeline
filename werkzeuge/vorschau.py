"""``vorschau`` — den Entwurf der Vorzeigeseite ansehen, bevor er die Welt erreicht.

Lokal existiert die Seite nur als QUELLE (``index.md``, ``_config.yml``,
``artefakte/``); ihr HTML erzeugt erst Jekyll auf den GitHub-Servern,
beim Push. Wer den Entwurf vorher pruefen will — die Handfragen des
Runbooks verlangen genau das —, braucht eine lokale Darstellung.

Dieses Werkzeug rendert ALLE Markdown-Seiten des Baums (Startseite,
Bereiche, Migrationsberichte, Verlauf) in ein EIGENES Verzeichnis
neben dem Push-Verzeichnis, nie hinein: Eine von Hand dazugelegte
``index.html`` kollidierte beim Veroeffentlichen mit der von Jekyll
gebauten. Artefakte und Assets werden verlinkt (Symlink), nicht
kopiert — die Vorschau ist eine Sicht auf den Entwurf, kein zweiter
Datenbestand.

Die Vorschau ist eine LESEHILFE, kein Abbild des Pages-Themas: Inhalt,
Zahlen, Tabellen und Links sind pruefbar; die Optik der Live-Seite
entsteht erst beim Bau. Gerendert wird mit ``python3-markdown``
(Debian-Paket, auf dem System vorhanden), Erweiterungen ``tables`` und
``attr_list``; die Ueberschriften bekommen die ids, die Pages ihnen gibt.

Aufruf::

    python3 werkzeuge/vorschau.py --seite runs/vorzeige \\
        --out runs/vorzeige-vorschau
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from html import escape
from pathlib import Path
from typing import Dict, List, Optional

#: Verzeichnisse, die als Ganzes in die Vorschau verlinkt werden —
#: Artefakt-Belege und Seiten-Assets; ihr Inhalt wird nicht gerendert.
GANZ_VERLINKEN = ("artefakte", "assets", "plv")

#: TeX-Formeln, die vor dem Markdown-Lauf aus dem Text genommen werden.
#: Erst Block ($$...$$, darf Zeilen umfassen), dann inline ($...$, nicht
#: ueber Zeilenenden) — sonst frisst das inline-Muster die halbe
#: Blockformel.
_MATHE = re.compile(r"\$\$.+?\$\$|\$[^$\n]+?\$", re.S)

#: Liquid-Tags um einen Rumpf, den Liquid nicht auswerten soll. Auf Pages
#: nimmt Liquid sie heraus, die Vorschau ebenso (unternehmensseite.ROH_AUF).
_ROH = re.compile(r"\{%-?\s*(?:end)?raw\s*-?%\}")

#: Platzhalter fuer eine herausgenommene Formel. Nur Buchstaben und
#: Ziffern: Markdown laesst ein gewoehnliches Wort in Ruhe, waehrend
#: Unterstriche oder Klammern im Platzhalter dasselbe Schicksal ereilten
#: wie die Formel, die er vertritt.
_PLATZHALTER = "xmathex{}x"


def _mathe_herausnehmen(text: str):
    """Formeln durch Platzhalter ersetzen und getrennt zurueckgeben.

    Ohne diesen Schritt geht die Mathematik durch den Markdown-Lauf
    kaputt, und zwar auf zwei Weisen, die beide nicht auffallen, weil sie
    gueltiges HTML erzeugen:

    * ``attr_list`` liest eine geschweifte Klammer hinter einem Wort als
      Attributliste. Aus ``\frac{{}_{a_0}V^{bpfl}}`` wird ein Element mit
      dem Attribut ``a_0="a_0"``.
    * Der Unterstrich ist in Markdown Hervorhebung. Aus ``_{j}p_y`` wird
      ein ``<em>``, das mitten in der Formel oeffnet und irgendwo wieder
      schliesst.

    MathJax bekommt dann keinen TeX-Ausdruck mehr, sondern TeX mit
    HTML-Tags darin, und zeigt Buchstabensalat. Gemessen an der
    Vorzeige-Seite: dreizehn Formeln im KLV-Tarifplan, vier in der
    Grundsatzdokumentation.

    Zurueck kommen die Formeln so, wie kramdown sie auf Pages an MathJax
    gibt: ``$$...$$`` im Text als ``\\(...\\)`` (abgesetzt nur als eigener
    Absatz, :func:`_eigener_absatz`), HTML-maskiert, damit ein ``<`` in der
    Formel kein Tag oeffnet. Liefert den Text, die Formeln wie geschrieben
    (fuer die ids der Ueberschriften) und ihre Anzeige.
    """
    formeln: List[str] = []
    anzeige: List[str] = []

    def weg(treffer) -> str:
        roh = treffer.group(0)
        formeln.append(roh)
        if roh.startswith("$$") and not _eigener_absatz(text, treffer.start(), treffer.end()):
            roh = "\\(" + roh[2:-2].strip() + "\\)"
        anzeige.append(escape(roh, quote=False))
        return _PLATZHALTER.format(len(formeln) - 1)

    return _MATHE.sub(weg, text), formeln, anzeige


def _eigener_absatz(text: str, anfang: int, ende: int) -> bool:
    """Steht die Formel ``text[anfang:ende]`` als eigener Absatz da?

    So unterscheidet kramdown eine abgesetzte Formel von einer im Text: davor
    der Anfang oder eine Leerzeile (und hoechstens drei Leerzeichen), danach
    eine Leerzeile oder das Ende."""
    return (re.search(r"(?:\A|\n[ \t]*\n)[ \t]{0,3}\Z", text[:anfang]) is not None
            and re.match(r"[ \t]*(?:\n[ \t]*\n|\n?[ \t]*\Z)", text[ende:]) is not None)


def _mathe_zurueck(html: str, formeln: List[str]) -> str:
    """Die Platzhalter wieder durch ihre Formeln ersetzen."""
    for i, roh in enumerate(formeln):
        html = html.replace(_PLATZHALTER.format(i), roh)
    return html


def _gfm_ids(texte: List[str]) -> List[str]:
    """Die ids, die Pages den Ueberschriften einer Seite gibt, in ihrer
    Reihenfolge.

    Pages rendert mit kramdown, Eingabe GFM (Vorgabe in
    ``github-pages``), und das gibt jeder Ueberschrift ohne eigene id eine
    aus ihrem Text (``generate_gfm_header_id`` in kramdown-parser-gfm):
    klein geschrieben, alles ausser Wortzeichen, Bindestrich, Leerzeichen
    und Tab gestrichen, jedes Leerzeichen und jeder Tab einzeln ein
    Bindestrich. Kehrt eine id wieder, bekommt sie ``-1``, ``-2`` angehaengt.
    Aus ``T-Box`` wird ``t-box``, aus ``Schlüssel`` wird ``schlüssel``; ein
    Verweis wie ``[T-Box](#t-box)`` traegt live. Ohne diese ids liefe er in
    der Vorschau ins Leere (Glossar, Bau vom 08.10.2026).
    """
    gezaehlt: Dict[str, int] = {}
    ids: List[str] = []
    for text in texte:
        kennung = re.sub(r"[^\w\- \t]", "", text.lower()).replace(" ", "-").replace("\t", "-")
        gezaehlt[kennung] = gezaehlt.get(kennung, -1) + 1
        ids.append(f"{kennung}-{gezaehlt[kennung]}" if gezaehlt[kennung] else kennung)
    return ids


#: Eine eigene id am Ende einer Ueberschrift, so wie kramdown sie liest
#: (``HEADER_ID``); attr_list setzt sie in der Vorschau ebenso.
_EIGENE_ID = re.compile(r"[\t ]\{#[A-Za-z_:][\w.:-]*\}$")


def _ids_erweiterung(markdown, formeln: List[str]):
    """Die Markdown-Erweiterung, die jeder Ueberschrift ohne eigene id die id
    aus :func:`_gfm_ids` gibt.

    Sie laeuft vor der Inline-Verarbeitung: kramdown rechnet aus der Quelle
    der Ueberschrift (``raw_text``), nicht aus dem, was sie anzeigt, und die
    Formeln stehen dort noch als Formeln, nicht als Platzhalter."""
    from markdown.extensions import Extension
    from markdown.treeprocessors import Treeprocessor

    class Ids(Treeprocessor):
        def run(self, wurzel):
            koepfe = [el for el in wurzel.iter()
                      if el.tag in ("h1", "h2", "h3", "h4", "h5", "h6")
                      and "id" not in el.attrib and not _EIGENE_ID.search(el.text or "")]
            texte = [_mathe_zurueck((el.text or "").strip(), formeln) for el in koepfe]
            for el, kennung in zip(koepfe, _gfm_ids(texte)):
                el.set("id", kennung)

    class Erweiterung(Extension):
        def extendMarkdown(self, md):
            md.treeprocessors.register(Ids(md), "gfm_ids", 30)   # "inline" hat 20

    return Erweiterung()

#: Die Vorschau zeigt, was Jekyll zeigen wird: dasselbe Stylesheet, dasselbe
#: Geruest (werkzeuge/../vorzeige-seite/_layouts/default.html). Ein eigenes
#: Aussehen der Vorschau waere eine zweite Wahrheit.
SEITE = ('<!DOCTYPE html><html lang="de"><head><meta charset="utf-8">'
         '<meta name="viewport" content="width=device-width, initial-scale=1">'
         '<title>Vorschau — {name}</title>'
         '<link rel="stylesheet" href="{wurzel}assets/stil.css">'
         '<style>.vorschau-marke{{background:#c2622d;color:#fff;'
         'padding:.4rem 2rem;font:600 .75rem/1.4 system-ui,sans-serif;'
         'letter-spacing:.05em}}</style></head><body>'
         '<p class="vorschau-marke">Vorschau des Entwurfs — nicht die '
         'veroeffentlichte Seite.</p>'
         '<main>{rumpf}</main></body></html>')


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python3 werkzeuge/vorschau.py",
        description="Entwurf der Vorzeigeseite lokal ansehen, vor dem "
                    "Schieben.")
    p.add_argument("--seite", required=True,
                   help="gebautes Push-Verzeichnis (vorzeigeseite.py --out)")
    p.add_argument("--out", required=True,
                   help="Vorschau-Verzeichnis — NICHT das Push-Verzeichnis")
    args = p.parse_args(argv)

    try:
        import markdown
    except ImportError:
        print("python3-markdown fehlt (Debian: apt install python3-markdown).",
              file=sys.stderr)
        return 2

    seite = Path(args.seite).resolve()
    out = Path(args.out).resolve()
    if not (seite / "index.md").is_file():
        print(f"Keine gebaute Seite: {seite}", file=sys.stderr)
        return 2
    if out == seite or seite in out.parents:
        print("Die Vorschau darf nicht ins Push-Verzeichnis: eine index.html "
              "dort kollidierte mit der von Jekyll gebauten.", file=sys.stderr)
        return 2

    out.mkdir(parents=True, exist_ok=True)
    gerendert, verlinkt = 0, 0
    for quelle in sorted(seite.rglob("*")):
        rel = quelle.relative_to(seite)
        # Inhalte von als Ganzes verlinkten Verzeichnissen nicht betreten.
        if any(teil in GANZ_VERLINKEN for teil in rel.parts[:-1]):
            continue
        ziel = out / rel
        if quelle.is_dir():
            if quelle.name not in GANZ_VERLINKEN:
                continue
        elif quelle.name.startswith("_") or rel.parts[0].startswith("_"):
            # Jekyll-Interna (Konfiguration, Layouts) — die Vorschau bringt
            # ihr eigenes Geruest mit demselben Stylesheet mit.
            continue
        elif quelle.suffix == ".md":
            roh, formeln, anzeige = _mathe_herausnehmen(
                _ROH.sub("", quelle.read_text(encoding="utf-8")))
            rumpf = _mathe_zurueck(
                markdown.markdown(roh, extensions=[
                    "tables", "attr_list", _ids_erweiterung(markdown, formeln)]),
                anzeige)
            # Jekyll (jekyll-relative-links, auf Pages vorgegeben) macht
            # aus einem Link auf eine .md-Datei den Link auf ihr
            # gerendertes Gegenstueck; die Vorschau tut dasselbe.
            rumpf = re.sub(r'href="([^":]+)\.md"', r'href="\1.html"', rumpf)
            ziel = ziel.with_suffix(".html")
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(
                SEITE.format(name=str(rel), rumpf=rumpf,
                             wurzel="../" * (len(rel.parts) - 1)),
                encoding="utf-8")
            gerendert += 1
            continue
        # Verzeichnisse aus GANZ_VERLINKEN und lose Nicht-Markdown-Dateien
        # werden verlinkt, nicht kopiert — die Vorschau ist eine Sicht auf
        # den Entwurf, kein zweiter Datenbestand.
        ziel.parent.mkdir(parents=True, exist_ok=True)
        if ziel.is_symlink():
            ziel.unlink()
        elif ziel.exists():
            print(f"{ziel} existiert und ist kein Symlink — nicht angefasst.",
                  file=sys.stderr)
            return 2
        ziel.symlink_to(os.path.relpath(quelle, ziel.parent))
        verlinkt += 1

    print(f"{out}: {gerendert} Seiten gerendert, {verlinkt} Verweise gesetzt")

    print()
    print(f"Vorschau: {out / 'index.html'}")
    print("Sichtung im Browser: README, Abschnitt 'Ansehen vor dem Schieben'.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
