"""Lebenslauf eines Falls und Leser des Betriebs, Fix-Runde nach der blinden
Pruefrunde I (ADR-026, Nachtrag Pruefrunde I).

Je Fund die Invariante, ueber die echten Kommandos:

* **I06** — eine ANGENOMMENE Migrationsabnahme verliert ihre Geltung fuer den
  Abbruch nur durch einen Widerruf, den eine fuer A-M4 berechtigte Rolle
  GEZEICHNET hat. Eine Ablehnung mit dem Schluessel einer berechtigten Rolle
  wird gezeichnet (Freigabe und Zeichnung im Snapshot); eine ohne Schluessel
  bleibt zulaessig, unsigniert und in ihrer Gestalt wie bisher. EINE Regel:
  ``gate_entscheid.gezeichneter_widerruf_fehler``.
* **I07** — der Leser des Betriebs (``betrieb.uebernahme.lies_abnahme_snapshot``)
  liest den Fallauftrag, den A-M4, A-M1 und A-B2 signiert nennen, mit
  derselben Regel wie jede Abnahme: geltende, angenommene Spitze der
  A-M6-Kette, Signatur, Rollenregel unter der Linie (damit "verfallen").
* **I08** — jeder Snapshot, auf dem der Betrieb gruendet, traegt das aktuelle
  Schema; geprueft an der einen Lesestelle.
* **I09** — der Fingerabdruck der Programmleitung gehoert unter der Spitze
  der Linie keiner Rolle der Ordnung, bei JEDER Annahme des Falls
  (``fallauftrag_pruefen``), den Abbruch eingeschlossen.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.gates import fall_belegen, gate_entscheid, stand_belegen
from rechner_pipeline.gates.abox_validate import main as pq3
from rechner_pipeline.gates.generation_golden import main as pk1
from rechner_pipeline.models.freigabe import freigabe_fuer, pruefe_freigabe
from rechner_pipeline.models.schemas import p9_snapshot_sha256
from rechner_pipeline.models.zeichnung import ABBRUCH_GATE
from tests.e2e_fixture import bereite_pk1_fall
from tests.zeichnung_fixture import (
    PROGRAMMLEITUNG_SCHLUESSEL_DATEI,
    RECHENKERN_SCHLUESSEL_DATEI,
    VA,
    annahme_args,
    linie_args,
    zeichne_kernstand,
    zeichne_tarifwerk,
    zeichne_tboxstand,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
STICHTAG = dt.date(2026, 1, 1)


def _snapshots(fall: Path, gate: str):
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((fall / "entscheide").glob(f"{gate}-*.json"))]


def _annahme(fall: Path, gate: str, *extra: str, **kw):
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", gate, "--entscheid", "angenommen",
        "--entscheider", "fachrolle", "--begruendung", f"{gate} (Runde I)",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, **kw), *extra])


# --------------------------------------------------------------------------- #
# I06: nur ein gezeichneter Widerruf gibt den Abbruch nach A-M4 frei
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def _abgenommen_vorlage(tmp_path_factory):
    """Ein Tarif-Fall bis zur geltenden A-M4-Annahme, ueber die echten Kommandos."""
    wurzel = tmp_path_factory.mktemp("runde-i-am4")
    fall = bereite_pk1_fall(wurzel, scope="tarif")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    assert _annahme(fall, "A-Q1").exit_code == 0
    zeichne_tboxstand(fall, REPO_ROOT)
    zeichne_tarifwerk(fall, REPO_ROOT)
    zeichne_kernstand(fall, REPO_ROOT)
    assert _annahme(fall, "A-M1").exit_code == 0
    assert pk1(["--fall", str(fall), "--generation", "klv/tg2012",
                "--repo-root", str(REPO_ROOT)]).exit_code == 0
    ergebnis = _annahme(fall, "A-M4")
    assert ergebnis.exit_code == 0, ergebnis.errors
    return wurzel


@pytest.fixture()
def abgenommen(_abgenommen_vorlage, tmp_path):
    """Eine frische Kopie des abgenommenen Falls je Test (Schluessel 0600 bleiben)."""
    ziel = tmp_path / "welt"
    shutil.copytree(_abgenommen_vorlage, ziel, symlinks=True)
    return ziel / "fall"


def _abbruch(fall: Path):
    vorlage = fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "Lieferung unbrauchbar", "--bestand", "bleibt beim Abgeber",
        "--uebergabe", "an den Vorstand"])
    assert vorlage.exit_code == 0, vorlage.errors
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", ABBRUCH_GATE, "--entscheid", "angenommen",
        "--entscheider", "programmleitung", "--begruendung", "Abbruch (Runde I)",
        "--repo-root", str(REPO_ROOT), *annahme_args(fall, fuer=ABBRUCH_GATE)])


def _am4_spitze(fall: Path) -> dict:
    kette = _snapshots(fall, "A-M4")
    genannt = {v for d in kette for v in d["vorgaenger"]}
    (spitze,) = [d for d in kette if d["snapshot_sha256"] not in genannt]
    return spitze


def _hinlegen(fall: Path, daten: dict) -> dict:
    daten = {k: v for k, v in daten.items() if k != "snapshot_sha256"}
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    (fall / "entscheide" / f"{daten['gate']}-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return daten


def _ablehnung_von_hand(fall: Path, *, rolle: str = "agent/unbekannt") -> dict:
    """Eine Ablehnung VON HAND in entscheide/ — ohne Schluessel, ohne Gate,
    Gestalt wie das Gate sie schreibt (der Angriff der Pruefrunde I)."""
    annahme = _am4_spitze(fall)
    daten = {k: v for k, v in annahme.items()
             if k not in ("zeichnung", "freigabe", "fallauftrag", "snapshot_sha256")}
    daten.update({"entscheid": "abgelehnt", "rolle": rolle, "entscheider": "niemand",
                  "begruendung": "untergeschoben", "vorgaenger": [annahme["snapshot_sha256"]],
                  "pflichtbelege": {}, "pk1_belege": {}, "standabnahmen": {}})
    return _hinlegen(fall, daten)


def _gezeichnet_ablehnen(fall: Path):
    """Das Aktuariat lehnt A-M4 mit seinem Schluessel ab — der Ausweg."""
    return gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M4", "--entscheid", "abgelehnt",
        "--entscheider", "aktuariat", "--begruendung", "Abnahme widerrufen",
        "--rolle", VA, "--repo-root", str(REPO_ROOT), *annahme_args(fall)])


def test_i06_eine_untergeschobene_ablehnung_gibt_den_abbruch_nicht_frei(abgenommen):
    """Rot auf 9fa1538: Mit einer hingelegten, unsignierten A-M4-Ablehnung
    zeichnete die Programmleitung den Abbruch (Exit 0) — die Abnahme war tot.

    Mutationsprobe: in ``_lebenslauf_vorlage`` den Zweig mit
    ``gezeichneter_widerruf_fehler`` entfernen -> rot."""
    fall = abgenommen
    _ablehnung_von_hand(fall)
    ergebnis = _abbruch(fall)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert ergebnis.errors[0]["code"] == "vorbedingung", ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "nicht gezeichnet widerrufen" in meldung and "unsignierte Ablehnung" in meldung
    assert "das Aktuariat lehnt A-M4 mit seinem Schluessel ab" in meldung, meldung
    assert _snapshots(fall, ABBRUCH_GATE) == []


def test_i06_die_ablehnung_eines_agenten_bleibt_unsigniert_und_gibt_nichts_frei(abgenommen):
    """Ein Agent darf ablehnen (ADR-008, Punkt 6) — ohne Ordnung und mit dem
    Ring nur zum Lesen ist die Ablehnung unsigniert, ihre Gestalt wie bisher.
    Sie sperrt, sie gibt den Abbruch nach der Abnahme nicht frei."""
    fall = abgenommen
    ring = [teil for teil in annahme_args(fall) if teil.endswith(".key")]
    argv = ["--fall", str(fall), "--gate", "A-M4", "--entscheid", "abgelehnt",
            "--entscheider", "programmleitung", "--begruendung", "Zwischenstand",
            "--rolle", "agent/programmleitung", "--repo-root", str(REPO_ROOT),
            *linie_args(fall)]
    for datei in ring:
        argv += ["--freigabe-schluessel", datei]
    abgelehnt = gate_entscheid.main(argv)
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    spitze = _am4_spitze(fall)
    assert spitze["entscheid"] == "abgelehnt" and spitze["rolle"] == "agent/programmleitung"
    # Die Gestalt einer unsignierten Ablehnung: dieselben Felder wie vorher.
    assert "freigabe" not in spitze and "zeichnung" not in spitze and "fallauftrag" not in spitze
    ergebnis = _abbruch(fall)
    assert ergebnis.exit_code == 20 and "unsignierte Ablehnung" in ergebnis.errors[0]["message"]


def test_i06_der_gezeichnete_widerruf_des_aktuariats_gibt_den_abbruch_frei(abgenommen):
    """Der Ausweg: Das Aktuariat lehnt mit seinem Schluessel ab. Das Gate
    ZEICHNET die Ablehnung (Freigabe, Zeichnung unter der Spitze), die
    Signatur ist pruefbar, danach geht der Abbruch.

    Rot auf 9fa1538: Die Ablehnung trug keine Freigabe.
    Mutationsprobe: im Gate ``ablehnung_gezeichnet_von`` nie setzen -> rot."""
    fall = abgenommen
    abgelehnt = _gezeichnet_ablehnen(fall)
    assert abgelehnt.exit_code == 0, abgelehnt.errors
    spitze = _am4_spitze(fall)
    assert spitze["entscheid"] == "abgelehnt" and spitze["rolle"] == VA
    assert spitze["zeichnung"]["rolle"] == VA and "ordnungsglied_sha256" in spitze["zeichnung"]
    schluessel = (fall.parent / "p9-freigabe.key").read_bytes()
    assert spitze["freigabe"]["schluessel_sha256"] == hashlib.sha256(schluessel).hexdigest()
    ring = {hashlib.sha256(schluessel).hexdigest(): schluessel}
    assert pruefe_freigabe(spitze, ring) == []
    ergebnis = _abbruch(fall)
    assert ergebnis.exit_code == 0, ergebnis.errors
    assert len(_snapshots(fall, ABBRUCH_GATE)) == 1


def test_i06_eine_gefaelschte_gezeichnete_ablehnung_traegt_nicht(abgenommen):
    """Eine gezeichnete Ablehnung, deren Inhalt danach geaendert wurde (Hash
    nachgefuehrt, Signatur nicht): Der Kettenleser prueft JEDE getragene
    Freigabe — der Abbruch bleibt verweigert.

    Mutationsprobe: ``models.freigabe.pruefe_freigabe`` wieder nur fuer
    Annahmen pruefen lassen -> rot."""
    fall = abgenommen
    assert _gezeichnet_ablehnen(fall).exit_code == 0
    echt = _am4_spitze(fall)
    (fall / "entscheide" / f"A-M4-{echt['snapshot_sha256']}.json").unlink()
    _hinlegen(fall, {**echt, "begruendung": "anders begruendet"})
    ergebnis = _abbruch(fall)
    assert ergebnis.exit_code == 20, ergebnis.errors
    assert "Freigabesignatur stimmt nicht" in ergebnis.errors[0]["message"]
    assert _snapshots(fall, ABBRUCH_GATE) == []


def test_i06_ein_widerruf_einer_unberechtigten_rolle_traegt_nicht(abgenommen):
    """Gezeichnet, Signatur echt — aber von mensch/rechenkern, die A-M4 nicht
    zeichnen darf: Die Rollenregel verweigert (dieselbe wie fuer Annahmen)."""
    fall = abgenommen
    assert _gezeichnet_ablehnen(fall).exit_code == 0
    echt = _am4_spitze(fall)
    (fall / "entscheide" / f"A-M4-{echt['snapshot_sha256']}.json").unlink()
    rk = (fall.parent / RECHENKERN_SCHLUESSEL_DATEI).read_bytes()
    daten = {k: v for k, v in echt.items() if k not in ("freigabe", "snapshot_sha256")}
    daten["rolle"] = "mensch/rechenkern"
    daten["zeichnung"] = {**daten["zeichnung"], "rolle": "mensch/rechenkern"}
    daten["freigabe"] = freigabe_fuer(daten, rk)
    _hinlegen(fall, daten)
    ergebnis = _abbruch(fall)
    assert ergebnis.exit_code == 20, ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "nicht von einer berechtigten Rolle" in meldung and "mensch/rechenkern" in meldung


def _aufrufer(quelle: str, name: str):
    """Die Funktionen, die ``name`` rufen (statisch)."""
    treffer = []
    for funktion in ast.walk(ast.parse(quelle)):
        if isinstance(funktion, ast.FunctionDef):
            for knoten in ast.walk(funktion):
                if isinstance(knoten, ast.Call) and (
                        getattr(knoten.func, "id", None) == name
                        or getattr(knoten.func, "attr", None) == name):
                    treffer.append(funktion.name)
    return treffer


#: Die Leser, denen eine Ablehnung als Spitze etwas FREIGIBT — gemessen
#: (ADR-026, Nachtrag Pruefrunde I): nur der Abbruch nach A-M4. Jeder geht
#: durch die eine Regel; ein neuer muss hier eingetragen werden.
FREIGEBENDE_ABLEHNUNGSLESER = [("gates/gate_entscheid.py", "_lebenslauf_vorlage")]


def test_i06_ratsche_eine_regel_fuer_jeden_leser_dem_eine_ablehnung_etwas_freigibt():
    """Statische Ratsche (benannt): Die Aufrufer von
    ``gezeichneter_widerruf_fehler`` in src sind genau die gemessene Menge."""
    gefunden = []
    for pfad in sorted(SRC.rglob("*.py")):
        gefunden += [(str(pfad.relative_to(SRC)), f)
                     for f in _aufrufer(pfad.read_text(encoding="utf-8"),
                                        "gezeichneter_widerruf_fehler")]
    assert gefunden == FREIGEBENDE_ABLEHNUNGSLESER


def test_i06_ratsche_positivkontrolle():
    quelle = ("def a(s):\n    return gezeichneter_widerruf_fehler(s, 'A-M4', ordnung=o, linie=l)\n"
              "def b(s):\n    return ge.gezeichneter_widerruf_fehler(s, 'A-M4', ordnung=o, linie=l)\n"
              "def c(s):\n    return s\n")
    assert _aufrufer(quelle, "gezeichneter_widerruf_fehler") == ["a", "b"]


# --------------------------------------------------------------------------- #
# I09: die Programmleitung gehoert keiner Rolle der Ordnung — bei jeder Zeichnung
# --------------------------------------------------------------------------- #


@pytest.fixture()
def beauftragt(tmp_path):
    """Ein Tarif-Fall mit Auftrag und P-Q3, A-Q1 noch offen."""
    fall = bereite_pk1_fall(tmp_path, scope="tarif")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO_ROOT)]).exit_code == 0
    annahme_args(fall)   # beauftragt den Fall (ADR-026)
    assert _snapshots(fall, "A-M6")
    return fall


def _ordnung_mit_aktuariatsschluessel(fall: Path, schluessel: Path, name: str) -> Path:
    ordnung = json.loads((fall.parent / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    ordnung["rollen"][VA]["schluessel_sha256"] = hashlib.sha256(schluessel.read_bytes()).hexdigest()
    pfad = fall.parent / name
    pfad.write_text(json.dumps(ordnung), encoding="utf-8")
    return pfad


def test_i09_der_schluessel_der_programmleitung_zeichnet_nicht_als_rolle_der_ordnung(beauftragt):
    """Ein spaeteres Glied gibt den Schluessel der Programmleitung dem
    Aktuariat. Rot auf 9fa1538: Er zeichnete A-Q1 als mensch/aktuariat und
    danach den Abbruch als Programmleitung. Jetzt verweigert jede Annahme des
    Falls mit Code ``fallauftrag`` und dem Ausweg.

    Mutationsprobe: die Pruefung ``pl_fp in besetzt`` in
    ``fallauftrag_pruefen`` entfernen -> rot."""
    fall = beauftragt
    pl = fall.parent / PROGRAMMLEITUNG_SCHLUESSEL_DATEI
    o2 = _ordnung_mit_aktuariatsschluessel(fall, pl, "ordnung-pl.json")
    aq1 = _annahme(fall, "A-Q1", "--freigabe-schluessel", str(pl), ordnung_pfad=o2)
    assert aq1.exit_code == 20, aq1.errors
    assert aq1.errors[0]["code"] == "fallauftrag", aq1.errors
    meldung = aq1.errors[0]["message"]
    assert "Schluessel der Programmleitung" in meldung and VA in meldung
    assert "neu beauftragen" in meldung and _snapshots(fall, "A-Q1") == []
    assert fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--grund", "g", "--bestand", "b", "--uebergabe", "u"]).exit_code == 0
    am5 = _annahme(fall, ABBRUCH_GATE, fuer=ABBRUCH_GATE, ordnung_pfad=o2)
    assert am5.exit_code == 20 and am5.errors[0]["code"] == "fallauftrag", am5.errors
    assert _snapshots(fall, ABBRUCH_GATE) == []


def test_i09_positivkontrolle_ein_eigener_neuer_schluessel_zeichnet(beauftragt):
    """Dasselbe Glied mit einem EIGENEN neuen Schluessel des Aktuariats: A-Q1
    nimmt an — die Regel trifft nur den Schluessel der Programmleitung."""
    fall = beauftragt
    neu = fall.parent / "aktuariat-neu.key"
    neu.write_bytes(hashlib.sha256(b"aktuariat neu").digest() * 2)
    neu.chmod(0o600)
    o3 = _ordnung_mit_aktuariatsschluessel(fall, neu, "ordnung-neu.json")
    aq1 = _annahme(fall, "A-Q1", "--freigabe-schluessel", str(neu), ordnung_pfad=o3)
    assert aq1.exit_code == 0, aq1.errors


# --------------------------------------------------------------------------- #
# I07: der Betrieb liest den Auftrag, den die Abnahmen nennen
# --------------------------------------------------------------------------- #


def _betriebsfall(tmp_path: Path) -> Path:
    from tests.test_betrieb_uebernahme import _fall

    return _fall(tmp_path)


def _registriere(tmp_path: Path, fall: Path):
    from tests.test_betrieb_uebernahme import _mit_config

    return ueb.eingang_anlegen(_mit_config(tmp_path / "daten"), fall, STICHTAG)


def test_i07_positivkontrolle_der_beauftragte_fall_registriert(tmp_path):
    fall = _betriebsfall(tmp_path)
    assert (_registriere(tmp_path, fall) / "eingang.json").is_file()


def test_i07_ein_zurueckgezogener_auftrag_traegt_keine_registrierung(tmp_path):
    """Der Vorstand zieht den Auftrag NACH den Abnahmen zurueck (A-M6
    abgelehnt, neue Spitze). Rot auf 9fa1538: registriert. Jetzt verweigert,
    die Meldung nennt den zurueckgezogenen Auftrag und den Ausweg.

    Mutationsprobe: den Lesezweig des Fallauftrags in
    ``lies_abnahme_snapshot`` entfernen -> rot."""
    from tests.test_betrieb_uebernahme import am6_snapshot

    fall = _betriebsfall(tmp_path)
    auftrag = am6_snapshot("probe-uebernahme")
    _hinlegen(fall, {**{k: v for k, v in auftrag.items()
                        if k not in ("freigabe", "zeichnung", "auftrag", "snapshot_sha256")},
                     "entscheid": "abgelehnt", "begruendung": "Auftrag zurueckgezogen",
                     "vorgaenger": [auftrag["snapshot_sha256"]],
                     "pflichtbelege": {}})
    with pytest.raises(ueb.UebernahmeError) as fehler:
        _registriere(tmp_path, fall)
    meldung = str(fehler.value)
    assert auftrag["snapshot_sha256"][:16] in meldung and "traegt nicht" in meldung
    assert "entscheid='abgelehnt'" in meldung and "beauftragt den Fall (neu)" in meldung, meldung
    assert not (tmp_path / "daten" / "uebernahme" / "probe-uebernahme").exists()


def test_i07_nach_einem_neuen_auftrag_erst_wieder_mit_neu_gezeichneten_abnahmen(tmp_path):
    """Der Vorstand beauftragt neu (A-M6-Kette waechst). A-M4, A-M1 und A-B2
    unter dem alten Auftrag tragen nicht mehr — verweigert; neu gezeichnet
    unter dem geltenden Auftrag registriert der Betrieb."""
    from rechner_pipeline.models.freigabe import freigabe_fuer as _f
    from tests.freigabe_testschluessel import VORSTANDKEY
    from tests.test_betrieb_uebernahme import (
        _pb1_ledger,
        am1_snapshot,
        am4_snapshot,
        am6_snapshot,
        fuehrungsbeleg,
    )

    fall = _betriebsfall(tmp_path)
    alt = am6_snapshot("probe-uebernahme")
    neu = {k: v for k, v in alt.items() if k not in ("freigabe", "snapshot_sha256")}
    neu.update({"vorgaenger": [alt["snapshot_sha256"]], "begruendung": "neu beauftragt",
                "entschieden_am": "2026-01-01T09:30:00+00:00"})
    neu["freigabe"] = _f(neu, VORSTANDKEY)
    neu = _hinlegen(fall, neu)
    with pytest.raises(ueb.UebernahmeError, match=alt["snapshot_sha256"][:16]):
        _registriere(tmp_path, fall)
    # Neu gezeichnet unter dem geltenden Auftrag:
    for p in list((fall / "entscheide").glob("A-M4-*.json")) + list(
            (fall / "entscheide").glob("A-M1-*.json")) + list(
            (fall / "entscheide").glob("A-B2-*.json")):
        p.unlink()
    am1 = am1_snapshot("probe-uebernahme", fallauftrag=neu["snapshot_sha256"])
    (fall / "entscheide" / f"A-M1-{am1['snapshot_sha256']}.json").write_text(json.dumps(am1))
    am4 = am4_snapshot("probe-uebernahme", pb1_ledger_sha=_pb1_ledger(fall),
                       fuehrungsprobe_sha=fuehrungsbeleg(fall), fallauftrag=neu["snapshot_sha256"],
                       pins={"am1_snapshot": am1["snapshot_sha256"]})
    (fall / "entscheide" / f"A-M4-{am4['snapshot_sha256']}.json").write_text(json.dumps(am4))
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": am4["snapshot_sha256"]}}), encoding="utf-8")
    assert (_registriere(tmp_path, fall) / "eingang.json").is_file()


def _vorstandswelt(tmp_path: Path, erklaerung: str):
    """Ein Fall (Scope bestand), echt beauftragt mit dem Vorstandsschluessel V0
    (fall_belegen auftrag, gate_entscheid A-M6); A-M1/A-M4 nennen diesen
    Auftrag. Danach Glied 2: Vorstand V0 -> V1 mit ``erklaerung``."""
    from rechner_pipeline import fall as fall_mod
    from tests import freigabe_testschluessel as ft
    from tests import test_betrieb_uebernahme as tbu

    def schreibe(pfad: Path, roh: bytes) -> Path:
        pfad.write_bytes(roh)
        pfad.chmod(0o600)
        return pfad

    keys = tmp_path / "keys"
    keys.mkdir()
    v0 = schreibe(keys / "vorstand-v0.key", ft.VORSTANDKEY)
    v1 = schreibe(keys / "vorstand-v1.key", hashlib.sha256(b"V1").digest() * 2)
    pl = schreibe(keys / "pl.key", hashlib.sha256(b"PL").digest() * 2)
    betrieb = schreibe(keys / "betrieb.key", ft.BETRIEBSKEY)
    linie = ft.suitelinie_anlegen(tmp_path / "linie")
    ord1 = keys / "ordnung1.json"
    ord1.write_bytes(ft.ordnung_bytes())
    fall = tmp_path / "probe-uebernahme"
    fall_mod.anlegen(fall, scope="bestand")
    quelle = tmp_path / "lieferung.csv"
    quelle.write_text("police;vs\n1;100\n", encoding="utf-8")
    fall_mod.registrieren(fall, quelle)
    assert fall_belegen.main([
        "auftrag", "--fall", str(fall), "--zeichnungsordnung", str(ord1),
        "--programmleitung-schluessel", str(pl), "--programmleitung-klasse", "mensch",
        "--auftrag", "migrieren", "--linie", str(linie)]).exit_code == 0
    a6 = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-M6", "--entscheid", "angenommen",
        "--entscheider", "vorstand", "--begruendung", "beauftragt", "--repo-root", str(REPO_ROOT),
        "--linie", str(linie), "--zeichnungsordnung", str(ord1), "--freigabe-schluessel", str(v0)])
    assert a6.exit_code == 0, a6.errors
    auftrag = a6.summary["snapshot_sha256"]
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True, exist_ok=True)
    tbu._zugangsstand(fall / "abgeleitet" / "bestand")
    am1 = tbu.am1_snapshot(fall.name, fallauftrag=auftrag)
    (fall / "entscheide" / f"A-M1-{am1['snapshot_sha256']}.json").write_text(json.dumps(am1))
    am4 = tbu.am4_snapshot(fall.name, pb1_ledger_sha=tbu._pb1_ledger(fall),
                           fuehrungsprobe_sha=tbu.fuehrungsbeleg(fall), fallauftrag=auftrag,
                           pins={"am1_snapshot": am1["snapshot_sha256"]})
    (fall / "entscheide" / f"A-M4-{am4['snapshot_sha256']}.json").write_text(json.dumps(am4))
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": am4["snapshot_sha256"]}}))
    o2 = json.loads(ft.ordnung_bytes())
    o2["rollen"]["mensch/vorstand"]["schluessel_sha256"] = hashlib.sha256(v1.read_bytes()).hexdigest()
    ord2 = keys / "ordnung2.json"
    ord2.write_text(json.dumps(o2, sort_keys=True), encoding="utf-8")
    from rechner_pipeline.models.ordnungslinie import lade_linie_strukturell_zur_anzeige

    glieder, _ = lade_linie_strukturell_zur_anzeige(linie)
    g2 = stand_belegen.main([
        "ordnung", "--linie", str(linie), "--ordnung", str(ord2),
        "--vorgaenger", glieder[-1]["glied_sha256"], "--vorstand-schluessel", str(v0),
        "--fruehere-zeichnungen", f"mensch/vorstand={erklaerung}"])
    assert g2.exit_code == 0, g2.errors
    ring = {hashlib.sha256(k).hexdigest(): k
            for k in (ft.TESTKEY, ft.BETRIEB_FREIGABEKEY, v0.read_bytes(), v1.read_bytes())}
    stand = tbu._mit_config(tmp_path / "daten")
    return lambda: ueb.eingang_anlegen(stand, fall, STICHTAG, schluesselring=ring, linie=linie,
                                       betriebsschluessel=betrieb, zeichnungsordnung=ord2)


def test_i07_verfallen_auf_der_wurzel_laesst_den_zugang_nicht_eintreten(tmp_path):
    """Rot auf 9fa1538: Der Vorstand erklaert seine frueheren Zeichnungen fuer
    verfallen — der Produzent nennt als Folge "jede Annahme jedes Falls" —,
    und der Betrieb registrierte trotzdem. Jetzt verweigert."""
    registriere = _vorstandswelt(tmp_path, "verfallen")
    with pytest.raises(ueb.UebernahmeError) as fehler:
        registriere()
    meldung = str(fehler.value)
    assert "Fallauftrag" in meldung and "verfallen" in meldung, meldung


def test_i07_gueltig_auf_der_wurzel_traegt_weiter(tmp_path):
    """Positivkontrolle: Derselbe Wechsel mit "gueltig" (geordneter Wechsel,
    derselbe Halter) — die Registrierung nimmt an."""
    registriere = _vorstandswelt(tmp_path, "gueltig")
    assert (registriere() / "eingang.json").is_file()


# --------------------------------------------------------------------------- #
# I08: der Betrieb gruendet nur auf dem aktuellen Schema
# --------------------------------------------------------------------------- #


def test_i08_eine_zugangsabnahme_nach_altem_schema_traegt_keinen_eintritt(tmp_path, monkeypatch):
    """Rot auf 9fa1538: A-B2 nach Schema 9 (Gate 4.0.0, ohne fallauftrag),
    signiert mit dem Schluessel von mensch/betrieb, trug den Eintritt.

    Mutationsprobe: die Schema-Pruefung in ``lies_abnahme_snapshot`` entfernen
    -> rot."""
    from rechner_pipeline.models.schemas import P9_GATE_VERSION_JE_SCHEMA, P9Snapshot
    from tests import zugangsabnahme_testhelfer as zh
    from tests.freigabe_testschluessel import BETRIEB_FREIGABEKEY

    echte_naht = zh.schreibe_zugangsabnahme

    def alte_naht(fall, **kw):
        sha = echte_naht(fall, **kw)
        pfad = Path(fall) / "entscheide" / f"A-B2-{sha}.json"
        daten = json.loads(pfad.read_text(encoding="utf-8"))
        pfad.unlink()
        alt = {k: v for k, v in daten.items() if k not in ("snapshot_sha256", "freigabe", "fallauftrag")}
        alt.update({"schema_version": 9, "gate_version": P9_GATE_VERSION_JE_SCHEMA[9]})
        alt["freigabe"] = freigabe_fuer(alt, BETRIEB_FREIGABEKEY)
        alt = _hinlegen(Path(fall), alt)
        assert P9Snapshot.validate_payload(alt) == []
        return alt["snapshot_sha256"]

    monkeypatch.setattr(ueb, "_STANDARD_ZUGANGSABNAHME", alte_naht)
    fall = _betriebsfall(tmp_path)
    with pytest.raises(ueb.UebernahmeError, match=r"A-B2-.*nach Schema 9 — der Betrieb gruendet nur"):
        _registriere(tmp_path, fall)


#: Die Stellen in betrieb/, die das Schema eines Abnahme-Snapshots halten —
#: genau eine: die Lesestelle, durch die jede gruendende Lesung geht
#: (Ratsche mit ==; die Lesungen selbst zaehlt
#: tests/test_abnahme_rolle_klasse.LESESTELLEN).
SCHEMA_WACHEN = [("betrieb/uebernahme.py", "lies_abnahme_snapshot")]


def _schema_wachen(quelle: str, datei: str):
    treffer = []
    for funktion in ast.walk(ast.parse(quelle)):
        if not isinstance(funktion, ast.FunctionDef):
            continue
        for knoten in ast.walk(funktion):
            if isinstance(knoten, ast.Compare) and any(
                    isinstance(n, ast.Name) and n.id == "P9_SNAPSHOT_SCHEMA_VERSION"
                    for n in ast.walk(knoten)):
                treffer.append((datei, funktion.name))
    return treffer


def test_i08_ratsche_eine_schemawache_im_betrieb():
    """Statische Ratsche (benannt): Der Vergleich mit dem aktuellen Schema
    steht in betrieb/ genau einmal, in ``lies_abnahme_snapshot``."""
    gefunden = []
    for pfad in sorted((SRC / "betrieb").rglob("*.py")):
        gefunden += _schema_wachen(pfad.read_text(encoding="utf-8"), str(pfad.relative_to(SRC)))
    assert gefunden == SCHEMA_WACHEN


def test_i08_ratsche_positivkontrolle():
    quelle = ("def a(d):\n    if d.get('schema_version') != P9_SNAPSHOT_SCHEMA_VERSION:\n        x\n"
              "def b(d):\n    return d\n")
    assert _schema_wachen(quelle, "x.py") == [("x.py", "a")]
