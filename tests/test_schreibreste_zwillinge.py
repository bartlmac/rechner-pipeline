"""Ein Schreibrest liegt nie dauerhaft neben einem Beleg — auch nicht der Hardlink-Zwilling.

Befund der blinden Pruefrunde H (H16, niedrig): ``gates._common.schreibe_exklusiv``
haengt per ``os.link`` ein und entfernt danach die Tempdatei. Ein Prozessende
genau dazwischen laesst unter ``.<ziel>.<zufall>.tmp`` einen zweiten,
beschreibbaren Namen derselben Bytes liegen. Die Zusage "der naechste Aufruf
fuer dasselbe Ziel raeumt ihn weg" galt nur, wenn die Wiederholung das Ziel neu
schreibt — an vier gemessenen Stellen nicht: ``linie.json`` (Wiederholung
Exit 2), ein Glied der Ordnungslinie (``bereits_vorhanden``), das T-Box-Archiv
(liegt schon), der A-M5-Snapshot (danach endet jeder Aufruf an der Sperre des
Abbruchs).

Invariante: Jeder Aufruf, der einen Bereich betritt oder ein Ziel als "liegt
schon" erkennt, raeumt die Zwillinge dort — EINE Stelle
(``_common.raeume_zwillinge``), gerufen beim Eintritt; im Gate VOR der Sperre
des Abbruchs. Menge: jede Schreibstelle von ``schreibe_exklusiv`` im Paket
(Ratsche unten).

Der Ausfall wird hier als sein Ergebnis nachgestellt: ein Hardlink des
eingehaengten Belegs unter dem Tempnamen (``os.link``), wie ihn ein
Prozessende nach dem Einhaengen hinterlaesst (Stoerung im Repro des Pruefers:
``os._exit`` unmittelbar nach ``os.link``).

Mutationsprobe: den Aufruf von ``raeume_zwillinge`` je Stelle entfernen -> der
zugehoerige Test rot; im Gate hinter die Sperre des Abbruchs schieben ->
``test_der_zwilling_des_abbruchs_*`` rot.

Knoten: system/entscheid
"""

from __future__ import annotations

import ast
import os
import secrets
from collections import Counter
from pathlib import Path

from rechner_pipeline.gates import gate_entscheid, stand_belegen
from rechner_pipeline.gates._common import raeume_zwillinge
from rechner_pipeline.models import ordnungslinie as ol
from rechner_pipeline.models import standabnahme as sa
from tests.zeichnung_fixture import VORSTAND_SCHLUESSEL_DATEI, erklaerung_args, linie_anlegen

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "rechner_pipeline"


def _zwilling(ziel: Path) -> Path:
    rest = ziel.parent / f".{ziel.name}.{secrets.token_hex(8)}.tmp"
    os.link(ziel, rest)
    assert rest.stat().st_nlink == 2
    return rest


def _reste(verzeichnis: Path) -> list:
    return sorted(p.name for p in verzeichnis.iterdir() if p.name.endswith(".tmp"))


def test_die_eine_stelle_raeumt_nur_zwillinge(tmp_path):
    """Ein Zwilling geht; ein Rest OHNE eingehaengtes Ziel (Ausfall vor
    ``os.link``, er gehoert dem naechsten Schreiber desselben Ziels), ein Rest
    mit anderem Inhalt und fremde Punktdateien bleiben."""
    beleg = tmp_path / "A-Q1-ab.json"
    beleg.write_bytes(b"{}")
    zwilling = _zwilling(beleg)
    fremd_inhalt = tmp_path / f".{beleg.name}.{secrets.token_hex(8)}.tmp"
    fremd_inhalt.write_bytes(b"{}")
    ohne_ziel = tmp_path / ".A-Q1-cd.json.0123456789abcdef.tmp"
    ohne_ziel.write_bytes(b"{}")
    fremd = tmp_path / ".gitkeep"
    fremd.write_bytes(b"")
    assert raeume_zwillinge(tmp_path) == [zwilling.name]
    assert not zwilling.exists() and fremd_inhalt.exists() and ohne_ziel.exists()
    assert fremd.exists() and beleg.read_bytes() == b"{}"


def test_linie_json_die_wiederholung_liefert_den_ungestoerten_lauf(tmp_path):
    """Rot vor dem Fix: Wiederholung Exit 2 ("schon ein Linienbereich"), der
    Zwilling blieb."""
    linie = tmp_path / "linie"
    assert stand_belegen.main(["linie", "--linie", str(linie)]).exit_code == 0
    _zwilling(linie / sa.LINIE_MARKER)
    nochmal = stand_belegen.main(["linie", "--linie", str(linie)])
    assert nochmal.exit_code == 0, nochmal.errors
    assert nochmal.summary["bereits_vorhanden"] is True
    assert _reste(linie) == []
    # Ein Linienbereich mit Inhalt bleibt verweigert.
    (linie / "ordnung").mkdir()
    assert stand_belegen.main(["linie", "--linie", str(linie)]).exit_code != 0


def _ordnung_2(tmp_path: Path) -> Path:
    import json

    o = json.loads((tmp_path / "zeichnungsordnung.json").read_text(encoding="utf-8"))
    o["rollen"]["mensch/revision"] = {"schluessel_sha256": "ab" * 32,
                                      "schluesselklasse": "simulation", "gates": []}
    datei = tmp_path / "o2.json"
    datei.write_text(json.dumps(o, sort_keys=True), encoding="utf-8")
    return datei


def test_das_glied_der_ordnungslinie(tmp_path):
    """Rot vor dem Fix: Wiederholung Exit 0 (``bereits_vorhanden``), der
    Zwilling blieb — auch nach dem Anhaengen von Glied 3."""
    linie = linie_anlegen(tmp_path)
    datei = _ordnung_2(tmp_path)
    [eins], _ = ol.lade_linie_strukturell_zur_anzeige(linie)
    argv = ["ordnung", "--linie", str(linie), "--ordnung", str(datei),
            "--vorgaenger", eins["glied_sha256"],
            "--vorstand-schluessel", str(tmp_path / VORSTAND_SCHLUESSEL_DATEI),
            *erklaerung_args([eins], datei, "gueltig")]
    erst = stand_belegen.main(argv)
    assert erst.exit_code == 0, erst.errors
    _zwilling(Path(erst.paths["glied"]))
    nochmal = stand_belegen.main(argv)
    assert nochmal.exit_code == 0 and nochmal.summary["bereits_vorhanden"] is True
    assert _reste(linie / ol.VERZEICHNIS) == []


def test_das_archiv_der_tbox(tmp_path):
    """Rot vor dem Fix: das Archiv lag schon, die Wiederholung schrieb nicht
    und raeumte nicht."""
    linie = linie_anlegen(tmp_path)
    vermerk = linie / "abgeleitet" / "tbox" / "vermerk.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text("Vermerk.\n", encoding="utf-8")
    argv = ["tbox", "--linie", str(linie), "--repo-root", str(REPO),
            "--artefakt", "abgeleitet/tbox/vermerk.md", "--begruendung", "Erstabnahme"]
    assert stand_belegen.main(argv).exit_code == 0
    archiv = linie / stand_belegen.TBOX_ARCHIV_RELATIV
    [beleg] = list(archiv.glob("*.json"))
    _zwilling(beleg)
    assert stand_belegen.main(argv).exit_code == 0
    assert _reste(archiv) == []


def test_der_zwilling_des_abbruchs_vor_der_sperre(tmp_path):
    """Rot vor dem Fix: Jeder weitere Aufruf im abgebrochenen Fall endete an
    der Sperre (Exit 20), bevor er Reste raeumte."""
    from tests.test_fallauftrag_lebenslauf import _abbruch, _aq1
    from tests.e2e_fixture import bereite_pk1_fall
    from rechner_pipeline.gates.abox_validate import main as pq3

    fall = bereite_pk1_fall(tmp_path, ("klv/tg2012",), scope="tarif")
    assert pq3(["--fall", str(fall), "--repo-root", str(REPO)]).exit_code == 0
    assert _aq1(fall).exit_code == 0
    _, abbruch = _abbruch(fall)
    assert abbruch.exit_code == 0, abbruch.errors
    _zwilling(Path(abbruch.paths["snapshot"]))
    danach = _aq1(fall)
    assert danach.exit_code == 20 and danach.errors[0]["code"] == "fallabbruch"
    assert _reste(fall / "entscheide") == []


# --------------------------------------------------------------------------- #
# Ratsche: die Schreibstellen und die Stellen, die raeumen
# --------------------------------------------------------------------------- #


def _aufrufe(quelle: str, name: str) -> Counter:
    zaehler: Counter = Counter()

    class B(ast.NodeVisitor):
        funktion = "<modul>"

        def visit_FunctionDef(self, k):
            vorher, self.funktion = self.funktion, k.name
            self.generic_visit(k)
            self.funktion = vorher

        def visit_Call(self, k):
            f = k.func
            if (f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")) == name:
                zaehler[self.funktion] += 1
            self.generic_visit(k)

    B().visit(ast.parse(quelle))
    return zaehler


def _im_paket(name: str) -> Counter:
    gesamt: Counter = Counter()
    for pfad in sorted(SRC.rglob("*.py")):
        if pfad.name == "_common.py":
            continue
        for funktion, n in _aufrufe(pfad.read_text(encoding="utf-8"), name).items():
            gesamt[(pfad.relative_to(SRC).as_posix(), funktion)] += n
    return gesamt


#: Gemessen 2026-10-01 (Pruefrunde H): die Schreibstellen von
#: ``schreibe_exklusiv`` im Paket. Je Stelle, wer den Zwilling raeumt:
#: * ``stand_belegen.main`` (3): ``linie.json`` (Eintritt in ``linie``),
#:   Glied (Eintritt in ``ordnung``), T-Box-Archiv (Eintritt ins Archiv);
#: * ``gate_entscheid.main`` (1): Snapshot (Eintritt in ``entscheide/`` vor
#:   der Sperre des Abbruchs);
#: * ``_provenienz.schreibe_pk1_beleg`` (1): die Wiederholung SCHREIBT immer
#:   (``schreibe_exklusiv`` raeumt die Reste des Ziels vor dem eigenen
#:   Schreiben, auch wenn es dann ``FileExistsError`` meldet).
SCHREIBSTELLEN = Counter({("gates/stand_belegen.py", "main"): 3,
                          ("gates/gate_entscheid.py", "main"): 1,
                          ("gates/_provenienz.py", "schreibe_pk1_beleg"): 1})
RAEUMSTELLEN = Counter({("gates/stand_belegen.py", "main"): 3,
                        ("gates/gate_entscheid.py", "main"): 1})


def test_ratsche_schreibstellen_und_raeumstellen():
    """Statische Ratsche (AST, benannt) mit ==: Eine neue Schreibstelle von
    ``schreibe_exklusiv`` erzwingt die Frage, wer ihren Zwilling raeumt; die
    Raeumstellen sind gezaehlt. Verhalten an der Naht halten die Tests oben."""
    assert _im_paket("schreibe_exklusiv") == SCHREIBSTELLEN
    assert _im_paket("raeume_zwillinge") == RAEUMSTELLEN


def test_ratsche_positivkontrolle_des_detektors():
    quelle = ("def main():\n    schreibe_exklusiv(a, b)\n    x.schreibe_exklusiv(c, d)\n"
              "def neben():\n    raeume_zwillinge(v)\n")
    assert _aufrufe(quelle, "schreibe_exklusiv") == Counter({"main": 2})
    assert _aufrufe(quelle, "raeume_zwillinge") == Counter({"neben": 1})


def test_im_gate_raeumt_der_eintritt_vor_der_sperre_des_abbruchs():
    """Statische Ratsche (AST, benannt): In ``gate_entscheid.main`` steht der
    Aufruf von ``raeume_zwillinge`` VOR dem von ``abbruch_im_fall``."""
    baum = ast.parse(Path(gate_entscheid.__file__).read_text(encoding="utf-8"))
    main = next(k for k in baum.body if isinstance(k, ast.FunctionDef) and k.name == "main")
    zeilen = {}
    for k in ast.walk(main):
        if isinstance(k, ast.Call):
            name = k.func.id if isinstance(k.func, ast.Name) else getattr(k.func, "attr", "")
            if name in ("raeume_zwillinge", "abbruch_im_fall"):
                zeilen.setdefault(name, k.lineno)
    assert zeilen["raeume_zwillinge"] < zeilen["abbruch_im_fall"], zeilen
