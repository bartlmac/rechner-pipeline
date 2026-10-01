"""A-M4 rechnet den Fuehrungswert nach und haelt jeden Beleg an die Regeln der Spez.

Pruefrunde G, Funde G03 und G04, ueber die echte Kette des zweiten
Baldrian-Laufs (``tests/test_baldrian2_e2e.py``) und das echte Kommando
``gates.abnahmebericht``. Verstuemmelt wird nur der Beleg, Hashes, die ihn
binden, werden nachgefuehrt; das Pruefergebnis wird nie ersetzt.

G03, Invariante: A-M4 pinnt nur einen Fuehrungswert, den es aus dem
gebundenen Bestand (``bestand_sha256``) und der gebundenen Config
(``config_sha256``) ueber dieselbe Funktion wie die Suite selbst
nachgerechnet hat, in der Konvention, die der Kopf nennt; und der Bericht
weist ihn aus (Summen und Anzahl je Stichtag, Konvention, Bindungen; je
Vertrag), im HTML und in der Summary. Vorher wurde nur die Form geprueft:
ein verdoppeltes Deckungskapital, eine falsche Konvention und ein falscher
Status "nicht mehr in Kraft" gingen durch.

G04, Invariante: Jeder Beleg der Bestandsstrecke, den A-M4 pinnt, nennt
GENAU die Tarifregeln der Spez, die A-M4 bindet, und hat diese Spez gelesen.
Menge (gemessen, Ratsche mit ``==``): Uebernahmebeleg, Schichtbeleg der
Verankerung, die drei Belege des aktuariellen Tests, Suite, Fuehrungsprobe.
Vorher las A-M4 die Regelangaben gar nicht.

Die A-Box dieses Schnitts ist ein Platzhalter: Er fuehrt keine (siehe
``test_baldrian2_e2e``), und die Scope-Bindung braucht nur die Datei.

Knoten: klv/tg2015
"""

from __future__ import annotations

import ast
import contextlib
import copy
import hashlib
import inspect
import json
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, Iterator

import pytest

from rechner_pipeline.bestand import cli_fortschreibung, cli_report
from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    abnahmebericht,
    aktuartest_lauf,
    bestand_uebernehmen,
    bestand_validate,
    fuehrungsprobe,
    migrationssuite_lauf,
    transformation_anwenden,
    verankerung_belegen,
)
from tests.e2e_fixture import zellen_config
from tests.test_baldrian2_e2e import (
    ABNAHMEN,
    ABZUG_1,
    ABZUG_2,
    ANKER,
    FIXTURE,
    GENERATION,
    METADATEN,
    NICHT_LIEFERUNG,
    PROTOKOLL,
    REPO_ROOT,
    STICHPROBE,
    STICHTAG_1,
    STICHTAG_2,
    TARIF_GENERATION,
    _lieferungs_flags,
    schreibe_auskunft,
)

SRC = REPO_ROOT / "src" / "rechner_pipeline"

#: Plausibilitaetsbaender: Ohne sie ist der P-B1-Beleg nicht abnahmereif
#: (``abnahmebericht.PB1_PFLICHT_POSITIV``); die Kette des Regressionstests
#: endet deshalb vor A-M4, diese hier nicht.
BAENDER = ("\n[plausibilitaet]\nentry_age = [0, 99]\nduration = [1, 80]\n"
           "premium_duration = [1, 80]\nsum_insured = [100, 10000000]\n")

#: Die Belege der Bestandsstrecke, die mit Tarifregeln gerechnet haben und die
#: A-M4 haelt — gemessen am gefahrenen Lauf (Pfad im Fall -> Ort der Angabe).
BELEGE_MIT_REGELN = {
    "abgeleitet/bestand/uebernahme.json": "tarifwerk/quellverfahren",
    "abgeleitet/schichten/verankerung_schichten.json": "provenienz.parameter.tarifregeln",
    "abgeleitet/berichte/aktuartest.json": "tarifregeln",
    "abgeleitet/berichte/aktuartest-A-M2.json": "tarifregeln",
    "abgeleitet/berichte/aktuartest-A-M3.json": "tarifregeln",
    "abgeleitet/berichte/migrationssuite.json": "tarifregeln",
    "abgeleitet/berichte/fuehrungsprobe.json": "provenienz.parameter.tarifregeln",
}


@pytest.fixture(scope="module")
def am4_fall(tmp_path_factory) -> Path:
    """Die Kette des zweiten Laufs bis zur Vorlage von A-M4, abnahmereif.

    Dieselben Schritte und Aufrufe wie ``test_baldrian2_e2e.gefahrener_fall``,
    dazu die Plausibilitaetsbaender in der Config des Falls. Die Belege nennen
    absolute Pfade in diesen Fall (P-B1-Rollen, Aufruf der Probe): Er wird an
    Ort und Stelle verstuemmelt und Byte fuer Byte zurueckgesetzt.
    """
    basis = tmp_path_factory.mktemp("am4")
    fall = basis / "fall"
    anlegen(fall, scope="bestand")
    for pfad in sorted(FIXTURE.glob("*")):
        if pfad.suffix in (".csv", ".json") and pfad.name not in NICHT_LIEFERUNG:
            registrieren(fall, pfad)
    registrieren(fall, schreibe_auskunft(basis / "auskunft"))
    abgeleitet = fall / "abgeleitet"
    (abgeleitet / "spez").mkdir(parents=True)
    shutil.copy2(FIXTURE / "klv-tg2015.spez.json", abgeleitet / "spez" / "klv-tg2015.spez.json")
    spec = abgeleitet / "transformation" / "abzug.spec.json"
    spec.parent.mkdir(parents=True)
    shutil.copy2(FIXTURE / "transformation.spec.json", spec)
    zeilen = abgeleitet / "transformation" / "zeilen.json"
    assert transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec), "--anwenden", "--zeilen", str(zeilen)]) == 0
    bestand = abgeleitet / "bestand"
    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen), "--tarif-generation", TARIF_GENERATION,
        "--stichtag", STICHTAG_1, "--vorgeschichte", METADATEN, "--generation-spez", GENERATION,
        "--anfangszustand", "materialisieren", "--anker-erwartungswerte", ANKER,
        "--out-dir", str(bestand)] + _lieferungs_flags()) == 0
    assert transformation_anwenden.main([
        "--fall", str(fall), "--spec", str(spec), "--anwenden", "--zeilen", str(zeilen),
        "--ziel", str(bestand / "bestand.parquet"),
        "--ergebnis", str(abgeleitet / "transformation" / "ergebnis.json")]) == 0
    config = abgeleitet / "bestand-config.toml"
    config.write_text(zellen_config((bestand / "generation-zellen.toml").read_text("utf-8"),
                                    name=TARIF_GENERATION, knoten=GENERATION) + BAENDER,
                      encoding="utf-8")
    assert verankerung_belegen.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
        "--zeilen", str(zeilen), "--vorgeschichte", METADATEN, "--anker-erwartungswerte", ANKER,
        "--config", str(config), "--stichtag", STICHTAG_1] + _lieferungs_flags()) == 0
    schichten = abgeleitet / "schichten" / "verankerung_schichten.json"

    def pb1(lauf: Path, portfolio: str, bis: str, diagnostics: str) -> None:
        ergebnis = bestand_validate.main([
            "--portfolio", str(lauf / portfolio), "--historie", str(lauf / "historie.parquet"),
            "--ledger", str(lauf / "ledger.parquet"), "--scheiben", str(lauf / "scheiben.parquet"),
            "--merkmale", str(lauf / "merkmale.parquet"),
            "--schichten", str(lauf / "schichten.parquet"),
            "--verankerung", str(lauf / "verankerung.parquet"), "--config", str(config),
            "--bis", bis, "--manifest", str(lauf / "laufmanifest.json"),
            "--repo-root", str(REPO_ROOT), "--diagnostics-dir", str(abgeleitet / diagnostics)])
        assert ergebnis.exit_code == 0, ergebnis.errors

    pb1(bestand, "bestand.parquet", STICHTAG_1, "diagnostics")
    gemeinsam = ["--zeilen", str(zeilen), "--vorgeschichte", METADATEN,
                 "--anker-erwartungswerte", ANKER, "--schicht", str(schichten),
                 "--repo-root", str(REPO_ROOT)] + _lieferungs_flags()
    for abnahme, erwartung in ABNAHMEN:
        assert aktuartest_lauf.main([
            "--fall", str(fall), "--abnahme", abnahme, "--generation", GENERATION,
            "--erwartungswerte", erwartung, "--stichprobe", STICHPROBE,
            "--bestand", str(bestand / "bestand.parquet")] + gemeinsam) == 0, abnahme
    assert migrationssuite_lauf.main([
        "--fall", str(fall), "--generation", GENERATION, "--abzug-1", ABZUG_1,
        "--abzug-2", ABZUG_2, "--gevo-protokoll", PROTOKOLL,
        "--bestand", str(bestand / "bestand.parquet"), "--config", str(config),
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2] + gemeinsam) == 0
    nach = abgeleitet / "bestand-nach"
    assert cli_fortschreibung.main(["--config", str(config), "--bis", STICHTAG_2,
                                    "--uebernahme", str(bestand), "--out-dir", str(nach)]) == 0
    pb1(nach, "bestand_gesamt.parquet", STICHTAG_2, "diagnostics-nach")
    assert fuehrungsprobe.main([
        "--fall", str(fall), "--generation", GENERATION, "--uebernahme", str(bestand),
        "--fortschreibung", str(nach), "--config", str(config),
        "--stichtag", STICHTAG_1] + gemeinsam) == 0
    berichte = abgeleitet / "berichte"
    for name, lauf, portfolio, bis in (
            ("bestandsbericht-vor.html", bestand, "bestand.parquet", STICHTAG_1),
            ("bestandsbericht-nach.html", nach, "bestand_gesamt.parquet", STICHTAG_2)):
        assert cli_report.main([
            "--portfolio", str(lauf / portfolio), "--historie", str(lauf / "historie.parquet"),
            "--ledger", str(lauf / "ledger.parquet"), "--bis", bis,
            "--out", str(berichte / name)]) == 0, name
    # Die A-Box: ein Platzhalter (dieser Schnitt fuehrt keine; die
    # Scope-Bindung braucht nur die Datei).
    (abgeleitet / "abox").mkdir()
    (abgeleitet / "abox" / "abox.json").write_text("{}", encoding="utf-8")
    return fall


def _am4(fall: Path):
    berichte = fall / "abgeleitet" / "berichte"
    return abnahmebericht.main([
        "--fall", str(fall), "--suite", str(berichte / "migrationssuite.json"),
        "--titel", "Migrationsabnahme Testschnitt",
        "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
        "--spec", str(fall / "abgeleitet" / "transformation" / "abzug.spec.json"),
        "--transformation-ergebnis",
        str(fall / "abgeleitet" / "transformation" / "ergebnis.json"),
        "--bestandsbericht-vor", str(berichte / "bestandsbericht-vor.html"),
        "--bestandsbericht-nach", str(berichte / "bestandsbericht-nach.html"),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(fall / "abgeleitet" / "diagnostics"),
    ])


def _sha(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


@contextlib.contextmanager
def _verstuemmelt(fall: Path, rel: str, aenderung: Callable[[Dict[str, Any]], None]
                  ) -> Iterator[None]:
    """Einen JSON-Beleg aendern und die Hashes nachfuehren, unter denen Suite
    und aktuarieller Test ihn gebunden haben; danach Byte fuer Byte zurueck."""
    pfad = fall / rel
    gesichert = {}
    for name in ("migrationssuite.json", "aktuartest.json", "aktuartest-A-M2.json",
                 "aktuartest-A-M3.json"):
        p = fall / "abgeleitet" / "berichte" / name
        gesichert[p] = p.read_bytes()
    gesichert.setdefault(pfad, pfad.read_bytes())
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        aenderung(daten)
        pfad.write_text(json.dumps(daten, indent=2, sort_keys=True, ensure_ascii=False),
                        encoding="utf-8")
        neu = _sha(pfad)
        for p in gesichert:
            if p == pfad:
                continue
            beleg = json.loads(p.read_text(encoding="utf-8"))
            if rel in (beleg.get("eingaben") or {}):
                beleg["eingaben"][rel] = neu
                p.write_text(json.dumps(beleg, indent=2, sort_keys=True, ensure_ascii=False),
                             encoding="utf-8")
        yield
    finally:
        for p, roh in gesichert.items():
            p.write_bytes(roh)


def _fehler(ergebnis) -> str:
    return " | ".join(f"{e['code']}: {e['message']}" for e in ergebnis.errors)


# --------------------------------------------------------------------------- #
# Positivkontrolle: die unveraenderte Kette
# --------------------------------------------------------------------------- #

def test_die_unveraenderte_kette_nimmt_a_m4_an_und_weist_den_fuehrungswert_aus(am4_fall):
    """Exit 0 — und die Vorlage NENNT den Fuehrungswert: in der Summary
    (Konvention, Bindungen, je Stichtag Anzahl in Kraft und Summen) und im
    HTML je Vertrag. Die Summen sind hier unabhaengig aus den Zeilen des
    Suite-Belegs aufaddiert."""
    ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code == 0, _fehler(ergebnis)
    suite = json.loads((am4_fall / "abgeleitet" / "berichte" / "migrationssuite.json")
                       .read_text(encoding="utf-8"))
    fw = ergebnis.summary["fuehrungswert"]
    assert fw["konvention"] == suite["fuehrungswert"]["konvention"] == "monatsgenau"
    assert fw["bestand_sha256"] == suite["bestand_sha256"]
    assert fw["config_sha256"] == _sha(am4_fall / "abgeleitet" / "bestand-config.toml")
    for termin in ("stichtag_1", "stichtag_2"):
        zeilen = [v["fuehrungswert"][termin] for v in suite["vertraege"]
                  if v["fuehrungswert"][termin] is not None]
        assert fw[termin]["stichtag"] == suite[termin]
        assert fw[termin]["in_kraft"] == len(zeilen)
        assert fw[termin]["nicht_in_kraft"] == len(suite["vertraege"]) - len(zeilen)
        for groesse in ("deckungskapital", "rueckkaufswert", "korrekturschicht"):
            assert fw[termin]["summen"][groesse] == pytest.approx(
                sum(z[groesse] for z in zeilen), abs=1e-6)
    assert fw["stichtag_1"]["in_kraft"] == len(suite["vertraege"]) > 0
    html = (am4_fall / "abgeleitet" / "berichte" / "migrationsabnahme.html").read_text("utf-8")
    assert "Führungswert" in html
    erster = suite["vertraege"][0]
    assert f"{erster['fuehrungswert']['stichtag_1']['deckungskapital']:.2f}" in html


# --------------------------------------------------------------------------- #
# G03: der Fuehrungswert wird nachgerechnet
# --------------------------------------------------------------------------- #

def _dk_verdoppelt(s):
    t = s["vertraege"][0]["fuehrungswert"]["stichtag_1"]
    t["deckungskapital"] = t["deckungskapital"] * 2.0 + 1000.0


def _konvention_jahreszeile(s):
    s["fuehrungswert"]["konvention"] = "jahreszeile"


def _nicht_mehr_in_kraft(s):
    in_kraft = next(v for v in s["vertraege"] if v["fuehrungswert"]["stichtag_2"] is not None)
    in_kraft["fuehrungswert"]["stichtag_2"] = None


def _rkw_einer_police_am_folgestichtag(s):
    v = next(v for v in s["vertraege"] if v["fuehrungswert"]["stichtag_2"] is not None)
    v["fuehrungswert"]["stichtag_2"]["rueckkaufswert"] += 0.01


@pytest.mark.parametrize("aenderung", [
    _dk_verdoppelt, _konvention_jahreszeile, _nicht_mehr_in_kraft,
    _rkw_einer_police_am_folgestichtag,
], ids=lambda f: f.__name__.strip("_"))
def test_ein_verfaelschter_fuehrungswert_wird_verweigert(am4_fall, aenderung):
    with _verstuemmelt(am4_fall, "abgeleitet/berichte/migrationssuite.json", aenderung):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != 0
    text = _fehler(ergebnis)
    assert "suite_scope_contract" in text and "nachgerechnet" in text, text


def test_eine_nach_der_suite_geaenderte_nebentabelle_wird_verweigert(am4_fall):
    """Auf den GEBUNDENEN Bytes: Liegt neben dem Bestand eine Tabelle, die die
    Suite nicht gelesen hat, rechnet A-M4 nicht auf ihr — es verweigert."""
    pfad = am4_fall / "abgeleitet" / "bestand" / "reduktionen.parquet"
    assert not pfad.exists()
    shutil.copy2(am4_fall / "abgeleitet" / "bestand" / "historie.parquet", pfad)
    try:
        ergebnis = _am4(am4_fall)
    finally:
        pfad.unlink()
    assert ergebnis.exit_code != 0
    assert "reduktionen.parquet" in _fehler(ergebnis), _fehler(ergebnis)


def test_ratsche_jeder_aufrufer_der_suitepruefung_nennt_den_fall():
    """Statisch (AST): ``_bestands_suite_fehler`` rechnet nach und braucht
    dafuer den Fall; der Parameter hat keinen Standardwert, und JEDER Aufrufer
    in src (Bericht und Entscheid) uebergibt ihn. Positivkontrolle: die Suche
    findet beide Aufrufer."""
    parameter = inspect.signature(abnahmebericht._bestands_suite_fehler).parameters
    assert parameter["fall"].default is inspect.Parameter.empty
    aufrufer = {}
    for p in sorted(SRC.rglob("*.py")):
        for k in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(k, ast.Call) and isinstance(k.func, (ast.Attribute, ast.Name))
                    and getattr(k.func, "attr", getattr(k.func, "id", None))
                    == "_bestands_suite_fehler"):
                aufrufer[str(p.relative_to(SRC))] = {kw.arg for kw in k.keywords}
    assert set(aufrufer) == {"gates/abnahmebericht.py", "gates/gate_entscheid.py"}
    assert all("fall" in kws for kws in aufrufer.values()), aufrufer


# --------------------------------------------------------------------------- #
# G04: jeder Beleg nennt die Regeln der Spez
# --------------------------------------------------------------------------- #

def _angabe(daten: Dict[str, Any], ort: str) -> Dict[str, Any]:
    if ort == "tarifwerk/quellverfahren":
        return daten
    for teil in ort.split("."):
        daten = daten[teil]
    return daten


def test_ratsche_die_menge_der_belege_mit_regeln(am4_fall):
    """``==`` gegen die Menge, die A-M4 haelt, und Positivkontrolle: jeder
    dieser Belege liegt im gefahrenen Lauf und nennt dieselben Regeln."""
    assert set(abnahmebericht.TARIFREGEL_BELEGE) == set(BELEGE_MIT_REGELN)
    regeln = set()
    for rel, ort in BELEGE_MIT_REGELN.items():
        angabe = _angabe(json.loads((am4_fall / rel).read_text(encoding="utf-8")), ort)
        regeln.add(json.dumps({"tarifwerk": angabe["tarifwerk"],
                               "quellverfahren": angabe["quellverfahren"]}, sort_keys=True))
    assert len(regeln) == 1, regeln


@pytest.mark.parametrize("rel", sorted(BELEGE_MIT_REGELN))
def test_ein_beleg_mit_anderen_regeln_wird_verweigert(am4_fall, rel):
    """Der Umfang der Teilkuendigung im Beleg umgestellt — die Suite, der
    aktuarielle Test, die Probe: jeder Beleg, nicht nur der nachgerechnete."""
    def aenderung(d):
        _angabe(d, BELEGE_MIT_REGELN[rel])["tarifwerk"]["tku_umfang"] = "alle_bausteine"

    with _verstuemmelt(am4_fall, rel, aenderung):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != 0
    text = _fehler(ergebnis)
    assert Path(rel).name in text and "Tarifregeln" in text, text


@pytest.mark.parametrize("rel", sorted(BELEGE_MIT_REGELN))
def test_ein_beleg_ohne_regelangabe_wird_verweigert(am4_fall, rel):
    def aenderung(d):
        ort = BELEGE_MIT_REGELN[rel]
        if ort == "tarifwerk/quellverfahren":
            del d["quellverfahren"]
        else:
            *weg, letzt = ort.split(".")
            for teil in weg:
                d = d[teil]
            del d[letzt]

    with _verstuemmelt(am4_fall, rel, aenderung):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != 0
    text = _fehler(ergebnis)
    assert Path(rel).name in text and "Tarifregeln" in text, text


def test_ein_aktuarieller_test_auf_einer_anderen_spez_wird_verweigert(am4_fall):
    """Die ehrliche Variante: ein alter Beleg, gerechnet auf einer frueheren
    Spez, waehrend die Kette neu lief. Er nennt dieselben Regeln, hat aber
    eine andere Spez gelesen."""
    rel = "abgeleitet/berichte/aktuartest-A-M2.json"

    def aenderung(d):
        schluessel = next(k for k in d["eingaben"] if k.endswith(".spez.json"))
        d["eingaben"][schluessel] = "0" * 64

    with _verstuemmelt(am4_fall, rel, aenderung):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != 0
    text = _fehler(ergebnis)
    assert "aktuartest-A-M2.json" in text and "Spez" in text, text


def test_die_regeln_der_spez_stehen_in_der_summary(am4_fall):
    """A-M4 bindet die Spez: Hash und Regeln stehen im Beleg der Vorlage."""
    ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code == 0, _fehler(ergebnis)
    spez = am4_fall / "abgeleitet" / "spez" / "klv-tg2015.spez.json"
    gebunden = ergebnis.summary["tarifregeln"]
    assert gebunden["spez_sha256"] == _sha(spez)
    roh = json.loads(spez.read_text(encoding="utf-8"))
    assert gebunden["regeln"]["tarifwerk"] == roh["tarifwerk"]
    assert gebunden["regeln"]["quellverfahren"] == roh["quellverfahren"]
    assert copy.deepcopy(gebunden["regeln"])["generation"] == roh["generation"]
