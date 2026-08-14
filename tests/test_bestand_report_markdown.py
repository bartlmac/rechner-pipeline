"""Markdown-Ausgabe des Bestandsberichts (Doku-Engine-Pfad).

Derselbe Berichtsinhalt wie die HTML-Form, aber druckgerecht: Beträge je
Tabelle auf eine gemeinsame Einheit skaliert, jede Aggregation mit ihrem
Zeitraum. Die Grafiken werden als PNG neben das Dokument geschrieben.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import List, Tuple

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.report_markdown import einheit_fuer, render_markdown
from rechner_pipeline.toolbox import bestand_report as cli
from rechner_pipeline.bestand.parquet_io import write_portfolio

REPO_ROOT = Path(__file__).resolve().parents[1]
GESAMT = REPO_ROOT / "examples" / "bestand_gesamt.toml"
STICHTAG = dt.date(2026, 1, 1)
BIS = dt.date(2045, 1, 1)


@pytest.fixture(scope="module")
def lauf():
    """Ein Gesamtbestand-Lauf (beide Versicherungsarten)."""
    cfg = load_config(GESAMT)
    basis = generate(cfg, bis=STICHTAG)
    erg = fortschreiben(basis, cfg, BIS, neuzugang_ab=STICHTAG)
    return cfg, mit_zugaengen(basis, erg.zugaenge), erg


def test_einheit_waehlt_die_groebste_lesbare_stufe():
    """Je Tabelle EINE Einheit, gewaehlt nach dem groessten Betrag."""
    assert einheit_fuer([1234.0])[1] == "EUR"
    assert einheit_fuer([25_000.0])[1] == "Tsd. EUR"
    assert einheit_fuer([5_000_000.0])[1] == "Mio. EUR"
    assert einheit_fuer([48_000_000.0])[1] == "Mio. EUR"
    assert einheit_fuer([73_000_000_000.0])[1] == "Mrd. EUR"
    # Der groesste Wert entscheidet fuer die ganze Menge:
    teiler, name, _stellen = einheit_fuer([12.0, 5_000_000.0])
    assert name == "Mio. EUR" and teiler == 1e6
    assert einheit_fuer([])[1] == "EUR"
    assert einheit_fuer([-9_000_000.0])[1] == "Mio. EUR"   # Betrag zaehlt


def test_gesamtbestand_ergibt_einen_bericht_mit_beiden_nachweisungen(lauf, tmp_path):
    cfg, bestand, erg = lauf
    text = render_markdown(
        bestand, bild_dir=tmp_path, bild_praefix="b",
        historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
        config=cfg, bis=BIS, stichtag=STICHTAG,
        titel="Bestandsbericht",
    )
    assert "## Bestandsbewegung: Kapitalversicherung" in text
    assert "## Bestandsbewegung: Berufsunfähigkeit" in text
    # Je Nachweisung beide Traeger-Bestaende:
    for ueberschrift in ("Beitragspflichtiger Bestand", "Beitragsfreier Bestand",
                         "Anwärter", "Leistungsbezieher"):
        assert f"### {ueberschrift}" in text
    # Grafiken liegen als PNG daneben und sind relativ referenziert:
    bilder = sorted(p.name for p in tmp_path.glob("b_*.png"))
    assert len(bilder) >= 8
    for name in re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text):
        assert "/" not in name, name
        assert (tmp_path / name).is_file(), name


def test_aggregationen_nennen_ihren_zeitraum(lauf, tmp_path):
    """Eine Anzahl ohne Zeitraum ist keine Information."""
    cfg, bestand, erg = lauf
    text = render_markdown(
        bestand, bild_dir=tmp_path, historie=erg.historie, ledger=erg.ledger,
        scheiben=erg.scheiben, config=cfg, bis=BIS, stichtag=STICHTAG,
    )
    assert re.search(r"## Geschäftsvorfälle \d{4} bis \d{4}", text)
    assert re.search(r"Bewegung in Stück, \d{4} bis \d{4}", text)
    assert re.search(r"## Aktuarielle Kennzahlen je Stichtag, \d{4} bis \d{4}", text)
    # Der Kopf nennt Berichtszeitraum, Stichtag und Horizont:
    assert re.search(r"- Berichtszeitraum: \d{4} bis \d{4}", text)
    assert f"- Referenzstichtag: {STICHTAG.isoformat()}" in text
    assert f"- Projektionshorizont: {BIS.isoformat()}" in text


def test_betraege_sind_je_tabelle_einheitlich_skaliert(lauf, tmp_path):
    cfg, bestand, erg = lauf
    text = render_markdown(
        bestand, bild_dir=tmp_path, historie=erg.historie, ledger=erg.ledger,
        scheiben=erg.scheiben, config=cfg, bis=BIS, stichtag=STICHTAG,
    )
    # Jede Betragstabelle nennt ihre Einheit:
    assert re.search(r"Bewegung in Versicherungssumme, .*, in (Tsd\.|Mio\.|Mrd\.)? ?EUR", text)
    assert "Summe (" in text   # GeVo-Tabelle
    # Keine unskalierten Riesenzahlen mehr (mehr als 12 Ziffern in einer Zelle):
    for zelle in re.findall(r"\| ([\d.]{13,}) \|", text):
        pytest.fail(f"unskalierter Betrag in der Tabelle: {zelle}")


def test_tabellen_haben_durchgehend_gleiche_spaltenzahl(lauf, tmp_path):
    cfg, bestand, erg = lauf
    zeilen = render_markdown(
        bestand, bild_dir=tmp_path, historie=erg.historie, ledger=erg.ledger,
        scheiben=erg.scheiben, config=cfg, bis=BIS, stichtag=STICHTAG,
    ).splitlines()
    tabellen, i = 0, 0
    while i < len(zeilen):
        if (zeilen[i].startswith("|") and i + 1 < len(zeilen)
                and set(zeilen[i + 1]) <= set("|- ")):
            spalten = zeilen[i].count("|") - 1
            tabellen += 1
            j = i + 2
            while j < len(zeilen) and zeilen[j].startswith("|"):
                assert zeilen[j].count("|") - 1 == spalten, zeilen[j]
                j += 1
            i = j
        else:
            i += 1
    assert tabellen >= 8


def test_stichtag_trennt_auch_im_markdown(lauf, tmp_path):
    cfg, bestand, erg = lauf
    kw = dict(bild_dir=tmp_path, historie=erg.historie, ledger=erg.ledger,
              scheiben=erg.scheiben, config=cfg, bis=BIS)
    mit = render_markdown(bestand, stichtag=STICHTAG, **kw)
    ohne = render_markdown(bestand, **kw)
    assert "ab hier Prognose" in mit
    assert "ab hier Prognose" not in ohne
    # Genau eine Trennstelle je Bewegungstabelle (2 Produkte x 2 Traeger x 2 Masse):
    assert mit.count("ab hier Prognose") == 8


def test_cli_format_md(lauf, tmp_path):
    cfg, bestand, erg = lauf
    pfade = {
        "portfolio": write_portfolio(bestand, tmp_path / "b.parquet"),
        "historie": write_portfolio(erg.historie, tmp_path / "h.parquet"),
        "ledger": write_portfolio(erg.ledger, tmp_path / "l.parquet"),
        "scheiben": write_portfolio(erg.scheiben, tmp_path / "s.parquet"),
    }
    out = tmp_path / "ausgabe" / "bericht.md"
    assert cli.main([
        "--portfolio", str(pfade["portfolio"]), "--historie", str(pfade["historie"]),
        "--ledger", str(pfade["ledger"]), "--scheiben", str(pfade["scheiben"]),
        "--config", str(GESAMT), "--bis", BIS.isoformat(),
        "--stichtag", STICHTAG.isoformat(), "--format", "md", "--out", str(out),
    ]) == 0
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# ")
    # Grafiken liegen neben dem Dokument (Default-Bildverzeichnis):
    assert list(out.parent.glob("bericht_*.png"))
    # --format md ohne --out ist ein Usage-Fehler (die Grafiken brauchen ein Ziel):
    assert cli.main([
        "--portfolio", str(pfade["portfolio"]), "--format", "md",
    ]) == 2


def test_bildpfade_liegen_neben_dem_dokument(lauf, tmp_path):
    """Die Doku-Engine loest relative Bildpfade zur Quelldatei auf — die
    Grafiken muessen also neben dem Markdown liegen und ohne Verzeichnis
    referenziert sein. (Der frueher genutzte externe Renderer fand sie
    nicht, im PDF blieben nur die Bildunterschriften.)"""
    cfg, bestand, erg = lauf
    ziel = tmp_path / "unterordner"
    text = render_markdown(
        bestand, bild_dir=ziel, bild_praefix="bericht",
        historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
        config=cfg, bis=BIS, stichtag=STICHTAG,
    )
    referenzen = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    assert referenzen
    for name in referenzen:
        assert "/" not in name and not name.startswith("."), name
        assert (ziel / name).is_file(), name
    # Jede erzeugte Grafik wird auch referenziert (keine Waisen):
    erzeugt = {p.name for p in ziel.glob("*.png")}
    assert erzeugt == set(referenzen)


# --------------------------------------------------------------------------- #
# Beide Darstellungen zeigen denselben Bericht
# --------------------------------------------------------------------------- #


def _abschnitte_html(html: str) -> List[Tuple[int, str]]:
    return [
        (int(m.group(1)), re.sub(r"<[^>]+>", "", m.group(2)).strip())
        for m in re.finditer(r"<h([23])>(.*?)</h\1>", html, re.S)
    ]


def _abschnitte_md(text: str) -> List[Tuple[int, str]]:
    return [
        (len(m.group(1)) , m.group(2).strip())
        for m in re.finditer(r"^(#{2,3}) (.+)$", text, re.M)
    ]


def test_beide_darstellungen_haben_dieselbe_gliederung(lauf, tmp_path):
    """Kern der Drift-Sicherung: HTML und Markdown sind zwei Darstellungen
    EINES Berichts. Weichen ihre Abschnitte voneinander ab, ist der
    Bericht auseinandergelaufen — genau das ist hier schon passiert und
    soll nicht wieder passieren."""
    from rechner_pipeline.bestand import report

    cfg, bestand, erg = lauf
    kw = dict(historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
              config=cfg, bis=BIS, stichtag=STICHTAG)
    html = report.render_html(bestand, **kw)
    md = render_markdown(bestand, bild_dir=tmp_path, **kw)

    h_titel = [t for _e, t in _abschnitte_html(html)]
    m_titel = [t for _e, t in _abschnitte_md(md)]
    assert h_titel == m_titel, (
        "Abschnitte weichen ab:\n"
        f"  nur HTML: {[t for t in h_titel if t not in m_titel]}\n"
        f"  nur MD:   {[t for t in m_titel if t not in h_titel]}"
    )
    # Auch die Ebenen (h2/h3 gegen ##/###) muessen uebereinstimmen:
    assert _abschnitte_html(html) == _abschnitte_md(md)


def test_struktur_wird_je_versicherungsart_gezeigt(lauf, tmp_path):
    """Eintrittsalter, Laufzeit und versicherte Leistung sind je Art anders
    definiert (Versicherungssumme gegen Jahresrente) — eine gemeinsame
    Darstellung waere nicht lesbar."""
    from rechner_pipeline.bestand import report

    cfg, bestand, erg = lauf
    kw = dict(historie=erg.historie, ledger=erg.ledger, scheiben=erg.scheiben,
              config=cfg, bis=BIS, stichtag=STICHTAG)
    md = render_markdown(bestand, bild_dir=tmp_path, **kw)
    html = report.render_html(bestand, **kw)

    for text in (md, html):
        # Unter der Struktur stehen beide Versicherungsarten als eigene
        # Unterabschnitte:
        assert "Kapitalversicherung" in text and "Berufsunfähigkeit" in text
    # Je Art vier Grafiken (drei Merkmale und die Copula):
    for produkt in ("klv", "bu"):
        bilder = sorted(p.name for p in tmp_path.glob(f"*_{produkt}_*.png"))
        merkmale = [b for b in bilder if "copula" in b or "age" in b
                    or "duration" in b or "insured" in b or "rente" in b]
        assert len(merkmale) == 4, (produkt, bilder)
