"""Zwei Bestands-Stichtage brauchen einen Jahreswechsel (Entscheid des
Maintainers 2026-09-07 zu Review T23-05).

A-M4 verlangt im Bestands-Scope ein ausgewiesenes Bewegungsjahr; das
Bewegungskonto weist nur vollstaendige Kalenderjahre aus. Zwei Stichtage im
selben Kalenderjahr koennen das strukturell nicht erfuellen — der Fall-Scope
sagt es am Eingang (fail-fast), nicht erst A-M4 mit einem Zaehlerbefund.

Knoten: system/bestand
"""

from __future__ import annotations

import datetime as dt

import pytest

from rechner_pipeline.gates._fall_scope import stichtage_fehler, validate_scope_bindung


@pytest.mark.parametrize("erster, zweiter", [
    ("2026-01-01", "2027-01-01"),   # der Regelfall (Baldrian, E2E)
    ("2026-03-01", "2027-01-01"),   # unterjaehrige Uebernahme, Horizont am Jahreswechsel
    ("2026-12-31", "2027-01-01"),   # knappster zulaessiger Abstand
    ("2026-01-01", "2028-06-30"),   # mehr als ein Jahr
])
def test_stichtage_mit_jahreswechsel_sind_zulaessig(erster, zweiter):
    assert stichtage_fehler(dt.date.fromisoformat(erster), dt.date.fromisoformat(zweiter)) is None


@pytest.mark.parametrize("erster, zweiter, stichwort", [
    ("2026-01-01", "2026-07-01", "1. Januar des Folgejahres"),   # der merge-session-Fall
    ("2026-01-01", "2026-12-31", "1. Januar des Folgejahres"),   # ein Tag zu frueh
    ("2026-07-01", "2026-07-01", "nach Stichtag 1"),             # gleich
    ("2027-01-01", "2026-01-01", "nach Stichtag 1"),             # rueckwaerts
])
def test_stichtage_ohne_jahreswechsel_werden_abgewiesen(erster, zweiter, stichwort):
    fehler = stichtage_fehler(dt.date.fromisoformat(erster), dt.date.fromisoformat(zweiter))
    assert fehler and stichwort in fehler, fehler


def test_persistierte_bindung_haelt_dieselbe_regel():
    """Eine gespeicherte Bindung mit zwei Stichtagen im selben Jahr ist
    ungueltig — dieselbe Regel, nicht nur beim Erzeugen."""
    basis = {
        "scope": "bestand", "eingang_sha256": "0" * 64, "abox_sha256": "1" * 64,
        "system": {"commit": "abc", "branch": "x", "dirty": False, "quellcode_sha256": "2" * 64},
    }
    ok = validate_scope_bindung({**basis, "stichtage": ["2026-01-01", "2027-01-01"]})
    assert not any("stichtage" in f for f in ok), ok
    zu_kurz = validate_scope_bindung({**basis, "stichtage": ["2026-01-01", "2026-07-01"]})
    assert any("1. Januar des Folgejahres" in f for f in zu_kurz), zu_kurz
