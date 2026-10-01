"""Der Fuehrungswert der Migrationsabnahme — ein Vertrag, vier Leser.

Entscheid des Maintainers (2026-10-01): Die Migrationsabnahme A-M4 weist
je Vertrag des Zugangs zusaetzlich den Wert aus, den die Bestandsfuehrung
fuer ihn FUEHRT — Deckungsrueckstellung, Rueckkaufswert und
Korrekturschicht, wie sie der Monatsabschluss am Zugangsstichtag und am
Folgestichtag festschreiben wird, in seiner Bewertungskonvention.

Der Fuehrungswert ist ein SYSTEMWERT, kein Vergleich mit der Lieferung: Die
Suite vergleicht weiter die Monatsreserve mit dem gelieferten
Deckungskapital (``dk_stichtag_1``); der Fuehrungswert haengt an demselben
Vertragszustand, den dieser Vergleich bestaetigt, und sagt, was der
Abschluss daraus macht. Die Zugangsprobe (``betrieb.zugangsprobe``) haelt
die Abschlusszeilen des Betriebs gegen ihn.

Gerechnet wird er in der Bestandsschicht ueber DIESELBE Bewertungsstrecke
wie der Abschluss (``bestand.migrationszugang.fuehrungswerte`` ruft
``bestand.auswertung.einzelwerte_am``); hier steht nur der Vertrag: die
Produzentin (``gates.migrationssuite_lauf``), die Suite (``qa.migrationssuite``
traegt ihn unveraendert), A-M4 (``gates.abnahmebericht``) und die
Zugangsprobe lesen dieselben Namen. Die Schichtenkarte laesst ``qa``
nicht in ``bestand`` und ``gates`` nicht in ``betrieb``; der Vertrag wohnt
deshalb hier.

Knoten: system/entscheid
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Mapping, Optional

from rechner_pipeline.models.bestand import BEWERTUNGSKONVENTIONEN

#: Die Fassung des Suite-Belegs, die den Fuehrungswert traegt. Belege ohne
#: das Feld ``schema_version`` sind Fassung 1 (vor dem 2026-10-01).
SUITE_SCHEMA_VERSION = 2
#: Was der Fuehrungswert ist.
ART = "systemwert"
HINWEIS = (
    "Systemwert der Bestandsfuehrung: der Wert, den der Monatsabschluss fuer den "
    "Vertrag fuehrt, gerechnet ueber die Bewertungsstrecke des Abschlusses aus dem "
    "Bestand des Falls — kein Vergleich mit einer Lieferung")
#: Die Abschlussspalten, die er traegt.
GROESSEN = ("deckungskapital", "rueckkaufswert", "korrekturschicht")
#: Die Termine je Vertrag (Zugangsstichtag, Folgestichtag der Suite).
TERMINE = ("stichtag_1", "stichtag_2")
#: Die Felder eines Termins.
FELDER = ("stichtag", "status_code") + GROESSEN
#: Die Felder des Kopfs im Suite-Beleg.
KOPF_FELDER = ("art", "hinweis", "konvention", "bestand_sha256", "config_sha256")


def kopf(konvention: str, *, bestand_sha256: str, config_sha256: str) -> Dict[str, Any]:
    """Der Kopf des Fuehrungswerts im Suite-Beleg."""
    return {"art": ART, "hinweis": HINWEIS, "konvention": konvention,
            "bestand_sha256": bestand_sha256, "config_sha256": config_sha256}


def termin(stichtag: str, zeile: Mapping[str, Any]) -> Dict[str, Any]:
    """Ein Termin aus einer Bewertungszeile (``einzelwerte_am``)."""
    return {"stichtag": stichtag, "status_code": str(zeile["status"]),
            **{g: float(zeile[g]) for g in GROESSEN}}


def _endlich(wert: Any) -> bool:
    return (isinstance(wert, (int, float)) and not isinstance(wert, bool)
            and math.isfinite(float(wert)))


def fuehrungswert_fehler(suite: Mapping[str, Any]) -> List[str]:
    """Der Fuehrungswert eines Suite-Belegs gegen seinen Vertrag (leer = in Ordnung).

    Pflicht im Bestands-Scope von A-M4: Fassung :data:`SUITE_SCHEMA_VERSION`,
    der Kopf mit Art, Hinweis, Konvention und den Bindungen (der Bestand ist
    der der Suite, die Config steht unter ihren Eingaben), und JEDER Vertrag
    mit einem Termin am Zugangsstichtag — ein Vertrag des Zugangs steht dort
    im Abschluss. Am Folgestichtag ist ``null`` die Aussage "nicht mehr in
    Kraft".
    """
    fehler: List[str] = []
    if suite.get("schema_version") != SUITE_SCHEMA_VERSION:
        return [f"Migrationssuite der Fassung {suite.get('schema_version', 1)!r} traegt keinen "
                f"Fuehrungswert (erwartet Fassung {SUITE_SCHEMA_VERSION}) — die Suite neu "
                "ausfuehren (gates.migrationssuite_lauf --config <bestand-config>)"]
    k = suite.get("fuehrungswert")
    if not isinstance(k, dict) or set(k) != set(KOPF_FELDER):
        return [f"Fuehrungswert: Kopf {sorted(k) if isinstance(k, dict) else k!r} ist nicht "
                f"{sorted(KOPF_FELDER)}"]
    if k["art"] != ART or k["hinweis"] != HINWEIS:
        fehler.append("Fuehrungswert: Art oder Hinweis ist nicht der des Vertrags (Systemwert)")
    if k["konvention"] not in BEWERTUNGSKONVENTIONEN:
        fehler.append(f"Fuehrungswert: Konvention {k['konvention']!r} unbekannt")
    if k["bestand_sha256"] != suite.get("bestand_sha256"):
        fehler.append("Fuehrungswert: gerechnet auf einem anderen Bestand als die Suite")
    eingaben = suite.get("eingaben")
    if isinstance(eingaben, dict) and k["config_sha256"] not in set(eingaben.values()):
        fehler.append("Fuehrungswert: die Config steht nicht unter den Eingaben der Suite")
    for i, urteil in enumerate(suite.get("vertraege") or []):
        wo = f"vertraege[{i}] ({urteil.get('police_id')})"
        fw = urteil.get("fuehrungswert") if isinstance(urteil, dict) else None
        if not isinstance(fw, dict) or set(fw) != set(TERMINE):
            fehler.append(f"{wo}: Fuehrungswert fehlt oder ist nicht {list(TERMINE)}")
            continue
        for t in TERMINE:
            eintrag = fw[t]
            if eintrag is None:
                if t == "stichtag_1":
                    fehler.append(f"{wo}: kein Fuehrungswert am Zugangsstichtag — ein Vertrag "
                                  "des Zugangs steht dort im Abschluss")
                continue
            if not isinstance(eintrag, dict) or set(eintrag) != set(FELDER):
                fehler.append(f"{wo}.{t}: Felder sind nicht {list(FELDER)}")
                continue
            if eintrag["stichtag"] != suite.get(t):
                fehler.append(f"{wo}.{t}: Stichtag {eintrag['stichtag']!r} ist nicht der der Suite")
            for g in GROESSEN:
                if not _endlich(eintrag[g]):
                    fehler.append(f"{wo}.{t}.{g}: keine endliche Zahl")
    return fehler


def je_police(suite: Mapping[str, Any], termin_name: str) -> Dict[str, Optional[Dict[str, Any]]]:
    """Police -> Termin des Fuehrungswerts (``None``: nicht in Kraft)."""
    return {str(u.get("police_id")): (u.get("fuehrungswert") or {}).get(termin_name)
            for u in suite.get("vertraege") or [] if isinstance(u, dict)}
