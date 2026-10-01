"""Die Vorgangsfolge eines Vertrags — EIN Zustand, den jeder Leser rechnet.

Seit dem Entscheid des Maintainers vom 2026-10-01 (ADR-023, Nachtrag
2026-10-01; Tarifplan KLV 7.1 bis 7.3) traegt ein Vertrag beliebig viele
Beitragsherabsetzungen (``RED``) und Teilkuendigungen (``TKU``), in jeder
Reihenfolge, verschraenkt mit dynamischen Erhoehungen (``ERH``) und einer
Beitragsfreistellung (``PEX``). Vorher kannte der Kern hoechstens EINEN
Vorgang je Vertrag (``ReduzierterVertrag`` mit einer ``Reduktion``), und
jeder Leser — Engine, Bewertung, Ledger-Herleitung, Fuehrungsprobe — baute
den herabgesetzten Vertrag aus dieser einen Zeile nach.

**Die Invariante.** Der Zustand eines Vertrags ist die Folge seiner
Vorgaenge; jeder Leser rechnet auf derselben Folge. Deshalb steht die Folge
hier, einmal, und die Leser fragen sie: :class:`Vorgangsfolge` faltet die
Vorgaenge eines Vertrags in Zustaende (:class:`Vertragsstand`), jeder
Zustand kennt seine Reserve, seinen Rueckkaufswert, seine Summen und seine
Beitraege. Ein Leser waehlt nur noch den Zeitpunkt.

**Reihenfolge an einem Jahrestag.** Alle Vorgaenge wirken am Jahrestag
ihres Vertragsjahres. Fallen mehrere auf denselben Tag, gilt die Reihenfolge
der Engine: Beitragsfreistellung, Beitragsherabsetzung, Teilkuendigung,
Erhoehung (:data:`RANG`). Storno, Tod und Ablauf sehen den Zustand VOR den
Vorgaengen ihres Tages (``stand_vor``), eine Bewertung am Stichtag den
Zustand NACH allen Vorgaengen bis einschliesslich zum Stichtag
(``stand_am``).

**Die Darstellung je Baustein** (:class:`Baustein`). Grundversicherung und
jede Erhoehungsscheibe sind je ein Baustein. Ein Baustein traegt

* seinen WIRKSAMEN Kern: den Modellpunkt mit der Summe nach allen
  Teilkuendigungen. Die Teilkuendigung trifft jeden Bestandteil des Bausteins
  mit demselben Anteil — fortgefuehrten Teil, beitragsfreie Teilsummen,
  Zillmer-Rueckstand; der Kern ist summenhomogen (Fund N10), also ist der
  teilgekuendigte Baustein der gewoehnliche Baustein mit kleinerer Summe;
* seinen VERLAUF relativ zu diesem Kern (Abschnitte ``(ab, c, q)``): ``c``
  ist der fortgefuehrte Beitragsfaktor (jede Herabsetzung multipliziert ihn
  mit f), ``q`` die bei Herabsetzungen fixierte beitragsfreie Summe relativ
  zur wirksamen Summe. Der Verlauf ist ein Zahlungspfad
  (:mod:`rechner_pipeline.kern.zahlungspfad`) — die Rekursion braucht keine
  Homogenitaet;
* seine gefuehrte Summe ``vs`` (fortgefuehrter plus fixierter Teil) und,
  nach einer Beitragsfreistellung, die beitragsfreie Summe ``s_bfr``.

Ein Vertrag mit EINER Herabsetzung oder EINER Teilkuendigung rechnet hier
bitgleich wie zuvor ueber ``ReduzierterVertrag`` (Test
``tests/test_vorgangsfolge.py``): dieselben Ausdruecke in derselben
Reihenfolge. Ein beitragspflichtiger Vertrag ohne Vorgang wird gar nicht
ueber diese Klasse gerechnet; seine Werte entstehen unveraendert im Kern. Ein
beitragsfrei gestellter Vertrag ohne Herabsetzung und Teilkuendigung ist die
Folge aus seinen Scheiben und der Freistellung (Kern 3.19.0, Pruefrunde H,
H01): Die Bewertung liest Reserve und Rueckkaufswert des beitragsfreien
Vertrags hier, statt sie daneben zu rechnen — dieselben Ausdruecke wie
``monatsreserve_beitragsfrei`` fuer die Reserve, der Rueckkaufswert nach B3.

**Regeln der Verkettung** (Tarifplan KLV 7.3, Annahmen B2 bis B4):

* Jeder Vorgang wirkt proportional auf den Vertrag in seinem AKTUELLEN
  Zustand.
* Teilkuendigung mit fortgefuehrtem Anteil f: jede Komponente jedes
  betroffenen Bausteins mal f. Ausgezahlt wird (1-f) mal der Rueckkaufswert
  des betroffenen Teils unmittelbar vor dem Vorgang (Stornoabzug nach dem
  Tarifwerk: je Vertrag oder je Baustein), dazu eine noch getragene
  Korrekturschicht vollstaendig. Welche Bausteine betroffen sind, sagt das
  Tarifwerk (``tku_umfang``): alle (eigene Tarife der PLV) oder nur die
  Grundversicherung (Bedingungswerk des uebernommenen Tarifs, Entscheid B1 vom 2026-10-01).
* Beitragsherabsetzung mit Anteil f: der Beitrag jedes Bausteins mal f, der
  freiwerdende Anteil des Rueckkaufs-Tracks wird nach dem Verfahren des
  Tarifs (prospektiv / mit Abzug) in eine weitere fixierte beitragsfreie
  Teilsumme umgewandelt; schon fixierte Teile bleiben. Nur solange ein
  Beitrag laeuft — nicht ab dem Beitragsende, nicht nach einer
  Beitragsfreistellung (benannt verweigert, Ausweg Teilkuendigung).
* Nach einer Beitragsfreistellung kuendigt die Teilkuendigung den Anteil
  (1-f) der beitragsfreien Summe jedes betroffenen Bausteins; ausgezahlt
  wird (1-f) mal der Rueckkaufswert des beitragsfreien Vertrags (B3,
  Entscheid des Maintainers 2026-10-01: Rueckstellung abzueglich des
  Stornoabzugs nach derselben Tarifregel, angewandt auf die beitragsfreie
  Summe; :func:`stornoabzug_auf`).
* Nicht summenhomogen sind allein die Grenzen des Stornoabzugs
  (Mindest- und Hoechstbetrag) und die Stueckkosten des Beitrags. Beide
  werden nie skaliert, sondern auf dem Zustand gebildet, den der Vertrag
  gerade hat (Annahme B4).

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rechner_pipeline.kern.beitragsreduktion import (
    MIT_ABZUG,
    PROSPEKTIV,
    TEILKUENDIGUNG,
    BeitragsreduktionFehler,
    Reduktion,
    _abzugsfaktor,
    _pruefe_eingaben,
    pruefe_vorgangsjahr,
)
from rechner_pipeline.kern.konventionen import untergrenze_basissumme
from rechner_pipeline.kern.korrekturschicht import (
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.kern.model_point import ModelPoint
from rechner_pipeline.kern.produkte.klv import Monatsreserve
from rechner_pipeline.kern.rechenkern import Rechenkern

#: Die Codes der Vorgaenge, die die Folge ordnet. ``RED`` und ``TKU`` sind
#: die Vorgaenge der Nebentabelle ``reduktionen``; ``PEX`` und ``ERH`` gehen
#: aus Statushistorie und Scheiben in die Folge ein.
RED = "RED"
TKU = "TKU"
PEX = "PEX"
ERH = "ERH"
#: Reihenfolge der Vorgaenge AM SELBEN Jahrestag — die der Ereignis-Engine
#: (``bestand.ereignisse``): erst die Beitragsfreistellung, dann die
#: Herabsetzung, dann die Teilkuendigung, zuletzt die Erhoehung. Storno,
#: Tod und Ablauf stehen davor (sie beenden den Vertrag und sehen den
#: Zustand vor den Vorgaengen ihres Tages).
RANG: Dict[str, int] = {PEX: 0, RED: 1, TKU: 2, ERH: 3}

#: Umfang der Teilkuendigung — Tarifwerk-Merkmal der Generation (Entscheid
#: B1 vom 2026-10-01, Tarifplan KLV 7.2): ``alle_bausteine`` kuendigt Grundversicherung
#: und jede Erhoehungsscheibe mit demselben Anteil (eigene Tarife der PLV,
#: Entscheid des Maintainers 2026-10-01); ``grundversicherung`` kuendigt
#: nur die Grundversicherung, die Scheiben bleiben (Bedingungswerk des
#: uebernommenen Tarifs, Ziffer 6).
UMFANG_ALLE = "alle_bausteine"
UMFANG_GRUND = "grundversicherung"
TKU_UMFAENGE: Tuple[str, ...] = (UMFANG_ALLE, UMFANG_GRUND)



def tku_umfang_fuer(red_verfahren: str, tku_umfang: Optional[str] = None) -> str:
    """Der Umfang der Teilkuendigung eines Tarifs — der angegebene, sonst der
    des Bedingungswerks, das ``red_verfahren`` nennt (Entscheid B1 vom 2026-10-01, Tarifplan
    KLV 7.2): ``teilkuendigung`` (ein Tarif ohne Beitragsherabsetzung, der
    uebernommene Tarif, Bedingungswerk Ziffer 6) -> nur die
    Grundversicherung; jedes andere -> alle Bausteine. Die EINE Stelle
    dieser Regel fuer Config, Uebernahme und Pruefstrecke; ein Tarif stellt
    sie mit EINEM Wert (``tku_umfang``) um."""
    if tku_umfang is not None:
        if str(tku_umfang) not in TKU_UMFAENGE:
            raise VorgangsfolgeFehler(
                f"tku_umfang {tku_umfang!r} unbekannt (bekannt: {list(TKU_UMFAENGE)})")
        return str(tku_umfang)
    return UMFANG_GRUND if str(red_verfahren) == TEILKUENDIGUNG else UMFANG_ALLE


#: Der unveraenderte Verlauf eines Bausteins: ab Vertragsjahr 0 voller
#: Beitrag (c = 1), keine fixierte beitragsfreie Teilsumme (q = 0).
_GEWOEHNLICH: Tuple[Tuple[int, float, float], ...] = ((0, 1.0, 0.0),)


class VorgangsfolgeFehler(BeitragsreduktionFehler):
    """Eine Folge, die der Kern nicht rechnet — benannt, mit Ausweg."""


def _jahr_der_folge(mp: ModelPoint, jahr: int, art: str) -> None:
    """Die Jahresgrenzen der Folge (``beitragsreduktion.pruefe_vorgangsjahr``,
    die eine Stelle), benannt als Fehler der Folge."""
    try:
        pruefe_vorgangsjahr(mp, jahr, art)
    except BeitragsreduktionFehler as exc:
        raise VorgangsfolgeFehler(str(exc)) from exc


@dataclass(frozen=True)
class Vorgang:
    """Ein Vorgang der Nebentabelle ``reduktionen``.

    ``jahr`` ist das Vertragsjahr der GRUNDVERSICHERUNG (Wirkungstag: sein
    Jahrestag), ``anteil`` der fortgefuehrte Anteil f, ``verfahren`` bei der
    Herabsetzung das des Tarifs (prospektiv / mit Abzug), bei der
    Teilkuendigung ``teilkuendigung``.
    """

    jahr: int
    art: str
    anteil: float
    verfahren: str

    @property
    def schluessel(self) -> Tuple[int, int]:
        return (int(self.jahr), RANG[self.art])


def vorgang(jahr: int, anteil: float, verfahren: str) -> Vorgang:
    """Der Vorgang einer Tabellenzeile: welcher es ist, sagt das Verfahren
    (``teilkuendigung`` -> ``TKU``, sonst ``RED``; dieselbe Zuordnung wie
    ``models.bestand.reduktion_ereignis``)."""
    art = TKU if str(verfahren) == TEILKUENDIGUNG else RED
    return Vorgang(jahr=int(jahr), art=art, anteil=float(anteil),
                   verfahren=str(verfahren))


def stornoabzug_auf(kern: Rechenkern, a: int, summe: float, reserve: float) -> float:
    """Der Stornoabzug des Tarifs auf eine Summe und ihre Reserve.

    DIESELBE Tarifregel wie die Spalte ``StoAb`` der Verlaufszeile
    (``KLV.stornoabzug``): Satz mal (Summe minus Reserve), begrenzt auf
    Mindest- und Hoechstbetrag, null nach dem Ablauf und in der flexiblen
    Phase. Nur Summe und Reserve sind frei — die Verlaufszeile rechnet sie
    fuer den Vertrag ohne Vorgang, hier stehen die des Zustands, den der
    Vertrag gerade hat: nach Herabsetzungen die neue Gesamtsumme, nach einer
    Beitragsfreistellung die beitragsfreie Summe und ihre Reserve (B3,
    Entscheid des Maintainers 2026-10-01; verworfen: die Rueckstellung ohne
    Abzug auszuzahlen, oder wie bisher keinen Rueckkaufswert). Die Grenzen werden nie skaliert (Annahme B4): Sie sind Betraege des
    Tarifs, keine Anteile.

    Die Verlaufszeile selbst bleibt unberuehrt (Charakterisierung); die
    Regel sitzt am Ereignis-Anschluss wie die Untergrenze der
    beitragsfreien Summe.
    """
    mp = kern.mp
    if a > mp.n or kern.produkt.ist_flex_phase(a):
        return 0.0
    return min(mp.stoab_max, max(mp.stoab_min, mp.stoab_satz * (summe - reserve)))


def _positiver_rueckkaufstrack(reserven: Sequence[Monatsreserve]) -> float:
    """Summe der auf null begrenzten Rueckkaufs-Tracks der Bausteine — das
    Gewicht, nach dem der vertragsweite Abzug verteilt wird (Runde F, F1;
    dieselbe Bildung wie ``reduziere_geschichtet``). Keine Summe der
    Basisschicht, deshalb nicht ``untergrenze_basissumme``."""
    return sum(max(0.0, r.vx_mrv) for r in reserven)


@dataclass(frozen=True)
class Baustein:
    """Grundversicherung oder Erhoehungsscheibe in ihrem aktuellen Zustand.

    ``kern`` ist der WIRKSAME Kern (Summe nach allen Teilkuendigungen),
    ``abschnitte`` der Verlauf relativ zu ihm: ``(ab, c, q)`` gilt ab dem
    lokalen Vertragsjahr ``ab`` (Vertragsjahr der Scheibe = Vertragsjahr des
    Grundvertrags minus ``erh_jahr``). ``vs`` ist die gefuehrte Summe des
    beitragspflichtigen Tracks, ``s_bfr`` die beitragsfreie Summe nach einer
    Beitragsfreistellung, ``zuschlag`` (nur Grundversicherung) die bei der
    Beitragsfreistellung wertstetig ueberfuehrte Korrekturschicht als
    beitragsfreie Summe.
    """

    erh_jahr: int
    kern: Rechenkern
    vs: float
    abschnitte: Tuple[Tuple[int, float, float], ...] = _GEWOEHNLICH
    s_bfr: Optional[float] = None
    zuschlag: float = 0.0

    @classmethod
    def aus_kern(cls, erh_jahr: int, kern: Rechenkern) -> "Baustein":
        return cls(erh_jahr=int(erh_jahr), kern=kern, vs=kern.mp.sum_insured)

    @property
    def gewoehnlich(self) -> bool:
        """Ohne Herabsetzung: der Verlauf ist der des wirksamen Kerns."""
        return self.abschnitte == _GEWOEHNLICH

    @property
    def beitragsfaktor(self) -> float:
        return self.abschnitte[-1][1]

    @property
    def beitragsfrei(self) -> bool:
        return self.s_bfr is not None

    def _abschnitt(self, j: int) -> Tuple[int, float, float]:
        aktuell = self.abschnitte[0]
        for ab in self.abschnitte:
            if ab[0] <= j:
                aktuell = ab
        return aktuell

    def pfad(self):
        """Der Verlauf als Zahlungspfad relativ zum wirksamen Kern.

        Leistung ``c + q``, Beitrag ``c``, Verwaltungskosten des
        fortgefuehrten Teils ``c``, des umgewandelten ``q``,
        Abschlusskostenrest ``c`` (die Abschlusskosten folgen dem Beitrag,
        klv.md 7.1). Fuer EINE Herabsetzung dieselben Tupel wie
        ``beitragsreduktion.als_zahlungspfad``.
        """
        from rechner_pipeline.kern.zahlungspfad import Zahlungspfad

        mp = self.kern.mp
        je_jahr = [self._abschnitt(j) for j in range(mp.n)]
        letzter = self.abschnitte[-1]
        return Zahlungspfad(
            leistung=tuple(c + q for _, c, q in je_jahr),
            ablauf=letzter[1] + letzter[2],
            beitrag=tuple(c for _, c, _ in je_jahr[:mp.t]),
            kosten_bpfl=tuple(c for _, c, _ in je_jahr),
            kosten_bfr=tuple(q for _, _, q in je_jahr),
            abschlusskosten=tuple(c for _, c, _ in je_jahr),
        )

    def monatsreserve(self, monate: int) -> Monatsreserve:
        """Reserve des Bausteins (beitragspflichtiger Track) am lokalen
        Monats-Stichtag. Stornoabzug und Rueckkaufswert dieser Zeile sind die
        des Pfades; vertragsweit bildet sie :class:`Vertragsstand` neu."""
        if self.gewoehnlich:
            return self.kern.monatsreserve(int(monate))
        from rechner_pipeline.kern.zahlungspfad import (
            monatsreserve as pfad_monatsreserve,
        )

        w = pfad_monatsreserve(self.kern.mp, self.pfad(), self.kern.basis, int(monate))
        return Monatsreserve(
            monate=w.monate, jahr=w.jahr, monatsanteil=w.monatsanteil,
            drx_bpfl=w.drx_bpfl, vx_mrv=w.vx_mrv, stoab=w.stoab, rkw=w.rkw,
        )

    def beitragsfreie_summe_bei(self, a: int) -> float:
        """Die beitragsfreie Summe bei einer Beitragsfreistellung im lokalen
        Vertragsjahr ``a``: ``max(0, V^MRV / V^bfr)`` auf dem aktuellen
        Verlauf, ab dem Beitragsende die gefuehrte Summe — dieselbe Regel wie
        ``KLV.beitragsfreie_summe`` und ``ReduzierterVertrag.beitragsfreie_summe``."""
        if self.gewoehnlich:
            return self.kern.beitragsfreie_summe(int(a))
        from rechner_pipeline.kern.zahlungspfad import (
            verlaufszeile as pfad_verlaufszeile,
            vertragskonstanten,
        )

        mp = self.kern.mp
        if a >= mp.t:
            return self.vs
        zeile = pfad_verlaufszeile(
            mp, self.pfad(), self.kern.basis, int(a),
            skalare=vertragskonstanten(mp, self.kern.basis))
        return untergrenze_basissumme(
            zeile.vx_mrv / self.kern.verlaufszeile(int(a)).vx_bfr)

    def satz_bfr(self, monate: int) -> float:
        """Beitragsfreier Reservesatz am lokalen Monats-Stichtag, linear
        zwischen den Jahrestagen (wie ``KLV.monatsreserve_beitragsfrei``)."""
        monate = int(monate)
        if monate > 12 * self.kern.mp.n:
            raise VorgangsfolgeFehler(
                f"Monats-Stichtag {monate} liegt nach dem Ablauf "
                f"(n = {self.kern.mp.n} Jahre)")
        a, rest = divmod(monate, 12)
        satz = self.kern.verlaufszeile(a).vx_bfr
        if rest:
            u = rest / 12.0
            satz = (1.0 - u) * satz + u * self.kern.verlaufszeile(a + 1).vx_bfr
        return satz

    def beitragskern(self) -> Rechenkern:
        """Der Kern des FORTGEFUEHRTEN Teils (Summe ``c`` mal wirksame Summe):
        Er traegt den Beitrag des Bausteins, einschliesslich der je Baustein
        festen Stueckkosten (Annahme B4; Pruefrunde T27, Befund 13)."""
        return Rechenkern(dataclasses.replace(
            self.kern.mp,
            sum_insured=self.beitragsfaktor * self.kern.mp.sum_insured))


@dataclass(frozen=True)
class Vorgangsergebnis:
    """Was ein Vorgang gebucht hat — die Soll-Groessen jeder Buchung.

    ``vs_neu`` ist die neue Gesamtsumme (beitragspflichtig: die gefuehrte
    Summe aller Bausteine; nach einer Beitragsfreistellung die beitragsfreie
    Gesamtsumme), ``absorbiert`` die dabei aufgenommene Korrekturschicht,
    ``auszahlung`` bei der Teilkuendigung die rechnerische Auszahlung (vor der
    Kappung auf null), sonst None. ``dk_vor``/``dk_nach`` sind das
    Deckungskapital des Vertrags am Wirkungstag vor und nach dem Vorgang
    (ohne Korrekturschicht), ``reduktionen`` je betroffenem Baustein seine
    Reduktion (Erhoehungsjahr, Reduktion) — die Groessen des GeVo-Tests.
    """

    vorgang: Vorgang
    vs_vor: float
    vs_neu: float
    absorbiert: float
    auszahlung: Optional[float]
    dk_vor: float
    dk_nach: float
    reduktionen: Tuple[Tuple[int, Reduktion], ...]


@dataclass(frozen=True)
class Vertragsstand:
    """Ein Vertrag in einem Zustand seiner Vorgangsfolge.

    ``grund_mp`` ist der Ursprungs-Modellpunkt der Grundversicherung (die
    Welt, auf der eine Korrekturschicht verankert ist), ``schicht`` die noch
    als eigene Position getragene Korrekturschicht (Parameter,
    Verankerungsmonat) — None, sobald ein Vorgang sie aufgenommen hat.
    """

    grund_mp: ModelPoint
    bausteine: Tuple[Baustein, ...]
    stoab_je_baustein: bool
    tku_umfang: str
    pex_jahr: Optional[int] = None
    schicht: Optional[Tuple[Any, int]] = None

    # ------------------------------------------------------------------ #
    # Aufbau
    # ------------------------------------------------------------------ #

    @classmethod
    def anfang(
        cls,
        grund: Rechenkern,
        scheiben: Sequence[Tuple[int, Rechenkern]] = (),
        *,
        stoab_je_baustein: bool,
        tku_umfang: str,
        schicht: Optional[Tuple[Any, int]] = None,
    ) -> "Vertragsstand":
        """Der Vertrag vor jedem Vorgang: Grundversicherung und die schon
        bestehenden Scheiben, gewoehnlich. Kein Default fuer das Tarifwerk —
        wer den Zustand baut, schreibt es hin (Pruefrunde T27, Befund 12)."""
        if tku_umfang not in TKU_UMFAENGE:
            raise VorgangsfolgeFehler(
                f"tku_umfang {tku_umfang!r} unbekannt (bekannt: {list(TKU_UMFAENGE)})")
        bausteine = (Baustein.aus_kern(0, grund),) + tuple(
            Baustein.aus_kern(int(e), k) for e, k in sorted(scheiben, key=lambda s: s[0]))
        return cls(grund_mp=grund.mp, bausteine=bausteine,
                   stoab_je_baustein=bool(stoab_je_baustein),
                   tku_umfang=str(tku_umfang),
                   schicht=None if schicht is None else (schicht[0], int(schicht[1])))

    @property
    def beitragsfrei(self) -> bool:
        return self.pex_jahr is not None

    def bestehend(self, monate: int) -> Tuple[Baustein, ...]:
        """Die Bausteine, die am Monats-Stichtag bestehen — eine Erhoehung
        gehoert ab ihrem Jahrestag zum Vertrag."""
        return tuple(b for b in self.bausteine if 12 * b.erh_jahr <= int(monate))

    def _schicht_bei(self, monate: int) -> float:
        if not schicht_traegt(self.schicht, int(monate)):
            return 0.0
        return schichtwert_bei(self.schicht[0], int(self.schicht[1]), self.grund_mp,
                               int(monate))

    def nach_erhoehung(self, jahr: int, kern: Rechenkern) -> "Vertragsstand":
        """Eine dynamische Erhoehung: ein neuer, gewoehnlicher Baustein — auch
        nach Herabsetzungen und Teilkuendigungen (Entscheid 2026-09-26)."""
        _jahr_der_folge(self.grund_mp, jahr, ERH)
        if self.beitragsfrei:
            raise VorgangsfolgeFehler(
                f"Erhoehung im Vertragsjahr {jahr} nach der Beitragsfreistellung "
                f"im Jahr {self.pex_jahr} — ein beitragsfreier Vertrag hat keine "
                "Dynamik mehr")
        return dataclasses.replace(
            self, bausteine=self.bausteine + (Baustein.aus_kern(int(jahr), kern),))

    def nach_pex(self, jahr: int) -> "Vertragsstand":
        """Die Beitragsfreistellung: Jeder Baustein fixiert seine beitragsfreie
        Summe auf seinem aktuellen Verlauf. Eine nach der Verankerung noch
        getragene Korrekturschicht geht wertstetig als Zuschlag in die Summe
        der Grundversicherung ein (``zuschlag_bei_pex``, Entscheid
        2026-09-15); liegt die Freistellung davor, laeuft sie als eigene
        Position weiter."""
        jahr = int(jahr)
        _jahr_der_folge(self.grund_mp, jahr, PEX)
        if self.beitragsfrei:
            raise VorgangsfolgeFehler(
                f"zweite Beitragsfreistellung im Jahr {jahr} (die erste im Jahr "
                f"{self.pex_jahr}) — ein Vertrag wird einmal beitragsfrei gestellt")
        neu: List[Baustein] = []
        for i, b in enumerate(self.bausteine):
            lokal = jahr - b.erh_jahr
            if i > 0 and lokal <= 0:
                raise VorgangsfolgeFehler(
                    f"Scheibe aus Vertragsjahr {b.erh_jahr} liegt nicht vor der "
                    f"Beitragsfreistellung (Jahr {jahr})")
            neu.append(dataclasses.replace(b, s_bfr=b.beitragsfreie_summe_bei(lokal)))
        schicht = self.schicht
        if schicht_traegt(schicht, 12 * jahr):
            neu[0] = dataclasses.replace(neu[0], zuschlag=zuschlag_bei_pex(
                schicht, Rechenkern(self.grund_mp), jahr))
            schicht = None
        return dataclasses.replace(self, bausteine=tuple(neu), pex_jahr=jahr,
                                   schicht=schicht)

    # ------------------------------------------------------------------ #
    # Werte
    # ------------------------------------------------------------------ #

    def _reserve_pol(self, monate: int, teile: Sequence[Baustein]) -> Monatsreserve:
        """Vertragsweite Monatsreserve des beitragspflichtigen Tracks —
        derselbe Weg wie ``vertrags_monatsreserve_reduziert``: Reserven je
        Baustein an seinem versetzten Stichtag, Stornoabzug nach dem
        Tarifwerk auf der gefuehrten Summe des Zustands."""
        if not teile:
            raise VorgangsfolgeFehler(
                "keine Bausteine — ein Vertrag ohne Grundversicherung ist keiner")
        dr = mrv = 0.0
        stuecke = []
        for b in teile:
            versetzt = int(monate) - 12 * b.erh_jahr
            if versetzt < 0:
                raise VorgangsfolgeFehler(
                    f"Erhoehungsscheibe aus Jahr {b.erh_jahr} existiert am "
                    f"Monats-Stichtag {monate} noch nicht")
            reserve = b.monatsreserve(versetzt)
            dr += reserve.drx_bpfl
            mrv += reserve.vx_mrv
            stuecke.append((b, versetzt, reserve))
        grund = teile[0].kern
        mp = grund.mp
        a = int(monate) // 12
        if self.stoab_je_baustein:
            stoab = rkw = 0.0
            for b, versetzt, reserve in stuecke:
                mp_k = b.kern.mp
                a_k = versetzt // 12
                if a_k > mp_k.n or b.kern.produkt.ist_flex_phase(a_k):
                    teil_stoab = 0.0
                else:
                    teil_stoab = min(
                        mp_k.stoab_max,
                        max(mp_k.stoab_min,
                            mp_k.stoab_satz * (b.vs - reserve.drx_bpfl)))
                stoab += teil_stoab
                rkw += max(0.0, reserve.vx_mrv - teil_stoab)
        else:
            if a > mp.n or grund.produkt.ist_flex_phase(a):
                stoab = 0.0
            else:
                vs = sum(b.vs for b in teile)
                stoab = min(mp.stoab_max,
                            max(mp.stoab_min, mp.stoab_satz * (vs - dr)))
            rkw = max(0.0, mrv - stoab)
        return Monatsreserve(
            monate=int(monate), jahr=a, monatsanteil=(int(monate) % 12) / 12.0,
            drx_bpfl=dr, vx_mrv=mrv, stoab=stoab, rkw=rkw,
        )

    def _reserve_bfr(self, monate: int, teile: Sequence[Baustein]) -> Dict[str, float]:
        """Reserve und Rueckkaufswert des beitragsfreien Vertrags (Entscheid B3 vom 2026-10-01).

        Deckungskapital: je Baustein die beitragsfreie Summe auf dem
        beitragsfreien Reservesatz. Rueckkaufswert: diese Rueckstellung
        abzueglich des Stornoabzugs nach derselben Tarifregel, angewandt auf
        die beitragsfreie Summe und ihre Rueckstellung (:func:`stornoabzug_auf`;
        je Vertrag oder je Baustein nach dem Tarifwerk), null in der
        flexiblen Phase, nie negativ. Die wertstetig ueberfuehrte Schicht ist
        Teil der garantierten Summe und zaehlt mit; ausgewiesen wird sie
        trotzdem als ``korrekturschicht`` (Grundsatzdokumentation 9.11)."""
        dk = korr = summe = 0.0
        rkw_je = 0.0
        stoab_je = 0.0
        stuecke = []
        for b in teile:
            lokal = int(monate) - 12 * b.erh_jahr
            satz = b.satz_bfr(lokal)
            basis = b.s_bfr * satz
            zusatz = b.zuschlag * satz
            dk += basis
            korr += zusatz
            s = b.s_bfr + b.zuschlag
            summe += s
            stuecke.append((b, lokal, s, basis + zusatz))
            if self.stoab_je_baustein:
                teil = stornoabzug_auf(b.kern, lokal // 12, s, basis + zusatz)
                stoab_je += teil
                rkw_je += max(0.0, basis + zusatz - teil)
        if self.stoab_je_baustein:
            stoab, rkw = stoab_je, rkw_je
        else:
            grund = teile[0].kern
            stoab = stornoabzug_auf(grund, int(monate) // 12, summe, dk + korr)
            rkw = max(0.0, dk + korr - stoab)
        return {"dk": dk, "korr": korr, "stoab": stoab, "rkw": rkw,
                "vs_bfr": summe}

    def werte(self, monate: int) -> Dict[str, float]:
        """Die Bewertungsgroessen am Monats-Stichtag (``monate`` volle Monate
        seit Versicherungsbeginn), ueber die dann bestehenden Bausteine.

        ``deckungskapital`` enthaelt die Korrekturschicht (eigene Position
        oder ueberfuehrt), ``korrekturschicht`` weist sie aus;
        ``rueckkaufswert`` ist der des Zustands (beitragsfrei: Entscheid B3 vom 2026-10-01),
        ``leistung`` die gefuehrte Summe des beitragspflichtigen Tracks,
        ``vs_bfr`` die beitragsfreie Gesamtsumme (0 vor der Freistellung)."""
        teile = self.bestehend(monate)
        korr_eigen = self._schicht_bei(monate)
        leistung = sum(b.vs for b in teile)
        if not self.beitragsfrei:
            r = self._reserve_pol(monate, teile)
            return {"status": "POL", "deckungskapital": r.drx_bpfl + korr_eigen,
                    "rueckkaufswert": r.rkw + korr_eigen,
                    "korrekturschicht": korr_eigen, "vs_bfr": 0.0,
                    "leistung": leistung, "vx_mrv": r.vx_mrv, "stoab": r.stoab}
        r = self._reserve_bfr(monate, teile)
        return {"status": "PEX",
                "deckungskapital": r["dk"] + r["korr"] + korr_eigen,
                "rueckkaufswert": r["rkw"] + korr_eigen,
                "korrekturschicht": r["korr"] + korr_eigen,
                "vs_bfr": self.vs_bfr(), "leistung": leistung,
                "vx_mrv": r["dk"] + r["korr"], "stoab": r["stoab"]}

    def reserve(self, monate: int) -> Monatsreserve:
        """Die vertragsweite Monatsreserve des beitragspflichtigen Tracks,
        ohne Korrekturschicht (der Spiegel von ``vertrags_monatsreserve``)."""
        if self.beitragsfrei:
            raise VorgangsfolgeFehler(
                "beitragsfreier Vertrag: die Reserve steht in werte()")
        return self._reserve_pol(monate, self.bestehend(monate))

    def gesamt_vs(self) -> float:
        """Die gefuehrte Summe aller Bausteine (beitragspflichtiger Track) —
        Bezugsgroesse einer Erhoehung und Leistung bei Tod und Ablauf, solange
        der Vertrag beitragspflichtig ist."""
        return sum(b.vs for b in self.bausteine)

    def vs_bfr(self) -> float:
        """Die beitragsfreie Gesamtsumme — Leistung bei Tod und Ablauf nach
        der Beitragsfreistellung. Dieselbe Summationsreihenfolge wie die
        Leser des herabgesetzten Vertrags vorher (Summe ueber alle Bausteine,
        dann der Zuschlag der Schicht)."""
        if not self.beitragsfrei:
            return 0.0
        return (sum(b.s_bfr for b in self.bausteine)
                + sum(b.zuschlag for b in self.bausteine))

    def leistung(self) -> float:
        """Die Leistung eines terminalen Falls (Tod, Ablauf)."""
        return self.vs_bfr() if self.beitragsfrei else self.gesamt_vs()

    def rkw(self, jahr: int) -> float:
        """Der Rueckkaufswert am Jahrestag ``jahr`` (Storno): der des
        Zustands, plus eine noch als eigene Position getragene Schicht."""
        return self.werte(12 * int(jahr))["rueckkaufswert"]

    def beitragskerne(self, monate: int) -> List[Tuple[int, Rechenkern]]:
        """Je bestehendem Baustein (Erhoehungsjahr, Kern des fortgefuehrten
        Teils) — leer nach der Beitragsfreistellung."""
        if self.beitragsfrei:
            return []
        return [(b.erh_jahr, b.beitragskern()) for b in self.bestehend(monate)]

    # ------------------------------------------------------------------ #
    # Vorgaenge
    # ------------------------------------------------------------------ #

    def _betroffen(self, jahr: int, art: str) -> List[int]:
        """Indizes der Bausteine, die ein Vorgang im Jahr ``jahr`` trifft:
        alle schon bestehenden (eine Scheibe desselben Jahrestags entsteht
        danach); bei der Teilkuendigung mit Umfang ``grundversicherung`` nur
        die Grundversicherung."""
        if art == TKU and self.tku_umfang == UMFANG_GRUND:
            return [0]
        return [i for i, b in enumerate(self.bausteine)
                if i == 0 or b.erh_jahr < int(jahr)]

    def nach_vorgang(self, v: Vorgang) -> Tuple["Vertragsstand", Vorgangsergebnis]:
        """Den Vorgang ``v`` auf diesen Zustand anwenden."""
        if v.art not in (RED, TKU):
            raise VorgangsfolgeFehler(f"unbekannter Vorgang {v.art!r} (RED, TKU)")
        if (v.art == TKU) != (v.verfahren == TEILKUENDIGUNG):
            raise VorgangsfolgeFehler(
                f"Vorgang {v.art} mit Verfahren {v.verfahren!r} — die Teilkuendigung "
                "traegt das Verfahren 'teilkuendigung', die Beitragsherabsetzung das "
                "des Tarifs (prospektiv, mit_abzug)")
        if not math.isfinite(v.anteil) or not 0.0 < v.anteil <= 1.0:
            raise VorgangsfolgeFehler(
                f"Anteil {v.anteil!r} liegt nicht in (0, 1] — er ist der "
                "fortgefuehrte Anteil; 0 waere eine Beitragsfreistellung bzw. ein "
                "Rueckkauf")
        try:
            if v.art == RED:
                return self._herabsetzen(v)
            return self._teilkuendigen(v)
        except VorgangsfolgeFehler:
            raise
        except BeitragsreduktionFehler as exc:
            # Die Eingangswachen der Einzelreduktion (Laufzeit, Beitragsende)
            # gelten unveraendert; benannt als Fehler der Folge.
            raise VorgangsfolgeFehler(str(exc)) from exc

    def _dk(self, monate: int) -> float:
        """Deckungskapital ohne Korrekturschicht (Groesse des GeVo-Tests)."""
        teile = self.bestehend(monate)
        if self.beitragsfrei:
            r = self._reserve_bfr(monate, teile)
            return r["dk"] + r["korr"]
        return self._reserve_pol(monate, teile).drx_bpfl

    def _herabsetzen(self, v: Vorgang) -> Tuple["Vertragsstand", Vorgangsergebnis]:
        jahr, f = int(v.jahr), float(v.anteil)
        if self.beitragsfrei:
            raise VorgangsfolgeFehler(
                f"Beitragsherabsetzung im Vertragsjahr {jahr} nach der "
                f"Beitragsfreistellung im Jahr {self.pex_jahr} — ein beitragsfreier "
                "Vertrag hat keinen Beitrag, den eine Herabsetzung senken koennte "
                "(Tarifplan KLV 7.1). Ausweg: die Teilkuendigung (TKU), die einen "
                "Anteil der beitragsfreien Summe kuendigt und auszahlt")
        if v.verfahren not in (PROSPEKTIV, MIT_ABZUG):
            raise VorgangsfolgeFehler(
                f"Beitragsherabsetzung mit Verfahren {v.verfahren!r} — bekannt sind "
                f"{[PROSPEKTIV, MIT_ABZUG]}")
        grund_kern = self.bausteine[0].kern
        _pruefe_eingaben(grund_kern.mp, jahr, f, v.verfahren)
        idx = self._betroffen(jahr, RED)
        teile = [self.bausteine[i] for i in idx]
        zusatz = self._schicht_bei(12 * jahr)
        monate = 12 * jahr
        dk_vor = self._dk(monate)
        vs_vor = self.gesamt_vs()
        vorher = [b.monatsreserve(12 * (jahr - b.erh_jahr)) for b in teile]

        if v.verfahren == PROSPEKTIV:
            nach_abzug = [1.0] * len(teile)
        elif self.stoab_je_baustein:
            # Je Baustein sein eigener Rueckkaufswert (Bedingungswerk Ziffer
            # 4; Runde F, Nachbesserung 2) — auf dem Zustand des Bausteins.
            nach_abzug = [
                _abzugsfaktor(r.vx_mrv, stornoabzug_auf(
                    b.kern, jahr - b.erh_jahr, b.vs, r.drx_bpfl))
                for b, r in zip(teile, vorher)]
        else:
            # Je Vertrag (Tarifplan 6): (1-f) x RKW des Vertrags, verteilt nach
            # dem auf null begrenzten Rueckkaufs-Track der Bausteine (Runde F, F1).
            gesamt = self._reserve_pol(monate, teile)
            positiv = _positiver_rueckkaufstrack(vorher)
            faktor = min(1.0, gesamt.rkw / positiv) if positiv > 0.0 else 1.0
            nach_abzug = [faktor] * len(teile)

        neu = list(self.bausteine)
        reduktionen: List[Tuple[int, Reduktion]] = []
        for k, (i, b) in enumerate(zip(idx, teile)):
            a = jahr - b.erh_jahr
            zeile = b.kern.verlaufszeile(a)
            c = b.beitragsfaktor
            s_eff = b.kern.mp.sum_insured
            umgewandelt = untergrenze_basissumme(
                c * zeile.vx_mrv * nach_abzug[k] * (1.0 - f))
            # Die Korrekturschicht geht ungekuerzt in den umgewandelten Teil der
            # Grundversicherung (Entscheid 2026-09-15; klv.md 7.1).
            if i == 0 and zusatz:
                umgewandelt += zusatz
            if zeile.vx_bfr <= 0.0:
                raise VorgangsfolgeFehler(
                    f"Vertragsjahr {a}: beitragsfreier Reservesatz ist "
                    f"{zeile.vx_bfr!r} — eine Umwandlung ist dort nicht definiert")
            teil = umgewandelt / zeile.vx_bfr
            vs_bpfl = s_eff * c
            vs_neu = vs_bpfl * f + teil + (b.vs - vs_bpfl)
            dk_bpfl = c * zeile.drx_bpfl
            dk_b_vor = vorher[k].drx_bpfl
            dk_b_nach = dk_bpfl * f + (dk_b_vor - dk_bpfl) + umgewandelt
            c_neu = c * f
            q_neu = (vs_neu - c_neu * s_eff) / s_eff
            bjb_alt = (b.kern if c == 1.0 else b.beitragskern()).gross_annual_premium()
            reduktionen.append((b.erh_jahr, Reduktion(
                jahr=a, anteil=f, verfahren=v.verfahren, vs_alt=b.vs, vs_neu=vs_neu,
                bjb_alt=bjb_alt, bjb_neu=bjb_alt * f, dk_vor=dk_b_vor,
                dk_nach=dk_b_nach)))
            neu[i] = dataclasses.replace(
                b, vs=vs_neu, abschnitte=b.abschnitte + ((a, c_neu, q_neu),))
        # Aufgenommen ist die Schicht, sobald sie traegt — auch mit Wert null.
        stand = dataclasses.replace(self, bausteine=tuple(neu), schicht=None
                                    if schicht_traegt(self.schicht, monate)
                                    else self.schicht)
        ergebnis = Vorgangsergebnis(
            vorgang=v, vs_vor=vs_vor, vs_neu=stand.gesamt_vs(), absorbiert=zusatz,
            auszahlung=None, dk_vor=dk_vor, dk_nach=stand._dk(monate),
            reduktionen=tuple(reduktionen))
        return stand, ergebnis

    def _teilkuendigen(self, v: Vorgang) -> Tuple["Vertragsstand", Vorgangsergebnis]:
        jahr, f = int(v.jahr), float(v.anteil)
        grund_kern = self.bausteine[0].kern
        _pruefe_eingaben(grund_kern.mp, jahr, f, TEILKUENDIGUNG)
        monate = 12 * jahr
        idx = self._betroffen(jahr, TKU)
        teile = [self.bausteine[i] for i in idx]
        zusatz = self._schicht_bei(monate)
        dk_vor = self._dk(monate)
        vs_vor = self.vs_bfr() if self.beitragsfrei else self.gesamt_vs()
        # Der Rueckkaufswert des BETROFFENEN Teils unmittelbar vor dem Vorgang
        # — je Vertrag oder je Baustein nach dem Tarifwerk; nach einer
        # Beitragsfreistellung der des beitragsfreien Vertrags (B3).
        if self.beitragsfrei:
            rkw_vor = self._reserve_bfr(monate, teile)["rkw"]
        else:
            rkw_vor = self._reserve_pol(monate, teile).rkw
        auszahlung = (1.0 - f) * rkw_vor + zusatz

        neu = list(self.bausteine)
        reduktionen: List[Tuple[int, Reduktion]] = []
        for i, b in zip(idx, teile):
            a = jahr - b.erh_jahr
            kern_neu = Rechenkern(dataclasses.replace(
                b.kern.mp, sum_insured=f * b.kern.mp.sum_insured))
            b_neu = dataclasses.replace(
                b, kern=kern_neu, vs=f * b.vs,
                s_bfr=None if b.s_bfr is None else f * b.s_bfr,
                zuschlag=f * b.zuschlag)
            if b.beitragsfrei:
                vor_b = (b.s_bfr + b.zuschlag) * b.satz_bfr(12 * a)
                nach_b = (b_neu.s_bfr + b_neu.zuschlag) * b_neu.satz_bfr(12 * a)
            else:
                vor_b = b.monatsreserve(12 * a).vx_mrv
                nach_b = b_neu.monatsreserve(12 * a).vx_mrv
            reduktionen.append((b.erh_jahr, Reduktion(
                jahr=a, anteil=f, verfahren=TEILKUENDIGUNG, vs_alt=b.vs,
                vs_neu=b_neu.vs,
                bjb_alt=0.0 if b.beitragsfrei else b.beitragskern().gross_annual_premium(),
                bjb_neu=0.0 if b.beitragsfrei else b_neu.beitragskern().gross_annual_premium(),
                dk_vor=vor_b, dk_nach=nach_b)))
            neu[i] = b_neu
        stand = dataclasses.replace(self, bausteine=tuple(neu), schicht=None
                                    if schicht_traegt(self.schicht, monate)
                                    else self.schicht)
        ergebnis = Vorgangsergebnis(
            vorgang=v, vs_vor=vs_vor,
            vs_neu=stand.vs_bfr() if stand.beitragsfrei else stand.gesamt_vs(),
            absorbiert=zusatz, auszahlung=auszahlung, dk_vor=dk_vor,
            dk_nach=stand._dk(monate), reduktionen=tuple(reduktionen))
        return stand, ergebnis


class Vorgangsfolge:
    """Die Folge der Vorgaenge eines Vertrags, gefaltet in Zustaende.

    ``grund`` und ``scheiben`` sind die Kerne der Grundversicherung und der
    Erhoehungsscheiben (Erhoehungsjahr, Kern), ``vorgaenge`` die Zeilen der
    Nebentabelle ``reduktionen`` dieser Police (in beliebiger Reihenfolge —
    geordnet wird hier), ``pex_jahr`` das Vertragsjahr einer
    Beitragsfreistellung, ``schicht`` die Korrekturschicht eines
    uebernommenen Vertrags. Das Tarifwerk (Stornoabzug je Baustein,
    Umfang der Teilkuendigung) hat keinen Default.

    Verweigert (benannt, mit Ausweg) wird, was der Tarifplan ausschliesst
    (KLV 7.3): ein Vorgang ausserhalb der Vertragsjahre ``0 < a < n`` (auch
    im Jahr 0; die Grenzen stehen an einer Stelle,
    ``beitragsreduktion.pruefe_vorgangsjahr``), eine Beitragsherabsetzung,
    Erhoehung oder Beitragsfreistellung ab dem Beitragsende, eine
    Beitragsherabsetzung nach der Beitragsfreistellung, zwei gleiche
    Vorgaenge am selben Jahrestag, eine Erhoehung nach der
    Beitragsfreistellung.
    """

    def __init__(
        self,
        grund: Rechenkern,
        scheiben: Sequence[Tuple[int, Rechenkern]],
        vorgaenge: Sequence[Vorgang],
        *,
        pex_jahr: Optional[int] = None,
        schicht: Optional[Tuple[Any, int]] = None,
        stoab_je_baustein: bool,
        tku_umfang: str,
    ) -> None:
        geordnet = sorted(vorgaenge, key=lambda v: v.schluessel)
        schluessel = [v.schluessel for v in geordnet]
        doppelt = sorted({s for s in schluessel if schluessel.count(s) > 1})
        if doppelt:
            jahr, rang = doppelt[0]
            art = next(a for a, r in RANG.items() if r == rang)
            raise VorgangsfolgeFehler(
                f"zwei Vorgaenge {art} am Jahrestag des Vertragsjahres {jahr} — je "
                "Jahrestag gibt es hoechstens eine Herabsetzung und eine "
                "Teilkuendigung; ihre Reihenfolge waere nicht bestimmt. Ausweg: die "
                "beiden Anteile zu einem Vorgang zusammenfassen (f = f1 x f2)")
        self.vorgaenge: Tuple[Vorgang, ...] = tuple(geordnet)
        zeitachse: List[Tuple[Tuple[int, int], str, Any]] = []
        anfangs_scheiben = []
        for e, k in scheiben:
            # Scheiben vor dem ersten Ereignis der Folge sind Anfangsbestand
            # (auch mitgebrachte Bausteine eines uebernommenen Vertrags).
            zeitachse.append(((int(e), RANG[ERH]), ERH, (int(e), k)))
        for v in geordnet:
            zeitachse.append((v.schluessel, v.art, v))
        if pex_jahr is not None:
            zeitachse.append(((int(pex_jahr), RANG[PEX]), PEX, int(pex_jahr)))
        zeitachse.sort(key=lambda z: z[0])
        stand = Vertragsstand.anfang(
            grund, anfangs_scheiben, stoab_je_baustein=stoab_je_baustein,
            tku_umfang=tku_umfang, schicht=schicht)
        self._staende: List[Tuple[Tuple[int, int], Vertragsstand]] = [
            ((-1, -1), stand)]
        self.ergebnisse: List[Vorgangsergebnis] = []
        for schl, art, inhalt in zeitachse:
            if art == ERH:
                stand = stand.nach_erhoehung(inhalt[0], inhalt[1])
            elif art == PEX:
                stand = stand.nach_pex(inhalt)
            else:
                stand, ergebnis = stand.nach_vorgang(inhalt)
                self.ergebnisse.append(ergebnis)
            self._staende.append((schl, stand))

    def stand_am(self, monate: int) -> Vertragsstand:
        """Der Zustand am Monats-Stichtag: alle Vorgaenge bis einschliesslich
        zu seinem Jahrestag (Bewertung)."""
        aktuell = self._staende[0][1]
        for (jahr, _rang), stand in self._staende[1:]:
            if 12 * jahr <= int(monate):
                aktuell = stand
        return aktuell

    def stand_vor(self, jahr: int, art: str) -> Vertragsstand:
        """Der Zustand unmittelbar VOR einem Vorgang der Art ``art`` am
        Jahrestag ``jahr`` (Storno, Tod, Ablauf: ``art`` = ``PEX``, also vor
        allen Vorgaengen des Tages)."""
        grenze = (int(jahr), RANG[art])
        aktuell = self._staende[0][1]
        for schl, stand in self._staende[1:]:
            if schl < grenze:
                aktuell = stand
        return aktuell

    def ergebnis(self, jahr: int, art: str) -> Optional[Vorgangsergebnis]:
        """Das Ergebnis des Vorgangs ``art`` am Jahrestag ``jahr`` (None, wenn
        die Folge keinen solchen kennt)."""
        for e in self.ergebnisse:
            if e.vorgang.schluessel == (int(jahr), RANG[art]):
                return e
        return None

    @property
    def erstes_jahr(self) -> Optional[int]:
        """Das Vertragsjahr des ersten Vorgangs (None ohne Vorgang)."""
        return self.vorgaenge[0].jahr if self.vorgaenge else None
