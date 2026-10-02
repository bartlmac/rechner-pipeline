"""Hebung traegt nur, was im alten Artefakt steht; der Lader nennt jeden Regelwert.

Pruefrunde H, H13: Die Hebung einer Spez 0.1.0 uebernahm Bloecke
``tarifwerk``/``quellverfahren``, die 0.1.0 nicht kennt — Tarifregeln ohne
Fundstelle und ohne A-Box standen danach in einer geltenden Spez, und der
benannte Weg ueber die Feststellung mit Fundstelle war versperrt. Regel
(ADR-024, Nachtrag "Regel der Hebung"): Eine Hebung darf nur tragen, was im
alten Artefakt steht; eine 0.1.0-Datei mit Bloecken aus dem 0.2.0-Vokabular
ist keine 0.1.0-Datei und wird benannt verweigert. Dieselbe Bauform hatte die
Hebung der A-Box (gemessen: acht Tarifregel-Aussagen still mitgehoben).

Bekannter Punkt (a): Ein Dynamiksatz ``null`` liess den Lader mit einem
rohen Pydantic-Fehler ohne Ausweg scheitern; ein Wert ausserhalb des
Bereichs ging durch den Lader. Jetzt nennt der Lader fuer JEDES Merkmal
beider Bloecke Merkmal, erlaubten Bereich und Ausweg.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.ontologie import tbox
from rechner_pipeline.spez import validierung as sv

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "baldrian2_e2e" / "klv-tg2015.spez.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _als_0_1_0(daten: dict, *, ohne=("tarifwerk", "quellverfahren")) -> dict:
    alt = {k: v for k, v in daten.items() if k not in ohne}
    alt["tbox_version"] = "0.1.0"
    return alt


# --------------------------------------------------------------------------- #
# H13: Hebung der Spez
# --------------------------------------------------------------------------- #

def test_positivkontrolle_eine_echte_0_1_0_spez_wird_gehoben():
    gehoben = sv.hebe_spez_auf_geltende_version(sv.spez_bytes(_als_0_1_0(_fixture())))
    spez = sv.lade_spez_aus_bytes(gehoben)
    assert spez.tbox_version == tbox.TBOX_VERSION
    assert spez.tarifwerk == {} and spez.quellverfahren == {}


@pytest.mark.parametrize("veraenderung, genannt", [
    (lambda d, f: d.update(tarifwerk=dict(f["tarifwerk"], tku_umfang="alle_bausteine")),
     "tarifwerk"),
    (lambda d, f: d.update(quellverfahren=dict(f["quellverfahren"])), "quellverfahren"),
    (lambda d, f: d.update(tarifwerk={}), "tarifwerk"),
    (lambda d, f: d["urteil"].update(geaenderte_tarifwerksmerkmale=[]),
     "urteil.geaenderte_tarifwerksmerkmale"),
])
def test_h13_eine_0_1_0_spez_mit_vokabular_von_0_2_0_wird_verweigert(veraenderung, genannt):
    """Vorher: gehoben, und die Strecke rechnete mit den mitgetragenen Regeln
    (tku_umfang alle_bausteine statt der Feststellung)."""
    fixture = _fixture()
    alt = _als_0_1_0(fixture)
    veraenderung(alt, fixture)
    with pytest.raises(sv.SpezHebungFehler, match=genannt) as exc:
        sv.hebe_spez_auf_geltende_version(sv.spez_bytes(alt))
    assert "ergaenze_tarifregeln" in str(exc.value) and "spez.erzeugen" in str(exc.value)


def test_h13_der_weg_ueber_die_feststellung_bleibt_offen():
    """Der Ausweg der Meldung fuehrt zum Ziel: Bloecke weg, heben, Feststellung
    mit Fundstelle eintragen — ergibt byte-genau die Fixture."""
    regeln = json.loads((FIXTURE.parent / "tarifregeln.json").read_text(encoding="utf-8"))
    gehoben = sv.hebe_spez_auf_geltende_version(sv.spez_bytes(_als_0_1_0(_fixture())))
    assert sv.ergaenze_tarifregeln(gehoben, regeln) == FIXTURE.read_bytes()


# --------------------------------------------------------------------------- #
# H13: Hebung der A-Box (dieselbe Bauform)
# --------------------------------------------------------------------------- #

def test_h13_eine_0_1_0_a_box_mit_bloecken_von_0_2_0_wird_verweigert(tmp_path):
    from rechner_pipeline.ontologie.abox import (
        ABox,
        abox_pfad,
        hebe_auf_geltende_version,
        lade_aus_bytes,
    )
    from tests.test_tarifregeln_aus_spez import VOLLSTAENDIG, _pq3_fall

    fall = _pq3_fall(tmp_path, "bestand", VOLLSTAENDIG)
    daten = json.loads(abox_pfad(fall).read_bytes())
    daten["tbox_version"] = "0.1.0"
    with pytest.raises(ValueError, match="Vokabular von 0.2.0") as exc:
        hebe_auf_geltende_version(lade_aus_bytes(json.dumps(daten).encode()))
    assert "gates.abox_merge" in str(exc.value)
    # Positivkontrolle: dieselbe A-Box ohne die Bloecke wird gehoben.
    for gen in daten["generationen"]:
        for block in tbox.GENERATIONS_BLOECKE:
            gen.pop(block, None)
    neu = hebe_auf_geltende_version(lade_aus_bytes(json.dumps(daten).encode()))
    assert isinstance(neu, ABox) and neu.tbox_version == tbox.TBOX_VERSION


# --------------------------------------------------------------------------- #
# (a): der Lader nennt jeden Regelwert ausserhalb des Vokabulars
# --------------------------------------------------------------------------- #

MERKMALE = [(b, m) for b, bereiche in tbox.GENERATIONS_BLOECKE.items() for m in bereiche]


def test_die_menge_der_merkmale_ist_die_der_t_box():
    """== : ein neues Merkmal der T-Box landet in der Parametrisierung unten."""
    assert len(MERKMALE) == 9 == sum(len(v) for v in tbox.GENERATIONS_BLOECKE.values())


@pytest.mark.parametrize("block, merkmal", MERKMALE)
@pytest.mark.parametrize("wert", [None, [], "kein-wert-des-bereichs"])
def test_jeder_falsche_regelwert_wird_mit_merkmal_bereich_und_ausweg_verweigert(
        block, merkmal, wert):
    daten = _fixture()
    daten[block] = {**daten[block], merkmal: wert}
    with pytest.raises(sv.SpezRegelwertFehler) as exc:
        sv.lade_spez_aus_bytes(sv.spez_bytes(daten))
    meldung = str(exc.value)
    assert f"{block}.{merkmal} = {json.dumps(wert)}" in meldung, meldung
    assert tbox.bereich_text(tbox.GENERATIONS_BLOECKE[block][merkmal]) in meldung
    assert "spez.erzeugen" in meldung and "nicht_belegt" in meldung


def test_null_am_dynamiksatz_nennt_die_feststellung_als_ausweg():
    """Der Befund des Punkts (a) woertlich: kein roher Pydantic-Fehler mehr."""
    daten = _fixture()
    daten["quellverfahren"]["erhoehungssatz"] = None
    with pytest.raises(sv.SpezRegelwertFehler,
                       match=r"quellverfahren\.erhoehungssatz = null .* oder die "
                             r"Feststellung 'nicht_belegt'"):
        sv.lade_spez_aus_bytes(sv.spez_bytes(daten))


def test_unbekanntes_merkmal_und_kein_objekt_werden_benannt():
    daten = _fixture()
    daten["quellverfahren"] = {**daten["quellverfahren"], "stichtag_der_quelle": "x"}
    with pytest.raises(sv.SpezRegelwertFehler, match="stichtag_der_quelle ist kein Merkmal"):
        sv.lade_spez_aus_bytes(sv.spez_bytes(daten))
    daten = _fixture()
    daten["tarifwerk"] = ["scheiben_mit_gamma1"]
    with pytest.raises(sv.SpezRegelwertFehler, match="tarifwerk ist kein Objekt"):
        sv.lade_spez_aus_bytes(sv.spez_bytes(daten))


def test_positivkontrolle_belegte_werte_und_die_feststellung_laden():
    daten = _fixture()
    assert sv.lade_spez_aus_bytes(sv.spez_bytes(daten)).tarifwerk == daten["tarifwerk"]
    daten["quellverfahren"]["erhoehungssatz"] = "nicht_belegt"
    assert sv.lade_spez_aus_bytes(
        sv.spez_bytes(daten)).quellverfahren["erhoehungssatz"] == "nicht_belegt"
