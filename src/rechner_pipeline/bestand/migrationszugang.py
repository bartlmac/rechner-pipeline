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
import itertools
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
    #: Prospektiver Wert am t_a, EXTERN gerechnet — fuer Vertraege,
    #: deren Welt mehr ist als der eine Modellpunkt (Anfangszustaende:
    #: Erhoehungsscheiben, Beitragsfreistellung, Herabsetzung). Ohne
    #: ihn rechnet ``uebernehmen`` die Stamm-Welt selbst — fuer
    #: Zustands-Vertraege ergaebe das ein PHANTOM-Residuum aus der
    #: Weltendifferenz statt des echten Rests (zweiter Baldrian-Lauf:
    #: rho bis 0,04 bei Serien-Policen). Der Aufrufer rechnet auf
    #: DERSELBEN Basis (drx_bpfl) und DERSELBEN Zustands-Welt, auf der
    #: auch die Pruefstrecke bewertet.
    dk_prosp_extern: Optional[float] = None

    def __post_init__(self) -> None:
        if self.monate_ta < 0:
            raise MigrationszugangFehler(
                f"police {self.police_id}: monate_ta={self.monate_ta} liegt "
                "vor Vertragsbeginn"
            )
        # Unterjaehrige Verankerung ist seit dem 9.6-Nachtrag
        # (Rumpfjahr-Konvention, 2026-08-31) zulaessig: Das Gitter beginnt
        # am Jahrestag davor, das erste Gitterjahr traegt den
        # Einheitsstrom pro rata, Werte am und nach t_a entstehen durch
        # dieselbe lineare Monatsmischung wie ueberall im Kern. Die alte
        # Ablehnung ("bis die Konvention entschieden ist") ist damit
        # gegenstandslos.


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
    """Prospektive Deckungsrueckstellung je ZAHLUNGSJAHR der Schicht.

    Zahlungsjahre sind ``ab_jahr .. n-1`` — das Ablaufjahr ``n`` traegt
    KEINE Amortisations-Zahlung: Am Ablauf zahlt der Vertrag die
    garantierte Erlebensfallsumme, eine Fuehrungs-Korrektur hat dort
    nichts mehr zu verteilen (Terminalbedingung V_korr(n) = 0,
    Grundsatzdokumentation 9.7). Mit einem Gewicht auch im Ablaufjahr
    stand die Schicht am Ablauf noch auf rho x Basis(n) — im zweiten
    Baldrian-Lauf als A-M2-Befund gefunden (Police 7000586:
    kVx_MRV(n) um exakt rho x Erlebensfallsumme ueber der
    Ablaufleistung).
    """
    n = kern.mp.n
    return [kern.verlaufszeile(a).drx_bpfl for a in range(ab_jahr, n)]


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
        if jahr >= mp.n:
            # Verankerung genau am Ablauf: Es gibt keine Restlaufzeit, ueber
            # die etwas zu verteilen waere. Der prospektive Wert an diesem
            # einen Punkt ist zwar positiv (die Ablaufleistung), aber
            # eine Schicht darauf haette keinen Zeitraum zum Abbauen — sie
            # waere im selben Moment faellig wie die Leistung selbst. Das ist
            # eine sofortige Ausbuchung und muss als solche behandelt werden.
            # Der Ausbuchungswert ist der Wert der GERECHNETEN Welt:
            # bei Zustands-Welten der vom Aufrufer gerechnete
            # Prospektivwert (dk_prosp_extern), sonst die
            # Ablaufleistung des Stamm-Modellpunkts.
            dk_ablauf = (float(v.dk_prosp_extern)
                         if v.dk_prosp_extern is not None
                         else kern.verlaufszeile(mp.n).drx_bpfl)
            ergebnisse.append(
                Zugangsergebnis(
                    police_id=v.police_id, monate_ta=v.monate_ta,
                    dk_ist=float(v.dk_ist), dk_prosp=dk_ablauf,
                    residuum=float(v.dk_ist) - dk_ablauf, parameter=None,
                    befund=(
                        "Verankerung am Ablauf: keine Restlaufzeit, ueber die "
                        "das Residuum verteilt werden koennte — es ist sofort "
                        "ueber das Ergebnis auszubuchen und auszuweisen"
                    ),
                )
            )
            continue
        # Der prospektive Wert AM t_a kommt von den STUETZSTELLEN des
        # Kernverlaufs (bis einschliesslich n) — die Form-Basis dagegen
        # traegt nur ZAHLUNGSJAHRE (bis n-1, Terminalbedingung); die
        # beiden teilen sich seit dem A-M2-Befund des zweiten Laufs
        # bewusst keine Liste mehr.
        basis = _basisverlauf(kern, jahr)
        rumpf = v.monate_ta % 12
        if v.dk_prosp_extern is not None:
            # Zustands-Welten (Scheiben, Beitragsfreistellung,
            # Herabsetzung) rechnet der Aufrufer — siehe Feld-Docstring.
            dk_prosp = float(v.dk_prosp_extern)
        elif rumpf == 0:
            dk_prosp = kern.verlaufszeile(jahr).drx_bpfl
        else:
            # Prospektiver Wert AM unterjaehrigen t_a: lineare Mischung der
            # Jahresraender — die Monatskonvention des Kerns (9.14), keine
            # eigene Uhr der Schicht.
            theta = rumpf / 12.0
            dk_prosp = ((1.0 - theta) * kern.verlaufszeile(jahr).drx_bpfl
                        + theta * kern.verlaufszeile(jahr + 1).drx_bpfl)
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
                # Select-Kappung ist Aufrufer-Pflicht (Zustandsmodell-
                # Vertrag): im homogenen Modell (max_dauer 0) startet
                # jede Verweildauer bei 0; das VERTRAGSMERKMAL
                # verweildauer_ta bleibt ungekappt in der Tabelle.
                verweildauer=min(v.verweildauer, bw.modell.max_dauer),
                rumpfmonate=rumpf,
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
            # Das Residuum ist die Differenz zwischen geliefertem Stand
            # und eigener Rechnung -- also selbst eine Rechnung.
            "betrag_herkunft": "gerechnet",
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

#: Kleinste Absetzung, die aus cent-gerundeten Lieferfeldern noch
#: IDENTIFIZIERBAR ist. Eine "Loesung" mit kleinerem abgesetzten Betrag
#: ist mathematisch konsistent und fachlich leer: Sie presst das
#: Rundungsrauschen der Lieferung in einen Anteil nahe 1 (zweiter
#: Baldrian-Lauf: fuenf Policen mit f zwischen 0.9999893 und 0.9999995,
#: abgesetzte Betraege 3 bis 37 Cent) — siehe
#: :func:`_pruefe_wirksame_absetzung`.
ABSETZUNG_MINDESTBETRAG = 1.0


def _pruefe_wirksame_absetzung(vs_alt: float, anteil: float) -> None:
    """Degenerations-Wache der Absetzungs-Rueckwege (2. Lauf, 2026-09-01).

    Liegt der abgesetzte Betrag unter der Aufloesung cent-gerundeter
    Lieferfelder, sind die gelieferten Werte OHNE wirksame Absetzung
    erklaerbar — der Vorfall in der Historie und die Wertlage
    widersprechen sich. Das ist ein benannter Befund, kein Zustand: Als
    Herabsetzung gefuehrt lief im zweiten Lauf jede
    Kandidaten-Plausibilitaet ins Leere (Korridor um eine faktisch
    ungeteilte Welt).
    """
    betrag = vs_alt * (1.0 - anteil)
    if betrag < ABSETZUNG_MINDESTBETRAG:
        raise MigrationszugangFehler(
            f"abgeleitete Absetzung betraegt nur {betrag:.2f} EUR "
            f"(fortgefuehrter Anteil {anteil:.7f}) — unterhalb der "
            "Aufloesung cent-gerundeter Lieferfelder. Die gelieferten "
            "Werte sind ohne wirksame Absetzung erklaerbar; die "
            "Vorfallshistorie widerspricht der Wertlage. Nicht als "
            "Herabsetzung fuehren — den Widerspruch bei der Quelle "
            "klaeren (Vorfalls-/Feldsemantik) oder den Anteil "
            "nachliefern lassen."
        )


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
            vs_alt, anteil, probe = _verfeinere_absetzung(
                modellpunkt_felder, jahr=jahr, erlsumme=erlsumme,
                jbrutto=jbrutto, verfahren=verfahren,
                roh_anteil=anteil, roh_vs=vs_alt, roh_probe=probe)
            _pruefe_wirksame_absetzung(vs_alt, anteil)
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


def leite_pex_ursprungssumme_ab(
    modellpunkt_felder: Mapping[str, Any],
    *,
    pex_jahr: int,
    vs_bfr: float,
) -> float:
    """Ursprungssumme eines beitragsfrei UEBERNOMMENEN Vertrags ableiten.

    Der Abzug fuehrt bei diesen Vertraegen als Versicherungssumme die
    BEITRAGSFREIE Summe — den Zustand nach der Freistellung. Der
    Zielkern rechnet aber aus der Ursprungssumme: Er bildet
    ``VS_bfr = VS * v_bfr(a0)`` selbst. Ohne Umkehrung wuerde die
    gelieferte beitragsfreie Summe ein zweites Mal umgewandelt und der
    Vertrag um den Faktor ``v_bfr`` zu klein bewertet.

    Die Umkehrung ist exakt: Alle Zielgroessen sind homogen in der
    Versicherungssumme, ``v_bfr(a0)`` je Einheit ist der gesuchte
    Faktor. Nach dem Ende der Beitragszahlungsdauer ist er eins — dort
    IST die gelieferte Summe die Ursprungssumme.

    Fuer eine SERIE (Grund + Erhoehungsscheiben) mit terminalem PEX
    liefert die Inversion durch den Grund-Faktor eine
    AEQUIVALENZGROESSE, nicht die historische Bausteinsumme: Die
    Umwandlungsfaktoren der Bausteine sind verschieden (versetzte
    Zillmer-Fenster), die historische Zerlegung ist aus der
    Ein-Punkt-Inversion nicht rekonstruierbar. Tragfaehig ist sie
    trotzdem, weil nach terminalem PEX jede erreichbare Folgegroesse
    nur an der beitragsfreien Gesamtsumme haengt, die die Inversion
    exakt reproduziert.
    """
    einheit = ModelPoint(**{**dict(modellpunkt_felder), "sum_insured": 1.0})
    if pex_jahr <= 0 or pex_jahr > einheit.n:
        raise MigrationszugangFehler(
            f"Beitragsfreistellungsjahr {pex_jahr} liegt nicht in der "
            f"Laufzeit (0 < jahr <= n = {einheit.n})"
        )
    if vs_bfr <= 0.0:
        raise MigrationszugangFehler(
            f"gelieferte beitragsfreie Summe {vs_bfr!r} unplausibel")
    faktor = Rechenkern(einheit).beitragsfreie_summe(pex_jahr)
    if faktor <= 0.0:
        raise MigrationszugangFehler(
            f"beitragsfreier Umwandlungsfaktor in Jahr {pex_jahr} ist "
            f"{faktor!r} — eine Umkehrung ist dort nicht definiert"
        )
    return vs_bfr / faktor


def kalibriere_absetzung_aus_dk(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    dk_ist: float,
    monate_dk: int,
    verfahren: str,
    toleranz: float = 1e-9,
) -> Tuple[float, float]:
    """Anteil und Ursprungssumme aus dem GELIEFERTEN Wert kalibrieren.

    Der Rueckfallweg fuer Absetzungen, deren Beitragsgleichung entfaellt
    (Beitragszahlung am Stichtag beendet) und fuer die kein Anteil
    nachgeliefert wurde. Statt der zweiten Gleichung aus dem Jahresbeitrag
    tritt der gelieferte Wert am Verankerungszeitpunkt: Zu jedem Anteil
    folgt die Ursprungssumme exakt aus der Erlebensfallsumme, und der
    daraus gerechnete Bestandswert ist monoton im Anteil — Bisektion
    findet den Anteil, der den gelieferten Wert trifft.

    **Der Preis ist Zirkularitaet, und sie ist auszuweisen:** Der
    Vergleich am Verankerungszeitpunkt ist fuer diese Vertraege danach
    konstruktionsbedingt erfuellt und traegt keine Aussage mehr. Aussage
    tragen die Punkte DANEBEN — die Fortschreibung, der Verlauf, die
    Geschaeftsvorfaelle. Das ist dieselbe Kohorten-Logik wie beim
    Migrationszugang (Grundsatzdokumentation 9.12): Wer den Anker
    setzt, misst nicht mehr am Anker.
    """
    def wert(anteil: float) -> Tuple[float, float]:
        vs = leite_ursprungssumme_ab(
            modellpunkt_felder, jahr=jahr, erlsumme=erlsumme,
            anteil=anteil, verfahren=verfahren)
        from rechner_pipeline.kern.beitragsreduktion import ReduzierterVertrag

        kern = Rechenkern(ModelPoint(**{**dict(modellpunkt_felder),
                                        "sum_insured": vs}))
        rv = ReduzierterVertrag.nach(kern, jahr, anteil, verfahren=verfahren)
        return vs, rv.monatsreserve(monate_dk).vx_mrv

    unten, oben = 1e-6, 1.0 - 1e-6
    try:
        _, w_unten = wert(unten)
        _, w_oben = wert(oben)
    except (MigrationszugangFehler, ValueError) as exc:
        raise MigrationszugangFehler(
            f"Kalibrierung nicht durchfuehrbar: {exc}") from exc
    if not (min(w_unten, w_oben) - 0.02 <= dk_ist <= max(w_unten, w_oben) + 0.02):
        raise MigrationszugangFehler(
            f"gelieferter Wert {dk_ist} liegt ausserhalb des erreichbaren "
            f"Bereichs [{min(w_unten, w_oben):.2f}, {max(w_unten, w_oben):.2f}] "
            "— der Anteil ist damit nicht kalibrierbar"
        )
    steigend = w_oben > w_unten
    for _ in range(200):
        mitte = 0.5 * (unten + oben)
        _, w = wert(mitte)
        if abs(w - dk_ist) <= toleranz * max(1.0, abs(dk_ist)):
            break
        if (w < dk_ist) == steigend:
            unten = mitte
        else:
            oben = mitte
    anteil = 0.5 * (unten + oben)
    vs, _ = wert(anteil)
    _pruefe_wirksame_absetzung(vs, anteil)
    return vs, anteil


def leite_ursprungssumme_ab(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    anteil: float,
    verfahren: str,
) -> float:
    """Ursprungssumme einer Alt-Absetzung bei BEKANNTEM Anteil ableiten.

    Der Fall der Nachlieferung: Der fortgefuehrte Bruchteil ``f`` ist
    geliefert (Zustandsparameter), die Versicherungssumme vor der
    Absetzung nicht — und die Beitragsgleichung faellt weg, weil die
    Beitragszahlungsdauer abgelaufen ist. Mit bekanntem ``f`` ist die
    ERLSUMME-Gleichung in jedem Stornoabzugs-Zweig LINEAR in der
    Ursprungssumme; der Zweig wird wie in :func:`leite_absetzung_ab`
    am eigenen Kandidaten geprueft und die Vorwaertsprobe muss die
    gelieferte Summe auf die Centrundung treffen.
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
    if not 0.0 < anteil < 1.0:
        raise MigrationszugangFehler(
            f"Anteil {anteil!r} liegt nicht in (0, 1) — er ist der "
            "fortgefuehrte Bruchteil des Beitrags"
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
    if vbfr <= 0.0:
        raise MigrationszugangFehler(f"kVx_bfr({jahr}) = {vbfr!r} <= 0")
    frei = 1.0 - anteil
    s_satz = einheit.stoab_satz
    flex_oder_null = (
        verfahren == "prospektiv"
        or kern_einheit.produkt.ist_flex_phase(jahr)
        or s_satz <= 0.0
    )

    kandidaten: List[Tuple[str, float]] = []
    if flex_oder_null:
        faktor = anteil + v * frei / vbfr
        kandidaten.append(("flex_oder_null", erlsumme / faktor))
    else:
        # Satz-Zweig: ERLSUMME = VS * (f + (v - s(1-v)) * (1-f) / vbfr)
        faktor = anteil + (v - s_satz * (1.0 - v)) * frei / vbfr
        if faktor > 0.0:
            vs = erlsumme / faktor
            if einheit.stoab_min <= s_satz * vs * (1.0 - v) <= einheit.stoab_max:
                kandidaten.append(("satz", vs))
        # Klammerzweige: ERLSUMME = VS * (f + v(1-f)/vbfr) - c(1-f)/vbfr
        for zweig, c in (("min", einheit.stoab_min),
                         ("max", einheit.stoab_max)):
            faktor = anteil + v * frei / vbfr
            vs = (erlsumme + c * frei / vbfr) / faktor
            roh = s_satz * vs * (1.0 - v)
            passt = (roh <= c) if zweig == "min" else (roh >= c)
            if passt:
                kandidaten.append((zweig, vs))

    fehler: List[str] = []
    for zweig, vs_alt in kandidaten:
        if vs_alt <= 0.0:
            fehler.append(f"{zweig}: Ursprungssumme {vs_alt:.2f} <= 0")
            continue
        try:
            probe = reduziere(
                Rechenkern(ModelPoint(**{
                    **dict(modellpunkt_felder), "sum_insured": vs_alt})),
                jahr, anteil, verfahren=verfahren)
        except BeitragsreduktionFehler as exc:
            fehler.append(f"{zweig}: {exc}")
            continue
        if abs(probe.vs_neu - erlsumme) <= ABLEITUNG_SELBSTCHECK_TOL:
            return vs_alt
        fehler.append(
            f"{zweig}: Vorwaertsprobe daneben (vs_neu {probe.vs_neu:.4f} "
            f"vs. {erlsumme})")
    raise MigrationszugangFehler(
        "Ursprungssumme nicht ableitbar — kein Stornoabzugs-Zweig "
        "reproduziert die gelieferte Summe ("
        + ("; ".join(fehler) if fehler else "keine Kandidaten") + ")"
    )


def _verfeinere_absetzung(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    jbrutto: float,
    verfahren: str,
    roh_anteil: float,
    roh_vs: float,
    roh_probe: Any,
) -> Tuple[float, float, Any]:
    """Den rohen Anteil auf einen glatten Vertragsparameter schaerfen.

    Beide Lieferfelder sind centgerundet; die Rueckrechnung nutzt beide
    zugleich, ihre Rundungsfehler verstaerken sich also in Anteil UND
    Ursprungssumme. Ein fortgefuehrter Beitragsanteil ist aber ein
    VEREINBARTER Parameter und praktisch immer glatt (die Lieferung
    zeigt 0,4 / 0,5 / 0,6 / 0,75).

    Deshalb wird nicht gerundet und gehofft, sondern VERIFIZIERT: Zu
    jedem glatten Kandidaten in der Naehe des rohen Werts wird die
    Ursprungssumme exakt aus der ERLSUMME bestimmt (eine Gleichung, eine
    Unbekannte) und der daraus folgende Jahresbeitrag gegen den
    gelieferten gehalten — ein Feld, das in diese Bestimmung NICHT
    eingeht. Genommen wird der GROEBSTE Kandidat, der beide Felder
    centgenau trifft; trifft keiner, bleibt es beim rohen Wert.
    """
    from rechner_pipeline.kern.beitragsreduktion import (
        BeitragsreduktionFehler,
        reduziere,
    )

    for stellen in (2, 3, 4):
        kandidat = round(roh_anteil, stellen)
        if not 0.0 < kandidat < 1.0 or kandidat == roh_anteil:
            continue
        try:
            vs_kandidat = leite_ursprungssumme_ab(
                modellpunkt_felder, jahr=jahr, erlsumme=erlsumme,
                anteil=kandidat, verfahren=verfahren)
            probe = reduziere(
                Rechenkern(ModelPoint(**{**dict(modellpunkt_felder),
                                         "sum_insured": vs_kandidat})),
                jahr, kandidat, verfahren=verfahren)
        except (MigrationszugangFehler, BeitragsreduktionFehler):
            continue
        if (abs(probe.vs_neu - erlsumme) <= ABLEITUNG_SELBSTCHECK_TOL
                and abs(probe.bjb_neu - jbrutto) <= ABLEITUNG_SELBSTCHECK_TOL):
            return vs_kandidat, kandidat, probe
    return roh_vs, roh_anteil, roh_probe


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


def leite_erhoehung_aus_satz_ab(
    *,
    jahr: int,
    erlsumme: float,
    satz: float,
) -> AbgeleiteteErhoehung:
    """Zerlegung aus dem BELEGTEN Dynamiksatz — ohne Beitragsgleichung.

    Das Tarifwerk bildet die neue Scheibe als ``S' = e * S^ges`` (klv.md,
    GeVo-Katalog ERH). Bei GENAU EINER Erhoehung folgt daraus
    ``ERLSUMME = S_grund * (1 + e)``, also eine Zerlegung ohne den
    Jahresbeitrag — sie traegt deshalb auch Vertraege, deren
    Beitragszahlung am Stichtag beendet ist.

    Der Satz ``e`` wird NICHT geraten: Er ist eine Eigenschaft der
    Lieferung und gehoert belegt (``pruefe_erhoehungssatz`` haelt einen
    Kandidaten gegen die gelieferten Jahresbeitraege) sowie in den
    Meldungs-Korridor eingeordnet. Ohne Beleg gilt die
    Beitragszerlegung :func:`leite_erhoehung_ab`.
    """
    if not 0.0 < satz < 1.0:
        raise MigrationszugangFehler(
            f"Erhoehungssatz {satz!r} liegt nicht in (0, 1)")
    if erlsumme <= 0.0:
        raise MigrationszugangFehler(f"ERLSUMME {erlsumme!r} unplausibel")
    grundsumme = erlsumme / (1.0 + satz)
    # Verifizierte Glaettung: Versicherungssummen werden auf ganze Euro
    # gefuehrt. Der gerundete Wert wird NICHT einfach genommen, sondern
    # muss die gelieferte Gesamtsumme centgenau reproduzieren — sonst
    # bleibt der rohe Quotient. Ohne diesen Schritt traegt der
    # Rundungsrest der Lieferung bis in die Reserve (gemessen: ein
    # hundertstel Cent ueber der Abnahmegrenze).
    glatt = round(grundsumme)
    if glatt > 0 and abs(glatt * (1.0 + satz) - erlsumme) <= 0.005:
        grundsumme = float(glatt)
    return AbgeleiteteErhoehung(
        grundsumme=grundsumme, erhoehungssumme=erlsumme - grundsumme,
        jahr=jahr)


@dataclass(frozen=True)
class AbgeleiteteSerie:
    """Die IST-Struktur eines Vertrags mit MEHREREN Alt-Ereignissen.

    Lieferung 2 der Baldrian-Uebernahme traegt Ereignis-SERIEN als
    Regelfall (jaehrliche Dynamiken, dazwischen Herabsetzungen). Das
    lineare Zwei-Gleichungs-System der Einzel-Ableitung ist dann
    dauerhaft unterbestimmt; bestimmend wird der BELEGTE Dynamiksatz:
    Jede Annahme erhoeht die Gesamtsumme um den Faktor (1 + Satz), jede
    Herabsetzung multipliziert NUR die Grundsumme mit dem
    fortgefuehrten Anteil (so sagt es das gelieferte Bedingungswerk:
    Teilkuendigung der Grundversicherung, Erhoehungen unberuehrt).
    Damit ist jede Folge aus Erhoehungen und Herabsetzungen LINEAR in
    der Ursprungs-Grundsumme — die gelieferte Gesamtsumme bestimmt sie
    geschlossen, ohne Nachlieferung von Scheibenbestaenden.

    SENSITIVITAET (Hinweis des Maintainers, 2026-09-01): Stufen, die
    aelter sind als die Zillmerdauer, tragen keinen
    Abschlusskosten-Restbestand mehr — Rekonstruktionsunsicherheit
    konzentriert sich auf die jungen Stufen. Die Probe gegen den
    gelieferten Jahresbeitrag laeuft im aktuariellen Test mit (BJB ist
    Pruefgroesse) und belegt Satz und Anteile je Vertrag unabhaengig.

    Die Struktur ist die IST-Welt am Stichtag: Die Grundsumme traegt
    die Herabsetzungen bereits in sich (kleinere Summe auf laufendem
    Blatt — genau so rechnet die Quelle nach einer Teilkuendigung
    weiter, ihre Blattformel ist zustandslos). Die VERFAHRENSFRAGE der
    Absetzung (Quelle mit Abzug, Ziel verlustfrei) ist damit fuer die
    Punktwerte in die Struktur eingepreist und gehoert als Behandlung
    in die Gate-Vorlage; gemessen wird sie an den
    Geschaeftsvorfaellen des Pruefzeitraums (A-M3), nicht doppelt am
    Stichtagswert.
    """

    grundsumme: float
    scheiben: Tuple[Tuple[int, float], ...]
    absetzungen: Tuple[Tuple[int, float], ...]
    #: Jahre von Herabsetzungen, deren Anteil aus der IST-Welt NICHT
    #: identifizierbar und fuer sie unerheblich ist: Liegt die
    #: Herabsetzung vor der ersten Erhoehung, skaliert sie die gesamte
    #: Kette — die gelieferte Summe bestimmt die IST-Struktur dann
    #: OHNE den historischen Anteil (jeder Kandidat ergibt dieselbe
    #: Struktur). Ein konkreter Anteil stuende als geratener Beleg da;
    #: das Jahr wird stattdessen hier ausgewiesen.
    anteil_unbestimmt: Tuple[int, ...] = ()

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "grundsumme": self.grundsumme,
            "scheiben": [list(s) for s in self.scheiben],
            "absetzungen": [list(a) for a in self.absetzungen],
            "anteil_unbestimmt": list(self.anteil_unbestimmt),
        }


def leite_serie_aus_satz_ab(
    *,
    ereignisse: Sequence[Tuple[str, int, Optional[float]]],
    erlsumme: float,
    satz: float,
) -> AbgeleiteteSerie:
    """IST-Struktur einer Ereignis-Serie aus dem belegten Dynamiksatz.

    ``ereignisse`` ist die chronologische Folge ``(art, jahr, anteil)``
    mit art in {ERH, RED}; ``anteil`` ist nur bei RED gesetzt (der
    fortgefuehrte Bruchteil f der Grundsumme, nachgelieferte Auskunft).
    Eine Beitragsfreistellung gehoert NICHT hierher — sie ist terminal
    und laeuft ueber die Gesamtsummen-Inversion
    (:func:`leite_pex_ursprungssumme_ab`). Die Zerlegung ist fuer den
    Wert unerheblich, weil nach terminalem PEX jede erreichbare
    Folgegroesse homogen in der beitragsfreien GESAMTSUMME ist:
    Bausteine desselben Ablauftermins tragen am selben Bewertungstag
    denselben Reservesatz je Einheit beitragsfreier Summe. Die
    UMWANDLUNGSFAKTOREN der Bausteine sind dagegen NICHT gleich (die
    Zillmer-Fenster der Scheiben liegen versetzt) — das
    Inversions-Ergebnis ist darum eine Aequivalenzgroesse, keine
    historische Bausteinsumme.

    Rueckgabe in IST-Summen: Scheiben centgerundet (so bucht die
    Quelle), die Grundsumme als Rest zur gelieferten Gesamtsumme —
    damit reproduziert die Struktur ERLSUMME exakt. Reisst die
    Vorwaertsprobe trotzdem (Satz passt nicht zur Lieferung), ist das
    ein harter Fehler, keine stille Glaettung.
    """
    if not 0.0 < satz < 1.0:
        raise MigrationszugangFehler(
            f"Erhoehungssatz {satz!r} liegt nicht in (0, 1)")
    if erlsumme <= 0.0:
        raise MigrationszugangFehler(f"ERLSUMME {erlsumme!r} unplausibel")
    if not ereignisse:
        raise MigrationszugangFehler("leere Ereignisfolge")

    grund_einheit = 1.0
    scheiben_einheiten: List[Tuple[int, float]] = []
    absetzungen: List[Tuple[int, float]] = []
    letztes_jahr = 0
    for art, jahr, anteil in ereignisse:
        if jahr <= letztes_jahr:
            raise MigrationszugangFehler(
                f"Ereignisjahre nicht strikt aufsteigend (Jahr {jahr} "
                f"nach {letztes_jahr}) — die Quelle bucht je Jahrestag "
                "hoechstens einen Vorfall; Lieferung klaeren"
            )
        letztes_jahr = jahr
        if art == "ERH":
            e = satz * (grund_einheit + sum(e for _, e in scheiben_einheiten))
            scheiben_einheiten.append((jahr, e))
        elif art == "RED":
            if anteil is None or not 0.0 < anteil < 1.0:
                raise MigrationszugangFehler(
                    f"Absetzung im Jahr {jahr} ohne gueltigen "
                    f"fortgefuehrten Anteil ({anteil!r}) — je Ereignis "
                    "nachliefern lassen (POLNR;GEVO;DATUM;ANTEIL)"
                )
            grund_einheit *= anteil
            absetzungen.append((jahr, anteil))
        else:
            raise MigrationszugangFehler(
                f"Ereignisart {art!r} gehoert nicht in die Serie "
                "(erwartet ERH/RED; PEX ist terminal und laeuft separat)"
            )

    gesamt_einheit = grund_einheit + sum(e for _, e in scheiben_einheiten)
    grundsumme_roh = erlsumme / gesamt_einheit
    # Versicherungssummen werden auf ganze Euro gefuehrt: Der glatte
    # Kandidat muss die Lieferung reproduzieren, sonst bleibt der rohe
    # Quotient (dieselbe verifizierte Glaettung wie bei der
    # Einzel-Erhoehung).
    glatt = round(grundsumme_roh)
    if glatt > 0 and abs(glatt * gesamt_einheit - erlsumme) <= 0.005 * (
            1 + len(scheiben_einheiten)):
        grundsumme_roh = float(glatt)
    scheiben = tuple(
        (jahr, round(grundsumme_roh * e, 2))
        for jahr, e in scheiben_einheiten
    )
    grundsumme_ist = round(erlsumme - sum(s for _, s in scheiben), 2)
    if grundsumme_ist <= 0.0:
        raise MigrationszugangFehler(
            f"rekonstruierte Grundsumme {grundsumme_ist!r} unplausibel — "
            f"der Satz {satz} passt nicht zur gelieferten Summe"
        )
    probe = grundsumme_roh * grund_einheit
    if abs(probe - grundsumme_ist) > 0.01 * (1 + len(scheiben)):
        raise MigrationszugangFehler(
            f"Vorwaertsprobe reisst: Grundsumme aus Kette {probe:.2f} "
            f"gegen Rest zur Lieferung {grundsumme_ist:.2f} — Satz oder "
            "Anteile passen nicht zur gelieferten Summe; Auskunft "
            "klaeren, nicht glaetten"
        )
    return AbgeleiteteSerie(
        grundsumme=grundsumme_ist,
        scheiben=scheiben,
        absetzungen=tuple(absetzungen),
    )


def bestimme_serie_mit_kandidaten(
    modellpunkt_felder: Mapping[str, Any],
    *,
    ereignisse: Sequence[Tuple[str, int, Optional[float]]],
    erlsumme: float,
    satz: float,
    jbrutto: float,
    kandidaten: Sequence[float],
    scheiben_mit_gamma1: bool = False,
    anker: Optional[Tuple[int, float]] = None,
    abs_tol: float = ABLEITUNG_SELBSTCHECK_TOL,
) -> AbgeleiteteSerie:
    """Offene Herabsetzungs-Anteile einer Serie aus einer ZWEITEN Gleichung bestimmen.

    Die exakten Anteile sind bei der Quelle endgueltig nicht mehr
    feststellbar (registrierte Auskunft), das Tarifwerk kennt aber nur
    endlich viele Stufen. Zu jeder Kandidaten-Kombination der offenen
    Herabsetzungen loest die Serien-Ableitung die Struktur geschlossen
    aus der Gesamtsumme — diskriminieren kann also nur eine zweite,
    unabhaengige Gleichung:

    * Solange der Vertrag Beitrag zahlt: der gelieferte JAHRESBEITRAG
      gegen die Summe der Baustein-Beitraege (Grund und jede
      Erhoehungsscheibe mit ihrem eigenen Eintrittsalter, gamma1 nach
      Lieferungsregel; dasselbe Muster wie
      :func:`pruefe_erhoehungssatz`). Der Beitrag geht in die
      Zerlegung nicht ein — die Probe ist keine Umkehrung ihrer selbst.
    * Ist die Beitragszahlungsdauer abgelaufen (JBRUTTO 0), tritt der
      ANKERWERT an die Stelle: das gelieferte Deckungskapital am
      Verankerungszeitpunkt gegen die vertragsweite Reserve der
      Struktur. Anders als die stetige Kalibrierung
      (:func:`kalibriere_absetzung_aus_dk`) waehlt das nur unter den
      ENDLICH VIELEN belegten Hypothesen; der Punktvergleich am Anker
      traegt danach trotzdem weniger Aussage — Aussage tragen die
      Punkte daneben (Kohorten-Logik, Grundsatzdokumentation 9.12).

    GENAU EIN Treffer bestimmt die Anteile (mit Beleg in
    ``absetzungen``). Treffen MEHRERE Kombinationen und ergeben sie
    DIESELBE Struktur, ist der Anteil aus der IST-Welt nicht
    identifizierbar UND fuer sie unerheblich (eine Herabsetzung vor
    der ersten Erhoehung skaliert die gesamte Kette — die gelieferte
    Summe bestimmt die Struktur ohne den historischen Anteil): Die
    Struktur wird zurueckgegeben, das Jahr steht in
    ``anteil_unbestimmt`` statt eines geratenen Anteils in
    ``absetzungen``. Treffen mehrere mit VERSCHIEDENEN Strukturen,
    ist das ein benannter Fehler — eine Bestimmung per Wuerfelwurf
    waere schlimmer als eine ausgewiesene Luecke. Zweiter
    Baldrian-Lauf, 2026-09-01.
    """
    offen = [i for i, (art, _, anteil) in enumerate(ereignisse)
             if art == "RED" and anteil is None]
    if not offen:
        return leite_serie_aus_satz_ab(
            ereignisse=ereignisse, erlsumme=erlsumme, satz=satz)
    eindeutig = sorted(set(kandidaten))
    if len(eindeutig) < 2:
        raise MigrationszugangFehler(
            f"Kandidatenmenge {list(kandidaten)!r}: unter zwei "
            "verschiedenen Kandidaten ist nichts zu bestimmen — einen "
            "bekannten Anteil direkt liefern (POLNR;GEVO;DATUM;ANTEIL)"
        )
    if len(offen) > 3:
        raise MigrationszugangFehler(
            f"{len(offen)} offene Herabsetzungen: die "
            "Kandidaten-Kombinatorik traegt keine Bestimmung mehr — "
            "Anteile je Ereignis nachliefern lassen"
        )
    if jbrutto > 0.0:
        probe_name = "Jahresbeitrag"
        geliefert = jbrutto
    elif anker is not None:
        probe_name = "Ankerwert"
        geliefert = float(anker[1])
    else:
        raise MigrationszugangFehler(
            "JBRUTTO <= 0 und kein Ankerwert: beide zweiten "
            "Gleichungen entfallen, offene Herabsetzungs-Anteile sind "
            "aus Kandidaten nicht bestimmbar — Anteile je Ereignis "
            "nachliefern lassen"
        )

    from rechner_pipeline.kern.rechenkern import (
        erhoehungs_scheibe,
        vertrags_monatsreserve,
    )

    kern_felder = {k: v for k, v in dict(modellpunkt_felder).items()
                   if not k.startswith("_")}
    treffer: List[Tuple[Tuple[float, ...], AbgeleiteteSerie]] = []
    proben: List[str] = []
    for kombi in itertools.product(eindeutig, repeat=len(offen)):
        versuch = list(ereignisse)
        for pos, f in zip(offen, kombi):
            art, jahr, _ = versuch[pos]
            versuch[pos] = (art, jahr, f)
        try:
            serie = leite_serie_aus_satz_ab(
                ereignisse=versuch, erlsumme=erlsumme, satz=satz)
        except MigrationszugangFehler as exc:
            proben.append(f"{kombi}: {exc}")
            continue
        grund_mp = ModelPoint(**{**kern_felder,
                                 "sum_insured": serie.grundsumme})
        grund = Rechenkern(grund_mp)
        scheiben_kerne = [
            (jahr_s, Rechenkern(erhoehungs_scheibe(
                grund_mp, jahr_s, summe,
                gamma1_uebernehmen=scheiben_mit_gamma1)))
            for jahr_s, summe in serie.scheiben
        ]
        if jbrutto > 0.0:
            system = (grund.gross_annual_premium()
                      if grund_mp.t > 0 else 0.0)
            system += sum(k.gross_annual_premium()
                          for _, k in scheiben_kerne if k.mp.t > 0)
        else:
            system = vertrags_monatsreserve(
                grund, scheiben_kerne, int(anker[0])).vx_mrv
        abw = abs(system - geliefert)
        proben.append(f"{kombi}: Abweichung {abw:.4f}")
        # Jeder Baustein ist eine eigene, fuer sich gerundete
        # Komponente des gelieferten Werts.
        if abw <= abs_tol * (1 + len(serie.scheiben)):
            treffer.append((kombi, serie))
    if len(treffer) == 1:
        return treffer[0][1]
    lage = "; ".join(proben)
    if not treffer:
        raise MigrationszugangFehler(
            f"kein belegter Kandidat reproduziert den gelieferten "
            f"{probe_name} {geliefert} ({lage}) — Kandidatenmenge oder "
            "Dynamiksatz klaeren, Anteile nachliefern lassen"
        )
    # Mehrere Treffer: identische Struktur = Anteil unerheblich. Die
    # Unerheblichkeit gilt JE POSITION, nicht pauschal: Eine offene
    # Herabsetzung, auf deren Wert sich alle Treffer-Kombinationen
    # einigen, IST durch die Probe bestimmt und bleibt in den
    # Absetzungen — nur wo die Kombinationen auseinanderlaufen, ist
    # der Anteil wirklich unerheblich fuer die Struktur.
    tol = abs_tol * (1 + len(treffer[0][1].scheiben))
    erste = treffer[0][1]
    if all(
        len(s.scheiben) == len(erste.scheiben)
        and abs(s.grundsumme - erste.grundsumme) <= tol
        and all(ja == jb and abs(sa - sb) <= tol
                for (ja, sa), (jb, sb) in zip(s.scheiben, erste.scheiben))
        for _, s in treffer[1:]
    ):
        offene_jahre = tuple(
            ereignisse[i][1] for k, i in enumerate(offen)
            if len({kombi[k] for kombi, _ in treffer}) > 1
        )
        return AbgeleiteteSerie(
            grundsumme=erste.grundsumme,
            scheiben=erste.scheiben,
            absetzungen=tuple(a for a in erste.absetzungen
                              if a[0] not in offene_jahre),
            anteil_unbestimmt=offene_jahre,
        )
    raise MigrationszugangFehler(
        f"mehrere Kandidaten-Kombinationen reproduzieren den "
        f"gelieferten {probe_name} mit VERSCHIEDENEN Strukturen "
        f"({lage}) — die Bestimmung waere ein Wuerfelwurf. Anteile je "
        "Ereignis nachliefern lassen, oder (wenn die Pruefpunkte "
        "nachweislich bewertungsinvariant sind, z. B. alle nach dem "
        "Beitragszahlungsende) eine dokumentierte Arbeits-Lesart je "
        "Ereignis setzen — sie ist dann eine Entscheidung, kein "
        "Systemwert"
    )


def pruefe_erhoehungssatz(
    kandidat: float,
    belege: Sequence[Tuple[Mapping[str, Any], int, float, float]],
    *,
    abs_tol: float = 0.011,
) -> Dict[str, Any]:
    """Einen Dynamiksatz gegen die gelieferten Jahresbeitraege pruefen.

    Je Beleg ``(modellpunkt_felder, jahr, erlsumme, jbrutto)`` wird die
    Zerlegung AUS DEM SATZ gebildet und der daraus folgende
    Gesamt-Jahresbeitrag (Grundvertrag plus Scheibe, jede bis zu ihrer
    eigenen Beitragszahlungsdauer) gegen den gelieferten gehalten. Der
    Beitrag geht in die Zerlegung nicht ein — die Pruefung ist also
    unabhaengig, nicht die Umkehrung ihrer selbst.

    Schluessel mit fuehrendem Unterstrich (etwa ``_police``) sind
    Beleg-Metadaten und erreichen den Modellpunkt nicht.

    Rueckgabe wie beim Abzugsabgleich: Zaehler, Quote und die groessten
    Ausreisser. Ein Urteil faellt hier NICHT; das ist Sache des
    Menschen, der den Satz fuer den Fall festlegt.
    """
    from rechner_pipeline.kern.rechenkern import erhoehungs_scheibe

    verletzende: List[Tuple[float, str]] = []
    geprueft = 0
    max_abw = 0.0
    for felder, jahr, erlsumme, jbrutto in belege:
        if jbrutto <= 0.0:
            continue
        zerlegung = leite_erhoehung_aus_satz_ab(
            jahr=jahr, erlsumme=erlsumme, satz=kandidat)
        kern_felder = {k: v for k, v in dict(felder).items()
                       if not k.startswith("_")}
        grund_mp = ModelPoint(**{**kern_felder,
                                 "sum_insured": zerlegung.grundsumme})
        grund = Rechenkern(grund_mp)
        scheibe = Rechenkern(erhoehungs_scheibe(
            grund_mp, jahr, zerlegung.erhoehungssumme))
        system = 0.0
        if grund_mp.t > 0:
            system += grund.gross_annual_premium()
        if scheibe.mp.t > 0:
            system += scheibe.gross_annual_premium()
        geprueft += 1
        abw = abs(system - jbrutto)
        max_abw = max(max_abw, abw)
        if abw > abs_tol:
            verletzende.append((abw, str(felder.get("_police", ""))))
    verletzende.sort(key=lambda e: -e[0])
    return {
        "satz": kandidat,
        "geprueft": geprueft,
        "verletzt": len(verletzende),
        "passt": geprueft > 0 and not verletzende,
        "quote_stuetzend": ((geprueft - len(verletzende)) / geprueft
                            if geprueft else 0.0),
        "max_abweichung": max_abw,
        "groesste_abweichungen": [round(a, 4) for a, _ in verletzende[:5]],
    }


def leite_erhoehung_ab(
    modellpunkt_felder: Mapping[str, Any],
    *,
    jahr: int,
    erlsumme: float,
    jbrutto: float,
    scheiben_mit_gamma1: bool = False,
) -> AbgeleiteteErhoehung:
    """Grund- und Erhoehungssumme einer Alt-Dynamik ableiten.

    Loest das lineare System

        S_g + S_s               = ERLSUMME
        S_g * B_g + S_s * B_s   = JBRUTTO

    mit den Beitragsraten des Grundvertrags (``B_g``) und der Scheibe
    (``B_s``, Modellpunkt mit versetzten Dauern). Welche
    Beitragsformel die Scheibe traegt, ist eine EIGENSCHAFT DER
    LIEFERUNG (``scheiben_mit_gamma1``, wie ueberall in der
    Serien-Ableitung; Vorgabe = GrundVS-Regel der ersten Lieferung) —
    mit der falschen Regel loest das System auf eine falsche
    Zerlegung. Beide zahlen bis zum SELBEN Kalenderzeitpunkt
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
    scheiben_rate = Rechenkern(erhoehungs_scheibe(
        einheit, jahr, 1.0,
        gamma1_uebernehmen=scheiben_mit_gamma1)).gross_premium_rate()
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
