"""Negativvertraege fuer Ledger, P9-Kette und menschliche Freigabe.

Die Tests bauen eine vollstaendige synthetische A-Box, echtes P-Q3 und einen
schema-validen P-K1-Beleg.  A-M4 erreicht dadurch wirklich den A-Q1-Lesepfad;
manipulierte Snapshots duerfen nicht schon an einer irrelevanten fehlenden
Vorbedingung scheitern.

Knoten: klv
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

import pytest

from rechner_pipeline.fall import anlegen, registrieren
from tests.zeichnung_fixture import VA, standard_ordnung
from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates._provenienz import (
    O3_BELEG_GATE_VERSION,
    schreibe_pk1_beleg,
    systemstand,
)
from rechner_pipeline.gates._common import load_gate_ledger, run_command
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.kern.model_point import KLV_DEFAULT
from rechner_pipeline.models.schemas import P9Snapshot, p9_snapshot_sha256
from rechner_pipeline.ontologie.abox import speichere
from rechner_pipeline.ontologie.aussage import Provenienz, belegt
from rechner_pipeline.ontologie.tbox import (
    ABox,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Quelle,
    Tarifgeneration,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ZEIT = "2026-08-20T14:00:00+00:00"


def _schluessel(pfad: Path, byte: bytes = b"k") -> Path:
    pfad.write_bytes(byte * 64)
    pfad.chmod(0o600)
    return pfad


def _fall(tmp_path: Path) -> Path:
    fall = tmp_path / "fall"
    anlegen(fall)
    quelle_original = tmp_path / "quelle.xlsm"
    quelle_original.write_bytes(b"synthetische quelle")
    registrieren(fall, quelle_original)
    [eintrag] = json.loads(
        (fall / "eingang.json").read_text(encoding="utf-8")
    )["quellen"]
    quelle = Quelle(
        datei=eintrag["datei"], sha256=eintrag["sha256"], art="tarifrechner"
    )
    provenienz = Provenienz(
        quelle_datei=quelle.datei,
        quelle_sha256=quelle.sha256,
        fundstelle="Kalkulation!A1",
        akteur="test/am4-manipulationsschutz@abc1234",
        erhoben_am=ZEIT,
    )
    modellpunkt = asdict(KLV_DEFAULT)
    for feld in ("x", "sex", "n", "t", "sum_insured", "zw"):
        modellpunkt.pop(feld)
    parameter = {
        feld: belegt(modellpunkt[feld], [provenienz])
        for feld in PFLICHT_PARAMETER
    }
    abox = ABox(
        fall=str(fall),
        generationen=[Tarifgeneration(
            id="klv/tg2012",
            name="TG2012",
            familie="klv",
            quellen=[quelle],
            zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
        )],
    )
    speichere(abox, fall)
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return fall


def _p9(fall: Path, key: Path | None, gate: str, entscheid: str = "angenommen"):
    argv = [
        "--fall", str(fall),
        "--gate", gate,
        "--entscheid", entscheid,
        "--rolle", VA,
        "--entscheider", "fachrolle",
        "--begruendung", f"{gate} {entscheid} geprueft",
        "--repo-root", str(REPO_ROOT),
    ]
    if key is not None:
        # Die Ordnung liegt NEBEN dem Fall (ausserhalb), auch wenn der
        # Schluessel absichtlich falsch liegt — geprueft wird der Schluessel.
        ordnung = standard_ordnung(fall.parent, key)
        argv.extend(["--freigabe-schluessel", str(key),
                     "--zeichnungsordnung", str(ordnung)])
    return gate_entscheid.main(argv)


def _o3_beleg(fall: Path) -> None:
    abox_pfad = fall / "abgeleitet" / "abox" / "abox.json"
    abox_hash = sha256(abox_pfad.read_bytes()).hexdigest()
    stand = systemstand(REPO_ROOT)
    schreibe_pk1_beleg(
        fall / "abgeleitet" / "diagnostics",
        gate_version=O3_BELEG_GATE_VERSION,
        status="passed",
        exit_code=0,
        generation="klv/tg2012",
        abox_sha256=abox_hash,
        system=stand,
        input_hashes={"abgeleitet/abox/abox.json": abox_hash},
        summary={
            "generation": "klv/tg2012",
            "abox_sha256": abox_hash,
            "system": stand,
        },
    )


def _bereit_fuer_g2(tmp_path: Path) -> tuple[Path, Path, Path]:
    fall = _fall(tmp_path)
    key = _schluessel(tmp_path / "p9.key")
    aq1 = _p9(fall, key, "A-Q1")
    assert aq1.exit_code == 0
    # A-M1 geht A-M4 voraus (ADR-010); der Manipulationsschutz-Fall ist
    # tarif-Scope, dort traegt A-M1 keine eigenen Belegrollen.
    assert _p9(fall, key, "A-M1").exit_code == 0
    _o3_beleg(fall)
    return fall, key, Path(aq1.paths["snapshot"])


@pytest.mark.parametrize(
    "manipulation",
    ["minimal", "gate", "command", "version", "required_typ", "hash_key"],
)
def test_annahme_lehnt_manipulierten_pq3_ledger_ab(
    tmp_path: Path, manipulation: str
) -> None:
    fall = _fall(tmp_path)
    key = _schluessel(tmp_path / "p9.key")
    ledger = fall / "abgeleitet" / "diagnostics" / "abox_validate.gate.json"
    daten = json.loads(ledger.read_text(encoding="utf-8"))
    if manipulation == "minimal":
        daten = {
            "status": "passed",
            "input_hashes": {"beliebig": sha256(
                (fall / "abgeleitet" / "abox" / "abox.json").read_bytes()
            ).hexdigest()},
        }
    elif manipulation == "gate":
        daten["gate"] = "P-K1.generations-golden-master"
    elif manipulation == "command":
        daten["command"] = "generation_golden"
    elif manipulation == "version":
        daten["gate_version"] = "999.0.0"
    elif manipulation == "required_typ":
        daten["required"] = "true"
    else:
        daten["input_hashes"]["abox"] = daten["input_hashes"].pop(
            "abgeleitet/abox/abox.json"
        )
    ledger.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-Q1")

    assert result.exit_code == 20
    assert result.errors[0]["code"] == "vorbedingung"
    assert "Ledger-/Provenienzvertrag" in result.errors[0]["message"]
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []


@pytest.mark.parametrize("manipulation", ["inhalt", "dateiname", "signatur"])
def test_am4_lehnt_manipulierten_aq1_snapshot_ab(
    tmp_path: Path, manipulation: str
) -> None:
    fall, key, snapshot_pfad = _bereit_fuer_g2(tmp_path)
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    if manipulation == "inhalt":
        daten["begruendung"] = "nachtraeglich geschoent"
        snapshot_pfad.write_text(json.dumps(daten), encoding="utf-8")
    elif manipulation == "dateiname":
        snapshot_pfad.rename(snapshot_pfad.with_name(f"A-Q1-{'f' * 64}.json"))
    else:
        daten["freigabe"]["signatur"] = "0" * 64
        daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
        neu = snapshot_pfad.with_name(
            gate_entscheid._snapshot_dateiname("A-Q1", daten["snapshot_sha256"])
        )
        snapshot_pfad.unlink()
        neu.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert "A-Q1-Snapshot-Vertrag verletzt" in result.errors[0]["message"]
    if manipulation == "signatur":
        assert "Freigabesignatur" in result.errors[0]["message"]


def test_p9_schema_verweigert_agenten_annahme_im_lesepfad(
    tmp_path: Path,
) -> None:
    """Die Agenten-Sperre muss auch beim LESEN eines Snapshots greifen.

    Auf dem Schreibweg verweigert die Kommandozeile einem Agenten die
    Annahme. Ein Snapshot kann aber auch von aussen praepariert im Fall
    liegen; dann ist diese Schemaregel die letzte Instanz, die ihn
    abweist. Ohne diesen Test liesse sich die Regel ersatzlos loeschen,
    ohne dass die Suite es bemerkt — der Kern der Arbeitsteilung
    (ein Agent entscheidet kein menschliches Gate) haette dann keinen
    Waechter mehr im Lesepfad.
    """
    _, _, snapshot_pfad = _bereit_fuer_g2(tmp_path)
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    assert daten["rolle"] == VA
    assert daten["entscheid"] == "angenommen"

    # ADR-018: Rollenkennungen tragen die Ebene; eine Agentenrolle im
    # Snapshot einer Annahme faellt im Lesepfad, egal was die Zeichnung sagt.
    daten["rolle"] = "agent/programmleitung"
    daten["zeichnung"]["rolle"] = "agent/programmleitung"

    assert (
        "an agent cannot authorize an accepted human gate"
        in P9Snapshot.validate_payload(daten)
    )

    # Gegenprobe: die Ablehnung durch einen Agenten bleibt zulaessig.
    daten["entscheid"] = "abgelehnt"
    assert not any(
        "an agent cannot authorize" in fehler
        for fehler in P9Snapshot.validate_payload(daten)
    )


@pytest.mark.parametrize(
    "ungueltiger_wert", [{}, []], ids=["objekt", "liste"]
)
def test_am4_lehnt_nichtskalaren_vorgaenger_kontrolliert_ab(
    tmp_path: Path, ungueltiger_wert: object
) -> None:
    fall, key, snapshot_pfad = _bereit_fuer_g2(tmp_path)
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    daten["vorgaenger"] = [ungueltiger_wert]

    schema_fehler = P9Snapshot.validate_payload(daten)
    assert "every vorgaenger entry must be a SHA-256" in schema_fehler
    snapshot_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert result.errors[0]["code"] == "vorbedingung"
    assert "A-Q1-Snapshot-Vertrag verletzt" in result.errors[0]["message"]
    assert "every vorgaenger entry must be a SHA-256" in result.errors[0][
        "message"
    ]


@pytest.mark.parametrize(
    "ungueltiger_wert", [{}, []], ids=["objekt", "liste"]
)
def test_am4_lehnt_nichtskalaren_pk1_beleg_kontrolliert_ab(
    tmp_path: Path, ungueltiger_wert: object
) -> None:
    fall, key, _ = _bereit_fuer_g2(tmp_path)
    am4 = _p9(fall, key, "A-M4")
    assert am4.exit_code == 0
    snapshot_pfad = Path(am4.paths["snapshot"])
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    daten["pk1_belege"]["klv/tg2012"] = [ungueltiger_wert]

    schema_fehler = P9Snapshot.validate_payload(daten)
    assert any("contains a non-SHA-256" in fehler for fehler in schema_fehler)
    snapshot_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert result.errors[0]["code"] == "snapshot"
    assert "P9-Snapshot-Vertrag verletzt" in result.errors[0]["message"]
    assert "contains a non-SHA-256" in result.errors[0]["message"]


@pytest.mark.parametrize(
    "ungueltiger_wert", [{}, []], ids=["objekt", "liste"]
)
def test_am4_lehnt_nichtskalaren_scope_pflichtbeleg_kontrolliert_ab(
    tmp_path: Path, ungueltiger_wert: object
) -> None:
    fall, key, _ = _bereit_fuer_g2(tmp_path)
    am4 = _p9(fall, key, "A-M4")
    assert am4.exit_code == 0
    snapshot_pfad = Path(am4.paths["snapshot"])
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    daten["pflichtbelege"]["pq3_ledger"] = [ungueltiger_wert]

    schema_fehler = P9Snapshot.validate_payload(daten)
    assert any("contains a non-SHA-256" in fehler for fehler in schema_fehler)
    snapshot_pfad.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert result.errors[0]["code"] == "snapshot"
    assert "P9-Snapshot-Vertrag verletzt" in result.errors[0]["message"]
    assert "contains a non-SHA-256" in result.errors[0]["message"]


def test_am4_lehnt_signierten_snapshot_mit_fehlender_scope_rolle_ab(
    tmp_path: Path,
) -> None:
    fall, key, _ = _bereit_fuer_g2(tmp_path)
    am4 = _p9(fall, key, "A-M4")
    assert am4.exit_code == 0
    snapshot_pfad = Path(am4.paths["snapshot"])
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    daten["pflichtbelege"].pop("pq3_ledger")
    daten.pop("snapshot_sha256")
    daten["freigabe"] = gate_entscheid._freigabe_fuer(
        daten, key.read_bytes()
    )
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    # Das paketweite JSON-Schema bleibt absichtlich generisch; die exakte
    # Rollenmenge wird aus dem Fall-Scope beim Lesen abgeleitet.
    assert P9Snapshot.validate_payload(daten) == []
    manipuliert = snapshot_pfad.with_name(
        gate_entscheid._snapshot_dateiname("A-M4", daten["snapshot_sha256"])
    )
    snapshot_pfad.unlink()
    manipuliert.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert result.errors[0]["code"] == "snapshot"
    assert "nicht exakt" in result.errors[0]["message"]
    assert "aus dem Scope" in result.errors[0]["message"]


def test_am4_lehnt_fehlenden_vorgaenger_ab(tmp_path: Path) -> None:
    fall, key, erster = _bereit_fuer_g2(tmp_path)
    zweiter = _p9(fall, key, "A-Q1", entscheid="abgelehnt")
    assert zweiter.exit_code == 0
    erster.unlink()

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert "Vorgaenger" in result.errors[0]["message"]
    assert "existiert nicht" in result.errors[0]["message"]


def test_am4_lehnt_zwei_gueltige_spitzen_ab(tmp_path: Path) -> None:
    fall, key, snapshot_pfad = _bereit_fuer_g2(tmp_path)
    daten = json.loads(snapshot_pfad.read_text(encoding="utf-8"))
    daten["begruendung"] = "konkurrierender Entscheidungszweig"
    daten["entschieden_am"] = "2026-08-20T15:00:00+00:00"
    daten["vorgaenger"] = []
    daten.pop("snapshot_sha256")
    daten["freigabe"] = gate_entscheid._freigabe_fuer(daten, key.read_bytes())
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    assert P9Snapshot.validate_payload(daten) == []
    zweig = snapshot_pfad.with_name(
        gate_entscheid._snapshot_dateiname("A-Q1", daten["snapshot_sha256"])
    )
    zweig.write_text(json.dumps(daten), encoding="utf-8")

    result = _p9(fall, key, "A-M4")

    assert result.exit_code == 20
    assert "genau eine eindeutige Spitze" in result.errors[0]["message"]


def test_vorgaenger_graph_erkennt_zyklus_auch_unabhaengig_vom_hashschema(
    tmp_path: Path,
) -> None:
    a, b = "a" * 64, "b" * 64
    snapshots = {
        a: (tmp_path / "a.json", {"vorgaenger": [b]}),
        b: (tmp_path / "b.json", {"vorgaenger": [a]}),
    }

    spitzen, fehler = gate_entscheid._pruefe_snapshot_graph(snapshots)

    assert spitzen == []
    assert any("Zyklus" in meldung for meldung in fehler)


def test_annahme_braucht_externen_privaten_schluessel(tmp_path: Path) -> None:
    fall = _fall(tmp_path)

    ohne = _p9(fall, None, "A-Q1")
    assert ohne.exit_code == 20
    assert ohne.errors[0]["code"] == "freigabe"

    intern = _schluessel(fall / "intern.key")
    innerhalb = _p9(fall, intern, "A-Q1")
    assert innerhalb.exit_code == 20
    assert "innerhalb des Falls" in innerhalb.errors[0]["message"]


@pytest.mark.skipif(os.name == "nt", reason="POSIX-Hardlink-Vertrag")
def test_annahme_lehnt_in_den_fall_hardverlinkten_schluessel_ab(
    tmp_path: Path,
) -> None:
    fall = _fall(tmp_path)
    extern = _schluessel(tmp_path / "extern.key")
    os.link(extern, fall / "schluessel-spiegel.key")

    result = _p9(fall, extern, "A-Q1")

    assert result.exit_code == 20
    assert "Hardlinks" in result.errors[0]["message"]


def test_schluesselpfad_und_bytes_erscheinen_nicht_im_ledger(tmp_path: Path) -> None:
    fall = _fall(tmp_path)
    key = _schluessel(tmp_path / "streng-geheim.key", byte=b"z")

    result = _p9(fall, key, "A-Q1")

    assert result.exit_code == 0
    ledger = json.loads((
        fall / "abgeleitet" / "diagnostics" / "gate_entscheid_aq1.gate.json"
    ).read_text(encoding="utf-8"))
    serialisiert = json.dumps(ledger)
    assert str(key) not in serialisiert
    assert (b"z" * 64).decode() not in serialisiert
    assert "<extern-redigiert>" in serialisiert


def test_p9_cli_emittiert_genau_ein_json_und_schema_valides_ledger(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fall = _fall(tmp_path)
    key = _schluessel(tmp_path / "p9.key")
    argv = [
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--rolle", VA, "--entscheider", "fachrolle",
        "--begruendung", "CLI-Vertrag geprueft", "--repo-root", str(REPO_ROOT),
        "--freigabe-schluessel", str(key),
        "--zeichnungsordnung", str(standard_ordnung(tmp_path, key)),
    ]

    returncode = run_command(gate_entscheid.main, argv)
    ausgabe = capsys.readouterr().out
    payload = json.loads(ausgabe)

    assert len(ausgabe.rstrip("\n").splitlines()) == 1
    assert returncode == payload["exit_code"] == 0
    eintraege, lesefehler = load_gate_ledger(
        fall / "abgeleitet" / "diagnostics"
    )
    assert lesefehler == []
    p9 = [entry for entry in eintraege if entry.command == "gate_entscheid_aq1"]
    assert len(p9) == 1
    assert p9[0].status == "passed"
