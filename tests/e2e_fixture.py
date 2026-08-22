"""Materialisierung des versionierten O3-/G-2-Pflicht-Fixtures.

Das eingecheckte Fixture traegt fachliche Eingaben und unabhaengige
Erwartungswerte. Laufartefakte entstehen dagegen fuer jeden Test neu unter
``tmp_path``: so prueft der E2E-Pfad echte Registrierung und Extraktion, ohne
einen gitignorierten Fall-Arbeitsbereich als versteckte Vorbedingung zu haben.

Knoten: klv/tg2012
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from rechner_pipeline.fall import anlegen, registrieren
from rechner_pipeline.gates.extract import main as extract
from rechner_pipeline.ontologie.abox import speichere
from rechner_pipeline.ontologie.aussage import Provenienz, belegt
from rechner_pipeline.ontologie.tbox import (
    ABox,
    BEKANNTE_PARAMETER,
    Parametrierungszelle,
    Quelle,
    Tarifgeneration,
)
from rechner_pipeline.quellen.vorverdichtung import verzeichnis_der_generation
from rechner_pipeline.spez.erzeugen import baue_spez
from rechner_pipeline.spez.validierung import speichere_spez

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PFAD = REPO_ROOT / "tests" / "fixtures" / "o3_g2_minimal" / "fixture.json"
O3_GENERATION = "klv/tg2012"


@dataclass(frozen=True)
class O3Fixture:
    """Validierte, unveraenderliche Sicht auf die versionierten Testdaten."""

    fall: str
    generation: str
    quelle: Path
    quelle_sha256: str
    parameter: dict[str, Any]
    akteur: str
    erhoben_am: str
    fundstelle_parameter: str
    fundstelle_ratzu: str
    erwartung: dict[str, Any]


def lade_o3_fixture() -> O3Fixture:
    """Fixture laden und seine Vollstaendigkeit an der Dateigrenze pruefen."""
    if not FIXTURE_PFAD.is_file():
        raise AssertionError(
            f"versioniertes O3-/G-2-Pflicht-Fixture fehlt: {FIXTURE_PFAD}"
        )
    roh = json.loads(FIXTURE_PFAD.read_text(encoding="utf-8"))
    if roh.get("schema_version") != 1:
        raise AssertionError("O3-/G-2-Fixture hat nicht schema_version 1")
    if roh.get("generation") != O3_GENERATION:
        raise AssertionError(
            f"O3-/G-2-Fixture muss {O3_GENERATION!r} beschreiben"
        )

    parameter = roh.get("parameter")
    if not isinstance(parameter, dict):
        raise AssertionError("O3-/G-2-Fixture ohne Parameterobjekt")
    if set(parameter) != set(BEKANNTE_PARAMETER):
        raise AssertionError(
            "O3-/G-2-Fixture deckt den Parametervertrag nicht exakt: "
            f"erwartet {sorted(BEKANNTE_PARAMETER)}, gefunden "
            f"{sorted(parameter)}"
        )

    quelle_daten = roh.get("quelle", {})
    quelle = (FIXTURE_PFAD.parent / quelle_daten.get("datei", "")).resolve()
    if not quelle.is_file():
        raise AssertionError(f"Quelle des O3-/G-2-Fixtures fehlt: {quelle}")
    ist_hash = sha256(quelle.read_bytes()).hexdigest()
    if ist_hash != quelle_daten.get("sha256"):
        raise AssertionError(
            "Quelle des O3-/G-2-Fixtures weicht vom versionierten SHA-256 ab: "
            f"{ist_hash}"
        )

    provenienz = roh.get("provenienz", {})
    erwartung = roh.get("erwartung")
    if not isinstance(erwartung, dict):
        raise AssertionError("O3-/G-2-Fixture ohne Erwartungsobjekt")
    return O3Fixture(
        fall=str(roh["fall"]),
        generation=str(roh["generation"]),
        quelle=quelle,
        quelle_sha256=ist_hash,
        parameter=dict(parameter),
        akteur=str(provenienz["akteur"]),
        erhoben_am=str(provenienz["erhoben_am"]),
        fundstelle_parameter=str(provenienz["fundstelle_parameter"]),
        fundstelle_ratzu=str(provenienz["fundstelle_ratzu"]),
        erwartung=dict(erwartung),
    )


def _generation(
    generation: str,
    quelle: Quelle,
    fixture: O3Fixture,
) -> Tarifgeneration:
    parameter = {}
    for feld, wert in sorted(fixture.parameter.items()):
        fundstelle = (
            fixture.fundstelle_ratzu
            if feld.startswith("ratzu_zw")
            else fixture.fundstelle_parameter
        )
        provenienz = Provenienz(
            quelle_datei=quelle.datei,
            quelle_sha256=quelle.sha256,
            fundstelle=fundstelle,
            akteur=fixture.akteur,
            erhoben_am=fixture.erhoben_am,
        )
        parameter[feld] = belegt(wert, [provenienz])

    name = generation.rsplit("/", 1)[-1].upper()
    return Tarifgeneration(
        id=generation,
        name=name,
        familie="klv",
        quellen=[quelle],
        zellen=[Parametrierungszelle(id="zelle:-", parameter=parameter)],
    )


def bereite_o3_fall(
    tmp_path: Path,
    generationen: tuple[str, ...] = (O3_GENERATION,),
    *,
    scope: str = "tarif",
) -> Path:
    """Das Fixture ueber echte Registrierung und Extraktion materialisieren."""
    fixture = lade_o3_fixture()
    if fixture.generation not in generationen:
        raise AssertionError(
            f"Fixture-Generation {fixture.generation!r} fehlt in {generationen!r}"
        )

    fall = tmp_path / "fall"
    anlegen(fall, scope=scope)
    registrieren(fall, fixture.quelle)
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    eintrag = next(
        quelle
        for quelle in register["quellen"]
        if quelle["datei"] == fixture.quelle.name
    )
    if eintrag["sha256"] != fixture.quelle_sha256:
        raise AssertionError("Registrierung hat den Fixture-Quellhash veraendert")
    quelle = Quelle(
        datei=eintrag["datei"],
        sha256=eintrag["sha256"],
        art="tarifrechner",
    )

    vorverdichtung = verzeichnis_der_generation(fall, fixture.generation)
    extraktion = extract([
        "--repo-root", str(REPO_ROOT),
        "--input", str(fall / "eingang" / quelle.datei),
        "--out-dir", str(vorverdichtung),
        "--adapter", "excel",
        "--export-backend", "openpyxl",
    ])
    if extraktion.exit_code != 0:
        raise AssertionError(
            f"Fixture-Extraktion scheitert: {extraktion.errors!r}"
        )

    abox = ABox(
        fall=fixture.fall,
        generationen=[
            _generation(generation, quelle, fixture)
            for generation in generationen
        ],
    )
    speichere(abox, fall)
    speichere_spez(baue_spez(abox, fixture.generation), fall)
    return fall
