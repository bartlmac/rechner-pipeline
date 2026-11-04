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
    fremde_zeile = liste.ereignisse.iloc[[0]].copy()
    fremde_zeile.loc[:, "police_id"] = 999_999_999
    fremde_zeile.loc[:, "lfd"] = 1
    fremd = pd.concat([liste.ereignisse, fremde_zeile], ignore_index=True)
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
    ohne_welt = _ohne_welt(config)       # jedes Weltfeld nach SICHT_FELDER
    mit = ereignisse.buche(stamm, config, BIS, liste)
    ohne = ereignisse.buche(stamm, ohne_welt, BIS, liste)
    for name in mit._fields:
        pd.testing.assert_frame_equal(getattr(mit, name), getattr(ohne, name))
    with pytest.raises((AttributeError, TypeError, ereignisse.EreignisError)):
        ereignisse.fortschreiben(stamm, ohne_welt, BIS, zugaenge=zugaenge)


# --------------------------------------------------------------------------- #
# 6. Bitgleich zur Engine vor ADR-031
# --------------------------------------------------------------------------- #

#: Fingerabdruck der fuenf Tabellen (sha256 ueber die sha256 der Parquet-
#: Dateien in der Reihenfolge der Fortschreibung), gerechnet mit der
#: UNGETEILTEN Engine auf dem Stand c58605e (vor ADR-031) fuer genau die
#: Welten der Fixtures oben. Die geteilte Engine (Ziehung, dann Buchung)
#: muss ihn treffen — das ist das Prüfkriterium des ADR im Kleinen. Eine
#: Aenderung der Draw-Reihenfolge, eines Stroms oder einer Buchung macht
#: ihn rot; wer ihn aendert, aendert die Simulation und sagt es.
FINGERABDRUCK_VOR_ADR031 = {
    "klv": "7389876586f9f3f01e6ad1b03e0b0ecfb07e97414c5ed26e3624844b85387958",
    "bu": "525d76f8990fe3c4de624c42eaad36aa1a5d373dca509bae851d098ced23a3b4",
}


def _fingerabdruck(fortschreibung, tmp_path: Path) -> str:
    import hashlib

    teile = []
    for name in fortschreibung._fields:
        p = tmp_path / f"{name}.parquet"
        write_portfolio(getattr(fortschreibung, name), p)
        teile.append(hashlib.sha256(p.read_bytes()).hexdigest())
    return hashlib.sha256("".join(teile).encode()).hexdigest()


@pytest.mark.parametrize("welt", ["klv", "bu"])
def test_die_geteilte_engine_ist_bitgleich_zur_engine_vor_adr031(welt, klv, bu, tmp_path):
    config, stamm, zugaenge = klv if welt == "klv" else bu
    geteilt = ereignisse.buche(stamm, config, BIS, _liste(config, stamm, zugaenge))
    assert _fingerabdruck(geteilt, tmp_path / "geteilt") == FINGERABDRUCK_VOR_ADR031[welt]
    fassade = ereignisse.fortschreiben(stamm, config, BIS, zugaenge=zugaenge)
    assert _fingerabdruck(fassade, tmp_path / "fassade") == FINGERABDRUCK_VOR_ADR031[welt]


# --------------------------------------------------------------------------- #
# 7. Die Buchung haelt die Liste gegen die Regeln der Welt (Pruefung, Befund B1)
# --------------------------------------------------------------------------- #


def _zeile(gesamt, ereignisse_df, pid, jahr, code, anteil=float("nan"), verfahren=""):
    """Ein Eintrag der Liste fuer ``pid`` im Vertragsjahr ``jahr`` mit dem
    Wirkungstag am Jahrestag, als naechste laufende Nummer der Police."""
    start = pd.Timestamp(gesamt.set_index("police_id").loc[pid, "insurance_start"])
    eigene = ereignisse_df.loc[ereignisse_df["police_id"] == pid, "lfd"]
    return {"police_id": pid, "lfd": (int(eigene.max()) + 1) if len(eigene) else 1,
            "vertragsjahr": jahr, "ereignis": code,
            "wirkungstag": start + pd.DateOffset(years=jahr), "anteil": anteil,
            "verfahren": verfahren}


def _mit(liste, *zeilen) -> Ereignisliste:
    df = pd.concat([liste.ereignisse, pd.DataFrame(list(zeilen))], ignore_index=True)
    df = df.astype(dict(ziehung.EREIGNISLISTE_SPALTEN))
    return Ereignisliste(liste.zugaenge, df.sort_values(["police_id", "lfd"], kind="stable").reset_index(drop=True))


@pytest.fixture(scope="module")
def klv_welt(klv):
    """Config, Gesamtbestand, Liste und die Kandidaten fuer die Regelproben:
    ein Vertrag mit Beitragsfreistellung, der danach weiterlaeuft, und ein
    Vertrag ohne Ende, dessen Ablauf und Beitragsende vor dem Horizont liegen."""
    config, stamm, zugaenge = klv
    gesamt = pd.concat([stamm, zugaenge], ignore_index=True)
    liste = _liste(config, stamm, zugaenge)
    E = liste.ereignisse
    vertrag = gesamt.set_index("police_id")
    ende = set(E.loc[E["ereignis"].isin(["TOD", "STO"]), "police_id"])
    mit_pex = set(E.loc[E["ereignis"] == "PEX", "police_id"])
    pex = None
    for _, r in E[(E["ereignis"] == "PEX") & ~E["police_id"].isin(ende)].iterrows():
        pid, j = int(r["police_id"]), int(r["vertragsjahr"])
        n, t = int(vertrag.loc[pid, "duration"]), int(vertrag.loc[pid, "premium_duration"])
        if j + 2 < min(n, t) and pd.Timestamp(vertrag.loc[pid, "insurance_start"]) + pd.DateOffset(years=j + 2) <= pd.Timestamp(BIS):
            pex = (pid, j)
            break
    laeuft = None
    for pid, row in vertrag.iterrows():
        n, t = int(row["duration"]), int(row["premium_duration"])
        start = pd.Timestamp(row["insurance_start"])
        if (pid not in ende and pid not in mit_pex and t + 1 < n
                and start + pd.DateOffset(years=n) <= pd.Timestamp(BIS)):
            laeuft = (int(pid), n, t)
            break
    assert pex is not None and laeuft is not None, "die Fixtures tragen keine Kandidaten"
    return config, stamm, gesamt, liste, pex, laeuft


def _verweigert(config, stamm, liste, muster):
    with pytest.raises(ereignisse.EreignisError, match=muster):
        ereignisse.buche(stamm, config, BIS, liste)


def test_eine_zweite_beitragsfreistellung_ist_ein_fehler(klv_welt):
    config, stamm, gesamt, liste, (pid, j), _ = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, j + 1, "PEX")),
                rf"police {pid}: PEX im Vertragsjahr {j + 1}: zweite Beitragsfreistellung")


def test_eine_erhoehung_nach_der_beitragsfreistellung_ist_ein_fehler(klv_welt):
    config, stamm, gesamt, liste, (pid, j), _ = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, j + 1, "ERH", 0.05)),
                rf"police {pid}: ERH im Vertragsjahr {j + 1}: Erhoehung nach der Beitragsfreistellung")


def test_ein_storno_nach_der_beitragsfreistellung_ist_ein_fehler(klv_welt):
    config, stamm, gesamt, liste, (pid, j), _ = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, j + 1, "STO")),
                rf"police {pid}: STO im Vertragsjahr {j + 1}: Storno nach der Beitragsfreistellung")


def test_eine_herabsetzung_nach_der_beitragsfreistellung_ist_ein_fehler_der_buchung(klv_welt):
    """Vor der Pruefung fing das der Kern (Vorgangsfolge); jetzt steht die
    Regel mit den anderen an einer Stelle, vor dem ersten Kernaufruf."""
    config, stamm, gesamt, liste, (pid, j), _ = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, j + 1, "RED", 0.5, "prospektiv")),
                rf"police {pid}: RED im Vertragsjahr {j + 1}: Herabsetzung nach der Beitragsfreistellung")


def test_ein_storno_im_ablaufjahr_ist_ein_fehler(klv_welt):
    config, stamm, gesamt, liste, _, (pid, n, t) = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, n, "STO")),
                rf"police {pid}: STO im Vertragsjahr {n}: Storno im Ablaufjahr")


def test_eine_beitragsfreistellung_nach_dem_beitragsende_ist_ein_fehler(klv_welt):
    config, stamm, gesamt, liste, _, (pid, n, t) = klv_welt
    _verweigert(config, stamm, _mit(liste, _zeile(gesamt, liste.ereignisse, pid, t + 1, "PEX")),
                rf"police {pid}: PEX im Vertragsjahr {t + 1}: Beitragsfreistellung nach dem Beitragsende")


def test_ein_verschobener_wirkungstag_ist_ein_fehler(klv_welt):
    """Die Buchung las nur das Vertragsjahr; ein Wirkungstag, der nicht der
    Jahrestag ist, wurde still uebergangen."""
    config, stamm, gesamt, liste, _, _ = klv_welt
    df = liste.ereignisse.copy()
    i = df.index[df["ereignis"] == "ERH"][0]
    pid, jahr = int(df.loc[i, "police_id"]), int(df.loc[i, "vertragsjahr"])
    df.loc[i, "wirkungstag"] = df.loc[i, "wirkungstag"] + pd.DateOffset(years=1)
    _verweigert(config, stamm, Ereignisliste(liste.zugaenge, df),
                rf"police {pid}: ERH im Vertragsjahr {jahr}: Wirkungstag .* ist nicht der Jahrestag")


def test_die_form_der_eintraege_wird_geprueft(klv_welt):
    """Anteil und Verfahren tragen nur Herabsetzung und Teilkuendigung, den
    Satz ohne Verfahren die Erhoehung, die uebrigen Ereignisse nichts."""
    config, stamm, gesamt, liste, _, _ = klv_welt
    df = liste.ereignisse
    erh = df.index[df["ereignis"] == "ERH"][0]
    mit_verfahren = df.copy(); mit_verfahren.loc[erh, "verfahren"] = "quatsch"
    _verweigert(config, stamm, Ereignisliste(liste.zugaenge, mit_verfahren),
                "ERH im Vertragsjahr .*: braucht einen Satz und kein Verfahren")
    tod = df.index[df["ereignis"] == "TOD"][0]
    mit_anteil = df.copy(); mit_anteil.loc[tod, "anteil"] = 0.5
    _verweigert(config, stamm, Ereignisliste(liste.zugaenge, mit_anteil),
                "TOD im Vertragsjahr .*: traegt Anteil oder Verfahren")
    tku = df.index[df["ereignis"] == "TKU"]
    if len(tku):
        ohne = df.copy(); ohne.loc[tku[0], "verfahren"] = ""
        _verweigert(config, stamm, Ereignisliste(liste.zugaenge, ohne),
                    "TKU im Vertragsjahr .*: ohne Anteil oder Verfahren")


def test_der_wirkungstag_eines_bu_ereignisses_ist_der_jahrestag(bu):
    config, stamm, zugaenge = bu
    liste = _liste(config, stamm, zugaenge)
    df = liste.ereignisse.copy()
    assert len(df), "die BU-Welt hat kein Ereignis gezogen"
    i = df.index[0]
    pid, jahr, code = int(df.loc[i, "police_id"]), int(df.loc[i, "vertragsjahr"]), str(df.loc[i, "ereignis"])
    df.loc[i, "wirkungstag"] = df.loc[i, "wirkungstag"] + pd.DateOffset(years=1)
    with pytest.raises(ereignisse.EreignisError, match=rf"police {pid}: {code} im Vertragsjahr {jahr}: Wirkungstag"):
        ereignisse.buche(stamm, config, BIS, Ereignisliste(liste.zugaenge, df))


@pytest.mark.parametrize("produkt", ["klv", "bu"])
def test_echte_gezogene_listen_haben_eine_gueltige_folge(produkt, klv, bu):
    config, stamm, zugaenge = klv if produkt == "klv" else bu
    liste = _liste(config, stamm, zugaenge)
    geprueft = ereignisse._ereignisse_je_police(liste.ereignisse)
    assert sum(map(len, geprueft.values())) == len(liste.ereignisse)


@pytest.mark.parametrize("lfd,jahre,codes,muster", [
    ([0], [1], ["ERH"], "lfd.*positiv"),
    ([1, 1], [1, 2], ["ERH", "STO"], "lfd.*doppelt"),
    ([1, 3], [1, 2], ["ERH", "STO"], "lfd.*fortlaufend"),
    ([2, 1], [2, 1], ["STO", "PEX"], "lfd.*reihenfolge"),
    ([1, 2], [2, 1], ["STO", "PEX"], "Vertragsjahr.*faellt"),
    ([1, 2], [1, 1], ["ERH", "ERH"], "ERH.*doppelt"),
    ([1, 2], [1, 1], ["TKU", "TKU"], "TKU.*doppelt"),
    ([1, 2], [1, 1], ["PEX", "PEX"], "PEX.*doppelt"),
    ([1, 2], [1, 1], ["RED", "RED"], "RED.*doppelt"),
])
def test_fremde_liste_mit_falscher_folge_wird_vor_der_buchung_verweigert(
    lfd, jahre, codes, muster,
):
    df = pd.DataFrame({
        "police_id": [17] * len(lfd), "lfd": lfd,
        "vertragsjahr": jahre, "ereignis": codes,
        "wirkungstag": [pd.Timestamp("2021-01-01")] * len(lfd),
        "anteil": [float("nan")] * len(lfd), "verfahren": [""] * len(lfd),
    })
    with pytest.raises(ereignisse.EreignisError, match=rf"police 17: .*{muster}"):
        ereignisse._ereignisse_je_police(df)


def test_verschiedene_vorgaenge_im_selben_jahr_bleiben_in_zugreihenfolge():
    df = pd.DataFrame({
        "police_id": [17, 17, 19], "lfd": [1, 2, 1],
        "vertragsjahr": [1, 1, 4], "ereignis": ["ERH", "PEX", "TOD"],
        "wirkungstag": [pd.Timestamp("2021-01-01")] * 3,
        "anteil": [0.05, float("nan"), float("nan")],
        "verfahren": ["", "", ""],
    })
    assert [e["ereignis"] for e in ereignisse._ereignisse_je_police(df)[17]] == ["ERH", "PEX"]


def _regelzeile(code, jahr, *, anteil=float("nan"), verfahren="", tag=None):
    return {"vertragsjahr": jahr, "ereignis": code,
            "wirkungstag": pd.Timestamp(tag or dt.date(2020 + jahr, 1, 1)),
            "anteil": anteil, "verfahren": verfahren}


@pytest.mark.parametrize("fall,schlecht,gut,fehler", [
    ("tag", _regelzeile("ERH", 2, anteil=.05, tag="2022-02-01"),
     _regelzeile("ERH", 2, anteil=.05), "Wirkungstag"),
    ("erh_ende", _regelzeile("ERH", 5, anteil=.05),
     _regelzeile("ERH", 4, anteil=.05), "Erhoehung nach dem Beitragsende"),
    ("red_ende", _regelzeile("RED", 5, anteil=.5, verfahren="prospektiv"),
     _regelzeile("RED", 4, anteil=.5, verfahren="prospektiv"),
     "Herabsetzung nach dem Beitragsende"),
    ("tku_ablauf", _regelzeile("TKU", 10, anteil=.5, verfahren="teilkuendigung"),
     _regelzeile("TKU", 9, anteil=.5, verfahren="teilkuendigung"),
     "Teilkuendigung im Ablaufjahr"),
    ("pex_anteil", _regelzeile("PEX", 2, anteil=.5),
     _regelzeile("PEX", 2), "traegt Anteil oder Verfahren"),
])
def test_klv_zustandsregel_mit_zulaessigem_nachbarfall(fall, schlecht, gut, fehler):
    row = {"insurance_start": pd.Timestamp("2020-01-01"),
           "duration": 10, "premium_duration": 5}
    tarifwerk = {"red_verfahren": "prospektiv"}
    assert any(fehler in f for f in ereignisse._regelverstoesse(
        row, [schlecht], 0, None, tarifwerk=tarifwerk)), fall
    assert ereignisse._regelverstoesse(row, [gut], 0, None, tarifwerk=tarifwerk) == [], fall


def test_herabsetzung_bei_tarif_ohne_herabsetzung_wird_verweigert():
    row = {"insurance_start": pd.Timestamp("2020-01-01"),
           "duration": 10, "premium_duration": 5}
    e = _regelzeile("RED", 2, anteil=.5, verfahren="prospektiv")
    assert any("Tarif, der sie nicht kennt" in f for f in ereignisse._regelverstoesse(
        row, [e], 0, None, tarifwerk={"red_verfahren": ereignisse.TEILKUENDIGUNG}))
    assert ereignisse._regelverstoesse(
        row, [e], 0, None, tarifwerk={"red_verfahren": "prospektiv"}) == []


def test_bu_eintrag_ohne_parameter_ist_zulaessig():
    row = {"insurance_start": pd.Timestamp("2020-01-01")}
    schlecht = _regelzeile("INV", 2, anteil=.5)
    gut = _regelzeile("INV", 2)
    assert any("traegt Anteil oder Verfahren" in f for f in ereignisse._bu_regelverstoesse(row, [schlecht]))
    assert ereignisse._bu_regelverstoesse(row, [gut]) == []


def test_beitragsfrei_uebernommener_vertrag_startet_beitragsfrei():
    row = {"insurance_start": pd.Timestamp("2020-01-01"),
           "duration": 10, "premium_duration": 5}
    e = _regelzeile("PEX", 3)
    tarifwerk = {"red_verfahren": "prospektiv"}
    assert any("zweite Beitragsfreistellung" in f for f in ereignisse._regelverstoesse(
        row, [e], 3, 2, tarifwerk=tarifwerk))
    assert ereignisse._regelverstoesse(row, [e], 3, None, tarifwerk=tarifwerk) == []


# --------------------------------------------------------------------------- #
# 8. Das Tarifwerk jeder Generation in der Fuehrungssicht (Pruefung, Befund B2)
# --------------------------------------------------------------------------- #


def test_die_fuehrungssicht_haelt_das_tarifwerk_jeder_generation(plv):
    """Nicht nur die erste Generation: bestand_gesamt.toml fuehrt mit TG2015
    ein abweichendes Tarifwerk; jede Generation steht mit allen Feldern in
    ihrer Sicht."""
    config, _ = plv
    fuehrung = config.fuehrung()
    tarifwerke = {tuple(sorted(g.tarifwerk().items())) for g in config.generationen}
    assert len(tarifwerke) >= 2, "die Config traegt nur ein Tarifwerk; der Test haette keine Zaehne"
    for g in config.generationen:
        sicht = fuehrung.generation(g.name)
        assert sicht.tarifwerk == g.tarifwerk(), g.name
        assert sicht.generation_fields == g.generation_fields(), g.name
        assert sicht.nummernkreis == config.nummernkreis(g), g.name
        assert sicht.bu_generation_fields == (
            g.bu_generation_fields() if g.produkt == "bu" else None), g.name
        assert sicht.zellen == tuple(g.zellen), g.name
        assert (sicht.gueltig_von, sicht.gueltig_bis, sicht.max_endalter, sicht.produkt,
                sicht.knoten) == (g.gueltig_von, g.gueltig_bis, g.max_endalter, g.produkt,
                                  g.knoten), g.name


def test_die_buchung_bucht_jede_generation_mit_ihrem_tarifwerk(monkeypatch):
    """Zwei Generationen mit verschiedenem Tarifwerk: Die Buchung mit der
    echten Fuehrungssicht weicht von einer Sicht ab, die allen Generationen
    das Tarifwerk der ersten gibt (Mutation M10 der Pruefung)."""
    import dataclasses

    from rechner_pipeline.bestand import config as cfg

    config = load_config(KONFIG["klv"])
    gens = list(config.generationen)
    assert len(gens) >= 2
    a, b = gens[0], dataclasses.replace(gens[1], scheiben_mit_gamma1=not gens[1].scheiben_mit_gamma1)
    config2 = dataclasses.replace(config, generationen=[a, b] + gens[2:])
    strom = bestand_aus_zugangsstrom(config2)
    stamm = pd.concat([strom[strom["tarif_generation"] == a.name].head(30),
                       strom[strom["tarif_generation"] == b.name].head(30)], ignore_index=True)
    liste = Ereignisliste(leere_zugaenge(), ziehung.ziehe(stamm, config2, BIS))
    echt = ereignisse.buche(stamm, config2, BIS, liste)
    policen_b = set(stamm.loc[stamm["tarif_generation"] == b.name, "police_id"])
    assert echt.scheiben["police_id"].isin(policen_b).any(), "keine Erhoehung in der zweiten Generation"
    original = cfg.BestandConfig.fuehrung

    def m10(self):
        sicht = original(self)
        erste = sicht.generationen[0].tarifwerk
        return dataclasses.replace(sicht, generationen=tuple(
            dataclasses.replace(g, tarifwerk=erste) for g in sicht.generationen))

    monkeypatch.setattr(cfg.BestandConfig, "fuehrung", m10)
    vertauscht = ereignisse.buche(stamm, config2, BIS, liste)
    assert any(not getattr(echt, n).equals(getattr(vertauscht, n)) for n in echt._fields)


# --------------------------------------------------------------------------- #
# 9. Die Buchung kommt ohne jedes Weltfeld aus (Pruefung, Befund B4)
# --------------------------------------------------------------------------- #


def _ohne_welt(config):
    """Jedes Weltfeld nach SICHT_FELDER auf None — in der Config, im
    Tagesbetrieb und in jeder Generation. Ein neues Weltfeld zaehlt von
    selbst mit."""
    import dataclasses

    from rechner_pipeline.bestand import config as cfg

    s = cfg.SICHT_FELDER
    tagesbetrieb = dataclasses.replace(
        config.tagesbetrieb, **{f: None for f in s["Tagesbetrieb"]["welt"]})
    generationen = [dataclasses.replace(g, **{f: None for f in s["TarifGeneration"]["welt"]})
                    for g in config.generationen]
    return dataclasses.replace(
        config, **{f: None for f in s["BestandConfig"]["welt"]},
        tagesbetrieb=tagesbetrieb, generationen=generationen)


@pytest.mark.parametrize("welt", ["klv", "bu"])
def test_die_buchung_kommt_ohne_jedes_weltfeld_aus(welt, klv, bu):
    config, stamm, zugaenge = klv if welt == "klv" else bu
    liste = _liste(config, stamm, zugaenge)
    ohne_cfg = _ohne_welt(config)
    assert ohne_cfg.seed is None and ohne_cfg.annahmen is None
    assert ohne_cfg.tagesbetrieb.meldeverzug_tod is None
    assert all(g.verteilungen is None and g.neuzugang_pro_jahr is None for g in ohne_cfg.generationen)
    mit = ereignisse.buche(stamm, config, BIS, liste)
    ohne = ereignisse.buche(stamm, ohne_cfg, BIS, liste)
    for name in mit._fields:
        pd.testing.assert_frame_equal(getattr(mit, name), getattr(ohne, name))
