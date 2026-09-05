"""Tageslauf: Nachholen, Wache P-B1, Monatsabschluss, Protokoll — ueber mehrere Tage.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B4. Die PLV wird Tag
fuer Tag gefuehrt; eine ausgefallene Nacht wird nachgeholt, ein roter
Stand nie uebernommen, ein Monatserster genau einmal festgeschrieben,
und alles davon steht im Protokoll. Der Bestand ist klein (acht
Vertraege je Generation), damit ein Lauf Sekunden dauert — die Mechanik
haengt nicht an der Groesse.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.manifest import lies_manifest
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import (
    EXIT_NACHLAUF,
    EXIT_OK,
    EXIT_USAGE,
    EXIT_WACHE_ROT,
    Ablage,
    TageslaufError,
    gefuehrter_tag,
    lies_protokoll,
    monatserste_in,
    tageslauf,
)
from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"

BETRIEBSBEGINN = dt.date(2026, 1, 1)


def _kleine_config() -> str:
    """Die PLV-Config mit acht Vertraegen je Generation und Betriebsbeginn 2026-01-01."""
    text = PLV.read_text(encoding="utf-8")
    text = re.sub(r"^sample_size = \d+$", "sample_size = 8", text, flags=re.M)
    assert "betriebsbeginn = 2026-01-01" in text
    return text


def _ablage(wurzel: Path) -> Ablage:
    ablage = Ablage(wurzel)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    return ablage


@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    """Drei Laeufe: Erstbefuellung bis 31.1., dann 3.2. (mit Monatswechsel
    und zwei nachgeholten Tagen), dann 4.2."""
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    codes = [
        tageslauf(ablage, dt.date(2026, 1, 31))[0],
        tageslauf(ablage, dt.date(2026, 2, 3))[0],
        tageslauf(ablage, dt.date(2026, 2, 4))[0],
    ]
    return ablage, codes


def test_die_laeufe_sind_gruen_und_fuehren_den_tag(gefuehrt):
    ablage, codes = gefuehrt
    assert codes == [EXIT_OK, EXIT_OK, EXIT_OK]
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 4)
    manifest = lies_manifest(ablage.stand)
    assert manifest["horizont"] == "2026-02-04"
    dateien = {p.name for p in ablage.stand.iterdir()}
    assert {"bestand.parquet", "bestand_gesamt.parquet", "historie.parquet", "ledger.parquet",
            "scheiben.parquet", "zugaenge.parquet", "laufmanifest.json"} <= dateien
    assert not ablage.arbeit.exists()


def test_protokoll_hat_eine_zeile_je_lauf(gefuehrt):
    """Mutationsprobe: Protokollzeile nur bei gruenem Lauf — dann fehlte
    unten der rote Lauf; Nachholen ohne Tagesliste — dann waere die
    Luecke unsichtbar."""
    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    assert [z["heute"] for z in zeilen] == ["2026-01-31", "2026-02-03", "2026-02-04"]
    erst, zweit, dritt = zeilen
    assert erst["gefuehrt_vorher"] is None
    assert erst["nachgeholt"][0] == "2026-01-01" and erst["nachgeholt"][-1] == "2026-01-30"
    assert zweit["gefuehrt_vorher"] == "2026-01-31" and zweit["nachgeholt"] == ["2026-02-01", "2026-02-02"]
    assert dritt["nachgeholt"] == []
    for z in zeilen:
        assert z["uebernommen"] is True
        assert z["pb1"]["urteil"] == "gruen"
        assert z["config_sha256"] and z["kern_version"] and z["manifest_sha256"]
        assert set(z["bestand"]) == {"in_force", "je_produkt", "uebernommen_in_force",
                                     "policiert_beginn_folgt"}
        assert z["bestand"]["uebernommen_in_force"] == 0 and z["uebernahmen"] == []
        assert z["tagesjournal"]["zeilen_gesamt"] >= z["tagesjournal"]["gebucht"]
    assert erst["neugeschaeft_seit_betriebsbeginn"] > 0
    assert erst["tagesjournal"]["neugeschaeft"] > 0
    # Jede Zeile ist fuer sich gueltiges JSON mit sortierten Schluesseln:
    roh = ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines()
    assert len(roh) == 3 and all(json.loads(r) for r in roh)
    assert roh[0] == json.dumps(json.loads(roh[0]), ensure_ascii=False, sort_keys=True)


def test_monatsabschluss_genau_einmal_und_schreibgeschuetzt(gefuehrt):
    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    # Die Erstbefuellung schreibt den Eroeffnungsstand zum Betriebsbeginn:
    assert [a["stichtag"] for a in zeilen[0]["abschluesse"]] == ["2026-01-01"]
    assert [a["stichtag"] for a in zeilen[1]["abschluesse"]] == ["2026-02-01"]
    assert zeilen[1]["abschluesse"][0]["neu"] is True
    assert zeilen[2]["abschluesse"] == []
    assert (ablage.abschluesse / "abschluss_2026-01-01.parquet").is_file()
    pfad = ablage.abschluesse / "abschluss_2026-02-01.parquet"
    assert pfad.is_file()
    if os.name != "nt":
        assert (pfad.stat().st_mode & 0o777) == 0o444
    abschluss = read_portfolio(pfad)
    assert len(abschluss) > 0 and set(abschluss["stichtag"].dt.date) == {dt.date(2026, 2, 1)}
    bericht = ablage.berichte / "bestandsbericht_2026-02-01.html"
    assert bericht.is_file() and "Bestandsbericht PLV zum 2026-02-01" in bericht.read_text("utf-8")


def test_tagesjournal_ist_bijektiv_und_nur_angefuegt(gefuehrt):
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.betrieb.tagesjournal import validate_tagesjournal

    ablage, _ = gefuehrt
    config = load_config(ablage.config_pfad)
    journal = read_portfolio(ablage.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    assert validate_tagesjournal(journal, ledger, config, dt.date(2026, 2, 4), ab_tag=BETRIEBSBEGINN) == []
    assert (journal["buchungsdatum"] >= pd.Timestamp(BETRIEBSBEGINN)).all()
    assert (journal["buchungsdatum"] <= pd.Timestamp("2026-02-04")).all()
    assert journal["buchungsdatum"].is_monotonic_increasing


def test_nachholen_ergibt_denselben_stand_wie_jede_nacht(gefuehrt, tmp_path):
    """Determinismus: ein Lauf direkt bis zum 4.2. liefert byteidentische
    Ausgaben und dasselbe Journal wie die drei Laeufe.

    Mutationsprobe: Seed aus dem Aufruftag oder ein Journal, das nur die
    Buchungen des Lauftags kennt — dann weichen Journal oder Stand ab."""
    ablage, _ = gefuehrt
    direkt = _ablage(tmp_path / "direkt")
    assert tageslauf(direkt, dt.date(2026, 2, 4))[0] == EXIT_OK
    a, b = lies_manifest(ablage.stand), lies_manifest(direkt.stand)
    assert a["ausgaben"] == b["ausgaben"]
    j_a = read_portfolio(ablage.tagesjournal_pfad)
    j_b = read_portfolio(direkt.tagesjournal_pfad)
    pd.testing.assert_frame_equal(j_a, j_b)
    assert (ablage.abschluesse / "abschluss_2026-02-01.parquet").read_bytes() == \
        (direkt.abschluesse / "abschluss_2026-02-01.parquet").read_bytes()
    zeile = lies_protokoll(direkt.protokoll_pfad)[0]
    assert zeile["nachgeholt"][0] == "2026-01-01" and len(zeile["nachgeholt"]) == 34
    assert [x["stichtag"] for x in zeile["abschluesse"]] == ["2026-01-01", "2026-02-01"]
    assert (ablage.abschluesse / "abschluss_2026-01-01.parquet").read_bytes() == \
        (direkt.abschluesse / "abschluss_2026-01-01.parquet").read_bytes()


def test_ein_tag_wird_nicht_zweimal_und_nicht_rueckwaerts_gefuehrt(gefuehrt):
    ablage, _ = gefuehrt
    with pytest.raises(TageslaufError, match="nicht danach"):
        tageslauf(ablage, dt.date(2026, 2, 4))
    with pytest.raises(TageslaufError, match="nicht danach"):
        tageslauf(ablage, dt.date(2026, 1, 15))
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 4)
    assert len(lies_protokoll(ablage.protokoll_pfad)) == 3


def test_rote_wache_uebernimmt_den_stand_nicht(gefuehrt, tmp_path):
    """Mutationsprobe: Wache entfernt oder Stand vor der Wache uebernommen
    — dann fuehrte der Stand den 5.2. mit einem Bestand ausserhalb der
    Plausibilitaetsbaender, und der Exit waere 0."""
    quelle, _ = gefuehrt
    ablage = Ablage(tmp_path / "rot")
    shutil.copytree(quelle.wurzel, ablage.wurzel)
    text = ablage.config_pfad.read_text(encoding="utf-8")
    text = text.replace("entry_age = [18, 64]", "entry_age = [18, 19]", 1)
    ablage.config_pfad.write_text(text, encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 5))
    assert code == EXIT_WACHE_ROT
    assert zeile["uebernommen"] is False and zeile["pb1"]["urteil"] == "rot"
    assert any("entry_age" in b for b in zeile["pb1"]["befunde"])
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 4)          # der gestrige bleibt
    assert lies_manifest(ablage.stand)["horizont"] == "2026-02-04"
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    assert zeilen[-1]["heute"] == "2026-02-05" and zeilen[-1]["uebernommen"] is False
    # Das Journal ist unveraendert geblieben:
    pd.testing.assert_frame_equal(
        read_portfolio(ablage.tagesjournal_pfad), read_portfolio(quelle.tagesjournal_pfad))
    # Nach der Korrektur laeuft derselbe Tag gruen durch:
    ablage.config_pfad.write_text(quelle.config_pfad.read_text(encoding="utf-8"), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 5))
    assert code == EXIT_OK and zeile["gefuehrt_vorher"] == "2026-02-04"
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 5)


def test_stand_und_protokoll_muessen_zusammenpassen(gefuehrt, tmp_path):
    quelle, _ = gefuehrt
    ablage = Ablage(tmp_path / "kaputt")
    shutil.copytree(quelle.wurzel, ablage.wurzel)
    zeilen = ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines()
    ablage.protokoll_pfad.write_text("\n".join(zeilen[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(TageslaufError, match="passen nicht zusammen"):
        tageslauf(ablage, dt.date(2026, 2, 5))
    ablage.protokoll_pfad.unlink()
    with pytest.raises(TageslaufError, match="passen nicht zusammen"):
        gefuehrter_tag(ablage)
    (ablage.stand / "laufmanifest.json").unlink()
    with pytest.raises(TageslaufError, match="kein gefuehrter Stand"):
        gefuehrter_tag(ablage)


def test_erstbefuellung_verlangt_config_und_betriebsbeginn(tmp_path):
    ablage = Ablage(tmp_path / "leer")
    with pytest.raises(TageslaufError, match="keine Config"):
        tageslauf(ablage, dt.date(2026, 1, 5))
    ablage = _ablage(tmp_path / "ohne")
    text = ablage.config_pfad.read_text(encoding="utf-8").replace("betriebsbeginn = 2026-01-01\n", "")
    ablage.config_pfad.write_text(text, encoding="utf-8")
    with pytest.raises(TageslaufError, match="betriebsbeginn"):
        tageslauf(ablage, dt.date(2026, 1, 5))
    ablage = _ablage(tmp_path / "frueh")
    with pytest.raises(TageslaufError, match="vor dem Betriebsbeginn"):
        tageslauf(ablage, dt.date(2025, 12, 31))


def test_cli(gefuehrt, tmp_path, capsys):
    ablage = _ablage(tmp_path / "cli")
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-06",
                    "--image-digest", "sha256:abc"]) == EXIT_OK
    assert "2026-01-06 gefuehrt" in capsys.readouterr().err
    assert lies_protokoll(ablage.protokoll_pfad)[0]["image_digest"] == "sha256:abc"
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "kein-datum"]) == EXIT_USAGE
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-06"]) == EXIT_USAGE
    assert "nicht danach" in capsys.readouterr().err


def test_monatserste_in():
    assert monatserste_in(dt.date(2026, 1, 31), dt.date(2026, 2, 3)) == [dt.date(2026, 2, 1)]
    assert monatserste_in(dt.date(2026, 1, 31), dt.date(2026, 4, 1)) == [
        dt.date(2026, 2, 1), dt.date(2026, 3, 1), dt.date(2026, 4, 1)]
    assert monatserste_in(dt.date(2026, 2, 1), dt.date(2026, 2, 28)) == []
    assert monatserste_in(dt.date(2025, 12, 31), dt.date(2026, 1, 1)) == [dt.date(2026, 1, 1)]
