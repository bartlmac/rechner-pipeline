"""Laeufer-Kommandos: Zellwahl je Police und Anfangszustand der Vorgeschichte.

Die zweite Lieferung traegt eine mehrzellige Spez (tarifart x status)
und Vertraege, die beitragsfrei UEBERNOMMEN werden. Beides konnte der
Suite-/Aktuartest-Laeufer vorher nicht: Er waehlte die Zelle nur bei
einzelliger Spez richtig und kannte keinen Anfangszustand. Diese Tests
halten die neuen Wege fest — inklusive der harten Ausgaenge, die ein
stilles Zurueckfallen auf eine falsche Zelle verhindern.

Knoten: klv
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Dict, List

import pandas as pd
import pytest

from rechner_pipeline.gates.migrationssuite_lauf import (
    auspraegungen_je_police,
    baue_auftraege,
    beitragsfrei_seit_jahr_je_police,
    VORGABE,
)


@dataclass
class _Zelle:
    # model_point traegt SCHLICHTE Werte — wie die geladene Spez
    # (spez/schema.py: Wert ist ein Typ-Alias, kein Traeger-Objekt).
    auspraegungen: Dict[str, str] = field(default_factory=dict)
    model_point: Dict[str, object] = field(default_factory=dict)


@dataclass
class _Spez:
    zellen: List[_Zelle] = field(default_factory=list)


def _generationsfelder(zins: float) -> Dict[str, object]:
    return {
        "zins": zins, "tafel": "DAV2008_T_NR_U70",
        "alpha": 0.025, "beta1": 0.03,
        "gamma1": 0.001, "gamma2": 0.00125,
        "gamma3": 0.0025, "policy_fee": 12.0,
        "min_alter_flex": 60, "min_rlz_flex": 5,
        "stoab_satz": 0.005, "stoab_min": 50.0,
        "stoab_max": 200.0, "zillmer_dauer": 5,
        "ratzu_zw2": 0.02, "ratzu_zw4": 0.03,
        "ratzu_zw12": 0.05,
    }


MEHRZELLIG = _Spez(zellen=[
    _Zelle({"status": "nichtraucher", "tarifart": "einzel"},
           _generationsfelder(0.0175)),
    _Zelle({"status": "raucher", "tarifart": "einzel"},
           _generationsfelder(0.0125)),
])

EINZELLIG = _Spez(zellen=[_Zelle({}, _generationsfelder(0.0175))])

SPALTEN = dict(VORGABE)


def _bestand(*policen: int) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "police_id": p, "sex": "F", "entry_age": 45, "duration": 30,
            "premium_duration": 20, "sum_insured": 100000.0, "zahlweise": 12,
            "insurance_start": pd.Timestamp("2016-01-01"),
        }
        for p in policen
    ])


def _abzug(*policen: int) -> List[Dict[str, str]]:
    return [
        {"POLNR": str(p), "DECKKAP": "1234.56", "JBRUTTO": "4150.51"}
        for p in policen
    ]


def test_auspraegungen_je_police_liest_die_dimensionsfelder():
    zeilen = [
        {"police_id": "7000001", "status": "raucher", "tarifart": "einzel"},
        {"police_id": "7000002", "status": "nichtraucher",
         "tarifart": "einzel"},
    ]
    aus = auspraegungen_je_police(MEHRZELLIG, zeilen)
    assert aus["7000001"] == {"status": "raucher", "tarifart": "einzel"}
    assert aus["7000002"]["status"] == "nichtraucher"


def test_fehlende_dimension_in_der_zeile_faellt_hart():
    with pytest.raises(SystemExit, match="7000001.*status"):
        auspraegungen_je_police(
            MEHRZELLIG, [{"police_id": "7000001", "tarifart": "einzel"}])


def test_zeile_ohne_police_id_faellt_hart():
    with pytest.raises(SystemExit, match="police_id"):
        auspraegungen_je_police(MEHRZELLIG, [{"status": "raucher"}])


def test_mehrzellige_spez_ohne_zeilen_faellt_hart():
    with pytest.raises(SystemExit, match="Zellwahl"):
        baue_auftraege(
            _bestand(7000001), MEHRZELLIG, _abzug(7000001), [], [],
            stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
            spalten=SPALTEN,
        )


def test_zellwahl_je_police_parametriert_je_zelle():
    auftraege = baue_auftraege(
        _bestand(7000001, 7000002), MEHRZELLIG,
        _abzug(7000001, 7000002), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        auspraegungen={
            "7000001": {"status": "raucher", "tarifart": "einzel"},
            "7000002": {"status": "nichtraucher", "tarifart": "einzel"},
        },
    )
    je_police = {a.police_id: a for a in auftraege}
    assert je_police["7000001"].model_point["zins"] == 0.0125
    assert je_police["7000002"].model_point["zins"] == 0.0175


def test_anfangszustand_fliesst_in_den_pruefauftrag():
    auftraege = baue_auftraege(
        _bestand(7000001), EINZELLIG, _abzug(7000001), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        beitragsfrei_seit={"7000001": 7},
    )
    assert auftraege[0].beitragsfrei_seit_jahr == 7


def test_pex_der_vorgeschichte_wird_zum_vertragsjahr():
    vorgeschichte = [
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2023"},
        {"POLNR": "7000001", "GEVO": "ERH", "DATUM": "01.01.2020"},
        {"POLNR": "9999999", "GEVO": "PEX", "DATUM": "01.01.2023"},
    ]
    seit = beitragsfrei_seit_jahr_je_police(
        vorgeschichte, _bestand(7000001), spalten=SPALTEN)
    # Beginn 2016-01-01, PEX 2023-01-01 -> Vertragsjahr 7; fremde Police
    # ohne Bestandszeile bleibt draussen, ERH setzt keinen Zustand.
    assert seit == {"7000001": 7}


def test_pex_abseits_des_jahrestags_faellt_hart():
    vorgeschichte = [{"POLNR": "7000001", "GEVO": "PEX",
                      "DATUM": "01.07.2023"}]
    with pytest.raises(SystemExit, match="Jahrestag"):
        beitragsfrei_seit_jahr_je_police(
            vorgeschichte, _bestand(7000001), spalten=SPALTEN)


def test_zweites_pex_derselben_police_faellt_hart():
    vorgeschichte = [
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2022"},
        {"POLNR": "7000001", "GEVO": "PEX", "DATUM": "01.01.2023"},
    ]
    with pytest.raises(SystemExit, match="zwei PEX"):
        beitragsfrei_seit_jahr_je_police(
            vorgeschichte, _bestand(7000001), spalten=SPALTEN)


# --------------------------------------------------------------------------- #
# Anfangszustaende ERH/RED je Police (Ableitung im Laeufer)
# --------------------------------------------------------------------------- #

from rechner_pipeline.gates.migrationssuite_lauf import (
    anfangszustaende_je_police,
)
from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.beitragsreduktion import reduziere
from rechner_pipeline.kern.rechenkern import Rechenkern, erhoehungs_scheibe


def _tg_default_spez():
    """Einzellige Spez mit den Feldern des Referenz-Modellpunkts."""
    import dataclasses as dc
    from rechner_pipeline.models.bestand import GENERATION_FIELDS

    felder = dc.asdict(KLV_DEFAULT)
    return _Spez(zellen=[_Zelle({}, {
        f: felder[f] for f in GENERATION_FIELDS
    })])


def _bestand_mit(*policen: int, beginn="2016-01-01") -> pd.DataFrame:
    rahmen = _bestand(*policen)
    rahmen["insurance_start"] = pd.Timestamp(beginn)
    # Die Referenz-Vorwaertsrechnung laeuft auf KLV_DEFAULT (sex M,
    # geschlechtsabhaengige Tafel) — die Ableitung muss denselben
    # Modellpunkt sehen, sonst vergleicht der Test zwei Vertraege.
    rahmen["sex"] = KLV_DEFAULT.sex
    rahmen["entry_age"] = KLV_DEFAULT.x
    rahmen["duration"] = KLV_DEFAULT.n
    rahmen["premium_duration"] = KLV_DEFAULT.t
    rahmen["zahlweise"] = KLV_DEFAULT.zw
    return rahmen


def test_anfangszustand_erh_leitet_scheibe_und_grundsumme_ab():
    s_grund, s_scheibe, jahr = 80000.0, 12000.0, 6
    grund = Rechenkern(type(KLV_DEFAULT)(**{
        **KLV_DEFAULT.__dict__, "sum_insured": s_grund}))
    scheibe = Rechenkern(erhoehungs_scheibe(grund.mp, jahr, s_scheibe))
    zeilen = [{"police_id": "7000001",
               "sum_insured": round(s_grund + s_scheibe, 2),
               "brutto_jahresbeitrag": round(
                   grund.gross_annual_premium()
                   + scheibe.gross_annual_premium(), 2)}]
    vorgeschichte = [{"POLNR": "7000001", "GEVO": "ERH",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000001), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert not warnungen
    (jahr_s, summe), = zustaende["7000001"]["scheiben"]
    assert jahr_s == 6
    assert summe == pytest.approx(s_scheibe, rel=5e-5)
    assert zustaende["7000001"]["sum_insured"] == pytest.approx(
        s_grund, rel=5e-5)


def test_doppelte_vorgeschichts_zeile_faellt_hart():
    """Review-Befund B7: eine doppelt gelieferte Ereigniszeile zaehlte
    still als zusaetzliche Quell-Komponente und gaebe der
    Rundungstoleranz eine unverdiente Stufe — eine Datenanomalie darf
    keine Toleranz kaufen."""
    zeilen = [{"police_id": "7000003", "sum_insured": 90000.0,
               "brutto_jahresbeitrag": 1000.0}]
    vorgeschichte = [
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2022"},
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2022"},
    ]
    with pytest.raises(SystemExit, match="doppelt geliefert"):
        anfangszustaende_je_police(
            _tg_default_spez(), zeilen, vorgeschichte,
            _bestand_mit(7000003), spalten=SPALTEN,
            red_verfahren="mit_abzug")


def test_anfangszustand_red_leitet_anteil_und_ursprungssumme_ab():
    r = reduziere(Rechenkern(KLV_DEFAULT), 6, 0.6, verfahren="mit_abzug")
    zeilen = [{"police_id": "7000002", "sum_insured": round(r.vs_neu, 2),
               "brutto_jahresbeitrag": round(r.bjb_neu, 2)}]
    vorgeschichte = [{"POLNR": "7000002", "GEVO": "RED",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000002), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert not warnungen
    jahr, anteil = zustaende["7000002"]["reduktion"]
    assert jahr == 6
    assert anteil == pytest.approx(0.6, rel=5e-5)
    assert zustaende["7000002"]["sum_insured"] == pytest.approx(
        KLV_DEFAULT.sum_insured, rel=5e-5)


def test_nachgelieferter_anteil_ersetzt_die_beitragsgleichung():
    r = reduziere(Rechenkern(KLV_DEFAULT), 6, 0.75, verfahren="mit_abzug")
    zeilen = [{"police_id": "7000365", "sum_insured": round(r.vs_neu, 2),
               "brutto_jahresbeitrag": 0.0}]
    vorgeschichte = [{"POLNR": "7000365", "GEVO": "RED",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000365), spalten=SPALTEN,
        red_verfahren="mit_abzug", red_anteile={"7000365": 0.75})
    assert not warnungen
    jahr, anteil = zustaende["7000365"]["reduktion"]
    assert (jahr, anteil) == (6, 0.75)
    assert zustaende["7000365"]["sum_insured"] == pytest.approx(
        KLV_DEFAULT.sum_insured, rel=5e-5)


def test_unbestimmbare_erhoehung_wird_warnung_statt_zustand():
    zeilen = [{"police_id": "7000050", "sum_insured": 92000.0,
               "brutto_jahresbeitrag": 0.0}]
    vorgeschichte = [{"POLNR": "7000050", "GEVO": "ERH",
                      "DATUM": "01.01.2022"}]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000050), spalten=SPALTEN,
        red_verfahren="mit_abzug")
    assert zustaende == {}
    assert len(warnungen) == 1 and "7000050" in warnungen[0]


def test_auftragsbau_uebernimmt_zustand_und_ursprungssumme():
    auftraege = baue_auftraege(
        _bestand_mit(7000002), EINZELLIG, _abzug(7000002), [], [],
        stichtag_1=dt.date(2026, 1, 1), stichtag_2=dt.date(2027, 1, 1),
        spalten=SPALTEN,
        anfangszustaende={"7000002": {
            "reduktion": (6, 0.6), "sum_insured": 100000.0}},
    )
    a, = auftraege
    assert a.reduktion == (6, 0.6)
    assert a.model_point["sum_insured"] == 100000.0


# --------------------------------------------------------------------------- #
# Die Korrekturschicht erreicht den Pruefauftrag
# --------------------------------------------------------------------------- #

def _schicht_datei(fall, inhalt, name: str = "schicht.json") -> str:
    """Eine REGISTRIERTE Schichtdatei im Fall anlegen."""
    import json as _json

    from rechner_pipeline.fall import registrieren

    quelle = fall.parent / name
    quelle.write_text(_json.dumps(inhalt), encoding="utf-8")
    registrieren(fall, quelle)
    return quelle.name


def test_die_korrekturschicht_erreicht_den_pruefauftrag(tmp_path):
    """Die Schicht war im Kern vorhanden, in der Testengine verdrahtet und
    durch Tests gedeckt — aber KEIN Kommando konnte sie setzen.

    Sie ist ein Vertragsattribut, das die Uebernahmestrecke ableitet
    (Grundsatzdokumentation 9.14: der Rechenkern bleibt historienfrei),
    muss also von aussen in den Auftrag kommen. Und aus einer
    REGISTRIERTEN Quelle: Ein Residuum, das der Pruefer selbst setzen
    koennte, waere kein Beweis, sondern ein Regler.
    """
    from rechner_pipeline.fall import anlegen
    from rechner_pipeline.gates.aktuartest_lauf import _schichten

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    name = _schicht_datei(fall, {
        "7000001": {
            "schichttyp": "hist",
            "verankerungszustand": "beitragspflichtig",
            "verweildauer": 12,
            "rho": 850.0,
            "formfunktion": "konstantes_fenster",
            "formparameter": {"fenster": 12},
        }
    })

    schichten = _schichten(fall, name)
    assert set(schichten) == {"7000001"}
    assert schichten["7000001"].rho == 850.0
    assert schichten["7000001"].verweildauer == 12

    # Ohne Angabe bleibt es beim schichtfreien Lauf — kein stiller Default.
    assert _schichten(fall, None) == {}


def test_eine_unbrauchbare_schicht_faellt_hart(tmp_path):
    """Eine halb gelesene Schicht waere schlimmer als keine: Sie traegt ein
    Residuum, das niemand geprueft hat."""
    from rechner_pipeline.fall import anlegen
    from rechner_pipeline.gates.aktuartest_lauf import _schichten

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    name = _schicht_datei(fall, {"7000001": {"schichttyp": "unbekannt",
                                             "verankerungszustand": "x",
                                             "verweildauer": 1, "rho": 1.0,
                                             "formfunktion": "f"}})

    with pytest.raises(SystemExit, match="unbrauchbar"):
        _schichten(fall, name)


def test_die_beiden_residuen_kommen_getrennt_in_den_auftrag(tmp_path):
    """9.13, Entscheidung E2 2026-08-31: R_conv wird separat erfasst.

    Je Police darf die registrierte Schichtdatei jetzt BEIDE Residuen
    tragen — hist verankert bei t_a, conv mit eigenem t_0 am
    Migrationsstichtag. Die beiden werden nie vermischt: getrennte
    Parameter, getrennte Verankerung, in der Engine getrennte Felder.
    """
    from rechner_pipeline.fall import anlegen
    from rechner_pipeline.gates.aktuartest_lauf import (
        _schicht_felder,
        _schichten,
    )

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    hist = {
        "schichttyp": "hist", "verankerungszustand": "beitragspflichtig",
        "verweildauer": 12, "rho": 850.0,
        "formfunktion": "konstantes_fenster", "formparameter": {"fenster": 12},
    }
    conv = {
        "schichttyp": "conv", "verankerungszustand": "beitragspflichtig",
        "verweildauer": 0, "rho": 12.5,
        "formfunktion": "konstantes_fenster", "formparameter": {"fenster": 6},
        "monate_t0": 132,
    }
    name = _schicht_datei(fall, {"7000001": {"hist": hist, "conv": conv}})

    schichten = _schichten(fall, name)
    felder = _schicht_felder(schichten["7000001"])
    assert felder["schicht"].rho == 850.0
    assert felder["schicht"].schichttyp == "hist"
    assert felder["schicht_conv"].rho == 12.5
    assert felder["schicht_conv"].schichttyp == "conv"
    assert felder["monate_t0"] == 132

    # Das flache Format bleibt gueltig -- es traegt nur R_hist.
    flach = _schichten(fall, _schicht_datei(fall, {"7000002": hist}, "schicht-flach.json"))
    assert _schicht_felder(flach["7000002"]) == {"schicht": flach["7000002"]}


def test_conv_ohne_t0_und_fremde_teile_fallen_hart(tmp_path):
    """Eine Zweitverankerung ohne Verankerungszeitpunkt verankert nichts."""
    from rechner_pipeline.fall import anlegen
    from rechner_pipeline.gates.aktuartest_lauf import _schichten

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    conv_ohne_t0 = {
        "schichttyp": "conv", "verankerungszustand": "beitragspflichtig",
        "verweildauer": 0, "rho": 1.0,
        "formfunktion": "konstantes_fenster", "formparameter": {"fenster": 6},
    }
    with pytest.raises(SystemExit) as exc:
        _schichten(fall, _schicht_datei(fall, {"1": {"conv": conv_ohne_t0}}))
    assert "monate_t0" in str(exc.value)

    with pytest.raises(SystemExit) as exc:
        _schichten(fall, _schicht_datei(
            fall, {"1": {"hist": conv_ohne_t0, "extra": {}}}, "schicht-extra.json"))
    assert "unbekannte Teile" in str(exc.value)


def test_anfangszustand_serie_baut_ist_struktur_mit_absetzung():
    """Lieferung-2-Regelfall: Ereignis-Serie. Referenz ist die Handkette
    10000 -> ERH(1) +500 -> RED(2, f=0.6) Grund 6000 -> ERH(3) +325;
    der Anteil kommt JE EREIGNIS ueber die Datums-Nachlieferung."""
    zeilen = [{"police_id": "7000003", "sum_insured": 6825.00,
               "brutto_jahresbeitrag": 100.0}]
    vorgeschichte = [
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2017"},
        {"POLNR": "7000003", "GEVO": "RED", "DATUM": "01.01.2018"},
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2019"},
    ]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000003), spalten=SPALTEN,
        red_verfahren="mit_abzug", erhoehungssatz=0.05,
        red_anteile_je_datum={"7000003": {"01.01.2018": 0.6}})
    assert not warnungen
    z = zustaende["7000003"]
    assert z["sum_insured"] == pytest.approx(6000.00, abs=0.01)
    assert [j for j, _ in z["scheiben"]] == [1, 3]
    assert [s for _, s in z["scheiben"]] == pytest.approx(
        [500.00, 325.00], abs=0.01)
    assert z["alt_absetzungen"] == ((2, 0.6),)
    assert "reduktion" not in z, (
        "die Serie ist IST-Struktur, kein Reduktions-Zustand")


def test_anfangszustand_serie_bestimmt_offene_anteile_aus_kandidaten():
    """Auskunft 4 des zweiten Laufs: Anteile je Ereignis endgueltig
    nicht lieferbar. Mit belegter Kandidatenmenge bestimmt die
    Beitragsgleichung den offenen Anteil (Handkette wie oben, wahres
    f=0.6) — gleicher IST-Zustand wie bei der Datums-Nachlieferung,
    weiterhin ohne reduktion."""
    import dataclasses as _dc

    from rechner_pipeline.kern import erhoehungs_scheibe

    grund_mp = _dc.replace(KLV_DEFAULT, sum_insured=6000.0)
    jbrutto = round(
        Rechenkern(grund_mp).gross_annual_premium()
        + Rechenkern(erhoehungs_scheibe(
            grund_mp, 1, 500.0)).gross_annual_premium()
        + Rechenkern(erhoehungs_scheibe(
            grund_mp, 3, 325.0)).gross_annual_premium(), 2)
    zeilen = [{"police_id": "7000003", "sum_insured": 6825.00,
               "brutto_jahresbeitrag": jbrutto}]
    vorgeschichte = [
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2017"},
        {"POLNR": "7000003", "GEVO": "RED", "DATUM": "01.01.2018"},
        {"POLNR": "7000003", "GEVO": "ERH", "DATUM": "01.01.2019"},
    ]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000003), spalten=SPALTEN,
        red_verfahren="mit_abzug", erhoehungssatz=0.05,
        red_anteil_kandidaten=(0.50, 0.60, 0.75))
    assert not warnungen
    z = zustaende["7000003"]
    assert z["sum_insured"] == pytest.approx(6000.00, abs=0.01)
    assert [s for _, s in z["scheiben"]] == pytest.approx(
        [500.00, 325.00], abs=0.01)
    assert z["alt_absetzungen"] == ((2, 0.6),)
    assert "reduktion" not in z


def test_anfangszustand_serie_mit_terminalem_pex_ist_einpunkt():
    """Erhoehung + terminale Beitragsfreistellung: Ein-Punkt-Inversion.

    Nicht-zirkulaere Referenz (Review-Befund B1): Die gelieferte
    beitragsfreie Summe kommt aus der WAHREN Scheiben-Welt — Grund
    10000 mit eigenem Umwandlungsfaktor, Scheibe 500 (ERH Jahr 3) mit
    IHREM (deutlich anderen) Faktor. Der Zonen-Beleg zeigt beides:
    die Faktoren der Bausteine sind NICHT gleich (die alte
    Docstring-Praemisse war falsch), und die Ein-Punkt-Welt ist an
    den erreichbaren Folgegroessen trotzdem exakt wert-aequivalent,
    weil nach terminalem PEX alles homogen in der beitragsfreien
    GESAMTSUMME ist. Die abgeleitete sum_insured ist darum eine
    AEQUIVALENZGROESSE, nicht die historische Bausteinsumme 10500."""
    import dataclasses as _dc

    from rechner_pipeline.kern import erhoehungs_scheibe

    grund = Rechenkern(_dc.replace(KLV_DEFAULT, sum_insured=10000.0))
    scheibe = Rechenkern(erhoehungs_scheibe(grund.mp, 3, 500.0))
    f_g = Rechenkern(_dc.replace(grund.mp, sum_insured=1.0)
                     ).beitragsfreie_summe(8)
    f_s = Rechenkern(_dc.replace(scheibe.mp, sum_insured=1.0)
                     ).beitragsfreie_summe(5)
    assert abs(f_s - f_g) > 0.05, "Zonen-Beleg: Faktoren verschieden"
    vs_bfr_geliefert = round(
        grund.beitragsfreie_summe(8) + scheibe.beitragsfreie_summe(5), 2)

    zeilen = [{"police_id": "7000004", "sum_insured": vs_bfr_geliefert,
               "brutto_jahresbeitrag": 0.0}]
    vorgeschichte = [
        {"POLNR": "7000004", "GEVO": "ERH", "DATUM": "01.01.2019"},
        {"POLNR": "7000004", "GEVO": "PEX", "DATUM": "01.01.2024"},
    ]
    zustaende, warnungen = anfangszustaende_je_police(
        _tg_default_spez(), zeilen, vorgeschichte,
        _bestand_mit(7000004), spalten=SPALTEN,
        red_verfahren="mit_abzug", erhoehungssatz=0.05)
    assert not warnungen
    z = zustaende["7000004"]
    assert z["beitragsfrei_seit_jahr"] == 8
    assert "scheiben" not in z
    # Die Aequivalenzgroesse: Inversion der GESAMTSUMME durch den
    # Grund-Faktor — nicht die historische Summe der Bausteine.
    assert z["sum_insured"] == pytest.approx(
        vs_bfr_geliefert / f_g, rel=1e-9)
    # Wert-Aequivalenz an mehreren Punkten: Ein-Punkt-Welt und wahre
    # Scheiben-Welt tragen dieselbe beitragsfreie Reserve. Der einzige
    # Unterschied ist die Cent-Rundung des GELIEFERTEN Werts (die
    # Ein-Punkt-Welt reproduziert den gerundeten, die wahre Welt den
    # ungerundeten Stand) — darum halber Cent, nicht 1e-6.
    einpunkt = Rechenkern(_dc.replace(
        KLV_DEFAULT, sum_insured=z["sum_insured"]))
    for m in (12 * 9, 12 * 10 + 5, 12 * 25):
        wahr = (grund.monatsreserve_beitragsfrei(8, m)
                + scheibe.monatsreserve_beitragsfrei(5, m - 36))
        assert einpunkt.monatsreserve_beitragsfrei(8, m) == pytest.approx(
            wahr, abs=0.005)
    # Die QUELLSEITIGE Komponentenzahl (Grund + eine Erhoehung) bleibt
    # fuer die Rundungs-Skalierung des Wertvergleichs ausgewiesen.
    assert z["quell_komponenten"] == 2


def test_anfangszustand_serie_ohne_satz_und_pex_nicht_terminal_fallen_hart():
    zeilen = [{"police_id": "7000005", "sum_insured": 6825.00,
               "brutto_jahresbeitrag": 100.0}]
    serie = [
        {"POLNR": "7000005", "GEVO": "ERH", "DATUM": "01.01.2017"},
        {"POLNR": "7000005", "GEVO": "ERH", "DATUM": "01.01.2019"},
    ]
    with pytest.raises(SystemExit, match="erhoehungssatz"):
        anfangszustaende_je_police(
            _tg_default_spez(), zeilen, serie,
            _bestand_mit(7000005), spalten=SPALTEN,
            red_verfahren="mit_abzug")
    nicht_terminal = [
        {"POLNR": "7000005", "GEVO": "PEX", "DATUM": "01.01.2017"},
        {"POLNR": "7000005", "GEVO": "ERH", "DATUM": "01.01.2019"},
    ]
    with pytest.raises(SystemExit, match="terminal"):
        anfangszustaende_je_police(
            _tg_default_spez(), zeilen, nicht_terminal,
            _bestand_mit(7000005), spalten=SPALTEN,
            red_verfahren="mit_abzug", erhoehungssatz=0.05)


def test_schicht_wird_bei_ersetztem_red_vergleich_ausgewiesen_ausgelassen():
    """RED-Anfangszustand + Korrekturschicht ist in der Engine bewusst
    undefiniert. Mit ersetztem Wertvergleich (Plausibilitaets-Beleg,
    Aktuars-Entscheid) wird die Schicht AUSGEWIESEN ausgelassen; ohne
    Ersetzung bleibt der Eintrag stehen — der Engine-Waechter soll die
    Kombination hart benennen, nichts faellt still weg."""
    from rechner_pipeline.gates.aktuartest_lauf import _schicht_fuer

    schicht = {"hist": {"platzhalter": True}}
    ausgelassen: list = []
    # Mit Ersetzung: Schicht raus, Police vermerkt.
    aus = _schicht_fuer(
        "7000292", {"reduktion": (3, 0.6)}, schicht,
        {"anlass": "RED", "beleg": "notiz"}, ausgelassen)
    assert aus is None and ausgelassen == ["7000292"]
    # Ohne Ersetzung: Eintrag bleibt (Waechter-Fall der Engine).
    aus = _schicht_fuer(
        "7000293", {"reduktion": (3, 0.6)}, schicht, None, ausgelassen)
    assert aus is schicht and ausgelassen == ["7000292"]
    # Ohne Reduktion: Schicht bleibt selbstverstaendlich im Pfad.
    aus = _schicht_fuer("7000294", {}, schicht,
                        {"anlass": "RED"}, ausgelassen)
    assert aus is schicht and ausgelassen == ["7000292"]
