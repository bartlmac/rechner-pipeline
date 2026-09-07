"""Konvention Belegidentitaet (Review T23-01): Ein Gate liest eine Datei,
deren Hash es als Beleg protokolliert, nicht getrennt davon ein zweites Mal.

Der Beleg-Hash muss aus denselben Bytes stammen, die geparst, validiert
oder gerendert wurden (``models.manifest.lies_gehasht`` /
``GeleseneDatei``). Sonst bezeugt der Beleg irgendeinen Zustand der Datei
zu irgendeinem Zeitpunkt des Laufs — nicht den geprueften. Dieser Test ist
die Ratsche gegen das Muster "hash_files(pfad) hier, pfad.read_text()
dort": Er findet je Funktion Ausdruecke, die sowohl in einen Hash-Aufruf
gehen als auch gelesen werden, und Ausdruecke, die in einer Funktion
mehrfach gelesen werden.

Reichweite, ehrlich benannt: Verglichen werden Ausdruecke innerhalb EINER
Funktion (``ast.unparse``) — Ausdrucks-, nicht Variablenidentitaet: derselbe
Text ``Path(p)`` in zwei getrennten Comprehensions zaehlt als eine Datei
(Fehlalarm moeglich, ausserhalb ``gates/`` beobachtet). Ein Pfad, der in
einer Hilfsfunktion gelesen und im Aufrufer gehasht wird, oder ein Adapter,
der die Datei ueber einen eigenen Kanal liest (``extract``), bleibt hier
unsichtbar — dafuer steht der Lese-Zaehl-Test in
``tests/test_belegidentitaet_t23.py``, der die Gates tatsaechlich fahren
laesst. Testtragend ist die Ratsche fuer ``gates/``; ueber die uebrigen
Schichten laeuft sie informativ (die Funde dort — Zeichnungsordnung,
Bestandsprofil — sind in Block 1 mit umgestellt).

Knoten: system/assurance
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path
from typing import List

import pytest

GATES = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline" / "gates"
#: Aufrufe, die eine Datei fuer einen Beleg hashen.
HASH_FUNKTIONEN = {
    "hash_files", "file_sha256", "sha256_datei", "_sha256_datei", "_sha256",
}
#: Methoden, mit denen eine Datei gelesen wird.
LESE_METHODEN = {"read_text", "read_bytes", "open"}


def _callee(call: ast.Call) -> str | None:
    f = call.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        return f.attr
    return None


#: ``open`` auf diesen Modulen ist kein ``Path.open`` (``os.open`` liefert
#: einen Deskriptor, ``io.open``/``gzip.open`` nehmen Modi anders entgegen).
KEIN_PFAD_EMPFAENGER = {"os", "io", "gzip", "zipfile", "codecs", "builtins"}


def _ist_lesender_open(call: ast.Call) -> bool:
    """``read_text``/``read_bytes`` lesen immer; ``open`` nur ohne
    Schreibmodus (``w``, ``a``, ``x``, ``+``) — ``open("xb")`` ist ein
    Schreiben und kein zweiter Lesepfad. ``os.open`` u. ae. sind keine
    Pfad-Lesungen im Sinne der Ratsche."""
    if _callee(call) != "open":
        return True
    empfaenger = call.func.value if isinstance(call.func, ast.Attribute) else None
    if isinstance(empfaenger, ast.Name) and empfaenger.id in KEIN_PFAD_EMPFAENGER:
        return False
    modus = None
    if call.args and isinstance(call.args[0], ast.Constant):
        modus = call.args[0].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            modus = kw.value.value
    if not isinstance(modus, str):
        return True
    return not any(c in modus for c in "wax+")


def _hash_ausdruecke(call: ast.Call) -> List[str]:
    """Die gehashten Pfad-Ausdruecke eines Hash-Aufrufs (Listenelemente
    einzeln, sonst das Argument selbst)."""
    aus: List[str] = []
    for arg in call.args:
        if isinstance(arg, (ast.List, ast.Tuple)):
            aus.extend(ast.unparse(e) for e in arg.elts)
        else:
            aus.append(ast.unparse(arg))
    return aus


def verstoesse(datei: Path) -> List[str]:
    baum = ast.parse(datei.read_text(encoding="utf-8"))
    befunde: List[str] = []
    for fn in ast.walk(baum):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        gehasht: set = set()
        gelesen: Counter = Counter()
        for node in ast.walk(fn):
            if not isinstance(node, ast.Call):
                continue
            name = _callee(node)
            if name in HASH_FUNKTIONEN:
                gehasht.update(_hash_ausdruecke(node))
            elif name in LESE_METHODEN and isinstance(node.func, ast.Attribute):
                if _ist_lesender_open(node):
                    gelesen[ast.unparse(node.func.value)] += 1
        for ausdruck in sorted(gehasht & set(gelesen)):
            befunde.append(
                f"{datei.name}:{fn.name}: {ausdruck!r} wird gehasht UND "
                "getrennt gelesen — Beleg und Verarbeitung aus verschiedenen "
                "Bytes (T23-01); lies_gehasht verwenden"
            )
        for ausdruck, n in sorted(gelesen.items()):
            if n >= 2:
                befunde.append(
                    f"{datei.name}:{fn.name}: {ausdruck!r} wird {n}x gelesen "
                    "— einmal lesen, Bytes wiederverwenden (T23-01)"
                )
    return befunde


@pytest.mark.parametrize(
    "datei", sorted(GATES.glob("*.py")), ids=lambda p: p.name,
)
def test_kein_gate_hasht_und_liest_dieselbe_datei_getrennt(datei: Path):
    assert verstoesse(datei) == []
