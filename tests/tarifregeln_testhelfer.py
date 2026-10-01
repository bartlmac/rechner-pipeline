"""Testhelfer: eine Spez mit ANDEREN belegten Tarifregeln in einen Fall legen.

Seit dem Nachtrag zu ADR-024 tragen die Kommandos der Bestandsstrecke keine
Tarifschalter mehr; ein Test, der dieselbe Lieferung unter einer anderen
Regel faehrt (ein anderes Verfahren der Quelle, kein Abzug je Baustein),
legt dafuer eine Spez mit dieser Regel in den Fall. Das ist eine
ABSICHTLICHE Abweichung von der Fixture — eine Testeingabe, kein Beleg —
und geht deshalb nicht ueber den Weg der eingefrorenen Fixtures
(``spez.validierung.ergaenze_tarifregeln``), sondern ueber diese eine Stelle,
die jede Variante gegen den Lader und die Pflicht der Bestandsmigration
haelt.

Knoten: klv
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable

from rechner_pipeline.spez.schema import StrukturUrteil, TarifSpez, ZellSpez
from rechner_pipeline.spez.tarifregeln import tarifregeln_der_spez
from rechner_pipeline.spez.validierung import (
    lade_spez_aus_bytes,
    speichere_spez,
    spez_bytes,
    spez_pfad,
)

#: Die Tarifregeln eines synthetischen UEBERNOMMENEN Tarifs fuer Tests,
#: deren Gegenstand nicht die Regel ist. Bewusst nicht das Tarifwerk des
#: eigenen Geschaefts: Ein Test, der zufaellig mit der PLV-Vorgabe gruen
#: ist, saehe nicht, ob die Regel aus der Spez kommt.
TESTTARIF_TARIFWERK: Dict[str, Any] = {
    "scheiben_mit_gamma1": True, "stoab_je_baustein": True,
    "red_verfahren": "teilkuendigung", "tku_umfang": "grundversicherung",
}
TESTTARIF_QUELLVERFAHREN: Dict[str, Any] = {
    "red_verfahren": "teilkuendigung", "erhoehungssatz": 0.05,
    "dk_stichtag": "jahrestag", "formfunktion": "proportional_zur_basis",
}


def lege_spez(
    fall: Path,
    model_point: Dict[str, Any],
    *,
    generation: str = "klv/tg2015",
    tarifwerk: Dict[str, Any] | None = None,
    quellverfahren: Dict[str, Any] | None = None,
) -> Path:
    """Eine einzellige Spez mit belegten Tarifregeln in den Fall legen — fuer
    synthetische Faelle ohne A-Box (Uebernahme-Einheitstests)."""
    spez = TarifSpez(
        generation=generation, familie="klv",
        urteil=StrukturUrteil(ergebnis="parametrierung",
                              begruendung=["synthetische Testspez"]),
        tarifwerk=dict(TESTTARIF_TARIFWERK if tarifwerk is None else tarifwerk),
        quellverfahren=dict(TESTTARIF_QUELLVERFAHREN if quellverfahren is None
                            else quellverfahren),
        zellen=[ZellSpez(knoten=f"{generation}/zelle:-", model_point=dict(model_point))],
    )
    return speichere_spez(spez, fall)


def spez_variante(
    quelle: Path,
    fall: Path,
    generation: str,
    *,
    tarifwerk: Dict[str, Any] | None = None,
    quellverfahren: Dict[str, Any] | None = None,
    ohne: Iterable[str] = (),
    pruefen: bool = True,
) -> Path:
    """Die Spez ``quelle`` mit geaenderten Regeln als Spez des Falls ablegen.

    ``ohne``: Merkmale ``block.merkmal``, die in der Variante FEHLEN (fuer die
    Verweigerung). ``pruefen``: die Variante muss die Pflicht erfuellen —
    aus, wenn gerade eine unvollstaendige Spez gebraucht wird.
    """
    daten = json.loads(Path(quelle).read_bytes())
    daten["tarifwerk"] = {**daten.get("tarifwerk", {}), **(tarifwerk or {})}
    daten["quellverfahren"] = {**daten.get("quellverfahren", {}), **(quellverfahren or {})}
    for eintrag in ohne:
        block, merkmal = eintrag.split(".", 1)
        daten[block].pop(merkmal)
    roh = spez_bytes(daten)
    spez = lade_spez_aus_bytes(roh)
    if pruefen:
        tarifregeln_der_spez(spez)
    ziel = spez_pfad(fall, generation)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(roh)
    return ziel
