"""Testprofile des aktuariellen Tests: Stichprobenweite und Abnahmekriterien.

Der aktuarielle Test besteht aus drei Abnahmen (ADR-010, ADR-012):
``A-M1`` Stichtagstest, ``A-M2`` Verlaufstest, ``A-M3``
Geschaeftsvorfalltest. Jede hat eine eigene Stichprobe, eigene Kriterien
und einen eigenen Bericht — und wird einzeln gezeichnet.

Zwei Dinge stehen deshalb hier und nicht in der Engine:

**Die Stichprobenweite.** Jeder Test kann von ``voll`` (ganzer Bestand
bzw. alle vorhandenen Geschaeftsvorfaelle) bis ``minimal`` (ein Fall je
Auspraegung) gefahren werden. Die Weite ist eine Entscheidung des
Aktuariats je Migrationsfall, keine Eigenschaft des Tests: Ein
Erstlauf gegen eine unbekannte Lieferung faehrt eng, eine Abnahme faehrt
weit. Weil die Weite den Beleg traegt, gehoert sie in das Profil und in
den Bericht.

**Die Abnahmekriterien.** Bis hierher zog die Engine ihre Toleranzen aus
``qa.abzugsabgleich`` — eine Quelle, nie aufgeweicht. Das war richtig,
solange es einen Test gab. Bei drei Tests mit verschiedenen Fragen ist es
falsch: Eine Ablaufleistung in zehn Jahren traegt eine andere Toleranz als
ein Deckungskapital am Uebernahmestichtag, und ein Rueckkaufswert zum
Stornotermin wieder eine andere. Die Kriterien stehen deshalb je Groesse
im Profil, beim Geschaeftsvorfalltest je Vorfallart.

**Wo die Untergrenze liegt.** Gelieferte Werte sind in aller Regel auf
Cent gerundet. Der mittlere Rundungsabstand ist ein Viertel Cent; im
Vorfuehrlauf lag der Median der Abweichungen bei 0,0024 und war damit
reines Rundungsrauschen, kein Befund. Eine Toleranz unterhalb dieser
Schwelle misst die Darstellungskonvention der Lieferung statt der
Rechnung. :data:`RUNDUNGSRAUSCHEN` haelt die Schwelle fest, und
:meth:`Kriterium.pruefe_ueber_rauschen` weist ein Profil zurueck, das sie
unterschreitet.

Knoten: klv
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

#: Groesster Betrag, den eine centgerundete Lieferung allein durch die
#: Rundung erzeugen kann. Eine Abnahmegrenze darunter ist keine fachliche
#: Aussage mehr.
RUNDUNGSRAUSCHEN = 0.005

#: Die drei Tests. Die Kennungen sind zugleich die Gate-Kennungen
#: (ADR-012); die Reihenfolge ist die Reihenfolge der Abnahme.
TESTS: Tuple[str, ...] = ("A-M1", "A-M2", "A-M3")

TITEL: Mapping[str, str] = {
    "A-M1": "Stichtagstest",
    "A-M2": "Verlaufstest",
    "A-M3": "Geschaeftsvorfalltest",
}


class ProfilFehler(ValueError):
    """Profil unbrauchbar — fail-fast statt eines nicht tragenden Belegs."""


@dataclass(frozen=True)
class Kriterium:
    """Wann ein Einzelwert stimmt und wann die Verteilung abnahmefaehig ist.

    ``abs_tol`` und ``rel_tol`` entscheiden ueber den einzelnen Vergleich.
    ``max_abs_residuum`` und ``p95_abs_residuum`` entscheiden ueber die
    Gruppe: Auch wenn jeder Einzelwert innerhalb seiner Toleranz liegt,
    kann eine Verteilung zu breit sein, um eine Methode zu belegen
    (Grundsatzdokumentation 9.15 — Toleranzen auf Maximum und hohen
    Perzentilen, nie auf Mittelwert oder Median).

    ``None`` bei einer Verteilungsgrenze heisst: nicht gefordert. Das ist
    eine bewusste Entscheidung des Aktuariats und steht so im Bericht —
    im Unterschied zu einer Grenze, die niemand gesetzt hat.
    """

    abs_tol: float
    rel_tol: float
    max_abs_residuum: Optional[float] = None
    p95_abs_residuum: Optional[float] = None

    def __post_init__(self) -> None:
        for name, wert in (("abs_tol", self.abs_tol), ("rel_tol", self.rel_tol)):
            if wert < 0:
                raise ProfilFehler(f"{name}={wert} ist negativ")
        for name, wert in (
            ("max_abs_residuum", self.max_abs_residuum),
            ("p95_abs_residuum", self.p95_abs_residuum),
        ):
            if wert is not None and wert < 0:
                raise ProfilFehler(f"{name}={wert} ist negativ")
        if (
            self.max_abs_residuum is not None
            and self.p95_abs_residuum is not None
            and self.p95_abs_residuum > self.max_abs_residuum
        ):
            raise ProfilFehler(
                f"p95_abs_residuum={self.p95_abs_residuum} liegt ueber "
                f"max_abs_residuum={self.max_abs_residuum} — das Perzentil "
                "kann das Maximum nicht ueberschreiten, die Grenze waere wirkungslos"
            )

    def pruefe_ueber_rauschen(self, wofuer: str) -> None:
        """Verteilungsgrenzen unter dem Rundungsrauschen sind keine Aussage."""
        for name, wert in (
            ("max_abs_residuum", self.max_abs_residuum),
            ("p95_abs_residuum", self.p95_abs_residuum),
        ):
            if wert is not None and 0 < wert < RUNDUNGSRAUSCHEN:
                raise ProfilFehler(
                    f"{wofuer}: {name}={wert} liegt unter dem "
                    f"Rundungsrauschen {RUNDUNGSRAUSCHEN} einer "
                    "centgerundeten Lieferung — eine solche Grenze misst "
                    "die Darstellung, nicht die Rechnung"
                )

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "abs_tol": self.abs_tol,
            "rel_tol": self.rel_tol,
            "max_abs_residuum": self.max_abs_residuum,
            "p95_abs_residuum": self.p95_abs_residuum,
        }


@dataclass(frozen=True)
class Testprofil:
    """Ein Test: welche Stichprobe, welche Kriterien, welcher Bericht.

    ``kriterien`` ist beim Stichtags- und beim Verlaufstest nach
    Vergleichsgroesse geschluesselt (``kVx_MRV``, ``RKW``, ...), beim
    Geschaeftsvorfalltest nach Vorfallart (``STO``, ``PEX``, ...) — dort
    entscheidet die Art des Vorfalls ueber die Toleranz, nicht die
    Groesse.

    ``weite`` beschreibt die Stichprobenziehung in Worten und ist Teil des
    Belegs. Sie wird hier nicht validiert, weil die Ziehung selbst in
    :mod:`rechner_pipeline.qa.stichprobe` sitzt; das Profil traegt nur die
    Aussage, WIE weit gezogen wurde.
    """

    #: Der Name beginnt mit "Test" und wuerde sonst von pytest als
    #: Testklasse eingesammelt — die Klasse ist aber ein Fachbegriff des
    #: aktuariellen Tests, kein Testgeruest.
    __test__ = False

    kennung: str
    kriterien: Mapping[str, Kriterium]
    weite: str
    grundtoleranz: Kriterium
    bemerkung: str = ""

    def __post_init__(self) -> None:
        if self.kennung not in TESTS:
            raise ProfilFehler(
                f"unbekannter Test {self.kennung!r} — bekannt sind {list(TESTS)}"
            )
        if not self.weite:
            raise ProfilFehler(
                f"{self.kennung}: keine Stichprobenweite benannt — ein "
                "Ergebnis ohne Angabe der Weite traegt keinen Beleg"
            )
        self.grundtoleranz.pruefe_ueber_rauschen(f"{self.kennung}/grundtoleranz")
        for schluessel, k in self.kriterien.items():
            k.pruefe_ueber_rauschen(f"{self.kennung}/{schluessel}")

    @property
    def titel(self) -> str:
        return TITEL[self.kennung]

    def fuer(self, schluessel: str) -> Kriterium:
        """Kriterium fuer eine Groesse bzw. Vorfallart, sonst die Grundtoleranz."""
        return self.kriterien.get(schluessel, self.grundtoleranz)

    def als_beleg(self) -> Dict[str, Any]:
        return {
            "kennung": self.kennung,
            "titel": self.titel,
            "weite": self.weite,
            "grundtoleranz": self.grundtoleranz.als_beleg(),
            "kriterien": {
                s: k.als_beleg() for s, k in sorted(self.kriterien.items())
            },
            "bemerkung": self.bemerkung,
        }


# --------------------------------------------------------------------------- #
# Vorlagen der drei Abnahmen
# --------------------------------------------------------------------------- #
#
# Ein Profil ist eine Entscheidung des Aktuariats je Migrationsfall. Diese
# Vorlagen sind der begruendete Ausgangspunkt dafuer, nicht die
# Entscheidung selbst: Sie tragen die Toleranzen, die aus der NATUR des
# jeweiligen Vergleichs folgen, und der Fall passt an, wo er Grund dazu
# hat. Eine Anpassung ist damit sichtbar — anders als eine Zahl, die
# irgendwann irgendwer gesetzt hat.
#
# Die Weite bleibt bewusst ohne Vorbelegung: Wie weit gezogen wurde, kann
# keine Vorlage wissen, und ein Vorgabewert waere genau die stille
# Annahme, die der Beleg verhindern soll.

#: Was eine centgerundete Lieferung an einem Vergleich zum SELBEN
#: Zeitpunkt hoechstens erzeugt. Beide Seiten runden, also das Doppelte
#: des Rundungsrauschens, aufgerundet auf den Cent.
_CENTGENAU = Kriterium(
    abs_tol=0.01, rel_tol=1e-9,
    max_abs_residuum=0.05, p95_abs_residuum=0.02,
)

#: Ein Wert, den das Quellsystem ueber Jahre fortgeschrieben hat. Jeder
#: Jahresschritt rundet erneut, und die Kostenverlaeufe beider Systeme
#: laufen minimal auseinander. Cent-Gleichheit ist hier nicht erreichbar
#: und ihre Forderung waere kein strengerer, sondern ein untauglicher
#: Test.
_FORTGESCHRIEBEN = Kriterium(
    abs_tol=0.05, rel_tol=1e-7,
    max_abs_residuum=1.00, p95_abs_residuum=0.25,
)

VORLAGEN: Mapping[str, Dict[str, Any]] = {
    "A-M1": {
        "grundtoleranz": _CENTGENAU,
        "kriterien": {},
        "bemerkung": (
            "Beide Punkte vergleichen zum selben Zeitpunkt gegen einen "
            "gelieferten Wert; es trennt sie nur die Rundung. Eine "
            "Unterscheidung je Groesse ist deshalb nicht begruendet — "
            "kVx_MRV, RKW, BJB und VS_bfr tragen dieselbe Grenze. Der "
            "Uebernahmepunkt ist bei gefuehrter Korrekturschicht "
            "konstruktionsbedingt null; aussagekraeftig ist der zweite "
            "Punkt, der die Fortschreibungsregel prueft."
        ),
    },
    "A-M2": {
        "grundtoleranz": _FORTGESCHRIEBEN,
        "kriterien": {},
        "bemerkung": (
            "Die Punkte liegen fuenf und zehn Jahre nach der Uebernahme "
            "und am Ablauf. Zum Ablauf ist der Wert keine Rechengroesse "
            "mehr, sondern die Zahlung an den Kunden — er verdiente eine "
            "engere Grenze als die Zwischenpunkte. Die Engine "
            "schluesselt die Kriterien dieses Tests aber nach "
            "Vergleichsgroesse, nicht nach Anlass, und die Ablaufleistung "
            "ist dieselbe Groesse kVx_MRV wie die Zwischenwerte. Wer den "
            "Ablauf enger fahren will, prueft ihn heute als eigenen Lauf. "
            "Das ist eine bekannte Enge der Profilstruktur, keine "
            "fachliche Aussage."
        ),
    },
    "A-M3": {
        "grundtoleranz": _CENTGENAU,
        "kriterien": {
            # Die einzige Art, die eine eigene Grenze verdient. Eine
            # Erhoehung legt eine Scheibe mit Reserve null an, dDK ist
            # also strukturell null — und eine gelieferte Null traegt
            # keinen Rundungsfehler, den man zugestehen muesste. Alle
            # uebrigen Arten vergleichen gegen einen centgerundeten
            # Betrag und tragen deshalb die Grundtoleranz; sie hier
            # einzeln zu wiederholen sagte nichts aus.
            # Der engere Wert steht beim Einzelvergleich, nicht bei den
            # Verteilungsgrenzen: Die halten die Untergrenze des
            # Rundungsrauschens ein, weil auch eine Verteilung von Nullen
            # gegen centgerundete Nachbarwerte ausgewertet wird.
            "ERH": Kriterium(
                abs_tol=0.001, rel_tol=1e-9,
                max_abs_residuum=RUNDUNGSRAUSCHEN,
                p95_abs_residuum=RUNDUNGSRAUSCHEN,
            ),
        },
        "bemerkung": (
            "Rueckkauf, Tod und Ablauf beenden den Vertrag; dort IST der "
            "Wert die Auszahlung, und eine Abweichung bekommt der Kunde "
            "zu spueren. Sie tragen dieselbe centgenaue Grenze wie die "
            "Umwandlungen — nicht aus Bequemlichkeit, sondern weil alle "
            "gegen einen centgerundeten Betrag zum selben Zeitpunkt "
            "vergleichen. "
            "Zur Herabsetzung: Rechnet das abgebende Unternehmen sie mit "
            "Stornoabzug und das Zielsystem verlustfrei, weicht dDK um "
            "genau diesen Abzug ab. Diese Grenze aufzuweiten, um den "
            "Befund verschwinden zu lassen, waere falsch — die Abweichung "
            "ist der Sachverhalt, den die Abnahme sehen soll. Sie gehoert "
            "in die Abnahmeentscheidung, belegt durch die Beschreibung "
            "des Quellverfahrens, nicht in eine stillere Toleranz. "
            "Invalidisierung und Reaktivierung stehen nicht in der "
            "Tabelle: Die Engine rechnet ihr dDK nicht, solange die "
            "BU-Zustandsbewertung offen ist."
        ),
    },
}


def vorlage(kennung: str, *, weite: str, bemerkung: str = "") -> Testprofil:
    """Das Profil einer Abnahme aus ihrer Vorlage bauen.

    ``weite`` ist Pflicht und beschreibt die Ziehung in Worten — sie
    gehoert in den Beleg und kann nicht vorbelegt werden. ``bemerkung``
    tritt NEBEN die Begruendung der Vorlage, statt sie zu ersetzen: Wer
    im Fall etwas anderes entscheidet, soll sagen warum, ohne dass die
    urspruengliche Begruendung verschwindet.
    """
    if kennung not in VORLAGEN:
        raise ProfilFehler(
            f"keine Vorlage fuer {kennung!r} — vorhanden sind "
            f"{sorted(VORLAGEN)}"
        )
    v = VORLAGEN[kennung]
    texte = [v["bemerkung"]]
    if bemerkung:
        texte.append(f"Zum Fall: {bemerkung}")
    return Testprofil(
        kennung=kennung,
        kriterien=dict(v["kriterien"]),
        weite=weite,
        grundtoleranz=v["grundtoleranz"],
        bemerkung=" ".join(texte),
    )
