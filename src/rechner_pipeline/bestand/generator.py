"""Der Zugangsstrom der Simulation: Vertragsattribute und jaehrlicher Neuzugang.

Zieht je Tarifgeneration die Vertragsattribute — Randverteilungen und
paarweise Spearman-Korrelationen aus der TOML-Config, Abhaengigkeit ueber
eine Gauss-Copula (:mod:`rechner_pipeline.bestand.stochastik`) — und baut
daraus die kanonischen Stammzeilen (:mod:`rechner_pipeline.models.bestand`).

Zwei Konsumenten teilen sich die Attributziehung: der jaehrliche
Zugangsstrom :func:`neuzugaenge` (Pruefstrecke, ``cli_fortschreibung
--neuzugang-ab``) und das tagesgenaue Neugeschaeft der Vorzeige
(:mod:`rechner_pipeline.betrieb.neugeschaeft`). Beide buchen jeden Vertrag
als Zugang; einen Bestand OHNE Geschichte gibt es nicht mehr.

Bis zum 2026-09-21 stand hier ausserdem der Batch-Erzeuger (``generate``,
``sample_size``): ein auf einmal gezogener Bestand ohne eine einzige
Buchung. Er war nie mehr als Kulisse — die Vorzeige holte daraus fuenf
Vertraege des Grenztages, die Pruefstrecke des Migrationsfalls 2220
Vertraege, an denen keine Pruefung hing (gemessen: alle Gates gruen ohne
sie). Entfernt, ADR-020.

Rechnet NICHTS Aktuarielles: keine Beitraege, keine Barwerte, keine
Reserven — gerechnete Groessen kommen aus dem stabilen Kern
(:func:`rechner_pipeline.bestand.kernlauf.berechne_vertrag`).

Seed-Disziplin: NIE mit dem nackten Master-Seed seeden —
``SeedSequence(seed)`` ist bitidentisch zu ``SeedSequence([seed, 0])``
(Trailing-Zero-Normalisierung). Jede Stromfamilie traegt ihre eigene
Konstante (Neuzugang: ``NEUZUGANG_STREAM``, Tagesneugeschaeft:
``betrieb.neugeschaeft.NEUGESCHAEFT_STREAM``, Ereignis-Engine: 424242).

Knoten: klv, bu
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

#: Draw order je Produkt: BU zieht die versicherte Jahresrente statt
#: Versicherungssumme und kennt weder eigene Beitragsdauer noch Zahlweise
#: (Beitraege laufen ueber die volle Laufzeit, jaehrlich) — die
#: KLV-Reihenfolge bleibt unveraendert (Determinismus-Contract).
COPULA_ORDER_JE_PRODUKT = {
    "klv": COPULA_ORDER,
    "bu": ("entry_age", "sex", "duration", "bu_rente"),
}

#: Fachliche Mindest-Jahresrente eines BU-Vertrags (Gegenstueck zur
#: Mindest-Versicherungssumme von 1.000 bei KLV).
MIN_BU_RENTE = 1200.0


def _month_first(year: int, month: int) -> _dt.date:
    return _dt.date(year, month, 1)


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _ziehe_attribute(
    gen: TarifGeneration, rng: np.random.Generator, n: int
) -> Dict[str, np.ndarray]:
    """Vertragsattribute ziehen (Copula-Block, dann Zahlweise — feste Reihenfolge).

    Wird von jaehrlichem Neuzugang und Tagesneugeschaeft identisch genutzt; die
    rng-Aufrufreihenfolge ist Teil des Determinismus-Contracts. Fuer
    BU-Generationen gilt eine eigene, kuerzere Zugreihenfolge
    (:data:`COPULA_ORDER_JE_PRODUKT`) — der KLV-Pfad bleibt bit-identisch.
    """
    if gen.produkt == "bu":
        return _ziehe_bu_attribute(gen, rng, n)
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
        "bu_rente": np.zeros(n, dtype=np.float64),
        "sex": np.asarray([str(v) for v in drawn["sex"]], dtype=object),
        "zahlweise": np.asarray([int(v) for v in zahlweise_raw], dtype=np.int64),
    }


def _ziehe_bu_attribute(
    gen: TarifGeneration, rng: np.random.Generator, n: int
) -> Dict[str, np.ndarray]:
    """Attribute einer BU-Generation (Alter, Sex, Laufzeit, Jahresrente).

    Das BU-Beispielprodukt zahlt Beitraege ueber die volle Versicherungsdauer
    und kennt nur Jahreszahlung — ``premium_duration`` und ``zahlweise``
    werden daher nicht gezogen, sondern fachlich gesetzt (und von
    ``validate_portfolio`` so erzwungen).
    """
    order = COPULA_ORDER_JE_PRODUKT["bu"]
    corr = build_corr_matrix(order, gen.korrelationen)
    u = correlated_uniforms(rng, corr, n)
    drawn: Dict[str, np.ndarray] = {}
    for k, merkmal in enumerate(order):
        spec = gen.verteilungen[merkmal]
        drawn[merkmal] = transform(u[:, k], spec.typ, spec.params)

    entry_age = np.asarray(np.rint(drawn["entry_age"].astype(float)), dtype=np.int64)
    entry_age = np.clip(entry_age, 18, gen.max_endalter - 1)
    duration = np.asarray(np.rint(drawn["duration"].astype(float)), dtype=np.int64)
    duration = np.clip(duration, 1, None)
    duration = np.minimum(duration, gen.max_endalter - entry_age)
    duration = np.maximum(duration, 1)
    bu_rente = np.maximum(np.asarray(drawn["bu_rente"], dtype=np.float64), MIN_BU_RENTE)
    return {
        "entry_age": entry_age,
        "duration": duration,
        "premium_duration": duration.copy(),   # Beitragsdauer = Laufzeit
        "sum_insured": np.zeros(n, dtype=np.float64),
        "bu_rente": bu_rente,
        "sex": np.asarray([str(v) for v in drawn["sex"]], dtype=object),
        "zahlweise": np.ones(n, dtype=np.int64),
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
            "produkt": np.full(n, gen.produkt, dtype=object),
            "status_id": np.ones(n, dtype=np.int64),
            "status_code": np.full(n, "POL", dtype=object),
            "status_date": pd.to_datetime(starts),
            "sex": attribute["sex"],
            "date_of_birth": pd.to_datetime(birth),
            "entry_age": entry_age,
            "duration": duration,
            "premium_duration": premium_duration,
            "sum_insured": attribute["sum_insured"],
            "bu_rente": attribute["bu_rente"],
            "zahlweise": attribute["zahlweise"],
            "insurance_start": pd.to_datetime(starts),
            "insurance_end": pd.to_datetime(ins_end),
            "payment_end": pd.to_datetime(pay_end),
            # Eigenes Geschaeft: der Vertrag kommt mit seinem Abschluss in
            # die Buecher. Nur uebernommene Bestaende trennen die beiden
            # Daten (gates/bestand_uebernehmen setzt den Stichtag).
            "bestandszugang": pd.to_datetime(starts),
        }
    )


#: SeedSequence-Konstante der Neuzugangs-Stroeme ([seed, NEUZUGANG_STREAM,
#: gen_index, kalenderjahr]) — getrennt von der Ereignis-Engine
#: ([seed, 424242, police_id]) und dem Tagesneugeschaeft.
NEUZUGANG_STREAM = 771177

#: police_id-Offset der Neuzugaenge innerhalb des Generations-Nummernkreises.
#: 1..1_000_000 gehoerte dem Batch-Erzeuger; der ist weg (ADR-020), der
#: Bereich bleibt frei, damit bestehende Laeufe und Belege ihre Nummern
#: behalten. Der jaehrliche Erzeuger zaehlt ab hier jahrgangsweise weiter
#: und endet vor ``_NEUZUGANG_ID_GRENZE`` — darueber (ab 5 Mio) liegt das
#: Tagesneugeschaeft (``betrieb.neugeschaeft``).
_NEUZUGANG_ID_OFFSET = 2_000_000
_NEUZUGANG_ID_GRENZE = 5_000_000


def neuzugaenge(
    config: BestandConfig, von: _dt.date, bis: _dt.date
) -> pd.DataFrame:
    """Simulierter Neuzugang: POL-Basiszeilen mit Beginn in ``[von, bis]``.

    Je Generation und Kalenderjahr werden ``round(jahresziel(jahr))``
    Vertraege aus einem eigenen Substream gezogen — das Jahresziel ist
    ``neuzugang_pro_jahr`` mit dem Jahresfaktor ``neuzugang_trend``
    (:meth:`~rechner_pipeline.bestand.config.TarifGeneration.jahresziel`;
    ohne Trend der bisherige konstante Satz) — mit Attributen aus derselben
    Ziehung wie das Tagesneugeschaeft und Beginn gleichverteilt ueber ALLE Monatsersten des
    Kalenderjahres.
    Draws sind horizont- und fensterunabhaengig: pro Jahrgang wird immer
    voll gezogen und erst danach auf Gueltigkeitsfenster und ``[von, bis]``
    gefiltert — dadurch ist der Neuzugang bei Horizont-Erweiterung ein
    Praefix (fruehere Zugaenge aendern sich nicht), die police_ids sind
    jahrgangsstabil, und Rand-Jahrgaenge tragen anteilig weniger Volumen
    (gleiche Monatsdichte wie volle Jahrgaenge).
    """
    fehler = config.validate()
    if fehler:
        raise ValueError("Config ungueltig: " + "; ".join(fehler))
    von_ts, bis_ts = pd.Timestamp(von), pd.Timestamp(bis)
    frames: List[pd.DataFrame] = []
    for gen in config.generationen:
        kreis = config.nummernkreis(gen)
        anzahl = gen.neuzugang_pro_jahr
        if anzahl <= 0:
            continue
        fenster_von = gen.gueltig_von.year * 12 + (gen.gueltig_von.month - 1) + (
            1 if gen.gueltig_von.day > 1 else 0
        )
        fenster_bis = gen.gueltig_bis.year * 12 + (gen.gueltig_bis.month - 1)
        # Jahrgangsstabile Nummern auch bei Trend: Der Offset eines
        # Jahrgangs ist die Summe der Ziele aller frueheren Jahrgaenge —
        # ohne Trend genau ``(jahr - erstes Jahr) * anzahl`` wie bisher.
        offset = _NEUZUGANG_ID_OFFSET
        for jahr in range(gen.gueltig_von.year, gen.gueltig_bis.year + 1):
            anzahl = int(round(gen.jahresziel(jahr)))
            erster = max(fenster_von, jahr * 12)
            letzter = min(fenster_bis, jahr * 12 + 11)
            if erster > letzter or anzahl <= 0:
                continue
            # Nummernkreis-Guard VOR den Draws (jahrgangsstabile Offsets):
            offset += anzahl
            if offset >= _NEUZUGANG_ID_GRENZE:
                raise ValueError(
                    f"generation {gen.name}: Neuzugang-Nummernkreis erschoepft "
                    "(neuzugang_pro_jahr x Jahrgaenge zu gross)"
                )
            # Jahrgaenge ohne Schnitt mit [von, bis] draw-neutral ueberspringen
            # (eigener Substream je Jahr — fremde Jahre brauchen keine Draws):
            if (
                pd.Timestamp(_month_first(letzter // 12, letzter % 12 + 1)) < von_ts
                or pd.Timestamp(_month_first(erster // 12, erster % 12 + 1)) > bis_ts
            ):
                continue
            rng = np.random.Generator(
                np.random.PCG64(
                    np.random.SeedSequence([config.seed, NEUZUGANG_STREAM, kreis - 1, jahr])
                )
            )
            attribute = _ziehe_attribute(gen, rng, anzahl)
            # Ueber ALLE 12 Monatserste des Jahres ziehen (fensterunabhaengig):
            monate = rng.integers(jahr * 12, jahr * 12 + 12, size=anzahl)
            starts = [_month_first(int(m) // 12, int(m) % 12 + 1) for m in monate]
            police_ids = (
                np.arange(1, anzahl + 1, dtype=np.int64)
                + kreis * 10_000_000
                + (offset - anzahl)
            )
            frame = _baue_frame(gen, attribute, starts, police_ids)
            # Erst NACH dem Ziehen filtern (Gueltigkeitsfenster + Horizont) —
            # verworfene Draws halten das Praefix stabil.
            im_fenster = (monate >= erster) & (monate <= letzter)
            maske = (
                im_fenster
                & (frame["insurance_start"] >= von_ts)
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
