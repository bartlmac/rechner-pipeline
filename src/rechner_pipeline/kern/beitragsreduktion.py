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

**Die gemeinsame Konstruktion.** Beide Verfahren teilen den Vertrag: Ein
Anteil ``f`` bleibt beitragspflichtig, der Rest wird beitragsfrei
gestellt. Weil der Jahresbeitrag proportional zur Versicherungssumme ist
(``BJB = VS * Bxt``), ist ``f`` zugleich der Beitrags- und der
Summenanteil des fortgefuehrten Teils.

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
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:  # pragma: no cover
    from rechner_pipeline.kern.produkte.klv import Monatsreserve

from rechner_pipeline.kern.rechenkern import Rechenkern

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
    ein Vertragsjahr, keine Monate — eine unterjaehrige Reduktion ist
    damit nicht ausdrueckbar, und das ist Absicht: Sie wuerde einen
    unterjaehrigen Verankerungszeitpunkt erzeugen, und wie die
    Korrekturschicht ein Rumpfjahr behandelt, ist noch nicht entschieden
    (offener Punkt, betrifft nicht nur diesen Geschaeftsvorfall).

    Wer das erweitern will, muss zuerst die Rumpfjahr-Konvention klaeren —
    nicht hier einen Monatsparameter ergaenzen.
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
    mp = kern.mp
    if jahr < 0 or jahr > mp.n:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr} ausserhalb der Laufzeit (n={mp.n})"
        )
    if jahr >= mp.t:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: die Beitragszahlungsdauer ist beendet "
            f"(t={mp.t}) — es gibt keinen Beitrag zu reduzieren"
        )

    zeile = kern.verlaufszeile(jahr)
    dk_vor = zeile.drx_bpfl
    vs_alt = mp.sum_insured
    bjb_alt = kern.gross_annual_premium()

    # Der fortgefuehrte Teil bleibt unveraendert; nur der freiwerdende
    # Anteil wird umgewandelt.
    frei = 1.0 - anteil
    if verfahren == PROSPEKTIV:
        # Verlustfrei: derselbe Satz wie bei vollstaendiger Freistellung.
        umgewandelt = dk_vor * frei
    else:
        # Wie ein Teilrueckkauf: anteiliger Stornoabzug auf den
        # freiwerdenden Teil, bevor umgewandelt wird.
        umgewandelt = (dk_vor - zeile.stoab) * frei

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


@dataclass(frozen=True)
class ReduzierterVertrag:
    """Der geteilte Vertrag NACH einer Beitragsreduktion — die Folgebewertung.

    Die Reduktion selbst rechnet :func:`reduziere`; dieses Objekt traegt
    den Vertrag DANACH. Zweiteilung des Tarifwerks: der fortgefuehrte
    Anteil ``anteil`` bleibt ein beitragspflichtiger Vertrag ueber
    ``anteil * VS`` — saemtliche Zielgroessen des Kerns sind homogen in
    der Versicherungssumme (der Beitrag ist ``VS * Bxt``) und skalieren
    deshalb exakt mit. Der umgewandelte Teil ist eine bei der Reduktion
    FIXIERTE beitragsfreie Summe, die auf dem beitragsfreien Reservesatz
    weiterlaeuft — dieselbe Mechanik wie die Summe einer
    Beitragsfreistellung (Tarifplan klv.md, GeVo-Katalog PEX).

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
        """Vertragsweite Reserven des geteilten Vertrags am Monats-Stichtag."""
        from rechner_pipeline.kern.produkte.klv import Monatsreserve

        self._pruefe_monat(monate)
        mr = self.kern.monatsreserve(monate)
        umgewandelt = self.bfr_teil * self._bfr_satz(monate)
        anteil = self.reduktion.anteil
        dr = anteil * mr.drx_bpfl + umgewandelt
        mrv = anteil * mr.vx_mrv + umgewandelt
        mp = self.kern.mp
        a = int(monate) // 12
        if a > mp.n or self.kern.produkt.ist_flex_phase(a):
            stoab = 0.0
        else:
            stoab = min(mp.stoab_max,
                        max(mp.stoab_min,
                            mp.stoab_satz * (self.reduktion.vs_neu - dr)))
        return Monatsreserve(
            monate=int(monate), jahr=a, monatsanteil=(int(monate) % 12) / 12.0,
            drx_bpfl=dr, vx_mrv=mrv, stoab=stoab,
            rkw=max(0.0, mrv - stoab),
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
        """Reserve nach einer SPAETEREN Beitragsfreistellung des geteilten
        Vertrags: die dort fixierte Gesamtsumme laeuft auf dem
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
