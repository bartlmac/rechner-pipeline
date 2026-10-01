"""Gemeinsame System- und P-K1-Beweisprovenienz.

Ein ueberschreibbarer ``generation_golden.gate.json``-Ledger kann nicht
beweisen, dass Gate P-K1 fuer *jede* Generation einer A-Box gelaufen ist.  Der
Ledger bleibt das Prozessprotokoll des letzten Laufs; der Abnahmebeweis ist
hingegen ein deterministischer, inhaltsadressierter Beleg je Generation.
Sein Eigenhash wird beim Lesen nachgerechnet und sein Dateiname daraus
abgeleitet.  Ein erneuter identischer Lauf ist damit idempotent, ein anderer
Stand erzeugt eine neue Datei statt einen alten Beleg zu ersetzen.

Der Systemstand verbindet den vorhandenen Git-Stand mit einem SHA-256 ueber
die tatsaechlich installierten Python-/XML-Dateien des Pakets.  ``dirty=ja``
allein waere kein exakter Stand: zwei verschiedene lokale Codeaenderungen
haetten sonst denselben Wert.

Hier liegt die EINE Subprozess-Stelle des Pakets (:func:`_git_lesen`):
lesende git-Kommandos aus einer abschliessenden Liste, fuer den
Systemstand (P-K1, P9) und seit 2026-10-01 fuer den Aenderungsbeleg der
Kernabnahme A-K2 (``gates.kernstand_belegen``).

Knoten: klv, system/assurance
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

O3_BELEG_SCHEMA_VERSION = 1
O3_BELEG_GATE = "P-K1.generations-golden-master"
O3_BELEG_COMMAND = "generation_golden"
O3_BELEG_GATE_VERSION = "1.0.0"
O3_BELEG_GLOB = "generation_golden.*.beleg.json"

_BELEG_FELDER = frozenset({
    "schema_version",
    "gate",
    "gate_version",
    "command",
    "status",
    "exit_code",
    "generation",
    "abox_sha256",
    "system",
    "input_hashes",
    "summary",
    "beleg_sha256",
})
_SYSTEM_FELDER = frozenset({
    "commit", "branch", "dirty", "quellcode_sha256",
})


def _ist_sha256(wert: object) -> bool:
    return (
        isinstance(wert, str)
        and re.fullmatch(r"[0-9a-f]{64}", wert) is not None
    )


#: Die lesenden git-Kommandos — abschliessend. Jeder Aufruf von
#: :func:`_git_lesen` nennt eines davon; was danach kommt, sind DATEN
#: (Commit-Angaben, Pfade), keine Optionen. Der Waechter
#: ``test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt`` haelt
#: die Menge mit ``==``.
#:
#: Die ersten drei protokollieren den Systemstand (P-K1, P9). Die uebrigen
#: kamen mit der Kernabnahme A-K2 (Entscheid des Maintainers 2026-10-01):
#: Der Aenderungsbeleg zeigt die Aenderungen am Rechenkern zwischen dem
#: zuletzt abgenommenen Kernstand und dem lebenden — Diffstat, Commits,
#: nicht committete Aenderungen, der alte Kern. Lesend wie die ersten drei;
#: sie rechnen und bewerten nichts, sie protokollieren, was vorliegt.
GIT_COMMIT = ("rev-parse", "HEAD")
GIT_ZWEIG = ("rev-parse", "--abbrev-ref", "HEAD")
GIT_STATUS = ("status", "--porcelain")
GIT_STATUS_PFADE = ("status", "--porcelain", "--untracked-files=all", "--")
GIT_AUFLOESEN = ("rev-parse", "--verify", "--quiet")
GIT_MERGE_BASE = ("merge-base",)
GIT_DIFFSTAT = ("diff", "--numstat", "--no-renames")
GIT_LOG = ("log", "--no-renames", "--name-only", "--format=%x1e%H%x1f%cs%x1f%s")
GIT_DATEIEN = ("ls-tree", "-r", "--name-only")
GIT_INHALT = ("show",)
LESENDE_KOMMANDOS = (
    GIT_COMMIT, GIT_ZWEIG, GIT_STATUS, GIT_STATUS_PFADE, GIT_AUFLOESEN,
    GIT_MERGE_BASE, GIT_DIFFSTAT, GIT_LOG, GIT_DATEIEN, GIT_INHALT,
)

#: Eine Commit-Angabe, wie ein Mensch sie nennt (Hash, Zweig, ``HEAD``,
#: ``origin/main``) — nie mit einem Strich vorn, damit sie keine Option
#: werden kann.
_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/^~-]*$")


class GitAngabeFehler(ValueError):
    """Eine Angabe an git, die keine Daten waere, sondern eine Option."""


def _git_lesen(repo_root: Path, kommando: Tuple[str, ...], *daten: str) -> Optional[bytes]:
    """DIE eine Subprozess-Stelle des Pakets: ein lesendes git-Kommando.

    Sie protokolliert nur Beweisprovenienz (P-K1, P9, A-K2) und beeinflusst
    keine fachliche Rechnung. ``kommando`` ist eines aus
    :data:`LESENDE_KOMMANDOS`; ``daten`` sind Commit-Angaben, ``ref:pfad``,
    Pfade oder der Trenner ``--`` — nichts davon beginnt mit einem Strich.
    Ist Git nicht verfuegbar oder scheitert das Kommando, ist die Antwort
    ``None``, und der Aufrufer benennt den Zustand.
    """
    if kommando not in LESENDE_KOMMANDOS:
        raise GitAngabeFehler(f"kein lesendes git-Kommando: {kommando!r}")
    for wert in daten:
        if wert != "--" and (not isinstance(wert, str) or not wert or wert.startswith("-")):
            raise GitAngabeFehler(f"git-Angabe {wert!r} waere eine Option, keine Angabe")
    try:
        return subprocess.run(
            ["git", *kommando, *daten],
            cwd=repo_root,
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout
    except Exception:  # noqa: BLE001 - None ist ein benannter Zustand
        return None


def _text(roh: Optional[bytes]) -> Optional[str]:
    return None if roh is None else roh.decode("utf-8", errors="replace")


def _git_stand(repo_root: Path) -> Dict[str, str]:
    """Den Git-Stand mit drei eng begrenzten, lesenden Aufrufen erfassen.

    Ist Git nicht verfuegbar, bleibt der Zustand mit ``unbekannt``
    ausdruecklich benannt.
    """
    stand: Dict[str, str] = {}
    for name, roh in (("commit", _git_lesen(repo_root, GIT_COMMIT)),
                      ("branch", _git_lesen(repo_root, GIT_ZWEIG)),
                      ("dirty", _git_lesen(repo_root, GIT_STATUS))):
        out = _text(roh)
        if out is None:
            stand[name] = "unbekannt"
            continue
        out = out.strip()
        stand[name] = ("ja" if out else "nein") if name == "dirty" else out
    return stand


def git_commit_von(repo_root: Path, angabe: str) -> Optional[str]:
    """Die Commit-Angabe ``angabe`` als vollstaendiger Hash (None = keiner)."""
    if not _REF.match(angabe or ""):
        raise GitAngabeFehler(f"Commit-Angabe {angabe!r} ist keine Angabe")
    out = _text(_git_lesen(repo_root, GIT_AUFLOESEN, f"{angabe}^{{commit}}"))
    out = (out or "").strip()
    return out if re.fullmatch(r"[0-9a-f]{40}", out) else None


def git_merge_base(repo_root: Path, a: str, b: str) -> Optional[str]:
    out = (_text(_git_lesen(repo_root, GIT_MERGE_BASE, a, b)) or "").strip()
    return out if re.fullmatch(r"[0-9a-f]{40}", out) else None


def git_diffstat(repo_root: Path, von: str, pfade: Tuple[str, ...]) -> Optional[list]:
    """Zeilen hinzu/weg je Datei zwischen ``von`` und dem ARBEITSBAUM.

    Gegen den Arbeitsbaum, nicht gegen ``HEAD``: Der Beleg bindet den Kern,
    der vorliegt (``kern_sha256``), und die Sicht muss dieselben Bytes
    zeigen. Binaerdateien tragen ``None`` als Zeilenzahl.
    """
    out = _text(_git_lesen(repo_root, GIT_DIFFSTAT, von, "--", *pfade))
    if out is None:
        return None
    zeilen = []
    for zeile in out.splitlines():
        teile = zeile.split("\t")
        if len(teile) != 3:
            continue
        plus, minus, pfad = teile
        zeilen.append((None if plus == "-" else int(plus),
                       None if minus == "-" else int(minus), pfad))
    return zeilen


def git_commits(repo_root: Path, von: str, pfade: Tuple[str, ...]) -> Optional[list]:
    """Die Commits ``von..HEAD``, die einen der Pfade beruehren, aelteste zuerst.

    Je Commit: Hash, Datum, Betreffzeile und die beruehrten Dateien. Die
    Betreffzeile ist Fremdtext — der Aufrufer behandelt sie als Daten.
    """
    out = _text(_git_lesen(repo_root, GIT_LOG, f"{von}..HEAD", "--", *pfade))
    if out is None:
        return None
    commits = []
    for block in out.split("\x1e"):
        if not block.strip():
            continue
        kopf, _, rest = block.partition("\n")
        teile = kopf.split("\x1f")
        if len(teile) != 3:
            continue
        commits.append({
            "commit": teile[0], "datum": teile[1], "betreff": teile[2],
            "dateien": sorted(z.strip() for z in rest.splitlines() if z.strip()),
        })
    commits.reverse()
    return commits


def git_nicht_committet(repo_root: Path, pfade: Tuple[str, ...]) -> Optional[list]:
    """``(status, pfad)`` jeder nicht committeten Aenderung unter den Pfaden."""
    out = _text(_git_lesen(repo_root, GIT_STATUS_PFADE, *pfade))
    if out is None:
        return None
    return [(zeile[:2].strip(), zeile[3:].strip()) for zeile in out.splitlines() if len(zeile) > 3]


def git_dateien(repo_root: Path, ref: str, pfad: str) -> Optional[list]:
    """Die Dateien unter ``pfad`` im Commit ``ref``."""
    out = _text(_git_lesen(repo_root, GIT_DATEIEN, ref, "--", pfad))
    return None if out is None else [z for z in out.splitlines() if z]


def git_inhalt(repo_root: Path, ref: str, pfad: str) -> Optional[bytes]:
    """Die Bytes der Datei ``pfad`` im Commit ``ref``."""
    return _git_lesen(repo_root, GIT_INHALT, f"{ref}:{pfad}")


#: Der produktive Stand des Rechenkerns. Entwicklung im Fall laeuft auf
#: einem Branch, der abgenommene Kern liegt auf main (Entscheid des
#: Maintainers 2026-09-16) — damit ist der ALTE Kern nicht erfunden,
#: sondern benennbar.
#:
#: Ausdruecklich der FERNE Ref, nicht der lokale (Entscheid 2026-09-16,
#: zweiter Teil): Was geteilt ist, ist produktiv; ein lokaler
#: ``main``-Ref ist eine Privatmeinung. Der Fall ist nicht theoretisch —
#: beim Aufsetzen des Reviews lag das lokale ``main`` dieses Arbeitsbaums
#: hinter ``origin/main``, und eine Regression dagegen haette gegen einen
#: Kern gerechnet, der nirgends produktiv ist. Aufgefallen waere es
#: nicht: Der Zweig enthaelt den veralteten Ref, die Aktualitaetspruefung
#: meldet gruen.
PRODUKTIVER_ZWEIG = "origin/main"


def git_stand(repo_root: Path) -> Dict[str, str]:
    """Der Git-Stand des Arbeitsbaums — oeffentlicher Name fuer ``_git_stand``.

    A-K2 haelt den Git-Teil seines Belegs gegen den LEBENDEN Stand
    (Commit); seit 2026-10-01 rechnet es den ganzen Aenderungsbeleg ueber
    dieselbe Subprozess-Stelle nach (:func:`_git_lesen`, Waechter:
    test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt).
    """
    return _git_stand(repo_root)


def zweig_ist_aktuell(vergleich: Mapping[str, str]) -> bool:
    """Liegt der Branch auf der Spitze des Referenzzweigs auf?

    Reine Funktion ueber die FESTGEHALTENEN Werte — ohne Subprozess. Seit
    2026-10-01 ist ``referenz`` der zuletzt abgenommene Kernstand
    (``kernstand_belegen --von``); liegt der lebende Stand auf ihm auf,
    zeigt die Differenz nur die Aenderungen dieses Zweigs. Das Gate rechnet
    den ganzen Beleg ueber :func:`_git_lesen` nach, den Merge-Base
    eingeschlossen.
    """
    basis, spitze = vergleich.get("merge_base"), vergleich.get("referenz_commit")
    return bool(basis) and basis == spitze and basis != "unbekannt"


def _ausgefuehrtes_paket() -> Path:
    return Path(__file__).resolve().parents[1]


def _quellcode_sha256() -> str:
    """SHA-256 des ausfuehrbaren Paketstands, pfad- und laengengetrennt."""
    return paket_sha256(_ausgefuehrtes_paket())


#: Wo im Baum unter ``--repo-root`` das Paket liegt (src-Layout).
PAKET_IM_REPO = ("src", "rechner_pipeline")


def lebendes_repo(wert: object) -> Path:
    """``--repo-root`` aufloesen — und verlangen, dass der Baum das Paket
    traegt, das gerade rechnet (Pruefrunde G, G12).

    Der ``type`` jedes ``--repo-root`` der Schicht gates (Ratsche in
    ``tests/test_repo_root_lebendes_paket.py``): EINE Stelle, durch die jeder
    Pfad muss. Befund: Den lebenden Stand von Kern (A-K2) und Tarifwerk
    (A-T1) rechnete das System aus den Dateien unter ``--repo-root``, Commit
    und ``dirty`` des Systemstands ebenfalls — das Paket, das rechnet, kam
    ueber ``PYTHONPATH`` von woanders. A-M4 meldete "keine Aenderung seit
    Abnahme", waehrend ein anderer Kern rechnete. A-O1 nahm schon das
    importierte Modul.

    Verlangt wird INHALTSGLEICHHEIT, nicht derselbe Ort: derselbe Hash wie
    der Systemstand (``_quellcode_sha256``) ueber ``<repo_root>/src/
    rechner_pipeline``. Ein nicht editierbar installiertes Paket neben
    seinem Repo bleibt moeglich. Kein Schalter zum Abschalten.

    Grenze, benannt: Gehalten wird das Paket (``.py``, ``.xml``). Was der
    lebende Stand ausserhalb des Pakets liest — Configs und Tarifplaene des
    Tarifwerks (A-T1), Referenzwerte und Grundsatzdokumentation des
    Kernstands —, liest er aus ``--repo-root``; dass der rechnende Code
    dieselben Dateien liest, sichert die Inhaltsgleichheit des Pakets nicht.

    ``argparse.ArgumentTypeError`` mit beiden Hashes und dem Ausweg — der
    Parser macht daraus den Aufruffehler (Exit 2).
    """
    import argparse

    repo = Path(str(wert)).resolve()
    paket = repo.joinpath(*PAKET_IM_REPO)
    if not (paket / "__init__.py").is_file():
        raise argparse.ArgumentTypeError(
            f"{repo} traegt kein Paket unter {'/'.join(PAKET_IM_REPO)} — der lebende Stand "
            "ist der des Codes, der rechnet (Pruefrunde G). Ausweg: --repo-root auf den Baum "
            f"des ausgefuehrten Pakets ({_ausgefuehrtes_paket().parents[1]})")
    soll, ist = _quellcode_sha256(), paket_sha256(paket)
    if soll != ist:
        raise argparse.ArgumentTypeError(
            f"{repo} ist nicht das ausgefuehrte Paket: unter --repo-root liegt "
            f"{'/'.join(PAKET_IM_REPO)} mit dem Hash {ist[:16]}, ausgefuehrt wird "
            f"{_ausgefuehrtes_paket()} mit {soll[:16]} — der lebende Stand (Kern, Tarifwerk, "
            "Systemstand) waere der eines anderen Codes als dessen, der rechnet (Pruefrunde "
            "G). Ausweg: --repo-root auf den Baum des ausgefuehrten Pakets "
            f"({_ausgefuehrtes_paket().parents[1]}), oder PYTHONPATH bzw. die Installation "
            f"auf {paket.parent}")
    return repo


def paket_sha256(paket: Path) -> str:
    """SHA-256 eines Paketbaums, pfad- und laengengetrennt (``.py``, ``.xml``)."""
    paket = Path(paket)
    dateien = sorted(
        pfad for pfad in paket.rglob("*")
        if pfad.is_file() and pfad.suffix in {".py", ".xml"}
    )
    h = hashlib.sha256()
    for pfad in dateien:
        relativ = pfad.relative_to(paket).as_posix().encode("utf-8")
        inhalt = pfad.read_bytes()
        h.update(len(relativ).to_bytes(8, "big"))
        h.update(relativ)
        h.update(len(inhalt).to_bytes(8, "big"))
        h.update(inhalt)
    return h.hexdigest()


def systemstand(repo_root: Path) -> Dict[str, str]:
    """Den fuer P-K1 und P9 gemeinsam vergleichbaren Systemstand liefern."""
    return {**_git_stand(repo_root), "quellcode_sha256": _quellcode_sha256()}


def _beleg_hash(kern: Mapping[str, Any]) -> str:
    kanonisch = json.dumps(
        kern,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(kanonisch.encode("utf-8")).hexdigest()


def _generation_dateiname(generation: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]+", "-", generation).strip("-")
    if not name:
        raise ValueError("P-K1-Beleg: Generation ergibt keinen Dateinamen")
    return name


def pk1_beleg_dateiname(generation: str, beleg_sha256: str) -> str:
    """Den einzigen gueltigen Dateinamen eines P-K1-Belegs ableiten."""
    return (
        f"generation_golden.{_generation_dateiname(generation)}."
        f"{beleg_sha256}.beleg.json"
    )


def schreibe_pk1_beleg(
    diagnostics_dir: Path,
    *,
    gate_version: str,
    status: str,
    exit_code: int,
    generation: str,
    abox_sha256: str,
    system: Mapping[str, str],
    input_hashes: Mapping[str, str],
    summary: Mapping[str, Any],
) -> Path:
    """Einen gruenen P-K1-Beleg exklusiv und inhaltsadressiert schreiben."""
    kern: Dict[str, Any] = {
        "schema_version": O3_BELEG_SCHEMA_VERSION,
        "gate": O3_BELEG_GATE,
        "gate_version": gate_version,
        "command": O3_BELEG_COMMAND,
        "status": status,
        "exit_code": exit_code,
        "generation": generation,
        "abox_sha256": abox_sha256,
        "system": dict(system),
        "input_hashes": dict(input_hashes),
        "summary": dict(summary),
    }
    beleg_sha256 = _beleg_hash(kern)
    daten = {**kern, "beleg_sha256": beleg_sha256}
    fehler = _pruefe_o3_beleg_daten(daten)
    if fehler:
        raise ValueError("P-K1-Beleg ungueltig: " + "; ".join(fehler))

    diagnostics_dir.mkdir(parents=True, exist_ok=True)
    ziel = diagnostics_dir / pk1_beleg_dateiname(generation, beleg_sha256)
    payload = (
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    from rechner_pipeline.gates._common import schreibe_exklusiv

    try:
        schreibe_exklusiv(ziel, payload)
    except FileExistsError:
        if ziel.read_bytes() != payload:
            raise ValueError(
                f"P-K1-Beleg {ziel.name} existiert mit anderem Inhalt - "
                "ein inhaltsadressierter Beleg wird nie ueberschrieben"
            )
    return ziel


def _pruefe_o3_beleg_daten(daten: object) -> list[str]:
    fehler: list[str] = []
    if not isinstance(daten, dict):
        return ["Inhalt ist kein JSON-Objekt"]

    felder = set(daten)
    if felder != _BELEG_FELDER:
        fehlt = sorted(_BELEG_FELDER - felder)
        fremd = sorted(felder - _BELEG_FELDER)
        if fehlt:
            fehler.append(f"Pflichtfelder fehlen: {fehlt}")
        if fremd:
            fehler.append(f"unbekannte Felder: {fremd}")
    if (
        type(daten.get("schema_version")) is not int
        or daten.get("schema_version") != O3_BELEG_SCHEMA_VERSION
    ):
        fehler.append(
            f"schema_version muss {O3_BELEG_SCHEMA_VERSION} sein"
        )
    if daten.get("gate") != O3_BELEG_GATE:
        fehler.append(f"gate muss {O3_BELEG_GATE!r} sein")
    if daten.get("gate_version") != O3_BELEG_GATE_VERSION:
        fehler.append(
            f"gate_version muss {O3_BELEG_GATE_VERSION!r} sein"
        )
    if daten.get("command") != O3_BELEG_COMMAND:
        fehler.append(f"command muss {O3_BELEG_COMMAND!r} sein")
    if daten.get("status") != "passed":
        fehler.append("status muss 'passed' sein")
    exit_code = daten.get("exit_code")
    if type(exit_code) is not int or exit_code != 0:
        fehler.append("exit_code muss die ganze Zahl 0 sein")
    generation = daten.get("generation")
    if (
        not isinstance(generation, str)
        or re.fullmatch(r"[a-z0-9_]+/[a-z0-9_]+", generation) is None
    ):
        fehler.append(
            "generation muss eine Knoten-ID <familie>/<generation> sein"
        )
    if not _ist_sha256(daten.get("abox_sha256")):
        fehler.append("abox_sha256 ist kein vollstaendiger SHA-256")

    system = daten.get("system")
    if not isinstance(system, dict):
        fehler.append("system muss ein Objekt sein")
    else:
        if set(system) != _SYSTEM_FELDER:
            fehler.append(
                f"system muss exakt die Felder {sorted(_SYSTEM_FELDER)} tragen"
            )
        if any(not isinstance(wert, str) or not wert for wert in system.values()):
            fehler.append("alle Systemstand-Werte muessen nichtleer sein")
        if not _ist_sha256(system.get("quellcode_sha256")):
            fehler.append("system.quellcode_sha256 ist kein SHA-256")

    input_hashes = daten.get("input_hashes")
    if not isinstance(input_hashes, dict) or not input_hashes:
        fehler.append("input_hashes muss ein nichtleeres Objekt sein")
    else:
        for schluessel, wert in input_hashes.items():
            if not isinstance(schluessel, str) or not schluessel:
                fehler.append("input_hashes enthaelt einen leeren Pfadschluessel")
            if not _ist_sha256(wert):
                fehler.append(
                    f"input_hashes[{schluessel!r}] ist kein SHA-256"
                )
        if input_hashes.get("abgeleitet/abox/abox.json") != daten.get(
            "abox_sha256"
        ):
            fehler.append(
                "input_hashes bindet nicht dieselbe A-Box wie abox_sha256"
            )

    summary = daten.get("summary")
    if not isinstance(summary, dict):
        fehler.append("summary muss ein Objekt sein")
    else:
        if summary.get("generation") != generation:
            fehler.append("summary.generation weicht von generation ab")
        if summary.get("abox_sha256") != daten.get("abox_sha256"):
            fehler.append("summary.abox_sha256 weicht von abox_sha256 ab")
        if summary.get("system") != system:
            fehler.append("summary.system weicht vom Systemstand ab")

    beleg_sha256 = daten.get("beleg_sha256")
    if not _ist_sha256(beleg_sha256):
        fehler.append("beleg_sha256 ist kein vollstaendiger SHA-256")
    else:
        kern = {k: v for k, v in daten.items() if k != "beleg_sha256"}
        if _beleg_hash(kern) != beleg_sha256:
            fehler.append("beleg_sha256 stimmt nicht mit dem Inhalt ueberein")
    return fehler


def pruefe_pk1_beleg(pfad: Path) -> Tuple[Optional[dict], list[str]]:
    """Einen P-K1-Beleg samt Eigenhash und abgeleitetem Dateinamen pruefen."""
    try:
        daten = json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{pfad.name}: nicht als JSON lesbar: {exc}"]

    fehler = _pruefe_o3_beleg_daten(daten)
    if isinstance(daten, dict):
        generation = daten.get("generation")
        beleg_sha256 = daten.get("beleg_sha256")
        if isinstance(generation, str) and _ist_sha256(beleg_sha256):
            try:
                erwartet = pk1_beleg_dateiname(generation, beleg_sha256)
            except ValueError as exc:
                fehler.append(f"Dateiname nicht ableitbar: {exc}")
            else:
                if pfad.name != erwartet:
                    fehler.append(
                        f"Dateiname {pfad.name!r} stimmt nicht mit dem "
                        f"Beleginhalt ueberein (erwartet {erwartet!r})"
                    )
    return daten if isinstance(daten, dict) else None, [
        f"{pfad.name}: {meldung}" for meldung in fehler
    ]
