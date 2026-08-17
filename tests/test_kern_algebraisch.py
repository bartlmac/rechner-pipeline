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

Knoten: klv, bu
"""

from __future__ import annotations

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
# Stufe 3: Produkt — das Aequivalenzprinzip
# --------------------------------------------------------------------------- #


@LANGSAM
@given(alter=st.integers(min_value=18, max_value=70))
def test_nettobeitrag_ist_barwertquotient(bw, alter):
    """P = PV(Leistungen) / PV(Beitragsrente)."""
    if alter + 10 > _hoechstes_alter(bw):
        return
    pvb, pvp = bw.pv_benefits(alter), bw.pv_premiums(alter)
    if abs(pvp) <= ABS_TOL:
        return                       # entartet an den Grenzaltern
    assert _nah(bw.net_premium(alter), pvb / pvp)


@LANGSAM
@given(alter=st.integers(min_value=18, max_value=70))
def test_aequivalenzprinzip(bw, alter):
    """PV(Leistungen) - P·PV(Beitraege) = 0 — der Kern des Tarifs."""
    if alter + 10 > _hoechstes_alter(bw):
        return
    pvb, pvp = bw.pv_benefits(alter), bw.pv_premiums(alter)
    saldo = pvb - bw.net_premium(alter) * pvp
    assert _nah(saldo, 0.0) or abs(saldo) <= ABS_TOL + REL_TOL * abs(pvb), (
        f"PV(Leistungen) - P·PV(Beitraege) = {saldo} != 0 bei x = {alter}")


@LANGSAM
@given(faktor=st.sampled_from([2.0, 10.0, 1000.0]))
def test_leistung_skaliert_linear_mit_der_versicherungssumme(faktor):
    """Der Nettobeitrag ist homogen in der Versicherungssumme.

    Kosten und Rundung koennen das brechen — deshalb auf dem NETTO-Teil
    geprueft, nicht auf dem Bruttobeitrag.
    """
    import dataclasses

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
