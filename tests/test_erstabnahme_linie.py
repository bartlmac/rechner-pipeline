"""Erstabnahme des Zielsystems — vier Gegenstaende, vier Rollen, ein Ort ausserhalb des Falls.

Entscheid des Maintainers 2026-10-01 (ADR-025): "Entweder gibt es eine
Initialzeichnung an allen relevanten Zustaenden oder gar nicht" — "ja, alle".
Jede Rolle zeichnet ihren Gegenstand einmal im LINIENBEREICH; ein Fall
zeichnet danach nur, was sich durch ihn aendert, und verweist sonst auf die
geltende Abnahme (Weg b). Dazu die Versionslinie der Zeichnungsordnung:
Gezeichnet wird unter ihrer Spitze, gelesen unter der Ordnung, unter der
gezeichnet wurde.

Proben und ihre Mutationen (Bauprotokoll in der Rueckgabe): Verweis auf die
Erstabnahme ohne Fall loest auf und wird nach einer Aenderung verweigert
(Stand nicht per == -> rot); Snapshot unter nicht eingetragener Ordnung als
Verweis -> verweigert; Rolle hatte das Gate DAMALS nicht -> verweigert,
damals ja und heute nicht mehr -> angenommen; Erweiterung der Ordnung
entwertet nichts; Glied umgeschrieben/entfernt/ausgetauscht -> verweigert;
Anhaengen mit falschem Vorgaenger, ohne Maintainer-Zeichnung, mit
Allzweck-Rolle oder mit fachlichem Gate der Wurzelrolle -> verweigert;
Tageslauf ohne Abnahme des Anfangsbestands -> Exit 2 mit Ausweg.

Knoten: system/entscheid
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.gates import gate_entscheid, kernstand_belegen, stand_belegen
from rechner_pipeline.gates import tarifwerk_belegen
from rechner_pipeline.models import anfangsbestand as ab
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models import tarifwerkabnahme as tw
from rechner_pipeline.models.zeichnung import GUELTIGE_GATES, zeichnende_rolle_fehler
from rechner_pipeline.ontologie import tbox
from tests.zeichnung_fixture import (
    ARCHITEKTUR,
    VORSTAND_SCHLUESSEL_DATEI,
    RECHENKERN,
    VA,
    annahme_args,
    linie_anlegen,
    ordnung_schreiben,
)

REPO = Path(__file__).resolve().parents[1]
AGENTEN = REPO / ".claude" / "agents"


# --------------------------------------------------------------------------- #
# Helfer
# --------------------------------------------------------------------------- #


def _zeichne_in_linie(linie: Path, gate: str, **kw):
    """Den Gegenstand ``gate`` im Linienbereich vorlegen und zeichnen."""
    if gate == "A-K2":
        assert kernstand_belegen.main([
            "--linie", str(linie), "--repo-root", str(REPO), "--von", "HEAD",
            "--begruendung", "Erstabnahme des Kernstands"]).exit_code == 0
        fuer = "A-K2"
    elif gate == "A-O1":
        vermerk = linie / "abgeleitet" / "tbox" / "vermerk.md"
        vermerk.parent.mkdir(parents=True, exist_ok=True)
        vermerk.write_text("Erstabnahme der T-Box.\n", encoding="utf-8")
        beleg = stand_belegen.main([
            "tbox", "--linie", str(linie), "--repo-root", str(REPO),
            "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "Erstabnahme"])
        assert beleg.exit_code == 0, beleg.errors
        (linie / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
            "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
            "verfasser_rolle": "mensch/aktuariat",
            "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                        "begruendung": "Erstabnahme (Suite)"}]}), encoding="utf-8")
        fuer = "A-O1"
    else:
        assert gate == "A-T1"
        assert tarifwerk_belegen.main([
            "--linie", str(linie), "--repo-root", str(REPO), "--von", "HEAD",
            "--begruendung", "Erstabnahme des Tarifwerks"]).exit_code == 0
        fuer = None
    return gate_entscheid.main([
        "--linie", str(linie), "--gate", gate, "--entscheid", "angenommen",
        "--entscheider", "verantwortung", "--begruendung", f"Erstabnahme {gate}",
        "--repo-root", str(REPO), *annahme_args(linie, fuer=fuer, **kw)])


def _spitze(bereich: Path, gate: str) -> dict:
    snap, fehler = stand_belegen.geltende_spitze(bereich, gate)
    assert snap is not None, fehler
    return snap


def _fall_mit_linie(tmp_path: Path):
    """Linie (mit Ordnungslinie) und Erstabnahme der drei Code-Gegenstaende,
    dann ein Tariffall, der unter derselben Linie zeichnet."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012

    linie = linie_anlegen(tmp_path)
    for gate in ("A-K2", "A-O1", "A-T1"):
        ergebnis = _zeichne_in_linie(linie, gate)
        assert ergebnis.exit_code == 0, (gate, ergebnis.errors)
    fall = _bereite_fall(tmp_path, ("klv/tg2012",), mit_kernstand=False,
                         mit_tboxstand=False, mit_tarifwerk=False)
    assert _o3_tg2012(fall).exit_code == 0
    return linie, fall


def _verweise(fall: Path, linie: Path, gates=("A-K2", "A-O1", "A-T1")):
    for gate in gates:
        ergebnis = stand_belegen.main([
            "verweisen", "--fall", str(fall), "--gate", gate, "--linie", str(linie),
            "--repo-root", str(REPO)])
        assert ergebnis.exit_code == 0, (gate, ergebnis.errors)


def _am4(fall: Path):
    from tests.test_pk1_am4_beweisvertrag import _p9_annahme

    return _p9_annahme(fall, "A-M4", "Migration abgenommen")


def _haenge_an(linie: Path, ordnung: dict, datei: Path, **kw):
    datei.write_text(json.dumps(ordnung, sort_keys=True), encoding="utf-8")
    glieder, _ = ol.lade_linie(linie)
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(datei),
            "--vorgaenger", kw.pop("vorgaenger", glieder[-1]["glied_sha256"] if glieder
                                   else "keiner"),
            "--eingetragen-am", "2026-10-01T09:00:00+00:00"]
    schluessel = kw.pop("schluessel", linie.parent / VORSTAND_SCHLUESSEL_DATEI)
    if schluessel is not None:
        argv += ["--vorstand-schluessel", str(schluessel)]
    return stand_belegen.main(argv)


def _ordnung(verzeichnis: Path) -> dict:
    return json.loads((verzeichnis / "zeichnungsordnung.json").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# Die Tabelle: Gegenstand -> Werkzeug, Sicht, Gate, Rolle, vorlegender Agent
# --------------------------------------------------------------------------- #

TABELLE = [
    ("kernstand", "rechner_pipeline.gates.kernstand_belegen", "abgeleitet/kern/aenderung.md",
     "A-K2", "mensch/rechenkern", "agent/rechenkern", "A-M4"),
    ("tboxstand", "rechner_pipeline.gates.stand_belegen tbox", "abgeleitet/tbox/aenderung.md",
     "A-O1", "mensch/architektur", "agent/architektur", "A-M4"),
    ("tarifwerkstand", "rechner_pipeline.gates.tarifwerk_belegen",
     "abgeleitet/tarifwerk/aenderung.md", "A-T1", "mensch/aktuariat", "agent/aktuariat", "A-M4"),
    ("anfangsbestand", "rechner_pipeline.betrieb.anfangsbestand belegen",
     "abgeleitet/anfangsbestand/beleg.md", "A-B3", "mensch/betrieb", "agent/betrieb", "betrieb"),
]


def test_die_tabelle_der_vier_gegenstaende_ist_vollstaendig():
    """== gegen den Vertrag; jedes Werkzeug importierbar, jedes Gate
    zeichenbar, jede vorlegende Agentenrolle definiert (.claude/agents)."""
    assert [(g.rolle, g.werkzeug, g.sicht_relativ, g.gate, g.verantwortung, g.agent,
             g.verlangt_von) for g in sa.GEGENSTAENDE] == TABELLE
    for _, werkzeug, _, gate, _, agent, _ in TABELLE:
        importlib.import_module(werkzeug.split()[0])
        assert gate in GUELTIGE_GATES
        assert (AGENTEN / f"{agent.split('/')[1]}.md").is_file(), agent


# --------------------------------------------------------------------------- #
# Ordnungslinie
# --------------------------------------------------------------------------- #


def test_die_wurzel_ist_unsigniert_und_benennt_die_vorstand_rolle(tmp_path):
    linie = linie_anlegen(tmp_path)
    (glied,), fehler = ol.lade_linie(linie)
    assert fehler == []
    assert glied["zeichnung"] is None and glied["eintrag"]["art"] == "wurzel"
    assert "unsigniert" in glied["eintrag"]["vermerk"]
    ordnung = ol.ordnung_aus(glied)
    assert ordnung["rollen"][ol.WURZELROLLE]["gates"] == list(ol.WURZEL_GATES)
    assert {a["art"] for a in glied["aenderungen"]} == {"neue_rolle"}
    assert (linie / "abgeleitet" / "ordnung" / "linie.md").is_file()


def test_ohne_vorstand_rolle_oder_mit_allzweck_rolle_kein_glied(tmp_path):
    linie = linie_anlegen(tmp_path)
    ordnung = _ordnung(tmp_path)
    stern = json.loads(json.dumps(ordnung))
    stern["rollen"][VA]["gates"] = ["*"]
    ergebnis = _haenge_an(linie, stern, tmp_path / "o2.json")
    assert ergebnis.exit_code != 0 and "Allzweck" in ergebnis.errors[0]["message"]
    ohne = json.loads(json.dumps(ordnung))
    del ohne["rollen"][ol.WURZELROLLE]
    ergebnis = _haenge_an(linie, ohne, tmp_path / "o3.json")
    assert ergebnis.exit_code != 0 and ol.WURZELROLLE in ergebnis.errors[0]["message"]
    fachlich = json.loads(json.dumps(ordnung))
    fachlich["rollen"][ol.WURZELROLLE]["gates"] = [ol.ORDNUNGS_GATE, "A-M4"]
    ergebnis = _haenge_an(linie, fachlich, tmp_path / "o4.json")
    assert ergebnis.exit_code != 0, "die Wurzelrolle nimmt nichts fachlich ab"


def test_eine_rolle_des_abgebenden_hauses_verleiht_der_vorstand_nicht(tmp_path):
    """Die Linie der PLV fuehrt nur Rollen der PLV: Die Vollmacht des
    Aktuars des abgebenden Hauses kaeme von seinem eigenen Haus und wird im
    Fallauftrag anerkannt, nicht verliehen (ADR-025, Abschnitt 8 d)."""
    linie = linie_anlegen(tmp_path)
    fremd = _ordnung(tmp_path)
    fremd["rollen"]["mensch/quell-aktuar"] = {
        "schluessel_sha256": "ef" * 32, "schluesselklasse": "mensch", "gates": ["A-Q1"]}
    ergebnis = _haenge_an(linie, fremd, tmp_path / "o2.json")
    assert ergebnis.exit_code != 0
    assert "abgebenden Hauses" in ergebnis.errors[0]["message"], ergebnis.errors
    assert ol.ROLLEN_DES_ABGEBENDEN_HAUSES == ("mensch/quell-aktuar",)
    assert ol.WURZELROLLE == "mensch/vorstand" and ol.WURZELROLLE_ANZEIGE == "Vorstand"


def test_ein_spaeteres_glied_zeichnet_der_vorstand_mit_dem_schluessel_der_spitze(tmp_path):
    linie = linie_anlegen(tmp_path)
    ordnung = _ordnung(tmp_path)
    neu = json.loads(json.dumps(ordnung))
    neu["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    ohne = _haenge_an(linie, neu, tmp_path / "o2.json", schluessel=None)
    assert ohne.exit_code != 0 and "nicht anhaengbar" in ohne.errors[0]["message"]
    fremd = tmp_path / "fremd.key"
    fremd.write_bytes(b"f" * 64)
    fremd.chmod(0o600)
    assert _haenge_an(linie, neu, tmp_path / "o2.json", schluessel=fremd).exit_code != 0
    falscher = _haenge_an(linie, neu, tmp_path / "o2.json", vorgaenger="ab" * 32)
    assert falscher.exit_code != 0 and "nicht die Spitze" in falscher.errors[0]["message"]
    gut = _haenge_an(linie, neu, tmp_path / "o2.json")
    assert gut.exit_code == 0, gut.errors
    glieder, fehler = ol.lade_linie(linie, {hashlib.sha256(
        (tmp_path / VORSTAND_SCHLUESSEL_DATEI).read_bytes()).hexdigest():
        (tmp_path / VORSTAND_SCHLUESSEL_DATEI).read_bytes()})
    assert fehler == [] and len(glieder) == 2
    assert glieder[1]["zeichnung"]["rolle"] == ol.WURZELROLLE


def test_die_aenderungsliste_unterscheidet_verbreiterung_und_neue_rolle(tmp_path):
    """Eine stille Verbreiterung einer bestehenden Rolle ist als solche
    ausgewiesen — gerechnet, nicht behauptet; eine behauptete Liste bricht."""
    linie = linie_anlegen(tmp_path)
    ordnung = _ordnung(tmp_path)
    neu = json.loads(json.dumps(ordnung))
    neu["rollen"][ARCHITEKTUR]["gates"] = ["A-O1", "A-K2"]
    neu["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    assert _haenge_an(linie, neu, tmp_path / "o2.json").exit_code == 0
    glieder, _ = ol.lade_linie(linie)
    arten = {(a["art"], a["rolle"]) for a in glieder[1]["aenderungen"]}
    assert arten == {("gates_erweitert", ARCHITEKTUR), ("neue_rolle", "mensch/revision")}
    sicht = (linie / "abgeleitet" / "ordnung" / "linie.md").read_text(encoding="utf-8")
    assert f"bestehende Rolle {ARCHITEKTUR} um ['A-K2'] erweitert" in sicht
    # Behauptet statt gerechnet: die Liste leeren und das Glied neu hashen.
    pfad = next((linie / ol.VERZEICHNIS).glob("0002-*.json"))
    glied = json.loads(pfad.read_text(encoding="utf-8"))
    glied["aenderungen"] = []
    glied["glied_sha256"] = ol.glied_sha256(glied)
    pfad.unlink()
    (pfad.parent / ol.dateiname(glied)).write_text(json.dumps(glied), encoding="utf-8")
    _, fehler = ol.lade_linie(linie)
    assert any("Aenderungsliste" in f for f in fehler), fehler


def test_ein_umgeschriebenes_oder_entferntes_glied_bricht_die_linie(tmp_path):
    linie = linie_anlegen(tmp_path)
    neu = _ordnung(tmp_path)
    neu["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    assert _haenge_an(linie, neu, tmp_path / "o2.json").exit_code == 0
    erstes = next((linie / ol.VERZEICHNIS).glob("0001-*.json"))
    roh = erstes.read_bytes()
    daten = json.loads(roh)
    daten["eingetragen_am"] = "2020-01-01T00:00:00+00:00"
    erstes.write_text(json.dumps(daten), encoding="utf-8")
    assert ol.lade_linie(linie)[1]
    erstes.write_bytes(roh)
    assert ol.lade_linie(linie)[1] == []
    erstes.unlink()
    assert ol.lade_linie(linie)[1]


# --------------------------------------------------------------------------- #
# Erstabnahme und Weg (b)
# --------------------------------------------------------------------------- #


def test_verweis_auf_die_erstabnahme_ohne_fall_loest_auf_und_verweigert_nach_aenderung(
        tmp_path, monkeypatch):
    """Signatur, Rolle, Klasse und Stand per == — gegen eine Abnahme, die in
    keinem Fall liegt. Danach eine Aenderung des Tarifwerks: derselbe Verweis
    wird verweigert.

    Mutationsprobe: in ``stand_belegen.verweis_fehler`` den Vergleich
    ``snap.get("stand") != stand`` aussetzen -> der zweite Teil wird gruen -> rot."""
    linie, fall = _fall_mit_linie(tmp_path)
    assert _am4(fall).exit_code != 0
    _verweise(fall, linie)
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors
    for gate, rolle in (("A-K2", "kernstand"), ("A-O1", "tboxstand"), ("A-T1", "tarifwerkstand")):
        eintrag = am4.summary["standabnahmen"][rolle]
        snap = _spitze(linie, gate)
        assert eintrag["weg"] == sa.KEINE_AENDERUNG
        assert eintrag["anzeige"].startswith(
            f"keine Aenderung seit Abnahme {snap['snapshot_sha256'][:16]} (Linie {linie.name}, ")
        assert snap["fall_scope"] == sa.LINIE_SCOPE and snap["zeichnung"]["ordnungsglied_sha256"]
    assert am4.summary["ordnungslinie"].startswith("Glied 1 ")
    echt = tarifwerk_belegen.lebender_stand
    monkeypatch.setattr(tarifwerk_belegen, "lebender_stand",
                        lambda repo: {**echt(repo), "tarifwerk_sha256": "00" * 32})
    abgelehnt = _am4(fall)
    assert abgelehnt.exit_code != 0
    meldung = abgelehnt.errors[0]["message"]
    assert "tarifwerk/verweis.json" in meldung and "es gab eine Aenderung" in meldung, meldung
    erneut = stand_belegen.main(["verweisen", "--fall", str(fall), "--gate", "A-T1",
                                 "--linie", str(linie), "--repo-root", str(REPO)])
    assert erneut.exit_code != 0 and "es gab eine Aenderung" in erneut.errors[0]["message"]


def test_gezeichnet_wird_nur_unter_der_spitze_der_linie(tmp_path):
    linie = linie_anlegen(tmp_path)
    ordnung = _ordnung(tmp_path)
    ordnung["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    andere = tmp_path / "andere" / "zeichnungsordnung.json"
    andere.parent.mkdir()
    ordnung_schreiben(andere, ordnung["rollen"])
    args = annahme_args(linie, fuer="A-K2")
    args[args.index("--zeichnungsordnung") + 1] = str(andere)
    assert kernstand_belegen.main(["--linie", str(linie), "--repo-root", str(REPO),
                                   "--von", "HEAD", "--begruendung", "x"]).exit_code == 0
    ergebnis = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "r", "--begruendung", "b", "--repo-root", str(REPO), *args])
    assert ergebnis.exit_code != 0 and "nicht die Spitze" in ergebnis.errors[0]["message"]


def test_im_linienbereich_nur_die_vier_gegenstaende_und_a_b3_nur_dort(tmp_path):
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall

    linie = linie_anlegen(tmp_path)
    ergebnis = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-M4", "--entscheid", "angenommen",
        "--entscheider", "r", "--begruendung", "b", "--repo-root", str(REPO),
        *annahme_args(linie)])
    assert ergebnis.exit_code == 2 and "nicht zeichenbar" in ergebnis.errors[0]["message"]
    fall = _bereite_fall(tmp_path, ("klv/tg2012",), mit_kernstand=False,
                         mit_tboxstand=False, mit_tarifwerk=False)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-B3", "--entscheid", "angenommen",
        "--entscheider", "r", "--begruendung", "b", "--repo-root", str(REPO),
        *annahme_args(fall)])
    assert ergebnis.exit_code == 2 and "Linienbereich" in ergebnis.errors[0]["message"]


def test_der_linienbereich_ist_nur_anfuegbar_wie_entscheide(tmp_path):
    """Derselbe Schutz wie ``faelle/<fall>/entscheide/``: derselbe Entscheid
    ist idempotent, ein Snapshot wird nie ueberschrieben, die Kette pinnt
    ihre Vorgaenger; die Glieder der Ordnung werden exklusiv geschrieben."""
    linie = linie_anlegen(tmp_path)
    erst = _zeichne_in_linie(linie, "A-T1")
    assert erst.exit_code == 0, erst.errors
    nochmal = _zeichne_in_linie(linie, "A-T1")
    assert nochmal.summary.get("bereits_vorhanden") is True
    abgelehnt = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-T1", "--entscheid", "abgelehnt",
        "--rolle", VA, "--entscheider", "r", "--begruendung", "zurueck",
        "--repo-root", str(REPO), *annahme_args(linie)])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    spitze = _spitze(linie, "A-T1")
    assert spitze["entscheid"] == "abgelehnt"
    assert spitze["vorgaenger"] == [erst.summary["snapshot_sha256"]]
    glied = next((linie / ol.VERZEICHNIS).glob("*.json"))
    with pytest.raises(FileExistsError):
        from rechner_pipeline.gates._common import schreibe_exklusiv

        schreibe_exklusiv(glied, b"{}")


# --------------------------------------------------------------------------- #
# Lesen unter der damaligen Ordnung
# --------------------------------------------------------------------------- #


def test_damals_berechtigt_heute_nicht_mehr_wird_angenommen(tmp_path):
    """Die Ordnung entzieht der Rolle spaeter A-T1 — die Erstabnahme, unter
    der sie es hatte, traegt weiter (kein rueckwirkender Entzug, ADR-022 —
    jetzt pruefbar)."""
    linie, fall = _fall_mit_linie(tmp_path)
    _verweise(fall, linie)
    neu = _ordnung(tmp_path)
    neu["rollen"][VA]["gates"] = [g for g in neu["rollen"][VA]["gates"] if g != "A-T1"]
    assert _haenge_an(linie, neu, tmp_path / "zeichnungsordnung.neu.json").exit_code == 0
    (tmp_path / "zeichnungsordnung.json").write_text(
        (tmp_path / "zeichnungsordnung.neu.json").read_text(encoding="utf-8"), encoding="utf-8")
    am4 = _am4(fall)
    # A-Q1 und A-M1 wurden unter Glied 1 gezeichnet und gelten ebenso weiter.
    assert am4.exit_code == 0, am4.errors
    assert am4.summary["ordnungslinie"].startswith("Glied 2 ")


def test_eine_erweiterung_der_ordnung_entwertet_keine_abnahme(tmp_path):
    """Der Fall, den ein Hash-Gleichheitsvergleich gebrochen haette."""
    linie, fall = _fall_mit_linie(tmp_path)
    _verweise(fall, linie)
    neu = _ordnung(tmp_path)
    neu["rollen"]["mensch/revision"] = {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "simulation", "gates": []}
    assert _haenge_an(linie, neu, tmp_path / "zeichnungsordnung.neu.json").exit_code == 0
    (tmp_path / "zeichnungsordnung.json").write_text(
        (tmp_path / "zeichnungsordnung.neu.json").read_text(encoding="utf-8"), encoding="utf-8")
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors


def test_damals_nicht_berechtigt_wird_verweigert_auch_wenn_heute_berechtigt():
    """Die Regel liest die Ordnung des GEPINNTEN Glieds, nicht die heutige."""
    damals = {"schema_version": 2, "rollen": {
        VA: {"schluessel_sha256": "aa" * 32, "schluesselklasse": "mensch", "gates": ["A-M4"]},
        ol.WURZELROLLE: {"schluessel_sha256": "bb" * 32, "schluesselklasse": "mensch",
                              "gates": [ol.ORDNUNGS_GATE]}}}
    heute = json.loads(json.dumps(damals))
    heute["rollen"][VA]["gates"] = ["A-M4", "A-T1"]
    glied = ol.baue_glied(json.dumps(damals).encode(), nummer=1, vorgaenger=None,
                          eingetragen_am="2026-10-01")
    snapshot = {"gate": "A-T1", "rolle": VA, "freigabe": {"schluessel_sha256": "aa" * 32},
                "zeichnung": {"rolle": VA, "schluesselklasse": "mensch",
                              "ordnung_sha256": glied["ordnung_sha256"],
                              "ordnungsglied_sha256": glied["glied_sha256"]}}
    rolle, fehler = zeichnende_rolle_fehler(snapshot, "A-T1", heute, linie=[glied])
    assert rolle is None and "nicht fuer A-T1" in fehler
    # Ohne Linie begruendet die Abnahme nichts (ADR-025, Nachtrag 2026-10-01):
    # Der Weg gegen die heutige Ordnung des Lesers ist entfallen.
    for ohne in (None, []):
        rolle, fehler = zeichnende_rolle_fehler(snapshot, "A-T1", heute, linie=ohne)
        assert rolle is None and "ohne Ordnungslinie" in fehler


def test_ein_snapshot_ohne_glied_ist_nicht_lokalisierbar(tmp_path):
    """Abnahmen vor der Linie (abgeschlossene Faelle) gelten fuer IHREN Fall,
    als Grundlage eines neuen sind sie nicht verwendbar."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012

    (tmp_path / "alt").mkdir()
    alt = _bereite_fall(tmp_path / "alt", ("klv/tg2012",))   # ohne Linie gezeichnet
    (tmp_path / "neu").mkdir()
    linie, fall = _fall_mit_linie(tmp_path / "neu")
    _verweise(fall, linie, gates=("A-K2", "A-O1"))
    ergebnis = stand_belegen.main([
        "verweisen", "--fall", str(fall), "--gate", "A-T1", "--snapshot",
        str(next((alt / "entscheide").glob("A-T1-*.json"))), "--repo-root", str(REPO)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    am4 = _am4(fall)
    assert am4.exit_code != 0
    # Der fruehere Fall zeichnete unter SEINER Linie (die Linie ist Pflicht,
    # ADR-025, Nachtrag 2026-10-01): In dieser Linie ist sein Glied nicht
    # lokalisierbar — als Grundlage nicht verwendbar.
    meldung = am4.errors[0]["message"]
    assert ("nicht lokalisierbar" in meldung
            or "steht nicht in der Ordnungslinie" in meldung), am4.errors
    assert _o3_tg2012 is not None


def test_ein_ausgetauschtes_erstes_glied_verweigert_jede_lesestelle(tmp_path):
    """Anderer Inhalt, gleiche Form: Der Glied-Hash aendert sich, jede
    Abnahme, die das alte Glied pinnt, ist nicht mehr lokalisierbar.

    Mutationsprobe: in ``ordnungslinie.damalige_ordnung`` nur ueber den
    Ordnungs-Hash statt das Glied lokalisieren -> bleibt gruen -> rot."""
    linie, fall = _fall_mit_linie(tmp_path)
    _verweise(fall, linie)
    erstes = next((linie / ol.VERZEICHNIS).glob("0001-*.json"))
    alt = json.loads(erstes.read_text(encoding="utf-8"))
    ersatz = ol.baue_glied(alt["ordnung_text"].encode("utf-8"), nummer=1, vorgaenger=None,
                           eingetragen_am="2026-10-01T23:59:00+00:00")
    erstes.unlink()
    (erstes.parent / ol.dateiname(ersatz)).write_text(json.dumps(ersatz), encoding="utf-8")
    am4 = _am4(fall)
    assert am4.exit_code != 0
    assert "steht nicht in der Ordnungslinie" in am4.errors[0]["message"], am4.errors


def test_die_vorstand_rolle_zeichnet_keine_fachliche_abnahme(tmp_path):
    linie = linie_anlegen(tmp_path)
    assert kernstand_belegen.main(["--linie", str(linie), "--repo-root", str(REPO),
                                   "--von", "HEAD", "--begruendung", "x"]).exit_code == 0
    args = annahme_args(linie, fuer="A-K2")
    i = len(args) - 1 - args[::-1].index("--freigabe-schluessel")
    args[i + 1] = str(tmp_path / VORSTAND_SCHLUESSEL_DATEI)
    ergebnis = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "r", "--begruendung", "b", "--repo-root", str(REPO), *args])
    assert ergebnis.exit_code != 0
    assert "nicht zeichnungsberechtigt" in ergebnis.errors[0]["message"], ergebnis.errors


# --------------------------------------------------------------------------- #
# Sichten
# --------------------------------------------------------------------------- #


def test_jede_vorlage_hat_ihre_lesbare_sicht(tmp_path):
    linie = linie_anlegen(tmp_path)
    for gate in ("A-K2", "A-O1", "A-T1"):
        assert _zeichne_in_linie(linie, gate).exit_code == 0
    for g in sa.AM4_GEGENSTAENDE:
        sicht = (linie / g.sicht_relativ).read_text(encoding="utf-8")
        assert sicht.startswith("# "), g.gate
    tbox_sicht = (linie / "abgeleitet/tbox/aenderung.md").read_text(encoding="utf-8")
    assert "Erstabnahme: das ganze Vokabular" in tbox_sicht
    tw_sicht = (linie / tw.SICHT_RELATIV).read_text(encoding="utf-8")
    assert "Tarifgenerationen der Configs" in tw_sicht and "KLV-1994" in tw_sicht


def test_die_t_box_sicht_zeigt_den_diff_gegen_das_zuletzt_abgenommene_vokabular(
        tmp_path, monkeypatch):
    linie = linie_anlegen(tmp_path)
    assert _zeichne_in_linie(linie, "A-O1").exit_code == 0
    echt = tbox.vokabular()
    geaendert = json.loads(json.dumps(echt))
    geaendert["quelle_arten"] = list(geaendert["quelle_arten"]) + ["neue-art"]
    monkeypatch.setattr(tbox, "vokabular", lambda: geaendert)
    beleg = stand_belegen.tbox_aenderungsbeleg(linie, REPO, "abgeleitet/tbox/vermerk.md", "x")
    assert beleg["vorher"] is not None
    sicht = stand_belegen.rendere_tbox_sicht(beleg)
    assert "Aenderungen gegenueber dem zuletzt abgenommenen Vokabular" in sicht
    assert "`quelle_arten` (geaendert)" in sicht


# --------------------------------------------------------------------------- #
# Tarifwerk
# --------------------------------------------------------------------------- #


def test_der_tarifwerk_beleg_zeigt_je_generation_jedes_geaenderte_feld():
    alt = {"tarifplaene": {"docs/tarifplaene/klv.md": "a"}, "generationen": {
        "configs/x.toml": {"KLV-1": {"zins": 0.04, "tafel": "T"}}}}
    neu = {"tarifplaene": {"docs/tarifplaene/klv.md": "b"}, "generationen": {
        "configs/x.toml": {"KLV-1": {"zins": 0.03, "tafel": "T"}, "KLV-2": {"zins": 0.01}}}}
    diff = tw.unterschiede(alt, neu)
    assert diff["tarifplaene"] == [{"pfad": "docs/tarifplaene/klv.md", "zustand": "geaendert"}]
    assert diff["generationen"] == [
        {"config": "configs/x.toml", "generation": "KLV-1", "zustand": "geaendert",
         "felder": [{"feld": "zins", "vorher": 0.04, "nachher": 0.03}]},
        {"config": "configs/x.toml", "generation": "KLV-2", "zustand": "neu", "felder": []}]
    assert tw.stand_aus(alt) != tw.stand_aus(neu)


def test_die_grenze_des_tarifwerks_erfahrung_und_fremde_generationen_gehoeren_nicht_dazu():
    text = (REPO / "configs" / "bestand_gesamt.toml").read_text(encoding="utf-8")
    gens = tw.generationen_aus(text, "configs/bestand_gesamt.toml")
    assert "TG2015" not in gens and "KLV-1994" in gens
    assert not set(tw.NICHT_TARIFWERK) & set(gens["KLV-1994"])
    assert {"zins", "tafel", "red_verfahren"} <= set(gens["KLV-1994"]) or \
        {"zins", "tafel"} <= set(gens["KLV-1994"])
    geaendert = text.replace("neuzugang_pro_jahr = 100", "neuzugang_pro_jahr = 999", 1)
    assert tw.generationen_aus(geaendert, "x") == gens   # Erfahrung: kein Tarifwerk
    zins = text.replace("zins = 0.04", "zins = 0.041", 1)
    assert tw.generationen_aus(zins, "x") != gens


def test_die_tarifplaene_gehoeren_nicht_mehr_zum_kernstand():
    from rechner_pipeline.models import kernabnahme as ka

    assert "docs/tarifplaene" not in ka.kernstand_pfade()
    assert tw.TARIFPLAENE == "docs/tarifplaene"


# --------------------------------------------------------------------------- #
# Anfangsbestand
# --------------------------------------------------------------------------- #


@pytest.fixture()
def aufgebaut(tmp_path, monkeypatch):
    """Eine Ablage nach dem Aufbaulauf — ohne Naht: Der naechste Lauf
    verlangt die Abnahme des Anfangsbestands."""
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.test_betrieb_tageslauf import _ablage

    monkeypatch.setattr(anf, "_STANDARD_ANFANGSBESTAND", None)
    ablage = _ablage(tmp_path / "daten")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 31))
    assert code == EXIT_OK and zeile["uebernommen"] is True
    return ablage


def _zeichner():
    from rechner_pipeline.betrieb import tageslauf as tl

    return tl.betriebszeichner(tl.Ablage(Path("/nirgends")))


def test_ohne_abnahme_des_anfangsbestands_laeuft_nach_dem_aufbaulauf_kein_tag(aufgebaut):
    """Benannter Zustand mit Ausweg, Exit 2, rote Protokollzeile.

    Mutationsprobe: ``anfangsbestand_fehler`` immer None -> gruen -> rot."""
    from rechner_pipeline.betrieb.tageslauf import EXIT_USAGE, tageslauf

    code, zeile = tageslauf(aufgebaut, dt.date(2026, 2, 3))
    assert code == EXIT_USAGE and zeile["uebernommen"] is False
    assert "kein abgenommener Anfangsbestand" in zeile["fehler"]
    assert "anfangsbestand belegen" in zeile["fehler"]


def test_belegen_zeichnen_binden_dann_laeuft_der_tag(aufgebaut, tmp_path):
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.anfangsbestand_testhelfer import linie_neben, zeichne_ab3
    from tests.freigabe_testschluessel import TESTRING

    linie = linie_neben(aufgebaut.wurzel)
    beleg = anf.belegen(aufgebaut.wurzel, linie, _zeichner())
    assert ab.beleg_fehler(beleg) == [] and beleg["pb1"]["urteil"] == "gruen"
    assert (linie / ab.SICHT_RELATIV).read_text(encoding="utf-8").startswith("# Abnahme")
    sha = zeichne_ab3(linie, beleg)
    bindung = anf.binden(aufgebaut.wurzel, linie, _zeichner(), schluesselring=TESTRING,
                         snapshot_sha256=sha, ordnungslinie=ol.lade_linie(linie)[0])
    assert bindung["stand"] == ab.stand_aus_beleg(beleg)
    code, zeile = tageslauf(aufgebaut, dt.date(2026, 2, 3))
    assert code == EXIT_OK, zeile.get("fehler")


def test_binden_verweigert_fremden_stand_und_unberechtigte_rolle(aufgebaut):
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from tests.anfangsbestand_testhelfer import ab3_snapshot, linie_neben
    from tests.freigabe_testschluessel import TESTKEY, TESTRING

    linie = linie_neben(aufgebaut.wurzel)
    beleg = anf.belegen(aufgebaut.wurzel, linie, _zeichner())
    roh_sha = hashlib.sha256((linie / ab.BELEG_RELATIV).read_bytes()).hexdigest()
    (linie / "entscheide").mkdir(exist_ok=True)
    falsch = ab3_snapshot(linie, beleg_sha256=roh_sha,
                          stand={**ab.stand_aus_beleg(beleg), "tabellen_sha256": "00" * 32},
                          vorgaenger=[])
    (linie / "entscheide" / f"A-B3-{falsch['snapshot_sha256']}.json").write_text(
        json.dumps(falsch), encoding="utf-8")
    with pytest.raises(anf.AnfangsbestandFehler, match="nicht der, den die Ablage"):
        anf.binden(aufgebaut.wurzel, linie, _zeichner(), schluesselring=TESTRING,
                   snapshot_sha256=falsch["snapshot_sha256"],
                   ordnungslinie=ol.lade_linie(linie)[0])
    fremd = ab3_snapshot(linie, beleg_sha256=roh_sha, stand=ab.stand_aus_beleg(beleg),
                         vorgaenger=[falsch["snapshot_sha256"]], schluessel=TESTKEY,
                         rolle=VA)
    (linie / "entscheide" / f"A-B3-{fremd['snapshot_sha256']}.json").write_text(
        json.dumps(fremd), encoding="utf-8")
    with pytest.raises(anf.AnfangsbestandFehler, match="A-B3"):
        anf.binden(aufgebaut.wurzel, linie, _zeichner(), schluesselring=TESTRING,
                   snapshot_sha256=fremd["snapshot_sha256"],
                   ordnungslinie=ol.lade_linie(linie)[0])
    assert not (aufgebaut.wurzel / ab.BINDUNG_DATEI).exists()


def test_eine_veraenderte_bindung_haelt_den_tag_an(aufgebaut):
    from rechner_pipeline.betrieb.tageslauf import EXIT_USAGE, tageslauf
    from tests.anfangsbestand_testhelfer import schreibe_anfangsbestand

    from rechner_pipeline.betrieb import tageslauf as tl

    with tl.lauf_sperre(aufgebaut):
        schreibe_anfangsbestand(aufgebaut, _zeichner())
    pfad = aufgebaut.wurzel / ab.BINDUNG_DATEI
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["kennzahlen"]["in_kraft"] = 10 ** 6
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    code, zeile = tageslauf(aufgebaut, dt.date(2026, 2, 3))
    assert code == EXIT_USAGE and "Signatur" in zeile["fehler"], zeile.get("fehler")


def test_der_gate_a_b3_im_linienbereich_nimmt_den_beleg_an(aufgebaut, tmp_path):
    """Der Weg ueber das Entscheid-Kommando (statt des Testhelfers):
    Beleg-Vertrag, Rollenmenge ``anfangsbestand``, Stand aus dem Beleg."""
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from tests.zeichnung_fixture import vorstand_rolle, standard_ordnung

    linie = linie_anlegen(tmp_path / "zeichnen", rolle="mensch/betrieb",
                          gates=["A-B3"], klasse="mensch")
    anf.belegen(aufgebaut.wurzel, linie, _zeichner())
    ergebnis = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-B3", "--entscheid", "angenommen",
        "--entscheider", "betriebsverantwortung", "--begruendung", "Anfangsbestand geprueft",
        "--repo-root", str(REPO), *annahme_args(linie, rolle="mensch/betrieb",
                                                gates=["A-B3"], klasse="mensch")])
    assert ergebnis.exit_code == 0, ergebnis.errors
    snap = json.loads(Path(ergebnis.paths["snapshot"]).read_text(encoding="utf-8"))
    assert set(snap["pflichtbelege"]) == {"anfangsbestand"}
    assert snap["stand"]["gefuehrter_tag"] == "2026-01-31"
    assert vorstand_rolle and standard_ordnung


def test_der_leser_des_betriebs_haelt_die_damalige_ordnung(tmp_path):
    """Die Lesestelle des Betriebs (``uebernahme.lies_abnahme_snapshot``,
    durch die Registrierung, Zugangsprobe und Neuaufsetzen gehen) mit der
    Ordnungslinie: Der A-M4-Snapshot unter Glied 1 traegt; gegen eine Linie
    mit ausgetauschtem Glied ist er nicht lokalisierbar; der Zeichner des
    Betriebs laedt die Linie ueber ``--linie``."""
    from rechner_pipeline.betrieb import tageslauf as tl
    from rechner_pipeline.betrieb import uebernahme as ueb
    from rechner_pipeline.models.freigabe import lade_schluesselring

    linie, fall = _fall_mit_linie(tmp_path)
    _verweise(fall, linie)
    am4 = _am4(fall)
    assert am4.exit_code == 0, am4.errors
    ring, _, _ = lade_schluesselring(
        [str(p) for p in sorted(tmp_path.glob("*.key"))], ausserhalb=fall)
    glieder, _ = ol.lade_linie(linie)
    sha = am4.summary["snapshot_sha256"]
    daten, _, verifiziert = ueb.lies_am4_snapshot(
        fall, sha, schluesselring=ring, ordnung=None, ordnungslinie=glieder)
    assert verifiziert and daten["zeichnung"]["ordnungsglied_sha256"] == glieder[0]["glied_sha256"]
    fremd = [ol.baue_glied(glieder[0]["ordnung_text"].encode(), nummer=1, vorgaenger=None,
                           eingetragen_am="2027-01-01")]
    with pytest.raises(ueb.UebernahmeError, match="steht nicht in der Ordnungslinie"):
        ueb.lies_am4_snapshot(fall, sha, schluesselring=ring, ordnung=None, ordnungslinie=fremd)
    schluessel, ordnung = tl._STANDARD_BETRIEBSZEICHNUNG
    z = tl.betriebszeichner(tl.Ablage(tmp_path / "daten"), schluessel, ordnung, linie=linie)
    assert z.ordnungslinie == glieder
