"""Kein Abbruch blockiert den Betrieb, kein Nachlauf faerbt einen gruenen Tag rot — Angriffsrunde nach T27.

Die Klasse: Ein Abbruch an einer Naht darf nur den laufenden Schritt
kosten. Gemessen: ein Loeschen, das seinen eigenen Marker zuerst
loeschte; ein Neuaufsetzen, das im Container nicht vollendet wurde; ein
vorausdatierter Eingang, der jeden Lauf bis zum Stichtag rot machte; ein
Aufraeumen nach der Protokollzeile, das den gefuehrten Tag als Fehlschlag
meldete; Tracebacks mit Exit 1 statt einer Meldung.

Knoten: system/betrieb
"""

from __future__ import annotations

import hashlib

import datetime as dt
import os
from pathlib import Path

import pytest

from tests.freigabe_testschluessel import betriebsargs, linieargs

from rechner_pipeline.betrieb import _loeschen
from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from tests.test_betrieb_seite import _ablage
from tests.test_betrieb_uebernahme import STICHTAG, _fall, _kleine_config
from tests.test_betrieb_uebernahme import _mit_config  # noqa: E402


def test_ein_abbruch_mitten_im_loeschen_laesst_den_marker_stehen(tmp_path, monkeypatch):
    """Mutationsprobe: wieder shutil.rmtree auf den ganzen Baum -> rot."""
    wurzel = tmp_path / "w"
    ziel = wurzel / ".paket.alt"
    (ziel / "abschluesse").mkdir(parents=True)
    for name in ("a.html", "stand.json", "z.parquet", "abschluesse/x.parquet"):
        (ziel / name).write_text("x", encoding="utf-8")
    echt = os.unlink
    gesehen: list = []

    def stirbt_nach_dem_ersten(pfad, *a, **k):
        echt(pfad, *a, **k)
        gesehen.append(pfad)
        if len(gesehen) == 1:
            raise KeyboardInterrupt("Prozessende mitten im Loeschen")

    monkeypatch.setattr(os, "unlink", stirbt_nach_dem_ersten)
    with pytest.raises(KeyboardInterrupt):
        _loeschen.entferne_verzeichnis(ziel, innerhalb=wurzel, marker="stand.json", grund="t")
    monkeypatch.undo()
    assert (ziel / "stand.json").is_file(), "der Marker ging vor dem Rest"
    _loeschen.entferne_verzeichnis(ziel, innerhalb=wurzel, marker="stand.json", grund="t")
    assert not ziel.exists()


def test_ein_gescheitertes_wegraeumen_nach_dem_tausch_ist_kein_exportfehler(tmp_path, monkeypatch):
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    anker = tmp_path / "anker"
    st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=anker)
    echt = st._entferne_paket

    def scheitert_am_alten(pfad, marker, grund):
        if pfad.name == ".paket.alt":
            raise OSError(5, "I/O error")
        return echt(pfad, marker, grund)

    monkeypatch.setattr(st, "_entferne_paket", scheitert_am_alten)
    paket = st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=anker)
    monkeypatch.undo()
    assert (paket / "stand.json").is_file()
    st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=anker)
    assert not (tmp_path / ".paket.alt").exists(), "der naechste Export raeumt den Rest"


def test_neuaufsetzen_erneut_gefahren_vollendet_den_tausch(tmp_path, monkeypatch):
    """Der dokumentierte Weg nach einem Abbruch zwischen den Umbenennungen:
    dieselbe Routine erneut. Mutationsprobe: den Vollenden-Zweig in main
    entfernen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    fall = _fall_mit_nebentabellen(tmp_path)
    echt = os.rename

    def stirbt(quelle, ziel, *a, **k):
        if Path(quelle).name.startswith("daten.neu-") and Path(ziel) == ablage.wurzel:
            raise KeyboardInterrupt("Prozessende")
        return echt(quelle, ziel, *a, **k)

    monkeypatch.setattr(na.os, "rename", stirbt)
    with pytest.raises(KeyboardInterrupt):
        na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG)
    monkeypatch.undo()
    assert not ablage.wurzel.exists()
    assert na.main(["--stand", str(ablage.wurzel), "--fall", str(fall),
                    "--stichtag", STICHTAG.isoformat(),
                    *betriebsargs("--betriebsschluessel"), *linieargs()]) == 0
    assert (ablage.wurzel / na.PROVENIENZ_DATEI).is_file()
    assert not list(tmp_path.glob("daten.neu-*"))


def test_ein_vorausdatierter_eingang_ruht_bis_zu_seinem_stichtag(tmp_path):
    """Betriebsbeginn 1.12.2025, Eingang zum 1.1.2026: Die Laeufe im
    Dezember fuehren den eigenen Betrieb gruen, der Eingang wartet; am
    Stichtag tritt er ein. Vorher war jeder Lauf davor rot.
    Mutationsprobe: wartende Eingaenge nicht herausnehmen -> rot."""
    import re

    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(re.sub(
        r"^betriebsbeginn = .*$", "betriebsbeginn = 2025-12-01",
        _kleine_config(), flags=re.M), encoding="utf-8")
    ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)
    code, zeile = tageslauf(ablage, dt.date(2025, 12, 15))
    assert code == EXIT_OK, zeile.get("fehler")
    # Mit dem Hash des Eingangs (ADR-022): Die Aufnahme als wartender Eingang
    # ist sein Eintritt, ein spaeterer Lauf erkennt ihn daran wieder.
    eingang_sha = hashlib.sha256(
        (stand / "uebernahme" / "probe-uebernahme" / "eingang.json").read_bytes()).hexdigest()
    assert zeile["wartende_uebernahmen"] == [
        {"fall": "probe-uebernahme", "stichtag": "2026-01-01", "eingang_sha256": eingang_sha}]
    assert zeile["uebernahmen"] == []
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 5))
    assert code == EXIT_OK, zeile.get("fehler")
    assert [u["fall"] for u in zeile["uebernahmen"]] == ["probe-uebernahme"]


def test_ein_gescheitertes_aufraeumen_nach_der_zeile_faerbt_den_tag_nicht_rot(tmp_path, monkeypatch):
    """Mutationsprobe: das Wegraeumen des Markers wieder in den Fehlerpfad
    der Zeile -> rot."""
    ablage = _ablage(tmp_path / "plv")

    def scheitert(_ablage):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "entferne_publish_marker", scheitert)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    monkeypatch.undo()
    assert code == EXIT_OK and zeile["uebernommen"] is True
    assert lies_protokoll(ablage.protokoll_pfad)[-1]["uebernommen"] is True
    assert tageslauf(ablage, dt.date(2026, 2, 4))[0] == EXIT_OK


def test_ein_ausgabefehler_der_registrierung_ist_eine_meldung(tmp_path, monkeypatch, capsys):
    fall = _fall(tmp_path)

    def voll(*a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(ueb, "eingang_anlegen", voll)
    code = ueb.main(["--stand", str(tmp_path / "daten"), "--fall", str(fall),
                     "--stichtag", STICHTAG.isoformat(), *betriebsargs("--betriebsschluessel"),
                     *linieargs()])
    assert code == 2 and "Ein-/Ausgabefehler" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# RC06 (Angriffsrunde C): ein leerer Abschluss ist keine Abweichung
# --------------------------------------------------------------------------- #


def test_ein_wiederanlauf_weist_den_leeren_eroeffnungsabschluss_nicht_als_befund_aus(
        tmp_path, monkeypatch):
    """Ein Unternehmen beginnt leer (ADR-020): Der Eroeffnungsabschluss ist
    eine gueltige leere Bilanz, und der ungestoerte Lauf traegt keinen
    Befund. Nach einem Ausfall im Publish-Fenster rechnete der Wiederanlauf
    denselben Abschluss nach und schrieb 'abschluss: leer' in die gruene,
    verkettete Zeile — dieselben Bytes, dauerhaft anderer Befund.
    Mutationsprobe: pruefe_abschluss gibt fuer eine leere Datei wieder
    pauschal den Befund 'leer' zurueck -> rot."""
    ref = _ablage(tmp_path / "ref")
    assert tageslauf(ref, dt.date(2026, 1, 31))[0] == EXIT_OK
    a_ref = lies_protokoll(ref.protokoll_pfad)[-1]["abschluesse"][0]
    assert a_ref["in_kraft"] == 0 and "befunde" not in a_ref, "Voraussetzung: leerer Eroeffnungsabschluss"

    ausfall = _ablage(tmp_path / "ausfall")

    def stirbt_im_publish(*_a, **_k):
        raise OSError(5, "I/O error im Publish-Fenster")

    monkeypatch.setattr(tl, "_uebernehmen", stirbt_im_publish)
    code, _ = tageslauf(ausfall, dt.date(2026, 1, 31))
    monkeypatch.undo()
    assert code != EXIT_OK
    assert tl.abschluss_pfad(ausfall.abschluesse, dt.date(2026, 1, 1)).is_file(), (
        "Voraussetzung: der gescheiterte Lauf hat den Abschluss schon festgeschrieben")
    code, zeile = tageslauf(ausfall, dt.date(2026, 1, 31))
    assert code == EXIT_OK, zeile.get("fehler")
    a_ist = zeile["abschluesse"][0]
    assert a_ist["nachgerechnet"] is True and a_ist["sha256"] == a_ref["sha256"]
    assert a_ist.get("befunde") is None, a_ist.get("befunde")


def test_ein_leerer_abschluss_ueber_einem_gefuellten_stichtag_bleibt_ein_befund(tmp_path, monkeypatch):
    """Das Gegenstueck: Die Datei traegt keinen Stichtag, der Dateiname sagt
    ihn. Ein Abschluss, der leer ist, obwohl die Neuberechnung des
    benannten Stichtags Vertraege in Kraft findet, ist abgeschnitten und
    wird ausgewiesen — 'leer ist gueltig' darf nicht zu 'leer ist immer
    gut' werden. Mutationsprobe: leere Datei -> immer [] -> rot."""
    import stat

    from rechner_pipeline.bestand.parquet_io import write_portfolio
    from rechner_pipeline.models.bestand import ABSCHLUSS_NAMES, ABSCHLUSS_SPALTEN

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK

    def _kein_bericht(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "_bericht", _kein_bericht)
    assert tageslauf(ablage, dt.date(2026, 3, 2))[0] != EXIT_OK
    monkeypatch.undo()
    feb = tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 2, 1))
    assert len(tl.read_portfolio(feb)) > 0, "Voraussetzung: der Februar ist gefuellt"
    feb.chmod(stat.S_IMODE(feb.stat().st_mode) | 0o200)
    import pandas as pd
    write_portfolio(pd.DataFrame(
        {n: pd.Series(dtype=d) for n, d in ABSCHLUSS_SPALTEN})[list(ABSCHLUSS_NAMES)], feb)
    code, zeile = tageslauf(ablage, dt.date(2026, 3, 2))
    assert code == EXIT_OK, zeile.get("fehler")
    eintrag = {a["stichtag"]: a for a in zeile["abschluesse"]}["2026-02-01"]
    assert eintrag["nachgerechnet"] is True
    assert any("leer" in b and "2026-02-01" in b for b in eintrag.get("befunde", [])), eintrag
