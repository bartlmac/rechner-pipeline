"""Zeichnungsordnung und Schluessel fuer Tests — nach ADR-018.

Eine Annahme braucht seit ADR-018 eine Zeichnungsordnung (Schema 2) und
einen Schluessel, aus dem die Rolle BESTIMMT wird. Dieser Helfer legt
beides je Testfall an: eine simulierte Rolle ``mensch/aktuariat``
(Schluesselklasse ``simulation``) und optional weitere Rollen.

Die Rolle zeichnet die Gates des Falls (:data:`FALL_GATES`), NICHT die des
Betriebs (A-B1, A-B2): Ein Schluessel, der Migrations- und Betriebsabnahmen
zugleich zeichnet, verdeckte genau den Fall, den die Rollenregel der Leser
prueft (Entscheid 2026-10-01; Ratsche in tests/test_abnahme_rolle_klasse.py).
Wer A-B1 zeichnet, legt die Ordnung mit ``rolle="mensch/betrieb"`` an.

Ebenso wenig zeichnet sie den Kernstand: A-K2 gehoert ``mensch/rechenkern``
(ADR-018), mit eigenem Schluessel neben dem Fall (``p9-rechenkern.key``).
Jede Standardordnung fuehrt diese Rolle mit; :func:`annahme_args` legt
beide Schluessel in den Ring — A-M4 prueft die Signatur der A-K2-Annahme,
auf der es gruendet —, und :func:`zeichne_kernstand` legt den Kernstand
eines Falls vor und zeichnet ihn (Entscheid des Maintainers 2026-10-01:
jeder Fall traegt sein A-K2). :func:`zeichne_tboxstand` tut dasselbe fuer
den T-Box-Stand (A-O1, mensch/architektur), sobald die Versionslinie der
T-Box einen Uebergang hat; :func:`zeichne_stand` zeichnet beides.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

VA = "mensch/aktuariat"
QUELLE = "mensch/quell-aktuar"
AGENT = "agent/programmleitung"
RECHENKERN = "mensch/rechenkern"
ARCHITEKTUR = "mensch/architektur"

_STANDARD_SCHLUESSEL = b"test-only-p9-authorization-key!" * 2
#: Der Schluessel der Rolle mensch/rechenkern — getrennt je Rolle.
_RECHENKERN_SCHLUESSEL = b"test-only-p9-rechenkern-key-ak2!" * 2
#: Der Schluessel der Rolle mensch/architektur (A-O1) — getrennt je Rolle.
_ARCHITEKTUR_SCHLUESSEL = b"test-only-p9-architektur-key-o1!" * 2
#: Dateinamen der getrennten Schluessel neben dem Fall.
RECHENKERN_SCHLUESSEL_DATEI = "p9-rechenkern.key"
ARCHITEKTUR_SCHLUESSEL_DATEI = "p9-architektur.key"
#: Die Gates der Rollen der Standabnahme (models.standabnahme): je Gate eine
#: eigene Rolle mit eigenem Schluessel — Rolle, Gate, Schluesseldatei, Inhalt.
STANDROLLEN = (
    (RECHENKERN, "A-K2", RECHENKERN_SCHLUESSEL_DATEI, _RECHENKERN_SCHLUESSEL),
    (ARCHITEKTUR, "A-O1", ARCHITEKTUR_SCHLUESSEL_DATEI, _ARCHITEKTUR_SCHLUESSEL),
)
RECHENKERN_GATES = ["A-K2"]


def _fall_gates() -> List[str]:
    from rechner_pipeline.models.zeichnung import GUELTIGE_GATES

    eigene = {gate for _, gate, _, _ in STANDROLLEN}
    return [g for g in GUELTIGE_GATES if g not in ("A-B1", "A-B2") and g not in eigene]


#: Die Gates der Standardrolle: alle zeichenbaren ausser denen des Betriebs
#: und der Standabnahme (A-K2, A-O1).
FALL_GATES: List[str] = _fall_gates()


def schluessel_anlegen(pfad: Path, inhalt: bytes = _STANDARD_SCHLUESSEL) -> str:
    """Schluesseldatei (0600) anlegen; Rueckgabe: Fingerabdruck."""
    if not pfad.exists():
        pfad.write_bytes(inhalt)
        pfad.chmod(0o600)
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def ordnung_schreiben(pfad: Path, rollen: Dict[str, dict]) -> Path:
    pfad.write_text(json.dumps({"schema_version": 2, "rollen": rollen}),
                    encoding="utf-8")
    return pfad


def standard_ordnung(
    verzeichnis: Path,
    schluessel: Path,
    *,
    klasse: str = "simulation",
    rolle: str = VA,
    gates: Optional[List[str]] = None,
    weitere: Optional[Dict[str, dict]] = None,
) -> Path:
    """Ordnung mit einer zeichnenden Rolle fuer diesen Schluessel — und der
    Rolle mensch/rechenkern mit ihrem eigenen Schluessel daneben."""
    fp = schluessel_anlegen(schluessel)
    rollen = {rolle: {"schluessel_sha256": fp, "schluesselklasse": klasse,
                      "gates": gates if gates is not None else list(FALL_GATES)}}
    for name, gate, datei, inhalt in STANDROLLEN:
        if rolle == name:
            continue
        eigener_fp = schluessel_anlegen(schluessel.parent / datei, inhalt)
        if eigener_fp != fp:
            rollen[name] = {"schluessel_sha256": eigener_fp, "schluesselklasse": klasse,
                            "gates": [gate]}
    rollen.update(weitere or {})
    return ordnung_schreiben(verzeichnis / "zeichnungsordnung.json", rollen)


def annahme_args(fall: Path, **kw) -> List[str]:
    """``--zeichnungsordnung ... --freigabe-schluessel ...`` fuer einen Fall.

    Ordnung und Schluessel liegen NEBEN dem Fall (ausserhalb, wie es die
    Ordnung verlangt), je Fall genau einmal angelegt.
    """
    fuer = kw.pop("fuer", None)
    schluessel = fall.parent / "p9-freigabe.key"
    ordnung = fall.parent / "zeichnungsordnung.json"
    if not ordnung.exists():
        standard_ordnung(fall.parent, schluessel, **kw)
    # Der Ring: alle Schluessel, der zeichnende zuletzt. A-K2 zeichnet
    # mensch/rechenkern, A-O1 mensch/architektur, jedes andere Gate die
    # Standardrolle; A-M4 prueft mit dem Ring die Signaturen der Annahmen,
    # auf denen es gruendet.
    eigene = {gate: fall.parent / datei for _, gate, datei, _ in STANDROLLEN}
    if fuer in eigene:
        ring = [eigene[fuer]]
    else:
        ring = [d for d in eigene.values() if d.exists()] + [schluessel]
    args = ["--zeichnungsordnung", str(ordnung)]
    for datei in ring:
        args += ["--freigabe-schluessel", str(datei)]
    # Eine simulierte Rolle handelt unter einem Mandat — Pflicht seit
    # Review T22-07 (ADR-018): das Mandat liegt wie die Ordnung neben dem Fall.
    if kw.get("klasse", "simulation") == "simulation":
        args += ["--mandat", str(mandat_datei(fall))]
    return args


def mandat_datei(fall: Path) -> Path:
    """Das Mandatsdokument der simulierten Rolle dieses Falls (einmal angelegt)."""
    mandat = fall.parent / "mandat.md"
    if not mandat.exists():
        mandat.write_text(
            "Mandat der Vorzeige: die simulierte Rolle prueft die Vorlagen "
            "und zeichnet die Gates dieses Falls.\n", encoding="utf-8")
    return mandat


def zeichne_kernstand(fall: Path, repo_root: Path, *, von: str = "HEAD", **kw):
    """Den Kernstand eines Falls vorlegen und als mensch/rechenkern zeichnen.

    ``von`` = der zuletzt abgenommene Kernstand; in der Suite ``HEAD`` — der
    Kern des lebenden Stands gilt als abgenommen, der Beleg sagt "nichts
    geaendert" (oder nennt, was im Arbeitsbaum offen ist). Der gemeinsame
    Weg fuer jeden Test, der A-M4 zeichnet (Entscheid 2026-10-01), statt
    je Test. Setzt eine A-Box und P-Q3 voraus wie jede Annahme.
    """
    from rechner_pipeline.gates import gate_entscheid, kernstand_belegen

    beleg = kernstand_belegen.main([
        "--fall", str(fall), "--repo-root", str(repo_root), "--von", von,
        "--begruendung", "Kernstand des Falls (Suite)"])
    assert beleg.exit_code == 0, beleg.errors
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-K2", "--entscheid", "angenommen",
        "--entscheider", "rechenkern-verantwortung",
        "--begruendung", "Aenderungen am Kernstand qualitativ geprueft",
        "--repo-root", str(repo_root), *annahme_args(fall, fuer="A-K2", **kw)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def zeichne_tboxstand(fall: Path, repo_root: Path, **kw):
    """Den T-Box-Stand eines Falls vorlegen und als mensch/architektur zeichnen.

    Das Gegenstueck zu :func:`zeichne_kernstand` fuer den zweiten Gegenstand
    der Standabnahme (``models.standabnahme``): Hat die Versionslinie der
    T-Box einen Uebergang (seit 0.2.0), verlangt A-M4 je Fall ein A-O1 —
    der Beleg kommt vom Produzenten (``gates.stand_belegen tbox``), die
    Stellungnahme legt (simuliert) das Aktuariat. Alles wird LEBEND
    gerechnet: Modul-Hash, Versionen, Artefakt-Hash; ein Vermerk im Fall
    dient als Artefakt, damit keine Datei des Repos festgeschrieben ist.
    Solange die Linie ein Element hat (Weg c, Basislinie), tut der Helfer
    nichts und gibt None zurueck.
    """
    import json

    from rechner_pipeline.gates import gate_entscheid, stand_belegen
    from rechner_pipeline.ontologie import tbox

    if stand_belegen.basislinie_gilt():
        return None
    vermerk = fall / "abgeleitet" / "tbox" / "vermerk-suite.md"
    vermerk.parent.mkdir(parents=True, exist_ok=True)
    vermerk.write_text(
        f"Aenderungsvermerk der Suite: T-Box {tbox.TBOX_VERSIONEN[-2]} -> "
        f"{tbox.TBOX_VERSION}.\n", encoding="utf-8")
    beleg = stand_belegen.main([
        "tbox", "--fall", str(fall), "--repo-root", str(repo_root),
        "--artefakt", "abgeleitet/tbox/vermerk-suite.md",
        "--begruendung", "T-Box-Stand des Falls (Suite)"])
    assert beleg.exit_code == 0, beleg.errors
    (fall / stand_belegen.TBOX_STELLUNGNAHME_RELATIV).write_text(json.dumps({
        "schema_version": 1, "nach_version": tbox.TBOX_VERSION,
        "verfasser_rolle": "mensch/aktuariat",
        "felder": [{"name": "tarifwerk", "wirkung": "bewertungsrelevant",
                    "begruendung": "Tarifwerk der Generation als belegte Aussage (Suite)"}],
    }), encoding="utf-8")
    ergebnis = gate_entscheid.main([
        "--fall", str(fall), "--gate", "A-O1", "--entscheid", "angenommen",
        "--entscheider", "it-verantwortung",
        "--begruendung", "Diffs der T-Box geprueft (Suite)",
        "--repo-root", str(repo_root), *annahme_args(fall, fuer="A-O1", **kw)])
    assert ergebnis.exit_code == 0, ergebnis.errors
    return ergebnis


def zeichne_stand(fall: Path, repo_root: Path, **kw):
    """Den ganzen Stand eines Falls zeichnen: T-Box-Stand (A-O1, falls die
    Linie einen Uebergang hat) und Kernstand (A-K2). Der gemeinsame Weg fuer
    jeden Test, der A-M4 zeichnet."""
    zeichne_tboxstand(fall, repo_root, **kw)
    return zeichne_kernstand(fall, repo_root, **kw)
