"""Tarif-Spezifikation: das Stage-2-Artefakt (SDD in gebundener Form).

Die Spez ist KEIN Prosa-Dokument fuers Modell und KEINE freie DSL,
sondern die typisierte Parametrierung des Kern-Rueckgrats: je
Parametrierungszelle die aufgeloesten ModelPoint-Felder, dazu die
Tafel-Anforderungen (Importe und Ableitungen wie die Unisex-
Mischtafel), das berechnete Struktur-Urteil (Parametrierung derselben
Familie oder mehr?) und benannte Erweiterungsstellen fuer alles, was
das Schema sprengt — nur DORT entstuende freie Implementierung.

Aus der Spez werden generiert: die menschenlesbare Fachspezifikation
(P7, das G-1-Abnahmedokument) und die Kern-Parametrierung. Die Spez
ist gegen die A-Box deterministisch validierbar (jeder Wert muss dort
belegt sein — die Spez ist Projektion, nicht zweite Quelle).

Knoten: klv
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rechner_pipeline.ontologie.aussage import Wert
from rechner_pipeline.ontologie.tbox import TBOX_VERSION

SPEZ_VERSION = "0.1.0"

#: Das Rechen-Rueckgrat, auf das diese Spez parametriert. Fall-1-Umfang:
#: der stabile KLV-Kern (Kommutation + Zustandsmodell, Version 2.x).
BACKBONE = "kern.klv/kommutation+zustandsmodell"


class StrukturUrteil(BaseModel):
    """Das BERECHNETE Urteil: Integration oder neues Produkt (F1/D2).

    Dirks Kernvorgabe an den Workflow — "erkennen, dass der neue
    Rechner strukturell zum alten passt, und integrieren statt
    duplizieren" — ist genau dieses Objekt: deterministisch abgeleitet
    aus dem A-Box-Vergleich, nicht behauptet.
    """

    model_config = ConfigDict(extra="forbid")

    ergebnis: Literal[
        "parametrierung",
        "parametrierung_mit_erweiterung",
        "neue_produktfamilie",
    ]
    referenz_generation: Optional[str] = None
    neue_dimensionen: List[str] = Field(default_factory=list)
    neue_tafeln: List[str] = Field(default_factory=list)
    geaenderte_parameter: List[str] = Field(default_factory=list)
    #: Anforderungen, die das Rueckgrat heute NICHT erfuellt — jede
    #: erzeugt eine Erweiterungsstelle.
    formel_erweiterungen: List[str] = Field(default_factory=list)
    begruendung: List[str] = Field(min_length=1)


class TafelAbleitung(BaseModel):
    """Eine abgeleitete Tafel (z. B. Unisex-Mischung) als DATEN-Regel.

    Die VBA-Mischformel ``qx = min(1, f*qx_M + (1-f)*qx_F)`` wird beim
    Import einmal ausgerechnet und als eigene Tafel gespeichert —
    bit-treu (dieselbe Formel, dieselben Doubles), aber ohne
    Kern-Formelaenderung: die exakte Tafelnamens-Aufloesung des Kerns
    greift zuerst.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)          # z. B. DAV2008_T_NR_U70
    basis_m: str = Field(min_length=1)       # DAV2008_T_NR_M
    basis_f: str = Field(min_length=1)       # DAV2008_T_NR_F
    maenneranteil: float = Field(ge=0.0, le=1.0)
    regel: Literal["min1_linear"] = "min1_linear"


class ZellSpez(BaseModel):
    """Die aufgeloeste Parametrierung EINER Merkmalskombination."""

    model_config = ConfigDict(extra="forbid")

    knoten: str = Field(min_length=1)        # A-Box-Knoten der Zelle
    auspraegungen: Dict[str, str] = Field(default_factory=dict)
    #: Aufgeloeste ModelPoint-Felder (tafel bereits final, d. h.
    #: inklusive Status-Suffix und ggf. Unisex-Ableitungsname).
    model_point: Dict[str, Wert] = Field(min_length=1)


class Erweiterungsstelle(BaseModel):
    """Benannte Stelle, an der das Schema nicht reicht (D2)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    beschreibung: str = Field(min_length=1)
    status: Literal["offen", "implementiert"] = "offen"


class TarifSpez(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spez_version: str = SPEZ_VERSION
    tbox_version: str = TBOX_VERSION
    generation: str = Field(min_length=1)    # A-Box-Knoten (klv/tg2015)
    familie: Literal["klv"]
    backbone: str = BACKBONE
    urteil: StrukturUrteil
    #: Unisex-Kalkulationsvorgabe der Generation (z. B. "U70").
    unisex: Optional[str] = None
    zellen: List[ZellSpez] = Field(min_length=1)
    #: Tafeln (xml-Ebene, mit _M/_F), die der Kern noch nicht fuehrt.
    tafel_importe: List[str] = Field(default_factory=list)
    tafel_ableitungen: List[TafelAbleitung] = Field(default_factory=list)
    erweiterungsstellen: List[Erweiterungsstelle] = Field(default_factory=list)

    @model_validator(mode="after")
    def _konsistenz(self) -> "TarifSpez":
        if self.urteil.formel_erweiterungen and not self.erweiterungsstellen:
            raise ValueError(
                "Formel-Erweiterungen ohne benannte Erweiterungsstellen — "
                "freie Implementierung braucht einen benannten Ort (D2)"
            )
        offene = [e.id for e in self.erweiterungsstellen if e.status == "offen"]
        if self.urteil.ergebnis == "parametrierung" and offene:
            raise ValueError(
                f"Urteil 'parametrierung' mit offenen Erweiterungsstellen "
                f"{offene} — das Urteil waere gelogen"
            )
        if self.unisex is not None and not self.tafel_ableitungen:
            raise ValueError(
                "unisex ohne Tafel-Ableitungen — die Mischtafel ist die "
                "Umsetzung der Unisex-Vorgabe"
            )
        return self
