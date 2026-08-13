"""Produkt-Registry des stabilen Kerns.

Die Produkt-Naht für die beschlossene KI-Evolution: ein Produkt ist eine
Klasse mit dem Contract

* Klassenattribute ``kennung`` (Registry-Schlüssel), ``contract_prefix``
  (Prefix der Scalars/Tables im Golden-Master-Contract) und
  ``model_point_cls`` (der zugehörige ModelPoint-Typ);
* Konstruktor ``Produkt(mp)``;
* Methoden ``scalars() -> dict`` und ``verlaufswerte() -> list[dict]``.

Registrierte Produkte: KLV (2-Zustands-Fall, migriert aus dem
Quell-Workbook) und BU (Beispielprodukt, reine Zustandsmodell-
Konfiguration mit Select-Tafeln). Ein neues Produkt registriert sich
hier — ``berechne(mp, produkt=...)`` findet es über die Kennung.
"""

from __future__ import annotations

from typing import Dict, Type

from rechner_pipeline.kern.produkte.bu import BU
from rechner_pipeline.kern.produkte.klv import KLV


class UnbekanntesProduktError(KeyError):
    """Die angeforderte Produkt-Kennung ist nicht registriert."""


PRODUKTE: Dict[str, Type] = {KLV.kennung: KLV, BU.kennung: BU}


def hole(kennung: str) -> Type:
    """Produktklasse zur Kennung — fail-fast bei unbekanntem Produkt."""
    if kennung not in PRODUKTE:
        raise UnbekanntesProduktError(
            f"Produkt {kennung!r} nicht registriert (bekannt: {sorted(PRODUKTE)})"
        )
    return PRODUKTE[kennung]
