"""Der Zielvertrag (ADR-030), Stufe 0: Version, Katalog, Wurzelprotokoll,
Konformitaet und der eine Anbieter.

Jede Regel der Konformitaet hat hier eine Positivkontrolle: eine
absichtlich falsche Implementierung, die genau diesen Befund ausloest.
Ohne sie waere "die PLV ist konform" ein Test, der nichts findet.

Knoten: system/zielsystem
"""

from __future__ import annotations

import pytest

from rechner_pipeline.plv.zielsystem import PLV
from rechner_pipeline.zielsystem import anbieter, konformitaet, version, vertrag


# --------------------------------------------------------------------------- #
# Version
# --------------------------------------------------------------------------- #

def test_die_vertragsversion_ist_dreistellig():
    assert version.zerlege(version.VERTRAG_VERSION) == (0, 1, 0)


@pytest.mark.parametrize("kaputt", ["1.2", "1.2.3.4", "a.b.c", "", "1.2.x", " 1.2.3"])
def test_keine_vertragsversion_ist_ein_fehler(kaputt):
    with pytest.raises(ValueError):
        version.zerlege(kaputt)


@pytest.mark.parametrize("angeboten, verlangt, erwartet", [
    ("0.1.0", "0.1.0", True),
    ("0.1.7", "0.1.0", True),      # dritte Zahl frei
    ("0.2.0", "0.1.0", False),     # andere Nebenversion: der Vertrag verlangt mehr oder weniger
    ("0.0.9", "0.1.0", False),
    ("1.1.0", "0.1.0", False),     # andere Hauptversion
])
def test_vertraeglich_heisst_gleiche_haupt_und_nebenversion(angeboten, verlangt, erwartet):
    assert version.vertraeglich(angeboten, verlangt) is erwartet


# --------------------------------------------------------------------------- #
# Katalog und Wurzelprotokoll
# --------------------------------------------------------------------------- #

def test_der_katalog_nennt_die_fuenf_gemessenen_faehigkeiten():
    assert set(vertrag.FAEHIGKEITEN) == {
        "rechnungsgrundlagen", "bestandsdaten", "bewertung", "zugang", "bestandspruefung",
    }
    assert all(beschreibung for beschreibung in vertrag.FAEHIGKEITEN.values())


def test_der_katalog_ist_unveraenderlich():
    with pytest.raises(TypeError):
        vertrag.FAEHIGKEITEN["neu"] = "x"  # type: ignore[index]
    with pytest.raises(TypeError):
        vertrag.PROTOKOLL_JE_FAEHIGKEIT["neu"] = object  # type: ignore[index]


def test_in_stufe_0_beschreibt_der_vertrag_noch_keine_faehigkeit():
    """Stufe 1 traegt rechnungsgrundlagen ein, Stufe 2 bewertung. Bis dahin
    darf niemand eine Faehigkeit anbieten (Konformitaet, unten)."""
    assert dict(vertrag.PROTOKOLL_JE_FAEHIGKEIT) == {}
    assert set(vertrag.PROTOKOLL_JE_FAEHIGKEIT) <= set(vertrag.FAEHIGKEITEN)


def test_das_wurzelprotokoll_ist_strukturell():
    """Eine Implementierung importiert nichts aus dem Tool, sie hat nur
    die Form (wie InputAdapter fuer die Quellen)."""
    assert isinstance(PLV(), vertrag.Zielsystem)

    class Fremd:
        name = "fremd"
        vertragsversion = "0.1.0"

        def faehigkeiten(self):
            return frozenset()

        def faehigkeit(self, name):
            raise KeyError(name)

    assert isinstance(Fremd(), vertrag.Zielsystem)
    assert not isinstance(object(), vertrag.Zielsystem)


# --------------------------------------------------------------------------- #
# Konformitaet: die PLV besteht, jede Regel hat eine Positivkontrolle
# --------------------------------------------------------------------------- #

def test_die_plv_ist_konform():
    assert konformitaet.pruefe(PLV()) == []


def test_der_anbieter_liefert_die_plv_und_sie_ist_konform():
    zs = anbieter.zielsystem()
    assert isinstance(zs, PLV)
    assert zs.name == "plv"
    assert konformitaet.pruefe(zs) == []


def _abart(**aenderungen):
    """Eine PLV mit absichtlich falschen Zuegen."""
    klasse = type("Abart", (PLV,), aenderungen)
    return klasse()


def test_ohne_wurzelprotokoll_nur_ein_befund():
    befunde = konformitaet.pruefe(object())
    assert len(befunde) == 1 and "Wurzelprotokoll Zielsystem nicht" in befunde[0]


@pytest.mark.parametrize("name", ["", "PLV", "plv-1", "1plv", 7])
def test_name_muss_eine_kennung_sein(name):
    befunde = konformitaet.pruefe(_abart(name=name))
    assert any("ist keine Kennung" in b for b in befunde), befunde


@pytest.mark.parametrize("v", ["0.1", "x", None, 1])
def test_vertragsversion_muss_eine_version_sein(v):
    befunde = konformitaet.pruefe(_abart(vertragsversion=v))
    assert any("ist keine Vertragsversion" in b for b in befunde), befunde


@pytest.mark.parametrize("v", ["0.2.0", "1.1.0", "0.0.1"])
def test_vertragsversion_muss_vertraeglich_sein(v):
    befunde = konformitaet.pruefe(_abart(vertragsversion=v))
    assert any("nicht vertraeglich" in b for b in befunde), befunde


def test_die_dritte_zahl_der_version_ist_frei():
    assert konformitaet.pruefe(_abart(vertragsversion="0.1.9")) == []


def test_faehigkeiten_muss_ein_frozenset_sein():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: set()))
    assert any("erwartet frozenset" in b for b in befunde), befunde


def test_unbekannte_faehigkeit_ist_ein_befund():
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"kaffee"})))
    assert any("unbekannte Faehigkeit 'kaffee'" in b for b in befunde), befunde


def test_faehigkeit_ohne_protokoll_darf_niemand_anbieten():
    """Stufe 0: der Vertrag beschreibt kein Protokoll; ein Zielsystem, das
    trotzdem 'bewertung' anbietet, behauptet etwas, das der Vertrag nicht
    prueft."""
    befunde = konformitaet.pruefe(_abart(faehigkeiten=lambda self: frozenset({"bewertung"})))
    assert any("beschreibt dafuer kein Protokoll" in b for b in befunde), befunde


def test_eine_nicht_angebotene_faehigkeit_darf_nicht_geliefert_werden():
    befunde = konformitaet.pruefe(_abart(faehigkeit=lambda self, name: object()))
    assert sorted(b for b in befunde if "obwohl es die Faehigkeit nicht anbietet" in b) == [
        f"liefert {n!r}, obwohl es die Faehigkeit nicht anbietet"
        for n in sorted(vertrag.FAEHIGKEITEN)
    ]


def test_angebotene_faehigkeit_wird_gegen_ihr_protokoll_geprueft(monkeypatch):
    """Die Mechanik der Stufen 1 und 2, hier mit einem Probeprotokoll:
    Angeboten und geliefert, aber nicht in der verlangten Form -> Befund;
    angeboten, aber KeyError -> Befund; in der Form -> kein Befund."""
    from types import MappingProxyType
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class Probe(Protocol):
        def wert(self) -> int: ...

    class Gut:
        def wert(self) -> int:
            return 1

    monkeypatch.setattr(
        konformitaet, "PROTOKOLL_JE_FAEHIGKEIT", MappingProxyType({"bewertung": Probe}))
    bietet = {"faehigkeiten": lambda self: frozenset({"bewertung"})}
    schlecht = konformitaet.pruefe(_abart(**bietet, faehigkeit=lambda self, n: object()))
    assert any("erfuellt das Protokoll Probe nicht" in b for b in schlecht), schlecht
    fehlt = konformitaet.pruefe(_abart(**bietet))
    assert any("liefert dafuer aber KeyError" in b for b in fehlt), fehlt
    gut = konformitaet.pruefe(_abart(
        **bietet, faehigkeit=lambda self, n: Gut() if n == "bewertung" else (_ for _ in ()).throw(KeyError(n))))
    assert gut == []


def test_die_plv_nennt_ihre_vertragsversion_selbst():
    """Kein Import der Konstante: Sonst waere die Vertraeglichkeit nie
    eine Pruefung. Die Quelle der PLV traegt die Version als Literal."""
    from pathlib import Path

    import rechner_pipeline.plv.zielsystem as modul

    quelle = Path(modul.__file__).read_text(encoding="utf-8")
    assert 'vertragsversion = "0.1.0"' in quelle
    assert "VERTRAG_VERSION" not in quelle
