"""Aktuarieller Test: Wertvergleich je Vertrag an seinen eigenen Pruefpunkten.

Umsetzung von ADR-010 (Trennung aktuarieller Test / Migrationscontrolling;
normative Referenz: Grundsatzdokumentation Abschnitt 9.12 und 9.15). Der
Test besteht aus drei Abnahmen, die dem Controlling alle drei vorausgehen
(ADR-012):

``A-M1`` **Stichtagstest**
    Zwei Punkte je Vertrag: der Uebernahmestand am Verankerungszeitpunkt
    $t_a$ und der naechste Vertragsstichtag laut Fortschreibung. Der
    zweite Punkt ist der eigentliche Zugewinn — er prueft nicht den
    Uebernahmeakt, sondern die Fortschreibungsregel.

``A-M2`` **Verlaufstest**
    Nach fuenf Jahren, nach zehn Jahren, zum Ablauf. Ein Fehler in der
    Ausscheideordnung oder im Kostenverlauf zeigt sich nicht nach einem
    Jahr, sondern erst zum Ablauf — dort, wo der Wert eine Zahlung an den
    Kunden ist.

``A-M3`` **Geschaeftsvorfalltest**
    Ein Punkt je Geschaeftsvorfall, der Zeitpunkt vom Vorfall bestimmt.
    Ein migrierter Bestand, der am Stichtag stimmt und beim ersten
    Rueckkauf falsch zahlt, ist nicht abgenommen.

Drei Invarianten gelten im Code, nicht nur in der Doku:

* **Der Vergleichszeitpunkt ist ein Vertragsattribut**, kein
  Suite-Parameter. Jeder Vertrag wird an SEINEN Punkten gemessen.
* **Kein interpolierter Vergleich ohne Anlass.** Stichtags- und
  Verlaufspunkte liegen auf dem Vertragsjahrestag; ein Wert dazwischen
  waere ein Interpolat und ist ein harter Fehler. Unterjaehrig ist nur
  ein Geschaeftsvorfall, und dort mit voller Absicht:

  Der Kern bildet unterjaehrige Reserven **linear zwischen den
  Vertragsjahrestagen** (Abschnitt 6; ``klv.monatsreserve``). Beim
  Geschaeftsvorfall ist dieser Wert aber kein Hilfskonstrukt, sondern der
  Betrag, den das Unternehmen zum Stornotermin auszahlt oder bei der
  Freistellung gutschreibt. Ihn nicht zu pruefen hiesse, die tatsaechliche
  Zahlung nicht zu pruefen. Rechnet das Quellsystem unterjaehrig anders,
  ist die Differenz eine echte Konventionsdifferenz mit Zahlungswirkung —
  genau das, was der Geschaeftsvorfalltest finden soll.

  Der Unterschied zum Verbot aus ADR-010: Dort geht es um den
  Migrationsstichtag, an dem ALLE Vertraege gleichzeitig verglichen
  wuerden — dort misst ein unterjaehriger Vergleich die
  Interpolationskonvention statt der Methode und entwertet das Residuum
  als Diagnoseinstrument. Beim einzelnen Geschaeftsvorfall ist die
  Konvention der Gegenstand, nicht die Stoerung.
* **Keine Summation der Vergleichsgroessen.** Die Engine bildet keine
  Deckungskapital-Summe. Sie kennt ausschliesslich Verteilungsgroessen
  des Residuums, geclustert nach Historientyp UND Anlass — ein Residuum
  bei der Uebernahme und eines beim Ablauf sind verschiedene Befunde und
  gehoeren nicht in denselben Topf.

Das Residuum ``system - erwartet`` ist der Wertvergleich, den wir heute
haben: Solange es keine Korrekturschicht gibt (Grundsatzdokumentation
Abschnitt 9), traegt der Test diesen Vergleich — am richtigen Zeitpunkt
und ohne Summen. Der Platz fuer das methodische Residuum R bleibt
benannt und leer.

Vollstaendigkeit heisst hier: die **Stichprobe** (``qa.stichprobe``) wurde
vollstaendig abgearbeitet. Die Nichtpruefung der Nicht-Stichprobe ist kein
Befund, sondern die Definition. Mitgelieferte Pruefsummen sind
Transportsicherung: Sie werden getrennt ausgewiesen und fliessen nie in
das fachliche Urteil ein.

Toleranzen kommen aus dem Testprofil (``qa.testprofil``), nicht mehr aus
einer Konstante: Drei Tests mit verschiedenen Fragen brauchen verschiedene
Grenzen, und die Grenze gehoert in den Beleg.

Knoten: klv
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Tuple

from rechner_pipeline.kern import ModelPoint
from rechner_pipeline.kern.beitragsreduktion import (
    PROSPEKTIV,
    ReduzierterVertrag,
    reduziere,
)
from rechner_pipeline.kern.rechenkern import (
    Rechenkern,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)
from rechner_pipeline.kern.korrekturschicht import (
    Korrekturschicht,
    Schichtparameter,
    form_konstantes_fenster,
    form_proportional_zur_basis,
)
from rechner_pipeline.qa.migrationssuite import DATEN_AUSNAHMEN
from rechner_pipeline.qa.stichprobe import Stichprobe
from rechner_pipeline.qa.testprofil import Kriterium, Testprofil

#: Groessen, die die Engine rechnen kann. Ein unbekannter Erwartungs-Key
#: ist ein harter Fehler — stiller Verzicht waere ein falscher Nachweis.
#:
#: ``dDK`` ist die Veraenderung des Deckungskapitals durch einen
#: Geschaeftsvorfall. Sie ist der tragende Pruefwert des
#: Geschaeftsvorfalltests: Eine laufende Rente ist keine Groesse zu EINEM
#: Zeitpunkt und taugt nicht als Vergleichswert, die Veraenderung des
#: Deckungskapitals dagegen ist fuer jeden Vorfall definiert.
GEPRUEFTE_GROESSEN = ("kVx_MRV", "RKW", "BJB", "VS_bfr", "dDK")

#: Hohe Perzentile der |Residuum|-Verteilung (Grundsatzdokumentation
#: 9.15: Toleranzen auf Maximum und hohen Perzentilen, nie auf
#: Mittelwert oder Median).
PERZENTILE = (95, 99)

# --------------------------------------------------------------------------- #
# Anlaesse
# --------------------------------------------------------------------------- #

#: Der Uebernahmestand am Verankerungszeitpunkt $t_a$ (A-M1, erster Punkt).
ANLASS_UEBERNAHME = "uebernahme"
#: Der naechste Vertragsstichtag laut Fortschreibung (A-M1, zweiter Punkt).
ANLASS_FORTSCHREIBUNG = "fortschreibung"
#: Ein Punkt des Verlaufs: 5 Jahre, 10 Jahre, Ablauf (A-M2).
ANLASS_VERLAUF = "verlauf"

STICHTAGS_ANLAESSE = (ANLASS_UEBERNAHME, ANLASS_FORTSCHREIBUNG)

#: Die Geschaeftsvorfaelle des Bewegungsjournals (A-M3). Die Kennungen sind
#: dieselben wie im Ledger der Bestandsfuehrung.
GEVO_ARTEN = ("STO", "PEX", "ABL", "TOD", "INV", "REA", "ERH", "RED")

ALLE_ANLAESSE = STICHTAGS_ANLAESSE + (ANLASS_VERLAUF,) + GEVO_ARTEN

#: Was ein Geschaeftsvorfall mit dem Deckungskapital macht: der Zustand
#: unmittelbar VOR und unmittelbar NACH dem Vorfall, am selben Zeitpunkt.
#: ``None`` heisst: Die Engine rechnet diesen Zustandswechsel nicht — dann
#: ist ``dDK`` fuer diesen Vorfall ein harter Fehler statt einer stillen
#: Falschrechnung.
#:
#: * Rueckkauf, Ablauf und Tod beenden den Vertrag; das Deckungskapital
#:   geht auf null, ``dDK`` ist also der negative Bestandswert.
#: * Die Beitragsfreistellung wandelt um: vom beitragspflichtigen auf den
#:   beitragsfreien Wert. Bei verlustfreier Umwandlung ist ``dDK`` null,
#:   ein Abzug macht sie negativ — genau der Pruefwert, um den es geht.
#: * Eine dynamische Erhoehung legt eine neue Scheibe an, deren Reserve bei
#:   null beginnt: ``dDK`` ist null. Ein anderer Wert ist ein Befund.
#: * Die Herabsetzung TEILT den Vertrag: Ein Anteil laeuft
#:   beitragspflichtig weiter, der Rest wird umgewandelt. Wie viel, steht
#:   nicht im Zustand, sondern im Parameter des Vorfalls — deshalb
#:   verlangt sie ``parameter["anteil"]`` am Pruefpunkt.
#: * Invalidisierung und Reaktivierung sind Zustandswechsel des
#:   BU-Zustandsgraphen. Sie brauchen die BU-Zustandsbewertung; die
#:   Engine lehnt sie ab, statt einen KLV-Wert auszugeben.
GEVO_WIRKUNG: Mapping[str, Optional[Tuple[str, str]]] = {
    "STO": ("bestand", "beendet"),
    "ABL": ("bestand", "beendet"),
    "TOD": ("bestand", "beendet"),
    "PEX": ("beitragspflichtig", "beitragsfrei"),
    "RED": ("beitragspflichtig", "herabgesetzt"),
    "ERH": ("bestand", "bestand"),
    "INV": None,
    "REA": None,
}

#: Zustaende, die einen Parameter des Vorfalls brauchen — und welchen.
#: Ohne ihn ist der Wert nicht bestimmt, und die Engine bricht ab, statt
#: einen Anteil zu raten.
ZUSTANDSPARAMETER: Mapping[str, str] = {"herabgesetzt": "anteil"}


class AktuartestFehler(ValueError):
    """Testauftrag verletzt den Engine-Vertrag — fail-fast."""


@dataclass(frozen=True)
class Pruefpunkt:
    """Ein Vergleich: ein Zeitpunkt und die dort erwarteten Werte.

    ``monate`` sind die vollen Vertragsmonate seit Beginn. Auf dem
    Jahresgitter (Vielfaches von 12) rechnet die Engine die Verlaufszeile,
    unterjaehrig die linear gemischte Monatsreserve. Unterjaehrig ist NUR
    mit einem Geschaeftsvorfall als ``anlass`` zulaessig — dann ist die
    Mischungskonvention der Gegenstand der Pruefung, nicht ihre Stoerung.

    ``erwartet`` traegt die gelieferten Vergleichswerte mit Kern-
    Groessennamen als Schluesseln.

    ``parameter`` traegt, was der Vorfall selbst mitbringt und was nicht
    aus dem Vertrag folgt — bei der Herabsetzung der fortgefuehrte
    Beitragsanteil. Fuer alle anderen Anlaesse bleibt er leer.
    """

    monate: int
    erwartet: Dict[str, float]
    anlass: str
    parameter: Mapping[str, float] = field(default_factory=dict)

    @property
    def ist_gevo(self) -> bool:
        return self.anlass in GEVO_ARTEN

    @property
    def jahr(self) -> int:
        return self.monate // 12

    @property
    def unterjaehrig(self) -> bool:
        return self.monate % 12 != 0


@dataclass(frozen=True)
class Vertragspruefung:
    """Ein Vertrag mit allen Pruefpunkten, die ein Test an ihm hat.

    ``historientyp`` clustert die Verteilungsauswertung (z. B. nach der
    Uebergangsklasse der Historie); die Engine schreibt ihm keine Semantik
    vor.
    """

    police_id: str
    model_point: Dict[str, Any]
    historientyp: str
    punkte: Tuple[Pruefpunkt, ...]
    scheiben: Tuple[Tuple[int, float], ...] = field(default_factory=tuple)
    beitragsfrei_seit_jahr: Optional[int] = None
    #: Schichtparameter des Migrationszugangs (Grundsatzdokumentation 9.11).
    #: Sind sie gesetzt, vergleicht die Engine den Wert EINSCHLIESSLICH
    #: Korrekturschicht — das Residuum wird damit von einer Restgroesse zu
    #: einer kalibrierten: Am Verankerungszeitpunkt ist es
    #: konstruktionsbedingt null, und interessant wird, was DANEBEN
    #: passiert (der zweite Punkt von A-M1, der Verlauf von A-M2, die
    #: Geschaeftsvorfaelle von A-M3).
    #:
    #: Ohne sie bleibt der rohe Wertvergleich — der ist weiter gueltig,
    #: solange ein Fall keine Schicht fuehrt.
    schicht: Optional[Schichtparameter] = None
    #: Der Verankerungszeitpunkt in vollen Vertragsmonaten. Pflicht, wenn
    #: eine Schicht gesetzt ist: Die Schicht rechnet ab dort, nicht ab
    #: Vertragsbeginn.
    monate_ta: Optional[int] = None
    #: ANFANGSZUSTAND einer Herabsetzung VOR dem Migrationsstichtag:
    #: ``(vertragsjahr, fortgefuehrter_anteil)``. Der Vertrag wird dann als
    #: geteilter Vertrag bewertet (Kern 3.1.0,
    #: :class:`~rechner_pipeline.kern.beitragsreduktion.ReduzierterVertrag`,
    #: Zielverfahren prospektiv). Eine Herabsetzung ZWISCHEN den
    #: Pruefpunkten ist kein Anfangszustand, sondern ein RED-Pruefpunkt.
    reduktion: Optional[Tuple[int, float]] = None


def verankerungspunkt(monate: int, erwartet: Dict[str, float]) -> Pruefpunkt:
    """Der Uebernahmestand am Verankerungszeitpunkt — der haeufigste Punkt."""
    return Pruefpunkt(monate=monate, erwartet=erwartet, anlass=ANLASS_UEBERNAHME)


# --------------------------------------------------------------------------- #
# Auftragspruefung
# --------------------------------------------------------------------------- #


def _pruefe_punkt(v: Vertragspruefung, p: Pruefpunkt, mp: ModelPoint) -> None:
    if p.anlass not in ALLE_ANLAESSE:
        raise AktuartestFehler(
            f"police {v.police_id}: unbekannter Anlass {p.anlass!r} — "
            f"bekannt sind {list(ALLE_ANLAESSE)}"
        )
    if p.monate < 0:
        raise AktuartestFehler(
            f"police {v.police_id}: monate={p.monate} liegt vor Vertragsbeginn"
        )
    if p.unterjaehrig and not p.ist_gevo:
        raise AktuartestFehler(
            f"police {v.police_id}: monate={p.monate} ist kein Rechenpunkt "
            f"(Anlass {p.anlass!r}). Stichtags- und Verlaufspunkte liegen auf "
            "dem Vertragsjahrestag; ein Wert dazwischen waere linear "
            "gemischt und misst die Mischungskonvention statt der Methode "
            "(ADR-010). Unterjaehrig ist nur ein Geschaeftsvorfall, weil "
            "dort die Konvention selbst den ausgezahlten Betrag bestimmt"
        )
    if p.monate > 12 * mp.n:
        raise AktuartestFehler(
            f"police {v.police_id}: monate={p.monate} liegt hinter dem "
            f"Vertragsende (n={mp.n} Jahre)"
        )
    if not p.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: Pruefpunkt {p.anlass} ohne "
            "Vergleichsgroessen ist kein Testauftrag"
        )
    unbekannt = sorted(set(p.erwartet) - set(GEPRUEFTE_GROESSEN))
    if unbekannt:
        raise AktuartestFehler(
            f"police {v.police_id}: unbekannte Groessen {unbekannt} "
            f"(gerechnet werden: {list(GEPRUEFTE_GROESSEN)})"
        )
    if "dDK" in p.erwartet and not p.ist_gevo:
        raise AktuartestFehler(
            f"police {v.police_id}: dDK ist die Veraenderung des "
            f"Deckungskapitals DURCH einen Geschaeftsvorfall; am Anlass "
            f"{p.anlass!r} gibt es keinen Vorfall, der sie erzeugt"
        )
    if p.ist_gevo and GEVO_WIRKUNG[p.anlass] is None and "dDK" in p.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: dDK fuer {p.anlass} verlangt die "
            "BU-Zustandsbewertung (Invalidisierung/Reaktivierung wechseln "
            "den Zustand des BU-Graphen). Die Engine rechnet sie nicht und "
            "gibt keinen KLV-Wert aus, der so aussaehe als sei er einer"
        )
    verlangt = ZUSTANDSPARAMETER.get(
        (GEVO_WIRKUNG.get(p.anlass) or ("", ""))[1]
    )
    if verlangt is not None and "dDK" in p.erwartet:
        wert = p.parameter.get(verlangt)
        if wert is None:
            raise AktuartestFehler(
                f"police {v.police_id}: dDK fuer {p.anlass} verlangt "
                f"parameter[{verlangt!r}] — wie weit der Vertrag geteilt "
                "wird, steht im Vorfall und nicht im Vertrag. Die Engine "
                "raet ihn nicht"
            )
        if not math.isfinite(wert) or not 0.0 <= wert <= 1.0:
            raise AktuartestFehler(
                f"police {v.police_id}: {verlangt}={wert!r} liegt nicht in "
                "[0, 1] — er ist der fortgefuehrte Bruchteil des Beitrags"
            )
        if p.unterjaehrig:
            raise AktuartestFehler(
                f"police {v.police_id}: monate={p.monate} — die Herabsetzung "
                "findet nur am Vertragsstichtag statt (Beschluss 2026-08-28, "
                "kern.beitragsreduktion). Ein unterjaehriger Punkt setzte "
                "eine Rumpfjahr-Konvention voraus, die noch nicht "
                "entschieden ist"
            )
    if v.scheiben and set(p.erwartet) - {"kVx_MRV", "RKW", "BJB", "dDK"}:
        raise AktuartestFehler(
            f"police {v.police_id}: mit Erhoehungsscheiben rechnet die "
            "Engine nur kVx_MRV, RKW, BJB und dDK vertragsweit — andere "
            "Groessen sind nicht definiert statt still falsch"
        )
    if v.beitragsfrei_seit_jahr is not None and "RKW" in p.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: RKW im beitragsfreien Zustand ist nicht "
            "definiert — Groesse weglassen oder Engine erweitern"
        )
    if v.beitragsfrei_seit_jahr is None and "VS_bfr" in p.erwartet:
        raise AktuartestFehler(
            f"police {v.police_id}: VS_bfr ist nur im beitragsfreien "
            "Zustand eine Testgroesse — die beitragsfreie Summe existiert "
            "erst nach der Umwandlung (Bestand-Konvention fuehrt fuer "
            "aktive Vertraege 0.00, die Blattzeile den hypothetischen "
            "Umwandlungswert; still verglichen waere beides falsch)"
        )


def _pruefe_auftrag(v: Vertragspruefung) -> ModelPoint:
    """Engine-Vertrag des Auftrags — Verletzungen sind harte Fehler."""
    if not v.punkte:
        raise AktuartestFehler(
            f"police {v.police_id}: kein Pruefpunkt — ein Vertrag ohne "
            "Vergleichszeitpunkt ist kein Testauftrag"
        )
    if v.scheiben and v.beitragsfrei_seit_jahr is not None:
        raise AktuartestFehler(
            f"police {v.police_id}: Erhoehungsscheiben UND "
            "Beitragsfreistellung zusammen rechnet die Engine nicht — der "
            "beitragsfreie Scheibenpfad ist nicht definiert statt still "
            "der aktive Track"
        )
    if v.beitragsfrei_seit_jahr is not None and v.beitragsfrei_seit_jahr <= 0:
        raise AktuartestFehler(
            f"police {v.police_id}: beitragsfrei_seit_jahr="
            f"{v.beitragsfrei_seit_jahr} ist kein Vertragsjahr"
        )
    if v.reduktion is not None:
        jahr, anteil = v.reduktion
        unvertraeglich = [
            name for name, gesetzt in (
                ("Erhoehungsscheiben", bool(v.scheiben)),
                ("Beitragsfreistellung als Anfangszustand",
                 v.beitragsfrei_seit_jahr is not None),
                ("Korrekturschicht", v.schicht is not None),
            ) if gesetzt
        ]
        if unvertraeglich:
            raise AktuartestFehler(
                f"police {v.police_id}: Herabsetzung als Anfangszustand "
                f"zusammen mit {', '.join(unvertraeglich)} rechnet die "
                "Engine nicht — die Kombination ist nicht definiert statt "
                "still ein Track"
            )
        if jahr <= 0:
            raise AktuartestFehler(
                f"police {v.police_id}: Reduktionsjahr {jahr} ist kein "
                "Vertragsjahr"
            )
        if not 0.0 <= anteil <= 1.0:
            raise AktuartestFehler(
                f"police {v.police_id}: Reduktionsanteil {anteil} liegt "
                "nicht in [0, 1] — er ist der fortgefuehrte Bruchteil des "
                "Beitrags"
            )
        frueh = [p.monate for p in v.punkte if p.monate < 12 * jahr]
        if frueh:
            raise AktuartestFehler(
                f"police {v.police_id}: Pruefpunkte {sorted(frueh)[:3]} "
                f"liegen VOR der Herabsetzung (Jahr {jahr}) — dort gilt der "
                "unreduzierte Vertrag, der Auftrag ist widerspruechlich"
            )
    if v.schicht is not None:
        if v.monate_ta is None:
            raise AktuartestFehler(
                f"police {v.police_id}: Schichtparameter ohne monate_ta — die "
                "Korrekturschicht rechnet ab dem Verankerungszeitpunkt, nicht "
                "ab Vertragsbeginn"
            )
        if v.monate_ta % 12 != 0 or v.monate_ta < 0:
            raise AktuartestFehler(
                f"police {v.police_id}: monate_ta={v.monate_ta} ist kein "
                "Rechenpunkt (Grundsatzdokumentation 9.12)"
            )
        frueh = [p.monate for p in v.punkte if p.monate < v.monate_ta]
        if frueh:
            raise AktuartestFehler(
                f"police {v.police_id}: Pruefpunkte {sorted(frueh)[:3]} liegen "
                f"VOR dem Verankerungszeitpunkt {v.monate_ta} — dort ist die "
                "Korrekturschicht nicht definiert, der Vertrag gehoerte dem "
                "abgebenden Unternehmen"
            )
    doppelt = _doppelte_punkte(v.punkte)
    if doppelt:
        raise AktuartestFehler(
            f"police {v.police_id}: mehrfacher Pruefpunkt {doppelt} — "
            "derselbe Zeitpunkt mit demselben Anlass zaehlte doppelt in "
            "die Verteilung"
        )
    mp = ModelPoint(**v.model_point)
    for p in v.punkte:
        _pruefe_punkt(v, p, mp)
    return mp


def _doppelte_punkte(punkte: Tuple[Pruefpunkt, ...]) -> List[Tuple[int, str]]:
    gesehen: Dict[Tuple[int, str], int] = {}
    for p in punkte:
        gesehen[(p.monate, p.anlass)] = gesehen.get((p.monate, p.anlass), 0) + 1
    return sorted(k for k, n in gesehen.items() if n > 1)


# --------------------------------------------------------------------------- #
# Systemwerte
# --------------------------------------------------------------------------- #


def _kerne(v: Vertragspruefung, mp: ModelPoint):
    grund = Rechenkern(mp)
    scheiben = [
        (jahr_s, Rechenkern(erhoehungs_scheibe(mp, jahr_s, vs)))
        for jahr_s, vs in v.scheiben
    ]
    return grund, scheiben


def _deckungskapital(
    v: Vertragspruefung,
    mp: ModelPoint,
    kern: Rechenkern,
    scheiben,
    monate: int,
    zustand: str,
    parameter: Mapping[str, float] = MappingProxyType({}),
    red_verfahren: str = PROSPEKTIV,
) -> float:
    """Deckungskapital in einem benannten Zustand — ohne Interpolation.

    ``bestand`` ist der gefuehrte Wert, ``beendet`` ist null (der Vertrag
    existiert nach dem Vorfall nicht mehr), ``beitragspflichtig`` und
    ``beitragsfrei`` sind die beiden Seiten der Umwandlung.
    ``herabgesetzt`` ist der geteilte Vertrag nach einer Beitragsreduktion.
    """
    if zustand == "beendet":
        return 0.0
    if v.reduktion is not None:
        # Anfangszustand Herabsetzung: der geteilte Vertrag (Kern 3.1.0).
        rv = ReduzierterVertrag.nach(
            kern, v.reduktion[0], v.reduktion[1], verfahren=red_verfahren)
        if zustand == "herabgesetzt":
            raise AktuartestFehler(
                f"police {v.police_id}: zweite Herabsetzung eines bereits "
                "herabgesetzten Vertrags ist nicht abgebildet"
            )
        if zustand == "beitragsfrei":
            if monate % 12:
                raise AktuartestFehler(
                    f"police {v.police_id}: Beitragsfreistellung eines "
                    "herabgesetzten Vertrags unterjaehrig ist nicht "
                    "abgebildet — sie wirkt am Vertragsjahrestag"
                )
            return rv.reserve_beitragsfrei(monate // 12, monate)
        # "bestand" und "beitragspflichtig": der gefuehrte Wert des
        # geteilten Vertrags.
        return rv.monatsreserve(monate).vx_mrv
    if zustand == "herabgesetzt":
        # Das Zielverfahren rechnet prospektiv, also verlustfrei. Rechnet
        # das Quellsystem mit Abzug, ist die Differenz kein Fehler,
        # sondern die Verfahrensfrage — sie gehoert in das Residuum und
        # nicht in eine Anpassung der Engine (kern.beitragsreduktion).
        return reduziere(
            kern, monate // 12, parameter["anteil"], verfahren=red_verfahren
        ).dk_nach
    if zustand == "beitragsfrei":
        a0 = v.beitragsfrei_seit_jahr
        if a0 is None:
            raise AktuartestFehler(
                f"police {v.police_id}: beitragsfreier Wert verlangt "
                "beitragsfrei_seit_jahr"
            )
        if monate % 12:
            return kern.monatsreserve_beitragsfrei(a0, monate)
        return kern.reserve_beitragsfrei(a0, monate // 12)
    # "bestand" und "beitragspflichtig" sind derselbe gefuehrte Wert; die
    # Unterscheidung benennt nur, worauf sich der Vergleich bezieht.
    if scheiben:
        return vertrags_monatsreserve(kern, scheiben, monate).vx_mrv
    if monate % 12:
        return kern.monatsreserve(monate).vx_mrv
    return kern.zustand_am(monate).vx_mrv


def _schichtwert(v: Vertragspruefung, mp: ModelPoint, p: Pruefpunkt) -> float:
    """Der Wert der Korrekturschicht am Pruefpunkt (0.0 ohne Schicht).

    Die Schicht rechnet ab dem Verankerungszeitpunkt; ein Pruefpunkt DAVOR
    liegt ausserhalb ihrer Definition und ist ein Auftragsfehler. Auf dem
    Jahresgitter wird der Verlaufswert genommen, unterjaehrig linear
    zwischen den Jahresraendern gemischt — dieselbe Konvention wie fuer die
    Basisschicht (Abschnitt 6), denn die Schicht ist dieselbe Rekursion
    mit anderen Zahlungen und darf keine eigene Zeitachse bekommen
    ("Overlay ohne dritte Uhr", 9.5).
    """
    if v.schicht is None:
        return 0.0
    jahr_ta = v.monate_ta // 12
    kern = Rechenkern(mp)
    basis = [kern.verlaufszeile(a).drx_bpfl for a in range(jahr_ta, mp.n + 1)]
    if v.schicht.formfunktion == "konstantes_fenster":
        fenster = int(v.schicht.formparameter["fenster"])
        form = form_konstantes_fenster(len(basis), min(fenster, len(basis)))
    else:
        form = form_proportional_zur_basis(basis)
    bw = kern.produkt.bw
    schicht = Korrekturschicht(
        bw.modell, tuple(tuple(pair) for pair in v.schicht.vererbend)
    )
    verlauf = schicht.verlauf(v.schicht, form, mp.x + jahr_ta)

    seit_ta = p.monate - v.monate_ta
    j, rest = divmod(seit_ta, 12)
    if j >= len(verlauf) - 1:
        return verlauf[-1]
    if rest == 0:
        return verlauf[j]
    anteil = rest / 12.0
    return (1.0 - anteil) * verlauf[j] + anteil * verlauf[j + 1]


def _system_werte(
    v: Vertragspruefung, mp: ModelPoint, p: Pruefpunkt,
    red_verfahren: str = PROSPEKTIV,
) -> Dict[str, float]:
    """Die angeforderten Groessen am Pruefpunkt — ohne Interpolation."""
    kern, scheiben = _kerne(v, mp)
    werte: Dict[str, float] = {}
    gefragt = set(p.erwartet)

    if "dDK" in gefragt:
        vor, nach = GEVO_WIRKUNG[p.anlass]  # von _pruefe_punkt abgesichert
        dk_vor = _deckungskapital(
            v, mp, kern, scheiben, p.monate, vor, p.parameter,
            red_verfahren=red_verfahren)
        dk_nach = _deckungskapital(
            v, mp, kern, scheiben, p.monate, nach, p.parameter,
            red_verfahren=red_verfahren)
        werte["dDK"] = dk_nach - dk_vor

    if v.reduktion is not None:
        # Der geteilte Vertrag (Anfangszustand Herabsetzung): Reserven und
        # Rueckkaufswert vertragsweit ueber beide Teile, der Beitrag ist
        # der fortgefuehrte Anteil. Keine Schicht dazu — die Kombination
        # weist _pruefe_auftrag zurueck.
        rv = ReduzierterVertrag.nach(
            kern, v.reduktion[0], v.reduktion[1], verfahren=red_verfahren)
        if gefragt & {"kVx_MRV", "RKW"}:
            m = rv.monatsreserve(p.monate)
            if "kVx_MRV" in gefragt:
                werte["kVx_MRV"] = m.vx_mrv
            if "RKW" in gefragt:
                werte["RKW"] = m.rkw
        if "BJB" in gefragt:
            werte["BJB"] = rv.bjb(p.monate)
        return werte

    if scheiben:
        if gefragt & {"kVx_MRV", "RKW"}:
            m = vertrags_monatsreserve(kern, scheiben, p.monate)
            if "kVx_MRV" in gefragt:
                werte["kVx_MRV"] = m.vx_mrv
            if "RKW" in gefragt:
                werte["RKW"] = m.rkw
        if "BJB" in gefragt:
            # Jede Scheibe ist ein eigener Modellpunkt mit eigenem
            # Beitrag bis zu IHRER Beitragszahlungsdauer — dieselbe
            # Regel wie in der Bestandsfuehrung
            # (bestand.auswertung.beitraege); der gelieferte
            # Jahresbeitrag eines Dynamik-Vertrags enthaelt die
            # Scheibenbeitraege.
            gesamt = (0.0 if p.monate >= 12 * mp.t
                      else kern.gross_annual_premium())
            for erh_jahr, k in scheiben:
                if p.monate - 12 * erh_jahr < 12 * k.mp.t:
                    gesamt += k.gross_annual_premium()
            werte["BJB"] = gesamt
        return werte

    if v.beitragsfrei_seit_jahr is not None:
        a0 = v.beitragsfrei_seit_jahr
        if "kVx_MRV" in gefragt:
            werte["kVx_MRV"] = _deckungskapital(
                v, mp, kern, scheiben, p.monate, "beitragsfrei"
            )
        if "VS_bfr" in gefragt:
            werte["VS_bfr"] = kern.beitragsfreie_summe(a0)
        if "BJB" in gefragt:
            werte["BJB"] = 0.0
        return werte

    if p.unterjaehrig:
        m = kern.monatsreserve(p.monate)
        if "kVx_MRV" in gefragt:
            werte["kVx_MRV"] = m.vx_mrv
        if "RKW" in gefragt:
            werte["RKW"] = m.rkw
    else:
        zeile = kern.zustand_am(p.monate)
        if "kVx_MRV" in gefragt:
            werte["kVx_MRV"] = zeile.vx_mrv
        if "RKW" in gefragt:
            werte["RKW"] = zeile.rkw
    if "BJB" in gefragt:
        werte["BJB"] = (
            0.0 if p.jahr >= mp.t else kern.gross_annual_premium()
        )
    return _mit_schicht(v, mp, p, werte)


#: Groessen, auf die die Korrekturschicht wirkt. Das Deckungskapital
#: traegt sie unmittelbar; der Rueckkaufswert folgt ihr, weil die Schicht
#: sich bei Rueckkauf mit auszahlt (Grundsatzdokumentation 9.7, Klasse B
#: wertkontinuierlich). Beitrag und beitragsfreie Summe beruehrt sie
#: nicht — sie sind Groessen des Vertrags, nicht seiner Bewertung.
SCHICHT_GROESSEN = ("kVx_MRV", "RKW", "dDK")


def _mit_schicht(
    v: Vertragspruefung, mp: ModelPoint, p: Pruefpunkt, werte: Dict[str, float]
) -> Dict[str, float]:
    """Die Korrekturschicht auf die betroffenen Groessen legen.

    Ohne Schicht bleibt alles unveraendert — der rohe Wertvergleich ist
    weiter gueltig, solange ein Fall keine fuehrt.

    Mit Schicht misst der Test nicht mehr ``system - erwartet`` roh,
    sondern die Differenz EINSCHLIESSLICH der verankerten Korrektur. Am
    Verankerungszeitpunkt ist sie konstruktionsbedingt null; was der Test
    dann noch findet, liegt DANEBEN — in der Fortschreibung, im Verlauf
    oder in einem Geschaeftsvorfall. Genau das ist der Zugewinn.

    Bei ``dDK`` wirkt sie doppelt und hebt sich zum Teil auf: Ein
    vererbender Vorfall (Tod) laesst die Schicht verfallen, ein
    wertkontinuierlicher (Storno) zahlt sie mit aus. Die Engine bildet
    deshalb dieselbe Differenz wie fuer die Basisschicht — vorher minus
    nachher — nur auf dem Gesamtwert.
    """
    if v.schicht is None:
        return werte
    korr = _schichtwert(v, mp, p)
    for groesse in SCHICHT_GROESSEN:
        if groesse not in werte:
            continue
        if groesse == "dDK":
            # dDK ist bereits eine Differenz. Die Schicht veraendert sie um
            # ihren eigenen Sprung an dieser Stelle: Bei Beendigung faellt
            # sie mit auf null, bei einer Umwandlung laeuft sie weiter.
            vor, nach = GEVO_WIRKUNG[p.anlass]
            werte[groesse] += (0.0 if nach == "beendet" else korr) - korr
        else:
            werte[groesse] += korr
    return werte


# --------------------------------------------------------------------------- #
# Vergleich
# --------------------------------------------------------------------------- #


def _ok(ist: float, soll: float, k: Kriterium) -> bool:
    return math.isclose(ist, soll, rel_tol=k.rel_tol, abs_tol=k.abs_tol)


def pruefe_vertrag(
    v: Vertragspruefung, profil: Testprofil, *,
    red_verfahren: str = PROSPEKTIV,
) -> Dict[str, Any]:
    """Einen Vertrag an allen seinen Pruefpunkten pruefen (deterministisch).

    Auftrags-Verletzungen (falscher Rechenpunkt, unbekannte Groessen) sind
    harte Fehler; kranke LIEFERDATEN (kaputter Modellpunkt, unzulaessige
    Scheibe) werden je Vertrag isoliert und als Befund ausgewiesen — das
    entscheidet :func:`pruefe_stichprobe`.

    Ein Vertrag gilt genau dann als bestanden, wenn JEDER seiner
    Pruefpunkte besteht: Ein Vertrag, der am Uebernahmestichtag stimmt und
    beim naechsten Stichtag nicht, hat einen Fehler.
    """
    mp = _pruefe_auftrag(v)
    pruefungen: List[Dict[str, Any]] = []
    befunde: List[str] = []
    for p in v.punkte:
        werte = _system_werte(v, mp, p, red_verfahren=red_verfahren)
        # Beim Geschaeftsvorfalltest entscheidet die Vorfallart ueber die
        # Toleranz, sonst die Vergleichsgroesse.
        for groesse in sorted(p.erwartet):
            schluessel = p.anlass if p.ist_gevo else groesse
            k = profil.fuer(schluessel)
            system = float(werte[groesse])
            erwartet = float(p.erwartet[groesse])
            residuum = system - erwartet
            ok = _ok(system, erwartet, k)
            pruefungen.append(
                {
                    "anlass": p.anlass,
                    "monate": p.monate,
                    "groesse": groesse,
                    "system": system,
                    "erwartet": erwartet,
                    "residuum": residuum,
                    "ok": ok,
                }
            )
            if not ok:
                befunde.append(
                    f"{p.anlass}@{p.monate}M {groesse}: system {system!r} "
                    f"vs. erwartet {erwartet!r} (residuum {residuum!r})"
                )
    return {
        "police_id": v.police_id,
        "historientyp": v.historientyp,
        "anlaesse": sorted({p.anlass for p in v.punkte}),
        "bestanden": not befunde,
        "pruefungen": pruefungen,
        "befunde": befunde,
    }


def _perzentil(sortierte_betraege: List[float], p: int) -> float:
    """Empirisches Perzentil (deterministisch, ohne Interpolation)."""
    idx = max(0, math.ceil(p / 100.0 * len(sortierte_betraege)) - 1)
    return sortierte_betraege[idx]


def verteilung(residuen: List[float]) -> Dict[str, Any]:
    """Verteilungsgroessen der |Residuen| — die EINZIGEN Aggregate.

    Keine Summe der Vergleichswerte, kein Mittelwert, kein Median
    (ADR-010, Grundsatzdokumentation 9.15). Die Betragssumme der
    ABWEICHUNGEN ist eine Groesse der Residuum-Verteilung, keine
    Bestandssumme. Oeffentlich, weil das Gate-Kommando die Aggregate
    hiermit nachrechnet.
    """
    betraege = sorted(abs(r) for r in residuen)
    if not betraege:
        return {"anzahl_werte": 0}
    aus: Dict[str, Any] = {
        "anzahl_werte": len(betraege),
        "max_abs_residuum": betraege[-1],
        "summe_abs_residuum": math.fsum(betraege),
    }
    for p in PERZENTILE:
        aus[f"p{p}_abs_residuum"] = _perzentil(betraege, p)
    return aus


def verteilungsbefunde(
    verteilungen: Mapping[str, Dict[str, Any]], profil: Testprofil
) -> List[str]:
    """Wo eine Verteilung ihre Abnahmegrenze reisst.

    Auch wenn jeder Einzelwert in seiner Toleranz liegt, kann eine
    Verteilung zu breit sein, um eine Methode zu belegen. Geprueft wird auf
    Maximum und 95er-Perzentil, nie auf Mittelwert oder Median.
    """
    befunde: List[str] = []
    for schluessel in sorted(verteilungen):
        v = verteilungen[schluessel]
        if not v.get("anzahl_werte"):
            continue
        k = profil.fuer(schluessel)
        for feld, grenze in (
            ("max_abs_residuum", k.max_abs_residuum),
            ("p95_abs_residuum", k.p95_abs_residuum),
        ):
            if grenze is None:
                continue
            wert = v.get(feld)
            if wert is not None and wert > grenze:
                befunde.append(
                    f"{schluessel}: {feld}={wert!r} ueber der "
                    f"Abnahmegrenze {grenze!r}"
                )
    return befunde


def pruefe_stichprobe(
    vertraege: List[Vertragspruefung],
    stichprobe: Stichprobe,
    profil: Testprofil,
    *,
    transportsicherung: Optional[Mapping[str, Any]] = None,
    system: Optional[Mapping[str, str]] = None,
    red_verfahren: str = PROSPEKTIV,
) -> Dict[str, Any]:
    """Einen der drei Tests ueber eine belegte Stichprobe fahren.

    ``vertraege`` muessen die Stichprobe exakt abdecken: Jeder gezogene
    Vertrag wird geprueft, kein anderer. Fehlende oder ueberzaehlige
    Auftraege sind Mengenbefunde und schlagen den Test fehl — die
    Nichtpruefung der Nicht-Stichprobe dagegen ist per Definition kein
    Befund. ``transportsicherung`` (z. B. Datei-Hashes oder gelieferte
    Kontrollsummen) wird unveraendert und GETRENNT ausgewiesen; sie ist
    nie Teil des fachlichen Urteils.
    """
    if not vertraege:
        raise AktuartestFehler(
            "leere Auftragsliste — ein Test ohne Vertraege ist kein "
            "bestandener Test, sondern ein Aufruffehler"
        )
    ids = [v.police_id for v in vertraege]
    if len(ids) != len(set(ids)):
        doppelt = sorted({i for i in ids if ids.count(i) > 1})
        raise AktuartestFehler(
            f"doppelte Pruefauftraege fuer {doppelt[:5]} — die Verteilung "
            "des Residuums waere verzerrt"
        )

    gezogen = set(stichprobe.police_ids)
    geliefert = set(ids)
    mengenbefunde: List[str] = []
    fehlend = sorted(gezogen - geliefert)
    if fehlend:
        mengenbefunde.append(
            f"stichprobe nicht abgearbeitet: {len(fehlend)} Vertraege "
            f"ohne Pruefauftrag (z. B. {fehlend[:5]})"
        )
    ueberzaehlig = sorted(geliefert - gezogen)
    if ueberzaehlig:
        mengenbefunde.append(
            f"{len(ueberzaehlig)} Pruefauftraege ausserhalb der "
            f"Stichprobe (z. B. {ueberzaehlig[:5]}) — der Beleg deckt "
            "sie nicht"
        )
    stichprobe_vollstaendig = not mengenbefunde

    ergebnisse: List[Dict[str, Any]] = []
    for v in vertraege:
        try:
            ergebnisse.append(
                pruefe_vertrag(v, profil, red_verfahren=red_verfahren))
        except AktuartestFehler:
            # Ein verletzter Engine-Vertrag ist ein Konstruktionsfehler
            # des AUFRUFS, kein Lieferbefund — er wird nie zu einem
            # Vertrags-Befund herabgestuft (ADR-010 Abschnitt 4).
            raise
        except DATEN_AUSNAHMEN as exc:
            ergebnisse.append(
                {
                    "police_id": v.police_id,
                    "historientyp": v.historientyp,
                    "anlaesse": sorted({p.anlass for p in v.punkte}),
                    "bestanden": False,
                    "pruefungen": [],
                    "befunde": [
                        "daten: Vertrag nicht rechenbar "
                        f"({type(exc).__name__}: {exc})"
                    ],
                }
            )

    alle_pruefungen = [p for e in ergebnisse for p in e["pruefungen"]]

    # Zwei Cluster-Achsen: der Historientyp sagt, WELCHE Vertraege
    # auseinanderlaufen, der Anlass sagt, WO im Vertragsleben.
    gruppen: Dict[str, Dict[str, Any]] = {}
    for typ in sorted({e["historientyp"] for e in ergebnisse}):
        im_typ = [e for e in ergebnisse if e["historientyp"] == typ]
        residuen = [p["residuum"] for e in im_typ for p in e["pruefungen"]]
        gruppen[typ] = {
            "anzahl": len(im_typ),
            "bestanden": sum(1 for e in im_typ if e["bestanden"]),
            **verteilung(residuen),
        }

    nach_anlass: Dict[str, Dict[str, Any]] = {}
    for anlass in sorted({p["anlass"] for p in alle_pruefungen}):
        residuen = [p["residuum"] for p in alle_pruefungen if p["anlass"] == anlass]
        nach_anlass[anlass] = {
            "anzahl_vergleiche": len(residuen),
            **verteilung(residuen),
        }

    # Grundlage der Verteilungsgrenzen: beim Geschaeftsvorfalltest die
    # Vorfallart, sonst die Vergleichsgroesse.
    schluessel_von = (
        (lambda p: p["anlass"])
        if profil.kennung == "A-M3"
        else (lambda p: p["groesse"])
    )
    nach_schluessel: Dict[str, Dict[str, Any]] = {}
    for s in sorted({schluessel_von(p) for p in alle_pruefungen}):
        residuen = [p["residuum"] for p in alle_pruefungen if schluessel_von(p) == s]
        nach_schluessel[s] = verteilung(residuen)

    grenzbefunde = verteilungsbefunde(nach_schluessel, profil)
    alle_residuen = [p["residuum"] for p in alle_pruefungen]
    fehlgeschlagen = sum(1 for e in ergebnisse if not e["bestanden"])
    ergebnis: Dict[str, Any] = {
        "profil": profil.als_beleg(),
        "stichprobe": stichprobe.als_beleg(),
        "anzahl": len(ergebnisse),
        "bestanden": len(ergebnisse) - fehlgeschlagen,
        "fehlgeschlagen": fehlgeschlagen,
        "mengenbefunde": mengenbefunde,
        "grenzbefunde": grenzbefunde,
        "stichprobe_vollstaendig": stichprobe_vollstaendig,
        "verteilung": verteilung(alle_residuen),
        "gruppen": gruppen,
        "nach_anlass": nach_anlass,
        "nach_kriterium": nach_schluessel,
        "vertraege": ergebnisse,
        # Verfahrens-Beleg (Eigenschaft des Migrationsfalls, siehe
        # kern.beitragsreduktion): ohne ihn waere eine Differenz zweier
        # Systeme nicht erklaerbar, sondern nur ein unerklaerter Rest.
        "red_verfahren": red_verfahren,
        "test_bestanden": (
            stichprobe_vollstaendig
            and fehlgeschlagen == 0
            and not grenzbefunde
        ),
    }
    if transportsicherung is not None:
        ergebnis["transportsicherung"] = dict(transportsicherung)
    if system is not None:
        ergebnis["system"] = dict(system)
    return ergebnis
