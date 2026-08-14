"""Diskrepanz: der Widerspruch zwischen Quellen als Modellobjekt (P2).

Wenn Tarifmeldung und Rechner sich widersprechen — Normalfall, nicht
Ausnahme — entsteht eine Diskrepanz mit BEIDEN Lesarten und ihren
Belegen. Kein stiller Overwrite, keine Mehrheitsentscheidung durch ein
Modell. Die Aufloesung ist ein expliziter Vorgang mit Verantwortlichem
und Begruendung; erst sie macht aus dem Widerspruch wieder eine
belegte Aussage.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rechner_pipeline.ontologie.aussage import Lesart, Wert


class Entscheidung(BaseModel):
    """Die menschliche Aufloesung einer Diskrepanz (P9-Baustein)."""

    model_config = ConfigDict(extra="forbid")

    entscheider: str = Field(min_length=1)
    begruendung: str = Field(min_length=1)
    gewaehlter_wert: Wert
    entschieden_am: str = Field(min_length=1)  # ISO-8601 UTC


class Diskrepanz(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Deterministische ID: ``<knoten>#<feld>`` — dieselbe Kollision
    #: erzeugt dieselbe Diskrepanz, Laeufe bleiben vergleichbar.
    id: str = Field(min_length=1)
    knoten: str = Field(min_length=1)
    feld: str = Field(min_length=1)
    lesarten: List[Lesart] = Field(min_length=2)
    status: Literal["offen", "aufgeloest"] = "offen"
    entscheidung: Optional[Entscheidung] = None

    @model_validator(mode="after")
    def _konsistenz(self) -> "Diskrepanz":
        if self.id != f"{self.knoten}#{self.feld}":
            raise ValueError(
                f"Diskrepanz-ID {self.id!r} ist nicht '<knoten>#<feld>' — "
                "die ID ist abgeleitet, nicht frei"
            )
        if self.status == "aufgeloest" and self.entscheidung is None:
            raise ValueError(
                "aufgeloest ohne Entscheidung (Entscheider + Begruendung) — "
                "genau das unterscheidet Aufloesung von Overwrite"
            )
        if self.status == "offen" and self.entscheidung is not None:
            raise ValueError("offen mit Entscheidung — Status nachziehen")
        return self


def diskrepanz_id(knoten: str, feld: str) -> str:
    return f"{knoten}#{feld}"
