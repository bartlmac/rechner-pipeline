"""T26-03, zu Ende: der Betriebseingang liest den Rollenvertrag und prueft die Zeichnung.

Weg 2 (Entscheid des Maintainers 2026-09-22): Der Belegrollen-Vertrag wohnt
in ``models.belegrollen`` — einmal definiert, von Gate und Betrieb gelesen.
Die Zeichnungsschicht ist zu Ende gebaut: ``models.freigabe`` haelt
Schluesselring, Signieren und Pruefen (aus dem Gate gezogen, das Gate
delegiert), der Betriebseingang verifiziert die Freigabesignatur bei der
Registrierung, verlangt Schema 7 (Schluesselklasse) und der Tageslauf nimmt
keinen unverifizierten Eingang. Zwei unabhaengige Zeugen: der eigene
Vollstaendigkeitscheck gegen den Vertrag und das verifizierte Siegel.

Knoten: system/betrieb
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.models import belegrollen as br
from rechner_pipeline.models import freigabe as fg
from rechner_pipeline.models.schemas import p9_snapshot_sha256
from rechner_pipeline.models.zeichnung import GATES_MIT_PFLICHTBELEGEN
from tests.freigabe_testschluessel import FREMDER_SCHLUESSEL, TESTKEY, TESTRING
from tests.test_betrieb_uebernahme import PLV, STICHTAG, _fall, am4_snapshot


# --- der Vertrag in models ---------------------------------------------------

def test_der_vertrag_wohnt_in_models_und_die_scopes_bleiben_gleich():
    """Ratsche: ``fall`` darf nichts importieren, also spiegelt models die
    Scope-Liste — exakt gleich, oder rot. Und die Gates MIT Pflichtbelegen
    sind exakt die Schluessel des Vertrags (dieselbe Ratsche wie
    tests/test_gate_vokabel_ab1.py, jetzt gegen models).

    Mutationsprobe: einen Scope in models streichen -> rot; ein Gate aus
    BELEGROLLEN nehmen -> rot."""
    assert br.SCOPES == fall_mod.FALL_SCOPES
    assert set(br.BELEGROLLEN) == set(GATES_MIT_PFLICHTBELEGEN)
    assert br.am4_belegrollen("bestand") == [
        "pq3_ledger", "aq1_snapshot", "am1_snapshot", "am2_snapshot", "am3_snapshot",
        "pk1_belege", "pb1_ledger", "migrationssuite", "fuehrungsprobe", "abnahmebericht"]
    assert not hasattr(fall_mod, "BELEGROLLEN") and not hasattr(fall_mod, "belegrollen")
    with pytest.raises(br.BelegrollenFehler, match="Scope"):
        br.belegrollen("A-M4", "irgendwas")


# --- DoRAs Fall: der Betrieb prueft die Rollenmenge ----------------------------

def test_ein_snapshot_mit_nur_einer_pflichtrolle_wird_nicht_uebernommen(tmp_path):
    """DoRAs schaerfster Einzelfall: Ein A-M4-Snapshot, dessen einzige
    Pflichtrolle pb1_ledger ist, wurde uebernommen — solange Beleggraph und
    Tabellen stimmten. Jetzt liest der Betriebseingang denselben Vertrag wie
    das Gate: nicht EXAKT die zehn Rollen des Bestands-Scopes, keine Abnahme.

    Positivkontrolle: derselbe Fall mit allen zehn Rollen tritt ein.
    Mutationsprobe: ``erwartete_rollen`` in lies_am4_snapshot wieder
    weglassen -> rot."""
    voll = _fall(tmp_path / "voll", name="voll")
    ueb.eingang_anlegen(tmp_path / "daten", voll, STICHTAG)
    duenn = _fall(tmp_path / "duenn", name="duenn", snapshot=None)
    sha = json.loads((duenn / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json").read_bytes())
    from tests.test_betrieb_uebernahme import _pb1_ledger
    ledger_sha = _pb1_ledger(duenn)
    daten = am4_snapshot("duenn", pb1_ledger_sha=ledger_sha, rollen=("pb1_ledger",))
    (duenn / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten), encoding="utf-8")
    (duenn / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="nicht exakt die aus dem Scope abgeleiteten Rollen"):
        ueb.eingang_anlegen(tmp_path / "daten-duenn", duenn, STICHTAG)
    assert not (tmp_path / "daten-duenn" / "uebernahme" / "duenn").exists()


# --- die Zeichnungsschicht: Signatur, Schema, zwei Zeugen ----------------------

def _fall_mit_snapshot(wurzel: Path, name: str, **snapshot_kw) -> Path:
    from tests.test_betrieb_uebernahme import _pb1_ledger
    fall = _fall(wurzel, name=name, snapshot=None)
    daten = am4_snapshot(name, pb1_ledger_sha=_pb1_ledger(fall), **snapshot_kw)
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    return fall


def test_gate_und_betrieb_pruefen_dieselbe_signatur():
    """Eine Regel, zwei Aufrufer: Das Gate signiert und prueft ueber
    models.freigabe (seine alten Namen delegieren), der Betrieb prueft
    dieselbe Funktion. Roundtrip, Manipulation, fremder Schluessel."""
    daten = am4_snapshot("probe")
    assert daten["freigabe"]["verfahren"] == "hmac-sha256-v1"
    assert fg.pruefe_freigabe(daten, TESTRING) == []
    assert gate_entscheid._pruefe_freigabe(daten, TESTRING) == []
    assert gate_entscheid._freigabe_fuer(
        {k: v for k, v in daten.items() if k not in ("freigabe", "snapshot_sha256")}, TESTKEY
    ) == daten["freigabe"]
    manipuliert = dict(daten); manipuliert["begruendung"] = "doch nicht"
    assert any("stimmt nicht" in f for f in fg.pruefe_freigabe(manipuliert, TESTRING))
    fremd = am4_snapshot("probe", schluessel=FREMDER_SCHLUESSEL)
    assert any("nicht bereitgestellten" in f for f in fg.pruefe_freigabe(fremd, TESTRING))


def test_der_betriebseingang_verifiziert_die_signatur_und_der_tageslauf_verlangt_sie(tmp_path, monkeypatch):
    """Zwei Zeugen. Mit Ring: eine manipulierte oder fremd signierte Abnahme
    tritt nicht ein; eine echte wird als verifiziert registriert. Ohne Ring:
    registriert mit ``signatur_verifiziert: False`` als benanntem Zustand —
    und ``lies_uebernahme`` (der Tageslauf) nimmt sie NICHT in die Fuehrung.

    Mutationsprobe: die Signaturpruefung in lies_am4_snapshot entfernen ->
    die Fremdschluessel-Zusicherung rot; die Verlangung in lies_uebernahme
    entfernen -> die letzte Zusicherung rot."""
    config = load_config(PLV)
    echt = _fall_mit_snapshot(tmp_path / "a", "echt")
    ziel = ueb.eingang_anlegen(tmp_path / "daten", echt, STICHTAG)
    eingang = json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))
    assert eingang["zeichnung"]["signatur_verifiziert"] is True
    assert eingang["zeichnung"]["schluesselklasse"] == "mensch"
    assert len(ueb.lies_uebernahme(ziel, config).bestand) == 3

    fremd = _fall_mit_snapshot(tmp_path / "b", "fremd", schluessel=FREMDER_SCHLUESSEL)
    with pytest.raises(ueb.UebernahmeError, match="nicht bereitgestellten Schluessel"):
        ueb.eingang_anlegen(tmp_path / "daten", fremd, STICHTAG)
    assert not (tmp_path / "daten" / "uebernahme" / "fremd").exists(), "kein halber Eingang"

    # Manipulation NACH der Signatur: Inhalt geaendert, Selbstadressierung
    # nachgezogen — die Signatur passt nicht mehr.
    mani = _fall_mit_snapshot(tmp_path / "c", "mani")
    pfad = next((mani / "entscheide").glob("A-M4-*.json"))
    d = json.loads(pfad.read_text(encoding="utf-8")); d["begruendung"] = "umgeschrieben"
    d["snapshot_sha256"] = p9_snapshot_sha256(d); pfad.unlink()
    (mani / "entscheide" / f"A-M4-{d['snapshot_sha256']}.json").write_text(json.dumps(d), encoding="utf-8")
    (mani / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": d["snapshot_sha256"]}}), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="stimmt nicht mit dem Snapshot-Inhalt"):
        ueb.eingang_anlegen(tmp_path / "daten", mani, STICHTAG)

    # Ohne Ring: benannter Zustand, und die Fuehrung verweigert.
    monkeypatch.setattr(ueb, "_STANDARD_SCHLUESSELRING", None)
    ohne = _fall_mit_snapshot(tmp_path / "d", "ohne")
    ziel2 = ueb.eingang_anlegen(tmp_path / "daten", ohne, STICHTAG)
    assert json.loads((ziel2 / "eingang.json").read_text(encoding="utf-8"))["zeichnung"]["signatur_verifiziert"] is False
    with pytest.raises(ueb.UebernahmeError, match="ohne verifizierte Freigabesignatur"):
        ueb.lies_uebernahme(ziel2, config)


def test_ein_altsnapshot_ohne_schluesselklasse_tritt_nicht_ein(tmp_path):
    """Schema 6 traegt keine Schluesselklasse. Lesen (Seite) geht weiter —
    registriert wird nur Schema 7: die Zeichnung ist Teil des Vertrags.
    Mutationsprobe: die Schema-Pruefung in eingang_anlegen entfernen -> rot."""
    alt = _fall_mit_snapshot(tmp_path / "alt", "alt", schema=6)
    z = ueb.pruefe_am4_snapshot(alt, json.loads((alt / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").read_text())["summary"]["snapshot_sha256"])
    assert z["schema_version"] == 6 and z["schluesselklasse"] == "nicht ausgewiesen"
    with pytest.raises(ueb.UebernahmeError, match="Schema 6.*Schema 7"):
        ueb.eingang_anlegen(tmp_path / "daten", alt, STICHTAG)


def test_der_schluesselring_weist_schluessel_im_vertrauensraum_ab(tmp_path):
    """Die Ladepruefung des Gates lebt jetzt in models und gilt fuer den
    Betrieb: ein Schluessel INNERHALB des Vertrauensraums ist keiner."""
    fall = tmp_path / "fall"; fall.mkdir()
    innen = fall / "p9.key"; innen.write_bytes(TESTKEY); innen.chmod(0o600)
    ring, fehler, aktiv = fg.lade_schluesselring([str(innen)], ausserhalb=fall)
    assert ring == {} and any("innerhalb des Vertrauensraums" in f for f in fehler)
    aussen = tmp_path / "p9.key"; aussen.write_bytes(TESTKEY); aussen.chmod(0o600)
    ring, fehler, aktiv = fg.lade_schluesselring([str(aussen)], ausserhalb=fall)
    assert fehler == [] and ring == TESTRING and aktiv == next(iter(TESTRING))
