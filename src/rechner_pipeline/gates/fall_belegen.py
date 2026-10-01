"""``fall_belegen`` — die Vorlagen des Lebenslaufs eines Falls: Auftrag und Abbruch.

ADR-026 (Entscheid des Maintainers 2026-10-01): Ein Fall beginnt mit dem
gezeichneten Fallauftrag (``A-M6``, Vorstand) und endet mit der
Migrationsabnahme oder dem gezeichneten Fallabbruch (``A-M5``,
Programmleitung des Falls). Dieses Kommando legt die VORLAGE beider an ihren
festen Ort und daneben eine lesbare Sicht; gezeichnet wird mit
``gates.gate_entscheid`` — das Gate rechnet jede ableitbare Angabe nach,
statt der Vorlage zu glauben, und schreibt ihren Inhalt signiert in den
Snapshot (``models.fallauftrag``).

* ``auftrag`` — WER den Fall fuehrt (Rolle und Fingerabdruck der
  Programmleitung), WAS migriert wird (Fall, Scope, die Bytes des Eingangs),
  unter welchen Mandaten simulierte Rollen handeln, auf welchem Stand des
  Zielsystems (Verweis auf die geltenden Abnahmen der Linie) und der
  benannte, heute leere Platz fuer den Aktuar des abgebenden Hauses.
* ``abbruch`` — woran der Fall scheitert, welche Gates gezeichnet waren
  (aus ``entscheide/`` gerechnet), was mit dem Bestand geschieht, wohin die
  Uebergabe geht, was die Eingangspruefung fand (woertlich; der Abbruch geht
  auch bei verletztem Eingang) und an welchem Stand er endet.

Run via::

    python -m rechner_pipeline.gates.fall_belegen auftrag --fall faelle/<fall> \\
        --linie linie --zeichnungsordnung <ordnung> \\
        --programmleitung-schluessel <datei> --programmleitung-klasse mensch|simulation \\
        [--mandat <rolle>=<datei> ...] --auftrag "<Auftragstext des Vorstands>"
    python -m rechner_pipeline.gates.fall_belegen abbruch --fall faelle/<fall> \\
        --grund "<woran der Fall scheitert>" --bestand "<was mit dem Bestand geschieht>" \\
        --uebergabe "<wohin die Uebergabe geht>" --repo-root .

Producer, kein Gate.

Knoten: system/entscheid
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.gates import stand_belegen as _stand
from rechner_pipeline.gates._common import (
    Exit,
    ToolboxResult,
    build_result,
    lies_gehasht,
    run_command,
)
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.models import fallauftrag as fa
from rechner_pipeline.models import standabnahme as sa
from rechner_pipeline.models.ordnungslinie import WURZELROLLE
from rechner_pipeline.models.schemas import P9Snapshot
from rechner_pipeline.models.zeichnung import (
    ABBRUCH_GATE,
    AUFTRAG_GATE,
    FALLROLLEN_GATES,
    PROGRAMMLEITUNG,
    ausserhalb_von,
    lade_zeichnungsordnung,
)

COMMAND = "fall_belegen"
#: 2.0.0 (ADR-026, Nachtrag Runde G): die Vorlage des Abbruchs traegt Schema 2
#: mit ``eingang_befund``; eine Vorlage nach Schema 1 nimmt das Gate nicht mehr.
GATE_VERSION = "2.0.0"


class FallBelegFehler(RuntimeError):
    """Eine Angabe der Vorlage ist nicht bestimmbar — mit dem Grund."""


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(Path(pfad).read_bytes()).hexdigest()


def fall_angaben(fall: Path) -> Dict[str, str]:
    """Name (wie jeder Snapshot ihn fuehrt) und Scope (aus ``fall.json``)."""
    return {"name": Path(fall).name, "scope": fall_mod.lade_scope(Path(fall))}


def lieferung(fall: Path) -> Dict[str, Any]:
    """Die Lieferung, wie der Fall sie bindet (ADR-002): der SHA-256 von
    ``eingang.json`` und je registrierter Quelle Name und SHA-256."""
    # Einmal lesen: Hash und Inhalt aus denselben Bytes (Review T23-01).
    gelesen = lies_gehasht(Path(fall) / fall_mod.EINGANG_REGISTER)
    register = gelesen.json()
    quellen = sorted(({"datei": q["datei"], "sha256": q["sha256"]}
                      for q in register.get("quellen") or []), key=lambda q: q["datei"])
    return {"eingang_sha256": gelesen.sha256, "quellen": quellen}


def zielsystem(linie: Optional[Path]) -> Dict[str, Any]:
    """Der Stand des Zielsystems per Verweis: je Gegenstand, den A-M4
    verlangt, die geltende ANGENOMMENE Abnahme der Linie (oder ``None``).
    Ohne Linie: benannt ohne."""
    if linie is None:
        return {"linie": None, "abnahmen": {}}
    kennung = json.loads((Path(linie) / sa.LINIE_MARKER).read_text(encoding="utf-8"))
    abnahmen: Dict[str, Optional[str]] = {}
    for g in sa.AM4_GEGENSTAENDE:
        spitze, _ = _stand.geltende_spitze(Path(linie), g.gate)
        abnahmen[g.gate] = (spitze["snapshot_sha256"]
                            if spitze is not None and spitze.get("entscheid") == "angenommen"
                            else fa.OHNE_ABNAHME)
    return {"linie": str(kennung.get("name")), "abnahmen": abnahmen}


def mandatsrollen(ordnung: Mapping[str, Any], pl_klasse: str) -> List[str]:
    """Die Rollen, deren Mandat der Auftrag nennen muss: jede simulierte Rolle
    der Ordnung ausser der Wurzel (sie handelt im Fall nur durch den Auftrag),
    dazu die Programmleitung, wenn sie simuliert ist."""
    rollen = sorted(r for r, e in (ordnung.get("rollen") or {}).items()
                    if e.get("schluesselklasse") == "simulation" and r != WURZELROLLE)
    return sorted(set(rollen) | ({PROGRAMMLEITUNG} if pl_klasse == "simulation" else set()))


def gezeichnet(fall: Path, *, ausser: str = ABBRUCH_GATE) -> List[Dict[str, str]]:
    """Welche Gates im Fall gezeichnet sind — jeder Snapshot unter
    ``entscheide/`` (strukturell gelesen), ohne die des Abbruchs selbst."""
    aus: List[Dict[str, str]] = []
    verzeichnis = Path(fall) / "entscheide"
    for pfad in sorted(verzeichnis.glob("A-*.json")) if verzeichnis.is_dir() else []:
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise FallBelegFehler(f"{pfad.name}: nicht lesbar ({exc})") from exc
        if P9Snapshot.validate_payload(daten) or \
                pfad.name != f"{daten.get('gate')}-{daten.get('snapshot_sha256')}.json":
            raise FallBelegFehler(f"{pfad.name}: kein gueltiger Snapshot")
        if daten["gate"] == ausser:
            continue
        aus.append({"gate": daten["gate"], "entscheid": daten["entscheid"],
                    "snapshot_sha256": daten["snapshot_sha256"]})
    return sorted(aus, key=lambda e: (e["gate"], e["snapshot_sha256"]))


def baue_auftrag(fall: Path, *, ordnung: Mapping[str, Any], linie: Optional[Path],
                 pl_fingerabdruck: str, pl_klasse: str, mandate: Mapping[str, str],
                 text: str) -> Dict[str, Any]:
    """Die Vorlage des Fallauftrags — oder :class:`FallBelegFehler`."""
    fingerabdruecke = {e.get("schluessel_sha256"): r
                       for r, e in (ordnung.get("rollen") or {}).items()}
    if pl_fingerabdruck in fingerabdruecke:
        raise FallBelegFehler(
            f"der Schluessel der Programmleitung gehoert in der Ordnung schon der Rolle "
            f"{fingerabdruecke[pl_fingerabdruck]!r} — die Trennung der Operatoren waere nur "
            "behauptet; die Programmleitung bekommt einen eigenen Schluessel")
    soll = mandatsrollen(ordnung, pl_klasse)
    if sorted(mandate) != soll:
        raise FallBelegFehler(
            f"Mandate fuer {sorted(mandate)} angegeben, simuliert handeln {soll} — jede "
            "simulierte Rolle des Falls handelt unter einem Mandat, das der Auftrag nennt "
            "(--mandat <rolle>=<datei>)")
    beleg = {
        "schema_version": fa.AUFTRAG_SCHEMA_VERSION,
        "art": fa.AUFTRAG_ART,
        "fall": fall_angaben(fall),
        "lieferung": lieferung(fall),
        "programmleitung": {
            "rolle": PROGRAMMLEITUNG, "schluessel_sha256": pl_fingerabdruck,
            "schluesselklasse": pl_klasse,
            "gates": sorted(g for g, r in FALLROLLEN_GATES.items() if r == PROGRAMMLEITUNG)},
        "mandate": dict(sorted(mandate.items())),
        "zielsystem": zielsystem(linie),
        "abgebendes_haus": {"aktuar": None, "vermerk": fa.ABGEBENDES_HAUS_VERMERK},
        "auftrag": text.strip(),
    }
    fehler = fa.auftrag_fehler(beleg)
    if fehler:
        raise FallBelegFehler("; ".join(fehler))
    return beleg


def baue_abbruch(fall: Path, *, repo_root: Path, grund: str, bestand: str,
                 uebergabe: str) -> Dict[str, Any]:
    """Die Vorlage des Fallabbruchs — oder :class:`FallBelegFehler`."""
    spitze, sf = _stand.geltende_spitze(Path(fall), AUFTRAG_GATE)
    if spitze is None or spitze.get("entscheid") != "angenommen":
        raise FallBelegFehler(
            "der Fall hat keinen geltenden Fallauftrag — abbrechen kann nur, wer ihn fuehrt, "
            f"und gefuehrt wird ein Fall nur mit Auftrag ({'; '.join(sf[:2]) or 'abgelehnt'})")
    beleg = {
        "schema_version": fa.ABBRUCH_SCHEMA_VERSION,
        "art": fa.ABBRUCH_ART,
        "fall": Path(fall).name,
        "fallauftrag": spitze["snapshot_sha256"],
        "grund": grund.strip(),
        "gezeichnet": gezeichnet(fall),
        # Der Abbruch geht auch bei verletztem Eingang (ADR-026, Nachtrag
        # Runde G): Der Befund steht woertlich darin, das Gate rechnet ihn nach.
        "eingang_befund": fall_mod.pruefen(Path(fall)),
        "bestand": bestand.strip(),
        "uebergabe": uebergabe.strip(),
        "stand": {"eingang_sha256": _sha256(Path(fall) / fall_mod.EINGANG_REGISTER),
                  "system": systemstand(Path(repo_root))},
    }
    fehler = fa.abbruch_fehler(beleg)
    if fehler:
        raise FallBelegFehler("; ".join(fehler))
    return beleg


def rendere_auftrag(beleg: Mapping[str, Any]) -> str:
    """Die Sicht des Vorstands auf die Vorlage (Markdown), deterministisch."""
    from rechner_pipeline.gates.kernstand_belegen import _c, _md

    pl = beleg["programmleitung"]
    ziel = beleg["zielsystem"]
    z = [f"# Fallauftrag {AUFTRAG_GATE} — {_md(beleg['fall']['name'])}", "",
         f"Scope: {_md(beleg['fall']['scope'])}.  ",
         f"Auftrag: {_md(beleg['auftrag'])}", "",
         "## Die Lieferung", "",
         f"Eingangsregister {_c(beleg['lieferung']['eingang_sha256'][:16])}; aendert sich der "
         "Eingang, gilt dieser Auftrag nicht mehr.", ""]
    z += [f"- {_c(q['datei'])} {_c(q['sha256'][:16])}" for q in beleg["lieferung"]["quellen"]]
    z += ["", "## Die Programmleitung des Falls", "",
          f"{_md(pl['rolle'])}, Schluessel {_c(pl['schluessel_sha256'][:16])}, Klasse "
          f"{_md(pl['schluesselklasse'])}; ihr Recht aus diesem Auftrag: {_md(pl['gates'])} "
          "(Fallabbruch).", "", "## Mandate simulierter Rollen", ""]
    z += [f"- {_md(r)}: {_c(s[:16])}" for r, s in beleg["mandate"].items()] or ["- keine"]
    z += ["", "## Stand des Zielsystems", ""]
    if ziel["linie"] is None:
        z.append("Ohne Linie: kein Verweis auf eine Abnahme der Linie.")
    else:
        z.append(f"Linie {_md(ziel['linie'])}:")
        z += [f"- {g}: " + (_c(s[:16]) if s else "keine Abnahme in der Linie")
              for g, s in ziel["abnahmen"].items()]
    z += ["", "## Das abgebende Haus", "", _md(beleg["abgebendes_haus"]["vermerk"]), "",
          "Aus der Vorlage erzeugt (`gates.fall_belegen auftrag`); massgeblich ist die "
          f"Vorlage und, nach der Zeichnung, der {AUFTRAG_GATE}-Snapshot.", ""]
    return "\n".join(z)


def rendere_abbruch(beleg: Mapping[str, Any]) -> str:
    """Die Sicht der Programmleitung auf die Vorlage des Abbruchs."""
    from rechner_pipeline.gates.kernstand_belegen import _c, _md

    z = [f"# Fallabbruch {ABBRUCH_GATE} — {_md(beleg['fall'])}", "",
         "Dieser Fall endet hier, ohne Abnahme.", "",
         f"Woran er scheitert: {_md(beleg['grund'])}  ",
         f"Was mit dem Bestand geschieht: {_md(beleg['bestand'])}  ",
         f"Wohin die Uebergabe geht: {_md(beleg['uebergabe'])}", "",
         f"Fallauftrag {_c(beleg['fallauftrag'][:16])}; Eingang "
         f"{_c(beleg['stand']['eingang_sha256'][:16])}; System "
         f"{_c(beleg['stand']['system']['commit'][:12])}.", "", "## Der Eingang", ""]
    if beleg["eingang_befund"]:
        z += ["Der Eingang verletzt sein Register — Befund der Eingangspruefung, woertlich:", ""]
        z += [f"- {_md(satz)}" for satz in beleg["eingang_befund"]]
    else:
        z.append("Der Eingang ist unversehrt: Er erfuellt sein Register.")
    z += ["", "## Gezeichnet waren", ""]
    z += [f"- {_md(e['gate'])} {_md(e['entscheid'])} {_c(e['snapshot_sha256'][:16])}"
          for e in beleg["gezeichnet"]] or ["- nichts ausser dem Auftrag"]
    z += ["", "Nach der Zeichnung ist im Fall nichts mehr zeichenbar.", ""]
    return "\n".join(z)


def main(argv: Optional[List[str]] = None) -> ToolboxResult:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.fall_belegen",
        description="Vorlagen des Lebenslaufs eines Falls: Fallauftrag (A-M6) und Fallabbruch "
                    "(A-M5). Producer, kein Gate.")
    unter = p.add_subparsers(dest="aktion", required=True)
    a = unter.add_parser("auftrag", help="die Vorlage des Fallauftrags")
    a.add_argument("--fall", required=True)
    a.add_argument("--linie", required=True,
                   help="Linienbereich (Pflicht, ADR-025): der Auftrag verweist auf seine "
                        "geltenden Abnahmen")
    a.add_argument("--zeichnungsordnung", required=True)
    a.add_argument("--programmleitung-schluessel", dest="pl_schluessel", required=True,
                   help="Schluesseldatei der Programmleitung (ausserhalb des Falls); nur ihr "
                        "Fingerabdruck geht in die Vorlage")
    a.add_argument("--programmleitung-klasse", dest="pl_klasse", required=True,
                   choices=["mensch", "simulation"])
    a.add_argument("--mandat", action="append", default=None,
                   help="<rolle>=<datei>: das Mandat einer simulierten Rolle (wiederholbar)")
    a.add_argument("--auftrag", required=True, help="der Auftragstext des Vorstands")
    b = unter.add_parser("abbruch", help="die Vorlage des Fallabbruchs")
    b.add_argument("--fall", required=True)
    b.add_argument("--repo-root", dest="repo_root", required=True)
    b.add_argument("--grund", required=True)
    b.add_argument("--bestand", required=True)
    b.add_argument("--uebergabe", required=True)
    args = p.parse_args(argv)

    def _fehler(code: int, text: str) -> ToolboxResult:
        return build_result(command=COMMAND, gate_version=GATE_VERSION, exit_code=code,
                            errors=[{"code": "fall_belegen", "message": text}])

    fall = Path(args.fall)
    if sa.bereich_art(fall) != "fall":
        return _fehler(Exit.USAGE, f"kein Fall-Arbeitsbereich: {fall}")
    try:
        if args.aktion == "auftrag":
            ordnung, _, of = lade_zeichnungsordnung(args.zeichnungsordnung, fall)
            if of or ordnung is None:
                return _fehler(Exit.USAGE, "; ".join(of) or "--zeichnungsordnung fehlt")
            linie = Path(args.linie)
            if sa.bereich_art(linie) != "linie":
                return _fehler(Exit.USAGE, f"kein Linienbereich: {linie}")
            pl = Path(args.pl_schluessel)
            if not pl.is_file() or not ausserhalb_von(pl, fall):
                return _fehler(Exit.USAGE, "--programmleitung-schluessel muss eine Datei "
                                           "ausserhalb des Falls sein")
            mandate: Dict[str, str] = {}
            for eintrag in args.mandat or []:
                rolle, _, datei = eintrag.partition("=")
                pfad = Path(datei)
                if not rolle or not pfad.is_file() or not ausserhalb_von(pfad, fall):
                    return _fehler(Exit.USAGE, f"--mandat {eintrag!r}: erwartet <rolle>=<datei> "
                                               "mit einer Datei ausserhalb des Falls")
                mandate[rolle] = _sha256(pfad)
            beleg = baue_auftrag(fall, ordnung=ordnung, linie=linie,
                                 pl_fingerabdruck=_sha256(pl), pl_klasse=args.pl_klasse,
                                 mandate=mandate, text=args.auftrag)
            ziel, sicht = fall / fa.AUFTRAG_RELATIV, fall / fa.AUFTRAG_SICHT_RELATIV
            text = rendere_auftrag(beleg)
        else:
            beleg = baue_abbruch(fall, repo_root=Path(args.repo_root).resolve(),
                                 grund=args.grund, bestand=args.bestand,
                                 uebergabe=args.uebergabe)
            ziel, sicht = fall / fa.ABBRUCH_RELATIV, fall / fa.ABBRUCH_SICHT_RELATIV
            text = rendere_abbruch(beleg)
    except (FallBelegFehler, fall_mod.FallFehler, OSError, ValueError, KeyError) as exc:
        return _fehler(Exit.FILE_CONTRACT, str(exc))
    daten = _stand._json_bytes(beleg)
    _stand._ersetze(ziel, daten)
    _stand._ersetze(sicht, text.encode("utf-8"))
    gate = AUFTRAG_GATE if args.aktion == "auftrag" else ABBRUCH_GATE
    return build_result(
        command=COMMAND, gate_version=GATE_VERSION, exit_code=Exit.OK,
        paths={"vorlage": str(ziel), "sicht": str(sicht)},
        summary={"gate": gate, "vorlage_sha256": hashlib.sha256(daten).hexdigest(),
                 "naechster_schritt": (
                     f"ansehen {sicht}, dann zeichnen: python -m "
                     f"rechner_pipeline.gates.gate_entscheid --fall {fall} --gate {gate} ...")},
        output_hashes={str(ziel): hashlib.sha256(daten).hexdigest()})


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(run_command(main))
