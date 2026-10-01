"""Die Erklaerung "verfallen" trifft die LINIE einer Rolle, nicht ihren Namen von damals.

Befund der blinden Pruefrunde I (I01 und I05, hoch, derselbe Fund aus zwei
Linsen; I02, mittel; eine Klasse): Die Wirkung der Erklaerung hing am
ROLLENNAMEN des gepinnten Glieds und an genau EINEM Uebergang —
``abloesung_fehler`` bestimmte die Rolle einmal und beendete die Verfolgung
nach dem ersten ``gueltig``. Gemessen: (1) Umbenennung mit ``gueltig``, danach
"verfallen" auf den Schluessel unter dem neuen Namen — die Zeichnungen des
alten Schluessels trugen weiter, auch eine unter einer aelteren Kopie mit
zurueckgestellter Uhr; (2) der Vorstandsschluessel wandert mit ``gueltig`` zu
einer anderen Rolle und wird dort fuer verfallen erklaert — der Fallauftrag
des Schluessels trug weiter; (3) Vorstand v1 -> v2 ``gueltig``, v2 -> v3
``verfallen`` — der Produzent nannte "jeder Fallauftrag ... traegt nichts
mehr", der v1-Fallauftrag trug weiter. Die Folge, die der Produzent nennt, war
nicht die Wirkung.

Invariante: "verfallen" fuer eine Rolle an einem Glied entwertet JEDE fruehere
Abnahme in der LINIE dieser Rolle (Namen und Schluessel, Kontinuitaet ueber den
Namen ODER den Schluessel), gleich wann und mit welchem ihrer frueheren
Schluessel sie gezeichnet wurde; die Folge, die der Produzent nennt, IST die
Wirkung. Menge: jeder gruendende Leser geht durch
``models.ordnungslinie.damalige_ordnung`` -> ``abloesung_fehler``
(Ratsche in tests/test_ordnungslinie_erklaerung.py); Wirkung UND Folge kommen
aus ``treffer_der_erklaerungen`` (Ratsche unten, ``==``).

Mutationsproben (Rueckmeldung der Runde): ``linie_fortschreiben`` ohne Wirkung
(nur der Name von damals) -> Umbenennung und Wanderung rot; nach dem ersten
``gueltig`` abbrechen -> zweimaliger Wechsel rot; Folge aus einer eigenen
Rechnung statt aus ``getroffene_abnahmen`` -> Eigenschaftstest rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import inspect
import json
import shutil
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rechner_pipeline import fall as fallmod
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.gates import fall_belegen, gate_entscheid
from rechner_pipeline.models import ordnungslinie as ol
from tests.test_ordnungslinie_erklaerung import (
    _anhaengen,
    _betrieb_liest_am4,
    _entscheid,
    _ersetze,
    _fp,
    _ordnung,
    _schluessel,
    _welt,
)
from tests.zeichnung_fixture import (
    VA,
    VORSTAND_SCHLUESSEL_DATEI,
    linie_anlegen,
    mandat_datei,
)

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


def _glieder(linie: Path) -> list:
    glieder, fehler = ol.lade_linie_strukturell_zur_anzeige(linie)
    assert not fehler, fehler
    return glieder


def _uhr_vor(monkeypatch, zeitpunkt: str, *, tage: int = 30) -> None:
    """Die Naht der Uhr des Gates: ``entschieden_am`` ``tage`` vor
    ``zeitpunkt`` — der Halter eines alten Schluessels mit zurueckgestellter Uhr."""
    zeit = (dt.datetime.fromisoformat(zeitpunkt) - dt.timedelta(days=tage)).isoformat()
    monkeypatch.setattr(gate_entscheid, "utc_now", lambda: zeit)


# --------------------------------------------------------------------------- #
# (1) Umbenennung: derselbe Schluessel unter neuem Namen, danach "verfallen"
# --------------------------------------------------------------------------- #

NEUER_NAME = "mensch/aktuariat-leitung"


def _umbenennen(tmp_path: Path, linie: Path) -> dict:
    """Glied 2: mensch/aktuariat heisst jetzt NEUER_NAME (Schluessel, Klasse und
    Gates unveraendert), ``gueltig`` — der Halter ist derselbe."""
    o2 = _ordnung(tmp_path)
    o2["rollen"][NEUER_NAME] = o2["rollen"].pop(VA)
    ergebnis = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={VA: "gueltig"},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return o2


def _neuer_name_verfallen(tmp_path: Path, linie: Path, o2: dict) -> dict:
    """Glied 3: dem Schluessel unter dem neuen Namen wird nicht mehr getraut."""
    o3 = json.loads(json.dumps(o2))
    o3["rollen"][NEUER_NAME]["schluessel_sha256"] = _fp(
        _schluessel(tmp_path / "aussen" / "aktuariat-drei.key"))
    ergebnis = _anhaengen(linie, o3, tmp_path / "o3.json", erklaerung={NEUER_NAME: "verfallen"},
                          vorstand=[tmp_path / VORSTAND_SCHLUESSEL_DATEI])
    assert ergebnis.exit_code == 0, ergebnis.errors
    folge = ergebnis.summary["fruehere_zeichnungen"][NEUER_NAME]
    assert folge.startswith("verfallen: jede fruehere Abnahme ["), folge
    assert "A-M4" in folge and VA in folge, folge
    return o3


def test_umbenennung_dann_verfallen_der_alte_schluessel_unter_der_kopie(tmp_path, monkeypatch):
    """Der Halter des alten Schluessels zeichnet A-M4 unter der aelteren Kopie
    (nur Glied 1), die Uhr 30 Tage vor der Umbenennung. Der Leser des Betriebs
    mit der echten Linie verweigert: Glied 3 hat die Linie der Rolle (alter und
    neuer Name, derselbe Schluessel) fuer verfallen erklaert. Rot auf 9fa1538:
    angenommen (die Verfolgung endete beim ``gueltig`` der Umbenennung)."""
    linie, fall, basis = _welt(tmp_path)
    kopie = tmp_path / "kopie" / "linie"
    shutil.copytree(linie, kopie)
    o2 = _umbenennen(tmp_path, linie)
    _neuer_name_verfallen(tmp_path, linie, o2)
    _uhr_vor(monkeypatch, _glieder(linie)[1]["eingetragen_am"])
    ist = _entscheid(fall, "A-M4", _ersetze(basis, "--linie", kopie))
    assert ist.exit_code == 0, ist.errors          # benannte Grenze: das Gate unter der Kopie
    with pytest.raises(ueb.UebernahmeError) as fehler:
        _betrieb_liest_am4(tmp_path, fall, linie, ist.summary["snapshot_sha256"])
    meldung = str(fehler.value)
    assert "Glied 3" in meldung and NEUER_NAME in meldung and "verfallen erklaert" in meldung, \
        meldung
    assert f"Linie der zeichnenden Rolle {VA}" in meldung, meldung


def test_umbenennung_dann_verfallen_auch_die_rechtmaessig_fruehere(tmp_path):
    """Die rechtmaessige A-M4 vor der Umbenennung: Nach der Umbenennung allein
    traegt sie (Positivkontrolle — ``gueltig``, derselbe Halter); nach
    "verfallen" auf den Schluessel unter dem neuen Namen nicht mehr (die
    Ueberentwertung ist die sichere Richtung und die genannte Folge)."""
    linie, fall, basis = _welt(tmp_path)
    am4 = _entscheid(fall, "A-M4", basis)
    assert am4.exit_code == 0, am4.errors
    sha = am4.summary["snapshot_sha256"]
    o2 = _umbenennen(tmp_path, linie)
    daten, _, verifiziert = _betrieb_liest_am4(tmp_path, fall, linie, sha)
    assert verifiziert and daten["zeichnung"]["rolle"] == VA
    _neuer_name_verfallen(tmp_path, linie, o2)
    with pytest.raises(ueb.UebernahmeError, match="verfallen erklaert"):
        _betrieb_liest_am4(tmp_path, fall, linie, sha)


# --------------------------------------------------------------------------- #
# (2) Wanderung und (3) zweimaliger Wechsel: der Vorstand — gelesen von A-M5
# --------------------------------------------------------------------------- #


def _fall_ohne_auftrag(tmp_path: Path) -> Path:
    fall = tmp_path / "fall"
    fallmod.anlegen(fall)
    quelle = tmp_path / "quelle.txt"
    quelle.write_text("Lieferung der Probe\n", encoding="utf-8")
    fallmod.registrieren(fall, quelle)
    return fall


def _pl(tmp_path: Path) -> Path:
    return _schluessel(tmp_path / "aussen" / "programmleitung.key") \
        if not (tmp_path / "aussen" / "programmleitung.key").exists() \
        else tmp_path / "aussen" / "programmleitung.key"


def _beauftragen(tmp_path: Path, fall: Path, linie: Path, ordnung: Path, ring: list):
    """Vorlage legen und A-M6 zeichnen — unter ``linie`` (die echte oder die
    aeltere Kopie); der letzte Schluessel im Ring zeichnet."""
    daten = json.loads(ordnung.read_text(encoding="utf-8"))
    argv = ["auftrag", "--fall", str(fall), "--linie", str(linie), "--zeichnungsordnung",
            str(ordnung), "--programmleitung-schluessel", str(_pl(tmp_path)),
            "--programmleitung-klasse", "simulation", "--auftrag", "Probe beauftragen"]
    for rolle in fall_belegen.mandatsrollen(daten, "simulation"):
        argv += ["--mandat", f"{rolle}={mandat_datei(fall)}"]
    vorlage = fall_belegen.main(argv)
    assert vorlage.exit_code == 0, vorlage.errors
    args = ["--fall", str(fall), "--linie", str(linie), "--gate", "A-M6", "--entscheid",
            "angenommen", "--entscheider", "vorstand", "--begruendung", "beauftragt",
            "--repo-root", str(REPO), "--zeichnungsordnung", str(ordnung),
            "--mandat", str(mandat_datei(fall))]
    for datei in ring:
        args += ["--freigabe-schluessel", str(datei)]
    ergebnis = gate_entscheid.main(args)
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def _abbrechen(tmp_path: Path, fall: Path, linie: Path, ordnung: Path, ring: list):
    """Der Leser: A-M5 unter der ECHTEN Linie — er haelt den Fallauftrag
    (``fallauftrag_pruefen``) gegen die Linie."""
    vorlage = fall_belegen.main([
        "abbruch", "--fall", str(fall), "--repo-root", str(REPO), "--grund", "Probe",
        "--bestand", "bleibt beim abgebenden Haus", "--uebergabe", "an den Vorstand"])
    assert vorlage.exit_code == 0, vorlage.errors
    args = ["--fall", str(fall), "--linie", str(linie), "--gate", "A-M5", "--entscheid",
            "angenommen", "--entscheider", "programmleitung", "--begruendung", "abbrechen",
            "--repo-root", str(REPO), "--zeichnungsordnung", str(ordnung),
            "--mandat", str(mandat_datei(fall))]
    for datei in [*ring, _pl(tmp_path)]:
        args += ["--freigabe-schluessel", str(datei)]
    return gate_entscheid.main(args)


def _vorstandsfall(tmp_path: Path, monkeypatch, *, wanderung: bool, glied3: bool, angriff: bool):
    """Glied 1: Vorstand v1. Glied 2: v1 -> v2, ``gueltig``; bei ``wanderung``
    haelt danach mensch/beirat den Schluessel v1. Glied 3 (``glied3``): bei
    ``wanderung`` beirat v1 -> b2, sonst Vorstand v2 -> v3, je ``verfallen``.
    Der Fallauftrag mit v1: ``angriff`` — NACH den Gliedern unter der aelteren
    Kopie, Uhr 30 Tage vor Glied 2; sonst rechtmaessig VOR Glied 2."""
    linie = linie_anlegen(tmp_path)
    kopie = tmp_path / "kopie" / "linie"
    shutil.copytree(linie, kopie)
    fall = _fall_ohne_auftrag(tmp_path)
    o1 = tmp_path / "zeichnungsordnung.json"
    v1 = tmp_path / VORSTAND_SCHLUESSEL_DATEI
    if not angriff:
        _beauftragen(tmp_path, fall, linie, o1, [v1])
    v2 = _schluessel(tmp_path / "aussen" / "vorstand-zwei.key")
    o2 = _ordnung(tmp_path)
    o2["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(v2)
    if wanderung:
        o2["rollen"]["mensch/beirat"] = {"schluessel_sha256": _fp(v1),
                                        "schluesselklasse": "simulation", "gates": []}
    zwei = _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={ol.WURZELROLLE: "gueltig"},
                      vorstand=[v1])
    assert zwei.exit_code == 0, zwei.errors
    ordnung, folge = tmp_path / "o2.json", None
    if glied3:
        o3 = json.loads(json.dumps(o2))
        verfallen = "mensch/beirat" if wanderung else ol.WURZELROLLE
        o3["rollen"][verfallen]["schluessel_sha256"] = _fp(
            _schluessel(tmp_path / "aussen" / "drei.key"))
        drei = _anhaengen(linie, o3, tmp_path / "o3.json", erklaerung={verfallen: "verfallen"},
                          vorstand=[v1, v2])
        assert drei.exit_code == 0, drei.errors
        ordnung, folge = tmp_path / "o3.json", drei.summary["fruehere_zeichnungen"][verfallen]
    if angriff:
        _uhr_vor(monkeypatch, _glieder(linie)[1]["eingetragen_am"])
        _beauftragen(tmp_path, fall, kopie, o1, [v1])
        monkeypatch.undo()
    return _abbrechen(tmp_path, fall, linie, ordnung, [v1, v2]), folge


@pytest.mark.parametrize("wanderung", [True, False], ids=["wanderung", "zweimaliger_wechsel"])
@pytest.mark.parametrize("angriff", [True, False], ids=["kopie_uhr_zurueck", "rechtmaessig"])
def test_verfallen_trifft_den_fallauftrag_der_vorstandslinie(tmp_path, monkeypatch, wanderung,
                                                              angriff):
    """(2) v1 wandert mit ``gueltig`` zu mensch/beirat und wird dort fuer
    verfallen erklaert; (3) v1 -> v2 ``gueltig``, v2 -> v3 ``verfallen``. Der
    Fallauftrag mit v1 — rechtmaessig vor Glied 2 oder als Angriff unter der
    Kopie mit zurueckgestellter Uhr — traegt nichts mehr; die Folge, die der
    Produzent zu Glied 3 nannte, sagt genau das (A-M6, Kaskade). Rot auf
    9fa1538: A-M5 angenommen."""
    ergebnis, folge = _vorstandsfall(tmp_path, monkeypatch, wanderung=wanderung, glied3=True,
                                     angriff=angriff)
    assert ergebnis.exit_code != 0, ergebnis.summary
    meldung = ergebnis.errors[0]["message"]
    assert ergebnis.errors[0]["code"] == "fallauftrag", ergebnis.errors
    assert "Glied 3" in meldung and "verfallen erklaert" in meldung, meldung
    # Die Folge, die der Produzent zu Glied 3 nannte, IST diese Wirkung.
    assert folge.startswith("verfallen: jede fruehere Abnahme ['A-M6']"), folge
    assert "jeder Fallauftrag (A-M6) und alles, was darauf gruendet" in folge, folge


@pytest.mark.parametrize("wanderung", [True, False], ids=["wanderung", "zweimaliger_wechsel"])
@pytest.mark.parametrize("angriff", [True, False], ids=["kopie_uhr_zurueck", "rechtmaessig"])
def test_positivkontrolle_ohne_verfallen_traegt_der_fallauftrag(tmp_path, monkeypatch,
                                                                wanderung, angriff):
    """Nur Glied 2 (``gueltig``): Der Fallauftrag mit v1 traegt — rechtmaessig
    und, benannte Grenze (i) des Nachtrags H, auch mit zurueckgestellter Uhr:
    ``gueltig`` ist die Entscheidung des Vorstands, dem Halter weiter zu trauen."""
    ergebnis, _ = _vorstandsfall(tmp_path, monkeypatch, wanderung=wanderung, glied3=False,
                                 angriff=angriff)
    assert ergebnis.exit_code == 0, ergebnis.errors


# --------------------------------------------------------------------------- #
# Eigenschaft: Wirkung im Leser == unabhaengig formulierte Regel; Folge == Wirkung
# --------------------------------------------------------------------------- #

_NAMEN = ("mensch/a", "mensch/b", "mensch/c")
_SCHLUESSEL = tuple(hashlib.sha256(f"k{i}".encode()).hexdigest() for i in range(5))
_GATES = ("A-K2", "A-T1", "A-M4")
_KLASSEN = ("mensch", "simulation")
_START = dt.datetime(2026, 10, 1, 8, tzinfo=dt.timezone.utc)


@st.composite
def _ordnung_strategie(draw) -> dict:
    namen = draw(st.lists(st.sampled_from(_NAMEN), min_size=1, max_size=3, unique=True))
    schluessel = draw(st.permutations(_SCHLUESSEL))
    return {"schema_version": 2, "rollen": {
        n: {"schluessel_sha256": schluessel[k], "schluesselklasse": draw(st.sampled_from(_KLASSEN)),
            "gates": sorted(draw(st.sets(st.sampled_from(_GATES), max_size=3)))}
        for k, n in enumerate(sorted(namen))}}


@st.composite
def _linie_strategie(draw) -> list:
    ordnungen = draw(st.lists(_ordnung_strategie(), min_size=3, max_size=6))
    glieder: list = []
    for j, o in enumerate(ordnungen):
        vorher = ordnungen[j - 1] if j else None
        geminderte = ol.geminderte_rollen(ol.aenderungen(vorher, o)) if j else []
        erklaerung = {r: draw(st.sampled_from(ol.ERKLAERUNGEN)) for r in geminderte}
        glieder.append(ol.baue_glied(
            json.dumps(o, sort_keys=True).encode("utf-8"), nummer=j + 1,
            vorgaenger=glieder[-1]["glied_sha256"] if glieder else None,
            eingetragen_am=(_START + dt.timedelta(hours=j)).isoformat(), vorher=vorher,
            fruehere_zeichnungen=erklaerung))
    return glieder


def _regel(ordnungen: list, erkl: list, eingetragen: list, i: int, name: str, gate: str,
           zeit: dt.datetime) -> "tuple[bool, set]":
    """Die Regel, im Test formuliert (ADR-025, Nachtrag Pruefrunde I) — ohne
    den Code des Lesers: ``(traegt, {(j, rolle, art)})``. Die Linie der Rolle
    sind alle Namen und Schluesseln, die vom gepinnten Glied an ueber denselben
    Namen oder denselben Schluessel erreicht werden (Mengen wachsen nur)."""
    eintrag = ordnungen[i]["rollen"][name]
    fp, klasse = eintrag["schluessel_sha256"], eintrag["schluesselklasse"]
    namen, schluessel = {name}, {fp}
    stufen = [(set(namen), set(schluessel))]
    for m in range(i + 1, len(ordnungen)):
        rollen = ordnungen[m]["rollen"]
        geaendert = True
        while geaendert:
            vorher = (len(namen), len(schluessel))
            schluessel |= {e["schluessel_sha256"] for n, e in rollen.items() if n in namen}
            namen |= {n for n, e in rollen.items() if e["schluessel_sha256"] in schluessel}
            geaendert = (len(namen), len(schluessel)) != vorher
        stufen.append((set(namen), set(schluessel)))

    def halter(m: int):
        n_m = stufen[m - i][0]
        for n, e in ordnungen[m]["rollen"].items():
            if n in n_m and e["schluessel_sha256"] == fp and gate in e["gates"] \
                    and e["schluesselklasse"] == klasse:
                return n
        return None

    ereignisse, traegt = set(), True
    for j in range(i + 1, len(ordnungen)):
        alt, neu = ordnungen[j - 1]["rollen"], ordnungen[j]["rollen"]
        for r, wert in erkl[j].items():
            if wert != "verfallen" or r not in stufen[j - 1 - i][0]:
                continue
            ganz = r not in neu or neu[r]["schluessel_sha256"] != alt[r]["schluessel_sha256"] \
                or neu[r]["schluesselklasse"] != alt[r]["schluesselklasse"]
            if ganz or (gate in alt[r]["gates"] and gate not in neu[r]["gates"]):
                ereignisse.add((j, r, "verfallen"))
                traegt = False
        h_vor, h_nach = halter(j - 1), halter(j)
        if h_vor is not None and h_nach is None and erkl[j].get(h_vor) == "gueltig":
            ereignisse.add((j, h_vor, "gueltig"))
            if not zeit < eingetragen[j]:
                traegt = False
    return traegt, ereignisse


@settings(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(glieder=_linie_strategie(), zeitpunkte=st.lists(st.integers(-1, 6), min_size=1,
                                                         max_size=3))
def test_eigenschaft_wirkung_und_folge_sind_die_regel(glieder, zeitpunkte):
    """Fuer zufaellige Linien aus drei bis sechs Gliedern mit zufaelligen
    Aenderungen und Erklaerungen: Fuer JEDE Abnahme, die unter einem Glied
    zeichnen durfte (jede Rolle, jedes ihrer Gates, mehrere Zeitpunkte),
    stimmt die Wirkung im Leser (``abloesung_fehler``) mit der im Test
    formulierten Regel ueberein; und die Folge, die der Produzent je Glied und
    Rolle nennt (``getroffene_abnahmen``, ``folge_der_erklaerung``), nennt
    GENAU die Gates der Abnahmen, die die Erklaerung trifft."""
    ordnungen = [ol.ordnung_aus(g) for g in glieder]
    erkl = [g["fruehere_zeichnungen"] for g in glieder]
    eingetragen = [dt.datetime.fromisoformat(g["eingetragen_am"]) for g in glieder]
    soll_folge: dict = {}
    for i, o in enumerate(ordnungen):
        for name, e in o["rollen"].items():
            for gate in e["gates"]:
                for z in zeitpunkte:
                    zeit = _START + dt.timedelta(hours=z, minutes=30)
                    snapshot = {"freigabe": {"schluessel_sha256": e["schluessel_sha256"]},
                                "entschieden_am": zeit.isoformat()}
                    traegt, ereignisse = _regel(ordnungen, erkl, eingetragen, i, name, gate, zeit)
                    ist = ol.abloesung_fehler(snapshot, glieder, glieder[i], gate=gate)
                    assert (ist is None) == traegt, (i, name, gate, zeit, ist, ereignisse)
                for j, r, art in ereignisse:
                    if art == erkl[j][r]:
                        soll_folge.setdefault((j, r), set()).add(gate)
    for j in range(1, len(glieder)):
        getroffen = ol.getroffene_abnahmen(glieder, j)
        folge = ol.folge_der_erklaerung(glieder, j)
        assert set(getroffen) == set(erkl[j]) == set(folge)
        for r in erkl[j]:
            gates = sorted(soll_folge.get((j, r), set()))
            assert getroffen[r]["gates"] == gates, (j, r, getroffen[r], gates)
            if gates:
                assert str(gates) in folge[r], (j, r, folge[r])


# --------------------------------------------------------------------------- #
# Ratschen
# --------------------------------------------------------------------------- #


def _funktionen_mit(quelle: str, *, aufruf: str = "", konstante: str = "") -> set:
    """Die Funktionen, die ``aufruf`` rufen bzw. die Zeichenkette ``konstante``
    als Literal fuehren (AST)."""
    gefunden = set()
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, ast.FunctionDef):
            continue
        for d in ast.walk(knoten):
            if aufruf and isinstance(d, ast.Call):
                f = d.func
                if (f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")) == aufruf:
                    gefunden.add(knoten.name)
            if konstante and isinstance(d, ast.Constant) and d.value == konstante:
                gefunden.add(knoten.name)
    return gefunden


def test_ratsche_folge_und_wirkung_kommen_aus_einer_bestimmung():
    """Statische Ratsche (AST, benannt), mit ``==``: Die Erklaerungen eines
    Glieds liest im Paket fuer ihre WIRKUNG nur ``treffer_der_erklaerungen``;
    die Folge (``getroffene_abnahmen``) ruft dieselbe Funktion, der Leser
    (``abloesung_fehler``) ebenso, und die Ausgabe des Produzenten kommt nur aus
    ``folge_der_erklaerung`` -> ``getroffene_abnahmen``. Wer das Feld
    ``fruehere_zeichnungen`` sonst liest, baut, prueft oder vergleicht es."""
    quelle = Path(ol.__file__).read_text(encoding="utf-8")
    assert _funktionen_mit(quelle, aufruf="treffer_der_erklaerungen") \
        == {"abloesung_fehler", "getroffene_abnahmen"}
    assert _funktionen_mit(quelle, aufruf="getroffene_abnahmen") == {"folge_der_erklaerung"}
    gefunden = set()
    for pfad in sorted(SRC.rglob("*.py")):
        for f in _funktionen_mit(pfad.read_text(encoding="utf-8"),
                                 konstante="fruehere_zeichnungen"):
            gefunden.add((pfad.relative_to(SRC).as_posix(), f))
    assert gefunden == {
        ("models/ordnungslinie.py", "baue_glied"),            # baut
        ("models/ordnungslinie.py", "glied_fehler"),          # prueft die Form
        ("models/ordnungslinie.py", "treffer_der_erklaerungen"),  # Wirkung
        ("models/ordnungslinie.py", "getroffene_abnahmen"),   # Folge (dieselben Treffer)
        ("gates/stand_belegen.py", "main"),                   # Wiederholung; Ausgabe
        ("gates/stand_belegen.py", "_ordnung_vorschau"),      # Ausgabe der Vorschau
    }, gefunden
    # Die Zeitregel: ohne Vorgabe fuer die Uhr des Aufrufs.
    p = inspect.signature(ol.neues_glied).parameters["uhr"]
    assert p.kind is inspect.Parameter.KEYWORD_ONLY and p.default is inspect.Parameter.empty


def test_ratsche_positivkontrolle_des_detektors():
    quelle = ("def a():\n    treffer_der_erklaerungen(1)\n"
              "def b(g):\n    return g['fruehere_zeichnungen']\n"
              "def c():\n    x.treffer_der_erklaerungen()\n    return 'andere'\n")
    assert _funktionen_mit(quelle, aufruf="treffer_der_erklaerungen") == {"a", "c"}
    assert _funktionen_mit(quelle, konstante="fruehere_zeichnungen") == {"b"}


def test_die_kette_der_glieder_bleibt_von_der_erklaerung_unberuehrt(tmp_path):
    """Nach ``verfallen`` auf dem Vorstand nach einem ``gueltig``-Wechsel laedt
    die Linie mit allen drei Gliedern (Glied 3 zeichnet v2, Glied 2 v1): Die
    Erklaerung wirkt auf Abnahmen, nie auf Glieder."""
    linie = linie_anlegen(tmp_path)
    v1 = tmp_path / VORSTAND_SCHLUESSEL_DATEI
    v2 = _schluessel(tmp_path / "aussen" / "v2.key")
    o2 = _ordnung(tmp_path)
    o2["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(v2)
    assert _anhaengen(linie, o2, tmp_path / "o2.json", erklaerung={ol.WURZELROLLE: "gueltig"},
                      vorstand=[v1]).exit_code == 0
    o3 = json.loads(json.dumps(o2))
    o3["rollen"][ol.WURZELROLLE]["schluessel_sha256"] = _fp(
        _schluessel(tmp_path / "aussen" / "v3.key"))
    assert _anhaengen(linie, o3, tmp_path / "o3.json", erklaerung={ol.WURZELROLLE: "verfallen"},
                      vorstand=[v1, v2]).exit_code == 0
    ring = {_fp(d): d.read_bytes() for d in (v1, v2)}
    glieder, fehler = ol.lade_linie(linie, ring=ring)
    assert fehler == [] and [g["nummer"] for g in glieder] == [1, 2, 3], fehler


# --- Ruecknahme eines "gueltig": was ein spaeteres "verfallen" erreicht ---------
#
# Bei der Vereinigung von Hand nachgerechnet (ADR-025, Nachtrag Pruefrunde I,
# benannte Grenze i): Die Ruecknahme geht immer, aber nicht immer in einem
# Schritt. Die Ketten fragen die eine Bestimmung direkt; die Erklaerung jedes
# Glieds nennt genau die geminderten Rollen (sonst waere es nicht anhaengbar).

_V = {"mensch/vorstand": {"schluessel_sha256": "KV", "gates": ["A-Z1", "A-M6"],
                          "schluesselklasse": "produktion"}}


def _r(schluessel: str, gates: list) -> dict:
    return {"schluessel_sha256": schluessel, "gates": gates, "schluesselklasse": "produktion"}


def _kette(*stufen) -> list:
    glieder, vorher = [], None
    for nummer, (rollen, erklaerung) in enumerate(stufen, 1):
        if vorher is not None:
            assert sorted(erklaerung) == ol.geminderte_rollen(
                ol.aenderungen({"rollen": vorher}, {"rollen": rollen}))
        glieder.append({"nummer": nummer, "ordnung_text": json.dumps({"rollen": rollen}),
                        "fruehere_zeichnungen": erklaerung})
        vorher = rollen
    return glieder


RUECKNAHME_KETTEN = {
    # "verfallen" an einem Glied, das nur ein Gate entzieht, trifft nur dieses
    # Gate: die A-M1, mit "gueltig" an Glied 2 entzogen, bleibt bei der Zeitregel.
    "verfallen_am_gate_trifft_nur_dieses_gate": (
        [({**_V, "akt": _r("K1", ["A-M1", "A-M4"])}, {}),
         ({**_V, "akt": _r("K1", ["A-M4"])}, {"akt": "gueltig"}),
         ({**_V, "akt": _r("K2", ["A-M4"])}, {"akt": "gueltig"}),
         ({**_V, "akt": _r("K2", [])}, {"akt": "verfallen"})],
        "A-M1", [(1, "akt", "gueltig")]),
    # ... zurueckgenommen wird es von einer Minderung, die den Schluessel trifft.
    "verfallen_am_schluessel_nimmt_das_gate_zurueck": (
        [({**_V, "akt": _r("K1", ["A-M1", "A-M4"])}, {}),
         ({**_V, "akt": _r("K1", ["A-M4"])}, {"akt": "gueltig"}),
         ({**_V, "akt": _r("K2", ["A-M4"])}, {"akt": "verfallen"})],
        "A-M1", [(1, "akt", "gueltig"), (2, "akt", "verfallen")]),
    # Name UND Schluessel verlassen die Ordnung mit "gueltig": die Linie reisst,
    # das "verfallen" einer fremden Rolle erreicht die Abnahme nicht.
    "linie_reisst_wenn_name_und_schluessel_gehen": (
        [({**_V, "akt": _r("K1", ["A-M4"])}, {}),
         ({**_V, "neu": _r("K2", ["A-M4"])}, {"akt": "gueltig"}),
         ({**_V}, {"neu": "verfallen"})],
        "A-M4", [(1, "akt", "gueltig")]),
    # ... der Umweg: den Namen wieder eintragen und mit "verfallen" entfernen.
    "ruecknahme_ueber_den_wieder_eingetragenen_namen": (
        [({**_V, "akt": _r("K1", ["A-M4"])}, {}),
         ({**_V}, {"akt": "gueltig"}),
         ({**_V, "akt": _r("K9", [])}, {}),
         ({**_V}, {"akt": "verfallen"})],
        "A-M4", [(1, "akt", "gueltig"), (3, "akt", "verfallen")]),
}


@pytest.mark.parametrize("name", sorted(RUECKNAHME_KETTEN))
def test_ruecknahme_eines_gueltig_was_ein_spaeteres_verfallen_erreicht(name):
    stufen, gate, erwartet = RUECKNAHME_KETTEN[name]
    assert ol.treffer_der_erklaerungen(
        _kette(*stufen), 0, rolle="akt", schluessel_sha256="K1", gate=gate,
        klasse="produktion") == erwartet
