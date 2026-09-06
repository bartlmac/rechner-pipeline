"""Rollenmodell mit Schluesselklassen (ADR-018).

Die Reviews T20 und U1 fanden: Aus keinem Beleg war ablesbar, ob ein
Mensch oder eine KI-Session gezeichnet hatte; ein Alt-Weg liess eine
behauptete Rolle 'mensch' ohne Ordnung annehmen; Agentenschluessel waren
von Menschenschluesseln nicht unterscheidbar. Jeder Test hier waere vor
der Korrektur gruen gewesen.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models.schemas import P9Snapshot, p9_snapshot_sha256
from rechner_pipeline.models.zeichnung import lade_zeichnungsordnung

from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import AGENT, VA, ordnung_schreiben, schluessel_anlegen

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def _annahme(fall: Path, schluessel: Path, ordnung: Path, *extra: str):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", "geprueft",
        "--repo-root", str(REPO_ROOT),
        "--freigabe-schluessel", str(schluessel), "--zeichnungsordnung", str(ordnung),
        *extra,
    ])


def test_agentenschluessel_zeichnet_nicht(fall, tmp_path):
    """Eine Ordnung, die einer Agentenrolle Gates gibt, ist ungueltig; ein
    Agentenschluessel in einer gueltigen Ordnung zeichnet nichts."""
    agent_key = tmp_path / "agent.key"
    fp = schluessel_anlegen(agent_key, b"agent-schluessel-der-vorbereitung!" * 2)
    mit_gates = ordnung_schreiben(tmp_path / "falsch.json", {
        AGENT: {"schluessel_sha256": fp, "schluesselklasse": "agent", "gates": ["A-Q1"]},
    })
    _, _, fehler = lade_zeichnungsordnung(str(mit_gates), fall)
    assert any("zeichnen nie" in f for f in fehler), fehler

    ordnung = ordnung_schreiben(tmp_path / "ordnung.json", {
        AGENT: {"schluessel_sha256": fp, "schluesselklasse": "agent", "gates": []},
    })
    ergebnis = _annahme(fall, agent_key, ordnung)
    assert ergebnis.exit_code == 20
    assert "nicht zeichnungsberechtigt" in ergebnis.errors[0]["message"]
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []


def test_simulierte_rolle_traegt_ihre_klasse_und_ihr_mandat(fall, tmp_path):
    key = tmp_path / "va.key"
    fp = schluessel_anlegen(key)
    ordnung = ordnung_schreiben(tmp_path / "ordnung.json", {
        VA: {"schluessel_sha256": fp, "schluesselklasse": "simulation", "gates": ["*"]},
    })
    mandat = tmp_path / "mandat.md"
    mandat.write_text("Mandat: A-Q1 vorbereiten und zeichnen.", encoding="utf-8")

    ergebnis = _annahme(fall, key, ordnung, "--mandat", str(mandat))
    assert ergebnis.exit_code == 0
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["schema_version"] == 7
    assert snapshot["rolle"] == VA
    assert snapshot["zeichnung"] == {
        "rolle": VA,
        "ordnung_sha256": hashlib.sha256(ordnung.read_bytes()).hexdigest(),
        "schluesselklasse": "simulation",
        "mandat_sha256": hashlib.sha256(mandat.read_bytes()).hexdigest(),
    }
    # Der Renderer liest die Besetzung aus dem Snapshot.
    import sys
    sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
    import falldaten
    [eintrag] = falldaten.kette(fall)["entscheide"]
    assert eintrag["schluesselklasse"] == "simulation"
    assert eintrag["rolle"] == VA


def test_alte_rollenwerte_ohne_ebene_gelten_nicht_mehr(fall, tmp_path):
    key = tmp_path / "va.key"
    fp = schluessel_anlegen(key)
    ordnung = ordnung_schreiben(tmp_path / "ordnung.json", {
        VA: {"schluessel_sha256": fp, "schluesselklasse": "simulation", "gates": ["*"]},
    })
    ergebnis = _annahme(fall, key, ordnung, "--rolle", "mensch")
    assert ergebnis.exit_code == 2
    assert "keine Rollenkennung mit Ebene" in ergebnis.errors[0]["message"]


def test_schema_1_ordnung_wird_mit_hinweis_abgewiesen(fall, tmp_path):
    alt = tmp_path / "alt.json"
    alt.write_text(json.dumps({"schema_version": 1, "rollen": {
        "plv-va": {"schluessel_sha256": "0" * 64, "gates": ["*"]}}}), encoding="utf-8")
    _, _, fehler = lade_zeichnungsordnung(str(alt), fall)
    assert fehler and "ADR-018" in fehler[0]


def test_altsnapshot_schema_6_bleibt_lesbar():
    """Die sechzehn Snapshots des zweiten Baldrian-Laufs sind eine
    ausgewiesene Ausnahme: gueltig, gepinnt, nicht nachsigniert."""
    daten = {
        "schema_version": 6, "command": "gate_entscheid", "gate_version": "0.6.0",
        "gate": "A-M1", "entscheid": "angenommen", "entscheider": "plv-aktuar",
        "rolle": "mensch", "begruendung": "x", "fall": "f",
        "artefakt_hashes": {"eingang.json": "ab" * 32, "abgeleitet/abox/abox.json": "cd" * 32},
        "system": {"branch": "b", "commit": "c", "dirty": "nein", "quellcode_sha256": "ef" * 32},
        "vorgaenger": [], "entschieden_am": "2026-09-01T10:00:00+00:00",
        "fall_scope": "bestand", "pflichtbelege": {"aktuartest": ["ab" * 32]},
        "freigabe": {"schluessel_sha256": "cd" * 32, "signatur": "ef" * 32,
                     "verfahren": "hmac-sha256-v1"},
    }
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    assert P9Snapshot.validate_payload(daten) == []

    # Derselbe Inhalt als Schema 7 ohne Zeichnung ist keine Annahme.
    neu = dict(daten, schema_version=7, gate_version="0.7.0", rolle=VA)
    neu.pop("snapshot_sha256")
    neu["snapshot_sha256"] = p9_snapshot_sha256(neu)
    fehler = P9Snapshot.validate_payload(neu)
    assert any("requires zeichnung" in f for f in fehler), fehler
    # Und eine Rolle ohne Ebene faellt in Schema 7.
    neu["rolle"] = "mensch"
    assert any("role id with its level" in f for f in P9Snapshot.validate_payload(neu))


def test_entscheide_ohne_ordnung_entscheidet_nichts(fall, capsys):
    from rechner_pipeline.ontologie import entscheide

    rc = entscheide.main(["--fall", str(fall), "--diskrepanz", "x#y", "--wert", "1",
                          "--entscheider", "X", "--begruendung", "y", "--rolle", VA])
    assert rc == 2
    assert "Alt-Weg" in capsys.readouterr().err


def test_behauptete_rolle_mit_schluessel_ohne_ordnung_nimmt_nicht_an(fall, tmp_path):
    """Der Alt-Weg des Vier-Rollen-Modells: Schluessel da, Rolle behauptet,
    keine Ordnung — vorher eine gueltige Annahme, jetzt die Sperre."""
    key = tmp_path / "va.key"
    schluessel_anlegen(key)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--rolle", VA, "--entscheider", "fachrolle", "--begruendung", "geprueft",
        "--repo-root", str(REPO_ROOT), "--freigabe-schluessel", str(key),
    ])
    assert ergebnis.exit_code == 20
    assert ergebnis.errors[0]["code"] == "zeichnung"
    assert "ADR-018" in ergebnis.errors[0]["message"]
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []
