"""Ereignis-Engine: die Buchung der Fortschreibung (Storno/Tod/PEX/Ablauf).

The MUST building block of the stable-kernel paradigm (decision 2026-08-11):
the portfolio is rolled forward as a status history — the contract-level
state process — while every calculated amount (RKW, paid-up sum, benefits)
comes from the stable kernel in-process, never from formulas of this module.

Seit ADR-031 ist die Engine in Ziehung und Buchung geschnitten. Die
ZIEHUNG (``bestand.ziehung``, Ebene 4) sagt, was in der simulierten Welt
geschieht, und liefert eine :class:`~rechner_pipeline.bestand.ziehung.Ereignisliste`
— ohne einen Betrag des Kerns. Die BUCHUNG (dieses Modul, Ebene 3,
:func:`buche`) wendet die Liste mit Betraegen aus dem Kern an und schreibt
Statushistorie, Ledger, Scheiben, Zugaenge und Reduktionen. Eine Anwendung
ohne Simulation (etwa ein Cashflow-Lauf) ruft nur die Buchung mit einer
gegebenen Liste. :func:`fortschreiben` ist die Fassade fuer beides in einem
Aufruf — die Schnittstelle vor ADR-031, unveraendert; sie ist die eine
Stelle, an der die Buchung die Welt ruft (Ratsche ``code_karte``). Die
Buchung ist bitgleich zur ungeteilten Engine: dieselbe Reihenfolge je
Vertragsjahr, dieselben Kernaufrufe.

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
* Beitragsherabsetzung (``RED``) und Teilkuendigung (``TKU``): zwei
  Geschaeftsvorfaelle (Entscheid des Maintainers 2026-10-01, ADR-023), je
  mit EIGENEM Substrom (``HERABSETZUNG_STREAM``, ``TEILKUENDIGUNG_STREAM``,
  Register ``bestand.zufallsstroeme``). Die Herabsetzung zieht je Jahr
  ``j+1 < t`` eines beitragspflichtigen Vertrags (nur solange ein Beitrag
  laeuft, nie nach PEX) und nur in einem Tarif, der sie kennt (nicht bei
  ``red_verfahren = teilkuendigung``, dem uebernommenen Tarif); die
  Teilkuendigung je Jahr ``j+1 < n``, beitragspflichtig, ausfinanziert UND
  nach einer Beitragsfreistellung. Beliebig viele Vorgaenge je Vertrag, in
  jeder Reihenfolge (Entscheid des Maintainers 2026-10-01): Jeder gezogene
  Vorgang wird ausgefuehrt, auf dem Zustand, den der Vertrag dann hat
  (``kern.vorgangsfolge``). Mit beiden Raten 0 (Vorgabe) ist jede Welt
  bitgleich zum Stand davor.
* Stornoabschlag bei Scheiben: WO die Tarif-Grenzen (stoab_min/max)
  greifen und ob eine Scheibe gamma1 traegt, sagt das Tarifwerk der
  GENERATION (``TarifGeneration.tarifwerk()``, Freischaltung Schritt 4):
  Vorgabe je VERTRAG und ohne gamma1 (Tarifplan KLV, :func:`vertrags_rkw`,
  fuer Vertraege ohne Scheiben bit-identisch zur Kern-Verlaufszeile); eine
  uebernommene Generation kann je Baustein abziehen und die Scheiben mit
  voller Beitragsformel rechnen, so wie ihre Abnahmen es getan haben.
* Mitgebrachte Scheiben: Ein uebernommener Vertrag bringt seine
  Alt-Erhoehungen als Bausteine mit (``gates.bestand_uebernehmen``,
  ``fortschreiben(..., scheiben=...)``); die Engine rechnet auf ihnen
  weiter und nummeriert neue Scheiben dahinter. Zurueck gibt sie nur die
  NEUEN Scheiben — wie Historie und Ledger, die der Aufrufer dem
  Uebernahme-Journal nachstellt.

Outputs (:class:`Fortschreibung`): a Statushistorie (follow-up status rows,
schema :data:`~rechner_pipeline.models.bestand.STATUS_HISTORIE_SPALTEN`), an
Ereignis-Ledger with the kernel-computed amounts (schema
:data:`~rechner_pipeline.models.bestand.LEDGER_SPALTEN`) and the
Erhoehungsscheiben (schema
:data:`~rechner_pipeline.models.bestand.SCHEIBEN_SPALTEN`).

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import math
from typing import Any, Dict, List, Mapping, NamedTuple, Tuple

import numpy as np
import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.bestand.schichten import schichten_je_police
from rechner_pipeline.kern.beitragsreduktion import TEILKUENDIGUNG
from rechner_pipeline.kern.vorgangsfolge import (
    Vertragsstand,
    Vorgangsergebnis,
    tku_umfang_fuer,
    vorgang,
)
from rechner_pipeline.kern.korrekturschicht import (
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.models.bestand import (
    AKTIVE_STATUS,
    LEDGER_SPALTEN,
    SCHEIBEN_NAMES,
    SCHEIBEN_SPALTEN,
    STAMM_NAMES,
    STAMM_SPALTEN,
    REDUKTIONEN_SPALTEN,
    REDUKTION_EREIGNISSE,
    STATUS_HISTORIE_SPALTEN,
    bu_model_point_kwargs,
    model_point_kwargs,
    reduktion_ereignis,
)
# Die Ziehung (Ebene 4): die EINE Kante der Buchung in die Welt. Ueber sie
# kommen die Stromkonstanten (fuer Leser, die sie hier erwarten), die Codes
# der Ereignisliste, der gemeinsame Fehler und die Fassade zum Erzeuger.
from rechner_pipeline.bestand.ziehung import (  # noqa: F401 — Re-Exporte
    EREIGNIS_STREAM,
    ERH,
    HERABSETZUNG_STREAM,
    INV,
    PEX,
    REA,
    RED,
    STO,
    TEILKUENDIGUNG_STREAM,
    TKU,
    TOD,
    Ereignisliste,
    EreignisError,
    bu_uebergang,
    neuzugaenge as _neuzugaenge_der_welt,
    ziehe,
    ziehe_bu_vertrag,
    ziehe_vertrag,
    zugangslage as _zugangslage,
)

#: Betrags-Art der BU-GeVos: die von diesem Geschaeftsvorfall betroffene
#: versicherte Jahresrente (Bezugsgroesse der Nachweisung) — bei
#: Invalidisierung die beginnende, bei Reaktivierung/Tod/Ablauf aus dem
#: Leistungsbezug die endende Rente. Das Beispielprodukt zahlt weder
#: Todesfall- noch Erlebensfallleistung; solche GeVos tragen 0.
BU_BETRAG_ART = "BU_Jahresrente"
#: Betragsart des gebuchten Bruttojahresbeitrags (Zugang und Erhoehung).
BJB_BETRAG_ART = "BJB"


def _bjb(kern: Rechenkern, jahr: int = 0) -> float:
    """Der tarifliche Bruttojahresbeitrag im Vertragsjahr ``jahr``.

    Dieselbe Groesse, die die Bewertung fuehrt (``auswertung.beitraege``):
    VS mal Bxt, und null, sobald die Beitragszahlungsdauer abgelaufen ist.
    Der Beitrag wird GERECHNET, nicht geliefert — er folgt aus dem Kern
    dieses Vertrags (Betragsbindung T20-04).
    """
    if jahr >= kern.mp.t:
        return 0.0
    return float(kern.gross_annual_premium())

#: Sentinel fuer "Argument nicht gesetzt" (None ist ein gueltiger Wert:
#: GeVos ohne Zustandswechsel).
_KEIN_ARGUMENT = object()


class Fortschreibung(NamedTuple):
    """Ergebnis von :func:`fortschreiben` (fuenf deterministische Tabellen).

    ``zugaenge`` sind die waehrend der Fortschreibung entstandenen
    Neuzugaenge (POL-Basiszeilen). :func:`mit_zugaengen` (stamm, zugaenge)
    setzt beide zum Gesamtbestand zusammen; GEFUEHRT ist er erst nach
    :func:`rechner_pipeline.bestand.fuehrung.fuehre_fort`, das den
    juengsten Journalstand auf den Stamm projiziert (siehe
    ``cli_fortschreibung``).
    """

    historie: pd.DataFrame
    ledger: pd.DataFrame
    scheiben: pd.DataFrame
    zugaenge: pd.DataFrame
    reduktionen: pd.DataFrame


def _add_years(d: _dt.date, years: int) -> _dt.date:
    return _dt.date(d.year + years, d.month, 1)


def _vertragsjahr(beginn: _dt.date, datum: _dt.date) -> int:
    """Volle Vertragsjahre zwischen Beginn und Datum (Monatszaehlung).

    Alle Daten des Stamms liegen auf dem Monatsersten, deshalb genuegt die
    Monatsdifferenz. Dieselbe Rechnung wie in ``gates.bestand_uebernehmen``
    — Zugangsjahr und gebuchtes Vertragsjahr muessen zusammenpassen.
    """
    monate = (datum.year - beginn.year) * 12 + (datum.month - beginn.month)
    return max(0, monate // 12)


def _leerer_frame(spalten) -> pd.DataFrame:
    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in spalten})


class _Vertrag:
    """Grundscheibe + Erhoehungsscheiben eines Vertrags (Schichtungsprinzip).

    Kapselt die Aggregation der Kern-Betraege ueber alle Scheiben; jede
    Scheibe rechnet auf ihrem eigenen Modellpunkt, das Vertragsjahr einer
    Scheibe ist um ihr Erhoehungsjahr versetzt. ``tarifwerk`` sind die
    Schalter der Generation (``TarifGeneration.tarifwerk()``),
    ``mitgebracht`` die Bausteine, die ein uebernommener Vertrag schon
    hat — sie liegen VOR dem ersten simulierten Jahr.
    """

    def __init__(
        self,
        mp: ModelPoint,
        *,
        tarifwerk: Mapping[str, Any],
        mitgebracht: List[Tuple[int, float, Rechenkern]] = (),
        schicht: Tuple[Any, int] | None = None,
    ) -> None:
        self.grund_mp = mp
        self.grund = Rechenkern(mp)
        # Das Tarifwerk der Generation hat keine Vorgabe (Pruefrunde I, I14):
        # Wer den Vertrag fuehrt, nennt es — vorher galt ohne Angabe still das
        # des eigenen Geschaefts.
        self.tarifwerk = dict(tarifwerk)
        # Der Umfang der Teilkuendigung ist der des Bedingungswerks, das das
        # Verfahren nennt, wenn ihn das Tarifwerk nicht ausdrueckt (Entscheid
        # B1 vom 2026-10-01; dieselbe Regel wie ``TarifGeneration.tarifwerk``).
        self.tarifwerk.setdefault("tku_umfang", tku_umfang_fuer(
            str(self.tarifwerk["red_verfahren"])))
        self.scheiben: List[Tuple[int, float, Rechenkern]] = [
            (int(jahr), float(vs), kern) for jahr, vs, kern in mitgebracht
        ]  # (jahr, vs, kern)
        #: Korrekturschicht (Schichtparameter, monate_ta) eines uebernommenen
        #: Vertrags — Storno zahlt Basiswert plus Schichtwert
        #: (wertkontinuierlich, Ausgestaltung des Tarifplans; Grundsatz-
        #: dokumentation 9.7). Tod und Ablauf sind unberuehrt (feste Summe,
        #: Terminalbedingung), eine Beitragsfreistellung absorbiert — nach
        #: ihr gibt es kein Storno mehr, die Schicht ist damit erledigt.
        self.schicht = schicht
        #: Der Zustand in der Vorgangsfolge (``kern.vorgangsfolge``), sobald
        #: der erste Herabsetzungs- oder Teilkuendigungsvorgang gebucht ist —
        #: ab dann rechnet der Vertrag ueber ihn. Davor None: Ein Vertrag
        #: ohne Vorgang rechnet unveraendert ueber seine Bausteine.
        self.stand: Vertragsstand | None = None

    @property
    def kennt_herabsetzung(self) -> bool:
        """Ob der Tarif eine Beitragsherabsetzung kennt. Der uebernommene
        Tarif (``red_verfahren = teilkuendigung``) kennt nur EINEN Vorgang —
        bei der Quelle "Herabsetzung" genannt, im Vokabular der PLV die
        Teilkuendigung (Entscheid des Maintainers 2026-10-01)."""
        return str(self.tarifwerk["red_verfahren"]) != TEILKUENDIGUNG

    def _stand(self, beitragsfrei_ab: int | None) -> Vertragsstand:
        if self.stand is None:
            stand = Vertragsstand.anfang(
                self.grund, [(j, k) for j, _, k in self.scheiben],
                stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"]),
                tku_umfang=str(self.tarifwerk["tku_umfang"]),
                schicht=self.schicht)
            if beitragsfrei_ab is not None:
                stand = stand.nach_pex(beitragsfrei_ab)
            self.stand = stand
        return self.stand

    def vorgang(
        self, jahr: int, anteil: float, verfahren: str, beitragsfrei_ab: int | None,
    ) -> Vorgangsergebnis:
        """Eine Beitragsherabsetzung oder Teilkuendigung ausfuehren — auf dem
        Zustand, den der Vertrag JETZT hat (``kern.vorgangsfolge``: jeder
        Vorgang wirkt proportional auf den aktuellen Zustand).

        Die Korrekturschicht geht beim ersten Vorgang nach der Verankerung
        VOLLSTAENDIG in die Neuberechnung ein (Entscheid des Maintainers
        2026-09-15): bei der Herabsetzung in die beitragsfreie Summe des
        umgewandelten Teils der Grundversicherung, bei der Teilkuendigung in
        die Auszahlung. Danach traegt der Vertrag keine Schicht mehr.
        """
        stand, ergebnis = self._stand(beitragsfrei_ab).nach_vorgang(
            vorgang(jahr, anteil, verfahren))
        self.stand = stand
        self.schicht = stand.schicht
        return ergebnis

    def pex(self, jahr: int) -> float:
        """Die Beitragsfreistellung buchen; liefert die beitragsfreie Summe."""
        if self.stand is not None:
            self.stand = self.stand.nach_pex(jahr)
            return self.stand.vs_bfr()
        return self.beitragsfreie_summe(jahr)

    def leistung(self, pex_summe: float | None) -> float:
        """Todesfall- bzw. Ablaufleistung: die gefuehrte Summe, nach der
        Beitragsfreistellung die beitragsfreie Summe — nach Vorgaengen die
        des Zustands."""
        if self.stand is not None:
            return self.stand.leistung()
        if pex_summe is not None:
            return pex_summe
        return self.gesamt_vs()

    def gesamt_vs(self) -> float:
        if self.stand is not None:
            return self.stand.gesamt_vs()
        return self.grund_mp.sum_insured + sum(vs for _, vs, _ in self.scheiben)

    def erhoehe(self, jahr: int, vs: float) -> ModelPoint:
        # Scheiben-Regel zentral im Kern (erhoehungs_scheibe); ob die
        # Scheibe gamma1 traegt, sagt das Tarifwerk der Generation.
        mp = erhoehungs_scheibe(
            self.grund_mp, jahr, vs,
            gamma1_uebernehmen=bool(self.tarifwerk["scheiben_mit_gamma1"]),
        )
        self.scheiben.append((jahr, vs, Rechenkern(mp)))
        if self.stand is not None:
            # Nach Vorgaengen ist die neue Scheibe ein weiterer, gewoehnlicher
            # Baustein des Vertrags in seinem aktuellen Zustand.
            self.stand = self.stand.nach_erhoehung(jahr, self.scheiben[-1][2])
        return mp

    def rkw(self, jahr: int) -> float:
        if self.stand is not None:
            # Der Vertrag rechnet ueber seinen Zustand in der Vorgangsfolge.
            return self.stand.rkw(jahr)
        wert = vertrags_rkw(
            self.grund, [(erh_jahr, kern) for erh_jahr, _, kern in self.scheiben], jahr,
            stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"]),
        )
        if schicht_traegt(self.schicht, 12 * jahr):
            parameter, monate_ta = self.schicht
            wert += schichtwert_bei(parameter, monate_ta, self.grund_mp, 12 * jahr)
        return wert

    def beitragsfreie_summe(self, a0: int) -> float:
        summe = self.grund.beitragsfreie_summe(a0) + sum(
            kern.beitragsfreie_summe(a0 - erh_jahr)
            for erh_jahr, _, kern in self.scheiben
        )
        # Eine Beitragsfreistellung NACH der Verankerung fuehrt die
        # Korrekturschicht wertstetig in die beitragsfreie Summe ueber
        # (Entscheid des Maintainers 2026-09-15). Vorher fiel sie hier
        # stillschweigend heraus — und das, obwohl rkw() eine Methode
        # darueber dieselbe Schicht sehr wohl mitrechnet. Die gebuchte
        # VS_bfr ist eine garantierte Leistung; sie traegt den Wert.
        return summe + zuschlag_bei_pex(self.schicht, self.grund, a0)


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
        # Der eigene Bestand rechnet seine Betraege selbst -- hier ist
        # das der Normalfall und keine Einschraenkung. Bemerkenswert wird
        # die Angabe erst im uebernommenen Bestand, wo daneben Betraege
        # aus der Lieferung stehen.
        "betrag_herkunft": "gerechnet",
    }


def _keine_weiteren(police_id: int, offen: int) -> None:
    """Jedes Ereignis der Liste wird gebucht — oder die Liste passt nicht
    zum Vertrag (nach seinem Ende, jenseits des Horizonts, vor seinem
    Zugang). Fail-fast statt stillem Verwerfen: Eine Ziehung, die nicht in
    die Buecher kommt, waere unsichtbar."""
    if offen:
        raise EreignisError(
            f"police {police_id}: {offen} Ereignis(se) der Liste bleiben "
            "ungebucht — nach dem Ende des Vertrags, jenseits des Horizonts "
            "oder vor dem Zugang; die Liste passt nicht zum Vertrag")


def _ohne_parameter(e: Mapping[str, Any]) -> bool:
    return math.isnan(float(e["anteil"])) and not str(e["verfahren"] or "")


def _regelverstoesse(
    row: Mapping[str, Any],
    ereignisse,
    ab_jahr: int,
    pex_jahr: int | None,
    *,
    tarifwerk: Mapping[str, Any],
) -> List[str]:
    """Die Liste EINES KLV-Vertrags gegen die Regeln der Welt halten
    (Fehlerlisten-Idiom, leer = buchbar).

    Die Ziehung zieht nur, was der Zustand zulaesst (Modul-Docstring von
    ``bestand.ziehung``). Eine Liste, die von aussen kommt, kann mehr
    behaupten; die Buchung bucht sie nicht still (Pruefung der
    merge-session, Befund B1): Der Wirkungstag ist der Jahrestag des
    Vertragsjahrs; die Beitragsfreistellung kommt hoechstens einmal, nur
    beitragspflichtig und nicht an einem beitragsfrei uebernommenen
    Vertrag; nach ihr gibt es kein Storno, keine Erhoehung und keine
    Herabsetzung; kein Storno und keine Teilkuendigung im Ablaufjahr, keine
    Erhoehung und keine Herabsetzung nach dem Beitragsende, keine
    Herabsetzung in einem Tarif, der sie nicht kennt. Anteil und Verfahren
    tragen nur Herabsetzung und Teilkuendigung, den Satz ohne Verfahren die
    Erhoehung, die uebrigen Ereignisse nichts. Was nach dem Ende des
    Vertrags steht, meldet die Buchung selbst (``_keine_weiteren``); einen
    fremden Code ebenso.
    """
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    t = int(row["premium_duration"])
    kennt_herabsetzung = str(tarifwerk["red_verfahren"]) != TEILKUENDIGUNG
    fehler: List[str] = []
    beitragsfrei_ab: int | None = pex_jahr
    for e in ereignisse:
        jahr, code = int(e["vertragsjahr"]), str(e["ereignis"])
        wo = f"{code} im Vertragsjahr {jahr}"
        jahrestag = _add_years(start, jahr)
        if pd.Timestamp(e["wirkungstag"]).date() != jahrestag:
            fehler.append(f"{wo}: Wirkungstag {pd.Timestamp(e['wirkungstag']).date().isoformat()} "
                          f"ist nicht der Jahrestag {jahrestag.isoformat()}")
        if code in REDUKTION_EREIGNISSE:
            if math.isnan(float(e["anteil"])) or not str(e["verfahren"] or ""):
                fehler.append(f"{wo}: ohne Anteil oder Verfahren")
        elif code == ERH:
            if math.isnan(float(e["anteil"])) or str(e["verfahren"] or ""):
                fehler.append(f"{wo}: braucht einen Satz und kein Verfahren")
        elif code in (TOD, STO, PEX) and not _ohne_parameter(e):
            fehler.append(f"{wo}: traegt Anteil oder Verfahren, das Ereignis hat keine")
        if code == PEX:
            if beitragsfrei_ab is not None:
                fehler.append(f"{wo}: zweite Beitragsfreistellung — beitragsfrei seit Jahr {beitragsfrei_ab}")
            elif not jahr < t:
                fehler.append(f"{wo}: Beitragsfreistellung nach dem Beitragsende (t={t})")
            beitragsfrei_ab = jahr
        elif code == STO:
            if beitragsfrei_ab is not None:
                fehler.append(f"{wo}: Storno nach der Beitragsfreistellung im Jahr {beitragsfrei_ab}")
            if not jahr < n:
                fehler.append(f"{wo}: Storno im Ablaufjahr (n={n})")
        elif code == ERH:
            if beitragsfrei_ab is not None:
                fehler.append(f"{wo}: Erhoehung nach der Beitragsfreistellung im Jahr {beitragsfrei_ab}")
            elif not jahr < t:
                fehler.append(f"{wo}: Erhoehung nach dem Beitragsende (t={t})")
        elif code == RED:
            if beitragsfrei_ab is not None:
                fehler.append(f"{wo}: Herabsetzung nach der Beitragsfreistellung im Jahr {beitragsfrei_ab}")
            elif not jahr < t:
                fehler.append(f"{wo}: Herabsetzung nach dem Beitragsende (t={t})")
            elif not kennt_herabsetzung:
                fehler.append(f"{wo}: Herabsetzung in einem Tarif, der sie nicht kennt")
        elif code == TKU:
            if not jahr < n:
                fehler.append(f"{wo}: Teilkuendigung im Ablaufjahr (n={n})")
        if code in (TOD, STO):
            break
    return fehler


def _bu_regelverstoesse(row: Mapping[str, Any], ereignisse) -> List[str]:
    """Die Liste EINES BU-Vertrags: Wirkungstag am Jahrestag, keine Parameter
    (die Zustandsregeln prueft die Buchung selbst)."""
    start = pd.Timestamp(row["insurance_start"]).date()
    fehler: List[str] = []
    for e in ereignisse:
        jahr, code = int(e["vertragsjahr"]), str(e["ereignis"])
        jahrestag = _add_years(start, jahr)
        if pd.Timestamp(e["wirkungstag"]).date() != jahrestag:
            fehler.append(f"{code} im Vertragsjahr {jahr}: Wirkungstag "
                          f"{pd.Timestamp(e['wirkungstag']).date().isoformat()} ist nicht der "
                          f"Jahrestag {jahrestag.isoformat()}")
        if code in (INV, REA, TOD) and not _ohne_parameter(e):
            fehler.append(f"{code} im Vertragsjahr {jahr}: traegt Anteil oder Verfahren, "
                          "das Ereignis hat keine")
    return fehler


def _je_jahr(ereignisse) -> Dict[int, List[Mapping[str, Any]]]:
    aus: Dict[int, List[Mapping[str, Any]]] = {}
    for e in ereignisse:
        aus.setdefault(int(e["vertragsjahr"]), []).append(e)
    return aus


def _buche_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    bis: _dt.date,
    ereignisse,
    ab_jahr: int = 0,
    pex_jahr: int | None = None,
    *,
    tarifwerk: Mapping[str, Any],
    mitgebracht: List[Tuple[int, float, Rechenkern]] = (),
    schicht: Tuple[Any, int] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Die Ereignisse EINES KLV-Vertrags buchen; returns (events, NEUE
    Scheiben, Herabsetzungen).

    ``ereignisse`` sind die Eintraege der Ereignisliste dieses Vertrags
    (:func:`rechner_pipeline.bestand.ziehung.ziehe_vertrag`), in
    Zugreihenfolge. Die Buchung laeuft ueber dieselben Vertragsjahre wie
    die Ziehung und wendet je Jahr die Ereignisse in ihrer Reihenfolge an,
    mit Betraegen aus dem Kern: Tod und Storno beenden den Vertrag, die
    Beitragsfreistellung fixiert die beitragsfreie Summe, Herabsetzung und
    Teilkuendigung wirken auf den Zustand in der Vorgangsfolge, die
    Erhoehung legt eine Scheibe an. Der Ablauf ist kein Ereignis der Liste:
    Ihn bucht die Fuehrung, wenn der Vertrag alle ``n`` Jahre ueberlebt hat
    und ``insurance_end <= bis``.

    ``ab_jahr`` ist das erste zu simulierende Vertragsjahr — 0 fuer
    eigenes Geschaeft, das Zugangsjahr fuer einen uebernommenen Vertrag.
    ``pex_jahr`` setzt ihn beitragsfrei ab diesem Vertragsjahr, ohne die
    Beitragsfreistellung noch einmal zu buchen: Sie ist beim abgebenden
    Unternehmen geschehen, die Uebernahme hat sie bereits verbucht.
    """
    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    verstoesse = _regelverstoesse(row, ereignisse, ab_jahr, pex_jahr, tarifwerk=tarifwerk)
    if verstoesse:
        raise EreignisError(f"police {police_id}: " + "; ".join(verstoesse[:3]))

    vertrag = _Vertrag(
        ModelPoint(**model_point_kwargs(row, generation_fields)),
        tarifwerk=tarifwerk, mitgebracht=mitgebracht, schicht=schicht,
    )

    events: List[Dict[str, Any]] = []
    scheiben: List[Dict[str, Any]] = []
    reduktionen: List[Dict[str, Any]] = []

    def buche(
        code: str, jahr: int, art: str, betrag: float, status: Any = _KEIN_ARGUMENT
    ) -> None:
        events.append(
            _event(police_id, code, jahr, _add_years(start, jahr), art, betrag, status)
        )

    def reduziere_vertrag(jahr: int, anteil: float, verfahren: str) -> None:
        """Herabsetzung (RED) oder Teilkuendigung (TKU) ausfuehren und buchen
        — welcher Vorgang, sagt das Verfahren (``reduktion_ereignis``). Der
        Vorgang wirkt auf den Zustand, den der Vertrag jetzt hat; frueheren
        Vorgaengen folgt er, statt verworfen zu werden (Entscheid des
        Maintainers 2026-10-01: beliebig viele, in jeder Reihenfolge)."""
        code = reduktion_ereignis(verfahren)
        ergebnis = vertrag.vorgang(jahr, anteil, verfahren, beitragsfrei_ab)
        # Die neue Gesamtsumme (nach einer Beitragsfreistellung die neue
        # beitragsfreie Summe). Kein Statuswechsel.
        buche(code, jahr,
              "VS_teilkuendigung" if code == "TKU" else "VS_herabsetzung",
              ergebnis.vs_neu, status=None)
        if ergebnis.absorbiert:
            # Die absorbierte Korrekturschicht als eigene Zeile. Ohne sie
            # verschwaende der Betrag aus dem Ausweis: Die Spalte
            # korrekturschicht des Abschlusses faellt ab hier auf null
            # (dieselbe Konstruktion wie dDK_uebernahme beim Zugang).
            buche(code, jahr, "dDK_absorption", ergebnis.absorbiert, status=None)
        if code == "TKU":
            # Der gekuendigte Anteil wird AUSGEZAHLT — Rueckkaufswert des
            # betroffenen Teils plus die vollstaendig absorbierte
            # Korrekturschicht. IMMER gebucht (Angriffsrunde 4 der Pruefrunde
            # T27). Faellt die Summe unter null, wird auf NULL GEKAPPT
            # (Entscheid des Maintainers 2026-09-26), und der gekappte
            # Betrag steht als Kappung_teilkuendigung im Ledger.
            auszahlung = float(ergebnis.auszahlung)
            buche(code, jahr, "RKW_teilkuendigung", max(0.0, auszahlung), status=None)
            if auszahlung < 0.0:
                buche(code, jahr, "Kappung_teilkuendigung", -auszahlung, status=None)
        reduktionen.append({
            "police_id": police_id,
            "reduktion_jahr": jahr,
            "reduktion_datum": pd.Timestamp(_add_years(start, jahr)),
            "anteil": anteil,
            "verfahren": verfahren,
        })

    # Ein beitragsfrei uebernommener Vertrag bringt seinen Zustand mit.
    # Die beitragsfreie Summe wurde bei der Beitragsfreistellung fixiert
    # und wird hier aus demselben Vertragsjahr rekonstruiert — dieselbe
    # Rechnung wie in der Uebernahme, damit Buchung und Fortschreibung
    # nicht auseinanderlaufen.
    beitragsfrei_ab: int | None = pex_jahr
    pex_summe = (
        vertrag.beitragsfreie_summe(pex_jahr) if pex_jahr is not None else 0.0
    )
    je_jahr = _je_jahr(ereignisse)
    offen = sum(len(v) for v in je_jahr.values())
    horizont_erreicht = False

    for j in range(ab_jahr, n):
        stichtag_jahr = _add_years(start, j + 1)
        if stichtag_jahr > bis:
            horizont_erreicht = True
            break
        # Die Ereignisse des Jahres in der Reihenfolge der Ziehung (Tod,
        # Storno, Beitragsfreistellung, Herabsetzung, Teilkuendigung,
        # Erhoehung) — die Betraege kommen aus dem Kern, zum Zustand, den
        # der Vertrag JETZT hat.
        for e in je_jahr.get(j + 1, ()):
            offen -= 1
            code = str(e["ereignis"])
            if code == TOD:
                buche("TOD", j + 1, "Todesfallleistung", vertrag.leistung(
                    pex_summe if beitragsfrei_ab is not None else None))
                _keine_weiteren(police_id, offen)
                return events, scheiben, reduktionen
            if code == STO:
                buche("STO", j + 1, "RKW", vertrag.rkw(j + 1))
                _keine_weiteren(police_id, offen)
                return events, scheiben, reduktionen
            if code == PEX:
                beitragsfrei_ab = j + 1
                pex_summe = vertrag.pex(j + 1)
                buche("PEX", j + 1, "VS_bfr", pex_summe)
            elif code in REDUKTION_EREIGNISSE:
                reduziere_vertrag(j + 1, float(e["anteil"]), str(e["verfahren"]))
            elif code == ERH:
                # Dynamische Erhoehung: neue Scheibe, kein Statuswechsel. Auch
                # nach Vorgaengen (Entscheid 2026-09-26): die Erhoehung bezieht
                # sich auf die gefuehrte Summe danach.
                betrag = float(e["anteil"]) * vertrag.gesamt_vs()
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
                        # Schicht-eigene Rechnungsgrundlage aus dem
                        # Kern-Konstruktor persistieren (ADR-011): die
                        # Scheibe ist aus ihren Parametern reproduzierbar.
                        "gamma1": mp_s.gamma1,
                    }
                )
                buche("ERH", j + 1, "VS_erhoehung", betrag, status=None)
                # Die Erhoehung bewegt eine Summe UND einen Beitrag: die
                # neue Scheibe ist ein eigener Modellpunkt mit eigenem
                # Bruttojahresbeitrag (dieselbe Zerlegung wie in der
                # Bewertung). Eigene Zeile, eigene Betragsart.
                buche("ERH", j + 1, BJB_BETRAG_ART,
                      _bjb(vertrag.scheiben[-1][2]), status=None)
            else:
                raise EreignisError(
                    f"police {police_id}: Ereignis {code!r} der Liste ist fuer "
                    "einen KLV-Vertrag nicht buchbar")

    _keine_weiteren(police_id, offen)
    if not horizont_erreicht:
        # Ablauf: alle n Jahre ueberlebt und insurance_end <= bis.
        buche("ABL", n, "Ablaufleistung", vertrag.leistung(
            pex_summe if beitragsfrei_ab is not None else None))
    return events, scheiben, reduktionen


def _simuliere_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
    seed: int,
    bis: _dt.date,
    ab_jahr: int = 0,
    pex_jahr: int | None = None,
    *,
    tarifwerk: Mapping[str, Any],
    mitgebracht: List[Tuple[int, float, Rechenkern]] = (),
    schicht: Tuple[Any, int] | None = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Simulate one contract: ziehen, dann buchen (die Fassade je Vertrag).

    Die Schnittstelle vor ADR-031; liefert (events, NEUE Scheiben,
    Herabsetzungen) wie :func:`_buche_vertrag`.
    """
    gezogen = ziehe_vertrag(
        row, generation_fields, annahmen, seed, bis, ab_jahr, pex_jahr,
        tarifwerk=tarifwerk,
    )
    return _buche_vertrag(
        row, generation_fields, bis, gezogen, ab_jahr, pex_jahr,
        tarifwerk=tarifwerk, mitgebracht=mitgebracht, schicht=schicht,
    )


def _buche_bu_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    bis: _dt.date,
    ereignisse,
    ab_jahr: int = 0,
    bu_seit: int | None = None,
) -> List[Dict[str, Any]]:
    """Die Ereignisse EINES BU-Vertrags buchen; liefert die gebuchten GeVos.

    Der Zustandsprozess ist derselbe, den der Kern bewertet; welche
    Uebergaenge geschehen, sagt die Ziehung
    (:func:`rechner_pipeline.bestand.ziehung.ziehe_bu_vertrag`). Hier wird
    gebucht: die Invalidisierung mit der beginnenden Rente (Zustand BU),
    die Reaktivierung mit der endenden (Zustand POL), der Tod mit der
    endenden Rente im Leistungsbezug und mit 0 aus dem Anwaerterstand, der
    Ablauf mit der Rente, wenn der Vertrag im Leistungsbezug endet.

    Gitter und Konventionen wie beim KLV-Pfad: Vertragsjahr ``j`` läuft von
    Jahrestag ``j`` bis ``j+1``, Ereignisse werden am Jahrestag ``j+1``
    gebucht.
    """
    from rechner_pipeline.kern.produkte.bu import AKTIV, BU_ZUSTAND

    police_id = int(row["police_id"])
    start = pd.Timestamp(row["insurance_start"]).date()
    n = int(row["duration"])
    rente = float(row["bu_rente"])
    verstoesse = _bu_regelverstoesse(row, ereignisse)
    if verstoesse:
        raise EreignisError(f"police {police_id}: " + "; ".join(verstoesse[:3]))
    events: List[Dict[str, Any]] = []

    def buche(ereignis: str, jahr: int, betrag: float, status: Any) -> None:
        events.append(
            _event(
                police_id, ereignis, jahr, _add_years(start, jahr),
                BU_BETRAG_ART, betrag, status,
            )
        )

    # Wie beim KLV-Pfad: Ein uebernommener Vertrag bringt seinen Zustand mit.
    zustand = BU_ZUSTAND if bu_seit is not None else AKTIV
    je_jahr = _je_jahr(ereignisse)
    offen = sum(len(v) for v in je_jahr.values())
    horizont_erreicht = False

    for j in range(ab_jahr, n):
        if _add_years(start, j + 1) > bis:
            horizont_erreicht = True
            break
        for e in je_jahr.get(j + 1, ()):
            offen -= 1
            code = str(e["ereignis"])
            if zustand == AKTIV:
                if code == INV:
                    # Invalidisierung: die BU-Rente beginnt (Beitragsbefreiung
                    # ist im Produkt implizit — Beitraege laufen nur in aktiv).
                    buche("INV", j + 1, rente, "BU")
                    zustand = BU_ZUSTAND
                elif code == TOD:
                    buche("TOD", j + 1, 0.0, "TOD")
                    _keine_weiteren(police_id, offen)
                    return events
                else:
                    raise EreignisError(
                        f"police {police_id}: Ereignis {code!r} der Liste ist im "
                        "Anwaerterstand eines BU-Vertrags nicht buchbar")
            else:
                if code == REA:
                    # Reaktivierung: die Rente endet, der Vertrag ist wieder
                    # Anwaerter (und wieder beitragspflichtig).
                    buche("REA", j + 1, rente, "POL")
                    zustand = AKTIV
                elif code == TOD:
                    buche("TOD", j + 1, rente, "TOD")
                    _keine_weiteren(police_id, offen)
                    return events
                else:
                    raise EreignisError(
                        f"police {police_id}: Ereignis {code!r} der Liste ist im "
                        "Leistungsbezug eines BU-Vertrags nicht buchbar")

    _keine_weiteren(police_id, offen)
    if not horizont_erreicht:
        # Ablauf: die Rente endet spaetestens mit dem Vertrag.
        buche("ABL", n, rente if zustand == BU_ZUSTAND else 0.0, "ABL")
    return events


def _simuliere_bu_vertrag(
    row: Mapping[str, Any],
    generation_fields: Mapping[str, Any],
    annahmen,
    seed: int,
    bis: _dt.date,
    ab_jahr: int = 0,
    bu_seit: int | None = None,
) -> List[Dict[str, Any]]:
    """Simuliere einen BU-Vertrag: ziehen, dann buchen (die Fassade je Vertrag)."""
    gezogen = ziehe_bu_vertrag(
        row, generation_fields, annahmen, seed, bis, ab_jahr=ab_jahr, bu_seit=bu_seit,
    )
    return _buche_bu_vertrag(
        row, generation_fields, bis, gezogen, ab_jahr=ab_jahr, bu_seit=bu_seit,
    )


def _annahmen_pruefen(config: BestandConfig) -> None:
    """Die Erfahrungsannahmen der Welt (die Fassade fragt sie vor der Ziehung,
    wie vor ADR-031; die Buchung braucht sie nicht)."""
    konfig_fehler = config.annahmen.validate()
    if konfig_fehler:
        raise EreignisError("; ".join(konfig_fehler))


def _stamm_pruefen(stamm: pd.DataFrame) -> None:
    """Die Waechter des Basisbestands (fail-fast, vor Ziehung und Buchung)."""
    fehlend = [c for c in STAMM_NAMES if c not in stamm.columns]
    if fehlend:
        raise EreignisError(f"Stamm-Spalten fehlen: {fehlend}")
    # Zwei zulaessige Formen, unterschieden am Bestandszugang:
    #
    # EIGENES Geschaeft (Zugang = Versicherungsbeginn) muss ein
    # Ursprungsbestand sein. Sonst waere es eine Zeitscheiben- oder
    # Journalsicht, und die Engine simulierte sie ab insurance_start ein
    # zweites Mal.
    #
    # UEBERNOMMENES Geschaeft (Zugang spaeter) bringt seinen Zustand mit:
    # Es ist der Sinn einer Uebernahme, dass der Vertrag nicht bei null
    # anfaengt. Erlaubt ist genau der Zustand BEIM ZUGANG — traegt der
    # Stamm einen spaeteren, ist der Bestand bereits fortgeschrieben und
    # wuerde es ein zweites Mal.
    if len(stamm):
        uebernommen = (
            pd.to_datetime(stamm["bestandszugang"])
            > pd.to_datetime(stamm["insurance_start"])
        )
        eigen = stamm[~uebernommen]
        if len(eigen) and not (
            (eigen["status_code"] == "POL").all() & (eigen["status_id"] == 1).all()
        ):
            raise EreignisError(
                "Stamm ist kein Basisbestand (nur status_code POL mit status_id 1): "
                "Zeitscheiben oder Historie-Sichten koennen nicht erneut "
                "fortgeschrieben werden — die Engine simuliert ab insurance_start"
            )
        uebern = stamm[uebernommen]
        if len(uebern):
            tot = uebern[~uebern["status_code"].isin(AKTIVE_STATUS)]
            if len(tot):
                raise EreignisError(
                    f"{len(tot)} uebernommene Vertraege stehen in einem "
                    f"Endzustand (z. B. police {int(tot['police_id'].iloc[0])}, "
                    f"{tot['status_code'].iloc[0]}) — ein beendeter Vertrag "
                    "wird nicht uebernommen und nicht fortgeschrieben"
                )
            spaet = uebern[
                pd.to_datetime(uebern["status_date"])
                > pd.to_datetime(uebern["bestandszugang"])
            ]
            if len(spaet):
                raise EreignisError(
                    f"{len(spaet)} uebernommene Vertraege tragen einen "
                    "Zustandswechsel NACH ihrem Bestandszugang (z. B. police "
                    f"{int(spaet['police_id'].iloc[0])}): Der Bestand ist "
                    "bereits fortgeschrieben und wuerde ein zweites Mal "
                    "simuliert — den Zugangsstand uebergeben"
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


def _zugaenge_bestimmen(
    stamm: pd.DataFrame,
    config: BestandConfig,
    bis: _dt.date,
    *,
    neuzugang_ab: _dt.date | None,
    zugaenge: pd.DataFrame | None,
) -> pd.DataFrame:
    """Die Zugaenge eines Laufs: mitgebracht (Tagesbetrieb), aus dem
    jaehrlichen Erzeuger der Welt (``neuzugang_ab``) oder keine — ein
    Erzeuger je Lauf, mit denselben Waechtern wie vor ADR-031."""
    hat_neuzugang = any(g.neuzugang_pro_jahr > 0 for g in config.generationen)
    if zugaenge is not None and neuzugang_ab is not None:
        raise EreignisError(
            "zugaenge und neuzugang_ab schliessen sich aus — entweder der "
            "jaehrliche Erzeuger (neuzugang_ab) oder mitgebrachte Zugaenge "
            "(Tagesbetrieb), nie beide in einem Lauf"
        )
    if zugaenge is not None:
        return _pruefe_mitgebrachte_zugaenge(stamm, zugaenge)
    if neuzugang_ab is not None and hat_neuzugang:
        neuzugang_ab = pd.Timestamp(neuzugang_ab).date()
        if neuzugang_ab > bis:
            raise EreignisError(
                f"neuzugang_ab {neuzugang_ab.isoformat()} liegt nach dem "
                f"Horizont bis {bis.isoformat()} (vertauschte Argumente?)"
            )
        if len(stamm) and (
            stamm["insurance_start"] >= pd.Timestamp(neuzugang_ab)
        ).any():
            raise EreignisError(
                "Basisbestand enthaelt Vertraege mit Beginn am oder nach dem "
                f"Referenzstichtag {neuzugang_ab.isoformat()} — Neuzugang wuerde "
                "den Zeitraum doppelt besiedeln (ein Erzeuger je Zeitfenster) — "
                "der Basisbestand darf nur Vertraege bis zum Referenzstichtag tragen"
            )
        zugaenge = _neuzugaenge_der_welt(config, neuzugang_ab, bis)
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
        return zugaenge
    return _leerer_frame(STAMM_SPALTEN)


def _vertraege_pruefen(gesamt: pd.DataFrame, config: BestandConfig) -> None:
    """Jeder Vertrag gehoert zu einer Generation der Config, und Produkt des
    Vertrags und Produkt seiner Generation passen zusammen — sonst liefe
    die Zeile mit fremden Rechnungsgrundlagen still durch Ziehung, Buchung
    und Auswertung (eine BU-Generation traegt z.B. keine KLV-Kosten)."""
    generationen = {g.name for g in config.generationen}
    produkt_je_generation = {g.name: g.produkt for g in config.generationen}
    for row in gesamt.to_dict("records"):
        name = str(row["tarif_generation"])
        if name not in generationen:
            raise EreignisError(
                f"police {row['police_id']}: Tarifgeneration {name!r} nicht in Config "
                f"(bekannt: {sorted(generationen)})"
            )
        produkt = str(row.get("produkt", "klv"))
        if produkt_je_generation.get(name) != produkt:
            raise EreignisError(
                f"police {row['police_id']}: produkt {produkt!r} passt nicht "
                f"zur Tarifgeneration {name!r} (produkt "
                f"{produkt_je_generation.get(name)!r})"
            )


def _ereignisse_je_police(ereignisse: pd.DataFrame) -> Dict[int, List[Dict[str, Any]]]:
    """police_id -> ihre Eintraege der Ereignisliste in Zugreihenfolge (lfd)."""
    from rechner_pipeline.bestand.ziehung import EREIGNISLISTE_NAMES

    fehlend = [c for c in EREIGNISLISTE_NAMES if c not in ereignisse.columns]
    if fehlend:
        raise EreignisError(f"Ereignisliste: Spalten fehlen: {fehlend}")
    aus: Dict[int, List[Dict[str, Any]]] = {}
    if len(ereignisse) == 0:
        return aus
    geordnet = ereignisse.sort_values(["police_id", "lfd"], kind="stable")
    for e in geordnet.to_dict("records"):
        aus.setdefault(int(e["police_id"]), []).append(e)
    return aus


def buche(
    stamm: pd.DataFrame,
    config: BestandConfig,
    bis: _dt.date,
    liste: Ereignisliste,
    *,
    merkmale: pd.DataFrame | None = None,
    scheiben: pd.DataFrame | None = None,
    schichten: pd.DataFrame | None = None,
    verankerung: pd.DataFrame | None = None,
) -> Fortschreibung:
    """Die Buchung (ADR-031): eine gegebene Ereignisliste bis ``bis`` auf den
    Basisbestand anwenden, mit Betraegen aus dem Kern.

    ``liste`` ist, was die Welt geschehen laesst
    (:class:`~rechner_pipeline.bestand.ziehung.Ereignisliste`): die
    Zugaenge als POL-Basiszeilen und die Ereignisse aller Vertraege. Die
    Buchung zieht nichts; sie kennt weder Seed noch Annahmen. Jeder Zugang
    bekommt seinen ZUG-Eintrag (Summe und Beitrag), jeder Vertrag wird ab
    seinem Zugang gebucht, jedes Ereignis der Liste kommt in die Buecher
    oder ist ein Fehler. ``scheiben``, ``schichten`` und ``verankerung``
    wie bei :func:`fortschreiben`.

    Returns :class:`Fortschreibung` — dieselben fuenf Tabellen wie
    :func:`fortschreiben`, Byte fuer Byte, wenn die Liste die Ziehung
    derselben Welt ist.
    """
    _stamm_pruefen(stamm)
    bis = pd.Timestamp(bis).date()
    zugaenge = _pruefe_mitgebrachte_zugaenge(stamm, liste.zugaenge)
    gesamt = (
        pd.concat([stamm, zugaenge], ignore_index=True) if len(zugaenge) else stamm
    )
    _vertraege_pruefen(gesamt, config)
    je_police = _ereignisse_je_police(liste.ereignisse)
    fremd = sorted(set(je_police) - set(int(p) for p in gesamt["police_id"]))
    if fremd:
        raise EreignisError(
            f"Ereignisliste nennt Policen, die der Bestand nicht fuehrt: {fremd[:5]}")

    # Rechnungsgrundlagen je Vertrag statt je Generation: Ist eine
    # Generation in Tarifzellen aufgeteilt, steht die Sterbetafel in der
    # Zelle und der Generationsrumpf traegt sie gar nicht. Dieselbe
    # Aufloesung wie die Bewertung — die Simulation muss denselben Tarif
    # rechnen wie der Bericht, sonst laufen sie auseinander.
    from rechner_pipeline.bestand.auswertung import grundlagen_je_police

    # Die Buchung liest die Sicht der Fuehrung (ADR-031): Tarifwerk, Kern-
    # felder, BU-Grundlagen. Seed und Annahmen der Welt kennt sie nicht.
    fuehrung = config.fuehrung()
    grundlagen = grundlagen_je_police(config, merkmale)
    generationen = {g.name: g.generation_fields for g in fuehrung.generationen}
    tarifwerk_je_generation = {g.name: g.tarifwerk for g in fuehrung.generationen}
    mitgebracht_je_police = _mitgebrachte_scheiben(stamm, scheiben, grundlagen)
    try:
        schicht_je_police = schichten_je_police(stamm, schichten, verankerung)
    except ValueError as exc:
        raise EreignisError(str(exc)) from exc
    if schicht_je_police:
        haupt_zugang = stamm.set_index("police_id")
        eigene = [
            pid for pid in schicht_je_police
            if pd.Timestamp(haupt_zugang.loc[pid, "bestandszugang"])
            <= pd.Timestamp(haupt_zugang.loc[pid, "insurance_start"])
        ]
        if eigene:
            raise EreignisError(
                f"schichten: Korrekturschicht an einem eigenen Vertrag "
                f"(police {eigene[:5]}) — nur ein uebernommener Vertrag ist verankert")
    bu_generationen = {
        g.name: g.bu_generation_fields
        for g in fuehrung.generationen
        if g.produkt == "bu"
    }

    alle_events: List[Dict[str, Any]] = []
    alle_scheiben: List[Dict[str, Any]] = []
    alle_reduktionen: List[Dict[str, Any]] = []
    # Zugangs-GeVos: ein ZUG-Ledger-Eintrag je Neuzugang (kein Statuswechsel —
    # die POL-Basiszeile ist der Zugangs-Satz selbst).
    for zugang in zugaenge.to_dict("records"):
        ist_bu = str(zugang.get("produkt", "klv")) == "bu"
        beginn = pd.Timestamp(zugang["insurance_start"]).date()
        alle_events.append(
            _event(
                int(zugang["police_id"]),
                "ZUG",
                0,
                beginn,
                BU_BETRAG_ART if ist_bu else "VS",
                float(zugang["bu_rente"] if ist_bu else zugang["sum_insured"]),
                status_code=None,
            )
        )
        # Ein Zugang bewegt nicht nur eine Summe, sondern auch einen
        # Beitrag — das Neugeschaeft eines Zeitraums wird in beidem
        # gemessen. Zweite Zeile desselben Vorfalls, eigene Betragsart,
        # Betrag aus dem Kern dieses Vertrags.
        gen_name = str(zugang["tarif_generation"])
        if ist_bu:
            from rechner_pipeline.kern.produkte.bu import BU, BUModelPoint

            bjb = float(BU(BUModelPoint(
                **bu_model_point_kwargs(zugang, bu_generationen[gen_name])
            )).bruttobeitrag())
        else:
            bjb = _bjb(Rechenkern(ModelPoint(
                **model_point_kwargs(zugang, generationen[gen_name])
            )))
        alle_events.append(
            _event(int(zugang["police_id"]), "ZUG", 0, beginn,
                   BJB_BETRAG_ART, bjb, status_code=None)
        )
    for row in gesamt.to_dict("records"):
        name = str(row["tarif_generation"])
        pid = int(row["police_id"])
        ab_jahr, zustand, seit = _zugangslage(row)
        produkt = str(row.get("produkt", "klv"))
        try:
            if produkt == "bu":
                # BU: Uebergaenge aus den Rechnungsgrundlagen des Produkts,
                # transformiert durch die Erfahrungsannahmen, gezogen in der
                # Welt; hier die Buchung der Rente.
                events = _buche_bu_vertrag(
                    row, bu_generationen[name], bis, je_police.get(pid, ()),
                    ab_jahr=ab_jahr,
                    bu_seit=seit if zustand == "BU" else None,
                )
                neue_scheiben = []
                neue_reduktionen = []
            else:
                events, neue_scheiben, neue_reduktionen = _buche_vertrag(
                    row, grundlagen(pid, name), bis, je_police.get(pid, ()),
                    ab_jahr=ab_jahr,
                    pex_jahr=seit if zustand == "PEX" else None,
                    tarifwerk=tarifwerk_je_generation[name],
                    mitgebracht=mitgebracht_je_police.get(pid, ()),
                    schicht=(
                        schicht_je_police[pid][:2]
                        if pid in schicht_je_police else None
                    ),
                )
        except EreignisError:
            raise
        except Exception as exc:
            raise EreignisError(
                f"police {row['police_id']}: {type(exc).__name__}: {exc}"
            ) from exc
        alle_events.extend(events)
        alle_scheiben.extend(neue_scheiben)
        alle_reduktionen.extend(neue_reduktionen)

    if alle_reduktionen:
        reduktionen_df = (
            pd.DataFrame(alle_reduktionen)
            .astype(dict(REDUKTIONEN_SPALTEN))
            .sort_values(["police_id"], kind="stable")
            .reset_index(drop=True)[[n for n, _ in REDUKTIONEN_SPALTEN]]
        )
    else:
        reduktionen_df = _leerer_frame(REDUKTIONEN_SPALTEN)

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
            reduktionen_df,
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
            "betrag_herkunft": ereignisse["betrag_herkunft"].astype(object),
        }
    ).reset_index(drop=True)

    # Statushistorie = nur Zustandswechsel; ERH aendert den Zustand nicht,
    # ZUG ist die POL-Basiszeile selbst (liegt in zugaenge) — beide tragen
    # status_code None. Bei INV/REA faellt der GeVo-Code vom Zielzustand
    # auseinander (INV -> BU, REA -> POL).
    zustaende = ereignisse[ereignisse["status_code"].notna()].copy()
    if len(zustaende) == 0:
        return Fortschreibung(
            _leerer_frame(STATUS_HISTORIE_SPALTEN), ledger, scheiben_df,
            zugaenge, reduktionen_df,
        )
    # status_id je Police fortlaufend NACH dem mitgebrachten Stand. Beim
    # eigenen Geschaeft ist das die Basis-POL mit status_id 1, also wie
    # bisher ab 2. Ein beitragsfrei uebernommener Vertrag traegt schon
    # eine 2 (die PEX-Zeile der Uebernahme) und wird ab 3 fortgezaehlt --
    # sonst gaebe es zwei Zeilen mit derselben Nummer, und der Stamm
    # koennte seinen juengsten Journalstand nicht mehr bestimmen.
    mitgebracht = gesamt.set_index("police_id")["status_id"]
    zustaende["status_id"] = (
        zustaende.groupby("police_id").cumcount()
        + 1
        + zustaende["police_id"].map(mitgebracht).astype("int64")
    )
    historie = pd.DataFrame(
        {
            "police_id": zustaende["police_id"].astype("int64"),
            "status_id": zustaende["status_id"].astype("int64"),
            "status_code": zustaende["status_code"].astype(object),
            "status_date": pd.to_datetime(zustaende["status_date"]),
        }
    ).reset_index(drop=True)
    return Fortschreibung(
        historie, ledger, scheiben_df, zugaenge, reduktionen_df)


def fortschreiben(
    stamm: pd.DataFrame,
    config: BestandConfig,
    bis: _dt.date,
    *,
    neuzugang_ab: _dt.date | None = None,
    merkmale: pd.DataFrame | None = None,
    zugaenge: pd.DataFrame | None = None,
    scheiben: pd.DataFrame | None = None,
    schichten: pd.DataFrame | None = None,
    verankerung: pd.DataFrame | None = None,
    liste: Ereignisliste | None = None,
) -> Fortschreibung:
    """Roll the base portfolio forward to ``bis`` — ziehen, dann buchen.

    Die Fassade vor ADR-031, unveraendert in Schnittstelle und Ergebnis:
    Die Welt zieht (:func:`rechner_pipeline.bestand.ziehung.ziehe`, und bei
    ``neuzugang_ab`` ihren jaehrlichen Zugangsstrom), die Fuehrung bucht
    (:func:`buche`). Wer die Liste schon hat (der Tageslauf mit seinem
    Tagesstrom), uebergibt sie als ``liste``: Dann wird nicht gezogen,
    sondern genau diese Liste gebucht — dasselbe wie :func:`buche`; die
    Liste traegt ihre Zugaenge selbst und schliesst ``zugaenge`` und
    ``neuzugang_ab`` aus.

    ``schichten`` und ``verankerung`` (Freischaltung, Schritt 5) sind die
    Korrekturschicht je uebernommenem Vertrag und ihr Verankerungs-
    zeitpunkt (``schichten.parquet``, ``verankerung.parquet`` der
    Uebernahme): Storno zahlt Basiswert plus Schichtwert. Beide Tabellen
    gehoeren zusammen; eine Schicht ohne Anker ist ein Fehler.

    ``scheiben`` (Freischaltung, Schritt 4) sind die MITGEBRACHTEN
    Erhoehungsscheiben uebernommener Vertraege (``scheiben.parquet`` der
    Uebernahme): Bausteine vor dem Bestandszugang, auf denen die Engine
    weiterrechnet — Rueckkaufswert, beitragsfreie Summe, Gesamtsumme und
    die Bezugsgroesse neuer Erhoehungen. Jede Scheibe traegt ihr gamma1
    selbst (ADR-011). Eine Scheibe NACH dem Zugang oder an einem eigenen
    Vertrag ist ein Fehler: Der Bestand waere bereits fortgeschrieben.
    Zurueck kommen nur die NEUEN Scheiben (siehe Modul-Docstring).

    Returns :class:`Fortschreibung` — Statushistorie (state changes only;
    a dynamische Erhoehung changes no state), Ereignis-Ledger (every GeVo
    incl. ERH/ZUG), the created Erhoehungsscheiben and the Neuzugaenge.

    ``neuzugang_ab`` (Referenzstichtag) schaltet den simulierten Neuzugang
    frei: neue Vertraege mit Beginn in ``[neuzugang_ab, bis]`` entstehen aus
    :func:`rechner_pipeline.bestand.generator.neuzugaenge` (Volumen je
    Generation: ``neuzugang_pro_jahr``), erhalten einen ZUG-Ledger-Eintrag
    und werden ab ihrem Beginn mitsimuliert. Der Basisbestand darf dann
    keine Vertraege am oder nach dem Referenzstichtag enthalten (Doppelzaehlung).

    ``zugaenge`` (Tagesbetrieb, Fachkonzept docs/simulation/tagesbetrieb.md)
    bringt die Neuzugaenge MIT, statt sie ueber den jaehrlichen Erzeuger
    zu ziehen: POL-Basiszeilen, die genau wie der simulierte Neuzugang
    ihren ZUG-Eintrag bekommen und ab ihrem Beginn mitsimuliert werden.
    Der Beginn darf hinter ``bis`` liegen (verkauft, Beginn folgt) — dann
    steht der Zugang im Ledger, und die Engine simuliert noch nichts.
    Schliesst ``neuzugang_ab`` aus: ein Erzeuger je Lauf.

    ``stamm`` is the generator's base portfolio (one POL row per contract);
    the event assumptions come from ``config.annahmen``, the amounts from the
    stable kernel. Pure function of (stamm, config, bis, neuzugang_ab) —
    seed-deterministic, the Stamm itself is never mutated. Fail-fast
    guards: only POL base rows
    (an Auskunfts- or Journalsicht fed back in is an error — the engine
    would re-simulate it from insurance_start), unique positive police_id,
    valid event rates, durations within the engine's 0..50 window.
    """
    if liste is not None:
        if zugaenge is not None or neuzugang_ab is not None:
            raise EreignisError(
                "liste schliesst zugaenge und neuzugang_ab aus — die Liste "
                "traegt ihre Zugaenge selbst, ein Erzeuger je Lauf")
        return buche(
            stamm, config, bis, liste, merkmale=merkmale, scheiben=scheiben,
            schichten=schichten, verankerung=verankerung,
        )
    _stamm_pruefen(stamm)
    _annahmen_pruefen(config)
    bis = pd.Timestamp(bis).date()
    zugaenge = _zugaenge_bestimmen(
        stamm, config, bis, neuzugang_ab=neuzugang_ab, zugaenge=zugaenge)
    gesamt = (
        pd.concat([stamm, zugaenge], ignore_index=True) if len(zugaenge) else stamm
    )
    _vertraege_pruefen(gesamt, config)
    liste = Ereignisliste(zugaenge, ziehe(gesamt, config, bis, merkmale=merkmale))
    return buche(
        stamm, config, bis, liste, merkmale=merkmale, scheiben=scheiben,
        schichten=schichten, verankerung=verankerung,
    )


def _mitgebrachte_scheiben(
    stamm: pd.DataFrame,
    scheiben: pd.DataFrame | None,
    grundlagen,
) -> Dict[int, List[Tuple[int, float, Rechenkern]]]:
    """police_id -> mitgebrachte Bausteine als (Erhoehungsjahr, Summe, Kern).

    Nur uebernommene Vertraege bringen Scheiben mit, und nur solche vor
    ihrem Bestandszugang. Der Kern jeder Scheibe entsteht aus ihrer Zeile
    (Alter, Restdauern, Summe, gamma1) und den Rechnungsgrundlagen des
    Vertrags — genau wie in der Bewertung (``auswertung._scheiben_kerne``).
    """
    if scheiben is None or len(scheiben) == 0:
        return {}
    fehlend = [c for c in SCHEIBEN_NAMES if c not in scheiben.columns]
    if fehlend:
        raise EreignisError(f"scheiben: Spalten fehlen: {fehlend}")
    haupt = stamm.set_index("police_id")
    fremd = sorted(set(scheiben["police_id"]) - set(haupt.index))
    if fremd:
        raise EreignisError(
            f"scheiben: police_id unbekannt im Bestand: {fremd[:5]}")
    aus: Dict[int, List[Tuple[int, float, Rechenkern]]] = {}
    for s in scheiben.sort_values(["police_id", "scheiben_id"]).to_dict("records"):
        pid = int(s["police_id"])
        h = haupt.loc[pid]
        zugang = pd.Timestamp(h["bestandszugang"])
        if zugang <= pd.Timestamp(h["insurance_start"]):
            raise EreignisError(
                f"police {pid}: mitgebrachte Scheibe an einem eigenen Vertrag "
                "— nur ein uebernommener Vertrag bringt Bausteine mit")
        if pd.Timestamp(s["erhoehung_datum"]) > zugang:
            raise EreignisError(
                f"police {pid}: mitgebrachte Scheibe vom "
                f"{pd.Timestamp(s['erhoehung_datum']).date()} liegt NACH dem "
                f"Bestandszugang {zugang.date()} — der Bestand ist bereits "
                "fortgeschrieben und wuerde ein zweites Mal simuliert")
        row = {
            "entry_age": s["entry_age"], "sex": h["sex"],
            "duration": s["duration"], "premium_duration": s["premium_duration"],
            "sum_insured": s["sum_insured"], "zahlweise": h["zahlweise"],
        }
        kwargs = model_point_kwargs(row, grundlagen(pid, str(h["tarif_generation"])))
        # Schicht-eigene Rechnungsgrundlage der Scheibe (ADR-011).
        kwargs["gamma1"] = float(s["gamma1"])
        aus.setdefault(pid, []).append(
            (int(s["erhoehung_jahr"]), float(s["sum_insured"]),
             Rechenkern(ModelPoint(**kwargs))))
    return aus


def _pruefe_mitgebrachte_zugaenge(
    stamm: pd.DataFrame, zugaenge: pd.DataFrame
) -> pd.DataFrame:
    """Mitgebrachte Zugaenge muessen aussehen wie die des Erzeugers.

    Dieselben Wachposten wie fuer den simulierten Neuzugang — nur dass
    hier niemand den Erzeuger kontrolliert: POL-Ursprungszeilen mit
    Zugang am Beginn, eindeutige und stammfremde Nummern, Laufzeiten im
    Verlaufsfenster der Engine. Ein Fehler hier ist ein Fehler des
    Aufrufers und wird ihm genannt, nicht still herausgefiltert.
    """
    fehlend = [c for c in STAMM_NAMES if c not in zugaenge.columns]
    if fehlend:
        raise EreignisError(f"zugaenge: Stamm-Spalten fehlen: {fehlend}")
    zugaenge = zugaenge[list(STAMM_NAMES)].reset_index(drop=True)
    if len(zugaenge) == 0:
        return _leerer_frame(STAMM_SPALTEN)
    if not (
        (zugaenge["status_code"] == "POL").all()
        and (zugaenge["status_id"] == 1).all()
        and (
            pd.to_datetime(zugaenge["bestandszugang"])
            == pd.to_datetime(zugaenge["insurance_start"])
        ).all()
    ):
        raise EreignisError(
            "zugaenge: nur POL-Ursprungszeilen mit Zugang am Versicherungsbeginn "
            "— ein Zugang ist ein neuer Vertrag, kein mitgebrachter Zustand"
        )
    if zugaenge["police_id"].duplicated().any():
        raise EreignisError("zugaenge: police_id nicht eindeutig")
    if int(zugaenge["police_id"].min()) <= 0:
        raise EreignisError("zugaenge: police_id <= 0 (Substream-Konvention verlangt > 0)")
    ueberschneidung = set(zugaenge["police_id"]) & set(stamm["police_id"])
    if ueberschneidung:
        raise EreignisError(
            f"zugaenge: police_ids kollidieren mit dem Basisbestand: "
            f"{sorted(ueberschneidung)[:5]}"
        )
    zu_lang = zugaenge[zugaenge["duration"] > 50]
    if len(zu_lang):
        raise EreignisError(
            f"zugaenge: duration > 50 ({len(zu_lang)} Vertraege, z. B. police "
            f"{int(zu_lang['police_id'].iloc[0])}): ausserhalb des "
            "Verlaufsfensters der Bestand-Engine (0..50)"
        )
    return zugaenge


def mit_zugaengen(stamm: pd.DataFrame, zugaenge: pd.DataFrame) -> pd.DataFrame:
    """Gesamtbestand = Basisbestand + Neuzugaenge (POL-Basiszeilen).

    Das Ergebnis erfuellt denselben Contract wie der Generator-Output
    (validate_portfolio-konform, eindeutige police_ids) und traegt noch
    Ursprungszustaende; den gefuehrten Zustand setzt erst
    :func:`rechner_pipeline.bestand.fuehrung.fuehre_fort`.
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
