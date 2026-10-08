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
import sys
from pathlib import Path

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
              '<span id="oben"></span>')
    _schreibe(v / "index.html", sauber)
    befunde, zusammen = sp.verweise(v)
    assert befunde == ["teil/s.html: nix.html — kein Ziel"], befunde
    assert "extern: {'example.org': 1}" in zusammen

    _schreibe(v / "index.html", sauber + '<a href="a.html#fehlt">f</a> <a href="b.html">b</a> '
              '<a href="/abs.html">abs</a>')
    befunde, _ = sp.verweise(v)
    assert sorted(befunde) == sorted([
        "index.html: /abs.html — absoluter Pfad",
        "index.html: a.html#fehlt — kein Sprungziel",
        "index.html: b.html — kein Ziel",
        "teil/s.html: nix.html — kein Ziel"])


def _paket_und_seite(tmp_path: Path):
    paket = tmp_path / "paket"
    dateien = {"index.html": _sha(b"A"), "abschluesse/abschluss_2026-10-01.parquet": _sha(b"P"),
               "bestandsbericht_2026-10-01.html": _sha(b"B")}
    _schreibe(paket / "stand.json", json.dumps({"dateien": dateien}))
    seite = tmp_path / "seite"
    _schreibe(seite / "plv" / "index.html", b"A")
    _schreibe(seite / "plv" / "bestandsbericht_2026-10-01.html", b"B")
    _schreibe(seite / "berichte" / "bestandsbericht_2026-10-01.html", b"B")
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

    assert mutiert("abweichend", lambda s: (s / "plv" / "index.html").write_bytes(b"X")) == [
        "plv/index.html: weicht von stand.json ab"]
    assert mutiert("fremd", lambda s: (s / "plv" / "fremd.txt").write_bytes(b"F")) == [
        "plv/fremd.txt: ohne Eintrag in stand.json"]
    assert mutiert("fehlt", lambda s: (s / "plv" / "index.html").unlink()) == [
        "plv/index.html: in stand.json, aber nicht veroeffentlicht"]
    assert mutiert("kopie", lambda s: (s / "berichte" / "bestandsbericht_2026-10-01.html")
                   .write_bytes(b"Y")) == [
        "berichte/bestandsbericht_2026-10-01.html: keine bytegleiche Datei des Pakets"]


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
    _schreibe(seite / "plv" / "index.html", "deadbeef99 im Beleg selbst")
    argumente = (seite, fall, "probe", paket, anker, daten, tmp_path)
    befunde, zusammen = sp.pruefsummen(*argumente)
    assert befunde == [] and "'Paket': 1" in zusammen

    _schreibe(seite / "index.md", "Manifest ab12cd34ef56 und deadbeef99\n")
    befunde, _ = sp.pruefsummen(*argumente)
    assert befunde == ["index.md: deadbeef99 — ohne Quelle"]


def test_der_auftritt_faehrt_die_seitenpruefung_als_letzten_schritt(tmp_path: Path, monkeypatch):
    """Mit Stands-Paket, Anker und Vorschau prueft der Bau zuletzt die
    gebaute Seite; ein Befund haelt die Kette an. Ohne Paket gibt es nichts
    gegen stand.json zu halten, der Schritt entfaellt."""
    aufrufe: list = []
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    aus = tmp_path / "seite"
    argv = ["--fall", "f", "--name", "n", "--out", str(aus), "--vorschau", "vorschau",
            "--stands-paket", "paket", "--anker", "anker.jsonl"]
    assert at.main(argv) == 0
    assert [Path(k[1]).name for k in aufrufe] == [
        "falldaten.py", "vorzeigeseite.py", "unternehmensseite.py", "bereinigung.py",
        "vorschau.py", "seitenpruefung.py"]
    letzter = aufrufe[-1]
    assert letzter[2] == "alle"
    assert dict(zip(letzter[3::2], letzter[4::2])) == {
        "--seite": str(aus), "--vorschau": "vorschau", "--fall": "f", "--name": "n",
        "--paket": "paket", "--anker": "anker.jsonl",
        "--daten": str(aus.parent / "falldaten.json"), "--repo": str(ROOT)}

    aufrufe.clear()
    monkeypatch.setattr(at, "_schritt", lambda kommando, erlaubt=(0,): (
        aufrufe.append(kommando) or (1 if "seitenpruefung.py" in kommando[1] else 0)))
    assert at.main(argv) == 1

    aufrufe.clear()
    monkeypatch.setattr(at, "_schritt",
                        lambda kommando, erlaubt=(0,): aufrufe.append(kommando) or 0)
    assert at.main(argv[:6]) == 0
    assert "seitenpruefung.py" not in [Path(k[1]).name for k in aufrufe]
