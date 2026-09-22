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
    # Positivkontrolle der Probe: heute ist genau die Teilkuendigung die Luecke.
    assert set(VERFAHREN) - set(PRODUKTIV_AUSFUEHRBAR) == {TEILKUENDIGUNG}


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

def test_tarifwerk_luecken_sieht_die_teilkuendigung_und_sonst_nichts():
    """Die PLV-Config traegt die TG2015 mit ihrem Bedingungswerk — genau
    diese eine Luecke, kein Beifang beim eigenen Geschaeft."""
    cfg = load_config(PLV)
    assert tarifwerk_luecken(cfg.generationen) == [("TG2015", "red_verfahren", TEILKUENDIGUNG)]
    text = bauauftrag_text("TG2015", "red_verfahren", TEILKUENDIGUNG)
    assert "Bauauftrag" in text and "NICHT anzupassen" in text
    # Der alte, falsche Ausweg darf nirgends mehr stehen.
    assert "auf 'prospektiv'" not in text and "umstellen" not in text


def test_config_wache_latent_bei_rate_null_und_hart_bei_erreichbarem_pfad():
    """Die echte Config ist gueltig (Rate 0, Luecke latent; die Pruefstrecke
    rekonstruiert die Teilkuendigung absichtlich). Wird der Pfad
    erreichbar, ist die Config keine gueltige — und der Befund ist ein
    Bauauftrag, kein Config-Rat.

    Mutationsprobe: die Erreichbarkeits-Bedingung streichen -> die echte
    Config wird ungueltig (erste Zusicherung rot); den Aufruf der Ratsche
    in ``validate`` entfernen -> zweite Zusicherung rot.
    """
    assert load_config(PLV).validate() == []
    kaputt = PLV.read_text(encoding="utf-8") + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    fehler = config_aus_text(kaputt).validate()
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


def test_die_freischaltung_blockiert_eine_generation_die_der_betrieb_nicht_fuehren_kann(tmp_path):
    """DoRAs Fall, an der richtigen Stelle: Eine Lieferung, deren Generation
    per Bedingungswerk die Teilkuendigung traegt, wird registriert — aber
    der Betrieb nimmt sie NICHT in die Fuehrung, unabhaengig davon, ob heute
    eine Herabsetzung simuliert wird. Der Befund nennt den Bauauftrag.

    Dieselbe Lieferung, dieselben Bytes: Nur der Schalter der Generation in
    der Config der Laufzeit entscheidet. Die Testwelt ist die etablierte
    kleine Config (keine Tarifzellen, also keine merkmale-Pflicht, die den
    Eingang VOR der Ratsche abwiese — das war der erste Entwurf dieses
    Tests, und er war blind). Die Vorbedingungen stehen als Zusicherung.

    Mutationsprobe: den Ratschen-Block in ``lies_uebernahme`` entfernen ->
    die erste Zusicherung rot, die Positivkontrolle bleibt gruen.
    """
    anker = '[[generation]]\nname = "klv/zellen"\n'
    assert anker in _CONFIG_TOML, "Fixture-Anker der Testwelt hat sich bewegt"
    mit = config_aus_text(_CONFIG_TOML.replace(
        anker, anker + 'red_verfahren = "teilkuendigung"\n', 1))
    ohne = config_aus_text(_CONFIG_TOML)
    gen = mit.generationen[0]
    assert gen.tarifwerk()["red_verfahren"] == TEILKUENDIGUNG
    assert not gen.zellen, "Fixture: ohne Zellen, sonst greift die merkmale-Pflicht vor der Ratsche"
    assert mit.annahmen.herabsetzung.a == 0.0, "Fixture: die Luecke muss LATENT sein"
    assert ohne.generationen[0].tarifwerk()["red_verfahren"] != TEILKUENDIGUNG

    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, _fall_mit_generation(tmp_path / "fall", gen.name, "quell-lieferung"), STICHTAG)
    eingang = stand / "uebernahme" / "quell-lieferung"
    with pytest.raises(ueb.UebernahmeError, match="Migration blockiert.*Bauauftrag.*teilkuendigung"):
        ueb.lies_uebernahme(eingang, mit)
    # Positivkontrolle: dieselben Bytes, ein ausfuehrbares Verfahren -> tritt ein.
    assert len(ueb.lies_uebernahme(eingang, ohne).bestand) == 3


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
