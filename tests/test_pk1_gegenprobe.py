"""P-K1-Gegenprobe: wo die Spez den Quell-Rechner bewusst verlaesst.

Eine menschlich entschiedene Diskrepanz GEGEN den Rechner (Gate A-Q1)
macht den Golden Master nicht wertlos — sie praezisiert ihn: Unter der
EIGENEN Lesart des Rechners muss der Kern ihn weiterhin exakt
reproduzieren. Diese Tests halten fest, wann die Gegenprobe greift und
vor allem, wann NICHT: eine vorlaeufige Aufloesung, eine fremde Zelle
oder eine Lesart ohne Rechner-Provenienz duerfen nie einen Wert
ersetzen — sonst waere die Gegenprobe ein Weg, jede Abweichung
wegzudefinieren.

Knoten: klv/tg2015
"""

from __future__ import annotations

from rechner_pipeline.gates.generation_golden import gegenprobe_felder
from rechner_pipeline.ontologie.aussage import Lesart, Provenienz
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz, Entscheidung
from rechner_pipeline.ontologie.tbox import ABox

RECHNER = "Tarifrechner_KLV_TG2015.xlsm"
MELDUNG = "Mitteilung_143_KLV_TG2015.docx"
ZELLE = "klv/tg2015/zelle:nichtraucher,einzel"


def _prov(datei: str) -> Provenienz:
    return Provenienz(
        quelle_datei=datei, quelle_sha256="a" * 64, fundstelle="x",
        akteur="test/extrahiere-quellfragment@abc1234",
        erhoben_am="2026-08-28T00:00:00+00:00",
    )


def _diskrepanz(*, feld="zins", knoten=ZELLE, gewaehlt=0.0125,
                vorlaeufig=False, rechner_datei=RECHNER,
                aufgeloest=True) -> Diskrepanz:
    return Diskrepanz(
        id=f"{knoten}#{feld}", knoten=knoten, feld=feld,
        lesarten=[
            Lesart(wert=0.0125, provenienz=[_prov(MELDUNG)]),
            Lesart(wert=0.0175, provenienz=[_prov(rechner_datei)]),
        ],
        status="aufgeloest" if aufgeloest else "offen",
        entscheidung=Entscheidung(
            entscheider="Test-Operator", begruendung="Beleg",
            gewaehlter_wert=gewaehlt,
            entschieden_am="2026-08-28T00:00:00+00:00",
            vorlaeufig=vorlaeufig,
        ) if aufgeloest else None,
    )


def _abox(*diskrepanzen) -> ABox:
    return ABox(fall="test", generationen=[], diskrepanzen=list(diskrepanzen))


def test_entschiedene_diskrepanz_wird_gegen_die_rechner_lesart_geprueft():
    felder = gegenprobe_felder(_abox(_diskrepanz()), ZELLE, RECHNER)
    assert felder["zins"]["rechner_wert"] == 0.0175
    assert felder["zins"]["spez_wert"] == 0.0125
    assert felder["zins"]["entscheider"] == "Test-Operator"


def test_vorlaeufige_aufloesung_loest_keine_gegenprobe_aus():
    """Sonst koennte ein Agent den Golden Master an sich selbst anpassen."""
    assert gegenprobe_felder(
        _abox(_diskrepanz(vorlaeufig=True)), ZELLE, RECHNER) == {}


def test_offene_diskrepanz_loest_keine_gegenprobe_aus():
    assert gegenprobe_felder(
        _abox(_diskrepanz(aufgeloest=False)), ZELLE, RECHNER) == {}


def test_diskrepanz_einer_anderen_zelle_wirkt_nicht():
    fremd = _diskrepanz(knoten="klv/tg2015/zelle:raucher,haus")
    assert gegenprobe_felder(_abox(fremd), ZELLE, RECHNER) == {}


def test_entscheid_zugunsten_des_rechners_ersetzt_nichts():
    """Folgt die Entscheidung dem Rechner, gibt es keine Abweichung."""
    assert gegenprobe_felder(
        _abox(_diskrepanz(gewaehlt=0.0175)), ZELLE, RECHNER) == {}


def test_lesart_ohne_rechner_provenienz_ersetzt_nichts():
    """Meldung gegen Bestand: der Rechner sagt dazu nichts."""
    fremde_quelle = _diskrepanz(rechner_datei="baldrian_abzug.csv")
    assert gegenprobe_felder(_abox(fremde_quelle), ZELLE, RECHNER) == {}


def test_ohne_bekannte_rechnerdatei_greift_die_gegenprobe_nie():
    assert gegenprobe_felder(_abox(_diskrepanz()), ZELLE, "") == {}
