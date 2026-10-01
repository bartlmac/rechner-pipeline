"""Eine Auskunft der Quelle ist eine REGISTRIERTE Datei — nie ein Kommandozeilenparameter.

Entscheid des Maintainers (2026-09-30): Der fortgefuehrte Beitragsanteil
einer Alt-Herabsetzung ist eine Auskunft der abgebenden Gesellschaft. Sie
gehoert wie jede Lieferung in den Fall (Register, SHA-256, Provenienz) und
ist damit fuer die Zeichnung bindbar. Ein ``--red-anteil POLNR=ANTEIL`` am
Aufruf war es nicht: Die menschlichen Gates hashen den Eingang, nicht den
Aufruf — der Beleg nannte die Werte als getippte Liste, ohne Herkunft.

Die Klasse, nicht der Einzelfall: Fuenf Kommandos verarbeiten
Herabsetzungsanteile (Uebernahme, Verankerung, aktuarieller Test,
Migrationscontrolling, Fuehrungsprobe). Vier kannten beides, eines nur den
Einzelwert — die Luecke war nur im Zusammenspiel zu sehen. Drei Instrumente
halten die Klasse zu:

* Ratsche (statisch, an der SENKE statt am Namen): Die Menge ist die aller
  Aufrufer von ``anfangszustaende_je_police`` / ``_serienzustand`` unter
  ``gates/`` (aus dem Code hergeleitet, mit ``==`` gegen die erwarteten
  fuenf); jeder nennt ``--red-anteile-datei``. Die Anteile an diesen
  Aufrufen stammen ausschliesslich aus ``lies_auskuenfte`` (Herkunft bis
  durch Parameter verfolgt), und kein Argument unter ``gates/`` liefert je
  Police einen Anteil (Detektor auf dest und Wiederholbarkeit, nicht auf das
  Literal ``--red-anteil``). Jeder Detektor hat eine Positivkontrolle.
* Zaehltest je Kommando (dynamisch): mit registrierter Datei gruen UND die
  Datei erreicht die Anfangszustaende UND der Beleg nennt sie mit ihrem
  Hash; ohne Registrierung (die Datei liegt nur im Dateisystem)
  verweigert das Kommando mit dem Ausweg, bevor es etwas schreibt.
* Mutationsproben je Kommando (siehe die jeweiligen Docstrings).

Knoten: klv/tg2015
"""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Dict, List

import pytest

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates import (
    aktuartest_lauf,
    bestand_uebernehmen,
    fuehrungsprobe,
    migrationssuite_lauf,
    verankerung_belegen,
)
from rechner_pipeline.gates._common import Eingangsbindung
from rechner_pipeline.gates.aktuartest_lauf import _schichten
from rechner_pipeline.gates.migrationssuite_lauf import lies_auskuenfte
from tests.test_baldrian2_e2e import (  # noqa: F401  (Fixture + Konstanten)
    ABNAHMEN,
    ABZUG_1,
    ABZUG_2,
    ANKER,
    AUSKUNFT,
    AUSKUNFT_BEZUG,
    ERHOEHUNGSSATZ,
    GENERATION,
    KANDIDATEN,
    METADATEN,
    PROTOKOLL,
    RED_ANTEILE,
    RED_DATEN,
    RED_VERFAHREN,
    REPO_ROOT,
    STICHPROBE,
    STICHTAG_1,
    STICHTAG_2,
    TARIF_GENERATION,
    gefahrener_fall,
)

GATES = REPO_ROOT / "src" / "rechner_pipeline" / "gates"

#: Die Kommandos, die Herabsetzungsanteile verarbeiten — die Menge, die
#: die Ratsche aus dem Code herleitet und hiermit gleichsetzt. Ein sechstes
#: Modul, das ``red_anteile`` verarbeitet, bricht diesen Test: Es muss
#: ``--red-anteile-datei`` kennen und hier eingetragen werden.
ANTEIL_KOMMANDOS = (
    "aktuartest_lauf",
    "bestand_uebernehmen",
    "fuehrungsprobe",
    "migrationssuite_lauf",
    "verankerung_belegen",
)


#: Die Kommandos, die einen Schichtbeleg (``--schicht``) konsumieren — sie
#: halten ihn gegen ihre eigene Auskunft (Welt-Gleichheit).
SCHICHT_KOMMANDOS = ("aktuartest_lauf", "migrationssuite_lauf",
                     "fuehrungsprobe")


# --------------------------------------------------------------------------- #
# Ratsche (statisch)
# --------------------------------------------------------------------------- #


def _option_strings(quelle: str) -> List[str]:
    """Alle ``--...``-Literale, die ein ``add_argument``-Aufruf nennt."""
    optionen: List[str] = []
    for knoten in ast.walk(ast.parse(quelle)):
        if (isinstance(knoten, ast.Call)
                and isinstance(knoten.func, ast.Attribute)
                and knoten.func.attr == "add_argument"):
            optionen += [
                a.value for a in knoten.args
                if isinstance(a, ast.Constant) and isinstance(a.value, str)
                and a.value.startswith("--")]
    return optionen


def _einzelwert_stellen(quelle: str) -> List[int]:
    """Zeilen, in denen das Literal ``"--red-anteil"`` (der Einzelwert)
    vorkommt — als Argument UND als Text eines Aufrufbaus (``_aufruf``).
    ``--red-anteil-kandidat`` ist ein anderes Literal und bleibt."""
    return sorted(
        k.lineno for k in ast.walk(ast.parse(quelle))
        if isinstance(k, ast.Constant) and k.value == "--red-anteil")


#: Die Senken: die Funktionen, die aus den Herabsetzungsanteilen den
#: Anfangszustand einer Police rechnen. Wer sie ruft, verarbeitet Anteile —
#: gleich, wie er seine Variablen nennt (Block F, Nachbesserung: die
#: Ratsche haengt an der Senke, nicht am Namen ``red_anteile`` oder am
#: Literal ``--red-anteil``).
SENKEN = ("anfangszustaende_je_police", "_serienzustand")
#: Die Schluesselwoerter, ueber die Anteile in eine Senke gehen.
ANTEIL_SCHLUESSEL = ("red_anteile", "red_anteile_je_datum")
#: Lesende Zugriffe auf ein Mapping; jeder andere Zugriff auf eine
#: Anteils-Variable (update, setdefault, Zuweisung je Schluessel) ist eine
#: Quelle neben der Auskunft.
_LESEND = frozenset({"get", "items", "keys", "values", "copy"})


def _quellen() -> Dict[str, str]:
    return {p.stem: p.read_text(encoding="utf-8")
            for p in sorted(GATES.glob("*.py"))}


def _aufgerufen_als(aufruf: ast.Call):
    if isinstance(aufruf.func, ast.Name):
        return aufruf.func.id
    if isinstance(aufruf.func, ast.Attribute):
        return aufruf.func.attr
    return None


class _Umgebung:
    """Alle Funktionen und Aufrufe der Module, je Aufruf mit der
    umschliessenden Funktion."""

    def __init__(self, quellen: Dict[str, str]) -> None:
        self.funktionen: Dict[str, list] = {}
        self.aufrufe: list = []
        for modul, text in quellen.items():
            self._lauf(modul, ast.parse(text), None)

    def _lauf(self, modul, knoten, funktion) -> None:
        for kind in ast.iter_child_nodes(knoten):
            innen = funktion
            if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.funktionen.setdefault(kind.name, []).append((modul, kind))
                innen = kind
            if isinstance(kind, ast.Call):
                self.aufrufe.append((modul, funktion, kind))
            self._lauf(modul, kind, innen)

    def senken_aufrufe(self) -> list:
        return [(m, f, a) for m, f, a in self.aufrufe
                if _aufgerufen_als(a) in SENKEN]


def _ist_auskunftsobjekt(funktion, name: str) -> bool:
    """``name`` wird in der Funktion ausschliesslich aus einem Aufruf von
    ``lies_auskuenfte`` gebunden (und mindestens einmal)."""
    if funktion is None:
        return False
    werte = []
    for k in ast.walk(funktion):
        if isinstance(k, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == name for t in k.targets):
            werte.append(k.value)
        elif (isinstance(k, ast.AnnAssign) and isinstance(k.target, ast.Name)
              and k.target.id == name and k.value is not None):
            werte.append(k.value)
    return bool(werte) and all(
        isinstance(w, ast.Call) and _aufgerufen_als(w) == "lies_auskuenfte"
        for w in werte)


def _ausdruck_probleme(u: _Umgebung, ausdruck, modul, funktion,
                       besucht: set) -> List[str]:
    """Stammt ``ausdruck`` ausschliesslich aus der Auskunft (oder ist leer)?
    Erlaubt sind: ``{}``, eine Variable mit erlaubter Herkunft, ``a or b``,
    ``dict(x)``, ``<Auskunft>.anteile``/``.je_datum`` und ein Dict-
    Comprehension ueber ``<erlaubt>.items()`` ohne Fremdnamen."""
    def rekursiv(x):
        return _ausdruck_probleme(u, x, modul, funktion, besucht)

    if isinstance(ausdruck, ast.Dict) and not ausdruck.keys:
        return []
    if isinstance(ausdruck, ast.Name):
        return _name_probleme(u, ausdruck.id, modul, funktion, besucht)
    if isinstance(ausdruck, ast.BoolOp) and isinstance(ausdruck.op, ast.Or):
        return [p for w in ausdruck.values for p in rekursiv(w)]
    if (isinstance(ausdruck, ast.Call) and isinstance(ausdruck.func, ast.Name)
            and ausdruck.func.id == "dict" and len(ausdruck.args) == 1
            and not ausdruck.keywords
            and not isinstance(ausdruck.args[0], ast.Starred)):
        return rekursiv(ausdruck.args[0])
    if (isinstance(ausdruck, ast.Attribute)
            and ausdruck.attr in ("anteile", "je_datum")
            and isinstance(ausdruck.value, ast.Name)
            and _ist_auskunftsobjekt(funktion, ausdruck.value.id)):
        return []
    if isinstance(ausdruck, ast.DictComp) and len(ausdruck.generators) == 1:
        gen = ausdruck.generators[0]
        ziele = {n.id for n in ast.walk(gen.target) if isinstance(n, ast.Name)}
        if (not gen.ifs and isinstance(gen.iter, ast.Call)
                and isinstance(gen.iter.func, ast.Attribute)
                and gen.iter.func.attr == "items" and not gen.iter.args):
            frei = {n.id for teil in (ausdruck.key, ausdruck.value)
                    for n in ast.walk(teil) if isinstance(n, ast.Name)}
            if not frei - ziele - {"dict"}:
                return rekursiv(gen.iter.func.value)
    return [f"{ast.unparse(ausdruck)!r} (Zeile {ausdruck.lineno}): Herkunft "
            "nicht aus lies_auskuenfte herleitbar"]


def _name_probleme(u: _Umgebung, name: str, modul, funktion,
                   besucht: set) -> List[str]:
    if funktion is None:
        return [f"{name}: Anteile aus dem Modulbereich"]
    marke = (modul, funktion.lineno, name)
    if marke in besucht:  # Kreis (``x = x or {}``): die Erstpruefung traegt
        return []
    besucht.add(marke)
    probleme: List[str] = []
    werte = []
    for k in ast.walk(funktion):
        if isinstance(k, ast.Assign):
            for t in k.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    werte.append(k.value)
                elif isinstance(t, (ast.Tuple, ast.List)) and any(
                        isinstance(e, ast.Name) and e.id == name
                        for e in ast.walk(t)):
                    probleme.append(f"{name} (Zeile {k.lineno}): Entpacken")
        elif (isinstance(k, ast.AnnAssign) and isinstance(k.target, ast.Name)
              and k.target.id == name and k.value is not None):
            werte.append(k.value)
        elif isinstance(k, ast.AugAssign) and any(
                isinstance(e, ast.Name) and e.id == name
                for e in ast.walk(k.target)):
            probleme.append(f"{name} (Zeile {k.lineno}): erweitert")
        elif isinstance(k, (ast.For, ast.AsyncFor)) and any(
                isinstance(e, ast.Name) and e.id == name
                for e in ast.walk(k.target)):
            probleme.append(f"{name} (Zeile {k.lineno}): Schleifenvariable")
        elif (isinstance(k, ast.NamedExpr) and isinstance(k.target, ast.Name)
              and k.target.id == name):
            probleme.append(f"{name} (Zeile {k.lineno}): Walrus")
        elif (isinstance(k, ast.Attribute) and isinstance(k.value, ast.Name)
              and k.value.id == name and k.attr not in _LESEND):
            probleme.append(f"{name}.{k.attr} (Zeile {k.lineno}): "
                            "veraendernder Zugriff")
        elif (isinstance(k, ast.Subscript) and isinstance(k.value, ast.Name)
              and k.value.id == name and not isinstance(k.ctx, ast.Load)):
            probleme.append(f"{name}[...] (Zeile {k.lineno}): je Schluessel "
                            "gesetzt")
    a = funktion.args
    positional = [x.arg for x in a.posonlyargs + a.args]
    ist_parameter = name in positional + [x.arg for x in a.kwonlyargs]
    if ist_parameter:
        aufrufer = [(m, f, c) for m, f, c in u.aufrufe
                    if _aufgerufen_als(c) == funktion.name]
        if not aufrufer:
            probleme.append(f"{name}: Parameter von {funktion.name} ohne "
                            "Aufrufer — Herkunft nicht pruefbar")
        for m, f, c in aufrufer:
            if any(isinstance(x, ast.Starred) for x in c.args) or any(
                    k.arg is None for k in c.keywords):
                probleme.append(f"{funktion.name} (Zeile {c.lineno}): "
                                "*args/**kwargs an der Weitergabe")
                continue
            ausdruck = next((k.value for k in c.keywords if k.arg == name),
                            None)
            if ausdruck is None and name in positional and (
                    positional.index(name) < len(c.args)):
                ausdruck = c.args[positional.index(name)]
            if ausdruck is not None:  # fehlt er, gilt der Vorgabewert
                probleme += _ausdruck_probleme(u, ausdruck, m, f, besucht)
    elif not werte:
        probleme.append(f"{name}: in {funktion.name} nirgends gebunden")
    for wert in werte:
        probleme += _ausdruck_probleme(u, wert, modul, funktion, besucht)
    return probleme


def _herkunft_probleme(quellen: Dict[str, str]):
    """(Probleme, Zahl der geprueften Senken-Schluesselwoerter): Jeder
    Anteil, der in eine Senke geht, stammt aus ``lies_auskuenfte`` oder ist
    leer — sonst ist er eine zweite Quelle neben der registrierten Datei."""
    u = _Umgebung(quellen)
    probleme: List[str] = []
    geprueft = 0
    for modul, funktion, aufruf in u.senken_aufrufe():
        ort = f"{modul}:{aufruf.lineno}"
        if any(isinstance(x, ast.Starred) for x in aufruf.args) or any(
                k.arg is None for k in aufruf.keywords):
            probleme.append(f"{ort}: *args/**kwargs an einer Senke")
        for k in aufruf.keywords:
            if k.arg in ANTEIL_SCHLUESSEL:
                geprueft += 1
                probleme += [f"{ort}: {p}" for p in _ausdruck_probleme(
                    u, k.value, modul, funktion, set())]
    return probleme, geprueft


def _argumente(quelle: str) -> List[dict]:
    """Jedes ``add_argument`` eines Moduls: Option, dest, Wiederholbarkeit,
    Typ."""
    gefunden = []
    for k in ast.walk(ast.parse(quelle)):
        if not (isinstance(k, ast.Call) and isinstance(k.func, ast.Attribute)
                and k.func.attr == "add_argument"):
            continue
        optionen = [a.value for a in k.args
                    if isinstance(a, ast.Constant)
                    and isinstance(a.value, str) and a.value.startswith("--")]
        kw = {x.arg: x.value for x in k.keywords}
        option = optionen[0] if optionen else ""
        dest = (kw["dest"].value if isinstance(kw.get("dest"), ast.Constant)
                else option.lstrip("-").replace("-", "_"))
        aktion = (kw["action"].value
                  if isinstance(kw.get("action"), ast.Constant) else None)
        gefunden.append({
            "option": option, "dest": dest,
            "wiederholbar": aktion in ("append", "extend") or "nargs" in kw,
            "typ": ast.unparse(kw["type"]) if "type" in kw else None})
    return gefunden


#: Die einzigen Argumente unter ``gates/``, die ``anteil`` im Namen oder
#: dest tragen: die Datei (ein Name, keine Werte) und die Kandidatenmenge
#: (Zahlen OHNE Police — sie gilt fuer alle Vertraege).
ERLAUBTE_ANTEIL_ARGUMENTE = {
    ("--red-anteile-datei", "red_anteile_datei", None),
    ("--red-anteil-kandidat", "red_anteil_kandidaten", "float"),
}
#: Wiederholbare Argumente OHNE Zahlentyp (ein ``POLNR=WERT`` liesse sich
#: darin verstecken), exakt: Groessen fuer den Plausibilitaets-Beleg und
#: Schluesseldateien — beides je Lauf, nie je Police.
ERLAUBTE_WIEDERHOLBARE_TEXTE = {
    ("aktuartest_lauf", "--plausibilitaet-groesse"),
    ("gate_entscheid", "--freigabe-schluessel"),
    # <rolle>=<datei> je simulierter Rolle (ADR-026): In den Auftrag geht nur
    # der SHA-256 der Mandatsdatei je Rollenkennung — kein Wert je Police.
    ("fall_belegen", "--mandat"),
    # Schluesseldateien des Vorstands (Pruefrunde G, G09): nach einem
    # Schluesselwechsel der alte UND der neue — je Glied, nie je Police.
    ("stand_belegen", "--vorstand-schluessel"),
}


def _argument_verstoesse(quellen: Dict[str, str]) -> List[str]:
    verstoesse = []
    for modul, text in quellen.items():
        for a in _argumente(text):
            if ("anteil" in a["option"].lower() or "anteil" in a["dest"].lower()):
                if (a["option"], a["dest"], a["typ"]) not in ERLAUBTE_ANTEIL_ARGUMENTE:
                    verstoesse.append(f"{modul}: {a['option']} (dest {a['dest']}) "
                                      "nennt einen Anteil und ist nicht erlaubt")
            if (a["wiederholbar"] and a["typ"] is None
                    and (modul, a["option"]) not in ERLAUBTE_WIEDERHOLBARE_TEXTE):
                verstoesse.append(f"{modul}: {a['option']} ist ein "
                                  "wiederholbarer Text — darin liesse sich ein "
                                  "Anteil je Police verstecken")
    return verstoesse


_GUT = """
def main(args):
    red_anteile = {}
    red_anteile_je_datum = {}
    if args.datei:
        auskuenfte = lies_auskuenfte(fall, args.datei, bindung, vg)
        red_anteile = dict(auskuenfte.anteile)
        red_anteile_je_datum = {
            p: dict(d) for p, d in auskuenfte.je_datum.items()}
    return anfangszustaende_je_police(
        spez, red_anteile=red_anteile, red_anteile_je_datum=red_anteile_je_datum)
"""

_GUT_UEBER_PARAMETER = """
def pruefe(red_anteile, red_anteile_je_datum):
    red_anteile = red_anteile or {}
    return anfangszustaende_je_police(
        spez, red_anteile=red_anteile, red_anteile_je_datum=red_anteile_je_datum)

def main(args):
    a = lies_auskuenfte(fall, args.datei, bindung, vg)
    return pruefe(red_anteile=dict(a.anteile),
                  red_anteile_je_datum={p: dict(d) for p, d in a.je_datum.items()})
"""

#: Schlechte Formen, je eine Art, eine zweite Quelle neben die Auskunft zu
#: stellen. Jede muss der Detektor melden.
_SCHLECHT = {
    "je_schluessel_gesetzt": """
def main(args):
    red_anteile = {}
    for e in args.einzeln:
        p, _, w = e.partition("=")
        red_anteile[p] = float(w)
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)
""",
    "direkt_aus_dem_argument": """
def main(args):
    return anfangszustaende_je_police(
        spez, red_anteile=_parse(args.anteil_je_police))
""",
    "neben_der_auskunft_ergaenzt": """
def main(args):
    a = lies_auskuenfte(fall, args.datei, bindung, vg)
    red_anteile = dict(a.anteile)
    red_anteile.update(_parse(args.einzeln))
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)
""",
    "dict_mit_zusatz": """
def main(args):
    a = lies_auskuenfte(fall, args.datei, bindung, vg)
    return anfangszustaende_je_police(
        spez, red_anteile=dict(a.anteile, **_parse(args.einzeln)))
""",
    "erweitert": """
def main(args):
    a = lies_auskuenfte(fall, args.datei, bindung, vg)
    red_anteile = dict(a.anteile)
    red_anteile |= _parse(args.einzeln)
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)
""",
    "literal_mit_werten": """
def main(args):
    red_anteile = {"7000396": 0.6}
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)
""",
    "auskunftsobjekt_nicht_aus_lies_auskuenfte": """
def main(args):
    a = Auskuenfte(anteile=_parse(args.einzeln), je_datum={}, beleg={})
    return anfangszustaende_je_police(spez, red_anteile=dict(a.anteile))
""",
    "je_datum_aus_dem_argument": """
def main(args):
    return _serienzustand(p, f, m, red_anteile={},
                          red_anteile_je_datum=_parse(args.einzeln))
""",
    "ueber_parameter_weitergereicht": """
def pruefe(red_anteile):
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)

def main(args):
    return pruefe(red_anteile=_parse(args.einzeln))
""",
    "ueber_parameter_positional": """
def pruefe(red_anteile):
    return anfangszustaende_je_police(spez, red_anteile=red_anteile)

def main(args):
    return pruefe(_parse(args.einzeln))
""",
    "kwargs_an_der_senke": """
def main(args):
    return anfangszustaende_je_police(spez, **_parse(args))
""",
}


def test_ratsche_der_detektor_sieht_den_einzelwert_und_die_verarbeitung():
    """Positivkontrolle: Eine Ratsche mit null Treffern ist erst dann etwas
    wert, wenn feststeht, dass der Detektor einen Treffer meldete, gaebe
    es einen — hier fuer jede Art, eine zweite Quelle neben die Auskunft
    zu stellen (Block F, Nachbesserung: die Ratsche haengt an der Senke,
    nicht am Namen)."""
    argument = "p.add_argument('--red-anteil', dest='x')\n"
    aufrufbau = "a = []\na += ['--red-anteil', str(e)]\n"
    kandidat = "p.add_argument('--red-anteil-kandidat')\n"
    assert _einzelwert_stellen(argument) == [1]
    assert _einzelwert_stellen(aufrufbau) == [2]
    assert _einzelwert_stellen(kandidat) == []
    assert _option_strings(argument) == ["--red-anteil"]
    assert _option_strings("p.add_argument('--red-anteile-datei')") == [
        "--red-anteile-datei"]

    assert _herkunft_probleme({"m": _GUT}) == ([], 2)
    assert _herkunft_probleme({"m": _GUT_UEBER_PARAMETER}) == ([], 2)
    for art, quelle in _SCHLECHT.items():
        probleme, _ = _herkunft_probleme({"m": quelle})
        assert probleme, f"der Detektor uebersieht: {art}"

    mp = ("p.add_argument('--anteil-je-police', dest='einzeln', "
          "action='append', default=[])\n")
    text = ("p.add_argument('--fraktion', dest='x', action='append')\n")
    zahl = ("p.add_argument('--red-anteil-kandidat', "
            "dest='red_anteil_kandidaten', action='append', type=float)\n")
    datei = "p.add_argument('--red-anteile-datei', dest='red_anteile_datei')\n"
    assert len(_argument_verstoesse({"m": mp})) == 2
    assert len(_argument_verstoesse({"m": text})) == 1
    assert _argument_verstoesse({"m": zahl + datei}) == []
    # Ein ``--red-anteil-kandidat`` als Text waere ein ``POLNR=WERT``-Versteck.
    assert _argument_verstoesse({"m": zahl.replace(", type=float", "")})


def test_ratsche_kein_kommando_kennt_den_einzelwert():
    """Mutationsprobe: ``--red-anteil`` in einem Parser (oder in
    ``fuehrungsprobe._aufruf``) wieder eintragen -> rot."""
    treffer = {
        f"{p.name}:{z}": None
        for p in sorted(GATES.glob("*.py"))
        for z in _einzelwert_stellen(p.read_text(encoding="utf-8"))}
    assert not treffer, (
        f"{sorted(treffer)}: ein Einzelwert-Argument je Police ist fuer die "
        "Zeichnung nicht bindbar (Entscheid 2026-09-30) — die Auskunft als "
        "Datei registrieren (python -m rechner_pipeline.fall registrieren), "
        "dann --red-anteile-datei")


def test_ratsche_jedes_kommando_das_eine_senke_ruft_kennt_die_datei():
    """Die Menge kommt aus dem Code: alle Module unter ``gates/``, die
    ``anfangszustaende_je_police`` oder ``_serienzustand`` rufen (die Senken,
    an denen die Anteile wirken) — gleich, wie sie ihre Variablen nennen. Der
    Vergleich ist ``==``: Ein neues Modul faellt hier auf, statt die Regel
    still zu umgehen; ein Kommando, das den Schalter verliert, auch.
    Mutationsprobe: ``--red-anteile-datei`` aus einem Parser entfernen ->
    rot; ein sechstes Modul mit einem Senken-Aufruf -> rot."""
    hergeleitet = sorted({m for m, _, _ in _Umgebung(_quellen()).senken_aufrufe()})
    assert hergeleitet == sorted(ANTEIL_KOMMANDOS), hergeleitet
    ohne = [n for n in hergeleitet
            if "--red-anteile-datei" not in _option_strings(
                (GATES / f"{n}.py").read_text(encoding="utf-8"))]
    assert not ohne, (
        f"{ohne}: verarbeitet Herabsetzungsanteile, kennt aber "
        "--red-anteile-datei nicht")


def test_ratsche_jeder_anteil_an_einer_senke_stammt_aus_der_auskunft():
    """Die Invariante an der Senke: ``red_anteile`` und
    ``red_anteile_je_datum`` kommen an JEDEM Senken-Aufruf ausschliesslich
    aus ``lies_auskuenfte`` (oder sind leer) — auch ueber Parameter
    weitergereicht (``fuehrungsprobe.pruefe_fuehrung``). Die Zahl der
    geprueften Stellen ist exakt: sechs Senken-Aufrufe (je einer in den
    fuenf Kommandos, dazu die Weitergabe an die Serie in
    ``migrationssuite_lauf``), an jedem BEIDE Schluesselwoerter — ein Aufruf,
    der ``red_anteile_je_datum`` nicht uebergibt, faellt ebenso auf. Nach
    jedem neuen Aufruf muss die Zahl hier bewusst nachgezogen werden. Mutationsprobe: in
    einem Kommando ``red_anteile[...] = ...`` oder ``.update(...)`` neben
    die Auskunft setzen -> rot."""
    probleme, geprueft = _herkunft_probleme(_quellen())
    assert not probleme, probleme
    assert len(_Umgebung(_quellen()).senken_aufrufe()) == 6
    assert geprueft == 12, geprueft


def test_ratsche_kein_argument_liefert_je_police_einen_anteil():
    """Der Detektor haengt an dest und Wiederholbarkeit, nicht am Literal
    ``--red-anteil``: ein umbenanntes ``--anteil-je-police`` (dest
    ``einzeln``, ``action=append``) faellt auf, auch ohne jede Verarbeitung
    (Mutation Mp des Pruefers). Erlaubt sind exakt die Datei und die
    Kandidatenmenge als Zahlen. Mutationsprobe: in einem Parser
    ``p.add_argument('--anteil-je-police', dest='einzeln',
    action='append')`` eintragen -> rot."""
    assert not _argument_verstoesse(_quellen()), _argument_verstoesse(_quellen())
    alle = {(m, a["option"], a["dest"], a["typ"])
            for m, t in _quellen().items() for a in _argumente(t)
            if "anteil" in a["option"].lower()}
    assert {(o, d, t) for _, o, d, t in alle} == ERLAUBTE_ANTEIL_ARGUMENTE
    assert sorted(m for m, o, _, _ in alle if o == "--red-anteile-datei") == sorted(
        ANTEIL_KOMMANDOS)
    assert sorted(m for m, o, _, _ in alle if o == "--red-anteil-kandidat") == sorted(
        ANTEIL_KOMMANDOS)


def test_ratsche_jeder_aufrufer_von_schichten_nennt_die_auskunft_des_laufs():
    """Die Welt-Gleichheit gilt nur, wo der Aufrufer die Auskunft seines
    Laufs uebergibt: Jeder Aufruf von ``_schichten`` unter ``gates/`` setzt
    ``auskunft=`` ausdruecklich; die Menge der Aufrufer ist exakt die der
    drei Kommandos mit ``--schicht``. Ein vierter Aufrufer faellt auf,
    statt mit dem Vorgabewert ``None`` still zu verweigern (oder, bei einem
    Beleg ohne Auskunft, zu passieren). Mutationsprobe: ``auskunft=`` aus
    einem Aufruf entfernen -> rot."""
    aufrufe = [(m, a) for m, _, a in _Umgebung(_quellen()).aufrufe
               if _aufgerufen_als(a) == "_schichten"]
    assert sorted({m for m, _ in aufrufe}) == sorted(SCHICHT_KOMMANDOS)
    assert len(aufrufe) == 3
    for modul, aufruf in aufrufe:
        assert any(k.arg == "auskunft" for k in aufruf.keywords), (
            f"{modul}:{aufruf.lineno}: _schichten ohne auskunft=")


# --------------------------------------------------------------------------- #
# Lesart der Auskunft (Einheit): lies_auskuenfte
# --------------------------------------------------------------------------- #


#: Die Vorgeschichte der Einheitstests: P1 zwei Herabsetzungen, P2 eine, P3
#: nur eine Erhoehung (kein RED-Ereignis).
_VORGESCHICHTE = [
    {"POLNR": "P1", "GEVO": "RED", "DATUM": "01.01.2019"},
    {"POLNR": "P1", "GEVO": "RED", "DATUM": "01.01.2021"},
    {"POLNR": "P2", "GEVO": "RED", "DATUM": "01.06.2020"},
    {"POLNR": "P3", "GEVO": "ERH", "DATUM": "01.01.2019"},
]


def _fall(tmp_path: Path, inhalt: str, name: str = "auskunft.csv") -> Path:
    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    quelle = tmp_path / "quelle" / name
    quelle.parent.mkdir()
    quelle.write_text(inhalt, encoding="utf-8")
    registrieren(fall, quelle)
    return fall


def test_die_auskunft_traegt_anteile_je_datum_und_den_bezug(tmp_path):
    fall = _fall(tmp_path, (
        "POLNR;GEVO;DATUM;ANTEIL;BEZUG\n"
        "P1;RED;01.01.2019;0.60;Auskunft 2/4\n"
        "P1;RED;01.01.2021;0.50;Schreiben vom 3.3.\n"
        "P2;RED;;0.75;\n"
        "P3;ERH;01.01.2019;;\n"))
    bindung = Eingangsbindung(fall)
    a = lies_auskuenfte(fall, "auskunft.csv", bindung, _VORGESCHICHTE)
    assert a.anteile == {"P1": 0.50, "P2": 0.75}
    assert a.je_datum == {"P1": {"01.01.2019": 0.60, "01.01.2021": 0.50}}
    roh = (fall / "eingang" / "auskunft.csv").read_bytes()
    assert a.beleg == {
        "name": "auskunft.csv",
        "sha256": hashlib.sha256(roh).hexdigest(),
        "bezug": {"P1": ["Auskunft 2/4", "Schreiben vom 3.3."]},
    }
    # Gebunden: derselbe Hash steht in den Eingaben des Laufs.
    assert bindung.als_beleg() == {"eingang/auskunft.csv": a.beleg["sha256"]}


def test_eine_auskunft_ohne_bezug_spalte_bleibt_lesbar(tmp_path):
    """Rueckwaertskompatibel: BEZUG ist optional."""
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;0.6\n")
    a = lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), _VORGESCHICHTE)
    assert a.anteile == {"P1": 0.6}
    assert a.beleg["bezug"] == {}


@pytest.mark.parametrize("inhalt, muster", [
    ("POLNR;GEVO;DATUM\nP1;RED;01.01.2019\n", "ANTEIL"),
    ("GEVO;DATUM;ANTEIL\nRED;01.01.2019;0.6\n", "POLNR"),
    ("POLNR;DATUM;ANTEIL\nP1;01.01.2019;0.6\n", "GEVO"),
    ("POLNR;GEVO;DATUM;ANTEIL\nP1;ERH;01.01.2019;0.6\n", "keine RED-Zeile"),
    ("POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;sechzig\n", "keine Zahl"),
    ("POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;0.6\nP1;RED;01.01.2019;0.5\n",
     "widersprechen"),
])
def test_eine_auskunft_die_nichts_tragen_kann_wird_verweigert(
        tmp_path, inhalt, muster):
    """Ohne die Spalte waeren alle Zeilen still verworfen worden: eine
    leere Auskunft sieht dann aus wie eine gelesene. Mutationsprobe: die
    Kopfpruefung entfernen -> rot."""
    fall = _fall(tmp_path, inhalt)
    with pytest.raises(SystemExit, match=muster):
        lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), _VORGESCHICHTE)


@pytest.mark.parametrize("wert", [
    "nan", "NaN", "inf", "-inf", "Infinity", "0", "0.0", "1", "1.0", "-0.2",
    "1.5", "100"])
def test_ein_anteil_ausserhalb_von_null_bis_eins_wird_benannt_verweigert(
        tmp_path, wert):
    """Block F, Nachbesserung: Ein Anteil ist der fortgefuehrte Bruchteil
    des Beitrags — echt zwischen 0 und 1. ``nan`` und ``inf`` liessen
    ``float()`` durch und wanderten in den Anfangszustand; 0 waere eine
    Kuendigung, 1 keine Herabsetzung; ``60`` ist ein Prozentwert. Die
    Meldung nennt Police, Datum und Wert und den Ausweg. Mutationsprobe: die
    Pruefung entfernen -> rot; die Grenze auf ``<= 0``/``>= 1`` lockern
    (0 bzw. 1 geht durch) -> rot."""
    fall = _fall(tmp_path, f"POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;{wert}\n")
    with pytest.raises(SystemExit) as exc:
        lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), _VORGESCHICHTE)
    text = str(exc.value)
    assert "P1" in text and "01.01.2019" in text and repr(wert) in text, text
    assert "zwischen 0 und 1" in text and "berichtigen" in text, text


@pytest.mark.parametrize("wert", ["0.000001", "1e-9", "0.5", "0.999999"])
def test_ein_anteil_knapp_innerhalb_der_grenzen_wird_gelesen(tmp_path, wert):
    """Die Gegenseite der Grenze: knapp darunter und knapp darueber bleibt
    gueltig — sonst waere eine zu enge Pruefung nicht von der richtigen zu
    unterscheiden (Mutation in die andere Richtung: ``< 0.5`` -> rot)."""
    fall = _fall(tmp_path, f"POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;{wert}\n")
    a = lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), _VORGESCHICHTE)
    assert a.anteile == {"P1": float(wert)}


@pytest.mark.parametrize("zeile, muster", [
    ("P9;RED;01.01.2019;0.6", "P9"),
    ("P3;RED;01.01.2019;0.6", "P3"),
    ("P3;RED;;0.6", "P3"),
    ("P1;RED;01.01.2020;0.6", "01.01.2020"),
    ("P1;RED;2019-01-01;0.6", "2019-01-01"),
    (";RED;01.01.2019;0.6", "POLNR"),
    ("  ;RED;;0.6", "POLNR"),
], ids=["unbekannte_police", "police_nur_mit_erh", "undatiert_ohne_red",
        "datum_ohne_ereignis", "anderes_datumsformat", "leere_polnr",
        "polnr_nur_leerzeichen"])
def test_eine_zeile_ohne_ereignis_der_vorgeschichte_wird_verweigert(
        tmp_path, zeile, muster):
    """Block F, Nachbesserung (Repros P1/P6): Police UND Datum muessen einem
    RED-Ereignis der Vorgeschichte entsprechen, das Datum als gleicher Text
    (``_serienzustand`` schlaegt je Datum nach Text nach — ein ISO-Datum
    bliebe dort ohne Wirkung); ohne DATUM genuegt ein RED der Police; eine
    leere POLNR traegt nichts. Die gueltige Zeile davor haelt die Kontrolle:
    die Verweigerung kommt von der falschen Zeile. Mutationsprobe: die
    Datumspruefung bzw. die Policepruefung einzeln entfernen -> rot."""
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\n"
                           f"P1;RED;01.01.2019;0.6\n{zeile}\n")
    with pytest.raises(SystemExit) as exc:
        lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall),
                        _VORGESCHICHTE)
    text = str(exc.value)
    assert muster in text and "neu registrieren" in text, text


def test_eine_undatierte_zeile_genuegt_mit_einem_red_der_police(tmp_path):
    """Die Gegenseite: ohne DATUM reicht die Police (Pauschalwert), mit
    DATUM das Datum — beides bleibt gueltig."""
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\n"
                           "P1;RED;;0.6\nP2;RED;01.06.2020;0.7\n")
    a = lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall),
                        _VORGESCHICHTE)
    assert a.anteile == {"P1": 0.6, "P2": 0.7}


def test_die_spalten_der_vorgeschichte_folgen_dem_aufruf(tmp_path):
    """Die Vorgeschichte kann andere Spaltennamen tragen (Schalter der
    Suite); die Zuordnung liest sie ueber ``spalten``, nicht ueber feste
    Namen. Mutationsprobe: ``spalten`` ignorieren -> rot."""
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\nP1;RED;01.01.2019;0.6\n")
    fremd = [{"NR": "P1", "ART": "RED", "AM": "01.01.2019"}]
    a = lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), fremd,
                        {"police": "NR", "gevo": "ART", "datum": "AM"})
    assert a.anteile == {"P1": 0.6}


def test_dieselbe_zeile_zweimal_ist_kein_widerspruch(tmp_path):
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\n"
                           "P1;RED;01.01.2019;0.6\nP1;RED;01.01.2019;0.6\n")
    a = lies_auskuenfte(fall, "auskunft.csv", Eingangsbindung(fall), _VORGESCHICHTE)
    assert a.je_datum == {"P1": {"01.01.2019": 0.6}}


def test_eine_auskunft_nur_im_dateisystem_wird_mit_dem_ausweg_verweigert(tmp_path):
    fall = _fall(tmp_path, "POLNR;GEVO;DATUM;ANTEIL\nP1;RED;;0.6\n")
    (fall / "lose.csv").write_text(
        "POLNR;GEVO;DATUM;ANTEIL\nP1;RED;;0.6\n", encoding="utf-8")
    bindung = Eingangsbindung(fall)
    with pytest.raises(SystemExit) as exc:
        lies_auskuenfte(fall, "lose.csv", bindung, _VORGESCHICHTE)
    text = str(exc.value)
    assert "nicht registriert" in text
    assert "fall registrieren" in text and "--red-anteile-datei" in text
    assert bindung.als_beleg() == {}, "nichts gelesen, nichts gebunden"


# --------------------------------------------------------------------------- #
# Zaehltest je Kommando (dynamisch), auf dem Baldrian-2-Fall
# --------------------------------------------------------------------------- #


def _lieferung() -> List[str]:
    """Die Arbeitsannahme des Laufs OHNE die Auskunft (die setzt der Test);
    die Tarifregeln traegt die Spez des Falls (ADR-024, Nachtrag)."""
    flags: List[str] = []
    for k in KANDIDATEN:
        flags += ["--red-anteil-kandidat", k]
    return flags


def _pfade(fall: Path) -> Dict[str, Path]:
    a = fall / "abgeleitet"
    return {
        "bestand": a / "bestand",
        "nach": a / "bestand-nach",
        "zeilen": a / "transformation" / "zeilen.json",
        "config": a / "bestand-config.toml",
        "schichten": a / "schichten" / "verankerung_schichten.json",
    }


def _aufruf(kommando: str, fall: Path, datei_args: List[str],
            ziel: Path) -> List[str]:
    """Der Aufruf des Kommandos wie im Lauf, mit der Auskunft aus
    ``datei_args`` und allen Ausgaben unter ``ziel``."""
    p = _pfade(fall)
    ziel.mkdir(parents=True, exist_ok=True)
    wurzel = ["--fall", str(fall)]
    if kommando == "bestand_uebernehmen":
        return wurzel + [
            "--zeilen", str(p["zeilen"]),
            "--tarif-generation", TARIF_GENERATION, "--stichtag", STICHTAG_1,
            "--vorgeschichte", METADATEN, "--generation-spez", GENERATION,
            "--anfangszustand", "materialisieren",
            "--anker-erwartungswerte", ANKER, "--out-dir", str(ziel / "uebernahme"),
        ] + _lieferung() + datei_args
    if kommando == "verankerung_belegen":
        return wurzel + [
            "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
            "--zeilen", str(p["zeilen"]), "--vorgeschichte", METADATEN,
            "--anker-erwartungswerte", ANKER,
            "--out", str(ziel / "verankerung_schichten.json"),
        ] + _lieferung() + datei_args
    if kommando == "aktuartest_lauf":
        abnahme, erwartung = ABNAHMEN[0]
        return wurzel + [
            "--abnahme", abnahme, "--generation", GENERATION,
            "--erwartungswerte", erwartung, "--stichprobe", STICHPROBE,
            "--bestand", str(p["bestand"] / "bestand.parquet"),
            "--zeilen", str(p["zeilen"]), "--vorgeschichte", METADATEN,
            "--schicht", str(p["schichten"]),
            "--repo-root", str(REPO_ROOT), "--out", str(ziel / "at.json"),
        ] + _lieferung() + datei_args
    if kommando == "migrationssuite_lauf":
        return wurzel + [
            "--generation", GENERATION, "--abzug-1", ABZUG_1,
            "--abzug-2", ABZUG_2, "--gevo-protokoll", PROTOKOLL,
            "--bestand", str(p["bestand"] / "bestand.parquet"),
            "--stichtag-1", STICHTAG_1, "--stichtag-2", STICHTAG_2,
            "--zeilen", str(p["zeilen"]), "--vorgeschichte", METADATEN,
            "--anker-erwartungswerte", ANKER, "--schicht", str(p["schichten"]),
            "--config", str(p["config"]),
            "--repo-root", str(REPO_ROOT), "--out", str(ziel / "suite.json"),
        ] + _lieferung() + datei_args
    assert kommando == "fuehrungsprobe", kommando
    return wurzel + [
        "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
        "--uebernahme", str(p["bestand"]), "--fortschreibung", str(p["nach"]),
        "--config", str(p["config"]), "--zeilen", str(p["zeilen"]),
        "--vorgeschichte", METADATEN, "--stichtag", STICHTAG_1,
        "--anker-erwartungswerte", ANKER, "--schicht", str(p["schichten"]),
        "--out", str(ziel / "probe.json"),
    ] + _lieferung() + datei_args


MAINS = {
    "aktuartest_lauf": aktuartest_lauf.main,
    "bestand_uebernehmen": bestand_uebernehmen.main,
    "fuehrungsprobe": fuehrungsprobe.main,
    "migrationssuite_lauf": migrationssuite_lauf.main,
    "verankerung_belegen": verankerung_belegen.main,
}


def _beleg(kommando: str, ziel: Path) -> dict:
    """Der Beleg des Laufs: (Eingaben, Parameterblock oder None)."""
    def lies(name: str) -> dict:
        return json.loads((ziel / name).read_text(encoding="utf-8"))

    if kommando == "bestand_uebernehmen":
        d = lies("uebernahme/uebernahme.json")
        return {"eingaben": d["eingaben"], "parameter": d}
    if kommando == "verankerung_belegen":
        d = lies("verankerung_schichten.json")["provenienz"]
        return {"eingaben": d["eingaben"], "parameter": d["parameter"]}
    if kommando == "fuehrungsprobe":
        d = lies("probe.json")["provenienz"]
        return {"eingaben": d["eingaben"], "parameter": d["parameter"]}
    d = lies("at.json" if kommando == "aktuartest_lauf" else "suite.json")
    # Block F, Nachbesserung: Auch diese beiden Laeufe fuehren die Auskunft
    # als ``red_anteile_datei {name, sha256, bezug}`` im Ergebnis.
    return {"eingaben": d["eingaben"], "parameter": d}


@pytest.fixture
def anfangszustaende_mitschnitt(monkeypatch):
    """Haengt sich vor ``anfangszustaende_je_police`` und schreibt mit, welche
    Anteile jedes Kommando ihr gibt — die Stelle, an der die Auskunft
    fachlich wirkt. Patcht jeden Namen, unter dem ein Kommando sie ruft
    (Modul-Import von ``fuehrungsprobe``, Direktruf der Suite, spaete
    Importe der uebrigen)."""
    echt = migrationssuite_lauf.anfangszustaende_je_police
    aufrufe: List[dict] = []

    def schreibt_mit(*a, **k):
        aufrufe.append({
            "red_anteile": dict(k.get("red_anteile") or {}),
            "red_anteile_je_datum": {
                p: dict(d) for p, d in
                (k.get("red_anteile_je_datum") or {}).items()},
        })
        return echt(*a, **k)

    monkeypatch.setattr(migrationssuite_lauf, "anfangszustaende_je_police",
                        schreibt_mit)
    monkeypatch.setattr(fuehrungsprobe, "anfangszustaende_je_police",
                        schreibt_mit)
    return aufrufe


@pytest.mark.parametrize("kommando", ANTEIL_KOMMANDOS)
def test_zaehltest_mit_registrierter_auskunft_gruen_und_gebunden(
        kommando, gefahrener_fall, anfangszustaende_mitschnitt):
    """Je Kommando: gruen, die Auskunft erreicht die Anfangszustaende (mit
    Anteil UND Datum), und der Beleg nennt die Datei mit dem Hash ihrer
    Bytes — der Beleg bezeugt, was das Kommando gelesen hat. Der Einzelwert
    steht in keinem Beleg mehr.

    Mutationsproben je Kommando: ``red_anteile=`` im Aufruf von
    ``anfangszustaende_je_police`` auf ``{}`` setzen -> rot; die Datei nicht
    ueber die Bindung lesen -> rot (Eingaben ohne die Datei)."""
    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-gruen" / kommando
    code = MAINS[kommando](
        _aufruf(kommando, fall, ["--red-anteile-datei", AUSKUNFT], ziel))
    assert code == 0, f"{kommando} mit registrierter Auskunft"

    erwartet_anteile = {e.partition("=")[0]: float(e.partition("=")[2])
                        for e in RED_ANTEILE}
    erwartet_je_datum = {p: {RED_DATEN[p]: a}
                         for p, a in erwartet_anteile.items()}
    assert anfangszustaende_mitschnitt, (
        f"{kommando} ruft anfangszustaende_je_police nicht")
    for aufruf in anfangszustaende_mitschnitt:
        assert aufruf["red_anteile"] == erwartet_anteile
        assert aufruf["red_anteile_je_datum"] == erwartet_je_datum

    roh = (fall / "eingang" / AUSKUNFT).read_bytes()
    sha = hashlib.sha256(roh).hexdigest()
    beleg = _beleg(kommando, ziel)
    assert beleg["eingaben"].get(f"eingang/{AUSKUNFT}") == sha, (
        f"{kommando}: die Auskunft steht nicht mit dem Hash ihrer Bytes in "
        f"den Eingaben ({sorted(beleg['eingaben'])})")
    parameter = beleg["parameter"]
    if parameter is not None:
        assert "red_anteile" not in parameter, (
            "der Einzelwert steht nicht mehr im Beleg")
        assert parameter["red_anteile_datei"] == {
            "name": AUSKUNFT, "sha256": sha,
            "bezug": {p: [AUSKUNFT_BEZUG] for p in erwartet_anteile}}


def test_die_fuehrungsprobe_nennt_die_auskunft_in_ihrem_aufruf_und_ist_nachrechenbar(
        gefahrener_fall):
    """Block F, Nachbesserung: Die Naht ``Fuehrungsprobe._aufruf`` — der
    Aufruf im Beleg ist das, womit der Abnahmebericht die Probe nachrechnet.
    Liesse ``_aufruf`` die Auskunft aus, rechnete die Nachrechnung eine
    andere Welt und fiele bei jedem Fall mit Herabsetzungen, oder, schlimmer,
    bestaetigte sich an einem Beleg, der die Auskunft nie genannt hat. Die
    Zaehlprobe prueft deshalb beides: das Paar ``--red-anteile-datei <name>``
    steht im Aufruf, und die Nachrechnung mit genau diesem Aufruf findet
    keine Abweichung. Mutationsprobe (Mh des Pruefers): das Paar aus
    ``_aufruf`` entfernen -> rot."""
    from rechner_pipeline.gates import abnahmebericht

    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-aufruf" / "fuehrungsprobe"
    assert fuehrungsprobe.main(_aufruf(
        "fuehrungsprobe", fall, ["--red-anteile-datei", AUSKUNFT], ziel)) == 0
    probe = json.loads((ziel / "probe.json").read_text(encoding="utf-8"))
    aufruf = probe["provenienz"]["aufruf"]
    paare = [(a, b) for a, b in zip(aufruf, aufruf[1:])]
    assert ("--red-anteile-datei", AUSKUNFT) in paare, aufruf
    assert abnahmebericht._fuehrungsprobe_nachgerechnet(
        probe, fall, REPO_ROOT) == []

    # Gegenprobe: Ohne das Paar rechnet die Nachrechnung eine andere Welt
    # (hier: ohne Auskunft) und benennt die Abweichung — der Beleg bezeugt
    # dann nicht die Probe, die er nennt.
    i = aufruf.index("--red-anteile-datei")
    ohne = dict(probe, provenienz=dict(
        probe["provenienz"], aufruf=aufruf[:i] + aufruf[i + 2:]))
    meldung = abnahmebericht._fuehrungsprobe_nachgerechnet(
        ohne, fall, REPO_ROOT)
    assert meldung, "eine Probe ohne die Auskunft im Aufruf haette auffallen muessen"


@pytest.mark.parametrize("kommando", ["aktuartest_lauf",
                                      "migrationssuite_lauf"])
def test_ohne_auskunft_fuehrt_das_ergebnis_das_feld_mit_null(
        kommando, gefahrener_fall):
    """Das Feld steht IMMER im Ergebnis — ``null``, wenn der Lauf keine
    Auskunft nennt. Der Abnahmebericht verlangt es (ein Ergebnis ohne das
    Feld ist von einem Lauf vor dieser Aenderung), und nur ein immer
    geschriebenes Feld unterscheidet ``keine Auskunft`` von ``Lauf kannte
    das Feld nicht``. Mutationsprobe: das Feld nur bei vorhandener Auskunft
    schreiben -> rot."""
    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-null" / kommando
    argv = _aufruf(kommando, fall, [], ziel)
    # ohne Schicht und Vorgeschichte: die Welt ohne jede Herabsetzungs-Lage
    for option in ("--schicht", "--vorgeschichte"):
        i = argv.index(option)
        del argv[i:i + 2]
    MAINS[kommando](argv)
    ergebnis = _beleg(kommando, ziel)["parameter"]
    assert "red_anteile_datei" in ergebnis
    assert ergebnis["red_anteile_datei"] is None


@pytest.mark.parametrize("kommando", ANTEIL_KOMMANDOS)
def test_zaehltest_ohne_registrierung_wird_mit_dem_ausweg_verweigert(
        kommando, gefahrener_fall):
    """Dieselbe Datei, gleicher Inhalt, nur im Dateisystem: Das Kommando
    verweigert — sagt, dass sie nicht registriert ist und wie sie es wird —
    und schreibt nichts (kein Beleg, kein Ergebnis). Mutationsprobe: den
    Zugriff am Register vorbei (``Path(name)`` statt ``eingang_datei``)
    -> rot."""
    fall = gefahrener_fall
    lose = fall / f"auskunft_nicht_registriert_{kommando}.csv"
    lose.write_bytes((fall / "eingang" / AUSKUNFT).read_bytes())
    assert lose.is_file()
    ziel = fall / "abgeleitet" / "auskunft-verweigert" / kommando
    argv = _aufruf(kommando, fall, ["--red-anteile-datei", lose.name], ziel)
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando](argv)
    text = str(exc.value)
    assert "nicht registriert" in text and "fall registrieren" in text, text
    assert not [p for p in ziel.rglob("*") if p.is_file()], (
        f"{kommando} hat vor der Verweigerung geschrieben")


@pytest.mark.parametrize("kommando", ANTEIL_KOMMANDOS)
def test_eine_auskunft_ohne_ereignisse_wird_nicht_still_ueberlesen(
        kommando, gefahrener_fall, capsys):
    """Die Anteile gehoeren zu den Ereignissen der Vorgeschichte (bei der
    Uebernahme: zum Anfangszustand). Ohne sie blieb die Auskunft frueher
    ungelesen und ungebunden, der Lauf gruen — ein stilles Verwerfen. Jetzt
    Exit 2 mit Begruendung, vor jedem Schreiben. Mutationsprobe: die
    Pruefung im Kommando entfernen -> rot."""
    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-ohne-ereignisse" / kommando
    argv = _aufruf(kommando, fall, ["--red-anteile-datei", AUSKUNFT], ziel)
    if kommando == "bestand_uebernehmen":
        argv[argv.index("materialisieren")] = "grundvertrag"
    else:
        i = argv.index("--vorgeschichte")
        del argv[i:i + 2]
    assert MAINS[kommando](argv) == 2
    assert "--red-anteile-datei wirkt nur" in capsys.readouterr().err
    assert not [p for p in ziel.rglob("*") if p.is_file()]


@pytest.mark.parametrize("kommando", ANTEIL_KOMMANDOS)
def test_der_einzelwert_je_police_wird_nicht_mehr_angenommen(
        kommando, gefahrener_fall, capsys):
    """Breaking Change: ``--red-anteil POLNR=ANTEIL`` ist in allen fuenf
    Kommandos entfernt. Der Aufruf ist im uebrigen der gruene des
    Laufs — die Ablehnung kommt vom Schalter, nicht von einem anderen
    Fehler. Mutationsprobe: den Schalter in einem Parser wieder
    eintragen -> rot."""
    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-einzelwert" / kommando
    argv = _aufruf(kommando, fall, ["--red-anteile-datei", AUSKUNFT], ziel)
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando](argv + ["--red-anteil", "7000396=0.60"])
    assert exc.value.code == 2
    fehler = capsys.readouterr().err
    assert "--red-anteil" in fehler, fehler
    assert not [p for p in ziel.rglob("*") if p.is_file()]


def _auskunft_registrieren(fall: Path, tmp_path: Path, name: str,
                           inhalt: str) -> str:
    """Eine weitere Auskunft unter ``name`` im Fall registrieren (der Fall
    des Moduls ist modulweit geteilt: Namen sind je Test eindeutig)."""
    quelle = tmp_path / "quelle" / name
    quelle.parent.mkdir(parents=True, exist_ok=True)
    quelle.write_text(inhalt, encoding="utf-8")
    registrieren(fall, quelle)
    return name


@pytest.mark.parametrize("kommando", ANTEIL_KOMMANDOS)
@pytest.mark.parametrize("zusatz, muster", [
    ("9999999;RED;01.01.2020;0.33;Schreiben X\n", "9999999"),
    ("7000396;RED;31.12.2099;0.11;Schreiben Y\n", "31.12.2099"),
    (";RED;01.01.2020;0.33;ohne Police\n", "POLNR"),
], ids=["unbekannte_police", "datum_ohne_ereignis", "leere_polnr"])
def test_eine_auskunftszeile_ohne_wirkung_wird_verweigert(
        kommando, zusatz, muster, gefahrener_fall, tmp_path):
    """Block F, Nachbesserung (Repro P1): Eine RED-Zeile, die keinem
    RED-Ereignis der Vorgeschichte entspricht, bliebe still ohne Wirkung —
    und stuende doch im Beleg mit Hash und Bezug, als haette sie getragen.
    Jetzt verweigern alle fuenf Kommandos, bevor sie schreiben. Mutationsprobe:
    die Zuordnung in ``lies_auskuenfte`` entfernen -> rot."""
    fall = gefahrener_fall
    inhalt = ((fall / "eingang" / AUSKUNFT).read_text(encoding="utf-8")
              + zusatz)
    name = _auskunft_registrieren(
        fall, tmp_path, f"auskunft_ohne_wirkung_{kommando}_{muster[:4]}.csv",
        inhalt)
    ziel = fall / "abgeleitet" / "auskunft-ohne-wirkung" / kommando / muster
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando](_aufruf(
            kommando, fall, ["--red-anteile-datei", name], ziel))
    text = str(exc.value)
    assert muster in text and "neu registrieren" in text, text
    assert not [p for p in ziel.rglob("*") if p.is_file()], (
        f"{kommando} hat vor der Verweigerung geschrieben")


# --------------------------------------------------------------------------- #
# Konsument des Schichtbelegs: aktuartest_lauf --schicht
# --------------------------------------------------------------------------- #


def _auskunft_des_falls(fall: Path) -> dict:
    """Der Belegblock der Auskunft des Falls, wie ihn ein Lauf mit
    ``--red-anteile-datei`` fuehrt (Name und SHA-256 der Bytes)."""
    roh = (fall / "eingang" / AUSKUNFT).read_bytes()
    return {"name": AUSKUNFT, "sha256": hashlib.sha256(roh).hexdigest(),
            "bezug": {}}


def _manipuliert(fall: Path, aendere) -> str:
    """Kopie des Schichtbelegs mit geaendertem Provenienz-Parameterblock;
    Systemstand und Eingaben bleiben die echten — nur die Aussage ueber die
    Auskunft ist gefaelscht. Gibt den Namen unter ``abgeleitet/`` zurueck."""
    quelle = _pfade(fall)["schichten"]
    d = json.loads(quelle.read_text(encoding="utf-8"))
    aendere(d["provenienz"]["parameter"])
    ziel = quelle.with_name("verankerung_schichten_manipuliert.json")
    ziel.write_text(json.dumps(d), encoding="utf-8")
    return str(ziel.relative_to(fall))


def test_der_konsument_nimmt_den_echten_beleg_an(gefahrener_fall):
    """Kontrolle fuer die folgenden: Dieselbe Pruefung laesst den
    unveraenderten Beleg durch — sonst bewiese ihre Ablehnung nichts."""
    fall = gefahrener_fall
    roh = _schichten(fall, str(_pfade(fall)["schichten"].relative_to(fall)),
                     bindung=Eingangsbindung(fall), repo_root=REPO_ROOT,
                     auskunft=_auskunft_des_falls(fall))
    assert roh


def test_der_konsument_prueft_die_auskunft_gegen_die_eingaben(gefahrener_fall):
    """Die Aussage ``red_anteile_datei`` ist nachrechenbar, nicht nur
    behauptet: Name und Hash muessen unter den Eingaben des Belegs stehen
    (die der Konsument ohnehin gegen die Platte nachrechnet). Mutationsprobe:
    den Abgleich in ``_schichten`` entfernen -> rot."""
    fall = gefahrener_fall

    def anderer_hash(parameter):
        parameter["red_anteile_datei"]["sha256"] = "0" * 64

    def andere_datei(parameter):
        parameter["red_anteile_datei"]["name"] = "eine_andere_auskunft.csv"

    for aendere, muster in ((anderer_hash, "red_anteile_datei"),
                            (andere_datei, "red_anteile_datei")):
        name = _manipuliert(fall, aendere)
        with pytest.raises(SystemExit, match=muster):
            _schichten(fall, name, bindung=Eingangsbindung(fall),
                       repo_root=REPO_ROOT, auskunft=_auskunft_des_falls(fall))


def test_der_konsument_lehnt_den_einzelwert_im_beleg_ab(gefahrener_fall):
    """Ein Beleg, der Anteile als getippte Liste nennt, ist im Schema des
    Einzelparameters — nicht bindbar. Mutationsprobe: die Schemapruefung in
    ``_schichten`` entfernen -> rot."""
    fall = gefahrener_fall
    name = _manipuliert(
        fall, lambda p: p.__setitem__("red_anteile", ["7000396=0.60"]))
    with pytest.raises(SystemExit, match="Einzelparameter"):
        _schichten(fall, name, bindung=Eingangsbindung(fall),
                   repo_root=REPO_ROOT, auskunft=_auskunft_des_falls(fall))


# --------------------------------------------------------------------------- #
# Welt-Gleichheit: Schichtbeleg und Lauf lesen dieselbe Auskunft
# --------------------------------------------------------------------------- #

def _andere_auskunft(fall: Path, tmp_path: Path, name: str) -> str:
    """Eine zweite, in sich gueltige Auskunft mit anderem Anteil (gleiche
    Policen und Daten wie die des Falls)."""
    return _auskunft_registrieren(fall, tmp_path, name, (
        "POLNR;GEVO;DATUM;ANTEIL;BEZUG\n"
        f"7000396;RED;{RED_DATEN['7000396']};0.50;zweite Auskunft\n"
        f"7000679;RED;{RED_DATEN['7000679']};0.50;zweite Auskunft\n"))


@pytest.mark.parametrize("kommando", SCHICHT_KOMMANDOS)
def test_ein_lauf_mit_anderer_auskunft_als_der_schichtbeleg_wird_verweigert(
        kommando, gefahrener_fall, tmp_path):
    """Block F, Nachbesserung (Repro P2): Der Schichtbeleg wurde mit der
    Auskunft A erzeugt, der Lauf liest die Auskunft B — beide einzeln
    gueltig, gebunden und gruen, aber zwei Welten: Der Lauf vergleicht
    gelieferte Werte mit einer Anfangslage, auf der die Schicht nie
    verankert wurde. Der Lauf verweigert mit Ausweg, bevor er schreibt.
    Mutationsprobe: den Abgleich in ``_schichten`` entfernen -> rot."""
    fall = gefahrener_fall
    name = _andere_auskunft(fall, tmp_path, f"auskunft_b_{kommando}.csv")
    ziel = fall / "abgeleitet" / "auskunft-welt" / f"andere-{kommando}"
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando](_aufruf(
            kommando, fall, ["--red-anteile-datei", name], ziel))
    text = str(exc.value)
    assert "Schichtbeleg" in text and AUSKUNFT in text and name in text, text
    assert "--red-anteile-datei" in text and "neu erzeugen" in text, text
    assert not [p for p in ziel.rglob("*") if p.is_file()], (
        f"{kommando} hat vor der Verweigerung geschrieben")


@pytest.mark.parametrize("kommando", SCHICHT_KOMMANDOS)
def test_ein_lauf_ohne_auskunft_mit_einem_schichtbeleg_mit_auskunft_wird_verweigert(
        kommando, gefahrener_fall):
    """Repro P3: Der Schichtbeleg traegt die Auskunft, der Lauf nennt keine —
    er rechnete die Anfangslage ohne Anteile und nahm die Schicht einer
    anderen Welt. ``keine Auskunft`` gilt nur dann als gleich, wenn sie auf
    BEIDEN Seiten fehlt. Mutationsprobe: ``None`` des Laufs als gleich
    behandeln -> rot."""
    fall = gefahrener_fall
    ziel = fall / "abgeleitet" / "auskunft-welt" / f"ohne-{kommando}"
    with pytest.raises(SystemExit) as exc:
        MAINS[kommando](_aufruf(kommando, fall, [], ziel))
    text = str(exc.value)
    assert "Schichtbeleg" in text and AUSKUNFT in text, text
    assert "keine Auskunft" in text and "--red-anteile-datei" in text, text
    assert not [p for p in ziel.rglob("*") if p.is_file()]


def _prov_manipuliert(fall: Path, aendere, name: str) -> str:
    """Wie :func:`_manipuliert`, aber mit Zugriff auf die GANZE Provenienz
    (Eingaben UND Parameterblock)."""
    quelle = _pfade(fall)["schichten"]
    d = json.loads(quelle.read_text(encoding="utf-8"))
    aendere(d["provenienz"])
    ziel = quelle.with_name(name)
    ziel.write_text(json.dumps(d), encoding="utf-8")
    return str(ziel.relative_to(fall))


def _ohne_auskunft_im_parameterblock(prov):
    del prov["parameter"]["red_anteile_datei"]


def _ohne_auskunft_ueberhaupt(prov):
    del prov["parameter"]["red_anteile_datei"]
    del prov["eingaben"][f"eingang/{AUSKUNFT}"]


def _auskunft_nur_im_parameterblock(prov):
    del prov["eingaben"][f"eingang/{AUSKUNFT}"]


def _schicht_pruefen(fall: Path, name: str, auskunft):
    return _schichten(fall, name, bindung=Eingangsbindung(fall),
                      repo_root=REPO_ROOT, auskunft=auskunft)


def test_ein_beleg_dessen_eingaben_eine_auskunft_nennen_der_parameterblock_aber_nicht_ist_ein_formfehler(
        gefahrener_fall):
    """Die Eingaben nennen die Auskunft, der Parameterblock fuehrt sie nicht:
    der Beleg widerspricht sich selbst — mit dem Lauf-Vergleich allein (der
    Block fehlt, also ``keine Auskunft``) lieferte ein Lauf OHNE Auskunft
    den Beleg als gleich aus. Mutationsprobe: die Formpruefung entfernen ->
    rot."""
    fall = gefahrener_fall
    name = _prov_manipuliert(fall, _ohne_auskunft_im_parameterblock,
                             "schicht_form1.json")
    for auskunft in (None, _auskunft_des_falls(fall)):
        with pytest.raises(SystemExit, match="Formfehler"):
            _schicht_pruefen(fall, name, auskunft)


def test_ein_beleg_dessen_parameterblock_eine_auskunft_fuehrt_die_eingaben_nicht_ist_ein_formfehler(
        gefahrener_fall):
    """Umgekehrt: der Block nennt die Auskunft, die Eingaben binden sie
    nicht — die Aussage ist nicht nachrechenbar. Mutationsprobe: die
    Nachrechnung gegen die Eingaben entfernen -> rot."""
    fall = gefahrener_fall
    name = _prov_manipuliert(fall, _auskunft_nur_im_parameterblock,
                             "schicht_form2.json")
    with pytest.raises(SystemExit, match="red_anteile_datei"):
        _schicht_pruefen(fall, name, _auskunft_des_falls(fall))


def test_keine_auskunft_auf_beiden_seiten_gilt_als_gleich(gefahrener_fall):
    """Die Gegenseite der Welt-Gleichheit: Ein Beleg ohne Auskunft (weder
    im Parameterblock noch unter den Eingaben) und ein Lauf ohne Auskunft
    sind dieselbe Welt — sonst waere jeder Fall ohne Herabsetzungen
    gesperrt. Mutationsprobe: ``None`` == ``None`` als ungleich -> rot."""
    fall = gefahrener_fall
    name = _prov_manipuliert(fall, _ohne_auskunft_ueberhaupt,
                             "schicht_ohne.json")
    assert _schicht_pruefen(fall, name, None)
    with pytest.raises(SystemExit, match="keine Auskunft"):
        _schicht_pruefen(fall, name, _auskunft_des_falls(fall))


def test_dieselbe_auskunft_auf_beiden_seiten_wird_angenommen(gefahrener_fall):
    """Kontrolle: Gleicher Hash, gleiche Welt — auch unter anderem Namen
    derselben Bytes (Gleichheit ist die der Bytes)."""
    fall = gefahrener_fall
    gleich = dict(_auskunft_des_falls(fall), name="kopie_derselben_bytes.csv")
    assert _schicht_pruefen(
        fall, str(_pfade(fall)["schichten"].relative_to(fall)), gleich)


# --------------------------------------------------------------------------- #
# Der Abnahmebericht bindet die Auskunft mit (A-M4)
# --------------------------------------------------------------------------- #


def _suite_und_probe(fall: Path):
    berichte = fall / "abgeleitet" / "berichte"
    suite = json.loads((berichte / "migrationssuite.json").read_text("utf-8"))
    probe = json.loads((berichte / "fuehrungsprobe.json").read_text("utf-8"))
    return suite, probe


def test_der_abnahmebericht_nimmt_die_suite_des_echten_laufs_mit_auskunft_an(
        gefahrener_fall):
    """Kontrolle: Suite und Fuehrungsprobe des echten Laufs tragen dieselbe
    Auskunft, der Abnahmebericht findet nichts."""
    from rechner_pipeline.gates import abnahmebericht

    fall = gefahrener_fall
    suite, probe = _suite_und_probe(fall)
    assert suite["red_anteile_datei"]["name"] == AUSKUNFT
    assert abnahmebericht._suite_auskunft_fehler(suite) == []
    assert abnahmebericht._fuehrungsprobe_fehler(
        probe, fall=fall, repo_root=REPO_ROOT, suite=suite,
        erwartetes_system=suite["system"]) == []


def test_der_abnahmebericht_verlangt_das_feld_der_suite(gefahrener_fall):
    """Block F, Nachbesserung: Eine Suite ohne ``red_anteile_datei`` ist von
    einem Lauf, der die Auskunft nicht nennen konnte — der Bericht nimmt sie
    nicht an (Verschaerfung der Akzeptanzmenge -> GATE_VERSION 6.0.0, ADR-012).
    ``null`` ist dagegen gueltig (keine Auskunft). Mutationsprobe: die
    Pflicht entfernen -> rot."""
    from rechner_pipeline.gates import abnahmebericht

    suite, _ = _suite_und_probe(gefahrener_fall)
    ohne = {k: v for k, v in suite.items() if k != "red_anteile_datei"}
    fehler = abnahmebericht._suite_auskunft_fehler(ohne)
    assert fehler and "red_anteile_datei" in fehler[0], fehler
    assert abnahmebericht._suite_auskunft_fehler(
        dict(suite, red_anteile_datei=None)) == []


@pytest.mark.parametrize("aendere, muster", [
    (lambda d: d.update(sha256="0" * 64), "eingaben"),
    (lambda d: d.update(sha256="abc"), "SHA-256"),
    (lambda d: d.update(name=""), "name"),
    (lambda d: d.update(bezug=["x"]), "bezug"),
    (lambda d: d.update(name="andere.csv"), "eingaben"),
], ids=["hash_nicht_in_den_eingaben", "hash_kein_sha", "name_leer",
        "bezug_kein_objekt", "name_nicht_in_den_eingaben"])
def test_der_abnahmebericht_rechnet_die_auskunft_der_suite_nach(
        gefahrener_fall, aendere, muster):
    """Die Aussage ``red_anteile_datei`` der Suite ist nachrechenbar: Name
    und Hash muessen unter den Eingaben der Suite stehen (die der Bericht
    ohnehin bindet). Mutationsprobe: den Abgleich mit den Eingaben
    entfernen -> rot."""
    from rechner_pipeline.gates import abnahmebericht

    suite, _ = _suite_und_probe(gefahrener_fall)
    datei = dict(suite["red_anteile_datei"])
    aendere(datei)
    fehler = abnahmebericht._suite_auskunft_fehler(
        dict(suite, red_anteile_datei=datei))
    assert fehler and muster in " ".join(fehler), fehler


def test_der_abnahmebericht_haelt_suite_und_fuehrungsprobe_auf_einer_auskunft(
        gefahrener_fall):
    """Suite und Fuehrungsprobe muessen dieselbe Auskunft gelesen haben —
    sonst traegt die Fuehrung eine andere Welt als die, in der die Suite
    abgenommen wurde, und beide Belege einzeln sind gruen. Mutationsprobe:
    den Abgleich in ``_fuehrungsprobe_fehler`` entfernen -> rot."""
    from rechner_pipeline.gates import abnahmebericht

    fall = gefahrener_fall
    suite, probe = _suite_und_probe(fall)
    for fremd in (None, dict(suite["red_anteile_datei"], sha256="1" * 64)):
        fehler = abnahmebericht._fuehrungsprobe_fehler(
            probe, fall=fall, repo_root=REPO_ROOT,
            suite=dict(suite, red_anteile_datei=fremd),
            erwartetes_system=suite["system"])
        assert any("verschiedene Auskuenfte" in f for f in fehler), fehler


def test_die_version_des_abnahmeberichts_nennt_den_grund():
    """ADR-012: Die Akzeptanzmenge hat sich geaendert (eine Suite ohne das
    Feld war vorher gueltig) — Major, und die README-Zeile erzaehlt den
    Sprung. ``tests/test_gate_versionsregel.py`` haelt Version und Zeile
    zusammen; hier steht, WARUM 6.0.0."""
    from rechner_pipeline.gates import abnahmebericht

    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    zeile = next(z for z in readme.splitlines()
                 if z.startswith("| G2-Vorlage (Version `"))
    # 7.0.0 (Pruefer-Befund B1, 2026-10-01), 8.0.0 (Fuehrungswert,
    # 2026-10-01), 9.0.0 (Tarifregeln aus der Spez, ADR-024 Nachtrag) und
    # 10.0.0 (Pruefrunde G: Fuehrungswert nachgerechnet, Belege an der Spez)
    # erweitern dieselbe Zeile; der Grund fuer 6.0.0 steht weiter darin.
    assert abnahmebericht.GATE_VERSION == "10.0.0"
    assert "`10.0.0`" in zeile and "nachgerechnet" in zeile
    assert "`9.0.0`" in zeile and "Spez" in zeile
    assert "`6.0.0`" in zeile and "red_anteile_datei" in zeile
    assert "`7.0.0`" in zeile and "pflichtschicht" in zeile
    assert "`8.0.0`" in zeile and "fuehrungswert" in zeile
