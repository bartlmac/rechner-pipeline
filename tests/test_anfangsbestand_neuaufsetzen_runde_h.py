"""Anfangsbestand und Neuaufsetzen nach der Pruefrunde H (Funde H08, H17, H18).

* H08: Beim Anfangsbestand (A-B3) rechnete niemand das Urteil der
  Bestandswache und die Kennzahlen des Belegs nach. Das Gate sieht die
  Ablage nicht, ``binden`` hielt nur die Stand-Felder. Ein Beleg mit
  geschoentem Urteil oder geschoenten Kennzahlen wurde abgenommen und
  gebunden. Invariante: Gebunden wird nur ein Anfangsbestand, dessen Beleg
  JETZT, auf den Bytes der Ablage mit denselben Funktionen neu gebaut, der
  gezeichnete ist — Urteil der Wache, Kennzahlen und jedes andere Feld. Die
  Menge steht im Vertrag (``models.anfangsbestand.BELEG_BEIM_BINDEN_NACHGERECHNET``
  und ``BELEG_BEIM_BINDEN_GEGLAUBT``); die Ratsche haelt sie mit == gegen
  ``BELEG_FELDER``.
* H17: ``belegen`` raeumte seine Schreibreste nie. Invariante: Ein
  Schreibrest liegt nie dauerhaft neben einem Beleg; der naechste Aufruf
  fuer dasselbe Ziel raeumt ihn — mit der Erkennung und dem Raeumen des
  Betriebs (``tageslauf.raeume_schreibreste_von``), keine dritte Fassung.
  Die Menge der Tempdatei-Schreiber in ``betrieb/`` haelt eine Ratsche.
* H18: Ein Prozessende des Neuaufsetzens zwischen dem Anlegen der
  Vorbereitung und der ersten Umbenennung liess ``<daten>.neu-<zeit>``
  ungenannt liegen. Invariante: Eine liegengebliebene Vorbereitung ist nie
  still. Jeder Aufruf, der die Ablage betritt, geht durch
  ``tageslauf.lauf_sperre``; dort wird sie erkannt. Der Tageslauf und jeder
  andere Aufruf halten benannt an; das Neuaufsetzen raeumt seine eigene,
  nie veroeffentlichte Vorbereitung ab; was veroeffentlicht gewesen sein
  koennte, bleibt liegen und wird genannt.

Jedes Prozessende ist ein echtes (Subprozess, ``os._exit`` an der Stelle).

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import rechner_pipeline
from rechner_pipeline.betrieb import anfangsbestand as anf
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.models import anfangsbestand as ab

SRC = Path(rechner_pipeline.__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[1]
BETRIEB = SRC / "rechner_pipeline" / "betrieb"


def _subprozess(code: str, cwd: Path) -> subprocess.CompletedProcess:
    umgebung = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), str(REPO)]),
                "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-c", code], env=umgebung, cwd=str(cwd),
                          capture_output=True, text=True, timeout=300)


# --------------------------------------------------------------------------- #
# Welt des Anfangsbestands: Linie, Schluessel, Ablage nach dem Aufbaulauf
# --------------------------------------------------------------------------- #


@pytest.fixture()
def welt(tmp_path, monkeypatch):
    """Linie (ein Glied: die Betriebsordnung der Suite), Schluesseldateien,
    eine kleine Ablage nach dem Aufbaulauf — ohne Naht des Anfangsbestands."""
    from rechner_pipeline.gates import stand_belegen
    from tests import freigabe_testschluessel as fk
    from tests.test_betrieb_tageslauf import _ablage

    monkeypatch.setattr(anf, "_STANDARD_ANFANGSBESTAND", None)
    (tmp_path / "schluessel").mkdir()
    k = {}
    for name, inhalt in (("betrieb", fk.BETRIEBSKEY), ("freigabe", fk.BETRIEB_FREIGABEKEY),
                         ("vorstand", fk.VORSTANDKEY)):
        pfad = tmp_path / "schluessel" / f"{name}.key"
        pfad.write_bytes(inhalt)
        pfad.chmod(0o600)
        k[name] = pfad
    ordnung = tmp_path / "schluessel" / "ordnung.json"
    ordnung.write_bytes(fk.ordnung_bytes())
    linie = tmp_path / "linie"
    assert stand_belegen.main(["linie", "--linie", str(linie)]).exit_code == 0
    r = stand_belegen.main(["ordnung", "--linie", str(linie), "--ordnung", str(ordnung),
                            "--vorgaenger", "keiner",
                            "--eingetragen-am", "2026-10-01T08:00:00+00:00"])
    assert r.exit_code == 0, r.errors
    ablage = _ablage(tmp_path / "daten")
    code, zeile = tl.tageslauf(ablage, dt.date(2026, 2, 3), schluessel=k["betrieb"],
                               zeichnungsordnung=ordnung)
    assert code == tl.EXIT_OK, zeile
    return {"k": k, "ordnung": ordnung, "linie": linie, "ablage": ablage, "tmp": tmp_path}


def _belegen_argv(w) -> list:
    return ["belegen", "--stand", str(w["ablage"].wurzel), "--linie", str(w["linie"]),
            "--schluessel", str(w["k"]["betrieb"]), "--zeichnungsordnung", str(w["ordnung"])]


def _binden_argv(w) -> list:
    return ["binden", "--stand", str(w["ablage"].wurzel), "--linie", str(w["linie"]),
            "--freigabe-schluessel", str(w["k"]["vorstand"]),
            "--freigabe-schluessel", str(w["k"]["freigabe"]),
            "--schluessel", str(w["k"]["betrieb"]), "--zeichnungsordnung", str(w["ordnung"])]


def _a_b3(w):
    from rechner_pipeline.gates import gate_entscheid

    return gate_entscheid.main([
        "--linie", str(w["linie"]), "--gate", "A-B3", "--entscheid", "angenommen",
        "--entscheider", "betrieb", "--begruendung", "Anfangsbestand geprueft",
        "--repo-root", str(REPO), "--zeichnungsordnung", str(w["ordnung"]),
        "--freigabe-schluessel", str(w["k"]["vorstand"]),
        "--freigabe-schluessel", str(w["k"]["freigabe"])])


def _zeichner(w):
    return tl.betriebszeichner(w["ablage"], w["k"]["betrieb"], w["ordnung"],
                               wofuer="der Test", ohne="kein Test")


def _lege_beleg_vor(w, beleg: dict) -> None:
    """Einen Beleg am festen Ort vorlegen, die Sicht aus genau ihm — so, wie
    es jeder kann, der den Linienbereich beschreiben darf."""
    roh = (json.dumps(beleg, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode()
    pfad = w["linie"] / ab.BELEG_RELATIV
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_bytes(roh)
    (w["linie"] / ab.SICHT_RELATIV).write_text(ab.rendere_sicht(json.loads(roh)),
                                               encoding="utf-8")


# --------------------------------------------------------------------------- #
# H08: binden rechnet Urteil und Kennzahlen nach
# --------------------------------------------------------------------------- #


def test_ehrlich_belegt_gezeichnet_und_gebunden(welt, capsys):
    """Positivkontrolle: belegen, A-B3 und binden ueber die Kommandos, danach
    laeuft der Tag."""
    assert anf.main(_belegen_argv(welt)) == 0
    assert _a_b3(welt).exit_code == 0
    assert anf.main(_binden_argv(welt)) == 0, capsys.readouterr().err
    bindung = json.loads((welt["ablage"].wurzel / ab.BINDUNG_DATEI).read_text(encoding="utf-8"))
    beleg = json.loads((welt["linie"] / ab.BELEG_RELATIV).read_text(encoding="utf-8"))
    assert bindung["kennzahlen"] == beleg["kennzahlen"]
    assert bindung["schema_version"] == ab.BINDUNG_SCHEMA_VERSION


@pytest.mark.parametrize("schoenung", ["urteil", "kennzahl"])
def test_ein_geschoenter_beleg_wird_nicht_gebunden(welt, capsys, schoenung):
    """H08. ``urteil``: Der Stand ist beschaedigt (eine Police doppelt), die
    Wache auf genau diesen Bytes ist rot; im Beleg steht "gruen" (und sonst
    nichts geaendert). ``kennzahl``: gesunder Stand, im Beleg ein Vertrag
    mehr. Beide Belege besteht das Gate (Form, gruenes Urteil), ``binden``
    band sie mit Exit 0. Jetzt: Exit 2, das Feld ist genannt, keine Bindung.

    Mutationsprobe: in ``binden`` den Vergleich mit dem neu gebauten Beleg
    entfernen -> Exit 0 -> rot."""
    import pandas as pd

    w = welt
    ablage = w["ablage"]
    if schoenung == "urteil":
        datei = next(ablage.stand.resolve().rglob("bestand_gesamt.parquet"))
        df = pd.read_parquet(datei)
        pd.concat([df, df.iloc[[0]]]).to_parquet(datei, index=False)
        assert anf.main(_belegen_argv(w)) == 2      # ehrlich: verweigert
        assert "nicht gruen" in capsys.readouterr().err
    beleg = anf.baue_beleg(ablage, _zeichner(w))
    if schoenung == "urteil":
        assert beleg["pb1"]["urteil"] == "rot"
        beleg["pb1"] = {"urteil": "gruen", "geprueft": beleg["pb1"]["geprueft"], "befunde": []}
        erwartet = "pb1"
    else:
        assert beleg["pb1"]["urteil"] == "gruen"
        beleg["kennzahlen"]["vertraege"] += 1
        erwartet = "kennzahlen"
    assert ab.beleg_fehler(beleg) == []
    _lege_beleg_vor(w, beleg)
    gate = _a_b3(w)
    assert gate.exit_code == 0, gate.errors       # das Gate sieht die Ablage nicht
    capsys.readouterr()
    rc = anf.main(_binden_argv(w))
    meldung = capsys.readouterr().err
    assert rc == 2, meldung
    assert erwartet in meldung and "Ausweg" in meldung, meldung
    assert not (ablage.wurzel / ab.BINDUNG_DATEI).exists()


def test_ohne_den_gezeichneten_beleg_am_festen_ort_wird_nicht_gebunden(welt, capsys):
    """Was nicht neben dem Snapshot liegt, kann niemand nachrechnen: Ein
    nach dem Zeichnen ersetzter Beleg (anderer Hash) ist ein benannter
    Fehler. Vorher band ``binden`` dann mit leeren Kennzahlen."""
    assert anf.main(_belegen_argv(welt)) == 0
    assert _a_b3(welt).exit_code == 0
    pfad = welt["linie"] / ab.BELEG_RELATIV
    pfad.write_bytes(pfad.read_bytes() + b"\n")
    capsys.readouterr()
    assert anf.main(_binden_argv(welt)) == 2
    assert "gezeichnete Beleg" in capsys.readouterr().err
    assert not (welt["ablage"].wurzel / ab.BINDUNG_DATEI).exists()


def test_ratsche_jedes_feld_des_belegs_ist_eingeteilt():
    """Ratsche (==): Jedes Feld des Belegs wird beim Binden nachgerechnet
    oder ausdruecklich geglaubt, mit Grund — ein neues Feld erzwingt eine
    Entscheidung. Heute wird keines geglaubt."""
    nach = ab.BELEG_BEIM_BINDEN_NACHGERECHNET
    geglaubt = ab.BELEG_BEIM_BINDEN_GEGLAUBT
    assert not nach & set(geglaubt)
    assert nach | set(geglaubt) == ab.BELEG_FELDER
    assert all(isinstance(g, str) and g for g in geglaubt.values())
    assert geglaubt == {}
    assert nach == frozenset({
        "schema_version", "art", "ablage", "ablage_stand", "tabellen", "config_sha256",
        "code", "pb1", "eingaenge", "kennzahlen", "vorher", "abweichung"})


def test_zaehltest_jedes_nachgerechnete_feld_faellt_auf(welt):
    """Dynamisch: Auf einem echten Beleg wird je nachgerechnetem Feld genau
    dieses verbogen; die Nachrechnung nennt genau dieses Feld. Der
    unveraenderte Beleg ergibt keine Abweichung (Positivkontrolle).

    Mutationsprobe: ein Feld aus ``BELEG_BEIM_BINDEN_NACHGERECHNET``
    nehmen -> Ratsche rot und hier sein Fall rot."""
    frisch = anf.baue_beleg(welt["ablage"], _zeichner(welt))
    gezeichnet = json.loads(json.dumps(frisch))
    assert ab.nachrechnung_abweichungen(gezeichnet, frisch) == []
    for feld in sorted(ab.BELEG_FELDER):
        verbogen = json.loads(json.dumps(frisch))
        verbogen[feld] = {"verbogen": feld}
        assert ab.nachrechnung_abweichungen(verbogen, frisch) == [feld], feld


# --------------------------------------------------------------------------- #
# H17: belegen raeumt seine Schreibreste
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("ziel", [ab.BELEG_RELATIV, ab.SICHT_RELATIV])
def test_ein_prozessende_beim_belegen_hinterlaesst_keinen_dauerhaften_rest(welt, ziel):
    """Prozessende (os._exit) unmittelbar vor dem Einhaengen des Ziels, im
    eigenen Prozess; danach derselbe Aufruf: Exit 0 und kein Rest.

    Mutationsprobe: das Raeumen in ``anfangsbestand._schreibe`` entfernen ->
    der Rest bleibt -> rot."""
    zielname = Path(ziel).name
    code = (
        "import os, sys\n"
        "from rechner_pipeline.betrieb import anfangsbestand as anf\n"
        "echt = os.replace\n"
        "def stirb(quelle, ziel, *a, **k):\n"
        f"    if os.path.basename(os.fspath(ziel)) == {zielname!r}:\n"
        "        os._exit(137)\n"
        "    return echt(quelle, ziel, *a, **k)\n"
        "os.replace = stirb\n"
        f"sys.exit(anf.main({_belegen_argv(welt)!r}))\n")
    lauf = _subprozess(code, welt["tmp"])
    assert lauf.returncode == 137, lauf.stderr
    verzeichnis = (welt["linie"] / ziel).parent
    reste = [p.name for p in verzeichnis.iterdir() if p.name.startswith(f".{zielname}.")]
    assert len(reste) == 1, reste                  # die Probe hat den Ausfall erreicht
    assert anf.main(_belegen_argv(welt)) == 0
    assert not [p.name for p in verzeichnis.iterdir() if p.name.startswith(".")]
    assert (welt["linie"] / ab.BELEG_RELATIV).is_file()
    assert (welt["linie"] / ab.SICHT_RELATIV).is_file()


def _tempdatei_stellen() -> Counter:
    """Jede Funktion in ``betrieb/*.py``, die eine Tempdatei anlegt — ein
    Primitiv (``neue_datei``, ``mkstemp``, ``mkdtemp``, ``schreibe_exklusiv``)
    oder einen selbst gebauten Namen auf ``.tmp`` — mit ihrer Anzahl."""
    primitive = {"neue_datei", "mkstemp", "mkdtemp", "schreibe_exklusiv",
                 "NamedTemporaryFile", "TemporaryDirectory"}
    stellen: Counter = Counter()
    for datei in sorted(BETRIEB.glob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for f in ast.walk(baum):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(f):
                if isinstance(n, ast.Call):
                    name = (n.func.attr if isinstance(n.func, ast.Attribute)
                            else getattr(n.func, "id", None))
                    if name in primitive:
                        stellen[(datei.stem, f.name, name)] += 1
                elif isinstance(n, ast.JoinedStr) and any(
                        isinstance(v, ast.Constant) and str(v.value).endswith(".tmp")
                        and not str(v.value).endswith("*.tmp")
                        for v in n.values):
                    stellen[(datei.stem, f.name, "name.tmp")] += 1
    return stellen


#: Die Tempdatei-Schreiber des Betriebs und wer ihren Rest nach einem
#: Prozessende raeumt (H17, Klasse). Eine neue Stelle ist rot, bis sie hier
#: mit ihrem Raeumer steht.
TEMPDATEI_STELLEN = {
    ("anfangsbestand", "_schreibe", "neue_datei"):
        "raeumt vor dem Schreiben die Reste desselben Ziels (tageslauf.raeume_schreibreste_von)",
    ("tageslauf", "_schreibe_json_atomar", "mkstemp"):
        "Ziel durch schreibziel; der Lauf raeumt unter der Sperre (SCHREIBZIELE)",
    ("tageslauf", "_bericht", "neue_datei"):
        "Ziel durch schreibziel; der Lauf raeumt unter der Sperre (SCHREIBZIELE)",
    ("seite", "bereite_bestand_heute_vor", "neue_datei"):
        "Ziel durch schreibziel; raeumt selbst und der Lauf unter der Sperre",
    ("seite", "_schreibe", "neue_datei"):
        "OFFEN, nicht gebaut: Export-Ziel ausserhalb der Ablage, kein Raeumer",
    ("zugangsprobe", "_schreibe_beleg", "name.tmp"):
        "OFFEN, nicht gebaut: raeumt nur den Rest derselben Prozessnummer",
    ("zugangsprobe", "zugangsprobe", "mkdtemp"):
        "Arbeitsverzeichnis der Probe ausserhalb der Ablage, kein Schreibrest eines Ziels",
    ("tageslauf", "_tageslauf", "TemporaryDirectory"):
        "eingefrorene Config im Systemtemp, nicht neben einem Beleg oder in der Ablage",
}


def test_ratsche_die_tempdatei_schreiber_des_betriebs():
    """Ratsche (==, je Stelle mit Anzahl 1): die Menge aus H17. Vorher baute
    ``anfangsbestand._schreibe`` seinen Tempnamen selbst und raeumte nie."""
    assert _tempdatei_stellen() == Counter({k: 1 for k in TEMPDATEI_STELLEN})


def test_ratsche_tempdatei_positivkontrolle(tmp_path, monkeypatch):
    """Die Ratsche sieht einen selbst gebauten Tempnamen und ein Primitiv."""
    probe = tmp_path / "probe.py"
    probe.write_text("def a(z):\n    t = z.parent / f'.{z.name}.x.tmp'\n"
                     "def b(z):\n    neue_datei(z.parent, z.name)\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "BETRIEB", tmp_path)
    assert _tempdatei_stellen() == Counter({("probe", "a", "name.tmp"): 1,
                                            ("probe", "b", "neue_datei"): 1})


# --------------------------------------------------------------------------- #
# H18: eine liegengebliebene Vorbereitung des Neuaufsetzens ist nie still
# --------------------------------------------------------------------------- #


@pytest.fixture()
def gefuehrt(tmp_path):
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    assert tl.tageslauf(ablage, dt.date(2026, 2, 3))[0] == tl.EXIT_OK
    return ablage


def _na_argv(ablage, fall, *extra) -> list:
    from tests.freigabe_testschluessel import betriebsargs, linieargs
    from tests.test_betrieb_uebernahme import STICHTAG

    return ["--stand", str(ablage.wurzel), "--fall", str(fall),
            "--stichtag", STICHTAG.isoformat(), *betriebsargs("--betriebsschluessel"),
            *linieargs(), *extra]


def _tageslauf_argv(ablage, heute="2026-02-05") -> list:
    from tests.freigabe_testschluessel import betriebsargs

    return ["--stand", str(ablage.wurzel), "--heute", heute, *betriebsargs()]


def _stirbt_im_neuaufsetzen(ablage, fall, stelle: str, *extra):
    """Das Neuaufsetzen im eigenen Prozess, mit den Naehten der Suite, und
    ein Prozessende (os._exit) an ``stelle``: ``eingang`` nach dem Anlegen
    des Eingangs (vor der Provenienz), ``archivierung`` an der ersten
    Umbenennung (nach der Provenienz)."""
    if stelle == "eingang":
        stoerung = "na.lies_uebernahme = lambda *a, **k: os._exit(137)\n"
    else:
        stoerung = (
            "echt = os.rename\n"
            "def stirb(quelle, ziel, *a, **k):\n"
            "    if '.archiv' in os.path.basename(os.fspath(ziel)) or "
            "os.path.basename(os.fspath(ziel)) == 'archiv':\n"
            "        os._exit(137)\n"
            "    return echt(quelle, ziel, *a, **k)\n"
            "na.os.rename = stirb\n")
    code = (
        "import os, sys\n"
        "from rechner_pipeline.betrieb import neuaufsetzen as na\n"
        "from rechner_pipeline.betrieb import uebernahme as ueb\n"
        "from tests.freigabe_testschluessel import TESTRING\n"
        "from tests.zugangsabnahme_testhelfer import schreibe_zugangsabnahme\n"
        "ueb._STANDARD_SCHLUESSELRING = TESTRING\n"
        "ueb._STANDARD_ZUGANGSABNAHME = schreibe_zugangsabnahme\n"
        + stoerung
        + f"sys.exit(na.main({_na_argv(ablage, fall, *extra)!r}))\n")
    lauf = _subprozess(code, ablage.wurzel.parent)
    assert lauf.returncode == 137, lauf.stderr
    reste = sorted(ablage.wurzel.parent.glob(f"{ablage.wurzel.name}.neu-*"))
    assert len(reste) == 1 and ablage.wurzel.is_dir(), reste   # Zustand erreicht
    return reste[0]


@pytest.mark.parametrize("stelle", ["eingang", "archivierung"])
def test_eine_liegengebliebene_vorbereitung_haelt_den_tag_an_und_das_neuaufsetzen_raeumt_sie(
        gefuehrt, tmp_path, capsys, stelle):
    """H18. Nach dem Prozessende: Der Tageslauf haelt an (Exit 2) und nennt
    den Rest samt Ausweg, ohne eine Zeile zu schreiben; das wiederholte
    Neuaufsetzen raeumt die nie veroeffentlichte Vorbereitung ab, nennt sie
    und setzt neu auf; danach laeuft der Tag.

    Mutationsprobe: die Pruefung in ``lauf_sperre`` entfernen -> Tageslauf
    Exit 0 -> rot; das Abraeumen im Neuaufsetzen entfernen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    protokoll = gefuehrt.protokoll_pfad.read_bytes()
    rest = _stirbt_im_neuaufsetzen(gefuehrt, fall, stelle)
    assert (rest / na.PROVENIENZ_DATEI).is_file() == (stelle == "archivierung")
    capsys.readouterr()
    assert tl.main(_tageslauf_argv(gefuehrt)) == tl.EXIT_USAGE
    meldung = capsys.readouterr().err
    assert rest.name in meldung and "neuaufsetzen" in meldung and "Ausweg" in meldung, meldung
    assert "nie veroeffentlicht" in meldung, meldung
    assert gefuehrt.protokoll_pfad.read_bytes() == protokoll
    # Jeder andere Aufruf, der die Ablage betritt, haelt ebenso an.
    from tests.freigabe_testschluessel import betriebsargs, linieargs

    assert anf.main(["belegen", "--stand", str(gefuehrt.wurzel), *linieargs(),
                     *betriebsargs()]) == 2
    assert rest.name in capsys.readouterr().err
    # Das Neuaufsetzen raeumt seine eigene, nie veroeffentlichte Vorbereitung.
    assert na.main(_na_argv(gefuehrt, fall)) == 0
    meldung = capsys.readouterr().err
    assert rest.name in meldung and "entfernt" in meldung, meldung
    namen = sorted(p.name for p in tmp_path.iterdir() if p.name.startswith("daten"))
    assert not [n for n in namen if ".neu-" in n], namen
    archive = [n for n in namen if ".archiv-" in n]
    assert len(archive) == 1, namen
    assert tl.Ablage(tmp_path / archive[0]).protokoll_pfad.read_bytes() == protokoll
    assert tl.main(_tageslauf_argv(gefuehrt)) == tl.EXIT_OK


def test_mit_festem_archiv_wird_der_rest_nicht_fertig(gefuehrt, tmp_path, capsys):
    """Mit festem ``--archiv`` nannte die Provenienz des Rests nach einem
    zweiten Lauf ein existierendes Archiv — der Rest sah "fertig" aus. Jetzt
    raeumt der zweite Lauf ihn ab, BEVOR er das Archiv anlegt."""
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    archiv = tmp_path / "archiv"
    rest = _stirbt_im_neuaufsetzen(gefuehrt, fall, "archivierung", "--archiv", str(archiv))
    assert json.loads((rest / "neuaufsetzen.json").read_text(encoding="utf-8"))["archiv"] \
        == str(archiv)
    capsys.readouterr()
    from rechner_pipeline.betrieb import neuaufsetzen as na

    assert na.main(_na_argv(gefuehrt, fall, "--archiv", str(archiv))) == 0, \
        capsys.readouterr().err
    assert not rest.exists() and archiv.is_dir()
    assert tl.main(_tageslauf_argv(gefuehrt)) == tl.EXIT_OK


def test_zwei_vorbereitungen_werden_beide_genannt_und_beide_geraeumt(gefuehrt, tmp_path, capsys):
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    rest = _stirbt_im_neuaufsetzen(gefuehrt, fall, "eingang")
    zweiter = rest.with_name(f"{gefuehrt.wurzel.name}.neu-20200101T000000Z")
    shutil.copytree(rest, zweiter, symlinks=True)
    capsys.readouterr()
    assert tl.main(_tageslauf_argv(gefuehrt)) == tl.EXIT_USAGE
    meldung = capsys.readouterr().err
    assert rest.name in meldung and zweiter.name in meldung, meldung
    assert na.main(_na_argv(gefuehrt, fall)) == 0
    assert not rest.exists() and not zweiter.exists()


@pytest.mark.parametrize("art", ["archiv_da", "gefuehrt", "fremder_name"])
def test_was_veroeffentlicht_gewesen_sein_koennte_bleibt_liegen_und_wird_genannt(
        gefuehrt, tmp_path, capsys, art):
    """Gegenrichtung: Eine Vorbereitung, deren Provenienz ein existierendes
    Archiv nennt, eine, die ein Protokoll traegt (sie war eine Ablage), und
    ein Name, den das Neuaufsetzen nicht vergibt, werden nie entfernt —
    Tageslauf und Neuaufsetzen halten an und nennen sie als "nicht
    bestimmbar", nie als "nie veroeffentlicht".

    Mutationsproben: die Pruefung auf ein existierendes Archiv bzw. auf ein
    Journal in ``_nie_veroeffentlicht`` entfernen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    name = ("daten.neu-irgendwas" if art == "fremder_name" else "daten.neu-20200101T000000Z")
    rest = tmp_path / name
    (rest / "configs").mkdir(parents=True)
    if art == "archiv_da":
        (tmp_path / "daten.archiv-20200101T000000Z").mkdir()
        (rest / na.PROVENIENZ_DATEI).write_text(json.dumps(
            {"archiv": str(tmp_path / "daten.archiv-20200101T000000Z")}), encoding="utf-8")
    elif art == "gefuehrt":
        (rest / "journal").mkdir()
        (rest / "journal" / "protokoll.jsonl").write_text("{}\n", encoding="utf-8")
    vorher = sorted(str(p.relative_to(tmp_path)) for p in rest.rglob("*"))
    capsys.readouterr()
    assert tl.main(_tageslauf_argv(gefuehrt)) == tl.EXIT_USAGE
    meldung = capsys.readouterr().err
    assert rest.name in meldung and "nicht bestimmbar" in meldung, meldung
    assert "nie veroeffentlicht" not in meldung, meldung
    assert na.main(_na_argv(gefuehrt, fall)) == 2
    meldung = capsys.readouterr().err
    assert rest.name in meldung and "von Hand" in meldung, meldung
    assert sorted(str(p.relative_to(tmp_path)) for p in rest.rglob("*")) == vorher
    assert not list(tmp_path.glob("daten.archiv-2026*"))


def _lauf_sperre_stellen() -> Counter:
    """Jede Aufrufstelle von ``lauf_sperre`` in ``src`` (Modul, Funktion)."""
    stellen: Counter = Counter()
    for datei in sorted((SRC / "rechner_pipeline").rglob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8"))
        for f in ast.walk(baum):
            if not isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for n in ast.walk(f):
                if isinstance(n, ast.Call) and (
                        getattr(n.func, "id", None) == "lauf_sperre"
                        or getattr(n.func, "attr", None) == "lauf_sperre"):
                    stellen[(datei.stem, f.name)] += 1
    return stellen


def test_ratsche_jeder_eintritt_in_die_ablage_geht_durch_lauf_sperre():
    """Ratsche (==): die Aufrufe, die die Ablage betreten — alle ueber
    ``lauf_sperre``, und dort sitzt die Erkennung. Nur das Neuaufsetzen
    raeumt ab (``vorbereitung_abraeumen=True``); jeder andere haelt an."""
    assert _lauf_sperre_stellen() == Counter({
        ("anfangsbestand", "_gesperrt"): 1,
        ("neuaufsetzen", "neu_aufsetzen"): 1,
        ("zugangsprobe", "zugangsprobe"): 1,
        ("seite", "stands_paket"): 1,
        ("seite", "main"): 1,
        ("tageslauf", "tageslauf"): 1,
        ("uebernahme", "eingang_anlegen"): 1,
    })
    quelle = (BETRIEB / "tageslauf.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    sperre = next(f for f in ast.walk(baum)
                  if isinstance(f, ast.FunctionDef) and f.name == "lauf_sperre")
    gerufen = {getattr(n.func, "id", None) for n in ast.walk(sperre) if isinstance(n, ast.Call)}
    assert "_liegengebliebene_vorbereitungen" in gerufen
    abraeumer = [datei.stem for datei in sorted(BETRIEB.glob("*.py"))
                 if "vorbereitung_abraeumen=True" in datei.read_text(encoding="utf-8")]
    assert abraeumer == ["neuaufsetzen"]


def test_ratsche_lauf_sperre_positivkontrolle(tmp_path, monkeypatch):
    probe = tmp_path / "rechner_pipeline" / "probe.py"
    probe.parent.mkdir()
    probe.write_text("def neu(a):\n    with tl.lauf_sperre(a):\n        pass\n",
                     encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "SRC", tmp_path)
    assert _lauf_sperre_stellen() == Counter({("probe", "neu"): 1})


def test_die_erkennung_sitzt_in_lauf_sperre(tmp_path):
    """Direkt an der Stelle, durch die jeder Aufruf geht: ein Rest neben der
    Ablage -> benannter Fehler, die Sperre ist danach frei."""
    ablage = tl.Ablage(tmp_path / "daten")
    ablage.wurzel.mkdir()
    rest = tmp_path / "daten.neu-20260101T000000Z"
    (rest / "configs").mkdir(parents=True)
    with pytest.raises(tl.TageslaufError, match=rest.name):
        with tl.lauf_sperre(ablage):
            pass
    with tl.lauf_sperre(ablage, vorbereitung_abraeumen=True) as geraeumt:
        assert len(geraeumt) == 1 and rest.name in geraeumt[0]
    assert not rest.exists()
    with tl.lauf_sperre(ablage) as geraeumt:
        assert geraeumt == []
