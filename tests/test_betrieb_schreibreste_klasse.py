"""Schreibreste als Klasse — Runde E, Klasse D geschlossen.

Runde D, Fund 6: Ein Prozesstod zwischen dem Schreiben der Tempdatei und
dem Umhaengen liess ``.<ziel>.<zufall>.tmp`` fuer immer in der Ablage
liegen, beim exklusiven Abschluss als Hardlink-Zwilling der 0444-Datei.
Der Fix zaehlte vier Namensmuster im Aufraeumen auf. Das Arbeitsverzeichnis,
das Laufmanifest und die vorbereitete Seite fehlten — und der naechste
Schreiber haette ebenso gefehlt.

Die Invariante: Jede Punkt-Tempdatei eines Ziels, das der Tageslauf oder
der Render der Seite unter der Ablage atomar schreibt, entfernt der naechste
Lauf unter der Lauf-Sperre, ohne je ein Ziel, eine Nicht-Punktdatei oder ein
Verzeichnis anzufassen; ein Hardlink-Zwilling verschwindet, das Ziel behaelt
einen Namen.

Die Menge ist EINE Aussage im Code: ``tageslauf.SCHREIBZIELE``. Jeder
Schreiber nimmt seinen Zielpfad durch ``tageslauf.schreibziel`` (nur, was in
der Tabelle steht), und ``_raeume_schreibreste`` raeumt genau die Tabelle.
Drei Instrumente halten das fest:

* Ratsche (statisch, AST): findet jede Schreibstelle, die eine Tempdatei
  anlegt oder an einen solchen Schreiber weiterreicht, und verlangt, dass
  sie ihr Ziel durch ``schreibziel`` nimmt (ein Export-Ziel durch
  ``seite.ausserhalb_der_ablage``) — mit == gegen die benannten Ausnahmen,
  je AUFRUFSTELLE und mit Anzahl, ueber die transitive Importhuelle von
  betrieb (Runde E, Nachbesserung: vorher je Funktion und eine Stufe weit).
* Zaehltest (dynamisch): je Eintrag der Tabelle ein Rest, ein Lauf, danach
  kein Rest; dazu ein Spion am gemeinsamen ``os.open``-Weg der Primitive
  ueber einen echten Lauf, der jede angelegte Tempdatei einem Eintrag
  zuordnet (== in beide Richtungen). Dazu das Staging der Registrierung
  (``uebernahme.neu/<fall>/``): Jede Form eines verwaisten Verzeichnisses
  raeumt der naechste Lauf, ein registrierter Eingang bleibt byte-gleich.
* Mutationsprobe je Eintrag: das Aufraeumen genau eines Eintrags
  zuruecknehmen, genau dieser Fall wird rot.

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import datetime as dt
import fnmatch
import hashlib
import os
import re
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

import pytest

from rechner_pipeline.bestand import parquet_io
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from tests.test_betrieb_seite import _ablage

SRC = Path(tl.__file__).resolve().parents[2]
PAKET = SRC / "rechner_pipeline"

#: Die Primitive, die eine Tempdatei ``.<ziel>.<zufall>.tmp`` anlegen.
PRIMITIVE = frozenset({"neue_datei", "mkstemp", "schreibe_exklusiv"})

#: Die Bindungen eines Zielpfads: ``schreibziel`` gibt nur ein Ziel aus
#: ``tageslauf.SCHREIBZIELE`` frei (dessen Rest der Lauf raeumt),
#: ``ausserhalb_der_ablage`` nur ein Ziel AUSSERHALB der Ablage (Export).
BINDUNGEN = frozenset({"schreibziel", "ausserhalb_der_ablage"})

#: Schreibstellen, die ihr Ziel NICHT binden — je AUFRUFSTELLE
#: (Funktion, gerufener Name, Zielausdruck), mit Grund (Runde E,
#: Nachbesserung: vorher je Funktion, und ein zweiter Aufruf in einer
#: ausgenommenen Funktion fiel keinem Instrument auf). Die Ratsche
#: vergleicht die ANZAHL je Stelle mit ==.
#:
#: Durchreicher bekommen den Zielpfad als Parameter; ihre Aufrufer prueft
#: die Ratsche (die Funktion wird selbst ein Schreiber).
DURCHREICHER = {
    ("rechner_pipeline.bestand.parquet_io.write_portfolio", "neue_datei",
     "path.parent, path.name"): "Ziel ist Parameter",
    ("rechner_pipeline.bestand.abschluss.schreibe_abschluss", "write_portfolio",
     "df, pfad, exklusiv=True"): "Verzeichnis ist Parameter",
    ("rechner_pipeline.bestand.manifest.schreibe_manifest", "neue_datei",
     "lauf, ziel.name"): "Laufverzeichnis ist Parameter",
    ("rechner_pipeline.betrieb.tageslauf._bericht", "neue_datei",
     "ziel.parent, ziel.name"): "Ziel ist Parameter",
    ("rechner_pipeline.betrieb.tageslauf._schreibe_json_atomar", "mkstemp",
     "dir=pfad.parent, prefix=f'.{pfad.name}.', suffix='.tmp'"): "Ziel ist Parameter",
    ("rechner_pipeline.betrieb.seite._schreibe", "neue_datei",
     "ziel.parent, ziel.name"): "Ziel ist Parameter",
    # Pruefrunde H, H17: der Schreiber des Anfangsbestands nimmt das Primitiv
    # des Betriebs und raeumt die Reste seines Ziels selbst
    # (tageslauf.raeume_schreibreste_von); sein Ziel liegt im Linienbereich.
    ("rechner_pipeline.betrieb.anfangsbestand._schreibe", "neue_datei",
     "ziel.parent, ziel.name"): "Ziel ist Parameter",
    # Die Gate-Belege (gates._common, ueber models.schemas erreicht): Das
    # Ledger-Verzeichnis kommt vom Aufrufer; ein Aufruf aus betrieb oder
    # bestand mit einem Ziel in der Ablage waere eine neue Stelle.
    ("rechner_pipeline.gates._common.write_gate_ledger", "mkstemp",
     "prefix=f'.{out_path.name}.', suffix='.tmp', dir=diag_dir"): "Ledger-Verzeichnis ist Parameter",
    ("rechner_pipeline.gates._common.begin_gate_ledger_attempt", "write_gate_ledger",
     "marker, attempt.diagnostics_dir, repo_root=attempt.repo_root, attempt=attempt.versuch, "
     "started_at=attempt.started_at, ended_at=utc_now(), command_line=attempt.command_line"):
        "Ledger-Verzeichnis aus dem Kontext des Gates",
    ("rechner_pipeline.gates._common.finalize_gate_ledger", "write_gate_ledger",
     "result, attempt.diagnostics_dir, repo_root=attempt.repo_root, attempt=attempt.versuch, "
     "started_at=attempt.started_at, ended_at=utc_now(), command_line=attempt.command_line"):
        "Ledger-Verzeichnis aus dem Kontext des Gates",
    ("rechner_pipeline.gates._common._argument_error_result", "begin_gate_ledger_attempt",
     "command=command, gate=gate, gate_version=contract.gate_version, "
     "diagnostics_dir=diagnostics_dir, repo_root=Path(repo_root_raw) if (repo_root_raw := "
     "_argument_value(error, argv, 'repo_root')) else None, "
     "command_line=_redact_argv(argv, contract.sensitive_options)"):
        "Ledger-Verzeichnis aus den Argumenten des Gates",
    ("rechner_pipeline.gates._common._argument_error_result", "finalize_gate_ledger",
     "result"): "Ledger-Verzeichnis aus dem Kontext des Gates",
    ("rechner_pipeline.gates._common.run_command", "_argument_error_result",
     "exc, command_argv"): "Ledger-Verzeichnis aus den Argumenten des Gates",
}
#: Stellen, deren Rest ein anderer Weg raeumt. Ihre Funktion wird dadurch
#: KEIN Schreiber. Die Registrierung baut unter ``uebernahme.neu/<fall>/``
#: unter der Lauf-Sperre; der Rest ist das ganze Verzeichnis, das der
#: naechste Tageslauf entfernt (``tageslauf._raeume_uebernahme_staging``).
_STAGING = ("Staging uebernahme.neu/<fall>: der naechste Tageslauf raeumt das "
            "verwaiste Verzeichnis unter der Lauf-Sperre")
AUSSERHALB = {
    ("rechner_pipeline.betrieb.uebernahme.eingang_anlegen", "write_portfolio",
     "_umnummeriert(tabelle, abbildung, datei), arbeit / datei"): _STAGING,
    ("rechner_pipeline.betrieb.uebernahme.eingang_anlegen", "write_portfolio",
     "uebersetzung, arbeit / POLICENNUMMERN_DATEI"): _STAGING,
    # Der Beleg des Anfangsbestands und seine Sicht liegen im LINIENBEREICH
    # (ADR-025), nicht in der Ablage: Kein Lauf der Ablage raeumt dort;
    # ``_schreibe`` raeumt die Reste seines Ziels vor dem Schreiben selbst
    # (Pruefrunde H, H17). ``main`` reicht die Linie durch.
    ("rechner_pipeline.betrieb.anfangsbestand.belegen", "_schreibe",
     "Path(linie) / ab.BELEG_RELATIV, roh"): "Ziel im Linienbereich",
    ("rechner_pipeline.betrieb.anfangsbestand.belegen", "_schreibe",
     "Path(linie) / ab.SICHT_RELATIV, sicht"): "Ziel im Linienbereich",
}
#: Eine Stelle, die GENAU so zweimal in ihrer Funktion steht (die Ratsche
#: vergleicht die Anzahl): ``run_command`` schliesst das Ledger auf zwei Wegen.
ZWEIMAL = {
    ("rechner_pipeline.gates._common.run_command", "finalize_gate_ledger", "result"):
        "Ledger-Verzeichnis aus dem Kontext des Gates",
}


# --------------------------------------------------------------------------- #
# Ratsche (statisch)
# --------------------------------------------------------------------------- #


def _modulname(pfad: Path) -> str:
    teile = pfad.relative_to(SRC).with_suffix("").parts
    return ".".join(teile[:-1] if teile[-1] == "__init__" else teile)


def _moduldatei(modul: str):
    basis = SRC / modul.replace(".", "/")
    for datei in (basis.with_suffix(".py"), basis / "__init__.py"):
        if datei.is_file():
            return datei
    return None


def _eigenes_paket(name: str) -> bool:
    return name == "rechner_pipeline" or name.startswith("rechner_pipeline.")


def _quellen() -> dict:
    """betrieb/*.py und jedes Modul des Pakets, das betrieb DIREKT ODER
    INDIREKT importiert — die transitive Huelle, aus den Importen
    hergeleitet, nicht aufgezaehlt (Runde E, Nachbesserung).

    WARUM transitiv: Die erste Fassung ging eine Stufe weit und nur ueber
    ``from x import y``. ``gates._common.write_gate_ledger`` schreibt ueber
    ``mkstemp``; betrieb erreicht das Modul nur ueber ``models.schemas`` —
    ein Schreiber in ``bestand/report.py`` ueber diesen Helfer blieb
    unsichtbar (Probe A des Pruefers). Gefolgt wird jeder Form: ``import
    x``, ``from x import y`` (auch ``y`` als Untermodul), relative Importe,
    Importe in Funktionen, und die Pakete (``__init__``), die ein Import
    ausfuehrt. Die Gegenprobe ist dynamisch
    (``test_quellen_der_ratsche_sind_transitiv_geschlossen``).
    """
    def lies(modul):
        datei = _moduldatei(modul)
        return None if datei is None else (datei.read_text(encoding="utf-8"),
                                           datei.name == "__init__.py")

    return _huelle([_modulname(p) for p in sorted((PAKET / "betrieb").glob("*.py"))], lies)


def _huelle(start, lies) -> dict:
    """Die transitive Importhuelle von ``start`` im eigenen Paket.
    ``lies(modul)``: ``(text, ist_paket)`` oder None, wenn ``modul`` kein
    Modul ist (ein Name AUS einem Modul)."""
    offen, module = list(start), {}
    while offen:
        modul = offen.pop()
        gelesen = None if modul in module else lies(modul)
        if gelesen is None:
            continue   # schon gesehen, oder ein Name aus einem Modul, kein Modul
        text, ist_paket = gelesen
        module[modul] = text
        teile = modul.split(".")
        offen += [".".join(teile[:i]) for i in range(1, len(teile))]
        for knoten in ast.walk(ast.parse(text)):
            if isinstance(knoten, ast.Import):
                offen += [a.name for a in knoten.names if _eigenes_paket(a.name)]
            elif isinstance(knoten, ast.ImportFrom):
                if knoten.level:
                    paket = teile if ist_paket else teile[:-1]
                    basis = paket[:len(paket) - knoten.level + 1]
                    name = ".".join(basis + ([knoten.module] if knoten.module else []))
                else:
                    name = knoten.module or ""
                if _eigenes_paket(name):
                    offen += [name] + [f"{name}.{a.name}" for a in knoten.names]
    return module


def _funktionen(baum: ast.Module):
    for knoten in baum.body:
        if isinstance(knoten, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield knoten.name, knoten
        elif isinstance(knoten, ast.ClassDef):
            for f in knoten.body:
                if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{knoten.name}.{f.name}", f


def _gerufen(aufruf: ast.Call):
    f = aufruf.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def _gebunden(aufruf: ast.Call) -> bool:
    """Nimmt der Aufruf sein Ziel durch eine der :data:`BINDUNGEN`?"""
    for arg in [*aufruf.args, *(k.value for k in aufruf.keywords)]:
        if any(isinstance(n, ast.Call) and _gerufen(n) in BINDUNGEN for n in ast.walk(arg)):
            return True
    return False


def _zielausdruck(aufruf: ast.Call) -> str:
    """Die Argumente der Stelle, wie sie im Quelltext stehen (normalisiert)."""
    return ", ".join([ast.unparse(a) for a in aufruf.args] + [
        f"{k.arg}={ast.unparse(k.value)}" if k.arg else f"**{ast.unparse(k.value)}"
        for k in aufruf.keywords])


def ungebundene_schreibstellen(quellen: dict, ausserhalb=frozenset(AUSSERHALB)) -> Counter:
    """Jede AUFRUFSTELLE (Funktion, gerufener Name, Zielausdruck), die ein
    Primitiv oder einen Schreiber aufruft, ohne ihr Ziel zu binden — mit
    ihrer Anzahl. Eine Funktion mit einer solchen Stelle ist selbst ein
    Schreiber (Fixpunkt), ausser die Stelle steht in ``ausserhalb``.

    Statisch und ueber Kurznamen: ein Name, der hier als Schreiber gilt,
    gilt es in jedem Modul. Das ist eine Ueberdeckung, keine Luecke — ein
    Fehlalarm faellt als Abweichung vom == unten auf.
    """
    aufrufe = {}
    for modul, text in quellen.items():
        for name, f in _funktionen(ast.parse(text)):
            aufrufe[f"{modul}.{name}"] = (
                name.split(".")[-1],
                [(_gerufen(c), _gebunden(c), _zielausdruck(c))
                 for c in ast.walk(f) if isinstance(c, ast.Call)],
            )
    schreiber = set(PRIMITIVE)
    while True:
        neu = {kurz for qual, (kurz, calls) in aufrufe.items()
               if any(n in schreiber and not g and (qual, n, z) not in ausserhalb
                      for n, g, z in calls)}
        if neu <= schreiber:
            break
        schreiber |= neu
    return Counter((qual, n, z) for qual, (_, calls) in aufrufe.items()
                   for n, g, z in calls if n in schreiber and not g)


def test_ratsche_jede_schreibstelle_bindet_ihr_ziel():
    """Statische Ratsche (Runde E, Klasse D geschlossen; Nachbesserung: je
    Aufrufstelle): Die ungebundenen Schreibstellen sind GENAU die benannten
    Durchreicher und Stellen ausserhalb der Aufraeumung, jede genau einmal.
    Eine neue Stelle ``write_portfolio(x, ablage.journal / "neu.parquet")``
    — auch in einer Funktion, die schon eine Ausnahme traegt — ist ein
    Eintrag mehr und die Ratsche rot. Ausweg: ``schreibziel(ablage, ...)``
    und ein Eintrag in ``tageslauf.SCHREIBZIELE`` — dann raeumt der Lauf
    ihren Rest; ein Export-Ziel nimmt ``seite.ausserhalb_der_ablage``.
    Mutationsprobe: eine Bindung an einer Aufrufstelle entfernen -> rot."""
    erwartet = Counter({**DURCHREICHER, **AUSSERHALB}.keys()) + Counter({k: 2 for k in ZWEIMAL})
    assert ungebundene_schreibstellen(_quellen()) == erwartet


def test_ratsche_positivkontrolle_findet_den_vergessenen_schreiber():
    """Die Ratsche sieht einen neuen Schreiber, direkt und ueber einen
    Durchreicher; ein gebundener Schreiber bleibt still."""
    quellen = _quellen()
    probe = (
        "def neu(ablage, df):\n"
        "    write_portfolio(df, ablage.journal / 'neu.parquet')\n"
        "def _helfer(ziel):\n"
        "    neue_datei(ziel.parent, ziel.name)\n"
        "def lauf(ablage):\n"
        "    _helfer(ablage.wurzel / 'x.json')\n"
        "def gebunden(ablage, df):\n"
        "    write_portfolio(df, schreibziel(ablage, ablage.journal / 'neu.parquet'))\n"
        "def export(ablage, ziel):\n"
        "    _schreibe(ausserhalb_der_ablage(ablage, ziel / 'x.json'), '')\n"
    )
    gefunden = ungebundene_schreibstellen({**quellen, "probe": probe})
    assert gefunden - ungebundene_schreibstellen(quellen) == Counter({
        ("probe.neu", "write_portfolio", "df, ablage.journal / 'neu.parquet'"): 1,
        ("probe._helfer", "neue_datei", "ziel.parent, ziel.name"): 1,
        ("probe.lauf", "_helfer", "ablage.wurzel / 'x.json'"): 1,
    })


# --------------------------------------------------------------------------- #
# schreibziel: fail-fast mit Ausweg
# --------------------------------------------------------------------------- #


def _beispielname(muster: str) -> str:
    return muster.replace("*", "probe")


@pytest.mark.parametrize("eintrag", tl.SCHREIBZIELE, ids=lambda e: f"{e[0]}/{e[1]}")
def test_schreibziel_gibt_jeden_eintrag_frei(tmp_path, eintrag):
    ablage = Ablage(tmp_path / "plv")
    pfad = ablage.wurzel / eintrag[0] / _beispielname(eintrag[1])
    assert tl.schreibziel(ablage, pfad) == pfad


@pytest.mark.parametrize("relativ", [
    "journal/neu.parquet",            # bekanntes Verzeichnis, fremder Name
    "seite/index.html",               # der Name, aber das falsche Verzeichnis
    "abschluesse/sub/abschluss_x.parquet",  # nicht unmittelbar im Verzeichnis
    "../publish.json",                # ausserhalb der Wurzel
])
def test_schreibziel_verweigert_ein_ziel_ausserhalb_der_tabelle(tmp_path, relativ):
    ablage = Ablage(tmp_path / "plv")
    with pytest.raises(tl.TageslaufError, match="kein Schreibziel der Ablage") as fehler:
        tl.schreibziel(ablage, ablage.wurzel / relativ)
    assert "Ausweg" in str(fehler.value) and "SCHREIBZIELE" in str(fehler.value)


# --------------------------------------------------------------------------- #
# Zaehltest (dynamisch)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def ein_tag(tmp_path_factory):
    """Ein gruener Lauf (31.1.) — der 3.2. danach schreibt Abschluss und Bericht."""
    ablage = _ablage(tmp_path_factory.mktemp("sr") / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    return ablage.wurzel


@pytest.fixture(scope="module")
def zwei_tage(ein_tag, tmp_path_factory):
    wurzel = tmp_path_factory.mktemp("sr2") / "plv"
    shutil.copytree(ein_tag, wurzel, symlinks=True)
    assert tageslauf(Ablage(wurzel), dt.date(2026, 2, 3))[0] == EXIT_OK
    return wurzel


def _kopie(quelle: Path, ziel: Path) -> Ablage:
    shutil.copytree(quelle, ziel, symlinks=True)
    return Ablage(ziel)


_TEMP = re.compile(r"^\.(?P<ziel>.+)\.[^.]+\.tmp$")


def _eintrag_von(wurzel: Path, tmp: Path):
    """Der Eintrag von SCHREIBZIELE, zu dem eine Tempdatei gehoert (oder None)."""
    treffer = _TEMP.match(tmp.name)
    if not treffer:
        return None
    for relativ, muster in tl.SCHREIBZIELE:
        if (tmp.parent == wurzel / relativ
                and fnmatch.fnmatchcase(treffer.group("ziel"), muster)):
            return (relativ, muster)
    return None


def _spion_tempdateien(monkeypatch) -> list:
    """Jede Datei, die exklusiv neu angelegt wird (Liste, waechst mit).

    Runde E, Nachbesserung: gespaeht wird am GEMEINSAMEN Weg der drei
    Primitive — ``os.open`` mit ``O_CREAT | O_EXCL``. ``neue_datei``,
    ``tempfile.mkstemp`` und ``gates._common.schreibe_exklusiv`` legen ihre
    Tempdatei alle so an; die erste Fassung ersetzte nur ``neue_datei`` und
    ``mkstemp`` und hoerte ``schreibe_exklusiv`` nicht. Ein neues Primitiv
    auf demselben Weg hoert der Spion ohne Eintrag hier.
    """
    angelegt = []
    echtes_open = os.open
    exklusiv = os.O_CREAT | os.O_EXCL

    def spion_open(pfad, flags, *args, **kwargs):
        fd = echtes_open(pfad, flags, *args, **kwargs)
        if flags & exklusiv == exklusiv:
            angelegt.append(Path(os.fsdecode(pfad)))
        return fd

    monkeypatch.setattr(os, "open", spion_open)
    return angelegt


def test_spion_hoert_jedes_primitiv(tmp_path, monkeypatch):
    """Positivkontrolle des Spions (Runde E, Nachbesserung): Er hoert alle
    drei Primitive ab, auch ``gates._common.schreibe_exklusiv``, das seine
    Tempdatei selbst mit ``os.open`` anlegt. Vorher sah er nur
    ``neue_datei`` und ``mkstemp`` — ein Schreiber ueber schreibe_exklusiv
    in der Ablage waere dem Zaehltest entgangen."""
    from rechner_pipeline.gates import _common

    angelegt = _spion_tempdateien(monkeypatch)
    parquet_io.neue_datei(tmp_path, "a")
    os.close(tempfile.mkstemp(prefix=".b.", suffix=".tmp", dir=tmp_path)[0])
    _common.schreibe_exklusiv(tmp_path / "c", b"c")
    assert sorted(p.name.split(".")[1] for p in angelegt) == ["a", "b", "c"]
    assert all(p.parent == tmp_path for p in angelegt)


def test_jede_tempdatei_eines_echten_laufs_gehoert_zu_einem_schreibziel(ein_tag, tmp_path, monkeypatch):
    """Spion ueber einen echten Lauf mit Abschluss, Bericht, Journal, Marker,
    Stand und Seite: Jede Tempdatei, die unter der Ablage entsteht, gehoert
    zu einem Eintrag von SCHREIBZIELE, und jeder Eintrag wird gebraucht (==).
    Gespaeht wird am gemeinsamen Weg der Primitive (``os.open`` exklusiv,
    Runde E, Nachbesserung) — nicht an einer Liste von Schreibern.
    Mutationsprobe: einen Eintrag aus SCHREIBZIELE streichen -> rot (der
    Lauf verweigert sein Ziel)."""
    ablage = _kopie(ein_tag, tmp_path / "plv")
    angelegt = _spion_tempdateien(monkeypatch)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert code == EXIT_OK and zeile["uebernommen"] is True
    wurzel = ablage.wurzel
    unter_der_ablage = [p for p in angelegt if wurzel in p.parents]
    assert unter_der_ablage, "der Spion sah keine Tempdatei — er misst nichts"
    ohne_eintrag = [str(p.relative_to(wurzel)) for p in unter_der_ablage
                    if _eintrag_von(wurzel, p) is None]
    assert ohne_eintrag == []
    assert {_eintrag_von(wurzel, p) for p in unter_der_ablage} == set(tl.SCHREIBZIELE)


def _zielname(ort: Path, muster: str) -> str:
    vorhanden = sorted(p.name for p in ort.glob(muster)
                       if p.is_file() and not p.name.startswith("."))
    return vorhanden[0] if vorhanden else _beispielname(muster)


def _alle_tempreste(wurzel: Path) -> set:
    return {str(p.relative_to(wurzel)) for p in wurzel.rglob(".*.tmp")}


@pytest.mark.parametrize("eintrag", tl.SCHREIBZIELE, ids=lambda e: f"{e[0]}/{e[1]}")
def test_der_naechste_lauf_raeumt_den_rest_jedes_schreibziels(zwei_tage, tmp_path, eintrag):
    """Je Eintrag von SCHREIBZIELE: ein halb geschriebener Rest, bei Parquet
    zusaetzlich ein Hardlink-Zwilling des Ziels, daneben fremde Namen, die
    stehen bleiben muessen (``.gitkeep``, eine Punktdatei ohne ``.tmp``, eine
    Nicht-Punktdatei mit ``.tmp``, ein VERZEICHNIS im Muster). Gefahren wird
    die Wiederholung des gefuehrten Tags: Sie schreibt nichts, also misst der
    Test nur das Aufraeumen — ein neuer Tag verwirft ``stand.neu`` ohnehin.
    Mutationsprobe je Eintrag: ihn in ``_raeume_schreibreste`` ueberspringen
    -> genau dieser Fall rot."""
    relativ, muster = eintrag
    ablage = _kopie(zwei_tage, tmp_path / "plv")
    ort = ablage.wurzel / relativ
    ort.mkdir(parents=True, exist_ok=True)
    zielname = _zielname(ort, muster)
    ziel = ort / zielname
    rest = ort / f".{zielname}.00ff00ff00ff00ff.tmp"
    rest.write_bytes(b"halb")
    zwilling = None
    if zielname.endswith(".parquet"):
        if not ziel.exists():
            ziel.write_bytes(b"PAR1")
        zwilling = ort / f".{zielname}.feedfacecafebeef.tmp"
        os.link(ziel, zwilling)
        assert ziel.stat().st_nlink == 2
    fremd = [ort / ".gitkeep", ort / f".{zielname}.00ff.bak", ort / f"{zielname}.00ff.tmp"]
    for p in fremd:
        p.write_bytes(b"fremd")
    verzeichnis = ort / f".{zielname}.0d0d0d0d.tmp"
    verzeichnis.mkdir()
    assert _alle_tempreste(ablage.wurzel) >= {str(rest.relative_to(ablage.wurzel))}

    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert (code, zeile.get("bereits_gefuehrt")) == (EXIT_OK, True)
    assert _alle_tempreste(ablage.wurzel) == {str(verzeichnis.relative_to(ablage.wurzel))}
    assert verzeichnis.is_dir()
    assert all(p.read_bytes() == b"fremd" for p in fremd)
    if zwilling is not None:
        assert not zwilling.exists() and ziel.stat().st_nlink == 1


def _abbild(wurzel: Path) -> dict:
    return {str(p.relative_to(wurzel)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(wurzel.rglob("*")) if p.is_file() and not p.is_symlink()}


def test_positivkontrolle_ohne_reste_fasst_das_aufraeumen_nichts_an(zwei_tage, tmp_path):
    """Die unveraenderte Welt: ein gefuehrter Tag ohne Rest. Nach der
    Wiederholung steht jede Datei der Ablage mit denselben Bytes da, und es
    gibt keine Tempdatei — das Aufraeumen nimmt nur, was ein Rest ist.
    Die erste Wiederholung raeumt den verwaisten Stand des Vortags (eine
    andere Aufraeumung, ``_verwaiste_staende_entfernen``); gemessen wird
    die zweite."""
    ablage = _kopie(zwei_tage, tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    vorher = _abbild(ablage.wurzel)
    assert _alle_tempreste(ablage.wurzel) == set()
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert (code, zeile.get("bereits_gefuehrt")) == (EXIT_OK, True)
    assert _abbild(ablage.wurzel) == vorher


# --------------------------------------------------------------------------- #
# Runde E, Nachbesserung: Ausnahmen je Aufrufstelle, Quellen transitiv,
# Spion am gemeinsamen os.open-Weg, Staging der Uebernahme
# --------------------------------------------------------------------------- #


def _mutiert(quellen: dict, modul: str, anker: str, einschub: str) -> dict:
    text = quellen[modul]
    assert text.count(anker) == 1, f"Anker {anker!r} nicht eindeutig in {modul}"
    return {**quellen, modul: text.replace(anker, einschub + anker)}


def test_ratsche_sieht_eine_zweite_schreibstelle_in_einer_ausgenommenen_funktion():
    """Probe C des Pruefers (Runde E): Die Ausnahmen galten je FUNKTION —
    ein zweiter, ungebundener Aufruf in einer schon ausgenommenen Funktion
    fiel keinem Instrument auf. Jetzt zaehlt die Ratsche Aufrufstellen
    (Funktion, gerufener Name, Zielausdruck)."""
    quellen = _quellen()
    modul = "rechner_pipeline.betrieb.seite"
    mutiert = _mutiert(
        quellen, modul, "    (ziel / PAKET_BAU_MARKER).unlink()\n",
        "    _schreibe(ablage.journal / 'letzter_export.json', '{}')\n")
    neu = ungebundene_schreibstellen(mutiert) - ungebundene_schreibstellen(quellen)
    assert (f"{modul}._stands_paket_unter_sperre", "_schreibe",
            "ablage.journal / 'letzter_export.json', '{}'") in neu


def test_ratsche_zaehlt_dieselbe_aufrufstelle_zweimal():
    """Eine Ausnahme deckt GENAU eine Stelle: Derselbe Aufruf ein zweites
    Mal in derselben Funktion ist eine Stelle mehr (== auf die Anzahl)."""
    quellen = _quellen()
    modul = "rechner_pipeline.betrieb.uebernahme"
    stelle = "        write_portfolio(uebersetzung, arbeit / POLICENNUMMERN_DATEI)\n"
    mutiert = _mutiert(quellen, modul, stelle, stelle)
    neu = ungebundene_schreibstellen(mutiert) - ungebundene_schreibstellen(quellen)
    assert neu == {(f"{modul}.eingang_anlegen", "write_portfolio",
                    "uebersetzung, arbeit / POLICENNUMMERN_DATEI"): 1}


def test_ratsche_sieht_einen_schreiber_ueber_einen_indirekt_importierten_helfer():
    """Probe A des Pruefers (Runde E): ``gates._common.write_gate_ledger``
    schreibt ueber ``mkstemp``; betrieb importiert gates._common nur
    INDIREKT (ueber models.schemas). Die Quellen der Ratsche reichten eine
    Importstufe weit und kannten den Schreiber nicht — ein neuer Aufruf in
    bestand/report.py blieb unsichtbar."""
    quellen = _quellen()
    assert "rechner_pipeline.gates._common" in quellen
    modul = "rechner_pipeline.bestand.report"
    mutiert = {**quellen, modul: quellen[modul] + (
        "\n\ndef _probe_beleg(ablage, ergebnis):\n"
        "    write_gate_ledger(ergebnis, ablage.berichte)\n")}
    neu = ungebundene_schreibstellen(mutiert) - ungebundene_schreibstellen(quellen)
    assert (f"{modul}._probe_beleg", "write_gate_ledger", "ergebnis, ablage.berichte") in neu



def test_ausserhalb_der_ablage_gibt_nur_ziele_ausserhalb_frei(tmp_path):
    """Die zweite Bindung (Runde E, Nachbesserung): Ein Export-Ziel in der
    Ablage — direkt, in der Wurzel selbst oder ueber einen Link in sie —
    ist ein Fehler mit Ausweg, bevor die Tempdatei entsteht; ein Ziel
    daneben geht durch."""
    from rechner_pipeline.betrieb import seite

    ablage = Ablage(tmp_path / "plv")
    ablage.journal.mkdir(parents=True)
    (tmp_path / "link").symlink_to(ablage.journal, target_is_directory=True)
    for pfad in (ablage.journal / "x.json", ablage.wurzel / "x.json", tmp_path / "link" / "x.json"):
        with pytest.raises(seite.SeiteError, match="Ausweg") as fehler:
            seite.ausserhalb_der_ablage(ablage, pfad)
        assert "SCHREIBZIELE" in str(fehler.value)
    draussen = tmp_path / "paket" / "stand.json"
    assert seite.ausserhalb_der_ablage(ablage, draussen) == draussen


def test_huelle_folgt_jeder_importform():
    """Positivkontrolle der Huelle an einem erfundenen Paket: Jede Form
    fuehrt genau zu ihrem Modul — ``import x``, ``from x import y`` mit
    ``y`` als Untermodul (und als Name, der KEIN Modul ist), relative
    Importe aus Modul und Paket, ein Import in einer Funktion, die
    Elternpakete. Ein fremdes Paket und ein unerreichtes Modul bleiben
    draussen. Die echte Huelle braucht heute nicht jede Form; ohne diese
    Probe fiele eine kaputte Form erst beim naechsten Import auf."""
    rp = "rechner_pipeline"
    paket = {
        f"{rp}": ("", True),
        f"{rp}.a": ("", True),
        f"{rp}.a.start": (
            f"import {rp}.b.eins\n"
            f"from {rp}.c import zwei, NAME\n"
            "from . import nachbar\n"
            "import pandas\n"
            "def spaet():\n"
            f"    from {rp}.e.vier import x\n", False),
        f"{rp}.a.nachbar": ("from ..d import drei\n", False),
        f"{rp}.b": ("", True),
        f"{rp}.b.eins": ("", False),
        f"{rp}.c": ("NAME = 1\n", True),
        f"{rp}.c.zwei": ("", False),
        f"{rp}.d": ("from .fuenf import y\n", True),
        f"{rp}.d.drei": ("", False),
        f"{rp}.d.fuenf": ("", False),
        f"{rp}.e": ("", True),
        f"{rp}.e.vier": ("", False),
        f"{rp}.unerreicht": ("", False),
    }
    gefunden = _huelle([f"{rp}.a.start"], paket.get)
    assert set(gefunden) == set(paket) - {f"{rp}.unerreicht"}

def test_quellen_der_ratsche_sind_transitiv_geschlossen():
    """Dynamische Gegenprobe zur statischen Huelle: Jedes Modul des Pakets,
    das der Import aller betrieb-Module tatsaechlich laedt, steht in den
    Quellen der Ratsche. Gemessen in einem frischen Interpreter — im
    Testprozess haben andere Tests laengst mehr geladen."""
    import json as _json
    import subprocess

    betrieb = sorted(_modulname(p) for p in (PAKET / "betrieb").glob("*.py"))
    code = (
        "import importlib, json, sys\n"
        f"for m in {betrieb!r}:\n"
        "    importlib.import_module(m)\n"
        "print(json.dumps(sorted(m for m in sys.modules "
        "if m == 'rechner_pipeline' or m.startswith('rechner_pipeline.'))))\n")
    umgebung = {**os.environ, "PYTHONPATH": str(SRC)}
    lauf = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                          env=umgebung, check=True)
    geladen = set(_json.loads(lauf.stdout.strip().splitlines()[-1]))
    assert "rechner_pipeline.gates._common" in geladen   # Positivkontrolle
    assert geladen - set(_quellen()) == set()


@pytest.fixture(scope="module")
def mit_eingang(tmp_path_factory):
    """Eine Ablage mit REGISTRIERTEM Eingang und einem gruenen Lauf (9.1.)."""
    from rechner_pipeline.betrieb import uebernahme as ueb
    from tests.test_betrieb_uebernahme import STICHTAG, _fall, _mit_config

    basis = tmp_path_factory.mktemp("staging")
    stand = basis / "daten"
    ueb.eingang_anlegen(_mit_config(stand), _fall(basis), STICHTAG)
    assert tageslauf(Ablage(stand), dt.date(2026, 1, 9))[0] == EXIT_OK
    return stand


def _abbild_mit_modus(wurzel: Path) -> dict:
    return {str(p.relative_to(wurzel)): (p.stat().st_mode,
                                         hashlib.sha256(p.read_bytes()).hexdigest())
            for p in sorted(wurzel.rglob("*")) if p.is_file() and not p.is_symlink()}


def _staging_reste(staging: Path, eingang: Path) -> None:
    """Jede Form, die ein abgebrochenes Anlegen in ``uebernahme.neu/``
    hinterlaesst: mitten im ersten Schreiben (nur die Tempdatei), mitten in
    einer spaeteren Tabelle (0444-Tabellen und eine Tempdatei), vor dem
    Umbenennen (vollstaendig mit eingang.json) und gleich nach ``mkdir``."""
    rest = staging / "fall-x"
    rest.mkdir(parents=True)
    (rest / ".bestand.parquet.00ff00ff00ff00ff.tmp").write_bytes(b"halb")
    halb = staging / "fall-halb"
    halb.mkdir()
    shutil.copy2(eingang / "bestand.parquet", halb / "bestand.parquet")
    (halb / ".historie.parquet.feedfacecafebeef.tmp").write_bytes(b"halb")
    shutil.copytree(eingang, staging / "fall-fertig")
    assert (staging / "fall-fertig" / "eingang.json").stat().st_mode & 0o222 == 0
    (staging / "fall-leer").mkdir()


def test_der_naechste_lauf_raeumt_jedes_verwaiste_staging(mit_eingang, tmp_path):
    """Runde E, Nachbesserung: Die Registrierung eines Eingangs baut ihn
    unter ``uebernahme.neu/<fall>/`` und haengt ihn unter der LAUF-Sperre
    um. Ein Verzeichnis dort, das der Tageslauf unter der Sperre vorfindet,
    ist verwaist — samt der Tempdatei eines ``write_portfolio``, das mitten
    im Schreiben starb. Vorher raeumte es nur die naechste Registrierung
    DESSELBEN Falls; kam keine, lag der Rest fuer immer.

    Zaehltest ueber jede Form des Rests (auch 0444-Tabellen und eine
    fertige eingang.json): Nach dem Lauf steht kein Verzeichnis mehr in
    ``uebernahme.neu/``. Was die Registrierung dort nie anlegt, bleibt:
    ein Link nach draussen (samt Ziel) und eine Datei. Der registrierte
    Eingang unter ``uebernahme/`` bleibt byte- und modusgleich.
    Mutationsprobe: das Raeumen des Stagings zuruecknehmen -> rot."""
    from rechner_pipeline.betrieb import uebernahme as ueb

    ablage = _kopie(mit_eingang, tmp_path / "daten")
    [eingang] = [p for p in ablage.uebernahme.iterdir() if p.is_dir()]
    staging = ablage.wurzel / ueb.STAGING_DIR
    _staging_reste(staging, eingang)
    draussen = tmp_path / "draussen"
    (draussen / "fall-y").mkdir(parents=True)
    (draussen / "fall-y" / ".bestand.parquet.0a0a0a0a.tmp").write_bytes(b"fremd")
    (staging / "fall-link").symlink_to(draussen / "fall-y", target_is_directory=True)
    (staging / "notiz.txt").write_bytes(b"fremd")
    vorher = _abbild_mit_modus(ablage.uebernahme)
    assert len(vorher) >= 5

    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert (code, zeile.get("bereits_gefuehrt")) == (EXIT_OK, True)
    assert sorted(p.name for p in staging.iterdir()) == ["fall-link", "notiz.txt"]
    assert (draussen / "fall-y" / ".bestand.parquet.0a0a0a0a.tmp").read_bytes() == b"fremd"
    assert _abbild_mit_modus(ablage.uebernahme) == vorher


def test_eine_staging_wurzel_als_link_wird_nicht_verfolgt(mit_eingang, tmp_path):
    """``uebernahme.neu`` selbst als Link nach draussen: Der Lauf folgt ihm
    nicht — dort liegt nichts, was die Registrierung angelegt hat."""
    from rechner_pipeline.betrieb import uebernahme as ueb

    ablage = _kopie(mit_eingang, tmp_path / "daten")
    draussen = tmp_path / "draussen"
    (draussen / "fall-x").mkdir(parents=True)
    staging = ablage.wurzel / ueb.STAGING_DIR
    staging.rmdir()   # die Registrierung liess sie leer zurueck
    staging.symlink_to(draussen, target_is_directory=True)
    assert tageslauf(ablage, dt.date(2026, 1, 9))[0] == EXIT_OK
    assert (draussen / "fall-x").is_dir()


def test_ein_staging_mit_eingang_neben_seinem_eingang_wird_nicht_geloescht(mit_eingang, tmp_path):
    """Die zweite Sicherung der Registrierung, gespiegelt (T26-01): Traegt
    ein Staging-Verzeichnis eine eingang.json und steht unter
    ``uebernahme/`` ein Eingang desselben Namens, entscheidet kein Name,
    was ein Rest ist. Der Lauf verweigert mit Ausweg und loescht nichts.
    Mutationsprobe: ``ohne_marker`` weglassen -> rot."""
    from rechner_pipeline.betrieb import uebernahme as ueb

    ablage = _kopie(mit_eingang, tmp_path / "daten")
    [eingang] = [p for p in ablage.uebernahme.iterdir() if p.is_dir()]
    zwilling = ablage.wurzel / ueb.STAGING_DIR / eingang.name
    shutil.copytree(eingang, zwilling)
    with pytest.raises(tl.TageslaufError, match="Ausweg") as fehler:
        tageslauf(ablage, dt.date(2026, 1, 9))
    assert str(zwilling) in str(fehler.value)
    assert (zwilling / "eingang.json").is_file()
