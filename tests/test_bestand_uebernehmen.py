"""Bestandsuebernahme: der Zustand kommt aus der Geschichte.

Das Zielmodell fuehrt im Stamm den JUENGSTEN Journalstand und in der
Statushistorie die Wechsel ab ``status_id 2``; ``POL`` ist dort fuer die
KLV gar nicht zulaessig, weil es der implizite Ursprung ist. P-B1 prueft
beide Seiten gegeneinander.

Fuer einen uebernommenen Vertrag folgt daraus: Ein beitragsfrei
gestellter Vertrag ist kein Vertrag mit einem anderen Feld, sondern ein
Vertrag mit einer Geschichte — als POL begonnen, irgendwann eine
PEX-Zeile bekommen. Wer das verwechselt, fuehrt ihn auf dem falschen
Track (gamma3, VS_bfr) und rechnet ihn still falsch.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt

import pytest

from rechner_pipeline.gates.bestand_uebernehmen import GEVO_STATUS, baue

ZEILE = {
    "police_id": 7000001, "beginn": "2016-02-01", "entry_age": 37,
    "sex": "M", "duration": 12, "premium_duration": 7,
    "sum_insured": 66000.0, "zahlweise": 12,
}


#: Rechnungsgrundlagen der Generation. Nur noetig, sobald ein Vertrag
#: beitragsfrei uebernommen wird: Dann bucht die Uebernahme die Umbuchung
#: in den beitragsfreien Bestand und muss deren Summe rechnen.
GRUNDLAGEN = {
    "zins": 0.0125, "tafel": "DAV2008_T_NR_U70", "alpha": 0.025,
    "beta1": 0.03, "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
    "policy_fee": 12.0, "min_alter_flex": 60, "min_rlz_flex": 5,
}


def _baue(vorgeschichte=None, grundlagen=GRUNDLAGEN):
    return baue(
        [dict(ZEILE)], tarif_generation="TG2015", produkt="klv",
        stichtag=dt.date(2026, 1, 1), vorgeschichte=vorgeschichte or {},
        generationsfelder=grundlagen,
    )


def test_ohne_geschichte_steht_der_vertrag_im_ursprung():
    stamm, historie, ledger, hinweise = _baue()

    assert stamm.loc[0, "status_code"] == "POL"
    assert stamm.loc[0, "status_id"] == 1
    assert len(historie) == 0
    assert len(ledger) == 1
    assert any("Vorgeschichte" in h for h in hinweise)


def test_beitragsfreistellung_setzt_den_stamm_auf_den_juengsten_stand():
    """P-B1 haelt Stamm und Journal gegeneinander — sie muessen passen."""
    stamm, historie, _ledger, _h = _baue(
        {"7000001": [("PEX", dt.date(2022, 2, 1))]})

    assert stamm.loc[0, "status_code"] == "PEX"
    assert stamm.loc[0, "status_id"] == 2
    assert stamm.loc[0, "status_date"] == dt.datetime(2022, 2, 1)
    # Die Historie traegt den Wechsel, nicht den Ursprung.
    assert list(historie["status_code"]) == ["PEX"]
    assert list(historie["status_id"]) == [2]


def test_erhoehung_und_herabsetzung_erzeugen_keinen_statuswechsel():
    """Beide aendern Summe und Beitrag, nicht den Zustand."""
    stamm, historie, _l, _h = _baue({"7000001": [
        ("ERH", dt.date(2018, 2, 1)),
        ("RED", dt.date(2020, 2, 1)),
    ]})

    assert stamm.loc[0, "status_code"] == "POL"
    assert len(historie) == 0
    assert "ERH" not in GEVO_STATUS and "RED" not in GEVO_STATUS


def test_mehrere_wechsel_werden_fortlaufend_nummeriert():
    stamm, historie, _l, _h = _baue({"7000001": [
        ("PEX", dt.date(2020, 2, 1)),
        ("STO", dt.date(2024, 2, 1)),
    ]})

    assert list(historie["status_id"]) == [2, 3]
    assert list(historie["status_code"]) == ["PEX", "STO"]
    assert stamm.loc[0, "status_code"] == "STO"


def test_geburtsdatum_wird_konstruiert_nicht_uebernommen():
    """Der Stamm verlangt Monatsersten UND die exakte Monatsidentitaet
    ``insurance_start - date_of_birth == 12 * entry_age``."""
    stamm, _h, _l, _hin = _baue()
    gebdat = stamm.loc[0, "date_of_birth"]

    assert gebdat.day == 1
    monate = ((2016 * 12 + 2) - (gebdat.year * 12 + gebdat.month))
    assert monate == 12 * 37


def test_abweichendes_geliefertes_geburtsdatum_wird_gemeldet():
    """Die Abweichung ist eine Aussage ueber die Alterskonvention der
    Quelle und gehoert in den Befund."""
    zeile = dict(ZEILE, geburtsdatum="1979-12-08")
    _s, _h, _l, hinweise = baue(
        [zeile], tarif_generation="TG2015", produkt="klv",
        stichtag=dt.date(2026, 1, 1), vorgeschichte={})

    assert any("Geburtsdaten weichen" in h for h in hinweise)


def test_die_uebernahme_archiviert_die_gevo_metadatenliste(tmp_path):
    """E1 (Entscheidung 2026-08-31): Archiv der PLV.

    Das Quellsystem wird stillgelegt und als Archiv genutzt -- die
    gelieferte GeVo-Metadatenliste gehoert deshalb dauerhaft zum
    Zielbestand, nicht nur ins Migrations-Staging. Byte-identisch: Ein
    Archiv, das beim Archivieren umschreibt, archiviert nicht.
    """
    import json

    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import bestand_uebernehmen

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")

    metadaten = tmp_path / "gevo_metadaten.csv"
    metadaten.write_text(
        "POLNR;GEVO;DATUM\n7000001;ERH;01.02.2020\n", encoding="utf-8")
    registrieren(fall, metadaten)

    zeilen = tmp_path / "zeilen.json"
    zeilen.write_text(json.dumps([dict(ZEILE)]), encoding="utf-8")
    ziel = fall / "abgeleitet" / "bestand"

    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", "TG2015", "--stichtag", "2026-01-01",
        "--vorgeschichte", "gevo_metadaten.csv",
        "--out-dir", str(ziel),
    ]) == 0

    archiv = ziel / "quellarchiv" / "gevo_metadaten.csv"
    assert archiv.read_bytes() == metadaten.read_bytes()


# --------------------------------------------------------------------------- #
# Verankerungsattribute (Grundsatzdokumentation 9.12, K3)
# --------------------------------------------------------------------------- #


def test_verankerung_wird_vertragsmerkmal_wenn_die_lieferung_sie_traegt(tmp_path):
    """t_a, Wert, Zustand und Verweildauer wandern als Nebentabelle in den
    Bestand — bisher lebten sie nur im Pruefauftrag, je Lauf aus den
    Erwartungswerten rekonstruiert (K3: dieselbe Luecke, die ADR-011
    nannte).
    """
    import json

    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import bestand_uebernehmen
    from rechner_pipeline.models.bestand import (
        STAMM_NAMES,
        VERANKERUNG_NAMES,
        validate_verankerung,
    )

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    metadaten = tmp_path / "gevo_metadaten.csv"
    # ERH ist kein Statuswechsel — beide Vertraege bleiben
    # beitragspflichtig; den beitragsfreien Fall prueft der Unit-Test
    # darunter (die Uebernahme beitragsfreier Vertraege verlangt
    # Rechnungsgrundlagen, die hier nichts zur Sache tun).
    metadaten.write_text(
        "POLNR;GEVO;DATUM\n7000002;ERH;01.02.2020\n", encoding="utf-8")
    registrieren(fall, metadaten)

    zeilen = tmp_path / "zeilen.json"
    zeilen.write_text(json.dumps([
        {**ZEILE, "monate_ta": 120, "dk_ta": 41_000.50},
        {**ZEILE, "police_id": 7000002, "monate_ta": 108, "dk_ta": 38_500.25},
    ]), encoding="utf-8")
    ziel = fall / "abgeleitet" / "bestand"

    assert bestand_uebernehmen.main([
        "--fall", str(fall), "--zeilen", str(zeilen),
        "--tarif-generation", "TG2015", "--stichtag", "2026-02-01",
        "--vorgeschichte", "gevo_metadaten.csv",
        "--out-dir", str(ziel),
    ]) == 0

    stamm = read_portfolio(ziel / "bestand.parquet",
                           expected_columns=STAMM_NAMES)
    tabelle = read_portfolio(ziel / "verankerung.parquet",
                             expected_columns=VERANKERUNG_NAMES)
    assert validate_verankerung(stamm, tabelle) == []
    je = tabelle.set_index("police_id")
    assert je.loc[7000001, "zustand_ta"] == "beitragspflichtig"
    assert je.loc[7000001, "verweildauer_ta"] == 10
    assert je.loc[7000001, "dk_ta"] == 41_000.50
    assert je.loc[7000002, "monate_ta"] == 108


def test_zustand_am_ta_kommt_aus_der_vorgeschichte():
    """Beitragsfrei seit zwei Jahren vor t_a: Zustand und Verweildauer.

    Die Ableitung nutzt dieselbe registrierte Vorgeschichte wie die
    Statushistorie — kein zweiter Kanal, keine stille Vorgabe.
    """
    import datetime as _dt

    from rechner_pipeline.gates.bestand_uebernehmen import _verankerungstabelle

    tabelle = _verankerungstabelle(
        [{**ZEILE, "monate_ta": 120, "dk_ta": 38_500.25}],
        {"7000001": [("PEX", _dt.date(2024, 2, 1))]},
    )
    zeile = tabelle.iloc[0]
    assert zeile["zustand_ta"] == "beitragsfrei"
    assert zeile["verweildauer_ta"] == 2
    # Ein PEX NACH t_a aendert den Zustand am t_a nicht.
    spaeter = _verankerungstabelle(
        [{**ZEILE, "monate_ta": 120, "dk_ta": 1.0}],
        {"7000001": [("PEX", _dt.date(2026, 6, 1))]},
    )
    assert spaeter.iloc[0]["zustand_ta"] == "beitragspflichtig"


def test_halbe_verankerungslieferung_faellt_hart(tmp_path):
    """Alle oder keine — sonst hielte die Schicht den Rest fuer frei."""
    import json

    from rechner_pipeline.fall import anlegen, registrieren
    from rechner_pipeline.gates import bestand_uebernehmen

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    metadaten = tmp_path / "gevo_metadaten.csv"
    metadaten.write_text("POLNR;GEVO;DATUM\n", encoding="utf-8")
    registrieren(fall, metadaten)
    zeilen = tmp_path / "zeilen.json"
    zeilen.write_text(json.dumps([
        {**ZEILE, "monate_ta": 120, "dk_ta": 1.0},
        {**ZEILE, "police_id": 7000002},
    ]), encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        bestand_uebernehmen.main([
            "--fall", str(fall), "--zeilen", str(zeilen),
            "--tarif-generation", "TG2015", "--stichtag", "2026-02-01",
            "--vorgeschichte", "gevo_metadaten.csv",
            "--out-dir", str(fall / "abgeleitet" / "bestand"),
        ])
    assert "ALLE" in str(exc.value)


def test_terminaler_vorfall_vor_ta_ist_ein_lieferungswiderspruch():
    """Ein beendeter Vertrag hat keinen spaeteren Rechenpunkt."""
    import datetime as _dt

    from rechner_pipeline.gates.bestand_uebernehmen import _verankerungstabelle

    with pytest.raises(SystemExit) as exc:
        _verankerungstabelle(
            [{**ZEILE, "monate_ta": 120, "dk_ta": 1.0}],
            {"7000001": [("STO", _dt.date(2020, 2, 1))]},
        )
    assert "terminaler Vorfall" in str(exc.value)


def test_validate_verankerung_findet_die_naheliegenden_fehler():
    """Unbekannte Police, doppeltes t_a, t_a nach Ablauf."""
    import pandas as pd

    from rechner_pipeline.gates.bestand_uebernehmen import _verankerungstabelle
    from rechner_pipeline.models.bestand import validate_verankerung

    stamm, _h, _l, _hw = _baue()
    gut = _verankerungstabelle(
        [{**ZEILE, "monate_ta": 60, "dk_ta": 10.0}], {})
    assert validate_verankerung(stamm, gut) == []

    fremd = gut.assign(police_id=999)
    assert any("ausserhalb des Bestands" in b
               for b in validate_verankerung(stamm, fremd))

    doppelt = pd.concat([gut, gut], ignore_index=True)
    assert any("mehrere Verankerungen" in b
               for b in validate_verankerung(stamm, doppelt))

    zu_spaet = gut.assign(monate_ta=12 * (ZEILE["duration"] + 1))
    befunde = validate_verankerung(stamm, zu_spaet)
    assert any("nach Vertragsablauf" in b for b in befunde)
