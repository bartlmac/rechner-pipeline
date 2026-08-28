"""Korrekturschicht des Migrationszugangs: dieselbe Rekursion, andere Zahlungen.

Normative Referenz: Grundsatzdokumentation Abschnitt 9. Ein uebernommener
Vertrag wird konstruktiv neu gerechnet; die am Verankerungszeitpunkt
verbleibende Bewertungsdifferenz traegt eine eigene Schicht.

**Warum es keine zweite Engine braucht.** Abschnitt 9.6 sagt es selbst:
"Die Korrekturschicht ist kein zweiter Rechenweg, sondern dieselbe
Rekursion mit anderen Zahlungen." Die Kollapsform

.. math::
    V^{korr}_j(s, d) = c_s(j, d) + v \\cdot
    ( 1 - \\sum_{s' \\in F_s} p_{s \\to s'} ) \\cdot V^{korr}_{j+1}(s, d^+)

entsteht aus der vorhandenen Thiele-Rekursion
(:class:`~rechner_pipeline.kern.zustandsmodell.Zustandsmodell`), indem man
die **wertkontinuierlichen** Uebergaenge aus der Uebergangsfunktion
weglaesst: Ihre Wahrscheinlichkeitsmasse bleibt per Residuum-Regel im
Zustand — und genau das ist die richtige Dynamik, denn ein
wertkontinuierlicher Uebergang traegt den Schichtwert eins zu eins weiter.
Nur die **vererbenden** Ursachen zehren am Wert.

Der Nebeneffekt ist der Beweis fuer die Optionsunabhaengigkeit aus 9.8:
Storno und Beitragsfreistellung sind wertkontinuierlich, fallen also aus
der reduzierten Dynamik heraus und koennen den Kalibrierungsfaktor
$\\rho$ gar nicht beeinflussen. Was in der Grundsatzdokumentation eine
Aussage ist, wird hier eine Eigenschaft der Konstruktion.

**Historienfreiheit** (9.14): Dieses Modul sieht kein Journal. Es bekommt
den Verankerungszustand als Parameter — abgeleitet hat ihn die
Uebernahmestrecke, nicht der Kern.

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from rechner_pipeline.kern.zustandsmodell import Zustandsmodell

# Es gibt hier bewusst KEINE feste Schwelle fuer "zu kurze Restlaufzeit".
#
# Ein frueherer Entwurf hatte eine, mit der Begruendung aus
# Grundsatzdokumentation 9.10: unterhalb einer Schwelle explodiere
# $\rho = R/\Pi$. Nachgemessen traegt das nicht. $\rho$ ist ein
# Zwischenwert, kein Ausweiswert: Er waechst zwar (von 54 auf 850 bei
# einer Restlaufzeit von 20 auf 1 Jahr), wird aber mit einer im selben
# Mass kleineren Formfunktion multipliziert. Der Schichtwert bleibt in
# jedem Fall exakt das Residuum, der Terminalwert exakt null — die
# Rechnung ist bei jeder Restlaufzeit korrekt.
#
# Eine feste Zahl haette deshalb kein Ergebnis beurteilt (das tun die
# Toleranzen des aktuariellen Tests), sondern die METHODE umgeschaltet:
# ab drei Jahren verteilen, darunter ausbuchen. Zwei verschiedene
# Behandlungen desselben Sachverhalts, getrennt durch einen Wert, den
# niemand begruenden kann.
#
# Was bleibt, ist eine Entscheidung des Rechnungswesens: Ob ein
# Unternehmen kurze Restlaufzeiten ABSICHTLICH ausbuchen statt verteilen
# will. Die kommt als ``ausbuchungsgrenze`` je Aufruf herein und steht
# damit im Beleg, statt als Konstante im Kern zu stecken.

#: Schichttypen (9.13): das Historienresiduum ist die primaere
#: Qualitaetskennzahl, das Konventionsresiduum die optionale Zweitschicht.
SCHICHT_HIST = "hist"
SCHICHT_CONV = "conv"


class KorrekturschichtFehler(ValueError):
    """Verankerung nicht durchfuehrbar — fail-fast statt stiller Naeherung."""


class KeinAmortisationsraum(KorrekturschichtFehler):
    """$\\Pi = 0$: es gibt keinen Zeitraum, ueber den verteilt werden koennte.

    Der einzige mathematisch zwingende Grenzfall — nicht eine Frage der
    Bilanzpolitik, sondern eine Division durch null.
    """


class Degeneration(KorrekturschichtFehler):
    """Die gesetzte Ausbuchungsgrenze ist unterschritten.

    Wird NUR geworfen, wenn der Aufrufer eine ``ausbuchungsgrenze``
    mitgibt. Ohne sie rechnet die Schicht auch kurze Restlaufzeiten — die
    Werte stimmen dort (siehe Kopf des Moduls).
    """


class FloorVerletzung(KorrekturschichtFehler):
    """Basis plus Korrektur unterschreitet die Mindestwerte (9.10)."""

    def __init__(self, jahr: int, wert: float, floor: float) -> None:
        super().__init__(
            f"Jahr {jahr}: Basis plus Korrektur {wert!r} unter dem "
            f"Mindestwert {floor!r} — R waere zu kappen, der gekappte Teil "
            "geht in den Klaerungsprozess (Grundsatzdokumentation 9.4), nie "
            "in die Schicht"
        )
        self.jahr = jahr
        self.wert = wert
        self.floor = floor


# --------------------------------------------------------------------------- #
# Formfunktion
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Formfunktion:
    """Wie sich das Residuum ueber die Restlaufzeit verteilt (9.9).

    Anforderung der Grundsatzdokumentation: in ALLEN Erlebenszustaenden
    definiert (ein Vertrag kann beitragsfrei oder im Rentenbezug
    migrieren, eine rein beitragsproportionale Form waere unvollstaendig)
    und ueber die Restlaufzeit integrierbar mit $\\Pi > 0$.

    ``werte`` ist der Einheitsstrom je Jahr ab dem Verankerungszeitpunkt.
    ``kennung`` und ``parameter`` gehen in den Beleg — aus ihnen ist die
    Form reproduzierbar, ohne die Werte selbst zu speichern (9.11).
    """

    kennung: str
    werte: Tuple[float, ...]
    parameter: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.werte:
            raise KorrekturschichtFehler(
                f"Formfunktion {self.kennung!r}: leerer Einheitsstrom"
            )
        for i, w in enumerate(self.werte):
            if not math.isfinite(w):
                raise KorrekturschichtFehler(
                    f"Formfunktion {self.kennung!r}: Wert {i} ist {w!r}"
                )
            if w < 0.0:
                raise KorrekturschichtFehler(
                    f"Formfunktion {self.kennung!r}: Wert {i} ist negativ "
                    f"({w!r}) — der Einheitsstrom traegt kein Vorzeichen, "
                    "das Vorzeichen des Residuums steckt in rho"
                )
        if not any(w > 0.0 for w in self.werte):
            raise KorrekturschichtFehler(
                f"Formfunktion {self.kennung!r}: durchweg null — Pi waere "
                "null und rho nicht definiert"
            )

    def als_beleg(self) -> Dict[str, Any]:
        return {"kennung": self.kennung, "parameter": dict(self.parameter)}


def form_proportional_zur_basis(basisverlauf: Sequence[float]) -> Formfunktion:
    """Default aus 9.9: $g \\propto V^{base}(t)$ — glatt, ueberall definiert.

    ``basisverlauf`` sind die prospektiven Basiswerte je Jahr AB dem
    Verankerungszeitpunkt. Negative Basiswerte (ungetilgter Zillmerrest)
    tragen keinen Einheitsstrom: Ein Residuum dort zu verrenten hiesse,
    es auf einer Groesse zu verteilen, die selbst noch nicht existiert.
    """
    werte = tuple(max(0.0, float(v)) for v in basisverlauf)
    return Formfunktion(kennung="proportional_zur_basis", werte=werte)


def form_konstantes_fenster(horizont: int, fenster: int) -> Formfunktion:
    """$g \\equiv 1$ auf $[t_a,\\, t_a + n]$ (9.9, Kandidat 2).

    Am leichtesten zu erklaeren; ``fenster`` ist Produktparameter. Bei
    kurzer Restlaufzeit wird der Abbau steil (bei einem Jahr Restlaufzeit
    traegt dieses eine Jahr die ganze Differenz) — richtig gerechnet
    bleibt es trotzdem. Ob ein so steiler Abbau noch als Verteilung
    gelten soll, entscheidet der Aufrufer ueber ``ausbuchungsgrenze``.
    """
    if fenster <= 0:
        raise KorrekturschichtFehler(f"Amortisationsfenster {fenster} <= 0")
    werte = tuple(1.0 if j < fenster else 0.0 for j in range(horizont))
    return Formfunktion(
        kennung="konstantes_fenster", werte=werte, parameter={"fenster": fenster}
    )


# --------------------------------------------------------------------------- #
# Persistierte Parameter
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Schichtparameter:
    """Alles, woraus $V^{korr}$ jederzeit reproduzierbar ist (9.11).

    Persistiert werden **Parameter, keine Zwischenwerte**. Der Kern bekommt
    diesen Satz als Vertragsattribut — abgeleitet hat ihn die
    Uebernahmestrecke (9.14: die Ableitungslast liegt quellseitig oder im
    Migrationssystem, der Rechenkern bleibt historienfrei).
    """

    schichttyp: str
    verankerungszustand: str
    verweildauer: int
    rho: float
    formfunktion: str
    formparameter: Mapping[str, Any] = field(default_factory=dict)
    vererbend: Tuple[Tuple[str, str], ...] = ()
    kohorte: str = "t_a"
    in_ueberschuss: bool = True
    in_zzr: bool = True

    def __post_init__(self) -> None:
        if self.schichttyp not in (SCHICHT_HIST, SCHICHT_CONV):
            raise KorrekturschichtFehler(
                f"unbekannter Schichttyp {self.schichttyp!r}"
            )
        if not math.isfinite(self.rho):
            raise KorrekturschichtFehler(f"rho ist {self.rho!r}")
        if self.verweildauer < 0:
            raise KorrekturschichtFehler(
                f"Verweildauer {self.verweildauer} negativ"
            )

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "schichttyp": self.schichttyp,
            "verankerungszustand": self.verankerungszustand,
            "verweildauer": self.verweildauer,
            "rho": self.rho,
            "formfunktion": self.formfunktion,
            "formparameter": dict(self.formparameter),
            "vererbend": [list(p) for p in self.vererbend],
            "kohorte": self.kohorte,
            "in_ueberschuss": self.in_ueberschuss,
            "in_zzr": self.in_zzr,
        }


# --------------------------------------------------------------------------- #
# Die Schicht
# --------------------------------------------------------------------------- #


def vererbende_dynamik(
    uebergang: Callable[[str, str, int, int], float],
    vererbend: Tuple[Tuple[str, str], ...],
) -> Callable[[str, str, int, int], float]:
    """Uebergangsfunktion, in der NUR die vererbenden Ursachen wirken (9.6).

    Alles andere wird auf null gesetzt; seine Wahrscheinlichkeitsmasse
    bleibt per Residuum-Regel im Zustand
    (:meth:`Zustandsmodell._wegzuege`). Das ist die Kollapsform — nicht
    naeherungsweise, sondern exakt: Ein wertkontinuierlicher Uebergang
    traegt den Schichtwert eins zu eins weiter, der Wert verhaelt sich
    also, als waere der Vertrag geblieben.
    """
    erlaubt = frozenset(vererbend)

    def reduziert(von: str, nach: str, alter: int, dauer: int) -> float:
        if (von, nach) not in erlaubt:
            return 0.0
        return uebergang(von, nach, alter, dauer)

    return reduziert


class Korrekturschicht:
    """Die zweite Bewertungsschicht auf der Dynamik der ersten.

    Sie rechnet mit demselben :class:`Zustandsmodell` wie die Basisschicht,
    nur auf einer Uebergangsfunktion, aus der die wertkontinuierlichen
    Uebergaenge entfernt sind. Zahlungsprofil, Faelligkeit, Diskontierung
    und Rundung sind dieselben.
    """

    def __init__(
        self,
        modell: Zustandsmodell,
        vererbend: Tuple[Tuple[str, str], ...],
    ) -> None:
        unbekannt = [
            p for p in vererbend
            if p[0] not in modell.zustaende or p[1] not in modell.zustaende
        ]
        if unbekannt:
            raise KorrekturschichtFehler(
                f"vererbende Uebergaenge ausserhalb des Zustandsraums: "
                f"{unbekannt} (Zustaende: {list(modell.zustaende)})"
            )
        self.vererbend = tuple(vererbend)
        self.modell = Zustandsmodell(
            modell.zustaende,
            modell.zins,
            vererbende_dynamik(modell.uebergang, self.vererbend),
            max_dauer=modell.max_dauer,
        )

    # -- Barwert des Einheitsstroms ---------------------------------------- #

    def pi(
        self,
        form: Formfunktion,
        alter0: int,
        zustand: str,
        *,
        verweildauer: int = 0,
    ) -> float:
        """$\\Pi_s(t,d)$ — Barwert des Einheitsstroms unter der Dynamik (9.8).

        Eine geschlossene Form ist ausdruecklich nicht erforderlich: Es ist
        DIESELBE Rekursion wie fuer $V^{korr}$, nur mit $c = g$.
        """
        return self.modell.barwert(
            zustand,
            alter0,
            len(form.werte),
            zahlung_zustand=lambda s, j: form.werte[j] if s == zustand else 0.0,
            start_dauer=verweildauer,
        )

    # -- Verankerungsoperator ---------------------------------------------- #

    def verankere(
        self,
        form: Formfunktion,
        alter0: int,
        zustand: str,
        residuum: float,
        *,
        verweildauer: int = 0,
        schichttyp: str = SCHICHT_HIST,
        ausbuchungsgrenze: Optional[float] = None,
        kohorte: str = "t_a",
        in_ueberschuss: bool = True,
        in_zzr: bool = True,
    ) -> Schichtparameter:
        """$\\mathcal{A}(t, s, d, R)$: $\\rho = R/\\Pi_s(t,d)$, $c_s = \\rho g$.

        Ein Operator, vier Aufrufkontexte (9.8) — Erstverankerung bei der
        Migration, Klasse-C-Uebergang, Klasse-A-Geschaeftsvorfall mit
        $R = 0$, Zweitverankerung fuer das Konventionsresiduum. Alle vier
        rufen diese eine Funktion mit anderen Argumenten.
        """
        if not math.isfinite(residuum):
            raise KorrekturschichtFehler(f"Residuum ist {residuum!r}")
        p = self.pi(form, alter0, zustand, verweildauer=verweildauer)
        if p <= 0.0:
            # Der einzige zwingende Grenzfall: kein Zeitraum, ueber den
            # verteilt werden koennte. Keine Ermessensfrage.
            raise KeinAmortisationsraum(
                f"Pi = {p!r}: die Formfunktion traegt ueber die Restlaufzeit "
                "keinen Einheitsstrom (kein erlebter Zeitraum oder durchweg "
                "null) — es gibt nichts, worauf sich das Residuum verteilen "
                "liesse"
            )
        if ausbuchungsgrenze is not None and p < ausbuchungsgrenze:
            # Bilanzentscheidung des Aufrufers, keine Eigenschaft der Methode:
            # Er will kurze Restlaufzeiten ausbuchen statt verteilen. Die
            # Rechnung selbst waere auch hier korrekt.
            raise Degeneration(
                f"Pi = {p!r} unter der gesetzten Ausbuchungsgrenze "
                f"{ausbuchungsgrenze!r}: Das Residuum ist nach dieser Vorgabe "
                "sofort ueber das Ergebnis auszubuchen statt zu verteilen — "
                "und die Ausbuchung ist auszuweisen"
            )
        return Schichtparameter(
            schichttyp=schichttyp,
            verankerungszustand=zustand,
            verweildauer=verweildauer,
            rho=residuum / p,
            formfunktion=form.kennung,
            formparameter=form.parameter,
            vererbend=self.vererbend,
            kohorte=kohorte,
            in_ueberschuss=in_ueberschuss,
            in_zzr=in_zzr,
        )

    # -- Bewertung ---------------------------------------------------------- #

    def verlauf(
        self, parameter: Schichtparameter, form: Formfunktion, alter0: int
    ) -> List[float]:
        """$V^{korr}$ zu jedem Jahresbeginn ab dem Verankerungszeitpunkt.

        ``werte[0]`` ist der Wert AM Verankerungszeitpunkt; er ist
        konstruktionsbedingt das Residuum selbst (bis auf Gleitkomma), weil
        die Rekursion linear in der Zahlung ist und $\\rho\\Pi = R$ gilt.
        Das ist der Selbsttest, der ohne Zusatzaufwand mitlaeuft.
        """
        zustand = parameter.verankerungszustand
        rho = parameter.rho
        return self.modell.barwert_verlauf(
            zustand,
            alter0,
            len(form.werte),
            zahlung_zustand=(
                lambda s, j: rho * form.werte[j] if s == zustand else 0.0
            ),
            start_dauer=parameter.verweildauer,
        )

    def wert(
        self,
        parameter: Schichtparameter,
        form: Formfunktion,
        alter0: int,
        jahr: int,
    ) -> float:
        """$V^{korr}$ zu Beginn des Jahres ``jahr`` nach der Verankerung."""
        verlauf = self.verlauf(parameter, form, alter0)
        if not 0 <= jahr < len(verlauf):
            raise KorrekturschichtFehler(
                f"Jahr {jahr} ausserhalb des Verlaufs (0..{len(verlauf) - 1})"
            )
        return verlauf[jahr]

    # -- Guardrail: pfadweiser Floor ---------------------------------------- #

    def pruefe_floor(
        self,
        parameter: Schichtparameter,
        form: Formfunktion,
        alter0: int,
        basisverlauf: Sequence[float],
        mindestwerte: Sequence[float],
    ) -> None:
        """Basis plus Korrektur gegen die Mindestwerte — FUER ALLE ZEITPUNKTE.

        Grundsatzdokumentation 9.10: Bei $R < 0$ (typisch bei nicht
        getilgtem Abschlusskostenanteil) genuegt es NICHT, am
        Verankerungspunkt zu pruefen. Die Schicht laeuft ueber die
        Restlaufzeit und kann dazwischen unter den Floor tauchen.
        """
        korr = self.verlauf(parameter, form, alter0)
        n = min(len(korr), len(basisverlauf), len(mindestwerte))
        for j in range(n):
            gesamt = float(basisverlauf[j]) + korr[j]
            floor = float(mindestwerte[j])
            if gesamt < floor - 1e-9:
                raise FloorVerletzung(j, gesamt, floor)


# --------------------------------------------------------------------------- #
# Heilung: welcher Geschaeftsvorfall die Schicht aufloest (9.7, Klasse A)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Heilungsregel:
    """Was ein Geschaeftsvorfall mit der Korrekturschicht macht.

    ``heilt`` heisst: Der Vorfall rechnet den Vertrag neu und rechnet dabei
    das Gesamt-Deckungskapital EINSCHLIESSLICH der Schicht an. Danach ist
    der Kalibrierungsfaktor null — der Vertrag ist rein prospektiv, das
    Migrationsresiduum ist erledigt (9.7, Klasse A).

    ``geprueft`` unterscheidet eine fachlich entschiedene Zuordnung von
    einer vorlaeufigen. Vorlaeufige Eintraege sind bewusst vollstaendig
    aufgefuehrt statt weggelassen: Ein fehlender Vorfall wuerde stillschweigend
    nicht heilen, und niemand faende die Luecke.
    """

    heilt: bool
    geprueft: bool
    begruendung: str


#: Je Geschaeftsvorfall, ob er die Korrekturschicht aufloest.
#:
#: **Ziel der Zuordnung** (Beschluss 2026-08-28): Das Residuum soll so
#: schnell wie moeglich verschwinden, aber nur dort, wo es rechtskonform
#: ist — naemlich wo der Vertrag ohnehin neu gerechnet wird.
#:
#: **Abweichung von Grundsatzdokumentation 9.7:** Die Tabelle dort fuehrt
#: "Dynamik" unter den rechnenden Geschaeftsvorfaellen der Klasse A. Das
#: trifft fuer die dynamische Erhoehung dieses Systems nicht zu: Sie legt
#: eine NEUE SCHEIBE an und laesst den bestehenden Vertrag unberuehrt
#: (``kern.rechenkern.erhoehungs_scheibe``). Es wird nichts neu gerechnet,
#: also gibt es keinen Anlass, die Schicht aufzuloesen. Der Abschnitt ist
#: entsprechend praezisiert.
HEILUNG: Mapping[str, Heilungsregel] = {
    "RED": Heilungsregel(
        heilt=True, geprueft=True,
        begruendung="Beitragsreduktion rechnet den Vertrag neu — das "
                    "Gesamt-Deckungskapital einschliesslich Schicht geht in "
                    "die Neuberechnung ein (9.7, Klasse A)",
    ),
    "PEX": Heilungsregel(
        heilt=True, geprueft=False,
        begruendung="Beitragsfreistellung rechnet neu; 9.7 fuehrt sie als "
                    "Klasse A. Zuordnung uebernommen, fachlich noch nicht "
                    "bestaetigt",
    ),
    "ERH": Heilungsregel(
        heilt=False, geprueft=True,
        begruendung="Die dynamische Erhoehung legt eine neue Scheibe an und "
                    "laesst den bestehenden Vertrag unberuehrt — es wird "
                    "nichts neu gerechnet. Abweichung von 9.7, wo Dynamik "
                    "unter Klasse A steht",
    ),
    "STO": Heilungsregel(
        heilt=False, geprueft=True,
        begruendung="Rueckkauf ist wertkontinuierlich (9.7, Klasse B): Die "
                    "Schicht zahlt sich im Rueckkaufswert mit aus, statt "
                    "aufgeloest zu werden",
    ),
    "TOD": Heilungsregel(
        heilt=False, geprueft=True,
        begruendung="Tod mit fester Versicherungssumme ist vererbend (9.7, "
                    "Klasse B): Der Schichtwert verfaellt",
    ),
    "ABL": Heilungsregel(
        heilt=False, geprueft=True,
        begruendung="Der Ablauf traegt die Terminalbedingung V_korr(T) = 0 — "
                    "die Schicht ist dort ohnehin null",
    ),
    "INV": Heilungsregel(
        heilt=False, geprueft=False,
        begruendung="Invalidisierung wechselt den Zustand des BU-Graphen. Ob "
                    "der Wechsel neu rechnet, haengt an der noch offenen "
                    "BU-Zustandsbewertung",
    ),
    "REA": Heilungsregel(
        heilt=False, geprueft=False,
        begruendung="Reaktivierung wie INV — offen bis zur BU-Bewertung",
    ),
    "MIG": Heilungsregel(
        heilt=False, geprueft=True,
        begruendung="Der Migrationszugang ERZEUGT die Schicht; er kann sie "
                    "nicht im selben Vorgang aufloesen",
    ),
}


def heilt(vorfall: str) -> bool:
    """Ob dieser Geschaeftsvorfall die Korrekturschicht aufloest.

    Ein unbekannter Vorfall ist ein harter Fehler, keine stille
    Nicht-Heilung: Wer eine neue Vorfallart einfuehrt, muss ihre Wirkung
    auf die Schicht entscheiden.
    """
    regel = HEILUNG.get(vorfall)
    if regel is None:
        raise KorrekturschichtFehler(
            f"unbekannter Geschaeftsvorfall {vorfall!r} — seine Wirkung auf "
            "die Korrekturschicht ist zu entscheiden, bevor er gebucht wird "
            f"(bekannt: {sorted(HEILUNG)})"
        )
    return regel.heilt


def ungeprueft() -> List[str]:
    """Die Vorfaelle, deren Zuordnung fachlich noch nicht bestaetigt ist."""
    return sorted(k for k, r in HEILUNG.items() if not r.geprueft)


def absorbiere(parameter: Schichtparameter) -> Schichtparameter:
    """Klasse-A-Absorption: der Vertrag ist geheilt, die Schicht ist null.

    Der Verankerungsoperator mit $R = 0$ (9.8, dritter Aufrufkontext).
    Die uebrigen Parameter bleiben stehen, damit im Beleg nachvollziehbar
    ist, dass hier einmal eine Schicht war — eine geloeschte Schicht und
    eine nie vorhandene sind verschiedene Sachverhalte.
    """
    return dataclasses.replace(parameter, rho=0.0)
