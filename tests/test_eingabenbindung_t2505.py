"""Jeder Producer bindet seine Eingaben (Review T25-05, Haelfte b).

Ein Beleg ist nur so viel wert wie die Bindung seiner Eingaben: Er muss
den Hash DER BYTES tragen, die verarbeitet wurden. Zwei Verletzungen gab
es, und beide betrafen Kommandos, deren Ergebnis eine Abnahme traegt.

* Eine Eingabe wird gelesen, aber nicht gebunden — das Kommando urteilt
  ueber etwas, das sein Beleg nicht nennt. ``bestand_uebernehmen`` hatte
  GAR KEINEN Eingaben-Block; ``aktuartest_lauf`` auch nicht;
  ``migrationssuite_lauf`` band genau eine von zehn.
* Eine Datei wird ZWEIMAL gelesen, einmal zum Hashen und einmal zum
  Verarbeiten. Dann bezeugt der Hash nicht die verarbeiteten Bytes.
  Genau das tat ``migrationssuite_lauf`` mit der einen Datei, die es
  band.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates._common import Eingangsbindung


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


# --- Die gemeinsame Tuer -------------------------------------------------


def test_die_bindung_liest_einmal_und_nennt_den_hash_der_bytes(tmp_path):
    datei = tmp_path / "eingabe.json"
    datei.write_text(json.dumps({"a": 1}), encoding="utf-8")
    bindung = Eingangsbindung(tmp_path)

    gelesen = bindung.binde(datei)

    assert gelesen.json() == {"a": 1}
    assert gelesen.sha256 == _sha256(datei)
    # Im Fall relativ gefuehrt: ein portabler Beleg.
    assert bindung.als_beleg() == {"eingabe.json": _sha256(datei)}


def test_ausserhalb_der_basis_wird_absolut_gefuehrt(tmp_path):
    aussen = tmp_path / "aussen"
    aussen.mkdir()
    datei = aussen / "x.json"
    datei.write_text("{}", encoding="utf-8")
    bindung = Eingangsbindung(tmp_path / "fall")

    bindung.binde(datei)

    assert list(bindung.als_beleg()) == [str(datei.resolve())]


def test_ein_anderswo_gebildeter_hash_kann_uebernommen_werden(tmp_path):
    """Fuer Ketten, die eine fremde Provenienz nachrechnen: Die Hashes
    sind dabei ohnehin gebildet — sie gehoeren in den eigenen Beleg,
    statt nach dem Vergleich verworfen zu werden."""
    bindung = Eingangsbindung(tmp_path)
    bindung.registriere(tmp_path / "fremd.parquet", "a" * 64)
    assert bindung.als_beleg() == {"fremd.parquet": "a" * 64}


def test_der_beleg_ist_sortiert(tmp_path):
    """Ein Beleg, dessen Reihenfolge vom Zufall abhaengt, ist nicht
    vergleichbar — und ein Diff zweier Laeufe waere unlesbar."""
    bindung = Eingangsbindung(tmp_path)
    for name in ("z.json", "a.json", "m.json"):
        pfad = tmp_path / name
        pfad.write_text("{}", encoding="utf-8")
        bindung.binde(pfad)
    assert list(bindung.als_beleg()) == ["a.json", "m.json", "z.json"]


# --- Die drei Producer ---------------------------------------------------


def test_die_uebernahme_bindet_ihre_eingaben(tmp_path):
    """``bestand_uebernehmen`` trug bisher gar keinen Eingaben-Block: Der
    Beleg nannte zwei Eingaben beim DATEINAMEN und keine mit ihrem Hash.
    Ein Beleg, der nicht sagt, aus welchen Bytes der Zugangsstand
    entstanden ist, bindet die Uebernahme an nichts."""
    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import bestand_uebernehmen
    from tests.test_bestand_uebernehmen import ZEILE

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    metadaten = tmp_path / "gevo_metadaten.csv"
    metadaten.write_text("POLNR;GEVO;DATUM\n7000001;ERH;01.02.2020\n",
                         encoding="utf-8")
    registrieren(fall, metadaten)
    zeilen = tmp_path / "zeilen.json"
    zeilen.write_text(json.dumps([dict(ZEILE)]), encoding="utf-8")
    ziel = fall / "abgeleitet" / "bestand"

    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", "TG2015", "--stichtag", "2026-01-01",
        "--vorgeschichte", "gevo_metadaten.csv",
        "--anfangszustand", "grundvertrag",
        "--out-dir", str(ziel),
    ]) == 0

    beleg = json.loads((ziel / "uebernahme.json").read_text(encoding="utf-8"))
    eingaben = beleg["eingaben"]
    assert eingaben, "der Beleg nennt keine einzige Eingabe"
    # Die Zeilenliste liegt ausserhalb des Falls, die Vorgeschichte darin.
    assert eingaben[str(zeilen.resolve())] == _sha256(zeilen)
    registriert = fall / "eingang" / "gevo_metadaten.csv"
    assert eingaben[str(registriert.relative_to(fall))] == _sha256(registriert)
    # Und jeder Hash gehoert wirklich zu der Datei, die er nennt.
    for rel, summe in eingaben.items():
        pfad = Path(rel)
        pfad = pfad if pfad.is_absolute() else fall / rel
        assert summe == _sha256(pfad), rel
