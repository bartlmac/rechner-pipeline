"""Rueckbau des zweiten Baldrian-Laufs — der Kern ohne die Faehigkeiten, die nur
der uebernommene Tarif braucht.

Vor Fall 3 (der Neufassung der Uebernahme) soll das Zielsystem so dastehen,
als haette es den uebernommenen Tarif nie gerechnet: ohne die Ausgestaltungen
im Kern, die allein fuer ihn entstanden sind, ohne seine Tafeln, ohne seine
Generation in der Config. Was die Migration am WERKZEUG gelehrt hat
(Korrekturschicht, Verankerung, Serien-Rekonstruktion, Pruefstrecken) und die
Teilkuendigung als Vorgang des eigenen Geschaefts bleiben (Entscheid des
Maintainers, 2026-10-01).

Zurueckgebaut sind vier Regelwerte, die in der Config nur die Generation
TG2015 fuehrte (gemessen: 13 eigene Generationen tragen den anderen Wert):
``scheiben_mit_gamma1 = true``, ``stoab_je_baustein = true``, ``tku_umfang =
grundversicherung``; dazu die sechs Tafeln aus dem Tarifrechner der Quelle.
Die Regeln selbst bleiben im Vokabular (T-Box, Spez) und in den Signaturen:
Eine Spez darf sie belegen — der Kern VERWEIGERT dann benannt, statt nach der
Regel des eigenen Geschaefts zu rechnen. Das ist die Stelle, an der Fall 3
anhaelt und die Kern-Erweiterung unter A-K2 bringt.

Invariante: Kein Weg in den Kern rechnet eine zurueckgebaute Ausgestaltung;
jeder verweigert mit derselben Meldung (``rechenkern.faehigkeit_fehlt``).
Menge: die Verzweigungen auf diese Regelwerte in ``kern/`` (Ratsche unten,
``==``, mit Positivkontrolle des Detektors).

Die Tests, die auf diesem Stand keinen Gegenstand haben, stehen in
``tests/rueckbau_fall2_ausgesetzt.txt`` (Mechanik: ``tests/rueckbau.py``).

Knoten: klv
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.kern import beitragsreduktion as br
from rechner_pipeline.kern import rechenkern as rk
from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern import vorgangsfolge as vf
from rechner_pipeline.kern.model_point import KLV_DEFAULT
from tests import rueckbau

REPO = Path(__file__).resolve().parents[1]
KERN = REPO / "src" / "rechner_pipeline" / "kern"

MP = dataclasses.replace(KLV_DEFAULT, sum_insured=50000.0, zw=1)
GRUND = rk.Rechenkern(MP)

#: Die Zahl der ausgesetzten Tests. Sie waechst nicht unbemerkt; wer einen Test
#: aussetzt, aendert diese Zahl und sagt im Commit, warum.
ANZAHL_AUSGESETZT = 746

ZURUECKGEBAUT = {
    "scheiben_mit_gamma1": lambda: rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=True),
    "stoab_je_baustein, Reserve des Vertrags": lambda: rk.vertrags_monatsreserve(
        GRUND, [], 60, stoab_je_baustein=True),
    "stoab_je_baustein, Vorgangsfolge": lambda: vf.Vertragsstand.anfang(
        GRUND, (), stoab_je_baustein=True, tku_umfang=vf.UMFANG_ALLE).werte(60),
    "stoab_je_baustein, Herabsetzung": lambda: br.reduziere_geschichtet(
        GRUND, [], 5, 0.7, verfahren="mit_abzug", stoab_je_baustein=True),
    "tku_umfang grundversicherung": lambda: vf.Vertragsstand.anfang(
        GRUND, (), stoab_je_baustein=False, tku_umfang=vf.UMFANG_GRUND).nach_vorgang(
            vf.vorgang(5, 0.7, br.TEILKUENDIGUNG)),
}


@pytest.mark.parametrize("weg", sorted(ZURUECKGEBAUT))
def test_der_kern_verweigert_die_zurueckgebaute_ausgestaltung_benannt(weg):
    with pytest.raises(rk.KernFaehigkeitFehlt) as fehler:
        ZURUECKGEBAUT[weg]()
    meldung = str(fehler.value)
    assert "Der Kern rechnet diese Ausgestaltung nicht" in meldung
    assert "A-K2" in meldung and "mensch/rechenkern" in meldung


def test_positivkontrolle_die_regeln_des_eigenen_geschaefts_rechnen():
    assert rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=False).gamma1 == 0.0
    assert rk.vertrags_monatsreserve(GRUND, [], 60, stoab_je_baustein=False).rkw > 0.0
    stand = vf.Vertragsstand.anfang(GRUND, (), stoab_je_baustein=False,
                                    tku_umfang=vf.UMFANG_ALLE)
    assert stand.werte(60)["deckungskapital"] > 0.0
    # Die Teilkuendigung als Vorgang des eigenen Geschaefts bleibt.
    danach, _ = stand.nach_vorgang(vf.vorgang(5, 0.7, br.TEILKUENDIGUNG))
    assert danach.gesamt_vs() == pytest.approx(0.7 * MP.sum_insured)


def test_keine_generation_der_configs_fuehrt_eine_zurueckgebaute_regel():
    gesehen = 0
    for pfad in sorted((REPO / "configs").glob("bestand_*.toml")):
        for generation in load_config(pfad).generationen:
            tarifwerk = generation.tarifwerk()
            gesehen += 1
            assert generation.name != "TG2015"
            assert tarifwerk["scheiben_mit_gamma1"] is False, generation.name
            assert tarifwerk["stoab_je_baustein"] is False, generation.name
            assert tarifwerk["tku_umfang"] == vf.UMFANG_ALLE, generation.name
            assert tarifwerk["red_verfahren"] != br.TEILKUENDIGUNG, generation.name
    assert gesehen > 0


def test_die_tafeln_der_quelle_sind_nicht_im_kern():
    for name in ("DAV2008_T_NR_U70", "DAV2008_T_R_U70", "DAV2008_T_NR_M", "DAV2008_T_NR_F",
                 "DAV2008_T_R_M", "DAV2008_T_R_F"):
        assert f'<table name="{name}"' not in (KERN / "tafeln.xml").read_text(encoding="utf-8")
    with pytest.raises(tafeln.MissingMortalityTableError):
        tafeln.qx_vector("M", "DAV2008_T_NR_U70")
    assert len(tafeln.qx_vector("M", "DAV2008_T")) > 100      # Positivkontrolle


# --------------------------------------------------------------------------- #
# Ratsche: jede Verzweigung auf einen zurueckgebauten Regelwert verweigert
# --------------------------------------------------------------------------- #

_REGELN = ("stoab_je_baustein", "gamma1_uebernehmen", "UMFANG_GRUND")


def _nennt_regel(knoten: ast.AST) -> bool:
    return any(isinstance(n, ast.Name) and n.id in _REGELN
               or isinstance(n, ast.Attribute) and n.attr in _REGELN
               for n in ast.walk(knoten))


def _verzweigungen(quelle: str) -> list:
    """Je ``if``/``elif``, dessen Bedingung einen zurueckgebauten Regelwert
    nennt: ob sein Zweig NUR aus der einen Verweigerung besteht."""
    aus = []
    for knoten in ast.walk(ast.parse(quelle)):
        if isinstance(knoten, ast.If) and _nennt_regel(knoten.test):
            zweig = knoten.body
            aus.append(len(zweig) == 1 and isinstance(zweig[0], ast.Raise)
                       and isinstance(zweig[0].exc, ast.Call)
                       and getattr(zweig[0].exc.func, "id", "") == "faehigkeit_fehlt")
    return aus


def test_ratsche_jede_verzweigung_auf_einen_zurueckgebauten_wert_verweigert():
    je_datei = {p.name: _verzweigungen(p.read_text(encoding="utf-8"))
                for p in sorted(KERN.glob("*.py"))}
    je_datei = {name: v for name, v in je_datei.items() if v}
    assert {name: len(v) for name, v in je_datei.items()} == {
        "beitragsreduktion.py": 2, "rechenkern.py": 2, "vorgangsfolge.py": 4}
    assert all(all(v) for v in je_datei.values()), je_datei


def test_ratsche_positivkontrolle_des_detektors():
    rechnet = "def f(stoab_je_baustein):\n    if stoab_je_baustein:\n        return 1\n    return 0\n"
    verweigert = ("def f(stoab_je_baustein):\n    if stoab_je_baustein:\n"
                  "        raise faehigkeit_fehlt('x', True)\n    return 0\n")
    assert _verzweigungen(rechnet) == [False]
    assert _verzweigungen(verweigert) == [True]


# --------------------------------------------------------------------------- #
# Die Liste der ausgesetzten Tests
# --------------------------------------------------------------------------- #

def test_die_liste_der_ausgesetzten_tests_ist_festgehalten():
    liste = rueckbau.ausgesetzt()
    assert len(liste) == ANZAHL_AUSGESETZT
    assert liste == sorted(set(liste)), "sortiert und ohne Dubletten"
    for kennung in liste:
        datei = kennung.split("::", 1)[0]
        assert (REPO / datei).is_file(), kennung
        assert not datei.endswith("test_rueckbau_fall2.py"), "der Rueckbau setzt sich nicht selbst aus"


def test_jede_kennung_der_liste_gibt_es_in_der_suite():
    """Die Suite eigens gesammelt (ohne die Liste abzuwaehlen ist das nicht
    moeglich, also gegen die Meldung des Sammelns): Nennt die Liste eine
    Kennung, die es nicht gibt, bricht das Sammeln mit Exit 4 und der
    benannten Meldung ab."""
    import subprocess
    import sys

    ergebnis = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider",
         "-p", "no:xdist", str(REPO / "tests")],
        capture_output=True, text=True, cwd=REPO)
    assert ergebnis.returncode == 0, (ergebnis.stdout[-600:], ergebnis.stderr[-600:])
    assert f"{ANZAHL_AUSGESETZT} deselected" in ergebnis.stdout


def test_die_mechanik_trennt_ausgesetzte_von_unbekannten_kennungen():
    stellen, ohne_test = rueckbau.teile(["a::x", "b::y", "c::z"], ["b::y", "d::fehlt"])
    assert (stellen, ohne_test) == ([1], ["d::fehlt"])
    assert rueckbau.ausgesetzt(REPO / "tests" / "gibt_es_nicht.txt") == []


def test_jeder_lauf_nennt_die_zahl_der_ausgesetzten_tests(tmp_path):
    liste = tmp_path / "liste.txt"
    liste.write_text("# Kommentar\n\ntests/test_a.py::test_x\ntests/test_b.py::test_y\n")
    assert rueckbau.ausgesetzt(liste) == ["tests/test_a.py::test_x", "tests/test_b.py::test_y"]
    (zeile,) = rueckbau.bericht(liste)
    assert "2 Tests ausgesetzt" in zeile and "A-K2" in zeile
    assert rueckbau.bericht(tmp_path / "fehlt.txt") == []
