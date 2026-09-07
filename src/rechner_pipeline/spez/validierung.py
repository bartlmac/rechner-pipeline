"""Spez-gegen-A-Box-Validierung: die Spez ist Projektion, nicht Quelle.

Jeder Wert der Spez muss in der A-Box belegt sein (gleicher Wert,
gleiche Zelle) — sonst haette Stage 2 still eine eigene Wahrheit
eingefuehrt. Das ist P6 auf der Spez: geprueft wird gegen die A-Box
als Referenz, nicht gegen Plausibilitaet.

Repo-Idiom: ``validate_spez(...) -> List[str]`` (leer = in Ordnung);
Ablage deterministisch neben der A-Box im Fall-Arbeitsbereich.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Set

from rechner_pipeline.ontologie.aussage import Zustand
from rechner_pipeline.ontologie.merge import werte_gleich
from rechner_pipeline.ontologie.tbox import TBOX_VERSION, ABox, PFLICHT_PARAMETER
from rechner_pipeline.spez.schema import SPEZ_VERSION, TarifSpez

SPEZ_DATEI = "spez.json"


def spez_pfad(fall: Path, generation: str) -> Path:
    name = generation.replace("/", "-")
    return fall / "abgeleitet" / "spez" / f"{name}.{SPEZ_DATEI}"


def speichere_spez(spez: TarifSpez, fall: Path) -> Path:
    pfad = spez_pfad(fall, spez.generation)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    daten = spez.model_dump(mode="json", exclude_none=True)
    pfad.write_text(
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pfad


def lade_spez_aus_bytes(roh: bytes) -> TarifSpez:
    """Spez aus bereits gelesenen Bytes (Review T23-01): Ein Gate, das die
    Spez hasht UND parst, tut beides aus denselben Bytes.

    Fail-closed bei fehlender Versionsdeklaration (Review T23-02): Der
    Modell-Default gilt fuer die Konstruktion, nie fuer die Deserialisierung
    — eine Spez-Datei ohne ``spez_version``/``tbox_version`` gilt nicht
    still als aktuell (siehe ontologie.abox.lade_aus_bytes).
    """
    daten = json.loads(roh)
    if not isinstance(daten, dict):
        raise ValueError("Spez: kein JSON-Objekt")
    fehlend = [k for k in ("spez_version", "tbox_version") if k not in daten]
    if fehlend:
        raise ValueError(
            f"Spez ohne Versionsdeklaration ({', '.join(fehlend)}) — aus der "
            "A-Box neu erzeugen (spez.erzeugen), nicht still als aktuell "
            "einstufen"
        )
    return TarifSpez.model_validate_json(roh)


def lade_spez(fall: Path, generation: str) -> TarifSpez:
    return lade_spez_aus_bytes(spez_pfad(fall, generation).read_bytes())


def validate_spez(spez: TarifSpez, abox: ABox) -> List[str]:
    fehler: List[str] = []
    # Die Spez-Datei muss das geltende Spez-Schema tragen (Review T23-02:
    # der Default machte "nicht deklariert" und "aktuell" ununterscheidbar,
    # und verglichen wurde spez_version bisher nirgends).
    if spez.spez_version != SPEZ_VERSION:
        fehler.append(
            f"spez_version: Spez traegt {spez.spez_version!r}, geltend ist "
            f"{SPEZ_VERSION!r} — die Spez ist aus der A-Box neu zu erzeugen "
            "(spez.erzeugen)"
        )
    # Spez, A-Box und Code muessen dieselbe T-Box sprechen (Review T22-02).
    if spez.tbox_version != abox.tbox_version or spez.tbox_version != TBOX_VERSION:
        fehler.append(
            f"tbox_version: Spez {spez.tbox_version!r}, A-Box "
            f"{abox.tbox_version!r}, geltend {TBOX_VERSION!r} — die Spez ist "
            "aus der A-Box neu zu erzeugen (spez.erzeugen), oder die "
            "T-Box-Aenderung geht ueber A-K1"
        )
    gen = next((g for g in abox.generationen if g.id == spez.generation), None)
    if gen is None:
        fehler.append(f"Generation {spez.generation!r} nicht in der A-Box")
        return fehler

    unisex_abox = (
        str(gen.unisex.wert)
        if gen.unisex is not None and gen.unisex.zustand is Zustand.BELEGT
        else None
    )
    if spez.unisex != unisex_abox:
        fehler.append(
            f"unisex: Spez sagt {spez.unisex!r}, A-Box {unisex_abox!r}"
        )

    abox_zellen = {z.id: z for z in gen.zellen}
    spez_zellen = {s.knoten.rsplit("/", 1)[-1]: s for s in spez.zellen}
    if set(abox_zellen) != set(spez_zellen):
        fehler.append(
            f"Zellenmengen weichen ab: A-Box {sorted(abox_zellen)}, "
            f"Spez {sorted(spez_zellen)}"
        )
        return fehler

    ableitungen = {a.name: a for a in spez.tafel_ableitungen}
    benutzte_ableitungen: set = set()
    for zid, spez_zelle in sorted(spez_zellen.items()):
        abox_zelle = abox_zellen[zid]
        if spez_zelle.knoten != f"{gen.id}/{zid}":
            fehler.append(f"{zid}: Knoten {spez_zelle.knoten!r} falsch gebaut")
        # Rueckrichtung (Vollstaendigkeit): jedes Pflichtfeld der T-Box
        # muss in der Spez stehen — ein geloeschtes Feld liesse den Kern
        # sonst still mit seinem Default rechnen.
        for pflicht in PFLICHT_PARAMETER:
            if pflicht not in spez_zelle.model_point:
                fehler.append(
                    f"{gen.id}/{zid}/{pflicht}: Pflichtfeld fehlt in der "
                    "Spez — der Kern wuerde still mit dem Default rechnen"
                )
        for feld, wert in spez_zelle.model_point.items():
            aussage = abox_zelle.parameter.get(feld)
            if aussage is None or aussage.zustand is not Zustand.BELEGT:
                fehler.append(
                    f"{gen.id}/{zid}/{feld}: in der Spez gesetzt, in der "
                    "A-Box nicht belegt — die Spez hat eine eigene Wahrheit"
                )
                continue
            if feld == "tafel":
                # Finaler Name = A-Box-Basis + ggf. Unisex-Ableitung.
                erwartet = (
                    f"{aussage.wert}_{spez.unisex}" if spez.unisex
                    else str(aussage.wert)
                )
                if wert != erwartet:
                    fehler.append(
                        f"{gen.id}/{zid}/tafel: Spez {wert!r}, erwartet "
                        f"{erwartet!r} (A-Box-Basis {aussage.wert!r})"
                    )
                elif spez.unisex:
                    if wert not in ableitungen:
                        fehler.append(
                            f"{gen.id}/{zid}/tafel: Unisex-Tafel {wert!r} "
                            "ohne Ableitungsregel in der Spez"
                        )
                    else:
                        benutzte_ableitungen.add(wert)
                        ableitung = ableitungen[wert]
                        basis = str(aussage.wert)
                        if (ableitung.basis_m != f"{basis}_M"
                                or ableitung.basis_f != f"{basis}_F"):
                            fehler.append(
                                f"Tafel-Ableitung {wert}: Basen "
                                f"{ableitung.basis_m}/{ableitung.basis_f} "
                                f"passen nicht zur A-Box-Basis {basis!r}"
                            )
            elif not werte_gleich(wert, aussage.wert):
                fehler.append(
                    f"{gen.id}/{zid}/{feld}: Spez {wert!r} != A-Box "
                    f"{aussage.wert!r}"
                )

    for ableitung in spez.tafel_ableitungen:
        if ableitung.name not in benutzte_ableitungen:
            fehler.append(
                f"Tafel-Ableitung {ableitung.name}: keine Zelle nutzt sie "
                "(verwaiste Ableitung)"
            )
        erwartet_anteil = (
            int(spez.unisex[1:]) / 100.0 if spez.unisex else None
        )
        if erwartet_anteil is None:
            fehler.append(
                f"Tafel-Ableitung {ableitung.name}: ohne Unisex-Vorgabe"
            )
        elif not werte_gleich(ableitung.maenneranteil, erwartet_anteil):
            fehler.append(
                f"Tafel-Ableitung {ableitung.name}: Maenneranteil "
                f"{ableitung.maenneranteil} != Vorgabe {erwartet_anteil}"
            )
    return fehler
