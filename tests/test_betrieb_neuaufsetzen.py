"""Der Betrieb aus der Uebernahme (Freischaltung, Schritt 9; Review T25-07).

Der Tagesbetrieb fuehrte den uebernommenen Bestand in einer anderen Welt
als die Abnahmen (Review T22-11): Der Eingang kannte weder die Bausteine
noch die Korrekturschicht noch den Uebernahmebeleg, die Fortschreibung des
Tageslaufs bekam sie nicht, und die Tarifwerk-Schalter der Laufzeit-Config
hielt niemand gegen den Beleg. Jetzt:

* Der Eingang registriert scheiben.parquet, schichten.parquet und
  uebernahme.json (Hash), der Betrieb liest sie und prueft die Schalter.
* Der Tageslauf reicht Bausteine, Schicht und Verankerung in die
  Fortschreibung; die uebernommenen Bausteine stehen im Stand.
* Die Routine ``betrieb.neuaufsetzen`` setzt die Laufzeit aus dem Fall neu
  auf — durch Umbenennen, nie durch Loeschen.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import neuaufsetzen as na
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from rechner_pipeline.models.bestand import (
    SCHEIBEN_NAMES, SCHEIBEN_SPALTEN, SCHICHTEN_NAMES, SCHICHTEN_SPALTEN,
    VERANKERUNG_NAMES, VERANKERUNG_SPALTEN,
)
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import STICHTAG, _fall

REPO_ROOT = Path(__file__).resolve().parents[1]


def _scheiben(police_id: int) -> pd.DataFrame:
    zeile = {
        "police_id": police_id, "scheiben_id": 1, "erhoehung_jahr": 3,
        "erhoehung_datum": pd.Timestamp("2021-03-01"), "entry_age": 38, "duration": 22,
        "premium_duration": 17, "sum_insured": 5000.0, "gamma1": 0.0,
    }
    return pd.DataFrame([zeile])[list(SCHEIBEN_NAMES)].astype(dict(SCHEIBEN_SPALTEN))


def _schichten(police_id: int) -> pd.DataFrame:
    zeile = {
        "police_id": police_id, "schichttyp": "conv", "verankerungszustand": "aktiv",
        "verweildauer": 0, "rho": 0.02, "formfunktion": "konstant", "formparameter": "{}",
        "vererbend": "[]", "kohorte": "2026-01", "in_ueberschuss": False, "in_zzr": False,
        "rumpfmonate": 0,
    }
    return pd.DataFrame([zeile])[list(SCHICHTEN_NAMES)].astype(dict(SCHICHTEN_SPALTEN))


def _verankerung(police_id: int) -> pd.DataFrame:
    zeile = {"police_id": police_id, "monate_ta": 94, "zustand_ta": "beitragspflichtig",
             "verweildauer_ta": 0, "dk_ta": 12000.0}
    return pd.DataFrame([zeile])[list(VERANKERUNG_NAMES)].astype(dict(VERANKERUNG_SPALTEN))


def _fall_mit_nebentabellen(tmp_path: Path, *, tarifwerk: dict | None = None) -> Path:
    fall = _fall(tmp_path)
    quelle = fall / "abgeleitet" / "bestand"
    # Der Baustein gehoert zur Zugangsbuchung: die Kern-Herleitung der
    # Buchung (P-B1, T20-04) rechnet Grundsumme plus Baustein.
    ledger = read_portfolio(quelle / "ledger.parquet")
    zug = (ledger["police_id"] == 7_000_001) & (ledger["ereignis"] == "ZUG")
    ledger.loc[zug, "betrag"] = 60000.0 + 5000.0
    write_portfolio(ledger, quelle / "ledger.parquet")
    write_portfolio(_scheiben(7_000_001), quelle / "scheiben.parquet")
    write_portfolio(_schichten(7_000_001), quelle / "schichten.parquet")
    write_portfolio(_verankerung(7_000_001), quelle / "verankerung.parquet")
    beleg = {"schema_version": 1, "anfangszustand": "materialisieren"}
    if tarifwerk is not None:
        beleg["tarifwerk"] = tarifwerk
    (quelle / "uebernahme.json").write_text(json.dumps(beleg), encoding="utf-8")
    return fall


# --------------------------------------------------------------------------- #
# Eingang: Bausteine, Schicht und Beleg wandern mit
# --------------------------------------------------------------------------- #

def test_eingang_registriert_bausteine_schicht_und_beleg(tmp_path):
    fall = _fall_mit_nebentabellen(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    eingang = json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))
    assert {"scheiben.parquet", "schichten.parquet", "uebernahme.json"} <= set(eingang["dateien"])
    ablage = _ablage(stand)
    from rechner_pipeline.bestand.config import load_config
    u = ueb.lies_uebernahme(ziel, load_config(ablage.config_pfad))
    assert len(u.scheiben) == 1 and len(u.schichten) == 1
    assert u.beleg["anfangszustand"] == "materialisieren"


def test_eingang_ohne_nebentabellen_bleibt_lesbar(tmp_path):
    """Zugaenge vor der Freischaltung tragen weder Bausteine noch Beleg."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage(stand)
    from rechner_pipeline.bestand.config import load_config
    u = ueb.lies_uebernahme(ziel, load_config(ablage.config_pfad))
    assert u.scheiben is None and u.schichten is None and u.beleg == {}


def test_tarifwerk_der_config_wird_gegen_den_beleg_gehalten(tmp_path):
    """Die Laufzeit-Config sagt fuer KLV-2017 stoab_je_baustein=false; ein
    Beleg, dessen Abnahmen mit true bestanden wurden, ist ein Widerspruch."""
    fall = _fall_mit_nebentabellen(tmp_path, tarifwerk={
        "scheiben_mit_gamma1": False, "stoab_je_baustein": True, "red_verfahren": "prospektiv",
    })
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage(stand)
    from rechner_pipeline.bestand.config import load_config
    with pytest.raises(ueb.UebernahmeError, match="Tarifwerk"):
        ueb.lies_uebernahme(ziel, load_config(ablage.config_pfad))
    # Der passende Beleg ist kein Befund.
    passend = ueb.tarifwerk_fehler(load_config(ablage.config_pfad), ["KLV-2017"], {
        "tarifwerk": {"scheiben_mit_gamma1": False, "stoab_je_baustein": False, "red_verfahren": "prospektiv"},
    })
    assert passend == []


# --------------------------------------------------------------------------- #
# Tageslauf: die Fortschreibung bekommt die Nebentabellen
# --------------------------------------------------------------------------- #

def test_tageslauf_fuehrt_die_uebernommenen_bausteine_im_stand(tmp_path, monkeypatch):
    """Die Engine bekommt Bausteine, Schicht und Verankerung der Uebernahme
    wirklich uebergeben (Spion auf fortschreiben) — nicht nur der Stand
    bekommt die Dateien (Review Schritt 9)."""
    from rechner_pipeline.betrieb import tageslauf as tl_modul
    fall = _fall_mit_nebentabellen(tmp_path)
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = _ablage(stand)
    gesehen = {}
    echt = tl_modul.fortschreiben

    def spion(*args, **kwargs):
        gesehen.update(kwargs)
        return echt(*args, **kwargs)

    monkeypatch.setattr(tl_modul, "fortschreiben", spion)
    rc, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert rc == EXIT_OK
    for rolle in ("scheiben", "schichten", "verankerung"):
        assert gesehen.get(rolle) is not None, rolle
        assert 7_000_001 in set(gesehen[rolle]["police_id"]), rolle
    assert zeile["verankerung"]["angewandt"] is True
    scheiben = read_portfolio(ablage.stand / "scheiben.parquet")
    assert 7_000_001 in set(scheiben["police_id"])
    schichten = read_portfolio(ablage.stand / "schichten.parquet")
    assert list(schichten["police_id"]) == [7_000_001] and float(schichten["rho"].iloc[0]) == 0.02
    assert 7_000_001 in set(read_portfolio(ablage.stand / "bestand_gesamt.parquet")["police_id"])


# --------------------------------------------------------------------------- #
# Routine: Betrieb neu aufsetzen — umbenennen, nie loeschen
# --------------------------------------------------------------------------- #

@pytest.fixture()
def gefuehrt(tmp_path):
    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


def test_neuaufsetzen_archiviert_und_setzt_neu_auf(gefuehrt, tmp_path):
    ablage = gefuehrt
    alte_protokollzeilen = lies_protokoll(ablage.protokoll_pfad)
    assert alte_protokollzeilen
    fall = _fall_mit_nebentabellen(tmp_path)
    jetzt = dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc)
    provenienz = na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG, jetzt=jetzt)
    archiv = Path(provenienz["archiv"])
    # Nichts geloescht: die alte Ablage lebt vollstaendig im Archiv weiter.
    assert archiv.name == "daten.archiv-20260908T060000Z"
    assert lies_protokoll(Ablage(archiv).protokoll_pfad) == alte_protokollzeilen
    assert (archiv / "stand").exists() and (archiv / "configs" / "bestand.toml").is_file()
    # Die neue Ablage: Config, Eingang, Provenienz — noch kein Stand.
    neu = Ablage(ablage.wurzel)
    assert neu.config_pfad.read_bytes() == Ablage(archiv).config_pfad.read_bytes()
    assert (neu.uebernahme / "probe-uebernahme" / "eingang.json").is_file()
    assert json.loads((neu.wurzel / na.PROVENIENZ_DATEI).read_text(encoding="utf-8"))["archiv"] == str(archiv)
    assert not neu.stand.exists()
    # Die Erstbefuellung baut den Stand mit dem uebernommenen Bestand.
    assert tageslauf(neu, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert 7_000_001 in set(read_portfolio(neu.stand / "bestand_gesamt.parquet")["police_id"])
    assert len(lies_protokoll(neu.protokoll_pfad)) == 1


def test_neuaufsetzen_verweigert_unter_lauf_sperre_und_bei_falscher_config(gefuehrt, tmp_path):
    ablage = gefuehrt
    fall = _fall_mit_nebentabellen(tmp_path, tarifwerk={
        "scheiben_mit_gamma1": True, "stoab_je_baustein": True, "red_verfahren": "prospektiv",
    })
    with pytest.raises(na.NeuaufsetzenError, match="Tarifwerk"):
        na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG)
    assert ablage.stand.exists() and not list(tmp_path.glob("daten.archiv-*"))
    # Vorabpruefung des Eingangs (Review Schritt 9): ein falscher Stichtag
    # faellt auf, BEVOR die alte Ablage bewegt wird.
    with pytest.raises(na.NeuaufsetzenError, match="nichts bewegt") as info:
        na.neu_aufsetzen(ablage.wurzel, _fall_mit_nebentabellen(tmp_path / "c"), dt.date(2026, 3, 1))
    assert ablage.stand.exists() and not list(tmp_path.glob("daten.archiv-*"))
    # Die vorbereitete Ablage bleibt als benannter Rest liegen (die Routine
    # loescht nichts) und wird in der Meldung genannt.
    [rest] = list(tmp_path.glob("daten.neu-*"))
    assert str(rest) in str(info.value)
    # Ein anderer Prozess haelt die Sperre (flock, wie der Tageslauf).
    import fcntl
    halter = open(ablage.sperre, "a+", encoding="utf-8")
    fcntl.flock(halter.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        with pytest.raises(na.NeuaufsetzenError, match="Sperre"):
            na.neu_aufsetzen(ablage.wurzel, _fall_mit_nebentabellen(tmp_path / "b"), STICHTAG)
    finally:
        halter.close()
    # Kein Archiv — nichts wurde bewegt; der benannte Rest von oben bleibt.
    assert not list(tmp_path.glob("daten.archiv-*"))


def test_neuaufsetzen_cli(gefuehrt, tmp_path):
    fall = _fall_mit_nebentabellen(tmp_path)
    rc = na.main(["--stand", str(gefuehrt.wurzel), "--fall", str(fall), "--stichtag", STICHTAG.isoformat(),
                  "--archiv", str(tmp_path / "archiv")])
    assert rc == 0
    assert (tmp_path / "archiv" / "journal").is_dir()
    assert na.main(["--stand", str(tmp_path / "gibt-es-nicht"), "--fall", str(fall), "--stichtag", "2026-01-01"]) == 2


def test_neuaufsetzen_loescht_nichts():
    """Ratsche: die Routine kennt kein rmtree und kein unlink."""
    quelle = (REPO_ROOT / "src" / "rechner_pipeline" / "betrieb" / "neuaufsetzen.py").read_text(encoding="utf-8")
    assert "rmtree" not in quelle and ".unlink(" not in quelle and "os.remove" not in quelle
