"""Klasse: Paarbuchung je Vorfall mit Beitragswirkung — Runde F, Befund F4.

Die Invariante: Die Engine bucht je Vorfall einer Ereignisart mit
Beitragswirkung GENAU ein Paar — die Summenzeile und die Beitragszeile
(``BJB``) — fuer dieselbe Police am selben Tag; bei einem uebernommenen
Vertrag bucht der Zugang nur die Summe. Vorher band ``validate_ledger`` nur
die Summenzeile der Erhoehung an ihre Scheibe, und ``ledger_bindung`` pruefte
den BETRAG vorhandener Beitragszeilen: Eine verdoppelte oder gestrichene
Beitragszeile einer Erhoehung (und die fehlende des Zugangs) bemerkten weder
P-B1 noch die Fuehrungsprobe noch der Bericht.

Die Menge der Ereignisarten ist nicht abgetippt, sondern hergeleitet
(``models.bestand.BEITRAGSEREIGNISSE`` aus dem Vokabular der Betragsarten) und
hier mit ``==`` gegen die Stellen gehalten, an denen die Engine die
Beitragszeile bucht (Quelltext von ``bestand.ereignisse``) und gegen den
gemessenen Lauf. Drei Instrumente: Ratschen (statisch bzw. am echten Lauf,
mit Positivkontrolle), Zaehltest je Art und Verstoss (verdoppelt, fehlend,
Summenzeile fehlend) an P-B1, an der Fuehrungsprobe und am Bericht, und die
Mutationsprobe je Instanz in den Docstrings.

Nachbesserung (Runde F): Eine Zeile, die eine andere Regel schon meldet, nimmt
ihren ganzen Vorfall aus der Paarregel (Abschnitt 6); ein in der Zeit getrenntes
Paar ist EIN Befund (``tag_verschoben``); der Scanner der Ratsche kennt jede
Schreibform der Beitragszeile (positionell, Schluesselwort, Konstante, Literal)
und laeuft ueber das ganze Paket.

Knoten: klv
"""

from __future__ import annotations

import ast
import datetime as _dt
import inspect

import pandas as pd
import pytest

from rechner_pipeline.bestand import ereignisse as _ereignisse
from rechner_pipeline.bestand import ledger_bindung as _bindung
from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from rechner_pipeline.models import bestand as _modell
from rechner_pipeline.models.bestand import (
    BEITRAG_BETRAG_ART,
    BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN,
    BEITRAGSEREIGNISSE,
    EREIGNIS_VALUES,
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    PAAR_TAG_VERSCHOBEN,
    beitragspaar_verstoesse,
    validate_ledger,
)
from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: F401
from tests.test_reduktionen_vertrag import _stamm as _stamm_eigen
from tests.test_t27_pruefstrecke_runde_c import POL, _urteil, welt  # noqa: F401

VERSTOESSE = ("doppelt", "fehlt")
HORIZONT = pd.Timestamp("2027-01-01")        # Jahrestag des Jahres 12 von POL (Beginn 2015-01-01)


# --------------------------------------------------------------------------- #
# Der echte Lauf (eigenes Geschaeft): ZUG und ERH aus der Engine
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def eigen():
    """Ein echter Lauf mit Neuzugang: Die Engine bucht Zugang UND Erhoehung
    mit Beitragszeile; Stamm, Journal, Scheiben und Ledger wie P-B1 sie sieht."""
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
    from tests.test_bestand_neuzugang import EXAMPLE, REF
    from tests.zugangsstrom import bestand_aus_zugangsstrom

    bis = _dt.date(2016, 1, 1)
    config = load_config(EXAMPLE)
    basis = bestand_aus_zugangsstrom(config, bis=REF)
    erg = fortschreiben(basis, config, bis, neuzugang_ab=REF)
    return {"stamm": mit_zugaengen(basis, erg.zugaenge), "ledger": erg.ledger,
            "historie": erg.historie, "scheiben": erg.scheiben, "horizont": bis}


def _p_b1(eigen, ledger, scheiben=True):
    return validate_ledger(
        eigen["stamm"], ledger, eigen["historie"],
        eigen["scheiben"] if scheiben else None, horizont=eigen["horizont"])


def _zeile_der_art(ledger, art, betrag_art, *, summe: bool = False):
    """Index einer Zeile der Art — ``summe``: irgendeine Nicht-Beitragszeile."""
    maske = (ledger["ereignis"] == art) & (
        (ledger["betrag_art"] != BEITRAG_BETRAG_ART) if summe
        else (ledger["betrag_art"] == betrag_art))
    return ledger.index[maske][3]


def _verdoppelt(ledger, i):
    return pd.concat([ledger.iloc[:i + 1], ledger.loc[[i]], ledger.iloc[i + 1:]]).reset_index(drop=True)


def _gestrichen(ledger, i):
    return ledger.drop(i).reset_index(drop=True)


# --------------------------------------------------------------------------- #
# 1. Ratschen: die Menge ist hergeleitet und stimmt mit der Engine ueberein
# --------------------------------------------------------------------------- #


#: Die Namen, unter denen die Betragsart ``BJB`` im Quelltext steht (die Konstante
#: der Engine, die des Modells, der Alias der Ledger-Bindung).
_BJB_NAMEN = frozenset({"BJB_BETRAG_ART", "BEITRAG_BETRAG_ART", "BJB_ART"})


def _ist_bjb(knoten) -> bool:
    """Ein Argument, das die Betragsart ``BJB`` nennt: die Konstante (als Name
    oder als ``modul.NAME``) oder das Literal ``"BJB"``."""
    if isinstance(knoten, ast.Name):
        return knoten.id in _BJB_NAMEN
    if isinstance(knoten, ast.Attribute):
        return knoten.attr in _BJB_NAMEN
    return isinstance(knoten, ast.Constant) and knoten.value == "BJB"


def _ereignisse_mit_beitragszeile(quelle: str):
    """Die Ereignisarten, fuer die der Quelltext eine Zeile mit der Betragsart
    ``BJB`` bucht: Je Aufruf, der ``BJB`` als Argument traegt — positionell ODER
    als Schluesselwort, als Konstante ODER als Literal — die Ereigniscode-Literale
    unter seinen Argumenten (positionell oder Schluesselwort). Bewusste Grenze:
    Eine Betragsart, die ueber eine Zwischenvariable ankommt, sieht der Scanner
    nicht; die Messung am echten Lauf (``test_der_echte_lauf_bucht...``) faengt
    sie."""
    gefunden = set()
    for knoten in ast.walk(ast.parse(quelle)):
        if not isinstance(knoten, ast.Call):
            continue
        teile = [*knoten.args, *(k.value for k in knoten.keywords)]
        if not any(_ist_bjb(a) for a in teile):
            continue
        gefunden |= {a.value for a in teile
                     if isinstance(a, ast.Constant) and a.value in EREIGNIS_VALUES}
    return gefunden


@pytest.mark.parametrize("quelle,erwartet", [
    ('buche("RED", 3, BJB_BETRAG_ART, 1.0)', {"RED"}),
    ('buche("RED", 3, "BJB", 1.0)', {"RED"}),
    ('buche("RED", 3, art=BJB_BETRAG_ART, betrag=1.0)', {"RED"}),
    ('buche("RED", 3, art="BJB", betrag=1.0)', {"RED"}),
    ('_event(1, ereignis="PEX", jahr=0, art="BJB")', {"PEX"}),
    ('_event(1, "PEX", 0, d, art=modell.BEITRAG_BETRAG_ART)', {"PEX"}),
    ('buche("RED", 3, BEITRAG_BETRAG_ART, 1.0)', {"RED"}),
    ('buche("RED", 3, "VS", 1.0)', set()),                      # keine Beitragszeile
    ('buche("BJB", 3, "VS", 1.0)\nbuche(1, 2, "BJB", 3)', set()),  # kein Ereigniscode
], ids=["pos_name", "pos_literal", "kw_name", "kw_literal", "kw_ereignis", "attribut",
        "alias", "negativ_andere_art", "negativ_kein_code"])
def test_positivkontrolle_der_scanner_findet_jede_schreibform(quelle, erwartet):
    """Der Scanner der Ratsche ist je Schreibform gemessen: positionell und als
    Schluesselwort, als Konstante, als Literal ``"BJB"``, als Attribut und als
    Alias — und er findet nichts, wo keine Beitragszeile gebucht wird. Ohne diese
    Kontrolle bezeugte 'die Mengen sind gleich' nur die Formen, die er kennt.
    Mutationsprobe: die Keyword-Auswertung aus dem Scanner nehmen -> die
    Schluesselwort-Faelle rot; das Literal nicht erkennen -> die Literal-Faelle
    rot."""
    assert _ereignisse_mit_beitragszeile(quelle) == erwartet


def test_ratsche_die_menge_stimmt_mit_den_buchungsstellen_der_engine_ueberein():
    """Statische Ratsche mit ``==`` ueber das ganze Paket (nicht nur das Modul der
    Engine): Die Ereignisarten, an denen irgendeine Stelle von ``rechner_pipeline``
    die Beitragszeile bucht, sind GENAU ``BEITRAGSEREIGNISSE``. Bucht die Engine
    kuenftig auch bei RED oder PEX einen Beitrag — in welcher Schreibform auch
    immer —, wird dieser Test rot, bis die Menge (Vokabular, Wache, Probe)
    nachgezogen ist. Mutationsprobe: ``BJB`` aus ``BETRAG_ART_JE_EREIGNIS`` fuer
    ERH streichen -> rot; eine dritte ``buche``-Zeile mit ``BJB_BETRAG_ART``,
    ``"BJB"`` oder ``art=...`` in der Engine ergaenzen -> rot."""
    import pathlib

    import rechner_pipeline

    gefunden = set()
    for datei in pathlib.Path(rechner_pipeline.__file__).parent.rglob("*.py"):
        gefunden |= _ereignisse_mit_beitragszeile(datei.read_text(encoding="utf-8"))
    assert gefunden == set(BEITRAGSEREIGNISSE)
    assert _ereignisse_mit_beitragszeile(inspect.getsource(_ereignisse)) == set(BEITRAGSEREIGNISSE)
    assert set(BEITRAGSEREIGNISSE) == {"ZUG", "ERH"}


def test_ratsche_die_betragsart_heisst_ueberall_gleich():
    """Drei Module nennen die Beitragsart; ein Test haelt sie gleich, damit
    die Menge nicht an einem Tippfehler zerfaellt."""
    assert BEITRAG_BETRAG_ART == _ereignisse.BJB_BETRAG_ART == _bindung.BJB_ART == "BJB"


def test_ratsche_die_ausnahme_ist_genau_diese_und_begruendet():
    """``==`` statt ``<=``: Die Ausnahme (kein BJB beim uebernommenen Zugang)
    ist genau diese, eine Teilmenge der Beitragsereignisse, mit Grund.
    Mutationsprobe: einen Eintrag ergaenzen -> rot."""
    assert set(BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN) == {"ZUG"}
    assert set(BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN) <= set(BEITRAGSEREIGNISSE)
    assert all(len(g) > 20 for g in BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN.values())


def test_ratsche_die_regel_nennt_keine_ereignisart_im_klartext():
    """Statische Ratsche: Die Regel laeuft ueber die hergeleitete Menge, nicht
    ueber einen Zweig je Art. Mutationsprobe: ein ``== "ERH"``-Zweig in
    ``beitragspaar_verstoesse`` -> rot."""
    import re

    quelle = inspect.getsource(beitragspaar_verstoesse)
    assert [w for w in EREIGNIS_VALUES if re.search(rf"['\"]{w}['\"]", quelle)] == []
    # Positivkontrolle: derselbe Scanner findet einen solchen Zweig.
    assert re.search(r"['\"]ERH['\"]", 'if art == "ERH":')


def test_ratsche_beide_konsumenten_rufen_die_eine_regel():
    """P-B1 und Probe rufen ``beitragspaar_verstoesse``, keine Abschrift.
    Mutationsprobe: einen der beiden Aufrufe entfernen -> rot."""
    assert "beitragspaar_verstoesse(" in inspect.getsource(validate_ledger)
    assert "beitragspaar_verstoesse(" in inspect.getsource(pruefe_fuehrung)


def test_der_echte_lauf_bucht_je_vorfall_genau_ein_paar(eigen):
    """Die Messung am echten Lauf: Die Ereignisarten mit Beitragszeile sind
    ``BEITRAGSEREIGNISSE``, und je (Police, Tag, Art) steht genau eine
    Summenzeile und genau eine Beitragszeile. Positivkontrolle der Zaehltests
    unten: P-B1 ist auf dem unveraenderten Lauf leer."""
    led = eigen["ledger"]
    mit_bjb = set(led.loc[led["betrag_art"] == BEITRAG_BETRAG_ART, "ereignis"])
    assert mit_bjb == set(BEITRAGSEREIGNISSE)
    for art in BEITRAGSEREIGNISSE:
        je = led[led["ereignis"] == art].assign(
            bjb=lambda d: d["betrag_art"] == BEITRAG_BETRAG_ART).groupby(
            ["police_id", "status_date"])["bjb"].agg(["sum", "size"])
        assert len(je) > 3, f"die Welt traegt zu wenige {art}"
        assert ((je["sum"] == 1) & (je["size"] == 2)).all(), art
    assert _p_b1(eigen, led) == []
    assert beitragspaar_verstoesse(led, eigen["stamm"]) == {}


# --------------------------------------------------------------------------- #
# 2. Zaehltest je Art und Verstoss an P-B1 (validate_ledger)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verstoss", VERSTOESSE)
@pytest.mark.parametrize("art", BEITRAGSEREIGNISSE)
def test_p_b1_meldet_eine_verstuemmelte_beitragszeile_genau_einmal(eigen, art, verstoss):
    """Zaehltest je Art und Verstoss: eine Beitragszeile verdoppelt bzw.
    gestrichen -> GENAU ein Befund, und er nennt die Art. Fuer den Zugang
    meldet die Einmal-Regel der Ausnahme-Ereignisse die Verdopplung schon: Die
    Paarregel scheidet diese Zeile aus (ein Fehler, ein Befund).
    Mutationsprobe: ``beitragspaar_verstoesse`` aus validate_ledger entfernen
    -> beide ERH-Faelle und der ZUG-Fall 'fehlt' rot; ``schon_gemeldet``
    nicht weitergeben -> ZUG 'doppelt' zeigt zwei Befunde."""
    led = eigen["ledger"]
    i = _zeile_der_art(led, art, BEITRAG_BETRAG_ART)
    ledger = _verdoppelt(led, i) if verstoss == "doppelt" else _gestrichen(led, i)
    fehler = _p_b1(eigen, ledger)
    assert len(fehler) == 1, fehler
    assert fehler[0].startswith(f"ledger: {art}-Buchung"), fehler


@pytest.mark.parametrize("art", BEITRAGSEREIGNISSE)
def test_p_b1_meldet_eine_beitragszeile_ohne_summenzeile(eigen, art):
    """Die Gegenrichtung der Paarung: Die Summenzeile des Vorfalls fehlt, die
    Beitragszeile steht allein. Mutationsprobe: ``summe_fehlt`` aus
    ``beitragspaar_verstoesse`` streichen -> rot."""
    led = eigen["ledger"]
    ledger = _gestrichen(led, _zeile_der_art(led, art, None, summe=True))
    fehler = _p_b1(eigen, ledger)
    assert sum("mit Beitragszeile (BJB) ohne Summenzeile" in f for f in fehler) == 1, fehler


def test_p_b1_meldet_eine_doppelte_summenzeile_der_erhoehung_auch_ohne_scheiben(eigen):
    """Ohne Scheiben band bisher nichts die Summenzeile der Erhoehung; die
    Paarregel zaehlt sie. Mutationsprobe: ``summe_zuviel`` streichen -> rot."""
    led = eigen["ledger"]
    ledger = _verdoppelt(led, _zeile_der_art(led, "ERH", "VS_erhoehung"))
    assert _p_b1(eigen, led, scheiben=False) == []                  # Positivkontrolle
    fehler = _p_b1(eigen, ledger, scheiben=False)
    assert len(fehler) == 1 and "mehr als einer Summenzeile" in fehler[0], fehler


def _hand(stamm, art, betrag_art, datum, jahr, herkunft):
    return {"police_id": 900_001, "tarif_generation": "TG2015", "ereignis": art,
            "vertragsjahr": jahr, "status_date": pd.Timestamp(datum),
            "betrag_art": betrag_art, "betrag": 100.0, "betrag_herkunft": herkunft}


def _tabelle(zeilen):
    return pd.DataFrame(zeilen)[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))


def test_der_zugang_eines_uebernommenen_vertrags_bucht_keine_beitragszeile():
    """Die benannte Ausnahme in BEIDE Richtungen: Der Zugang eines
    uebernommenen Vertrags ohne Beitragszeile ist gruen, MIT Beitragszeile ein
    Befund; beim eigenen Geschaeft ist es umgekehrt. Mutationsprobe:
    ``BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN`` leeren -> der erste Fall rot; die
    Ausnahme auf alle Vertraege ausdehnen -> der letzte Fall rot."""
    uebernommen = _stamm_eigen()
    uebernommen["bestandszugang"] = pd.Timestamp("2026-01-01")
    eigenes = _stamm_eigen()
    zug_u = _hand(uebernommen, "ZUG", "VS", "2026-01-01", 11, "geliefert")
    # 'geliefert' wie die Summenzeile: Die Herkunftsregel trifft sonst schon die
    # Beitragszeile, und der Test zaehlte zwei Befunde fuer zwei Fehler.
    bjb_u = _hand(uebernommen, "ZUG", "BJB", "2026-01-01", 11, "geliefert")
    assert validate_ledger(uebernommen, _tabelle([zug_u])) == []
    fehler = validate_ledger(uebernommen, _tabelle([zug_u, bjb_u]))
    assert len(fehler) == 1 and "uebernommenen Vertrag" in fehler[0], fehler
    zug_e = _hand(eigenes, "ZUG", "VS", "2015-01-01", 0, "gerechnet")
    bjb_e = _hand(eigenes, "ZUG", "BJB", "2015-01-01", 0, "gerechnet")
    assert validate_ledger(eigenes, _tabelle([zug_e, bjb_e])) == []
    fehler = validate_ledger(eigenes, _tabelle([zug_e]))
    assert len(fehler) == 1 and "ohne die Beitragszeile" in fehler[0], fehler


def test_der_befund_nennt_policen_und_ausweg():
    """Der Text ist die Meldung des Gates: Art, Verstoss, Police, Ausweg."""
    eigenes = _stamm_eigen()
    zug = _hand(eigenes, "ZUG", "VS", "2015-01-01", 0, "gerechnet")
    (text,) = validate_ledger(eigenes, _tabelle([zug]))
    assert "police [900001]" in text and "Ausweg" in text and "Paar" in text


# --------------------------------------------------------------------------- #
# 3. Zaehltest an der Fuehrungsprobe
# --------------------------------------------------------------------------- #


def _paar_in(welt, *, bjb_zeilen: int, summe_zeilen: int = 1):
    """Die Fortschreibung der Welt mit EINER Erhoehung der Police POL zum
    Jahrestag des Jahres 12 — ``summe_zeilen`` Summenzeilen und ``bjb_zeilen``
    Beitragszeilen, sonst nichts."""
    tab = dict(welt["tab"])
    stamm = welt["ueb"]["bestand"]
    gen = stamm[stamm["police_id"] == POL].iloc[0]["tarif_generation"]
    zeilen = [{"police_id": POL, "tarif_generation": gen, "ereignis": "ERH",
               "vertragsjahr": 12, "status_date": HORIZONT, "betrag_art": art,
               "betrag": 1.0, "betrag_herkunft": "gerechnet"}
              for art in ["VS_erhoehung"] * summe_zeilen + [BEITRAG_BETRAG_ART] * bjb_zeilen]
    tab["ledger"] = pd.concat([tab["ledger"], _tabelle(zeilen)], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    return tab


def _paar_befunde(urteil):
    return [b for b in urteil["befunde"] if b["art"] == "beitragspaar"]


def test_positivkontrolle_die_welt_und_ein_vollstaendiges_paar_bleiben_gruen(welt):
    """Die Welt bucht den uebernommenen Zugang ohne Beitragszeile — kein Befund.
    Ein vollstaendiges Erhoehungspaar ebenso (die uebrigen Regeln der Probe, etwa
    die Scheibe, melden andere Befunde und gehoeren nicht hierher)."""
    assert _paar_befunde(_urteil(welt, welt["tab"])) == []
    assert _paar_befunde(_urteil(welt, _paar_in(welt, bjb_zeilen=1))) == []


@pytest.mark.parametrize("verstoss", VERSTOESSE)
@pytest.mark.parametrize("art", BEITRAGSEREIGNISSE)
def test_die_probe_meldet_eine_verstuemmelte_beitragszeile_genau_einmal(welt, art, verstoss):
    """Zaehltest je Art und Verstoss an der Probe. ERH: Beitragszeile
    verdoppelt bzw. fehlend; ZUG: der uebernommene Zugang traegt keine
    Beitragszeile, eine eingelegte ist der Verstoss ('doppelt'), die fehlende ist
    die Regel (kein Befund). Mutationsprobe: den Aufruf von
    ``beitragspaar_verstoesse`` in ``pruefe_fuehrung`` entfernen -> rot."""
    if art == "ERH":
        tab = _paar_in(welt, bjb_zeilen=2 if verstoss == "doppelt" else 0)
    else:
        assert art == "ZUG"
        tab = dict(welt["tab"])
        ledger = tab["ledger"]
        zug = ledger[(ledger["police_id"] == POL) & (ledger["ereignis"] == "ZUG")]
        assert len(zug) == 1
        bjb = zug.assign(betrag_art=BEITRAG_BETRAG_ART, betrag_herkunft="gerechnet")
        tab["ledger"] = pd.concat([ledger, bjb] if verstoss == "doppelt" else [ledger],
                                  ignore_index=True)
    befunde = _paar_befunde(_urteil(welt, tab))
    if art == "ZUG" and verstoss == "fehlt":
        assert befunde == []                          # die benannte Ausnahme
        return
    assert len(befunde) == 1, [b["text"] for b in befunde]
    assert befunde[0]["text"].startswith(f"{art}-Buchung") and befunde[0]["ereignis"] == art


def test_die_probe_meldet_eine_beitragszeile_ohne_summenzeile(welt):
    """Mutationsprobe: ``summe_fehlt`` aus ``beitragspaar_verstoesse`` -> rot."""
    befunde = _paar_befunde(_urteil(welt, _paar_in(welt, bjb_zeilen=1, summe_zeilen=0)))
    assert len(befunde) == 1 and "ohne Summenzeile" in befunde[0]["text"]


# --------------------------------------------------------------------------- #
# 4. Der Bericht rendert keinen Lauf mit verstuemmelter Beitragszeile
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("verstoss", VERSTOESSE)
def test_der_bericht_rendert_keine_verstuemmelte_beitragszeile(tmp_path, verstoss):
    """Der Weg der Gutachter: eine Ledgerzeile (ERH, BJB) verdoppelt bzw.
    gestrichen, Laufmanifest stimmig nachgefuehrt. P-B1 und Bericht weisen
    ab (die Anzahl und die Summe der Beitragszeilen waeren falsch);
    Positivkontrolle: der unveraenderte Lauf rendert. Mutationsprobe: die
    Paarregel aus validate_ledger entfernen -> rot."""
    from rechner_pipeline.bestand import cli_report as _bericht
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from tests.test_t27_runde_d_bestand import (
        _bericht_argv,
        _lauf,
        _manifest_nachfuehren,
        _pb1_fehler,
    )

    out, cfg = _lauf(tmp_path, "2030-01-01")
    assert _pb1_fehler(out, cfg, _dt.date(2030, 1, 1)) == []
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", tmp_path / "ok.html")) == 0
    led = read_portfolio(out / "ledger.parquet")
    i = _zeile_der_art(led, "ERH", BEITRAG_BETRAG_ART)
    neu = _verdoppelt(led, i) if verstoss == "doppelt" else _gestrichen(led, i)
    write_portfolio(neu.astype(led.dtypes.to_dict()), out / "ledger.parquet")
    _manifest_nachfuehren(out, cfg)
    fehler = [f["message"] for f in _pb1_fehler(out, cfg, _dt.date(2030, 1, 1))]
    assert len(fehler) == 1 and fehler[0].startswith("ledger: ERH-Buchung"), fehler
    ziel = tmp_path / "x.html"
    assert _bericht.main(_bericht_argv(out, cfg, "2030-01-01", ziel)) != 0
    assert not ziel.exists()


# --------------------------------------------------------------------------- #
# 5. Die Welt der Probe bucht den uebernommenen Zugang ohne Beitragszeile
# --------------------------------------------------------------------------- #


def test_der_echte_migrationszugang_bucht_keine_beitragszeile(welt):
    """Die Ausnahme ist gemessen, nicht angenommen: Im gefahrenen Baldrian-Lauf
    traegt der Ledger der Uebernahme je uebernommenem Vertrag genau eine
    ZUG-Summenzeile und keine Beitragszeile (``gates.bestand_uebernehmen``).
    Mutationsprobe: in der Uebernahme eine BJB-Zeile mitbuchen -> rot."""
    led = welt["ueb"]["ledger"]
    zug = led[led["ereignis"] == "ZUG"]
    assert len(zug) > 3 and set(zug["betrag_art"]) == {"VS"}
    assert BEITRAG_BETRAG_ART not in set(led["betrag_art"])
    assert set(EREIGNIS_VALUES) >= set(BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN)
    assert _modell.BETRAG_ART_JE_EREIGNIS["ZUG"][-1] == BEITRAG_BETRAG_ART


# --------------------------------------------------------------------------- #
# 6. Nachbesserung Runde F: eine gemeldete Zeile, ein Befund — ein Vorfall, ein Befund
# --------------------------------------------------------------------------- #


def _erh_paar(stamm, *, jahr: int = 5, tag: str = "2020-01-01"):
    """Ein vollstaendiges Erhoehungspaar der Police 900001 (Summe + Beitrag)."""
    return _tabelle([
        _hand(stamm, "ERH", "VS_erhoehung", tag, jahr, "gerechnet"),
        _hand(stamm, "ERH", "BJB", tag, jahr, "gerechnet")])


def test_die_paarregel_nimmt_den_ganzen_vorfall_aus_wenn_eine_zeile_gemeldet_ist():
    """Einheit: Meldet eine andere Regel die Beitragszeile eines Paars, bringt
    die Partnerzeile (die Summenzeile am richtigen Tag) keinen zusaetzlichen
    Befund 'Beitragszeile fehlt' — ein Vorfall, ein Fehler. Positivkontrolle:
    dieselbe Beitragszeile fehlt ohne Meldung -> ``bjb_fehlt``; die Meldung der
    SUMMENzeile nimmt umgekehrt die Beitragszeile aus. Mutationsprobe: nur die
    gemeldete Zeile statt des Vorfalls ausnehmen -> rot."""
    stamm = _stamm_eigen()
    paar = _erh_paar(stamm)
    assert beitragspaar_verstoesse(paar, stamm) == {}
    ohne_bjb = paar.iloc[[0]].reset_index(drop=True)
    assert beitragspaar_verstoesse(ohne_bjb, stamm) == {("ERH", "bjb_fehlt"): [900_001]}
    assert beitragspaar_verstoesse(paar, stamm, [False, True]) == {}
    assert beitragspaar_verstoesse(paar, stamm, [True, False]) == {}
    # eine gemeldete Zeile eines ANDEREN Vorfalls (anderes Vertragsjahr) nimmt nichts aus
    zwei = pd.concat([paar, _erh_paar(stamm, jahr=6, tag="2021-01-01").iloc[[0]]],
                     ignore_index=True)
    assert beitragspaar_verstoesse(zwei, stamm, [True, False, False]) == {
        ("ERH", "bjb_fehlt"): [900_001]}


def test_die_paarregel_meldet_ein_in_der_zeit_getrenntes_paar_als_einen_vorfall():
    """Teilverschiebung (Einheit): Summen- und Beitragszeile desselben
    Vertragsjahres stehen auf verschiedenen Tagen -> EIN Befund fuer den ganzen
    Vorfall, nicht 'Beitragszeile fehlt' UND 'Summenzeile fehlt' (zwei fuer
    einen Fehler). Das Paar in zwei VERSCHIEDENEN Vertragsjahren sind zwei
    unvollstaendige Vorfaelle und bleiben zwei Befunde. Mutationsprobe: den
    Vorfall nach dem Tag statt nach dem Vertragsjahr schluesseln -> rot; die
    Anzahlregeln fuer den getrennten Vorfall nicht ausnehmen -> rot."""
    stamm = _stamm_eigen()
    paar = _erh_paar(stamm)
    getrennt = paar.assign(status_date=[pd.Timestamp("2020-01-01"), pd.Timestamp("2020-03-01")])
    assert beitragspaar_verstoesse(getrennt, stamm) == {("ERH", PAAR_TAG_VERSCHOBEN): [900_001]}
    # Auch ein zugleich falsch gezaehlter Vorfall ist EIN Befund: zwei
    # Summenzeilen auf zwei Tagen, keine Beitragszeile.
    zwei_summen = pd.concat([paar.iloc[[0]], paar.iloc[[0]].assign(
        status_date=pd.Timestamp("2020-03-01"))], ignore_index=True)
    assert beitragspaar_verstoesse(zwei_summen, stamm) == {("ERH", PAAR_TAG_VERSCHOBEN): [900_001]}
    spaeter = pd.Timestamp("2020-03-01")
    zwei_beitraege = pd.concat([paar.iloc[[1]], paar.iloc[[1]].assign(status_date=spaeter)],
                               ignore_index=True)
    assert beitragspaar_verstoesse(zwei_beitraege, stamm) == {
        ("ERH", PAAR_TAG_VERSCHOBEN): [900_001]}
    paar_und_beitrag = pd.concat([paar, paar.iloc[[1]].assign(status_date=spaeter)],
                                 ignore_index=True)
    assert beitragspaar_verstoesse(paar_und_beitrag, stamm) == {
        ("ERH", PAAR_TAG_VERSCHOBEN): [900_001]}
    # Positivkontrolle: dasselbe Paar am selben Tag ist leer (oben), und ein
    # ZWEITES Vertragsjahr mit eigenem Paar stoert den Vorfall nicht.
    beide = pd.concat([paar, _erh_paar(stamm, jahr=6, tag="2021-01-01")], ignore_index=True)
    assert beitragspaar_verstoesse(beide, stamm) == {}
    zwei_jahre = pd.concat([
        paar.iloc[[0]], paar.iloc[[1]].assign(
            vertragsjahr=6, status_date=pd.Timestamp("2021-01-01"))], ignore_index=True)
    assert beitragspaar_verstoesse(zwei_jahre, stamm) == {
        ("ERH", "bjb_fehlt"): [900_001], ("ERH", "summe_fehlt"): [900_001]}


@pytest.mark.parametrize("fall,zeile", [
    # (Name, (Art, Betragsart, Datum, Vertragsjahr)) — die eingelegte Zeile steht
    # allein; ohne Meldung der anderen Regel brachte sie einen Paar-Befund.
    ("fenster_vor_zugang", ("ERH", "VS_erhoehung", "2025-03-01", 10)),
    ("fenster_hinter_horizont", ("ERH", "VS_erhoehung", "2028-01-01", 13)),
    ("ausnahme_zugang_am_falschen_tag", ("ZUG", "BJB", "2026-03-01", 11)),
])
def test_die_probe_bringt_fuer_eine_schon_gemeldete_zeile_keinen_paar_befund(welt, fall, zeile):
    """Zaehltest: Eine Zeile, die das Buchungsfenster oder eine Ausnahmeregel
    schon melden, bringt GENAU einen Befund dieser Regel und keinen
    zusaetzlichen 'beitragspaar'-Befund (ein Fehler, ein Befund).
    Positivkontrolle: dieselbe Zeile ohne Fenster und Ausnahme (die Paarbuchung
    selbst: eine Summenzeile am Jahrestag ohne Beitragszeile) meldet das Paar.
    Mutationsprobe: ``gemeldet`` in ``pruefe_fuehrung`` nicht an die Paarregel
    geben -> alle drei Faelle rot."""
    art, betrag_art, tag, jahr = zeile
    tab = dict(welt["tab"])
    stamm = welt["ueb"]["bestand"]
    gen = stamm[stamm["police_id"] == POL].iloc[0]["tarif_generation"]
    zeilen = _tabelle([{"police_id": POL, "tarif_generation": gen, "ereignis": art,
                        "vertragsjahr": jahr, "status_date": pd.Timestamp(tag),
                        "betrag_art": betrag_art, "betrag": 1.0, "betrag_herkunft": "gerechnet"}])
    tab["ledger"] = pd.concat([tab["ledger"], zeilen], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True)
    urteil = _urteil(welt, tab)
    regel = [b for b in urteil["befunde"]
             if b["art"] in ("buchungsfenster", "ausnahme_ereignis")
             and b["text"].startswith(f"{art}-Buchung")]
    assert len(regel) == 1, [(b["art"], b["text"][:70]) for b in urteil["befunde"]]
    assert _paar_befunde(urteil) == []
    # Positivkontrolle: dieselbe Zeile, am Jahrestag im Lauf, ist die Paarbuchung allein.
    kontrolle = _urteil(welt, _paar_in(welt, bjb_zeilen=0))
    assert len(_paar_befunde(kontrolle)) == 1


def test_die_probe_meldet_ein_in_der_zeit_getrenntes_paar_als_einen_befund(welt):
    """Teilverschiebung in der Probe (Pruefer-Befund): Die Beitragszeile einer
    Erhoehung steht zwei Monate neben dem Jahrestag, die Summenzeile am
    Jahrestag. Die Zeile am falschen Tag meldet der Wirkungstag-Befund; die
    Partnerzeile und die verschobene Zeile bringen keinen 'beitragspaar'-Befund
    (vorher drei Befunde fuer einen Fehler). Positivkontrolle: das Paar am
    Jahrestag ist leer. Mutationsprobe: ``falscher_tag`` nicht an die Paarregel
    geben -> rot."""
    from tests.test_klasse_probe_betrag_wirkungstag_f import NEBEN_DEM_JAHRESTAG

    assert _paar_befunde(_urteil(welt, _paar_in(welt, bjb_zeilen=1))) == []
    tab = _paar_in(welt, bjb_zeilen=1)
    led = tab["ledger"].copy()
    bjb = (led["police_id"] == POL) & (led["betrag_art"] == BEITRAG_BETRAG_ART) \
        & (led["ereignis"] == "ERH")
    assert bjb.sum() == 1
    led.loc[bjb, "status_date"] = NEBEN_DEM_JAHRESTAG
    urteil = _urteil(welt, dict(tab, ledger=led))
    assert [b["art"] for b in urteil["befunde"] if b["art"] in ("wirkungstag", "beitragspaar")] \
        == ["wirkungstag"], [(b["art"], b["text"][:70]) for b in urteil["befunde"]]


def test_p_b1_meldet_ein_in_der_zeit_getrenntes_paar_als_einen_befund(eigen):
    """Dasselbe an P-B1 auf dem echten Lauf: Die Beitragszeile einer Erhoehung
    steht einen Monat nach ihrer Summenzeile im selben Vertragsjahr -> GENAU ein
    Befund, und er nennt den Vorfall. Positivkontrolle: der unveraenderte Lauf
    ist leer. Mutationsprobe: ``tag_verschoben`` streichen -> zwei Befunde
    (Beitragszeile fehlt, Summenzeile fehlt), rot."""
    led = eigen["ledger"].copy()
    assert _p_b1(eigen, led, scheiben=False) == []
    i = _zeile_der_art(led, "ERH", BEITRAG_BETRAG_ART)
    led.loc[i, "status_date"] = led.loc[i, "status_date"] + pd.DateOffset(months=1)
    fehler = _p_b1(eigen, led, scheiben=False)
    assert len(fehler) == 1, fehler
    assert fehler[0].startswith("ledger: ERH-Buchung") and "verschiedenen Tagen" in fehler[0]


def test_p_b1_bringt_fuer_eine_schon_gemeldete_zeile_keinen_paar_befund():
    """Zaehltest an P-B1: Der Zugang eines uebernommenen Vertrags steht nicht am
    Zugangstag (Ausnahmeregel) und traegt eine Beitragszeile, die er nicht
    traegt — die Paarregel meldet die Zeile nicht ein zweites Mal. Mutationsprobe:
    ``gemeldet`` in ``validate_ledger`` nicht an die Paarregel geben -> rot."""
    uebernommen = _stamm_eigen()
    uebernommen["bestandszugang"] = pd.Timestamp("2026-01-01")
    zug = _hand(uebernommen, "ZUG", "VS", "2026-01-01", 11, "geliefert")
    bjb = _hand(uebernommen, "ZUG", "BJB", "2026-03-01", 11, "geliefert")
    fehler = validate_ledger(uebernommen, _tabelle([zug, bjb]))
    assert not [f for f in fehler if "Paar aus Summenzeile und Beitragszeile" in f], fehler
    assert len([f for f in fehler if "ZUG-Buchung" in f]) == 1, fehler
