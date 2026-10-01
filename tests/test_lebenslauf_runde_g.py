"""Lebenslauf eines Falls, Fix-Runde nach der blinden Pruefrunde G (ADR-026, Nachtrag).

Je Fund die Invariante, ueber die echten Kommandos:

* **G14** — die Migrationsabnahme (und jede andere Annahme, die auf Annahmen
  des Falls gruendet) gruendet nur auf Annahmen, die den GELTENDEN
  Fallauftrag nennen. Eine Annahme unter einem abgeloesten Auftrag ist keine
  Vorbedingung mehr. EINE Pruefung in ``gate_entscheid.fallauftrag_pruefen``;
  jeder gruendende Leser meldet dort an, was er gelesen hat (Ratsche mit ``==``
  ueber die Leser, dazu der dynamische Zaehltest an der Naht).
* **G13 (Teil 2)** — die Linie eines Falls ist die Linie des Auftrags: Jede
  Abnahme, die der Auftrag aus der Linie nennt, liegt in der Kette ihres Gates
  in der Linie, die das Gate jetzt bekommt.
* **G15** — der Abbruch nach einer A-M4 braucht den Schluessel der Rolle, die
  A-M4 gezeichnet hat, im Ring; die Meldung nennt die Rolle, statt "nicht
  lesbar" zu sagen.
* **G16** — der Abbruch geht auch bei verletztem Eingang; der Befund steht
  woertlich im Abbruch und ist vom Gate nachgerechnet. Der Auftrag bleibt
  verweigert.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
from collections import Counter
from pathlib import Path

import pytest

from rechner_pipeline.gates import fall_belegen, gate_entscheid
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.models import fallauftrag as fa
from rechner_pipeline.models.zeichnung import ABBRUCH_GATE, AUFTRAG_GATE
from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import (
    PROGRAMMLEITUNG_SCHLUESSEL_DATEI,
    annahme_args,
    fallauftrag_zeichnen,
    linie_anlegen,
    mandat_datei,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GATE_ENTSCHEID = REPO_ROOT / "src" / "rechner_pipeline" / "gates" / "gate_entscheid.py"


def _snapshots(bereich: Path, gate: str):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((bereich / "entscheide").glob(f"{gate}-*.json"))]


def _geltender_auftrag(fall: Path) -> str:
    from rechner_pipeline.gates.stand_belegen import geltende_spitze

    spitze, fehler = geltende_spitze(fall, AUFTRAG_GATE)
    assert spitze is not None and spitze["entscheid"] == "angenommen", fehler
    return spitze["snapshot_sha256"]


def _annahme(fall: Path, gate: str, *extra: str, **kw):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", gate, "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", f"{gate} (Runde G)",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, **kw), *extra])


def _auftrag_zurueckziehen(fall: Path):
    """Der Vorstand zieht den Auftrag zurueck: A-M6 abgelehnt (neue Spitze)."""
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", AUFTRAG_GATE, "--entscheid", "abgelehnt",
        "--entscheider", "vorstand", "--begruendung", "Auftrag zurueckgezogen",
        "--rolle", "mensch/vorstand",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, fuer=AUFTRAG_GATE)])
    assert ergebnis.exit_code == 0, ergebnis.errors


# --------------------------------------------------------------------------- #
# G14: Vorbedingungen nur unter dem geltenden Auftrag
# --------------------------------------------------------------------------- #


def test_g14_am4_gruendet_nicht_auf_annahmen_unter_abgeloestem_auftrag(tmp_path, monkeypatch):
    """Auftrag A1, darunter A-Q1, A-O1, A-T1, A-K2, A-M1; der Vorstand zieht A1
    zurueck und beauftragt neu (A2) mit einem anderen Mandat. A-M4 unter A2
    verweigert und nennt Gate, beide Auftraege und den Ausweg; unter A2 neu
    gezeichnet nimmt es an.

    Mutationsprobe: in fallauftrag_pruefen die Pruefung der Vorbedingungen
    entfernen -> A-M4 angenommen -> rot."""
    from tests.test_pk1_am4_beweisvertrag import _bereite_fall, _o3_tg2012
    from tests.zeichnung_fixture import zeichne_stand

    fall = _bereite_fall(tmp_path, ("klv/tg2012",))
    assert _o3_tg2012(fall).exit_code == 0
    a1 = _geltender_auftrag(fall)
    _auftrag_zurueckziehen(fall)
    mandat_datei(fall).write_text("Mandat 2 (neu): zeichnet nur nach Ruecksprache.\n",
                                  encoding="utf-8")
    fallauftrag_zeichnen(fall)
    a2 = _geltender_auftrag(fall)
    assert a1 != a2

    ergebnis = _annahme(fall, "A-M4")
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "fallauftrag", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "A-Q1" in meldung and a1[:16] in meldung and a2[:16] in meldung, meldung
    assert "neu zeichnen" in meldung, meldung
    assert _snapshots(fall, "A-M4") == []

    # Positivkontrolle: unter dem geltenden Auftrag neu gezeichnet -> A-M4 nimmt an.
    # Der Zaehltest an der Naht: genau diese Annahmen des Falls meldet A-M4 an.
    assert _annahme(fall, "A-Q1").exit_code == 0
    zeichne_stand(fall, REPO_ROOT)
    assert _annahme(fall, "A-M1").exit_code == 0
    gesehen = []
    echt = gate_entscheid.fallauftrag_pruefen

    def mitschreiben(*args, **kw):
        gesehen.append({g: s["fallauftrag"] for g, s in kw["vorbedingungen"].items()})
        return echt(*args, **kw)

    monkeypatch.setattr(gate_entscheid, "fallauftrag_pruefen", mitschreiben)
    ergebnis = _annahme(fall, "A-M4")
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert gesehen == [{g: a2 for g in ("A-Q1", "A-M1", "A-O1", "A-T1", "A-K2")}]
    [am4] = _snapshots(fall, "A-M4")
    assert am4["fallauftrag"] == a2


def test_g14_jede_annahme_meldet_an_was_sie_liest_auch_ohne_vorbedingung(tmp_path, monkeypatch):
    """Die Stelle ist fuer jede Annahme eines Falls dieselbe: Ein Gate ohne
    gruendende Lesung meldet die leere Menge an (kein Standardwert, der eine
    vergessene Anmeldung verdeckte)."""
    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    gesehen = []
    echt = gate_entscheid.fallauftrag_pruefen

    def mitschreiben(*args, **kw):
        gesehen.append(dict(kw["vorbedingungen"]))
        return echt(*args, **kw)

    monkeypatch.setattr(gate_entscheid, "fallauftrag_pruefen", mitschreiben)
    assert _annahme(fall, "A-Q1").exit_code == 0
    assert gesehen == [{}]


def test_g14_fallauftrag_pruefen_hat_keinen_standardwert_fuer_die_vorbedingungen():
    """Ratsche (statisch, benannt): ``vorbedingungen`` und ``linie_pfad`` sind
    Pflicht-Schluesselwoerter — wer die Stelle ruft, muss sagen, worauf er
    gruendet und unter welcher Linie."""
    import inspect

    sig = inspect.signature(gate_entscheid.fallauftrag_pruefen)
    for name in ("vorbedingungen", "linie_pfad"):
        p = sig.parameters[name]
        assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty


def _leser(quelle: str) -> Counter:
    """Je umschliessender Funktion: Aufrufe des Kettenlesers mit Signatur
    (``_lade_snapshot_kette``) und Anmeldungen an der Stelle des Auftrags
    (Zuweisung an ``<...>vorbedingungen[...]``)."""
    zaehler: Counter = Counter()

    class Besucher(ast.NodeVisitor):
        def __init__(self):
            self.funktion = "<modul>"

        def visit_FunctionDef(self, knoten):
            vorher, self.funktion = self.funktion, knoten.name
            self.generic_visit(knoten)
            self.funktion = vorher

        def visit_Call(self, knoten):
            f = knoten.func
            if (f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")) == "_lade_snapshot_kette":
                zaehler[("lesen", self.funktion)] += 1
            self.generic_visit(knoten)

        def visit_Assign(self, knoten):
            for ziel in knoten.targets:
                if (isinstance(ziel, ast.Subscript) and isinstance(ziel.value, ast.Name)
                        and ziel.value.id.endswith("vorbedingungen")):
                    zaehler[("anmelden", self.funktion)] += 1
            self.generic_visit(knoten)

    Besucher().visit(ast.parse(quelle))
    return zaehler


#: Gemessen 2026-10-01 (Runde G, G14). Die Leser mit Signatur in gate_entscheid:
#: * ``standabnahme_pruefen`` — Weg a, die Kette des Gegenstands im Fall
#:   (A-K2, A-O1, A-T1): GRUENDET, meldet an. Weg b (Verweis auf die Linie)
#:   liest keine Kette des Falls und traegt keinen Auftrag — ausgenommen.
#: * ``fallauftrag_pruefen`` — die A-M6-Kette selbst (der Auftrag).
#: * ``_lebenslauf_vorlage`` — die A-M4-Kette als SPERRE des Abbruchs; sie
#:   gruendet nichts (eine A-M4 unter welchem Auftrag auch immer sperrt).
#: * ``main`` — A-B2: A-M4 und A-M1 (gruenden, melden an); A-M4: A-Q1 und
#:   A-M1..A-M3 in einer Schleife (gruenden, melden an); die eigene Kette des
#:   Gates (Vorgaenger, gruendet nichts).
LESER = Counter({
    ("lesen", "standabnahme_pruefen"): 1, ("anmelden", "standabnahme_pruefen"): 1,
    ("lesen", "fallauftrag_pruefen"): 1,
    ("lesen", "_lebenslauf_vorlage"): 1,
    ("lesen", "main"): 5, ("anmelden", "main"): 4,
    # Weg (b) der Standabnahme (Pruefrunde G, G11): liest die Kette der LINIE,
    # um die Gueltigkeit des Verweises zu halten. Eine Abnahme der Linie
    # traegt keinen Auftrag und wird nicht angemeldet.
    ("lesen", "_verweis_gilt_fehler"): 1,
})


def test_g14_ratsche_jeder_gruendende_leser_meldet_an():
    assert _leser(GATE_ENTSCHEID.read_text(encoding="utf-8")) == LESER


def test_g14_ratsche_positivkontrolle_des_detektors():
    quelle = ("def a(f):\n    k = _lade_snapshot_kette(f)\n    vorbedingungen['A-Q1'] = k\n"
              "def b(f):\n    x._lade_snapshot_kette(f)\n    fall_vorbedingungen[g] = 1\n"
              "    andere['x'] = 1\n")
    assert _leser(quelle) == Counter({("lesen", "a"): 1, ("anmelden", "a"): 1,
                                      ("lesen", "b"): 1, ("anmelden", "b"): 1})


# --------------------------------------------------------------------------- #
# G13, Teil 2: die Linie des Falls ist die Linie des Auftrags
# --------------------------------------------------------------------------- #


def test_g13_eine_kopie_der_linie_ohne_ihre_abnahmen_ist_nicht_die_linie_des_auftrags(tmp_path):
    """Der Auftrag nennt die Erstabnahme A-T1 der Linie. Eine Kopie mit
    denselben Gliedern der Ordnungslinie, aber ohne die Ketten, wird
    verweigert; die echte Linie nimmt an — auch nachdem sie seit dem Auftrag
    eine neue Abnahme bekommen hat.

    Mutationsprobe: die Pruefung der Linie in fallauftrag_pruefen entfernen ->
    A-Q1 unter der Kopie angenommen -> rot."""
    from tests.test_erstabnahme_linie import _zeichne_in_linie

    linie = linie_anlegen(tmp_path)
    assert _zeichne_in_linie(linie, "A-T1").exit_code == 0
    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    fallauftrag_zeichnen(fall)
    [auftrag] = _snapshots(fall, AUFTRAG_GATE)
    [at1] = _snapshots(linie, "A-T1")
    assert auftrag["auftrag"]["zielsystem"]["abnahmen"]["A-T1"] == at1["snapshot_sha256"]

    kopie = tmp_path / "kopie" / "linie"
    kopie.mkdir(parents=True)
    shutil.copy2(linie / "linie.json", kopie / "linie.json")
    shutil.copytree(linie / "ordnung", kopie / "ordnung")
    args = annahme_args(fall)
    args[args.index("--linie") + 1] = str(kopie)
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-Q1", "--entscheid", "angenommen",
        "--entscheider", "aktuariat", "--begruendung", "unter einer Kopie",
        "--repo-root", str(REPO_ROOT), *args])
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "fallauftrag", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "nicht die Linie des Auftrags" in meldung and "A-T1" in meldung, meldung
    assert _snapshots(fall, "A-Q1") == []

    # Eine NEUE Abnahme der Linie seit dem Auftrag ist erlaubt.
    assert _zeichne_in_linie(linie, "A-K2").exit_code == 0
    assert _annahme(fall, "A-Q1").exit_code == 0


# --------------------------------------------------------------------------- #
# G15: der Ring des Abbruchs nach einer A-M4
# --------------------------------------------------------------------------- #


def test_g15_der_abbruch_nach_abgelehnter_am4_nennt_die_rolle_deren_schluessel_fehlt(tmp_path):
    """Der Ausweg "A-M4 ablehnen, dann abbrechen" mit dem Ring aus Vorstand und
    Programmleitung: verweigert, und die Meldung nennt die Rolle, die die
    A-M4-Kette gezeichnet hat, und dass ihr Schluessel in den Ring gehoert. Mit
    dem Schluessel im Ring nimmt das Gate an.

    Mutationsprobe: die Meldung auf "nicht lesbar" zuruecksetzen -> rot."""
    from tests.freigabe_testschluessel import AKTUARIAT_ROLLE, TESTKEY
    from tests.test_betrieb_uebernahme import am4_snapshot

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    fallauftrag_zeichnen(fall)
    am4 = am4_snapshot(fall.name)
    (fall / "entscheide" / f"A-M4-{am4['snapshot_sha256']}.json").write_text(
        json.dumps(am4), encoding="utf-8")
    aktuar = tmp_path / "aktuar.key"
    aktuar.write_bytes(TESTKEY)
    aktuar.chmod(0o600)
    # Seit Pruefrunde I gibt nur eine GEZEICHNETE Ablehnung den Abbruch frei:
    # das Aktuariat der Spitze mit seinem Schluessel (zuletzt im Ring) unter der
    # Ordnung der Spitze; der Schluessel der Suite-A-M4 liest die Kette.
    abgelehnt = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M4", "--entscheid", "abgelehnt",
        "--entscheider", "aktuariat", "--begruendung", "Abnahme zurueckgenommen",
        "--rolle", AKTUARIAT_ROLLE, "--repo-root", str(REPO_ROOT),
        "--freigabe-schluessel", str(aktuar), *annahme_args(fall)])
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    assert [("freigabe" in s) for s in _snapshots(fall, "A-M4")
            if s["entscheid"] == "abgelehnt"] == [True]
    assert fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "g", "--bestand", "b", "--uebergabe", "u"]).exit_code == 0

    def abbruch(*vorne: str):
        args = annahme_args(fall, fuer=ABBRUCH_GATE)
        pl = args.index(str(fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI))
        args[pl - 1:pl - 1] = list(vorne)
        return gate_entscheid.main([
            "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
            "--entscheider", "programmleitung", "--begruendung", "x",
            "--repo-root", str(REPO_ROOT), *args])

    ohne = abbruch()
    assert ohne.exit_code == 20, ohne.errors
    meldung = ohne.errors[0]["message"]
    fp = hashlib.sha256(TESTKEY).hexdigest()
    assert AKTUARIAT_ROLLE in meldung and fp[:16] in meldung and "in den Ring" in meldung, meldung
    assert _snapshots(fall, ABBRUCH_GATE) == []
    mit = abbruch("--freigabe-schluessel", str(aktuar))
    assert mit.exit_code == 0, mit.errors


# --------------------------------------------------------------------------- #
# G16: Abbruch bei verletztem Eingang
# --------------------------------------------------------------------------- #


def _eingang_verletzen(fall: Path) -> str:
    quelle = next(p for p in sorted((fall / "eingang").iterdir()) if p.is_file())
    os.chmod(fall / "eingang", 0o755)
    quelle.chmod(0o644)
    quelle.unlink()
    return quelle.name


def test_g16_abbruch_bei_verletztem_eingang_traegt_den_befund_woertlich(tmp_path):
    """Die registrierte Kopie der Lieferung geht verloren. Der Abbruch wird
    gezeichnet, und der Befund der Eingangspruefung steht woertlich in der
    Vorlage, im signierten Abbruch und in der Sicht; eine Vorlage, die den
    Befund verschweigt, wird verweigert. Neu beauftragt wird nicht.

    Mutationsproben: (1) die Eingangssperre wieder fuer A-M5 -> rot;
    (2) den Vergleich des Befunds in _lebenslauf_vorlage entfernen -> die
    geschoente Vorlage geht durch -> rot."""
    from rechner_pipeline import fall as fall_mod

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    fallauftrag_zeichnen(fall)
    name = _eingang_verletzen(fall)
    befund = fall_mod.pruefen(fall)
    assert befund and name in befund[0]

    def vorlage():
        return fall_belegen.main([
            "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
            "--grund", "die Lieferung ist verloren", "--bestand", "bleibt beim Abgeber",
            "--uebergabe", "an den Vorstand"])

    def abbruch():
        return gate_entscheid.main([
            "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
            "--entscheider", "programmleitung", "--begruendung", "Lieferung verloren",
            "--repo-root", str(REPO_ROOT), *annahme_args(fall, fuer=ABBRUCH_GATE)])

    assert vorlage().exit_code == 0
    beleg = json.loads((fall / fa.ABBRUCH_RELATIV).read_text(encoding="utf-8"))
    assert beleg["eingang_befund"] == befund
    from rechner_pipeline.gates.kernstand_belegen import _md

    sicht = (fall / fa.ABBRUCH_SICHT_RELATIV).read_text(encoding="utf-8")
    assert "verletzt sein Register" in sicht and _md(befund[0]) in sicht, sicht

    # Eine Vorlage, die den Befund verschweigt: nachgerechnet, verweigert.
    geschoent = {**beleg, "eingang_befund": []}
    (fall / fa.ABBRUCH_RELATIV).write_text(json.dumps(geschoent), encoding="utf-8")
    ergebnis = abbruch()
    assert ergebnis.exit_code == 20 and "eingang_befund" in ergebnis.errors[0]["message"], \
        ergebnis.errors

    assert vorlage().exit_code == 0
    ergebnis = abbruch()
    assert ergebnis.exit_code == 0, ergebnis.errors
    [snapshot] = _snapshots(fall, ABBRUCH_GATE)
    assert snapshot["abbruch"]["eingang_befund"] == befund

    # Auf einer beschaedigten Lieferung wird nicht beauftragt — und nach dem
    # Abbruch ohnehin nichts mehr gezeichnet; die Eingangssperre des Auftrags
    # zeigt sich deshalb an einem zweiten Fall ohne Abbruch.


def test_g16_der_auftrag_bleibt_bei_verletztem_eingang_verweigert(tmp_path):
    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    _eingang_verletzen(fall)
    ergebnis = fallauftrag_zeichnen(fall, streng=False)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "eingang", ergebnis.errors
    assert _snapshots(fall, AUFTRAG_GATE) == []


def test_g16_der_abbruch_bei_unversehrtem_eingang_sagt_es():
    """Die Form: ``eingang_befund`` ist eine Liste von Saetzen; leer heisst
    unversehrt, und die Sicht sagt es."""
    beleg = {"schema_version": fa.ABBRUCH_SCHEMA_VERSION, "art": fa.ABBRUCH_ART,
             "fall": "f", "fallauftrag": "aa" * 32, "grund": "g", "bestand": "b",
             "uebergabe": "u", "gezeichnet": [], "eingang_befund": [],
             "stand": {"eingang_sha256": "bb" * 32,
                       "system": {"commit": "c", "branch": "b", "dirty": "nein",
                                  "quellcode_sha256": "dd" * 32}}}
    assert fa.abbruch_fehler(beleg) == []
    assert "unversehrt" in fall_belegen.rendere_abbruch(beleg)
    for falsch in ([""], "kaputt", [1]):
        assert fa.abbruch_fehler({**beleg, "eingang_befund": falsch})
    assert fa.abbruch_fehler({k: v for k, v in beleg.items() if k != "eingang_befund"})
