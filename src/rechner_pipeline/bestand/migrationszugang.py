"""Migrationszugang: konstruktive Neuberechnung eines uebernommenen Vertrags.

Das ist der Vorgang, um den es in diesem System geht
(Grundsatzdokumentation Abschnitt 9): Ein Vertrag zieht mit seinen
URSPRUNGSPARAMETERN ins Zielsystem und wird dort neu gerechnet — nicht
mit uebernommenen Werten gefuehrt. Die am Verankerungszeitpunkt
verbleibende Differenz zwischen geliefertem und neu gerechnetem Wert
traegt eine eigene Bewertungsschicht.

**Warum das ein eigener Geschaeftsvorfall ist.** Bisher kannte das
Bewegungsjournal ``ZUG`` fuer den Neuzugang — einen frisch
abgeschlossenen Vertrag, der bei null beginnt. Ein uebernommener Vertrag
ist etwas anderes: Er bringt einen Bestand mit, einen
Verankerungszustand und ein Residuum. Ohne eigenes Ereignis erschiene er
im Bestandsbericht wie ein Neuzugang aus dem Nichts, und die Uebernahme
selbst waere nirgends belegt.

``MIG`` traegt deshalb als Betrag die **Veraenderung des
Deckungskapitals durch die Uebernahme** — also genau das Residuum. Das
ist dieselbe Groesse, die der Geschaeftsvorfalltest ohnehin prueft
(``dDK``), und sie macht die Uebernahme im Bericht sichtbar.

**Was hier NICHT passiert.** Die Historie des Quellsystems wird nicht
nachgefahren (9.14: der Rechenkern bleibt historienfrei). Eingang ist
allein der Zustandsschnappschuss — Ursprungsparameter,
Verankerungszeitpunkt, Zustand und der gelieferte Wert. Was das
abgebende Unternehmen in den Jahren davor gebucht hat, sieht dieses
Modul nicht und braucht es nicht.

Knoten: klv
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import pandas as pd

from rechner_pipeline.kern import ModelPoint
from rechner_pipeline.kern.korrekturschicht import (
    Formfunktion,
    Korrekturschicht,
    KorrekturschichtFehler,
    Schichtparameter,
    form_konstantes_fenster,
    form_proportional_zur_basis,
)
from rechner_pipeline.kern.rechenkern import Rechenkern
from rechner_pipeline.models.bestand import LEDGER_SPALTEN

#: Ereigniskennung des Migrationszugangs im Bewegungsjournal.
MIG = "MIG"

#: Betragsart des Ereignisses: die Veraenderung des Deckungskapitals
#: durch die Uebernahme. Sie ist das Residuum und damit die Groesse, die
#: der Geschaeftsvorfalltest prueft.
BETRAG_ART = "dDK_uebernahme"

#: Die Formfunktionen, die der Zugang kennt (Grundsatzdokumentation 9.9).
#: Weitere kommen dazu, wenn ein Tarifplan sie fordert — nicht auf Vorrat.
FORMEN = ("proportional_zur_basis", "konstantes_fenster")


class MigrationszugangFehler(ValueError):
    """Uebernahme nicht durchfuehrbar — fail-fast statt stiller Naeherung."""


@dataclass(frozen=True)
class Uebernahme:
    """Ein Vertrag, wie das abgebende Unternehmen ihn liefert.

    ``model_point`` sind die transformierten URSPRUNGSPARAMETER — der
    Vertrag, wie er einmal abgeschlossen wurde, nicht sein heutiger Wert.
    Genau darin liegt die Konstruktivitaet: Das Zielsystem rechnet daraus
    selbst, statt einen gelieferten Stand fortzuschreiben.

    ``monate_ta`` ist der Verankerungszeitpunkt in vollen Vertragsmonaten
    — der letzte exakte Rechenpunkt des Quellsystems (9.12). ``dk_ist``
    ist der dort gelieferte Wert.
    """

    police_id: int
    model_point: Mapping[str, Any]
    monate_ta: int
    dk_ist: float
    zustand: str = "aktiv"
    verweildauer: int = 0
    historientyp: str = "unbekannt"
    kohorte: str = "t_a"

    def __post_init__(self) -> None:
        if self.monate_ta < 0:
            raise MigrationszugangFehler(
                f"police {self.police_id}: monate_ta={self.monate_ta} liegt "
                "vor Vertragsbeginn"
            )
        if self.monate_ta % 12 != 0:
            # Offener Punkt, bewusst nicht halb geloest: Ein rechnender
            # Geschaeftsvorfall zwischen zwei Vertragsstichtagen setzt nach
            # 9.12 den Verankerungszeitpunkt — er ist aktueller als der
            # letzte Jahrestag. Die Korrekturschicht rechnet aber auf dem
            # Jahresgitter (9.6); ein unterjaehriger Verankerungspunkt
            # braucht entweder ein Monatsgitter oder eine Konvention, wie
            # das erste Rumpfjahr behandelt wird. Beides ist eine fachliche
            # Entscheidung, keine technische — bis sie getroffen ist, wird
            # der Fall abgelehnt statt still auf den Jahrestag gerundet.
            raise MigrationszugangFehler(
                f"police {self.police_id}: monate_ta={self.monate_ta} ist "
                f"unterjaehrig (Vertragsjahr {self.monate_ta // 12}, Monat "
                f"{self.monate_ta % 12}). Nach 9.12 setzt ein rechnender "
                "Geschaeftsvorfall den Verankerungszeitpunkt, auch zwischen "
                "zwei Stichtagen — die Korrekturschicht rechnet aber auf dem "
                "Jahresgitter. Wie das Rumpfjahr zu behandeln ist, ist offen "
                "und zu entscheiden, bevor solche Vertraege uebernommen werden"
            )


@dataclass(frozen=True)
class Zugangsergebnis:
    """Was die Uebernahme eines Vertrags hinterlaesst."""

    police_id: int
    monate_ta: int
    dk_ist: float
    dk_prosp: float
    residuum: float
    parameter: Optional[Schichtparameter]
    befund: Optional[str] = None

    @property
    def getragen(self) -> bool:
        """Ob eine Schicht die Differenz traegt (sonst steht ein Befund)."""
        return self.parameter is not None

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "police_id": self.police_id,
            "monate_ta": self.monate_ta,
            "dk_ist": self.dk_ist,
            "dk_prosp": self.dk_prosp,
            "residuum": self.residuum,
            "schicht": self.parameter.als_beleg() if self.parameter else None,
            "befund": self.befund,
        }


def _basisverlauf(kern: Rechenkern, ab_jahr: int) -> List[float]:
    """Prospektive Deckungsrueckstellung je Jahr ab dem Verankerungszeitpunkt."""
    n = kern.mp.n
    return [kern.verlaufszeile(a).drx_bpfl for a in range(ab_jahr, n + 1)]


def _forme(kennung: str, basis: Sequence[float], fenster: Optional[int]) -> Formfunktion:
    if kennung == "proportional_zur_basis":
        return form_proportional_zur_basis(basis)
    if kennung == "konstantes_fenster":
        if fenster is None:
            raise MigrationszugangFehler(
                "konstantes_fenster verlangt ein Amortisationsfenster"
            )
        return form_konstantes_fenster(len(basis), min(fenster, len(basis)))
    raise MigrationszugangFehler(
        f"unbekannte Formfunktion {kennung!r} — bekannt sind {list(FORMEN)}"
    )


def uebernehmen(
    vertraege: Sequence[Uebernahme],
    *,
    formfunktion: str = "proportional_zur_basis",
    fenster: Optional[int] = None,
    vererbend: Optional[Tuple[Tuple[str, str], ...]] = None,
    ausbuchungsgrenze: Optional[float] = None,
) -> List[Zugangsergebnis]:
    """Konstruktive Neuberechnung: rechnen, Residuum bilden, verankern.

    Je Vertrag drei Schritte, in dieser Reihenfolge (9.1, Zwei-Schritt-
    Prinzip mit anschliessender Verankerung):

    1. Aus den Ursprungsparametern den prospektiven Wert am
       Verankerungszeitpunkt rechnen — das Zielsystem rechnet selbst.
    2. Das Residuum bilden: geliefert minus prospektiv.
    3. Verankern: das Residuum auf die Restlaufzeit legen
       (:class:`~rechner_pipeline.kern.korrekturschicht.Korrekturschicht`).

    Ein Vertrag, dessen Verankerung scheitert, wird NICHT stillschweigend
    ohne Schicht uebernommen — er traegt einen Befund und muss vor der
    Uebernahme entschieden werden.
    """
    if not vertraege:
        raise MigrationszugangFehler(
            "leere Uebernahme — ein Zugang ohne Vertraege ist ein Aufruffehler"
        )
    ids = [v.police_id for v in vertraege]
    if len(ids) != len(set(ids)):
        doppelt = sorted({i for i in ids if ids.count(i) > 1})
        raise MigrationszugangFehler(
            f"doppelte police_id in der Uebernahme: {doppelt[:5]}"
        )

    ergebnisse: List[Zugangsergebnis] = []
    for v in vertraege:
        mp = ModelPoint(**dict(v.model_point))
        kern = Rechenkern(mp)
        jahr = v.monate_ta // 12
        if jahr > mp.n:
            raise MigrationszugangFehler(
                f"police {v.police_id}: Verankerungszeitpunkt liegt hinter "
                f"dem Vertragsende (n={mp.n})"
            )
        basis = _basisverlauf(kern, jahr)
        if jahr >= mp.n:
            # Verankerung genau am Ablauf: Es gibt keine Restlaufzeit, ueber
            # die etwas zu verteilen waere. Der Wert der Formfunktion an
            # diesem einen Punkt ist zwar positiv (die Ablaufleistung), aber
            # eine Schicht darauf haette keinen Zeitraum zum Abbauen — sie
            # waere im selben Moment faellig wie die Leistung selbst. Das ist
            # eine sofortige Ausbuchung und muss als solche behandelt werden.
            ergebnisse.append(
                Zugangsergebnis(
                    police_id=v.police_id, monate_ta=v.monate_ta,
                    dk_ist=float(v.dk_ist), dk_prosp=basis[0],
                    residuum=float(v.dk_ist) - basis[0], parameter=None,
                    befund=(
                        "Verankerung am Ablauf: keine Restlaufzeit, ueber die "
                        "das Residuum verteilt werden koennte — es ist sofort "
                        "ueber das Ergebnis auszubuchen und auszuweisen"
                    ),
                )
            )
            continue
        dk_prosp = basis[0]
        residuum = float(v.dk_ist) - dk_prosp

        bw = kern.produkt.bw
        f_vererbend = vererbend or ((bw.AKTIV, bw.TOT),)
        schicht = Korrekturschicht(bw.modell, f_vererbend)
        try:
            form = _forme(formfunktion, basis, fenster)
            parameter = schicht.verankere(
                form,
                mp.x + jahr,
                v.zustand if v.zustand in bw.modell.zustaende else bw.AKTIV,
                residuum,
                verweildauer=v.verweildauer,
                ausbuchungsgrenze=ausbuchungsgrenze,
                kohorte=v.kohorte,
            )
            befund = None
        except (KorrekturschichtFehler, MigrationszugangFehler) as exc:
            parameter, befund = None, f"{type(exc).__name__}: {exc}"

        ergebnisse.append(
            Zugangsergebnis(
                police_id=v.police_id,
                monate_ta=v.monate_ta,
                dk_ist=float(v.dk_ist),
                dk_prosp=dk_prosp,
                residuum=residuum,
                parameter=parameter,
                befund=befund,
            )
        )
    return ergebnisse


def zugangsjournal(
    ergebnisse: Sequence[Zugangsergebnis],
    stichtag: _dt.date,
    tarif_generation: str,
) -> pd.DataFrame:
    """Die ``MIG``-Zeilen fuers Bewegungsjournal (eine je uebernommenem Vertrag).

    Der Betrag ist das Residuum — die Veraenderung des Deckungskapitals
    durch die Uebernahme. Damit erscheint der Zugang im Bestandsbericht
    als das, was er ist, und nicht als Neuzugang aus dem Nichts.

    Vertraege mit Befund kommen NICHT ins Journal: Was nicht verankert
    werden konnte, ist nicht uebernommen.
    """
    zeilen = [
        {
            "police_id": int(e.police_id),
            "tarif_generation": tarif_generation,
            "ereignis": MIG,
            "vertragsjahr": e.monate_ta // 12,
            "status_date": pd.Timestamp(stichtag),
            "betrag_art": BETRAG_ART,
            "betrag": e.residuum,
        }
        for e in ergebnisse
        if e.getragen
    ]
    rahmen = pd.DataFrame(
        zeilen,
        columns=[n for n, _ in LEDGER_SPALTEN],
    )
    for name, dtype in LEDGER_SPALTEN:
        rahmen[name] = rahmen[name].astype(dtype)
    return rahmen


def zugangsbericht(ergebnisse: Sequence[Zugangsergebnis]) -> Dict[str, Any]:
    """Was die Uebernahme insgesamt ergeben hat — fuer Beleg und Bericht.

    Ausgewiesen werden ausschliesslich Verteilungsgroessen der Residuen
    und Zaehler, keine Bestandssumme: Dieselbe Regel wie im aktuariellen
    Test (9.15). Die Summe der Residuen ist hier allerdings eine echte
    Bilanzgroesse — sie ist der Betrag, den die Korrekturschicht
    insgesamt traegt, und gehoert in die Ueberleitung.
    """
    getragen = [e for e in ergebnisse if e.getragen]
    befunde = [e for e in ergebnisse if not e.getragen]
    betraege = sorted(abs(e.residuum) for e in getragen)
    return {
        "vertraege": len(ergebnisse),
        "uebernommen": len(getragen),
        "mit_befund": len(befunde),
        "summe_residuum": sum(e.residuum for e in getragen),
        "max_abs_residuum": betraege[-1] if betraege else 0.0,
        "befunde": [
            {"police_id": e.police_id, "befund": e.befund} for e in befunde
        ][:50],
    }


# --------------------------------------------------------------------------- #
# Rueckrechnung einer Alt-Absetzung (Zustandsextrakt per Ableitungsregel)
# --------------------------------------------------------------------------- #

#: Toleranz des Vorwaerts-Selbstchecks: die gelieferten Felder sind
#: centgerundet, die Rueckrechnung kann sie also hoechstens auf die
#: Rundung genau reproduzieren. Ein groesserer Rest heisst: falscher
#: Zweig, falsches Verfahren oder inkonsistente Lieferung.
ABLEITUNG_SELBSTCHECK_TOL = 0.011


@dataclass(frozen=True)
class AbgeleiteteAbsetzung:
    """Die aus dem Abzug zurueckgerechnete Alt-Absetzung eines Vertrags.

    ``vs_alt`` und ``anteil`` sind VERTRAGSPARAMETER, die die Lieferung
    nicht direkt traegt: Der Abzug fuehrt den Zustand NACH der Absetzung
    (ERLSUMME = neue Gesamtsumme, JBRUTTO = fortgefuehrter Beitrag). Mit
    dem dokumentierten Verfahren der Quelle (Aktuarielle Notiz 2026/04:
    Teilkuendigung) sind beide eindeutig bestimmbar, solange der Vertrag
    am Stichtag noch Beitrag zahlt — sonst ist das System unterbestimmt
    und die Parameter muessen nachgeliefert werden (kein Raten).

    ``selbstcheck_*`` sind die Vorwaertsprobe: :func:`reduziere` mit den
    abgeleiteten Parametern muss die gelieferten Felder auf die
    Centrundung genau reproduzieren.
    """

    vs_alt: float
    anteil: float
    jahr: int
    verfahren: str
    stoab_zweig: str
    selbstcheck_vs_neu: float
    selbstcheck_bjb_neu: float

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "vs_alt": self.vs_alt,
            "anteil": self.anteil,
            "jahr": self.jahr,
            "verfahren": self.verfahren,
            "stoab_zweig": self.stoab_zweig,
            "selbstcheck_vs_neu": self.selbstcheck_vs_neu,
            "selbstcheck_bjb_neu": self.selbstcheck_bjb_neu,
        }


def leite_absetzung_ab(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    jbrutto: float,
    verfahren: str,
) -> AbgeleiteteAbsetzung:
    """Ursprungssumme und fortgefuehrten Anteil einer Alt-Absetzung ableiten.

    Eingang sind die Felder des Modellpunkts OHNE belastbare
    Versicherungssumme (``sum_insured`` wird ignoriert), das
    Absetzungsjahr aus der GeVo-Metadatenliste und die gelieferten
    Felder ERLSUMME (neue Gesamtsumme) und JBRUTTO (fortgefuehrter
    Jahresbeitrag) des Abzugs.

    Herleitung: Alle Zielgroessen des Kerns sind je Einheit
    Versicherungssumme formuliert. Mit den Saetzen ``v = kVx_bpfl(j)``,
    ``vbfr = kVx_bfr(j)`` und der Beitragsrate ``Bxt`` gilt

        K := JBRUTTO / Bxt = f * VS                     (fortgefuehrter Teil)
        S - K = (DR - StoAb) * (1 - f) / vbfr           (umgewandelter Teil)

    und je Stornoabzugs-Zweig (Regelwerk des Tarifplans) wird die zweite
    Gleichung nach VS aufloesbar: im Satz-Zweig und bei StoAb = 0 linear,
    in den geklammerten Zweigen (Unter-/Obergrenze) quadratisch. Der
    Zweig wird nicht geraten: Jeder Kandidat muss das Regelwerk an
    seiner eigenen Loesung erfuellen, und die Vorwaertsprobe ueber
    :func:`reduziere` muss die gelieferten Felder treffen.
    """
    from rechner_pipeline.kern.beitragsreduktion import (
        VERFAHREN,
        BeitragsreduktionFehler,
        reduziere,
    )

    if verfahren not in VERFAHREN:
        raise MigrationszugangFehler(
            f"unbekanntes Verfahren {verfahren!r} — bekannt sind "
            f"{list(VERFAHREN)}"
        )
    if jbrutto <= 0.0:
        raise MigrationszugangFehler(
            "JBRUTTO <= 0: die Beitragszahlung ist am Stichtag beendet, "
            "der fortgefuehrte Anteil ist aus dem Abzug NICHT bestimmbar — "
            "f oder die Versicherungssumme vor der Absetzung nachliefern "
            "lassen, nicht raten"
        )
    if erlsumme <= 0.0:
        raise MigrationszugangFehler(f"ERLSUMME {erlsumme!r} unplausibel")

    einheit = ModelPoint(**{**dict(modellpunkt_felder), "sum_insured": 1.0})
    kern_einheit = Rechenkern(einheit)
    if not 0 < jahr < einheit.t:
        raise MigrationszugangFehler(
            f"Absetzungsjahr {jahr} liegt nicht in der Beitragszahlungs"
            f"dauer (0 < jahr < t = {einheit.t})"
        )
    zeile = kern_einheit.verlaufszeile(jahr)
    v, vbfr = zeile.vx_bpfl, zeile.vx_bfr
    bxt = kern_einheit.gross_premium_rate()
    if vbfr <= 0.0 or bxt <= 0.0:
        raise MigrationszugangFehler(
            f"Saetze unplausibel (kVx_bfr={vbfr!r}, Bxt={bxt!r})"
        )
    k_teil = jbrutto / bxt
    if erlsumme <= k_teil:
        raise MigrationszugangFehler(
            f"ERLSUMME {erlsumme} liegt nicht ueber dem fortgefuehrten "
            f"Teil {k_teil:.2f} — keine Absetzung ableitbar"
        )

    s_satz = einheit.stoab_satz
    flex_oder_null = (
        verfahren == "prospektiv"
        or kern_einheit.produkt.ist_flex_phase(jahr)
        or s_satz <= 0.0
    )

    kandidaten: List[Tuple[str, float]] = []
    if flex_oder_null:
        if v <= 0.0:
            raise MigrationszugangFehler(f"kVx_bpfl({jahr}) = {v!r} <= 0")
        kandidaten.append(
            ("flex_oder_null", k_teil + (erlsumme - k_teil) * vbfr / v))
    else:
        # Satz-Zweig: StoAb = s * VS * (1 - v), linear in VS.
        nenner = v - s_satz * (1.0 - v)
        if nenner > 0.0:
            vs = k_teil + (erlsumme - k_teil) * vbfr / nenner
            if einheit.stoab_min <= s_satz * vs * (1.0 - v) <= einheit.stoab_max:
                kandidaten.append(("satz", vs))
        # Geklammerte Zweige: StoAb konstant c, quadratisch in VS.
        for zweig, c in (("min", einheit.stoab_min),
                         ("max", einheit.stoab_max)):
            # v*VS^2 - (c + K*v + (S-K)*vbfr)*VS + c*K = 0
            b = c + k_teil * v + (erlsumme - k_teil) * vbfr
            disk = b * b - 4.0 * v * c * k_teil
            if disk < 0.0 or v <= 0.0:
                continue
            for wurzel in ((b + math.sqrt(disk)) / (2.0 * v),
                           (b - math.sqrt(disk)) / (2.0 * v)):
                if wurzel <= k_teil:
                    continue
                roh = s_satz * wurzel * (1.0 - v)
                passt = (roh <= c) if zweig == "min" else (roh >= c)
                if passt:
                    kandidaten.append((zweig, wurzel))

    fehler: List[str] = []
    for zweig, vs_alt in kandidaten:
        anteil = k_teil / vs_alt
        if not 0.0 < anteil < 1.0:
            fehler.append(f"{zweig}: Anteil {anteil:.6f} ausserhalb (0, 1)")
            continue
        try:
            probe = reduziere(
                Rechenkern(ModelPoint(**{
                    **dict(modellpunkt_felder), "sum_insured": vs_alt})),
                jahr, anteil, verfahren=verfahren)
        except BeitragsreduktionFehler as exc:
            fehler.append(f"{zweig}: {exc}")
            continue
        if (abs(probe.vs_neu - erlsumme) <= ABLEITUNG_SELBSTCHECK_TOL
                and abs(probe.bjb_neu - jbrutto) <= ABLEITUNG_SELBSTCHECK_TOL):
            return AbgeleiteteAbsetzung(
                vs_alt=vs_alt, anteil=anteil, jahr=jahr,
                verfahren=verfahren, stoab_zweig=zweig,
                selbstcheck_vs_neu=probe.vs_neu,
                selbstcheck_bjb_neu=probe.bjb_neu,
            )
        fehler.append(
            f"{zweig}: Vorwaertsprobe daneben (vs_neu {probe.vs_neu:.4f} "
            f"vs. {erlsumme}, bjb_neu {probe.bjb_neu:.4f} vs. {jbrutto})")

    raise MigrationszugangFehler(
        "Alt-Absetzung nicht ableitbar — kein Stornoabzugs-Zweig "
        "reproduziert die gelieferten Felder ("
        + ("; ".join(fehler) if fehler else "keine Kandidaten")
        + "). Verfahren und Lieferung klaeren, nicht raten."
    )


@dataclass(frozen=True)
class AbgeleiteteErhoehung:
    """Die aus dem Abzug zurueckgerechnete Alt-Dynamikerhoehung.

    Der Abzug fuehrt die GESAMTsumme nach der Erhoehung; fuer die
    konstruktive Rechnung braucht das Zielsystem die Zerlegung in
    Grundvertrag und Scheibe (Tarifwerk: eigener Modellpunkt je Scheibe
    mit versetzten Dauern und ohne gamma1). Bei GENAU EINER Erhoehung
    sind ERLSUMME und JBRUTTO zwei lineare Gleichungen in
    (Grundsumme, Erhoehungssumme) — die Beitragsraten beider Teile sind
    bekannte, verschiedene Saetze. Ohne laufenden Beitrag ist das System
    unterbestimmt (nachliefern lassen, nicht raten).
    """

    grundsumme: float
    erhoehungssumme: float
    jahr: int

    #: REICHWEITEN-WARNUNG (Hinweis der Zulieferung, 2026-08-28): Diese
    #: Ableitung traegt NUR den Fall genau EINER Erhoehung je Vertrag.
    #: Bei n Erhoehungen stehen n+1 Unbekannte zwei gelieferten Groessen
    #: gegenueber — ab der zweiten Erhoehung ist das System dauerhaft
    #: unterbestimmt, nicht nur in Randfaellen. Die Ableitung ist deshalb
    #: eine FALL-Ableitungsregel (Migrationskonzept Kap. 4), nicht die
    #: Grundlage der Uebernahme; der allgemeine Mechanismus ist der
    #: Migrationszugang ueber das gelieferte Deckungskapital als Anker
    #: plus Korrekturschicht (Grundsatzdokumentation Abschnitt 9).

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "grundsumme": self.grundsumme,
            "erhoehungssumme": self.erhoehungssumme,
            "jahr": self.jahr,
        }


def leite_erhoehung_ab(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    jbrutto: float,
) -> AbgeleiteteErhoehung:
    """Grund- und Erhoehungssumme einer Alt-Dynamik ableiten.

    Loest das lineare System

        S_g + S_s               = ERLSUMME
        S_g * B_g + S_s * B_s   = JBRUTTO

    mit den Beitragsraten des Grundvertrags (``B_g``) und der Scheibe
    (``B_s``, Modellpunkt mit versetzten Dauern und gamma1 = 0 nach der
    Tarifwerk-Regel). Beide zahlen bis zum SELBEN Kalenderzeitpunkt
    (t bzw. t - jahr ab Erhoehung) — solange der Vertrag am Stichtag
    Beitrag zahlt, enthaelt JBRUTTO beide Teile.

    Reichweite: siehe Warnung an :class:`AbgeleiteteErhoehung` — genau
    EINE Erhoehung je Vertrag, sonst dauerhaft unterbestimmt.
    """
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe

    if jbrutto <= 0.0:
        raise MigrationszugangFehler(
            "JBRUTTO <= 0: die Beitragszahlung ist am Stichtag beendet, "
            "die Zerlegung in Grund- und Erhoehungssumme ist aus dem "
            "Abzug NICHT bestimmbar — Erhoehungs- oder Grundsumme "
            "nachliefern lassen, nicht raten"
        )
    if erlsumme <= 0.0:
        raise MigrationszugangFehler(f"ERLSUMME {erlsumme!r} unplausibel")

    einheit = ModelPoint(**{**dict(modellpunkt_felder), "sum_insured": 1.0})
    if not 0 < jahr < einheit.t:
        raise MigrationszugangFehler(
            f"Erhoehungsjahr {jahr} liegt nicht in der Beitragszahlungs"
            f"dauer (0 < jahr < t = {einheit.t})"
        )
    grund_rate = Rechenkern(einheit).gross_premium_rate()
    scheiben_rate = Rechenkern(
        erhoehungs_scheibe(einheit, jahr, 1.0)).gross_premium_rate()
    if abs(grund_rate - scheiben_rate) < 1e-12:
        raise MigrationszugangFehler(
            "Beitragsraten von Grundvertrag und Scheibe sind gleich — "
            "die Zerlegung ist nicht bestimmbar"
        )
    grundsumme = (jbrutto - erlsumme * scheiben_rate) / (
        grund_rate - scheiben_rate)
    erhoehungssumme = erlsumme - grundsumme
    if grundsumme <= 0.0 or erhoehungssumme <= 0.0:
        raise MigrationszugangFehler(
            f"Zerlegung unplausibel (Grundsumme {grundsumme:.2f}, "
            f"Erhoehungssumme {erhoehungssumme:.2f}) — Lieferung und "
            "Erhoehungsjahr klaeren"
        )
    return AbgeleiteteErhoehung(
        grundsumme=grundsumme, erhoehungssumme=erhoehungssumme, jahr=jahr)


# --------------------------------------------------------------------------- #
# Geschaeftsvorfall-Metadaten der Vorgeschichte (Grundsatzdokumentation 9.14)
# --------------------------------------------------------------------------- #

#: Vorfaelle, die im Quellsystem eine Neuberechnung ausgeloest haben und
#: deshalb einen Rechenpunkt setzen (9.12: t_a ist das Maximum aus letztem
#: Vertragsstichtag und letztem RECHNENDEM Geschaeftsvorfall). Ein Storno
#: oder Tod beendet den Vertrag und kommt in einer Uebernahme nicht vor;
#: eine Erhoehung dagegen rechnet.
RECHNENDE_VORFAELLE = frozenset({"ERH", "PEX", "RED", "ZUZ", "VERL"})


@dataclass(frozen=True)
class Vorgang:
    """Ein Geschaeftsvorfall der Vorgeschichte — Zeitpunkt und Art, KEIN Wert.

    Das ist die Trennlinie aus 9.14: Die Vollhistorie bleibt beim
    abgebenden Unternehmen, die *Metadaten* kommen mit. Sie tragen keinen
    Betrag, weil der Rechenkern sie nie sehen darf — er wuerde sonst
    rechnen, was er konstruktiv selbst ermitteln soll.

    Wozu sie dann dienen: den Verankerungszeitpunkt zu bestimmen, die
    Residuum-Verteilung nach Historientyp zu clustern und Ausreisser
    erklaerbar zu machen. Ohne sie ist die aktuarielle Abnahme laut 9.14
    nicht durchfuehrbar — sie ist Abnahmevoraussetzung, nicht Komfort.
    """

    police_id: int
    art: str
    monate_seit_beginn: int

    def __post_init__(self) -> None:
        if self.monate_seit_beginn < 0:
            raise MigrationszugangFehler(
                f"police {self.police_id}: Vorgang vor Vertragsbeginn "
                f"({self.monate_seit_beginn} Monate)"
            )

    @property
    def rechnet(self) -> bool:
        return self.art in RECHNENDE_VORFAELLE


def verankerungszeitpunkt(
    vorgeschichte: Sequence[Vorgang], monate_am_stichtag: int
) -> int:
    """$t_a = \\max(\\text{letzter Vertragsstichtag}, \\text{letzter rechnender Vorfall})$.

    Die Konvention aus 9.12, und zugleich die Antwort auf die Frage, was
    "letzte technische Aenderung" heisst: Faellt ein rechnender Vorfall
    NICHT auf den Vertragsstichtag, gilt sein Datum — es ist aktueller.

    Der zurueckgegebene Wert ist immer ein Rechenpunkt: Der letzte
    Vertragsstichtag ist per Definition einer, und ein rechnender Vorfall
    setzt selbst einen.
    """
    letzter_stichtag = (monate_am_stichtag // 12) * 12
    rechnende = [v.monate_seit_beginn for v in vorgeschichte if v.rechnet]
    if not rechnende:
        return letzter_stichtag
    letzter_vorfall = max(rechnende)
    if letzter_vorfall > monate_am_stichtag:
        raise MigrationszugangFehler(
            f"Vorgang {letzter_vorfall} Monate nach Beginn liegt hinter dem "
            f"Stichtag ({monate_am_stichtag} Monate) — die Vorgeschichte "
            "gehoert vor die Uebernahme"
        )
    return max(letzter_stichtag, letzter_vorfall)


def historientyp(vorgeschichte: Sequence[Vorgang]) -> str:
    """Cluster fuer die Verteilungsauswertung (9.12, Lieferobjekt 2).

    Grob und absichtlich so: Die Cluster sollen erklaeren, WARUM Residuen
    auseinanderlaufen, nicht jeden Vertrag einzeln beschreiben. Ein
    feineres Raster gehoert in den Tarifplan, wenn ein Bestand es
    verlangt.
    """
    arten = {v.art for v in vorgeschichte}
    if not arten:
        return "ohne_vorgeschichte"
    if "PEX" in arten:
        return "beitragsfrei"
    if "RED" in arten:
        return "reduziert"
    if "ERH" in arten:
        return "dynamik"
    return "sonstige"


def pruefe_metadatenliste(vorgeschichte: Sequence[Vorgang]) -> List[str]:
    """Dass die Liste wirklich nur Metadaten traegt — kein Betrag.

    Ein Beleg dafuer, dass die Trennung aus 9.14 eingehalten ist: Kaeme
    hier ein Wert mit, koennte er in die Bewertung sickern, und die
    konstruktive Neuberechnung waere keine mehr.
    """
    befunde: List[str] = []
    for v in vorgeschichte:
        for feld in ("betrag", "wert", "dk", "reserve"):
            if hasattr(v, feld):
                befunde.append(
                    f"police {v.police_id}: Metadatensatz traegt {feld!r} — "
                    "die Vorgeschichte liefert Zeitpunkte, keine Werte (9.14)"
                )
    return befunde
