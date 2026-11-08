"""Schichtbeleg-Producer und sein Bindungs-Vertrag beim Konsumenten.

Der Producer schliesst die Werkzeug-Luecke zwischen Kern-API
(migrationszugang.uebernehmen) und aktuartest_lauf --schicht; der
Konsument akzeptiert das abgeleitete Artefakt NUR ueber nachgerechnete
Provenienz (Systemstand + Eingabe-Hashes) — die Tests hier greifen
beide Seiten an: falsche Eingaben, veraenderte Dateien, fremder
Systemstand.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.gates.aktuartest_lauf import _schichten
from rechner_pipeline.gates.verankerung_belegen import baue_schichtbeleg, main as erzeuge_schichtbeleg
from rechner_pipeline.fall import anlegen
from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.korrekturschicht import Schichtparameter
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.models.bestand import GENERATION_FIELDS
from tests.tarifregeln_testhelfer import lege_spez

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclasses.dataclass
class _Zelle:
    auspraegungen: dict
    model_point: dict


@dataclasses.dataclass
class _Spez:
    zellen: list


def _spez_einzellig() -> _Spez:
    felder = dataclasses.asdict(KLV_DEFAULT)
    return _Spez(zellen=[_Zelle({}, {
        f: felder[f] for f in GENERATION_FIELDS})])


def _bestand(*policen: int) -> pd.DataFrame:
    return pd.DataFrame([{
        "police_id": p,
        "sum_insured": KLV_DEFAULT.sum_insured,
        "entry_age": KLV_DEFAULT.x,
        "duration": KLV_DEFAULT.n,
        "premium_duration": KLV_DEFAULT.t,
        "zahlweise": KLV_DEFAULT.zw,
        "sex": KLV_DEFAULT.sex,
        "insurance_start": pd.Timestamp("2016-01-01"),
    } for p in policen])


def _verankerung(*policen: int, dk_plus: float = 500.0) -> pd.DataFrame:
    v_prosp = Rechenkern(KLV_DEFAULT).zustand_am(120).vx_mrv
    return pd.DataFrame([{
        "police_id": p,
        "monate_ta": 120,
        "zustand_ta": "beitragspflichtig",
        "verweildauer_ta": 10,
        "dk_ta": round(v_prosp + dk_plus, 2),
    } for p in policen])


def test_der_beleg_traegt_das_residuum_und_ist_konstruktorkompatibel():
    """Referenz: dk_ta wurde als Kernwert + 500 gesetzt — das Residuum
    je Police muss diese 500 zeigen, und die hist-Felder muessen einen
    Schichtparameter konstruieren (der Rundtrip, den der Konsument
    faehrt)."""
    beleg = baue_schichtbeleg(
        _verankerung(7000001, 7000002), _bestand(7000001, 7000002),
        None, _spez_einzellig(), formfunktion="proportional_zur_basis")
    assert beleg["summary"]["vertraege"] == 2
    assert beleg["summary"]["getragen"] == 2
    assert beleg["befunde"] == []
    assert beleg["summary"]["residuum_summe"] == pytest.approx(1000.0,
                                                               abs=0.05)
    for police in ("7000001", "7000002"):
        felder = beleg["schichten"][police]["hist"]
        parameter = Schichtparameter(
            **{k: (tuple(tuple(x) for x in v) if k == "vererbend" else v)
               for k, v in felder.items()})
        assert parameter.als_beleg() == felder


def test_verankerung_ohne_stammzeile_und_fremder_zustand_fallen_hart():
    with pytest.raises(SystemExit, match="nicht im Stamm"):
        baue_schichtbeleg(
            _verankerung(7000001), _bestand(7000009), None,
            _spez_einzellig(), formfunktion="proportional_zur_basis")
    kaputt = _verankerung(7000001)
    kaputt.loc[0, "zustand_ta"] = "storniert"
    with pytest.raises(SystemExit, match="nicht abgebildet"):
        baue_schichtbeleg(
            kaputt, _bestand(7000001), None, _spez_einzellig(),
            formfunktion="proportional_zur_basis")


def test_mehrzellige_spez_verlangt_merkmale():
    spez = _spez_einzellig()
    zweite = _Zelle({"status": "raucher"}, dict(spez.zellen[0].model_point))
    spez.zellen[0].auspraegungen = {"status": "nichtraucher"}
    spez.zellen.append(zweite)
    with pytest.raises(SystemExit, match="Merkmalstabelle"):
        baue_schichtbeleg(
            _verankerung(7000001), _bestand(7000001), None, spez,
            formfunktion="proportional_zur_basis")
    merkmale = pd.DataFrame([{
        "police_id": 7000001, "dimension": "status",
        "auspraegung": "nichtraucher"}])
    beleg = baue_schichtbeleg(
        _verankerung(7000001), _bestand(7000001), merkmale, spez,
        formfunktion="proportional_zur_basis")
    assert "7000001" in beleg["schichten"]


# --------------------------------------------------------------------------- #
# Der Bindungs-Vertrag des Konsumenten (aktuartest_lauf --schicht)
# --------------------------------------------------------------------------- #


def _wrapper_datei(tmp_path: Path, *, kaputt: str = "",
                   policen: tuple[int, ...] = (7000001,)) -> Path:
    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    (fall / "abgeleitet" / "schichten").mkdir(parents=True)
    eingabe = fall / "abgeleitet" / "bestand" / "verankerung.parquet"
    eingabe.parent.mkdir(parents=True)
    _verankerung(*policen).to_parquet(eingabe)
    _bestand(*policen).to_parquet(eingabe.with_name("bestand.parquet"))
    lege_spez(fall, _spez_einzellig().zellen[0].model_point)
    pfad = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    assert erzeuge_schichtbeleg([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--generation", "klv/tg2015", "--out", str(pfad),
    ]) == 0
    beleg = json.loads(pfad.read_text(encoding="utf-8"))
    if kaputt == "systemstand":
        beleg["provenienz"]["systemstand"] = {"gefaelscht": "x"}
    if kaputt == "ohne_provenienz":
        del beleg["provenienz"]
    # Die vier Lagen, in denen der Beleg sein eigenes Urteil verraet
    # (Befund T26-06). Provenienz und Eingabe-Hashes bleiben dabei
    # KORREKT — genau das war der Punkt: Der Consumer rechnete die Kette
    # nach und uebersah, dass der Producer rot war.
    if kaputt == "rot":
        beleg["befunde"] = [{"police_id": 7000001,
                             "befund": "Verankerung am Ablauf",
                             "residuum": -21931.59}]
        beleg["summary"]["befunde"] = 1
    if kaputt == "nur_summary_rot":
        beleg["summary"]["befunde"] = 1
    if kaputt == "unvollstaendig":
        beleg["summary"]["vertraege"] = 2
    if kaputt == "tabelle_passt_nicht":
        beleg["summary"]["getragen"] = 2
        beleg["summary"]["vertraege"] = 2
    pfad.write_text(json.dumps(beleg), encoding="utf-8")
    if kaputt == "eingabe":
        eingabe.write_bytes(eingabe.read_bytes() + b"x")
    return fall


def test_schichtbeleg_liest_und_schreibt_ueber_fremde_bestandsdaten(tmp_path, monkeypatch):
    """Der Producer verarbeitet gebundene Bytes und veroeffentlicht ueber den Vertrag."""
    from rechner_pipeline.plv.bestandsdaten import PLVBestandsdaten
    from rechner_pipeline.plv.zielsystem import PLV
    from rechner_pipeline.zielsystem import anbieter

    gelesen = []
    geschrieben = []

    class FremdeDaten(PLVBestandsdaten):
        def tabelle_aus_bytes(self, roh, *, erwartete_spalten=None):
            gelesen.append(roh)
            return super().tabelle_aus_bytes(roh, erwartete_spalten=erwartete_spalten)

        def schreibe_tabelle(self, tabelle, pfad, *, exklusiv=False):
            geschrieben.append((pfad.name, len(tabelle), exklusiv))
            return super().schreibe_tabelle(tabelle, pfad, exklusiv=exklusiv)

    class FremdesZiel(PLV):
        def faehigkeit(self, name):
            return FremdeDaten() if name == "bestandsdaten" else super().faehigkeit(name)

    monkeypatch.setattr(anbieter, "zielsystem", lambda: FremdesZiel())
    fall = _wrapper_datei(tmp_path)
    assert gelesen == [(fall / "abgeleitet" / "bestand" / "bestand.parquet").read_bytes()]
    assert geschrieben == [("schichten.parquet", 1, False)]
    assert (fall / "abgeleitet" / "bestand" / "schichten.parquet").is_file()


def test_schichtbeleg_schreibt_manifest_ueber_fremde_bestandsdaten(tmp_path, monkeypatch):
    """Der zweite Erzeuger uebergibt Laufart und Ausgaben an den Vertrag."""
    from rechner_pipeline.plv.bestandsdaten import PLVBestandsdaten
    from rechner_pipeline.plv.zielsystem import PLV
    from rechner_pipeline.zielsystem import anbieter

    gesehen = []

    class FremdeDaten(PLVBestandsdaten):
        def laufmanifest_schreiben(self, lauf, **angaben):
            gesehen.append((lauf, angaben))
            return super().laufmanifest_schreiben(lauf, **angaben)

    class FremdesZiel(PLV):
        def faehigkeit(self, name):
            return FremdeDaten() if name == "bestandsdaten" else super().faehigkeit(name)

    fall = tmp_path / "fall"
    anlegen(fall, scope="bestand")
    eingabe = fall / "abgeleitet" / "bestand" / "verankerung.parquet"
    eingabe.parent.mkdir(parents=True)
    _verankerung(7000001).to_parquet(eingabe)
    _bestand(7000001).to_parquet(eingabe.with_name("bestand.parquet"))
    lege_spez(fall, _spez_einzellig().zellen[0].model_point)
    config = tmp_path / "config.toml"
    config.write_bytes(b"[meta]\n")
    monkeypatch.setattr(anbieter, "zielsystem", lambda: FremdesZiel())
    assert erzeuge_schichtbeleg([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT),
        "--generation", "klv/tg2015", "--config", str(config),
        "--stichtag", "2026-01-01",
    ]) == 0
    assert len(gesehen) == 1
    assert gesehen[0][0] == eingabe.parent
    assert gesehen[0][1]["laufart"] == "migrationszugang"
    assert {pfad.name for pfad in gesehen[0][1]["ausgaben"]} == {
        "bestand.parquet", "verankerung.parquet", "schichten.parquet",
    }
    assert (eingabe.parent / "laufmanifest.json").is_file()


def test_abgeleiteter_beleg_wird_nur_mit_nachgerechneter_bindung_akzeptiert(
        tmp_path):
    fall = _wrapper_datei(tmp_path)
    schichten = _schichten(
        fall, "abgeleitet/schichten/verankerung_schichten.json",
        repo_root=REPO_ROOT)
    assert isinstance(schichten["7000001"]["hist"], Schichtparameter)


def test_echter_beleg_mit_zwei_policen_bleibt_bindbar(tmp_path):
    fall = _wrapper_datei(tmp_path, policen=(7000001, 7000002))
    schichten = _schichten(
        fall, "abgeleitet/schichten/verankerung_schichten.json",
        repo_root=REPO_ROOT)
    assert set(schichten) == {"7000001", "7000002"}


@pytest.mark.parametrize("mutation", [
    "alle_eingaben_fehlen",
    "verankerung_fehlt",
    "residuum_summe_verfaelscht",
    "schichtparameter_verfaelscht",
])
def test_schichtbeleg_prueft_pflichtbindungen_und_werte(tmp_path, mutation):
    """T28-02: Der Beleg darf weder seine Pflichtquellen auswaehlen noch
    einen anderen Zahlenwert bei gleich bleibenden Eingaben behaupten.
    Die Positivkontrolle mit zwei Policen steht unmittelbar darueber."""
    fall = _wrapper_datei(tmp_path, policen=(7000001, 7000002))
    pfad = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    beleg = json.loads(pfad.read_text(encoding="utf-8"))
    if mutation == "alle_eingaben_fehlen":
        beleg["provenienz"]["eingaben"] = {}
    elif mutation == "verankerung_fehlt":
        del beleg["provenienz"]["eingaben"][
            "abgeleitet/bestand/verankerung.parquet"]
    elif mutation == "residuum_summe_verfaelscht":
        beleg["summary"]["residuum_summe"] += 100
    else:
        beleg["schichten"]["7000001"]["hist"]["rho"] += 0.01
    pfad.write_text(json.dumps(beleg), encoding="utf-8")
    with pytest.raises(SystemExit, match="nachgerechneten Beleg"):
        _schichten(fall, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)


@pytest.mark.parametrize("feld", ["befunde", "rumpfmonate"])
def test_nachrechnung_unterscheidet_bool_und_zahl(tmp_path, feld):
    """Ein echter Schichtbeleg darf durch 0 -> false weder im Urteil noch
    im Schichtparameter einen anderen JSON-Typ erhalten. Python-Gleichheit
    allein faengt diese Aenderung nicht."""
    fall = _wrapper_datei(tmp_path)
    pfad = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    beleg = json.loads(pfad.read_text(encoding="utf-8"))
    if feld == "befunde":
        assert beleg["summary"]["befunde"] == 0
        beleg["summary"]["befunde"] = False
    else:
        hist = beleg["schichten"]["7000001"]["hist"]
        assert hist["rumpfmonate"] == 0
        hist["rumpfmonate"] = False
    pfad.write_text(json.dumps(beleg), encoding="utf-8")
    with pytest.raises(SystemExit, match="nachgerechneten Beleg"):
        _schichten(fall, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)


def test_manipulation_der_eingabe_faellt_hart(tmp_path):
    fall = _wrapper_datei(tmp_path, kaputt="eingabe")
    with pytest.raises(SystemExit, match="veraendert"):
        _schichten(fall, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)


#: Die Lagen, in denen ein Beleg sein eigenes Urteil verraet, samt dem
#: Stichwort, an dem der Consumer sie benennen muss. Als Tabelle, nicht als
#: Einzelfall: Wer nur den roten Producerlauf prueft, akzeptiert einen
#: Beleg mit geleerter Befundliste und unveraendertem summary.
URTEILSLAGEN = [
    ("rot", "ROT"),
    ("nur_summary_rot", "ROT"),
    ("unvollstaendig", "unvollstaendig"),
    ("tabelle_passt_nicht", "passt nicht"),
]


@pytest.mark.parametrize("kaputt,stichwort", URTEILSLAGEN)
def test_ein_beleg_mit_eigenem_befund_wird_nicht_fachlich_verwendet(
        tmp_path, kaputt, stichwort):
    """Befund T26-06: Ein echter ROTER Producerlauf (25 von 26 Policen
    getragen) fuehrte zu drei gruenen aktuariellen Vorlagenlaeufen.

    Der Consumer rechnete Systemstand und Eingabe-Hashes nach — und
    reduzierte danach direkt auf ``schichten``. ``befunde`` und
    ``summary`` sah er nie. Die Kette war belegt, das Urteil nicht.

    Die Positivkontrolle steht als eigener Test daneben: Derselbe Beleg
    unveraendert wird angenommen. Ohne sie koennte der Consumer alles
    ablehnen und saehe genauso gruen aus.
    """
    fall = _wrapper_datei(tmp_path, kaputt=kaputt)
    with pytest.raises(SystemExit, match=stichwort):
        _schichten(fall, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)


def test_fremder_systemstand_und_fehlende_provenienz_fallen_hart(tmp_path):
    fall = _wrapper_datei(tmp_path, kaputt="systemstand")
    with pytest.raises(SystemExit, match="Systemstand"):
        _schichten(fall, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)
    fall2 = _wrapper_datei(tmp_path / "b", kaputt="ohne_provenienz")
    with pytest.raises(SystemExit, match="Provenienzblock"):
        _schichten(fall2, "abgeleitet/schichten/verankerung_schichten.json",
                   repo_root=REPO_ROOT)


def test_zustands_vertraege_verankern_auf_ihrer_welt():
    """Ausweitung Nr. 18 des zweiten Laufs: Ohne Anfangszustaende
    verankerte der Producer die Stamm-Welt — bei Serien-Policen wurde
    die Weltendifferenz (Einzelbaustein vs. Scheiben) zum
    Phantom-Residuum (im Fall: rho bis 0,04). Mit Anfangszustand
    rechnet dk_prosp auf der Scheiben-Welt (drx-Basis): Ein dk_ta
    GENAU auf dieser Welt ergibt Residuum ~0."""
    from rechner_pipeline.kern.rechenkern import (
        erhoehungs_scheibe,
        vertrags_monatsreserve,
    )

    # Junge Scheibe (2 Jahre alt am t_a): ihr Zillmer-Rest trennt
    # gefuehrten Wert und Deckungsrueckstellung.
    grund, erh_jahr, summe = 90000.0, 8, 4500.0
    grund_mp = dataclasses.replace(KLV_DEFAULT, sum_insured=grund)
    kerne = [(erh_jahr, Rechenkern(erhoehungs_scheibe(
        grund_mp, erh_jahr, summe, gamma1_uebernehmen=False)))]
    welt = vertrags_monatsreserve(Rechenkern(grund_mp), kerne, 120)
    # Zonen-Beleg: die Scheiben-Welt trennt gefuehrten Wert und
    # Deckungsrueckstellung — genau die Differenz, die auf der
    # falschen Basis zum Phantom-rho wurde (Korrektur Nr. 20).
    assert welt.vx_mrv - welt.drx_bpfl > 10.0
    dk_welt = welt.vx_mrv
    verankerung = pd.DataFrame([{
        "police_id": 7000001, "monate_ta": 120,
        "zustand_ta": "beitragspflichtig", "verweildauer_ta": 10,
        "dk_ta": round(dk_welt, 2),
    }])
    zustand = {"7000001": {
        "sum_insured": grund, "scheiben": ((erh_jahr, summe),)}}
    beleg = baue_schichtbeleg(
        verankerung, _bestand(7000001), None, _spez_einzellig(),
        formfunktion="proportional_zur_basis",
        anfangszustaende=zustand)
    rho = beleg["schichten"]["7000001"]["hist"]["rho"]
    assert abs(beleg["summary"]["residuum_max_abs"]) <= 0.01
    assert abs(rho) < 1e-5

    # Gegenprobe: OHNE Zustand entsteht genau das Phantom-Residuum
    # (Stamm-Welt-drx minus Scheiben-Welt-drx).
    phantom = baue_schichtbeleg(
        verankerung, _bestand(7000001), None, _spez_einzellig(),
        formfunktion="proportional_zur_basis")
    stamm_drx = Rechenkern(KLV_DEFAULT).verlaufszeile(10).drx_bpfl
    assert phantom["summary"]["residuum_max_abs"] == pytest.approx(
        abs(round(dk_welt, 2) - stamm_drx), abs=0.02)
