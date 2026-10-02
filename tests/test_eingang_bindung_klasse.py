"""Der Betriebseingang bindet alles, was er fuehrt — Angriffsrunde nach T27.

Die Klasse: Was der Betrieb aus einem Eingang liest, haengt an einem
Zeugen, den der Eingang nicht selbst schreibt. Der Uebernahmebeleg hing
an nichts (Tarifwerk-Pruefung umgehbar), eingang.json hing an nichts
(stimmig umgeschrieben rechnete der Lauf die Geschichte neu), und ohne
Schluessel entstand ein Eingang, den kein Lauf je annahm.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json

import pytest

from rechner_pipeline.betrieb import tageslauf as tl

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from rechner_pipeline.bestand.config import config_aus_text
from tests.test_betrieb_uebernahme import STICHTAG, _fall, _kleine_config
from tests.test_betrieb_uebernahme import _mit_config  # noqa: E402


def test_ein_nach_der_abnahme_geaenderter_uebernahmebeleg_wird_nicht_registriert(tmp_path):
    """Mutationsprobe: die Belegschleife in eingang_anlegen entfernen -> rot."""
    fall = _fall(tmp_path)
    beleg = fall / "abgeleitet" / "bestand" / "uebernahme.json"
    d = json.loads(beleg.read_text(encoding="utf-8"))
    vorher = dict(d["tarifwerk"])
    d["tarifwerk"] = {**vorher, "stoab_je_baustein": not vorher["stoab_je_baustein"]}
    assert d["tarifwerk"] != vorher, "die Probe aendert nichts"
    beleg.write_text(json.dumps(d), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="nicht der, den der A-M4-Snapshot bezeugt"):
        ueb.eingang_anlegen(_mit_config(tmp_path / "daten"), fall, STICHTAG)
    assert not (tmp_path / "daten" / "uebernahme" / "probe-uebernahme").exists()


def test_ein_entfernter_uebernahmebeleg_wird_nicht_registriert(tmp_path):
    fall = _fall(tmp_path)
    (fall / "abgeleitet" / "bestand" / "uebernahme.json").unlink()
    with pytest.raises(ueb.UebernahmeError, match="Uebernahmebeleg fehlt"):
        ueb.eingang_anlegen(_mit_config(tmp_path / "daten"), fall, STICHTAG)


def test_ein_beleg_ohne_tarifwerk_ist_eine_luecke():
    cfg = config_aus_text(_kleine_config())
    assert ueb.tarifwerk_fehler(cfg, ["KLV-2017"], {"anfangszustand": "ohne_bausteine"})


def test_ein_nach_dem_eintritt_stimmig_umgeschriebener_eingang_wird_nicht_mehr_gefuehrt(tmp_path):
    """Der Angreifer: Geschlecht einer Police geaendert, Tabelle neu
    geschrieben, Summe in eingang.json nachgezogen — der naechste Lauf
    rechnete die Geschichte aus dem geaenderten Eingang neu, gruen.
    Seit Runde C halten ihn zwei Schichten: der bezeugte Hash jeder gruenen
    Zeile (_pruefe_bezeugte_eingaenge) und die Nachrechnung der letzten
    Zeile (eingang_sha256). Der Lauf verweigert, bevor er etwas baut.
    Mutationsprobe: beide nicht rufen -> rot."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK

    tabelle = ziel / "bestand.parquet"
    stamm = read_portfolio(tabelle)
    stamm.loc[stamm.index[0], "sex"] = "M" if stamm.loc[stamm.index[0], "sex"] == "F" else "F"
    tabelle.chmod(0o644)
    write_portfolio(stamm, tabelle)
    kopf = ziel / "eingang.json"
    kopf.chmod(0o644)
    d = json.loads(kopf.read_text(encoding="utf-8"))
    d["dateien"]["bestand.parquet"] = hashlib.sha256(tabelle.read_bytes()).hexdigest()
    kopf.write_text(json.dumps(d, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(tl.TageslaufError, match="eingang"):
        tageslauf(ablage, dt.date(2026, 2, 4))


# --------------------------------------------------------------------------- #
# Zeilengrenze: Schreiber und Leser trennen an LF
# --------------------------------------------------------------------------- #


def test_eine_zeile_mit_zeilentrenner_zeichen_bleibt_eine_zeile(tmp_path):
    """Mutationsprobe: in jsonl_zeilen wieder splitlines -> rot."""
    from rechner_pipeline.betrieb.tageslauf import _anfuegen, lies_protokoll

    pfad = tmp_path / "protokoll.jsonl"
    _anfuegen(pfad, {"schema_version": 2, "fall": "a b\u0085c"})
    _anfuegen(pfad, {"schema_version": 2, "fall": "d"})
    zeilen = lies_protokoll(pfad)
    assert [z["fall"] for z in zeilen] == ["a b\u0085c", "d"]


def test_ein_fallname_mit_trennzeichen_wird_nicht_registriert(tmp_path):
    fall = _fall(tmp_path)
    kopf = fall / "fall.json"
    kopf.write_text(json.dumps({"name": "probe x", "schema_version": 1}), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="Trennzeichen"):
        ueb.eingang_anlegen(_mit_config(tmp_path / "daten"), fall, STICHTAG)


def test_kein_jsonl_leser_im_betrieb_trennt_mit_splitlines():
    """Ratsche: der eine Weg ist models.anker.jsonl_zeilen."""
    from pathlib import Path

    wurzel = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"
    dateien = list((wurzel / "betrieb").glob("*.py")) + [wurzel / "models" / "anker.py"]
    treffer = [f"{p.name}:{n}" for p in dateien
               for n, z in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
               if ".splitlines(" in z and not z.lstrip().startswith("#")
               and "``str.splitlines``" not in z]
    assert treffer == []
