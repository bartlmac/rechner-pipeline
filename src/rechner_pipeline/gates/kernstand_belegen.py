"""``kernstand_belegen`` — die Belege der Kernabnahme A-K2 (Producer).

Entscheid des Maintainers 2026-10-01: A-K2 wird formell Teil des Ablaufs.
A-M4 verlangt, dass der KERNSTAND, auf dem ein Fall rechnet, abgenommen
ist (``models.standabnahme``). Hat er sich seit einer frueheren Abnahme
geaendert, legt dieser Producer ihn vor — mit ``--von`` = dem zuletzt
abgenommenen Kernstand; ist er unveraendert, reicht der Verweis
(``gates.stand_belegen verweisen``). Auch ein unveraenderter Kern ist ein
gueltiger, zeichenbarer Beleg (er sagt dann genau das). Zwei Pruefungen:

1. **Qualitative Pruefung der Aenderungen.** Der Aenderungsbeleg
   (``abgeleitet/kern/aenderung.json``) zeigt die Aenderungen am
   Rechenkern zwischen ``--von`` und dem lebenden Stand — je Modul des
   Gegenstands (:data:`models.kernabnahme.KERNSTAND`) den Diffstat, die
   Commits des Zweigs, die das Modul beruehren (Hash, Datum, Betreffzeile
   als Kurzbeschreibung), und was nicht committet ist; dazu
   Versionsuebergang, beide Kern-Hashes, den Sammelhash der Referenzwerte
   und welche sich bewegt haben. Daneben die lesbare Sicht fuer den
   Pruefer (``abgeleitet/kern/aenderung.md``), aus dem Beleg erzeugt —
   nie umgekehrt.
2. **Regression.** Das Werkzeug ist noch nicht gebaut. Solange
   :data:`models.kernabnahme.REGRESSION_AUSNAHME_ERLAUBT` gilt, schreibt
   dieser Producer ``abgeleitet/kern/regression.json`` als benannte
   AUSNAHME: Zustand ``nicht_gefahren``, Grund "Werkzeug noch nicht
   erstellt" — kein Feld, das wie ein Ergebnis aussieht.

Das Gate (``gate_entscheid --gate A-K2``) glaubt dem Beleg nicht, es
rechnet ihn mit :func:`baue_aenderungsbeleg` nach. Git-Zugriff nur ueber
die eine Subprozess-Stelle in ``gates._provenienz``.

Run via::

    python -m rechner_pipeline.gates.kernstand_belegen --fall faelle/<fall> \\
        --repo-root . --von <zuletzt abgenommener Kernstand> \\
        --begruendung "<warum dieser Kernstand>"
    python -m rechner_pipeline.gates.kernstand_belegen --linie linie ...   (Erstabnahme, ADR-025)

Knoten: system/entscheid
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rechner_pipeline.gates._provenienz import lebendes_repo  # --repo-root (G12)
from rechner_pipeline.gates._common import (
    Exit,
    ToolboxResult,
    build_result,
    ein_ausgabe_benannt,
    raeume_schreibreste,
    run_command,
)
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
from rechner_pipeline.models import kernabnahme as ka

COMMAND = "kernstand_belegen"
GATE = "A-K2.kernaenderung"
#: 2.0.0 (2026-10-09, ADR-028 Nachtrag): Ein Vergleichsstand, dem ein Teil des
#: Gegenstands am heutigen Pfad fehlt, wird verweigert. Major (ADR-012): Ein
#: solcher Lauf schrieb vorher einen Beleg. Im selben Sprung zaehlt der
#: Kernstand nur noch die Dateien des Gegenstands
#: (``models.kernabnahme.gehoert_zum_kernstand``); eine fremde Datei daneben
#: machte ihn vorher still "anders".
GATE_VERSION = "2.0.0"

#: Schema des Aenderungsbelegs. 4 (2026-10-01, ADR-025): der Gegenstand
#: ohne die Tarifplaene (sie gehoeren zum Tarifwerk, A-T1). 3 (2026-10-01):
#: der Kernstand entlang der Module mit Commits, ``--von`` statt
#: ``origin/main``, ein unveraenderter Kern ist ein gueltiger Beleg. 2
#: kannte nur Hashes und Versionen.
KERN_AENDERUNG_SCHEMA_VERSION = 4
#: Schema des Regressionsbelegs (Ergebnis wie Ausnahme).
KERN_REGRESSION_SCHEMA_VERSION = 1
ART = "kernstand"

_VERSION = re.compile(r"""^__version__\s*=\s*["']([^"']+)["']""", re.M)


class KernstandFehler(RuntimeError):
    """Der Kernstand ist nicht bestimmbar — mit dem Grund."""


def _sammelhash(eintraege: List[Tuple[str, bytes]]) -> str:
    """Name UND Inhalt je Datei, sortiert — ein Umbenennen ist eine Aenderung."""
    sammel = hashlib.sha256()
    for name, inhalt in sorted(eintraege, key=lambda e: e[0]):
        sammel.update(name.encode("utf-8"))
        sammel.update(inhalt)
    return sammel.hexdigest()


def kern_modul_hash(repo_root: Path) -> Optional[str]:
    """Sammelhash des Rechenkern-Pakets im Arbeitsbaum: Code und
    Rechnungsgrundlagen ``tafeln.xml`` (``models.kernabnahme.KERN_ENDUNGEN``),
    keine andere Datei daneben."""
    verzeichnis = repo_root / ka.KERN_PAKET
    if not verzeichnis.is_dir():
        return None
    return _sammelhash([
        (d.relative_to(verzeichnis).as_posix(), d.read_bytes())
        for d in verzeichnis.rglob("*")
        if d.is_file() and ka.gehoert_zum_kernstand(d.relative_to(repo_root).as_posix())
    ])


def referenzwerte_hash(repo_root: Path) -> Optional[str]:
    """Sammelhash der eingefrorenen Kern-Referenzwerte, sortiert nach Name."""
    verzeichnis = repo_root / ka.KERN_REFERENZWERTE
    if not verzeichnis.is_dir():
        return None
    return _sammelhash([(d.name, d.read_bytes()) for d in verzeichnis.glob("*.json")])


def kernstand_hash(repo_root: Path) -> Optional[str]:
    """Sammelhash ueber die GANZE Pfadmenge des Kernstands
    (:data:`models.kernabnahme.KERNSTAND`: Code, Referenzwerte,
    Grundsatzdokumentation) — Name relativ zur Repo-Wurzel und
    Inhalt je Datei des Gegenstands (``models.kernabnahme.gehoert_zum_kernstand``).
    Der Code-Stand, gegen den ein Verweis "keine Aenderung" gehalten wird."""
    eintraege: List[Tuple[str, bytes]] = []
    for pfad in ka.kernstand_pfade():
        ort = repo_root / pfad
        if ort.is_file():
            eintraege.append((pfad, ort.read_bytes()))
        elif ort.is_dir():
            eintraege.extend(
                (d.relative_to(repo_root).as_posix(), d.read_bytes())
                for d in ort.rglob("*")
                if d.is_file() and ka.gehoert_zum_kernstand(d.relative_to(repo_root).as_posix()))
    return _sammelhash(eintraege) if eintraege else None


def kern_version(text: Optional[str]) -> Optional[str]:
    """``__version__`` aus dem Quelltext von ``kern/__init__.py`` — gelesen,
    nicht importiert (das Tool greift nicht in die Vorzeige, ADR-017)."""
    treffer = _VERSION.search(text or "")
    return treffer.group(1) if treffer else None


def _kern_alt(repo_root: Path, commit: str) -> Tuple[str, Optional[str]]:
    """Sammelhash und Version des Kern-Pakets im Commit ``commit``."""
    dateien = git_dateien(repo_root, commit, ka.KERN_PAKET)
    if dateien is None:
        raise KernstandFehler(f"die Dateien des Kerns in {commit[:12]} sind nicht lesbar")
    eintraege: List[Tuple[str, bytes]] = []
    for pfad in dateien:
        relativ = pfad[len(ka.KERN_PAKET) + 1:]
        if not ka.gehoert_zum_kernstand(pfad):
            continue
        inhalt = git_inhalt(repo_root, commit, pfad)
        if inhalt is None:
            raise KernstandFehler(f"{pfad} in {commit[:12]} ist nicht lesbar")
        eintraege.append((relativ, inhalt))
    init = dict(eintraege).get("__init__.py")
    return _sammelhash(eintraege), kern_version(init.decode("utf-8") if init else None)


def _bereich(modul: str) -> str:
    for wurzel, _, _ in ka.KERNSTAND:
        if modul == wurzel or modul.startswith(wurzel + "/"):
            return wurzel
    return modul


def _modulordnung(modul: str) -> Tuple[int, str]:
    for i, (wurzel, _, _) in enumerate(ka.KERNSTAND):
        if modul == wurzel or modul.startswith(wurzel + "/"):
            return i, modul
    return len(ka.KERNSTAND), modul


def _baue(repo_root: Path, angabe: str, von: str, begruendung: str) -> Dict[str, Any]:
    """Den Aenderungsbeleg zwischen dem Commit ``von`` und dem Arbeitsbaum bauen.

    Deterministisch: Dieselben Commits, derselbe Arbeitsbaum und dieselbe
    Begruendung ergeben denselben Beleg — darauf beruht die Nachrechnung im
    Gate. Kein Zeitstempel.
    """
    stand = git_stand(repo_root)
    if stand.get("commit") == "unbekannt":
        raise KernstandFehler("der Git-Stand des Arbeitsbaums ist nicht lesbar")
    pfade = ka.kernstand_pfade()
    fehlend = [p for p in pfade if not git_dateien(repo_root, von, p)]
    if fehlend:
        raise KernstandFehler(
            f"im Stand {von[:12]} fehlt {', '.join(fehlend)}: ein Stand in frueherer Ordnung "
            "ist kein Vergleichsstand (ADR-028); --von auf einen Stand der heutigen Ordnung setzen")
    basis = git_merge_base(repo_root, von, "HEAD")
    diffstat = git_diffstat(repo_root, von, pfade)
    commits = git_commits(repo_root, von, pfade)
    offen = git_nicht_committet(repo_root, pfade)
    verfolgt = [d for p in pfade for d in (git_dateien(repo_root, "HEAD", p) or [])]
    if diffstat is None or commits is None or offen is None:
        raise KernstandFehler(
            f"Diffstat, Commits oder Status zwischen {von[:12]} und dem Arbeitsbaum "
            "sind nicht lesbar")
    kern_alt, von_version = _kern_alt(repo_root, von)
    init = repo_root / ka.KERN_PAKET / "__init__.py"
    nach_version = kern_version(init.read_text(encoding="utf-8") if init.is_file() else None)

    module: Dict[str, Dict[str, Any]] = {}

    def modul(pfad: str) -> Optional[Dict[str, Any]]:
        name = ka.kernmodul(pfad)
        if name is None:
            return None
        return module.setdefault(name, {
            "modul": name, "bereich": _bereich(name), "hinzu": 0, "weg": 0,
            "dateien": [], "commits": [], "nicht_committet": []})

    for pfad in verfolgt:
        modul(pfad)
    for plus, minus, pfad in diffstat:
        eintrag = modul(pfad)
        if eintrag is None:
            continue
        eintrag["dateien"].append({"pfad": pfad, "hinzu": plus, "weg": minus})
        eintrag["hinzu"] += plus or 0
        eintrag["weg"] += minus or 0
    alle_commits: List[Dict[str, Any]] = []
    for c in commits:
        beruehrt = sorted({m for m in (ka.kernmodul(d) for d in c["dateien"]) if m})
        if not beruehrt:
            continue
        kurz = {"commit": c["commit"], "datum": c["datum"], "betreff": c["betreff"]}
        alle_commits.append({**kurz, "module": beruehrt})
        for name in beruehrt:
            modul(name)["commits"].append(kurz)  # type: ignore[index]
    for status, pfad in offen:
        # Nur Dateien des Gegenstands, wie im Fingerabdruck: Eine fremde,
        # nicht verfolgte Datei im Kern ist keine Aenderung des Kernstands.
        eintrag = modul(pfad) if ka.gehoert_zum_kernstand(pfad) else None
        if eintrag is not None:
            eintrag["nicht_committet"].append({"status": status, "pfad": pfad})
    geordnet = [module[n] for n in sorted(module, key=_modulordnung)]
    for eintrag in geordnet:
        eintrag["dateien"].sort(key=lambda d: d["pfad"])
        eintrag["nicht_committet"].sort(key=lambda d: d["pfad"])
    referenz_prefix = ka.KERN_REFERENZWERTE + "/"
    geaenderte_referenzwerte = sorted({
        p[len(referenz_prefix):]
        for p in [d for _, _, d in diffstat] + [p for _, p in offen]
        if p.startswith(referenz_prefix)})
    kern_jetzt = kern_modul_hash(repo_root)
    veraendert = bool(kern_alt != kern_jetzt or any(
        e["hinzu"] or e["weg"] or e["commits"] or e["nicht_committet"]
        or any(d["hinzu"] is None for d in e["dateien"]) for e in geordnet))
    return {
        "schema_version": KERN_AENDERUNG_SCHEMA_VERSION,
        "art": ART,
        "gegenstand": [{"pfad": p, "gliederung": g, "begruendung": b}
                       for p, g, b in ka.KERNSTAND],
        "von_version": von_version,
        "nach_version": nach_version,
        "kern_alt_sha256": kern_alt,
        "kern_sha256": kern_jetzt,
        "referenzwerte_sha256": referenzwerte_hash(repo_root),
        "geaenderte_referenzwerte": geaenderte_referenzwerte,
        "git": {
            "referenz": angabe,
            "referenz_commit": von,
            "merge_base": basis or "unbekannt",
            "aktuell": stand["commit"],
            "zweig": stand.get("branch", "unbekannt"),
            "dirty": stand.get("dirty", "unbekannt"),
        },
        "veraendert": veraendert,
        "module": geordnet,
        "commits": alle_commits,
        "begruendung": begruendung,
    }


def baue_aenderungsbeleg(repo_root: Path, von: str, begruendung: str) -> Dict[str, Any]:
    """Der Aenderungsbeleg vom zuletzt abgenommenen Kernstand ``von`` bis zum
    lebenden Stand. Wirft :class:`KernstandFehler` mit dem Grund."""
    try:
        commit = git_commit_von(repo_root, von)
    except GitAngabeFehler as exc:
        raise KernstandFehler(str(exc)) from exc
    if commit is None:
        raise KernstandFehler(f"--von {von!r} ist kein Commit dieses Repos")
    return _baue(repo_root, von, commit, begruendung)


def nachgerechnet(repo_root: Path, beleg: Dict[str, Any]) -> Dict[str, Any]:
    """Den Beleg aus seinen eigenen Angaben neu bauen (Nachrechnung im Gate).

    Mit dem FESTGEHALTENEN Commit, nicht der Angabe: Laeuft ``origin/main``
    nach dem Belegen weiter, bleibt der Beleg nachrechenbar.
    """
    git = beleg.get("git") if isinstance(beleg.get("git"), dict) else {}
    von = str(git.get("referenz_commit") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", von):
        raise KernstandFehler("git.referenz_commit ist kein Commit-Hash")
    return _baue(repo_root, str(git.get("referenz") or ""), von, str(beleg.get("begruendung") or ""))


def regressionsausnahme(aenderung: Dict[str, Any]) -> Dict[str, Any]:
    """Der Regressionsbeleg als benannte AUSNAHME — gebunden an den Uebergang."""
    return {
        "schema_version": KERN_REGRESSION_SCHEMA_VERSION,
        "zustand": ka.ZUSTAND_NICHT_GEFAHREN,
        "grund": ka.GRUND_NICHT_GEFAHREN,
        "grundlage": ka.AUSNAHME_GRUNDLAGE,
        **{feld: aenderung.get(feld) for feld in ka.BINDUNGSFELDER},
    }


# --------------------------------------------------------------------------- #
# Die lesbare Sicht
# --------------------------------------------------------------------------- #

#: Was mitten in einer Zeile Markup waere (Hervorhebung, Code, Verweis,
#: Tabellenzelle, Durchstreichung). Zeilenanfang-Markup (``#``, ``-``,
#: ``>``) kann hier nicht entstehen: Fremdtext steht nie am Zeilenanfang.
_MD_SONDER = re.compile(r"([\\`*_\[\]|~])")


def _md(text: Any) -> str:
    """Fremdtext (Commit-Betreff, Pfade) fuer die Sicht maskieren: HTML und
    Markdown-Zeichen, Zeilenumbrueche — ein Betreff ist Daten, kein Markup."""
    t = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = " ".join(t.split())
    return _MD_SONDER.sub(r"\\\1", t)


def _c(text: Any) -> str:
    """Fremdtext als Code-Spanne: Ihr Inhalt ist in Markdown woertlich; nur
    ein Backtick oder Zeilenumbruch koennte sie verlassen."""
    t = " ".join(str(text).replace("`", "'").split())
    return f"`{t}`"


def _zahl(wert: Any) -> str:
    return "binaer" if wert is None else str(wert)


def rendere_sicht(beleg: Dict[str, Any], regression: Optional[Dict[str, Any]]) -> str:
    """Die Sicht des Pruefers (Markdown), deterministisch aus den Belegen."""
    git = beleg.get("git") or {}
    z: List[str] = [
        "# Kernabnahme A-K2 — Kernstand des Falls", "",
        f"Zuletzt abgenommener Kernstand: {_c(git.get('referenz'))} "
        f"(Commit {_c(str(git.get('referenz_commit'))[:12])}, Version "
        f"{_md(beleg.get('von_version'))}).  ",
        f"Lebender Stand: Commit {_c(str(git.get('aktuell'))[:12])} auf "
        f"{_c(git.get('zweig'))}, Version {_md(beleg.get('nach_version'))}, "
        f"nicht committete Aenderungen im Arbeitsbaum: {_md(git.get('dirty'))}.", "",
        f"Begruendung der Vorlage: {_md(beleg.get('begruendung'))}", "",
    ]
    if not beleg.get("veraendert"):
        z += ["**Seit dem zuletzt abgenommenen Kernstand hat sich am Rechenkern "
              "nichts geaendert.** Die Abnahme bestaetigt diesen Stand fuer den Fall.", ""]
    z += ["## Pruefung 1 — Aenderungen entlang der Module", "",
          "| Modul | Zeilen hinzu | Zeilen weg | Commits | nicht committet |",
          "|---|---:|---:|---:|---:|"]
    for m in beleg.get("module") or []:
        z.append(f"| {_c(m['modul'])} | {m['hinzu']} | {m['weg']} | "
                 f"{len(m['commits'])} | {len(m['nicht_committet'])} |")
    z.append("")
    for m in beleg.get("module") or []:
        if not (m["dateien"] or m["commits"] or m["nicht_committet"]):
            continue
        z += [f"### {_c(m['modul'])}", ""]
        for d in m["dateien"]:
            z.append(f"- Datei {_c(d['pfad'])}: +{_zahl(d['hinzu'])} / -{_zahl(d['weg'])}")
        for c in m["commits"]:
            z.append(f"- Commit {_c(c['commit'][:12])} vom {_md(c['datum'])}: {_md(c['betreff'])}")
        for o in m["nicht_committet"]:
            z.append(f"- nicht committet ({_md(o['status'])}): {_c(o['pfad'])} "
                     "— ohne Commit-Beschreibung")
        z.append("")
    z += ["## Referenzwerte", "",
          f"Sammelhash: {_c(beleg.get('referenzwerte_sha256'))}.  ",
          "Bewegt: " + (", ".join(f"{_c(n)}" for n in beleg.get("geaenderte_referenzwerte") or [])
                        or "keiner") + ".", "",
          "## Pruefung 2 — Regression", ""]
    if ka.ist_ausnahme(regression):
        z += [f"**{ka.ANZEIGE_REGRESSION}.** {ka.DECKUNG_UNTER_AUSNAHME} "
              f"Grundlage: {ka.AUSNAHME_GRUNDLAGE}.", ""]
    elif regression is None:
        z += ["Regressionsbeleg liegt nicht vor.", ""]
    else:
        z += [f"Regressionsbeleg: {regression.get('vertraege_geprueft')} von "
              f"{regression.get('vertraege_gesamt')} Vertraegen durchgerechnet, "
              f"{len(regression.get('abweichungen') or [])} Abweichung(en) je Vertrag.", ""]
    z += ["## Gegenstand der Abnahme", ""]
    for g in beleg.get("gegenstand") or []:
        z.append(f"- {_c(g['pfad'])} — {_md(g['begruendung'])}")
    z += ["", "Aus dem Aenderungsbeleg erzeugt (`gates.kernstand_belegen`); massgeblich "
          "ist der Beleg, nicht diese Sicht.", ""]
    return "\n".join(z)


def _ersetze(ziel: Path, daten: bytes) -> None:
    """``daten`` atomar unter ``ziel`` ablegen (ein neuer Kernstand ersetzt
    den alten Beleg; die A-K2-Zeichnung pinnt den Hash und faellt dann)."""
    ziel.parent.mkdir(parents=True, exist_ok=True)
    raeume_schreibreste(ziel)
    tmp = ziel.parent / f".{ziel.name}.{secrets.token_hex(8)}.tmp"
    try:
        with open(tmp, "wb") as datei:
            datei.write(daten)
            datei.flush()
            os.fsync(datei.fileno())
        os.replace(tmp, ziel)
    finally:
        tmp.unlink(missing_ok=True)


def _json_bytes(daten: Dict[str, Any]) -> bytes:
    return (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


@ein_ausgabe_benannt(command=COMMAND, gate=GATE, gate_version=GATE_VERSION)
def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.kernstand_belegen",
        description="Belege der Kernabnahme A-K2: Aenderungen am Rechenkern seit "
                    "dem zuletzt abgenommenen Kernstand, Regression (Producer, kein Gate).")
    ziel = p.add_mutually_exclusive_group(required=True)
    ziel.add_argument("--fall", default=None)
    ziel.add_argument("--linie", default=None,
                      help="Linienbereich: Abnahme ausserhalb eines Falls (Erstabnahme, ADR-025)")
    p.add_argument("--repo-root", type=lebendes_repo, dest="repo_root", required=True)
    p.add_argument("--von", required=True,
                   help="der zuletzt abgenommene Kernstand (Commit-Angabe); fuer die "
                        "erste Abnahme ausdruecklich anzugeben, es gibt keine Vorgabe")
    p.add_argument("--begruendung", required=True,
                   help="Kurzbegruendung der Vorlage (warum dieser Kernstand)")
    args = p.parse_args(argv)

    def _fehler(code: int, text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate=GATE, gate_version=GATE_VERSION,
                            exit_code=code, errors=[{"code": "kernstand", "message": text}])

    from rechner_pipeline.models.standabnahme import bereich_art

    fall = Path(args.fall or args.linie)
    if bereich_art(fall) is None:
        return _fehler(Exit.USAGE, f"kein Fall- oder Linienbereich: {fall}")
    if not args.begruendung.strip():
        return _fehler(Exit.USAGE, "--begruendung ist leer")
    repo = Path(args.repo_root).resolve()
    try:
        beleg = baue_aenderungsbeleg(repo, args.von, args.begruendung.strip())
    except KernstandFehler as exc:
        return _fehler(Exit.FILE_CONTRACT, f"Kernstand nicht bestimmbar: {exc}")
    git = beleg["git"]
    if git["merge_base"] != git["referenz_commit"]:
        return _fehler(
            Exit.FILE_CONTRACT,
            f"--von {args.von!r} ist kein Vorfahre des lebenden Stands (merge-base "
            f"{git['merge_base'][:12]}) — die Differenz mischte die Aenderungen dieses "
            "Zweigs mit fremden; den Zweig auf den abgenommenen Stand bringen")
    if beleg["von_version"] is None or beleg["nach_version"] is None:
        return _fehler(Exit.FILE_CONTRACT, "die Kern-Version ist in einem der Staende nicht lesbar")

    ausgaben: Dict[str, bytes] = {ka.AENDERUNG_RELATIV: _json_bytes(beleg)}
    regression: Optional[Dict[str, Any]] = None
    if ka.REGRESSION_AUSNAHME_ERLAUBT:
        regression = regressionsausnahme(beleg)
        ausgaben[ka.REGRESSION_RELATIV] = _json_bytes(regression)
    # Die Sicht aus genau den Bytes der Belege, wie das Gate sie beim Zeichnen
    # neu erzeugt (gates.sichten, Runde G): Faellt eine Schreibstelle aus,
    # gehoeren Beleg und Sicht nicht zusammen, und A-K2 wird nicht gezeichnet.
    ausgaben[ka.SICHT_RELATIV] = rendere_sicht(
        json.loads(ausgaben[ka.AENDERUNG_RELATIV]),
        json.loads(ausgaben[ka.REGRESSION_RELATIV]) if regression is not None else None,
    ).encode("utf-8")
    for relativ, daten in ausgaben.items():
        _ersetze(fall / relativ, daten)
    summary: Dict[str, Any] = {
        "von": git["referenz"], "von_commit": git["referenz_commit"],
        "aktuell": git["aktuell"], "von_version": beleg["von_version"],
        "nach_version": beleg["nach_version"], "veraendert": beleg["veraendert"],
        "module_mit_aenderung": sum(1 for m in beleg["module"] if m["hinzu"] or m["weg"]
                                    or m["commits"] or m["nicht_committet"]),
        "commits": len(beleg["commits"]),
        "regression": (ka.ANZEIGE_REGRESSION if regression is not None else
                       "nicht geschrieben — die Ausnahme ist nicht mehr erlaubt; den "
                       "Regressionsproduzenten fahren"),
    }
    return build_result(
        command=COMMAND, gate=GATE, gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={relativ: str(fall / relativ) for relativ in ausgaben},
        summary=summary,
        output_hashes={relativ: hashlib.sha256(daten).hexdigest()
                       for relativ, daten in ausgaben.items()},
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
