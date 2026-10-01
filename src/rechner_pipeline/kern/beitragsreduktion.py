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
auf den Anteil ``f``, und der freiwerdende Anteil des Rueckkaufswerts wird in
beitragsfreie Summe umgewandelt, die als eigenes Leistungsprofil neben
dem fortgefuehrten steht (:func:`als_zahlungspfad`). Weil der
Jahresbeitrag proportional zur Versicherungssumme ist (``BJB = VS *
Bxt``), ist ``f`` zugleich der Beitrags- und der Summenanteil des
fortgefuehrten Teils.

Die Rede vom "geteilten Vertrag" stammt aus der Zeit, in der die
Folgebewertung zwei skalierte Vertraege addierte. Sie hat die Mathematik
falsch dargestellt: Es gibt einen Vertrag und einen Verlauf.

**Wo sie sich unterscheiden: was mit dem freiwerdenden Anteil des
Rueckkaufswerts geschieht.**

``prospektiv`` (Zielverfahren)
    Der freiwerdende Anteil wird **verlustfrei** in beitragsfreie
    Versicherungssumme umgewandelt — mit demselben Satz UND auf
    demselben Track, den auch die vollstaendige Beitragsfreistellung
    verwendet: dem Rueckkaufswert-Track V^MRV, nicht der
    Deckungsrueckstellung V^bpfl (Entscheid des Maintainers
    2026-09-30, F1 (b)). Innerhalb der Zillmerdauer liegen beide Tracks
    um den noch nicht getilgten Abschlusskostenrest auseinander; auf
    V^bpfl umgewandelt lag die Herabsetzung mit f -> 0 darunter (Messung
    der Runde C, KLV a0 = 1: Beitragsfreistellung 4.898,47, Herabsetzung
    mit f = 0 2.356,97), und der Tarifplan widersprach sich selbst.

``mit_abzug`` (verbreitetes Altverfahren)
    Das System behandelt die Reduktion wie eine **Teilkuendigung**: Auf
    den freiwerdenden Anteil wird der anteilige Stornoabzug erhoben,
    bevor er in beitragsfreie Summe umgewandelt wird — umgewandelt wird
    also (1-f) x RKW, RKW = max(0, V^MRV - StoAb), genau die Groesse, die
    die Quelle bei der Teilkuendigung auszahlt. Auch das ist
    vertretbar — bei einem Teilrueckkauf ist der Abzug ueblich, und
    genau so haben viele Altbestaende die Herabsetzung gefuehrt.

Bei ``f = 1`` (keine Reduktion) aendert sich nichts. Bei ``f = 0`` ist
die prospektive Herabsetzung die Beitragsfreistellung (gleiche Summe,
gleicher Pfad, auch innerhalb der Zillmerdauer); die mit Abzug liegt um
den Stornoabzug darunter. Dazwischen weichen die Verfahren um den
anteiligen Stornoabzug (1-f) x StoAb ab; der Abzug ist hoechstens der
Rueckkaufswert selbst.

**Untergrenze.** Der umgewandelte Teil ist nie negativ (wie
RKW = max(0, ...)): Keine Summe und keine Leistung wird negativ, auch
nicht bei nicht positiver Rueckstellung im ersten Vertragsjahr (Befund
RC01 der Runde C). Auf dem Rueckkaufs-Track entsteht dort nach der
Nachmessung kein negativer Wert mehr; die Untergrenze bleibt als
Eigenschaft der Regel.

**Grenze des Floors (Entscheid des Maintainers 2026-09-30).** Der Floor auf
null gilt fuer den umgewandelten Teil der BASISSCHICHT, nicht fuer die
Korrekturschicht: Eine negative Schicht (rho < 0) kann den umgewandelten
Teil darunter druecken, und die Summe wird dann nicht geklemmt. Die Schicht
ist Migrationsdifferenz, keine Tarifgroesse — eine Untergrenze, die sie
einschlosse, machte aus einer Differenz zwischen zwei Systemen eine
Tarifaussage und verdeckte genau die Abweichung, die die Schicht ausweisen
soll. (Die Teilkuendigung kappt die Auszahlung dagegen auf null, weil dort
Geld fliesst und ein Kunde aus einer Migrationsdifferenz keine
Nachzahlungsforderung bekommt, Entscheid 2026-09-26 — siehe die Engine.)

**Zwei Geschaeftsvorfaelle** (Entscheid des Maintainers 2026-10-01,
ADR-023; klv.md 7.1 und 7.2). Die BEITRAGSHERABSETZUNG (``RED``) senkt den
Beitrag auf f und wandelt den freiwerdenden Teil in beitragsfreie Summe um
(``prospektiv`` oder ``mit_abzug``); es fliesst kein Geld, und sie setzt
einen laufenden Beitrag voraus (``0 < jahr < t``). Die TEILKUENDIGUNG
(``TKU``) kuendigt einen Summenanteil (1-f) und zahlt dessen
Rueckkaufswert nach Tarif aus; sie ist in jeder Generation beitragspflichtig,
ausfinanziert und nach einer Beitragsfreistellung moeglich
(``0 < jahr < n``). Hier rechnet ``verfahren=TEILKUENDIGUNG`` diesen Vorgang
fuer EINEN Vorgang je Vertrag; beliebig viele Vorgaenge in jeder Reihenfolge
rechnet :mod:`rechner_pipeline.kern.vorgangsfolge`, und fuer einen einzelnen
Vorgang bitgleich zu dieser Klasse. Verworfen wurde EIN Vorgang mit
Verfahrensschalter, der eine Herabsetzung nach t still als Teilkuendigung
rechnet: Es sind zwei Vorgaenge mit verschiedener Wirkung, und das Ledger
muss sagen, was geschah. Eine Herabsetzung nach t verweigert der Kern
deshalb benannt, mit dem Ausweg Teilkuendigung.

Knoten: klv
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:  # pragma: no cover
    from rechner_pipeline.kern.produkte.klv import Monatsreserve

from rechner_pipeline.kern.konventionen import untergrenze_basissumme
from rechner_pipeline.kern.korrekturschicht import (
    schicht_traegt,
    schichtwert_bei,
)
from rechner_pipeline.kern.rechenkern import (
    Rechenkern,
    vertrags_monatsreserve,
)

#: Die beiden Verfahren. Welches gilt, ist eine Eigenschaft des SYSTEMS,
#: nicht des Vertrags — deshalb steht es im Beleg der Migration und nicht
#: im Modellpunkt.
PROSPEKTIV = "prospektiv"
MIT_ABZUG = "mit_abzug"
#: Die Teilkuendigung — seit dem Entscheid 2026-10-01 ein EIGENER
#: Geschaeftsvorfall (``TKU``) jeder Generation; als ``red_verfahren`` einer
#: Generation heisst der Wert: Dieser Tarif kennt keine Beitragsherabsetzung
#: (Entscheid des Maintainers 2026-10-01: der uebernommene Tarif kennt nur die
#: Teilkuendigung; sie kommt aus ihrer eigenen Rate, nicht aus einem
#: Herabsetzungswunsch — die fruehere Annahme A1 ist ersetzt). Ob sie nur die
#: Grundversicherung oder alle Bausteine kuerzt, sagt das Merkmal
#: ``tku_umfang`` (Entscheid B1, klv.md 7.2). Herkunft: Quell-Verfahren der
#: Baldrian-Uebernahme (Bedingungswerk Ziffer 6, A-M3-Befund des zweiten
#: Laufs): Der Anteil (1-f) der
#: GRUNDVERSICHERUNG wird GEKUENDIGT und sein Rueckkaufswert
#: ausgezahlt — kein beitragsfrei gestellter Teil bleibt zurueck, der
#: Vertrag danach ist der zustandslose Vertrag mit f x S (die Quelle
#: rechnet blattweise weiter). Die PLV-Verfahren oben wandeln dagegen
#: den freiwerdenden Teil in eine beitragsfreie Summe um (Zweiteilung).
TEILKUENDIGUNG = "teilkuendigung"
VERFAHREN = (PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG)
#: Was der PRODUKTIVE Pfad (``reduziere_geschichtet``, der eine Eingang
#: der Fuehrung) tatsaechlich ausfuehrt. ``VERFAHREN`` sagt, welche Worte
#: bekannt sind; dieses Tupel sagt, welche die Fuehrung rechnen kann. Ein
#: Test haelt es gegen ``reduziere_geschichtet``: Was hier steht, laeuft;
#: was fehlt, wird verweigert. Die Teilkuendigung war die Luecke (Befund
#: T26-12) und ist seit dem Bauauftrag des Maintainers (2026-09-22) im
#: produktiven Pfad gebaut: Grund gekuendigt, Scheiben unveraendert, die
#: Auszahlung bucht die Engine.
PRODUKTIV_AUSFUEHRBAR = (PROSPEKTIV, MIT_ABZUG, TEILKUENDIGUNG)


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
    kern: Rechenkern, jahr: int, anteil: float, *, verfahren: str = PROSPEKTIV,
    zusatz_dk: float = 0.0,
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
    if zusatz_dk < 0.0 or not math.isfinite(zusatz_dk):
        raise BeitragsreduktionFehler(
            f"zusatz_dk {zusatz_dk!r}: beitragsfreies Deckungskapital ohne "
            "eigene Zusage ist nicht negativ und endlich")

    if verfahren == TEILKUENDIGUNG:
        if zusatz_dk:
            raise BeitragsreduktionFehler(
                "Teilkuendigung mit Korrekturschicht: Der Vertrag danach ist "
                "der ZUSTANDSLOSE Vertrag mit f x S — es gibt keinen "
                "beitragsfreien Teil, in den die Schicht eingehen koennte. "
                "Sie geht vollstaendig in die AUSZAHLUNG des gekuendigten "
                "Anteils (Entscheid 2026-09-15); reduziere_geschichtet ruft "
                "deshalb ohne zusatz_dk, die Engine bucht sie mit aus. Ein "
                "direkter Aufruf mit zusatz_dk ist ein Programmierfehler")
        # Teilkuendigung der Grundversicherung MIT AUSZAHLUNG: Die
        # Reserve des gekuendigten Anteils verlaesst den Vertrag
        # (dDK = -(1-f) x kVx), der Rest laeuft ZUSTANDSLOS mit f x S
        # weiter — wegen der Summen-Homogenitaet des Kerns ist
        # dk_nach = f x dk_vor exakt; gerechnet wird er trotzdem ueber
        # den neuen Modellpunkt, nicht ueber die Formel. Der Abzug nach
        # Ziffer 4 mindert die AUSZAHLUNG an den Kunden, nicht die
        # verbleibende Reserve. Basis ist der GEFUEHRTE Wert (kVx_MRV)
        # — die Groesse, die die Quelle bucht und der
        # Geschaeftsvorfalltest vergleicht.
        if anteil <= 0.0:
            raise BeitragsreduktionFehler(
                "Teilkuendigung mit fortgefuehrtem Anteil 0 ist eine "
                "VOLLkuendigung — als Storno-Vorfall fuehren, nicht als "
                "Herabsetzung"
            )
        vs_alt = kern.mp.sum_insured
        neu = Rechenkern(dataclasses.replace(
            kern.mp, sum_insured=anteil * vs_alt))
        return Reduktion(
            jahr=jahr,
            anteil=anteil,
            verfahren=verfahren,
            vs_alt=vs_alt,
            vs_neu=anteil * vs_alt,
            bjb_alt=kern.gross_annual_premium(),
            bjb_neu=neu.gross_annual_premium(),
            dk_vor=kern.verlaufszeile(jahr).vx_mrv,
            dk_nach=neu.verlaufszeile(jahr).vx_mrv,
        )

    zeile = kern.verlaufszeile(jahr)
    # Der ungeteilte Vertrag traegt seinen eigenen Stornoabschlag; beim
    # verlustfreien Verfahren wird keiner erhoben. Der Abzug bezieht sich
    # auf den Track, der umgewandelt wird: den Rueckkaufswert V^MRV.
    nach_abzug = (
        1.0 if verfahren == PROSPEKTIV
        else _abzugsfaktor(zeile.vx_mrv, zeile.stoab)
    )
    return _reduziere_eine_schicht(
        kern, jahr, anteil, nach_abzug, verfahren, zusatz_dk=zusatz_dk)


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
    if verfahren == TEILKUENDIGUNG:
        # Die Teilkuendigung (Bedingungswerk Ziffer 6) kuendigt einen
        # Anteil der GRUNDVERSICHERUNGSSUMME mit Auszahlung — sie setzt
        # keinen laufenden Beitrag voraus und ist darum auch im
        # beitragsfreien Nachlauf (t <= jahr < n) definiert. Ihre
        # Grenze ist der Ablauf, nicht das Beitragsende.
        if jahr >= mp.n:
            raise BeitragsreduktionFehler(
                f"Vertragsjahr {jahr}: der Vertrag laeuft bei n={mp.n} "
                "ab — am oder nach dem Ablauf gibt es nichts mehr zu "
                "kuendigen"
            )
    elif jahr >= mp.t:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: die Beitragszahlungsdauer ist beendet "
            f"(t={mp.t}) — es gibt keinen Beitrag zu reduzieren. Eine "
            "Beitragsherabsetzung setzt einen laufenden Beitrag voraus; "
            "Ausweg: die Teilkuendigung (eigener Geschaeftsvorfall TKU, "
            "verfahren='teilkuendigung'), die einen Summenanteil kuendigt "
            "und auszahlt"
        )


def _abzugsfaktor(mrv: float, stoab: float) -> float:
    """Der Anteil des Rueckkaufswerts, der den Stornoabschlag ueberlebt.

    Faktor f mit mrv * f = max(0, mrv - StoAb) = RKW: Umgewandelt wird bei
    der Herabsetzung mit Abzug der Rueckkaufs-Track (klv.md 7.1, wie bei
    der Beitragsfreistellung), und der Abzug ist hoechstens der Wert, von
    dem er abgezogen wird — wie beim Rueckkaufswert selbst
    (RKW = max(0, V^MRV - StoAb); Angriffsrunde nach T27: bei kleinen
    Summen trieb der Mindestabzug die umgewandelte Summe unter null, und
    negative Leistungen folgten). Bei nicht positivem Rueckkaufswert gibt
    es nichts abzuziehen: Dann rechnet das Verfahren wie das
    prospektive, und "mit Abzug" liegt nie ueber "prospektiv".
    """
    if mrv <= 0.0:
        return 1.0
    return 1.0 - min(stoab, mrv) / mrv


def _reduziere_eine_schicht(
    kern: Rechenkern,
    jahr: int,
    anteil: float,
    nach_abzug: float,
    verfahren: str = PROSPEKTIV,
    *,
    zusatz_dk: float = 0.0,
) -> "Reduktion":
    """Die Reduktion EINER Schicht — der gemeinsame Rechenteil.

    ``nach_abzug`` ist der Anteil des Rueckkaufswerts (V^MRV), der die
    Umwandlung ueberlebt: 1.0 beim verlustfreien Verfahren, sonst der
    vertragsweit gebildete Faktor (RKW / V^MRV). Beim ungeteilten Vertrag ist die Schicht der
    Vertrag, und beide Wege rechnen dieselbe Formel — deshalb steht sie
    hier einmal.
    """
    mp = kern.mp
    zeile = kern.verlaufszeile(jahr)
    dk_vor = zeile.drx_bpfl
    vs_alt = mp.sum_insured
    bjb_alt = kern.gross_annual_premium()

    # Der fortgefuehrte Teil bleibt unveraendert; nur der freiwerdende
    # Anteil wird umgewandelt — auf dem Rueckkaufswert-Track V^MRV, GENAU
    # wie die Beitragsfreistellung (S_bfr = V^MRV / V^bfr, klv.md 6):
    # Entscheid des Maintainers 2026-09-30, F1 (b). Auf V^bpfl umgewandelt
    # lag die Herabsetzung mit f -> 0 innerhalb der Zillmerdauer um den
    # Abschlusskostenrest unter der Beitragsfreistellung (KLV a0 = 1:
    # 2.356,97 gegen 4.898,47). Der Anteil (1-f) des Rests folgt dem
    # Beitrag und ist mit der Herabsetzung abgeschrieben (klv.md 7.1,
    # "Abschlusskosten folgen dem Beitrag"): ein Verlust des Unternehmens,
    # beim Verfahren mit Abzug teilweise durch den Stornoabzug gedeckt.
    #
    # Untergrenze null (RC01, Runde C): der umgewandelte Teil ist nie
    # negativ, wie RKW = max(0, ...). Ohne sie ging bei nicht positivem
    # Wert eine NEGATIVE Summe in den Vertrag, und die Leistungen mit ihr
    # (-239,41 auf dem Modellpunkt des Angreifers, x=20, n=t=40, f=0,001,
    # als die Umwandlung noch auf der Rueckstellung lag; auf dem Testpunkt
    # RC01 auf KLV_DEFAULT -305,02, alt — tests/test_herabsetzung_mrv_track.py).
    # Der Floor gilt fuer die Basisschicht; die Korrekturschicht kommt
    # darunter noch hinzu (siehe unten) und wird nicht mehr geklemmt.
    umgewandelt = untergrenze_basissumme(
        zeile.vx_mrv * nach_abzug * (1.0 - anteil))
    # ``zusatz_dk`` ist Deckungskapital OHNE eigene Zusage — die
    # Korrekturschicht eines uebernommenen Vertrags. Sie traegt keinen
    # Beitrag, gehoert also vollstaendig zum umgewandelten Teil, nicht
    # anteilig zum fortgefuehrten: Die Herabsetzung ist eine
    # Neuvereinbarung, das Gesamt-Deckungskapital EINSCHLIESSLICH Schicht
    # ist der Startwert der Neuberechnung, und danach fuehrt allein die
    # Logik des Zielsystems (Entscheid des Maintainers 2026-09-15; 9.7
    # Klasse A). Beim verlustfreien Verfahren ist dk_nach damit exakt
    # dk_vor + zusatz_dk — kein Sprung an der Naht.
    #
    # Als eigener Summand, nicht in den Ausdruck darueber gezogen: Ohne
    # Schicht bleibt die Rechnung bitgleich zu der, die die
    # Charakterisierungswerte des Kerns tragen.
    #
    # UNGEKUERZT, auch mit Abzug (Angriffsrunde nach T27): Der Stornoabzug
    # ist ein Betrag des Grundvertrags, (1-f) x StoAb, und steckt schon im
    # Summanden darueber (klv.md 7.1; Grundsatz 9.7: den Abzug traegt die
    # Basisschicht, nicht die Schicht). Mit einem Abzugsfaktor
    # multipliziert (damals auf der Rueckstellung gebildet, 1 - StoAb/DR),
    # zog die Schicht den Abzug ein zweites Mal an — nahe DR = 0
    # unbegrenzt, bei DR < 0 als Geschenk; auf V^MRV gebildet bleibt es
    # dasselbe Doppelzaehlen.
    if zusatz_dk:
        umgewandelt += zusatz_dk

    if zeile.vx_bfr <= 0.0:
        raise BeitragsreduktionFehler(
            f"Vertragsjahr {jahr}: beitragsfreier Reservesatz ist "
            f"{zeile.vx_bfr!r} — eine Umwandlung ist dort nicht definiert"
        )
    vs_bfr_teil = umgewandelt / zeile.vx_bfr
    vs_neu = vs_alt * anteil + vs_bfr_teil

    # Das Deckungskapital nach dem Vorfall (Basis der Rueckstellung, wie
    # dk_vor): der fortgefuehrte Teil traegt seine anteilige Reserve, der
    # umgewandelte seinen Wert — dieselbe Groesse, die der Zahlungspfad im
    # Reduktionsjahr als Rueckstellung ausweist (Test).
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


def _unveraendert(kern: Rechenkern, jahr: int) -> "Reduktion":
    """Die Identitaet als Reduktion: eine Erhoehungsscheibe, die eine
    Teilkuendigung NICHT trifft. Anteil 1, Summe und Beitrag unveraendert,
    dDK = 0. Als ``Reduktion`` getragen, damit der herabgesetzte Vertrag
    ueberall dieselbe Form hat (``reduzierte_teile`` -> ein
    ``ReduzierterVertrag`` je Schicht); der Zahlungspfad mit f = 1 und
    q = 0 ist die unveraenderte Scheibe."""
    zeile = kern.verlaufszeile(jahr)
    vs = kern.mp.sum_insured
    bjb = kern.gross_annual_premium()
    return Reduktion(
        jahr=jahr, anteil=1.0, verfahren=TEILKUENDIGUNG,
        vs_alt=vs, vs_neu=vs, bjb_alt=bjb, bjb_neu=bjb,
        dk_vor=zeile.vx_mrv, dk_nach=zeile.vx_mrv,
    )


def reduziere_geschichtet(
    grund: Rechenkern,
    scheiben: Sequence[Tuple[int, Rechenkern]],
    jahr: int,
    anteil: float,
    *,
    verfahren: str = PROSPEKTIV,
    zusatz_dk: float = 0.0,
    stoab_je_baustein: bool = False,
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
    Rueckkaufswert der Schicht verteilt — dem Anteil, aus dem der
    umgewandelte Betrag stammt. Beim verlustfreien Verfahren entfaellt
    die Frage, dort wird kein Abzug erhoben.

    **Je Baustein, wo das Tarifwerk es sagt** (Runde D): Bei
    ``stoab_je_baustein=True`` (Bedingungswerk Ziffer 4) gilt der Abzug je
    BAUSTEIN mit eigenen Grenzen, und der Rueckkaufswert des Vertrags ist
    die Summe der auf null begrenzten Baustein-Rueckkaufswerte. Umgewandelt
    wird dann (1-f) x dieser RKW — dieselbe Groesse, die ein Storno am
    selben Tag zahlt (``vertrags_rkw``) und die die Teilkuendigung schon
    hielt. Der Faktor bleibt einer fuer alle Schichten (RKW / V^MRV der
    Summe); die vertragsweite Bildung ignorierte den Schalter und wich im
    Messfall (KLV_DEFAULT, Abzug 0,005 / 50 / 200, Scheiben in Jahr 2 und 3,
    a0 = 6, f = 0,3) um 92,87 EUR Summe ab (54.578,30 statt 54.485,43).
    Das Tarifwerk wird nie geraten: Der Aufrufer reicht den Schalter der
    Generation durch.

    **Die Korrekturschicht gehoert zur Grundscheibe.** ``zusatz_dk`` geht
    dort in die Umwandlung ein und nirgends sonst: Die Schicht ist auf den
    Modellpunkt des Grundvertrags kalibriert (``schichtwert_bei``), nicht
    auf die Erhoehungen — eine Aufteilung ueber die Schichten waere eine
    zweite Konvention ohne fachlichen Grund.

    Rueckgabe: je Schicht ihr Erhoehungsjahr und ihre Reduktion, in der
    Reihenfolge (Grundscheibe zuerst) von ``vertrags_monatsreserve``.
    """
    if verfahren == TEILKUENDIGUNG:
        # Teilkuendigung (Bedingungswerk Ziffer 6) trifft NUR die
        # Grundversicherung: Ihr Anteil (1-f) wird gekuendigt und
        # ausgezahlt, der Rest laeuft zustandslos mit f x S; die
        # Erhoehungsscheiben laufen UNVERAENDERT weiter (A-M3-Befund des
        # zweiten Laufs: derselbe dDK mit und ohne Scheiben). Gebaut als
        # Bauauftrag T26-12 (Entscheid des Maintainers 2026-09-22).
        #
        # ``zusatz_dk`` — die Korrekturschicht — geht NICHT in die Teile:
        # Es gibt keinen beitragsfreien Teil, in den sie eingehen koennte.
        # Sie geht vollstaendig in die AUSZAHLUNG (Entscheid 2026-09-15:
        # "Schicht geht vollstaendig in die Neuberechnung ein" — deren
        # einziges Vehikel ist hier die Zahlung an den Kunden); die Engine
        # bucht sie dort (``ereignisse._Vertrag.herabsetzen``). Der Vertrag
        # danach traegt keine Schicht mehr.
        #
        # Die Folgebewertung braucht keinen Sonderweg: Der Zahlungspfad mit
        # q = 0 IST der zustandslose Vertrag mit f x S — nachgemessen gegen
        # den unabhaengigen Kern mit gesenkter Summe auf 1e-15
        # (tests/test_teilkuendigung_produktiv_t2612.py).
        _pruefe_eingaben(grund.mp, jahr, anteil, verfahren)
        for erh_jahr, _kern in scheiben:
            if jahr - erh_jahr < 0:
                raise BeitragsreduktionFehler(
                    f"Erhoehungsscheibe aus Jahr {erh_jahr} existiert im "
                    f"Vertragsjahr {jahr} noch nicht"
                )
        aus_tk: List[Tuple[int, "Reduktion"]] = [
            (0, reduziere(grund, jahr, anteil, verfahren=verfahren))]
        for erh_jahr, kern in scheiben:
            aus_tk.append((erh_jahr, _unveraendert(kern, jahr - erh_jahr)))
        return aus_tk
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
    gesamt = vertrags_monatsreserve(
        grund, list(scheiben), 12 * jahr, stoab_je_baustein=stoab_je_baustein)
    # Der Anteil des Rueckkaufswerts, der die Umwandlung ueberlebt, JE SCHICHT.
    if verfahren == PROSPEKTIV:
        nach_abzug = [1.0] * len(teile)
    elif stoab_je_baustein:
        # Abzug je Baustein (Bedingungswerk Ziffer 4): Jeder Baustein traegt
        # seinen eigenen Abzug und wandelt genau SEINEN Rueckkaufswert um,
        # ``max(0, V^MRV_i - StoAb_i)`` — dieselbe Groesse, die sein Storno am
        # selben Tag zahlt, und dieselbe Bildung wie beim ungeteilten Vertrag
        # (``reduziere``: ``_abzugsfaktor``). Die Summe ist (1-f) x
        # ``gesamt.rkw`` (die Summe der auf null begrenzten Baustein-Werte),
        # und ein Baustein mit negativem Rueckkaufs-Track wandelt nichts um
        # (Floor je Schicht). Runde F, Nachbesserung 2: Vorher bekam jede
        # Schicht denselben Faktor ``gesamt.rkw / sum max(0, V^MRV_i)`` — die
        # Summe stimmte, die Werte je Schicht nicht: Der Baustein mit dem
        # kleineren Abzug wandelte mehr um als seinen eigenen Rueckkaufswert,
        # der mit dem groesseren weniger (Messfall: Abzug 0,005 / 50 / 200,
        # Zillmerdauer 5, f = 0,5, Herabsetzung Jahr 2, V^MRV Grund 2.605,86 /
        # Scheibe 275,25, Abzug 200,00 / 101,41: umgewandelt Grund 1.166,62
        # statt 1.202,93, Scheibe 123,23 statt 86,92 — Summe 1.289,85 gleich).
        # Der Auftrag sagt "verteilt nach dem geklemmten
        # Baustein-RKW"; der gemeinsame Faktor tat es nur ohne verschiedene
        # Abzuege (Tarifplan klv.md 7.1 steht nicht dagegen).
        nach_abzug = [
            _abzugsfaktor(k.verlaufszeile(jahr - e).vx_mrv,
                          k.verlaufszeile(jahr - e).stoab)
            for e, k in teile]
    else:
        # Abzug je Vertrag (Tarifplan 6): einmal auf den Gesamtwerten
        # gebildet, ``gesamt.rkw`` = max(0, sum V^MRV - StoAb). Umgewandelt wird
        # (1-f) x dieser RKW — genau so viel, auch wenn ein Baustein einen
        # negativen Rueckkaufs-Track hat (Runde F, F1) —, verteilt nach dem auf
        # null begrenzten Rueckkaufs-Track der Schicht (die Baustein-Groesse,
        # auf der der vertragsweite Abzug aufsitzt; ein Baustein-RKW mit eigenem
        # Abzug gibt es hier nicht). Der Faktor ist RKW geteilt durch die Summe
        # der auf null begrenzten V^MRV, denn nur diese Summe geht in die
        # Umwandlung ein (``_reduziere_eine_schicht``: je Schicht max(0, ...)).
        # Geteilt durch die UNBEGRENZTE Summe (``gesamt.vx_mrv``) wurde der
        # Faktor groesser als eins, sobald eine junge Scheibe in der
        # Zillmerdauer negativ war: Messfall KLV x=18, n=t=40, alpha 0,04,
        # zillmer_dauer 1, Scheibe 20.000 aus Jahr 1, Herabsetzung Jahr 2,
        # f = 0,5: Ist 334,40, Soll 114,88 (V^MRV Grund 429,77, Scheibe
        # -282,12); ohne Abzug 625,47 statt 214,88 — "mit Abzug" lag UEBER
        # "prospektiv". Mit Abzug 0 und f -> 0 lag es bei 1.250,94 statt beim
        # Storno-RKW 429,77.
        positiv = sum(
            max(0.0, kern.verlaufszeile(jahr - erh_jahr).vx_mrv)
            for erh_jahr, kern in teile)
        faktor = min(1.0, gesamt.rkw / positiv) if positiv > 0.0 else 1.0
        nach_abzug = [faktor] * len(teile)

    aus: List[Tuple[int, "Reduktion"]] = []
    for i, (erh_jahr, kern) in enumerate(teile):
        # Die Schicht rechnet ihre eigene Reduktion — mit ihrem eigenen
        # Eintrittsalter, ihrer eigenen Restdauer und ihrem eigenen
        # beitragsfreien Reservesatz. Nur der Abzug kommt von aussen, und
        # die Korrekturschicht nur bei der Grundscheibe (teile[0]): Sie
        # ist auf DEREN Modellpunkt kalibriert.
        aus.append((erh_jahr, _reduziere_eine_schicht(
            kern, jahr - erh_jahr, anteil, nach_abzug[i], verfahren,
            zusatz_dk=zusatz_dk if i == 0 else 0.0)))
    return aus


def reduzierte_teile(
    grund: Rechenkern,
    scheiben: Sequence[Tuple[int, Rechenkern]],
    jahr: int,
    anteil: float,
    verfahren: str,
    *,
    schicht: Optional[Tuple[Any, int]] = None,
    stoab_je_baustein: bool = False,
) -> List[Tuple[int, Any]]:
    """Der herabgesetzte Vertrag, je Schicht — DIE eine Rekonstruktion.

    Vier Stellen brauchen sie: die Ereignis-Engine beim Ziehen, die
    Bewertung am Stichtag, die Ledger-Herleitung (P-B1) und die
    Fuehrungsprobe. Genau solche Wiederholungen waren der Befund T25-06:
    Vier Abschriften derselben Regel, und die beiden "unabhaengigen"
    Gegenrechnungen bestaetigten den Fehler der Bewertung, statt ihn zu
    widerlegen. Hier steht sie einmal.

    ``schicht`` ist die Korrekturschicht (Parameter, Verankerungsmonat)
    eines uebernommenen Vertrags. Liegt der Verankerungspunkt vor der
    Herabsetzung, geht ihr Wert VOLLSTAENDIG in die Neuberechnung ein
    (Entscheid des Maintainers 2026-09-15) — danach traegt der Vertrag
    keine Schicht mehr.
    """
    zusatz = 0.0
    if schicht_traegt(schicht, 12 * jahr):
        zusatz = schichtwert_bei(schicht[0], int(schicht[1]), grund.mp, 12 * jahr)
    aktive = [(j, k) for j, k in scheiben if j < jahr]
    teile = reduziere_geschichtet(
        grund, aktive, jahr, anteil, verfahren=verfahren, zusatz_dk=zusatz,
        stoab_je_baustein=stoab_je_baustein)
    kerne = [grund] + [k for _, k in aktive]
    aus = [
        (erh_jahr, ReduzierterVertrag(kern=kerne[i], reduktion=red))
        for i, (erh_jahr, red) in enumerate(teile)
    ]
    # Erhoehungen AB dem Reduktionsjahr: Die Dynamik laeuft nach einer
    # Herabsetzung weiter, bezogen auf die Summe danach (Entscheid des
    # Projekts 2026-09-26). Jede spaetere Scheibe ist ein gewoehnlicher,
    # nicht herabgesetzter Baustein. Vorher liess dieser Pfad sie still
    # weg — die Bewertung fuehrte eine gebuchte Erhoehung nicht.
    aus += [(j, nachher_zugekommen(k)) for j, k in scheiben if j >= jahr]
    return aus


def nachher_zugekommen(kern: Rechenkern) -> "ReduzierterVertrag":
    """Eine Erhoehungsscheibe, die NACH der Herabsetzung entstand: ein
    gewoehnlicher Baustein in der Form des herabgesetzten Vertrags
    (Anteil 1, ab seinem eigenen Vertragsjahr 0)."""
    return ReduzierterVertrag(kern=kern, reduktion=_unveraendert(kern, 0))


def bestehende_teile(teile, monate: int):
    """Die Bausteine, die am Monats-Stichtag schon bestehen — spaetere
    Erhoehungen gehoeren erst ab ihrem Jahrestag zum Vertrag."""
    return [(e, v) for e, v in teile if 12 * int(e) <= int(monate)]


def absorbierte_schicht(
    grund: Rechenkern, jahr: int, schicht: Optional[Tuple[Any, int]]
) -> float:
    """Der Schichtwert, den eine Herabsetzung im Jahr ``jahr`` aufnimmt.

    Null, wenn der Vertrag keine Schicht traegt oder die Verankerung nach
    der Herabsetzung liegt. Derselbe Wert, den :func:`reduzierte_teile`
    einrechnet — die Buchung im Ledger weist ihn aus.
    """
    if not schicht_traegt(schicht, 12 * jahr):
        return 0.0
    return schichtwert_bei(schicht[0], int(schicht[1]), grund.mp, 12 * jahr)


def vertrags_monatsreserve_reduziert(
    teile: Sequence[Tuple[int, "ReduzierterVertrag"]], monate: int,
    *, stoab_je_baustein: bool,
) -> "Monatsreserve":
    """Vertragsweite Monatsreserve eines herabgesetzten GESCHICHTETEN Vertrags.

    Spiegel von
    :func:`rechner_pipeline.kern.rechenkern.vertrags_monatsreserve`, nur
    dass jede Schicht ihren herabgesetzten Verlauf rechnet: Reserven sind
    die Summe der Schichtwerte, jede an ihrem versetzten Stichtag.

    WO der Stornoabschlag greift, sagt das Tarifwerk der Generation — und
    zwar auch NACH der Herabsetzung (Pruefrunde T27, Befund 12: der
    reduzierte Verlauf kannte den Schalter nicht, ein Folge-Rueckkauf nach
    Teilkuendigung verlor den Abzug je Baustein, und die P-B1-Kontrolle
    rechnete ueber denselben Weg). Deshalb hat ``stoab_je_baustein`` hier
    KEINEN Default: Wer den reduzierten Verlauf bewertet, schreibt das
    Tarifwerk hin, sonst laeuft er nicht.

    * ``False`` (Tarifplan KLV, Abschnitt 6/7.1): der Abschlag gilt je
      VERTRAG, einmal auf den Gesamtwerten gebildet. Bezugsgroesse ist die
      NEUE Gesamtsumme — die Summe der ``vs_neu`` aller Schichten, also
      fortgefuehrter plus umgewandelter Teil. Die alte waere die Summe
      eines Vertrags, den es nicht mehr gibt.
    * ``True`` (Bedingungswerk einer uebernommenen Generation, Ziffer 4):
      jeder Baustein traegt seinen eigenen Abzug mit eigenen Grenzen,
      bezogen auf SEINE herabgesetzte Summe ``vs_neu`` und seine eigene
      Reserve, mit eigener Ablauf-/Flexphasenpruefung am versetzten
      Stichtag; der Rueckkaufswert ist die Summe der auf null begrenzten
      Baustein-Rueckkaufswerte — derselbe Weg wie
      ``vertrags_monatsreserve(stoab_je_baustein=True)``, nur mit der
      Summe nach der Herabsetzung.
    """
    from rechner_pipeline.kern.produkte.klv import Monatsreserve

    if not teile:
        raise BeitragsreduktionFehler(
            "keine Schichten — ein Vertrag ohne Grundscheibe ist keiner")
    teile = bestehende_teile(teile, monate)
    dr = mrv = 0.0
    stuecke: List[Tuple[Any, int, Any]] = []
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
        stuecke.append((vertrag, versetzt, reserve))

    grund = teile[0][1].kern
    mp = grund.mp
    a = monate // 12
    if stoab_je_baustein:
        stoab = rkw = 0.0
        for vertrag, versetzt, reserve in stuecke:
            mp_k = vertrag.kern.mp
            a_k = versetzt // 12
            if a_k > mp_k.n or vertrag.kern.produkt.ist_flex_phase(a_k):
                teil_stoab = 0.0
            else:
                teil_stoab = min(
                    mp_k.stoab_max,
                    max(mp_k.stoab_min,
                        mp_k.stoab_satz
                        * (vertrag.reduktion.vs_neu - reserve.drx_bpfl)))
            stoab += teil_stoab
            rkw += max(0.0, reserve.vx_mrv - teil_stoab)
    else:
        if a > mp.n or grund.produkt.ist_flex_phase(a):
            stoab = 0.0
        else:
            vs = sum(v.reduktion.vs_neu for _, v in teile)
            stoab = min(mp.stoab_max,
                        max(mp.stoab_min, mp.stoab_satz * (vs - dr)))
        rkw = max(0.0, mrv - stoab)
    return Monatsreserve(
        monate=monate, jahr=a, monatsanteil=(monate % 12) / 12.0,
        drx_bpfl=dr, vx_mrv=mrv, stoab=stoab, rkw=rkw,
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
        # Die Abschlusskosten folgen dem Beitrag (klv.md 7.1): Der
        # fortgefuehrte Vertrag traegt f des noch nicht getilgten Rests,
        # (1-f) ist mit der Herabsetzung abgeschrieben — ein Verlust des
        # Unternehmens, beim Verfahren mit Abzug teilweise durch den
        # Stornoabzug gedeckt. Vorher trug der Pfad den vollen Rest,
        # waehrend die beitragsfreie Summe f rechnete: Eine
        # Beitragsfreistellung nach der Herabsetzung sprang in der
        # Zillmerdauer um bis zu einem Tausender je 100.000 EUR.
        abschlusskosten=tuple(1.0 if j < a0 else f for j in range(mp.n)),
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
        *, verfahren: str = PROSPEKTIV, zusatz_dk: float = 0.0,
    ) -> "ReduzierterVertrag":
        if verfahren == TEILKUENDIGUNG:
            raise BeitragsreduktionFehler(
                "Folgebewertung einer Teilkuendigung ist der ZUSTANDSLOSE "
                "Vertrag mit f x S (Rechenkern mit gesenkter Summe) — es "
                "gibt keinen geteilten Vertrag und keinen beitragsfreien "
                "Teil zu fuehren"
            )
        return cls(kern=kern, reduktion=reduziere(
            kern, jahr, anteil, verfahren=verfahren, zusatz_dk=zusatz_dk))

    @property
    def bfr_teil(self) -> float:
        """Die bei der Reduktion fixierte beitragsfreie Summe."""
        return self.reduktion.vs_neu - self.reduktion.anteil * self.reduktion.vs_alt

    @property
    def ist_teilkuendigung(self) -> bool:
        return self.reduktion.verfahren == TEILKUENDIGUNG

    @property
    def folgekern(self) -> Rechenkern:
        """Der Vertrag nach der TEILKUENDIGUNG: der ZUSTANDSLOSE Kern mit der
        fortgefuehrten Summe — ein gewoehnlicher Vertrag mit kleinerer Summe
        (Bedingungswerk Ziffer 6; klv.md 7.1).

        Der Zahlungspfad mit q = 0 ist ihm NICHT gleich: Er rechnet den
        Zillmer-Rueckstand alpha * t * BJB des UNGEKUERZTEN Vertrags weiter
        (zahlungspfad, Skalare des Ursprungsvertrags), waehrend der Kern
        mit f x S nur f mal diesen Rueckstand traegt. In den Jahren der
        Zillmerdauer lag der Rueckkaufswert damit um (1-f) x alpha x t x
        BJB x azd/azd_full zu hoch, und ein Storno zahlte zu viel — der
        gekuendigte Anteil und der verbliebene Vertrag fuehrten den
        Rueckstand beide (Angriffsrunde 2 der Pruefrunde T27, Fund N10;
        der Test von T26-12 verglich erst ab Jahr 10, nach der
        Zillmerdauer, und war blind). Fuer eine unveraenderte Scheibe
        (anteil 1) ist der Folgekern der Kern selbst.
        """
        if self.reduktion.vs_neu == self.kern.mp.sum_insured:
            return self.kern
        return Rechenkern(dataclasses.replace(
            self.kern.mp, sum_insured=self.reduktion.vs_neu))

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
        if self.ist_teilkuendigung:
            return self.folgekern.monatsreserve(int(monate))
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
        if self.ist_teilkuendigung:
            return self.folgekern.beitragsfreie_summe(pex_jahr)
        # Ueber DENSELBEN Pfad wie die Reserve — ein Vertrag, ein Weg
        # (vorher: der skalierte Ursprungsvertrag, der den
        # Abschlusskostenrest anders las als der Pfad). S_bfr = V_MRV /
        # V_bfr wie im Tarifplan (klv.md 6); ab Beitragsende die Summe.
        from rechner_pipeline.kern.zahlungspfad import (
            verlaufszeile as pfad_verlaufszeile,
            vertragskonstanten,
        )

        mp = self.kern.mp
        if pex_jahr >= mp.t:
            return self.reduktion.vs_neu
        zeile = pfad_verlaufszeile(
            mp, als_zahlungspfad(self.reduktion, mp), self.kern.basis,
            int(pex_jahr), skalare=vertragskonstanten(mp, self.kern.basis))
        return untergrenze_basissumme(
            zeile.vx_mrv / self.kern.verlaufszeile(int(pex_jahr)).vx_bfr)

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
        if self.ist_teilkuendigung:
            return self.folgekern.monatsreserve_beitragsfrei(pex_jahr, int(monate))
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
