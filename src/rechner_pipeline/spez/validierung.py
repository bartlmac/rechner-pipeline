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
from rechner_pipeline.ontologie.tbox import (
    GENERATIONS_BLOECKE,
    PFLICHT_PARAMETER,
    TBOX_VERSION,
    ABox,
)
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
    # NICHTS RECHNET AUF EINER SPEZ, DEREN VOKABULAR ES NICHT KENNT. Dieser
    # Lader ist die eine Tuer jedes Lesers (Ratsche:
    # tests/test_spez_lader_klasse.py) — die Bestandsstrecke las die Spez
    # bis T-Box 0.2.0 ohne jede Versionspruefung, und eingefrorene Spez
    # einer frueheren T-Box liefen dort gruen durch. Ein Mismatch ist ein
    # Fehler, keine Warnung (wie P-Q3 und P-K1), mit dem Ausweg.
    if daten["spez_version"] != SPEZ_VERSION or daten["tbox_version"] != TBOX_VERSION:
        raise SpezVersionFehler(
            f"Spez spricht T-Box {daten['tbox_version']!r} / Spez-Schema "
            f"{daten['spez_version']!r}, geltend sind {TBOX_VERSION!r} / "
            f"{SPEZ_VERSION!r} — verweigert. Ausweg: aus der A-Box neu "
            "erzeugen (spez.erzeugen) oder ueber einen deklarierten Uebergang "
            "heben (spez.validierung.hebe_spez_auf_geltende_version)"
        )
    return TarifSpez.model_validate_json(roh)


class SpezVersionFehler(ValueError):
    """Die Spez spricht ein anderes Vokabular als der Code."""


def lade_spez(fall: Path, generation: str) -> TarifSpez:
    return lade_spez_aus_bytes(spez_pfad(fall, generation).read_bytes())


def _hebe_spez_0_1_0_auf_0_2_0(daten: dict) -> dict:
    """T-Box 0.1.0 -> 0.2.0 ist fuer die Spez additiv: ``tarifwerk``,
    ``quellverfahren`` und ``urteil.geaenderte_tarifwerksmerkmale`` sind
    optional und bleiben leer (nicht erhoben — wie bei der gehobenen A-Box).
    Nur die Version wandert; das Spez-Schema bleibt."""
    return {**daten, "tbox_version": "0.2.0"}


#: Hebungsregeln der Spez je Schritt der T-Box-Versionslinie — dieselbe
#: Linie wie ``ontologie.abox.HEBUNGEN`` (Test: jeder Schritt hat eine).
SPEZ_HEBUNGEN = {
    ("0.1.0", "0.2.0"): _hebe_spez_0_1_0_auf_0_2_0,
}


def spez_bytes(daten: dict) -> bytes:
    """Die kanonische Form einer Spez-Datei (wie :func:`speichere_spez`)."""
    return (json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def hebe_spez_auf_geltende_version(roh: bytes) -> bytes:
    """Die Bytes einer Spez der Vorversion(en) auf die geltende T-Box heben —
    nur ueber deklarierte Uebergaenge, nur fuer das geltende Spez-Schema.

    Der benannte Weg fuer eine Spez, zu der keine A-Box vorliegt (etwa die
    eingefrorenen Spez der Baldrian-Laeufe); eine Spez MIT A-Box wird neu
    erzeugt. Das Ergebnis besteht den Lader; schreibt nichts.
    """
    from rechner_pipeline.ontologie.tbox import TBOX_VERSIONEN

    daten = json.loads(roh)
    if not isinstance(daten, dict) or "tbox_version" not in daten:
        raise ValueError("Spez ohne Versionsdeklaration — nicht hebbar, neu erzeugen")
    if daten.get("spez_version") != SPEZ_VERSION:
        raise ValueError(
            f"Spez-Schema {daten.get('spez_version')!r} ist nicht das geltende "
            f"{SPEZ_VERSION!r} — keine Hebung deklariert, neu erzeugen")
    linie = tuple(TBOX_VERSIONEN)
    von = daten["tbox_version"]
    if von == TBOX_VERSION:
        raise ValueError(f"Spez spricht bereits die geltende T-Box {TBOX_VERSION!r}")
    if von not in linie:
        raise ValueError(
            f"Spez traegt T-Box {von!r}; die Versionslinie {linie!r} kennt keinen "
            "Uebergang von dort — neu erzeugen")
    for schritt in zip(linie[linie.index(von):], linie[linie.index(von) + 1:]):
        regel = SPEZ_HEBUNGEN.get(schritt)
        if regel is None:
            raise ValueError(f"kein deklarierter Uebergang {schritt[0]} -> {schritt[1]}")
        daten = regel(daten)
    neu = spez_bytes(daten)
    lade_spez_aus_bytes(neu)        # muss den Lader bestehen
    return neu


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
            "T-Box-Aenderung geht ueber A-O1"
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

    # Tarifwerk und Quellverfahren (T-Box 0.2.0), beide Richtungen: Jeder
    # Wert der Spez ist in der A-Box belegt und gleich; jedes belegte
    # Merkmal der A-Box steht in der Spez — fehlt es, rechnete die Fuehrung
    # still mit der Vorgabe des eigenen Geschaefts.
    for block in GENERATIONS_BLOECKE:
        abox_block = {
            m: a.wert for m, a in gen.block(block).items()
            if a.zustand is Zustand.BELEGT
        }
        spez_block = getattr(spez, block)
        for merkmal in sorted(set(abox_block) | set(spez_block)):
            if merkmal not in abox_block:
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: in der Spez gesetzt "
                    f"({spez_block[merkmal]!r}), in der A-Box nicht belegt — "
                    "die Spez hat eine eigene Wahrheit")
            elif merkmal not in spez_block:
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: in der A-Box belegt "
                    f"({abox_block[merkmal]!r}), fehlt in der Spez — die "
                    "Fuehrung rechnete sonst still mit der Vorgabe")
            elif not (type(spez_block[merkmal]) is type(abox_block[merkmal])
                      and werte_gleich(spez_block[merkmal], abox_block[merkmal])):
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: Spez "
                    f"{spez_block[merkmal]!r} != A-Box {abox_block[merkmal]!r}")

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
