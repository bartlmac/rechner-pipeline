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
    """Die PLV-Config als schnelle Testwelt: acht Vertraege je verkaufender
    Generation (die uebernommene TG2015 bleibt bei 0) und die
    Erzeugungsgrenze am 1.1.2026.

    Die echte PLV beginnt am 1.7.1994 und baut ihren Bestand Tag fuer Tag
    auf; das sind zweiunddreissig Jahre Tagesstrom und rund 34 Sekunden je
    Lauf. Fuer die Tests wird die Grenze deshalb nach vorn gesetzt: Der
    Batch stellt den Bestand, der Tagesstrom traegt nur die Tage des Tests.
    Beides ist derselbe Mechanismus, nur an einer anderen Grenze — die
    lange Geschichte prueft test_betrieb_lange_geschichte.
    """
    text = PLV.read_text(encoding="utf-8")
    text = re.sub(r"^sample_size = [1-9]\d*$", "sample_size = 8", text, flags=re.M)
    text = re.sub(r"^betriebsbeginn = .*$", "betriebsbeginn = 2026-01-01", text, flags=re.M)
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
    # Der naechste Lauf raeumt den Rest auf und fuehrt den Tag.
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert gefuehrter_tag(ablage) == dt.date(2026, 2, 3)
    assert sorted(p.name for p in ablage.wurzel.glob("stand-*") if p.is_dir()) == [
        ablage.stand.resolve().name]


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
    assert ablage.stand.resolve() != aktuell and not aktuell.exists()


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
    _pruefe_nachweis entfernen -> rot."""
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
    Mutationsprobe: den Manifest-Vergleich in _pruefe_nachweis entfernen -> rot."""
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
    """Meldeverzug auf 400 Tage gesetzt: Kein Tod seit Betriebsbeginn ist
    bis heute gebucht — und keiner steht im Stand, obwohl die volle
    Wirkungshistorie welche kennt."""
    from rechner_pipeline.betrieb import tagesjournal as tj
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from rechner_pipeline.bestand.generator import generate

    monkeypatch.setattr(tj, "meldeverzug_tage", lambda config, police_id, jahr: 400)
    ablage = _ablage(tmp_path / "plv")
    # Groessere Stichprobe, damit seit Betriebsbeginn Todesfaelle vorkommen.
    ablage.config_pfad.write_text(
        _kleine_config().replace("sample_size = 8", "sample_size = 60"), encoding="utf-8")
    heute = dt.date(2026, 9, 30)
    assert tageslauf(ablage, heute)[0] == EXIT_OK
    config = load_config(ablage.config_pfad)
    voll = fortschreiben(generate(config, bis=BETRIEBSBEGINN), config, heute)
    tode_voll = voll.ledger[(voll.ledger["ereignis"] == "TOD")
                            & (voll.ledger["status_date"] > pd.Timestamp(BETRIEBSBEGINN))]
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    tode_stand = ledger[(ledger["ereignis"] == "TOD") & (ledger["status_date"] > pd.Timestamp(BETRIEBSBEGINN))]
    assert len(tode_stand) == 0
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    for pid in tode_voll["police_id"]:
        assert gesamt.loc[gesamt["police_id"] == pid, "status_code"].iloc[0] != "TOD"
    if len(tode_voll) == 0:
        pytest.skip("kein Todesfall seit Betriebsbeginn in der kleinen Config — Aussage nicht pruefbar")
