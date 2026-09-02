"""Migrationszugang: konstruktive Neuberechnung eines uebernommenen Vertrags.

Das ist der Vorgang, um den es in diesem Branch geht. Geprueft wird, was
ihn ausmacht:

* Das Zielsystem rechnet SELBST aus den Ursprungsparametern — der
  gelieferte Wert geht nur ins Residuum ein, nie in die Bewertung.
* Der Zugang ist ein eigener Geschaeftsvorfall mit dem Residuum als
  Betrag, kein Neuzugang aus dem Nichts.
* Was nicht verankert werden kann, wird nicht still uebernommen.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import datetime as _dt

import pytest

from rechner_pipeline.kern import KLV_DEFAULT
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.bestand.migrationszugang import (
    BETRAG_ART,
    MIG,
    MigrationszugangFehler,
    Uebernahme,
    uebernehmen,
    zugangsbericht,
    zugangsjournal,
)
from rechner_pipeline.models.bestand import LEDGER_NAMES

MP = dataclasses.asdict(KLV_DEFAULT)
KERN = Rechenkern(KLV_DEFAULT)
TA_JAHR = 9
TA = 12 * TA_JAHR
PROSP = KERN.verlaufszeile(TA_JAHR).drx_bpfl
STICHTAG = _dt.date(2026, 1, 1)


def _uebernahme(police_id: int = 1, delta: float = -850.0, **kwargs) -> Uebernahme:
    kwargs.setdefault("monate_ta", TA)
    return Uebernahme(
        police_id=police_id, model_point=MP, dk_ist=PROSP + delta, **kwargs
    )


# --------------------------------------------------------------------------- #
# 1. Konstruktive Neuberechnung
# --------------------------------------------------------------------------- #


def test_das_zielsystem_rechnet_selbst_statt_den_wert_zu_uebernehmen():
    """Der Kern der Methode: der gelieferte Wert ist nicht der Bewertungswert.

    Zwei Vertraege mit identischen Ursprungsparametern und verschiedenen
    gelieferten Staenden bekommen denselben prospektiven Wert. Nur das
    Residuum unterscheidet sie.
    """
    a, b = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    assert a.dk_prosp == b.dk_prosp == pytest.approx(PROSP)
    assert a.residuum == pytest.approx(-850.0)
    assert b.residuum == pytest.approx(+420.0)


def test_residuum_ist_geliefert_minus_prospektiv():
    e, = uebernehmen([_uebernahme(delta=-333.33)])
    assert e.residuum == pytest.approx(e.dk_ist - e.dk_prosp, rel=1e-12)


def test_ohne_differenz_bleibt_die_schicht_leer():
    """Ein Vertrag, den beide Systeme gleich sehen, traegt keine Schicht."""
    e, = uebernehmen([_uebernahme(delta=0.0)])
    assert e.getragen
    assert e.parameter.rho == 0.0


@pytest.mark.parametrize("delta", [-2000.0, -1.0, 1.0, 5000.0])
def test_die_schicht_traegt_das_residuum_exakt(delta: float):
    """Die Verankerung trifft den gelieferten Stand auf den Cent.

    Das ist der Sinn: Nach der Uebernahme zeigt das Zielsystem denselben
    Wert wie die Lieferung — aber es hat ihn gerechnet, nicht kopiert.
    """
    from rechner_pipeline.kern.korrekturschicht import (
        Korrekturschicht,
        form_proportional_zur_basis,
    )

    e, = uebernehmen([_uebernahme(delta=delta)])
    # Zahlungsjahre TA_JAHR .. n-1: das Ablaufjahr traegt keine
    # Amortisations-Zahlung (Terminalbedingung, A-M2-Befund Lauf 2).
    basis = [KERN.verlaufszeile(a).drx_bpfl for a in range(TA_JAHR, KLV_DEFAULT.n)]
    bw = KERN.produkt.bw
    schicht = Korrekturschicht(bw.modell, ((bw.AKTIV, bw.TOT),))
    verlauf = schicht.verlauf(
        e.parameter, form_proportional_zur_basis(basis), KLV_DEFAULT.x + TA_JAHR
    )
    assert e.dk_prosp + verlauf[0] == pytest.approx(e.dk_ist, rel=1e-12)


# --------------------------------------------------------------------------- #
# 2. Der Zugang ist ein eigener Geschaeftsvorfall
# --------------------------------------------------------------------------- #


def test_zugangsjournal_traegt_das_residuum_als_betrag():
    """MIG ist kein ZUG: Der Betrag ist die Veraenderung des Deckungskapitals."""
    erg = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    j = zugangsjournal(erg, STICHTAG, "KLV-1994")

    assert list(j.columns) == list(LEDGER_NAMES)
    assert set(j["ereignis"]) == {MIG}
    assert set(j["betrag_art"]) == {BETRAG_ART}
    assert sorted(j["betrag"]) == pytest.approx([-850.0, 420.0])
    assert set(j["vertragsjahr"]) == {TA_JAHR}


def test_journalzeilen_haben_die_dtypes_des_ledgers():
    """Sonst faellt der Zugang erst beim Schreiben auf."""
    from rechner_pipeline.models.bestand import LEDGER_SPALTEN

    j = zugangsjournal(uebernehmen([_uebernahme()]), STICHTAG, "KLV-1994")
    for name, dtype in LEDGER_SPALTEN:
        assert str(j[name].dtype) == dtype, name


def test_leeres_journal_behaelt_seine_form():
    """Auch ohne uebernommenen Vertrag ist das Ergebnis ein gueltiger Rahmen."""
    j = zugangsjournal([], STICHTAG, "KLV-1994")
    assert list(j.columns) == list(LEDGER_NAMES)
    assert len(j) == 0


# --------------------------------------------------------------------------- #
# 3. Was nicht getragen werden kann, wird nicht still uebernommen
# --------------------------------------------------------------------------- #


def test_nicht_verankerbarer_vertrag_traegt_einen_befund():
    """Ein Vertrag am Ablauftag hat keinen Amortisationsraum.

    Er wird NICHT ohne Schicht durchgewinkt — sonst waere sein Residuum
    still verschwunden.
    """
    letztes_jahr = KLV_DEFAULT.n
    e, = uebernehmen([
        Uebernahme(
            police_id=9, model_point=MP, monate_ta=12 * letztes_jahr,
            dk_ist=KERN.verlaufszeile(letztes_jahr).drx_bpfl - 500.0,
        )
    ])
    assert not e.getragen
    assert e.befund
    assert e.residuum == pytest.approx(-500.0)


def test_vertrag_mit_befund_kommt_nicht_ins_journal():
    """Was nicht verankert wurde, ist nicht uebernommen."""
    letztes_jahr = KLV_DEFAULT.n
    erg = uebernehmen([
        _uebernahme(1, -850.0),
        Uebernahme(police_id=2, model_point=MP, monate_ta=12 * letztes_jahr,
                   dk_ist=KERN.verlaufszeile(letztes_jahr).drx_bpfl - 500.0),
    ])
    j = zugangsjournal(erg, STICHTAG, "KLV-1994")
    assert list(j["police_id"]) == [1]
    bericht = zugangsbericht(erg)
    assert bericht["uebernommen"] == 1
    assert bericht["mit_befund"] == 1
    assert bericht["befunde"][0]["police_id"] == 2


def test_unterjaehrige_verankerung_traegt_das_rumpfjahr_pro_rata():
    """Die Rumpfjahr-Konvention (9.6-Nachtrag, entschieden 2026-08-31).

    Frueher wurde der Fall abgelehnt ("bis entschieden ist, wie das
    Rumpfjahr behandelt wird"). Entschieden ist: Das Gitter beginnt am
    Jahrestag vor t_a, das erste Gitterjahr traegt den Einheitsstrom pro
    rata ((12-m)/12), und der Wert AM t_a ist die lineare Mischung der
    Gitterwerte — dieselbe Monatskonvention wie ueberall im Kern, keine
    dritte Uhr. Der Selbsttest der Verankerung bleibt damit erhalten:
    V(t_a) ist konstruktionsbedingt das Residuum.
    """
    from rechner_pipeline.kern import Rechenkern
    from rechner_pipeline.kern.korrekturschicht import Korrekturschicht
    from rechner_pipeline.kern.model_point import KLV_DEFAULT

    kern = Rechenkern(KLV_DEFAULT)
    rumpf = 5
    monate_ta = TA + rumpf
    theta = rumpf / 12.0
    jahr = monate_ta // 12
    basis0 = kern.verlaufszeile(jahr).drx_bpfl
    basis1 = kern.verlaufszeile(jahr + 1).drx_bpfl
    prospektiv = (1.0 - theta) * basis0 + theta * basis1
    delta = -850.0

    e, = uebernehmen([
        Uebernahme(police_id=1, model_point=MP, monate_ta=monate_ta,
                   dk_ist=prospektiv + delta)
    ])
    assert e.befund is None
    assert e.parameter is not None
    assert e.parameter.rumpfmonate == rumpf
    assert e.residuum == pytest.approx(delta)

    # Selbsttest am unterjaehrigen t_a: linear gemischter Schichtwert ==
    # Residuum. Ohne die pro-rata-Kuerzung des ersten Gitterjahres laege
    # er daneben — genau das unterscheidet die Konvention vom stillen
    # Runden auf den Jahrestag.
    from rechner_pipeline.kern.korrekturschicht import (
        form_proportional_zur_basis,
    )

    bw = kern.produkt.bw
    schicht = Korrekturschicht(bw.modell, ((bw.AKTIV, bw.TOT),))
    basis = [kern.verlaufszeile(a).drx_bpfl
             for a in range(jahr, KLV_DEFAULT.n)]  # Zahlungsjahre bis n-1
    form = form_proportional_zur_basis(basis)
    verlauf = schicht.verlauf(e.parameter, form, KLV_DEFAULT.x + jahr)
    am_ta = (1.0 - theta) * verlauf[0] + theta * verlauf[1]
    assert am_ta == pytest.approx(delta, rel=1e-9)

    # Und der Gitterfall bleibt bitgleich: rumpfmonate=0 aendert nichts.
    glatt, = uebernehmen([
        Uebernahme(police_id=1, model_point=MP, monate_ta=TA,
                   dk_ist=basis0 + delta)
    ])
    assert glatt.parameter.rumpfmonate == 0


# --------------------------------------------------------------------------- #
# 5. Geschaeftsvorfall-Metadaten der Vorgeschichte (9.14)
# --------------------------------------------------------------------------- #


def test_verankerungszeitpunkt_ist_das_maximum_aus_stichtag_und_vorfall():
    """9.12: t_a = max(letzter Vertragsstichtag, letzter rechnender Vorfall)."""
    from rechner_pipeline.bestand.migrationszugang import (
        Vorgang, verankerungszeitpunkt,
    )

    # Vorfall im Vertragsjahr 8, Stichtag im Jahr 9: der Jahrestag gewinnt.
    assert verankerungszeitpunkt([Vorgang(1, "ERH", 100)], 115) == 108
    # Ohne Vorgeschichte bleibt der letzte Jahrestag.
    assert verankerungszeitpunkt([], 115) == 108
    # Ein Vorfall NACH dem letzten Jahrestag ist aktueller und gewinnt.
    assert verankerungszeitpunkt([Vorgang(1, "RED", 110)], 115) == 110


def test_nicht_rechnende_vorfaelle_setzen_keinen_verankerungspunkt():
    """Nur was gerechnet hat, hinterlaesst einen Rechenpunkt."""
    from rechner_pipeline.bestand.migrationszugang import (
        Vorgang, verankerungszeitpunkt,
    )

    # Ein Ereignis ohne Neuberechnung (hier: eine erfundene Kennung)
    assert verankerungszeitpunkt([Vorgang(1, "NOTIZ", 110)], 115) == 108


def test_vorgeschichte_hinter_dem_stichtag_faellt_hart_aus():
    from rechner_pipeline.bestand.migrationszugang import (
        Vorgang, verankerungszeitpunkt,
    )

    with pytest.raises(MigrationszugangFehler, match="hinter dem Stichtag"):
        verankerungszeitpunkt([Vorgang(1, "ERH", 200)], 115)


@pytest.mark.parametrize(
    "arten, erwartet",
    [
        ([], "ohne_vorgeschichte"),
        (["ERH", "ERH"], "dynamik"),
        (["RED"], "reduziert"),
        (["ERH", "PEX"], "beitragsfrei"),
        (["NOTIZ"], "sonstige"),
    ],
)
def test_historientyp_clustert_die_verteilungsauswertung(arten, erwartet):
    """Grob und absichtlich so — die Cluster erklaeren, nicht beschreiben."""
    from rechner_pipeline.bestand.migrationszugang import Vorgang, historientyp

    vg = [Vorgang(1, a, 60 + i) for i, a in enumerate(arten)]
    assert historientyp(vg) == erwartet


def test_die_metadatenliste_traegt_keinen_betrag():
    """Die Trennlinie aus 9.14: Zeitpunkte kommen mit, Werte nicht.

    Kaeme ein Wert mit, koennte er in die Bewertung sickern — und die
    konstruktive Neuberechnung waere keine mehr.
    """
    import dataclasses

    from rechner_pipeline.bestand.migrationszugang import (
        Vorgang, pruefe_metadatenliste,
    )

    felder = {f.name for f in dataclasses.fields(Vorgang)}
    assert felder == {"police_id", "art", "monate_seit_beginn"}
    assert pruefe_metadatenliste([Vorgang(1, "ERH", 60)]) == []


def test_vorgang_vor_vertragsbeginn_faellt_hart_aus():
    from rechner_pipeline.bestand.migrationszugang import Vorgang

    with pytest.raises(MigrationszugangFehler, match="vor Vertragsbeginn"):
        Vorgang(1, "ERH", -1)


def test_doppelte_police_faellt_hart_aus():
    with pytest.raises(MigrationszugangFehler, match="doppelte police_id"):
        uebernehmen([_uebernahme(1), _uebernahme(1)])


def test_leere_uebernahme_ist_ein_aufruffehler():
    with pytest.raises(MigrationszugangFehler, match="leere Uebernahme"):
        uebernehmen([])


def test_verankerung_hinter_dem_vertragsende_faellt_hart_aus():
    with pytest.raises(MigrationszugangFehler, match="hinter dem Vertragsende"):
        uebernehmen([
            Uebernahme(police_id=1, model_point=MP,
                       monate_ta=12 * (KLV_DEFAULT.n + 1), dk_ist=1.0)
        ])


# --------------------------------------------------------------------------- #
# 4. Beleg
# --------------------------------------------------------------------------- #


def test_bericht_weist_verteilung_und_bilanzgroesse_getrennt_aus():
    """Die Summe der Residuen ist hier eine echte Bilanzgroesse.

    Anders als im aktuariellen Test, wo Summen verboten sind: Was die
    Korrekturschicht insgesamt traegt, gehoert in die Ueberleitung.
    """
    erg = uebernehmen([_uebernahme(1, -850.0), _uebernahme(2, +420.0)])
    b = zugangsbericht(erg)
    assert b["summe_residuum"] == pytest.approx(-430.0)
    assert b["max_abs_residuum"] == pytest.approx(850.0)
    assert b["vertraege"] == 2


def test_ergebnis_ist_als_beleg_serialisierbar():
    """Der Zugang muss in einen Fall geschrieben werden koennen."""
    import json

    e, = uebernehmen([_uebernahme()])
    beleg = e.als_beleg()
    json.dumps(beleg)  # wirft, wenn etwas nicht serialisierbar ist
    assert beleg["schicht"]["formfunktion"] == "proportional_zur_basis"
    assert beleg["schicht"]["kohorte"] == "t_a"


def test_fallback_kohorte_wird_durchgereicht():
    """9.12: Wer nur den Stand am Migrationsstichtag hat, ist eigene Kohorte."""
    e, = uebernehmen([_uebernahme(kohorte="t_0-fallback")])
    assert e.parameter.kohorte == "t_0-fallback"


# --------------------------------------------------------------------------- #
# Rueckrechnung einer Alt-Absetzung (leite_absetzung_ab)
# --------------------------------------------------------------------------- #

import dataclasses as _dc

import pytest as _pytest

from rechner_pipeline.kern import KLV_DEFAULT as _KLV_DEFAULT
from rechner_pipeline.kern.beitragsreduktion import (
    reduziere as _reduziere,
)
from rechner_pipeline.kern.rechenkern import Rechenkern as _Rechenkern
from rechner_pipeline.bestand.migrationszugang import (
    MigrationszugangFehler as _MZFehler,
    leite_absetzung_ab,
)


def _mp_felder(**override):
    felder = _dc.asdict(_KLV_DEFAULT)
    felder.update(override)
    return felder


def _roundtrip(vs_true, f_true, jahr, verfahren, *, runden=True, **mp_override):
    """Vorwaerts rechnen, (centgerundet) liefern, zurueckrechnen."""
    felder = _mp_felder(sum_insured=vs_true, **mp_override)
    r = _reduziere(_Rechenkern(type(_KLV_DEFAULT)(**felder)), jahr, f_true,
                   verfahren=verfahren)
    s = round(r.vs_neu, 2) if runden else r.vs_neu
    p = round(r.bjb_neu, 2) if runden else r.bjb_neu
    return leite_absetzung_ab(
        felder, jahr=jahr, erlsumme=s, jbrutto=p, verfahren=verfahren)


# KLV_DEFAULT (stoab_satz 0.01, min 50, max 150): VS 100000 in Jahr 9
# klemmt an der OBERGRENZE; kleine Summen an der UNTERGRENZE; schmale
# Bandmitte ueber angepasste Grenzen; flexible Phase ueber das Alter.
@_pytest.mark.parametrize("fall", [
    dict(vs=100000.0, f=0.6, jahr=9, verfahren="mit_abzug",
         erwartet_zweig="max"),
    dict(vs=100000.0, f=0.4, jahr=9, verfahren="mit_abzug",
         erwartet_zweig="satz", stoab_max=5000.0),
    dict(vs=100000.0, f=0.6, jahr=9, verfahren="mit_abzug",
         erwartet_zweig="min", stoab_min=1200.0, stoab_max=5000.0),
    dict(vs=100000.0, f=0.6, jahr=9, verfahren="prospektiv",
         erwartet_zweig="flex_oder_null"),
    dict(vs=100000.0, f=0.5, jahr=26, verfahren="mit_abzug",
         erwartet_zweig="flex_oder_null", t=28),  # x+26=71>=60, 26>=30-5
])
def test_rueckrechnung_trifft_die_wahren_parameter(fall):
    mp_override = {k: v for k, v in fall.items()
                   if k not in ("vs", "f", "jahr", "verfahren",
                                "erwartet_zweig")}
    ergebnis = _roundtrip(fall["vs"], fall["f"], fall["jahr"],
                          fall["verfahren"], **mp_override)
    assert ergebnis.stoab_zweig == fall["erwartet_zweig"]
    # Centrundung der Lieferung begrenzt die Genauigkeit; die wahren
    # Parameter muessen aber auf Bruchteile eines Promille getroffen sein.
    assert ergebnis.vs_alt == _pytest.approx(fall["vs"], rel=5e-5)
    assert ergebnis.anteil == _pytest.approx(fall["f"], rel=5e-5)


def test_rueckrechnung_ohne_rundung_ist_exakt():
    ergebnis = _roundtrip(100000.0, 0.6, 9, "mit_abzug", runden=False)
    assert ergebnis.vs_alt == _pytest.approx(100000.0, rel=1e-9)
    assert ergebnis.anteil == _pytest.approx(0.6, rel=1e-9)


def test_ohne_laufenden_beitrag_ist_die_ableitung_unterbestimmt():
    with _pytest.raises(_MZFehler, match="NICHT bestimmbar"):
        leite_absetzung_ab(_mp_felder(), jahr=9, erlsumme=50000.0,
                           jbrutto=0.0, verfahren="mit_abzug")


def test_falsches_verfahren_liefert_andere_parameter():
    """Die Umkehrung kann das Verfahren NICHT aus (ERLSUMME, JBRUTTO)
    widerlegen: mit dem falschen Verfahren findet sie ein anderes, in
    sich konsistentes Parameterpaar. Der Test haelt fest, DASS die
    Parameter dann daneben liegen — der Schiedsrichter ist der
    unabhaengige Deckungskapital-Vergleich der Migrationssuite, nicht
    die Vorwaertsprobe. Deshalb ist das Verfahren dokumentierte
    Fall-Eigenschaft (Aktuarielle Notiz), keine Raterei der Ableitung."""
    felder = _mp_felder(sum_insured=100000.0)
    r = _reduziere(_Rechenkern(_KLV_DEFAULT), 9, 0.6, verfahren="mit_abzug")
    falsch = leite_absetzung_ab(
        felder, jahr=9, erlsumme=round(r.vs_neu, 2),
        jbrutto=round(r.bjb_neu, 2), verfahren="prospektiv")
    assert abs(falsch.vs_alt - 100000.0) > 10.0
    assert abs(falsch.anteil - 0.6) > 1e-4


def test_erlsumme_unter_dem_fortgefuehrten_teil_faellt_hart():
    with _pytest.raises(_MZFehler, match="keine Absetzung ableitbar"):
        leite_absetzung_ab(
            _mp_felder(), jahr=9, erlsumme=1000.0,
            jbrutto=round(_Rechenkern(_KLV_DEFAULT).gross_annual_premium(), 2),
            verfahren="mit_abzug")


def test_absetzung_unterhalb_der_rundungsaufloesung_faellt_hart():
    """Zweiter Lauf: fuenf RED-Policen, deren JBRUTTO praktisch der
    volle Beitrag zur ERLSUMME ist. Die Gleichungen liefern dann ein f
    nahe 1 (abgesetzt: Centbetraege) — ein Rundungsphantom, kein
    Zustand. Als Herabsetzung gefuehrt lief jede
    Kandidaten-Plausibilitaet ins Leere; die Ableitung benennt den
    Widerspruch zwischen Vorfallshistorie und Wertlage jetzt hart."""
    felder = _mp_felder(sum_insured=34500.0)
    bjb_voll = _Rechenkern(
        type(_KLV_DEFAULT)(**felder)).gross_annual_premium()
    with _pytest.raises(_MZFehler, match="ohne wirksame Absetzung"):
        leite_absetzung_ab(
            felder, jahr=3, erlsumme=34500.0,
            jbrutto=bjb_voll * (1.0 - 1e-6),
            verfahren="prospektiv")


def test_kalibrierung_auf_rand_anteil_faellt_als_widerspruch():
    """Auch der Anker-Rueckfallweg: Trifft der gelieferte Wert die
    UNGETEILTE Welt, laeuft die Bisektion an den Rand f -> 1 und
    wuerde eine Absetzung um Centbetraege behaupten — derselbe
    Widerspruch, dieselbe harte Benennung."""
    from rechner_pipeline.bestand.migrationszugang import (
        kalibriere_absetzung_aus_dk,
    )

    felder = _mp_felder(sum_insured=42000.0)
    dk = round(_Rechenkern(
        type(_KLV_DEFAULT)(**felder)).monatsreserve(120).vx_mrv, 2)
    with _pytest.raises(_MZFehler, match="ohne wirksame Absetzung"):
        kalibriere_absetzung_aus_dk(
            felder, jahr=3, erlsumme=42000.0, dk_ist=dk,
            monate_dk=120, verfahren="prospektiv")


# --------------------------------------------------------------------------- #
# Rueckrechnung einer Alt-Dynamikerhoehung (leite_erhoehung_ab)
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand.migrationszugang import leite_erhoehung_ab
from rechner_pipeline.kern.rechenkern import (
    erhoehungs_scheibe as _erhoehungs_scheibe,
)


def test_erhoehungszerlegung_trifft_die_wahren_summen():
    """Roundtrip mit centgerundeter Lieferung: die wahren Teilsummen
    muessen auf Bruchteile eines Promille getroffen sein."""
    s_grund, s_scheibe, jahr = 80000.0, 12000.0, 6
    felder = _mp_felder(sum_insured=s_grund)
    grund = _Rechenkern(type(_KLV_DEFAULT)(**felder))
    scheibe = _Rechenkern(_erhoehungs_scheibe(grund.mp, jahr, s_scheibe))
    erlsumme = round(s_grund + s_scheibe, 2)
    jbrutto = round(grund.gross_annual_premium()
                    + scheibe.gross_annual_premium(), 2)

    ergebnis = leite_erhoehung_ab(
        felder, jahr=jahr, erlsumme=erlsumme, jbrutto=jbrutto)
    assert ergebnis.grundsumme == _pytest.approx(s_grund, rel=5e-5)
    assert ergebnis.erhoehungssumme == _pytest.approx(s_scheibe, rel=5e-5)


def test_erhoehungszerlegung_ohne_rundung_ist_exakt():
    s_grund, s_scheibe, jahr = 80000.0, 12000.0, 6
    felder = _mp_felder(sum_insured=s_grund)
    grund = _Rechenkern(type(_KLV_DEFAULT)(**felder))
    scheibe = _Rechenkern(_erhoehungs_scheibe(grund.mp, jahr, s_scheibe))
    ergebnis = leite_erhoehung_ab(
        felder, jahr=jahr, erlsumme=s_grund + s_scheibe,
        jbrutto=grund.gross_annual_premium() + scheibe.gross_annual_premium())
    assert ergebnis.grundsumme == _pytest.approx(s_grund, rel=1e-9)
    assert ergebnis.erhoehungssumme == _pytest.approx(s_scheibe, rel=1e-9)


def test_erhoehungszerlegung_ohne_beitrag_ist_unterbestimmt():
    with _pytest.raises(_MZFehler, match="NICHT bestimmbar"):
        leite_erhoehung_ab(_mp_felder(), jahr=6, erlsumme=92000.0, jbrutto=0.0)


def test_erhoehungszerlegung_weist_unplausible_lieferung_zurueck():
    """Ein Beitrag, der zur Gesamtsumme ohne Erhoehung passt (oder sie
    uebersteigt), ergibt keine positive Scheibe — Befund statt Raten."""
    felder = _mp_felder(sum_insured=92000.0)
    nur_grund = _Rechenkern(type(_KLV_DEFAULT)(**felder))
    with _pytest.raises(_MZFehler, match="Zerlegung unplausibel"):
        leite_erhoehung_ab(
            felder, jahr=6, erlsumme=92000.0,
            jbrutto=round(nur_grund.gross_annual_premium(), 2))


# --------------------------------------------------------------------------- #
# Ursprungssumme bei bekanntem Anteil (leite_ursprungssumme_ab)
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand.migrationszugang import leite_ursprungssumme_ab


@_pytest.mark.parametrize("verfahren,f,jahr,override", [
    ("mit_abzug", 0.75, 8, {}),                                   # max-Zweig
    ("mit_abzug", 0.4, 9, {"stoab_max": 5000.0}),                 # satz-Zweig
    ("mit_abzug", 0.6, 9, {"stoab_min": 1200.0, "stoab_max": 5000.0}),  # min
    ("prospektiv", 0.6, 9, {}),
])
def test_ursprungssumme_bei_bekanntem_anteil(verfahren, f, jahr, override):
    felder = _mp_felder(sum_insured=100000.0, **override)
    r = _reduziere(_Rechenkern(type(_KLV_DEFAULT)(**felder)), jahr, f,
                   verfahren=verfahren)
    vs = leite_ursprungssumme_ab(
        felder, jahr=jahr, erlsumme=round(r.vs_neu, 2), anteil=f,
        verfahren=verfahren)
    assert vs == _pytest.approx(100000.0, rel=5e-5)


def test_ursprungssumme_verlangt_einen_echten_anteil():
    with _pytest.raises(_MZFehler, match="fortgefuehrte Bruchteil"):
        leite_ursprungssumme_ab(
            _mp_felder(), jahr=8, erlsumme=90000.0, anteil=1.0,
            verfahren="mit_abzug")


# --------------------------------------------------------------------------- #
# Ursprungssumme eines beitragsfrei uebernommenen Vertrags
# --------------------------------------------------------------------------- #

from rechner_pipeline.bestand.migrationszugang import (
    leite_erhoehung_aus_satz_ab,
    leite_pex_ursprungssumme_ab,
    pruefe_erhoehungssatz,
)


def test_pex_ursprungssumme_kehrt_die_umwandlung_um():
    """Der Abzug fuehrt die beitragsfreie Summe; der Kern braucht die
    Ursprungssumme und wandelt selbst um."""
    pex_jahr = 7
    kern = _Rechenkern(_KLV_DEFAULT)
    vs_bfr = kern.beitragsfreie_summe(pex_jahr)
    vs = leite_pex_ursprungssumme_ab(
        _mp_felder(), pex_jahr=pex_jahr, vs_bfr=round(vs_bfr, 2))
    assert vs == _pytest.approx(_KLV_DEFAULT.sum_insured, rel=5e-5)


def test_pex_ursprungssumme_ohne_umkehrung_waere_zu_klein():
    """Mutationsfaenger: die gelieferte Summe direkt als Ursprungssumme
    zu nehmen, unterschaetzt den Vertrag um den Umwandlungsfaktor."""
    pex_jahr = 7
    kern = _Rechenkern(_KLV_DEFAULT)
    vs_bfr = kern.beitragsfreie_summe(pex_jahr)
    assert vs_bfr < 0.9 * _KLV_DEFAULT.sum_insured
    vs = leite_pex_ursprungssumme_ab(
        _mp_felder(), pex_jahr=pex_jahr, vs_bfr=round(vs_bfr, 2))
    assert vs > 1.1 * vs_bfr


def test_pex_ursprungssumme_weist_unmoegliche_jahre_zurueck():
    with _pytest.raises(_MZFehler, match="nicht in der Laufzeit"):
        leite_pex_ursprungssumme_ab(_mp_felder(), pex_jahr=0, vs_bfr=1000.0)


# --------------------------------------------------------------------------- #
# Zerlegung aus dem belegten Dynamiksatz
# --------------------------------------------------------------------------- #


def test_satz_zerlegung_trifft_die_tarifwerk_regel():
    """S' = e * S^ges: aus der Gesamtsumme folgen beide Teile."""
    z = leite_erhoehung_aus_satz_ab(jahr=6, erlsumme=105000.0, satz=0.05)
    assert z.grundsumme == _pytest.approx(100000.0, rel=1e-12)
    assert z.erhoehungssumme == _pytest.approx(5000.0, rel=1e-12)


def test_satz_zerlegung_braucht_keinen_beitrag():
    """Der Vorteil gegenueber der Beitragszerlegung: sie traegt auch
    Vertraege, deren Beitragszahlung beendet ist."""
    z = leite_erhoehung_aus_satz_ab(jahr=4, erlsumme=52500.0, satz=0.05)
    assert z.erhoehungssumme > 0


@_pytest.mark.parametrize("satz", [0.0, 1.0, -0.05])
def test_satz_ausserhalb_null_bis_eins_faellt_hart(satz):
    with _pytest.raises(_MZFehler, match="nicht in"):
        leite_erhoehung_aus_satz_ab(jahr=6, erlsumme=105000.0, satz=satz)


def test_satzpruefung_belegt_den_richtigen_und_verwirft_die_anderen():
    """Die Pruefung haelt den Satz gegen den Jahresbeitrag — eine
    Groesse, die in die Zerlegung NICHT eingeht."""
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe as _es

    jahr, satz_wahr = 6, 0.05
    grundsumme = 100000.0
    felder = _mp_felder(sum_insured=grundsumme)
    grund = _Rechenkern(type(_KLV_DEFAULT)(**felder))
    scheibe = _Rechenkern(_es(grund.mp, jahr, grundsumme * satz_wahr))
    beleg = (felder, jahr, grundsumme * (1 + satz_wahr),
             round(grund.gross_annual_premium()
                   + scheibe.gross_annual_premium(), 2))

    richtig = pruefe_erhoehungssatz(satz_wahr, [beleg])
    assert richtig["passt"] and richtig["geprueft"] == 1
    for falsch in (0.03, 0.07):
        assert not pruefe_erhoehungssatz(falsch, [beleg])["passt"]


def test_satzpruefung_ignoriert_belege_ohne_beitrag():
    """Ohne Beitrag gibt es nichts zu pruefen — und kein stilles Bestehen."""
    ergebnis = pruefe_erhoehungssatz(0.05, [(_mp_felder(), 6, 105000.0, 0.0)])
    assert ergebnis["geprueft"] == 0 and not ergebnis["passt"]


def test_verfeinerung_schaerft_den_anteil_auf_den_glatten_parameter():
    """Aus zwei centgerundeten Feldern kommt ein leicht verrauschter
    Anteil; die Verfeinerung prueft glatte Kandidaten gegen den
    Jahresbeitrag und trifft den vereinbarten Parameter exakt."""
    jahr, f_wahr, vs_wahr = 6, 0.6, 65000.0
    felder = _mp_felder(sum_insured=vs_wahr)
    r = _reduziere(_Rechenkern(type(_KLV_DEFAULT)(**felder)), jahr, f_wahr,
                   verfahren="mit_abzug")
    ergebnis = leite_absetzung_ab(
        felder, jahr=jahr, erlsumme=round(r.vs_neu, 2),
        jbrutto=round(r.bjb_neu, 2), verfahren="mit_abzug")
    assert ergebnis.anteil == f_wahr           # exakt, nicht nur nahe
    assert ergebnis.vs_alt == _pytest.approx(vs_wahr, rel=1e-6)


def test_kalibrierung_findet_den_anteil_aus_dem_ankerwert():
    """Rueckfallweg ohne Beitragsgleichung: der gelieferte Wert am
    Verankerungszeitpunkt bestimmt den Anteil."""
    from rechner_pipeline.bestand.migrationszugang import (
        kalibriere_absetzung_aus_dk,
    )
    from rechner_pipeline.kern.beitragsreduktion import ReduzierterVertrag

    jahr, f_wahr, vs_wahr, monate = 6, 0.6, 65000.0, 120
    felder = _mp_felder(sum_insured=vs_wahr)
    kern = _Rechenkern(type(_KLV_DEFAULT)(**felder))
    rv = ReduzierterVertrag.nach(kern, jahr, f_wahr, verfahren="mit_abzug")
    dk = round(rv.monatsreserve(monate).vx_mrv, 2)
    erlsumme = round(rv.reduktion.vs_neu, 2)

    vs, f = kalibriere_absetzung_aus_dk(
        felder, jahr=jahr, erlsumme=erlsumme, dk_ist=dk, monate_dk=monate,
        verfahren="mit_abzug")
    assert f == _pytest.approx(f_wahr, abs=1e-4)
    assert vs == _pytest.approx(vs_wahr, rel=1e-4)


def test_kalibrierung_weist_unerreichbare_werte_zurueck():
    """Ein Wert ausserhalb des erreichbaren Bereichs wird nicht durch
    einen Randanteil 'getroffen' — er faellt."""
    from rechner_pipeline.bestand.migrationszugang import (
        kalibriere_absetzung_aus_dk,
    )
    with _pytest.raises(_MZFehler, match="ausserhalb des erreichbaren"):
        kalibriere_absetzung_aus_dk(
            _mp_felder(), jahr=6, erlsumme=70000.0, dk_ist=1.0,
            monate_dk=120, verfahren="mit_abzug")


class TestSerienAbleitung:
    """leite_serie_aus_satz_ab: die Lieferung-2-Serien, handgerechnet.

    Referenz ist die Vorwaertskette der Quelle: Grundsumme 76000, sechs
    Annahmen zu 5 Prozent der jeweiligen Gesamtsumme — die Zahlen des
    realen Vertrags 7000755 der zweiten Baldrian-Lieferung.
    """

    def test_reine_erhoehungsserie_trifft_die_vorwaertskette_centgenau(self):
        from rechner_pipeline.bestand.migrationszugang import (
            leite_serie_aus_satz_ab,
        )

        ereignisse = [("ERH", j, None) for j in (1, 3, 4, 7, 8, 9)]
        serie = leite_serie_aus_satz_ab(
            ereignisse=ereignisse, erlsumme=101847.27, satz=0.05)
        assert serie.grundsumme == pytest.approx(76000.00, abs=0.01)
        erwartet = [3800.00, 3990.00, 4189.50, 4398.98, 4618.92, 4849.87]
        assert [s for _, s in serie.scheiben] == pytest.approx(
            erwartet, abs=0.01)
        assert [j for j, _ in serie.scheiben] == [1, 3, 4, 7, 8, 9]
        # Die IST-Struktur reproduziert die gelieferte Summe exakt.
        assert serie.grundsumme + sum(s for _, s in serie.scheiben) == (
            pytest.approx(101847.27, abs=0.001))
        assert serie.absetzungen == ()

    def test_absetzung_wirkt_nur_auf_die_grundsumme(self):
        """Handkette: 10000 -> ERH(1): +500 -> RED(2, f=0.6):
        Grund 6000 -> ERH(3): +325 (5 Prozent von 6500). Gesamt 6825."""
        from rechner_pipeline.bestand.migrationszugang import (
            leite_serie_aus_satz_ab,
        )

        serie = leite_serie_aus_satz_ab(
            ereignisse=[("ERH", 1, None), ("RED", 2, 0.6), ("ERH", 3, None)],
            erlsumme=6825.00, satz=0.05)
        assert serie.grundsumme == pytest.approx(6000.00, abs=0.01)
        assert [s for _, s in serie.scheiben] == pytest.approx(
            [500.00, 325.00], abs=0.01)
        assert serie.absetzungen == ((2, 0.6),)

    def test_fehlerpfade_fail_fast(self):
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            leite_serie_aus_satz_ab,
        )

        with pytest.raises(MigrationszugangFehler, match="aufsteigend"):
            leite_serie_aus_satz_ab(
                ereignisse=[("ERH", 3, None), ("ERH", 2, None)],
                erlsumme=1000.0, satz=0.05)
        with pytest.raises(MigrationszugangFehler, match="Anteil"):
            leite_serie_aus_satz_ab(
                ereignisse=[("ERH", 1, None), ("RED", 2, None)],
                erlsumme=1000.0, satz=0.05)
        with pytest.raises(MigrationszugangFehler, match="terminal"):
            leite_serie_aus_satz_ab(
                ereignisse=[("PEX", 1, None), ("ERH", 2, None)],
                erlsumme=1000.0, satz=0.05)
        # Ein Satz, der die gelieferte Summe strukturell verfehlt
        # (Grundsumme wuerde negativ), bricht hart.
        with pytest.raises(MigrationszugangFehler):
            leite_serie_aus_satz_ab(
                ereignisse=[("ERH", 1, None)],
                erlsumme=1000.0, satz=1.5)


class TestSerienKandidatenBestimmung:
    """bestimme_serie_mit_kandidaten: offene Anteile aus dem Beitrag.

    Handkette der wahren Welt (Muster der 14 Serie+RED-Policen des
    zweiten Laufs, z. B. ERH,ERH,RED): Grundsumme 80000, Satz 5
    Prozent, ERH(3)=4000, ERH(5)=4200, RED(8, f=0.6) auf die
    Grundsumme -> IST-Grund 48000, ERLSUMME 56200. Der gelieferte
    Jahresbeitrag ist die Summe der Baustein-Beitraege dieser
    IST-Struktur — er diskriminiert die Kandidaten, weil jede andere
    f-Annahme eine andere Baustein-Mischung mit anderem Gesamtbeitrag
    ergibt.
    """

    EREIGNISSE = [("ERH", 3, None), ("ERH", 5, None), ("RED", 8, None)]
    ERLSUMME, SATZ = 56200.0, 0.05
    KANDIDATEN = (0.50, 0.60, 0.75)

    def _jbrutto_der_wahren_welt(self, gamma1: bool) -> float:
        from rechner_pipeline.kern import erhoehungs_scheibe

        grund_mp = type(_KLV_DEFAULT)(
            **_mp_felder(sum_insured=48000.0))
        s = _Rechenkern(grund_mp).gross_annual_premium()
        for jahr, summe in ((3, 4000.0), (5, 4200.0)):
            s += _Rechenkern(erhoehungs_scheibe(
                grund_mp, jahr, summe, gamma1_uebernehmen=gamma1,
            )).gross_annual_premium()
        return round(s, 2)

    def test_bestimmung_trifft_den_wahren_anteil(self):
        from rechner_pipeline.bestand.migrationszugang import (
            bestimme_serie_mit_kandidaten,
        )

        serie = bestimme_serie_mit_kandidaten(
            _mp_felder(), ereignisse=self.EREIGNISSE,
            erlsumme=self.ERLSUMME, satz=self.SATZ,
            jbrutto=self._jbrutto_der_wahren_welt(False),
            kandidaten=self.KANDIDATEN)
        assert serie.absetzungen == ((8, 0.6),)
        assert serie.grundsumme == pytest.approx(48000.0, abs=0.01)
        assert [s for _, s in serie.scheiben] == pytest.approx(
            [4000.0, 4200.0], abs=0.01)

    def test_kandidatenmenge_ohne_den_wahren_wert_faellt(self):
        """Zonen-Beleg der Trennschaerfe: die falschen Kandidaten
        reproduzieren den Beitrag WIRKLICH nicht — sonst wuerde der
        Treffer-Test eine leere Auswahl pruefen."""
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            bestimme_serie_mit_kandidaten,
        )

        with pytest.raises(MigrationszugangFehler,
                           match="kein belegter Kandidat"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=self.EREIGNISSE,
                erlsumme=self.ERLSUMME, satz=self.SATZ,
                jbrutto=self._jbrutto_der_wahren_welt(False),
                kandidaten=(0.50, 0.75))

    def test_gamma1_regel_der_lieferung_diskriminiert_mit(self):
        """Die Beitragsprobe muss mit der Tarifwerks-Regel der
        Lieferung rechnen: Ein mit voller Formel gelieferter Beitrag
        trifft nur mit gamma1-Flag — ohne Flag fehlt je Scheibe der
        gamma1-Anteil und kein Kandidat passt."""
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            bestimme_serie_mit_kandidaten,
        )

        jbrutto = self._jbrutto_der_wahren_welt(True)
        serie = bestimme_serie_mit_kandidaten(
            _mp_felder(), ereignisse=self.EREIGNISSE,
            erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=jbrutto,
            kandidaten=self.KANDIDATEN, scheiben_mit_gamma1=True)
        assert serie.absetzungen == ((8, 0.6),)
        with pytest.raises(MigrationszugangFehler,
                           match="kein belegter Kandidat"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=self.EREIGNISSE,
                erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=jbrutto,
                kandidaten=self.KANDIDATEN, scheiben_mit_gamma1=False)

    def test_unerheblichkeit_gilt_je_position_nicht_pauschal(self):
        """Review-Befund B6: RED vor der ersten Erhoehung skaliert nur
        die Kette (unerheblich), ein spaeteres RED ist ueber den
        Beitrag EINDEUTIG bestimmt — die Pauschal-Markierung warf den
        bestimmten Anteil weg. Wahre Welt: RED(1, f beliebig),
        IST-Grund danach 80000, ERH(3)=4000, ERH(5)=4200,
        RED(8, f=0.5) -> IST-Grund 40000, ERLSUMME 48200."""
        from rechner_pipeline.kern import erhoehungs_scheibe
        from rechner_pipeline.bestand.migrationszugang import (
            bestimme_serie_mit_kandidaten,
        )

        grund_mp = type(_KLV_DEFAULT)(**_mp_felder(sum_insured=40000.0))
        jbrutto = _Rechenkern(grund_mp).gross_annual_premium()
        for jahr, summe in ((3, 4000.0), (5, 4200.0)):
            jbrutto += _Rechenkern(erhoehungs_scheibe(
                grund_mp, jahr, summe)).gross_annual_premium()

        serie = bestimme_serie_mit_kandidaten(
            _mp_felder(),
            ereignisse=[("RED", 1, None), ("ERH", 3, None),
                        ("ERH", 5, None), ("RED", 8, None)],
            erlsumme=48200.0, satz=self.SATZ,
            jbrutto=round(jbrutto, 2), kandidaten=self.KANDIDATEN)

        assert serie.anteil_unbestimmt == (1,)
        assert serie.absetzungen == ((8, 0.5),)
        assert serie.grundsumme == pytest.approx(40000.0, abs=0.01)
        assert [s for _, s in serie.scheiben] == pytest.approx(
            [4000.0, 4200.0], abs=0.01)

    def test_fehlerpfade_fail_fast(self):
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            bestimme_serie_mit_kandidaten,
        )

        with pytest.raises(MigrationszugangFehler,
                           match="kein Ankerwert"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=self.EREIGNISSE,
                erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=0.0,
                kandidaten=self.KANDIDATEN)
        with pytest.raises(MigrationszugangFehler,
                           match="unter zwei verschiedenen"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=self.EREIGNISSE,
                erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=1000.0,
                kandidaten=(0.6, 0.6))
        viele = [("ERH", 1, None)] + [
            ("RED", j, None) for j in (2, 4, 6, 8)]
        with pytest.raises(MigrationszugangFehler,
                           match="Kombinatorik"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=viele,
                erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=1000.0,
                kandidaten=self.KANDIDATEN)

    def test_ankerwert_diskriminiert_wenn_der_beitrag_entfaellt(self):
        """Die drei beitragslosen Serien-Policen des zweiten Laufs
        (Beitragszahlungsdauer am Stichtag abgelaufen, JBRUTTO 0):
        das gelieferte Deckungskapital am Verankerungszeitpunkt tritt
        als zweite Gleichung an die Beitragsstelle — Wahl unter den
        endlich vielen belegten Hypothesen, keine stetige
        Kalibrierung."""
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            bestimme_serie_mit_kandidaten,
        )
        from rechner_pipeline.kern import erhoehungs_scheibe
        from rechner_pipeline.kern.rechenkern import (
            vertrags_monatsreserve,
        )

        monate = 12 * 10
        grund_mp = type(_KLV_DEFAULT)(**_mp_felder(sum_insured=48000.0))
        dk_wahr = vertrags_monatsreserve(
            _Rechenkern(grund_mp),
            [(jahr, _Rechenkern(erhoehungs_scheibe(grund_mp, jahr, s)))
             for jahr, s in ((3, 4000.0), (5, 4200.0))],
            monate).vx_mrv
        serie = bestimme_serie_mit_kandidaten(
            _mp_felder(), ereignisse=self.EREIGNISSE,
            erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=0.0,
            kandidaten=self.KANDIDATEN,
            anker=(monate, round(dk_wahr, 2)))
        assert serie.absetzungen == ((8, 0.6),)
        assert serie.grundsumme == pytest.approx(48000.0, abs=0.01)
        # Zonen-Beleg: ohne den wahren Kandidaten faellt die Wahl.
        with pytest.raises(MigrationszugangFehler,
                           match="kein belegter Kandidat"):
            bestimme_serie_mit_kandidaten(
                _mp_felder(), ereignisse=self.EREIGNISSE,
                erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=0.0,
                kandidaten=(0.50, 0.75),
                anker=(monate, round(dk_wahr, 2)))

    def test_herabsetzung_vor_erster_erhoehung_ist_anteil_invariant(self):
        """Police 7000569 des zweiten Laufs: Liegt die Herabsetzung vor
        jeder Erhoehung, skaliert sie die gesamte Kette — jede
        Kandidaten-Annahme ergibt DIESELBE IST-Struktur. Das ist kein
        Wuerfelwurf, sondern Unerheblichkeit: Struktur zurueckgeben,
        Jahr als anteil_unbestimmt ausweisen, keinen Anteil raten."""
        from rechner_pipeline.bestand.migrationszugang import (
            bestimme_serie_mit_kandidaten,
        )
        from rechner_pipeline.kern import erhoehungs_scheibe

        grund_mp = type(_KLV_DEFAULT)(**_mp_felder(sum_insured=10000.0))
        jbrutto = round(
            _Rechenkern(grund_mp).gross_annual_premium()
            + _Rechenkern(erhoehungs_scheibe(
                grund_mp, 3, 500.0)).gross_annual_premium()
            + _Rechenkern(erhoehungs_scheibe(
                grund_mp, 4, 525.0)).gross_annual_premium(), 2)
        serie = bestimme_serie_mit_kandidaten(
            _mp_felder(),
            ereignisse=[("RED", 1, None), ("ERH", 3, None),
                        ("ERH", 4, None)],
            erlsumme=11025.0, satz=self.SATZ, jbrutto=jbrutto,
            kandidaten=self.KANDIDATEN)
        assert serie.grundsumme == pytest.approx(10000.0, abs=0.01)
        assert [s for _, s in serie.scheiben] == pytest.approx(
            [500.0, 525.0], abs=0.01)
        assert serie.absetzungen == ()
        assert serie.anteil_unbestimmt == (1,)
        assert serie.als_beleg()["anteil_unbestimmt"] == [1]

    def test_invarianter_anker_mit_verschiedenen_strukturen_faellt(self):
        """Policen 7000679/7000396 des zweiten Laufs: Liegt der Anker
        NACH dem Beitragszahlungsende, ist das Deckungskapital homogen
        in der Gesamtsumme — jeder Kandidat trifft, aber die Strukturen
        (Grund/Scheiben-Split) sind VERSCHIEDEN und an frueheren
        Punkten bewertungsrelevant. Das System darf dann nicht waehlen:
        benannter Fehler mit dem Lesart-Ausweg."""
        from rechner_pipeline.bestand.migrationszugang import (
            MigrationszugangFehler,
            bestimme_serie_mit_kandidaten,
            leite_serie_aus_satz_ab,
        )
        from rechner_pipeline.kern import erhoehungs_scheibe
        from rechner_pipeline.kern.rechenkern import (
            vertrags_monatsreserve,
        )

        felder = _mp_felder(t=5)
        ereignisse = [("ERH", 1, None), ("ERH", 2, None),
                      ("RED", 3, None)]
        erlsumme, monate = 60000.0, 12 * 12  # weit nach t=5

        def dk(f):
            er = [(a, j, f if a == "RED" else None)
                  for a, j, _ in ereignisse]
            s = leite_serie_aus_satz_ab(
                ereignisse=er, erlsumme=erlsumme, satz=0.05)
            gm = type(_KLV_DEFAULT)(**{**felder,
                                       "sum_insured": s.grundsumme})
            return vertrags_monatsreserve(
                _Rechenkern(gm),
                [(j, _Rechenkern(erhoehungs_scheibe(gm, j, su)))
                 for j, su in s.scheiben],
                monate).vx_mrv

        # Zonen-Beleg: nach dem Beitragsende ist das DK strukturfrei —
        # sonst pruefte der Test nicht den Mehrdeutigkeits-Pfad.
        assert dk(0.50) == pytest.approx(dk(0.75), abs=1e-6)
        with pytest.raises(MigrationszugangFehler,
                           match="VERSCHIEDENEN Strukturen"):
            bestimme_serie_mit_kandidaten(
                felder, ereignisse=ereignisse, erlsumme=erlsumme,
                satz=0.05, jbrutto=0.0, kandidaten=self.KANDIDATEN,
                anker=(monate, round(dk(0.60), 2)))

    def test_geschlossene_serie_braucht_keine_probe(self):
        """Alle Anteile gesetzt: reine Delegation an die Ableitung —
        auch mit jbrutto=0 (die Beitragsgleichung wird nicht gebraucht,
        ihr Fehlen darf dann nicht werfen)."""
        from rechner_pipeline.bestand.migrationszugang import (
            bestimme_serie_mit_kandidaten,
            leite_serie_aus_satz_ab,
        )

        ereignisse = [("ERH", 3, None), ("RED", 8, 0.6)]
        direkt = leite_serie_aus_satz_ab(
            ereignisse=ereignisse, erlsumme=self.ERLSUMME, satz=self.SATZ)
        via = bestimme_serie_mit_kandidaten(
            _mp_felder(), ereignisse=ereignisse,
            erlsumme=self.ERLSUMME, satz=self.SATZ, jbrutto=0.0,
            kandidaten=self.KANDIDATEN)
        assert via == direkt


def test_ablauf_verankerung_nutzt_den_extern_gerechneten_wert():
    """Review-Befund B5: Auch am Ablauf ist der Ausbuchungswert der
    Wert der GERECHNETEN Welt. Der Ablauf-Sonderzweig fiel fuer
    Zustands-Welten still auf die Stamm-Ablaufleistung zurueck — das
    Residuum des Ausbuchungs-Befunds war dann die falsche Differenz."""
    mp_dict = dict(MP)
    n = mp_dict["n"]
    extern = 55555.55
    e, = uebernehmen([
        Uebernahme(police_id=1, model_point=MP, monate_ta=12 * n,
                   dk_ist=extern + 500.0, dk_prosp_extern=extern)
    ])
    assert e.befund is not None and "Ablauf" in e.befund
    assert e.dk_prosp == pytest.approx(extern)
    assert e.residuum == pytest.approx(500.0)

    # Ohne externen Wert bleibt die Stamm-Ablaufleistung die Basis.
    stamm, = uebernehmen([
        Uebernahme(police_id=1, model_point=MP, monate_ta=12 * n,
                   dk_ist=1000.0)
    ])
    ablauf = KERN.verlaufszeile(n).drx_bpfl
    assert stamm.dk_prosp == pytest.approx(ablauf)


def test_extern_gerechneter_prospektivwert_bestimmt_das_residuum():
    """Ausweitung Nr. 18: Zustands-Welten rechnet der Aufrufer — das
    Residuum ist dann exakt dk_ist minus dem extern uebergebenen
    Prospektivwert, nicht die Stamm-Welt-Differenz."""
    ta = 12 * 10
    extern = 12345.67
    e, = uebernehmen([
        Uebernahme(police_id=1, model_point=MP, monate_ta=ta,
                   dk_ist=extern + 500.0, dk_prosp_extern=extern)
    ])
    assert e.dk_prosp == pytest.approx(extern)
    assert e.residuum == pytest.approx(500.0)
    assert e.parameter is not None
