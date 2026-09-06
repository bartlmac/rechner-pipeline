"""Uebernahme-Eingang: registrieren, unantastbar lesen, im Tagesbetrieb mitfahren.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B5. Ein migrierter
Bestand tritt als datierter Zugang in den Tagesbetrieb ein: einmal
registriert (Fall-Bezug, Summen je Datei), dann in jedem Lauf im selben
Strom fortgeschrieben wie das eigene Geschaeft. Der Eingang hier ist
synthetisch (ein kleiner Zugangsstand wie ihn gates.bestand_uebernehmen
hinterlaesst); der echte Baldrian-Zugang liegt im Fall-Arbeitsbereich
und ist kein Repo-Inhalt (ADR-002).

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"
STICHTAG = dt.date(2026, 1, 1)


def _zugangsstand(ziel: Path) -> None:
    """Ein Zugangsstand wie von gates.bestand_uebernehmen: drei Vertraege
    der Generation KLV-2017 (Nummernkreis 7 Mio, wie ein fremder Bestand),
    einer davon beitragsfrei uebernommen."""
    zeilen = []
    for k, (beginn, status) in enumerate([("2018-03-01", "POL"), ("2019-07-01", "POL"),
                                          ("2017-11-01", "PEX")]):
        b = pd.Timestamp(beginn)
        zeilen.append({
            "police_id": 7_000_001 + k, "tarif_generation": "KLV-2017", "produkt": "klv",
            "status_id": 2 if status == "PEX" else 1, "status_code": status,
            "status_date": pd.Timestamp("2023-11-01") if status == "PEX" else b,
            "sex": "F", "date_of_birth": b - pd.DateOffset(years=35), "entry_age": 35,
            "duration": 25, "premium_duration": 20, "sum_insured": 60000.0, "bu_rente": 0.0,
            "zahlweise": 12, "insurance_start": b, "insurance_end": b + pd.DateOffset(years=25),
            "payment_end": b + pd.DateOffset(years=20), "bestandszugang": pd.Timestamp(STICHTAG),
        })
    stamm = pd.DataFrame(zeilen)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))
    historie = pd.DataFrame([{
        "police_id": 7_000_003, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2023-11-01"),
    }]).astype(dict(STATUS_HISTORIE_SPALTEN))
    ledger_zeilen = [{
        "police_id": int(z["police_id"]), "tarif_generation": "KLV-2017", "ereignis": "ZUG",
        "vertragsjahr": int((pd.Timestamp(STICHTAG).year * 12 + 1 - (z["insurance_start"].year * 12 + z["insurance_start"].month)) // 12),
        "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS", "betrag": 60000.0,
        "betrag_herkunft": "geliefert",
    } for z in zeilen]
    # Die Umbuchung des beitragsfrei uebernommenen Vertrags: Betrag ist die
    # beitragsfreie Summe, vom aufnehmenden Unternehmen aus den
    # Ursprungsparametern gerechnet (gates.bestand_uebernehmen; die
    # Lieferung traegt sie nicht) — gebucht zum Zugangsstichtag im
    # Vertragsjahr des Zugangs, beitragsfrei seit Vertragsjahr 6.
    from rechner_pipeline.kern import ModelPoint, Rechenkern

    gen = next(g for g in load_config(PLV).generationen if g.name == "KLV-2017")
    kern = Rechenkern(ModelPoint(x=35, sex="F", n=25, t=20, sum_insured=60000.0, zw=12,
                                 **gen.generation_fields()))
    ledger_zeilen.append({
        "police_id": 7_000_003, "tarif_generation": "KLV-2017", "ereignis": "PEX",
        "vertragsjahr": 8, "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS",
        "betrag": float(kern.beitragsfreie_summe(6)), "betrag_herkunft": "gerechnet",
    })
    ledger = pd.DataFrame(ledger_zeilen)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    ziel.mkdir(parents=True, exist_ok=True)
    write_portfolio(stamm, ziel / "bestand.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")


def _fall(wurzel: Path, name: str = "probe-uebernahme") -> Path:
    fall = wurzel / name
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "fall.json").write_text(json.dumps({"name": name, "schema_version": 1}), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": "ab" * 32}}), encoding="utf-8")
    _zugangsstand(fall / "abgeleitet" / "bestand")
    return fall


@pytest.fixture()
def eingang(tmp_path):
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    return stand, fall, ziel


def test_eingang_wird_registriert_und_ist_unantastbar(eingang):
    stand, fall, ziel = eingang
    daten = json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))
    assert daten["fall"] == "probe-uebernahme" and daten["stichtag"] == "2026-01-01"
    assert daten["snapshot_sha256"] == "ab" * 32
    assert set(daten["dateien"]) == {"bestand.parquet", "historie.parquet", "ledger.parquet"}
    if os.name != "nt":
        for datei in ziel.iterdir():
            assert (datei.stat().st_mode & 0o777) == 0o444
    with pytest.raises(ueb.UebernahmeError, match="nie ueberschrieben"):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    config = load_config(PLV)
    gelesen = ueb.lies_uebernahmen(stand / "uebernahme", config)
    assert [u.fall for u in gelesen] == ["probe-uebernahme"]
    assert len(gelesen[0].bestand) == 3 and gelesen[0].merkmale is None
    # Mutationsprobe: veraenderte Datei -> Lesen bricht ab.
    pfad = ziel / "ledger.parquet"
    pfad.chmod(0o644)
    ledger = read_portfolio(pfad)
    ledger.loc[ledger.index[0], "betrag"] += 1.0
    write_portfolio(ledger, pfad)
    with pytest.raises(ueb.UebernahmeError, match="registrierten Summe"):
        ueb.lies_uebernahmen(stand / "uebernahme", config)


def test_eingang_prueft_seine_form(tmp_path):
    config = load_config(PLV)
    assert ueb.lies_uebernahmen(tmp_path / "gibt-es-nicht", config) == []
    ohne = tmp_path / "uebernahme" / "ohne"
    ohne.mkdir(parents=True)
    with pytest.raises(ueb.UebernahmeError, match="eingang.json"):
        ueb.lies_uebernahmen(tmp_path / "uebernahme", config)
    assert any("dateien" in f for f in ueb.validate_eingang({"schema_version": 1, "fall": "x", "stichtag": "2026-01-01"}))
    assert any("stichtag" in f for f in ueb.validate_eingang({"schema_version": 1, "fall": "x", "stichtag": "gestern", "dateien": {"bestand.parquet": "0" * 64, "historie.parquet": "0" * 64, "ledger.parquet": "0" * 64}}))
    fall = _fall(tmp_path, "fremd")
    with pytest.raises(ueb.UebernahmeError, match="kein Fall-Arbeitsbereich"):
        ueb.eingang_anlegen(tmp_path / "d", tmp_path / "kein-fall", STICHTAG)
    with pytest.raises(ueb.UebernahmeError, match="fehlen"):
        ueb.eingang_anlegen(tmp_path / "d", fall, STICHTAG, quelle=tmp_path / "leer")
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "2026-01-01"]) == 0
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "2026-01-01"]) == 2
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "kein"]) == 2


def _kleine_config() -> str:
    text = PLV.read_text(encoding="utf-8")
    return re.sub(r"^sample_size = [1-9]\d*$", "sample_size = 6", text, flags=re.M)


def test_uebernahme_faehrt_im_tagesbetrieb_mit(eingang):
    """Der uebernommene Bestand steht ab dem Stichtag im Stand, seine
    gelieferten Buchungen im Ledger und im Tagesjournal, der Fall-Bezug
    im Protokoll — und die Wache P-B1 ist auf dem Gesamtbestand gruen.

    Mutationsprobe: Uebernahme-Eingang ignoriert — dann fehlen die drei
    Vertraege im Stand und die ZUG-Buchungen im Journal."""
    stand, _, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert code == EXIT_OK, zeile
    assert zeile["uebernommen"] is True and zeile["pb1"]["urteil"] == "gruen"
    [u] = zeile["uebernahmen"]
    assert (u["fall"], u["stichtag"], u["vertraege"], u["snapshot_sha256"]) == (
        "probe-uebernahme", "2026-01-01", 3, "ab" * 32)
    # Der Fall des Fixtures hat keinen Snapshot: die Zeichnung ist "nicht
    # ausgewiesen" — benannt, nicht leer (B8).
    assert u["zeichnung"]["rolle"] == "nicht ausgewiesen"
    assert u["zeichnung"]["signatur_verifiziert"] is False
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    assert {7_000_001, 7_000_002, 7_000_003} <= set(gesamt["police_id"])
    assert (gesamt.set_index("police_id").loc[7_000_003, "status_code"]) == "PEX"
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    geliefert = ledger[ledger["betrag_herkunft"] == "geliefert"]
    assert len(geliefert) == 3 and set(geliefert["ereignis"]) == {"ZUG"}
    umbuchung = ledger[(ledger["ereignis"] == "PEX") & (ledger["police_id"] == 7_000_003)]
    assert len(umbuchung) == 1 and umbuchung["status_date"].iloc[0] == pd.Timestamp(STICHTAG)
    journal = read_portfolio(ablage.tagesjournal_pfad)
    ueb_zeilen = journal[journal["herkunft"] == "uebernahme"]
    # Drei gelieferte Zugaenge; die gerechnete Umbuchung ist eine Buchung
    # der Fortschreibungsseite (herkunft fortschreibung), am selben Tag.
    assert len(ueb_zeilen) == 3
    pex_journal = journal[(journal["ereignis"] == "PEX") & (journal["police_id"] == 7_000_003)]
    assert len(pex_journal) == 1 and pex_journal["buchungsdatum"].iloc[0] == pd.Timestamp("2026-01-01")
    assert (ueb_zeilen["buchungsdatum"] == pd.Timestamp("2026-01-01")).all()   # Donnerstag
    assert zeile["bestand"]["uebernommen_in_force"] == 3


def test_teilbestand_bekommt_seinen_eigenen_monatsbericht(eingang):
    """Konzept, Abschnitt 6: Der Monatsbericht weist den uebernommenen
    Teilbestand getrennt aus, solange der Schalter steht.

    Mutationsprobe: Schalter ignoriert — dann fehlt der Teilbestand-Bericht,
    obwohl teilbestand_getrennt = true in der Config steht."""
    stand, _, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 2))
    assert code == EXIT_OK, zeile
    abschluesse = zeile["abschluesse"]
    assert [a["stichtag"] for a in abschluesse] == ["2026-01-01", "2026-02-01"]
    assert "bericht" not in abschluesse[0]            # nur der juengste Abschluss wird gerendert
    assert abschluesse[1]["bericht"] == "bestandsbericht_2026-02-01.html"
    assert abschluesse[1]["teilbestaende"] == [
        {"fall": "probe-uebernahme",
         "bericht": "bestandsbericht_2026-02-01_teilbestand-probe-uebernahme.html"}]
    teil = (ablage.berichte / "bestandsbericht_2026-02-01_teilbestand-probe-uebernahme.html").read_text("utf-8")
    assert "Teilbestand probe-uebernahme (uebernommen) zum 2026-02-01" in teil
    # Die Generationentafel des Berichts zaehlt je Generation: im Teilbestand
    # genau die drei uebernommenen KLV-2017-Vertraege, sonst nichts.
    zeilen = re.findall(r"<td>(KLV-\d{4}|BU-\d{4}|TG2015)</td>.*?<td class=\"num\">(\d+)</td></tr>", teil)
    assert dict(zeilen)["KLV-2017"] == "3"
    assert all(anzahl == "0" for name, anzahl in zeilen if name != "KLV-2017")
    gesamt = (ablage.berichte / "bestandsbericht_2026-02-01.html").read_text("utf-8")
    zeilen_gesamt = re.findall(r"<td>(KLV-\d{4}|BU-\d{4}|TG2015)</td>.*?<td class=\"num\">(\d+)</td></tr>", gesamt)
    assert int(dict(zeilen_gesamt)["KLV-2017"]) > 3
    # Ohne den Schalter kein Teilbestand-Bericht:
    aus = Ablage(stand.parent / "aus")
    import shutil
    shutil.copytree(stand, aus.wurzel)
    for p in (aus.stand, aus.journal, aus.abschluesse, aus.berichte):
        shutil.rmtree(p, ignore_errors=True)
    aus.config_pfad.chmod(0o644)
    aus.config_pfad.write_text(
        _kleine_config().replace("teilbestand_getrennt = true", "teilbestand_getrennt = false"),
        encoding="utf-8")
    code, zeile = tageslauf(aus, dt.date(2026, 2, 2))
    assert code == EXIT_OK and "teilbestaende" not in zeile["abschluesse"][1]
