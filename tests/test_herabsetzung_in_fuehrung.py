"""Die Herabsetzung in der produktiven Fuehrung (Review T25-06).

Der Kernbaustein fuer die Beitragsreduktion war fertig und fachlich
abgenommen, gerufen wurde er nur von der Pruefstrecke — das "kann ohne
tut", das der Befund benennt. Hier wird er gefahren: Die Ereignis-Engine
zieht eine Herabsetzung, die Bewertung rechnet den geknickten Verlauf,
und P-B1 leitet beide Buchungen aus dem Kern her.

Die Korrekturschicht geht dabei VOLLSTAENDIG in die Neuberechnung ein
(Entscheid des Maintainers 2026-09-15): Die Herabsetzung garantiert die
Tat, nicht den Wert; sie ist eine Neuvereinbarung und schiebt den Vertrag
in die Logik des Zielsystems. Kein Sprung an der Naht, danach keine
Schicht und kein Korrekturtermin — und der absorbierte Betrag steht als
eigene Ledger-Zeile, sonst verschwaende er aus dem Ausweis.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.korrekturschicht import schichtwert_bei
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    model_point_kwargs,
    validate_reduktionen,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen

BIS = _dt.date(2046, 1, 1)
POLICEN = list(range(900_001, 900_041))
ANTEIL = 0.6


def _config(mit_red: bool):
    if not mit_red:
        return config_aus_text(_CONFIG_TOML)
    toml = _CONFIG_TOML.replace(
        "[annahmen]\nerh_prozent = 0.05",
        f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {ANTEIL}",
    ) + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    return config_aus_text(toml)


@pytest.fixture(scope="module")
def welt():
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                    for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    ohne = fortschreiben(stamm, _config(False), BIS,
                         schichten=schichten, verankerung=verankerung)
    mit = fortschreiben(stamm, _config(True), BIS,
                        schichten=schichten, verankerung=verankerung)
    return stamm, schichten, verankerung, ohne, mit


#: Fingerabdruck des Fixture-Laufs OHNE Herabsetzung, gemessen auf dem
#: Stand VOR dem Feature (55c341b). Er ist der eigentliche Beweis fuer
#: den eigenen Zufallsstrom.
#:
#: Ein Vergleich zweier Laeufe DIESES Standes taugte dafuer nicht: Der
#: zusaetzliche Draw traefe beide gleich, und der Vergleich saehe ihn
#: nicht — dieselbe Blindheit wie bei jedem Zwei-Welten-Test, dessen
#: beide Welten aus demselben Code stammen. Erst der Bezug nach draussen
#: macht ihn scharf.
VOR_DER_HERABSETZUNG = {
    "ledger": "93eb2d6d54311549964de02511d05fd1951feec412e9f8aa05ecdab87433089b",
    "historie": "1a7c7272cad9e89c6c8c1112b903bbd4d7e7f4bbf5aa7425a10dcf49fcb80414",
    "scheiben": "12d1304e35328f68dee92a54e2b4d3486a4435bb2380e52f0b8779336e15f95a",
}


def test_ohne_herabsetzung_ist_der_bestand_derselbe_wie_zuvor(welt):
    """Die Ratsche fuer HERABSETZUNG_STREAM.

    Die feste Draw-Reihenfolge des Hauptstroms traegt die pfadweise
    Vergleichbarkeit der Laeufe: Dort verbraucht auch eine Rate von 0
    ihren Draw. Ein RED-Draw in dieser Reihenfolge haette deshalb JEDEN
    bestehenden Bestand verschoben, ohne dass sich fachlich etwas
    aendert. Gemessen gegen den Stand davor, nicht gegen einen zweiten
    Lauf desselben Standes."""
    import hashlib

    _stamm_, _s, _v, ohne, _mit = welt
    for name, df in (("ledger", ohne.ledger), ("historie", ohne.historie),
                     ("scheiben", ohne.scheiben)):
        roh = df.to_csv(index=False).encode("utf-8")
        assert hashlib.sha256(roh).hexdigest() == VOR_DER_HERABSETZUNG[name], name


def test_der_eigene_strom_verschiebt_keinen_bestehenden_bestand(welt):
    """Der Grund fuer HERABSETZUNG_STREAM, als Messung.

    Die feste Draw-Reihenfolge des Hauptstroms traegt die pfadweise
    Vergleichbarkeit der Laeufe. Ein neuer Draw in ihr haette jeden
    bestehenden Bestand verschoben — auch bei Rate 0, denn dort
    verbraucht jede Rate ihren Draw. Gemessen wird deshalb nicht die
    Absicht, sondern das Ergebnis: Tod, Storno, Beitragsfreistellung und
    Ablauf muessen Zeile fuer Zeile dieselben bleiben."""
    _stamm_, _s, _v, ohne, mit = welt
    unberuehrt = ("TOD", "STO", "PEX", "ABL")
    pfad = ["police_id", "ereignis", "vertragsjahr", "status_date"]
    a = ohne.ledger[ohne.ledger["ereignis"].isin(unberuehrt)]
    b = mit.ledger[mit.ledger["ereignis"].isin(unberuehrt)]
    # WELCHES Ereignis WANN faellt, haengt allein an den Draws.
    pd.testing.assert_frame_equal(
        a[pfad].reset_index(drop=True), b[pfad].reset_index(drop=True))
    assert len(a) > 0, "Fixture ohne Abgaenge bezeugt nichts"
    # Die BETRAEGE duerfen sich unterscheiden, aber nur dort, wo wirklich
    # herabgesetzt wurde — sonst waere die Herabsetzung ein Rundschlag.
    reduziert = set(int(p) for p in mit.reduktionen["police_id"])
    a_rest = a[~a["police_id"].isin(reduziert)].reset_index(drop=True)
    b_rest = b[~b["police_id"].isin(reduziert)].reset_index(drop=True)
    pd.testing.assert_frame_equal(a_rest, b_rest)
    assert len(a_rest) > 0
    # Und die Herabsetzung passiert wirklich.
    assert len(mit.reduktionen) > 0
    assert (mit.ledger["ereignis"] == "RED").sum() > 0


def test_die_tabelle_haelt_ihren_eigenen_vertrag_ein(welt):
    stamm, _s, _v, _ohne, mit = welt
    assert validate_reduktionen(stamm, mit.reduktionen, mit.historie) == []
    assert set(mit.reduktionen["verfahren"]) == {"prospektiv"}
    assert (mit.reduktionen["anteil"] == ANTEIL).all()


def test_jede_herabsetzung_bucht_summe_und_absorbierte_schicht(welt):
    """Zwei Zeilen je Vorfall: die neue Gesamtsumme und der Schichtbetrag,
    der in die Neuberechnung eingegangen ist. Ohne die zweite faellt die
    Spalte korrekturschicht des Abschlusses ab hier auf null, und niemand
    saehe, wohin der Betrag ging."""
    stamm, _s, _v, _ohne, mit = welt
    felder = _config(True).generationen[0].generation_fields()
    haupt = stamm.set_index("police_id")
    red = mit.ledger[mit.ledger["ereignis"] == "RED"]
    for zeile in mit.reduktionen.to_dict("records"):
        pid, jahr = int(zeile["police_id"]), int(zeile["reduktion_jahr"])
        zeilen = red[(red["police_id"] == pid) & (red["vertragsjahr"] == jahr)]
        arten = dict(zip(zeilen["betrag_art"], zeilen["betrag"]))
        assert set(arten) == {"VS_herabsetzung", "dDK_absorption"}
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], felder))
        erwartet = schichtwert_bei(_parameter(), MONATE_TA, mp, 12 * jahr)
        assert erwartet > 0.0
        assert arten["dDK_absorption"] == pytest.approx(erwartet, rel=1e-12)


def test_die_bewertung_ist_an_der_naht_wertstetig(welt):
    """Die fachliche Zusage, gegen eine unabhaengige Groesse gemessen:
    Das Deckungskapital des herabgesetzten Vertrags am Jahrestag ist genau
    das des ungekuerzten EINSCHLIESSLICH Schicht."""
    stamm, sch, ver, _ohne, mit = welt
    cfg = _config(True)
    geprueft = 0
    for zeile in mit.reduktionen.to_dict("records"):
        pid, jahr = int(zeile["police_id"]), int(zeile["reduktion_jahr"])
        stichtag = _dt.date(2015 + jahr, 1, 1)
        gemeinsam = dict(scheiben=mit.scheiben, schichten=sch, verankerung=ver)
        a = {z["police_id"]: z for z in einzelwerte_am(
            stamm, mit.historie, cfg, stichtag,
            reduktionen=mit.reduktionen, **gemeinsam)}[pid]
        b = {z["police_id"]: z for z in einzelwerte_am(
            stamm, mit.historie, cfg, stichtag, **gemeinsam)}[pid]
        if a["status"] != "POL":
            continue
        assert a["deckungskapital"] == pytest.approx(
            b["deckungskapital"], rel=1e-12)
        # Der ungekuerzte Wert ENTHAELT die Schicht; der herabgesetzte
        # weist keine mehr aus — sie ist in seiner Basis aufgegangen.
        assert b["korrekturschicht"] > 0.0
        assert a["korrekturschicht"] == 0.0
        # Beitrag und Summe folgen der Vereinbarung.
        assert a["jahresbeitrag"] == pytest.approx(
            b["jahresbeitrag"] * ANTEIL, rel=1e-12)
        assert a["leistung"] > b["leistung"]
        geprueft += 1
    assert geprueft >= 1


def test_ohne_die_tabelle_bewertet_die_fuehrung_den_falschen_vertrag(welt):
    """Die Gegenprobe zum Test darueber: Wer die Herabsetzung nicht
    mitliefert, bekommt den ungekuerzten Beitrag — deshalb muss die
    Tabelle den Betriebsweg mitlaufen."""
    stamm, sch, ver, _ohne, mit = welt
    cfg = _config(True)
    zeile = mit.reduktionen.iloc[0]
    pid, jahr = int(zeile["police_id"]), int(zeile["reduktion_jahr"])
    stichtag = _dt.date(2015 + jahr + 2, 1, 1)
    gemeinsam = dict(scheiben=mit.scheiben, schichten=sch, verankerung=ver)
    a = {z["police_id"]: z for z in einzelwerte_am(
        stamm, mit.historie, cfg, stichtag,
        reduktionen=mit.reduktionen, **gemeinsam)}[pid]
    b = {z["police_id"]: z for z in einzelwerte_am(
        stamm, mit.historie, cfg, stichtag, **gemeinsam)}[pid]
    assert a["jahresbeitrag"] < b["jahresbeitrag"]


def test_p_b1_leitet_jede_buchung_her_und_vermisst_die_tabelle(welt):
    """Die Herleitung geht denselben Weg wie die Engine — und ohne die
    Reduktionstabelle findet sie die Betraege nicht mehr aus dem Kern."""
    stamm, sch, ver, _ohne, mit = welt
    cfg = _config(True)
    gen = cfg.generationen[0]
    zug = pd.DataFrame([{
        "police_id": p, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for p in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(
        dict(LEDGER_SPALTEN))
    voll = pd.concat([zug, mit.ledger], ignore_index=True)
    gemeinsam = dict(scheiben=mit.scheiben, historie=mit.historie,
                     schichten=sch, verankerung=ver)
    assert pruefe_ledger_betraege(
        stamm, voll, cfg, reduktionen=mit.reduktionen, **gemeinsam) == []
    ohne_tabelle = pruefe_ledger_betraege(stamm, voll, cfg, **gemeinsam)
    assert ohne_tabelle and "RED" in ohne_tabelle[0]


def test_eine_rate_ohne_hoehe_ist_ein_config_fehler():
    """Eine Herabsetzung auf 0 waere eine Beitragsfreistellung."""
    toml = _CONFIG_TOML + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n"
    befunde = config_aus_text(toml).validate()
    assert any("red_anteil" in b for b in befunde)
    # Und mit Hoehe ist sie in Ordnung.
    assert _config(True).validate() == []


# --- Der Betriebsweg: die Tabelle laeuft mit -----------------------------
#
# Eine Nebentabelle, die der Erzeuger schreibt und der Betrieb nicht
# mitfuehrt, ist der Betriebsbefund N-01 in neuer Gestalt: Die Fuehrung
# rechnet mit ihr, die Wache ohne sie, und das richtige Ledger faellt als
# falsch auf. Deshalb steht reduktionen in ROLLEN_DATEIEN — Manifest,
# P-B1-Rolle, Wache und Teilbestand folgen daraus.


def _lauf_mit_herabsetzung(tmp_path):
    from rechner_pipeline.bestand import cli_fortschreibung as fs_cli
    from rechner_pipeline.bestand.parquet_io import write_portfolio

    stamm = _stamm([{"id": p, "beginn": "2015-01-01"} for p in POLICEN])
    portfolio = tmp_path / "eigen.parquet"
    write_portfolio(stamm, portfolio)
    cfg = tmp_path / "cfg.toml"
    cfg.write_text(
        _CONFIG_TOML.replace(
            "[annahmen]\nerh_prozent = 0.05",
            f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {ANTEIL}",
        ) + "\n[annahmen.herabsetzung]\na = 0.08\nb = 0.0\n",
        encoding="utf-8")
    out = tmp_path / "lauf"
    code = fs_cli.main([
        "--config", str(cfg), "--bis", "2046-01-01",
        "--portfolio", str(portfolio), "--out-dir", str(out),
    ])
    assert code == 0
    return out, cfg


def test_der_lauf_schreibt_die_tabelle_und_das_manifest_bindet_sie(tmp_path):
    from rechner_pipeline.bestand.manifest import (
        NEBENTABELLEN,
        ROLLEN_DATEIEN,
        lauf_eingaben,
        lies_manifest,
    )

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    assert "reduktionen" in ROLLEN_DATEIEN and "reduktionen" in NEBENTABELLEN
    pfad = out / ROLLEN_DATEIEN["reduktionen"]
    assert pfad.is_file(), "der Lauf traegt seine Herabsetzungen nicht"
    # Der Lieferschein bindet sie wie jede andere Ausgabe.
    manifest = lies_manifest(out)
    assert ROLLEN_DATEIEN["reduktionen"] in manifest["ausgaben"]
    # Und die Rollentabelle reicht sie an jeden Konsumenten weiter.
    assert "reduktionen" in lauf_eingaben(out, cfg)


def test_p_b1_prueft_die_tabelle_und_leitet_die_buchungen_her(tmp_path):
    """Die Wache bekommt dieselben Eingaben wie der Erzeuger — sonst
    rechnet sie den herabgesetzten Vertrag ungekuerzt nach und meldet das
    richtige Ledger als falsch (N-01)."""
    from rechner_pipeline.bestand.manifest import lauf_eingaben, lies_manifest
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    eingaben = lauf_eingaben(out, cfg)
    _tabellen, geprueft, fehler, _usage = lies_und_pruefe_pb1(
        eingaben, bis=_dt.date(2046, 1, 1), manifest=lies_manifest(out))
    assert fehler == [], fehler[:3]
    assert geprueft["reduktionen_zeilen"] > 0
    # Der Beleg zaehlt die hergeleiteten Betraege — RED eingeschlossen.
    # Ein Literal an dieser Stelle haette sie unterschlagen und ein zu
    # kleines Testat ausgewiesen.
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    ledger = read_portfolio(out / "ledger.parquet")
    assert geprueft["betraege_hergeleitet"] >= int(
        (ledger["ereignis"] == "RED").sum())


def test_die_wache_ohne_die_tabelle_meldet_das_richtige_ledger_als_falsch(
    tmp_path,
):
    """Die Gegenprobe zu N-01, an der neuen Tabelle: Wird sie nicht
    mitgefuehrt, ist der Lauf gruen und die Pruefung rot."""
    from rechner_pipeline.bestand.manifest import lauf_eingaben, lies_manifest
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    out, cfg = _lauf_mit_herabsetzung(tmp_path)
    manifest = lies_manifest(out)
    eingaben = {r: p for r, p in lauf_eingaben(out, cfg).items()
                if r != "reduktionen"}
    _t, _g, fehler, _u = lies_und_pruefe_pb1(
        eingaben, bis=_dt.date(2046, 1, 1), manifest=manifest)
    assert any("RED" in str(f.get("message", "")) for f in fehler), fehler[:2]


def test_jede_erzeugerrolle_braucht_einen_spaltenvertrag(monkeypatch, tmp_path):
    """Die Ratsche hinter dem Fund beim Einbau: Die P-B1-Engine lief ueber
    eine ZWEITE, handgepflegte Rollenliste neben ihrem Spaltenvertrag. Eine
    neue Erzeugerrolle fiel still hindurch — nicht gelesen, nicht geprueft,
    und trotzdem Exit 0. Ohne Positivkontrolle waere diese Ableitung eine
    Ratsche mit null Treffern."""
    from rechner_pipeline.bestand import manifest as m
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    monkeypatch.setitem(m.ROLLEN_DATEIEN, "phantom", "phantom.parquet")
    with pytest.raises(ValueError, match="ohne Spaltenvertrag"):
        lies_und_pruefe_pb1({"portfolio": tmp_path / "x.parquet"},
                            bis=None, manifest=None)


def test_in_den_stand_kommt_nur_eine_gebuchte_herabsetzung():
    """Der Tagesbetrieb schneidet auf den Buchungsstand. Eine Herabsetzung
    gehoert in den Stand, wenn ihre RED-Zeile darin steht — abgeleitet aus
    dem Ledger, nicht als zweite Regel auf dem Reduktionsdatum."""
    from rechner_pipeline.betrieb.tageslauf import _gebuchte_reduktionen

    reduktionen = pd.DataFrame({
        "police_id": [1, 2],
        "reduktion_jahr": [5, 6],
        "reduktion_datum": [pd.Timestamp("2020-01-01"),
                            pd.Timestamp("2021-01-01")],
        "anteil": [0.6, 0.6],
        "verfahren": ["prospektiv", "prospektiv"],
    })
    ledger = pd.DataFrame({
        "police_id": [1, 2], "ereignis": ["RED", "STO"],
    })
    gebucht = _gebuchte_reduktionen(reduktionen, ledger)
    assert list(gebucht["police_id"]) == [1]
    # Ohne Tabelle bleibt es dabei.
    assert _gebuchte_reduktionen(None, ledger) is None
