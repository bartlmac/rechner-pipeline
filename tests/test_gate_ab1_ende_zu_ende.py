"""A-B1 durch den ECHTEN Gate-Pfad — der Test, der gefehlt hat.

Befund 2026-09-16: ``A-B1.auslieferung`` war seit seiner Einfuehrung
funktional tot. Das Entscheid-Kommando rechnete den Ankersatz als
Pflichtbeleg aus (``pflichtbelege["anker"]``), schrieb ihn aber nicht in
``kern_inhalt`` — und ``kern_inhalt`` ist genau das, was signiert wird.
Die Unterschrift bezeugte danach alles ausser dem, was sie bezeugen
sollte: WELCHES Paket ausgeliefert wurde. Exit 0, kein Warnwort.

Gefunden hat es niemand, weil beide A-B1-Tests auf der falschen Seite
der Schreibstelle lagen: Der eine prueft die Tabelle
(``belegrollen("A-B1", ...)``), der andere den Konsumenten, und zwar nur
in seinem Negativfall mit leerem ``entscheide/``-Verzeichnis. Die Zeile,
an der Tabelle und Snapshot sich treffen, fuhr kein Test an.

Dieser Test faehrt sie an. Er baut seine Nutzlast nicht selbst, sondern
liest den Snapshot, den das Kommando auf die Platte geschrieben hat.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models import anker as anker_mod
from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import annahme_args

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def _anker(fall: Path, *, art: str = anker_mod.ART_AUSLIEFERUNG):
    """Eine Ankerdatei mit genau einem Satz — wie der Export sie anlegt."""
    protokoll = fall.parent / "protokoll.jsonl"
    protokoll.write_text(
        json.dumps({"tag": "2026-09-16", "zeile": 1}) + "\n", encoding="utf-8"
    )
    satz = anker_mod.ankersatz(
        protokoll, "2026-09-16", "a" * 64, "b" * 64,
        art=art, erstellt="2026-09-16T10:00:00Z",
    )
    pfad = anker_mod.haenge_an(fall.parent / "anker", satz)
    return pfad, anker_mod.satz_hash(satz)


def _ab1(fall: Path, anker: Path, satz: str, *extra: str):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-B1", "--entscheid", "angenommen",
        "--entscheider", "Betriebsverantwortung",
        "--begruendung", "Stand geht nach aussen.",
        "--anker", str(anker), "--ankersatz", satz,
        "--repo-root", str(REPO_ROOT), *annahme_args(fall), *extra,
    ])


def test_die_auslieferung_pinnt_ihren_ankersatz_im_snapshot(fall):
    """DIE Zusicherung, die gefehlt hat.

    Nicht "das Kommando laeuft durch" — sondern: Der geschriebene
    Snapshot traegt die Belegbindung. Vor der Reparatur war der Exit-Code
    0 und ``pflichtbelege`` fehlte im Snapshot vollstaendig.
    """
    anker, satz = _anker(fall)
    ergebnis = _ab1(fall, anker, satz)
    assert ergebnis.exit_code == 0, ergebnis.errors

    snapshot = json.loads(
        Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8")
    )
    assert snapshot["pflichtbelege"] == {"anker": [satz]}, (
        "der Ankersatz steht nicht im Snapshot — die Unterschrift bezeugt "
        "nicht, WELCHES Paket ausgeliefert wurde"
    )
    assert snapshot["fall_scope"] == "bestand"


def test_der_ankersatz_liegt_im_signierten_inhalt(fall):
    """Nicht nur IM Snapshot, sondern im SIGNIERTEN Teil.

    Ein Feld, das der Snapshot zwar traegt, das aber ausserhalb der
    Signatur liegt, waere nachtraeglich austauschbar — die Bindung waere
    dekorativ. Geprueft ueber den Selbstadressierungs-Hash: Wer
    pflichtbelege aendert, aendert snapshot_sha256.
    """
    anker, satz = _anker(fall)
    snapshot = json.loads(
        Path(_ab1(fall, anker, satz).paths["snapshot"]).read_text(
            encoding="utf-8")
    )
    verbogen = dict(snapshot, pflichtbelege={"anker": ["c" * 64]})
    assert gate_entscheid.p9_snapshot_sha256(
        verbogen) != snapshot["snapshot_sha256"], (
        "pflichtbelege gehen nicht in die Selbstadressierung ein")


def test_der_lesepfad_prueft_die_rollenmenge_auch_fuer_ab1(fall):
    """Die zweite Haelfte: Was geschrieben wurde, wird beim LESEN gegen
    den Belegvertrag gehalten — sonst reichte ein handgeschriebener
    Snapshot mit leerer Rollenmenge."""
    anker, satz = _anker(fall)
    snapshot = json.loads(
        Path(_ab1(fall, anker, satz).paths["snapshot"]).read_text(
            encoding="utf-8")
    )
    assert gate_entscheid._pruefe_g2_snapshot_semantik(
        snapshot, snapshot["system"]) == []

    kaputt = dict(snapshot, pflichtbelege={})
    assert gate_entscheid._pruefe_g2_snapshot_semantik(
        kaputt, kaputt["system"]), (
        "ein Snapshot ohne Pflichtbelege muss dem Lesepfad auffallen")


def test_eine_momentaufnahme_ist_keine_auslieferung(fall):
    """Positivkontrolle der Art-Pruefung: Der Detektor darf nicht gegen
    jeden Ankersatz gruen sein."""
    anker, satz = _anker(fall, art=anker_mod.ART_MOMENTAUFNAHME)
    ergebnis = _ab1(fall, anker, satz)
    assert ergebnis.exit_code != 0
    assert list((fall / "entscheide").glob("A-B1-*.json")) == []
