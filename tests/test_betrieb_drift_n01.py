"""Der Betriebsweg prueft und liest, was der Fallweg prueft und liest (Betriebsbefund N-01).

Beim Neuaufsetzen des Betriebsstands aus dem Fall endete der Tageslauf in
der Wache rot: zwei Rueckkaeufe im zehnten Jahr wichen je einen Cent vom
Ledger ab. Das Ledger war richtig (Basis plus Korrekturschicht, Kern
3.5.0), die Wache falsch — sie hatte Korrekturschicht und Verankerung
nicht an die P-B1-Engine gereicht, obwohl ``_stand_bauen`` beide schreibt
und in die Fortschreibung gibt. Dieselbe Luecke, dreimal an demselben Weg:
der Teilbestandsbericht ohne Schicht (rund 13.700 EUR Deckungskapital je
Vertrag), der Monatsabschluss ohne Schicht, und ein Eingang, dessen
Nebentabellen niemand gegen die Vokabel des Gates hielt (die Fixture
dieses Tests trug ``zustand_ta = "POL"``; der Kern brach vier Schichten
tiefer ab).

Zwei Invarianten, zwei Ratschen:
* Wer die P-B1-Engine ruft, baut ihre Eingaben nicht selbst, sondern aus
  ``ROLLEN_DATEIEN`` (``bestand.manifest.lauf_eingaben``).
* Was der Betrieb an Nebentabellen liest, wird gegen dieselbe Vokabel
  gehalten wie im Gate (``models.bestand``).

Knoten: system/betrieb
"""

from __future__ import annotations

import ast
import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.manifest import (
    NEBENTABELLEN,
    PFLICHT_ROLLEN,
    ROLLEN_DATEIEN,
    lauf_eingaben,
    nebentabellen_in,
)
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, lies_protokoll, tageslauf
from rechner_pipeline.models.bestand import (
    VERANKERUNGSZUSTAENDE,
    ZUSTAENDE_TA,
    validate_schichten,
    validate_verankerung,
)
from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen, _schichten, _verankerung
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import STICHTAG, _fall

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "rechner_pipeline"


@pytest.fixture(scope="module")
def gefuehrt_mit_schicht(tmp_path_factory):
    """Ein Betrieb mit uebernommenem Vertrag samt Bausteinen, Schicht und Verankerung."""
    wurzel = tmp_path_factory.mktemp("n01")
    fall = _fall_mit_nebentabellen(wurzel)
    stand = wurzel / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage(stand)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    return ablage


# --------------------------------------------------------------------------- #
# Invariante 1: die Wache liest jede Rolle, die der Stand traegt
# --------------------------------------------------------------------------- #

def test_die_wache_bekommt_jede_rolle_die_der_stand_schreibt(gefuehrt_mit_schicht, monkeypatch):
    """Klasse, nicht Einzelfall: JEDE Datei der Rollentabelle, die im Stand
    liegt, erreicht die P-B1-Engine — auch eine kuenftige Nebentabelle.
    Mutationsprobe: die Rollen in _wache wieder von Hand bauen -> rot."""
    ablage = gefuehrt_mit_schicht
    gesehen: list = []
    echt = tl.lies_und_pruefe_pb1

    def spion(eingaben, **kw):
        gesehen.append(dict(eingaben))
        return echt(eingaben, **kw)

    monkeypatch.setattr(tl, "lies_und_pruefe_pb1", spion)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    assert gesehen, "die Wache hat die Engine nicht gerufen"
    im_stand = {rolle for rolle, datei in ROLLEN_DATEIEN.items() if (ablage.stand / datei).is_file()}
    assert {"schichten", "verankerung"} <= im_stand          # die Fixture traegt sie
    assert im_stand <= set(gesehen[-1]), sorted(im_stand - set(gesehen[-1]))
    # Die Engine hat sie auch geprueft, nicht nur bekommen:
    assert zeile["pb1"]["geprueft"]["schichten_zeilen"] == 1
    assert zeile["pb1"]["geprueft"]["verankerung_zeilen"] == 1


def test_lauf_eingaben_ist_die_tabelle(tmp_path):
    for rolle in PFLICHT_ROLLEN:
        assert rolle in ROLLEN_DATEIEN
    assert set(PFLICHT_ROLLEN) | set(NEBENTABELLEN) == set(ROLLEN_DATEIEN)
    (tmp_path / ROLLEN_DATEIEN["schichten"]).write_bytes(b"")
    eingaben = lauf_eingaben(tmp_path, tmp_path / "c.toml")
    assert set(eingaben) == set(PFLICHT_ROLLEN) | {"schichten", "config"}
    assert nebentabellen_in(tmp_path) == {"schichten": tmp_path / "schichten.parquet"}


def test_abschluss_und_berichte_tragen_die_korrekturschicht(gefuehrt_mit_schicht):
    """Der Monatsabschluss weist die Schicht des uebernommenen Vertrags aus
    (rho != 0 in der Fixture), der Teilbestand traegt jede Rolle, und der
    Bericht nennt die Schicht als Position statt nur andere Kurven zu zeigen."""
    ablage = gefuehrt_mit_schicht
    eintraege = [e for z in lies_protokoll(ablage.protokoll_pfad) for e in z.get("abschluesse", [])]
    assert eintraege, "kein Monatsabschluss im gefuehrten Fenster"
    abschluss = read_portfolio(ablage.abschluesse / eintraege[0]["datei"])
    schicht = abschluss.loc[abschluss["police_id"] == 7_000_001, "korrekturschicht"]
    assert len(schicht) == 1 and float(schicht.iloc[0]) != 0.0
    tabellen = {rolle: read_portfolio(ablage.stand / datei)
                for rolle, datei in ROLLEN_DATEIEN.items() if (ablage.stand / datei).is_file()}
    teil = tl._teilbestand(tabellen, [7_000_001])
    assert set(teil) == set(ROLLEN_DATEIEN)
    assert len(teil["schichten"]) == 1 and len(teil["verankerung"]) == 1
    mit_bericht = [e for e in eintraege if "bericht" in e]
    assert mit_bericht, "kein Bestandsbericht im gefuehrten Fenster"
    for eintrag in mit_bericht:
        html = (ablage.berichte / eintrag["bericht"]).read_text("utf-8")
        assert "davon Korrekturschicht" in html
        for teilbestand in eintrag.get("teilbestaende", []):
            teil_html = (ablage.berichte / teilbestand["bericht"]).read_text("utf-8")
            assert "davon Korrekturschicht" in teil_html


def _fall_mit_schicht_auf_allen(wurzel: Path) -> Path:
    """Wie _fall_mit_nebentabellen, aber Schicht und Verankerung auch fuer den
    Vertrag, der im Fixture-Betrieb im zehnten Jahr storniert (7000002,
    Beginn 2019-07-01: 78 Monate bis zum Stichtag)."""
    fall = _fall_mit_nebentabellen(wurzel)
    quelle = fall / "abgeleitet" / "bestand"
    schichten = pd.concat([_schichten(7_000_001), _schichten(7_000_002)], ignore_index=True)
    verankerung = pd.concat([_verankerung(7_000_001), _verankerung(7_000_002)], ignore_index=True)
    verankerung.loc[verankerung["police_id"] == 7_000_002, "monate_ta"] = 78
    write_portfolio(schichten, quelle / "schichten.parquet")
    write_portfolio(verankerung, quelle / "verankerung.parquet")
    return fall


def test_ein_storno_mit_schicht_laeuft_gruen_durch_die_wache(tmp_path):
    """Der Betriebsbefund selbst: Storno eines uebernommenen Vertrags mit
    Korrekturschicht (rho = 0,02). Die Buchung traegt Basis plus Schicht;
    die Wache leitet denselben Betrag her — vorher rechnete sie ohne
    Schicht und meldete das richtige Ledger als falsch (Exit 3).
    Mutationsprobe: schichten/verankerung aus lauf_eingaben nehmen -> rot."""
    fall = _fall_mit_schicht_auf_allen(tmp_path)
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage(stand)
    # Vor dem Storno: der Abschluss weist die Schicht des Vertrags aus.
    code, zeile = tageslauf(ablage, dt.date(2029, 1, 4))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    abschluss = read_portfolio(ablage.abschluesse / zeile["abschluesse"][-1]["datei"])
    schicht = abschluss.loc[abschluss["police_id"] == 7_000_002, "korrekturschicht"]
    assert len(schicht) == 1 and float(schicht.iloc[0]) != 0.0
    # Das Jahr des Stornos: gruen, und der Storno steht im Ledger.
    code, zeile = tageslauf(ablage, dt.date(2030, 1, 4))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    assert zeile["pb1"]["urteil"] == "gruen"
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    sto = ledger[(ledger["police_id"] == 7_000_002) & (ledger["ereignis"] == "STO")]
    assert len(sto) == 1 and int(sto["vertragsjahr"].iloc[0]) == 10
    assert zeile["pb1"]["geprueft"]["betraege_hergeleitet"] >= len(ledger[ledger["ereignis"] == "STO"])


# --------------------------------------------------------------------------- #
# Invariante 2: der Betriebseingang haelt die Vokabel des Gates
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("tabelle,spalte,wert", [
    ("verankerung", "zustand_ta", "POL"),
    ("verankerung", "zustand_ta", ""),
    ("schichten", "verankerungszustand", "POL"),
    ("schichten", "verankerungszustand", "beitragspflichtig"),
])
def test_ein_zugangsstand_mit_fremder_vokabel_wird_kein_eingang(tmp_path, tabelle, spalte, wert):
    """Die alte Fixture dieses Betriebs trug genau diese Werte, und der
    Tageslauf lief gruen — bis der Kern sie bewerten sollte."""
    fall = _fall_mit_nebentabellen(tmp_path)
    quelle = fall / "abgeleitet" / "bestand"
    df = read_portfolio(quelle / f"{tabelle}.parquet")
    df[spalte] = wert
    write_portfolio(df, quelle / f"{tabelle}.parquet")
    stand = tmp_path / "daten"
    with pytest.raises(ueb.UebernahmeError, match="Gate"):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    assert not (stand / "uebernahme" / "probe-uebernahme").exists()
    # Dieselbe Pruefung faengt es auch beim Lesen — ein Eingang, der die
    # Registrierung umgangen hat, kommt nicht in die Fortschreibung.
    fehler = ueb.nebentabellen_fehler(
        read_portfolio(quelle / "bestand.parquet"), read_portfolio(quelle / "historie.parquet"),
        read_portfolio(quelle / "scheiben.parquet"), read_portfolio(quelle / "verankerung.parquet"),
        read_portfolio(quelle / "schichten.parquet"))
    assert any(spalte in f for f in fehler), fehler


def test_die_vokabel_ist_die_des_gates():
    """Gate, Engine und Betrieb sprechen dieselbe Sprache: die Verankerung
    die der Uebernahme, die Schicht die Erlebenszustaende der Kern-Modelle
    (gegen den Kern gehalten in test_korrekturschicht)."""
    from rechner_pipeline.gates.verankerung_belegen import ZUSTAENDE

    assert ZUSTAENDE == ZUSTAENDE_TA
    assert "aktiv" in VERANKERUNGSZUSTAENDE
    # Die korrigierte Fixture besteht die Pruefung, die alte ("POL") nicht.
    stamm = pd.DataFrame([{"police_id": 7_000_001, "duration": 25}])
    assert validate_verankerung(stamm, _verankerung(7_000_001)) == []
    assert validate_schichten(stamm, _schichten(7_000_001), _verankerung(7_000_001)) == []
    alt = _verankerung(7_000_001); alt["zustand_ta"] = "POL"
    assert any("zustand_ta" in f for f in validate_verankerung(stamm, alt))
    alt = _schichten(7_000_001); alt["verankerungszustand"] = "POL"
    assert any("verankerungszustand" in f for f in validate_schichten(stamm, alt, _verankerung(7_000_001)))


# --------------------------------------------------------------------------- #
# Ratsche: kein Aufrufer der Engine tippt die Rollen ab
# --------------------------------------------------------------------------- #

ERBAUER = {SRC / "bestand" / "manifest.py", SRC / "bestand" / "vorbedingungen.py"}


def _rollen_literale(quelle: str) -> list:
    """Dict-/Tupel-/Listen-Literale, die zwei oder mehr P-B1-Rollen nennen."""
    rollen = set(ROLLEN_DATEIEN)
    treffer = []
    for knoten in ast.walk(ast.parse(quelle)):
        namen: set = set()
        if isinstance(knoten, ast.Dict):
            namen = {k.value for k in knoten.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        elif isinstance(knoten, (ast.Tuple, ast.List)):
            namen = {e.value for e in knoten.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if len(namen & rollen) >= 2:
            treffer.append((knoten.lineno, sorted(namen & rollen)))
    return treffer


def _aufrufer_der_engine() -> list:
    return sorted(
        p for p in SRC.rglob("*.py")
        if "lies_und_pruefe_pb1" in p.read_text("utf-8") and p not in ERBAUER
    )


def test_kein_aufrufer_der_engine_baut_die_rollen_von_hand():
    """Vier Aufrufer, vier abgetippte Listen, eine unvollstaendig — die
    Bauform war der Fehler. Wer die Engine ruft, nimmt die Tabelle."""
    aufrufer = _aufrufer_der_engine()
    assert {p.name for p in aufrufer} >= {"tageslauf.py", "cli_abschluss.py", "cli_report.py", "bestand_validate.py"}
    befunde = {
        str(p.relative_to(REPO_ROOT)): treffer
        for p in aufrufer
        if (treffer := _rollen_literale(p.read_text("utf-8")))
    }
    assert befunde == {}, befunde


def test_die_ratsche_faengt_die_abgetippte_liste():
    """Selbsttest der Ratsche gegen die Fassung vor dem Fix."""
    assert _rollen_literale(
        'eingaben = {"portfolio": a / "x", "historie": a / "y", "config": c}\n') == [(1, ["historie", "portfolio"])]
    assert _rollen_literale('for rolle in ("portfolio", "historie", "ledger"):\n    pass\n') == [(1, ["historie", "ledger", "portfolio"])]
    assert _rollen_literale('eingaben = {"portfolio": a}\nx = ("config", "portfolio")\n') == []
