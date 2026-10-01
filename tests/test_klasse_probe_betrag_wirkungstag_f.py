"""Die Fuehrungsprobe zaehlt nur endliche Betraege und Buchungen am Jahrestag — Runde F, Befund F5.

Zwei Klassen, je Instanz gezaehlt:

* **Endlicher Betrag.** ``abs(betrag - erwartet) > TOLERANZ`` ist bei NaN
  immer falsch: Ein NaN-Betrag (RED, ABL, jede Art) galt in der Probe als
  geprueft und uebereinstimmend, waehrend P-B1 ihn als 'fehlende Werte (NaN)
  in betrag' abweist. Die Invariante: JEDE Zeile der uebernommenen Vertraege
  traegt einen endlichen Betrag — die Menge ist das Ledger-Vokabular
  ``EREIGNIS_VALUES``, nicht die Menge der nachgerechneten Arten; eine solche
  Zeile wird nicht nachgerechnet und nicht als geprueft gezaehlt.
* **Wirkungstag.** Der Wirkungstag einer Herabsetzung ist der Jahrestag des
  Reduktionsjahres (Regel aus ``validate_reduktionen``, Fund N16); die
  Fuehrungsprobe verglich nur Tabelle und Ledger miteinander und bemerkte
  nicht, dass beide gleich verschoben waren. Dieselbe Regel gilt fuer jede
  andere Buchung nach dem Stichtag: Die Engine bucht zum Jahreswechsel
  (``models.bestand.jahrestag_verstoesse``); ausgenommen sind die
  Zugangsbuchungen am Zugangstag. Die RED-Zeilen bindet die Tabelle.

Die Welt ist der gefahrene zweite Baldrian-Lauf wie in
``test_klasse_probe_e``; nur Betrag bzw. Datum der von Hand eingelegten Zeile
ist der Fehler, die Positivkontrolle jeweils dieselbe Zeile mit endlichem
Betrag bzw. am Jahrestag.

Knoten: klv
"""

from __future__ import annotations

import inspect

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.gates.fuehrungsprobe import GEPRUEFTE_BUCHUNGEN, pruefe_fuehrung
from rechner_pipeline.models.bestand import (
    BETRAG_ART_JE_EREIGNIS,
    EREIGNIS_VALUES,
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    ZUGANGSTAG_EREIGNISSE,
    jahrestag_verstoesse,
    reduktion_jahrestag,
)
from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: F401
from tests.test_klasse_paarbuchung_f import eigen  # noqa: F401
from tests.test_t27_pruefstrecke_runde_c import (  # noqa: F401
    POL,
    ZUGANGSJAHR,
    _mit_red,
    _urteil,
    welt,
)

#: Jahrestag des Jahres 12 von POL (Beginn 2015-01-01) = der belegte Horizont.
JAHRESTAG = pd.Timestamp("2027-01-01")
#: Nach dem Zugang (2026-01-01), im Lauf, KEIN Jahrestag (Vertragsjahr 11).
NEBEN_DEM_JAHRESTAG = pd.Timestamp("2026-03-01")
NICHT_ENDLICH = (float("nan"), float("inf"), float("-inf"))
ARTEN_OHNE_RED = [a for a in EREIGNIS_VALUES if a != "RED"]


def _mit_zeile(welt, art: str, datum: pd.Timestamp, betrag: float, jahr=None):
    """Die Fortschreibung der Welt mit EINER eingelegten Buchung — ohne Tabelle
    und Folgezeilen; nur Art, Datum und Betrag sind der Gegenstand."""
    tab = dict(welt["tab"])
    stamm = welt["ueb"]["bestand"]
    row = stamm[stamm["police_id"] == POL].iloc[0]
    beginn = pd.Timestamp(row["insurance_start"])
    if jahr is None:
        jahr = ((datum.year * 12 + datum.month) - (beginn.year * 12 + beginn.month)) // 12
    neu = pd.DataFrame([{
        "police_id": POL, "tarif_generation": row["tarif_generation"], "ereignis": art,
        "vertragsjahr": int(jahr), "status_date": datum,
        "betrag_art": BETRAG_ART_JE_EREIGNIS[art][0], "betrag": betrag,
        "betrag_herkunft": "gerechnet"}])[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))
    tab["ledger"] = pd.concat([tab["ledger"], neu], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    return tab


def _befunde(urteil, art: str):
    return [b for b in urteil["befunde"] if b["art"] == art]


# --------------------------------------------------------------------------- #
# Endlicher Betrag
# --------------------------------------------------------------------------- #


def test_ratsche_die_probe_prueft_die_endlichkeit_ueber_das_ganze_vokabular():
    """Statisch: Die Pruefung der Endlichkeit steht in der Probe und nennt keine
    Ereignisart (sie gilt fuer jede), und die nachgerechneten Arten sind eine
    echte Teilmenge des Vokabulars — Beweis, dass 'jede Art' mehr ist als die
    Menge der Nachrechnung. Mutationsprobe: die Endlichkeitspruefung in
    ``pruefe_fuehrung`` entfernen -> rot."""
    quelle = inspect.getsource(pruefe_fuehrung)
    assert "np.isfinite(" in quelle and "betrag_nicht_endlich" in quelle
    assert set(GEPRUEFTE_BUCHUNGEN) < set(EREIGNIS_VALUES)


@pytest.mark.parametrize("betrag", NICHT_ENDLICH, ids=["nan", "inf", "-inf"])
@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_probe_meldet_jeden_nicht_endlichen_betrag_genau_einmal(welt, art, betrag):
    """Zaehltest je Ereignisart und Wert: Die Zeile am Jahrestag im Lauf mit
    nicht endlichem Betrag bringt GENAU einen Befund 'betrag_nicht_endlich', und
    bei den nachgerechneten Arten keinen zusaetzlichen Abweichungsbefund und
    keine Zaehlung als geprueft (ein Fehler, ein Befund). Positivkontrolle:
    dieselbe Zeile mit endlichem Betrag bringt keinen.
    Mutationsprobe: die Endlichkeitspruefung entfernen -> alle Faelle rot;
    die Zeile nicht aus ``nach`` nehmen -> die Faelle der nachgerechneten Arten
    rot (Abweichungsbefund bzw. Zaehlung)."""
    basis = _urteil(welt, welt["tab"])
    gut = _urteil(welt, _mit_zeile(welt, art, JAHRESTAG, 1.0))
    assert _befunde(gut, "betrag_nicht_endlich") == []
    urteil = _urteil(welt, _mit_zeile(welt, art, JAHRESTAG, betrag))
    treffer = _befunde(urteil, "betrag_nicht_endlich")
    assert len(treffer) == 1, urteil["befunde"][:4]
    assert treffer[0]["text"].startswith(f"{art}-Buchung") and treffer[0]["police_id"] == str(POL)
    assert not urteil["bestanden"]
    if art in GEPRUEFTE_BUCHUNGEN:
        assert urteil["buchungen_geprueft"][art] == basis["buchungen_geprueft"][art]
        assert urteil["buchungen_abweichend"] == basis["buchungen_abweichend"]
        assert [b for b in urteil["befunde"] if b["art"] == "buchung"] == []


def test_ein_nan_betrag_einer_vorhandenen_herabsetzung_besteht_die_probe_nicht(welt):
    """Der Fall des Gutachters an einer ECHTEN Herabsetzung (Tabelle und Ledger
    stimmig): Eine NaN-Auszahlung galt als uebereinstimmend. Positivkontrolle:
    dieselbe Herabsetzung mit dem Soll besteht. Mutationsprobe: die
    Endlichkeitspruefung entfernen -> rot."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 1)
    assert _urteil(welt, tab)["bestanden"]
    led = tab["ledger"].copy()
    i = led.index[(led["ereignis"] == "RED") & (led["betrag_art"] == "RKW_teilkuendigung")]
    assert len(i) == 1, "die Welt traegt keine Auszahlung der Teilkuendigung"
    led.loc[i, "betrag"] = np.nan
    urteil = _urteil(welt, dict(tab, ledger=led))
    assert not urteil["bestanden"]
    assert len(_befunde(urteil, "betrag_nicht_endlich")) == 1


# --------------------------------------------------------------------------- #
# Wirkungstag
# --------------------------------------------------------------------------- #


def test_ratsche_die_regel_ist_eine_und_beide_konsumenten_rufen_sie():
    """Die Jahrestag-Regel ist eine Funktion: ``validate_reduktionen`` und die
    Probe rufen ``reduktion_jahrestag``, keine Abschrift der Datumsarithmetik.
    Mutationsprobe: in einem der beiden eine eigene ``DateOffset``-Rechnung
    einbauen -> rot."""
    from rechner_pipeline.models.bestand import validate_reduktionen

    assert "reduktion_jahrestag(" in inspect.getsource(validate_reduktionen)
    assert "reduktion_jahrestag(" in inspect.getsource(pruefe_fuehrung)
    assert "jahrestag_verstoesse(" in inspect.getsource(pruefe_fuehrung)
    assert "DateOffset" not in inspect.getsource(validate_reduktionen)
    assert reduktion_jahrestag("2015-02-01", 11) == pd.Timestamp("2026-02-01")


def test_die_regel_selbst_lasst_nur_die_zugangsbuchung_am_zugangstag_aus(welt):
    """Die Regel im Kleinen, mit den Zahlen von Hand: Beginn 2015-02-01, Zugang
    2026-01-01 — Jahrestag des Jahres 10 ist 2025-02-01, der Zugangstag also
    kein Jahrestag. ZUG/MIG/PEX am Zugangstag sind ausgenommen, STO am selben
    Tag nicht. Mutationsprobe: die Ausnahme auf alle Arten ausdehnen -> der
    STO-Fall rot; sie streichen -> die Zugangsfaelle rot."""
    stamm = welt["ueb"]["bestand"]
    zeile = stamm[stamm["police_id"] == 7000044].iloc[0]
    assert (pd.Timestamp(zeile["insurance_start"]), pd.Timestamp(zeile["bestandszugang"])) == (
        pd.Timestamp("2015-02-01"), pd.Timestamp("2026-01-01"))
    arten = ["ZUG", "MIG", "PEX", "STO"]
    led = pd.DataFrame({
        "police_id": [7000044] * 4, "ereignis": arten,
        "vertragsjahr": [10] * 4, "status_date": [pd.Timestamp("2026-01-01")] * 4})
    assert set(ZUGANGSTAG_EREIGNISSE) == {"ZUG", "MIG", "PEX"}
    assert list(jahrestag_verstoesse(led, stamm)) == [False, False, False, True]
    am_jahrestag = led.assign(status_date=pd.Timestamp("2025-02-01"))
    assert not jahrestag_verstoesse(am_jahrestag, stamm).any()


@pytest.mark.parametrize("art", ARTEN_OHNE_RED)
def test_die_probe_haelt_jede_art_am_jahrestag_gruen(welt, art):
    """Positivkontrolle je Art: dieselbe Zeile am Jahrestag bringt keinen
    Wirkungstag-Befund."""
    urteil = _urteil(welt, _mit_zeile(welt, art, JAHRESTAG, 1.0))
    assert _befunde(urteil, "wirkungstag") == [], urteil["befunde"][:4]


@pytest.mark.parametrize("art", ARTEN_OHNE_RED)
def test_die_probe_meldet_jede_art_neben_dem_jahrestag_genau_einmal(welt, art):
    """Zaehltest je Art: eine Buchung im Lauf, aber nicht am Jahrestag, bringt
    GENAU einen Befund zu ihrem Platz — den Wirkungstag-Befund, oder bei den
    Ausnahme-Ereignissen (ZUG, MIG: Zugangstag; ABL: Vertragsende) den ihrer
    Zeitpunktregel, die sie schon meldet (ein Fehler, ein Befund).
    Mutationsprobe: ``jahrestag_verstoesse`` in ``pruefe_fuehrung`` entfernen
    -> die Faelle ohne Ausnahmeregel rot; ``~gemeldet`` weglassen -> ZUG, MIG
    und ABL zeigen zwei Befunde."""
    urteil = _urteil(welt, _mit_zeile(welt, art, NEBEN_DEM_JAHRESTAG, 1.0))
    platz = [b for b in urteil["befunde"]
             if b["art"] in ("wirkungstag", "ausnahme_ereignis", "buchungsfenster")
             and b["text"].startswith(f"{art}-Buchung")]
    assert len(platz) == 1, [b["text"] for b in urteil["befunde"]][:5]
    if art not in ("ZUG", "MIG", "ABL"):
        assert platz[0]["art"] == "wirkungstag" and "Jahrestag 2026-01-01" in platz[0]["text"]


def test_die_probe_meldet_ein_falsches_vertragsjahr_am_richtigen_tag(welt):
    """Die Regel prueft Datum UND Vertragsjahr zusammen: Eine Buchung am
    Jahrestag des Jahres 12 mit Vertragsjahr 11 steht nicht an ihrem Platz.
    Mutationsprobe: das Vertragsjahr aus der Sollrechnung nehmen -> rot."""
    urteil = _urteil(welt, _mit_zeile(welt, "STO", JAHRESTAG, 1.0, jahr=ZUGANGSJAHR))
    assert len(_befunde(urteil, "wirkungstag")) == 1


def test_die_probe_meldet_die_herabsetzung_mit_gleich_verschobenem_wirkungstag(welt):
    """Der Fall des Gutachters: Tabelle UND Ledger mit demselben falschen
    Wirkungstag (zwei Monate VOR dem Jahrestag: im Lauf, nach dem Zugang und
    nicht hinter dem Horizont). Die Vergleichsregel
    'Ledger gleich Tabelle' sieht nichts; die Jahrestag-Regel meldet EINEN
    Befund. Positivkontrolle: derselbe Aufbau am Jahrestag bestanden.
    Mutationsprobe: die Tabellenpruefung in ``pruefe_fuehrung`` entfernen ->
    rot; die RED-Zeilen nicht von der Zeilenregel ausnehmen -> rot (zwei
    Befunde fuer einen Fehler)."""
    tab = _mit_red(welt, POL, ZUGANGSJAHR + 1)
    assert _urteil(welt, tab)["bestanden"]
    verschoben = tab["reduktionen"].copy()
    jahrestag = pd.Timestamp(verschoben.loc[verschoben["police_id"] == POL, "reduktion_datum"].iloc[0])
    neu = jahrestag - pd.DateOffset(months=2)
    verschoben.loc[verschoben["police_id"] == POL, "reduktion_datum"] = neu
    led = tab["ledger"].copy()
    led.loc[(led["police_id"] == POL) & (led["ereignis"] == "RED"), "status_date"] = neu
    urteil = _urteil(welt, dict(tab, reduktionen=verschoben, ledger=led))
    treffer = [b for b in urteil["befunde"] if "Jahrestag" in b["text"]]
    assert len(treffer) == 1 and treffer[0]["art"] == "herabsetzung", urteil["befunde"][:4]
    assert str(jahrestag.date()) in treffer[0]["text"] and str(neu.date()) in treffer[0]["text"]
    assert not urteil["bestanden"]


# --------------------------------------------------------------------------- #
# Nachbesserung Runde F: die Regel ist am ECHTEN Lauf gemessen, nicht nur am gebauten
# --------------------------------------------------------------------------- #


def test_der_gefahrene_uebernahmelauf_traegt_jede_zeile_am_jahrestag(welt):
    """Messung am gefahrenen Baldrian-Lauf (uebernommene Vertraege, Zugang am
    2026-01-01, der kein Jahrestag sein muss): Ledger der Uebernahme UND der
    Fortschreibung stehen ohne Verstoss gegen die Jahrestag-Regel — die Regel
    ist nicht gegen den eigenen Lauf geschrieben. Positivkontrolle je Art, die
    der Lauf bucht (ZUG, PEX, ABL): dieselbe Zeile einen Monat verschoben ->
    GENAU diese Zeile. Mutationsprobe: die Ausnahme am Zugangstag streichen ->
    die ZUG- und PEX-Zeilen der Uebernahme sind Verstoesse, rot; die Pruefung
    des Datums streichen -> die Verschiebung bleibt unbemerkt, rot."""
    stamm = welt["ueb"]["bestand"]
    for led in (welt["ueb"]["ledger"], welt["tab"]["ledger"]):
        assert len(led) > 30 and not jahrestag_verstoesse(led, stamm).any()
    led = welt["tab"]["ledger"]
    assert set(led["ereignis"]) == {"ZUG", "PEX", "ABL"}
    for art in ("ZUG", "PEX", "ABL"):
        i = led.index[led["ereignis"] == art][0]
        verschoben = led.copy()
        verschoben.loc[i, "status_date"] = verschoben.loc[i, "status_date"] + pd.DateOffset(months=1)
        maske = jahrestag_verstoesse(verschoben, stamm)
        assert list(verschoben.index[maske]) == [i], art


@pytest.mark.parametrize("art", ["ZUG", "ERH", "PEX", "STO", "TOD", "ABL"])
def test_der_echte_lauf_des_eigenen_geschaefts_traegt_jede_zeile_am_jahrestag(eigen, art):
    """Messung am echten Lauf mit Neuzugang (E13 des Pruefers): Die Engine bucht
    jedes GeVo am Jahrestag; die Regel meldet auf dem unveraenderten Ledger
    nichts. Positivkontrolle je Art: eine Zeile der Art einen Monat verschoben ->
    GENAU diese Zeile (der Zugang des eigenen Geschaefts steht am Beginn, dem
    Jahrestag des Jahres 0). Mutationsprobe: die Regel auf ``!= soll`` ohne
    Vertragsjahr umbauen -> rot."""
    led, stamm = eigen["ledger"], eigen["stamm"]
    assert len(led) > 100 and not jahrestag_verstoesse(led, stamm).any()
    assert art in set(led["ereignis"])
    i = led.index[led["ereignis"] == art][3]
    verschoben = led.copy()
    verschoben.loc[i, "status_date"] = verschoben.loc[i, "status_date"] + pd.DateOffset(months=1)
    assert list(verschoben.index[jahrestag_verstoesse(verschoben, stamm)]) == [i]


# --------------------------------------------------------------------------- #
# Nachbesserung Runde F: die Messung steht im Befundtext
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("betrag", NICHT_ENDLICH, ids=["nan", "inf", "-inf"])
def test_der_befund_nennt_den_gemessenen_betrag_und_das_datum(welt, betrag):
    """Verankerung: Der Befundtext traegt, was der Test gemessen hat — den
    Betrag (``nan``/``inf``), das Datum der Zeile und die Betragsart —, damit
    der Test nicht aus einem anderen Grund gruen wird. Mutationsprobe: den
    Betrag aus dem Text nehmen -> rot."""
    urteil = _urteil(welt, _mit_zeile(welt, "STO", JAHRESTAG, betrag))
    (treffer,) = _befunde(urteil, "betrag_nicht_endlich")
    assert repr(betrag) in treffer["text"]
    assert "2027-01-01" in treffer["text"] and "RKW" in treffer["text"]


@pytest.mark.parametrize("art", ["STO", "TOD", "PEX"])
def test_der_wirkungstag_befund_nennt_datum_jahrestag_und_vertragsjahr(welt, art):
    """Verankerung: Der Befund einer Zeile neben dem Jahrestag nennt das
    gebuchte Datum (2026-03-01), den Jahrestag des Vertragsjahres (2026-01-01)
    und das Vertragsjahr (11) — die Zahlen der gemessenen Welt (Beginn
    2015-01-01, Zugang 2026-01-01). Mutationsprobe: das Vertragsjahr aus dem Text
    nehmen -> rot."""
    urteil = _urteil(welt, _mit_zeile(welt, art, NEBEN_DEM_JAHRESTAG, 1.0))
    (treffer,) = _befunde(urteil, "wirkungstag")
    text = treffer["text"]
    assert text.startswith(f"{art}-Buchung am 2026-03-01 ")
    assert "Jahrestag 2026-01-01" in text and "Vertragsjahres 11" in text
