"""Aktuarielle Auswertungen der Fortschreibung — Werte aus dem stabilen Kern.

Per reporting date and contract this module pulls the calculated quantities
from the stable kernel in-process (:func:`Rechenkern.zustand_am` — the
decided standard path) and aggregates them into a per-Stichtag series for
the Bestandsbericht. It computes NOTHING actuarial of its own:

* Deckungskapital: ``kDRx_bpfl`` for premium-paying contracts; after a
  Beitragsfreistellung the paid-up reserve
  :func:`Rechenkern.reserve_beitragsfrei` (``VS_bfr(a0) * kVx_bfr(a)``).
* Rueckkaufswert: the row's ``RKW`` — premium-paying track only (the sheet
  defines no surrender rule for paid-up contracts, Stufe 1).
* Beitragsfreie Summe: ``VS_bfr`` fixed at the PEX year.

Efficiency follows the documented reuse convention: one
:class:`~rechner_pipeline.kern.Rechenkern` per contract, indexed per
Stichtag (its Verlaufszeilen are cached per instance).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.ereignisse import bestand_mit_historie
from rechner_pipeline.bestand.zeitscheibe import months_between, zeitscheibe
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import model_point_kwargs


def vertragswerte(
    kern: Rechenkern, months_exp: int, pex_jahr: Optional[int] = None
) -> Dict[str, Any]:
    """Aktuarielle Werte eines Vertrags am Stichtag (``months_exp`` volle Monate).

    ``pex_jahr`` ist das Vertragsjahr der Beitragsfreistellung (None =
    beitragspflichtig). Rueckkaufswert nur auf dem beitragspflichtigen Track;
    fuer beitragsfreie Vertraege ist er 0.0 (im Blatt nicht definiert).
    """
    jahr = int(months_exp) // 12
    if pex_jahr is None:
        zeile = kern.zustand_am(months_exp)
        return {
            "jahr": zeile.jahr,
            "status": "POL",
            "deckungskapital": zeile.drx_bpfl,
            "rueckkaufswert": zeile.rkw,
            "vs_bfr": 0.0,
        }
    return {
        "jahr": jahr,
        "status": "PEX",
        "deckungskapital": kern.reserve_beitragsfrei(pex_jahr, jahr),
        "rueckkaufswert": 0.0,
        "vs_bfr": kern.beitragsfreie_summe(pex_jahr),
    }


def _kerne_je_police(
    stamm: pd.DataFrame, config: BestandConfig
) -> Dict[int, Rechenkern]:
    generationen = {g.name: g.generation_fields() for g in config.generationen}
    kerne: Dict[int, Rechenkern] = {}
    for row in stamm.to_dict("records"):
        name = str(row["tarif_generation"])
        if name not in generationen:
            raise ValueError(
                f"police {row['police_id']}: Tarifgeneration {name!r} nicht in "
                f"Config (bekannt: {sorted(generationen)})"
            )
        kerne[int(row["police_id"])] = Rechenkern(
            ModelPoint(**model_point_kwargs(row, generationen[name]))
        )
    return kerne


def _pex_jahre(stamm: pd.DataFrame, historie: pd.DataFrame) -> Dict[int, int]:
    """police_id -> Vertragsjahr der Beitragsfreistellung (aus der Historie)."""
    pex = historie[historie["status_code"] == "PEX"]
    if len(pex) == 0:
        return {}
    starts = stamm.set_index("police_id")["insurance_start"]
    return {
        int(pid): months_between(starts.loc[pid].date(), datum.date()) // 12
        for pid, datum in zip(pex["police_id"], pex["status_date"])
    }


def auswertungs_verlauf(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtage: List[_dt.date],
) -> List[Dict[str, Any]]:
    """Aggregierte aktuarielle Kennzahlen je Stichtag (in-force-Bestand).

    ``historie`` darf None sein (reiner Basisbestand ohne Ereignisse) —
    dann sind alle Vertraege beitragspflichtig. Deterministisch: die
    Summationsreihenfolge folgt der Zeitscheiben-Sortierung.
    """
    if historie is not None and len(historie) > 0:
        sicht = bestand_mit_historie(stamm, historie)
        pex_jahre = _pex_jahre(stamm, historie)
    else:
        sicht = stamm
        pex_jahre = {}
    kerne = _kerne_je_police(stamm, config)

    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        scheibe = zeitscheibe(sicht, stichtag)
        agg: Dict[str, Any] = {
            "stichtag": stichtag.isoformat(),
            "vertraege": int(len(scheibe)),
            "deckungskapital": 0.0,
            "deckungskapital_bfr": 0.0,
            "rueckkaufswert": 0.0,
            "vs_bfr": 0.0,
        }
        for pid, months_exp, status in zip(
            scheibe["police_id"], scheibe["months_exp"], scheibe["status_code"]
        ):
            pex_jahr = None
            if status == "PEX":
                if int(pid) not in pex_jahre:
                    raise ValueError(
                        f"police {pid}: PEX-Status ohne PEX-Zeile in der Historie"
                    )
                pex_jahr = pex_jahre[int(pid)]
            werte = vertragswerte(kerne[int(pid)], int(months_exp), pex_jahr)
            agg["deckungskapital"] += werte["deckungskapital"]
            if werte["status"] == "PEX":
                agg["deckungskapital_bfr"] += werte["deckungskapital"]
                agg["vs_bfr"] += werte["vs_bfr"]
            else:
                agg["rueckkaufswert"] += werte["rueckkaufswert"]
        reihe.append(agg)
    return reihe
