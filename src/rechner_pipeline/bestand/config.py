"""TOML configuration for the Bestandsdaten generator.

Text-based config (no Excel), read with stdlib ``tomllib`` and validated with
plain dataclasses returning error lists — the repo's schema idiom, no external
schema library. The category structure follows the DAV reference toolchain's
parameter semantics (tariff master data, distributions, correlations,
simulation/plausibility) with our own parameter values.

Layout (see ``examples/bestand_klv.toml``)::

    [meta]                      seed, beschreibung
    [[generation]]              KLV tariff generation (validity window, zins,
                                tafel, cost loadings, sample_size, ...)
    [generation.verteilungen.<merkmal>]   distribution spec per attribute
    [[generation.korrelation]]  pairwise Spearman rank correlations
    [plausibilitaet]            value bands for the sanity gate
"""

from __future__ import annotations

import datetime as _dt
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Tuple

from rechner_pipeline.models.bestand import GENERATION_FIELDS

#: Attributes every generation must configure a distribution for.
REQUIRED_MERKMALE: Tuple[str, ...] = (
    "entry_age",
    "sex",
    "duration",
    "premium_duration",
    "sum_insured",
    "zahlweise",
)

#: Distribution types implemented without scipy (project decision 2026-08-11:
#: full takeover of the reference generation incl. copula, lean dependencies).
#: gamma/beta would need scipy and raise NotImplementedError when configured.
SUPPORTED_TYPES: Tuple[str, ...] = (
    "normal",
    "normal_trunc",
    "lognormal",
    "weibull",
    "poisson",
    "empirical_discrete",
)

#: Attributes allowed in the correlation matrix (transformed via latent
#: normal; categorical attributes work like the reference does gender).
CORRELATABLE: Tuple[str, ...] = (
    "entry_age",
    "sex",
    "duration",
    "premium_duration",
    "sum_insured",
)


@dataclass
class VerteilungsSpec:
    merkmal: str
    typ: str
    params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors: List[str] = []
        p = self.params
        if self.typ not in SUPPORTED_TYPES:
            errors.append(
                f"verteilung {self.merkmal}: typ {self.typ!r} nicht unterstuetzt "
                f"(unterstuetzt: {list(SUPPORTED_TYPES)}; gamma/beta erst bei realem Bedarf)"
            )
            return errors
        if self.typ in ("normal", "normal_trunc"):
            for k in ("mean", "sd"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "sd" in p and float(p["sd"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: sd <= 0")
        if self.typ == "normal_trunc":
            for k in ("min", "max"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "min" in p and "max" in p and float(p["min"]) >= float(p["max"]):
                errors.append(f"verteilung {self.merkmal}: min >= max")
        if self.typ == "lognormal":
            for k in ("meanlog", "sdlog"):
                if k not in p:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt")
            if "sdlog" in p and float(p["sdlog"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: sdlog <= 0")
        if self.typ == "weibull":
            for k in ("shape", "scale"):
                if k not in p or float(p[k]) <= 0:
                    errors.append(f"verteilung {self.merkmal}: {k} fehlt oder <= 0")
        if self.typ == "poisson":
            if "lambda" not in p or float(p["lambda"]) <= 0:
                errors.append(f"verteilung {self.merkmal}: lambda fehlt oder <= 0")
        if self.typ == "empirical_discrete":
            values = p.get("values")
            probs = p.get("probs")
            if not values or not probs:
                errors.append(f"verteilung {self.merkmal}: values/probs fehlen")
            elif len(values) != len(probs):
                errors.append(f"verteilung {self.merkmal}: values/probs ungleich lang")
            elif any(float(w) < 0 for w in probs) or sum(float(w) for w in probs) <= 0:
                errors.append(f"verteilung {self.merkmal}: probs muessen >= 0 sein, Summe > 0")
        return errors


@dataclass
class Korrelation:
    var_i: str
    var_j: str
    rho: float

    def validate(self) -> List[str]:
        errors: List[str] = []
        for v in (self.var_i, self.var_j):
            if v not in CORRELATABLE:
                errors.append(f"korrelation {self.var_i}/{self.var_j}: {v} nicht korrelierbar")
        if self.var_i == self.var_j:
            errors.append(f"korrelation {self.var_i}: var_i == var_j")
        if not -1.0 < float(self.rho) < 1.0:
            errors.append(f"korrelation {self.var_i}/{self.var_j}: rho ausserhalb (-1, 1)")
        return errors


@dataclass
class TarifGeneration:
    name: str
    gueltig_von: _dt.date
    gueltig_bis: _dt.date
    sample_size: int
    max_endalter: int
    # Kernel-Tarifparameter (GENERATION_FIELDS des ModelPoint-Contracts):
    zins: float = 0.0
    tafel: str = ""
    alpha: float = 0.0
    beta1: float = 0.0
    gamma1: float = 0.0
    gamma2: float = 0.0
    gamma3: float = 0.0
    policy_fee: float = 0.0
    min_alter_flex: int = 0
    min_rlz_flex: int = 0
    verteilungen: Dict[str, VerteilungsSpec] = field(default_factory=dict)
    korrelationen: List[Korrelation] = field(default_factory=list)

    def generation_fields(self) -> Dict[str, Any]:
        """The kernel-side tariff parameters (joined into ModelPoint kwargs)."""
        return {name: getattr(self, name) for name in GENERATION_FIELDS}

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.name:
            errors.append("generation: name fehlt")
        prefix = f"generation {self.name or '?'}"
        if self.gueltig_von >= self.gueltig_bis:
            errors.append(f"{prefix}: gueltig_von >= gueltig_bis")
        if self.sample_size <= 0:
            errors.append(f"{prefix}: sample_size <= 0")
        if self.sample_size > 1_000_000:
            errors.append(
                f"{prefix}: sample_size > 1_000_000 (police_id-Nummernkreis je "
                "Generation ist 10 Mio; Obergrenze schuetzt vor Kollisionen)"
            )
        if not 0 < self.max_endalter <= 121:
            errors.append(f"{prefix}: max_endalter ausserhalb (0, 121]")
        if self.zins <= -1.0:
            errors.append(f"{prefix}: zins <= -100%")
        if not self.tafel:
            errors.append(f"{prefix}: tafel fehlt")
        for merkmal in REQUIRED_MERKMALE:
            if merkmal not in self.verteilungen:
                errors.append(f"{prefix}: verteilung fuer {merkmal} fehlt")
        for spec in self.verteilungen.values():
            errors.extend(f"{prefix}: {e}" for e in spec.validate())
        seen = set()
        for korr in self.korrelationen:
            errors.extend(f"{prefix}: {e}" for e in korr.validate())
            key = tuple(sorted((korr.var_i, korr.var_j)))
            if key in seen:
                errors.append(f"{prefix}: korrelation {key} doppelt")
            seen.add(key)
        # Die Korrelations-Kombination muss als Matrix realisierbar sein —
        # sonst wuerde die PSD-Reparatur der Copula die konfigurierten Werte
        # stillschweigend (bis ~Faktor 2) verfaelschen. Nicht-PSD = Config-Fehler.
        if self.korrelationen and not any("korrelation" in e for e in errors):
            import numpy as np

            from rechner_pipeline.bestand.stochastik import build_corr_matrix

            matrix = build_corr_matrix(CORRELATABLE, self.korrelationen)
            min_eig = float(np.linalg.eigvalsh((matrix + matrix.T) / 2.0).min())
            if min_eig < -1e-8:
                errors.append(
                    f"{prefix}: Korrelations-Kombination nicht realisierbar "
                    f"(Matrix nicht positiv semidefinit, min. Eigenwert {min_eig:.3f}) "
                    "— rhos abschwaechen oder Paare entfernen"
                )
        return errors


@dataclass
class BestandConfig:
    seed: int
    beschreibung: str
    generationen: List[TarifGeneration]
    plausibilitaet: Dict[str, Tuple[float, float]] = field(default_factory=dict)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.seed <= 0:
            errors.append("meta.seed fehlt oder <= 0 (Pflicht fuer Reproduzierbarkeit)")
        if not self.generationen:
            errors.append("mindestens eine [[generation]] erforderlich")
        names = [g.name for g in self.generationen]
        if len(names) != len(set(names)):
            errors.append("generation-Namen nicht eindeutig")
        for gen in self.generationen:
            errors.extend(gen.validate())
        for merkmal, band in self.plausibilitaet.items():
            if len(band) != 2 or float(band[0]) >= float(band[1]):
                errors.append(f"plausibilitaet {merkmal}: Band muss (min, max) mit min < max sein")
        return errors


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _to_date(value: Any, label: str, errors: List[str]) -> _dt.date:
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    errors.append(f"{label}: kein TOML-Datum")
    return _dt.date(1900, 1, 1)


def load_config(path: Path) -> BestandConfig:
    """Load and structurally parse a config; call ``.validate()`` afterwards."""
    raw = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    errors: List[str] = []
    meta: Mapping[str, Any] = raw.get("meta", {})

    generationen: List[TarifGeneration] = []
    for g in raw.get("generation", []):
        verteilungen: Dict[str, VerteilungsSpec] = {}
        for merkmal, spec in g.get("verteilungen", {}).items():
            params = {k: v for k, v in spec.items() if k != "typ"}
            verteilungen[merkmal] = VerteilungsSpec(
                merkmal=merkmal, typ=str(spec.get("typ", "")), params=params
            )
        korrelationen = [
            Korrelation(
                var_i=str(k.get("var_i", "")),
                var_j=str(k.get("var_j", "")),
                rho=float(k.get("rho", 0.0)),
            )
            for k in g.get("korrelation", [])
        ]
        generationen.append(
            TarifGeneration(
                name=str(g.get("name", "")),
                gueltig_von=_to_date(g.get("gueltig_von"), "gueltig_von", errors),
                gueltig_bis=_to_date(g.get("gueltig_bis"), "gueltig_bis", errors),
                sample_size=int(g.get("sample_size", 0)),
                max_endalter=int(g.get("max_endalter", 85)),
                zins=float(g.get("zins", 0.0)),
                tafel=str(g.get("tafel", "")),
                alpha=float(g.get("alpha", 0.0)),
                beta1=float(g.get("beta1", 0.0)),
                gamma1=float(g.get("gamma1", 0.0)),
                gamma2=float(g.get("gamma2", 0.0)),
                gamma3=float(g.get("gamma3", 0.0)),
                policy_fee=float(g.get("policy_fee", 0.0)),
                min_alter_flex=int(g.get("min_alter_flex", 0)),
                min_rlz_flex=int(g.get("min_rlz_flex", 0)),
                verteilungen=verteilungen,
                korrelationen=korrelationen,
            )
        )

    plausibilitaet: Dict[str, Tuple[float, float]] = {}
    for m, b in raw.get("plausibilitaet", {}).items():
        if isinstance(b, (list, tuple)) and len(b) == 2:
            plausibilitaet[str(m)] = (float(b[0]), float(b[1]))
        else:
            errors.append(f"plausibilitaet {m}: Band muss Liste [min, max] sein")

    config = BestandConfig(
        seed=int(meta.get("seed", 0)),
        beschreibung=str(meta.get("beschreibung", "")),
        generationen=generationen,
        plausibilitaet=plausibilitaet,
    )
    if errors:
        raise ValueError("Config-Ladefehler: " + "; ".join(errors))
    return config
