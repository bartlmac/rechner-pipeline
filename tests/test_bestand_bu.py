"""BU im Bestand: Erzeugung, Zustandsprozess, Kopplung an den Kern.

Der Kern der Sache (Beschluss 2026-08-13): die Ereignis-Engine simuliert
für BU GENAU den Prozess, den der Kern bewertet — die Übergänge kommen aus
den vier Ausscheideordnungen des Produkts, nicht aus Config-Raten. Der
Monte-Carlo-Abgleich gegen ``Zustandsmodell.verteilung`` ist deshalb ein
echter Kopplungstest und keine Statistik-Kosmetik.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.ereignisse import (
    EreignisError,
    bestand_mit_historie,
    fortschreiben,
)
from rechner_pipeline.bestand.generator import generate
from rechner_pipeline.bestand.zeitscheibe import zeitscheibe
from rechner_pipeline.kern.produkte.bu import AKTIV, BU, BU_ZUSTAND, TOT, BUModelPoint
from rechner_pipeline.models.bestand import (
    STAMM_SPALTEN,
    bu_model_point_kwargs,
    validate_portfolio,
    validate_statushistorie,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
BU_EXAMPLE = REPO_ROOT / "examples" / "bestand_bu.toml"
KLV_EXAMPLE = REPO_ROOT / "examples" / "bestand_klv.toml"


@pytest.fixture(scope="module")
def config():
    return load_config(BU_EXAMPLE)


@pytest.fixture(scope="module")
def portfolio(config):
    return generate(config)


def _bu_stamm(*vertraege: dict) -> pd.DataFrame:
    """Mini-BU-Bestand (Monatserster-Konvention wie im ganzen Modul)."""
    rows = []
    for v in vertraege:
        start = v["start"]
        rows.append(
            {
                "police_id": v["police_id"],
                "tarif_generation": v.get("tarif_generation", "BU-2000"),
                "produkt": "bu",
                "status_id": 1,
                "status_code": "POL",
                "status_date": start,
                "sex": v.get("sex", "M"),
                "date_of_birth": dt.date(start.year - v["x"], start.month, 1),
                "entry_age": v["x"],
                "duration": v["n"],
                "premium_duration": v["n"],
                "sum_insured": 0.0,
                "bu_rente": v.get("rente", 12000.0),
                "zahlweise": 1,
                "insurance_start": start,
                "insurance_end": dt.date(start.year + v["n"], start.month, 1),
                "payment_end": dt.date(start.year + v["n"], start.month, 1),
            }
        )
    df = pd.DataFrame(rows)
    for name, dtype in STAMM_SPALTEN:
        if dtype == "datetime64[ns]":
            df[name] = pd.to_datetime(df[name])
        else:
            df[name] = df[name].astype(dtype)
    return df[[n for n, _ in STAMM_SPALTEN]]


# --------------------------------------------------------------------------- #
# Erzeugung
# --------------------------------------------------------------------------- #


def test_bu_bestand_erfuellt_den_contract(portfolio, config):
    assert len(portfolio) == config.generationen[0].sample_size
    assert validate_portfolio(portfolio) == []
    assert set(portfolio["produkt"]) == {"bu"}
    # Produktfuehrende Leistungsspalte ist die Jahresrente:
    assert (portfolio["bu_rente"] > 0).all()
    assert (portfolio["sum_insured"] == 0.0).all()
    # Fachlichkeit des Beispielprodukts:
    assert (portfolio["premium_duration"] == portfolio["duration"]).all()
    assert (portfolio["zahlweise"] == 1).all()
    # Endalter respektiert die Konfiguration:
    assert (portfolio["entry_age"] + portfolio["duration"] <= 67).all()


def test_bu_erzeugung_ist_deterministisch(config):
    pd.testing.assert_frame_equal(generate(config), generate(config))


def test_klv_bestand_bleibt_produkt_klv():
    """Der Diskriminator ist rueckwaertskompatibel: ohne produkt-Angabe
    in der TOML bleibt eine Generation KLV."""
    klv = load_config(KLV_EXAMPLE)
    assert [g.produkt for g in klv.generationen] == ["klv", "klv"]
    df = generate(klv)
    assert set(df["produkt"]) == {"klv"}
    assert (df["bu_rente"] == 0.0).all()


# --------------------------------------------------------------------------- #
# Zustandsprozess der Fortschreibung
# --------------------------------------------------------------------------- #


def test_bu_fortschreibung_liefert_gueltige_historie(portfolio, config):
    erg = fortschreiben(portfolio, config, dt.date(2050, 1, 1))
    assert validate_statushistorie(portfolio, erg.historie) == []
    codes = set(erg.ledger["ereignis"])
    assert {"INV", "TOD", "ABL"} <= codes
    # BU kennt weder Storno noch Beitragsfreistellung noch Erhoehung:
    assert not codes & {"STO", "PEX", "ERH"}
    assert len(erg.scheiben) == 0
    # Jeder GeVo traegt die Bezugsgroesse des Produkts:
    assert set(erg.ledger["betrag_art"]) == {"BU_Jahresrente"}


def test_bu_fortschreibung_ist_deterministisch_und_praefixstabil(portfolio, config):
    frueh = dt.date(2020, 1, 1)
    a = fortschreiben(portfolio, config, frueh)
    b = fortschreiben(portfolio, config, frueh)
    pd.testing.assert_frame_equal(a.historie, b.historie)
    spaet = fortschreiben(portfolio, config, dt.date(2050, 1, 1))
    praefix = spaet.historie[
        spaet.historie["status_date"] <= pd.Timestamp(frueh)
    ].reset_index(drop=True)
    pd.testing.assert_frame_equal(praefix, a.historie)


def test_invalidisierung_und_reaktivierung_als_gevos(config, monkeypatch):
    """Forcierter Pfad: Invalidisierung im Jahr 1, Reaktivierung im Jahr 2.

    Die Uebergaenge werden am Produkt gepatcht (die synthetischen Tafeln
    liefern nur kleine Wahrscheinlichkeiten) — geprueft wird die
    Buchungslogik der Engine, nicht die Tafel.
    """
    def uebergang(self, von, nach, alter, dauer):
        if von == AKTIV and nach == BU_ZUSTAND:
            return 1.0 if alter == 40 else 0.0
        if von == BU_ZUSTAND and nach == AKTIV:
            return 1.0
        return 0.0

    monkeypatch.setattr(BU, "_uebergang", uebergang)
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20}
    )
    erg = fortschreiben(stamm, config, dt.date(2040, 1, 1))

    assert list(erg.ledger["ereignis"]) == ["INV", "REA", "ABL"]
    assert list(erg.historie["status_code"]) == ["BU", "POL", "ABL"]
    assert list(erg.historie["status_id"]) == [2, 3, 4]
    # Buchung am Jahrestag j+1 (wie im KLV-Pfad):
    assert erg.historie["status_date"].iloc[0] == pd.Timestamp(dt.date(2011, 5, 1))
    assert erg.historie["status_date"].iloc[1] == pd.Timestamp(dt.date(2012, 5, 1))
    # Betraege: die betroffene Jahresrente; der Ablauf aus dem Anwaerterstand
    # zahlt nichts (das Produkt kennt keine Erlebensfallleistung).
    assert list(erg.ledger["betrag"]) == [12000.0, 12000.0, 0.0]
    assert validate_statushistorie(stamm, erg.historie) == []


def test_tod_im_leistungsbezug_beendet_die_rente(config, monkeypatch):
    def uebergang(self, von, nach, alter, dauer):
        if von == AKTIV and nach == BU_ZUSTAND:
            return 1.0 if alter == 40 else 0.0
        if von == BU_ZUSTAND and nach == TOT:
            return 1.0
        return 0.0

    monkeypatch.setattr(BU, "_uebergang", uebergang)
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20}
    )
    erg = fortschreiben(stamm, config, dt.date(2040, 1, 1))
    assert list(erg.ledger["ereignis"]) == ["INV", "TOD"]
    # Tod aus dem Leistungsbezug beendet die laufende Rente (Bezugsgroesse),
    # Tod aus dem Anwaerterstand betrifft keine Rente:
    assert list(erg.ledger["betrag"]) == [12000.0, 12000.0]
    assert list(erg.historie["status_code"]) == ["BU", "TOD"]


def test_tod_als_anwaerter_zahlt_nichts(config, monkeypatch):
    def uebergang(self, von, nach, alter, dauer):
        return 1.0 if (von == AKTIV and nach == TOT) else 0.0

    monkeypatch.setattr(BU, "_uebergang", uebergang)
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20}
    )
    erg = fortschreiben(stamm, config, dt.date(2040, 1, 1))
    assert list(erg.ledger["ereignis"]) == ["TOD"]
    assert list(erg.ledger["betrag"]) == [0.0]


def test_ablauf_im_leistungsbezug_beendet_die_rente(config, monkeypatch):
    def uebergang(self, von, nach, alter, dauer):
        return 1.0 if (von == AKTIV and nach == BU_ZUSTAND and alter == 40) else 0.0

    monkeypatch.setattr(BU, "_uebergang", uebergang)
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20}
    )
    erg = fortschreiben(stamm, config, dt.date(2040, 1, 1))
    assert list(erg.ledger["ereignis"]) == ["INV", "ABL"]
    # Rente laeuft bis zum Ablauf und endet mit ihm:
    assert list(erg.ledger["betrag"]) == [12000.0, 12000.0]
    assert list(erg.historie["status_code"]) == ["BU", "ABL"]
    zeile = erg.historie.iloc[-1]
    assert zeile["status_date"] == pd.Timestamp(dt.date(2030, 5, 1))


def test_zeitscheibe_kennt_den_leistungsbezug(config, monkeypatch):
    def uebergang(self, von, nach, alter, dauer):
        return 1.0 if (von == AKTIV and nach == BU_ZUSTAND and alter == 40) else 0.0

    monkeypatch.setattr(BU, "_uebergang", uebergang)
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20}
    )
    erg = fortschreiben(stamm, config, dt.date(2040, 1, 1))
    sicht = bestand_mit_historie(stamm, erg.historie)
    # Vor der Invalidisierung Anwaerter, danach im Leistungsbezug — beides
    # in-force (AKTIVE_STATUS), der Ablauf beendet den Bestand.
    assert list(zeitscheibe(sicht, dt.date(2011, 1, 1))["status_code"]) == ["POL"]
    assert list(zeitscheibe(sicht, dt.date(2015, 1, 1))["status_code"]) == ["BU"]
    assert len(zeitscheibe(sicht, dt.date(2031, 1, 1))) == 0


# --------------------------------------------------------------------------- #
# Kopplung Simulation <-> Bewertung (der eigentliche Beleg)
# --------------------------------------------------------------------------- #


def test_realisation_trifft_die_modellverteilung(config):
    """Monte-Carlo-Abgleich: die simulierte Zustandsverteilung nach 20
    Jahren stimmt mit ``Zustandsmodell.verteilung`` ueberein.

    Das ist der Beleg, dass Ereignis-Engine und Kern denselben Prozess
    fahren — nicht nur zufaellig aehnliche. Toleranz grosszuegig (endliche
    Stichprobe), aber die Groessenordnung ist eindeutig.
    """
    jahre = 20
    x, n = 35, jahre
    stamm = _bu_stamm(*[
        {"police_id": 10000001 + i, "start": dt.date(2000, 1, 1), "x": x, "n": n}
        for i in range(4000)
    ])
    erg = fortschreiben(stamm, config, dt.date(2000 + jahre + 1, 1, 1))

    # Realisation: Endzustand je Police (kein terminaler Status = Ablauf
    # als Anwaerter oder im Leistungsbezug).
    letzter = (
        erg.historie.sort_values(["police_id", "status_id"], kind="stable")
        .groupby("police_id")
        .tail(1)
        .set_index("police_id")["status_code"]
    )
    tot = int((letzter == "TOD").sum())
    # Wer beim Ablauf im Leistungsbezug war, hat als vorletzten Status BU:
    vor_ablauf = (
        erg.historie[erg.historie["status_code"] != "ABL"]
        .sort_values(["police_id", "status_id"], kind="stable")
        .groupby("police_id")
        .tail(1)
        .set_index("police_id")["status_code"]
    )
    abgelaufen = set(letzter[letzter == "ABL"].index)
    im_bezug = sum(
        1 for p in abgelaufen if vor_ablauf.get(p) == "BU"
    )
    aktiv = len(stamm) - tot - im_bezug

    produkt = BU(BUModelPoint(**bu_model_point_kwargs(
        stamm.iloc[0], config.generationen[0].bu_generation_fields()
    )))
    verteilung = produkt.modell.verteilung(AKTIV, x, jahre)
    erwartet = {AKTIV: 0.0, BU_ZUSTAND: 0.0, TOT: 0.0}
    for (zustand, _dauer), masse in verteilung.items():
        erwartet[zustand] += masse

    for zustand, ist in ((AKTIV, aktiv), (BU_ZUSTAND, im_bezug), (TOT, tot)):
        soll = erwartet[zustand] * len(stamm)
        assert abs(ist - soll) <= max(12.0, 4.0 * soll ** 0.5), (
            f"{zustand}: simuliert {ist}, Modell {soll:.1f}"
        )


def test_bu_reserve_aus_dem_kern_ist_anschlussfaehig(config):
    """Die Ereignis-Engine liefert Vertragsjahr und BU-Dauer, der Kern die
    Reserve — beide Groessen muessen zusammenpassen (Grenze dauer <= a-1)."""
    produkt = BU(BUModelPoint(
        x=40, sex="M", n=20, bu_rente=12000.0,
        **{k: v for k, v in config.generationen[0].bu_generation_fields().items()
           if k != "zins"},
        zins=config.generationen[0].zins,
    ))
    # Anwaerter-Reserve startet per Aequivalenzprinzip bei 0:
    assert produkt.reserve_aktiv(0) == pytest.approx(0.0, abs=1e-9)
    # Reserve im Leistungsbezug ist deutlich positiv und faellt zum Ablauf:
    assert produkt.reserve_bu(5, 0) > produkt.reserve_aktiv(5)
    assert produkt.reserve_bu(19, 0) > 0.0
    with pytest.raises(ValueError, match="fachlich unmoeglich"):
        produkt.reserve_bu(3, 5)


def test_gemischter_bestand_simuliert_beide_produkte():
    """Ein Bestand darf KLV- und BU-Vertraege zugleich fuehren; jede
    Generation wird mit ihrer eigenen Fachlichkeit simuliert."""
    import copy

    klv = load_config(KLV_EXAMPLE)
    bu = load_config(BU_EXAMPLE)
    gemischt = copy.deepcopy(klv)
    gemischt.generationen = [klv.generationen[1], bu.generationen[0]]
    gemischt.ereignisse = klv.ereignisse
    assert gemischt.validate() == []

    df = generate(gemischt)
    assert set(df["produkt"]) == {"klv", "bu"}
    assert validate_portfolio(df) == []
    erg = fortschreiben(df, gemischt, dt.date(2035, 1, 1))
    assert validate_statushistorie(df, erg.historie) == []

    ledger = erg.ledger.merge(
        df[["police_id", "produkt"]], on="police_id", how="left"
    )
    klv_gevos = set(ledger.loc[ledger["produkt"] == "klv", "ereignis"])
    bu_gevos = set(ledger.loc[ledger["produkt"] == "bu", "ereignis"])
    # KLV-Fachlichkeit bleibt bei KLV, BU-Fachlichkeit bei BU:
    assert not bu_gevos & {"STO", "PEX", "ERH"}
    assert not klv_gevos & {"INV", "REA"}
    assert "INV" in bu_gevos


def test_bu_generation_ohne_rechnungsgrundlagen_ist_config_fehler():
    import copy

    cfg = copy.deepcopy(load_config(BU_EXAMPLE))
    cfg.generationen[0].tafel_ri = "GIBTS-NICHT"
    fehler = cfg.validate()
    assert any("GIBTS-NICHT" in f for f in fehler)


def test_bu_vertrag_mit_unbekannter_generation_ist_fehler(config):
    stamm = _bu_stamm(
        {"police_id": 10000001, "start": dt.date(2010, 5, 1), "x": 40, "n": 20,
         "tarif_generation": "GIBTS-NICHT"}
    )
    with pytest.raises(EreignisError, match="GIBTS-NICHT"):
        fortschreiben(stamm, config, dt.date(2020, 1, 1))
