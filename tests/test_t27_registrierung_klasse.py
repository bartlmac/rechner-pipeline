"""Registrierung als Klasse — Pruefrunde T27, Befunde 04, 05 und 16.

Die Klasse: Eine Registrierung verwendet genau die Bytes, die sie geprueft
hat; sie prueft die Gueltigkeit eines Belegs (geltende Spitze der
Entscheidkette), nicht nur seine Echtheit; und sie prueft registrierte
Daten in ihrer Rohform, bevor sie sie zu einer Abbildung reduziert.

Knoten: system/betrieb
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.models.snapshot_kette import nachfolger_von, pruefe_snapshot_graph
from tests.test_betrieb_uebernahme import (
    PLV,
    STICHTAG,
    _fall,
    _pb1_ledger,
    am4_snapshot,
    ueb_p9_sha,
)


# --------------------------------------------------------------------------- #
# T27-04: die geprueften Bytes sind die verwendeten
# --------------------------------------------------------------------------- #


def test_die_registrierung_verwendet_die_bytes_die_sie_geprueft_hat(tmp_path, monkeypatch):
    """Die Naht des Gutachters: nach der Hashpruefung, beim Eintritt in
    die Sperre, wird die Quelle gegen einen konsistenten anderen Stand
    getauscht (60.000 -> 120.000 EUR). Der Eingang muss die GEPRUEFTEN
    60.000 tragen. Mutationsprobe: die Tabellen in der Kopierschleife
    wieder von der Platte lesen -> 120.000 -> rot."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    quelle = fall / "abgeleitet" / "bestand" / "bestand.parquet"
    echt = ueb.eingang_sperre

    def _tauscht_beim_eintritt(stand_):
        tabelle = read_portfolio(quelle)
        tabelle["sum_insured"] = tabelle["sum_insured"] * 2.0
        write_portfolio(tabelle, quelle)
        return echt(stand_)

    monkeypatch.setattr(ueb, "eingang_sperre", _tauscht_beim_eintritt)
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    monkeypatch.undo()
    assert read_portfolio(quelle)["sum_insured"].tolist() == [120000.0] * 3, "der Tausch hat nicht stattgefunden"
    im_eingang = read_portfolio(ziel / "bestand.parquet")
    assert im_eingang["sum_insured"].tolist() == [60000.0] * 3
    gelesen = ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, load_config(PLV))
    assert gelesen[0].bestand["sum_insured"].tolist() == [60000.0] * 3


# --------------------------------------------------------------------------- #
# T27-05: die geltende Spitze der A-M4-Kette, nicht die Echtheit einer Datei
# --------------------------------------------------------------------------- #


def _kettenglied(fall, name: str, *, entscheid: str, vorgaenger):
    daten = am4_snapshot(name, pb1_ledger_sha=_pb1_ledger(fall), entscheid=entscheid)
    daten["vorgaenger"] = list(vorgaenger)
    daten["entschieden_am"] = "2026-01-02T10:00:00+00:00"
    daten["snapshot_sha256"] = ueb_p9_sha(daten)
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    return daten["snapshot_sha256"]


def _spitze_laut_gate_ledger(fall) -> str:
    return json.loads((fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json")
                      .read_text(encoding="utf-8"))["summary"]["snapshot_sha256"]


def test_eine_ueberholte_annahme_ist_nicht_mehr_registrierbar(tmp_path):
    """Annahme A, danach Ablehnung B mit Vorgaenger A: A ist echt, aber
    nicht gueltig. Mutationsprobe: die Spitzenpruefung entfernen -> rot."""
    fall = _fall(tmp_path)
    alt = _spitze_laut_gate_ledger(fall)
    neu = _kettenglied(fall, "probe-uebernahme", entscheid="abgelehnt", vorgaenger=[alt])
    with pytest.raises(ueb.UebernahmeError, match="geltende Spitze") as exc:
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=alt)
    assert neu[:16] in str(exc.value) and "abgelehnt" in str(exc.value)
    assert not (tmp_path / "daten" / ueb.UEBERNAHME_DIR / "probe-uebernahme").exists()


def test_die_neue_annahme_an_der_spitze_ist_registrierbar_die_alte_nicht(tmp_path):
    """Positivkontrolle: Eine zweite Annahme B mit Vorgaenger A ist die
    Spitze — B registriert, A nicht."""
    fall = _fall(tmp_path)
    alt = _spitze_laut_gate_ledger(fall)
    neu = _kettenglied(fall, "probe-uebernahme", entscheid="angenommen", vorgaenger=[alt])
    with pytest.raises(ueb.UebernahmeError, match="geltende Spitze"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=alt)
    ziel = ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=neu)
    assert json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))["snapshot_sha256"] == neu


def test_ein_kaputtes_kettenglied_macht_die_spitze_unbekannt(tmp_path):
    fall = _fall(tmp_path)
    alt = _spitze_laut_gate_ledger(fall)
    (fall / "entscheide" / ("A-M4-" + "f" * 64 + ".json")).write_text("{kein json", encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="nicht lesbar"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=alt)


def test_der_kettenvertrag_ist_derselbe_fuer_gate_und_eingang():
    """Ein Vertrag, zwei Leser: Zyklus, fehlender Vorgaenger, Spitze."""
    kette = {"a": {"vorgaenger": []}, "b": {"vorgaenger": ["a"]}, "c": {"vorgaenger": ["b"]}}
    assert pruefe_snapshot_graph(kette) == (["c"], [])
    assert nachfolger_von(kette, "a") == ["b"]
    zyklus = {"a": {"vorgaenger": ["b"]}, "b": {"vorgaenger": ["a"]}}
    spitzen, fehler = pruefe_snapshot_graph(zyklus)
    assert spitzen == [] and any("Zyklus" in f for f in fehler)
    _, fehler = pruefe_snapshot_graph({"a": {"vorgaenger": ["x"]}}, {"a": "A-M4-a.json"})
    assert fehler == ["A-M4-a.json: Vorgaenger x existiert nicht"]
    zwei = {"a": {"vorgaenger": []}, "b": {"vorgaenger": []}}
    spitzen, fehler = pruefe_snapshot_graph(zwei)
    assert spitzen == ["a", "b"] and any("genau eine" in f for f in fehler)


# --------------------------------------------------------------------------- #
# T27-16: die Bruecke wird in ihrer Rohform geprueft
# --------------------------------------------------------------------------- #


def test_eine_widerspruechliche_bruecke_wird_abgewiesen_nicht_wegreduziert(tmp_path):
    """Die Rohtabelle des Gutachters: (7000001,1),(7000002,2),(7000003,3)
    plus (7000001,2),(7000002,1). Als Dict eine saubere Bijektion mit
    vertauschten Quellen — als Tabelle ein Widerspruch. Manifest-Hash
    korrekt nachgefuehrt, damit die semantische Pruefung selbst gemessen
    wird. Mutationsprobe: die Duplikatpruefung entfernen -> rot."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    config = load_config(PLV)
    assert len(ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, config)) == 1
    pfad = ziel / ueb.POLICENNUMMERN_DATEI
    pfad.chmod(0o644)
    bruecke = read_portfolio(pfad)
    zusatz = pd.DataFrame({"quelle_police_id": pd.Series([7_000_001, 7_000_002], dtype="int64"),
                           "ziel_police_id": pd.Series([2, 1], dtype="int64")})
    write_portfolio(pd.concat([bruecke, zusatz], ignore_index=True), pfad)
    manifest = ziel / ueb.EINGANG_DATEI
    manifest.chmod(0o644)
    daten = json.loads(manifest.read_text(encoding="utf-8"))
    daten["dateien"][ueb.POLICENNUMMERN_DATEI] = ueb.sha256_bytes(pfad.read_bytes())
    manifest.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="keine Abbildung"):
        ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, config)


# --------------------------------------------------------------------------- #
# Angriffsrunde 2 (Betrieb): N21 und N24
# --------------------------------------------------------------------------- #


def test_auch_eine_bezeugte_nebentabelle_wird_gegen_den_beleggraphen_gehalten(tmp_path):
    """N21: Die Registrierung hielt nur die drei Pflichttabellen gegen den
    Graphen; eine nach der Abnahme getauschte Scheibentabelle ging
    ungeprueft ein, obwohl der Graph ihren Hash nannte. Mutationsprobe:
    die Schleife zurueck auf PFLICHT -> rot."""
    from tests.test_betrieb_neuaufsetzen import _fall_mit_nebentabellen

    fall = _fall_mit_nebentabellen(tmp_path)
    scheiben = fall / "abgeleitet" / "bestand" / "scheiben.parquet"
    tabelle = read_portfolio(scheiben)
    tabelle["sum_insured"] = tabelle["sum_insured"] * 2.0
    write_portfolio(tabelle, scheiben)
    with pytest.raises(ueb.UebernahmeError, match="bezeugt"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)
    # Positivkontrolle: unveraendert registriert sich der Fall.
    frisch = _fall_mit_nebentabellen(tmp_path / "b")
    assert ueb.eingang_anlegen(tmp_path / "daten-b", frisch, STICHTAG).is_dir()


def test_ein_kettenglied_in_rohform_ist_ein_benannter_fehler(tmp_path):
    """N24: ein Glied, das JSON ist, aber kein Objekt (Liste, Zahl), liess
    die Registrierung mit AttributeError abstuerzen."""
    fall = _fall(tmp_path)
    alt = _spitze_laut_gate_ledger(fall)
    (fall / "entscheide" / ("A-M4-" + "e" * 64 + ".json")).write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="kein Objekt"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=alt)


def test_die_registrierung_nimmt_die_lauf_sperre_der_ablage(tmp_path):
    """Angriffsrunde (Betrieb): Registrierung und Tageslauf nahmen
    verschiedene Sperren. Haelt ein Lauf die Ablage, wartet die
    Registrierung nicht und mischt nichts — sie bricht mit Meldung ab.
    Mutationsprobe: die Lauf-Sperre in eingang_anlegen entfernen -> rot."""
    import fcntl

    from rechner_pipeline.betrieb.tageslauf import Ablage

    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ablage = Ablage(stand)
    ablage.wurzel.mkdir(parents=True, exist_ok=True)
    with open(ablage.sperre, "a+") as fremd:
        fcntl.flock(fremd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ueb.UebernahmeError, match="Sperre"):
            ueb.eingang_anlegen(stand, fall, STICHTAG)
    assert ueb.eingang_anlegen(stand, fall, STICHTAG).is_dir()


def test_eine_vertauschte_bruecke_wird_erkannt(tmp_path):
    """Angriffsrunde (Betrieb): Eine in sich stimmige, aber vertauschte
    Bruecke (7000001 -> 2, 7000002 -> 1) galt als gueltig. Die
    Vergaberegel des Schreibers macht die Sollabbildung rekonstruierbar.
    Mutationsprobe: die Regelpruefung entfernen -> rot."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    pfad = ziel / ueb.POLICENNUMMERN_DATEI
    pfad.chmod(0o644)
    b = read_portfolio(pfad)
    b["ziel_police_id"] = b["ziel_police_id"].replace({1: 2, 2: 1})
    write_portfolio(b, pfad)
    manifest = ziel / ueb.EINGANG_DATEI
    manifest.chmod(0o644)
    daten = json.loads(manifest.read_text(encoding="utf-8"))
    daten["dateien"][ueb.POLICENNUMMERN_DATEI] = ueb.sha256_bytes(pfad.read_bytes())
    manifest.write_text(json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="Vergaberegel"):
        ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, load_config(PLV))


def test_ein_fallfremdes_oder_ungezeichnetes_kettenglied_verletzt_die_kette(tmp_path):
    """Angriffsrunde (Betrieb): Der Eingang pruefte an fremden Gliedern nur
    Selbstadressierung und Vorgaenger — ein fallfremdes Glied ueberholte
    die Annahme. Jetzt dieselbe Aufnahmeregel wie das Gate.
    Mutationsprobe: die Fallbindung nicht pruefen -> rot."""
    fall = _fall(tmp_path)
    alt = _spitze_laut_gate_ledger(fall)
    _kettenglied(fall, "anderer-fall", entscheid="abgelehnt", vorgaenger=[alt])
    with pytest.raises(ueb.UebernahmeError, match="Fallbindung"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=alt)
