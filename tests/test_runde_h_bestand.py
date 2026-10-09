"""Pruefrunde H, Bestand und Bewertung — drei Funde, drei Invarianten.

**H01 — der Rueckkaufswert des beitragsfreien Vertrags.** Abschluss und
Fuehrungswert wiesen fuer JEDEN beitragsfreien Vertrag den Rueckkaufswert
0,00 aus, waehrend der Kern (``Vertragsstand.werte``) fuer denselben
Vertragsstand Rueckstellung minus Stornoabzug rechnet (Tarifplan KLV 7.2,
Entscheid B3). Invariante: Jeder Leser des Vertragsstands weist in der
Fuehrungskonvention (``monatsgenau``) fuer einen beitragsfreien Vertrag
denselben Rueckkaufswert aus wie der Kern; die Bewertungsstrecke bezieht ihn
vom Kern (EINE Rechnung). Die Jahreszeile bleibt die Regel, in der sie
geschrieben wurde (Rueckkaufswert beitragsfrei 0,00), damit ein alter
Abschluss deckungsgleich nachrechnet (Tarifplan KLV 6).

Die Sollrechnung ist unabhaengig vom Ist-Weg: Der Stornoabzug wird hier von
Hand gebildet (Satz mal Summe minus Reserve, Mindest- und Hoechstbetrag,
flexible Phase, je Vertrag oder je Baustein), aus den Tarifparametern des
Modellpunkts und den Reserven, die der Kern je Baustein mit
``monatsreserve_beitragsfrei`` fuehrt — nicht ueber ``Vertragsstand``.

**H02/H04 — die Jahresgrenzen der Vorgaenge auf jedem Tabellenweg.** Eine
Beitragsfreistellung am oder nach dem Beitragsende (a >= t) nahmen P-B1, der
Abschluss und die Bewertung an; nur der Kern verweigerte sie, und nur, wenn
der Vertrag ueber die Vorgangsfolge lief. Invariante: Jede Vorgangsart der
Folge (``kern.vorgangsfolge.RANG``) erreicht auf jedem Tabellenweg, der ihr
Vertragsjahr traegt, die EINE Stelle des Kerns
(``beitragsreduktion.pruefe_vorgangsjahr``) — auch ohne weiteren Vorgang.
Ratsche: die Menge Art mal Weg mit ``==``, je Paar eine Verletzung und eine
Positivkontrolle.

**H03/H05 — die Reduktionstabelle ohne Ledger.** P-B1 prueft registrierte
Vorgaenge nur mit Config, auch wenn kein Ledger vorliegt, und haelt die
Tabelle dann selbst gegen Tarifwerk und Annahmen (dieselbe Funktion wie der
Ledger-Weg); was ohne Ledger ungeprueft bleibt (die Buchungen), steht
ausdruecklich in der Summary.

Knoten: klv, system/bestand
"""

from __future__ import annotations

import ast
import datetime as _dt
import itertools
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import pytest

from rechner_pipeline.bestand import cli_abschluss, cli_fortschreibung
from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import config_aus_text, load_config
from rechner_pipeline.bestand.fuehrung import months_between
from rechner_pipeline.bestand.manifest import schreibe_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1
from rechner_pipeline.gates import bestand_validate
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    KONVENTION_JAHRESZEILE,
    KONVENTION_MONATSGENAU,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
    model_point_kwargs,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"
CONFIG = REPO_ROOT / "plv" / "configs" / "bestand_klv.toml"
HORIZONT = _dt.date(2020, 1, 1)
STICHTAG = _dt.date(2019, 11, 1)

#: Die Meldungen der EINEN Stelle (kern.beitragsreduktion.pruefe_vorgangsjahr)
#: je Art an der oberen Grenze — der Test erkennt an ihnen, dass der Kern
#: geantwortet hat, nicht eine Abschrift seiner Grenze.
KERN_TEXT = {
    "PEX": "Beitragsfreistellung nach dem Beitragsende",
    "RED": "die Beitragszahlungsdauer ist beendet",
    "TKU": "am oder nach dem Ablauf gibt es nichts mehr zu kuendigen",
    "ERH": "Erhoehung nach dem Beitragsende",
}


# --------------------------------------------------------------------------- #
# Die Welt: ein echter Lauf der Fortschreibung (Producer, oeffentlicher Weg)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def lauf(tmp_path_factory) -> Path:
    ziel = tmp_path_factory.mktemp("lauf")
    assert cli_fortschreibung.main([
        "--config", str(CONFIG), "--neuzugang-ab", "1994-07-01", "--bis", HORIZONT.isoformat(),
        "--out-dir", str(ziel),
    ]) == 0
    return ziel


def _kopie(lauf: Path, ziel: Path, **tabellen: pd.DataFrame) -> Path:
    """Der Lauf mit ersetzten Tabellen, Manifest nachgefuehrt (das
    Bedrohungsmodell des Repos: frei editierbar, passend neu gehasht)."""
    ziel.mkdir(parents=True)
    for pfad in lauf.glob("*.parquet"):
        (ziel / pfad.name).write_bytes(pfad.read_bytes())
    for name, df in tabellen.items():
        write_portfolio(df, ziel / f"{name}.parquet")
    schreibe_manifest(ziel, horizont=HORIZONT, neuzugang_ab=None,
                      config_pfad=CONFIG, ausgaben=sorted(ziel.glob("*.parquet")))
    return ziel


def _tabellen(d: Path) -> Dict[str, pd.DataFrame]:
    return {n: read_portfolio(d / f"{n}.parquet") for n in
            ("bestand_gesamt", "historie", "scheiben", "reduktionen", "ledger")}


# --------------------------------------------------------------------------- #
# H01 — Rueckkaufswert des beitragsfreien Vertrags
# --------------------------------------------------------------------------- #


def _stoab_von_hand(mp: ModelPoint, a: int, summe: float, reserve: float) -> float:
    """Der Stornoabzug des Tarifplans (KLV 6), von Hand: null nach dem Ablauf
    und in der flexiblen Phase, sonst Satz mal (Summe minus Reserve), begrenzt
    auf Mindest- und Hoechstbetrag."""
    flex = mp.x + a >= mp.min_alter_flex and a >= mp.n - mp.min_rlz_flex
    if a > mp.n or flex:
        return 0.0
    return min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (summe - reserve)))


@pytest.fixture(scope="module")
def abschluss(lauf, tmp_path_factory) -> pd.DataFrame:
    """Der Monatsabschluss des Producers (bestand.cli_abschluss)."""
    out = tmp_path_factory.mktemp("abschluss")
    assert cli_abschluss.main([
        "--config", str(CONFIG), "--lauf", str(lauf), "--stichtag", STICHTAG.isoformat(),
        "--bis", HORIZONT.isoformat(), "--out-dir", str(out)]) == 0
    return read_portfolio(out / f"abschluss_{STICHTAG.isoformat()}.parquet")


def test_h01_abschluss_weist_den_rueckkaufswert_beitragsfreier_vertraege_nach_b3_aus(lauf, abschluss):
    """Auf 6b26517 rot: jeder beitragsfreie Vertrag mit Rueckkaufswert 0,00.

    Soll je Vertrag: Rueckstellung (das Deckungskapital der Zeile) minus
    Stornoabzug auf die beitragsfreie Summe und ihre Rueckstellung, vertragsweit
    (alle Generationen der Config tragen den Abzug je Vertrag), nie negativ —
    von Hand gerechnet."""
    config = load_config(CONFIG)
    gen = {g.name: g for g in config.generationen}
    for g in gen.values():
        assert not g.tarifwerk()["stoab_je_baustein"], g.name
    stamm = read_portfolio(lauf / "bestand_gesamt.parquet").set_index("police_id")
    pex = abschluss[abschluss["status_code"] == "PEX"]
    assert len(pex) >= 20, len(pex)
    mit_abzug = 0
    for z in pex.itertuples(index=False):
        row = stamm.loc[int(z.police_id)]
        mp = ModelPoint(**model_point_kwargs(
            row.to_dict(), gen[str(row["tarif_generation"])].generation_fields()))
        a = months_between(pd.Timestamp(row["insurance_start"]).date(), STICHTAG) // 12
        stoab = _stoab_von_hand(mp, a, float(z.vs_bfr), float(z.deckungskapital))
        soll = max(0.0, float(z.deckungskapital) - stoab)
        mit_abzug += stoab > 0.0
        assert float(z.rueckkaufswert) == pytest.approx(soll, rel=1e-12, abs=1e-8), (
            int(z.police_id), float(z.rueckkaufswert), soll)
    # Kein Detektor ohne Treffer: der Abzug wirkt bei den meisten Vertraegen.
    assert mit_abzug >= len(pex) // 2, (mit_abzug, len(pex))


def test_h01_fuehrungswert_und_abschluss_weisen_denselben_rueckkaufswert_aus(lauf, abschluss):
    """Der Fuehrungswert der Migrationsabnahme (bestand.migrationszugang.
    fuehrungswerte) und der Abschluss sind zwei Leser desselben Stands: gleich
    bis aufs Bit, und fuer beitragsfreie Vertraege nicht null."""
    from rechner_pipeline.bestand.migrationszugang import fuehrungswerte

    t = _tabellen(lauf)
    _konv, werte = fuehrungswerte(
        t["bestand_gesamt"], t["historie"], CONFIG.read_text("utf-8"), {"s": STICHTAG},
        scheiben=t["scheiben"], reduktionen=t["reduktionen"])
    pex = abschluss[abschluss["status_code"] == "PEX"]
    for z in pex.itertuples(index=False):
        fw = werte[str(int(z.police_id))]["s"]
        assert fw["rueckkaufswert"] == float(z.rueckkaufswert), int(z.police_id)
    assert (pex["rueckkaufswert"] > 0.0).sum() >= len(pex) // 2


def _welt_je_baustein(je_baustein: bool):
    """Ein Vertrag (Beginn 2015-01-01, n=25, t=20) mit einer Erhoehungsscheibe
    aus Jahr 5 und einer Beitragsfreistellung im Jahr 8 — ohne Herabsetzung
    und Teilkuendigung (also bisher nicht ueber die Vorgangsfolge)."""
    toml = _CONFIG_TOML.replace(
        "min_rlz_flex = 5\n",
        f"min_rlz_flex = 5\nstoab_je_baustein = {'true' if je_baustein else 'false'}\n", 1)
    assert toml != _CONFIG_TOML
    config = config_aus_text(toml)
    stamm = _stamm([{"id": 1, "beginn": "2015-01-01", "n": 25, "t": 20}])
    historie = pd.DataFrame([{"police_id": 1, "status_id": 2, "status_code": "PEX",
                              "status_date": pd.Timestamp("2023-01-01")}]
                            ).astype(dict(STATUS_HISTORIE_SPALTEN))
    scheiben = pd.DataFrame([{
        "police_id": 1, "scheiben_id": 1, "erhoehung_jahr": 5,
        "erhoehung_datum": pd.Timestamp("2020-01-01"), "entry_age": 45, "duration": 20,
        "premium_duration": 15, "sum_insured": 5000.0, "gamma1": 0.0,
    }])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))
    return config, stamm, historie, scheiben


def _soll_je_baustein(config, stamm, scheiben, monate: int, je_baustein: bool) -> float:
    felder = config.generationen[0].generation_fields()
    grund_mp = ModelPoint(**model_point_kwargs(stamm.iloc[0].to_dict(), felder))
    s = scheiben.iloc[0]
    scheibe_row = dict(stamm.iloc[0].to_dict(), entry_age=s["entry_age"], duration=s["duration"],
                       premium_duration=s["premium_duration"], sum_insured=s["sum_insured"])
    scheibe_kw = model_point_kwargs(scheibe_row, felder)
    scheibe_kw["gamma1"] = float(s["gamma1"])
    teile = [(0, Rechenkern(grund_mp)), (int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**scheibe_kw)))]
    pex = 8
    stuecke = []
    for e, kern in teile:
        lokal = monate - 12 * e
        dk = kern.monatsreserve_beitragsfrei(pex - e, lokal)
        stuecke.append((kern.mp, lokal // 12, kern.beitragsfreie_summe(pex - e), dk))
    if je_baustein:
        return sum(max(0.0, dk - _stoab_von_hand(mp, a, summe, dk)) for mp, a, summe, dk in stuecke)
    dk = sum(st[3] for st in stuecke)
    summe = sum(st[2] for st in stuecke)
    return max(0.0, dk - _stoab_von_hand(grund_mp, monate // 12, summe, dk))


@pytest.mark.parametrize("je_baustein", [False, True])
@pytest.mark.parametrize("stichtag", [_dt.date(2023, 1, 1), _dt.date(2024, 6, 1),
                                      _dt.date(2036, 3, 1)])
def test_h01_rueckkaufswert_beitragsfrei_nach_der_tarifregel_des_stornoabzugs(je_baustein, stichtag):
    """Der Abzug je Vertrag oder je Baustein nach dem Tarifwerk der Generation
    (Tarifplan KLV 6), auf der beitragsfreien Summe jedes Bausteins und ihrer
    Rueckstellung. Stichtage: der Jahrestag der Freistellung, unterjaehrig, und
    die flexible Phase (dort kein Abzug)."""
    config, stamm, historie, scheiben = _welt_je_baustein(je_baustein)
    zeile = einzelwerte_am(stamm, historie, config, stichtag, scheiben=scheiben,
                           konvention=KONVENTION_MONATSGENAU)[0]
    monate = months_between(_dt.date(2015, 1, 1), stichtag)
    assert zeile["status"] == "PEX"
    soll = _soll_je_baustein(config, stamm, scheiben, monate, je_baustein)
    assert zeile["rueckkaufswert"] == pytest.approx(soll, rel=1e-12), (zeile, soll)
    if stichtag.year < 2035:
        assert zeile["rueckkaufswert"] < zeile["deckungskapital"]   # der Abzug wirkt
    else:
        assert zeile["rueckkaufswert"] == pytest.approx(zeile["deckungskapital"], rel=1e-12)


def test_h01_die_regeln_unterscheiden_sich_wirklich():
    """Kein Detektor ohne Treffer: Mit derselben Welt ergeben Abzug je Vertrag
    und je Baustein verschiedene Rueckkaufswerte."""
    werte = []
    for je in (False, True):
        config, stamm, historie, scheiben = _welt_je_baustein(je)
        werte.append(einzelwerte_am(stamm, historie, config, _dt.date(2024, 6, 1),
                                    scheiben=scheiben)[0]["rueckkaufswert"])
    assert werte[0] != pytest.approx(werte[1], rel=1e-9), werte


def test_h01_die_jahreszeile_bleibt_die_regel_in_der_sie_geschrieben_wurde():
    """Die Konvention ``jahreszeile`` (aeltere, festgeschriebene Abschluesse)
    fuehrte den Rueckkaufswert eines beitragsfreien Vertrags mit 0,00 und
    rechnet so weiter nach — sonst wuerde jeder alte Abschluss nachtraeglich
    zum Befund (Tarifplan KLV 6). Die Fuehrungskonvention weist B3 aus."""
    config, stamm, historie, scheiben = _welt_je_baustein(False)
    alt = einzelwerte_am(stamm, historie, config, _dt.date(2024, 6, 1), scheiben=scheiben,
                         konvention=KONVENTION_JAHRESZEILE)[0]
    neu = einzelwerte_am(stamm, historie, config, _dt.date(2024, 6, 1), scheiben=scheiben,
                         konvention=KONVENTION_MONATSGENAU)[0]
    assert alt["status"] == neu["status"] == "PEX"
    assert alt["rueckkaufswert"] == 0.0
    assert neu["rueckkaufswert"] > 0.0


def test_h01_herabgesetzt_und_freigestellt_derselbe_weg():
    """Ein Vertrag mit Herabsetzung und spaeterer Freistellung lief schon ueber
    die Folge, stand aber im Ausweis mit 0,00 (werte_nach_vorgaengen). Jetzt
    der Wert des Zustands — Soll von Hand auf Summe und Reserve der Zeile."""
    from rechner_pipeline.models.bestand import REDUKTIONEN_NAMES, REDUKTIONEN_SPALTEN

    config = config_aus_text(_CONFIG_TOML)
    stamm = _stamm([{"id": 1, "beginn": "2015-01-01", "n": 25, "t": 20}])
    historie = pd.DataFrame([{"police_id": 1, "status_id": 2, "status_code": "PEX",
                              "status_date": pd.Timestamp("2026-01-01")}]
                            ).astype(dict(STATUS_HISTORIE_SPALTEN))
    red = pd.DataFrame([{"police_id": 1, "reduktion_jahr": 8,
                         "reduktion_datum": pd.Timestamp("2023-01-01"), "anteil": 0.6,
                         "verfahren": "prospektiv"}])[list(REDUKTIONEN_NAMES)].astype(
        dict(REDUKTIONEN_SPALTEN))
    zeile = einzelwerte_am(stamm, historie, config, _dt.date(2027, 4, 1),
                           reduktionen=red)[0]
    assert zeile["status"] == "PEX"
    mp = ModelPoint(**model_point_kwargs(stamm.iloc[0].to_dict(),
                                         config.generationen[0].generation_fields()))
    soll = max(0.0, zeile["deckungskapital"] - _stoab_von_hand(
        mp, 12, zeile["vs_bfr"], zeile["deckungskapital"]))
    assert zeile["rueckkaufswert"] == pytest.approx(soll, rel=1e-12)
    assert 0.0 < zeile["rueckkaufswert"] < zeile["deckungskapital"]


# --------------------------------------------------------------------------- #
# H02/H04 — Jahresgrenzen der Vorgaenge auf jedem Tabellenweg
# --------------------------------------------------------------------------- #


def _pex_am_beitragsende(lauf: Path, ziel: Path, *, jahr_von_t: int = 0):
    """In den echten Lauf eine Beitragsfreistellung im Vertragsjahr t (+
    ``jahr_von_t``) eintragen — Historie, Ledger und Stamm stimmig, bei einem
    beitragspflichtig laufenden Vertrag ohne Vorgaenge und Scheiben, dessen
    Beitragsende vor dem Horizont liegt. Ab t ist die beitragsfreie Summe die
    gefuehrte (Tarifplan KLV 6), also bucht das Ledger die Summe des Stamms —
    den Betrag, den die Herleitung dort selbst nennt."""
    t = _tabellen(lauf)
    st, h, led = t["bestand_gesamt"], t["historie"], t["ledger"]
    jahr_je = st["premium_duration"] + jahr_von_t
    datum_je = [pd.Timestamp(b) + pd.DateOffset(years=int(j))
                for b, j in zip(st["insurance_start"], jahr_je)]
    kandidaten = st[(jahr_je < st["duration"])
                    & (st["status_code"] == "POL") & (st["produkt"] == "klv")
                    & ~st["police_id"].isin(t["reduktionen"]["police_id"])
                    & ~st["police_id"].isin(t["scheiben"]["police_id"])
                    & ~st["police_id"].isin(h["police_id"])
                    & pd.Series([d < pd.Timestamp(HORIZONT) for d in datum_je], index=st.index)]
    assert len(kandidaten), "die Welt traegt keinen laufenden Vertrag mit t < n vor dem Horizont"
    r = kandidaten.iloc[0]
    pid, jahr = int(r["police_id"]), int(r["premium_duration"]) + jahr_von_t
    datum = pd.Timestamp(r["insurance_start"]) + pd.DateOffset(years=jahr)
    h = pd.concat([h, pd.DataFrame([{"police_id": pid, "status_id": 2, "status_code": "PEX",
                                     "status_date": datum}]).astype(dict(STATUS_HISTORIE_SPALTEN))])
    h = h.sort_values(["police_id", "status_id"]).reset_index(drop=True)
    st = st.copy()
    maske = st["police_id"] == pid
    st.loc[maske, "status_id"] = 2
    st.loc[maske, "status_code"] = "PEX"
    st.loc[maske, "status_date"] = datum
    zeile = {"police_id": pid, "tarif_generation": r["tarif_generation"], "ereignis": "PEX",
             "vertragsjahr": jahr, "status_date": datum, "betrag_art": "VS_bfr",
             "betrag": float(r["sum_insured"]), "betrag_herkunft": led["betrag_herkunft"].iloc[0]}
    led = pd.concat([led, pd.DataFrame([zeile]).astype(led.dtypes.to_dict())])
    led = led.sort_values(["police_id", "status_date"], kind="stable").reset_index(drop=True)
    d = _kopie(lauf, ziel, historie=h, bestand_gesamt=st, ledger=led)
    return d, pid, r


def _pb1_cli(d: Path, tmp: Path):
    return bestand_validate.main([
        "--portfolio", str(d / "bestand_gesamt.parquet"), "--historie", str(d / "historie.parquet"),
        "--scheiben", str(d / "scheiben.parquet"), "--ledger", str(d / "ledger.parquet"),
        "--reduktionen", str(d / "reduktionen.parquet"), "--bis", HORIZONT.isoformat(),
        "--config", str(CONFIG), "--manifest", str(d / "laufmanifest.json"),
        "--diagnostics-dir", str(tmp / "diag")])


def test_h02_pb1_verweigert_die_freistellung_am_beitragsende(lauf, tmp_path):
    """Auf 6b26517 rot: P-B1 (oeffentlicher Weg, Vollprofil, Manifest) Exit 0.
    Soll: Exit 20 mit der Meldung des Kerns, je Weg (Historie und Ledger)."""
    d, pid, _r = _pex_am_beitragsende(lauf, tmp_path / "lauf")
    ergebnis = _pb1_cli(d, tmp_path)
    meldungen = [e["message"] for e in ergebnis.errors]
    assert ergebnis.exit_code == 20, (ergebnis.status, meldungen[:3])
    for weg in ("historie", "ledger"):
        assert any(m.startswith(f"vorgangsjahr {weg}: police {pid}") and KERN_TEXT["PEX"] in m
                   for m in meldungen), (weg, meldungen[:5])


def test_h02_positivkontrolle_dieselbe_freistellung_ein_jahr_vor_dem_beitragsende(lauf, tmp_path):
    """Dieselbe Manipulation im letzten zulaessigen Jahr (t-1) loest die
    Jahresgrenze nicht aus — die Regel trifft die Grenze, nicht die
    Manipulation (der Betrag passt dort nicht, also nur keine
    Vorgangsjahr-Meldung)."""
    d, pid, _r = _pex_am_beitragsende(lauf, tmp_path / "lauf", jahr_von_t=-1)
    meldungen = [e["message"] for e in _pb1_cli(d, tmp_path).errors]
    assert not any(m.startswith("vorgangsjahr") for m in meldungen), meldungen[:3]


def test_h02_abschluss_verweigert_die_freistellung_am_beitragsende(lauf, tmp_path):
    """Der Producer des Abschlusses (cli_abschluss) prueft ueber dieselbe
    Engine und schreibt nichts fest."""
    d, _pid, _r = _pex_am_beitragsende(lauf, tmp_path / "lauf")
    out = tmp_path / "abs"
    assert cli_abschluss.main([
        "--config", str(CONFIG), "--lauf", str(d), "--stichtag", STICHTAG.isoformat(),
        "--bis", HORIZONT.isoformat(), "--out-dir", str(out)]) != 0
    assert not list(out.glob("abschluss_*.parquet"))


@pytest.mark.parametrize("konvention", [KONVENTION_JAHRESZEILE, KONVENTION_MONATSGENAU])
def test_h02_die_bewertung_ohne_folge_erreicht_dieselbe_regel(lauf, tmp_path, konvention):
    """Ein direkter Aufrufer der Bewertungsstrecke (einzelwerte_am) rechnet
    den Vertrag nicht still als beitragsfrei, in keiner Konvention."""
    d, pid, r = _pex_am_beitragsende(lauf, tmp_path / "lauf")
    t = _tabellen(d)
    stichtag = (pd.Timestamp(r["insurance_start"])
                + pd.DateOffset(years=int(r["premium_duration"]), months=6)).date()
    with pytest.raises(ValueError, match=KERN_TEXT["PEX"]):
        einzelwerte_am(t["bestand_gesamt"], t["historie"], load_config(CONFIG), stichtag,
                       scheiben=t["scheiben"], reduktionen=t["reduktionen"],
                       konvention=konvention)


def _eine_zeile_je_weg(art: str, weg: str, jahr: int) -> Dict[str, pd.DataFrame]:
    """Eine Zeile der Art ``art`` im Vertragsjahr ``jahr`` auf genau dem Weg
    ``weg`` (n=25, t=20, Beginn 2000-01-01)."""
    datum = pd.Timestamp("2000-01-01") + pd.DateOffset(years=jahr)
    if weg == "historie":
        return {"historie": pd.DataFrame([{"police_id": 1, "status_id": 2, "status_code": art,
                                           "status_date": datum}])}
    if weg == "ledger":
        return {"ledger": pd.DataFrame([{"police_id": 1, "ereignis": art, "vertragsjahr": jahr,
                                         "status_date": datum}])}
    if weg == "reduktionen":
        return {"reduktionen": pd.DataFrame([{
            "police_id": 1, "reduktion_jahr": jahr, "reduktion_datum": datum, "anteil": 0.6,
            "verfahren": "teilkuendigung" if art == "TKU" else "prospektiv"}])}
    if weg == "scheiben":
        return {"scheiben": pd.DataFrame([{"police_id": 1, "erhoehung_jahr": jahr,
                                           "erhoehung_datum": datum}])}
    raise AssertionError(weg)


def test_h02_ratsche_jede_art_auf_jedem_weg_erreicht_den_kern():
    """Ratsche (dynamisch, ``==``): Die Menge Art mal Weg, die die Engine
    deklariert (``VORGANGSJAHR_WEGE``), ist genau die Menge der Paare, auf
    denen eine Verletzung der oberen Grenze die Meldung des KERNS ausloest; die
    Arten sind genau die der Folge (``RANG``). Positivkontrolle je Paar: das
    letzte zulaessige Jahr meldet nichts, und das Jahr 0 meldet je Paar die
    untere Grenze."""
    from rechner_pipeline.bestand.vorbedingungen import (
        VORGANGSJAHR_WEGE,
        vorgangsjahr_fehler,
    )
    from rechner_pipeline.kern.vorgangsfolge import RANG

    assert set(VORGANGSJAHR_WEGE) == set(RANG)
    stamm = _stamm([{"id": 1, "beginn": "2000-01-01", "n": 25, "t": 20}])
    obergrenze = {"PEX": 20, "RED": 20, "ERH": 20, "TKU": 25}
    alle_wege = sorted({w for wege in VORGANGSJAHR_WEGE.values() for w in wege})
    assert alle_wege == ["historie", "ledger", "reduktionen", "scheiben"]
    treffer = set()
    for art, weg in itertools.product(sorted(RANG), alle_wege):
        if weg == "historie" and art != "PEX":
            continue   # die Historie traegt nur Zustaende
        if weg == "reduktionen" and art not in ("RED", "TKU"):
            continue
        if weg == "scheiben" and art != "ERH":
            continue
        fehler = vorgangsjahr_fehler(stamm, **_eine_zeile_je_weg(art, weg, obergrenze[art]))
        if any(f.startswith(f"vorgangsjahr {weg}: police 1") and KERN_TEXT[art] in f
               for f in fehler):
            treffer.add((art, weg))
        assert vorgangsjahr_fehler(stamm, **_eine_zeile_je_weg(art, weg, obergrenze[art] - 1)) == []
        unten = vorgangsjahr_fehler(stamm, **_eine_zeile_je_weg(art, weg, 0))
        assert any("fruehestens am ersten Jahrestag" in f for f in unten), (art, weg, unten)
    deklariert = {(art, weg) for art, wege in VORGANGSJAHR_WEGE.items() for weg in wege}
    assert treffer == deklariert
    assert len(deklariert) == 8


def test_h02_ratsche_die_engine_ruft_die_regel_und_die_regel_den_kern():
    """Ratsche (statisch, benannt als solche): ``lies_und_pruefe_pb1`` ruft
    ``vorgangsjahr_fehler``, und die ruft ``pruefe_vorgangsjahr`` — keine
    eigene Grenze daneben (kein Vergleich mit premium_duration/duration)."""
    baum = ast.parse((SRC / "bestand" / "vorbedingungen.py").read_text("utf-8"))
    funktionen = {f.name: f for f in ast.walk(baum) if isinstance(f, ast.FunctionDef)}

    def gerufen(f) -> set:
        return {getattr(c.func, "id", getattr(c.func, "attr", None))
                for c in ast.walk(f) if isinstance(c, ast.Call)}

    assert "vorgangsjahr_fehler" in gerufen(funktionen["lies_und_pruefe_pb1"])
    regel = funktionen["vorgangsjahr_fehler"]
    assert "pruefe_vorgangsjahr" in gerufen(regel)
    vergleiche = [c for c in ast.walk(regel) if isinstance(c, ast.Compare)
                  and any(isinstance(o, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)) for o in c.ops)]
    assert vergleiche == [], [ast.unparse(c) for c in vergleiche]


# --------------------------------------------------------------------------- #
# H03/H05 — Reduktionstabelle ohne Ledger
# --------------------------------------------------------------------------- #


def _ohne_ledger(d: Path, *, config: bool, reduktionen: Optional[Path] = None) -> dict:
    e = {"portfolio": d / "bestand_gesamt.parquet", "historie": d / "historie.parquet",
         "scheiben": d / "scheiben.parquet",
         "reduktionen": reduktionen or d / "reduktionen.parquet"}
    if config:
        e["config"] = CONFIG
    return e


@pytest.fixture(scope="module")
def verfaelscht(lauf, tmp_path_factory) -> Path:
    """Eine Herabsetzung auf Verfahren ``mit_abzug`` und Anteil 0,123 gesetzt
    (die Config sagt prospektiv und red_anteil 0,6), alle Teilkuendigungen auf
    Anteil 0,3 (tk_anteil 0,7) — Manifest nachgefuehrt."""
    red = read_portfolio(lauf / "reduktionen.parquet").copy()
    i = red.index[red["verfahren"] == "prospektiv"][0]
    red.loc[i, "verfahren"] = "mit_abzug"
    red.loc[i, "anteil"] = 0.123
    red.loc[red["verfahren"] == "teilkuendigung", "anteil"] = 0.3
    return _kopie(lauf, tmp_path_factory.mktemp("v") / "lauf", reduktionen=red)


def _verlangt_config(usage) -> bool:
    return any(u["code"] == "missing_arg" and "--config" in u["message"] for u in usage)


def test_h03_ohne_ledger_und_ohne_config_ist_ein_bedienfehler(verfaelscht):
    """Auf 6b26517 rot: weder Usage noch Fehler."""
    _, _, fehler, usage = lies_und_pruefe_pb1(_ohne_ledger(verfaelscht, config=False))
    assert _verlangt_config(usage), (usage, fehler[:3])


def test_h03_ohne_ledger_mit_config_haelt_die_tabelle_gegen_tarifwerk_und_annahmen(verfaelscht):
    """Auf 6b26517 rot: gruen. Soll: dieselben Befunde wie auf dem Ledger-Weg —
    unabhaengig aus der TOML gezaehlt: jede Teilkuendigung und die eine
    Herabsetzung beim Anteil, die Herabsetzung beim Verfahren."""
    import tomllib

    annahmen = tomllib.loads(CONFIG.read_text("utf-8"))["annahmen"]
    red = read_portfolio(verfaelscht / "reduktionen.parquet")
    soll_anteil = int(sum(
        abs(float(a) - (annahmen["tk_anteil"] if v == "teilkuendigung" else annahmen["red_anteil"])) > 1e-12
        for a, v in zip(red["anteil"], red["verfahren"])))
    _, geprueft, fehler, usage = lies_und_pruefe_pb1(_ohne_ledger(verfaelscht, config=True))
    assert not usage
    meldungen = [f["message"] for f in fehler]
    anteil = [m for m in meldungen if "die Annahmen sagen" in m]
    verfahren = [m for m in meldungen if "das Tarifwerk der Generation sagt 'prospektiv'" in m]
    assert len(anteil) == soll_anteil and soll_anteil > 1, (len(anteil), soll_anteil)
    assert len(verfahren) == 1, verfahren


def test_h03_positivkontrolle_unveraendert_gruen_und_die_buchungen_ausdruecklich_ungeprueft(lauf):
    """Die unveraenderte Tabelle mit Config ohne Ledger: gruen — und die
    Summary sagt, wie viele registrierte Vorgaenge ohne Pruefung ihrer
    Buchungen geblieben sind. Mit Ledger fehlt der Eintrag (dort ist geprueft)."""
    _, geprueft, fehler, usage = lies_und_pruefe_pb1(_ohne_ledger(lauf, config=True))
    assert not usage and not fehler, (usage, fehler[:3])
    n = len(read_portfolio(lauf / "reduktionen.parquet"))
    assert geprueft["reduktionen_buchungen_ungeprueft"] == n > 0
    e = dict(_ohne_ledger(lauf, config=True), ledger=lauf / "ledger.parquet")
    _, geprueft, fehler, usage = lies_und_pruefe_pb1(e, bis=HORIZONT)
    assert not usage and not fehler
    assert "reduktionen_buchungen_ungeprueft" not in geprueft


def test_h03_gate_pb1_oeffentlicher_weg(verfaelscht, tmp_path):
    """P-B1 ueber die CLI: ohne Config Exit 2, mit Config Exit 20."""
    d = verfaelscht
    basis = ["--portfolio", str(d / "bestand_gesamt.parquet"),
             "--historie", str(d / "historie.parquet"), "--scheiben", str(d / "scheiben.parquet"),
             "--reduktionen", str(d / "reduktionen.parquet"),
             "--diagnostics-dir", str(tmp_path / "diag")]
    assert bestand_validate.main(basis).exit_code == 2
    assert bestand_validate.main(basis + ["--config", str(CONFIG)]).exit_code == 20


def test_h03_ratsche_die_bindung_der_tabelle_hat_eine_stelle():
    """Ratsche (statisch, ``==``): ``red_bindung_fehler`` ruft in der
    Bestandsschicht genau EINE Funktion — die, durch die Ledger-Weg und
    Tabellen-Weg der Engine gehen; beide rufen sie."""
    aufrufer = set()
    for pfad in sorted((SRC / "bestand").glob("*.py")):
        baum = ast.parse(pfad.read_text("utf-8"))
        for f in ast.walk(baum):
            if isinstance(f, ast.FunctionDef):
                for c in ast.walk(f):
                    if isinstance(c, ast.Call) and getattr(c.func, "id", None) == "red_bindung_fehler":
                        aufrufer.add((pfad.name, f.name))
    assert aufrufer == {("ledger_bindung.py", "pruefe_reduktionen_tarifwerk")}
    for pfad, name in (("ledger_bindung.py", "pruefe_ledger_betraege"),
                       ("vorbedingungen.py", "lies_und_pruefe_pb1")):
        baum = ast.parse((SRC / "bestand" / pfad).read_text("utf-8"))
        f = next(x for x in ast.walk(baum) if isinstance(x, ast.FunctionDef) and x.name == name)
        assert any(isinstance(c, ast.Call) and getattr(c.func, "id", None) == "pruefe_reduktionen_tarifwerk"
                   for c in ast.walk(f)), (pfad, name)
