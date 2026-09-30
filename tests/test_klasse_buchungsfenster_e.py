"""Klasse: Buchungsfenster, fuer JEDE Ereignisart — Runde E.

Die Invariante: Jede Fortschreibungsbuchung eines Vertrags liegt echt NACH
seinem Bestandszugang (Datum gleich Zugang ist unzulaessig) und nicht hinter
dem im Laufmanifest belegten Horizont — fuer jede Ereignisart des Ledgers.
Runde C (RC02) hat die Wache fuer ``RED`` gebaut; ``STO``, ``TOD``, ``ABL``,
``ERH`` und ``PEX`` vor dem Zugang oder hinter dem Horizont gingen durch
``validate_ledger`` und die Fuehrungsprobe ohne Befund, obwohl der Lauf sie
nicht gefahren haben kann (die Engine simuliert einen uebernommenen Vertrag
erst ab seinem Zugangsjahr und nie ueber den Horizont).

Die Menge ist das Ledger-Vokabular ``EREIGNIS_VALUES``. Die Ausnahmen stehen
als Mengen im Code, mit Grund: ``ZUGANGSTAG_EREIGNISSE`` (Zugangsbuchung,
Migrations-Residuum, Umbuchung eines beitragsfrei uebernommenen Vertrags am
Zugangstag) und ``ZUGANG_HINTER_HORIZONT`` (Neugeschaeft mit Beginn nach dem
Laufdatum). Die gelieferte Vorgeschichte steht in der Historie, nicht im
Ledger — eine Ledgerzeile davor hat keine Ausnahme.

Nachbesserung (Pruefer-Befunde 1 und 2): Die Ausnahme-Ereignisse ZUG, MIG und
ABL waren an keinen Zeitpunkt gebunden, und der Zugang hinter dem Horizont war
nach oben offen. Aus jedem Grund wird eine Regel
(``ausnahme_ereignis_verstoesse``; ZUG genau einmal und am Zugangstag, MIG am
Zugangstag und nur bei uebernommenen Vertraegen, ABL am Vertragsende), der
Zugang hinter dem Horizont endet am Monatsersten nach dem Horizont; Zaehltest
je Art am echten Lauf, Mutation je Regel.

Drei Instrumente: Ratsche (statisch, ``==``, mit Positivkontrolle), Zaehltest
(je Ereignisart gemessen, parametrisiert ueber ``EREIGNIS_VALUES``) und die
Mutationsprobe je Ereignisart in den Docstrings. Die Fuehrungsprobe hat ihren
Zaehltest in ``test_klasse_probe_e``.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import inspect
import re
import shutil

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.models.bestand import (
    AUSNAHME_EINMAL_JE_POLICE,
    AUSNAHME_NUR_UEBERNOMMEN,
    AUSNAHME_ZEITPUNKT,
    BETRAG_ART_JE_EREIGNIS,
    EREIGNIS_OHNE_ANNAHME,
    EREIGNIS_VALUES,
    LEDGER_NAMES,
    LEDGER_SPALTEN,
    ZUGANG_HINTER_HORIZONT,
    ZUGANGSTAG_EREIGNISSE,
    ZUGANGSTAG_NUR_UEBERNOMMEN,
    ausnahme_ereignis_verstoesse,
    buchungsfenster_verstoesse,
    validate_ledger,
)
from tests.test_reduktionen_vertrag import _stamm as _stamm_eigen

BEGINN = pd.Timestamp("2015-01-01")
ZUGANG = pd.Timestamp("2026-01-01")
VOR = pd.Timestamp("2025-01-01")
INNEN = pd.Timestamp("2027-01-01")
HORIZONT = _dt.date(2028, 1, 1)
DAHINTER = pd.Timestamp("2029-01-01")

#: Die Erwartung, von Hand und unabhaengig von den Mengen im Code: Was am
#: Zugangstag eines UEBERNOMMENEN Vertrags stehen darf.
AM_ZUGANGSTAG_ERLAUBT = {"ZUG", "MIG", "PEX"}


def _uebernommen(zugang: pd.Timestamp = ZUGANG):
    stamm = _stamm_eigen()
    stamm["bestandszugang"] = zugang
    return stamm


def _zeile(art: str, datum: pd.Timestamp, *, uebernommen: bool = True) -> pd.DataFrame:
    """Eine formal gueltige Buchung der Art am ``datum`` — nur der ORT ist der
    Fehler. Der Zugang eines uebernommenen Vertrags traegt 'geliefert'."""
    jahr = ((datum.year * 12 + datum.month) - (BEGINN.year * 12 + BEGINN.month)) // 12
    herkunft = "geliefert" if (art == "ZUG" and uebernommen) else "gerechnet"
    return pd.DataFrame([{
        "police_id": 900_001, "tarif_generation": "TG2015", "ereignis": art,
        "vertragsjahr": jahr, "status_date": datum,
        "betrag_art": BETRAG_ART_JE_EREIGNIS[art][0], "betrag": 100.0,
        "betrag_herkunft": herkunft,
    }])[list(LEDGER_NAMES)].astype(dict(LEDGER_SPALTEN))


def _fall_am(art: str, datum: pd.Timestamp):
    """(Stamm, Buchung): Die Art steht am ``datum`` an IHREM Platz — Runde E,
    Nachbesserung. ZUG und MIG stehen am Zugangstag (der Stamm bekommt ihn),
    ein Ablauf am Vertragsende (der Stamm bekommt sein Ende und seine Dauer);
    jede andere Art steht an irgendeinem Tag im Lauf, der Stamm bleibt."""
    stamm = _uebernommen()
    if art in ("ZUG", "MIG"):
        stamm = _uebernommen(datum)
    elif art == "ABL":
        jahre = datum.year - BEGINN.year
        stamm["insurance_end"] = datum
        stamm["duration"] = jahre
        stamm["premium_duration"] = min(int(stamm["premium_duration"].iloc[0]), jahre)
    return stamm, _zeile(art, datum)


def _fenster(fehler):
    return [f for f in fehler if "Bestandszugang" in f or "Horizont" in f]


# --------------------------------------------------------------------------- #
# 1. Ratsche (statisch)
# --------------------------------------------------------------------------- #


def _sonderwege(quelle: str):
    """Ereigniscodes des Ledger-Vokabulars im Klartext einer Quelle — ein
    Zweig je Art ist der Sonderweg, der beim naechsten neuen Code fehlt."""
    return sorted(w for w in EREIGNIS_VALUES if re.search(rf"['\"]{w}['\"]", quelle))


def test_ratsche_die_regel_laeuft_ueber_die_mengen_und_nicht_ueber_zweige_je_art():
    """Statische Ratsche. Die Funktion nennt keine Ereignisart im Klartext:
    Fuer JEDE Art des Vokabulars gilt dieselbe Regel, die Ausnahmen kommen
    aus den benannten Mengen. Mutationsprobe: ein ``art == "RED"``-Zweig in
    buchungsfenster_verstoesse -> rot."""
    assert _sonderwege(inspect.getsource(buchungsfenster_verstoesse)) == []
    # Positivkontrolle: derselbe Scanner findet den alten RED-Block.
    assert _sonderwege('rot = (ledger["ereignis"] == "RED").to_numpy()') == ["RED"]


def test_ratsche_die_ausnahmen_sind_genau_diese_und_begruendet():
    """``==`` statt ``<=``: Die Ausnahmemengen sind genau die hier genannten —
    ein neuer Eintrag ist eine Entscheidung und braucht diesen Test.
    Mutationsprobe: ein Ereignis in ZUGANGSTAG_EREIGNISSE ergaenzen oder
    streichen -> rot."""
    assert set(ZUGANGSTAG_EREIGNISSE) == AM_ZUGANGSTAG_ERLAUBT
    assert set(ZUGANG_HINTER_HORIZONT) == {"ZUG"}
    assert set(ZUGANGSTAG_NUR_UEBERNOMMEN) == {"PEX"}
    assert set(ZUGANGSTAG_NUR_UEBERNOMMEN) <= set(ZUGANGSTAG_EREIGNISSE)
    for menge in (ZUGANGSTAG_EREIGNISSE, ZUGANG_HINTER_HORIZONT):
        assert set(menge) <= set(EREIGNIS_VALUES)
        assert all(isinstance(g, str) and len(g) > 10 for g in menge.values())


def test_ratsche_beide_konsumenten_rufen_die_eine_regel():
    """Statisch: P-B1 (``validate_ledger``) und die Fuehrungsprobe rufen
    dieselbe Funktion; ein Konsument mit eigener Abschrift laeuft auseinander
    (die Probe trug nur den RED-Block)."""
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    assert "buchungsfenster_verstoesse(" in inspect.getsource(validate_ledger)
    assert "buchungsfenster_verstoesse(" in inspect.getsource(pruefe_fuehrung)


# --------------------------------------------------------------------------- #
# 2. Zaehltest: je Ereignisart des Vokabulars
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_positivkontrolle_im_fenster_ist_jede_art_gruen(art):
    """Die unveraenderte Welt: dieselbe Buchung ein Jahr NACH dem Zugang und
    vor dem Horizont ist formal gueltig — ohne diese Kontrolle waere ein
    Test, der nie anschlaegt, von einem, der nichts sieht, nicht zu
    unterscheiden. ZUG, MIG und ABL stehen dabei an ihrem Platz (Zugangstag,
    Vertragsende, ``_fall_am``): ausserhalb davon gelten sie als unbelegt."""
    stamm, zeile = _fall_am(art, INNEN)
    assert validate_ledger(stamm, zeile, horizont=HORIZONT) == []
    assert validate_ledger(stamm, zeile) == []


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_eine_buchung_vor_dem_zugang_weist_validate_ledger_ab(art):
    """Zaehltest je Art (auch der Zugang selbst, als 'geliefert': die
    Vorgeschichte steht in der Historie, nicht im Ledger). Genau ein Befund,
    genau diese Art. Mutationsprobe: die Untergrenze fuer genau diese Art
    in buchungsfenster_verstoesse ausnehmen -> genau dieser Fall rot."""
    fehler = validate_ledger(_uebernommen(), _zeile(art, VOR))
    assert len(fehler) == 1, fehler
    assert fehler[0].startswith(f"ledger: {art}-Buchung nicht nach dem Bestandszugang"), fehler


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_am_zugangstag_stehen_nur_die_zugangsbuchungen(art):
    """Die Grenze ist scharf (Datum gleich Zugang ist unzulaessig) — bis auf
    die benannten Zugangsbuchungen, deren Erwartung HIER von Hand steht und
    nicht aus der Menge im Code gelesen wird. Mutationsprobe: ``<`` statt
    ``<=`` in der Regel (Grenze aufweichen) -> alle nicht erlaubten Arten rot;
    ein Ereignis aus ZUGANGSTAG_EREIGNISSE streichen -> genau dieses rot."""
    fehler = validate_ledger(_uebernommen(), _zeile(art, ZUGANG))
    if art in AM_ZUGANGSTAG_ERLAUBT:
        assert fehler == [], fehler
    else:
        assert len(fehler) == 1, fehler
        assert fehler[0].startswith(f"ledger: {art}-Buchung nicht nach dem Bestandszugang"), fehler


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_eine_buchung_hinter_dem_belegten_horizont_weist_validate_ledger_ab(art):
    """Zaehltest je Art. Ohne belegten Horizont gibt es keine Obergrenze
    (Positivkontrolle). Mutationsprobe: die Obergrenze fuer genau diese Art
    ausnehmen -> genau dieser Fall rot."""
    stamm, zeile = _fall_am(art, DAHINTER)       # die Art an IHREM Platz, hinter dem Horizont
    fehler = validate_ledger(stamm, zeile, horizont=HORIZONT)
    assert len(fehler) == 1, fehler
    assert fehler[0].startswith(f"ledger: {art}-Buchung nach dem belegten Horizont 2028-01-01"), fehler
    assert validate_ledger(stamm, zeile) == []


#: Der Horizont des Tests und der Monatserste NACH ihm: bis dahin darf ein
#: Neugeschaeft beginnen (Antrag am Laufdatum, Beginn am naechsten Monatsersten),
#: von Hand hier, nicht aus der Regel gelesen.
FRUEH = _dt.date(2025, 6, 15)
GRENZE = pd.Timestamp("2025-07-01")


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_hinter_dem_horizont_ist_nur_der_zugang_am_zugangstag_erlaubt(art):
    """Der Horizont liegt VOR dem Zugang (Neugeschaeft mit Beginn nach dem
    Laufdatum): Am Zugangstag darf der Zugang stehen, jede andere Art nicht —
    und der Zugang an einem anderen Tag hinter dem Horizont ebenso nicht.
    Positivkontrolle: der Zugang am Monatsersten nach dem Horizont
    (Nachbesserung Runde E, Befund 2: die Ausnahme ist nicht mehr nach oben
    offen, s. ``test_der_zugang_hinter_dem_horizont_endet_am_naechsten_monatsersten``).
    Mutationsprobe: ``ZUG`` aus ZUGANG_HINTER_HORIZONT streichen -> rot."""
    stamm = _uebernommen(GRENZE)
    fehler = [f for f in validate_ledger(stamm, _zeile(art, GRENZE), horizont=FRUEH)
              if "Horizont" in f]
    if art == "ZUG":
        assert fehler == []
        spaeter = [f for f in validate_ledger(_uebernommen(), _zeile(art, INNEN), horizont=FRUEH)
                   if "Horizont" in f]
        assert len(spaeter) == 1
    else:
        assert len(fehler) == 1, fehler


@pytest.mark.parametrize("horizont,grenze", [
    (_dt.date(2025, 6, 15), "2025-07-01"),      # mitten im Monat
    (_dt.date(2025, 6, 30), "2025-07-01"),      # Ultimo
    (_dt.date(2025, 6, 1), "2025-07-01"),       # Monatserster: Beginn erst NACH dem Verkaufstag
    (_dt.date(2025, 12, 31), "2026-01-01"),     # Jahreswechsel
])
def test_der_zugang_hinter_dem_horizont_endet_am_naechsten_monatsersten(horizont, grenze):
    """Runde E, Nachbesserung (Befund 2): Die Ausnahme ``ZUG_HINTER_HORIZONT``
    ist auf den gemessenen Bereich begrenzt — ein Zugang hinter dem Horizont
    steht hoechstens am ersten Monatsersten STRENG NACH ihm (so beginnt ein am
    Laufdatum verkaufter Vertrag). Zaehltest: am Monatsersten nach dem Horizont
    gruen, einen Tag dahinter und einen Monat dahinter je genau ein Befund.
    Die Erwartung der Grenze steht hier von Hand je Fall.
    Mutationsprobe: die Schranke ``datum <= grenze`` in
    buchungsfenster_verstoesse streichen (Ausnahme wieder offen) -> rot."""
    g = pd.Timestamp(grenze)
    gruen = validate_ledger(_uebernommen(g), _zeile("ZUG", g), horizont=horizont)
    assert [f for f in gruen if "Horizont" in f] == [], gruen
    for dahinter in (g + pd.Timedelta(days=1), g + pd.DateOffset(months=1)):
        fehler = [f for f in validate_ledger(_uebernommen(dahinter), _zeile("ZUG", dahinter),
                                             horizont=horizont) if "Horizont" in f]
        assert len(fehler) == 1, (dahinter, fehler)
        assert fehler[0].startswith("ledger: ZUG-Buchung nach dem belegten Horizont"), fehler


def test_der_pex_umbuchung_am_zugangstag_braucht_einen_uebernommenen_vertrag():
    """Beim eigenen Geschaeft (Zugang = Beginn) gibt es keinen mitgebrachten
    Zustand: PEX am Beginn ist kein Zugang. Positivkontrolle: derselbe Tag mit
    ZUG ist gruen. Mutationsprobe: ZUGANGSTAG_NUR_UEBERNOMMEN leeren -> rot."""
    eigen = _stamm_eigen()
    zeile_pex = _zeile("PEX", BEGINN, uebernommen=False)
    fehler = validate_ledger(eigen, zeile_pex)
    assert any("PEX-Buchung nicht nach dem Bestandszugang" in f for f in fehler), fehler
    assert validate_ledger(eigen, _zeile("ZUG", BEGINN, uebernommen=False)) == []


def test_die_regel_selbst_liefert_zwei_masken_je_zeile():
    """Die Naht der Funktion (von beiden Konsumenten gerufen): eine Maske je
    Zeile, getrennt nach Untergrenze und Obergrenze."""
    led = pd.concat([_zeile("STO", VOR), _zeile("STO", INNEN), _zeile("STO", DAHINTER)],
                    ignore_index=True)
    vor, hinter = buchungsfenster_verstoesse(led, _uebernommen(), HORIZONT)
    assert list(vor) == [True, False, False]
    assert list(hinter) == [False, False, True]
    vor, hinter = buchungsfenster_verstoesse(led, _uebernommen(), None)
    assert not hinter.any() and isinstance(hinter, np.ndarray)


# --------------------------------------------------------------------------- #
# Nachbesserung Runde E (Befund 1): ZUG, MIG und ABL sind an einen Zeitpunkt gebunden
# --------------------------------------------------------------------------- #
#
# Eine Ausnahmemenge ohne Wache fuer ihren Grund ist keine geschlossene Klasse:
# ZUG, MIG und ABL (``EREIGNIS_OHNE_ANNAHME``) standen nach dem Zugang an jedem
# Tag im Lauf ohne Befund. Aus jedem Grund wird eine Regel:
#   ZUG  genau einmal je Police (je Betragsart) und nur am Zugangstag,
#   MIG  nur am Zugangstag und nur bei einem uebernommenen Vertrag,
#   ABL  nur am Vertragsende (status_date == insurance_end, vertragsjahr == duration).


def _ungeregelt(ausnahmen, regeln):
    """Ausnahme-Ereignisse ohne Regel und Regeln ohne Ausnahme."""
    return sorted(set(ausnahmen) ^ set(regeln))


def test_ratsche_jede_ausnahme_hat_ihre_regel_mit_zeitpunkt():
    """Statische Ratsche, ``==``: Die Ausnahme-Ereignisse (aus keiner Annahme
    gezogen) und die Ereignisse mit Zeitpunktregel sind dieselbe Menge; die
    Zeitpunkte, die Einmal- und die Nur-uebernommen-Regel stehen hier von Hand.
    Ein neues Ausnahme-Ereignis ist ohne Regel rot.
    Mutationsprobe: ein Ereignis aus AUSNAHME_ZEITPUNKT streichen -> rot."""
    assert _ungeregelt(EREIGNIS_OHNE_ANNAHME, AUSNAHME_ZEITPUNKT) == []
    assert dict(AUSNAHME_ZEITPUNKT) == {
        "ZUG": "zugangstag", "MIG": "zugangstag", "ABL": "vertragsende"}
    assert set(AUSNAHME_EINMAL_JE_POLICE) == {"ZUG"}
    assert set(AUSNAHME_NUR_UEBERNOMMEN) == {"MIG"}
    # Positivkontrolle: die Ratsche findet ein Ereignis ohne Regel und eine Regel
    # ohne Ausnahme.
    assert _ungeregelt(set(EREIGNIS_OHNE_ANNAHME) | {"NEU"}, AUSNAHME_ZEITPUNKT) == ["NEU"]
    assert _ungeregelt(EREIGNIS_OHNE_ANNAHME, dict(AUSNAHME_ZEITPUNKT, TOD="zugangstag")) == ["TOD"]


def test_ratsche_die_ausnahmeregel_nennt_keine_ereignisart_und_beide_konsumenten_rufen_sie():
    """Statisch: Die Regel laeuft ueber die Mengen, nicht ueber Zweige je Art,
    und P-B1 und die Fuehrungsprobe rufen dieselbe Funktion.
    Mutationsprobe: ein ``art == "ABL"``-Zweig in der Regel oder einen der beiden
    Aufrufe entfernen -> rot."""
    from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung

    assert _sonderwege(inspect.getsource(ausnahme_ereignis_verstoesse)) == []
    assert "ausnahme_ereignis_verstoesse(" in inspect.getsource(validate_ledger)
    assert "ausnahme_ereignis_verstoesse(" in inspect.getsource(pruefe_fuehrung)


@pytest.fixture(scope="module")
def ausnahme_welt():
    """Ein echter Lauf mit Neuzugang (eigenes Geschaeft): ZUG aus dem Erzeuger,
    ABL aus der Engine — der Lauf bucht beides an seinem Platz."""
    from rechner_pipeline.bestand.config import load_config
    from rechner_pipeline.bestand.ereignisse import fortschreiben, mit_zugaengen
    from tests.test_bestand_neuzugang import EXAMPLE, REF
    from tests.zugangsstrom import bestand_aus_zugangsstrom

    bis = _dt.date(2016, 1, 1)
    config = load_config(EXAMPLE)
    basis = bestand_aus_zugangsstrom(config, bis=REF)
    erg = fortschreiben(basis, config, bis, neuzugang_ab=REF)
    return {"stamm": mit_zugaengen(basis, erg.zugaenge), "ledger": erg.ledger,
            "horizont": bis}


def _der_art(fehler, art):
    return [f for f in fehler if f.startswith(f"ledger: {art}-Buchung")]


def _faelle(welt, art):
    """(Horizont, {Fall: (Stamm, Ledger)}) der Art: ``gruen`` ist der Lauf an
    seinem Platz, die uebrigen Faelle haben genau EINEN Fehler dieser Art."""
    stamm, ledger = welt["stamm"], welt["ledger"]
    horizont = welt["horizont"]
    if art == "ZUG":
        zug = ledger[(ledger["ereignis"] == "ZUG") & (ledger["betrag_art"] == "VS")]
        i = zug["status_date"].idxmin()        # der fruehste Zugang: ein Monat spaeter liegt im Lauf
        verschoben = ledger.copy()
        verschoben.loc[i, "status_date"] = ledger.loc[i, "status_date"] + pd.DateOffset(months=1)
        return horizont, {
            "gruen": (stamm, ledger),
            "verschoben": (stamm, verschoben),
            "verdoppelt": (stamm, pd.concat([ledger, ledger.loc[[i]]], ignore_index=True))}
    if art == "ABL":
        i = ledger.index[ledger["ereignis"] == "ABL"][0]
        frueher = ledger.copy()
        frueher.loc[i, "status_date"] = ledger.loc[i, "status_date"] - pd.DateOffset(years=1)
        jahr = ledger.copy()
        jahr.loc[i, "vertragsjahr"] = int(ledger.loc[i, "vertragsjahr"]) - 1
        return horizont, {
            "gruen": (stamm, ledger),
            "verschoben": (stamm, frueher),
            "vertragsjahr_falsch": (stamm, jahr)}
    if art == "MIG":
        from rechner_pipeline.bestand.migrationszugang import uebernehmen, zugangsjournal
        from tests.test_migrationszugang import _uebernahme

        erg = uebernehmen([_uebernahme(900_001)])
        ueb = _uebernommen()
        eigen = _stamm_eigen()
        mig = zugangsjournal(erg, ZUGANG.date(), "TG2015")
        spaet = mig.assign(status_date=mig["status_date"] + pd.DateOffset(years=1))
        return HORIZONT, {
            "gruen": (ueb, mig),
            "verschoben": (ueb, spaet),
            "eigener_vertrag": (eigen, zugangsjournal(erg, BEGINN.date(), "TG2015"))}
    raise KeyError(art)          # ein neues Ausnahme-Ereignis braucht hier seine Faelle


@pytest.mark.parametrize("art", sorted(EREIGNIS_OHNE_ANNAHME))
def test_die_ausnahme_ereignisse_stehen_an_ihrem_zeitpunkt_und_sonst_nicht(ausnahme_welt, art):
    """Zaehltest je Ausnahme-Ereignis am echten Lauf (ZUG, ABL) bzw. an der
    echten Uebernahmezeile (MIG, ``zugangsjournal``): im richtigen Zeitpunkt
    gruen — und je verschoben oder verdoppelt GENAU EIN Befund dieser Art.
    Mutationsprobe je Regel: (1) ``ZUG`` aus AUSNAHME_ZEITPUNKT streichen ->
    ``ZUG/verschoben`` rot; (2) AUSNAHME_EINMAL_JE_POLICE leeren ->
    ``ZUG/verdoppelt`` rot; (3) ``MIG`` aus AUSNAHME_ZEITPUNKT streichen ->
    ``MIG/verschoben`` rot; (4) AUSNAHME_NUR_UEBERNOMMEN leeren ->
    ``MIG/eigener_vertrag`` rot; (5) ``ABL`` streichen bzw. die Pruefung von
    ``status_date == insurance_end`` weglassen -> ``ABL/verschoben`` rot; (6) die
    Pruefung ``vertragsjahr == duration`` weglassen -> ``ABL/vertragsjahr_falsch``
    rot."""
    horizont, faelle = _faelle(ausnahme_welt, art)
    stamm, ledger = faelle["gruen"]
    assert validate_ledger(stamm, ledger, horizont=horizont) == []      # der echte Lauf
    assert len(faelle) >= 3
    for name, (stamm, ledger) in faelle.items():
        if name == "gruen":
            continue
        fehler = _der_art(validate_ledger(stamm, ledger, horizont=horizont), art)
        assert len(fehler) == 1, (art, name, fehler)
    # Keine andere Ausnahme-Art ist von diesem Fall betroffen.
    for name, (stamm, ledger) in faelle.items():
        andere = [a for a in EREIGNIS_OHNE_ANNAHME if a != art]
        fehler = validate_ledger(stamm, ledger, horizont=horizont)
        assert all(_der_art(fehler, a) == [] for a in andere), (art, name, fehler)


@pytest.mark.parametrize("art", sorted(EREIGNIS_OHNE_ANNAHME))
def test_ein_befund_je_fehler_fensterregel_und_ausnahmeregel_melden_nicht_doppelt(art):
    """Dieselbe Zeile wird nicht von beiden Regeln gemeldet: Ein ZUG, MIG oder
    ABL VOR dem Zugang ist ein Fensterbefund, kein zweiter 'nicht am Platz'.
    Mutationsprobe: ``schon_gemeldet`` in der Regel ignorieren -> rot."""
    fehler = validate_ledger(_uebernommen(), _zeile(art, VOR))
    assert len(fehler) == 1 and "nicht nach dem Bestandszugang" in fehler[0], (art, fehler)


def test_die_regel_selbst_liefert_masken_je_regel_und_zeile():
    """Die Naht der Funktion (von beiden Konsumenten gerufen): eine Maske je
    Regel, je Ledgerzeile; ``schon_gemeldet`` nimmt Zeilen heraus."""
    stamm, zeile = _fall_am("ZUG", ZUGANG)
    verdoppelt = pd.concat([zeile, zeile], ignore_index=True)
    masken = ausnahme_ereignis_verstoesse(verdoppelt, stamm)
    assert sorted(masken) == ["einmal", "uebernommen", "zeitpunkt"]
    assert list(masken["einmal"]) == [False, True]
    assert not masken["zeitpunkt"].any() and not masken["uebernommen"].any()
    weg = np.array([False, True])
    assert not ausnahme_ereignis_verstoesse(verdoppelt, stamm, weg)["einmal"].any()


# --------------------------------------------------------------------------- #
# Die Naht von P-B1: Laufmanifest -> Horizont -> jede Art
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def lauf(tmp_path_factory):
    """Ein echter Fortschreibungslauf des eigenen Geschaefts bis 2030-01-01."""
    from tests.test_t27_runde_d_bestand import _lauf

    out, cfg = _lauf(tmp_path_factory.mktemp("fenster"), "2030-01-01")
    return out, cfg


def _mit_zeile(lauf_dir, cfg, art: str, datum: str, ziel):
    from tests.test_t27_runde_d_bestand import _manifest_nachfuehren

    shutil.copytree(lauf_dir, ziel)
    st = read_portfolio(ziel / "bestand_gesamt.parquet")
    led = read_portfolio(ziel / "ledger.parquet")
    pid = int(st[st.status_code == "POL"].police_id.iloc[0])
    zeile = st.set_index("police_id").loc[pid]
    ts = pd.Timestamp(datum)
    jahr = ((ts.year * 12 + ts.month)
            - (pd.Timestamp(zeile["insurance_start"]).year * 12
               + pd.Timestamp(zeile["insurance_start"]).month)) // 12
    neu = pd.DataFrame([{
        "police_id": pid, "tarif_generation": zeile["tarif_generation"], "ereignis": art,
        "vertragsjahr": jahr, "status_date": ts, "betrag_art": BETRAG_ART_JE_EREIGNIS[art][0],
        "betrag": 1.0, "betrag_herkunft": "gerechnet"}]).astype(led.dtypes.to_dict())
    write_portfolio(pd.concat([led, neu], ignore_index=True).sort_values(
        ["police_id", "status_date"], kind="stable").reset_index(drop=True), ziel / "ledger.parquet")
    _manifest_nachfuehren(ziel, cfg)
    return ziel


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_p_b1_haelt_jede_art_gegen_den_horizont_des_laufmanifests(lauf, tmp_path, art):
    """Die Naht: ``lies_und_pruefe_pb1`` reicht den im Manifest BELEGTEN
    Horizont an ``validate_ledger`` — fuer jede Art. Positivkontrolle: dieselbe
    Zeile ein Jahr vor dem Horizont bringt keinen Fensterbefund.
    Mutationsprobe: ``horizont=`` im Aufruf von validate_ledger weglassen ->
    rot (alle Arten)."""
    from tests.test_t27_runde_d_bestand import _pb1_fehler

    out, cfg = lauf
    innen = _mit_zeile(out, cfg, art, "2029-01-01", tmp_path / "innen")
    assert _fenster([f["message"] for f in _pb1_fehler(innen, cfg, _dt.date(2030, 1, 1))]) == []
    hinter = _mit_zeile(out, cfg, art, "2031-01-01", tmp_path / "hinter")
    fenster = _fenster([f["message"] for f in _pb1_fehler(hinter, cfg, _dt.date(2030, 1, 1))])
    assert len(fenster) == 1 and fenster[0].startswith(
        f"ledger: {art}-Buchung nach dem belegten Horizont 2030-01-01"), fenster
