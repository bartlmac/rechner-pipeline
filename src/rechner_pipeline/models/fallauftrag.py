"""Der Lebenslauf eines Falls — Fallauftrag am Anfang, Fallabbruch am Ende.

Frage des Maintainers (2026-10-01): "Wer beauftragt einen Fall ...? Startet
ja der Orchestrator Programmleiter, aber jemand muss es beauftragen und dem
Programmleiter den Auftrag geben und das kann nur ein Mensch sein (Auftrag
zeichnen)." Entschieden (ADR-026): Ein Fall beginnt mit dem gezeichneten
FALLAUFTRAG und endet mit der Migrationsabnahme — oder mit dem gezeichneten
FALLABBRUCH.

* :data:`~rechner_pipeline.models.zeichnung.AUFTRAG_GATE` (``A-M6.fallauftrag``)
  zeichnet die Wurzelrolle, der Vorstand (``mensch/vorstand``): Die
  Programmleitung entsteht erst mit dem Fall und kann ihn deshalb nicht
  beauftragen. Der Auftrag beauftragt, er nimmt nichts ab.
* :data:`~rechner_pipeline.models.zeichnung.ABBRUCH_GATE` (``A-M5.fallabbruch``)
  zeichnet ``mensch/programmleitung`` — mit dem Recht, das ihr der Fallauftrag
  gibt, nicht die Ordnung der Linie: Eine Fall-Rolle entsteht mit dem Fall.

Dieses Modul haelt den Vertrag beider Belege: was sie sagen, in welcher Form,
und die Ordnung, die der Fallauftrag fuer die Fall-Rolle bildet
(:func:`rechtsordnung`). Es rechnet nichts nach, was einen Fall braucht —
das tut das Gate (``gates.gate_entscheid``) gegen den Fall und die Linie.

**Der Fallauftrag** sagt und bindet:

* welcher Fall (``fall``: Name und Scope, wie ``fall.json`` sie fuehrt);
* welche Lieferung (``lieferung``: der SHA-256 von ``eingang.json`` und je
  registrierter Quelle Name und SHA-256 — dieselbe Bindung, die A-Q1 und
  A-M4 heute an ``artefakt_hashes['eingang.json']`` halten). Aendert sich
  der Eingang, gilt der Auftrag nicht mehr;
* wer die Programmleitung des Falls ist (``programmleitung``: Rolle,
  Fingerabdruck, Schluesselklasse, und ihr Gate ``A-M5``) — HIER wird die
  Fall-Rolle benannt;
* die Mandate der simulierten Rollen (``mandate``: Rolle -> SHA-256 des
  Mandatsdokuments; wie heute in ``zeichnung.mandat_sha256`` gefuehrt);
* den Stand des Zielsystems per Verweis (``zielsystem``: die Linie und je
  Gegenstand der Standabnahme die geltende Abnahme dort, oder ``None``);
* einen benannten Platz fuer das abgebende Haus (``abgebendes_haus``):
  Benennt es seinen Aktuar, haelt der Auftrag die Benennung fest — die PLV
  erkennt sie an, sie verleiht sie nicht. Heute leer und so benannt;
* den Auftragstext des Vorstands (``auftrag``).

**Der Fallabbruch** sagt: woran der Fall scheitert (``grund``), welche Gates
gezeichnet waren (``gezeichnet``, aus ``entscheide/`` gerechnet), was mit dem
Bestand geschieht (``bestand``), wohin die Uebergabe geht (``uebergabe``),
auf welchem Auftrag (``fallauftrag``), was die Eingangspruefung beim Abbruch
fand (``eingang_befund``, woertlich; leer = unversehrt) und an welchem Stand
er endet (``stand``: Eingang und Systemstand).

Knoten: system/entscheid
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping

from rechner_pipeline.models.zeichnung import (
    ABBRUCH_GATE,
    AUFTRAG_GATE,
    FALLROLLEN_GATES,
    PROGRAMMLEITUNG,
    ZEICHNENDE_KLASSEN,
    gueltige_rollenkennung,
)

#: Fester Ort der Vorlage des Fallauftrags im Fall (Produzent
#: ``gates.fall_belegen auftrag``) und ihre lesbare Sicht.
AUFTRAG_RELATIV = "abgeleitet/auftrag/fallauftrag.json"
AUFTRAG_SICHT_RELATIV = "abgeleitet/auftrag/fallauftrag.md"
#: Fester Ort der Vorlage des Fallabbruchs (``gates.fall_belegen abbruch``).
ABBRUCH_RELATIV = "abgeleitet/abbruch/fallabbruch.json"
ABBRUCH_SICHT_RELATIV = "abgeleitet/abbruch/fallabbruch.md"

AUFTRAG_SCHEMA_VERSION = 1
AUFTRAG_ART = "fallauftrag"
AUFTRAG_FELDER = frozenset({
    "schema_version", "art", "fall", "lieferung", "programmleitung", "mandate",
    "zielsystem", "abgebendes_haus", "auftrag",
})
#: Schema 2 (ADR-026, Nachtrag Runde G): ``eingang_befund`` — der Abbruch
#: geht auch bei verletztem Eingang und traegt den Befund woertlich. Schema 1
#: ist nie gezeichnet worden (Gate-Version 5.0.0 vor dem Merge) und wird nicht
#: mehr gelesen.
ABBRUCH_SCHEMA_VERSION = 2
ABBRUCH_ART = "fallabbruch"
ABBRUCH_FELDER = frozenset({
    "schema_version", "art", "fall", "fallauftrag", "grund", "gezeichnet",
    "bestand", "uebergabe", "eingang_befund", "stand",
})

#: Was der Platz des abgebenden Hauses heute sagt — woertlich.
ABGEBENDES_HAUS_VERMERK = (
    "nicht benannt: Das abgebende Haus hat keinen Aktuar benannt. Benennt es ihn, "
    "haelt dieser Auftrag die Benennung fest — die PLV erkennt sie an, sie "
    "verleiht sie nicht (ADR-025, Abschnitt 8 d).")
#: Was ``zielsystem`` ohne Abnahme eines Gegenstands in der Linie sagt.
OHNE_ABNAHME = None

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SYSTEM_FELDER = frozenset({"commit", "branch", "dirty", "quellcode_sha256"})


def _sha(wert: object) -> bool:
    return isinstance(wert, str) and _SHA256.match(wert) is not None


def _text(wert: object) -> bool:
    return isinstance(wert, str) and bool(wert.strip())


def auftrag_fehler(beleg: object) -> List[str]:
    """Die FORM eines Fallauftrags. Leer = in Ordnung.

    Was der Auftrag gegen den Fall und die Linie bindet (Name, Scope,
    Eingang, Mandate, Abnahmen der Linie), rechnet das Gate nach; hier steht
    nur, was aus dem Beleg allein folgt — eine Regel fuer Gate, Schema und
    jeden Leser.
    """
    if not isinstance(beleg, dict):
        return ["der Fallauftrag ist kein JSON-Objekt"]
    fehler: List[str] = []
    if set(beleg) != AUFTRAG_FELDER:
        return [f"der Fallauftrag traegt genau die Felder {sorted(AUFTRAG_FELDER)}"]
    if beleg.get("schema_version") != AUFTRAG_SCHEMA_VERSION or beleg.get("art") != AUFTRAG_ART:
        fehler.append(f"schema_version {AUFTRAG_SCHEMA_VERSION} und art {AUFTRAG_ART!r} erwartet")
    fall = beleg.get("fall")
    if not (isinstance(fall, dict) and set(fall) == {"name", "scope"} and _text(fall.get("name"))
            and fall.get("scope") in ("tarif", "bestand")):
        fehler.append("fall muss {name, scope in (tarif, bestand)} sein")
    lieferung = beleg.get("lieferung")
    quellen = lieferung.get("quellen") if isinstance(lieferung, dict) else None
    if not (isinstance(lieferung, dict) and set(lieferung) == {"eingang_sha256", "quellen"}
            and _sha(lieferung.get("eingang_sha256")) and isinstance(quellen, list)
            and all(isinstance(q, dict) and set(q) == {"datei", "sha256"} and _text(q.get("datei"))
                    and _sha(q.get("sha256")) for q in quellen)):
        fehler.append("lieferung muss {eingang_sha256 (SHA-256), quellen [{datei, sha256}]} sein")
    elif not quellen:
        fehler.append("lieferung.quellen ist leer — ein Auftrag ohne registrierte Lieferung "
                      "beauftragt nichts (zuerst die Quellen registrieren)")
    elif [q["datei"] for q in quellen] != sorted(q["datei"] for q in quellen):
        fehler.append("lieferung.quellen muss nach datei sortiert sein")
    pl = beleg.get("programmleitung")
    if not (isinstance(pl, dict)
            and set(pl) == {"rolle", "schluessel_sha256", "schluesselklasse", "gates"}
            and pl.get("rolle") == PROGRAMMLEITUNG and _sha(pl.get("schluessel_sha256"))
            and pl.get("schluesselklasse") in ZEICHNENDE_KLASSEN
            and pl.get("gates") == sorted(g for g, r in FALLROLLEN_GATES.items()
                                          if r == PROGRAMMLEITUNG)):
        fehler.append(
            f"programmleitung muss {{rolle {PROGRAMMLEITUNG!r}, schluessel_sha256, "
            f"schluesselklasse in {list(ZEICHNENDE_KLASSEN)}, gates [{ABBRUCH_GATE!r}]}} sein — "
            "die Fall-Rolle wird hier benannt, mit dem Recht, das der Auftrag ihr gibt")
    mandate = beleg.get("mandate")
    if not (isinstance(mandate, dict) and all(
            gueltige_rollenkennung(r) and str(r).startswith("mensch/") and _sha(s)
            for r, s in mandate.items())):
        fehler.append("mandate muss {mensch/<rolle>: SHA-256 des Mandats} sein")
    elif isinstance(pl, dict) and (pl.get("schluesselklasse") == "simulation") != (
            PROGRAMMLEITUNG in mandate):
        fehler.append("eine simulierte Programmleitung handelt unter einem Mandat, eine "
                      "menschliche ohne — mandate muss sie genau dann fuehren")
    ziel = beleg.get("zielsystem")
    if not (isinstance(ziel, dict) and set(ziel) == {"linie", "abnahmen"}
            and (ziel.get("linie") is None or _text(ziel.get("linie")))
            and isinstance(ziel.get("abnahmen"), dict)
            and all(isinstance(g, str) and (s is None or _sha(s))
                    for g, s in ziel["abnahmen"].items())
            and (ziel.get("linie") is not None or not ziel["abnahmen"])):
        fehler.append("zielsystem muss {linie (Name oder None), abnahmen {gate: SHA-256 oder "
                      "None}} sein; ohne Linie keine Abnahmen")
    haus = beleg.get("abgebendes_haus")
    if haus != {"aktuar": None, "vermerk": ABGEBENDES_HAUS_VERMERK}:
        fehler.append("abgebendes_haus ist heute der benannte leere Platz "
                      "{aktuar: None, vermerk: <woertlich>} (ADR-026)")
    if not _text(beleg.get("auftrag")):
        fehler.append("auftrag (der Auftragstext des Vorstands) fehlt")
    return fehler


def rechtsordnung(auftrag: Mapping[str, Any]) -> Dict[str, Any]:
    """Die Ordnung, die der Fallauftrag fuer die Fall-Rolle bildet.

    Dieselbe Gestalt wie eine Zeichnungsordnung (``models.zeichnung``), damit
    EINE Regel (``zeichnende_rolle_fehler``) fuer Linien- und Fall-Rollen
    gilt: Bei einem Gate aus ``FALLROLLEN_GATES`` haelt sie die Rolle gegen
    diese Ordnung, sonst gegen die der Linie.
    """
    pl = auftrag["programmleitung"]
    return {"schema_version": 2, "rollen": {pl["rolle"]: {
        "schluessel_sha256": pl["schluessel_sha256"],
        "schluesselklasse": pl["schluesselklasse"],
        "gates": list(pl["gates"]),
    }}}


def abbruch_fehler(beleg: object) -> List[str]:
    """Die FORM eines Fallabbruchs. Leer = in Ordnung. Die Bindung an den
    Fall (Auftrag, gezeichnete Gates, Befund des Eingangs, Eingang,
    Systemstand) rechnet das Gate nach."""
    if not isinstance(beleg, dict):
        return ["der Fallabbruch ist kein JSON-Objekt"]
    if set(beleg) != ABBRUCH_FELDER:
        return [f"der Fallabbruch traegt genau die Felder {sorted(ABBRUCH_FELDER)}"]
    fehler: List[str] = []
    if beleg.get("schema_version") != ABBRUCH_SCHEMA_VERSION or beleg.get("art") != ABBRUCH_ART:
        fehler.append(f"schema_version {ABBRUCH_SCHEMA_VERSION} und art {ABBRUCH_ART!r} erwartet")
    if not _text(beleg.get("fall")):
        fehler.append("fall fehlt")
    if not _sha(beleg.get("fallauftrag")):
        fehler.append(f"fallauftrag muss der SHA-256 des geltenden {AUFTRAG_GATE}-Snapshots sein")
    for feld, was in (("grund", "woran der Fall scheitert"),
                      ("bestand", "was mit dem Bestand geschieht"),
                      ("uebergabe", "wohin die Uebergabe geht")):
        if not _text(beleg.get(feld)):
            fehler.append(f"{feld} ({was}) fehlt")
    gezeichnet = beleg.get("gezeichnet")
    if not (isinstance(gezeichnet, list) and all(
            isinstance(e, dict) and set(e) == {"gate", "entscheid", "snapshot_sha256"}
            and isinstance(e.get("gate"), str)
            and e.get("entscheid") in ("angenommen", "abgelehnt")
            and _sha(e.get("snapshot_sha256")) for e in gezeichnet)):
        fehler.append("gezeichnet muss [{gate, entscheid, snapshot_sha256}] sein")
    elif gezeichnet != sorted(gezeichnet, key=lambda e: (e["gate"], e["snapshot_sha256"])):
        fehler.append("gezeichnet muss nach (gate, snapshot_sha256) sortiert sein")
    befund = beleg.get("eingang_befund")
    if not (isinstance(befund, list) and all(_text(z) for z in befund)):
        fehler.append("eingang_befund muss die Liste der Saetze der Eingangspruefung sein "
                      "(leer = der Eingang erfuellt sein Register)")
    stand = beleg.get("stand")
    system = stand.get("system") if isinstance(stand, dict) else None
    if not (isinstance(stand, dict) and set(stand) == {"eingang_sha256", "system"}
            and _sha(stand.get("eingang_sha256")) and isinstance(system, dict)
            and set(system) == _SYSTEM_FELDER
            and all(isinstance(v, str) and v for v in system.values())):
        fehler.append(f"stand muss {{eingang_sha256, system {sorted(_SYSTEM_FELDER)}}} sein")
    return fehler
