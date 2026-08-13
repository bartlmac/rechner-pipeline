"""Deterministischer Bestandsbericht: eine selbst-enthaltene HTML-Datei.

Rendert ein Portfolio (Parquet/DataFrame) in einen lesbaren Bericht für ein
Fachpublikum: Bestandsverlauf über Stichtage, Strukturverteilungen, die
Abhängigkeit Alter↔Laufzeit (macht die Copula-Parametrisierung sichtbar) und
eine Kennzahlen-Tabelle. Alle Grafiken sind Inline-SVG — eine Datei, kein
Werkzeug beim Empfänger nötig.

Mit Statushistorie und Ereignis-Ledger (Fortschreibung, optional) zeigt der
Bericht zusätzlich die Ereignis-/Abgangs-Sichten: der Bestandsverlauf wird
abgangsbereinigt (Zeitscheiben auf der Mehrzeilen-Sicht), dazu kommen der
in-force-Bestand nach Status (beitragspflichtig/beitragsfrei), die
Ereignisse je Kalenderjahr, die Betragssummen je Ereignisart und die
Bestandsbewegung in Nachweisungs-Struktur (Stück und Versicherungssumme,
beitragspflichtig/beitragsfrei, mit geprüfter Bestands-Identität).

Determinismus (Golden-Master-fähig): fester ``svg.hashsalt``, Schriften als
Pfade (``svg.fonttype='path'``), ``metadata={'Date': None}`` beim Export,
explizite Sortierungen — gleiche Parquet-Dateien ergeben den byte-identischen
Bericht (bei gepinntem matplotlib).
"""

from __future__ import annotations

import datetime as _dt
import io
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (Backend muss vor pyplot stehen)
import pandas as pd  # noqa: E402

from rechner_pipeline.bestand.auswertung import auswertungs_verlauf  # noqa: E402
from rechner_pipeline.bestand.config import BestandConfig  # noqa: E402
from rechner_pipeline.bestand.ereignisse import bestand_mit_historie  # noqa: E402
from rechner_pipeline.bestand.kennzahlen import (  # noqa: E402
    EREIGNIS_LABELS,
    EREIGNIS_REIHENFOLGE,
    bewegungskonto,
    ereignis_summen,
    ereignisse_je_jahr,
    generationsnamen,
    jahresraster,
    status_verlauf,
    verlauf,
)
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe  # noqa: E402

REPORT_VERSION = "1.3.0"

_RC = {
    "svg.hashsalt": "rechner-pipeline-bestand",
    "svg.fonttype": "path",
    "figure.figsize": (8.0, 3.6),
    "figure.dpi": 100,
    "axes.grid": True,
    "grid.alpha": 0.3,
}

#: Feste Generationen-Farben (deterministisch, unabhängig von der Zeichenreihenfolge).
_FARBEN = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b")

#: Feste Ereignis-Farben (Reihenfolge wie EREIGNIS_REIHENFOLGE).
_EREIGNIS_FARBEN = {
    "ZUG": "#1f77b4",
    "ERH": "#17becf",
    "PEX": "#9467bd",
    "STO": "#ff7f0e",
    "TOD": "#d62728",
    "ABL": "#2ca02c",
}

#: Status-Farben der in-force-Sicht.
_STATUS_FARBEN = {"POL": "#1f77b4", "PEX": "#9467bd"}


def _farbe(index: int) -> str:
    return _FARBEN[index % len(_FARBEN)]


def _svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    text = buf.getvalue()
    return text[text.index("<svg") :]


def _zahl(value: float, dezimal: int = 0) -> str:
    """Deutsche Tausender-Formatierung ohne Locale-Abhängigkeit."""
    s = f"{value:,.{dezimal}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #


def _chart_verlauf_vertraege(reihe: List[Dict[str, Any]], generationen: List[str]) -> str:
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    fig, ax = plt.subplots()
    unten = [0] * len(reihe)
    for gi, gen in enumerate(generationen):
        werte = [r["generationen"].get(gen, 0) for r in reihe]
        ax.bar(x, werte, bottom=unten, label=gen, color=_farbe(gi), width=0.8)
        unten = [u + w for u, w in zip(unten, werte)]
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("aktive Verträge")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    ax.legend(loc="upper right", fontsize=8)
    return _svg(fig)


def _chart_verlauf_summe(reihe: List[Dict[str, Any]]) -> str:
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    werte = [r["summe_vs"] / 1e6 for r in reihe]
    fig, ax = plt.subplots()
    ax.plot(x, werte, marker="o", markersize=3, color=_FARBEN[0])
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("Versicherungssumme (Mio.)")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    return _svg(fig)


def _chart_histogramm(
    scheibe: pd.DataFrame, spalte: str, titel: str, xlabel: str, bins: int, generationen: List[str]
) -> str:
    fig, ax = plt.subplots(figsize=(4.0, 3.0))
    daten = [
        scheibe.loc[scheibe["tarif_generation"] == gen, spalte].to_numpy(float)
        for gen in generationen
    ]
    ax.hist(daten, bins=bins, stacked=True,
            label=generationen, color=[_farbe(i) for i in range(len(generationen))])
    ax.set_title(titel, fontsize=10)
    ax.set_xlabel(xlabel)
    ax.set_ylabel("Verträge")
    ax.legend(fontsize=7)
    return _svg(fig)


def _chart_scatter_alter_laufzeit(df: pd.DataFrame, generationen: List[str]) -> str:
    fig, ax = plt.subplots(figsize=(5.0, 3.6))
    for gi, gen in enumerate(generationen):
        rows = df[df["tarif_generation"] == gen]
        ax.scatter(rows["entry_age"], rows["duration"], s=8, alpha=0.35,
                   color=_farbe(gi), label=gen, edgecolors="none")
    ax.set_xlabel("Eintrittsalter")
    ax.set_ylabel("Laufzeit (Jahre)")
    ax.set_title("Abhängigkeit Eintrittsalter ↔ Laufzeit (Copula)", fontsize=10)
    ax.legend(fontsize=8)
    return _svg(fig)


def _chart_status_verlauf(reihe: List[Dict[str, Any]]) -> str:
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    fig, ax = plt.subplots()
    unten = [0] * len(reihe)
    for status, label in (("POL", "beitragspflichtig (POL)"), ("PEX", "beitragsfrei (PEX)")):
        werte = [r[status] for r in reihe]
        ax.bar(x, werte, bottom=unten, label=label,
               color=_STATUS_FARBEN[status], width=0.8)
        unten = [u + w for u, w in zip(unten, werte)]
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("in-force-Verträge")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    ax.legend(loc="upper right", fontsize=8)
    return _svg(fig)


def _chart_deckungskapital(reihe: List[Dict[str, Any]]) -> str:
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    fig, ax = plt.subplots()
    bpfl = [(r["deckungskapital"] - r["deckungskapital_bfr"]) / 1e6 for r in reihe]
    bfr = [r["deckungskapital_bfr"] / 1e6 for r in reihe]
    ax.bar(x, bpfl, label="beitragspflichtig", color=_STATUS_FARBEN["POL"], width=0.8)
    ax.bar(x, bfr, bottom=bpfl, label="beitragsfrei", color=_STATUS_FARBEN["PEX"], width=0.8)
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("Deckungskapital (Mio.)")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    ax.legend(loc="upper right", fontsize=8)
    return _svg(fig)


def _chart_ereignisse_je_jahr(reihe: List[Dict[str, Any]]) -> str:
    x = list(range(len(reihe)))
    labels = [str(r["jahr"]) for r in reihe]
    fig, ax = plt.subplots()
    unten = [0] * len(reihe)
    for code in EREIGNIS_REIHENFOLGE:
        werte = [r[code] for r in reihe]
        ax.bar(x, werte, bottom=unten, label=f"{EREIGNIS_LABELS[code]} ({code})",
               color=_EREIGNIS_FARBEN[code], width=0.8)
        unten = [u + w for u, w in zip(unten, werte)]
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("Ereignisse")
    ax.set_xlabel("Kalenderjahr")
    ax.legend(loc="upper right", fontsize=8)
    return _svg(fig)


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def render_html(
    df: pd.DataFrame,
    stichtage: Optional[List[_dt.date]] = None,
    titel: str = "Bestandsbericht",
    quelle_hash: Optional[str] = None,
    historie: Optional[pd.DataFrame] = None,
    ledger: Optional[pd.DataFrame] = None,
    config: Optional[BestandConfig] = None,
    scheiben: Optional[pd.DataFrame] = None,
    bis: Optional[_dt.date] = None,
) -> str:
    """Rendert den vollständigen Bericht als selbst-enthaltenes HTML.

    ``historie``/``ledger`` (beide zusammen, aus demselben
    ``fortschreiben``-Lauf) schalten die Ereignis-/Abgangs-Sichten frei;
    der Bestandsverlauf rechnet dann auf der abgangsbereinigten
    Mehrzeilen-Sicht statt auf dem Basisbestand. ``config`` (die
    Bestand-Config mit den Tarifgenerationen) schaltet zusätzlich die
    aktuariellen Kennzahlen frei (Deckungskapital, Rückkaufswert — Werte
    in-process aus dem stabilen Kern); sie muss dieselbe sein, mit der
    Bestand und Fortschreibung erzeugt wurden. ``bis`` (der
    Fortschreibungs-Horizont, dasselbe Datum wie beim ``fortschreiben``-Lauf)
    schaltet die Bestandsbewegung in Nachweisungs-Struktur frei — ohne den
    Horizont ließe sich nicht entscheiden, welche Jahre vollständig
    simuliert sind.
    """
    if (historie is None) != (ledger is None):
        raise ValueError(
            "historie und ledger gehoeren zusammen (ein fortschreiben-Lauf) — "
            "entweder beide angeben oder keines"
        )
    if scheiben is not None and historie is None:
        raise ValueError(
            "scheiben nur zusammen mit historie/ledger (ein fortschreiben-Lauf)"
        )
    if ledger is not None:
        fremd = set(ledger["police_id"]) - set(df["police_id"])
        if fremd:
            raise ValueError(
                f"Ledger referenziert Policen ausserhalb des Bestands: "
                f"{sorted(fremd)[:5]} — bei Neuzugaengen den Gesamtbestand "
                "uebergeben (mit_zugaengen(stamm, zugaenge)), sonst waere der "
                "Bericht in sich widerspruechlich"
            )
    if (
        ledger is not None
        and scheiben is None
        and (ledger["ereignis"] == "ERH").any()
    ):
        raise ValueError(
            "Ledger enthaelt dynamische Erhoehungen (ERH) — ohne scheiben "
            "waeren aktuarielle Kennzahlen und Bewegungs-Summen systematisch "
            "zu niedrig (Betraege enthalten die Scheiben bereits)"
        )
    if stichtage is None:
        stichtage = jahresraster(df)
    generationen = generationsnamen(df)
    # Mit Historie rechnen Verlauf und Zeitscheiben abgangsbereinigt auf der
    # Mehrzeilen-Sicht; Strukturbilder je Vertrag bleiben auf dem Basisbestand.
    bestand = bestand_mit_historie(df, historie) if historie is not None else df
    reihe = verlauf(bestand, stichtage)
    # Strukturbild am Bestands-Hoechststand (erster Maximums-Stichtag —
    # deterministisch und aussagekraeftiger als der duenne Bestandsauslauf).
    hoechststand = max(reihe, key=lambda r: (r["vertraege"], -reihe.index(r)))
    struktur_stichtag = _dt.date.fromisoformat(hoechststand["stichtag"])
    scheibe = zeitscheibe(bestand, struktur_stichtag)

    with plt.rc_context(_RC):
        svg_vertraege = _chart_verlauf_vertraege(reihe, generationen)
        svg_summe = _chart_verlauf_summe(reihe)
        svg_alter = _chart_histogramm(
            scheibe, "age", f"Alter am {struktur_stichtag.isoformat()}", "Alter", 20, generationen
        )
        svg_laufzeit = _chart_histogramm(
            scheibe, "duration", "Laufzeiten", "Jahre", 15, generationen
        )
        svg_summen = _chart_histogramm(
            scheibe, "sum_insured", "Versicherungssummen", "Summe", 20, generationen
        )
        svg_scatter = _chart_scatter_alter_laufzeit(df, generationen)
        svg_status = svg_ereignisse = svg_dk = ""
        if historie is not None and len(ledger) > 0:
            svg_status = _chart_status_verlauf(status_verlauf(bestand, stichtage))
            svg_ereignisse = _chart_ereignisse_je_jahr(ereignisse_je_jahr(ledger))
        reihe_ausw: List[Dict[str, Any]] = []
        if config is not None:
            reihe_ausw = auswertungs_verlauf(
                df, historie, config, stichtage, scheiben=scheiben
            )
            svg_dk = _chart_deckungskapital(reihe_ausw)

    zeilen = []
    for r in reihe:
        gen_mix = ", ".join(f"{g}: {n}" for g, n in r["generationen"].items()) or "—"
        zeilen.append(
            f"<tr><td>{r['stichtag']}</td><td class='num'>{r['vertraege']}</td>"
            f"<td class='num'>{_zahl(r['summe_vs'])}</td>"
            f"<td class='num'>{_zahl(r['mittel_alter'], 1)}</td>"
            f"<td class='num'>{_zahl(r['mittel_restlaufzeit_jahre'], 1)}</td>"
            f"<td>{gen_mix}</td></tr>"
        )
    tabelle = (
        "<table><thead><tr><th>Stichtag</th><th>Verträge</th>"
        "<th>Σ Versicherungssumme</th><th>Ø Alter</th><th>Ø Restlaufzeit (J.)</th>"
        "<th>Generationen</th></tr></thead><tbody>"
        + "".join(zeilen)
        + "</tbody></table>"
    )

    zeitraum = (
        f"{df['insurance_start'].dt.date.min().isoformat()} bis "
        f"{df['insurance_end'].dt.date.max().isoformat()}"
    )
    quelle = (
        f"<li>Quelle (SHA-256, gekürzt): <code>{quelle_hash[:16]}</code></li>"
        if quelle_hash
        else ""
    )

    fortschreibung_zeile = ""
    ereignis_html = ""
    if historie is not None:
        summen = ereignis_summen(ledger)
        if summen:
            letzter = ledger["status_date"].max().date().isoformat()
            fortschreibung_zeile = (
                f"<li>Fortschreibung: {len(ledger)} Ereignisse "
                f"(letztes am {letzter})</li>"
            )
            summen_zeilen = "".join(
                f"<tr><td>{s['label']} ({s['ereignis']})</td>"
                f"<td class='num'>{s['anzahl']}</td>"
                f"<td>{s['betrag_art']}</td>"
                f"<td class='num'>{_zahl(s['summe_betrag'], 2)}</td></tr>"
                for s in summen
            )
            summen_tabelle = (
                "<table><thead><tr><th>Ereignis</th><th>Anzahl</th>"
                "<th>Betrag-Art</th><th>Σ Betrag</th></tr></thead><tbody>"
                + summen_zeilen
                + "</tbody></table>"
            )
            ereignis_html = f"""
<h2>Fortschreibung und Abgänge</h2>
<div class="charts">{svg_status}{svg_ereignisse}</div>
{summen_tabelle}
<p>Der Bestandsverlauf oben ist abgangsbereinigt: stornierte, gestorbene und
abgelaufene Verträge verlassen den Bestand am Buchungstag. Neuzugänge (ZUG)
treten mit ihrem Versicherungsbeginn ein; ihr Betrag in der Tabelle ist die
Versicherungssumme des Zugangs (Bestandsvolumen, kein Zahlungsstrom).
Beitragsfreie
Verträge (PEX) bleiben in-force und gehen mit ihrer ursprünglichen
Versicherungssumme in den Verlauf ein; die bei Beitragsfreistellung
fixierten beitragsfreien Summen (VS_bfr) zeigt die Tabelle. Die Spalte
"Σ Versicherungssumme" im Bestandsverlauf führt die Grundscheiben-Summen;
die durch dynamische Erhöhungen hinzugekommenen Summen zeigt die
ERH-Zeile der Tabelle, die aktuariellen Kennzahlen enthalten die Scheiben
vollständig. Alle Beträge stammen aus dem stabilen Rechenkern.</p>"""
        else:
            fortschreibung_zeile = "<li>Fortschreibung: keine Ereignisse im Horizont</li>"
            ereignis_html = (
                "\n<h2>Fortschreibung und Abgänge</h2>"
                "<p>Keine Ereignisse im Berichtszeitraum.</p>"
            )

    bewegung_html = ""
    if historie is not None and bis is not None and len(ledger) > 0:
        konto = bewegungskonto(df, historie, ledger, scheiben, bis=bis)
        relevant = [
            z for z in konto
            if z["bpfl"]["anfang"]["stueck"] or z["bpfl"]["ende"]["stueck"]
            or z["bpfl"]["zugang_neuzugang"]["stueck"]
            or z["bfr"]["anfang"]["stueck"] or z["bfr"]["ende"]["stueck"]
        ]
        alle_ok = all(
            ok for z in konto for oks in z["identitaet"].values() for ok in oks.values()
        )

        def _bewegungstabelle(mass: str, dezimal: int) -> str:
            zeilen_html = []
            for z in relevant:
                b, f = z["bpfl"], z["bfr"]
                werte = [
                    b["anfang"][mass], b["zugang_neuzugang"][mass],
                    b["zugang_erhoehung"][mass], b["abgang_storno"][mass],
                    b["abgang_tod"][mass], b["abgang_ablauf"][mass],
                    b["umbuchung_beitragsfrei"][mass], b["ende"][mass],
                    f["anfang"][mass], f["zugang_umbuchung"][mass],
                    f["abgang_tod"][mass], f["abgang_ablauf"][mass], f["ende"][mass],
                ]
                zellen = "".join(
                    f"<td class='num'>{_zahl(w, dezimal) if mass == 'summe' else int(w)}</td>"
                    for w in werte
                )
                zeilen_html.append(f"<tr><td>{z['jahr']}</td>{zellen}</tr>")
            kopf = (
                "<tr><th rowspan='2'>Jahr</th>"
                "<th colspan='8'>beitragspflichtig</th>"
                "<th colspan='5'>beitragsfrei</th></tr>"
                "<tr><th>Anfang</th><th>+Zugang</th><th>+Erh.</th><th>−Storno</th>"
                "<th>−Tod</th><th>−Ablauf</th><th>−&rarr;bfr</th><th>Ende</th>"
                "<th>Anfang</th><th>+&larr;bpfl</th><th>−Tod</th><th>−Ablauf</th>"
                "<th>Ende</th></tr>"
            )
            return f"<table><thead>{kopf}</thead><tbody>{''.join(zeilen_html)}</tbody></table>"

        pruefsatz = (
            "Die Identität Anfangsbestand + Zugang − Abgang = Endbestand gilt "
            "in jedem Jahr, je Track, in Stück und Summe (Gate-geprüft)."
            if alle_ok else
            "WARNUNG: Bewegungs-Identität verletzt — Daten inkonsistent "
            "(Gate B1 schlägt fehl)."
        )
        bewegung_html = f"""
<h2>Bestandsbewegung (Nachweisungs-Struktur)</h2>
<h3>Stück</h3>
{_bewegungstabelle("stueck", 0)}
<h3>Versicherungssumme</h3>
{_bewegungstabelle("summe", 0)}
<p>Struktur nach der BaFin-Nachweisung zur Bestandsbewegung: Zugang aus
Versicherungsbeginnen (die POL-Basiszeile ist der Zugangs-GeVo) und
dynamischen Erhöhungen (nur Summe); Abgang mit den abgehenden
Versicherungssummen (inklusive Erhöhungsscheiben), nicht den
Auszahlungsbeträgen; Beitragsfreistellung als Umbuchung (Abgang
beitragspflichtig mit der Gesamt-VS, Zugang beitragsfrei mit der
beitragsfreien Summe). Ausgewiesen sind nur Jahre, die der
Fortschreibungs-Horizont vollständig abdeckt. {pruefsatz}</p>"""

    auswertung_html = ""
    if config is not None:
        ausw_zeilen = "".join(
            f"<tr><td>{r['stichtag']}</td><td class='num'>{r['vertraege']}</td>"
            f"<td class='num'>{_zahl(r['deckungskapital'])}</td>"
            f"<td class='num'>{_zahl(r['deckungskapital_bfr'])}</td>"
            f"<td class='num'>{_zahl(r['rueckkaufswert'])}</td>"
            f"<td class='num'>{_zahl(r['vs_bfr'])}</td></tr>"
            for r in reihe_ausw
            if r["vertraege"] > 0
        )
        ausw_tabelle = (
            "<table><thead><tr><th>Stichtag</th><th>Verträge</th>"
            "<th>Σ Deckungskapital</th><th>davon beitragsfrei</th>"
            "<th>Σ Rückkaufswert (bpfl.)</th><th>Σ VS_bfr (fixiert)</th>"
            "</tr></thead><tbody>" + ausw_zeilen + "</tbody></table>"
        )
        auswertung_html = f"""
<h2>Aktuarielle Kennzahlen je Stichtag</h2>
<div class="charts">{svg_dk}</div>
{ausw_tabelle}
<p>Alle Werte kommen in-process aus dem stabilen Rechenkern.
Deckungskapital: beitragspflichtig die Deckungsrückstellung kDRx_bpfl,
nach Beitragsfreistellung die beitragsfreie Reserve (VS_bfr mal kVx_bfr).
Rückkaufswert nur auf dem beitragspflichtigen Track (das Quell-Blatt
definiert keine Rückkaufsregel für beitragsfreie Verträge).</p>"""

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{titel}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 60rem; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }}
h1, h2 {{ border-bottom: 1px solid #ddd; padding-bottom: .3rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: .85rem; }}
th, td {{ border: 1px solid #ddd; padding: .3rem .5rem; text-align: left; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
thead {{ background: #f5f5f5; }}
.charts {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
.charts svg {{ max-width: 100%; height: auto; }}
footer {{ margin-top: 2rem; font-size: .8rem; color: #666; }}
</style>
</head>
<body>
<h1>{titel}</h1>
<ul>
<li>Verträge gesamt: {len(df)}</li>
<li>Tarifgenerationen: {", ".join(generationen)}</li>
<li>Vertragszeitraum: {zeitraum}</li>
<li>Stichtage: {len(stichtage)} ({stichtage[0].isoformat()} bis {stichtage[-1].isoformat()})</li>
{fortschreibung_zeile}
{quelle}
</ul>

<h2>Bestandsverlauf</h2>
<div class="charts">{svg_vertraege}{svg_summe}</div>
{ereignis_html}
{bewegung_html}
{auswertung_html}

<h2>Bestandsstruktur am {struktur_stichtag.isoformat()} (Höchststand: {hoechststand["vertraege"]} Verträge)</h2>
<div class="charts">{svg_alter}{svg_laufzeit}{svg_summen}</div>

<h2>Merkmals-Abhängigkeit</h2>
<div class="charts">{svg_scatter}</div>
<p>Das Streudiagramm zeigt die konfigurierte Rangkorrelation zwischen
Eintrittsalter und Laufzeit (Gauß-Copula): ältere Eintrittsalter gehen mit
kürzeren Laufzeiten einher.</p>

<h2>Kennzahlen je Stichtag</h2>
{tabelle}

<footer>
Erzeugt mit <code>python -m rechner_pipeline.toolbox.bestand_report</code>
(Version {REPORT_VERSION}). Das Rendering ist deterministisch: dieselbe
Parquet-Datei ergibt den byte-identischen Bericht.
</footer>
</body>
</html>
"""
