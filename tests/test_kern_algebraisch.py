"""Algebraische Falsifikation des Zielkerns: aktuarielle Identitaeten.

Gerettet aus dem Gate G6 der abgeschafften Portierungs-Kette. Dort war es
die Excel-UNABHAENGIGE Gegenprobe: waehrend der Golden Master nur zeigt,
dass ein Kern die Werte reproduziert, die er in der Arbeitsmappe gesehen
hat, drueckt diese Pruefung die Funktionen gegen die Identitaeten,
Schranken und Rekursionen, die fuer die erklaerte Rechnungsgrundlage
gelten muessen — ganz gleich, welche Zahl irgendwo zwischengespeichert
ist. Ein Wertevergleich auf vier Nachkommastellen kann relative Drift
verstecken; diese Pruefung kann es nicht.

Der Gegenstand hat sich geaendert, der Zweck nicht: geprueft wird jetzt
der ZIELKERN (``kern.zustandsmodell``, ``kern.produkte``,
``kern.tafeln``) statt eines generierten Fremdkerns. Damit entfaellt die
Vertrags-/Aufloesungsmechanik des Gates (function_mappings, dynamischer
Import): unser Kern ist kein fremdes Artefakt mehr, wir importieren ihn
direkt. Die Identitaeten sind unveraendert uebernommen.

Nicht uebernommen: die l_x-Identitaeten der Sterblichkeitsstufe. Der
Zielkern kennt keine Absterbeordnung — er rechnet auf reinen
Uebergangswahrscheinlichkeiten (ADR-004). Eine l_x-Rekursion waere dort
keine Pruefung, sondern eine Tautologie ueber eine Groesse, die es nicht
gibt. Die Kommutations-Identitaeten (D/N/C/M) gelten weiterhin, aber fuer
den separaten Zweitkern — sie stehen deshalb hier bei ihm.

Stufe 3 (Aequivalenzprinzip) trifft seit dieser Fassung den PRODUKTIVEN
Beitragspfad: geprueft werden ``KLV.gross_premium_rate`` (Bxt) und
``KLV.net_premium_rate`` (Pxt) — die Groessen, die Verlaufswerte,
Reserven und Golden Master tragen. Die Gegenrechnung entsteht
unabhaengig aus den Bausteinen des Kommutations-ZWEITKERNS (ADR-004);
der Produktivpfad rechnet auf dem Zustandsmodell. Zuvor stand hier eine
Identitaet ueber ``pv_benefits``/``pv_premiums``/``net_premium``, also
ueber Whole-Life-Durchreicher, die kein Produkt aufruft und deren
Nettobeitrag definitionsgemaess ihr eigener Quotient ist — eine
Tautologie, die eine um den Faktor 7 verfaelschte A_x ueberlebte. Die
Durchreicher bleiben (gemeinsamer Interface-Punkt des
Zweitkern-Abgleichs), werden jetzt aber gegen den Zweitkern geprueft
statt gegen sich selbst.

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses
import math

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from rechner_pipeline.kern import KLV_DEFAULT, tafeln
from rechner_pipeline.kern.konventionen import MAX_ALTER
from rechner_pipeline.kern.produkte.klv import KLV
from rechner_pipeline.kern.zustandsmodell import ZustandsBarwerte

#: Toleranzen des frueheren qa_contract.json — unveraendert uebernommen.
REL_TOL = 1e-9
ABS_TOL = 1e-12

#: Rechnungsbasen, ueber die die Identitaeten gelten muessen. Bewusst
#: mehrere: eine Identitaet, die nur fuer den Default haelt, ist keine.
BASEN = [
    ("M", "DAV2008_T", 0.0175),
    ("F", "DAV2008_T", 0.0225),
    ("M", "DAV1994_T", 0.0175),
    ("U70", "DAV2008_T_NR", 0.0125),
]

LANGSAM = settings(
    max_examples=40, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


def _nah(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=ABS_TOL)


def _endlich(name: str, wert: float) -> None:
    assert math.isfinite(wert), f"{name} = {wert} ist nicht endlich"


def _barwerte(basis_spec) -> ZustandsBarwerte:
    sex, tafel, zins = basis_spec
    return ZustandsBarwerte(tafeln.basis(sex, tafel), zins)


def _hoechstes_alter(bw: ZustandsBarwerte) -> int:
    """Letztes Alter, fuer das der Kern definiert ist (Tafel-Erschoepfung)."""
    erschoepft = bw.basis.erschoepft
    return (erschoepft - 1) if erschoepft is not None else MAX_ALTER


@pytest.fixture(params=BASEN, ids=lambda b: f"{b[0]}-{b[1]}-{b[2]}")
def bw(request) -> ZustandsBarwerte:
    return _barwerte(request.param)


@pytest.fixture(params=BASEN, ids=lambda b: f"{b[0]}-{b[1]}-{b[2]}")
def basis_spec(request):
    """Dieselbe Rechnungsbasis als (sex, tafel, zins) — fuer Modellpunkte."""
    return request.param


def _zweitkern(sex: str, tafel: str, zins: float):
    """Barwert-Bausteine des Kommutations-Zweitkerns (ADR-004).

    Zweite, unabhaengige Implementierung derselben Rechnungsbasis: sie
    geht ueber die Absterbeordnung l_x und die Kommutationszahlen
    D/N/C/M, waehrend der Produktivpfad auf Uebergangswahrscheinlich-
    keiten rechnet. Eine Gegenrechnung aus diesen Bausteinen ist damit
    keine Umformung des geprueften Rumpfes.
    """
    from rechner_pipeline.kommutationskern.barwerte import Barwerte
    from rechner_pipeline.kommutationskern.kommutation import fuer

    return Barwerte(fuer(sex, tafel, zins), zins)


# --------------------------------------------------------------------------- #
# Stufe 1: Sterblichkeit
# --------------------------------------------------------------------------- #


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=118))
def test_qx_liegt_in_null_bis_eins(bw, alter):
    """0 <= q_x <= 1, endlich."""
    if alter > _hoechstes_alter(bw):
        return
    q = bw.basis.qx_at(alter)
    _endlich("qx", q)
    assert 0.0 <= q <= 1.0, f"qx({alter}) = {q} liegt nicht in [0,1]"


def test_tafel_endet_mit_sicherem_tod(bw):
    """Endalter-Politik: an der Erschoepfungsgrenze ist q_x = 1.

    Das ist die Bedingung, aus der die Erschoepfung ueberhaupt abgeleitet
    wird (kern.tafeln.erschoepft_ab) — sie hier zu pruefen bindet die
    Ableitung an ihre fachliche Bedeutung.
    """
    if bw.basis.erschoepft is None:
        pytest.skip("Tafel erreicht kein sicheres Endalter")
    assert bw.basis.qx_at(bw.basis.erschoepft - 1) >= 1.0


# --------------------------------------------------------------------------- #
# Stufe 2: Barwert-Identitaeten (Rechnungsbasis + vorschuessige Zahlung)
# --------------------------------------------------------------------------- #


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=118))
def test_Ax_liegt_in_null_bis_eins(bw, alter):
    if alter > _hoechstes_alter(bw):
        return
    a = bw.Ax(alter)
    _endlich("Ax", a)
    assert -ABS_TOL <= a <= 1.0 + ABS_TOL, f"A_{alter} = {a} liegt nicht in [0,1]"


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=118))
def test_leibrenten_barwert_bilanz(bw, alter):
    """A_x + d·ae_x = 1 — die Grundidentitaet der vorschuessigen Zahlung."""
    if alter > _hoechstes_alter(bw):
        return
    d = bw.zins / (1.0 + bw.zins)
    a, ae = bw.Ax(alter), bw.aex(alter)
    assert _nah(a + d * ae, 1.0), (
        f"A_{alter} + d·ae_{alter} = {a + d * ae} != 1 (d = {d})")


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=118))
def test_leibrente_aus_versicherung(bw, alter):
    """ae_x = (1 - A_x)/d."""
    if alter > _hoechstes_alter(bw):
        return
    d = bw.zins / (1.0 + bw.zins)
    a, ae = bw.Ax(alter), bw.aex(alter)
    assert _nah(ae, (1.0 - a) / d), (
        f"ae_{alter} = {ae} != (1 - A_{alter})/d = {(1.0 - a) / d}")


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=117))
def test_leibrenten_rekursion(bw, alter):
    """ae_x = 1 + v·p_x·ae_{x+1}."""
    if alter + 1 > _hoechstes_alter(bw):
        return
    v = 1.0 / (1.0 + bw.zins)
    q = bw.basis.qx_at(alter)
    ist, folge = bw.aex(alter), bw.aex(alter + 1)
    soll = 1.0 + v * (1.0 - q) * folge
    assert _nah(ist, soll), f"ae_{alter} = {ist} != 1 + v·p·ae_{alter + 1} = {soll}"


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=117))
def test_versicherungs_rekursion(bw, alter):
    """A_x = v·q_x + v·p_x·A_{x+1}."""
    if alter + 1 > _hoechstes_alter(bw):
        return
    v = 1.0 / (1.0 + bw.zins)
    q = bw.basis.qx_at(alter)
    ist, folge = bw.Ax(alter), bw.Ax(alter + 1)
    soll = v * q + v * (1.0 - q) * folge
    assert _nah(ist, soll), f"A_{alter} = {ist} != v·q + v·p·A_{alter + 1} = {soll}"


# --------------------------------------------------------------------------- #
# Stufe 3: Produkt — das Aequivalenzprinzip auf dem produktiven Beitragssatz
# --------------------------------------------------------------------------- #

#: Alter, bis zu dem die l_x-Rekursion des Zweitkerns rechenbare Stellen
#: hat. Darueber faellt l_x unter 1e-6 des Anfangsbestands (DAV2008_T:
#: l_117 = 1.2e-07 gegen l_0 = 1e+05), und die Quotienten M_x/D_x beider
#: Kerne driften um bis zu 1e-05 relativ — Ausloeschung im Zweitkern,
#: kein Zielkern-Befund. Unterhalb der Grenze liegt die gemessene
#: Abweichung bei <= 1e-13 relativ, also 1e+04 unter REL_TOL: die Grenze
#: ist begruendet, nicht auf Gruen gestellt.
ZWEITKERN_MAX_ALTER = 100


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=118))
def test_whole_life_durchreicher_stimmen_mit_dem_zweitkern_ueberein(
    basis_spec, alter
):
    """A_x, ae_x und A_x/ae_x gegen den Kommutations-Zweitkern.

    ``pv_benefits``/``pv_premiums``/``net_premium`` sind der gemeinsame
    Interface-Punkt beider Kerne (ADR-004); kein Produkt ruft sie auf.
    Frueher stand hier ``net_premium == pv_benefits/pv_premiums`` — der
    Methodenrumpf gegen sich selbst, also wahr fuer JEDE A_x. Jetzt
    entscheidet ein zweiter, unabhaengig gebauter Kern.
    """
    bw = _barwerte(basis_spec)
    if alter > min(_hoechstes_alter(bw), ZWEITKERN_MAX_ALTER):
        return
    zk = _zweitkern(*basis_spec)
    assert _nah(bw.pv_benefits(alter), zk.pv_benefits(alter)), (
        f"PV(Leistungen) weicht vom Zweitkern ab bei x = {alter}")
    assert _nah(bw.pv_premiums(alter), zk.pv_premiums(alter)), (
        f"PV(Beitragsrente) weicht vom Zweitkern ab bei x = {alter}")
    assert _nah(bw.net_premium(alter), zk.net_premium(alter)), (
        f"Whole-Life-Nettobeitrag weicht vom Zweitkern ab bei x = {alter}")


@LANGSAM
@given(
    alter=st.integers(min_value=20, max_value=55),
    n=st.integers(min_value=5, max_value=40),
    t_roh=st.integers(min_value=1, max_value=40),
)
def test_aequivalenzprinzip_bruttobeitrag(basis_spec, alter, n, t_roh):
    """Aequivalenzprinzip auf dem produktiven Bruttobeitragssatz Bxt.

    Bxt·axt = Axn + gamma1·axt + gamma2·(axn-axt) + beta1·Bxt·axt
              + alpha·t·Bxt

    Das Aequivalenzprinzip des Tarifs auf der Groesse, die der Kern
    wirklich ausliefert (``KLV.gross_premium_rate``, Skalar Bxt): der
    Barwert der Beitraege deckt Leistungsbarwert, laufende Verwaltungs-
    kosten (gamma1/gamma2), Inkassokosten (beta1) und die gezillmerten
    Abschlusskosten (alpha·t). Die Gegenrechnung nimmt Axn/axn/axt aus
    dem Kommutations-Zweitkern, nur Bxt kommt aus dem Produktivpfad —
    eine falsche Beitragsformel kann den Saldo nicht mehr mitziehen.
    """
    t = min(t_roh, n)
    sex, tafel, zins = basis_spec
    grenze = min(_hoechstes_alter(_barwerte(basis_spec)), ZWEITKERN_MAX_ALTER)
    if alter + n > grenze:
        return
    mp = dataclasses.replace(
        KLV_DEFAULT, sex=sex, tafel=tafel, zins=zins, x=alter, n=n, t=t)
    zk = _zweitkern(sex, tafel, zins)
    axt, axn = zk.axn_k(alter, t, 1), zk.axn_k(alter, n, 1)
    leistung = zk.endowment_benefit_pv(alter, n)

    bxt = KLV(mp).gross_premium_rate()
    einnahmen = bxt * axt
    ausgaben = (
        leistung
        + mp.gamma1 * axt
        + mp.gamma2 * (axn - axt)
        + mp.beta1 * bxt * axt
        + mp.alpha * t * bxt
    )
    _endlich("Bxt", bxt)
    assert _nah(einnahmen, ausgaben), (
        f"Aequivalenz verletzt bei x={alter}, n={n}, t={t}: "
        f"Beitragsbarwert {einnahmen} != Ausgabenbarwert {ausgaben} "
        f"(Saldo {einnahmen - ausgaben})")


@LANGSAM
@given(
    alter=st.integers(min_value=20, max_value=55),
    n=st.integers(min_value=5, max_value=40),
    t_roh=st.integers(min_value=1, max_value=40),
)
def test_nettobeitrag_deckt_leistung_und_zillmerung(
    basis_spec, alter, n, t_roh
):
    """Pxt·axt = Axn + alpha·t·Bxt — der gezillmerte Nettobeitrag.

    Zweite produktive Groesse (``KLV.net_premium_rate``, Skalar Pxt):
    sie traegt den Leistungsbarwert plus die ueber t Jahre gezillmerten
    Abschlusskosten, aber keine laufenden Kosten. Bxt und Pxt kommen aus
    dem Produktivpfad, Axn und axt aus dem Zweitkern.
    """
    t = min(t_roh, n)
    sex, tafel, zins = basis_spec
    grenze = min(_hoechstes_alter(_barwerte(basis_spec)), ZWEITKERN_MAX_ALTER)
    if alter + n > grenze:
        return
    mp = dataclasses.replace(
        KLV_DEFAULT, sex=sex, tafel=tafel, zins=zins, x=alter, n=n, t=t)
    zk = _zweitkern(sex, tafel, zins)
    axt = zk.axn_k(alter, t, 1)
    leistung = zk.endowment_benefit_pv(alter, n)

    produkt = KLV(mp)
    pxt, bxt = produkt.net_premium_rate(), produkt.gross_premium_rate()
    _endlich("Pxt", pxt)
    assert _nah(pxt * axt, leistung + mp.alpha * t * bxt), (
        f"Nettobeitrags-Aequivalenz verletzt bei x={alter}, n={n}, t={t}: "
        f"Pxt·axt = {pxt * axt} != Axn + alpha·t·Bxt = "
        f"{leistung + mp.alpha * t * bxt}")


@LANGSAM
@given(faktor=st.sampled_from([2.0, 10.0, 1000.0]))
def test_leistung_skaliert_linear_mit_der_versicherungssumme(faktor):
    """Der Nettobeitrag ist homogen in der Versicherungssumme.

    Kosten und Rundung koennen das brechen — deshalb auf dem NETTO-Teil
    geprueft, nicht auf dem Bruttobeitrag.
    """
    basis = KLV(KLV_DEFAULT)
    gross = KLV(dataclasses.replace(
        KLV_DEFAULT, sum_insured=KLV_DEFAULT.sum_insured * faktor))
    assert _nah(gross.net_premium_rate(), basis.net_premium_rate()), (
        "die Nettobeitragsrate darf nicht von der Versicherungssumme abhaengen")


# --------------------------------------------------------------------------- #
# Stufe 4: Kommutation — gilt weiter, aber fuer den Zweitkern (ADR-004)
# --------------------------------------------------------------------------- #


@pytest.fixture()
def kom():
    from rechner_pipeline.kommutationskern.kommutation import fuer

    return fuer("M", "DAV2008_T", 0.0175)


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=110))
def test_kommutation_Dx_definition(kom, alter):
    """D_x = v^x · l_x."""
    v = 1.0 / 1.0175
    soll = (v ** alter) * kom.lx[alter]
    assert _nah(kom.dx[alter], soll), f"D_{alter} != v^x·l_x"


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=110))
def test_kommutation_Nx_rekursion(kom, alter):
    """N_x = D_x + N_{x+1}."""
    assert _nah(kom.nx[alter], kom.dx[alter] + kom.nx[alter + 1])


@LANGSAM
@given(alter=st.integers(min_value=0, max_value=110))
def test_kommutation_Mx_rekursion(kom, alter):
    """M_x = C_x + M_{x+1}."""
    assert _nah(kom.mx[alter], kom.cx[alter] + kom.mx[alter + 1])
