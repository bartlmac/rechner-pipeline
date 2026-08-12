"""Ereignis-Engine: Statushistorie der Fortschreibung (Storno/Tod/PEX/Ablauf).

The MUST building block of the stable-kernel paradigm (decision 2026-08-11):
the portfolio is rolled forward as a status history — the contract-level
state process — while every calculated amount (RKW, paid-up sum, benefits)
comes from the stable kernel in-process, never from formulas of this module.

Model (Stufe 1, annual):

* Simulation lattice: contract anniversaries (month-first dates, like all
  module dates). Policy year ``j`` spans anniversary ``j`` to ``j+1``; events
  of year ``j`` are booked at anniversary ``j+1`` — matching the kernel's
  Verlaufszeilen (``a`` = completed contract years).
* Per policy year, hierarchical competing risks on the active track:
  death (first-order qx of the tariff basis, scaled by ``tod_faktor``),
  then lapse (``storno_rate``, only while ``j+1 < n``), then paid-up
  conversion (``pex_rate``, only while premiums are still due, ``j+1 < t``).
  After PEX the contract stays exposed to death and maturity only (no lapse
  of paid-up contracts in Stufe 1 — the sheet defines no RKW_bfr rule).
* Amounts from the kernel: STO pays the row's RKW, PEX fixes the paid-up sum
  ``VS_bfr``, TOD pays the sum insured (or the paid-up sum after PEX), ABL
  pays the endowment benefit at ``insurance_end``.
* Determinism: one PCG64 substream per contract,
  ``SeedSequence([seed, EREIGNIS_STREAM, police_id])`` — adding contracts
  never shifts another contract's events, and extending the horizon ``bis``
  keeps all earlier events identical (consistent prefix).
* Draw contract (Common Random Numbers): per simulated policy year the draw
  order is FIXED and config-independent — death draw, then (premium-paying
  track) lapse draw while ``j+1 < n``, then PEX draw while ``j+1 < t``.
  Rates act only as thresholds; a rate of 0 still consumes its draw. Runs
  of different configs on the same portfolio are therefore pathwise
  comparable as long as their event histories agree (e.g. the lapse set at
  storno_rate=0.02 is a subset of the one at 0.03).

Outputs: a Statushistorie (follow-up status rows, schema
:data:`~rechner_pipeline.models.bestand.STATUS_HISTORIE_SPALTEN`) and an
Ereignis-Ledger with the kernel-computed amounts (schema
:data:`~rechner_pipeline.models.bestand.LEDGER_SPALTEN`).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Mapping, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    STAMM_NAMES,
    STATUS_HISTORIE_SPALTEN,
    model_point_kwargs,
)

#: SeedSequence-Konstante: separates event streams from the generator's
#: generation streams ([seed, gen_index]) — never reuse for other purposes.
#: Separation assumptions (SeedSequence normalizes trailing zeros, so
#: [seed, X] == [seed, X, 0]): police_id must be > 0 (enforced in
#: :func:`fortschreiben`; the generator issues >= 10_000_001) and gen_index
#: stays small — a third stream family needs a NEW distinct constant.
EREIGNIS_STREAM = 424242


class EreignisError(ValueError):
    """Raised when the portfolio and config do not fit the simulation."""


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _leere_frames() -> Tuple[pd.DataFrame, pd.DataFrame]:
    historie = pd.DataFrame(
        {name: pd.Series(dtype=dtype) for name, dtype in STATUS_HISTORIE_SPALTEN}
    )
    ledger = pd.DataFrame(
        {name: pd.Series(dtype=dtype) for name, dtype in LEDGER_SPALTEN}
    )
    return historie, ledger


def _simuliere_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    ereignisse,
    seed: int,
    bis: _dt.date,
) -> List[Dict[str, Any]]:
    """Simulate one contract; returns booked events (chronological)."""
    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    t = int(row["premium_duration"])
    x = int(row["entry_age"])
    vs = float(row["sum_insured"])

    kern = Rechenkern(ModelPoint(**model_point_kwargs(row, generation_fields)))
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, EREIGNIS_STREAM, police_id]))
    )

    events: List[Dict[str, Any]] = []

    def buche(code: str, jahr: int, art: str, betrag: float) -> None:
        events.append(
            {
                "police_id": police_id,
                "status_code": code,
                "vertragsjahr": jahr,
                "status_date": pd.Timestamp(_add_years(start, jahr)),
                "betrag_art": art,
                "betrag": float(betrag),
            }
        )

    beitragsfrei_ab: int | None = None
    horizont_erreicht = False

    for j in range(n):
        stichtag_jahr = _add_years(start, j + 1)
        if stichtag_jahr > bis:
            horizont_erreicht = True
            break

        # Feste Draw-Reihenfolge je Jahr (Raten sind nur Schwellen, siehe
        # Modul-Docstring): eine Rate von 0 verbraucht ihren Draw trotzdem —
        # sonst waeren Laeufe verschiedener Configs nicht pfadweise
        # vergleichbar (Common Random Numbers, Rate-0-Baseline).
        # 1. Tod im Vertragsjahr j (Tafel-qx der Tarifbasis, skaliert);
        #    bei tod_faktor 0 wird die Tafel nicht angefasst:
        if ereignisse.tod_faktor > 0.0:
            qx = min(1.0, kern.kom.qx_at(x + j) * ereignisse.tod_faktor)
        else:
            qx = 0.0
        if rng.random() < qx:
            if beitragsfrei_ab is None:
                buche("TOD", j + 1, "Todesfallleistung", vs)
            else:
                buche(
                    "TOD", j + 1, "Todesfallleistung",
                    kern.beitragsfreie_summe(beitragsfrei_ab),
                )
            return events

        if beitragsfrei_ab is None:
            # 2. Storno (nur beitragspflichtig, nicht im Ablaufjahr):
            if j + 1 < n and rng.random() < ereignisse.storno_rate:
                buche("STO", j + 1, "RKW", kern.verlaufszeile(j + 1).rkw)
                return events
            # 3. Beitragsfreistellung (nur solange Beitraege laufen):
            if j + 1 < t and rng.random() < ereignisse.pex_rate:
                beitragsfrei_ab = j + 1
                buche("PEX", j + 1, "VS_bfr", kern.beitragsfreie_summe(j + 1))

    if not horizont_erreicht:
        # Ablauf: alle n Jahre ueberlebt und insurance_end <= bis.
        if beitragsfrei_ab is None:
            buche("ABL", n, "Ablaufleistung", vs)
        else:
            buche("ABL", n, "Ablaufleistung", kern.beitragsfreie_summe(beitragsfrei_ab))
    return events


def fortschreiben(
    stamm: pd.DataFrame, config: BestandConfig, bis: _dt.date
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Roll the base portfolio forward to ``bis``: Statushistorie + Ledger.

    ``stamm`` is the generator's base portfolio (one POL row per contract);
    the event rates come from ``config.ereignisse``, the amounts from the
    stable kernel. Pure function of (stamm, config, bis) — seed-deterministic,
    the Stamm itself is never mutated. Fail-fast guards: only POL base rows
    (a Zeitscheibe or Historie view fed back in is an error — the engine
    would re-simulate it from insurance_start), unique positive police_id,
    valid event rates, durations within the sheet-anchored 0..50 range.
    """
    fehlend = [c for c in STAMM_NAMES if c not in stamm.columns]
    if fehlend:
        raise EreignisError(f"Stamm-Spalten fehlen: {fehlend}")
    konfig_fehler = config.ereignisse.validate()
    if konfig_fehler:
        raise EreignisError("; ".join(konfig_fehler))
    if len(stamm) and not (
        (stamm["status_code"] == "POL").all() & (stamm["status_id"] == 1).all()
    ):
        raise EreignisError(
            "Stamm ist kein Basisbestand (nur status_code POL mit status_id 1): "
            "Zeitscheiben oder Historie-Sichten koennen nicht erneut "
            "fortgeschrieben werden — die Engine simuliert ab insurance_start"
        )
    if stamm["police_id"].duplicated().any():
        raise EreignisError("police_id nicht eindeutig")
    if len(stamm) and int(stamm["police_id"].min()) <= 0:
        raise EreignisError("police_id <= 0 (Substream-Konvention verlangt > 0)")
    if len(stamm) and int(stamm["duration"].max()) > 50:
        raise EreignisError(
            "duration > 50: ausserhalb des blattfest verankerten "
            "Verlaufsbereichs des Kerns (Vertragsjahre 0..50)"
        )
    bis = pd.Timestamp(bis).date()
    generationen = {g.name: g.generation_fields() for g in config.generationen}

    alle_events: List[Dict[str, Any]] = []
    for row in stamm.to_dict("records"):
        name = str(row["tarif_generation"])
        if name not in generationen:
            raise EreignisError(
                f"police {row['police_id']}: Tarifgeneration {name!r} nicht in Config "
                f"(bekannt: {sorted(generationen)})"
            )
        try:
            alle_events.extend(
                _simuliere_vertrag(row, generationen[name], config.ereignisse,
                                   config.seed, bis)
            )
        except EreignisError:
            raise
        except Exception as exc:
            raise EreignisError(
                f"police {row['police_id']}: {type(exc).__name__}: {exc}"
            ) from exc

    if not alle_events:
        return _leere_frames()

    ereignisse = pd.DataFrame(alle_events).sort_values(
        ["police_id", "vertragsjahr"], kind="stable"
    )
    # status_id je Police fortlaufend ab 2 (Basis-POL im Stamm ist 1).
    ereignisse["status_id"] = ereignisse.groupby("police_id").cumcount() + 2

    generation_je_police = stamm.set_index("police_id")["tarif_generation"]
    historie = pd.DataFrame(
        {
            "police_id": ereignisse["police_id"].astype("int64"),
            "status_id": ereignisse["status_id"].astype("int64"),
            "status_code": ereignisse["status_code"].astype(object),
            "status_date": pd.to_datetime(ereignisse["status_date"]),
        }
    ).reset_index(drop=True)
    ledger = pd.DataFrame(
        {
            "police_id": ereignisse["police_id"].astype("int64"),
            "tarif_generation": ereignisse["police_id"]
            .map(generation_je_police)
            .astype(object),
            "ereignis": ereignisse["status_code"].astype(object),
            "vertragsjahr": ereignisse["vertragsjahr"].astype("int64"),
            "status_date": pd.to_datetime(ereignisse["status_date"]),
            "betrag_art": ereignisse["betrag_art"].astype(object),
            "betrag": ereignisse["betrag"].astype("float64"),
        }
    ).reset_index(drop=True)
    return historie, ledger


def bestand_mit_historie(
    stamm: pd.DataFrame, historie: pd.DataFrame
) -> pd.DataFrame:
    """DAV-style multi-row view: Stamm rows plus one row per history status.

    Every history row repeats its contract's Stamm columns byte-identically
    and replaces only ``status_id``/``status_code``/``status_date`` — exactly
    the shape the Zeitscheibe's youngest-status selection expects.
    """
    unbekannt = set(historie["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        raise EreignisError(
            f"historie: police_id unbekannt: {sorted(unbekannt)[:5]}"
        )
    if len(historie) == 0:
        return stamm.copy().reset_index(drop=True)

    stammdaten = stamm.drop(columns=["status_id", "status_code", "status_date"])
    folge = historie.merge(stammdaten, on="police_id", how="left", validate="m:1")
    beide = pd.concat([stamm, folge[list(STAMM_NAMES)]], ignore_index=True)
    return (
        beide.sort_values(["police_id", "status_id"], kind="stable")
        .reset_index(drop=True)[list(STAMM_NAMES)]
    )
