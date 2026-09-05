"""Erzeugte Generationentabellen der Tarifplaene — P7: erzeugt, nicht abgetippt.

Der Tarifplan eines Produkts (``docs/tarifplaene/<produkt>.md``, Paragraf
13) beschreibt die Bestandsgenerationen der PLV. Bis zum Tagesbetrieb
stand die Tabelle handgeschrieben da und wurde zeilenweise gegen die
Config gehalten; mit den Generationen bis heute, den Uebernahmen in
Tarifzellen und den Verkaufsregeln (Fachkonzept
docs/simulation/tagesbetrieb.md, Abschnitt 5) wird sie ERZEUGT: aus der
Bestand-Config, in genau einem Markdown-Block, den ein Test gegen den
Generator haelt. Was der Tarifplan ueber die Generationen behauptet,
ist damit dasselbe, was der Bestand rechnet.

Drei Tabellen je Produkt:

* die Generationen mit ihren Rechnungsgrundlagen und ihrem Vertrieb
  (Batch-Stichprobe, Jahresziel mit Trend, uebernommen);
* je Generation in Tarifzellen (uebernommene Bestaende) die Zellen mit
  ihren abweichenden Grundlagen;
* was sich von Generation zu Generation aendert — die Felder, die
  zwischen zwei aufeinanderfolgenden Generationen einen anderen Wert
  tragen. Ein Generationenwechsel ist genau diese Liste.

Run via::

    python -m rechner_pipeline.bestand.tarifplan_tabellen \\
        --config configs/bestand_gesamt.toml --produkt klv

Der Block beginnt mit ``<!-- erzeugt: ... -->`` und endet mit
``<!-- /erzeugt -->``; ``--einsetzen docs/tarifplaene/klv.md`` ersetzt
den Block in der Datei.

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from rechner_pipeline.bestand.config import BestandConfig, TarifGeneration, load_config
from rechner_pipeline.models.bestand import BU_GENERATION_FIELDS, GENERATION_FIELDS

MARKER_ANFANG = "<!-- erzeugt: python -m rechner_pipeline.bestand.tarifplan_tabellen --config {config} --produkt {produkt} -->"
MARKER_ENDE = "<!-- /erzeugt -->"
_BLOCK = re.compile(
    r"<!-- erzeugt: python -m rechner_pipeline\.bestand\.tarifplan_tabellen[^\n]*-->\n.*?<!-- /erzeugt -->",
    re.DOTALL,
)

#: Kernfelder je Produkt in Tabellenreihenfolge (fuer die Wechsel-Tabelle).
_FELDER = {
    "klv": GENERATION_FIELDS,
    "bu": ("zins",) + tuple(BU_GENERATION_FIELDS) if "zins" not in BU_GENERATION_FIELDS
    else tuple(BU_GENERATION_FIELDS),
}


def _wert(name: str, wert: Any) -> str:
    if name == "zins":
        return f"{float(wert):.2%}"
    if isinstance(wert, float):
        return f"{wert:g}" if name not in ("policy_fee",) else f"{wert:.0f}"
    return str(wert)


def _vertrieb(gen: TarifGeneration) -> str:
    teile: List[str] = []
    if gen.sample_size > 0:
        teile.append(f"Batch {gen.sample_size}")
    if gen.neuzugang_pro_jahr > 0:
        trend = (
            f", Trend {gen.neuzugang_trend:+.0%}/Jahr" if gen.neuzugang_trend else ""
        )
        teile.append(f"Neugeschäft {gen.neuzugang_pro_jahr}/Jahr{trend}")
    if not teile:
        teile.append("übernommen")
    return "; ".join(teile)


def _zeile_klv(g: TarifGeneration) -> str:
    return (
        f"| `{g.knoten}` | {g.name} | "
        f"{g.gueltig_von:%Y-%m}–{g.gueltig_bis:%Y-%m} | "
        f"{g.zins:.2%} | {g.tafel} | {g.alpha} | {g.beta1} | "
        f"{g.gamma1}/{g.gamma2}/{g.gamma3} | {g.policy_fee:.0f} | {_vertrieb(g)} |"
    )


def _zeile_bu(g: TarifGeneration) -> str:
    return (
        f"| `{g.knoten}` | {g.name} | "
        f"{g.gueltig_von:%Y-%m}–{g.gueltig_bis:%Y-%m} | "
        f"{g.zins:.2%} | {g.tafel_aktiv}/{g.tafel_i}/"
        f"{g.tafel_ri}/{g.tafel_ti} | {g.zuschlag} | {_vertrieb(g)} |"
    )


def _zellen_tabelle(g: TarifGeneration) -> List[str]:
    dims = list(g.dimensionen())
    zeilen = [
        "",
        f"Tarifzellen der übernommenen Generation **{g.name}** (`{g.knoten}`, "
        f"Rechnungszins {g.zins:.2%}, Zellen über {' × '.join(f'`{d}`' for d in dims)}; "
        "je Zelle nur die vom Rumpf abweichenden Felder):",
        "",
        "| Zelle | Tafel | $\\alpha$ | $\\beta_1$ | $\\gamma_{1/2}$ | $\\kappa$ | StoAb Satz/min/max | Ratenzuschlag zw2/4/12 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for zelle in g.zellen:
        f = {**g.generation_fields(), **zelle.felder}
        name = "/".join(str(zelle.auspraegungen[d]) for d in dims)
        zeilen.append(
            f"| {name} | {f['tafel']} | {f['alpha']} | {f['beta1']} | "
            f"{f['gamma1']}/{f['gamma2']} | {float(f['policy_fee']):.0f} | "
            f"{f['stoab_satz']}/{f['stoab_min']}/{f['stoab_max']} | "
            f"{f['ratzu_zw2']}/{f['ratzu_zw4']}/{f['ratzu_zw12']} |"
        )
    return zeilen


def _wechsel(gens: Sequence[TarifGeneration], produkt: str) -> List[str]:
    felder = _FELDER[produkt]
    zeilen = [
        "",
        "Was sich von Generation zu Generation ändert (verkaufende Generationen "
        "in Verkaufsreihenfolge; leer heißt: nur das Fenster):",
        "",
        "| Wechsel | geänderte Rechnungsgrundlagen |",
        "|---|---|",
    ]
    verkaufend = [g for g in gens if g.sample_size > 0 or g.neuzugang_pro_jahr > 0]
    for vorher, danach in zip(verkaufend, verkaufend[1:]):
        a = {**vorher.generation_fields(), **vorher.bu_generation_fields()}
        b = {**danach.generation_fields(), **danach.bu_generation_fields()}
        unterschiede = [
            f"{name} {_wert(name, a[name])} → {_wert(name, b[name])}"
            for name in felder if a.get(name) != b.get(name)
        ]
        zeilen.append(
            f"| {vorher.name} → {danach.name} | {'; '.join(unterschiede) or '—'} |"
        )
    return zeilen


def erzeuge_block(config: BestandConfig, produkt: str, config_pfad: str) -> str:
    """Den Markdown-Block fuer Paragraf 13 des Tarifplans erzeugen."""
    gens = sorted(
        (g for g in config.generationen if g.produkt == produkt),
        key=lambda g: (g.gueltig_von, g.name),
    )
    if not gens:
        raise ValueError(f"keine Generation mit produkt {produkt!r} in {config_pfad}")
    zeilen = [MARKER_ANFANG.format(config=config_pfad, produkt=produkt)]
    if produkt == "klv":
        zeilen += [
            "| Knoten | Name | gültig | Zins | Tafel | $\\alpha$ | $\\beta_1$ | $\\gamma_{1/2/3}$ | $\\kappa$ | Vertrieb |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        zeilen += [_zeile_klv(g) for g in gens if not g.zellen]
        for g in gens:
            if g.zellen:
                zeilen += _zellen_tabelle(g)
    else:
        zeilen += [
            "| Knoten | Name | gültig | Zins | Tafeln (aktiv/i/ri/ti) | Zuschlag | Vertrieb |",
            "|---|---|---|---|---|---|---|",
        ]
        zeilen += [_zeile_bu(g) for g in gens]
    zeilen += _wechsel(gens, produkt)
    zeilen.append(MARKER_ENDE)
    return "\n".join(zeilen) + "\n"


def block_in_datei(text: str) -> Optional[str]:
    """Den erzeugten Block einer Tarifplan-Datei finden (None = keiner)."""
    treffer = _BLOCK.search(text)
    return treffer.group(0) + "\n" if treffer else None


def einsetzen(text: str, block: str) -> str:
    """Den vorhandenen Block ersetzen — ohne Block ist die Datei kein Ziel."""
    if block_in_datei(text) is None:
        raise ValueError(
            "Tarifplan traegt keinen erzeugten Block (<!-- erzeugt: ... --> ... "
            "<!-- /erzeugt -->) — die Marker einmal von Hand setzen"
        )
    return _BLOCK.sub(lambda _m: block.rstrip("\n"), text, count=1)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.bestand.tarifplan_tabellen",
        description="Generationentabellen eines Tarifplans aus der Bestand-Config erzeugen.",
    )
    parser.add_argument("--config", required=True, help="Bestand-Config (TOML).")
    parser.add_argument("--produkt", required=True, choices=("klv", "bu"))
    parser.add_argument(
        "--einsetzen", default=None,
        help="Tarifplan-Datei, deren erzeugter Block ersetzt wird (sonst: stdout).",
    )
    ns = parser.parse_args(argv)
    try:
        config = load_config(Path(ns.config))
    except (OSError, ValueError) as exc:
        print(f"tarifplan_tabellen: {exc}", file=sys.stderr)
        return 2
    fehler = config.validate()
    if fehler:
        print(f"tarifplan_tabellen: Config ungueltig: {'; '.join(fehler)}", file=sys.stderr)
        return 2
    block = erzeuge_block(config, ns.produkt, ns.config)
    if ns.einsetzen:
        pfad = Path(ns.einsetzen)
        try:
            neu = einsetzen(pfad.read_text(encoding="utf-8"), block)
        except (OSError, ValueError) as exc:
            print(f"tarifplan_tabellen: {exc}", file=sys.stderr)
            return 2
        pfad.write_text(neu, encoding="utf-8")
        print(f"tarifplan_tabellen: Block in {pfad} erneuert", file=sys.stderr)
        return 0
    sys.stdout.write(block)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
