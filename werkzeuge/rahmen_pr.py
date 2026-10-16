"""``rahmen_pr`` — den Rahmen der Seite als Inhalt eines Pull Requests nach plv-fiktion legen.

Die Seite hat zwei Teile (Entscheid des Maintainers 09.10.2026, Weg C): Den
Betriebsteil (``betrieb/``) baut der Workflow von plv-fiktion jeden Abend aus
dem, was der Tagesbetrieb in den Zweig ``betrieb`` legt; alles andere, der
Rahmen, aendert sich nur per Pull Request. Der Workflow rendert den
Betriebsteil mit dem Code des Commits, den ``CODESTAND`` in ``main`` nennt.

Dieses Kommando baut die GANZE Seite aus einem Commit dieses Repositorys
(``auftritt.py``, mit Wache und Seitenpruefung), nimmt daraus den Rahmen und
legt ihn als einen Commit auf einen neuen Zweig ``beitrag/...`` im Klon von
plv-fiktion, in einem eigenen Arbeitsverzeichnis (git worktree). ``CODESTAND``
schreibt es selbst: den Commit, aus dem es eben gebaut hat. So koennen
gerenderter Rahmen und gepinnter Code nicht auseinanderlaufen.

Es haelt an, statt zu raten:

* wenn dieses Repository Aenderungen ausserhalb eines Commits traegt — dann
  gaebe es den Stand nicht, den CODESTAND nennen muesste;
* wenn der Bau oder eine Pruefung einen Befund hat, auch eine Luecke;
* wenn der Klon nicht sauber ist, der Zweig schon besteht oder nicht unter
  ``beitrag/`` liegt (nur dorthin darf geschoben werden, Ruleset nur-betrieb).

Es schiebt nichts und legt keinen Pull Request an: Push, Pull Request und
Merge macht der Maintainer. Liegt CODESTAND noch nicht auf origin, sagt es
das; vor dem Merge muss rechner-pipeline gepusht sein, sonst findet der
Workflow den Code nicht.

Aufruf::

    python werkzeuge/rahmen_pr.py --klon ../plv-fiktion \\
        --fall faelle/<fall> --name <kurzname> \\
        --abzug <abzug-1>.csv --abzug <abzug-2>.csv --film <film>.mp4 \\
        --stands-paket <paket> --anker <anker>.jsonl --ab1 <A-B1>.json \\
        [--oeffentliches-paket] [--zweig beitrag/rahmen-JJJJ-MM-TT] \\
        [--basis main] [--arbeit runs/rahmen-pr-...] [--anhang "Zeilen"]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

WERKZEUGE = Path(__file__).resolve().parent
CODE = WERKZEUGE.parent

#: Der Betriebsteil gehoert nicht in den Rahmen (unternehmensseite.BETRIEB_DIR).
BETRIEB_DIR = "betrieb"
#: Die Datei in main von plv-fiktion, die den Code des Workflows pinnt.
CODESTAND = "CODESTAND"
#: Nur unter diesem Praefix darf ein Zweig nach plv-fiktion (Ruleset nur-betrieb).
PRAEFIX = "beitrag/"


class Halt(RuntimeError):
    pass


def _git(repo: Path, *args: str, pruefen: bool = True) -> str:
    lauf = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    if pruefen and lauf.returncode != 0:
        raise Halt(f"git {' '.join(args)} in {repo}: {lauf.stderr.strip() or lauf.stdout.strip()}")
    return lauf.stdout.strip()


def codestand(code: Path = CODE) -> str:
    """Der Commit, aus dem gebaut wird — nur, wenn der Baum ihm entspricht."""
    offen = _git(code, "status", "--porcelain")
    if offen:
        raise Halt(f"{code} traegt Aenderungen ausserhalb eines Commits; CODESTAND muesste einen "
                   "Stand nennen, den es nicht gibt. Erst committen:\n" + offen[:2000])
    return _git(code, "rev-parse", "HEAD")


def rahmen_dateien(seite: Path) -> List[str]:
    """Die Dateien des Rahmens im gebauten Baum: alles ausser ``betrieb/``."""
    dateien: List[str] = []
    for p in sorted(seite.rglob("*")):
        rel = p.relative_to(seite)
        if rel.parts[0] == BETRIEB_DIR or p.is_dir():
            continue
        if p.is_symlink():
            raise Halt(f"{rel}: ein Symlink im gebauten Baum")
        dateien.append(rel.as_posix())
    return dateien


def fuelle(arbeitsbaum: Path, seite: Path, stand: str) -> List[str]:
    """Den Arbeitsbaum des Zweigs auf den Rahmen setzen: was er traegt, faellt
    weg; der Rahmen und CODESTAND kommen hinein, je Datei benannt gestaged."""
    _git(arbeitsbaum, "rm", "-r", "-q", "--cached", "--ignore-unmatch", ".")
    for p in sorted(arbeitsbaum.iterdir()):
        if p.name == ".git":
            continue
        if p.is_dir() and not p.is_symlink():
            shutil.rmtree(p)
        else:
            p.unlink()
    dateien = rahmen_dateien(seite)
    for rel in dateien:
        ziel = arbeitsbaum / rel
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seite / rel, ziel)
    (arbeitsbaum / CODESTAND).write_text(stand + "\n", encoding="utf-8")
    dateien.append(CODESTAND)
    liste = arbeitsbaum.parent / "rahmen-dateien.txt"
    liste.write_text("\n".join(dateien) + "\n", encoding="utf-8")
    _git(arbeitsbaum, "add", f"--pathspec-from-file={liste}")
    rest = _git(arbeitsbaum, "status", "--porcelain")
    if any(not z.startswith(("A ", "M ", "D ", "R ")) for z in rest.splitlines()):
        raise Halt("Nach dem Staging liegt etwas ungestaged im Arbeitsbaum:\n" + rest[:2000])
    return dateien


def _baue(kommando: List[str], umgebung: dict) -> int:
    """Die ganze Seite bauen (auftritt.py); Rueckgabe: Exit."""
    return subprocess.run(kommando, cwd=CODE, env=umgebung).returncode


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/rahmen_pr.py",
                                description=__doc__.splitlines()[0])
    p.add_argument("--klon", required=True, help="Klon von bartlmac/plv-fiktion")
    heute = _dt.date.today().isoformat()
    p.add_argument("--zweig", default=f"{PRAEFIX}rahmen-{heute}",
                   help=f"neuer Zweig im Klon (Vorgabe: {PRAEFIX}rahmen-{heute})")
    p.add_argument("--basis", default="main", help="Ref im Klon, auf dem der Zweig beginnt")
    p.add_argument("--arbeit", default=None,
                   help="frisches Verzeichnis fuer Bau und Arbeitsbaum "
                        "(Vorgabe: runs/rahmen-pr-<Zeit>)")
    p.add_argument("--anhang", default="", help="Zeilen am Ende der Commit-Botschaft")
    for name in ("--fall", "--name", "--film", "--stands-paket", "--anker", "--ab1"):
        p.add_argument(name, required=name != "--ab1")
    p.add_argument("--abzug", action="append", default=[])
    p.add_argument("--verlauf", default=None)
    p.add_argument("--oeffentliches-paket", dest="oeffentlich", action="store_true")
    args = p.parse_args(argv)

    klon = Path(args.klon).resolve()
    arbeit = Path(args.arbeit or CODE / "runs" /
                  f"rahmen-pr-{_dt.datetime.now().strftime('%Y%m%d-%H%M%S')}").resolve()
    try:
        if not args.zweig.startswith(PRAEFIX):
            raise Halt(f"Zweig {args.zweig!r}: nach plv-fiktion nur unter {PRAEFIX}")
        if arbeit.exists():
            raise Halt(f"{arbeit} besteht schon; ein frisches Verzeichnis waehlen")
        stand = codestand()
        if _git(klon, "status", "--porcelain"):
            raise Halt(f"{klon} ist nicht sauber")
        if _git(klon, "rev-parse", "--verify", "--quiet", f"refs/heads/{args.zweig}", pruefen=False):
            raise Halt(f"Zweig {args.zweig} besteht im Klon schon")
        basis = _git(klon, "rev-parse", "--verify", f"{args.basis}^{{commit}}")

        # Die ganze Seite aus genau diesem Commit: der Code dieses Baums,
        # nicht ein installiertes Paket.
        umgebung = dict(os.environ, PYTHONPATH=str(CODE / "src"), PYTHONDONTWRITEBYTECODE="1")
        bau = [sys.executable, str(WERKZEUGE / "auftritt.py"), "--teil", "beide",
               "--fall", args.fall, "--name", args.name, "--film", args.film,
               *(t for a in args.abzug for t in ("--abzug", a)),
               "--stands-paket", args.stands_paket, "--anker", args.anker,
               *(("--ab1", args.ab1) if args.ab1 else ()),
               *(("--oeffentliches-paket",) if args.oeffentlich else ()),
               *(("--verlauf", args.verlauf) if args.verlauf else ()),
               "--out", str(arbeit / "seite"), "--vorschau", str(arbeit / "vorschau")]
        arbeit.mkdir(parents=True)
        print(f"== Bau der ganzen Seite aus {stand[:12]} nach {arbeit}")
        rc = _baue(bau, umgebung)
        if rc != 0:
            raise Halt(f"Bau oder Pruefung mit Exit {rc}; kein Pull Request")
        if codestand() != stand:
            raise Halt("Der Codebaum hat sich waehrend des Baus geaendert")

        arbeitsbaum = arbeit / "plv-fiktion"
        _git(klon, "worktree", "add", "-q", "-b", args.zweig, str(arbeitsbaum), basis)
        dateien = fuelle(arbeitsbaum, arbeit / "seite", stand)
        if not _git(arbeitsbaum, "diff", "--cached", "--name-only"):
            # Den eben angelegten, leeren Zweig nicht stehen lassen: Er traegt
            # nichts, und ein zweiter Aufruf scheiterte an ihm.
            _git(klon, "worktree", "remove", "--force", str(arbeitsbaum))
            _git(klon, "branch", "-D", args.zweig)
            raise Halt(f"Der Rahmen aus {stand[:12]} gleicht {args.basis}; nichts zu beantragen")
        botschaft = (f"Rahmen vom {_dt.date.today().strftime('%d.%m.%Y')}, gebaut aus "
                     f"rechner-pipeline {stand[:7]}\n\n"
                     f"CODESTAND {stand}: Mit diesem Code rendert der Workflow den "
                     "Betriebsteil.\nGebaut mit werkzeuge/rahmen_pr.py (auftritt.py, Wache und "
                     "Seitenpruefung ohne Befund); der Betriebsteil gehoert nicht zum Rahmen.\n")
        if args.anhang:
            botschaft += "\n" + args.anhang.strip() + "\n"
        datei = arbeit / "botschaft.txt"
        datei.write_text(botschaft, encoding="utf-8")
        _git(arbeitsbaum, "commit", "-q", "-F", str(datei))
        commit = _git(arbeitsbaum, "rev-parse", "HEAD")
        im_commit = set(_git(arbeitsbaum, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
        if im_commit != set(dateien) or _git(arbeitsbaum, "status", "--porcelain"):
            raise Halt("Der Commit traegt nicht genau den Rahmen")
        if _git(arbeitsbaum, "show", f"HEAD:{CODESTAND}") != stand:
            raise Halt("CODESTAND im Commit ist nicht der gebaute Stand")
        auf_origin = _git(CODE, "branch", "-r", "--contains", stand, pruefen=False)
    except Halt as exc:
        print(f"HALT: {exc}", file=sys.stderr)
        return 1

    print(f"Zweig {args.zweig} im Klon {klon}: Commit {commit[:12]} auf {args.basis} ({basis[:12]})")
    print(f"  CODESTAND {stand}")
    print(f"  {_git(klon, 'diff', '--shortstat', basis, commit) or 'keine Aenderung'}")
    print(f"  Arbeitsbaum {arbeitsbaum}; Vorschau {arbeit / 'vorschau'}")
    if not auf_origin:
        print(f"HINWEIS: {stand[:12]} liegt noch nicht auf origin. Vor dem Merge des Pull "
              "Requests rechner-pipeline pushen, sonst findet der Workflow den Code nicht.")
    print("Push, Pull Request und Merge macht der Maintainer.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
