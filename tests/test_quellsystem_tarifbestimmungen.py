"""Die Tarifbestimmungen der Quelle: Garantien im Dokument, nicht nur im Code.

Was die Quelle ihren Kunden GARANTIERT hat, muss das aufnehmende
Unternehmen abbilden (Bestandsuebertragung: die Vertraege gehen mit
ihren Bedingungen ueber). Die Markdown-Quelle ist massgeblich; diese
Tests halten fest, dass Dokument, Tarifwerk und Bestandsfuehrung
dasselbe sagen — und dass der gewollte Meldungsfehler drinsteht statt
still repariert zu werden.

Knoten: klv
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from quellsystem.tarifbestimmungen import als_pdf, quelle, text  # noqa: E402
from quellsystem.tarifwerk import ZELLEN  # noqa: E402


def test_die_garantien_stehen_im_dokument():
    """Die zwei Quell-Konventionen sind ZUSAGEN, keine Interna.

    Ziffer 4: Abzug je Versicherungsbaustein gesondert (Grundversicherung
    und jede Erhoehung einzeln). Ziffer 6: Herabsetzung als
    Teilkuendigung der Grundversicherung MIT AUSZAHLUNG. Genau das
    fuehrt die Bestandsfuehrung aus — Dokument und Fuehrung muessen
    dasselbe sagen, sonst liefert die Quelle Bedingungen, die ihr
    eigenes System nicht rechnet.
    """
    md = text()
    assert "GESONDERT erhoben" in md
    assert "jede planmäßige Erhöhung je einzeln" in md
    assert "AUSGEZAHLT" in md
    assert "Erhöhungen bleiben von der" in md and "Herabsetzung unberührt" in md
    assert "eigenständiger Baustein" in md


def test_der_formelanhang_traegt_den_meldungsfehler_eins_zu_eins():
    """Anhang A ist die Zeichenerklaerung der Meldung — samt Indexfehler.

    Der gewollte Fehler (Regie F3) steckt NUR in der Doku: N(x) ist als
    Summe ab j=1 statt j=0 definiert, M(x) korrekt; das Rechenwerk (VBA
    wie die Python-Kopie) rechnet richtig. Sein Zweck: Ein Fehler in der
    Tarifmeldung wird nie maschinell "wegentschieden", er erzwingt die
    menschliche Abnahme. Wer ihn im Dokument still repariert, nimmt der
    Vorfuehrung genau diesen Fall.
    """
    md = text()
    assert "N(x) = Summe von j=1 bis omega-x über D(x+j)" in md
    assert "M(x) = Summe von j=0 bis omega-x über C(x+j)" in md
    assert "N(x) = Summe von j=0" not in md
    assert "RUNDEN" in md and "16 Nachkommastellen" in md


def test_die_grundlagen_tabelle_traegt_das_tarifwerk():
    """Markdown-Tabelle und tarifwerk.ZELLEN muessen deckungsgleich sein.

    Die Textquelle ist von Hand editierbar — genau deshalb braucht sie
    einen Waechter gegen das Auseinanderlaufen mit dem Rechenwerk.
    """
    md = text()
    zeilen = [z for z in md.splitlines()
              if z.startswith("|") and " / " in z]
    assert len(zeilen) == len(ZELLEN) == 6
    for (status, tarifart), zelle in sorted(ZELLEN.items()):
        passend = [z for z in zeilen if f"{status} / {tarifart}" in z]
        assert len(passend) == 1, f"Zeile fuer {status}/{tarifart}"
        zeile = passend[0]
        assert zelle.tafel in zeile
        assert "1,25" in zeile
        assert f"{zelle.alpha * 1000:.0f} Promille" in zeile
        assert (f"{zelle.gamma1}/{zelle.gamma2}/{zelle.gamma3}"
                in zeile.replace(" ", ""))


def test_die_optik_ist_schreibmaschine():
    """Frontmatter setzt den Altsystem-Look — Monospace, analog gerendert."""
    md = text()
    assert md.startswith("---")
    assert "DejaVu Sans Mono" in md.split("---")[1]


def test_pdf_rendert_ueber_die_doku_engine(tmp_path):
    if shutil.which("docker") is None:
        pytest.skip("Docker (Doku-Engine) nicht vorhanden")
    pdf = als_pdf(tmp_path / "Tarifbestimmungen_KLV_TG2015.pdf")
    inhalt = pdf.read_bytes()
    assert inhalt.startswith(b"%PDF-") and len(inhalt) > 10_000
    assert b"DejaVuSansMono" in inhalt, "der Schreibmaschinen-Font fehlt"
    assert quelle().suffix == ".md"
