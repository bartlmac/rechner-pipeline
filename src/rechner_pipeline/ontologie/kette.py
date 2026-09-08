"""Ketten-Pruefung: die A-Box muss aus ihren Fragmenten folgen.

Die Systempruefung fand den Merge als einzigen unprotokollierten
Uebergang der Kette: nichts band abox.json an die Extraktions-Fragmente
— eine direkt editierte A-Box (geloeschte Widersprueche, verschobene
Werte) haette alle Gates passiert. Diese Pruefung schliesst das:

Der Merge laeuft als CLI mit Ledger (``gates.abox_merge``), der die
Fragment-Hashes, Akteure und den Erhebungszeitpunkt festhaelt. Hier
wird die Kette deterministisch nachgerechnet: Merge aus den Fragmenten
wiederholen und die gespeicherte A-Box dagegen halten — erlaubt sind
AUSSCHLIESSLICH Abweichungen, die aus dokumentierten
Diskrepanz-Aufloesungen folgen (gewaehlter Wert einer Lesart, Provenienz
aus dieser Lesart). Alles andere ist ein Befund.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from rechner_pipeline.models.zeichnung import validiere_zeichnung
from rechner_pipeline.ontologie.abox import lade
from rechner_pipeline.ontologie.aussage import Aussage, Zustand
from rechner_pipeline.ontologie.befuellung import QuellFragment, baue_abox
from rechner_pipeline.ontologie.merge import werte_gleich
from rechner_pipeline.ontologie.tbox import ABox
from rechner_pipeline.models.manifest import lies_gehasht

FRAGMENTE_ORDNER = "fragmente"
MERGE_LEDGER = "abox_merge.gate.json"


def fragmente_ordner(fall: Path) -> Path:
    return fall / "abgeleitet" / "abox" / FRAGMENTE_ORDNER


def fragment_pfade(fall: Path) -> List[Path]:
    """Die Fragmentdateien eines Falls in stabiler Reihenfolge (ohne
    ``akteure.json``); leer, wenn es den Ordner nicht gibt."""
    ordner = fragmente_ordner(fall)
    if not ordner.is_dir():
        return []
    return [
        p for p in sorted(ordner.glob("*.json")) if p.name != "akteure.json"
    ]


def fragment_aus_bytes(roh: bytes) -> QuellFragment:
    """Fragment aus bereits gelesenen Bytes (Review T23-01): Wer ein
    Fragment hasht UND parst, tut beides aus denselben Bytes."""
    return QuellFragment.model_validate_json(roh)


def lade_fragmente(fall: Path) -> Dict[str, QuellFragment]:
    return {
        p.name: fragment_aus_bytes(p.read_bytes()) for p in fragment_pfade(fall)
    }


def _vergleiche_aussage(
    ort: str,
    ist: Aussage,
    soll: Aussage,
    aufgeloeste: Dict[str, object],
    fehler: List[str],
) -> None:
    """Ist-Aussage gegen den Merge-Stand halten.

    Identisch ist immer erlaubt. Abweichung ist NUR erlaubt, wenn der
    Merge-Stand widerspruechlich war und eine dokumentierte Aufloesung
    genau den Ist-Wert gewaehlt hat.
    """
    if ist.model_dump(mode="json") == soll.model_dump(mode="json"):
        return
    if soll.zustand is Zustand.WIDERSPRUECHLICH:
        entscheidung = aufgeloeste.get(soll.diskrepanz_id)
        if entscheidung is None:
            fehler.append(
                f"{ort}: weicht vom Merge-Stand ab, aber die Diskrepanz "
                f"{soll.diskrepanz_id!r} ist nicht aufgeloest"
            )
            return
        if ist.zustand is not Zustand.BELEGT or not werte_gleich(
            ist.wert, entscheidung.gewaehlter_wert
        ):
            fehler.append(
                f"{ort}: {ist.wert!r} entspricht nicht dem entschiedenen "
                f"Wert {entscheidung.gewaehlter_wert!r}"
            )
            return
        passende_lesarten = [
            lesart for lesart in soll.lesarten
            if werte_gleich(lesart.wert, entscheidung.gewaehlter_wert)
        ]
        erlaubte_provenienzen = {
            p.model_dump_json()
            for lesart in passende_lesarten for p in lesart.provenienz
        }
        belegte_provenienzen = {
            p.model_dump_json() for p in ist.provenienz
        }
        if not (belegte_provenienzen & erlaubte_provenienzen):
            fehler.append(
                f"{ort}: kein Beleg aus einer Lesart mit dem entschiedenen "
                f"Wert {entscheidung.gewaehlter_wert!r} vorhanden"
            )
            return
        fremde = [
            p for p in ist.provenienz
            if p.model_dump_json() not in erlaubte_provenienzen
        ]
        if fremde:
            fehler.append(
                f"{ort}: Provenienz stammt aus keiner Lesart mit dem "
                f"entschiedenen Wert {entscheidung.gewaehlter_wert!r} "
                "— Beleg einer verworfenen Lesart oder eingeschleuster Beleg"
            )
        return
    fehler.append(
        f"{ort}: weicht vom Merge-Stand ab ohne dokumentierte Aufloesung "
        f"(Merge: {soll.zustand.value}/{soll.wert!r}, "
        f"A-Box: {ist.zustand.value}/{ist.wert!r})"
    )


def pruefe_kette(
    fall: Path, *, abox: Optional[ABox] = None, register: Optional[dict] = None,
) -> List[str]:
    """A-Box gegen Fragmente + Merge-Ledger pruefen (leer = in Ordnung).

    Ohne Fragmente (synthetische/gebaute A-Box) meldet die Pruefung das
    als eigenen Zustand — der Aufrufer entscheidet, ob das zulaessig ist.

    ``abox``/``register``: A-Box und Eingang-Register, die der Aufrufer
    bereits aus den fuer den Beleg gehashten Bytes geparst hat (Review
    T23-01) — dann prueft die Kette genau diese Bytes und liest keine der
    beiden Dateien ein zweites Mal.
    """
    import hashlib

    # Fragmente einmal lesen: Hash-Abgleich mit dem Merge-Ledger und
    # Merge-Nachbau aus denselben Bytes (Review T23-01) — ein Pruefer, der
    # andere Bytes vergleicht als er hasht, prueft nicht.
    gelesene = {p.name: lies_gehasht(p) for p in fragment_pfade(fall)}
    fragmente = {n: fragment_aus_bytes(g.roh) for n, g in gelesene.items()}
    ledger_pfad = fall / "abgeleitet" / "diagnostics" / MERGE_LEDGER
    if not fragmente:
        return ["keine_fragmente"]
    if not ledger_pfad.is_file():
        return [
            "Fragmente vorhanden, aber kein Merge-Ledger "
            f"({ledger_pfad.name}) — die A-Box ist nicht an die "
            "Extraktion gebunden; Merge ueber gates.abox_merge fahren"
        ]
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    summary = ledger.get("summary", {})
    akteure = summary.get("akteure", {})
    erhoben_am = summary.get("erhoben_am", "")
    fragment_hashes = summary.get("fragment_hashes", {})

    fehler: List[str] = []
    ordner = fragmente_ordner(fall)
    for name in sorted(fragmente):
        ist_hash = gelesene[name].sha256
        if fragment_hashes.get(name) != ist_hash:
            fehler.append(
                f"Fragment {name}: Hash weicht vom Merge-Ledger ab — "
                "nach dem Merge veraendert oder Merge nicht wiederholt"
            )
    if set(fragment_hashes) != set(fragmente):
        fehler.append(
            f"Fragmentmenge weicht vom Merge-Ledger ab "
            f"(Ledger: {sorted(fragment_hashes)}, "
            f"vorhanden: {sorted(fragmente)})"
        )
    if fehler:
        return fehler

    if register is None:
        register = json.loads(
            (fall / "eingang.json").read_text(encoding="utf-8")
        )
    namen = sorted(fragmente)
    try:
        soll_abox = baue_abox(
            str(fall),
            [fragmente[n] for n in namen],
            register,
            [akteure[n] for n in namen],
            erhoben_am,
        )
    except KeyError as exc:
        return [f"Merge-Ledger ohne Akteur fuer Fragment {exc}"]

    ist_abox = abox if abox is not None else lade(fall)
    soll_gen = {g.id: g for g in soll_abox.generationen}
    ist_gen = {g.id: g for g in ist_abox.generationen}
    if set(soll_gen) != set(ist_gen):
        return [
            f"Generationen weichen ab (Merge: {sorted(soll_gen)}, "
            f"A-Box: {sorted(ist_gen)})"
        ]

    # Diskrepanzen: Menge und Lesarten muessen dem Merge entsprechen;
    # Status/Entscheidung sind der legitime Freiheitsgrad — die WAHL. Ihre
    # Rollenbindung ist es nicht (Review T23-06): eine Aufloesung, die eine
    # Schluesselklasse behauptet, unterliegt derselben Regel wie die CLI.
    soll_d = {d.id: d for d in soll_abox.diskrepanzen}
    ist_d = {d.id: d for d in ist_abox.diskrepanzen}
    for did, d in sorted(ist_d.items()):
        if d.entscheidung is not None and d.entscheidung.zeichnung is not None:
            for f in validiere_zeichnung(d.entscheidung.zeichnung, form="beide"):
                fehler.append(f"Diskrepanz {did}: Rollenbindung der Aufloesung — {f}")
    if set(soll_d) != set(ist_d):
        fehler.append(
            f"Diskrepanzenmenge weicht ab (Merge: {sorted(soll_d)}, "
            f"A-Box: {sorted(ist_d)}) — geloeschte oder erfundene "
            "Widersprueche"
        )
    aufgeloeste = {
        d.id: d.entscheidung for d in ist_abox.diskrepanzen
        if d.status == "aufgeloest" and d.entscheidung is not None
    }
    for d_id in sorted(set(soll_d) & set(ist_d)):
        if ([l.model_dump(mode="json") for l in soll_d[d_id].lesarten]
                != [l.model_dump(mode="json") for l in ist_d[d_id].lesarten]):
            fehler.append(f"Diskrepanz {d_id}: Lesarten veraendert")

    for gen_id in sorted(set(soll_gen) & set(ist_gen)):
        soll, ist = soll_gen[gen_id], ist_gen[gen_id]
        if [d.model_dump(mode="json") for d in soll.dimensionen] != \
           [d.model_dump(mode="json") for d in ist.dimensionen]:
            fehler.append(f"{gen_id}: Dimensionen veraendert")
        if soll.quellnamen != ist.quellnamen:
            fehler.append(f"{gen_id}: Quellnamen-Mapping veraendert")
        if soll.anmerkungen != ist.anmerkungen:
            fehler.append(f"{gen_id}: Anmerkungen veraendert")
        soll_z = {z.id: z for z in soll.zellen}
        ist_z = {z.id: z for z in ist.zellen}
        if set(soll_z) != set(ist_z):
            fehler.append(f"{gen_id}: Zellenmenge veraendert")
            continue
        for zid in sorted(soll_z):
            felder_soll = soll_z[zid].parameter
            felder_ist = ist_z[zid].parameter
            if set(felder_soll) != set(felder_ist):
                fehler.append(
                    f"{gen_id}/{zid}: Feldmenge veraendert "
                    f"(+{sorted(set(felder_ist) - set(felder_soll))} "
                    f"-{sorted(set(felder_soll) - set(felder_ist))})"
                )
                continue
            for feld in sorted(felder_soll):
                _vergleiche_aussage(
                    f"{gen_id}/{zid}/{feld}",
                    felder_ist[feld], felder_soll[feld],
                    aufgeloeste, fehler,
                )
        if (soll.unisex is None) != (ist.unisex is None):
            fehler.append(f"{gen_id}: unisex erfunden oder geloescht")
        elif soll.unisex is not None:
            _vergleiche_aussage(
                f"{gen_id}/unisex", ist.unisex, soll.unisex,
                aufgeloeste, fehler,
            )
    return fehler
