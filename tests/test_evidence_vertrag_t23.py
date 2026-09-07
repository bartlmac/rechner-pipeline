"""Versionierter Evidence-Vertrag (Review T23-02, T23-03, T23-09; Block 2).

Drei Befunde, eine Klasse: Ein Beleg, der etwas ueber einen Stand aussagt,
muss diesen Stand nachweisbar machen — statt ihn zu synthetisieren oder
frei zu behaupten.

* T23-02: Ein fehlender Versionsschluessel darf beim LADEN nicht still zur
  aktuellen Version werden. Der Modell-Default gilt fuer die Konstruktion
  (eine frisch gebaute A-Box spricht das aktuelle Vokabular), die Lader
  verlangen die Deklaration — sonst sind "nicht deklariert" und "aktuell"
  ununterscheidbar, und jeder Versionsvergleich laeuft ins Leere. Der Test
  laeuft ueber ALLE Leser mit Versionsfeld (A-Box, Spez, die vier
  from_dict der Ergebnis-Schemata), nicht nur die zwei Reviewer-Zitate.
* T23-03: A-K1 belegt einen echten Uebergang: ``von_version`` ist der im
  Code deklarierte Vorgaenger (``TBOX_VERSIONEN``), die Ordnung laeuft
  aufwaerts. Erfundene, rueckwaerts laufende und vorgaengerlose
  Uebergaenge werden nicht signiert.
* T23-09: Belegpfade sind raeumlich gebunden — das A-K1-Artefakt im Fall
  oder im Repo, das Mandat (wie Ordnung und Schluessel) AUSSERHALB des
  Falls; das galt bisher nur fuer die Ordnung.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models import schemas
from rechner_pipeline.models.zeichnung import ausserhalb_des_falls
from rechner_pipeline.ontologie import tbox as tbox_modul
from rechner_pipeline.ontologie.abox import lade_aus_bytes, speichere
from rechner_pipeline.ontologie.tbox import ABOX_SCHEMA_VERSION, TBOX_VERSION, ABox
from rechner_pipeline.spez.schema import SPEZ_VERSION
from rechner_pipeline.spez.validierung import lade_spez_aus_bytes, validate_spez
from tests.e2e_fixture import bereite_pk1_fall
from tests.test_tbox_version_ak1 import _beleg
from tests.zeichnung_fixture import annahme_args

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# T23-02: kein Versionsschluessel -> kein Laden (alle Leser, nicht zwei)
# --------------------------------------------------------------------------- #

def test_versionslinie_ist_konsistent_mit_der_code_version():
    """Die letzte Version der Linie ist die, die der Code traegt — sonst
    wuerden zwei Wahrheiten ueber die T-Box im Code stehen."""
    assert tbox_modul.TBOX_VERSIONEN[-1] == TBOX_VERSION
    assert tuple(tbox_modul.TBOX_VERSIONEN) == tuple(dict.fromkeys(tbox_modul.TBOX_VERSIONEN))


def test_abox_datei_ohne_versionsdeklaration_wird_nicht_geladen():
    abox = ABox(fall="f", generationen=[])
    voll = json.loads(abox.model_dump_json())
    assert voll["tbox_version"] == TBOX_VERSION and voll["schema_version"] == ABOX_SCHEMA_VERSION
    assert lade_aus_bytes(json.dumps(voll).encode()).tbox_version == TBOX_VERSION
    for schluessel in ("tbox_version", "schema_version"):
        ohne = {k: v for k, v in voll.items() if k != schluessel}
        with pytest.raises(ValueError, match="Versionsdeklaration"):
            lade_aus_bytes(json.dumps(ohne).encode())


def test_spez_datei_ohne_versionsdeklaration_wird_nicht_geladen(tmp_path):
    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    spez_pfad = next((fall / "abgeleitet" / "spez").glob("*.spez.json"))
    voll = json.loads(spez_pfad.read_text(encoding="utf-8"))
    assert lade_spez_aus_bytes(json.dumps(voll).encode()).spez_version == SPEZ_VERSION
    for schluessel in ("spez_version", "tbox_version"):
        ohne = {k: v for k, v in voll.items() if k != schluessel}
        with pytest.raises(ValueError, match="Versionsdeklaration"):
            lade_spez_aus_bytes(json.dumps(ohne).encode())


def test_spez_version_und_abox_schema_werden_verglichen(tmp_path):
    """Die bisher unverglichenen Felder: eine fremde spez_version bzw. ein
    fremdes A-Box-Dateischema sind ein Befund, kein stiller Durchlauf."""
    from rechner_pipeline.ontologie.abox import lade, validate_abox
    from rechner_pipeline.spez.erzeugen import baue_spez

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    abox = lade(fall)
    spez = baue_spez(abox, abox.generationen[0].id)
    assert not any("spez_version" in f for f in validate_spez(spez, abox))
    fremd = spez.model_copy(update={"spez_version": "999.0.0"})
    assert any("spez_version" in f for f in validate_spez(fremd, abox))
    assert not any("schema_version" in f for f in validate_abox(abox))
    alt = abox.model_copy(update={"schema_version": 0})
    assert any("schema_version" in f for f in validate_abox(alt))


@pytest.mark.parametrize("klasse", [
    schemas.CommonResult, schemas.QaReport, schemas.QaContract, schemas.RunDossierV2Delta,
])
def test_ergebnis_schemata_synthetisieren_keine_schema_version(klasse):
    with pytest.raises(ValueError, match="schema_version fehlt"):
        klasse.from_dict({"command": "x", "run": {}, "qa_report": {}})


# --------------------------------------------------------------------------- #
# T23-03: A-K1 belegt einen nachweisbaren Uebergang
# --------------------------------------------------------------------------- #

def _pruefe(fall: Path, beleg: Path) -> list:
    return gate_entscheid.pruefe_tbox_aenderung(beleg, fall, repo_root=REPO_ROOT)


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def test_uebergang_ohne_vorgaenger_in_der_linie_wird_nicht_signiert(fall, monkeypatch):
    """Eine einelementige Linie hat keinen alten Stand: nichts zu zeichnen."""
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", (TBOX_VERSION,))
    fehler = _pruefe(fall, _beleg(fall, von_version="0.0.9"))
    assert any("keinen Uebergang" in f or "Vorgaenger" in f for f in fehler)


def test_uebergang_vom_deklarierten_vorgaenger_ist_gueltig(fall, monkeypatch):
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", ("0.0.9", TBOX_VERSION))
    assert _pruefe(fall, _beleg(fall, von_version="0.0.9")) == []


@pytest.mark.parametrize("von, stichwort", [
    ("0.0.8", "Vorgaenger"),          # erfunden: nicht der Vorgaenger in der Linie
    ("9.9.9", "aufwaerts"),           # rueckwaerts
    (TBOX_VERSION, "gleich"),         # kein Uebergang
])
def test_erfundene_oder_rueckwaerts_laufende_uebergaenge_fallen(fall, monkeypatch, von, stichwort):
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", ("0.0.9", TBOX_VERSION))
    fehler = _pruefe(fall, _beleg(fall, von_version=von))
    assert any(stichwort in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# T23-09: Belegpfade sind raeumlich gebunden
# --------------------------------------------------------------------------- #

def test_ak1_artefakt_ausserhalb_von_fall_und_repo_wird_abgewiesen(fall, monkeypatch, tmp_path):
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", ("0.0.9", TBOX_VERSION))
    fremd = tmp_path / "anderswo" / "vermerk.md"
    fremd.parent.mkdir()
    fremd.write_text("extern\n", encoding="utf-8")
    sha = hashlib.sha256(fremd.read_bytes()).hexdigest()
    absolut = _beleg(fall, von_version="0.0.9", artefakt={"pfad": str(fremd), "sha256": sha})
    assert any("kanonischer Pfad" in f for f in _pruefe(fall, absolut))
    hinaus = _beleg(fall, von_version="0.0.9",
                    artefakt={"pfad": "../anderswo/vermerk.md", "sha256": sha})
    assert any("kanonischer Pfad" in f for f in _pruefe(fall, hinaus))


def test_ak1_artefakt_im_repo_ist_erlaubt(fall, monkeypatch):
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", ("0.0.9", TBOX_VERSION))
    adr = Path("docs") / "architektur" / "adr-018-rollenmodell-und-schluesselklassen.md"
    sha = hashlib.sha256((REPO_ROOT / adr).read_bytes()).hexdigest()
    beleg = _beleg(fall, von_version="0.0.9", artefakt={"pfad": adr.as_posix(), "sha256": sha})
    assert _pruefe(fall, beleg) == []


def test_mandat_innerhalb_des_falls_autorisiert_nichts(fall, tmp_path):
    innen = fall / "mandat.txt"
    innen.write_text("Mandat\n", encoding="utf-8")
    assert not ausserhalb_des_falls(innen, fall)
    aussen = tmp_path / "mandat.txt"
    aussen.write_text("Mandat\n", encoding="utf-8")
    assert ausserhalb_des_falls(aussen, fall)
    assert not ausserhalb_des_falls(tmp_path / "fehlt.txt", fall)


def test_p9_gate_verweigert_mandat_im_fall(fall, monkeypatch):
    monkeypatch.setattr(tbox_modul, "TBOX_VERSIONEN", ("0.0.9", TBOX_VERSION))
    _beleg(fall, von_version="0.0.9")
    innen = fall / "abgeleitet" / "mandat.txt"
    innen.write_text("Mandat\n", encoding="utf-8")
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-K1", "--entscheid", "angenommen",
        "--entscheider", "IT-Verantwortung", "--begruendung", "T-Box erweitert",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall), "--mandat", str(innen),
    ])
    assert ergebnis.exit_code != 0
    assert any("innerhalb des Falls" in e.get("message", "") for e in ergebnis.errors)


# --------------------------------------------------------------------------- #
# Nachtrag adversarialer Review Block 2: kein Weg am fail-closed Lader vorbei,
# und die Fallgrenze liest ".." lexikalisch richtig
# --------------------------------------------------------------------------- #

def test_pk1_laedt_die_abox_nicht_am_fail_closed_lader_vorbei(tmp_path):
    """P-K1 parste die A-Box direkt (ABox.model_validate_json) — dieselbe
    Luecke wie T23-02, nur in einer zweiten Datei. Eine A-Box ohne
    tbox_version darf kein gruenes Golden-Master-Urteil bekommen."""
    from rechner_pipeline.gates import generation_golden
    from rechner_pipeline.ontologie.abox import abox_pfad

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    pfad = abox_pfad(fall)
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    del daten["tbox_version"]
    pfad.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    ergebnis = generation_golden.main([
        "--fall", str(fall), "--generation", "klv/tg2012",
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(fall / "abgeleitet" / "diagnostics"),
    ])
    assert ergebnis.exit_code != 0
    assert any("Versionsdeklaration" in e.get("message", "") for e in ergebnis.errors), ergebnis.errors


def test_fallgrenze_liest_punktpunkt_lexikalisch_richtig(fall, tmp_path, monkeypatch):
    """'../mandat.txt', aufgerufen aus dem Fall heraus, liegt AUSSERHALB —
    pathlib.relative_to kollabiert '..' nicht, deshalb wird lexikalisch
    normalisiert (ohne Symlinks aufzuloesen)."""
    aussen = fall.parent / "mandat_extern.txt"
    aussen.write_text("Mandat\n", encoding="utf-8")
    monkeypatch.chdir(fall)
    assert ausserhalb_des_falls(Path("../mandat_extern.txt"), Path("."))
    # Und ein Symlink im Fall, der nach aussen zeigt, bleibt "innerhalb":
    link = fall / "mandat_link.txt"
    link.symlink_to(aussen)
    assert not ausserhalb_des_falls(Path("mandat_link.txt"), Path("."))
