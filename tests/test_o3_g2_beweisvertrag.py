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
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import rechner_pipeline.gates.generation_golden as generation_golden
from rechner_pipeline.bestand import cli_fortschreibung, cli_report
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import abnahmebericht, bestand_validate, gate_entscheid
from rechner_pipeline.gates._fall_scope import pruefe_scope_beleg
from rechner_pipeline.gates._provenienz import (
    pruefe_o3_beleg,
    schreibe_o3_beleg,
)
from rechner_pipeline.gates.abox_validate import main as o1
from rechner_pipeline.gates.extract import main as extract
from rechner_pipeline.gates.generation_golden import main as o3
from rechner_pipeline.kern import Rechenkern
from rechner_pipeline.kern.model_point import KLV_DEFAULT
from rechner_pipeline.ontologie.abox import lade, speichere
from rechner_pipeline.ontologie.aussage import Provenienz, belegt
from rechner_pipeline.ontologie.transformation import (
    FeldMapping,
    TransformationsSpec,
    ZIEL_PFLICHT,
)
from rechner_pipeline.ontologie.tbox import (
    ABox,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Quelle,
    Tarifgeneration,
)
from rechner_pipeline.quellen.vorverdichtung import verzeichnis_der_generation
from rechner_pipeline.qa.migrationssuite import VertragsPruefung, pruefe_bestand
from rechner_pipeline.spez.erzeugen import baue_spez
from rechner_pipeline.spez.validierung import speichere_spez

REPO_ROOT = Path(__file__).resolve().parents[1]
XLSM = REPO_ROOT / "tests" / "fixtures" / "Tarifrechner_KLV_TG2012.xlsm"
ZEIT = "2026-08-20T08:00:00+00:00"


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


def _generation(
    generation: str,
    quelle: Quelle,
    provenienz: Provenienz,
) -> Tarifgeneration:
    modellpunkt = asdict(KLV_DEFAULT)
    for feld in ("x", "sex", "n", "t", "sum_insured", "zw"):
        modellpunkt.pop(feld)
    parameter = {
        feld: belegt(modellpunkt[feld], [provenienz])
        for feld in PFLICHT_PARAMETER
    }
    name = generation.rsplit("/", 1)[-1].upper()
    return Tarifgeneration(
        id=generation,
        name=name,
        familie="klv",
        quellen=[quelle],
        zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
    )


def _bereite_fall(
    tmp_path: Path,
    generationen: tuple[str, ...],
    *,
    scope: str = "tarif",
) -> Path:
    """Echten TG2012-Input vorbereiten; weitere Generationen teilen die Werte."""
    assert XLSM.is_file(), "verpflichtendes synthetisches XLSM-Fixture fehlt"
    fall = tmp_path / "fall"
    anlegen(fall, scope=scope)
    registrieren(fall, XLSM)
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    [eintrag] = register["quellen"]
    quelle = Quelle(
        datei=eintrag["datei"],
        sha256=eintrag["sha256"],
        art="tarifrechner",
    )
    provenienz = Provenienz(
        quelle_datei=quelle.datei,
        quelle_sha256=quelle.sha256,
        fundstelle="Kalkulation!$D$4:$H$5",
        akteur="test/o3-g2-e2e@abc1234",
        erhoben_am=ZEIT,
    )

    vorverdichtung = verzeichnis_der_generation(fall, "klv/tg2012")
    extraktion = extract([
        "--repo-root", str(REPO_ROOT),
        "--input", str(fall / "eingang" / quelle.datei),
        "--out-dir", str(vorverdichtung),
        "--adapter", "excel",
        "--export-backend", "openpyxl",
    ])
    assert extraktion.exit_code == 0

    abox = ABox(
        fall=str(fall),
        generationen=[
            _generation(generation, quelle, provenienz)
            for generation in generationen
        ],
    )
    speichere(abox, fall)
    # Nur TG2012 wird in diesen Tests mit dem echten Quellrechner gefahren.
    # Der Mehrgenerationentest muss gerade daran scheitern, dass fuer die
    # zweite A-Box-Generation kein O3-Beleg existiert.
    speichere_spez(baue_spez(abox, "klv/tg2012"), fall)
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


def _bereite_bestands_scope_beleg(tmp_path: Path) -> tuple[Path, Path]:
    """Echte Producer von O1/O3/B1/Abnahmebericht bis zum Scope-Beleg."""
    fall = _bereite_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    assert _o3_tg2012(fall).exit_code == 0

    lauf = fall / "abgeleitet" / "bestand"
    assert cli_fortschreibung.main([
        "--config", str(REPO_ROOT / "configs" / "bestand_klv.toml"),
        "--bis", "2020-01-01",
        "--out-dir", str(lauf),
    ]) == 0
    ziel = lauf / "bestand_gesamt.parquet"
    diagnostics = fall / "abgeleitet" / "diagnostics"
    b1 = bestand_validate.main([
        "--portfolio", str(ziel),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(diagnostics),
    ])
    assert b1.exit_code == 0

    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    [quelle] = register["quellen"]
    transformation = fall / "abgeleitet" / "transformation"
    transformation.mkdir(parents=True)
    spec = TransformationsSpec(
        quelle_datei=quelle["datei"],
        quelle_sha256=quelle["sha256"],
        akteur="test/bestands-scope-e2e@abc1234",
        erhoben_am=ZEIT,
        felder=[
            FeldMapping(
                ziel=feld,
                typ="direkt",
                quellen=[feld],
                begruendung="synthetischer E2E-Durchstich des Scope-Vertrags",
            )
            for feld in ZIEL_PFLICHT
        ],
    )
    spec_pfad = transformation / "bestand.spec.json"
    spec_pfad.write_text(spec.model_dump_json(), encoding="utf-8")
    ziel_hash = sha256(ziel.read_bytes()).hexdigest()
    ergebnis_pfad = transformation / "bestand.ergebnis.json"
    ergebnis_pfad.write_text(json.dumps({
        "schema_version": 1,
        "spec_sha256": sha256(spec_pfad.read_bytes()).hexdigest(),
        "quelle_sha256": quelle["sha256"],
        "quellspalten": list(ZIEL_PFLICHT),
        "ziel_datei": str(ziel.relative_to(fall)),
        "ziel_sha256": ziel_hash,
        "zeilen_quelle": len(read_portfolio(ziel)),
        "zeilen_ziel": len(read_portfolio(ziel)),
        "befunde": [],
    }, sort_keys=True), encoding="utf-8")

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
    )
    suite_pfad = fall / "abgeleitet" / "suite.json"
    suite_pfad.write_text(json.dumps(suite, sort_keys=True), encoding="utf-8")

    berichte = fall / "abgeleitet" / "berichte"
    berichte.mkdir(parents=True)
    vor = berichte / "bestand-vor.html"
    nach = berichte / "bestand-nach.html"
    assert cli_report.main([
        "--portfolio", str(lauf / "bestand.parquet"),
        "--out", str(vor),
        "--stichtage", "2026-01-01",
        "--titel", "Bestand vor Migration",
    ]) == 0
    assert cli_report.main([
        "--portfolio", str(ziel),
        "--out", str(nach),
        "--stichtage", "2027-01-01",
        "--titel", "Bestand nach Migration",
    ]) == 0
    assert "2026-01-01" in vor.read_text(encoding="utf-8")
    assert "2027-01-01" in nach.read_text(encoding="utf-8")

    bericht = abnahmebericht.main([
        "--fall", str(fall),
        "--suite", str(suite_pfad),
        "--titel", "Bestands-Scope E2E",
        "--stichtag-1", "2026-01-01",
        "--stichtag-2", "2027-01-01",
        "--spec", str(spec_pfad),
        "--transformation-ergebnis", str(ergebnis_pfad),
        "--bestandsbericht-vor", str(vor),
        "--bestandsbericht-nach", str(nach),
        "--repo-root", str(REPO_ROOT),
    ])
    assert bericht.exit_code == 0
    scope_beleg = Path(bericht.paths["scope_beleg"])
    daten, fehler = pruefe_scope_beleg(
        scope_beleg, fall=fall, pruefe_artefakte=True
    )
    assert fehler == [] and daten is not None
    return fall, suite_pfad


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


def test_bestands_scope_bindet_alle_dag_belege_bis_g2(tmp_path: Path):
    fall, _suite = _bereite_bestands_scope_beleg(tmp_path)

    g2 = _p9_annahme(fall, "G-2", "Bestandsbeweise vollstaendig geprueft")

    assert g2.exit_code == 0
    snapshot = json.loads(Path(g2.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["fall_scope"] == "bestand"
    assert set(snapshot["pflichtbelege"]) == {
        "o1_ledger", "g1_snapshot", "o3_belege", "transformationsspec",
        "transformationsergebnis", "b1_ledger", "migrationssuite",
        "bestandsbericht_vor", "bestandsbericht_nach", "abnahmebericht",
    }
    assert all(snapshot["pflichtbelege"].values())


def test_bestands_scope_blockiert_jedes_nachtraeglich_geaenderte_pflichtartefakt(
    tmp_path: Path,
):
    fall, _suite_pfad = _bereite_bestands_scope_beleg(tmp_path)
    [scope_beleg_pfad] = list(
        (fall / "abgeleitet" / "diagnostics").glob(
            "abnahmebericht.*.beleg.json"
        )
    )
    scope_beleg = json.loads(scope_beleg_pfad.read_text(encoding="utf-8"))

    for rolle, eintrag in scope_beleg["artefakte"].items():
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
