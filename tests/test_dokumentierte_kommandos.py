"""Jedes woertlich dokumentierte Kommando wird vom Parser seines Moduls angenommen.

Befund Pruefrunde H (H14): Der woertliche Aufruf der Zugangsprobe im Skill
``migrationsfall-durchfuehren`` und in ``AGENTS.md`` nannte das
Pflichtargument ``--linie`` nicht; der Parser wies ihn ab. Wer dem Skill
folgt, scheitert am ersten Schritt — und der Fliesstext darunter
korrigierte das nur mittelbar. Die Klasse ist "ein Dokument nennt einen
Aufruf, den das Kommando nicht annimmt"; sie ist MECHANIK, kein
Wortlisten-Test: Geprueft wird nicht, was ein Text sagt, sondern ob ein
woertlich angegebenes ``python -m rechner_pipeline....`` den echten
Argumentparser des Moduls besteht (Pflichtargumente vorhanden, kein
unbekannter Schalter, Unterbefehl bekannt, Auswahlwerte zulaessig).

Die Menge: die Skills und Agenten unter ``.claude/`` (die Spiegel unter
``.agents/`` sind byte-gleich, ``tests/test_agent_workflow_docs.py``),
``AGENTS.md``, ``README.md``, ``ONBOARDING.md`` und die ADRs 025 und 026
(Bedienfolgen). Gefunden wird ein Kommando in einem Codeblock (Zeilen mit
``\\`` am Ende werden verbunden) oder in einer Inline-Code-Spanne
(Zeilenumbrueche darin sind Leerraum), wenn ``python -m rechner_pipeline.``
am Anfang oder hinter einer Pipe steht.

Behandelt, ausdruecklich und gezaehlt:

* Platzhalter (``<fall>``, ``faelle/<fall>``) sind WERTE: Typ und Auswahl
  werden fuer sie nicht geprueft. Fuer konkrete Werte wird die Auswahl
  geprueft, der ``type`` nie ausgefuehrt (er liest Dateien oder hasht den
  Baum — das ist Laufzeit, kein Aufruf).
* Optionale Teile in eckigen Klammern (``[--bis <ISO>]``) werden
  MITgeprueft: die Klammern entfallen, der Inhalt muss bestehen.
* Alternativen (``A-M1|A-M2|A-M3``) werden JE Alternative geprueft.
* Eine Auslassung ``...`` heisst "weitere Angaben": dann wird nur geprueft,
  dass jeder genannte Schalter bekannt ist, nicht die Pflichtargumente.
* ``...]`` am Ende einer Klammer heisst "wiederholbar" und entfaellt;
  ``...`` direkt nach einem Schalter ist dessen Wert.
* Eine blosse Nennung (``python -m rechner_pipeline.x`` ohne Argument)
  ist kein Aufruf; geprueft wird nur, dass das Modul einen Parser hat. Die
  Nennung eines Unterbefehls ohne Schalter (``... anfangsbestand belegen``)
  prueft, dass der Unterbefehl bekannt ist.

Was sich so nicht pruefen laesst, steht in :data:`AUSNAHMEN` mit Grund,
gehalten mit ``==``.

Knoten: system/skills
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parents[1]

#: Die Dokumente, deren woertliche Aufrufe gelten muessen.
DOKUMENTE: Tuple[str, ...] = tuple(sorted(
    [str(p.relative_to(REPO)) for p in (REPO / ".claude" / "skills").glob("*/SKILL.md")]
    + [str(p.relative_to(REPO)) for p in (REPO / ".claude" / "agents").glob("*.md")]
    + ["AGENTS.md", "README.md", "ONBOARDING.md"]
    + [str(p.relative_to(REPO)) for p in (REPO / "docs" / "architektur").glob("adr-02[56]-*.md")]
))

PRAEFIX = "python -m rechner_pipeline."

#: Woertliche Kommandos, die der Test bewusst NICHT gegen den Parser haelt
#: (Dokument, Kommando woertlich, Leerraum normalisiert) -> Grund. Gehalten
#: mit ``==``: Eine Ausnahme, deren Kommando es so nicht mehr gibt (auch:
#: berichtigt), faellt auf und wird gestrichen.
AUSNAHMEN: Dict[Tuple[str, str], str] = {}


@dataclass(frozen=True)
class Kommando:
    dokument: str
    zeile: int
    text: str

    def _woerter(self) -> List[str]:
        # Ein Platzhalter mit Leerraum (``<schluessel der programmleitung>``)
        # ist EIN Wert.
        text = re.sub(r"<[^<>]*>", lambda m: m.group(0).replace(" ", "_"), self.text)
        return shlex.split(text, comments=True)

    @property
    def modul(self) -> str:
        return self._woerter()[2]

    @property
    def argumente(self) -> List[str]:
        return self._woerter()[3:]

    def __str__(self) -> str:
        return f"{self.dokument}:{self.zeile}: {self.text}"


_FENCE = re.compile(r"^\s*```")


def _aufrufe_in(text: str) -> List[Tuple[int, str]]:
    """Die Kommandos in einer Zeile bzw. Spanne: am Anfang oder hinter einer
    Pipe (``git diff ... | python -m rechner_pipeline.ontologie.impact``),
    bis zur naechsten Pipe oder zur schliessenden Klammer eines ``$( )``.
    Rueckgabe: (Zeichenposition, Kommando)."""
    aus: List[Tuple[int, str]] = []
    for treffer in re.finditer(re.escape(PRAEFIX), text):
        i = treffer.start()
        davor = text[:i].rstrip()
        if davor and not davor.endswith(("|", "$(")):
            continue                       # mitten in Prosa: keine Zeile, die ruft
        stueck = text[i:].split(" | ", 1)[0]
        tiefe = 0
        for j, zeichen in enumerate(stueck):
            tiefe += (zeichen == "(") - (zeichen == ")")
            if tiefe < 0:
                stueck = stueck[:j]
                break
        aus.append((i, stueck.strip()))
    return aus


def _aus_codeblock(zeilen: List[Tuple[int, str]], dokument: str) -> List[Kommando]:
    aus: List[Kommando] = []
    logisch: List[Tuple[int, str]] = []
    puffer, start = "", None
    for nr, zeile in zeilen:
        if start is None:
            start = nr
        stueck = zeile.rstrip()
        if stueck.endswith("\\"):
            puffer += stueck[:-1] + " "
            continue
        logisch.append((start, puffer + stueck))
        puffer, start = "", None
    if puffer:
        logisch.append((start, puffer))
    for nr, zeile in logisch:
        text = " ".join(zeile.split())
        for vorsatz in ("$ ", "! "):
            if text.startswith(vorsatz):
                text = text[len(vorsatz):]
        aus.extend(Kommando(dokument, nr, k) for _, k in _aufrufe_in(text))
    return aus


def kommandos_aus(dokument: str, wurzel: Path = REPO) -> List[Kommando]:
    """Alle woertlichen Kommandos eines Dokuments, in Reihenfolge."""
    zeilen = (wurzel / dokument).read_text(encoding="utf-8").splitlines()
    aus: List[Kommando] = []
    prosa: List[Tuple[int, str]] = []
    block: Optional[List[Tuple[int, str]]] = None
    for nr, zeile in enumerate(zeilen, 1):
        if _FENCE.match(zeile):
            if block is None:
                block = []
                prosa.append((nr, ""))       # ein Codeblock beendet jede Spanne
            else:
                aus.extend(_aus_codeblock(block, dokument))
                block = None
            continue
        if block is not None:
            block.append((nr, zeile))
        else:
            prosa.append((nr, zeile))
    # Inline-Spannen: ueber Zeilen hinweg, aber nie ueber eine Leerzeile
    # (Absatzgrenze) oder einen Codeblock.
    absatz: List[Tuple[int, str]] = []
    for nr, zeile in prosa + [(len(zeilen) + 1, "")]:
        if zeile.strip():
            absatz.append((nr, zeile))
            continue
        if absatz:
            text = "\n".join(z for _, z in absatz)
            for treffer in re.finditer(r"`([^`]+)`", text):
                inhalt = " ".join(treffer.group(1).split())
                for _, k in _aufrufe_in(inhalt):
                    zeile_nr = absatz[0][0] + text[:treffer.start()].count("\n")
                    aus.append(Kommando(dokument, zeile_nr, k))
        absatz = []
    return sorted(aus, key=lambda k: k.zeile)


def alle_kommandos() -> List[Kommando]:
    return [k for dok in DOKUMENTE for k in kommandos_aus(dok)]


# --------------------------------------------------------------------------- #
# Der Parser eines Moduls, ohne das Kommando auszufuehren
# --------------------------------------------------------------------------- #

class _Gefangen(Exception):
    def __init__(self, parser: argparse.ArgumentParser):
        self.parser = parser


def parser_von(modul: str) -> argparse.ArgumentParser:
    """Den Parser holen, den ``main`` baut — ``parse_args`` wird abgefangen,
    BEVOR geparst wird; nichts des Kommandos laeuft."""
    m = importlib.import_module(modul)
    if not hasattr(m, "main"):
        raise AssertionError(f"{modul}: kein main — kein Kommando")
    original = argparse.ArgumentParser.parse_args

    def fangen(self, args=None, namespace=None):
        raise _Gefangen(self)

    argparse.ArgumentParser.parse_args = fangen
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            m.main(["--hilfe-wird-nie-geparst"])
    except _Gefangen as g:
        return g.parser
    finally:
        argparse.ArgumentParser.parse_args = original
    raise AssertionError(f"{modul}: main lief ohne parse_args")


def _ist_platzhalter(wert: str) -> bool:
    return "<" in wert and ">" in wert


class _Fehler(Exception):
    pass


def _parse(parser: argparse.ArgumentParser, argv: List[str], *, nur_schalter: bool) -> None:
    """Mit dem echten argparse parsen — ohne ``type`` (Laufzeit), mit
    Auswahlpruefung fuer konkrete Werte. ``nur_schalter``: Pflichtargumente
    nicht verlangen (Auslassung ``...``), unbekannte Schalter schon."""
    get_value = argparse.ArgumentParser._get_value
    check_value = argparse.ArgumentParser._check_value
    error = argparse.ArgumentParser.error

    def roh(self, action, arg_string):
        return arg_string

    def auswahl(self, action, value):
        if isinstance(value, str) and _ist_platzhalter(value):
            return
        return check_value(self, action, value)

    def fehler(self, message):
        raise _Fehler(f"{self.prog}: {message}")

    gelockert = []
    if nur_schalter:
        def lockern(p):
            for a in p._actions:
                if a.required:
                    gelockert.append(a)
                    a.required = False
                if isinstance(a, argparse._SubParsersAction):
                    for sub in a.choices.values():
                        lockern(sub)
        lockern(parser)
    argparse.ArgumentParser._get_value = roh
    argparse.ArgumentParser._check_value = auswahl
    argparse.ArgumentParser.error = fehler
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            if nur_schalter:
                _, rest = parser.parse_known_args(argv)
                unbekannt = [r for r in rest if r.startswith("-")]
                if unbekannt:
                    raise _Fehler(f"{parser.prog}: unbekannte Schalter {unbekannt}")
            else:
                parser.parse_args(argv)
    finally:
        argparse.ArgumentParser._get_value = get_value
        argparse.ArgumentParser._check_value = check_value
        argparse.ArgumentParser.error = error
        for a in gelockert:
            a.required = True


def varianten(argumente: List[str]) -> Tuple[List[List[str]], bool]:
    """Die zu pruefenden Argumentlisten und ob eine Auslassung vorliegt.
    Klammern ``[ ]`` entfallen (der Inhalt wird mitgeprueft); ``a|b`` wird je
    Alternative geprueft (ausser in Platzhaltern)."""
    # ``...`` direkt nach einem Schalter ist dessen Wert (``--grund ...``),
    # sonst eine Auslassung weiterer Angaben.
    roh: List[str] = []
    auslassung = False
    for a in argumente:
        if a in ("...]", "…]"):
            continue                       # Wiederholung: ``[--x <wert> ...]``
        if a in ("...", "…"):
            if roh and roh[-1].startswith("-"):
                roh.append("<...>")
            else:
                auslassung = True
            continue
        roh.append(a)
    roh = [a.strip("[]") for a in roh]
    roh = [a for a in roh if a]
    alternativen = [i for i, a in enumerate(roh)
                    if "|" in a and not _ist_platzhalter(a) and not a.startswith("-")]
    if not alternativen:
        return [roh], auslassung
    i = alternativen[0]
    aus: List[List[str]] = []
    for wahl in roh[i].split("|"):
        rest, _ = varianten(roh[:i] + [wahl] + roh[i + 1:])
        aus.extend(rest)
    return aus, auslassung


def pruefe(k: Kommando) -> Optional[str]:
    """None = angenommen; sonst die Meldung des Parsers."""
    argumente = k.argumente
    try:
        parser = parser_von(k.modul)
    except (ImportError, AssertionError) as exc:
        return f"Modul {k.modul}: {exc}"
    if not argumente:
        return None                       # Nennung: Modul mit Parser genuegt
    listen, auslassung = varianten(argumente)
    # Nennung eines Unterbefehls (``... anfangsbestand belegen``) ohne jeden
    # Schalter: der Unterbefehl muss bekannt sein, Pflichtangaben nicht.
    auslassung = auslassung or not any(a.startswith("-") for a in argumente)
    for argv in listen:
        try:
            _parse(parser_von(k.modul), argv, nur_schalter=auslassung)
        except _Fehler as exc:
            return str(exc)
        except Exception as exc:          # eigene error() eines Parsers (Gate-Vertrag)
            return f"{type(exc).__name__}: {exc}"
    return None


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

KOMMANDOS = alle_kommandos()


def _ausgenommen(k: Kommando) -> bool:
    return (k.dokument, k.text) in AUSNAHMEN


@pytest.mark.parametrize("kommando", [k for k in KOMMANDOS if not _ausgenommen(k)], ids=str)
def test_jedes_woertliche_kommando_besteht_den_parser(kommando: Kommando) -> None:
    befund = pruefe(kommando)
    assert befund is None, f"{kommando}\n  -> {befund}"


def test_die_menge_ist_nicht_leer_und_die_ausnahmen_gibt_es() -> None:
    """Der Detektor sieht etwas (sonst waere Gruen leer), und jede Ausnahme
    trifft genau ein vorhandenes Kommando (== statt >=)."""
    assert len(KOMMANDOS) >= 50, len(KOMMANDOS)
    for (dok, text), grund in AUSNAHMEN.items():
        treffer = [k for k in KOMMANDOS if (k.dokument, k.text) == (dok, text)]
        assert len(treffer) == 1 and grund, (dok, text, len(treffer))
    assert sum(_ausgenommen(k) for k in KOMMANDOS) == len(AUSNAHMEN)


@pytest.mark.parametrize("text, erwartet", [
    # Positivkontrolle: der Befund aus H14 (ohne --linie) faellt ...
    ("python -m rechner_pipeline.betrieb.zugangsprobe --stand <ablage> --fall faelle/<fall> "
     "--stichtag <iso> --schluessel <s> --zeichnungsordnung <o> --freigabe-schluessel <f>",
     "--linie"),
    # ... ein unbekannter Schalter faellt ...
    ("python -m rechner_pipeline.gates.migrationssuite_lauf --gibt-es-nicht 1 ...",
     "--gibt-es-nicht"),
    # ... ein entfallener Tarifschalter faellt (sprechend) ...
    ("python -m rechner_pipeline.gates.migrationssuite_lauf --red-verfahren prospektiv ...",
     "entfaellt"),
    # ... ein unbekannter Unterbefehl faellt ...
    ("python -m rechner_pipeline.gates.stand_belegen gibtsnicht --linie <l>", "gibtsnicht"),
    # ... eine unzulaessige Alternative faellt ...
    ("python -m rechner_pipeline.gates.aktuartest --abnahme A-M1|A-M9 ...", "A-M9"),
    # ... und der Aufruf aus deploy/plv/README.md besteht.
    ("python -m rechner_pipeline.betrieb.zugangsprobe --stand ~/apps/plv/daten "
     "--fall faelle/<fall> --stichtag 2026-01-01 [--bis <ISO>] "
     "--freigabe-schluessel <v> --freigabe-schluessel <a> --schluessel <b> "
     "--zeichnungsordnung <o> --linie ~/apps/plv/linie", None),
])
def test_positivkontrolle_der_detektor_faellt_was_falsch_ist(text: str, erwartet: Optional[str]) -> None:
    befund = pruefe(Kommando("kontrolle", 1, text))
    if erwartet is None:
        assert befund is None, befund
    else:
        assert befund is not None and erwartet in befund, befund


def test_die_extraktion_findet_codeblock_und_spanne_ueber_zeilen(tmp_path: Path) -> None:
    """Die Extraktion ist selbst Mechanik: Fortsetzungszeilen im Codeblock,
    eine Inline-Spanne ueber einen Zeilenumbruch, und nichts ausserhalb."""
    dok = tmp_path / "x.md"
    dok.write_text(
        "Text `python -m\n  rechner_pipeline.a.b --x\n  <y>` weiter.\n\n"
        "```\npython -m rechner_pipeline.c.d \\\n    --e <f>\n```\n"
        "`python -m pytest` und `rechner_pipeline.e` sind keine.\n\n"
        "`python -m pytest $(git diff | python -m rechner_pipeline.g.h | x)`\n",
        encoding="utf-8")
    gefunden = [(k.zeile, k.text) for k in kommandos_aus("x.md", tmp_path)]
    assert gefunden == [(1, "python -m rechner_pipeline.a.b --x <y>"),
                        (6, "python -m rechner_pipeline.c.d --e <f>"),
                        (11, "python -m rechner_pipeline.g.h")], gefunden
