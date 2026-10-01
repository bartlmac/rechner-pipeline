"""Betrieb nach der Pruefrunde I (Funde I20, I21).

* I20: Erkennung der liegengebliebenen Vorbereitung und Vollenden des
  Tauschs bauten ein glob-Muster aus dem Namen der Ablage
  (``<wurzel>.neu-*``), unmaskiert. Mit ``[`` im Namen passte das Muster
  nicht mehr auf den eigenen Namen (beide blind, der Tageslauf legte eine
  leere Ablage an) — und fuer ``daten[1]`` passte es auf die Vorbereitung
  der Nachbarablage ``daten1``. Invariante: Kein glob-Muster in ``betrieb/``
  und ``gates/`` traegt einen Namens- oder Pfadanteil, der vom Bediener
  kommt; die Vorbereitungen neben einer Ablage werden ohne Muster gesucht
  (``tageslauf._vorbereitungen_neben``: Namensvergleich ueber ``iterdir``).
  Die Ratsche haelt die verbleibenden Muster mit ``==``, je mit dem Grund,
  warum ihr Text fest ist.
* I21: Ein E/A-Fehler beim Anlegen von ``<daten>.neu-<zeit>/configs`` liess
  die schon angelegte Vorbereitung ungenannt liegen; der naechste Aufruf,
  auch der Timer, hielt an. Invariante: Bricht das Neuaufsetzen mit einem
  E/A-Fehler ab, bevor etwas bewegt ist, raeumt es seine eigene
  Vorbereitung ab und sagt das, oder nennt den Rest — an JEDER Schreibstelle
  zwischen dem Anlegen und dem Tausch. Gebaut als EIN Schutz um den ganzen
  Abschnitt; getestet je Schreibstelle (gemessene Menge, Ratsche ``==``).
  Dazu die zwei Schreiber, die die Ratsche der Runde H als offen fuehrte
  (``seite._schreibe``, ``zugangsprobe._schreibe_beleg``): Sie raeumen die
  Reste ihres Ziels jetzt mit der einen Erkennung des Betriebs
  (``tageslauf.raeume_schreibreste_von``).

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import builtins
import errno
import glob
import io
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import rechner_pipeline
from rechner_pipeline.betrieb import tageslauf as tl

SRC = Path(rechner_pipeline.__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[1]

#: Die Sonderzeichen eines glob-Musters, je in einem Ablagenamen.
SONDERNAMEN = ["daten[1]", "dat]en[", "daten*", "dat?n"]


def _subprozess(code: str, cwd: Path) -> subprocess.CompletedProcess:
    umgebung = {**os.environ, "PYTHONPATH": os.pathsep.join([str(SRC), str(REPO)]),
                "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run([sys.executable, "-c", code], env=umgebung, cwd=str(cwd),
                          capture_output=True, text=True, timeout=300)


# --------------------------------------------------------------------------- #
# I20: Vorbereitung und Tausch bei Sonderzeichen im Namen der Ablage
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("name", SONDERNAMEN + ["daten1"])
def test_eine_vorbereitung_wird_bei_jedem_ablagenamen_erkannt(tmp_path, name):
    """Neben ``<name>`` liegt eine nie veroeffentlichte Vorbereitung: Jeder
    Aufruf haelt benannt an, das Neuaufsetzen raeumt sie ab. ``daten1`` ist
    die Positivkontrolle (auch vor dem Fix gruen).

    Mutationsprobe: in ``_vorbereitungen_neben`` wieder ``glob`` mit dem
    unmaskierten Namen -> rot."""
    ablage = tl.Ablage(tmp_path / name)
    ablage.wurzel.mkdir()
    rest = tmp_path / f"{name}.neu-20260101T000000Z"
    (rest / "configs").mkdir(parents=True)
    with pytest.raises(tl.TageslaufError) as exc:
        with tl.lauf_sperre(ablage):
            pass
    assert rest.name in str(exc.value) and "nie veroeffentlicht" in str(exc.value)
    with tl.lauf_sperre(ablage, vorbereitung_abraeumen=True) as geraeumt:
        assert len(geraeumt) == 1 and rest.name in geraeumt[0]
    assert not rest.exists()


def test_die_vorbereitung_einer_nachbarablage_ist_nicht_die_eigene(tmp_path):
    """Gegenrichtung: ``daten[1].neu-*`` passte unmaskiert auf
    ``daten1.neu-<zeit>`` — die Vorbereitung der Nachbarablage ``daten1``
    hielt ``daten[1]`` an. Sie gehoert ihr nicht und bleibt unberuehrt."""
    ablage = tl.Ablage(tmp_path / "daten[1]")
    ablage.wurzel.mkdir()
    nachbar = tmp_path / "daten1.neu-20260101T000000Z"
    (nachbar / "configs").mkdir(parents=True)
    with tl.lauf_sperre(ablage, vorbereitung_abraeumen=True) as geraeumt:
        assert geraeumt == []
    assert (nachbar / "configs").is_dir()


@pytest.mark.parametrize("name", SONDERNAMEN + ["daten1"])
def test_der_unterbrochene_tausch_wird_bei_jedem_ablagenamen_vollendet(tmp_path, name):
    """Prozessende zwischen den zwei Umbenennungen: Die Ablage fehlt, das
    Archiv liegt, der fertige Aufbau nennt es. Der naechste Eintritt setzt
    den Aufbau ein, statt eine leere Ablage anzulegen."""
    from rechner_pipeline.betrieb.neuaufsetzen import PROVENIENZ_DATEI

    wurzel = tmp_path / name
    archiv = tmp_path / f"{name}.archiv-20260101T000000Z"
    archiv.mkdir()
    aufbau = tmp_path / f"{name}.neu-20260101T000000Z"
    (aufbau / "configs").mkdir(parents=True)
    (aufbau / PROVENIENZ_DATEI).write_text(json.dumps({"archiv": str(archiv)}),
                                           encoding="utf-8")
    with tl.lauf_sperre(tl.Ablage(wurzel)) as geraeumt:
        assert geraeumt == []
    assert (wurzel / PROVENIENZ_DATEI).is_file() and (wurzel / "configs").is_dir()
    assert not aufbau.exists()


#: Die Funktionen, deren Muster-Argument gemessen wird, und seine Stelle.
_MUSTER_ARG = {"glob": 0, "rglob": 0, "iglob": 0, "fnmatch": 1, "fnmatchcase": 1,
               "raeume_schreibreste_von": 1}


def _muster_stellen(wurzel: Path) -> Counter:
    """Jedes glob-Muster in ``betrieb/`` und ``gates/``, das KEIN fester Text
    ist (kein String-Literal): (Datei, Funktion, Muster als Quelltext)."""
    stellen: Counter = Counter()
    for schicht in ("betrieb", "gates"):
        for datei in sorted((wurzel / schicht).glob("*.py")):
            for n in ast.walk(ast.parse(datei.read_text(encoding="utf-8"))):
                if not isinstance(n, ast.Call):
                    continue
                name = (n.func.attr if isinstance(n.func, ast.Attribute)
                        else getattr(n.func, "id", None))
                stelle = _MUSTER_ARG.get(name)
                if stelle is None or len(n.args) <= stelle:
                    continue
                arg = n.args[stelle]
                if not isinstance(arg, ast.Constant):
                    stellen[(f"{schicht}/{datei.name}", name, ast.unparse(arg))] += 1
    return stellen


#: Die verbleibenden Muster mit veraenderlichem Anteil, je mit dem Grund, warum
#: ihr Text fest ist (Pruefrunde I, I20). Statische Ratsche (``==``): Ein neues
#: Muster aus einem Wert ist rot, bis hier steht, woher der Wert kommt — ein
#: Name des Bedieners wird maskiert (``glob.escape``) oder ohne Muster
#: verglichen.
MUSTER_MIT_FESTEM_TEXT = {
    ("betrieb/anfangsbestand.py", "raeume_schreibreste_von", "ziel.name"):
        "Name aus models.anfangsbestand (BELEG_RELATIV, SICHT_RELATIV), Konstante",
    ("betrieb/seite.py", "glob", "f'.{ziel.name}.*.tmp'"):
        "ziel ist <ablage>/seite/index.html, der Name eine Konstante",
    ("betrieb/seite.py", "raeume_schreibreste_von", "glob.escape(ziel.name)"):
        "maskiert",
    ("betrieb/zugangsprobe.py", "raeume_schreibreste_von", "glob.escape(out.name)"):
        "maskiert",
    ("betrieb/tageslauf.py", "fnmatchcase", "muster"):
        "Muster aus der Tabelle SCHREIBZIELE (Konstanten)",
    ("betrieb/tageslauf.py", "glob", "f'.{muster}.*.tmp'"):
        "muster ist ein Muster seiner Aufrufer: SCHREIBZIELE oder ein Eintrag hier",
    ("betrieb/tageslauf.py", "raeume_schreibreste_von", "muster"):
        "Schleife ueber SCHREIBZIELE (Konstanten)",
    ("betrieb/tageslauf.py", "glob", "f'{STAND_DIR}-*'"):
        "Konstante STAND_DIR",
    ("betrieb/uebernahme.py", "glob", "f'{gate}-*.json'"):
        "Gate-Name aus dem Code (GUELTIGE_GATES), ohne Musterzeichen",
    ("gates/_common.py", "glob", "f'*{GATE_LEDGER_SUFFIX}'"):
        "Konstante GATE_LEDGER_SUFFIX",
    ("gates/_common.py", "glob", "f'.{glob.escape(ziel.name)}.*.tmp'"):
        "maskiert",
    ("gates/abnahmebericht.py", "rglob", "schicht_datei"):
        "Konstante PB1_ROLLEN_DATEIEN['schichten']",
    ("gates/gate_entscheid.py", "glob", "O3_BELEG_GLOB"):
        "Konstante O3_BELEG_GLOB",
    ("gates/gate_entscheid.py", "glob", "f'.{args.gate}-*.json.*.tmp'"):
        "--gate hat choices=GUELTIGE_GATES, ohne Musterzeichen",
    ("gates/gate_entscheid.py", "glob", "f'{ABBRUCH_GATE}-*.json'"):
        "Konstante ABBRUCH_GATE",
    ("gates/gate_entscheid.py", "glob", "f'{gate}-*.json'"):
        "Gate-Name aus dem Code (GUELTIGE_GATES), ohne Musterzeichen",
    ("gates/stand_belegen.py", "glob", "f'{gate}-*.json'"):
        "Gate-Name aus dem Code (GUELTIGE_GATES), ohne Musterzeichen",
    ("gates/tarifwerk_belegen.py", "glob", "tw.CONFIG_MUSTER"):
        "Konstante CONFIG_MUSTER",
}


def test_ratsche_kein_glob_muster_aus_einem_namen_des_bedieners():
    """Statische Ratsche (``==``) ueber die Muster mit veraenderlichem Anteil.
    Vorher standen hier zweimal ``f'{wurzel.name}.neu-*'`` (tageslauf)."""
    assert _muster_stellen(SRC / "rechner_pipeline") == Counter(
        {k: 1 for k in MUSTER_MIT_FESTEM_TEXT})
    # Die Gate-Namen, die als fester Text gelten, tragen kein Musterzeichen.
    from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

    assert all(glob.escape(g) == g for g in GUELTIGE_GATES)


def test_ratsche_muster_positivkontrolle(tmp_path):
    """Die Ratsche sieht ein Muster aus einem Namen, nicht aber ein Literal."""
    (tmp_path / "betrieb").mkdir()
    (tmp_path / "gates").mkdir()
    (tmp_path / "betrieb" / "probe.py").write_text(
        "def a(w):\n    return w.parent.glob(f'{w.name}.neu-*')\n"
        "def b(w):\n    return w.glob('*.json')\n", encoding="utf-8")
    assert _muster_stellen(tmp_path) == Counter(
        {("betrieb/probe.py", "glob", "f'{w.name}.neu-*'"): 1})


# --------------------------------------------------------------------------- #
# I21: ein E/A-Fehler zwischen dem Anlegen und dem Tausch
# --------------------------------------------------------------------------- #


@pytest.fixture()
def gefuehrt(tmp_path):
    import datetime as dt

    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    assert tl.tageslauf(ablage, dt.date(2026, 2, 3))[0] == tl.EXIT_OK
    return ablage


def _na_argv(ablage, fall) -> list:
    from tests.freigabe_testschluessel import betriebsargs, linieargs
    from tests.test_betrieb_uebernahme import STICHTAG

    return ["--stand", str(ablage.wurzel), "--fall", str(fall),
            "--stichtag", STICHTAG.isoformat(), *betriebsargs("--betriebsschluessel"),
            *linieargs()]


class _Stoerung:
    """Zaehlt die Schreibstellen des Abschnitts zwischen dem Anlegen der
    Vorbereitung und dem Tausch und wirft an der ``k``-ten einen E/A-Fehler
    (ENOSPC), VOR dem Schreiben.

    Eine Schreibstelle ist ein Aufruf von open (Schreibmodus), os.open mit
    O_CREAT/O_WRONLY/O_RDWR, mkdir, rename, replace, link, symlink, unlink,
    rmdir, dessen Pfad in der Vorbereitung liegt, sowie die erste Umbenennung
    (Ablage -> Archiv), die den Abschnitt schliesst. Kein Schreiben ist ein
    mkdir auf ein vorhandenes Verzeichnis (``exist_ok``). Schreibt eine
    Bibliothek ohne diese Aufrufe (pyarrow in C++), ist das keine gemessene
    Stelle."""

    ARTEN = ("mkdir", "rename", "replace", "link", "symlink", "unlink", "rmdir")

    def __init__(self, monkeypatch, wurzel: Path, k: int):
        self.praefix = f"{wurzel.name}.neu-"
        self.archiv_praefix = f"{wurzel.name}.archiv-"
        self.k = k
        self.spur: list = []
        self.abschnitt_zu = False
        echt_open, echt_os_open = builtins.open, os.open

        def _open(datei, mode="r", *a, **kw):
            if isinstance(datei, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
                self._stelle(f"open:{mode}", datei)
            return echt_open(datei, mode, *a, **kw)

        def _os_open(pfad, flags, *a, **kw):
            if flags & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
                self._stelle("os.open", pfad)
            return echt_os_open(pfad, flags, *a, **kw)

        monkeypatch.setattr(builtins, "open", _open)
        monkeypatch.setattr(io, "open", _open)
        monkeypatch.setattr(os, "open", _os_open)
        for art in self.ARTEN:
            echt = getattr(os, art)
            zweiter = art in ("rename", "replace", "link", "symlink")

            def _f(*a, _echt=echt, _art=art, _zweiter=zweiter, **kw):
                self._stelle(f"os.{_art}", a[1] if _zweiter else a[0],
                             quelle=a[0] if _zweiter else None)
                return _echt(*a, **kw)
            monkeypatch.setattr(os, art, _f)

    def _stelle(self, art, pfad, quelle=None):
        if self.abschnitt_zu:
            return
        if art == "os.mkdir" and os.path.isdir(pfad):
            # mkdir(exist_ok=True) auf ein vorhandenes Verzeichnis schreibt
            # nichts; ein Fehler dort wird von exist_ok geschluckt.
            return
        teile = Path(os.fsdecode(pfad)).parts
        archivierung = (art == "os.rename" and teile and teile[-1].startswith(self.archiv_praefix))
        ab = next((i for i, t in enumerate(teile) if t.startswith(self.praefix)), None)
        if not archivierung and ab is None:
            return
        self.spur.append((art, teile[-1] if archivierung else "/".join(teile[ab:])))
        if archivierung:
            self.abschnitt_zu = True
        if len(self.spur) == self.k:
            raise OSError(errno.ENOSPC, "No space left on device (Test)", os.fsdecode(pfad))


def _neuaufsetzen_mit_stoerung(monkeypatch, gefuehrt, fall, k: int, capsys):
    from rechner_pipeline.betrieb import neuaufsetzen as na

    capsys.readouterr()
    with monkeypatch.context() as m:
        stoerung = _Stoerung(m, gefuehrt.wurzel, k)
        code = na.main(_na_argv(gefuehrt, fall))
    return code, stoerung, capsys.readouterr().err


#: Die gemessene Menge der Schreibstellen des Abschnitts (ungestoerter Lauf):
#: das Anlegen der Vorbereitung und ihrer configs, die Config, der Eingang
#: (eingang_anlegen), die Provenienz, die erste Umbenennung. Ratsche (``==``):
#: Eine neue Schreibstelle im Abschnitt aendert die Zahl und wird damit
#: mitgetestet.
ANZAHL_SCHREIBSTELLEN = 30


@pytest.fixture()
def fall(tmp_path):
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    return _fall_mit_nebentabellen(tmp_path)


def test_ratsche_die_schreibstellen_des_abschnitts(gefuehrt, fall, monkeypatch, capsys):
    """Der ungestoerte Lauf: gemessene Spur bis einschliesslich der
    Archivierung. Positivkontrolle der Messung: die ersten beiden Stellen
    sind das Anlegen der Vorbereitung und ihrer configs, die letzte die
    Archivierung."""
    code, stoerung, meldung = _neuaufsetzen_mit_stoerung(monkeypatch, gefuehrt, fall, 0, capsys)
    assert code == 0, meldung
    spur = stoerung.spur
    neu = spur[1][1]
    assert neu.startswith(f"{gefuehrt.wurzel.name}.neu-") and "/" not in neu, spur
    assert spur[:4] == [("os.mkdir", f"{neu}/configs"), ("os.mkdir", neu),
                        ("os.mkdir", f"{neu}/configs"),
                        ("open:wb", f"{neu}/configs/bestand.toml")], spur
    assert spur[-1][0] == "os.rename" and ".archiv-" in spur[-1][1], spur
    assert len(spur) == ANZAHL_SCHREIBSTELLEN, spur


@pytest.mark.parametrize("k", range(1, ANZAHL_SCHREIBSTELLEN + 1))
def test_ein_ea_fehler_vor_dem_tausch_hinterlaesst_keine_ungenannte_vorbereitung(
        gefuehrt, fall, monkeypatch, capsys, k):
    """I21, je Schreibstelle des Abschnitts: E/A-Fehler (ENOSPC) an der
    ``k``-ten Stelle. Danach: Exit 2, nichts bewegt (Ablage an ihrem Ort,
    Protokoll byte-gleich, kein Archiv), keine Vorbereitung liegt, die
    Meldung sagt, dass sie entfernt ist; der naechste Aufruf, der die Ablage
    betritt, haelt nicht an. Vorher blieb sie an Stelle 2/3 (Anlegen von
    configs) ungenannt liegen, und der Timer stand.

    Mutationsprobe: den Schutz wieder erst nach dem Anlegen von configs
    greifen lassen -> rot an den Stellen davor."""
    protokoll = gefuehrt.protokoll_pfad.read_bytes()
    code, stoerung, meldung = _neuaufsetzen_mit_stoerung(monkeypatch, gefuehrt, fall, k, capsys)
    assert len(stoerung.spur) >= k, stoerung.spur     # die Stoerung hat die Stelle erreicht
    assert code == 2, meldung
    assert "Traceback" not in meldung, meldung
    eltern = gefuehrt.wurzel.parent
    reste = sorted(p.name for p in eltern.iterdir()
                   if p.name.startswith(f"{gefuehrt.wurzel.name}.neu-"))
    assert reste == [], (stoerung.spur[k - 1], reste, meldung)
    assert "entfernt" in meldung and "nichts bewegt" in meldung, (stoerung.spur[k - 1], meldung)
    assert gefuehrt.protokoll_pfad.read_bytes() == protokoll
    assert not [p for p in eltern.iterdir() if ".archiv-" in p.name]
    with tl.lauf_sperre(gefuehrt) as geraeumt:
        assert geraeumt == []


def test_nach_einem_ea_fehler_laeuft_der_tag(gefuehrt, fall, monkeypatch, capsys):
    """Positivkontrolle am Tageslauf selbst fuer die Stelle des Funds (das
    Anlegen von configs nach dem Anlegen der Vorbereitung): Der Timer
    laeuft weiter."""
    from tests.freigabe_testschluessel import betriebsargs

    code, stoerung, meldung = _neuaufsetzen_mit_stoerung(monkeypatch, gefuehrt, fall, 3, capsys)
    assert code == 2 and stoerung.spur[2][1].endswith("/configs"), (stoerung.spur, meldung)
    assert tl.main(["--stand", str(gefuehrt.wurzel), "--heute", "2026-02-05",
                    *betriebsargs()]) == tl.EXIT_OK, capsys.readouterr().err


# --------------------------------------------------------------------------- #
# I21: die zwei offenen Schreiber der Runde H raeumen ihre Reste
# --------------------------------------------------------------------------- #


_SCHREIBER = {
    "seite": ("from rechner_pipeline.betrieb import seite as s\n",
              "s._schreibe(ziel, 'neu')\n"),
    "zugangsprobe": ("from rechner_pipeline.betrieb import zugangsprobe as s\n",
                     "s._schreibe_beleg(ziel, {'neu': True})\n"),
}


@pytest.mark.parametrize("schreiber", sorted(_SCHREIBER))
def test_ein_prozessende_beim_schreiben_hinterlaesst_keinen_dauerhaften_rest(tmp_path, schreiber):
    """Prozessende (os._exit) unmittelbar vor dem Einhaengen, im eigenen
    Prozess; danach derselbe Schreiber fuer dasselbe Ziel: kein Rest.
    ``zugangsprobe`` raeumte nur den Rest derselben Prozessnummer,
    ``seite._schreibe`` gar keinen.

    Mutationsprobe: das Raeumen im Schreiber entfernen -> rot."""
    ziel = tmp_path / "ziel[1].json"          # mit Musterzeichen im Namen
    ziel.write_text("alt", encoding="utf-8")
    fremd = tmp_path / ".anderes.json.123.tmp"   # Rest eines anderen Ziels: bleibt
    fremd.write_text("x", encoding="utf-8")
    import_, aufruf = _SCHREIBER[schreiber]
    code = (
        "import os, sys\n"
        "from pathlib import Path\n" + import_ +
        f"ziel = Path({str(ziel)!r})\n"
        "echt = os.replace\n"
        "def stirb(quelle, z, *a, **k):\n"
        "    if os.path.basename(os.fspath(z)) == ziel.name:\n"
        "        os._exit(137)\n"
        "    return echt(quelle, z, *a, **k)\n"
        "os.replace = stirb\n" + aufruf)
    lauf = _subprozess(code, tmp_path)
    assert lauf.returncode == 137, lauf.stderr
    reste = [p.name for p in tmp_path.iterdir() if p.name.startswith(f".{ziel.name}.")]
    assert len(reste) == 1, reste                  # die Probe hat den Ausfall erreicht
    assert ziel.read_text(encoding="utf-8") == "alt"
    lauf = _subprozess(import_ + "from pathlib import Path\n"
                       f"ziel = Path({str(ziel)!r})\n" + aufruf, tmp_path)
    assert lauf.returncode == 0, lauf.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([ziel.name, fremd.name])
