"""Diskrepanz: der Widerspruch zwischen Quellen als Modellobjekt (P2).

Wenn Tarifmeldung und Rechner sich widersprechen — Normalfall, nicht
Ausnahme — entsteht eine Diskrepanz mit BEIDEN Lesarten und ihren
Belegen. Kein stiller Overwrite, keine Mehrheitsentscheidung durch ein
Modell. Die Aufloesung ist ein expliziter Vorgang mit Verantwortlichem
und Begruendung; erst sie macht aus dem Widerspruch wieder eine
belegte Aussage.

Knoten: klv
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rechner_pipeline.ontologie.aussage import Lesart, Wert


class Beleg(BaseModel):
    """Die Rechnung, auf die sich eine Aufloesung stuetzt.

    Eine Begruendung in Prosa kann auf eine Datei VERWEISEN; sie kann
    nicht sichern, dass es noch dieselbe ist. Genau das fiel beim ersten
    vollstaendigen Lauf auf: Alle acht Diskrepanzen beriefen sich woertlich
    auf ``abgeleitet/berichte/abzugsabgleich.json`` — und deren Pruefsumme
    stand in keinem Ledger und keinem Snapshot. Die Datei haette
    ausgetauscht werden koennen, ohne dass ein Gate anschlaegt, und mit ihr
    der Beweis fuer die gesamte Parametrierung.

    Der Beleg macht daraus eine Bindung: Gate P-Q3 rechnet die Pruefsumme
    nach, statt der Begruendung zu glauben.
    """

    model_config = ConfigDict(extra="forbid")

    #: Fall-relativer Pfad, z. B. ``abgeleitet/berichte/abzugsabgleich.json``.
    datei: str = Field(min_length=1)
    sha256: str = Field(min_length=64, max_length=64)

    @model_validator(mode="after")
    def _hexziffern(self) -> "Beleg":
        if any(z not in "0123456789abcdef" for z in self.sha256):
            raise ValueError("sha256 ist keine Hex-Zeichenkette")
        return self


class Entscheidung(BaseModel):
    """Die Aufloesung einer Diskrepanz (P9-Baustein).

    ``vorlaeufig=True`` kennzeichnet eine Arbeits-Aufloesung (z. B. eines
    Agenten fuer einen Golden-Master-Lauf): sie darf Stage 2/3 tragen,
    aber KEIN menschliches Gate passieren — der P9-Snapshot verweigert
    die Abnahme, solange vorlaeufige Entscheidungen existieren. So kann
    der vorlaeufige Zustand nicht still zum Dauerzustand werden (P2/P4).
    """

    model_config = ConfigDict(extra="forbid")

    entscheider: str = Field(min_length=1)
    begruendung: str = Field(min_length=1)
    gewaehlter_wert: Wert
    entschieden_am: str = Field(min_length=1)  # ISO-8601 UTC
    vorlaeufig: bool = False
    #: Die deterministische Rechnung, die die Lesart stuetzt — Datei und
    #: Pruefsumme. Optional, weil nicht jede Aufloesung eine Rechnung hat
    #: (manche entscheidet das Aktuariat aus dem Tarifwerk). Wo es eine
    #: gibt, gehoert sie hierher und nicht nur in den Begruendungstext.
    beleg: Optional[Beleg] = None


class Diskrepanz(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: Deterministische ID: ``<knoten>#<feld>`` — dieselbe Kollision
    #: erzeugt dieselbe Diskrepanz, Laeufe bleiben vergleichbar.
    id: str = Field(min_length=1)
    knoten: str = Field(min_length=1)
    feld: str = Field(min_length=1)
    lesarten: List[Lesart] = Field(min_length=2)   # Lesart selbst ist frozen
    status: Literal["offen", "aufgeloest"] = "offen"
    entscheidung: Optional[Entscheidung] = None
    #: Append-only: ersetzte (vorlaeufige) Entscheidungen bleiben
    #: nachvollziehbar — der Weg vorlaeufig -> endgueltig ist Teil der
    #: Nachweiskette, kein Overwrite (Systempruefung Befund 24).
    entscheidungs_historie: List[Entscheidung] = Field(default_factory=list)

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
