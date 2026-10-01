"""Anhaengen an die Ordnungslinie: Folge vor der Wahl, Uhr des Aufrufs, eine Sperre.

Befunde der blinden Pruefrunde I:

* I03/I15/I19 (mittel, derselbe Fund aus drei Linsen): Die Folge einer
  Erklaerung war erst lesbar, NACHDEM das Glied gezeichnet und unwiderruflich
  angehaengt war; "vor der Wahl die Folge lesen" war nicht ausfuehrbar.
  Invariante: Es gibt einen Aufruf, der fuer genau dieses Glied die Folge jeder
  Erklaerung nennt und nichts schreibt (``ordnung --vorschau``), und er nennt
  dieselbe Folge wie danach das Anhaengen (``==``).
* I04 (niedrig): ``--eingetragen-am`` in der Zukunft wurde angenommen.
  Invariante: Ein Glied wird nicht spaeter datiert als die Uhr des Aufrufs.
* I18 (mittel): Zwei gleichzeitige ``ordnung`` auf derselben Spitze endeten
  beide mit Exit 0 und legten zwei Glieder derselben Nummer ab (die
  Exklusivitaet wirkte je Dateiname, der den Hash trug). Invariante: Lesen der
  Spitze, Pruefen des Vorgaengers und Anhaengen geschehen unter EINER Sperre;
  von zwei gleichzeitigen Eintraegen gelingt genau einer, der andere wird
  benannt verweigert, und die Linie bleibt ladbar; ein zweites Glied derselben
  Nummer entsteht auch auf einem Weg ohne die Sperre nicht (Name = Nummer).
  Gemessen auf 9fa1538 (Subprozesse, gemeinsamer Start): 20 von 20 Runden
  legten zwei Glieder der Nummer 2 ab, in 5 davon meldeten beide Exit 0.

Mutationsproben (Rueckmeldung der Runde): die Vorschau schreibt die Sicht ->
``test_vorschau_*`` rot; Obergrenze der Uhr entfernt -> ``test_uhr_*`` rot;
Sperre durch einen leeren Kontext ersetzt -> ``test_gleichzeitig_*`` rot;
Dateiname wieder mit Hash -> ``test_ohne_sperre_*`` rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

import rechner_pipeline
from rechner_pipeline.gates import stand_belegen
from rechner_pipeline.gates._common import schreibe_exklusiv
from rechner_pipeline.models import ordnungslinie as ol
from tests.test_ordnungslinie_erklaerung import _anhaengen, _fp, _ordnung, _schluessel
from tests.zeichnung_fixture import VA, VORSTAND_SCHLUESSEL_DATEI, linie_anlegen


def _baum(wurzel: Path) -> dict:
    """Jede Datei unter ``wurzel`` (auch Punktdateien) mit ihren Bytes."""
    return {p.relative_to(wurzel).as_posix(): p.read_bytes()
            for p in sorted(wurzel.rglob("*")) if p.is_file()}


def _spitze(linie: Path) -> dict:
    glieder, fehler = ol.lade_linie_strukturell_zur_anzeige(linie)
    assert not fehler, fehler
    return glieder[-1]


def _mindernde_ordnung(tmp_path: Path) -> Path:
    """Die Ordnung des naechsten Glieds: der Vorstand wechselt den Schluessel,
    dem Aktuariat wird A-T1 entzogen — zwei geminderte Rollen."""
    o2 = _ordnung(tmp_path)
    o2["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(
        _schluessel(tmp_path / "aussen" / "vorstand-neu.key"))
    o2["rollen"][VA]["gates"] = [g for g in o2["rollen"][VA]["gates"] if g != "A-T1"]
    datei = tmp_path / "o2.json"
    datei.write_text(json.dumps(o2, sort_keys=True), encoding="utf-8")
    return datei


def _ordnung_args(linie: Path, datei: Path, erklaerung: dict, *extra: str) -> list:
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(datei),
            "--vorgaenger", _spitze(linie)["glied_sha256"], *extra]
    for rolle, wert in erklaerung.items():
        argv += ["--fruehere-zeichnungen", f"{rolle}={wert}"]
    return argv


# --------------------------------------------------------------------------- #
# I03: die Vorschau
# --------------------------------------------------------------------------- #


def test_vorschau_schreibt_nichts_und_nennt_dieselbe_folge_wie_das_anhaengen(tmp_path):
    """Ohne Erklaerung und ohne Schluessel: die geminderten Rollen und je Rolle
    die Folge BEIDER Erklaerungen; der ganze Linienbereich ist danach
    byte-gleich (kein Glied, keine Sicht, keine Tempdatei, keine Sperrdatei).
    Mit Erklaerung: dieselbe Folge (``==``) wie danach das echte Anhaengen.
    Rot auf 9fa1538: ``--vorschau`` gab es nicht."""
    linie = linie_anlegen(tmp_path)
    datei = _mindernde_ordnung(tmp_path)
    vorher = _baum(linie)
    ohne = stand_belegen.main(_ordnung_args(linie, datei, {}, "--vorschau"))
    assert ohne.exit_code == 0, ohne.errors
    assert _baum(linie) == vorher
    s = ohne.summary
    assert s["vorschau"] is True and s["geschrieben"] is False and s["nummer"] == 2
    assert s["geminderte_rollen"] == sorted([VA, ol.WURZELROLLE])
    assert s["erklaerung_fehlt"] == s["geminderte_rollen"]
    assert "fruehere_zeichnungen" not in s
    assert set(s["folgen"][ol.WURZELROLLE]) == set(s["folgen"][VA]) == set(ol.ERKLAERUNGEN)
    assert "jeder Fallauftrag (A-M6)" in s["folgen"][ol.WURZELROLLE]["verfallen"]
    assert s["folgen"][VA]["gueltig"].startswith("gueltig: Abnahmen ['A-T1']")
    wahl = {ol.WURZELROLLE: "verfallen", VA: "gueltig"}
    mit = stand_belegen.main(_ordnung_args(linie, datei, wahl, "--vorschau"))
    assert mit.exit_code == 0, mit.errors
    assert _baum(linie) == vorher
    assert mit.summary["erklaerung_fehlt"] == []
    assert mit.summary["folgen"] == {r: {w: s["folgen"][r][w]} for r, w in wahl.items()}
    echt = stand_belegen.main(_ordnung_args(
        linie, datei, wahl, "--vorstand-schluessel", str(tmp_path / VORSTAND_SCHLUESSEL_DATEI)))
    assert echt.exit_code == 0, echt.errors
    assert echt.summary["fruehere_zeichnungen"] == mit.summary["fruehere_zeichnungen"]
    assert echt.summary["aenderung"] == mit.summary["aenderung"]


def test_vorschau_prueft_wie_das_anhaengen(tmp_path):
    """Die Vorschau haelt dieselben Vorbedingungen wie das Anhaengen (Spitze,
    fremde Erklaerung) und schreibt auch dann nichts; das Anhaengen ohne
    Erklaerung nennt die Vorschau als Weg."""
    linie = linie_anlegen(tmp_path)
    datei = _mindernde_ordnung(tmp_path)
    vorher = _baum(linie)
    falsch = stand_belegen.main(["ordnung", "--linie", str(linie), "--ordnung", str(datei),
                                 "--vorgaenger", "ab" * 32, "--vorschau"])
    assert falsch.exit_code != 0 and "nicht die Spitze" in falsch.errors[0]["message"]
    fremd = stand_belegen.main(_ordnung_args(linie, datei, {"mensch/rechenkern": "gueltig"},
                                             "--vorschau"))
    assert fremd.exit_code != 0 and "nicht mindert" in fremd.errors[0]["message"]
    assert _baum(linie) == vorher
    ohne = stand_belegen.main(_ordnung_args(
        linie, datei, {}, "--vorstand-schluessel", str(tmp_path / VORSTAND_SCHLUESSEL_DATEI)))
    assert ohne.exit_code != 0
    assert "--vorschau" in ohne.errors[0]["message"], ohne.errors
    assert sorted(p.name for p in (linie / ol.VERZEICHNIS).iterdir()) == ["0001.json"]


# --------------------------------------------------------------------------- #
# I04: nicht spaeter als die Uhr des Aufrufs
# --------------------------------------------------------------------------- #

UHR = "2026-10-01T12:00:00+00:00"


@pytest.mark.parametrize("eingetragen,angenommen", [
    ("2026-10-01T12:00:00.000001+00:00", False),     # eine Mikrosekunde nach der Uhr
    ("2026-10-01T12:00:00+00:00", True),             # genau die Uhr
    ("2026-10-01T14:00:00+02:00", True),             # dieselbe Zeit, andere Zone
    ("2027-10-01T12:00:00+00:00", False),            # der Fund: ein Jahr zu spaet
    ("2026-10-01T07:59:59.999999+00:00", False),     # vor der Spitze (Glied 1: 08:00)
])
def test_uhr_ein_glied_liegt_zwischen_spitze_und_uhr_des_aufrufs(tmp_path, monkeypatch,
                                                                  eingetragen, angenommen):
    """Grenzen in beide Richtungen; die Uhr ueber die Naht des Moduls
    (``stand_belegen.utc_now``). Rot auf 9fa1538: die Zeitpunkte nach der Uhr
    wurden angenommen."""
    linie = linie_anlegen(tmp_path)
    monkeypatch.setattr(stand_belegen, "utc_now", lambda: UHR)
    o2 = _ordnung(tmp_path)
    o2["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI], eingetragen=eingetragen)
    assert (ergebnis.exit_code == 0) == angenommen, (ergebnis.errors, ergebnis.summary)
    if not angenommen and eingetragen > UHR:
        assert "nach der Uhr des Aufrufs" in ergebnis.errors[0]["message"], ergebnis.errors


def test_uhr_ohne_angabe_ist_das_glied_auf_die_uhr_datiert(tmp_path, monkeypatch):
    linie = linie_anlegen(tmp_path)
    monkeypatch.setattr(stand_belegen, "utc_now", lambda: UHR)
    o2 = _ordnung(tmp_path)
    o2["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    assert _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={},
                      vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI]).exit_code == 0
    assert _spitze(linie)["eingetragen_am"] == UHR


# --------------------------------------------------------------------------- #
# I18: eine Sperre, und je Nummer genau ein Glied
# --------------------------------------------------------------------------- #

_KIND = r'''
import os, sys, time
bereit, start = sys.argv[1], sys.argv[2]
from rechner_pipeline.gates import stand_belegen
from rechner_pipeline.gates._common import run_command
open(bereit, "w").close()
while not os.path.exists(start):
    time.sleep(0.0005)
sys.exit(run_command(stand_belegen.main, sys.argv[3:]))
'''


def _gleichzeitig(tmp_path: Path, runde: int) -> tuple:
    basis = tmp_path / f"runde-{runde}"
    linie = linie_anlegen(basis)
    o = _ordnung(basis)
    dateien = []
    for name in ("mensch/revision", "mensch/pruefung"):
        o2 = json.loads(json.dumps(o))
        o2["rollen"][name] = {"schluessel_sha256": hashlib.sha256(name.encode()).hexdigest(),
                              "schluesselklasse": "simulation", "gates": []}
        datei = basis / f"{name.split('/')[1]}.json"
        datei.write_text(json.dumps(o2, sort_keys=True), encoding="utf-8")
        dateien.append(datei)
    paket = str(Path(rechner_pipeline.__file__).resolve().parents[1])
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1",
           "PYTHONPATH": os.pathsep.join([paket, os.environ.get("PYTHONPATH", "")])}
    start = basis / "start"
    spitze = _spitze(linie)["glied_sha256"]
    kinder = []
    for k, datei in enumerate(dateien):
        kinder.append(subprocess.Popen(
            [sys.executable, "-c", _KIND, str(basis / f"bereit-{k}"), str(start), "ordnung",
             "--linie", str(linie), "--ordnung", str(datei), "--vorgaenger", spitze,
             "--vorstand-schluessel", str(basis / VORSTAND_SCHLUESSEL_DATEI)],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=str(basis)))
    frist = time.monotonic() + 120
    while not all((basis / f"bereit-{k}").exists() for k in range(2)):
        assert time.monotonic() < frist, "die Prozesse wurden nicht bereit"
        time.sleep(0.01)
    start.write_text("los", encoding="utf-8")
    ergebnisse = []
    for kind in kinder:
        out, err = kind.communicate(timeout=120)
        ergebnisse.append((kind.returncode, json.loads(out) if out.strip() else {"stderr": err}))
    return linie, basis, ergebnisse


@pytest.mark.parametrize("runde", range(3))
def test_gleichzeitig_genau_einer_gelingt_und_die_linie_bleibt_ladbar(tmp_path, runde):
    """Zwei echte Prozesse, gemeinsamer Start, dieselbe Spitze, verschiedene
    Ordnungen: genau einer Exit 0, der andere benannt verweigert ("nicht die
    Spitze" — er hat die neue Spitze unter der Sperre gelesen), unter
    ``ordnung/`` genau ``0001.json`` und ``0002.json``, die Linie laedt mit
    dem Ring. Rot auf 9fa1538 in 20 von 20 gemessenen Runden (zwei Glieder der
    Nummer 2)."""
    linie, basis, ergebnisse = _gleichzeitig(tmp_path, runde)
    codes = sorted(code for code, _ in ergebnisse)
    assert codes == [0, 20], ergebnisse
    [verweigert] = [aus for code, aus in ergebnisse if code != 0]
    assert "nicht die Spitze" in verweigert["errors"][0]["message"], verweigert
    assert sorted(p.name for p in (linie / ol.VERZEICHNIS).iterdir()) == ["0001.json", "0002.json"]
    schluessel = (basis / VORSTAND_SCHLUESSEL_DATEI).read_bytes()
    glieder, fehler = ol.lade_linie(linie, ring={hashlib.sha256(schluessel).hexdigest():
                                                 schluessel})
    assert fehler == [] and len(glieder) == 2, fehler


def test_ohne_sperre_entsteht_kein_zweites_glied_derselben_nummer(tmp_path, monkeypatch):
    """Ein Weg OHNE die Sperre: Zwischen dem Lesen der Spitze und dem Anhaengen
    legt ein anderer Schreiber ein richtig gezeichnetes Glied 2 ab. Das
    Anhaengen wird benannt verweigert, unter ``ordnung/`` liegt genau ein
    Glied 2, und die Linie laedt. Rot auf 9fa1538: zwei Glieder der Nummer 2,
    Exit 0, Linie unladbar."""
    linie = linie_anlegen(tmp_path)
    schluessel = (tmp_path / VORSTAND_SCHLUESSEL_DATEI).read_bytes()
    eins = _spitze(linie)
    fremd = _ordnung(tmp_path)
    fremd["rollen"]["mensch/pruefung"] = {"schluessel_sha256": "cd" * 32,
                                         "schluesselklasse": "simulation", "gates": []}
    zuvor = ol.baue_glied(json.dumps(fremd, sort_keys=True).encode(), nummer=2,
                          vorgaenger=eins["glied_sha256"], eingetragen_am=eins["eingetragen_am"],
                          vorstand=(schluessel, "simulation"), vorher=ol.ordnung_aus(eins))
    echt = ol.neues_glied

    def mit_wettlauf(*args, **kwargs):
        glied = echt(*args, **kwargs)
        schreibe_exklusiv(linie / ol.VERZEICHNIS / ol.dateiname(zuvor),
                          json.dumps(zuvor, sort_keys=True).encode("utf-8"))
        return glied

    monkeypatch.setattr(ol, "neues_glied", mit_wettlauf)
    monkeypatch.setattr(stand_belegen, "sperre_der_ordnung", lambda linie: contextlib.nullcontext(),
                        raising=False)
    o2 = _ordnung(tmp_path)
    o2["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code != 0, ergebnis.summary
    assert "liegt schon" in ergebnis.errors[0]["message"], ergebnis.errors
    glieder, fehler = ol.lade_linie(linie, ring={hashlib.sha256(schluessel).hexdigest():
                                                 schluessel})
    assert fehler == [] and [g["glied_sha256"] for g in glieder][-1] == zuvor["glied_sha256"]


def test_ratsche_der_name_eines_glieds_ist_seine_nummer(tmp_path):
    """Ratsche an der Naht: Der Name haengt nur an der Nummer (zwei
    verschiedene Glieder derselben Nummer haben denselben Namen); der Leser
    nimmt ein Glied unter einem anderen Namen nicht auf (Positivkontrolle:
    unter seinem Namen laedt es)."""
    linie = linie_anlegen(tmp_path)
    eins = _spitze(linie)
    anders = dict(eins, glied_sha256="ff" * 32)
    assert ol.dateiname(eins) == ol.dateiname(anders) == "0001.json"
    assert ol.dateiname({"nummer": 12, "glied_sha256": "x"}) == "0012.json"
    pfad = linie / ol.VERZEICHNIS / "0001.json"
    alt = pfad.with_name(f"0001-{eins['glied_sha256']}.json")
    pfad.rename(alt)
    glieder, fehler = ol.lade_linie(linie, ring={})
    assert glieder == [] and any("Dateiname passt nicht" in f for f in fehler), fehler
    alt.rename(pfad)
    assert ol.lade_linie(linie, ring={})[1] == []
