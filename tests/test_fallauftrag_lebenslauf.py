"""Der Lebenslauf eines Falls — Fallauftrag (A-M6) und Fallabbruch (A-M5), ADR-026.

Frage des Maintainers: "jemand muss es beauftragen und dem Programmleiter
den Auftrag geben und das kann nur ein Mensch sein (Auftrag zeichnen)". Die
Tests halten die Aussagen des Entscheids einzeln:

* jeder Abnahmepunkt eines Falls setzt den geltenden Fallauftrag voraus —
  an EINER Stelle (``gates.gate_entscheid.fallauftrag_pruefen``);
* den Auftrag zeichnet der Vorstand (Rolle der Linie), keine andere Rolle;
* der Auftrag ist an die Lieferung gebunden — aendert sich der Eingang,
  gilt er nicht mehr;
* er benennt die Programmleitung (Rolle, Fingerabdruck) und die Mandate
  simulierter Rollen; die Fall-Rolle hat ihr Recht auf A-M5 aus IHM, die
  Ordnung der Linie kann es niemandem geben (EINE Regel:
  ``models.zeichnung.zeichnende_rolle_fehler``);
* der Abbruch ist der positive Satz "dieser Fall endet hier, ohne Abnahme";
  danach ist im Fall nichts mehr zeichenbar;
* die Wurzel traegt genau die Gates der Wurzel, keine fachliche Abnahme.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.fall import registrieren
from rechner_pipeline.gates import fall_belegen, gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models import fallauftrag as fa
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models.schemas import P9Snapshot
from rechner_pipeline.models.zeichnung import (
    ABBRUCH_GATE,
    AUFTRAG_GATE,
    FALLROLLEN_GATES,
    PROGRAMMLEITUNG,
    ZEICHENBARE_GATES,
    pruefe_ordnung,
    zeichnende_rolle_fehler,
)
from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import (
    PROGRAMMLEITUNG_SCHLUESSEL_DATEI,
    VA,
    VORSTAND_SCHLUESSEL_DATEI,
    annahme_args,
    fallauftrag_zeichnen,
    mandat_datei,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def fall(tmp_path: Path) -> Path:
    """Ein pruefbereiter Tarif-Fall (A-Box, P-Q3 gruen), noch ohne Auftrag."""
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(f), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    return f


def _aq1(fall: Path, **kw):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--entscheider", "aktuariat", "--begruendung", "Quellen geprueft",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, **kw)])


def _snapshots(fall: Path, gate: str):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((fall / "entscheide").glob(f"{gate}-*.json"))]


def _abbruch(fall: Path, *, schluessel: "Path | None" = None):
    vorlage = fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "die Lieferung traegt keinen pruefbaren Bestand",
        "--bestand", "wird nicht uebernommen; er bleibt beim abgebenden Haus",
        "--uebergabe", "an den Vorstand, mit dem Befund der Programmleitung"])
    args = annahme_args(fall, fuer=ABBRUCH_GATE)
    if schluessel is not None:
        args += ["--freigabe-schluessel", str(schluessel)]
    return vorlage, gate_entscheid.main([
        "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
        "--entscheider", "programmleitung", "--begruendung", "Fall endet ohne Abnahme",
        "--repo-root", str(REPO_ROOT), *args])


# --------------------------------------------------------------------------- #
# Der Auftrag: ohne ihn keine Abnahme
# --------------------------------------------------------------------------- #


def test_ohne_fallauftrag_nimmt_kein_gate_des_falls_an(fall):
    """Mutationsprobe: in gate_entscheid den Aufruf von fallauftrag_pruefen
    entfernen -> A-Q1 wird angenommen -> rot."""
    ergebnis = _aq1(fall, ohne_auftrag=True)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "fallauftrag"
    assert "keinen Fallauftrag" in ergebnis.errors[0]["message"]
    assert _snapshots(fall, "A-Q1") == []


def test_der_vorstand_beauftragt_und_der_auftrag_bindet_was_er_sagt(fall):
    ergebnis = fallauftrag_zeichnen(fall)
    [auftrag] = _snapshots(fall, AUFTRAG_GATE)
    assert auftrag["rolle"] == ol.WURZELROLLE == ergebnis.summary["rolle"]
    inhalt = auftrag["auftrag"]
    assert fa.auftrag_fehler(inhalt) == []
    assert inhalt["fall"] == {"name": fall.name, "scope": "tarif"}
    # die Lieferung: die Bytes des Eingangs, wie der Fall sie bindet
    eingang_sha = hashlib.sha256((fall / "eingang.json").read_bytes()).hexdigest()
    assert inhalt["lieferung"]["eingang_sha256"] == eingang_sha
    assert auftrag["artefakt_hashes"]["eingang.json"] == eingang_sha
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))["quellen"]
    assert inhalt["lieferung"]["quellen"] == sorted(
        ({"datei": q["datei"], "sha256": q["sha256"]} for q in register),
        key=lambda q: q["datei"])
    # die Programmleitung des Falls: hier benannt, mit ihrem Recht
    pl_fp = hashlib.sha256((fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI)
                           .read_bytes()).hexdigest()
    assert inhalt["programmleitung"] == {"rolle": PROGRAMMLEITUNG, "schluessel_sha256": pl_fp,
                                         "schluesselklasse": "simulation",
                                         "gates": [ABBRUCH_GATE]}
    # die Mandate jeder simulierten Rolle, ausser der Wurzel
    mandat = hashlib.sha256(mandat_datei(fall).read_bytes()).hexdigest()
    assert set(inhalt["mandate"].values()) == {mandat}
    assert ol.WURZELROLLE not in inhalt["mandate"] and PROGRAMMLEITUNG in inhalt["mandate"]
    # die Linie ist Pflicht: der Auftrag verweist auf ihre Abnahmen (hier keine)
    assert inhalt["zielsystem"] == {"linie": "linie",
                                    "abnahmen": {"A-K2": None, "A-O1": None, "A-T1": None}}
    assert inhalt["abgebendes_haus"] == {"aktuar": None, "vermerk": fa.ABGEBENDES_HAUS_VERMERK}
    # und jeder Abnahmepunkt danach nennt ihn signiert
    assert _aq1(fall).exit_code == 0
    [aq1] = _snapshots(fall, "A-Q1")
    assert aq1["fallauftrag"] == auftrag["snapshot_sha256"]
    assert (fall / fa.AUFTRAG_SICHT_RELATIV).is_file()


def test_der_auftrag_verweist_auf_die_abnahmen_der_linie(tmp_path):
    from tests.zeichnung_fixture import linie_anlegen

    linie = linie_anlegen(tmp_path)
    f = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    fallauftrag_zeichnen(f)
    [auftrag] = _snapshots(f, AUFTRAG_GATE)
    assert auftrag["auftrag"]["zielsystem"] == {
        "linie": linie.name, "abnahmen": {"A-K2": None, "A-O1": None, "A-T1": None}}
    assert auftrag["zeichnung"]["ordnungsglied_sha256"]


def test_nur_der_vorstand_beauftragt(fall):
    """Die Standardrolle (mensch/aktuariat) traegt A-M6 nicht.
    Mutationsprobe: _zeichnungsfehler fuer A-M6 ueberspringen -> rot."""
    assert fall_belegen.main([
        "auftrag", "--fall", str(fall), "--zeichnungsordnung", str(_ordnung(fall)),
        "--linie", str(fall.parent / "linie"),
        "--programmleitung-schluessel", str(_pl_schluessel(fall)),
        "--programmleitung-klasse", "mensch", *_mandate(fall),
        "--auftrag", "x"]).exit_code == 0
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", AUFTRAG_GATE, "--entscheid", "angenommen",
        "--entscheider", "aktuariat", "--begruendung", "selbst beauftragt",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, ohne_auftrag=True)])
    assert ergebnis.exit_code == 20 and "nicht zeichnungsberechtigt" in \
        ergebnis.errors[0]["message"], ergebnis.errors
    assert _snapshots(fall, AUFTRAG_GATE) == []


def _ordnung(fall: Path) -> Path:
    annahme_args(fall, ohne_auftrag=True)
    return fall.parent / "zeichnungsordnung.json"


def _pl_schluessel(fall: Path) -> Path:
    from tests.zeichnung_fixture import _PROGRAMMLEITUNG_SCHLUESSEL, schluessel_anlegen

    pfad = fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI
    schluessel_anlegen(pfad, _PROGRAMMLEITUNG_SCHLUESSEL)
    return pfad


def _mandate(fall: Path):
    ordnung = json.loads(_ordnung(fall).read_text(encoding="utf-8"))
    return [teil for rolle in fall_belegen.mandatsrollen(ordnung, "mensch")
            for teil in ("--mandat", f"{rolle}={mandat_datei(fall)}")]


def test_ein_geaenderter_eingang_entzieht_dem_auftrag_die_geltung(fall, tmp_path):
    """Mutationsprobe: in fallauftrag_pruefen den Vergleich der Eingangs-Hashes
    entfernen -> A-Q1 auf geaenderter Lieferung angenommen -> rot."""
    fallauftrag_zeichnen(fall)
    nachgereicht = tmp_path / "nachgereicht.txt"
    nachgereicht.write_text("eine nachgereichte Quelle\n", encoding="utf-8")
    registrieren(fall, nachgereicht)
    # P-Q3 auf der neuen Lieferung, damit allein der Auftrag entscheidet
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    ergebnis = _aq1(fall, ohne_auftrag=True)
    assert ergebnis.exit_code == 20 and ergebnis.errors[0]["code"] == "fallauftrag"
    assert "gilt nicht mehr" in ergebnis.errors[0]["message"]
    # neu beauftragt, auf der neuen Lieferung: die Kette des Auftrags waechst
    fallauftrag_zeichnen(fall)
    assert len(_snapshots(fall, AUFTRAG_GATE)) == 2
    assert _aq1(fall).exit_code == 0


def test_eine_umgeschriebene_vorlage_nimmt_der_vorstand_nicht_an(fall):
    """Das Gate rechnet die Vorlage nach (Fall, Lieferung, Linie, Mandate),
    statt ihr zu glauben."""
    _ordnung(fall)
    assert fall_belegen.main([
        "auftrag", "--fall", str(fall), "--zeichnungsordnung", str(_ordnung(fall)),
        "--linie", str(fall.parent / "linie"),
        "--programmleitung-schluessel", str(_pl_schluessel(fall)),
        "--programmleitung-klasse", "mensch", *_mandate(fall),
        "--auftrag", "x"]).exit_code == 0
    pfad = fall / fa.AUFTRAG_RELATIV
    vorlage = json.loads(pfad.read_text(encoding="utf-8"))
    vorlage["lieferung"]["eingang_sha256"] = "ab" * 32
    pfad.write_text(json.dumps(vorlage), encoding="utf-8")
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", AUFTRAG_GATE, "--entscheid", "angenommen",
        "--entscheider", "vorstand", "--begruendung", "x", "--repo-root", str(REPO_ROOT),
        *annahme_args(fall, fuer=AUFTRAG_GATE)])
    assert ergebnis.exit_code == 20 and "lieferung" in ergebnis.errors[0]["message"]


def test_ein_anderes_mandat_als_das_beauftragte_zeichnet_nicht(fall, tmp_path):
    """Die Mandate bindet der Auftrag. Mutationsprobe: die Mandatspruefung
    gegen den Auftrag entfernen -> rot."""
    fallauftrag_zeichnen(fall)
    anderes = tmp_path / "anderes-mandat.md"
    anderes.write_text("Ein anderes Mandat.\n", encoding="utf-8")
    args = annahme_args(fall)
    args[args.index("--mandat") + 1] = str(anderes)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--entscheider", "aktuariat", "--begruendung", "x", "--repo-root", str(REPO_ROOT),
        *args])
    assert ergebnis.exit_code == 20 and ergebnis.errors[0]["code"] == "mandat"
    assert "Teil des Auftrags" in ergebnis.errors[0]["message"]


# --------------------------------------------------------------------------- #
# Woher eine Rolle ihr Recht hat — EINE Regel
# --------------------------------------------------------------------------- #


def test_keine_ordnung_gibt_das_recht_auf_den_abbruch():
    """A-M5 ist nicht vergebbar: Das Recht kommt aus dem Fallauftrag."""
    assert ABBRUCH_GATE not in ZEICHENBARE_GATES and ABBRUCH_GATE in FALLROLLEN_GATES
    fehler = pruefe_ordnung({"schema_version": 2, "rollen": {VA: {
        "schluessel_sha256": "ab" * 32, "schluesselklasse": "mensch", "gates": [ABBRUCH_GATE]}}})
    assert fehler and "Fallauftrag" in fehler[0]


def test_die_regel_haelt_den_abbruch_gegen_den_auftrag():
    auftrag = {"snapshot_sha256": "aa" * 32, "auftrag": {
        "programmleitung": {"rolle": PROGRAMMLEITUNG, "schluessel_sha256": "bb" * 32,
                            "schluesselklasse": "mensch", "gates": [ABBRUCH_GATE]}}}
    auftrag["auftrag"].update({k: v for k, v in _gueltiger_auftrag().items()
                               if k != "programmleitung"})
    # Die Ordnung der Linie kennt die Programmleitung nicht (Rolle des Falls).
    ordnung_ohne_pl = _linienordnung()
    glied = ol.baue_glied(json.dumps(ordnung_ohne_pl).encode(), nummer=1, vorgaenger=None,
                          eingetragen_am="2026-10-01T08:00:00+00:00")
    linie = [glied]
    abbruch = {"rolle": PROGRAMMLEITUNG, "fallauftrag": "aa" * 32,
               "freigabe": {"schluessel_sha256": "bb" * 32},
               "zeichnung": {"rolle": PROGRAMMLEITUNG, "schluesselklasse": "mensch",
                             "ordnung_sha256": glied["ordnung_sha256"],
                             "ordnungsglied_sha256": glied["glied_sha256"]}}
    assert zeichnende_rolle_fehler(abbruch, ABBRUCH_GATE, ordnung_ohne_pl, linie=linie,
                                   fallauftrag=auftrag) == (PROGRAMMLEITUNG, None)
    # ohne Auftrag: nicht pruefbar
    rolle, meldung = zeichnende_rolle_fehler(abbruch, ABBRUCH_GATE, ordnung_ohne_pl,
                                             linie=linie)
    assert rolle is None and "Fallauftrag" in meldung
    # ein anderer Auftrag als der geltende
    rolle, meldung = zeichnende_rolle_fehler({**abbruch, "fallauftrag": "dd" * 32},
                                             ABBRUCH_GATE, ordnung_ohne_pl, linie=linie,
                                             fallauftrag=auftrag)
    assert rolle is None and "geltenden Auftrag" in meldung
    # ein Schluessel, den der Auftrag nicht benennt (der des Vorstands)
    fremd = {**abbruch, "freigabe": {"schluessel_sha256": "11" * 32}}
    rolle, meldung = zeichnende_rolle_fehler(fremd, ABBRUCH_GATE, ordnung_ohne_pl,
                                             linie=linie, fallauftrag=auftrag)
    assert rolle is None
    # ohne Linie begruendet auch der Abbruch nichts
    rolle, meldung = zeichnende_rolle_fehler(abbruch, ABBRUCH_GATE, ordnung_ohne_pl,
                                             linie=None, fallauftrag=auftrag)
    assert rolle is None and "ohne Ordnungslinie" in meldung


def _gueltiger_auftrag() -> dict:
    return {
        "schema_version": 1, "art": "fallauftrag", "fall": {"name": "f", "scope": "tarif"},
        "lieferung": {"eingang_sha256": "ab" * 32,
                      "quellen": [{"datei": "q.xlsm", "sha256": "cd" * 32}]},
        "programmleitung": {"rolle": PROGRAMMLEITUNG, "schluessel_sha256": "bb" * 32,
                            "schluesselklasse": "mensch", "gates": [ABBRUCH_GATE]},
        "mandate": {}, "zielsystem": {"linie": None, "abnahmen": {}},
        "abgebendes_haus": {"aktuar": None, "vermerk": fa.ABGEBENDES_HAUS_VERMERK},
        "auftrag": "migrieren",
    }


def test_die_form_des_auftrags():
    assert fa.auftrag_fehler(_gueltiger_auftrag()) == []
    for feld, wert in (("programmleitung", {"rolle": "mensch/aktuariat"}),
                       ("abgebendes_haus", {"aktuar": "jemand", "vermerk": "x"}),
                       ("auftrag", " "),
                       ("lieferung", {"eingang_sha256": "ab" * 32, "quellen": []})):
        assert fa.auftrag_fehler({**_gueltiger_auftrag(), feld: wert}), feld


def test_das_schema_kennt_auftrag_und_abbruch_erst_ab_schema_10():
    from tests.test_betrieb_uebernahme import am4_snapshot

    annahme = am4_snapshot("f", schema=9)
    assert "fallauftrag" not in annahme and P9Snapshot.validate_payload(annahme) == []
    ohne = am4_snapshot("f")
    ohne.pop("fallauftrag")
    from rechner_pipeline.models.schemas import p9_snapshot_sha256

    ohne["snapshot_sha256"] = p9_snapshot_sha256(ohne)
    assert any("fallauftrag" in f for f in P9Snapshot.validate_payload(ohne))


# --------------------------------------------------------------------------- #
# Der Abbruch
# --------------------------------------------------------------------------- #


def test_die_programmleitung_bricht_ab_und_danach_ist_nichts_mehr_zeichenbar(fall):
    """Mutationsprobe: abbruch_im_fall immer None -> nach dem Abbruch wird
    A-Q1 angenommen -> rot."""
    fallauftrag_zeichnen(fall)
    vorlage, ergebnis = _abbruch(fall)
    assert vorlage.exit_code == 0, vorlage.errors
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert "endet hier, ohne Abnahme" in ergebnis.summary["anzeige"]
    [abbruch] = _snapshots(fall, ABBRUCH_GATE)
    [auftrag] = _snapshots(fall, AUFTRAG_GATE)
    assert abbruch["rolle"] == PROGRAMMLEITUNG
    assert abbruch["fallauftrag"] == auftrag["snapshot_sha256"]
    inhalt = abbruch["abbruch"]
    assert inhalt["gezeichnet"] == [{"gate": AUFTRAG_GATE, "entscheid": "angenommen",
                                     "snapshot_sha256": auftrag["snapshot_sha256"]}]
    assert inhalt["stand"]["eingang_sha256"] == auftrag["artefakt_hashes"]["eingang.json"]
    assert (fall / fa.ABBRUCH_SICHT_RELATIV).is_file()
    for gate, entscheid in (("A-Q1", "angenommen"), ("A-Q1", "abgelehnt"),
                            (AUFTRAG_GATE, "angenommen"), (ABBRUCH_GATE, "abgelehnt")):
        args = annahme_args(fall, fuer=gate) if entscheid == "angenommen" else [
            "--rolle", "agent/programmleitung", "--linie", str(fall.parent / "linie")]
        danach = gate_entscheid.main([
            "--fall", str(fall), "--gate", gate, "--entscheid", entscheid,
            "--entscheider", "x", "--begruendung", "nach dem Abbruch",
            "--repo-root", str(REPO_ROOT), *args])
        assert danach.exit_code == 20 and danach.errors[0]["code"] == "fallabbruch", (
            gate, entscheid, danach.errors)


def test_ohne_auftrag_kann_die_programmleitung_nicht_abbrechen(fall):
    """Die Vorlage braucht den Auftrag, das Gate auch.
    Mutationsprobe: Rechtsordnung der Fall-Rolle aus der Ordnung statt aus
    dem Auftrag -> rot (der Schluessel steht in keiner Ordnung)."""
    annahme_args(fall, ohne_auftrag=True)
    vorlage = fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "g", "--bestand", "b", "--uebergabe", "u"])
    assert vorlage.exit_code != 0 and "keinen geltenden Fallauftrag" in vorlage.errors[0]["message"]
    # Eine von Hand gelegte, sonst stimmige Vorlage: Allein der fehlende
    # Auftrag haelt den Abbruch an.
    from rechner_pipeline.gates._provenienz import systemstand

    (fall / fa.ABBRUCH_RELATIV).parent.mkdir(parents=True, exist_ok=True)
    (fall / fa.ABBRUCH_RELATIV).write_text(json.dumps({
        "schema_version": 1, "art": "fallabbruch", "fall": fall.name,
        "fallauftrag": "aa" * 32, "grund": "g", "bestand": "b", "uebergabe": "u",
        "gezeichnet": fall_belegen.gezeichnet(fall),
        "stand": {"eingang_sha256": hashlib.sha256((fall / "eingang.json").read_bytes())
                  .hexdigest(), "system": systemstand(REPO_ROOT)}}), encoding="utf-8")
    _pl_schluessel(fall)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
        "--entscheider", "programmleitung", "--begruendung", "x",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, fuer=ABBRUCH_GATE,
                                                     ohne_auftrag=True)])
    assert ergebnis.exit_code == 20 and ergebnis.errors[0]["code"] == "fallauftrag", \
        ergebnis.errors
    assert _snapshots(fall, ABBRUCH_GATE) == []


def test_nur_die_benannte_programmleitung_bricht_ab(fall):
    """Der Vorstand (Rolle der Linie) hat kein Recht auf A-M5 — es kommt aus
    dem Auftrag und gehoert der Fall-Rolle."""
    fallauftrag_zeichnen(fall)
    _, ergebnis = _abbruch(fall, schluessel=fall.parent / VORSTAND_SCHLUESSEL_DATEI)
    assert ergebnis.exit_code == 20 and ergebnis.errors[0]["code"] == "zeichnung", ergebnis.errors
    assert "Fallauftrag benennt" in ergebnis.errors[0]["message"]
    assert _snapshots(fall, ABBRUCH_GATE) == []


def test_eine_abgenommene_migration_bricht_niemand_mehr_ab(fall):
    """A-M5 nach einer geltenden A-M4-Annahme widerriefe die Abnahme.
    Mutationsprobe: die A-M4-Pruefung in _lebenslauf_vorlage entfernen -> rot."""
    from tests.freigabe_testschluessel import TESTKEY
    from tests.test_betrieb_uebernahme import am4_snapshot

    fallauftrag_zeichnen(fall)
    am4 = am4_snapshot(fall.name)
    (fall / "entscheide" / f"A-M4-{am4['snapshot_sha256']}.json").write_text(
        json.dumps(am4), encoding="utf-8")
    testkey = fall.parent / "am4-test.key"
    testkey.write_bytes(TESTKEY)
    testkey.chmod(0o600)
    vorlage = fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "g", "--bestand", "b", "--uebergabe", "u"])
    assert vorlage.exit_code == 0
    args = annahme_args(fall, fuer=ABBRUCH_GATE)
    # Den Pruefschluessel von A-M4 VOR den zeichnenden (der letzte zeichnet).
    pl = args.index(str(fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI))
    args[pl - 1:pl - 1] = ["--freigabe-schluessel", str(testkey)]
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
        "--entscheider", "programmleitung", "--begruendung", "x",
        "--repo-root", str(REPO_ROOT), *args])
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert "widerriefe die Abnahme" in ergebnis.errors[0]["message"]


# --------------------------------------------------------------------------- #
# Die Wurzel: Ordnungsaenderung und Fallauftrag, keine fachliche Abnahme
# --------------------------------------------------------------------------- #


def _linienordnung(**vorstand_gates) -> dict:
    return {"schema_version": 2, "rollen": {
        ol.WURZELROLLE: {"schluessel_sha256": "11" * 32, "schluesselklasse": "mensch",
                         "gates": vorstand_gates.get("gates", list(ol.WURZEL_GATES))},
        VA: {"schluessel_sha256": "22" * 32, "schluesselklasse": "mensch",
             "gates": vorstand_gates.get("va", ["A-Q1"])},
    }}


def test_die_gates_der_wurzel_stehen_an_einer_stelle():
    assert ol.WURZEL_GATES == (ol.ORDNUNGS_GATE, AUFTRAG_GATE)
    ok = lambda d: ol.ordnung_inhalt_fehler(json.dumps(d))[1]  # noqa: E731
    assert ok(_linienordnung()) == []
    assert ok(_linienordnung(gates=[ol.ORDNUNGS_GATE])) == []   # Altstand: nur A-Z1
    # die Wurzel nimmt nichts fachlich ab
    assert ok(_linienordnung(gates=[ol.ORDNUNGS_GATE, AUFTRAG_GATE, "A-M4"]))
    # ohne A-Z1 zeichnet niemand das naechste Glied
    assert ok(_linienordnung(gates=[AUFTRAG_GATE]))
    # keine andere Rolle beauftragt
    assert ok(_linienordnung(va=["A-Q1", AUFTRAG_GATE]))
    # die Programmleitung ist eine Rolle des Falls, nicht der Linie
    mit_pl = _linienordnung()
    mit_pl["rollen"][PROGRAMMLEITUNG] = {"schluessel_sha256": "33" * 32,
                                         "schluesselklasse": "mensch", "gates": []}
    assert any("Rolle des Falls" in f for f in ok(mit_pl))


def test_woher_die_rollen_ihr_recht_haben():
    """Die Tabelle Linie/Fall (ADR-018, Nachtrag 2026-10-01; ADR-026) mit ``==``:
    Fall-Rollen haben ihr Recht aus dem Fallauftrag, Linien-Rollen aus der
    Ordnung der Linie; die Wurzel traegt genau die Gates der Wurzel."""
    from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

    assert FALLROLLEN_GATES == {ABBRUCH_GATE: PROGRAMMLEITUNG} == {"A-M5": "mensch/programmleitung"}
    assert set(FALLROLLEN_GATES.values()) == set(ol.ROLLEN_DES_FALLS)
    assert ol.WURZEL_GATES == ("A-Z1", AUFTRAG_GATE) == ("A-Z1", "A-M6")
    # Was eine Ordnung vergeben kann: alles ausser den Gates der Fall-Rollen
    assert set(GUELTIGE_GATES) - set(ZEICHENBARE_GATES) == set(FALLROLLEN_GATES)
    assert set(ZEICHENBARE_GATES) - set(GUELTIGE_GATES) == {ol.ORDNUNGS_GATE}
