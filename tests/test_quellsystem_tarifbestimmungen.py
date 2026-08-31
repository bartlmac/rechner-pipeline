"""Die Tarifbestimmungen der Quelle: Garantien im Dokument, nicht nur im Code.

Was die Quelle ihren Kunden GARANTIERT hat, muss das aufnehmende
Unternehmen abbilden (Bestandsuebertragung: die Vertraege gehen mit
ihren Bedingungen ueber). Deshalb stehen die beiden Konventionen, die
die Quelle vom Zielsystem unterscheiden, ALS ZUSAGEN im AVB-artigen
Lieferartefakt — und diese Tests halten fest, dass Dokument und
Bestandsfuehrung dasselbe sagen.

Knoten: klv
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.tarifbestimmungen import als_pdf, schreibe  # noqa: E402


def _xml(pfad: Path) -> str:
    return zipfile.ZipFile(pfad).read("word/document.xml").decode("utf-8")


def test_das_dokument_ist_deterministisch(tmp_path):
    """Gleicher Inhalt, gleiche Bytes — sonst wechselte der registrierte
    Hash der Lieferung bei jedem Lauf."""
    a = schreibe(tmp_path / "a.docx").read_bytes()
    b = schreibe(tmp_path / "b.docx").read_bytes()
    assert a == b


def test_die_garantien_stehen_im_dokument(tmp_path):
    """Die zwei Quell-Konventionen sind ZUSAGEN, keine Interna.

    Ziffer 4: Abzug je Versicherungsbaustein gesondert (Grundversicherung
    und jede Erhoehung einzeln). Ziffer 6: Herabsetzung als
    Teilkuendigung der Grundversicherung MIT AUSZAHLUNG. Genau das
    fuehrt die Bestandsfuehrung aus — Dokument und Fuehrung muessen
    dasselbe sagen, sonst liefert die Quelle Bedingungen, die ihr
    eigenes System nicht rechnet.
    """
    xml = _xml(schreibe(tmp_path / "avb.docx"))
    assert "GESONDERT erhoben" in xml
    assert "jede planmaessige Erhoehung je einzeln" in xml
    assert "AUSGEZAHLT" in xml
    assert "Erhoehungen bleiben von der Herabsetzung unberuehrt" in xml
    assert "eigenstaendiger Baustein" in xml


def test_der_formelanhang_traegt_den_meldungsfehler_eins_zu_eins(tmp_path):
    """Anhang A ist die Zeichenerklaerung der Meldung — samt Indexfehler.

    Der gewollte Fehler (Regie F3) steckt NUR in der Doku: N(x) ist als
    Summe ab j=1 statt j=0 definiert, M(x) korrekt; das Rechenwerk (VBA
    wie die Python-Kopie) rechnet richtig. Sein Zweck: Ein Fehler in der
    Tarifmeldung wird nie maschinell "wegentschieden", er erzwingt die
    menschliche Abnahme. Wer ihn im Dokument still repariert, nimmt der
    Vorfuehrung genau diesen Fall.
    """
    xml = _xml(schreibe(tmp_path / "avb.docx"))
    assert "N(x) = Summe von j=1 bis omega-x ueber D(x+j)" in xml
    assert "M(x) = Summe von j=0 bis omega-x ueber C(x+j)" in xml
    # Die stille Reparatur waere j=0 in der N-Zeile:
    assert "N(x) = Summe von j=0" not in xml
    assert "RUNDEN" in xml and "16 Nachkommastellen" in xml
    # Alle sechs Zellen stehen in der Grundlagen-Tabelle.
    for status in ("Nichtraucher", "Raucher"):
        for tarifart in ("Einzel", "Kollektiv", "Haus"):
            assert f"{status} / {tarifart}" in xml


def test_pdf_erzeugung_liefert_ein_pdf(tmp_path):
    import shutil

    if shutil.which("soffice") is None:
        pytest.skip("LibreOffice nicht vorhanden")
    docx = schreibe(tmp_path / "avb.docx")
    pdf = als_pdf(docx, tmp_path)
    inhalt = pdf.read_bytes()
    assert inhalt.startswith(b"%PDF-") and len(inhalt) > 10_000
