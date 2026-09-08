"""Zeichnungsvertrag (Review T23-06, T23-08; Block 4).

T23-06: Die Regel der Rollenbindung (ADR-018: Altform oder Form mit
Schluesselklasse; eine Simulation nur unter Mandat) galt nur in der
Argumentverarbeitung von ``ontologie.entscheide`` und im P9-Schema. Wer
eine Entscheidung direkt konstruierte, eine A-Box von Hand schrieb oder
``loese_diskrepanz_auf`` direkt rief, konnte jede Schluesselklasse
behaupten — und validate_abox, pruefe_kette und Gate P-Q3 liessen es
durch. Jetzt steht die Regel an EINER Stelle
(``models.zeichnung.validiere_zeichnung``) und gilt an jedem Eintritt.

T23-08: Der Idempotenz-Kurzschluss des P9-Gates verglich nur einen
Kern-Inhalt ohne Zeichnung; ein Wiederholungsaufruf mit anderem
Schluessel, anderer Ordnung oder ohne Mandat bekam "bereits_vorhanden"
mit Exit 0, ohne dass seine Zeichnung je geprueft wurde. Jetzt laufen die
Sperren vor dem Kurzschluss, und die Zeichnung ist Teil des Vergleichs.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models.zeichnung import validiere_zeichnung
from rechner_pipeline.ontologie.abox import abox_pfad, lade, validate_abox
from rechner_pipeline.ontologie.aussage import Lesart, Provenienz
from rechner_pipeline.ontologie.befuellung import loese_diskrepanz_auf
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz, Entscheidung
from rechner_pipeline.ontologie.kette import pruefe_kette
from tests.e2e_fixture import bereite_pk1_fall
from tests.test_kette_und_vorbedingungen import fall_mit_fragmenten, merge_cli  # noqa: F401
from tests.zeichnung_fixture import VA, ordnung_schreiben, schluessel_anlegen

REPO_ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 64
ALT = {"rolle": VA, "ordnung_sha256": SHA}
NEU_MENSCH = {**ALT, "schluesselklasse": "mensch"}
NEU_SIM = {**ALT, "schluesselklasse": "simulation", "mandat_sha256": "b" * 64}
SIM_OHNE_MANDAT = {**ALT, "schluesselklasse": "simulation"}


# --------------------------------------------------------------------------- #
# T23-06: die Regel an einer Stelle
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("z", [ALT, NEU_MENSCH, NEU_SIM])
def test_gueltige_zeichnungen(z):
    assert validiere_zeichnung(z) == []


@pytest.mark.parametrize("z, stichwort", [
    ({}, "zeichnung muss"),
    ({"rolle": VA}, "zeichnung muss"),
    (SIM_OHNE_MANDAT, "braucht mandat_sha256"),
    ({**ALT, "schluesselklasse": "agent"}, "in (mensch, simulation)"),
    ({**NEU_SIM, "mandat_sha256": "kein-hash"}, "mandat"),
    ({**NEU_MENSCH, "extra": "x"}, "zeichnung muss"),
    ("text", "Tabelle"),
    # Review Block 4: Rolle und Ordnungs-Hash nur auf Typ geprueft
    ({**NEU_MENSCH, "rolle": "nicht-mal-eine-rolle"}, "Rollenkennung"),
    ({**NEU_MENSCH, "ordnung_sha256": "kein-hash-x"}, "SHA-256"),
    ({"rolle": "plv-aktuar", "ordnung_sha256": "kein-hash"}, "SHA-256 der Ordnung"),
    ({"rolle": " ", "ordnung_sha256": SHA}, "nichtleeren Rolle"),
])
def test_ungueltige_zeichnungen(z, stichwort):
    fehler = validiere_zeichnung(z)
    assert any(stichwort in f for f in fehler), fehler


def test_form_alt_und_neu_sind_getrennt_pruefbar():
    assert validiere_zeichnung(NEU_MENSCH, form="alt")
    assert validiere_zeichnung(ALT, form="neu")
    assert validiere_zeichnung(ALT, form="alt") == [] and validiere_zeichnung(NEU_SIM, form="neu") == []


def _entscheidung(z):
    return Entscheidung(
        entscheider="x", begruendung="y", gewaehlter_wert=0.025,
        entschieden_am="2026-09-08T00:00:00+00:00", zeichnung=z,
    )


@pytest.mark.parametrize("z", [SIM_OHNE_MANDAT, {}, {**ALT, "schluesselklasse": "agent"}])
def test_entscheidung_direkt_konstruiert_unterliegt_derselben_regel(z):
    """Der Reviewer-Fall: an ontologie.entscheide vorbei."""
    with pytest.raises(ValidationError, match="zeichnung"):
        _entscheidung(z)


def test_entscheidung_mit_gueltiger_zeichnung_bleibt_konstruierbar():
    """Auch die Altform {rolle, ordnung_sha256} bleibt konstruierbar — nicht
    als Wunsch, sondern als benannte Grenze: die 14 Aufloesungen des zweiten
    Laufs tragen sie (rolle "plv-aktuar"), und das Modell kennt keinen
    Zeitpunkt, ab dem die Altform nicht mehr NEU entstehen darf. Die CLI
    schreibt sie nie mehr; ein Stichtag waere eine ADR-018-Ergaenzung."""
    for z in (None, ALT, {"rolle": "plv-aktuar", "ordnung_sha256": SHA}, NEU_MENSCH, NEU_SIM):
        assert _entscheidung(z).zeichnung == z


def _lesarten():
    prov = Provenienz(quelle_datei="meldung.pdf", quelle_sha256="c" * 64,
                      fundstelle="Tab. 2", akteur="test", erhoben_am="2026-09-08T00:00:00+00:00")
    return [Lesart(wert=0.025, provenienz=(prov,)), Lesart(wert=0.03, provenienz=(prov,))]


def _diskrepanz_am_modell_vorbei(z):
    """Konstruktion OHNE Validierung — der Weg einer A-Box, die je an
    Pydantic vorbei entsteht."""
    e = Entscheidung.model_construct(
        entscheider="x", begruendung="y", gewaehlter_wert=0.025,
        entschieden_am="2026-09-08T00:00:00+00:00", vorlaeufig=False, beleg=None, zeichnung=z,
    )
    return Diskrepanz.model_construct(
        id="klv/tg2012/zelle:-#beta1", knoten="klv/tg2012/zelle:-", feld="beta1",
        lesarten=_lesarten(), status="aufgeloest", entscheidung=e, entscheidungs_historie=[],
    )


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def test_validate_abox_prueft_die_rollenbindung(fall):
    abox = lade(fall)
    abox.diskrepanzen.append(_diskrepanz_am_modell_vorbei(SIM_OHNE_MANDAT))
    assert any("mandat_sha256" in f and "Diskrepanz" in f for f in validate_abox(abox))
    # Positivkontrolle: eine gueltige Rollenbindung ist kein Befund.
    abox.diskrepanzen[-1] = _diskrepanz_am_modell_vorbei(NEU_SIM)
    assert not any("mandat" in f for f in validate_abox(abox))


def test_kette_prueft_die_rollenbindung_der_aufloesung(fall_mit_fragmenten):
    """Der Schutz, der eigens gegen direkt editierte A-Boxen gebaut wurde,
    erklaerte Status/Entscheidung zum Freiheitsgrad — die Wahl ist frei,
    ihre Rollenbindung nicht."""
    f = fall_mit_fragmenten
    assert merge_cli(["--fall", str(f)]).exit_code == 0
    abox = lade(f)
    offen = abox.diskrepanzen[0]
    e = Entscheidung.model_construct(
        entscheider="x", begruendung="y", gewaehlter_wert=offen.lesarten[0].wert,
        entschieden_am="2026-09-08T00:00:00+00:00", vorlaeufig=False, beleg=None,
        zeichnung=SIM_OHNE_MANDAT,
    )
    abox.diskrepanzen[0] = Diskrepanz.model_construct(
        id=offen.id, knoten=offen.knoten, feld=offen.feld, lesarten=offen.lesarten,
        status="aufgeloest", entscheidung=e, entscheidungs_historie=[],
    )
    fehler = pruefe_kette(f, abox=abox)
    assert any("Rollenbindung" in x and "mandat_sha256" in x for x in fehler), fehler


def test_pq3_weist_handgeschriebene_aufloesung_ohne_mandat_ab(fall):
    """Der Gate-Bypass-Fall: eine gueltig aussehende abox.json mit genau
    diesem Defekt, durch Gate P-Q3 — ein Befund, kein Traceback. Ehrlich:
    hier faengt der Modell-Validator beim LADEN (P-Q3 meldet den Ladefehler
    als Befund); die Kreuz-Objekt-Schleifen in validate_abox/pruefe_kette
    sind Verteidigung in der Tiefe fuer eine A-Box, die je an Pydantic
    vorbei entsteht, und werden von den model_construct-Tests geprueft."""
    daten = json.loads(abox_pfad(fall).read_text(encoding="utf-8"))
    d = Diskrepanz(
        id="klv/tg2012/zelle:-#beta1", knoten="klv/tg2012/zelle:-", feld="beta1",
        lesarten=_lesarten(), status="aufgeloest", entscheidung=_entscheidung(NEU_SIM),
    ).model_dump(mode="json", exclude_none=True)
    d["entscheidung"]["zeichnung"] = SIM_OHNE_MANDAT
    daten["diskrepanzen"].append(d)
    abox_pfad(fall).write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    ergebnis = pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)])
    assert ergebnis.exit_code != 0
    assert any("mandat_sha256" in e.get("message", "") for e in ergebnis.errors), ergebnis.errors


def test_loese_diskrepanz_auf_schreibt_die_altform_nicht_mehr(fall):
    """Anmerkung der merge-session zum Testat: solange die Altform fuer NEUE
    Zeichnungen offen ist, kann eine Simulation ohne Klasse entstehen, und
    die Mandatspflicht haengt an der Klasse. Der Schreibpfad verlangt die
    Form mit Klasse; gelesen wird die Altform weiter."""
    abox = lade(fall)
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg2012/zelle:-#beta1", knoten="klv/tg2012/zelle:-", feld="beta1",
        lesarten=_lesarten(),
    ))
    with pytest.raises(ValueError, match="Schluesselklasse"):
        loese_diskrepanz_auf(
            abox, "klv/tg2012/zelle:-#beta1", 0.025, "x", "y",
            "2026-09-08T00:00:00+00:00", zeichnung=ALT,
        )
    neu = loese_diskrepanz_auf(
        abox, "klv/tg2012/zelle:-#beta1", 0.025, "x", "y",
        "2026-09-08T00:00:00+00:00", zeichnung=NEU_SIM,
    )
    assert neu.diskrepanzen[-1].entscheidung.zeichnung == NEU_SIM


def test_loese_diskrepanz_auf_direkt_gerufen_verweigert(fall):
    abox = lade(fall)
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg2012/zelle:-#beta1", knoten="klv/tg2012/zelle:-", feld="beta1",
        lesarten=_lesarten(),
    ))
    # Der Schreibpfad prueft vor der Konstruktion (ValueError mit Ausweg);
    # das Modell wuerde dieselbe Zeichnung ebenfalls verweigern.
    with pytest.raises(ValueError, match="mandat_sha256"):
        loese_diskrepanz_auf(
            abox, "klv/tg2012/zelle:-#beta1", 0.025, "x", "y",
            "2026-09-08T00:00:00+00:00", zeichnung=SIM_OHNE_MANDAT,
        )


def test_betriebseingang_behauptet_keine_fremde_klasse_und_keine_simulation_ohne_mandat():
    basis = {"schema_version": ueb.EINGANG_SCHEMA_VERSION, "fall": "f", "stichtag": "2026-01-01",
             "snapshot_sha256": None, "dateien": {"bestand.parquet": "d" * 64}}
    ok = ueb.validate_eingang({**basis, "zeichnung": {"schluesselklasse": "simulation", "mandat_sha256": "b" * 64}})
    assert not any("zeichnung" in f for f in ok), ok
    ohne = ueb.validate_eingang({**basis, "zeichnung": {"schluesselklasse": "simulation"}})
    assert any("mandat_sha256" in f for f in ohne), ohne
    fremd = ueb.validate_eingang({**basis, "zeichnung": {"schluesselklasse": "orakel"}})
    assert any("keine zeichnende Schluesselklasse" in f for f in fremd), fremd
    # Ein Agent ist eine bekannte Klasse, aber keine zeichnende (Review Block 4).
    agent = ueb.validate_eingang({**basis, "zeichnung": {"schluesselklasse": "agent"}})
    assert any("keine zeichnende Schluesselklasse" in f for f in agent), agent
    nicht_ausgewiesen = ueb.validate_eingang({**basis, "zeichnung": {"schluesselklasse": ueb.NICHT_AUSGEWIESEN}})
    assert not any("zeichnung" in f for f in nicht_ausgewiesen)


def test_zeichnung_aus_snapshot_reicht_das_mandat_durch(tmp_path):
    fall = tmp_path / "fall"
    (fall / "entscheide").mkdir(parents=True)
    sha = "e" * 64
    (fall / "entscheide" / f"A-M4-{sha}.json").write_text(json.dumps({
        "gate": "A-M4", "entscheid": "angenommen", "rolle": VA, "entscheider": "va",
        "schema_version": 7, "zeichnung": NEU_SIM, "freigabe": {"schluessel_sha256": "f" * 64},
    }), encoding="utf-8")
    z = ueb.zeichnung_aus_snapshot(fall, sha)
    assert z["schluesselklasse"] == "simulation" and z["mandat_sha256"] == "b" * 64


# --------------------------------------------------------------------------- #
# T23-08: Sperren vor dem Kurzschluss, Zeichnung im Vergleich
# --------------------------------------------------------------------------- #

def _annahme(fall, schluessel, ordnung, *extra):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", "geprueft",
        "--repo-root", str(REPO_ROOT),
        "--freigabe-schluessel", str(schluessel), "--zeichnungsordnung", str(ordnung),
        *extra,
    ])


def _snapshot(ergebnis):
    return json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))


def test_wiederholung_ohne_mandat_ist_kein_treffer_sondern_sperre(fall, tmp_path):
    key = tmp_path / "va.key"
    fp = schluessel_anlegen(key)
    ordnung = ordnung_schreiben(tmp_path / "ordnung.json", {
        VA: {"schluessel_sha256": fp, "schluesselklasse": "simulation", "gates": ["*"]},
    })
    mandat = tmp_path / "mandat.md"
    mandat.write_text("Mandat.", encoding="utf-8")
    erste = _annahme(fall, key, ordnung, "--mandat", str(mandat))
    assert erste.exit_code == 0 and not erste.summary.get("bereits_vorhanden")
    # Identische Wiederholung: Treffer, wie gewollt.
    zweite = _annahme(fall, key, ordnung, "--mandat", str(mandat))
    assert zweite.exit_code == 0 and zweite.summary.get("bereits_vorhanden") is True
    assert _snapshot(zweite)["snapshot_sha256"] == _snapshot(erste)["snapshot_sha256"]
    # Der Reviewer-Fall: dieselbe Wiederholung OHNE Mandat bekam vorher
    # "bereits_vorhanden" mit Exit 0 — die Sperre lief nie.
    ohne = _annahme(fall, key, ordnung)
    assert ohne.exit_code == 20 and ohne.errors[0]["code"] == "mandat"
    assert len(list((fall / "entscheide").glob("A-Q1-*.json"))) == 1


def test_andere_ordnung_oder_anderer_schluessel_ist_kein_identischer_entscheid(fall, tmp_path):
    key = tmp_path / "va.key"
    fp = schluessel_anlegen(key)
    ordnung = ordnung_schreiben(tmp_path / "ordnung.json", {
        VA: {"schluessel_sha256": fp, "schluesselklasse": "mensch", "gates": ["*"]},
    })
    erste = _annahme(fall, key, ordnung)
    assert erste.exit_code == 0, erste.errors
    s1 = _snapshot(erste)
    # (b) geaenderte Ordnung, gleiche Rolle: kein Treffer, neuer Snapshot in der Kette
    ordnung2 = ordnung_schreiben(tmp_path / "ordnung2.json", {
        VA: {"schluessel_sha256": fp, "schluesselklasse": "mensch", "gates": ["*"]},
        "mensch/quell-aktuar": {"schluessel_sha256": "9" * 64, "schluesselklasse": "mensch", "gates": []},
    })
    zweite = _annahme(fall, key, ordnung2)
    assert zweite.exit_code == 0, zweite.errors
    assert not zweite.summary.get("bereits_vorhanden")
    s2 = _snapshot(zweite)
    assert s2["zeichnung"]["ordnung_sha256"] == hashlib.sha256(ordnung2.read_bytes()).hexdigest()
    assert s1["snapshot_sha256"] in s2["vorgaenger"]
    # (a) anderer Schluessel derselben Rolle: ebenfalls kein Treffer
    key2 = tmp_path / "va2.key"
    fp2 = schluessel_anlegen(key2, b"another-key-of-the-same-role!!" * 2)
    ordnung3 = ordnung_schreiben(tmp_path / "ordnung3.json", {
        VA: {"schluessel_sha256": fp2, "schluesselklasse": "mensch", "gates": ["*"]},
    })
    # Die Kette verlangt die Schluessel der Vorgaenger-Signaturen im Ring;
    # der ZULETZT genannte Schluessel zeichnet (key2), der alte prueft nur.
    dritte = _annahme(fall, key, ordnung3, "--freigabe-schluessel", str(key2))
    assert dritte.exit_code == 0, dritte.errors
    assert not dritte.summary.get("bereits_vorhanden")
    assert _snapshot(dritte)["freigabe"]["schluessel_sha256"] != s1["freigabe"]["schluessel_sha256"]
