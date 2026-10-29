"""Der Ereignisstrom als Eingang der Buchung (ADR-031).

Die Ereignis-Engine ist in Ziehung (``bestand.ziehung``, Ebene 4: was in
der simulierten Welt geschieht) und Buchung (``bestand.ereignisse``, Ebene
3: was die Fuehrung damit tut, mit Betraegen aus dem Kern) geschnitten;
dazwischen liegt genau ein Datentyp, die Ereignisliste. Drei Zusicherungen
des ADR, je mit Positivkontrolle:

1. Die Liste entsteht ohne einen Betrag des Kerns.
2. Die Buchung aus einer gegebenen Liste ergibt denselben Stand wie die
   Fassade ``fortschreiben`` — Byte fuer Byte, in jeder der fuenf Tabellen.
3. Eine Mutation der Ziehung wird in der Buchung sichtbar: an genau dem
   Vertrag, oder als Fehler, wenn die Liste nicht mehr zum Vertrag passt.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand import ereignisse, ziehung
from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.parquet_io import write_portfolio
from rechner_pipeline.bestand.ziehung import Ereignisliste, leere_zugaenge
from rechner_pipeline.kern.rechenkern import Rechenkern
from tests.zugangsstrom import bestand_aus_zugangsstrom

REPO = Path(__file__).resolve().parents[1]
KONFIG = {
    "klv": REPO / "plv" / "configs" / "bestand_klv.toml",
    "bu": REPO / "plv" / "configs" / "bestand_bu.toml",
}
BIS = dt.date(2026, 10, 29)


def _welt(produkt: str, basis_bis: dt.date, anzahl: int = 60):
    """Config und ein kleiner Basisbestand aus dem Zugangsstrom (die ersten
    Vertraege mit Beginn vor ``basis_bis``), dazu die naechsten als
    mitgebrachte Zugaenge — damit auch die Zugangsbuchung im Spiel ist."""
    config = load_config(KONFIG[produkt])
    strom = bestand_aus_zugangsstrom(config)
    frueh = strom[strom["insurance_start"] < pd.Timestamp(basis_bis)]
    spaet = strom[strom["insurance_start"] >= pd.Timestamp(basis_bis)]
    stamm = frueh.head(anzahl).reset_index(drop=True)
    zugaenge = spaet.head(anzahl // 3).reset_index(drop=True)
    return config, stamm, zugaenge


@pytest.fixture(scope="module")
def klv():
    return _welt("klv", dt.date(1998, 1, 1))


@pytest.fixture(scope="module")
def bu():
    return _welt("bu", dt.date(2010, 1, 1), anzahl=30)


def _liste(config, stamm, zugaenge, bis=BIS) -> Ereignisliste:
    gesamt = pd.concat([stamm, zugaenge], ignore_index=True)
    return Ereignisliste(zugaenge, ziehung.ziehe(gesamt, config, bis))


# --------------------------------------------------------------------------- #
# 1. Die Liste entsteht ohne Kern
# --------------------------------------------------------------------------- #


def test_die_liste_entsteht_ohne_einen_betrag_des_kerns(klv, monkeypatch):
    """Die Ziehung liest Rechnungsgrundlagen (die Tafel), nie einen
    Rechenwert: Mit einem Rechenkern, der sich nicht bauen laesst, zieht
    sie trotzdem. Positivkontrolle: Die Buchung braucht ihn und faellt."""
    config, stamm, zugaenge = klv

    def verweigert(self, *args, **kwargs):
        raise AssertionError("der Rechenkern wurde gebaut")

    monkeypatch.setattr(Rechenkern, "__init__", verweigert)
    liste = _liste(config, stamm, zugaenge)
    arten = set(liste.ereignisse["ereignis"])
    assert len(liste.ereignisse) > 0 and {"STO", "PEX", "ERH"} <= arten, arten
    assert list(liste.ereignisse.columns) == list(ziehung.EREIGNISLISTE_NAMES)
    # Positivkontrolle: Schon die Zugangsbuchung (Beitrag des Zugangs)
    # baut den Kern, der Vertrag selbst ebenso.
    with pytest.raises(AssertionError, match="der Rechenkern wurde gebaut"):
        ereignisse.buche(stamm, config, BIS, liste)
    nur_stamm = liste.ereignisse[liste.ereignisse["police_id"].isin(stamm["police_id"])]
    with pytest.raises(ereignisse.EreignisError, match="AssertionError: der Rechenkern"):
        ereignisse.buche(stamm, config, BIS, Ereignisliste(leere_zugaenge(), nur_stamm))


def test_die_bu_liste_entsteht_ohne_einen_beitrag_des_produkts(bu, monkeypatch):
    """Dasselbe fuer die BU: Die Uebergaenge kommen aus den Ausscheide-
    ordnungen des Produkts; sein Beitrag wird fuer die Liste nicht gerechnet."""
    from rechner_pipeline.kern.produkte.bu import BU

    config, stamm, zugaenge = bu

    def verweigert(self, *args, **kwargs):
        raise AssertionError("der Bruttobeitrag wurde gerechnet")

    monkeypatch.setattr(BU, "bruttobeitrag", verweigert)
    liste = _liste(config, stamm, zugaenge)
    assert len(liste.ereignisse) > 0
    assert set(liste.ereignisse["ereignis"]) <= {"INV", "REA", "TOD"}
    with pytest.raises(AssertionError, match="der Bruttobeitrag wurde gerechnet"):
        ereignisse.buche(stamm, config, BIS, liste)


# --------------------------------------------------------------------------- #
# 2. Buchung aus gegebener Liste = Fassade, Byte fuer Byte
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("welt", ["klv", "bu"])
def test_die_buchung_aus_der_liste_ist_die_fortschreibung_byte_fuer_byte(
    welt, klv, bu, tmp_path,
):
    config, stamm, zugaenge = klv if welt == "klv" else bu
    fassade = ereignisse.fortschreiben(stamm, config, BIS, zugaenge=zugaenge)
    geteilt = ereignisse.buche(stamm, config, BIS, _liste(config, stamm, zugaenge))
    assert len(fassade.ledger) > 0
    for name in fassade._fields:
        a, b = tmp_path / f"a_{name}.parquet", tmp_path / f"b_{name}.parquet"
        write_portfolio(getattr(fassade, name), a)
        write_portfolio(getattr(geteilt, name), b)
        assert a.read_bytes() == b.read_bytes(), name


def test_die_fassade_je_vertrag_ist_ziehen_dann_buchen(klv):
    """``_simuliere_vertrag`` (die Schnittstelle vor ADR-031) ist genau die
    Verkettung der beiden Haelften."""
    config, stamm, _ = klv
    gen = {g.name: g for g in config.generationen}
    row = stamm.iloc[0].to_dict()
    g = gen[str(row["tarif_generation"])]
    fassade = ereignisse._simuliere_vertrag(
        row, g.generation_fields(), config.annahmen, config.seed, BIS,
        tarifwerk=g.tarifwerk())
    gezogen = ziehung.ziehe_vertrag(
        row, g.generation_fields(), config.annahmen, config.seed, BIS,
        tarifwerk=g.tarifwerk())
    geteilt = ereignisse._buche_vertrag(
        row, g.generation_fields(), BIS, gezogen, tarifwerk=g.tarifwerk())
    assert fassade == geteilt
    assert [e["lfd"] for e in gezogen] == list(range(1, len(gezogen) + 1))


# --------------------------------------------------------------------------- #
# 3. Eine Mutation der Ziehung wird sichtbar
# --------------------------------------------------------------------------- #


def _ledger_je_police(fortschreibung):
    return {
        int(pid): grp.drop(columns=["police_id"]).reset_index(drop=True)
        for pid, grp in fortschreibung.ledger.groupby("police_id", sort=True)
    }


def test_ein_frueheres_storno_bucht_genau_diesen_vertrag_anders(klv):
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    soll = _ledger_je_police(ereignisse.buche(stamm, config, BIS, liste))
    ereignisse_mut = liste.ereignisse.copy()
    # Ein Storno ab dem dritten Vertragsjahr: Ein Jahr frueher liegt es noch
    # im gefuehrten Fenster des Vertrags (Jahr 0 wird nicht gebucht).
    i = ereignisse_mut.index[
        (ereignisse_mut["ereignis"] == "STO") & (ereignisse_mut["vertragsjahr"] >= 3)][0]
    pid = int(ereignisse_mut.loc[i, "police_id"])
    ereignisse_mut.loc[i, "vertragsjahr"] -= 1
    ereignisse_mut.loc[i, "wirkungstag"] = ereignisse_mut.loc[i, "wirkungstag"] - pd.DateOffset(years=1)
    ist = _ledger_je_police(ereignisse.buche(
        stamm, config, BIS, Ereignisliste(zugaenge, ereignisse_mut)))
    assert not soll[pid].equals(ist[pid]), "das fruehere Storno blieb unsichtbar"
    assert set(soll) == set(ist)
    for andere in soll:
        if andere != pid:
            pd.testing.assert_frame_equal(soll[andere], ist[andere])


def test_ein_gestrichener_tod_laesst_den_vertrag_weiterlaufen(klv):
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    tode = liste.ereignisse[liste.ereignisse["ereignis"] == "TOD"]
    assert len(tode), "die Welt hat keinen Tod gezogen"
    i = tode.index[0]
    pid = int(liste.ereignisse.loc[i, "police_id"])
    ohne = liste.ereignisse.drop(index=i)
    soll = _ledger_je_police(ereignisse.buche(stamm, config, BIS, liste))[pid]
    ist = _ledger_je_police(ereignisse.buche(
        stamm, config, BIS, Ereignisliste(zugaenge, ohne)))[pid]
    assert "TOD" in set(soll["ereignis"]) and "TOD" not in set(ist["ereignis"])


def test_ein_ereignis_nach_dem_ende_des_vertrags_ist_ein_fehler(klv):
    """Nichts wird still verworfen: Ein Ereignis hinter dem Storno (oder
    jenseits des Horizonts) bleibt ungebucht, und die Buchung sagt es."""
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    sto = liste.ereignisse[liste.ereignisse["ereignis"] == "STO"].iloc[0]
    nach = {
        "police_id": int(sto["police_id"]), "lfd": int(sto["lfd"]) + 1,
        "vertragsjahr": int(sto["vertragsjahr"]) + 1, "ereignis": "ERH",
        "wirkungstag": sto["wirkungstag"] + pd.DateOffset(years=1),
        "anteil": 0.05, "verfahren": "",
    }
    mutiert = pd.concat([liste.ereignisse, pd.DataFrame([nach])], ignore_index=True)
    mutiert = mutiert.astype(dict(ziehung.EREIGNISLISTE_SPALTEN))
    with pytest.raises(ereignisse.EreignisError, match=rf"police {int(sto['police_id'])}: 1 Ereignis"):
        ereignisse.buche(stamm, config, BIS, Ereignisliste(zugaenge, mutiert))


def test_eine_fremde_police_in_der_liste_ist_ein_fehler(klv):
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    fremd = liste.ereignisse.copy()
    fremd.loc[fremd.index[0], "police_id"] = 999_999_999
    with pytest.raises(ereignisse.EreignisError, match="Policen, die der Bestand nicht fuehrt"):
        ereignisse.buche(stamm, config, BIS, Ereignisliste(zugaenge, fremd))


def test_ein_unbuchbares_ereignis_ist_ein_fehler(klv):
    """Ein BU-Uebergang an einem KLV-Vertrag: nicht buchbar, kein stiller Sprung."""
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    falsch = liste.ereignisse.copy()
    i = falsch.index[falsch["ereignis"] == "ERH"][0]
    falsch.loc[i, "ereignis"] = "INV"
    with pytest.raises(ereignisse.EreignisError, match="nicht buchbar"):
        ereignisse.buche(stamm, config, BIS, Ereignisliste(zugaenge, falsch))


# --------------------------------------------------------------------------- #
# 4. Der Tagesstrom: Neugeschaeft, Ereignisse und Meldetage in einem Aufruf
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def plv():
    """Die Config der Vorzeige (Betriebsbeginn, Nummernkreise, Meldeverzug)
    mit einem kleinen Basisbestand aus ihrem Zugangsstrom."""
    config = load_config(REPO / "plv" / "configs" / "bestand_gesamt.toml")
    strom = bestand_aus_zugangsstrom(config)
    stamm = strom[strom["insurance_start"] < pd.Timestamp(dt.date(1998, 1, 1))]
    return config, stamm.head(60).reset_index(drop=True)


def test_der_tagesstrom_nennt_jeden_tod_den_die_fuehrung_bucht(plv):
    """Die Meldetage des Stroms decken jeden Tod des Ledgers — auch die Tode,
    die eine Uebernahme mitbringt (``ledger_voran``)."""
    from rechner_pipeline.betrieb.ziehung import tagesstrom

    config, stamm = plv
    betriebsbeginn, heute = dt.date(2026, 1, 5), BIS
    voran = pd.DataFrame([{
        "police_id": int(stamm["police_id"].iloc[0]), "tarif_generation": "x",
        "ereignis": "TOD", "vertragsjahr": 3,
        "status_date": pd.Timestamp("2019-07-01"), "betrag_art": "Todesfallleistung",
        "betrag": 1.0, "betrag_herkunft": "geliefert",
    }])
    strom = tagesstrom(config, stamm, betriebsbeginn, heute, ledger_voran=voran)
    assert len(strom.liste.zugaenge) > 0, "kein Neugeschaeft im Fenster"
    ergebnis = ereignisse.buche(stamm, config, heute, strom.liste)
    tode = ergebnis.ledger[ergebnis.ledger["ereignis"] == "TOD"]
    assert len(tode) > 0, "die Welt hat keinen Tod gezogen"
    gebucht = {(int(p), pd.Timestamp(d).year) for p, d in zip(tode["police_id"], tode["status_date"])}
    assert gebucht <= set(strom.meldetage)
    assert (int(stamm["police_id"].iloc[0]), 2019) in strom.meldetage


def test_das_tagesjournal_nimmt_die_meldetage_aus_dem_tagesstrom(plv):
    """Mit Strom: dieselben Buchungstage wie die Ableitung aus der Config
    (bitgleich). Ohne Meldetag fuer einen Tod: ein Befund, kein stiller
    Rueckgriff auf die Welt. Ein anderer Meldetag: sichtbar."""
    from rechner_pipeline.betrieb.tagesjournal import TagesjournalError, mit_buchungstagen
    from rechner_pipeline.betrieb.ziehung import tagesstrom

    config, stamm = plv
    strom = tagesstrom(config, stamm, dt.date(2026, 1, 5), BIS)
    ledger = ereignisse.buche(stamm, config, BIS, strom.liste).ledger
    aus_strom = mit_buchungstagen(config, ledger, meldetage=strom.meldetage)
    aus_config = mit_buchungstagen(config, ledger)
    pd.testing.assert_frame_equal(aus_strom, aus_config)
    tod = ledger[ledger["ereignis"] == "TOD"].iloc[0]
    schluessel = (int(tod["police_id"]), pd.Timestamp(tod["status_date"]).year)
    ohne = {k: v for k, v in strom.meldetage.items() if k != schluessel}
    with pytest.raises(TagesjournalError, match=rf"police {schluessel[0]}: kein Meldetag"):
        mit_buchungstagen(config, ledger, meldetage=ohne)
    anders = dict(strom.meldetage)
    anders[schluessel] = anders[schluessel] + 400
    assert not mit_buchungstagen(config, ledger, meldetage=anders).equals(aus_config)


def test_die_buchung_zieht_nicht(klv, monkeypatch):
    """Die Buchung mit einer gegebenen Liste ruft die Welt nicht; die
    Fassade tut es (Positivkontrolle)."""
    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)

    def verweigert(*args, **kwargs):
        raise AssertionError("die Welt wurde gerufen")

    monkeypatch.setattr(ereignisse, "ziehe", verweigert)
    monkeypatch.setattr(ereignisse, "ziehe_vertrag", verweigert)
    monkeypatch.setattr(ereignisse, "ziehe_bu_vertrag", verweigert)
    assert len(ereignisse.buche(stamm, config, BIS, liste).ledger) > 0
    with pytest.raises(AssertionError, match="die Welt wurde gerufen"):
        ereignisse.fortschreiben(stamm, config, BIS, zugaenge=zugaenge)


def test_die_ratsche_nennt_genau_die_drei_kanten_des_adr():
    """ADR-031, Entscheid des Maintainers vom 2026-10-29: drei benannte
    Kanten aus der Fuehrung in die Welt — nicht mehr, nicht weniger (==)."""
    from rechner_pipeline.ontologie.code_karte import VORZEIGE_NACH_WERKZEUG_ERLAUBT

    assert VORZEIGE_NACH_WERKZEUG_ERLAUBT == {
        ("rechner_pipeline/betrieb/tageslauf.py", "rechner_pipeline/betrieb/ziehung.py"),
        ("rechner_pipeline/bestand/ereignisse.py", "rechner_pipeline/bestand/ziehung.py"),
        ("rechner_pipeline/betrieb/tagesjournal.py", "rechner_pipeline/bestand/zufallsstroeme.py"),
    }


# --------------------------------------------------------------------------- #
# 5. Zwei Sichten auf dieselbe Config
# --------------------------------------------------------------------------- #


def test_die_sichten_decken_jedes_feld_der_config_genau_einmal():
    """Fuehrung und Welt teilen sich die Felder der Config vollstaendig und
    ueberschneidungsfrei (==, damit ein neues Feld eingeordnet werden muss);
    die Grenze folgt A-T1: NICHT_TARIFWERK liegt bis auf den Nummernkreis in
    der Welt, der Nummernkreis bei der Fuehrung."""
    import dataclasses

    from rechner_pipeline.bestand import config as cfg
    from rechner_pipeline.models.tarifwerkabnahme import NICHT_TARIFWERK

    for klasse, sichten in cfg.SICHT_FELDER.items():
        felder = {f.name for f in dataclasses.fields(getattr(cfg, klasse))}
        f, w, b = (set(sichten[k]) for k in ("fuehrung", "welt", "beide"))
        assert f | w | b == felder, (klasse, sorted(felder ^ (f | w | b)))
        assert not (f & w) and not (f & b) and not (w & b), klasse
    welt_der_generation = set(cfg.SICHT_FELDER["TarifGeneration"]["welt"])
    a_t1 = {("korrelationen" if k == "korrelation" else k) for k in NICHT_TARIFWERK}
    assert a_t1 - {"nummernkreis"} == welt_der_generation
    assert "nummernkreis" in cfg.SICHT_FELDER["TarifGeneration"]["fuehrung"]


def test_die_fuehrungssicht_traegt_kein_welt_feld_und_umgekehrt(plv):
    import dataclasses

    from rechner_pipeline.bestand import config as cfg

    config, _ = plv
    fuehrung, welt = config.fuehrung(), config.welt()
    namen_f = {f.name for f in dataclasses.fields(cfg.Fuehrungssicht)} | {
        f.name for f in dataclasses.fields(cfg.GenerationFuehrung)}
    namen_w = {f.name for f in dataclasses.fields(cfg.Weltsicht)} | {
        f.name for f in dataclasses.fields(cfg.GenerationWelt)}
    for welt_feld in ("seed", "annahmen", "verteilungen", "korrelationen",
                      "neuzugang_pro_jahr", "meldeverzug_tod", "wochentagsgewichte"):
        assert welt_feld not in namen_f, welt_feld
    for fuehrungs_feld in ("tarifwerk", "generation_fields", "nummernkreis",
                           "betriebsbeginn", "zellen", "gueltig_von"):
        assert fuehrungs_feld not in namen_w, fuehrungs_feld
    assert [g.name for g in fuehrung.generationen] == [g.name for g in welt.generationen]
    g0 = config.generationen[0]
    assert fuehrung.generation(g0.name).tarifwerk == g0.tarifwerk()
    assert fuehrung.generation(g0.name).nummernkreis == config.nummernkreis(g0)
    assert welt.seed == config.seed and welt.annahmen is config.annahmen
    with pytest.raises(KeyError):
        fuehrung.generation("gibt-es-nicht")


def test_die_buchung_kommt_ohne_die_welt_aus(klv):
    """Mit einer Config, deren Weltfelder fehlen, bucht die Fuehrung eine
    gegebene Liste — dasselbe Ergebnis wie mit der ganzen Datei. Die
    Fassade (ziehen, dann buchen) braucht die Welt (Positivkontrolle)."""
    import dataclasses

    config, stamm, zugaenge = klv
    liste = _liste(config, stamm, zugaenge)
    ohne_welt = dataclasses.replace(config, seed=None, annahmen=None)
    mit = ereignisse.buche(stamm, config, BIS, liste)
    ohne = ereignisse.buche(stamm, ohne_welt, BIS, liste)
    for name in mit._fields:
        pd.testing.assert_frame_equal(getattr(mit, name), getattr(ohne, name))
    with pytest.raises((AttributeError, TypeError, ereignisse.EreignisError)):
        ereignisse.fortschreiben(stamm, ohne_welt, BIS, zugaenge=zugaenge)
