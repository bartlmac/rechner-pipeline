"""Faehigkeit 3 des Zielvertrags: Bewertung (ADR-030, Stufe 2).

Was das Tool vom Zielsystem braucht, um gelieferte Werte zu pruefen:
die Werte eines Vertrags an einem Vertragsmonat, den Vertrag in seiner
Vorgangsfolge, die Korrekturschicht, die Regeln der Vorgaenge, die
Praemiensaetze und den Verlauf einer Generation, und den vollstaendigen
Rechenlauf eines Modellpunkts. Vertragsdaten gehen hinein, Werte kommen
heraus; das Protokoll nennt keinen Rechenkern, keinen Baustein und
keinen Scheiben-Modellpunkt.

Drei Grenzen sind bewusst gezogen:

* Die beitragsfreie Reserve eines Vertrags mit Erhoehungsscheiben kommt
  JE BAUSTEIN (``Vertragswerte.reserven_beitragsfrei``), nicht als Summe.
  Die beiden Pruefstrecken summieren sie in verschiedener Reihenfolge,
  und Gleitkommasummen haengen von ihr ab (gemessen auf Fall 3: 2391
  von 5517 Faellen verschieden in der letzten Stelle). Der Vergleich
  kennt seine Komponenten ohnehin, weil seine Toleranz mit ihnen
  waechst; die Summation bleibt deshalb beim Vergleich.
* Ein Vertrag in seiner Vorgangsfolge liefert seine Werte als Ganzes
  (``Stand.werte``): Dort summiert das Zielsystem selbst, wie es die
  Fuehrung auch tut.
* Ausnahmen: Was eine unplausible Lieferung ausloesen kann, kommt als
  ``Datenfehler`` (eine Folge, die das Zielsystem nicht rechnet:
  ``Vorgangsfehler``; eine Schicht, die es nicht traegt:
  ``Schichtfehler``). Die Implementierung uebersetzt ihre eigenen
  Ausnahmen dorthin; Pythons eigene (ValueError, TypeError, KeyError,
  ArithmeticError) bleiben, was sie sind.

Knoten: system/zielsystem
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, Sequence, Tuple, runtime_checkable

__all__ = [
    "Bewertung", "Datenfehler", "Folge", "Praemien", "Reserve", "Schicht",
    "Schichtfehler", "Stand", "Vertragswerte", "Vorgangsergebnis", "Vorgangsfehler",
    "Vorgangsregeln", "Werte",
]


class Datenfehler(ValueError):
    """Das Zielsystem rechnet diese Daten nicht: eine Lieferung, die
    ausserhalb seiner Regeln liegt. Ein Befund des Vertrags, kein Defekt."""


class Vorgangsfehler(Datenfehler):
    """Eine Vorgangsfolge, die das Zielsystem nicht rechnet (benannt, mit
    Ausweg im Text)."""


class Schichtfehler(Datenfehler):
    """Eine Korrekturschicht, die das Zielsystem nicht traegt."""


@dataclass(frozen=True)
class Reserve:
    """Die Reserve des beitragspflichtigen Vertrags an einem Monat."""

    vx_mrv: float
    rkw: float


@dataclass(frozen=True)
class Werte:
    """Die Werte eines Vertrags in seiner Vorgangsfolge an einem Monat.

    ``deckungskapital`` enthaelt die Korrekturschicht, ``korrekturschicht``
    weist sie aus, ``vx_mrv`` ist die Reserve ohne die eigene Position der
    Schicht; ``status`` ist ``POL`` (beitragspflichtig) oder ``PEX``.
    """

    status: str
    deckungskapital: float
    rueckkaufswert: float
    korrekturschicht: float
    vs_bfr: float
    vx_mrv: float


@dataclass(frozen=True)
class Praemien:
    """Die Praemiensaetze eines Modellpunkts (Golden-Master-Groessen)."""

    bxt: float
    bjb: float
    bzb: float
    pxt: float


@dataclass(frozen=True)
class Vorgangsergebnis:
    """Was ein Vorgang gebucht hat: die neue Gesamtsumme, die dabei
    aufgenommene Korrekturschicht und bei der Teilkuendigung die
    rechnerische Auszahlung (sonst None)."""

    vs_neu: float
    absorbiert: float
    auszahlung: Optional[float]


@dataclass(frozen=True)
class Vorgangsregeln:
    """Die Regeln der Vorgaenge, wie das Zielsystem sie fuehrt: der Rang
    je Vorgangsart an einem Jahrestag, der Name des Verfahrens
    Teilkuendigung, die Verfahren der Herabsetzung und die Umfaenge der
    Teilkuendigung. Die Arten sind die Ereigniscodes des Ledgers (PEX,
    RED, TKU, ERH)."""

    rang: Mapping[str, int]
    teilkuendigung: str
    verfahren: Tuple[str, ...]
    umfaenge: Tuple[str, ...]

    def art(self, verfahren: str) -> str:
        """Die Vorgangsart einer Tabellenzeile: ``TKU`` fuer das Verfahren
        Teilkuendigung, sonst ``RED``."""
        return "TKU" if str(verfahren) == self.teilkuendigung else "RED"

    def schluessel(self, jahr: int, verfahren: str) -> Tuple[int, int]:
        """Die Ordnung eines Vorgangs: Jahrestag, dann Rang."""
        return (int(jahr), self.rang[self.art(verfahren)])


@runtime_checkable
class Schicht(Protocol):
    """Eine Korrekturschicht, wie das Zielsystem sie aus dem Beleg liest.
    Das Tool liest nur Typ und Rumpfmonate; alles andere ist Sache des
    Zielsystems."""

    schichttyp: str
    rumpfmonate: int


@runtime_checkable
class Stand(Protocol):
    """Ein Vertrag in einem Zustand seiner Vorgangsfolge."""

    pex_jahr: Optional[int]
    beitragsfrei: bool

    def werte(self, monate: int) -> Werte: ...

    def komponenten(self, monate: int) -> int:
        """Die Zahl der Bausteine, aus denen der Wert am Monat besteht."""
        ...

    def gesamt_vs(self) -> float: ...

    def vs_bfr_ohne_zuschlag(self) -> float:
        """Die beitragsfreie Gesamtsumme ohne den Zuschlag, mit dem das
        Zielsystem eine Schicht bei der Freistellung ueberfuehrt (die
        Summe, wie eine Quelle sie liefert)."""
        ...

    def jahresbeitrag(self, monate: int) -> float: ...

    def leistung(self) -> float:
        """Die Leistung eines terminalen Falls (Tod, Ablauf): beitragsfrei
        die beitragsfreie Gesamtsumme, sonst die gefuehrte Summe."""
        ...

    def nach_erhoehung(self, jahr: int, summe: float) -> "Stand": ...

    def nach_pex(self, jahr: int) -> "Stand": ...

    def nach_vorgang(self, jahr: int, anteil: float, verfahren: str) -> "Stand": ...


@runtime_checkable
class Folge(Protocol):
    """Die Vorgangsfolge eines Vertrags, gefaltet in Staende."""

    def stand_am(self, monate: int) -> Stand: ...

    def stand_vor(self, jahr: int, art: str) -> Stand: ...

    def hat_vorgang(self, jahr: int, art: str) -> bool: ...

    def ergebnis(self, jahr: int, art: str) -> Optional[Vorgangsergebnis]:
        """Was der Vorgang ``art`` am Jahrestag ``jahr`` gebucht hat; None,
        wenn die Folge keinen solchen kennt."""
        ...


@runtime_checkable
class Vertragswerte(Protocol):
    """Ein Vertrag (Grundversicherung und Erhoehungsscheiben) im
    beitragspflichtigen oder beitragsfreien Zustand, ohne Vorgaenge."""

    felder: Mapping[str, Any]
    scheiben: Tuple[Tuple[int, float], ...]

    def komponenten(self) -> int: ...

    def mit_scheibe(self, jahr: int, summe: float) -> "Vertragswerte":
        """Der Vertrag mit einer weiteren Erhoehungsscheibe nach der Regel
        des Zielsystems (Jahr und Summe)."""
        ...

    def mit_baustein(self, jahr: int, felder: Mapping[str, Any]) -> "Vertragswerte":
        """Der Vertrag mit einem weiteren Baustein aus eigenen Feldern, wie
        die Fuehrung ihn fuehrt (eine gebuchte Erhoehungsscheibe)."""
        ...

    def reserve(self, monate: int) -> Reserve: ...

    def reserven_beitragsfrei(self, pex_jahr: int, monate: int) -> Tuple[float, ...]:
        """Die beitragsfreie Reserve je Baustein (Grund, dann die Scheiben in
        ihrer Reihenfolge), jede ab ihrem eigenen Jahrestag."""
        ...

    def beitragsfreie_summe(self, pex_jahr: int) -> float:
        """Die beitragsfreie Gesamtsumme ueber die Bausteine, die im Jahr
        der Freistellung bestehen (Grund, Scheiben vor diesem Jahr)."""
        ...

    def gesamtsumme(self) -> float: ...

    def jahresbeitrag(self, monate: int, pex_jahr: Optional[int]) -> float: ...

    def stand(self, *, schicht: Optional[Tuple[Schicht, int]], tku_umfang: str) -> Stand:
        """Der Vertrag vor jedem Vorgang, mit allen Scheiben als Bausteine."""
        ...

    def folge(
        self,
        vorgaenge: Sequence[Tuple[int, float, str]],
        *,
        pex_jahr: Optional[int],
        schicht: Optional[Tuple[Schicht, int]],
        tku_umfang: str,
    ) -> Folge: ...


@runtime_checkable
class Bewertung(Protocol):
    """Faehigkeit ``bewertung``."""

    def vorgangsregeln(self) -> Vorgangsregeln: ...

    def tku_umfang(self, red_verfahren: str, gewuenscht: Optional[str]) -> str:
        """Der Umfang einer Teilkuendigung zum Verfahren der Herabsetzung;
        ``ValueError`` fuer eine Kombination, die das Zielsystem nicht kennt."""
        ...

    def vertrag(
        self,
        felder: Mapping[str, Any],
        scheiben: Sequence[Tuple[int, float]] = (),
        *,
        gamma1_uebernehmen: bool,
        stoab_je_baustein: bool,
    ) -> Vertragswerte: ...

    def scheibe(
        self, felder: Mapping[str, Any], jahr: int, summe: float, *, gamma1_uebernehmen: bool,
    ) -> Mapping[str, Any]:
        """Die Felder einer Erhoehungsscheibe als eigener Baustein, wie das
        Zielsystem sie aus dem Grundvertrag ableitet (die Fuehrung
        schreibt sie in ihre Scheibentabelle); ``ValueError``, wenn das
        Jahr keine Scheibe traegt."""
        ...

    def schichtfelder(self) -> Tuple[str, ...]:
        """Die Felder, die eine Schicht traegt: dieselben in Tabelle und
        Beleg, damit ein Vergleich keines auslaesst."""
        ...

    def schicht_aus_beleg(self, beleg: Mapping[str, Any]) -> Schicht:
        """Die Schicht aus den Feldern eines Schichtbelegs; ``Schichtfehler``
        oder ``TypeError``, wenn der Beleg keine Schicht beschreibt."""
        ...

    def schichtwert(
        self, schicht: Schicht, monate_anker: int, felder: Mapping[str, Any], monate: int
    ) -> float: ...

    def zuschlag_bei_pex(
        self, schicht: Optional[Tuple[Schicht, int]], felder: Mapping[str, Any], pex_jahr: int
    ) -> float: ...

    def schicht_traegt(self, schicht: Optional[Tuple[Schicht, int]], monate: int) -> bool: ...

    def ab_verankerung(self, monate_anker: int, monate: int) -> bool: ...

    def praemien(self, felder: Mapping[str, Any]) -> Praemien: ...

    def verlauf(self, felder: Mapping[str, Any], k: int) -> Mapping[str, Any]:
        """Die Verlaufszeile des Vertragsjahres ``k`` als Blattzeile des
        Golden-Master-Vergleichs."""
        ...

    def rechne(self, produkt: str, felder: Mapping[str, Any]) -> Mapping[str, Any]:
        """Der vollstaendige Rechenlauf: ``scalars`` und ``tables`` je
        Blatt, wie der Golden-Master-Vergleich sie liest."""
        ...
