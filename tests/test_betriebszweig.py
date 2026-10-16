"""Was der Workflow von plv-fiktion aus dem Zweig betrieb nimmt (werkzeuge/betriebszweig.py),
und der Workflow selbst (plv/seite/.github/workflows/seite.yml).

Weg C (Entscheid des Maintainers 09.10.2026): Automatisch aendert sich nur
``betrieb/``. Der Zweig traegt genau, was die Routine ablegt; ausserhalb von
``betrieb/`` gleicht der gebaute Baum dem Rahmen aus main. Der Workflow
liefert nur aus main aus, startet nicht bei einem Push auf betrieb und
pinnt jede Action auf einen Commit.

Knoten: system/betrieb
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "werkzeuge"))

import betriebszweig as bz  # noqa: E402

WORKFLOW = ROOT / "plv" / "seite" / ".github" / "workflows" / "seite.yml"


def _zweig(wurzel: Path) -> Path:
    paket = wurzel / "paket"
    paket.mkdir(parents=True)
    (paket / "stand.json").write_text(json.dumps({"dateien": {
        "index.html": "a" * 64, "protokoll.jsonl": "b" * 64, "laufmanifest.json": "c" * 64,
        "tagesjournal.parquet": "d" * 64, "abschluesse/abschluss_2026-10-01.parquet": "e" * 64}}),
        encoding="utf-8")
    for name in ("index.html", "protokoll.jsonl", "laufmanifest.json"):
        (paket / name).write_text("x", encoding="utf-8")
    (wurzel / "anker.jsonl").write_text("{}\n", encoding="utf-8")
    (wurzel / "A-B1.json").write_text("{}", encoding="utf-8")
    (wurzel / ".git").mkdir()
    (wurzel / ".git" / "HEAD").write_text("ref: refs/heads/betrieb\n", encoding="utf-8")
    return wurzel


@pytest.mark.parametrize("anlegen, befund", [
    (lambda z: (z / ".github" / "workflows").mkdir(parents=True)
     or (z / ".github" / "workflows" / "x.yml").write_text("on: push", encoding="utf-8"),
     ".github/workflows/x.yml: ein Workflow-Verzeichnis im Zweig betrieb"),
    (lambda z: (z / "paket" / ".github").mkdir()
     or (z / "paket" / ".github" / "a").write_text("", encoding="utf-8"),
     "paket/.github/a: ein Workflow-Verzeichnis im Zweig betrieb"),
    (lambda z: (z / "README.md").write_text("", encoding="utf-8"), "README.md: nicht erlaubt"),
    (lambda z: (z / "paket" / "tagesjournal.parquet").write_bytes(b"PAR1"),
     "paket/tagesjournal.parquet: keine oeffentliche Datei des Pakets"),
    (lambda z: (z / "paket" / "abschluesse").mkdir()
     or (z / "paket" / "abschluesse" / "abschluss_2026-10-01.parquet").write_bytes(b"PAR1"),
     "paket/abschluesse/abschluss_2026-10-01.parquet: nicht erlaubt (das Paket liegt flach unter paket/)"),
    (lambda z: (z / "paket" / "fremd.html").write_text("", encoding="utf-8"),
     "paket/fremd.html: steht nicht in stand.json"),
    (lambda z: (z / "A-B1.json").unlink(), "A-B1.json: fehlt"),
    (lambda z: (z / "paket" / "link.html").symlink_to(z / "paket" / "index.html"),
     "paket/link.html: ein Symlink"),
])
def test_im_zweig_betrieb_liegt_nur_was_die_routine_ablegt(tmp_path, anlegen, befund):
    """Positivkontrolle zuerst: Was die Routine ablegt (paket/ ohne Parquet,
    anker.jsonl, A-B1.json), geht durch, das .git des Checkouts zaehlt nicht.
    Jede Abweichung ist ein Befund, der die Auslieferung anhaelt."""
    zweig = _zweig(tmp_path / "zweig")
    assert bz.zweig(zweig) == []
    anlegen(zweig)
    assert befund in bz.zweig(zweig)
    assert bz.main(["zweig", str(zweig)]) == 1


@pytest.mark.parametrize("name", ["Bericht.html", "bericht(1).html", "bericht 1.html",
                                  'bericht"1.html', "bericht<b>.html", "berichtä.html"])
def test_ein_dateiname_im_paket_hat_nur_a_z_0_9_und_unterstrich_punkt_strich(tmp_path, name):
    """Der Name geht als Verweis in die Seite (Entscheid des Maintainers
    16.10.2026). Positivkontrolle: Ein Name aus allen erlaubten Zeichen geht
    durch. Die Abschluesse, die stand.json mit Schraegstrich nennt, sind kein
    Befund, denn geprueft werden die Dateien im Zweig. Ein fremdes Zeichen
    ist ein Befund, auch wenn stand.json den Namen nennt."""
    zweig = _zweig(tmp_path / "zweig")
    stand = json.loads((zweig / "paket" / "stand.json").read_text(encoding="utf-8"))
    for n in ("bestandsbericht_2026-01-01_teil-9.html", name):
        stand["dateien"][n] = "f" * 64
        (zweig / "paket" / "stand.json").write_text(json.dumps(stand), encoding="utf-8")
        (zweig / "paket" / n).write_text("x", encoding="utf-8")
        if n != name:
            assert bz.zweig(zweig) == []
    assert bz.zweig(zweig) == [f"paket/{name}: Dateiname mit anderen Zeichen als a-z, 0-9, _ . -"]
    assert bz.main(["zweig", str(zweig)]) == 1


#: Ein Bericht, wie der Tagesbetrieb ihn schreibt: Grafik als SVG mit Verweisen
#: auf sich selbst, ein Verweis auf einen anderen Bericht, Namensraeume mit
#: http-Adressen, Stylesheet, eine Adresse im Text. Nichts davon ist ein Befund.
BERICHT = """<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Bestandsbericht</title>
<style>table { border-collapse: collapse } td.zahl { text-align: right }</style></head>
<body><h1>Bestandsbericht</h1><p>Quelle der Daten: https://example.org, Stand online.</p>
<p><a href="../berichte/bestandsbericht_2026-01-01.html">Vormonat</a></p>
<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" version="1.1">
<metadata><rdf:RDF><cc:Work><dc:type rdf:resource="http://purl.org/dc/dcmitype/StillImage"/>
</cc:Work></rdf:RDF></metadata><defs><style type="text/css">*{stroke-linejoin: round}</style>
<path id="m1" d="M 0 0 L 1 1"/><clipPath id="p1"><rect x="0" y="0" width="1" height="1"/></clipPath></defs>
<g clip-path="url(#p1)"><use xlink:href="#m1" x="1" y="2" style="fill: #2f5d62"/></g></svg>
FUSS</body></html>
"""


@pytest.mark.parametrize("schnipsel, befund", [
    ("<script>alert(1)</script>", "<script>"),
    ("<SCRIPT SRC=x.js></SCRIPT>", "<script>"),
    ("<img src=x.png onerror=alert(1)>", "Attribut onerror"),
    ('<img src="x.png"onerror="alert(1)">', "Attribut onerror"),
    ("<svg onload=alert(1)></svg>", "Attribut onload"),
    ('<a href="javascript:alert(1)">x</a>', "javascript:"),
    ('<a href="java&#115;cript&colon;alert(1)">x</a>', "javascript:"),
    ('<a href="java\tscript:alert(1)">x</a>', "javascript:"),
    ("<iframe src=x.html></iframe>", "<iframe>"),
    ("<object data=x></object>", "<object>"),
    ("<embed src=x>", "<embed>"),
    ("<form action=x><button>x</button></form>", "<form>"),
    ("<base href=../>", "<base>"),
    ('<meta http-equiv="Refresh" content="0; url=../">', "meta refresh"),
    ('<img src="https://example.org/x.png">', "src=https://example.org/x.png (von aussen)"),
    ('<img src="//example.org/x.png">', "src=//example.org/x.png (von aussen)"),
    ('<img src="&#104;ttps://example.org/x.png">', "src=https://example.org/x.png (von aussen)"),
    ('<img src="\x01https://example.org/x.png">', "src=\x01https://example.org/x.png (von aussen)"),
    ('<img src="&NewLine;https://example.org/x.png">', "src=https://example.org/x.png (von aussen)"),
    ('<img src="/&Tab;/example.org/x.png">', "src=//example.org/x.png (von aussen)"),
    ('<img src="ht\ttps://example.org/x.png">', "src=https://example.org/x.png (von aussen)"),
    ('<img srcset="a.png 1x, https://example.org/b.png 2x">', "srcset=https://example.org/b.png (von aussen)"),
    ('<img src="data:image/png;base64,AAAA">', "src=data:image/png (von aussen)"),
    ('<link rel="stylesheet" href="https://example.org/s.css">', "href=https://example.org/s.css (von aussen)"),
    ('<link rel=preload as=image href=a.png imagesrcset="https://example.org/x.png 1x">',
     "imagesrcset=https://example.org/x.png (von aussen)"),
    ('<img src="a.png" attributionsrc="https://example.org/r">', "attributionsrc=https://example.org/r (von aussen)"),
    ('<svg><use xlink:href="https://example.org/s.svg#a"/></svg>', "xlink:href=https://example.org/s.svg#a (von aussen)"),
    ('<a href="https://example.org/">nach aussen</a>', "href=https://example.org/ (von aussen)"),
    ('<svg><animate attributeName="href" to="https://example.org/x"/></svg>', "to=https://example.org/x (von aussen)"),
    ('<div style="background: url(https://example.org/x.png)">x</div>', "url(https://example.org/x.png) (von aussen)"),
    ("<style>@import 'zusatz.css';</style>", "@import"),
    ("<p style=\"background: image-set('x.png' 1x)\">x</p>", "image-set("),
    ("<style>p { background: \\75 rl(x.png) }</style>", "\\"),
    # Ein Parser, der anders liest als der Browser: Der Kommentar endet fuer den
    # Browser bei --!>, im SVG ist <style> kein reiner Text.
    ("<!-- --!><img src=x onerror=alert(1)> -->", "Attribut onerror"),
    ('<svg><style><img src="https://example.org/x"></style></svg>', "src=https://example.org/x (von aussen)"),
])
def test_ein_html_des_pakets_ist_ohne_skript_und_laedt_nichts_von_aussen(tmp_path, schnipsel, befund):
    """Die HTML-Dateien des Pakets gehen byteweise auf die Seite; was darin
    steht, schreibt ein Server, nicht dieser Code (Entscheid des Maintainers
    16.10.2026, Weg 1: der Workflow prueft, statt neu zu rendern).
    Positivkontrolle: ein Bericht, wie der Tagesbetrieb ihn schreibt, ist ohne
    Befund. Mit einem Schnipsel darin haelt der Zweig an."""
    zweig = _zweig(tmp_path / "zweig")
    bericht = zweig / "paket" / "index.html"
    bericht.write_text(BERICHT.replace("FUSS", ""), encoding="utf-8")
    assert bz.zweig(zweig) == []
    bericht.write_text(BERICHT.replace("FUSS", schnipsel), encoding="utf-8")
    assert f"paket/index.html: {befund}" in bz.zweig(zweig)
    assert bz.main(["zweig", str(zweig)]) == 1


#: Jedes Attribut, das eine Adresse traegt: die Endungen src, srcset und href
#: an Beispielen, dazu jeder Einzelname aus betriebszweig.
ADRESS_ATTRIBUTE = ("src", "srcset", "href", "xlink:href", "imagesrcset", "attributionsrc",
                    *bz._ADRESS_ATTRIBUTE)
#: Was im Browser zwei Attribute trennt; "" heisst: direkt nach einem Wert in
#: Anfuehrungszeichen.
TRENNER = (" ", "\t", "\n", "\r", "\f", "/", "")


def test_jede_adresse_von_aussen_wird_gefunden_wie_der_browser_die_attribute_trennt():
    """Der Browser zerlegt die Attribute im Rohtext. Zeichenreferenzen loest
    er erst im Wert auf, Tab und Zeilenumbruch streicht er erst in der
    Adresse (Befund B8 der Pruefung durch merge-session, 16.10.2026: Mit
    <img\\nsrc=...> und einem &quot; im vorigen Wert lud Chromium von aussen,
    und die Pruefung meldete nichts). Gekreuzt: jedes Adress-Attribut, klein
    und gross geschrieben, nach jedem Trenner, mit und ohne ein &quot; im
    vorigen Wert, das wie dasselbe Attribut aussieht, und zwei Adressen von
    aussen. Positivkontrolle: dieselben Schnipsel mit einer Adresse im Paket
    sind ohne Befund."""
    abweichend = []
    for name in ADRESS_ATTRIBUTE:
        for schreibung in (name, name.upper()):
            for trenner in TRENNER:
                for vorher in ('<img a="1"', f'<img alt="&quot;{name}="'):
                    for adresse, von_aussen in (("https://example.org/x", True),
                                                ("//example.org/x", True), ("bericht.html", False)):
                        schnipsel = f'{vorher}{trenner}{schreibung}="{adresse}">'
                        befunde = bz.html_befunde(BERICHT.replace("FUSS", schnipsel))
                        if befunde != ([f"{name}={adresse} (von aussen)"] if von_aussen else []):
                            abweichend.append((schnipsel, befunde))
    assert abweichend == [], f"{len(abweichend)} Abweichungen, zuerst {abweichend[:3]}"


def test_ein_html_des_pakets_ist_utf_8(tmp_path):
    zweig = _zweig(tmp_path / "zweig")
    (zweig / "paket" / "index.html").write_bytes("<p>Bestand zum 1. März</p>".encode("latin-1"))
    assert bz.zweig(zweig) == ["paket/index.html: nicht in UTF-8"]


def test_ein_befund_bleibt_eine_zeile_im_protokoll(tmp_path, capsys):
    """Befunde tragen Namen und Werte aus dem Zweig. Ein Zeilenumbruch darin
    beginnt keine Zeile im Protokoll des Workflows, die der Runner als Befehl
    (``::…``) laese."""
    zweig = _zweig(tmp_path / "zweig")
    (zweig / "paket" / "x\n::error::y.html").write_text("x", encoding="utf-8")
    assert bz.main(["zweig", str(zweig)]) == 1
    zeilen = capsys.readouterr().out.splitlines()
    assert not [z for z in zeilen if z.startswith("::")], zeilen
    assert any("paket/x\\x0a::error::y.html" in z for z in zeilen), zeilen


@pytest.mark.parametrize("name, inhalt", [
    ("index.html", "---\npermalink: /neu/\n---\n<p>x</p>\n"),
    ("index.html", "﻿---\npermalink: /neu/\n---\n<p>x</p>\n"),
    ("laufmanifest.json", "---\npermalink: /neu.json\n---\n{}\n"),
    ("protokoll.jsonl", "---\n---\n{}\n"),
])
def test_keine_datei_des_pakets_hat_einen_vorspann(tmp_path, name, inhalt):
    """Mit einem Vorspann gaebe Pages die Datei durch Jekyll: Liquid liefe, und
    permalink legte sie an eine Adresse ausserhalb von betrieb/. Die Pruefung
    rahmen saehe das nicht, sie laeuft vor Jekyll (gemessen mit
    jekyll-build-pages v1.0.13 am 16.10.2026: /neu/ entstand). Positivkontrolle:
    drei Striche im Inneren der Datei sind kein Vorspann."""
    zweig = _zweig(tmp_path / "zweig")
    datei = zweig / "paket" / name
    datei.write_text("<p>Bestand</p>\n---\n" if name.endswith(".html") else "{}\n---\n",
                     encoding="utf-8")
    assert bz.zweig(zweig) == []
    datei.write_text(inhalt, encoding="utf-8")
    assert f"paket/{name}: beginnt mit einem Vorspann (---), Jekyll verarbeitete die Datei" \
        in bz.zweig(zweig)


def test_ausserhalb_von_betrieb_gleicht_der_baum_dem_rahmen(tmp_path):
    """Nur betrieb/ darf der Bau des Abends schreiben. Eine geaenderte, eine
    neue und eine fehlende Datei des Rahmens sind je ein Befund; ein Ordner
    betrieb/ im Rahmen selbst auch (den Betriebsteil baut nur der Workflow)."""
    rahmen, seite = tmp_path / "rahmen", tmp_path / "seite"
    for wurzel in (rahmen, seite):
        (wurzel / "it").mkdir(parents=True)
        (wurzel / "index.md").write_text("# Start\n", encoding="utf-8")
        (wurzel / "it" / "index.md").write_text("# IT\n", encoding="utf-8")
    (rahmen / ".git").mkdir()
    (rahmen / ".git" / "HEAD").write_text("x", encoding="utf-8")
    (seite / "betrieb").mkdir()
    (seite / "betrieb" / "index.md").write_text("# Bestandsführung\n", encoding="utf-8")
    assert bz.rahmen(rahmen, seite) == []
    (seite / "index.md").write_text("# Start, nachts geaendert\n", encoding="utf-8")
    (seite / "neu.html").write_text("", encoding="utf-8")
    (seite / "it" / "index.md").unlink()
    assert bz.rahmen(rahmen, seite) == [
        "it/index.md: im Rahmen, nicht im gebauten Baum",
        "neu.html: im gebauten Baum, nicht im Rahmen",
        "index.md: anders als im Rahmen"]
    (rahmen / "betrieb").mkdir()
    assert bz.rahmen(rahmen, seite)[0].startswith("betrieb/ liegt schon im Rahmen")


def _abschnitt(text: str, kopf: str) -> str:
    """Der Block unter einer Zeile ``kopf`` bis zur naechsten Zeile gleicher
    oder geringerer Einrueckung. Gelesen wird der Text: PyYAML ist keine
    Abhaengigkeit des Repositorys."""
    zeilen = text.splitlines()
    start = next(i for i, z in enumerate(zeilen) if z.rstrip() == kopf)
    tiefe = len(kopf) - len(kopf.lstrip())
    block = []
    for z in zeilen[start + 1:]:
        if z.strip() and not z.lstrip().startswith("#") and len(z) - len(z.lstrip()) <= tiefe:
            break
        block.append(z)
    return "\n".join(block)


def test_der_workflow_startet_nie_bei_einem_push_auf_betrieb():
    text = WORKFLOW.read_text(encoding="utf-8")
    ausloeser = _abschnitt(text, "on:")
    assert re.search(r"^  push:\n    branches: \[main\]$", ausloeser, re.M), ausloeser
    assert re.findall(r"^  (\w+):", ausloeser, re.M) == ["push", "workflow_dispatch", "schedule"]
    assert len(re.findall(r"^    - cron:", ausloeser, re.M)) >= 2, "GitHub laesst Zeitplaene aus"


def test_ausgeliefert_wird_nur_aus_main_und_nur_nach_dem_bau():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _abschnitt(text, "permissions:").strip() == "contents: read"
    auslieferung = _abschnitt(text, "  veroeffentlichen:")
    assert "    needs: bauen" in auslieferung
    assert "    if: github.ref == 'refs/heads/main'" in auslieferung
    assert re.sub(r"\s+", " ", _abschnitt(auslieferung, "    permissions:")).strip() == \
        "pages: write id-token: write"
    assert "permissions" not in _abschnitt(text, "  bauen:")


def test_jede_action_ist_auf_einen_commit_gepinnt():
    """Ein Tag laesst sich verschieben, ein Commit nicht. jekyll-build-pages
    auf dem lokal gemessenen Stand v1.0.13."""
    text = WORKFLOW.read_text(encoding="utf-8")
    verwendet = re.findall(r"uses:\s*(\S+)", text)
    assert verwendet and all(re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", u) for u in verwendet), verwendet
    assert re.search(r"jekyll-build-pages@44a6e6beabd48582f863aeeb6cb2151cc1716697\s+# v1\.0\.13", text)


def test_der_workflow_baut_den_betriebsteil_mit_den_pruefungen():
    """Die Schritte, die der Plan verlangt, in dieser Folge: Allowlist des
    Zweigs, der Betriebsteil ohne Fall aus dem oeffentlichen Paket (die
    Seitenpruefung faehrt auftritt.py mit), der Vergleich mit dem Rahmen, erst
    dann Jekyll. Der Code kommt aus CODESTAND; python-markdown in der
    gemessenen Fassung; kein Checkout behaelt seine Zugangsdaten."""
    text = WORKFLOW.read_text(encoding="utf-8")
    bau = _abschnitt(text, "  bauen:")
    folge = ["betriebszweig.py zweig zweig", "auftritt.py --teil betrieb",
             "betriebszweig.py rahmen rahmen seite", "jekyll-build-pages@"]
    stellen = [bau.index(f) for f in folge]
    assert stellen == sorted(stellen), folge
    for teil in ("--oeffentliches-paket", "--ab1 zweig/A-B1.json", "--anker zweig/anker.jsonl",
                 "--stands-paket zweig/paket", "--vorschau", "markdown==3.4.1"):
        assert teil in bau, teil
    assert re.search(r"repository: bartlmac/rechner-pipeline\n\s+ref: \$\{\{ steps\.code\.outputs\.stand \}\}", bau)
    checkouts = bau.count("uses: actions/checkout@")
    assert checkouts == 3 and bau.count("persist-credentials: false") == checkouts
