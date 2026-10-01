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
    befunde = regelwert_befunde(daten)
    if befunde:
        raise SpezRegelwertFehler(
            "Spez " + repr(daten.get("generation")) + ": " + "; ".join(befunde)
            + ". Die Spez fuehrt jede Tarifregel als Wert ihres Wertebereichs "
            "oder — fuer ein Merkmal, das nur erhoben sein muss — als "
            "ausdrueckliche Feststellung 'nicht_belegt'; null ist weder das "
            "eine noch das andere. Ausweg: die Spez aus der A-Box neu erzeugen "
            "(spez.erzeugen) bzw. fuer eine Spez ohne A-Box die Feststellung mit "
            "Fundstelle eintragen (spez.validierung.ergaenze_tarifregeln); "
            "dass es keinen Wert gibt, heisst 'nicht_belegt'.")
    return TarifSpez.model_validate_json(roh)


class SpezVersionFehler(ValueError):
    """Die Spez spricht ein anderes Vokabular als der Code."""


class SpezRegelwertFehler(ValueError):
    """Ein Wert in ``tarifwerk``/``quellverfahren`` liegt ausserhalb des
    Vokabulars der T-Box (falscher Typ, ausserhalb des Bereichs, null,
    unbekanntes Merkmal)."""


def regelwert_befunde(daten: dict) -> List[str]:
    """Jeder Wert der Bloecke ``tarifwerk`` und ``quellverfahren`` gegen den
    Wertebereich der T-Box — mit Merkmal und erlaubtem Bereich je Befund.

    Vorher (Pruefrunde H, bekannter Punkt a) verweigerte der Lader einen
    Dynamiksatz ``null`` mit einem rohen Pydantic-Fehler ohne Ausweg, und ein
    Wert ausserhalb des Bereichs ging durch den Lader und fiel erst an der
    Tuer der Bestandsstrecke (``spez.tarifregeln.tarifregeln_der_spez``) —
    im Scope ``tarif`` nie. Dieselbe Regel wie dort (``tbox.wert_im_bereich``,
    typstreng), jetzt fuer JEDEN Leser.
    """
    from rechner_pipeline.ontologie.tbox import (
        BESTAND_ERHOBEN,
        BLOCK_TITEL,
        bereich_text,
        wert_im_bereich,
    )
    from rechner_pipeline.spez.tarifregeln import (
        NICHT_BELEGT,
        ist_feststellung_nicht_belegt,
    )

    befunde: List[str] = []
    for block, bereiche in GENERATIONS_BLOECKE.items():
        werte = daten.get(block, {})
        if not isinstance(werte, dict):
            befunde.append(f"{block} ist kein Objekt (Merkmal -> Wert), sondern {werte!r}")
            continue
        for merkmal, wert in sorted(werte.items()):
            if merkmal not in bereiche:
                befunde.append(f"{block}.{merkmal} ist kein Merkmal des "
                               f"{BLOCK_TITEL[block]}s (bekannt: {sorted(bereiche)})")
            elif ist_feststellung_nicht_belegt(block, merkmal, wert):
                continue
            elif wert is None or not wert_im_bereich(wert, bereiche[merkmal]):
                erlaubt = bereich_text(bereiche[merkmal])
                if merkmal in BESTAND_ERHOBEN.get(block, ()):
                    erlaubt += f" oder die Feststellung {NICHT_BELEGT!r}"
                befunde.append(f"{block}.{merkmal} = {json.dumps(wert)} liegt nicht im "
                               f"Wertebereich {erlaubt}")
    return befunde


def lade_spez(fall: Path, generation: str) -> TarifSpez:
    return lade_spez_aus_bytes(spez_pfad(fall, generation).read_bytes())


class SpezHebungFehler(ValueError):
    """Die Datei traegt, was ihre Version nicht kennen kann — keine Hebung."""


def _hebe_spez_0_1_0_auf_0_2_0(daten: dict) -> dict:
    """T-Box 0.1.0 -> 0.2.0 ist fuer die Spez additiv: ``tarifwerk``,
    ``quellverfahren`` und ``urteil.geaenderte_tarifwerksmerkmale`` sind
    optional und bleiben leer (nicht erhoben — wie bei der gehobenen A-Box).
    Nur die Version wandert; das Spez-Schema bleibt.

    EINE HEBUNG TRAEGT NUR, WAS IM ALTEN ARTEFAKT STEHEN KANN (Pruefrunde H,
    H13; ADR-024, Nachtrag "Regel der Hebung"). Vorher uebernahm die Regel
    Bloecke aus dem 0.2.0-Vokabular aus einer Datei, die sich 0.1.0 nannte:
    Tarifregeln ohne Fundstelle und ohne A-Box standen danach in einer
    geltenden Spez, und der Weg ueber die Feststellung mit Fundstelle
    (:func:`ergaenze_tarifregeln`) war versperrt ("bereits Tarifregeln").
    Eine solche Datei ist keine 0.1.0-Datei; sie wird benannt verweigert —
    auch mit leerem Block, denn schon der Schluessel gehoert nicht zu 0.1.0.
    """
    fremd = [k for k in GENERATIONS_BLOECKE if k in daten]
    if "geaenderte_tarifwerksmerkmale" in (daten.get("urteil") or {}):
        fremd.append("urteil.geaenderte_tarifwerksmerkmale")
    if fremd:
        raise SpezHebungFehler(
            f"Spez nennt T-Box '0.1.0', traegt aber {fremd} aus dem Vokabular "
            "von 0.2.0 — das kann eine 0.1.0-Datei nicht tragen; eine Hebung "
            "traegt nur, was im alten Artefakt steht, und erfindet keine "
            "Tarifregeln ohne Beleg. Ausweg: die Regeln ueber die A-Box bringen "
            "(P-Q3, spez.erzeugen) oder — fuer eine Spez ohne A-Box — die "
            "Bloecke entfernen, heben und die Feststellung mit Fundstelle "
            "eintragen (spez.validierung.ergaenze_tarifregeln).")
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


def ergaenze_tarifregeln(roh: bytes, regeln: dict) -> bytes:
    """Die Tarifregeln eines abgenommenen Laufs in eine eingefrorene Spez
    OHNE A-Box eintragen — der benannte Weg fuer die Testfixtures der
    Baldrian-Laeufe (ADR-024, Nachtrag), neben :func:`hebe_spez_auf_geltende_version`.

    Eine Spez MIT A-Box bekommt ihre Regeln nur ueber die A-Box (P-Q3,
    ``spez.erzeugen``; P-K1 haelt beide Richtungen). Die eingefrorenen Spez
    haben keine; ihre Regeln standen bis hierher als Schalter in den
    Testaufrufen und sind die im Lauf festgestellten (A-Q1). ``regeln`` ist
    das Dokument dieser Feststellung: je Block und Merkmal ein Eintrag mit
    ``fundstelle`` (ohne Fundstelle kein Beleg) und ENTWEDER ``wert`` (belegt)
    ODER ``zustand: "nicht_belegt"`` (ausdruecklich festgestellt, dass es
    keinen gibt — wie die A-Box es fuehrt; Pruefrunde G). Ein weggelassenes
    Merkmal ist nicht erhoben. Dieselbe Projektion wie ``spez.erzeugen``
    (``spez.tarifregeln.spez_block``). Verweigert, wenn die Spez schon Regeln
    traegt (kein Ueberschreiben), nicht die geltende T-Box spricht, ein
    Eintrag nicht diese Form hat oder das Ergebnis die Tarifregeln einer
    Bestandsmigration nicht vollstaendig traegt — jede Verweigerung als
    ``ValueError`` mit Namen und Ausweg. Schreibt nichts.
    """
    from types import SimpleNamespace

    from rechner_pipeline.spez.tarifregeln import (
        NICHT_BELEGT,
        spez_block,
        tarifregeln_der_spez,
    )

    daten = json.loads(roh)
    if not isinstance(daten, dict) or daten.get("tbox_version") != TBOX_VERSION:
        raise ValueError(
            "Spez spricht nicht die geltende T-Box — erst heben "
            "(hebe_spez_auf_geltende_version)")
    if any(daten.get(block) for block in GENERATIONS_BLOECKE):
        raise ValueError(
            "Spez traegt bereits Tarifregeln — nicht ueberschreiben; eine andere "
            "Regel ist eine neue Feststellung (A-Box, spez.erzeugen)")
    if regeln.get("generation") != daten.get("generation"):
        raise ValueError(
            f"Regeln fuer {regeln.get('generation')!r}, Spez ist "
            f"{daten.get('generation')!r}")
    for block in GENERATIONS_BLOECKE:
        feststellungen = {}
        for merkmal, eintrag in sorted((regeln.get(block) or {}).items()):
            wo = f"{block}.{merkmal}"
            if not isinstance(eintrag, dict) or not str(eintrag.get("fundstelle") or "").strip():
                raise ValueError(f"{wo}: ohne Fundstelle kein Beleg")
            unbekannt = sorted(set(eintrag) - {"wert", "zustand", "fundstelle"})
            if unbekannt:
                raise ValueError(f"{wo}: unbekannte Felder {unbekannt} — ein Eintrag "
                                 "traegt fundstelle und wert ODER zustand")
            if "wert" in eintrag and "zustand" in eintrag:
                raise ValueError(f"{wo}: traegt beides, wert und zustand — belegt "
                                 "ODER ausdruecklich nicht belegt")
            if "zustand" in eintrag:
                if eintrag["zustand"] != NICHT_BELEGT:
                    raise ValueError(
                        f"{wo}: zustand {eintrag['zustand']!r} — ausdrueckbar ist nur "
                        f"{NICHT_BELEGT!r}; was mehrdeutig oder widerspruechlich ist, "
                        "wird in der A-Box entschieden, nicht hier")
                feststellungen[merkmal] = SimpleNamespace(
                    zustand=Zustand.NICHT_BELEGT, wert=None)
                continue
            if "wert" not in eintrag:
                raise ValueError(
                    f"{wo}: weder wert noch zustand — belegt heisst "
                    '{"wert": ..., "fundstelle": ...}, ausdruecklich nicht belegt '
                    f'{{"zustand": "{NICHT_BELEGT}", "fundstelle": ...}}')
            if eintrag["wert"] is None:
                raise ValueError(
                    f"{wo}: wert ist null — null ist kein Beleg; dass es keinen "
                    f'Wert gibt, heisst {{"zustand": "{NICHT_BELEGT}", "fundstelle": ...}}')
            feststellungen[merkmal] = SimpleNamespace(
                zustand=Zustand.BELEGT, wert=eintrag["wert"])
        daten[block] = spez_block(block, feststellungen)
    neu = spez_bytes(daten)
    tarifregeln_der_spez(lade_spez_aus_bytes(neu))   # Lader und Pflicht
    return neu


def validate_spez(spez: TarifSpez, abox: ABox) -> List[str]:
    from rechner_pipeline.spez.tarifregeln import spez_block as projiziere

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
    # Die Rueckrichtung haelt die EINE Projektion (spez.tarifregeln.spez_block):
    # auch die Feststellung "nicht belegt" eines zu erhebenden Merkmals
    # (Pruefrunde G) — fehlt sie in der Spez, wird aus "trifft nicht zu"
    # still "nie erhoben".
    for block in GENERATIONS_BLOECKE:
        abox_block = projiziere(block, gen.block(block))
        spez_werte = getattr(spez, block)
        for merkmal in sorted(set(abox_block) | set(spez_werte)):
            if merkmal not in abox_block:
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: in der Spez gesetzt "
                    f"({spez_werte[merkmal]!r}), in der A-Box nicht belegt — "
                    "die Spez hat eine eigene Wahrheit")
            elif merkmal not in spez_werte:
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: in der A-Box "
                    f"{abox_block[merkmal]!r}, fehlt in der Spez — die "
                    "Fuehrung rechnete sonst still mit der Vorgabe")
            elif not (type(spez_werte[merkmal]) is type(abox_block[merkmal])
                      and werte_gleich(spez_werte[merkmal], abox_block[merkmal])):
                fehler.append(
                    f"{gen.id}/{block}.{merkmal}: Spez "
                    f"{spez_werte[merkmal]!r} != A-Box {abox_block[merkmal]!r}")

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
