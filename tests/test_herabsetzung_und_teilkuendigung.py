"""Beitragsherabsetzung und Teilkuendigung sind zwei Geschaeftsvorfaelle (ADR-023).

Entscheid des Maintainers vom 2026-10-01: "Herabsetzung betrifft NUR
Beitraege und macht nur Sinn, solange ein Beitrag bezahlt wird. Eine
Teilkuendigung kann immer (beitragspflichtig oder ausfinanziert) gemacht
werden, hat aber eine andere Wirkung — Teil des Deckungskapitals wird
ausgezahlt." Beide gibt es in jeder PLV-Generation; das Ledger sagt, WAS
geschah (``RED`` bzw. ``TKU``), eine Teilkuendigung ist nie als RED gebucht.

* Beitragsherabsetzung (``RED``): Beitrag auf f, freiwerdender Teil in
  beitragsfreie Summe umgewandelt, keine Zahlung; nur ``0 < Jahr < t`` und
  ohne PEX — danach verweigert mit dem Ausweg Teilkuendigung.
* Teilkuendigung (``TKU``): Summenanteil (1-f) gekuendigt, Rueckkaufswert
  nach Tarif (mit Stornoabzug) ausgezahlt; in jeder Generation fuer
  ``0 < Jahr < n``, auch nach der Beitragsfreistellung; eigene Rate
  (``annahmen.teilkuendigung``), eigener Anteil (``tk_anteil``), eigener
  Zufallsstrom. Sie trifft in den eigenen Tarifen JEDEN Baustein
  proportional, im uebernommenen Tarif die Grundversicherung (Entscheid B1 vom 2026-10-01).

Die Entscheide des Maintainers vom 2026-10-01 (Nachtrag) ersetzen die
Annahmen A1, A3 und A4 (klv.md 7.2): Der uebernommene Tarif kennt EINEN
Vorgang — die Teilkuendigung, aus ihrer eigenen Rate (kein zweiter Weg
ueber den Herabsetzungswunsch); die Teilkuendigung trifft alle Bausteine;
beliebig viele Vorgaenge je Vertrag, in jeder Reihenfolge. A2 (welcher
Vorgang eine gelieferte Absetzung war) ist bestaetigt.

Knoten: klv
"""

from __future__ import annotations

import ast
import copy
import dataclasses
import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import rechner_pipeline.kern.beitragsreduktion as br
from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand.config import Annahme
from rechner_pipeline.bestand.ereignisse import (
    HERABSETZUNG_STREAM,
    TEILKUENDIGUNG_STREAM,
    fortschreiben,
)
from rechner_pipeline.bestand.kennzahlen import bewegungskonto
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import KLV_DEFAULT, ModelPoint, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    TEILKUENDIGUNG,
    VERFAHREN,
    BeitragsreduktionFehler,
    reduziere,
    reduzierte_teile,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.korrekturschicht import schichtwert_bei
from rechner_pipeline.models.bestand import (
    ANNAHME_ERZEUGT,
    BETRAG_ART_JE_EREIGNIS,
    EREIGNIS_VALUES,
    LEISTUNG_BEI_ZAHLUNG,
    REDUKTION_EREIGNISSE,
    alt_absetzung_ist_teilkuendigung,
    model_point_kwargs,
    red_bindung_fehler,
    reduktion_ereignis,
    validate_reduktionen,
)
from tests.test_bestand_uebernommen_fortschreiben import _stamm
from tests.test_herabsetzung_ausfinanziert import (
    N,
    POLICEN,
    RATE_DER_WELT,
    _config,
    _pb1,
)
from tests.test_herabsetzung_in_fuehrung import ANTEIL, BIS
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen

F = 0.6
MP = KLV_DEFAULT
T, N_K = MP.t, MP.n
FELDER = dataclasses.asdict(MP)


def _folgekern(f: float = F) -> Rechenkern:
    """Die Zusage der Teilkuendigung, ohne den Herabsetzungspfad: f x S."""
    return Rechenkern(dataclasses.replace(MP, sum_insured=f * MP.sum_insured))


# --------------------------------------------------------------------------- #
# Kern: zwei Vorgaenge, keine Umdeutung
# --------------------------------------------------------------------------- #


def test_der_kern_kennt_keine_umdeutung_nach_t():
    """Die gebaute Regel A (eine Herabsetzung nach t still als
    Teilkuendigung rechnen) ist ersetzt: Es gibt keine Funktion mehr, die das
    Verfahren nach dem Jahr umdeutet, und kein Zweitwissen, welche Verfahren
    nach t definiert sind."""
    assert not hasattr(br, "wirksames_verfahren")
    assert not hasattr(br, "NACH_BEITRAGSENDE_DEFINIERT")


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_die_herabsetzung_gibt_es_nur_waehrend_der_beitragszahlung(verfahren):
    """Jahr t-1: die Umwandlung (Summe danach ueber f x S, kein Geld); Jahr t
    und n-1: verweigert, mit dem Ausweg Teilkuendigung. Mutationsproben: die
    Wache ``jahr >= t`` auf ``jahr > t`` -> Jahr t laeuft -> rot; auf
    ``jahr >= t - 1`` -> Jahr t-1 verweigert -> rot."""
    red = reduziere(Rechenkern(MP), T - 1, F, verfahren=verfahren)
    assert red.verfahren == verfahren
    assert red.vs_neu > F * MP.sum_insured + 1.0
    for jahr in (T, N_K - 1):
        with pytest.raises(BeitragsreduktionFehler, match="Ausweg: die Teilkuendigung"):
            reduziere(Rechenkern(MP), jahr, F, verfahren=verfahren)


@pytest.mark.parametrize("jahr", [1, T - 1, T, N_K - 1])
def test_die_teilkuendigung_gibt_es_in_jedem_jahr_vor_dem_ablauf(jahr):
    """Beitragspflichtig wie ausfinanziert: Summe danach f x S, Reserve danach
    die des Folgevertrags f x S, gegen den unabhaengigen Kern; der Ablauf (n)
    bleibt die Grenze. Mutationsprobe: die Ablaufwache ``jahr >= n`` auf
    ``jahr >= n - 1`` -> Jahr n-1 verweigert -> rot."""
    red = reduziere(Rechenkern(MP), jahr, F, verfahren=TEILKUENDIGUNG)
    assert red.vs_neu == pytest.approx(F * MP.sum_insured, rel=1e-15)
    assert red.dk_nach == pytest.approx(_folgekern().verlaufszeile(jahr).vx_mrv, rel=1e-12)
    teile = reduzierte_teile(Rechenkern(MP), [], jahr, F, TEILKUENDIGUNG, stoab_je_baustein=False)
    ist = vertrags_monatsreserve_reduziert(teile, 12 * jahr + 5, stoab_je_baustein=False)
    assert ist.rkw == pytest.approx(_folgekern().monatsreserve(12 * jahr + 5).rkw, rel=1e-12)


def test_am_ablauf_gibt_es_nichts_zu_kuendigen():
    with pytest.raises(BeitragsreduktionFehler, match="laeuft bei n="):
        reduziere(Rechenkern(MP), N_K, F, verfahren=TEILKUENDIGUNG)


# --------------------------------------------------------------------------- #
# Vokabular und Datenmodell
# --------------------------------------------------------------------------- #


def test_das_ledger_vokabular_traegt_beide_vorgaenge_getrennt():
    """Eine Teilkuendigung ist nie als RED gebucht: Die Herabsetzung hat keine
    Zahlungszeile mehr, die Teilkuendigung ihre eigene Summenart."""
    assert {"RED", "TKU"} <= set(EREIGNIS_VALUES)
    assert set(REDUKTION_EREIGNISSE) == {"RED", "TKU"}
    assert set(BETRAG_ART_JE_EREIGNIS["RED"]) == {"VS_herabsetzung", "dDK_absorption"}
    assert set(BETRAG_ART_JE_EREIGNIS["TKU"]) == {
        "VS_teilkuendigung", "dDK_absorption", "RKW_teilkuendigung", "Kappung_teilkuendigung"}
    assert dict(LEISTUNG_BEI_ZAHLUNG) == {"TKU": ("RKW_teilkuendigung",)}
    assert ANNAHME_ERZEUGT["teilkuendigung"] == ("klv", "TKU")
    assert ANNAHME_ERZEUGT["herabsetzung"] == ("klv", "RED")
    assert [reduktion_ereignis(v) for v in VERFAHREN] == ["RED", "RED", "TKU"]


def _zeile(jahr: int, verfahren: str, *, t: int = 15) -> tuple:
    stamm = _stamm([{"id": 1, "beginn": "2015-01-01", "zugang": "2014-01-01", "n": N, "t": t}])
    stamm["bestandszugang"] = pd.Timestamp("2015-01-01")
    red = pd.DataFrame([{
        "police_id": 1, "reduktion_jahr": jahr,
        "reduktion_datum": pd.Timestamp("2015-01-01") + pd.DateOffset(years=jahr),
        "anteil": ANTEIL, "verfahren": verfahren}])
    return stamm, red


@pytest.mark.parametrize("verfahren,jahr,gueltig", [
    (PROSPEKTIV, 14, True), (PROSPEKTIV, 15, False), (MIT_ABZUG, 24, False),
    (TEILKUENDIGUNG, 14, True), (TEILKUENDIGUNG, 15, True), (TEILKUENDIGUNG, 24, True),
    (TEILKUENDIGUNG, 25, False), (TEILKUENDIGUNG, 0, False), (PROSPEKTIV, 0, False),
])
def test_das_datenmodell_haelt_die_grenzen_je_vorgang(verfahren, jahr, gueltig):
    """t = 15, n = 25: Herabsetzung 0 < Jahr < t, Teilkuendigung 0 < Jahr < n
    (beide Grenzen beider Vorgaenge). Die Herabsetzung nach t nennt den
    Ausweg."""
    stamm, red = _zeile(jahr, verfahren)
    fehler = validate_reduktionen(stamm, red, None)
    assert (fehler == []) == gueltig, fehler
    if verfahren != TEILKUENDIGUNG and jahr >= 15:
        assert any("Ausweg: die Teilkuendigung" in f for f in fehler), fehler


# --------------------------------------------------------------------------- #
# Die Engine: beide Vorgaenge in jeder Generation (Zaehltest)
# --------------------------------------------------------------------------- #


def _welt(verfahren: str, *, rate=RATE_DER_WELT, tk_rate=RATE_DER_WELT):
    config = _config(verfahren, rate, tk_rate=tk_rate)
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01",
                     "n": N, "t": (12, 15, 20)[p % 3]} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


@pytest.fixture(scope="module")
def welten():
    return {v: _welt(v) for v in VERFAHREN}


def _t(stamm):
    return stamm.set_index("police_id")["premium_duration"]


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_zaehltest_beide_vorgaenge_vor_und_nach_t_in_jeder_generation(welten, verfahren):
    """Je Generation: Herabsetzungen (RED) nur vor t, ohne Zahlungszeile;
    Teilkuendigungen (TKU) vor UND nach t, je mit Summe und Auszahlung. Der
    uebernommene Tarif (``teilkuendigung``) bucht keine RED — er kennt keine
    Beitragsherabsetzung. Registriert ist je Vorgang das passende Verfahren;
    je Police beliebig viele (Entscheid 2026-10-01). Mutationsproben: die
    RED-Bedingung auf ``j + 1 < n`` -> Abbruch im Kern -> rot; die
    TKU-Bedingung auf ``j + 1 < t`` -> keine TKU nach t -> rot; nach dem
    ersten Vorgang nicht mehr ausfuehren -> keine Police mit zweien -> rot."""
    config, stamm, schichten, verankerung, erg = welten[verfahren]
    led, red = erg.ledger, erg.reduktionen
    t = _t(stamm)
    red_zeilen = led[led["ereignis"] == "RED"]
    tku_zeilen = led[led["ereignis"] == "TKU"]
    if verfahren == TEILKUENDIGUNG:
        assert red_zeilen.empty
    else:
        assert len(red_zeilen) > 0
        assert (red_zeilen["vertragsjahr"].to_numpy()
                < t.loc[red_zeilen["police_id"]].to_numpy()).all()
        assert set(red_zeilen["betrag_art"]) <= {"VS_herabsetzung", "dDK_absorption"}
    ab_t = tku_zeilen["vertragsjahr"].to_numpy() >= t.loc[tku_zeilen["police_id"]].to_numpy()
    assert ab_t.any() and (~ab_t).any(), "Teilkuendigung vor UND nach t"
    for (pid, jahr), eigene in tku_zeilen.groupby(["police_id", "vertragsjahr"]):
        assert {"VS_teilkuendigung", "RKW_teilkuendigung"} <= set(eigene["betrag_art"]), (pid, jahr)
    soll = {(int(p), int(j), "TKU" if v == TEILKUENDIGUNG else "RED")
            for p, j, v in zip(red["police_id"], red["reduktion_jahr"], red["verfahren"])}
    gebucht = {(int(p), int(j), str(e)) for p, j, e in zip(
        led["police_id"], led["vertragsjahr"], led["ereignis"]) if e in ("RED", "TKU")}
    assert gebucht == soll
    # A4 ist ersetzt: Policen mit mehr als einem Vorgang (Positivkontrolle).
    assert red["police_id"].duplicated().any()


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_jeder_leser_sieht_jede_buchung(welten, verfahren):
    """P-B1 ohne Befund; das Bewegungskonto schliesst je Jahr mit der eigenen
    Position der Teilkuendigung; die Bewertung (Abschluss) traegt nach einer
    Teilkuendigung den unabhaengig gebauten Folgevertrag."""
    welt = welten[verfahren]
    config, stamm, schichten, verankerung, erg = welt
    assert _pb1(welt, erg.ledger) == []
    konto = bewegungskonto(stamm, erg.historie, erg.ledger, erg.scheiben, bis=BIS)
    assert any(z["bpfl"]["veraenderung_teilkuendigung"]["summe"] < 0 for z in konto)
    for zeile in konto:
        for track, oks in zeile["identitaet"].items():
            assert all(oks.values()), (zeile["jahr"], track)
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    geprueft = 0
    red = erg.reduktionen
    # Die Teilkuendigung als ERSTER Vorgang einer Police, Stichtag vor dem
    # naechsten (Folgen: tests/test_vorgangsfolge_leser.py).
    for i, z in red.groupby("police_id").head(1).iterrows():
        if z["verfahren"] != TEILKUENDIGUNG:
            continue
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        if ((red["police_id"] == pid) & (red["reduktion_jahr"] > jahr)
                & (red["reduktion_jahr"] <= jahr + 1)).any():
            continue
        beginn = pd.Timestamp(haupt.loc[pid, "insurance_start"])
        stichtag = (beginn + pd.DateOffset(years=jahr + 1)).date()
        h = erg.historie
        if stichtag > BIS or len(h[(h["police_id"] == pid) & h["status_code"].isin(
                ["STO", "TOD", "ABL", "PEX"]) & (h["status_date"] <= pd.Timestamp(stichtag))]):
            continue                                    # PEX danach: eigener Vertrag
        werte = einzelwerte_am(stamm, h, config, stichtag, scheiben=erg.scheiben,
                               schichten=schichten, verankerung=verankerung,
                               reduktionen=erg.reduktionen)
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
        if len(erg.scheiben[erg.scheiben["police_id"] == pid]):
            continue                                    # Scheiben: test_t27_teilkuendigung_klasse
        soll = vertrags_rkw(Rechenkern(dataclasses.replace(mp, sum_insured=ANTEIL * mp.sum_insured)),
                            [], jahr + 1, stoab_je_baustein=True)
        ist = next(w for w in werte if int(w["police_id"]) == pid)["rueckkaufswert"]
        assert ist == pytest.approx(soll, rel=1e-9), pid
        geprueft += 1
    assert geprueft > 0


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_auszahlung_der_teilkuendigung_folgt_der_unabhaengigen_zusage(welten, verfahren):
    """In den eigenen Tarifen trifft die Teilkuendigung JEDEN Baustein
    (Entscheid des Maintainers 2026-10-01): Auszahlung (1-f) x RKW des
    Vertrags — Grundscheibe UND Erhoehungsscheiben, MIT Stornoabzug nach dem
    Tarifwerk — plus absorbierte Schicht (verworfen: Auszahlung ohne Abzug,
    klv.md 7.2). Soll aus dem Kern-Primitiv ``vertrags_rkw`` ueber die
    Bausteine, gebaut aus Stamm und Scheiben, fuer die Teilkuendigung als
    ersten Vorgang einer Police. Positivkontrolle: Faelle mit Scheiben.
    Mutationsprobe: Umfang Grundversicherung -> rot (Faelle mit Scheiben)."""
    from rechner_pipeline.kern import erhoehungs_scheibe

    config, stamm, schichten, verankerung, erg = welten[verfahren]
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    led = erg.ledger
    pex = erg.historie[erg.historie["status_code"] == "PEX"].set_index("police_id")["status_date"]
    geprueft = mit_scheiben = 0
    for z in erg.reduktionen.groupby("police_id").head(1).to_dict("records"):
        if z["verfahren"] != TEILKUENDIGUNG:
            continue
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        if pid in pex.index and pex.loc[pid] <= z["reduktion_datum"]:
            continue
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
        s = erg.scheiben[(erg.scheiben["police_id"] == pid) & (erg.scheiben["erhoehung_jahr"] < jahr)]
        kerne = [(int(e), Rechenkern(erhoehungs_scheibe(mp, int(e), float(v))))
                 for e, v in zip(s["erhoehung_jahr"], s["sum_insured"])]
        eigene = led[(led["police_id"] == pid) & (led["ereignis"] == "TKU")
                     & (led["vertragsjahr"] == jahr)]
        arten = dict(zip(eigene["betrag_art"], eigene["betrag"]))
        rechnerisch = (1 - ANTEIL) * vertrags_rkw(
            Rechenkern(mp), kerne, jahr, stoab_je_baustein=True
        ) + schichtwert_bei(_parameter(), MONATE_TA, mp, 12 * jahr)
        assert arten["RKW_teilkuendigung"] == pytest.approx(max(0.0, rechnerisch), abs=1e-6)
        assert arten["VS_teilkuendigung"] == pytest.approx(
            ANTEIL * (mp.sum_insured + float(s["sum_insured"].sum())), rel=1e-12)
        geprueft += 1
        mit_scheiben += bool(kerne)
    assert geprueft >= 3 and mit_scheiben >= 1, (geprueft, mit_scheiben)


# --------------------------------------------------------------------------- #
# Bitgleichheit und Unabhaengigkeit der Stroeme
# --------------------------------------------------------------------------- #

#: Gemessen auf ca61419 (Kern 3.15.0), vor jedem Bau, mit der Config von
#: test_herabsetzung_ausfinanziert (prospektiv, Rate 0,08): (1) Police
#: 940006, t = n = 25, Ledger vollstaendig; (2) Police 930004, t = 18 < n,
#: Ledger vollstaendig (ERH 14, TOD 24 — die Herabsetzung zog damals nicht
#: nach t, und sie zieht es auch jetzt nicht).
ZEUGEN = {
    (940_006, 25): (3, "4fb54958b7fd8722b4420ed02035d4db2dd891a546d558c86dc83841d755d1ad"),
    (930_004, 18): (3, None),
}
ZEUGE_930004_VOR_T = "f74283e21f484a161a6422a28dfb2d8f66a582a11c8ae0a2e1f69a633ceb1dc8"
ZEUGE_930004_AB_T = "ff99ecb6f85aaa176482b5475314497f9ba29d026e0ee83259f3344e8e24d868"


def _fingerabdruck(df: pd.DataFrame) -> str:
    return hashlib.sha256(df.to_csv(index=False).encode()).hexdigest()


def _zeuge(pid: int, t: int, tk_rate: float = 0.0) -> pd.DataFrame:
    stamm = _stamm([{"id": pid, "beginn": "2015-01-01", "zugang": "2026-01-01",
                     "n": 25, "t": t}])
    return fortschreiben(stamm, _config(PROSPEKTIV, tk_rate=tk_rate), BIS).ledger


def test_zeugen_ohne_teilkuendigungsrate_sind_bitgleich_zum_stand_davor():
    """Mit Teilkuendigungsrate 0 (Vorgabe) ist der Strom latent: beide Zeugen
    Zeile fuer Zeile wie auf ca61419. Mutationsprobe: den TKU-Draw aus dem
    Hauptstrom nehmen (``rng.random()`` statt ``rng_tk.random()``) -> rot
    (der Hauptstrom verschiebt sich, obwohl die Rate null ist)."""
    led = _zeuge(940_006, 25)
    assert len(led) == 3 and _fingerabdruck(led) == ZEUGEN[(940_006, 25)][1]
    led = _zeuge(930_004, 18)
    assert _fingerabdruck(led[led["vertragsjahr"] < 18]) == ZEUGE_930004_VOR_T
    assert _fingerabdruck(led[led["vertragsjahr"] >= 18]) == ZEUGE_930004_AB_T


def test_eine_teilkuendigungsrate_verschiebt_weder_hauptstrom_noch_herabsetzung(welten):
    """Dieselbe Welt mit und ohne Teilkuendigungsrate: Bis zur ersten
    Teilkuendigung einer Police sind ihre Buchungen identisch — Hauptstrom
    (Tod, Storno, PEX, Erhoehung) und Herabsetzungsstrom laufen unberuehrt."""
    ohne = _welt(PROSPEKTIV, tk_rate=0.0)[4].ledger
    mit = welten[PROSPEKTIV][4].ledger
    erste_tku = mit[mit["ereignis"] == "TKU"].groupby("police_id")["vertragsjahr"].min()
    assert len(erste_tku) >= 3
    for pid in POLICEN:
        grenze = int(erste_tku.get(pid, 10 ** 6))
        a = ohne[(ohne["police_id"] == pid) & (ohne["vertragsjahr"] < grenze)].reset_index(drop=True)
        b = mit[(mit["police_id"] == pid) & (mit["vertragsjahr"] < grenze)].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b)


def test_herabsetzung_und_teilkuendigung_ziehen_unabhaengig():
    """Bei gleicher Rate fallen die beiden Vorgaenge NICHT auf dieselben
    Policen und Jahre: die erste Treffer-Folge je Police aus den beiden
    Stroemen unterscheidet sich (bei gleichen Stromwerten waere sie
    identisch — perfekte Abhaengigkeit)."""
    seed = _config(PROSPEKTIV).seed

    def erster_treffer(strom: int, pid: int) -> int:
        rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([seed, strom, pid])))
        return next((j for j in range(12, 25) if rng.random() < RATE_DER_WELT), -1)

    paare = [(erster_treffer(HERABSETZUNG_STREAM, p), erster_treffer(TEILKUENDIGUNG_STREAM, p))
             for p in POLICEN]
    gleich = sum(1 for a, b in paare if a == b and a != -1)
    verschieden = sum(1 for a, b in paare if a != b)
    assert verschieden > len(POLICEN) // 2 and gleich < len(POLICEN) // 4, (gleich, verschieden)


def test_das_stromregister_ist_eindeutig_und_vollstaendig():
    """Ein Register (``bestand.zufallsstroeme``), aus dem jedes Modul liest:
    keine ``*_STREAM``-Konstante unter src/ traegt einen eigenen Zahlenwert
    (AST), die Werte sind eindeutig, und die fuenf frueheren Werte sind exakt
    die alten (Bitgleichheit). Positivkontrolle: zwei gleiche Werte brechen
    die Pruefung des Registers."""
    from rechner_pipeline.bestand import zufallsstroeme as z

    assert dict(z.STROEME) == {
        "ereignis": 424242, "herabsetzung": 606606, "teilkuendigung": 313131,
        "neuzugang": 771177, "meldeverzug": 552211, "neugeschaeft": 918273}
    src = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"
    eigene = []
    for p in sorted(src.rglob("*.py")):
        for k in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if (isinstance(k, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id.endswith("_STREAM") for t in k.targets)
                    and isinstance(k.value, ast.Constant)):
                eigene.append(str(p.relative_to(src)))
    assert eigene == []
    with pytest.raises(z.StromKollision):
        z._pruefe_eindeutig({"a": 1, "b": 1})


# --------------------------------------------------------------------------- #
# Bindung an das System (P-B1 und Fuehrungsprobe dieselbe Regel)
# --------------------------------------------------------------------------- #


def test_der_uebernommene_tarif_kennt_nur_die_teilkuendigung():
    """Entscheid des Maintainers 2026-10-01 (A1 ersetzt): Der uebernommene
    Tarif (``red_verfahren = teilkuendigung``) kennt EINEN Vorgang — die
    Teilkuendigung, aus ihrer eigenen Rate. Die Herabsetzungsrate zieht dort
    nichts (keine doppelte Rate); eine TKU ohne Teilkuendigungsrate ist
    unbelegt, auch wenn eine Herabsetzungsrate steht; eine RED dort ist ein
    Befund. Mutationsproben: den Herabsetzungsstrom fuer diesen Tarif wieder
    als TKU ausfuehren -> rot (erste Aussage); ``auch_erzeugt`` zurueck -> rot
    (dritte Aussage)."""
    welt = _welt(TEILKUENDIGUNG, tk_rate=0.0)
    config, stamm, schichten, verankerung, erg = welt
    assert config.annahmen.herabsetzung(0.0) > 0.0
    assert not erg.ledger["ereignis"].isin(["RED", "TKU"]).any() and len(erg.reduktionen) == 0
    mit_tk = _welt(TEILKUENDIGUNG)
    assert (mit_tk[4].ledger["ereignis"] == "TKU").any()
    assert _pb1(mit_tk, mit_tk[4].ledger) == []
    nur_red_rate = copy.deepcopy(mit_tk[0])
    nur_red_rate.annahmen.teilkuendigung = Annahme(a=0.0, b=0.0)
    from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
    from tests.test_herabsetzung_ausfinanziert import _voll

    m = mit_tk
    fehler = pruefe_ledger_betraege(
        m[1], _voll(m, m[4].ledger), nur_red_rate, scheiben=m[4].scheiben,
        historie=m[4].historie, schichten=m[2], verankerung=m[3],
        reduktionen=m[4].reduktionen)
    assert any("annahmen.teilkuendigung" in f for f in fehler), fehler[:3]
    an = copy.deepcopy(config.annahmen)
    assert any("keine Beitragsherabsetzung kennt" in f for f in red_bindung_fehler(
        1, 5, ANTEIL, PROSPEKTIV, beitragsdauer=12,
        generation_verfahren=TEILKUENDIGUNG, annahmen=an))


@pytest.mark.parametrize("jahr,soll", [(11, []), (12, ["nach dem Beitragsende"])])
def test_die_bindung_haelt_die_herabsetzung_an_der_grenze_t(jahr, soll):
    an = _config(PROSPEKTIV).annahmen
    fehler = red_bindung_fehler(1, jahr, ANTEIL, PROSPEKTIV, beitragsdauer=12,
                                generation_verfahren=PROSPEKTIV, annahmen=an)
    assert [s for s in soll if any(s in f for f in fehler)] == soll and (bool(fehler) == bool(soll)), fehler


# --------------------------------------------------------------------------- #
# Migrationszugang: A2 und die Grenzen der Vorgeschichte
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("quelle,jahr,pex,tk", [
    (PROSPEKTIV, T - 1, None, False), (PROSPEKTIV, T, None, True),
    (MIT_ABZUG, N_K - 1, None, True),
    (TEILKUENDIGUNG, 1, None, True), (TEILKUENDIGUNG, T - 1, None, True),
    # B5: nach der Beitragsfreistellung immer die Teilkuendigung — beide Grenzen.
    (PROSPEKTIV, T - 4, T - 4, True), (PROSPEKTIV, T - 5, T - 4, False),
    (MIT_ABZUG, T - 2, T - 4, True), (TEILKUENDIGUNG, 1, 5, True),
])
def test_a2_welcher_vorgang_eine_alt_absetzung_war(quelle, jahr, pex, tk):
    """Die EINE Uebersetzungsregel (A2, B5): Kennt die Quelle nur die
    Teilkuendigung, war jede Absetzung eine; sonst vor dem Beitragsende und
    vor der Beitragsfreistellung eine Herabsetzung, danach eine
    Teilkuendigung. Mutationsproben: ``jahr >= t`` -> ``jahr > t`` -> rot;
    ``jahr >= beitragsfrei_ab`` -> ``>`` -> rot."""
    from rechner_pipeline.models.bestand import zielverfahren

    assert alt_absetzung_ist_teilkuendigung(quelle, jahr, T, beitragsfrei_ab=pex) is tk
    assert zielverfahren(quelle, jahr, T, beitragsfrei_ab=pex) == (TEILKUENDIGUNG if tk else quelle)


def test_die_uebersetzungsregel_hat_keinen_default_fuer_die_freistellung():
    """Wer die Regel fragt, sagt, ob der Vertrag beitragsfrei war — ein
    vergessenes Argument faellt, statt still "nicht beitragsfrei" zu lesen."""
    with pytest.raises(TypeError):
        alt_absetzung_ist_teilkuendigung(PROSPEKTIV, T - 1, T)  # type: ignore[call-arg]


@pytest.mark.parametrize("verfahren", VERFAHREN)
@pytest.mark.parametrize("jahr", [T, N_K - 1])
def test_mit_auskunft_ist_die_ursprungssumme_erlsumme_durch_f(verfahren, jahr):
    from rechner_pipeline.bestand.migrationszugang import leite_ursprungssumme_ab

    assert leite_ursprungssumme_ab(FELDER, jahr=jahr, erlsumme=41_250.0, anteil=0.75,
                                   verfahren=verfahren) == pytest.approx(55_000.0, rel=1e-15)


def test_die_teilkuendigung_vor_t_ist_mit_auskunft_ebenso_bestimmt():
    """Nachbarfall: unter dem Verfahren teilkuendigung VOR t lief die Ableitung
    in die Umwandlungs-Zweige und fand keinen Kandidaten (ca61419: Abbruch)."""
    from rechner_pipeline.bestand.migrationszugang import leite_ursprungssumme_ab

    assert leite_ursprungssumme_ab(FELDER, jahr=T - 5, erlsumme=30_000.0, anteil=0.6,
                                   verfahren=TEILKUENDIGUNG) == pytest.approx(50_000.0, rel=1e-15)


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_ohne_auskunft_verweigert_die_ableitung_mit_dem_ausweg(verfahren):
    from rechner_pipeline.bestand.migrationszugang import (
        MigrationszugangFehler,
        kalibriere_absetzung_aus_dk,
        leite_absetzung_ab,
    )

    with pytest.raises(MigrationszugangFehler, match="--red-anteile-datei"):
        leite_absetzung_ab(FELDER, jahr=T + 1, erlsumme=41_250.0, jbrutto=0.0,
                           verfahren=verfahren)
    with pytest.raises(MigrationszugangFehler, match="--red-anteile-datei"):
        kalibriere_absetzung_aus_dk(FELDER, jahr=T + 1, erlsumme=41_250.0, dk_ist=30_000.0,
                                    monate_dk=12 * (T + 2), verfahren=verfahren)


def test_vor_t_bleibt_die_ableitung_der_herabsetzung_unveraendert():
    from rechner_pipeline.bestand.migrationszugang import leite_absetzung_ab

    red = reduziere(Rechenkern(dataclasses.replace(MP, sum_insured=60_000.0)),
                    T - 1, 0.5, verfahren=PROSPEKTIV)
    ab = leite_absetzung_ab(FELDER, jahr=T - 1, erlsumme=round(red.vs_neu, 2),
                            jbrutto=round(red.bjb_neu, 2), verfahren=PROSPEKTIV)
    assert ab.anteil == pytest.approx(0.5, abs=1e-9)
    assert ab.vs_alt == pytest.approx(60_000.0, abs=0.5)


def _serie(verfahren, *, mit_auskunft=True, red_jahr=T + 2, tku_umfang=None, folge=None):
    from rechner_pipeline.gates.migrationssuite_lauf import _serienzustand

    folge = folge or [("ERH", 3, "01.01.2003"), ("ERH", 5, "01.01.2005"),
                      ("RED", red_jahr, "01.01.2022")]
    je_datum = {"P1": {"01.01.2022": 0.6, "01.01.2004": 0.8}} if mit_auskunft else {}
    return _serienzustand(
        "P1", folge, dict(FELDER), erlsumme=70_000.0, erhoehungssatz=0.05,
        red_anteile={}, red_anteile_je_datum=je_datum, red_verfahren=verfahren,
        tku_umfang=tku_umfang)


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_eine_serie_mit_alt_herabsetzung_nach_t_ist_in_jeder_generation_ableitbar(verfahren):
    """A2: nach t eine Teilkuendigung; der Anteil kommt aus der Auskunft und
    DECKT die Struktur (``gedeckt_durch``, Pflichtschicht der Abnahmen). Ohne
    Auskunft: verweigert mit dem Ausweg.

    Welche Bausteine sie kuerzt, sagt das Tarifwerk (Entscheid B1 vom
    2026-10-01): Der uebernommene Tarif kuendigt nur die Grundversicherung
    (Grund mit f, Scheiben unveraendert) — mit dem Merkmal benannt in jeder
    Generation dasselbe; die eigenen Tarife der PLV kuerzen alle Bausteine.
    Kontrollen geschlossen gerechnet, ohne die Ableitung."""
    from rechner_pipeline.bestand.migrationszugang import MigrationszugangFehler

    grund_umfang = _serie(verfahren, tku_umfang="grundversicherung")
    assert grund_umfang == _serie(TEILKUENDIGUNG)
    assert grund_umfang["gedeckt_durch"] == "auskunft"
    g = 70_000.0 / (0.6 + 0.05 + 0.05 * 1.05)
    assert dict(grund_umfang["scheiben"])[3] == pytest.approx(0.05 * g, abs=0.01)
    assert grund_umfang["sum_insured"] == pytest.approx(0.6 * g, abs=0.02)

    alle = _serie(verfahren, tku_umfang="alle_bausteine")
    g_alle = 70_000.0 / (0.6 * (1.0 + 0.05 + 0.05 * 1.05))
    assert "vorgaenge" not in alle                       # zustandslos in IST-Summen
    assert alle["gedeckt_durch"] == "auskunft"
    assert dict(alle["scheiben"])[3] == pytest.approx(0.6 * 0.05 * g_alle, abs=0.01)
    assert dict(alle["scheiben"])[5] == pytest.approx(0.6 * 0.05 * 1.05 * g_alle, abs=0.01)
    assert alle["sum_insured"] == pytest.approx(0.6 * g_alle, abs=0.02)
    assert alle["sum_insured"] + sum(dict(alle["scheiben"]).values()) == pytest.approx(
        70_000.0, abs=0.005)
    if verfahren != TEILKUENDIGUNG:
        assert _serie(verfahren) == alle                 # Vorgabe der PLV-Verfahren
    with pytest.raises(MigrationszugangFehler, match="--red-anteile-datei"):
        _serie(verfahren, mit_auskunft=False)


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_eine_serie_mit_herabsetzung_vor_t_wird_als_geteilter_vertrag_abgeleitet(verfahren):
    """B5: Kennt die Quelle eine echte Herabsetzung, ist der Vertrag nach
    einer Absetzung vor t GETEILT. Vorher verweigert ("die Serien-Ableitung
    kennt nur die Teilkuendigung"); jetzt traegt der Zustand Ursprungssummen
    und Vorgaenge. Kontrolle UNABHAENGIG von der Vorgangsfolge: der
    Rechenweg vor ihr (``reduzierte_teile``, eine Herabsetzung ueber Grund
    und Scheiben) muss mit dieser Struktur die gelieferte Summe treffen."""
    from rechner_pipeline.kern.beitragsreduktion import reduzierte_teile

    zustand = _serie(verfahren, red_jahr=T - 1)
    assert zustand["vorgaenge"] == ((T - 1, 0.6, verfahren),)
    assert zustand["gedeckt_durch"] == "auskunft"
    grund = Rechenkern(dataclasses.replace(MP, sum_insured=zustand["sum_insured"]))
    scheiben = [(j, Rechenkern(erhoehungs_scheibe(MP, j, vs))) for j, vs in zustand["scheiben"]]
    teile = reduzierte_teile(grund, scheiben, T - 1, 0.6, verfahren)
    assert sum(t.reduktion.vs_neu for _, t in teile) == pytest.approx(70_000.0, abs=0.02)
    # Die Erhoehungen folgen der Regel der Engine: Satz x gefuehrte Summe davor.
    assert dict(zustand["scheiben"])[3] == pytest.approx(0.05 * zustand["sum_insured"], abs=0.01)


def test_eine_serie_mit_teilkuendigung_nach_pex_bleibt_die_ein_punkt_inversion():
    """B5: nach der Beitragsfreistellung war jede gelieferte Absetzung eine
    Teilkuendigung der beitragsfreien Summe. Vorher fiel die Serie hart ("PEX
    nicht terminal"); jetzt bestimmt die gelieferte (gekuerzte) Summe die
    Aequivalenzsumme wie bei terminaler Freistellung."""
    from rechner_pipeline.bestand.migrationszugang import leite_pex_ursprungssumme_ab

    folge = [("ERH", 3, "01.01.2003"), ("PEX", 6, "01.01.2006"), ("RED", 9, "01.01.2009")]
    zustand = _serie(PROSPEKTIV, folge=folge)
    assert zustand["beitragsfrei_seit_jahr"] == 6
    assert zustand["sum_insured"] == leite_pex_ursprungssumme_ab(
        dict(FELDER), pex_jahr=6, vs_bfr=70_000.0)
    assert zustand["quell_komponenten"] == 2
    with pytest.raises(SystemExit, match="nichts mehr um"):
        _serie(PROSPEKTIV, folge=[("PEX", 6, "01.01.2006"), ("ERH", 7, "01.01.2007")])


@pytest.mark.parametrize("art,jahr,datum,teil", [
    ("RED", 0, "2015-01-01", "Versicherungsbeginn"),
    ("RED", 25, "2040-01-01", "Ablauf"),
    ("RED", 24, "2039-01-01", "nach dem Stichtag"),
    ("PEX", 30, "2045-01-01", "Ablauf"),
    ("RED", 11, "2026-01-01", None),
    ("ERH", 1, "2016-01-01", None),
])
def test_b2_die_grenzen_der_vorgeschichte_an_einer_stelle(art, jahr, datum, teil):
    """Pruefer-Befund B2: eine Alt-Absetzung nach dem Stichtag, am oder nach
    dem Ablauf wurde ohne Meldung uebernommen. Jetzt prueft EINE Funktion vor
    jeder Verzweigung, fuer jeden Vorgang: 0 < Jahr < n, Datum <= Stichtag.
    Mutationsproben: ``jahr >= n`` -> ``jahr > n`` (Jahr n laeuft) -> rot;
    ``datum > zugang`` -> ``datum >= zugang`` (Stichtag selbst verweigert)
    -> rot."""
    from rechner_pipeline.gates.migrationssuite_lauf import vorgeschichte_grenzfehler

    zeile = pd.Series({"duration": 25, "bestandszugang": pd.Timestamp("2026-01-01")})
    befund = vorgeschichte_grenzfehler(art, jahr, pd.Timestamp(datum).date(), zeile)
    if teil is None:
        assert befund is None
    else:
        assert befund is not None and teil in befund and "Lieferung klaeren" in befund


def test_b1_unbestimmte_anfangszustaende_werden_verweigert_mit_dem_ausweg():
    """Pruefer-Befund B1, als Klasse: Jede Warnung der Ableitung fuehrt zur
    Verweigerung, nie zu einem still zustandslosen Vertrag."""
    from rechner_pipeline.gates.migrationssuite_lauf import (
        AnfangszustandUnbestimmt,
        verweigere_unbestimmte,
    )

    verweigere_unbestimmte([])
    with pytest.raises(AnfangszustandUnbestimmt, match="--red-anteile-datei"):
        verweigere_unbestimmte(["Police 1 (Serie): JBRUTTO <= 0"])


# --------------------------------------------------------------------------- #
# Pruefstrecke: Migrationssuite und aktuarieller Test
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("art,quelle,jahr", [
    ("RED", PROSPEKTIV, T + 2), ("RED", MIT_ABZUG, T + 2), ("TKU", PROSPEKTIV, T + 2),
    ("TKU", PROSPEKTIV, T - 3),
])
def test_migrationssuite_rechnet_die_teilkuendigung_des_pruefzeitraums(art, quelle, jahr):
    """Ein geliefertes TKU ist die Teilkuendigung; ein geliefertes RED nach t
    liest A2. Folgestichtag: der Vertrag f x S."""
    from rechner_pipeline.qa.migrationssuite import GeVoErwartung, VertragsPruefung, pruefe_vertrag

    s1, s2 = 12 * (jahr - 1) + 3, 12 * jahr + 3
    urteil = pruefe_vertrag(VertragsPruefung(
        police_id="P-1", model_point=dict(FELDER),
        monate_stichtag_1=s1, monate_stichtag_2=s2,
        dk_erwartet_1=round(Rechenkern(MP).monatsreserve(s1).vx_mrv, 2),
        dk_erwartet_2=round(_folgekern().monatsreserve(s2).vx_mrv, 2),
        bjb_erwartet_1=(round(Rechenkern(MP).gross_annual_premium(), 2) if s1 < 12 * T else 0.0),
        gevos=(GeVoErwartung(art=art, monate=12 * jahr, betrag_erwartet=None, anteil=F),),
    ), red_verfahren=quelle)
    assert urteil["bestanden"], urteil["befunde"]


@pytest.mark.parametrize("anlass,quelle,jahr", [
    ("RED", PROSPEKTIV, T + 3), ("TKU", PROSPEKTIV, T - 3), ("TKU", MIT_ABZUG, T + 3),
])
def test_a_m3_misst_den_ddk_der_teilkuendigung(anlass, quelle, jahr):
    """A-M3: ein eigener Pruefpunkt je Vorgang; dDK = -(1-f) x kVx_MRV."""
    from rechner_pipeline.qa.aktuarieller_test import Pruefpunkt, Vertragspruefung, pruefe_vertrag
    from rechner_pipeline.qa.testprofil import Kriterium, Testprofil

    soll = -(1 - F) * Rechenkern(MP).zustand_am(12 * jahr).vx_mrv
    punkt = Pruefpunkt(monate=12 * jahr, erwartet={"dDK": round(soll, 2)},
                       anlass=anlass, parameter={"anteil": F})
    v = Vertragspruefung(police_id="P1", model_point=dict(FELDER),
                         historientyp="ohne_gevo", punkte=(punkt,))
    profil = Testprofil(kennung="A-M3", weite="vollbestand", kriterien={},
                        grundtoleranz=Kriterium(abs_tol=0.005, rel_tol=1e-9))
    urteil = pruefe_vertrag(v, profil, red_verfahren=quelle)
    assert urteil["bestanden"], urteil["befunde"]


# --------------------------------------------------------------------------- #
# Ratschen: die Aufzaehler der Ereigniscodes
# --------------------------------------------------------------------------- #

SRC = Path(__file__).resolve().parents[1] / "src" / "rechner_pipeline"
CODES = set(EREIGNIS_VALUES)
ARTEN = {"VS_herabsetzung", "VS_teilkuendigung", "dDK_absorption",
         "RKW_teilkuendigung", "Kappung_teilkuendigung"}

#: Inventar (AST, gemessen nach dem Bau): je Modul die Zahl der Aufzaehlungen
#: von Ereigniscodes (Tupel, Listen, Mengen, Dict-Schluessel mit mindestens
#: zwei Codes), der Verzweigungen nach ``"RED"``/``"TKU"`` und der
#: Betragsart-Literale der beiden Vorgaenge. Vorher (ca61419) siehe die
#: Rueckgabe des Baus. ``==``: ein neuer Aufzaehler ist ein Befund.
#:
#: Nachgemessen mit der Vorgangsfolge (Entscheid 2026-10-01), je Aenderung
#: begruendet: migrationszugang +2 Verzweigungen nach dem QUELLcode ``RED``
#: (Provenienzname der Lieferung: welche Ereignisse die Serie ueber die
#: Vorgangsfolge ableitet); fuehrungsprobe -1 (der Vergleich laeuft ueber
#: ``PEX_CODE``/``RED_CODE`` an einer Stelle); aktuarieller_test +1
#: Aufzaehlung (``VORGANG_ANLAESSE``, die eine Stelle der Frage "ist dieser
#: Punkt ein Vorgang?") und +1 Verzweigung (ein gelieferter TKU-Punkt ist die
#: Teilkuendigung); migrationssuite +1 Aufzaehlung (``VORGANG_ARTEN``, dieselbe
#: Frage fuer die GeVos), die Verzweigungen nach "zweite Herabsetzung" und
#: "Folge-GeVo" sind entfallen.
#:
#: Pruefrunde G (Fund G02): beitragsreduktion +1 Aufzaehlung
#: (``VORGANGSJAHR_OBERGRENZE``, die eine Stelle der Jahresgrenzen aller
#: Vorgangsarten; ``tests/test_runde_g_vorgaenge.py`` haelt sie mit ``==``
#: gegen ``vorgangsfolge.RANG``); keine Verzweigung nach RED/TKU.
INVENTAR = {
    "bestand/cli_fortschreibung.py": (0, 0, 1),
    "bestand/ereignisse.py": (0, 2, 5),
    "bestand/kennzahlen.py": (4, 4, 4),
    "bestand/ledger_bindung.py": (7, 1, 0),
    "bestand/migrationszugang.py": (1, 5, 0),
    "bestand/report.py": (1, 0, 0),
    "bestand/vorbedingungen.py": (1, 0, 1),
    "betrieb/seite.py": (1, 0, 0),
    "gates/bestand_uebernehmen.py": (4, 0, 0),
    "gates/fuehrungsprobe.py": (1, 0, 0),
    "gates/migrationssuite_lauf.py": (1, 7, 0),
    "kern/beitragsreduktion.py": (1, 0, 0),
    "kern/korrekturschicht.py": (1, 0, 0),
    "models/bestand.py": (12, 2, 14),
    # T-Box 0.2.0 (Entwurf, ADR-024): der Katalog der Geschaeftsvorfaelle und
    # die Vertrags-/Migrationsvokabeln SPIEGELN die Mengen des Datenmodells;
    # ``tests/test_tbox_erweiterung_020.py`` haelt jede Spiegelung mit ``==``.
    "ontologie/tbox.py": (4, 0, 6),
    "qa/aktuarieller_test.py": (3, 1, 0),
    "qa/migrationssuite.py": (5, 1, 0),
}
#: Die VOLLSTAENDIGEN Aufzaehlungen (alle Codes): Hier faellt der naechste
#: neue Code an EINER Stelle auf — dieser Test nennt jede, die ihn nicht kennt.
#: Dritter Eintrag: die Codes, die eine Aufzaehlung BEGRUENDET nicht fuehrt
#: (die Korrekturschicht heilt Vorfaelle am laufenden Vertrag; der Zugang
#: ist keiner).
VOLLSTAENDIG = (
    ("rechner_pipeline.models.bestand", "EREIGNIS_VALUES", set()),
    ("rechner_pipeline.models.bestand", "BETRAG_ART_JE_EREIGNIS", set()),
    ("rechner_pipeline.bestand.kennzahlen", "EREIGNIS_REIHENFOLGE", set()),
    ("rechner_pipeline.bestand.kennzahlen", "EREIGNIS_LABELS", set()),
    ("rechner_pipeline.bestand.report", "_EREIGNIS_FARBEN", set()),
    ("rechner_pipeline.betrieb.seite", "EREIGNIS_TITEL", set()),
    ("rechner_pipeline.kern.korrekturschicht", "HEILUNG", {"ZUG"}),
    ("rechner_pipeline.ontologie.tbox", "GESCHAEFTSVORFAELLE", set()),
)


def _messen(quelle: str):
    baum = ast.parse(quelle)
    aufz = verzw = arten = 0
    for k in ast.walk(baum):
        elts = (k.elts if isinstance(k, (ast.Tuple, ast.List, ast.Set))
                else k.keys if isinstance(k, ast.Dict) else None)
        if elts is not None and len({e.value for e in elts if isinstance(e, ast.Constant)}
                                    & (CODES | {"TKU"})) >= 2:
            aufz += 1
        if isinstance(k, ast.Compare):
            verzw += sum(1 for x in [k.left, *k.comparators]
                         if isinstance(x, ast.Constant) and x.value in ("RED", "TKU"))
        if isinstance(k, ast.Constant) and k.value in ARTEN:
            arten += 1
    return aufz, verzw, arten


def test_ratsche_positivkontrolle_des_inventars():
    probe = ('X = ("RED", "STO")\nif a == "TKU": pass\nY = {"PEX": 1, "TOD": 2}\n'
             'z = "VS_teilkuendigung"\n')
    assert _messen(probe) == (2, 1, 1)
    assert _messen("X = ('RED',)\n") == (0, 0, 0)


def test_ratsche_inventar_der_aufzaehler():
    gemessen = {}
    for p in sorted(SRC.rglob("*.py")):
        wert = _messen(p.read_text(encoding="utf-8"))
        if any(wert):
            gemessen[str(p.relative_to(SRC))] = wert
    assert gemessen == INVENTAR


def test_jede_vollstaendige_aufzaehlung_kennt_jeden_code():
    """Der naechste neue Ereigniscode faellt HIER auf, einmal, mit jeder Stelle,
    die ihn nicht kennt. Positivkontrolle: ein erfundener Code fehlt ueberall."""
    import importlib

    fehlt = {}
    for modul, name, ohne in VOLLSTAENDIG:
        menge = set(getattr(importlib.import_module(modul), name))
        if menge != CODES - ohne:
            fehlt[f"{modul}.{name}"] = sorted(CODES - ohne ^ menge)
    assert fehlt == {}
    for modul, name, _ in VOLLSTAENDIG:
        assert "XYZ" not in set(getattr(importlib.import_module(modul), name))


#: Pruefer-Befund B3: die Ratsche zaehlt je AUFRUFSTELLE, nicht je Modul.
#: Jede Stelle der Frage "welcher Vorgang war die gelieferte Absetzung?"
#: (die EINE Uebersetzungsregel, A2/B5; ``zielverfahren`` ist dieselbe Regel
#: in der Form des Verfahrens) hat einen Verhaltenstest, der rot wird, wenn
#: genau diese Stelle die alte Frage stellt (nur das Verfahren der Quelle,
#: ohne Jahr oder Freistellung): migrationszugang 3 + 2 (Ableitung ohne
#: Auskunft, Kalibrierung — ``test_ohne_auskunft_verweigert...``;
#: Ursprungssumme mit Auskunft — ``test_mit_auskunft...``; Serie ueber die
#: Folge — ``test_eine_serie...``), migrationssuite_lauf 1 (Einzelfall der
#: Uebernahme — die e2e-Kette), models/bestand 1 (``zielverfahren`` selbst),
#: qa/migrationssuite 1 (``test_migrationssuite_rechnet...``),
#: qa/aktuarieller_test 1 (``test_a_m3...``).
#: ``reduktion_ereignis`` (Code aus dem Verfahren): nachgemessen mit der
#: Vorgangsfolge — die Leser fragen den Code je Zeile der Folge, nicht mehr je
#: Police; migrationszugang 1 (Serie ueber die Folge), tageslauf 1 (Schnitt
#: je Police, Datum und Code).
AUFRUFSTELLEN = {
    "alt_absetzung_ist_teilkuendigung": {
        "bestand/migrationszugang.py": 3,
        "gates/migrationssuite_lauf.py": 1,
        "models/bestand.py": 1,
    },
    "zielverfahren": {
        "bestand/migrationszugang.py": 2,
        "qa/migrationssuite.py": 1,
        "qa/aktuarieller_test.py": 1,
    },
    "reduktion_ereignis": {
        "bestand/ereignisse.py": 1,
        "bestand/ledger_bindung.py": 2,
        "bestand/migrationszugang.py": 1,
        "betrieb/tageslauf.py": 1,
        "gates/fuehrungsprobe.py": 2,
        "models/bestand.py": 2,
    },
}


def _aufrufe(quelle: str, name: str) -> int:
    return sum(1 for k in ast.walk(ast.parse(quelle))
               if isinstance(k, ast.Call) and (
                   (isinstance(k.func, ast.Name) and k.func.id == name)
                   or (isinstance(k.func, ast.Attribute) and k.func.attr == name)))


def test_ratsche_aufrufstellen_der_vorgangsfrage():
    assert _aufrufe("f(1)\nif a and f(2): pass\nx.f(3)\ng(1)\n", "f") == 3   # Positivkontrolle
    for name, soll in AUFRUFSTELLEN.items():
        gemessen = {}
        for p in sorted(SRC.rglob("*.py")):
            n = _aufrufe(p.read_text(encoding="utf-8"), name)
            if n:
                gemessen[str(p.relative_to(SRC))] = n
        assert gemessen == soll, name
