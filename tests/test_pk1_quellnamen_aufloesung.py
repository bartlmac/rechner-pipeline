"""P-K1: Beispiel-Modellpunkt aus fremd benannten Names-Manager-Eintraegen.

Die Namen der Eingabezellen (x, VS, Geschlecht, Merkmale) sind eine
Konvention des QUELLSYSTEMS. Die erste Lieferung hiess sie Sex/Status/
Tarifart, die zweite GESCHL/RK/BGRP — das Gate darf an keiner von beiden
kleben, sondern loest ueber die ``quellnamen`` der A-Box auf und faellt
ohne Zuordnung auf die Namen der Erst-Lieferung zurueck (Fixtures).

Knoten: klv
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import pytest

from rechner_pipeline.gates.generation_golden import (
    _dimensions_auspraegungen,
    _modellpunkt_eingaben,
    _quellname_fuer,
    _waehle_zelle,
)


@dataclass
class _Zelle:
    auspraegungen: Dict[str, str] = field(default_factory=dict)


@dataclass
class _Spez:
    zellen: List[_Zelle] = field(default_factory=list)


LEGACY_NAMEN = {
    "x": "45", "n": "30", "t": "20", "VS": "100000", "zw": "12",
    "Sex": "M", "Status": "Nichtraucher", "Tarifart": "Einzel",
}

TG2015_NAMEN = {
    "x": "45", "n": "30", "t": "20", "VS": "100000", "zw": "12",
    "GESCHL": "U70", "RK": "Nichtraucher", "BGRP": "Einzel",
}

TG2015_QUELLNAMEN = {
    "GESCHL": "eingabe:geschlecht",
    "RK": "dimension:status",
    "Status": "dimension:status",
    "BGRP": "dimension:tarifart",
    "Tarifart": "dimension:tarifart",
    # Wert-Eintraege duerfen NICHT als Namenskandidaten gelten:
    "Einzel": "dimension:tarifart=einzel",
    "Raucher": "dimension:status=raucher",
}

SPEZ = _Spez(zellen=[
    _Zelle({"status": "nichtraucher", "tarifart": "einzel"}),
    _Zelle({"status": "raucher", "tarifart": "einzel"}),
])


def test_erstlieferungs_namen_gelten_ohne_quellnamen_weiter():
    eingaben = _modellpunkt_eingaben(LEGACY_NAMEN)
    assert eingaben["x"] == 45 and eingaben["sex_roh"] == "M"
    auspraegungen = _dimensions_auspraegungen(SPEZ, LEGACY_NAMEN)
    assert auspraegungen == {"status": "Nichtraucher", "tarifart": "Einzel"}
    zelle = _waehle_zelle(SPEZ, auspraegungen)
    assert zelle.auspraegungen == {"status": "nichtraucher",
                                   "tarifart": "einzel"}


def test_fremde_namen_werden_ueber_quellnamen_aufgeloest():
    eingaben = _modellpunkt_eingaben(TG2015_NAMEN, TG2015_QUELLNAMEN)
    assert eingaben["sex_roh"] == "U70"
    auspraegungen = _dimensions_auspraegungen(
        SPEZ, TG2015_NAMEN, TG2015_QUELLNAMEN)
    assert auspraegungen == {"status": "Nichtraucher", "tarifart": "Einzel"}


def test_wert_eintraege_sind_keine_namenskandidaten():
    # "Einzel": "dimension:tarifart=einzel" existiert im Names-Manager
    # NICHT als Zelle — und selbst wenn, traefe der Semantik-Schluessel
    # "dimension:tarifart" ihn nicht (exakte Token-Gleichheit).
    namen = dict(TG2015_NAMEN)
    namen["Einzel"] = "irgendwas"
    name = _quellname_fuer(
        "dimension:tarifart", TG2015_QUELLNAMEN, namen, rueckfall="Tarifart")
    assert name == "BGRP"


def test_mehrdeutige_zuordnung_mit_verschiedenen_werten_faellt_hart():
    namen = dict(TG2015_NAMEN)
    namen["Status"] = "Raucher"        # RK sagt Nichtraucher, Status Raucher
    with pytest.raises(ValueError, match="mehrdeutig"):
        _quellname_fuer(
            "dimension:status", TG2015_QUELLNAMEN, namen, rueckfall="Status")


def test_gleiche_werte_mehrerer_kandidaten_sind_eindeutig():
    namen = dict(TG2015_NAMEN)
    namen["Status"] = "Nichtraucher"   # beide Kandidaten, ein Wert
    name = _quellname_fuer(
        "dimension:status", TG2015_QUELLNAMEN, namen, rueckfall="Status")
    assert namen[name] == "Nichtraucher"


def test_fehlende_pflicht_eingabe_faellt_auf_erstlieferungsnamen_und_hart():
    # Ohne existierenden Kandidaten greift der Rueckfall-Name; fehlt auch
    # der, ist es ein harter Fehler, der den Aufloesungsweg nennt.
    namen = dict(TG2015_NAMEN)
    del namen["GESCHL"]
    with pytest.raises(ValueError, match="Sex.*quellnamen"):
        _modellpunkt_eingaben(namen, TG2015_QUELLNAMEN)


def test_ohne_passende_zelle_faellt_die_wahl_hart():
    with pytest.raises(ValueError, match="keine Spez-Zelle"):
        _waehle_zelle(SPEZ, {"status": "Raucher", "tarifart": "Haus"})
