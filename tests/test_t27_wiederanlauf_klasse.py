"""Wiederanlauf und Registrierung als Klasse — Pruefrunde T27, Befunde 01, 02, 03 und A27-01.

Die Klasse hinter den vier Befunden: Ein Reparatur- oder Wiederanlaufpfad
darf belegte Bytes nie neu schreiben, muss den Publikationszustand aus der
Sache lesen (nicht aus einem Stellvertreter, nicht zum falschen Zeitpunkt),
und eine historische Sicht setzt Stamm und Historie gemeinsam auf den
Stichtag. Jeder Test hier injiziert einen Ausfall oder einen
Betriebszustand, den der Gutachter gemessen hat, und verlangt den Zustand
des ungestoerten Laufs.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path

import pandas as pd
import pytest

from tests.freigabe_testschluessel import betriebsargs

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
    STATUS_HISTORIE_SPALTEN,
)
from tests.test_betrieb_uebernahme import (
    fuehrungsbeleg,
    uebernahmebeleg,
    PLV,
    STICHTAG,
    _fall,
    _kleine_config,
    _pb1_ledger,
    am4_snapshot,
)
from tests.test_betrieb_uebernahme import _mit_config  # noqa: E402


# --------------------------------------------------------------------------- #
# T27-01: der Teilzeilenschnitt schreibt belegte Zeilen nie neu
# --------------------------------------------------------------------------- #


def _protokoll(pfad: Path, zeilen: int = 3) -> bytes:
    voll = b"".join(
        json.dumps({"heute": f"2026-01-0{i + 1}", "uebernommen": True}).encode() + b"\n"
        for i in range(zeilen))
    pfad.write_bytes(voll + b'{"heute": "2026-01-0')
    return voll


def test_der_teilzeilenschnitt_schreibt_belegte_zeilen_nie_neu(tmp_path, monkeypatch):
    """Die Ratsche am Verhalten: Waehrend des Schnitts ist jeder Schreibpfad
    verboten, der die Datei neu anlegt — belegte Zeilen sind Beweismaterial
    (T24-04). Mutationsprobe: ``write_bytes(roh[:schnitt])`` -> rot."""
    pfad = tmp_path / "protokoll.jsonl"
    voll = _protokoll(pfad)

    def _verboten(self, *a, **k):
        raise AssertionError(f"Neuschreiben von {self}: belegte Zeilen gehen durch keinen Schreibpfad")

    monkeypatch.setattr(Path, "write_bytes", _verboten)
    monkeypatch.setattr(Path, "write_text", _verboten)
    assert tl._schneide_teilzeile(pfad) is True
    assert pfad.read_bytes() == voll
    assert tl._schneide_teilzeile(pfad) is False


def test_ein_ausfall_im_schnitt_laesst_die_datei_wie_sie_war(tmp_path, monkeypatch):
    """Der zweite Ausfall des Gutachters (T27-01): Scheitert der Schnitt
    selbst, bleibt die Datei, wie sie war — nicht leer. Der saubere Retry
    schneidet dann."""
    pfad = tmp_path / "protokoll.jsonl"
    voll = _protokoll(pfad)
    vorher = pfad.read_bytes()

    def _kaputt(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl.os, "truncate", _kaputt)
    with pytest.raises(OSError):
        tl._schneide_teilzeile(pfad)
    monkeypatch.undo()
    assert pfad.read_bytes() == vorher, "der Reparaturpfad hat belegte Bytes angefasst"
    assert tl._schneide_teilzeile(pfad) is True
    assert pfad.read_bytes() == voll


def test_die_angefangene_zeile_eines_roten_laufs_sperrt_die_ablage_nicht(tmp_path):
    """Kalibrierungsfund N7: Der Schnitt lief nur unter dem Publish-Marker;
    ein roter Lauf setzt keinen. Sein Fragment machte das Protokoll fuer
    jeden folgenden Lauf unlesbar — dauerhaft. Mutationsprobe: den Schnitt
    am Laufanfang entfernen -> rot."""
    from tests.test_betrieb_tageslauf import _ablage
    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    vorher = ablage.protokoll_pfad.read_bytes()
    assert vorher.endswith(b"\n") and not ablage.publish_marker.exists()
    with open(ablage.protokoll_pfad, "ab") as f:
        f.write(b'{"heute": "2026-02-03", "uebernommen": false, "fehler": "Pl')
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    zeilen = lies_protokoll(ablage.protokoll_pfad)
    assert [z["heute"] for z in zeilen] == ["2026-01-31", "2026-02-03"]
    assert ablage.protokoll_pfad.read_bytes().startswith(vorher)


# --------------------------------------------------------------------------- #
# T27-02: ein eingerechneter Eingang bleibt erkannt, auch wenn seine
# Vertraege spaeter ablaufen — gefragt wird der Abschluss seines Stichtags
# --------------------------------------------------------------------------- #


def _abschluss(ablage: Ablage, tag: dt.date, police_ids) -> None:
    """Ein Abschluss in voller Gestalt (seit 2026-10-01 liest jeder Leser ihn
    ueber lies_abschluss, und eine Tabelle nur mit police_id ist keiner)."""
    from rechner_pipeline.models.bestand import ABSCHLUSS_SPALTEN

    ablage.abschluesse.mkdir(parents=True, exist_ok=True)
    zeilen = [{"police_id": int(p), "stichtag": pd.Timestamp(tag), "produkt": "klv",
               "tarif_generation": "KLV-2017", "status_code": "POL", "leistung": 1.0,
               "deckungskapital": 1.0, "rueckkaufswert": 1.0, "korrekturschicht": 0.0,
               "vs_bfr": 0.0, "jahresbeitrag": 1.0, "kern_version": "x",
               "bewertungskonvention": "monatsgenau"} for p in police_ids]
    tabelle = pd.DataFrame(zeilen, columns=[n for n, _ in ABSCHLUSS_SPALTEN]).astype(
        dict(ABSCHLUSS_SPALTEN))
    write_portfolio(tabelle, tl.abschluss_pfad(ablage.abschluesse, tag))


def test_der_abschluss_des_zugangsstichtags_entscheidet_nicht_der_juengste(tmp_path):
    """Mutationsprobe: wieder den juengsten Abschluss fragen -> rot (Februar
    und Maerz kennen die abgelaufenen Vertraege nicht mehr)."""
    ablage = Ablage(tmp_path / "daten")
    ids = [1, 2, 3]
    _abschluss(ablage, dt.date(2026, 1, 1), ids)     # hier trat der Eingang ein
    _abschluss(ablage, dt.date(2026, 2, 1), [])      # danach: alle abgelaufen
    _abschluss(ablage, dt.date(2026, 3, 1), [])
    assert tl._eingang_eingerechnet(ablage, dt.date(2026, 1, 1), ids) is True
    # Gegenrichtung (ADR-011): den Eingang kennt der Abschluss seines
    # Stichtags NICHT -> nicht eingerechnet, der Lauf muss ihn abweisen.
    assert tl._eingang_eingerechnet(ablage, dt.date(2026, 1, 1), [9]) is False
    # Noch kein Abschluss ab dem Stichtag: offen, kein Widerspruch.
    assert tl._eingang_eingerechnet(ablage, dt.date(2026, 4, 1), ids) is None


def _kurzer_zugangsstand(ziel: Path, *, mit_pex: bool) -> None:
    """Drei (bzw. ein) Vertraege der Generation KLV-2017, Beginn 2021-02-01,
    Laufzeit fuenf Jahre: Sie laufen am 2026-02-01 ab — einen Monat nach
    dem Zugang. Genau der Betriebszustand des Gutachters (T27-02, A27-01)."""
    beginn = pd.Timestamp("2021-02-01")
    zeilen = []
    lagen = [("POL", 7_000_001), ("POL", 7_000_002), ("PEX", 7_000_003)] if mit_pex else [("POL", 7_000_001)]
    for status, pid in lagen:
        zeilen.append({
            "police_id": pid, "tarif_generation": "KLV-2017", "produkt": "klv",
            "status_id": 2 if status == "PEX" else 1, "status_code": status,
            "status_date": pd.Timestamp("2023-11-01") if status == "PEX" else beginn,
            "sex": "F", "date_of_birth": beginn - pd.DateOffset(years=35), "entry_age": 35,
            "duration": 5, "premium_duration": 5, "sum_insured": 60000.0, "bu_rente": 0.0,
            "zahlweise": 12, "insurance_start": beginn, "insurance_end": beginn + pd.DateOffset(years=5),
            "payment_end": beginn + pd.DateOffset(years=5), "bestandszugang": pd.Timestamp(STICHTAG),
        })
    stamm = pd.DataFrame(zeilen)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))
    hist_zeilen = [{"police_id": 7_000_003, "status_id": 2, "status_code": "PEX",
                    "status_date": pd.Timestamp("2023-11-01")}] if mit_pex else []
    historie = pd.DataFrame(hist_zeilen, columns=[n for n, _ in STATUS_HISTORIE_SPALTEN]).astype(
        dict(STATUS_HISTORIE_SPALTEN))
    vj = (pd.Timestamp(STICHTAG).year * 12 + 1 - (beginn.year * 12 + beginn.month)) // 12
    ledger_zeilen = [{
        "police_id": int(z["police_id"]), "tarif_generation": "KLV-2017", "ereignis": "ZUG",
        "vertragsjahr": int(vj), "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS",
        "betrag": 60000.0, "betrag_herkunft": "geliefert",
    } for z in zeilen]
    if mit_pex:
        gen = next(g for g in load_config(PLV).generationen if g.name == "KLV-2017")
        kern = Rechenkern(ModelPoint(x=35, sex="F", n=5, t=5, sum_insured=60000.0, zw=12,
                                     **gen.generation_fields()))
        ledger_zeilen.append({
            "police_id": 7_000_003, "tarif_generation": "KLV-2017", "ereignis": "PEX",
            "vertragsjahr": int(vj), "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS",
            "betrag": float(kern.beitragsfreie_summe(2)), "betrag_herkunft": "gerechnet",
        })
    ledger = pd.DataFrame(ledger_zeilen)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    ziel.mkdir(parents=True, exist_ok=True)
    write_portfolio(stamm, ziel / "bestand.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")
    uebernahmebeleg(ziel, len(stamm))


def _kurzer_fall(wurzel: Path, *, mit_pex: bool, name: str = "kurz-uebernahme") -> Path:
    fall = wurzel / name
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "entscheide").mkdir()
    (fall / "fall.json").write_text(json.dumps({"name": name, "schema_version": 1}), encoding="utf-8")
    _kurzer_zugangsstand(fall / "abgeleitet" / "bestand", mit_pex=mit_pex)
    from tests.test_betrieb_uebernahme import lege_auftrag

    lege_auftrag(fall)   # der Auftrag, den A-M4 nennt (Pruefrunde I, I07)
    daten = am4_snapshot(name, pb1_ledger_sha=_pb1_ledger(fall), fuehrungsprobe_sha=fuehrungsbeleg(fall))
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    return fall


def _betrieb(tmp_path, *, mit_pex: bool):
    fall = _kurzer_fall(tmp_path, mit_pex=mit_pex)
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    return ablage


def test_ein_nachhollauf_ueber_den_ablauf_hinweg_laeuft_nach_einem_berichtsfehler_wieder_an(tmp_path, monkeypatch):
    """T27-02 in der Welt des Gutachters: Zugang 01.01., Ablauf 01.02.,
    Nachholen bis 02.03.; nur der Monatsbericht scheitert. Der Retry muss
    Exit 0 sein — der Eingang ist eingerechnet, der Januarabschluss
    traegt ihn, dass Februar und Maerz ihn nicht mehr tragen, ist der
    normale Lauf der Dinge."""
    ablage = _betrieb(tmp_path, mit_pex=True)

    def _kein_bericht(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "_bericht", _kein_bericht)
    code, zeile = tageslauf(ablage, dt.date(2026, 3, 2))
    monkeypatch.undo()
    assert code != EXIT_OK and zeile["uebernommen"] is False
    januar = tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 1, 1))
    maerz = tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 3, 1))
    assert januar.is_file() and maerz.is_file(), "ohne Abschluesse ueber den Ablauf hinweg prueft der Test nichts"
    # Der Eingang wird auf das Nummernband des Betriebs umnummeriert (1..3);
    # der Januarabschluss traegt genau diese Zielnummern, der Maerz keine mehr.
    ziel_ids = {1, 2, 3}
    assert ziel_ids <= set(int(p) for p in read_portfolio(januar)["police_id"])
    assert not (set(int(p) for p in read_portfolio(maerz)["police_id"]) & ziel_ids)

    code, zeile = tageslauf(ablage, dt.date(2026, 3, 2))
    assert code == EXIT_OK, f"der Retry gelingt nicht: {zeile.get('fehler')}"
    assert zeile["uebernommen"] is True
    # Positivkontrolle: ohne den Berichtsfehler ist derselbe Lauf gruen.
    frisch = _betrieb(tmp_path / "kontrolle", mit_pex=True)
    assert tageslauf(frisch, dt.date(2026, 3, 2))[0] == EXIT_OK


# --------------------------------------------------------------------------- #
# A27-01: die historische Sicht setzt Stamm und Historie auf denselben Stichtag
# --------------------------------------------------------------------------- #


def test_ein_historischer_abschluss_vor_dem_ablauf_ist_rechenbar(tmp_path):
    """Ein Vertrag ohne Vorgeschichte, der am 01.02. ablaeuft: Der
    Januarabschluss schneidet die Historie vor den Ablauf (leer), der Stamm
    trug den terminalen Status von heute — die Bewertung verweigerte
    ("Folgezustand ... keine Historie"), Exit 4, dauerhaft. Stamm und
    Historie gehoeren gemeinsam auf den Stichtag."""
    ablage = _betrieb(tmp_path, mit_pex=False)
    code, zeile = tageslauf(ablage, dt.date(2026, 3, 2))
    assert code == EXIT_OK, zeile.get("fehler")
    januar = read_portfolio(tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 1, 1)))
    assert 1 in set(int(p) for p in januar["police_id"])        # Zielnummer des einen Vertrags
    maerz = read_portfolio(tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 3, 1)))
    assert 1 not in set(int(p) for p in maerz["police_id"])


# --------------------------------------------------------------------------- #
# T27-03: ein vollstaendiges, nie veroeffentlichtes Staging sperrt den
# Writer nicht — der Publikationszustand ist das Ziel, nicht der Marker
# --------------------------------------------------------------------------- #


def test_ein_vollstaendiges_staging_ohne_publikation_blockiert_die_wiederholung_nicht(tmp_path, monkeypatch):
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"

    def _kein_rename(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(os, "rename", _kein_rename)
    with pytest.raises(OSError):
        ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)
    monkeypatch.undo()
    rest = stand / ueb.STAGING_DIR / "probe-uebernahme"
    ziel = stand / ueb.UEBERNAHME_DIR / "probe-uebernahme"
    assert rest.is_dir() and (rest / ueb.EINGANG_DATEI).is_file() and not ziel.exists()
    # Der Reader bleibt frei: nichts ist veroeffentlicht.
    assert ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, load_config(PLV)) == []
    # Die Wiederholung derselben Registrierung gelingt und raeumt den Rest weg.
    assert ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG) == ziel
    assert ziel.is_dir() and not rest.exists()
    # Ein VEROEFFENTLICHTER Eingang wird weiterhin nie ueberschrieben.
    with pytest.raises(ueb.UebernahmeError, match="nie ueberschrieben"):
        ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)


# --------------------------------------------------------------------------- #
# Kalibrierungsfunde der zweiten Runde: N8 (Ankerreihe) und N9 (Config-Naht)
# --------------------------------------------------------------------------- #


def test_ein_abgebrochenes_anfuegen_macht_die_ankerreihe_nicht_unlesbar(tmp_path):
    """N8: Teilwrite ohne Umbruch, danach ein sauberer Export. Vorher: beide
    Saetze verschmolzen, lies_anker warf dauerhaft 'Zeile 3 ist kein JSON'.
    Mutationsprobe: _schneide_fragment in haenge_an nicht rufen -> rot."""
    from rechner_pipeline.models import anker

    d = tmp_path / "anker"
    anker.haenge_an(d, {"n": 1})
    anker.haenge_an(d, {"n": 2})
    pfad = d / anker.ANKER_DATEI
    vorher = pfad.read_bytes()
    with open(pfad, "ab") as f:
        f.write(b'{"n": 3, "abgebro')
    assert [s["n"] for s in anker.lies_anker(pfad)] == [1, 2]
    anker.haenge_an(d, {"n": 4})
    assert [s["n"] for s in anker.lies_anker(pfad)] == [1, 2, 4]
    assert pfad.read_bytes().startswith(vorher)


def test_neuaufsetzen_prueft_die_config_die_es_schreibt(tmp_path, monkeypatch):
    """N9: Nach dem ersten Lesen der Config wird die Datei getauscht (hier:
    unbrauchbar gemacht). Die Pruefung muss auf den gelesenen Bytes laufen —
    die neue Ablage traegt sie. Mutationsprobe: load_config(pfad) statt
    config_aus_text(bytes) -> der zweite Lesevorgang sieht Muell -> rot."""
    import pathlib

    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    fall = _fall_mit_nebentabellen(tmp_path)
    original = ablage.config_pfad.read_bytes()
    echtes_read_bytes = pathlib.Path.read_bytes
    gelesen: list = []

    def tauschend(self):
        inhalt = echtes_read_bytes(self)
        if self == ablage.config_pfad:
            gelesen.append(self)
            if len(gelesen) == 1:
                echtes_write = pathlib.Path.write_bytes
                echtes_write(self, b"[meta]\nkaputt = \n")
        return inhalt

    monkeypatch.setattr(pathlib.Path, "read_bytes", tauschend)
    provenienz = na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG,
                                  jetzt=dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc))
    monkeypatch.undo()
    assert gelesen, "die Config wurde nie ueber read_bytes gelesen"
    assert Ablage(ablage.wurzel).config_pfad.read_bytes() == original
    assert provenienz["config_sha256"] == ueb.sha256_bytes(original)


def test_ein_nachgerechneter_abschluss_wird_belegt_wie_ein_neuer(tmp_path, monkeypatch):
    """Angriffsrunde (Betrieb): Scheitert ein Lauf nach dem Schreiben der
    Abschluesse, trug der Retry sie nur als "nachgerechnet" ohne sha256,
    Monatskennzahlen und Bericht ein — der Beleg war dauerhaft weg. Und
    ein Abschluss, dessen chmod ausfiel, blieb schreibbar.
    Mutationsprobe: den Eintrag des nachgerechneten Abschlusses wieder
    ohne sha256 bauen -> rot."""
    import stat

    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK

    def _kein_bericht(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "_bericht", _kein_bericht)
    code, _ = tageslauf(ablage, dt.date(2026, 3, 2))
    monkeypatch.undo()
    assert code != EXIT_OK
    feb = tl.abschluss_pfad(ablage.abschluesse, dt.date(2026, 2, 1))
    assert feb.is_file(), "der gescheiterte Lauf hat keinen Abschluss geschrieben"
    feb.chmod(0o644)                     # das ausgefallene chmod
    code, zeile = tageslauf(ablage, dt.date(2026, 3, 2))
    assert code == EXIT_OK, zeile.get("fehler")
    eintraege = {a["stichtag"]: a for a in zeile["abschluesse"]}
    for tag in ("2026-02-01", "2026-03-01"):
        a = eintraege[tag]
        assert a.get("sha256") and "in_kraft" in a, a
    assert eintraege["2026-03-01"].get("bericht"), eintraege["2026-03-01"]
    assert stat.S_IMODE(feb.stat().st_mode) == 0o444


def test_ein_ein_ausgabefehler_im_vorlauf_hat_einen_exit_code_des_vertrags(tmp_path, monkeypatch):
    """Angriffsrunde (Betrieb): Ein Ausfall in der Ruecknahme (Vorlauf unter
    der Sperre) endete mit Traceback und Exit 1 — kein Code des Vertrags.
    Mutationsprobe: den OSError-Fang in main entfernen -> rot."""
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK

    def _kaputt(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "nimm_publish_zurueck", _kaputt)
    code = tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-02-03", *betriebsargs()])
    assert code == tl.EXIT_USAGE


def test_ein_fehlender_stand_bei_gefuehrtem_protokoll_ist_kein_neuanfang(tmp_path):
    """Angriffsrunde (Betrieb): Fehlt das Pfadobjekt 'stand', fing der Lauf
    still von vorn an und zerstoerte die Protokollkette. Mutationsprobe:
    die Pruefung entfernen -> rot."""
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    vorher = ablage.protokoll_pfad.read_bytes()
    ablage.stand.unlink()
    with pytest.raises(tl.TageslaufError, match="Stand und Nachweis"):
        tageslauf(ablage, dt.date(2026, 2, 3))
    assert ablage.protokoll_pfad.read_bytes() == vorher


# --------------------------------------------------------------------------- #
# Angriffsrunde Betrieb: Prozessende zwischen den zwei Umbenennungen
# --------------------------------------------------------------------------- #


def test_ein_prozessende_zwischen_den_umbenennungen_laesst_den_betrieb_nicht_ohne_ablage(tmp_path, monkeypatch):
    """neuaufsetzen archiviert die alte Ablage und setzt die neue mit einer
    zweiten Umbenennung an ihre Stelle. Endet der Prozess dazwischen, legte
    der naechste Tageslauf eine LEERE Wurzel an und fuehrte von vorn. Die
    fertig gebaute neue Ablage (ihre Provenienz ist das Letzte, was
    geschrieben wird) ist die Absicht — der naechste, der die Ablage
    oeffnet, vollendet den Tausch. Mutationsprobe: das Vollenden
    entfernen -> rot."""
    from rechner_pipeline.betrieb import neuaufsetzen as na
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    fall = _fall_mit_nebentabellen(tmp_path)
    echtes_rename = os.rename
    aufrufe: list = []

    def stirbt_beim_zweiten(quelle, ziel, *args, **kwargs):
        if Path(quelle).name.startswith("daten.neu-") and Path(ziel) == ablage.wurzel:
            aufrufe.append((quelle, ziel))
            raise KeyboardInterrupt("Prozessende zwischen den Umbenennungen")
        return echtes_rename(quelle, ziel, *args, **kwargs)

    monkeypatch.setattr(na.os, "rename", stirbt_beim_zweiten)
    with pytest.raises(KeyboardInterrupt):
        na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG,
                         jetzt=dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc))
    monkeypatch.undo()
    assert not ablage.wurzel.exists(), "die Probe hat den Zwischenzustand nicht erreicht"
    neu = Ablage(ablage.wurzel)
    assert tageslauf(neu, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert (neu.wurzel / na.PROVENIENZ_DATEI).is_file(), "der Tageslauf hat von vorn angefangen"
    assert (neu.uebernahme / "probe-uebernahme" / "eingang.json").is_file()
    assert not list(tmp_path.glob("daten.neu-*"))


def test_ein_unvollstaendiger_aufbau_wird_nicht_eingesetzt(tmp_path):
    """Gegenrichtung: Ohne Provenienz (Abbruch VOR ihrem Schreiben) ist die
    neue Ablage nicht fertig; fehlt dann die Wurzel, wird nichts eingesetzt,
    sondern der Lauf verweigert mit Namen des Rests."""
    (tmp_path / "daten.neu-20260908T060000Z" / "configs").mkdir(parents=True)
    (tmp_path / "daten.archiv-20260908T060000Z").mkdir()
    with pytest.raises(tl.TageslaufError, match="neu-20260908T060000Z"):
        tageslauf(Ablage(tmp_path / "daten"), dt.date(2026, 2, 3))
    assert not (tmp_path / "daten").exists()


# --------------------------------------------------------------------------- #
# Angriffsrunde Betrieb: der Tageslauf liest die Config genau einmal
# --------------------------------------------------------------------------- #


def test_der_tageslauf_rechnet_protokolliert_und_prueft_dieselbe_config(tmp_path, monkeypatch):
    """Die Config wurde viermal von der Platte gelesen (Rechnung, Hash der
    Protokollzeile, Manifest, P-B1). Ein Tausch nach dem ersten Lesen gab
    einen Stand, der mit der einen Config gerechnet und mit einer anderen
    bezeugt war. Mutationsprobe: wieder vom Ablagepfad lesen -> rot."""
    from tests.test_betrieb_seite import _ablage

    ablage = _ablage(tmp_path / "daten")
    original = ablage.config_pfad.read_bytes()
    echt = tl.load_config

    def tauscht_danach(pfad):
        cfg = echt(pfad)
        ablage.config_pfad.write_bytes(original + b"\n# nach dem Lesen getauscht\n")
        return cfg

    monkeypatch.setattr(tl, "load_config", tauscht_danach)
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    monkeypatch.undo()
    [zeile] = lies_protokoll(ablage.protokoll_pfad)
    assert zeile["config_sha256"] == ueb.sha256_bytes(original)
    manifest = json.loads((ablage.stand / "laufmanifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["sha256"] == ueb.sha256_bytes(original)


# --------------------------------------------------------------------------- #
# Angriffsrunde Betrieb: registriert wird nur, was der Tagesbetrieb annimmt
# --------------------------------------------------------------------------- #


def test_ein_zugangsstand_ohne_vertrag_in_kraft_am_stichtag_wird_nicht_registriert(tmp_path, monkeypatch):
    """Alle Vertraege laufen genau am Zugangsstichtag ab: Die Registrierung
    nahm den Eingang unwiderruflich an, und der Tagesbetrieb stand danach
    still (P-B1 rot an jedem folgenden Tag). Registriert wird nur, was
    die Wache des Tageslaufs annimmt. Mutationsprobe: die Probe in
    eingang_anlegen entfernen -> rot."""
    echt = pd.Timestamp

    def ablauf_am_stichtag(x, *a, **k):
        return echt("2021-01-01") if x == "2021-02-01" else echt(x, *a, **k)

    monkeypatch.setattr(pd, "Timestamp", ablauf_am_stichtag)
    fall = _kurzer_fall(tmp_path, mit_pex=False)
    monkeypatch.undo()
    stamm = read_portfolio(fall / "abgeleitet" / "bestand" / "bestand.parquet")
    assert (stamm["insurance_end"] == echt(STICHTAG)).all(), "die Probe hat den Ablauf nicht getroffen"
    stand = tmp_path / "daten"
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    try:
        ueb.eingang_anlegen(_mit_config(stand), fall, STICHTAG)
    except ueb.UebernahmeError:
        assert not (ablage.uebernahme / "kurz-uebernahme").exists()
        return
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 5))
    assert code == EXIT_OK, (
        "registriert, aber der Tagesbetrieb nimmt den Eingang nicht an: "
        f"{zeile.get('fehler') or (zeile.get('pb1') or {}).get('befunde')}")
