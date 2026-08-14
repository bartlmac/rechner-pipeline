"""Bestandsbericht als Markdown mit PNG-Grafiken (Doku-Engine-Pfad).

Zweite Ausgabeform desselben Berichts: :mod:`rechner_pipeline.bestand.report`
erzeugt eine selbst-enthaltene HTML-Datei (Inline-SVG, Bildschirm), dieses
Modul ein Markdown-Dokument mit PNG-Grafiken für die Doku-Engine
(Quarto/Typst → PDF). Beide lesen dieselben Kennzahlen-Funktionen und
dieselbe Nachweisungs-Beschreibung (:data:`~rechner_pipeline.bestand.report.NACHWEISUNGEN`)
— es gibt EINEN Berichtsinhalt in zwei Darstellungen, keine zwei Berichte.

Zwei Dinge löst diese Form anders als das HTML, weil eine Druckseite
schmaler ist als ein Bildschirm:

* **Einheiten**: Beträge werden je Tabelle auf eine gemeinsame Einheit
  skaliert (EUR, Tsd. EUR, Mio. EUR, Mrd. EUR); die Einheit steht in der
  Einleitungszeile der Tabelle bzw. im Spaltenkopf. Sonst stünden dort
  zwölfstellige Zahlen, die niemand mehr liest.
* **Zeiträume**: Jede Aggregation nennt den Zeitraum, über den sie summiert
  — eine Anzahl ohne Zeitraum ist keine Information.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
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
    ereignis_summen,
    generationsnamen,
    jahresraster,
    verlauf,
)
from rechner_pipeline.bestand.report import (  # noqa: E402
    NACHWEISUNGEN,
    REPORT_VERSION,
    _RC,
    _grundlagen_html,
    _leistungssicht,
    _neugeschaeft_html,
    _prozent,
    _stichtags_position,
)
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe  # noqa: E402

#: Einheiten-Stufen: (Schwelle, Teiler, Bezeichnung, Nachkommastellen).
#: Gewählt wird die Stufe, in der der größte Betrag der Tabelle einstellig
#: bis vierstellig bleibt — die Staffelung der Geschäftsberichterstattung
#: (ab 1.000 in Tsd., ab 1 Mio. in Mio., ab 1 Mrd. in Mrd.). Zwei
#: Nachkommastellen halten die Auflösung; wissenschaftliche Notation kommt
#: in einem Geschäftsdokument nicht vor.
EINHEITEN: Tuple[Tuple[float, float, str, int], ...] = (
    (1e9, 1e9, "Mrd. EUR", 2),
    (1e6, 1e6, "Mio. EUR", 2),
    (1e4, 1e3, "Tsd. EUR", 1),
    (0.0, 1.0, "EUR", 0),
)


def einheit_fuer(werte) -> Tuple[float, str, int]:
    """Gemeinsame Einheit für eine Wertemenge (Teiler, Bezeichnung, Stellen).

    Je Tabelle EINE Einheit — verschiedene Einheiten in einer Spalte wären
    nicht vergleichbar. Maßgeblich ist der größte Absolutbetrag.
    """
    groesste = max((abs(float(w)) for w in werte), default=0.0)
    for schwelle, teiler, name, stellen in EINHEITEN:
        if groesste >= schwelle:
            return teiler, name, stellen
    return 1.0, "EUR", 0


def zahl(value: float, dezimal: int = 0) -> str:
    """Deutsche Tausender-Formatierung ohne Locale-Abhängigkeit."""
    s = f"{value:,.{dezimal}f}"
    return s.replace(",", "_").replace(".", ",").replace("_", ".")


def _tabelle(kopf: List[str], zeilen: List[List[str]]) -> str:
    return "\n".join(
        ["| " + " | ".join(kopf) + " |", "|" + "---|" * len(kopf)]
        + ["| " + " | ".join(z) + " |" for z in zeilen]
    )


def _zeitraum(von: Any, bis: Any) -> str:
    """Zeitraum-Angabe für eine Aggregation (Jahre)."""
    return f"{von} bis {bis}"


def _speichere(fig, ziel: Path) -> str:
    fig.savefig(ziel, bbox_inches="tight")
    plt.close(fig)
    return ziel.name


def render_markdown(
    df: pd.DataFrame,
    bild_dir: Path,
    bild_praefix: str = "bericht",
    stichtage: Optional[List[_dt.date]] = None,
    titel: str = "Bestandsbericht",
    historie: Optional[pd.DataFrame] = None,
    ledger: Optional[pd.DataFrame] = None,
    config: Optional[BestandConfig] = None,
    scheiben: Optional[pd.DataFrame] = None,
    bis: Optional[_dt.date] = None,
    stichtag: Optional[_dt.date] = None,
) -> str:
    """Bericht als Markdown; die Grafiken landen als PNG in ``bild_dir``.

    Die Bilder werden relativ referenziert (gleicher Ordner wie das
    Markdown), damit die Doku-Engine sie ohne Pfadumbau findet.
    """
    bild_dir = Path(bild_dir)
    bild_dir.mkdir(parents=True, exist_ok=True)
    if (historie is None) != (ledger is None):
        raise ValueError(
            "historie und ledger gehoeren zusammen (ein fortschreiben-Lauf)"
        )
    if stichtage is None:
        stichtage = jahresraster(df)
    sicht = bestand_mit_historie(df, historie) if historie is not None else df
    leistung, leistung_label = _leistungssicht(df)
    generationen = generationsnamen(df)
    reihe = verlauf(sicht, stichtage, leistung)
    jahre_von, jahre_bis = stichtage[0].year, stichtage[-1].year

    def bild(name: str) -> Path:
        return bild_dir / f"{bild_praefix}_{name}.png"

    teile: List[str] = [f"# {titel}", ""]

    # ---------------------------------------------------------------- #
    # Kopf: was der Bericht zeigt
    # ---------------------------------------------------------------- #
    teile += [
        f"- {z}"
        for z in kopfzeilen(df, generationen, stichtage, stichtag, bis)
    ] + [""]
    if stichtag is not None:
        teile += [TEXTE["stichtag"], ""]

    with plt.rc_context(_RC):
        # ---------------------------------------------------------- #
        # Bestandsverlauf
        # ---------------------------------------------------------- #
        x = list(range(len(reihe)))
        labels = [r["stichtag"][:4] for r in reihe]
        schritt = max(1, len(x) // 12)
        grenze = None
        if stichtag is not None:
            grenze = next(
                (i for i, r in enumerate(reihe)
                 if r["stichtag"] >= stichtag.isoformat()), None
            )
        fig, ax = plt.subplots(figsize=(8.0, 2.8))
        unten = [0] * len(reihe)
        for gi, gen in enumerate(generationen):
            werte = [r["generationen"].get(gen, 0) for r in reihe]
            ax.bar(x, werte, bottom=unten, label=gen,
                   color=_farbe_zyklisch(gi), width=0.8)
            unten = [u + w for u, w in zip(unten, werte)]
        if grenze is not None:
            ax.axvline(grenze - 0.5, color="#333333", linewidth=1.0, linestyle="--")
        ax.set_xticks(x[::schritt], labels[::schritt])
        ax.set_ylabel("in-force-Verträge")
        ax.legend(fontsize=7)
        verlauf_bild = _speichere(fig, bild("verlauf"))
        teile.append(
            f"\n## Bestandsverlauf\n\n"
            f"![In-force-Bestand je Stichtag]({verlauf_bild})\n\n"
            + TEXTE["verlauf"]
        )

        # ---------------------------------------------------------- #
        # Bestandsstruktur je Versicherungsart
        # ---------------------------------------------------------- #
        struktur_stichtag = stichtag or _dt.date.fromisoformat(
            max(reihe, key=lambda r: r["vertraege"])["stichtag"]
        )
        scheibe = zeitscheibe(sicht, struktur_stichtag)
        bloecke = []
        for gruppe in produkt_gruppen(df):
            teil_df = teilbestand(df, gruppe["produkt"])
            teil_scheibe = teilbestand(scheibe, gruppe["produkt"])
            if len(teil_scheibe) == 0:
                continue
            gens = generationsnamen(teil_df)
            bilder = []
            for spalte, label in STRUKTUR_MERKMALE:
                if spalte == "leistung":
                    spalte, label = gruppe["leistung"], gruppe["leistung_label"]
                elif spalte == "age":
                    label = f"Alter am {struktur_stichtag.isoformat()}"
                fig, ax = plt.subplots(figsize=(4.4, 2.8))
                daten = [
                    teil_scheibe.loc[
                        teil_scheibe["tarif_generation"] == g, spalte
                    ].to_numpy(float)
                    for g in gens
                ]
                ax.hist(daten, bins=20, stacked=True, label=gens,
                        color=[_farbe_zyklisch(i) for i in range(len(gens))])
                ax.set_xlabel(label)
                ax.set_ylabel("Verträge")
                ax.legend(fontsize=6)
                datei = _speichere(
                    fig, bild(f"{gruppe['produkt']}_{spalte}")
                )
                bilder.append(f"![{label}]({datei})")
            fig, ax = plt.subplots(figsize=(5.4, 3.2))
            for gi, gen in enumerate(gens):
                rows = teil_df[teil_df["tarif_generation"] == gen]
                ax.scatter(rows["entry_age"], rows["duration"], s=7, alpha=0.35,
                           color=_farbe_zyklisch(gi), label=gen, edgecolors="none")
            ax.set_xlabel("Eintrittsalter")
            ax.set_ylabel("Laufzeit (Jahre)")
            ax.legend(fontsize=7)
            copula = _speichere(fig, bild(f"{gruppe['produkt']}_copula"))
            bloecke.append(
                f"\n### {gruppe['titel']}\n\n" + "\n\n".join(bilder)
                + f"\n\n![Eintrittsalter und Laufzeit]({copula})"
            )
        teile.append(
            f"\n## Bestandsstruktur am {struktur_stichtag.isoformat()}\n\n"
            + TEXTE["struktur"] + "\n" + "".join(bloecke)
        )

        # ---------------------------------------------------------- #
        # Nachweisungen und Geschaeftsvorfaelle
        # ---------------------------------------------------------- #
        if historie is not None and bis is not None and len(ledger) > 0:
            for spec in NACHWEISUNGEN:
                if not spec["vorhanden"](df):
                    continue
                konto = spec["konto"](df, historie, ledger, scheiben, bis)
                if not konto:
                    continue
                teile.append(
                    _nachweisung_md(konto, spec, stichtag, config, bild, bild_praefix)
                )

            gevo_von = int(ledger["status_date"].dt.year.min())
            gevo_bis = int(ledger["status_date"].dt.year.max())
            summen = ereignis_summen(ledger)
            teiler, einheit, stellen = einheit_fuer(
                [s["summe_betrag"] for s in summen]
            )
            teile.append(
                f"\n## Geschäftsvorfälle {_zeitraum(gevo_von, gevo_bis)}\n\n"
                + _tabelle(
                    ["Geschäftsvorfall", "Anzahl", "Bezugsgröße",
                     f"Summe ({einheit})"],
                    [
                        [f"{s['label']} ({s['ereignis']})", str(s["anzahl"]),
                         s["betrag_art"], zahl(s["summe_betrag"] / teiler, stellen)]
                        for s in summen
                    ],
                )
                + "\n\n"
                + TEXTE["gevo"].format(zeitraum=_zeitraum(gevo_von, gevo_bis))
            )

        # ---------------------------------------------------------- #
        # Aktuarielle Kennzahlen
        # ---------------------------------------------------------- #
        # Zeitraum der ausgewiesenen Zeilen (nicht der ganzen
        # Stichtagsliste) — identisch zur HTML-Darstellung.
        mit_bestand = [r for r in reihe if r["vertraege"] > 0]
        zeitraum = (
            _zeitraum(mit_bestand[0]["stichtag"][:4],
                      mit_bestand[-1]["stichtag"][:4])
            if mit_bestand else _zeitraum(jahre_von, jahre_bis)
        )
        teiler, einheit, stellen = einheit_fuer([r["summe_vs"] for r in reihe])
        teile.append(
            f"\n## Kennzahlen je Stichtag, {zeitraum}\n\n"
            + _tabelle(
                ["Stichtag", "Verträge", f"Σ {leistung_label} ({einheit})",
                 "Ø Alter", "Ø Restlaufzeit (J.)"],
                [
                    [r["stichtag"], str(r["vertraege"]),
                     zahl(r["summe_vs"] / teiler, stellen),
                     zahl(r["mittel_alter"], 1),
                     zahl(r["mittel_restlaufzeit_jahre"], 1)]
                    for r in reihe
                    if r["vertraege"] > 0 and int(r["stichtag"][:4]) % 5 == 0
                ],
            )
            + "\n\n" + TEXTE["kennzahlen"]
        )

        if config is not None:
            ausw = auswertungs_verlauf(df, historie, config, stichtage,
                                       scheiben=scheiben)
            aktiv = [r for r in ausw if r["vertraege"] > 0]
            if aktiv:
                teile.append(_kennzahlen_md(aktiv, reihe, leistung_label, df))

    teile.append(
        "\n## Zur Lesart\n\n"
        + TEXTE["lesart_betraege"] + " " + TEXTE["lesart"]
        + "\n\nErzeugt mit `python -m rechner_pipeline.toolbox.bestand_report "
        f"--format md` (Berichtsversion {REPORT_VERSION})."
    )
    return "\n".join(teile) + "\n"


def _farbe_zyklisch(index: int) -> str:
    farben = ("#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b")
    return farben[index % len(farben)]


def _nachweisung_md(
    konto: List[Dict[str, Any]],
    spec: Dict[str, Any],
    stichtag: Optional[_dt.date],
    config: Optional[BestandConfig],
    bild,
    praefix: str,
) -> str:
    """Eine Nachweisung als Markdown — je Träger-Bestand Grafik und Bewegung."""
    relevant = [
        z for z in konto
        if any(
            z[track]["anfang"]["stueck"] or z[track]["ende"]["stueck"]
            for track, _t, _p in spec["tracks"]
        )
    ]
    if not relevant:
        return ""
    von, bis_jahr = relevant[0]["jahr"], relevant[-1]["jahr"]
    alle_ok = all(
        ok for z in konto for oks in z["identitaet"].values() for ok in oks.values()
    )
    pruefsatz = (
        "Die Identität Anfangsbestand + Zugang − Abgang = Endbestand gilt in "
        f"jedem Jahr, je Bestand, in Stück und {spec['bezug']} (Gate-geprüft)."
        if alle_ok else
        "WARNUNG: Bewegungs-Identität verletzt — Daten inkonsistent."
    )
    grundlagen = _als_markdown(_grundlagen_html(spec, config))
    neugeschaeft = _als_markdown(_neugeschaeft_html(relevant, spec, stichtag))

    bloecke = []
    for track, track_titel, positionen in spec["tracks"]:
        x = list(range(len(relevant)))
        labels = [str(z["jahr"]) for z in relevant]
        fig, ax = plt.subplots(figsize=(8.0, 2.4))
        ax.bar(x, [z[track]["ende"]["stueck"] for z in relevant],
               color=spec["farben"][track], width=0.8)
        pos = _stichtags_position(relevant, stichtag) if stichtag else None
        if pos is not None:
            ax.axvline(pos, color="#333333", linewidth=1.0, linestyle="--")
        schritt = max(1, len(x) // 12)
        ax.set_xticks(x[::schritt], labels[::schritt])
        ax.set_ylabel(f"{track_titel} (Jahresende)")
        ax.set_xlabel("Kalenderjahr")
        datei = _speichere(fig, bild(f"{spec['produkt']}_{track}"))

        bloecke.append(
            f"\n### {track_titel}\n\n![{track_titel} je Jahresende]({datei})\n\n"
            f"Bewegung in Stück, {_zeitraum(von, bis_jahr)}:\n\n"
            + _bewegungstabelle(relevant, track, positionen, "stueck", stichtag)
            + f"\n\nBewegung in {spec['bezug']}, {_zeitraum(von, bis_jahr)}, "
            f"in {_einheit_je_tabelle(relevant, track, positionen, 'summe')}:\n\n"
            + _bewegungstabelle(relevant, track, positionen, "summe", stichtag)
        )

    return f"""
## Bestandsbewegung: {spec['titel']}

Struktur nach der BaFin-Nachweisung zur Bestandsbewegung; Bezugsgröße ist
die {spec['bezug']}. {spec['erlaeuterung']} {pruefsatz}

{grundlagen}
{neugeschaeft}
{"".join(bloecke)}"""


def _bewegungstabelle(
    konto: List[Dict[str, Any]],
    track: str,
    positionen,
    mass: str,
    stichtag: Optional[_dt.date],
) -> str:
    """Bewegungstabelle mit gemeinsamer Einheit und Stichtags-Trennzeile."""
    werte_alle = [
        z[track][pos][mass] for z in konto for pos, _t in positionen
    ]
    teiler, einheit, stellen = (
        einheit_fuer(werte_alle) if mass == "summe" else (1.0, "Stück", 0)
    )
    kopf = ["Jahr"] + [titel for _pos, titel in positionen]

    zeilen: List[List[str]] = []
    getrennt = False
    for z in konto:
        if stichtag is not None and not getrennt and z["jahr"] >= stichtag.year:
            zeilen.append(
                [f"**{stichtag.isoformat()}**", "**ab hier Prognose**"]
                + [""] * (len(positionen) - 1)
            )
            getrennt = True
        zeilen.append(
            [str(z["jahr"])]
            + [
                zahl(z[track][pos][mass] / teiler, stellen) if mass == "summe"
                else str(int(z[track][pos][mass]))
                for pos, _t in positionen
            ]
        )
    return _tabelle(kopf, zeilen)


def _einheit_je_tabelle(konto, track, positionen, mass) -> str:
    """Einheit einer Bewegungstabelle (fuer die Einleitungszeile)."""
    if mass != "summe":
        return "Stück"
    return einheit_fuer(
        [z[track][pos][mass] for z in konto for pos, _t in positionen]
    )[1]


def _kennzahlen_md(
    ausw: List[Dict[str, Any]],
    reihe: List[Dict[str, Any]],
    leistung_label: str,
    df: pd.DataFrame,
) -> str:
    """Aktuarielle Kennzahlen je Stichtag (Zehnjahres-Raster)."""
    vs_je_stichtag = {r["stichtag"]: r["summe_vs"] for r in reihe}
    ist_bu = "produkt" in df.columns and set(df["produkt"]) == {"bu"}
    auswahl = [r for r in ausw if int(r["stichtag"][:4]) % 5 == 0]
    if not auswahl:
        auswahl = ausw
    betraege = [
        w for r in auswahl
        for w in (vs_je_stichtag.get(r["stichtag"], 0.0), r["deckungskapital"])
    ]
    teiler, einheit, stellen = einheit_fuer(betraege)
    if ist_bu:
        kopf = ["Stichtag", "Verträge", "im Leistungsbezug",
                f"Σ Jahresrente ({einheit})", f"Σ Deckungskapital ({einheit})"]
        zeilen = [
            [r["stichtag"], str(r["bu_vertraege"]), str(r["bu_leistungsbezug"]),
             zahl(r["bu_jahresrente"] / teiler, stellen),
             zahl(r["deckungskapital"] / teiler, stellen)]
            for r in auswahl
        ]
    else:
        kopf = ["Stichtag", "Verträge", f"Σ {leistung_label} ({einheit})",
                f"Σ Deckungskapital ({einheit})",
                f"davon beitragsfrei ({einheit})",
                f"Σ Rückkaufswert ({einheit})"]
        zeilen = [
            [r["stichtag"], str(r["vertraege"]),
             zahl(vs_je_stichtag.get(r["stichtag"], 0.0) / teiler, stellen),
             zahl(r["deckungskapital"] / teiler, stellen),
             zahl(r["deckungskapital_bfr"] / teiler, stellen),
             zahl(r["rueckkaufswert"] / teiler, stellen)]
            for r in auswahl
        ]
    von, bis = ausw[0]["stichtag"][:4], ausw[-1]["stichtag"][:4]
    return (
        f"\n## Aktuarielle Kennzahlen je Stichtag, {_zeitraum(von, bis)}\n\n"
        + _tabelle(kopf, zeilen)
        + "\n\n" + TEXTE["kennzahlen"]
    )


def _als_markdown(html: str) -> str:
    """Die gemeinsamen Erläuterungs-Bausteine aus HTML in Markdown übernehmen.

    Die Textbausteine (Rechnungsgrundlagen, Zugangs-Annahme) sind für beide
    Ausgabeformen dieselben — hier wird nur das Markup getauscht, damit die
    Aussagen nicht doppelt gepflegt werden müssen.
    """
    if not html:
        return ""
    text = (
        html.replace("<p>", "\n").replace("</p>", "\n")
        .replace("<strong>", "**").replace("</strong>", "**")
        .replace("<ul>", "\n").replace("</ul>", "\n")
        .replace("<li>", "- ").replace("</li>", "\n")
    )
    zeilen = [z.strip() for z in text.splitlines()]
    return "\n".join(z for z in zeilen if z)
