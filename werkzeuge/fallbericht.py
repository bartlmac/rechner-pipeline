"""``fallbericht`` — aus dem Datenmodell eines Falls eine Darstellung bauen.

Beobachtungshilfe, kein Gate. Sie rendert, was ``falldaten.py`` erhoben
hat, und fügt genau an den vorgesehenen Stellen freien Text hinzu.

**Die Arbeitsteilung ist der Zweck.** Zahlen kommen aus dem Modell und
ändern sich beim nächsten Lauf von selbst; Struktur und Beschriftungen
stehen hier und bleiben; erzählt wird nur, was sich nicht ableiten lässt.
Das sind vier Stellen, und zwei davon füllen sich aus signierten Quellen:

1. ``anlass`` — worum es in diesem Fall geht. Von Hand, ein Absatz.
2. ``wirkung`` je Diskrepanz — was der Befund fachlich bedeutet, eine
   Zeile. Von Hand.
3. die Begründungen der Abnahmen — wörtlich aus den Entscheid-Snapshots.
   Deren Schema, Selbstadressierung und Dateiname prüft dieses Werkzeug;
   die Freigabesignatur NICHT (kein Schlüsselring in einem
   Darstellungswerkzeug, externes Review T19-02).
4. Auszüge aus registrierten Quellen — ebenfalls gebunden.

Wer die Darstellung ohne Textdatei baut, bekommt eine vollständige Seite
ohne Erzählung. Das ist Absicht: Die Zahlen tragen für sich, der Text
ordnet nur ein.

**Zwei Sichten, ein Modell.** Die fachliche Sicht führt Bestand, Abnahmen
und die Werte der Befunde; die technische führt Provenienz, Kette und die
Belegmethode. Die Abgrenzungen sind im Modell je Sicht markiert und
verteilen sich entsprechend.

Aufruf::

    python werkzeuge/falldaten.py --fall faelle/<fall> --out daten.json
    python werkzeuge/fallbericht.py --daten daten.json --out bericht.html \\
        [--texte texte.json]

Der Renderer gibt BEIDE Sichten gemeinsam aus; eine Auswahl ueber
``--sicht`` stand hier frueher im Aufrufvertrag, war aber nie gebaut
(externes Review T19-07).
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

GROESSEN_TITEL = {
    "entry_age": "Eintrittsalter",
    "duration": "Laufzeit",
    "premium_duration": "Beitragszahlungsdauer",
    "sum_insured": "Versicherungssumme",
    "deckkap": "Deckungskapital",
    "jbrutto": "Jahresbeitrag",
    "erlsumme": "Versicherungssumme (Abzug)",
}
GEVO_TITEL = {
    "ERH": "Erhöhung", "PEX": "Beitragsfreistellung", "RED": "Absetzung",
    "STO": "Rückkauf", "TOD": "Todesfall", "ABL": "Ablauf",
}


def _e(x: Any) -> str:
    return html.escape(str(x if x is not None else ""))


def _zahl(x: Any, dez: int = 2) -> str:
    if not isinstance(x, (int, float)):
        return _e(x)
    if isinstance(x, int) or float(x).is_integer():
        return f"{int(x):,}".replace(",", ".")
    return f"{x:,.{dez}f}".replace(",", "@").replace(".", ",").replace("@", ".")


def _quelle(d: Dict[str, Any], gruppe: str) -> str:
    """Woraus dieser Abschnitt gelesen wurde.

    Ohne die Angabe bleibt "alle Zahlen sind nachrechenbar" eine
    Behauptung: Der Leser wuesste nicht, WO er nachrechnen soll.
    """
    quellen = (d.get(gruppe) or {}).get("gelesen_aus") or []
    if not quellen:
        return ""
    return ('<p class="quelle">Gelesen aus '
            + ", ".join(f"<code>{_e(q)}</code>" for q in quellen)
            + "</p>")


def _tabelle(kopf: List[str], zeilen: List[List[str]],
             titel: str = "", rechts: Optional[List[int]] = None) -> str:
    rechts = rechts or []
    z = ['<div class="scroll"><table>']
    if titel:
        z.append(f"<caption>{_e(titel)}</caption>")
    z.append("<thead><tr>" + "".join(f"<th>{_e(k)}</th>" for k in kopf)
             + "</tr></thead><tbody>")
    for zeile in zeilen:
        z.append("<tr>" + "".join(
            f'<td class="r">{c}</td>' if i in rechts else f"<td>{c}</td>"
            for i, c in enumerate(zeile)) + "</tr>")
    z.append("</tbody></table></div>")
    return "".join(z)


# --------------------------------------------------------------------------- #
# Fachliche Sicht
# --------------------------------------------------------------------------- #

def _fach(d: Dict[str, Any], texte: Dict[str, Any]) -> str:
    z: List[str] = []
    b = d.get("bestand") or {}
    a = d.get("abnahmen") or {}

    z.append('<div class="block f"><span class="marke">Fachliche Sicht</span>')
    z.append("<h2>Der Bestand</h2>")

    if b.get("vorhanden"):
        zeilen = []
        for schluessel, k in sorted((b.get("groessen") or {}).items()):
            if not k:
                continue
            zeilen.append([_e(GROESSEN_TITEL.get(schluessel, schluessel)),
                           _zahl(k["min"]), _zahl(k["max"]), _zahl(k["median"])])
        for abzug in (b.get("abzuege") or [])[:1]:
            for schluessel in ("deckkap", "jbrutto"):
                k = abzug.get(schluessel)
                if k:
                    zeilen.append([_e(GROESSEN_TITEL.get(schluessel, schluessel)),
                                   _zahl(k["min"]), _zahl(k["max"]),
                                   _zahl(k["median"])])
        z.append(_tabelle(["Größe", "kleinster", "größter", "Median"], zeilen,
                          f"{_zahl(b['anzahl'])} Verträge am Übernahmestichtag",
                          rechts=[1, 2, 3]))

        for name, titel in (("vorgeschichte", "Vorgeschichte vor der Übernahme"),
                            ("vorfaelle_im_zeitraum", "Geschäftsvorfälle im Prüfzeitraum")):
            g = (b.get(name) or {}).get("je_art") or {}
            if not g:
                continue
            zeilen = [[_e(GEVO_TITEL.get(art, art)), _zahl(e["anzahl"]),
                       _zahl(e.get("betrag_summe", "")) if e.get("betrag_summe") else "—"]
                      for art, e in sorted(g.items())]
            z.append(_tabelle(["Art", "Anzahl", "Betragssumme"], zeilen, titel,
                              rechts=[1, 2]))

        for probe in b.get("kreuzproben") or []:
            wort = "geht auf" if probe.get("stimmt") else "GEHT NICHT AUF"
            z.append(f'<p class="probe">{_e(probe["was"])}: '
                     f'{_zahl(probe["links"])} gegen {_zahl(probe["rechts"])} '
                     f'— <b>{wort}</b>.</p>')

    z.append(_quelle(d, "bestand"))
    z.append(_transformation(d))

    z.append("<h2>Die Abnahmen</h2>")
    zeilen = []
    for t in a.get("aktuariell", []):
        v = t.get("verteilung") or {}
        s = t.get("stichprobe") or {}
        zeilen.append([
            f'<b>{_e(t["kennung"])}</b> {_e(t["titel"])}',
            _zahl(s.get("umfang")) + (" (Vollerhebung)" if s.get("vollerhebung")
                                      else f" von {_zahl(s.get('grundgesamtheit'))}"),
            f'{_zahl(t["bestanden"])} / {_zahl(t["anzahl"])}',
            _zahl(v.get("max_abs_residuum"), 4) + " €" if v else "—",
        ])
    c = a.get("controlling") or {}
    if c:
        zeilen.append([
            "<b>A-M4</b> Migrationscontrolling",
            f'{_zahl(c["anzahl"])} (ganzer Bestand)',
            f'{_zahl(c["bestanden"])} / {_zahl(c["anzahl"])}',
            f'{_zahl(c["pruefluecken"])} Prüflücken',
        ])
    z.append(_tabelle(["Abnahme", "Umfang", "Ergebnis", "größte Abweichung"],
                      zeilen, "Was geprüft wurde", rechts=[1, 2, 3]))

    for t in a.get("aktuariell", []):
        je = t.get("je_groesse") or {}
        if not je:
            continue
        zeilen = [[_e(g), _zahl(w.get("anzahl_werte")),
                   _zahl(w.get("max_abs_residuum"), 6),
                   _zahl(w.get("p95_abs_residuum"), 6)]
                  for g, w in sorted(je.items())]
        z.append(_tabelle(["Vergleichsgröße", "Werte", "max |R|", "p95 |R|"],
                          zeilen, f"{t['kennung']} — Residuen je Größe (Euro)",
                          rechts=[1, 2, 3]))

    z.append(_quelle(d, "abnahmen"))
    z.append(_befunde(d, texte, "fachlich"))
    z.append(_abgrenzungen(d, "fachlich"))
    z.append("</div>")
    return "".join(z)


def _transformation(d: Dict[str, Any]) -> str:
    """Das Feldmapping — der Uebersetzungsakt als Tabelle.

    Er ist der fachliche Kern einer Migration und zugleich die Stelle, an
    der ein Missverstaendnis nicht auffaellt, weil hinterher alles rechnet.
    Deshalb steht hier nicht nur, WAS abgebildet wurde, sondern auch, was
    ausdruecklich draussen blieb und warum.
    """
    t = d.get("transformation") or {}
    if not t.get("vorhanden"):
        return ""
    z = ["<h2>Die Übersetzung</h2>"]
    z.append(f'<p>{_zahl(t.get("anzahl_quellspalten"))} Quellspalten wurden auf '
             f'{_zahl(t.get("anzahl_zielfelder"))} Zielfelder abgebildet. '
             f'{_zahl(t.get("zeilen_quelle"))} Zeilen gingen hinein, '
             f'{_zahl(t.get("zeilen_ziel"))} kamen heraus'
             + (f', {_zahl(len(t.get("befunde") or []))} Befunde.'
                if t.get("befunde") else ' — ohne Befund.') + '</p>')

    zeilen = []
    for f in t.get("felder", []):
        art = f.get("berechnung") or ("Kodierung" if f.get("kodierung") else "—")
        kodierung = ""
        if f.get("kodierung"):
            kodierung = ", ".join(f"{_e(k)} → {_e(v)}"
                                  for k, v in sorted(f["kodierung"].items()))
        zeilen.append([
            ", ".join(f"<code>{_e(q)}</code>" for q in f.get("quellen") or []),
            f'<code>{_e(f.get("ziel"))}</code>',
            _e(art),
            kodierung or "",
        ])
    z.append(_tabelle(["Quelle", "Ziel", "Umsetzung", "Kodierung"], zeilen,
                      "Feldabbildung"))

    nicht = t.get("nicht_uebernommen") or []
    if nicht:
        z.append('<div class="fund"><p class="titel">'
                 f'{_zahl(len(nicht))} Quellspalten wurden ausdrücklich '
                 'nicht übernommen</p>')
        for e in nicht:
            spalten = ", ".join(f"<code>{_e(q)}</code>"
                                for q in e.get("quellen") or [])
            grund = e.get("begruendung") or "<b>ohne Begründung</b>"
            z.append(f"<p>{spalten} — {_e(grund) if e.get('begruendung') else grund}</p>")
        z.append("</div>")

    if t.get("stumm_weggelassen"):
        z.append('<div class="fund"><p class="titel">Weder abgebildet noch '
                 'verworfen</p><p>'
                 + ", ".join(f"<code>{_e(s)}</code>"
                             for s in t["stumm_weggelassen"])
                 + " — über diese Spalten hält der Spec nichts fest.</p></div>")

    konflikte = t.get("konflikte") or []
    if konflikte:
        z.append('<div class="fund"><p class="titel">'
                 f'{_zahl(len(konflikte))} offene Fragen der Übersetzung, '
                 'menschlich entschieden</p>')
        for k in konflikte:
            z.append(f'<p><code>{_e(k.get("quellspalte"))}</code> — '
                     f'{_e(k.get("entscheidung"))}</p>')
        z.append("</div>")

    abgeleitet = t.get("abgeleitete_felder") or []
    if abgeleitet:
        z.append("<p>Aus mehreren Quellspalten <em>abgeleitet</em> statt "
                 "kopiert: " + ", ".join(f"<code>{_e(f)}</code>"
                                         for f in abgeleitet) + ".</p>")
    for anmerkung in t.get("anmerkungen") or []:
        z.append(f'<p class="probe">{_e(anmerkung)}</p>')
    z.append(_quelle(d, "transformation"))
    return "".join(z)


# --------------------------------------------------------------------------- #
# Technische Sicht
# --------------------------------------------------------------------------- #

def _it(d: Dict[str, Any], texte: Dict[str, Any]) -> str:
    z: List[str] = []
    l = d.get("lieferung") or {}
    k = d.get("kette") or {}

    z.append('<div class="block i"><span class="marke">Technische Sicht</span>')
    z.append("<h2>Die Lieferung</h2>")
    zeilen = [[f'<code>{_e(q["datei"])}</code>', _zahl(q.get("bytes")),
               f'<code>{_e(str(q.get("sha256"))[:12])}…</code>',
               "nachgereicht" if q.get("nachgereicht") else ""]
              for q in l.get("quellen", [])]
    z.append(_tabelle(["Datei", "Bytes", "Prüfsumme", ""], zeilen,
                      f'{_zahl(l.get("anzahl"))} registrierte Quellen, '
                      f'davon {_zahl(l.get("anzahl_nachgereicht"))} auf Rückfrage',
                      rechts=[1]))

    z.append(_quelle(d, "lieferung"))
    z.append("<h2>Die Kette</h2>")
    zeilen = [[_e(g.get("gate")), f'<code>{_e(g.get("kommando"))}</code>',
               _e(g.get("status")), _e(str(g.get("gestartet"))[11:19])]
              for g in k.get("gates", [])]
    z.append(_tabelle(["Gate", "Kommando", "Urteil", "Zeit"], zeilen,
                      f'{_zahl(k.get("anzahl_gate_laeufe"))} Gate-Läufe'))

    zeilen = [[_e(e.get("gate")), _e(e.get("entscheid")), _e(e.get("rolle")),
               _e(e.get("schluesselklasse") or "—"),
               f'<code>{_e(e.get("schluessel_sha256"))}…</code>',
               _zahl(e.get("artefakte_gebunden"))]
              for e in k.get("entscheide", [])]
    z.append(_tabelle(["Gate", "Entscheid", "Rolle", "Schlüsselklasse", "Schlüssel",
                       "gebundene Artefakte"],
                      zeilen, "Die menschlichen Abnahmen", rechts=[5]))

    for e in k.get("entscheide", []):
        if e.get("begruendung"):
            z.append(f'<blockquote><p>{_e(e["begruendung"])}</p>'
                     f'<cite>Begründung im Snapshot {_e(e["gate"])}, '
                     f'entschieden {_e(str(e.get("entschieden_am"))[:10])}'
                     f'{"" if e.get("strukturell_verifiziert") else " — Snapshot mit Befund"}'
                     f'</cite>'
                     f'</blockquote>')

    z.append(_quelle(d, "kette"))
    z.append(_befunde(d, texte, "technisch"))
    z.append(_abgrenzungen(d, "technisch"))
    z.append("</div>")
    return "".join(z)


# --------------------------------------------------------------------------- #

def _befunde(d: Dict[str, Any], texte: Dict[str, Any], sicht: str) -> str:
    """Die Diskrepanzen — fachlich als Werte, technisch als Belegmethode."""
    p = d.get("parameter") or {}
    disk = p.get("diskrepanzen") or []
    if not disk:
        return ""
    z = ["<h2>Befunde an der Lieferung</h2>"]

    if sicht == "fachlich":
        zeilen = []
        for e in disk:
            lesarten = e.get("lesarten") or []
            werte = " gegen ".join(_e(l.get("wert")) for l in lesarten)
            zeilen.append([_e(e.get("feld")), _e(e.get("knoten")), werte,
                           f'<b>{_e(e.get("gewaehlt"))}</b>'])
        z.append(_tabelle(["Feld", "Zelle", "Lesarten", "gewählt"], zeilen,
                          f"{len(disk)} Widersprüche zwischen Meldung und Rechner"))
        z.append(_quelle(d, "parameter"))
        for schluessel, text in (texte.get("wirkung") or {}).items():
            z.append(f'<div class="fund"><p class="titel">{_e(schluessel)}</p>'
                     f'<p>{_e(text)}</p></div>')
    else:
        for name, beleg in (p.get("belege") or {}).items():
            z.append(f'<div class="fund"><p class="titel">Belegrechnung '
                     f'<code>{_e(name)}</code></p>')
            for feld in ("gegenstand", "belegmenge", "reihenfolge"):
                if beleg.get(feld):
                    z.append(f"<p>{_e(beleg[feld])}</p>")
            for schluessel in ("abgleiche", "kandidaten"):
                eintraege = beleg.get(schluessel) or {}
                if not eintraege:
                    continue
                zeilen = []
                for name2, e in sorted(eintraege.items()):
                    if not isinstance(e, dict):
                        continue
                    zeilen.append([
                        _e(name2), _zahl(e.get("geprueft")),
                        _zahl(e.get("verletzt")),
                        _zahl(e.get("quote_stuetzend"), 3)
                        if e.get("quote_stuetzend") is not None else "—",
                    ])
                if zeilen:
                    z.append(_tabelle(["Lesart", "geprüft", "verletzt",
                                       "Quote"], zeilen, rechts=[1, 2, 3]))
            z.append("</div>")
    return "".join(z)


def _abgrenzungen(d: Dict[str, Any], sicht: str) -> str:
    eintraege = [a for a in d.get("abgrenzungen") or [] if a.get("sicht") == sicht]
    if not eintraege:
        return ""
    z = ["<h3>Wo die Aussage endet</h3><ul>"]
    for a in eintraege:
        teil = f'<strong>{_e(a["was"])}</strong>'
        if a.get("abnahme"):
            teil = f'{_e(a["abnahme"])}: ' + teil
        if a.get("zahlen"):
            teil += f' — {_e(a["zahlen"])}'
        z.append(f"<li>{teil}</li>")
    z.append("</ul>")
    return "".join(z)


def _kopf(d: Dict[str, Any], texte: Dict[str, Any]) -> str:
    b = d.get("bestand") or {}
    a = d.get("abnahmen") or {}
    c = a.get("controlling") or {}
    abzug = (b.get("abzuege") or [{}])[0]
    dk = (abzug.get("deckkap") or {}).get("summe")
    _kette = d.get("kette") or {}
    # T19-02: Dieses Werkzeug prueft keine Signaturen (kein
    # Schluesselring) — gezaehlt werden strukturell unversehrte
    # Snapshots, und die Kachel sagt genau das.
    eingereicht = _kette.get("entscheide_strukturell_verifiziert")
    if eingereicht is None:
        eingereicht = len(_kette.get("entscheide") or [])

    kacheln = [
        (_zahl(b.get("anzahl")), "Verträge"),
        (_e(", ".join((d.get("parameter") or {}).get("generationen") or [])),
         "Tarifgeneration"),
        (f"{_zahl(dk)} €" if dk else "—", "Deckungskapital"),
        (f'{_e(c.get("stichtag_1"))} / {_e(c.get("stichtag_2"))}'
         if c else "—", "Stichtage"),
        (_zahl(eingereicht), "Abnahmen eingereicht"),
    ]
    z = [f'<h1>{_e(texte.get("titel") or d["fall"]["name"])}</h1>']
    if texte.get("anlass"):
        z.append(f'<p class="unter">{_e(texte["anlass"])}</p>')
    z.append('<div class="zahlen">')
    for wert, beschriftung in kacheln:
        z.append(f'<div class="zahl"><b>{wert}</b><span>{beschriftung}</span></div>')
    z.append("</div>")
    return "".join(z)


STIL = """
:root{--grund:#f8f8f6;--flaeche:#fff;--tinte:#1b1e1c;--matt:#5f6663;
--linie:#dcdfda;--stark:#c1c6bf;--fach:#8c4a2f;--fach-flach:#f8e8e0;
--it:#2f5d62;--it-flach:#e7efef}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
--grund:#101312;--flaeche:#171b19;--tinte:#e7eae6;--matt:#98a09b;
--linie:#272d2a;--stark:#3a423d;--fach:#d9a184;--fach-flach:#2a1a13;
--it:#7fb3b6;--it-flach:#16282a}}
:root[data-theme="dark"]{--grund:#101312;--flaeche:#171b19;--tinte:#e7eae6;
--matt:#98a09b;--linie:#272d2a;--stark:#3a423d;--fach:#d9a184;
--fach-flach:#2a1a13;--it:#7fb3b6;--it-flach:#16282a}
*{box-sizing:border-box}
body{margin:0;background:var(--grund);color:var(--tinte);
font:15.5px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:60rem;margin:0 auto;padding:3.5rem 1.3rem 6rem}
h1{font:600 2.2rem/1.12 Georgia,serif;margin:0 0 .5rem;letter-spacing:-.015em}
h2{font:600 1.35rem/1.25 Georgia,serif;margin:2.4rem 0 .8rem}
h3{font:600 .95rem/1.3 system-ui,sans-serif;margin:2rem 0 .5rem;
text-transform:uppercase;letter-spacing:.05em;color:var(--matt)}
p{margin:0 0 .85rem;max-width:44rem}
.unter{color:var(--matt);font-size:1.02rem;margin-bottom:2rem}
code{font:.85em ui-monospace,Menlo,monospace;
background:color-mix(in srgb,var(--linie) 55%,transparent);
padding:.1em .35em;border-radius:3px}
.zahlen{display:grid;gap:1px;background:var(--linie);border:1px solid var(--linie);
border-radius:6px;overflow:hidden;margin:0 0 3rem;
grid-template-columns:repeat(auto-fit,minmax(9.5rem,1fr))}
.zahl{background:var(--flaeche);padding:.9rem 1rem}
.zahl b{display:block;font:600 1.3rem/1.15 Georgia,serif;
font-variant-numeric:tabular-nums;margin-bottom:.2rem;word-break:break-word}
.zahl span{font-size:.72rem;color:var(--matt);text-transform:uppercase;
letter-spacing:.05em}
.block{border-left:4px solid;padding:.2rem 0 .2rem 1.5rem;margin:0 0 3.5rem}
.block.f{border-color:var(--fach)}.block.i{border-color:var(--it)}
.marke{display:inline-block;font-size:.69rem;font-weight:600;letter-spacing:.08em;
text-transform:uppercase;padding:.2em .6em;border-radius:3px;margin-bottom:.4rem}
.block.f .marke{background:var(--fach-flach);color:var(--fach);border:1px solid var(--fach)}
.block.i .marke{background:var(--it-flach);color:var(--it);border:1px solid var(--it)}
.scroll{overflow-x:auto;margin:.9rem 0 1.5rem;border:1px solid var(--linie);
border-radius:6px;background:var(--flaeche)}
table{border-collapse:collapse;width:100%;font-size:.87rem;
font-variant-numeric:tabular-nums}
caption{text-align:left;font-weight:600;padding:.8rem 1rem .1rem;font-size:.9rem}
th{text-align:left;font-size:.7rem;text-transform:uppercase;letter-spacing:.06em;
color:var(--matt);font-weight:600;padding:.6rem 1rem;
border-bottom:1px solid var(--stark);white-space:nowrap}
td{padding:.5rem 1rem;border-bottom:1px solid var(--linie);vertical-align:top}
td.r{text-align:right;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
blockquote{margin:1rem 0;padding:.85rem 1rem;background:var(--flaeche);
border:1px solid var(--linie);border-left:3px solid var(--stark);
border-radius:0 4px 4px 0;font-size:.89rem}
blockquote p{margin:0;max-width:none}
blockquote cite{display:block;margin-top:.45rem;font-size:.76rem;
color:var(--matt);font-style:normal}
.fund{padding:.9rem 1.1rem;border-radius:4px;margin:1.2rem 0}
.block.f .fund{background:var(--fach-flach)}
.block.i .fund{background:var(--it-flach)}
.fund p{margin:0 0 .5rem;max-width:none}.fund p:last-child{margin-bottom:0}
.fund .titel{font-weight:600}
.probe{font-size:.9rem;color:var(--matt)}
.quelle{font-size:.76rem;color:var(--matt);margin:-.8rem 0 1.6rem;
font-family:ui-monospace,Menlo,monospace}
.quelle code{background:none;padding:0}
ul{padding-left:1.1rem;margin:0 0 1rem;max-width:44rem}
li{margin-bottom:.4rem}
.fuss{margin-top:3.5rem;padding-top:1rem;border-top:1px solid var(--linie);
color:var(--matt);font-size:.78rem}
"""


def _luecken_block(d: Dict[str, Any]) -> str:
    """Fehlendes SICHTBAR machen, nicht nur nach stderr melden.

    Externes Review T19-03: Ein Modell mit Luecken erzeugte eine Seite,
    die vollstaendig aussah — der Hinweis stand nur auf der Konsole des
    Erzeugers, nicht im Dokument, das Menschen lesen. Ein Bericht, der
    sein eigenes Fehlen verschweigt, ist schlimmer als ein fehlender
    Bericht.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    offene = luecken(d)
    if not offene:
        return ""
    zeilen = "".join(
        f"<li><b>{_e(l['was'])}</b> — {_e(l['wirkung'])} "
        f"<code>{_e(l['gruppe'])}.{_e(l['feld'])}</code></li>"
        for l in offene)
    return ('<section class="luecken"><h2>Was dieser Bericht NICHT zeigt'
            '</h2><p>Der Fall traegt die folgenden Angaben nicht; die '
            'Darstellung laesst sie offen, statt Vollstaendigkeit zu '
            f'behaupten.</p><ul>{zeilen}</ul></section>')


def baue(d: Dict[str, Any], texte: Dict[str, Any]) -> str:
    titel = texte.get("titel") or d["fall"]["name"]
    z = [f"<title>{_e(titel)}</title><style>{STIL}</style><main>",
         _kopf(d, texte), _luecken_block(d), _fach(d, texte), _it(d, texte)]
    z.append('<p class="fuss">Erzeugt aus den Prüfartefakten des Falls '
             f'<code>{_e(d["fall"]["name"])}</code>. Alle Zahlen sind dort '
             'nachrechenbar; frei geschrieben sind ausschließlich der '
             'einleitende Absatz und die Wirkungszeilen der Befunde. Die '
             'Begründungen der Abnahmen stammen wörtlich aus den '
             'Entscheid-Snapshots des Falls: Schema, Selbstadressierung '
             'und Dateiname sind hier geprüft, die Freigabesignatur '
             'NICHT — dafür fehlt diesem Werkzeug bewusst das '
             'Schlüsselmaterial.</p></main>')
    return "".join(z)


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/fallbericht.py",
        description="Falldarstellung aus dem Datenmodell rendern.")
    p.add_argument("--daten", required=True, help="Ausgabe von falldaten.py")
    p.add_argument("--texte", default=None,
                   help="JSON mit titel, anlass und wirkung je Befund")
    p.add_argument("--out", required=True)
    args = p.parse_args(argv)

    daten = json.loads(Path(args.daten).read_text(encoding="utf-8"))
    texte = {}
    if args.texte:
        texte = json.loads(Path(args.texte).read_text(encoding="utf-8"))

    ziel = Path(args.out)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(baue(daten, texte), encoding="utf-8")
    frei = (1 if texte.get("anlass") else 0) + len(texte.get("wirkung") or {})
    print(f"{ziel}  ({frei} frei geschriebene Textstellen)")
    # Derselbe Vertrag wie falldaten.py (Review T20-03): Der Bericht wird
    # geschrieben — mit sichtbarem Lueckenblock —, aber ein unvollstaendiger
    # Fall endet nicht als normaler Erfolg. Exit 3 = geschrieben, mit
    # Luecken; wer nur den Exit-Code weiterreicht, sieht es.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from falldaten import luecken  # noqa: E402 — Nachbarwerkzeug

    offene = luecken(daten)
    for l in offene:
        print(f"  LUECKE: {l['was']} ({l['gruppe']}.{l['feld']}) — "
              f"{l['wirkung']}", file=sys.stderr)
    return 3 if offene else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
