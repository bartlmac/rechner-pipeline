"""Die Herabsetzung im ausfinanzierten Nachlauf — Entscheid des Maintainers 2026-09-30.

Ein ausfinanzierter Vertrag (Beitragszahlungsdauer t abgelaufen, Jahr >= t,
kein PEX) KANN herabgesetzt werden. Das Datenmodell und die Pruefstrecke
liessen das seit Fund N6 (Kern 3.4.0) zu und rechneten es nach; die
Simulationsengine zog sie nie (``j + 1 < t`` vor dem Draw) — ein Vertrag,
den die Pruefstrecke akzeptiert und die Fuehrung nie erzeugt, ist eine
Luecke zwischen Zusage und Lauf.

GEMESSEN VOR DEM BAU (Kern 3.4.0): Was nach t definiert ist, ist allein die
Teilkuendigung. ``reduziere`` verweigert ``prospektiv`` und ``mit_abzug``
ab ``jahr >= t`` ("es gibt keinen Beitrag zu reduzieren"), das Datenmodell
weist sie ab, und der Tarifplan (klv.md 7.1) sagt nach t nichts: Beide
Verfahren wandeln den freiwerdenden BEITRAGSanteil (1-f) um, und nach t gibt
es keinen Beitrag, den ein Anteil f fortfuehren koennte. Die Engine zieht
deshalb nach t nur fuer das Verfahren, das der Kern traegt; fuer die beiden
anderen bleibt es beim Stand (Annahme in klv.md 7.1, der Maintainer
entscheidet nach). Die Untergrenze dieser Aussage ist eine Ratsche: Die
Menge der Verfahren, die nach t gezogen werden, ist DIESELBE, die der Kern
und das Datenmodell dort zulassen — kein Verfahren darf in der Engine
vorankommen, ohne dass Kern und Datenmodell es tragen, und keins darf dort
zugelassen sein, ohne dass die Engine es zieht.

Die Zusage, gegen die hier gemessen wird, ist unabhaengig aufgebaut (wie in
test_t27_teilkuendigung_klasse): nach der Teilkuendigung ist der Vertrag die
Grundversicherung mit Summe f x S als gewoehnlicher Rechenkern plus seine
unveraenderten Erhoehungsscheiben; ausgezahlt wird (1-f) x Rueckkaufswert
der Grundscheibe plus die absorbierte Schicht.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import einzelwerte_am
from rechner_pipeline.bestand import cli_fortschreibung
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ereignisse import HERABSETZUNG_STREAM, fortschreiben
from rechner_pipeline.bestand.kennzahlen import bewegungskonto
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    NACH_BEITRAGSENDE_DEFINIERT,
    PROSPEKTIV,
    TEILKUENDIGUNG,
    VERFAHREN,
    BeitragsreduktionFehler,
    reduziere,
)
from rechner_pipeline.kern.korrekturschicht import schichtwert_bei
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    model_point_kwargs,
    validate_reduktionen,
)
from tests.test_bestand_uebernommen_fortschreiben import _CONFIG_TOML, _stamm
from tests.test_baldrian2_e2e import STICHTAG_2
from tests.test_herabsetzung_in_fuehrung import ANTEIL, BIS
from tests.test_schicht_in_fuehrung import MONATE_TA, _parameter, _tabellen
from tests.test_t27_pruefstrecke_runde_c import (  # noqa: F401
    _pb1 as _baldrian_pb1,
    _probe_datei as _baldrian_probe,
    _tabellen as _baldrian_tabellen,
    gefahrener_fall,
    welt as fall_welt,
)
from tests.test_t27_teilkuendigung_klasse import (
    _folgevertrag,
    _scheiben_kerne,
    _scheiben_vor,
    _soll_rkw,
)

N = 25
#: Beitragszahlungsdauern der Welt: t = 12 liegt genau ein Jahr nach dem
#: Zugang (Vertragsjahr 11) — das erste Reduktionsjahr ist dort schon
#: Nachlauf; 15 und 20 lassen Jahre davor und danach.
T_JE_POLICE = (12, 15, 20)
POLICEN = list(range(910_001, 910_061))
#: Herabsetzungsrate der Welt (Vorgabe von ``_config``/``_toml``).
RATE_DER_WELT = 0.08


def _t(pid: int) -> int:
    return T_JE_POLICE[pid % len(T_JE_POLICE)]


def _toml(verfahren: str, rate: float, *, still: bool = False) -> str:
    """Die Config der Uebernahme-Welt mit Verfahren und Herabsetzungsrate.

    ``still`` legt alle anderen Ausscheideursachen und die Dynamik still:
    Die Welt ist dann deterministisch genug, um Grenzen festzunageln.
    """
    anker = '[[generation]]\nname = "klv/zellen"\n'
    assert anker in _CONFIG_TOML
    toml = _CONFIG_TOML.replace(
        anker, anker + f'red_verfahren = "{verfahren}"\nstoab_je_baustein = true\n', 1,
    ).replace(
        "[annahmen]\nerh_prozent = 0.05",
        f"[annahmen]\nerh_prozent = 0.05\nred_anteil = {ANTEIL}",
    ) + f"\n[annahmen.herabsetzung]\na = {rate}\nb = 0.0\n"
    if still:
        for alt, neu in (
            ("[annahmen.storno]\na = 0.02", "[annahmen.storno]\na = 0.0"),
            ("[annahmen.beitragsfreistellung]\na = 0.02",
             "[annahmen.beitragsfreistellung]\na = 0.0"),
            ("[annahmen.tod]\na = 0.0\nb = 1.0", "[annahmen.tod]\na = 0.0\nb = 0.0"),
            ("[annahmen.erhoehung]\na = 0.05", "[annahmen.erhoehung]\na = 0.0"),
        ):
            assert alt in toml, alt
            toml = toml.replace(alt, neu)
    return toml


def _config(verfahren: str, rate: float = RATE_DER_WELT, *, still: bool = False):
    config = config_aus_text(_toml(verfahren, rate, still=still))
    assert config.validate() == []
    return config


def _welt_bauen(verfahren: str):
    config = _config(verfahren)
    stamm = _stamm([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01",
                     "n": N, "t": _t(p)} for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


@pytest.fixture(scope="module")
def welt():
    """Teilkuendigung, Vertraege mit t < n — die Welt des Zaehltests."""
    return _welt_bauen(TEILKUENDIGUNG)


@pytest.fixture(scope="module")
def welten():
    """Dieselbe Welt, dieselbe Rate, je Verfahren — fuer die Ratsche."""
    return {v: _welt_bauen(v) for v in VERFAHREN}


def _nachlauf(stamm: pd.DataFrame, erg) -> pd.DataFrame:
    """Die Reduktionen ab dem Ende der Beitragszahlung (Jahr >= t)."""
    t = stamm.set_index("police_id")["premium_duration"]
    red = erg.reduktionen
    return red[red["reduktion_jahr"].to_numpy() >= t.loc[red["police_id"]].to_numpy()]


def _red_ab_t(stamm: pd.DataFrame, ledger: pd.DataFrame) -> pd.DataFrame:
    t = stamm.set_index("police_id")["premium_duration"]
    red = ledger[ledger["ereignis"] == "RED"]
    return red[red["vertragsjahr"].to_numpy() >= t.loc[red["police_id"]].to_numpy()]


# --------------------------------------------------------------------------- #
# Der Zaehltest: die Engine zieht die Herabsetzung im Nachlauf
# --------------------------------------------------------------------------- #


def test_die_engine_zieht_die_teilkuendigung_im_ausfinanzierten_nachlauf(welt):
    """Welt mit Herabsetzungsrate und Vertraegen mit t < n: es gibt RED-
    Buchungen mit vertragsjahr >= t (vorher 0). Je Instanz: jede Reduktion
    ab t hat ihre Summen- UND ihre Auszahlungszeile, und es gibt genau so
    viele Reduktionen wie Policen mit RED-Buchung (hoechstens eine je
    Police).

    Mutationsprobe: die Bedingung in ``ereignisse._simuliere_vertrag`` zurueck auf
    ``j + 1 < t`` -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    assert (stamm["premium_duration"] < stamm["duration"]).all()
    nach_t = _nachlauf(stamm, erg)
    assert len(nach_t) > 0, "keine Reduktion im Nachlauf — der Fall bleibt ungezogen"
    led = erg.ledger
    red = led[led["ereignis"] == "RED"]
    assert len(_red_ab_t(stamm, led)) >= 2 * len(nach_t)
    for z in nach_t.to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        eigene = red[(red["police_id"] == pid) & (red["vertragsjahr"] == jahr)]
        arten = set(eigene["betrag_art"])
        assert {"VS_herabsetzung", "RKW_teilkuendigung"} <= arten, (pid, jahr, arten)
    assert len(erg.reduktionen) == red["police_id"].nunique()
    assert erg.reduktionen["police_id"].is_unique


def test_der_nachlauf_hat_beide_grenzen_t_und_n(welt):
    """Jahr t selbst ist das erste Nachlaufjahr (>=), Jahr n der Ablauf
    (<). Die Welt mit t = 12 und Zugang im Vertragsjahr 11 bringt das erste
    Nachlaufjahr als allererstes Simulationsjahr."""
    config, stamm, schichten, verankerung, erg = welt
    n = stamm.set_index("police_id")["duration"]
    t = stamm.set_index("police_id")["premium_duration"]
    red = erg.reduktionen
    assert (red["reduktion_jahr"].to_numpy() < n.loc[red["police_id"]].to_numpy()).all()
    bei_t = red["reduktion_jahr"].to_numpy() == t.loc[red["police_id"]].to_numpy()
    assert bei_t.any(), "keine Reduktion genau im Jahr t"


# --------------------------------------------------------------------------- #
# Dieselbe Rate vor und nach t: die Ziehung unabhaengig nachgebaut
# --------------------------------------------------------------------------- #


def _erwartetes_reduktionsjahr(config, stamm: pd.DataFrame, ledger: pd.DataFrame,
                               pid: int) -> tuple[int | None, float | None]:
    """Das Reduktionsjahr einer Police und das u, das es ausloest — aus dem
    Strom SELBST gezogen, nicht aus der Engine.

    Der Strom ist ``SeedSequence([seed, HERABSETZUNG_STREAM, police_id])``
    (``ereignisse._simuliere_vertrag``); je simuliertes Vertragsjahr j + 1
    im Fenster ``ab_jahr + 1 <= j + 1 < n`` EIN Draw, und zwar solange der
    Vertrag lebt und nicht beitragsfrei ist: Im Jahr eines Todes, eines
    Storno oder der Beitragsfreistellung wird nicht (mehr) gezogen. Diese
    drei Jahre kommen aus dem Hauptstrom und stehen hier als Tatsache im
    Ledger — sie sind nicht der Gegenstand der Probe, die Rate und der
    Strom der Herabsetzung sind es. Das erwartete Jahr ist das erste im
    Fenster, dessen Draw u < Rate erfuellt, vor UND nach t mit DERSELBEN
    Rate.
    """
    zeile = stamm.set_index("police_id").loc[pid]
    n = int(zeile["duration"])
    beginn = pd.Timestamp(zeile["insurance_start"])
    zugang = pd.Timestamp(zeile["bestandszugang"])
    ab_jahr = ((zugang.year - beginn.year) * 12 + zugang.month - beginn.month) // 12
    eigene = ledger[(ledger["police_id"] == pid)
                    & ledger["ereignis"].isin(["PEX", "STO", "TOD"])]
    ende = min([int(v) for v in eigene["vertragsjahr"]] + [n])
    fenster = range(ab_jahr + 1, n)
    rng = np.random.Generator(np.random.PCG64(
        np.random.SeedSequence([config.seed, HERABSETZUNG_STREAM, pid])))
    for jahr in fenster:
        u = rng.random()
        if jahr >= ende:
            return None, None
        if u < RATE_DER_WELT:
            return jahr, u
    return None, None


def test_die_nachlauf_ziehung_hat_dieselbe_rate_und_denselben_strom_wie_davor(welt):
    """Block F, Nachbesserung (Pruefer-Befund): Der Zaehltest oben sagt nur,
    DASS nach t gezogen wird, nicht MIT WELCHER Rate und AUS WELCHEM Strom —
    eine halbe Rate nach t liess jeden Test gruen. Hier baut der Test die
    Ziehung je Police selbst: den Strom
    ``SeedSequence([seed, HERABSETZUNG_STREAM, police_id])`` ziehen, das erste
    Jahr im Fenster mit u < Rate nehmen (dieselbe Rate vor und nach t) und
    gegen das Ledger vergleichen, ``==``, fuer JEDE Police der Welt.

    Positivkontrollen, damit das Gruen etwas bezeugt: Es gibt erwartete
    Reduktionen vor UND nach t, und es gibt Policen, deren Draw im Fenster
    knapp ueber der halben Rate liegt (u in [Rate/2, Rate)) — genau die
    verliert eine halbe Rate nach t.

    Mutationsproben: in ``_simuliere_vertrag`` die Rate im Nachlauf-Zweig
    halbieren (``annahmen.herabsetzung(0.0) * (0.5 if j + 1 >= t else 1.0)``)
    -> rot; im Nachlauf-Zweig einen anderen Strom nehmen (``rng.random()``
    statt ``rng_red.random()`` fuer ``j + 1 >= t``) -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    assert config.annahmen.herabsetzung(0.0) == RATE_DER_WELT
    t = stamm.set_index("police_id")["premium_duration"]
    gebucht = dict(zip(erg.reduktionen["police_id"], erg.reduktionen["reduktion_jahr"]))
    vor_t = nach_t = knapp = 0
    for pid in POLICEN:
        jahr, u = _erwartetes_reduktionsjahr(config, stamm, erg.ledger, pid)
        assert gebucht.get(pid) == jahr, (pid, jahr, gebucht.get(pid))
        if jahr is None:
            continue
        if jahr < t.loc[pid]:
            vor_t += 1
        else:
            nach_t += 1
            knapp += u >= RATE_DER_WELT / 2
    assert vor_t >= 3 and nach_t >= 3 and knapp >= 1, (vor_t, nach_t, knapp)


# --------------------------------------------------------------------------- #
# Grenzen, deterministisch: Rate ~1, alles andere still
# --------------------------------------------------------------------------- #


def _still(beginne, *, t: int, n: int = N):
    # Rate knapp unter 1: die Config weist a >= 1 ab (sicheres Ereignis);
    # die Draws sind gesetzt, der Test bleibt deterministisch.
    config = _config(TEILKUENDIGUNG, 0.999999, still=True)
    pid = 920_000
    stamm = _stamm([{"id": pid + i, "beginn": b, "zugang": "2026-01-01", "n": n, "t": t}
                    for i, b in enumerate(beginne)])
    erg = fortschreiben(stamm, config, _dt.date(2060, 1, 1))
    return stamm, erg


def test_die_reduktion_liegt_im_ersten_nachlaufjahr_und_nie_im_ablaufjahr():
    """Rate ~1, sonst nichts: jede Police reduziert im ersten Simulationsjahr,
    sofern es vor dem Ablauf liegt.

    * Beginn 2014 (Vertragsjahr 12 beim Zugang), t = 12: das erste
      Reduktionsjahr 13 liegt im Nachlauf.
    * Beginn 2002 (Vertragsjahr 24 beim Zugang): das einzig moegliche Jahr
      ist 25 = n, der Ablauf — keine Reduktion, der Vertrag laeuft ab.
    * Beginn 2003 (Vertragsjahr 23): das letzte gueltige Reduktionsjahr 24 =
      n - 1 wird gezogen.

    Mutationsproben: ``j + 1 < n`` -> ``j + 1 <= n`` (der Kern verweigert das
    Ablaufjahr -> Abbruch -> rot); ``j + 1 < n`` -> ``j + 1 < n - 1`` (Jahr
    24 fehlt -> rot)."""
    stamm, erg = _still(["2014-01-01", "2002-01-01", "2003-01-01"], t=12)
    pids = list(stamm["police_id"])
    red = erg.reduktionen.set_index("police_id")["reduktion_jahr"].to_dict()
    assert red.get(pids[0]) == 13
    assert pids[1] not in red
    assert red.get(pids[2]) == 24
    led = erg.ledger
    assert not len(led[(led["police_id"] == pids[1]) & (led["ereignis"] == "RED")])
    assert len(led[(led["police_id"] == pids[1]) & (led["ereignis"] == "ABL")]) == 1


# --------------------------------------------------------------------------- #
# Unabhaengige Sollrechnung je Reduktion im Nachlauf
# --------------------------------------------------------------------------- #


def test_summe_und_auszahlung_der_nachlauf_reduktion_folgen_der_unabhaengigen_zusage(welt):
    """Nach der Teilkuendigung ist der Vertrag f x S (plus die unveraenderten
    Scheiben); ausgezahlt wird (1-f) x Rueckkaufswert der Grundscheibe plus
    die absorbierte Schicht, bei negativer Summe auf null gekappt. Soll aus
    dem Kern-Primitiv ``vertrags_rkw`` und ``schichtwert_bei``, nicht aus
    der Engine. Mutationsprobe: in der Engine den Anteil der Auszahlung
    (1.0 - anteil) -> anteil -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    gen = config.generationen[0]
    haupt = stamm.set_index("police_id")
    led = erg.ledger
    geprueft = 0
    for z in _nachlauf(stamm, erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        mp = ModelPoint(**model_point_kwargs(haupt.loc[pid], gen.generation_fields()))
        scheiben = _scheiben_vor(erg, pid, jahr)
        # Erhoehungen laufen nur solange Beitraege laufen: im Nachlauf
        # kommt keine mehr hinzu.
        assert all(j < mp.t for j, _ in scheiben), (pid, scheiben)
        eigene = led[(led["police_id"] == pid) & (led["ereignis"] == "RED")
                     & (led["vertragsjahr"] == jahr)]
        arten = dict(zip(eigene["betrag_art"], eigene["betrag"]))
        assert arten["VS_herabsetzung"] == pytest.approx(
            ANTEIL * mp.sum_insured + sum(vs for _, vs in scheiben), rel=1e-12), pid
        rechnerisch = (1 - ANTEIL) * vertrags_rkw(
            Rechenkern(mp), [], jahr, stoab_je_baustein=True
        ) + schichtwert_bei(_parameter(), MONATE_TA, mp, 12 * jahr)
        assert arten["RKW_teilkuendigung"] == pytest.approx(max(0.0, rechnerisch), abs=1e-6), pid
        geprueft += 1
    assert geprueft > 0


# --------------------------------------------------------------------------- #
# Die Naht: Herleitung, Bewertung, Bewegungskonto
# --------------------------------------------------------------------------- #


def _voll(welt, ledger: pd.DataFrame) -> pd.DataFrame:
    config, stamm, *_ = welt
    gen = config.generationen[0]
    zug = pd.DataFrame([{
        "police_id": pid, "tarif_generation": gen.name, "ereignis": "ZUG",
        "vertragsjahr": 11, "status_date": pd.Timestamp("2026-01-01"),
        "betrag_art": "VS", "betrag": 100_000.0, "betrag_herkunft": "geliefert",
    } for pid in POLICEN])[[n for n, _ in LEDGER_SPALTEN]].astype(dict(LEDGER_SPALTEN))
    return pd.concat([zug, ledger], ignore_index=True)


def _pb1(welt, ledger: pd.DataFrame, reduktionen=None):
    config, stamm, schichten, verankerung, erg = welt
    return pruefe_ledger_betraege(
        stamm, _voll(welt, ledger), config, scheiben=erg.scheiben, historie=erg.historie,
        schichten=schichten, verankerung=verankerung,
        reduktionen=erg.reduktionen if reduktionen is None else reduktionen)


def test_p_b1_leitet_die_gezogene_nachlauf_reduktion_her(welt):
    """Die Herleitung muss den Fall tragen, den die Engine jetzt erzeugt:
    null Befunde auf dem ungestoerten Lauf — und eine um 1 EUR verschobene
    Summe bzw. eine gestrichene Auszahlung IM NACHLAUF bleibt nicht
    unentdeckt (kein blinder Fleck). Mutationsprobe: in
    ``_Herleitung.red_buchungen`` fuer ``jahr >= t`` kein Soll herleiten
    (``return {}``) -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    assert _nachlauf(stamm, erg).shape[0] > 0
    assert _pb1(welt, erg.ledger) == []
    led = erg.ledger
    ab_t = _red_ab_t(stamm, led)
    summe = ab_t.index[ab_t["betrag_art"] == "VS_herabsetzung"][0]
    zahl = ab_t.index[ab_t["betrag_art"] == "RKW_teilkuendigung"][0]
    plus = led.copy()
    plus.loc[summe, "betrag"] += 1.0
    assert _pb1(welt, plus), "verschobene Summe im Nachlauf unentdeckt"
    assert _pb1(welt, led.drop(index=zahl)), "gestrichene Auszahlung im Nachlauf unentdeckt"


def test_die_bewertung_laeuft_ueber_die_nachlauf_reduktion_und_trifft_den_folgevertrag(welt):
    """``einzelwerte_am`` bricht nicht ab (vorher gab es diese Vertraege nie),
    und der Rueckkaufswert im Jahr nach der Reduktion ist der des
    unabhaengig gebauten Folgevertrags (f x S als gewoehnlicher Kern plus
    Scheiben). Mutationsprobe: in ``auswertung._reduzierte_vertraege``
    Reduktionen ab ``t`` uebergehen -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    geprueft = 0
    for z in _nachlauf(stamm, erg).to_dict("records"):
        pid, jahr = int(z["police_id"]), int(z["reduktion_jahr"])
        beginn = pd.Timestamp(stamm.set_index("police_id").loc[pid, "insurance_start"])
        stichtag = (beginn + pd.DateOffset(years=jahr + 1)).date()
        h = erg.historie
        beendet = h[(h["police_id"] == pid) & (h["status_code"].isin(["STO", "TOD", "ABL"]))
                    & (h["status_date"] <= pd.Timestamp(stichtag))]
        if len(beendet) or stichtag > BIS:
            continue
        zeilen = einzelwerte_am(
            stamm, h, config, stichtag, scheiben=erg.scheiben, schichten=schichten,
            verankerung=verankerung, reduktionen=erg.reduktionen)
        zeile = next(w for w in zeilen if int(w["police_id"]) == pid)
        mp, grund_neu = _folgevertrag(config, stamm, pid, jahr)
        kerne = _scheiben_kerne(mp, config, _scheiben_vor(erg, pid, jahr))
        assert zeile["rueckkaufswert"] == pytest.approx(
            _soll_rkw(grund_neu, kerne, jahr + 1), rel=1e-9), pid
        geprueft += 1
    assert geprueft > 0


def test_das_bewegungskonto_haelt_die_identitaet_mit_nachlauf_reduktionen(welt):
    """Anfang + Zugang - Abgang = Ende je Jahr, Track und Mass, und die
    Endsumme des beitragspflichtigen Tracks ist die Summe der Einzelbewertung
    an jedem Jahresstichtag (nicht die des Kontos selbst). Mutationsprobe: in
    ``kennzahlen.bewegungskonto`` RED-Zeilen ab Vertragsjahr 15 ausblenden
    -> rot."""
    config, stamm, schichten, verankerung, erg = welt
    assert _nachlauf(stamm, erg).shape[0] > 0
    konto = bewegungskonto(stamm, erg.historie, erg.ledger, erg.scheiben, bis=BIS)
    assert len(konto) >= 10
    for zeile in konto:
        for track, oks in zeile["identitaet"].items():
            for mass, ok in oks.items():
                assert ok, (zeile["jahr"], track, mass)
    for zeile in konto:
        stichtag = _dt.date(zeile["jahr"] + 1, 1, 1)
        einzeln = einzelwerte_am(
            stamm, erg.historie, config, stichtag, scheiben=erg.scheiben,
            schichten=schichten, verankerung=verankerung, reduktionen=erg.reduktionen)
        soll = sum(w["leistung"] for w in einzeln if w["status"] == "POL")
        assert zeile["bpfl"]["ende"]["summe"] == pytest.approx(soll, rel=1e-9), zeile["jahr"]


# --------------------------------------------------------------------------- #
# Die Ratsche: die Engine zieht nach t genau das, was Kern und Datenmodell tragen
# --------------------------------------------------------------------------- #


def _kern_traegt_nach_t(verfahren: str) -> bool:
    from rechner_pipeline.kern import KLV_DEFAULT

    assert KLV_DEFAULT.t < KLV_DEFAULT.n
    try:
        reduziere(Rechenkern(KLV_DEFAULT), KLV_DEFAULT.t, ANTEIL, verfahren=verfahren)
    except BeitragsreduktionFehler:
        return False
    return True


def _datenmodell_laesst_nach_t_zu(verfahren: str) -> bool:
    stamm = _stamm([{"id": 1, "beginn": "2015-01-01", "zugang": "2026-01-01", "n": N, "t": 15}])
    zeile = pd.DataFrame([{
        "police_id": 1, "reduktion_jahr": 15,
        "reduktion_datum": pd.Timestamp("2015-01-01") + pd.DateOffset(years=15),
        "anteil": ANTEIL, "verfahren": verfahren}])
    return validate_reduktionen(stamm, zeile, None) == []


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_die_engine_zieht_nach_t_genau_die_verfahren_die_kern_und_datenmodell_tragen(welten, verfahren):
    """Eine Menge, drei Sichten, ``==``: Kern, Datenmodell und Engine sagen
    je Verfahren dasselbe. Positivkontrolle: Die Welt zieht vor t fuer JEDES
    Verfahren (dieselbe Rate) — ein Verfahren ohne Reduktion nach t fehlt also
    nicht an der Rate, sondern an der Regel. Die Menge ist nicht leer und nicht
    alles. Mutationsprobe: die Sperre der Engine fuer prospektiv/mit_abzug
    entfernen -> der Kern verweigert im Lauf -> rot; den Kern fuer
    prospektiv nach t oeffnen ohne die Engine -> rot."""
    config, stamm, schichten, verankerung, erg = welten[verfahren]
    t = stamm.set_index("police_id")["premium_duration"]
    red = erg.reduktionen
    vor_t = (red["reduktion_jahr"].to_numpy() < t.loc[red["police_id"]].to_numpy()).sum()
    assert vor_t > 0, "Positivkontrolle: die Welt zieht vor t nicht"
    engine = len(_nachlauf(stamm, erg)) > 0
    assert engine == _kern_traegt_nach_t(verfahren) == _datenmodell_laesst_nach_t_zu(verfahren), verfahren
    # Die Menge selbst: das Tupel, das die Engine liest, ist das, was der
    # Kern tatsaechlich akzeptiert — und heute allein die Teilkuendigung.
    kern_menge = {v for v in VERFAHREN if _kern_traegt_nach_t(v)}
    assert kern_menge == set(NACH_BEITRAGSENDE_DEFINIERT)
    assert kern_menge == {TEILKUENDIGUNG}


# --------------------------------------------------------------------------- #
# Die Naht zur Fuehrungsprobe: der gefahrene Fall des zweiten Laufs, mit Rate
# --------------------------------------------------------------------------- #


def test_ein_lauf_des_zweiten_baldrian_falls_mit_nachlauf_reduktionen_besteht_p_b1_und_probe(fall_welt):
    """Dieselbe Kette wie die Freischaltung (Fortschreibung des uebernommenen
    Bestands -> P-B1 auf Dateien -> Fuehrungsprobe), nur mit einer
    Herabsetzungsrate, die die Engine im ausfinanzierten Nachlauf ziehen
    laesst (Baldrian-Policen mit t < n, Zugang 2026). Die Probe ist der
    Konsument, der die Engine WIDERLEGEN soll: Sie muss die jetzt gebuchten
    Nachlauf-Reduktionen herleiten und bestehen, nicht nur dulden.

    Mutationsprobe: in ``fuehrungsprobe.red_soll`` fuer ``jahr >= t`` kein
    Soll herleiten (``return {}``) -> rot."""
    ab = fall_welt["fall"] / "abgeleitet"
    text = (ab / "bestand-config.toml").read_text(encoding="utf-8")
    cfg = ab / "cfg-nachlauf.toml"
    cfg.write_text(text + (f"\n[annahmen]\nred_anteil = {ANTEIL}\n"
                           "[annahmen.herabsetzung]\na = 0.5\nb = 0.0\n"), encoding="utf-8")
    nach = ab / "bestand-nachlauf"
    assert cli_fortschreibung.main([
        "--config", str(cfg), "--bis", STICHTAG_2,
        "--uebernahme", str(ab / "bestand"), "--out-dir", str(nach),
    ]) == 0
    tab = _baldrian_tabellen(nach)
    stamm = tab["bestand"]
    ab_t = _red_ab_t(stamm, tab["ledger"])
    assert len(ab_t) > 0, "keine Nachlauf-Reduktion im Fall — die Probe saehe nichts"
    welt2 = dict(fall_welt, cfg_pfad=cfg)
    pb1 = _baldrian_pb1(welt2, nach)
    assert pb1.exit_code == 0, pb1.errors
    code, beleg = _baldrian_probe(welt2, nach)
    assert code == 0 and beleg["befunde"] == [], beleg["befunde"][:3]


# --------------------------------------------------------------------------- #
# Der Bezug nach draussen: die Ziehung im Nachlauf verschiebt nichts davor
# --------------------------------------------------------------------------- #

#: Fingerabdruecke der Welt dieses Moduls, gemessen auf dem Stand VOR dem
#: Bau (25cca08). Ein Vergleich zweier Laeufe DIESES Standes saehe eine
#: Verschiebung nicht — beide Welten stammten aus demselben Code. Erst der
#: Bezug nach draussen macht den Test scharf. Ledger je Verfahren: bei
#: ``prospektiv`` und ``mit_abzug`` ALLE Zeilen (die Engine zieht dort nach t
#: nichts, also bitgleich), bei der Teilkuendigung die Zeilen VOR t (dahinter
#: kommen die neuen Buchungen). Historie und Scheiben sind fuer alle drei
#: identisch: Eine Herabsetzung aendert keinen Status, und Erhoehungen gibt es
#: nur, solange Beitraege laufen.
VOR_DEM_NACHLAUF = {
    PROSPEKTIV: {
        "ledger": "6f88a541fb2862f6b95dd3cc057067609137aa9688940e8231fdf3f3f5683739",
        "scheiben": "227fec2e8c11712fac8e436032af4ec9c082fe51bae25b026f4925a8d777bf81",
    },
    MIT_ABZUG: {
        "ledger": "6f4dd6660e9ce8fbae9d10a535abd08a69107d850e239173f0d3846f0971db49",
        "scheiben": "91f988eedd5fce2aba8f54928d6d1f44f3250a366c6674dbba9e89b2021198c1",
    },
    TEILKUENDIGUNG: {
        "ledger": "e381f9394bcb78cb7d7fdf3002a3ba788dae71ba3e1fb464efffcc2d68f61c0e",
        "scheiben": "820e2180e9ec9acf8aee35936eb12ded617134dee6726aaf0349aec35936bcb4",
    },
}
HISTORIE_VOR_DEM_NACHLAUF = "7440ee258c5aff5433bf726d4b1bdd472f8ee464dc631a72899f3c9d15557242"


@pytest.mark.parametrize("verfahren", VERFAHREN)
def test_die_ziehung_im_nachlauf_verschiebt_keinen_bestehenden_bestand(welten, verfahren):
    """Gemessen gegen den Stand davor: Historie und Scheiben sind bitgleich,
    das Ledger bitgleich bis t (Teilkuendigung) bzw. ganz (PLV-Verfahren).
    Mutationsprobe: die Nachlauf-Ziehung aus dem HAUPTstrom nehmen
    (``rng.random()`` statt ``rng_red.random()`` im Nachlauf-Zweig) -> rot."""
    import hashlib

    config, stamm, schichten, verankerung, erg = welten[verfahren]
    led = erg.ledger
    if verfahren == TEILKUENDIGUNG:
        t = stamm.set_index("police_id")["premium_duration"]
        led = led[led["vertragsjahr"].to_numpy() < t.loc[led["police_id"]].to_numpy()]

    def fingerabdruck(df):
        return hashlib.sha256(df.to_csv(index=False).encode("utf-8")).hexdigest()

    assert fingerabdruck(led) == VOR_DEM_NACHLAUF[verfahren]["ledger"]
    assert fingerabdruck(erg.scheiben) == VOR_DEM_NACHLAUF[verfahren]["scheiben"]
    assert fingerabdruck(erg.historie) == HISTORIE_VOR_DEM_NACHLAUF


# --------------------------------------------------------------------------- #
# Grenze des Floors (Entscheid des Maintainers 2026-09-30)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verfahren", [PROSPEKTIV, MIT_ABZUG])
def test_der_floor_deckt_die_basisschicht_und_nicht_die_korrekturschicht(verfahren):
    """Der Floor auf null gilt fuer den umgewandelten Teil der BASISSCHICHT;
    eine negative Korrekturschicht (rho < 0) kann ihn darunter druecken — die
    Schicht ist Migrationsdifferenz, keine Tarifgroesse (klv.md 7.1, Docstring
    von ``kern.beitragsreduktion``). Sollrechnung unabhaengig aus den
    Verlaufszeilen des Kerns und ``schichtwert_bei``, nicht aus
    ``reduzierte_teile``: Der beitragsfreie Teil ist (Basis + Schicht) / V^bfr,
    mit der Schicht UNGEKLEMMT negativ. Die Gegenprobe: dieselbe Reduktion
    ohne Schicht bleibt bei ihrem nicht negativen Basisteil.

    Mutationsprobe: in ``_reduziere_eine_schicht`` den Floor ueber die Summe
    ziehen (``umgewandelt = max(0.0, umgewandelt + zusatz_dk)``) -> rot."""
    from rechner_pipeline.kern import KLV_DEFAULT
    from rechner_pipeline.kern.beitragsreduktion import reduzierte_teile

    grund = Rechenkern(KLV_DEFAULT)
    jahr, f = MONATE_TA // 12, ANTEIL
    parameter = _parameter(rho=-0.9)
    schicht = schichtwert_bei(parameter, MONATE_TA, KLV_DEFAULT, 12 * jahr)
    zeile = grund.verlaufszeile(jahr)
    basis = (1 - f) * (zeile.vx_mrv if verfahren == PROSPEKTIV
                       else max(0.0, zeile.vx_mrv - zeile.stoab))
    assert basis > 0.0 and schicht < -basis, (basis, schicht)   # der Fall traegt die Aussage

    ohne = reduzierte_teile(grund, [], jahr, f, verfahren)[0][1].reduktion
    mit = reduzierte_teile(grund, [], jahr, f, verfahren,
                           schicht=(parameter, MONATE_TA))[0][1].reduktion
    bfr_ohne = ohne.vs_neu - f * KLV_DEFAULT.sum_insured
    bfr_mit = mit.vs_neu - f * KLV_DEFAULT.sum_insured
    assert bfr_ohne == pytest.approx(basis / zeile.vx_bfr, rel=1e-12) and bfr_ohne > 0.0
    assert bfr_mit == pytest.approx((basis + schicht) / zeile.vx_bfr, rel=1e-12)
    assert bfr_mit < 0.0, "der Floor darf die negative Schicht nicht einschliessen"
