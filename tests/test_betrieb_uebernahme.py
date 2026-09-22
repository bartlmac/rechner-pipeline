"""Uebernahme-Eingang: registrieren, unantastbar lesen, im Tagesbetrieb mitfahren.

Fachkonzept docs/simulation/tagesbetrieb.md, Block B5. Ein migrierter
Bestand tritt als datierter Zugang in den Tagesbetrieb ein: einmal
registriert (Fall-Bezug, Summen je Datei), dann in jedem Lauf im selben
Strom fortgeschrieben wie das eigene Geschaeft. Der Eingang hier ist
synthetisch (ein kleiner Zugangsstand wie ihn gates.bestand_uebernehmen
hinterlaesst); der echte Baldrian-Zugang liegt im Fall-Arbeitsbereich
und ist kein Repo-Inhalt (ADR-002).

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
    STATUS_HISTORIE_NAMES,
    STATUS_HISTORIE_SPALTEN,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PLV = REPO_ROOT / "configs" / "bestand_gesamt.toml"
STICHTAG = dt.date(2026, 1, 1)


def _zugangsstand(ziel: Path) -> None:
    """Ein Zugangsstand wie von gates.bestand_uebernehmen: drei Vertraege
    der Generation KLV-2017 (Nummernkreis 7 Mio, wie ein fremder Bestand),
    einer davon beitragsfrei uebernommen."""
    zeilen = []
    for k, (beginn, status) in enumerate([("2018-03-01", "POL"), ("2019-07-01", "POL"),
                                          ("2017-11-01", "PEX")]):
        b = pd.Timestamp(beginn)
        zeilen.append({
            "police_id": 7_000_001 + k, "tarif_generation": "KLV-2017", "produkt": "klv",
            "status_id": 2 if status == "PEX" else 1, "status_code": status,
            "status_date": pd.Timestamp("2023-11-01") if status == "PEX" else b,
            "sex": "F", "date_of_birth": b - pd.DateOffset(years=35), "entry_age": 35,
            "duration": 25, "premium_duration": 20, "sum_insured": 60000.0, "bu_rente": 0.0,
            "zahlweise": 12, "insurance_start": b, "insurance_end": b + pd.DateOffset(years=25),
            "payment_end": b + pd.DateOffset(years=20), "bestandszugang": pd.Timestamp(STICHTAG),
        })
    stamm = pd.DataFrame(zeilen)[list(STAMM_NAMES)].astype(dict(STAMM_SPALTEN))
    historie = pd.DataFrame([{
        "police_id": 7_000_003, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2023-11-01"),
    }]).astype(dict(STATUS_HISTORIE_SPALTEN))
    ledger_zeilen = [{
        "police_id": int(z["police_id"]), "tarif_generation": "KLV-2017", "ereignis": "ZUG",
        "vertragsjahr": int((pd.Timestamp(STICHTAG).year * 12 + 1 - (z["insurance_start"].year * 12 + z["insurance_start"].month)) // 12),
        "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS", "betrag": 60000.0,
        "betrag_herkunft": "geliefert",
    } for z in zeilen]
    # Die Umbuchung des beitragsfrei uebernommenen Vertrags: Betrag ist die
    # beitragsfreie Summe, vom aufnehmenden Unternehmen aus den
    # Ursprungsparametern gerechnet (gates.bestand_uebernehmen; die
    # Lieferung traegt sie nicht) — gebucht zum Zugangsstichtag im
    # Vertragsjahr des Zugangs, beitragsfrei seit Vertragsjahr 6.
    from rechner_pipeline.kern import ModelPoint, Rechenkern

    gen = next(g for g in load_config(PLV).generationen if g.name == "KLV-2017")
    kern = Rechenkern(ModelPoint(x=35, sex="F", n=25, t=20, sum_insured=60000.0, zw=12,
                                 **gen.generation_fields()))
    ledger_zeilen.append({
        "police_id": 7_000_003, "tarif_generation": "KLV-2017", "ereignis": "PEX",
        "vertragsjahr": 8, "status_date": pd.Timestamp(STICHTAG), "betrag_art": "VS",
        "betrag": float(kern.beitragsfreie_summe(6)), "betrag_herkunft": "gerechnet",
    })
    ledger = pd.DataFrame(ledger_zeilen)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    ziel.mkdir(parents=True, exist_ok=True)
    write_portfolio(stamm, ziel / "bestand.parquet")
    write_portfolio(historie, ziel / "historie.parquet")
    write_portfolio(ledger, ziel / "ledger.parquet")


def am4_snapshot(fall_name: str, *, gate: str = "A-M4",
                 entscheid: str = "angenommen",
                 pb1_ledger_sha: str = "ab" * 32,
                 rollen: "tuple[str, ...] | None" = None,
                 schema: int = 7,
                 schluessel: "bytes | None" = None) -> dict:
    """Ein gueltiger P9-Snapshot, wie ihn das Gate schreibt — Schema 7 mit
    Zeichnung (Rolle, Schluesselklasse), EXAKT den Pflichtrollen seines
    Scopes und einer ECHTEN Freigabesignatur (Testschluessel; conftest
    reicht den Ring an den Betriebseingang). Nur ``pb1_ledger`` zeigt auf
    einen echten Beleg (er bindet die Tabellen, T26-03); die uebrigen
    Rollen tragen Platzhalter-Hashes, fuer die der Beleggraph nichts
    findet — im echten Fall schreibt das Gate sie, hier buergt die
    Signatur. ``rollen`` ueberschreibt die Rollenmenge (DoRAs Fall: nur
    pb1_ledger), ``schema=6`` baut einen Altsnapshot ohne Klasse.
    """
    from rechner_pipeline.models.belegrollen import am4_belegrollen
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import P9_GATE_VERSION, p9_snapshot_sha256
    from tests.freigabe_testschluessel import TESTKEY

    scope = "bestand"
    alle = list(rollen) if rollen is not None else (am4_belegrollen(scope) if gate == "A-M4" else ["pb1_ledger"])
    gen_beleg = hashlib.sha256(b"pk1:klv/plv_2017").hexdigest()
    pflichtbelege = {}
    for rolle in alle:
        if rolle == "pb1_ledger":
            pflichtbelege[rolle] = [pb1_ledger_sha]
        elif rolle == "pk1_belege":
            pflichtbelege[rolle] = [gen_beleg]
        else:
            pflichtbelege[rolle] = [hashlib.sha256(rolle.encode()).hexdigest()]
    rolle_id = "mensch" if schema == 6 else "mensch/aktuar"
    daten = {
        "schema_version": schema, "command": "gate_entscheid",
        "gate_version": "0.6.0" if schema == 6 else P9_GATE_VERSION,
        "gate": gate, "entscheid": entscheid, "entscheider": "Verantwortlicher Aktuar",
        "rolle": rolle_id, "begruendung": "Controlling bestanden",
        "fall": fall_name,
        "artefakt_hashes": {"eingang.json": "ab" * 32,
                            "abgeleitet/abox/abox.json": "cd" * 32},
        "system": {"branch": "main", "commit": "abc1234", "dirty": "nein",
                   "quellcode_sha256": "ef" * 32},
        "vorgaenger": [], "entschieden_am": "2026-01-01T10:00:00+00:00",
        "fall_scope": scope,
        "pflichtbelege": pflichtbelege,
    }
    daten["zeichnung"] = ({"rolle": rolle_id, "ordnung_sha256": "cd" * 32} if schema == 6
                          else {"rolle": rolle_id, "ordnung_sha256": "cd" * 32, "schluesselklasse": "mensch"})
    if gate == "A-M4":
        daten["pk1_belege"] = {"klv/plv_2017": [gen_beleg]} if "pk1_belege" in pflichtbelege else {}   # Schluessel: familie/generation
    if entscheid == "angenommen":
        daten["freigabe"] = freigabe_fuer(daten, schluessel or TESTKEY)
    daten["snapshot_sha256"] = p9_snapshot_sha256(daten)
    return daten


def _pb1_ledger(fall: Path) -> str:
    """Ein P-B1-Gate-Ledger ueber die Tabellen des Zugangsstands.

    Er ist der Beleg, ueber den der Betriebseingang die uebernommenen
    Tabellen an die Migrationsabnahme bindet (Befund T26-03): Der
    A-M4-Snapshot nennt seinen Hash als Pflichtbeleg, der Ledger nennt
    die Hashes der Tabellen.
    """
    import hashlib

    bestand = fall / "abgeleitet" / "bestand"
    eingaben = {
        str(pfad.relative_to(fall)): hashlib.sha256(pfad.read_bytes()).hexdigest()
        for pfad in sorted(bestand.glob("*.parquet"))
    }
    ledger = {
        "schema_version": 1, "command": "bestand_validate",
        "gate": "P-B1.bestandspruefung", "gate_version": "0.1.0",
        "status": "passed", "attempt": 1,
        "input_hashes": eingaben,
        "summary": {"vertraege": 3},
    }
    pfad = fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
    roh = json.dumps(ledger, ensure_ascii=False, sort_keys=True).encode("utf-8")
    pfad.write_bytes(roh)
    return hashlib.sha256(roh).hexdigest()


def _beleg_neu(fall: Path, name: str = "probe-uebernahme") -> None:
    """P-B1-Ledger und A-M4-Snapshot auf den JETZIGEN Tabellen neu bauen.

    Wer die Tabellen eines Falls nachtraeglich aendert, aendert damit
    auch das, was die Abnahme bezeugt. Frueher fiel das nicht auf, weil
    der Eingang keinen Bezug zwischen beidem herstellte (T26-03).
    """
    ledger_sha = _pb1_ledger(fall)
    daten = am4_snapshot(name, pb1_ledger_sha=ledger_sha)
    for alt in (fall / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")


def _snapshot_sha(fall: Path) -> str:
    """Der Snapshot-Hash, den DIESER Fall traegt — nicht ein zweiter,
    neu gebauter: Seit der Pflichtbeleg auf einen echten Ledger zeigt,
    haengt der Hash am Inhalt des Falls."""
    beleg = fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json"
    return json.loads(beleg.read_text(encoding="utf-8"))["summary"]["snapshot_sha256"]


def _fall(wurzel: Path, name: str = "probe-uebernahme", *, snapshot: "dict | None | str" = "echt") -> Path:
    """Ein Fall mit Zugangsstand und (Standard) einem strukturell gueltigen
    A-M4-Snapshot; ``snapshot=None`` legt keinen an, ein Dict wird so
    geschrieben, wie es ist (Manipulationsproben)."""
    fall = wurzel / name
    (fall / "abgeleitet" / "diagnostics").mkdir(parents=True)
    (fall / "entscheide").mkdir()
    (fall / "fall.json").write_text(json.dumps({"name": name, "schema_version": 1}), encoding="utf-8")
    # Erst die Tabellen, dann ihr P-B1-Ledger, dann der Snapshot, der ihn
    # nennt — dieselbe Reihenfolge wie im echten Fall.
    _zugangsstand(fall / "abgeleitet" / "bestand")
    ledger_sha = _pb1_ledger(fall)
    if snapshot is not None:
        daten = (am4_snapshot(name, pb1_ledger_sha=ledger_sha)
                 if snapshot == "echt" else snapshot)
        (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
            json.dumps(daten, ensure_ascii=False), encoding="utf-8")
        (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
            json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}), encoding="utf-8")
    return fall


ECHTER_SHA = None  # wird je Test aus dem Snapshot gelesen


@pytest.fixture()
def eingang(tmp_path):
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, fall, STICHTAG)
    return stand, fall, ziel


def test_eingang_wird_registriert_und_ist_unantastbar(eingang):
    stand, fall, ziel = eingang
    daten = json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))
    assert daten["fall"] == "probe-uebernahme" and daten["stichtag"] == "2026-01-01"
    # Der Hash DIESES Falls: Seit der Pflichtbeleg auf einen echten
    # P-B1-Ledger zeigt (T26-03), haengt er am Inhalt des Falls und laesst
    # sich nicht mehr aus dem Namen allein nachbauen.
    assert daten["snapshot_sha256"] == _snapshot_sha(fall)
    # Schema 6 fuehrt keine Schluesselklasse — das steht dann so da.
    assert daten["zeichnung"]["schluesselklasse"] == "mensch"   # Schema 7
    assert daten["zeichnung"]["rolle"] == "mensch/aktuar"   # Rollen-Id mit Ebene (ADR-018)
    assert daten["zeichnung"]["signatur_verifiziert"] is True   # mit dem Testring geprueft
    # Seit Review T24-08 traegt der Eingang die Uebersetzungstabelle mit:
    # Das Zielsystem vergibt eigene Policennummern, und ohne die Tabelle
    # waere eine Rueckfrage an die Quelle nicht beantwortbar.
    assert set(daten["dateien"]) == {"bestand.parquet", "historie.parquet",
                                     "ledger.parquet", "policennummern.parquet"}
    # Das Nummernband: erster Eingang, drei Vertraege, auf volle Tausend
    # aufgerundet — 1..1000. Der naechste Fall faengt bei 1001 an.
    assert daten["band"] == {"von": 1, "bis": 1000}
    assert daten["schema_version"] == ueb.EINGANG_SCHEMA_VERSION == 2
    if os.name != "nt":
        for datei in ziel.iterdir():
            assert (datei.stat().st_mode & 0o777) == 0o444
    with pytest.raises(ueb.UebernahmeError, match="nie ueberschrieben"):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    config = load_config(PLV)
    gelesen = ueb.lies_uebernahmen(stand / "uebernahme", config)
    assert [u.fall for u in gelesen] == ["probe-uebernahme"]
    assert len(gelesen[0].bestand) == 3 and gelesen[0].merkmale is None
    # Mutationsprobe: veraenderte Datei -> Lesen bricht ab.
    pfad = ziel / "ledger.parquet"
    pfad.chmod(0o644)
    ledger = read_portfolio(pfad)
    ledger.loc[ledger.index[0], "betrag"] += 1.0
    write_portfolio(ledger, pfad)
    with pytest.raises(ueb.UebernahmeError, match="registrierten Summe"):
        ueb.lies_uebernahmen(stand / "uebernahme", config)


def test_eingang_prueft_seine_form(tmp_path):
    config = load_config(PLV)
    assert ueb.lies_uebernahmen(tmp_path / "gibt-es-nicht", config) == []
    ohne = tmp_path / "uebernahme" / "ohne"
    ohne.mkdir(parents=True)
    with pytest.raises(ueb.UebernahmeError, match="eingang.json"):
        ueb.lies_uebernahmen(tmp_path / "uebernahme", config)
    assert any("dateien" in f for f in ueb.validate_eingang({"schema_version": 1, "fall": "x", "stichtag": "2026-01-01"}))
    assert any("stichtag" in f for f in ueb.validate_eingang({"schema_version": 1, "fall": "x", "stichtag": "gestern", "dateien": {"bestand.parquet": "0" * 64, "historie.parquet": "0" * 64, "ledger.parquet": "0" * 64}}))
    fall = _fall(tmp_path, "fremd")
    with pytest.raises(ueb.UebernahmeError, match="kein Fall-Arbeitsbereich"):
        ueb.eingang_anlegen(tmp_path / "d", tmp_path / "kein-fall", STICHTAG)
    with pytest.raises(ueb.UebernahmeError, match="fehlen"):
        ueb.eingang_anlegen(tmp_path / "d", fall, STICHTAG, quelle=tmp_path / "leer")
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "2026-01-01"]) == 0
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "2026-01-01"]) == 2
    assert ueb.main(["--stand", str(tmp_path / "d"), "--fall", str(fall), "--stichtag", "kein"]) == 2


def _kleine_config() -> str:
    """Betriebsbeginn am 1.1.2026: das Unternehmen beginnt leer und baut
    seinen Bestand Tag fuer Tag auf (ADR-020) — die echte PLV tut das seit
    1994, die Testwelt nur ueber die Tage des Tests."""
    text = PLV.read_text(encoding="utf-8")
    return re.sub(r"^betriebsbeginn = .*$", "betriebsbeginn = 2026-01-01", text, flags=re.M)


def test_ein_abschluss_der_den_eingang_traegt_macht_ihn_nicht_neu(eingang, monkeypatch):
    """Befund T26-02, Szenario 4: Der Abschluss kannte den Bestand doch.

    Ein Lauf schreibt den Monatsabschluss — unwiderruflich, 0444 — und
    scheitert danach am Bericht. Die Protokollzeile sagt "nicht
    uebernommen", also kennt der naechste Lauf keinen gruenen Vorgaenger,
    der diesen Eingang gefuehrt haette. Er hielt ihn deshalb fuer NEU und
    wies ihn ab: "Stichtag 2026-01-01 liegt nicht nach dem juengsten
    festgeschriebenen Monatsabschluss 2026-01-01". Dauerhaft, ohne Ausweg.

    Die Frage "ist dieser Eingang schon eingerechnet" wurde an einen
    STELLVERTRETER gestellt (das Protokoll), obwohl die Sache selbst
    danebenliegt: Der Abschluss traegt die Zielnummern des Eingangs oder
    er traegt sie nicht.

    Mutationsprobe in der Gegenrichtung steht daneben: Ein Eingang, den
    der Abschluss NICHT kennt, muss weiterhin abgewiesen werden — sonst
    haette die Reparatur die Regel aus ADR-011 aufgehoben statt sie
    genauer zu beantworten.
    """
    from rechner_pipeline.betrieb import tageslauf as tl

    stand, _, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")

    def _kein_bericht(*_a, **_k):
        raise OSError(5, "I/O error")

    monkeypatch.setattr(tl, "_bericht", _kein_bericht)
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    monkeypatch.undo()
    assert code != EXIT_OK and zeile["uebernommen"] is False
    abschluss = ablage.abschluesse / "abschluss_2026-01-01.parquet"
    assert abschluss.is_file(), "ohne festgeschriebenen Abschluss prueft der Test nichts"
    assert not [z for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]

    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert code == EXIT_OK, f"der Retry gelingt nicht: {zeile.get('fehler')}"
    assert zeile["uebernommen"] is True
    assert [u["fall"] for u in zeile["uebernahmen"]] == ["probe-uebernahme"]


def test_ein_eingang_hinter_einem_fremden_abschluss_bleibt_abgewiesen(eingang, tmp_path):
    """Die Gegenrichtung derselben Grenze (ADR-011).

    Ein Abschluss wird nie neu gerechnet. Ein Zugang, der hinter ihn
    zurueckreicht und den er NICHT kennt, bewegte einen Bilanzwert
    rueckwirkend — er bleibt abgewiesen, auch nachdem die Frage genauer
    gestellt wird.
    """
    stand, _, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK

    # Ein ZWEITER Fall, zum 1.1. — hinter dem inzwischen festgeschriebenen
    # Februar-Abschluss, und in keinem von beiden enthalten.
    zweiter = _fall(tmp_path / "zweiter", "spaeter-eingang")
    ueb.eingang_anlegen(stand, zweiter, dt.date(2026, 1, 1))
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 4))
    assert code != EXIT_OK
    assert "liegt nicht nach dem juengsten festgeschriebenen" in zeile["fehler"]


def test_uebernahme_faehrt_im_tagesbetrieb_mit(eingang):
    """Der uebernommene Bestand steht ab dem Stichtag im Stand, seine
    gelieferten Buchungen im Ledger und im Tagesjournal, der Fall-Bezug
    im Protokoll — und die Wache P-B1 ist auf dem Gesamtbestand gruen.

    Mutationsprobe: Uebernahme-Eingang ignoriert — dann fehlen die drei
    Vertraege im Stand und die ZUG-Buchungen im Journal."""
    stand, fall, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 9))
    assert code == EXIT_OK, zeile
    assert zeile["uebernommen"] is True and zeile["pb1"]["urteil"] == "gruen"
    [u] = zeile["uebernahmen"]
    assert (u["fall"], u["stichtag"], u["vertraege"], u["snapshot_sha256"]) == (
        "probe-uebernahme", "2026-01-01", 3, _snapshot_sha(fall))
    # Der Fall des Fixtures traegt einen strukturell geprueften A-M4-Snapshot
    # (T22-06): Rolle aus dem Snapshot, Schluesselklasse in Schema 6 nicht
    # gefuehrt — benannt, nicht leer (B8); die Signatur prueft niemand.
    assert u["zeichnung"]["rolle"] == "mensch/aktuar"
    assert u["zeichnung"]["schluesselklasse"] == "mensch"
    assert u["zeichnung"]["signatur_verifiziert"] is True
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    # Die uebernommenen Vertraege fuehrt der Betrieb unter SEINEN Nummern
    # (Review T24-08). Gefragt wird nicht nach Literalen, sondern ueber die
    # Uebersetzungstabelle — so prueft der Test die Kette Quelle -> Tabelle
    # -> Bestand und nicht eine abgetippte Zahl.
    from rechner_pipeline.models.bestand import POLICENNUMMERN_NAMES

    karte = read_portfolio(
        ablage.uebernahme / "probe-uebernahme" / ueb.POLICENNUMMERN_DATEI,
        expected_columns=POLICENNUMMERN_NAMES)
    abbildung = dict(zip(karte["quelle_police_id"], karte["ziel_police_id"]))
    assert abbildung == {7_000_001: 1, 7_000_002: 2, 7_000_003: 3}
    assert set(abbildung.values()) <= set(gesamt["police_id"])
    # Keine Quellnummer ueberlebt im Betrieb:
    assert not ({7_000_001, 7_000_002, 7_000_003} & set(gesamt["police_id"]))
    assert (gesamt.set_index("police_id").loc[abbildung[7_000_003], "status_code"]) == "PEX"
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    geliefert = ledger[ledger["betrag_herkunft"] == "geliefert"]
    assert len(geliefert) == 3 and set(geliefert["ereignis"]) == {"ZUG"}
    umbuchung = ledger[(ledger["ereignis"] == "PEX")
                       & (ledger["police_id"] == abbildung[7_000_003])]
    assert len(umbuchung) == 1 and umbuchung["status_date"].iloc[0] == pd.Timestamp(STICHTAG)
    journal = read_portfolio(ablage.tagesjournal_pfad)
    ueb_zeilen = journal[journal["herkunft"] == "uebernahme"]
    # Drei gelieferte Zugaenge; die gerechnete Umbuchung ist eine Buchung
    # der Fortschreibungsseite (herkunft fortschreibung), am selben Tag.
    assert len(ueb_zeilen) == 3
    pex_journal = journal[(journal["ereignis"] == "PEX")
                          & (journal["police_id"] == abbildung[7_000_003])]
    assert len(pex_journal) == 1 and pex_journal["buchungsdatum"].iloc[0] == pd.Timestamp("2026-01-01")
    assert (ueb_zeilen["buchungsdatum"] == pd.Timestamp("2026-01-01")).all()   # Donnerstag
    assert zeile["bestand"]["uebernommen_in_force"] == 3


def test_teilbestand_bekommt_seinen_eigenen_monatsbericht(eingang):
    """Konzept, Abschnitt 6: Der Monatsbericht weist den uebernommenen
    Teilbestand getrennt aus, solange der Schalter steht.

    Mutationsprobe: Schalter ignoriert — dann fehlt der Teilbestand-Bericht,
    obwohl teilbestand_getrennt = true in der Config steht."""
    stand, _, _ = eingang
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 2))
    assert code == EXIT_OK, zeile
    abschluesse = zeile["abschluesse"]
    assert [a["stichtag"] for a in abschluesse] == ["2026-01-01", "2026-02-01"]
    assert "bericht" not in abschluesse[0]            # nur der juengste Abschluss wird gerendert
    assert abschluesse[1]["bericht"] == "bestandsbericht_2026-02-01.html"
    assert abschluesse[1]["teilbestaende"] == [
        {"fall": "probe-uebernahme",
         "bericht": "bestandsbericht_2026-02-01_teilbestand-probe-uebernahme.html"}]
    teil = (ablage.berichte / "bestandsbericht_2026-02-01_teilbestand-probe-uebernahme.html").read_text("utf-8")
    assert "Teilbestand probe-uebernahme (uebernommen) zum 2026-02-01" in teil
    # Die Generationentafel des Berichts zaehlt je Generation: im Teilbestand
    # genau die drei uebernommenen KLV-2017-Vertraege, sonst nichts.
    zeilen = re.findall(r"<td>(KLV-\d{4}|BU-\d{4}|TG2015)</td>.*?<td class=\"num\">(\d+)</td></tr>", teil)
    assert dict(zeilen)["KLV-2017"] == "3"
    assert all(anzahl == "0" for name, anzahl in zeilen if name != "KLV-2017")
    gesamt = (ablage.berichte / "bestandsbericht_2026-02-01.html").read_text("utf-8")
    zeilen_gesamt = re.findall(r"<td>(KLV-\d{4}|BU-\d{4}|TG2015)</td>.*?<td class=\"num\">(\d+)</td></tr>", gesamt)
    # KLV-2017 verkauft nicht mehr (Fenster bis 2021): im Gesamtbestand
    # stehen genau die drei uebernommenen, wie im Teilbestand. Der Gesamt-
    # bericht ist MEHR als der Teilbestand, weil das eigene Geschaeft der
    # aktuell verkaufenden Generation (KLV-2025) dazukommt — seit ADR-020
    # entsteht es aus dem Tagesstrom ab Betriebsbeginn.
    assert int(dict(zeilen_gesamt)["KLV-2017"]) == 3
    assert int(dict(zeilen_gesamt).get("KLV-2025", "0")) > 0
    # Ohne den Schalter kein Teilbestand-Bericht:
    aus = Ablage(stand.parent / "aus")
    import shutil
    shutil.copytree(stand, aus.wurzel)
    for p in (aus.stand, aus.journal, aus.abschluesse, aus.berichte):
        shutil.rmtree(p, ignore_errors=True)
    aus.config_pfad.chmod(0o644)
    aus.config_pfad.write_text(
        _kleine_config().replace("teilbestand_getrennt = true", "teilbestand_getrennt = false"),
        encoding="utf-8")
    code, zeile = tageslauf(aus, dt.date(2026, 2, 2))
    assert code == EXIT_OK and "teilbestaende" not in zeile["abschluesse"][1]


def test_ein_abgebrochenes_anlegen_hinterlaesst_keinen_halben_eingang(tmp_path, monkeypatch):
    """Review T22-03: Ein halb geschriebener Eingang blockierte dauerhaft
    ("existiert bereits"). Jetzt entsteht er neben seinem Namen und wird in
    einem Zug umbenannt; der Rest eines Abbruchs zaehlt nicht als Eingang.
    Mutationsprobe: direkt in ziel schreiben -> zweiter Versuch scheitert."""
    fall = _fall(tmp_path)
    stand = tmp_path / "daten"
    aufrufe = {"n": 0}
    echt = ueb.write_portfolio

    def _bricht_beim_zweiten(tabelle, pfad, *a, **k):
        # Beim SCHREIBEN abbrechen, nicht beim Hashen: Seit der Eingang
        # seine Tabellen an den Beleggraphen bindet (T26-03), wird schon
        # vor dem Anlegen gehasht — ein Zaehler auf sha256_bytes traefe
        # dann eine Stelle, an der es noch gar kein Arbeitsverzeichnis
        # gibt, und der Test pruefte nichts mehr.
        aufrufe["n"] += 1
        if aufrufe["n"] == 2:
            raise OSError("Platte weg")
        return echt(tabelle, pfad, *a, **k)

    monkeypatch.setattr(ueb, "write_portfolio", _bricht_beim_zweiten)
    with pytest.raises(OSError):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    monkeypatch.undo()
    ziel = stand / ueb.UEBERNAHME_DIR / "probe-uebernahme"
    rest = stand / ueb.STAGING_DIR / "probe-uebernahme"
    assert not ziel.exists()
    # Der Rest liegt in der Staging-Wurzel, NEBEN der Eingangswurzel — ein
    # Fallname kann ihn dort nicht mehr treffen (T26-01).
    assert rest.exists()
    # Der zweite Versuch gelingt und raeumt den Rest weg.
    assert ueb.eingang_anlegen(stand, fall, STICHTAG) == ziel
    assert ziel.is_dir() and not rest.exists()



# --------------------------------------------------------------------------- #
# Review T22-06: Der Uebernahmeweg glaubt keinem erfundenen Snapshot
# --------------------------------------------------------------------------- #

def test_ohne_am4_snapshot_gibt_es_keine_uebernahme(tmp_path):
    """Nachweis des Reviews: Snapshot optional, takeover_gaps [].
    Mutationsprobe: pruefe_am4_snapshot bei None durchwinken -> rot."""
    fall = _fall(tmp_path, snapshot=None)
    with pytest.raises(ueb.UebernahmeError, match="kein A-M4-Snapshot"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)
    assert not (tmp_path / "daten" / "uebernahme").exists()


def test_ein_erfundener_snapshot_faellt_an_der_selbstadressierung(tmp_path):
    """Nachweis des Reviews: frei erfundene Datei -> read_gate KEIN-GATE,
    Uebernahme trotzdem angelegt. Mutationsprobe: den Hash-Vergleich in
    pruefe_am4_snapshot entfernen -> rot."""
    daten = am4_snapshot("probe-uebernahme")
    daten["entscheider"] = "jemand anderes"          # Inhalt geaendert, Hash nicht
    fall = _fall(tmp_path, snapshot=daten)
    with pytest.raises(ueb.UebernahmeError, match="Selbstadressierung|snapshot_sha256"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)


@pytest.mark.parametrize("gate, entscheid, stichwort", [
    ("A-M1", "angenommen", "nicht A-M4"),
    ("A-M4", "abgelehnt", "ANGENOMMENE"),
])
def test_nur_eine_angenommene_migrationsabnahme_begruendet_die_uebernahme(tmp_path, gate, entscheid, stichwort):
    daten = am4_snapshot("probe-uebernahme", gate=gate, entscheid=entscheid)
    fall = _fall(tmp_path, snapshot=daten)
    # Die Datei liegt unter dem A-M4-Namen, damit der Weg bis zur Pruefung fuehrt.
    with pytest.raises(ueb.UebernahmeError, match=stichwort):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG, snapshot_sha256=daten["snapshot_sha256"])


def test_der_snapshot_muss_zum_fall_gehoeren(tmp_path):
    daten = am4_snapshot("ein-anderer-fall")
    fall = _fall(tmp_path, snapshot=daten)
    with pytest.raises(ueb.UebernahmeError, match="gehoert zum Fall"):
        ueb.eingang_anlegen(tmp_path / "daten", fall, STICHTAG)



def test_die_verankerung_wandert_in_den_stand_und_wird_als_nicht_angewandt_ausgewiesen(tmp_path):
    """Review T22-11 (Stufe 1): Der Eingang registrierte und hashte
    verankerung.parquet, der Tageslauf liess sie fallen — weder im Stand
    noch im Protokoll war der Bedeutungsverlust sichtbar. Jetzt liegt sie
    im Stand (gehasht im Manifest), das Protokoll weist sie als registriert
    und NICHT angewandt aus, die Seite fuehrt die Luecke. Die fachliche
    Anwendung selbst ist Stufe 2 (Fachentscheid offen).
    Mutationsprobe: das Durchreichen in _stand_bauen entfernen -> rot."""
    from rechner_pipeline.bestand.manifest import lies_manifest
    from rechner_pipeline.betrieb import seite as st
    from rechner_pipeline.betrieb.tageslauf import Ablage, EXIT_OK, tageslauf
    from rechner_pipeline.models.bestand import VERANKERUNG_SPALTEN

    fall = _fall(tmp_path)
    quelle = fall / "abgeleitet" / "bestand"
    verankerung = pd.DataFrame([{"police_id": 7_000_001, "monate_ta": 60, "zustand_ta": "beitragspflichtig",
                                 "verweildauer_ta": 0, "dk_ta": 10_000.0}])
    verankerung = verankerung[[s for s, _ in VERANKERUNG_SPALTEN]].astype(dict(VERANKERUNG_SPALTEN))
    write_portfolio(verankerung, quelle / "verankerung.parquet")
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, fall, STICHTAG)
    ablage = Ablage(stand)
    ablage.configs.mkdir(parents=True, exist_ok=True)
    ablage.config_pfad.write_text(_kleine_config(), encoding="utf-8")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 15))
    assert code == EXIT_OK, zeile.get("fehler")
    assert zeile["verankerung"]["registriert"] == 1 and zeile["verankerung"]["angewandt"] is False
    assert (ablage.stand / "verankerung.parquet").is_file()
    assert "verankerung.parquet" in " ".join(lies_manifest(ablage.stand)["ausgaben"].keys()) \
        or any("verankerung" in k for k in lies_manifest(ablage.stand)["ausgaben"])
    luecken = st.luecken(st.stand_modell(ablage))
    assert any("Verankerung" in l["was"] for l in luecken)


def test_die_gepruefte_zeichnung_stammt_aus_den_gepruefte_bytes(tmp_path, monkeypatch):
    """T24-06 Teil A: Wer erst prueft und dann neu liest, prueft eine andere
    Datei als die, die er auswertet.

    ``pruefe_am4_snapshot`` validierte Selbstadressierung, Gate, Entscheid und
    Fall auf dem gelesenen Inhalt — und gab dann die Zeichnung aus einem
    ZWEITEN Lesevorgang zurueck. Ein Tausch dazwischen lieferte eine
    registrierte Zeichnung mit entscheid 'abgelehnt', obwohl 'angenommen'
    geprueft worden war; ohne Abbruch, ohne Hinweis. Der Tausch hier ist der
    Nachbau: die Datei wird nach dem ersten Lesen ersetzt.
    """
    import pathlib

    fall = _fall(tmp_path)
    sha = _snapshot_sha(fall)
    pfad = fall / "entscheide" / f"A-M4-{sha}.json"
    echt = json.loads(pfad.read_text(encoding="utf-8"))
    getauscht = json.dumps({**echt, "entscheid": "abgelehnt"}, ensure_ascii=False)

    echtes_read_text = pathlib.Path.read_text
    gelesen: list = []

    def zaehlend(self, *args, **kw):
        inhalt = echtes_read_text(self, *args, **kw)
        if self == pfad:
            gelesen.append(self)
            if len(gelesen) == 1:
                # Nach dem ersten Lesen die Bytes austauschen — ein zweiter
                # Lesevorgang saehe jetzt eine abgelehnte Abnahme.
                echtes_write = pathlib.Path.write_text
                echtes_write(self, getauscht, encoding="utf-8")
        return inhalt

    monkeypatch.setattr(pathlib.Path, "read_text", zaehlend)
    zeichnung = ueb.pruefe_am4_snapshot(fall, sha)
    monkeypatch.undo()

    assert len(gelesen) == 1, f"der Snapshot wurde {len(gelesen)}-mal gelesen"
    assert zeichnung["entscheid"] == "angenommen"
    assert zeichnung["gate"] == "A-M4"
    # Die Bytes auf der Platte sind tatsaechlich die ausgetauschten — der
    # Test haette also etwas zu finden gehabt.
    assert json.loads(pfad.read_text(encoding="utf-8"))["entscheid"] == "abgelehnt"


@pytest.mark.parametrize("feld, wert, meldung", [
    ("snapshot_sha256", None, "keine SHA-256"),
    ("snapshot_sha256", "kein-hash", "keine SHA-256"),
    ("zeichnung", None, "zeichnung fehlt"),
    ("zeichnung", {"gate": "KEIN-GATE", "entscheid": "angenommen"}, "nicht A-M4"),
    ("zeichnung", {"gate": "A-M4", "entscheid": "abgelehnt"}, "ANGENOMMENE"),
])
def test_ein_eingang_ohne_angenommene_abnahme_wird_abgelehnt(eingang, feld, wert, meldung):
    """T24-06 Teil B: Der Leser prueft, was der Schreiber verlangt.

    ``eingang_anlegen`` laesst keine Uebernahme ohne angenommenes A-M4 zu —
    ``validate_eingang`` nahm bis hierher jede Tabelle an, die es vorfand:
    snapshot_sha256 = None war fehlerfrei, eine Zeichnung mit gate
    'KEIN-GATE' ebenso. Eine Regel, die nur der Schreibpfad kennt, schuetzt
    den nicht, der die Bytes spaeter liest — und gelesen wird der Eingang
    bei JEDEM Tageslauf.
    """
    _, _, ziel = eingang
    daten = json.loads((ziel / "eingang.json").read_text(encoding="utf-8"))
    assert ueb.validate_eingang(daten) == [], "der unveraenderte Eingang muss gruen sein"
    daten[feld] = wert
    fehler = ueb.validate_eingang(daten)
    assert any(meldung in f for f in fehler), f"{feld}={wert!r}: {fehler}"


# --------------------------------------------------------------------------- #
# T24-08: Das Zielsystem vergibt eigene Policennummern
# --------------------------------------------------------------------------- #

def _fall_mit_nummern(wurzel: Path, nummern: list, name: str = "probe-uebernahme") -> Path:
    """Ein Fall wie ``_fall``, dessen drei Vertraege die genannten
    Quellnummern tragen — um eine Lieferung zu bauen, die mit dem eigenen
    Neugeschaeft kollidieren WUERDE."""
    fall = _fall(wurzel, name)
    quelle = fall / "abgeleitet" / "bestand"
    alt = sorted(int(p) for p in read_portfolio(quelle / "bestand.parquet",
                                                expected_columns=STAMM_NAMES)["police_id"])
    tausch = dict(zip(alt, nummern))
    for datei, spalten in (("bestand.parquet", STAMM_NAMES),
                           ("historie.parquet", STATUS_HISTORIE_NAMES),
                           ("ledger.parquet", LEDGER_NAMES)):
        tab = read_portfolio(quelle / datei, expected_columns=spalten)
        tab["police_id"] = [tausch[int(p)] for p in tab["police_id"]]
        write_portfolio(tab, quelle / datei)
    _beleg_neu(fall, name)
    return fall


def test_eine_gelieferte_nummer_kollidiert_nie_mit_dem_eigenen_neugeschaeft(tmp_path):
    """T24-08, der Klassentest: Die eigene Nummernvergabe ist deterministisch
    und damit im Voraus berechenbar — eine Lieferung KANN genau die Nummer
    tragen, die das Tagesneugeschaeft an einem kuenftigen Tag zieht.

    Vorher lief so eine Lieferung ungeprueft durch, und der Lauf an genau
    jenem Tag brach hart ab ("police_ids kollidieren mit dem Basisbestand")
    — Jahre spaeter, zu einem Zeitpunkt, den niemand gewaehlt hat, ohne
    automatischen Ausweg: Die kollidierende eigene Police laesst sich nicht
    ueberspringen, ohne den deterministischen Strom und damit jede spaetere
    ID zu verschieben.

    Seit dem Entscheid des Maintainers (2026-09-15) vergibt das Zielsystem
    eigene Nummern, und die Kollision ist nicht mehr moeglich, statt nur
    frueh gemeldet zu werden.
    """
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.betrieb.neugeschaeft import neugeschaeft_am
    from tests.test_betrieb_tageslauf import _ablage as _welt

    ablage = _welt(tmp_path / "plv")
    config = load_config(ablage.config_pfad)
    kollisionstag = dt.date(2026, 2, 10)
    eigene = sorted(int(p) for p in neugeschaeft_am(config, kollisionstag)["police_id"])
    assert eigene, "die Testwelt verkauft an diesem Tag nichts — der Test saehe nichts"

    fall = _fall_mit_nummern(tmp_path, [eigene[0], eigene[0] + 1, eigene[0] + 2])
    ueb.eingang_anlegen(ablage.wurzel, fall, STICHTAG)
    abbildung = ueb.zielnummern(ablage.uebernahme / "probe-uebernahme")
    assert set(abbildung) == {eigene[0], eigene[0] + 1, eigene[0] + 2}

    # Der Lauf ueber den Kollisionstag hinaus: gruen, kein Abbruch.
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 20))
    assert code == EXIT_OK, zeile.get("fehler") or zeile.get("pb1")
    gesamt = read_portfolio(ablage.stand / "bestand_gesamt.parquet")
    ids = set(gesamt["police_id"])
    # Die gelieferte Nummer gehoert jetzt dem EIGENEN Neugeschaeft, der
    # gelieferte Vertrag lebt unter seiner Zielnummer.
    assert eigene[0] in ids and set(abbildung.values()) <= ids
    eigen_zeile = gesamt.set_index("police_id").loc[eigene[0]]
    assert str(eigen_zeile["tarif_generation"]) != "KLV-2017"


def test_zwei_faelle_teilen_keine_einzige_nummer(tmp_path):
    """Der Punkt, den die merge-session beim Entwurf gesehen hat: Der freie
    Raum ist frei von EIGENGESCHAEFT, nicht frei von anderen Faellen.

    Kollidieren zwei Uebernahmen miteinander, faellt das SPAETER auf als die
    Kollision mit dem eigenen Geschaeft — beide Seiten sind fremd, keine
    Zusicherung trennt sie. Deshalb bekommt jeder Fall sein eigenes Band.
    """
    stand = tmp_path / "daten"
    # Beide Lieferungen tragen ABSICHTLICH dieselben Quellnummern.
    ueb.eingang_anlegen(stand, _fall_mit_nummern(tmp_path / "a", [11, 12, 13], "fall-a"), STICHTAG)
    ueb.eingang_anlegen(stand, _fall_mit_nummern(tmp_path / "b", [11, 12, 13], "fall-b"), STICHTAG)

    a = ueb.zielnummern(stand / "uebernahme" / "fall-a")
    b = ueb.zielnummern(stand / "uebernahme" / "fall-b")
    assert set(a) == set(b) == {11, 12, 13}, "die Quellnummern sollen gleich sein"
    assert not (set(a.values()) & set(b.values())), "zwei Faelle teilen eine Zielnummer"

    baender = ueb.vergebene_baender(stand / "uebernahme")
    assert [(x["von"], x["bis"]) for x in baender] == [(1, 1000), (1001, 2000)]
    for band, karte in zip(baender, (a, b)):
        assert all(band["von"] <= z <= band["bis"] for z in karte.values())


def test_jede_zielnummer_liegt_im_freien_raum(tmp_path):
    """Die Zusicherung, auf der alles steht: Kein Erzeuger der PLV kann
    unter oder auf zehn Millionen vergeben (Nummernkreis k >= 1), also ist
    genau dieser Raum der Heimatraum uebernommener Bestaende."""
    stand = tmp_path / "daten"
    ueb.eingang_anlegen(stand, _fall(tmp_path), STICHTAG)
    ziele = ueb.zielnummern(stand / "uebernahme" / "probe-uebernahme").values()
    assert ziele and all(1 <= z <= ueb.NAMENSRAUM_UEBERNAHME_BIS for z in ziele)


def test_der_freie_raum_ist_endlich_und_sagt_es(tmp_path):
    """Kein stilles Ueberlaufen in den Zahlenraum des Eigengeschaefts: Ist
    der Raum erschoepft, bricht das Registrieren ab und nennt den Ausweg."""
    with pytest.raises(ueb.UebernahmeError, match="Nummernraum erschoepft"):
        ueb.naechstes_band(tmp_path / "leer", ueb.NAMENSRAUM_UEBERNAHME_BIS + 1)


def test_keine_quellnummer_ueberlebt_in_irgendeiner_tabelle(eingang):
    """Umnummeriert wird der GANZE Zugangsstand oder gar nicht: Ein halb
    umnummerierter Bestand zerfaellt — die Historie spraeche dann ueber
    Vertraege, die der Stamm nicht kennt."""
    _, _, ziel = eingang
    abbildung = ueb.zielnummern(ziel)
    quellen, ziele = set(abbildung), set(abbildung.values())
    gesehen = 0
    for name, spalten in {**ueb.PFLICHT, **ueb.OPTIONAL}.items():
        pfad = ziel / f"{name}.parquet"
        if not pfad.is_file():
            continue
        ids = set(read_portfolio(pfad, expected_columns=spalten)["police_id"])
        assert not (ids & quellen), f"{name}.parquet fuehrt noch Quellnummern"
        assert ids <= ziele, f"{name}.parquet nennt eine Police ausserhalb der Uebersetzung"
        if name == "bestand":
            # Beim Stamm die GEGENRICHTUNG mit: Eine Uebersetzung, die mehr
            # Policen nennt als der Bestand fuehrt, behauptet mehr, als der
            # Zugangsstand hergibt. Die Nebentabellen sind per Konstruktion
            # Teilmengen — dort waere die Gegenrichtung Laerm (nicht jeder
            # Vertrag hat Scheiben oder eine Schicht).
            assert ids == ziele, "die Uebersetzungstabelle und der Stamm gehen auseinander"
        gesehen += 1
    assert gesehen >= 3, "weniger Tabellen geprueft als der Zugangsstand fuehrt"


def test_ein_eingang_aus_altem_codestand_nennt_den_ausweg():
    """Betriebsbefund 2026-09-16: Eine Ablage, deren Eingang aus einem
    aelteren Codestand stammt, bricht den Tageslauf hart ab — gemessen an
    der laufenden Vorzeige, die seit T24-08 keinen Stand mehr uebernahm.

    Die Meldung nannte nur den Befund. Die naheliegende Reaktion darauf
    ist die FALSCHE: Wer "erwartet 2" liest, schreibt die 2 in die Datei
    und hat dann einen Eingang, der Schema 2 behauptet, ohne Nummernband
    und ohne Uebersetzungstabelle. Die Regel des Hauses lautet: ein
    harter Fehler mit sprechender Meldung, DIE DEN AUSWEG NENNT.
    """
    fehler = ueb.validate_eingang({
        "schema_version": 1, "fall": "x", "stichtag": "2026-01-01",
        "dateien": {"bestand.parquet": "0" * 64,
                    "historie.parquet": "0" * 64,
                    "ledger.parquet": "0" * 64},
    })
    schema = [f for f in fehler if "schema_version" in f]
    assert schema, fehler
    text = " ".join(schema)
    assert "neuaufsetzen" in text, (
        "die Meldung nennt den Ausweg nicht — sie laedt damit zum "
        "Umschreiben der Datei ein")
    assert "nie umgeschrieben" in text, (
        "die Meldung sagt nicht, dass ein Eingang unveraenderlich ist")


# --------------------------------------------------------------------------- #
# T26-03: Uebernommen wird, was die Abnahme gesehen hat
# --------------------------------------------------------------------------- #

def _tausche_bestand(fall: Path) -> None:
    """Die Stammtabelle NACH der Abnahme veraendern — eine Summe hoch."""
    pfad = fall / "abgeleitet" / "bestand" / "bestand.parquet"
    tab = read_portfolio(pfad, expected_columns=STAMM_NAMES)
    tab.loc[0, "sum_insured"] = 1_042_999.0
    write_portfolio(tab, pfad)


def _ohne_beleggraph(fall: Path) -> None:
    """Der Snapshot nennt einen Pflichtbeleg, den es nicht gibt."""
    (fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json").unlink()
    daten = am4_snapshot("probe-uebernahme", pb1_ledger_sha="ab" * 32)
    for alt in (fall / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")


def _widersprechender_graph(fall: Path) -> None:
    """Zwei Belege desselben Snapshots nennen verschiedene Stammtabellen."""
    import hashlib

    zweiter = {
        "schema_version": 1, "command": "abnahmebericht", "gate": "A-M4",
        "status": "passed",
        "provenienz": {"eingaben": {
            "abgeleitet/bestand/bestand.parquet": "cd" * 32}},
    }
    pfad = fall / "abgeleitet" / "diagnostics" / "abnahmebericht.gate.json"
    roh = json.dumps(zweiter, ensure_ascii=False, sort_keys=True).encode("utf-8")
    pfad.write_bytes(roh)
    erster = (fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json")
    daten = am4_snapshot(
        "probe-uebernahme",
        pb1_ledger_sha=hashlib.sha256(erster.read_bytes()).hexdigest())
    daten["pflichtbelege"]["abnahmebericht"] = [hashlib.sha256(roh).hexdigest()]
    daten["snapshot_sha256"] = ueb_p9_sha(daten)
    for alt in (fall / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")


def _pk1_luege(fall: Path) -> None:
    """Der Snapshot behauptet Generationenbelege, die er nicht auffuehrt."""
    import hashlib

    erster = (fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json")
    daten = am4_snapshot(
        "probe-uebernahme",
        pb1_ledger_sha=hashlib.sha256(erster.read_bytes()).hexdigest())
    daten["pk1_belege"] = {"klv/tg2015": ["ef" * 32]}
    daten["snapshot_sha256"] = ueb_p9_sha(daten)
    for alt in (fall / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")


def ueb_p9_sha(daten: dict) -> str:
    """Einen MUTIERTEN Snapshot schliessen: nachsignieren (Testschluessel),
    dann selbstadressieren — wie das Gate einen echten schliesst. Seit der
    Betriebseingang die Freigabesignatur prueft (T26-03, Weg 2), faellt ein
    nur neu adressierter Snapshot an der Signatur, bevor die Tabellenbindung
    gelesen wird; die Manipulationslagen unten pruefen aber gerade die
    Bindung. Wer eine KAPUTTE Signatur will, baut sie ausdruecklich
    (tests/test_belegrollen_und_zeichnung_t2603.py)."""
    from rechner_pipeline.models.freigabe import freigabe_fuer
    from rechner_pipeline.models.schemas import p9_snapshot_sha256
    from tests.freigabe_testschluessel import TESTKEY
    if daten.get("entscheid") == "angenommen":
        ohne = {k: v for k, v in daten.items() if k not in ("freigabe", "snapshot_sha256")}
        daten["freigabe"] = freigabe_fuer(ohne, TESTKEY)
    return p9_snapshot_sha256(daten)


#: Die Lagen, in denen die Uebernahme etwas anderes waere als das
#: Abgenommene — samt dem Stichwort, an dem der Eingang sie benennt.
ABNAHMELAGEN = [
    (_tausche_bestand, "bezeugt"),
    (_ohne_beleggraph, "keinen Hash"),
    (_widersprechender_graph, "widerspricht sich"),
    (_pk1_luege, "nicht stimmig"),
]


@pytest.mark.parametrize("manipulation,stichwort",
                         ABNAHMELAGEN,
                         ids=[m.__name__ for m, _ in ABNAHMELAGEN])
def test_uebernommen_wird_nur_was_die_abnahme_gesehen_hat(
        tmp_path, manipulation, stichwort):
    """Befund T26-03: Der Laufzeiteingang las die Quelltabellen, nummerierte
    sie um und registrierte sie — ohne jeden Bezug zu dem, was die
    Migrationsabnahme abgenommen hat. "Kein Quelltabellenhash steht in den
    behaupteten Snapshot-Artefakten."

    Geprueft wird die Klasse, nicht der gemeldete Fall: die nach der
    Abnahme getauschte Tabelle, der Snapshot ohne existierenden
    Beleggraphen, der sich widersprechende Graph und die Luege in den
    Generationenbelegen. Und nichts davon darf einen halben Eingang
    hinterlassen — geprueft wird VOR dem ersten Seiteneffekt.
    """
    fall = _fall(tmp_path)
    manipulation(fall)
    stand = tmp_path / "daten"
    with pytest.raises(ueb.UebernahmeError, match=stichwort):
        ueb.eingang_anlegen(stand, fall, STICHTAG)
    assert not (stand / ueb.UEBERNAHME_DIR).exists()
    assert not (stand / ueb.STAGING_DIR).exists()


# --------------------------------------------------------------------------- #
# T26-13: Die Bruecke zwischen Quell- und Zielnummern wird geprueft
# --------------------------------------------------------------------------- #

def _verbiege_map(eingang: Path, wie: str) -> None:
    """Die registrierte Uebersetzungstabelle nachtraeglich veraendern."""
    pfad = eingang / ueb.POLICENNUMMERN_DATEI
    pfad.chmod(0o644)
    if wie == "geloescht":
        pfad.unlink()
        return
    tab = read_portfolio(pfad, expected_columns=ueb.POLICENNUMMERN_NAMES)
    if wie == "falsche_zielnummer":
        tab.loc[0, "ziel_police_id"] = 999
    elif wie == "doppelte_zielnummer":
        tab.loc[0, "ziel_police_id"] = int(tab.loc[1, "ziel_police_id"])
    elif wie == "eine_zeile_fehlt":
        tab = tab.iloc[1:].reset_index(drop=True)
    elif wie == "mitsamt_manifest":
        # Der harte Fall: Die Map wird verbogen UND das Manifest
        # nachgezogen. Der Hash stimmt dann wieder — es bleibt nur die
        # Frage, ob die Bruecke inhaltlich traegt.
        tab = tab.iloc[1:].reset_index(drop=True)
    else:  # pragma: no cover
        raise AssertionError(wie)
    write_portfolio(tab, pfad)
    if wie == "mitsamt_manifest":
        manifest = eingang / ueb.EINGANG_DATEI
        manifest.chmod(0o644)
        daten = json.loads(manifest.read_text(encoding="utf-8"))
        daten["dateien"][ueb.POLICENNUMMERN_DATEI] = ueb.sha256_bytes(
            pfad.read_bytes())
        manifest.write_text(
            json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")


#: Die Lagen, in denen die Bruecke nicht mehr traegt. "geloescht" ist der
#: Fall, bei dem der Tageslauf frueher GRUEN blieb.
BRUECKENLAGEN = [
    ("falsche_zielnummer", "SHA-256"),
    ("doppelte_zielnummer", "SHA-256"),
    ("eine_zeile_fehlt", "SHA-256"),
    ("geloescht", "fehlt"),
    # Ohne diese Zeile pruefte nichts die INHALTLICHE Bruecke: Die drei
    # oberen fallen schon am Hash, und der Bijektions-Test daneben ruft
    # die Funktion direkt auf. Ein Aufruf, der aus lies_uebernahme
    # verschwindet, faellt nur hier auf.
    ("mitsamt_manifest", "Uebersetzung"),
]


@pytest.mark.parametrize("wie,stichwort", BRUECKENLAGEN)
def test_eine_verbogene_uebersetzung_faellt_beim_lesen(tmp_path, wie, stichwort):
    """Befund T26-13: policennummern.parquet war im Manifest verpflichtend
    und gehasht — gelesen hat sie niemand gegen diesen Hash.

    Eine Mutation nur an der Map, Manifest unveraendert, lieferte eine
    falsche Zielidentitaet; bei vollstaendigem Verlust der Bruecke blieb
    sogar die Tagesfuehrung gruen. Der Docstring versprach dabei
    ausdruecklich "wer sie aendert, bricht den Hash" — ein Satz, den
    niemand geprueft hat.
    """
    from rechner_pipeline.bestand.config import load_config

    stand = tmp_path / "daten"
    ziel = ueb.eingang_anlegen(stand, _fall(tmp_path), STICHTAG)
    cfg_pfad = tmp_path / "bestand.toml"
    cfg_pfad.write_text(_kleine_config(), encoding="utf-8")
    config = load_config(cfg_pfad)
    # Positivkontrolle: unveraendert wird gelesen, und die Bruecke steht
    # im gelesenen Eingang.
    [gelesen] = ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, config)
    assert len(gelesen.uebersetzung) == 3

    _verbiege_map(ziel, wie)
    with pytest.raises(ueb.UebernahmeError, match=stichwort):
        ueb.lies_uebernahmen(stand / ueb.UEBERNAHME_DIR, config)


#: Die Bijektivitaet als Tabelle — geprueft an der reinen Funktion, damit
#: jede Verletzung einzeln sichtbar wird und nicht hinter dem Hash
#: verschwindet.
UEBERSETZUNGSLAGEN = [
    ("vollstaendig und eindeutig", {1: 10, 2: 11, 3: 12}, [10, 11, 12], False),
    ("zwei Quellen auf dieselbe Police", {1: 10, 2: 10}, [10], True),
    ("gefuehrte Police ohne Quellnummer", {1: 10}, [10, 11], True),
    ("Uebersetzung nennt eine fremde Police", {1: 10, 2: 99}, [10], True),
    ("Zielnummer ausserhalb des Bands", {1: 10, 2: 5000}, [10, 5000], True),
]


@pytest.mark.parametrize("was,abbildung,gefuehrt,fehlerhaft",
                         UEBERSETZUNGSLAGEN)
def test_die_bruecke_muss_eine_bijektion_sein(was, abbildung, gefuehrt, fehlerhaft):
    """Ein gehashter Beleg sagt nur, dass die Datei nicht veraendert
    wurde — nicht, dass sie stimmt. Beide Richtungen geprueft: Die
    vollstaendige, eindeutige Bruecke MUSS durchgehen."""
    bestand = pd.DataFrame({"police_id": gefuehrt})
    fehler = ueb.uebersetzung_fehler(abbildung, bestand, {"von": 1, "bis": 1000})
    assert bool(fehler) is fehlerhaft, (was, fehler)


def test_gleichnamige_tabellen_an_zwei_orten_sind_kein_widerspruch(tmp_path):
    """Ein Fall traegt denselben Tabellennamen an mehreren Orten, und alle
    sind richtig: ``abgeleitet/bestand/historie.parquet`` ist der
    uebernommene Stand, ``abgeleitet/bestand-nach/historie.parquet`` der
    fortgeschriebene.

    Auf den Basisnamen verkuerzt sahen zwei Zeugen, die sich einig sind,
    wie ein Widerspruch aus — und das Neuaufsetzen brach ab. Gemessen an
    faelle/baldrian-klv-tg2015-lauf2: VIER Verzeichnisse mit
    historie.parquet, zwei davon in den Pflichtbelegen.

    Die Gegenrichtung steht daneben: Zwei Belege, die ueber DENSELBEN
    Pfad Verschiedenes sagen, bleiben ein Widerspruch
    (test_uebernommen_wird_nur_was_die_abnahme_gesehen_hat).
    """
    import hashlib

    fall = _fall(tmp_path)
    nach = fall / "abgeleitet" / "bestand-nach"
    nach.mkdir(parents=True)
    # Ein zweiter, ANDERER Stand derselben Tabellennamen — wie ihn die
    # Fortschreibung erzeugt.
    for datei in ("historie.parquet", "bestand.parquet", "ledger.parquet"):
        (nach / datei).write_bytes(
            (fall / "abgeleitet" / "bestand" / datei).read_bytes() + b"\x00")
    zweiter = {
        "schema_version": 1, "command": "fuehrungsprobe", "gate": "A-M4",
        "status": "passed",
        "provenienz": {"eingaben": {
            f"abgeleitet/bestand-nach/{d}": hashlib.sha256(
                (nach / d).read_bytes()).hexdigest()
            for d in ("historie.parquet", "bestand.parquet", "ledger.parquet")}},
    }
    pfad = fall / "abgeleitet" / "diagnostics" / "fuehrungsprobe.gate.json"
    roh = json.dumps(zweiter, ensure_ascii=False, sort_keys=True).encode("utf-8")
    pfad.write_bytes(roh)
    erster = fall / "abgeleitet" / "diagnostics" / "bestand_validate.gate.json"
    daten = am4_snapshot(
        "probe-uebernahme",
        pb1_ledger_sha=hashlib.sha256(erster.read_bytes()).hexdigest())
    daten["pflichtbelege"]["fuehrungsprobe"] = [hashlib.sha256(roh).hexdigest()]
    daten["snapshot_sha256"] = ueb_p9_sha(daten)
    for alt in (fall / "entscheide").glob("A-M4-*.json"):
        alt.unlink()
    (fall / "entscheide" / f"A-M4-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten, ensure_ascii=False), encoding="utf-8")
    (fall / "abgeleitet" / "diagnostics" / "gate_entscheid_am4.gate.json").write_text(
        json.dumps({"summary": {"snapshot_sha256": daten["snapshot_sha256"]}}),
        encoding="utf-8")

    # Beide Belege werden gelesen, beide Orte sind bezeugt — und der
    # Eingang entsteht, gebunden an den Stand SEINES Pfades.
    ziel = ueb.eingang_anlegen(stand := tmp_path / "daten", fall, STICHTAG)
    assert ziel.is_dir()
    snapshot, _, _verifiziert = ueb.lies_am4_snapshot(fall, _snapshot_sha(fall))
    belegt = ueb.belegte_tabellen(fall, snapshot)
    quelle = fall / "abgeleitet" / "bestand"
    for datei in ("historie.parquet", "bestand.parquet", "ledger.parquet"):
        assert ueb.bezeugter_hash(belegt, fall, quelle / datei, datei) == (
            hashlib.sha256((quelle / datei).read_bytes()).hexdigest()), datei
        assert ueb.bezeugter_hash(belegt, fall, nach / datei, datei) == (
            hashlib.sha256((nach / datei).read_bytes()).hexdigest()), datei
