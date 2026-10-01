"""Der lebende Stand ist der des Codes, der rechnet — ``--repo-root`` muss ihn tragen.

Befund der Pruefrunde G (G12): Den lebenden Stand von Kern (A-K2) und
Tarifwerk (A-T1) rechnete das System aus den Dateien unter ``--repo-root``,
nicht aus dem Paket, das ausgefuehrt wird. Mit ``PYTHONPATH`` auf einen Klon
mit veraendertem Kern und ``--repo-root`` auf das Original meldete A-M4
"keine Aenderung seit Abnahme", waehrend ein anderer Kern rechnete; der
Systemstand des Snapshots nannte Commit und ``dirty`` des Originals.

Invariante: Der Stand, den ein Gate oder Produzent als "lebend" ausweist,
ist der des Codes, der gerade rechnet. Gebaut an EINER Stelle, durch die
jeder Pfad muss — dort, wo ``--repo-root`` aufgeloest wird:
``gates._provenienz.lebendes_repo`` ist der ``type`` des Arguments in jedem
Kommando, das es fuehrt. Sie haelt den Hash des ausgefuehrten Pakets
(``_quellcode_sha256``) gegen denselben Hash ueber
``<repo_root>/src/rechner_pipeline`` und verweigert sonst mit beiden Hashes
und dem Ausweg. Kein Schalter zum Abschalten.

Die Proben bauen einen "Klon" als Kopie des Pakets in ``tmp_path`` —
einmal mit einer Zeile Kernaenderung (das Repro des Pruefers), einmal
unveraendert (Positivkontrolle: inhaltsgleich ist zulaessig, auch an
anderem Ort).

Knoten: system/assurance
"""

from __future__ import annotations

import argparse
import ast
import shutil
from collections import Counter
from pathlib import Path

import pytest

from rechner_pipeline.gates import (
    fall_belegen,
    gate_entscheid,
    kernstand_belegen,
    stand_belegen,
    tarifwerk_belegen,
)
from rechner_pipeline.gates import _provenienz
from rechner_pipeline.gates._common import GateArgumentError

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


def _klon(tmp_path: Path, *, veraendert: bool) -> Path:
    """Ein Baum mit ``src/rechner_pipeline`` — dem ausgefuehrten Paket gleich
    oder um eine Zeile im Kern veraendert (Stornoabzug verdoppelt)."""
    klon = tmp_path / ("klon" if veraendert else "klon-gleich")
    shutil.copytree(SRC, klon / "src" / "rechner_pipeline",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if veraendert:
        datei = klon / "src" / "rechner_pipeline" / "kern" / "beitragsreduktion.py"
        alt = datei.read_text(encoding="utf-8")
        neu = alt.replace("return 1.0 - min(stoab, mrv) / mrv",
                          "return 1.0 - 2.0 * min(stoab, mrv) / mrv")
        assert neu != alt, "die Zeile des Repros fehlt — die Probe veraendert nichts"
        datei.write_text(neu, encoding="utf-8")
    return klon


def _linie(tmp_path: Path) -> Path:
    from tests.zeichnung_fixture import linie_anlegen

    return linie_anlegen(tmp_path / "bereich")


# --------------------------------------------------------------------------- #
# Die Regel
# --------------------------------------------------------------------------- #


def test_ein_fremder_baum_wird_benannt_verweigert(tmp_path):
    """Rot vor dem Fix: es gab die Pruefung nicht (AttributeError). Die
    Meldung nennt beide Hashes und den Ausweg."""
    klon = _klon(tmp_path, veraendert=True)
    with pytest.raises(argparse.ArgumentTypeError) as fehler:
        _provenienz.lebendes_repo(str(klon))
    meldung = str(fehler.value)
    assert _provenienz._quellcode_sha256()[:16] in meldung
    assert _provenienz.paket_sha256(klon / "src" / "rechner_pipeline")[:16] in meldung
    assert "Ausweg" in meldung and "PYTHONPATH" in meldung, meldung


def test_ein_inhaltsgleicher_baum_an_anderem_ort_ist_zulaessig(tmp_path):
    """Positivkontrolle: Die Regel verlangt den INHALT, nicht den Ort — ein
    nicht editierbar installiertes Paket neben seinem Repo bleibt moeglich."""
    klon = _klon(tmp_path, veraendert=False)
    assert _provenienz.lebendes_repo(str(klon)) == klon.resolve()
    assert _provenienz.lebendes_repo(str(REPO)) == REPO.resolve()
    assert _provenienz.paket_sha256(SRC) == _provenienz._quellcode_sha256()


def test_ein_baum_ohne_paket_wird_verweigert(tmp_path):
    with pytest.raises(argparse.ArgumentTypeError, match="kein Paket"):
        _provenienz.lebendes_repo(str(tmp_path))


# --------------------------------------------------------------------------- #
# Ueber die echten Kommandos (der Weg des Pruefers)
# --------------------------------------------------------------------------- #


def test_das_gate_rechnet_nicht_gegen_einen_fremden_baum(tmp_path):
    """Rot vor dem Fix: Die Ablehnung im Linienbereich wurde unter dem
    Systemstand des fremden Baums geschrieben (exit 0)."""
    linie = _linie(tmp_path)
    klon = _klon(tmp_path, veraendert=True)
    with pytest.raises(GateArgumentError) as fehler:
        gate_entscheid.main([
            "--linie", str(linie), "--gate", "A-K2", "--entscheid", "abgelehnt",
            "--rolle", "agent/rechenkern", "--entscheider", "a", "--begruendung", "b",
            "--repo-root", str(klon)])
    assert "--repo-root" in str(fehler.value) and "Ausweg" in str(fehler.value)
    assert not (linie / "entscheide").exists() or not list((linie / "entscheide").iterdir())


@pytest.mark.parametrize("kommando", ("kernstand_belegen", "tarifwerk_belegen",
                                      "stand_belegen verweisen", "stand_belegen tbox",
                                      "fall_belegen abbruch"))
def test_kein_produzent_weist_den_stand_eines_fremden_baums_als_lebend_aus(
        tmp_path, capsys, kommando):
    """Rot vor dem Fix: jeder Produzent rechnete aus dem uebergebenen Baum."""
    linie = _linie(tmp_path)
    klon = str(_klon(tmp_path, veraendert=True))
    argv = {
        "kernstand_belegen": (kernstand_belegen.main, [
            "--linie", str(linie), "--repo-root", klon, "--von", "HEAD", "--begruendung", "x"]),
        "tarifwerk_belegen": (tarifwerk_belegen.main, [
            "--linie", str(linie), "--repo-root", klon, "--von", "HEAD", "--begruendung", "x"]),
        "stand_belegen verweisen": (stand_belegen.main, [
            "verweisen", "--fall", str(tmp_path / "fall"), "--gate", "A-K2",
            "--linie", str(linie), "--repo-root", klon]),
        "stand_belegen tbox": (stand_belegen.main, [
            "tbox", "--linie", str(linie), "--repo-root", klon, "--artefakt", "x.md",
            "--begruendung", "x"]),
        "fall_belegen abbruch": (fall_belegen.main, [
            "abbruch", "--fall", str(tmp_path / "fall"), "--repo-root", klon, "--grund", "g",
            "--bestand", "b", "--uebergabe", "u"]),
    }[kommando]
    with pytest.raises(SystemExit) as ende:
        argv[0](argv[1])
    assert ende.value.code == 2
    err = capsys.readouterr().err
    assert "--repo-root" in err and "nicht das ausgefuehrte Paket" in err, err


# --------------------------------------------------------------------------- #
# Ratsche: jedes Kommando mit --repo-root loest ihn ueber die eine Stelle auf
# --------------------------------------------------------------------------- #


def _repo_root_argumente(quelle: str, datei: str) -> Counter:
    """Je ``add_argument("--repo-root", ...)``: ob ``type=lebendes_repo``."""
    treffer: Counter = Counter()
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.Call) and getattr(k.func, "attr", None) == "add_argument" \
                and k.args and isinstance(k.args[0], ast.Constant) \
                and k.args[0].value == "--repo-root":
            typ = [w.value for w in k.keywords if w.arg == "type"]
            name = (getattr(typ[0], "id", None) or getattr(typ[0], "attr", None)) if typ else None
            treffer[(datei, name == "lebendes_repo")] += 1
    return treffer


#: Gemessen 2026-10-01 (AST ueber ``src``; ein einzeiliges grep uebersah den
#: mehrzeiligen Aufruf in ``ontologie/impact.py``): jedes
#: Kommando der Schicht gates, das ``--repo-root`` fuehrt. Ein neues Kommando
#: mit ``--repo-root`` ohne die eine Stelle ist rot.
KOMMANDOS_MIT_REPO_ROOT = Counter({
    ("gates/abnahmebericht.py", True): 1,
    ("gates/abox_merge.py", True): 1,
    ("gates/abox_validate.py", True): 1,
    ("gates/aktuartest.py", True): 1,
    ("gates/aktuartest_lauf.py", True): 1,
    ("gates/bestand_validate.py", True): 1,
    ("gates/extract.py", True): 1,
    ("gates/fall_belegen.py", True): 1,
    ("gates/fuehrungsprobe.py", True): 1,
    ("gates/gate_entscheid.py", True): 1,
    ("gates/generation_golden.py", True): 1,
    ("gates/kernstand_belegen.py", True): 1,
    ("gates/migrationssuite_lauf.py", True): 1,
    ("gates/stand_belegen.py", True): 2,
    ("gates/tarifwerk_belegen.py", True): 1,
    ("gates/verankerung_belegen.py", True): 1,
})
#: Benannte Ausnahmen: ``ontologie.landkarte`` und ``ontologie.impact`` lesen
#: den Baum unter ``--repo-root`` als GEGENSTAND (eine Karte des Codes, der
#: dort liegt; die Testmodule, die geaenderte Dateien erreichen) und weisen
#: keinen lebenden Stand aus; die Schicht ontologie darf gates nicht
#: importieren (Schichtenkarte).
AUSNAHMEN = {("ontologie/landkarte.py", False): 1, ("ontologie/impact.py", False): 1}


def test_ratsche_jedes_repo_root_argument_geht_durch_die_eine_stelle():
    gefunden: Counter = Counter()
    for pfad in sorted(SRC.rglob("*.py")):
        gefunden += _repo_root_argumente(pfad.read_text(encoding="utf-8"),
                                         pfad.relative_to(SRC).as_posix())
    assert gefunden == KOMMANDOS_MIT_REPO_ROOT + Counter(AUSNAHMEN)


def test_ratsche_positivkontrolle_des_detektors():
    quelle = ('p.add_argument("--repo-root", type=lebendes_repo)\n'
              'p.add_argument("--repo-root", type=_provenienz.lebendes_repo, default=".")\n'
              'p.add_argument("--repo-root", dest="repo_root", default=None)\n'
              'p.add_argument("--repo", type=lebendes_repo)\n')
    assert _repo_root_argumente(quelle, "x.py") == Counter({("x.py", True): 2,
                                                             ("x.py", False): 1})


# --------------------------------------------------------------------------- #
# Pruefrunde I, Nachtrag: der Rueckfall ohne --repo-root
# --------------------------------------------------------------------------- #
#
# Ohne ``--repo-root`` fielen ``gates.extract`` und ``gates.abnahmebericht`` auf
# das Arbeitsverzeichnis zurueck, ``gates.generation_golden`` auf den Baum des
# Pakets (``__file__``) — alle drei an ``lebendes_repo`` vorbei (der Baum muss
# inhaltsgleich mit dem ausgefuehrten Paket sein, kein fremder Bytecode). Der
# Abnahmebericht erzeugt die Vorlage, die ein Mensch fuer A-M4 zeichnet; aus
# dem Rueckfall kam der Systemstand, gegen den sie Suite, P-B1 und
# Fuehrungsprobe haelt. Ein ``default="."`` am Argument geht durch den
# ``type`` (argparse wandelt String-Vorgaben) und ist damit schon gedeckt.


def _rueckfaelle(quelle: str, datei: str) -> Counter:
    """Je Ausdruck ``<x> if args.repo_root else <rueckfall>``: der Rueckfall,
    eingeteilt in ``None`` (kein Baum), ``lebendes_repo`` (die eine Pruefung)
    oder den Quelltext (ein Baum an ihr vorbei)."""
    treffer: Counter = Counter()
    for k in ast.walk(ast.parse(quelle)):
        if isinstance(k, ast.IfExp) and "repo_root" in ast.unparse(k.test):
            sonst = k.orelse
            if isinstance(sonst, ast.Constant) and sonst.value is None:
                art = "None"
            elif isinstance(sonst, ast.Call) and getattr(sonst.func, "id", None) == "lebendes_repo":
                art = "lebendes_repo"
            else:
                art = ast.unparse(sonst)
            treffer[(datei, art)] += 1
    return treffer


def _arbeitsverzeichnisse(quelle: str, datei: str) -> Counter:
    """Je ``Path.cwd()``/``os.getcwd()``: wofuer — als Argument von
    ``lebendes_repo``, als Wurzel des Diagnostik-Rueckfalls
    (``cwd / "runs" / "diagnostics"``, kein Repo-Baum) oder anders."""
    baum = ast.parse(quelle)
    eltern = {kind: k for k in ast.walk(baum) for kind in ast.iter_child_nodes(k)}
    treffer: Counter = Counter()
    for k in ast.walk(baum):
        if isinstance(k, ast.Call) and ast.unparse(k.func) in ("Path.cwd", "os.getcwd"):
            oben = eltern.get(k)
            if isinstance(oben, ast.Call) and getattr(oben.func, "id", None) == "lebendes_repo":
                art = "lebendes_repo"
            else:
                kette = k
                while isinstance(eltern.get(kette), ast.BinOp):
                    kette = eltern[kette]
                art = "diagnostics" if ast.unparse(kette).endswith("'diagnostics'") else "anders"
            treffer[(datei, art)] += 1
    return treffer


#: Gemessen (AST ueber ``gates/``). ``==``: Ein neuer Rueckfall an der einen
#: Pruefung vorbei ist rot.
RUECKFAELLE = Counter({
    ("gates/abnahmebericht.py", "None"): 2,
    ("gates/abnahmebericht.py", "lebendes_repo"): 1,
    ("gates/abox_merge.py", "None"): 2,
    ("gates/abox_validate.py", "None"): 1,
    ("gates/aktuartest.py", "None"): 1,
    ("gates/bestand_validate.py", "None"): 2,
    ("gates/extract.py", "lebendes_repo"): 1,
    ("gates/gate_entscheid.py", "None"): 6,
    ("gates/generation_golden.py", "None"): 1,
    ("gates/generation_golden.py", "lebendes_repo"): 1,
    # ``repo_root is not None``: eine Liste, kein Baum.
    ("gates/gate_entscheid.py", "[]"): 1,
    ("gates/stand_belegen.py", "[]"): 1,
    # Der Ledger eines Aufruffehlers nennt den rohen Wert (``repo_root`` des
    # Ledgers ist reserviert, ungenutzt).
    ("gates/_common.py", "None"): 1,
})
ARBEITSVERZEICHNISSE = Counter({
    ("gates/_common.py", "diagnostics"): 1,
    ("gates/abnahmebericht.py", "diagnostics"): 1,
    ("gates/abnahmebericht.py", "lebendes_repo"): 1,
    ("gates/abox_merge.py", "diagnostics"): 1,
    ("gates/abox_validate.py", "diagnostics"): 1,
    ("gates/aktuartest.py", "diagnostics"): 1,
    ("gates/bestand_validate.py", "diagnostics"): 1,
    ("gates/extract.py", "diagnostics"): 1,
    ("gates/extract.py", "lebendes_repo"): 1,
    ("gates/gate_entscheid.py", "diagnostics"): 1,
    ("gates/generation_golden.py", "diagnostics"): 1,
})


def test_ratsche_jeder_rueckfall_geht_durch_die_eine_stelle():
    """Statisch (``==``): Kein Ausdruck unter ``gates/`` bestimmt ohne
    ``--repo-root`` einen Baum an ``lebendes_repo`` vorbei, und jedes
    Arbeitsverzeichnis ist entweder ihr Argument oder die Wurzel des
    Diagnostik-Rueckfalls."""
    rueck: Counter = Counter()
    cwd: Counter = Counter()
    for pfad in sorted((SRC / "gates").glob("*.py")):
        quelle, name = pfad.read_text(encoding="utf-8"), pfad.relative_to(SRC).as_posix()
        rueck += _rueckfaelle(quelle, name)
        cwd += _arbeitsverzeichnisse(quelle, name)
    assert rueck == RUECKFAELLE
    assert cwd == ARBEITSVERZEICHNISSE


def test_ratsche_rueckfall_positivkontrolle():
    quelle = ("a = Path(args.repo_root) if args.repo_root else Path.cwd()\n"
              "b = Path(args.repo_root) if args.repo_root else lebendes_repo(Path.cwd())\n"
              "c = Path(args.repo_root) if args.repo_root else None\n"
              "d = Path(args.d) if args.d else Path.cwd() / 'runs' / 'diagnostics'\n")
    assert _rueckfaelle(quelle, "x.py") == Counter({
        ("x.py", "Path.cwd()"): 1, ("x.py", "lebendes_repo"): 1, ("x.py", "None"): 1})
    assert _arbeitsverzeichnisse(quelle, "x.py") == Counter({
        ("x.py", "anders"): 1, ("x.py", "lebendes_repo"): 1, ("x.py", "diagnostics"): 1})


def _leere_eingaben(tmp_path: Path) -> list:
    """Vorhandene (leere) Pflichtdateien: A-M4 kommt damit bis zur Wahl des
    Baums; was danach scheitert, ist hier nicht der Gegenstand."""
    eingaben = []
    for flag in ("--suite", "--spec", "--transformation-ergebnis",
                 "--bestandsbericht-vor", "--bestandsbericht-nach"):
        datei = tmp_path / "eingaben" / (flag.strip("-") + ".json")
        datei.parent.mkdir(exist_ok=True)
        datei.write_text("{}", encoding="utf-8")
        eingaben += [flag, str(datei)]
    return eingaben + ["--titel", "t", "--stichtag-1", "2025-12-31",
                       "--stichtag-2", "2026-12-31",
                       "--bericht", str(tmp_path / "bericht.html"),
                       "--diagnostics-dir", str(tmp_path / "diagnostics")]


@pytest.mark.parametrize("kommando", ("abnahmebericht", "extract"))
def test_ohne_repo_root_wird_ein_fremdes_arbeitsverzeichnis_verweigert(
        tmp_path, monkeypatch, kommando):
    """Rot vor dem Fix: Ohne ``--repo-root`` rechnete A-M4 (und P-Q1) aus dem
    Arbeitsverzeichnis, auch wenn es ein Baum mit veraendertem Kern war.
    Jetzt: Exit 2 mit der Meldung von ``lebendes_repo``. Positivkontrolle:
    aus dem Baum des Pakets kommt keine solche Meldung.

    Mutationsprobe: den Rueckfall wieder auf ``Path.cwd()`` setzen -> rot."""
    from rechner_pipeline.gates import abnahmebericht, extract

    main, argv = {
        "abnahmebericht": (abnahmebericht.main, _leere_eingaben(tmp_path)),
        "extract": (extract.main, ["--diagnostics-dir", str(tmp_path / "diagnostics")]),
    }[kommando]
    klon = _klon(tmp_path, veraendert=True)
    monkeypatch.chdir(klon)
    ergebnis = main(argv)
    meldung = " ".join(e["message"] for e in ergebnis.errors)
    assert ergebnis.exit_code == 2, (ergebnis.exit_code, meldung)
    assert "nicht das ausgefuehrte Paket" in meldung and "Arbeitsverzeichnis" in meldung, meldung
    monkeypatch.chdir(REPO)
    ergebnis = main(argv)
    meldung = " ".join(e["message"] for e in ergebnis.errors)
    assert "nicht das ausgefuehrte Paket" not in meldung, meldung


def test_p_k1_prueft_auch_den_baum_des_pakets(tmp_path, monkeypatch):
    """P-K1 faellt ohne ``--repo-root`` auf den Baum des Pakets zurueck; der
    geht jetzt durch dieselbe Pruefung. Einen fremden Bytecode im
    ausgefuehrten Paket legt der Test nicht an (er schriebe in den
    Repo-Baum); er zeigt die Verdrahtung: verweigert ``lebendes_repo``, endet
    P-K1 benannt mit Exit 2, statt einen Beleg zu schreiben."""
    from rechner_pipeline.gates import generation_golden
    from tests.e2e_fixture import bereite_pk1_fall

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",))

    def _verweigert(wert):
        raise argparse.ArgumentTypeError(f"Probe: {wert} verweigert")

    monkeypatch.setattr(generation_golden, "lebendes_repo", _verweigert)
    ergebnis = generation_golden.main(["--fall", str(fall), "--generation", "klv/tg2012"])
    meldung = " ".join(e["message"] for e in ergebnis.errors)
    assert ergebnis.exit_code == 2, (ergebnis.exit_code, meldung)
    assert "Probe:" in meldung and "Baum des ausgefuehrten Pakets" in meldung, meldung
