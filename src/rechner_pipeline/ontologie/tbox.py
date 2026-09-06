"""T-Box v0: das Domaenenmodell des Migrationsfalls (Fall-1-Umfang).

Menschlich verantwortet und versioniert — Agenten aendern diese Datei
nie autonom; Aenderungsvorschlaege sind Artefakte, ueber die ein Mensch
entscheidet (Gate A-K1). Die A-Box (Instanzen) wird von Agenten
befuellt und ist Single Source of Truth fuer die nachgelagerten
Stufen; Code und Testfaelle sind Projektionen daraus.

Umfang v0 = was der erste Migrationsfall (KLV TG2012 -> TG2015)
zwingend braucht, nichts auf Vorrat: eine Produktfamilie (gemischte
KLV), Tarifgenerationen mit Merkmalsdimensionen (Tarifart,
Raucherstatus) und Parametrierungszellen, deren Parameterfelder exakt
auf die Stellschrauben des Kern-ModelPoints abbilden. Keine BU-,
Renten- oder Fonds-Klassen (kommen mit ihren Faellen als
T-Box-Erweiterung ueber A-K1).

Knoten: klv
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rechner_pipeline.ontologie.aussage import Aussage
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz
from rechner_pipeline.ontologie.ids import knoten_id, zellen_segment

TBOX_VERSION = "0.1.0"

#: Pflichtumfang einer Parametrierungszelle (P6-Referenz): ohne diese
#: Felder ist ein Tarif nicht rechenbar. Die Namen SIND die Feldnamen
#: des Kern-ModelPoints — die Projektion A-Box -> ModelPoint ist ein
#: Mapping, keine Uebersetzung.
PFLICHT_PARAMETER = (
    "zins",
    "tafel",
    "alpha",
    "beta1",
    "gamma1",
    "gamma2",
    "gamma3",
    "policy_fee",
    "stoab_satz",
    "stoab_min",
    "stoab_max",
    "min_alter_flex",
    "min_rlz_flex",
)

#: Optionale Parameter (Tarifwerk-Stellschrauben mit Kern-Defaults).
OPTIONALE_PARAMETER = (
    "zillmer_dauer",
    "ratzu_zw2",
    "ratzu_zw4",
    "ratzu_zw12",
)

BEKANNTE_PARAMETER = frozenset(PFLICHT_PARAMETER) | frozenset(OPTIONALE_PARAMETER)

QUELLE_ARTEN = ("tarifmeldung", "tarifrechner", "bestand")


class Quelle(BaseModel):
    """Eine registrierte Quelle des Falls (Bezug: Eingang-Register)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    datei: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    art: Literal["tarifmeldung", "tarifrechner", "bestand"]


class Merkmalsdimension(BaseModel):
    """Eine Differenzierungs-Dimension des Tarifs (z. B. Tarifart)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    auspraegungen: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _eindeutig(self) -> "Merkmalsdimension":
        if len(set(self.auspraegungen)) != len(self.auspraegungen):
            raise ValueError(f"Dimension {self.id}: doppelte Auspraegungen")
        for a in self.auspraegungen:
            if not a or a != a.lower():
                raise ValueError(
                    f"Dimension {self.id}: Auspraegung {a!r} nicht "
                    "kleingeschrieben (IDs, keine Anzeigetexte)"
                )
        return self


class Parametrierungszelle(BaseModel):
    """Eine Merkmalskombination mit ihren Rechnungsgrundlagen.

    Jede Zelle mappt vollstaendig auf die Stellschrauben des
    Kern-ModelPoints — "neue Tarifgeneration = Parametrierung, keine
    Formelaenderung" ist die Grundannahme; was sie sprengt, gehoert
    als Erweiterungsstelle in die Spez, nicht hierher.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    auspraegungen: Dict[str, str] = Field(default_factory=dict)
    parameter: Dict[str, Aussage] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _konsistenz(self) -> "Parametrierungszelle":
        if self.id != zellen_segment(self.auspraegungen):
            raise ValueError(
                f"Zellen-ID {self.id!r} passt nicht zu den Auspraegungen "
                f"(erwartet {zellen_segment(self.auspraegungen)!r}) — die "
                "ID ist abgeleitet, nicht frei"
            )
        unbekannt = set(self.parameter) - BEKANNTE_PARAMETER
        if unbekannt:
            raise ValueError(
                f"Zelle {self.id}: unbekannte Parameter {sorted(unbekannt)} "
                "— kein stiller Tippfehler-Parameter; T-Box erweitern (A-K1) "
                "oder Feldname korrigieren"
            )
        return self


class Tarifgeneration(BaseModel):
    """Eine Tarifgeneration einer Produktfamilie (der Fachknoten)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)          # z. B. "klv/tg2015"
    name: str = Field(min_length=1)        # z. B. "TG2015"
    familie: Literal["klv"]                # Fall-1-Umfang
    quellen: List[Quelle] = Field(min_length=1)
    dimensionen: List[Merkmalsdimension] = Field(default_factory=list)
    zellen: List[Parametrierungszelle] = Field(min_length=1)
    #: Unisex-Kalkulationsvorgabe (z. B. "U70" = 70 % Maenneranteil);
    #: None = geschlechtsspezifisch. Fachliche Aussage der Meldung.
    unisex: Optional[Aussage] = None
    #: Quellname -> Zielfeld (fremde Benennungslogik der Quelle wird
    #: erfasst, nicht normalisiert weggeworfen), z. B. "StoAb_rel" ->
    #: "parameter:stoab_satz". F1-Anforderung der Fragerunde.
    quellnamen: Dict[str, str] = Field(default_factory=dict)
    #: Beobachtungen der Extraktions-Agenten, die kein Schemafeld haben
    #: (z. B. Tarifsubstanz ausserhalb des Pflichtumfangs wie beta0) —
    #: sie gehoeren ins A-Q1-Dokument, nicht in den Papierkorb des Merge
    #: (Systempruefung Befunde 9/30).
    anmerkungen: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _konsistenz(self) -> "Tarifgeneration":
        erwartete_id = knoten_id(self.familie, self.name.lower())
        if self.id != erwartete_id:
            raise ValueError(
                f"Generations-ID {self.id!r} weicht von {erwartete_id!r} ab"
            )
        dim_ids = [d.id for d in self.dimensionen]
        if len(set(dim_ids)) != len(dim_ids):
            raise ValueError(f"{self.id}: doppelte Dimensions-IDs")
        # Zellen decken das kartesische Produkt exakt ab — eine fehlende
        # Kombination waere eine stillschweigend unparametrierte Zelle (P6).
        erwartet = {zellen_segment(kombi) for kombi in _kartesisch(self.dimensionen)}
        vorhanden = [z.id for z in self.zellen]
        if len(set(vorhanden)) != len(vorhanden):
            raise ValueError(f"{self.id}: doppelte Zellen")
        fehlt = erwartet - set(vorhanden)
        fremd = set(vorhanden) - erwartet
        if fehlt or fremd:
            raise ValueError(
                f"{self.id}: Zellen decken den Merkmalsraum nicht — "
                f"fehlend {sorted(fehlt)}, unbekannt {sorted(fremd)}"
            )
        for zelle in self.zellen:
            for dim_id, wert in zelle.auspraegungen.items():
                dim = next((d for d in self.dimensionen if d.id == dim_id), None)
                if dim is None:
                    raise ValueError(
                        f"{self.id}/{zelle.id}: unbekannte Dimension {dim_id!r}"
                    )
                if wert not in dim.auspraegungen:
                    raise ValueError(
                        f"{self.id}/{zelle.id}: {wert!r} ist keine "
                        f"Auspraegung von {dim_id}"
                    )
        return self


def _kartesisch(dimensionen: List[Merkmalsdimension]) -> List[Dict[str, str]]:
    kombis: List[Dict[str, str]] = [{}]
    for dim in sorted(dimensionen, key=lambda d: d.id):
        kombis = [
            {**kombi, dim.id: a} for kombi in kombis for a in dim.auspraegungen
        ]
    return kombis


class ABox(BaseModel):
    """Die Instanzen eines Migrationsfalls — SSOT fuer Stage 2 und 3."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    tbox_version: str = TBOX_VERSION
    fall: str = Field(min_length=1)
    generationen: List[Tarifgeneration] = Field(default_factory=list)
    diskrepanzen: List[Diskrepanz] = Field(default_factory=list)
