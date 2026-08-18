"""Config loading + validation for the Bestandsdaten module.

Knoten: klv, bu
"""

from __future__ import annotations

from pathlib import Path

from rechner_pipeline.bestand.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = REPO_ROOT / "configs" / "bestand_klv.toml"


def test_example_config_loads_and_validates():
    config = load_config(EXAMPLE)
    assert config.validate() == []
    assert config.seed == 20260811
    namen = [g.name for g in config.generationen]
    # Die Generationen folgen den Hoechstrechnungszins-Stufen und sind
    # zeitlich lueckenlos aneinandergereiht; die juengste verkauft weiter.
    assert namen[0] == "KLV-1994" and len(namen) >= 2
    assert namen == sorted(namen)
    for vorher, danach in zip(config.generationen, config.generationen[1:]):
        assert vorher.gueltig_bis < danach.gueltig_von
        assert danach.zins <= vorher.zins
    assert config.generationen[-1].neuzugang_pro_jahr > 0
    gen = config.generationen[0]
    assert gen.tafel == "DAV1994_T"
    assert gen.generation_fields()["zins"] == 0.04
    assert set(gen.verteilungen) >= {"entry_age", "sex", "duration",
                                     "premium_duration", "sum_insured", "zahlweise"}


def test_tarif_stellschrauben_defaults_und_vollstaendige_generation_fields():
    """Nicht konfigurierte Stellschrauben tragen die Kernel-Defaults, und
    generation_fields() deckt den vollen GENERATION_FIELDS-Contract ab."""
    from rechner_pipeline.models.bestand import GENERATION_FIELDS

    gen = load_config(EXAMPLE).generationen[0]
    fields = gen.generation_fields()
    assert set(fields) == set(GENERATION_FIELDS)
    assert fields["stoab_satz"] == 0.01
    assert fields["stoab_min"] == 50.0
    assert fields["stoab_max"] == 150.0
    assert fields["zillmer_dauer"] == 5
    assert (fields["ratzu_zw2"], fields["ratzu_zw4"], fields["ratzu_zw12"]) == (
        0.02, 0.03, 0.05,
    )


def test_missing_distribution_is_an_error(tmp_path: Path):
    toml = """
[meta]
seed = 1
[[generation]]
name = "G"
knoten = "klv/plv_test"
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
knoten = "klv/plv_test"
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
knoten = "klv/plv_test"
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


# --------------------------------------------------------------------------- #
# Ontologie-Bindung der Generationen (Integritaet: keine Parametrierung
# am System vorbei — jede gerechnete Generation ist ein Knoten)
# --------------------------------------------------------------------------- #


def _generation_kwargs(**override):
    import datetime as dt

    basis = dict(
        name="G", knoten="klv/plv_test",
        gueltig_von=dt.date(2000, 1, 1), gueltig_bis=dt.date(2010, 12, 31),
        sample_size=10, max_endalter=85, zins=0.02, tafel="DAV2008_T",
        alpha=0.025, beta1=0.025, gamma1=0.0008, gamma2=0.00125,
        gamma3=0.0025, policy_fee=24.0, min_alter_flex=60, min_rlz_flex=5,
    )
    basis.update(override)
    return basis


def test_generation_ohne_knoten_ist_ungueltig():
    from rechner_pipeline.bestand.config import TarifGeneration

    fehler = TarifGeneration(**_generation_kwargs(knoten="")).validate()
    assert any("knoten fehlt" in f for f in fehler)


def test_knoten_form_und_wurzel_werden_geprueft():
    from rechner_pipeline.bestand.config import TarifGeneration

    # Form: mindestens familie/generation, nur [a-z0-9_]
    fehler = TarifGeneration(**_generation_kwargs(knoten="klv")).validate()
    assert any("keine gueltige Knoten-ID" in f for f in fehler)
    fehler = TarifGeneration(
        **_generation_kwargs(knoten="klv/KLV-1994")).validate()
    assert any("keine gueltige Knoten-ID" in f for f in fehler)
    # Wurzel muss die Produktfamilie sein:
    fehler = TarifGeneration(
        **_generation_kwargs(knoten="bu/plv_2000")).validate()
    assert any("Knoten-Wurzel ist die Produktfamilie" in f for f in fehler)
    # ... und eine migrierte ID ist genauso zulaessig wie eine Demo-ID
    # (die Minimal-Generation hat keine Verteilungen — geprueft wird nur,
    # dass KEIN knoten-Befund dabei ist):
    fehler = TarifGeneration(
        **_generation_kwargs(knoten="klv/tg2015")).validate()
    assert not [f for f in fehler if "noten" in f]


def test_beispiel_configs_tragen_knoten_konsistent():
    """Gleicher Knoten => gleiche Rechnungsgrundlagen, ueber ALLE
    Beispiel-Configs hinweg. Sonst gaebe es zwei Wahrheiten unter einer ID."""
    from rechner_pipeline.bestand.config import GENERATION_FIELDS, load_config

    gesehen = {}
    for datei in ("bestand_klv.toml", "bestand_bu.toml", "bestand_gesamt.toml"):
        cfg = load_config(REPO_ROOT / "configs" / datei)
        assert cfg.validate() == [], datei
        for g in cfg.generationen:
            assert g.knoten, f"{datei}: {g.name} ohne Knoten"
            felder = {f: getattr(g, f) for f in GENERATION_FIELDS}
            felder["produkt"] = g.produkt
            if g.knoten in gesehen:
                assert gesehen[g.knoten] == (g.name, felder), (
                    f"Knoten {g.knoten} traegt in {datei} andere "
                    "Rechnungsgrundlagen als in einer anderen Config"
                )
            gesehen[g.knoten] = (g.name, felder)
    assert set(gesehen) == {
        "klv/plv_1994", "klv/plv_2000", "klv/plv_2004", "klv/plv_2007", "klv/plv_2008",
        "klv/plv_2012", "klv/plv_2015", "klv/plv_2017", "klv/plv_2022",
        "bu/plv_2000", "bu/plv_2017",
    }


def test_tarifplan_dokumentiert_die_plv_generationen():
    """P7-Drift-Schutz: die Paragraf-13-Tabellen der Tarifplaene muessen
    den Configs entsprechen — der Tarifplan darf nichts anderes behaupten
    als das, was der Bestand rechnet."""
    from rechner_pipeline.bestand.config import load_config

    cfg = load_config(REPO_ROOT / "configs" / "bestand_gesamt.toml")
    klv_md = (REPO_ROOT / "docs" / "tarifplaene" / "klv.md").read_text("utf-8")
    bu_md = (REPO_ROOT / "docs" / "tarifplaene" / "bu.md").read_text("utf-8")
    for g in cfg.generationen:
        doc = klv_md if g.produkt == "klv" else bu_md
        if g.produkt == "klv":
            zeile = (
                f"| `{g.knoten}` | {g.name} | "
                f"{g.gueltig_von:%Y-%m}–{g.gueltig_bis:%Y-%m} | "
                f"{g.zins:.2%} | {g.tafel} | {g.alpha} | {g.beta1} | "
                f"{g.gamma1}/{g.gamma2}/{g.gamma3} | {g.policy_fee:.0f} |"
            )
        else:
            zeile = (
                f"| `{g.knoten}` | {g.name} | "
                f"{g.gueltig_von:%Y-%m}–{g.gueltig_bis:%Y-%m} | "
                f"{g.zins:.2%} | {g.tafel_aktiv}/{g.tafel_i}/"
                f"{g.tafel_ri}/{g.tafel_ti} | {g.zuschlag} |"
            )
        assert zeile in doc, (
            f"Tarifplan-Paragraf 13 veraltet fuer {g.knoten} — erwartete "
            f"Zeile:\n{zeile}"
        )
