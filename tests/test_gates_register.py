"""Das Gate-Register bindet an den Code, der die Gates faehrt und erzwingt.

Knoten: system/assurance
"""

from __future__ import annotations

import json

import pytest

from rechner_pipeline.models import belegrollen
from rechner_pipeline.gates import (
    abnahmebericht, abox_merge, abox_validate, aktuartest, bestand_validate,
    extract, generation_golden, kernstand_belegen, register, tarifwerk_belegen,
)
from rechner_pipeline.models.zeichnung import GUELTIGE_GATES


def test_die_programmgates_des_registers_sind_die_konstanten_der_module():
    """Ein Gate-Modul, das seinen Namen aendert oder neu dazukommt, ohne
    dass das Register folgt, faellt hier — nicht erst auf der Seite."""
    im_code = {
        extract.GATE, abox_merge.GATE, abox_validate.GATE,
        generation_golden.GATE, bestand_validate.GATE, abnahmebericht.GATE,
        *aktuartest.GATES.values(),
        # Die Belegerzeuger der Standabnahme tragen den Namen ihres Gates.
        kernstand_belegen.GATE, tarifwerk_belegen.GATE,
    }
    # Reine Entscheid-Gates: Ihr Vorlagen-Erzeuger traegt keinen Gate-Namen
    # (Fallauftrag und Fallabbruch, Zugangsprobe, Anfangsbestand, Verweis der
    # T-Box) — ein Mensch zeichnet, die Maschine prueft nichts.
    im_register = {g.kennung_voll for g in register.REGISTER
                   if g.kennung not in ("A-Q1", "A-O1", "A-B1", "A-B2", "A-B3", "A-M5", "A-M6")}
    assert im_code == im_register


def test_die_abnahmen_des_registers_sind_die_zeichenbaren_gates():
    assert {g.kennung for g in register.REGISTER if g.art == "A"} == set(GUELTIGE_GATES)
    assert all(g.art in register.ART and g.gegenstand in register.GEGENSTAND
               for g in register.REGISTER)
    kennungen = [g.kennung for g in register.REGISTER]
    assert len(kennungen) == len(set(kennungen))


def test_die_vorgaenger_von_am4_kommen_aus_den_belegrollen(monkeypatch):
    """Behauptet wird nur, was models.belegrollen.BELEGROLLEN erzwingt. Mutationsprobe:
    eine neue Belegrolle ohne Zuordnung ist ein harter Fehler, kein
    stilles Weglassen."""
    # Seit der Standabnahme (ADR-018 Nachtrag 2026-10-01, ADR-025) gehoeren
    # die Abnahmen des Stands dazu: Kern (A-K2), T-Box (A-O1), Tarifwerk (A-T1).
    assert register.vorgaenger("A-M4", "tarif") == [
        "P-Q3", "A-Q1", "A-M1", "P-K1", "A-K2", "A-O1", "A-T1"]
    assert register.vorgaenger("A-M4", "bestand") == [
        "P-Q3", "A-Q1", "A-M1", "A-M2", "A-M3", "P-K1", "A-K2", "A-O1", "A-T1", "P-B1"]
    assert register.vorgaenger("A-M1", "bestand") == []
    mutiert = {**belegrollen.BELEGROLLEN, "A-M4": {"tarif": ("pq3_ledger", "neue_rolle"), "bestand": ()}}
    monkeypatch.setattr(register, "BELEGROLLEN", mutiert)
    with pytest.raises(register.RegisterFehler, match="neue_rolle"):
        register.vorgaenger("A-M4", "tarif")


def test_ausgabe_ist_vollstaendig_und_deterministisch(capsys):
    assert register.main(["--format", "markdown"]) == 0
    md = capsys.readouterr().out
    for g in register.REGISTER:
        assert f"**{g.kennung}** `{g.name}`" in md
    assert ("P-Q3, A-Q1, A-M1, P-K1, A-K2, A-O1, A-T1 / "
            "P-Q3, A-Q1, A-M1, A-M2, A-M3, P-K1, A-K2, A-O1, A-T1, P-B1") in md
    assert register.main(["--format", "json"]) == 0
    a = capsys.readouterr().out
    assert register.main(["--format", "json"]) == 0
    assert a == capsys.readouterr().out
    assert [d["kennung"] for d in json.loads(a)] == [g.kennung for g in register.REGISTER]
