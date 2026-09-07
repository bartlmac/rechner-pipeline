"""Ein Produzent loescht nur, was er selbst erzeugt hat (Review T24-07).

``stands_paket`` entfernte JEDES vorhandene Zielverzeichnis: ``--paket``
gleich ``--stand`` loeschte die Ablage mit Stand, Journal und Protokoll,
ein Tippfehler ein fremdes Verzeichnis. Die Klasse dahinter: ``rmtree``
loescht, was am Pfad LIEGT, nicht was der Name verspricht — dieselbe Luecke
hatte der Standwechsel des Tageslaufs, der ein per Symlink aufgeloestes
Verzeichnis entfernte, egal wohin der Symlink zeigte.

Zwei Regeln, eine Ratsche:
* Das Stands-Paket ersetzt nur ein frueheres Paket (``stand.json``) an
  einem Ziel, das weder in der Ablage liegt noch sie enthaelt.
* Der Tageslauf entfernt nur echte Stand-/Arbeitsverzeichnisse unmittelbar
  in der Wurzel — ueber EINEN Helfer, an den jedes ``rmtree`` gebunden ist.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, TageslaufError, tageslauf
from tests.test_betrieb_seite import _ablage

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    ablage = _ablage(tmp_path_factory.mktemp("plv"))
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def _ablage_intakt(ablage) -> bool:
    return ablage.stand.exists() and ablage.protokoll_pfad.is_file() and ablage.config_pfad.is_file()


# --------------------------------------------------------------------------- #
# Stands-Paket: das Ziel
# --------------------------------------------------------------------------- #

def test_paket_gleich_stand_loescht_die_ablage_nicht(gefuehrt):
    """Der Reviewer-Fall: --paket == --stand."""
    rc = st.main(["--stand", str(gefuehrt.wurzel), "--paket", str(gefuehrt.wurzel)])
    assert rc == 2
    assert _ablage_intakt(gefuehrt)


@pytest.mark.parametrize("ziel", ["in_der_ablage", "enthaelt_die_ablage", "die_ablage_selbst"])
def test_ziel_in_oder_um_die_ablage_wird_verweigert(gefuehrt, ziel):
    pfad = {
        "in_der_ablage": gefuehrt.wurzel / "paket",
        "enthaelt_die_ablage": gefuehrt.wurzel.parent,
        "die_ablage_selbst": gefuehrt.wurzel,
    }[ziel]
    fehler = st.paketziel_fehler(gefuehrt, pfad)
    assert fehler and "Ablage" in fehler
    with pytest.raises(st.SeiteError):
        st.stands_paket(gefuehrt, pfad)
    assert _ablage_intakt(gefuehrt)


def test_fremdes_verzeichnis_wird_nicht_ersetzt(gefuehrt, tmp_path):
    """Ein Verzeichnis ohne stand.json ist kein frueheres Paket — Inhalt bleibt."""
    fremd = tmp_path / "fremd"
    fremd.mkdir()
    (fremd / "wichtig.txt").write_text("nicht loeschen\n", encoding="utf-8")
    with pytest.raises(st.SeiteError, match="kein frueheres Stands-Paket"):
        st.stands_paket(gefuehrt, fremd)
    assert (fremd / "wichtig.txt").read_text(encoding="utf-8") == "nicht loeschen\n"


def test_datei_und_symlink_als_ziel_werden_verweigert(gefuehrt, tmp_path):
    datei = tmp_path / "datei"
    datei.write_text("x", encoding="utf-8")
    assert "Datei" in (st.paketziel_fehler(gefuehrt, datei) or "")
    echt = tmp_path / "echt"
    echt.mkdir()
    (echt / st.PAKET_DATEI).write_text("{}", encoding="utf-8")
    link = tmp_path / "link"
    link.symlink_to(echt)
    assert "Symlink" in (st.paketziel_fehler(gefuehrt, link) or "")
    assert (echt / st.PAKET_DATEI).is_file()


def test_neues_ziel_und_frueheres_paket_werden_geschrieben(gefuehrt, tmp_path):
    """Positivkontrolle: leeres Ziel wird angelegt, ein Paket wird ersetzt."""
    ziel = tmp_path / "paket"
    assert st.paketziel_fehler(gefuehrt, ziel) is None
    st.stands_paket(gefuehrt, ziel)
    assert (ziel / st.PAKET_DATEI).is_file()
    (ziel / "alt.txt").write_text("vom letzten Export\n", encoding="utf-8")
    st.stands_paket(gefuehrt, ziel)
    assert (ziel / st.PAKET_DATEI).is_file() and not (ziel / "alt.txt").exists()


# --------------------------------------------------------------------------- #
# Tageslauf: der Loeschhelfer
# --------------------------------------------------------------------------- #

def test_helfer_entfernt_nur_stand_und_arbeitsverzeichnisse_der_wurzel(gefuehrt, tmp_path):
    ablage = gefuehrt
    stand_alt = ablage.wurzel / f"{tl.STAND_DIR}-alt"
    stand_alt.mkdir()
    (stand_alt / "x").write_text("x", encoding="utf-8")
    tl._entferne_ablageverzeichnis(ablage, stand_alt)
    assert not stand_alt.exists()
    # ausserhalb der Wurzel: verweigert, Inhalt bleibt
    aussen = tmp_path / f"{tl.STAND_DIR}-backup"
    aussen.mkdir()
    (aussen / "backup.parquet").write_bytes(b"...")
    with pytest.raises(TageslaufError, match="verweigert"):
        tl._entferne_ablageverzeichnis(ablage, aussen)
    assert (aussen / "backup.parquet").exists()
    # in der Wurzel, aber kein Stand-/Arbeitsname: verweigert
    with pytest.raises(TageslaufError, match="verweigert"):
        tl._entferne_ablageverzeichnis(ablage, ablage.berichte)
    assert ablage.berichte.exists()
    # ein Symlink in der Wurzel, der nach aussen zeigt: verweigert, Ziel bleibt
    link = ablage.wurzel / f"{tl.STAND_DIR}-link"
    link.symlink_to(aussen)
    with pytest.raises(TageslaufError, match="verweigert"):
        tl._entferne_ablageverzeichnis(ablage, link)
    assert (aussen / "backup.parquet").exists()
    link.unlink()


def test_symlink_alias_in_der_wurzel_wird_verweigert(gefuehrt):
    """Isoliert die Symlink-Pruefung: Ziel UND Name waeren fuer sich erlaubt
    (echtes stand-Verzeichnis in der Wurzel), nur der Weg dahin ist ein Link."""
    ablage = gefuehrt
    echt = ablage.wurzel / f"{tl.STAND_DIR}-real"
    echt.mkdir()
    (echt / "x").write_text("x", encoding="utf-8")
    alias = ablage.wurzel / f"{tl.STAND_DIR}-alias"
    alias.symlink_to(echt.name)
    assert "verweigert" in (tl._ablageverzeichnis_fehler(ablage, alias) or "")
    with pytest.raises(TageslaufError, match="verweigert"):
        tl._entferne_ablageverzeichnis(ablage, alias)
    assert (echt / "x").exists()
    alias.unlink()
    tl._entferne_ablageverzeichnis(ablage, echt)
    assert not echt.exists()


def test_nur_die_paketdatei_macht_ein_frueheres_paket(gefuehrt, tmp_path):
    """Isoliert den Marker: index.html allein ist kein Stands-Paket."""
    ziel = tmp_path / "halb"
    ziel.mkdir()
    (ziel / "index.html").write_text("<html></html>", encoding="utf-8")
    assert "kein frueheres Stands-Paket" in (st.paketziel_fehler(gefuehrt, ziel) or "")
    (ziel / st.PAKET_DATEI).write_text("{}", encoding="utf-8")
    assert st.paketziel_fehler(gefuehrt, ziel) is None


def test_umgesetzter_stand_symlink_nach_aussen_loescht_kein_backup(tmp_path):
    """Die Klasse im Tageslauf: ``stand`` zeigt (von Hand umgesetzt) auf ein
    Backup ausserhalb der Ablage. Der Lauf bricht VOR dem Tausch ab: Backup
    und Symlink bleiben, Stand und Nachweis passen weiter zusammen, und nach
    der Handreparatur des Symlinks laeuft der Tag durch."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert ablage.stand.is_symlink()
    echter_stand = ablage.stand.resolve()
    backup = tmp_path / "backup-stand"
    backup.mkdir()
    (backup / "bestand.parquet").write_bytes((echter_stand / "bestand.parquet").read_bytes())
    for name in echter_stand.iterdir():
        if name.name != "bestand.parquet":
            (backup / name.name).write_bytes(name.read_bytes())
    ablage.stand.unlink()
    ablage.stand.symlink_to(backup)
    rc = tageslauf(ablage, dt.date(2026, 2, 4))[0]
    assert rc != EXIT_OK
    assert backup.exists() and (backup / "bestand.parquet").exists()
    # Nichts getauscht: der Symlink zeigt weiter auf das Backup, kein Wedge.
    assert ablage.stand.resolve() == backup.resolve()
    # Handreparatur laut Meldung: Symlink zurueck auf den echten Stand.
    ablage.stand.unlink()
    ablage.stand.symlink_to(echter_stand.name)
    assert tageslauf(ablage, dt.date(2026, 2, 4))[0] == EXIT_OK
    assert ablage.stand.resolve() != echter_stand and backup.exists()


# --------------------------------------------------------------------------- #
# Ratsche: jedes rmtree in betrieb/ ist an die zwei geprueften Stellen gebunden
# --------------------------------------------------------------------------- #

def test_jedes_rmtree_in_betrieb_ist_an_eine_geprueft_stelle_gebunden():
    betrieb = REPO_ROOT / "src" / "rechner_pipeline" / "betrieb"
    fundstellen = {}
    for datei in sorted(betrieb.glob("*.py")):
        text = datei.read_text(encoding="utf-8")
        fundstellen[datei.name] = len(re.findall(r"\bshutil\.rmtree\(", text))
    erlaubt = {"seite.py": 1, "tageslauf.py": 1, "uebernahme.py": 1}
    zuviel = {k: v for k, v in fundstellen.items() if v and v != erlaubt.get(k)}
    assert not zuviel, (
        f"neue rmtree-Stelle(n) in betrieb/: {zuviel} — jede Loeschung eines "
        "Verzeichnisses laeuft ueber tageslauf._entferne_ablageverzeichnis oder "
        "hinter seite.paketziel_fehler; uebernahme.py loescht nur seinen eigenen "
        "'.neu'-Rest neben dem Eingang"
    )
