"""Coverage: welcher Anteil des Pflichtumfangs ist belegt — und woher (P6).

Der gefaehrliche Fehler ist nicht die falsche Extraktion, sondern die
stillschweigend fehlende. Deshalb wird gegen den PFLICHTUMFANG der
T-Box gemessen (nicht gegen das, was zufaellig extrahiert wurde):
je Zelle und Pflichtfeld der Zustand, je Feld die Quellenlage
(nur Meldung / nur Rechner / beide) aus der Provenienz.

Reine Berechnung, deterministisch, JSON-faehig — der Bericht ist ein
Gate-Artefakt, keine Prosa.

Knoten: klv
"""

from __future__ import annotations

from typing import Any, Dict

from rechner_pipeline.ontologie.aussage import Aussage, Zustand
from rechner_pipeline.ontologie.tbox import (
    ABox,
    GENERATIONS_BLOECKE,
    PFLICHT_PARAMETER,
    Tarifgeneration,
    tarifregeln_luecken,
)


def _quellenlage(aussage: Aussage, arten_je_datei: Dict[str, str]) -> str:
    arten = sorted({
        arten_je_datei.get(p.quelle_datei, "unbekannt")
        for p in aussage.provenienz
    } | {
        arten_je_datei.get(p.quelle_datei, "unbekannt")
        for lesart in aussage.lesarten
        for p in lesart.provenienz
    })
    return "+".join(arten) if arten else "-"


def coverage_generation(gen: Tarifgeneration) -> Dict[str, Any]:
    """Pflichtfeld-Abdeckung einer Generation, je Zelle und gesamt."""
    arten_je_datei = {q.datei: q.art for q in gen.quellen}
    zellen: Dict[str, Any] = {}
    # fehlt_in_extraktion ist ein EIGENER Zaehler: "gesucht, nicht da"
    # (nicht_belegt, aktive Agenten-Aussage) und "nie erwaehnt" (der
    # gefaehrliche stille Fall) duerfen im Aggregat nicht verschmelzen.
    zaehler = {z.value: 0 for z in Zustand}
    zaehler["fehlt_in_extraktion"] = 0
    for zelle in gen.zellen:
        felder: Dict[str, Any] = {}
        for feld in PFLICHT_PARAMETER:
            aussage = zelle.parameter.get(feld)
            if aussage is None:
                # Nicht einmal als nicht_belegt erfasst: die Extraktion
                # hat das Feld uebersehen — genau der stille Fall.
                felder[feld] = {"zustand": "fehlt_in_extraktion", "quellen": "-"}
                zaehler["fehlt_in_extraktion"] += 1
                continue
            felder[feld] = {
                "zustand": aussage.zustand.value,
                "quellen": _quellenlage(aussage, arten_je_datei),
            }
            zaehler[aussage.zustand.value] += 1
        zellen[zelle.id] = felder
    pflicht_gesamt = len(PFLICHT_PARAMETER) * len(gen.zellen)
    bericht: Dict[str, Any] = {
        "generation": gen.id,
        "pflichtfelder": len(PFLICHT_PARAMETER),
        "zellen": zellen,
        "zaehler": zaehler,
        "pflicht_gesamt": pflicht_gesamt,
        "belegt_quote": (
            zaehler[Zustand.BELEGT.value] / pflicht_gesamt
            if pflicht_gesamt else 0.0
        ),
        "vollstaendig": zaehler[Zustand.BELEGT.value] == pflicht_gesamt,
    }
    # Generationsweite Bloecke (T-Box 0.2.0): je Merkmal der Zustand, und
    # "fehlt_in_extraktion", wenn keine Quelle das Merkmal auch nur nannte.
    # AUSGEWIESEN; ``vollstaendig`` bleibt der Pflichtumfang der Parameter.
    # Fuer eine Bestandsmigration sind die Bloecke Pflicht — das Urteil steht
    # unter ``tarifregeln_bestand`` und blockiert P-Q3 im Scope ``bestand``
    # (die Coverage kennt den Scope nicht, das Gate schon). Ein nicht
    # erhobenes Tarifwerk ist damit sichtbar statt still durch die Vorgabe
    # des eigenen Geschaefts ersetzt.
    belegt: Dict[str, Dict[str, Any]] = {}
    erhoben: Dict[str, Any] = {}
    for block, bereiche in GENERATIONS_BLOECKE.items():
        belegt[block] = {m: a.wert for m, a in gen.block(block).items()
                         if a.zustand is Zustand.BELEGT}
        erhoben[block] = set(gen.block(block))
        aussagen = gen.block(block)
        eintraege = {}
        for merkmal in bereiche:
            aussage = aussagen.get(merkmal)
            eintraege[merkmal] = (
                {"zustand": "fehlt_in_extraktion", "quellen": "-"}
                if aussage is None else
                {"zustand": aussage.zustand.value,
                 "quellen": _quellenlage(aussage, arten_je_datei)}
            )
        bericht[block] = eintraege
        bericht[f"{block}_vollstaendig"] = all(
            e["zustand"] == Zustand.BELEGT.value for e in eintraege.values())
    luecken = tarifregeln_luecken(belegt, erhoben)
    bericht["tarifregeln_bestand"] = {
        "vollstaendig": not luecken, "luecken": luecken}
    return bericht


def coverage_bericht(abox: ABox) -> Dict[str, Any]:
    berichte = [coverage_generation(g) for g in abox.generationen]
    return {
        "fall": abox.fall,
        "tbox_version": abox.tbox_version,
        "generationen": berichte,
        "diskrepanzen_offen": sum(
            1 for d in abox.diskrepanzen if d.status == "offen"
        ),
        "vollstaendig": all(b["vollstaendig"] for b in berichte),
        **{
            f"{block}_vollstaendig": all(b[f"{block}_vollstaendig"] for b in berichte)
            for block in GENERATIONS_BLOECKE
        },
        "tarifregeln_bestand_vollstaendig": all(
            b["tarifregeln_bestand"]["vollstaendig"] for b in berichte),
    }
