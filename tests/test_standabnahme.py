"""Der Stand, auf dem ein Fall laeuft, ist abgenommen — EINE Regel fuer Kern und T-Box.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01):
"T-Box-Erweiterung muss auch ein Abnahmepunkt im Prozess sein, wird bei
'keiner Aenderung' durchgewunken (da keine Aenderung vorhanden)." A-M4
verlangt je Gegenstand (Kernstand A-K2, T-Box-Stand A-O1), dass der Stand
abgenommen ist: (a) im Fall gezeichnet, (b) "keine Aenderung" ueber einen
Verweis auf einen frueher angenommenen Snapshot, (c) nur T-Box: die
Versionslinie hat ein Element.

Heute laeuft jeder Fall auf T-Box 0.1.0 und faellt unter (c). Die Proben
fuer (a) und (b) der T-Box verlaengern die Versionslinie KUENSTLICH im Test
(monkeypatch) — das Modul ``ontologie/tbox.py`` bleibt unberuehrt.

Mutationsproben (Bauprotokoll): (b) ohne Gleichheitspruefung des Stands;
(b) mit dem Snapshot einer unberechtigten Rolle; (c) bei zwei Elementen in
der Linie; A-O1-Rollenregel aus — jede macht hier einen Test rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid, stand_belegen
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models.belegrollen import belegrollen
from rechner_pipeline.models.schemas import P9_GATES_MIT_STAND
from rechner_pipeline.models.zeichnung import GUELTIGE_GATES
from rechner_pipeline.ontologie import tbox
from tests.zeichnung_fixture import ARCHITEKTUR, annahme_args, zeichne_kernstand

REPO = Path(__file__).resolve().parents[1]
LINIE_MIT_UEBERGANG = ("0.0.9", tbox.TBOX_VERSION)


def _fall(wurzel: Path, *, mit_kernstand: bool = True) -> Path:
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012

    wurzel.mkdir(parents=True, exist_ok=True)
    fall = _bereite_fall(wurzel, ("klv/tg2012",), mit_kernstand=mit_kernstand)
    assert _o3_tg2012(fall).exit_code == 0
    return fall


def _am4(fall: Path):
    from tests.test_pk1_am4_beweisvertrag import _p9_annahme

    return _p9_annahme(fall, "A-M4", "Migration abgenommen")


def _snapshot(fall: Path, gate: str) -> Path:
    (pfad,) = list((fall / "entscheide").glob(f"{gate}-*.json"))
    return pfad


def _verweisen(fall: Path, gate: str, snapshot: Path):
    return stand_belegen.main([
        "verweisen", "--fall", str(fall), "--repo-root", str(REPO),
        "--gate", gate, "--snapshot", str(snapshot)])


def _zeichne_tboxstand(fall: Path, *schluessel_args: str):
    """Den T-Box-Uebergang vorlegen und zeichnen (mensch/architektur)."""
    vermerk = fall / "abgeleitet" / "tbox" / "vermerk.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text("Aenderungsvermerk: Raucherkennzeichen in der T-Box.\n", encoding="utf-8")
    beleg = stand_belegen.main([
        "tbox", "--fall", str(fall), "--repo-root", str(REPO),
        "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "Raucherkennzeichen"])
    assert beleg.exit_code == 0, beleg.errors
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "raucher", "wirkung": "tariflich",
                    "begruendung": "Zuschlag je Raucherstatus"}]}), encoding="utf-8")
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "it-verantwortung", "--begruendung", "Diffs der T-Box gesehen",
        "--repo-root", str(REPO), *(schluessel_args or annahme_args(fall, fuer="A-O1"))])


# --------------------------------------------------------------------------- #
# Die eine Regel: Gegenstaende, Rollen, Schema
# --------------------------------------------------------------------------- #


def test_die_gegenstaende_sind_eine_menge_an_jeder_stelle():
    """Ratsche: Gegenstaende == Gates mit ``stand`` im Snapshot; jede Rolle
    ist Pflichtrolle von A-M4 in beiden Scopes; jedes Gate ist zeichenbar."""
    assert tuple(g.gate for g in sa.GEGENSTAENDE) == P9_GATES_MIT_STAND
    for scope in ("tarif", "bestand"):
        assert {g.rolle for g in sa.GEGENSTAENDE} <= set(belegrollen("A-M4", scope))
    assert {g.gate for g in sa.GEGENSTAENDE} <= set(GUELTIGE_GATES)
    assert [g.gate for g in sa.GEGENSTAENDE if g.basislinie] == ["A-O1"]


def test_heute_liegt_die_t_box_auf_der_basislinie():
    """Messung: Die Linie hat ein Element — jeder bestehende Weg zu A-M4
    faellt fuer die T-Box unter (c)."""
    assert tuple(tbox.TBOX_VERSIONEN) == (tbox.TBOX_VERSION,)
    assert stand_belegen.basislinie_gilt()


def test_der_lebende_stand_je_gegenstand():
    kern = stand_belegen.lebender_stand("A-K2", REPO)
    assert set(kern) == {"version", "kern_sha256", "referenzwerte_sha256", "kernstand_sha256"}
    t = stand_belegen.lebender_stand("A-O1", REPO)
    assert t == {"version": tbox.TBOX_VERSION, "tbox_sha256": stand_belegen.tbox_modul_sha256()}


# --------------------------------------------------------------------------- #
# Kernstand: (b) "keine Aenderung" ueber einen Verweis
# --------------------------------------------------------------------------- #


def test_kern_keine_aenderung_ueber_den_verweis_auf_einen_frueheren_snapshot(tmp_path):
    frueher = _fall(tmp_path / "a")
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    assert _am4(neu).exit_code != 0
    verweis = _verweisen(neu, "A-K2", _snapshot(frueher, "A-K2"))
    assert verweis.exit_code == 0, verweis.errors
    am4 = _am4(neu)
    assert am4.exit_code == 0, am4.errors
    snap = json.loads(_snapshot(frueher, "A-K2").read_text(encoding="utf-8"))
    daten = json.loads((neu / "abgeleitet/kern/verweis.json").read_text(encoding="utf-8"))
    assert set(daten) == sa.VERWEIS_FELDER and daten["snapshot"] == snap
    eintrag = am4.summary["standabnahmen"]["kernstand"]
    assert eintrag["weg"] == sa.KEINE_AENDERUNG
    assert eintrag["anzeige"] == (
        f"keine Aenderung seit Abnahme {snap['snapshot_sha256'][:16]} "
        f"(Fall fall, entscheide/A-K2-{snap['snapshot_sha256']}.json); "
        + ka.ANZEIGE_REGRESSION)
    assert not list((neu / "entscheide").glob("A-K2-*.json")), "kein neuer Entscheid"


def test_kern_verweis_auf_einen_anderen_stand_wird_verweigert(tmp_path, monkeypatch):
    """Durchgewunken heisst belegt unveraendert: Der abgenommene Stand wird
    per == gegen den lebenden gehalten.

    Mutationsprobe: die Gleichheitspruefung in verweis_fehler entfernen -> rot."""
    frueher = _fall(tmp_path / "a")
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    assert _verweisen(neu, "A-K2", _snapshot(frueher, "A-K2")).exit_code == 0
    echt = stand_belegen.lebender_stand

    def anderer_kern(gate, repo_root):
        stand = echt(gate, repo_root)
        return {**stand, "version": "99.0.0"} if gate == "A-K2" and stand else stand

    monkeypatch.setattr(stand_belegen, "lebender_stand", anderer_kern)
    am4 = _am4(neu)
    assert am4.exit_code != 0
    assert "nicht der lebende" in am4.errors[0]["message"], am4.errors


def test_kern_verweis_auf_den_snapshot_einer_unberechtigten_rolle_wird_verweigert(tmp_path):
    """Dieselbe Rollenregel wie fuer jede Abnahme, auf der etwas gruendet:
    Die Ordnung des Falls gibt der Rolle des frueheren Schluessels A-K2 nicht.

    Mutationsprobe: den Rollenregel-Aufruf im Verweis-Zweig aussetzen -> rot."""
    frueher = _fall(tmp_path / "a")
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    assert _verweisen(neu, "A-K2", _snapshot(frueher, "A-K2")).exit_code == 0
    ordnung_pfad = neu.parent / "zeichnungsordnung.json"
    ordnung = json.loads(ordnung_pfad.read_text(encoding="utf-8"))
    ordnung["rollen"]["mensch/rechenkern"]["gates"] = []
    ordnung_pfad.write_text(json.dumps(ordnung), encoding="utf-8")
    am4 = _am4(neu)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "unberechtigten Schluessel" in meldung and "A-K2" in meldung, meldung


def test_eine_kette_im_fall_geht_jedem_verweis_vor(tmp_path):
    """Eine Ablehnung im Fall laesst sich nicht durch einen Verweis umgehen."""
    frueher = _fall(tmp_path / "a")
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    abgelehnt = gate_entscheid.main([
        "--fall", str(neu), "--gate", "A-K2", "--entscheid", "abgelehnt",
        "--rolle", "agent/rechenkern", "--entscheider", "agent", "--begruendung", "offen",
        "--repo-root", str(REPO)])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    assert _verweisen(neu, "A-K2", _snapshot(frueher, "A-K2")).exit_code == 0
    am4 = _am4(neu)
    assert am4.exit_code != 0
    assert "geht jedem Verweis vor" in am4.errors[0]["message"], am4.errors


def test_der_verweis_produzent_nimmt_keine_ablehnung_und_kein_fremdes_gate(tmp_path):
    frueher = _fall(tmp_path / "a")
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    fremd = _verweisen(neu, "A-O1", _snapshot(frueher, "A-K2"))
    assert fremd.exit_code != 0 and "gehoert zu 'A-K2'" in fremd.errors[0]["message"]
    snap = json.loads(_snapshot(frueher, "A-K2").read_text(encoding="utf-8"))
    falsch = tmp_path / "abgelehnt.json"
    falsch.write_text(json.dumps({**snap, "entscheid": "abgelehnt"}), encoding="utf-8")
    abgelehnt = _verweisen(neu, "A-K2", falsch)
    assert abgelehnt.exit_code != 0 and "keine Annahme" in abgelehnt.errors[0]["message"]


# --------------------------------------------------------------------------- #
# T-Box-Stand: (c), (a), (b) — mit kuenstlich verlaengerter Versionslinie
# --------------------------------------------------------------------------- #


def test_t_box_mit_uebergang_braucht_eine_abnahme(tmp_path, monkeypatch):
    """Zwei Elemente in der Linie: Es gab einen Uebergang, die Basislinie
    traegt nicht mehr. Ohne A-O1 und ohne Verweis verweigert A-M4.

    Mutationsprobe: basislinie_gilt auch bei zwei Elementen -> rot."""
    fall = _fall(tmp_path)
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    am4 = _am4(fall)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "T-Box-Stand" in meldung and "stand_belegen tbox" in meldung, meldung


def test_t_box_abnahme_im_fall(tmp_path, monkeypatch):
    fall = _fall(tmp_path)
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    ao1 = _zeichne_tboxstand(fall)
    assert ao1.exit_code == 0, ao1.errors
    snap = json.loads(Path(ao1.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snap["rolle"] == ARCHITEKTUR and snap["stand"]["version"] == tbox.TBOX_VERSION
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors
    eintrag = am4.summary["standabnahmen"]["tboxstand"]
    assert eintrag["weg"] == sa.ABNAHME_IM_FALL
    assert eintrag["anzeige"] == sa.anzeige_im_fall("A-O1", snap["snapshot_sha256"])
    assert am4.summary["pflichtbelege"]["tboxstand"] == [snap["snapshot_sha256"]]


def test_a_o1_zeichnet_nur_mensch_architektur(tmp_path, monkeypatch):
    fall = _fall(tmp_path)
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    falsch = _zeichne_tboxstand(fall, *annahme_args(fall))
    assert falsch.exit_code != 0 and "A-O1" in falsch.errors[0]["message"], falsch.errors


def test_a_m4_verweigert_ein_a_o1_dessen_rollenfeld_nicht_die_rolle_des_schluessels_ist(
        tmp_path, monkeypatch):
    """Rollenfeld gefaelscht, mit dem echten Schluessel neu signiert.

    Mutationsprobe: die Rollenregel fuer den Snapshot im Fall aussetzen -> rot."""
    from tests.test_abnahme_rolle_klasse import _behauptet, _neu_signiert

    fall = _fall(tmp_path)
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    assert _zeichne_tboxstand(fall).exit_code == 0
    pfad = _snapshot(fall, "A-O1")
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    schluessel = (fall.parent / "p9-architektur.key").read_bytes()
    neu = _neu_signiert(daten, schluessel, **_behauptet(daten, "mensch/aktuariat"))
    pfad.unlink()
    (pfad.parent / f"A-O1-{neu['snapshot_sha256']}.json").write_text(
        json.dumps(neu, ensure_ascii=False), encoding="utf-8")
    am4 = _am4(fall)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "A-O1" in meldung and "behauptet als Rolle" in meldung, meldung


def test_t_box_keine_aenderung_ueber_den_verweis(tmp_path, monkeypatch):
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    frueher = _fall(tmp_path / "a")
    assert _zeichne_tboxstand(frueher).exit_code == 0
    neu = _fall(tmp_path / "b")
    assert _am4(neu).exit_code != 0
    assert _verweisen(neu, "A-O1", _snapshot(frueher, "A-O1")).exit_code == 0
    am4 = _am4(neu)
    assert am4.exit_code == 0, am4.errors
    snap = json.loads(_snapshot(frueher, "A-O1").read_text(encoding="utf-8"))
    eintrag = am4.summary["standabnahmen"]["tboxstand"]
    assert eintrag["anzeige"] == sa.anzeige_keine_aenderung(
        snap["snapshot_sha256"], sa.herkunft(snap))
    assert eintrag["anzeige"].startswith("keine Aenderung seit Abnahme ")


def test_die_basislinie_steht_woertlich_im_a_m4_snapshot(tmp_path):
    fall = _fall(tmp_path)
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors
    snapshot = json.loads(Path(am4.paths["snapshot"]).read_text(encoding="utf-8"))
    assert snapshot["standabnahmen"]["tboxstand"]["anzeige"] == (
        f"keine Aenderung: die Versionslinie der T-Box hat ein Element "
        f"({tbox.TBOX_VERSION}), es gab keinen Uebergang")
