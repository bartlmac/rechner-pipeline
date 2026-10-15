"""Die Pruefung der gebauten Seite (werkzeuge/seitenpruefung.py) — jede
Pruefung mit Treffer und ohne, damit kein Detektor blind gruen bleibt.

Bis zum 08.10.2026 lagen diese Pruefungen nur im Arbeitsordner der
Seiten-Sitzung (Entscheid des Maintainers 04.10.2026: nach ``werkzeuge/``,
damit jede Veroeffentlichung sie faehrt). Die Breite auf dem Telefon braucht
Playwright und ist hier nicht abgedeckt — Werkstattausruestung wie
``schau.py``.

Knoten: klv
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "werkzeuge"))

import auftritt as at  # noqa: E402
import seitenpruefung as sp  # noqa: E402


def _sha(daten: bytes) -> str:
    return hashlib.sha256(daten).hexdigest()


def _schreibe(pfad: Path, inhalt) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(inhalt, bytes):
        pfad.write_bytes(inhalt)
    else:
        pfad.write_text(inhalt, encoding="utf-8")


def test_verweise_findet_tote_ziele_fehlende_sprungziele_und_absolute_pfade(tmp_path: Path):
    """Auch hinter einem Verzeichnis-Symlink: Die Vorschau verlinkt Teile der
    Seite so, und ``rglob`` folgt ihnen nicht."""
    v = tmp_path / "vorschau"
    _schreibe(v / "a.html", '<h2 id="da">A</h2>')
    _schreibe(v / "bild.svg", "<svg/>")
    _schreibe(v / "unter" / "index.html", "unter")
    _schreibe(tmp_path / "echt" / "s.html", '<a href="nix.html">x</a>')
    (v / "teil").symlink_to(tmp_path / "echt", target_is_directory=True)
    sauber = ('<a href="a.html">a</a> <a href="a.html#da">da</a> <img src="bild.svg"> '
              '<a href="unter/">u</a> <a href="https://example.org/x">e</a> <a href="#oben">o</a>'
              '<span id="oben"></span><video poster="bild.svg"></video>')
    _schreibe(v / "index.html", sauber)
    befunde, zusammen = sp.verweise(v)
    assert befunde == ["teil/s.html: nix.html — kein Ziel"], befunde
    assert "extern: {'example.org': 1}" in zusammen

    _schreibe(v / "index.html", sauber + '<a href="a.html#fehlt">f</a> <a href="b.html">b</a> '
              '<a href="/abs.html">abs</a> <video poster="weg.jpg"></video>')
    befunde, _ = sp.verweise(v)
    assert sorted(befunde) == sorted([
        "index.html: /abs.html — absoluter Pfad",
        "index.html: weg.jpg — kein Ziel",
        "index.html: a.html#fehlt — kein Sprungziel",
        "index.html: b.html — kein Ziel",
        "teil/s.html: nix.html — kein Ziel"])


def test_verweise_liest_einfache_anfuehrungszeichen_und_belege_sind_ein_hinweis(tmp_path: Path):
    """Bis 08.10.2026 las die Pruefung nur href="...": Zwei tote Verweise im
    Bericht der Migrationsabnahme (href='...') blieben ungesehen. Ein toter
    Verweis in einem Beleg (artefakte/, betrieb/plv/) ist ein Hinweis: Belege
    erscheinen unveraendert; auf der eigenen Seite bleibt er ein Befund."""
    v = tmp_path / "vorschau"
    _schreibe(v / "a.html", "<h2 id='da'>A</h2>")
    _schreibe(v / "index.html", "<a href='a.html#da'>da</a> <a href='weg.html'>w</a>")
    _schreibe(v / "migrationen" / "f" / "artefakte" / "bericht.html", "<a href='abgeleitet/x.html'>x</a>")
    _schreibe(v / "betrieb" / "plv" / "index.html", '<a href="fehlt.html">f</a>')
    befunde, zusammen = sp.verweise(v)
    assert befunde == ["index.html: weg.html — kein Ziel"], befunde
    assert "in Belegen ohne Ziel: 2" in zusammen
    assert "HINWEIS migrationen/f/artefakte/bericht.html: abgeleitet/x.html — kein Ziel" in zusammen


def test_eine_weiterleitung_ist_eine_seite_des_auftritts_kein_beleg(tmp_path: Path):
    """Der Bericht der Migrationsabnahme verweist vom Fallordner aus; dort, wohin
    der Browser den Verweis aufloest, liegt eine Weiterleitung, die das Manifest
    nennt. Dann zeigt kein Verweis eines Belegs ins Leere. Zeigt die
    Weiterleitung selbst ins Leere, ist das ein Befund, kein Hinweis; das Ziel
    eines meta refresh zaehlt wie ein Verweis."""
    v = tmp_path / "vorschau"
    a = v / "migrationen" / "f" / "artefakte"
    _schreibe(a / "abgeleitet" / "berichte" / "bericht.html", "<a href='abgeleitet/berichte/x.html'>x</a>")
    _schreibe(a / "abgeleitet" / "berichte" / "x.html", "<p>x</p>")
    weiter = a / "abgeleitet" / "berichte" / "abgeleitet" / "berichte" / "x.html"
    _schreibe(weiter, '<meta http-equiv="refresh" content="0; url=../../x.html"><a href="../../x.html">w</a>')
    _schreibe(a / "bereinigung.json", json.dumps({"weiterleitungen": [
        {"datei": "artefakte/abgeleitet/berichte/abgeleitet/berichte/x.html", "ziel": "../../x.html"}]}))
    befunde, zusammen = sp.verweise(v)
    assert befunde == [] and "in Belegen ohne Ziel: 0" in zusammen, (befunde, zusammen)
    _schreibe(weiter, '<meta http-equiv="refresh" content="0; url=../../weg.html">')
    befunde, zusammen = sp.verweise(v)
    assert befunde == ["migrationen/f/artefakte/abgeleitet/berichte/abgeleitet/berichte/x.html: "
                       "../../weg.html — kein Ziel"], befunde


def test_pages_findet_was_pages_anders_liest_als_die_vorschau(tmp_path: Path):
    """Gemessen mit dem Renderer von Pages am 08.10.2026: kramdown zeigt
    ``{: #x }`` am Ende einer Ueberschrift als Text, Liquid bricht an einem
    ``{{`` den Build ab, und ``$...$`` ist fuer kramdown Text. ``{#x}``, raw und
    ``$$...$$`` lesen beide gleich; Code zaehlt fuer Ueberschriften und
    Formeln nicht, fuer Liquid schon."""
    seite = tmp_path / "seite"
    _schreibe(seite / "index.md",
              "# Start\n\n## Über uns {#ueber-uns}\n\n```\n## Beispiel {: #x }\n$y$\n```\n\n"
              '<script>window.MathJax={tex:{inlineMath:[["$","$"]]}};</script>\n\n'
              "{% raw %}\nFormel $$\\frac{{}_{a}V}{b}$$ und `$HOME/$PFAD`\n{% endraw %}\n"
              "Ausserhalb von raw: `$a$` und ``x $b$ y``\n")
    assert sp.pages(seite)[0] == []
    _schreibe(seite / "unter" / "a.md",
              "## Über uns {: #ueber-uns }\n### Weiter {:.klasse}\n\nFormel $x_1$\n\n"
              "\\frac{{}_{a}V}{b}\n\n```\n{% include x %}\n```\n")
    befunde, _ = sp.pages(seite)
    assert [b.split(" — ")[0] for b in befunde] == [
        "unter/a.md:1: ## Über uns {: #ueber-uns }", "unter/a.md:2: ### Weiter {:.klasse}",
        "unter/a.md:6: {{ ausserhalb von raw", "unter/a.md:9: {% ausserhalb von raw",
        "unter/a.md:4: $ ausserhalb von Code und $$...$$ ('Formel $x_1$')",
        "unter/a.md:4: $ ausserhalb von Code und $$...$$ ('Formel $x_1$')"], befunde


def test_pages_zaehlt_jedes_dollar_auch_ueber_einen_zeilenumbruch(tmp_path: Path):
    """Drei Formeln im KLV-Tarifplan liefen ueber einen Zeilenumbruch und gingen
    am Import vorbei (bis 09.10.2026); eine Pruefung, die nur $...$ in einer
    Zeile suchte, sah sie nicht. Gezaehlt wird jedes $ ausserhalb von Code,
    Skript und $$...$$, auch einer $$-Formel ueber Zeilen."""
    seite = tmp_path / "seite"
    _schreibe(seite / "a.md", "# A\n\n$$a\n= b$$ und `$x$`\n\n```\n$y\n```\n")
    assert sp.pages(seite)[0] == []
    _schreibe(seite / "b.md", "# B\n\nDie Summe $f \\cdot\nS_i$ zuzueglich.\n")
    befunde, zusammen = sp.pages(seite)
    assert [b.split(" (")[0] for b in befunde] == [
        "b.md:3: $ ausserhalb von Code und $$...$$", "b.md:4: $ ausserhalb von Code und $$...$$"], befunde


def test_pages_verlangt_einen_titel_und_kein_markdown_in_belegen(tmp_path: Path):
    """Gemessen mit dem Renderer von Pages: Ohne Ueberschrift am Anfang hat eine
    Seite keinen Titel (jekyll-titles-from-headings, 38 Seiten bis 08.10.2026),
    und eine .md unter artefakte/ oder betrieb/plv/ wird zur Seite, ihr Original
    verschwindet (remove_originals, 09.10.2026)."""
    seite = tmp_path / "seite"
    _schreibe(seite / "a.md", "# Titel\n\n<nav class=\"kopf\"></nav>\n")
    _schreibe(seite / "b.md", "\n### Dritte Ebene genuegt\n")
    _schreibe(seite / "c.md", "---\nlayout: default\ntitle: Aus dem Vorspann\n---\nText\n")
    _schreibe(seite / "migrationen" / "f" / "artefakte" / "x.txt", "Lieferung als Text\n")
    assert sp.pages(seite)[0] == []
    _schreibe(seite / "d.md", '<nav class="kopf"></nav>\n\n# Titel danach\n')
    _schreibe(seite / "e.md", "#### Vierte Ebene\n")
    _schreibe(seite / "migrationen" / "f" / "artefakte" / "notiz.md", "# Notiz\n")
    _schreibe(seite / "betrieb" / "plv" / "probe.md", "# Probe\n")
    befunde, _ = sp.pages(seite)
    assert [b.split(" — ")[0].split(":")[0] for b in befunde] == [
        "betrieb/plv/probe.md", "d.md", "e.md", "migrationen/f/artefakte/notiz.md"], befunde


def test_ein_sprung_auf_eine_fehlende_ueberschrift_bleibt_ein_befund(tmp_path: Path):
    """Gegenprobe zu den ids, die die Vorschau den Ueberschriften gibt (wie
    Pages): Sprungziele auf vorhandene Ueberschriften tragen, auch mit Umlaut,
    eigener id oder Formel im Titel; ein Sprung auf eine Ueberschrift, die es
    nicht gibt, bleibt ein Befund. Gerendert wird wie im Bau: vorschau.py mit
    dem System-python3 und seinem python3-markdown."""
    if subprocess.run(["python3", "-c", "import markdown"], capture_output=True).returncode:
        pytest.skip("python3-markdown fehlt im System-python3")
    seite = tmp_path / "seite"
    _schreibe(seite / "assets" / "stil.css", "")
    _schreibe(seite / "index.md", "# Glossar\n\n### T-Box\n\n### Schlüssel\n\n### Über uns {#ueber-uns}\n\n"
              "### Barwert zu $t_a$\n\n[T-Box](#t-box), [Schlüssel](#schlüssel), [wir](#ueber-uns), "
              "[Barwert](#barwert-zu-t_a), [Ebene](#ebene)\n")
    lauf = subprocess.run(["python3", str(ROOT / "werkzeuge" / "vorschau.py"), "--seite", str(seite),
                           "--out", str(tmp_path / "vorschau")], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    befunde, _ = sp.verweise(tmp_path / "vorschau")
    assert befunde == ["index.html: #ebene — kein Sprungziel"], befunde


def test_die_vorschau_liest_raw_und_formeln_wie_pages(tmp_path: Path):
    """Liquid nimmt raw heraus, kramdown gibt $$...$$ im Text als \\(...\\) und als
    eigenen Absatz abgesetzt an MathJax, HTML-maskiert. Die Vorschau tut
    dasselbe; sonst saehe die Sichtung anders aus als die Seite."""
    if subprocess.run(["python3", "-c", "import markdown"], capture_output=True).returncode:
        pytest.skip("python3-markdown fehlt im System-python3")
    seite = tmp_path / "seite"
    _schreibe(seite / "index.md", "# Start\n\n{% raw %}\nIm Text $$k<j$$ und $$\\{1, 2\\}$$.\n\n"
              "$$\nV = \\frac{{}_{a}V}{b}\n$$\n\n$$x_0$$ beginnt den Absatz.\n\n{% endraw %}\n")
    lauf = subprocess.run(["python3", str(ROOT / "werkzeuge" / "vorschau.py"), "--seite", str(seite),
                           "--out", str(tmp_path / "vorschau")], capture_output=True, text=True)
    assert lauf.returncode == 0, lauf.stderr
    html = (tmp_path / "vorschau" / "index.html").read_text(encoding="utf-8")
    assert "raw" not in html
    assert "Im Text \\(k&lt;j\\) und \\(\\{1, 2\\}\\)." in html
    assert "$$\nV = \\frac{{}_{a}V}{b}\n$$" in html
    assert "\\(x_0\\) beginnt den Absatz." in html


def _paket_und_seite(tmp_path: Path):
    paket = tmp_path / "paket"
    dateien = {"index.html": _sha(b"A"), "abschluesse/abschluss_2026-10-01.parquet": _sha(b"P"),
               "bestandsbericht_2026-10-01.html": _sha(b"B")}
    _schreibe(paket / "stand.json", json.dumps({"dateien": dateien}))
    seite = tmp_path / "seite"
    _schreibe(seite / "betrieb" / "plv" / "index.html", b"A")
    _schreibe(seite / "betrieb" / "plv" / "bestandsbericht_2026-10-01.html", b"B")
    _schreibe(seite / "betrieb" / "berichte" / "bestandsbericht_2026-10-01.html", b"B")
    return seite, paket


def test_paket_haelt_plv_und_berichte_gegen_stand_json(tmp_path: Path):
    """Ohne Befund, wenn nur die Parquet-Tabellen fehlen; jede der vier
    Abweichungen ist ein Befund."""
    seite, paket = _paket_und_seite(tmp_path / "gut")
    befunde, zusammen = sp.paket(seite, paket)
    assert befunde == [] and "2 Dateien gleich stand.json, 1 nicht veroeffentlicht" in zusammen

    def mutiert(name, wie):
        s, p = _paket_und_seite(tmp_path / name)
        wie(s)
        return sp.paket(s, p)[0]

    plv = Path("betrieb") / "plv"
    assert mutiert("abweichend", lambda s: (s / plv / "index.html").write_bytes(b"X")) == [
        "betrieb/plv/index.html: weicht von stand.json ab"]
    assert mutiert("fremd", lambda s: (s / plv / "fremd.txt").write_bytes(b"F")) == [
        "betrieb/plv/fremd.txt: ohne Eintrag in stand.json"]
    assert mutiert("fehlt", lambda s: (s / plv / "index.html").unlink()) == [
        "betrieb/plv/index.html: in stand.json, aber nicht veroeffentlicht"]
    assert mutiert("kopie", lambda s: (s / "betrieb" / "berichte" / "bestandsbericht_2026-10-01.html")
                   .write_bytes(b"Y")) == [
        "betrieb/berichte/bestandsbericht_2026-10-01.html: keine bytegleiche Datei des Pakets"]


def test_pruefsummen_ordnet_jede_angezeigte_kennung_einer_quelle_zu(tmp_path: Path):
    """Eine Kennung aus dem Paket ist zugeordnet; eine Kennung ohne Quelle ist
    ein Befund. Nicht gezaehlt: Farben, reine Ziffern, die Belege selbst."""
    bekannt = "ab12cd34ef56" + "0" * 52
    seite, fall = tmp_path / "seite", tmp_path / "fall"
    (fall / "entscheide").mkdir(parents=True)
    _schreibe(fall / "eingang.json", json.dumps({"quellen": []}))
    paket = tmp_path / "paket"
    _schreibe(paket / "stand.json", json.dumps({"provenienz": {"manifest_sha256": bekannt}}))
    anker = tmp_path / "anker.jsonl"
    _schreibe(anker, json.dumps({"stand": "2026-10-08"}) + "\n")
    daten = tmp_path / "falldaten.json"
    _schreibe(daten, json.dumps({"belegkette": {"dateien": {}}}))
    _schreibe(seite / "index.md", "Manifest ab12cd34ef56, Police 12345678, Farbe "
              "<span style=\"color:#deadbe\">x</span>\n")
    _schreibe(seite / "betrieb" / "plv" / "index.html", "deadbeef99 im Beleg selbst")
    argumente = (seite, fall, "probe", paket, anker, daten, tmp_path)
    befunde, zusammen = sp.pruefsummen(*argumente)
    assert befunde == [] and "'Paket': 1" in zusammen

    _schreibe(seite / "index.md", "Manifest ab12cd34ef56 und deadbeef99\n")
    befunde, _ = sp.pruefsummen(*argumente)
    assert befunde == ["index.md: deadbeef99 — ohne Quelle"]


def test_ohne_fall_prueft_pruefsummen_nur_den_betriebsteil(tmp_path: Path):
    """Im Workflow von plv-fiktion gibt es keinen Fall: Gelesen wird nur
    betrieb/, mit Paket, Anker und A-B1 als Quellen. Eine Kennung im Rahmen
    zaehlt dort nicht (den Rahmen prueft der Bau des Pull Requests); eine
    Kennung im Betriebsteil ohne Quelle bleibt ein Befund, eine aus der A-B1
    ist zugeordnet."""
    seite, paket, anker = tmp_path / "seite", tmp_path / "paket", tmp_path / "anker.jsonl"
    _schreibe(paket / "stand.json", json.dumps({"stand": "2026-10-08"}))
    _schreibe(anker, json.dumps({"stand": "2026-10-08"}) + "\n")
    ab1 = tmp_path / "A-B1.json"
    _schreibe(ab1, json.dumps({"snapshot_sha256": "f1c48698" + "1" * 56}))
    _schreibe(seite / "index.md", "Im Rahmen cafe0123beef, ohne Quelle\n")
    _schreibe(seite / "betrieb" / "index.md", "Abnahme f1c48698\n")
    argumente = (seite, None, None, paket, anker, None, tmp_path, ab1)
    befunde, zusammen = sp.pruefsummen(*argumente)
    assert befunde == [] and "Snapshot': 1" in zusammen, (befunde, zusammen)
    _schreibe(seite / "betrieb" / "index.md", "Abnahme f1c48698 und cafe0123beef\n")
    assert sp.pruefsummen(*argumente)[0] == ["betrieb/index.md: cafe0123beef — ohne Quelle"]
    # Gegenprobe: mit Fall zaehlt auch der Rahmen.
    fall = tmp_path / "fall"
    (fall / "entscheide").mkdir(parents=True)
    daten = tmp_path / "falldaten.json"
    _schreibe(daten, json.dumps({"belegkette": {"dateien": {}}}))
    befunde, _ = sp.pruefsummen(seite, fall, "probe", paket, anker, daten, tmp_path, ab1)
    assert sorted(befunde) == ["betrieb/index.md: cafe0123beef — ohne Quelle",
                               "index.md: cafe0123beef — ohne Quelle"]


def test_der_auftritt_faehrt_die_seitenpruefung_als_letzten_schritt(tmp_path: Path, monkeypatch):
    """Die ganze Seite: erst der Rahmen aus dem Fall, dann der Betriebsteil
    ohne Fall, dann Wache, Vorschau und zuletzt die Seitenpruefung; ein Befund
    haelt die Kette an. Nur der Rahmen: ohne Vorschau und Pruefung, seine
    Verweise in den Betriebsteil haetten kein Ziel."""
    aufrufe: list = []
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    aus = tmp_path / "seite"
    rahmen = ["--fall", "f", "--name", "n", "--film", "film.mp4", "--out", str(aus),
              "--vorschau", "vorschau"]
    argv = rahmen + ["--stands-paket", "paket", "--anker", "anker.jsonl", "--ab1", "A-B1.json"]
    assert at.main(argv) == 0
    assert [Path(k[1]).name for k in aufrufe] == [
        "falldaten.py", "vorzeigeseite.py", "unternehmensseite.py", "falldaten.py",
        "unternehmensseite.py", "bereinigung.py", "vorschau.py", "seitenpruefung.py"]
    fall, seiten, betrieb, betriebsseiten = aufrufe[0], aufrufe[2], aufrufe[3], aufrufe[4]
    assert "--stands-paket" not in fall, "der Rahmen kennt das Paket nicht"
    assert seiten[seiten.index("--teil") + 1] == "rahmen"
    assert seiten[seiten.index("--film") + 1] == "film.mp4"
    for schalter, ziel in (("--quellen", ROOT / "plv" / "seite"), ("--docs", ROOT / "docs"),
                           ("--repo", ROOT)):
        assert seiten[seiten.index(schalter) + 1] == str(ziel), schalter
    assert aufrufe[1][aufrufe[1].index("--repo") + 1] == str(ROOT)
    assert "--fall" not in betrieb and betrieb[betrieb.index("--ab1") + 1] == "A-B1.json"
    assert betriebsseiten[betriebsseiten.index("--teil") + 1] == "betrieb"
    assert betriebsseiten[betriebsseiten.index("--daten") + 1] == str(aus.parent / "betriebsdaten.json")
    letzter = aufrufe[-1]
    assert letzter[2] == "alle"
    assert dict(zip(letzter[3::2], letzter[4::2])) == {
        "--seite": str(aus), "--vorschau": "vorschau", "--fall": "f", "--name": "n",
        "--daten": str(aus.parent / "falldaten.json"), "--paket": "paket",
        "--anker": "anker.jsonl", "--ab1": "A-B1.json", "--repo": str(ROOT)}

    aufrufe.clear()
    monkeypatch.setattr(at, "_schritt", lambda kommando, erlaubt=(0,): (
        aufrufe.append(kommando) or (1 if "seitenpruefung.py" in kommando[1] else 0)))
    assert at.main(argv) == 1

    aufrufe.clear()
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    assert at.main(["--teil", "rahmen"] + rahmen) == 0
    assert [Path(k[1]).name for k in aufrufe] == [
        "falldaten.py", "vorzeigeseite.py", "unternehmensseite.py", "bereinigung.py"]
    with pytest.raises(SystemExit):
        at.main(rahmen)   # beide Teile, aber ohne Paket


def test_der_betriebsteil_baut_ohne_fall_in_einen_baum_mit_rahmen(tmp_path: Path, monkeypatch):
    """So baut der Workflow von plv-fiktion den Abend: nur betrieb/, ohne Fall,
    in den ausgecheckten Rahmen; die Seitenpruefung laeuft ohne --fall und
    prueft die Kennungen nur im Betriebsteil."""
    aufrufe: list = []
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    aus = tmp_path / "seite"
    assert at.main(["--teil", "betrieb", "--out", str(aus), "--vorschau", "vorschau",
                    "--stands-paket", "paket", "--anker", "anker.jsonl", "--ab1", "A-B1.json"]) == 0
    assert [Path(k[1]).name for k in aufrufe] == [
        "falldaten.py", "unternehmensseite.py", "bereinigung.py", "vorschau.py",
        "seitenpruefung.py"]
    assert all("--fall" not in k and "--film" not in k for k in aufrufe)
    # Der Workflow ruft die Kette aus einem anderen Verzeichnis auf (der Code
    # liegt dort unter code/): Die Quellseiten kommen aus dem Codebaum der
    # Kette, nicht relativ zum Arbeitsverzeichnis (gefunden in der Probe des
    # Workflows am 15.10.2026).
    seiten = aufrufe[1]
    assert seiten[seiten.index("--quellen") + 1] == str(ROOT / "plv" / "seite")
    with pytest.raises(SystemExit):
        at.main(["--teil", "betrieb", "--out", str(aus)])   # ohne Paket
