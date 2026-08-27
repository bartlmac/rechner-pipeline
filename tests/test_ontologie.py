"""Ontologie-Kern: Aussagen-Invarianten, Merge (P2), A-Box, Coverage (P6).

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rechner_pipeline.ontologie import (
    ABox,
    Aussage,
    Diskrepanz,
    Entscheidung,
    Lesart,
    Merkmalsdimension,
    Parametrierungszelle,
    PFLICHT_PARAMETER,
    Provenienz,
    Quelle,
    Tarifgeneration,
    Zustand,
    belegt,
    nicht_belegt,
)
from rechner_pipeline.ontologie.abox import (
    lade,
    roundtrip_stabil,
    speichere,
    validate_abox,
)
from rechner_pipeline.ontologie.coverage import coverage_bericht
from rechner_pipeline.ontologie.ids import (
    KnotenIdFehler,
    knoten_id,
    zellen_segment,
)
from rechner_pipeline.ontologie.merge import merge_aussagen, merge_felder

SHA_A = "a" * 64
SHA_B = "b" * 64


def prov(datei: str = "Tarifrechner_KLV_TG2015.xlsm",
         sha: str = SHA_A,
         fundstelle: str = "Kalkulation!$E$4",
         akteur: str = "test") -> Provenienz:
    return Provenienz(
        quelle_datei=datei, quelle_sha256=sha, fundstelle=fundstelle,
        akteur=akteur, erhoben_am="2026-08-14T18:00:00+00:00",
    )


# --------------------------------------------------------------------------- #
# Aussagen: die Zustaende sind Invarianten, keine Konvention (P1/P3)
# --------------------------------------------------------------------------- #


def test_belegt_braucht_wert_und_beleg():
    a = belegt(0.0175, [prov()])
    assert a.zustand is Zustand.BELEGT and a.wert == 0.0175
    with pytest.raises(ValidationError, match="ohne Provenienz"):
        Aussage(zustand=Zustand.BELEGT, wert=1.0)
    with pytest.raises(ValidationError, match="ohne Wert"):
        Aussage(zustand=Zustand.BELEGT, provenienz=[prov()])


def test_nicht_belegt_traegt_nichts():
    assert nicht_belegt().zustand is Zustand.NICHT_BELEGT
    with pytest.raises(ValidationError, match="gelogen"):
        Aussage(zustand=Zustand.NICHT_BELEGT, wert=1.0)


def test_widerspruechlich_braucht_lesarten_und_diskrepanz():
    lesarten = [
        Lesart(wert=0.025, provenienz=[prov(fundstelle="Meldung Tab. 2")]),
        Lesart(wert=0.03, provenienz=[prov(fundstelle="Kalkulation!$E$7")]),
    ]
    a = Aussage(zustand=Zustand.WIDERSPRUECHLICH, lesarten=lesarten,
                diskrepanz_id="klv/tg2015/zelle:einzel,nichtraucher#beta1")
    assert a.wert is None
    with pytest.raises(ValidationError, match="diskrepanz_id"):
        Aussage(zustand=Zustand.WIDERSPRUECHLICH, lesarten=lesarten)
    with pytest.raises(ValidationError, match="zwei Lesarten"):
        Aussage(zustand=Zustand.WIDERSPRUECHLICH, lesarten=lesarten[:1],
                diskrepanz_id="x#y")


def test_diskrepanz_aufloesung_ist_expliziter_vorgang():
    lesarten = [
        Lesart(wert=1, provenienz=[prov()]),
        Lesart(wert=2, provenienz=[prov(sha=SHA_B, datei="m.docx")]),
    ]
    with pytest.raises(ValidationError, match="Entscheider"):
        Diskrepanz(id="k#f", knoten="k", feld="f", lesarten=lesarten,
                   status="aufgeloest")
    d = Diskrepanz(
        id="k#f", knoten="k", feld="f", lesarten=lesarten,
        status="aufgeloest",
        entscheidung=Entscheidung(
            entscheider="bartek", begruendung="Meldung ist massgeblich",
            gewaehlter_wert=1, entschieden_am="2026-08-15T09:00:00+00:00",
        ),
    )
    assert d.entscheidung.gewaehlter_wert == 1


# --------------------------------------------------------------------------- #
# Merge: P2 ist Merge-Code, kein Agenten-Urteil
# --------------------------------------------------------------------------- #


def test_merge_gleiche_werte_vereint_belege():
    a = belegt(0.0175, [prov(datei="meldung.docx", sha=SHA_B,
                             fundstelle="Tab. 2, Zeile 3")], konfidenz=0.9)
    b = belegt(0.0175, [prov()], konfidenz=0.7)
    ergebnis, diskrepanz = merge_aussagen("klv/tg2015/zelle:-", "zins", [a, b])
    assert diskrepanz is None
    assert ergebnis.zustand is Zustand.BELEGT
    assert len(ergebnis.provenienz) == 2          # BEIDE Belege
    assert ergebnis.konfidenz == 0.7              # konservativ: Minimum


def test_merge_rundungsartefakt_ist_kein_widerspruch():
    a = belegt(0.0008, [prov()])
    b = belegt(0.0008000000000001, [prov(sha=SHA_B, datei="m.docx")])
    ergebnis, diskrepanz = merge_aussagen("k", "gamma1", [a, b])
    assert diskrepanz is None and ergebnis.zustand is Zustand.BELEGT


def test_merge_widerspruch_erzeugt_diskrepanz_mit_beiden_lesarten():
    meldung = belegt(0.025, [prov(datei="m.docx", sha=SHA_B,
                                  fundstelle="Tab. 3")])
    rechner = belegt(0.03, [prov(fundstelle="Kalkulation!$E$7")])
    ergebnis, diskrepanz = merge_aussagen(
        "klv/tg2015/zelle:einzel,nichtraucher", "beta1", [meldung, rechner]
    )
    assert ergebnis.zustand is Zustand.WIDERSPRUECHLICH
    assert ergebnis.wert is None                  # kein stiller Gewinner
    assert diskrepanz is not None
    assert [l.wert for l in diskrepanz.lesarten] == [0.025, 0.03]
    assert diskrepanz.id == ergebnis.diskrepanz_id
    assert diskrepanz.status == "offen"


def test_merge_einseitig_und_leer():
    nur_eine, d = merge_aussagen("k", "f", [belegt(5, [prov()]), nicht_belegt()])
    assert d is None and nur_eine.zustand is Zustand.BELEGT
    keine, d = merge_aussagen("k", "f", [nicht_belegt(), nicht_belegt()])
    assert d is None and keine.zustand is Zustand.NICHT_BELEGT


def test_merge_verweigert_vorentschiedene_konflikte():
    kaputt = Aussage(
        zustand=Zustand.WIDERSPRUECHLICH, diskrepanz_id="k#f",
        lesarten=[Lesart(wert=1, provenienz=[prov()]),
                  Lesart(wert=2, provenienz=[prov(sha=SHA_B, datei="x")])],
    )
    with pytest.raises(ValueError, match="im Merge"):
        merge_aussagen("k", "f", [kaputt, belegt(1, [prov()])])


def test_merge_felder_feldmenge_ist_vereinigung():
    meldung = {"zins": belegt(0.0175, [prov(datei="m.docx", sha=SHA_B)])}
    rechner = {"zins": belegt(0.0175, [prov()]),
               "beta1": belegt(0.03, [prov()])}
    felder, diskrepanzen = merge_felder("k", [meldung, rechner])
    assert set(felder) == {"zins", "beta1"}
    assert not diskrepanzen
    assert len(felder["zins"].provenienz) == 2


# --------------------------------------------------------------------------- #
# T-Box-Invarianten: Merkmalsraum vollstaendig, IDs abgeleitet
# --------------------------------------------------------------------------- #


def _quelle(art: str = "tarifrechner") -> Quelle:
    return Quelle(datei="Tarifrechner_KLV_TG2015.xlsm", sha256=SHA_A, art=art)


def _zelle(auspraegungen: dict, **parameter) -> Parametrierungszelle:
    return Parametrierungszelle(
        id=zellen_segment(auspraegungen), auspraegungen=auspraegungen,
        parameter={k: belegt(v, [prov()]) for k, v in parameter.items()},
    )


def test_generation_zellen_muessen_merkmalsraum_exakt_decken():
    dims = [
        Merkmalsdimension(id="status", name="Raucherstatus",
                          auspraegungen=["raucher", "nichtraucher"]),
        Merkmalsdimension(id="tarifart", name="Tarifart",
                          auspraegungen=["einzel", "kollektiv", "haus"]),
    ]
    alle = [
        _zelle({"status": s, "tarifart": t})
        for s in ("raucher", "nichtraucher")
        for t in ("einzel", "kollektiv", "haus")
    ]
    gen = Tarifgeneration(
        id="klv/tg2015", name="TG2015", familie="klv",
        quellen=[_quelle()], dimensionen=dims, zellen=alle,
    )
    assert len(gen.zellen) == 6
    with pytest.raises(ValidationError, match="Merkmalsraum"):
        Tarifgeneration(
            id="klv/tg2015", name="TG2015", familie="klv",
            quellen=[_quelle()], dimensionen=dims, zellen=alle[:-1],
        )


def test_generation_ohne_dimensionen_hat_genau_eine_zelle():
    gen = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[_quelle()], zellen=[_zelle({})],
    )
    assert gen.zellen[0].id == "zelle:-"


def test_unbekannter_parameter_ist_hart():
    with pytest.raises(ValidationError, match="unbekannte Parameter"):
        _zelle({}, stoab_prozent=0.005)   # Tippfehler-Feld


def test_zellen_id_ist_abgeleitet_und_deterministisch():
    a = zellen_segment({"tarifart": "einzel", "status": "nichtraucher"})
    b = zellen_segment({"status": "nichtraucher", "tarifart": "einzel"})
    assert a == b == "zelle:nichtraucher,einzel"
    with pytest.raises(ValidationError, match="abgeleitet"):
        Parametrierungszelle(id="zelle:falsch", auspraegungen={})
    with pytest.raises(KnotenIdFehler):
        knoten_id("KLV")                  # Grossschreibung


# --------------------------------------------------------------------------- #
# A-Box: Determinismus, Kreuz-Validierung, Bindung an das Eingang-Register
# --------------------------------------------------------------------------- #


def _abox(fall: str = "faelle/test") -> ABox:
    gen = Tarifgeneration(
        id="klv/tg2012", name="TG2012", familie="klv",
        quellen=[_quelle()],
        zellen=[_zelle({}, zins=0.0175, tafel="DAV2008_T")],
    )
    return ABox(fall=fall, generationen=[gen])


def test_abox_roundtrip_ist_byte_stabil(tmp_path: Path):
    abox = _abox()
    assert roundtrip_stabil(abox)
    fall = tmp_path / "fall"
    pfad1 = speichere(abox, fall)
    inhalt1 = pfad1.read_bytes()
    speichere(lade(fall), fall)
    assert pfad1.read_bytes() == inhalt1


def test_validate_widerspruch_braucht_diskrepanz_objekt():
    abox = _abox()
    zelle = abox.generationen[0].zellen[0]
    lesarten = [Lesart(wert=1, provenienz=[prov()]),
                Lesart(wert=2, provenienz=[prov(sha=SHA_B, datei="m.docx")])]
    zelle.parameter["beta1"] = Aussage(
        zustand=Zustand.WIDERSPRUECHLICH, lesarten=lesarten,
        diskrepanz_id="klv/tg2012/zelle:-#beta1",
    )
    fehler = validate_abox(abox)
    assert any("Diskrepanz" in f and "fehlt" in f for f in fehler)
    abox.diskrepanzen.append(Diskrepanz(
        id="klv/tg2012/zelle:-#beta1", knoten="klv/tg2012/zelle:-",
        feld="beta1", lesarten=lesarten,
    ))
    assert validate_abox(abox) == []


def test_validate_verwaiste_offene_diskrepanz():
    abox = _abox()
    abox.diskrepanzen.append(Diskrepanz(
        id="k#f", knoten="k", feld="f",
        lesarten=[Lesart(wert=1, provenienz=[prov()]),
                  Lesart(wert=2, provenienz=[prov(sha=SHA_B, datei="x")])],
    ))
    assert any("verwaist" in f for f in validate_abox(abox))


def test_validate_bindet_quellen_an_das_eingang_register():
    abox = _abox()
    register = {"quellen": [
        {"datei": "Tarifrechner_KLV_TG2015.xlsm", "sha256": SHA_A},
    ]}
    assert validate_abox(abox, register) == []
    register["quellen"][0]["sha256"] = SHA_B
    assert any("registriert ist" in f for f in validate_abox(abox, register))
    register["quellen"] = []
    assert any("nicht registriert" in f for f in validate_abox(abox, register))


def test_validate_unisex_format():
    abox = _abox()
    abox.generationen[0].unisex = belegt("U70", [prov()])
    assert validate_abox(abox) == []
    abox.generationen[0].unisex = belegt("70U", [prov()])
    assert any("U<0..100>" in f for f in validate_abox(abox))


# --------------------------------------------------------------------------- #
# Coverage: gemessen wird der Pflichtumfang, nicht das Extrahierte (P6)
# --------------------------------------------------------------------------- #


def test_coverage_zaehlt_gegen_pflichtumfang():
    abox = _abox()
    bericht = coverage_bericht(abox)
    [gen] = bericht["generationen"]
    assert gen["pflicht_gesamt"] == len(PFLICHT_PARAMETER)
    assert gen["zaehler"]["belegt"] == 2          # zins + tafel
    assert not gen["vollstaendig"]
    # Das uebersehene Feld ist ausgewiesen, nicht verschwiegen:
    felder = gen["zellen"]["zelle:-"]
    assert felder["alpha"]["zustand"] == "fehlt_in_extraktion"
    assert felder["zins"]["quellen"] == "tarifrechner"
    assert bericht["vollstaendig"] is False


def test_coverage_quellenlage_beide():
    abox = _abox()
    gen = abox.generationen[0]
    gen.quellen = [
        _quelle(), Quelle(datei="m.docx", sha256=SHA_B, art="tarifmeldung"),
    ]
    gen.zellen[0].parameter["zins"] = Aussage(
        zustand=Zustand.BELEGT, wert=0.0175,
        provenienz=[prov(), prov(datei="m.docx", sha=SHA_B, fundstelle="Tab. 2")],
    )
    bericht = coverage_bericht(abox)
    felder = bericht["generationen"][0]["zellen"]["zelle:-"]
    assert felder["zins"]["quellen"] == "tarifmeldung+tarifrechner"
