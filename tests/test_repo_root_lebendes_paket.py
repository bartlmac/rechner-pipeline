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
