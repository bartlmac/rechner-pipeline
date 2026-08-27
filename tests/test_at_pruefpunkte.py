"""Die drei aktuariellen Abnahmen: Pruefpunkte, dDK, Profile (ADR-010/012).

Geprueft wird, was der Umbau NEU behauptet — nicht noch einmal, was
test_aktuarieller_test schon abdeckt:

* Ein Vertrag traegt mehrere Pruefpunkte und besteht nur, wenn ALLE
  bestehen.
* ``dDK`` ist die Veraenderung des Deckungskapitals durch einen
  Geschaeftsvorfall, je Vorfallart anders gebildet.
* Unterjaehrig ist genau dann zulaessig, wenn ein Geschaeftsvorfall den
  Rechenpunkt setzt.
* Toleranzen kommen aus dem Profil; Verteilungsgrenzen kippen den Test
  auch dann, wenn jeder Einzelwert in seiner Toleranz liegt.

Die Erwartungswerte der gruenen Pfade stammen aus demselben Kern —
geprueft wird das URTEIL, nicht die Rechnung.

Knoten: klv
"""

from __future__ import annotations

import dataclasses

import pytest

from rechner_pipeline.kern import KLV_DEFAULT, Rechenkern
from rechner_pipeline.qa.aktuarieller_test import (
    ANLASS_FORTSCHREIBUNG,
    ANLASS_UEBERNAHME,
    ANLASS_VERLAUF,
    GEVO_ARTEN,
    AktuartestFehler,
    Pruefpunkt,
    Vertragspruefung,
    pruefe_stichprobe,
    pruefe_vertrag,
)
from rechner_pipeline.qa.stichprobe import ziehe
from rechner_pipeline.qa.testprofil import (
    RUNDUNGSRAUSCHEN,
    Kriterium,
    ProfilFehler,
    Testprofil,
)

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA = 12 * 9
ENG = Kriterium(abs_tol=0.005, rel_tol=1e-9)


def _profil(kennung="A-M1", kriterien=None, grund=ENG, weite="vollbestand"):
    return Testprofil(
        kennung=kennung, weite=weite, kriterien=kriterien or {},
        grundtoleranz=grund,
    )


def _vertrag(*punkte, police_id="P1", **kwargs):
    return Vertragspruefung(
        police_id=police_id, model_point=dict(MP),
        historientyp=kwargs.pop("historientyp", "ohne_gevo"),
        punkte=tuple(punkte), **kwargs,
    )


# --------------------------------------------------------------------------- #
# 1. Mehrere Pruefpunkte je Vertrag
# --------------------------------------------------------------------------- #


def test_vertrag_besteht_nur_wenn_jeder_pruefpunkt_besteht():
    """Der Zugewinn von A-M1: der zweite Zeitpunkt kann allein kippen.

    Ein Vertrag, der am Uebernahmestichtag stimmt und beim naechsten
    Stichtag nicht, hat einen Fortschreibungsfehler — den eine
    Korrekturschicht spaeter verdecken wuerde.
    """
    uebernahme = KERN.zustand_am(TA).vx_mrv
    fort = KERN.zustand_am(TA + 12).vx_mrv
    gut = _vertrag(
        Pruefpunkt(TA, {"kVx_MRV": uebernahme}, ANLASS_UEBERNAHME),
        Pruefpunkt(TA + 12, {"kVx_MRV": fort}, ANLASS_FORTSCHREIBUNG),
    )
    assert pruefe_vertrag(gut, _profil())["bestanden"] is True

    nur_zweiter_falsch = _vertrag(
        Pruefpunkt(TA, {"kVx_MRV": uebernahme}, ANLASS_UEBERNAHME),
        Pruefpunkt(TA + 12, {"kVx_MRV": fort + 5.0}, ANLASS_FORTSCHREIBUNG),
    )
    ergebnis = pruefe_vertrag(nur_zweiter_falsch, _profil())
    assert ergebnis["bestanden"] is False
    # Der Befund benennt den Anlass — sonst weiss der Aktuar nicht, WO.
    assert "fortschreibung" in ergebnis["befunde"][0]
    assert sorted(ergebnis["anlaesse"]) == ["fortschreibung", "uebernahme"]


def test_derselbe_zeitpunkt_mit_demselben_anlass_faellt_hart_aus():
    """Doppelte Punkte zaehlten doppelt in die Verteilung."""
    p = Pruefpunkt(TA, {"kVx_MRV": 1.0}, ANLASS_UEBERNAHME)
    with pytest.raises(AktuartestFehler, match="mehrfacher Pruefpunkt"):
        pruefe_vertrag(_vertrag(p, p), _profil())


def test_vertrag_ohne_pruefpunkt_ist_kein_testauftrag():
    with pytest.raises(AktuartestFehler, match="kein Pruefpunkt"):
        pruefe_vertrag(_vertrag(), _profil())


# --------------------------------------------------------------------------- #
# 2. dDK je Geschaeftsvorfall
# --------------------------------------------------------------------------- #


def test_ddk_bei_storno_ist_der_negative_bestandswert():
    """Der Vertrag endet: das Deckungskapital geht auf null."""
    dk = KERN.zustand_am(TA).vx_mrv
    v = _vertrag(Pruefpunkt(TA, {"dDK": -dk}, "STO"))
    ergebnis = pruefe_vertrag(v, _profil("A-M3"))
    assert ergebnis["bestanden"] is True
    assert ergebnis["pruefungen"][0]["system"] == pytest.approx(-dk)


def test_ddk_bei_beitragsfreistellung_ist_die_umwandlungsdifferenz():
    """Verlustfreie Umwandlung ergibt null; ein Abzug macht dDK negativ."""
    a0 = TA // 12
    bpfl = KERN.zustand_am(TA).vx_mrv
    bfr = KERN.reserve_beitragsfrei(a0, a0)
    v = _vertrag(
        Pruefpunkt(TA, {"dDK": bfr - bpfl}, "PEX"),
        beitragsfrei_seit_jahr=a0,
    )
    ergebnis = pruefe_vertrag(v, _profil("A-M3"))
    assert ergebnis["bestanden"] is True
    assert ergebnis["pruefungen"][0]["system"] == pytest.approx(bfr - bpfl)


def test_ddk_bei_erhoehung_ist_null():
    """Die neue Scheibe beginnt bei null — ein anderer Wert ist ein Befund."""
    v = _vertrag(Pruefpunkt(TA, {"dDK": 0.0}, "ERH"))
    assert pruefe_vertrag(v, _profil("A-M3"))["bestanden"] is True

    falsch = _vertrag(Pruefpunkt(TA, {"dDK": 250.0}, "ERH"))
    assert pruefe_vertrag(falsch, _profil("A-M3"))["bestanden"] is False


@pytest.mark.parametrize("art", ["INV", "REA"])
def test_ddk_bei_bu_zustandswechsel_faellt_hart_aus(art: str):
    """Lieber kein Wert als ein KLV-Wert, der wie ein BU-Wert aussieht."""
    v = _vertrag(Pruefpunkt(TA, {"dDK": 0.0}, art))
    with pytest.raises(AktuartestFehler, match="BU-Zustandsbewertung"):
        pruefe_vertrag(v, _profil("A-M3"))


def test_ddk_ohne_geschaeftsvorfall_faellt_hart_aus():
    """Ohne Vorfall gibt es keine Veraenderung, die dDK messen koennte."""
    v = _vertrag(Pruefpunkt(TA, {"dDK": 0.0}, ANLASS_UEBERNAHME))
    with pytest.raises(AktuartestFehler, match="DURCH einen Geschaeftsvorfall"):
        pruefe_vertrag(v, _profil())


def test_jede_gevo_art_ist_in_der_wirkungstabelle_erfasst():
    """Eine neue Vorfallart darf nicht still ohne Wirkung durchlaufen."""
    from rechner_pipeline.qa.aktuarieller_test import GEVO_WIRKUNG

    assert set(GEVO_WIRKUNG) == set(GEVO_ARTEN)


# --------------------------------------------------------------------------- #
# 3. Unterjaehrige Rechenpunkte
# --------------------------------------------------------------------------- #


def test_unterjaehrig_ist_nur_mit_geschaeftsvorfall_zulaessig():
    """Der Vorfall setzt den Rechenpunkt; sonst waere der Wert interpoliert.

    Das ist die geschaerfte Form der ADR-010-Invariante: Verboten ist die
    INTERPOLATION, nicht der unterjaehrige Vergleich einer Groesse, die
    das System an diesem Termin tatsaechlich bildet.
    """
    monat = TA + 5
    erlaubt = _vertrag(
        Pruefpunkt(monat, {"dDK": -KERN.monatsreserve(monat).vx_mrv}, "STO")
    )
    assert pruefe_vertrag(erlaubt, _profil("A-M3"))["bestanden"] is True

    for anlass in (ANLASS_UEBERNAHME, ANLASS_FORTSCHREIBUNG, ANLASS_VERLAUF):
        verboten = _vertrag(Pruefpunkt(monat, {"kVx_MRV": 1.0}, anlass))
        with pytest.raises(AktuartestFehler, match="kein Rechenpunkt"):
            pruefe_vertrag(verboten, _profil())


def test_unterjaehriger_wert_folgt_der_zinsfreien_konvention_des_systems():
    """Der unterjaehrige Wert IST die lineare Konvention — und das ist gewollt.

    Wichtig fuer die Auslegung der Invariante: Die Monatsreserve des Kerns
    ist ausdruecklich linear zwischen den Vertragsjahrestagen gebildet
    (Grundsatzdokumentation Abschnitt 6, ``klv.monatsreserve``). Beim
    Geschaeftsvorfall ist dieser Wert kein Hilfskonstrukt, sondern der
    Betrag, den das Unternehmen tatsaechlich auszahlt oder gutschreibt.
    Genau diese Konvention gehoert geprueft: Interpoliert das Quellsystem
    anders, ist die Differenz eine echte Konventionsdifferenz mit
    Zahlungswirkung — kein Messfehler des Tests.
    """
    monat = TA + 7
    m = KERN.monatsreserve(monat)
    v = _vertrag(Pruefpunkt(monat, {"kVx_MRV": m.vx_mrv, "RKW": m.rkw}, "STO"))
    assert pruefe_vertrag(v, _profil("A-M3"))["bestanden"] is True

    jahr_a = KERN.zustand_am(TA).vx_mrv
    jahr_b = KERN.zustand_am(TA + 12).vx_mrv
    linear = jahr_a + (jahr_b - jahr_a) * 7 / 12
    assert m.vx_mrv == pytest.approx(linear, abs=1e-9), (
        "Die Konvention ist linear. Aendert sie sich, aendert sich der "
        "ausgezahlte Betrag — dann ist dieser Test die Stelle, an der es "
        "auffaellt."
    )


def test_unbekannter_anlass_faellt_hart_aus():
    v = _vertrag(Pruefpunkt(TA, {"kVx_MRV": 1.0}, "XYZ"))
    with pytest.raises(AktuartestFehler, match="unbekannter Anlass"):
        pruefe_vertrag(v, _profil())


# --------------------------------------------------------------------------- #
# 4. Profil: Toleranzen und Abnahmegrenzen
# --------------------------------------------------------------------------- #


def test_toleranz_kommt_aus_dem_profil_nicht_aus_einer_konstante():
    """Dieselbe Abweichung, zwei Profile, zwei Urteile."""
    dk = KERN.zustand_am(TA).vx_mrv
    v = _vertrag(Pruefpunkt(TA, {"kVx_MRV": dk + 0.5}, ANLASS_UEBERNAHME))
    assert pruefe_vertrag(v, _profil())["bestanden"] is False
    weit = _profil(grund=Kriterium(abs_tol=1.0, rel_tol=1e-9))
    assert pruefe_vertrag(v, weit)["bestanden"] is True


def test_kriterium_je_gevo_art_schlaegt_die_grundtoleranz():
    """Bei A-M3 entscheidet die Vorfallart, nicht die Groesse."""
    dk = KERN.zustand_am(TA).vx_mrv
    v = _vertrag(Pruefpunkt(TA, {"dDK": -dk + 0.5}, "STO"))
    profil = _profil("A-M3", kriterien={"STO": Kriterium(abs_tol=1.0, rel_tol=1e-9)})
    assert pruefe_vertrag(v, profil)["bestanden"] is True
    # ohne die Ausnahme greift die enge Grundtoleranz
    assert pruefe_vertrag(v, _profil("A-M3"))["bestanden"] is False


def test_verteilungsgrenze_kippt_den_test_trotz_gruener_einzelwerte():
    """Grundsatzdokumentation 9.15: die Verteilung urteilt mit.

    Jeder Einzelwert liegt in seiner Toleranz — die Verteilung ist
    trotzdem breiter, als die Abnahme zulaesst.
    """
    dk = KERN.zustand_am(TA).vx_mrv
    vertraege = [
        _vertrag(
            Pruefpunkt(TA, {"kVx_MRV": dk + 0.4}, ANLASS_UEBERNAHME),
            police_id=f"P{i}",
        )
        for i in (1, 2)
    ]
    sp = ziehe("vollbestand", ["P1", "P2"])
    locker = Kriterium(abs_tol=1.0, rel_tol=1e-9)
    ohne_grenze = _profil(grund=locker)
    assert pruefe_stichprobe(vertraege, sp, ohne_grenze)["test_bestanden"] is True

    mit_grenze = _profil(
        grund=Kriterium(abs_tol=1.0, rel_tol=1e-9, max_abs_residuum=0.1)
    )
    ergebnis = pruefe_stichprobe(vertraege, sp, mit_grenze)
    assert ergebnis["test_bestanden"] is False
    assert ergebnis["fehlgeschlagen"] == 0, "die Einzelwerte sind gruen"
    assert ergebnis["grenzbefunde"], "die Verteilung reisst die Grenze"


def test_abnahmegrenze_unter_dem_rundungsrauschen_wird_abgelehnt():
    """Eine Grenze unter einem halben Cent misst die Darstellung."""
    with pytest.raises(ProfilFehler, match="Rundungsrauschen"):
        _profil(grund=Kriterium(
            abs_tol=0.01, rel_tol=1e-9,
            max_abs_residuum=RUNDUNGSRAUSCHEN / 2,
        ))


def test_perzentilgrenze_ueber_der_maximalgrenze_ist_wirkungslos():
    with pytest.raises(ProfilFehler, match="kann das Maximum nicht"):
        Kriterium(abs_tol=0.01, rel_tol=1e-9,
                  max_abs_residuum=1.0, p95_abs_residuum=2.0)


def test_profil_ohne_stichprobenweite_traegt_keinen_beleg():
    with pytest.raises(ProfilFehler, match="Stichprobenweite"):
        _profil(weite="")


def test_unbekannter_test_wird_abgelehnt():
    with pytest.raises(ProfilFehler, match="unbekannter Test"):
        _profil(kennung="A-M9")


# --------------------------------------------------------------------------- #
# 5. Auswertung nach Anlass
# --------------------------------------------------------------------------- #


def test_residuen_werden_nach_anlass_getrennt_ausgewiesen():
    """Ein Residuum bei der Uebernahme und eines beim Ablauf sind zweierlei."""
    u = KERN.zustand_am(TA).vx_mrv
    f = KERN.zustand_am(TA + 12).vx_mrv
    v = _vertrag(
        Pruefpunkt(TA, {"kVx_MRV": u}, ANLASS_UEBERNAHME),
        Pruefpunkt(TA + 12, {"kVx_MRV": f - 0.3}, ANLASS_FORTSCHREIBUNG),
    )
    profil = _profil(grund=Kriterium(abs_tol=1.0, rel_tol=1e-9))
    ergebnis = pruefe_stichprobe([v], ziehe("vollbestand", ["P1"]), profil)
    nach = ergebnis["nach_anlass"]
    assert set(nach) == {"uebernahme", "fortschreibung"}
    assert nach["uebernahme"]["max_abs_residuum"] == pytest.approx(0.0)
    assert nach["fortschreibung"]["max_abs_residuum"] == pytest.approx(0.3)
    # Zusammengeworfen waere der Befund halb so gross erschienen.
    assert ergebnis["verteilung"]["anzahl_werte"] == 2


def test_profil_steht_im_ergebnis_und_traegt_den_beleg():
    """Ohne Weite und Kriterien im Ergebnis ist ein gruener Test nicht lesbar."""
    v = _vertrag(Pruefpunkt(TA, {"kVx_MRV": KERN.zustand_am(TA).vx_mrv},
                            ANLASS_UEBERNAHME))
    profil = _profil(weite="1 Fall je Vorfallart")
    ergebnis = pruefe_stichprobe([v], ziehe("vollbestand", ["P1"]), profil)
    assert ergebnis["profil"]["weite"] == "1 Fall je Vorfallart"
    assert ergebnis["profil"]["kennung"] == "A-M1"
    assert ergebnis["profil"]["grundtoleranz"]["abs_tol"] == ENG.abs_tol
