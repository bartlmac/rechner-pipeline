"""Beitragsreduktion: zwei vertretbare Verfahren, eine echte Differenz.

Eine Beitragsreduktion ist der Geschaeftsvorfall, an dem sich zeigt,
wofuer die Korrekturschicht da ist. Ihr Ergebnis ist **nirgends per
Groesse garantiert**: Anders als die Versicherungssumme oder die
Ablaufleistung gibt es keinen zugesagten Wert, den zwei Systeme treffen
muessten. Jedes Haus rechnet sie nach seinem eigenen, aktuariell
sauberen Verfahren — und genau daraus entsteht eine Differenz, die kein
Fehler ist.

Die Grundsatzdokumentation fuehrt sie in 9.7 als rechnenden
Geschaeftsvorfall (Klasse A, "Herabsetzung").

**Die gemeinsame Konstruktion.** Der Vertrag wird NICHT geteilt. Er
bekommt ab dem Reduktionsjahr einen geknickten Verlauf: Der Beitrag faellt
auf den Anteil ``f``, und der freiwerdende Reserveanteil wird in
beitragsfreie Summe umgewandelt, die als eigenes Leistungsprofil neben
dem fortgefuehrten steht (:func:`als_zahlungspfad`). Weil der
Jahresbeitrag proportional zur Versicherungssumme ist (``BJB = VS *
Bxt``), ist ``f`` zugleich der Beitrags- und der Summenanteil des
fortgefuehrten Teils.

Die Rede vom "geteilten Vertrag" stammt aus der Zeit, in der die
Folgebewertung zwei skalierte Vertraege addierte. Sie hat die Mathematik
falsch dargestellt: Es gibt einen Vertrag und einen Verlauf.

**Wo sie sich unterscheiden: was mit dem freiwerdenden Reserveanteil
geschieht.**

``prospektiv`` (Zielverfahren)
    Der freiwerdende Anteil wird **verlustfrei** in beitragsfreie
    Versicherungssumme umgewandelt — mit demselben Satz, den auch die
    vollstaendige Beitragsfreistellung verwendet. Die Deckungs-
    rueckstellung bleibt in voller Hoehe im Vertrag.

``mit_abzug`` (verbreitetes Altverfahren)
    Das System behandelt die Reduktion wie eine **Teilkuendigung**: Auf
    den freiwerdenden Anteil wird der anteilige Stornoabzug erhoben,
    bevor er in beitragsfreie Summe umgewandelt wird. Auch das ist
    vertretbar — bei einem Teilrueckkauf ist der Abzug ueblich, und
    genau so haben viele Altbestaende die Herabsetzung geführt.

Beide treffen die Randfaelle: Bei ``f = 1`` (keine Reduktion) aendert
sich nichts, bei ``f = 0`` sind sie die vollstaendige
Beitragsfreistellung — verlustfrei die eine, mit Abzug die andere.
Dazwischen weichen sie um den anteiligen Stornoabzug ab.

Knoten: klv
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rechner_pipeline.kern.produkte.klv import Monatsreserve

from rechner_pipeline.kern.rechenkern import (
    Rechenkern,
    vertrags_monatsreserve,
)

#: Die beiden Verfahren. Welches gilt, ist eine Eigenschaft des SYSTEMS,
#: nicht des Vertrags — deshalb steht es im Beleg der Migration und nicht
#: im Modellpunkt.
PROSPEKTIV = "prospektiv"
MIT_ABZUG = "mit_abzug"
VERFAHREN = (PROSPEKTIV, MIT_ABZUG)


class BeitragsreduktionFehler(ValueError):
    """Reduktion nicht durchfuehrbar — fail-fast statt stiller Naeherung."""


@dataclass(frozen=True)
class Reduktion:
    """Das Ergebnis einer Beitragsreduktion im Vertragsjahr ``jahr``."""

    jahr: int
    anteil: float
    verfahren: str
    vs_alt: float
    vs_neu: float
    bjb_alt: float
    bjb_neu: float
    dk_vor: float
    dk_nach: float

    @property
    def d_dk(self) -> float:
        """Veraenderung des Deckungskapitals — der Pruefwert des GeVo-Tests."""
        return self.dk_nach - self.dk_vor

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "jahr": self.jahr,
            "anteil": self.anteil,
            "verfahren": self.verfahren,
            "vs_alt": self.vs_alt,
            "vs_neu": self.vs_neu,
            "bjb_alt": self.bjb_alt,
            "bjb_neu": self.bjb_neu,
            "dk_vor": self.dk_vor,
            "dk_nach": self.dk_nach,
            "dDK": self.d_dk,
        }


def reduziere(
    kern: Rechenkern, jahr: int, anteil: float, *, verfahren: str = PROSPEKTIV
) -> Reduktion:
    """Den Beitrag im Vertragsjahr ``jahr`` auf ``anteil`` senken.

    ``anteil`` ist der fortgefuehrte Bruchteil des Beitrags: ``0.6`` senkt
    ihn auf 60 Prozent. ``1.0`` ist keine Reduktion, ``0.0`` die
    vollstaendige Beitragsfreistellung.

    **Nur am Vertragsstichtag** (Beschluss 2026-08-28). Die Signatur nimmt
    ein Vertragsjahr, keine Monate. Die Rumpfjahr-Konvention der
    KORREKTURSCHICHT ist seit 2026-08-31 entschieden (9.6-Nachtrag:
    Verankerung und Bewertung am unterjaehrigen t_a) — sie regelt aber
    nur, wie die Schicht einen unterjaehrigen Punkt TRAEGT, nicht die
    unterjaehrige AUSFUEHRUNG eines Geschaeftsvorfalls. Eine Reduktion
    zwischen zwei Jahrestagen braucht zusaetzlich den unterjaehrigen
    Knick des Zahlungsprofils samt Beitragsabgrenzung — ein eigener Bau,
    kein Monatsparameter an dieser Signatur.
    """
    _pruefe_eingaben(kern.mp, jahr, anteil, verfahren)

    zeile = kern.verlaufszeile(jahr)
    # Der ungeteilte Vertrag traegt seinen eigenen Stornoabschlag; beim
    # verlustfreien Verfahren wird keiner erhoben.
    nach_abzug = (
        1.0 if verfahren == PROSPEKTIV
        else _abzugsfaktor(zeile.drx_bpfl, zeile.stoab, jahr)
    )
    return _reduziere_eine_schicht(kern, jahr, anteil, nach_abzug, verfahren)


def _pruefe_eingaben(
    mp: ModelPoint, jahr: int, anteil: float, verfahren: str
) -> None:
    """Die Eingangswachen — fuer JEDEN Weg in die Reduktion dieselben.

    Sie standen einmal nur im ungeteilten Weg. Der geschichtete lief
    daran vorbei und nahm klaglos einen Anteil von -1 (negative
    Versicherungssummen), einen Anteil von 5 (der Vertrag verdreifacht
    sich) und ein Vertragsjahr nach dem Beitragsende (es gibt keinen
    Beitrag mehr zu senken). Eine Wache, die nur an einem von zwei
    Eingaengen steht, ist keine.

    Beim geschichteten Vertrag genuegt die Pruefung am Grundvertrag: Jede
    Scheibe traegt ``n' = n - e`` und ``t' = t - e`` und rechnet im
    Vertragsjahr ``jahr - e`` — die Bedingungen sind damit aequivalent.
    """
    if verfahren not in VERFAHREN:
        raise BeitragsreduktionFehler(
            f"unbekanntes Verfahren {verfahren!r} — bekannt sind {list(VERFAHREN)}"
        )
    if not math.isfinite(anteil) or not 0.0 <= anteil <= 1.0:
        raise BeitragsreduktionFehler(
            f"Anteil {anteil!r} liegt nicht in [0, 1] — er ist der "
            "fortgefuehrte Bruchteil des Beitrags"
        )
    if jahr < 0 or jahr > mp.n:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr} ausserhalb der Laufzeit (n={mp.n})"
        )
    if jahr >= mp.t:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: die Beitragszahlungsdauer ist beendet "
            f"(t={mp.t}) — es gibt keinen Beitrag zu reduzieren"
        )


def _abzugsfaktor(dk: float, stoab: float, jahr: int) -> float:
    """Der Anteil der Reserve, der den Stornoabschlag ueberlebt."""
    if dk <= 0.0:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: Deckungsrueckstellung ist {dk!r} — ein "
            "anteiliger Stornoabschlag ist darauf nicht bildbar"
        )
    return 1.0 - stoab / dk


def _reduziere_eine_schicht(
    kern: Rechenkern,
    jahr: int,
    anteil: float,
    nach_abzug: float,
    verfahren: str = PROSPEKTIV,
) -> "Reduktion":
    """Die Reduktion EINER Schicht — der gemeinsame Rechenteil.

    ``nach_abzug`` ist der Anteil der Reserve, der die Umwandlung
    ueberlebt: 1.0 beim verlustfreien Verfahren, sonst der vertragsweit
    gebildete Faktor. Beim ungeteilten Vertrag ist die Schicht der
    Vertrag, und beide Wege rechnen dieselbe Formel — deshalb steht sie
    hier einmal.
    """
    mp = kern.mp
    zeile = kern.verlaufszeile(jahr)
    dk_vor = zeile.drx_bpfl
    vs_alt = mp.sum_insured
    bjb_alt = kern.gross_annual_premium()

    # Der fortgefuehrte Teil bleibt unveraendert; nur der freiwerdende
    # Anteil wird umgewandelt.
    umgewandelt = dk_vor * nach_abzug * (1.0 - anteil)

    if zeile.vx_bfr <= 0.0:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: beitragsfreier Reservesatz ist "
            f"{zeile.vx_bfr!r} — eine Umwandlung ist dort nicht definiert"
        )
    vs_bfr_teil = umgewandelt / zeile.vx_bfr
    vs_neu = vs_alt * anteil + vs_bfr_teil

    # Das Deckungskapital nach dem Vorfall: der fortgefuehrte Teil traegt
    # seine anteilige Reserve, der umgewandelte seinen Wert.
    dk_nach = dk_vor * anteil + umgewandelt

    return Reduktion(
        jahr=jahr,
        anteil=anteil,
        verfahren=verfahren,
        vs_alt=vs_alt,
        vs_neu=vs_neu,
        bjb_alt=bjb_alt,
        bjb_neu=bjb_alt * anteil,
        dk_vor=dk_vor,
        dk_nach=dk_nach,
    )


def reduziere_geschichtet(
    grund: Rechenkern,
    scheiben: Sequence[Tuple[int, Rechenkern]],
    jahr: int,
    anteil: float,
    *,
    verfahren: str = PROSPEKTIV,
) -> List[Tuple[int, "Reduktion"]]:
    """Herabsetzung eines Vertrags MIT dynamischen Erhoehungsscheiben.

    **Anteilig ueber alle Schichten** (Tarifplan KLV 12, entschieden
    2026-08-31): Jede Schicht traegt denselben Faktor ``anteil``. Das ist
    keine willkuerliche Wahl unter mehreren, sondern die einzige Regel,
    die ohne neue Konvention auskommt — weil der Jahresbeitrag jeder
    Schicht proportional zu ihrer Summe ist, ergibt derselbe Faktor je
    Schicht in der Summe genau den Zielbeitrag::

        sum_i (f * BJB_i) = f * sum_i BJB_i

    Die Alternativen brauchen mehr als eine Rechnung: "juengste zuerst"
    braucht eine Reihenfolge und eine Regel fuer die teilweise
    zurueckgenommene Schicht, "nur die Grundscheibe" laesst den Beitrag
    der Erhoehungen unsenkbar.

    **Der Stornoabschlag bleibt vertragsweit.** Seine Grenzen
    ``stoab_min``/``stoab_max`` gelten je VERTRAG (Tarifplan 6); je
    Schicht gebildet griffen sie mehrfach und der Abzug waere bei einem
    geschichteten Vertrag ein Vielfaches des zugesagten. Er wird deshalb
    EINMAL auf den Gesamtwerten gebildet und dann proportional zur
    Deckungsrueckstellung der Schicht verteilt — dem Anteil, aus dem der
    umgewandelte Betrag stammt. Beim verlustfreien Verfahren entfaellt
    die Frage, dort wird kein Abzug erhoben.

    Rueckgabe: je Schicht ihr Erhoehungsjahr und ihre Reduktion, in der
    Reihenfolge (Grundscheibe zuerst) von ``vertrags_monatsreserve``.
    """
    teile: List[Tuple[int, Rechenkern]] = [(0, grund)] + list(scheiben)
    _pruefe_eingaben(grund.mp, jahr, anteil, verfahren)

    # Erst die Schichten pruefen, dann rechnen: Eine Scheibe, die es im
    # Reduktionsjahr noch nicht gibt, soll als Reduktionsfehler auffallen
    # und nicht tief in der vertragsweiten Reserve.
    for erh_jahr, _kern in teile:
        if jahr - erh_jahr < 0:
            raise BeitragsreduktionFehler(
                f"Erhoehungsscheibe aus Jahr {erh_jahr} existiert im "
                f"Vertragsjahr {jahr} noch nicht"
            )

    # Die vertragsweiten Groessen am Reduktionsstichtag: Sie entscheiden
    # ueber den Abzug, bevor irgendeine Schicht gerechnet wird.
    gesamt = vertrags_monatsreserve(grund, list(scheiben), 12 * jahr)
    # Der Anteil der Reserve, der die Umwandlung ueberlebt. Derselbe
    # Faktor fuer jede Schicht: Der Abzug ist vertragsweit gebildet und
    # wird proportional zur eingebrachten Reserve getragen.
    nach_abzug = (
        1.0 if verfahren == PROSPEKTIV
        else _abzugsfaktor(gesamt.drx_bpfl, gesamt.stoab, jahr)
    )

    aus: List[Tuple[int, "Reduktion"]] = []
    for erh_jahr, kern in teile:
        # Die Schicht rechnet ihre eigene Reduktion — mit ihrem eigenen
        # Eintrittsalter, ihrer eigenen Restdauer und ihrem eigenen
        # beitragsfreien Reservesatz. Nur der Abzug kommt von aussen.
        aus.append((erh_jahr, _reduziere_eine_schicht(
            kern, jahr - erh_jahr, anteil, nach_abzug, verfahren)))
    return aus


def vertrags_monatsreserve_reduziert(
    teile: Sequence[Tuple[int, "ReduzierterVertrag"]], monate: int
) -> "Monatsreserve":
    """Vertragsweite Monatsreserve eines herabgesetzten GESCHICHTETEN Vertrags.

    Spiegel von
    :func:`rechner_pipeline.kern.rechenkern.vertrags_monatsreserve`, nur
    dass jede Schicht ihren herabgesetzten Verlauf rechnet: Reserven sind
    die Summe der Schichtwerte, jede an ihrem versetzten Stichtag; der
    Stornoabschlag gilt je VERTRAG und wird einmal auf den Gesamtwerten
    gebildet.

    Bezugsgroesse des Abschlags ist die NEUE Gesamtsumme — die Summe der
    ``vs_neu`` aller Schichten, also fortgefuehrter plus umgewandelter
    Teil. Die alte waere die Summe eines Vertrags, den es nicht mehr gibt.
    """
    from rechner_pipeline.kern.produkte.klv import Monatsreserve

    if not teile:
        raise BeitragsreduktionFehler(
            "keine Schichten — ein Vertrag ohne Grundscheibe ist keiner")
    dr = mrv = 0.0
    for erh_jahr, vertrag in teile:
        versetzt = monate - 12 * erh_jahr
        if versetzt < 0:
            raise BeitragsreduktionFehler(
                f"Erhoehungsscheibe aus Jahr {erh_jahr} existiert am "
                f"Monats-Stichtag {monate} noch nicht"
            )
        reserve = vertrag.monatsreserve(versetzt)
        dr += reserve.drx_bpfl
        mrv += reserve.vx_mrv

    grund = teile[0][1].kern
    mp = grund.mp
    a = monate // 12
    if a > mp.n or grund.produkt.ist_flex_phase(a):
        stoab = 0.0
    else:
        vs = sum(v.reduktion.vs_neu for _, v in teile)
        stoab = min(mp.stoab_max,
                    max(mp.stoab_min, mp.stoab_satz * (vs - dr)))
    return Monatsreserve(
        monate=monate, jahr=a, monatsanteil=(monate % 12) / 12.0,
        drx_bpfl=dr, vx_mrv=mrv, stoab=stoab,
        rkw=max(0.0, mrv - stoab),
    )


def als_zahlungspfad(red: "Reduktion", mp: ModelPoint) -> "Zahlungspfad":
    """Die Herabsetzung als VERLAUF statt als Skalierung.

    Der herabgesetzte Vertrag ist ein Vertrag mit einem geknickten
    Zahlungsverlauf: Ab dem Reduktionsjahr traegt er den Bruchteil ``f``
    des Beitrags und die Leistung ``f + q``, wobei ``q`` die umgewandelte
    beitragsfreie Summe relativ zur Ursprungssumme ist. Die Kosten folgen
    getrennt — der fortgefuehrte Teil traegt gamma2 anteilig, der
    umgewandelte gamma3 auf seiner eigenen Summe.

    **Warum das mehr ist als eine zweite Schreibweise.** Die
    Skalierung setzt Homogenitaet in der Versicherungssumme voraus: Sie
    rechnet den Ursprungsvertrag einmal und multipliziert. Das gilt fuer
    einen ungeteilten Vertrag exakt — und nur fuer den. Sobald
    Erhoehungsscheiben mit eigenem Eintrittsalter und eigener
    Beitragsdauer dazukommen, gibt es keinen gemeinsamen Faktor mehr.
    Der Verlauf braucht keine Homogenitaet; er beschreibt, was gezahlt
    wird, und die Rekursion rechnet es aus.

    Damit ist die Beschraenkung des Tarifplans auf den ungeteilten
    Vertrag keine Grenze der Rechnung mehr. Was bei geschichteten
    Vertraegen fehlt, ist die ZUSAGE, wie sich eine Herabsetzung des
    Gesamtbeitrags auf die Schichten verteilt — eine Tarifentscheidung
    (Tarifplan KLV, Abschnitt 12).

    Geprueft ist die Gleichwertigkeit am ungeteilten Vertrag: Pfad und
    Skalierung stimmen ueber alle Vertragsjahre bis auf
    Gleitkommarauschen ueberein (siehe Test).
    """
    from rechner_pipeline.kern.zahlungspfad import Zahlungspfad

    a0, f = red.jahr, red.anteil
    if red.vs_alt <= 0.0:
        raise BeitragsreduktionFehler(
            f"Ursprungssumme {red.vs_alt!r} — ohne sie ist kein relativer "
            "Verlauf bildbar")
    q = (red.vs_neu - f * red.vs_alt) / red.vs_alt
    nachher = f + q
    return Zahlungspfad(
        leistung=tuple(1.0 if j < a0 else nachher for j in range(mp.n)),
        ablauf=nachher,
        beitrag=tuple(1.0 if j < a0 else f for j in range(mp.t)),
        kosten_bpfl=tuple(1.0 if j < a0 else f for j in range(mp.n)),
        kosten_bfr=tuple(0.0 if j < a0 else q for j in range(mp.n)),
    )


@dataclass(frozen=True)
class ReduzierterVertrag:
    """Der herabgesetzte Vertrag NACH der Reduktion — die Folgebewertung.

    Die Reduktion selbst rechnet :func:`reduziere`; dieses Objekt traegt
    den Vertrag DANACH — als EINEN Vertrag mit geknicktem Verlauf, nicht
    als Summe zweier Vertraege. Ab dem Reduktionsjahr traegt er den
    Beitragsanteil ``anteil`` und daneben die bei der Reduktion FIXIERTE
    beitragsfreie Summe, die auf dem beitragsfreien Reservesatz
    weiterlaeuft — dieselbe Mechanik wie die Summe einer
    Beitragsfreistellung (Tarifplan klv.md, 7.1 und GeVo-Katalog PEX).

    Gerechnet wird ueber den Zahlungspfad (:func:`als_zahlungspfad`),
    nicht ueber zwei skalierte Vertraege. Die Skalierung waere nur beim
    ungeteilten Vertrag exakt, weil sie Homogenitaet in der
    Versicherungssumme voraussetzt; der Pfad braucht sie nicht.

    Stornoabschlag und Rueckkaufswert gelten je VERTRAG, einmal auf die
    Gesamtwerte gerechnet — dieselbe Regel wie bei Erhoehungsscheiben
    (:func:`rechner_pipeline.kern.rechenkern.vertrags_monatsreserve`);
    die Gesamt-VS ist die neue Gesamtsumme ``vs_neu``.
    """

    kern: Rechenkern
    reduktion: Reduktion

    @classmethod
    def nach(
        cls, kern: Rechenkern, jahr: int, anteil: float,
        *, verfahren: str = PROSPEKTIV,
    ) -> "ReduzierterVertrag":
        return cls(kern=kern, reduktion=reduziere(
            kern, jahr, anteil, verfahren=verfahren))

    @property
    def bfr_teil(self) -> float:
        """Die bei der Reduktion fixierte beitragsfreie Summe."""
        return self.reduktion.vs_neu - self.reduktion.anteil * self.reduktion.vs_alt

    def _pruefe_monat(self, monate: int) -> None:
        if monate < 12 * self.reduktion.jahr:
            raise BeitragsreduktionFehler(
                f"Monats-Stichtag {monate} liegt vor der Reduktion "
                f"(Jahr {self.reduktion.jahr}) — davor gilt der "
                "unreduzierte Vertrag"
            )

    def _bfr_satz(self, monate: int) -> float:
        """Beitragsfreier Reservesatz, linear zwischen den Jahrestagen."""
        a, rest = divmod(int(monate), 12)
        satz = self.kern.verlaufszeile(a).vx_bfr
        if rest:
            u = rest / 12.0
            satz = (1.0 - u) * satz + u * self.kern.verlaufszeile(a + 1).vx_bfr
        return satz

    def monatsreserve(self, monate: int) -> "Monatsreserve":
        """Vertragsweite Reserven des herabgesetzten Vertrags am Monats-Stichtag.

        Gerechnet ueber den ZAHLUNGSPFAD: eine Rekursion ueber den
        tatsaechlichen Verlauf, statt den Ursprungsvertrag zu rechnen und
        mit dem Anteil zu multiplizieren.

        Die Skalierung war exakt, aber nur unter einer Voraussetzung --
        Homogenitaet in der Versicherungssumme. Sie gilt fuer einen
        ungeteilten Vertrag und faellt, sobald Erhoehungsscheiben mit
        eigenem Eintrittsalter und eigener Beitragsdauer dazukommen. Der
        Verlauf braucht die Voraussetzung nicht: Er beschreibt, was
        gezahlt wird. Offen ist bei geschichteten Vertraegen nur die
        Zusage der Verteilung (Tarifplan KLV, Abschnitt 12).

        Die Umstellung ist wertneutral -- Pfad und Skalierung stimmen an
        jedem Monats-Stichtag ueberein (Test in tests/test_zahlungspfad).
        Getragen wird die Gleichheit von den KOSTENPROFILEN des Pfades:
        Ohne sie liefe der Verlauf mit den vollen Verwaltungskosten des
        beitragspflichtigen Vertrags und laege um Hunderte Euro daneben.
        """
        from rechner_pipeline.kern.produkte.klv import Monatsreserve
        from rechner_pipeline.kern.zahlungspfad import (
            monatsreserve as pfad_monatsreserve,
        )

        self._pruefe_monat(monate)
        mp = self.kern.mp
        werte = pfad_monatsreserve(
            mp, als_zahlungspfad(self.reduktion, mp), self.kern.basis,
            int(monate),
        )
        return Monatsreserve(
            monate=werte.monate, jahr=werte.jahr,
            monatsanteil=werte.monatsanteil,
            drx_bpfl=werte.drx_bpfl, vx_mrv=werte.vx_mrv,
            stoab=werte.stoab, rkw=werte.rkw,
        )

    def bjb(self, monate: int) -> float:
        """Bruttojahresbeitrag nach der Reduktion (0 nach Ende der Zahlung)."""
        self._pruefe_monat(monate)
        if monate >= 12 * self.kern.mp.t:
            return 0.0
        return self.reduktion.bjb_neu

    def beitragsfreie_summe(self, pex_jahr: int) -> float:
        """Beitragsfreie Gesamtsumme bei SPAETERER Beitragsfreistellung.

        Der fortgefuehrte Anteil wandelt zu seinem Satz (``anteil *
        VS_bfr(pex_jahr)``), der bereits umgewandelte Teil ist fixiert
        und bleibt unveraendert.
        """
        if pex_jahr < self.reduktion.jahr:
            raise BeitragsreduktionFehler(
                f"Beitragsfreistellung im Jahr {pex_jahr} vor der Reduktion "
                f"(Jahr {self.reduktion.jahr})"
            )
        return (self.reduktion.anteil * self.kern.beitragsfreie_summe(pex_jahr)
                + self.bfr_teil)

    def reserve_beitragsfrei(self, pex_jahr: int, monate: int) -> float:
        """Reserve nach einer SPAETEREN Beitragsfreistellung des
        herabgesetzten Vertrags: die dort fixierte Gesamtsumme laeuft auf dem
        beitragsfreien Reservesatz weiter (Spiegel von
        :meth:`Rechenkern.monatsreserve_beitragsfrei`)."""
        if monate < 12 * pex_jahr:
            raise BeitragsreduktionFehler(
                f"Monats-Stichtag {monate} vor der Beitragsfreistellung "
                f"(Jahr {pex_jahr})"
            )
        return self.beitragsfreie_summe(pex_jahr) * self._bfr_satz(monate)

    def terminale_leistung(self, pex_jahr: Optional[int] = None) -> float:
        """Leistung eines terminalen Falls (TOD, ABL) nach der Reduktion.

        Auf dem (teil-)beitragspflichtigen Track die neue Gesamtsumme
        ``vs_neu``; nach einer spaeteren Beitragsfreistellung die dort
        fixierte beitragsfreie Gesamtsumme — dieselbe Regel wie beim
        ungeteilten Vertrag (Tarifplan klv.md, GeVo-Katalog TOD/ABL).
        """
        if pex_jahr is not None:
            return self.beitragsfreie_summe(pex_jahr)
        return self.reduktion.vs_neu


def verfahrensdifferenz(kern: Rechenkern, jahr: int, anteil: float) -> Dict[str, float]:
    """Was die Verfahrenswahl an diesem Vertrag ausmacht.

    Das ist die Groesse, die im Migrationsfall zum Residuum wird: Rechnet
    das abgebende Unternehmen mit Abzug und das Zielsystem prospektiv,
    liefert die Quelle einen niedrigeren Stand — und die Differenz ist
    kein Fehler, sondern eine Verfahrensfrage, die die Korrekturschicht
    traegt.
    """
    ziel = reduziere(kern, jahr, anteil, verfahren=PROSPEKTIV)
    quelle = reduziere(kern, jahr, anteil, verfahren=MIT_ABZUG)
    return {
        "jahr": jahr,
        "anteil": anteil,
        "vs_prospektiv": ziel.vs_neu,
        "vs_mit_abzug": quelle.vs_neu,
        "d_vs": quelle.vs_neu - ziel.vs_neu,
        "dk_prospektiv": ziel.dk_nach,
        "dk_mit_abzug": quelle.dk_nach,
        "d_dk": quelle.dk_nach - ziel.dk_nach,
    }
