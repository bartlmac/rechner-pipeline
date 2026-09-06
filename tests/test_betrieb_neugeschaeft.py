"""Tagesneugeschaeft: Jahressumme, Wochenende null, Montag hoeher, Tagesseed.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B2. Der Versicherer
verkauft jeden Werktag; wie viel, entscheidet das Jahresziel mit Trend,
verteilt ueber Wochentagsgewichte, mit einem Bernoulli-Zug auf den Rest.
Jeder Tag ist fuer sich reproduzierbar, unabhaengig von der Reihenfolge
der Laeufe. Die Mutationsproben sind in den Docstrings benannt.

Gebunden an den Systemstrang des Tagesbetriebs (wie
``test_bestand_uebernommen_fortschreiben`` an ``system/bestand``): Gegenstand
ist die Mechanik des Verkaufskalenders, nicht die Tarifmathematik eines
Produkts; die Import-Kante zu ``betrieb.neugeschaeft`` selektiert die
Datei bei jeder Aenderung dort.

Knoten: system/betrieb
"""

from __future__ import annotations

import copy
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import config_aus_text, load_config
from rechner_pipeline.bestand.ereignisse import EreignisError, fortschreiben
from rechner_pipeline.bestand.generator import generate, neuzugaenge
from rechner_pipeline.betrieb.neugeschaeft import (
    NeugeschaeftError,
    generationsseed,
    jahresziel,
    naechster_monatserster,
    neugeschaeft_am,
    neugeschaeft_zwischen,
    tagesziel,
    verkaufstag,
)
from rechner_pipeline.models.bestand import STAMM_SPALTEN, validate_portfolio

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"
KLV = REPO_ROOT / "configs" / "bestand_klv.toml"

JAHR = 2027


def _tage(jahr: int):
    tag = dt.date(jahr, 1, 1)
    while tag.year == jahr:
        yield tag
        tag += dt.timedelta(days=1)


@pytest.fixture(scope="module")
def config():
    return load_config(PLV)


@pytest.fixture(scope="module")
def verkaufend(config):
    return [(i, g) for i, g in enumerate(config.generationen) if g.neuzugang_pro_jahr > 0]


@pytest.fixture(scope="module")
def jahr_2027(config):
    return neugeschaeft_zwischen(config, dt.date(JAHR, 1, 1), dt.date(JAHR, 12, 31))


def _verkaufstage(config, frame: pd.DataFrame) -> pd.Series:
    index = {g.name: (i, g) for i, g in enumerate(config.generationen)}
    return pd.Series(
        [verkaufstag(index[n][1], index[n][0], int(p))
         for n, p in zip(frame["tarif_generation"], frame["police_id"])],
        index=frame.index,
    )


# --------------------------------------------------------------------------- #
# Jahresziel und Tagesziel
# --------------------------------------------------------------------------- #


def test_tagesziele_summieren_auf_das_jahresziel(config, verkaufend):
    """Mutationsprobe: Gewichtssumme nur ueber die Werktage statt ueber
    alle Tage — dann summierten die Tagesziele nicht mehr auf das Ziel."""
    assert verkaufend, "die PLV verkauft"
    for _, gen in verkaufend:
        summe = sum(tagesziel(config, gen, tag) for tag in _tage(JAHR))
        ziel = jahresziel(gen, JAHR)
        assert ziel == pytest.approx(
            gen.neuzugang_pro_jahr * (1 + gen.neuzugang_trend) ** (JAHR - gen.gueltig_von.year)
        )
        assert summe == pytest.approx(ziel)
    # Ausserhalb des Fensters gibt es kein Ziel:
    gen = verkaufend[0][1]
    assert jahresziel(gen, gen.gueltig_von.year - 1) == 0.0
    assert tagesziel(config, gen, gen.gueltig_bis + dt.timedelta(days=1)) == 0.0


def test_jahressumme_trifft_das_ziel_bis_auf_den_bernoulli_rest(config, verkaufend, jahr_2027):
    """Die Zahl eines Tages weicht hoechstens um einen Vertrag vom
    Erwartungswert ab; ueber ein Jahr bleibt die Summe nahe am Ziel.

    Mutationsprobe: Poisson statt Bernoulli-Rest oder ein weggelassener
    Rest — dann faellt die Jahressumme aus dem Band (bei rund 261
    Verkaufstagen ist die Standardabweichung der Bernoulli-Reste unter 9)."""
    je_generation = jahr_2027["tarif_generation"].value_counts()
    for _, gen in verkaufend:
        ziel = jahresziel(gen, JAHR)
        ist = int(je_generation.get(gen.name, 0))
        assert abs(ist - ziel) <= 25, (gen.name, ist, ziel)
    # Und der Tagesbetrieb bleibt beim Ziel: kein Tag weicht um mehr als
    # einen Vertrag vom Erwartungswert ab.
    tage = _verkaufstage(config, jahr_2027)
    for (_, gen) in verkaufend:
        zeilen = jahr_2027[jahr_2027["tarif_generation"] == gen.name]
        je_tag = tage.loc[zeilen.index].value_counts()
        for tag, anzahl in je_tag.items():
            erwartung = tagesziel(config, gen, tag)
            assert abs(anzahl - erwartung) < 1.0, (gen.name, tag, anzahl, erwartung)


def test_wochenende_ohne_verkauf(config, jahr_2027):
    """Mutationsprobe: Gewicht am Samstag auf 1 — dann verkauft die PLV
    samstags, und diese Pruefung faellt."""
    tage = _verkaufstage(config, jahr_2027)
    assert not (tage.map(lambda t: t.weekday()) >= 5).any()
    for tag in _tage(JAHR):
        if tag.weekday() >= 5:
            assert len(neugeschaeft_am(config, tag)) == 0, tag


def test_montag_verkauft_mehr(config, verkaufend):
    """Erwartungswert: Montag 1,3-fach; realisiert ueber fuenf Jahre
    ebenfalls mehr als an jedem anderen Werktag."""
    gen = verkaufend[0][1]
    montag = dt.date(JAHR, 3, 1)
    assert montag.weekday() == 0
    for k in range(1, 5):
        assert tagesziel(config, gen, montag) == pytest.approx(
            1.3 * tagesziel(config, gen, montag + dt.timedelta(days=k))
        )
    fuenf_jahre = neugeschaeft_zwischen(config, dt.date(2026, 1, 1), dt.date(2030, 12, 31))
    je_wochentag = _verkaufstage(config, fuenf_jahre).map(lambda t: t.weekday()).value_counts()
    assert je_wochentag[0] > max(je_wochentag.get(k, 0) for k in range(1, 5))


def test_trend_laesst_das_unternehmen_schrumpfen(config):
    gen = next(g for g in config.generationen if g.name == "KLV-2025")
    assert gen.neuzugang_trend < 0
    assert jahresziel(gen, 2026) > jahresziel(gen, 2030) > jahresziel(gen, 2035)
    frueh = neugeschaeft_zwischen(config, dt.date(2026, 1, 1), dt.date(2026, 12, 31))
    spaet = neugeschaeft_zwischen(config, dt.date(2035, 1, 1), dt.date(2035, 12, 31))
    n_frueh = int((frueh["tarif_generation"] == gen.name).sum())
    n_spaet = int((spaet["tarif_generation"] == gen.name).sum())
    assert n_frueh > n_spaet
    assert abs(n_spaet - jahresziel(gen, 2035)) <= 25


# --------------------------------------------------------------------------- #
# Determinismus je Tag
# --------------------------------------------------------------------------- #


def test_tag_ist_reproduzierbar_und_reihenfolgeunabhaengig(config, jahr_2027):
    """Mutationsprobe: Seed aus dem Aufruftag statt dem Kalendertag, oder
    ein Generator ueber alle Tage hinweg — dann haengt ein Tag davon ab,
    was vorher erzeugt wurde."""
    # Der erste Verkaufstag im Maerz mit Abschluss — deterministisch
    # gewaehlt, nicht geraten (ein Werktag mit Erwartung 0,5 hat oft null).
    tage = _verkaufstage(config, jahr_2027)
    tag = min(t for t in tage if t >= dt.date(JAHR, 3, 1))
    allein = neugeschaeft_am(config, tag)
    assert len(allein) > 0
    pd.testing.assert_frame_equal(allein, neugeschaeft_am(config, tag))
    pd.testing.assert_frame_equal(allein, neugeschaeft_zwischen(config, tag, tag))
    im_jahr = jahr_2027[tage == tag].reset_index(drop=True)
    pd.testing.assert_frame_equal(allein, im_jahr)
    # Praefix-/Suffix-Stabilitaet: ein Teilbereich ist die exakte Teilmenge.
    teil = neugeschaeft_zwischen(config, dt.date(JAHR, 3, 1), dt.date(JAHR, 3, 31))
    erwartet = jahr_2027[(tage >= dt.date(JAHR, 3, 1)) & (tage <= dt.date(JAHR, 3, 31))]
    pd.testing.assert_frame_equal(teil, erwartet.reset_index(drop=True))
    # Zwei Laeufe mit verschiedenen Startdaten treffen denselben Tag gleich:
    lauf_a = neugeschaeft_zwischen(config, tag - dt.timedelta(days=40), tag)
    lauf_b = neugeschaeft_zwischen(config, tag - dt.timedelta(days=3), tag)
    tag_a = lauf_a[_verkaufstage(config, lauf_a) == tag].reset_index(drop=True)
    tag_b = lauf_b[_verkaufstage(config, lauf_b) == tag].reset_index(drop=True)
    pd.testing.assert_frame_equal(tag_a, allein)
    pd.testing.assert_frame_equal(tag_b, allein)


def test_seed_haengt_am_namen_nicht_an_der_position(config):
    """Mutationsprobe: gen_index statt Name im Seed — dann veraendert
    eine vorn eingefuegte Generation die Verkaufstage aller anderen."""
    assert generationsseed("KLV-2025") != generationsseed("BU-2025")
    assert generationsseed("KLV-2025") == generationsseed("KLV-2025")
    umgestellt = copy.deepcopy(config)
    umgestellt.generationen = list(reversed(umgestellt.generationen))
    monat = neugeschaeft_zwischen(config, dt.date(JAHR, 5, 1), dt.date(JAHR, 5, 31))
    monat_um = neugeschaeft_zwischen(umgestellt, dt.date(JAHR, 5, 1), dt.date(JAHR, 5, 31))
    # Dieselben Vertraege (Merkmale und Verkaufstage), nur die Nummern
    # folgen dem Nummernkreis der neuen Position.
    a = monat.drop(columns="police_id").sort_values(
        ["tarif_generation", "insurance_start", "sum_insured", "bu_rente", "entry_age"]
    ).reset_index(drop=True)
    b = monat_um.drop(columns="police_id").sort_values(
        ["tarif_generation", "insurance_start", "sum_insured", "bu_rente", "entry_age"]
    ).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_anderer_seed_anderer_tag(config):
    anders = copy.deepcopy(config)
    anders.seed += 1
    a = neugeschaeft_zwischen(config, dt.date(JAHR, 3, 1), dt.date(JAHR, 3, 31))
    b = neugeschaeft_zwischen(anders, dt.date(JAHR, 3, 1), dt.date(JAHR, 3, 31))
    assert not a.drop(columns="police_id").equals(b.drop(columns="police_id"))


# --------------------------------------------------------------------------- #
# Vertragsform: Beginn, Nummern, Contract
# --------------------------------------------------------------------------- #


def test_beginn_ist_der_naechste_monatserste(config, jahr_2027):
    assert naechster_monatserster(dt.date(2027, 12, 31)) == dt.date(2028, 1, 1)
    assert naechster_monatserster(dt.date(2027, 2, 1)) == dt.date(2027, 3, 1)
    tage = _verkaufstage(config, jahr_2027)
    for beginn, zugang, tag in zip(
        jahr_2027["insurance_start"], jahr_2027["bestandszugang"], tage
    ):
        assert beginn.date() == naechster_monatserster(tag)
        assert zugang == beginn          # Stamm: Monatserster-Konvention


def test_vertraege_sind_gueltig_und_kollisionsfrei(config, jahr_2027):
    assert validate_portfolio(jahr_2027) == []
    assert not jahr_2027["police_id"].duplicated().any()
    batch = generate(config)
    assert not set(jahr_2027["police_id"]) & set(batch["police_id"])
    jaehrlich = neuzugaenge(config, dt.date(2026, 1, 1), dt.date(2036, 1, 1))
    assert not set(jahr_2027["police_id"]) & set(jaehrlich["police_id"])
    assert set(jahr_2027["produkt"]) == {"klv", "bu"}
    assert set(jahr_2027["tarif_generation"]) == {"KLV-2025", "BU-2025"}


def test_verkaufstag_ist_aus_der_nummer_rueckrechenbar(config, jahr_2027):
    tage = _verkaufstage(config, jahr_2027)
    assert tage.map(lambda t: t.year).eq(JAHR).all()
    probe = jahr_2027.iloc[::37]
    for pid, tag in zip(probe["police_id"], tage.loc[probe.index]):
        assert int(pid) in set(neugeschaeft_am(config, tag)["police_id"])
    gen0 = config.generationen[0]
    with pytest.raises(NeugeschaeftError, match="Nummernkreis"):
        verkaufstag(gen0, 0, 10_000_001)          # eine Batch-Nummer


def _zwei_generationen(neuzugang: int, gewichte: str = "") -> str:
    def block(name, von, bis):
        return f"""
[[generation]]
name = "{name}"
knoten = "klv/plv_{name.lower()}"
gueltig_von = {von}
gueltig_bis = {bis}
sample_size = 0
neuzugang_pro_jahr = {neuzugang}
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
    return (
        "[meta]\nseed = 11\n"
        + block("G1", "2020-01-01", "2024-12-31")
        + block("G2", "2025-01-01", "2030-12-31")
        + "\n[tagesbetrieb]\n" + gewichte
    )


def test_generationenwechsel_am_fenster():
    """Ein Tag verkauft die Generation, deren Fenster ihn enthaelt.
    3650 je Jahr bei Gewicht 1 an jedem Tag = genau zehn je Tag (2024 als
    Schaltjahr neun oder zehn)."""
    cfg = config_aus_text(_zwei_generationen(
        3650, "wochentagsgewichte = { mo = 1.0, di = 1.0, mi = 1.0, do = 1.0, fr = 1.0, sa = 1.0, so = 1.0 }\n"))
    assert cfg.validate() == []
    letzter_g1 = neugeschaeft_am(cfg, dt.date(2024, 12, 31))
    erster_g2 = neugeschaeft_am(cfg, dt.date(2025, 1, 1))
    assert set(letzter_g1["tarif_generation"]) == {"G1"} and 9 <= len(letzter_g1) <= 10
    assert set(erster_g2["tarif_generation"]) == {"G2"} and len(erster_g2) == 10
    assert len(neugeschaeft_am(cfg, dt.date(2019, 12, 31))) == 0
    assert len(neugeschaeft_am(cfg, dt.date(2031, 1, 1))) == 0
    # Beginn des Silvester-Verkaufs ist der Neujahrstag:
    assert (letzter_g1["insurance_start"] == pd.Timestamp("2025-01-01")).all()


def test_zu_viele_vertraege_am_tag_sind_ein_fehler():
    cfg = config_aus_text(_zwei_generationen(
        10_000, "wochentagsgewichte = { mo = 1.0, di = 0.0, mi = 0.0, do = 0.0, fr = 0.0, sa = 0.0, so = 0.0 }\n"))
    with pytest.raises(NeugeschaeftError, match="je Tag"):
        neugeschaeft_am(cfg, dt.date(2027, 3, 15))


def test_ungueltige_config_ist_ein_fehler(config):
    kaputt = copy.deepcopy(config)
    kaputt.tagesbetrieb.wochentagsgewichte["mo"] = -1.0
    with pytest.raises(NeugeschaeftError, match="Config ungueltig"):
        neugeschaeft_am(kaputt, dt.date(JAHR, 3, 15))
    with pytest.raises(NeugeschaeftError, match="vertauschte"):
        neugeschaeft_zwischen(config, dt.date(JAHR, 3, 15), dt.date(JAHR, 3, 14))


# --------------------------------------------------------------------------- #
# Der jaehrliche Erzeuger folgt demselben Jahresziel
# --------------------------------------------------------------------------- #


def test_jaehrlicher_neuzugang_folgt_dem_jahresziel(config):
    """Mutationsprobe: Trend im jaehrlichen Erzeuger ignoriert — dann
    zieht er 120 je Jahr statt des schrumpfenden Ziels."""
    z = neuzugaenge(config, dt.date(2026, 1, 1), dt.date(2036, 1, 1))
    gen = next(g for g in config.generationen if g.name == "KLV-2025")
    je_jahr = z[z["tarif_generation"] == gen.name]["insurance_start"].dt.year.value_counts()
    for jahr in range(2027, 2036):
        assert int(je_jahr.get(jahr, 0)) == round(jahresziel(gen, jahr)), jahr
    assert int(je_jahr[2035]) < int(je_jahr[2027])


def test_jaehrlicher_neuzugang_ohne_trend_ist_unveraendert():
    """Nummern und Volumen des Erzeugers ohne Trend bleiben byte-identisch
    zum bisherigen Verhalten (jahrgangsstabile Offsets)."""
    cfg = copy.deepcopy(load_config(KLV))
    idx, gen = next((i, g) for i, g in enumerate(cfg.generationen) if g.name == "KLV-2008")
    gen.neuzugang_pro_jahr = 20
    z = neuzugaenge(cfg, dt.date(2008, 1, 1), dt.date(2012, 1, 1))
    zweitjahr = z[z["insurance_start"].dt.year == 2009]
    # Offset des zweiten Jahrgangs = 1 * 20, Nummern 21..40 im Block:
    assert set(zweitjahr["police_id"]) <= set(
        (idx + 1) * 10_000_000 + 2_000_000 + k for k in range(21, 41)
    )
    assert len(zweitjahr) == 20


# --------------------------------------------------------------------------- #
# Mitgebrachte Zugaenge in der Ereignis-Engine
# --------------------------------------------------------------------------- #


def _mini_stamm(config) -> pd.DataFrame:
    start = dt.date(2020, 3, 1)
    row = {
        "police_id": 10000001, "tarif_generation": "KLV-2017", "produkt": "klv",
        "status_id": 1, "status_code": "POL", "status_date": start, "sex": "M",
        "date_of_birth": dt.date(1980, 3, 1), "entry_age": 40, "duration": 25,
        "premium_duration": 20, "sum_insured": 100000.0, "bu_rente": 0.0,
        "zahlweise": 12, "insurance_start": start,
        "insurance_end": dt.date(2045, 3, 1), "payment_end": dt.date(2040, 3, 1),
        "bestandszugang": start,
    }
    df = pd.DataFrame([row])
    for name, dtype in STAMM_SPALTEN:
        df[name] = pd.to_datetime(df[name]) if dtype == "datetime64[ns]" else df[name].astype(dtype)
    return df[[n for n, _ in STAMM_SPALTEN]]


def test_fortschreiben_bucht_mitgebrachte_zugaenge(config):
    """Mutationsprobe: ZUG nur fuer den jaehrlichen Erzeuger — dann
    fehlten den mitgebrachten Zugaengen ihre Buchungen."""
    stamm = _mini_stamm(config)
    woche = neugeschaeft_zwischen(config, dt.date(2026, 1, 5), dt.date(2026, 1, 16))
    assert len(woche) > 0
    ergebnis = fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=woche)
    pd.testing.assert_frame_equal(ergebnis.zugaenge, woche)
    zug = ergebnis.ledger[ergebnis.ledger["ereignis"] == "ZUG"].set_index("police_id")
    assert set(zug.index) == set(woche["police_id"])
    for zeile in woche.itertuples(index=False):
        buchung = zug.loc[zeile.police_id]
        assert buchung["status_date"] == zeile.insurance_start     # Wirkungstag = Beginn
        assert buchung["vertragsjahr"] == 0
        if zeile.produkt == "bu":
            assert buchung["betrag_art"] == "BU_Jahresrente"
            assert buchung["betrag"] == zeile.bu_rente
        else:
            assert buchung["betrag_art"] == "VS"
            assert buchung["betrag"] == zeile.sum_insured
    # Ein Beginn hinter dem Horizont ist erlaubt (verkauft, Beginn folgt):
    spaet = neugeschaeft_zwischen(config, dt.date(2026, 2, 23), dt.date(2026, 2, 27))
    ergebnis = fortschreiben(stamm, config, dt.date(2026, 2, 28), zugaenge=spaet)
    assert (ergebnis.ledger[ergebnis.ledger["ereignis"] == "ZUG"]["status_date"]
            == pd.Timestamp("2026-03-01")).all()


def test_mitgebrachte_zugaenge_werden_geprueft(config):
    stamm = _mini_stamm(config)
    woche = neugeschaeft_zwischen(config, dt.date(2026, 1, 5), dt.date(2026, 1, 9))
    with pytest.raises(EreignisError, match="schliessen sich aus"):
        fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=woche,
                      neuzugang_ab=dt.date(2026, 1, 1))
    kollision = woche.copy()
    kollision.loc[kollision.index[0], "police_id"] = 10000001
    with pytest.raises(EreignisError, match="kollidieren"):
        fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=kollision)
    zustand = woche.copy()
    zustand.loc[zustand.index[0], "status_id"] = 2
    zustand.loc[zustand.index[0], "status_code"] = "PEX"
    with pytest.raises(EreignisError, match="POL-Ursprungszeilen"):
        fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=zustand)
    with pytest.raises(EreignisError, match="Stamm-Spalten fehlen"):
        fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=woche.drop(columns="sex"))
    # Leere Zugaenge sind ein gueltiger, leerer Fall:
    leer = fortschreiben(stamm, config, dt.date(2026, 3, 1), zugaenge=woche.iloc[0:0])
    assert len(leer.zugaenge) == 0 and "ZUG" not in set(leer.ledger["ereignis"])
