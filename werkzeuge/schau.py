"""Screenshots der gebauten Vorschau — damit die Gestaltung geprueft wird,
statt sie zu behaupten.

Wer eine Seite baut, ohne sie anzusehen, meldet irgendwann "fertig", waehrend
etwas Kaputtes beim Leser steht: Ein ungueltiger CSS-Kurzbefehl verwirft eine
ganze Regel, ohne dass ein Test es merkt, und ein Diagramm ohne Breitenanschlag
skaliert seine Schrift mit. Dieses Werkzeug macht die Seite sichtbar — auch fuer
ein Modell, das sonst nur den Quelltext sieht.

Braucht Playwright samt Browser; beides ist KEINE Abhaengigkeit des Systems,
sondern Werkstattausruestung:

    .venv/bin/pip install playwright
    .venv/bin/playwright install chromium

Aufruf::

    .venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau
    .venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau index.html

Ohne Seitenangabe: Startseite, Vertiefungen und der Fallbericht, je in breiter
und schmaler Ansicht (1280 und 720 Pixel).
"""
from __future__ import annotations
import sys
from pathlib import Path
try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - Werkstattausruestung, kein Systemteil
    print("playwright fehlt: .venv/bin/pip install playwright && "
          ".venv/bin/playwright install chromium", file=sys.stderr)
    raise SystemExit(2)

STANDARD = ["index.html", "geschaeftsentwicklung/index.html", "migrationen/index.html",
            "migrationen/ki.html", "aktuariat/index.html", "it/index.html",
            "migrationen/baldrian/index.html"]
#: 1280 ist der Schreibtisch, 720 ein Tablet, 390 ein Telefon — und das
#: Telefon ist die Ansicht, in der eine Grafik mit fester viewBox am
#: staerksten schrumpft. Wer nur "schmal" prueft, sieht das nicht.
BREITEN = {"breit": 1280, "schmal": 720, "handy": 390}


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    quelle = Path(argv[0]).resolve()
    ziel = Path(argv[1]).resolve()
    seiten = argv[2:] or STANDARD
    ziel.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, breite in BREITEN.items():
            seite = browser.new_page(viewport={"width": breite, "height": 1000},
                                     device_scale_factor=1)
            for rel in seiten:
                pfad = quelle / rel
                if not pfad.is_file():
                    print(f"fehlt: {rel}", file=sys.stderr)
                    continue
                seite.goto(pfad.as_uri())
                seite.wait_for_timeout(120)
                datei = ziel / f"{rel.replace('/', '_').replace('.html', '')}-{name}.png"
                seite.screenshot(path=str(datei), full_page=True)
                print(f"{datei.name}  ({seite.evaluate('document.body.scrollHeight')} px hoch)")
            seite.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
