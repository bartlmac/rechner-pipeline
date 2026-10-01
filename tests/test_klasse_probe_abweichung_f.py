"""Die Fuehrungsprobe kennt EINE Abweichungsregel — Runde F, Nachbesserung (F5 als Klasse).

Die Klasse hinter dem Befund 'ein NaN-Betrag galt als geprueft': Ein Vergleich
``abs(ist - soll) > TOLERANZ`` ist bei NaN auf EINER der beiden Seiten immer
falsch — der Wert gilt als uebereinstimmend. Runde F schloss das fuer die
Buchungsbetraege der Fortschreibung (``betrag_nicht_endlich``); sechs weitere
Vergleichsstellen der Probe blieben blind: die Stammsumme, die Bausteine
(Scheiben), der Zugang und die PEX-Umbuchung im Uebernahme-Ledger und die
beiden Vergleiche der nachgerechneten Buchungen (hier ist der SOLL-Wert der
Pruefstrecke NaN, der Ist-Betrag ist schon gefiltert).

Die Invariante ist eine Funktion, kein Vorsatz: ``models.bestand.weicht_ab``
meldet jeden nicht endlichen Wert, auf der Ist- wie auf der Soll-Seite, als
Abweichung, und die Probe vergleicht NUR noch durch sie. Drei Instrumente:

* Ratsche (statisch, ``==``): Die Zahl der rohen ``abs(...) > TOLERANZ``-Vergleiche
  in ``fuehrungsprobe.py`` ist null, die Zahl der Aufrufe von ``weicht_ab`` ist
  die Zahl der Vergleichsstellen — mit Positivkontrolle je Schreibform.
* Zaehltest je Stelle und Seite: ein NaN genau dort -> genau ein Befund der Art
  der Stelle (Repros des Pruefers E1, E2, E9, E10 nachgebaut).
* Mutationsprobe je Instanz im Docstring.

Knoten: klv
"""

from __future__ import annotations

import ast
import inspect
import math

import pandas as pd
import pytest

from rechner_pipeline.gates import fuehrungsprobe as _probe
from rechner_pipeline.gates.fuehrungsprobe import TOLERANZ, pruefe_fuehrung
from rechner_pipeline.models import bestand as _modell
from tests.test_baldrian2_e2e import gefahrener_fall  # noqa: F401
from tests.test_t27_pruefstrecke_runde_c import (  # noqa: F401
    PEX_POLICE,
    POL,
    _mit_red,
    welt,
)

NAN = float("nan")
#: Police mit Bausteinen, Anfangszustand und der Ablaufleistung im Lauf (7000023).
POL_ABL = 7000023
#: Police mit Bausteinen im Anfangszustand der Pruefstrecke.
POL_SCHEIBEN = 7000019
#: Die Vergleichsstellen der Probe, je Befundart; die Ratsche zaehlt sie mit ``==``.
VERGLEICHSSTELLEN = 6


# --------------------------------------------------------------------------- #
# 1. Ratschen
# --------------------------------------------------------------------------- #


def _rohe_vergleiche(quelle: str) -> int:
    """Die Zahl der Vergleiche, deren eine Seite ``abs(...)`` und deren andere
    ``TOLERANZ`` ist — in jeder Schreibform (``abs(x) > TOLERANZ``,
    ``TOLERANZ < abs(x)``, ``>=``/``<=``, ueberall im Ausdrucksbaum)."""
    zahl = 0
    for k in ast.walk(ast.parse(quelle)):
        if not isinstance(k, ast.Compare):
            continue
        seiten = [k.left, *k.comparators]
        hat_abs = any(isinstance(s, ast.Call) and isinstance(s.func, ast.Name)
                      and s.func.id == "abs" for s in seiten)
        hat_tol = any(isinstance(s, ast.Name) and s.id == "TOLERANZ" for s in seiten)
        zahl += hat_abs and hat_tol
    return zahl


def _aufrufe(quelle: str, name: str) -> int:
    return sum(isinstance(k, ast.Call) and isinstance(k.func, ast.Name) and k.func.id == name
               for k in ast.walk(ast.parse(quelle)))


@pytest.mark.parametrize("quelle", [
    "if abs(a - b) > TOLERANZ:\n    pass",
    "if abs(a - b) >= TOLERANZ:\n    pass",
    "if TOLERANZ < abs(a - b):\n    pass",
    "x = any(p != q or abs(p[1] - q[1]) > TOLERANZ for p, q in z)",
    "if x:\n    pass\nelif abs(float(l.loc[i]) - g) > TOLERANZ:\n    pass",
], ids=["gt", "gte", "gespiegelt", "im_generator", "elif_mit_float"])
def test_positivkontrolle_der_scanner_findet_jede_schreibform(quelle):
    """Der Scanner der Ratsche findet den rohen Vergleich in jeder Form —
    ohne diese Kontrolle bezeugte 'null Treffer' nichts."""
    assert _rohe_vergleiche(quelle) == 1
    assert _rohe_vergleiche("if weicht_ab(a, b, TOLERANZ):\n    pass") == 0


def test_ratsche_die_probe_vergleicht_nur_durch_die_eine_regel():
    """Statische Ratsche mit ``==``: In ``fuehrungsprobe.py`` steht kein roher
    ``abs(...) > TOLERANZ``-Vergleich mehr, und ``weicht_ab`` wird genau an den
    Vergleichsstellen gerufen (nicht mehr, nicht weniger: eine geloeschte
    Pruefung faellt auf). Die Regel ist die des Modells, keine lokale Abschrift.
    Mutationsprobe: an einer Stelle den rohen Vergleich zurueckbauen -> rot;
    einen Aufruf von ``weicht_ab`` entfernen -> rot."""
    quelle = inspect.getsource(_probe)
    assert _rohe_vergleiche(quelle) == 0
    assert _aufrufe(quelle, "weicht_ab") == VERGLEICHSSTELLEN
    assert _probe.weicht_ab is _modell.weicht_ab


# --------------------------------------------------------------------------- #
# 2. Die Regel im Kleinen
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("ist,soll,erwartet", [
    (100.0, 100.0, False),
    (100.0, 100.0 + TOLERANZ / 2, False),
    (100.0, 100.0 + 2 * TOLERANZ, True),
    (100.0 + 2 * TOLERANZ, 100.0, True),
    (NAN, 100.0, True), (100.0, NAN, True), (NAN, NAN, True),
    (math.inf, 100.0, True), (100.0, -math.inf, True),
    (math.inf, math.inf, True),                 # abs(inf - inf) ist NaN, nicht 0
    (None, 100.0, True),                        # fehlender Wert ist keine Zahl
])
def test_die_regel_meldet_nicht_endliche_werte_beider_seiten_als_abweichung(ist, soll, erwartet):
    """Wertetabelle von Hand: gleiche und in der Toleranz liegende Werte
    stimmen ueberein, jede nicht endliche Seite weicht ab — auch NaN gegen NaN
    und inf gegen inf, die ein Vergleich gleich nennen koennte. Mutationsprobe:
    die Endlichkeitspruefung entfernen -> die NaN- und inf-Faelle rot."""
    assert _modell.weicht_ab(ist, soll, TOLERANZ) is erwartet


def test_die_regel_nimmt_numpy_und_pandas_werte():
    """Die Probe reicht Series-Elemente und numpy-Skalare durch."""
    import numpy as np

    assert _modell.weicht_ab(np.float64("nan"), np.float64(1.0), TOLERANZ) is True
    assert _modell.weicht_ab(pd.Series([1.0]).iloc[0], 1.0, TOLERANZ) is False


# --------------------------------------------------------------------------- #
# 3. Zaehltest je Stelle und Seite
# --------------------------------------------------------------------------- #


def _nan_im_soll(monkeypatch, police: int, wandle):
    """Der Anfangszustand der Pruefstrecke fuer ``police`` wird durch
    ``wandle(zustand)`` gewandelt — die Soll-Seite der Vergleiche."""
    orig = _probe.anfangszustaende_je_police

    def gepatcht(*a, **k):
        zustaende, warnungen = orig(*a, **k)
        zustaende[str(police)] = wandle(dict(zustaende.get(str(police), {})))
        return zustaende, warnungen

    monkeypatch.setattr(_probe, "anfangszustaende_je_police", gepatcht)


def _urteil_mit(welt, *, ueb=None, tab=None, zeilen=None):
    basis = dict(welt["basis"])
    if zeilen is not None:
        basis["zeilen"] = zeilen
    return pruefe_fuehrung(uebernahme=ueb or welt["ueb"],
                           fortschreibung=tab or welt["tab"], **basis)


def _befunde(urteil, art):
    return [b for b in urteil["befunde"] if b["art"] == art]


def _bestand_nan(welt, pid):
    """Die Stammsumme von ``pid`` ist NaN — in Uebernahme UND Fortschreibung
    (Repro E9: Die Identitaetspruefung des Endbestands sieht dann nichts)."""
    ueb, tab = dict(welt["ueb"]), dict(welt["tab"])
    for tabellen in (ueb, tab):
        b = tabellen["bestand"].copy()
        b.loc[b["police_id"] == pid, "sum_insured"] = NAN
        tabellen["bestand"] = b
    return ueb, tab


def _scheibe_nan(welt, pid):
    """Eine Scheibe von ``pid`` traegt NaN — in Uebernahme UND Fortschreibung
    (Repro E10)."""
    ueb, tab = dict(welt["ueb"]), dict(welt["tab"])
    for tabellen in (ueb, tab):
        s = tabellen["scheiben"].copy()
        i = s.index[s["police_id"] == pid][0]
        s.loc[i, "sum_insured"] = NAN
        tabellen["scheiben"] = s
    return ueb, tab


def _ledger_nan(welt, pid, art):
    """Die Zeile (``pid``, ``art``) der Uebernahme traegt NaN — im Ledger der
    Uebernahme UND im Anfang des Ledgers der Fortschreibung (Repros E1, E2)."""
    ueb, tab = dict(welt["ueb"]), dict(welt["tab"])
    for tabellen in (ueb, tab):
        led = tabellen["ledger"].copy()
        maske = (led["police_id"] == pid) & (led["ereignis"] == art)
        assert maske.sum() == 1, (pid, art)
        led.loc[maske, "betrag"] = NAN
        tabellen["ledger"] = led
    return ueb, tab


def _fall(welt, monkeypatch, stelle: str, seite: str):
    """Das Urteil der Probe mit einem NaN genau an der Stelle und Seite."""
    if seite == "ist":
        if stelle == "stammsumme":
            ueb, tab = _bestand_nan(welt, POL)
        elif stelle == "scheiben":
            ueb, tab = _scheibe_nan(welt, POL_SCHEIBEN)
        elif stelle == "zugang":
            ueb, tab = _ledger_nan(welt, POL, "ZUG")
        else:
            assert stelle == "umbuchung"
            ueb, tab = _ledger_nan(welt, PEX_POLICE, "PEX")
        return _urteil_mit(welt, ueb=ueb, tab=tab)
    if stelle == "stammsumme":
        zeilen = [dict(z, sum_insured=NAN) if int(z["police_id"]) == POL else z
                  for z in welt["basis"]["zeilen"]]
        return _urteil_mit(welt, zeilen=zeilen)
    if stelle == "scheiben":
        _nan_im_soll(monkeypatch, POL_SCHEIBEN, lambda z: dict(
            z, scheiben=tuple((j, NAN if i == 0 else s) for i, (j, s) in enumerate(z["scheiben"]))))
    elif stelle == "zugang":
        _nan_im_soll(monkeypatch, POL_SCHEIBEN, lambda z: dict(z, sum_insured=NAN))
    elif stelle == "umbuchung":
        _nan_im_soll(monkeypatch, PEX_POLICE, lambda z: dict(z, sum_insured=NAN))
    else:
        assert stelle == "buchung"
        _nan_im_soll(monkeypatch, POL_ABL, lambda z: dict(z, sum_insured=NAN))
    return _urteil_mit(welt)


STELLEN = [
    ("stammsumme", "ist"), ("stammsumme", "soll"),
    ("scheiben", "ist"), ("scheiben", "soll"),
    ("zugang", "ist"), ("zugang", "soll"),
    ("umbuchung", "ist"), ("umbuchung", "soll"),
    ("buchung", "soll"),
]


@pytest.mark.parametrize("stelle,seite", STELLEN, ids=[f"{s}-{x}" for s, x in STELLEN])
def test_die_probe_meldet_ein_nan_an_jeder_vergleichsstelle_genau_einmal(
        welt, monkeypatch, stelle, seite):
    """Zaehltest je Stelle und Seite: Ein NaN auf der Ist- bzw. der Soll-Seite
    des Vergleichs bringt GENAU einen Befund der Art der Stelle und das Urteil
    'nicht bestanden' (vorher: kein Befund, bestanden). Positivkontrolle: die
    Welt ist ohne das NaN frei von Befunden dieser Art.
    Mutationsprobe: an jeder der sechs Stellen den Aufruf von ``weicht_ab`` durch
    den rohen Vergleich ersetzen -> die Faelle dieser Stelle rot (die Ist-Faelle
    von 'buchung' sind durch ``betrag_nicht_endlich`` gedeckt und stehen im
    Modul ``test_klasse_probe_betrag_wirkungstag_f``)."""
    assert _befunde(_urteil_mit(welt), stelle) == []
    urteil = _fall(welt, monkeypatch, stelle, seite)
    treffer = _befunde(urteil, stelle)
    assert len(treffer) == 1, [(b["art"], b["text"][:80]) for b in urteil["befunde"]]
    assert "nan" in treffer[0]["text"]       # die Messung steht im Befundtext
    assert not urteil["bestanden"]


def test_die_probe_meldet_ein_nan_der_soll_buchung_einer_herabsetzung(welt, monkeypatch):
    """Die zweite Buchungsstelle (herabgesetzter Vertrag): Die Soll-Betraege der
    Herabsetzung sind NaN -> je gebuchter RED-Zeile genau ein Befund 'buchung'
    (vorher: alle als geprueft und uebereinstimmend gezaehlt). Positivkontrolle:
    dieselbe Herabsetzung mit dem echten Soll besteht.
    Mutationsprobe: den Vergleich in der Herabsetzungs-Zweig durch den rohen
    ersetzen -> rot."""
    from rechner_pipeline.models.bestand import red_sollbuchungen as echt

    tab = _mit_red(welt, POL, 12)
    assert _urteil_mit(welt, tab=tab)["bestanden"]
    monkeypatch.setattr(_probe, "red_sollbuchungen",
                        lambda *a, **k: {art: NAN for art in echt(*a, **k)})
    urteil = _urteil_mit(welt, tab=tab)
    red = tab["ledger"][tab["ledger"]["ereignis"] == "TKU"]
    assert len(red) >= 2
    assert len(_befunde(urteil, "buchung")) == len(red), [
        (b["art"], b["text"][:80]) for b in urteil["befunde"]]
    assert all("herabgesetzter Vertrag nan" in b["text"] for b in _befunde(urteil, "buchung"))
    assert not urteil["bestanden"]
