"""Pruefrunde J, Bestand und Uebernahme.

**J05 — ein Ledger ohne Zeile traegt keinen Vorgang.** Die Jahresgrenze der
Vorgaenge (``bestand.vorbedingungen.vorgangsjahr_fehler``) waehlte die
Ledgerzeilen bekannter Vertraege mit einer LISTE von Wahrheitswerten. Bei null
Zeilen ist die Liste leer, und eine leere Liste waehlt in pandas SPALTEN; der
Ledger verlor seine Spalten und der naechste Zugriff warf ``KeyError
'police_id'``. Ein gueltiger leerer Lauf des echten Produzenten (Fortschreibung
aus dem Nichts, ADR-020, Horizont vor dem ersten Neuzugang: null Vertraege,
null Buchungen) fiel durch P-B1 (Exit 20), den Abschluss (Exit 2), den Bericht
und die Registrierungsvorbedingung — ein FEHLENDER Ledger wurde angenommen.
Regression der Fix-Runde I (I10).
Invariante: Jeder Leser nimmt den leeren Lauf an wie den Lauf ohne Ledger.
Klasse: eine boolesche Liste als Zeilenmaske eines DataFrame (``df[[... for
...]]`` oder ``df[name]`` mit ``name = [... for ...]``). Menge (AST ueber
``src/rechner_pipeline``, Stand 90ee7e9): zwei Stellen —
``bestand/vorbedingungen.py:vorgangsjahr_fehler`` (der Fund, jetzt ein
numpy-Feld) und ``betrieb/tageslauf.py:_gebuchte_reduktionen`` (durch
``if not len(reduktionen): return`` vor der leeren Maske geschuetzt; nicht in
diesem Block geaendert, von der Ratsche namentlich gefuehrt). Listen aus
Spaltennamen (``df[[n for n, _ in SPALTEN]]``) sind keine Masken und zaehlen
nicht. Ratsche: ``test_j05_ratsche_keine_listenmaske`` (``==``, mit
Positivkontrolle des Detektors).
Nachbar im selben Lauf: Der Bericht (``bestand.report``) formatierte den
Zeitraum des Bestands aus NaN und warf; ein Bestand ohne Vertrag heisst jetzt
so.
Mutationsproben: die Liste zurueck in ``vorgangsjahr_fehler`` -> 5 rot (die
vier Leser des leeren Laufs und die Ratsche); die Wache im Bericht entfernt
-> 1 rot.

**J04 — eine beitragsfrei gelieferte Erhoehungsserie behaelt ihre
Bausteine, wo eine Tarifregel je Baustein greift.** Die Uebernahme fasste die
Serie zu EINEM Baustein mit der beitragsfreien Gesamtsumme zusammen
(``_serienzustand``, Ein-Punkt-Inversion). Unter dem Tarifwerk der Lieferung
(Stornoabzug je Baustein, Teilkuendigung nur der Grundversicherung) ist das
nicht wertgleich: Rueckkauf je zusammengefasster Scheibe um den
Mindestabzug zu hoch, Teilkuendigung zahlte zu viel aus. Alle Leser waren
gruen, weil sie denselben zusammengefassten Zustand lasen.
Invariante: Der Zustand der Uebernahme traegt die Bausteine, wenn eine Regel
der Spez nicht homogen in der beitragsfreien Gesamtsumme ist
(``migrationszugang.tarifwerk_homogen_in_bfr_summe``: Stornoabzug je
Baustein, Teilkuendigung nur der Grundversicherung; gamma1 der Scheiben und
das Deckungskapital sind homogen und gehoeren nicht dazu); kann sie sie nicht
belegen, verweigert sie benannt. Menge: die Aufrufer der Ein-Punkt-Inversion
(drei, Ratsche) und die Leser, die Scheiben UND Freistellung zusammen
verweigerten oder nur den Grundbaustein rechneten (aktuarieller Test,
Migrationssuite, Verankerung; Ratsche). Im Fixture des zweiten Laufs sechs
Vertraege (7000061, 7000106, 7000174, 7000300, 7000863, 7001003).
Mutationsproben: Zweig abgeschaltet -> 8 rot; Verankerung ohne den Zweig ->
6 rot (Fixture); Migrationssuite ohne den Zweig -> 3 rot; Teilkuendigung
nach Erhoehung ohne Anteil uebersprungen -> 1 rot.

**J06 — ein Vorgang der Vorgeschichte zwischen zwei Jahrestagen.** Siehe
den Abschnitt unten. Mutationsprobe: die Wache in ``baue`` abgeschaltet ->
3 rot.

Knoten: klv
"""

from __future__ import annotations

import ast
import datetime as _dt
import shutil
from pathlib import Path
from typing import Dict, List, Set

import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung, cli_report
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.gates import bestand_validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
CONFIG = REPO_ROOT / "configs" / "bestand_klv.toml"


# --------------------------------------------------------------------------- #
# J05 — der leere Lauf
# --------------------------------------------------------------------------- #

LEER_TAG = _dt.date(2026, 1, 15)


@pytest.fixture(scope="module")
def leerer_lauf(tmp_path_factory) -> Path:
    """Der ECHTE Produzent: Fortschreibung aus dem Nichts mit Neuzugang ab
    und Horizont am selben Tag, an dem kein Neuzugang faellt."""
    ziel = tmp_path_factory.mktemp("leer") / "lauf"
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--bis", LEER_TAG.isoformat(),
        "--neuzugang-ab", LEER_TAG.isoformat(), "--out-dir", str(ziel)]) == 0
    # Die Welt ist die gemeinte: null Vertraege, ein Ledger ohne Zeile.
    assert len(read_portfolio(ziel / "bestand_gesamt.parquet")) == 0
    assert (ziel / "ledger.parquet").is_file()
    assert len(read_portfolio(ziel / "ledger.parquet")) == 0
    return ziel


def _pb1_argumente(lauf: Path, tmp: Path, *, mit_ledger: bool) -> List[str]:
    argv = ["--portfolio", str(lauf / "bestand_gesamt.parquet"),
            "--historie", str(lauf / "historie.parquet"),
            "--scheiben", str(lauf / "scheiben.parquet"),
            "--config", str(CONFIG), "--diagnostics-dir", str(tmp / "diag")]
    if mit_ledger:   # --bis gehoert zum Ledger (Vertrag des Gates)
        argv += ["--ledger", str(lauf / "ledger.parquet"), "--bis", LEER_TAG.isoformat()]
    return argv


@pytest.mark.parametrize("mit_ledger", [True, False])
def test_j05_pb1_nimmt_den_leeren_lauf_an_wie_den_ohne_ledger(leerer_lauf, tmp_path, mit_ledger):
    """Auf 90ee7e9 rot mit Ledger: Exit 20, Meldung "'police_id'". Ohne
    Ledger (Positivkontrolle) gruen — beide Wege muessen gleich urteilen."""
    ergebnis = bestand_validate.main(_pb1_argumente(leerer_lauf, tmp_path, mit_ledger=mit_ledger))
    assert ergebnis.exit_code == 0, [e["message"] for e in ergebnis.errors][:3]


def test_j05_abschluss_auf_dem_leeren_lauf(leerer_lauf, tmp_path):
    """Auf 90ee7e9 rot: Exit 2, "bestand_abschluss: 'police_id'"."""
    out = tmp_path / "abschluss"
    assert cli_abschluss.main([
        "--config", str(CONFIG), "--lauf", str(leerer_lauf),
        "--stichtag", LEER_TAG.isoformat(), "--bis", LEER_TAG.isoformat(),
        "--out-dir", str(out)]) == 0
    assert len(read_portfolio(out / f"abschluss_{LEER_TAG.isoformat()}.parquet")) == 0


def test_j05_bericht_auf_dem_leeren_lauf(leerer_lauf, tmp_path):
    """Der Bericht liest den Lauf durch dieselbe Engine."""
    assert cli_report.main([
        "--portfolio", str(leerer_lauf / "bestand_gesamt.parquet"),
        "--historie", str(leerer_lauf / "historie.parquet"),
        "--ledger", str(leerer_lauf / "ledger.parquet"),
        "--scheiben", str(leerer_lauf / "scheiben.parquet"),
        "--config", str(CONFIG), "--bis", LEER_TAG.isoformat(),
        "--stichtage", LEER_TAG.isoformat(),
        "--out", str(tmp_path / "bericht.md")]) == 0


def test_j05_registrierungsvorbedingung_auf_dem_leeren_lauf(leerer_lauf, tmp_path):
    """Die Vorbedingung der Registrierung (dieselbe Funktion wie die Wache des
    Tageslaufs) ueber den leeren Eingang: keine Meldung."""
    from rechner_pipeline.betrieb.uebernahme import _eingang_pb1_fehler

    eingang = tmp_path / "eingang"
    eingang.mkdir()
    for datei in leerer_lauf.glob("*.parquet"):
        name = "bestand.parquet" if datei.name == "bestand_gesamt.parquet" else datei.name
        shutil.copyfile(datei, eingang / name)
    assert _eingang_pb1_fehler(eingang, LEER_TAG, CONFIG) == []


def _listenmasken(quelltext: str) -> List[str]:
    """Die Funktionen (Name), in denen eine boolesche Liste ein DataFrame
    indiziert: ``x[[<Vergleich> for ...]]`` oder ``x[name]`` mit ``name`` an
    eine Listenabstraktion ueber einen Vergleich/Wahrheitswert gebunden.
    ``.loc``/``.iloc`` waehlen mit einer leeren Liste Zeilen und zaehlen nicht."""
    def boolesch(knoten: ast.AST) -> bool:
        return isinstance(knoten, ast.ListComp) and isinstance(
            knoten.elt, (ast.Compare, ast.BoolOp)) or (
            isinstance(knoten, ast.ListComp) and isinstance(knoten.elt, ast.UnaryOp)
            and isinstance(knoten.elt.op, ast.Not))

    treffer: List[str] = []
    baum = ast.parse(quelltext)
    for f in ast.walk(baum):
        if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        gebunden: Set[str] = {
            z.targets[0].id for z in ast.walk(f)
            if isinstance(z, ast.Assign) and len(z.targets) == 1
            and isinstance(z.targets[0], ast.Name) and boolesch(z.value)}
        for s in ast.walk(f):
            if not isinstance(s, ast.Subscript):
                continue
            if isinstance(s.value, ast.Attribute) and s.value.attr in ("loc", "iloc"):
                continue
            if boolesch(s.slice) or (isinstance(s.slice, ast.Name) and s.slice.id in gebunden):
                treffer.append(f.name)
    return treffer


def test_j05_ratsche_keine_listenmaske():
    """Ratsche (statisch, ``==``): Die Menge der Listenmasken in
    ``src/rechner_pipeline`` ist genau die eine geschuetzte Stelle im
    Tageslauf. Positivkontrolle: Der Detektor findet die Form des Funds und
    die gebundene Form, und ignoriert Spaltenlisten."""
    probe = (
        "def a(l, v):\n    return l[[int(p) in v for p in l['police_id']]]\n"
        "def b(r, g):\n    m = [x in g for x in r['id']]\n    return r[m]\n"
        "def c(df, S):\n    return df[[n for n, _ in S]]\n")
    assert _listenmasken(probe) == ["a", "b"]

    gefunden = set()
    for pfad in sorted(SRC.rglob("*.py")):
        for name in _listenmasken(pfad.read_text("utf-8")):
            gefunden.add(f"{pfad.relative_to(SRC).as_posix()}:{name}")
    assert gefunden == {"betrieb/tageslauf.py:_gebuchte_reduktionen"}


# --------------------------------------------------------------------------- #
# J04 — die beitragsfrei gelieferte Erhoehungsserie behaelt ihre Bausteine
# --------------------------------------------------------------------------- #
#
# Unabhaengiges Soll: Die Bausteine baut der Test selbst (Satz auf die
# Gesamtsumme davor, Tarifplan KLV 7), ihre beitragsfreien Summen aus dem
# Umwandlungsfaktor JE BAUSTEIN (``Rechenkern.beitragsfreie_summe``), die
# Reserve je Einheit beitragsfreier Summe aus dem Grundbaustein
# (``monatsreserve_beitragsfrei``), den Stornoabzug nach der Regel des
# Tarifplans (Satz mal Summe minus Reserve, Mindest- und Hoechstbetrag) JE
# BAUSTEIN. Das Ist ist die Vorgangsfolge des Kerns auf dem Zustand, den die
# Uebernahme schreibt (``_serienzustand``) — nie dieselbe Funktion.

PEX_JAHR = 3
ERH_JAHRE = (1, 2)
SATZ = 0.05
BFR_GELIEFERT = 20000.0


def _mp_felder() -> Dict:
    import json

    spez = json.loads((REPO_ROOT / "tests" / "fixtures" / "baldrian2_e2e"
                       / "klv-tg2015.spez.json").read_text(encoding="utf-8"))
    zelle = next(z for z in spez["zellen"]
                 if z["auspraegungen"] == {"status": "nichtraucher", "tarifart": "einzel"})
    return {"x": 40, "sex": "M", "n": 20, "t": 20, "zw": 1, "sum_insured": 1.0,
            **zelle["model_point"]}


def _zustand(*, stoab_je_baustein: bool, tku_umfang: str, satz=SATZ, folge=None,
             red_anteile=None, red_verfahren="teilkuendigung"):
    from rechner_pipeline.gates.migrationssuite_lauf import _serienzustand

    folge = folge or ([("ERH", j, f"01.01.{2015 + j}") for j in ERH_JAHRE]
                      + [("PEX", PEX_JAHR, f"01.01.{2015 + PEX_JAHR}")])
    return _serienzustand(
        "1", folge, _mp_felder(), erlsumme=BFR_GELIEFERT, erhoehungssatz=satz,
        red_anteile=red_anteile or {}, red_anteile_je_datum={},
        scheiben_mit_gamma1=True, red_verfahren=red_verfahren,
        tku_umfang=tku_umfang, stoab_je_baustein=stoab_je_baustein)


def _soll_bausteine():
    """(Jahr, beitragsfreie Summe) je Baustein, unabhaengig gebaut."""
    from rechner_pipeline.kern import ModelPoint, Rechenkern
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe

    grund = ModelPoint(**_mp_felder())
    rel = [(0, 1.0)]
    for j in ERH_JAHRE:
        rel.append((j, SATZ * sum(r for _, r in rel)))
    faktoren = []
    for j, r in rel:
        mp = grund if j == 0 else erhoehungs_scheibe(grund, j, 1.0, gamma1_uebernehmen=True)
        faktoren.append((j, r, Rechenkern(mp).beitragsfreie_summe(PEX_JAHR - j)))
    s0 = BFR_GELIEFERT / sum(r * b for _, r, b in faktoren)
    return [(j, s0 * r * b) for j, r, b in faktoren]


def _rate(monate: int) -> float:
    """Reserve je Einheit beitragsfreier Summe (Grundbaustein)."""
    from rechner_pipeline.kern import ModelPoint, Rechenkern

    k = Rechenkern(ModelPoint(**_mp_felder()))
    return k.monatsreserve_beitragsfrei(PEX_JAHR, monate) / k.beitragsfreie_summe(PEX_JAHR)


def _abzug(summe: float, reserve: float) -> float:
    f = _mp_felder()
    return min(f["stoab_max"], max(f["stoab_min"], f["stoab_satz"] * (summe - reserve)))


def _folge(zustand, vorgaenge=(), *, stoab_je_baustein=True, tku_umfang="grundversicherung"):
    from rechner_pipeline.kern import ModelPoint, Rechenkern
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe
    from rechner_pipeline.kern.vorgangsfolge import Vorgangsfolge

    grund = ModelPoint(**{**_mp_felder(), "sum_insured": float(zustand["sum_insured"])})
    kerne = [(int(j), Rechenkern(erhoehungs_scheibe(grund, int(j), float(s),
                                                    gamma1_uebernehmen=True)))
             for j, s in zustand.get("scheiben", ())]
    return Vorgangsfolge(Rechenkern(grund), kerne, list(vorgaenge),
                         pex_jahr=int(zustand["beitragsfrei_seit_jahr"]),
                         stoab_je_baustein=stoab_je_baustein, tku_umfang=tku_umfang)


def test_j04_rueckkauf_mit_abzug_je_baustein_auf_dem_uebernommenen_zustand():
    """Auf 90ee7e9 rot: Der Zustand trug EINEN Baustein, der Rueckkaufswert
    einen Abzug statt drei."""
    zustand = _zustand(stoab_je_baustein=True, tku_umfang="grundversicherung")
    assert [j for j, _ in zustand.get("scheiben", ())] == list(ERH_JAHRE), zustand
    m = 132
    soll = sum(sb * _rate(m) - _abzug(sb, sb * _rate(m)) for _, sb in _soll_bausteine())
    w = _folge(zustand).stand_am(m).werte(m)
    assert w["vs_bfr"] == pytest.approx(BFR_GELIEFERT, abs=0.005)
    assert w["rueckkaufswert"] == pytest.approx(soll, abs=0.02), (w["rueckkaufswert"], soll)


def test_j04_teilkuendigung_nur_der_grundversicherung_auf_dem_uebernommenen_zustand():
    """Auf 90ee7e9 rot: die Teilkuendigung kuerzte die zusammengefasste
    Summe (zu viel ausgezahlt, zu wenig verbleibende Summe)."""
    from rechner_pipeline.kern.vorgangsfolge import vorgang

    zustand = _zustand(stoab_je_baustein=True, tku_umfang="grundversicherung")
    a, f = 13, 0.7
    e = _folge(zustand, [vorgang(a, f, "teilkuendigung")]).ergebnis(a, "TKU")
    bausteine = _soll_bausteine()
    s_grund = bausteine[0][1]
    d_grund = s_grund * _rate(12 * a)
    assert e.vs_neu == pytest.approx(f * s_grund + sum(s for _, s in bausteine[1:]), abs=0.02)
    assert e.auszahlung == pytest.approx((1 - f) * (d_grund - _abzug(s_grund, d_grund)), abs=0.02)


def test_j04_positivkontrolle_eigenes_tarifwerk_bleibt_zusammengefasst_und_wertgleich():
    """Homogenes Tarifwerk (Abzug vertragsweit, Teilkuendigung aller
    Bausteine): Die Uebernahme fasst weiter zusammen, und das ist wertgleich —
    Rueckkauf und Teilkuendigung treffen das Soll aus der Gesamtsumme."""
    from rechner_pipeline.kern.vorgangsfolge import vorgang

    zustand = _zustand(stoab_je_baustein=False, tku_umfang="alle_bausteine")
    assert not zustand.get("scheiben"), zustand
    m = 132
    d = BFR_GELIEFERT * _rate(m)
    w = _folge(zustand, stoab_je_baustein=False, tku_umfang="alle_bausteine").stand_am(m).werte(m)
    assert w["rueckkaufswert"] == pytest.approx(d - _abzug(BFR_GELIEFERT, d), abs=0.02)
    e = _folge(zustand, [vorgang(13, 0.7, "teilkuendigung")], stoab_je_baustein=False,
               tku_umfang="alle_bausteine").ergebnis(13, "TKU")
    assert e.vs_neu == pytest.approx(0.7 * BFR_GELIEFERT, abs=0.02)


@pytest.mark.parametrize("fall, text", [
    ("ohne_satz", "ohne belegten Dynamiksatz"),
    ("tku_nach_erh_ohne_anteil", "nach einer Erhoehung ohne gueltigen Anteil"),
    ("tku_nach_pex", "Teilkuendigung nach der Freistellung"),
    ("echte_herabsetzung", "echte Herabsetzung im Jahr 2"),
])
def test_j04_nicht_belegbare_struktur_wird_benannt_verweigert(fall, text):
    """Kann die Uebernahme die Bausteine nicht belegen, verweigert sie
    benannt (``MigrationszugangFehler`` -> Warnung -> ``verweigere_unbestimmte``)
    statt still zusammenzufassen."""
    from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler

    kw: Dict = {}
    if fall == "ohne_satz":
        kw["satz"] = None
    elif fall == "tku_nach_erh_ohne_anteil":
        kw["folge"] = [("ERH", 1, "01.01.2016"), ("RED", 2, "01.01.2017"),
                       ("PEX", 3, "01.01.2018")]
    elif fall == "tku_nach_pex":
        kw["folge"] = [("ERH", 1, "01.01.2016"), ("PEX", 3, "01.01.2018"),
                       ("RED", 5, "01.01.2020")]
    else:
        # Die Quelle kennt eine Herabsetzung (Uebersetzungsregel: vor t eine
        # echte Herabsetzung) — der Vertrag ist geteilt.
        kw["folge"] = [("ERH", 1, "01.01.2016"), ("RED", 2, "01.01.2017"),
                       ("PEX", 3, "01.01.2018")]
        kw["red_verfahren"] = "prospektiv"
        kw["red_anteile"] = {"1": 0.6}
    with pytest.raises(MigrationszugangFehler, match=text):
        _zustand(stoab_je_baustein=True, tku_umfang="grundversicherung", **kw)


def test_j04_teilkuendigung_vor_der_ersten_erhoehung_braucht_keinen_anteil():
    """Eine Teilkuendigung vor jeder Erhoehung skaliert die ganze Kette: die
    Bausteine sind ohne ihren Anteil bestimmt (Fixture: 7000174, 7000300,
    7000863). Ihr Jahr steht als unbestimmter Anteil im Zustand."""
    zustand = _zustand(stoab_je_baustein=True, tku_umfang="grundversicherung",
                       folge=[("RED", 1, "01.01.2016"), ("ERH", 2, "01.01.2017"),
                              ("PEX", 3, "01.01.2018")])
    assert [j for j, _ in zustand["scheiben"]] == [2]
    assert zustand["absetzungsanteil_unbestimmt"] == (1,)
    w = _folge(zustand).stand_am(36).werte(36)
    assert w["vs_bfr"] == pytest.approx(BFR_GELIEFERT, abs=0.005)


def _aufrufer(quelltext: str, name: str) -> List[str]:
    aus = []
    for f in ast.walk(ast.parse(quelltext)):
        if isinstance(f, ast.FunctionDef):
            for c in ast.walk(f):
                if isinstance(c, ast.Call) and getattr(
                        c.func, "id", getattr(c.func, "attr", None)) == name:
                    aus.append(f.name)
    return aus


def test_j04_ratsche_die_zusammenfassung_steht_hinter_der_homogenitaetsfrage():
    """Ratsche (statisch, ``==``): Die Ein-Punkt-Inversion
    (``leite_pex_ursprungssumme_ab``) wird in ``src`` an genau drei Stellen
    gerufen — der Einzel-Freistellung der Pruefstrecke, der Umbuchung der
    Uebernahme (ein Vertrag aus der Lieferzeile) und der Serie in
    ``_serienzustand``; dort steht sie hinter
    ``tarifwerk_homogen_in_bfr_summe``. Kommt eine Stelle dazu, muss hier
    entschieden werden, ob sie eine Serie zusammenfasst. Positivkontrolle:
    Der Detektor findet einen Aufruf in einer Probe."""
    assert _aufrufer("def p():\n    leite_pex_ursprungssumme_ab(1)\n",
                     "leite_pex_ursprungssumme_ab") == ["p"]
    gefunden = sorted(
        f"{p.relative_to(SRC).as_posix()}:{n}" for p in SRC.rglob("*.py")
        for n in _aufrufer(p.read_text("utf-8"), "leite_pex_ursprungssumme_ab"))
    assert gefunden == ["gates/bestand_uebernehmen.py:_beitragsfreie_uebernahme",
                        "gates/migrationssuite_lauf.py:_serienzustand",
                        "gates/migrationssuite_lauf.py:anfangszustaende_je_police"], gefunden
    assert "_serienzustand" in _aufrufer(
        (SRC / "gates" / "migrationssuite_lauf.py").read_text("utf-8"),
        "tarifwerk_homogen_in_bfr_summe")


def test_j04_ratsche_jeder_leser_fuehrt_bausteine_und_freistellung_ueber_die_folge():
    """Ratsche (statisch, ``==``): Die Leser des Anfangszustands, die eine
    beitragsfreie Uebernahme MIT Scheiben vorher verweigerten oder nur den
    Grundbaustein rechneten, fuehren sie ueber die Vorgangsfolge: der
    aktuarielle Test, die Migrationssuite und die Verankerung. Ihre
    Wegwahl-Funktionen pruefen beides zusammen (``scheiben`` UND
    ``beitragsfrei_seit_jahr`` bzw. ``pex``)."""
    def prueft_beides(pfad: Path, funktion: str, namen: Set[str]) -> bool:
        baum = ast.parse(pfad.read_text("utf-8"))
        f = next(x for x in ast.walk(baum) if isinstance(x, ast.FunctionDef) and x.name == funktion)
        for knoten in ast.walk(f):
            if isinstance(knoten, ast.BoolOp) and isinstance(knoten.op, ast.And):
                gelesen = {getattr(n, "attr", getattr(n, "id", None)) for n in ast.walk(knoten)}
                if namen <= gelesen:
                    return True
        return False

    assert prueft_beides(SRC / "qa" / "aktuarieller_test.py", "_mit_folge",
                         {"scheiben", "beitragsfrei_seit_jahr"})
    assert prueft_beides(SRC / "qa" / "migrationssuite.py", "_mit_vorgangsfolge",
                         {"scheiben", "beitragsfrei_seit_jahr"})
    assert prueft_beides(SRC / "gates" / "verankerung_belegen.py", "_zustands_dk_prosp",
                         {"scheiben", "pex"})


# --------------------------------------------------------------------------- #
# J06 — ein Vorgang der Vorgeschichte zwischen zwei Jahrestagen
# --------------------------------------------------------------------------- #
#
# Invariante: Die Uebernahme prueft die Jahrestags-Konvention in JEDEM Modus
# an EINER Stelle (``migrationssuite_lauf.vorgeschichte_jahrestag_fehler``),
# gerufen aus ``bestand_uebernehmen.baue`` (jeder Modus) und der Pruefstrecke.
# Matrix der Produzenten (gemessen): Die Ereignis-Engine bucht jeden Vorgang
# am Jahrestag (``bestand/ereignisse.py``), der Betrieb bucht ueber sie; die
# Uebernahme war der einzige Produzent, der eine unterjaehrige Freistellung
# annahm. Die Leser (P-B1, Fortschreibung, Abschluss) werden NICHT verschaerft.


def _baue_mit(vorgeschichte):
    from rechner_pipeline.gates.bestand_uebernehmen import baue

    gen = {g.name: g for g in load_config(CONFIG).generationen}["KLV-2015"]
    zeile = {"police_id": 7001, "beginn": "2015-01-01", "entry_age": 40, "duration": 20,
             "premium_duration": 20, "sex": "M", "sum_insured": 20000.0, "zahlweise": 1}
    return baue([zeile], tarif_generation="KLV-2015", produkt="klv",
                stichtag=_dt.date(2026, 1, 1), vorgeschichte={"7001": vorgeschichte},
                generationsfelder=gen.generation_fields())


@pytest.mark.parametrize("art, datum", [("PEX", _dt.date(2019, 7, 1)),
                                        ("ERH", _dt.date(2017, 3, 1)),
                                        ("RED", _dt.date(2018, 12, 1))])
def test_j06_unterjaehriger_vorgang_wird_in_jedem_modus_verweigert(art, datum):
    """Auf 90ee7e9 rot: ``baue`` (der Produzent, ohne --anfangszustand) nahm
    die Freistellung im Monat 54 an und rundete auf Jahr 4 ab."""
    with pytest.raises(SystemExit, match="nicht auf dem Vertragsjahrestag"):
        _baue_mit([(art, datum)])


def test_j06_positivkontrolle_am_jahrestag_angenommen():
    _stamm, historie, _ledger, _h = _baue_mit([("PEX", _dt.date(2019, 1, 1))])
    assert list(historie["status_code"]) == ["PEX"]


def test_j06_ratsche_eine_stelle_der_jahrestagsregel():
    """Ratsche (statisch, ``==``): Der Befundtext der Jahrestags-Konvention
    steht in ``src`` in genau einer Funktion, und die drei Leser der
    Vorgeschichte rufen sie. Positivkontrolle: der Detektor findet den Text
    in einer Probe."""
    text = "Vertragsjahrestag — Lieferung klaeren, nicht runden"

    def mit_text(quelltext: str) -> List[str]:
        return [f.name for f in ast.walk(ast.parse(quelltext))
                if isinstance(f, ast.FunctionDef) and any(
                    isinstance(c, ast.Constant) and isinstance(c.value, str)
                    and text in c.value for c in ast.walk(f))]

    assert mit_text(f"def p():\n    return '{text}'\n") == ["p"]
    gefunden = sorted(f"{p.relative_to(SRC).as_posix()}:{n}" for p in SRC.rglob("*.py")
                      for n in mit_text(p.read_text("utf-8")))
    assert gefunden == ["gates/migrationssuite_lauf.py:vorgeschichte_jahrestag_fehler"], gefunden
    assert "baue" in _aufrufer((SRC / "gates" / "bestand_uebernehmen.py").read_text("utf-8"),
                               "vorgeschichte_jahrestag_fehler")
    rufer = _aufrufer((SRC / "gates" / "migrationssuite_lauf.py").read_text("utf-8"),
                      "vorgeschichte_jahrestag_fehler")
    assert {"anfangszustaende_je_police", "beitragsfrei_seit_jahr_je_police"} <= set(rufer)
