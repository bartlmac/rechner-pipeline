"""Pruefrunde I, Fund I14 — Tarifregeln ausserhalb der Engines haben keine Vorgabe.

Die Migrationssuite rechnete die Scheibe eines Erhoehungs-Geschaeftsvorfalls
ZWISCHEN den Stichtagen immer ohne gamma1: ``erhoehungs_scheibe`` wurde dort
ohne ``gamma1_uebernehmen`` gerufen, und die Vorgabe des Kerns war die Regel
des eigenen Geschaefts. Die belegte Tarifregel ``scheiben_mit_gamma1`` wirkte
nur auf die Alt-Scheiben; eine Lieferung nach der belegten Regel wurde mit
Residuum 0,2338 verworfen. ADR-024 (fuenfter Nachtrag, Punkt 3) fuehrte die
Vorgaben im Kern und in ``bestand/`` als benannte Grenze — die Runde zeigt,
dass sie wirkt.

Invariante (Klasse): Ein Argument oder Feld, das eine Tarifregel traegt (ein
Merkmal aus ``tbox.TARIFWERK_MERKMALE`` oder dem Quellverfahren, dazu
``gamma1_uebernehmen``, ``verfahren`` der Herabsetzung und das ganze
``tarifwerk``), hat in ``kern/`` und ``bestand/`` keine Vorgabe — jeder
Aufrufer nennt die Regel aus dem Tarifwerk, das er haelt. Was bleibt, steht
mit Grund in der Ratsche (``==``), damit die Menge nicht waechst.

Knoten: klv
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import List, Tuple

import pytest

from rechner_pipeline.kern.model_point import KLV_DEFAULT
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.ontologie.tbox import QUELLVERFAHREN_WERTE, TARIFWERK_MERKMALE
from rechner_pipeline.qa.migrationssuite import GeVoErwartung, VertragsPruefung, pruefe_vertrag

SRC = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"

MP = dataclasses.replace(KLV_DEFAULT, sum_insured=50000.0, zw=1)
M1, M2 = 5 * 12 + 3, 7 * 12 + 3          # Stichtage: Monat 63 und 87
ERH_JAHR, ERH_VS = 6, 5000.0             # Erhoehung am Jahrestag 6 (Monat 72)


def _auftrag(gamma1: bool, *, vorgaenge=(), dk_1: float = 0.0, dk_2: float = 0.0) -> VertragsPruefung:
    return VertragsPruefung(
        police_id="P1", model_point=dataclasses.asdict(MP),
        monate_stichtag_1=M1, monate_stichtag_2=M2,
        dk_erwartet_1=dk_1, dk_erwartet_2=dk_2,
        gevos=(GeVoErwartung(art="ERH", monate=12 * ERH_JAHR, betrag_erwartet=ERH_VS),),
        vorgaenge=tuple(vorgaenge),
        scheiben_mit_gamma1=gamma1, stoab_je_baustein=False, tku_umfang="alle_bausteine",
        dk_am_jahrestag=False)


def _dk2(v: VertragsPruefung) -> float:
    r = pruefe_vertrag(v, red_verfahren="prospektiv")
    return {p["groesse"]: p["system"] for p in r["pruefungen"]}["dk_stichtag_2"]


def _scheibe_soll(gamma1: bool) -> float:
    """Reserve der Scheibe am zweiten Stichtag aus ihrer eigenen Reserveformel:
    Modellpunkt von Hand versetzt (x+e, n-e, t-e, Summe), gamma1 nach der
    Regel — nicht ueber ``erhoehungs_scheibe`` und nicht ueber die Suite."""
    mp = dataclasses.replace(MP, x=MP.x + ERH_JAHR, n=MP.n - ERH_JAHR, t=MP.t - ERH_JAHR,
                             sum_insured=ERH_VS, gamma1=MP.gamma1 if gamma1 else 0.0)
    return Rechenkern(mp).monatsreserve(M2 - 12 * ERH_JAHR).vx_mrv


def test_i14_erh_zwischen_den_stichtagen_folgt_der_belegten_regel():
    """Auf 9fa1538 rot: unter True und False derselbe Wert (13887,8638, die
    Rechnung ohne gamma1). Soll: zwei Werte, und der unter True ist Grundvertrag
    plus Scheibe nach der Reserveformel mit gamma1."""
    ist_true, ist_false = _dk2(_auftrag(True)), _dk2(_auftrag(False))
    soll_true = Rechenkern(MP).monatsreserve(M2).vx_mrv + _scheibe_soll(True)
    soll_false = Rechenkern(MP).monatsreserve(M2).vx_mrv + _scheibe_soll(False)
    assert abs(soll_true - soll_false) > 0.1          # die Regel wirkt in der Sollrechnung
    assert ist_true == pytest.approx(soll_true, rel=1e-12, abs=1e-9), (ist_true, soll_true)
    assert ist_false == pytest.approx(soll_false, rel=1e-12, abs=1e-9), (ist_false, soll_false)


def test_i14_auch_auf_dem_weg_ueber_die_vorgangsfolge():
    """Derselbe Vertrag mit einer Herabsetzung im Jahr 2 (Weg ueber die
    Vorgangsfolge): Die Scheibe der Erhoehung nach der Herabsetzung ist ein
    gewoehnlicher Baustein, also unterscheiden sich die beiden Regeln um genau
    die Differenz der Scheibenreserven (unabhaengig gerechnet). Auf 9fa1538:
    beide gleich (11920,3313)."""
    folge = ((2, 0.8, "prospektiv"),)
    differenz = _dk2(_auftrag(True, vorgaenge=folge)) - _dk2(_auftrag(False, vorgaenge=folge))
    assert differenz == pytest.approx(_scheibe_soll(True) - _scheibe_soll(False), rel=1e-9, abs=1e-9)
    assert abs(differenz) > 0.1


def test_i14_das_urteil_folgt_der_belegten_regel():
    """Eine Lieferung nach der belegten Regel (gamma1 je Scheibe) besteht; eine
    nach der Regel des eigenen Geschaefts wird verworfen (auf 9fa1538
    umgekehrt)."""
    dk_1 = round(Rechenkern(MP).monatsreserve(M1).vx_mrv, 2)
    grund_2 = Rechenkern(MP).monatsreserve(M2).vx_mrv
    belegt = _auftrag(True, dk_1=dk_1, dk_2=round(grund_2 + _scheibe_soll(True), 2))
    fremd = _auftrag(True, dk_1=dk_1, dk_2=round(grund_2 + _scheibe_soll(False), 2))
    assert pruefe_vertrag(belegt, red_verfahren="prospektiv")["bestanden"]
    assert not pruefe_vertrag(fremd, red_verfahren="prospektiv")["bestanden"]


# --------------------------------------------------------------------------- #
# Ratsche: die verbleibenden Vorgaben in kern/ und bestand/
# --------------------------------------------------------------------------- #

#: Namen, unter denen eine Tarifregel in eine Funktion reicht. ``verfahren``
#: ist das Verfahren der Herabsetzung (red_verfahren der Generation),
#: ``gamma1_uebernehmen`` die Regel scheiben_mit_gamma1 im Kern, ``tarifwerk``
#: das ganze Tarifwerk einer Generation.
REGEL_NAMEN = (frozenset(TARIFWERK_MERKMALE) | frozenset(QUELLVERFAHREN_WERTE)
               | {"dk_am_jahrestag", "gamma1_uebernehmen", "verfahren", "tarifwerk"})


def regelstellen(quelltext: str) -> List[Tuple[str, str, bool]]:
    """(Ort, Name, hat Vorgabe) fuer jedes regeltragende Argument JEDER Funktion
    und Methode (auch verschachtelt) und jedes regeltragende Feld einer Klasse."""
    aus: List[Tuple[str, str, bool]] = []
    for knoten in ast.walk(ast.parse(quelltext)):
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = knoten.args
            positional = a.posonlyargs + a.args
            mit_vorgabe = {x.arg for x in positional[len(positional) - len(a.defaults):]}
            mit_vorgabe |= {x.arg for x, d in zip(a.kwonlyargs, a.kw_defaults) if d is not None}
            for arg in positional + a.kwonlyargs:
                if arg.arg in REGEL_NAMEN:
                    aus.append((knoten.name, arg.arg, arg.arg in mit_vorgabe))
        elif isinstance(knoten, ast.ClassDef):
            for feld in knoten.body:
                if (isinstance(feld, ast.AnnAssign) and isinstance(feld.target, ast.Name)
                        and feld.target.id in REGEL_NAMEN):
                    wert = feld.value
                    vorgabe = wert is not None and not (
                        isinstance(wert, ast.Call) and ast.unparse(wert.func).endswith("field")
                        and not any(k.arg in ("default", "default_factory") for k in wert.keywords))
                    aus.append((knoten.name, feld.target.id, vorgabe))
    return aus


def _mit_vorgabe() -> set:
    return {(str(p.relative_to(SRC)), ort, name)
            for schicht in ("kern", "bestand")
            for p in sorted((SRC / schicht).rglob("*.py"))
            for ort, name, vorgabe in regelstellen(p.read_text(encoding="utf-8")) if vorgabe}


def test_i14_ratsche_die_verbleibenden_vorgaben_sind_benannt():
    """Ratsche (statisch, ``==``): Jede verbleibende Vorgabe hat ihren Grund.

    * ``kern/rechenkern.py vertrags_monatsreserve stoab_je_baustein`` — ein
      Aufrufer ausserhalb dieses Zuschnitts (``gates/verankerung_belegen.py``)
      und ``bestand.migrationszugang.bestimme_serie_mit_kandidaten`` nennen die
      Regel nicht; beide lesen nur ``vx_mrv``, das vom Merkmal nicht abhaengt
      (benannte Grenze, Tarifplan KLV 7, ADR-024 Nachtrag 5 Punkt 3).
    * ``kern/vorgangsfolge.py tku_umfang_fuer tku_umfang`` — ``None`` ist keine
      Regel des eigenen Geschaefts, sondern die Ableitung aus dem Verfahren des
      Bedingungswerks der Generation (Tarifplan KLV 7.2, Entscheid B1).
    * ``bestand/config.py TarifGeneration`` (vier Merkmale) — die Config der
      Generation IST die Quelle des Tarifwerks der Fuehrung; fuer eine
      uebernommene Generation schreibt die Uebernahme jedes Merkmal
      ausdruecklich (``generation-zellen.toml``), und Fuehrungsprobe und
      Registrierung halten die Config gegen den Beleg.
    * ``bestand/migrationszugang.py uebernehmen fenster`` — ``None`` heisst
      "kein Fenster"; die Form, die eines braucht (``konstantes_fenster``),
      verweigert ohne es benannt.
    """
    assert _mit_vorgabe() == {
        ("kern/rechenkern.py", "vertrags_monatsreserve", "stoab_je_baustein"),
        ("kern/vorgangsfolge.py", "tku_umfang_fuer", "tku_umfang"),
        ("bestand/config.py", "TarifGeneration", "scheiben_mit_gamma1"),
        ("bestand/config.py", "TarifGeneration", "stoab_je_baustein"),
        ("bestand/config.py", "TarifGeneration", "red_verfahren"),
        ("bestand/config.py", "TarifGeneration", "tku_umfang"),
        ("bestand/migrationszugang.py", "uebernehmen", "fenster"),
    }, sorted(_mit_vorgabe())


@pytest.mark.parametrize("quelltext, erwartet", [
    ("def f(v, *, gamma1_uebernehmen=False): pass", [("f", "gamma1_uebernehmen", True)]),
    ("class K:\n    def m(self, tarifwerk=None): pass\n", [("m", "tarifwerk", True)]),
    ("def f(k, j, a, n, verfahren='prospektiv', *, z=0): pass", [("f", "verfahren", True)]),
    ("def f(v, *, verfahren): pass", [("f", "verfahren", False)]),
    ("class K:\n    stoab_je_baustein: bool = False\n", [("K", "stoab_je_baustein", True)]),
    ("def f(v, *, andere=1): pass", []),
])
def test_i14_positivkontrolle_der_detektor_sieht_eine_vorgabe(quelltext, erwartet):
    assert regelstellen(quelltext) == erwartet


def test_i14_ohne_regel_wird_verweigert():
    """Verhalten, nicht nur Quelltext: Wer die Regel nicht nennt, bekommt einen
    TypeError statt der Regel des eigenen Geschaefts."""
    from rechner_pipeline.bestand.kernlauf import vertrags_rkw
    from rechner_pipeline.kern.beitragsreduktion import reduziere, reduziere_geschichtet
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe

    kern = Rechenkern(MP)
    with pytest.raises(TypeError, match="gamma1_uebernehmen"):
        erhoehungs_scheibe(MP, 3, 1000.0)
    with pytest.raises(TypeError, match="verfahren"):
        reduziere(kern, 3, 0.5)
    with pytest.raises(TypeError, match="stoab_je_baustein|verfahren"):
        reduziere_geschichtet(kern, [], 3, 0.5)
    with pytest.raises(TypeError, match="stoab_je_baustein"):
        vertrags_rkw(kern, [], 3)
