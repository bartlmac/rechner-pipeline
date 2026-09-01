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


# --------------------------------------------------------------------------- #
# 7. Korrekturschicht im Test (Grundsatzdokumentation 9, ADR-010)
# --------------------------------------------------------------------------- #


def _uebernommen(delta: float = -850.0, ta_jahr: int = 9):
    """Ein uebernommener Vertrag samt seiner verankerten Schicht."""
    from rechner_pipeline.bestand.migrationszugang import Uebernahme, uebernehmen

    prosp = KERN.verlaufszeile(ta_jahr).drx_bpfl
    e, = uebernehmen([
        Uebernahme(police_id=1, model_point=dict(MP),
                   monate_ta=12 * ta_jahr, dk_ist=prosp + delta)
    ])
    return e, prosp + delta, 12 * ta_jahr


def test_ohne_schicht_meldet_der_test_die_uebernahmedifferenz_als_fehler():
    """Der rohe Wertvergleich kann nicht anders — er kennt die Methode nicht."""
    _, geliefert, ta = _uebernommen()
    v = _vertrag(Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME))
    ergebnis = pruefe_vertrag(v, _profil())
    assert ergebnis["bestanden"] is False
    assert ergebnis["pruefungen"][0]["residuum"] == pytest.approx(850.0)


def test_mit_schicht_ist_die_uebernahmedifferenz_konstruktionsbedingt_null():
    """Das ist der Zugewinn: Der Test misst ab jetzt, was DANEBEN passiert.

    Am Verankerungszeitpunkt traegt die Schicht genau das Residuum. Was
    der Test dort noch findet, waere ein Fehler der Verankerung selbst.
    """
    e, geliefert, ta = _uebernommen()
    v = _vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        schicht=e.parameter, monate_ta=ta,
    )
    ergebnis = pruefe_vertrag(v, _profil())
    assert ergebnis["bestanden"] is True
    assert ergebnis["pruefungen"][0]["residuum"] == pytest.approx(0.0, abs=1e-9)


def test_die_schicht_wirkt_auch_am_naechsten_stichtag():
    """A-M1 prueft die Fortschreibung — die Schicht laeuft dort mit."""
    e, geliefert, ta = _uebernommen()
    fort_basis = KERN.verlaufszeile(ta // 12 + 1).drx_bpfl

    # Der Wert, den das System am naechsten Stichtag zeigt, liegt zwischen
    # der reinen Basis und dem gelieferten Stand: Die Schicht ist teilweise
    # abgebaut.
    v = _vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        Pruefpunkt(ta + 12, {"kVx_MRV": fort_basis}, ANLASS_FORTSCHREIBUNG),
        schicht=e.parameter, monate_ta=ta,
    )
    ergebnis = pruefe_vertrag(v, _profil())
    zweiter = ergebnis["pruefungen"][1]
    assert zweiter["system"] < fort_basis, "die Schicht ist negativ, senkt also"
    assert zweiter["system"] > fort_basis - 850.0, "sie ist teilweise abgebaut"


def test_schicht_ist_am_ablauf_exakt_null():
    """A-M2-Befund des zweiten Laufs (Police 7000586): Am Ablauftermin
    gilt tarifbedingt kVx_MRV(n) = Erlebensfallsumme — eine
    Fuehrungs-Korrektur hat dort nichts mehr zu verteilen
    (Terminalbedingung V_korr(n) = 0, 9.7). Mit einem Zahlungsgewicht
    auch im Ablaufjahr stand die Schicht dort noch auf rho x Basis(n).
    Der Punkt DAVOR muss die Schicht weiterhin tragen — sonst waere
    sie nur frueher abgeschaltet statt korrekt amortisiert."""
    e, geliefert, ta = _uebernommen()
    ablauf = 12 * KLV_DEFAULT.n
    ablaufleistung = KERN.verlaufszeile(KLV_DEFAULT.n).vx_mrv
    v = _vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        Pruefpunkt(ablauf, {"kVx_MRV": round(ablaufleistung, 2)},
                   ANLASS_VERLAUF),
        schicht=e.parameter, monate_ta=ta,
    )
    ergebnis = pruefe_vertrag(v, _profil())
    assert ergebnis["bestanden"], ergebnis["befunde"]
    am_ablauf = next(p for p in ergebnis["pruefungen"]
                     if p["monate"] == ablauf)
    assert am_ablauf["system"] == pytest.approx(ablaufleistung, abs=1e-9)
    # Zonen-Beleg: ein Jahr vor Ablauf wirkt die Schicht noch.
    vor_ablauf = 12 * (KLV_DEFAULT.n - 1)
    basis_vor = KERN.verlaufszeile(KLV_DEFAULT.n - 1).vx_mrv
    v2 = _vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        Pruefpunkt(vor_ablauf, {"kVx_MRV": round(basis_vor, 2)},
                   ANLASS_VERLAUF),
        schicht=e.parameter, monate_ta=ta,
    )
    p_vor = next(p for p in pruefe_vertrag(v2, _profil())["pruefungen"]
                 if p["monate"] == vor_ablauf)
    assert abs(p_vor["system"] - basis_vor) > 1.0


def test_schicht_ohne_verankerungszeitpunkt_faellt_hart_aus():
    """Die Schicht rechnet ab t_a — ohne den Zeitpunkt ist sie undefiniert."""
    e, geliefert, ta = _uebernommen()
    v = _vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        schicht=e.parameter,
    )
    with pytest.raises(AktuartestFehler, match="ohne monate_ta"):
        pruefe_vertrag(v, _profil())


def test_pruefpunkt_vor_der_verankerung_faellt_hart_aus():
    """Vor t_a gehoerte der Vertrag dem abgebenden Unternehmen."""
    e, geliefert, ta = _uebernommen()
    v = _vertrag(
        Pruefpunkt(ta - 12, {"kVx_MRV": 1.0}, ANLASS_UEBERNAHME),
        schicht=e.parameter, monate_ta=ta,
    )
    with pytest.raises(AktuartestFehler, match="VOR dem Verankerungszeitpunkt"):
        pruefe_vertrag(v, _profil())


def test_beitrag_bleibt_von_der_schicht_unberuehrt():
    """Die Schicht ist Deckungskapital, kein Vertragsmerkmal (9.10)."""
    e, geliefert, ta = _uebernommen()
    mit = _vertrag(
        Pruefpunkt(ta, {"BJB": KERN.gross_annual_premium()}, ANLASS_UEBERNAHME),
        schicht=e.parameter, monate_ta=ta,
    )
    ohne = _vertrag(
        Pruefpunkt(ta, {"BJB": KERN.gross_annual_premium()}, ANLASS_UEBERNAHME)
    )
    assert pruefe_vertrag(mit, _profil())["bestanden"]
    assert pruefe_vertrag(ohne, _profil())["bestanden"]


# --------------------------------------------------------------------------- #
# Herabsetzung (RED) — der Vorfall, dessen Wirkung im Parameter steht
# --------------------------------------------------------------------------- #


def test_red_rechnet_dDK_aus_dem_anteil():
    """Der Pruefwert der Herabsetzung ist die Wirkung des Zielverfahrens.

    Die Engine darf ihn nicht aus einem Zustandspaar ableiten: Wie weit
    der Vertrag geteilt wird, steht im Vorfall.
    """
    from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, reduziere

    jahr = 9
    erwartet = reduziere(KERN, jahr, 0.6, verfahren=PROSPEKTIV).d_dk
    vertrag = _vertrag(
        Pruefpunkt(12 * jahr, {"dDK": erwartet}, "RED", {"anteil": 0.6})
    )
    assert pruefe_vertrag(vertrag, _profil("A-M3"))["bestanden"] is True


def test_red_ohne_anteil_ist_harter_fehler():
    """Ein geratener Anteil waere eine erfundene Vergleichsgroesse."""
    vertrag = _vertrag(Pruefpunkt(12 * 9, {"dDK": -100.0}, "RED"))
    with pytest.raises(AktuartestFehler, match="parameter\\['anteil'\\]"):
        pruefe_vertrag(vertrag, _profil("A-M3"))


@pytest.mark.parametrize("anteil", [-0.1, 1.5, float("nan")])
def test_red_anteil_ausserhalb_null_bis_eins_faellt_aus(anteil):
    vertrag = _vertrag(
        Pruefpunkt(12 * 9, {"dDK": -100.0}, "RED", {"anteil": anteil})
    )
    with pytest.raises(AktuartestFehler, match="liegt nicht in"):
        pruefe_vertrag(vertrag, _profil("A-M3"))


def test_red_unterjaehrig_faellt_aus_solange_das_rumpfjahr_offen_ist():
    """Anders als Storno ist die Herabsetzung nur am Vertragsstichtag.

    Sie unterjaehrig zuzulassen hiesse, eine Rumpfjahr-Konvention still
    festzulegen (offener Punkt O-1).
    """
    vertrag = _vertrag(
        Pruefpunkt(12 * 9 + 3, {"dDK": -100.0}, "RED", {"anteil": 0.6})
    )
    with pytest.raises(AktuartestFehler, match="nur am Vertragsstichtag"):
        pruefe_vertrag(vertrag, _profil("A-M3"))


def test_anteil_eins_aendert_das_deckungskapital_nicht():
    """Der Randfall haelt fest, dass keine Reduktion auch keine Wirkung hat."""
    vertrag = _vertrag(
        Pruefpunkt(12 * 9, {"dDK": 0.0}, "RED", {"anteil": 1.0})
    )
    assert pruefe_vertrag(vertrag, _profil("A-M3"))["bestanden"] is True


# --------------------------------------------------------------------------- #
# Anfangszustand Herabsetzung (Kern 3.1.0): der geteilte Vertrag
# --------------------------------------------------------------------------- #


def _zweiteilung(monate: int, jahr: int = 8, anteil: float = 0.6):
    """Unabhaengige Nachrechnung aus Kern-Primitiven (ohne ReduzierterVertrag)."""
    from rechner_pipeline.kern.beitragsreduktion import reduziere

    r = reduziere(KERN, jahr, anteil)
    bfr_teil = r.vs_neu - anteil * r.vs_alt
    a, rest = divmod(monate, 12)
    satz = KERN.verlaufszeile(a).vx_bfr
    if rest:
        u = rest / 12.0
        satz = (1.0 - u) * satz + u * KERN.verlaufszeile(a + 1).vx_bfr
    return anteil * KERN.monatsreserve(monate).vx_mrv + bfr_teil * satz


def test_reduzierter_anfangszustand_bewertet_den_geteilten_vertrag():
    monate = 12 * 10
    erwartet_mrv = _zweiteilung(monate)
    erwartet_bjb = 0.6 * KERN.gross_annual_premium()
    v = _vertrag(
        Pruefpunkt(monate=monate,
                   erwartet={"kVx_MRV": round(erwartet_mrv, 2),
                             "BJB": round(erwartet_bjb, 2)},
                   anlass="uebernahme"),
        reduktion=(8, 0.6),
    )
    urteil = pruefe_vertrag(v, _profil(grund=Kriterium(abs_tol=0.01,
                                                       rel_tol=1e-9)))
    assert urteil["bestanden"], urteil["befunde"]


def test_reduzierter_anfangszustand_faellt_nicht_auf_den_unreduzierten_wert():
    """Mutationsfaenger: der unreduzierte kVx_MRV darf NICHT bestehen."""
    monate = 12 * 10
    v = _vertrag(
        Pruefpunkt(monate=monate,
                   erwartet={"kVx_MRV": round(KERN.monatsreserve(monate).vx_mrv, 2)},
                   anlass="uebernahme"),
        reduktion=(8, 0.6),
    )
    urteil = pruefe_vertrag(v, _profil())
    assert not urteil["bestanden"]


def test_ddk_der_beitragsfreistellung_eines_reduzierten_vertrags():
    """PEX auf Alt-RED: verlustfreie Umwandlung des GETEILTEN Vertrags."""
    monate = 12 * 10
    v = _vertrag(
        Pruefpunkt(monate=monate, erwartet={"dDK": 0.0}, anlass="PEX"),
        reduktion=(8, 0.6),
    )
    urteil = pruefe_vertrag(v, _profil(kennung="A-M3"))
    assert urteil["bestanden"], urteil["befunde"]


def test_reduktion_mit_scheiben_oder_pex_zustand_faellt_hart():
    with pytest.raises(AktuartestFehler, match="Kombination"):
        pruefe_vertrag(_vertrag(
            Pruefpunkt(monate=120, erwartet={"kVx_MRV": 1.0},
                       anlass="uebernahme"),
            reduktion=(8, 0.6), scheiben=((9, 5000.0),),
        ), _profil())
    with pytest.raises(AktuartestFehler, match="Kombination"):
        pruefe_vertrag(_vertrag(
            Pruefpunkt(monate=120, erwartet={"kVx_MRV": 1.0},
                       anlass="uebernahme"),
            reduktion=(8, 0.6), beitragsfrei_seit_jahr=9,
        ), _profil())


def test_pruefpunkt_vor_der_reduktion_ist_widerspruechlich():
    with pytest.raises(AktuartestFehler, match="VOR der Herabsetzung"):
        pruefe_vertrag(_vertrag(
            Pruefpunkt(monate=12 * 5, erwartet={"kVx_MRV": 1.0},
                       anlass="uebernahme"),
            reduktion=(8, 0.6),
        ), _profil())


def test_scheiben_vertrag_traegt_den_beitrag_beider_teile():
    """Der gelieferte Jahresbeitrag eines Dynamik-Vertrags enthaelt die
    Scheibenbeitraege — Regel der Bestandsfuehrung, unabhaengig
    nachgerechnet aus den Teil-Modellpunkten."""
    from rechner_pipeline.kern import erhoehungs_scheibe

    erh_jahr, erh_summe = 6, 20000.0
    scheibe = Rechenkern(erhoehungs_scheibe(KLV_DEFAULT, erh_jahr, erh_summe))
    erwartet = KERN.gross_annual_premium() + scheibe.gross_annual_premium()
    monate = 12 * 9
    v = _vertrag(
        Pruefpunkt(monate=monate,
                   erwartet={"BJB": round(erwartet, 2)},
                   anlass="uebernahme"),
        scheiben=((erh_jahr, erh_summe),),
    )
    urteil = pruefe_vertrag(v, _profil(grund=Kriterium(abs_tol=0.01,
                                                       rel_tol=1e-9)))
    assert urteil["bestanden"], urteil["befunde"]

    # Mutationsfaenger: der Grundbeitrag allein darf NICHT bestehen.
    v2 = _vertrag(
        Pruefpunkt(monate=monate,
                   erwartet={"BJB": round(KERN.gross_annual_premium(), 2)},
                   anlass="uebernahme"),
        scheiben=((erh_jahr, erh_summe),),
    )
    assert not pruefe_vertrag(v2, _profil())["bestanden"]


def test_red_ddk_folgt_dem_verfahren_des_falls():
    """Unabhaengige Kontrolle gegen die Formel der Aktuariellen Notiz
    2026/04: bei Teilkuendigung ist dDK = -StoAb * (1 - f); das
    Zielverfahren prospektiv ist verlustfrei (dDK = 0)."""
    jahr, f = 10, 0.6
    stoab = KERN.verlaufszeile(jahr).stoab
    punkt = Pruefpunkt(monate=12 * jahr, erwartet={"dDK": 0.0},
                       anlass="RED", parameter={"anteil": f})

    prospektiv = pruefe_vertrag(_vertrag(punkt), _profil(kennung="A-M3"))
    assert prospektiv["bestanden"], prospektiv["befunde"]

    erwartet_abzug = -stoab * (1 - f)
    punkt_abzug = Pruefpunkt(monate=12 * jahr,
                             erwartet={"dDK": round(erwartet_abzug, 2)},
                             anlass="RED", parameter={"anteil": f})
    mit_abzug = pruefe_vertrag(
        _vertrag(punkt_abzug), _profil(kennung="A-M3"),
        red_verfahren="mit_abzug")
    assert mit_abzug["bestanden"], mit_abzug["befunde"]


def test_stichprobe_belegt_das_red_verfahren():
    from rechner_pipeline.qa.stichprobe import Stichprobe

    v = _vertrag(Pruefpunkt(
        monate=120,
        erwartet={"kVx_MRV": round(KERN.zustand_am(120).vx_mrv, 2)},
        anlass="uebernahme"))
    probe = Stichprobe(profil="vollbestand", parameter={},
                       police_ids=("P1",), grundgesamtheit=1)
    ergebnis = pruefe_stichprobe([v], probe, _profil(
        grund=Kriterium(abs_tol=0.01, rel_tol=1e-9)),
        red_verfahren="mit_abzug")
    assert ergebnis["red_verfahren"] == "mit_abzug"


# --------------------------------------------------------------------------- #
# Ersetzter Wertvergleich: Plausibilitaet statt Vergleich
# --------------------------------------------------------------------------- #

from rechner_pipeline.qa.aktuarieller_test import (
    KRITERIUM_PLAUSIBILITAET,
    KRITERIUM_VERGLEICH,
    PLAUSIBILITAET,
)

GRUND = "Altrechnung nicht rekonstruierbar (Auskunft der Zulieferung)"


def _rkw_punkt(monate=120, rkw=None, dk=None):
    zeile = KERN.zustand_am(monate)
    return Pruefpunkt(
        monate=monate,
        erwartet={"kVx_MRV": round(dk if dk is not None else zeile.vx_mrv, 2),
                  "RKW": round(rkw if rkw is not None else zeile.rkw, 2)},
        anlass="uebernahme",
    )


def test_plausibilitaet_ersetzt_den_wertvergleich_im_korridor():
    """Ein gelieferter Rueckkaufswert, der den centgenauen Vergleich
    reisst, aber im Korridor des Tarifwerks liegt, besteht — und wird
    als ersetzter Vergleich ausgewiesen."""
    zeile = KERN.zustand_am(120)
    daneben = round(zeile.rkw + 50.0, 2)       # 50 EUR mehr, im Korridor
    v = _vertrag(_rkw_punkt(rkw=daneben), plausibilitaet={"RKW": GRUND})
    urteil = pruefe_vertrag(v, _profil())
    assert urteil["bestanden"], urteil["befunde"]
    rkw = next(p for p in urteil["pruefungen"] if p["groesse"] == "RKW")
    assert rkw["kriterium"] == KRITERIUM_PLAUSIBILITAET
    assert rkw["erwartet_im_korridor"] and rkw["begruendung"] == GRUND
    # Das Deckungskapital bleibt im WERTVERGLEICH — die Ausnahme gilt
    # genau der benannten Groesse.
    dk = next(p for p in urteil["pruefungen"] if p["groesse"] == "kVx_MRV")
    assert dk["kriterium"] == KRITERIUM_VERGLEICH


def test_plausibilitaet_faengt_einen_unmoeglichen_systemwert():
    """Kein Freibrief: ein Systemwert ausserhalb des Korridors faellt."""
    zeile = KERN.zustand_am(120)
    v = _vertrag(_rkw_punkt(), plausibilitaet={"RKW": GRUND})
    urteil = pruefe_vertrag(v, _profil())
    assert urteil["bestanden"]
    # Korridor ist [DK - stoab_max, DK]; ein Systemwert darunter faellt.
    korridor = next(p for p in urteil["pruefungen"]
                    if p["groesse"] == "RKW")["korridor"]
    assert korridor[0] == pytest.approx(
        zeile.vx_mrv - KLV_DEFAULT.stoab_max, abs=0.02)
    assert korridor[1] == pytest.approx(zeile.vx_mrv, abs=0.02)


def test_plausibilitaet_prueft_auch_den_gelieferten_wert():
    """Die Ausnahme trifft beide Seiten: ein gelieferter Wert ausserhalb
    des Korridors ist ein Befund GEGEN DIE LIEFERUNG."""
    zeile = KERN.zustand_am(120)
    unmoeglich = round(zeile.vx_mrv - 5 * KLV_DEFAULT.stoab_max, 2)
    v = _vertrag(_rkw_punkt(rkw=unmoeglich), plausibilitaet={"RKW": GRUND})
    urteil = pruefe_vertrag(v, _profil())
    assert not urteil["bestanden"]
    assert any("GELIEFERTER Wert" in b for b in urteil["befunde"]), urteil


def test_groesse_ohne_plausibilitaetsregel_faellt_hart():
    """Nur wo eine Regel des Tarifwerks existiert, laesst sich der
    Wertvergleich ersetzen — sonst waere es ein Weg, jeden Fehlschlag
    wegzudefinieren."""
    assert "dDK" not in PLAUSIBILITAET
    v = _vertrag(_rkw_punkt(), plausibilitaet={"dDK": GRUND})
    with pytest.raises(AktuartestFehler, match="keine Plausibilitaetsregel"):
        pruefe_vertrag(v, _profil())


def test_kvx_mrv_plausibilitaet_ohne_kandidaten_faellt_hart():
    """kVx_MRV und BJB haben ihre Regel NUR ueber die belegte
    Kandidatenmenge — ohne sie bleibt die Groesse im Wertvergleich,
    ein Antrag ist ein Auftragsfehler (Massstab des Aktuars: kein
    Pauschal-informativ)."""
    assert "kVx_MRV" in PLAUSIBILITAET and "BJB" in PLAUSIBILITAET
    v = _vertrag(_rkw_punkt(), plausibilitaet={"kVx_MRV": GRUND})
    with pytest.raises(AktuartestFehler, match="bleibt im Wertvergleich"):
        pruefe_vertrag(v, _profil())


def test_plausibilitaet_ohne_begruendung_faellt_hart():
    v = _vertrag(_rkw_punkt(), plausibilitaet={"RKW": "   "})
    with pytest.raises(AktuartestFehler, match="ohne Begruendung"):
        pruefe_vertrag(v, _profil())


def test_ersetzte_vergleiche_verzerren_die_residuum_verteilung_nicht():
    """Ein Residuum ohne gemeinsamen Massstab gehoert nicht in die
    Verteilung — sonst kippten die Abnahmegrenzen an einer Groesse, die
    gar nicht verglichen wurde."""
    from rechner_pipeline.qa.stichprobe import Stichprobe

    zeile = KERN.zustand_am(120)
    v = _vertrag(_rkw_punkt(rkw=round(zeile.rkw + 50.0, 2)),
                 plausibilitaet={"RKW": GRUND})
    probe = Stichprobe(profil="vollbestand", parameter={},
                       police_ids=("P1",), grundgesamtheit=1)
    ergebnis = pruefe_stichprobe([v], probe, _profil())
    assert ergebnis["test_bestanden"], ergebnis["grenzbefunde"]
    assert ergebnis["verteilung"]["max_abs_residuum"] < 0.02
    assert ergebnis["plausibilitaets_pruefungen"] == 1
    assert ergebnis["plausibilitaet_statt_vergleich"] == {"P1": {"RKW": GRUND}}


def test_gate_rechnet_die_plausibilitaet_nach_und_faengt_manipulation():
    """Ein von Hand auf gruen gesetztes Urteil faellt im Gate."""
    from rechner_pipeline.gates.aktuartest import test_fehler
    from rechner_pipeline.qa.stichprobe import Stichprobe

    zeile = KERN.zustand_am(120)
    unmoeglich = round(zeile.vx_mrv - 5 * KLV_DEFAULT.stoab_max, 2)
    v = _vertrag(_rkw_punkt(rkw=unmoeglich), plausibilitaet={"RKW": GRUND})
    probe = Stichprobe(profil="vollbestand", parameter={},
                       police_ids=("P1",), grundgesamtheit=1)
    ergebnis = pruefe_stichprobe([v], probe, _profil())
    assert not ergebnis["test_bestanden"]
    assert test_fehler(ergebnis) == []

    # Manipulation: das rote Einzelurteil auf gruen drehen.
    import copy
    gefaelscht = copy.deepcopy(ergebnis)
    for p in gefaelscht["vertraege"][0]["pruefungen"]:
        if p["groesse"] == "RKW":
            p["ok"] = True
            p["erwartet_im_korridor"] = True
    gefaelscht["vertraege"][0]["befunde"] = []
    gefaelscht["vertraege"][0]["bestanden"] = True
    befunde = test_fehler(gefaelscht)
    assert any("Korridor" in f for f in befunde), befunde


class TestKandidatenKorridor:
    """Korridor aus der Tarifformel ueber die belegte Kandidatenmenge.

    Zweiter Plausibilitaets-Befund des zweiten Baldrian-Laufs: Der
    generische Storno-Bound ist fuer Vertraege mit UNBEKANNTEM
    Herabsetzungsanteil ein Korridor um eine Vermutung (oft exakt
    stoab_max breit, teils auf einen Punkt entartet). Kennt das
    Tarifwerk nur endlich viele Stufen (belegte Auskunft), ist der
    zulaessige Bereich das Intervall der Kandidaten-Ergebnisse —
    dieselbe ReduzierterVertrag-Rechnung, je Kandidat statt einmal.
    """

    KANDIDATEN = (0.50, 0.60, 0.75)
    JAHR, MONATE = 10, 144

    def _kandidaten_werte(self, groesse):
        from rechner_pipeline.kern.beitragsreduktion import (
            ReduzierterVertrag,
        )

        aus = []
        for f in self.KANDIDATEN:
            rv = ReduzierterVertrag.nach(KERN, self.JAHR, f)
            if groesse == "BJB":
                aus.append(rv.bjb(self.MONATE))
            else:
                m = rv.monatsreserve(self.MONATE)
                aus.append(m.vx_mrv if groesse == "kVx_MRV" else m.rkw)
        return aus

    def _vertrag_mit_kandidaten(self, erwartet):
        return _vertrag(
            Pruefpunkt(monate=self.MONATE, erwartet=erwartet,
                       anlass="uebernahme"),
            reduktion=(self.JAHR, 0.60),
            reduktion_kandidaten=self.KANDIDATEN,
            plausibilitaet={g: GRUND for g in erwartet},
        )

    def test_korridor_ist_intervall_der_kandidaten_rechnungen(self):
        """Fuer jede der drei Groessen: Der Beleg-Korridor ist exakt
        [min, max] der unabhaengig nachgerechneten Kandidaten-Werte,
        und ein Lieferwert auf einem Kandidaten besteht."""
        erwartet = {}
        korridore = {}
        for groesse in ("kVx_MRV", "RKW", "BJB"):
            werte = self._kandidaten_werte(groesse)
            # Zonen-Beleg: die Kandidaten unterscheiden sich wirklich,
            # sonst pruefte der Test ein entartetes Intervall.
            assert max(werte) - min(werte) > 1.0
            korridore[groesse] = (min(werte), max(werte))
            erwartet[groesse] = round(werte[0], 2)  # Kandidat 0.50
        urteil = pruefe_vertrag(
            self._vertrag_mit_kandidaten(erwartet), _profil())
        assert urteil["bestanden"], urteil["befunde"]
        for p in urteil["pruefungen"]:
            assert p["kriterium"] == KRITERIUM_PLAUSIBILITAET
            unten, oben = korridore[p["groesse"]]
            assert p["korridor"][0] == pytest.approx(unten)
            assert p["korridor"][1] == pytest.approx(oben)

    def test_lieferwert_ausserhalb_der_kandidatenmenge_faellt(self):
        """Kein Freibrief: Ein gelieferter Wert, der mit KEINEM
        Kandidaten vertraeglich ist, ist ein Befund gegen die
        Lieferung."""
        werte = self._kandidaten_werte("RKW")
        daneben = round(min(werte) - 500.0, 2)
        urteil = pruefe_vertrag(
            self._vertrag_mit_kandidaten({"RKW": daneben}), _profil())
        assert not urteil["bestanden"]
        assert any("GELIEFERTER Wert" in b for b in urteil["befunde"])

    def test_kandidaten_ohne_reduktion_fallen_hart(self):
        v = _vertrag(_rkw_punkt(),
                     reduktion_kandidaten=self.KANDIDATEN)
        with pytest.raises(AktuartestFehler,
                           match="ohne Herabsetzungs-Anfangszustand"):
            pruefe_vertrag(v, _profil())

    def test_ein_kandidat_spannt_keinen_korridor(self):
        v = _vertrag(
            Pruefpunkt(monate=self.MONATE, erwartet={"RKW": 1.0},
                       anlass="uebernahme"),
            reduktion=(self.JAHR, 0.60),
            reduktion_kandidaten=(0.60, 0.60),
            plausibilitaet={"RKW": GRUND},
        )
        with pytest.raises(AktuartestFehler, match="kein Korridor"):
            pruefe_vertrag(v, _profil())

    def test_rkw_ohne_kandidaten_behaelt_den_tarifwerks_bound(self):
        """Der Lauf-1-Tatbestand bleibt: Zustand bekannt, nur die
        Abzugskonvention der Quelle weicht ab — dort gilt weiter
        [kVx_MRV - stoab_max, kVx_MRV]."""
        zeile = KERN.zustand_am(120)
        v = _vertrag(_rkw_punkt(), plausibilitaet={"RKW": GRUND})
        urteil = pruefe_vertrag(v, _profil())
        korridor = next(p for p in urteil["pruefungen"]
                        if p["groesse"] == "RKW")["korridor"]
        assert korridor[0] == pytest.approx(
            zeile.vx_mrv - KLV_DEFAULT.stoab_max, abs=0.02)
        assert korridor[1] == pytest.approx(zeile.vx_mrv, abs=0.02)


def test_die_zweitverankerung_traegt_das_konventionsresiduum_getrennt():
    """9.13, Entscheidung E2 2026-08-31: R_conv wird separat erfasst.

    Aufbau: Am Verankerungszeitpunkt t_a heilt die hist-Schicht die
    Uebernahmedifferenz; am Migrationsstichtag t_0 (ein Jahr spaeter)
    bleibt eine kleine, SYSTEMATISCHE Konventionsdifferenz. Ohne conv-
    Schicht ist sie ein Befund; mit ihr ist der Punkt konstruktionsbedingt
    getroffen -- und die hist-Schicht blieb unangetastet, denn die beiden
    Residuen werden nie vermischt.
    """
    from rechner_pipeline.bestand.migrationszugang import Uebernahme, uebernehmen

    e, geliefert, ta = _uebernommen()
    t0 = ta + 12
    basis_t0 = KERN.verlaufszeile(t0 // 12).drx_bpfl
    hist_wert_t0 = pruefe_vertrag(_vertrag(
        Pruefpunkt(t0, {"kVx_MRV": basis_t0}, ANLASS_FORTSCHREIBUNG),
        schicht=e.parameter, monate_ta=ta,
    ), _profil())["pruefungen"][0]["system"]

    delta_conv = 12.5
    geliefert_t0 = hist_wert_t0 + delta_conv
    # Die Zweitverankerung nutzt denselben Operator, nur als conv-Schicht
    # am t_0 (delta klein und positiv -- eine Rundungskonvention, kein
    # Historienfehler).
    e_conv, = uebernehmen([
        Uebernahme(police_id=1, model_point=dict(MP),
                   monate_ta=t0,
                   dk_ist=KERN.verlaufszeile(t0 // 12).drx_bpfl + delta_conv)
    ])
    import dataclasses

    conv = dataclasses.replace(e_conv.parameter, schichttyp="conv")

    ohne = pruefe_vertrag(_vertrag(
        Pruefpunkt(t0, {"kVx_MRV": geliefert_t0}, ANLASS_FORTSCHREIBUNG),
        schicht=e.parameter, monate_ta=ta,
    ), _profil())
    # Residuum = System - erwartet: das System liegt um die
    # Konventionsdifferenz UNTER dem gelieferten Wert.
    assert ohne["pruefungen"][0]["residuum"] == pytest.approx(-delta_conv)

    mit = pruefe_vertrag(_vertrag(
        Pruefpunkt(t0, {"kVx_MRV": geliefert_t0}, ANLASS_FORTSCHREIBUNG),
        schicht=e.parameter, monate_ta=ta,
        schicht_conv=conv, monate_t0=t0,
    ), _profil())
    assert mit["pruefungen"][0]["residuum"] == pytest.approx(0.0, abs=1e-9)


def test_vertauschte_schichttypen_fallen_hart():
    """hist gehoert nach schicht, conv nach schicht_conv -- nie umgekehrt.

    Wer das Konventionsresiduum in das hist-Feld legt, vermischt die
    beiden Residuen, die 9.13 ausdruecklich trennt -- und die primaere
    Qualitaetskennzahl R_hist waere still verfaelscht.
    """
    import dataclasses

    e, geliefert, ta = _uebernommen()
    conv = dataclasses.replace(e.parameter, schichttyp="conv")

    with pytest.raises(AktuartestFehler) as exc:
        pruefe_vertrag(_vertrag(
            Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
            schicht=conv, monate_ta=ta,
        ), _profil())
    assert "R_hist" in str(exc.value)

    with pytest.raises(AktuartestFehler) as exc:
        pruefe_vertrag(_vertrag(
            Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
            schicht=e.parameter, monate_ta=ta,
            schicht_conv=e.parameter, monate_t0=ta,
        ), _profil())
    assert "'conv'" in str(exc.value)


def test_zweitverankerung_ohne_t0_faellt_hart():
    import dataclasses

    e, geliefert, ta = _uebernommen()
    conv = dataclasses.replace(e.parameter, schichttyp="conv")
    with pytest.raises(AktuartestFehler) as exc:
        pruefe_vertrag(_vertrag(
            Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
            schicht=e.parameter, monate_ta=ta,
            schicht_conv=conv,
        ), _profil())
    assert "monate_t0" in str(exc.value)


def test_das_ergebnis_traegt_den_pruefauftrag_zum_nachrechnen():
    """Ein Testergebnis ohne seine Eingaben ist eine Behauptung.

    Der Entscheid soll die Vertragswerte NACHRECHNEN koennen — hier
    geschieht genau das: Aus dem persistierten Auftrag wird der Kern neu
    gebaut, und der Systemwert des Pruefpunkts faellt identisch.
    """
    from rechner_pipeline.kern import Rechenkern
    from rechner_pipeline.kern.model_point import ModelPoint

    v = _vertrag(Pruefpunkt(TA, {"kVx_MRV": KERN.zustand_am(TA).vx_mrv},
                            ANLASS_UEBERNAHME))
    ergebnis = pruefe_vertrag(v, _profil())
    auftrag = ergebnis["auftrag"]

    nachgebaut = Rechenkern(ModelPoint(**auftrag["model_point"]))
    p = ergebnis["pruefungen"][0]
    assert nachgebaut.zustand_am(p["monate"]).vx_mrv == p["system"]

    # Der Auftrag ist vollstaendig, nicht nur der Modellpunkt.
    assert auftrag["scheiben"] == []
    assert auftrag["monate_ta"] is None
    assert auftrag["schicht"] is None
    assert sorted(auftrag["model_point"]) == sorted(auftrag["model_point"])

    # Mit Schicht steht ihr Beleg im Auftrag.
    e, geliefert, ta = _uebernommen()
    mit = pruefe_vertrag(_vertrag(
        Pruefpunkt(ta, {"kVx_MRV": geliefert}, ANLASS_UEBERNAHME),
        schicht=e.parameter, monate_ta=ta,
    ), _profil())
    assert mit["auftrag"]["monate_ta"] == ta
    assert mit["auftrag"]["schicht"]["rho"] == e.parameter.rho


class TestScheibenGamma1Regel:
    """Die gamma1-Regel der Erhoehungsscheiben ist eine Tarifwerks-
    Eigenschaft der LIEFERUNG, keine Kern-Konstante — gefunden im
    zweiten Baldrian-Lauf als bit-stabiler BJB-Fehlbetrag ueber beide
    Stichtage (Aktuars-Befund): Die Quelle der zweiten Lieferung rechnet
    jede Scheibe mit der VOLLEN Beitragsformel, der Kern rechnete stur
    die GrundVS-Regel der ersten."""

    def test_flag_schaltet_die_volle_formel_und_default_bleibt_alt(self):
        import dataclasses

        from rechner_pipeline.kern import KLV_DEFAULT
        from rechner_pipeline.kern.rechenkern import (
            Rechenkern,
            erhoehungs_scheibe,
        )

        alt = erhoehungs_scheibe(KLV_DEFAULT, 5, 4000.0)
        voll = erhoehungs_scheibe(KLV_DEFAULT, 5, 4000.0,
                                  gamma1_uebernehmen=True)
        assert alt.gamma1 == 0.0
        assert voll.gamma1 == KLV_DEFAULT.gamma1 > 0.0
        # Unabhaengige Referenz: die volle Scheibe ist exakt der direkt
        # konstruierte Modellpunkt mit gamma1 — kein eigener Formelpfad.
        direkt = dataclasses.replace(
            KLV_DEFAULT, x=KLV_DEFAULT.x + 5, n=KLV_DEFAULT.n - 5,
            t=KLV_DEFAULT.t - 5, sum_insured=4000.0)
        assert Rechenkern(voll).gross_annual_premium() == pytest.approx(
            Rechenkern(direkt).gross_annual_premium(), abs=1e-9)
        assert Rechenkern(voll).gross_annual_premium() > (
            Rechenkern(alt).gross_annual_premium())

    def test_engine_rechnet_bjb_je_nach_lieferungsregel(self):
        """Derselbe Auftrag, nur das Flag verschieden: Der BJB-Systemwert
        muss sich exakt um den gamma1-Beitragsanteil der Scheibe
        unterscheiden (Mutation 'Flag wird ignoriert' faellt)."""
        import dataclasses

        from rechner_pipeline.kern import KLV_DEFAULT
        from rechner_pipeline.kern.rechenkern import Rechenkern
        from rechner_pipeline.qa.aktuarieller_test import (
            Pruefpunkt,
            Vertragspruefung,
            _kerne,
        )

        mp = KLV_DEFAULT
        basis = dict(
            police_id="X", model_point=dataclasses.asdict(mp),
            historientyp="dynamik",
            punkte=(Pruefpunkt(monate=120, erwartet={"BJB": 1.0},
                               anlass="uebernahme"),),
            scheiben=((5, 4000.0),),
        )
        ohne = Vertragspruefung(**basis)
        mit = Vertragspruefung(**basis, scheiben_mit_gamma1=True)
        g0, s0 = _kerne(ohne, mp)
        g1, s1 = _kerne(mit, mp)
        bjb_ohne = g0.gross_annual_premium() + s0[0][1].gross_annual_premium()
        bjb_mit = g1.gross_annual_premium() + s1[0][1].gross_annual_premium()
        erwartete_differenz = (
            Rechenkern(dataclasses.replace(
                mp, x=mp.x + 5, n=mp.n - 5, t=mp.t - 5, sum_insured=4000.0)
            ).gross_annual_premium()
            - Rechenkern(dataclasses.replace(
                mp, x=mp.x + 5, n=mp.n - 5, t=mp.t - 5, sum_insured=4000.0,
                gamma1=0.0)).gross_annual_premium())
        assert bjb_mit - bjb_ohne == pytest.approx(erwartete_differenz,
                                                   abs=1e-9)
        assert erwartete_differenz > 0.0


class TestStoabJeBausteinRegel:
    """WO die Stornoabschlag-Grenzen greifen, ist eine Tarifwerks-
    Eigenschaft der LIEFERUNG — gefunden im zweiten Baldrian-Lauf als
    RKW-Residuen in Vielfachen der Grenzbetraege (Aktuars-Befund): Die
    Quelle erhebt den Abzug je BAUSTEIN gesondert (Bedingungswerk
    Ziffer 4), der Kern klemmte stur einmal je Vertrag."""

    def test_engine_rechnet_rkw_je_nach_lieferungsregel(self):
        """Derselbe Auftrag, nur das Flag verschieden: Der RKW-Systemwert
        muss je Baustein exakt die Summe der Einzel-Monatsreserven
        treffen (unabhaengige Kontrollrechnung) und sich vom
        vertragsweiten Wert unterscheiden (Mutation 'Flag wird
        ignoriert' faellt)."""
        import dataclasses

        from rechner_pipeline.kern import KLV_DEFAULT
        from rechner_pipeline.kern.rechenkern import (
            Rechenkern,
            erhoehungs_scheibe,
        )
        from rechner_pipeline.qa.aktuarieller_test import (
            Pruefpunkt,
            Vertragspruefung,
            _system_werte,
        )

        mp = KLV_DEFAULT
        monate = 12 * 22 + 5  # DR-sensitive Zone: Grenzen unterscheidbar
        basis = dict(
            police_id="X", model_point=dataclasses.asdict(mp),
            historientyp="dynamik",
            punkte=(Pruefpunkt(monate=monate, erwartet={"RKW": 1.0},
                               anlass="uebernahme"),),
            scheiben=((8, 5000.0),),
        )
        p = basis["punkte"][0]
        je_vertrag = _system_werte(Vertragspruefung(**basis), mp, p)
        je_baustein = _system_werte(
            Vertragspruefung(**basis, stoab_je_baustein=True), mp, p)

        grund = Rechenkern(mp).monatsreserve(monate)
        scheibe = Rechenkern(
            erhoehungs_scheibe(mp, 8, 5000.0)).monatsreserve(monate - 12 * 8)
        assert je_baustein["RKW"] == pytest.approx(grund.rkw + scheibe.rkw)
        assert je_baustein["RKW"] != pytest.approx(
            je_vertrag["RKW"], rel=1e-6)


def _zustandslos_fixture():
    """Eine reduziert-Police, deren Anfangszustand nicht ableitbar war
    (leere anfangszustaende) — der Serie+RED-Fall des zweiten Laufs."""
    import pandas as pd

    from rechner_pipeline.kern import KLV_DEFAULT

    import dataclasses as dc
    felder = dc.asdict(KLV_DEFAULT)
    from rechner_pipeline.models.bestand import GENERATION_FIELDS

    @dc.dataclass
    class _Zelle:
        auspraegungen: dict
        model_point: dict

    @dc.dataclass
    class _Spez:
        zellen: list

    spez = _Spez(zellen=[_Zelle({}, {
        f: felder[f] for f in GENERATION_FIELDS})])
    bestand = pd.DataFrame([{
        "police_id": 7000717, "sum_insured": felder["sum_insured"],
        "entry_age": felder["x"], "duration": felder["n"],
        "premium_duration": felder["t"], "zahlweise": felder["zw"],
        "sex": felder["sex"],
        "insurance_start": pd.Timestamp("2016-01-01"),
    }])
    lieferung = {"vertraege": [{
        "police_id": "7000717", "historientyp": "reduziert",
        "monate_ta": 120, "beitragsfrei_seit_jahr": None,
        "punkte": [{"monate": 120, "anlass": "uebernahme",
                    "erwartet": {"BJB": 1.0}}],
    }]}
    return lieferung, bestand, spez


def test_quell_komponenten_skalieren_die_rundungstoleranz():
    """Die zwei letzten A-M1-Fehlschlaege des zweiten Laufs (7000061,
    7000977): beitragsfrei uebernommene ERH-Serien, deren Ein-Punkt-
    Inversion die Bausteine der Quelle kollabiert (scheiben leer,
    komponenten=1) — der gelieferte kVx_MRV bleibt aber die Summe von
    k je fuer sich gerundeten Baustein-Werten. Die QUELLSEITIGE
    Komponentenzahl skaliert deshalb die Rundungstoleranz — dieselbe
    hergeleitete Fehlerfortpflanzung wie bei den Scheiben-Vertraegen,
    keine Ermessens-Weitung."""
    a0, monate = 8, 120
    basis = dict(beitragsfrei_seit_jahr=a0)
    probe = pruefe_vertrag(_vertrag(
        Pruefpunkt(monate=monate, erwartet={"kVx_MRV": 1.0},
                   anlass="uebernahme"), **basis), _profil())
    system = next(p["system"] for p in probe["pruefungen"])
    # Residuum sicher ueber der Grundtoleranz (0,01) und unter der
    # 5-Komponenten-Toleranz (0,01 + 4 x 0,005 = 0,03).
    erwartet = round(system, 2) + 0.02
    punkt = Pruefpunkt(monate=monate, erwartet={"kVx_MRV": erwartet},
                       anlass="uebernahme")
    ohne = pruefe_vertrag(_vertrag(punkt, **basis), _profil())
    assert not ohne["bestanden"]
    mit = pruefe_vertrag(
        _vertrag(punkt, **basis, quell_komponenten=5), _profil())
    assert mit["bestanden"], mit["befunde"]
    assert mit["komponenten"] == 5
    assert mit["auftrag"]["quell_komponenten"] == 5
    with pytest.raises(AktuartestFehler, match="mindestens einer"):
        pruefe_vertrag(_vertrag(punkt, **basis, quell_komponenten=0),
                       _profil())


def test_auftragsbau_weist_vorgeschichte_ohne_zustand_aus():
    """20 von 25 reduziert-Policen liefen im zweiten Lauf ZUSTANDSLOS in
    den Wertvergleich (Zustandsableitung scheiterte nur mit stderr-
    Warnung) und urteilten auf einer falschen Welt. Ein Vertrag mit
    Vorgeschichte, aber ohne ableitbaren Anfangszustand, ist kein
    Pruefauftrag — die Luecke wird im Rueckgabewert AUSGEWIESEN (das
    Verhalten der ersten Lieferung — sichtbar rot statt still — bleibt;
    neu ist, dass der Beleg die Ursache traegt statt nur stderr)."""
    from rechner_pipeline.gates.aktuartest_lauf import baue_auftraege

    lieferung, bestand, spez = _zustandslos_fixture()
    auftraege, _ausgelassen, zustandslos = baue_auftraege(
        lieferung, bestand, spez, auspraegungen_je_police={},
        anfangszustaende={})
    assert zustandslos == ["7000717"]
    assert len(auftraege) == 1


def test_auftragsbau_verwirft_plausibilitaet_ohne_zustand_ausgewiesen():
    """Die Vorfallart-Reichweite eines Plausibilitaets-Belegs trifft
    auch Policen ohne ableitbaren Anfangszustand. Dort ersetzt der
    Beleg nichts (Systemwert = Stammwelt, Kandidaten-Regeln brauchen
    den Herabsetzungszustand) — der Antrag wird VERWORFEN statt eines
    Auftrags, den die Engine-Wache hart abweist: Im zweiten Lauf starb
    daran der komplette A-M1 statt der rechenbaren Punkte."""
    from rechner_pipeline.gates.aktuartest_lauf import baue_auftraege

    lieferung, bestand, spez = _zustandslos_fixture()
    auftraege, _ausgelassen, zustandslos = baue_auftraege(
        lieferung, bestand, spez, auspraegungen_je_police={},
        anfangszustaende={},
        plausibilitaet={"7000717": {"kVx_MRV": GRUND, "BJB": GRUND}},
        red_anteil_kandidaten=(0.50, 0.60, 0.75))
    assert zustandslos == ["7000717"]
    assert auftraege[0].plausibilitaet == {}
    assert auftraege[0].reduktion_kandidaten == ()
    # Der Auftrag ist engine-vertraeglich: kein AktuartestFehler, die
    # Police faellt im Wertvergleich sichtbar rot statt den Lauf zu
    # brechen.
    urteil = pruefe_vertrag(auftraege[0], _profil())
    assert not urteil["bestanden"]
    assert all(p["kriterium"] == KRITERIUM_VERGLEICH
               for p in urteil["pruefungen"])


def test_auftragsbau_verwirft_plausibilitaet_bei_serien_ist_struktur():
    """Korrektur 12 des zweiten Laufs: Nach der Serien-Aufloesung
    (Ausweitung 11) traegt die Police einen VOLLSTAENDIG bestimmten
    Zustand (Scheiben + Grundsumme, kein reduktion) — die
    Vorfallart-Reichweite des Belegs beantragte trotzdem weiter
    kVx_MRV/BJB-Plausibilitaet, deren Regel den Herabsetzungszustand
    braucht, und A-M1 starb wortgleich an der Engine-Wache. Ohne
    Herabsetzungs-Anfangszustand entfaellt der Antrag ausgewiesen;
    die Police ist NICHT zustandslos und laeuft im Wertvergleich."""
    from rechner_pipeline.gates.aktuartest_lauf import baue_auftraege

    lieferung, bestand, spez = _zustandslos_fixture()
    auftraege, _ausgelassen, zustandslos = baue_auftraege(
        lieferung, bestand, spez, auspraegungen_je_police={},
        anfangszustaende={"7000717": {
            "scheiben": ((3, 4000.0),), "sum_insured": 48000.0}},
        plausibilitaet={"7000717": {"kVx_MRV": GRUND, "BJB": GRUND,
                                    "RKW": GRUND}},
        red_anteil_kandidaten=(0.50, 0.60, 0.75))
    assert zustandslos == []
    assert auftraege[0].scheiben == ((3, 4000.0),)
    assert auftraege[0].plausibilitaet == {}
    assert auftraege[0].reduktion_kandidaten == ()
    # Engine-vertraeglich: der Wertvergleich urteilt, keine Wache.
    urteil = pruefe_vertrag(auftraege[0], _profil())
    assert all(p["kriterium"] == KRITERIUM_VERGLEICH
               for p in urteil["pruefungen"])
