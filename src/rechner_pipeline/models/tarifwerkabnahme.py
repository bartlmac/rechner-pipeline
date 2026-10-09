"""Der Vertrag der Tarifwerk-Abnahme A-T1 — Gegenstand, Belegorte, Auszug.

Entscheid des Maintainers 2026-10-01 (ADR-025): Das Tarifwerk der PLV ist
einer der vier Gegenstaende der Erstabnahme des Zielsystems, verantwortet
von ``mensch/aktuariat``. Bis hierher lief es in der Pfadmenge des
Kernstands mit (``docs/tarifplaene`` in ``models.kernabnahme.KERNSTAND``)
und wurde damit von der Rechenkern-Verantwortung gezeichnet — von der
falschen Rolle, und die Parametrierung der eigenen Generationen in den
Configs zeichnete niemand.

Hier steht, was mehrere Schichten lesen: der Produzent
(``gates.tarifwerk_belegen``), das Gate (``gates.gate_entscheid``: A-T1 und
die Vorbedingung von A-M4) und der Stand (``gates.stand_belegen``).

**Der Gegenstand, EINMAL bestimmt** (:data:`TARIFWERK`):

* ``plv/tarifplaene`` — die Tarifplaene: was die PLV ihren Kunden
  verspricht und wie (Ausgestaltung je Produkt). Je Datei ein Teil der Sicht.
* die Parametrierung der EIGENEN Tarifgenerationen in den PLV-Configs
  (``plv/configs/*.toml``; eigen = Knoten ``<familie>/plv_<...>``): je
  ``[[generation]]`` alle Felder AUSSER den Erfahrungs- und Betriebsfeldern
  (:data:`NICHT_TARIFWERK`), samt Tarifzellen und Tarifwerks-Schaltern —
  Rechnungszins, Tafeln, Kostensaetze, Rueckkaufs- und Herabsetzungsregeln,
  Verkaufsfenster, Endalter. Je Generation ein Teil der Sicht.

**Bewusst NICHT im Gegenstand — die Grenze:**

* die Erfahrungsannahmen und die Simulation der Vorfuehrung (``[annahmen]``,
  ``[plausibilitaet]``, ``[tagesbetrieb]``, ``[meta]`` und je Generation
  Neuzugang, Verteilungen, Korrelationen): Sie sagen, wie sich die
  simulierte Welt VERHAELT (wie viele Kunden kaufen, kuendigen, sterben), nicht,
  was ein Vertrag VERSPRICHT. Kein Vertragswert aendert sich, wenn sie sich
  aendern; sie gehoeren der Regie der Vorfuehrung und dem Betrieb, nicht
  dem Tarifwerk;
* der Nummernkreis einer Generation: die Identitaet der Policen (Betrieb),
  keine Tarifeigenschaft;
* uebernommene Generationen (z. B. ``klv/tg2015``): Ihr Tarifwerk ist das des
  abgebenden Hauses und wird im Fall abgenommen (P-K1, A-M1, A-M4);
* der Rechenkern und seine Referenzwerte (A-K2) und die T-Box (A-O1).

Die Auswahl ist eine Ausnahmeliste, keine Positivliste: Ein neues Feld einer
Generation gehoert zum Tarifwerk, bis jemand begruendet, dass es Erfahrung
ist. In dieser Richtung faellt eine vergessene Einordnung als Abnahme auf,
nicht als stille Luecke.

Knoten: system/entscheid
"""

from __future__ import annotations

import hashlib
import json
import tomllib
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Die Belegorte im Bereich (Fall oder Linie), fest wie bei A-K2.
AENDERUNG_RELATIV = "abgeleitet/tarifwerk/aenderung.json"
SICHT_RELATIV = "abgeleitet/tarifwerk/aenderung.md"

#: Die Tarifplaene (je Datei ein Teil).
TARIFPLAENE = "plv/tarifplaene"
#: Die Configs der PLV (je eigene Generation ein Teil).
CONFIG_VERZEICHNIS = "plv/configs"
CONFIG_MUSTER = "*.toml"

#: DER GEGENSTAND VON A-T1, als Pfadmenge mit Begruendung.
TARIFWERK: Tuple[Tuple[str, str, str], ...] = (
    (TARIFPLAENE, "je_datei",
     "Tarifplaene: was die PLV verspricht und wie (Ausgestaltung je Produkt)"),
    (CONFIG_VERZEICHNIS, "je_generation",
     "Parametrierung der eigenen Tarifgenerationen: Rechnungsgrundlagen, Kosten, "
     "Rueckkaufs- und Herabsetzungsregeln, Tarifzellen, Verkaufsfenster"),
)

#: Felder einer ``[[generation]]``, die NICHT zum Tarifwerk gehoeren — je mit
#: Grund (siehe Moduldocstring).
NICHT_TARIFWERK: Dict[str, str] = {
    "neuzugang_pro_jahr": "Erfahrung/Simulation: Verkaufsvolumen",
    "neuzugang_trend": "Erfahrung/Simulation: Verkaufsvolumen",
    "verteilungen": "Erfahrung/Simulation: Bestandsstruktur des Neugeschaefts",
    "korrelation": "Erfahrung/Simulation: Bestandsstruktur des Neugeschaefts",
    "nummernkreis": "Betrieb: Identitaet der Policen, keine Tarifeigenschaft",
}

#: Eigene Generation: der Generationsteil des Knotens beginnt so.
EIGEN_PRAEFIX = "plv_"


class TarifwerkFehler(ValueError):
    """Eine Config ist nicht lesbar — mit dem Grund."""


def ist_eigen(knoten: object) -> bool:
    if not isinstance(knoten, str) or "/" not in knoten:
        return False
    return knoten.split("/", 1)[1].startswith(EIGEN_PRAEFIX)


def _jsonfaehig(wert: Any) -> Any:
    """TOML-Werte (Datum) in kanonisches JSON."""
    if isinstance(wert, dict):
        return {str(k): _jsonfaehig(v) for k, v in sorted(wert.items())}
    if isinstance(wert, list):
        return [_jsonfaehig(v) for v in wert]
    if hasattr(wert, "isoformat"):
        return wert.isoformat()
    return wert


def generationen_aus(config_text: str, name: str) -> Dict[str, Dict[str, Any]]:
    """Die Tarifwerk-Felder der eigenen Generationen einer Config.

    Rueckgabe: ``{generationsname: {feld: wert}}`` (kanonisch, sortiert).
    Wirft :class:`TarifwerkFehler`, wenn die Config kein TOML ist oder eine
    eigene Generation keinen Namen traegt.
    """
    try:
        daten = tomllib.loads(config_text)
    except tomllib.TOMLDecodeError as exc:
        raise TarifwerkFehler(f"{name}: kein TOML ({exc})") from exc
    ergebnis: Dict[str, Dict[str, Any]] = {}
    for gen in daten.get("generation") or []:
        if not isinstance(gen, dict) or not ist_eigen(gen.get("knoten")):
            continue
        gname = gen.get("name")
        if not isinstance(gname, str) or not gname:
            raise TarifwerkFehler(f"{name}: eigene Generation ohne Namen")
        if gname in ergebnis:
            raise TarifwerkFehler(f"{name}: Generation {gname!r} doppelt")
        ergebnis[gname] = _jsonfaehig(
            {k: v for k, v in gen.items() if k not in NICHT_TARIFWERK})
    return ergebnis


def kanonisch(daten: Any) -> bytes:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def tarifwerk_inhalt(
    tarifplaene: Iterable[Tuple[str, bytes]],
    configs: Iterable[Tuple[str, bytes]],
) -> Dict[str, Any]:
    """Der Inhalt des Tarifwerks aus (Pfad, Bytes)-Paaren — die eine
    Ableitung fuer den lebenden Stand, den Stand eines Commits und die
    Nachrechnung im Gate."""
    plaene = {pfad: hashlib.sha256(roh).hexdigest() for pfad, roh in tarifplaene}
    generationen: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for pfad, roh in configs:
        try:
            text = roh.decode("utf-8")
        except UnicodeError as exc:
            raise TarifwerkFehler(f"{pfad}: kein UTF-8 ({exc})") from exc
        eigene = generationen_aus(text, pfad)
        if eigene:
            generationen[pfad] = eigene
    return {"tarifplaene": dict(sorted(plaene.items())),
            "generationen": dict(sorted(generationen.items()))}


def stand_aus(inhalt: Dict[str, Any]) -> Dict[str, str]:
    """Der Stand des Tarifwerks — der Wert, den A-T1 abnimmt und A-M4 per
    ``==`` gegen den lebenden haelt."""
    return {
        "tarifplaene_sha256": hashlib.sha256(kanonisch(inhalt["tarifplaene"])).hexdigest(),
        "parametrierung_sha256": hashlib.sha256(kanonisch(inhalt["generationen"])).hexdigest(),
        "tarifwerk_sha256": hashlib.sha256(kanonisch(inhalt)).hexdigest(),
    }


def unterschiede(alt: Dict[str, Any], neu: Dict[str, Any]) -> Dict[str, Any]:
    """Was sich je Tarifplan und je Generation geaendert hat — deterministisch."""
    plaene: List[Dict[str, str]] = []
    for pfad in sorted(set(alt["tarifplaene"]) | set(neu["tarifplaene"])):
        a, n = alt["tarifplaene"].get(pfad), neu["tarifplaene"].get(pfad)
        zustand = ("neu" if a is None else "entfallen" if n is None
                   else "unveraendert" if a == n else "geaendert")
        plaene.append({"pfad": pfad, "zustand": zustand})
    gens: List[Dict[str, Any]] = []
    for pfad in sorted(set(alt["generationen"]) | set(neu["generationen"])):
        ga, gn = alt["generationen"].get(pfad, {}), neu["generationen"].get(pfad, {})
        for name in sorted(set(ga) | set(gn)):
            fa, fn = ga.get(name), gn.get(name)
            if fa is None or fn is None:
                gens.append({"config": pfad, "generation": name,
                             "zustand": "neu" if fa is None else "entfallen", "felder": []})
                continue
            felder = [{"feld": f, "vorher": fa.get(f), "nachher": fn.get(f)}
                      for f in sorted(set(fa) | set(fn)) if fa.get(f) != fn.get(f)]
            gens.append({"config": pfad, "generation": name,
                         "zustand": "geaendert" if felder else "unveraendert",
                         "felder": felder})
    return {"tarifplaene": plaene, "generationen": gens}


def konfig_pfade(namen: Iterable[str]) -> List[str]:
    """Die Config-Pfade der PLV aus einer Dateiliste (``plv/configs/*.toml``,
    nicht rekursiv)."""
    return sorted(p for p in namen
                  if p.startswith(CONFIG_VERZEICHNIS + "/")
                  and "/" not in p[len(CONFIG_VERZEICHNIS) + 1:] and p.endswith(".toml"))


def tarifplan_pfade(namen: Iterable[str]) -> List[str]:
    return sorted(p for p in namen if p.startswith(TARIFPLAENE + "/"))


def teil_von(pfad: str) -> Optional[str]:
    """Der Teil des Gegenstands, zu dem ein Repo-Pfad gehoert (None = keiner)."""
    if pfad.startswith(TARIFPLAENE + "/"):
        return pfad
    if pfad in konfig_pfade([pfad]):
        return pfad
    return None
