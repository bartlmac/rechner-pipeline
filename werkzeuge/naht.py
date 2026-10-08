"""Findet Stellen, an denen zwei Bausteine ohne Abstand aneinanderkleben.

Die erzeugten Bausteine liefern ihre Teile ohne Trennzeichen aus — eine
Kachel schreibt Titel, Formatmarke, Kennzahl und Zweck hintereinander, ein
Abgrenzungsband Aussage, Zahlen und Sicht. Den Abstand setzt das
Stylesheet. Fehlt dort eine Regel, steht auf der Seite
"A-M1 StichtagstestHTML" oder "...am zweiten Stichtagfachlich" — im
Markup unsichtbar, im Browser sofort zu sehen.

Dieses Werkzeug liest die gebaute Vorschau im Browser und meldet jedes
Paar benachbarter Inline-Teile, zwischen denen weder Leerzeichen noch
Rand liegt. Geprueft wird, was der Leser sieht (gemessener Pixelabstand),
nicht was im Quelltext steht.

Braucht Playwright samt Browser wie werkzeuge/schau.py — Werkstatt-
ausruestung, keine Abhaengigkeit des Systems:

    .venv/bin/pip install playwright
    .venv/bin/playwright install chromium

Aufruf::

    .venv/bin/python werkzeuge/naht.py runs/vorzeige-vorschau

Rueckgabe 0, wenn keine Klebestelle bleibt, sonst 1 — damit es sich in
eine Pruefkette haengen laesst. Vor jedem Lauf prueft sich das Werkzeug
an einer eigenen Probe: null Treffer soll "sauber" heissen und nicht
"blind geworden" (Rueckgabe 2, wenn die Probe nicht aufgeht).
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

#: Im Browser gemessen: Textknoten und Inline-Elemente in Lesereihenfolge,
#: Paar fuer Paar. Satzzeichen an der Naht sind gewollt ("<a>Bericht</a>."),
#: Formelsatz und SVG-Titel bringen eigene Abstaende mit.
JS = r"""() => {
  const treffer = [];
  const pfad = el => { const t = []; while (el && el.tagName) {
      let s = el.tagName.toLowerCase();
      if (el.className && typeof el.className === 'string')
        s += '.' + el.className.trim().split(/\s+/).join('.');
      t.unshift(s); el = el.parentElement; } return t.slice(-3).join(' > '); };
  const inline = n => n.nodeType === 3 ? true
      : (n.nodeType === 1 && getComputedStyle(n).display.startsWith('inline'));
  const mathe = n => { const e = n.nodeType === 1 ? n : n.parentElement;
      return !!(e && (e.closest('mjx-container') || /^MJX/.test(e.tagName || ''))); };
  const kasten = n => n.nodeType === 1 ? n.getBoundingClientRect()
      : (() => { const r = document.createRange(); r.selectNodeContents(n);
                 return r.getBoundingClientRect(); })();
  for (const el of document.querySelectorAll('body *')) {
    if (el.closest('svg')) continue;
    const kinder = [...el.childNodes];
    for (let i = 0; i < kinder.length - 1; i++) {
      const a = kinder[i], b = kinder[i + 1];
      if (a.nodeType === 3 && b.nodeType === 3) continue;
      if (!inline(a) || !inline(b)) continue;
      if (mathe(a) || mathe(b)) continue;
      const ta = a.textContent || '', tb = b.textContent || '';
      if (!ta.trim() || !tb.trim()) continue;
      if (/\s$/.test(ta) || /^\s/.test(tb)) continue;
      if (!/[\p{L}\p{N}\)]$/u.test(ta)) continue;
      if (!/^[\p{L}\p{N}„«"']/u.test(tb)) continue;
      const ra = kasten(a), rb = kasten(b);
      if (!ra.height || !rb.height) continue;
      if (rb.top > ra.bottom - 2) continue;      // andere Zeile: kein Kleben
      if (rb.left - ra.right >= 2) continue;     // Abstand kommt aus dem Rand
      treffer.push({pfad: pfad(a.nodeType === 1 ? a : a.parentElement),
                    a: ta.slice(-30), b: tb.slice(0, 30)});
    }
  }
  return treffer;
}"""


#: Die Probe: Der erste Fall MUSS gefunden werden, die anderen duerfen es
#: nicht. Aendert sich ein Selektor oder eine Bedingung so, dass der
#: Detektor nichts mehr sieht, faellt das hier auf und nicht erst, wenn
#: eine geklebte Stelle monatelang auf der Seite steht.
PROBE = """<p class="klebt"><b>Titel</b><span>Zahl</span></p>
<p class="luft"><b>Titel</b> <span>Zahl</span></p>
<p class="rand"><b style="margin-right:6px">Titel</b><span>Zahl</span></p>
<p class="satz"><a href="#">Bericht</a>. Weiter im Text.</p>
<p class="umbruch"><b style="display:block">Titel</b><span>Zahl</span></p>"""


def _probe(seite) -> str:
    """Leer, wenn die Probe aufgeht; sonst der Grund."""
    seite.set_content(PROBE)
    pfade = [t["pfad"] for t in seite.evaluate(JS)]
    if not any("klebt" in pfad for pfad in pfade):
        return "die zusammengeklebte Probe wird nicht gefunden"
    erlaubt = [pfad for pfad in pfade if "klebt" not in pfad]
    if erlaubt:
        return f"meldet eine erlaubte Naht: {erlaubt[0]}"
    return ""


def main(argv=None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Aufruf: naht.py <vorschau-verzeichnis>", file=sys.stderr)
        return 2
    wurzel = Path(argv[0]).resolve()
    seiten = sorted(wurzel.rglob("*.html"))
    gefunden = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        seite = browser.new_page(viewport={"width": 1280, "height": 1000})
        fehler = _probe(seite)
        if fehler:
            print(f"ABBRUCH: Selbstprobe fehlgeschlagen — {fehler}", file=sys.stderr)
            browser.close()
            return 2
        for datei in seiten:
            seite.goto(datei.as_uri())
            seite.wait_for_timeout(60)
            for t in seite.evaluate(JS):
                gefunden += 1
                print(f"{datei.relative_to(wurzel)}: {t['pfad']}")
                print(f"    ...{t['a']!r} + {t['b']!r}...")
        browser.close()
    print(f"{len(seiten)} Seiten geprueft, {gefunden} Klebestellen")
    return 1 if gefunden else 0


if __name__ == "__main__":
    raise SystemExit(main())
