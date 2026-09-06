"""Externes Review T22-02: Die T-Box-Version war nominal — kein Gate verglich sie.

Nachweis des Reviews: ``abox_tbox 999.0.0 -> pq3_exit 0``. Und fuer A-K1
gab es keinen Beleg-Vertrag: Eine T-Box-Aenderung liess sich zeichnen,
ohne dass irgendetwas die Aenderung belegte. Jetzt haelt P-Q3 die A-Box,
P-K1 die Spez gegen die geltende Version, und A-K1 verlangt den Beleg
``abgeleitet/tbox/aenderung.json``.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.ontologie import tbox as tbox_modul
from rechner_pipeline.ontologie.abox import abox_pfad, lade, validate_abox
from rechner_pipeline.ontologie.tbox import TBOX_VERSION
from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import annahme_args

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def _abox_mit_version(fall: Path, version: str) -> None:
    pfad = abox_pfad(fall)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["tbox_version"] = version
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------- #
# P-Q3 und P-K1 vergleichen die Version
# --------------------------------------------------------------------------- #

def test_pq3_verweigert_eine_abox_fremder_tbox_version(fall):
    """Der Nachweis des Reviews. Mutationsprobe: den Vergleich in
    validate_abox entfernen -> gruen trotz 999.0.0 -> dieser Test rot."""
    _abox_mit_version(fall, "999.0.0")
    abox = lade(fall)
    assert any("tbox_version" in f for f in validate_abox(abox))
    ergebnis = pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)])
    assert ergebnis.exit_code != 0
    assert any("tbox_version" in e["message"] for e in ergebnis.errors)


def test_validate_spez_haelt_spez_abox_und_code_zusammen(fall):
    from rechner_pipeline.spez.erzeugen import baue_spez
    from rechner_pipeline.spez.validierung import validate_spez

    abox = lade(fall)
    spez = baue_spez(abox, abox.generationen[0].id)
    assert not any("tbox_version" in f for f in validate_spez(spez, abox))
    fremd = spez.model_copy(update={"tbox_version": "999.0.0"})
    assert any("tbox_version" in f for f in validate_spez(fremd, abox))
    abox_fremd = abox.model_copy(update={"tbox_version": "999.0.0"})
    assert any("tbox_version" in f for f in validate_spez(spez, abox_fremd))


# --------------------------------------------------------------------------- #
# A-K1 hat einen Beleg-Vertrag
# --------------------------------------------------------------------------- #

def _ak1(fall: Path, *extra: str):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-K1", "--entscheid", "angenommen",
        "--entscheider", "IT-Verantwortung", "--begruendung", "T-Box erweitert",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall), *extra,
    ])


def _beleg(fall: Path, **ueberschreibung) -> Path:
    tbox_dir = fall / "abgeleitet" / "tbox"
    tbox_dir.mkdir(parents=True, exist_ok=True)
    artefakt = tbox_dir / "aenderungsvermerk.md"
    artefakt.write_text("Neues Pflichtfeld in der T-Box.\n", encoding="utf-8")
    daten = {
        "schema_version": 1,
        "von_version": "0.0.9",
        "nach_version": TBOX_VERSION,
        "tbox_sha256": hashlib.sha256(Path(tbox_modul.__file__).read_bytes()).hexdigest(),
        "artefakt": {"pfad": "abgeleitet/tbox/aenderungsvermerk.md",
                     "sha256": hashlib.sha256(artefakt.read_bytes()).hexdigest()},
        "begruendung": "Erweiterung um ein Pflichtfeld, siehe Vermerk.",
    }
    daten.update(ueberschreibung)
    pfad = tbox_dir / "aenderung.json"
    pfad.write_text(json.dumps(daten, indent=2), encoding="utf-8")
    return pfad


def test_ak1_ohne_beleg_wird_gesperrt(fall):
    ergebnis = _ak1(fall)
    assert ergebnis.exit_code == 20
    assert ergebnis.errors[0]["code"] == "vorbedingung"
    assert "aenderung.json" in ergebnis.errors[0]["message"]
    assert list((fall / "entscheide").glob("A-K1-*.json")) == []


def test_ak1_mit_beleg_pinnt_ihn_als_pflichtrolle(fall):
    beleg = _beleg(fall)
    ergebnis = _ak1(fall)
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["pflichtbelege"] == {
        "tbox_aenderung": [hashlib.sha256(beleg.read_bytes()).hexdigest()]}
    assert snapshot["fall_scope"] == "tarif"
    # Der Lesepfad prueft die Rollenmenge auch fuer A-K1:
    assert gate_entscheid._pruefe_g2_snapshot_semantik(snapshot) == []
    kaputt = dict(snapshot, pflichtbelege={})
    assert gate_entscheid._pruefe_g2_snapshot_semantik(kaputt)


@pytest.mark.parametrize("feld, wert, stichwort", [
    ("tbox_sha256", "00" * 32, "T-Box-Moduls"),
    ("nach_version", "999.0.0", "nach_version"),
    ("von_version", TBOX_VERSION, "gleich"),
    ("begruendung", "", "begruendung"),
])
def test_ak1_beleg_muss_zu_code_und_aenderung_passen(fall, feld, wert, stichwort):
    """Mutationsprobe je Zeile: die jeweilige Pruefung in
    pruefe_tbox_aenderung entfernen -> die Zeile wird gruen -> rot."""
    _beleg(fall, **{feld: wert})
    ergebnis = _ak1(fall)
    assert ergebnis.exit_code == 20
    assert stichwort in ergebnis.errors[0]["message"]


def test_ak1_beleg_artefakt_muss_existieren_und_stimmen(fall):
    _beleg(fall, artefakt={"pfad": "abgeleitet/tbox/gibt-es-nicht.md", "sha256": "00" * 32})
    assert "nicht gefunden" in _ak1(fall).errors[0]["message"]
    _beleg(fall, artefakt={"pfad": "abgeleitet/tbox/aenderungsvermerk.md", "sha256": "00" * 32})
    assert "Hash stimmt nicht" in _ak1(fall).errors[0]["message"]
