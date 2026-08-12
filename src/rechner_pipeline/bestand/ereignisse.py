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
  conversion (``pex_rate``, only while premiums are still due, ``j+1 < t``),
  then dynamische Erhoehung (``erh_rate``, premium-paying track only).
  After PEX the contract stays exposed to death and maturity only (no lapse
  of paid-up contracts in Stufe 1 — the sheet defines no RKW_bfr rule).
* Dynamische Erhoehung (Schichtungsprinzip): an accepted Erhoehung creates a
  new Scheibe — actuarially an own model point on the SAME tariff generation
  (entry age = current age, terms = remaining terms, sum =
  ``erh_prozent`` of the current total sum insured, compounding). The
  contract state does not change (no Statushistorie row); the GeVo is
  recorded in the Ledger and the Scheibe in the Scheiben table. All later
  amounts aggregate over Grundscheibe + Erhoehungsscheiben.
* Amounts from the kernel, summed over all Scheiben of the contract: STO
  pays the rows' RKW, PEX fixes the paid-up sums ``VS_bfr``, TOD pays the
  total sum insured (or the total paid-up sum after PEX), ABL pays the
  endowment benefit at ``insurance_end``.
* Determinism: one PCG64 substream per contract,
  ``SeedSequence([seed, EREIGNIS_STREAM, police_id])`` — adding contracts
  never shifts another contract's events, and extending the horizon ``bis``
  keeps all earlier events identical (consistent prefix).
* Draw contract (Common Random Numbers): per simulated policy year the draw
  order is FIXED and config-independent — death draw, then (premium-paying
  track) lapse draw while ``j+1 < n``, then PEX draw while ``j+1 < t``,
  then ERH draw while ``j+1 < t``. The ERH draw is skipped in the PEX year
  itself and never drawn after PEX (outcome-dependent divergence, see
  below). Rates act only as thresholds; a rate of 0 still consumes its
  draw. Runs of different configs on the same portfolio are therefore
  pathwise comparable as long as their event histories agree (e.g. the
  lapse set at storno_rate=0.02 is a subset of the one at 0.03).
* Stornoabschlag bei Scheiben: die Tarif-Grenzen (stoab_min/max) gelten je
  VERTRAG, nicht je Scheibe — der Abzug wird einmal auf die Gesamtwerte
  gerechnet (:func:`vertrags_rkw`); fuer Vertraege ohne Scheiben ist das
  bit-identisch zur Kern-Verlaufszeile.

Outputs (:class:`Fortschreibung`): a Statushistorie (follow-up status rows,
schema :data:`~rechner_pipeline.models.bestand.STATUS_HISTORIE_SPALTEN`), an
Ereignis-Ledger with the kernel-computed amounts (schema
:data:`~rechner_pipeline.models.bestand.LEDGER_SPALTEN`) and the
Erhoehungsscheiben (schema
:data:`~rechner_pipeline.models.bestand.SCHEIBEN_SPALTEN`).
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
from typing import Any, Dict, List, Mapping, NamedTuple, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    LEDGER_SPALTEN,
    SCHEIBEN_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
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


class Fortschreibung(NamedTuple):
    """Ergebnis von :func:`fortschreiben` (vier deterministische Tabellen).

    ``zugaenge`` sind die waehrend der Fortschreibung entstandenen
    Neuzugaenge (POL-Basiszeilen); der Gesamtbestand fuer Zeitscheibe,
    Auswertung und Bericht ist :func:`mit_zugaengen` (stamm, zugaenge).
    """

    historie: pd.DataFrame
    ledger: pd.DataFrame
    scheiben: pd.DataFrame
    zugaenge: pd.DataFrame


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _leerer_frame(spalten) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in spalten})


def vertrags_rkw(
    grund: Rechenkern, scheiben: List[Tuple[int, Rechenkern]], jahr: int
) -> float:
    """Vertragsweiter Rueckkaufswert ueber Grund- und Erhoehungsscheiben.

    Die Stornoabschlag-Grenzen des Tarifwerks (stoab_min/max) sind je
    VERTRAG kalibriert: der Abzug wird einmal auf die Gesamtwerte gerechnet
    (satz * (Gesamt-VS - Gesamt-Deckungsrueckstellung), begrenzt), nicht je
    Scheibe — sonst wuerde die Untergrenze je Scheibe binden und der
    Gesamtabzug mit der Scheibenzahl wachsen. Fuer Vertraege ohne Scheiben
    ist das Ergebnis bit-identisch zur RKW-Spalte der Kern-Verlaufszeile.
    """
    zeilen = [grund.verlaufszeile(jahr)] + [
        kern.verlaufszeile(jahr - erh_jahr) for erh_jahr, kern in scheiben
    ]
    mrv = 0.0
    for z in zeilen:
        mrv += z.vx_mrv
    if grund.produkt.ist_flex_phase(jahr):
        stoab = 0.0
    else:
        mp = grund.mp
        vs = mp.sum_insured + sum(kern.mp.sum_insured for _, kern in scheiben)
        dr = 0.0
        for z in zeilen:
            dr += z.drx_bpfl
        stoab = min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (vs - dr)))
    return max(0.0, mrv - stoab)


class _Vertrag:
    """Grundscheibe + Erhoehungsscheiben eines Vertrags (Schichtungsprinzip).

    Kapselt die Aggregation der Kern-Betraege ueber alle Scheiben; jede
    Scheibe rechnet auf ihrem eigenen Modellpunkt, das Vertragsjahr einer
    Scheibe ist um ihr Erhoehungsjahr versetzt.
    """

    def __init__(self, mp: ModelPoint) -> None:
        self.grund_mp = mp
        self.grund = Rechenkern(mp)
        self.scheiben: List[Tuple[int, float, Rechenkern]] = []  # (jahr, vs, kern)

    def gesamt_vs(self) -> float:
        return self.grund_mp.sum_insured + sum(vs for _, vs, _ in self.scheiben)

    def erhoehe(self, jahr: int, vs: float) -> ModelPoint:
        mp = dataclasses.replace(
            self.grund_mp,
            x=self.grund_mp.x + jahr,
            n=self.grund_mp.n - jahr,
            t=self.grund_mp.t - jahr,
            sum_insured=vs,
        )
        self.scheiben.append((jahr, vs, Rechenkern(mp)))
        return mp

    def rkw(self, jahr: int) -> float:
        return vertrags_rkw(
            self.grund, [(erh_jahr, kern) for erh_jahr, _, kern in self.scheiben], jahr
        )

    def beitragsfreie_summe(self, a0: int) -> float:
        return self.grund.beitragsfreie_summe(a0) + sum(
            kern.beitragsfreie_summe(a0 - erh_jahr)
            for erh_jahr, _, kern in self.scheiben
        )


def _simuliere_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    ereignisse,
    seed: int,
    bis: _dt.date,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simulate one contract; returns (booked events, Erhoehungsscheiben)."""
    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    t = int(row["premium_duration"])
    x = int(row["entry_age"])

    vertrag = _Vertrag(ModelPoint(**model_point_kwargs(row, generation_fields)))
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, EREIGNIS_STREAM, police_id]))
    )

    events: List[Dict[str, Any]] = []
    scheiben: List[Dict[str, Any]] = []

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
    pex_summe = 0.0
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
            qx = min(1.0, vertrag.grund.kom.qx_at(x + j) * ereignisse.tod_faktor)
        else:
            qx = 0.0
        if rng.random() < qx:
            if beitragsfrei_ab is None:
                buche("TOD", j + 1, "Todesfallleistung", vertrag.gesamt_vs())
            else:
                buche("TOD", j + 1, "Todesfallleistung", pex_summe)
            return events, scheiben

        if beitragsfrei_ab is None:
            # 2. Storno (nur beitragspflichtig, nicht im Ablaufjahr):
            if j + 1 < n and rng.random() < ereignisse.storno_rate:
                buche("STO", j + 1, "RKW", vertrag.rkw(j + 1))
                return events, scheiben
            # 3. Beitragsfreistellung (nur solange Beitraege laufen):
            if j + 1 < t and rng.random() < ereignisse.pex_rate:
                beitragsfrei_ab = j + 1
                pex_summe = vertrag.beitragsfreie_summe(j + 1)
                buche("PEX", j + 1, "VS_bfr", pex_summe)
        if beitragsfrei_ab is None:
            # 4. Dynamische Erhoehung (nur beitragspflichtig, solange
            #    Beitraege laufen): neue Scheibe, kein Statuswechsel.
            if j + 1 < t and rng.random() < ereignisse.erh_rate:
                betrag = ereignisse.erh_prozent * vertrag.gesamt_vs()
                mp_s = vertrag.erhoehe(j + 1, betrag)
                scheiben.append(
                    {
                        "police_id": police_id,
                        "scheiben_id": len(vertrag.scheiben),
                        "erhoehung_jahr": j + 1,
                        "erhoehung_datum": pd.Timestamp(_add_years(start, j + 1)),
                        "entry_age": mp_s.x,
                        "duration": mp_s.n,
                        "premium_duration": mp_s.t,
                        "sum_insured": mp_s.sum_insured,
                    }
                )
                buche("ERH", j + 1, "VS_erhoehung", betrag)

    if not horizont_erreicht:
        # Ablauf: alle n Jahre ueberlebt und insurance_end <= bis.
        if beitragsfrei_ab is None:
            buche("ABL", n, "Ablaufleistung", vertrag.gesamt_vs())
        else:
            buche("ABL", n, "Ablaufleistung", pex_summe)
    return events, scheiben


def fortschreiben(
    stamm: pd.DataFrame,
    config: BestandConfig,
    bis: _dt.date,
    *,
    neuzugang_ab: _dt.date | None = None,
) -> Fortschreibung:
    """Roll the base portfolio forward to ``bis``.

    Returns :class:`Fortschreibung` — Statushistorie (state changes only;
    a dynamische Erhoehung changes no state), Ereignis-Ledger (every GeVo
    incl. ERH/ZUG), the created Erhoehungsscheiben and the Neuzugaenge.

    ``neuzugang_ab`` (Referenzstichtag) schaltet den simulierten Neuzugang
    frei: neue Vertraege mit Beginn in ``(neuzugang_ab, bis]`` entstehen aus
    :func:`rechner_pipeline.bestand.generator.neuzugaenge` (Volumen je
    Generation: ``neuzugang_pro_jahr``), erhalten einen ZUG-Ledger-Eintrag
    und werden ab ihrem Beginn mitsimuliert. Der Basisbestand darf dann
    keine Vertraege nach dem Referenzstichtag enthalten (Doppelzaehlung).

    ``stamm`` is the generator's base portfolio (one POL row per contract);
    the event rates come from ``config.ereignisse``, the amounts from the
    stable kernel. Pure function of (stamm, config, bis, neuzugang_ab) —
    seed-deterministic, the Stamm itself is never mutated. Fail-fast
    guards: only POL base rows
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

    hat_neuzugang = any(g.neuzugang_pro_jahr > 0 for g in config.generationen)
    if neuzugang_ab is not None and hat_neuzugang:
        neuzugang_ab = pd.Timestamp(neuzugang_ab).date()
        if neuzugang_ab > bis:
            raise EreignisError(
                f"neuzugang_ab {neuzugang_ab.isoformat()} liegt nach dem "
                f"Horizont bis {bis.isoformat()} (vertauschte Argumente?)"
            )
        if len(stamm) and (
            stamm["insurance_start"] > pd.Timestamp(neuzugang_ab)
        ).any():
            raise EreignisError(
                "Basisbestand enthaelt Vertraege mit Beginn nach dem "
                f"Referenzstichtag {neuzugang_ab.isoformat()} — Neuzugang wuerde "
                "den Zeitraum doppelt besiedeln (ein Erzeuger je Zeitfenster). "
                "Basisbestand mit generate(config, bis=Referenzstichtag) erzeugen"
            )
        from rechner_pipeline.bestand.generator import neuzugaenge

        zugaenge = neuzugaenge(config, neuzugang_ab, bis)
        ueberschneidung = set(zugaenge["police_id"]) & set(stamm["police_id"])
        if ueberschneidung:
            raise EreignisError(
                f"Neuzugang-police_ids kollidieren mit dem Basisbestand: "
                f"{sorted(ueberschneidung)[:5]}"
            )
        zu_lang = zugaenge[zugaenge["duration"] > 50]
        if len(zu_lang):
            generationen_namen = sorted(set(zu_lang["tarif_generation"]))
            raise EreignisError(
                f"Neuzugang mit duration > 50 (max {int(zu_lang['duration'].max())}, "
                f"{len(zu_lang)} Vertraege, Generation {generationen_namen}, "
                f"z. B. police {int(zu_lang['police_id'].iloc[0])}): ausserhalb "
                "des blattfest verankerten Verlaufsbereichs des Kerns — "
                "duration-Verteilung bzw. max_endalter der Config begrenzen"
            )
    else:
        zugaenge = _leerer_frame(STAMM_SPALTEN)

    generationen = {g.name: g.generation_fields() for g in config.generationen}

    alle_events: List[Dict[str, Any]] = []
    alle_scheiben: List[Dict[str, Any]] = []
    # Zugangs-GeVos: ein ZUG-Ledger-Eintrag je Neuzugang (kein Statuswechsel —
    # die POL-Basiszeile ist der Zugangs-Satz selbst).
    for zugang in zugaenge.to_dict("records"):
        alle_events.append(
            {
                "police_id": int(zugang["police_id"]),
                "status_code": "ZUG",
                "vertragsjahr": 0,
                "status_date": pd.Timestamp(zugang["insurance_start"]),
                "betrag_art": "VS",
                "betrag": float(zugang["sum_insured"]),
            }
        )
    gesamt = (
        pd.concat([stamm, zugaenge], ignore_index=True) if len(zugaenge) else stamm
    )
    for row in gesamt.to_dict("records"):
        name = str(row["tarif_generation"])
        if name not in generationen:
            raise EreignisError(
                f"police {row['police_id']}: Tarifgeneration {name!r} nicht in Config "
                f"(bekannt: {sorted(generationen)})"
            )
        try:
            events, scheiben = _simuliere_vertrag(
                row, generationen[name], config.ereignisse, config.seed, bis
            )
        except EreignisError:
            raise
        except Exception as exc:
            raise EreignisError(
                f"police {row['police_id']}: {type(exc).__name__}: {exc}"
            ) from exc
        alle_events.extend(events)
        alle_scheiben.extend(scheiben)

    if alle_scheiben:
        scheiben_df = (
            pd.DataFrame(alle_scheiben)
            .astype(dict(SCHEIBEN_SPALTEN))
            .sort_values(["police_id", "scheiben_id"], kind="stable")
            .reset_index(drop=True)[[n for n, _ in SCHEIBEN_SPALTEN]]
        )
    else:
        scheiben_df = _leerer_frame(SCHEIBEN_SPALTEN)

    if not alle_events:
        return Fortschreibung(
            _leerer_frame(STATUS_HISTORIE_SPALTEN),
            _leerer_frame(LEDGER_SPALTEN),
            scheiben_df,
            zugaenge,
        )

    ereignisse = pd.DataFrame(alle_events).sort_values(
        ["police_id", "vertragsjahr"], kind="stable"
    )
    generation_je_police = gesamt.set_index("police_id")["tarif_generation"]
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

    # Statushistorie = nur Zustandswechsel; ERH aendert den Zustand nicht,
    # ZUG ist die POL-Basiszeile selbst (liegt in zugaenge).
    zustaende = ereignisse[~ereignisse["status_code"].isin(("ERH", "ZUG"))].copy()
    if len(zustaende) == 0:
        return Fortschreibung(
            _leerer_frame(STATUS_HISTORIE_SPALTEN), ledger, scheiben_df, zugaenge
        )
    # status_id je Police fortlaufend ab 2 (Basis-POL im Stamm ist 1).
    zustaende["status_id"] = zustaende.groupby("police_id").cumcount() + 2
    historie = pd.DataFrame(
        {
            "police_id": zustaende["police_id"].astype("int64"),
            "status_id": zustaende["status_id"].astype("int64"),
            "status_code": zustaende["status_code"].astype(object),
            "status_date": pd.to_datetime(zustaende["status_date"]),
        }
    ).reset_index(drop=True)
    return Fortschreibung(historie, ledger, scheiben_df, zugaenge)


def mit_zugaengen(stamm: pd.DataFrame, zugaenge: pd.DataFrame) -> pd.DataFrame:
    """Gesamtbestand = Basisbestand + Neuzugaenge (POL-Basiszeilen).

    Das Ergebnis ist der Bestand fuer Zeitscheibe, Auswertung und Bericht;
    es erfuellt denselben Basis-Contract wie der Generator-Output
    (validate_portfolio-konform, eindeutige police_ids).
    """
    if len(zugaenge) == 0:
        return stamm.copy().reset_index(drop=True)
    beide = pd.concat([stamm, zugaenge], ignore_index=True)
    if beide["police_id"].duplicated().any():
        raise EreignisError("police_id-Kollision zwischen Bestand und Neuzugang")
    return (
        beide.sort_values("police_id", kind="stable")
        .reset_index(drop=True)[list(STAMM_NAMES)]
    )


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
            f"historie: police_id unbekannt: {sorted(unbekannt)[:5]} — "
            "bei Neuzugaengen den Gesamtbestand uebergeben "
            "(mit_zugaengen(stamm, zugaenge))"
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
