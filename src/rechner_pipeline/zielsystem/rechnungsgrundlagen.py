"""Faehigkeit 1 des Zielvertrags: Rechnungsgrundlagen (ADR-030, Stufe 1).

Was das Tool vom Zielsystem braucht, ohne dessen Kern zu kennen: welche
Produkte es fuehrt, den Parametersatz je Produkt (die Felder seines
Modellpunkts und die Defaults der Felder, die eine Generation auslassen
darf), und seine Tafeln (die Namen, die Pruefung einer Alterstafel, das
Lesen seines Tafelspeichers). Den Modellpunkt selbst baut das Tool seit
Stufe 2 nicht mehr: Die Bewertung nimmt die wirksamen Felder entgegen.

Der Parametersatz ist die Wurzel von T28-04: Ein ausgelassenes optionales
Feld einer Spez-Zelle ist im Kern wirksam, mit dem Default des Kerns.
Vor dieser Stufe kannte nur ``kern/model_point.py`` den Default, und
``models/bestand.py`` importierte ihn von dort. Jetzt sagt das Zielsystem
ihn ueber den Vertrag, und ``models.bestand.model_point_kwargs`` (der eine
Weg des Tools zum wirksamen Satz) liest ihn von hier.

Seit Stufe 3e kommt die wirksame Tarifzelle je Police aus der validierten
Fuehrungsansicht hinzu. Das Protokoll ist strukturell (``typing.Protocol``).

Knoten: system/zielsystem
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, FrozenSet, Mapping, Protocol, Tuple, runtime_checkable

from rechner_pipeline.zielsystem.bestandsdaten import Fuehrungsansicht

__all__ = ["Parametersatz", "Rechnungsgrundlagen"]


@dataclass(frozen=True)
class Parametersatz:
    """Der Parametersatz eines Produkts, wie das Zielsystem ihn fuehrt.

    ``felder``: (Name, Typname) in der Reihenfolge des Modellpunkts;
    ``defaults``: die Felder, die eine Generation auslassen darf, mit dem
    Wert, der dann wirksam ist. Jeder Default-Name ist ein Feld.
    """

    produkt: str
    felder: Tuple[Tuple[str, str], ...]
    defaults: Mapping[str, Any]

    def feldnamen(self) -> Tuple[str, ...]:
        return tuple(name for name, _ in self.felder)


@runtime_checkable
class Rechnungsgrundlagen(Protocol):
    """Faehigkeit ``rechnungsgrundlagen``."""

    def produkte(self) -> FrozenSet[str]:
        """Die Kennungen der Produkte, die das Zielsystem fuehrt."""
        ...

    def parametersatz(self, produkt: str) -> Parametersatz:
        """Der Parametersatz des Produkts; ``KeyError`` fuer ein unbekanntes."""
        ...

    def verfuegbare_tafeln(self) -> FrozenSet[str]:
        """Die Namen der Alterstafeln, die das Zielsystem fuehrt."""
        ...

    def pruefe_alterstafel(self, name: str, werte: Mapping[int, float]) -> None:
        """Alter -> qx gegen die Tafelregeln des Zielsystems halten;
        ``ValueError`` mit dem Grund, sonst nichts."""
        ...

    def tafeln_lesen(
        self, text: str
    ) -> Tuple[Mapping[str, Mapping[int, float]], FrozenSet[str]]:
        """Den Tafelspeicher des Zielsystems aus seinem Text lesen: die
        Alterstafeln mit Werten und ALLE vergebenen Tafelnamen (auch die
        der Select-Tafeln); ``ValueError``, wenn der Text die Tafelregeln
        verletzt."""
        ...

    def fuehrungsgrundlagen(
        self, ansicht: Fuehrungsansicht, merkmale: Any,
    ) -> Callable[[int, str], Mapping[str, Any]]:
        """Wirksame Tarifzelle je Police aus der validierten Fuehrungsansicht.

        Fehlende Generation oder Merkmalszelle ist ein ``ValueError``.
        """
        ...
