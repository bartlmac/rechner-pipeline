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

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import _provenienz, gate_entscheid, kernstand_belegen
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
        "--repo-root", str(REPO_ROOT),
        # A-B1 zeichnet mensch/betrieb (ADR-018), nicht die Rolle des Falls.
        *annahme_args(fall, rolle="mensch/betrieb", gates=["A-B1"]), *extra,
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


def _pakethash_unabhaengig() -> str:
    """Den signierten Paketinhalt ohne Aufruf des Gate-Hashers nachrechnen."""
    paket = REPO_ROOT / "src" / "rechner_pipeline"
    digest = hashlib.sha256()
    for pfad in sorted(p for p in paket.rglob("*")
                       if p.is_file() and p.suffix in {".py", ".xml"}):
        name = pfad.relative_to(paket).as_posix().encode("utf-8")
        inhalt = pfad.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(inhalt).to_bytes(8, "big"))
        digest.update(inhalt)
    return digest.hexdigest()


def test_ab1_nimmt_ohne_git_die_gueltige_image_revision_signiert_auf(
        fall, monkeypatch):
    revision = "c" * 40
    monkeypatch.setattr(_provenienz, "_git_lesen", lambda *_: None)
    monkeypatch.setenv("PLV_IMAGE_REVISION", revision)
    anker, satz = _anker(fall)
    ergebnis = _ab1(fall, anker, satz)
    assert ergebnis.exit_code == 0, ergebnis.errors
    pfad = Path(ergebnis.paths["snapshot"])
    snapshot = json.loads(pfad.read_text(encoding="utf-8"))
    assert snapshot["system"] == {
        "commit": revision, "branch": "unbekannt", "dirty": "unbekannt",
        "quellcode_sha256": _pakethash_unabhaengig(),
    }
    assert ergebnis.summary["system_commit"] == revision[:12]
    assert ergebnis.summary["system_dirty"] == "unbekannt"
    assert gate_entscheid.pruefe_snapshot_ohne_schluessel(snapshot, pfad.name) == []
    key = (fall.parent / "p9-freigabe.key").read_bytes()
    ring = {hashlib.sha256(key).hexdigest(): key}
    assert gate_entscheid._pruefe_freigabe(snapshot, ring) == []
    _kette, _spitzen, fehler = gate_entscheid._lade_snapshot_kette(
        fall / "entscheide", "A-B1", fall, ring, snapshot["system"])
    assert fehler == []

    nochmal = _ab1(fall, anker, satz)
    assert nochmal.exit_code == 0 and nochmal.summary["bereits_vorhanden"] is True
    assert nochmal.paths["snapshot"] == str(pfad)

    verbogen = dict(snapshot, system={**snapshot["system"], "commit": "d" * 40})
    assert gate_entscheid._pruefe_freigabe(verbogen, ring)
    pfad.write_text(json.dumps(verbogen), encoding="utf-8")
    assert gate_entscheid._lade_snapshot_kette(
        fall / "entscheide", "A-B1", fall, ring, snapshot["system"])[2]


def test_ab1_bevorzugt_den_lesbaren_git_commit(fall, monkeypatch):
    monkeypatch.setenv("PLV_IMAGE_REVISION", "c" * 40)
    git_commit = _provenienz.git_stand(REPO_ROOT)["commit"]
    assert git_commit != "unbekannt"
    anker, satz = _anker(fall)
    ergebnis = _ab1(fall, anker, satz)
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text("utf-8"))
    assert snapshot["system"]["commit"] == git_commit
    assert ergebnis.summary["system_commit"] == git_commit[:12]


@pytest.mark.parametrize("revision", [None, "unbekannt", "a" * 12,
                                             "A" * 40, "g" * 40, "a" * 41])
def test_ab1_belaesst_ungueltige_image_revision_bei_unbekannt(
        fall, monkeypatch, revision):
    monkeypatch.setattr(_provenienz, "_git_lesen", lambda *_: None)
    if revision is None:
        monkeypatch.delenv("PLV_IMAGE_REVISION", raising=False)
    else:
        monkeypatch.setenv("PLV_IMAGE_REVISION", revision)
    anker, satz = _anker(fall)
    ergebnis = _ab1(fall, anker, satz)
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text("utf-8"))
    assert snapshot["system"]["commit"] == "unbekannt"
    assert ergebnis.summary["system_commit"] == "unbekannt"


@pytest.mark.parametrize("gate", ["A-K2", "A-M4"])
def test_andere_gates_erhellen_ohne_git_den_systemstand_nicht(
        fall, monkeypatch, gate):
    monkeypatch.setattr(_provenienz, "_git_lesen", lambda *_: None)
    monkeypatch.setenv("PLV_IMAGE_REVISION", "c" * 40)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", gate, "--entscheid", "abgelehnt",
        "--rolle", "mensch/rechenkern" if gate == "A-K2" else "mensch/aktuariat",
        "--entscheider", "Pruefung", "--begruendung", "Beleg fehlt.",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, fuer=gate),
    ])
    assert ergebnis.exit_code == 0, ergebnis.errors
    snapshot = json.loads(Path(ergebnis.paths["snapshot"]).read_text("utf-8"))
    assert snapshot["system"]["commit"] == "unbekannt"
    assert snapshot["system"]["branch"] == "unbekannt"
    assert snapshot["system"]["dirty"] == "unbekannt"
    assert _provenienz.systemstand(REPO_ROOT)["commit"] == "unbekannt"


def test_ak2_verweigert_ohne_lesbaren_git_stand_weiter(tmp_path, monkeypatch):
    aenderung = kernstand_belegen.baue_aenderungsbeleg(
        REPO_ROOT, "HEAD", "Probe des Git-Belegvertrags")
    pfad = tmp_path / "aenderung.json"
    pfad.write_text(json.dumps(aenderung), encoding="utf-8")
    monkeypatch.setattr(_provenienz, "_git_lesen", lambda *_: None)
    monkeypatch.setattr(gate_entscheid, "git_stand", lambda *_: {
        "commit": "unbekannt", "branch": "unbekannt", "dirty": "unbekannt"})
    monkeypatch.setenv("PLV_IMAGE_REVISION", "c" * 40)
    fehler = gate_entscheid.pruefe_kernaenderung(pfad, tmp_path, repo_root=REPO_ROOT)
    assert any("Git-Stand ist nicht lesbar" in meldung for meldung in fehler), fehler
