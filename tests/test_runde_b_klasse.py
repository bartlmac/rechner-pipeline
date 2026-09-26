"""Die bestaetigten Funde der Angriffsrunde B nach T27, je als Klasse.

Jeder Test fuehrt die Stoerung des Angreifers nach und verlangt den
Zustand des ungestoerten Laufs bzw. die Abweisung. Die Klassen:
Belege eines nachgerechneten Abschlusses, kein Export aus einem
unterbrochenen Lauf, eigene Reste des Exports, Eingangsfehler statt
Traceback, der Schluessel vor jedem Aufbau, jede mitgebrachte Tabelle
bezeugt, die Zahlen der letzten Zeile aus dem Stand, kein Eingang
verschwindet, eine Lesung je Paketdatei, kein negativer Wert aus der
Herabsetzung mit Abzug, kein Bericht ueber eine unpruefbare Herabsetzung.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, tageslauf
from rechner_pipeline.models import anker as ak
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import STICHTAG, _beleg_neu, _fall, _kleine_config

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "werkzeuge"))
import falldaten as fd  # noqa: E402


@pytest.fixture()
def gefuehrt(tmp_path):
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage


# --- Betrieb -------------------------------------------------------------------


def test_ein_nachgerechneter_abschluss_behaelt_seinen_beleg_in_seite_und_paket(tmp_path, monkeypatch):
    """Mutationsprobe: in abschluesse_aus_protokoll nur neue Eintraege
    belegen -> rot."""
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK

    def kein_bericht(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "_bericht", kein_bericht)
    assert tageslauf(ablage, dt.date(2026, 2, 2))[0] != EXIT_OK
    monkeypatch.undo()
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    modell = st.stand_modell(ablage)
    feb = next(a for a in modell["abschluesse"] if a["stichtag"] == "2026-02-01")
    assert feb.get("datei") and feb.get("sha256"), feb
    paket = st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert (paket / "abschluesse" / feb["datei"]).is_file()


def test_eine_vertragszahl_ohne_abschlussdatei_wird_nicht_veroeffentlicht(gefuehrt, tmp_path):
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
    mit_zahl = [a for a in stand["abschluesse"] if a.get("in_kraft") is not None]
    assert mit_zahl
    mit_zahl[-1]["datei"] = None
    (paket / "stand.json").chmod(0o644)
    (paket / "stand.json").write_text(json.dumps(stand, sort_keys=True), encoding="utf-8")
    with pytest.raises(fd.FalldatenFehler, match="ohne Abschlussdatei"):
        fd._pruefe_abschluesse_gegen_das_protokoll(paket, stand, stand["dateien"])


def test_kein_export_aus_einem_unterbrochenen_lauf(gefuehrt, tmp_path):
    """Mutationsprobe: die beiden Pruefungen im Export entfernen -> rot."""
    gefuehrt.publish_marker.write_text("{}", encoding="utf-8")
    with pytest.raises(st.SeiteError, match="nicht abgeschlossen"):
        st.stands_paket(gefuehrt, tmp_path / "p1", anker_verzeichnis=tmp_path / "anker")
    gefuehrt.publish_marker.unlink()
    roh = gefuehrt.protokoll_pfad.read_bytes()
    gefuehrt.protokoll_pfad.chmod(0o644)
    gefuehrt.protokoll_pfad.write_bytes(roh + b'{"halb": 1}')
    with pytest.raises(st.SeiteError, match="nicht abgeschlossen"):
        st.stands_paket(gefuehrt, tmp_path / "p2", anker_verzeichnis=tmp_path / "anker")


def test_eine_zeile_ohne_zeilenende_ist_keine_zeile():
    assert ak.jsonl_zeilen('{"a": 1}\n{"b": 2}') == ['{"a": 1}']


def test_ein_leerer_beiseite_ort_blockiert_den_export_nicht(gefuehrt, tmp_path):
    """Mutationsprobe: den Leer-Zweig fuer .alt entfernen -> rot."""
    st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    (tmp_path / ".paket.alt").mkdir()
    st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert not (tmp_path / ".paket.alt").exists()


@pytest.mark.parametrize("kaputt", [b"[meta]\nname = \"x\"\n[[generation", b"[meta]\nname = \"\xe2\x82"])
def test_eine_halbe_config_ist_ein_eingangsfehler(tmp_path, kaputt, capsys):
    ablage = _ablage(tmp_path / "plv")
    ablage.config_pfad.chmod(0o644)
    ablage.config_pfad.write_bytes(kaputt)
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-02-03"]) == tl.EXIT_USAGE
    assert "nicht lesbar" in capsys.readouterr().err
    fall = _fall(tmp_path / "f")
    assert ueb.main(["--stand", str(ablage.wurzel), "--fall", str(fall),
                     "--stichtag", STICHTAG.isoformat()]) == 2


def test_neuaufsetzen_ohne_schluessel_baut_nichts(tmp_path, monkeypatch):
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    monkeypatch.setattr(ueb, "_STANDARD_SCHLUESSELRING", None)
    with pytest.raises(na.NeuaufsetzenError, match="Freigabeschluessel"):
        na.neu_aufsetzen(ablage.wurzel, _fall_mit_nebentabellen(tmp_path), STICHTAG)
    assert not list(tmp_path.glob("daten.neu-*"))


def test_eine_nicht_bezeugte_nebentabelle_wird_nicht_registriert(tmp_path):
    """Mutationsprobe: unbezeugte Nebentabellen wieder durchlassen -> rot."""
    import pandas as pd

    from rechner_pipeline.bestand.parquet_io import write_portfolio
    from rechner_pipeline.models.bestand import VERANKERUNG_SPALTEN

    fall = _fall(tmp_path)
    verankerung = pd.DataFrame([{"police_id": 7_000_001, "monate_ta": 60, "zustand_ta": "beitragspflichtig",
                                 "verweildauer_ta": 0, "dk_ta": 10_000.0}])
    verankerung = verankerung[[s for s, _ in VERANKERUNG_SPALTEN]].astype(dict(VERANKERUNG_SPALTEN))
    write_portfolio(verankerung, fall / "abgeleitet" / "bestand" / "verankerung.parquet")
    with pytest.raises(ueb.UebernahmeError, match="verankerung.parquet"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)
    _beleg_neu(fall)                                   # Positivkontrolle: bezeugt -> registriert
    ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)


def test_die_zahlen_der_letzten_zeile_folgen_aus_dem_stand(gefuehrt, tmp_path):
    """Mutationsprobe: _pruefe_zahlen_der_zeile nicht rufen -> rot."""
    zeilen = [z for z in gefuehrt.protokoll_pfad.read_text(encoding="utf-8").split("\n") if z.strip()]
    letzte = json.loads(zeilen[-1])
    letzte["bestand"]["in_force"] = int(letzte["bestand"]["in_force"]) + 1000
    zeilen[-1] = json.dumps(letzte, ensure_ascii=False, sort_keys=True)
    gefuehrt.protokoll_pfad.chmod(0o644)
    gefuehrt.protokoll_pfad.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    with pytest.raises(st.SeiteError, match="nicht aus dem Stand folgen"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


def test_ein_gefuehrter_eingang_verschwindet_nicht(tmp_path):
    """Mutationsprobe: die Pruefung auf fehlende bezeugte Eingaenge entfernen -> rot."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    ziel.rename(ziel.parent / "anders-benannt")
    with pytest.raises(tl.TageslaufError, match="nicht mehr in der Ablage"):
        tageslauf(ablage, dt.date(2026, 2, 4))


def test_jede_paketdatei_wird_einmal_gelesen(gefuehrt, tmp_path, monkeypatch):
    """Der Angreifer: stand.json meldet doppelt so viele Buchungen, und das
    Journal wird nach der ersten (gehashten) Lesung durch eine verdoppelte
    Fassung ersetzt — die Zaehlung der zweiten Lesung bestaetigte die
    falsche Zahl. Mutationsprobe: das Paket nicht einfrieren -> rot."""
    import pandas as pd

    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    anker = tmp_path / "anker"
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=anker)
    stand = json.loads((paket / "stand.json").read_text(encoding="utf-8"))
    echt = stand["buchungen"]["gesamt"]
    stand["buchungen"]["gesamt"] = 2 * echt
    (paket / "stand.json").chmod(0o644)
    (paket / "stand.json").write_text(json.dumps(stand, sort_keys=True), encoding="utf-8")
    journal = paket / "tagesjournal.parquet"
    doppelt = pd.concat([read_portfolio(journal)] * 2, ignore_index=True)
    lies = Path.read_bytes
    gelesen: list = []

    def tauscht(self):
        roh = lies(self)
        if self == journal and not gelesen:
            gelesen.append(self)
            journal.chmod(0o644)
            write_portfolio(doppelt, journal)
        return roh

    monkeypatch.setattr(Path, "read_bytes", tauscht)
    try:
        with pytest.raises(fd.FalldatenFehler, match="Buchungen"):
            fd.betrieb(paket, anker / ak.ANKER_DATEI)
    finally:
        monkeypatch.undo()
    assert gelesen, "die Probe hat das Journal nie gelesen"


# --- Herabsetzung --------------------------------------------------------------


@pytest.mark.parametrize("summe", [300.0, 1000.0, 1700.0])
@pytest.mark.parametrize("a0", [1, 2, 3])
def test_mit_abzug_wird_nie_negativ_und_liegt_nie_ueber_prospektiv(summe, a0):
    """Der Abzug ist hoechstens die Rueckstellung. Mutationsprobe: den
    Abzug wieder unbegrenzt -> rot."""
    import dataclasses

    from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
    from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV, reduziere

    kern = Rechenkern(dataclasses.replace(KLV_DEFAULT, sum_insured=summe))
    for f in (0.03, 0.1, 0.6):
        mit = reduziere(kern, a0, f, verfahren=MIT_ABZUG)
        pro = reduziere(kern, a0, f, verfahren=PROSPEKTIV)
        assert mit.vs_neu >= f * summe - 1e-9, (summe, a0, f, mit.vs_neu)
        assert mit.vs_neu <= pro.vs_neu + 1e-9


def test_der_bericht_verweigert_eine_herabsetzung_ohne_config(tmp_path):
    """Mutationsprobe: die Ausnahme fuer den Bericht wieder einfuehren -> rot."""
    from rechner_pipeline.bestand import cli_report as cli
    from tests.test_herabsetzung_in_fuehrung import _lauf_mit_herabsetzung

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    argv = ["--portfolio", str(out / "bestand_gesamt.parquet"), "--historie", str(out / "historie.parquet"),
            "--ledger", str(out / "ledger.parquet"), "--scheiben", str(out / "scheiben.parquet"),
            "--bis", "2046-01-01", "--stichtag", "2030-01-01", "--out", str(tmp_path / "b.html")]
    assert cli.main(argv) == 2
    assert cli.main(argv + ["--config", str(cfg)]) == 0             # Positivkontrolle


def test_der_dokumentierte_bericht_mit_config_und_merkmalen_laeuft_auf_einer_zellen_generation(gefahrener_fall):
    """Die Merkmale gehen auch in die Pruefung. Mutationsprobe: merkmale
    nicht in die Eingaben der Pruefung legen -> rot."""
    from rechner_pipeline.bestand import cli_report as cli

    nach = gefahrener_fall / "abgeleitet" / "bestand-nach"
    bestand = gefahrener_fall / "abgeleitet" / "bestand"
    code = cli.main([
        "--portfolio", str(nach / "bestand_gesamt.parquet"), "--historie", str(nach / "historie.parquet"),
        "--ledger", str(nach / "ledger.parquet"), "--scheiben", str(nach / "scheiben.parquet"),
        "--merkmale", str(bestand / "merkmale.parquet"),
        "--config", str(gefahrener_fall / "abgeleitet" / "bestand-config.toml"),
        "--bis", "2027-01-01", "--stichtag", "2026-01-01",
        "--out", str(nach / "bericht-probe.html")])
    assert code == 0


from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: E402,F401
