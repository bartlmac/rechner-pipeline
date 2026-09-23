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


def _kleine_config(faktor: float = 1.0) -> str:
    """Die PLV-Config als schnelle Testwelt: Betriebsbeginn am 1.1.2026.

    Die echte PLV beginnt am 1.7.1994 und baut ihren Bestand Tag fuer Tag
    auf; das sind zweiunddreissig Jahre Tagesstrom. Fuer die Tests beginnt
    das Unternehmen deshalb erst 2026 — leer, wie jedes Unternehmen an
    seinem ersten Tag (ADR-020): der Tagesstrom traegt nur die Tage des
    Tests, und der Eroeffnungsabschluss zum 1.1.2026 ist leer. Die lange
    Geschichte prueft test_betrieb_lange_geschichte.

    ``faktor`` vervielfacht die Jahresziele — fuer Tests, die genug
    Vertraege brauchen, damit seltene Ereignisse im Fenster vorkommen.
    """
    text = PLV.read_text(encoding="utf-8")
    if faktor != 1.0:
        text = re.sub(r"^neuzugang_pro_jahr = (\d+)$",
                      lambda m: f"neuzugang_pro_jahr = {max(1, round(int(m.group(1)) * faktor))}",
                      text, flags=re.M)
    text = re.sub(r"^betriebsbeginn = .*$", "betriebsbeginn = 2026-01-01", text, flags=re.M)
    assert "betriebsbeginn = 2026-01-01" in text
    return text


def _voll(config, heute: dt.date, ab: dt.date = BETRIEBSBEGINN, basis=None):
    """Dieselbe Welt unabhaengig vom Tageslauf gerechnet: mit ``basis``
    beginnen (Standard: leer), den Tagesstrom ab ``ab`` einspielen, bis
    ``heute`` fortschreiben — die volle Wirkungshistorie ohne Buchungstage
    und Stichtagssicht. ``basis`` traegt eine uebernommene (umnummerierte)
    Startpopulation ein, deren Tode das eigene Geschaeft nicht liefert."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.betrieb.neugeschaeft import neugeschaeft_zwischen
    from rechner_pipeline.models.bestand import leerer_stamm

    return fortschreiben(leerer_stamm() if basis is None else basis, config, heute,
                         zugaenge=neugeschaeft_zwischen(config, ab, heute))


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
        assert z["image_digest"] == "nicht erfasst"
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


def test_derselbe_tag_noch_einmal_ist_ein_benannter_noop(gefuehrt):
    """Der Lauf ist idempotent: Der bereits gefuehrte Tag laeuft mit Exit 0
    durch, ohne Protokollzeile, Stand und Manifest bytegleich. Sonst faerbt
    eine Erstbefuellung am Tag des ersten Timers die erste Nacht rot.
    Mutationsprobe: rueckwaerts darf nicht mit durchrutschen."""
    ablage, _ = gefuehrt
    manifest_vorher = (ablage.stand / "laufmanifest.json").read_bytes()
    protokoll_vorher = ablage.protokoll_pfad.read_bytes()
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    assert code == EXIT_OK and zeile == {"heute": "2026-02-04", "bereits_gefuehrt": True}
    assert (ablage.stand / "laufmanifest.json").read_bytes() == manifest_vorher
    assert ablage.protokoll_pfad.read_bytes() == protokoll_vorher
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 4)
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-02-04"]) == EXIT_OK
    assert ablage.protokoll_pfad.read_bytes() == protokoll_vorher
    # Rueckwaerts bleibt ein Fehler (Exit 2 ueber main):
    with pytest.raises(TageslaufError, match="rueckwaerts"):
        tageslauf(ablage, dt.date(2026, 1, 15))
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-15"]) == EXIT_USAGE
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
    erste = lies_protokoll(ablage.protokoll_pfad)[0]
    assert erste["image_digest"] == "sha256:abc"
    # Was die Umgebung nicht liefert, ist ein benannter Zustand, kein leeres Feld:
    assert erste["image_revision"] == "nicht erfasst" and erste["image_tag"] == "nicht erfasst"
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "kein-datum"]) == EXIT_USAGE
    # Derselbe Tag noch einmal: benannter No-op, keine zweite Protokollzeile.
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-06"]) == EXIT_OK
    assert "bereits gefuehrt, nichts zu tun" in capsys.readouterr().err
    assert len(lies_protokoll(ablage.protokoll_pfad)) == 1
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-01-05"]) == EXIT_USAGE
    assert "rueckwaerts" in capsys.readouterr().err


def test_monatserste_in():
    assert monatserste_in(dt.date(2026, 1, 31), dt.date(2026, 2, 3)) == [dt.date(2026, 2, 1)]
    assert monatserste_in(dt.date(2026, 1, 31), dt.date(2026, 4, 1)) == [
        dt.date(2026, 2, 1), dt.date(2026, 3, 1), dt.date(2026, 4, 1)]
    assert monatserste_in(dt.date(2026, 2, 1), dt.date(2026, 2, 28)) == []
    assert monatserste_in(dt.date(2025, 12, 31), dt.date(2026, 1, 1)) == [dt.date(2026, 1, 1)]


# --------------------------------------------------------------------------- #
# Review T22-03: Der Standwechsel ist eine Transaktion
# --------------------------------------------------------------------------- #

def test_der_stand_ist_ein_symlink_auf_ein_versioniertes_verzeichnis(gefuehrt):
    """Vorher zwei Renames mit einem Moment ohne stand/; jetzt zeigt der
    Symlink immer auf einen vollstaendigen Stand, und nur EIN versioniertes
    Verzeichnis lebt."""
    ablage, _ = gefuehrt
    assert ablage.stand.is_symlink()
    ziel = ablage.stand.resolve()
    assert ziel.name.startswith("stand-") and ziel.is_dir()
    versioniert = sorted(p.name for p in ablage.wurzel.glob("stand-*") if p.is_dir())
    assert versioniert == [ziel.name]
    manifest = lies_manifest(ablage.stand)
    assert manifest["horizont"] == "2026-02-04"
    assert not (ablage.wurzel / "stand.alt").exists()


def test_ein_gescheiterter_tausch_laesst_den_gestrigen_stand_stehen(tmp_path, monkeypatch):
    """Fehlerinjektion des Reviews (stand_exists False, gefuehrter_tag None):
    scheitert der Tausch, bleibt der alte Stand der gefuehrte, der Lauf ist
    rot mit Protokollzeile. Mutationsprobe: os.replace durch die alten zwei
    Renames ersetzen -> der Stand ist weg -> rot."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    alt = ablage.stand.resolve()

    def _kaputt(*_a, **_k):
        raise OSError("Platte weg")

    monkeypatch.setattr(tl.os, "replace", _kaputt)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    monkeypatch.undo()
    assert code != EXIT_OK and "OSError" in zeile["fehler"]
    assert zeile["uebernommen"] is False
    assert ablage.stand.is_symlink() and ablage.stand.resolve() == alt
    assert gefuehrter_tag(ablage) == dt.date(2026, 1, 31)
    assert lies_protokoll(ablage.protokoll_pfad)[-1]["heute"] == "2026-02-03"
    # Der naechste Lauf raeumt den Rest auf und fuehrt den Tag. Der
    # unmittelbare Vorgaenger bleibt dabei liegen — er ist die Ruecknahme
    # des Standwechsels (T24-01 b) — und geht mit dem Lauf danach.
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 3)
    assert tageslauf(ablage, dt.date(2026, 2, 4))[0] == EXIT_OK
    assert tageslauf(ablage, dt.date(2026, 2, 5))[0] == EXIT_OK
    # Der stabile Zustand ist "aktueller Stand plus EIN Vorgaenger": Jeder
    # Lauf laesst seinen Vorgaenger liegen, der naechste raeumt den davor
    # ab. Das ist der Preis der Umkehrbarkeit, und er ist begrenzt.
    uebrig = sorted(p.name for p in ablage.wurzel.glob("stand-*") if p.is_dir())
    assert ablage.stand.resolve().name in uebrig
    assert len(uebrig) <= 2, uebrig


def test_zwei_laeufe_auf_derselben_ablage_gibt_es_nicht(tmp_path):
    """Kein Prozess-Lock (Review): zwei gleichzeitige Laeufe teilten
    stand.neu, Journal und Protokoll. Mutationsprobe: flock entfernen -> rot."""
    import fcntl

    ablage = _ablage(tmp_path / "plv")
    ablage.wurzel.mkdir(parents=True, exist_ok=True)
    with open(ablage.sperre, "a+") as fremd:
        fcntl.flock(fremd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(TageslaufError, match="Sperre"):
            tageslauf(ablage, dt.date(2026, 1, 31))
        assert not ablage.stand.exists()
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK


def test_ein_stand_der_erstfassung_wird_in_die_symlink_form_ueberfuehrt(tmp_path):
    """Die Laufzeit unter ~/apps/plv hat noch ein echtes Verzeichnis stand/;
    der naechste Lauf fuehrt es in die Symlink-Form ueber, ohne den Tag zu
    verlieren."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    # Erstfassung nachstellen: Symlink durch das echte Verzeichnis ersetzen.
    ziel = ablage.stand.resolve()
    ablage.stand.unlink()
    os.rename(ziel, ablage.stand)
    assert ablage.stand.is_dir() and not ablage.stand.is_symlink()
    assert gefuehrter_tag(ablage) == dt.date(2026, 1, 31)
    assert tageslauf(ablage, dt.date(2026, 2, 1))[0] == EXIT_OK
    assert ablage.stand.is_symlink() and gefuehrter_tag(ablage) == dt.date(2026, 2, 1)
    # Die beiseitegeschobene Erstfassung bleibt bis zum NAECHSTEN Lauf
    # liegen: Seit dem Write-Ahead-Rahmen (T24-01 b) ist der Standwechsel
    # umkehrbar, und dazu muss es etwas geben, worauf man zurueckzeigen
    # kann. Aufgeraeumt wird sie, sobald der Symlink steht.
    assert (ablage.wurzel / "stand-erstfassung").exists()
    assert tageslauf(ablage, dt.date(2026, 2, 2))[0] == EXIT_OK
    assert not (ablage.wurzel / "stand-erstfassung").exists()


def test_verwaiste_standverzeichnisse_und_linkreste_werden_vor_dem_lauf_entfernt(tmp_path):
    """Ein Rest eines abgebrochenen Tauschs (fremdes stand-*-Verzeichnis,
    stand.link) darf nicht liegen bleiben. Mutationsprobe:
    _verwaiste_staende_entfernen zu pass -> rot."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    verwaist = ablage.wurzel / "stand-deadbeefdeadbeef"
    verwaist.mkdir()
    (verwaist / "rest.txt").write_text("x", encoding="utf-8")
    os.symlink(verwaist.name, ablage.wurzel / tl.STAND_LINK_TMP)
    aktuell = ablage.stand.resolve()
    assert tageslauf(ablage, dt.date(2026, 2, 1))[0] == EXIT_OK
    assert not verwaist.exists() and not (ablage.wurzel / tl.STAND_LINK_TMP).exists()
    assert ablage.stand.resolve() != aktuell
    # Der unmittelbare Vorgaenger ist noch da (umkehrbarer Standwechsel,
    # T24-01 b) und geht mit dem naechsten Lauf.
    assert aktuell.exists()
    assert tageslauf(ablage, dt.date(2026, 2, 2))[0] == EXIT_OK
    assert not aktuell.exists()


# --------------------------------------------------------------------------- #
# Review T22-05: Das Protokoll ist ein Nachweis, keine Behauptung
# --------------------------------------------------------------------------- #

def test_jede_protokollzeile_nennt_den_hash_ihrer_vorgaengerin(gefuehrt):
    ablage, _ = gefuehrt
    roh = [z for z in ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines() if z.strip()]
    zeilen = [json.loads(z) for z in roh]
    assert zeilen[0]["schema_version"] == 2 and zeilen[0]["vorgaenger_sha256"] == ""
    for vorher, jetzt in zip(roh, zeilen[1:]):
        assert jetzt["vorgaenger_sha256"] == tl._zeilen_hash(vorher)


def test_eine_entfernte_mittlere_zeile_bricht_die_kette(tmp_path):
    """Nachweis des Reviews: mittlere von drei Zeilen entfernt, letzter Tag
    weiter akzeptiert. Mutationsprobe: die Kettenpruefung in lies_protokoll
    entfernen -> rot."""
    ablage = _ablage(tmp_path / "plv")
    for tag in (dt.date(2026, 1, 31), dt.date(2026, 2, 3), dt.date(2026, 2, 4)):
        assert tageslauf(ablage, tag)[0] == EXIT_OK
    zeilen = ablage.protokoll_pfad.read_text(encoding="utf-8").splitlines()
    assert len(zeilen) == 3
    ablage.protokoll_pfad.write_text("\n".join([zeilen[0], zeilen[2]]) + "\n", encoding="utf-8")
    with pytest.raises(TageslaufError, match="Protokollkette"):
        lies_protokoll(ablage.protokoll_pfad)
    with pytest.raises(TageslaufError, match="Protokollkette"):
        gefuehrter_tag(ablage)
    with pytest.raises(TageslaufError):
        tageslauf(ablage, dt.date(2026, 2, 5))


def test_ein_veraendertes_journal_passt_nicht_mehr_zum_protokoll(tmp_path):
    """Nachweis des Reviews: Betragsaenderung im Journal, claimed_hash_matches
    False, aber weiter gruen. Mutationsprobe: den Journal-Hash-Vergleich in
    pruefe_nachweis entfernen -> rot."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    journal = read_portfolio(ablage.tagesjournal_pfad)
    assert len(journal) > 0
    journal.loc[journal.index[0], "betrag"] = float(journal.loc[journal.index[0], "betrag"]) + 1.0
    from rechner_pipeline.bestand.parquet_io import write_portfolio
    write_portfolio(journal, ablage.tagesjournal_pfad)
    with pytest.raises(TageslaufError, match="Journal"):
        gefuehrter_tag(ablage)


def test_ein_fremder_stand_passt_nicht_zum_protokoll(tmp_path):
    """Manifest-Hash der letzten gruenen Zeile gegen den Stand auf der Platte.
    Mutationsprobe: den Manifest-Vergleich in pruefe_nachweis entfernen -> rot."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    manifest = ablage.stand / "laufmanifest.json"
    daten = json.loads(manifest.read_text(encoding="utf-8"))
    daten["bemerkung"] = "angefasst"
    manifest.write_text(json.dumps(daten, indent=2), encoding="utf-8")
    with pytest.raises(TageslaufError):
        gefuehrter_tag(ablage)


# --------------------------------------------------------------------------- #
# Review T22-04: Stand, Seite und Journal sagen dasselbe
# --------------------------------------------------------------------------- #

def test_der_stand_enthaelt_nur_gebuchte_ereignisse(gefuehrt):
    """Nachweis des Reviews: bestand_gesamt_status TOD, tod_im_tagesjournal
    False. Jetzt ist jede Ledger-Zeile des Stands bis heute gebucht, das
    Journal ist die Menge dieser Zeilen seit Betriebsbeginn, und kein
    Vertrag traegt einen Zustand, dessen Buchung noch aussteht.
    Mutationsprobe: gebuchte_sicht in _stand_bauen entfernen -> rot."""
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.betrieb.tagesjournal import mit_buchungstagen

    ablage, _ = gefuehrt
    config = load_config(ablage.config_pfad)
    heute = gefuehrter_tag(ablage)
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    sicht = mit_buchungstagen(config, ledger)
    assert (sicht["buchungsdatum"] <= pd.Timestamp(heute)).all()
    journal = read_portfolio(ablage.tagesjournal_pfad)
    seit_beginn = sicht[sicht["buchungsdatum"] >= pd.Timestamp(BETRIEBSBEGINN)]
    assert len(journal) == len(seit_beginn)
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    tod = gesamt[gesamt["status_code"] == "TOD"]
    gebuchte_tode = set(ledger.loc[ledger["ereignis"] == "TOD", "police_id"])
    assert set(tod["police_id"]) <= gebuchte_tode


def test_ein_verzoegert_gemeldeter_tod_erscheint_erst_am_buchungstag(tmp_path, monkeypatch):
    """Meldeverzug auf 400 Tage gesetzt: Kein seit Betriebsbeginn
    eingetretener Tod ist bis heute gebucht — und keiner steht im Stand,
    obwohl die volle Wirkungshistorie welche kennt.

    Die Sterblichkeit tragen gealterte uebernommene Vertraege: Eine junge
    Firma, die 2026 leer beginnt (ADR-020), stirbt im Fenster nicht (siehe
    test_ein_abschluss_ist_dieselbe_datei). Frueher half hier eine groessere
    Stichprobe des jungen Geschaefts und ein Skip, wenn doch keiner starb —
    ein Detektor, der gruen sein konnte, ohne je seinen Gegenstand gesehen zu
    haben. Jetzt garantiert die Uebernahme ihn.
    """
    from rechner_pipeline.betrieb import tagesjournal as tj
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.models.bestand import STAMM_NAMES

    monkeypatch.setattr(tj, "meldeverzug_tage", lambda config, police_id, jahr: 400)
    ablage = _ablage(tmp_path / "plv")
    eingang = _gealterte_uebernahme(ablage, tmp_path / "plv-fall")
    heute = dt.date(2026, 9, 30)
    assert tageslauf(ablage, heute)[0] == EXIT_OK
    config = load_config(ablage.config_pfad)

    # Die volle Wirkungshistorie: die uebernommene (umnummerierte) Basis plus
    # eigenes Geschaeft, ganz ohne Buchungsschnitt. fortschreiben kennt die
    # Tode nach ihrem Wirkungstag; der Meldeverzug wirkt erst beim Buchen.
    basis = read_portfolio(eingang / "bestand.parquet", expected_columns=STAMM_NAMES)
    voll = _voll(config, heute, basis=basis)
    tode_voll = voll.ledger[(voll.ledger["ereignis"] == "TOD")
                            & (voll.ledger["status_date"] > pd.Timestamp(BETRIEBSBEGINN))]
    # Zusicherung, kein Skip: Ohne einen eingetretenen Tod pruefte der Test
    # nichts (der Detektor ohne Treffer). Eine Testwelt ohne den Gegenstand
    # ist ein Fehler der Testwelt, kein Grund zu ueberspringen.
    assert len(tode_voll) > 0, (
        "Testwelt ohne eingetretenen Tod seit Betriebsbeginn — der Test kann "
        "seinen Gegenstand nicht sehen")

    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    tode_stand = ledger[(ledger["ereignis"] == "TOD")
                        & (ledger["status_date"] > pd.Timestamp(BETRIEBSBEGINN))]
    assert len(tode_stand) == 0
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    for pid in tode_voll["police_id"]:
        assert gesamt.loc[gesamt["police_id"] == pid, "status_code"].iloc[0] != "TOD"


def _gealterter_zugangsstand(ziel: Path, n: int = 400) -> None:
    """Der bewaehrte Zugangsstand (drei Fremdvertraege, einer beitragsfrei)
    plus ``n`` gealterte POL-Vertraege — die Population, aus der im kurzen
    Testfenster ueberhaupt Todesfaelle entstehen.

    Eine junge Firma, die 2026 leer beginnt (ADR-020), hat in sechs Monaten
    keine (gemessen: 0 bei 4275 Vertraegen); der Gegenstand dieses Tests — ein
    spaet gebuchter Tod ueber eine Monatsgrenze — braucht Alter, und Alter
    kommt in den Betrieb nur ueber eine Uebernahme. Gemessen liefern die
    gealterten Zeilen zehn Tode mit Wirkung Februar bis Mai und Buchung
    (Meldeverzug 40) im Folgemonat, alle noch vor dem 30.6. — genau das, was
    der Stichtagsschnitt in ``_stichtagssicht`` je Abschluss ausblenden muss.

    Die PEX-Historienzeile aus ``_zugangsstand`` ist kein Beiwerk: Ohne sie
    laesst ``gebuchte_sicht`` den Eroeffnungsabschluss zum 1.1. mit LEERER
    Historie zurueck, und die Auswertung verweigert eine Stammtabelle mit
    spaeteren Folgezustaenden (den Toden) ohne Journal (ADR-011). Ein echter
    uebernommener Bestand traegt seine Statushistorie ohnehin."""
    import pandas as pd
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from rechner_pipeline.models.bestand import (
        LEDGER_NAMES, LEDGER_SPALTEN, STAMM_NAMES, STAMM_SPALTEN)
    from tests.test_betrieb_uebernahme import _zugangsstand

    _zugangsstand(ziel)
    stamm = read_portfolio(ziel / "bestand.parquet", expected_columns=STAMM_NAMES)
    ledger = read_portfolio(ziel / "ledger.parquet", expected_columns=LEDGER_NAMES)

    zeilen, zug = [], []
    for k in range(n):
        # Alt genug fuer Sterblichkeit (Alter heute ~77-83), aber Eintritts-
        # alter im Sanity-Band [18, 64] von P-B1 und Restlaufzeit weit ueber
        # das Fenster hinaus (Ende ab 2037), damit im Fenster Tode fallen und
        # keine Ablaeufe. Beginnmonat variiert ueber alle zwoelf, damit die
        # Tode sich ueber die Monate verteilen (Wirkung Feb-Mai).
        monat = (k % 12) + 1
        alter = 60 + (k % 5)                       # 60..64, im Band [18, 64]
        b = pd.Timestamp(f"20{7 + (k % 3):02d}-{monat:02d}-01")   # 2007..2009
        zeilen.append({
            "police_id": 7_000_010 + k, "tarif_generation": "KLV-2017", "produkt": "klv",
            "status_id": 1, "status_code": "POL", "status_date": b,
            "sex": "F" if k % 2 else "M", "date_of_birth": b - pd.DateOffset(years=alter),
            "entry_age": alter, "duration": 30, "premium_duration": 20,
            "sum_insured": 50000.0, "bu_rente": 0.0, "zahlweise": 12,
            "insurance_start": b, "insurance_end": b + pd.DateOffset(years=30),
            "payment_end": b + pd.DateOffset(years=20),
            "bestandszugang": pd.Timestamp(BETRIEBSBEGINN)})
        zug.append({
            "police_id": 7_000_010 + k, "tarif_generation": "KLV-2017", "ereignis": "ZUG",
            "vertragsjahr": int((BETRIEBSBEGINN.year * 12 + 1
                                 - (b.year * 12 + b.month)) // 12),
            "status_date": pd.Timestamp(BETRIEBSBEGINN), "betrag_art": "VS",
            "betrag": 50000.0, "betrag_herkunft": "geliefert"})
    aged = pd.DataFrame(zeilen)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))
    aged_zug = pd.DataFrame(zug)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    write_portfolio(pd.concat([stamm, aged], ignore_index=True), ziel / "bestand.parquet")
    write_portfolio(pd.concat([ledger, aged_zug], ignore_index=True), ziel / "ledger.parquet")


def _gealterte_uebernahme(ablage: Ablage, fall_wurzel: Path,
                          name: str = "gealterte-uebernahme") -> Path:
    """Einen Fall mit gealtertem Zugangsstand als Eingang der Ablage
    registrieren — mit echtem P-B1-Ledger und A-M4-Snapshot wie ein
    Migrationsfall. Die Belegbauteile (``_pb1_ledger``, ``am4_snapshot``)
    sind populationsagnostisch und kommen aus ``test_betrieb_uebernahme``;
    der Eingang ist deterministisch, zwei Aufrufe liefern Byte fuer Byte
    dasselbe (leeres Nummernband -> gleiche Zielnummern). Rueckgabe: das
    Eingangsverzeichnis mit den umnummerierten Tabellen des Zielsystems."""
    from rechner_pipeline.betrieb import uebernahme as ueb
    from tests.test_betrieb_uebernahme import _pb1_ledger, am4_snapshot

    fall = fall_wurzel / name
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "entscheide").mkdir()
    (fall / "fall.json").write_text(
        json.dumps({"name": name, "schema_version": 1}), encoding="utf-8")
    _gealterter_zugangsstand(fall / "abgeleitet" / "bestand")
    ledger_sha = _pb1_ledger(fall)
    daten = am4_snapshot(name, pb1_ledger_sha=ledger_sha)
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")
    return ueb.eingang_anlegen(ablage.wurzel, fall, BETRIEBSBEGINN)


def test_ein_abschluss_ist_dieselbe_datei_ob_am_stichtag_oder_nachgeholt(tmp_path, monkeypatch):
    """T24-02: Der Monatsabschluss ist der Stand, den das Unternehmen an
    seinem Stichtag hatte — nicht der, den es spaeter rueckblickend fuer
    diesen Stichtag ausrechnet.

    Der Lauf baut seine Tabellen mit der gebuchten Sicht von heute. Die
    Abschluss-Schleife schrieb damit jeden Stichtag: Wirkungsfilter auf dem
    Stichtag, Buchungsschnitt auf dem Lauftag. Ein Todesfall mit Wirkung im
    Januar und Buchung im Maerz fehlte dadurch schon im Februar-Abschluss,
    obwohl das Unternehmen im Februar nichts von ihm wusste. Beide Wege
    waren gruen und schrieben dieselbe 0444-Datei mit anderem Inhalt.

    Gemessen wird das Versprechen aus deploy/plv/README und Fachkonzept
    Abschnitt 7: derselbe Stand, als haette der Lauf jede Nacht
    stattgefunden. Gegenprobe: Ohne den Stichtagsschnitt in
    ``_stichtagssicht`` weichen genau die Abschluesse ab, in deren Monat
    eine Buchung von jenseits der Monatsgrenze faellt.
    """
    from rechner_pipeline.betrieb import tagesjournal as tj

    # Vierzig Tage Meldeverzug ueberschreiten jede Monatsgrenze — der
    # Zufall der Verteilung wird durch eine feste Zahl ersetzt, damit der
    # Test nicht manchmal nichts prueft.
    monkeypatch.setattr(tj, "meldeverzug_tage", lambda config, police_id, jahr: 40)

    def welt(name: str) -> Ablage:
        # Leer beginnende PLV (ADR-020) plus eine Uebernahme gealterter
        # Fremdvertraege: aus ihnen — nicht aus dem jungen Neugeschaeft von
        # 2026 — entstehen die spaet gebuchten Tode ueber die Monatsgrenze,
        # den Gegenstand dieses Tests. Der Eingang ist deterministisch, beide
        # Welten sehen ihn Byte fuer Byte gleich; die einzige Variable bleibt
        # die Fahrweise (nachgeholt vs. jede Nacht).
        ablage = _ablage(tmp_path / name)
        _gealterte_uebernahme(ablage, tmp_path / f"{name}-fall")
        return ablage

    ende = dt.date(2026, 6, 30)
    nachgeholt = welt("nachgeholt")
    assert tageslauf(nachgeholt, ende)[0] == EXIT_OK

    jede_nacht = welt("jede_nacht")
    for tag in (dt.date(2026, 2, 1), dt.date(2026, 3, 1), dt.date(2026, 4, 1),
                dt.date(2026, 5, 1), dt.date(2026, 6, 1), ende):
        assert tageslauf(jede_nacht, tag)[0] == EXIT_OK

    # Vorbedingung: Ohne eine Buchung jenseits der Monatsgrenze pruefte der
    # Test nichts. Das ist eine Zusicherung, kein Skip — eine Testwelt ohne
    # den Gegenstand ist ein Fehler der Testwelt.
    journal = read_portfolio(nachgeholt.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
    ueber_die_grenze = journal[
        journal["buchungsdatum"].dt.to_period("M") > journal["status_date"].dt.to_period("M")]
    assert len(ueber_die_grenze) > 0, (
        "Testwelt ohne Buchung jenseits der Monatsgrenze — der Test kann "
        "seinen Gegenstand nicht sehen")

    dateien = sorted(p.name for p in nachgeholt.abschluesse.glob("abschluss_*.parquet"))
    assert dateien == sorted(p.name for p in jede_nacht.abschluesse.glob("abschluss_*.parquet"))
    assert len(dateien) == 6
    for name in dateien:
        assert (nachgeholt.abschluesse / name).read_bytes() == \
            (jede_nacht.abschluesse / name).read_bytes(), (
                f"{name} haengt davon ab, wann gerechnet wurde")


def test_der_buchungsschnitt_komponiert(tmp_path):
    """Die Annahme, auf der ``_stichtagssicht`` steht: Zweimal schneiden
    (erst heute, dann Stichtag) ist dasselbe wie einmal auf den Stichtag.

    Deshalb muss der Lauf die ungefilterte Wirkungshistorie nicht
    mitfuehren — er schneidet die Tabellen, die er ohnehin hat, ein
    zweites Mal. Traegt ``buchungstag`` je Zeile, gilt das; wuerde er
    jemals von den uebrigen Zeilen der Tabelle abhaengen (eine laufende
    Nummer, ein Kontingent je Tag), faellt dieser Test und mit ihm die
    Vereinfachung.
    """
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.betrieb.tagesjournal import gebuchte_sicht

    pfad = tmp_path / "bestand.toml"
    pfad.write_text(_kleine_config(faktor=5), encoding="utf-8")
    config = load_config(pfad)
    heute = dt.date(2026, 6, 30)
    voll = _voll(config, heute)

    for stichtag in (dt.date(2026, 2, 1), dt.date(2026, 4, 1), heute):
        einmal = gebuchte_sicht(config, voll.historie, voll.ledger, voll.scheiben,
                                stichtag, ab_tag=BETRIEBSBEGINN)
        zwischen = gebuchte_sicht(config, voll.historie, voll.ledger, voll.scheiben,
                                  heute, ab_tag=BETRIEBSBEGINN)
        zweimal = gebuchte_sicht(config, *zwischen, stichtag, ab_tag=BETRIEBSBEGINN)
        for a, b, rolle in zip(einmal, zweimal, ("historie", "ledger", "scheiben")):
            pd.testing.assert_frame_equal(
                a.reset_index(drop=True), b.reset_index(drop=True),
                obj=f"{rolle} zum {stichtag.isoformat()}")


def test_die_bewertung_am_stichtag_haengt_nicht_am_stand_des_stammes(gefuehrt):
    """Die zweite Annahme von ``_stichtagssicht``: Der Stichtagsschnitt
    laesst ``portfolio`` unberuehrt, weil die Bewertung ihren Zustand aus
    dem Journal herleitet (``journalsicht``) und der Stamm nur Stammdaten
    beisteuert.

    Wuerde die Bewertung je auf den fortgeschriebenen Zustand des Stammes
    zurueckfallen, traegt der Abschluss wieder das Wissen des Lauftags —
    lautlos, denn beide Wege liefern eine vollstaendige Tabelle. Dieser
    Test faellt dann, bevor es jemand an den Zahlen merkt.
    """
    from rechner_pipeline.bestand.auswertung import einzelwerte_am
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.fuehrung import fuehre_fort
    from rechner_pipeline.betrieb.tagesjournal import gebuchte_sicht

    ablage, _ = gefuehrt
    config = load_config(ablage.config_pfad)
    lies = lambda name: read_portfolio(ablage.stand / f"{name}.parquet")
    port, hist, led, sch = (lies("bestand_gesamt"), lies("historie"),
                            lies("ledger"), lies("scheiben"))
    stichtag = dt.date(2026, 2, 1)
    h_s, _, s_s = gebuchte_sicht(config, hist, led, sch, stichtag, ab_tag=BETRIEBSBEGINN)

    mit_stamm_von_heute = einzelwerte_am(port, h_s, config, stichtag, scheiben=s_s)
    mit_stamm_vom_stichtag = einzelwerte_am(
        fuehre_fort(port, h_s), h_s, config, stichtag, scheiben=s_s)
    assert mit_stamm_von_heute == mit_stamm_vom_stichtag


def test_der_stichtagsschnitt_ruehrt_die_vorgeschichte_nicht_an(tmp_path, monkeypatch):
    """Die Gegenrichtung zu T24-02: Der Schnitt darf auch nicht zu viel
    nehmen. Ereignisse mit Wirkung VOR dem Betriebsbeginn sind
    Eroeffnungsstand — sie gehoeren vollstaendig dazu, unabhaengig davon,
    wann ihr rechnerischer Buchungstag laege.

    Warum das eine eigene Zusicherung braucht: Der Abnahmetest vergleicht
    zwei Welten. Faellt ``ab_tag`` weg, sind BEIDE gleich falsch, und der
    Vergleich bleibt gruen — nachgemessen, alle 25 Tests des Moduls
    blieben gruen. Eine Eigenschaft, die nur im Vergleich geprueft wird,
    ist gegen einen Fehler blind, der beide Seiten trifft.
    """
    import rechner_pipeline.betrieb.tageslauf as tl
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.betrieb import tagesjournal as tj
    from rechner_pipeline.betrieb.tagesjournal import mit_buchungstagen

    # Vierhundert Tage: Der Buchungstag eines Todes aus der Vorgeschichte
    # rutscht damit hinter den Stichtag — genau der Fall, den ab_tag deckt.
    monkeypatch.setattr(tj, "meldeverzug_tage", lambda config, police_id, jahr: 400)
    pfad = tmp_path / "bestand.toml"
    pfad.write_text(_kleine_config(faktor=8), encoding="utf-8")
    config = load_config(pfad)
    stichtag = dt.date(2026, 2, 1)
    # Vorgeschichte gibt es im eigenen Geschaeft nicht mehr (ADR-020): Sie
    # entsteht nur durch Uebernahme. Die Welt hier stellt sie nach, indem
    # der Strom LANGE vor dem Betriebsbeginn einsetzt — so, wie ein
    # uebernommener Bestand die gealterte Geschichte des abgebenden
    # Unternehmens mitbringt. Erst gealterte Vertraege sterben oft genug,
    # dass ein Tod mit Meldeverzug hinter den Stichtag rutscht (junge
    # Vertraege eines kurzen Fensters sterben praktisch nie).
    voll = _voll(config, dt.date(2026, 6, 30), ab=dt.date(2008, 1, 1))

    vorgeschichte = voll.ledger[voll.ledger["status_date"] < pd.Timestamp(BETRIEBSBEGINN)]
    spaet = mit_buchungstagen(config, vorgeschichte)
    spaet = spaet[spaet["buchungsdatum"] > pd.Timestamp(stichtag)]
    assert len(spaet) > 0, (
        "Testwelt ohne Vorgeschichts-Buchung hinter dem Stichtag — ohne sie "
        "koennte der Test den Verlust der Vorgeschichte nicht bemerken")

    tabellen = {"historie": voll.historie, "ledger": voll.ledger, "scheiben": voll.scheiben}
    sicht = tl._stichtagssicht(tabellen, config, stichtag, BETRIEBSBEGINN)

    geblieben = sicht["ledger"][
        sicht["ledger"]["status_date"] < pd.Timestamp(BETRIEBSBEGINN)]
    pd.testing.assert_frame_equal(
        vorgeschichte.reset_index(drop=True), geblieben.reset_index(drop=True),
        obj="Ledger der Vorgeschichte")


# --- T24-01 (a): die drei Stellen, die ein Lauf nicht still hinnimmt -----
#
# Der Review hat vier Fehlerfenster reproduziert. Drei davon sind
# Einzelstellen und hier geschlossen; das vierte — ein gemeinsamer
# Commit-Punkt fuer den ganzen Lauf — ist Schritt (b).
#
# Die vorhandene Fehlerinjektion oben patcht os.replace GLOBAL und feuert
# damit beim allerersten atomaren Parquet-Write, weit vor dem eigentlichen
# Tausch: Sie bezeugt den alten Stand bei einem fruehen, harmlosen
# Dateifehler, nicht am Commit-Punkt. Die Proben hier treffen gezielt.


def _nur_bei(ziel_teil: str):
    """os.replace/os.rename, das NUR beim benannten Ziel scheitert."""
    echt_replace, echt_rename = os.replace, os.rename

    def _replace(src, dst, *a, **k):
        if ziel_teil in str(dst):
            raise OSError(5, f"injiziert bei {dst}")
        return echt_replace(src, dst, *a, **k)

    def _rename(src, dst, *a, **k):
        if ziel_teil in str(dst):
            raise OSError(5, f"injiziert bei {dst}")
        return echt_rename(src, dst, *a, **k)

    return _replace, _rename


def test_fehlender_stand_mit_versionierten_resten_raeumt_nichts_auf(tmp_path):
    """Der Zustand nach einem Absturz im Erstuebergang: stand fehlt, die
    versionierten Verzeichnisse liegen da. Vorher hielt die Aufraeumung
    JEDES davon fuer eine Waise und loeschte den gefuehrten Bestand — der
    T24-07-Fix deckte nur den haengenden Symlink.

    Der Lauf wird NICHT abgebrochen: Eine Ablage ohne stand ist ein
    legitimer Ausgangspunkt. Gefaehrlich ist das Loeschen, und genau das
    unterbleibt, solange die Praemisse unklar ist."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    ziel = ablage.stand.resolve()
    ablage.stand.unlink()                      # Symlink weg, Stand bleibt
    assert not ablage.stand.exists() and ziel.is_dir()

    tl._verwaiste_staende_entfernen(ablage)
    assert ziel.is_dir(), "der gefuehrte Stand wurde geloescht"

    # Der benannte Ausweg funktioniert: Symlink von Hand setzen.
    ablage.stand.symlink_to(ziel.name)
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK


def test_ohne_versionierte_reste_bleibt_das_aufraeumen_still(tmp_path):
    """Positivkontrolle: Eine frische Ablage hat keinen stand und keine
    Reste — dort ist nichts unklar, und die Wache darf nicht feuern."""
    ablage = _ablage(tmp_path / "plv")
    assert not ablage.stand.exists()
    tl._verwaiste_staende_entfernen(ablage)    # kein Fehler
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK


def _abschluss_aus_gescheitertem_lauf(ablage, monkeypatch):
    """Ein Lauf, der den Monatsabschluss SCHREIBT und danach scheitert.

    Genau der Zustand, den die Fehlerinjektion des Reviews hinterlaesst:
    Die 0444-Datei liegt da, der gefuehrte Tag ist nicht gewandert — also
    faellt der naechste Lauf noch einmal auf denselben Monatsersten.
    """
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    echt = tl.write_portfolio

    def _journal_kaputt(df, pfad, *a, **k):
        if "tagesjournal" in str(pfad):
            raise OSError(28, "No space left on device")
        return echt(df, pfad, *a, **k)

    monkeypatch.setattr(tl, "write_portfolio", _journal_kaputt)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    monkeypatch.undo()
    assert code != EXIT_OK and zeile["uebernommen"] is False
    neu_geschrieben = [a for a in zeile["abschluesse"] if a["neu"]]
    assert neu_geschrieben, "Fixture ohne Monatsabschluss bezeugt nichts"
    datei = ablage.abschluesse / neu_geschrieben[0]["datei"]
    assert datei.is_file()
    return datei


def test_ein_vorhandener_abschluss_wird_nachgerechnet(tmp_path, monkeypatch):
    """Vorher galt eine vorhandene Abschlussdatei ungeprueft als gueltig —
    auch eine aus einem technisch gescheiterten Lauf. Jetzt rechnet der
    Lauf sie nach; unveraendert heisst befundfrei."""
    ablage = _ablage(tmp_path / "plv")
    datei = _abschluss_aus_gescheitertem_lauf(ablage, monkeypatch)

    _code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    vorhanden = [a for a in zeile["abschluesse"]
                 if a["datei"] == datei.name and not a["neu"]]
    assert vorhanden, "der vorhandene Abschluss wurde nicht wieder betrachtet"
    assert all(a.get("nachgerechnet") for a in vorhanden)
    assert not any("befunde" in a for a in vorhanden)


def test_ein_abweichender_abschluss_wird_ausgewiesen_und_bleibt_stehen(
    tmp_path, monkeypatch
):
    """Die Probe: Passt der festgeschriebene Stand nicht mehr zur
    Neuberechnung, nennt die Protokollzeile es — und die 0444-Datei bewegt
    sich nicht (ADR-011). Ohne die Nachrechnung sah das niemand."""
    from rechner_pipeline.bestand.parquet_io import write_portfolio

    ablage = _ablage(tmp_path / "plv")
    datei = _abschluss_aus_gescheitertem_lauf(ablage, monkeypatch)

    davor = datei.read_bytes()
    datei.chmod(0o644)
    tabelle = read_portfolio(datei)
    tabelle.loc[tabelle.index[0], "deckungskapital"] += 1000.0
    write_portfolio(tabelle, datei)
    manipuliert = datei.read_bytes()
    assert manipuliert != davor

    _code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    betroffen = [a for a in zeile["abschluesse"]
                 if a["datei"] == datei.name and not a["neu"]]
    assert betroffen and betroffen[0].get("befunde"), \
        "die Abweichung wurde nicht ausgewiesen"
    assert any("deckungskapital" in b for b in betroffen[0]["befunde"])
    assert datei.read_bytes() == manipuliert, "der Abschluss wurde angefasst"


def test_eine_unschreibbare_protokollzeile_ist_ein_benannter_fehler(
    tmp_path, monkeypatch
):
    """Der Stand ist uebernommen, die Zeile fehlt: Stand und Nachweis sagen
    ab jetzt Verschiedenes. Vorher lief hier ein roher OSError bis zur CLI
    durch — ohne Nachweis und ohne Ausweg."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK

    def _kaputt(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(tl, "_anfuegen", _kaputt)
    with pytest.raises(tl.TageslaufError, match="Protokollzeile"):
        tageslauf(ablage, dt.date(2026, 2, 3))


# --- T24-01 (b): der Lauf als EINE Veroeffentlichung ---------------------
#
# Ein Tageslauf veroeffentlicht mehrere extern sichtbare Artefakte
# nacheinander — Monatsabschluesse, Tagesjournal, Stand-Symlink,
# Protokollzeile. Jedes ist fuer sich atomar; zusammen waren sie es
# nicht. Der Write-Ahead-Marker bindet sie: Wer dazwischen abstuerzt,
# hinterlaesst einen BENANNTEN Zwischenzustand, den der naechste Lauf
# zuruecknimmt.
#
# Gefordert ist an jeder Naht dasselbe: entweder der alte Stand ist
# vollstaendig funktionsfaehig UND ein sauberer Retry gelingt, oder der
# neue ist vollstaendig uebernommen — nie ein dauerhaft blockierter
# Zustand.

#: Die Naehte, an denen ein Lauf abbrechen kann. "bericht" und
#: "protokoll-teilweise" sind nach Befund T26-02 dazugekommen: Der Bericht
#: entsteht NACH dem festgeschriebenen Abschluss, und ein Protokoll-Append
#: kann mitten in der Zeile abbrechen statt davor.
NAEHTE = ("abschluss", "bericht", "journal", "generation", "symlink",
          "protokoll", "protokoll-teilweise")

#: Die Ablage-Zustaende, aus denen heraus ein Lauf startet. Bisher wurde
#: ausschliesslich aus dem Symlink-Zustand geprueft — die Tests
#: initialisierten immer erst einen gruenen Stand. Genau daran ist der
#: Wiederanlauf aus der Erstbefuellung und aus dem Legacy-Zustand
#: vorbeigelaufen (Befund T26-02, Szenarien 1 und 2).
AUSGANGSZUSTAENDE = ("leer", "legacy", "symlink")


def _ausgangszustand(tmp_path, zustand: str):
    """Eine Ablage im genannten Zustand, plus der bis dahin gefuehrte Tag."""
    ablage = _ablage(tmp_path / "plv")
    if zustand == "leer":
        return ablage, None
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    if zustand == "legacy":
        # Die Symlinkform bytegleich in ein echtes Verzeichnis ueberfuehren —
        # der unterstuetzte Zustand vor dem Erstuebergang.
        ziel = ablage.stand.resolve()
        ablage.stand.unlink()
        os.rename(ziel, ablage.stand)
    return ablage, dt.date(2026, 1, 31)


def _injiziere(monkeypatch, naht: str):
    """Gezielt an EINER Naht scheitern — nicht global.

    Die alte Fehlerinjektion des Moduls patcht os.replace pauschal und
    feuert beim ersten atomaren Parquet-Write, weit vor jedem
    Commit-Punkt (Review T24-01, Punkt 5)."""
    if naht == "journal":
        echt = tl.write_portfolio

        def _kaputt(df, pfad, *a, **k):
            if "tagesjournal" in str(pfad):
                raise OSError(28, "No space left on device")
            return echt(df, pfad, *a, **k)

        monkeypatch.setattr(tl, "write_portfolio", _kaputt)
    elif naht == "generation":
        echt = tl.os.rename

        def _kaputt(src, dst, *a, **k):
            if "stand-" in str(dst):
                raise OSError(5, "I/O error")
            return echt(src, dst, *a, **k)

        monkeypatch.setattr(tl.os, "rename", _kaputt)
    elif naht == "symlink":
        echt = tl.os.replace

        def _kaputt(src, dst, *a, **k):
            if str(dst).endswith("/stand"):
                raise OSError(5, "I/O error")
            return echt(src, dst, *a, **k)

        monkeypatch.setattr(tl.os, "replace", _kaputt)
    elif naht == "abschluss":
        def _kaputt(*_a, **_k):
            # Abbruch WAEHREND des Festschreibens. Der Abschluss ist der
            # erste unwiderrufliche Schritt (0444, nie neu gerechnet); die
            # Naht davor war bisher ungeprueft, weil der Marker erst
            # dahinter lag.
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(tl, "schreibe_abschluss", _kaputt)
    elif naht == "bericht":
        def _kaputt(*_a, **_k):
            raise OSError(5, "I/O error")

        monkeypatch.setattr(tl, "_bericht", _kaputt)
    elif naht == "protokoll-teilweise":
        def _kaputt(pfad, zeile):
            # Der Anfang der Zeile steht, der Rest nicht — der Teilwrite,
            # den ein Absturz hinterlaesst. Ohne Zeilenumbruch: Die Zeile
            # ist nie eine geworden.
            with open(pfad, "a", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(zeile, ensure_ascii=False, sort_keys=True)[:60])
            raise OSError(5, "I/O error")

        monkeypatch.setattr(tl, "_anfuegen", _kaputt)
    else:
        def _kaputt(*_a, **_k):
            raise OSError(28, "No space left on device")

        monkeypatch.setattr(tl, "_anfuegen", _kaputt)


@pytest.mark.parametrize("zustand", AUSGANGSZUSTAENDE)
@pytest.mark.parametrize("naht", NAEHTE)
def test_ein_absturz_an_jeder_naht_laesst_sich_wiederaufnehmen(
    tmp_path, monkeypatch, naht, zustand
):
    """Jede Naht mal jeder Ausgangszustand — die Klasse, nicht der Fall.

    Der Befund T26-02 war nicht, dass EIN Wiederanlauf fehlte, sondern
    dass die Pruefung nur eine Spalte der Matrix kannte: Sie legte immer
    erst einen gruenen Symlink-Stand an. Aus der Erstbefuellung heraus
    blieb der neue Stand stehen, waehrend Journal und Marker
    zurueckgenommen wurden; aus dem Legacy-Zustand heraus verschwand der
    letzte belegte alte Stand.
    """
    ablage, _vorher_tag = _ausgangszustand(tmp_path, zustand)
    vorher_journal = (ablage.tagesjournal_pfad.read_bytes()
                      if ablage.tagesjournal_pfad.is_file() else None)

    _injiziere(monkeypatch, naht)
    try:
        code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
        assert code != EXIT_OK, f"Naht {naht}: der Lauf meldete Erfolg"
    except tl.TageslaufError:
        pass                      # die Protokollzeile selbst scheiterte
    monkeypatch.undo()

    # Der gefuehrte Tag ist NICHT gewandert — oder der Lauf war ganz durch.
    # Beides ist zulaessig; ein dritter Zustand nicht.
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK, (
        f"{zustand}/{naht}: der Retry gelingt nicht — genau das war der Befund")
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 3)
    assert not ablage.publish_marker.exists(), "Marker nicht aufgeraeumt"
    assert not ablage.tagesjournal_vorher_pfad.exists()
    # Das Protokoll ist wieder eine ungebrochene Kette — sonst haette der
    # Retry einen Zustand hinterlassen, der beim naechsten Lesen platzt.
    assert [z for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]
    # Der Vorgaenger liegt noch da: Seit dem Write-Ahead-Rahmen wird er
    # erst vom NAECHSTEN Lauf entfernt, wenn der Symlink steht. Genau das
    # macht den Standwechsel umkehrbar.
    assert tageslauf(ablage, dt.date(2026, 2, 4))[0] == EXIT_OK
    assert tageslauf(ablage, dt.date(2026, 2, 5))[0] == EXIT_OK
    uebrig = sorted(p.name for p in ablage.wurzel.glob("stand-*") if p.is_dir())
    assert ablage.stand.resolve().name in uebrig
    assert len(uebrig) <= 2, uebrig
    # Das Journal ist entweder das alte oder das neue — nie ein Mischling.
    # (Der Ausgangszustand "leer" hat keines; dort ist nichts zu halten.)
    if vorher_journal is not None:
        assert ablage.tagesjournal_pfad.is_file()


def test_der_marker_liegt_nur_waehrend_der_veroeffentlichung(tmp_path,
                                                             monkeypatch):
    """Positivkontrolle: Ein gruener Lauf hinterlaesst keinen Marker —
    sonst naehme der naechste Lauf jedes Mal etwas zurueck."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    assert not ablage.publish_marker.exists()

    gesehen = {}
    echt = tl._uebernehmen

    def _spion(ablage_, kennung):
        gesehen["marker"] = ablage_.publish_marker.is_file()
        gesehen["kopie"] = ablage_.tagesjournal_vorher_pfad.is_file()
        return echt(ablage_, kennung)

    monkeypatch.setattr(tl, "_uebernehmen", _spion)
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert gesehen["marker"], "kein Write-Ahead-Marker beim Standwechsel"
    assert gesehen["kopie"], "keine Ruecknahme-Kopie des Journals"
    assert not ablage.publish_marker.exists()


def test_ein_unlesbarer_marker_haelt_den_lauf_an(tmp_path):
    """Unklarheit ist ein benannter Zustand: Ob ein Publish unterwegs war,
    weiss bei einer kaputten Datei niemand — und eine Ruecknahme auf
    Verdacht waere schlimmer als keine."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    ablage.publish_marker.write_text("{kaputt", encoding="utf-8")

    with pytest.raises(tl.TageslaufError, match="laesst sich aber nicht lesen"):
        tageslauf(ablage, dt.date(2026, 2, 3))


def test_jeder_abschluss_traegt_seine_monatskennzahlen(gefuehrt):
    """Die Monatszeile der Unternehmensseite konsumiert das Modell, sie
    rechnet nicht selbst (Auftrag des Maintainers 2026-09-19).

    Geprueft wird am ECHTEN Protokoll des Laufs, nicht an einer selbst
    gebauten Sicht: Die Zahlen sollen aus derselben Stichtagssicht
    stammen, aus der auch der Abschluss entsteht.
    """
    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    abschluesse = [a for z in zeilen for a in z["abschluesse"]]
    assert abschluesse, "kein Abschluss im Protokoll"
    for a in abschluesse:
        for feld in ("in_kraft", "zugaenge", "leistungen"):
            assert feld in a, (a["stichtag"], feld)
            assert isinstance(a[feld], int), (a["stichtag"], feld)
            assert a[feld] >= 0, (a["stichtag"], feld)


def test_in_kraft_des_abschlusses_ist_der_stand_seines_stichtags(gefuehrt):
    """Nicht der Stand von heute: Auf der Sicht von heute erzaehlte die
    Zahl vom selben Stichtag eine andere Geschichte als der Abschluss
    daneben (T24-02)."""
    from rechner_pipeline.bestand.fuehrung import bestand_am

    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    for z in zeilen:
        for a in z["abschluesse"]:
            stichtag = dt.date.fromisoformat(a["stichtag"])
            abschluss = read_portfolio(ablage.abschluesse / a["datei"])
            # Der Abschluss IST der in-force-Stand seines Stichtags; seine
            # Zeilenzahl muss die gemeldete Zahl sein.
            assert a["in_kraft"] == len(abschluss), a["stichtag"]


def test_die_zaehler_zaehlen_vorfaelle_und_nicht_buchungszeilen(gefuehrt):
    """Ein Zugang bucht Summe UND Bruttojahresbeitrag — zwei Zeilen
    desselben Vorfalls (BETRAG_ART_JE_EREIGNIS). Wer Zeilen zaehlt,
    meldet doppelt so viele Zugaenge, wie es gab."""
    from rechner_pipeline.models.bestand import ZUGANG_EREIGNISSE

    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    gemeldet = sum(a["zugaenge"] for z in zeilen for a in z["abschluesse"])
    journal = read_portfolio(ablage.stand / ".." / "journal" / "tagesjournal.parquet") \
        if (ablage.stand / ".." / "journal" / "tagesjournal.parquet").exists() else None
    if journal is None:
        pytest.skip("kein Tagesjournal in dieser Ablage")
    zug = journal[journal["ereignis"].isin(ZUGANG_EREIGNISSE)]
    zeilenzahl = len(zug)
    vorfaelle = len(zug.drop_duplicates(subset=["police_id", "ereignis", "status_date"]))
    if zeilenzahl == vorfaelle:
        pytest.skip("in dieser Ablage bucht kein Zugang zwei Betragsarten")
    assert gemeldet <= vorfaelle, (gemeldet, vorfaelle, zeilenzahl)


def test_geschriebene_und_nachgerechnete_kennzahlen_stimmen_ueberein(gefuehrt):
    """Zwei Wege, eine Zahl — und genau das wird hier geprueft.

    Der Tagesbetrieb SCHREIBT die Kennzahlen, wenn er einen Abschluss
    anlegt. Der Paket-Export RECHNET sie nach fuer Abschluesse, die sie
    noch nicht tragen (aeltere Laeufe). Zwei Stellen, die dieselbe
    Groesse bestimmen, sind die Klasse, die in diesem Repo mehrfach
    zugeschlagen hat — zuletzt als A-B1 funktional tot war und als die
    Bewegungsrechnung RED auf beiden Seiten derselben Identitaet
    auslaesst (T26-11).

    Deshalb rufen beide Wege dieselbe Funktion, und dieser Test haelt
    ihre Ergebnisse gegeneinander: Die Protokollwerte werden entfernt,
    der Export rechnet sie nach, und beide muessen gleich sein.
    """
    from rechner_pipeline.betrieb.seite import (
        KENNZAHL_FELDER, abschluesse_aus_protokoll,
    )

    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    geschrieben = {a["stichtag"]: {f: a[f] for f in KENNZAHL_FELDER}
                   for z in zeilen for a in z["abschluesse"]}
    assert geschrieben, "kein Abschluss mit Kennzahlen im Protokoll"

    # Dieselben Zeilen OHNE die Zahlen — so sehen Protokolle aus, die vor
    # der Einfuehrung der Felder entstanden sind.
    ohne = [
        {**z, "abschluesse": [{k: v for k, v in a.items()
                               if k not in KENNZAHL_FELDER}
                              for a in z["abschluesse"]]}
        for z in zeilen
    ]
    # Die Quellen einzeln, wie sie auch der Konsument aus dem Paket
    # stellt — nicht die Ablage: Eine Ablage koennte nur der Erzeuger
    # reichen, und der Test pruefte dann einen Weg, den es beim Leser
    # des Pakets gar nicht gibt.
    journal = read_portfolio(ablage.tagesjournal_pfad,
                             expected_columns=TAGESJOURNAL_NAMES)
    nachgerechnet = {
        e["stichtag"]: {f: e.get(f) for f in KENNZAHL_FELDER}
        for e in abschluesse_aus_protokoll(
            ohne, journal=journal, abschluesse_dir=ablage.abschluesse)
    }

    for stichtag, werte in geschrieben.items():
        assert nachgerechnet[stichtag] == werte, (
            f"{stichtag}: geschrieben {werte}, nachgerechnet "
            f"{nachgerechnet[stichtag]}")


def test_ohne_quelle_bleibt_die_zahl_leer_statt_null(gefuehrt, tmp_path):
    """Eine erfundene Null waere schlimmer als eine Luecke: "nicht
    gerechnet" und "null Vorfaelle" sind verschiedene Aussagen."""
    from rechner_pipeline.betrieb.seite import (
        KENNZAHL_FELDER, abschluesse_aus_protokoll,
    )

    ablage, _ = gefuehrt
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    ohne = [
        {**z, "abschluesse": [{k: v for k, v in a.items()
                               if k not in KENNZAHL_FELDER}
                              for a in z["abschluesse"]]}
        for z in zeilen
    ]
    # Keine Quellen: kein Journal, ein Abschlussverzeichnis, das es nicht
    # gibt. So sieht ein Aufrufer aus, der nur das Protokoll hat.
    for eintrag in abschluesse_aus_protokoll(
            ohne, journal=None, abschluesse_dir=tmp_path / "leer"):
        for feld in KENNZAHL_FELDER:
            assert feld not in eintrag, (eintrag["stichtag"], feld)
