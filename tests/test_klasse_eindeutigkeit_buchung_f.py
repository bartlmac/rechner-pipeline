"""Klasse: je Buchung genau eine Zeile, fuer ALLE Ereignisarten — Runde F, Nachbesserung.

Die Invariante: Je (Police, Ereignis, Wirkungstag, Betragsart) steht GENAU eine
Zeile im Ledger. Die Paarregel (``beitragspaar_verstoesse``, F4) zaehlte nur
die Zeilen der Beitragsereignisse ZUG und ERH; eine verdoppelte Zeile jeder
anderen Art (STO, TOD, PEX, ABL, RED, MIG, INV, REA) bemerkten weder P-B1 noch
die Fuehrungsprobe noch der Bericht — die Probe rechnete sie zweimal nach und
zaehlte sie zweimal als geprueft.

Die Regel ist EINE Funktion (``models.bestand.doppelte_buchungen``), gerufen von
``validate_ledger``, von ``pruefe_fuehrung`` (Fortschreibung und Ledger der
Uebernahme) und von der Vollstaendigkeitspruefung der Herabsetzung
(``ledger_bindung``). Die Paarregel bleibt daneben: Sie zaehlt, was KEINE
Verdopplung ist (Beitragszeile ohne Summenzeile, zwei verschiedene
Summenzeilen); die Verdopplung ihrer Arten meldet sie weiter selbst — die
Eindeutigkeitsregel nimmt :data:`BEITRAGSEREIGNISSE` aus (ein Fehler, ein
Befund). Instrumente: Ratsche (statisch, mit Positivkontrolle), Zaehltest je
Ereignisart aus ``EREIGNIS_VALUES`` an der Regel selbst und an den Konsumenten,
die Mutationsprobe je Instanz im Docstring.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import inspect
import re

import numpy as np
import pandas as pd
import pytest

from rechner_pipeline.bestand import ledger_bindung as _bindung
from rechner_pipeline.gates.fuehrungsprobe import pruefe_fuehrung
from rechner_pipeline.models.bestand import (
    BETRAG_ART_JE_EREIGNIS,
    BEITRAGSEREIGNISSE,
    BUCHUNG_SCHLUESSEL,
    EREIGNIS_VALUES,
    doppelte_buchungen,
    validate_ledger,
)
from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: F401
from tests.test_klasse_paarbuchung_f import _p_b1, _verdoppelt, eigen  # noqa: F401
from tests.test_klasse_probe_betrag_wirkungstag_f import JAHRESTAG, _mit_zeile
from tests.test_t27_pruefstrecke_runde_c import POL, PEX_POLICE, _mit_red, _urteil, welt  # noqa: F401

#: Die Arten, die der echte Lauf (``eigen``) bucht; die Zaehltests an den
#: Konsumenten laufen ueber sie. MIG, INV und REA stehen nur in der Regel
#: selbst (Zaehltest ueber das ganze Vokabular) bzw. in eigenen Faellen. RED
#: und TKU bucht der echte Lauf, seit die Config der PLV Herabsetzung und
#: Teilkuendigung erzeugt (2026-10-01).
ARTEN_IM_ECHTEN_LAUF = ["ZUG", "ERH", "RED", "TKU", "PEX", "STO", "TOD", "ABL"]
POL_ABL = 7000023     # bucht im gefahrenen Baldrian-Lauf eine echte ABL am 2027-01-01


def _zeilen(art: str, n: int, *, police: int = 1, tag: str = "2020-01-01",
            betrag_art: str | None = None) -> pd.DataFrame:
    return pd.DataFrame({
        "police_id": [police] * n, "ereignis": [art] * n,
        "status_date": [pd.Timestamp(tag)] * n,
        "betrag_art": [betrag_art or BETRAG_ART_JE_EREIGNIS[art][0]] * n,
        "betrag": [1.0] * n})


def _befunde(urteil, art):
    return [b for b in urteil["befunde"] if b["art"] == art]


# --------------------------------------------------------------------------- #
# 1. Ratschen
# --------------------------------------------------------------------------- #


def test_ratsche_der_schluessel_ist_der_der_buchung_und_das_vokabular_vollstaendig():
    """Der Schluessel ist (Police, Ereignis, Wirkungstag, Betragsart) — so
    haelt ihn die Vorgabe fest, und jede Ereignisart des Vokabulars hat eine
    Betragsart (sonst waere der Zaehltest unten nicht fuer jede Art
    gebaut). Mutationsprobe: eine Spalte aus dem Schluessel nehmen -> rot."""
    assert BUCHUNG_SCHLUESSEL == ("police_id", "ereignis", "status_date", "betrag_art")
    assert set(BETRAG_ART_JE_EREIGNIS) == set(EREIGNIS_VALUES)


def test_ratsche_die_regel_nennt_keine_ereignisart_im_klartext():
    """Statisch: Die Regel laeuft ueber den Schluessel, nicht ueber einen Zweig
    je Art. Mutationsprobe: ein ``== "STO"``-Zweig in ``doppelte_buchungen`` ->
    rot."""
    quelle = inspect.getsource(doppelte_buchungen)
    assert [w for w in EREIGNIS_VALUES if re.search(rf"['\"]{w}['\"]", quelle)] == []
    assert re.search(r"['\"]STO['\"]", 'if art == "STO":')          # Positivkontrolle


def test_ratsche_alle_konsumenten_rufen_die_eine_regel():
    """P-B1, die Probe und die Vollstaendigkeitspruefung der Herabsetzung rufen
    ``doppelte_buchungen``, keine Abschrift. Mutationsprobe: einen der drei
    Aufrufe entfernen -> rot."""
    assert "doppelte_buchungen(" in inspect.getsource(validate_ledger)
    assert "doppelte_buchungen(" in inspect.getsource(pruefe_fuehrung)
    assert "doppelte_buchungen(" in inspect.getsource(_bindung)


def test_ratsche_die_ausnahme_sind_genau_die_beitragsereignisse():
    """``==``: Die Eindeutigkeitsregel laesst nur die Arten aus, deren
    Verdopplung die Paarregel meldet. Mutationsprobe: ein Eintrag mehr oder
    weniger im Standard -> rot."""
    standard = inspect.signature(doppelte_buchungen).parameters["ohne_arten"].default
    assert tuple(standard) == tuple(BEITRAGSEREIGNISSE)


# --------------------------------------------------------------------------- #
# 2. Die Regel selbst, je Ereignisart des Vokabulars
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_regel_zaehlt_jede_verdoppelte_zeile_genau_einmal(art):
    """Zaehltest je Ereignisart aus ``EREIGNIS_VALUES``: Eine Zeile einmal ->
    keine Meldung; verdoppelt -> GENAU die zweite Zeile (die ueberzaehlige).
    Die Beitragsereignisse meldet die Paarregel; mit ``ohne_arten=()`` zaehlt
    die Regel auch sie. Mutationsprobe: ``keep=False`` statt ``"first"`` -> die
    Zeile zaehlt doppelt, rot; die Ausnahme entfernen -> der Fall der
    Beitragsereignisse rot."""
    assert not doppelte_buchungen(_zeilen(art, 1), ohne_arten=()).any()
    zwei = _zeilen(art, 2)
    alle = doppelte_buchungen(zwei, ohne_arten=())
    assert list(alle) == [False, True]
    standard = doppelte_buchungen(zwei)
    assert list(standard) == ([False, False] if art in BEITRAGSEREIGNISSE else [False, True])


@pytest.mark.parametrize("art", EREIGNIS_VALUES)
def test_die_regel_haelt_verschiedene_buchungen_auseinander(art):
    """Gegenprobe je Art: Eine andere Police, ein anderer Tag oder eine andere
    Betragsart ist eine ANDERE Buchung (keine Meldung); ebenso die Zeile einer
    anderen Art. Mutationsprobe: eine Schluesselspalte weglassen -> rot."""
    arten = BETRAG_ART_JE_EREIGNIS[art]
    andere = [
        _zeilen(art, 1), _zeilen(art, 1, police=2), _zeilen(art, 1, tag="2021-01-01"),
        _zeilen("STO" if art != "STO" else "TOD", 1)]
    if len(arten) > 1:
        andere.append(_zeilen(art, 1, betrag_art=arten[1]))
    assert not doppelte_buchungen(pd.concat(andere, ignore_index=True), ohne_arten=()).any()


def test_die_regel_laesst_gemeldete_zeilen_aus():
    """Eine Zeile, die eine andere Regel schon beanstandet (Fenster,
    Ausnahme-Ereignis), scheidet aus — ein Fehler, ein Befund; die Nummerierung
    des Ledgers (Index) ist dabei gleichgueltig. Mutationsprobe: ``schon_gemeldet``
    ignorieren -> rot."""
    led = pd.concat([_zeilen("STO", 2), _zeilen("TOD", 2)], ignore_index=True)
    led.index = [10, 3, 7, 3]
    assert list(doppelte_buchungen(led)) == [False, True, False, True]
    assert list(doppelte_buchungen(led, np.array([False, True, False, False]))) == [
        False, False, False, True]


# --------------------------------------------------------------------------- #
# 3. Zaehltest an P-B1 (validate_ledger) auf dem echten Lauf
# --------------------------------------------------------------------------- #


def test_der_echte_lauf_traegt_jede_zeile_einmal_und_die_arten_sind_gemessen(eigen):
    """Positivkontrolle: Der echte Lauf ist eindeutig und P-B1 leer; die Arten,
    ueber die der Zaehltest laeuft, sind GENAU die gebuchten (``==``)."""
    led = eigen["ledger"]
    assert set(led["ereignis"]) == set(ARTEN_IM_ECHTEN_LAUF)
    assert not doppelte_buchungen(led, ohne_arten=()).any()
    assert _p_b1(eigen, led) == []


@pytest.mark.parametrize("art", ARTEN_IM_ECHTEN_LAUF)
def test_p_b1_meldet_eine_verdoppelte_zeile_jeder_art_genau_einmal(eigen, art):
    """Zaehltest je Art am echten Lauf (E7 des Pruefers): eine Zeile der Art
    verdoppelt -> GENAU ein Befund, und er nennt die Art. ZUG und ERH meldet die
    Paarregel bzw. die Einmal-Regel des Zugangs (ein Fehler, ein Befund).
    Mutationsprobe: den Aufruf in ``validate_ledger`` entfernen -> die Faelle
    PEX, STO, TOD, ABL rot."""
    led = eigen["ledger"]
    i = led.index[led["ereignis"] == art][3]
    fehler = _p_b1(eigen, _verdoppelt(led, i), scheiben=False)
    assert len(fehler) == 1, fehler
    assert fehler[0].startswith(f"ledger: {art}-Buchung"), fehler


# --------------------------------------------------------------------------- #
# 4. Zaehltest an der Fuehrungsprobe
# --------------------------------------------------------------------------- #


def _doppelt(tab, art, *, jahr_ab=None):
    """Die Fortschreibung mit der ersten Zeile der Art nach dem Stichtag
    verdoppelt."""
    led = tab["ledger"]
    i = led.index[(led["ereignis"] == art)
                  & (led["status_date"] > pd.Timestamp("2026-01-01"))][0]
    return dict(tab, ledger=_verdoppelt(led, i))


def _basis_und_doppelt(welt, art):
    if art == "ABL":
        basis = welt["tab"]                       # die echte ABL von 7000023
    else:
        basis = _mit_zeile(welt, art, JAHRESTAG, 1.0)
    return basis, _doppelt(basis, art)


@pytest.mark.parametrize("art", ["STO", "PEX", "TOD", "ABL"])
def test_die_probe_meldet_eine_verdoppelte_buchung_einmal_und_zaehlt_sie_nicht_doppelt(welt, art):
    """Zaehltest je nachgerechnete Art (E6 des Pruefers): die Zeile nach dem
    Stichtag verdoppelt -> GENAU ein Befund 'doppelte_buchung', und die
    ueberzaehlige Zeile wird weder nachgerechnet noch als geprueft gezaehlt:
    Geprueft, abweichend und Zahl der Abweichungsbefunde bleiben die der
    einfachen Zeile. Mutationsprobe: die ueberzaehlige Zeile nicht aus ``nach``
    nehmen -> geprueft steigt, rot; den Aufruf entfernen -> rot."""
    basis, doppelt = _basis_und_doppelt(welt, art)
    einfach = _urteil(welt, basis)
    assert _befunde(einfach, "doppelte_buchung") == []
    urteil = _urteil(welt, doppelt)
    treffer = _befunde(urteil, "doppelte_buchung")
    assert len(treffer) == 1, [(b["art"], b["text"][:70]) for b in urteil["befunde"]]
    assert treffer[0]["text"].startswith(f"{art}-Buchung") and treffer[0]["ereignis"] == art
    assert urteil["buchungen_geprueft"] == einfach["buchungen_geprueft"]
    assert urteil["buchungen_abweichend"] == einfach["buchungen_abweichend"]
    assert len(_befunde(urteil, "buchung")) == len(_befunde(einfach, "buchung"))
    assert not urteil["bestanden"]


def test_die_probe_meldet_eine_verdoppelte_zeile_der_herabsetzung_einmal(welt):
    """RED: Die Vollstaendigkeitspruefung der Herabsetzung zaehlt 'genau einmal'
    und meldete die verdoppelte Zeile schon; jetzt meldet es die
    Eindeutigkeitsregel, und die Herabsetzung sieht die ueberzaehlige Zeile nicht
    mehr (ein Fehler, ein Befund). Positivkontrolle: dieselbe Herabsetzung
    einfach bestanden. Mutationsprobe: ``eigene`` der Vollstaendigkeitspruefung
    nicht bereinigen -> zwei Befunde, rot."""
    tab = _mit_red(welt, POL, 12)
    einfach = _urteil(welt, tab)
    assert einfach["bestanden"]
    led = tab["ledger"]
    i = led.index[(led["ereignis"] == "TKU") & (led["betrag_art"] == "RKW_teilkuendigung")][0]
    urteil = _urteil(welt, dict(tab, ledger=_verdoppelt(led, i)))
    assert len(_befunde(urteil, "doppelte_buchung")) == 1
    assert _befunde(urteil, "herabsetzung") == []
    assert urteil["buchungen_geprueft"] == einfach["buchungen_geprueft"]
    assert len(urteil["befunde"]) == 1, [(b["art"], b["text"][:70]) for b in urteil["befunde"]]


@pytest.mark.parametrize("police,art", [(POL, "ZUG"), (PEX_POLICE, "PEX")])
def test_die_probe_meldet_eine_verdoppelte_zeile_im_ledger_der_uebernahme(welt, police, art):
    """Der Ledger der Uebernahme (E1/E2-Welt): Eine verdoppelte Zugangs- oder
    Umbuchungszeile war eine Reihe mit zwei Eintraegen, die der Vergleich nicht
    in eine Zahl wandeln konnte. Jetzt EIN Befund, ohne Absturz.
    Mutationsprobe: den Aufruf fuer den Uebernahme-Ledger entfernen -> rot."""
    ueb = dict(welt["ueb"])
    led = ueb["ledger"]
    i = led.index[(led["police_id"] == police) & (led["ereignis"] == art)][0]
    ueb["ledger"] = _verdoppelt(led, i)
    urteil = pruefe_fuehrung(uebernahme=ueb, fortschreibung=None, **welt["basis"])
    assert len(_befunde(urteil, "doppelte_buchung")) == 1
    assert len(urteil["befunde"]) == 1, [(b["art"], b["text"][:70]) for b in urteil["befunde"]]


# --------------------------------------------------------------------------- #
# 5. Der Bericht rendert keinen Lauf mit verdoppelter Zeile
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("art", ["STO", "PEX", "TOD", "ABL"])
def test_der_bericht_rendert_keine_verdoppelte_zeile(tmp_path, art):
    """Der Weg der Gutachter (E11/E14): eine Ledgerzeile der Art verdoppelt,
    Laufmanifest stimmig nachgefuehrt -> P-B1 weist mit GENAU einem Befund ab,
    der Bericht rendert nicht. Positivkontrolle: der unveraenderte Lauf rendert.
    Mutationsprobe: den Aufruf in ``validate_ledger`` entfernen -> rot."""
    from rechner_pipeline.bestand import cli_report as _bericht
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
    from tests.test_t27_runde_d_bestand import (
        _bericht_argv,
        _lauf,
        _manifest_nachfuehren,
        _pb1_fehler,
    )

    bis = "2045-01-01"
    out, cfg = _lauf(tmp_path, bis)
    assert _pb1_fehler(out, cfg, _dt.date.fromisoformat(bis)) == []
    assert _bericht.main(_bericht_argv(out, cfg, bis, tmp_path / "ok.html")) == 0
    led = read_portfolio(out / "ledger.parquet")
    kandidaten = led.index[led["ereignis"] == art]
    assert len(kandidaten), f"der Lauf bucht keine {art}"
    write_portfolio(_verdoppelt(led, kandidaten[0]).astype(led.dtypes.to_dict()),
                    out / "ledger.parquet")
    _manifest_nachfuehren(out, cfg)
    fehler = [f["message"] for f in _pb1_fehler(out, cfg, _dt.date.fromisoformat(bis))]
    # Die Folgen (Bilanz der Bewegungen, Beitragsfreistellung je Police) melden
    # andere Pruefungen daneben; die Eindeutigkeitsregel meldet die Ursache
    # genau einmal.
    ursache = [f for f in fehler if "mehrfach gebucht" in f]
    assert len(ursache) == 1 and ursache[0].startswith(f"ledger: {art}-Buchung"), fehler
    ziel = tmp_path / "x.html"
    assert _bericht.main(_bericht_argv(out, cfg, bis, ziel)) != 0
    assert not ziel.exists()


def test_die_probe_meldet_eine_verdoppelte_zeile_am_falschen_tag_je_fehler_einmal(welt):
    """Zwei Fehler, zwei Befunde: Eine Zeile neben dem Jahrestag (Wirkungstag)
    UND verdoppelt (Eindeutigkeit) bringt den Wirkungstag-Befund fuer die erste
    Zeile — die Buchung — und GENAU einen Eindeutigkeits-Befund fuer die
    Wiederholung; die Wiederholung wird nicht zusaetzlich als falsch datiert
    gezaehlt. Mutationsprobe: die ueberzaehlige Zeile nicht in ``gemeldet``
    aufnehmen -> zwei Wirkungstag-Befunde, rot."""
    from tests.test_klasse_probe_betrag_wirkungstag_f import NEBEN_DEM_JAHRESTAG

    tab = _mit_zeile(welt, "STO", NEBEN_DEM_JAHRESTAG, 1.0)
    led = tab["ledger"]
    i = led.index[led["status_date"] == NEBEN_DEM_JAHRESTAG][0]
    urteil = _urteil(welt, dict(tab, ledger=_verdoppelt(led, i)))
    assert len(_befunde(urteil, "wirkungstag")) == 1
    assert len(_befunde(urteil, "doppelte_buchung")) == 1


# --------------------------------------------------------------------------- #
# 6. Die Herabsetzung im Ledger-Gate: die Wiederholung zaehlt die Vollstaendigkeit nicht mit
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def welt_tk():
    """Der Bestand mit Teilkuendigungen aus ``test_t27_teilkuendigung_klasse``
    (in-memory, echte Engine) — dieselbe Welt, andere Fixture-Bezeichnung."""
    from rechner_pipeline.bestand.ereignisse import fortschreiben
    from tests.test_bestand_uebernommen_fortschreiben import _stamm as _stamm_tk
    from tests.test_herabsetzung_in_fuehrung import BIS, POLICEN
    from tests.test_schicht_in_fuehrung import _tabellen
    from tests.test_t27_teilkuendigung_klasse import _config

    config = _config()
    stamm = _stamm_tk([{"id": p, "beginn": "2015-01-01", "zugang": "2026-01-01"}
                       for p in POLICEN])
    schichten, verankerung = _tabellen(POLICEN)
    erg = fortschreiben(stamm, config, BIS, schichten=schichten, verankerung=verankerung)
    return config, stamm, schichten, verankerung, erg


def test_die_vollstaendigkeitspruefung_der_herabsetzung_zaehlt_die_wiederholung_nicht(welt_tk):
    """Die Vollstaendigkeit (T27-14) verlangt jede Soll-Zeile 'genau einmal' und
    meldete eine verdoppelte Auszahlung als 'mehrfach gebucht'. Jetzt meldet das
    die Eindeutigkeitsregel in ``validate_ledger`` (GENAU einmal), und die
    Vollstaendigkeit sieht nur die erste Zeile (ein Fehler, ein Befund).
    Positivkontrolle: der einfache Lauf ist leer. Mutationsprobe: die
    Bereinigung in ``ledger_bindung`` entfernen -> die Vollstaendigkeit meldet
    zusaetzlich, rot."""
    from tests.test_t27_teilkuendigung_klasse import _pb1, _voll

    config, stamm, schichten, verankerung, erg = welt_tk
    led = erg.ledger
    assert _pb1(welt_tk, led) == []
    i = led.index[(led["ereignis"] == "TKU") & (led["betrag_art"] == "RKW_teilkuendigung")][0]
    doppelt = _verdoppelt(led, i)
    fehler = _pb1(welt_tk, doppelt)
    assert not [f for f in fehler if "registrierter Herabsetzungen" in f], fehler
    meldungen = validate_ledger(stamm, _voll(welt_tk, doppelt))
    assert len([m for m in meldungen if "mehrfach gebucht" in m]) == 1, meldungen
    assert [m for m in meldungen if "mehrfach gebucht" in m][0].startswith("ledger: TKU-Buchung")
