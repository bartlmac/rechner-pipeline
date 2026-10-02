"""Die Engines der Bestandsstrecke tragen fuer keine Tarifregel eine Vorgabe.

Befund Pruefrunde H (H12): Der Skill ``pruefe-migrationscontrolling``
beschrieb den Weg "Pruefauftraege selbst bauen, ``pruefe_bestand`` rufen".
Er lief ohne jeden Fehler — mit den Vorgaben des EIGENEN Geschaefts:
``red_verfahren`` prospektiv, ``VertragsPruefung`` ohne gamma1 in den
Scheiben, Stornoabzug je Vertrag, Deckungskapital kalendertaeglich. Auf der
Lieferung des zweiten Laufs bestanden 2 von 29 Vertraegen statt 29 von 29;
27 Urteile wichen ab. Die Kommandos lesen die Regeln seit ADR-024
(Nachtrag) aus der Spez — die Engine darunter hielt die stille Vorgabe
weiter bereit, fuer jeden, der sie ohne das Kommando ruft.

Invariante: Wer eine Engine der Bestandsstrecke (``qa.migrationssuite``,
``qa.aktuarieller_test``) ruft, NENNT jede Tarifregel. Kein Argument und
kein Feld eines Pruefauftrags, das eine Regel aus ``tbox.TARIFWERK_MERKMALE``
oder dem Quellverfahren traegt (oder eine solche Regel, wie
``dk_am_jahrestag`` den Stichtag des gelieferten Deckungskapitals), hat
eine Vorgabe — auch nicht die privaten Stufen, durch die ein oeffentlicher
Einstieg die Regel reicht.

Ratsche: die Menge der regeltragenden Stellen mit ``==`` (ein neuer
Einstieg mit Regel faellt auf und wird hier bewusst aufgenommen), davon
mit Vorgabe: null; die Positivkontrolle zeigt, dass der Detektor eine
Vorgabe sieht.

Knoten: klv
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path
from typing import List, Tuple

import pytest

from rechner_pipeline.ontologie.tbox import QUELLVERFAHREN_WERTE, TARIFWERK_MERKMALE

SRC = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"

#: Die Engines, deren Einstiege eine Regel tragen.
ENGINES: Tuple[str, ...] = ("qa/migrationssuite.py", "qa/aktuarieller_test.py")

#: Namen, unter denen eine Tarifregel in die Engine reicht: die Merkmale der
#: Spez und ``dk_am_jahrestag`` (die Lesart von ``quellverfahren.dk_stichtag``).
REGEL_NAMEN = frozenset(TARIFWERK_MERKMALE) | frozenset(QUELLVERFAHREN_WERTE) | {"dk_am_jahrestag"}


def regelstellen(quelltext: str) -> List[Tuple[str, str, bool]]:
    """(Ort, Name, hat Vorgabe) fuer jedes regeltragende Argument einer
    Funktion auf Modulebene und jedes regeltragende Feld einer Klasse auf
    Modulebene."""
    aus: List[Tuple[str, str, bool]] = []
    for knoten in ast.parse(quelltext).body:
        if isinstance(knoten, ast.FunctionDef):
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
                    # ``field(kw_only=True)`` ohne default ist keine Vorgabe.
                    wert = feld.value
                    vorgabe = wert is not None and not (
                        isinstance(wert, ast.Call) and ast.unparse(wert.func).endswith("field")
                        and not any(k.arg in ("default", "default_factory") for k in wert.keywords))
                    aus.append((knoten.name, feld.target.id, vorgabe))
    return aus


def _alle() -> List[Tuple[str, str, str, bool]]:
    return [(engine, ort, name, vorgabe)
            for engine in ENGINES
            for ort, name, vorgabe in regelstellen((SRC / engine).read_text(encoding="utf-8"))]


def test_ratsche_keine_regelstelle_der_engines_hat_eine_vorgabe() -> None:
    mit = [s for s in _alle() if s[3]]
    assert mit == [], (
        "Eine Engine der Bestandsstrecke traegt eine Vorgabe fuer eine Tarifregel — "
        f"wer sie ohne das Kommando ruft, rechnet still die Regel des eigenen Geschaefts: {mit}")


def test_ratsche_die_menge_der_regelstellen_ist_bekannt() -> None:
    """== statt >=: Ein neuer Einstieg mit Regel wird hier bewusst aufgenommen
    (und traegt keine Vorgabe); eine verschwundene Stelle faellt ebenso auf."""
    gezaehlt = {(e, o, n) for e, o, n, _ in _alle()}
    assert gezaehlt == {
        ("qa/migrationssuite.py", "VertragsPruefung", "scheiben_mit_gamma1"),
        ("qa/migrationssuite.py", "VertragsPruefung", "stoab_je_baustein"),
        ("qa/migrationssuite.py", "VertragsPruefung", "tku_umfang"),
        ("qa/migrationssuite.py", "VertragsPruefung", "dk_am_jahrestag"),
        ("qa/migrationssuite.py", "_pruefe_ueber_vorgangsfolge", "red_verfahren"),
        ("qa/migrationssuite.py", "pruefe_vertrag", "red_verfahren"),
        ("qa/migrationssuite.py", "pruefe_bestand", "red_verfahren"),
        ("qa/aktuarieller_test.py", "Vertragspruefung", "scheiben_mit_gamma1"),
        ("qa/aktuarieller_test.py", "Vertragspruefung", "stoab_je_baustein"),
        ("qa/aktuarieller_test.py", "Vertragspruefung", "tku_umfang"),
        ("qa/aktuarieller_test.py", "_kandidaten_rechnung", "red_verfahren"),
        ("qa/aktuarieller_test.py", "_korridor_rkw", "red_verfahren"),
        ("qa/aktuarieller_test.py", "_deckungskapital", "red_verfahren"),
        ("qa/aktuarieller_test.py", "_folge_des_auftrags", "red_verfahren"),
        ("qa/aktuarieller_test.py", "_system_werte_folge", "red_verfahren"),
        ("qa/aktuarieller_test.py", "_system_werte", "red_verfahren"),
        ("qa/aktuarieller_test.py", "pruefe_vertrag", "red_verfahren"),
        ("qa/aktuarieller_test.py", "pruefe_stichprobe", "red_verfahren"),
    }, sorted(gezaehlt)


@pytest.mark.parametrize("quelltext, erwartet", [
    ("def f(v, *, red_verfahren='prospektiv'): pass", [("f", "red_verfahren", True)]),
    ("def f(v, red_verfahren='prospektiv'): pass", [("f", "red_verfahren", True)]),
    ("def f(v, *, red_verfahren): pass", [("f", "red_verfahren", False)]),
    ("class K:\n    stoab_je_baustein: bool = False\n", [("K", "stoab_je_baustein", True)]),
    ("class K:\n    tku_umfang: str = field(default=None)\n", [("K", "tku_umfang", True)]),
    ("class K:\n    tku_umfang: str = field(kw_only=True)\n", [("K", "tku_umfang", False)]),
    ("def f(v, *, andere=1): pass", []),
])
def test_positivkontrolle_der_detektor_sieht_eine_vorgabe(quelltext, erwartet) -> None:
    assert regelstellen(quelltext) == erwartet


def test_der_pruefauftrag_ohne_regel_wird_verweigert() -> None:
    """Verhalten, nicht nur Quelltext: Ein Pruefauftrag ohne die Regeln und
    ein Einstieg ohne Verfahren werden verweigert (TypeError beim Aufruf),
    statt still die PLV-Regel zu rechnen."""
    from rechner_pipeline.qa import aktuarieller_test as at
    from rechner_pipeline.qa import migrationssuite as ms

    pflicht_ms = {f.name for f in dataclasses.fields(ms.VertragsPruefung)
                  if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING}
    assert {"scheiben_mit_gamma1", "stoab_je_baustein", "tku_umfang",
            "dk_am_jahrestag"} <= pflicht_ms
    pflicht_at = {f.name for f in dataclasses.fields(at.Vertragspruefung)
                  if f.default is dataclasses.MISSING and f.default_factory is dataclasses.MISSING}
    assert {"scheiben_mit_gamma1", "stoab_je_baustein", "tku_umfang"} <= pflicht_at
    with pytest.raises(TypeError, match="red_verfahren"):
        ms.pruefe_bestand([])
    with pytest.raises(TypeError, match="red_verfahren"):
        ms.pruefe_vertrag(None)
    with pytest.raises(TypeError, match="red_verfahren"):
        at.pruefe_vertrag(None, None)
    with pytest.raises(TypeError, match="red_verfahren"):
        at.pruefe_stichprobe([], None, None)
