"""Gliederung und Textbausteine des Bestandsberichts.

Überschriften, Reihenfolge und Erläuterungen stehen hier und nicht im
Renderer: der Bericht ist eine fachliche Aussage, das HTML nur seine
Darstellung. Wer den Aufbau ändern will, ändert :data:`ABSCHNITTE` und
:data:`TEXTE` — nicht das Markup.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

#: Reihenfolge und Überschriften der Abschnitte. Der Bericht führt vom
#: Bestand über seine Struktur zu Bewegung, Geschäftsvorfällen und
#: Bewertung.
ABSCHNITTE: Tuple[Tuple[str, str], ...] = (
    ("verlauf", "Bestandsverlauf"),
    ("struktur", "Bestandsstruktur"),
    ("bewegung", "Bestandsbewegung"),          # je Versicherungsart erweitert
    ("gevo", "Geschäftsvorfälle"),
    ("kennzahlen", "Aktuarielle Kennzahlen"),
    ("lesart", "Zur Lesart"),
)

#: Klartext-Bausteine. Platzhalter in geschweiften Klammern werden von den
#: Renderern gefüllt; Markup steht hier bewusst nicht.
TEXTE: Dict[str, str] = {
    "verlauf": (
        "In-force-Bestand je Stichtag, gestapelt nach Tarifgeneration. "
        "Abgänge (Storno, Tod, Ablauf) verlassen den Bestand am Buchungstag; "
        "Zugänge treten mit ihrem Versicherungsbeginn ein. Die Vertragszahl "
        "ist die des Gesamtbestands; das versicherte Volumen steht je "
        "Versicherungsart getrennt, weil Versicherungssumme und Jahresrente "
        "nicht addierbar sind."
    ),
    "struktur": (
        "Die Struktur wird je Versicherungsart getrennt gezeigt: "
        "Eintrittsalter, Laufzeit und versicherte Leistung sind je Art "
        "anders definiert und in einer gemeinsamen Darstellung nicht "
        "vergleichbar. Die Merkmale sind nicht unabhängig gezogen — eine "
        "Gauß-Copula bildet die konfigurierten Rangkorrelationen ab."
    ),
    "gevo": (
        "Die Anzahl ist die Summe über den gesamten Berichtszeitraum "
        "({zeitraum}), kein Jahreswert. Die Bezugsgröße des Betrags "
        "unterscheidet sich je Geschäftsvorfall und Versicherungsart; "
        "Beträge verschiedener Bezugsgrößen stehen deshalb getrennt. "
        "Der Zugang enthält auch die Verträge des Ausgangsbestands — mit "
        "ihrem Versicherungsbeginn als Zugangszeitpunkt, wie im "
        "Bewegungskonto. Sonst begänne die Zugangsreihe erst beim "
        "simulierten Neugeschäft, während alle Abgänge über den ganzen "
        "Zeitraum ausgewiesen sind."
    ),
    "kennzahlen": (
        "Stichtagswerte, keine Zeitraum-Aggregate: Bestand und Reserven am "
        "jeweiligen Stichtag, gerechnet aus dem stabilen Rechenkern."
    ),
    "beitraege": (
        "Stichtagswerte des laufenden Beitrags, keine Zeitraum-Summen. "
        "Zwei Größen werden unterschieden: der Σ Jahresbeitrag ist der "
        "tarifliche Bruttobeitrag für ein Jahr (BJB), das Σ "
        "Beitragsvolumen p. a. ist der tatsächlich gezahlte Betrag eines "
        "Jahres — also einschließlich Ratenzuschlag für unterjährige "
        "Zahlweise und Stückkosten (BZB mal Zahlweise). Beim "
        "BU-Beispielprodukt fallen beide zusammen: es kennt weder "
        "unterjährige Zahlweise noch Stückkosten. Nicht enthalten sind "
        "Verträge, die keinen Beitrag mehr zahlen: beitragsfrei gestellte "
        "(PEX), solche mit abgelaufener Beitragszahlungsdauer und "
        "BU-Verträge im Leistungsbezug (Beitragsbefreiung). Beiträge sind "
        "über die Versicherungsarten addierbar — anders als die "
        "versicherten Leistungen."
    ),
    "lesart": (
        "Aggregierte Zahlen beziehen sich auf den im Abschnittstitel "
        "genannten Zeitraum; Stichtagswerte sind als solche gekennzeichnet. "
        "Zwei Daten steuern den Bericht: der Simulationshorizont (wie weit "
        "Geschäftsvorfälle gerechnet sind) und der Referenzstichtag (die "
        "Grenze zwischen Historie und Prognose, in allen Zeitachsen als "
        "gestrichelte Linie). Alle Diagramme enden am Simulationshorizont — "
        "jenseits davon sind Tod und Storno nicht gerechnet, eine Kurve "
        "dort wäre keine Prognose, sondern eine Überzeichnung des Bestands. "
        "Rechts der Stichtagslinie ist alles Projektion desselben Modells. "
        "Das Rendering ist deterministisch: dieselben Eingabedateien ergeben "
        "denselben Bericht."
    ),
    "lesart_betraege": (
        "Beträge sind je Tabelle auf eine gemeinsame Einheit skaliert; die "
        "Einheit steht in der Einleitungszeile oder im Spaltenkopf."
    ),
    "stichtag": (
        "Der Referenzstichtag trennt den beobachteten Bestandsaufbau "
        "(Historie) von der Projektion (Prognose). Beide Teile entstehen im "
        "selben Modell — der Unterschied ist nicht „gegeben gegen gerechnet“, "
        "sondern Bestandsaufbau gegen Projektion."
    ),
}


def kopfzeilen(
    df: pd.DataFrame,
    generationen: List[str],
    stichtage: List[_dt.date],
    stichtag: Optional[_dt.date],
    bis: Optional[_dt.date],
    quelle_hash: Optional[str] = None,
) -> List[str]:
    """Die Kopfangaben des Berichts (Klartext, ohne Markup).

    Die Vertragszahl ist die Zeilenzahl der Datei, also die ganze
    Kohorte einschließlich längst abgegangener Verträge — nicht der
    In-force-Bestand eines Stichtags. Der steht je Stichtag im
    Bestandsverlauf und in den aktuariellen Kennzahlen.
    """
    zeilen = [
        f"Verträge in der Datei (Kohorte inkl. Abgängen): {len(df)}",
        f"Tarifgenerationen: {', '.join(generationen)}",
        f"Berichtszeitraum: {stichtage[0].year} bis {stichtage[-1].year}",
    ]
    if stichtag is not None:
        zeilen.append(
            f"Referenzstichtag: {stichtag.isoformat()} — bis dahin Historie, "
            "danach Prognose"
        )
    if bis is not None:
        zeilen.append(f"Projektionshorizont: {bis.isoformat()}")
    if quelle_hash:
        zeilen.append(f"Quelle (Parquet-Hash): {quelle_hash[:8]}…")
    return zeilen


#: Die Struktur-Merkmale je Versicherungsart. Die Leistungsspalte
#: unterscheidet sich (Versicherungssumme gegen Jahresrente) — deshalb wird
#: die Struktur je Art gezeigt und nicht über den Gesamtbestand.
STRUKTUR_MERKMALE: Tuple[Tuple[str, str], ...] = (
    ("age", "Alter am Stichtag"),
    ("duration", "Laufzeit (Jahre)"),
    ("leistung", "versicherte Leistung"),
)


def produkt_gruppen(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Die Versicherungsarten des Bestands mit ihren Merkmalen.

    Liefert je Art Bezeichnung, Filter, Leistungsspalte und deren Label —
    die Grundlage für alle produktweisen Darstellungen. Ein Bestand ohne
    Produkt-Spalte gilt als reine Kapitalversicherung (Altbestand).
    """
    from rechner_pipeline.models.bestand import LEISTUNGSSPALTE

    bezeichnungen = {"klv": "Kapitalversicherung", "bu": "Berufsunfähigkeit"}
    leistungs_label = {
        "klv": "Versicherungssumme", "bu": "versicherte Jahresrente",
    }
    if "produkt" not in df.columns:
        vorhanden = ["klv"]
    else:
        vorhanden = [p for p in ("klv", "bu") if (df["produkt"] == p).any()]
    return [
        {
            "produkt": p,
            "titel": bezeichnungen[p],
            "leistung": LEISTUNGSSPALTE[p],
            "leistung_label": leistungs_label[p],
        }
        for p in vorhanden
    ]


def teilbestand(df: pd.DataFrame, produkt: str) -> pd.DataFrame:
    """Zeilen einer Versicherungsart (Bestand ohne Produkt-Spalte: alles)."""
    if "produkt" not in df.columns:
        return df
    return df[df["produkt"] == produkt]
