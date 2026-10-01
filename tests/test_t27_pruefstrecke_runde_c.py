"""Die Pruefstrecke der Herabsetzung, Runde C — Befunde RC02, RC03, RC04.

Die Klasse: P-B1, Fuehrungsprobe und der A-M4-Konsument nahmen eine
Herabsetzung an, die der Lauf nie gebucht haben kann, und liessen die
Bewertungsgrundlage der Fortschreibung unbewacht. Drei Gesichter derselben
Luecke, im echten Fall des zweiten Laufs (Police 7000001 mit 43.000 EUR
Summe, Police 7000047 beitragsfrei uebernommen) nachgefahren:

* **RC02** — eine Herabsetzung VOR dem Bestandszugang (Vorgeschichte der
  abgebenden Gesellschaft) oder NACH dem im Manifest belegten Horizont ist
  keine Buchung dieses Laufs. Eingetragen vom 2025-01-01 (Zugang
  2026-01-01) kuerzte sie die Summe am Stichtag von 43.000 auf 25.800 EUR,
  bei gruenem P-B1, gruener Probe und gruenem Konsumenten; die Probe
  rechnete Buchungen vor dem Stichtag gar nicht nach.
* **RC03** — eine Herabsetzung auf einem beitragsfreien Vertrag: Die
  Engine zieht sie nicht, die Bewertung bricht ab, P-B1 und Probe leiteten
  ihr Soll aus dem beitragspflichtigen Vertrag her.
* **RC04** — ``schichten.parquet`` und ``merkmale.parquet`` (und
  ``verankerung.parquet``) der Fortschreibung sind Vertragsidentitaet, auf
  der der Abschluss bewertet; die Probe hielt sie gegen nichts.

Jede Aussage hat ihre Positivkontrolle (dieselbe Eintragung an einem
zulaessigen Ort bzw. die unveraenderte Tabelle bleibt gruen) — sonst
waere ein Test, der nie anschlaegt, von einem, der nichts sieht, nicht zu
unterscheiden.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import pytest

from rechner_pipeline.bestand.auswertung import grundlagen_je_police
from rechner_pipeline.bestand.config import config_aus_text
from rechner_pipeline.bestand.ledger_bindung import _Herleitung, pruefe_ledger_betraege
from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.bestand.schichten import schichten_je_police
from rechner_pipeline.gates import bestand_validate, fuehrungsprobe
from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from rechner_pipeline.models.bestand import (
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    REDUKTIONEN_NAMES,
    REDUKTIONEN_SPALTEN,
    validate_ledger,
    validate_reduktionen,
)
from tests.test_baldrian2_e2e import (  # noqa: F401
    ANKER,
    GENERATION,
    METADATEN,
    REPO_ROOT,
    STICHTAG_1,
    STICHTAG_2,
    _lieferungs_flags,
    _probe_material,
    gefahrener_fall,
)
from tests.test_reduktionen_vertrag import _reduktionen as _red_zeile
from tests.test_reduktionen_vertrag import _stamm as _stamm_eigen

#: Police 7000001: beitragspflichtig, Beginn 2015-01-01, Zugang 2026-01-01
#: (elf volle Vertragsjahre), Summe 43.000 EUR — der Fall des Befunds RC02.
POL = 7000001
#: Police 7000047: beitragsfrei uebernommen (PEX im Vertragsjahr 1) — RC03.
PEX_POLICE = 7000047
ANTEIL = 0.6
ZUGANGSJAHR = 11        # volle Vertragsjahre von 7000001 am Zugang 2026-01-01


# --------------------------------------------------------------------------- #
# Datenvertrag: validate_reduktionen / validate_ledger (P-B1)
# --------------------------------------------------------------------------- #


def _uebernommen():
    """Der Stamm der Reduktions-Tests als UEBERNOMMENER Vertrag: Beginn
    2015-01-01, Zugang 2026-01-01."""
    stamm = _stamm_eigen()
    stamm["bestandszugang"] = pd.Timestamp("2026-01-01")
    return stamm


def test_eine_herabsetzung_vor_dem_bestandszugang_weist_p_b1_ab():
    """RC02. Mutationsprobe: die Zugangsgrenze in validate_reduktionen
    entfernen -> rot."""
    fehler = validate_reduktionen(_uebernommen(), _red_zeile(jahr=10))   # 2025-01-01
    assert any("Bestandszugang" in f for f in fehler), fehler


def test_die_zugangsgrenze_ist_scharf_und_die_positivkontrolle_bleibt_gruen():
    """Am Zugangstag selbst simuliert die Engine nichts (erste moegliche RED:
    ein Jahr danach) — das Jahr des Zugangs ist unzulaessig, das folgende
    zulaessig."""
    stamm = _uebernommen()
    assert any("Bestandszugang" in f for f in validate_reduktionen(stamm, _red_zeile(jahr=ZUGANGSJAHR)))
    assert validate_reduktionen(stamm, _red_zeile(jahr=ZUGANGSJAHR + 1)) == []


def test_eigenes_geschaeft_ist_von_der_zugangsgrenze_nicht_betroffen():
    """Beim eigenen Geschaeft ist der Zugang der Beginn: jede Herabsetzung
    ab Jahr 1 liegt danach. Sonst kippte die Grenze jeden bestehenden Lauf."""
    assert validate_reduktionen(_stamm_eigen(), _red_zeile(jahr=1)) == []


def test_eine_herabsetzung_nach_dem_belegten_horizont_weist_p_b1_ab():
    """RC02, zweite Instanz. Mutationsprobe: die Horizontgrenze entfernen -> rot."""
    stamm = _uebernommen()
    zeile = _red_zeile(jahr=13)                                          # 2028-01-01
    fehler = validate_reduktionen(stamm, zeile, horizont=_dt.date(2027, 1, 1))
    assert any("belegten Horizont" in f for f in fehler), fehler
    # Positivkontrolle: am Horizont selbst und ohne belegten Horizont gruen.
    assert validate_reduktionen(stamm, zeile, horizont=_dt.date(2028, 1, 1)) == []
    assert validate_reduktionen(stamm, zeile) == []


def _ledger(stamm, *, red_datum: str, red_jahr: int, horizont_zeile: bool = False):
    zeilen = [
        {"police_id": 900_001, "tarif_generation": "TG2015", "ereignis": "ZUG",
         "vertragsjahr": ZUGANGSJAHR, "status_date": pd.Timestamp("2026-01-01"),
         "betrag_art": "VS", "betrag": 60000.0, "betrag_herkunft": "geliefert"},
        {"police_id": 900_001, "tarif_generation": "TG2015", "ereignis": "RED",
         "vertragsjahr": red_jahr, "status_date": pd.Timestamp(red_datum),
         "betrag_art": "VS_herabsetzung", "betrag": 36000.0, "betrag_herkunft": "gerechnet"},
    ]
    return pd.DataFrame(zeilen)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))


def test_eine_red_buchung_vor_dem_zugang_weist_validate_ledger_ab():
    """RC02: die Buchung selbst, nicht nur die Tabelle. Mutationsprobe: den
    RED-Zweig in validate_ledger entfernen -> rot."""
    stamm = _uebernommen()
    fehler = validate_ledger(stamm, _ledger(stamm, red_datum="2025-01-01", red_jahr=10))
    assert any("RED-Buchung nicht nach dem Bestandszugang" in f for f in fehler), fehler
    # Positivkontrolle: dieselbe Buchung ein Jahr nach dem Zugang ist formal gueltig.
    assert validate_ledger(stamm, _ledger(stamm, red_datum="2027-01-01", red_jahr=12)) == []
    # Die Grenze ist scharf: am Zugangstag selbst ebenso unzulaessig.
    am_zugang = validate_ledger(stamm, _ledger(stamm, red_datum="2026-01-01", red_jahr=ZUGANGSJAHR))
    assert any("RED-Buchung nicht nach dem Bestandszugang" in f for f in am_zugang), am_zugang


def test_eine_red_buchung_nach_dem_horizont_weist_validate_ledger_ab():
    stamm = _uebernommen()
    led = _ledger(stamm, red_datum="2028-01-01", red_jahr=13)
    fehler = validate_ledger(stamm, led, horizont=_dt.date(2027, 1, 1))
    assert any("nach dem belegten Horizont" in f for f in fehler), fehler
    assert validate_ledger(stamm, led, horizont=_dt.date(2028, 1, 1)) == []
    assert validate_ledger(stamm, led) == []


def test_eine_herabsetzung_auf_beitragsfreiem_vertrag_weist_validate_reduktionen_ab():
    """RC03: Die Teilkuendigung ist nicht mehr 'ausdruecklich nach PEX
    zugelassen'. Mutationsprobe: die PEX-Jahr-Regel entfernen -> rot."""
    stamm = _stamm_eigen()
    historie = pd.DataFrame([{
        "police_id": 900_001, "status_id": 2, "status_code": "PEX",
        "status_date": pd.Timestamp("2016-01-01"),           # Jahr 1
    }])
    fehler = validate_reduktionen(
        stamm, _red_zeile(jahr=12, verfahren="teilkuendigung"), historie=historie)
    assert any("Teilkuendigung" in f and "Beitragsfreistellung im Jahr 1" in f for f in fehler), fehler
    # Die Grenze ist scharf: im PEX-Jahr selbst ist der Vertrag schon
    # beitragsfrei (die Engine bucht PEX vor der Herabsetzung desselben Jahres).
    im_pex_jahr = historie.assign(status_date=pd.Timestamp("2027-01-01"))   # PEX im Jahr 12
    assert validate_reduktionen(
        stamm, _red_zeile(jahr=12, verfahren="teilkuendigung"), historie=im_pex_jahr)
    # Positivkontrolle: VOR der Beitragsfreistellung bleibt sie zulaessig.
    assert validate_reduktionen(
        stamm, _red_zeile(jahr=8, verfahren="teilkuendigung"), historie=im_pex_jahr) == []
    assert validate_reduktionen(
        stamm, _red_zeile(jahr=11, verfahren="teilkuendigung"), historie=im_pex_jahr) == []


# --------------------------------------------------------------------------- #
# Die Welt: der gefahrene Fall des zweiten Laufs mit einer Herabsetzungs-Config
# --------------------------------------------------------------------------- #


def _tabellen(lauf: Path) -> Dict[str, Any]:
    def lies(name: str, pflicht: bool = True):
        pfad = lauf / f"{name}.parquet"
        return read_portfolio(pfad) if pfad.is_file() else None

    horizont = json.loads((lauf / "laufmanifest.json").read_text(encoding="utf-8"))["horizont"]
    return {
        "ledger": lies("ledger"), "scheiben": lies("scheiben"), "historie": lies("historie"),
        "bestand": lies("bestand_gesamt"), "reduktionen": lies("reduktionen"),
        "schichten": lies("schichten"), "verankerung": lies("verankerung"),
        "merkmale": lies("merkmale"), "horizont": _dt.date.fromisoformat(horizont),
    }


@pytest.fixture(scope="module")
def welt(gefahrener_fall):  # noqa: F811
    ueb, _fort, basis = _probe_material(gefahrener_fall)
    ab = gefahrener_fall / "abgeleitet"
    text = (ab / "bestand-config.toml").read_text(encoding="utf-8")
    # Die Rate ist positiv, aber so klein, dass die Engine keine Herabsetzung
    # zieht: Eine Config ohne Herabsetzungsrate belegt keinen Anteil (RC05,
    # Runde C), und die von Hand eingelegten Herabsetzungen dieser Tests
    # sollen an der Probe und an P-B1 gemessen werden, nicht an der Rate.
    text_red = text + (f"\n[annahmen]\nred_anteil = {ANTEIL}\n"
                       "[annahmen.herabsetzung]\na = 1e-6\nb = 0.0\n")
    cfg_pfad = ab / "cfg-runde-c.toml"
    cfg_pfad.write_text(text_red, encoding="utf-8")
    config = config_aus_text(text_red)
    assert config.validate() == []
    tab = _tabellen(ab / "bestand-nach")
    assert tab["horizont"] == _dt.date.fromisoformat(STICHTAG_2)
    basis_red = dict(basis, config=config)
    gut = pruefe_fuehrung(uebernahme=ueb, fortschreibung=tab, **basis_red)
    assert gut["bestanden"], ("Positivkontrolle der Welt", gut["befunde"][:3])
    assert POL in set(int(p) for p in ueb["bestand"]["police_id"])
    return {"fall": gefahrener_fall, "ueb": ueb, "tab": tab, "basis": basis_red,
            "config": config, "cfg_pfad": cfg_pfad}


def _zeile(welt, pid: int) -> Dict[str, Any]:
    stamm = welt["ueb"]["bestand"]
    return stamm[stamm["police_id"] == pid].to_dict("records")[0]


def _mit_red(welt, pid: int, jahr: int, *, verfahren: str = "teilkuendigung",
             anteil: float = ANTEIL, tab: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Die Fortschreibung der Welt mit EINER eingetragenen Herabsetzung —
    Tabelle und Ledger stimmig, die Betraege nach der Regel von P-B1
    (``_Herleitung.red_buchungen``), also so, wie die Engine sie buchen
    wuerde. Nur der ORT der Eintragung ist der Fehler."""
    tab = dict(tab or welt["tab"])
    ueb, config = welt["ueb"], welt["config"]
    row = _zeile(welt, pid)
    beginn = pd.Timestamp(row["insurance_start"])
    datum = beginn + pd.DateOffset(years=jahr)
    schicht = schichten_je_police(ueb["bestand"], ueb["schichten"], ueb["verankerung"])
    scheiben = [(int(j), float(v)) for j, v in zip(
        ueb["scheiben"][ueb["scheiben"]["police_id"] == pid]["erhoehung_jahr"],
        ueb["scheiben"][ueb["scheiben"]["police_id"] == pid]["sum_insured"])]
    h = _Herleitung(row, grundlagen_je_police(config, ueb["merkmale"])(pid, row["tarif_generation"]),
                    scheiben, {g.name: g.tarifwerk() for g in config.generationen}[row["tarif_generation"]])
    h.setze_reduktion(jahr, anteil, verfahren, schicht.get(pid))
    soll = h.red_buchungen(schicht.get(pid))
    neu_red = pd.DataFrame([{
        "police_id": pid, "reduktion_jahr": jahr, "reduktion_datum": datum,
        "anteil": anteil, "verfahren": verfahren}])[list(REDUKTIONEN_NAMES)].astype(
            dict(REDUKTIONEN_SPALTEN))
    alt = tab["reduktionen"]
    tab["reduktionen"] = (neu_red if alt is None else pd.concat([alt, neu_red], ignore_index=True)
                          ).sort_values("police_id", kind="stable").reset_index(drop=True)
    zeilen = pd.DataFrame([{
        "police_id": pid, "tarif_generation": row["tarif_generation"], "ereignis": "RED",
        "vertragsjahr": jahr, "status_date": datum, "betrag_art": art, "betrag": float(b),
        "betrag_herkunft": "gerechnet"} for art, b in soll.items()])[list(LEDGER_NAMES)].astype(
            dict(LEDGER_SPALTEN))
    tab["ledger"] = pd.concat([tab["ledger"], zeilen], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    return tab


def _urteil(welt, tab):
    return pruefe_fuehrung(uebernahme=welt["ueb"], fortschreibung=tab, **welt["basis"])


def _texte(urteil, art: Optional[str] = None) -> List[str]:
    return [b["text"] for b in urteil["befunde"] if art is None or b["art"] == art]


# --------------------------------------------------------------------------- #
# RC02 in der Fuehrungsprobe
# --------------------------------------------------------------------------- #


def test_die_positivkontrolle_eine_herabsetzung_im_lauf_besteht_die_probe(welt):
    """Dieselbe Eintragung, ein Jahr NACH dem Zugang (2027-01-01 = Horizont):
    die Welt und ihre Betraege sind so gebaut, dass die Probe sie annimmt —
    nur der Ort macht sie in den folgenden Tests zum Fehler."""
    urteil = _urteil(welt, _mit_red(welt, POL, ZUGANGSJAHR + 1))
    assert urteil["bestanden"], urteil["befunde"][:3]
    assert urteil["buchungen_geprueft"]["RED"] >= 2


def test_die_probe_weist_die_herabsetzung_vor_dem_zugang_ab(welt):
    """Der Fall der Runde C: RED 2025-01-01 vor ZUG 2026-01-01. Vorher: 0
    Befunde. Mutationsprobe: die Zugangsgrenze in pruefe_fuehrung entfernen
    -> der Befund 'Bestandszugang' verschwindet (der Endledger-Befund
    bleibt, deshalb pruefen die Tests unten beide getrennt)."""
    urteil = _urteil(welt, _mit_red(welt, POL, ZUGANGSJAHR - 1))
    assert not urteil["bestanden"]
    assert any("Bestandszugang" in t for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]


def test_die_zugangsgrenze_der_probe_ist_scharf(welt):
    """Am Zugangstag selbst simuliert die Engine nichts: Jahr 11 von 7000001
    faellt auf 2026-01-01 = Zugang. Mutationsprobe: ``<=`` zu ``<`` -> rot."""
    urteil = _urteil(welt, _mit_red(welt, POL, ZUGANGSJAHR))
    assert any("Bestandszugang" in t for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]


def test_die_probe_haelt_das_ledger_bis_zum_stichtag_gegen_die_uebernahme(welt):
    """Ohne Herabsetzungstabelle: allein die RED-BUCHUNG vor dem Zugang, im
    Ledger der Fortschreibung. ``_pruefe_endzustand`` haelt die Zeit bis zum
    Stichtag gegen die Uebernahme. Mutationsprobe: den Ledger-Vergleich in
    _pruefe_endzustand entfernen -> rot."""
    mit = _mit_red(welt, POL, ZUGANGSJAHR - 1)
    tab = dict(mit, reduktionen=welt["tab"]["reduktionen"])
    urteil = _urteil(welt, tab)
    assert any("bis zum Stichtag" in t for t in _texte(urteil, "endledger")), urteil["befunde"][:4]


def test_die_probe_rechnet_eine_verfaelschte_buchung_vor_dem_stichtag_nicht_nur_nach(welt):
    """+1 EUR auf der Zeile vor dem Stichtag: die Probe hat sie nie gesehen
    (nur P-B1 fiel). Jetzt faellt sie an der Vorgeschichte."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR - 1)
    led = tab["ledger"].copy()
    i = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "VS_herabsetzung")][0]
    led.loc[i, "betrag"] += 1.0
    assert not _urteil(welt, dict(tab, ledger=led))["bestanden"]


def test_die_uebernahme_selbst_bleibt_fuer_die_vorgeschichte_gruen(welt):
    """Positivkontrolle der Endledger-Regel: die unveraenderte Welt hat
    Buchungen bis zum Stichtag (ZUG, PEX) und ist gruen — der Vergleich
    schlaegt nicht auf jedem Bestand an."""
    led = welt["tab"]["ledger"]
    assert (pd.to_datetime(led["status_date"]) <= pd.Timestamp(STICHTAG_1)).sum() >= 29
    assert not [b for b in _urteil(welt, welt["tab"])["befunde"] if b["art"] == "endledger"]


def test_die_probe_weist_die_herabsetzung_nach_dem_horizont_ab(welt):
    """RC02, zweite Instanz. Mutationsprobe: die Horizontgrenze in
    pruefe_fuehrung entfernen -> rot."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 2)                # 2028-01-01
    assert tab["horizont"] == _dt.date(2027, 1, 1)
    urteil = _urteil(welt, tab)
    assert any("belegten Horizont" in t for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]
    # Positivkontrolle: mit dem Horizont, der sie einschliesst, gruen.
    assert _urteil(welt, dict(tab, horizont=_dt.date(2028, 1, 1)))["bestanden"]


def test_der_horizont_wird_an_tabelle_und_buchung_getrennt_gehalten(welt):
    """Die Tabelle allein (Zeilen der Herabsetzung fehlen im Ledger) und die
    Buchung allein (Tabelle fehlt) — je ein eigener Befund, damit die
    Streichung EINER der beiden Pruefungen nicht von der anderen verdeckt
    wird. Mutationsproben: je einen der beiden Zweige entfernen -> rot."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 2)
    ohne_buchung = dict(tab, ledger=welt["tab"]["ledger"])
    urteil = _urteil(welt, ohne_buchung)
    assert any(t.startswith("Teilkuendigung am") and "belegten Horizont" in t
               for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]
    ohne_tabelle = dict(tab, reduktionen=welt["tab"]["reduktionen"])
    urteil = _urteil(welt, ohne_tabelle)
    assert any(t.startswith("RED-Buchung nach dem belegten Horizont")
               for t in _texte(urteil, "herabsetzung")), urteil["befunde"][:4]


def _mit_eigener_pex(tab: Dict[str, Any], pid: int, jahr: int, gebucht_am: str) -> Dict[str, Any]:
    """Eine PEX-Buchung der FORTSCHREIBUNG (nicht der Uebernahme) im Vertragsjahr."""
    row = tab["ledger"][tab["ledger"]["police_id"] == pid].iloc[0]
    zeile = pd.DataFrame([{
        "police_id": pid, "tarif_generation": row["tarif_generation"], "ereignis": "PEX",
        "vertragsjahr": jahr, "status_date": pd.Timestamp(gebucht_am), "betrag_art": "VS_bfr",
        "betrag": 1000.0, "betrag_herkunft": "gerechnet"}])[list(LEDGER_NAMES)].astype(
            dict(LEDGER_SPALTEN))
    return dict(tab, ledger=pd.concat([tab["ledger"], zeile], ignore_index=True))


def test_eine_eigene_beitragsfreistellung_derselben_oder_frueherer_jahre_schliesst_die_herabsetzung_aus(welt):
    """RC03 fuer den Vertrag, der in der FORTSCHREIBUNG beitragsfrei wird
    (nicht schon uebernommen beitragsfrei): PEX im Jahr 12, Herabsetzung im
    Jahr 12 (die Engine bucht PEX vor der Herabsetzung desselben Jahres,
    also ist der Vertrag beitragsfrei) und im Jahr 13. Im Jahr 12 vor einer
    PEX im Jahr 13 bleibt sie zulaessig. Mutationsproben: ``<=`` zu ``<``
    in der Probe -> rot; den Rueckgriff auf die eigene PEX-Buchung
    entfernen -> rot."""
    same = _mit_eigener_pex(_mit_red(welt, POL, ZUGANGSJAHR + 1), POL, ZUGANGSJAHR + 1, "2027-01-01")
    assert any("beitragsfrei gestellten Vertrag" in t and "Jahr 12" in t
               for t in _texte(_urteil(welt, same), "herabsetzung"))
    spaeter = _mit_eigener_pex(_mit_red(welt, POL, ZUGANGSJAHR + 2), POL, ZUGANGSJAHR + 1, "2027-01-01")
    assert any("beitragsfrei gestellten Vertrag" in t
               for t in _texte(_urteil(welt, spaeter), "herabsetzung"))
    davor = _mit_eigener_pex(_mit_red(welt, POL, ZUGANGSJAHR + 1), POL, ZUGANGSJAHR + 2, "2028-01-01")
    assert not any("beitragsfrei gestellten Vertrag" in t
                   for t in _texte(_urteil(welt, dict(davor, horizont=_dt.date(2028, 1, 1)))))


# --------------------------------------------------------------------------- #
# RC03: Herabsetzung auf einem beitragsfreien Vertrag
# --------------------------------------------------------------------------- #


def _pex_vertrag_und_jahr(welt):
    row = _zeile(welt, PEX_POLICE)
    assert row["status_code"] == "PEX", "die Welt traegt 7000047 nicht beitragsfrei"
    beginn, zugang = pd.Timestamp(row["insurance_start"]), pd.Timestamp(row["bestandszugang"])
    ab_jahr = ((zugang.year * 12 + zugang.month) - (beginn.year * 12 + beginn.month)) // 12
    return ab_jahr + 1


def test_die_probe_leitet_fuer_einen_beitragsfreien_vertrag_kein_soll_her(welt):
    """RC03, Fall 7000047: PEX im Vertragsjahr 1, Teilkuendigung danach.
    Ledger und Tabelle tragen genau die Betraege, die aus dem
    beitragspflichtigen Vertrag folgen — vorher 'bestanden'. Jetzt der
    Widerspruch. Mutationsprobe: die PEX-Pruefung in pruefe_fuehrung
    entfernen -> rot (das Soll des beitragspflichtigen Vertrags passt zu
    den Zeilen)."""
    jahr = _pex_vertrag_und_jahr(welt)
    urteil = _urteil(welt, _mit_red(welt, PEX_POLICE, jahr))
    assert not urteil["bestanden"]
    assert any("beitragsfrei gestellten Vertrag" in t for t in _texte(urteil, "herabsetzung")), \
        urteil["befunde"][:4]
    # Kein Betrags-Befund daneben: Es gibt kein Soll, gegen das ein Betrag falsch waere.
    assert not [b for b in urteil["befunde"] if b["art"] == "buchung"]
    # ... und keine Vollstaendigkeit: Summe verschoben oder Auszahlung gestrichen
    # aendert an der Meldung nichts. Mutationsproben: den Skip in der
    # Vollstaendigkeits- bzw. der Zeilenschleife der Probe entfernen -> rot.
    for verstuemmelt in _verstuemmelt(_mit_red(welt, PEX_POLICE, jahr)):
        nur = [b for b in _urteil(welt, verstuemmelt)["befunde"] if b["art"] in ("buchung", "herabsetzung")]
        assert len(nur) == 1 and "beitragsfrei gestellten Vertrag" in nur[0]["text"], nur


def test_p_b1_leitet_fuer_einen_beitragsfreien_vertrag_kein_soll_her(welt):
    """RC03 in ``pruefe_ledger_betraege``: Widerspruch statt Betragsherleitung.
    Mutationsprobe: den Widerspruch in ledger_bindung entfernen -> []."""
    tab = _mit_red(welt, PEX_POLICE, _pex_vertrag_und_jahr(welt))
    fehler = pruefe_ledger_betraege(
        tab["bestand"], tab["ledger"], welt["config"], scheiben=tab["scheiben"],
        historie=tab["historie"], merkmale=tab["merkmale"], schichten=tab["schichten"],
        verankerung=tab["verankerung"], reduktionen=tab["reduktionen"])
    assert any("beitragsfrei gestellten Vertrag" in f for f in fehler), fehler
    assert not any("Ledger" in f and "Kern" in f for f in fehler), fehler
    # Positivkontrolle: dieselbe Herabsetzung auf dem beitragspflichtigen Vertrag: keine Befunde.
    gut = _mit_red(welt, POL, ZUGANGSJAHR + 1)
    assert pruefe_ledger_betraege(
        gut["bestand"], gut["ledger"], welt["config"], scheiben=gut["scheiben"],
        historie=gut["historie"], merkmale=gut["merkmale"], schichten=gut["schichten"],
        verankerung=gut["verankerung"], reduktionen=gut["reduktionen"]) == []


def test_p_b1_weist_die_herabsetzung_auf_dem_beitragsfreien_vertrag_ueber_die_tabelle_ab(welt):
    """Dieselbe Regel im Datenvertrag (Tabelle gegen Historie)."""
    tab = _mit_red(welt, PEX_POLICE, _pex_vertrag_und_jahr(welt))
    fehler = validate_reduktionen(tab["bestand"], tab["reduktionen"], tab["historie"])
    assert any("beitragsfrei" in f.lower() and "Zustandswechsel" in f for f in fehler), fehler


def _verstuemmelt(tab: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Dieselbe Welt mit (a) um 1 EUR verschobener Summe und (b) gestrichener
    Auszahlung: Gegen ein hergeleitetes Soll waeren beide Befunde."""
    led = tab["ledger"]
    summe = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "VS_herabsetzung")]
    zahl = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "RKW_teilkuendigung")]
    assert len(summe) and len(zahl)
    plus = led.copy()
    plus.loc[summe[0], "betrag"] += 1.0
    return [dict(tab, ledger=plus), dict(tab, ledger=led.drop(index=zahl[0]))]


def test_p_b1_meldet_nur_den_widerspruch_und_leitet_kein_soll_her(welt):
    """Fuer eine Herabsetzung auf einem beitragsfreien Vertrag gibt es kein
    Soll — weder Betrag noch Vollstaendigkeit. Die Meldung ist der
    Widerspruch, nichts daneben (kein 'Ledger x, Kern y' gegen einen Kern,
    den es nicht gibt). Mutationsproben: den Zeilen-Skip bzw. den
    Vollstaendigkeits-Skip in ledger_bindung entfernen -> rot."""
    basis = _mit_red(welt, PEX_POLICE, _pex_vertrag_und_jahr(welt))
    for tab in _verstuemmelt(basis):
        fehler = pruefe_ledger_betraege(
            tab["bestand"], tab["ledger"], welt["config"], scheiben=tab["scheiben"],
            historie=tab["historie"], merkmale=tab["merkmale"], schichten=tab["schichten"],
            verankerung=tab["verankerung"], reduktionen=tab["reduktionen"])
        assert len(fehler) == 1 and "beitragsfrei gestellten Vertrag" in fehler[0], fehler


def test_p_b1_widerspruch_ist_am_pex_jahr_scharf(welt):
    """Beitragsfrei ab dem Reduktionsjahr (PEX-Jahr == Reduktionsjahr) ist
    schon ein Widerspruch, ein PEX ein Jahr SPAETER nicht. Mutationsprobe:
    ``<=`` zu ``<`` in ledger_bindung -> rot."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 1)
    beginn = pd.Timestamp(_zeile(welt, POL)["insurance_start"])

    def fehler(pex_jahr: int):
        historie = pd.concat([tab["historie"], pd.DataFrame([{
            "police_id": POL, "status_id": int(tab["historie"]["status_id"].max()) + 1,
            "status_code": "PEX", "status_date": beginn + pd.DateOffset(years=pex_jahr)}])],
            ignore_index=True).astype(tab["historie"].dtypes.to_dict())
        return pruefe_ledger_betraege(
            tab["bestand"], tab["ledger"], welt["config"], scheiben=tab["scheiben"],
            historie=historie, merkmale=tab["merkmale"], schichten=tab["schichten"],
            verankerung=tab["verankerung"], reduktionen=tab["reduktionen"])

    assert any("beitragsfrei gestellten Vertrag" in f for f in fehler(ZUGANGSJAHR + 1))
    assert not any("beitragsfrei gestellten Vertrag" in f for f in fehler(ZUGANGSJAHR + 2))


# --------------------------------------------------------------------------- #
# RC04: Nebentabellen der Fortschreibung
# --------------------------------------------------------------------------- #


def test_positivkontrolle_unveraenderte_nebentabellen_geben_null_befunde(welt):
    urteil = _urteil(welt, welt["tab"])
    assert urteil["befunde"] == []
    for rolle in ("schichten", "verankerung", "merkmale"):
        assert welt["tab"][rolle] is not None and len(welt["tab"][rolle]), rolle


def test_ein_verschobenes_rho_in_den_schichten_der_fortschreibung_faellt(welt):
    """RC04: rho 1e-8 -> 0,05 in der Fortschreibungs-schichten.parquet
    (Deckungskapital +55 Prozent, vorher 0 Befunde). Mutationsprobe: den
    Nebentabellen-Vergleich UND den Schichtbeleg-Vergleich der
    Fortschreibung entfernen -> rot; jeden einzeln -> der andere haelt."""
    tab = dict(welt["tab"])
    sch = tab["schichten"].copy()
    sch.loc[sch["police_id"] == POL, "rho"] = 0.05
    urteil = _urteil(welt, dict(tab, schichten=sch))
    assert not urteil["bestanden"]
    schicht = [b for b in urteil["befunde"] if b["art"] == "schicht" and b.get("feld") == "rho"]
    assert any("Fortschreibung" in b["text"] and "Uebernahme" in b["text"] for b in schicht), schicht
    assert any("Schichtbeleg" in b["text"] and "Fortschreibung" in b["text"] for b in schicht), schicht
    assert all(b["police_id"] == str(POL) for b in schicht)


def test_ein_gewechseltes_merkmal_in_der_fortschreibung_faellt(welt):
    """RC04: nichtraucher -> raucher (Deckungskapital -66,31 EUR). Mutationsprobe:
    den Vergleich der Merkmale entfernen -> rot."""
    tab = dict(welt["tab"])
    m = tab["merkmale"].copy()
    eigene = m[m["police_id"] == POL]
    i = eigene.index[0]
    dimension = m.loc[i, "dimension"]
    andere = sorted(set(m[m["dimension"] == dimension]["auspraegung"]) - {m.loc[i, "auspraegung"]})
    assert andere, "die Welt kennt keine zweite Auspraegung — der Test bezeugte nichts"
    m.loc[i, "auspraegung"] = andere[0]
    urteil = _urteil(welt, dict(tab, merkmale=m))
    assert not urteil["bestanden"]
    assert any(b["art"] == "merkmale" and b.get("feld") == "auspraegung" and b["police_id"] == str(POL)
               for b in urteil["befunde"]), urteil["befunde"][:4]


def test_eine_verschobene_verankerung_in_der_fortschreibung_faellt(welt):
    """Dieselbe Klasse an der dritten Nebentabelle (der Angreifer der
    Runde C liess sie im Skript, der Befund nennt zwei: die Bewertung
    haengt an allen drei)."""
    v = welt["tab"]["verankerung"].copy()
    v.loc[v["police_id"] == POL, "monate_ta"] = v.loc[v["police_id"] == POL, "monate_ta"] - 12
    urteil = _urteil(welt, dict(welt["tab"], verankerung=v))
    assert any(b["art"] == "verankerung" and b.get("feld") == "monate_ta"
               for b in urteil["befunde"]), urteil["befunde"][:4]


@pytest.mark.parametrize("rolle", ["schichten", "verankerung", "merkmale"])
def test_eine_fehlende_oder_zusaetzliche_zeile_der_nebentabelle_faellt(welt, rolle):
    tab = welt["tab"]
    ohne = tab[rolle].iloc[1:]
    assert any(rolle in b["text"] and "fehlen" in b["text"]
               for b in _urteil(welt, dict(tab, **{rolle: ohne}))["befunde"])
    assert any(rolle in b["text"] and "fehlen" in b["text"]
               for b in _urteil(welt, dict(tab, **{rolle: tab[rolle].iloc[0:0]}))["befunde"])
    doppelt = pd.concat([tab[rolle], tab[rolle].iloc[[0]]], ignore_index=True).astype(
        tab[rolle].dtypes.to_dict())
    assert any(rolle in b["text"] and "mehrfach" in b["text"]
               for b in _urteil(welt, dict(tab, **{rolle: doppelt}))["befunde"])


def test_werkzeug_aufrufer_ohne_die_nebentabellen_bleiben_unbehelligt(welt):
    """Eine Fortschreibung, die die Nebentabellen gar nicht modelliert
    (kein Schluessel), wird nicht mit dem Fehlen bestraft — die Wache
    gilt dort, wo ``fuehre_probe`` sie liest (Dateien, unten)."""
    tab = {k: v for k, v in welt["tab"].items() if k not in ("schichten", "verankerung", "merkmale")}
    assert _urteil(welt, tab)["bestanden"]


# --------------------------------------------------------------------------- #
# Dateiebene: derselbe Weg wie der Betrieb (fuehre_probe, bestand_validate)
# --------------------------------------------------------------------------- #

_LAUF_NR = iter(range(1000))


def _lauf_kopie(welt) -> Path:
    ab = welt["fall"] / "abgeleitet"
    ziel = ab / f"bestand-runde-c-{next(_LAUF_NR)}"
    shutil.copytree(ab / "bestand-nach", ziel)
    for pfad in ziel.iterdir():
        pfad.chmod(0o644)
    return ziel


def _schreibe_lauf(welt, ziel: Path, tab: Dict[str, Any]) -> None:
    """Die Tabellen einer Welt in ein Laufverzeichnis, Manifest nachgefuehrt
    (Hashes aller Ausgaben, Config der Herabsetzungs-Welt)."""
    for name, datei in (("ledger", "ledger"), ("reduktionen", "reduktionen"),
                        ("schichten", "schichten"), ("merkmale", "merkmale"),
                        ("verankerung", "verankerung")):
        if tab[name] is not None:
            write_portfolio(tab[name], ziel / f"{datei}.parquet")
    m = json.loads((ziel / "laufmanifest.json").read_text(encoding="utf-8"))
    for pfad in ziel.glob("*.parquet"):
        if pfad.name != "bestand.parquet":
            m["ausgaben"][pfad.name] = hashlib.sha256(pfad.read_bytes()).hexdigest()
    m["config"]["sha256"] = hashlib.sha256(welt["cfg_pfad"].read_bytes()).hexdigest()
    (ziel / "laufmanifest.json").write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


def _pb1(welt, lauf: Path):
    argv = [
        "--portfolio", str(lauf / "bestand_gesamt.parquet"),
        "--historie", str(lauf / "historie.parquet"),
        "--ledger", str(lauf / "ledger.parquet"),
        "--scheiben", str(lauf / "scheiben.parquet"),
        "--merkmale", str(lauf / "merkmale.parquet"),
        "--schichten", str(lauf / "schichten.parquet"),
        "--verankerung", str(lauf / "verankerung.parquet"),
        "--config", str(welt["cfg_pfad"]),
        "--bis", STICHTAG_2,
        "--manifest", str(lauf / "laufmanifest.json"),
        "--repo-root", str(REPO_ROOT),
        "--diagnostics-dir", str(lauf / "diag"),
    ]
    if (lauf / "reduktionen.parquet").is_file():
        argv += ["--reduktionen", str(lauf / "reduktionen.parquet")]
    return bestand_validate.main(argv)


def _probe_datei(welt, lauf: Path) -> tuple:
    fall = welt["fall"]
    out = lauf / "probe.json"
    code = fuehrungsprobe.main([
        "--fall", str(fall), "--repo-root", str(REPO_ROOT), "--generation", GENERATION,
        "--uebernahme", str(fall / "abgeleitet" / "bestand"), "--fortschreibung", str(lauf),
        "--config", str(welt["cfg_pfad"]),
        "--zeilen", str(fall / "abgeleitet" / "transformation" / "zeilen.json"),
        "--vorgeschichte", METADATEN, "--stichtag", STICHTAG_1,
        "--anker-erwartungswerte", ANKER,
        "--schicht", str(fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"),
        "--stoab-je-baustein", "--out", str(out),
    ] + _lieferungs_flags())
    return code, json.loads(out.read_text(encoding="utf-8"))


def test_datei_positivkontrolle_lauf_mit_herabsetzung_im_lauf_ist_gruen(welt):
    """Dieselbe Herabsetzung an 7000001 ein Jahr nach dem Zugang: P-B1 Exit 0,
    Probe Exit 0 — die Welt der folgenden Dateitests."""
    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, _mit_red(welt, POL, ZUGANGSJAHR + 1))
    pb1 = _pb1(welt, lauf)
    assert pb1.exit_code == 0, pb1.errors
    code, beleg = _probe_datei(welt, lauf)
    assert code == 0 and beleg["befunde"] == [], beleg["befunde"][:3]


def test_datei_herabsetzung_vor_dem_stichtag_gibt_p_b1_exit_20_und_probe_befund(welt):
    """Der Fall der Runde C, End-zu-Ende: RED 2025-01-01 vor ZUG 2026-01-01,
    Manifest stimmig nachgefuehrt. P-B1 Exit 20, die Probe Befund."""
    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, _mit_red(welt, POL, ZUGANGSJAHR - 1))
    pb1 = _pb1(welt, lauf)
    assert pb1.exit_code == 20, (pb1.exit_code, pb1.errors)
    # Beide Wachen der Engine, je fuer sich: die Tabelle und die Buchung.
    assert any(e["code"] == "reduktionen" and "Bestandszugang" in e["message"] for e in pb1.errors), pb1.errors
    assert any(e["code"] == "ledger" and "Bestandszugang" in e["message"] for e in pb1.errors), pb1.errors
    code, beleg = _probe_datei(welt, lauf)
    assert code == 1 and any("Bestandszugang" in b["text"] for b in beleg["befunde"]), beleg["befunde"][:3]


def test_datei_herabsetzung_nach_dem_horizont_gibt_p_b1_exit_20_und_probe_befund(welt):
    """RC02, zweite Instanz, End-zu-Ende: Lauf bis 2027-01-01, RED am
    2028-01-01. Der Horizont kommt aus dem Manifest — bestand_validate
    reicht --bis, der Wert des Laufs ist aber der belegte."""
    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, _mit_red(welt, POL, ZUGANGSJAHR + 2))
    pb1 = _pb1(welt, lauf)
    assert pb1.exit_code == 20, (pb1.exit_code, pb1.errors)
    assert any(e["code"] == "reduktionen" and "belegten Horizont" in e["message"] for e in pb1.errors), pb1.errors
    assert any(e["code"] == "ledger" and "belegten Horizont" in e["message"] for e in pb1.errors), pb1.errors
    code, beleg = _probe_datei(welt, lauf)
    assert code == 1 and any("belegten Horizont" in b["text"] for b in beleg["befunde"]), beleg["befunde"][:3]


def test_datei_teilkuendigung_auf_beitragsfreiem_vertrag_wird_abgewiesen(welt):
    """RC03, End-zu-Ende (Police 7000047, Teilkuendigung im Jahr nach dem
    Zugang, Betraege des beitragspflichtigen Vertrags)."""
    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, _mit_red(welt, PEX_POLICE, _pex_vertrag_und_jahr(welt)))
    pb1 = _pb1(welt, lauf)
    assert pb1.exit_code == 20, (pb1.exit_code, pb1.errors)
    assert any("beitragsfrei" in e["message"] for e in pb1.errors), pb1.errors
    code, beleg = _probe_datei(welt, lauf)
    assert code == 1 and any("beitragsfrei gestellten Vertrag" in b["text"] for b in beleg["befunde"])


def test_datei_nebentabellen_der_fortschreibung_werden_von_der_probe_gelesen(welt):
    """RC04 ueber ``fuehre_probe``: Die Tabellen werden aus dem Laufverzeichnis
    gelesen und gebunden. Mutationsprobe: die Nebentabellen in ``fuehre_probe``
    nicht lesen -> rot (in-memory blieben sie gruen)."""
    lauf = _lauf_kopie(welt)
    tab = dict(welt["tab"])
    sch = tab["schichten"].copy()
    sch.loc[sch["police_id"] == POL, "rho"] = 0.05
    _schreibe_lauf(welt, lauf, dict(tab, schichten=sch))
    code, beleg = _probe_datei(welt, lauf)
    assert code == 1
    assert any(b["art"] == "schicht" and b.get("feld") == "rho" for b in beleg["befunde"]), beleg["befunde"][:3]
    # Der Lauf ist als solcher stimmig (Manifest nachgefuehrt): allein die Probe sieht es.
    m = tab["merkmale"].copy()
    i = m.index[m["police_id"] == POL][0]
    m.loc[i, "auspraegung"] = sorted(set(m[m["dimension"] == m.loc[i, "dimension"]]["auspraegung"])
                                     - {m.loc[i, "auspraegung"]})[0]
    lauf2 = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf2, dict(tab, merkmale=m))
    code2, beleg2 = _probe_datei(welt, lauf2)
    assert code2 == 1 and any(b["art"] == "merkmale" for b in beleg2["befunde"])


def test_datei_unveraenderter_lauf_gibt_null_befunde(welt):
    """Positivkontrolle der Dateiebene: kopierter, unveraenderter Lauf."""
    lauf = _lauf_kopie(welt)
    code, beleg = _probe_datei(welt, lauf)
    assert code == 0 and beleg["befunde"] == []
    assert "laufmanifest.json" in " ".join(beleg["provenienz"]["eingaben"])


# --------------------------------------------------------------------------- #
# Nachbesserung der Pruefstrecke: Teilkuendigung nach dem Beitragsende (N6)
# --------------------------------------------------------------------------- #

#: Police 7000159: beitragspflichtig, t = 7, n = 12, Beginn 2015-05-01,
#: Zugang 2026-01-01 — die Welt des Pruefers fuer die Teilkuendigung im
#: beitragsfrei ausfinanzierten Nachlauf (Jahr 11 >= t).
NACHLAUF_POLICE = 7000159
NACHLAUF_JAHR = 11


def _p_b1_betraege(welt, tab) -> List[str]:
    return pruefe_ledger_betraege(
        tab["bestand"], tab["ledger"], welt["config"], scheiben=tab["scheiben"],
        historie=tab["historie"], merkmale=tab["merkmale"], schichten=tab["schichten"],
        verankerung=tab["verankerung"], reduktionen=tab["reduktionen"])


def test_die_teilkuendigung_im_beitragsfreien_nachlauf_ist_bewusst_zulaessig_und_wird_nachgerechnet(welt):
    """Nachbesserung, Pruefer-Befund zu RC03: Eine Teilkuendigung nach dem
    Ende der Beitragszahlung (t <= Jahr < n), beitragspflichtig gefuehrt
    (kein PEX), ist KEIN Fall der RC03-Abweisung. Entscheid: zulaessig.

    Warum: Fund N6 (d2cb348) hat sie im Datenmodell ausdruecklich
    zugelassen — Ziffer 6 kuendigt einen Summenanteil und setzt keinen
    laufenden Beitrag voraus, der Kern rechnet sie bis zur
    Versicherungsdauer (Kern 3.4.0), und die Bewertung laeuft durch. Der
    Widerspruch von RC03 gilt dem BEITRAGSFREI GESTELLTEN Vertrag (PEX-Jahr
    <= Reduktionsjahr), nicht dem ausfinanzierten. Die Probe-Invariante
    'kein Soll auf einem beitragsfreien Vertrag' haengt deshalb am
    PEX-Jahr, nicht an t. Seit dem Entscheid des Maintainers 2026-09-30
    zieht die Engine selbst diese Buchung: Im ausfinanzierten Nachlauf
    (``t <= j + 1 < n``) zieht sie die Teilkuendigung (Block F,
    Nachbesserung; gezogen und gemessen in
    tests/test_herabsetzung_ausfinanziert.py). DIESER Test haelt die
    REGISTRIERTE Variante — eine von Hand in die Tabellen gelegte
    Buchung ohne Lauf — und rechnet sie trotzdem her: Das Soll wird
    hergeleitet und gehalten, gleich ob gezogen oder eingetragen.

    Mutationsproben: (a) die Teilkuendigungs-Grenze in validate_reduktionen
    von ``n`` auf ``t`` -> rot; (b) den RC03-Widerspruch in ledger_bindung
    bzw. fuehrungsprobe zusaetzlich bei ``jahr >= t`` ausloesen -> rot;
    (c) das Soll nicht herleiten -> der verfaelschte Betrag unten bleibt
    unentdeckt -> rot."""
    row = _zeile(welt, NACHLAUF_POLICE)
    t, n = int(row["premium_duration"]), int(row["duration"])
    assert row["status_code"] == "POL" and t <= NACHLAUF_JAHR < n, (t, NACHLAUF_JAHR, n)
    tab = _mit_red(welt, NACHLAUF_POLICE, NACHLAUF_JAHR)

    # Datenvertrag, P-B1-Herleitung und Probe: null Befunde.
    assert validate_reduktionen(tab["bestand"], tab["reduktionen"], tab["historie"],
                                horizont=tab["horizont"]) == []
    assert _p_b1_betraege(welt, tab) == []
    urteil = _urteil(welt, tab)
    assert urteil["bestanden"] and urteil["befunde"] == [], urteil["befunde"][:3]

    # Die Bewertung laeuft durch (der Kern rechnet sie) — kein Abbruch wie beim
    # beitragsfrei gestellten Vertrag.
    from rechner_pipeline.bestand.auswertung import einzelwerte_am

    werte = einzelwerte_am(
        tab["bestand"], tab["historie"], welt["config"], tab["horizont"],
        scheiben=tab["scheiben"], merkmale=tab["merkmale"], schichten=tab["schichten"],
        verankerung=tab["verankerung"], reduktionen=tab["reduktionen"])
    eigene = [w for w in werte if int(w["police_id"]) == NACHLAUF_POLICE]
    assert len(eigene) == 1 and eigene[0]["deckungskapital"] > 0

    # Kein blinder Fleck: Das Soll wird auch hier hergeleitet. Verschobene
    # Summe und gestrichene Auszahlung sind Betrags-/Vollstaendigkeitsbefunde,
    # nicht der Widerspruch des beitragsfreien Vertrags.
    for verstuemmelt in _verstuemmelt(tab):
        fehler = _p_b1_betraege(welt, verstuemmelt)
        assert fehler and not any("beitragsfrei gestellten Vertrag" in f for f in fehler), fehler
        befunde = _urteil(welt, verstuemmelt)["befunde"]
        assert befunde, "verfaelschte Buchung unentdeckt"
        assert not any("beitragsfrei gestellten Vertrag" in b["text"] for b in befunde), befunde[:3]

    # Gegenprobe der Grenze: dieselbe Stelle als Herabsetzung auf Beitragsbasis
    # bleibt jenseits von t unzulaessig (nur die Teilkuendigung ist zugelassen).
    prospektiv = tab["reduktionen"].copy()
    prospektiv["verfahren"] = "prospektiv"
    assert any("Beitragszahlungsdauer" in f for f in validate_reduktionen(
        tab["bestand"], prospektiv, tab["historie"], horizont=tab["horizont"]))


def test_datei_teilkuendigung_im_beitragsfreien_nachlauf_ist_fuer_p_b1_und_probe_gruen(welt):
    """Dieselbe Entscheidung End-zu-Ende: P-B1 Exit 0, Probe Exit 0."""
    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, _mit_red(welt, NACHLAUF_POLICE, NACHLAUF_JAHR))
    pb1 = _pb1(welt, lauf)
    assert pb1.exit_code == 0, pb1.errors
    code, beleg = _probe_datei(welt, lauf)
    assert code == 0 and beleg["befunde"] == [], beleg["befunde"][:3]


# --------------------------------------------------------------------------- #
# Nachbesserung der Pruefstrecke: Manifest ohne lesbaren Horizont (kein stiller Default)
# --------------------------------------------------------------------------- #


def _pb1_mit_manifest(welt, manifest, bis):
    from rechner_pipeline.bestand.manifest import ROLLEN_DATEIEN
    from rechner_pipeline.bestand.vorbedingungen import lies_und_pruefe_pb1

    lauf = _lauf_kopie(welt)
    _schreibe_lauf(welt, lauf, welt["tab"])
    eingaben = {rolle: lauf / datei for rolle, datei in ROLLEN_DATEIEN.items()
                if (lauf / datei).is_file()}
    eingaben["config"] = welt["cfg_pfad"]
    m = manifest(json.loads((lauf / "laufmanifest.json").read_text(encoding="utf-8")))
    return lies_und_pruefe_pb1(eingaben, bis=bis, manifest=m)


@pytest.mark.parametrize("bis", [None, _dt.date.fromisoformat(STICHTAG_2)])
@pytest.mark.parametrize("kaputt", [
    lambda m: {k: v for k, v in m.items() if k != "horizont"},
    lambda m: dict(m, horizont="kein-datum"),
    lambda m: dict(m, horizont=None),
], ids=["fehlt", "kein_datum", "none"])
def test_ein_manifest_ohne_lesbaren_horizont_ist_ein_fehler_und_schaltet_die_wache_nicht_ab(welt, kaputt, bis):
    """Nachbesserung (RC02): ``lies_und_pruefe_pb1`` schluckte einen nicht
    lesbaren Manifest-Horizont zu ``None`` — die Horizontwache an
    Herabsetzung und RED-Buchung war dann still aus, bei gruener Meldung.
    Fail-fast: ein Manifest ohne lesbaren Horizont ist ein Fehler (code
    ``manifest``) mit Ausweg. Mit ``bis`` fiel der Aufruf vorher als
    rohe KeyError/ValueError aus der Funktion.

    Mutationsprobe: die Fehlermeldung entfernen (except: horizont = None)
    -> rot."""
    _t, _g, fehler, _usage = _pb1_mit_manifest(welt, kaputt, bis)
    manifestfehler = [e for e in fehler if e["code"] == "manifest"]
    assert manifestfehler and "Horizont" in manifestfehler[0]["message"], fehler
    assert "Ausweg" in manifestfehler[0]["message"], manifestfehler[0]


def test_ein_intaktes_manifest_gibt_keinen_manifestfehler(welt):
    """Positivkontrolle: derselbe Aufruf mit dem unveraenderten Manifest.
    Mit ``bis`` ist der Lauf ganz gruen; ohne ``bis`` gilt nur, dass der
    Horizont gelesen wird (die Bewegungspruefung braucht ``bis``)."""
    bis = _dt.date.fromisoformat(STICHTAG_2)
    _t, _g, fehler, usage = _pb1_mit_manifest(welt, lambda m: m, bis)
    assert fehler == [] and usage == [], (fehler[:3], usage)
    _t, _g, fehler, _usage = _pb1_mit_manifest(welt, lambda m: m, None)
    assert not [e for e in fehler if e["code"] == "manifest"], fehler[:3]
