"""Ratsche: kein Leser nimmt einen einzelnen Vorgang an.

Die Klasse (Entscheid des Maintainers 2026-10-01): Bis Kern 3.16.0 baute
jeder Leser — Engine, Bewertung, Ledger-Herleitung, Fuehrungsprobe,
Migrationssuite, aktuarieller Test, Verankerung — den herabgesetzten Vertrag
aus EINER Zeile der Nebentabelle nach (``ReduzierterVertrag``,
``reduzierte_teile``), und die Nebentabelle wurde je Police auf eine Zeile
geschnitten. Seit der Vorgangsfolge (``kern.vorgangsfolge``) faltet jeder
Leser die Folge seiner Vorgaenge. Diese Ratsche haelt die Menge der Stellen,
die den Einzelvorgang-Weg noch rufen, mit ``==``:

* ``kern/beitragsreduktion.py`` selbst (die Einzelreduktion, auf die die Folge
  fuer EINEN Vorgang bitgleich abbildet) und ``kern/vorgangsfolge.py`` sind
  ausgenommen;
* ``bestand/migrationszugang.py`` behaelt 4 Aufrufe: die Umkehrung GENAU EINER
  gelieferten Absetzung (Beitragsgleichung, Kalibrierung am Ankerwert, deren
  Vorwaertsproben). Ihr Gegenstand ist ein Einzelereignis; eine Serie leitet
  ``leite_serie_ueber_folge_ab`` ueber die Folge ab.

Ein neuer Aufruf ist ein Befund: Er nimmt an, dass ein Vertrag hoechstens
einen Vorgang traegt. Dazu die zweite Bauform des Fehlers: eine Nebentabelle
der Vorgaenge, die je Police auf eine Zeile geschnitten wird
(``set_index("police_id")``, ``drop_duplicates``, ``.first()`` auf einer
Zeile, die ``reduktion`` nennt) — Soll: keine Stelle. Positivkontrollen:
beide Detektoren schlagen auf einem synthetischen Treffer an.

Knoten: klv
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"
EINZELWEG = {"ReduzierterVertrag", "reduzierte_teile", "vertrags_monatsreserve_reduziert",
             "reduziere_geschichtet", "reduziere"}
AUSGENOMMEN = {"kern/beitragsreduktion.py", "kern/vorgangsfolge.py"}
SOLL = {"bestand/migrationszugang.py": 4}
SCHNITT = re.compile(r"reduktion\w*.*(set_index\(\s*[\"']police_id[\"']\s*\)|drop_duplicates|\.first\(\))")


def _einzelweg(quelle: str) -> int:
    n = 0
    for k in ast.walk(ast.parse(quelle)):
        if not isinstance(k, ast.Call):
            continue
        f = k.func
        name = (f.id if isinstance(f, ast.Name)
                else f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)
                and f.value.id in EINZELWEG
                else f.attr if isinstance(f, ast.Attribute) else None)
        n += name in EINZELWEG
    return n


def test_positivkontrolle_der_detektoren():
    probe = ("rv = ReduzierterVertrag.nach(k, 1, 0.5)\nt = reduzierte_teile(k, [], 1, 0.5, 'p')\n"
             "x = br.reduziere(k, 1, 0.5)\ny = andere(1)\n")
    assert _einzelweg(probe) == 3
    assert SCHNITT.search('je = reduktionen.set_index("police_id")')
    assert SCHNITT.search("reduktionen = reduktionen.drop_duplicates(['police_id'])")
    assert not SCHNITT.search('stamm.set_index("police_id")')


def test_kein_leser_nimmt_einen_einzelnen_vorgang_an():
    gemessen = {}
    schnitte = []
    for p in sorted(SRC.rglob("*.py")):
        rel = str(p.relative_to(SRC))
        text = p.read_text(encoding="utf-8")
        for nr, zeile in enumerate(text.splitlines(), 1):
            if SCHNITT.search(zeile.split("#")[0]):
                schnitte.append(f"{rel}:{nr}")
        if rel in AUSGENOMMEN:
            continue
        n = _einzelweg(text)
        if n:
            gemessen[rel] = n
    assert gemessen == SOLL
    assert schnitte == []
