"""Beleg und Sicht der Abnahme-Produzenten unter Ausfaellen (Runde G, Linse betrieb-ausfall).

Die Pruefrunde G stoerte jede Schreibstelle der Produzenten, deren Belege
ein Mensch zeichnet, einzeln (ENOSPC, Prozessende) und verglich mit dem
ungestoerten Lauf. Fuenf Funde, eine Klasse und vier Nachbarn:

* G26 "Beleg neu, Sicht alt" (Klasse): Jeder Produzent schrieb erst den
  Beleg, dann die Sicht; fiel die Sicht aus, zeichnete das Gate die neue
  Vorlage, die der Mensch nie gesehen hat. Invariante: Gezeichnet wird nur
  eine Vorlage, deren Sicht am festen Ort byte-gleich die aus genau dieser
  Vorlage erzeugte ist. EINE Regel im Gate beim Zeichnen einer Annahme
  (``gates.sichten.sicht_fehler``), ein Register (``gates.sichten.SICHTEN``).
  Dazu: Ein Ein-/Ausgabefehler eines Produzenten ist ein benanntes Ergebnis,
  kein Traceback; ``stand_belegen ordnung`` zieht die Sicht eines schon
  liegenden Glieds nach, statt mit Exit 20 zu enden.
* G24: Fehlt das Archiv der T-Box, behauptete die naechste Vorlage still
  "Erstabnahme" und das Gate zeichnete A-O1 ohne Archivkopie.
* G25: Eine vorhandene, aber nicht lesbare oder nicht pruefbare Bindung
  des alten Anfangsbestands wurde zu "erste Abnahme dieser Ablage".
* G27: Ein Schreibrest von ``linie.json`` sperrte die Wiederholung von
  ``stand_belegen linie`` ("nicht leer").
* G28: Ein Ein-/Ausgabefehler bei Provenienz oder erster Umbenennung liess
  die Vorbereitung ``daten.neu-<zeit>`` ungenannt liegen.

Jeder Test faehrt die echten Kommandos und stoert genau einen Schreibschritt
auf der Ebene des Betriebssystems (``os.replace``/``os.link``/``os.rename``/
``os.fsync``/``open`` mit ENOSPC); kein Pruefergebnis ist ersetzt.

Mutationsproben (Bauprotokoll in der Rueckgabe der Fix-Runde): Aufruf von
``sicht_fehler`` im Gate entfernt -> die Sicht-Tests rot; Archivpruefung im
Register entfernt -> der Archiv-Test rot; ``_vorher_tbox`` wieder mit
``continue`` -> rot; ``_vorher`` des Anfangsbestands wieder mit breitem
``except`` -> rot; Ruecksprung fuer ein liegendes Glied entfernt -> rot;
Schreibrest-Ausnahme in ``linie`` entfernt -> rot; Abraeumen in
``neuaufsetzen`` entfernt -> rot; Dekorator eines Produzenten entfernt -> rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import contextlib
import datetime as dt
import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import rechner_pipeline
from rechner_pipeline.gates import gate_entscheid, kernstand_belegen, stand_belegen
from rechner_pipeline.gates import tarifwerk_belegen
from rechner_pipeline.gates._common import Exit
from rechner_pipeline.models import anfangsbestand as ab
from rechner_pipeline.models import fallauftrag as fa
from rechner_pipeline.models import kernabnahme as ka
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models import tarifwerkabnahme as tw
from rechner_pipeline.models.zeichnung import ABBRUCH_GATE, AUFTRAG_GATE
from rechner_pipeline.ontologie import tbox
from tests.zeichnung_fixture import (
    VORSTAND_SCHLUESSEL_DATEI,
    annahme_args,
    fallauftrag_zeichnen,
    linie_anlegen,
)

REPO = Path(__file__).resolve().parents[1]
SRC = Path(rechner_pipeline.__file__).resolve().parents[1]

SICHT = {"A-K2": ka.SICHT_RELATIV, "A-O1": stand_belegen.TBOX_SICHT_RELATIV,
         "A-T1": tw.SICHT_RELATIV}
BELEG = {"A-K2": ka.AENDERUNG_RELATIV, "A-O1": stand_belegen.TBOX_AENDERUNG_RELATIV,
         "A-T1": tw.AENDERUNG_RELATIV}


# --------------------------------------------------------------------------- #
# Helfer: Stoerung auf der Ebene des Betriebssystems
# --------------------------------------------------------------------------- #


def _enospc(ziel) -> OSError:
    return OSError(errno.ENOSPC, "kein Platz auf dem Geraet (Test)", os.fspath(ziel))


@contextlib.contextmanager
def _ausfall(monkeypatch, trifft, ops=("replace", "link")):
    """ENOSPC beim Einhaengen jedes Ziels, fuer das ``trifft(Path)`` gilt —
    an den Primitiven, durch die jeder Schreiber muss (Tempdatei daneben,
    dann ``os.replace`` bzw. ``os.link``)."""
    echt = {op: getattr(os, op) for op in ops}

    def mache(op):
        def gestoert(quelle, ziel, *a, **k):
            if trifft(Path(os.fspath(ziel))):
                raise _enospc(ziel)
            return echt[op](quelle, ziel, *a, **k)
        return gestoert

    with monkeypatch.context() as m:
        for op in ops:
            m.setattr(os, op, mache(op))
        yield


def _versuche(aufruf):
    """Der Produzent unter Ausfall: sein Ergebnis — oder (vor dem Fix) die
    Ausnahme, die er durchreichte."""
    try:
        return aufruf()
    except OSError as exc:
        return exc


def _ort(datei: Path):
    return lambda ziel: ziel.name == datei.name and ziel.parent == datei.parent


def _vorlegen(linie: Path, gate: str, begruendung: str):
    """Den Gegenstand im Linienbereich vorlegen (Produzent, kein Gate)."""
    if gate == "A-K2":
        return kernstand_belegen.main([
            "--linie", str(linie), "--repo-root", str(REPO), "--von", "HEAD",
            "--begruendung", begruendung])
    if gate == "A-T1":
        return tarifwerk_belegen.main([
            "--linie", str(linie), "--repo-root", str(REPO), "--von", "HEAD",
            "--begruendung", begruendung])
    vermerk = linie / "abgeleitet" / "tbox" / "vermerk.md"
    if not vermerk.is_file():
        vermerk.parent.mkdir(parents=True, exist_ok=True)
        vermerk.write_text("Erstabnahme der T-Box.\n", encoding="utf-8")
        (linie / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
            "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
            "verfasser_rolle": "mensch/aktuariat",
            "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                        "begruendung": "Erstabnahme (Suite)"}]}), encoding="utf-8")
    return stand_belegen.main([
        "tbox", "--linie", str(linie), "--repo-root", str(REPO),
        "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", begruendung])


def _zeichnen(linie: Path, gate: str, entscheid: str = "angenommen"):
    argv = ["--linie", str(linie), "--gate", gate, "--entscheid", entscheid,
            "--entscheider", "verantwortung", "--begruendung", f"{gate} (Suite)",
            "--repo-root", str(REPO)]
    # Auch eine Ablehnung haelt den Ring: Sie liest die Kette, deren Annahmen
    # signiert sind; gezeichnet ist sie dann von der Rolle des Schluessels.
    argv += annahme_args(linie, fuer=None if gate == "A-T1" else gate)
    if entscheid == "abgelehnt":
        argv += ["--rolle", "mensch/architektur"]
    return gate_entscheid.main(argv)


def _snapshots(bereich: Path, gate: str):
    return sorted((bereich / "entscheide").glob(f"{gate}-*.json"))


def _verweigert_wegen_sicht(ergebnis) -> str:
    assert ergebnis.exit_code == Exit.FILE_CONTRACT, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "sicht", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "Vorlage neu erzeugen" in meldung, meldung
    return meldung


# --------------------------------------------------------------------------- #
# G26: Beleg neu, Sicht alt — die drei Gegenstaende des Codes
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("gate", ["A-K2", "A-O1", "A-T1"])
def test_beleg_neu_sicht_alt_zeichnet_das_gate_nicht(tmp_path, monkeypatch, gate):
    """Vorlage 1 mit Sicht 1, dann Vorlage 2 mit ausgefallener Sicht: Das Gate
    verweigert benannt; nach der Wiederholung des Produzenten zeichnet es.

    Mutationsprobe: in gate_entscheid den Aufruf von sichten.sicht_fehler
    entfernen -> das Gate zeichnet Vorlage 2 -> rot."""
    linie = linie_anlegen(tmp_path)
    assert _vorlegen(linie, gate, "erste Vorlage").exit_code == 0
    sicht = linie / SICHT[gate]
    alt = sicht.read_bytes()
    with _ausfall(monkeypatch, _ort(sicht)):
        _versuche(lambda: _vorlegen(linie, gate, "zweite Vorlage"))
    assert sicht.read_bytes() == alt
    assert "zweite Vorlage" in (linie / BELEG[gate]).read_text(encoding="utf-8")
    meldung = _verweigert_wegen_sicht(_zeichnen(linie, gate))
    assert SICHT[gate] in meldung
    assert _snapshots(linie, gate) == []
    # Die Wiederholung des Produzenten liefert den ungestoerten Zustand.
    assert _vorlegen(linie, gate, "zweite Vorlage").exit_code == 0
    ergebnis = _zeichnen(linie, gate)
    assert ergebnis.exit_code == 0, ergebnis.errors


def test_sicht_neu_beleg_alt_und_fehlende_sicht_zeichnet_das_gate_nicht(tmp_path):
    """Die Gegenrichtung (Sicht der zweiten Vorlage neben dem Beleg der
    ersten — der Zustand, den ein Produzent mit der Reihenfolge Sicht vor
    Beleg nach einem Ausfall am Beleg hinterliesse) und die fehlende Sicht:
    Die Regel haengt nicht an der Schreibreihenfolge."""
    linie = linie_anlegen(tmp_path)
    sicht = linie / tw.SICHT_RELATIV
    assert _vorlegen(linie, "A-T1", "zweite Vorlage").exit_code == 0
    zweite = sicht.read_bytes()
    assert _vorlegen(linie, "A-T1", "erste Vorlage").exit_code == 0
    sicht.write_bytes(zweite)
    _verweigert_wegen_sicht(_zeichnen(linie, "A-T1"))
    sicht.unlink()
    assert "fehlt" in _verweigert_wegen_sicht(_zeichnen(linie, "A-T1"))
    assert _snapshots(linie, "A-T1") == []
    # Eine Ablehnung zeichnet nichts ab und braucht die Sicht nicht.
    ablehnung = gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-T1", "--entscheid", "abgelehnt",
        "--entscheider", "aktuariat", "--begruendung", "Sicht fehlt",
        "--rolle", "agent/aktuariat", "--repo-root", str(REPO)])
    assert ablehnung.exit_code == 0, ablehnung.errors


# --------------------------------------------------------------------------- #
# G26: Anfangsbestand A-B3
# --------------------------------------------------------------------------- #


def _betriebszeichner():
    from rechner_pipeline.betrieb import tageslauf as tl

    return tl.betriebszeichner(tl.Ablage(Path("/nirgends")))


def _aufgebaute_ablage(wurzel: Path):
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.test_betrieb_tageslauf import _ablage

    ablage = _ablage(wurzel)
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 31))
    assert code == EXIT_OK and zeile["uebernommen"] is True
    return ablage


def _ab3(linie: Path):
    return gate_entscheid.main([
        "--linie", str(linie), "--gate", "A-B3", "--entscheid", "angenommen",
        "--entscheider", "betriebsverantwortung", "--begruendung", "Anfangsbestand geprueft",
        "--repo-root", str(REPO), *annahme_args(linie, rolle="mensch/betrieb",
                                                gates=["A-B3"], klasse="mensch")])


def test_a_b3_zeichnet_nicht_unter_der_sicht_einer_anderen_ablage(tmp_path, monkeypatch):
    from rechner_pipeline.betrieb import anfangsbestand as anf

    monkeypatch.setattr(anf, "_STANDARD_ANFANGSBESTAND", None)
    fremd = _aufgebaute_ablage(tmp_path / "daten-x")
    eigen = _aufgebaute_ablage(tmp_path / "daten")
    linie = linie_anlegen(tmp_path / "zeichnen", rolle="mensch/betrieb", gates=["A-B3"],
                          klasse="mensch")
    anf.belegen(fremd.wurzel, linie, _betriebszeichner())
    sicht = linie / ab.SICHT_RELATIV
    alt = sicht.read_bytes()
    with _ausfall(monkeypatch, _ort(sicht)):
        _versuche(lambda: anf.belegen(eigen.wurzel, linie, _betriebszeichner()))
    assert sicht.read_bytes() == alt
    beleg = json.loads((linie / ab.BELEG_RELATIV).read_text(encoding="utf-8"))
    assert beleg["ablage"]["name"] == "daten"
    _verweigert_wegen_sicht(_ab3(linie))
    anf.belegen(eigen.wurzel, linie, _betriebszeichner())
    ergebnis = _ab3(linie)
    assert ergebnis.exit_code == 0, ergebnis.errors


# --------------------------------------------------------------------------- #
# G26: Fallauftrag A-M6 und Fallabbruch A-M5
# --------------------------------------------------------------------------- #


def test_auftrag_und_abbruch_zeichnen_nur_die_gesehene_vorlage(tmp_path, monkeypatch):
    """Die Sicht nennt Auftrag "erste", gezeichnet wuerde "zweite": Der
    Vorstand verweigert benannt; ebenso der Abbruch der Programmleitung."""
    from rechner_pipeline.gates import fall_belegen
    from tests.e2e_fixture import bereite_pk1_fall

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    gesehen = []
    echt = fall_belegen.main
    with monkeypatch.context() as m:
        m.setattr(fall_belegen, "main", lambda argv: gesehen.append(list(argv)) or echt(argv))
        fallauftrag_zeichnen(fall, auftrag="erste Fassung des Auftrags")
    argv = gesehen[0]
    argv[argv.index("--auftrag") + 1] = "zweite Fassung des Auftrags"
    sicht = fall / fa.AUFTRAG_SICHT_RELATIV
    alt = sicht.read_bytes()
    with _ausfall(monkeypatch, _ort(sicht)):
        _versuche(lambda: fall_belegen.main(list(argv)))
    assert sicht.read_bytes() == alt
    assert "zweite Fassung" in (fall / fa.AUFTRAG_RELATIV).read_text(encoding="utf-8")

    def zeichne(gate, wer):
        return gate_entscheid.main([
            "--fall", str(fall), "--gate", gate, "--entscheid", "angenommen",
            "--entscheider", wer, "--begruendung", f"{gate} (Suite)",
            "--repo-root", str(REPO), *annahme_args(fall, fuer=gate)])

    vorher = _snapshots(fall, AUFTRAG_GATE)
    _verweigert_wegen_sicht(zeichne(AUFTRAG_GATE, "vorstand"))
    assert _snapshots(fall, AUFTRAG_GATE) == vorher
    assert fall_belegen.main(list(argv)).exit_code == 0
    ergebnis = zeichne(AUFTRAG_GATE, "vorstand")
    assert ergebnis.exit_code == 0, ergebnis.errors

    def abbruch(grund):
        return fall_belegen.main([
            "abbruch", "--fall", str(fall), "--repo-root", str(REPO), "--grund", grund,
            "--bestand", "bleibt beim abgebenden Haus", "--uebergabe", "an den Vorstand"])

    assert abbruch("erster Grund").exit_code == 0
    sicht = fall / fa.ABBRUCH_SICHT_RELATIV
    alt = sicht.read_bytes()
    with _ausfall(monkeypatch, _ort(sicht)):
        _versuche(lambda: abbruch("zweiter Grund"))
    assert sicht.read_bytes() == alt
    _verweigert_wegen_sicht(zeichne(ABBRUCH_GATE, "programmleitung"))
    assert _snapshots(fall, ABBRUCH_GATE) == []
    assert abbruch("zweiter Grund").exit_code == 0
    ergebnis = zeichne(ABBRUCH_GATE, "programmleitung")
    assert ergebnis.exit_code == 0, ergebnis.errors


# --------------------------------------------------------------------------- #
# G26: das Register und die eine Stelle im Gate (Ratschen)
# --------------------------------------------------------------------------- #


def test_das_register_der_sichten_ist_die_menge_der_gates_mit_sicht():
    """== gegen die Menge der Gates, deren Produzent eine Sicht schreibt:
    die vier Gegenstaende der Standabnahme (Tabelle in
    test_erstabnahme_linie, Positivkontrolle) und die zwei Vorlagen des
    Lebenslaufs. Dazu jede Konstante ``*SICHT_RELATIV`` im Paket — eine
    neue Sicht ohne Registereintrag wird hier rot."""
    from rechner_pipeline.gates import sichten
    from tests.test_erstabnahme_linie import TABELLE

    soll = {gate: sicht for _, _, sicht, gate, _, _, _ in TABELLE}
    soll[AUFTRAG_GATE] = fa.AUFTRAG_SICHT_RELATIV
    soll[ABBRUCH_GATE] = fa.ABBRUCH_SICHT_RELATIV
    assert len(soll) == 6
    assert {g: e.sicht_relativ for g, e in sichten.SICHTEN.items()} == soll
    konstanten = set()
    for datei in sorted((SRC / "rechner_pipeline").rglob("*.py")):
        for knoten in ast.parse(datei.read_text(encoding="utf-8")).body:
            if isinstance(knoten, ast.Assign) and isinstance(knoten.value, ast.Constant):
                for ziel in knoten.targets:
                    if isinstance(ziel, ast.Name) and ziel.id.endswith("SICHT_RELATIV"):
                        konstanten.add(knoten.value.value)
    assert konstanten == set(soll.values())
    # Jede Pflichtrolle, deren Beleg die Sicht traegt, ist eine Rolle des Gates.
    from rechner_pipeline.models.belegrollen import BELEGROLLEN

    for gate, eintrag in sichten.SICHTEN.items():
        rollen = {r for v in BELEGROLLEN[gate].values() for r in v}
        assert {rolle for rolle, _ in eintrag.belege} <= rollen, gate


def test_das_gate_prueft_die_sicht_an_genau_einer_stelle():
    """Statische Ratsche (AST): ``sicht_fehler`` wird in gate_entscheid genau
    einmal gerufen — die eine Stelle, durch die jede Annahme muss."""
    baum = ast.parse(Path(gate_entscheid.__file__).read_text(encoding="utf-8"))
    aufrufe = [k for k in ast.walk(baum) if isinstance(k, ast.Call)
               and isinstance(k.func, ast.Attribute) and k.func.attr == "sicht_fehler"]
    assert len(aufrufe) == 1


def test_der_produzent_schreibt_die_sicht_die_das_gate_erzeugt(tmp_path):
    """Positivkontrolle der Regel: Nach einem ungestoerten Lauf ist die Sicht
    am festen Ort byte-gleich die aus dem Beleg erzeugte (deterministisch,
    dieselbe Renderfunktion)."""
    from rechner_pipeline.gates import sichten

    linie = linie_anlegen(tmp_path)
    for gate in ("A-K2", "A-T1", "A-O1"):
        assert _vorlegen(linie, gate, "Vorlage").exit_code == 0
        eintrag = sichten.SICHTEN[gate]
        belege = {rolle: json.loads((linie / relativ).read_text(encoding="utf-8"))
                  for rolle, relativ in eintrag.belege}
        assert eintrag.rendere(belege).encode("utf-8") == (linie / SICHT[gate]).read_bytes()


# --------------------------------------------------------------------------- #
# G26 (zweiter Teil): ein Ein-/Ausgabefehler ist ein benanntes Ergebnis
# --------------------------------------------------------------------------- #


def _fsync_kaputt(monkeypatch):
    def kaputt(fd):
        raise OSError(errno.ENOSPC, "kein Platz auf dem Geraet (Test)")
    monkeypatch.setattr(os, "fsync", kaputt)


def _benannt(ergebnis):
    assert not isinstance(ergebnis, BaseException), f"durchgereicht: {ergebnis!r}"
    assert ergebnis.exit_code == Exit.INTERNAL, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "ein_ausgabe", ergebnis.errors
    assert "denselben Aufruf wiederholen" in ergebnis.errors[0]["message"]


@pytest.mark.parametrize("produzent", ["kernstand_belegen", "tarifwerk_belegen",
                                       "stand_belegen"])
def test_ein_ausfall_beim_schreiben_ist_benannt(tmp_path, monkeypatch, produzent):
    """ENOSPC am fsync jeder Schreibstelle: benanntes Ergebnis, kein Traceback.

    Mutationsprobe: den Dekorator am main des Produzenten entfernen -> die
    Ausnahme geht durch -> rot."""
    linie = linie_anlegen(tmp_path)
    with monkeypatch.context() as m:
        _fsync_kaputt(m)
        if produzent == "stand_belegen":
            ergebnis = _versuche(lambda: stand_belegen.main(
                ["linie", "--linie", str(tmp_path / "neue-linie")]))
        else:
            ergebnis = _versuche(lambda: _vorlegen(linie, {"kernstand_belegen": "A-K2",
                                                           "tarifwerk_belegen": "A-T1"}[produzent],
                                                   "Vorlage"))
    _benannt(ergebnis)


def test_ein_ausfall_beim_schreiben_der_fallvorlage_ist_benannt(tmp_path, monkeypatch):
    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import fall_belegen

    fall = tmp_path / "fall"
    anlegen(fall, scope="tarif")
    registrieren(fall, REPO / "tests" / "fixtures" / "pk1_am4_minimal"
                 / "pk1_am4_anonymisiert.xlsm")
    gesehen = []
    echt = fall_belegen.main
    with monkeypatch.context() as m:
        m.setattr(fall_belegen, "main", lambda argv: gesehen.append(list(argv)) or echt(argv))
        fallauftrag_zeichnen(fall)
    with monkeypatch.context() as m:
        _fsync_kaputt(m)
        ergebnis = _versuche(lambda: fall_belegen.main(gesehen[0]))
    _benannt(ergebnis)


def test_die_produzenten_der_abnahmebelege_beenden_einen_ausfall_benannt():
    """Statische Ratsche mit Positivkontrolle: Die Produzenten-Module, die das
    Register der Sichten nennt (aus seinem Feld ``werkzeug``), sind GENAU die
    Module unter gates/, deren ``main`` den Dekorator ``ein_ausgabe_benannt``
    traegt — und jedes davon schreibt in ``main`` (sonst waere die Menge leer
    gemessen)."""
    from rechner_pipeline.gates import sichten

    produzenten = {e.werkzeug.split()[0].rsplit(".", 1)[1]
                   for e in sichten.SICHTEN.values() if e.werkzeug.startswith(
                       "rechner_pipeline.gates.")}
    assert produzenten == {"kernstand_belegen", "stand_belegen", "tarifwerk_belegen",
                           "fall_belegen"}
    dekoriert = set()
    for datei in sorted((SRC / "rechner_pipeline" / "gates").glob("*.py")):
        for knoten in ast.parse(datei.read_text(encoding="utf-8")).body:
            if isinstance(knoten, ast.FunctionDef) and knoten.name == "main" and any(
                    isinstance(d, ast.Call) and getattr(d.func, "id", None)
                    == "ein_ausgabe_benannt" for d in knoten.decorator_list):
                dekoriert.add(datei.stem)
    assert dekoriert == produzenten


# --------------------------------------------------------------------------- #
# G26 (dritter Teil): die Sicht der Ordnungslinie ist nachziehbar
# --------------------------------------------------------------------------- #


def test_ordnung_zieht_nach_einem_ausfall_die_sicht_nach_ohne_zweites_glied(
        tmp_path, monkeypatch):
    """Mutationsprobe: den Ruecksprung fuer ein schon liegendes Glied in
    stand_belegen.main entfernen -> Wiederholung Exit 20 -> rot."""
    linie = linie_anlegen(tmp_path)
    ordnung = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"]["mensch/zusatz"] = {"schluessel_sha256": "ab" * 32,
                                          "schluesselklasse": "mensch", "gates": ["A-M1"]}
    datei = tmp_path / "ordnung-2.json"
    datei.write_text(json.dumps(ordnung, sort_keys=True), encoding="utf-8")
    [wurzel], _ = ol.lade_linie_strukturell_zur_anzeige(linie)
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(datei),
            "--vorgaenger", wurzel["glied_sha256"],
            "--vorstand-schluessel", str(tmp_path / VORSTAND_SCHLUESSEL_DATEI),
            "--eingetragen-am", "2026-10-01T09:00:00+00:00"]
    sicht = linie / "abgeleitet" / "ordnung" / "linie.md"
    with _ausfall(monkeypatch, _ort(sicht)):
        _versuche(lambda: stand_belegen.main(list(argv)))
    glieder, _ = ol.lade_linie_strukturell_zur_anzeige(linie)
    assert len(glieder) == 2 and "## Glied 2" not in sicht.read_text(encoding="utf-8")
    for _ in range(2):   # derselbe Aufruf, auch ein zweites Mal
        ergebnis = stand_belegen.main(list(argv))
        assert ergebnis.exit_code == 0, ergebnis.errors
        assert ergebnis.summary["bereits_vorhanden"] is True
        glieder, _ = ol.lade_linie_strukturell_zur_anzeige(linie)
        assert len(glieder) == 2
        assert sicht.read_text(encoding="utf-8") == stand_belegen.rendere_ordnungslinie(glieder)
    # Ein ANDERER Vorgaenger ist kein Wiederholungsaufruf.
    anders = list(argv)
    anders[anders.index("--vorgaenger") + 1] = "keiner"
    assert stand_belegen.main(anders).exit_code == Exit.FILE_CONTRACT


# --------------------------------------------------------------------------- #
# G24: das Archiv der T-Box
# --------------------------------------------------------------------------- #


def _archiv(bereich: Path) -> Path:
    return bereich / stand_belegen.TBOX_ARCHIV_RELATIV


def test_ohne_archivkopie_zeichnet_das_gate_a_o1_nicht_und_die_wiederholung_heilt(
        tmp_path, monkeypatch):
    """ENOSPC beim Archiv: A-O1 wird nicht gezeichnet; der erneute Lauf des
    Produzenten liefert byte-gleich den Zustand des ungestoerten Laufs. Liegt
    der Beleg am festen Ort, aber seine Archivkopie nicht (ein Lauf vor dem
    Fix, eine Hand), verweigert das Gate benannt.

    Mutationsprobe: die Archivpruefung im Register entfernen -> A-O1 wird
    ohne Archivkopie angenommen -> rot."""
    ungestoert = linie_anlegen(tmp_path / "ungestoert")
    assert _vorlegen(ungestoert, "A-O1", "Vorlage").exit_code == 0
    linie = linie_anlegen(tmp_path / "gestoert")
    with _ausfall(monkeypatch, lambda z: z.parent.name == "archiv"):
        _versuche(lambda: _vorlegen(linie, "A-O1", "Vorlage"))
    assert not list(_archiv(linie).glob("*.json"))
    ergebnis = _zeichnen(linie, "A-O1")
    assert ergebnis.exit_code == Exit.FILE_CONTRACT, ergebnis.errors
    assert _snapshots(linie, "A-O1") == []
    assert _vorlegen(linie, "A-O1", "Vorlage").exit_code == 0
    for relativ in (stand_belegen.TBOX_AENDERUNG_RELATIV, stand_belegen.TBOX_SICHT_RELATIV):
        assert (linie / relativ).read_bytes() == (ungestoert / relativ).read_bytes()
    assert sorted(p.name for p in _archiv(linie).iterdir()) == \
        sorted(p.name for p in _archiv(ungestoert).iterdir())
    # Beleg und Sicht am festen Ort, die Archivkopie fehlt: keine Zeichnung.
    [kopie] = _archiv(linie).glob("*.json")
    roh = kopie.read_bytes()
    kopie.unlink()
    ergebnis = _zeichnen(linie, "A-O1")
    assert ergebnis.exit_code == Exit.FILE_CONTRACT, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "sicht"
    assert "fehlt im Archiv" in ergebnis.errors[0]["message"], ergebnis.errors
    assert _snapshots(linie, "A-O1") == []
    kopie.write_bytes(roh)
    assert _zeichnen(linie, "A-O1").exit_code == 0


def test_fehlt_die_archivkopie_einer_annahme_ist_das_keine_erstabnahme(tmp_path):
    """Die Linie traegt eine angenommene A-O1, ihr gepinnter Beleg fehlt im
    Archiv: die naechste Vorlage verweigert benannt, statt "Erstabnahme"
    zu behaupten. Ebenso ein Beleg, der nicht zum Pin passt.

    Mutationsprobe: in _vorher_tbox wieder ``continue`` -> rot."""
    linie = linie_anlegen(tmp_path)
    assert _vorlegen(linie, "A-O1", "Vorlage").exit_code == 0
    assert _zeichnen(linie, "A-O1").exit_code == 0
    [kopie] = _archiv(linie).glob("*.json")
    roh = kopie.read_bytes()
    kopie.unlink()
    ergebnis = _vorlegen(linie, "A-O1", "naechste Vorlage")
    assert ergebnis.exit_code == Exit.FILE_CONTRACT, ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "fehlt im Archiv" in meldung and "Ausweg" in meldung, meldung
    kopie.write_bytes(roh.replace(b'"begruendung": "Vorlage"', b'"begruendung": "anders"'))
    ergebnis = _vorlegen(linie, "A-O1", "naechste Vorlage")
    assert ergebnis.exit_code == Exit.FILE_CONTRACT
    assert "passt nicht zum Pin" in ergebnis.errors[0]["message"], ergebnis.errors
    kopie.write_bytes(roh)
    ergebnis = _vorlegen(linie, "A-O1", "naechste Vorlage")
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert ergebnis.summary["vorher"] is not None
    assert "Erstabnahme" not in (linie / stand_belegen.TBOX_SICHT_RELATIV).read_text(
        encoding="utf-8")


def test_eine_ablehnung_ueber_der_annahme_macht_keine_erstabnahme(tmp_path):
    """Ist die geltende Spitze eine Ablehnung, bleibt das zuletzt ABGENOMMENE
    Vokabular die Annahme davor — "keine Annahme" ist der einzige Weg zu
    "Erstabnahme"."""
    linie = linie_anlegen(tmp_path)
    assert _vorlegen(linie, "A-O1", "Vorlage").exit_code == 0
    angenommen = _zeichnen(linie, "A-O1")
    assert angenommen.exit_code == 0
    ablehnung = _zeichnen(linie, "A-O1", "abgelehnt")
    assert ablehnung.exit_code == 0, ablehnung.errors
    ergebnis = _vorlegen(linie, "A-O1", "naechste Vorlage")
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert ergebnis.summary["vorher"] == angenommen.summary["snapshot_sha256"]


# --------------------------------------------------------------------------- #
# G25: die Bindung des alten Anfangsbestands
# --------------------------------------------------------------------------- #


@pytest.fixture()
def ablage_mit_vorgaenger(tmp_path, monkeypatch):
    """Eine aufgebaute Ablage, deren Provenienz auf ein Archiv zeigt, und eine
    gezeichnete Bindung einer anderen, abgenommenen Ablage als Vorlage fuer
    die Bindung der alten."""
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from rechner_pipeline.betrieb import tageslauf as tl
    from rechner_pipeline.betrieb.neuaufsetzen import PROVENIENZ_DATEI
    from tests.anfangsbestand_testhelfer import schreibe_anfangsbestand

    monkeypatch.setattr(anf, "_STANDARD_ANFANGSBESTAND", None)
    alt = _aufgebaute_ablage(tmp_path / "alt")
    with tl.lauf_sperre(alt):
        schreibe_anfangsbestand(alt, _betriebszeichner())
    bindung = (alt.wurzel / ab.BINDUNG_DATEI).read_bytes()
    neu = _aufgebaute_ablage(tmp_path / "daten")
    archiv = tmp_path / "daten.archiv"
    archiv.mkdir()
    (neu.wurzel / PROVENIENZ_DATEI).write_text(json.dumps({"archiv": str(archiv)}),
                                               encoding="utf-8")
    linie = linie_anlegen(tmp_path / "zeichnen")
    return neu, archiv, bindung, linie


def test_eine_lesbare_alte_bindung_wird_die_abweichung(ablage_mit_vorgaenger):
    """Positivkontrolle: die gezeichnete Bindung im Archiv -> vorher, Abweichung."""
    from rechner_pipeline.betrieb import anfangsbestand as anf

    neu, archiv, bindung, linie = ablage_mit_vorgaenger
    (archiv / ab.BINDUNG_DATEI).write_bytes(bindung)
    beleg = anf.belegen(neu.wurzel, linie, _betriebszeichner())
    assert beleg["vorher"]["snapshot_sha256"] == json.loads(bindung)["snapshot_sha256"]
    assert beleg["abweichung"]


@pytest.mark.parametrize("stoerung", ["unlesbar", "signatur", "archiv_fehlt"])
def test_eine_nicht_lesbare_oder_nicht_pruefbare_alte_bindung_ist_keine_erste_abnahme(
        ablage_mit_vorgaenger, stoerung):
    """Mutationsprobe: in _vorher wieder ``except ...: return None`` -> belegen
    meldet "erste Abnahme" -> rot."""
    from rechner_pipeline.betrieb import anfangsbestand as anf

    neu, archiv, bindung, linie = ablage_mit_vorgaenger
    if stoerung == "unlesbar":
        (archiv / ab.BINDUNG_DATEI).write_bytes(bindung[: len(bindung) // 2])
    elif stoerung == "signatur":
        daten = json.loads(bindung)
        daten["kennzahlen"]["in_kraft"] = 10 ** 6
        (archiv / ab.BINDUNG_DATEI).write_text(json.dumps(daten), encoding="utf-8")
    else:
        archiv.rmdir()
    with pytest.raises(anf.AnfangsbestandFehler, match="zuletzt abgenommen") as info:
        anf.belegen(neu.wurzel, linie, _betriebszeichner())
    assert "Ausweg" in str(info.value)
    assert not (linie / ab.BELEG_RELATIV).exists()


def test_ohne_vorgaenger_ist_es_die_erste_abnahme(ablage_mit_vorgaenger, tmp_path):
    """"Es gab keine Ablage davor" (Archiv ohne Bindung und ohne eigene
    Provenienz) ist der einzige Weg zu "erste Abnahme"."""
    from rechner_pipeline.betrieb import anfangsbestand as anf

    neu, archiv, _, linie = ablage_mit_vorgaenger
    beleg = anf.belegen(neu.wurzel, linie, _betriebszeichner())
    assert beleg["vorher"] is None and beleg["abweichung"] is None
    assert "erste Abnahme dieser Ablage" in (linie / ab.SICHT_RELATIV).read_text(
        encoding="utf-8")


# --------------------------------------------------------------------------- #
# G27: ein Schreibrest von linie.json sperrt die Wiederholung nicht
# --------------------------------------------------------------------------- #


def test_ein_abbruch_beim_einhaengen_von_linie_json_sperrt_die_wiederholung_nicht(tmp_path):
    """Prozessende (os._exit) zwischen Tempdatei und Einhaengen, im eigenen
    Prozess; danach derselbe Aufruf: Exit 0, linie.json, kein Rest.

    Mutationsprobe: die Ausnahme fuer eigene Schreibreste in der Pruefung
    "leer" entfernen -> Exit 2 -> rot."""
    linie = tmp_path / "linie"
    code = ("import os, sys\n"
            "from rechner_pipeline.gates import stand_belegen\n"
            "os.link = lambda *a, **k: os._exit(137)\n"
            f"stand_belegen.main(['linie', '--linie', {str(linie)!r}])\n")
    umgebung = {**os.environ, "PYTHONPATH": str(SRC)}
    lauf = subprocess.run([sys.executable, "-c", code], env=umgebung, cwd=str(tmp_path),
                          capture_output=True, text=True, timeout=120)
    assert lauf.returncode == 137, lauf.stderr
    reste = [p.name for p in linie.iterdir()]
    assert len(reste) == 1 and reste[0].startswith(".linie.json."), reste
    ergebnis = stand_belegen.main(["linie", "--linie", str(linie)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert [p.name for p in linie.iterdir()] == [sa.LINIE_MARKER]
    # Ein fremder Inhalt bleibt ein Grund: ein Linienbereich entsteht leer.
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    (fremd / "notiz.txt").write_text("x", encoding="utf-8")
    assert stand_belegen.main(["linie", "--linie", str(fremd)]).exit_code == Exit.USAGE


# --------------------------------------------------------------------------- #
# G28: das Neuaufsetzen raeumt seine Vorbereitung ab
# --------------------------------------------------------------------------- #


@pytest.fixture()
def gefuehrt(tmp_path):
    from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def _neuaufsetzen_argv(ablage, fall):
    from tests.freigabe_testschluessel import betriebsargs, linieargs
    from tests.test_betrieb_uebernahme import STICHTAG

    return ["--stand", str(ablage.wurzel), "--fall", str(fall),
            "--stichtag", STICHTAG.isoformat(), *betriebsargs("--betriebsschluessel"),
            *linieargs()]


@pytest.mark.parametrize("stelle", ["provenienz", "archivierung"])
def test_ein_ausfall_vor_dem_tausch_hinterlaesst_keine_vorbereitung(
        gefuehrt, tmp_path, monkeypatch, capsys, stelle):
    """Mutationsprobe: das Abraeumen der Vorbereitung bei diesem Ausfall
    entfernen -> daten.neu-<zeit> bleibt liegen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    protokoll = gefuehrt.protokoll_pfad.read_bytes()
    vorher = sorted(p.name for p in tmp_path.iterdir())
    with monkeypatch.context() as m:
        if stelle == "provenienz":
            import builtins
            import io

            echt_open, echt_io = builtins.open, io.open

            def gestoert(echt):
                def oeffne(datei, modus="r", *a, **k):
                    if not isinstance(datei, int) and Path(os.fspath(datei)).name.endswith(
                            na.PROVENIENZ_DATEI) and any(c in modus for c in "wax+"):
                        raise _enospc(datei)
                    return echt(datei, modus, *a, **k)
                return oeffne

            m.setattr(builtins, "open", gestoert(echt_open))
            m.setattr(io, "open", gestoert(echt_io))
        else:
            echt = os.rename

            def umbenennen(quelle, ziel, *a, **k):
                if Path(os.fspath(ziel)).name.startswith("daten.archiv-"):
                    raise _enospc(ziel)
                return echt(quelle, ziel, *a, **k)

            m.setattr(os, "rename", umbenennen)
        rc = na.main(_neuaufsetzen_argv(gefuehrt, fall))
    meldung = capsys.readouterr().err
    assert rc == 2, meldung
    assert "nichts bewegt" in meldung and "entfernt" in meldung, meldung
    assert sorted(p.name for p in tmp_path.iterdir()) == vorher
    assert gefuehrt.protokoll_pfad.read_bytes() == protokoll
    # Die Wiederholung liefert das Ergebnis des ungestoerten Laufs.
    assert na.main(_neuaufsetzen_argv(gefuehrt, fall)) == 0
    namen = sorted(p.name for p in tmp_path.iterdir())
    assert not [n for n in namen if n.startswith("daten.neu-")], namen
    assert len([n for n in namen if n.startswith("daten.archiv-")]) == 1, namen
    neu = json.loads((gefuehrt.wurzel / na.PROVENIENZ_DATEI).read_text(encoding="utf-8"))
    from rechner_pipeline.betrieb.tageslauf import Ablage

    assert Ablage(Path(neu["archiv"])).protokoll_pfad.read_bytes() == protokoll
