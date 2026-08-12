"""Seed-deterministic portfolio generator (Bestandsaufbau, Stufe 1: KLV).

Draws contract attributes per tariff generation — marginals and pairwise
Spearman correlations from the TOML config, dependence via Gaussian copula
(:mod:`rechner_pipeline.bestand.stochastik`) — and assembles the canonical
portfolio DataFrame (:mod:`rechner_pipeline.models.bestand`).

The generator computes NOTHING actuarial: no premiums, no present values, no
reserves (project decision — calculated quantities come from the stable
kernel via :func:`rechner_pipeline.bestand.kernlauf.berechne_vertrag`).

Determinism: one master seed from the config; every generation draws from its
own child stream ``PCG64(SeedSequence([seed, generation_index]))``, so adding
a generation never changes the contracts of earlier generations.

Seed discipline: NEVER seed anything with the bare master seed —
``SeedSequence(seed)`` is bit-identical to ``SeedSequence([seed, 0])``
(trailing-zero normalization), i.e. the stream of generation 0. New stream
families need their own distinct constant (Neuzugang: ``NEUZUGANG_STREAM``,
Ereignis-Engine: 424242).
"""

from __future__ import annotations

import datetime as _dt
from typing import Dict, List

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig, TarifGeneration
from rechner_pipeline.bestand.stochastik import (
    build_corr_matrix,
    correlated_uniforms,
    transform,
)
from rechner_pipeline.models.bestand import STAMM_NAMES, STAMM_SPALTEN, stamm_dtypes

#: Fixed draw order of copula columns — part of the determinism contract.
COPULA_ORDER = ("entry_age", "sex", "duration", "premium_duration", "sum_insured")


def _month_first(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, 1)


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _draw_insurance_start(
    rng: np.random.Generator, gen: TarifGeneration, n: int
) -> List[_dt.date]:
    """Uniform month-first start dates within the generation's validity window."""
    von, bis = gen.gueltig_von, gen.gueltig_bis
    first = von.year * 12 + (von.month - 1) + (1 if von.day > 1 else 0)
    last = bis.year * 12 + (bis.month - 1)
    months = rng.integers(first, last + 1, size=n)
    return [_month_first(int(m) // 12, int(m) % 12 + 1) for m in months]


def _ziehe_attribute(
    gen: TarifGeneration, rng: np.random.Generator, n: int
) -> Dict[str, np.ndarray]:
    """Vertragsattribute ziehen (Copula-Block, dann Zahlweise — feste Reihenfolge).

    Wird von Batch-Generator und Neuzugang identisch genutzt; die
    rng-Aufrufreihenfolge ist Teil des Determinismus-Contracts.
    """
    # 1) Correlated uniforms for the copula attributes (fixed column order),
    #    then the marginal transform per configured distribution.
    corr = build_corr_matrix(COPULA_ORDER, gen.korrelationen)
    u = correlated_uniforms(rng, corr, n)
    drawn: Dict[str, np.ndarray] = {}
    for k, merkmal in enumerate(COPULA_ORDER):
        spec = gen.verteilungen[merkmal]
        drawn[merkmal] = transform(u[:, k], spec.typ, spec.params)

    # 2) Independent attributes (after the copula block — fixed order).
    spec_zw = gen.verteilungen["zahlweise"]
    zahlweise_raw = transform(rng.random(n), spec_zw.typ, spec_zw.params)

    # 3) Coerce + constrain into contract-valid integers.
    entry_age = np.asarray(np.rint(drawn["entry_age"].astype(float)), dtype=np.int64)
    entry_age = np.clip(entry_age, 18, gen.max_endalter - 1)

    duration = np.asarray(np.rint(drawn["duration"].astype(float)), dtype=np.int64)
    duration = np.clip(duration, 1, None)
    duration = np.minimum(duration, gen.max_endalter - entry_age)
    duration = np.maximum(duration, 1)

    premium_duration = np.asarray(
        np.rint(drawn["premium_duration"].astype(float)), dtype=np.int64
    )
    premium_duration = np.clip(premium_duration, 1, None)
    premium_duration = np.minimum(premium_duration, duration)

    sum_insured = np.asarray(drawn["sum_insured"], dtype=np.float64)
    sum_insured = np.maximum(sum_insured, 1000.0)

    return {
        "entry_age": entry_age,
        "duration": duration,
        "premium_duration": premium_duration,
        "sum_insured": sum_insured,
        "sex": np.asarray([str(v) for v in drawn["sex"]], dtype=object),
        "zahlweise": np.asarray([int(v) for v in zahlweise_raw], dtype=np.int64),
    }


def _baue_frame(
    gen: TarifGeneration,
    attribute: Dict[str, np.ndarray],
    starts: List[_dt.date],
    police_ids: np.ndarray,
) -> pd.DataFrame:
    """POL-Basiszeilen aus Attributen, Startdaten und Nummern zusammensetzen."""
    n = len(starts)
    entry_age = attribute["entry_age"]
    duration = attribute["duration"]
    premium_duration = attribute["premium_duration"]
    birth = [_add_years(s, -int(a)) for s, a in zip(starts, entry_age)]
    ins_end = [_add_years(s, int(d)) for s, d in zip(starts, duration)]
    pay_end = [_add_years(s, int(t)) for s, t in zip(starts, premium_duration)]
    return pd.DataFrame(
        {
            "police_id": police_ids,
            "tarif_generation": np.full(n, gen.name, dtype=object),
            "status_id": np.ones(n, dtype=np.int64),
            "status_code": np.full(n, "POL", dtype=object),
            "status_date": pd.to_datetime(starts),
            "sex": attribute["sex"],
            "date_of_birth": pd.to_datetime(birth),
            "entry_age": entry_age,
            "duration": duration,
            "premium_duration": premium_duration,
            "sum_insured": attribute["sum_insured"],
            "zahlweise": attribute["zahlweise"],
            "insurance_start": pd.to_datetime(starts),
            "insurance_end": pd.to_datetime(ins_end),
            "payment_end": pd.to_datetime(pay_end),
        }
    )


def _generate_generation(
    gen: TarifGeneration, gen_index: int, master_seed: int
) -> pd.DataFrame:
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([master_seed, gen_index])))
    n = gen.sample_size
    attribute = _ziehe_attribute(gen, rng, n)
    # 4) Time axis (month-first convention) — drawn AFTER the attributes,
    #    identical rng call order as before the refactoring.
    starts = _draw_insurance_start(rng, gen, n)
    police_ids = np.arange(1, n + 1, dtype=np.int64) + (gen_index + 1) * 10_000_000
    return _baue_frame(gen, attribute, starts, police_ids)


#: SeedSequence-Konstante der Neuzugangs-Stroeme ([seed, NEUZUGANG_STREAM,
#: gen_index, kalenderjahr]) — getrennt von Generator ([seed, gen_index])
#: und Ereignis-Engine ([seed, 424242, police_id]).
NEUZUGANG_STREAM = 771177

#: police_id-Offset der Neuzugaenge innerhalb des Generations-Nummernkreises
#: (Batch belegt 1..1_000_000).
_NEUZUGANG_ID_OFFSET = 2_000_000


def neuzugaenge(
    config: BestandConfig, von: _dt.date, bis: _dt.date
) -> pd.DataFrame:
    """Simulierter Neuzugang: POL-Basiszeilen mit Beginn in ``(von, bis]``.

    Je Generation und Kalenderjahr werden ``neuzugang_pro_jahr`` Vertraege
    aus einem eigenen Substream gezogen (Attribute wie im Batch-Generator,
    Beginn gleichverteilt ueber ALLE Monatsersten des Kalenderjahres).
    Draws sind horizont- und fensterunabhaengig: pro Jahrgang wird immer
    voll gezogen und erst danach auf Gueltigkeitsfenster und ``(von, bis]``
    gefiltert — dadurch ist der Neuzugang bei Horizont-Erweiterung ein
    Praefix (fruehere Zugaenge aendern sich nicht), die police_ids sind
    jahrgangsstabil, und Rand-Jahrgaenge tragen anteilig weniger Volumen
    (gleiche Monatsdichte wie volle Jahrgaenge, konsistent zum Batch).
    """
    fehler = config.validate()
    if fehler:
        raise ValueError("Config ungueltig: " + "; ".join(fehler))
    von_ts, bis_ts = pd.Timestamp(von), pd.Timestamp(bis)
    frames: List[pd.DataFrame] = []
    for idx, gen in enumerate(config.generationen):
        anzahl = gen.neuzugang_pro_jahr
        if anzahl <= 0:
            continue
        fenster_von = gen.gueltig_von.year * 12 + (gen.gueltig_von.month - 1) + (
            1 if gen.gueltig_von.day > 1 else 0
        )
        fenster_bis = gen.gueltig_bis.year * 12 + (gen.gueltig_bis.month - 1)
        for jahr in range(gen.gueltig_von.year, gen.gueltig_bis.year + 1):
            erster = max(fenster_von, jahr * 12)
            letzter = min(fenster_bis, jahr * 12 + 11)
            if erster > letzter:
                continue
            # Jahrgaenge ohne Schnitt mit (von, bis] draw-neutral ueberspringen
            # (eigener Substream je Jahr — fremde Jahre brauchen keine Draws):
            if (
                pd.Timestamp(_month_first(letzter // 12, letzter % 12 + 1)) <= von_ts
                or pd.Timestamp(_month_first(erster // 12, erster % 12 + 1)) > bis_ts
            ):
                continue
            # Nummernkreis-Guard VOR den Draws (jahrgangsstabile Offsets):
            offset = _NEUZUGANG_ID_OFFSET + (jahr - gen.gueltig_von.year) * anzahl
            if offset + anzahl >= 8_000_000:
                raise ValueError(
                    f"generation {gen.name}: Neuzugang-Nummernkreis erschoepft "
                    "(neuzugang_pro_jahr x Jahrgaenge zu gross)"
                )
            rng = np.random.Generator(
                np.random.PCG64(
                    np.random.SeedSequence([config.seed, NEUZUGANG_STREAM, idx, jahr])
                )
            )
            attribute = _ziehe_attribute(gen, rng, anzahl)
            # Ueber ALLE 12 Monatserste des Jahres ziehen (fensterunabhaengig):
            monate = rng.integers(jahr * 12, jahr * 12 + 12, size=anzahl)
            starts = [_month_first(int(m) // 12, int(m) % 12 + 1) for m in monate]
            police_ids = (
                np.arange(1, anzahl + 1, dtype=np.int64)
                + (idx + 1) * 10_000_000
                + offset
            )
            frame = _baue_frame(gen, attribute, starts, police_ids)
            # Erst NACH dem Ziehen filtern (Gueltigkeitsfenster + Horizont) —
            # verworfene Draws halten das Praefix stabil.
            im_fenster = (monate >= erster) & (monate <= letzter)
            maske = (
                im_fenster
                & (frame["insurance_start"] > von_ts)
                & (frame["insurance_start"] <= bis_ts)
            )
            frames.append(frame[maske])
    if not frames:
        return pd.DataFrame(
            {name: pd.Series(dtype=dtype) for name, dtype in STAMM_SPALTEN}
        )
    df = pd.concat(frames, ignore_index=True)
    df = df[list(STAMM_NAMES)].astype(stamm_dtypes())
    return df.sort_values("police_id", kind="stable").reset_index(drop=True)


def generate(
    config: BestandConfig, bis: _dt.date | None = None
) -> pd.DataFrame:
    """Generate the full portfolio for all configured tariff generations.

    ``bis`` (Referenzstichtag) macht den Generator zur Batch-Auswertung des
    Zugangs-Stroms bis zu diesem Datum: gezogen wird identisch (draw-then-
    filter), behalten werden nur Vertraege mit ``insurance_start <= bis`` —
    das Ergebnis ist die exakte Teilmenge des vollen Laufs. Zusammen mit
    ``fortschreiben(..., neuzugang_ab=bis)`` besiedelt so genau ein Erzeuger
    jedes Zeitfenster. Ohne ``bis`` unveraendert der volle Bestand.
    """
    errors = config.validate()
    if errors:
        raise ValueError("Config ungueltig: " + "; ".join(errors))
    frames = [
        _generate_generation(gen, idx, config.seed)
        for idx, gen in enumerate(config.generationen)
    ]
    df = pd.concat(frames, ignore_index=True)
    if bis is not None:
        df = df[df["insurance_start"] <= pd.Timestamp(bis)]
    df = df[list(STAMM_NAMES)].astype(stamm_dtypes())
    df = df.sort_values("police_id", kind="stable").reset_index(drop=True)
    if df["police_id"].duplicated().any():
        raise ValueError(
            "police_id-Kollision zwischen Generationen — Nummernkreis verletzt "
            "(sample_size-Obergrenze der Config umgangen?)"
        )
    return df
