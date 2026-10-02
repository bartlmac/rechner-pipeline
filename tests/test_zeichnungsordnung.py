"""Zeichnungsordnung: welche Rolle darf welches Gate zeichnen.

Die Zwei-Operatoren-Regie (Beschluss 2026-08-31) trennt den
Quell-Experten (zeichnet nur Lieferungen, keine Gates) vom PLV-Operator
(zeichnet die Abnahmen mit eigenem menschlichem Schluessel); der Mensch
selbst steigt nur nach Abbruchkriterien ein. Bis dahin prueften die Gates
NICHT, wer zeichnet: Jeder uebergebene Schluessel zeichnete jedes Gate --
ein Quell-Experte haette die Abnahme des aufnehmenden Unternehmens
signieren koennen, und niemand haette es gemerkt.

Die Ordnung bindet Rollen an Schluessel-Fingerabdruecke und Gates an
Rollen. Sie liegt wie die Schluessel ausserhalb des Falls: Eine Ordnung,
die der Fall selbst umschreiben kann, ordnet nichts.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.gates.generation_golden import main as pk1

from tests.e2e_fixture import bereite_pk1_fall

REPO_ROOT = Path(__file__).resolve().parents[1]


def _schluessel(pfad: Path, inhalt: bytes) -> str:
    """Schluesseldatei anlegen; Rueckgabe ist ihr Fingerabdruck."""
    pfad.write_bytes(inhalt)
    pfad.chmod(0o600)
    return hashlib.sha256(inhalt).hexdigest()


VA = "mensch/aktuariat"
QUELLE = "mensch/quell-aktuar"
#: Eine Rolle der PLV ohne Gate-Recht: Die Rolle des abgebenden Hauses kommt
#: nicht in die Linie (ADR-025), die Linie ist Pflicht (Nachtrag 2026-10-01).
OHNE_RECHT = "mensch/revision"
IT = "mensch/architektur"


def _schreibe_ordnung(pfad: Path, rollen: dict) -> Path:
    """Schema 2 (ADR-018): jede Rolle traegt ihre Schluesselklasse; ohne
    Angabe simuliert der Test eine menschliche Rolle."""
    for name, eintrag in rollen.items():
        eintrag.setdefault(
            "schluesselklasse", "agent" if name.startswith("agent/") else "simulation")
    pfad.write_text(
        json.dumps({"schema_version": 2, "rollen": rollen}), encoding="utf-8"
    )
    return pfad


def _ausserhalb_der_linie(ordnung: Path, fall: Path) -> bool:
    """Ob die Ordnung (mit der Wurzelrolle der Suite) nicht in die Linie darf."""
    from rechner_pipeline.models.ordnungslinie import ordnung_inhalt_fehler
    from tests.zeichnung_fixture import _wurzel_sicherstellen

    try:
        _wurzel_sicherstellen(ordnung, fall.parent)
    except (ValueError, KeyError, TypeError):
        return True
    return bool(ordnung_inhalt_fehler(ordnung.read_text(encoding="utf-8"))[1])


def _entscheid(fall: Path, gate: str, schluessel: Path, *extra: str):
    from tests.zeichnung_fixture import auftrag_args, mandat_datei

    # Der Fall ist beauftragt, unter der Ordnung des Tests (ADR-026), und sie
    # ist die Spitze der Linie (ADR-025: die Linie ist Pflicht). Eine Ordnung,
    # die nicht in die Linie darf, bekommt die Linie der Standardordnung — der
    # Aufruf zeichnet dann nicht unter der Spitze.
    ordnung = (Path(extra[extra.index("--zeichnungsordnung") + 1])
               if "--zeichnungsordnung" in extra else None)
    if ordnung is not None and ordnung.is_file() and not _ausserhalb_der_linie(ordnung, fall):
        vorab = auftrag_args(fall, ordnung)
    else:
        vorab = auftrag_args(fall)
    # Das Mandat faehrt immer mit: Pflicht bei Schluesselklasse simulation
    # (T22-07), ohne Wirkung bei mensch.
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", gate,
        "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", "geprueft",
        "--repo-root", str(REPO_ROOT), *vorab,
        "--freigabe-schluessel", str(schluessel),
        "--mandat", str(mandat_datei(fall)),
        *extra,
    ])


@pytest.fixture()
def aufbau(tmp_path: Path):
    """Ein pruefbereiter Tarif-Fall plus zwei getrennte Schluessel."""
    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
    ]).exit_code == 0
    va = tmp_path / "plv-va.key"
    experte = tmp_path / "quelle-experte.key"
    fp_va = _schluessel(va, b"plv-va-menschlicher-schluessel!!" * 2)
    fp_exp = _schluessel(experte, b"quelle-experte-schluessel!!!!!!!" * 2)
    ordnung = _schreibe_ordnung(tmp_path / "zeichnungsordnung.json", {
        VA: {"schluessel_sha256": fp_va,
             "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4"]},
        OHNE_RECHT: {"schluessel_sha256": fp_exp, "gates": []},
    })
    return fall, va, experte, ordnung


def test_die_berechtigte_rolle_zeichnet_und_steht_im_snapshot(aufbau):
    """Der Snapshot sagt nicht nur DASS, sondern als WER gezeichnet wurde.

    Rolle und Ordnungs-Hash stehen vor der Signatur im Snapshot und
    werden mitsigniert -- die Rollenbindung ist damit selbst Teil dessen,
    was die Freigabe beglaubigt.
    """
    fall, va, _experte, ordnung = aufbau
    ergebnis = _entscheid(fall, "A-Q1", va, "--zeichnungsordnung", str(ordnung))
    assert ergebnis.exit_code == 0

    snapshot = json.loads(
        Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["zeichnung"]["rolle"] == VA
    assert snapshot["zeichnung"]["schluesselklasse"] == "simulation"
    assert snapshot["rolle"] == VA
    assert snapshot["zeichnung"]["ordnung_sha256"] == hashlib.sha256(
        ordnung.read_bytes()).hexdigest()


def test_eine_rolle_ohne_gate_recht_wird_abgewiesen(aufbau):
    """Der Quell-Experte zeichnet keine Abnahme des aufnehmenden Hauses.

    Sein Schluessel ist gueltig, seine Datei privat, seine Rolle bekannt
    -- er ist nur nicht ZUSTAENDIG. Genau diese Unterscheidung fehlte.
    """
    fall, _va, experte, ordnung = aufbau
    ergebnis = _entscheid(
        fall, "A-Q1", experte, "--zeichnungsordnung", str(ordnung))
    assert ergebnis.exit_code == 20
    meldung = ergebnis.errors[0]["message"]
    assert OHNE_RECHT in meldung and "A-Q1" in meldung
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []


def test_ein_fremder_schluessel_gehoert_keiner_rolle(aufbau, tmp_path):
    fall, _va, _experte, ordnung = aufbau
    fremd = tmp_path / "fremd.key"
    _schluessel(fremd, b"irgendein-selbstgebauter-schluessel" * 2)
    ergebnis = _entscheid(
        fall, "A-Q1", fremd, "--zeichnungsordnung", str(ordnung))
    assert ergebnis.exit_code == 20
    assert "keiner Rolle" in ergebnis.errors[0]["message"]


def test_die_ordnung_darf_nicht_im_fall_liegen(aufbau):
    """Eine Ordnung, die der Fall selbst umschreiben kann, ordnet nichts."""
    fall, va, _experte, _ordnung = aufbau
    drin = _schreibe_ordnung(fall / "zeichnungsordnung.json", {
        VA: {"schluessel_sha256": "0" * 64, "gates": ["A-Q1"]},
    })
    ergebnis = _entscheid(fall, "A-Q1", va, "--zeichnungsordnung", str(drin))
    assert ergebnis.exit_code == 2
    assert "innerhalb des Falls" in ergebnis.errors[0]["message"]


def test_zwei_rollen_mit_demselben_schluessel_sind_ein_fehler(aufbau, tmp_path):
    """Sonst ist die Trennung der Operatoren nur behauptet."""
    fall, va, _experte, _ordnung = aufbau
    fp = hashlib.sha256(va.read_bytes()).hexdigest()
    doppelt = _schreibe_ordnung(tmp_path / "doppelt.json", {
        VA: {"schluessel_sha256": fp, "gates": ["A-Q1"]},
        OHNE_RECHT: {"schluessel_sha256": fp, "gates": []},
    })
    ergebnis = _entscheid(fall, "A-Q1", va, "--zeichnungsordnung", str(doppelt))
    assert ergebnis.exit_code == 2
    assert "denselben Schluessel" in ergebnis.errors[0]["message"]


def test_jedes_zeichenbare_gate_ist_einer_rolle_zuweisbar(tmp_path):
    """A-O1 fiel durch: zeichenbar (GUELTIGE_GATES), aber der Ordnung
    nicht zuweisbar — eine Ordnung mit Loch, gefunden beim Aufsetzen
    der Vier-Rollen-Regie (plv-it zeichnet A-O1). Der Waechter bindet
    die Zuweisbarkeit an die Liste der zeichenbaren Gates."""
    assert set(gate_entscheid.GUELTIGE_GATES) <= set(
        gate_entscheid.ZEICHNUNG_GATES)
    ordnung = _schreibe_ordnung(tmp_path / "mit-a-k1.json", {
        IT: {"schluessel_sha256": "0" * 64, "gates": ["A-O1"]},
    })
    geladen, sha, fehler = gate_entscheid._lade_zeichnungsordnung(
        str(ordnung), tmp_path / "fall")
    assert fehler == []
    assert geladen["rollen"][IT]["gates"] == ["A-O1"]
    assert sha


def test_eine_allzweck_rolle_zeichnet_nicht_mehr(aufbau, tmp_path):
    """Die fruehere Eskalationsrolle (gates '*', die Programmleitung als
    Allzweck-Zeichner) gibt es nicht mehr: Eine solche Ordnung kommt nicht in
    die Linie (ADR-025), und gezeichnet wird nur unter der Spitze der Linie
    (Nachtrag 2026-10-01: die Linie ist Pflicht). Den Abbruch zeichnet die
    Programmleitung mit dem Recht aus dem Fallauftrag (A-M5, ADR-026)."""
    from rechner_pipeline.models.ordnungslinie import ordnung_inhalt_fehler

    fall, va, _experte, _ordnung = aufbau
    mensch = tmp_path / "mensch.key"
    fp = _schluessel(mensch, b"maintainer-eskalations-schluessel!" * 2)
    ordnung = _schreibe_ordnung(tmp_path / "mit-mensch.json", {
        "mensch/programmleitung": {"schluessel_sha256": fp,
                                   "schluesselklasse": "mensch", "gates": ["*"]},
    })
    assert ordnung_inhalt_fehler(ordnung.read_text(encoding="utf-8"))[1]
    ergebnis = _entscheid(
        fall, "A-Q1", mensch, "--zeichnungsordnung", str(ordnung))
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert "Spitze" in ergebnis.errors[0]["message"]
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []


def test_ohne_ordnung_keine_annahme(aufbau):
    """ADR-018: Die zeichnende Rolle wird aus dem Schluessel bestimmt,
    nicht behauptet — ohne Ordnung gibt es keine Annahme. Vorher galt
    'die Ordnung ist Regie-Entscheid je Fall'; genau dieser Alt-Weg
    machte die Besetzung der Rolle in jedem Beleg unsichtbar."""
    fall, _va, experte, _ordnung = aufbau
    ergebnis = _entscheid(fall, "A-Q1", experte)
    assert ergebnis.exit_code == 20
    assert ergebnis.errors[0]["code"] == "zeichnung"
    assert list((fall / "entscheide").glob("A-Q1-*.json")) == []


def test_die_kette_prueft_die_zeichnung_der_vorbedingungen(aufbau):
    """A-M4 haelt jede Vorbedingung gegen die Ordnung, unter der sie
    gezeichnet wurde (ADR-025: die Linie ist Pflicht) — hier ein Snapshot
    unter einem Glied, das die Linie nicht kennt (die Zeichnung unter einer
    fremden, nicht eingetragenen Ordnung): als Vorbedingung wertlos.

    Frueher: A-Q1 und A-M1 unter einer laxen Ordnung (Stern fuer den
    Quell-Aktuar), A-M4 unter der richtigen — die Stern-Ordnung kommt heute
    nicht mehr in die Linie, und eine spaetere Ordnung entwertet eine
    damals berechtigte Zeichnung nicht (ein Entzug wirkt nicht zurueck).
    Was bleibt, ist die Frage, ob die Vorbedingung in DIESER Linie
    lokalisierbar ist.
    """
    from tests.test_abnahme_rolle_klasse import _neu_signiert

    fall, va, experte, ordnung = aufbau
    assert _entscheid(fall, "A-Q1", va, "--zeichnungsordnung", str(ordnung)).exit_code == 0
    assert _entscheid(fall, "A-M1", va, "--zeichnungsordnung", str(ordnung)).exit_code == 0
    # A-Q1 unter einem fremden Glied neu signieren (gueltige Signatur)
    (pfad,) = list((fall / "entscheide").glob("A-Q1-*.json"))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    neu = _neu_signiert(daten, va.read_bytes(), zeichnung={
        **daten["zeichnung"], "ordnungsglied_sha256": "ab" * 32})
    pfad.unlink()
    (pfad.parent / f"A-Q1-{neu['snapshot_sha256']}.json").write_text(
        json.dumps(neu, ensure_ascii=False), encoding="utf-8")
    # Der P-K1-Beleg ist eine eigene Vorbedingung von A-M4 und hier nicht
    # Gegenstand -- er wird regulaer erzeugt, damit die Kette bis zur
    # Zeichnungspruefung kommt.
    assert pk1([
        "--fall", str(fall), "--generation", "klv/tg2012",
        "--repo-root", str(REPO_ROOT),
    ]).exit_code == 0

    ergebnis = _entscheid(
        fall, "A-M4", va, "--zeichnungsordnung", str(ordnung))
    assert ergebnis.exit_code == 20
    meldung = ergebnis.errors[0]["message"]
    assert "A-Q1" in meldung and "unberechtigt" in meldung and "Ordnungslinie" in meldung
