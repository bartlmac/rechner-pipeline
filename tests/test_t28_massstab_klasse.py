"""Pruefrunde T28, Befund 01: Kein Pruefer nimmt den Massstab eines Vergleichs
aus dem Beleg, den er prueft.

Invariante: Die Toleranz eines Wertvergleichs der Migrationssuite und des
aktuariellen Tests weitet sich nur um Komponenten, die der Erzeuger auf den
gebundenen Eingaben gezaehlt hat, und die Kriterien eines Testprofils sind die
der Vorlage, nicht die des Belegs.

Menge (am Code gemessen, 2026-10-22): die zwei Leser der Komponentenzahl,
``abnahmebericht._suite_vergleich_ok`` (Suite, Vorlage und Entscheid A-M4) und
``aktuartest.test_fehler`` (Vorlage und Entscheid A-M1 bis A-M3), und der Leser
der Profilkriterien, ``aktuartest._profil_aus_beleg``. Der Pruefer hat den
ersten bis zur gezeichneten A-M4-Annahme nachgestellt: 1.000 EUR Abweichung bei
einer Police ohne Erhoehungsscheibe, behauptet waren 200.001 Komponenten; schon
sechs behauptete Komponenten liessen +0,04 EUR durch.

Der Weg ist der von T27-06 (Fuehrungsprobe): Der Erzeuger nennt seinen Aufruf,
der Pruefer faehrt ihn auf den gebundenen Eingaben neu und haelt den ganzen
Beleg dagegen. Die Kette ist die echte des zweiten Baldrian-Laufs
(``tests/test_am4_fuehrungswert_und_tarifregeln.py``); verstuemmelt wird nur
der Beleg, die Hashes, die ihn binden, werden nachgefuehrt.

Knoten: klv/tg2015
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any, Dict

from rechner_pipeline.gates import abnahmebericht
from rechner_pipeline.gates._common import Exit
from tests.test_am4_fuehrungswert_und_tarifregeln import (  # noqa: F401 — Fixture
    REPO_ROOT,
    SRC,
    STICHTAG_1,
    STICHTAG_2,
    _am4,
    _fehler,
    _verstuemmelt,
    am4_fall,
)

SUITE = "abgeleitet/berichte/migrationssuite.json"


def _suite(fall: Path) -> Dict[str, Any]:
    return json.loads((fall / SUITE).read_text(encoding="utf-8"))


def _erste_einkomponentige(suite: Dict[str, Any]):
    """Die erste Pruefung eines Vertrags, dessen Vergleiche alle eine
    Komponente tragen (eine Police ohne Erhoehungsscheibe, wie beim Pruefer)."""
    for i, u in enumerate(suite["vertraege"]):
        if u["pruefungen"] and all(p.get("komponenten") == 1 for p in u["pruefungen"]):
            return i
    raise AssertionError("die Kette traegt keinen Vertrag mit einer Komponente")


def _gekaufte_toleranz(delta: float, komponenten: int):
    """Den ersten Vergleich einer einkomponentigen Police um ``delta`` falsch
    machen und die Toleranz ueber eine behauptete Komponentenzahl kaufen: Das
    Residuum ist nachgefuehrt, ``ok`` und ``bestanden`` bleiben gruen, und die
    innere Nachrechnung (``_suite_fehler``) stimmt mit sich ueberein."""
    def aendern(s: Dict[str, Any]) -> None:
        u = s["vertraege"][_erste_einkomponentige(s)]
        p = u["pruefungen"][0]
        p["system"] = p["system"] + delta
        p["residuum"] = p["system"] - p["erwartet"]
        p["komponenten"] = komponenten
        assert abnahmebericht._suite_vergleich_ok(p), "Fixture: die Toleranz deckt delta nicht"
        assert abnahmebericht._suite_fehler(s) == [], "Fixture: innerlich inkonsistent"
    return aendern


# --------------------------------------------------------------------------- #
# Positivkontrolle
# --------------------------------------------------------------------------- #

def test_die_unveraenderte_suite_traegt_ihren_aufruf_und_wird_angenommen(am4_fall):
    suite = _suite(am4_fall)
    assert isinstance(suite.get("aufruf"), list) and "--abzug-1" in suite["aufruf"]
    # Pfade relativ zum Fall: der Beleg ist portabel und der Konsument loest
    # sie gegen seinen Fall auf.
    i = suite["aufruf"].index("--bestand")
    assert suite["aufruf"][i + 1] == "abgeleitet/bestand/bestand.parquet"
    ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code == Exit.OK, _fehler(ergebnis)


def test_ein_legitimer_mehrkomponentenvertrag_bleibt_gruen(am4_fall):
    """Eine pauschale Grenze von eins waere falsch (der Pruefer sagt es
    ausdruecklich): Die Kette traegt Vertraege mit mehr als einer Komponente,
    und die Nachrechnung nimmt ihre Toleranz an, weil der Erzeuger sie zaehlt."""
    suite = _suite(am4_fall)
    mehr = [p["komponenten"] for u in suite["vertraege"] for p in u["pruefungen"]
            if p["komponenten"] > 1]
    assert mehr, "die Kette traegt keinen Mehrkomponentenvertrag — Positivkontrolle blind"
    assert abnahmebericht._suite_nachgerechnet(suite, am4_fall, REPO_ROOT) == []


def test_nachrechnung_unterscheidet_bool_und_zahl_im_suite_beleg(am4_fall):
    """Der ganze Beleg muss auch den JSON-Typ bezeugen: In Python ist
    ``True == 1``, im gespeicherten Beleg sind das verschiedene Aussagen."""
    suite = _suite(am4_fall)
    suite["vertraege"][_erste_einkomponentige(suite)]["pruefungen"][0]["komponenten"] = True
    assert abnahmebericht._suite_nachgerechnet(suite, am4_fall, REPO_ROOT)


# --------------------------------------------------------------------------- #
# Die Gegenproben des Pruefers
# --------------------------------------------------------------------------- #

def test_tausend_euro_mit_200001_behaupteten_komponenten_werden_verweigert(am4_fall):
    with _verstuemmelt(am4_fall, SUITE, _gekaufte_toleranz(1000.0, 200_001)):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != Exit.OK
    assert "weicht von der nachgerechneten Suite" in _fehler(ergebnis), _fehler(ergebnis)


def test_vier_cent_mit_sechs_behaupteten_komponenten_werden_verweigert(am4_fall):
    """Die kleinere Variante der Zweitpruefung: Nicht erst eine absurde Zahl
    kauft Toleranz, schon eine uebliche. Das Delta liegt zwischen der flachen
    Grenze und der Grenze bei sechs Komponenten."""
    p = _suite(am4_fall)["vertraege"][_erste_einkomponentige(_suite(am4_fall))]["pruefungen"][0]
    flach = max(abnahmebericht.ABS_TOL, abs(p["erwartet"]) * abnahmebericht.REL_TOL)
    sechs = max(abnahmebericht.ABS_TOL + 5 * abnahmebericht._CENT_UNSCHAERFE,
                abs(p["erwartet"]) * abnahmebericht.REL_TOL)
    assert flach < sechs, "Fixture-Wert zu gross fuer den Zonen-Test"
    with _verstuemmelt(am4_fall, SUITE, _gekaufte_toleranz((flach + sechs) / 2, 6)):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != Exit.OK
    assert "weicht von der nachgerechneten Suite" in _fehler(ergebnis), _fehler(ergebnis)


def test_eine_suite_ohne_aufruf_wird_verweigert(am4_fall):
    with _verstuemmelt(am4_fall, SUITE, lambda s: s.pop("aufruf")):
        ergebnis = _am4(am4_fall)
    assert ergebnis.exit_code != Exit.OK
    assert "nennt ihren Aufruf nicht" in _fehler(ergebnis), _fehler(ergebnis)


def test_ratsche_jeder_aufrufer_der_suitepruefung_reicht_den_codebaum(am4_fall):
    """Statisch (AST): ``_bestands_suite_fehler`` faehrt die Suite neu und
    braucht dafuer den Codebaum; der Parameter hat keinen Standardwert, und
    JEDER Aufrufer in src (Bericht und Entscheid) uebergibt ihn. Und die
    Pruefung fuehrt wirklich zur Nachrechnung: Eine Suite, die nur in einem
    nachgerechneten Feld abweicht, faellt ueber genau diese Funktion."""
    parameter = inspect.signature(abnahmebericht._bestands_suite_fehler).parameters
    assert parameter["repo_root"].default is inspect.Parameter.empty
    aufrufer = {}
    for p in sorted(SRC.rglob("*.py")):
        for k in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(k, ast.Call) and isinstance(k.func, (ast.Attribute, ast.Name))
                    and getattr(k.func, "attr", getattr(k.func, "id", None))
                    == "_bestands_suite_fehler"):
                aufrufer[str(p.relative_to(SRC))] = {kw.arg for kw in k.keywords}
    assert set(aufrufer) == {"gates/abnahmebericht.py", "gates/gate_entscheid.py"}
    assert all({"fall", "repo_root"} <= kws for kws in aufrufer.values()), aufrufer
    suite = _suite(am4_fall)
    _gekaufte_toleranz(1000.0, 200_001)(suite)
    fehler = abnahmebericht._bestands_suite_fehler(
        suite, stichtag_1=STICHTAG_1, stichtag_2=STICHTAG_2,
        erwartetes_system=suite["system"], fall=am4_fall, repo_root=REPO_ROOT)
    assert any("weicht von der nachgerechneten Suite" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# Zusatzfund: der aktuarielle Test (A-M1 bis A-M3)
# --------------------------------------------------------------------------- #

AT_BELEGE = {"A-M1": "abgeleitet/berichte/aktuartest.json",
             "A-M2": "abgeleitet/berichte/aktuartest-A-M2.json",
             "A-M3": "abgeleitet/berichte/aktuartest-A-M3.json"}


def _at_vorlage(fall: Path, abnahme: str):
    from rechner_pipeline.gates import aktuartest

    return aktuartest.main([
        "--fall", str(fall), "--abnahme", abnahme, "--titel", f"Test {abnahme}",
        "--repo-root", str(REPO_ROOT)])


def _neu_aggregiert(test: Dict[str, Any]) -> None:
    """Was ein Faelscher nach einer geaenderten Zahl nachfuehrt: jede
    Verteilungsgroesse, die die Vorlage nachrechnet (``aktuartest.test_fehler``),
    damit das Ergebnis in sich stimmig bleibt."""
    from rechner_pipeline.gates.aktuartest import _ist_wertvergleich, _profil_aus_beleg
    from rechner_pipeline.qa.aktuarieller_test import verteilung, verteilungsbefunde

    vertraege = test["vertraege"]
    wert = [p for v in vertraege for p in v["pruefungen"] if _ist_wertvergleich(p)]

    def res(ps):
        return [p["system"] - p["erwartet"] for p in ps]

    test["verteilung"] = verteilung(res(wert))
    for typ in test["gruppen"]:
        im_typ = [v for v in vertraege if v.get("historientyp") == typ]
        test["gruppen"][typ] = {
            "anzahl": len(im_typ), "bestanden": sum(1 for v in im_typ if v.get("bestanden")),
            **verteilung(res([p for v in im_typ for p in v["pruefungen"]
                              if _ist_wertvergleich(p)]))}
    for anlass in test["nach_anlass"]:
        ps = [p for p in wert if p["anlass"] == anlass]
        test["nach_anlass"][anlass] = {"anzahl_vergleiche": len(ps), **verteilung(res(ps))}
    profil = _profil_aus_beleg(test["profil"])
    schluessel = (lambda p: p["anlass"]) if profil.kennung == "A-M3" else (lambda p: p["groesse"])
    test["nach_kriterium"] = {s: verteilung(res([p for p in wert if schluessel(p) == s]))
                              for s in sorted({schluessel(p) for p in wert})}
    test["grenzbefunde"] = verteilungsbefunde(test["nach_kriterium"], profil)


def _erster_wertvergleich_mit_einer_komponente(test: Dict[str, Any]):
    from rechner_pipeline.gates.aktuartest import _ist_wertvergleich

    for v in test["vertraege"]:
        if v.get("komponenten") == 1 and v["bestanden"]:
            for p in v["pruefungen"]:
                if _ist_wertvergleich(p):
                    return v, p
    raise AssertionError("kein bestandener Vertrag mit einer Komponente")


def test_jedes_ergebnis_des_aktuariellen_tests_traegt_seinen_aufruf_und_ist_nachrechenbar(am4_fall):
    from rechner_pipeline.gates import aktuartest

    for abnahme, rel in AT_BELEGE.items():
        test = json.loads((am4_fall / rel).read_text(encoding="utf-8"))
        assert isinstance(test.get("aufruf"), list) and "--erwartungswerte" in test["aufruf"]
        assert aktuartest.test_nachgerechnet(test, am4_fall, REPO_ROOT) == [], abnahme
        ergebnis = _at_vorlage(am4_fall, abnahme)
        assert ergebnis.exit_code == Exit.OK, (abnahme, _fehler(ergebnis))


def test_nachrechnung_unterscheidet_bool_und_zahl_im_aktuartest(am4_fall):
    from rechner_pipeline.gates import aktuartest

    test = json.loads((am4_fall / AT_BELEGE["A-M1"]).read_text(encoding="utf-8"))
    vertrag, _ = _erster_wertvergleich_mit_einer_komponente(test)
    vertrag["komponenten"] = True
    assert aktuartest.test_nachgerechnet(test, am4_fall, REPO_ROOT)


def test_eine_behauptete_komponentenzahl_kauft_im_verlaufstest_keine_toleranz(am4_fall):
    """Der Zusatzfund der merge-session (``aktuartest.py:330``): Dieselbe
    behauptete Zahl wie in der Suite, hier an der Vertragszeile. Das Delta
    liegt zwischen der Grenze des Profils und der Grenze bei sechs
    Komponenten und unter den Verteilungsgrenzen des Verlaufstests; das
    gefaelschte Ergebnis ist in sich stimmig."""
    from rechner_pipeline.gates import aktuartest

    def aendern(test: Dict[str, Any]) -> None:
        v, p = _erster_wertvergleich_mit_einer_komponente(test)
        grenze = test["profil"]["grundtoleranz"]["abs_tol"]
        p["system"] = p["erwartet"] + grenze + 2.5 * abnahmebericht._CENT_UNSCHAERFE
        p["residuum"] = p["system"] - p["erwartet"]
        v["komponenten"] = 6
        _neu_aggregiert(test)
        assert test["grenzbefunde"] == [] and test["test_bestanden"] is True
        assert aktuartest.test_fehler(test) == [], "Faelschung in sich nicht stimmig"

    with _verstuemmelt(am4_fall, AT_BELEGE["A-M2"], aendern):
        ergebnis = _at_vorlage(am4_fall, "A-M2")
    assert ergebnis.exit_code != Exit.OK
    assert "weicht vom nachgerechneten Test" in _fehler(ergebnis), _fehler(ergebnis)


def test_ein_selbst_geweitetes_profil_kauft_keine_toleranz(am4_fall):
    """Neben der Komponentenzahl nennt das Ergebnis auch die Kriterien seines
    Profils selbst (``aktuartest._profil_aus_beleg``), und mit ihnen die
    Verteilungsgrenzen. 50 EUR Abweichung bei einer Grenze von 100 EUR, in
    sich stimmig: vorher eine gruene Vorlage."""
    from rechner_pipeline.gates import aktuartest

    def aendern(test: Dict[str, Any]) -> None:
        _, p = _erster_wertvergleich_mit_einer_komponente(test)
        p["system"] = p["erwartet"] + 50.0
        p["residuum"] = p["system"] - p["erwartet"]
        test["profil"]["grundtoleranz"].update(
            abs_tol=100.0, max_abs_residuum=100.0, p95_abs_residuum=100.0)
        _neu_aggregiert(test)
        assert test["grenzbefunde"] == [] and test["test_bestanden"] is True
        assert aktuartest.test_fehler(test) == [], "Faelschung in sich nicht stimmig"

    with _verstuemmelt(am4_fall, AT_BELEGE["A-M1"], aendern):
        ergebnis = _at_vorlage(am4_fall, "A-M1")
    assert ergebnis.exit_code != Exit.OK
    assert "weicht vom nachgerechneten Test" in _fehler(ergebnis), _fehler(ergebnis)


def test_ein_ergebnis_ohne_aufruf_wird_verweigert(am4_fall):
    with _verstuemmelt(am4_fall, AT_BELEGE["A-M3"], lambda t: t.pop("aufruf")):
        ergebnis = _at_vorlage(am4_fall, "A-M3")
    assert ergebnis.exit_code != Exit.OK
    assert "nennt seinen Aufruf nicht" in _fehler(ergebnis), _fehler(ergebnis)


def test_ratsche_vorlage_und_entscheid_rechnen_den_test_nach():
    """Statisch (AST): Die Nachrechnung hat genau zwei Aufrufer, die Vorlage
    (``gates/aktuartest.py``) und den Entscheid von A-M1 bis A-M3
    (``gates/gate_entscheid.py``); beide uebergeben Ergebnis, Fall und
    Codebaum. Dass die Vorlage damit wirklich rot wird, zeigen die
    Gegenproben oben; der Entscheid ruft dieselbe Funktion."""
    from rechner_pipeline.gates import aktuartest

    assert list(inspect.signature(aktuartest.test_nachgerechnet).parameters) == [
        "test", "fall", "repo_root"]
    aufrufer = {}
    for p in sorted(SRC.rglob("*.py")):
        for k in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(k, ast.Call) and isinstance(k.func, (ast.Attribute, ast.Name))
                    and getattr(k.func, "attr", getattr(k.func, "id", None))
                    == "test_nachgerechnet"):
                aufrufer.setdefault(str(p.relative_to(SRC)), []).append(len(k.args))
    assert aufrufer == {"gates/aktuartest.py": [3], "gates/gate_entscheid.py": [3]}, aufrufer


def test_der_entscheid_von_a_m1_rechnet_den_test_nach(tmp_path):
    """Bis zur Zeichnung, wie der Pruefer bei A-M4: Die Faelschung ist in sich
    stimmig, der Bericht ist aus ihr gerendert und das Ledger bindet beide
    Bytes. Die Annahme prueft Ledger, Vertrag, Profil, Urteil, Systemstand
    und Wiedergabe des Berichts, und jede dieser Pruefungen besteht; erst die
    Nachrechnung weist sie ab."""
    from rechner_pipeline.gates import aktuartest
    from tests.test_pk1_am4_beweisvertrag import (
        _aktuartest_belege,
        _bereite_fall,
        _p9_annahme,
    )

    fall = _bereite_fall(tmp_path, ("klv/tg2012",), scope="bestand")
    _aktuartest_belege(fall)
    berichte = fall / "abgeleitet" / "berichte"
    ledger_pfad = fall / "abgeleitet" / "diagnostics" / "aktuartest.gate.json"
    test = json.loads((berichte / "aktuartest.json").read_text(encoding="utf-8"))
    v, p = _erster_wertvergleich_mit_einer_komponente(test)
    # Ueber der Grenze des Profils (0,01), unter der Grenze bei sechs
    # Komponenten und unter den Verteilungsgrenzen.
    p["system"] = p["erwartet"] + 0.015
    p["residuum"] = p["system"] - p["erwartet"]
    v["komponenten"] = 6
    _neu_aggregiert(test)
    assert aktuartest.test_fehler(test) == [] and test["test_bestanden"] is True
    (berichte / "aktuartest.json").write_text(json.dumps(test, sort_keys=True), encoding="utf-8")
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    titel = ledger["summary"]["bericht_erzeugung"]["titel"]
    (berichte / "aktuartest.html").write_text(
        aktuartest.baue_bericht(titel=titel, test=test), encoding="utf-8", newline="\n")
    ledger["summary"]["belege"] = {
        f"abgeleitet/berichte/{name}": hashlib.sha256((berichte / name).read_bytes()).hexdigest()
        for name in ("aktuartest.json", "aktuartest.html")}
    ledger_pfad.write_text(json.dumps(ledger), encoding="utf-8")

    entscheid = _p9_annahme(fall, "A-M1", "auf gekaufter Toleranz")
    assert entscheid.exit_code == 20
    assert "weicht vom nachgerechneten Test" in entscheid.errors[0]["message"], entscheid.errors
