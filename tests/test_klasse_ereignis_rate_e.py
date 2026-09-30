"""Klasse: Bindung Ereignisart -> Rate, fuer JEDE Ereignisart — Runde E.

Die Invariante: Eine Config, deren Erfahrungsannahme ein Ereignis nicht
erzeugen kann (Rate null), belegt keine gebuchte Fortschreibungszeile dieser
Ereignisart. Runde C (RC05) hat sie fuer die Herabsetzung gebaut
(``red_bindung_fehler``); Storno, Beitragsfreistellung, Erhoehung, Tod und die
vier BU-Uebergaenge blieben offen — ein Lauf galt als durch eine Config
erzeugt, die keine einzige seiner Stornozeilen haette ziehen koennen.

Die Menge, ueber die die Regel gilt, ist die Menge der Annahme-Felder von
``bestand.config.Annahmen`` (aus der Dataclass hergeleitet). Die Ausnahme —
Ereignisse, die aus keiner Annahme gezogen werden (ZUG, MIG, ABL) — steht als
Menge im Code (``EREIGNIS_OHNE_ANNAHME``), mit Grund.

Drei Instrumente, je Klasse:

1. **Ratsche** (statisch, als solche benannt): die Menge der Felder, die
   Ziele und die Ausnahmen werden mit ``==`` aufgezaehlt; ein neues Feld oder
   eine neue Ereignisart ohne Einordnung macht den Test rot. Mit
   Positivkontrolle (die Ratsche findet eine fehlende Instanz).
2. **Zaehltest** (dynamisch): fuer JEDE Instanz der Menge (parametrisiert ueber
   ``ANNAHME_ERZEUGT``, nicht ueber eine Liste im Test) wird gemessen, dass die
   unveraenderte Welt gruen ist und dass das Nullsetzen genau dieser Annahme
   genau die Zeilen dieser Ereignisart unbelegt macht — auf der echten Engine
   (KLV und BU) und an der Naht von P-B1.
3. **Mutationsprobe** je Instanz: siehe die Docstrings; die Regel fuer genau
   ein Feld zuruecknehmen macht genau den Fall dieses Felds rot.

Nachbesserung Runde E (Pruefer-Befund 4): ein (Produkt, Ereignis)-Paar, das
weder Ziel einer Annahme noch Ausnahme ist, ist ein Befund
(``unzugeordnete_ereignisse``) und kein stilles ``None`` mehr; der Zaehltest
misst die Paare einer echten KLV- und BU-Welt.

Die Fuehrungsprobe hat ihren Zaehltest in ``test_klasse_probe_e``.

Knoten: klv, bu
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as _dt
import inspect
import re

import pandas as pd
import pytest

from rechner_pipeline.bestand import ledger_bindung
from rechner_pipeline.bestand.config import (
    ANNAHME_FELDER,
    Annahme,
    Annahmen,
    load_config,
)
from rechner_pipeline.bestand.ereignisse import fortschreiben
from rechner_pipeline.bestand.ledger_bindung import pruefe_ledger_betraege
from rechner_pipeline.models.bestand import (
    ANNAHME_ERZEUGT,
    ANNAHME_MIT_ERSTER_ORDNUNG,
    BU_TOD_JE_ZUSTAND,
    EREIGNIS_OHNE_ANNAHME,
    EREIGNIS_VALUES,
    ZUSTANDSABHAENGIG,
    annahme_erzeugt_nicht,
    EreignisOhneZuordnung,
    annahme_fuer_ereignis,
    ereignis_zuordnungsfehler,
    unbelegte_ereignisse,
    unzugeordnete_ereignisse,
)
from tests import test_t27_teilkuendigung_klasse as tk
from tests.test_bestand_bu import BU_EXAMPLE
from tests.test_t27_teilkuendigung_klasse import welt as klv_welt  # noqa: F401
from tests.zugangsstrom import bestand_aus_zugangsstrom

NULL = Annahme(a=0.0, b=0.0)
#: Die TOML-Vorgabe ``{ a = 0.0 }`` ergibt b = 1 — bei Annahmen ohne Tafel ist
#: das KEINE Rate (die Engine zieht mit annahme(0.0)).
NUR_B = Annahme(a=0.0, b=1.0)

KLV_FELDER = sorted(f for f, (p, _e) in ANNAHME_ERZEUGT.items() if p == "klv")
BU_FELDER = sorted(f for f, (p, _e) in ANNAHME_ERZEUGT.items() if p == "bu")


def _annahme_felder() -> set:
    """Die Annahme-Felder der Dataclass — aus den Feldern hergeleitet."""
    return {
        f.name for f in dataclasses.fields(Annahmen)
        if f.default_factory is not dataclasses.MISSING
        and isinstance(f.default_factory(), Annahme)
    }


# --------------------------------------------------------------------------- #
# 1. Ratsche (statisch)
# --------------------------------------------------------------------------- #


def _luecken(felder, erzeugt, ereignisse, ohne):
    """Was an der Einordnung fehlt oder doppelt ist — leer heisst: jede
    Instanz der Menge traegt die Regel."""
    fehler = []
    fehler += [f"Annahmenfeld {f!r} nicht in ANNAHME_ERZEUGT" for f in sorted(set(felder) - set(erzeugt))]
    fehler += [f"ANNAHME_ERZEUGT kennt {f!r}, die Dataclass nicht" for f in sorted(set(erzeugt) - set(felder))]
    ziele = {e for _p, e in erzeugt.values()}
    fehler += [f"Ereignis {e!r} weder aus einer Annahme gezogen noch ausgenommen"
               for e in sorted(set(ereignisse) - ziele - set(ohne))]
    fehler += [f"Ereignis {e!r} zugleich gezogen und ausgenommen" for e in sorted(ziele & set(ohne))]
    fehler += [f"Ziel {e!r} ausserhalb des Ledger-Vokabulars" for e in sorted(ziele - set(ereignisse))]
    fehler += [f"Ausnahme {e!r} ausserhalb des Ledger-Vokabulars" for e in sorted(set(ohne) - set(ereignisse))]
    return fehler


def test_ratsche_jedes_annahmenfeld_und_jede_ereignisart_ist_eingeordnet():
    """Statische Ratsche. ``==`` statt ``<=``: Die Felder der Dataclass, die
    Schluessel von ANNAHME_ERZEUGT und die Felder von ANNAHME_FELDER sind
    dieselbe Menge, und jedes Ereignis des Ledgers ist entweder das Ziel einer
    Annahme oder als Ausnahme mit Grund benannt.

    Mutationsprobe: ein Feld aus ANNAHME_ERZEUGT streichen oder ein Ereignis
    aus beiden Mengen nehmen -> rot."""
    felder = _annahme_felder()
    assert felder == {n for n, _ in ANNAHME_FELDER}
    assert _luecken(felder, ANNAHME_ERZEUGT, EREIGNIS_VALUES, EREIGNIS_OHNE_ANNAHME) == []
    assert all(isinstance(g, str) and len(g) > 10 for g in EREIGNIS_OHNE_ANNAHME.values())


def test_ratsche_positivkontrolle_sie_findet_eine_fehlende_instanz():
    felder = _annahme_felder()
    ohne_storno = {f: pe for f, pe in ANNAHME_ERZEUGT.items() if f != "storno"}
    assert any("'storno'" in t for t in _luecken(felder, ohne_storno, EREIGNIS_VALUES, EREIGNIS_OHNE_ANNAHME))
    neu = dict(ANNAHME_ERZEUGT, stoerfall=("klv", "STO"))
    assert any("stoerfall" in t for t in _luecken(felder, neu, EREIGNIS_VALUES, EREIGNIS_OHNE_ANNAHME))
    assert any("'NEU'" in t for t in _luecken(
        felder, ANNAHME_ERZEUGT, tuple(EREIGNIS_VALUES) + ("NEU",), EREIGNIS_OHNE_ANNAHME))
    assert any("zugleich" in t for t in _luecken(
        felder, ANNAHME_ERZEUGT, EREIGNIS_VALUES, dict(EREIGNIS_OHNE_ANNAHME, TOD="x")))


def test_ratsche_erste_ordnung_stimmt_mit_der_beschreibung_der_felder_ueberein():
    """Zwei unabhaengige Aussagen muessen dasselbe sagen: die Menge der
    Annahmen mit Rechnungsgrundlage (ANNAHME_MIT_ERSTER_ORDNUNG) und die
    Beschreibung in ANNAHME_FELDER ('keine Rechnungsgrundlage'). Der Zaehltest
    unten misst sie zusaetzlich an der Engine."""
    ohne_tafel = {n for n, text in ANNAHME_FELDER if "keine Rechnungsgrundlage" in text}
    assert set(ANNAHME_ERZEUGT) - ohne_tafel == set(ANNAHME_MIT_ERSTER_ORDNUNG)


def test_ratsche_zustandsabhaengige_ereignisse_haben_je_zustand_ein_feld():
    """BU-Tod: Anwaerter und Leistungsbezieher ziehen aus verschiedenen
    Annahmen. Die Zuordnung je Zustand ist genau die Menge der Felder, die
    dasselbe Ereignis ziehen."""
    doppelt = {f for f, pe in ANNAHME_ERZEUGT.items() if pe in ZUSTANDSABHAENGIG}
    assert doppelt == set(BU_TOD_JE_ZUSTAND.values())
    assert set(BU_TOD_JE_ZUSTAND) == {False, True}
    for im_bezug, feld in BU_TOD_JE_ZUSTAND.items():
        assert annahme_fuer_ereignis("bu", "TOD", im_bezug) == feld


def test_ratsche_die_herleitung_nennt_keine_ereignisart_und_kein_feld_im_klartext():
    """Statisch: Die Regel laeuft ueber die Mengen, nicht ueber Zweige je
    Art. Eine Art, die im Quelltext der Regel auftaucht, ist ein Sonderweg,
    der beim naechsten neuen Feld vergessen wird."""
    quellen = "".join(inspect.getsource(f) for f in (
        unbelegte_ereignisse, annahme_fuer_ereignis, annahme_erzeugt_nicht,
        unzugeordnete_ereignisse, ereignis_zuordnungsfehler))
    woerter = set(EREIGNIS_VALUES) | set(ANNAHME_ERZEUGT)
    treffer = [w for w in woerter if re.search(rf"['\"]{w}['\"]", quellen)]
    assert treffer == []
    # Positivkontrolle: derselbe Scanner findet ein eingebautes Literal.
    assert [w for w in woerter if re.search(rf"['\"]{w}['\"]", quellen + ' x == "STO"')] == ["STO"]


def test_ratsche_p_b1_ruft_die_regel():
    """Statisch: Der Konsument P-B1 ruft die eine Regel (die Fuehrungsprobe
    wird in test_klasse_probe_e gezaehlt)."""
    assert "unbelegte_ereignisse(" in inspect.getsource(pruefe_ledger_betraege)
    assert ledger_bindung.unbelegte_ereignisse is unbelegte_ereignisse


# --------------------------------------------------------------------------- #
# 2. Zaehltest: die Regel selbst, je Feld
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("feld", sorted(ANNAHME_ERZEUGT))
def test_ohne_b_ist_eine_annahme_ohne_tafel_keine_rate(feld):
    """Die Rate ist ``annahme(0.0)`` bei Annahmen ohne Rechnungsgrundlage
    (b ohne Wirkung) und ``a + b * q`` sonst. ``{ a = 0 }`` im TOML (b = 1)
    ist bei Storno keine Rate, bei Tod schon."""
    annahmen = Annahmen(**{feld: NUR_B})
    assert annahme_erzeugt_nicht(annahmen, feld) == (feld not in ANNAHME_MIT_ERSTER_ORDNUNG)
    assert annahme_erzeugt_nicht(Annahmen(**{feld: NULL}), feld)
    assert not annahme_erzeugt_nicht(Annahmen(**{feld: Annahme(a=0.01, b=0.0)}), feld)


# --------------------------------------------------------------------------- #
# Die Welten: echte Engine, KLV und BU
# --------------------------------------------------------------------------- #


def _klv_pb1(welt, config):
    _c, stamm, schichten, verankerung, erg = welt
    return pruefe_ledger_betraege(
        stamm, tk._voll(welt, erg.ledger), config, scheiben=erg.scheiben,
        historie=erg.historie, schichten=schichten, verankerung=verankerung,
        reduktionen=erg.reduktionen)


def _mit(config, feld, annahme):
    c = copy.deepcopy(config)
    setattr(c.annahmen, feld, annahme)
    return c


def _anzahl_vorfaelle(ledger: pd.DataFrame, art: str) -> int:
    """Unabhaengige Zaehlung: Vorfaelle (Police, Vertragsjahr) der Art — eine
    Erhoehung oder Herabsetzung bucht mehrere Zeilen."""
    zeilen = ledger[ledger["ereignis"] == art]
    return int(len(zeilen[["police_id", "vertragsjahr"]].drop_duplicates()))


@pytest.fixture(scope="module")
def bu_welt():
    config = load_config(BU_EXAMPLE)
    stamm = bestand_aus_zugangsstrom(config, _dt.date(2010, 1, 1))
    erg = fortschreiben(stamm, config, _dt.date(2030, 1, 1))
    return config, stamm, erg


def _bu_pb1(welt, config):
    _c, stamm, erg = welt
    return pruefe_ledger_betraege(stamm, erg.ledger, config, historie=erg.historie)


def _bu_tod_im_bezug(erg) -> pd.Series:
    """Unabhaengig von zustand_vor: War die Police unmittelbar vor ihrem Tod
    im Leistungsbezug? Der juengste Zustand der Historie VOR dem Todestag."""
    h = erg.historie.sort_values(["police_id", "status_date", "status_id"], kind="stable")
    tod = erg.ledger[erg.ledger["ereignis"] == "TOD"]
    antwort = {}
    for z in tod.itertuples():
        davor = h[(h["police_id"] == z.police_id) & (h["status_date"] < z.status_date)]
        antwort[z.Index] = bool(len(davor)) and davor.iloc[-1]["status_code"] == "BU"
    return pd.Series(antwort, dtype=bool)


def _meldungen(fehler, feld):
    return [f for f in fehler if f"annahmen.{feld}:" in f]


# --------------------------------------------------------------------------- #
# Zaehltest P-B1 — KLV
# --------------------------------------------------------------------------- #


def test_positivkontrolle_die_klv_welt_ist_gruen_und_traegt_jede_klv_ereignisart(klv_welt):
    """Ohne Zeilen je Art waere der Zaehltest unten blind."""
    _c, _s, _sch, _v, erg = klv_welt
    assert _klv_pb1(klv_welt, klv_welt[0]) == []
    for feld in KLV_FELDER:
        art = ANNAHME_ERZEUGT[feld][1]
        assert _anzahl_vorfaelle(erg.ledger, art) > 0, (feld, art)


@pytest.mark.parametrize("feld", KLV_FELDER)
def test_p_b1_weist_die_zeilen_einer_ereignisart_ohne_rate_ab_klv(klv_welt, feld):
    """Zaehltest je Feld: Nullsetzen von ``feld`` macht GENAU die Zeilen seiner
    Ereignisart unbelegt — alle Vorfaelle, und kein anderes Feld.
    Mutationsprobe: ``annahme_erzeugt_nicht`` fuer genau dieses Feld
    verneinen -> genau dieser Fall rot."""
    config, _stamm, _sch, _ver, erg = klv_welt
    art = ANNAHME_ERZEUGT[feld][1]
    fehler = _klv_pb1(klv_welt, _mit(config, feld, NULL))
    treffer = _meldungen(fehler, feld)
    assert len(treffer) == 1, (feld, fehler[:3])
    soll = _anzahl_vorfaelle(erg.ledger, art)
    assert treffer[0].startswith(f"ledger: {soll} {art}-Buchung(en)"), (treffer[0], soll)
    for anderes in ANNAHME_ERZEUGT:
        if anderes != feld:
            assert _meldungen(fehler, anderes) == [], (feld, anderes)


@pytest.mark.parametrize("feld", KLV_FELDER)
def test_die_engine_zieht_ohne_rate_kein_ereignis_klv(klv_welt, feld):
    """Die Regel gegen die ENGINE gemessen: Dieselbe Welt, die Annahme auf
    null (und auf die TOML-Vorgabe a = 0 / b = 1) — die Engine bucht keine
    Zeile dieser Art. Das ist die Aussage, die P-B1 nachvollzieht; bucht die
    Engine trotz Nullsetzen, ist die Regel falsch."""
    config, stamm, schichten, verankerung, erg = klv_welt
    art = ANNAHME_ERZEUGT[feld][1]
    assert _anzahl_vorfaelle(erg.ledger, art) > 0            # Positivkontrolle
    for annahme in (NULL, NUR_B):
        if annahme is NUR_B and feld in ANNAHME_MIT_ERSTER_ORDNUNG:
            continue                                        # dort ist b > 0 eine Rate
        c = _mit(config, feld, annahme)
        lauf = fortschreiben(stamm, c, tk.BIS, schichten=schichten, verankerung=verankerung)
        assert _anzahl_vorfaelle(lauf.ledger, art) == 0, (feld, annahme)
        assert annahme_erzeugt_nicht(c.annahmen, feld)


# --------------------------------------------------------------------------- #
# Zaehltest P-B1 — BU
# --------------------------------------------------------------------------- #


def test_positivkontrolle_die_bu_welt_ist_gruen_und_traegt_jede_bu_ereignisart(bu_welt):
    config, _stamm, erg = bu_welt
    assert _bu_pb1(bu_welt, config) == []
    bezug = _bu_tod_im_bezug(erg)
    assert bezug.any() and (~bezug).any(), "TOD aus beiden Zustaenden noetig"
    for art in ("INV", "REA"):
        assert _anzahl_vorfaelle(erg.ledger, art) > 0, art


@pytest.mark.parametrize("feld", BU_FELDER)
def test_p_b1_weist_die_zeilen_einer_ereignisart_ohne_rate_ab_bu(bu_welt, feld):
    """Zaehltest je BU-Feld; beim Tod zaehlt der Zustand VOR dem Ereignis
    (Anwaerter -> aktivensterblichkeit, Leistungsbezug ->
    invalidensterblichkeit), unabhaengig von ``zustand_vor`` gezaehlt.
    Mutationsprobe: das Feld in ANNAHME_ERZEUGT umbiegen oder
    ``annahme_erzeugt_nicht`` fuer das Feld verneinen -> genau dieser Fall rot."""
    config, _stamm, erg = bu_welt
    art = ANNAHME_ERZEUGT[feld][1]
    ledger = erg.ledger
    if art == "TOD":
        bezug = _bu_tod_im_bezug(erg)
        gewollt = BU_TOD_JE_ZUSTAND[True] == feld
        ledger = ledger.loc[bezug[bezug == gewollt].index]
    soll = _anzahl_vorfaelle(ledger, art)
    assert soll > 0
    fehler = _bu_pb1(bu_welt, _mit(config, feld, NULL))
    treffer = _meldungen(fehler, feld)
    assert len(treffer) == 1, (feld, fehler[:3])
    assert treffer[0].startswith(f"ledger: {soll} {art}-Buchung(en)"), (treffer[0], soll)
    for anderes in ANNAHME_ERZEUGT:
        if anderes != feld:
            assert _meldungen(fehler, anderes) == [], (feld, anderes)


@pytest.mark.parametrize("feld", BU_FELDER)
def test_die_engine_zieht_ohne_rate_kein_ereignis_bu(bu_welt, feld):
    """Wie bei KLV gegen die Engine: Nullsetzen -> keine Zeile der Art aus
    diesem Zustand. Fuer die Sterblichkeiten zaehlt der Zustand davor; die
    Invalidisierung beeinflusst die Zustandsverteilung, deshalb wird der Zustand
    am neuen Lauf gemessen."""
    config, stamm, _erg = bu_welt
    art = ANNAHME_ERZEUGT[feld][1]
    c = _mit(config, feld, NULL)
    lauf = fortschreiben(stamm, c, _dt.date(2030, 1, 1))
    ledger = lauf.ledger
    if art == "TOD":
        bezug = _bu_tod_im_bezug(lauf)
        gewollt = BU_TOD_JE_ZUSTAND[True] == feld
        ledger = ledger.loc[bezug[bezug == gewollt].index]
    assert _anzahl_vorfaelle(ledger, art) == 0
    # ... und ein P-B1-Lauf gegen die NULL-Config ist auf DIESEM Lauf gruen:
    # die Zeilen, die die Regel meldet, sind genau die, die die Engine der
    # unveraenderten Welt gebucht hat (die Gegenprobe der Welt oben).
    assert _meldungen(pruefe_ledger_betraege(stamm, lauf.ledger, c, historie=lauf.historie), feld) == []


# --------------------------------------------------------------------------- #
# Ausnahmen und Fenster der Regel
# --------------------------------------------------------------------------- #


def test_zug_mig_abl_und_die_zugangsbuchungen_haengen_an_keiner_annahme(klv_welt):
    """Die Ausnahmen der Menge, gemessen: Mit ALLEN Annahmen auf null bleiben
    ZUG (Zugang am Zugangstag) und ABL unbelegt-frei — sie werden aus keiner
    Annahme gezogen. Die PEX-Umbuchung am Zugangstag (Uebernahme) ebenso."""
    config, stamm, _sch, _ver, erg = klv_welt
    alle_null = copy.deepcopy(config)
    for feld in ANNAHME_ERZEUGT:
        setattr(alle_null.annahmen, feld, NULL)
    voll = tk._voll(klv_welt, erg.ledger)
    assert set(voll["ereignis"]) >= {"ZUG", "ABL"}
    rest = voll[voll["ereignis"].isin(set(EREIGNIS_OHNE_ANNAHME))]
    assert len(rest) > 0
    assert unbelegte_ereignisse(stamm, rest, alle_null.annahmen) == {}
    # Positivkontrolle: dieselbe Config meldet die Zeilen der gezogenen Arten.
    assert set(unbelegte_ereignisse(stamm, voll, alle_null.annahmen)) == {
        f for f in KLV_FELDER if _anzahl_vorfaelle(erg.ledger, ANNAHME_ERZEUGT[f][1])}


def test_eine_zeile_am_oder_vor_dem_zugang_ist_nicht_sache_dieser_regel(klv_welt):
    """Was am Zugangstag steht, schreibt die Uebernahme (kein Ziehen einer
    Annahme); ob dort etwas stehen DARF, ist die Regel des Buchungsfensters.
    Die Zeile am Zugangstag wird hier nicht gemeldet, nach dem Zugang schon."""
    config, stamm, _sch, _ver, erg = klv_welt
    alle_null = copy.deepcopy(config)
    for feld in ANNAHME_ERZEUGT:
        setattr(alle_null.annahmen, feld, NULL)
    zeile = erg.ledger[erg.ledger["ereignis"] == "STO"].iloc[[0]].copy()
    pid = int(zeile.iloc[0]["police_id"])
    zugang = pd.Timestamp(stamm.set_index("police_id").loc[pid, "bestandszugang"])
    am = zeile.assign(status_date=zugang)
    assert unbelegte_ereignisse(stamm, am, alle_null.annahmen) == {}
    assert list(unbelegte_ereignisse(stamm, zeile, alle_null.annahmen)) == ["storno"]


# --------------------------------------------------------------------------- #
# Nachbesserung: ein Paar ohne Zuordnung ist ein Befund, kein stilles None
# --------------------------------------------------------------------------- #

#: Von Hand und unabhaengig von den Mengen im Code: Die (Produkt, Ereignis)-
#: Paare, die die Engine in den Welten unten BUCHT. KLV: die Neuzugangswelt
#: der Beispiel-Config (ohne RED: deren Herabsetzungsrate ist null) plus die
#: Teilkuendigungswelt der Klasse; BU: die Neuzugangswelt der BU-Beispiel-Config.
KLV_PAARE = {("klv", e) for e in ("ZUG", "ABL", "TOD", "STO", "PEX", "ERH", "RED")}
BU_PAARE = {("bu", e) for e in ("ZUG", "ABL", "TOD", "INV", "REA")}


@pytest.fixture(scope="module")
def neuzugangswelten():
    """Echte Engine, eigenes Geschaeft mit Neuzugang (ZUG aus dem Erzeuger):
    (klv, bu) je (Stamm, Ergebnis) mit dem Stamm ALLER Vertraege."""
    from rechner_pipeline.bestand.ereignisse import mit_zugaengen
    from tests.test_bestand_neuzugang import EXAMPLE, REF

    welten = {}
    for produkt, pfad, bis in (("klv", EXAMPLE, _dt.date(2016, 1, 1)),
                               ("bu", BU_EXAMPLE, _dt.date(2020, 1, 1))):
        config = load_config(pfad)
        basis = bestand_aus_zugangsstrom(config, bis=REF)
        erg = fortschreiben(basis, config, bis, neuzugang_ab=REF)
        welten[produkt] = (mit_zugaengen(basis, erg.zugaenge), erg)
    return welten


def _paare(produkt: str, ledger: pd.DataFrame) -> set:
    return {(produkt, str(e)) for e in set(ledger["ereignis"])}


def _erlaubt(produkt: str) -> set:
    """Ziele der Annahmen dieses Produkts plus die Ausnahmen — von Hand aus den
    Mengen des Codes gebildet, nicht aus der Regel selbst."""
    return ({pe for pe in ANNAHME_ERZEUGT.values() if pe[0] == produkt}
            | {(produkt, e) for e in EREIGNIS_OHNE_ANNAHME})


def test_die_engine_bucht_nur_paare_die_einer_annahme_oder_einer_ausnahme_gehoeren(
        neuzugangswelten, klv_welt):
    """Zaehltest an der Engine: die je Produkt gebuchten (Produkt, Ereignis)-
    Paare sind genau die hier von Hand aufgezaehlten (``==`` auf der
    beobachteten Menge) und eine Teilmenge der Ziele plus Ausnahmen — ein
    Produkt, das eine neue Ereignisart bucht, macht den Test rot, bis sie
    eingeordnet ist. Positivkontrolle: ein Paar, das die Engine nicht bucht
    (KLV mit INV), ist kein erlaubtes.
    Mutationsprobe: das Feld ``reaktivierung`` aus ANNAHME_ERZEUGT streichen -> rot."""
    (klv_stamm, klv_erg), (bu_stamm, bu_erg) = neuzugangswelten["klv"], neuzugangswelten["bu"]
    _c, tk_stamm, _sch, _ver, tk_erg = klv_welt
    klv_ledger = pd.concat([klv_erg.ledger, tk_erg.ledger], ignore_index=True)
    assert _paare("klv", klv_ledger) == KLV_PAARE
    assert _paare("bu", bu_erg.ledger) == BU_PAARE
    assert _paare("klv", klv_ledger) <= _erlaubt("klv")
    assert _paare("bu", bu_erg.ledger) <= _erlaubt("bu")
    # Positivkontrolle: die Schranke trennt.
    assert ("klv", "INV") not in _erlaubt("klv") and ("bu", "STO") not in _erlaubt("bu")
    # Dieselbe Aussage als Befundliste (die Regel, die P-B1 und die Probe rufen).
    assert unzugeordnete_ereignisse(klv_stamm, klv_erg.ledger) == []
    assert unzugeordnete_ereignisse(bu_stamm, bu_erg.ledger) == []


def test_ein_unbekanntes_paar_ist_ein_befund_und_kein_stilles_none(neuzugangswelten):
    """Eine BU-Police mit STO-Buchung (STO ist ein KLV-Ziel, nicht das des
    Produkts BU) und eine KLV-Police mit INV: je GENAU ein Befund mit dem
    Wortlaut des Ausweges. ``annahme_fuer_ereignis`` gibt fuer dasselbe Paar
    kein ``None`` mehr zurueck. Positivkontrolle: die unveraenderte Welt ist
    befundfrei, eine Ausnahme (ABL) und ein Ziel (TOD) bleiben ohne Befund.
    Mutationsprobe: das ``raise`` in annahme_fuer_ereignis durch ``return None``
    ersetzen -> rot."""
    bu_stamm, bu_erg = neuzugangswelten["bu"]
    klv_stamm, klv_erg = neuzugangswelten["klv"]
    text = ("Ereignis {art} fuer Produkt {p} ist keiner Annahme und keiner Ausnahme "
            "zugeordnet — in ANNAHME_ERZEUGT oder EREIGNIS_OHNE_ANNAHME eintragen")
    for stamm, erg, produkt, art in ((bu_stamm, bu_erg, "bu", "STO"),
                                     (klv_stamm, klv_erg, "klv", "INV")):
        zeile = erg.ledger[erg.ledger["ereignis"] == "ABL"].iloc[[0]].assign(ereignis=art)
        mit = pd.concat([erg.ledger, zeile], ignore_index=True)
        befunde = unzugeordnete_ereignisse(stamm, mit)
        assert len(befunde) == 1, befunde
        assert text.format(art=art, p=produkt) in befunde[0], befunde
        assert ereignis_zuordnungsfehler(produkt, art) == text.format(art=art, p=produkt)
        with pytest.raises(EreignisOhneZuordnung, match="keiner Annahme und keiner Ausnahme"):
            annahme_fuer_ereignis(produkt, art)
    # Ausnahme und Ziel: kein Befund, kein Fehler.
    assert annahme_fuer_ereignis("klv", "ABL") is None
    assert annahme_fuer_ereignis("klv", "TOD") == "tod"
    assert ereignis_zuordnungsfehler("klv", "ABL") is None
    assert ereignis_zuordnungsfehler("klv", "TOD") is None


def test_p_b1_meldet_ein_paar_ohne_zuordnung_genau_einmal(klv_welt):
    """An der Naht von P-B1: Eine INV-Zeile an einer KLV-Police (das
    Produkt kann sie nicht buchen) bringt genau einen Befund dieser Art —
    auch mit vollen Raten, die Regel haengt nicht an einer Null-Annahme.
    Mutationsprobe: den Aufruf von unzugeordnete_ereignisse in
    pruefe_ledger_betraege entfernen -> rot."""
    config, _stamm, _sch, _ver, erg = klv_welt
    zeile = erg.ledger[erg.ledger["ereignis"] == "ABL"].iloc[[0]].assign(
        ereignis="INV", betrag_art="BU_Jahresrente")
    voll = tk._voll(klv_welt, pd.concat([erg.ledger, zeile], ignore_index=True))
    fehler = pruefe_ledger_betraege(
        klv_welt[1], voll, config, scheiben=erg.scheiben, historie=erg.historie,
        schichten=klv_welt[2], verankerung=klv_welt[3], reduktionen=erg.reduktionen)
    treffer = [f for f in fehler if "keiner Annahme und keiner Ausnahme zugeordnet" in f]
    assert len(treffer) == 1, fehler[:4]
    assert "Ereignis INV fuer Produkt klv" in treffer[0]


def test_ratsche_p_b1_und_probe_rufen_die_zuordnungsregel():
    """Statisch: beide Konsumenten rufen ``unzugeordnete_ereignisse``."""
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    assert "unzugeordnete_ereignisse(" in inspect.getsource(pruefe_ledger_betraege)
    assert "unzugeordnete_ereignisse(" in inspect.getsource(pruefe_fuehrung)
