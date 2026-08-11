"""Deterministischer Bestandsbericht: eine selbst-enthaltene HTML-Datei.

Rendert ein Portfolio (Parquet/DataFrame) in einen lesbaren Bericht für ein
Fachpublikum: Bestandsverlauf über Stichtage, Strukturverteilungen, die
Abhängigkeit Alter↔Laufzeit (macht die Copula-Parametrisierung sichtbar) und
eine Kennzahlen-Tabelle. Alle Grafiken sind Inline-SVG — eine Datei, kein
Werkzeug beim Empfänger nötig.

Determinismus (Golden-Master-fähig): fester ``svg.hashsalt``, Schriften als
Pfade (``svg.fonttype='path'``), ``metadata={'Date': None}`` beim Export,
explizite Sortierungen — gleiche Parquet-Datei ergibt den byte-identischen
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

from rechner_pipeline.bestand.kennzahlen import (  # noqa: E402
    generationsnamen,
    jahresraster,
    verlauf,
)
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe  # noqa: E402

REPORT_VERSION = "1.0.0"

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


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def render_html(
    df: pd.DataFrame,
    stichtage: Optional[List[_dt.date]] = None,
    titel: str = "Bestandsbericht",
    quelle_hash: Optional[str] = None,
) -> str:
    """Rendert den vollständigen Bericht als selbst-enthaltenes HTML."""
    if stichtage is None:
        stichtage = jahresraster(df)
    generationen = generationsnamen(df)
    reihe = verlauf(df, stichtage)
    # Strukturbild am Bestands-Hoechststand (erster Maximums-Stichtag —
    # deterministisch und aussagekraeftiger als der duenne Bestandsauslauf).
    hoechststand = max(reihe, key=lambda r: (r["vertraege"], -reihe.index(r)))
    struktur_stichtag = _dt.date.fromisoformat(hoechststand["stichtag"])
    scheibe = zeitscheibe(df, struktur_stichtag)

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
{quelle}
</ul>

<h2>Bestandsverlauf</h2>
<div class="charts">{svg_vertraege}{svg_summe}</div>

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
