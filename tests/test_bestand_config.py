"""Config loading + validation for the Bestandsdaten module."""

from __future__ import annotations

from pathlib import Path

from rechner_pipeline.bestand.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


def test_example_config_loads_and_validates():
    config = load_config(EXAMPLE)
    assert config.validate() == []
    assert config.seed == 20260811
    assert [g.name for g in config.generationen] == ["KLV-1994", "KLV-2008"]
    gen = config.generationen[0]
    assert gen.tafel == "DAV1994_T"
    assert gen.generation_fields()["zins"] == 0.04
    assert set(gen.verteilungen) >= {"entry_age", "sex", "duration",
                                     "premium_duration", "sum_insured", "zahlweise"}


def test_missing_distribution_is_an_error(tmp_path: Path):
    toml = """
[meta]
seed = 1
[[generation]]
name = "G"
gueltig_von = 2000-01-01
gueltig_bis = 2001-01-01
sample_size = 10
max_endalter = 85
zins = 0.02
tafel = "DAV1994_T"
[generation.verteilungen.entry_age]
typ = "normal_trunc"
mean = 35.0
sd = 10.0
min = 18.0
max = 60.0
"""
    p = tmp_path / "c.toml"
    p.write_text(toml, encoding="utf-8")
    errors = load_config(p).validate()
    assert any("verteilung fuer sex fehlt" in e for e in errors)
    assert any("verteilung fuer sum_insured fehlt" in e for e in errors)


def test_unsupported_type_and_bad_rho_rejected(tmp_path: Path):
    toml = """
[meta]
seed = 1
[[generation]]
name = "G"
gueltig_von = 2000-01-01
gueltig_bis = 2001-01-01
sample_size = 10
max_endalter = 85
zins = 0.02
tafel = "DAV1994_T"
[generation.verteilungen.entry_age]
typ = "gamma"
mean = 2.0
sd = 1.0
[generation.verteilungen.sex]
typ = "empirical_discrete"
values = ["M", "F"]
probs = [1.0, 1.0]
[generation.verteilungen.duration]
typ = "empirical_discrete"
values = [10]
probs = [1.0]
[generation.verteilungen.premium_duration]
typ = "empirical_discrete"
values = [10]
probs = [1.0]
[generation.verteilungen.sum_insured]
typ = "lognormal"
meanlog = 10.0
sdlog = 0.5
[generation.verteilungen.zahlweise]
typ = "empirical_discrete"
values = [12]
probs = [1.0]
[[generation.korrelation]]
var_i = "entry_age"
var_j = "duration"
rho = 1.5
"""
    p = tmp_path / "c.toml"
    p.write_text(toml, encoding="utf-8")
    errors = load_config(p).validate()
    assert any("gamma" in e and "nicht unterstuetzt" in e for e in errors)
    assert any("rho ausserhalb" in e for e in errors)


def test_seed_is_mandatory(tmp_path: Path):
    p = tmp_path / "c.toml"
    p.write_text("[meta]\nbeschreibung = 'x'\n", encoding="utf-8")
    errors = load_config(p).validate()
    assert any("seed" in e for e in errors)


_BASE_GEN = """
[meta]
seed = 1
[[generation]]
name = "G"
gueltig_von = 2000-01-01
gueltig_bis = 2001-01-01
sample_size = {sample_size}
max_endalter = 85
zins = 0.02
tafel = "DAV1994_T"
[generation.verteilungen.entry_age]
typ = "normal_trunc"
mean = 35.0
sd = 10.0
min = 18.0
max = 60.0
[generation.verteilungen.sex]
typ = "empirical_discrete"
values = ["M", "F"]
probs = [1.0, 1.0]
[generation.verteilungen.duration]
typ = "empirical_discrete"
values = [10]
probs = [1.0]
[generation.verteilungen.premium_duration]
typ = "empirical_discrete"
values = [10]
probs = [1.0]
[generation.verteilungen.sum_insured]
typ = "lognormal"
meanlog = 10.0
sdlog = 0.5
[generation.verteilungen.zahlweise]
typ = "empirical_discrete"
values = [12]
probs = [1.0]
{extra}
"""


def test_non_psd_correlation_combination_rejected(tmp_path: Path):
    """Review-Fix: unrealisierbare rho-Kombinationen sind Config-Fehler —
    die Copula-PSD-Reparatur darf konfigurierte Werte nicht still verfaelschen."""
    extra = """
[[generation.korrelation]]
var_i = "entry_age"
var_j = "duration"
rho = 0.9
[[generation.korrelation]]
var_i = "duration"
var_j = "sum_insured"
rho = 0.9
[[generation.korrelation]]
var_i = "entry_age"
var_j = "sum_insured"
rho = -0.9
"""
    p = tmp_path / "c.toml"
    p.write_text(_BASE_GEN.format(sample_size=10, extra=extra), encoding="utf-8")
    errors = load_config(p).validate()
    assert any("nicht positiv semidefinit" in e for e in errors)


def test_sample_size_upper_bound(tmp_path: Path):
    p = tmp_path / "c.toml"
    p.write_text(_BASE_GEN.format(sample_size=2_000_000, extra=""), encoding="utf-8")
    errors = load_config(p).validate()
    assert any("sample_size > 1_000_000" in e for e in errors)


def test_malformed_plausibilitaet_band_is_load_error(tmp_path: Path):
    import pytest

    toml = _BASE_GEN.format(sample_size=10, extra="") + """
[plausibilitaet]
entry_age = [18, 30, 60]
"""
    p = tmp_path / "c.toml"
    p.write_text(toml, encoding="utf-8")
    with pytest.raises(ValueError, match="plausibilitaet entry_age"):
        load_config(p)
