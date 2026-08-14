"""Stage 1: von Quell-Fragmenten zur A-Box (deterministische Haelfte).

Die Arbeitsteilung ist P4: LLM-Extraktions-Agenten lesen die
Vorverdichtung EINER Quelle und liefern ein :class:`QuellFragment`
(Structured Output gegen das generierte JSON-Schema) — sie schlagen
vor. ALLES danach ist dieser deterministische Code: Fundstellen werden
zu voller Provenienz angereichert (SHA-256 aus dem Eingang-Register
des Falls, Akteur, Zeitpunkt), Fragmente werden gemergt (Widerspruch
=> Diskrepanz-Objekt, siehe :mod:`.merge`), die A-Box entsteht und
wird validiert.

Ein Agent, der ein Pflichtfeld in seiner Quelle nicht findet, meldet
es unter ``nicht_belegt`` — das ist eine Aussage ("gesucht, nicht da"),
kein Schweigen. Was kein Agent auch nur erwaehnt, weist die Coverage
als ``fehlt_in_extraktion`` aus (P6: die stillschweigend fehlende
Extraktion ist der gefaehrliche Fehler).

Dieses Modul ist SDK-frei: es kennt keine Modelle, nur deren
persistierte Fragmente.
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from rechner_pipeline.ontologie.aussage import (
    Aussage,
    Provenienz,
    Wert,
    Zustand,
    belegt,
    nicht_belegt,
)
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz
from rechner_pipeline.ontologie.ids import knoten_id, zellen_segment
from rechner_pipeline.ontologie.merge import merge_felder, werte_gleich
from rechner_pipeline.ontologie.tbox import (
    ABox,
    Merkmalsdimension,
    PFLICHT_PARAMETER,
    Parametrierungszelle,
    Quelle,
    Tarifgeneration,
)


class FragmentWert(BaseModel):
    """Ein vom Agenten extrahierter Wert mit seiner Fundstelle."""

    model_config = ConfigDict(extra="forbid")

    wert: Wert
    fundstelle: str = Field(min_length=1)
    konfidenz: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class FragmentZelle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auspraegungen: Dict[str, str] = Field(default_factory=dict)
    parameter: Dict[str, FragmentWert] = Field(default_factory=dict)


class QuellFragment(BaseModel):
    """Der Structured-Output-Contract eines Extraktions-Agenten.

    Genau EINE Quelle, genau EINE Generation — der Agent sieht die
    andere Quelle nie (Widersprueche entstehen im Merge, nicht im
    Agenten-Urteil).
    """

    model_config = ConfigDict(extra="forbid")

    generation: str = Field(min_length=1)      # z. B. "tg2015"
    quelle_datei: str = Field(min_length=1)    # Name im Eingang des Falls
    quelle_art: Literal["tarifmeldung", "tarifrechner", "bestand"]
    dimensionen: List[Merkmalsdimension] = Field(default_factory=list)
    zellen: List[FragmentZelle] = Field(min_length=1)
    unisex: Optional[FragmentWert] = None
    #: Quellname -> Zielfeld (fremde Benennungslogik erfassen).
    quellnamen: Dict[str, str] = Field(default_factory=dict)
    #: Pflichtfelder, die der Agent GESUCHT und in der Quelle NICHT
    #: gefunden hat ("gesucht, nicht da" — unterscheidbar von Schweigen).
    nicht_belegt: List[str] = Field(default_factory=list)
    #: Freitext-Beobachtungen (kein Ersatz fuer strukturierte Felder).
    anmerkungen: List[str] = Field(default_factory=list)


class BefuellungsFehler(ValueError):
    """Fachlicher Fehler beim Bauen der A-Box (fail-fast)."""


def _provenienz_fabrik(
    fragment: QuellFragment,
    register: dict,
    akteur: str,
    erhoben_am: str,
):
    registriert = {
        q["datei"]: q["sha256"] for q in register.get("quellen", [])
    }
    if fragment.quelle_datei not in registriert:
        raise BefuellungsFehler(
            f"Fragment-Quelle {fragment.quelle_datei!r} ist im "
            "Eingang-Register nicht registriert — keine Aussage ohne "
            "verankerte Quelle (P1)"
        )
    sha = registriert[fragment.quelle_datei]

    def baue(fundstelle: str) -> Provenienz:
        return Provenienz(
            quelle_datei=fragment.quelle_datei,
            quelle_sha256=sha,
            fundstelle=fundstelle,
            akteur=akteur,
            erhoben_am=erhoben_am,
        )

    return baue


def _vereine_dimensionen(
    fragmente: List[QuellFragment],
) -> List[Merkmalsdimension]:
    dimensionen: Dict[str, Merkmalsdimension] = {}
    for fragment in fragmente:
        for dim in fragment.dimensionen:
            vorhanden = dimensionen.get(dim.id)
            if vorhanden is None:
                dimensionen[dim.id] = dim
            elif sorted(vorhanden.auspraegungen) != sorted(dim.auspraegungen):
                raise BefuellungsFehler(
                    f"Dimension {dim.id!r}: Quellen nennen verschiedene "
                    f"Auspraegungen ({vorhanden.auspraegungen} vs. "
                    f"{dim.auspraegungen}) — Merkmalsraum-Konflikte sind "
                    "kein Merge-Fall, sondern ein Modellierungsbefund; "
                    "zuerst die Quellen klaeren"
                )
    return [dimensionen[k] for k in sorted(dimensionen)]


def baue_generation(
    name: str,
    fragmente: List[QuellFragment],
    register: dict,
    akteur_je_fragment: Dict[int, str],
    erhoben_am: str,
) -> Tuple[Tarifgeneration, List[Diskrepanz]]:
    """Fragmente EINER Generation deterministisch zur Generation mergen."""
    if not fragmente:
        raise BefuellungsFehler(f"Generation {name!r}: keine Fragmente")
    falsch = [f.generation for f in fragmente if f.generation != name]
    if falsch:
        raise BefuellungsFehler(
            f"Generation {name!r}: Fragmente anderer Generation {falsch}"
        )
    gen_id = knoten_id("klv", name)
    dimensionen = _vereine_dimensionen(fragmente)

    fabriken = [
        _provenienz_fabrik(f, register, akteur_je_fragment[i], erhoben_am)
        for i, f in enumerate(fragmente)
    ]

    # Je Zellen-ID und Quelle ein Feld->Aussage-Dict aufbauen.
    je_zelle: Dict[str, List[Dict[str, Aussage]]] = {}
    auspraegungen_je_zelle: Dict[str, Dict[str, str]] = {}
    for i, fragment in enumerate(fragmente):
        fabrik = fabriken[i]
        for zelle in fragment.zellen:
            zid = zellen_segment(zelle.auspraegungen)
            auspraegungen_je_zelle.setdefault(zid, zelle.auspraegungen)
            felder: Dict[str, Aussage] = {
                feld: belegt(
                    fw.wert, [fabrik(fw.fundstelle)], konfidenz=fw.konfidenz
                )
                for feld, fw in zelle.parameter.items()
            }
            for feld in fragment.nicht_belegt:
                felder.setdefault(feld, nicht_belegt())
            je_zelle.setdefault(zid, []).append(felder)

    zellen: List[Parametrierungszelle] = []
    diskrepanzen: List[Diskrepanz] = []
    for zid in sorted(je_zelle):
        knoten = f"{gen_id}/{zid}"
        felder, konflikte = merge_felder(knoten, je_zelle[zid])
        diskrepanzen.extend(konflikte)
        zellen.append(Parametrierungszelle(
            id=zid,
            auspraegungen=auspraegungen_je_zelle[zid],
            parameter=felder,
        ))

    # Unisex-Aussage ueber die Quellen mergen.
    unisex_fragmente: List[Dict[str, Aussage]] = []
    for i, fragment in enumerate(fragmente):
        if fragment.unisex is not None:
            unisex_fragmente.append({
                "unisex": belegt(
                    fragment.unisex.wert,
                    [fabriken[i](fragment.unisex.fundstelle)],
                    konfidenz=fragment.unisex.konfidenz,
                )
            })
    unisex: Optional[Aussage] = None
    if unisex_fragmente:
        gemergt, konflikte = merge_felder(gen_id, unisex_fragmente)
        diskrepanzen.extend(konflikte)
        unisex = gemergt["unisex"]

    # Quellnamen-Mapping vereinen. Das ist Dokumentation der fremden
    # Benennungslogik, kein Fachwert: abweichende Formulierungen werden
    # als sortierte Vereinigung erhalten (sichtbar, nicht entschieden) —
    # die P2-Maschinerie gilt den Werten, nicht den Notizen.
    quellnamen: Dict[str, str] = {}
    for fragment in fragmente:
        for quellname, ziel in fragment.quellnamen.items():
            vorhanden = quellnamen.get(quellname)
            if vorhanden is None:
                quellnamen[quellname] = ziel
            elif ziel not in vorhanden.split(" | "):
                quellnamen[quellname] = " | ".join(
                    sorted(set(vorhanden.split(" | ")) | {ziel})
                )

    registriert = {
        q["datei"]: q["sha256"] for q in register.get("quellen", [])
    }
    quellen = [
        Quelle(
            datei=f.quelle_datei,
            sha256=registriert[f.quelle_datei],
            art=f.quelle_art,
        )
        for f in fragmente
    ]

    generation = Tarifgeneration(
        id=gen_id,
        name=name.upper(),
        familie="klv",
        quellen=quellen,
        dimensionen=dimensionen,
        zellen=zellen,
        unisex=unisex,
        quellnamen=quellnamen,
    )
    return generation, diskrepanzen


def baue_abox(
    fall: str,
    fragmente: List[QuellFragment],
    register: dict,
    akteure: List[str],
    erhoben_am: str,
) -> ABox:
    """Alle Fragmente eines Falls zur A-Box mergen (je Generation)."""
    if len(akteure) != len(fragmente):
        raise BefuellungsFehler("je Fragment genau ein Akteur")
    generationen: List[Tarifgeneration] = []
    diskrepanzen: List[Diskrepanz] = []
    namen = sorted({f.generation for f in fragmente})
    for name in namen:
        indizes = [
            i for i, f in enumerate(fragmente) if f.generation == name
        ]
        gen, konflikte = baue_generation(
            name,
            [fragmente[i] for i in indizes],
            register,
            {j: akteure[i] for j, i in enumerate(indizes)},
            erhoben_am,
        )
        generationen.append(gen)
        diskrepanzen.extend(konflikte)
    return ABox(
        fall=fall, generationen=generationen, diskrepanzen=diskrepanzen
    )


def loese_diskrepanz_auf(
    abox: ABox,
    diskrepanz_id: str,
    gewaehlter_wert: Wert,
    entscheider: str,
    begruendung: str,
    entschieden_am: str,
) -> ABox:
    """Menschliche Aufloesung anwenden: Diskrepanz + Aussage nachziehen.

    Der gewaehlte Wert muss eine der Lesarten sein — die Aufloesung
    WAEHLT zwischen den Quellen, sie erfindet keinen dritten Wert (ein
    neuer Wert waere eine neue Quelle und gehoert als solche erfasst).
    Die Aussage wird belegt mit der Provenienz der gewaehlten Lesart.
    """
    from rechner_pipeline.ontologie.diskrepanz import Entscheidung

    kandidaten = [d for d in abox.diskrepanzen if d.id == diskrepanz_id]
    if not kandidaten:
        raise BefuellungsFehler(f"Diskrepanz {diskrepanz_id!r} unbekannt")
    [diskrepanz] = kandidaten
    if diskrepanz.status == "aufgeloest":
        raise BefuellungsFehler(f"{diskrepanz_id}: bereits aufgeloest")
    passende = [
        l for l in diskrepanz.lesarten
        if werte_gleich(l.wert, gewaehlter_wert)
    ]
    if not passende:
        raise BefuellungsFehler(
            f"{diskrepanz_id}: {gewaehlter_wert!r} ist keine der Lesarten "
            f"({[l.wert for l in diskrepanz.lesarten]}) — die Aufloesung "
            "waehlt zwischen den Quellen, sie erfindet keinen Wert"
        )
    [lesart] = passende[:1]

    diskrepanz.status = "aufgeloest"
    diskrepanz.entscheidung = Entscheidung(
        entscheider=entscheider,
        begruendung=begruendung,
        gewaehlter_wert=lesart.wert,
        entschieden_am=entschieden_am,
    )

    getroffen = 0
    for gen in abox.generationen:
        ziele: List[Tuple[Dict[str, Aussage], str]] = [
            (zelle.parameter, feld)
            for zelle in gen.zellen
            for feld, aussage in zelle.parameter.items()
            if aussage.diskrepanz_id == diskrepanz_id
        ]
        if gen.unisex is not None and gen.unisex.diskrepanz_id == diskrepanz_id:
            gen.unisex = belegt(lesart.wert, list(lesart.provenienz))
            getroffen += 1
        for parameter, feld in ziele:
            parameter[feld] = belegt(lesart.wert, list(lesart.provenienz))
            getroffen += 1
    if getroffen == 0:
        raise BefuellungsFehler(
            f"{diskrepanz_id}: keine Aussage referenziert die Diskrepanz"
        )
    return abox
