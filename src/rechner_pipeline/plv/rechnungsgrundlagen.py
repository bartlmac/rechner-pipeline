"""Die PLV erfuellt die Faehigkeit Rechnungsgrundlagen des Zielvertrags
(ADR-030, Stufe 1).

Produkt-Registry, Modellpunkt-Defaults und Tafelspeicher stammen aus dem
abgenommenen Kern. Die wirksame Tarifzelle der Fuehrung stammt aus der
PLV-Config und wird hier je Police aufgeloest. Der Kern bleibt unberuehrt.

Knoten: system/zielsystem
"""

from __future__ import annotations

import dataclasses
import xml.etree.ElementTree as ET
from functools import lru_cache
from types import MappingProxyType
from typing import Any, Callable, FrozenSet, Mapping, Tuple

from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern.produkte import PRODUKTE, hole
from rechner_pipeline.zielsystem.rechnungsgrundlagen import Parametersatz
from rechner_pipeline.zielsystem.bestandsdaten import Fuehrungsansicht

__all__ = ["PLVRechnungsgrundlagen"]


def _typname(typ: object) -> str:
    return typ if isinstance(typ, str) else getattr(typ, "__name__", repr(typ))


@lru_cache(maxsize=None)
def _parametersatz(produkt: str) -> Parametersatz:
    """Felder und Defaults des Modellpunkts eines registrierten Produkts;
    ``KeyError`` (``UnbekanntesProduktError``) fuer ein unbekanntes."""
    klasse = hole(produkt).model_point_cls
    felder = dataclasses.fields(klasse)
    return Parametersatz(
        produkt=produkt,
        felder=tuple((f.name, _typname(f.type)) for f in felder),
        defaults=MappingProxyType({
            f.name: f.default for f in felder if f.default is not dataclasses.MISSING
        }),
    )


class PLVRechnungsgrundlagen:
    """Die Rechnungsgrundlagen der PLV, in der Form des Protokolls
    ``zielsystem.rechnungsgrundlagen.Rechnungsgrundlagen``."""

    def produkte(self) -> FrozenSet[str]:
        return frozenset(PRODUKTE)

    def parametersatz(self, produkt: str) -> Parametersatz:
        return _parametersatz(produkt)

    def verfuegbare_tafeln(self) -> FrozenSet[str]:
        return frozenset(tafeln.verfuegbare_tafeln())

    def pruefe_alterstafel(self, name: str, werte: Mapping[int, float]) -> None:
        tafeln.validiere_alterstafel(name, werte)

    def tafeln_lesen(
        self, text: str
    ) -> Tuple[Mapping[str, Mapping[int, float]], FrozenSet[str]]:
        try:
            alterstafeln, select_tafeln = tafeln._parse_tables(text)
        except ET.ParseError as exc:
            raise ValueError(f"Tafelspeicher ist kein XML: {exc}") from exc
        return alterstafeln, frozenset(alterstafeln) | frozenset(select_tafeln)

    def fuehrungsgrundlagen(
        self, ansicht: Fuehrungsansicht, merkmale: Any,
    ) -> Callable[[int, str], Mapping[str, Any]]:
        from rechner_pipeline.bestand.auswertung import grundlagen_je_police
        from rechner_pipeline.bestand.config import BestandConfig, config_aus_text

        # Direkte Aufrufer des reinen Pruefkerns geben historisch eine
        # BestandConfig; der CLI-Weg reicht ausschliesslich die strukturierte,
        # validierte Ansicht mit genau dem gebundenen Text weiter.
        config = (ansicht if isinstance(ansicht, BestandConfig)
                  else config_aus_text(ansicht.config_text))
        if not isinstance(ansicht, BestandConfig):
            fehler = config.validate()
            if fehler:
                raise ValueError("Config ungueltig: " + "; ".join(fehler))
        return grundlagen_je_police(config, merkmale)
