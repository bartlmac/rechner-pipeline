"""Die PLV erfuellt die Faehigkeit Bewertung des Zielvertrags (ADR-030,
Stufe 2).

Weitergabe an ``kern.rechenkern`` (Rechenkern, Erhoehungsscheibe,
Vertragsreserve, Rechenlauf), ``kern.vorgangsfolge`` (Vorgangsfolge,
Vertragsstand), ``kern.korrekturschicht`` (Schichtparameter, Schichtwert,
Zuschlag, Verankerung) und ``kern.beitragsreduktion`` (Verfahren). Keine
eigene Formel: Wo die Konsumenten des Tools vorher selbst summierten,
steht die Summe jetzt hier, in derselben Reihenfolge; wo sie in
verschiedener Reihenfolge summierten, liefert der Vertrag die Bausteine
(``reserven_beitragsfrei``). Die Ausnahmen des Kerns werden in die des
Vertrags uebersetzt, mit dem Text des Kerns.

Knoten: system/zielsystem
"""

from __future__ import annotations

from types import MappingProxyType
import dataclasses
from typing import Any, List, Mapping, Optional, Sequence, Tuple

from rechner_pipeline.kern import (
    ModelPoint,
    Rechenkern,
    VORGANG_RANG,
    Vertragsstand,
    Vorgangsfolge,
    VorgangsfolgeFehler,
    berechne,
    erhoehungs_scheibe,
    tku_umfang_fuer,
    vertrags_monatsreserve,
    vorgang,
)
from rechner_pipeline.kern.beitragsreduktion import TEILKUENDIGUNG, VERFAHREN
from rechner_pipeline.kern.korrekturschicht import (
    KorrekturschichtFehler,
    Schichtparameter,
    ab_verankerung,
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.kern.produkte import hole
from rechner_pipeline.kern.tafeln import MissingMortalityTableError
from rechner_pipeline.kern.vorgangsfolge import TKU_UMFAENGE
from rechner_pipeline.zielsystem.bewertung import (
    Datenfehler,
    Praemien,
    Reserve,
    Schichtfehler,
    Vorgangsergebnis,
    Vorgangsfehler,
    Vorgangsregeln,
    Werte,
)

__all__ = ["PLVBewertung"]


def _uebersetzt(exc: BaseException) -> BaseException:
    """Die Ausnahme des Kerns als Ausnahme des Vertrags, mit dem Text des
    Kerns; Pythons eigene Ausnahmen bleiben, was sie sind."""
    if isinstance(exc, VorgangsfolgeFehler):
        return Vorgangsfehler(str(exc))
    if isinstance(exc, KorrekturschichtFehler):
        return Schichtfehler(str(exc))
    if isinstance(exc, MissingMortalityTableError):
        return Datenfehler(str(exc))
    return exc


def _kern(felder: Mapping[str, Any]) -> Rechenkern:
    try:
        return Rechenkern(ModelPoint(**felder))
    except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
        raise _uebersetzt(exc) from exc


class _Stand:
    """Ein Vertragsstand des Kerns in der Form des Protokolls ``Stand``."""

    def __init__(self, stand: Vertragsstand, grund_mp: ModelPoint, gamma1_uebernehmen: bool):
        self._stand = stand
        self._grund_mp = grund_mp
        self._gamma1 = gamma1_uebernehmen

    @property
    def pex_jahr(self) -> Optional[int]:
        return self._stand.pex_jahr

    @property
    def beitragsfrei(self) -> bool:
        return self._stand.beitragsfrei

    def werte(self, monate: int) -> Werte:
        w = self._stand.werte(monate)
        return Werte(
            status=str(w["status"]), deckungskapital=float(w["deckungskapital"]),
            rueckkaufswert=float(w["rueckkaufswert"]),
            korrekturschicht=float(w["korrekturschicht"]), vs_bfr=float(w["vs_bfr"]),
            vx_mrv=float(w["vx_mrv"]),
        )

    def komponenten(self, monate: int) -> int:
        return len(self._stand.bestehend(monate))

    def gesamt_vs(self) -> float:
        return self._stand.gesamt_vs()

    def vs_bfr_ohne_zuschlag(self) -> float:
        return self._stand.vs_bfr() - sum(b.zuschlag for b in self._stand.bausteine)

    def jahresbeitrag(self, monate: int) -> float:
        return sum(
            k.gross_annual_premium() for erh_jahr, k in self._stand.beitragskerne(monate)
            if monate - 12 * erh_jahr < 12 * k.mp.t)

    def leistung(self) -> float:
        return self._stand.leistung()

    def _neu(self, stand: Vertragsstand) -> "_Stand":
        return _Stand(stand, self._grund_mp, self._gamma1)

    def nach_erhoehung(self, jahr: int, summe: float) -> "_Stand":
        try:
            scheibe = Rechenkern(erhoehungs_scheibe(
                self._grund_mp, jahr, summe, gamma1_uebernehmen=self._gamma1))
            return self._neu(self._stand.nach_erhoehung(jahr, scheibe))
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc

    def nach_pex(self, jahr: int) -> "_Stand":
        try:
            return self._neu(self._stand.nach_pex(jahr))
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc

    def nach_vorgang(self, jahr: int, anteil: float, verfahren: str) -> "_Stand":
        try:
            stand, _ = self._stand.nach_vorgang(vorgang(jahr, float(anteil), verfahren))
            return self._neu(stand)
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc


class _Folge:
    def __init__(self, folge: Vorgangsfolge, grund_mp: ModelPoint, gamma1_uebernehmen: bool):
        self._folge = folge
        self._grund_mp = grund_mp
        self._gamma1 = gamma1_uebernehmen

    def stand_am(self, monate: int) -> _Stand:
        return _Stand(self._folge.stand_am(monate), self._grund_mp, self._gamma1)

    def stand_vor(self, jahr: int, art: str) -> _Stand:
        return _Stand(self._folge.stand_vor(jahr, art), self._grund_mp, self._gamma1)

    def hat_vorgang(self, jahr: int, art: str) -> bool:
        return self._folge.ergebnis(jahr, art) is not None

    def ergebnis(self, jahr: int, art: str) -> Optional[Vorgangsergebnis]:
        e = self._folge.ergebnis(jahr, art)
        if e is None:
            return None
        return Vorgangsergebnis(vs_neu=e.vs_neu, absorbiert=e.absorbiert, auszahlung=e.auszahlung)


class _Vertragswerte:
    """Grundversicherung und Scheiben als Kerne, einmal gebaut."""

    def __init__(
        self, felder: Mapping[str, Any], scheiben: Sequence[Tuple[int, float]],
        *, gamma1_uebernehmen: bool, stoab_je_baustein: bool,
        bausteine: Sequence[Tuple[int, Mapping[str, Any]]] = (),
    ):
        self.felder = MappingProxyType(dict(felder))
        self.scheiben = tuple((int(j), float(s)) for j, s in scheiben)
        self._bausteine = tuple((int(j), MappingProxyType(dict(f))) for j, f in bausteine)
        self._gamma1 = bool(gamma1_uebernehmen)
        self._stoab = bool(stoab_je_baustein)
        self._mp = ModelPoint(**self.felder)
        self._kern = Rechenkern(self._mp)
        try:
            self._kerne: List[Tuple[int, Rechenkern]] = [
                (j, Rechenkern(erhoehungs_scheibe(self._mp, j, s, gamma1_uebernehmen=self._gamma1)))
                for j, s in self.scheiben] + [
                (j, Rechenkern(ModelPoint(**f))) for j, f in self._bausteine]
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc

    def komponenten(self) -> int:
        return 1 + len(self._kerne)

    def mit_scheibe(self, jahr: int, summe: float) -> "_Vertragswerte":
        if self._bausteine:
            raise ValueError("nach einem Baustein aus eigenen Feldern kommt keine Scheibe mehr")
        return _Vertragswerte(
            self.felder, (*self.scheiben, (jahr, summe)),
            gamma1_uebernehmen=self._gamma1, stoab_je_baustein=self._stoab)

    def mit_baustein(self, jahr: int, felder: Mapping[str, Any]) -> "_Vertragswerte":
        return _Vertragswerte(
            self.felder, self.scheiben, gamma1_uebernehmen=self._gamma1,
            stoab_je_baustein=self._stoab, bausteine=(*self._bausteine, (jahr, felder)))

    def reserve(self, monate: int) -> Reserve:
        if self._kerne:
            m = vertrags_monatsreserve(
                self._kern, self._kerne, monate, stoab_je_baustein=self._stoab)
        else:
            m = self._kern.monatsreserve(monate)
        return Reserve(vx_mrv=m.vx_mrv, rkw=m.rkw)

    def reserven_beitragsfrei(self, pex_jahr: int, monate: int) -> Tuple[float, ...]:
        def _bfr(k: Rechenkern, a0: int, m: int) -> float:
            if m % 12:
                return k.monatsreserve_beitragsfrei(a0, m)
            return k.reserve_beitragsfrei(a0, m // 12)
        return (_bfr(self._kern, pex_jahr, monate), *(
            _bfr(k, pex_jahr - j, monate - 12 * j) for j, k in self._kerne))

    def beitragsfreie_summe(self, pex_jahr: int) -> float:
        return self._kern.beitragsfreie_summe(pex_jahr) + sum(
            k.beitragsfreie_summe(pex_jahr - j) for j, k in self._kerne if pex_jahr - j > 0)

    def gesamtsumme(self) -> float:
        return float(self._mp.sum_insured) + sum(k.mp.sum_insured for _, k in self._kerne)

    def jahresbeitrag(self, monate: int, pex_jahr: Optional[int]) -> float:
        if pex_jahr is not None:
            return 0.0
        if monate >= 12 * self._mp.t:
            gesamt = 0.0
        else:
            gesamt = self._kern.gross_annual_premium()
        for j, k in self._kerne:
            if monate - 12 * j < 12 * k.mp.t:
                gesamt += k.gross_annual_premium()
        return gesamt

    def stand(self, *, schicht: Optional[Tuple[Any, int]], tku_umfang: str) -> _Stand:
        try:
            return _Stand(Vertragsstand.anfang(
                self._kern, self._kerne, stoab_je_baustein=self._stoab,
                tku_umfang=tku_umfang, schicht=schicht), self._mp, self._gamma1)
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc

    def folge(
        self, vorgaenge: Sequence[Tuple[int, float, str]], *,
        pex_jahr: Optional[int], schicht: Optional[Tuple[Any, int]], tku_umfang: str,
    ) -> _Folge:
        try:
            folge = Vorgangsfolge(
                self._kern, self._kerne,
                [vorgang(int(j), float(a), str(v)) for j, a, v in vorgaenge],
                pex_jahr=pex_jahr, schicht=schicht,
                stoab_je_baustein=self._stoab, tku_umfang=tku_umfang)
        except (VorgangsfolgeFehler, KorrekturschichtFehler, MissingMortalityTableError) as exc:
            raise _uebersetzt(exc) from exc
        return _Folge(folge, self._mp, self._gamma1)


class PLVBewertung:
    """Die Bewertung der PLV, in der Form des Protokolls
    ``zielsystem.bewertung.Bewertung``."""

    def vorgangsregeln(self) -> Vorgangsregeln:
        return Vorgangsregeln(
            rang=MappingProxyType(dict(VORGANG_RANG)), teilkuendigung=TEILKUENDIGUNG,
            verfahren=tuple(VERFAHREN), umfaenge=tuple(TKU_UMFAENGE))

    def tku_umfang(self, red_verfahren: str, gewuenscht: Optional[str]) -> str:
        try:
            return tku_umfang_fuer(red_verfahren, gewuenscht)
        except VorgangsfolgeFehler as exc:
            raise Vorgangsfehler(str(exc)) from exc

    def vertrag(
        self, felder: Mapping[str, Any], scheiben: Sequence[Tuple[int, float]] = (),
        *, gamma1_uebernehmen: bool, stoab_je_baustein: bool,
    ) -> _Vertragswerte:
        return _Vertragswerte(
            felder, scheiben, gamma1_uebernehmen=gamma1_uebernehmen,
            stoab_je_baustein=stoab_je_baustein)

    def scheibe(
        self, felder: Mapping[str, Any], jahr: int, summe: float, *, gamma1_uebernehmen: bool,
    ) -> Mapping[str, Any]:
        return MappingProxyType(dataclasses.asdict(erhoehungs_scheibe(
            ModelPoint(**felder), int(jahr), float(summe), gamma1_uebernehmen=gamma1_uebernehmen)))

    def schichtfelder(self) -> Tuple[str, ...]:
        return tuple(f.name for f in dataclasses.fields(Schichtparameter))

    def schicht_aus_beleg(self, beleg: Mapping[str, Any]) -> Schichtparameter:
        try:
            return Schichtparameter(**{
                k: (tuple(tuple(x) for x in v) if k == "vererbend" else v)
                for k, v in beleg.items()})
        except KorrekturschichtFehler as exc:
            raise Schichtfehler(str(exc)) from exc

    def schichtwert(
        self, schicht: Schichtparameter, monate_anker: int, felder: Mapping[str, Any], monate: int,
    ) -> float:
        try:
            return schichtwert_bei(schicht, monate_anker, ModelPoint(**felder), monate)
        except KorrekturschichtFehler as exc:
            raise Schichtfehler(str(exc)) from exc

    def zuschlag_bei_pex(
        self, schicht: Optional[Tuple[Any, int]], felder: Mapping[str, Any], pex_jahr: int,
    ) -> float:
        try:
            return zuschlag_bei_pex(schicht, _kern(felder), pex_jahr)
        except KorrekturschichtFehler as exc:
            raise Schichtfehler(str(exc)) from exc

    def schicht_traegt(self, schicht: Optional[Tuple[Any, int]], monate: int) -> bool:
        return schicht_traegt(schicht, monate)

    def ab_verankerung(self, monate_anker: int, monate: int) -> bool:
        return ab_verankerung(monate_anker, monate)

    def praemien(self, felder: Mapping[str, Any]) -> Praemien:
        kern = _kern(felder)
        return Praemien(
            bxt=kern.gross_premium_rate(), bjb=kern.gross_annual_premium(),
            bzb=kern.gross_payable_premium(), pxt=kern.net_premium_rate())

    def verlauf(self, felder: Mapping[str, Any], k: int) -> Mapping[str, Any]:
        return _kern(felder).verlaufszeile(k).als_blattzeile()

    def rechne(self, produkt: str, felder: Mapping[str, Any]) -> Mapping[str, Any]:
        mp = hole(produkt).model_point_cls(**felder)
        try:
            return berechne(mp, produkt=produkt)
        except MissingMortalityTableError as exc:
            raise Datenfehler(str(exc)) from exc
