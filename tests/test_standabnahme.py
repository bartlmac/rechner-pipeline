"""Der Stand, auf dem ein Fall laeuft, ist abgenommen — EINE Regel fuer Kern und T-Box.

Entscheid des Maintainers 2026-10-01 (ADR-018, Nachtrag 2026-10-01):
"T-Box-Erweiterung muss auch ein Abnahmepunkt im Prozess sein, wird bei
'keiner Aenderung' durchgewunken (da keine Aenderung vorhanden)." A-M4
verlangt je Gegenstand (Kernstand A-K2, T-Box-Stand A-O1), dass der Stand
abgenommen ist: (a) im Fall gezeichnet, (b) "keine Aenderung" ueber einen
Verweis auf die GELTENDE Abnahme der Linie (seit Pruefrunde G, G11; vorher
auf einen beliebigen frueher angenommenen Snapshot), (c) nur T-Box: die
Versionslinie hat ein Element (entfallen, ADR-025).

Seit T-Box 0.2.0 (Entwurf, ADR-024) hat die ECHTE Versionslinie einen
Uebergang (0.1.0 -> 0.2.0): Jeder Fall auf dem neuen Stand braucht (a) oder
(b), die Proben dafuer laufen auf der echten Linie. Weg (c) gibt es nur noch
mit einer KUENSTLICH einelementigen Linie im Test (monkeypatch) — sonst
pruefte die Basislinien-Probe nichts mehr. Solange die echte Linie noch ein
Element hatte, war es umgekehrt (kuenstlich verlaengert); ``LINIE_MIT_UEBERGANG``
nimmt die echte Linie, sobald sie einen Uebergang traegt.

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
from tests.zeichnung_fixture import linie_args, ARCHITEKTUR, annahme_args, zeichne_kernstand

REPO = Path(__file__).resolve().parents[1]
LINIE_MIT_UEBERGANG = (tuple(tbox.TBOX_VERSIONEN) if len(tbox.TBOX_VERSIONEN) > 1
                       else ("0.0.9", tbox.TBOX_VERSION))
#: Die Basislinie (Weg c) — kuenstlich: ein Element.
LINIE_OHNE_UEBERGANG = (tbox.TBOX_VERSION,)


def _fall(wurzel: Path, *, mit_kernstand: bool = True,
          mit_tboxstand: bool = True) -> Path:
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012

    wurzel.mkdir(parents=True, exist_ok=True)
    fall = _bereite_fall(wurzel, ("klv/tg2012",), mit_kernstand=mit_kernstand,
                         mit_tboxstand=mit_tboxstand)
    assert _o3_tg2012(fall).exit_code == 0
    return fall


def _am4(fall: Path):
    from tests.test_pk1_am4_beweisvertrag import _p9_annahme

    return _p9_annahme(fall, "A-M4", "Migration abgenommen")


def _snapshot(fall: Path, gate: str) -> Path:
    (pfad,) = list((fall / "entscheide").glob(f"{gate}-*.json"))
    return pfad


def _in_der_linie(fall: Path, gate: str) -> dict:
    """Den Gegenstand in der Linie neben dem Fall abnehmen (Erstabnahme);
    Rueckgabe: die geltende Spitze."""
    from tests.test_erstabnahme_linie import _zeichne_in_linie

    ergebnis = _zeichne_in_linie(fall.parent / "linie", gate)
    assert ergebnis.exit_code == 0, ergebnis.errors
    spitze, fehler = stand_belegen.geltende_spitze(fall.parent / "linie", gate)
    assert spitze is not None, fehler
    return spitze


def _verweisen(fall: Path, gate: str):
    """Weg (b) ueber die Linie — der einzige Weg seit Pruefrunde G (G11):
    ``verweisen --snapshot`` ist entfallen. Die sieben Tests, die vorher ueber
    ``--snapshot`` auf den Snapshot eines frueheren Falls verwiesen (sechs
    hier, einer in ``test_erstabnahme_linie``), verweisen jetzt auf die
    geltende Abnahme der Linie."""
    return stand_belegen.main([
        "verweisen", "--fall", str(fall), "--repo-root", str(REPO),
        "--gate", gate, "--linie", str(fall.parent / "linie")])


def _zeichne_tboxstand(fall: Path, *schluessel_args: str):
    """Den T-Box-Uebergang vorlegen und zeichnen (mensch/architektur)."""
    vermerk = fall / "abgeleitet" / "tbox" / "vermerk.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text("Aenderungsvermerk: Raucherkennzeichen in der T-Box.\n", encoding="utf-8")
    beleg = stand_belegen.main([
        "tbox", "--fall", str(fall), "--vorher-linie", linie_args(fall)[1],
        "--repo-root", str(REPO),
        "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "Raucherkennzeichen"])
    assert beleg.exit_code == 0, beleg.errors
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "raucher", "wirkung": "tariflich",
                    "begruendung": "Zuschlag je Raucherstatus"}]}), encoding="utf-8")
    return gate_entscheid.main([
        "--fall", str(fall), *linie_args(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "it-verantwortung", "--begruendung", "Diffs der T-Box gesehen",
        "--repo-root", str(REPO), *(schluessel_args or annahme_args(fall, fuer="A-O1"))])


# --------------------------------------------------------------------------- #
# Die eine Regel: Gegenstaende, Rollen, Schema
# --------------------------------------------------------------------------- #


def test_die_gegenstaende_sind_eine_menge_an_jeder_stelle():
    """Ratsche (==): Gegenstaende == Gates mit ``stand`` im Snapshot; die
    A-M4-Gegenstaende == die Standrollen von A-M4 in beiden Scopes; die
    Gates der Linie == die Gates mit Belegrollen im Scope ``linie``; jedes
    Gate ist zeichenbar (ADR-025)."""
    from rechner_pipeline.models.belegrollen import BELEGROLLEN, LINIE

    assert tuple(g.gate for g in sa.GEGENSTAENDE) == P9_GATES_MIT_STAND
    assert [g.gate for g in sa.GEGENSTAENDE] == ["A-K2", "A-O1", "A-T1", "A-B3"]
    stand_rollen = {"kernstand", "tboxstand", "tarifwerkstand"}
    for scope in ("tarif", "bestand"):
        assert {g.rolle for g in sa.AM4_GEGENSTAENDE} == stand_rollen
        assert stand_rollen <= set(belegrollen("A-M4", scope))
    assert {g for g, v in BELEGROLLEN.items() if LINIE in v} == set(sa.LINIEN_GATES)
    assert {g.gate for g in sa.GEGENSTAENDE} <= set(GUELTIGE_GATES)
    assert sa.NUR_LINIE == ("A-B3",)


def test_weg_c_ist_entfallen_und_nur_im_schema_8_lesbar(tmp_path, monkeypatch):
    """Die Basislinie (Weg c) ersetzte die erste Abnahme der T-Box — die gibt
    es jetzt (ADR-025). Auch mit kuenstlich einelementiger Linie verlangt
    A-M4 eine Abnahme der T-Box; ein Schema-9-Snapshot fuehrt den Weg nicht,
    ein Schema-8-Snapshot bleibt mit ihm lesbar.

    Mutationsprobe: BASISLINIE in WEGE zuruecknehmen -> der Schema-9-Teil rot."""
    assert sa.BASISLINIE not in sa.WEGE and sa.BASISLINIE in sa.WEGE_LESBAR
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_OHNE_UEBERGANG)
    fall = _fall(tmp_path, mit_tboxstand=False)
    am4 = _am4(fall)
    assert am4.exit_code != 0
    assert "T-Box-Stand" in am4.errors[0]["message"], am4.errors

    from tests.test_betrieb_uebernahme import am4_snapshot
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import P9Snapshot, p9_snapshot_sha256

    for schema, gueltig in ((8, True), (9, False)):
        daten = am4_snapshot("fall-x", schema=schema)
        daten["standabnahmen"]["tboxstand"]["weg"] = sa.BASISLINIE
        daten.pop("snapshot_sha256")
        daten["freigabe"] = freigabe_fuer(
            {k: v for k, v in daten.items() if k != "freigabe"}, b"k" * 64)
        daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
        fehler = P9Snapshot.validate_payload(daten)
        assert (fehler == []) is gueltig, (schema, fehler)


def test_der_lebende_stand_je_gegenstand():
    kern = stand_belegen.lebender_stand("A-K2", REPO)
    assert set(kern) == {"version", "kern_sha256", "referenzwerte_sha256", "kernstand_sha256"}
    t = stand_belegen.lebender_stand("A-O1", REPO)
    assert t == {"version": tbox.TBOX_VERSION, "tbox_sha256": stand_belegen.tbox_modul_sha256(),
                 "vokabular_sha256": tbox.vokabular_sha256()}
    tw = stand_belegen.lebender_stand("A-T1", REPO)
    assert set(tw) == {"tarifplaene_sha256", "parametrierung_sha256", "tarifwerk_sha256"}


# --------------------------------------------------------------------------- #
# Kernstand: (b) "keine Aenderung" ueber einen Verweis
# --------------------------------------------------------------------------- #


def test_kern_keine_aenderung_ueber_den_verweis_auf_die_abnahme_der_linie(tmp_path):
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    assert _am4(neu).exit_code != 0
    snap = _in_der_linie(neu, "A-K2")
    verweis = _verweisen(neu, "A-K2")
    assert verweis.exit_code == 0, verweis.errors
    am4 = _am4(neu)
    assert am4.exit_code == 0, am4.errors
    daten = json.loads((neu / "abgeleitet/kern/verweis.json").read_text(encoding="utf-8"))
    assert set(daten) == sa.VERWEIS_FELDER and daten["snapshot"] == snap
    eintrag = am4.summary["standabnahmen"]["kernstand"]
    assert eintrag["weg"] == sa.KEINE_AENDERUNG
    assert eintrag["anzeige"] == (
        f"keine Aenderung seit Abnahme {snap['snapshot_sha256'][:16]} "
        f"(Linie linie, entscheide/A-K2-{snap['snapshot_sha256']}.json); "
        + ka.ANZEIGE_REGRESSION)
    assert not list((neu / "entscheide").glob("A-K2-*.json")), "kein neuer Entscheid"


def test_kern_verweis_auf_einen_anderen_stand_wird_verweigert(tmp_path, monkeypatch):
    """Durchgewunken heisst belegt unveraendert: Der abgenommene Stand wird
    per == gegen den lebenden gehalten.

    Mutationsprobe: die Gleichheitspruefung in verweis_fehler entfernen -> rot."""
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    _in_der_linie(neu, "A-K2")
    assert _verweisen(neu, "A-K2").exit_code == 0
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
    Die Ordnung, unter der der fruehere Snapshot gezeichnet wurde, gibt der
    Rolle seines Schluessels A-K2 nicht — hier: von mensch/architektur
    gezeichnet (Rollenfeld stimmig, Signatur gueltig). Seit die Linie Pflicht
    ist (ADR-025), gilt die Ordnung DER ZEICHNUNG; eine spaeter geaenderte
    Ordnung des Lesers entzoege nichts rueckwirkend.

    Mutationsprobe: den Rollenregel-Aufruf im Verweis-Zweig aussetzen -> rot."""
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import p9_snapshot_sha256

    neu = _fall(tmp_path / "b", mit_kernstand=False)
    snap = _in_der_linie(neu, "A-K2")
    rest = {k: v for k, v in snap.items() if k not in ("freigabe", "snapshot_sha256")}
    rest["rolle"] = "mensch/architektur"
    rest["zeichnung"] = {**rest["zeichnung"], "rolle": "mensch/architektur"}
    rest["freigabe"] = freigabe_fuer(
        rest, (neu.parent / "p9-architektur.key").read_bytes())
    rest["snapshot_sha256"] = p9_snapshot_sha256(rest)
    # In der Linie ausgetauscht (wer linie/entscheide/ beschreiben kann): echt
    # signiert, von einem Schluessel, dessen Rolle A-K2 nicht zeichnet.
    entscheide = neu.parent / "linie" / "entscheide"
    (entscheide / f"A-K2-{snap['snapshot_sha256']}.json").unlink()
    (entscheide / f"A-K2-{rest['snapshot_sha256']}.json").write_text(
        json.dumps(rest), encoding="utf-8")
    assert _verweisen(neu, "A-K2").exit_code == 0
    am4 = _am4(neu)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "unberechtigten Schluessel" in meldung and "A-K2" in meldung, meldung


def test_eine_kette_im_fall_geht_jedem_verweis_vor(tmp_path):
    """Eine Ablehnung im Fall laesst sich nicht durch einen Verweis umgehen."""
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    _in_der_linie(neu, "A-K2")
    abgelehnt = gate_entscheid.main([
        "--fall", str(neu), *linie_args(neu), "--gate", "A-K2", "--entscheid", "abgelehnt",
        "--rolle", "agent/rechenkern", "--entscheider", "agent", "--begruendung", "offen",
        "--repo-root", str(REPO)])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    assert _verweisen(neu, "A-K2").exit_code == 0
    am4 = _am4(neu)
    assert am4.exit_code != 0
    assert "geht jedem Verweis vor" in am4.errors[0]["message"], am4.errors


def test_der_verweis_produzent_nimmt_keine_ablehnung_und_kein_fremdes_gate(tmp_path):
    neu = _fall(tmp_path / "b", mit_kernstand=False)
    snap = _in_der_linie(neu, "A-K2")
    stand = stand_belegen.lebender_stand("A-O1", REPO)
    fremd = stand_belegen.verweis_fehler(stand_belegen.baue_verweis(snap),
                                         sa.gegenstand_fuer("A-O1"), stand)
    assert any("gehoert zu 'A-K2'" in f for f in fremd), fremd
    linie = neu.parent / "linie"
    abgelehnt = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-K2", "--entscheid", "abgelehnt",
        "--rolle", "mensch/rechenkern", "--entscheider", "r", "--begruendung", "zurueck",
        "--repo-root", str(REPO), *annahme_args(linie, fuer="A-K2")])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    abgelehnt = _verweisen(neu, "A-K2")
    assert abgelehnt.exit_code != 0 and "keine Annahme" in abgelehnt.errors[0]["message"]


# --------------------------------------------------------------------------- #
# T-Box-Stand: (a), (b) — mit der echten Linie (Uebergang 0.1.0 -> 0.2.0)
# --------------------------------------------------------------------------- #


def test_t_box_mit_uebergang_braucht_eine_abnahme(tmp_path, monkeypatch):
    """Ohne A-O1 und ohne Verweis verweigert A-M4.

    Mutationsprobe: den T-Box-Gegenstand aus AM4_GEGENSTAENDE nehmen -> rot."""
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    fall = _fall(tmp_path, mit_tboxstand=False)
    am4 = _am4(fall)
    assert am4.exit_code != 0
    meldung = am4.errors[0]["message"]
    assert "T-Box-Stand" in meldung and "stand_belegen tbox" in meldung, meldung


def test_t_box_abnahme_im_fall(tmp_path, monkeypatch):
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    fall = _fall(tmp_path, mit_tboxstand=False)
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
    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    fall = _fall(tmp_path, mit_tboxstand=False)
    falsch = _zeichne_tboxstand(fall, *annahme_args(fall))
    assert falsch.exit_code != 0 and "A-O1" in falsch.errors[0]["message"], falsch.errors


def test_a_m4_verweigert_ein_a_o1_dessen_rollenfeld_nicht_die_rolle_des_schluessels_ist(
        tmp_path, monkeypatch):
    """Rollenfeld gefaelscht, mit dem echten Schluessel neu signiert.

    Mutationsprobe: die Rollenregel fuer den Snapshot im Fall aussetzen -> rot."""
    from tests.test_abnahme_rolle_klasse import _behauptet, _neu_signiert

    monkeypatch.setattr(tbox, "TBOX_VERSIONEN", LINIE_MIT_UEBERGANG)
    fall = _fall(tmp_path, mit_tboxstand=False)
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
    neu = _fall(tmp_path / "b", mit_tboxstand=False)
    assert _am4(neu).exit_code != 0
    snap = _in_der_linie(neu, "A-O1")
    assert _verweisen(neu, "A-O1").exit_code == 0
    am4 = _am4(neu)
    assert am4.exit_code == 0, am4.errors
    eintrag = am4.summary["standabnahmen"]["tboxstand"]
    assert eintrag["anzeige"] == sa.anzeige_keine_aenderung(
        snap["snapshot_sha256"], sa.herkunft(snap))
    assert eintrag["anzeige"].startswith("keine Aenderung seit Abnahme ")
