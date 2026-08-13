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
explizite Sortierungen, inhaltsbasierte Clip-Pfad-Ids (matplotlib leitet
sie sonst aus Objektadressen ab) — gleiche Parquet-Dateien ergeben den
byte-identischen Bericht (bei gepinntem matplotlib).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import io
import re
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
    bu_bewegungskonto,
    ereignis_summen,
    ereignisse_je_jahr,
    generationsnamen,
    jahresraster,
    status_verlauf,
    verlauf,
)
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe  # noqa: E402

REPORT_VERSION = "1.5.0"

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
    "INV": "#8c564b",
    "REA": "#bcbd22",
    "STO": "#ff7f0e",
    "TOD": "#d62728",
    "ABL": "#2ca02c",
}

#: Status-Farben der in-force-Sicht (BU = Leistungsbezug).
_STATUS_FARBEN = {"POL": "#1f77b4", "PEX": "#9467bd", "BU": "#d62728"}

#: Beschriftung der in-force-Status in fester Reihenfolge.
_STATUS_LABELS = (
    ("POL", "beitragspflichtig (POL)"),
    ("PEX", "beitragsfrei (PEX)"),
    ("BU", "im Leistungsbezug (BU)"),
)


def _farbe(index: int) -> str:
    return _FARBEN[index % len(_FARBEN)]


#: matplotlib-Ids in SVG-Defs: Clip-Pfade (``pXXXXXXXXXX``) und
#: Marker-/Glyph-Pfade (``mXXXXXXXXXX``).
_ID_MUSTER = re.compile(r"\b([mp])[0-9a-f]{10}\b")


def _stabile_ids(svg: str) -> str:
    """Clip-Pfad-Ids deterministisch machen.

    matplotlib bildet die Ids von Clip-Pfaden und Markern teils ueber
    ``id(obj)``, also die Speicheradresse des Objekts — dieselbe Grafik
    bekommt dann bei jedem Rendern andere Ids, und der Bericht waere nicht
    byte-identisch reproduzierbar (Golden-Master-Anspruch des Moduls). Ohne
    diese Normalisierung faellt das nur nicht auf, solange eine Grafik
    zufaellig ohne solche Defs auskommt. Wir ersetzen sie
    durch Ids aus dem Inhalt: ein Praefix aus dem Hash der id-freien Grafik
    plus laufende Nummer in Auftretensreihenfolge.
    """
    roh = _ID_MUSTER.sub("__id__", svg)
    stamm = hashlib.sha256(roh.encode("utf-8")).hexdigest()[:6]
    ersetzt: Dict[str, str] = {}

    def _ersetze(treffer) -> str:
        alt = treffer.group(0)
        if alt not in ersetzt:
            ersetzt[alt] = f"{treffer.group(1)}{stamm}{len(ersetzt):04d}"
        return ersetzt[alt]

    return _ID_MUSTER.sub(_ersetze, svg)


def _svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", metadata={"Date": None}, bbox_inches="tight")
    plt.close(fig)
    text = buf.getvalue()
    return _stabile_ids(text[text.index("<svg") :])


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
    for status, label in _STATUS_LABELS:
        werte = [r.get(status, 0) for r in reihe]
        if not any(werte):
            continue   # Status kommt im Bestand nicht vor
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


#: Zustands-Farben der BU-Sichten.
_BU_FARBEN = {"anwaerter": "#1f77b4", "rentner": "#d62728"}


def _chart_bu_zustand(
    konto: List[Dict[str, Any]], track: str, ylabel: str
) -> str:
    """Bestand EINES BU-Zustands je Jahresende.

    Bewusst getrennte Grafiken je Zustand: Anwärter und Leistungsbezieher
    unterscheiden sich um Größenordnungen, in einer gemeinsamen Skala wäre
    der Leistungsbestand nicht mehr ablesbar.
    """
    x = list(range(len(konto)))
    labels = [str(z["jahr"]) for z in konto]
    fig, ax = plt.subplots(figsize=(8.0, 2.6))
    ax.bar(x, [z[track]["ende"]["stueck"] for z in konto],
           color=_BU_FARBEN[track], width=0.8)
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Kalenderjahr")
    return _svg(fig)


def _chart_bu_summe(
    reihe: List[Dict[str, Any]], schluessel: str, ylabel: str, farbe: str
) -> str:
    """Eine aggregierte BU-Größe je Stichtag (Summen sind vergleichbar)."""
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    fig, ax = plt.subplots(figsize=(8.0, 2.6))
    ax.plot(x, [r[schluessel] / 1e6 for r in reihe], marker="o",
            markersize=3, color=farbe)
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    return _svg(fig)


def _chart_ereignisse_je_jahr(reihe: List[Dict[str, Any]]) -> str:
    x = list(range(len(reihe)))
    labels = [str(r["jahr"]) for r in reihe]
    fig, ax = plt.subplots()
    unten = [0] * len(reihe)
    for code in EREIGNIS_REIHENFOLGE:
        werte = [r.get(code, 0) for r in reihe]
        if not any(werte):
            continue   # GeVo-Art kommt im Bestand nicht vor
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

    # ------------------------------------------------------------------ #
    # Berufsunfaehigkeit: eigene Nachweisung (Bezugsgroesse Jahresrente)
    # ------------------------------------------------------------------ #
    bu_html = ""
    ist_bu = "produkt" in df.columns and (df["produkt"] == "bu").any()
    if ist_bu and historie is not None and bis is not None:
        bu_konto = bu_bewegungskonto(df, historie, ledger, bis=bis)
        bu_relevant = [
            z for z in bu_konto
            if z["anwaerter"]["anfang"]["stueck"] or z["anwaerter"]["ende"]["stueck"]
            or z["rentner"]["anfang"]["stueck"] or z["rentner"]["ende"]["stueck"]
        ]
        bu_ok = all(
            ok for z in bu_konto for oks in z["identitaet"].values() for ok in oks.values()
        )

        #: Je Zustand eine eigene Tabelle mit genau seinen Positionen —
        #: eine gemeinsame Tabelle beider Zustände hätte 13 Spalten und
        #: wäre nicht mehr lesbar.
        BU_POSITIONEN = {
            "anwaerter": (
                ("anfang", "Anfang"),
                ("zugang_neuzugang", "+ Zugang"),
                ("zugang_reaktivierung", "+ Reaktivierung"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("umbuchung_leistungsbezug", "− in Leistungsbezug"),
                ("ende", "Ende"),
            ),
            "rentner": (
                ("anfang", "Anfang"),
                ("zugang_invalidisierung", "+ Invalidisierung"),
                ("abgang_reaktivierung", "− Reaktivierung"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("ende", "Ende"),
            ),
        }

        def _bu_tabelle(track: str, mass: str) -> str:
            positionen = BU_POSITIONEN[track]
            kopf = "<tr><th>Jahr</th>" + "".join(
                f"<th>{titel}</th>" for _, titel in positionen
            ) + "</tr>"
            zeilen = []
            for z in bu_relevant:
                zellen = "".join(
                    f"<td class='num'>"
                    f"{_zahl(z[track][pos][mass]) if mass == 'summe' else int(z[track][pos][mass])}"
                    "</td>"
                    for pos, _ in positionen
                )
                zeilen.append(f"<tr><td>{z['jahr']}</td>{zellen}</tr>")
            return f"<table><thead>{kopf}</thead><tbody>{''.join(zeilen)}</tbody></table>"
        bu_kennzahlen = ""
        if config is not None:
            aktiv = [r for r in reihe_ausw if r["bu_vertraege"] > 0]
            bu_zeilen = "".join(
                f"<tr><td>{r['stichtag']}</td><td class='num'>{r['bu_vertraege']}</td>"
                f"<td class='num'>{r['bu_leistungsbezug']}</td>"
                f"<td class='num'>{_zahl(r['bu_jahresrente'])}</td>"
                f"<td class='num'>{_zahl(r['bu_jahresrente_laufend'])}</td>"
                f"<td class='num'>{_zahl(r['deckungskapital'])}</td>"
                f"<td class='num'>{_zahl(r['deckungskapital_bu'])}</td></tr>"
                for r in aktiv
            )
            # Aggregierte Groessen bleiben in einer Grafik (Summen sind
            # vergleichbar); je Zustand getrennt nur dort, wo die
            # Groessenordnungen auseinanderfallen.
            bu_kennzahlen = f"""
<h3>Aktuarielle Kennzahlen je Stichtag</h3>
<div class="charts">{_chart_bu_summe(aktiv, "bu_jahresrente",
    "versicherte Jahresrente (Mio.)", _BU_FARBEN["anwaerter"])}</div>
<div class="charts">{_chart_bu_summe(aktiv, "bu_jahresrente_laufend",
    "laufende Jahresrente (Mio.)", _BU_FARBEN["rentner"])}</div>
<div class="charts">{_chart_bu_summe(aktiv, "deckungskapital",
    "Deckungskapital gesamt (Mio.)", "#2ca02c")}</div>
<div class="charts">{_chart_bu_summe(aktiv, "deckungskapital_anwaerter",
    "Deckungskapital Anwärter (Mio.)", _BU_FARBEN["anwaerter"])}</div>
<div class="charts">{_chart_bu_summe(aktiv, "deckungskapital_bu",
    "Deckungskapital Leistungsbezug (Mio.)", _BU_FARBEN["rentner"])}</div>
<table><thead><tr><th>Stichtag</th><th>BU-Verträge</th>
<th>davon im Leistungsbezug</th><th>Σ versicherte Jahresrente</th>
<th>Σ laufende Jahresrente</th><th>Σ Deckungskapital</th>
<th>davon Leistungsbezug</th></tr></thead><tbody>{bu_zeilen}</tbody></table>"""
        bu_generationen = [
            g for g in (config.generationen if config is not None else ())
            if g.produkt == "bu"
        ]
        if bu_generationen:
            g = bu_generationen[0]
            bu_grundlagen = (
                f"Invalidisierung {g.tafel_i}, Aktivensterblichkeit "
                f"{g.tafel_aktiv}, Reaktivierung {g.tafel_ri}, "
                f"Invalidensterblichkeit {g.tafel_ti}; Rechnungszins "
                f"{g.zins:.2%}".replace(".", ",")
            )
        else:
            bu_grundlagen = "siehe Tarifgeneration des Bestands"
        def _annahme_text(name: str, titel: str) -> str:
            annahme = getattr(config.annahmen, name) if config is not None else None
            if annahme is None or (annahme.a == 0.0 and annahme.b == 1.0):
                return f"{titel} unverändert"
            if annahme.b == 0.0:
                return f"{titel} {annahme.a:.1%}".replace(".", ",")
            return f"{titel} × {annahme.b:.2f}".replace(".", ",")

        bu_annahmen = ", ".join(
            _annahme_text(n, titel) for n, titel in (
                ("invalidisierung", "Invalidisierung"),
                ("reaktivierung", "Reaktivierung"),
                ("aktivensterblichkeit", "Aktivensterblichkeit"),
                ("invalidensterblichkeit", "Invalidensterblichkeit"),
            )
        )
        bu_pruefsatz = (
            "Die Identität Anfangsbestand + Zugang − Abgang = Endbestand gilt "
            "in jedem Jahr, je Track, in Stück und Jahresrente (Gate-geprüft)."
            if bu_ok else
            "WARNUNG: Bewegungs-Identität verletzt — Daten inkonsistent."
        )
        bu_html = f"""
<h2>Berufsunfähigkeit: Bestand und Bewegung</h2>
<p>Die BU-Nachweisung wird getrennt von der Kapitalversicherung geführt:
Bezugsgröße ist die versicherte <em>Jahresrente</em>, nicht die
Versicherungssumme — beide sind nicht addierbar. Getrennt werden
<em>Anwärter</em> (Zustand POL) und <em>Leistungsbezieher</em> (Zustand BU);
die Invalidisierung ist eine Umbuchung zwischen beiden Tracks, die
Reaktivierung die Rückbuchung. Bestandszahlen und Bewegung werden je
Zustand ausgewiesen — die beiden Bestände unterscheiden sich um
Größenordnungen, eine gemeinsame Darstellung wäre nicht ablesbar.
{bu_pruefsatz}</p>

<h3>Anwärter</h3>
<div class="charts">{_chart_bu_zustand(bu_relevant, "anwaerter", "Anwärter (Jahresende)") if bu_relevant else ""}</div>
<p>Bewegung in Stück:</p>
{_bu_tabelle("anwaerter", "stueck")}
<p>Bewegung in versicherter Jahresrente:</p>
{_bu_tabelle("anwaerter", "summe")}

<h3>Leistungsbezieher</h3>
<div class="charts">{_chart_bu_zustand(bu_relevant, "rentner", "Leistungsbezieher (Jahresende)") if bu_relevant else ""}</div>
<p>Bewegung in Stück:</p>
{_bu_tabelle("rentner", "stueck")}
<p>Bewegung in laufender Jahresrente:</p>
{_bu_tabelle("rentner", "summe")}
{bu_kennzahlen}
<p>Die Übergänge der Fortschreibung leiten sich aus denselben vier
Ausscheideordnungen ab wie die Bewertung, werden aber über die
<em>Erfahrungsannahmen</em> geführt: {bu_annahmen}. Die Bewertung selbst
bleibt unverändert auf den Rechnungsgrundlagen — im Anwärterstand die
Aktivenreserve, im Leistungsbezug die Invalidenreserve mit der Dauer seit
Rentenbeginn.</p>
<p><strong>Rechnungsgrundlagen:</strong> {bu_grundlagen}.</p>"""

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
table {{ border-collapse: collapse; width: 100%; font-size: .78rem; table-layout: auto; }}
/* Breite Nachweisungs-Tabellen bleiben lesbar: eigener Scroll-Bereich */
.breit {{ overflow-x: auto; }}
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
{bu_html}
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
