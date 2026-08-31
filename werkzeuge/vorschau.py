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
(Debian-Paket, auf dem System vorhanden), Erweiterung ``tables``.

Aufruf::

    python3 werkzeuge/vorschau.py --seite runs/vorzeige \\
        --out runs/vorzeige-vorschau
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List, Optional

#: Verzeichnisse, die als Ganzes in die Vorschau verlinkt werden —
#: Artefakt-Belege und Seiten-Assets; ihr Inhalt wird nicht gerendert.
GANZ_VERLINKEN = ("artefakte", "assets")

STIL = """
body{margin:0;background:#f8f8f6;color:#1b1e1c;
font:15.5px/1.6 system-ui,sans-serif}
main{max-width:56rem;margin:0 auto;padding:2.5rem 1.3rem 5rem}
h1{font:600 2rem/1.15 Georgia,serif}
h2{font:600 1.3rem/1.25 Georgia,serif;margin-top:2.2rem}
h3{font:600 1.05rem/1.3 Georgia,serif;margin-top:1.8rem}
table{border-collapse:collapse;font-size:.88rem;margin:1rem 0}
th,td{border:1px solid #cfd3cc;padding:.4rem .8rem;text-align:left}
th{background:#eceee9}
blockquote{margin:1rem 0;padding:.7rem 1rem;background:#fff;
border-left:3px solid #c1c6bf}
code{font:.85em ui-monospace,monospace;background:#e7eae4;
padding:.1em .3em;border-radius:3px}
.hinweis{background:#8c4a2f;color:#fff;padding:.5rem 1rem;
font-size:.85rem;margin:0}
a{color:#2f5d62}
"""

SEITE = ("<!DOCTYPE html><html lang=\"de\"><head><meta charset=\"utf-8\">"
         "<title>Vorschau — {name}</title><style>{stil}</style></head><body>"
         "<p class=\"hinweis\">VORSCHAU des Entwurfs — nicht die "
         "veroeffentlichte Seite. Die Optik der Live-Seite entsteht erst "
         "beim Jekyll-Bau.</p><main>{rumpf}</main></body></html>")


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
        elif quelle.name == "_config.yml":
            # Jekyll-Konfiguration — hat in der Vorschau keine Wirkung.
            continue
        elif quelle.suffix == ".md":
            rumpf = markdown.markdown(
                quelle.read_text(encoding="utf-8"),
                extensions=["tables", "attr_list"])
            # Jekyll (jekyll-relative-links, auf Pages vorgegeben) macht
            # aus einem Link auf eine .md-Datei den Link auf ihr
            # gerendertes Gegenstueck; die Vorschau tut dasselbe.
            rumpf = re.sub(r'href="([^":]+)\.md"', r'href="\1.html"', rumpf)
            ziel = ziel.with_suffix(".html")
            ziel.parent.mkdir(parents=True, exist_ok=True)
            ziel.write_text(
                SEITE.format(name=str(rel), stil=STIL, rumpf=rumpf),
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
