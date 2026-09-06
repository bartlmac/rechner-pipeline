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
from rechner_pipeline.gates.verankerung_belegen import baue_schichtbeleg
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.korrekturschicht import Schichtparameter
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.models.bestand import GENERATION_FIELDS

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


def _wrapper_datei(tmp_path: Path, *, kaputt: str = "") -> Path:
    fall = tmp_path / "fall"
    (fall / "abgeleitet" / "schichten").mkdir(parents=True)
    eingabe = fall / "abgeleitet" / "bestand" / "verankerung.parquet"
    eingabe.parent.mkdir(parents=True)
    _verankerung(7000001).to_parquet(eingabe)
    import hashlib

    beleg = baue_schichtbeleg(
        _verankerung(7000001), _bestand(7000001), None, _spez_einzellig(),
        formfunktion="proportional_zur_basis")
    beleg["provenienz"] = {
        "systemstand": systemstand(REPO_ROOT),
        "eingaben": {
            "abgeleitet/bestand/verankerung.parquet": hashlib.sha256(
                eingabe.read_bytes()).hexdigest()},
        "parameter": {"formfunktion": "proportional_zur_basis"},
    }
    if kaputt == "systemstand":
        beleg["provenienz"]["systemstand"] = {"gefaelscht": "x"}
    if kaputt == "ohne_provenienz":
        del beleg["provenienz"]
    pfad = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    pfad.write_text(json.dumps(beleg), encoding="utf-8")
    if kaputt == "eingabe":
        eingabe.write_bytes(eingabe.read_bytes() + b"x")
    return fall


def test_abgeleiteter_beleg_wird_nur_mit_nachgerechneter_bindung_akzeptiert(
        tmp_path):
    fall = _wrapper_datei(tmp_path)
    schichten = _schichten(
        fall, "abgeleitet/schichten/verankerung_schichten.json",
        repo_root=REPO_ROOT)
    assert isinstance(schichten["7000001"]["hist"], Schichtparameter)


def test_manipulation_der_eingabe_faellt_hart(tmp_path):
    fall = _wrapper_datei(tmp_path, kaputt="eingabe")
    with pytest.raises(SystemExit, match="veraendert"):
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
        grund_mp, erh_jahr, summe)))]
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
