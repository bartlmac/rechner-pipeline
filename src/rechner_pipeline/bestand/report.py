"""Deterministischer Bestandsbericht: eine selbst-enthaltene HTML-Datei.

Rendert ein Portfolio (Parquet/DataFrame) in einen lesbaren Bericht für ein
Fachpublikum: Bestandsverlauf über Stichtage, Strukturverteilungen, die
Abhängigkeit Alter↔Laufzeit (macht die Copula-Parametrisierung sichtbar) und
eine Kennzahlen-Tabelle. Alle Grafiken sind Inline-SVG — eine Datei, kein
Werkzeug beim Empfänger nötig.

Mit Statushistorie und Ereignis-Ledger (Fortschreibung, optional) zeigt der
Bericht zusätzlich die Ereignis-/Abgangs-Sichten: der Bestandsverlauf wird
abgangsbereinigt (Zeitscheiben auf der Mehrzeilen-Sicht), dazu kommen der
in-force-Bestand nach Status, die Ereignisse je Kalenderjahr und die
Betragssummen je Ereignisart.

Die **Bestandsbewegung** wird für beide Produkte nach EINEM Muster
ausgewiesen (:data:`NACHWEISUNGEN`): je Nachweisung zwei Träger-Bestände
mit einer Umbuchung dazwischen, je Träger eine Grafik und zwei
Bewegungstabellen (Stück und Bezugsgröße). Es unterscheiden sich nur die
Bezeichnungen und die Bezugsgröße — Versicherungssumme bei der
Kapitalversicherung, versicherte Jahresrente bei der Berufsunfähigkeit
(nicht addierbar, deshalb getrennte Nachweisungen). Mit ``stichtag`` wird
jede Reihe in **Historie** (Bestandsaufbau bis zum Stichtag) und
**Prognose** (Entwicklung danach) geteilt.

Determinismus (Golden-Master-fähig): fester ``svg.hashsalt``, Schriften als
Pfade (``svg.fonttype='path'``), ``metadata={'Date': None}`` beim Export,
explizite Sortierungen, inhaltsbasierte Clip-Pfad-Ids (matplotlib leitet
sie sonst aus Objektadressen ab) — gleiche Parquet-Dateien ergeben den
byte-identischen Bericht (bei gepinntem matplotlib).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import html as _html
import io
import re
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (Backend muss vor pyplot stehen)
import pandas as pd  # noqa: E402

from rechner_pipeline.bestand.auswertung import auswertungs_verlauf  # noqa: E402
from rechner_pipeline.bestand.berichtstexte import (  # noqa: E402
    STRUKTUR_MERKMALE,
    TEXTE,
    kopfzeilen,
    produkt_gruppen,
    teilbestand,
)
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
    ledger_mit_bestandszugang,
    status_verlauf,
    verlauf,
)
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe  # noqa: E402

REPORT_VERSION = "2.0.0"

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


def _leistungssicht(df: pd.DataFrame) -> Tuple[str, str]:
    """Produktfuehrende Leistungsspalte des Bestands und ihre Bezeichnung.

    Ein reiner BU-Bestand fuehrt seine Leistung in ``bu_rente``;
    ``sum_insured`` ist dort strukturell 0 und wuerde als Verlauf,
    Histogramm und Kennzahlen-Spalte drei leere Sichten ergeben. Bei
    gemischten Bestaenden bleibt es bei der Versicherungssumme (die
    Groessen sind nicht addierbar) — der Titel sagt dann, worauf sie sich
    bezieht.
    """
    if "produkt" not in df.columns:
        return "sum_insured", "Versicherungssumme"
    produkte = set(df["produkt"])
    if produkte == {"bu"}:
        return "bu_rente", "versicherte Jahresrente"
    if "bu" in produkte:
        return "sum_insured", "Versicherungssumme (Kapitalversicherung)"
    return "sum_insured", "Versicherungssumme"


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


def _prozent(value: float, dezimal: int = 2) -> str:
    """Prozentwert mit deutschem Dezimalkomma."""
    return f"{value * 100:.{dezimal}f}".replace(".", ",") + " %"


def _dezimal(value: float, dezimal: int = 2) -> str:
    """Dezimalzahl mit deutschem Komma (Faktoren, Quoten)."""
    return f"{value:.{dezimal}f}".replace(".", ",")


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


def _chart_verlauf_summe(
    reihe: List[Dict[str, Any]], label: str, titel: str = ""
) -> str:
    """Verlauf des versicherten Volumens EINER Versicherungsart.

    Je Art getrennt, weil die Bezugsgroessen nicht dieselben sind
    (Versicherungssumme gegen Jahresrente) — eine gemeinsame Kurve waere
    entweder eine Summe nicht addierbarer Groessen oder, schlimmer, eine
    Kurve nur der einen Art unter dem Titel des Gesamtbestands.
    """
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    werte = [r["summe_vs"] / 1e6 for r in reihe]
    fig, ax = plt.subplots(figsize=(5.0, 3.4))
    ax.plot(x, werte, marker="o", markersize=3, color=_FARBEN[0])
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel(f"{label} (Mio.)")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    if titel:
        ax.set_title(titel, fontsize=10)
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



def _chart_beitraege(reihe: List[Dict[str, Any]], mit_bu: bool) -> str:
    """Beitragsvolumen je Stichtag, gestapelt nach Versicherungsart.

    Anders als das versicherte Volumen sind Beitraege ueber die Arten
    addierbar — beides sind Zahlungen in Euro je Jahr. Deshalb hier eine
    gemeinsame Darstellung mit sichtbarem Anteil je Art.
    """
    x = list(range(len(reihe)))
    labels = [r["stichtag"][:4] for r in reihe]
    fig, ax = plt.subplots()
    klv = [r["bzb_jahr"] / 1e6 for r in reihe]
    ax.bar(x, klv, label="Kapitalversicherung", color=_FARBEN[0], width=0.8)
    if mit_bu:
        bu = [r["bu_beitrag"] / 1e6 for r in reihe]
        ax.bar(x, bu, bottom=klv, label="Berufsunfähigkeit",
               color=_FARBEN[1], width=0.8)
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel("Beitragsvolumen p. a. (Mio.)")
    ax.set_xlabel("Stichtag (1.1. des Jahres)")
    ax.legend(loc="upper right", fontsize=8)
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


# --------------------------------------------------------------------------- #
# Nachweisungen (Bestandsbewegung) — produktübergreifend gleich aufgebaut
# --------------------------------------------------------------------------- #

#: Eine Nachweisung je Produkt. Beide Bewegungskonten haben dieselbe Form:
#: zwei Träger-Bestände, zwischen denen eine Umbuchung läuft, je Position
#: Stück und eine Bezugsgröße. Nur Bezeichnungen und Bezugsgröße
#: unterscheiden sich — Versicherungssumme bei der Kapitalversicherung,
#: versicherte Jahresrente bei der Berufsunfähigkeit (nicht addierbar,
#: deshalb getrennte Nachweisungen).
NACHWEISUNGEN: Tuple[Dict[str, Any], ...] = (
    {
        "produkt": "klv",
        "titel": "Kapitalversicherung",
        "bezug": "Versicherungssumme",
        "erlaeuterung": (
            "Zugang aus den Versicherungsbeginnen (die POL-Basiszeile ist der "
            "Zugangs-Geschäftsvorfall) und aus dynamischen Erhöhungen (nur "
            "Summe, kein Stück); Abgänge mit den abgehenden "
            "Versicherungssummen einschließlich Erhöhungsscheiben, nicht mit "
            "den Auszahlungsbeträgen. Die Beitragsfreistellung ist eine "
            "Umbuchung: der beitragspflichtige Bestand verliert die "
            "Gesamt-Versicherungssumme, der beitragsfreie gewinnt die "
            "beitragsfreie Summe."
        ),
        "tracks": (
            ("bpfl", "Beitragspflichtiger Bestand", (
                ("anfang", "Anfang"),
                ("zugang_neuzugang", "+ Zugang"),
                ("zugang_erhoehung", "+ Erhöhung"),
                ("abgang_storno", "− Storno"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("umbuchung_beitragsfrei", "− beitragsfrei gestellt"),
                ("ende", "Ende"),
            )),
            ("bfr", "Beitragsfreier Bestand", (
                ("anfang", "Anfang"),
                ("zugang_umbuchung", "+ beitragsfrei gestellt"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("ende", "Ende"),
            )),
        ),
        "annahmen": (
            ("tod", "Sterblichkeit"),
            ("storno", "Storno"),
            ("beitragsfreistellung", "Beitragsfreistellung"),
            ("erhoehung", "dynamische Erhöhung"),
        ),
        "grundlagen": lambda g: f"{g.tafel}, Rechnungszins {_prozent(g.zins)}",
        "vorhanden": lambda df: "produkt" not in df.columns
        or (df["produkt"] == "klv").any(),
        "konto": lambda df, h, l, s, bis: bewegungskonto(df, h, l, s, bis=bis),
        "farben": {"bpfl": "#1f77b4", "bfr": "#9467bd"},
    },
    {
        "produkt": "bu",
        "titel": "Berufsunfähigkeit",
        "bezug": "versicherte Jahresrente",
        "erlaeuterung": (
            "Getrennt werden Anwärter (beitragszahlend, ohne Leistungsbezug) "
            "und Leistungsbezieher. Die Invalidisierung ist eine Umbuchung "
            "zwischen beiden Beständen, die Reaktivierung die Rückbuchung; "
            "Tod und Ablauf gehen aus dem Bestand ab, in dem der Vertrag "
            "zuletzt stand. Beide Bestände werden einzeln ausgewiesen — sie "
            "unterscheiden sich um Größenordnungen."
        ),
        "tracks": (
            ("anwaerter", "Anwärter", (
                ("anfang", "Anfang"),
                ("zugang_neuzugang", "+ Zugang"),
                ("zugang_reaktivierung", "+ Reaktivierung"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("umbuchung_leistungsbezug", "− in Leistungsbezug"),
                ("ende", "Ende"),
            )),
            ("rentner", "Leistungsbezieher", (
                ("anfang", "Anfang"),
                ("zugang_invalidisierung", "+ Invalidisierung"),
                ("abgang_reaktivierung", "− Reaktivierung"),
                ("abgang_tod", "− Tod"),
                ("abgang_ablauf", "− Ablauf"),
                ("ende", "Ende"),
            )),
        ),
        "annahmen": (
            ("invalidisierung", "Invalidisierung"),
            ("reaktivierung", "Reaktivierung"),
            ("aktivensterblichkeit", "Aktivensterblichkeit"),
            ("invalidensterblichkeit", "Invalidensterblichkeit"),
        ),
        "grundlagen": lambda g: (
            f"{g.tafel_i} (Invalidisierung), {g.tafel_aktiv} "
            f"(Aktivensterblichkeit), {g.tafel_ri} (Reaktivierung), "
            f"{g.tafel_ti} (Invalidensterblichkeit), Rechnungszins "
            f"{_prozent(g.zins)}"
        ),
        "vorhanden": lambda df: "produkt" in df.columns
        and (df["produkt"] == "bu").any(),
        "konto": lambda df, h, l, s, bis: bu_bewegungskonto(df, h, l, bis=bis),
        "farben": {"anwaerter": "#1f77b4", "rentner": "#d62728"},
    },
)


def _chart_track(
    konto: List[Dict[str, Any]], track: str, ylabel: str, farbe: str,
    stichtag: Optional[_dt.date],
) -> str:
    """Bestand EINES Trägers je Jahresende, mit Stichtags-Trennung.

    Je Träger eine eigene Grafik: die Bestände unterscheiden sich um
    Größenordnungen, in gemeinsamer Skala wäre der kleinere nicht mehr
    ablesbar.
    """
    x = list(range(len(konto)))
    labels = [str(z["jahr"]) for z in konto]
    fig, ax = plt.subplots(figsize=(8.0, 2.6))
    ax.bar(x, [z[track]["ende"]["stueck"] for z in konto], color=farbe, width=0.8)
    if stichtag is not None:
        grenze = _stichtags_position(konto, stichtag)
        if grenze is not None:
            ax.axvline(grenze, color="#333333", linewidth=1.0, linestyle="--")
    schritt = max(1, len(x) // 12)
    ax.set_xticks(x[::schritt], labels[::schritt])
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Kalenderjahr")
    return _svg(fig)


def _stichtags_position(
    konto: List[Dict[str, Any]], stichtag: _dt.date
) -> Optional[float]:
    """x-Position der Stichtagslinie zwischen den Jahresbalken."""
    jahre = [z["jahr"] for z in konto]
    if not jahre:
        return None
    if stichtag.year <= jahre[0]:
        # Vor dem Bestand: alles ist Prognose — die Linie steht am linken
        # Rand, wie die Trennzeile ganz oben in der Tabelle.
        return -0.5
    if stichtag.year not in jahre:
        # Am oder hinter dem Horizont (bzw. in einer Luecke der
        # ausgewiesenen Jahre): alles Historie — dieselbe Lesart wie die
        # Tabelle, die dort keine Trennzeile setzt.
        return None
    return jahre.index(stichtag.year) - 0.5


def _neugeschaeft_html(
    konto: List[Dict[str, Any]],
    spec: Dict[str, Any],
    stichtag: Optional[_dt.date],
) -> str:
    """Zugangs-Annahme der Prognose — abgelesen aus dem Konto.

    Bewusst NICHT aus der Konfiguration abgeleitet: ob ein Lauf
    überhaupt Neuzugang simuliert hat, entscheidet der Aufruf der
    Fortschreibung, nicht die Konfiguration. Eine Aussage aus der
    Konfiguration könnte deshalb der Zugangszeile derselben Tabelle
    widersprechen. Gelesen wird, was im Konto steht.
    """
    if stichtag is None:
        return ""
    track = spec["tracks"][0][0]
    prognose = [z for z in konto if z["jahr"] >= stichtag.year]
    mit_zugang = [
        z["jahr"] for z in prognose if z[track]["zugang_neuzugang"]["stueck"]
    ]
    if not prognose:
        return ""
    if not mit_zugang:
        satz = (
            "Die Projektion enthält keinen Zugang: der Bestand läuft ab dem "
            "Stichtag ab (Abwicklung)."
        )
    else:
        letztes = max(mit_zugang)
        stueck = sum(
            z[track]["zugang_neuzugang"]["stueck"] for z in prognose
        )
        rest = [z["jahr"] for z in prognose if z["jahr"] > letztes]
        nachsatz = (
            f" Ab {letztes + 1} kommt kein Zugang mehr hinzu — der Bestand "
            "läuft danach ab."
            if rest else
            " Der Ausweis endet mit dem Projektionshorizont."
        )
        satz = (
            f"Die Projektion enthält {stueck} Zugänge, letztmals im Jahr "
            f"{letztes}.{nachsatz}"
        )
    return f"<p><strong>Zugang in der Prognose:</strong> {satz}</p>"


def _grundlagen_html(
    spec: Dict[str, Any], config: Optional[BestandConfig]
) -> str:
    """Rechnungsgrundlagen und wirksame Erfahrungsannahmen der Nachweisung.

    Stichtags-Angabe, keine Entwicklungsgeschichte: was gilt, nicht was
    sich geändert hat. Die Bewertung läuft auf den Rechnungsgrundlagen
    (erste Ordnung), die Fortschreibung auf den Erfahrungsannahmen
    (dritte Ordnung) — beides wird hier nebeneinander genannt, damit der
    Unterschied im Bericht sichtbar ist.
    """
    if config is None:
        return ""
    generationen = [g for g in config.generationen if g.produkt == spec["produkt"]]
    if not generationen:
        return ""
    zeilen = "".join(
        f"<li>{_html.escape(g.name)} ({g.gueltig_von.isoformat()} bis "
        f"{g.gueltig_bis.isoformat()}): {_html.escape(spec['grundlagen'](g))}</li>"
        for g in generationen
    )

    def annahme_text(name: str, titel: str) -> str:
        """Eine Annahme in Worten — die affine Form vollständig.

        Der additive Teil darf nicht verschwinden: ``a`` und ``b`` können
        gleichzeitig wirken, und die Simulation wendet beide an.
        """
        annahme = getattr(config.annahmen, name)
        a, b = annahme.a, annahme.b
        if a == 0.0 and b == 0.0:
            text = f"{titel} findet nicht statt"
        elif b == 0.0:
            text = f"{titel} {_prozent(a)} p. a."
        elif a == 0.0:
            text = (
                f"{titel} wie Rechnungsgrundlage" if b == 1.0
                else f"{titel} Rechnungsgrundlage × {_dezimal(b)}"
            )
        else:
            faktor = (
                "Rechnungsgrundlage" if b == 1.0
                else f"Rechnungsgrundlage × {_dezimal(b)}"
            )
            text = f"{titel} {faktor} zuzüglich {_prozent(a)} p. a."
        if name == "erhoehung" and (a > 0.0 or b > 0.0):
            # Die Rate sagt, WIE OFT erhoeht wird; die Hoehe steht
            # daneben und waere sonst mit ihr verwechselbar.
            text += f" (Erhöhung um je {_prozent(config.annahmen.erh_prozent)})"
        return text

    annahmen = "; ".join(
        annahme_text(n, titel) for n, titel in spec["annahmen"]
    )
    return f"""
<p><strong>Rechnungsgrundlagen</strong> (Bewertung, erste Ordnung):</p>
<ul>{zeilen}</ul>
<p><strong>Erfahrungsannahmen</strong> (Fortschreibung, dritte Ordnung):
{annahmen.rstrip(".")}.</p>
"""


def _nachweisung_html(
    konto: List[Dict[str, Any]],
    spec: Dict[str, Any],
    stichtag: Optional[_dt.date],
    config: Optional[BestandConfig],
) -> str:
    """Eine vollständige Nachweisung: je Träger Grafik und Bewegung.

    Mit ``stichtag`` wird jede Tabelle an genau einer Stelle geteilt:
    darüber die Historie (Bestandsaufbau bis zum Stichtag), darunter die
    Prognose. Die Zahlen selbst sind dieselben — die Trennung sagt, welcher
    Teil beobachtet und welcher projiziert ist.
    """
    relevant = [
        z for z in konto
        if any(
            z[track]["anfang"]["stueck"] or z[track]["ende"]["stueck"]
            for track, _t, _p in spec["tracks"]
        )
    ]
    if not relevant:
        return ""
    alle_ok = all(
        ok for z in konto for oks in z["identitaet"].values() for ok in oks.values()
    )
    pruefsatz = (
        "Die Identität Anfangsbestand + Zugang − Abgang = Endbestand gilt in "
        f"jedem Jahr, je Bestand, in Stück und {spec['bezug']} (Gate-geprüft)."
        if alle_ok else
        "WARNUNG: Bewegungs-Identität verletzt — Daten inkonsistent "
        "(Gate B1 schlägt fehl)."
    )

    def tabelle(track: str, positionen, mass: str) -> str:
        kopf = "<tr><th>Jahr</th>" + "".join(
            f"<th>{titel}</th>" for _pos, titel in positionen
        ) + "</tr>"
        spalten = len(positionen) + 1
        zeilen: List[str] = []
        getrennt = False
        for z in relevant:
            if (
                stichtag is not None and not getrennt
                and z["jahr"] >= stichtag.year
            ):
                zeilen.append(
                    f"<tr class='grenze'><td colspan='{spalten}'>"
                    f"Stichtag {stichtag.isoformat()} — ab hier Prognose"
                    "</td></tr>"
                )
                getrennt = True
            zellen = "".join(
                "<td class='num'>"
                f"{_zahl(z[track][pos][mass]) if mass == 'summe' else int(z[track][pos][mass])}"
                "</td>"
                for pos, _titel in positionen
            )
            zeilen.append(f"<tr><td>{z['jahr']}</td>{zellen}</tr>")
        return (
            f"<div class=\"breit\"><table><thead>{kopf}</thead>"
            f"<tbody>{''.join(zeilen)}</tbody></table></div>"
        )

    bloecke = []
    for track, track_titel, positionen in spec["tracks"]:
        chart = _chart_track(
            relevant, track, f"{track_titel} (Jahresende)",
            spec["farben"][track], stichtag,
        )
        bloecke.append(f"""
<h3>{track_titel}</h3>
<div class="charts">{chart}</div>
<p>Bewegung in Stück:</p>
{tabelle(track, positionen, "stueck")}
<p>Bewegung in {spec['bezug']}:</p>
{tabelle(track, positionen, "summe")}""")

    return f"""
<h2>Bestandsbewegung: {spec['titel']}</h2>
<p>Struktur nach der BaFin-Nachweisung zur Bestandsbewegung; Bezugsgröße ist
die {spec['bezug']}. {spec['erlaeuterung']} {pruefsatz}</p>
{_grundlagen_html(spec, config)}
{_neugeschaeft_html(relevant, spec, stichtag)}
{"".join(bloecke)}"""


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
    stichtag: Optional[_dt.date] = None,
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
    simuliert sind. ``stichtag`` (der Referenzstichtag des Bestands) teilt
    die Nachweisungen in **Historie** (Bestandsaufbau bis zum Stichtag) und
    **Prognose** (Entwicklung danach) — in den Tabellen als Trennzeile, in
    den Grafiken als senkrechte Linie.
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
    leistung, leistung_label = _leistungssicht(df)
    reihe = verlauf(bestand, stichtage, leistung)
    # Volumen-Verlauf je Versicherungsart. Die Vertragszahl ist ueber die
    # Arten addierbar, das versicherte Volumen nicht — bei gemischtem
    # Bestand stuende sonst eine reine KLV-Kurve neben einem Balken ueber
    # alle Vertraege, ohne dass die Darstellung das sagt.
    volumen_reihen = [
        dict(gruppe, reihe=verlauf(
            teilbestand(bestand, gruppe["produkt"]), stichtage, gruppe["leistung"]
        ))
        for gruppe in produkt_gruppen(df)
    ]
    # Strukturbild am Bestands-Hoechststand (erster Maximums-Stichtag —
    # deterministisch und aussagekraeftiger als der duenne Bestandsauslauf).
    hoechststand = max(reihe, key=lambda r: (r["vertraege"], -reihe.index(r)))
    # Struktur am Referenzstichtag (sonst am Bestands-Hoechststand): der
    # Bericht ist ein Stichtagsbericht, und beide Darstellungen muessen
    # denselben Schnitt zeigen.
    struktur_stichtag = stichtag or _dt.date.fromisoformat(
        hoechststand["stichtag"]
    )
    scheibe = zeitscheibe(bestand, struktur_stichtag)
    # Ereignis-Sicht auf dem um die Bestands-Zugaenge ergaenzten Ledger:
    # die Engine bucht ZUG nur fuer Neuzugaenge, die Vertraege des
    # Ausgangsbestands sind zum Simulationsbeginn schon da. Ohne die
    # Ergaenzung zeigte die Grafik alle Abgaenge ueber den ganzen
    # Zeitraum, den Zugang aber erst ab dem ersten Neugeschaeftsjahr.
    # Ein leerer Ledger bleibt leer: dass die Fortschreibung im Horizont
    # nichts gebucht hat, ist die Aussage des Abschnitts — sie soll nicht
    # von einer Zugangsliste verdeckt werden.
    gevo_ledger = (
        ledger_mit_bestandszugang(df, ledger)
        if historie is not None and ledger is not None and len(ledger) > 0
        else ledger
    )

    with plt.rc_context(_RC):
        svg_vertraege = _chart_verlauf_vertraege(reihe, generationen)
        mehrere_arten = len(volumen_reihen) > 1
        svg_summe = "".join(
            _chart_verlauf_summe(
                v["reihe"],
                v["leistung_label"],
                v["titel"] if mehrere_arten else "",
            )
            for v in volumen_reihen
        )
        # Struktur je Versicherungsart: Eintrittsalter, Laufzeit und
        # versicherte Leistung sind je Art anders definiert (Summe gegen
        # Jahresrente) und in einer gemeinsamen Grafik nicht vergleichbar.
        struktur_bloecke: List[str] = []
        for gruppe in produkt_gruppen(df):
            teil_df = teilbestand(df, gruppe["produkt"])
            teil_scheibe = teilbestand(scheibe, gruppe["produkt"])
            gens = generationsnamen(teil_df)
            if len(teil_scheibe) == 0:
                continue
            bilder = []
            for spalte, label in STRUKTUR_MERKMALE:
                if spalte == "leistung":
                    spalte, label = gruppe["leistung"], gruppe["leistung_label"]
                elif spalte == "age":
                    label = f"Alter am {struktur_stichtag.isoformat()}"
                bilder.append(
                    _chart_histogramm(teil_scheibe, spalte, label, label, 20, gens)
                )
            scatter = _chart_scatter_alter_laufzeit(teil_df, gens)
            struktur_bloecke.append(f"""
<h3>{gruppe['titel']}</h3>
<div class="charts">{''.join(bilder)}</div>
<div class="charts">{scatter}</div>""")
        struktur_html = "".join(struktur_bloecke)
        svg_status = svg_ereignisse = svg_dk = svg_beitrag = ""
        if historie is not None and len(ledger) > 0:
            svg_status = _chart_status_verlauf(status_verlauf(bestand, stichtage))
            svg_ereignisse = _chart_ereignisse_je_jahr(
                ereignisse_je_jahr(gevo_ledger)
            )
        reihe_ausw: List[Dict[str, Any]] = []
        if config is not None:
            reihe_ausw = auswertungs_verlauf(
                df, historie, config, stichtage, scheiben=scheiben
            )
            svg_dk = _chart_deckungskapital(reihe_ausw)
            svg_beitrag = _chart_beitraege(
                [r for r in reihe_ausw if r["vertraege"] > 0],
                any(r["bu_vertraege"] for r in reihe_ausw),
            )

    # Je Versicherungsart eine eigene Volumen-Spalte — dieselbe Trennung
    # wie in den Grafiken; die Vertragszahl bleibt die Gesamtzahl.
    zeilen = []
    for i, r in enumerate(reihe):
        gen_mix = ", ".join(
            f"{_html.escape(str(g))}: {n}" for g, n in r["generationen"].items()
        ) or "—"
        volumen = "".join(
            f"<td class='num'>{_zahl(v['reihe'][i]['summe_vs'])}</td>"
            for v in volumen_reihen
        )
        zeilen.append(
            f"<tr><td>{r['stichtag']}</td><td class='num'>{r['vertraege']}</td>"
            f"{volumen}"
            f"<td class='num'>{_zahl(r['mittel_alter'], 1)}</td>"
            f"<td class='num'>{_zahl(r['mittel_restlaufzeit_jahre'], 1)}</td>"
            f"<td>{gen_mix}</td></tr>"
        )
    volumen_kopf = "".join(
        f"<th>Σ {_html.escape(v['leistung_label'])}"
        + (f" ({_html.escape(v['titel'])})" if len(volumen_reihen) > 1 else "")
        + "</th>"
        for v in volumen_reihen
    )
    tabelle = (
        "<table><thead><tr><th>Stichtag</th><th>Verträge</th>"
        f"{volumen_kopf}<th>Ø Alter</th><th>Ø Restlaufzeit (J.)</th>"
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

    kopf_html = "\n".join(
        f"<li>{_html.escape(z)}</li>"
        for z in kopfzeilen(df, generationen, stichtage, stichtag, bis, quelle_hash)
    )
    stichtag_absatz = (
        f"<p>{TEXTE['stichtag']}</p>" if stichtag is not None else ""
    )
    stichtag_zeile = (
        f"<li>Referenzstichtag: {stichtag.isoformat()} — bis dahin Historie, "
        "danach Prognose</li>"
        if stichtag is not None else ""
    )
    fortschreibung_zeile = ""
    klv_hinweis = (
        "Beitragsfreie Verträge (PEX) bleiben in-force und gehen mit ihrer "
        "ursprünglichen Versicherungssumme in den Verlauf ein; die bei "
        "Beitragsfreistellung fixierten beitragsfreien Summen (VS_bfr) zeigt "
        f"die Tabelle. Die Spalte \"Σ {leistung_label}\" im Bestandsverlauf "
        "führt die Grundscheiben-Summen; die durch dynamische Erhöhungen "
        "hinzugekommenen Summen zeigt die ERH-Zeile der Tabelle, die "
        "aktuariellen Kennzahlen enthalten die Scheiben vollständig. "
        if leistung == "sum_insured" else ""
    )
    ereignis_html = ""
    if historie is not None:
        summen = ereignis_summen(gevo_ledger)
        if summen:
            letzter = gevo_ledger["status_date"].max().date().isoformat()
            fortschreibung_zeile = (
                f"<li>Geschäftsvorfälle: {len(gevo_ledger)} "
                f"(letzter am {letzter})</li>"
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
            gevo_von = int(gevo_ledger["status_date"].dt.year.min())
            gevo_bis = int(gevo_ledger["status_date"].dt.year.max())
            gevo_zeitraum = f"{gevo_von} bis {gevo_bis}"
            ereignis_html = f"""
<h2>Geschäftsvorfälle {gevo_zeitraum}</h2>
<div class="charts">{svg_status}{svg_ereignisse}</div>
{summen_tabelle}
<p>{TEXTE["gevo"].format(zeitraum=gevo_zeitraum)} Der Bestandsverlauf ist
abgangsbereinigt: stornierte, gestorbene und abgelaufene Verträge verlassen
den Bestand am Buchungstag. {klv_hinweis}Alle Beträge stammen aus dem
stabilen Rechenkern.</p>"""
        else:
            fortschreibung_zeile = "<li>Fortschreibung: keine Ereignisse im Horizont</li>"
            ereignis_html = (
                f"\n<h2>Geschäftsvorfälle {stichtage[0].year} bis "
                f"{stichtage[-1].year}</h2>"
                "<p>Keine Ereignisse im Berichtszeitraum.</p>"
            )

    # ------------------------------------------------------------------ #
    # Bestandsbewegung in Nachweisungs-Struktur — EINE Darstellung fuer
    # beide Produkte. Die Konten haben dieselbe Form (zwei Traeger-Bestaende
    # mit einer Umbuchung dazwischen); es unterscheiden sich nur die
    # Bezeichnungen und die Bezugsgroesse (Versicherungssumme gegen
    # Jahresrente). Mit ``stichtag`` wird jede Reihe in Historie und
    # Prognose geteilt.
    # ------------------------------------------------------------------ #
    nachweisungen: List[str] = []
    if historie is not None and bis is not None and len(ledger) > 0:
        for spec in NACHWEISUNGEN:
            if not spec["vorhanden"](df):
                continue
            konto = spec["konto"](df, historie, ledger, scheiben, bis)
            if not konto:
                continue
            nachweisungen.append(
                _nachweisung_html(konto, spec, stichtag, config)
            )
    bewegung_html = "\n".join(nachweisungen)

    auswertung_html = ""
    # Zeitraum der tatsaechlich ausgewiesenen Zeilen (nicht der ganzen
    # Stichtagsliste) — sonst nennt der Titel Jahre ohne Bestand.
    mit_bestand = [r for r in reihe if r["vertraege"] > 0]
    ausw_zeitraum = (
        f"{mit_bestand[0]['stichtag'][:4]} bis {mit_bestand[-1]['stichtag'][:4]}"
        if mit_bestand else f"{stichtage[0].year} bis {stichtage[-1].year}"
    )
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
        # Beitraege in eigener Tabelle statt als weitere Spalten: die
        # Kennzahlen-Tabelle traegt Bestandsgroessen, hier stehen die
        # Zahlungen — und acht Spalten waeren nicht mehr lesbar.
        # Einheitliche Benennung ueber beide Versicherungsarten: EIN Begriff
        # je Groesse, die Art steht als Zusatz. Zwei Groessen werden
        # unterschieden — der tarifliche Jahresbeitrag und das tatsaechlich
        # gezahlte Volumen (mit Ratenzuschlag und Stueckkosten).
        mit_bu = any(r["bu_vertraege"] for r in reihe_ausw)
        if mit_bu:
            beitrag_kopf = (
                "<th>Σ Jahresbeitrag (Kapitalversicherung)</th>"
                "<th>Σ Jahresbeitrag (Berufsunfähigkeit)</th>"
                "<th>Σ Jahresbeitrag gesamt</th>"
                "<th>Σ Beitragsvolumen p. a.</th>"
            )
        else:
            beitrag_kopf = (
                "<th>Σ Jahresbeitrag</th><th>Σ Beitragsvolumen p. a.</th>"
            )
        beitrag_zeilen = "".join(
            f"<tr><td>{r['stichtag']}</td>"
            f"<td class='num'>{_zahl(r['bjb'])}</td>"
            + (
                f"<td class='num'>{_zahl(r['bu_beitrag'])}</td>"
                f"<td class='num'>{_zahl(r['bjb'] + r['bu_beitrag'])}</td>"
                if mit_bu else ""
            )
            + f"<td class='num'>{_zahl(r['bzb_jahr'] + r['bu_beitrag'])}</td></tr>"
            for r in reihe_ausw
            if r["vertraege"] > 0
        )
        beitrag_tabelle = (
            "<table><thead><tr><th>Stichtag</th>"
            f"{beitrag_kopf}</tr></thead><tbody>"
            + beitrag_zeilen
            + "</tbody></table>"
        )
        auswertung_html = f"""
<h2>Aktuarielle Kennzahlen je Stichtag, {ausw_zeitraum}</h2>
<div class="charts">{svg_dk}</div>
{ausw_tabelle}
<p>Alle Werte kommen in-process aus dem stabilen Rechenkern.
Deckungskapital: beitragspflichtig die Deckungsrückstellung kDRx_bpfl,
nach Beitragsfreistellung die beitragsfreie Reserve (VS_bfr mal kVx_bfr).
Rückkaufswert nur auf dem beitragspflichtigen Track (das Quell-Blatt
definiert keine Rückkaufsregel für beitragsfreie Verträge).</p>

<h3>Beiträge</h3>
<div class="charts">{svg_beitrag}</div>
{beitrag_tabelle}
<p>{TEXTE["beitraege"]}</p>"""

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
/* Trennung Historie / Prognose am Stichtag */
tr.grenze td {{ background: #eee; font-weight: 600; text-align: center;
  border-top: 2px solid #333; border-bottom: 2px solid #333; }}
th, td {{ border: 1px solid #ddd; padding: .3rem .5rem; text-align: left; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
thead {{ background: #f5f5f5; }}
.charts {{ display: flex; flex-wrap: wrap; gap: 1rem; }}
.charts svg {{ max-width: 100%; height: auto; }}
footer {{ margin-top: 2rem; font-size: .8rem; color: #666; }}
</style>
</head>
<body>
<h1>{_html.escape(titel)}</h1>
<ul>
{kopf_html}
</ul>
{stichtag_absatz}

<h2>Bestandsverlauf</h2>
<div class="charts">{svg_vertraege}{svg_summe}</div>
<p>{TEXTE["verlauf"]}</p>

<h2>Bestandsstruktur am {struktur_stichtag.isoformat()}</h2>
<p>{TEXTE["struktur"]}</p>
{struktur_html}
{bewegung_html}
{ereignis_html}

<h2>Kennzahlen je Stichtag, {ausw_zeitraum}</h2>
{tabelle}
<p>{TEXTE["kennzahlen"]}</p>
{auswertung_html}

<h2>Zur Lesart</h2>
<p>{TEXTE["lesart"]}</p>

<footer>
Erzeugt mit <code>python -m rechner_pipeline.bestand.cli_report</code>
(Version {REPORT_VERSION}).
</footer>
</body>
</html>
"""
