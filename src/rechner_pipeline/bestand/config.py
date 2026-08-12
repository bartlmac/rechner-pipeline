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

from rechner_pipeline.models.bestand import GENERATION_FIELD_DEFAULTS, GENERATION_FIELDS

_D = GENERATION_FIELD_DEFAULTS  # Kernel-Defaults der Tarif-Stellschrauben

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
    #: Simulierter Neuzugang je Kalenderjahr (Fortschreibung ab
    #: Referenzstichtag); 0 = kein Neuzugang. Wirkt nur innerhalb des
    #: Gueltigkeitsfensters der Generation.
    neuzugang_pro_jahr: int = 0
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
    # Tarifwerk-Stellschrauben; Defaults = Kernel-Defaults (Blattwerte):
    stoab_satz: float = _D["stoab_satz"]
    stoab_min: float = _D["stoab_min"]
    stoab_max: float = _D["stoab_max"]
    zillmer_dauer: int = _D["zillmer_dauer"]
    ratzu_zw2: float = _D["ratzu_zw2"]
    ratzu_zw4: float = _D["ratzu_zw4"]
    ratzu_zw12: float = _D["ratzu_zw12"]
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
        if not 0 <= self.neuzugang_pro_jahr <= 10_000:
            errors.append(f"{prefix}: neuzugang_pro_jahr ausserhalb [0, 10000]")
        if not 0 < self.max_endalter <= 121:
            errors.append(f"{prefix}: max_endalter ausserhalb (0, 121]")
        if self.zins <= -1.0:
            errors.append(f"{prefix}: zins <= -100%")
        if not self.tafel:
            errors.append(f"{prefix}: tafel fehlt")
        else:
            # max_endalter muss vor der Tafel-Erschoepfung liegen (Dx = 0),
            # sonst kann ein voll validiertes Setup Vertraege erzeugen, deren
            # Fortschreibung im Kern an Dx=0 scheitert.
            from rechner_pipeline.kern import MissingMortalityTableError
            from rechner_pipeline.kern.kommutation import fuer

            try:
                grenze = min(
                    max(a for a in range(len(kom.dx)) if kom.dx[a] > 0.0)
                    for kom in (
                        fuer("M", self.tafel, self.zins),
                        fuer("F", self.tafel, self.zins),
                    )
                )
            except MissingMortalityTableError as exc:
                errors.append(f"{prefix}: {exc}")
            else:
                if self.max_endalter > grenze:
                    errors.append(
                        f"{prefix}: max_endalter {self.max_endalter} liegt hinter "
                        f"der Tafel-Erschoepfung von {self.tafel} "
                        f"(letztes Alter mit Dx > 0: {grenze})"
                    )
        if self.stoab_min > self.stoab_max:
            errors.append(f"{prefix}: stoab_min > stoab_max")
        if self.stoab_satz < 0:
            errors.append(f"{prefix}: stoab_satz < 0")
        if self.zillmer_dauer <= 0:
            errors.append(f"{prefix}: zillmer_dauer <= 0")
        for name in ("ratzu_zw2", "ratzu_zw4", "ratzu_zw12"):
            if getattr(self, name) < 0:
                errors.append(f"{prefix}: {name} < 0")
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
class EreignisConfig:
    """Annual event rates of the Fortschreibung (Ereignis-Engine).

    All-zero defaults mean: no stochastic events, only the deterministic
    Ablauf. ``tod_faktor`` scales the first-order qx of the tariff basis
    (1.0 = table mortality; 0.0 = no death simulation). ``erh_rate`` is the
    annual acceptance probability of the dynamische Erhoehung (creates a new
    Erhoehungsscheibe of ``erh_prozent`` of the current total sum insured).
    """

    storno_rate: float = 0.0
    pex_rate: float = 0.0
    tod_faktor: float = 0.0
    erh_rate: float = 0.0
    erh_prozent: float = 0.0

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not 0.0 <= self.storno_rate < 1.0:
            errors.append("ereignisse: storno_rate ausserhalb [0, 1)")
        if not 0.0 <= self.pex_rate < 1.0:
            errors.append("ereignisse: pex_rate ausserhalb [0, 1)")
        if self.tod_faktor < 0.0:
            errors.append("ereignisse: tod_faktor < 0")
        if not 0.0 <= self.erh_rate < 1.0:
            errors.append("ereignisse: erh_rate ausserhalb [0, 1)")
        if self.erh_prozent < 0.0:
            errors.append("ereignisse: erh_prozent < 0")
        if self.erh_rate > 0.0 and self.erh_prozent == 0.0:
            errors.append("ereignisse: erh_rate > 0 verlangt erh_prozent > 0")
        return errors


@dataclass
class BestandConfig:
    seed: int
    beschreibung: str
    generationen: List[TarifGeneration]
    plausibilitaet: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    ereignisse: EreignisConfig = field(default_factory=EreignisConfig)

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
        errors.extend(self.ereignisse.validate())
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
                neuzugang_pro_jahr=int(g.get("neuzugang_pro_jahr", 0)),
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
                stoab_satz=float(g.get("stoab_satz", _D["stoab_satz"])),
                stoab_min=float(g.get("stoab_min", _D["stoab_min"])),
                stoab_max=float(g.get("stoab_max", _D["stoab_max"])),
                zillmer_dauer=int(g.get("zillmer_dauer", _D["zillmer_dauer"])),
                ratzu_zw2=float(g.get("ratzu_zw2", _D["ratzu_zw2"])),
                ratzu_zw4=float(g.get("ratzu_zw4", _D["ratzu_zw4"])),
                ratzu_zw12=float(g.get("ratzu_zw12", _D["ratzu_zw12"])),
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

    e: Mapping[str, Any] = raw.get("ereignisse", {})
    ereignisse = EreignisConfig(
        storno_rate=float(e.get("storno_rate", 0.0)),
        pex_rate=float(e.get("pex_rate", 0.0)),
        tod_faktor=float(e.get("tod_faktor", 0.0)),
        erh_rate=float(e.get("erh_rate", 0.0)),
        erh_prozent=float(e.get("erh_prozent", 0.0)),
    )

    config = BestandConfig(
        seed=int(meta.get("seed", 0)),
        beschreibung=str(meta.get("beschreibung", "")),
        generationen=generationen,
        plausibilitaet=plausibilitaet,
        ereignisse=ereignisse,
    )
    if errors:
        raise ValueError("Config-Ladefehler: " + "; ".join(errors))
    return config
