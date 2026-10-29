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
