"""Die Ratsche „Schalterwert produktiv ausfuehrbar" (Befund T26-12, als Klasse).

Drei Mengen gab es, zwei wurden geprueft: BEKANNT (``VERFAHREN``,
``Generation.validate``), UEBERTRAGEN (``tarifwerk_fehler`` der Uebernahme)
— und niemand prueft, ob der PRODUKTIVE Pfad den Schalterwert auch
ausfuehren kann. Durch dieses Loch fiel die Teilkuendigung der TG2015:
erlaubt, uebertragen, im Lauf verweigert. Die Klasse: *Ein uebernommener
Bestand bringt ein Tarifwerks-Merkmal mit, das der produktive Pfad nicht
ausfuehren kann.* Sie schliesst mit drei Instrumenten: der Deklaration
(``TARIFWERK_AUSFUEHRBAR``, ``PRODUKTIV_AUSFUEHRBAR``), der Ratsche bei der
Freischaltung und einem Zaehl-Test, der die Deklaration gegen den Kern haelt.

Entscheid des Maintainers 2026-09-22: Die Luecke ist ein BAUAUFTRAG, nie ein
Config-Rat. Entdecken bleibt Aufgabe von A-M1/2/3; Erzwingen macht die
Ratsche.

Knoten: system/bestand
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import (
    TARIFWERK_AUSFUEHRBAR,
    bauauftrag_text,
    config_aus_text,
    load_config,
    tarifwerk_luecken,
)
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import (
    PRODUKTIV_AUSFUEHRBAR,
    TEILKUENDIGUNG,
    VERFAHREN,
    BeitragsreduktionFehler,
    reduziere_geschichtet,
)
from rechner_pipeline.models.bestand import LEDGER_NAMES, STAMM_NAMES
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML
from tests.test_betrieb_uebernahme import (
    PLV,
    STICHTAG,
    _fall,
    _pb1_ledger,
    _zugangsstand,
    am4_snapshot,
)


def _kern(generation: str = "KLV-2017") -> Rechenkern:
    gen = next(g for g in load_config(PLV).generationen if g.name == generation)
    return Rechenkern(ModelPoint(x=35, sex="F", n=25, t=20, sum_insured=60000.0,
                                 zw=12, **gen.generation_fields()))


# --- Instrument 1: die Deklaration stimmt mit dem Kern ueberein ----------------

def test_die_deklaration_stimmt_mit_dem_produktiven_pfad_ueberein():
    """Zaehl-Test: JEDES bekannte Verfahren wird klassifiziert, und die
    Klassifikation ist die des Kerns. Was in ``PRODUKTIV_AUSFUEHRBAR``
    steht, rechnet ``reduziere_geschichtet``; was fehlt, verweigert es.

    Mutationsprobe: Teilkuendigung in das Tupel eintragen, ohne sie zu
    bauen -> rot (der Kern verweigert sie). Das Tupel um ``mit_abzug``
    kuerzen -> rot (der Kern rechnet es). Die Deklaration kann also weder
    zu viel noch zu wenig versprechen.
    """
    kern = _kern()
    for verfahren in VERFAHREN:
        if verfahren in PRODUKTIV_AUSFUEHRBAR:
            ergebnis = reduziere_geschichtet(kern, [], 5, 0.6, verfahren=verfahren)
            assert ergebnis and ergebnis[0][1].verfahren == verfahren, verfahren
        else:
            with pytest.raises(BeitragsreduktionFehler):
                reduziere_geschichtet(kern, [], 5, 0.6, verfahren=verfahren)
    # Exakt: seit dem Bauauftrag T26-12 (2026-09-22) ist jedes bekannte
    # Verfahren ausfuehrbar — die Menge der Luecken ist LEER, nicht >= 0.
    assert set(VERFAHREN) == set(PRODUKTIV_AUSFUEHRBAR)


def test_jeder_schalter_der_fuehrung_ist_deklariert():
    """Exakt, nicht >=: Die Schluessel der Deklaration SIND die Schalter von
    ``tarifwerk()``. Ein neuer Schalter ohne Deklaration faellt hier —
    das ist der Fang des naechsten, heute unbekannten Merkmals.

    Mutationsprobe: einen vierten Schalter in ``tarifwerk()`` aufnehmen,
    ohne ihn zu deklarieren -> rot; einen Schluessel aus der Deklaration
    streichen -> rot.
    """
    gen = load_config(PLV).generationen[0]
    assert set(TARIFWERK_AUSFUEHRBAR) == set(gen.tarifwerk())
    # und jeder deklarierte Bool-Schalter kennt beide Werte
    for schalter in ("scheiben_mit_gamma1", "stoab_je_baustein"):
        assert set(TARIFWERK_AUSFUEHRBAR[schalter]) == {False, True}


# --- Instrument 2: die Ratsche, generisch ---------------------------------------

def test_tarifwerk_luecken_sieht_heute_keine_luecke_und_findet_eine_simulierte(monkeypatch):
    """Die PLV-Config (TG2015 mit Teilkuendigung) hat seit dem Bau keine
    Luecke. Die Ratsche ist trotzdem scharf: Eine simulierte — ``mit_abzug``
    aus der Deklaration genommen — findet sie generisch, und der Befund ist
    ein Bauauftrag ohne Config-Rat."""
    cfg = load_config(PLV)
    assert tarifwerk_luecken(cfg.generationen) == []
    text = bauauftrag_text("TG2015", "red_verfahren", TEILKUENDIGUNG)
    assert "Bauauftrag" in text and "NICHT anzupassen" in text
    assert "auf 'prospektiv'" not in text and "umstellen" not in text
    from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV
    monkeypatch.setitem(TARIFWERK_AUSFUEHRBAR, "red_verfahren", (PROSPEKTIV, TEILKUENDIGUNG))
    kaputt = config_aus_text(_CONFIG_TOML.replace(
        '[[generation]]\nname = "klv/zellen"\n',
        '[[generation]]\nname = "klv/zellen"\nred_verfahren = "mit_abzug"\n', 1))
    assert tarifwerk_luecken(kaputt.generationen) == [("klv/zellen", "red_verfahren", MIT_ABZUG)]


def test_config_wache_latent_bei_rate_null_und_hart_bei_erreichbarem_pfad(monkeypatch):
    """Die echte Config ist gueltig — mit und ohne Herabsetzungsrate, denn
    jedes ihrer Verfahren ist gebaut. Die Wache prueft der Test an einer
    simulierten Luecke: Rate 0 -> latent (die Pruefstrecke braucht dieselbe
    Config), Rate > 0 -> keine gueltige Config, Befund = Bauauftrag.

    Mutationsprobe: die Erreichbarkeits-Bedingung streichen -> der latente
    Fall wird rot; den Aufruf der Ratsche in ``validate`` entfernen -> der
    harte Fall wird rot.
    """
    assert load_config(PLV).validate() == []
    # Rate UND Anteil: die Annahmen-Validierung verlangt zu einer
    # Herabsetzungsrate den fortgefuehrten Anteil (wie das T26-11-Fixture).
    mit_rate = PLV.read_text(encoding="utf-8").replace(
        "[annahmen]\n", "[annahmen]\nred_anteil = 0.6\n", 1
    ) + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    assert "red_anteil = 0.6" in mit_rate
    assert config_aus_text(mit_rate).validate() == []
    from rechner_pipeline.kern.beitragsreduktion import MIT_ABZUG, PROSPEKTIV
    monkeypatch.setitem(TARIFWERK_AUSFUEHRBAR, "red_verfahren", (PROSPEKTIV, MIT_ABZUG))
    assert load_config(PLV).validate() == [], "Rate 0: die Luecke bleibt latent"
    fehler = config_aus_text(mit_rate).validate()
    treffer = [f for f in fehler if "TG2015" in f and TEILKUENDIGUNG in f]
    assert len(treffer) == 1, fehler
    assert "Bauauftrag" in treffer[0]
    assert "auf 'prospektiv' oder 'mit_abzug' setzen" not in treffer[0]


# --- Instrument 3: die adversariale Probe an der Freischaltung -------------------

def _fall_mit_generation(wurzel: Path, generation: str, name: str) -> Path:
    """Ein Fall wie ``_fall``, dessen Zugangsstand die genannte Generation
    traegt — mit echtem P-B1-Ledger und A-M4-Snapshot auf den ENDGUELTIGEN
    Tabellen (erst Tabellen, dann Beleg, dann Snapshot)."""
    fall = wurzel / name
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "entscheide").mkdir()
    (fall / "fall.json").write_text(json.dumps({"name": name, "schema_version": 1}), encoding="utf-8")
    ziel = fall / "abgeleitet" / "bestand"
    _zugangsstand(ziel)
    for datei, spalten in (("bestand.parquet", STAMM_NAMES), ("ledger.parquet", LEDGER_NAMES)):
        tab = read_portfolio(ziel / datei, expected_columns=spalten)
        tab["tarif_generation"] = generation
        write_portfolio(tab, ziel / datei)
    sha = _pb1_ledger(fall)
    daten = am4_snapshot(name, pb1_ledger_sha=sha)
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    return fall


def test_die_freischaltung_blockiert_eine_generation_die_der_betrieb_nicht_fuehren_kann(tmp_path, monkeypatch):
    """DoRAs Fall, an der richtigen Stelle: Eine Lieferung, deren Generation
    ein Verfahren traegt, das der produktive Pfad nicht kann, wird
    registriert — aber der Betrieb nimmt sie NICHT in die Fuehrung,
    unabhaengig davon, ob heute eine Herabsetzung simuliert wird. Der
    Befund nennt den Bauauftrag.

    Seit dem Bau der Teilkuendigung gibt es keine echte Luecke mehr; die
    Probe simuliert eine (``mit_abzug`` aus der Deklaration genommen).
    Dieselbe Lieferung, dieselben Bytes: Nur der Schalter der Generation
    in der Config der Laufzeit und die Deklaration entscheiden. Testwelt
    ist die kleine Config ohne Tarifzellen (sonst wiese die merkmale-
    Pflicht den Eingang VOR der Ratsche ab — der erste Entwurf dieses
    Tests war so blind); die Vorbedingungen stehen als Zusicherung.

    Positivkontrollen: die Teilkuendigung tritt heute ein (gebaut), und
    dieselbe Lieferung unter ``prospektiv`` tritt ein.
    Mutationsprobe: den Ratschen-Block in ``lies_uebernahme`` entfernen ->
    die Blockade-Zusicherung rot, die Positivkontrollen bleiben gruen.
    """
    from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV

    anker = '[[generation]]\nname = "klv/zellen"\n'
    assert anker in _CONFIG_TOML, "Fixture-Anker der Testwelt hat sich bewegt"
    def cfg(verfahren):
        return config_aus_text(_CONFIG_TOML.replace(
            anker, anker + f'red_verfahren = "{verfahren}"\n', 1))
    tk, ab, pro = cfg("teilkuendigung"), cfg("mit_abzug"), config_aus_text(_CONFIG_TOML)
    gen = tk.generationen[0]
    assert not gen.zellen, "Fixture: ohne Zellen, sonst greift die merkmale-Pflicht vor der Ratsche"
    assert tk.annahmen.herabsetzung.a == 0.0, "Fixture: die Luecke muss LATENT sein"

    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, _fall_mit_generation(tmp_path / "fall", gen.name, "quell-lieferung"), STICHTAG)
    eingang = stand / "uebernahme" / "quell-lieferung"
    # Positivkontrolle 1: die Teilkuendigung ist gebaut — sie tritt ein.
    assert len(ueb.lies_uebernahme(eingang, tk).bestand) == 3
    # Die simulierte Luecke: mit_abzug gilt als nicht gebaut.
    monkeypatch.setitem(TARIFWERK_AUSFUEHRBAR, "red_verfahren", (PROSPEKTIV, TEILKUENDIGUNG))
    with pytest.raises(ueb.UebernahmeError, match="Migration blockiert.*Bauauftrag.*mit_abzug"):
        ueb.lies_uebernahme(eingang, ab)
    # Positivkontrolle 2: dieselben Bytes, ein ausfuehrbares Verfahren -> tritt ein.
    assert len(ueb.lies_uebernahme(eingang, pro).bestand) == 3


# --- Annahme 5, streng -----------------------------------------------------------

def test_ein_beleggraph_der_nicht_alle_pflichttabellen_bezeugt_wird_abgewiesen(tmp_path):
    """Annahme 5, entschieden STRENG (2026-09-22): bestand, historie UND
    ledger muessen vom Beleggraphen bezeugt sein. Ein Ledger, den die
    Abnahme nicht gesehen hat, ist eine Luecke — vorher nur eine Zeile auf
    stderr, die niemand las.

    Mutationsprobe: die Abweisung wieder auf bestand.parquet beschraenken
    -> rot. Positivkontrolle: der volle Beleggraph tritt ein.
    """
    fall = _fall(tmp_path / "voll")
    ueb.eingang_anlegen(tmp_path / "daten-voll", fall, STICHTAG)

    duenn = _fall(tmp_path / "duenn", name="duenn")
    ledger_pfad = duenn / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
    ledger = json.loads(ledger_pfad.read_text(encoding="utf-8"))
    ledger["input_hashes"] = {k: v for k, v in ledger["input_hashes"].items()
                              if k.endswith("bestand.parquet")}
    roh = json.dumps(ledger, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ledger_pfad.write_bytes(roh)
    daten = am4_snapshot("duenn", pb1_ledger_sha=hashlib.sha256(roh).hexdigest())
    for alt in (duenn / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (duenn / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (duenn / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    with pytest.raises(ueb.UebernahmeError, match="historie.parquet, ledger.parquet.*Annahme 5 streng"):
        ueb.eingang_anlegen(tmp_path / "daten-duenn", duenn, STICHTAG)
    assert not (tmp_path / "daten-duenn" / "uebernahme" / "duenn").exists(), "kein halber Eingang"
