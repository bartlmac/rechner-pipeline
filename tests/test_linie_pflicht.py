"""Die Ordnungslinie ist Pflicht — fuer jedes Zeichnen und jedes Gruenden (ADR-025, Nachtrag 2026-10-01).

Lage vorher: ``gate_entscheid`` nahm ``--linie`` mit ``default=None``; ohne
Linie wurde die Rolle gegen die HEUTIGE Ordnung gehalten und der
``ordnung_sha256`` eines Snapshots gegen nichts. Der Betrieb fuehrte
``--linie`` optional. Wortgleich das Loch vom 2026-09-16 (``--manifest``
optional): Jede Aussage, die nur mit einem Schalter gilt, laesst sich durch
Weglassen abschalten. Eine Wurzel, die man weglassen kann, ist keine.

Was hier gehalten wird:

* Zeichnen: kein Entscheid ohne ``--linie`` (Annahme wie Ablehnung, Fall wie
  Linienbereich) — Verweigerung mit Ausweg.
* Gruenden: die EINE Regel (``models.zeichnung.zeichnende_rolle_fehler``)
  hat keinen Zweig ohne Linie; ihr Parameter hat keinen Default, jeder
  Aufruf in ``src`` reicht ``linie=`` (Ratsche ``==`` mit Positivkontrolle);
  die Leser des Betriebs verlangen ``ordnungslinie`` ohne Default.
* ... und reichen den Ring (Pruefrunde G, G09): Wer die Linie liest, um auf
  ihr zu gruenden, ruft ``lade_linie`` mit ``ring=`` (Pflicht, kein Default);
  der strukturelle Einstieg ``lade_linie_strukturell_zur_anzeige`` ist
  benannt und gezaehlt (Ratsche ``==`` mit Positivkontrolle).
* Anzeigen: die Darstellungswerkzeuge rufen die Regel nicht (sie gruenden
  nichts; Altsnapshots bleiben fuer ihre Anzeige lesbar).
* Betrieb: die Kommandos, die auf einer Abnahme gruenden, verlangen
  ``--linie`` (Pflicht, ohne Default); der Nachtlauf nicht (benannte Menge).
* Der Anker des Betriebsschluessels: ``binden`` loest den Schluessel der
  Ablage unter der Linie auf und zeichnet ihn in die Bindung; der Nachtlauf
  haelt seinen Schluessel gegen diese Zahl.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import datetime as dt
import hashlib
import inspect
import json
from collections import Counter
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.gates import gate_entscheid
from rechner_pipeline.models import zeichnung as zmod
from tests.zeichnung_fixture import annahme_args, linie_anlegen

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


# --------------------------------------------------------------------------- #
# Zeichnen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("entscheid", ("angenommen", "abgelehnt"))
def test_ohne_linie_wird_nicht_entschieden(tmp_path, entscheid):
    """Mutationsprobe: die Pflichtpruefung in gate_entscheid entfernen ->
    eine Ablehnung ohne Linie wird geschrieben -> rot."""
    from rechner_pipeline.fall import anlegen

    fall = tmp_path / "fall"
    anlegen(fall)
    argv = ["--fall", str(fall), "--gate", "A-Q1", "--entscheid", entscheid,
            "--entscheider", "x", "--begruendung", "y", "--repo-root", str(REPO)]
    argv += (annahme_args(fall, ohne_linie=True, ohne_auftrag=True) if entscheid == "angenommen"
             else ["--rolle", "agent/programmleitung"])
    ergebnis = gate_entscheid.main(argv)
    assert ergebnis.exit_code == 2, ergebnis.errors
    meldung = ergebnis.errors[0]["message"]
    assert "ohne --linie wird nicht gezeichnet" in meldung and "Ausweg" in meldung
    assert "ADR-025" in meldung
    assert not (fall / "entscheide").exists() or not list((fall / "entscheide").iterdir())


def test_auch_im_linienbereich_nur_unter_der_spitze(tmp_path):
    """Der Linienbereich selbst ist die Linie: Gezeichnet wird dort unter
    seiner Spitze (dieselbe Pruefung)."""
    linie = linie_anlegen(tmp_path)
    args = annahme_args(linie, fuer="A-K2")
    assert "--linie" not in args          # der Bereich IST die Linie
    assert args[args.index("--zeichnungsordnung") + 1]


# --------------------------------------------------------------------------- #
# Gruenden: eine Regel, ohne Zweig ohne Linie
# --------------------------------------------------------------------------- #


def test_die_regel_hat_fuer_die_linie_keinen_default():
    """Wer die Regel ruft, muss die Linie nennen — ein vergessenes Argument
    ist ein TypeError, kein stiller Rueckfall auf die heutige Ordnung."""
    p = inspect.signature(zmod.zeichnende_rolle_fehler).parameters["linie"]
    assert p.default is inspect.Parameter.empty and p.kind is p.KEYWORD_ONLY
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from rechner_pipeline.betrieb import uebernahme as ueb
    from rechner_pipeline.betrieb import zugangsprobe as zpb

    for leser in (ueb.lies_abnahme_snapshot, ueb.lies_am4_snapshot, ueb.pruefe_am4_snapshot,
                  ueb.zeichnende_rolle, zpb.lies_soll, anf.binden):
        q = inspect.signature(leser).parameters["ordnungslinie"]
        assert q.default is inspect.Parameter.empty, leser.__name__


def test_ohne_linie_begruendet_keine_abnahme():
    """Positivkontrolle der Regel: None und die leere Linie verweigern, mit
    Ausweg — die Ordnung des Lesers spielt keine Rolle mehr."""
    daten = {"freigabe": {"schluessel_sha256": "aa" * 32}, "rolle": "mensch/aktuariat",
             "zeichnung": {"rolle": "mensch/aktuariat", "schluesselklasse": "mensch"}}
    ordnung = {"rollen": {"mensch/aktuariat": {"schluessel_sha256": "aa" * 32,
                                               "schluesselklasse": "mensch",
                                               "gates": ["A-M4"]}}}
    for linie in (None, []):
        rolle, fehler = zmod.zeichnende_rolle_fehler(daten, "A-M4", ordnung, linie=linie)
        assert rolle is None and "ohne Ordnungslinie" in fehler and "Ausweg" in fehler


def _regelaufrufe(quelle: str, datei: str) -> Counter:
    """Je umschliessender Funktion: Aufrufe der Regel, und ob sie ``linie=``
    mit einem Wert ausser dem Literal None reichen."""
    aufrufe: Counter = Counter()

    class Besucher(ast.NodeVisitor):
        def __init__(self):
            self.funktion = "<modul>"

        def visit_FunctionDef(self, knoten):
            vorher, self.funktion = self.funktion, knoten.name
            self.generic_visit(knoten)
            self.funktion = vorher

        def visit_Call(self, knoten):
            f = knoten.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name == "zeichnende_rolle_fehler":
                mit = any(k.arg == "linie" and not (isinstance(k.value, ast.Constant)
                                                    and k.value.value is None)
                          for k in knoten.keywords)
                aufrufe[(datei, self.funktion, mit)] += 1
            self.generic_visit(knoten)

    Besucher().visit(ast.parse(quelle))
    return aufrufe


#: Die gruendenden Leser — jede Stelle in ``src``, die die Regel ruft
#: (Datei, Funktion), gemessen 2026-10-01. Jede reicht die Linie.
GRUENDENDE_LESER = Counter({
    ("betrieb/uebernahme.py", "zeichnende_rolle", True): 1,
    ("gates/gate_entscheid.py", "standabnahme_pruefen", True): 2,
    ("gates/gate_entscheid.py", "fallauftrag_pruefen", True): 1,
    ("gates/gate_entscheid.py", "main", True): 3,
})


def test_ratsche_jeder_gruendende_leser_reicht_die_linie():
    gefunden: Counter = Counter()
    for pfad in sorted(SRC.rglob("*.py")):
        rel = str(pfad.relative_to(SRC))
        gefunden += _regelaufrufe(pfad.read_text(encoding="utf-8"), rel)
    assert gefunden == GRUENDENDE_LESER
    assert not [k for k in gefunden if not k[2]]


def test_ratsche_positivkontrolle_des_aufrufdetektors():
    quelle = ("def a(s, o, g):\n    zeichnende_rolle_fehler(s, 'A-M4', o, linie=g)\n"
              "def b(s, o):\n    zmod.zeichnende_rolle_fehler(s, 'A-M4', o, linie=None)\n"
              "def c(s, o):\n    zeichnende_rolle_fehler(s, 'A-M4', o)\n")
    assert _regelaufrufe(quelle, "x.py") == Counter({
        ("x.py", "a", True): 1, ("x.py", "b", False): 1, ("x.py", "c", False): 1})


# --------------------------------------------------------------------------- #
# Gruenden: ... und reicht den Ring (Pruefrunde G, G09)
# --------------------------------------------------------------------------- #


def test_der_leser_der_linie_hat_fuer_den_ring_keinen_default():
    """Wer die Linie liest, um darauf zu gruenden, reicht den Ring — ein
    vergessenes Argument ist ein TypeError, kein Rueckfall auf "nur die Form"
    (der alte Default ``ring=None`` pruefte keine Signatur)."""
    from rechner_pipeline.models import ordnungslinie as ol

    p = inspect.signature(ol.lade_linie).parameters["ring"]
    assert p.default is inspect.Parameter.empty and p.kind is p.KEYWORD_ONLY
    with pytest.raises(TypeError, match="ring ist Pflicht"):
        ol.lade_linie(REPO, ring=None)
    assert "ring" not in inspect.signature(ol.lade_linie_strukturell_zur_anzeige).parameters


def _linienaufrufe(quelle: str, datei: str) -> Counter:
    """Je umschliessender Funktion: Aufrufe der Leser der Linie — ``ring``
    (``lade_linie`` mit ``ring=`` ausser dem Literal None), ``ohne`` (ohne
    Ring) oder ``anzeige`` (der benannte strukturelle Einstieg)."""
    aufrufe: Counter = Counter()

    class Besucher(ast.NodeVisitor):
        def __init__(self):
            self.funktion = "<modul>"

        def visit_FunctionDef(self, knoten):
            vorher, self.funktion = self.funktion, knoten.name
            self.generic_visit(knoten)
            self.funktion = vorher

        def visit_Call(self, knoten):
            f = knoten.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
            if name == "lade_linie":
                mit = any(k.arg == "ring" and not (isinstance(k.value, ast.Constant)
                                                   and k.value.value is None)
                          for k in knoten.keywords)
                aufrufe[(datei, self.funktion, "ring" if mit else "ohne")] += 1
            elif name == "lade_linie_strukturell_zur_anzeige":
                aufrufe[(datei, self.funktion, "anzeige")] += 1
            self.generic_visit(knoten)

    Besucher().visit(ast.parse(quelle))
    return aufrufe


#: Die Leser der Linie in ``src``, gemessen 2026-10-01 (Pruefrunde G): Jeder,
#: der auf ihr gruendet, reicht den Ring. Vorher: fuenf Aufrufe, keiner mit Ring.
#: * das Gate (``main``): jede Annahme;
#: * der Produzent eines Glieds (``stand_belegen main``, zweimal: vor dem
#:   Anhaengen und fuer die Sicht danach) — wer anhaengt, gruendet auf der Spitze;
#: * der Zeichner des Betriebs (``betriebszeichner``): Registrierung,
#:   Zugangsprobe, Neuaufsetzen;
#: * die Bindung des Anfangsbestands (``anfangsbestand main``).
GRUENDENDE_LINIENLESER = Counter({
    ("betrieb/anfangsbestand.py", "main", "ring"): 1,
    ("betrieb/tageslauf.py", "betriebszeichner", "ring"): 1,
    ("gates/gate_entscheid.py", "main", "ring"): 1,
    ("gates/stand_belegen.py", "main", "ring"): 2,
})
#: Der strukturelle Einstieg, benannt: die Ablehnung im Gate — sie zeichnet
#: nichts und gruendet nichts, die Linie steht nur in ihrer Ausgabe.
ANZEIGENDE_LINIENLESER = Counter({
    ("gates/gate_entscheid.py", "main", "anzeige"): 1,
})


def test_ratsche_jeder_gruendende_leser_der_linie_reicht_den_ring():
    gefunden: Counter = Counter()
    for pfad in sorted(SRC.rglob("*.py")):
        if pfad.name == "ordnungslinie.py":
            continue                       # die Definition selbst
        gefunden += _linienaufrufe(pfad.read_text(encoding="utf-8"),
                                   str(pfad.relative_to(SRC)))
    assert gefunden == GRUENDENDE_LINIENLESER + ANZEIGENDE_LINIENLESER
    assert not [k for k in gefunden if k[2] == "ohne"]


def test_ratsche_positivkontrolle_des_linienaufrufdetektors():
    quelle = ("def a(b, r):\n    lade_linie(b, ring=r)\n"
              "def b(b):\n    ol.lade_linie(b, ring=None)\n"
              "def c(b):\n    ol.lade_linie(b)\n"
              "def d(b):\n    ol.lade_linie_strukturell_zur_anzeige(b)\n")
    assert _linienaufrufe(quelle, "x.py") == Counter({
        ("x.py", "a", "ring"): 1, ("x.py", "b", "ohne"): 1, ("x.py", "c", "ohne"): 1,
        ("x.py", "d", "anzeige"): 1})


def test_anzeigende_leser_rufen_die_regel_nicht():
    """Die Darstellung zeigt Entscheide (auch Altsnapshots ohne Glied) und
    gruendet nichts: Sie ruft weder die Regel noch den Leser des Betriebs —
    sonst muesste sie die Linie halten, oder sie gruendete ohne sie."""
    namen = {"zeichnende_rolle_fehler", "lies_abnahme_snapshot", "lies_am4_snapshot",
             "zeichnende_rolle"}
    for pfad in sorted((REPO / "werkzeuge").glob("*.py")):
        baum = ast.parse(pfad.read_text(encoding="utf-8"))
        gerufen = {getattr(k.func, "id", None) or getattr(k.func, "attr", None)
                   for k in ast.walk(baum) if isinstance(k, ast.Call)}
        assert not gerufen & namen, (pfad.name, gerufen & namen)


# --------------------------------------------------------------------------- #
# Betrieb: welche Kommandos die Linie verlangen
# --------------------------------------------------------------------------- #


def _linie_argument(modul: str):
    """(vorhanden, Pflicht) des Arguments ``--linie`` im Parser des Moduls."""
    pfad = SRC / (modul.split(".", 1)[1].replace(".", "/") + ".py")
    for k in ast.walk(ast.parse(pfad.read_text(encoding="utf-8"))):
        if isinstance(k, ast.Call) and getattr(k.func, "attr", None) == "add_argument" \
                and k.args and isinstance(k.args[0], ast.Constant) and k.args[0].value == "--linie":
            pflicht = any(w.arg == "required" and isinstance(w.value, ast.Constant)
                          and w.value.value is True for w in k.keywords)
            default = [w for w in k.keywords if w.arg == "default"]
            return True, pflicht and not default
    return False, False


def test_die_abgrenzung_der_betriebskommandos():
    """Die benannte Menge (``tageslauf.KOMMANDOS_MIT_LINIE``/``_OHNE_LINIE``)
    ist genau die Menge der Kommandos des Betriebs; die einen verlangen
    ``--linie`` ohne Default, die anderen kennen sie nicht.
    Mutationsprobe: ``--linie`` in einem gruendenden Kommando wieder
    optional -> rot."""
    kommandos = {f"rechner_pipeline.betrieb.{p.stem}" for p in (SRC / "betrieb").glob("*.py")
                 if "\ndef main(" in p.read_text(encoding="utf-8")}
    assert set(tl.KOMMANDOS_MIT_LINIE) | set(tl.KOMMANDOS_OHNE_LINIE) == kommandos
    assert not set(tl.KOMMANDOS_MIT_LINIE) & set(tl.KOMMANDOS_OHNE_LINIE)
    for modul in tl.KOMMANDOS_MIT_LINIE:
        assert _linie_argument(modul) == (True, True), modul
    for modul in tl.KOMMANDOS_OHNE_LINIE:
        assert _linie_argument(modul) == (False, False), modul
    assert tl._STANDARD_LINIE is not None   # die Naht der Suite; produktiv None


@pytest.mark.parametrize("modul", sorted(
    ("rechner_pipeline.betrieb.uebernahme", "rechner_pipeline.betrieb.zugangsprobe",
     "rechner_pipeline.betrieb.neuaufsetzen")))
def test_ein_gruendendes_kommando_ohne_linie_bricht_ab(modul, capsys):
    import importlib

    main = importlib.import_module(modul).main
    with pytest.raises(SystemExit) as ende:
        main(["--stand", "x", "--fall", "y", "--stichtag", "2026-01-01",
              "--betriebsschluessel", "k", "--schluessel", "k", "--zeichnungsordnung", "o"]
             if modul.endswith("uebernahme") is False else
             ["--stand", "x", "--fall", "y", "--stichtag", "2026-01-01",
              "--betriebsschluessel", "k", "--zeichnungsordnung", "o"])
    assert ende.value.code == 2
    assert "--linie" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Der Anker des Betriebsschluessels
# --------------------------------------------------------------------------- #


@pytest.fixture()
def gebunden(tmp_path):
    """Eine Ablage nach dem Aufbaulauf mit gezeichneter Bindung (ueber die
    Naht der Suite: belegen, A-B3 unter der Test-Linie, binden)."""
    from tests.test_betrieb_tageslauf import _ablage

    ablage = _ablage(tmp_path / "daten")
    for tag in (dt.date(2026, 1, 31), dt.date(2026, 2, 1)):
        code, zeile = tl.tageslauf(ablage, tag)
        assert code == tl.EXIT_OK, zeile.get("fehler")
    return ablage


def test_die_bindung_traegt_den_unter_der_linie_aufgeloesten_schluessel(gebunden):
    from rechner_pipeline.models import anfangsbestand as ab
    from tests.freigabe_testschluessel import BETRIEBSKEY, suitelinie_glied

    bindung = json.loads((gebunden.wurzel / ab.BINDUNG_DATEI).read_text(encoding="utf-8"))
    assert bindung["schema_version"] == ab.BINDUNG_SCHEMA_VERSION == 3
    assert bindung["betriebsschluessel_sha256"] == hashlib.sha256(BETRIEBSKEY).hexdigest()
    assert bindung["ordnungsglied_sha256"] == suitelinie_glied()["glied_sha256"]


def test_eine_ausgetauschte_ordnungsdatei_haelt_den_nachtlauf_an(gebunden, tmp_path, monkeypatch):
    """Die Ordnungsdatei des Betriebs gibt die Betriebsrolle einem ANDEREN
    Schluessel; der Lauf zeichnet mit ihm. Der Nachtlauf haelt an: Sein
    Schluessel ist nicht der, den die Linie beim Binden gab.

    Gemessen: Auch ohne den Anker hielte der Lauf an — die Zeilen und die
    Bindung sind mit dem alten Schluessel gezeichnet und mit dem neuen nicht
    pruefbar. Der Anker macht daraus die benannte Aussage und bindet den
    Schluessel an die Linie. Mutationsprobe: die Ankerpruefung in
    ``anfangsbestand_fehler`` entfernen -> die Meldung fehlt -> rot (wenn der
    Lauf bis zur Bindung kommt)."""
    from rechner_pipeline.models import anfangsbestand as ab
    from tests.freigabe_testschluessel import BETRIEBSROLLE, betriebsordnung

    neu = tmp_path / "aussen" / "betrieb-neu.key"
    neu.parent.mkdir()
    neu.write_bytes(hashlib.sha256(b"ein anderer betriebsschluessel").digest())
    neu.chmod(0o600)
    ordnung = betriebsordnung()
    ordnung["rollen"][BETRIEBSROLLE]["schluessel_sha256"] = hashlib.sha256(
        neu.read_bytes()).hexdigest()
    datei = tmp_path / "aussen" / "ordnung.json"
    datei.write_text(json.dumps(ordnung, sort_keys=True), encoding="utf-8")
    zeichner = tl.betriebszeichner(gebunden, neu, datei)
    ab_fehler = None
    from rechner_pipeline.betrieb import anfangsbestand as anf

    ab_fehler = anf.anfangsbestand_fehler(gebunden, zeichner)
    assert ab_fehler is not None and "nicht der gebundene" in ab_fehler, ab_fehler
    assert "neue Bindung unter der Linie" in ab_fehler
    # Der ganze Lauf haelt schon an der Protokollkette an (gemessen): Die
    # Zeilen tragen die Rolle mit dem alten Schluessel.
    monkeypatch.setattr(tl, "_STANDARD_BETRIEBSZEICHNUNG", (neu, datei))
    with pytest.raises(tl.TageslaufError, match="passen nicht zur Zeichnungsordnung"):
        tl.tageslauf(gebunden, dt.date(2026, 2, 2))
    assert (gebunden.wurzel / ab.BINDUNG_DATEI).is_file()


def test_binden_verweigert_eine_ordnungsdatei_die_nicht_die_der_linie_ist(tmp_path):
    """Beim Binden wird der Schluessel unter der Linie aufgeloest: Gibt die
    Ordnungsdatei des Betriebs die Rolle einem anderen Schluessel als die
    Spitze der Linie, bindet ``binden`` nicht."""
    from rechner_pipeline.betrieb import anfangsbestand as anf
    from tests.freigabe_testschluessel import BETRIEBSROLLE, betriebsordnung, suitelinie_glied

    zeichner = tl.betriebszeichner(tl.Ablage(Path("/nirgends")))
    assert anf.betriebsschluessel_der_linie(zeichner, [suitelinie_glied()]) == \
        zeichner.schluessel_sha256
    andere = betriebsordnung()
    andere["rollen"][BETRIEBSROLLE]["schluessel_sha256"] = "ab" * 32
    with pytest.raises(anf.AnfangsbestandFehler, match="nicht die\\s+der Linie"):
        anf.betriebsschluessel_der_linie(zeichner, [suitelinie_glied(andere)])
    with pytest.raises(anf.AnfangsbestandFehler, match="ohne Ordnungslinie"):
        anf.betriebsschluessel_der_linie(zeichner, [])
