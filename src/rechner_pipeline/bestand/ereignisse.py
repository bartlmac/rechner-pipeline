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
* Erfahrungsannahmen (3. Ordnung): JEDE Ereigniswahrscheinlichkeit der
  Simulation entsteht aus der ersten Ordnung ueber eine affine
  Transformation ``a + b * x``
  (:class:`~rechner_pipeline.bestand.config.Annahme`). Fuer Ereignisse mit
  Rechnungsgrundlage (Tod, Invalidisierung, Reaktivierung,
  Invalidensterblichkeit) rechnet ``b`` die Sicherheitsmarge heraus; fuer
  Ereignisse ohne (Storno, Beitragsfreistellung, dynamische Erhoehung) ist
  ``b = 0`` und ``a`` die Rate selbst. Die BEWERTUNG bleibt davon
  unberuehrt — Beitraege und Reserven rechnet der Kern auf erster Ordnung.
* Per policy year, hierarchical competing risks on the active track:
  death (Annahme ``tod`` auf der Tafel-qx der Tarifbasis), then lapse
  (Annahme ``storno``, only while ``j+1 < n``), then paid-up conversion
  (Annahme ``beitragsfreistellung``, while ``j+1 < t``), then dynamische
  Erhoehung (Annahme ``erhoehung``, premium-paying track only).
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
    bu_model_point_kwargs,
    model_point_kwargs,
)

#: SeedSequence-Konstante: separates event streams from the generator's
#: generation streams ([seed, gen_index]) — never reuse for other purposes.
#: Separation assumptions (SeedSequence normalizes trailing zeros, so
#: [seed, X] == [seed, X, 0]): police_id must be > 0 (enforced in
#: :func:`fortschreiben`; the generator issues >= 10_000_001) and gen_index
#: stays small — a third stream family needs a NEW distinct constant.
EREIGNIS_STREAM = 424242

#: Betrags-Art der BU-GeVos: die von diesem Geschaeftsvorfall betroffene
#: versicherte Jahresrente (Bezugsgroesse der Nachweisung) — bei
#: Invalidisierung die beginnende, bei Reaktivierung/Tod/Ablauf aus dem
#: Leistungsbezug die endende Rente. Das Beispielprodukt zahlt weder
#: Todesfall- noch Erlebensfallleistung; solche GeVos tragen 0.
BU_BETRAG_ART = "BU_Jahresrente"

#: Sentinel fuer "Argument nicht gesetzt" (None ist ein gueltiger Wert:
#: GeVos ohne Zustandswechsel).
_KEIN_ARGUMENT = object()


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


def _event(
    police_id: int,
    ereignis: str,
    jahr: int,
    datum: _dt.date,
    art: str,
    betrag: float,
    status_code: Any = _KEIN_ARGUMENT,
) -> Dict[str, Any]:
    """Ein gebuchter GeVo.

    ``ereignis`` ist der GeVo-Code des Ledgers, ``status_code`` der
    resultierende Vertragszustand der Statushistorie. Bei den meisten
    GeVos sind beide gleich; sie fallen auseinander, wo der GeVo einen
    ANDEREN Zustand herstellt (Reaktivierung ``REA`` -> ``POL``,
    Invalidisierung ``INV`` -> ``BU``) oder gar keinen Zustandswechsel
    bewirkt (``ERH``/``ZUG`` -> ``None``).
    """
    return {
        "police_id": police_id,
        "ereignis": ereignis,
        "status_code": ereignis if status_code is _KEIN_ARGUMENT else status_code,
        "vertragsjahr": jahr,
        "status_date": pd.Timestamp(datum),
        "betrag_art": art,
        "betrag": float(betrag),
    }


def _simuliere_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
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

    def buche(
        code: str, jahr: int, art: str, betrag: float, status: Any = _KEIN_ARGUMENT
    ) -> None:
        events.append(
            _event(police_id, code, jahr, _add_years(start, jahr), art, betrag, status)
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
        # 1. Tod im Vertragsjahr j: Erfahrungsannahme auf der Tafel-qx
        #    erster Ordnung der Tarifbasis. Bei b = 0 wird die Tafel gar
        #    nicht angefasst (Tafelgrenzen bleiben unberuehrt).
        qx_erste_ordnung = (
            vertrag.grund.basis.qx_at(x + j) if annahmen.tod.b else 0.0
        )
        if rng.random() < annahmen.tod(qx_erste_ordnung):
            if beitragsfrei_ab is None:
                buche("TOD", j + 1, "Todesfallleistung", vertrag.gesamt_vs())
            else:
                buche("TOD", j + 1, "Todesfallleistung", pex_summe)
            return events, scheiben

        if beitragsfrei_ab is None:
            # 2. Storno (nur beitragspflichtig, nicht im Ablaufjahr):
            if j + 1 < n and rng.random() < annahmen.storno(0.0):
                buche("STO", j + 1, "RKW", vertrag.rkw(j + 1))
                return events, scheiben
            # 3. Beitragsfreistellung (nur solange Beitraege laufen):
            if j + 1 < t and rng.random() < annahmen.beitragsfreistellung(0.0):
                beitragsfrei_ab = j + 1
                pex_summe = vertrag.beitragsfreie_summe(j + 1)
                buche("PEX", j + 1, "VS_bfr", pex_summe)
        if beitragsfrei_ab is None:
            # 4. Dynamische Erhoehung (nur beitragspflichtig, solange
            #    Beitraege laufen): neue Scheibe, kein Statuswechsel.
            if j + 1 < t and rng.random() < annahmen.erhoehung(0.0):
                betrag = annahmen.erh_prozent * vertrag.gesamt_vs()
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
                buche("ERH", j + 1, "VS_erhoehung", betrag, status=None)

    if not horizont_erreicht:
        # Ablauf: alle n Jahre ueberlebt und insurance_end <= bis.
        if beitragsfrei_ab is None:
            buche("ABL", n, "Ablaufleistung", vertrag.gesamt_vs())
        else:
            buche("ABL", n, "Ablaufleistung", pex_summe)
    return events, scheiben


def _pruefe_wegzuege(
    police_id: int, zustand: str, alter: int, dauer: int, summe: float
) -> None:
    """Markov-Bedingung nach der Transformation: die Wegzuege aus einem
    Zustand duerfen sich nicht auf mehr als 1 summieren.

    Die einzelne Annahme wird auf [0, 1] geklemmt, die SUMME konkurrierender
    Risiken bleibt davon ungeschuetzt — eine zu grosse Marge (b) koennte
    sie ueber 1 heben. Die kumulierten Schwellen der Ziehung wuerden das
    letzte Risiko dann still stutzen, und die Simulation liefe auf einer
    anderen Verteilung als das gleichnamige Zustandsmodell (das hier
    fail-fast abbricht). Deshalb dieselbe Grenze wie in
    :meth:`rechner_pipeline.kern.zustandsmodell.Zustandsmodell._wegzuege`.
    """
    if summe > 1.0 + 1e-12:
        raise EreignisError(
            f"police {police_id}: transformierte Wegzuege aus {zustand} "
            f"(Alter {alter}, Dauer {dauer}) summieren auf {summe} > 1 — "
            "die Erfahrungsannahmen heben die Uebergangswahrscheinlichkeiten "
            "ueber die Markov-Grenze (b zu gross)"
        )


def bu_uebergang(produkt, annahmen):
    """Übergangsfunktion des BU-Zustandsprozesses auf Erfahrungsannahmen.

    Legt die Erfahrungsschicht (3. Ordnung) über die vier
    Ausscheideordnungen des Produkts: jede Übergangswahrscheinlichkeit
    erster Ordnung wird durch ihre :class:`~rechner_pipeline.bestand.config.Annahme`
    transformiert. Die Simulation der Fortschreibung nutzt genau diese
    Funktion — sie ist damit auch der Ansatzpunkt, um die simulierte
    Zustandsverteilung gegen ein Modell derselben Ordnung zu prüfen
    (statt gegen die Bewertungsgrundlage erster Ordnung).
    """
    from rechner_pipeline.kern.produkte.bu import AKTIV, BU_ZUSTAND, TOT

    zuordnung = {
        (AKTIV, BU_ZUSTAND): annahmen.invalidisierung,
        (AKTIV, TOT): annahmen.aktivensterblichkeit,
        (BU_ZUSTAND, AKTIV): annahmen.reaktivierung,
        (BU_ZUSTAND, TOT): annahmen.invalidensterblichkeit,
    }

    def uebergang(von: str, nach: str, alter: int, dauer: int) -> float:
        annahme = zuordnung.get((von, nach))
        if annahme is None:
            return 0.0
        return annahme(produkt._uebergang(von, nach, alter, dauer))

    return uebergang


def _simuliere_bu_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
    seed: int,
    bis: _dt.date,
) -> List[Dict[str, Any]]:
    """Simuliere einen BU-Vertrag; liefert die gebuchten GeVos.

    Der Zustandsprozess ist derselbe, den der Kern bewertet — die
    Übergangswahrscheinlichkeiten kommen aus dem Produkt
    (:meth:`rechner_pipeline.kern.produkte.bu.BU._uebergang`, also aus den
    vier Ausscheideordnungen), nicht aus freien Raten. Darüber liegt die
    Erfahrungsschicht (:class:`~rechner_pipeline.bestand.config.Annahmen`):
    sie transformiert jede Übergangswahrscheinlichkeit affin, sodass die
    Simulation auf dritter Ordnung läuft, während die Bewertung
    unverändert auf erster bleibt.

    Gitter und Konventionen wie beim KLV-Pfad: Vertragsjahr ``j`` läuft von
    Jahrestag ``j`` bis ``j+1``, Ereignisse werden am Jahrestag ``j+1``
    gebucht, Alter im Jahr ``j`` ist ``x + j`` (identisch zur
    Jahresindizierung des Zustandsmodells). Die BU-Dauer (volle Jahre im
    Leistungsbezug) wird wie in der Engine bei der Select-Periode gekappt.

    Draw-Contract: EIN Uniform-Draw je simuliertem Vertragsjahr, Schwellen
    in fester Reihenfolge — aus ``aktiv`` erst Invalidisierung, dann Tod;
    aus ``bu`` erst Reaktivierung, dann Tod. Das ist exakt die
    Multinomialziehung der Übergangsmatrix des Jahres.
    """
    from rechner_pipeline.kern.produkte.bu import (
        AKTIV,
        BU,
        BU_ZUSTAND,
        TOT as TOT_ZUSTAND,
        BUModelPoint,
    )

    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    x = int(row["entry_age"])
    rente = float(row["bu_rente"])

    produkt = BU(BUModelPoint(**bu_model_point_kwargs(row, generation_fields)))
    uebergang = bu_uebergang(produkt, annahmen)
    max_dauer = produkt.modell.max_dauer
    rng = np.random.Generator(
        np.random.PCG64(np.random.SeedSequence([seed, EREIGNIS_STREAM, police_id]))
    )

    events: List[Dict[str, Any]] = []

    def buche(ereignis: str, jahr: int, betrag: float, status: Any) -> None:
        events.append(
            _event(
                police_id, ereignis, jahr, _add_years(start, jahr),
                BU_BETRAG_ART, betrag, status,
            )
        )

    zustand = AKTIV
    dauer = 0
    horizont_erreicht = False

    for j in range(n):
        if _add_years(start, j + 1) > bis:
            horizont_erreicht = True
            break
        alter = x + j
        u = rng.random()
        if zustand == AKTIV:
            p_inv = uebergang(AKTIV, BU_ZUSTAND, alter, 0)
            p_tod = uebergang(AKTIV, TOT_ZUSTAND, alter, 0)
            _pruefe_wegzuege(police_id, AKTIV, alter, 0, p_inv + p_tod)
            if u < p_inv:
                # Invalidisierung: die BU-Rente beginnt (Beitragsbefreiung
                # ist im Produkt implizit — Beitraege laufen nur in aktiv).
                buche("INV", j + 1, rente, "BU")
                zustand, dauer = BU_ZUSTAND, 0
            elif u < p_inv + p_tod:
                buche("TOD", j + 1, 0.0, "TOD")
                return events
        else:
            p_rea = uebergang(BU_ZUSTAND, AKTIV, alter, dauer)
            p_tod = uebergang(BU_ZUSTAND, TOT_ZUSTAND, alter, dauer)
            _pruefe_wegzuege(police_id, BU_ZUSTAND, alter, dauer, p_rea + p_tod)
            if u < p_rea:
                # Reaktivierung: die Rente endet, der Vertrag ist wieder
                # Anwaerter (und wieder beitragspflichtig).
                buche("REA", j + 1, rente, "POL")
                zustand, dauer = AKTIV, 0
            elif u < p_rea + p_tod:
                buche("TOD", j + 1, rente, "TOD")
                return events
            else:
                dauer = min(dauer + 1, max_dauer)

    if not horizont_erreicht:
        # Ablauf: die Rente endet spaetestens mit dem Vertrag.
        buche("ABL", n, rente if zustand == BU_ZUSTAND else 0.0, "ABL")
    return events


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
    the event assumptions come from ``config.annahmen``, the amounts from the
    stable kernel. Pure function of (stamm, config, bis, neuzugang_ab) —
    seed-deterministic, the Stamm itself is never mutated. Fail-fast
    guards: only POL base rows
    (a Zeitscheibe or Historie view fed back in is an error — the engine
    would re-simulate it from insurance_start), unique positive police_id,
    valid event rates, durations within the engine's 0..50 window.
    """
    fehlend = [c for c in STAMM_NAMES if c not in stamm.columns]
    if fehlend:
        raise EreignisError(f"Stamm-Spalten fehlen: {fehlend}")
    konfig_fehler = config.annahmen.validate()
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
            "duration > 50: ausserhalb des Verlaufsfensters der "
            "Bestand-Engine (Vertragsjahre 0..50; eigene konservative "
            "Grenze — der Kern selbst rechnet seit 3.0.0 bis zur "
            "Tafel-Erschoepfung)"
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
                "des Verlaufsfensters der Bestand-Engine (0..50) — "
                "duration-Verteilung bzw. max_endalter der Config begrenzen"
            )
    else:
        zugaenge = _leerer_frame(STAMM_SPALTEN)

    generationen = {g.name: g.generation_fields() for g in config.generationen}
    bu_generationen = {
        g.name: g.bu_generation_fields()
        for g in config.generationen
        if g.produkt == "bu"
    }
    produkt_je_generation = {g.name: g.produkt for g in config.generationen}

    alle_events: List[Dict[str, Any]] = []
    alle_scheiben: List[Dict[str, Any]] = []
    # Zugangs-GeVos: ein ZUG-Ledger-Eintrag je Neuzugang (kein Statuswechsel —
    # die POL-Basiszeile ist der Zugangs-Satz selbst).
    for zugang in zugaenge.to_dict("records"):
        ist_bu = str(zugang.get("produkt", "klv")) == "bu"
        alle_events.append(
            _event(
                int(zugang["police_id"]),
                "ZUG",
                0,
                pd.Timestamp(zugang["insurance_start"]).date(),
                BU_BETRAG_ART if ist_bu else "VS",
                float(zugang["bu_rente"] if ist_bu else zugang["sum_insured"]),
                status_code=None,
            )
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
        # Produkt des Vertrags und Produkt seiner Generation muessen
        # zusammenpassen — sonst liefe die Zeile mit fremden
        # Rechnungsgrundlagen still durch Engine und Auswertung (eine
        # BU-Generation traegt z.B. keine KLV-Kosten).
        produkt = str(row.get("produkt", "klv"))
        if produkt_je_generation.get(name) != produkt:
            raise EreignisError(
                f"police {row['police_id']}: produkt {produkt!r} passt nicht "
                f"zur Tarifgeneration {name!r} (produkt "
                f"{produkt_je_generation.get(name)!r})"
            )
        try:
            if produkt == "bu":
                # BU: Uebergaenge aus den Rechnungsgrundlagen des
                # Produkts, transformiert durch die Erfahrungsannahmen
                # (Storno/Beitragsfreistellung/Erhoehung kennt das
                # Beispielprodukt nicht; die zugehoerigen Annahmen wirken
                # daher nur auf KLV-Generationen).
                events = _simuliere_bu_vertrag(
                    row, bu_generationen[name], config.annahmen, config.seed, bis
                )
                scheiben = []
            else:
                events, scheiben = _simuliere_vertrag(
                    row, generationen[name], config.annahmen, config.seed, bis
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
            "ereignis": ereignisse["ereignis"].astype(object),
            "vertragsjahr": ereignisse["vertragsjahr"].astype("int64"),
            "status_date": pd.to_datetime(ereignisse["status_date"]),
            "betrag_art": ereignisse["betrag_art"].astype(object),
            "betrag": ereignisse["betrag"].astype("float64"),
        }
    ).reset_index(drop=True)

    # Statushistorie = nur Zustandswechsel; ERH aendert den Zustand nicht,
    # ZUG ist die POL-Basiszeile selbst (liegt in zugaenge) — beide tragen
    # status_code None. Bei INV/REA faellt der GeVo-Code vom Zielzustand
    # auseinander (INV -> BU, REA -> POL).
    zustaende = ereignisse[ereignisse["status_code"].notna()].copy()
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
