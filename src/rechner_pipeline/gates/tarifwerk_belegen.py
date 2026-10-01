"""``tarifwerk_belegen`` — der Beleg der Tarifwerk-Abnahme A-T1 (Producer).

Entscheid des Maintainers 2026-10-01 (ADR-025): Das Tarifwerk der PLV —
Tarifplaene und Parametrierung der eigenen Tarifgenerationen
(``models.tarifwerkabnahme.TARIFWERK``) — ist einer der vier Gegenstaende
der Erstabnahme des Zielsystems, gezeichnet von ``mensch/aktuariat``,
vorgelegt von ``agent/aktuariat``. Dieser Producer legt ihn vor, im
Linienbereich (Erstabnahme, spaetere Aenderungen in der Entwicklung) oder im
Fall (eine Aenderung, die der Fall erzwingt; Weg a der Standabnahme):

* ``abgeleitet/tarifwerk/aenderung.json`` — der Aenderungsbeleg zwischen
  ``--von`` (dem zuletzt abgenommenen Stand, als Commit) und dem
  Arbeitsbaum: je Tarifplan Zustand, Diffstat, Commits des Zweigs und was
  nicht committet ist; je eigener Generation jeder Config Zustand und JEDES
  geaenderte Tarifwerk-Feld mit altem und neuem Wert; je Config die Commits;
  beide Staende (``stand_vorher``, ``stand``);
* ``abgeleitet/tarifwerk/aenderung.md`` — die lesbare Sicht fuer den
  Pruefer, aus dem Beleg erzeugt, nie umgekehrt.

Das Gate (``gate_entscheid --gate A-T1``) glaubt dem Beleg nicht, es rechnet
ihn mit :func:`nachgerechnet` nach. Git-Zugriff nur ueber die eine
Subprozess-Stelle in ``gates._provenienz``.

Run via::

    python -m rechner_pipeline.gates.tarifwerk_belegen --linie linie \\
        --repo-root . --von <zuletzt abgenommener Stand> --begruendung "<text>"
    python -m rechner_pipeline.gates.tarifwerk_belegen --fall faelle/<fall> ...

Knoten: system/entscheid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.gates._provenienz import lebendes_repo  # --repo-root (G12)
from rechner_pipeline.gates._common import Exit, ToolboxResult, build_result, run_command
from rechner_pipeline.gates._provenienz import (
    GitAngabeFehler,
    git_commit_von,
    git_commits,
    git_dateien,
    git_diffstat,
    git_inhalt,
    git_merge_base,
    git_nicht_committet,
    git_stand,
)
from rechner_pipeline.gates.kernstand_belegen import _c, _ersetze, _json_bytes, _md, _zahl
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models import tarifwerkabnahme as tw

COMMAND = "tarifwerk_belegen"
GATE = "A-T1.tarifwerk"
GATE_VERSION = "1.0.0"
#: Schema des Aenderungsbelegs.
TARIFWERK_AENDERUNG_SCHEMA_VERSION = 1
ART = "tarifwerk"
PFADE = (tw.TARIFPLAENE, tw.CONFIG_VERZEICHNIS)


def _arbeitsbaum(repo_root: Path) -> Tuple[List[Tuple[str, bytes]], List[Tuple[str, bytes]]]:
    """Tarifplaene und PLV-Configs im Arbeitsbaum (auch nicht verfolgte)."""
    plaene = sorted(
        (d.relative_to(repo_root).as_posix(), d.read_bytes())
        for d in (repo_root / tw.TARIFPLAENE).rglob("*")
        if d.is_file() and "__pycache__" not in d.parts)
    configs = sorted(
        (c.relative_to(repo_root).as_posix(), c.read_bytes())
        for c in (repo_root / tw.CONFIG_VERZEICHNIS).glob(tw.CONFIG_MUSTER) if c.is_file())
    return plaene, configs


def lebender_inhalt(repo_root: Path) -> Dict[str, Any]:
    plaene, configs = _arbeitsbaum(repo_root)
    return tw.tarifwerk_inhalt(plaene, configs)


def lebender_stand(repo_root: Path) -> Dict[str, str]:
    """Der Stand des Tarifwerks im Arbeitsbaum (``models.tarifwerkabnahme``)."""
    return tw.stand_aus(lebender_inhalt(repo_root))


def _inhalt_im_commit(repo_root: Path, commit: str) -> Dict[str, Any]:
    def lies(pfade: List[str]) -> List[Tuple[str, bytes]]:
        paare = []
        for pfad in pfade:
            roh = git_inhalt(repo_root, commit, pfad)
            if roh is None:
                raise tw.TarifwerkFehler(f"{pfad} in {commit[:12]} ist nicht lesbar")
            paare.append((pfad, roh))
        return paare

    plaene = git_dateien(repo_root, commit, tw.TARIFPLAENE)
    configs = git_dateien(repo_root, commit, tw.CONFIG_VERZEICHNIS)
    if plaene is None or configs is None:
        raise tw.TarifwerkFehler(f"die Dateien des Tarifwerks in {commit[:12]} sind nicht lesbar")
    return tw.tarifwerk_inhalt(lies(tw.tarifplan_pfade(plaene)), lies(tw.konfig_pfade(configs)))


def _baue(repo_root: Path, angabe: str, von: str, begruendung: str) -> Dict[str, Any]:
    """Deterministisch: dieselben Commits, derselbe Arbeitsbaum, dieselbe
    Begruendung ergeben denselben Beleg — darauf beruht die Nachrechnung."""
    stand_git = git_stand(repo_root)
    if stand_git.get("commit") == "unbekannt":
        raise tw.TarifwerkFehler("der Git-Stand des Arbeitsbaums ist nicht lesbar")
    basis = git_merge_base(repo_root, von, "HEAD")
    diffstat = git_diffstat(repo_root, von, PFADE)
    commits = git_commits(repo_root, von, PFADE)
    offen = git_nicht_committet(repo_root, PFADE)
    if diffstat is None or commits is None or offen is None:
        raise tw.TarifwerkFehler(
            f"Diffstat, Commits oder Status zwischen {von[:12]} und dem Arbeitsbaum "
            "sind nicht lesbar")
    alt = _inhalt_im_commit(repo_root, von)
    neu = lebender_inhalt(repo_root)
    diff = tw.unterschiede(alt, neu)

    def kurz(c: Dict[str, Any]) -> Dict[str, str]:
        return {"commit": c["commit"], "datum": c["datum"], "betreff": c["betreff"]}

    teile: Dict[str, Dict[str, Any]] = {}

    def teil(pfad: str) -> Optional[Dict[str, Any]]:
        name = tw.teil_von(pfad)
        if name is None:
            return None
        return teile.setdefault(name, {"pfad": name, "hinzu": 0, "weg": 0, "binaer": False,
                                       "commits": [], "nicht_committet": []})

    for eintrag in diff["tarifplaene"]:
        teil(eintrag["pfad"])
    for pfad in sorted(set(alt["generationen"]) | set(neu["generationen"])):
        teil(pfad)
    for plus, minus, pfad in diffstat:
        t = teil(pfad)
        if t is None:
            continue
        t["hinzu"] += plus or 0
        t["weg"] += minus or 0
        t["binaer"] = t["binaer"] or plus is None
    alle_commits: List[Dict[str, Any]] = []
    for c in commits:
        beruehrt = sorted({n for n in (tw.teil_von(d) for d in c["dateien"]) if n})
        if not beruehrt:
            continue
        alle_commits.append({**kurz(c), "teile": beruehrt})
        for name in beruehrt:
            teil(name)["commits"].append(kurz(c))  # type: ignore[index]
    for status, pfad in offen:
        t = teil(pfad)
        if t is not None:
            t["nicht_committet"].append({"status": status, "pfad": pfad})
    for t in teile.values():
        t["nicht_committet"].sort(key=lambda d: d["pfad"])
    stand_vorher, stand_jetzt = tw.stand_aus(alt), tw.stand_aus(neu)
    return {
        "schema_version": TARIFWERK_AENDERUNG_SCHEMA_VERSION,
        "art": ART,
        "gegenstand": [{"pfad": p, "gliederung": g, "begruendung": b} for p, g, b in tw.TARIFWERK],
        "nicht_tarifwerk": dict(tw.NICHT_TARIFWERK),
        "git": {
            "referenz": angabe,
            "referenz_commit": von,
            "merge_base": basis or "unbekannt",
            "aktuell": stand_git["commit"],
            "zweig": stand_git.get("branch", "unbekannt"),
            "dirty": stand_git.get("dirty", "unbekannt"),
        },
        "stand_vorher": stand_vorher,
        "stand": stand_jetzt,
        "veraendert": stand_vorher != stand_jetzt,
        "tarifplaene": diff["tarifplaene"],
        "generationen": diff["generationen"],
        "teile": [teile[n] for n in sorted(teile)],
        "commits": alle_commits,
        "begruendung": begruendung,
    }


def baue_aenderungsbeleg(repo_root: Path, von: str, begruendung: str) -> Dict[str, Any]:
    try:
        commit = git_commit_von(repo_root, von)
    except GitAngabeFehler as exc:
        raise tw.TarifwerkFehler(str(exc)) from exc
    if commit is None:
        raise tw.TarifwerkFehler(f"--von {von!r} ist kein Commit dieses Repos")
    return _baue(repo_root, von, commit, begruendung)


def nachgerechnet(repo_root: Path, beleg: Dict[str, Any]) -> Dict[str, Any]:
    """Den Beleg aus seinen eigenen Angaben neu bauen (Nachrechnung im Gate)."""
    git = beleg.get("git") if isinstance(beleg.get("git"), dict) else {}
    von = str(git.get("referenz_commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", von):
        raise tw.TarifwerkFehler("git.referenz_commit ist kein Commit-Hash")
    return _baue(repo_root, str(git.get("referenz") or ""), von,
                 str(beleg.get("begruendung") or ""))


def _wert(w: Any) -> str:
    return _c(json.dumps(w, ensure_ascii=False, sort_keys=True))


def rendere_sicht(beleg: Dict[str, Any]) -> str:
    """Die Sicht des Pruefers (Markdown), deterministisch aus dem Beleg."""
    git = beleg.get("git") or {}
    z: List[str] = [
        "# Tarifwerk-Abnahme A-T1 — Tarifwerk der PLV", "",
        f"Zuletzt abgenommener Stand: {_c(git.get('referenz'))} (Commit "
        f"{_c(str(git.get('referenz_commit'))[:12])}).  ",
        f"Lebender Stand: Commit {_c(str(git.get('aktuell'))[:12])} auf "
        f"{_c(git.get('zweig'))}, nicht committete Aenderungen im Arbeitsbaum: "
        f"{_md(git.get('dirty'))}.", "",
        f"Begruendung der Vorlage: {_md(beleg.get('begruendung'))}", "",
    ]
    if not beleg.get("veraendert"):
        z += ["**Seit dem zuletzt abgenommenen Stand hat sich am Tarifwerk nichts "
              "geaendert.** Die Abnahme bestaetigt diesen Stand.", ""]
    z += ["## Tarifplaene", "", "| Tarifplan | Zustand | Zeilen hinzu | Zeilen weg | Commits |",
          "|---|---|---:|---:|---:|"]
    teile = {t["pfad"]: t for t in beleg.get("teile") or []}
    for p in beleg.get("tarifplaene") or []:
        t = teile.get(p["pfad"], {})
        z.append(f"| {_c(p['pfad'])} | {_md(p['zustand'])} | {_zahl(t.get('hinzu'))} | "
                 f"{_zahl(t.get('weg'))} | {len(t.get('commits') or [])} |")
    z += ["", "## Tarifgenerationen der Configs", "",
          "| Config | Generation | Zustand | geaenderte Felder |", "|---|---|---|---:|"]
    for g in beleg.get("generationen") or []:
        z.append(f"| {_c(g['config'])} | {_md(g['generation'])} | {_md(g['zustand'])} | "
                 f"{len(g['felder'])} |")
    z.append("")
    for g in beleg.get("generationen") or []:
        if not g["felder"]:
            continue
        z += [f"### {_md(g['generation'])} in {_c(g['config'])}", ""]
        for f in g["felder"]:
            z.append(f"- {_c(f['feld'])}: {_wert(f['vorher'])} -> {_wert(f['nachher'])}")
        z.append("")
    z += ["## Commits des Zweigs", ""]
    for t in beleg.get("teile") or []:
        if not (t["commits"] or t["nicht_committet"]):
            continue
        z += [f"### {_c(t['pfad'])}", ""]
        for c in t["commits"]:
            z.append(f"- Commit {_c(c['commit'][:12])} vom {_md(c['datum'])}: {_md(c['betreff'])}")
        for o in t["nicht_committet"]:
            z.append(f"- nicht committet ({_md(o['status'])}): {_c(o['pfad'])} "
                     "— ohne Commit-Beschreibung")
        z.append("")
    z += ["## Gegenstand der Abnahme", ""]
    for g in beleg.get("gegenstand") or []:
        z.append(f"- {_c(g['pfad'])} — {_md(g['begruendung'])}")
    z += ["", "Nicht Gegenstand (je Generation): "
          + ", ".join(f"{_c(k)} ({_md(v)})" for k, v in sorted(
              (beleg.get("nicht_tarifwerk") or {}).items())) + ".", "",
          "Aus dem Aenderungsbeleg erzeugt (`gates.tarifwerk_belegen`); massgeblich ist "
          "der Beleg, nicht diese Sicht.", ""]
    return "\n".join(z)


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.tarifwerk_belegen",
        description="Beleg der Tarifwerk-Abnahme A-T1: Aenderungen am Tarifwerk der PLV "
                    "seit dem zuletzt abgenommenen Stand (Producer, kein Gate).")
    ziel = p.add_mutually_exclusive_group(required=True)
    ziel.add_argument("--fall", default=None)
    ziel.add_argument("--linie", default=None, help="Linienbereich (Erstabnahme, ADR-025)")
    p.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", required=True)
    p.add_argument("--von", required=True,
                   help="der zuletzt abgenommene Stand (Commit-Angabe); fuer die "
                        "Erstabnahme ausdruecklich anzugeben, es gibt keine Vorgabe")
    p.add_argument("--begruendung", required=True)
    args = p.parse_args(argv)

    def _fehler(code: int, text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
                            exit_code=code, errors=[{"code": "tarifwerk", "message": text}])

    bereich = Path(args.fall or args.linie)
    if sa.bereich_art(bereich) is None:
        return _fehler(Exit.USAGE, f"kein Fall- oder Linienbereich: {bereich}")
    if not args.begruendung.strip():
        return _fehler(Exit.USAGE, "--begruendung ist leer")
    repo = Path(args.repo_root).resolve()
    try:
        beleg = baue_aenderungsbeleg(repo, args.von, args.begruendung.strip())
    except tw.TarifwerkFehler as exc:
        return _fehler(Exit.FILE_CONTRACT, f"Tarifwerk nicht bestimmbar: {exc}")
    git = beleg["git"]
    if git["merge_base"] != git["referenz_commit"]:
        return _fehler(
            Exit.FILE_CONTRACT,
            f"--von {args.von!r} ist kein Vorfahre des lebenden Stands — die Differenz "
            "mischte die Aenderungen dieses Zweigs mit fremden; den Zweig auf den "
            "abgenommenen Stand bringen")
    ausgaben = {tw.AENDERUNG_RELATIV: _json_bytes(beleg),
                tw.SICHT_RELATIV: rendere_sicht(beleg).encode("utf-8")}
    for relativ, daten in ausgaben.items():
        _ersetze(bereich / relativ, daten)
    return build_result(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={relativ: str(bereich / relativ) for relativ in ausgaben},
        summary={"von": git["referenz"], "von_commit": git["referenz_commit"],
                 "aktuell": git["aktuell"], "veraendert": beleg["veraendert"],
                 "generationen_geaendert": sum(1 for g in beleg["generationen"]
                                               if g["zustand"] != "unveraendert"),
                 "tarifplaene_geaendert": sum(1 for t in beleg["tarifplaene"]
                                              if t["zustand"] != "unveraendert"),
                 "stand": beleg["stand"]},
        output_hashes={relativ: hashlib.sha256(daten).hexdigest()
                       for relativ, daten in ausgaben.items()},
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
