"""O3-zu-G-2-Beweisvertrag mit echtem Golden-Master-Lauf.

Die Positivstrecke nutzt die eingecheckte synthetische XLSM, ihre echte
openpyxl-Vorverdichtung, den produktiven Rechenkern und beide echten Gates.
Die Negativstrecken beweisen, dass weder ein Teilbeleg bei mehreren
Generationen noch ein Beleg eines anderen A-Box- oder Systemstands fuer G-2
genuegt.

Knoten: klv
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import pytest

import rechner_pipeline.gates.generation_golden as generation_golden
from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.fall import registrieren
from rechner_pipeline.gates import abnahmebericht, bestand_validate, gate_entscheid
from rechner_pipeline.gates._provenienz import (
    pruefe_o3_beleg,
    schreibe_o3_beleg,
)
from rechner_pipeline.gates.abox_validate import main as o1
from rechner_pipeline.gates.generation_golden import main as o3
from rechner_pipeline.kern import Rechenkern
from rechner_pipeline.kern.model_point import KLV_DEFAULT
from rechner_pipeline.ontologie.abox import lade, speichere
from rechner_pipeline.ontologie.transformation import (
    FeldMapping,
    TransformationsSpec,
    ZIEL_PFLICHT,
)
from rechner_pipeline.quellen.vorverdichtung import verzeichnis_der_generation
from rechner_pipeline.qa.migrationssuite import VertragsPruefung, pruefe_bestand
from tests.e2e_fixture import bereite_o3_fall, lade_o3_fixture

REPO_ROOT = Path(__file__).resolve().parents[1]
def _p9_annahme(fall: Path, gate: str, begruendung: str):
    schluessel = fall.parent / "p9-freigabe.key"
    if not schluessel.exists():
        schluessel.write_bytes(b"test-only-p9-authorization-key!" * 2)
        schluessel.chmod(0o600)
    return gate_entscheid.main([
        "--fall", str(fall),
        "--gate", gate,
        "--entscheid", "angenommen",
        "--rolle", "mensch",
        "--entscheider", "fachrolle",
        "--begruendung", begruendung,
        "--repo-root", str(REPO_ROOT),
        "--freigabe-schluessel", str(schluessel),
    ])


def _bereite_fall(
    tmp_path: Path,
    generationen: tuple[str, ...],
    *,
    scope: str = "tarif",
) -> Path:
    """Echten TG2012-Input vorbereiten; weitere Generationen teilen die Werte."""
    fall = bereite_o3_fall(tmp_path, generationen, scope=scope)
    if scope == "bestand":
        bestandsquelle = tmp_path / "synthetischer-bestand.csv"
        bestandsquelle.write_text(
            ";".join(ZIEL_PFLICHT) + "\n"
            + ";".join([
                "P-SCOPE-1", "2015-01-01", "35", "M", "20", "15",
                "100000", "12", "POL", "Einzel",
            ]) + "\n",
            encoding="utf-8",
        )
        registrieren(fall, bestandsquelle)
    assert o1([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
    ]).exit_code == 0
    assert _p9_annahme(fall, "G-1", "A-Box fachlich geprueft").exit_code == 0
    return fall


def _o3_tg2012(fall: Path):
    return o3([
        "--fall", str(fall),
        "--generation", "klv/tg2012",
        "--repo-root", str(REPO_ROOT),
    ])


def _abnahmebericht(fall: Path):
    nachweise = fall / "abgeleitet" / "abnahmenachweise"
    return abnahmebericht.main([
        "--fall", str(fall),
        "--suite", str(fall / "abgeleitet" / "suite.json"),
        "--spec", str(nachweise / "transformationsspec.json"),
        "--transformation-ergebnis", str(nachweise / "transformation.json"),
        "--bestandsbericht-vor", str(nachweise / "bestand-vor.html"),
        "--bestandsbericht-nach", str(nachweise / "bestand-nach.html"),
        "--titel", "Bestands-Scope E2E",
        "--stichtag-1", "2026-01-01",
        "--stichtag-2", "2027-01-01",
        "--repo-root", str(REPO_ROOT),
    ])


def _bereite_bestandsfall(tmp_path: Path) -> Path:
    """Echte O1/O3/B1-/Suite-/Berichtsbelege fuer einen Bestandsfall."""
    fall = _bereite_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    assert _o3_tg2012(fall).exit_code == 0

    lauf = fall / "abgeleitet" / "bestand"
    assert cli_fortschreibung.main([
        "--config", str(REPO_ROOT / "configs" / "bestand_klv.toml"),
        "--bis", "2020-01-01",
        "--out-dir", str(lauf),
    ]) == 0
    ziel = lauf / "bestand_gesamt.parquet"
    # Der Bestandsfall hat exakt eine B1-Zeile und die Suite prueft exakt
    # diese eine Zeile. Eine Teilpruefung eines groesseren B1-Bestands waere
    # kein positiver Vollstaendigkeitsbeleg. Gewaehlt wird eine Zeile im
    # Ursprungszustand (status_id 1): der gefuehrte Gesamtbestand traegt
    # seit ADR-011 aktuelle Zustaende, und ein Folgezustand verlangte sein
    # Journal — das dieser Ein-Zeilen-Ausschnitt nicht mitfuehrt.
    gesamt = read_portfolio(ziel)
    ursprung = gesamt[gesamt["status_id"] == 1]
    write_portfolio(ursprung.iloc[:1].copy(), ziel)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    b1 = bestand_validate.main([
        "--portfolio", str(ziel),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diagnostics),
    ])
    assert b1.exit_code == 0

    ziel_hash = sha256(ziel.read_bytes()).hexdigest()

    kern = Rechenkern(KLV_DEFAULT)
    s1, s2 = 12 * 9 + 5, 12 * 10 + 5
    suite = pruefe_bestand(
        [VertragsPruefung(
            police_id="P-SCOPE-1",
            model_point=asdict(KLV_DEFAULT),
            monate_stichtag_1=s1,
            monate_stichtag_2=s2,
            dk_erwartet_1=round(kern.monatsreserve(s1).vx_mrv, 2),
            bjb_erwartet_1=round(kern.gross_annual_premium(), 2),
            dk_erwartet_2=round(kern.monatsreserve(s2).vx_mrv, 2),
        )],
        erwartete_anzahl=1,
        stichtag_1="2026-01-01",
        stichtag_2="2027-01-01",
        bestand_sha256=ziel_hash,
        system=gate_entscheid.systemstand(REPO_ROOT),
    )
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    nachweise = fall / "abgeleitet" / "abnahmenachweise"
    nachweise.mkdir(parents=True, exist_ok=True)
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    transformationsquelle = next(
        quelle for quelle in register["quellen"]
        if quelle["datei"] == "synthetischer-bestand.csv"
    )
    spec = TransformationsSpec(
        quelle_datei=transformationsquelle["datei"],
        quelle_sha256=transformationsquelle["sha256"],
        akteur="test/fixture@todo10.5",
        erhoben_am="2026-08-20",
        felder=[
            FeldMapping(
                ziel=feld,
                typ="direkt",
                quellen=[feld],
                begruendung="synthetischer E2E-Nachweis",
            )
            for feld in ZIEL_PFLICHT
        ],
    )
    spec_pfad = nachweise / "transformationsspec.json"
    spec_pfad.write_text(spec.model_dump_json(), encoding="utf-8")
    (nachweise / "transformation.json").write_text(
        json.dumps({
            "schema_version": 1,
            "spec_sha256": sha256(spec_pfad.read_bytes()).hexdigest(),
            "quelle_sha256": transformationsquelle["sha256"],
            "quellspalten": list(ZIEL_PFLICHT),
            "ziel_datei": ziel.relative_to(fall).as_posix(),
            "ziel_sha256": ziel_hash,
            "zeilen_quelle": 1,
            "zeilen_ziel": 1,
            "befunde": [],
        }),
        encoding="utf-8",
    )
    (nachweise / "bestand-vor.html").write_text(
        "<html>Bestand vor Migration</html>", encoding="utf-8")
    (nachweise / "bestand-nach.html").write_text(
        "<html>Bestand nach Migration</html>", encoding="utf-8")

    bericht = _abnahmebericht(fall)
    assert bericht.exit_code == 0
    abnahme_ledger = json.loads(
        (diagnostics / "abnahmebericht.gate.json").read_text(encoding="utf-8")
    )
    assert abnahme_ledger["status"] == "passed"
    assert set(abnahme_ledger["summary"]["bestandsbelege"]) == {
        "b1_ledger", "migrationssuite", "abnahmebericht",
    }
    assert set(abnahme_ledger["summary"]["renderer_artefakte"]) == {
        "spec",
        "transformation_ergebnis",
        "bestandsbericht_vor",
        "bestandsbericht_nach",
    }
    return fall


def test_echtes_o3_schreibt_beleg_und_g2_nimmt_denselben_stand_an(
    tmp_path: Path,
):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    abox_datei = fall / "abgeleitet" / "abox" / "abox.json"
    abox_sha256 = sha256(abox_datei.read_bytes()).hexdigest()

    erster_o3 = _o3_tg2012(fall)
    assert erster_o3.exit_code == 0
    assert erster_o3.summary["werte_verglichen"] == 616
    assert erster_o3.input_hashes["abgeleitet/abox/abox.json"] == abox_sha256
    beleg_pfad = Path(erster_o3.paths["o3_beleg"])
    beleg, fehler = pruefe_o3_beleg(beleg_pfad)
    assert fehler == []
    assert beleg is not None
    assert beleg["generation"] == "klv/tg2012"
    assert beleg["abox_sha256"] == abox_sha256
    assert beleg["system"] == gate_entscheid.systemstand(REPO_ROOT)

    # Derselbe Beweis ist idempotent: kein Overwrite und keine zweite Datei.
    zweiter_o3 = _o3_tg2012(fall)
    assert zweiter_o3.exit_code == 0
    assert Path(zweiter_o3.paths["o3_beleg"]) == beleg_pfad
    assert list(beleg_pfad.parent.glob("generation_golden.*.beleg.json")) == [
        beleg_pfad
    ]

    g2 = _p9_annahme(fall, "G-2", "O3-Beweis vollstaendig geprueft")
    assert g2.exit_code == 0
    snapshot = json.loads(Path(g2.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["o3_belege"] == {
        "klv/tg2012": [beleg["beleg_sha256"]]
    }
    assert snapshot["fall_scope"] == "tarif"
    assert set(snapshot["pflichtbelege"]) == {
        "o1_ledger", "g1_snapshot", "o3_belege",
    }
    assert not any("bestand" in rolle for rolle in snapshot["pflichtbelege"])


def test_tarif_scope_mit_fehlender_deklaration_blockiert_g2(tmp_path: Path):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0
    manifest = json.loads((fall / "fall.json").read_text(encoding="utf-8"))
    manifest.pop("scope")
    (fall / "fall.json").write_text(json.dumps(manifest), encoding="utf-8")

    g2 = _p9_annahme(fall, "G-2", "darf Scope nicht erraten")

    assert g2.exit_code == 20
    assert g2.errors[0]["code"] == "fall_scope"
    assert "nicht maschinenlesbar" in g2.errors[0]["message"]


def test_g2_blockiert_scope_downgrade_nach_signiertem_g1(tmp_path: Path):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    assert _o3_tg2012(fall).exit_code == 0
    manifest = json.loads((fall / "fall.json").read_text(encoding="utf-8"))
    manifest["scope"]["typ"] = "tarif"
    (fall / "fall.json").write_text(json.dumps(manifest), encoding="utf-8")

    g2 = _p9_annahme(fall, "G-2", "darf Bestands-Scope nicht herabstufen")

    assert g2.exit_code == 20
    assert "keine eindeutige, signierte G-1" in g2.errors[0]["message"]
    assert "Scope-" in g2.errors[0]["message"]


def test_bestands_scope_bindet_b1_suite_und_abnahmebericht_bis_g2(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)

    g2 = _p9_annahme(fall, "G-2", "Bestandsbeweise vollstaendig geprueft")

    assert g2.exit_code == 0
    snapshot = json.loads(Path(g2.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["fall_scope"] == "bestand"
    assert set(snapshot["pflichtbelege"]) == {
        "o1_ledger", "g1_snapshot", "o3_belege", "b1_ledger",
        "migrationssuite", "abnahmebericht",
    }
    assert all(snapshot["pflichtbelege"].values())


def test_abnahmebericht_blockiert_falschen_quellhash_trotz_konsistenter_kopie(
    tmp_path: Path,
):
    """Spec und Ergebnis duerfen dieselbe falsche Quellenbehauptung tragen."""
    fall = _bereite_bestandsfall(tmp_path)
    nachweise = fall / "abgeleitet" / "abnahmenachweise"
    spec_pfad = nachweise / "transformationsspec.json"
    ergebnis_pfad = nachweise / "transformation.json"
    spec = json.loads(spec_pfad.read_text(encoding="utf-8"))
    spec["quelle_sha256"] = "0" * 64
    spec_pfad.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    ergebnis = json.loads(ergebnis_pfad.read_text(encoding="utf-8"))
    ergebnis["spec_sha256"] = sha256(spec_pfad.read_bytes()).hexdigest()
    ergebnis["quelle_sha256"] = "0" * 64
    ergebnis_pfad.write_text(json.dumps(ergebnis, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert (bericht.exit_code, bericht.status) == (20, "failed")
    assert bericht.errors[0]["code"] == "transformation_contract"
    meldung = " ".join(fehler["message"] for fehler in bericht.errors)
    assert "tatsaechlich transformierten registrierten Datei" in meldung


def test_abnahmebericht_prueft_quellspalten_am_registrierten_csv_header_nach(
    tmp_path: Path,
):
    """Auch eine vollstaendig neu gehashte Spaltenbehauptung bleibt rot."""
    fall = _bereite_bestandsfall(tmp_path)
    quelle = fall / "eingang" / "synthetischer-bestand.csv"
    quelle.chmod(0o600)
    quelle.write_text(
        ";".join(ZIEL_PFLICHT[:-1]) + "\n"
        + ";".join([
            "P-SCOPE-1", "2015-01-01", "35", "M", "20", "15",
            "100000", "12", "POL",
        ]) + "\n",
        encoding="utf-8",
    )
    quelle.chmod(0o444)
    quelle_sha256 = sha256(quelle.read_bytes()).hexdigest()
    register_pfad = fall / "eingang.json"
    register = json.loads(register_pfad.read_text(encoding="utf-8"))
    eintrag = next(
        wert for wert in register["quellen"] if wert["datei"] == quelle.name
    )
    eintrag["sha256"] = quelle_sha256
    eintrag["bytes"] = quelle.stat().st_size
    register_pfad.write_text(json.dumps(register, sort_keys=True), encoding="utf-8")

    nachweise = fall / "abgeleitet" / "abnahmenachweise"
    spec_pfad = nachweise / "transformationsspec.json"
    ergebnis_pfad = nachweise / "transformation.json"
    spec = json.loads(spec_pfad.read_text(encoding="utf-8"))
    spec["quelle_sha256"] = quelle_sha256
    spec_pfad.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    ergebnis = json.loads(ergebnis_pfad.read_text(encoding="utf-8"))
    ergebnis["spec_sha256"] = sha256(spec_pfad.read_bytes()).hexdigest()
    ergebnis["quelle_sha256"] = quelle_sha256
    # Angreifer behaelt die alte, angeblich transformierte Spaltenliste bei.
    assert ergebnis["quellspalten"] == list(ZIEL_PFLICHT)
    ergebnis_pfad.write_text(json.dumps(ergebnis, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert (bericht.exit_code, bericht.status) == (20, "failed")
    assert bericht.errors[0]["code"] == "transformation_contract"
    meldung = " ".join(fehler["message"] for fehler in bericht.errors)
    assert "physischen Header" in meldung
    assert "tarifart" in meldung


def test_g2_prueft_neu_gehashte_transformationsquelle_gegen_das_register(
    tmp_path: Path,
):
    """Ein in sich konsistenter falscher Quellhash darf G-2 nicht passieren."""
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    renderer = ledger["summary"]["renderer_artefakte"]
    spec_pfad = fall / renderer["spec"]["pfad"]
    ergebnis_pfad = fall / renderer["transformation_ergebnis"]["pfad"]

    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    falscher_aber_formaler_hash = next(
        quelle["sha256"] for quelle in register["quellen"]
        if quelle["datei"] == lade_o3_fixture().quelle.name
    )
    spec_roh = json.loads(spec_pfad.read_text(encoding="utf-8"))
    spec_roh["quelle_sha256"] = falscher_aber_formaler_hash
    spec_pfad.write_text(json.dumps(spec_roh, sort_keys=True), encoding="utf-8")
    ergebnis = json.loads(ergebnis_pfad.read_text(encoding="utf-8"))
    ergebnis["spec_sha256"] = sha256(spec_pfad.read_bytes()).hexdigest()
    ergebnis["quelle_sha256"] = falscher_aber_formaler_hash
    ergebnis_pfad.write_text(json.dumps(ergebnis, sort_keys=True), encoding="utf-8")

    for rolle, pfad in (
        ("spec", spec_pfad),
        ("transformation_ergebnis", ergebnis_pfad),
    ):
        eintrag = renderer[rolle]
        neuer_hash = sha256(pfad.read_bytes()).hexdigest()
        eintrag["sha256"] = neuer_hash
        ledger["input_hashes"][eintrag["pfad"]] = neuer_hash

    erzeugung = ledger["summary"]["bericht_erzeugung"]
    erzeugung["spec"] = spec_roh
    erzeugung["transformation_ergebnis"] = ergebnis
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    suite = json.loads((fall / suite_eintrag["pfad"]).read_text(encoding="utf-8"))
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    bericht_pfad = fall / bericht_eintrag["pfad"]
    bericht_pfad.write_text(abnahmebericht.baue_bericht(
        titel=erzeugung["titel"],
        stichtag_1=erzeugung["stichtag_1"],
        stichtag_2=erzeugung["stichtag_2"],
        suite=suite,
        spec=TransformationsSpec.model_validate(spec_roh),
        transformation_ergebnis=ergebnis,
        bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
        bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
    ), encoding="utf-8")
    bericht_hash = sha256(bericht_pfad.read_bytes()).hexdigest()
    bericht_eintrag["sha256"] = bericht_hash
    ledger["summary"]["output_hashes"] = {
        bericht_eintrag["pfad"]: bericht_hash,
    }
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall,
        "G-2",
        "darf konsistent neu gehashte falsche Transformationsquelle nicht annehmen",
    )

    assert g2.exit_code == 20
    assert "tatsaechlich transformierten registrierten Datei" in (
        g2.errors[0]["message"]
    )


def test_abnahmebericht_bindet_behauptete_zielzeilen_an_b1_und_suite(
    tmp_path: Path,
):
    """Gleiche 2->2-Zaehler duerfen keinen physischen Einzeiler belegen."""
    fall = _bereite_bestandsfall(tmp_path)
    quelle = fall / "eingang" / "synthetischer-bestand.csv"
    zweite_zeile = ";".join([
        "P-SCOPE-2", "2016-01-01", "36", "F", "20", "15",
        "90000", "12", "POL", "Einzel",
    ])
    quelle.chmod(0o600)
    quelle.write_text(
        quelle.read_text(encoding="utf-8") + zweite_zeile + "\n",
        encoding="utf-8",
    )
    quelle.chmod(0o444)
    quelle_sha256 = sha256(quelle.read_bytes()).hexdigest()
    register_pfad = fall / "eingang.json"
    register = json.loads(register_pfad.read_text(encoding="utf-8"))
    eintrag = next(
        wert for wert in register["quellen"] if wert["datei"] == quelle.name
    )
    eintrag.update(sha256=quelle_sha256, bytes=quelle.stat().st_size)
    register_pfad.write_text(json.dumps(register, sort_keys=True), encoding="utf-8")

    nachweise = fall / "abgeleitet" / "abnahmenachweise"
    spec_pfad = nachweise / "transformationsspec.json"
    ergebnis_pfad = nachweise / "transformation.json"
    spec = json.loads(spec_pfad.read_text(encoding="utf-8"))
    spec["quelle_sha256"] = quelle_sha256
    spec_pfad.write_text(json.dumps(spec, sort_keys=True), encoding="utf-8")
    ergebnis = json.loads(ergebnis_pfad.read_text(encoding="utf-8"))
    ergebnis.update(
        spec_sha256=sha256(spec_pfad.read_bytes()).hexdigest(),
        quelle_sha256=quelle_sha256,
        zeilen_quelle=2,
        zeilen_ziel=2,
    )
    ergebnis_pfad.write_text(json.dumps(ergebnis, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert (bericht.exit_code, bericht.status) == (20, "failed")
    assert bericht.errors[0]["code"] == "transformation_contract"
    assert "B1 und Migrationssuite geprueften Bestandszeilenzahl" in (
        bericht.errors[0]["message"]
    )


def test_bestands_scope_blockiert_jedes_nachtraeglich_geaenderte_pflichtartefakt(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    ledger = json.loads(
        (fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json")
        .read_text(encoding="utf-8")
    )

    for rolle, eintrag in ledger["summary"]["bestandsbelege"].items():
        artefakt = fall / eintrag["pfad"]
        original = artefakt.read_bytes()
        artefakt.write_bytes(original + b"\n")
        try:
            g2 = _p9_annahme(
                fall, "G-2", f"darf geaenderten Beleg {rolle} nicht annehmen"
            )
        finally:
            artefakt.write_bytes(original)

        assert g2.exit_code == 20, rolle
        assert g2.errors[0]["code"] == "vorbedingung", rolle
        assert rolle in g2.errors[0]["message"], rolle
        assert "SHA-256" in g2.errors[0]["message"], rolle


@pytest.mark.parametrize(
    "rolle", ["b1_ledger", "migrationssuite", "abnahmebericht"]
)
def test_bestands_scope_blockiert_jeden_fehlenden_pflichtbeleg(
    tmp_path: Path,
    rolle: str,
):
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(
        ledger_pfad.read_text(encoding="utf-8")
    )
    if rolle == "abnahmebericht":
        ledger_pfad.unlink()
    else:
        (fall / ledger["summary"]["bestandsbelege"][rolle]["pfad"]).unlink()

    g2 = _p9_annahme(
        fall, "G-2", f"darf fehlenden Bestandsbeleg {rolle} nicht annehmen"
    )

    assert g2.exit_code == 20
    assert g2.errors[0]["code"] == "vorbedingung"
    assert rolle in g2.errors[0]["message"]
    assert "fehlt" in g2.errors[0]["message"]


@pytest.mark.parametrize("aenderung", ["geaendert", "geloescht"])
def test_g2_blockiert_veraltete_belege_nach_portfolio_drift(
    tmp_path: Path,
    aenderung: str,
):
    fall = _bereite_bestandsfall(tmp_path)
    b1_ledger = json.loads(
        (fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json")
        .read_text(encoding="utf-8")
    )
    portfolio = Path(b1_ledger["summary"]["portfolio_input"])
    if not portfolio.is_absolute():
        portfolio = REPO_ROOT / portfolio
    if aenderung == "geaendert":
        portfolio.write_bytes(portfolio.read_bytes() + b"drift")
    else:
        portfolio.unlink()

    g2 = _p9_annahme(fall, "G-2", "darf alten B1-Stand nicht annehmen")

    assert g2.exit_code == 20
    assert "B1-Eingangsartefakt" in g2.errors[0]["message"]


def test_g2_loest_repo_relatives_portfolio_nicht_ueber_schattenkopie_auf():
    with tempfile.TemporaryDirectory(prefix=".todo-10-3-", dir=REPO_ROOT) as tmp:
        fall = _bereite_bestandsfall(Path(tmp))
        b1 = json.loads(
            (fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json")
            .read_text(encoding="utf-8")
        )
        portfolio_schluessel = b1["summary"]["portfolio_input"]
        assert not Path(portfolio_schluessel).is_absolute()
        portfolio = REPO_ROOT / portfolio_schluessel
        schattenkopie = fall / portfolio_schluessel
        schattenkopie.parent.mkdir(parents=True, exist_ok=True)
        schattenkopie.write_bytes(portfolio.read_bytes())
        portfolio.write_bytes(b"manipulierter echter Repo-Pfad")

        g2 = _p9_annahme(
            fall,
            "G-2",
            "darf eine Schattenkopie am falschen Aufloesungspfad nicht nutzen",
        )

        assert g2.exit_code == 20
        assert "B1-Eingangsartefakt" in g2.errors[0]["message"]


def test_g2_validiert_neu_gehashte_unvollstaendige_suite_semantisch(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    suite_pfad = fall / suite_eintrag["pfad"]
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    suite["vollstaendig_geprueft"] = False
    suite["pruefluecken"] = ["manipulierte Pruefluecke"]
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")
    neuer_hash = sha256(suite_pfad.read_bytes()).hexdigest()
    suite_eintrag["sha256"] = neuer_hash
    ledger["input_hashes"][suite_eintrag["pfad"]] = neuer_hash
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf neu gehashte unvollstaendige Suite nicht annehmen"
    )

    assert g2.exit_code == 20
    assert "vollstaendig gepruefte Migrationssuite" in g2.errors[0]["message"]


def test_g2_fuehrt_b1_auf_konsistent_neu_behauptetem_portfolio_erneut_aus(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    b1_pfad = diagnostics / "bestand_validate.gate.json"
    b1 = json.loads(b1_pfad.read_text(encoding="utf-8"))
    portfolio_schluessel = b1["summary"]["portfolio_input"]
    portfolio = Path(portfolio_schluessel)
    if not portfolio.is_absolute():
        portfolio = REPO_ROOT / portfolio
    portfolio.write_bytes(b"kein Parquet und kein gueltiger B1-Bestand")
    portfolio_hash = sha256(portfolio.read_bytes()).hexdigest()
    b1["input_hashes"][portfolio_schluessel] = portfolio_hash
    b1["summary"]["portfolio_sha256"] = portfolio_hash
    b1_pfad.write_text(json.dumps(b1, sort_keys=True), encoding="utf-8")

    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    suite["bestand_sha256"] = portfolio_hash
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    abnahme_pfad = diagnostics / "abnahmebericht.gate.json"
    abnahme = json.loads(abnahme_pfad.read_text(encoding="utf-8"))
    for rolle, pfad in (("b1_ledger", b1_pfad), ("migrationssuite", suite_pfad)):
        eintrag = abnahme["summary"]["bestandsbelege"][rolle]
        neuer_hash = sha256(pfad.read_bytes()).hexdigest()
        eintrag["sha256"] = neuer_hash
        abnahme["input_hashes"][eintrag["pfad"]] = neuer_hash
    abnahme_pfad.write_text(json.dumps(abnahme, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf einen neu behaupteten roten B1-Bestand nicht annehmen"
    )

    assert g2.exit_code == 20
    assert "nicht als Bestand lesbar" in g2.errors[0]["message"]


def test_g2_reproduziert_konsistent_neu_gehashten_abnahmebericht(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    bericht_pfad = fall / bericht_eintrag["pfad"]
    bericht_pfad.write_text(
        "<html><body>ABNAHME ROT / frei erfunden</body></html>\n",
        encoding="utf-8",
    )
    neuer_hash = sha256(bericht_pfad.read_bytes()).hexdigest()
    bericht_eintrag["sha256"] = neuer_hash
    ledger["summary"]["output_hashes"][bericht_eintrag["pfad"]] = neuer_hash
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf einen frei erfundenen Bericht nicht annehmen"
    )

    assert g2.exit_code == 20
    assert "deterministischen Erzeugung" in g2.errors[0]["message"]


def test_g2_blockiert_umkodierte_zeilenenden_im_abnahmebericht(
    tmp_path: Path,
):
    """Bytegenau heisst bytegenau — auch bei blosser Umkodierung.

    Der Vergleich las den Bericht frueher als Text ein; Pythons
    Universal-Newlines uebersetzten CRLF still nach LF, sodass eine
    umkodierte Fassung samt nachgezogenem Hash als "bytegenau
    reproduziert" durchging. Der Inhalt bleibt dabei sichtbar gleich —
    genau deshalb faellt es ohne Test niemandem auf.
    """
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    bericht_pfad = fall / bericht_eintrag["pfad"]

    original = bericht_pfad.read_bytes()
    umkodiert = original.replace(b"\n", b"\r\n")
    assert umkodiert != original, "Vorbedingung: der Bericht hat Zeilenumbrueche"
    bericht_pfad.write_bytes(umkodiert)
    neuer_hash = sha256(umkodiert).hexdigest()
    bericht_eintrag["sha256"] = neuer_hash
    ledger["summary"]["output_hashes"][bericht_eintrag["pfad"]] = neuer_hash
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf eine umkodierte Berichtsfassung nicht annehmen"
    )

    assert g2.exit_code == 20
    assert "deterministischen Erzeugung" in g2.errors[0]["message"]


def test_g2_blockiert_neu_gehashten_bericht_mit_zeilenverlust(
    tmp_path: Path,
):
    """Ein roter Renderer-Vertrag darf nicht unter altem Grün passieren."""
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    suite = json.loads(
        (fall / suite_eintrag["pfad"]).read_text(encoding="utf-8"))
    bericht_pfad = fall / bericht_eintrag["pfad"]
    erzeugung = ledger["summary"]["bericht_erzeugung"]
    erzeugung["transformation_ergebnis"]["zeilen_ziel"] = 0
    bericht_pfad.write_text(abnahmebericht.baue_bericht(
        titel=erzeugung["titel"],
        stichtag_1=erzeugung["stichtag_1"],
        stichtag_2=erzeugung["stichtag_2"],
        suite=suite,
        spec=TransformationsSpec.model_validate(erzeugung["spec"]),
        transformation_ergebnis=erzeugung["transformation_ergebnis"],
        bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
        bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
    ), encoding="utf-8")
    neuer_hash = sha256(bericht_pfad.read_bytes()).hexdigest()
    bericht_eintrag["sha256"] = neuer_hash
    ledger["summary"]["output_hashes"][bericht_eintrag["pfad"]] = neuer_hash
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf Zeilenverlust nicht aus alter Summary begruenen"
    )

    assert g2.exit_code == 20
    assert "gebundenen Transformationsergebnis" in g2.errors[0]["message"]


def test_g2_blockiert_entfernte_renderer_rolle_samt_pflichtartefakt(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    spec_eintrag = ledger["summary"]["renderer_artefakte"].pop("spec")
    ledger["input_hashes"].pop(spec_eintrag["pfad"])
    (fall / spec_eintrag["pfad"]).unlink()
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf fehlendes Berichtsartefakt nicht uebergehen"
    )

    assert g2.exit_code == 20
    assert "exakt die Renderer-Artefakte" in g2.errors[0]["message"]


def test_g2_blockiert_neu_gehashtes_rotes_transformationsartefakt_bei_gruener_kopie(
    tmp_path: Path,
):
    """Dateiinhalt statt der frei editierbaren Renderer-Kopie entscheidet."""
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    eintrag = ledger["summary"]["renderer_artefakte"][
        "transformation_ergebnis"
    ]
    transformation_pfad = fall / eintrag["pfad"]
    transformation = json.loads(
        transformation_pfad.read_text(encoding="utf-8")
    )
    transformation["zeilen_ziel"] = 0
    transformation_pfad.write_text(
        json.dumps(transformation, sort_keys=True), encoding="utf-8"
    )
    neuer_hash = sha256(transformation_pfad.read_bytes()).hexdigest()
    eintrag["sha256"] = neuer_hash
    ledger["input_hashes"][eintrag["pfad"]] = neuer_hash
    # bericht_erzeugung und der bereits gruene HTML-Bericht bleiben unveraendert.
    assert ledger["summary"]["bericht_erzeugung"][
        "transformation_ergebnis"
    ]["zeilen_ziel"] == 1
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall,
        "G-2",
        "darf rotes Transformationsartefakt nicht aus gruener Kopie begruenen",
    )

    assert g2.exit_code == 20
    meldung = g2.errors[0]["message"]
    assert "gebundenen Transformationsergebnis" in meldung
    assert "Zeilenverlust blockiert" in meldung


def test_g2_blockiert_pfadalias_auf_vorbericht_als_fehlenden_nachbericht(
    tmp_path: Path,
):
    """Zwei Rollen duerfen nicht per ``./`` dieselben Bytes vortaeuschen."""
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    renderer = ledger["summary"]["renderer_artefakte"]
    vor_eintrag = renderer["bestandsbericht_vor"]
    nach_eintrag = renderer["bestandsbericht_nach"]
    (fall / nach_eintrag["pfad"]).unlink()

    vor_pfad = Path(vor_eintrag["pfad"])
    alias = f"{vor_pfad.parent.as_posix()}/./{vor_pfad.name}"
    ledger["input_hashes"].pop(nach_eintrag["pfad"])
    nach_eintrag.update(pfad=alias, sha256=vor_eintrag["sha256"])
    ledger["input_hashes"][alias] = vor_eintrag["sha256"]

    erzeugung = ledger["summary"]["bericht_erzeugung"]
    erzeugung["bestandsbericht_nach"] = alias
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    suite = json.loads(
        (fall / suite_eintrag["pfad"]).read_text(encoding="utf-8")
    )
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    bericht_pfad = fall / bericht_eintrag["pfad"]
    bericht_pfad.write_text(
        abnahmebericht.baue_bericht(
            titel=erzeugung["titel"],
            stichtag_1=erzeugung["stichtag_1"],
            stichtag_2=erzeugung["stichtag_2"],
            suite=suite,
            spec=TransformationsSpec.model_validate(erzeugung["spec"]),
            transformation_ergebnis=erzeugung["transformation_ergebnis"],
            bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
            bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
        ),
        encoding="utf-8",
    )
    neuer_hash = sha256(bericht_pfad.read_bytes()).hexdigest()
    bericht_eintrag["sha256"] = neuer_hash
    ledger["summary"]["output_hashes"] = {
        bericht_eintrag["pfad"]: neuer_hash
    }
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall,
        "G-2",
        "darf fehlenden Nachbericht nicht durch Pfadalias ersetzen",
    )

    assert g2.exit_code == 20
    assert "kein kanonischer Fallpfad" in g2.errors[0]["message"]


def test_g2_blockiert_hardlink_zwischen_vor_und_nachbericht(
    tmp_path: Path,
):
    """Zwei Pfade auf dasselbe Dateiobjekt sind keine zwei Pflichtbelege."""
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    renderer = ledger["summary"]["renderer_artefakte"]
    vor_eintrag = renderer["bestandsbericht_vor"]
    nach_eintrag = renderer["bestandsbericht_nach"]
    vor_pfad = fall / vor_eintrag["pfad"]
    nach_pfad = fall / nach_eintrag["pfad"]
    nach_pfad.unlink()
    nach_pfad.hardlink_to(vor_pfad)
    nach_eintrag["sha256"] = vor_eintrag["sha256"]
    ledger["input_hashes"][nach_eintrag["pfad"]] = vor_eintrag["sha256"]
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall,
        "G-2",
        "darf einen Hardlink nicht als zweiten Bestandsbericht annehmen",
    )

    assert g2.exit_code == 20
    assert "physisch verschiedene Dateien" in g2.errors[0]["message"]


def test_g2_blockiert_bestandsberichtrolle_auf_abnahmebericht_output(
    tmp_path: Path,
):
    """Der HTML-Output darf keine fehlende Vor-/Nachrolle ersetzen."""
    fall = _bereite_bestandsfall(tmp_path)
    ledger_pfad = (
        fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    )
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    renderer = ledger["summary"]["renderer_artefakte"]
    nach_eintrag = renderer["bestandsbericht_nach"]
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    ledger["input_hashes"].pop(nach_eintrag["pfad"])
    renderer["bestandsbericht_nach"] = dict(bericht_eintrag)

    erzeugung = ledger["summary"]["bericht_erzeugung"]
    erzeugung["bestandsbericht_nach"] = bericht_eintrag["pfad"]
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    suite = json.loads(
        (fall / suite_eintrag["pfad"]).read_text(encoding="utf-8")
    )
    bericht_pfad = fall / bericht_eintrag["pfad"]
    bericht_pfad.write_text(
        abnahmebericht.baue_bericht(
            titel=erzeugung["titel"],
            stichtag_1=erzeugung["stichtag_1"],
            stichtag_2=erzeugung["stichtag_2"],
            suite=suite,
            spec=TransformationsSpec.model_validate(erzeugung["spec"]),
            transformation_ergebnis=erzeugung["transformation_ergebnis"],
            bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
            bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
        ),
        encoding="utf-8",
    )
    neuer_hash = sha256(bericht_pfad.read_bytes()).hexdigest()
    bericht_eintrag["sha256"] = neuer_hash
    renderer["bestandsbericht_nach"]["sha256"] = neuer_hash
    ledger["input_hashes"][bericht_eintrag["pfad"]] = neuer_hash
    ledger["summary"]["output_hashes"] = {
        bericht_eintrag["pfad"]: neuer_hash
    }
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall,
        "G-2",
        "darf den Output nicht als fehlenden Nachbericht annehmen",
    )

    assert g2.status == "failed"
    assert g2.exit_code != 0
    assert "Eingabe- und Outputrollen" in g2.errors[0]["message"]


def test_g2_blockiert_neu_gehashte_rote_suite_trotz_alter_gruener_summary(
    tmp_path: Path,
):
    """G-2 muss das Suiteurteil selbst statt aus dem Ledger lesen."""
    fall = _bereite_bestandsfall(tmp_path)
    diagnostics = fall / "abgeleitet" / "diagnostics"
    ledger_pfad = diagnostics / "abnahmebericht.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    suite_eintrag = ledger["summary"]["bestandsbelege"]["migrationssuite"]
    bericht_eintrag = ledger["summary"]["bestandsbelege"]["abnahmebericht"]
    suite_pfad = fall / suite_eintrag["pfad"]
    bericht_pfad = fall / bericht_eintrag["pfad"]

    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    urteil = suite["vertraege"][0]
    pruefung = urteil["pruefungen"][0]
    pruefung["erwartet"] += 500.0
    pruefung["residuum"] = pruefung["system"] - pruefung["erwartet"]
    pruefung["ok"] = False
    urteil["bestanden"] = False
    suite["bestanden"], suite["fehlgeschlagen"] = 0, 1
    suite["suite_bestanden"] = False
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    erzeugung = ledger["summary"]["bericht_erzeugung"]
    assert erzeugung["spec"] is not None
    bericht_pfad.write_text(abnahmebericht.baue_bericht(
        titel=erzeugung["titel"],
        stichtag_1=erzeugung["stichtag_1"],
        stichtag_2=erzeugung["stichtag_2"],
        suite=suite,
        spec=TransformationsSpec.model_validate(erzeugung["spec"]),
        transformation_ergebnis=erzeugung["transformation_ergebnis"],
        bestandsbericht_vor=erzeugung["bestandsbericht_vor"],
        bestandsbericht_nach=erzeugung["bestandsbericht_nach"],
    ), encoding="utf-8")

    for rolle, pfad in (
        ("migrationssuite", suite_pfad),
        ("abnahmebericht", bericht_pfad),
    ):
        eintrag = ledger["summary"]["bestandsbelege"][rolle]
        neuer_hash = sha256(pfad.read_bytes()).hexdigest()
        eintrag["sha256"] = neuer_hash
        if rolle == "migrationssuite":
            ledger["input_hashes"][eintrag["pfad"]] = neuer_hash
        else:
            ledger["summary"]["output_hashes"][eintrag["pfad"]] = neuer_hash
    ledger_pfad.write_text(json.dumps(ledger, sort_keys=True), encoding="utf-8")

    g2 = _p9_annahme(
        fall, "G-2", "darf rote Suite nicht aus alter Summary begruenen"
    )

    assert g2.exit_code == 20
    assert "suite_bestanden" in g2.errors[0]["message"]
    assert "Migrationssuite ist nicht bestanden" in g2.errors[0]["message"]


def test_abnahmebericht_blockiert_unvollstaendige_suite_vor_gruenem_beleg(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    urteil = suite["vertraege"][0]
    urteil["pruefungen"] = [
        pruefung for pruefung in urteil["pruefungen"]
        if pruefung["groesse"] != "bjb_stichtag_1"
    ]
    urteil["nicht_geprueft"] = ["bjb_stichtag_1"]
    suite["vollstaendig_geprueft"] = False
    suite["pruefluecken"] = [
        "bjb_stichtag_1: bei 1 von 1 Verträgen NICHT geprüft "
        "(kein gelieferter Erwartungswert oder abgebrochene Prüfung)."
    ]
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert bericht.exit_code == 20
    assert bericht.errors[0]["code"] == "suite_scope_contract"
    assert "vollstaendig gepruefte Migrationssuite" in bericht.errors[0]["message"]


def test_abnahmebericht_verwechselt_portfolio_rolle_nicht_mit_b1_nebeneingang(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    b1_pfad = fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
    b1 = json.loads(b1_pfad.read_text(encoding="utf-8"))
    config_pfad = REPO_ROOT / "configs" / "bestand_klv.toml"
    config_hash = sha256(config_pfad.read_bytes()).hexdigest()
    b1["input_hashes"]["configs/bestand_klv.toml"] = config_hash
    b1_pfad.write_text(json.dumps(b1, sort_keys=True), encoding="utf-8")
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    suite["bestand_sha256"] = config_hash
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert bericht.exit_code == 20
    assert bericht.errors[0]["code"] == "b1_contract"
    assert "verschiedene Bestaende" in bericht.errors[0]["message"]


def test_abnahmebericht_blockiert_veralteten_suite_systemstand(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    suite["system"]["commit"] = "0" * 40
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert bericht.exit_code == 20
    assert bericht.errors[0]["code"] == "suite_scope_contract"
    assert "aktuellen Systemstand" in bericht.errors[0]["message"]


def test_abnahmebericht_blockiert_teilpruefung_des_b1_portfolios(
    tmp_path: Path,
):
    fall = _bereite_bestandsfall(tmp_path)
    lauf = fall / "abgeleitet" / "bestand"
    assert cli_fortschreibung.main([
        "--config", str(REPO_ROOT / "configs" / "bestand_klv.toml"),
        "--bis", "2020-01-01",
        "--out-dir", str(lauf),
    ]) == 0
    portfolio = lauf / "bestand_gesamt.parquet"
    diagnostics = fall / "abgeleitet" / "diagnostics"
    b1 = bestand_validate.main([
        "--portfolio", str(portfolio),
        "--historie", str(lauf / "historie.parquet"),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diagnostics),
    ])
    assert b1.exit_code == 0
    assert b1.summary["portfolio_zeilen"] > 1
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite = json.loads(suite_pfad.read_text(encoding="utf-8"))
    suite["bestand_sha256"] = sha256(portfolio.read_bytes()).hexdigest()
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    bericht = _abnahmebericht(fall)

    assert bericht.exit_code == 20
    assert bericht.errors[0]["code"] == "b1_contract"
    assert "Suite-Pruefmenge" in bericht.errors[0]["message"]


def test_o3_bleibt_bei_gescheitertem_belegschreiben_nicht_gruen(
    tmp_path: Path,
    monkeypatch,
):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))

    def _schreibfehler(*_args, **_kwargs):
        raise OSError("Belegziel nicht beschreibbar")

    monkeypatch.setattr(
        generation_golden, "schreibe_o3_beleg", _schreibfehler
    )
    ergebnis = _o3_tg2012(fall)

    assert ergebnis.exit_code == 20
    assert ergebnis.status == "failed"
    assert ergebnis.errors[0]["code"] == "o3_beleg"
    diagnostics = fall / "abgeleitet" / "diagnostics"
    assert list(diagnostics.glob("generation_golden.*.beleg.json")) == []
    ledger = json.loads(
        (diagnostics / "generation_golden.gate.json").read_text(
            encoding="utf-8"
        )
    )
    assert ledger["status"] == "failed"


def test_g2_blockt_wenn_bei_mehreren_generationen_ein_o3_beleg_fehlt(
    tmp_path: Path,
):
    fall = _bereite_fall(tmp_path, ("klv/tg2012", "klv/tg2013"))
    assert _o3_tg2012(fall).exit_code == 0

    g2 = _p9_annahme(fall, "G-2", "darf nicht angenommen werden")
    assert g2.exit_code == 20
    [fehler] = g2.errors
    assert fehler["code"] == "vorbedingung"
    assert "O3-Beleg fehlt fuer ['klv/tg2013']" in fehler["message"]


def test_g2_blockt_einen_beleg_fuer_fremde_generation(tmp_path: Path):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    o3_ergebnis = _o3_tg2012(fall)
    assert o3_ergebnis.exit_code == 0
    beleg = json.loads(
        Path(o3_ergebnis.paths["o3_beleg"]).read_text(encoding="utf-8")
    )
    fremde_summary = {**beleg["summary"], "generation": "klv/tg2013"}
    schreibe_o3_beleg(
        fall / "abgeleitet" / "diagnostics",
        gate_version=beleg["gate_version"],
        status=beleg["status"],
        exit_code=beleg["exit_code"],
        generation="klv/tg2013",
        abox_sha256=beleg["abox_sha256"],
        system=beleg["system"],
        input_hashes=beleg["input_hashes"],
        summary=fremde_summary,
    )

    g2 = _p9_annahme(fall, "G-2", "darf nicht angenommen werden")
    assert g2.exit_code == 20
    assert "fremde Generationen ['klv/tg2013']" in g2.errors[0]["message"]


def test_g2_blockt_o3_beleg_eines_anderen_abox_stands(tmp_path: Path):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0

    abox = lade(fall)
    abox.generationen[0].anmerkungen.append("neuer fachlicher Stand")
    speichere(abox, fall)
    assert o1([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
    ]).exit_code == 0
    assert _p9_annahme(
        fall, "G-1", "geaenderten A-Box-Stand geprueft"
    ).exit_code == 0

    g2 = _p9_annahme(fall, "G-2", "darf nicht angenommen werden")
    assert g2.exit_code == 20
    assert "A-Box-Stand abweichend" in g2.errors[0]["message"]


def test_g2_blockt_o3_beleg_eines_anderen_systemstands(
    tmp_path: Path,
    monkeypatch,
):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0

    abweichend = dict(gate_entscheid.systemstand(REPO_ROOT))
    alt = abweichend["quellcode_sha256"]
    abweichend["quellcode_sha256"] = "0" * 64 if alt != "0" * 64 else "1" * 64
    monkeypatch.setattr(gate_entscheid, "systemstand", lambda _repo: abweichend)

    g2 = _p9_annahme(fall, "G-2", "darf nicht angenommen werden")
    assert g2.exit_code == 20
    assert "Systemstand abweichend" in g2.errors[0]["message"]


def test_g2_blockt_nachtraeglich_geaenderte_o3_erwartungsdatei(
    tmp_path: Path,
):
    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0
    erwartung = (
        verzeichnis_der_generation(fall, "klv/tg2012")
        / "Kalkulation_table_values.csv"
    )
    erwartung.write_bytes(erwartung.read_bytes() + b"\n")

    g2 = _p9_annahme(fall, "G-2", "darf nicht angenommen werden")
    assert g2.exit_code == 20
    assert "O3-Eingangsartefakte abweichend" in g2.errors[0]["message"]


def test_ungueltige_generations_id_im_beleg_wird_befund_statt_crash(
    tmp_path: Path,
):
    pfad = tmp_path / f"generation_golden.x.{'a' * 64}.beleg.json"
    pfad.write_text(json.dumps({
        "generation": "!!!",
        "beleg_sha256": "a" * 64,
    }), encoding="utf-8")

    _beleg, fehler = pruefe_o3_beleg(pfad)
    assert any("Knoten-ID" in meldung for meldung in fehler)
    assert any("Dateiname nicht ableitbar" in meldung for meldung in fehler)
