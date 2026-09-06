"""Tarifplan-Generationentabellen sind erzeugt, und jede Generation hat ihren Referenzwert.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 5 und Block B6:
Der Tarifplan bekommt je Generation eine erzeugte Tabelle der
Rechnungsgrundlagen aus der Config (P7: erzeugt, nicht abgetippt) und
einen Abschnitt, was sich von Generation zu Generation aendert; der
Kern haelt je Generation einen Charakterisierungs-Referenzwert, damit
eine Parametrierung nicht still driftet.

Gebunden an den Systemstrang des Bestandsmoduls (Muster
``test_bestand_uebernommen_fortschreiben``): Gegenstand ist die Mechanik
"Tarifplan aus der Config" und die Vollstaendigkeit der Referenzwerte,
nicht die Tarifmathematik eines Produkts.

Knoten: system/bestand
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rechner_pipeline.bestand.config import load_config
from rechner_pipeline.bestand.tarifplan_tabellen import (
    block_in_datei,
    einsetzen,
    erzeuge_block,
    main,
)
from rechner_pipeline.models.bestand import BU_GENERATION_FIELDS, GENERATION_FIELDS

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG = "configs/bestand_gesamt.toml"
REFERENZWERTE = REPO_ROOT / "tests" / "fixtures" / "kern_referenzwerte"


@pytest.fixture(scope="module")
def config():
    return load_config(REPO_ROOT / CONFIG)


@pytest.mark.parametrize("produkt", ["klv", "bu"])
def test_tarifplan_block_ist_der_erzeugte(config, produkt):
    """P7-Drift-Schutz: Weicht der Block in der Datei vom Generator ab, ist
    der Tarifplan veraltet — neu erzeugen mit
    ``python -m rechner_pipeline.bestand.tarifplan_tabellen --config
    configs/bestand_gesamt.toml --produkt <produkt> --einsetzen
    docs/tarifplaene/<produkt>.md``."""
    doc = (REPO_ROOT / "docs" / "tarifplaene" / f"{produkt}.md").read_text("utf-8")
    ist = block_in_datei(doc)
    assert ist is not None, "Tarifplan traegt keinen erzeugten Block"
    soll = erzeuge_block(config, produkt, CONFIG)
    assert ist == soll, (
        f"docs/tarifplaene/{produkt}.md ist veraltet — Block neu erzeugen"
    )


def test_block_traegt_jede_generation_und_die_wechsel(config):
    klv = erzeuge_block(config, "klv", CONFIG)
    bu = erzeuge_block(config, "bu", CONFIG)
    for g in config.generationen:
        assert f"`{g.knoten}`" in (klv if g.produkt == "klv" else bu), g.knoten
    # Uebernommene Generation in Zellen: Zellentabelle statt einer Zeile.
    tg = next(g for g in config.generationen if g.zellen)
    assert f"Tarifzellen der übernommenen Generation **{tg.name}**" in klv
    assert "| nichtraucher/einzel | DAV2008_T_NR_U70 |" in klv
    assert "| raucher/kollektiv | DAV2008_T_R_U70 |" in klv
    # Wechsel: Zinssenkung von KLV-1994 auf KLV-2000, Tafelwechsel 2007 -> 2008.
    assert "| KLV-1994 → KLV-2000 | zins 4.00% → 3.25% |" in klv
    assert "| KLV-2007 → KLV-2008 | tafel DAV1994_T → DAV2008_T; policy_fee 24 → 30 |" in klv
    assert "| KLV-2022 → KLV-2025 | zins 0.25% → 1.00% |" in klv
    assert "| BU-2017 → BU-2025 | zins 0.90% → 1.00% |" in bu
    # Vertrieb: Batch, Jahresziel mit Trend, uebernommen.
    assert "| Batch 600 |" in klv
    assert "Neugeschäft 120/Jahr, Trend -4%/Jahr" in klv
    assert "übernommen" in klv


def test_einsetzen_ersetzt_genau_den_block(config, tmp_path):
    block = erzeuge_block(config, "bu", CONFIG)
    text = "# 13 Titel\n\nProsa davor.\n\n" + block + "\nProsa danach.\n"
    neu = einsetzen(text, block.replace("| Batch 500 |", "| Batch 501 |"))
    assert "Batch 501" in neu and "Prosa davor." in neu and "Prosa danach." in neu
    assert block_in_datei(neu) == block.replace("| Batch 500 |", "| Batch 501 |")
    with pytest.raises(ValueError, match="keinen erzeugten Block"):
        einsetzen("nur Prosa", block)
    pfad = tmp_path / "bu.md"
    pfad.write_text(text, encoding="utf-8")
    assert main(["--config", CONFIG, "--produkt", "bu", "--einsetzen", str(pfad)]) == 0
    assert block_in_datei(pfad.read_text("utf-8")) == block
    assert main(["--config", str(tmp_path / "fehlt.toml"), "--produkt", "bu"]) == 2


def test_jede_generation_hat_einen_referenzwert_auf_ihren_grundlagen(config):
    """Kern-Abnahmeprotokoll je Generation: Der eingefrorene Modellpunkt
    traegt genau die Rechnungsgrundlagen der Config. Aendert jemand die
    Config, muss er den Referenzwert bewusst neu einfrieren — die
    Parametrierung driftet nicht still.

    Mutationsprobe: zins einer Generation in der Config aendern — dann
    weicht der Modellpunkt der Referenz ab (hier), und berechne() liefert
    andere Werte (test_kern)."""
    for g in config.generationen:
        pfad = REFERENZWERTE / ("referenz_plv_" + g.knoten.replace("/", "_") + ".json")
        assert pfad.is_file(), f"Referenzwert fehlt: {pfad.name}"
        daten = json.loads(pfad.read_text("utf-8"))
        assert daten["produkt"] == g.produkt and daten["knoten"] == g.knoten
        mp = daten["model_point"]
        if g.produkt == "bu":
            erwartet = {f: getattr(g, f) for f in BU_GENERATION_FIELDS}
            erwartet["zins"] = g.zins
        elif g.zellen:
            erwartet = g.felder_fuer({"status": "nichtraucher", "tarifart": "einzel"})
        else:
            erwartet = g.generation_fields()
        for name, wert in erwartet.items():
            assert mp[name] == wert, (g.name, name, mp[name], wert)
        assert "ergebnis" in daten and daten["ergebnis"]
