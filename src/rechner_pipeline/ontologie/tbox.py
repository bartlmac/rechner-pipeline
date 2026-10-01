"""T-Box: das Domaenenmodell des Zielsystems, das A-Box und Spez sprechen.

Wer die T-Box aendert (Regel in der Fassung des Maintainers, 2026-10-01):

* In der ENTWICKLUNG der Loesung baut ein Agent unter ausdruecklichem
  Auftrag einen Entwurf im Arbeitsbaum — Vorschlag, Diff, Tests. Er
  entscheidet die Erweiterung nicht.
* In der LAUFZEIT einer Migration aendert kein Agent die T-Box
  schreibwirkend. Der Mensch (``mensch/architektur``) prueft die Diffs und
  zeichnet A-O1 (``A-O1.tbox-aenderung``) mit dem Aenderungsbeleg und der
  Stellungnahme des Aktuariats; erst dann gilt die neue Version.

Die A-Box (Instanzen eines Falls) wird von Agenten befuellt und ist die
einzige Wahrheit fuer die nachgelagerten Stufen; Code und Testfaelle sind
Projektionen daraus.

Umfang 0.1.0 war "was der erste Migrationsfall zwingend braucht": eine
Produktfamilie (gemischte KLV), Tarifgenerationen mit Merkmalsdimensionen
und Parametrierungszellen. 0.2.0 (ADR-024; vom Maintainer durchgesehen
2026-10-01, gezeichnet wird A-O1 im ersten Fall auf diesem Stand) traegt nach, was
Kern und Bestandsfuehrung inzwischen fuehren und die T-Box nie erfahren
hat:

* das TARIFWERK je Generation (Erhoehungsscheiben mit gamma1, Stornoabzug
  je Baustein, Verfahren der Herabsetzung) und das QUELLVERFAHREN (wie
  die abgebende Gesellschaft eine gelieferte Absetzung gemeint hat, samt
  Dynamiksatz, Stichtag des gelieferten Deckungskapitals und Ausgestaltung
  der Korrekturschicht) — beides als belegte Aussagen der A-Box, nicht
  mehr als Schalter am Aufruf eines Pruefkommandos. Fuer eine
  Bestandsmigration Pflicht (:data:`BESTAND_PFLICHT`, P-Q3 im Scope
  ``bestand``); die Kommandos der Bestandsstrecke lesen sie aus der Spez;
* den Katalog der Geschaeftsvorfaelle mit Betragsarten, Zustandswirkung
  und Produktbindung, einschliesslich der Teilkuendigung als eigenem
  Vorgang (ADR-023);
* das Vertragsvokabular einer Lieferung (Zielfelder, Status, Geschlecht,
  Zahlweise) und den Zustandsextrakt der Migration (Verankerung,
  Erhoehungsscheiben, Herabsetzungen, Merkmale; Grundsatzdokumentation
  9.12 und 9.14);
* die zweite Produktfamilie (BU) als VOKABULAR — Zustaende, Leistungs-
  groesse, Rechnungsgrundlagen —, nicht als instanziierbare Familie der
  A-Box: Extraktion, Spez und P-K1 rechnen heute nur die KLV.

Was bewusst draussen bleibt: Abnahmen, Belege, Rollen und Zeichnungen
(Prozess, nicht Domaene — ``models.belegrollen``, ``models.zeichnung``);
Erfahrungsannahmen dritter Ordnung (Simulationswerkzeug, Tarifplan KLV
Abschnitt 10); Spaltentypen und Dateischemata der Bestandsfuehrung
(``models.bestand``).

KEINE ZWEITE WAHRHEIT: Wo der Code eine Menge schon als Konstante fuehrt,
spiegelt die T-Box sie, und ``tests/test_tbox_erweiterung_020.py`` haelt
beide mit ``==`` gleich. Die T-Box importiert die Konstanten bewusst
NICHT — ein Import liesse das Vokabular still mit dem Code wandern, ohne
dass die Version sich hebt. Wandert der Code, wird der Test rot, und der
Rueckweg ist der vorgesehene: Version heben, A-O1.

Knoten: klv
"""

from __future__ import annotations

import hashlib
import json
import typing
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rechner_pipeline.ontologie.aussage import Aussage
from rechner_pipeline.ontologie.diskrepanz import Diskrepanz
from rechner_pipeline.ontologie.ids import knoten_id, zellen_segment

#: Version der T-Box (des Vokabulars, das A-Box und Spez sprechen).
#: REGEL (Review T22-02, Entscheid des Maintainers 2026-09-06): Jede
#: Aenderung am Schema der T-Box hebt diese Version, und jede Hebung geht
#: ueber das Gate A-O1 mit dem Pflichtbeleg ``abgeleitet/tbox/aenderung.json``
#: (alte und neue Version, SHA-256 dieses Moduls, Aenderungsartefakt).
#: Geprueft wird die Version an drei Stellen: P-Q3 haelt die A-Box gegen
#: sie (validate_abox), P-K1 die Spez gegen A-Box und sie (validate_spez),
#: A-O1 den Beleg gegen sie (gate_entscheid). Ein Mismatch ist ein
#: Fehler, keine Warnung — vorher war die Version ein ueberschreibbarer
#: Default, den niemand verglich. Dass das Vokabular sich nicht OHNE
#: Hebung bewegt, haelt der Abdruck :func:`vokabular_sha256` (Test).
TBOX_VERSION = "0.2.0"
#: Die Versionslinie der T-Box, aelteste zuerst — der im CODE nachweisbare
#: "alte Stand" fuer A-O1 (Review T23-03): ein Uebergang von_version ->
#: nach_version ist nur zeichenbar, wenn von der unmittelbare Vorgaenger
#: von nach in dieser Linie ist und nach die Version ist, die der Code
#: traegt. Bei jedem Bump wird die neue Version ANGEHAENGT; die Linie wird
#: nie umgeschrieben. Jeder Schritt der Linie hat eine Hebungsregel fuer
#: bestehende A-Boxen (``ontologie.abox.HEBUNGEN``).
TBOX_VERSIONEN: tuple = ("0.1.0", "0.2.0")
#: Schema der A-Box-DATEI (Struktur der Instanz-Datei, nicht das
#: Vokabular); beim Laden gegen den deklarierten Schluessel gehalten.
ABOX_SCHEMA_VERSION = 1

# --------------------------------------------------------------------------- #
# Rechnungsgrundlagen je Produktfamilie
# --------------------------------------------------------------------------- #

#: Pflichtumfang einer Parametrierungszelle (P6-Referenz): ohne diese
#: Felder ist ein Tarif nicht rechenbar. Die Namen SIND die Feldnamen
#: des Kern-ModelPoints — die Projektion A-Box -> ModelPoint ist ein
#: Mapping, keine Uebersetzung.
PFLICHT_PARAMETER = (
    "zins",
    "tafel",
    "alpha",
    "beta1",
    "gamma1",
    "gamma2",
    "gamma3",
    "policy_fee",
    "stoab_satz",
    "stoab_min",
    "stoab_max",
    "min_alter_flex",
    "min_rlz_flex",
)

#: Optionale Parameter (Tarifwerk-Stellschrauben mit Kern-Defaults).
OPTIONALE_PARAMETER = (
    "zillmer_dauer",
    "ratzu_zw2",
    "ratzu_zw4",
    "ratzu_zw12",
)

BEKANNTE_PARAMETER = frozenset(PFLICHT_PARAMETER) | frozenset(OPTIONALE_PARAMETER)

#: Rechnungsgrundlagen der BU (Tarifplan BU, Abschnitt 8; Spiegel von
#: ``models.bestand.BU_GENERATION_FIELDS``). Vokabular, noch nicht
#: Pflichtumfang einer A-Box-Zelle: eine BU-Generation ist in 0.2.0 nicht
#: instanziierbar (:data:`ABOX_FAMILIEN`).
BU_PARAMETER: Tuple[str, ...] = (
    "zins", "tafel_aktiv", "tafel_i", "tafel_ri", "tafel_ti", "zuschlag",
)

RECHNUNGSGRUNDLAGEN_JE_FAMILIE: Dict[str, Tuple[str, ...]] = {
    "klv": PFLICHT_PARAMETER + OPTIONALE_PARAMETER,
    "bu": BU_PARAMETER,
}

# --------------------------------------------------------------------------- #
# Produktfamilien
# --------------------------------------------------------------------------- #

#: Die Produktfamilien des Zielsystems (Spiegel von
#: ``models.bestand.PRODUKT_VALUES``; Wurzel jeder Knoten-ID).
PRODUKTFAMILIEN: Dict[str, str] = {
    "klv": "gemischte Kapitallebensversicherung",
    "bu": "selbstaendige Berufsunfaehigkeitsversicherung",
}
#: Die Familien, deren Tarifgenerationen eine A-Box INSTANZIIERT. Die BU
#: steht im Vokabular, aber nicht hier: Ihre Generation braucht eine
#: Extraktion, eine Spez und ein P-K1 fuer das Zustandsmodell, und keines
#: davon gibt es (naechste Stufe, mit dem ersten BU-Fall).
ABOX_FAMILIEN: Tuple[str, ...] = ("klv",)
#: Zustandsraum je Familie (Tarifplaene, Abschnitt 2; Spiegel der
#: Zustandsnamen des Kerns).
ZUSTAENDE_JE_FAMILIE: Dict[str, Tuple[str, ...]] = {
    "klv": ("aktiv", "tot"),
    "bu": ("aktiv", "bu", "tot"),
}
#: Die Leistungsgroesse, in der die Familie ihren Bestand misst
#: (Spiegel von ``models.bestand.LEISTUNGSSPALTE``).
LEISTUNGSGROESSE_JE_FAMILIE: Dict[str, str] = {
    "klv": "sum_insured",
    "bu": "bu_rente",
}

# --------------------------------------------------------------------------- #
# Tarifwerk je Generation und Verfahren der Quelle
# --------------------------------------------------------------------------- #

#: Die Verfahren der Herabsetzung (Tarifplan KLV 7.1/7.2; Spiegel von
#: ``kern.beitragsreduktion.VERFAHREN`` und ``models.bestand.RED_VERFAHREN``).
#: ``prospektiv`` und ``mit_abzug`` wandeln den freiwerdenden Beitrag in
#: beitragsfreie Summe um (Geschaeftsvorfall ``RED``); ``teilkuendigung``
#: kuendigt einen Summenanteil und zahlt ihn aus (``TKU``). Als Tarifwerk
#: einer Generation heisst ``teilkuendigung``: Dieser Tarif kennt keine
#: Beitragsherabsetzung, nur die Teilkuendigung (Entscheid des Maintainers
#: 2026-10-01, Tarifplan KLV 7.2; ersetzt die fruehere Annahme A1).
HERABSETZUNGSVERFAHREN: Tuple[str, ...] = ("prospektiv", "mit_abzug", "teilkuendigung")
#: Der Umfang der Teilkuendigung (Tarifplan KLV 7.2, Entscheid B1 vom
#: 2026-10-01; Spiegel von ``kern.vorgangsfolge.TKU_UMFAENGE``): alle
#: Bausteine (eigene Tarife der PLV) oder nur die Grundversicherung (der
#: uebernommene Tarif TG2015, Bedingungswerk Ziffer 6).
TKU_UMFAENGE: Tuple[str, ...] = ("alle_bausteine", "grundversicherung")
TEILKUENDIGUNG_VERFAHREN = "teilkuendigung"

#: Die Tarifwerks-Merkmale einer Generation (Grundsatzdokumentation 10
#: Nr. 9; Spiegel der Schluessel von ``bestand.config.TarifGeneration.
#: tarifwerk()``). Namen wie in der Bestand-Config — die Projektion ist ein
#: Mapping. Je Merkmal der zulaessige Wertebereich.
TARIFWERK_MERKMALE: Tuple[str, ...] = (
    "scheiben_mit_gamma1", "stoab_je_baustein", "red_verfahren", "tku_umfang",
)
TARIFWERK_WERTE: Dict[str, Tuple[Any, ...]] = {
    "scheiben_mit_gamma1": (False, True),
    "stoab_je_baustein": (False, True),
    "red_verfahren": HERABSETZUNGSVERFAHREN,
    "tku_umfang": TKU_UMFAENGE,
}
#: Das Tarifwerk des EIGENEN Geschaefts (Tarifplan KLV, Abschnitte 6 und 7):
#: Scheiben ohne gamma1, Stornoabzug je Vertrag, Herabsetzung prospektiv,
#: Teilkuendigung ueber alle Bausteine.
#: Fuer eine uebernommene Generation ist das KEINE Vorgabe — ihre Vertraege
#: tragen ihr Bedingungswerk, und ein nicht erhobenes Merkmal bleibt in der
#: Coverage sichtbar, statt still mit diesem Satz gefuellt zu werden.
TARIFWERK_EIGENES_GESCHAEFT: Dict[str, Any] = {
    "scheiben_mit_gamma1": False,
    "stoab_je_baustein": False,
    "red_verfahren": "prospektiv",
    "tku_umfang": "alle_bausteine",
}

#: Der eine Code, mit dem eine Lieferung beide Absetzungen fuehrt: Die
#: Vorgeschichte und die Auskunft der Quelle kennen nur ``RED``.
QUELL_ABSETZUNGSCODE = "RED"
#: Das QUELLVERFAHREN: wie die abgebende Gesellschaft eine gelieferte
#: Absetzung gemeint hat — eine Eigenschaft der Lieferung je Generation,
#: nicht das Tarifwerk, nach dem das Ziel kuenftig fuehrt (meist gleich,
#: weil die Vertraege ihr Bedingungswerk behalten; verschieden, wenn die
#: Quelle anders verfuhr, als ihr Bedingungswerk sagt). Lesart (ADR-023 mit
#: Nachtrag 2026-10-01; Grundsatzdokumentation 7.1: ab der Migration gilt das
#: Vokabular des Zielsystems): Ist das Quellverfahren ``teilkuendigung``, war
#: JEDE gelieferte Absetzung eine Teilkuendigung; sonst vor dem Beitragsende
#: und vor einer Beitragsfreistellung eine Herabsetzung, danach eine
#: Teilkuendigung (A2, Annahme B5). Die Regel selbst fuehrt das Datenmodell
#: an einer Stelle (``models.bestand.alt_absetzung_ist_teilkuendigung``).
#:
#: Neben der Lesart der Absetzung fuehrt der Block, was jede Rechnung der
#: Bestandsstrecke bestimmt und vorher als Schalter am Aufruf stand
#: (ADR-024, Nachtrag "die Kommandos lesen die Spez"):
#:
#: * ``erhoehungssatz`` — der Dynamiksatz der Quelle (S' = e * S^ges), aus
#:   dem die Alt-Erhoehungen einer Serie zerlegt werden. Optional: Ein Tarif
#:   ohne planmaessige Erhoehung hat keinen; dann zerlegt die Strecke je
#:   Vertrag aus dem Jahresbeitrag. ERHOBEN muss er sein (belegt oder
#:   ausdruecklich nicht belegt), sonst ist "trifft nicht zu" nicht von
#:   "vergessen" zu unterscheiden.
#: * ``dk_stichtag`` — zu welchem Zeitpunkt die Lieferung ihr
#:   Deckungskapital fuehrt (``kalendertag``: auf den Abzugsstichtag
#:   interpoliert; ``jahrestag``: zum letzten Vertragsjahrestag davor). Auf
#:   dem falschen Zeitpunkt misst das Controlling Reservezuwachs als Residuum.
#: * ``formfunktion`` und ``fenster`` — die Ausgestaltung der
#:   Korrekturschicht, die der Tarifplan eines migrierten Produkts festlegt
#:   (Grundsatzdokumentation 10 Nr. 9 und 9.9). Keine Eigenschaft der Quelle
#:   im engen Sinn, sondern der Migration dieser Generation; sie steht hier,
#:   weil sie wie das Verfahren der Quelle je Generation einmal entschieden
#:   und von Uebernahme und Verankerung gleich gelesen werden muss. Ein
#:   Fenster gibt es genau zur Formfunktion ``konstantes_fenster``.
QUELLVERFAHREN_WERTE: Dict[str, Any] = {}   # gefuellt unten (Zahlbereich)

#: Zu welchem Zeitpunkt eine Lieferung ihr Deckungskapital fuehrt.
DK_STICHTAGE: Tuple[str, ...] = ("kalendertag", "jahrestag")
#: Formfunktionen der Korrekturschicht (Grundsatzdokumentation 9.9).
FORMFUNKTIONEN: Tuple[str, ...] = ("proportional_zur_basis", "konstantes_fenster")
KONSTANTES_FENSTER = "konstantes_fenster"


class Zahlbereich(BaseModel):
    """Ein Wertebereich fuer eine ZAHL — wo eine Aufzaehlung nicht passt
    (Dynamiksatz, Fenster). Typstreng wie die Aufzaehlungen: ``True`` ist
    keine Zahl, ``1`` kein Satz."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    typ: Literal["float", "int"]
    #: Untergrenze (ausschliesslich bei ``float``, einschliesslich bei ``int``).
    untergrenze: float
    #: Obergrenze (ausschliesslich); None = offen.
    obergrenze: Optional[float] = None

    def enthaelt(self, wert: Any) -> bool:
        if isinstance(wert, bool):
            return False
        if self.typ == "int":
            if type(wert) is not int or wert < self.untergrenze:
                return False
        else:
            if type(wert) is not float or not wert > self.untergrenze:
                return False
        return self.obergrenze is None or wert < self.obergrenze

    def text(self) -> str:
        links = "[" if self.typ == "int" else "("
        rechts = "unbegrenzt)" if self.obergrenze is None else f"{self.obergrenze})"
        return f"{self.typ} {links}{self.untergrenze}, {rechts}"


QUELLVERFAHREN_WERTE.update({
    "red_verfahren": HERABSETZUNGSVERFAHREN,
    "erhoehungssatz": Zahlbereich(typ="float", untergrenze=0.0, obergrenze=1.0),
    "dk_stichtag": DK_STICHTAGE,
    "formfunktion": FORMFUNKTIONEN,
    "fenster": Zahlbereich(typ="int", untergrenze=1),
})

#: Die Bloecke generationsweiter Aussagen der A-Box (neben den Zellen):
#: Blockname -> Merkmal -> Wertebereich. Ein Widerspruch in einem Block
#: wird Diskrepanz am Knoten ``<generation>/<block>``.
GENERATIONS_BLOECKE: Dict[str, Dict[str, Any]] = {
    "tarifwerk": TARIFWERK_WERTE,
    "quellverfahren": QUELLVERFAHREN_WERTE,
}
BLOCK_TITEL: Dict[str, str] = {
    "tarifwerk": "Tarifwerk",
    "quellverfahren": "Quellverfahren",
}

#: Was eine BESTANDSMIGRATION je Generation belegt fuehren muss (Fall-Scope
#: ``bestand``; ADR-024, Nachtrag): das ganze Tarifwerk, die Lesart der
#: Absetzung, der Zeitpunkt des gelieferten Deckungskapitals und die
#: Formfunktion. Jedes dieser Merkmale bestimmt eine Rechnung der
#: Bestandsstrecke, und keines hat eine Vorgabe — die des eigenen Geschaefts
#: (:data:`TARIFWERK_EIGENES_GESCHAEFT`) ist fuer einen uebernommenen Tarif
#: keine Aussage. Im Scope ``tarif`` gilt die Pflicht nicht: Ein Tariffall
#: fuehrt keinen Bestand, und keine seiner Rechnungen liest die Bloecke.
BESTAND_PFLICHT: Dict[str, Tuple[str, ...]] = {
    "tarifwerk": TARIFWERK_MERKMALE,
    "quellverfahren": ("red_verfahren", "dk_stichtag", "formfunktion"),
}
#: Merkmale, die eine Bestandsmigration ERHEBEN muss, ohne dass sie belegt
#: sein muessen (belegt oder ausdruecklich ``nicht_belegt``). Das Fenster
#: folgt der Formfunktion (:func:`tarifregeln_luecken`).
BESTAND_ERHOBEN: Dict[str, Tuple[str, ...]] = {
    "quellverfahren": ("erhoehungssatz",),
}


def wert_im_bereich(wert: Any, bereich: Any) -> bool:
    """Typstreng: ``1`` ist nicht ``True`` und ``"true"`` kein Schalter."""
    if isinstance(bereich, Zahlbereich):
        return bereich.enthaelt(wert)
    return any(type(wert) is type(w) and wert == w for w in bereich)


def bereich_text(bereich: Any) -> str:
    """Der Wertebereich lesbar, fuer Meldungen."""
    if isinstance(bereich, Zahlbereich):
        return bereich.text()
    return repr(list(bereich))


def _bereich_vokabular(bereich: Any) -> Any:
    if isinstance(bereich, Zahlbereich):
        return bereich.model_dump(mode="json")
    return list(bereich)


def tarifregeln_luecken(
    belegt: Dict[str, Dict[str, Any]],
    erhoben: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Was einer Bestandsmigration an Tarifregeln fehlt — leer = vollstaendig.

    ``belegt``: Block -> Merkmal -> belegter Wert (genau das, was die Spez
    traegt). ``erhoben``: Block -> Menge der Merkmale, zu denen die A-Box
    ueberhaupt eine Aussage fuehrt (auch ``nicht_belegt``); None, wo nur die
    Spez vorliegt — die fuehrt nur Belegtes, und ob ein optionales Merkmal
    erhoben wurde, hat P-Q3 vorher entschieden.

    EINE Regel fuer P-Q3 (auf der A-Box) und fuer jedes Kommando der
    Bestandsstrecke (auf der Spez, ``spez.tarifregeln``): Was die Quelle
    pruefung durchlaesst, rechnet die Strecke, und umgekehrt.
    """
    luecken: List[str] = []
    for block, merkmale in BESTAND_PFLICHT.items():
        for merkmal in merkmale:
            if merkmal not in belegt.get(block, {}):
                luecken.append(f"{block}.{merkmal} nicht belegt")
    if erhoben is not None:
        for block, merkmale in BESTAND_ERHOBEN.items():
            for merkmal in merkmale:
                if merkmal not in erhoben.get(block, ()):
                    luecken.append(
                        f"{block}.{merkmal} nicht erhoben (belegt oder "
                        "ausdruecklich nicht_belegt)")
    quell = belegt.get("quellverfahren", {})
    if "formfunktion" in quell:
        if quell["formfunktion"] == KONSTANTES_FENSTER and "fenster" not in quell:
            luecken.append(
                "quellverfahren.fenster nicht belegt (Pflicht zur Formfunktion "
                f"{KONSTANTES_FENSTER})")
        if quell["formfunktion"] != KONSTANTES_FENSTER and "fenster" in quell:
            luecken.append(
                f"quellverfahren.fenster belegt ({quell['fenster']!r}), die "
                f"Formfunktion {quell['formfunktion']!r} kennt kein Fenster — "
                "widerspruechlich")
    return luecken


# --------------------------------------------------------------------------- #
# Geschaeftsvorfaelle
# --------------------------------------------------------------------------- #

class Geschaeftsvorfall(BaseModel):
    """Ein Geschaeftsvorfall des Bewegungskontos (Tarifplaene, Abschnitt 7)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    #: Produktfamilien, die den Vorfall kennen.
    familien: Tuple[str, ...]
    #: Der Status, den der Vorfall herstellt (None: keiner — er aendert
    #: Summe, Beitrag oder Zugehoerigkeit, nicht den Zustand).
    zustand: Optional[str] = None
    #: Die Betragsarten, die der Vorfall bucht.
    betragsarten: Tuple[str, ...]


def _gv(code, name, familien, zustand, betragsarten) -> Geschaeftsvorfall:
    return Geschaeftsvorfall(code=code, name=name, familien=familien,
                             zustand=zustand, betragsarten=betragsarten)


#: Spiegel von ``models.bestand.EREIGNIS_VALUES`` (Reihenfolge),
#: ``BETRAG_ART_JE_EREIGNIS``, ``EREIGNIS_ZUSTAND`` und der Produktbindung
#: aus ``ANNAHME_ERZEUGT``.
GESCHAEFTSVORFAELLE: Dict[str, Geschaeftsvorfall] = {g.code: g for g in (
    _gv("ZUG", "Zugang", ("klv", "bu"), None, ("VS", "BU_Jahresrente", "BJB")),
    _gv("MIG", "Migrationszugang (Residuum der Uebernahme)", ("klv", "bu"), None,
        ("dDK_uebernahme",)),
    _gv("ERH", "dynamische Erhoehung", ("klv",), None, ("VS_erhoehung", "BJB")),
    _gv("RED", "Beitragsherabsetzung", ("klv",), None,
        ("VS_herabsetzung", "dDK_absorption")),
    _gv("TKU", "Teilkuendigung", ("klv",), None,
        ("VS_teilkuendigung", "dDK_absorption", "RKW_teilkuendigung",
         "Kappung_teilkuendigung")),
    _gv("PEX", "Beitragsfreistellung", ("klv",), "PEX", ("VS_bfr", "VS")),
    _gv("INV", "Invalidisierung", ("bu",), "BU", ("BU_Jahresrente",)),
    _gv("REA", "Reaktivierung", ("bu",), "POL", ("BU_Jahresrente",)),
    _gv("STO", "Rueckkauf", ("klv",), "STO", ("RKW",)),
    _gv("TOD", "Tod", ("klv", "bu"), "TOD", ("Todesfallleistung", "BU_Jahresrente")),
    _gv("ABL", "Ablauf", ("klv", "bu"), "ABL", ("Ablaufleistung", "BU_Jahresrente")),
)}
#: Die beiden Vorfaelle, die eine Summe eines laufenden Vertrags senken und
#: dieselbe Nebentabelle ``reduktionen`` fuehren (ADR-023; Spiegel von
#: ``models.bestand.REDUKTION_EREIGNISSE``).
ABSETZUNG_VORGAENGE: Tuple[str, ...] = ("RED", "TKU")

# --------------------------------------------------------------------------- #
# Vertrag: was eine Lieferung je Vertrag traegt und das Ziel fuehrt
# --------------------------------------------------------------------------- #

#: Vertragsstatus des Bestands (Spiegel von ``models.bestand.
#: STATUS_CODE_VALUES``). Herabsetzung und Teilkuendigung sind KEIN Status:
#: ein anderer Verlauf, kein anderer Zustand.
VERTRAGSSTATUS: Dict[str, str] = {
    "POL": "beitragspflichtig in Kraft",
    "PEX": "beitragsfrei in Kraft",
    "BU": "im Leistungsbezug (BU)",
    "STO": "zurueckgekauft",
    "TOD": "durch Tod beendet",
    "ABL": "abgelaufen",
}
AKTIVE_STATUS: Tuple[str, ...] = ("POL", "PEX", "BU")
TERMINALE_STATUS: Tuple[str, ...] = ("STO", "TOD", "ABL")
#: Zielwerte des Geschlechts. Notwendig, weil der Kern jedes Nicht-"M" still
#: zur Frauentafel aufloest (``kern/tafeln._tafel_key``): ein durchgereichtes
#: "W" waere kein Fehler, sondern ein stiller Default (P2).
GESCHLECHTER: Tuple[str, ...] = ("M", "F")
ZAHLWEISEN: Tuple[int, ...] = (1, 2, 4, 12)

#: Ziel-Pflichtfelder eines transformierten Bestandsabzugs — die
#: Vertragsseite des Kern-Contracts plus Abgleichswerte (bis 0.1.0 als
#: ``ZIEL_PFLICHT`` in ``ontologie.transformation``, ausserhalb der
#: T-Box und ausserhalb ihrer Version). Bewusst NICHT die Generation-Felder
#: (Zins, Kosten): die kommen aus der Spez des Migrationsfalls, nie aus dem
#: Abzug.
#:
#: ``sex`` ist PFLICHT, weil der Kern es zwingend fuehrt: es steht in
#: ``models/bestand.CONTRACT_FIELDS``, ``model_point_kwargs`` liest
#: ``row["sex"]`` ohne Default, und der ModelPoint hat kein Default-
#: Geschlecht. Als optionales Feld fiele die Luecke erst im Kern auf
#: (KeyError), nicht in der Spec-Pruefung. Unisex macht das Geschlecht
#: tarif-wirkungslos, nicht entbehrlich — der Bestand fuehrt es weiter fuer
#: Nachweisung, Folgebewertung und spaetere geschlechtsabhaengige
#: Generationen. Fehlt der Lieferung eine Geschlechtsspalte, ist das ein
#: Befund fuer den Menschen (A-Q1), keine stille Auslassung.
#:
#: ``status`` und ``tarifart`` sind hier die MERKMALSDIMENSIONEN der
#: ersten uebernommenen Generation (TG2015: Raucherstatus, Tarifart), nicht
#: der Vertragsstatus — Befund des Entwurfs 0.2.0, nicht umgebaut: Die
#: Dimensionen gehoeren der Generation (A-Box), nicht jedem Abzug.
VERTRAG_PFLICHT: Tuple[str, ...] = (
    "police_id", "beginn", "entry_age", "sex", "duration",
    "premium_duration", "sum_insured", "zahlweise", "status", "tarifart",
)
#: Optionale Zielfelder (Abgleichswerte und Herkunfts-Extras).
#:
#: ``monate_ta``/``dk_ta`` sind die Verankerungsattribute
#: (Grundsatzdokumentation 9.12): der letzte exakte Rechenpunkt des
#: Quellsystems (in vollen Vertragsmonaten seit Beginn) und der dort
#: gelieferte Deckungskapitalwert. Nur zusammen sinnvoll —
#: ``gates.bestand_uebernehmen`` verlangt beide oder keins je Zeile.
VERTRAG_OPTIONAL: Tuple[str, ...] = (
    "vertragsjahre_am_stichtag", "brutto_jahresbeitrag",
    "brutto_zahlbeitrag", "deckungskapital", "geburtsdatum",
    "monate_ta", "dk_ta",
)

# --------------------------------------------------------------------------- #
# Migration: Vorgeschichte und Zustandsextrakt (Grundsatzdokumentation 9.14)
# --------------------------------------------------------------------------- #

#: Vorfaelle der gelieferten Vorgeschichte, die im Quellsystem eine
#: Neuberechnung ausgeloest haben und deshalb den Verankerungszeitpunkt
#: setzen (9.12; Spiegel von ``bestand.migrationszugang.
#: RECHNENDE_VORFAELLE``). Codes der QUELLE — ihre Provenienz-Namen
#: bleiben erhalten. ``ZUZ`` und ``VERL`` nennt der Code ohne fachliche
#: Erlaeuterung; ihre Bedeutung ist im Entwurf eine offene Frage, keine
#: Annahme. Die Vorgeschichte traegt Zeitpunkt und Art, nie einen Wert.
QUELL_VORGAENGE_RECHNEND: Tuple[str, ...] = ("ERH", "PEX", "RED", "ZUZ", "VERL")

#: Der Zustandsextrakt eines uebernommenen Vertrags: die Historienergebnisse,
#: die der Kern als Vertragsattribute sieht (9.14) — je Nebentabelle die
#: Merkmale ohne die Policennummer (Spiegel der Spaltennamen in
#: ``models.bestand``). Die Korrekturschicht gehoert nicht dazu: Sie liefert
#: nicht die Quelle, das Ziel leitet sie ab.
ZUSTANDSEXTRAKT: Dict[str, Tuple[str, ...]] = {
    "verankerung": ("monate_ta", "zustand_ta", "verweildauer_ta", "dk_ta"),
    "scheiben": ("scheiben_id", "erhoehung_jahr", "erhoehung_datum",
                 "entry_age", "duration", "premium_duration", "sum_insured",
                 "gamma1"),
    "reduktionen": ("reduktion_jahr", "reduktion_datum", "anteil", "verfahren"),
    "merkmale": ("dimension", "auspraegung"),
}
#: Vertragszustand am Verankerungszeitpunkt in der Sprache der Uebernahme.
ZUSTAENDE_TA: Tuple[str, ...] = ("beitragspflichtig", "beitragsfrei")
#: Startzustand der Korrekturschicht — ein Erlebenszustand des Zustands-
#: modells (Beitragsfreiheit ist keiner, sondern eine Eigenschaft des
#: Modellpunkts).
VERANKERUNGSZUSTAENDE: Tuple[str, ...] = ("aktiv", "bu")
QUELLE_ARTEN = ("tarifmeldung", "tarifrechner", "bestand")


# --------------------------------------------------------------------------- #
# Klassen der A-Box
# --------------------------------------------------------------------------- #

class Quelle(BaseModel):
    """Eine registrierte Quelle des Falls (Bezug: Eingang-Register)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    datei: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    art: Literal["tarifmeldung", "tarifrechner", "bestand"]


class Merkmalsdimension(BaseModel):
    """Eine Differenzierungs-Dimension des Tarifs (z. B. Tarifart)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    auspraegungen: List[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _eindeutig(self) -> "Merkmalsdimension":
        if len(set(self.auspraegungen)) != len(self.auspraegungen):
            raise ValueError(f"Dimension {self.id}: doppelte Auspraegungen")
        for a in self.auspraegungen:
            if not a or a != a.lower():
                raise ValueError(
                    f"Dimension {self.id}: Auspraegung {a!r} nicht "
                    "kleingeschrieben (IDs, keine Anzeigetexte)"
                )
        return self


class Parametrierungszelle(BaseModel):
    """Eine Merkmalskombination mit ihren Rechnungsgrundlagen.

    Jede Zelle mappt vollstaendig auf die Stellschrauben des
    Kern-ModelPoints — "neue Tarifgeneration = Parametrierung, keine
    Formelaenderung" ist die Grundannahme; was sie sprengt, gehoert
    als Erweiterungsstelle in die Spez, nicht hierher.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    auspraegungen: Dict[str, str] = Field(default_factory=dict)
    parameter: Dict[str, Aussage] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _konsistenz(self) -> "Parametrierungszelle":
        if self.id != zellen_segment(self.auspraegungen):
            raise ValueError(
                f"Zellen-ID {self.id!r} passt nicht zu den Auspraegungen "
                f"(erwartet {zellen_segment(self.auspraegungen)!r}) — die "
                "ID ist abgeleitet, nicht frei"
            )
        unbekannt = set(self.parameter) - BEKANNTE_PARAMETER
        if unbekannt:
            raise ValueError(
                f"Zelle {self.id}: unbekannte Parameter {sorted(unbekannt)} "
                "— kein stiller Tippfehler-Parameter; T-Box erweitern (A-O1) "
                "oder Feldname korrigieren"
            )
        return self


class Tarifgeneration(BaseModel):
    """Eine Tarifgeneration einer Produktfamilie (der Fachknoten)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)          # z. B. "klv/tg2015"
    name: str = Field(min_length=1)        # z. B. "TG2015"
    familie: Literal["klv"]                # ABOX_FAMILIEN
    quellen: List[Quelle] = Field(min_length=1)
    dimensionen: List[Merkmalsdimension] = Field(default_factory=list)
    zellen: List[Parametrierungszelle] = Field(min_length=1)
    #: Unisex-Kalkulationsvorgabe (z. B. "U70" = 70 % Maenneranteil);
    #: None = geschlechtsspezifisch. Fachliche Aussage der Meldung.
    unisex: Optional[Aussage] = None
    #: Tarifwerk der Generation (:data:`TARIFWERK_MERKMALE`), je Merkmal eine
    #: Aussage mit Provenienz — typisch aus dem Bedingungswerk. Ein Merkmal,
    #: das fehlt, ist NICHT die Vorgabe des eigenen Geschaefts, sondern nicht
    #: erhoben; die Coverage weist es aus.
    tarifwerk: Dict[str, Aussage] = Field(default_factory=dict)
    #: Verfahren der Quelle (:data:`QUELLVERFAHREN_WERTE`): wie die
    #: abgebende Gesellschaft gelieferte Vorgaenge gemeint hat.
    quellverfahren: Dict[str, Aussage] = Field(default_factory=dict)
    #: Quellname -> Zielfeld (fremde Benennungslogik der Quelle wird
    #: erfasst, nicht normalisiert weggeworfen), z. B. "StoAb_rel" ->
    #: "parameter:stoab_satz". F1-Anforderung der Fragerunde.
    quellnamen: Dict[str, str] = Field(default_factory=dict)
    #: Beobachtungen der Extraktions-Agenten, die kein Schemafeld haben
    #: (z. B. Tarifsubstanz ausserhalb des Pflichtumfangs wie beta0) —
    #: sie gehoeren ins A-Q1-Dokument, nicht in den Papierkorb des Merge
    #: (Systempruefung Befunde 9/30).
    anmerkungen: List[str] = Field(default_factory=list)

    def block(self, name: str) -> Dict[str, Aussage]:
        """Ein Block generationsweiter Aussagen (:data:`GENERATIONS_BLOECKE`)."""
        return getattr(self, name)

    @model_validator(mode="after")
    def _konsistenz(self) -> "Tarifgeneration":
        erwartete_id = knoten_id(self.familie, self.name.lower())
        if self.id != erwartete_id:
            raise ValueError(
                f"Generations-ID {self.id!r} weicht von {erwartete_id!r} ab"
            )
        for block, werte in GENERATIONS_BLOECKE.items():
            unbekannt = set(self.block(block)) - set(werte)
            if unbekannt:
                raise ValueError(
                    f"{self.id}: unbekannte Merkmale im {BLOCK_TITEL[block]} "
                    f"{sorted(unbekannt)} (bekannt: {list(werte)}) — T-Box "
                    "erweitern (A-O1) oder Merkmalsnamen korrigieren"
                )
        dim_ids = [d.id for d in self.dimensionen]
        if len(set(dim_ids)) != len(dim_ids):
            raise ValueError(f"{self.id}: doppelte Dimensions-IDs")
        # Zellen decken das kartesische Produkt exakt ab — eine fehlende
        # Kombination waere eine stillschweigend unparametrierte Zelle (P6).
        erwartet = {zellen_segment(kombi) for kombi in _kartesisch(self.dimensionen)}
        vorhanden = [z.id for z in self.zellen]
        if len(set(vorhanden)) != len(vorhanden):
            raise ValueError(f"{self.id}: doppelte Zellen")
        fehlt = erwartet - set(vorhanden)
        fremd = set(vorhanden) - erwartet
        if fehlt or fremd:
            raise ValueError(
                f"{self.id}: Zellen decken den Merkmalsraum nicht — "
                f"fehlend {sorted(fehlt)}, unbekannt {sorted(fremd)}"
            )
        for zelle in self.zellen:
            for dim_id, wert in zelle.auspraegungen.items():
                dim = next((d for d in self.dimensionen if d.id == dim_id), None)
                if dim is None:
                    raise ValueError(
                        f"{self.id}/{zelle.id}: unbekannte Dimension {dim_id!r}"
                    )
                if wert not in dim.auspraegungen:
                    raise ValueError(
                        f"{self.id}/{zelle.id}: {wert!r} ist keine "
                        f"Auspraegung von {dim_id}"
                    )
        return self


def block_knoten(generation_id: str, block: str) -> str:
    """Der Knoten, an dem ein Widerspruch eines Blocks Diskrepanz wird."""
    return f"{generation_id}/{block}"


def _kartesisch(dimensionen: List[Merkmalsdimension]) -> List[Dict[str, str]]:
    kombis: List[Dict[str, str]] = [{}]
    for dim in sorted(dimensionen, key=lambda d: d.id):
        kombis = [
            {**kombi, dim.id: a} for kombi in kombis for a in dim.auspraegungen
        ]
    return kombis


class ABox(BaseModel):
    """Die Instanzen eines Migrationsfalls — SSOT fuer Stage 2 und 3."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = ABOX_SCHEMA_VERSION
    tbox_version: str = TBOX_VERSION
    fall: str = Field(min_length=1)
    generationen: List[Tarifgeneration] = Field(default_factory=list)
    diskrepanzen: List[Diskrepanz] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Das Vokabular als Ganzes — und sein Abdruck
# --------------------------------------------------------------------------- #

def _felder(modell: type) -> Dict[str, Any]:
    """Feldnamen und Literal-Wertebereiche einer Klasse — keine Prosa, keine
    Typ-Darstellung (die aendert sich mit der Python-Version, das
    Vokabular nicht)."""
    ergebnis: Dict[str, Any] = {}
    for name, feld in sorted(modell.model_fields.items()):
        literale = (list(typing.get_args(feld.annotation))
                    if typing.get_origin(feld.annotation) is Literal else None)
        ergebnis[name] = {"pflicht": feld.is_required(), "literale": literale}
    return ergebnis


def vokabular() -> Dict[str, Any]:
    """Das Vokabular dieser T-Box als JSON-faehiges Objekt.

    Traegt alle Begriffe, Wertebereiche und die Felder der Klassen (A-Box und
    Extraktionsvertrag) — nicht die Version selbst und keine Beschreibungen.
    Grundlage des Abdrucks und des Aenderungsvermerks einer Hebung.
    """
    from rechner_pipeline.ontologie.befuellung import FragmentZelle, QuellFragment

    return {
        "rechnungsgrundlagen": {
            "pflicht": list(PFLICHT_PARAMETER),
            "optional": list(OPTIONALE_PARAMETER),
            "je_familie": {k: list(v) for k, v in RECHNUNGSGRUNDLAGEN_JE_FAMILIE.items()},
        },
        "produktfamilien": {
            "familien": sorted(PRODUKTFAMILIEN),
            "abox_familien": list(ABOX_FAMILIEN),
            "zustaende": {k: list(v) for k, v in ZUSTAENDE_JE_FAMILIE.items()},
            "leistungsgroesse": dict(LEISTUNGSGROESSE_JE_FAMILIE),
        },
        "tarifwerk": {
            "merkmale": list(TARIFWERK_MERKMALE),
            "werte": {k: list(v) for k, v in TARIFWERK_WERTE.items()},
            "eigenes_geschaeft": dict(TARIFWERK_EIGENES_GESCHAEFT),
        },
        "quellverfahren": {
            "werte": {k: _bereich_vokabular(v) for k, v in QUELLVERFAHREN_WERTE.items()},
            "absetzungscode": QUELL_ABSETZUNGSCODE,
            "teilkuendigung": TEILKUENDIGUNG_VERFAHREN,
        },
        "bestand_pflicht": {k: list(v) for k, v in BESTAND_PFLICHT.items()},
        "bestand_erhoben": {k: list(v) for k, v in BESTAND_ERHOBEN.items()},
        "geschaeftsvorfaelle": {
            "katalog": [g.model_dump(mode="json") for g in GESCHAEFTSVORFAELLE.values()],
            "absetzung": list(ABSETZUNG_VORGAENGE),
        },
        "vertrag": {
            "status": sorted(VERTRAGSSTATUS),
            "aktiv": list(AKTIVE_STATUS),
            "terminal": list(TERMINALE_STATUS),
            "geschlechter": list(GESCHLECHTER),
            "zahlweisen": list(ZAHLWEISEN),
            "pflicht": list(VERTRAG_PFLICHT),
            "optional": list(VERTRAG_OPTIONAL),
        },
        "migration": {
            "rechnende_vorgaenge": list(QUELL_VORGAENGE_RECHNEND),
            "zustandsextrakt": {k: list(v) for k, v in ZUSTANDSEXTRAKT.items()},
            "zustaende_ta": list(ZUSTAENDE_TA),
            "verankerungszustaende": list(VERANKERUNGSZUSTAENDE),
            "formfunktionen": list(FORMFUNKTIONEN),
        },
        "quelle_arten": list(QUELLE_ARTEN),
        "abox_schema": {
            m.__name__: _felder(m)
            for m in (ABox, Tarifgeneration, Parametrierungszelle,
                      Merkmalsdimension, Quelle)
        },
        "fragment_schema": {
            m.__name__: _felder(m) for m in (QuellFragment, FragmentZelle)
        },
    }


def vokabular_sha256() -> str:
    """Der Abdruck des Vokabulars (kanonisches JSON, SHA-256)."""
    roh = json.dumps(vokabular(), sort_keys=True, ensure_ascii=True,
                     separators=(",", ":"))
    return hashlib.sha256(roh.encode("ascii")).hexdigest()
