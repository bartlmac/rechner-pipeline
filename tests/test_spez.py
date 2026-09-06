"""Stage 2: Spez-Schema, Struktur-Urteil, Projektion, Spez-gegen-A-Box.

Knoten: klv
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from rechner_pipeline.ontologie import (
    ABox,
    Merkmalsdimension,
    Parametrierungszelle,
    PFLICHT_PARAMETER,
    Provenienz,
    Quelle,
    Tarifgeneration,
    belegt,
)
from rechner_pipeline.ontologie.ids import zellen_segment
from rechner_pipeline.spez.erzeugen import SpezFehler, baue_spez, strukturvergleich
from rechner_pipeline.spez.schema import StrukturUrteil, TafelAbleitung, TarifSpez, ZellSpez
from rechner_pipeline.spez.validierung import (
    lade_spez,
    speichere_spez,
    validate_spez,
)

SHA = "c" * 64


def _prov(fundstelle: str = "Kalkulation!$G$4") -> Provenienz:
    return Provenienz(
        quelle_datei="Tarifrechner_KLV_TG2015.xlsm", quelle_sha256=SHA,
        fundstelle=fundstelle, akteur="test",
        erhoben_am="2026-08-14T20:00:00+00:00",
    )


def _parameter(tafel: str = "DAV2008_T", **override):
    basis = {
        "zins": 0.0175, "tafel": tafel, "alpha": 0.025, "beta1": 0.03,
        "gamma1": 0.001, "gamma2": 0.00125, "gamma3": 0.0025,
        "policy_fee": 12.0, "stoab_satz": 0.005, "stoab_min": 50.0,
        "stoab_max": 200.0, "min_alter_flex": 60, "min_rlz_flex": 5,
    }
    basis.update(override)
    return {k: belegt(v, [_prov()]) for k, v in basis.items()}


def _tg2012() -> Tarifgeneration:
    parameter = _parameter(zins=0.0225, beta1=0.025, gamma1=0.0008,
                           policy_fee=24.0, stoab_satz=0.01, stoab_max=150.0)
    return Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[Quelle(datei="Tarifrechner_KLV_TG2012.xlsm", sha256=SHA,
                        art="tarifrechner")],
        zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
    )


def _tg2015() -> Tarifgeneration:
    dims = [
        Merkmalsdimension(id="status", name="Raucherstatus",
                          auspraegungen=["raucher", "nichtraucher"]),
        Merkmalsdimension(id="tarifart", name="Tarifart",
                          auspraegungen=["einzel", "kollektiv", "haus"]),
    ]
    zellen = []
    for s, suffix in (("raucher", "R"), ("nichtraucher", "NR")):
        for t in ("einzel", "kollektiv", "haus"):
            auspraegungen = {"status": s, "tarifart": t}
            zellen.append(Parametrierungszelle(
                id=zellen_segment(auspraegungen),
                auspraegungen=auspraegungen,
                parameter=_parameter(tafel=f"DAV2008_T_{suffix}"),
            ))
    return Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[Quelle(datei="Tarifrechner_KLV_TG2015.xlsm", sha256=SHA,
                        art="tarifrechner")],
        dimensionen=dims, zellen=zellen,
        unisex=belegt("U70", [_prov("Meldung Abschnitt 2")]),
    )


def _abox() -> ABox:
    return ABox(fall="faelle/test", generationen=[_tg2012(), _tg2015()])


KERN_TAFELN = {
    "DAV1994_T_M", "DAV1994_T_F", "DAV2008_T_M", "DAV2008_T_F",
}


def test_strukturvergleich_erkennt_parametrierung_mit_neuen_dimensionen():
    urteil = strukturvergleich(_tg2015(), _tg2012(), KERN_TAFELN, "U70")
    assert urteil.ergebnis == "parametrierung"
    assert urteil.neue_dimensionen == ["status", "tarifart"]
    # Neue Tafeln: R/NR-Vektoren + Unisex-Ableitungen, aber NICHT DAV2008_T_M/F
    assert "DAV2008_T_R_M" in urteil.neue_tafeln
    assert "DAV2008_T_NR_U70" in urteil.neue_tafeln
    assert "DAV2008_T_M" not in urteil.neue_tafeln
    assert "beta1" in urteil.geaenderte_parameter
    assert "stoab_satz" in urteil.geaenderte_parameter


def test_baue_spez_verlangt_aufgeloeste_abox():
    abox = _abox()
    gen = abox.generationen[1]
    gen.zellen[0].parameter.pop("zins")            # Luecke
    with pytest.raises(SpezFehler, match="Gate P-Q3"):
        baue_spez(abox, "klv/tg2015", "klv/tg2012", KERN_TAFELN)


def test_baue_spez_projiziert_zellen_und_ableitungen():
    spez = baue_spez(_abox(), "klv/tg2015", "klv/tg2012", KERN_TAFELN)
    assert spez.generation == "klv/tg2015"
    assert len(spez.zellen) == 6
    zelle = next(z for z in spez.zellen
                 if z.auspraegungen == {"status": "nichtraucher",
                                        "tarifart": "einzel"})
    assert zelle.model_point["tafel"] == "DAV2008_T_NR_U70"
    assert zelle.model_point["stoab_satz"] == 0.005
    namen = {a.name for a in spez.tafel_ableitungen}
    assert namen == {"DAV2008_T_R_U70", "DAV2008_T_NR_U70"}
    assert all(a.maenneranteil == 0.70 for a in spez.tafel_ableitungen)
    # Importe: die R/NR-Basisvektoren (xml-Ebene), nicht die Ableitungen
    assert "DAV2008_T_R_M" in spez.tafel_importe
    assert "DAV2008_T_NR_U70" not in spez.tafel_importe


def test_spez_schema_invarianten():
    zelle = ZellSpez(knoten="klv/tg2012/zelle:-",
                     model_point={"zins": 0.0225, "tafel": "DAV2008_T"})
    urteil = StrukturUrteil(ergebnis="parametrierung", begruendung=["x"])
    # unisex ohne Ableitung ist gelogen:
    with pytest.raises(ValidationError, match="Mischtafel"):
        TarifSpez(generation="klv/tg2015", familie="klv", urteil=urteil,
                  unisex="U70", zellen=[zelle])
    # Formel-Erweiterung braucht benannte Stelle:
    urteil2 = StrukturUrteil(ergebnis="parametrierung_mit_erweiterung",
                             formel_erweiterungen=["indexierung"],
                             begruendung=["x"])
    with pytest.raises(ValidationError, match="benannte Erweiterungsstellen"):
        TarifSpez(generation="klv/tg2015", familie="klv", urteil=urteil2,
                  zellen=[zelle])


def test_validate_spez_gegen_abox(tmp_path: Path):
    abox = _abox()
    spez = baue_spez(abox, "klv/tg2015", "klv/tg2012", KERN_TAFELN)
    assert validate_spez(spez, abox) == []
    # Roundtrip ueber den Fall-Arbeitsbereich:
    speichere_spez(spez, tmp_path)
    wieder = lade_spez(tmp_path, "klv/tg2015")
    assert validate_spez(wieder, abox) == []
    # Eigene Wahrheit der Spez wird erkannt:
    wieder.zellen[0].model_point["beta1"] = 0.031
    assert any("!= A-Box" in f for f in validate_spez(wieder, abox))
    # Falscher finaler Tafelname wird erkannt:
    spez2 = baue_spez(abox, "klv/tg2015", "klv/tg2012", KERN_TAFELN)
    spez2.zellen[0].model_point["tafel"] = "DAV2008_T_NR"
    assert any("erwartet" in f for f in validate_spez(spez2, abox))


def test_validate_spez_zellenmenge():
    abox = _abox()
    spez = baue_spez(abox, "klv/tg2015", "klv/tg2012", KERN_TAFELN)
    spez.zellen = spez.zellen[:-1]
    assert any("Zellenmengen" in f for f in validate_spez(spez, abox))
