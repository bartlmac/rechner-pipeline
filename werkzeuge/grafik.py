"""``grafik`` — der Bausteinsatz fuer generierte Darstellungen der Vorzeigeseite.

Jede Grafik der Seite entsteht beim Bau aus dem falldaten-Modell;
dieses Modul kennt das Modell NICHT, sondern nur einfache Eingaben
(Titel, Zahlen, Zustaende) und liefert Inline-SVG oder HTML. So bleibt
die Zuordnung "welcher Modellpfad speist welche Grafik" an einer
Stelle (den Seitengeneratoren), und jede weitere Grafik kostet wenig.

Zwei Regeln fuer alle Bausteine:

*Zwei Datenfarben.* Traegerfarbe fuer Gepruefte und Bestandene,
Kontrastfarbe fuer Einschraenkung, Abweichung und Grenze. Keine Ampel:
Sie machte aus einem Pruefbericht eine Werbebroschuere und funktioniert
fuer Farbfehlsichtige nicht. Identitaet haengt nie an der Farbe allein —
jede Marke traegt Text.

*Der Befund ist der Regelfall.* Jeder Baustein hat seinen Zweig fuer
den nicht-gruenen Fall (Marker jenseits der Schranke, Segment mit
Befund, Lueckenliste statt leerer Karte). Ein Baustein, der nur den
Erfolg zeigen koennte, waere keiner.
"""

from __future__ import annotations

import html
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Farben tragen je eine Rolle, und jede ist gerechnet, nicht geschaetzt
#: (Helligkeitsband, Chroma, Farbfehlsichtigkeit, Kontrast — geprueft mit dem
#: Zwilling des dataviz-Validators). SERIE_* unterscheidet WAS (Produkt,
#: Quelle), ZEIT_* unterscheidet WANN (Vorjahr gegen heute) als zwei Stufen
#: derselben Rampe. Als CSS-Variable mit Hex-Rueckfall, damit ein Muster die
#: Palette tauschen kann, ohne dass die Diagramme neu erzeugt werden muessen.
SERIE = ("var(--serie-1, #2a78d6)", "var(--serie-2, #eb6834)",
         "var(--serie-3, #1baf7a)", "var(--serie-4, #eda100)",
         "var(--serie-5, #e87ba4)")
ZEIT_FRUEHER = "var(--zeit-frueher, #6da7ec)"
ZEIT_JETZT = "var(--zeit-jetzt, #1c5cab)"
TRAEGER = SERIE[0]
KONTRAST = SERIE[1]
MATT = "var(--text-matt, #5f6663)"
TINTE = "var(--text-tinte, #1b1e1c)"
FLAECHE = "var(--flaeche-matt, #e7eae4)"
#: Marken bleiben duenn, Datenenden gerundet, zwischen Fuellungen 2 px Luft.
BALKEN_HOEHE = 18
LUFT = 3

#: Ein Diagramm wird NIE hochskaliert: Ohne feste Obergrenze streckt der
#: Browser die viewBox auf die Spaltenbreite, und aus 13 px Schrift werden
#: 25 — davon kam der Eindruck zufaelliger Schriftgroessen. Mit
#: ``max-width`` in Hoehe der viewBox gilt eine Einheit = ein Pixel; auf
#: schmalen Fenstern verkleinert es sich proportional — und genau das
#: bestimmt den Schriftgrad: Eine 900 Einheiten breite Grafik steht auf
#: einem 720-px-Fenster mit Faktor 0,7 da, aus 13 px werden dort 9. Die
#: Schrift liegt darum auf Fliesstextgroesse (15 px); auf dem breiten
#: Fenster ist sie so gross wie der Text daneben, auf dem schmalen bleibt
#: sie mit 11 px lesbar. Die Breite ist so gewaehlt, dass eine Grafik die
#: Flaeche fuellt, auf der sie liegt — sonst steht sie verloren in ihrer
#: Karte.
SCHRIFTGROESSE = 15
BREITE = 900
#: Fuer das Telefon: Dort bleibt keine Skalierung uebrig, die eine 900
#: Einheiten breite Grafik lesbar liesse (Faktor 0,4 — aus 15 px Schrift
#: werden 6). Eine zweite, eigene Fassung ist der einzige Weg, der den
#: Text in Groesse haelt; welche gezeigt wird, entscheidet das Stylesheet.
BREITE_HANDY = 330
#: Fuer Grafiken, die neben einer Kachel in einer schmalen Spalte stehen.
#: Eine Grafik, die breiter ist als ihr Platz, wird herunterskaliert — und
#: ihre Schrift mit ihr; dann hilft kein groesserer Schriftgrad.
BREITE_SCHMAL = 520
#: Mittlere Zeichenbreite bei dieser Groesse — fuer Platzbedarf von Text,
#: den SVG selbst nicht misst.
ZEICHEN = 7.9


def _svg(breite: int, hoehe: int, label: str, teile: Sequence[str],
         schrift: int = SCHRIFTGROESSE) -> str:
    return (f'<svg role="img" aria-label="{_e(label)}" '
            f'viewBox="0 0 {breite} {hoehe}" '
            f'style="width:100%;max-width:{breite}px;height:auto;'
            f'font:{schrift}px system-ui,sans-serif">'
            + "".join(teile) + "</svg>")


def _textbreite(text: str, schrift: int = SCHRIFTGROESSE) -> float:
    return len(str(text)) * ZEICHEN * schrift / SCHRIFTGROESSE


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _zahl(wert: Any, dez: int = 0) -> str:
    text = f"{float(wert):,.{dez}f}"
    return text.replace(",", "@").replace(".", ",").replace("@", ".")


def kurz(wert: Any, stueck: bool = False) -> str:
    """Zahl fuer den ersten Blick: gerundet, mit Einheit, ohne Nachkommastellen.

    Die Einheit wird so gewaehlt, dass mindestens zwei Stellen bleiben —
    aus 80.501.630 wird "81 Mio.", aus 8.254.286 aber "8.254 Tsd." statt
    eines nichtssagenden "8 Mio.". Stueckzahlen (``stueck``) werden erst ab
    einer Million abgekuerzt: "10.000 Vertraege" liest sich, "10 Tsd.
    Vertraege" klingt nach Schaetzung.
    """
    w = float(wert or 0)
    teiler = ((1e6, " Mio."),) if stueck else ((1e6, " Mio."), (1e3, " Tsd."))
    for t, einheit in teiler:
        if abs(w) >= t * 10:
            return _zahl(round(w / t)) + einheit
    return _zahl(round(w))


def vergleich(gruppen: Sequence[Tuple[str, Sequence[Tuple[str, float]]]],
              einheit: str = "", stueck: bool = False) -> str:
    """Zwei Zeitraeume als gestapelte Balken untereinander, gleiche Skala.

    Feste Spalten: Zeitraum links, Balken in der Mitte, Summe rechts. Die
    Skala richtet sich nach der groessten Summe, damit die Balken
    vergleichbar sind und nicht jeder fuer sich voll ausschlaegt. Die
    Legende bricht um, statt aus dem Bild zu laufen.
    """
    gruppen = [(t, [(n, float(w or 0)) for n, w in seg]) for t, seg in gruppen]
    summen = [sum(w for _, w in seg) for _, seg in gruppen]
    hoechst = max(summen + [1])
    namen: List[str] = []
    for _, seg in gruppen:
        for n, _w in seg:
            if n not in namen:
                namen.append(n)
    farben = (TRAEGER, KONTRAST, MATT, "#9db3b1", "#c2856a")
    farbe_je = {n: farben[i % len(farben)] for i, n in enumerate(namen)}

    breite = BREITE
    label_breite = max([_textbreite(t) for t, _ in gruppen] + [60.0]) + 10
    wert_breite = max([_textbreite(kurz(w, stueck)) for w in summen] + [48.0]) + 8
    x0 = round(label_breite)
    plot = breite - x0 - round(wert_breite)
    zeile, balken_hoehe = 34, 18

    teile: List[str] = []
    for i, ((titel, segmente), summe) in enumerate(zip(gruppen, summen)):
        y = 4 + i * zeile
        mitte = y + balken_hoehe / 2 + 4
        teile.append(f'<text x="0" y="{mitte:.0f}" fill="{MATT}">{_e(titel)}</text>')
        x = x0
        for name, wert in segmente:
            if wert <= 0:
                continue
            b = max(2.0, plot * wert / hoechst)
            teile.append(f'<g><title>{_e(titel)} · {_e(name)}: {_zahl(wert)}</title>'
                         f'<rect x="{x:.1f}" y="{y}" width="{b:.1f}" '
                         f'height="{balken_hoehe}" fill="{farbe_je[name]}"/></g>')
            x += b + 1
        teile.append(f'<text x="{breite}" y="{mitte:.0f}" text-anchor="end" '
                     f'fill="{TINTE}" font-weight="600">{_e(kurz(summe, stueck))}</text>')

    # Legende unter den Balken; was nicht in die Zeile passt, rutscht eine
    # tiefer, statt rechts aus dem Bild zu laufen.
    x, y = x0, 4 + len(gruppen) * zeile + 12
    for name in namen:
        platz = 12 + _textbreite(name) + 14
        if x + platz > breite:
            x, y = x0, y + 16
        teile.append(f'<rect x="{x:.0f}" y="{y - 8}" width="9" height="9" rx="1" '
                     f'fill="{farbe_je[name]}"/>'
                     f'<text x="{x + 13:.0f}" y="{y}" fill="{MATT}">{_e(name)}</text>')
        x += platz
    if einheit:
        teile.append(f'<text x="{breite}" y="{y}" text-anchor="end" '
                     f'fill="{MATT}">{_e(einheit)}</text>')
    label = "; ".join(f"{t}: " + ", ".join(f"{n} {_zahl(w)}" for n, w in seg)
                      for t, seg in gruppen)
    return _svg(breite, y + 8, label, teile)


def stat_tile(label: str, wert: str, delta: Optional[str] = None,
              richtung: str = "", fuss: str = "") -> str:
    """Eine Kennzahl als Kachel: Beschriftung, Wert, Veraenderung.

    Fuer einen einzelnen aktuellen Wert ist die Kachel die richtige Form —
    ein Balkendiagramm mit einem Balken sagt nichts, was die Zahl nicht
    schon sagt. ``richtung`` ist "auf" oder "ab" und faerbt nur das
    Vorzeichen, nicht den Text.
    """
    pfeil = {"auf": "▲", "ab": "▼"}.get(richtung, "")
    z = [f'<div class="kennzahl-kachel"><span class="marke">{_e(label)}</span>'
         f'<span class="wert">{_e(wert)}</span>']
    if delta:
        z.append(f'<span class="delta {_e(richtung)}">{pfeil} {_e(delta)}</span>')
    if fuss:
        z.append(f'<span class="fuss">{_e(fuss)}</span>')
    z.append("</div>")
    return "".join(z)


def anteil(paare: Sequence[Tuple[str, int]], einheit: str = "",
           breite: int = BREITE_SCHMAL) -> str:
    """Ein schlanker Balken: Zusammensetzung einer Menge, direkt beschriftet."""
    paare = [(t, int(w)) for t, w in paare if int(w) > 0]
    gesamt = sum(w for _, w in paare) or 1
    # Der Balken waechst mit seiner Flaeche: ueber die volle Textbreite
    # gezogen wirkt ein 26 Einheiten hoher Streifen wie ein Strich.
    hoehe = 40 if breite >= BREITE else 26
    teile: List[str] = []
    x = 0.0
    nutz = breite - LUFT * max(0, len(paare) - 1)
    for i, (titel, wert) in enumerate(paare):
        b = max(3.0, nutz * wert / gesamt)
        teile.append(f'<g><title>{_e(titel)}: {_zahl(wert)} {_e(einheit)}</title>'
                     f'<rect x="{x:.1f}" y="0" width="{b:.1f}" height="{hoehe}" '
                     f'rx="4" fill="{SERIE[i % len(SERIE)]}"/></g>')
        x += b + LUFT
    x, y = 0.0, hoehe + 22
    for i, (titel, wert) in enumerate(paare):
        text = f"{titel} {_zahl(wert)}"
        platz = 14 + _textbreite(text) + 20
        if x + platz > breite and x:
            x, y = 0.0, y + 20
        teile.append(f'<rect x="{x:.0f}" y="{y - 9}" width="9" height="9" rx="2" '
                     f'fill="{SERIE[i % len(SERIE)]}"/>'
                     f'<text x="{x + 14:.0f}" y="{y}" fill="{MATT}">{_e(text)}</text>')
        x += platz
    return _svg(breite, y + 6, ", ".join(f"{t} {w}" for t, w in paare), teile)


def labelbreite(*gruppen: Sequence[str]) -> float:
    """Die gemeinsame Labelbreite mehrerer Diagramme, damit sie buendig starten."""
    namen = [n for g in gruppen for n in g]
    return max([_textbreite(n) for n in namen] + [60.0]) + 14


def responsiv(breit: str, handy: str) -> str:
    """Zwei Fassungen derselben Grafik; das Stylesheet zeigt eine davon.

    Ein SVG mit fester viewBox skaliert seinen Text mit sich selbst. Auf
    einem Telefon bleibt davon nichts Lesbares uebrig, und CSS kann eine
    viewBox nicht aendern — also erzeugt der Bau beide Fassungen.
    """
    return (f'<span class="nur-breit">{breit}</span>'
            f'<span class="nur-handy">{handy}</span>')


def gruppiert(kategorien: Sequence[Tuple[str, Sequence[float]]],
              reihen: Sequence[str], einheit: str = "",
              formatiere=None, breite: int = 0, label: float = 0.0) -> str:
    """Je Kategorie ein Balkenpaar: frueher gegen heute, eine Rampe, zwei Stufen.

    Die Zeit ist eine geordnete Groesse, keine Identitaet — deshalb zwei
    Stufen derselben Farbe und nicht zwei Farben. Werte stehen direkt am
    Balken; eine Achse braucht es dann nicht, und der helle Ton darf
    kontrastarm sein, weil die Zahl daneben steht.
    """
    formatiere = formatiere or (lambda w: _zahl(w))
    farben = (ZEIT_FRUEHER, ZEIT_JETZT)
    hoechst = max([w for _, werte in kategorien for w in werte] + [1])
    breite = breite or BREITE
    # Die Labelspalte kann von aussen vorgegeben werden: Zwei Diagramme
    # untereinander, die ihre Breite je selbst messen, beginnen an
    # verschiedenen Stellen — das sieht aus wie ein Versatz und ist einer.
    label = label or max([_textbreite(t) for t, _ in kategorien] + [60.0]) + 14
    zahl = max([_textbreite(formatiere(w)) for _, werte in kategorien for w in werte]
               + [30.0]) + 16
    plot = breite - label - zahl
    # Zwischen zwei Zeitraeumen derselben Kategorie wenig Luft, zwischen
    # Kategorien viel — sonst liest man die falschen Balken als Paar.
    reihe_hoehe = len(reihen) * (BALKEN_HOEHE + LUFT) + 22
    teile: List[str] = []
    # Die Legende sitzt auf gemessener Textbreite, nicht auf festem Raster:
    # Auf dem Telefon ueberlappten "2025 bis 18.09." und "2026 bis 18.09."
    # sonst, weil das Raster von der breiten Fassung stammte.
    x, zeile = label, 0
    for i, name in enumerate(reihen):
        platz = 14 + _textbreite(name) + 18
        if x + platz > breite and x > label:
            x, zeile = label, zeile + 1
        y = 3 + zeile * 17
        teile.append(f'<rect x="{x:.0f}" y="{y}" width="9" height="9" rx="2" fill="{farben[i % 2]}"/>'
                     f'<text x="{x + 14:.0f}" y="{y + 9}" fill="{MATT}">{_e(name)}</text>')
        x += platz
    kopf = 27 + zeile * 17
    for k, (titel, werte) in enumerate(kategorien):
        oben = kopf + k * reihe_hoehe
        teile.append(f'<text x="{label - 10:.0f}" y="{oben + reihe_hoehe / 2 - 2:.0f}" '
                     f'text-anchor="end" fill="{TINTE}">{_e(titel)}</text>')
        for i, wert in enumerate(werte):
            y = oben + i * (BALKEN_HOEHE + LUFT)
            b = max(2.0, plot * float(wert or 0) / hoechst)
            teile.append(f'<g><title>{_e(titel)} · {_e(reihen[i])}: {_e(formatiere(wert))}'
                         f' {_e(einheit)}</title>'
                         f'<rect x="{label:.0f}" y="{y}" width="{b:.1f}" '
                         f'height="{BALKEN_HOEHE}" rx="4" fill="{farben[i % 2]}"/>'
                         f'<text x="{label + b + 8:.0f}" y="{y + BALKEN_HOEHE - 2}" '
                         f'fill="{MATT}">{_e(formatiere(wert))}</text></g>')
    hoehe = kopf + len(kategorien) * reihe_hoehe
    label_text = "; ".join(
        f"{t}: " + ", ".join(f"{reihen[i]} {formatiere(w)}" for i, w in enumerate(werte))
        for t, werte in kategorien)
    return _svg(breite, hoehe, label_text, teile)


def cent(wert: float) -> str:
    """Einen Euro-Betrag als Cent-Angabe beschriften — 0,0223 -> 2,2 ct."""
    return f"{_zahl(float(wert) * 100, 1)} ct"


# --------------------------------------------------------------------------- #
# Kennzahlen
# --------------------------------------------------------------------------- #

def kennzahlenband(gruppen: Sequence[Tuple[str, Sequence[Tuple[str, str]]]],
                   titel: Optional[str] = None) -> str:
    """Drei Gruppen mit je zwei bis drei Zahlen, eine Zeile.

    Eine Zahl allein ist eine Behauptung; erst die Gruppe erzeugt
    Bedeutung — deshalb erscheinen Umfang, Prueftiefe und
    Verbindlichkeit auf jeder Seite in derselben Ordnung. ``titel``
    beschriftet das Band als Ganzes — auf der Unternehmensseite als
    "Uebernahme X", damit die Zahlen der laufenden Migration nicht als
    Zahlen des Hauses gelesen werden.
    """
    z = ['<div class="kennzahlen">']
    if titel:
        z.append(f'<div class="bandtitel">{_e(titel)}</div>')
    for titel, zahlen in gruppen:
        z.append(f'<div class="gruppe"><div class="gruppentitel">'
                 f"{_e(titel)}</div>")
        for wert, einheit in zahlen:
            z.append(f'<div class="kennzahl"><b>{_e(wert)}</b>'
                     f"<span>{_e(einheit)}</span></div>")
        z.append("</div>")
    z.append("</div>")
    return "".join(z)


# --------------------------------------------------------------------------- #
# Toleranz-Ausschoepfung
# --------------------------------------------------------------------------- #

def toleranz(zeilen: Sequence[Dict[str, Any]]) -> str:
    """Je Abnahme die groesste Abweichung gegen die zugesagte Schranke.

    Alle Zeilen teilen EINE logarithmische Cent-Achse: Absolutwerte sind
    die Hauptlesart, nicht die Ausschoepfung — eine Quote ist eine
    Eigenschaft der gewaehlten Schranke, kein Guetemass, und zwischen
    Abnahmen nicht vergleichbar. Jede Zeile: ``titel``, ``ist_max``,
    ``ist_p95`` (Euro), ``grenze_max`` (Euro oder ``None``, wenn die
    Schranke je Pruefung gesetzt ist), ``werte`` (Anzahl Einzelwerte).
    Liegt ein Maximum jenseits seiner Schranke, steht die Marke in
    Kontrastfarbe und die Beschriftung nennt es — der Befund darf nicht
    aus dem Bild fallen.
    """
    import math
    werte_ct = [float(r["ist_max"]) * 100 for r in zeilen] + [
        float(r["grenze_max"]) * 100 for r in zeilen if r.get("grenze_max")]
    obergrenze = max(werte_ct + [1.0])
    lo, hi = math.log10(0.1), math.log10(obergrenze * 1.6)
    x0, breite = 230, 400

    def px(ct: float) -> float:
        ct = max(ct, 0.1)
        return x0 + breite * (math.log10(ct) - lo) / (hi - lo)

    hoehe = 30 * len(zeilen) + 26
    z = [f'<svg role="img" aria-label="Größte Abweichung je Abnahme: '
         + "; ".join(
             f"{r['titel']} {cent(r['ist_max'])}"
             + (f" bei Schranke {cent(r['grenze_max'])}" if r.get("grenze_max") else "")
             for r in zeilen)
         + f'" viewBox="0 0 760 {hoehe}" style="width:100%;max-width:760px;height:auto;font:{SCHRIFTGROESSE}px system-ui,sans-serif">']
    # Achse mit Zehnerpotenzen
    tick = 0.1
    while tick <= obergrenze * 1.6:
        tx = px(tick)
        z.append(f'<line x1="{tx:.1f}" y1="4" x2="{tx:.1f}" y2="{hoehe - 22}" '
                 f'stroke="{FLAECHE}" stroke-width="1"/>'
                 f'<text x="{tx:.1f}" y="{hoehe - 8}" text-anchor="middle" '
                 f'fill="{MATT}" font-size="9">{_zahl(tick, 1 if tick < 1 else 0)} ct</text>')
        tick *= 10
    for i, r in enumerate(zeilen):
        y = 8 + i * 30
        ist_max = float(r["ist_max"]) * 100
        ist_p95 = float(r.get("ist_p95") or 0) * 100
        grenze = float(r["grenze_max"]) * 100 if r.get("grenze_max") else None
        ueber = grenze is not None and ist_max > grenze
        farbe = KONTRAST if ueber else TRAEGER
        z.append(f'<g><title>{_e(r["titel"])}: größte Abweichung {cent(r["ist_max"])}'
                 + (f', 95 % der Werte unter {cent(r["ist_p95"])}' if r.get("ist_p95") else '')
                 + (f', Schranke {cent(r["grenze_max"])}' if grenze is not None
                    else ", Schranke je Prüfung nach Bausteinen") + "</title>")
        z.append(f'<text x="{x0 - 8}" y="{y + 13}" text-anchor="end" fill="{TINTE}">'
                 f'{_e(r["titel"])}</text>')
        if grenze is not None:
            gx = px(grenze)
            z.append(f'<rect x="{x0}" y="{y + 7}" width="{gx - x0:.1f}" height="8" '
                     f'rx="4" fill="{FLAECHE}"/>'
                     f'<line x1="{gx:.1f}" y1="{y + 2}" x2="{gx:.1f}" y2="{y + 20}" '
                     f'stroke="{KONTRAST}" stroke-width="2"/>')
        else:
            z.append(f'<rect x="{x0}" y="{y + 7}" width="{breite}" height="8" '
                     f'rx="4" fill="none" stroke="{FLAECHE}" stroke-dasharray="3,3"/>')
        if ist_p95 > 0:
            z.append(f'<circle cx="{px(ist_p95):.1f}" cy="{y + 11}" r="4" fill="#fff" '
                     f'stroke="{farbe}" stroke-width="2"/>')
        z.append(f'<circle cx="{px(ist_max):.1f}" cy="{y + 11}" r="4.5" fill="{farbe}"/>')
        text = (f"max {cent(r['ist_max'])}"
                + (f" · Schranke {cent(r['grenze_max'])}" if grenze is not None
                   else " · Schranke je Prüfung")
                + (" · ÜBER SCHRANKE" if ueber else "")
                + (f" · {_zahl(r['werte'])} Werte" if r.get("werte") else ""))
        z.append(f'<text x="{x0 + breite + 8}" y="{y + 15}" fill="{MATT}" font-size="10">'
                 f"{_e(text)}</text></g>")
    z.append("</svg>")
    return "".join(z)


# --------------------------------------------------------------------------- #
# Mengen
# --------------------------------------------------------------------------- #

def gestapelt(paare: Sequence[Tuple[str, int]]) -> str:
    """Derselbe Anteilsbalken ueber die volle Textbreite."""
    return anteil(paare, breite=BREITE)


def balken(eintraege: Sequence[Tuple[str, int]],
           betraege: Optional[Dict[str, float]] = None,
           einheit: str = "Vorfälle") -> str:
    """Horizontale Balken, eine Messgroesse, ein Farbton.

    Mit ``betraege`` (Titel -> Euro) steht rechts eine zweite Spalte —
    Anzahl und Betrag nebeneinander, ohne verrechnet zu werden: Die
    haeufigste Art ist nicht die gewichtigste. Die Spaltenbreiten richten
    sich nach dem laengsten Text, damit nichts ueberlaeuft.
    """
    eintraege = list(eintraege)
    hoechst = max((w for _, w in eintraege), default=1) or 1
    breite, zeile = BREITE, 26
    label = max([_textbreite(t) for t, _ in eintraege] + [40.0]) + 8
    zahl = max([_textbreite(_zahl(w)) for _, w in eintraege] + [24.0]) + 10
    betrag = (max([_textbreite(kurz(v) + " €") for v in betraege.values()] + [40.0]) + 12
              if betraege else 0.0)
    plot = breite - label - zahl - betrag
    teile: List[str] = []
    for i, (titel, wert) in enumerate(eintraege):
        y = 4 + i * zeile
        b = max(3.0, plot * wert / hoechst)
        teile.append(f'<g><title>{_e(titel)}: {_zahl(wert)} {_e(einheit)}</title>'
                     f'<text x="{label - 8:.0f}" y="{y + 11}" text-anchor="end" '
                     f'fill="{MATT}">{_e(titel)}</text>'
                     f'<rect x="{label:.0f}" y="{y}" width="{b:.1f}" height="14" '
                     f'rx="2" fill="{TRAEGER}"/>'
                     f'<text x="{label + b + 6:.0f}" y="{y + 11}" fill="{TINTE}">'
                     f"{_zahl(wert)}</text>")
        if betraege and titel in betraege:
            teile.append(f'<text x="{breite}" y="{y + 11}" text-anchor="end" '
                         f'fill="{MATT}">{_e(kurz(betraege[titel]))} €</text>')
        teile.append("</g>")
    return _svg(breite, 4 + zeile * len(eintraege) + 4,
                ", ".join(f"{t} {w}" for t, w in eintraege), teile)


def prozessband(segmente: Sequence[Tuple[str, int, bool]]) -> str:
    """Gate-Laeufe als Band: Segmentbreite = Anlaeufe, Farbe = Urteil.

    Hinter gruenen Urteilen stehen oft viele Anlaeufe — das Band zeigt,
    dass die Pruefstrecke keine Gummistempelmaschine ist. Ein nicht
    bestandenes Segment steht in Kontrastfarbe mit seinem Status.
    """
    gesamt = sum(max(1, int(v)) for _, v, _ in segmente) or 1
    nutz = 500 - 2 * (len(segmente) - 1)
    z = ['<svg role="img" aria-label="Gate-Laeufe: '
         + ", ".join(f"{t} {v} Anlaeufe" + ("" if ok else " nicht bestanden")
                     for t, v, ok in segmente)
         + f'" viewBox="0 0 520 44" style="width:100%;max-width:520px;height:auto;font:{SCHRIFTGROESSE}px system-ui,sans-serif">']
    x = 0
    for titel, versuche, ok in segmente:
        breite = max(10, round(nutz * max(1, int(versuche)) / gesamt))
        farbe = TRAEGER if ok else KONTRAST
        z.append(f'<g><title>{_e(titel)}: {versuche} Anlaeufe'
                 + ("" if ok else " — NICHT BESTANDEN") + "</title>"
                 f'<rect x="{x}" y="4" width="{breite}" height="16" rx="2" '
                 f'fill="{farbe}"/>')
        if breite >= 26:
            z.append(f'<text x="{x + breite / 2:.1f}" y="16" text-anchor="middle" '
                     f'fill="#fff" font-size="9">{_e(titel)}</text>')
        z.append(f'<text x="{x + breite / 2:.1f}" y="34" text-anchor="middle" '
                 f'fill="{MATT}" font-size="9">{versuche}</text></g>')
        x += breite + 2
    z.append("</svg>")
    return "".join(z)


def treppe(punkte: Sequence[Dict[str, Any]]) -> str:
    """Zeichnungen in Zeitreihenfolge; Hoehe = gebundene Artefakte.

    Jeder Punkt: ``gate``, ``gebunden``, ``final`` (bool), ``snapshot``
    (Kurzform). Finale Zeichnungen sind gefuellt und beschriftet,
    ueberholte offen — Zwischenstufen einer wachsenden Beleglage, keine
    Fehlschlaege.
    """
    if not punkte:
        return ""
    hoechst = max(int(p.get("gebunden") or 0) for p in punkte) or 1
    n = len(punkte)
    breite = 520
    schritt = (breite - 60) / max(n - 1, 1)
    z = ['<svg role="img" aria-label="Zeichnungskette: '
         + ", ".join(f"{p['gate']} {p.get('gebunden')} Artefakte"
                     + (" final" if p.get("final") else "") for p in punkte)
         + f'" viewBox="0 0 {breite} 110" style="width:100%;max-width:{breite}px;height:auto;font:{SCHRIFTGROESSE}px system-ui,sans-serif">']
    finale = [(i, p) for i, p in enumerate(punkte) if p.get("final")]
    def xy(i: int, p: Dict[str, Any]) -> Tuple[float, float]:
        return (30 + i * schritt, 80 - 60 * int(p.get("gebunden") or 0) / hoechst)
    if len(finale) > 1:
        pfad = " ".join(f"{'M' if k == 0 else 'L'}{xy(i, p)[0]:.1f},{xy(i, p)[1]:.1f}"
                        for k, (i, p) in enumerate(finale))
        z.append(f'<path d="{pfad}" fill="none" stroke="{TRAEGER}" '
                 f'stroke-width="2"/>')
    for i, p in enumerate(punkte):
        x, y = xy(i, p)
        final = bool(p.get("final"))
        z.append(f'<g><title>{_e(p["gate"])} · {p.get("gebunden")} gebundene '
                 f'Artefakte · Snapshot {_e(p.get("snapshot"))}'
                 + (" · final" if final else " · überholt") + "</title>")
        if final:
            z.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="{TRAEGER}"/>'
                     f'<text x="{x:.1f}" y="{y - 10:.1f}" text-anchor="middle" '
                     f'fill="{TINTE}">{_e(p["gate"])}</text>'
                     f'<text x="{x:.1f}" y="100" text-anchor="middle" '
                     f'fill="{MATT}" font-size="9">{p.get("gebunden")}</text>')
        else:
            z.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="#fff" '
                     f'stroke="{MATT}" stroke-width="1.5"/>')
        z.append("</g>")
    z.append("</svg>")
    return "".join(z)


# --------------------------------------------------------------------------- #
# Grenzen und Anlaufstellen
# --------------------------------------------------------------------------- #

def abgrenzungsband(karten: Sequence[Tuple[str, str, str]],
                    luecken: Sequence[str] = (),
                    leer_text: str = "Die Prüfartefakte weisen keine Lücke "
                                     "aus. Fachliche Einschränkungen, die "
                                     "nicht maschinell erfasst sind, stehen "
                                     "im Abschlussbericht.") -> str:
    """Was die Zahlen nicht sagen — an fester Stelle, nie wegklickbar.

    Jede Karte: (Aussage, Zahlen, Sicht 'fachlich'/'technisch'). Eine
    ausgewiesene Null ist eine Aussage; Schweigen liest sich als
    "nicht geprueft".
    """
    z = ['<div class="abgrenzungen">']
    for aussage, zahlen, sicht in karten:
        z.append(f'<div class="abgrenzung {_e(sicht)}"><b>{_e(aussage)}</b>'
                 + (f"<span>{_e(zahlen)}</span>" if zahlen else "")
                 + f'<i>{"technisch" if sicht == "technisch" else "fachlich"}</i></div>')
    for l in luecken:
        z.append(f'<div class="abgrenzung luecke"><b>Lücke: {_e(l)}</b></div>')
    if not karten and not luecken:
        z.append(f'<div class="abgrenzung leer"><b>{_e(leer_text)}</b></div>')
    z.append("</div>")
    return "".join(z)


def kacheln(eintraege: Sequence[Dict[str, Any]]) -> str:
    """Berichte als Anlaufstellen: Titel, Zweck, Kennzahl, Format."""
    z = ['<div class="kacheln">']
    for k in eintraege:
        marke = f'<em>{_e(k["format"])}</em>' if k.get("format") else ""
        z.append(f'<a class="kachel" href="{_e(k["href"])}"><b>{_e(k["titel"])}'
                 f"{marke}</b>"
                 + (f'<span class="kennzahl">{_e(k["kennzahl"])}</span>'
                    if k.get("kennzahl") else "")
                 + f'<span>{_e(k.get("zweck", ""))}</span></a>')
    z.append("</div>")
    return "".join(z)


def stationen(schritte: Sequence[Tuple[str, str, str]]) -> str:
    """Der Fall in Stationen: (Titel, Kennzahl, href) als Band."""
    z = ['<div class="stationen">']
    for titel, kennzahl, href in schritte:
        z.append(f'<a class="station" href="{_e(href)}"><b>{_e(kennzahl)}</b>'
                 f"<span>{_e(titel)}</span></a>")
    z.append("</div>")
    return "".join(z)


#: Kastenart des Prozessplans: Fuellung, Rand, Schrift der Kopfzeile, Name.
#: Die Farbe sagt, wer an der Station entscheidet (Entscheid des
#: Maintainers 04.10.2026): gelb, sobald ein Mensch abnimmt — auch wenn
#: das Haupt-Gate eine Programmpruefung ist —, gruen, wo nur das Programm
#: prueft, grau ohne eigenes Gate. Die Reihenfolge ist die der Legende.
_PLAN_ART = {
    "A": ("#fbf1c6", "#b48a00", "#6e5600", "Abnahme durch einen Menschen"),
    "P": ("#e4f2ea", "#3c8d5f", "#2b6b47", "Prüfung nur durch das Programm"),
    # Matt statt der weissen Flaeche der Seite: Weiss heisst in der Karte
    # "Mensch zeichnet" (die weissen Marken), und Legende wie Text sagen grau.
    None: ("var(--flaeche-matt, #e7eae4)", "var(--linie, #8192a8)", "var(--text-matt, #5f6663)", "ohne eigenes Gate"),
}


def _passt(text: str, schrift: int, fett: bool = False) -> float:
    """Geschaetzte Breite einer Zeile; fett laeuft breiter, Fliesstext
    schmaler als die Ziffern-Schaetzung von _textbreite."""
    return _textbreite(text, schrift) * (1.12 if fett else 0.93)


#: Farbe je Rolle — unabhaengig von der Gate-Farbe des Kastens. Die
#: Agentenrollen tragen ausgefuellte Marken, die menschliche Gegenrolle,
#: die ein Gate zeichnet, eine umrandete: legt vor gegen zeichnet.
ROLLEN_FARBE = {
    "Programmleitung": "#5f6663", "Aktuariat": "#7a5fbf",
    "Architektur": "#1c5cab", "Rechenkern": "#1c7c7c", "Betrieb": "#8a6d1f",
    "Vorstand": "#1b1e1c",
}
#: Kuerzel in den Kaesten; die Rollenleiste loest sie auf. Ausgeschrieben
#: waren die Marken zu viel Farbe je Kasten.
ROLLEN_KUERZEL = {"Programmleitung": "PL", "Aktuariat": "AK", "Architektur": "AR",
                  "Rechenkern": "RK", "Betrieb": "BE"}


def _marke(x: float, y: float, text: str, farbe: str, umrandet: bool = False,
           schrift_px: int = 12) -> Tuple[str, float]:
    """Eine Pille mit Kuerzel: gefuellt fuer eine Agentenrolle, weiss mit
    Rand fuer die menschliche Rolle, die zeichnet."""
    hoch = schrift_px + 8
    b = _textbreite(text, schrift_px) * 1.12 + schrift_px + 2   # fett laeuft breiter als die Schaetzung
    if umrandet:
        kasten = (f'<rect x="{x}" y="{y}" width="{b:.0f}" height="{hoch}" rx="{hoch / 2:.0f}" '
                  f'fill="#fff" stroke="{farbe}" stroke-width="1.5"/>')
        schrift = farbe
    else:
        kasten = f'<rect x="{x}" y="{y}" width="{b:.0f}" height="{hoch}" rx="{hoch / 2:.0f}" fill="{farbe}"/>'
        schrift = "#fff"
    return (kasten + f'<text x="{x + schrift_px * 0.6:.0f}" y="{y + hoch - 6}" font-size="{schrift_px}" '
            f'font-weight="700" fill="{schrift}">{_e(text)}</text>', b + 5)


def _umbrechen(text: str, schrift: int, breite: float) -> List[str]:
    """Text an Leerzeichen in Zeilen, die in ``breite`` passen (Schaetzung
    ueber die Zeichenbreite, wie ``_passt``)."""
    zeilen: List[str] = []
    zeile = ""
    for wort in text.split(" "):
        kandidat = f"{zeile} {wort}".strip()
        if zeile and _textbreite(kandidat, schrift) > breite:
            zeilen.append(zeile)
            zeile = wort
        else:
            zeile = kandidat
    if zeile:
        zeilen.append(zeile)
    return zeilen


def prozessplan(reihen: Sequence[Dict[str, Any]], band: str,
                rollen: Sequence[Sequence[str]], label: str) -> str:
    """Die Stationen als klickbare Kaesten, Reihe fuer Reihe von oben nach
    unten. Eine Reihe mit ``balken`` (ein einziger Kasten) laeuft ueber die
    ganze Breite — Auftrag und Lieferung oben, Zugang in die Buecher unten.
    Nach der ersten Kastenreihe das Band (Rueckfrageschleife), unten die
    Rollenleiste. Jede Reihe: {"titel": str, "balken": bool, "kaesten":
    [{"nummer", "zeilen", "gate", "art", "wer", "text", "href"}]}. Die
    Kaesten sind <a>-Gruppen — der Link sitzt im SVG selbst, nicht als
    Ueberlagerung."""
    # Die breiteste Kastenreihe bestimmt die Breite: Vier Kaesten ergeben
    # 50 + 4 * 236 + 3 * 26 + 50 = 1122 — in der Textspalte (921 px) rund
    # 0,82 der Groesse. Sieben Kaesten (1920) standen mit der Mindestbreite
    # von 1100 px bei 0,57 und liessen sich nur seitlich verschieben.
    B, LUECKE, X0 = 236, 26, 50
    INNEN = B - 28
    kastenreihen = [r for r in reihen if not r.get("balken")]
    spalten = max((len(r["kaesten"]) for r in kastenreihen), default=1)
    breite = 2 * X0 + spalten * B + (spalten - 1) * LUECKE
    voll = breite - 2 * X0
    # Kastenhoehe: Kopf, Titel, Text, dann die Artefaktzeilen, unten die Marken.
    zeilen_max = max((len(k.get("artefakte") or []) for r in kastenreihen for k in r["kaesten"]), default=0)
    H = 170 + 18 * zeilen_max + 30
    teile: List[str] = []

    def pruefe(text: str, schrift: int, fett: bool = False, spielraum: float = 0,
               innen: float = INNEN) -> None:
        if _passt(text, schrift, fett) + spielraum > innen:
            raise ValueError(f"Prozessplan: Zeile passt nicht in den Kasten: {text!r}")

    def marken(k: Dict[str, Any], x: float, y: float, rechts: float) -> List[str]:
        # Eine Zeile kleiner Marken: die Agentenrollen, die vorlegen
        # (gefuellt), dann die menschlichen Rollen, die zeichnen (weiss).
        aus: List[str] = []
        xm = x
        for rolle in k.get("rollen") or []:
            m, b = _marke(xm, y, ROLLEN_KUERZEL.get(rolle, rolle),
                          ROLLEN_FARBE.get(rolle, "#5f6663"), schrift_px=11)
            aus.append(m); xm += b
        for kuerzel, rolle in k.get("zeichnen") or []:
            m, b = _marke(xm, y, kuerzel, ROLLEN_FARBE.get(rolle, "#5f6663"),
                          umrandet=True, schrift_px=11)
            aus.append(m); xm += b
        if xm - 5 > rechts:
            raise ValueError(f"Prozessplan: die Marken von Station {k['nummer']} passen nicht in den Kasten")
        return aus

    def belege(k: Dict[str, Any], x: float, y: float, rechts: float, innen: float) -> List[str]:
        # Artefaktzeilen als eigene Links NEBEN dem Kasten-Link, nicht darin:
        # verschachtelte <a> sind nicht erlaubt; spaeter Gezeichnetes liegt
        # oben und faengt den Klick.
        aus: List[str] = []
        tag = "In Arbeit"
        for beschriftung, href in k.get("artefakte") or []:
            if href:
                pruefe(beschriftung, 13, innen=innen)
                aus.append(f'<a href="{_e(href)}" class="artefakt"><title>{_e(beschriftung)}</title>'
                           f'<text x="{x}" y="{y}" font-size="13" fill="var(--primaer, #1c5cab)" '
                           f'text-decoration="underline">{_e(beschriftung)}</text></a>')
            else:
                pruefe(beschriftung, 13, spielraum=_passt(tag, 13) + 8, innen=innen)
                aus.append(f'<text x="{x}" y="{y}" font-size="13" fill="var(--text-matt, #5f6663)">{_e(beschriftung)}</text>'
                           f'<text x="{rechts}" y="{y}" font-size="13" font-style="italic" text-anchor="end" '
                           f'fill="var(--text-matt, #5f6663)">{tag}</text>')
            y += 18
        return aus

    def kopf(k: Dict[str, Any]) -> str:
        return f'STATION {k["nummer"]}' + (f' · {_e(k["gate"])}' if k.get("gate") else "")

    def kasten(k: Dict[str, Any], xk: float, yk: float) -> str:
        fuell, rand, schrift, _ = _PLAN_ART[k.get("art")]
        t = [f'<a href="{_e(k["href"])}" class="station">'
             f'<title>{_e(k.get("wohin") or k["zeilen"][0])}</title>'
             f'<rect x="{xk}" y="{yk}" width="{B}" height="{H}" rx="10" fill="{fuell}" stroke="{rand}" stroke-width="1.5"/>'
             f'<text x="{xk + 14}" y="{yk + 24}" font-size="12" font-weight="700" fill="{schrift}">{kopf(k)}</text>']
        ty = yk + 50
        for z in k["zeilen"]:
            pruefe(z, 19, fett=True)
            t.append(f'<text x="{xk + 14}" y="{ty}" font-size="19" font-weight="700" '
                     f'fill="var(--text-tinte, #1b1e1c)">{_e(z)}</text>')
            ty += 24
        ty = yk + 100
        for z in (k.get("wer"), *k.get("text", [])):
            if z:
                pruefe(z, 14)
                t.append(f'<text x="{xk + 14}" y="{ty}" font-size="14" fill="var(--text-matt, #5f6663)">{_e(z)}</text>')
                ty += 19
        t.append("</a>")
        t += belege(k, xk + 14, yk + 162, xk + B - 14, INNEN)
        t += marken(k, xk + 10, yk + H - 28, xk + B - 8)
        return "".join(t)

    def balken(k: Dict[str, Any], xk: float, yk: float) -> Tuple[str, float]:
        # Drei Spalten nebeneinander: Kopf und Titel, Text, Belege.
        fuell, rand, schrift, _ = _PLAN_ART[k.get("art")]
        x2, x3 = xk + 300, xk + 640
        text = [z for z in (k.get("wer"), *k.get("text", [])) if z]
        n_belege = len(k.get("artefakte") or [])
        hb = max(78, 30 + 19 * max(len(text) - 1, 0), 30 + 18 * max(n_belege - 1, 0)) + 40
        titel = " ".join(k["zeilen"])
        pruefe(titel, 19, fett=True, innen=x2 - xk - 28)
        t = [f'<a href="{_e(k["href"])}" class="station">'
             f'<title>{_e(k.get("wohin") or titel)}</title>'
             f'<rect x="{xk}" y="{yk}" width="{voll}" height="{hb}" rx="10" fill="{fuell}" stroke="{rand}" stroke-width="1.5"/>'
             f'<text x="{xk + 14}" y="{yk + 24}" font-size="12" font-weight="700" fill="{schrift}">{kopf(k)}</text>'
             f'<text x="{xk + 14}" y="{yk + 50}" font-size="19" font-weight="700" '
             f'fill="var(--text-tinte, #1b1e1c)">{_e(titel)}</text>']
        ty = yk + 30
        for z in text:
            pruefe(z, 14, innen=x3 - x2 - 20)
            t.append(f'<text x="{x2}" y="{ty}" font-size="14" fill="var(--text-matt, #5f6663)">{_e(z)}</text>')
            ty += 19
        t.append("</a>")
        t += belege(k, x3, yk + 30, xk + voll - 14, xk + voll - 14 - x3)
        t += marken(k, xk + 10, yk + hb - 28, x2 - 20)
        return "".join(t), hb

    def pfeil(*punkte: Tuple[float, float]) -> str:
        weg = " ".join(f"{'M' if i == 0 else 'L'}{x} {y}" for i, (x, y) in enumerate(punkte))
        return (f'<path d="{weg}" stroke="var(--linie, #8192a8)" stroke-width="2" fill="none" '
                f'marker-end="url(#pfeil)"/>')

    # Legende, in zwei Zeilen: die Arten der Kaesten, dann Beleg und "In Arbeit".
    x = X0
    for art, (fuell, rand, _schrift, name) in _PLAN_ART.items():
        teile.append(f'<rect x="{x}" y="18" width="18" height="18" rx="4" fill="{fuell}" stroke="{rand}"/>'
                     f'<text x="{x + 26}" y="32" font-size="15" fill="var(--text-matt, #5f6663)">{_e(name)}</text>')
        x += 40 + _textbreite(name, 15)
    x = X0
    teile.append(f'<text x="{x}" y="60" font-size="15" fill="var(--primaer, #1c5cab)" text-decoration="underline">Beleg des Laufs</text>')
    x += 40 + _textbreite("Beleg des Laufs", 15)
    teile.append(f'<text x="{x}" y="60" font-size="15" font-style="italic" fill="var(--text-matt, #5f6663)">In Arbeit: liegt im Lauf noch nicht vor</text>')

    y = 92
    ende: Optional[Tuple[float, float]] = None     # wo der Weg zuletzt endete (x, y unten)
    band_gesetzt = False
    for reihe in reihen:
        if reihe.get("balken"):
            if ende:
                teile.append(pfeil((ende[0], ende[1] + 2), (ende[0], y - 4)))
            svg, hb = balken(reihe["kaesten"][0], X0, y)
            teile.append(svg)
            ende = (X0 + B / 2, y + hb)
            y += hb + 34
            continue
        if ende:
            if ende[0] == X0 + B / 2:
                teile.append(pfeil((ende[0], ende[1] + 2), (ende[0], y - 4)))
            else:
                teile.append(pfeil((ende[0], ende[1] + 2), (ende[0], y - 18),
                                   (X0 + B / 2, y - 18), (X0 + B / 2, y - 4)))
        teile.append(f'<text x="{X0}" y="{y + 16}" font-size="18" font-weight="700" '
                     f'fill="var(--text-tinte, #1b1e1c)">{_e(reihe["titel"])}</text>')
        yk = y + 32
        for i, k in enumerate(reihe["kaesten"]):
            xk = X0 + i * (B + LUECKE)
            teile.append(kasten(k, xk, yk))
            if i:   # Pfeil vom Vorgaenger
                teile.append(pfeil((xk - LUECKE + 4, yk + H / 2), (xk - 4, yk + H / 2)))
        ende = (X0 + (len(reihe["kaesten"]) - 1) * (B + LUECKE) + B / 2, yk + H)
        y = yk + H + 34
        if not band_gesetzt:
            # Die Rueckfrageschleife nach der ersten Kastenreihe: Von dort
            # kehrt am meisten zurueck (Diskrepanzen der Quellen).
            band_gesetzt = True
            zeilen = _umbrechen(band, 15, voll - B - 40 - 32)
            hband = 20 + 22 * len(zeilen)
            teile.append(pfeil((ende[0], ende[1] + 2), (ende[0], y + hband / 2),
                               (X0 + B / 2, y + hband / 2), (X0 + B / 2, y + hband + 30)))
            teile.append(f'<rect x="{X0 + B + 40}" y="{y}" width="{voll - B - 40}" height="{hband}" rx="8" '
                         f'fill="#fdf0e6" stroke="#d64d1f"/>'
                         + "".join(f'<text x="{X0 + B + 56}" y="{y + 26 + 22 * i}" font-size="15" '
                                   f'fill="#7a2e12">{_e(z)}</text>' for i, z in enumerate(zeilen)))
            y += hband + 34
            ende = None
    # Rollenleiste: so viele Spalten, wie die Breite traegt.
    spalten_r = max(1, min(len(rollen), int((voll - 32) // 300)))
    reihen_r = -(-len(rollen) // spalten_r)
    hr = 40 + 92 * reihen_r - 10
    teile.append(f'<rect x="{X0}" y="{y}" width="{voll}" height="{hr}" rx="10" fill="#f6f1ff" stroke="#7a5fbf"/>')
    teile.append(f'<text x="{X0 + 16}" y="{y + 26}" font-size="15" font-weight="700" fill="#4a3a80">'
                 f'ROLLEN · farbig: Agentenrolle legt vor · weiß: Mensch zeichnet</text>')
    sp = (voll - 32) / spalten_r
    for i, (agent, mensch, aufgabe) in enumerate(rollen):
        xr = X0 + 16 + (i % spalten_r) * sp
        yr = y + 40 + (i // spalten_r) * 92
        # Ohne Agentenrolle (der Vorstand) steht die zeichnende Rolle oben.
        farbe = ROLLEN_FARBE.get(agent or mensch[1], "#5f6663")
        if agent:
            m, b = _marke(xr, yr, ROLLEN_KUERZEL.get(agent, agent), farbe)
            teile.append(m)
            teile.append(f'<text x="{xr + b}" y="{yr + 14}" font-size="15" font-weight="700" fill="var(--text-tinte, #1b1e1c)">{_e(agent)}</text>')
            m2, b2 = _marke(xr, yr + 28, mensch[0], farbe, umrandet=True)
            teile.append(m2)
            teile.append(f'<text x="{xr + b2}" y="{yr + 42}" font-size="14" fill="var(--text-matt, #5f6663)">{_e(mensch[1])}</text>')
        else:
            m2, b2 = _marke(xr, yr, mensch[0], farbe, umrandet=True)
            teile.append(m2)
            teile.append(f'<text x="{xr + b2}" y="{yr + 14}" font-size="15" font-weight="700" fill="var(--text-tinte, #1b1e1c)">{_e(mensch[1])}</text>')
        teile.append(f'<text x="{xr}" y="{yr + 64}" font-size="14" fill="var(--text-matt, #5f6663)">{_e(aufgabe)}</text>')
    hoehe = y + hr + 24
    marker = ('<defs><marker id="pfeil" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto">'
              '<path d="M0 0 L8 4 L0 8 z" fill="var(--linie, #8192a8)"/></marker></defs>')
    return _svg(breite, hoehe, label, [marker, *teile])
