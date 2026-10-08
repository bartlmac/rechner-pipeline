"""Herabsetzung und Teilkuendigung im Tagesbetrieb der PLV — mit den Annahmen der Config.

Seit dem Auftrag des Maintainers vom 2026-10-01 erzeugt die Config der PLV
beide Vorgaenge (``[annahmen]``: Herabsetzung 0,8 Prozent, Teilkuendigung
0,5 Prozent je Jahr; Bedeutung in ``test_plv_vorgaenge_im_configbestand``).
Bis dahin waren Seite, Paket und Monatsbericht fuer ``RED`` und ``TKU`` nur
per Ratsche ueber die Aufzaehler gedeckt: Ein Leser KANNTE den Code, aber
kein Test sah ihn in einem gefuehrten Stand. Hier laeuft der Tageslauf
mit den Annahmen der echten Config — Erstbefuellung bis Silvester, dann der
Neujahrstag mit Monats- und Jahreswechsel — und jeder Leser wird gegen das
Journal gehalten: P-B1, Abschluss, Bestandsbericht, Seite, Stands-Paket.

Die Welt ist die schnelle Testwelt (``_kleine_config``) mit zehnfachem
Neugeschaeft und Betriebsbeginn 2025-01-01: Beide Vorgaenge setzen ein
volles Vertragsjahr voraus, und mit dem Betriebsbeginn 1994 dauerte die
Erstbefuellung eine Viertelstunde. Die Annahmen sind die der Config, Byte
fuer Byte.

Dazu der Befund aus Punkt 4 des Auftrags: Eine geaenderte Config in einer
bestehenden Ablage rechnete still weiter, obwohl jeder Lauf die Geschichte
vom Betriebsbeginn an neu rechnet. Der Lauf verweigert jetzt benannt.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import (
    EXIT_OK,
    EXIT_USAGE,
    Ablage,
    lies_protokoll,
    tageslauf,
)
from tests.freigabe_testschluessel import betriebsargs
from tests.test_betrieb_tageslauf import _ablage as _kleine_ablage
from tests.test_betrieb_tageslauf import _kleine_config

SILVESTER = dt.date(2026, 12, 31)
NEUJAHR = dt.date(2027, 1, 1)


def _config_text() -> str:
    text = _kleine_config(10.0)
    assert "herabsetzung = { a = 0.008, b = 0.0 }" in text, "Config ohne Herabsetzung"
    assert "teilkuendigung = { a = 0.005, b = 0.0 }" in text, "Config ohne Teilkuendigung"
    text = text.replace("betriebsbeginn = 2026-01-01", "betriebsbeginn = 2025-01-01")
    assert "betriebsbeginn = 2025-01-01" in text
    return text


@pytest.fixture(scope="module")
def gefuehrt(tmp_path_factory):
    ablage = Ablage(tmp_path_factory.mktemp("plv"))
    ablage.configs.mkdir(parents=True)
    ablage.config_pfad.write_text(_config_text(), encoding="utf-8")
    zeilen = [tageslauf(ablage, SILVESTER), tageslauf(ablage, NEUJAHR)]
    return ablage, zeilen


def _journal_vorgaenge(ablage) -> pd.DataFrame:
    j = read_portfolio(ablage.tagesjournal_pfad)
    return j[j["ereignis"].isin(["RED", "TKU"])]


def test_der_tageslauf_bucht_beide_vorgaenge_und_die_wache_ist_gruen(gefuehrt):
    """Herabsetzung: eine Buchung (die neue Summe, kein Geldfluss).
    Teilkuendigung: zwei (die neue Summe und die Auszahlung). Das Journal
    traegt genau die Vorgaenge, die der Stand bis heute fuehrt."""
    ablage, zeilen = gefuehrt
    for code, zeile in zeilen:
        assert code == EXIT_OK, zeile.get("fehler")
        assert zeile["pb1"]["urteil"] == "gruen", zeile["pb1"]["befunde"]
    assert zeilen[-1][1]["pb1"]["geprueft"]["reduktionen_zeilen"] > 0
    j = _journal_vorgaenge(ablage)
    arten = j.groupby(["ereignis", "police_id"])["betrag_art"].apply(lambda s: tuple(sorted(s)))
    assert set(arten.loc["RED"]) == {("VS_herabsetzung",)}
    assert set(arten.loc["TKU"]) == {("RKW_teilkuendigung", "VS_teilkuendigung")}
    assert (j.loc[j["betrag_art"] == "RKW_teilkuendigung", "betrag"] > 0).all()
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    im_stand = ledger[ledger["ereignis"].isin(["RED", "TKU"])
                      & (ledger["status_date"] <= pd.Timestamp(NEUJAHR))]
    schluessel = ["police_id", "ereignis", "status_date", "betrag_art", "betrag"]
    pd.testing.assert_frame_equal(
        j[schluessel].sort_values(schluessel).reset_index(drop=True),
        im_stand[schluessel].sort_values(schluessel).reset_index(drop=True))
    vorgaenge = j.drop_duplicates(["police_id", "ereignis"])["ereignis"].value_counts().to_dict()
    assert vorgaenge == {"RED": 8, "TKU": 8}


def test_der_abschluss_fuehrt_die_summe_nach_dem_vorgang(gefuehrt):
    """Der Abschluss zum Neujahrstag fuehrt jeden betroffenen Vertrag mit
    der gebuchten Summe nach dem Vorgang (ohne spaeteren Vorfall), der
    Vertrag bleibt in Kraft (POL, kein Statuswechsel). Betraege des
    Deckungskapitals pinnt dieser Test nicht."""
    ablage, _ = gefuehrt
    abschluss = read_portfolio(ablage.abschluesse / "abschluss_2027-01-01.parquet").set_index("police_id")
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    summe = ledger[ledger["betrag_art"].isin(["VS_herabsetzung", "VS_teilkuendigung"])]
    andere = ledger[~ledger["ereignis"].isin(["RED", "TKU", "ZUG"])]
    geprueft = 0
    for z in summe.itertuples():
        spaeter = andere[(andere["police_id"] == z.police_id)
                         & (andere["status_date"] >= z.status_date)]
        if z.police_id not in abschluss.index or len(spaeter):
            continue
        assert abschluss.loc[z.police_id, "status_code"] == "POL"
        assert abschluss.loc[z.police_id, "leistung"] == pytest.approx(z.betrag, rel=1e-12)
        geprueft += 1
    assert geprueft >= 10


def test_der_bestandsbericht_weist_beide_vorgaenge_aus(gefuehrt):
    """Ereignistabelle und Bewegungskonto des Jahresberichts zum
    Neujahrstag (der grosse Bericht; der Monatsbericht ist ein eigenes
    Dokument): je Vorgang die Anzahl aus dem Ledger, und das Konto des
    vollen Jahres 2026 traegt eine Teilkuendigung ungleich null."""
    ablage, _ = gefuehrt
    html = (ablage.berichte / "jahresbericht_2026.html").read_text(encoding="utf-8")
    ledger = read_portfolio(ablage.stand / "ledger.parquet")
    for titel, code, art in (("Beitragsherabsetzung (RED)", "RED", "VS_herabsetzung"),
                             ("Teilkündigung (TKU)", "TKU", "VS_teilkuendigung"),
                             ("Teilkündigung (TKU)", "TKU", "RKW_teilkuendigung")):
        soll = int(((ledger["ereignis"] == code) & (ledger["betrag_art"] == art)).sum())
        treffer = re.search(re.escape(titel) + r"</td><td class='num'>(\d+)</td><td>"
                            + re.escape(art) + "<", html)
        assert treffer, (titel, art)
        assert int(treffer.group(1)) == soll > 0
    assert "± Teilkündigung" in html and "± Herabsetzung" in html


def test_seite_und_paket_zeigen_beide_vorgaenge(gefuehrt, tmp_path):
    """Die Seite zaehlt je Vorfall (nicht je Buchungszeile): Eine
    Teilkuendigung mit zwei Buchungen ist EIN Vorfall. Paket und Seite
    sagen dasselbe wie das Journal."""
    ablage, _ = gefuehrt
    j = _journal_vorgaenge(ablage)
    soll = j[["police_id", "ereignis", "status_date"]].drop_duplicates()["ereignis"].value_counts()
    modell = st.stand_modell(ablage)
    je = modell["buchungen"]["je_ereignis"]
    assert (je["RED"], je["TKU"]) == (int(soll["RED"]), int(soll["TKU"]))
    html = (ablage.wurzel / "seite" / "index.html").read_text(encoding="utf-8")
    for titel, code in (("Beitragsherabsetzung", "RED"), ("Teilkündigung", "TKU")):
        assert f"<tr><td>{titel}</td><td class=\"num\">{je[code]}</td></tr>" in html
    paket = st.stands_paket(ablage, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    stand = json.loads((paket / st.PAKET_DATEI).read_text(encoding="utf-8"))
    assert stand["buchungen"]["je_ereignis"]["RED"] == je["RED"]
    assert stand["buchungen"]["je_ereignis"]["TKU"] == je["TKU"]


# --------------------------------------------------------------------------- #
# Punkt 4: eine geaenderte Config rechnet nicht still weiter
# --------------------------------------------------------------------------- #

def test_eine_geaenderte_config_haelt_den_lauf_an_und_nennt_den_ausweg(tmp_path):
    """Jeder Lauf rechnet die Geschichte vom Betriebsbeginn an neu. Eine
    geaenderte Config gilt damit von Beginn der Simulation an, und eine
    Ablage mit festgeschriebenen Abschluessen reproduziert sie nicht mehr.
    Vorher rechnete der Lauf still weiter (Exit 0, gruen), solange die
    Aenderung zufaellig keine gebuchte Vergangenheit traf, sonst brach er
    an einem Betragsunterschied im Journal ab, ohne die Ursache zu nennen.
    Jetzt: benannt, der Stand bleibt, eine rote Protokollzeile nennt den
    Grund, Ausweg Neuaufsetzen.

    Mutationsprobe: den Aufruf ``_pruefe_config_unveraendert`` in
    ``_stand_bauen`` entfernen -> der zweite Lauf ist gruen, rot."""
    ablage = _kleine_ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    alt = ablage.config_pfad.read_bytes()
    manifest = (ablage.stand / "laufmanifest.json").read_bytes()
    journal = ablage.tagesjournal_pfad.read_bytes()
    neu = alt.replace(b"herabsetzung = { a = 0.008, b = 0.0 }",
                      b"herabsetzung = { a = 0.02, b = 0.0 }")
    assert neu != alt
    ablage.config_pfad.write_bytes(neu)
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert code == EXIT_USAGE and zeile["uebernommen"] is False
    meldung = zeile["fehler"]
    assert meldung.startswith("TageslaufError") and "Config" in meldung
    assert "2026-01-31" in meldung
    assert "betrieb.neuaufsetzen" in meldung and "--config" in meldung
    assert (ablage.stand / "laufmanifest.json").read_bytes() == manifest
    assert ablage.tagesjournal_pfad.read_bytes() == journal
    assert tl.gefuehrter_tag(ablage) == dt.date(2026, 1, 31)
    assert tl.main(["--stand", str(ablage.wurzel), "--heute", "2026-02-03",
                    *betriebsargs()]) == EXIT_USAGE
    # Auch eine Aenderung ohne Wirkung (ein Kommentar) ist eine andere
    # Config: Ob sie wirkt, wuesste der Lauf erst, nachdem er gerechnet hat.
    ablage.config_pfad.write_bytes(alt + b"# nachgezogen\n")
    code, zeile = tageslauf(ablage, dt.date(2026, 2, 3))
    assert code == EXIT_USAGE and "neuaufsetzen" in zeile["fehler"]
    # Mit der Config, mit der das Protokoll gerechnet hat, laeuft der Tag.
    ablage.config_pfad.write_bytes(alt)
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    assert lies_protokoll(ablage.protokoll_pfad)[-1]["heute"] == "2026-02-03"


def test_der_bereits_gefuehrte_tag_ist_ein_no_op_nur_mit_derselben_config(tmp_path):
    """Der bereits gefuehrte Tag rechnet nicht (benannter No-op) — aber nur
    mit der Config, mit der er gerechnet wurde. Bis zur Pruefrunde G stand
    hier das Gegenteil ("dort aendert sie nichts", Exit 0 mit getauschter
    Config); plv/betrieb/README.md sagte an einer Stelle "haelt an, sobald die
    Kopie nicht mehr die ist", an einer anderen "selber Tag ist No-op".
    Entscheid: Die Wache laeuft vor dem No-op (Fund G07; ausfuehrlich in
    ``tests/test_runde_g_tageslauf.py``)."""
    ablage = _kleine_ablage(tmp_path / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 31))
    assert code == EXIT_OK and zeile.get("bereits_gefuehrt") is True
    ablage.config_pfad.write_bytes(ablage.config_pfad.read_bytes() + b"# x\n")
    code, zeile = tageslauf(ablage, dt.date(2026, 1, 31))
    assert code == EXIT_USAGE and zeile["uebernommen"] is False
