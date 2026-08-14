"""Aussagen: Werte mit Provenienz, Zustand und Konfidenz (P1, P3).

Eine A-Box traegt keine nackten Werte. Jede fachliche Einzelaussage
("der Rechnungszins der Zelle einzel/nichtraucher ist 0,0175") ist ein
eigenes Objekt mit

* dem Wert,
* dem Zustand — ``belegt``, ``nicht_belegt``, ``mehrdeutig`` und
  ``widerspruechlich`` sind unterscheidbare Zustaende, nicht alle
  ``null`` (P3),
* der Provenienz je Beleg: Quelldatei + SHA-256 (bindet an das
  Eingang-Register des Falls), Fundstelle (Zelladresse, Tabellenindex,
  VBA-Zeile), erhebender Akteur, Zeitpunkt (P1),
* optionaler Konfidenz des erhebenden Akteurs.

Die Validierungsregeln sind Teil der Datenstruktur (Pydantic-
Validatoren), nicht Konvention: eine "belegte" Aussage ohne Beleg kann
nicht konstruiert werden.
"""

from __future__ import annotations

import enum
import math
from typing import List, Optional, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

#: JSON-faehige Wertetypen. bool VOR int (sonst frisst int die bools).
Wert = Union[bool, int, float, str]


class Zustand(str, enum.Enum):
    BELEGT = "belegt"
    NICHT_BELEGT = "nicht_belegt"
    MEHRDEUTIG = "mehrdeutig"
    WIDERSPRUECHLICH = "widerspruechlich"


class Provenienz(BaseModel):
    """Ein Beleg: wo die Aussage herkommt und wer sie erhoben hat."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quelle_datei: str = Field(min_length=1)
    quelle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    fundstelle: str = Field(min_length=1)
    akteur: str = Field(min_length=1)
    erhoben_am: str = Field(min_length=1)  # ISO-8601 UTC


def _pruefe_endlich(wert: Optional[Wert]) -> Optional[Wert]:
    """NaN/Inf sind keine fachlichen Werte — fail-fast am Eingang.

    Ein NaN wuerde jede Wertegleichheit verfehlen (NaN != NaN) und damit
    eine Diskrepanz erzeugen, die sich nie aufloesen laesst.
    """
    if isinstance(wert, float) and not math.isfinite(wert):
        raise ValueError(f"nicht-endlicher Wert {wert!r} ist keine Aussage")
    return wert


class Lesart(BaseModel):
    """Eine von mehreren Lesarten (bei mehrdeutig/widerspruechlich).

    Tupel statt Listen: eine Lesart ist nach Konstruktion unveraenderlich
    — nachtraegliche Listen-Mutation wuerde die Validierung umgehen.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    wert: Wert
    provenienz: Tuple[Provenienz, ...] = Field(min_length=1)

    _endlich = field_validator("wert")(_pruefe_endlich)


class Aussage(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    zustand: Zustand = Zustand.NICHT_BELEGT
    wert: Optional[Wert] = None
    konfidenz: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    #: Tupel statt Listen (auch hier): .append() wuerde validate_assignment
    #: umgehen — unveraenderlich nach Konstruktion.
    provenienz: Tuple[Provenienz, ...] = Field(default_factory=tuple)
    #: Nur bei mehrdeutig/widerspruechlich: die konkurrierenden Lesarten.
    lesarten: Tuple[Lesart, ...] = Field(default_factory=tuple)
    #: Bei widerspruechlich: Verweis auf das Diskrepanz-Objekt (P2).
    diskrepanz_id: Optional[str] = None

    _endlich = field_validator("wert")(_pruefe_endlich)

    @model_validator(mode="after")
    def _konsistenz(self) -> "Aussage":
        if self.zustand is Zustand.BELEGT:
            if self.wert is None:
                raise ValueError("belegt ohne Wert")
            if not self.provenienz:
                raise ValueError("belegt ohne Provenienz — P1 verlangt den Beleg")
            if self.lesarten:
                raise ValueError("belegt mit Lesarten (das waere mehrdeutig)")
        elif self.zustand is Zustand.NICHT_BELEGT:
            if self.wert is not None or self.provenienz or self.lesarten:
                raise ValueError(
                    "nicht_belegt traegt weder Wert noch Beleg — sonst "
                    "waere der Zustand gelogen"
                )
        else:  # mehrdeutig | widerspruechlich
            if len(self.lesarten) < 2:
                raise ValueError(
                    f"{self.zustand.value} braucht mindestens zwei Lesarten"
                )
            if self.wert is not None:
                raise ValueError(
                    f"{self.zustand.value} traegt keinen entschiedenen Wert "
                    "— die Aufloesung ist ein eigener Vorgang"
                )
            if self.zustand is Zustand.WIDERSPRUECHLICH and not self.diskrepanz_id:
                raise ValueError(
                    "widerspruechlich ohne diskrepanz_id — der Widerspruch "
                    "ist ein Modellobjekt, kein Zustandsflag (P2)"
                )
        return self


def belegt(
    wert: Wert,
    provenienz: List[Provenienz],
    konfidenz: Optional[float] = None,
) -> Aussage:
    return Aussage(
        zustand=Zustand.BELEGT, wert=wert,
        provenienz=provenienz, konfidenz=konfidenz,
    )


def nicht_belegt() -> Aussage:
    return Aussage()
