"""Neuaufsetzen: eine Verweigerung hinterlaesst keinen Rest neben der Ablage.

Pruefer-Befund (Angriffsrunde 2026-10-01): ``neu_aufsetzen`` verweigerte bei
einer A-M4-Rolle ohne A-M4 richtig, liess aber ``daten.neu-<stempel>``
liegen — die Rollenpruefung lief erst in ``eingang_anlegen``, nachdem die
neue Ablage angelegt war. Die Klasse dahinter: Jede Verweigerung nach dem
Anlegen liess denselben Rest, und der naechste Aufruf verweigerte dann mit
"Rest eines abgebrochenen Aufbaus, von Hand klaeren".

Geschlossen in zwei Linien:

1. Die Vorbedingungen der Registrierung, die keinen Ort brauchen
   (``uebernahme.registrierung_vorbedingungen``: A-M4 und A-B2 samt
   Rollenregel, Schema, Tabellen und Belege gegen den Beleggraphen),
   prueft ``neu_aufsetzen`` BEVOR etwas angelegt wird — mit derselben
   Funktion, die ``eingang_anlegen`` ruft.
2. Was nur gegen die neue Ablage pruefbar ist (Bindung der A-B2 an Eingang
   und Stand, A-M1 der Soll-Bindung, Nebentabellen, P-B1, Lesbarkeit des
   Eingangs), scheitert nach dem Anlegen; dann entfernt ``neu_aufsetzen``
   seine eigene, nie veroeffentlichte Vorbereitung ueber
   ``betrieb._loeschen`` — die Lebenszyklus-Identitaet steht fest (Name
   ``<stand>.neu-<stempel>`` dieses Aufrufs, keine Provenienz geschrieben).

Der Zaehltest: je Verweigerungsursache, die ``neu_aufsetzen`` kennt, die
Geschwister der Ablage vorher und nachher — gleich (==), und die alte
Ablage unberuehrt.

``tageslauf.SCHREIBZIELE`` deckt dieses Staging NICHT ab: Die Tabelle
beschreibt atomare Schreiber UNTER der Ablage, deren Tempdateien der
naechste Lauf raeumt; ``<stand>.neu-*`` liegt neben der Ablage und gehoert
keinem Lauf.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from rechner_pipeline.betrieb import neuaufsetzen as na
from rechner_pipeline.betrieb import uebernahme as ueb
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, tageslauf
from tests.test_abnahme_rolle_klasse import _ordnung_klasse, _ordnung_ohne, _schreibe
from tests.test_betrieb_neuaufsetzen import _ablage, _fall_mit_nebentabellen
from tests.test_betrieb_uebernahme import STICHTAG

JETZT = dt.datetime(2026, 9, 8, 6, 0, tzinfo=dt.timezone.utc)


def _geschwister(ablage) -> list:
    return sorted(p.name for p in ablage.wurzel.parent.iterdir())


def _stand_der_ablage(ablage) -> dict:
    return {str(p.relative_to(ablage.wurzel)): p.stat().st_size
            for p in sorted(ablage.wurzel.rglob("*")) if p.is_file() and p.name != "lauf.lock"}


def _mit_ordnung(ordnung):
    def anpassen(tmp_path, kw, monkeypatch):
        # Die Abnahmen des Falls unter dem Glied dieser Ordnung, gelesen unter
        # ihrer Linie (ADR-025: die Linie ist Pflicht; gilt die Ordnung, unter
        # der gezeichnet wurde).
        from tests.test_abnahme_rolle_klasse import _unter_ordnung

        kw["betriebsschluessel"] = kw["_naht"][0]
        kw["zeichnungsordnung"] = _schreibe(tmp_path / "ordnung-aussen", "o.json", ordnung())
        kw["linie"] = _unter_ordnung(kw["fall"], ordnung(), tmp_path / "linie-neuaufsetzen")
    return anpassen


def _ohne_ring(tmp_path, kw, monkeypatch):
    monkeypatch.setattr(ueb, "_STANDARD_SCHLUESSELRING", None)


def _ohne_ab2(tmp_path, kw, monkeypatch):
    monkeypatch.setattr(ueb, "_STANDARD_ZUGANGSABNAHME", None)


def _ab2_vorab_unberechtigt(tmp_path, kw, monkeypatch):
    """Produktiv kommt A-B2 als --zugangsabnahme (oder aus dem Gate-Ledger)
    und wird VOR dem Anlegen gelesen; die Ordnung gibt mensch/betrieb A-B2
    nicht."""
    import hashlib

    from tests.freigabe_testschluessel import BETRIEB_FREIGABEKEY, suitelinie_pin
    from tests.zugangsabnahme_testhelfer import ab2_snapshot

    fall = kw["fall"]
    daten = ab2_snapshot(fall.name, pflichtbelege={
        rolle: [hashlib.sha256(rolle.encode()).hexdigest()]
        for rolle in ("zugangsprobe", "am4_snapshot", "eingang")},
        vorgaenger=[], schluessel=BETRIEB_FREIGABEKEY,
        pin=suitelinie_pin(_ordnung_ohne("A-B2")))
    (fall / "entscheide" / f"A-B2-{daten['snapshot_sha256']}.json").write_text(
        json.dumps(daten), encoding="utf-8")
    kw["zugangsabnahme_sha256"] = daten["snapshot_sha256"]
    _mit_ordnung(lambda: _ordnung_ohne("A-B2"))(tmp_path, kw, monkeypatch)


def _falscher_stichtag(tmp_path, kw, monkeypatch):
    kw["stichtag"] = dt.date(2026, 3, 1)


def _fremde_tabelle(tmp_path, kw, monkeypatch):
    from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio

    quelle = kw["fall"] / "abgeleitet" / "bestand" / "historie.parquet"
    tabelle = read_portfolio(quelle)
    write_portfolio(tabelle.iloc[:0], quelle)


def _spaete_ab2_bindung(tmp_path, kw, monkeypatch):
    def scheitert(*a, **k):
        raise ueb.UebernahmeError("A-B2 bindet einen anderen Stand (Test)")
    monkeypatch.setattr(ueb, "_zugangsabnahme_binden", scheitert)


def _eingang_unlesbar(tmp_path, kw, monkeypatch):
    def scheitert(*a, **k):
        raise ueb.UebernahmeError("Eingang unlesbar (Test)")
    monkeypatch.setattr(na, "lies_uebernahme", scheitert)


#: Je Verweigerungsursache: (Name, Anpassung, Meldungsmuster). Vor dem
#: Anlegen: Schluessel, A-B2, Rollenregel (A-M4 und A-B2), Klasse, Tabellen
#: gegen den Beleggraphen. Nach dem Anlegen: Stichtag gegen den Zugang
#: (Lesbarkeit), A-B2-Bindung, Lesbarkeit des Eingangs.
#: Je Verweigerungsursache: (Name, Anpassung, Meldungsmuster, vor dem
#: Anlegen?). ``True``: die Ursache faellt, BEVOR ein Verzeichnis entsteht.
URSACHEN = [
    ("ohne_freigabeschluessel", _ohne_ring, "Freigabeschluessel", True),
    ("ohne_zugangsabnahme", _ohne_ab2, "Zugangsabnahme A-B2", True),
    ("a_m4_rolle_ohne_gate", _mit_ordnung(lambda: _ordnung_ohne("A-M4")), "nicht fuer A-M4", True),
    ("a_b2_rolle_vorab", _ab2_vorab_unberechtigt, "nicht fuer A-B2", True),
    # In der Suite kommt A-B2 sonst ueber die Test-Naht, die ihn erst gegen
    # den geschriebenen Eingang anlegt — dann faellt die Rolle nach dem Anlegen.
    ("a_b2_rolle_ueber_naht", _mit_ordnung(lambda: _ordnung_ohne("A-B2")), "nicht fuer A-B2",
     False),
    ("a_m4_klasse", _mit_ordnung(lambda: _ordnung_klasse("mensch/aktuariat", "simulation")),
     "Schluesselklasse", True),
    ("tabelle_nicht_bezeugt", _fremde_tabelle, "nicht die, die der", True),
    ("stichtag", _falscher_stichtag, "nichts bewegt", False),
    ("a_b2_bindung_spaet", _spaete_ab2_bindung, "anderen Stand", False),
    ("eingang_unlesbar", _eingang_unlesbar, "Eingang unlesbar", False),
]


@pytest.mark.parametrize("name,anpassen,muster,vorab", URSACHEN, ids=[u[0] for u in URSACHEN])
def test_eine_verweigerung_hinterlaesst_keinen_rest(
        tmp_path, monkeypatch, _testbetriebsschluessel, name, anpassen, muster, vorab):
    """Mutationsprobe: die Vorpruefung in neu_aufsetzen streichen -> die
    Ursachen vor dem Anlegen legen doch an (rot an ``angelegt``) bzw. den
    Rueckbau streichen -> die spaeten Ursachen lassen einen Rest."""
    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    kw = {"fall": _fall_mit_nebentabellen(tmp_path), "stichtag": STICHTAG,
          "_naht": _testbetriebsschluessel}
    anpassen(tmp_path, kw, monkeypatch)
    kw.pop("_naht")
    vorher, inhalt = _geschwister(ablage), _stand_der_ablage(ablage)
    angelegt: list = []
    echtes_mkdir = Path.mkdir

    def mkdir(self, *a, **k):
        if ".neu-" in self.as_posix():
            angelegt.append(self)
        return echtes_mkdir(self, *a, **k)

    monkeypatch.setattr(Path, "mkdir", mkdir)
    with pytest.raises((na.NeuaufsetzenError, ueb.UebernahmeError)) as fehler:
        na.neu_aufsetzen(ablage.wurzel, kw.pop("fall"), kw.pop("stichtag"), jetzt=JETZT, **kw)
    assert muster in str(fehler.value), str(fehler.value)
    monkeypatch.setattr(Path, "mkdir", echtes_mkdir)
    assert _geschwister(ablage) == vorher
    assert _stand_der_ablage(ablage) == inhalt
    assert (angelegt == []) is vorab, angelegt


def test_positivkontrolle_ohne_ursache_wird_aufgesetzt(tmp_path, _testbetriebsschluessel):
    ablage = _ablage(tmp_path / "daten")
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    fall = _fall_mit_nebentabellen(tmp_path)
    vorher = _geschwister(ablage)
    provenienz = na.neu_aufsetzen(ablage.wurzel, fall, STICHTAG, jetzt=JETZT)
    assert _geschwister(ablage) == sorted(vorher + [Path(provenienz["archiv"]).name])
    assert json.loads((ablage.wurzel / na.PROVENIENZ_DATEI).read_text())["fall"]


def test_die_vorpruefung_ist_dieselbe_funktion_wie_in_der_registrierung():
    """Eine Implementierung, zwei Aufrufer — sonst pruefte das Neuaufsetzen
    vorab etwas anderes, als die Registrierung danach verlangt."""
    import ast
    import inspect

    for name, quelle in (("eingang_anlegen", inspect.getsource(ueb.eingang_anlegen)),
                         ("neuaufsetzen", inspect.getsource(na))):
        baum = ast.parse(quelle.lstrip())
        rufe = [k for k in ast.walk(baum) if isinstance(k, ast.Call)
                and (getattr(k.func, "attr", None) or getattr(k.func, "id", None))
                == "registrierung_vorbedingungen"]
        assert len(rufe) == 1, name
