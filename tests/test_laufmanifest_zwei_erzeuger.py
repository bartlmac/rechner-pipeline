"""Zwei Erzeuger schreiben Laufmanifeste — und jeder Leser sagt, welchen er will.

Seit dem Manifest-Entscheid (2026-09-16) verlangt die Migrationsabnahme
A-M4 ein Laufmanifest im P-B1-Beleg. Geschrieben hat es damals nur
``bestand.cli_fortschreibung`` — den Bestand, den A-M4 abnimmt, erzeugt
aber kein Fortschreibungslauf, sondern der Migrationszugang. Die Abnahme
eines echten Migrationsfalls war damit unerfuellbar, und zwar still: Alle
A-M4-Tests legen ihren belegten Lauf als Fortschreibung an, der
Ketten-e2e fuhr ``gates.abnahmebericht`` gar nicht mit. Aufgefallen ist
es erst beim Fahren des Falls.

Die Reparatur (Entscheid des Maintainers 2026-09-20, Weg D) macht
``gates.verankerung_belegen`` zum zweiten Manifest-Schreiber: Er ist der
letzte, der in das Uebernahme-Verzeichnis schreibt, und der erste, der
sowohl die Korrekturschicht als auch die Config der Fuehrung kennt.

Damit ist ``validate_manifest`` allein keine Zusicherung mehr — es sagt
nur noch, dass ein Manifest WOHLGEFORMT ist, nicht, dass es zum Kommando
passt. Dieses Modul haelt beide Haelften fest: die Rollentabelle je
Erzeuger, und dass jeder Leser seine Erwartung nennt.

Knoten: klv
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
from pathlib import Path

import pytest

from rechner_pipeline.bestand.manifest import (
    ERZEUGER,
    ERZEUGER_ERLAUBT,
    ERZEUGER_MIGRATIONSZUGANG,
    ManifestError,
    ROLLEN_DATEIEN,
    lies_manifest,
    pruefe_erzeuger,
    rollen_dateien,
    schreibe_manifest,
    validate_manifest,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"


def _lauf(tmp_path: Path, *, erzeuger: str) -> Path:
    """Ein Laufverzeichnis mit den Pflichtrollen DIESES Erzeugers."""
    lauf = tmp_path / erzeuger
    lauf.mkdir()
    config = tmp_path / "bestand-config.toml"
    config.write_text("# Config\n", encoding="utf-8")
    dateien = []
    for rolle in ("portfolio", "historie", "ledger", "scheiben"):
        ziel = lauf / rollen_dateien(erzeuger)[rolle]
        ziel.write_bytes(f"{erzeuger}:{rolle}".encode("utf-8"))
        dateien.append(ziel)
    schreibe_manifest(
        lauf,
        horizont=_dt.date(2026, 1, 1),
        neuzugang_ab=None,
        config_pfad=config,
        ausgaben=dateien,
        erzeuger=erzeuger,
    )
    return lauf


# --------------------------------------------------------------------------- #
# 1. Die Rollentabelle haengt am Erzeuger — und nur in einer Rolle
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("erzeuger, portfolio", [
    (ERZEUGER, "bestand_gesamt.parquet"),
    (ERZEUGER_MIGRATIONSZUGANG, "bestand.parquet"),
])
def test_die_portfolio_rolle_haengt_am_erzeuger(erzeuger: str, portfolio: str):
    """Der Unterschied ist keine Namenskosmetik, sondern zwei Mengen: Die
    Fortschreibung fuehrt Uebernahme UND eigenes Geschaeft, der
    Migrationszugang nur die uebernommenen Vertraege."""
    assert rollen_dateien(erzeuger)["portfolio"] == portfolio


def test_nur_die_portfolio_rolle_unterscheidet_sich():
    """Positivkontrolle zur Tabelle darueber: Waere mehr verschieden,
    muesste jeder Leser mehr wissen als den Erzeuger — und die Reparatur
    waere eine andere."""
    a, b = rollen_dateien(ERZEUGER), rollen_dateien(ERZEUGER_MIGRATIONSZUGANG)
    assert set(a) == set(b) == set(ROLLEN_DATEIEN)
    verschieden = {k for k in a if a[k] != b[k]}
    assert verschieden == {"portfolio"}, verschieden


def test_unbekannter_erzeuger_faellt_hart_aus():
    """Kein stiller Rueckfall auf die Vorgabe: Ein Manifest mit fremdem
    Erzeuger ist ein Befund, keine Fortschreibung."""
    with pytest.raises(ManifestError, match="unbekannter Erzeuger"):
        rollen_dateien("bestand_erfunden")


# --------------------------------------------------------------------------- #
# 2. Wohlgeformt ist nicht passend
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("erzeuger", ERZEUGER_ERLAUBT)
def test_beide_erzeuger_schreiben_ein_gueltiges_manifest(tmp_path: Path, erzeuger: str):
    lauf = _lauf(tmp_path, erzeuger=erzeuger)
    daten = lies_manifest(lauf)
    assert validate_manifest(daten) == []
    assert daten["erzeuger"] == erzeuger
    assert set(daten["ausgaben"]) == {
        rollen_dateien(erzeuger)[r]
        for r in ("portfolio", "historie", "ledger", "scheiben")}


def test_ein_dritter_erzeuger_ist_ein_befund(tmp_path: Path):
    """Die Menge ist kein Freibrief — sie hat genau zwei Elemente."""
    lauf = _lauf(tmp_path, erzeuger=ERZEUGER)
    pfad = lauf / "laufmanifest.json"
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["erzeuger"] = "bestand_erfunden"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    fehler = validate_manifest(daten)
    assert any("erzeuger" in f for f in fehler), fehler


@pytest.mark.parametrize("geschrieben, erwartet", [
    (ERZEUGER, ERZEUGER_MIGRATIONSZUGANG),
    (ERZEUGER_MIGRATIONSZUGANG, ERZEUGER),
])
def test_der_leser_nennt_seine_erwartung_und_haelt_sonst_an(
    tmp_path: Path, geschrieben: str, erwartet: str
):
    """In BEIDE Richtungen: Ein Betriebskommando nimmt kein
    Migrationsmanifest, und ein Migrationskonsument keinen
    Fortschreibungslauf. Eine Wache, die nur eine Richtung kennt, laesst
    die andere durch."""
    daten = lies_manifest(_lauf(tmp_path, erzeuger=geschrieben))
    assert validate_manifest(daten) == []          # wohlgeformt ...
    with pytest.raises(ManifestError, match="anderen Lauftyp"):
        pruefe_erzeuger(daten, erwartet)           # ... aber nicht passend


@pytest.mark.parametrize("erzeuger", ERZEUGER_ERLAUBT)
def test_die_wache_laesst_den_richtigen_durch(tmp_path: Path, erzeuger: str):
    """Positivkontrolle: Eine Wache, die alles abweist, bezeugt nichts."""
    pruefe_erzeuger(lies_manifest(_lauf(tmp_path, erzeuger=erzeuger)), erzeuger)


# --------------------------------------------------------------------------- #
# 3. Ratsche: jeder Leser eines Manifests nennt seine Erwartung
# --------------------------------------------------------------------------- #

#: Die Leser, die ein Manifest fuer einen LAUF lesen und deshalb sagen
#: muessen, welche Sorte sie erwarten. Die P-B1-Engine
#: (``bestand/vorbedingungen.py``) steht bewusst NICHT hier: Sie prueft
#: beide Lauftypen und schlaegt die Rollentabelle am Erzeuger des
#: Manifests nach, statt einen Typ zu verlangen — das ist ihre Aufgabe.
LESER_MIT_ERWARTUNG = {
    "betrieb/tageslauf.py",
    "betrieb/seite.py",
    "bestand/cli_abschluss.py",
}


def _liest_manifest(quelle: str) -> bool:
    return "lies_manifest(" in quelle


def test_jeder_lauf_leser_nennt_seine_erwartung():
    """Ratsche gegen den naechsten Leser, der es vergisst.

    ``==``, nicht ``<=``: Eine Ratsche, die "hoechstens so viele wie
    heute" sagt, laesst den vierten Leser durch, sobald jemand
    gleichzeitig einen alten entfernt.
    """
    leser = {
        str(p.relative_to(SRC)): p.read_text("utf-8")
        for p in sorted(SRC.rglob("*.py"))
        if _liest_manifest(p.read_text("utf-8"))
        and p != SRC / "bestand" / "manifest.py"   # dort steht die Definition
    }
    assert set(leser) == LESER_MIT_ERWARTUNG, sorted(leser)
    ohne = [name for name, quelle in leser.items()
            if "pruefe_erzeuger(" not in quelle]
    assert ohne == [], (
        "liest ein Laufmanifest, sagt aber nicht, welche Sorte Lauf es "
        "erwartet — pruefe_erzeuger() aufrufen", ohne)


def test_die_ratsche_findet_einen_leser_ohne_erwartung():
    """Positivkontrolle des Detektors: Ein Detektor ohne Treffer beweist
    nichts."""
    assert _liest_manifest("m = lies_manifest(lauf)\n")
    assert not _liest_manifest("x = lies_manifest_bytes(lauf)\n".replace(
        "lies_manifest_bytes", "lies_manifest_byte_s"))


def test_die_wache_steht_im_quelltext_und_nicht_nur_im_import():
    """Ein Import allein ist keine Pruefung — der Aufruf muss da sein.

    Gemessen ueber den AST, nicht ueber ``in``: ``pruefe_erzeuger`` in
    einem Kommentar oder Docstring haette die Zeichenkettenpruefung oben
    zufriedengestellt.
    """
    for name in sorted(LESER_MIT_ERWARTUNG):
        baum = ast.parse((SRC / name).read_text("utf-8"))
        aufrufe = [
            k for k in ast.walk(baum)
            if isinstance(k, ast.Call)
            and isinstance(k.func, ast.Name)
            and k.func.id == "pruefe_erzeuger"
        ]
        assert aufrufe, f"{name}: kein Aufruf von pruefe_erzeuger()"
