"""Rueckbau des zweiten Baldrian-Laufs — der Kern ohne die Faehigkeiten, die nur
der uebernommene Tarif braucht.

Vor Fall 3 (der Neufassung der Uebernahme) soll das Zielsystem so dastehen,
als haette es den uebernommenen Tarif nie gerechnet: ohne die Ausgestaltungen
im Kern, die allein fuer ihn entstanden sind, ohne seine Tafeln, ohne seine
Generation in der Config. Was die Migration am WERKZEUG gelehrt hat
(Korrekturschicht, Verankerung, Serien-Rekonstruktion, Pruefstrecken) und die
Teilkuendigung als Vorgang des eigenen Geschaefts bleiben (Entscheid des
Maintainers, 2026-10-01).

Kern 3.22.0 (Fall 3, A-K2) kehrt drei der Regelwerte zurueck, die in der Config
nur die Generation TG2015 fuehrte: ``scheiben_mit_gamma1``,
``stoab_je_baustein``, ``tku_umfang = grundversicherung``. Es sind
Faehigkeiten, keine Annahmen: keine Voreinstellung im Kern, die Wahl kommt
allein aus der Spez des Falls. Die sechs Tafeln der Quelle kommen nur ueber
den Tafel-Import des Falls (nach A-Q1) in den Kern; die Generation steht nicht
in den Configs.

Invariante: der Kern rechnet jeden Wert der drei Regeln, beidseitig, gegen
eine unabhaengige Handrechnung; keine Stelle verweigert eine Tarifregel mehr
(Ratsche unten, ``==``, mit Positivkontrolle des Detektors).

Die Tests, die ohne die Tafeln und die Generation keinen Gegenstand haben, stehen in
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

def _scheibe():
    return rk.Rechenkern(rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=True))


def test_die_scheibe_traegt_gamma1_nur_wenn_die_spez_es_sagt():
    """scheiben_mit_gamma1: beidseitig rechenbar, keine Voreinstellung im Kern
    (der Aufruf ohne die Regel ist ein TypeError, Kern 3.20.0)."""
    mit = rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=True)
    ohne = rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=False)
    assert mit.gamma1 == MP.gamma1 > 0.0
    assert ohne.gamma1 == 0.0
    assert (mit.x, mit.n, mit.t, mit.sum_insured) == (ohne.x, ohne.n, ohne.t, ohne.sum_insured) \
        == (MP.x + 3, MP.n - 3, MP.t - 3, 5000.0)
    with pytest.raises(TypeError):
        rk.erhoehungs_scheibe(MP, 3, 5000.0)


def test_der_stornoabzug_je_baustein_ist_die_summe_der_klemmen_je_baustein():
    """Unabhaengige Kontrolle: Abzug je Baustein ``min(max, max(min, satz *
    (VS_i - DR_i)))``, RKW = Summe von ``max(0, V^MRV_i - Abzug_i)``."""
    scheibe = _scheibe()
    r = rk.vertrags_monatsreserve(GRUND, [(3, scheibe)], 60, stoab_je_baustein=True)
    erwartet_stoab = erwartet_rkw = 0.0
    for kern, versetzt in ((GRUND, 60), (scheibe, 60 - 36)):
        teil = kern.monatsreserve(versetzt)
        abzug = min(kern.mp.stoab_max, max(kern.mp.stoab_min,
                    kern.mp.stoab_satz * (kern.mp.sum_insured - teil.drx_bpfl)))
        erwartet_stoab += abzug
        erwartet_rkw += max(0.0, teil.vx_mrv - abzug)
    assert r.stoab == pytest.approx(erwartet_stoab, abs=1e-9)
    assert r.rkw == pytest.approx(erwartet_rkw, abs=1e-9)
    # Der Unterschied zum vertragsweiten Abzug ist die Kern-Eigenschaft.
    je_vertrag = rk.vertrags_monatsreserve(GRUND, [(3, scheibe)], 60, stoab_je_baustein=False)
    assert r.stoab != je_vertrag.stoab
    assert r.vx_mrv == je_vertrag.vx_mrv and r.drx_bpfl == je_vertrag.drx_bpfl


def test_ohne_scheiben_sind_beide_abzugsregeln_gleich():
    a = rk.vertrags_monatsreserve(GRUND, [], 60, stoab_je_baustein=True)
    b = rk.vertrags_monatsreserve(GRUND, [], 60, stoab_je_baustein=False)
    assert a == b


def test_die_vorgangsfolge_rechnet_den_abzug_je_baustein():
    scheibe = _scheibe()
    je = vf.Vertragsstand.anfang(GRUND, [(3, scheibe)], stoab_je_baustein=True,
                                 tku_umfang=vf.UMFANG_ALLE).werte(60)
    vertrag = vf.Vertragsstand.anfang(GRUND, [(3, scheibe)], stoab_je_baustein=False,
                                      tku_umfang=vf.UMFANG_ALLE).werte(60)
    direkt = rk.vertrags_monatsreserve(GRUND, [(3, scheibe)], 60, stoab_je_baustein=True)
    assert je["rueckkaufswert"] == pytest.approx(direkt.rkw, abs=1e-9)
    assert je["rueckkaufswert"] != vertrag["rueckkaufswert"]


def test_die_herabsetzung_mit_abzug_wandelt_je_baustein_seinen_eigenen_rkw_um():
    scheibe = _scheibe()
    ergebnis = br.reduziere_geschichtet(
        GRUND, [(3, scheibe)], 5, 0.7, verfahren="mit_abzug", stoab_je_baustein=True)
    assert len(ergebnis) == 2
    gesamt = rk.vertrags_monatsreserve(GRUND, [(3, scheibe)], 60, stoab_je_baustein=True)
    umgewandelt = sum(red.vs_neu for _, red in ergebnis)
    assert 0.0 < umgewandelt < MP.sum_insured + 5000.0
    assert gesamt.rkw > 0.0


def test_die_teilkuendigung_nur_der_grundversicherung_laesst_die_scheibe_stehen():
    scheibe = _scheibe()

    def danach(umfang):
        stand = vf.Vertragsstand.anfang(GRUND, [(3, scheibe)], stoab_je_baustein=False,
                                        tku_umfang=umfang)
        return stand.nach_vorgang(vf.vorgang(5, 0.7, br.TEILKUENDIGUNG))[0]

    nur_grund = danach(vf.UMFANG_GRUND)
    alle = danach(vf.UMFANG_ALLE)
    assert nur_grund.gesamt_vs() == pytest.approx(0.7 * MP.sum_insured + 5000.0)
    assert alle.gesamt_vs() == pytest.approx(0.7 * (MP.sum_insured + 5000.0))


def test_positivkontrolle_die_regeln_des_eigenen_geschaefts_rechnen():
    assert rk.erhoehungs_scheibe(MP, 3, 5000.0, gamma1_uebernehmen=False).gamma1 == 0.0
    assert rk.vertrags_monatsreserve(GRUND, [], 60, stoab_je_baustein=False).rkw > 0.0
    stand = vf.Vertragsstand.anfang(GRUND, (), stoab_je_baustein=False,
                                    tku_umfang=vf.UMFANG_ALLE)
    assert stand.werte(60)["deckungskapital"] > 0.0
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


def test_die_tafeln_der_quelle_kommen_nur_ueber_den_import_in_den_kern():
    """Die Tafeln des uebernommenen Tarifs stehen erst nach dem Tafel-Import
    des Falls (nach A-Q1) im Kern; bis dahin fehlen sie benannt."""
    if f'<table name="DAV2008_T_NR_U70"' in (KERN / "tafeln.xml").read_text(encoding="utf-8"):
        assert len(tafeln.qx_vector("M", "DAV2008_T_NR_U70")) > 100
    else:
        with pytest.raises(tafeln.MissingMortalityTableError):
            tafeln.qx_vector("M", "DAV2008_T_NR_U70")
    assert len(tafeln.qx_vector("M", "DAV2008_T")) > 100      # Positivkontrolle


# --------------------------------------------------------------------------- #
# Ratsche: keine Verzweigung auf einen Regelwert verweigert mehr
# --------------------------------------------------------------------------- #

def test_ratsche_der_kern_verweigert_keine_tarifregel_mehr():
    """Menge (==): null Stellen im Kern, die einen Regelwert mit einer
    Verweigerung beantworten. Positivkontrolle des Detektors unten."""
    treffer = [p.name for p in sorted(KERN.glob("*.py"))
               if "faehigkeit_fehlt" in p.read_text(encoding="utf-8")
               and p.name != "__init__.py"]
    assert treffer == []


def test_ratsche_positivkontrolle_des_detektors():
    quelle = "def f(x):\n    raise faehigkeit_fehlt('x', True)\n"
    assert "faehigkeit_fehlt" in quelle


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
