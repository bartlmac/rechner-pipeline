"""Config des Tagesbetriebs: Trend, Wochentagsgewichte, Meldeverzug, Fenster.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B1: Die PLV traegt
ihre Generationen bis heute und den Abschnitt ``[tagesbetrieb]``. Was
hier steht, entscheidet spaeter, wie viel ein Werktag verkauft und wann
ein Tod gebucht wird — deshalb wird es beim Laden geprueft und nicht
erst beim Rechnen.

Knoten: klv, bu
"""

from __future__ import annotations

import copy
import datetime as dt
import math
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import (
    WOCHENTAGE,
    WOCHENTAGSGEWICHTE_VORGABE,
    Meldeverzug,
    Tagesbetrieb,
    TarifGeneration,
    config_aus_text,
    load_config,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"
KLV = REPO_ROOT / "configs" / "bestand_klv.toml"


def _generation(name: str, von: str, bis: str, sample_size: int = 10,
                produkt: str = "klv", extra: str = "") -> str:
    """Ein kleiner, gueltiger Generationsblock als TOML-Text."""
    knoten = f"{produkt}/plv_{name.lower()}"
    if produkt == "bu":
        return f"""
[[generation]]
name = "{name}"
knoten = "{knoten}"
produkt = "bu"
gueltig_von = {von}
gueltig_bis = {bis}
sample_size = {sample_size}
max_endalter = 67
zins = 0.01
tafel = "DAV1997_TAA"
{extra}
[generation.verteilungen.entry_age]
typ = "normal_trunc"
mean = 33.0
sd = 8.0
min = 20.0
max = 55.0
[generation.verteilungen.sex]
typ = "empirical_discrete"
values = ["M", "F"]
probs = [0.5, 0.5]
[generation.verteilungen.duration]
typ = "empirical_discrete"
values = [20, 25]
probs = [0.5, 0.5]
[generation.verteilungen.bu_rente]
typ = "lognormal"
meanlog = 9.4
sdlog = 0.35
"""
    return f"""
[[generation]]
name = "{name}"
knoten = "{knoten}"
gueltig_von = {von}
gueltig_bis = {bis}
sample_size = {sample_size}
max_endalter = 85
zins = 0.01
tafel = "DAV2008_T"
alpha = 0.025
beta1 = 0.025
gamma1 = 0.0008
gamma2 = 0.00125
gamma3 = 0.0025
policy_fee = 30.0
min_alter_flex = 60
min_rlz_flex = 5
{extra}
[generation.verteilungen.entry_age]
typ = "normal_trunc"
mean = 40.0
sd = 12.0
min = 18.0
max = 62.0
[generation.verteilungen.sex]
typ = "empirical_discrete"
values = ["M", "F"]
probs = [0.5, 0.5]
[generation.verteilungen.duration]
typ = "empirical_discrete"
values = [20, 25]
probs = [0.5, 0.5]
[generation.verteilungen.premium_duration]
typ = "empirical_discrete"
values = [20, 25]
probs = [0.5, 0.5]
[generation.verteilungen.sum_insured]
typ = "lognormal"
meanlog = 11.2
sdlog = 0.5
[generation.verteilungen.zahlweise]
typ = "empirical_discrete"
values = [12, 1]
probs = [0.9, 0.1]
"""


def _config(*generationen: str, tagesbetrieb: str = "") -> str:
    return "[meta]\nseed = 7\n" + "".join(generationen) + tagesbetrieb


# --------------------------------------------------------------------------- #
# Die PLV-Config: Generationen bis heute und der Tagesbetrieb
# --------------------------------------------------------------------------- #


def test_plv_config_traegt_die_generationen_bis_heute():
    cfg = load_config(PLV)
    assert cfg.validate() == []
    heute = dt.date(2026, 9, 5)
    im_vertrieb = {
        g.produkt: g.name for g in cfg.generationen
        if g.gueltig_von <= heute <= g.gueltig_bis
        and (g.sample_size > 0 or g.neuzugang_pro_jahr > 0)
    }
    assert im_vertrieb == {"klv": "KLV-2025", "bu": "BU-2025"}
    klv_2025 = next(g for g in cfg.generationen if g.name == "KLV-2025")
    assert klv_2025.knoten == "klv/plv_2025"
    assert klv_2025.neuzugang_pro_jahr > 0
    assert klv_2025.neuzugang_trend < 0          # das Unternehmen schrumpft
    bu_2025 = next(g for g in cfg.generationen if g.name == "BU-2025")
    assert bu_2025.knoten == "bu/plv_2025"
    assert bu_2025.neuzugang_pro_jahr > 0
    # Die Vorgaenger verkaufen nicht mehr in denselben Tagen:
    for name in ("KLV-2022", "BU-2017"):
        gen = next(g for g in cfg.generationen if g.name == name)
        assert gen.gueltig_bis == dt.date(2024, 12, 31)
        assert gen.neuzugang_pro_jahr == 0
    # Lueckenlos je Produkt: jede verkaufende Generation beginnt am Tag nach
    # der vorigen; die uebernommene TG2015 traegt das Fenster des abgebenden
    # Unternehmens und verkauft nicht.
    for produkt in ("klv", "bu"):
        gens = sorted(
            (g for g in cfg.generationen
             if g.produkt == produkt and (g.sample_size > 0 or g.neuzugang_pro_jahr > 0)),
            key=lambda g: g.gueltig_von,
        )
        for vorher, danach in zip(gens, gens[1:]):
            assert danach.gueltig_von == vorher.gueltig_bis + dt.timedelta(days=1)
    uebernommen = [g for g in cfg.generationen if g.sample_size == 0 and g.neuzugang_pro_jahr == 0]
    assert [g.name for g in uebernommen] == ["TG2015"] and uebernommen[0].zellen


def test_plv_config_traegt_den_tagesbetrieb():
    tb = load_config(PLV).tagesbetrieb
    assert tb.betriebsbeginn == dt.date(2026, 1, 1)
    assert tb.wochentagsgewichte == WOCHENTAGSGEWICHTE_VORGABE
    assert tb.meldeverzug_tod == Meldeverzug("lognormal", 14.0, 60.0)
    # Das Gewicht haengt nur vom Wochentag ab: Samstag/Sonntag 0, Montag
    # mehr als die uebrigen Werktage.
    montag = dt.date(2026, 9, 7)
    assert montag.weekday() == 0
    assert tb.gewicht(montag) == 1.3
    assert tb.gewicht(montag + dt.timedelta(days=5)) == 0.0   # Samstag
    assert tb.gewicht(montag + dt.timedelta(days=6)) == 0.0   # Sonntag
    assert all(tb.gewicht(montag + dt.timedelta(days=k)) == 1.0 for k in range(1, 5))


def test_ohne_abschnitt_gelten_die_vorgaben_des_konzepts():
    """Die Lehrbeispiel-Configs kennen keinen Tagesbetrieb; sie bleiben
    gueltig und tragen die Vorgaben — nur der Betriebsbeginn fehlt."""
    cfg = load_config(KLV)
    assert cfg.validate() == []
    assert cfg.tagesbetrieb == Tagesbetrieb()
    assert cfg.tagesbetrieb.betriebsbeginn is None
    assert all(g.neuzugang_trend == 0.0 for g in cfg.generationen)


# --------------------------------------------------------------------------- #
# Validierung: Trend, Gewichte, Meldeverzug
# --------------------------------------------------------------------------- #


def test_neuzugang_trend_wird_geprueft():
    cfg = load_config(PLV)
    gen = next(g for g in cfg.generationen if g.name == "KLV-2025")
    for schlecht in (-1.0, -1.5, 1.01):
        probe = copy.deepcopy(gen)
        probe.neuzugang_trend = schlecht
        assert any("neuzugang_trend" in f for f in probe.validate()), schlecht
    probe = copy.deepcopy(gen)
    probe.neuzugang_trend = math.nan
    assert any("neuzugang_trend ist nicht endlich" in f for f in probe.validate())
    for gut in (-0.99, 0.0, 0.5, 1.0):
        probe = copy.deepcopy(gen)
        probe.neuzugang_trend = gut
        assert not [f for f in probe.validate() if "neuzugang_trend" in f], gut


def test_neuzugang_trend_wird_geladen():
    cfg = config_aus_text(_config(_generation(
        "G1", "2020-01-01", "2030-12-31", extra="neuzugang_trend = -0.04\n")))
    assert cfg.generationen[0].neuzugang_trend == -0.04
    assert cfg.validate() == []


@pytest.mark.parametrize("gewichte, erwartet", [
    ("{ mo = 1.3, di = 1.0, mi = 1.0, do = 1.0, fr = -1.0, sa = 0.0, so = 0.0 }",
     "wochentagsgewicht fr < 0"),
    ("{ mo = 0.0, di = 0.0, mi = 0.0, do = 0.0, fr = 0.0, sa = 0.0, so = 0.0 }",
     "summieren auf 0"),
    ("{ mo = 1.0, di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 0.0 }",
     "genau die Schluessel"),
    ("{ mo = 1.0, di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 0.0, so = 0.0, feiertag = 0.0 }",
     "genau die Schluessel"),
    ("{ mo = nan, di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 0.0, so = 0.0 }",
     "nicht endlich"),
    ('{ mo = "viel", di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 0.0, so = 0.0 }',
     "keine Zahl"),
])
def test_wochentagsgewichte_werden_geprueft(gewichte, erwartet):
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2030-12-31"),
        tagesbetrieb=f"\n[tagesbetrieb]\nwochentagsgewichte = {gewichte}\n",
    ))
    fehler = cfg.validate()
    assert any(erwartet in f for f in fehler), fehler


def test_wochenendverkauf_ist_erlaubt_aber_nicht_vorgabe():
    """Die Gewichte sind Config, nicht Code: ein Samstagsverkauf ist
    zulaessig, wenn jemand ihn hinschreibt."""
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2030-12-31"),
        tagesbetrieb="\n[tagesbetrieb]\nwochentagsgewichte = "
        "{ mo = 1.0, di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 0.5, so = 0.0 }\n",
    ))
    assert cfg.validate() == []
    assert cfg.tagesbetrieb.gewicht(dt.date(2026, 9, 5)) == 0.5   # Samstag
    assert WOCHENTAGSGEWICHTE_VORGABE["sa"] == 0.0
    assert tuple(WOCHENTAGSGEWICHTE_VORGABE) == WOCHENTAGE


@pytest.mark.parametrize("verzug, erwartet", [
    ('{ verteilung = "normal", median_tage = 14, p95_tage = 60 }',
     "nicht unterstuetzt"),
    ('{ verteilung = "lognormal", median_tage = 60, p95_tage = 14 }',
     "muss ueber median_tage"),
    ('{ verteilung = "lognormal", median_tage = 14, p95_tage = 14 }',
     "muss ueber median_tage"),
    ('{ verteilung = "lognormal", median_tage = 0, p95_tage = 60 }',
     "median_tage <= 0"),
    ('{ verteilung = "lognormal", median_tage = inf, p95_tage = 60 }',
     "nicht endlich"),
])
def test_meldeverzug_wird_geprueft(verzug, erwartet):
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2030-12-31"),
        tagesbetrieb=f"\n[tagesbetrieb]\nmeldeverzug_tod = {verzug}\n",
    ))
    fehler = cfg.validate()
    assert any(erwartet in f for f in fehler), fehler


@pytest.mark.parametrize("abschnitt, erwartet", [
    ("[tagesbetrieb]\nfeiertage = []\n", "unbekannte Schluessel"),
    ("[tagesbetrieb]\nmeldeverzug_tod = { median = 14 }\n", "unbekannte Schluessel"),
    ("[tagesbetrieb]\nbetriebsbeginn = \"2026-01-01\"\n", "kein TOML-Datum"),
    ("[tagesbetrieb]\nwochentagsgewichte = 1.0\n", "muss eine Tabelle"),
])
def test_unbekannte_oder_falsche_schluessel_sind_ladefehler(abschnitt, erwartet):
    """Ein vertippter Schluessel liefe sonst still mit der Vorgabe durch."""
    with pytest.raises(ValueError, match=erwartet):
        config_aus_text(_config(
            _generation("G1", "2020-01-01", "2030-12-31"),
            tagesbetrieb="\n" + abschnitt,
        ))


# --------------------------------------------------------------------------- #
# Verkaufsfenster: ein Tag verkauft je Produkt genau eine Generation
# --------------------------------------------------------------------------- #


def test_ueberlappende_verkaufsfenster_sind_ein_fehler():
    """Mutationsprobe: ohne _validate_verkaufsfenster bleibt diese
    Config gueltig — und zwei Generationen verkauften am selben Tag."""
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2025-12-31"),
        _generation("G2", "2025-01-01", "2030-12-31"),
    ))
    fehler = cfg.validate()
    assert any("G1 und G2" in f and "Verkaufsfenster ueberlappen" in f
               for f in fehler), fehler
    # Ein einziger Tag Ueberlappung genuegt:
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2025-01-01"),
        _generation("G2", "2025-01-01", "2030-12-31"),
    ))
    assert any("Verkaufsfenster ueberlappen" in f for f in cfg.validate())
    # Nahtlos ist erlaubt:
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2024-12-31"),
        _generation("G2", "2025-01-01", "2030-12-31"),
    ))
    assert cfg.validate() == []


def test_nicht_verkaufende_generationen_duerfen_ueberlappen():
    """Eine uebernommene Generation (sample_size 0, kein Neuzugang)
    traegt das Fenster des abgebenden Unternehmens — es sagt nichts
    darueber, was die PLV an diesem Tag verkauft."""
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2030-12-31"),
        _generation("UEB", "2015-01-01", "2030-12-31", sample_size=0),
    ))
    assert cfg.validate() == []
    # ... aber mit Neuzugang verkauft sie, und dann zaehlt das Fenster:
    cfg = config_aus_text(_config(
        _generation("G1", "2020-01-01", "2030-12-31"),
        _generation("UEB", "2015-01-01", "2030-12-31", sample_size=0,
                    extra="neuzugang_pro_jahr = 5\n"),
    ))
    assert any("Verkaufsfenster ueberlappen" in f for f in cfg.validate())


def test_verschiedene_produkte_duerfen_ueberlappen():
    cfg = config_aus_text(_config(
        _generation("K", "2020-01-01", "2030-12-31"),
        _generation("B", "2020-01-01", "2030-12-31", produkt="bu"),
    ))
    assert cfg.validate() == []


def test_tagesbetrieb_dataclass_prueft_sich_selbst():
    tb = Tagesbetrieb(betriebsbeginn="2026-01-01")   # type: ignore[arg-type]
    assert any("kein Datum" in f for f in tb.validate())
    assert Tagesbetrieb().validate() == []
    gen = TarifGeneration(
        name="G", knoten="klv/plv_g", gueltig_von=dt.date(2020, 1, 1),
        gueltig_bis=dt.date(2021, 1, 1), sample_size=0, max_endalter=85,
        neuzugang_trend=-2.0,
    )
    assert any("neuzugang_trend" in f for f in gen.validate())
