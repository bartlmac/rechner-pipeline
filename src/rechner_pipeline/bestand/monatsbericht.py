"""Monatsbericht des Tagesbetriebs: EIN Stichtag, EIN Monat, zwoelf Monate Verlauf.

Warum ein eigener Renderer und nicht ein Parameter an
:func:`rechner_pipeline.bestand.report.render_html`: Dem grossen Bericht
laesst sich zwar ein Stichtagsraster mitgeben, aber das Raster steuert nur
Bestandsverlauf, Statusverlauf und die Auswertungstabellen. Drei Abschnitte
haengen nicht daran und zeigen unabhaengig davon die ganze Historie --
die Ereignissummen laufen ueber den vollen Ledger, das Ereignis-Chart
traegt eine Jahresachse ab dem ersten Geschaeftsjahr, und die
Nachweisungen rechnen von Bestandsbeginn bis zum Horizont. Ein Bericht,
der mit "Geschaeftsvorfaelle 1994 bis 2026" ueberschrieben ist, ist kein
Monatsbericht, auch wenn eine Kurve darin zwoelf Punkte hat. Dazu kommt
die Beschriftung: Die Charts des grossen Berichts kuerzen jeden Stichtag
auf sein Jahr (``stichtag[:4]``) und beschriften die Achse mit "1.1. des
Jahres"; auf einem Monatsraster stuenden dort zwoelf Jahreszahlen.

**Die Quelle sind die festgeschriebenen MONATSABSCHLUESSE, nicht eine
Nachrechnung.** Der Abschluss IST der in-force-Stand seines Stichtags; er
wird nach der Festschreibung nicht mehr angefasst und traegt bereits
Status, Leistung, Deckungskapital, Rueckkaufswert, Korrekturschicht und
Jahresbeitrag je Vertrag. Wer denselben Stichtag aus heutigen Tabellen
nachrechnet, erzaehlt von ihm eine andere Geschichte (T24-02): Der
Auskunfts-Schnitt auf der heutigen Sicht kennt Buchungen, die es am
Stichtag noch nicht gab. Genau das war am betriebenen Bestand zu sehen --
die nachgerechnete Vertragszahl zum 1.1.2026 lag um eins neben der Zahl
des Abschlusses, den die Unternehmensseite daneben ausweist. Ein Bericht,
der seiner eigenen Verlinkung widerspricht, ist kein Beleg.

Daraus folgt der Zuschnitt: Dieses Modul bekommt die dreizehn Abschluesse
des Zeitraums und das Tagesjournal, und sonst nichts. Kein Stamm, keine
Historie, keine Bewertung im Rechenkern -- die Bewertung ist im Abschluss
schon geschehen.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
import html as _html
from typing import Any, Dict, List, Mapping, Optional

import pandas as pd

from rechner_pipeline.bestand.berichtstexte import produkt_gruppen
from rechner_pipeline.bestand.kennzahlen import (
    EREIGNIS_LABELS,
    EREIGNIS_REIHENFOLGE,
)
from rechner_pipeline.bestand.report import (
    REPORT_VERSION,
    _EREIGNIS_FARBEN,
    _RC,
    _STATUS_FARBEN,
    _STATUS_LABELS,
    _svg,
    _zahl,
    plt,
)
from rechner_pipeline.models.bestand import (
    LEISTUNG_EREIGNISSE,
    ZUGANG_EREIGNISSE,
)

#: Ereignisse, die einen Vertrag in die Buecher bringen bzw. aus ihnen
#: herausnehmen. NICHT dasselbe wie ZUGANG_EREIGNISSE/LEISTUNG_EREIGNISSE:
#: Eine dynamische Erhoehung (ERH) ist ein Zugang an Versicherungssumme,
#: aber kein zusaetzlicher Vertrag, und eine Reaktivierung (REA) beendet
#: einen Leistungsbezug, ohne den Vertrag zu beenden. Die Stueckrechnung
#: braucht die engere Menge, sonst geht sie nicht auf.
STUECK_ZUGANG = ("ZUG", "MIG")
STUECK_ABGANG = ("STO", "TOD", "ABL")

#: Vorgabe fuer die Laenge des Berichtszeitraums.
MONATE = 12


def monatsraster(stichtag: _dt.date, monate: int = MONATE) -> List[_dt.date]:
    """Die Monatsersten des Berichtszeitraums: Eroeffnung plus ``monate``.

    Gibt ``monate + 1`` Daten zurueck, aufsteigend, der letzte ist
    ``stichtag``. Der erste ist der EROEFFNUNGSSTAND des Zeitraums, nicht
    einer der Berichtsmonate: Zu jedem Punkt ab dem zweiten gehoert die
    Periode (Vormonat, Monat], und nur mit dem Eroeffnungspunkt schliesst
    die Bewegungsrechnung ueber den Zeitraum.
    """
    raster = [stichtag]
    for _ in range(monate):
        erster = raster[0]
        raster.insert(0, (erster - _dt.timedelta(days=1)).replace(day=1))
    return raster


# --------------------------------------------------------------------------- #
# Zaehlung auf dem Tagesjournal
# --------------------------------------------------------------------------- #

def _sichtbar(journal: pd.DataFrame) -> pd.Series:
    """Der Sichtbarkeitstag je Zeile: ``max(status_date, buchungsdatum)``.

    Dieselbe Periodenachse wie
    :func:`~rechner_pipeline.bestand.kennzahlen.bewegungskennzahlen`, und
    aus demselben Grund: Ein Abschluss zum Stichtag S kennt einen Vorfall
    genau dann, wenn Wirkungstag UND Buchungstag <= S sind. Auf dem blossen
    Wirkungstag gezaehlt, fielen die Vorfaelle durch, die genau auf einen
    Stichtag wirken und danach gebucht werden -- am betriebenen Bestand
    ist das der Regelfall, nicht die Ausnahme. Dieselbe Achse macht
    ausserdem die Stueckrechnung pruefbar: Nur wenn Bestandszaehlung und
    Bewegungszaehlung denselben Schnitt benutzen, kann das Vertragskonto
    ueberhaupt aufgehen.
    """
    if "buchungsdatum" not in journal.columns:
        raise ValueError(
            "Der Monatsbericht braucht das Tagesjournal mit Spalte "
            "'buchungsdatum' -- ohne sie laesst sich der Sichtbarkeitstag "
            "nicht bilden, und jeder spaet gebuchte Vorfall auf einem "
            "Monatsersten fiele aus der Zaehlung")
    if not len(journal):
        # Ein leeres Journal ist ein moeglicher Zustand (erster
        # Betriebstag). Ohne den eigenen Zweig traegt die leere Spalte
        # keinen Zeittyp, und der Periodenvergleich brichte ab.
        return pd.Series(pd.to_datetime([]), index=journal.index)
    return journal[["status_date", "buchungsdatum"]].max(axis=1)


def _periode(journal: pd.DataFrame, von: _dt.date, bis: _dt.date) -> pd.DataFrame:
    """Die Zeilen der Periode ``(von, bis]`` auf dem Sichtbarkeitstag."""
    sichtbar = _sichtbar(journal)
    return journal[
        (sichtbar > pd.Timestamp(von)) & (sichtbar <= pd.Timestamp(bis))
    ]


def _vorfaelle(zeilen: pd.DataFrame, arten) -> int:
    """Vorfaelle, nicht Buchungszeilen.

    Ein Zugang bucht Versicherungssumme und Bruttojahresbeitrag als zwei
    Zeilen desselben Vorfalls; Schluessel ist (Police, Ereignis, Wirkungstag).
    """
    auswahl = zeilen[zeilen["ereignis"].isin(arten)]
    if not len(auswahl):
        return 0
    return int(len(auswahl.drop_duplicates(
        subset=["police_id", "ereignis", "status_date"])))


def ereignisse_je_monat(
    journal: pd.DataFrame, stichtage: List[_dt.date]
) -> List[Dict[str, Any]]:
    """Vorfaelle je Ereignisart und Berichtsmonat.

    ``stichtage`` ist das Raster aus :func:`monatsraster`; der erste Punkt
    ist die Eroeffnung und bekommt keine Zeile -- gezaehlt wird die Periode
    zwischen zwei aufeinanderfolgenden Punkten.
    """
    reihe: List[Dict[str, Any]] = []
    for vor, stichtag in zip(stichtage, stichtage[1:]):
        zeilen = _periode(journal, vor, stichtag)
        eintrag: Dict[str, Any] = {"stichtag": stichtag.isoformat()}
        for code in EREIGNIS_REIHENFOLGE:
            eintrag[code] = _vorfaelle(zeilen, [code])
        eintrag["zugaenge"] = _vorfaelle(zeilen, ZUGANG_EREIGNISSE)
        eintrag["leistungen"] = _vorfaelle(zeilen, LEISTUNG_EREIGNISSE)
        reihe.append(eintrag)
    return reihe


def ereignis_summen_periode(
    journal: pd.DataFrame, von: _dt.date, bis: _dt.date
) -> List[Dict[str, Any]]:
    """Anzahl und Betragssumme je Ereignisart in ``(von, bis]``.

    Wie :func:`~rechner_pipeline.bestand.kennzahlen.ereignis_summen`, nur
    auf der Periode statt auf dem ganzen Ledger -- und nach Betrags-Art
    getrennt, weil dieselben Codes bei Kapitalversicherung und
    Berufsunfaehigkeit verschiedene Bezugsgroessen tragen (Versicherungs-
    summe gegen Jahresrente). Eine gemeinsame Summe waere eine stille
    Vermischung nicht addierbarer Groessen.
    """
    zeilen = _periode(journal, von, bis)
    summen: List[Dict[str, Any]] = []
    for code in EREIGNIS_REIHENFOLGE:
        rows = zeilen[zeilen["ereignis"] == code]
        if len(rows) == 0:
            continue
        for art in sorted(set(rows["betrag_art"])):
            teil = rows[rows["betrag_art"] == art]
            summen.append({
                "ereignis": code,
                "label": EREIGNIS_LABELS[code],
                "anzahl": _vorfaelle(teil, [code]),
                "betrag_art": str(art),
                "summe_betrag": float(teil["betrag"].sum()),
            })
    return summen


# --------------------------------------------------------------------------- #
# Kennzahlen aus einem festgeschriebenen Abschluss
# --------------------------------------------------------------------------- #

def abschluss_kennzahlen(
    abschluss: pd.DataFrame, gruppen: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Die Bestandszahlen EINES Monatsabschlusses.

    Gelesen, nicht gerechnet: Jede Groesse steht im Abschluss und wurde
    dort zum Stichtag festgeschrieben. ``leistung_<produkt>`` bleibt je
    Versicherungsart getrennt -- Versicherungssumme und Jahresrente sind
    nicht addierbar.
    """
    werte: Dict[str, Any] = {
        "vertraege": int(len(abschluss)),
        "deckungskapital": float(abschluss["deckungskapital"].sum()),
        "rueckkaufswert": float(abschluss["rueckkaufswert"].sum()),
        "korrekturschicht": float(abschluss["korrekturschicht"].sum()),
        "vs_bfr": float(abschluss["vs_bfr"].sum()),
        "jahresbeitrag": float(abschluss["jahresbeitrag"].sum()),
    }
    status = abschluss["status_code"].value_counts()
    for code in ("POL", "PEX", "BU"):
        werte[code] = int(status.get(code, 0))
    bfr = abschluss[abschluss["status_code"] == "PEX"]
    werte["deckungskapital_bfr"] = float(bfr["deckungskapital"].sum())
    for gruppe in gruppen:
        teil = (abschluss[abschluss["produkt"] == gruppe["produkt"]]
                if "produkt" in abschluss.columns else abschluss)
        werte[f"leistung_{gruppe['produkt']}"] = float(teil["leistung"].sum())
        werte[f"vertraege_{gruppe['produkt']}"] = int(len(teil))
    return werte


# --------------------------------------------------------------------------- #
# Grafiken -- Monatsachse
# --------------------------------------------------------------------------- #

def _monatslabels(stichtage: List[str]) -> List[str]:
    """Achsenbeschriftung ``MM``; der Januar traegt das Jahr in zweiter Zeile.

    Dreizehn volle ISO-Daten passen nicht nebeneinander, dreizehnmal
    dieselbe Jahreszahl sagt nichts. Der Jahreswechsel ist die einzige
    Stelle, an der das Jahr gebraucht wird. Es steht UNTER dem Monat, nicht
    an seiner Stelle: eine vierstellige Zahl im Monatsraster stoesst sonst
    an ihre Nachbarn, und zwar genau auf den schmalen Grafiken, auf denen
    der Platz ohnehin knapp ist.
    """
    return [f"{s[5:7]}\n{s[:4]}" if s[5:7] == "01" else s[5:7]
            for s in stichtage]


def _legende_unter(ax, spalten: int) -> None:
    """Legende unter die Achse -- wenn es etwas zu beschriften gibt.

    In einem Monatsbericht sind die Balken ueber den ganzen Zeitraum
    annaehernd gleich hoch; es gibt keine leere Ecke, in der eine Legende
    niemandem im Weg staende. Ausserhalb der Achse verdeckt sie nichts,
    und ``bbox_inches="tight"`` beim Export nimmt sie mit.

    Ohne beschriftete Flaeche bleibt sie weg: Ein Monat ohne einen
    einzigen Geschaeftsvorfall ist ein moeglicher Monat, und matplotlib
    warnt dann ueber eine leere Legende.
    """
    if not ax.get_legend_handles_labels()[0]:
        return
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.22),
              ncol=spalten, fontsize=7.5, frameon=False)


def _chart_bestand_je_monat(reihe: List[Dict[str, Any]]) -> str:
    """In-force-Bestand je Monatserster, gestapelt nach Status."""
    x = list(range(len(reihe)))
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    unten = [0] * len(reihe)
    for status, label in _STATUS_LABELS:
        werte = [r.get(status, 0) for r in reihe]
        if not any(werte):
            continue
        ax.bar(x, werte, bottom=unten, label=label,
               color=_STATUS_FARBEN[status], width=0.75)
        unten = [u + w for u, w in zip(unten, werte)]
    ax.set_xticks(x, _monatslabels([r["stichtag"] for r in reihe]))
    ax.set_ylabel("Verträge in Kraft")
    _legende_unter(ax, 3)
    return _svg(fig)


def _chart_gevo_je_monat(reihe: List[Dict[str, Any]]) -> str:
    """Geschaeftsvorfaelle je Berichtsmonat, gestapelt nach Art."""
    x = list(range(len(reihe)))
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    unten = [0] * len(reihe)
    for code in EREIGNIS_REIHENFOLGE:
        werte = [r.get(code, 0) for r in reihe]
        if not any(werte):
            continue
        ax.bar(x, werte, bottom=unten, label=f"{EREIGNIS_LABELS[code]} ({code})",
               color=_EREIGNIS_FARBEN[code], width=0.75)
        unten = [u + w for u, w in zip(unten, werte)]
    ax.set_xticks(x, _monatslabels([r["stichtag"] for r in reihe]))
    ax.set_ylabel("Geschäftsvorfälle")
    _legende_unter(ax, 4)
    return _svg(fig)


def _chart_leistung_je_monat(
    reihe: List[Dict[str, Any]], schluessel: str, label: str, titel: str
) -> str:
    """Versichertes Volumen EINER Versicherungsart je Monatserster."""
    x = list(range(len(reihe)))
    werte = [r.get(schluessel, 0.0) / 1e6 for r in reihe]
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    ax.plot(x, werte, marker="o", markersize=3.5, color=_STATUS_FARBEN["POL"])
    ax.set_xticks(x, _monatslabels([r["stichtag"] for r in reihe]), fontsize=7)
    ax.set_ylabel(f"{label} (Mio.)", fontsize=8)
    ax.set_title(titel, fontsize=9)
    return _svg(fig)


def nahtstellen(reihe: List[Dict[str, Any]]) -> List[int]:
    """Die Stellen der Reihe, an denen die Bewertungskonvention wechselt.

    Die Konvention eines Abschlusses sagt ``models.bestand.abschluss_konvention``
    (gelesen ueber ``bestand.abschluss.lies_abschluss``); hier steht nur ihr
    Name. Ein leerer Abschluss traegt keine (``None``) und ist KEINE Naht:
    verglichen wird mit dem letzten Abschluss, der eine traegt.
    """
    naehte: List[int] = []
    letzte: Optional[str] = None
    for i, r in enumerate(reihe):
        k = r.get("konvention")
        if k is None:
            continue
        if letzte is not None and k != letzte:
            naehte.append(i)
        letzte = k
    return naehte


def _vergleichbar(a: Optional[Dict[str, Any]], b: Optional[Dict[str, Any]]) -> bool:
    """Zwei Abschluesse sind im Deckungskapital vergleichbar, wenn sie es in
    derselben Konvention fuehren — oder einer keine nennt (fehlt, leer)."""
    ka, kb = (a or {}).get("konvention"), (b or {}).get("konvention")
    return ka is None or kb is None or ka == kb


#: Groessen, die in der Bewertungskonvention stehen: Ueber eine Naht hinweg
#: ist ihre Differenz keine Bewegung des Bestands.
_DK_SCHLUESSEL = ("deckungskapital", "deckungskapital_bfr", "korrekturschicht")


def _chart_deckungskapital_je_monat(reihe: List[Dict[str, Any]]) -> str:
    """Deckungskapital je Monatserster, getrennt nach Beitragsstatus. An
    jeder Naht der Konvention steht eine Trennlinie, der Titel sagt es."""
    x = list(range(len(reihe)))
    fig, ax = plt.subplots(figsize=(3.6, 2.8))
    bpfl = [(r["deckungskapital"] - r["deckungskapital_bfr"]) / 1e6 for r in reihe]
    bfr = [r["deckungskapital_bfr"] / 1e6 for r in reihe]
    ax.bar(x, bpfl, label="beitragspflichtig", color=_STATUS_FARBEN["POL"], width=0.75)
    ax.bar(x, bfr, bottom=bpfl, label="beitragsfrei", color=_STATUS_FARBEN["PEX"], width=0.75)
    ax.set_xticks(x, _monatslabels([r["stichtag"] for r in reihe]), fontsize=7)
    ax.set_ylabel("Deckungskapital (Mio.)", fontsize=8)
    naehte = nahtstellen(reihe)
    for i in naehte:
        ax.axvline(i - 0.5, color="#b48a00", linestyle="--", linewidth=1.2)
    ax.set_title("Deckungskapital" + (" — Konventionswechsel (gestrichelt)" if naehte else ""),
                 fontsize=9)
    _legende_unter(ax, 2)
    return _svg(fig)


# --------------------------------------------------------------------------- #
# Tabellen
# --------------------------------------------------------------------------- #

def _delta(jetzt: float, vorher: Optional[float], dezimal: int = 0) -> str:
    """Veraenderung mit Vorzeichen; ohne Vergleichswert ein Gedankenstrich."""
    if vorher is None:
        return "—"
    d = jetzt - vorher
    if abs(d) < 0.5 * 10 ** -dezimal:
        return "±0" if dezimal == 0 else "±0," + "0" * dezimal
    return ("+" if d > 0 else "−") + _zahl(abs(d), dezimal)


def _stand_tabelle(
    jetzt: Dict[str, Any], vor: Optional[Dict[str, Any]],
    jahr: Optional[Dict[str, Any]], gruppen: List[Dict[str, Any]],
    stichtage: List[_dt.date],
) -> str:
    """Bestand am Stichtag, daneben Vormonat und Vorjahresmonat.

    Drei Spalten, weil ein Monatsbericht zwei Fragen beantworten muss: Was
    hat sich seit dem letzten Bericht geaendert (Vormonat), und ist das
    Bewegung oder Trend (Vorjahresmonat). Eine Zahl allein beantwortet
    keine von beiden.
    """
    zeilen: List[str] = []

    def zeile(name: str, schluessel: str, dezimal: int = 0) -> None:
        a = jetzt.get(schluessel, 0)
        b = vor.get(schluessel) if vor else None
        c = jahr.get(schluessel) if jahr else None
        dk = schluessel in _DK_SCHLUESSEL
        d_vor = (_delta(a, b, dezimal) if not dk or _vergleichbar(jetzt, vor)
                 else "Konvention gewechselt")
        d_jahr = (_delta(a, c, dezimal) if not dk or _vergleichbar(jetzt, jahr)
                  else "Konvention gewechselt")
        zeilen.append(
            f"<tr><td>{_html.escape(name)}</td>"
            f"<td class='num'>{_zahl(a, dezimal)}</td>"
            f"<td class='num'>{_zahl(b, dezimal) if b is not None else '—'}</td>"
            f"<td class='num'>{d_vor}</td>"
            f"<td class='num'>{_zahl(c, dezimal) if c is not None else '—'}</td>"
            f"<td class='num'>{d_jahr}</td></tr>"
        )

    zeile("Verträge in Kraft", "vertraege")
    for status, label in _STATUS_LABELS:
        if jetzt.get(status) or (vor or {}).get(status) or (jahr or {}).get(status):
            zeile(f"davon {label}", status)
    for gruppe in gruppen:
        zeile(f"Σ {gruppe['leistung_label']} ({gruppe['titel']})",
              f"leistung_{gruppe['produkt']}")
    zeile("Σ Deckungskapital", "deckungskapital")
    zeile("davon auf beitragsfreie Verträge", "deckungskapital_bfr")
    # Die Korrekturschicht steht auch dann, wenn sie klein ist. Sie ist
    # eine Position des Abschlusses (Grundsatzdokumentation 9.11), und
    # ein Bericht, der sie nur bei nennenswerter Hoehe zeigt, laesst
    # genau den Leser im Dunkeln, der nachsehen will, ob es sie gibt
    # (N-01). Auf dem gefuehrten Bestand sind es Cent-Betraege -- das ist
    # die Aussage, nicht ihr Fehlen.
    zeile("davon Korrekturschicht aus Übernahmen", "korrekturschicht", 2)
    zeile("Σ Rückkaufswert", "rueckkaufswert")
    zeile("Σ beitragsfreie Versicherungssumme (VS_bfr)", "vs_bfr")
    zeile("Σ Jahresbeitrag", "jahresbeitrag")
    return (
        "<table><thead><tr><th>Kennzahl</th>"
        f"<th>{stichtage[-1].isoformat()}</th>"
        f"<th>{stichtage[-2].isoformat()}</th><th>Veränderung</th>"
        f"<th>{stichtage[0].isoformat()}</th><th>Veränderung</th>"
        "</tr></thead><tbody>" + "".join(zeilen) + "</tbody></table>"
    )


def _bewegte_vertraege(
    journal: pd.DataFrame, policen: set, arten, bis: _dt.date
) -> Dict[str, int]:
    """Zu jedem bewegten Vertrag der Geschaeftsvorfall, der ihn bewegt hat.

    Genommen wird je Police der SPAETESTE Vorfall der gesuchten Arten bis
    zum Stichtag: Ein Vertrag, der storniert und spaeter abgelaufen waere,
    ist storniert ausgeschieden. Findet sich keiner, steht der Vertrag
    unter ``ohne Buchung`` -- das ist der Eroeffnungsbestand, der am ersten
    Tag da war und nicht hinzukam.
    """
    if not policen:
        return {}
    if not len(journal):
        # Bewegte Vertraege ohne jede Buchung: der Eroeffnungsbestand.
        return {"ohne Buchung": len(policen)}
    zeilen = journal[
        journal["police_id"].isin(policen)
        & journal["ereignis"].isin(arten)
        & (journal["status_date"] <= pd.Timestamp(bis))
    ]
    letzte = (zeilen.sort_values("status_date")
              .drop_duplicates(subset=["police_id"], keep="last"))
    gezaehlt = {code: int(n) for code, n
                in letzte["ereignis"].value_counts().items()}
    ohne = len(policen) - int(len(letzte))
    if ohne:
        gezaehlt["ohne Buchung"] = ohne
    return gezaehlt


def _vertragskonto(
    vorher: Optional[pd.DataFrame], nachher: pd.DataFrame,
    journal: pd.DataFrame, von: _dt.date, bis: _dt.date,
) -> str:
    """Stueckrechnung der Periode als ABGLEICH DER BEIDEN ABSCHLUESSE.

    Nicht die gebuchten Vorfaelle gezaehlt, sondern die Vertraege, die
    zwischen den beiden festgeschriebenen Abschluessen hinzugekommen oder
    ausgeschieden sind -- jeder mit dem Geschaeftsvorfall, der ihn bewegt
    hat. Damit schliesst das Konto nicht ungefaehr, sondern per
    Konstruktion, und jede Zeile steht fuer wirkliche Vertraege.

    Der Umweg ist noetig, weil Bestandszaehlung und Vorfallzaehlung
    verschiedene Zeitachsen haben, und zwar aus gutem Grund: Ein Ablauf
    tritt zum vereinbarten Tag ein, ob er gebucht ist oder nicht -- der
    Abschluss dieses Tages fuehrt den Vertrag schon nicht mehr. Ein Storno
    oder Todesfall wird dagegen gemeldet; bis zur Buchung bleibt der
    Vertrag in den Buechern. Faellt ein Monatserster auf ein Wochenende,
    wirken die Ablaeufe am Samstag und werden am Montag gebucht: Sie
    fehlen im Abschluss des einen Monats und erscheinen im Journal des
    naechsten. Aus Vorfallzaehlungen allein ginge das Konto dann um genau
    diese Faelle nicht auf -- am betriebenen Bestand im August 2026 um
    drei Vertraege.
    """
    if vorher is None:
        return (
            "<p>Zum " + von.isoformat() + " liegt kein Monatsabschluss vor; "
            "die Stückrechnung des Zeitraums beginnt erst mit dem ersten "
            "festgeschriebenen Bestand.</p>"
        )
    alt, neu = set(vorher["police_id"]), set(nachher["police_id"])
    zugang = _bewegte_vertraege(journal, neu - alt, STUECK_ZUGANG, bis)
    abgang = _bewegte_vertraege(journal, alt - neu, STUECK_ABGANG, bis)

    html = [
        f"<tr><td>Bestand am {von.isoformat()}</td>"
        f"<td class='num'>{_zahl(len(alt))}</td></tr>"
    ]
    for code, n in sorted(zugang.items(), key=lambda p: str(p[0])):
        name = (f"{EREIGNIS_LABELS[code]} ({code})" if code in EREIGNIS_LABELS
                else "Zugang ohne Buchung (Eröffnungsbestand)")
        html.append(f"<tr><td>{_html.escape(name)}</td>"
                    f"<td class='num'>+{_zahl(n)}</td></tr>")
    for code, n in sorted(abgang.items(), key=lambda p: str(p[0])):
        name = (f"{EREIGNIS_LABELS[code]} ({code})" if code in EREIGNIS_LABELS
                else "Abgang ohne Buchung")
        html.append(f"<tr><td>{_html.escape(name)}</td>"
                    f"<td class='num'>−{_zahl(n)}</td></tr>")
    html.append(
        f"<tr class='summe'><td>Bestand am {bis.isoformat()}</td>"
        f"<td class='num'>{_zahl(len(neu))}</td></tr>"
    )
    return (
        "<table><thead><tr><th>Position</th><th>Verträge</th>"
        "</tr></thead><tbody>" + "".join(html) + "</tbody></table>"
    )


def _monatstabelle(
    reihe: List[Dict[str, Any]], gevo: List[Dict[str, Any]],
    gruppen: List[Dict[str, Any]],
) -> str:
    """Eine Zeile je Berichtsmonat -- die Tabelle zu den Kurven darueber.

    Ohne den Eroeffnungspunkt: Zu ihm gehoert keine Periode, seine
    Bewegungsspalten waeren leer, und leere Zellen in der ersten Zeile
    liest jeder als fehlende Daten.
    """
    gevo_nach = {g["stichtag"]: g for g in gevo}
    zeilen = []
    for r in reihe[1:]:
        g = gevo_nach.get(r["stichtag"], {})
        volumen = "".join(
            "<td class='num'>"
            + _zahl(r.get("leistung_" + gr["produkt"], 0))
            + "</td>"
            for gr in gruppen
        )
        zeilen.append(
            f"<tr><td>{r['stichtag']}</td>"
            f"<td class='num'>{_zahl(r.get('vertraege', 0))}</td>"
            f"<td class='num'>{_zahl(r.get('POL', 0))}</td>"
            f"<td class='num'>{_zahl(r.get('PEX', 0))}</td>"
            f"<td class='num'>{_zahl(g.get('zugaenge', 0))}</td>"
            f"<td class='num'>{_zahl(g.get('leistungen', 0))}</td>"
            f"{volumen}"
            f"<td class='num'>{_zahl(r.get('deckungskapital', 0))}</td></tr>"
        )
    volumen_kopf = "".join(
        f"<th>Σ {_html.escape(gr['leistung_label'])}</th>" for gr in gruppen
    )
    return (
        "<table><thead><tr><th>Monatserster</th><th>Verträge in Kraft</th>"
        "<th>beitragspflichtig</th><th>beitragsfrei</th>"
        "<th>Zugangs-GeVo</th><th>Leistungs-GeVo</th>"
        f"{volumen_kopf}<th>Σ Deckungskapital</th>"
        "</tr></thead><tbody>" + "".join(zeilen) + "</tbody></table>"
    )


def _summen_tabelle(summen: List[Dict[str, Any]]) -> str:
    if not summen:
        return "<p>Im Berichtszeitraum wurde kein Geschäftsvorfall gebucht.</p>"
    zeilen = "".join(
        f"<tr><td>{_html.escape(s['label'])} ({s['ereignis']})</td>"
        f"<td class='num'>{_zahl(s['anzahl'])}</td>"
        f"<td>{_html.escape(s['betrag_art'])}</td>"
        f"<td class='num'>{_zahl(s['summe_betrag'], 2)}</td></tr>"
        for s in summen
    )
    return (
        "<table><thead><tr><th>Geschäftsvorfall</th><th>Anzahl</th>"
        "<th>Bezugsgröße</th><th>Σ Betrag</th></tr></thead><tbody>"
        + zeilen + "</tbody></table>"
    )


# --------------------------------------------------------------------------- #
# Bericht
# --------------------------------------------------------------------------- #

CSS = """
body { font-family: system-ui, sans-serif; max-width: 58rem; margin: 2rem auto;
  padding: 0 1rem; color: #1a1a1a; }
h1 { margin-bottom: .2rem; font-size: 1.6rem; }
p.unterzeile { margin-top: 0; color: #555; }
h2 { border-bottom: 1px solid #ddd; padding-bottom: .3rem; margin-top: 2.4rem;
  font-size: 1.15rem; }
h3 { font-size: .98rem; margin-top: 1.6rem; }
table { border-collapse: collapse; width: 100%; font-size: .82rem;
  margin: .8rem 0; }
th, td { border: 1px solid #ddd; padding: .35rem .55rem; text-align: left; }
td.num { text-align: right; font-variant-numeric: tabular-nums; }
thead { background: #f5f5f5; }
tr.summe td { font-weight: 600; border-top: 2px solid #333; }
ul.kopf { display: flex; flex-wrap: wrap; gap: .5rem 2rem; list-style: none;
  padding: .7rem 1rem; margin: 1rem 0; background: #f7f7f7;
  border: 1px solid #e3e3e3; font-size: .85rem; }
.charts { display: flex; flex-wrap: wrap; gap: 1rem; align-items: flex-start; }
.charts svg { max-width: 100%; height: auto; }
p.hinweis { font-size: .85rem; color: #444; }
/* Auf dem Telefon scrollt die TABELLE, nicht die Seite. Ohne das schiebt
   eine neunspaltige Bewegungstabelle das ganze Dokument nach rechts, und
   der Leser zieht bei jedem Absatz zurueck. Nur unterhalb der Satzbreite,
   damit die Ansicht am Schreibtisch bleibt, wie sie ist. */
@media (max-width: 42rem) {
  table { display: block; overflow-x: auto; white-space: nowrap; }
}
footer { margin-top: 2.5rem; font-size: .8rem; color: #666;
  border-top: 1px solid #ddd; padding-top: .6rem; }
"""


def render_html(
    abschluesse: Mapping[_dt.date, pd.DataFrame],
    journal: pd.DataFrame,
    stichtag: _dt.date,
    monate: int = MONATE,
    titel: Optional[str] = None,
    quelle_hash: Optional[str] = None,
    stand: Optional[_dt.date] = None,
    unternehmen: str = "Pfefferminzia Lebensversicherung AG",
    hinweis: str = "",
    konventionen: Optional[Mapping[_dt.date, Optional[str]]] = None,
) -> str:
    """Der Monatsbericht als selbst-enthaltenes HTML.

    ``konventionen`` nennt je Stichtag die Bewertungskonvention seines
    Abschlusses, wie ``bestand.abschluss.lies_abschluss`` sie sagt (``None``
    fuer einen leeren Abschluss). Ueberspannt das Fenster zwei Konventionen,
    zeichnet der Bericht die Reihe nicht still: Trennlinie an der Naht,
    keine Veraenderung des Deckungskapitals ueber sie hinweg, ein Satz dazu.

    ``abschluesse`` sind die festgeschriebenen Monatsabschluesse des
    Rasters (:func:`monatsraster`), mindestens der zum ``stichtag``.
    Fehlende Monate -- etwa vor dem Betriebsbeginn -- duerfen fehlen; ihre
    Zeile entfaellt, und die Bewegungsrechnung laesst den Anfangsbestand
    offen, statt ihn zu erfinden.

    ``journal`` ist das TAGESJOURNAL (mit ``buchungsdatum``), nicht der
    Ledger: Nur das Journal traegt den Buchungstag, und ohne ihn zaehlt
    keine Periodenrechnung die auf einem Monatsersten wirkenden, spaeter
    gebuchten Vorfaelle mit. ``stand`` ist der Tag, bis zu dem gefuehrt
    wurde (Vorgabe: der Stichtag); er steht im Kopf, damit ein Leser
    Stichtag und Stand nicht verwechselt.

    ``hinweis`` steht im Fuss. Ein Bericht ist eine selbst-enthaltene
    Datei und wandert ohne die Seite, die ihn verlinkt: Wer nur seinen
    Link bekommt, sieht deren Einordnung nicht. Was zum Verstaendnis des
    Berichts gehoert, muss deshalb IM Bericht stehen.

    Der Bericht zeigt AUSSCHLIESSLICH den Berichtszeitraum. Die
    Gesamtentwicklung seit Betriebsbeginn steht im Jahresbericht; sie hier
    zusaetzlich zu zeigen hiesse, zwei Dokumente mit verschiedener Frage
    in eines zu falten.
    """
    if stichtag not in abschluesse:
        raise ValueError(
            f"Zum Berichtsstichtag {stichtag.isoformat()} fehlt der "
            "Monatsabschluss -- ohne ihn gibt es keinen Bestand, ueber den "
            "zu berichten waere")
    stichtage = monatsraster(stichtag, monate)
    von, vormonat = stichtage[0], stichtage[-2]
    stand = stand or stichtag
    titel = titel or f"Monatsbericht zum {stichtag.isoformat()}"
    gruppen = produkt_gruppen(abschluesse[stichtag])

    kennzahlen = {
        tag: dict(abschluss_kennzahlen(abschluesse[tag], gruppen),
                  konvention=(konventionen or {}).get(tag))
        for tag in stichtage if tag in abschluesse
    }
    reihe = [dict(kennzahlen[t], stichtag=t.isoformat())
             for t in stichtage if t in kennzahlen]
    gevo = ereignisse_je_monat(journal, stichtage)
    jetzt = kennzahlen[stichtag]
    bekannte = sorted({str(r["konvention"]) for r in reihe if r.get("konvention") is not None})
    konvention_hinweis = (
        "<p class=\"hinweis\">Das Deckungskapital dieses Zeitraums steht in zwei "
        f"Konventionen ({', '.join(_html.escape(k) for k in bekannte)}): Abschlüsse "
        "vor der Umstellung führen den Wert des letzten Jahrestags, spätere den "
        "monatsgenauen. Festgeschriebene Abschlüsse werden nicht nachträglich "
        "geändert. Die Stufe am Wechsel ist deshalb keine Bewegung des Bestands; "
        "Veränderungen über den Wechsel hinweg sind nicht ausgewiesen.</p>"
        if len(bekannte) > 1 else "")

    with plt.rc_context(_RC):
        svg_bestand = _chart_bestand_je_monat(reihe)
        svg_gevo = _chart_gevo_je_monat(gevo)
        svg_volumen = "".join(
            _chart_leistung_je_monat(
                reihe, f"leistung_{gr['produkt']}",
                gr["leistung_label"], gr["titel"])
            for gr in gruppen
        )
        svg_dk = _chart_deckungskapital_je_monat(reihe)

    quelle = (
        "<li><b>Prüfsumme der Quelle:</b> "
        f"<code>{_html.escape(quelle_hash[:16])}</code></li>"
        if quelle_hash else ""
    )
    kopf = (
        f"<li><b>Berichtsstichtag:</b> {stichtag.isoformat()}</li>"
        f"<li><b>Berichtszeitraum:</b> {von.isoformat()} bis "
        f"{stichtag.isoformat()}</li>"
        f"<li><b>Stand der Führung:</b> {stand.isoformat()}</li>"
        f"<li><b>Verträge in Kraft:</b> {_zahl(jetzt['vertraege'])}</li>"
        f"{quelle}"
    )

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>{_html.escape(titel)}</title>
<style>{CSS}</style>
</head>
<body>
<h1>{_html.escape(titel)}</h1>
<p class="unterzeile">{_html.escape(unternehmen)} — Bestand am Stichtag,
Bewegung im Berichtsmonat, Entwicklung der letzten {monate} Monate.</p>
<ul class="kopf">
{kopf}
</ul>

<h2>Bestand am {stichtag.isoformat()}</h2>
{_stand_tabelle(jetzt, kennzahlen.get(vormonat), kennzahlen.get(von),
                gruppen, stichtage)}
{konvention_hinweis}
<p class="hinweis">Alle Zahlen stammen aus dem festgeschriebenen
Monatsabschluss des jeweiligen Stichtags; sie sind nicht nachgerechnet. Die
Vergleichsspalten zeigen denselben Abschluss einen Monat und
{monate} Monate früher: die eine beantwortet, was sich seit dem letzten
Bericht geändert hat, die andere, ob das Bewegung oder Trend ist.
Versicherungssumme und Jahresrente stehen getrennt, weil sie nicht
addierbar sind. Die Korrekturschicht ist der bei einer Übernahme
verankerte Anteil am Deckungskapital; sie ist darin enthalten und wird
gesondert ausgewiesen, damit erkennbar bleibt, wie viel des Kapitals
nicht aus eigener Fortschreibung stammt.</p>

<h2>Der Berichtsmonat: {vormonat.isoformat()} bis {stichtag.isoformat()}</h2>
{_vertragskonto(abschluesse.get(vormonat), abschluesse[stichtag],
                journal, vormonat, stichtag)}
<p class="hinweis">Die Stückrechnung gleicht die beiden Monatsabschlüsse ab:
Sie führt jeden Vertrag, der zwischen ihnen hinzugekommen oder
ausgeschieden ist, mit dem Geschäftsvorfall, der ihn bewegt hat.
Beitragsfreistellung, Beitragsherabsetzung, Invalidisierung und
Reaktivierung verschieben innerhalb des Bestands und lassen die
Vertragszahl unberührt; sie stehen in der Tabelle darunter.</p>
{_summen_tabelle(ereignis_summen_periode(journal, vormonat, stichtag))}
<p class="hinweis">Diese Tabelle zählt die im Monat GEBUCHTEN
Geschäftsvorfälle — Vorfälle, nicht Buchungszeilen: Ein Zugang bucht
Versicherungssumme und Jahresbeitrag als zwei Zeilen desselben Vorfalls.
Ein Vorfall gehört in den Monat, in dem er sichtbar wurde, also den
späteren von Wirkungstag und Buchungstag. Deshalb kann sie von der
Stückrechnung darüber abweichen: Ein Ablauf tritt zum vereinbarten Tag
ein, ob er gebucht ist oder nicht, und fällt der Monatserste auf ein
Wochenende, wirkt er am Samstag und wird am Montag gebucht.</p>

<h2>Die letzten {monate} Monate</h2>
<div class="charts">{svg_bestand}</div>
<div class="charts">{svg_gevo}</div>
<div class="charts">{svg_volumen}{svg_dk}</div>
{_monatstabelle(reihe, gevo, gruppen)}

<h2>Bewegung im Berichtszeitraum</h2>
{_vertragskonto(abschluesse.get(von), abschluesse[stichtag],
                journal, von, stichtag)}
{_summen_tabelle(ereignis_summen_periode(journal, von, stichtag))}

<h2>Zur Lesart</h2>
<p>Dies ist ein Betriebsbericht: Er endet am Berichtsstichtag und enthält
keine Projektion. Der Betrieb kennt die Zukunft nicht — er entdeckt sie
täglich. Der Bestand am Stichtag ist der Monatsabschluss desselben Tages;
ein Monatsabschluss wird nach seiner Festschreibung nicht mehr angefasst,
und deshalb steht hier dieselbe Zahl wie in jeder anderen Auswertung
dieses Stichtags.</p>
<p>Der Bericht zeigt ausschließlich den Berichtszeitraum. Die Entwicklung
des Bestandes seit Betriebsbeginn steht im Jahresbericht zum
Kalenderjahresende; beide Dokumente beantworten verschiedene Fragen und
sind nicht ineinander enthalten.</p>

<footer>
{_html.escape(unternehmen)} — erzeugt aus den festgeschriebenen
Monatsabschlüssen (Berichtsbaustein Version {REPORT_VERSION}).
{f"<br>{_html.escape(hinweis)}" if hinweis else ""}
</footer>
</body>
</html>
"""
