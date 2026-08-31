"""Die Tarifbestimmungen der Quelle — das AVB-artige Lieferartefakt.

Was der Vertrag GARANTIERT, steht nicht im Rechenkern, sondern in den
Tarifbestimmungen — und bei einer Bestandsuebertragung gehen die
Vertraege MIT ihren Bedingungen ueber: Das aufnehmende Unternehmen muss
abbilden, was hier zugesagt ist. Deshalb gehoert dieses Dokument in die
Lieferung (als PDF), und deshalb stehen die beiden Konventionen, die die
Quelle vom Zielsystem unterscheiden, HIER als Garantien:

* Rueckkauf: Stornoabzug **je Versicherungsbaustein** (Grundversicherung
  und jede Dynamik-Erhoehung gesondert, mit Mindest- und Hoechstbetrag
  je Baustein).
* Herabsetzung: **Teilkuendigung der Grundversicherung mit Auszahlung**
  des freiwerdenden Deckungskapitals abzueglich des anteiligen
  Stornoabzugs; Erhoehungen bleiben unberuehrt.

Der Formelanhang uebernimmt die Zeichenerklaerung der Tarifmeldung
(Abschnitt "A.2 Zusammenstellung der Bezeichnungen und Grundformeln")
**eins zu eins — einschliesslich ihres Indexfehlers**: Die
Kommutationszahl N_x ist dort als Summe ab j=1 statt j=0 definiert
(M_x korrekt). Der Fehler steckt NUR in der Doku; das Rechenwerk (VBA
wie die Python-Kopie) rechnet korrekt. Regie: MANIPULATIONEN.md F3 —
ein Fehler in der Tarifmeldung wird nie maschinell "wegentschieden",
er erzwingt die menschliche Abnahme. Das Dokument stellt ihn deshalb
kommentarlos dar; wer ihn hier still "repariert", nimmt der Vorfuehrung
den Fall.

PDF-Erzeugung ueber LibreOffice (headless). Das PDF ist NICHT
byte-deterministisch (Erzeugungs-Metadaten); massgeblich ist der Hash
des EINMAL erzeugten, registrierten Artefakts — Wiederholbarkeit liefert
die Versionierung der Lieferung, nicht die Re-Konvertierung.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Tuple

from quellsystem.docx import Block, schreibe_docx
from quellsystem.tarifwerk import ZELLEN


def _zellen_tabelle() -> List[List[str]]:
    zeilen = [[
        "Zelle", "Sterbetafel", "Rechnungszins", "Abschlusskosten (alpha)",
        "Inkassokosten (beta1)", "Verwaltung (gamma1/2/3)",
        "Stueckkosten p. a.",
    ]]
    for (status, tarifart), z in sorted(ZELLEN.items()):
        zeilen.append([
            f"{status} / {tarifart}", z.tafel,
            f"{z.zins * 100:.2f} %".replace(".", ","),
            f"{z.alpha * 1000:.0f} promille", f"{z.beta1 * 100:.1f} %".replace(".", ","),
            f"{z.gamma1}/{z.gamma2}/{z.gamma3}",
            f"{z.policy_fee:.2f} EUR".replace(".", ","),
        ])
    return zeilen


def bloecke() -> List[Block]:
    b: List[Block] = [
        ("titel", "Allgemeine Tarifbestimmungen"),
        ("absatz", "Kapitallebensversicherung nach Tarifwerk KLV TG2015 — "
                   "Baldrian Lebensversicherung a. G."),
        ("absatz", "Fassung Januar 2015. Diese Bestimmungen gelten fuer "
                   "alle ab dem 1. Januar 2015 nach Tarifwerk TG2015 "
                   "geschlossenen Versicherungen."),

        ("ueberschrift", "1. Versicherungsformen und Rechnungsgrundlagen"),
        ("absatz", "Der Tarif wird in sechs Ausgestaltungen gefuehrt "
                   "(Raucherstatus, Vertriebsweg). Fuer jede Ausgestaltung "
                   "gelten die folgenden Rechnungsgrundlagen:"),
        ("tabelle", _zellen_tabelle()),
        ("absatz", "Beitragszuschlaege bei unterjaehriger Zahlweise sowie "
                   "Mindest- und Hoechstbetraege des Abzugs nach Ziffer 4 "
                   "ergeben sich aus dem Tarifblatt der jeweiligen "
                   "Ausgestaltung."),

        ("ueberschrift", "2. Beitraege"),
        ("absatz", "Der Jahresbeitrag ergibt sich aus der "
                   "Versicherungssumme und dem tariflichen Beitragssatz "
                   "B(x,t) nach Anhang B. Bei unterjaehriger Zahlweise wird "
                   "der Jahresbeitrag zuzueglich Stueckkosten durch die "
                   "Zahl der Raten geteilt und um den Ratenzuschlag "
                   "erhoeht."),

        ("ueberschrift", "3. Planmaessige Erhoehungen (Dynamik)"),
        ("absatz", "Vereinbarte planmaessige Erhoehungen erhoehen die "
                   "Versicherungssumme ohne erneute Gesundheitspruefung. "
                   "Jede Erhoehung wird versicherungstechnisch als "
                   "eigenstaendiger Baustein gefuehrt: mit dem bei "
                   "Wirksamwerden erreichten Alter, der restlichen "
                   "Versicherungs- und Beitragszahlungsdauer und eigener "
                   "Wertermittlung nach Anhang A."),

        ("ueberschrift", "4. Rueckkauf und Abzug"),
        ("absatz", "Bei Kuendigung erstatten wir den Zeitwert der "
                   "Versicherung abzueglich eines Abzugs. Der Abzug "
                   "betraegt 0,5 % der Differenz aus Versicherungssumme "
                   "und Deckungskapital, mindestens jedoch den im "
                   "Tarifblatt genannten Mindestbetrag und hoechstens den "
                   "dort genannten Hoechstbetrag."),
        ("absatz", "Der Abzug wird fuer jeden Versicherungsbaustein "
                   "GESONDERT erhoben: fuer die Grundversicherung und fuer "
                   "jede planmaessige Erhoehung je einzeln, jeweils mit "
                   "Mindest- und Hoechstbetrag. Der Rueckkaufswert der "
                   "Versicherung ist die Summe der Rueckkaufswerte ihrer "
                   "Bausteine."),

        ("ueberschrift", "5. Beitragsfreistellung"),
        ("absatz", "Auf Verlangen wird die Versicherung beitragsfrei "
                   "gestellt. Die beitragsfreie Versicherungssumme wird "
                   "je Baustein zum letzten Jahrestag des "
                   "Versicherungsbeginns ermittelt (Anhang B) und ab "
                   "diesem Zeitpunkt fest gefuehrt."),

        ("ueberschrift", "6. Herabsetzung der Beitraege (Teilkuendigung)"),
        ("absatz", "Verlangt der Versicherungsnehmer eine Herabsetzung "
                   "des Beitrags, wird die Grundversicherung anteilig "
                   "gekuendigt: Die Versicherungssumme der "
                   "Grundversicherung wird auf den fortgefuehrten Anteil "
                   "herabgesetzt, und das freiwerdende Deckungskapital "
                   "wird nach Abzug des anteiligen Abzugs gemaess "
                   "Ziffer 4 AUSGEZAHLT. Planmaessige Erhoehungen bleiben "
                   "von der Herabsetzung unberuehrt; das Recht auf "
                   "kuenftige Erhoehungen bleibt bestehen."),

        ("ueberschrift", "Anhang A: Zusammenstellung der Bezeichnungen "
                        "und Grundformeln"),
        ("absatz", "Die Wertermittlung erfolgt nach der "
                   "Kommutationsmethode. Ausgehend von der jeweiligen "
                   "Sterbetafel q(x) und dem Rechnungszins i mit "
                   "v = 1/(1+i) werden gebildet (RUNDEN bezeichnet die "
                   "kaufmaennische Rundung auf 16 Nachkommastellen; "
                   "Hoechstalter omega = 123):"),
        ("absatz", "l(0) = 1.000.000;  "
                   "l(x+1) = RUNDEN( l(x) * (1 - q(x)) );  "
                   "T(x) = RUNDEN( l(x) - l(x+1) )"),
        ("absatz", "D(x) = RUNDEN( l(x) * v^x );  "
                   "C(x) = RUNDEN( T(x) * v^(x+1) )"),
        ("absatz", "N(x) = Summe von j=1 bis omega-x ueber D(x+j)"),
        ("absatz", "M(x) = Summe von j=0 bis omega-x ueber C(x+j)"),

        ("ueberschrift", "Anhang B: Barwerte und Beitragssatz"),
        ("absatz", "Temporaere vorschuessige Rente (jaehrlich): "
                   "ax:n = ( N(x) - N(x+n) ) / D(x). Bei k Zahlungen im "
                   "Jahr vermindert um das Abzugsglied "
                   "AG(k) * ( 1 - D(x+n)/D(x) ) mit "
                   "AG(k) = (1+i)/k * Summe( (s/k) / (1 + (s/k)*i) ) "
                   "fuer s = 0, ..., k-1."),
        ("absatz", "Todesfallbarwert: nAx = ( M(x) - M(x+n) ) / D(x); "
                   "Erlebensfallbarwert: nEx = D(x+n) / D(x)."),
        ("absatz", "Beitragssatz je Einheit Versicherungssumme: "
                   "B(x,t) = ( nAx + nEx + gamma1 * ax:t "
                   "+ gamma2 * (ax:n - ax:t) ) "
                   "/ ( (1 - beta1) * ax:t - alpha * t )."),
    ]
    return b


def schreibe(ziel: Path) -> Path:
    """Die Tarifbestimmungen als deterministisches DOCX."""
    return schreibe_docx(Path(ziel), bloecke())


def als_pdf(docx_pfad: Path, ziel_dir: Path) -> Path:
    """DOCX -> PDF ueber LibreOffice (headless).

    Nicht byte-deterministisch; massgeblich ist der registrierte Hash des
    einmal erzeugten Artefakts (siehe Modul-Docstring).
    """
    ziel_dir = Path(ziel_dir)
    ziel_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf",
         "--outdir", str(ziel_dir), str(docx_pfad)],
        check=True, capture_output=True, timeout=120,
    )
    pdf = ziel_dir / (Path(docx_pfad).stem + ".pdf")
    if not pdf.is_file():
        raise FileNotFoundError(f"LibreOffice hat kein PDF erzeugt: {pdf}")
    return pdf
