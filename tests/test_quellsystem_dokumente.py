"""Die Dokumente der Quelle: AVB und Tarifplan, sauber getrennt.

AVB tragen die ZUSAGEN (was das aufnehmende Unternehmen abbilden muss)
und enthalten KEINE Formel; der Tarifplan (Mitteilung 143) traegt die
Aktuarik — Rechnungsgrundlagen, Kostensaetze, Kommutationsformeln,
Rundungsvorschrift. Diese Tests halten fest, dass Dokumente, Tarifwerk
und Bestandsfuehrung dasselbe sagen — und dass der gewollte
Meldungsfehler drinsteht statt still repariert zu werden.

Knoten: klv
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.dokumente import AVB, TARIFPLAN, als_pdf, text  # noqa: E402
from quellsystem.export import RK  # noqa: E402
from quellsystem.tarifwerk import TAFEL, ZELLEN  # noqa: E402


def _de(zahl: float) -> str:
    return f"{zahl:g}".replace(".", ",")


def test_die_garantien_stehen_in_den_avb():
    """Die Quell-Konventionen sind ZUSAGEN, keine Interna.

    Ziffer 4: Abzug je Versicherungsbaustein gesondert (Grundversicherung
    und jede Erhoehung einzeln). Ziffer 6: Herabsetzung als
    Teilkuendigung der Grundversicherung MIT AUSZAHLUNG. Ziffer 3:
    keine Erhoehung unter fuenf Jahren Restlaufzeit. Genau das fuehrt
    die Bestandsfuehrung aus — Dokument und Fuehrung muessen dasselbe
    sagen, sonst liefert die Quelle Bedingungen, die ihr eigenes System
    nicht rechnet.
    """
    md = text(AVB)
    assert "GESONDERT erhoben" in md
    assert "jede planmäßige Erhöhung je einzeln" in md
    assert "AUSGEZAHLT" in md
    assert "Erhöhungen bleiben von der" in md and "Herabsetzung unberührt" in md
    assert "eigenständiger Baustein" in md
    assert "weniger als fünf Jahre" in md


def test_die_avb_sind_formelfrei():
    """AVB sind Bedingungen, kein Rechenwerk: keine Formeln, keine
    Zahlentabellen — die Aktuarik steht im Tarifplan, auf den die AVB
    verweisen."""
    md = text(AVB)
    assert "Tarifplan" in md and "Mitteilung 143" in md
    rumpf = md.split("```{=typst}")[-1].split("```", 1)[-1]
    assert "```" not in rumpf, "AVB brauchen keine Formelbloecke"
    assert not [z for z in rumpf.splitlines() if z.startswith("|")], (
        "AVB brauchen keine Tabellen")
    for zeichen in ("B(x,t)", "N(x)", "D(x)", "RUNDEN"):
        assert zeichen not in md, f"Formelzeichen {zeichen} gehoert nicht in AVB"


def test_der_tarifplan_traegt_den_meldungsfehler_eins_zu_eins():
    """Die Grundformeln sind die Zeichenerklaerung der Meldung — samt
    Indexfehler.

    Der gewollte Fehler (Regie F3) steckt NUR in der Doku: N(x) ist als
    Summe ab j=1 statt j=0 definiert, M(x) korrekt; das Rechenwerk (VBA
    wie die Python-Kopie) rechnet richtig. Sein Zweck: Ein Fehler in der
    Tarifmeldung wird nie maschinell "wegentschieden", er erzwingt die
    menschliche Abnahme. Wer ihn im Dokument still repariert, nimmt der
    Vorfuehrung genau diesen Fall.
    """
    md = text(TARIFPLAN)
    assert "N(x) = Summe von j=1 bis omega-x über D(x+j)" in md
    assert "M(x) = Summe von j=0 bis omega-x über C(x+j)" in md
    assert "N(x) = Summe von j=0" not in md


def test_die_rundung_steht_als_eigener_abschnitt_statt_in_den_formeln():
    """Beschluss 2026-09-01: kein RUNDEN(...)-Wrapper in den Formeln;
    die Rundungslogik wird einmal woertlich erklaert. Die Pins nennen
    genau das, was das Rechenwerk tut (konventionen.excel_round in der
    Kommutation, Cent erst in der Ausgabe, Buchen centgenau)."""
    md = text(TARIFPLAN)
    assert "RUNDEN" not in md
    assert "## 5. Rundung" in md
    assert "16 Nachkommastellen" in md
    assert "halb weg von null" in md
    assert "ungerundet" in md
    assert "auf den Cent" in md and "centgenau" in md


def test_die_kostentabellen_tragen_das_tarifwerk():
    """Tarifplan-Tabellen und tarifwerk.ZELLEN muessen deckungsgleich
    sein. Die Textquelle ist von Hand editierbar — genau deshalb braucht
    sie einen Waechter gegen das Auseinanderlaufen mit dem Rechenwerk.

    Die Doku-Struktur (eine Tabelle je Bestandsgruppe, Tafel nur nach
    Raucherstatus) setzt voraus, dass die Kosten NICHT vom Raucherstatus
    abhaengen — das wird hier mitgeprueft, nicht nur angenommen.
    """
    for tarifart in ("Einzel", "Kollektiv", "Haus"):
        nr = ZELLEN[("Nichtraucher", tarifart)]
        r = ZELLEN[("Raucher", tarifart)]
        for feld in ("alpha", "beta1", "gamma1", "gamma2", "gamma3",
                     "policy_fee", "stoab_satz", "stoab_min", "stoab_max",
                     "ratzu", "zins", "zillmer_dauer"):
            assert getattr(nr, feld) == getattr(r, feld), (
                f"{tarifart}.{feld}: Kosten haengen doch am Raucherstatus "
                "— dann stimmt die Tabellenstruktur des Tarifplans nicht")

    md = text(TARIFPLAN)
    for status, tafel in TAFEL.items():
        assert f"| {RK[status]} ({status}) | {tafel} |" in md
    assert "1,25 %" in md  # Tarifzins

    for tarifart in ("Einzel", "Kollektiv", "Haus"):
        zelle = ZELLEN[("Nichtraucher", tarifart)]
        segment = md.split(f"Bestandsgruppe {tarifart}:")[1].split(
            "\n## ")[0].split("Bestandsgruppe ")[0]
        assert f"| {_de(zelle.alpha * 1000)} Promille |" in segment
        # Baldrian meldet die Inkassokosten in PROMILLE (Regie-
        # Umbenennung A1.2; identische Werte, andere Einheit als die
        # PLV-Spez sie fuehrt — F2 vergleicht Excel gegen diese Zahl).
        assert f"| {_de(zelle.beta1 * 1000)} Promille |" in segment
        for g in (zelle.gamma1, zelle.gamma2, zelle.gamma3):
            assert f"| {_de(g * 1000)} Promille |" in segment
        assert f"{zelle.policy_fee:.2f}".replace(".", ",") + " EUR" in segment
        if zelle.stoab_satz:
            assert f"| {_de(zelle.stoab_satz * 100)} % |" in segment
            assert f"{zelle.stoab_min:.2f}".replace(".", ",") in segment
            assert f"{zelle.stoab_max:.2f}".replace(".", ",") in segment
            for zw in (2, 4, 12):
                assert f"| {_de(zelle.ratzu[zw] * 100)} % |" in segment
        else:
            assert segment.count("entfällt") == 2


def test_der_tarifplan_spricht_baldrian():
    """Die Meldung spricht die Sprache der QUELLE, nicht die der PLV.

    Die Sprachdifferenz ist Vorfuehr-Substanz (Regie-Umbenennungen):
    Tarifzins statt Rechnungszins, Risikoklasse statt Raucherstatus,
    Erlebensfallsumme statt Versicherungssumme — der Transformations-
    Skill muss die Semantik erkennen, nicht Woerter abgleichen. Dazu
    die zwei Konventionssaetze, aus denen die Migration Code ableitet:
    das Kalenderjahres-Alter (M1) und der Jahrestagswert des DECKKAP
    (die Quelle interpoliert nicht).
    """
    md = text(TARIFPLAN)
    assert "Tarifzins" in md
    assert "Rechnungszins" not in md
    assert "Risikoklasse" in md and "Raucherstatus" not in md
    assert "je Einheit Erlebensfallsumme" in md
    assert "Kalenderjahre von Versicherungsbeginn und Geburt" in md
    assert "## 6. Bestandsabzug" in md
    assert "letzten Vertragsjahrestag" in md and "interpoliert nicht" in md


def test_die_optik_ist_schreibmaschine():
    """Frontmatter und Typst-Vorspann setzen den Altsystem-Look:
    Monospace, Absatzabstand genau eine Leerzeile, Ueberschriften in
    Textgroesse."""
    for md_pfad in (AVB, TARIFPLAN):
        md = text(md_pfad)
        assert md.startswith("---")
        assert "DejaVu Sans Mono" in md.split("---")[1]
        assert "```{=typst}" in md
        assert "#set par(leading: 0.65em, justify: false)" in md
        assert "#set text(hyphenate: false)" in md
        assert "#show par: set block(spacing: 1.65em)" in md
        assert "#show heading: set text(size: 9.5pt)" in md
        # Die Gegenregel zum Codeblock-Grau der Engine: Formeln stehen
        # als Schreibmaschinentext im Fluss, nicht in einem Kasten.
        assert "#show raw.where(block: true): set block(fill: none" in md


def test_pdfs_rendern_ueber_die_doku_engine(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker (Doku-Engine) nicht vorhanden")
    for md, name in ((AVB, "AVB_KLV_TG2015.pdf"),
                     (TARIFPLAN, "Mitteilung_143_KLV_TG2015.pdf")):
        pdf = als_pdf(md, tmp_path / name)
        inhalt = pdf.read_bytes()
        assert inhalt.startswith(b"%PDF-") and len(inhalt) > 10_000
        assert b"DejaVuSansMono" in inhalt, "der Schreibmaschinen-Font fehlt"
