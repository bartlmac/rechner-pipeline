"""Portfolio schema for the Bestandsdaten module — tightly coupled to the kernel.

Defines the portfolio (Bestand) schema whose per-contract fields map 1:1 onto
the stable kernel's :class:`rechner_pipeline.kern.ModelPoint` contract, plus
portfolio identity and time axis (coupling decided 2026-08-11: Bestand is real
kernel input). Since the kernel promotion (stable, versioned software in
``rechner_pipeline.kern``), the kernel's ``ModelPoint`` is the contract SSOT;
:data:`MODEL_POINT_FIELDS` is the Bestand-side mirror, kept identical by a
consistency test (``tests/test_kern.py``). Transient, agent-generated kernels
(``generated/``, migration path) must satisfy the same field list.

Design rules (project decisions):

* Schema style follows the repo idiom — plain dataclass/constant definitions
  with ``validate``-style functions returning error lists; no external schema
  library.
* Column names are snake_case after the kernel contract; the DAV reference
  toolchain's UPPER_CASE columns are semantic reference only.
* Per-contract fields carry only what varies per contract. Tariff-generation
  parameters (zins, tafel, cost loadings ...) live in the TOML config and are
  joined into a full ``ModelPoint`` only when the kernel is invoked
  (:func:`model_point_kwargs`).

Knoten: klv, bu
"""

from __future__ import annotations

import dataclasses as _dc
import datetime as _dt
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import numpy as _np

from rechner_pipeline.kern.model_point import ModelPoint as _KernModelPoint

# --------------------------------------------------------------------------- #
# Kernel ModelPoint contract
# --------------------------------------------------------------------------- #

#: The kernel's ``ModelPoint`` field surface (name -> python type name).
#: Contract fields per the KLV kernel generated 2026-07-22; provenance: the
#: workbook's defined names (x=B4, Sex=B5, n=B6, t=B7, VS=B8, zw=B9, Zins=E4,
#: Tafel=E5, alpha=E6, beta1=E7, gamma1=E8, gamma2=E9, gamma3=E10, k=E11,
#: MinAlterFlex=H4, MinRLZFlex=H5) plus the tariff knobs lifted from the
#: sheet's formula literals (Stornoabschlag, Zillmer-Dauer, ratzu-Staffel E12).
MODEL_POINT_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("x", "int"),
    ("sex", "str"),
    ("n", "int"),
    ("t", "int"),
    ("sum_insured", "float"),
    ("zw", "int"),
    ("zins", "float"),
    ("tafel", "str"),
    ("alpha", "float"),
    ("beta1", "float"),
    ("gamma1", "float"),
    ("gamma2", "float"),
    ("gamma3", "float"),
    ("policy_fee", "float"),
    ("min_alter_flex", "int"),
    ("min_rlz_flex", "int"),
    ("stoab_satz", "float"),
    ("stoab_min", "float"),
    ("stoab_max", "float"),
    ("zillmer_dauer", "int"),
    ("ratzu_zw2", "float"),
    ("ratzu_zw4", "float"),
    ("ratzu_zw12", "float"),
)

#: Kernel fields that vary per contract (come from the portfolio row).
CONTRACT_FIELDS: Tuple[str, ...] = ("x", "sex", "n", "t", "sum_insured", "zw")

#: Kernel fields that come from the tariff generation (config), not the row.
GENERATION_FIELDS: Tuple[str, ...] = (
    "zins", "tafel", "alpha", "beta1", "gamma1", "gamma2", "gamma3",
    "policy_fee", "min_alter_flex", "min_rlz_flex",
    "stoab_satz", "stoab_min", "stoab_max", "zillmer_dauer",
    "ratzu_zw2", "ratzu_zw4", "ratzu_zw12",
)

#: Defaults of the kernel's defaulted (tariff-knob) fields — sourced from the
#: ModelPoint SSOT so a generation config may omit them (sheet behaviour).
GENERATION_FIELD_DEFAULTS: Dict[str, Any] = {
    f.name: f.default
    for f in _dc.fields(_KernModelPoint)
    if f.default is not _dc.MISSING
}

#: Allowed values for enum-like columns (module tuples, repo idiom).
SEX_VALUES: Tuple[str, ...] = ("M", "F")
#: Produkte des Bestands (Diskriminator je Vertrag; Kern-Registry-Kennungen).
#: Das Produkt entscheidet, welche Leistungsspalte fuehrt (KLV:
#: ``sum_insured``, BU: ``bu_rente``), welcher ModelPoint gebaut wird und
#: welche Zustaende die Ereignis-Engine simuliert.
PRODUKT_VALUES: Tuple[str, ...] = ("klv", "bu")
#: Full status enum of the Fortschreibung (Ereignis-Engine): POL = active
#: premium-paying, PEX = active paid-up (KLV), BU = active, drawing the
#: disability annuity (BU), STO/TOD/ABL = terminal.
#:
#: Die Herabsetzung ``RED`` steht bewusst NICHT hier. Sie ist wie die
#: dynamische Erhoehung ein Ereignis OHNE Statuswechsel: Der Vertrag
#: bleibt beitragspflichtig (``POL``), nur Summe und Beitrag aendern
#: sich. Ein eigener Status waere eine Aussage ueber den Zustand, die es
#: nicht gibt — ein herabgesetzter Vertrag ist kein anderer Zustand,
#: sondern ein anderer Verlauf.
STATUS_CODE_VALUES: Tuple[str, ...] = ("POL", "PEX", "BU", "STO", "TOD", "ABL")
#: The generator's base portfolio carries only active POL rows.
BASIS_STATUS: Tuple[str, ...] = ("POL",)
#: Statuses that count as in-force at a reporting date.
AKTIVE_STATUS: Tuple[str, ...] = ("POL", "PEX", "BU")
#: Terminal statuses: nothing may follow them in a Statushistorie.
TERMINALE_STATUS: Tuple[str, ...] = ("STO", "TOD", "ABL")
#: Status-Codes, die nur bei einem bestimmten Produkt vorkommen duerfen
#: (Beitragsfreistellung ist KLV-Fachlichkeit, der BU-Leistungsbezug
#: BU-Fachlichkeit) — die Historien-Validierung prueft das je Police.
PRODUKT_STATUS: Dict[str, Tuple[str, ...]] = {
    "klv": ("PEX",) + TERMINALE_STATUS,
    "bu": ("BU", "POL") + TERMINALE_STATUS,
}
ZAHLWEISE_VALUES: Tuple[int, ...] = (1, 2, 4, 12)

# --------------------------------------------------------------------------- #
# Portfolio columns
# --------------------------------------------------------------------------- #

#: Base (Stamm) portfolio columns in canonical order: (name, pandas dtype).
#: Dates are timezone-naive datetime64 in pandas and date32 in Parquet.
STAMM_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("tarif_generation", "object"),
    ("produkt", "object"),           # klv | bu (Kern-Registry-Kennung)
    ("status_id", "int64"),
    ("status_code", "object"),
    ("status_date", "datetime64[ns]"),
    ("sex", "object"),
    ("date_of_birth", "datetime64[ns]"),
    ("entry_age", "int64"),          # -> ModelPoint.x
    ("duration", "int64"),           # -> ModelPoint.n
    ("premium_duration", "int64"),   # -> ModelPoint.t (BU: == duration)
    ("sum_insured", "float64"),      # KLV: -> ModelPoint.sum_insured (BU: 0)
    ("bu_rente", "float64"),         # BU: -> BUModelPoint.bu_rente (KLV: 0)
    ("zahlweise", "int64"),          # -> ModelPoint.zw (BU: 1)
    ("insurance_start", "datetime64[ns]"),
    ("insurance_end", "datetime64[ns]"),
    ("payment_end", "datetime64[ns]"),
    # Wann der Vertrag in DIESE Buecher kam. Beim eigenen Geschaeft ist
    # das der Versicherungsbeginn; bei uebernommenem der
    # Migrationsstichtag — davor stand der Vertrag beim abgebenden
    # Unternehmen. Ohne die Unterscheidung fuehrte der Bestandsbericht
    # eine 2015 abgeschlossene Baldrian-Police ab 2015 in den Buechern
    # der PLV, elf Jahre vor der Uebernahme.
    ("bestandszugang", "datetime64[ns]"),
)

#: Die produktfuehrende Leistungsspalte (Bezugsgroesse der Nachweisung):
#: Versicherungssumme bei KLV, versicherte Jahresrente bei BU. Getrennte
#: Spalten statt einer umgedeuteten — sonst summierten Auswertungen still
#: Versicherungssummen und Jahresrenten zusammen.
LEISTUNGSSPALTE: Dict[str, str] = {"klv": "sum_insured", "bu": "bu_rente"}

#: Columns derived per Auskunfts-Schnitt (never part of the generated base portfolio).
ZEITSCHEIBEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("stichtag", "datetime64[ns]"),
    ("age", "int64"),
    ("months_exp", "int64"),
    ("months_rem", "int64"),
)

#: Status-Journal der Fortschreibung: follow-up status rows per contract.
#: Der Ursprungszustand (status_id 1, POL am Versicherungsbeginn) ist
#: Konvention, kein Datensatz — Journalzeilen beginnen bei status_id 2.
STATUS_HISTORIE_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("status_id", "int64"),
    ("status_code", "object"),
    ("status_date", "datetime64[ns]"),
)

#: Ereignis-Ledger: one row per booked event with its kernel-computed amount.
LEDGER_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("tarif_generation", "object"),
    # GeVo-Code: meist der resultierende status_code, faellt aber davon ab,
    # wo der GeVo einen ANDEREN Zustand herstellt (INV -> BU, REA -> POL)
    # oder gar keinen (ERH/ZUG).
    ("ereignis", "object"),          # PEX|STO|TOD|ABL|ERH|ZUG|INV|REA|RED|TKU
    ("vertragsjahr", "int64"),       # booked anniversary (completed years; ZUG: 0)
    ("status_date", "datetime64[ns]"),
    # Bezugsgroesse des Betrags — je Produkt verschieden: KLV fuehrt
    # Versicherungssummen/Rueckkaufswerte, BU die betroffene Jahresrente.
    ("betrag_art", "object"),        # RKW | VS_bfr | Todesfallleistung | Ablaufleistung | VS_erhoehung | VS_herabsetzung | VS_teilkuendigung | dDK_absorption | RKW_teilkuendigung | Kappung_teilkuendigung | VS (ZUG) | BU_Jahresrente
    ("betrag", "float64"),
    # Woher der BETRAG stammt. Im eigenen Bestand ist er immer
    # ``gerechnet`` — der Kern erzeugt ihn, und das ist der Normalfall.
    # In einem UEBERNOMMENEN Bestand faellt beides auseinander: Die
    # Zugangssumme steht im Abzug (``geliefert``), die beitragsfreie
    # Summe eines mitgebrachten PEX-Zustands dagegen nicht -- die
    # Vorgeschichte fuehrt keine Betraege (Grundsatzdokumentation 9.14),
    # also rechnet das AUFNEHMENDE Unternehmen sie konstruktiv.
    #
    # Das ist richtig so, aber es ist keine Buchung der Gegenseite. Ohne
    # das Merkmal staende sie im Bewegungskonto neben Buchungen, die aus
    # gelieferten Tatsachen stammen, und das Konto verloere genau die
    # Eigenschaft, fuer die man es fuehrt: unterscheiden zu koennen,
    # was belegt ist und was hergeleitet.
    ("betrag_herkunft", "object"),   # geliefert | gerechnet
)

#: Zulaessige Werte von ``betrag_herkunft``.
BETRAG_HERKUNFT = ("geliefert", "gerechnet")

#: GeVo-Codes des Ledgers. ``kennzahlen.EREIGNIS_REIHENFOLGE`` ist die
#: Ausgabereihenfolge DERSELBEN Menge (Test haelt beide deckungsgleich).
EREIGNIS_VALUES: Tuple[str, ...] = (
    "ZUG", "MIG", "ERH", "RED", "TKU", "PEX", "INV", "REA", "STO", "TOD", "ABL",
)
#: Die beiden Geschaeftsvorfaelle, die eine Summe eines laufenden Vertrags
#: senken (Entscheid des Maintainers 2026-10-01, ADR-023): die
#: BEITRAGSHERABSETZUNG ``RED`` (Beitrag auf f, Umwandlung in beitragsfreie
#: Summe, keine Zahlung, nur solange ein Beitrag laeuft) und die
#: TEILKUENDIGUNG ``TKU`` (Summenanteil gekuendigt, Rueckkaufswert
#: ausgezahlt, in jedem Vertragsjahr vor dem Ablauf). Beide registriert die
#: Nebentabelle ``reduktionen``; welcher Vorgang es war, sagt dort das
#: Verfahren (:func:`reduktion_ereignis`) und im Ledger der Code.
REDUKTION_EREIGNISSE: Tuple[str, ...] = ("RED", "TKU")

#: Welche GeVo einen ZUGANG zum Bestand bilden und welche eine LEISTUNG.
#: Die Zuordnung ist fachlich und vom Maintainer abgenommen (2026-09-17);
#: sie steht hier, weil zwei Konsumenten sie brauchen — der Tagesbetrieb
#: fuer die Monatskennzahlen und die Unternehmensseite fuer ihre
#: Bewegungsreihen. Zweimal gefuehrt wuerde sie auseinanderlaufen, sobald
#: jemand eine Art ergaenzt; dann saegten Tabelle und Kennzahl
#: Verschiedenes, beide fuer sich plausibel.
#:
#: Die ANZEIGENAMEN gehoeren nicht hierher: Wie eine Seite "STO"
#: beschriftet (Rueckkauf) ist ihre Sache, welche GeVo eine Leistung ist,
#: nicht.
#:
#: ``PEX`` steht in keiner der beiden Mengen. Eine Beitragsfreistellung
#: ist weder Zugang noch Leistung — sie wandelt um. Zugaenge und
#: Leistungen summieren sich deshalb NICHT auf alle Vorfaelle einer
#: Periode.
ZUGANG_EREIGNISSE: Tuple[str, ...] = ("ZUG", "ERH")
LEISTUNG_EREIGNISSE: Tuple[str, ...] = ("ABL", "STO", "TOD", "INV", "REA")
#: Vorfaelle, die NUR MIT einer Zahlung eine Leistung sind: Ereignis -> die
#: Betragsarten, die die Zahlung tragen. Die Teilkuendigung (``TKU``) zahlt
#: den gekuendigten Grundanteil aus; die Beitragsherabsetzung (``RED``)
#: wandelt nur um und zahlt nie (seit dem Entscheid 2026-10-01 zwei
#: Vorgaenge mit eigenem Code; vorher buchten beide ``RED``). Gezaehlt wird
#: der VORFALL (Police, Ereignis, Wirkungstag), nicht die Zeile (Pruefrunde
#: T27, Befund 15).
LEISTUNG_BEI_ZAHLUNG: Mapping[str, Tuple[str, ...]] = {"TKU": ("RKW_teilkuendigung",)}

#: GeVo, die WEDER Zugang NOCH Leistung sind — je mit Grund. Hier stehen
#: nur begruendete Ausnahmen: Eine Liste, die Ausnahmen und Versehen
#: mischt, sagt nicht mehr, ob sie waechst, weil es mehr Ausnahmen gibt
#: oder weil jemand eine Zuordnung vergessen hat. Ein Test haelt sie
#: gegen EREIGNIS_VALUES, damit ein neuer Code eingeordnet oder hier
#: benannt werden MUSS.
WEDER_ZUGANG_NOCH_LEISTUNG: Mapping[str, str] = {
    "PEX": "Beitragsfreistellung wandelt um, sie zahlt nicht aus und "
           "bringt nichts hinzu",
    "RED": "Beitragsherabsetzung senkt Beitrag und Summe eines laufenden "
           "Vertrags und wandelt um; sie zahlt nicht aus und bringt nichts "
           "hinzu (die Teilkuendigung, die auszahlt, ist TKU)",
    "TKU": "Teilkuendigung senkt die Summe und zahlt den gekuendigten Anteil "
           "aus; als Leistung zaehlt der Vorfall ueber LEISTUNG_BEI_ZAHLUNG, "
           "wenn die Auszahlung positiv ist (eine auf null gekappte zahlt nicht)",
    "MIG": "im Ledger nicht als eigene Art gebucht — ein Migrationszugang "
           "ist ein ZUG mit Quelle 'uebernahme'",
}

#: Welche Bezugsgroesse ein GeVo bucht — die Betragsart ist Teil der
#: Buchung, nicht freier Text: Ein ``STO`` mit ``Todesfallleistung`` oder
#: ein ``ERH`` mit ``RKW`` ist keine andere Sicht, sondern ein Fehler.
#: Zwei Werte, wo zwei Produkte denselben GeVo buchen (KLV-Summe gegen
#: BU-Jahresrente) oder die Uebernahme eine Umbuchung mit der gelieferten
#: Bezugsgroesse bucht (``PEX`` mit ``VS``, gates.bestand_uebernehmen).
#: ``BJB`` ist der Bruttojahresbeitrag: Ein Zugang und eine Erhoehung
#: bewegen nicht nur eine Summe, sondern auch einen Beitrag, und das
#: Neugeschaeft eines Zeitraums wird in beidem gemessen. Er steht als
#: EIGENE Zeile desselben Vorfalls — ein Betrag, eine Art, wie bei jeder
#: anderen Buchung. Die Abgaenge (STO, TOD, ABL) und die
#: Beitragsfreistellung fuehren ihre Beitragswirkung noch nicht; das ist
#: eine bekannte Asymmetrie und der naechste Schritt derselben Sache.
BETRAG_ART_JE_EREIGNIS: Dict[str, Tuple[str, ...]] = {
    "ZUG": ("VS", "BU_Jahresrente", "BJB"),
    "MIG": ("dDK_uebernahme",),
    "ERH": ("VS_erhoehung", "BJB"),
    # Beitragsherabsetzung: die neue Gesamtsumme, und — bei einem
    # uebernommenen Vertrag — die Korrekturschicht, die in die
    # Neuberechnung eingegangen ist. Eine Umbuchung ohne Zahlung, wie
    # dDK_uebernahme beim Zugang.
    "RED": ("VS_herabsetzung", "dDK_absorption"),
    # Teilkuendigung (eigener Vorfall seit 2026-10-01; Bedingungswerk
    # Ziffer 6, Bauauftrag T26-12): die neue Gesamtsumme, die absorbierte
    # Schicht, die Auszahlung des gekuendigten Grundanteils (Rueckkaufswert
    # plus Schicht, eine Zahlung wie RKW) und — nur wenn die Auszahlung auf
    # null gekappt wurde — der gekappte Betrag, positiv, eine Umbuchung
    # zulasten des Unternehmens.
    "TKU": ("VS_teilkuendigung", "dDK_absorption", "RKW_teilkuendigung",
            "Kappung_teilkuendigung"),
    "PEX": ("VS_bfr", "VS"),
    "INV": ("BU_Jahresrente",),
    "REA": ("BU_Jahresrente",),
    "STO": ("RKW",),
    "TOD": ("Todesfallleistung", "BU_Jahresrente"),
    "ABL": ("Ablaufleistung", "BU_Jahresrente"),
}

#: Welchen Zustand ein GeVo herstellt (Historienzeile desselben Datums).
#: ERH, RED, TKU, ZUG und MIG stellen keinen her: Sie aendern Summe, Beitrag
#: oder Zugehoerigkeit, nicht den Zustand.
EREIGNIS_ZUSTAND: Dict[str, str] = {
    "PEX": "PEX", "STO": "STO", "TOD": "TOD", "ABL": "ABL",
    "INV": "BU", "REA": "POL",
}

#: Welche Erfahrungsannahme (``bestand.config.Annahmen``) welches GeVo des
#: Ledgers zieht: Annahmenfeld -> (Produkt, Ereignis). Runde E, Klasse
#: geschlossen ("Bindung Ereignisart -> Rate"): Die Bindung der Herabsetzung
#: an ihre Rate (Runde C, RC05) war der erste Fall einer Regel, die fuer JEDE
#: Ereignisart gilt — eine Config, deren Annahme ein Ereignis nicht erzeugen
#: kann, belegt keine gebuchte Zeile dieser Art. Die Menge der Schluessel ist
#: die Menge der Annahme-Felder der Dataclass; ein Test haelt beide mit ``==``
#: gleich, damit ein neues Annahmenfeld hier eingeordnet werden MUSS.
#:
#: ``aktivensterblichkeit`` und ``invalidensterblichkeit`` ziehen beide ``TOD``
#: des BU-Produkts; welche gilt, entscheidet der Zustand VOR dem Ereignis
#: (:data:`BU_TOD_JE_ZUSTAND`).
ANNAHME_ERZEUGT: Mapping[str, Tuple[str, str]] = {
    "tod": ("klv", "TOD"),
    "storno": ("klv", "STO"),
    "beitragsfreistellung": ("klv", "PEX"),
    "erhoehung": ("klv", "ERH"),
    "herabsetzung": ("klv", "RED"),
    "teilkuendigung": ("klv", "TKU"),
    "invalidisierung": ("bu", "INV"),
    "reaktivierung": ("bu", "REA"),
    "aktivensterblichkeit": ("bu", "TOD"),
    "invalidensterblichkeit": ("bu", "TOD"),
}

#: (Produkt, Ereignis), das von MEHR als einer Annahme gezogen wird — dort
#: entscheidet der Zustand vor dem Ereignis. Aus :data:`ANNAHME_ERZEUGT`
#: abgeleitet, nicht abgetippt.
ZUSTANDSABHAENGIG: frozenset = frozenset(
    pe for pe in ANNAHME_ERZEUGT.values()
    if list(ANNAHME_ERZEUGT.values()).count(pe) > 1)

#: BU-Tod: welche Annahme zieht ihn, je nachdem, ob der Vertrag vor dem
#: Ereignis im Leistungsbezug stand (Schluessel True) oder Anwaerter war.
BU_TOD_JE_ZUSTAND: Mapping[bool, str] = {
    False: "aktivensterblichkeit",
    True: "invalidensterblichkeit",
}

#: Annahmen mit einer Rechnungsgrundlage erster Ordnung: Die Rate ist
#: ``a + b * q`` (q die Wahrscheinlichkeit der Tafel), sie ist nur dann
#: sicher null, wenn ``a`` UND ``b`` null sind. Alle anderen ziehen mit
#: ``annahme(0.0)`` — dort ist ``b`` ohne Wirkung (TOML-Default b = 1 ist
#: kein Zeichen einer Rate). Die Engine ruft sie so (``ereignisse``).
ANNAHME_MIT_ERSTER_ORDNUNG: frozenset = frozenset({
    "tod", "invalidisierung", "reaktivierung",
    "aktivensterblichkeit", "invalidensterblichkeit",
})

#: Ereignisse, die aus KEINER Annahme gezogen werden — je mit Grund. Stehen
#: nur begruendete Ausnahmen hier; ein Test haelt die Menge zusammen mit
#: den Zielen von :data:`ANNAHME_ERZEUGT` gleich ``EREIGNIS_VALUES``.
EREIGNIS_OHNE_ANNAHME: Mapping[str, str] = {
    "ZUG": "Zugang: Neugeschaeft oder Uebernahme, keine Erfahrungsannahme",
    "MIG": "Residuum der Uebernahme, eine Rechnung und kein Ereignis",
    "ABL": "Ablauf folgt aus der Laufzeit des Vertrags, nicht aus einer Rate",
}


class EreignisOhneZuordnung(ValueError):
    """Ein (Produkt, Ereignis)-Paar ist weder Ziel einer Annahme noch
    Ausnahme (Runde E, Nachbesserung)."""


def ereignis_zuordnungsfehler(produkt: str, ereignis: str) -> Optional[str]:
    """Der Befundtext, wenn das Paar (Produkt, Ereignis) weder das Ziel einer
    Annahme (:data:`ANNAHME_ERZEUGT`) noch eine Ausnahme
    (:data:`EREIGNIS_OHNE_ANNAHME`) ist — sonst None.

    Runde E, Nachbesserung: ``annahme_fuer_ereignis`` gab fuer ein solches
    Paar still None zurueck, und ``None`` heisst "Ausnahme, keine Annahme".
    Ein Produkt, das eine neue Ereignisart bucht (oder ein Ledger, das eine
    Art einem Produkt zuschreibt, das sie nicht kennt, z. B. INV an einer
    KLV-Police), lief so ohne Bindung an irgendeine Rate durch. Die Menge
    der Ausnahmen gilt fuer alle Produkte; die Ziele sind je Produkt."""
    if ereignis in EREIGNIS_OHNE_ANNAHME:
        return None
    if any(pe == (produkt, ereignis) for pe in ANNAHME_ERZEUGT.values()):
        return None
    return (f"Ereignis {ereignis} fuer Produkt {produkt} ist keiner Annahme und "
            "keiner Ausnahme zugeordnet — in ANNAHME_ERZEUGT oder "
            "EREIGNIS_OHNE_ANNAHME eintragen")


def annahme_fuer_ereignis(
    produkt: str, ereignis: str, im_leistungsbezug: bool = False
) -> Optional[str]:
    """Das Annahmenfeld, das dieses GeVo des Produkts zieht — oder None,
    wenn es aus keiner Annahme gezogen wird (:data:`EREIGNIS_OHNE_ANNAHME`).
    Ein Paar, das weder Ziel noch Ausnahme ist, wirft
    :class:`EreignisOhneZuordnung` (fail-fast mit Ausweg, der Text kommt aus
    :func:`ereignis_zuordnungsfehler`) — ``None`` ist nur noch die benannte
    Ausnahme. Ledgerweit meldet es :func:`unzugeordnete_ereignisse`."""
    fehler = ereignis_zuordnungsfehler(produkt, ereignis)
    if fehler is not None:
        raise EreignisOhneZuordnung(fehler)
    treffer = [f for f, pe in ANNAHME_ERZEUGT.items() if pe == (produkt, ereignis)]
    if len(treffer) > 1:
        return BU_TOD_JE_ZUSTAND[bool(im_leistungsbezug)]
    return treffer[0] if treffer else None


def unzugeordnete_ereignisse(stamm: Any, ledger: Any) -> List[str]:
    """Befunde zu Ledgerzeilen, deren (Produkt, Ereignis)-Paar weder Ziel einer
    Annahme noch Ausnahme ist: je Paar ein Text mit Zeilenzahl und Policen.

    Dieselbe Regel fuer P-B1 und die Fuehrungsprobe (Runde E, Nachbesserung).
    Sie gilt fuer JEDE Zeile, unabhaengig von Raten, Zugang und Horizont —
    ob eine Art einem Produkt ueberhaupt zugeordnet ist, ist keine Frage des
    Ortes. Das Produkt einer Police steht im Stamm (``produkt``; ohne die
    Spalte gilt ``klv``, wie in :func:`unbelegte_ereignisse`); Policen
    ausserhalb des Stamms pruefen andere Regeln."""
    if len(ledger) == 0:
        return []
    produkt_je = (stamm.set_index("police_id")["produkt"].astype(str).to_dict()
                  if "produkt" in stamm.columns else {})
    bekannt = set(int(p) for p in stamm["police_id"])
    gefunden: Dict[Tuple[str, str], List[int]] = {}
    zeilen = ledger[["police_id", "ereignis"]].drop_duplicates()
    anzahl = ledger.groupby(["police_id", "ereignis"]).size().to_dict()
    for pid, art in zip(zeilen["police_id"], zeilen["ereignis"]):
        if int(pid) not in bekannt:
            continue
        paar = (produkt_je.get(int(pid), "klv"), str(art))
        if ereignis_zuordnungsfehler(*paar) is not None:
            gefunden.setdefault(paar, []).extend([int(pid)] * int(anzahl[(pid, art)]))
    befunde = []
    for (produkt, art), policen in sorted(gefunden.items()):
        beispiele = ", ".join(str(p) for p in sorted(set(policen))[:3])
        befunde.append(
            f"ledger: {ereignis_zuordnungsfehler(produkt, art)} ({len(policen)} "
            f"Zeile(n), police {beispiele}{' ...' if len(set(policen)) > 3 else ''})")
    return befunde


def annahme_erzeugt_nicht(annahmen: Any, feld: str) -> bool:
    """Die Annahme kann ihr Ereignis nicht erzeugen (Rate null)."""
    annahme = getattr(annahmen, feld)
    if feld in ANNAHME_MIT_ERSTER_ORDNUNG:
        return not (float(annahme.a) or float(annahme.b))
    return not float(annahme(0.0))


def unbelegte_ereignisse(
    stamm: Any,
    ledger: Any,
    annahmen: Any,
    *,
    leistungsbezug: Optional[Any] = None,
) -> Dict[str, List[Tuple[int, int]]]:
    """Gebuchte Fortschreibungszeilen, die ihre Erfahrungsannahme nicht
    erzeugen kann: Annahmenfeld -> [(Police, Vertragsjahr), ...].

    Runde E, Klasse geschlossen ("Bindung Ereignisart -> Rate"): Die Engine
    zieht jedes Ereignis aus einer Annahme der Config
    (:data:`ANNAHME_ERZEUGT`); eine Annahme mit Rate null
    kann es nicht gezogen haben. Vorher band nur die Herabsetzung ihre Rate
    (Runde C, RC05) — eine Config ohne Storno-, Beitragsfreistellungs-,
    Erhoehungs- oder Sterblichkeitsannahme belegte trotzdem jede
    Storno-, PEX-, ERH- und TOD-Zeile des Ledgers, und der Lauf galt als
    durch die Config erzeugt, die ihn nicht erzeugt hat.

    Geprueft werden die Buchungen NACH dem Bestandszugang des Vertrags; was
    am oder vor dem Zugangstag steht, schreibt die Uebernahme und faellt
    unter die Regel des Buchungsfensters
    (:func:`buchungsfenster_verstoesse`). Ereignisse ohne
    Annahme (:data:`EREIGNIS_OHNE_ANNAHME`) sind ausgenommen.
    Beim BU-Tod entscheidet der Zustand VOR dem Ereignis
    (``leistungsbezug(police, datum) -> bool``, aus der Statushistorie: P-B1
    gibt ``ledger_bindung.zustand_vor`` mit), ob die Sterblichkeit des
    Anwaerters oder des Leistungsbeziehers die Rate ist. Ohne Angabe gilt der
    Anwaerter — die Fuehrungsprobe ist ein KLV-Werkzeug.

    Jede Art hat genau EINE erzeugende Annahme je Zustand. Der fruehere
    zweite Weg der Teilkuendigung (Herabsetzungswunsch des uebernommenen
    Tarifs, Annahme A1) ist mit dem Entscheid vom 2026-10-01 entfallen.
    """
    import pandas as pd

    if len(ledger) == 0:
        return {}
    null_felder = {f for f in ANNAHME_ERZEUGT if annahme_erzeugt_nicht(annahmen, f)}
    if not null_felder:
        return {}
    arten = {ANNAHME_ERZEUGT[f][1] for f in null_felder}
    kandidaten = ledger[ledger["ereignis"].isin(arten)]
    if len(kandidaten) == 0:
        return {}
    haupt = stamm.set_index("police_id")
    produkt_je = haupt["produkt"].astype(str).to_dict() if "produkt" in haupt.columns else {}
    zugang_je = haupt["bestandszugang"].to_dict()
    treffer: Dict[str, set] = {}
    for z in kandidaten.itertuples(index=False):
        pid = int(z.police_id)
        if pid not in zugang_je or pd.Timestamp(z.status_date) <= pd.Timestamp(zugang_je[pid]):
            continue
        produkt = produkt_je.get(pid, "klv")
        art = str(z.ereignis)
        im_bezug = ((produkt, art) in ZUSTANDSABHAENGIG
                    and leistungsbezug is not None
                    and bool(leistungsbezug(pid, pd.Timestamp(z.status_date))))
        if ereignis_zuordnungsfehler(produkt, art) is not None:
            continue      # ohne Zuordnung: Befund von unzugeordnete_ereignisse
        feld = annahme_fuer_ereignis(produkt, art, im_bezug)
        if feld in null_felder:
            treffer.setdefault(feld, set()).add((pid, int(z.vertragsjahr)))
    return {f: sorted(v) for f, v in treffer.items()}


def unbelegte_ereignisse_text(feld: str, eintraege: List[Tuple[int, int]]) -> str:
    """Die Meldung zu einem Annahmenfeld — dieselbe fuer P-B1 und die
    Fuehrungsprobe."""
    art = ANNAHME_ERZEUGT[feld][1]
    beispiele = "; ".join(f"police {p} Jahr {j}" for p, j in eintraege[:3])
    return (
        f"ledger: {len(eintraege)} {art}-Buchung(en), die die Annahmen nicht "
        f"erzeugen koennen (annahmen.{feld}: die Rate ist null) — z. B. "
        f"{beispiele}{' ...' if len(eintraege) > 3 else ''}. Ein Ereignis, "
        "das die Erfahrungsannahme der Config nicht zieht, ist keine Buchung "
        "dieses Laufs; Ausweg: die Config angeben, mit der der Lauf entstand, "
        "oder die Buchung streichen")


#: Ereignisse, die AM Zugangstag eines Vertrags stehen duerfen — je mit
#: Grund. Runde E, Klasse geschlossen ("Buchungsfenster"): Jede
#: Fortschreibungsbuchung liegt echt NACH dem Bestandszugang; am Zugangstag
#: selbst stehen nur die Buchungen, die der Zugang schreibt.
ZUGANGSTAG_EREIGNISSE: Mapping[str, str] = {
    "ZUG": "die Zugangsbuchung selbst",
    "MIG": "Residuum der Uebernahme, gebucht zum Zugangsstichtag",
    "PEX": "Umbuchung eines beitragsfrei uebernommenen Vertrags zum "
           "Zugangsstichtag (nur bei uebernommenem Vertrag)",
}

#: Teilmenge von :data:`ZUGANGSTAG_EREIGNISSE`, die nur bei einem
#: UEBERNOMMENEN Vertrag (Bestandszugang nach Versicherungsbeginn) am
#: Zugangstag stehen darf: Beim eigenen Geschaeft gibt es am Beginn keine
#: Umbuchung eines mitgebrachten Zustands.
ZUGANGSTAG_NUR_UEBERNOMMEN: Tuple[str, ...] = ("PEX",)

#: Die gelieferte Vorgeschichte eines uebernommenen Vertrags steht in der
#: Statushistorie, NICHT im Ledger (Grundsatzdokumentation 9.14; der
#: Migrationszugang bucht nur Zugang, Umbuchung und Residuum zum
#: Stichtag). Eine Ledgerzeile VOR dem Bestandszugang hat deshalb keine
#: Ausnahme: Was die abgebende Gesellschaft erlebt hat, ist im Journal des
#: aufnehmenden Unternehmens keine Bewegung.

#: Ereignisse, die HINTER dem Horizont stehen duerfen, wenn sie am Zugangstag
#: des Vertrags liegen — je mit Grund. Der Horizont des Laufs ist das Datum,
#: bis zu dem er Jahrestage simuliert hat; ein Neugeschaeft, dessen Beginn
#: auf den Monatsersten NACH dem Laufdatum faellt (Antrag heute, Beginn
#: morgen), ist im Bestand und damit im Ledger, ohne dass der Lauf ein
#: Vertragsjahr gefahren hat (Tageslauf, Erstbefuellung bis 31.1. mit Beginn
#: 1.2.). Es ist der Zugang selbst; jede andere Buchung dahinter ist
#: unbelegt.
#:
#: Die Ausnahme ist nach oben BEGRENZT (Runde E, Nachbesserung): Ein Vertrag
#: beginnt am Monatsersten STRENG nach dem Verkaufstag, also hoechstens am
#: ersten Monatsersten nach dem Horizont (:func:`monatserster_nach`). Ein
#: Zugang, der weiter dahinter steht, ist kein Neugeschaeft dieses Laufs.
ZUGANG_HINTER_HORIZONT: Mapping[str, str] = {
    "ZUG": "Neugeschaeft mit Beginn nach dem Laufdatum — der Zugang, kein "
           "gefahrenes Vertragsjahr",
}


def monatserster_nach(datum: Any) -> Any:
    """Der erste Monatserste STRENG nach ``datum`` (auch wenn ``datum`` selbst
    ein Monatserster ist): der Beginn eines Vertrags, der an diesem Tag
    verkauft wurde (Tageslauf, ADR-020)."""
    import pandas as pd

    ts = pd.Timestamp(datum)
    return (ts.to_period("M") + 1).to_timestamp()


def zugangsbuchungen(ledger: Any, stamm: Any) -> Any:
    """Je Ledgerzeile: ist sie eine Buchung, die der ZUGANG schreibt? Boolesches
    Feld — die EINE Definition (Pruefrunde I, Fund I10).

    Eine Zugangsbuchung steht am Zugangstag des Vertrags (``status_date`` gleich
    ``bestandszugang``) und ist eine Art aus :data:`ZUGANGSTAG_EREIGNISSE`; die
    Arten aus :data:`ZUGANGSTAG_NUR_UEBERNOMMEN` nur bei einem uebernommenen
    Vertrag (Bestandszugang nach Versicherungsbeginn). Das Merkmal setzt der
    Produzent selbst: ``gates.bestand_uebernehmen`` bucht Zugang und Umbuchung
    zum Zugangsstichtag, die Fortschreibung bucht jeden Vorgang echt NACH dem
    Bestandszugang (:func:`buchungsfenster_verstoesse`).

    Eine solche Zeile uebernimmt einen bestehenden Zustand in die Fuehrung des
    Zielsystems; sie ist kein Vorgang im Zugangsjahr. Ihr ``vertragsjahr`` ist
    das des Zugangs, nicht das des Vorgangs — das Jahr einer mitgebrachten
    Beitragsfreistellung steht in der Statushistorie (``validate_ledger``
    verlangt dort eine Freistellung am oder vor der Umbuchung). Die Policen der
    Zeilen muessen im Stamm stehen.
    """
    stamm_idx = stamm.set_index("police_id")
    pids = ledger["police_id"].to_numpy()
    zugang = stamm_idx.loc[pids, "bestandszugang"].to_numpy()
    beginn = stamm_idx.loc[pids, "insurance_start"].to_numpy()
    datum = ledger["status_date"].to_numpy()
    art = ledger["ereignis"].to_numpy()
    uebernommen = zugang > beginn
    darf_am_tag = _np.isin(art, list(ZUGANGSTAG_EREIGNISSE)) & (
        ~_np.isin(art, list(ZUGANGSTAG_NUR_UEBERNOMMEN)) | uebernommen)
    return (datum == zugang) & darf_am_tag


def buchungsfenster_verstoesse(
    ledger: Any, stamm: Any, horizont: Any = None
) -> Tuple[Any, Any]:
    """Je Ledgerzeile: liegt sie nicht nach dem Bestandszugang, liegt sie
    hinter dem belegten Horizont? Rueckgabe: zwei boolesche Felder.

    Die EINE Regel fuer P-B1 (``validate_ledger``) und die Fuehrungsprobe
    (Runde E, Klasse geschlossen): vorher stand die Wache nur im RED-Block
    und liess STO, TOD, ABL, ERH und PEX vor dem Zugang und hinter dem
    Horizont durch. Die Ausnahmen sind benannt
    (:data:`ZUGANGSTAG_EREIGNISSE`, :data:`ZUGANG_HINTER_HORIZONT`, der
    Zugang hinter dem Horizont hoechstens am Monatsersten nach ihm);
    ``horizont`` None heisst: der Lauf belegt keinen, dann gibt es keine
    obere Grenze. Die Policen der Zeilen muessen im Stamm stehen.
    """
    import pandas as pd

    stamm_idx = stamm.set_index("police_id")
    pids = ledger["police_id"].to_numpy()
    zugang = stamm_idx.loc[pids, "bestandszugang"].to_numpy()
    datum = ledger["status_date"].to_numpy()
    art = ledger["ereignis"].to_numpy()
    am_zugangstag = datum == zugang
    vor_zugang = (datum < zugang) | (am_zugangstag & ~zugangsbuchungen(ledger, stamm))
    if horizont is None:
        hinter = _np.zeros(len(ledger), dtype=bool)
    else:
        grenze = _np.datetime64(monatserster_nach(horizont))
        zugang_darf_dahinter = (_np.isin(art, list(ZUGANG_HINTER_HORIZONT))
                                & am_zugangstag & (datum <= grenze))
        hinter = (datum > _np.datetime64(pd.Timestamp(horizont))) & ~zugang_darf_dahinter
    return vor_zugang, hinter


#: Der Zeitpunkt, an dem ein Ausnahme-Ereignis (aus keiner Annahme gezogen,
#: :data:`EREIGNIS_OHNE_ANNAHME`) im Ledger stehen darf. Runde E,
#: Nachbesserung: ZUG, MIG und ABL waren nach dem Zugang an keinen Zeitpunkt
#: gebunden — eine Ausnahmemenge ohne Wache fuer ihren Grund ist keine
#: geschlossene Klasse. Der Grund steht in :data:`EREIGNIS_OHNE_ANNAHME`; hier
#: steht, was er fuer den Ort der Buchung heisst. Ein Test haelt beide Mengen
#: mit ``==`` gleich, damit ein neues Ausnahme-Ereignis seine Regel bekommen MUSS.
ZEITPUNKT_ZUGANGSTAG = "zugangstag"
ZEITPUNKT_VERTRAGSENDE = "vertragsende"
AUSNAHME_ZEITPUNKT: Mapping[str, str] = {
    "ZUG": ZEITPUNKT_ZUGANGSTAG,       # die Zugangsbuchung steht am Zugang
    "MIG": ZEITPUNKT_ZUGANGSTAG,       # das Residuum der Uebernahme zum Zugangsstichtag
    "ABL": ZEITPUNKT_VERTRAGSENDE,     # der Ablauf folgt aus der Laufzeit
}

#: Ausnahme-Ereignisse, die je Police (und Betragsart) genau einmal stehen: ein
#: Vertrag kommt einmal zu.
AUSNAHME_EINMAL_JE_POLICE: Tuple[str, ...] = ("ZUG",)

#: Ausnahme-Ereignisse, die es nur bei einem UEBERNOMMENEN Vertrag gibt (Zugang
#: nach Versicherungsbeginn): Beim eigenen Geschaeft gibt es kein Residuum einer
#: Uebernahme.
AUSNAHME_NUR_UEBERNOMMEN: Tuple[str, ...] = ("MIG",)


def ausnahme_ereignis_verstoesse(
    ledger: Any, stamm: Any, schon_gemeldet: Any = None
) -> Dict[str, Any]:
    """Je Regel eine boolesche Maske je Ledgerzeile: Regel -> Zeilen, die
    gegen sie verstossen.

    Die EINE Regel fuer P-B1 (``validate_ledger``) und die Fuehrungsprobe
    (Runde E, Nachbesserung). ``zeitpunkt``: die Zeile steht nicht an dem
    Zeitpunkt, den :data:`AUSNAHME_ZEITPUNKT` fuer ihre Art vorsieht
    (Zugangstag des Vertrags; Vertragsende: ``status_date == insurance_end``
    und ``vertragsjahr == duration``). ``einmal``: die Zeile ist eine
    Wiederholung — :data:`AUSNAHME_EINMAL_JE_POLICE` je Police und Betragsart,
    gezaehlt unter den Zeilen am richtigen Zeitpunkt. ``uebernommen``: die Art
    steht an einem eigenen Geschaeft, obwohl sie nur bei einem uebernommenen
    Vertrag vorkommt (:data:`AUSNAHME_NUR_UEBERNOMMEN`).

    ``schon_gemeldet``: Zeilen, die das Buchungsfenster
    (:func:`buchungsfenster_verstoesse`) bereits beanstandet — ein Fehler, ein
    Befund; sie scheiden hier aus. Die Policen der Zeilen muessen im Stamm
    stehen.
    """
    import pandas as pd

    stamm_idx = stamm.set_index("police_id")
    pids = ledger["police_id"].to_numpy()
    zugang = stamm_idx.loc[pids, "bestandszugang"].to_numpy()
    beginn = stamm_idx.loc[pids, "insurance_start"].to_numpy()
    ende = stamm_idx.loc[pids, "insurance_end"].to_numpy()
    dauer = stamm_idx.loc[pids, "duration"].to_numpy()
    datum = ledger["status_date"].to_numpy()
    jahr = ledger["vertragsjahr"].to_numpy()
    art = ledger["ereignis"].to_numpy()
    offen = (_np.ones(len(ledger), dtype=bool) if schon_gemeldet is None
             else ~_np.asarray(schon_gemeldet, dtype=bool))

    hat_regel = _np.isin(art, list(AUSNAHME_ZEITPUNKT))
    zeitpunkt_der_art = _np.array([AUSNAHME_ZEITPUNKT.get(a, "") for a in art], dtype=object)
    am_platz = _np.where(zeitpunkt_der_art == ZEITPUNKT_ZUGANGSTAG,
                         datum == zugang, (datum == ende) & (jahr == dauer))
    zeitpunkt = hat_regel & ~am_platz & offen

    uebernommen = _np.isin(art, list(AUSNAHME_NUR_UEBERNOMMEN)) & ~(zugang > beginn) & offen

    einmal = _np.zeros(len(ledger), dtype=bool)
    kandidat = _np.isin(art, list(AUSNAHME_EINMAL_JE_POLICE)) & offen & ~zeitpunkt
    if kandidat.any():
        schluessel = pd.DataFrame({
            "p": pids[kandidat], "e": art[kandidat],
            "b": ledger["betrag_art"].to_numpy()[kandidat]})
        einmal[_np.flatnonzero(kandidat)] = schluessel.duplicated(keep="first").to_numpy()
    return {"zeitpunkt": zeitpunkt, "einmal": einmal, "uebernommen": uebernommen}


def ausnahme_ereignis_text(regel: str, art: str, policen: List[int]) -> str:
    """Die Meldung zu einem Verstoss gegen eine Ausnahmeregel — dieselbe fuer
    P-B1 (mit dem Praefix ``ledger: ``) und die Fuehrungsprobe. Sie nennt Art,
    Regel, Policen und den Ausweg, und sie teilt keine Woerter mit dem Text
    des Buchungsfensters (ein Fehler, ein Befund, unterscheidbar)."""
    beispiele = ", ".join(str(p) for p in policen[:5])
    if regel == "zeitpunkt":
        if AUSNAHME_ZEITPUNKT[art] == ZEITPUNKT_ZUGANGSTAG:
            was = "steht nicht am Zugangstag des Vertrags"
            soll = f"{EREIGNIS_OHNE_ANNAHME[art]}; sie wird am Zugangstag gebucht"
        else:
            was = ("steht nicht am Vertragsende (status_date gleich insurance_end, "
                   "vertragsjahr gleich duration)")
            soll = f"{EREIGNIS_OHNE_ANNAHME[art]}"
    elif regel == "einmal":
        was = "steht mehr als einmal je Police und Betragsart"
        soll = "ein Vertrag kommt einmal zu"
    elif regel == "uebernommen":
        was = "steht an einem eigenen Geschaeft"
        soll = ("es gibt sie nur bei einem uebernommenen Vertrag (Zugang nach "
                "Versicherungsbeginn)")
    else:
        raise KeyError(regel)
    return (f"{art}-Buchung {was} (police [{beispiele}]) — {soll}. "
            "Ausweg: die Buchung streichen oder an den Platz legen, den der "
            "Erzeuger bucht")

#: Betragsart des gebuchten Bruttojahresbeitrags (Zugang und Erhoehung).
BEITRAG_BETRAG_ART = "BJB"

#: Die Ereignisarten, deren Vorfall einen Beitrag bewegt: HERGELEITET aus dem
#: Vokabular der Betragsarten, nicht abgetippt (Runde F, Klasse "Paarbuchung").
#: Die Engine bucht je solchem Vorfall ein PAAR: die Summenzeile und die
#: Beitragszeile (``BJB``), beide fuer dieselbe Police am selben Tag. Ein Test
#: haelt diese Menge mit ``==`` gegen die Stellen, an denen die Engine
#: (``bestand.ereignisse``) die Beitragszeile bucht — ein neues Beitragsereignis
#: muss hier, im Vokabular und in der Engine zugleich auftauchen.
BEITRAGSEREIGNISSE: Tuple[str, ...] = tuple(
    e for e, arten in BETRAG_ART_JE_EREIGNIS.items() if BEITRAG_BETRAG_ART in arten)

#: Beitragsereignisse, die bei einem UEBERNOMMENEN Vertrag (Bestandszugang nach
#: Versicherungsbeginn) KEINE Beitragszeile buchen — je mit Grund. Der Zugang
#: eines uebernommenen Vertrags bucht nur die gelieferte Summe; sein
#: Jahresbeitrag steht in der Lieferung und laeuft im aktuariellen Test mit
#: (``gates.bestand_uebernehmen``), nicht im Ledger des aufnehmenden
#: Unternehmens. Eine Beitragszeile dort ist keine Buchung des Erzeugers.
BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN: Mapping[str, str] = {
    "ZUG": "der Zugang eines uebernommenen Vertrags bucht nur die gelieferte "
           "Summe; sein Jahresbeitrag steht in der Lieferung",
}

#: Die Verstoesse gegen die Paarbuchung, je Vorfall (Police, Wirkungstag, Art).
PAAR_BJB_ZUVIEL = "bjb_zuviel"
PAAR_BJB_FEHLT = "bjb_fehlt"
PAAR_SUMME_ZUVIEL = "summe_zuviel"
PAAR_SUMME_FEHLT = "summe_fehlt"
PAAR_TAG_VERSCHOBEN = "tag_verschoben"


def beitragspaar_verstoesse(
    ledger: Any, stamm: Any, schon_gemeldet: Any = None
) -> Dict[Tuple[str, str], List[int]]:
    """Je (Ereignisart, Verstoss) die Policen, deren Vorfall die Paarbuchung
    verletzt — Runde F, Klasse "Paarbuchung".

    Die Engine bucht je Vorfall einer Art aus :data:`BEITRAGSEREIGNISSE`
    GENAU eine Summenzeile und GENAU eine Beitragszeile ``BJB`` am selben Tag
    fuer dieselbe Police (bei einem uebernommenen Vertrag fuer die Arten aus
    :data:`BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN` keine Beitragszeile). Vorher
    pruefte P-B1 den BETRAG vorhandener Beitragszeilen und band nur die
    Summenzeile der Erhoehung an ihre Scheibe: Eine verdoppelte oder gestrichene
    Beitragszeile einer Erhoehung (und eine fehlende des Zugangs) bemerkten
    weder P-B1 noch die Fuehrungsprobe, noch der Bericht. Gezaehlt wird je
    Vorfall (Police, Art, Vertragsjahr); die Kennzahlen zaehlen Vorfaelle je
    (Police, Wirkungstag, Art) — beide Einheiten fallen zusammen, solange das
    Paar am selben Tag steht (sonst meldet ``tag_verschoben``).

    Verstoesse: ``bjb_zuviel`` (mehr Beitragszeilen als erlaubt), ``bjb_fehlt``,
    ``summe_zuviel`` (mehr als eine Summenzeile), ``summe_fehlt`` (Beitragszeile
    ohne Summenzeile), ``tag_verschoben`` (Summen- und Beitragszeile desselben
    Vorfalls stehen auf verschiedenen Tagen).
    ``schon_gemeldet``: Zeilen, die eine andere Regel schon beanstandet
    (Buchungsfenster, Ausnahme-Ereignisse, Wirkungstag) — ein Fehler, ein
    Befund; eine gemeldete Zeile nimmt ihren GANZEN Vorfall (Police, Art,
    Vertragsjahr) aus, die Partnerzeile bringt keinen zusaetzlichen Befund.
    Ein in der Zeit getrenntes Paar (Teilverschiebung) ist EIN Befund fuer den
    Vorfall (``tag_verschoben``), nicht 'Beitragszeile fehlt' und 'Summenzeile
    fehlt' zugleich; ein Paar in zwei Vertragsjahren sind zwei unvollstaendige
    Vorfaelle. Die Policen der Zeilen muessen im Stamm stehen.
    """
    import pandas as pd

    art = ledger["ereignis"].to_numpy()
    beitrag = _np.isin(art, list(BEITRAGSEREIGNISSE))
    if not beitrag.any():
        return {}
    gemeldet = (_np.zeros(len(ledger), dtype=bool) if schon_gemeldet is None
                else _np.asarray(schon_gemeldet, dtype=bool))
    alle = pd.DataFrame({
        "police": ledger["police_id"].to_numpy()[beitrag].astype("int64"),
        "art": art[beitrag],
        "jahr": ledger["vertragsjahr"].to_numpy()[beitrag].astype("int64"),
        "tag": ledger["status_date"].to_numpy()[beitrag],
        "bjb": (ledger["betrag_art"].to_numpy()[beitrag] == BEITRAG_BETRAG_ART),
        "gemeldet": gemeldet[beitrag],
    })
    # Der Vorfall ist (Police, Art, Vertragsjahr): Die Engine bucht je Vertragsjahr
    # EIN Paar. Meldet eine andere Regel EINE Zeile des Vorfalls, scheidet der
    # ganze Vorfall hier aus — die Partnerzeile bringt keinen zusaetzlichen
    # Befund (Runde F, Nachbesserung: ein Vorfall, ein Befund).
    schluessel = ["police", "art", "jahr"]
    zeilen = alle[~alle.groupby(schluessel)["gemeldet"].transform("any")]
    if zeilen.empty:
        return {}
    je_vorfall = zeilen.groupby(schluessel, sort=True).agg(
        n_bjb=("bjb", "sum"), n=("bjb", "size"), n_tage=("tag", "nunique")).reset_index()
    je_vorfall["n_summe"] = je_vorfall["n"] - je_vorfall["n_bjb"]
    # Summen- und Beitragszeile eines Vorfalls auf verschiedenen Tagen: EIN
    # Befund fuer den ganzen Vorfall, die Anzahlregeln gelten dort nicht.
    getrennt = je_vorfall["n_tage"].to_numpy() > 1
    stamm_idx = stamm.set_index("police_id")
    uebernommen = (
        stamm_idx.loc[je_vorfall["police"].to_numpy(), "bestandszugang"].to_numpy()
        > stamm_idx.loc[je_vorfall["police"].to_numpy(), "insurance_start"].to_numpy())
    ohne_bjb = uebernommen & je_vorfall["art"].isin(
        list(BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN)).to_numpy()
    soll_bjb = _np.where(ohne_bjb, 0, 1)
    ist_bjb = je_vorfall["n_bjb"].to_numpy()
    ist_summe = je_vorfall["n_summe"].to_numpy()
    faelle = {
        PAAR_BJB_ZUVIEL: (ist_bjb > soll_bjb) & ~getrennt,
        PAAR_BJB_FEHLT: (ist_bjb < soll_bjb) & ~getrennt,
        PAAR_SUMME_ZUVIEL: (ist_summe > 1) & ~getrennt,
        PAAR_SUMME_FEHLT: (ist_summe < 1) & ~getrennt,
        PAAR_TAG_VERSCHOBEN: getrennt,
    }
    aus: Dict[Tuple[str, str], List[int]] = {}
    for verstoss, maske in faelle.items():
        for a in sorted(set(je_vorfall.loc[maske, "art"])):
            zeile = maske & (je_vorfall["art"] == a).to_numpy()
            aus[(str(a), verstoss)] = sorted(set(
                int(p) for p in je_vorfall.loc[zeile, "police"]))
    return aus


def beitragspaar_text(art: str, verstoss: str, policen: List[int]) -> str:
    """Die Meldung zu einem Verstoss gegen die Paarbuchung — dieselbe fuer
    P-B1 (mit dem Praefix ``ledger: ``) und die Fuehrungsprobe."""
    beispiele = ", ".join(str(p) for p in policen[:5])
    was = {
        PAAR_BJB_ZUVIEL: "mehr Beitragszeilen (BJB) als der Vorfall bucht",
        PAAR_BJB_FEHLT: "ohne die Beitragszeile (BJB) des Vorfalls",
        PAAR_SUMME_ZUVIEL: "mit mehr als einer Summenzeile",
        PAAR_SUMME_FEHLT: "mit Beitragszeile (BJB) ohne Summenzeile",
        PAAR_TAG_VERSCHOBEN: "mit Summen- und Beitragszeile auf verschiedenen Tagen",
    }[verstoss]
    if art in BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN and verstoss == PAAR_BJB_ZUVIEL:
        grund = " (bei einem uebernommenen Vertrag: " + (
            BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN[art] + ")")
    else:
        grund = ""
    return (f"{art}-Buchung {was}{grund} (police [{beispiele}]) — die Engine "
            "bucht je Vorfall ein Paar aus Summenzeile und Beitragszeile am "
            "selben Tag. Ausweg: die Zeile streichen bzw. nachtragen, die der "
            "Erzeuger bucht")


#: Der Schluessel einer Buchung: je Schluessel steht GENAU eine Zeile im Ledger.
BUCHUNG_SCHLUESSEL: Tuple[str, ...] = ("police_id", "ereignis", "status_date", "betrag_art")


def doppelte_buchungen(
    ledger: Any, schon_gemeldet: Any = None,
    ohne_arten: Iterable[str] = BEITRAGSEREIGNISSE,
) -> Any:
    """Je Ledgerzeile: ist sie die ueberzaehlige Wiederholung einer Buchung?
    Boolesches Feld — Runde F, Nachbesserung, Klasse "Eindeutigkeit je Buchung".

    Die Engine bucht je (Police, Ereignis, Wirkungstag, Betragsart)
    (:data:`BUCHUNG_SCHLUESSEL`) GENAU eine Zeile. Die Paarregel
    (:func:`beitragspaar_verstoesse`) zaehlte das nur fuer ZUG und ERH; eine
    verdoppelte Zeile jeder anderen Art — ein zweiter Storno, Tod, Ablauf, eine
    zweite Beitragsfreistellung oder Herabsetzungszeile — bemerkten weder P-B1
    noch die Fuehrungsprobe noch der Bericht, und die Probe rechnete die Zeile
    zweimal nach und zaehlte sie zweimal als geprueft. Gemeldet wird die
    ZWEITE und jede weitere Zeile eines Schluessels; die erste bleibt die
    Buchung (die Probe rechnet sie nach, genau einmal).

    ``ohne_arten``: Arten, deren Verdopplung eine andere Regel meldet — im
    Standard :data:`BEITRAGSEREIGNISSE` (die Paarregel meldet deren ``zuviel``
    mit eigenem Text; ein Fehler, ein Befund). Der Ledger der Uebernahme, den
    die Paarregel nicht ansieht, ruft mit ``ohne_arten=()``.
    ``schon_gemeldet``: Zeilen, die eine Regel oben schon beanstandet
    (Buchungsfenster, Ausnahme-Ereignisse) — sie scheiden aus. Die Regel nennt
    keine Ereignisart im Klartext; sie gilt fuer jede.
    """
    n = len(ledger)
    offen = _np.ones(n, dtype=bool) if schon_gemeldet is None \
        else ~_np.asarray(schon_gemeldet, dtype=bool)
    offen &= ~_np.isin(ledger["ereignis"].to_numpy(), list(ohne_arten))
    pos = _np.flatnonzero(offen)
    mehrfach = _np.zeros(n, dtype=bool)
    if len(pos):
        wiederholt = ledger.iloc[pos].duplicated(
            subset=list(BUCHUNG_SCHLUESSEL), keep="first").to_numpy()
        mehrfach[pos[wiederholt]] = True
    return mehrfach


def doppelte_buchung_text(art: str, policen: List[int]) -> str:
    """Die Meldung zur Eindeutigkeitsregel — dieselbe fuer P-B1 (mit dem
    Praefix ``ledger: ``) und die Fuehrungsprobe."""
    beispiele = ", ".join(str(p) for p in policen[:5])
    return (f"{art}-Buchung mehrfach gebucht (police [{beispiele}]) — je Police, "
            "Ereignis, Wirkungstag und Betragsart steht genau eine Zeile; die "
            "Wiederholung ist keine zweite Buchung. Ausweg: die doppelte Zeile "
            "streichen")


def reduktion_jahrestag(beginn: Any, jahr: Any) -> Any:
    """Der Jahrestag des Vertragsjahres ``jahr`` — der EINE Wirkungstag einer
    Herabsetzung und jeder Buchung, die die Engine zum Jahreswechsel zieht.
    Dieselbe Regel in ``validate_reduktionen`` (Fund N16) und in der
    Fuehrungsprobe (Runde F)."""
    import pandas as pd

    return pd.Timestamp(beginn) + pd.DateOffset(years=int(jahr))


def jahrestag_verstoesse(ledger: Any, stamm: Any) -> Any:
    """Je Ledgerzeile: steht sie NICHT am Jahrestag ihres Vertragsjahres
    (``insurance_start`` plus ``vertragsjahr`` Jahre)? Boolesches Feld.

    Runde F: Die Engine bucht jedes GeVo am Jahrestag; ``validate_ledger``
    prueft nur, dass ``vertragsjahr`` die Zahl der vollendeten Jahre ist, und
    der Monatserste genuegt — ein Wirkungstag zwei Monate neben dem Jahrestag
    ging durch. Ausgenommen sind die Zugangsbuchungen am Zugangstag
    (:data:`ZUGANGSTAG_EREIGNISSE`): Ein uebernommener Vertrag kommt am
    Stichtag zu, der kein Jahrestag sein muss. Die Policen der Zeilen muessen
    im Stamm stehen.
    """
    stamm_idx = stamm.set_index("police_id")
    pids = ledger["police_id"].to_numpy()
    beginn = stamm_idx.loc[pids, "insurance_start"].to_numpy()
    zugang = stamm_idx.loc[pids, "bestandszugang"].to_numpy()
    datum = ledger["status_date"].to_numpy()
    jahr = ledger["vertragsjahr"].to_numpy()
    art = ledger["ereignis"].to_numpy()
    soll = _np.array([
        _np.datetime64(reduktion_jahrestag(b, j)) for b, j in zip(beginn, jahr)],
        dtype="datetime64[ns]")
    am_zugang = _np.isin(art, list(ZUGANGSTAG_EREIGNISSE)) & (datum == zugang)
    return (datum != soll) & ~am_zugang


#: Erhoehungsscheiben (dynamische Erhoehung): each row is an own layer of a
#: contract, actuarially an own model point (Schichtungsprinzip). The base
#: layer (Grundscheibe) is the Stamm row itself; Scheiben start at id 1.
#: Column names deliberately mirror the Stamm contract fields so the kernel
#: coupling (:func:`model_point_kwargs`) works on a Scheibe row directly
#: (sex/zahlweise/tarif_generation come from the Stamm, contract level).
SCHEIBEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("scheiben_id", "int64"),          # 1, 2, ... je Police (0 = Grundscheibe im Stamm)
    ("erhoehung_jahr", "int64"),       # Vertragsjahr der Erhoehung (Jahrestag)
    ("erhoehung_datum", "datetime64[ns]"),
    ("entry_age", "int64"),            # Alter bei Erhoehung -> ModelPoint.x
    ("duration", "int64"),             # Restlaufzeit -> ModelPoint.n
    ("premium_duration", "int64"),     # Rest-Beitragsdauer -> ModelPoint.t
    ("sum_insured", "float64"),        # Erhoehungssumme -> ModelPoint.sum_insured
    # Schicht-eigene Rechnungsgrundlage (ADR-011): die Scheibe traegt ihr
    # gamma1 selbst (Tarifwerk-Regel: 0, Bezugsgroesse bleibt die GrundVS).
    # Eine Rekonstruktion aus der Tarifgeneration zur Bewertungszeit hatte
    # die Regel verloren (+2 % Scheibenbeitrag).
    ("gamma1", "float64"),             # -> ModelPoint.gamma1 der Scheibe
)

#: Herabsetzungen je Police — die Spiegeltabelle zu ``scheiben``.
#:
#: Eine dynamische Erhoehung legt eine neue Scheibe an (eigener
#: Modellpunkt, eigene Zeile in ``scheiben.parquet``). Eine Herabsetzung
#: legt keine neue Scheibe an, sie KNICKT den Verlauf des bestehenden
#: Vertrags: Ab dem Reduktionsjahr traegt er den fortgefuehrten
#: Beitragsanteil und daneben die dort fixierte beitragsfreie Summe
#: (``kern.beitragsreduktion.ReduzierterVertrag``, Tarifplan klv.md 7.1).
#:
#: Persistiert werden Jahr, Anteil und Verfahren — je VORGANG eine Zeile:
#: Die Tabelle fuehrt die FOLGE der Beitragsherabsetzungen (``RED``) und
#: Teilkuendigungen (``TKU``) einer Police, beliebig viele, in jeder
#: Reihenfolge (Entscheid des Maintainers 2026-10-01). Rekonstruiert wird
#: der Vertrag daraus zusammen mit den Scheiben, der Beitragsfreistellung
#: der Statushistorie und der Korrekturschicht —
#: ``kern.vorgangsfolge.Vorgangsfolge``, EINE Darstellung fuer alle Leser.
#: Verfahren und Anteil muessen dem Tarifwerk der Generation und den
#: Annahmen entsprechen (P-B1 prueft es): Ohne das Verfahren waere derselbe
#: Anteil je nach Bedingungswerk ein anderer Vertrag.
#:
#: NEBENTABELLE wie ``scheiben``: Keine Datei heisst, der Bestand hat
#: keine Herabsetzungen — nicht, dass niemand nachgesehen hat.
REDUKTIONEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("reduktion_jahr", "int64"),         # Vertragsjahr (nur am Jahrestag)
    ("reduktion_datum", "datetime64[ns]"),
    ("anteil", "float64"),               # fortgefuehrter Beitragsanteil, 0 < f < 1
    ("verfahren", "object"),             # prospektiv | mit_abzug | teilkuendigung
)

#: Verankerungsattribute je uebernommenem Vertrag (Grundsatzdokumentation
#: 9.12, Korrekturschicht-Umsetzung K3): t_a ist der letzte exakte
#: Rechenpunkt des Quellsystems in VERTRAGSMONATEN, ``dk_ta`` der dort
#: gelieferte Wert, ``zustand_ta``/``verweildauer_ta`` der Zustand und
#: seine vollen Jahre am Verankerungszeitpunkt (Selektionsargumente der
#: Schicht).
#:
#: NEBENTABELLE wie ``merkmale``: Nur migrierte Vertraege tragen eine
#: Verankerung — als Stammspalten hiessen leere Felder beim Eigenbestand
#: zweierlei ("trifft nicht zu" und "unbekannt"). Keine Datei heisst:
#: der Bestand hat keine Verankerungen. Bisher lebten die Attribute nur
#: im Pruefauftrag (aus den Erwartungswerten je Lauf rekonstruiert);
#: als Vertragsmerkmale persistiert kann die Korrekturschicht sie lesen,
#: ohne dass jemand die Lieferung erneut auswertet.
VERANKERUNG_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("monate_ta", "int64"),
    ("zustand_ta", "object"),
    ("verweildauer_ta", "int64"),
    ("dk_ta", "float64"),
)

#: Korrekturschicht je uebernommenem Vertrag (Grundsatzdokumentation 9.11,
#: Freischaltung Schritt 5): persistiert werden PARAMETER, keine
#: Zwischenwerte — genau die Felder von
#: ``kern.korrekturschicht.Schichtparameter``; ``formparameter`` und
#: ``vererbend`` als JSON-Text. Der Verankerungszeitpunkt steht in
#: ``verankerung.parquet`` (dieselbe Police, ``monate_ta``); beide Tabellen
#: gehoeren zusammen. NEBENTABELLE wie ``verankerung``: keine Datei heisst,
#: der Bestand traegt keine Schichten. Erzeugt vom Schichtbeleg-Producer
#: (``gates.verankerung_belegen``) in das Uebernahme-Verzeichnis, gelesen
#: von Ereignis-Engine (Storno zahlt Basis plus Schicht), Bewertung
#: (eigene Position im Abschluss) und P-B1 (Ledger-Herleitung).
SCHICHTEN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("schichttyp", "object"),
    ("verankerungszustand", "object"),
    ("verweildauer", "int64"),
    ("rho", "float64"),
    ("formfunktion", "object"),
    ("formparameter", "object"),      # JSON-Text
    ("vererbend", "object"),          # JSON-Text: [[von, nach], ...]
    ("kohorte", "object"),
    ("in_ueberschuss", "bool"),
    ("in_zzr", "bool"),
    ("rumpfmonate", "int64"),
)

#: Merkmalsauspraegungen je Vertrag — die Wahl der Tarifzelle.
#:
#: Eine Nebentabelle wie ``scheiben`` und ``historie``: Sie traegt NUR
#: Vertraege, deren Tarifgeneration Merkmalsdimensionen fuehrt. Fehlt sie,
#: hat der Bestand keine Zellen — nicht: die Information ging verloren.
#: Der Unterschied ist wichtig, weil ``NULL`` in einer Stammspalte beides
#: hiesse, "trifft nicht zu" und "unbekannt".
#:
#: LANGFORMAT und nicht eine Spalte je Dimension: WELCHE Dimensionen es
#: gibt, steht in der Tarifgeneration und ist damit Daten, nicht Schema.
#: Die uebernommene KLV TG2015 fuehrt ``status`` und ``tarifart``, eine
#: andere Generation fuehrt andere. Ein Attribut-Beutel ist das trotzdem
#: nicht: Das Vokabular ist kontrolliert — jede Dimension und jede
#: Auspraegung muss in der Spez der Generation deklariert sein, und genau
#: das prueft :func:`validate_merkmale`.
MERKMALE_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("dimension", "object"),        # z. B. status, tarifart
    ("auspraegung", "object"),      # z. B. nichtraucher, einzel
)

#: Abschluss: festgeschriebene Bewertungsergebnisse eines Stichtags
#: (ADR-011). Einzelvertraglich, nur-anfuegbar, nie ueberschrieben — ein
#: publizierter Stand darf sich nachtraeglich nicht bewegen, auch wenn der
#: Kern sich weiterentwickelt. ``kern_version`` benennt den Stand, unter
#: dem die Werte entstanden; eine spaetere Kontrolle weist Abweichungen
#: der Neuberechnung AUS, statt sie still zu ersetzen.
ABSCHLUSS_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("police_id", "int64"),
    ("stichtag", "datetime64[ns]"),
    ("produkt", "object"),
    ("tarif_generation", "object"),
    ("status_code", "object"),
    ("leistung", "float64"),          # VS (KLV, inkl. Scheiben) bzw. Jahresrente (BU)
    ("deckungskapital", "float64"),
    ("rueckkaufswert", "float64"),
    # Die Korrekturschicht je Vertrag als EIGENE Position (Grundsatz-
    # dokumentation 9.11: nie unsichtbar im Deckungskapital); sie ist in
    # deckungskapital und rueckkaufswert enthalten. 0 ohne Schicht.
    ("korrekturschicht", "float64"),
    ("vs_bfr", "float64"),
    ("jahresbeitrag", "float64"),
    ("kern_version", "object"),
    # Die Bewertungskonvention, in der die Zahlen dieser Datei stehen
    # (BEWERTUNGSKONVENTIONEN; gelesen wird sie nur ueber
    # abschluss_konvention). Seit 2026-10-01 — aeltere Abschluesse tragen
    # die Spalte nicht, und gerade das Fehlen ist ihre Aussage.
    ("bewertungskonvention", "object"),
)

#: Die Bewertungskonventionen eines Abschlusses (Entscheid des Maintainers
#: 2026-10-01, ADR-011 Nachtrag): WIE die Fuehrung das Deckungskapital, den
#: Rueckkaufswert und die Korrekturschicht eines Vertrags am Bewertungs-
#: stichtag aus dem Kern liest.
#:
#: * ``jahreszeile`` — der Wert zum letzten Vertragsjahrestag (die Zeile des
#:   angebrochenen Vertragsjahres). So fuehrte der Abschluss bis 2026-10-01;
#:   unterjaehrig wies er bis zu 11/12 des Jahreszuwachses zu wenig aus. Die
#:   Korrekturschicht einer nicht beitragsfreien Police stand schon damals
#:   monatsgenau darin — die Konvention ist die des damaligen Schreibers,
#:   nicht eine bereinigte.
#: * ``monatsgenau`` — die unterjaehrige Mischung des Kerns: linear zwischen
#:   den beiden Vertragsjahrestagen, die den Bewertungsstichtag einschliessen
#:   (``Rechenkern.monatsreserve`` und Geschwister), ohne Beitragsuebertrag
#:   (zurueckgestellt, dev-docs/offene-punkte.md).
KONVENTION_JAHRESZEILE = "jahreszeile"
KONVENTION_MONATSGENAU = "monatsgenau"
BEWERTUNGSKONVENTIONEN: Tuple[str, ...] = (KONVENTION_JAHRESZEILE, KONVENTION_MONATSGENAU)
#: Die Konvention, in der die Fuehrung heute festschreibt.
FUEHRUNGSKONVENTION = KONVENTION_MONATSGENAU
#: Wie eine Konvention je PRODUKT rechnet. Die BU bleibt auch unter
#: ``monatsgenau`` bei der Jahreszeile: Der Kern fuehrt fuer sie keine
#: unterjaehrige Reserve (``kern.produkte.bu`` kennt nur Vertragsjahre),
#: und eine Mischung in der Bestandsschicht waere eine Formel ausserhalb
#: des Kerns. Benannt statt still gemischt.
KONVENTION_JE_PRODUKT: Dict[str, Dict[str, str]] = {
    KONVENTION_JAHRESZEILE: {"klv": KONVENTION_JAHRESZEILE, "bu": KONVENTION_JAHRESZEILE},
    KONVENTION_MONATSGENAU: {"klv": KONVENTION_MONATSGENAU, "bu": KONVENTION_JAHRESZEILE},
}
#: Die Herkunft der Konvention eines gelesenen Abschlusses.
HERKUNFT_SPALTE = "spalte"
HERKUNFT_VOR_UMSTELLUNG = (
    "Jahreszeile, vor der Umstellung geschrieben (die Datei traegt keine Spalte "
    "bewertungskonvention)")
HERKUNFT_LEER = "leer: ein Abschluss ohne Zeile traegt keine Bewertung"

#: Tagesjournal des Tagesbetriebs (Fachkonzept docs/simulation/tagesbetrieb.md,
#: Abschnitt 3): je Zeile ein Verweis auf genau eine Ledger-Zeile (Police,
#: Ereignis, Wirkungstag ``status_date``) und der Kalendertag, an dem das
#: Unternehmen sie in die Buecher nimmt. Der Ledger bleibt das
#: Wirkungsjournal (Gate P-B1); diese Tabelle ist die Sicht der
#: Buchungstage — nur-anfuegbar, nie ueberschrieben. Ableitungsregeln und
#: Bijektions-Validator: ``rechner_pipeline.betrieb.tagesjournal``.
TAGESJOURNAL_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("buchungsdatum", "datetime64[ns]"),   # Kalendertag der Buchung (Werktag)
    ("police_id", "int64"),
    ("ereignis", "object"),                # GeVo-Code der Ledger-Zeile
    ("status_date", "datetime64[ns]"),     # Wirkungstag = Ledger.status_date
    ("betrag", "float64"),                 # identisch zur Ledger-Zeile
    ("betrag_art", "object"),
    ("herkunft", "object"),                # fortschreibung | neugeschaeft | uebernahme
)

#: Zulaessige Werte von ``tagesjournal.herkunft``: die Buchung stammt aus
#: der Fortschreibung des Bestands, aus dem Tagesneugeschaeft (Buchungstag
#: = Verkaufstag) oder aus einer Uebernahme (gelieferte Buchung).
HERKUNFT_VALUES: Tuple[str, ...] = ("fortschreibung", "neugeschaeft", "uebernahme")

STAMM_NAMES: Tuple[str, ...] = tuple(n for n, _ in STAMM_SPALTEN)
ZEITSCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in ZEITSCHEIBEN_SPALTEN)
STATUS_HISTORIE_NAMES: Tuple[str, ...] = tuple(n for n, _ in STATUS_HISTORIE_SPALTEN)
LEDGER_NAMES: Tuple[str, ...] = tuple(n for n, _ in LEDGER_SPALTEN)
SCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in SCHEIBEN_SPALTEN)
ABSCHLUSS_NAMES: Tuple[str, ...] = tuple(n for n, _ in ABSCHLUSS_SPALTEN)
#: Die Gestalt eines Abschlusses VOR der Umstellung (bis 2026-10-01): dieselben
#: Spalten ohne ``bewertungskonvention``. In der Laufzeit liegen solche Dateien
#: festgeschrieben (ADR-011); sie werden gelesen und nachgerechnet, nie
#: umgeschrieben.
ABSCHLUSS_NAMES_VOR_UMSTELLUNG: Tuple[str, ...] = tuple(
    n for n in ABSCHLUSS_NAMES if n != "bewertungskonvention")

#: Die BEWERTUNGSGROESSEN des Abschlusses — jede Zahl, die ein Bilanzwert
#: ist, abgeleitet statt aufgezaehlt (Review T25-09).
#:
#: Zwei Pruefungen fragen dieselbe Menge ab: die Endlichkeitswache vor dem
#: Festschreiben (:func:`validate_abschluss`) und die Nachrechnung gegen den
#: festgeschriebenen Stand (``bestand.abschluss.pruefe_abschluss``). Beide
#: fuehrten sie als wortgleiches Literal, und beiden fehlte dieselbe Spalte:
#: ``korrekturschicht`` — ausgerechnet die Position, die Grundsatz-
#: dokumentation 9.11 fordert, weil die Schicht nie unsichtbar im
#: Deckungskapital stehen darf. Eine unendliche Schicht durfte damit
#: festgeschrieben werden, und eine wandernde Schicht fiel der Kontrolle
#: nicht auf, solange die Summe stimmte.
#:
#: Die Ableitung ueber den Spaltentyp schliesst die Klasse: Wer dem
#: Abschluss eine neue Bewertungsgroesse gibt, bekommt beide Pruefungen
#: dafuer, ohne sie zu kennen.
ABSCHLUSS_ZAHLEN: Tuple[str, ...] = tuple(
    n for n, dtype in ABSCHLUSS_SPALTEN if dtype == "float64"
)
MERKMALE_NAMES: Tuple[str, ...] = tuple(n for n, _ in MERKMALE_SPALTEN)
VERANKERUNG_NAMES: Tuple[str, ...] = tuple(n for n, _ in VERANKERUNG_SPALTEN)
SCHICHTEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in SCHICHTEN_SPALTEN)
REDUKTIONEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in REDUKTIONEN_SPALTEN)
TAGESJOURNAL_NAMES: Tuple[str, ...] = tuple(n for n, _ in TAGESJOURNAL_SPALTEN)


#: Die Uebersetzungstabelle eines Uebernahme-Eingangs (Review T24-08): In
#: welche Zielnummer das Zielsystem eine gelieferte Policennummer gehoben
#: hat. Sie ist der Traeger der Nachvollziehbarkeit zur Quelle — die
#: Belege des Falls (uebernahme.json, A-M4-Snapshot) sprechen weiter in
#: QUELLnummern, die Tabellen des Betriebs in ZIELnummern.
POLICENNUMMERN_SPALTEN: Tuple[Tuple[str, str], ...] = (
    ("quelle_police_id", "int64"),   # wie geliefert
    ("ziel_police_id", "int64"),     # wie das Zielsystem sie fuehrt
)
POLICENNUMMERN_NAMES: Tuple[str, ...] = tuple(n for n, _ in POLICENNUMMERN_SPALTEN)

#: Die Vokabel der Nebentabellen uebernommener Vertraege — an EINER Stelle,
#: damit Gate, Pruefengine und Betriebseingang dieselbe Sprache pruefen
#: (Betriebsbefund N-01, 2026-09-08: der Betrieb las ``zustand_ta = "POL"``
#: anstandslos, das Gate haette es abgewiesen, der Kern brach vier
#: Schichten tiefer mit "Unbekannter Startzustand" ab).
#:
#: ``zustand_ta`` (verankerung.parquet): der Vertragszustand am
#: Verankerungszeitpunkt in der Sprache der Uebernahme.
ZUSTAENDE_TA: Tuple[str, ...] = ("beitragspflichtig", "beitragsfrei")

#: Die Verfahren der Herabsetzung — Vokabel der Nebentabelle
#: ``reduktionen``. Literal aus demselben Grund wie :data:`ZUSTAENDE_TA`:
#: Gate, P-B1-Engine und Betriebseingang pruefen die Tabelle, ohne den
#: Kern zu laden, und ``models`` darf die Vorzeige nicht importieren
#: (ADR-017). Die QUELLE bleibt ``kern.beitragsreduktion.VERFAHREN`` —
#: laeuft die Liste ihm davon, faellt das in
#: ``tests/test_models_vokabel_kern.py``, nicht erst vier Schichten
#: tiefer mit "unbekanntes Verfahren".
RED_VERFAHREN: Tuple[str, ...] = ("prospektiv", "mit_abzug", "teilkuendigung")
#: Das Verfahren der Nebentabelle ``reduktionen``, das eine TEILKUENDIGUNG
#: registriert (Ledger-Code ``TKU``); jedes andere registriert eine
#: Beitragsherabsetzung (``RED``). Literal aus demselben Grund wie
#: :data:`RED_VERFAHREN`.
TEILKUENDIGUNG_VERFAHREN = "teilkuendigung"


def reduktion_ereignis(verfahren: str) -> str:
    """Der Ledger-Code des Vorgangs, den eine Zeile der Nebentabelle
    ``reduktionen`` registriert: ``TKU`` fuer die Teilkuendigung, ``RED`` fuer
    die Beitragsherabsetzung (Entscheid des Maintainers 2026-10-01, ADR-023:
    zwei Geschaeftsvorfaelle). Die EINE Zuordnung fuer P-B1, die
    Fuehrungsprobe, die Auswertung und den Tagesbetrieb."""
    return "TKU" if str(verfahren) == TEILKUENDIGUNG_VERFAHREN else "RED"


def alt_absetzung_ist_teilkuendigung(
    quell_verfahren: str, jahr: int, beitragsdauer: int, *,
    beitragsfrei_ab: Optional[int],
) -> bool:
    """Welcher Vorgang des Zielsystems eine GELIEFERTE Absetzung der Quelle
    war — die EINE Uebersetzungsregel vom Vokabular der Quelle in das des
    Zielsystems (Grundsatzdokumentation 7.1; Tarifplan KLV 7.2, Annahmen A2
    und B5; ADR-023, Nachtrag 2026-10-01).

    Die Quelle bucht ihre Absetzungen mit EINEM Code (``RED``, so bleibt er
    als Provenienzname stehen). Das Zielsystem kennt zwei Vorgaenge mit
    eigenem Code; welcher es war, sagt diese Regel, und zwar in dieser
    Reihenfolge:

    * Rechnet die Quelle eine Absetzung als Teilkuendigung (Verfahren der
      Quelle ``teilkuendigung``, Beleg der Migration ``--red-verfahren``),
      war JEDE ihrer Absetzungen eine Teilkuendigung — vor und nach dem
      Beitragsende, vor und nach einer Beitragsfreistellung. So der
      uebernommene Tarif der zweiten Lieferung (Bedingungswerk Ziffer 6).
    * Kennt die Quelle eine echte Beitragsherabsetzung (Annahme B5), war eine
      Absetzung VOR dem Beitragsende und vor einer Beitragsfreistellung eine
      Herabsetzung; ab dem Beitragsende (``jahr >= beitragsdauer``) oder ab
      der Beitragsfreistellung (``jahr >= beitragsfrei_ab``) eine
      Teilkuendigung — es gab keinen Beitrag mehr, den eine Herabsetzung
      haette senken koennen.

    ``beitragsfrei_ab`` hat keinen Default: Wer die Regel fragt, sagt, ob
    der Vertrag beitragsfrei gestellt war (``None``: nicht).

    Das ist KEINE Umdeutung eines Vorgangs des Zielsystems; die Regel liest
    nur, was eine Lieferung mit dem einen Code meint."""
    if str(quell_verfahren) == TEILKUENDIGUNG_VERFAHREN:
        return True
    if int(jahr) >= int(beitragsdauer):
        return True
    return beitragsfrei_ab is not None and int(jahr) >= int(beitragsfrei_ab)


def zielverfahren(
    quell_verfahren: str, jahr: int, beitragsdauer: int, *,
    beitragsfrei_ab: Optional[int],
) -> str:
    """Das Verfahren des Zielvorgangs einer gelieferten Absetzung —
    ``teilkuendigung`` oder das Herabsetzungsverfahren der Quelle; dieselbe
    Regel wie :func:`alt_absetzung_ist_teilkuendigung`, in der Form, in der
    eine Zeile der Nebentabelle ``reduktionen`` sie traegt (der Code folgt
    daraus, :func:`reduktion_ereignis`)."""
    if alt_absetzung_ist_teilkuendigung(
            quell_verfahren, jahr, beitragsdauer, beitragsfrei_ab=beitragsfrei_ab):
        return TEILKUENDIGUNG_VERFAHREN
    return str(quell_verfahren)


#: ``verankerungszustand`` (schichten.parquet): der Startzustand der
#: Korrekturschicht — ein ERLEBENSzustand des Zustandsmodells, mit dem sie
#: bewertet wird ("aktiv" fuer Kapitalversicherungen, "aktiv"/"bu" fuer die
#: Berufsunfaehigkeit). Beitragsfreiheit ist kein Zustand des Modells,
#: sondern eine Eigenschaft des Modellpunkts; ein beitragsfrei verankerter
#: Vertrag traegt deshalb ``zustand_ta = "beitragsfrei"`` und
#: ``verankerungszustand = "aktiv"``. Der Test ``test_kern_algebraisch``
#: haelt die Liste gegen die Zustaende der Kern-Modelle.
VERANKERUNGSZUSTAENDE: Tuple[str, ...] = ("aktiv", "bu")


def stamm_dtypes() -> Dict[str, str]:
    return dict(STAMM_SPALTEN)


def leerer_stamm() -> Any:
    """Ein Stamm ohne Zeilen, mit den Spalten und Typen des Vertrags.

    Der Ausgangspunkt jedes Laufs, der seinen Bestand aus dem Zugangsstrom
    aufbaut (ADR-020): Es gibt keinen gezogenen Anfangsbestand mehr, also
    beginnt die Fuehrung leer und bucht jeden Vertrag als Zugang.
    """
    import pandas as pd

    return pd.DataFrame({name: pd.Series(dtype=dtype) for name, dtype in STAMM_SPALTEN})


# --------------------------------------------------------------------------- #
# Validation (error-list idiom)
# --------------------------------------------------------------------------- #


def validate_portfolio(df: Any) -> List[str]:
    """Validate a base portfolio DataFrame against the Stamm schema.

    Returns a list of error strings; empty list means valid. Checks column
    set/order, dtypes, enum values, and hard row-level invariants.
    """
    errors: List[str] = []
    cols = list(df.columns)
    if cols != list(STAMM_NAMES):
        errors.append(
            f"Spalten weichen ab: erwartet {list(STAMM_NAMES)}, vorhanden {cols}"
        )
        return errors  # ohne korrekte Spalten sind Detailchecks sinnlos

    for name, dtype in STAMM_SPALTEN:
        actual = str(df[name].dtype)
        if actual != dtype:
            errors.append(f"Spalte {name}: dtype {actual}, erwartet {dtype}")

    if df["police_id"].duplicated().any():
        errors.append("police_id nicht eindeutig")
    generation = df["tarif_generation"]
    if generation.isna().any() or generation.map(
        lambda wert: not isinstance(wert, str) or not wert.strip()
    ).any():
        errors.append("tarif_generation leer")
    if not df["sex"].isin(SEX_VALUES).all():
        errors.append(f"sex ausserhalb {SEX_VALUES}")
    if not df["produkt"].isin(PRODUKT_VALUES).all():
        errors.append(f"produkt ausserhalb {PRODUKT_VALUES}")
    # Zustandsregeln des gefuehrten Bestands (ADR-011): Der Stammsatz
    # traegt den AKTUELLEN Zustand. status_id 1 ist der Ursprungssatz und
    # unterliegt der strengen Ursprungsregel (POL am Versicherungsbeginn);
    # hoehere status_id sind gebuchte Folgezustaende — ihre Deckung mit dem
    # Journal prueft validate_stamm_journal (Gate P-B1 erzwingt sie).
    if (df["status_id"] < 1).any():
        errors.append("status_id < 1")
    if not df["status_code"].isin(STATUS_CODE_VALUES).all():
        errors.append(f"status_code ausserhalb {STATUS_CODE_VALUES}")
    ursprung = df["status_id"] == 1
    if not df.loc[ursprung, "status_code"].isin(BASIS_STATUS).all():
        errors.append("status_id 1 mit status_code != POL (Ursprungssatz)")
    folge = df[~ursprung]
    for produkt, erlaubt in PRODUKT_STATUS.items():
        zeilen = folge[folge["produkt"] == produkt]
        if len(zeilen) and not zeilen["status_code"].isin(erlaubt).all():
            errors.append(
                f"{produkt}: Folgestatus ausserhalb {sorted(erlaubt)}"
            )
    if not df["zahlweise"].isin(ZAHLWEISE_VALUES).all():
        errors.append(f"zahlweise ausserhalb {ZAHLWEISE_VALUES}")

    num = df[["entry_age", "duration", "premium_duration", "sum_insured", "bu_rente"]]
    # NaN-Vergleiche sind immer False — fehlende Werte muessen explizit
    # geprueft werden, sonst passieren sie jede Bandpruefung.
    nan_spalten = [c for c in num.columns if num[c].isna().any()]
    if nan_spalten:
        errors.append(f"fehlende Werte (NaN) in {nan_spalten}")
    # Unendlich ist kein fehlender Wert und faellt durch jede Bandpruefung:
    # inf > 0 ist wahr, inf <= 0 ist falsch. Ein Stammsatz mit
    # sum_insured = +inf passierte Gate P-B1, den Abschluss UND dessen
    # Kontrolle, weil math.isclose(inf, inf) wahr ist. Bilanzwerte sind
    # endlich; alles andere ist ein Datenfehler der Quelle.
    inf_spalten = [
        c for c in num.columns
        if bool(_np.isinf(num[c].to_numpy(dtype="float64", na_value=0.0)).any())
    ]
    if inf_spalten:
        errors.append(f"nichtendliche Werte (inf) in {inf_spalten}")
    if (num["entry_age"] < 0).any():
        errors.append("entry_age negativ")
    if (num["duration"] <= 0).any():
        errors.append("duration <= 0")
    if (num["premium_duration"] <= 0).any():
        errors.append("premium_duration <= 0")
    if (df["premium_duration"] > df["duration"]).any():
        errors.append("premium_duration > duration")

    # Produktabhaengige Leistungs-Invarianten: genau die Spalte des Produkts
    # traegt die versicherte Leistung, die andere ist strikt 0 — eine
    # vertauschte Spalte waere sonst eine stille Falschbewertung.
    klv = df[df["produkt"] == "klv"]
    bu = df[df["produkt"] == "bu"]
    if len(klv):
        if (klv["sum_insured"] <= 0).any():
            errors.append("klv: sum_insured <= 0")
        if (klv["bu_rente"] != 0.0).any():
            errors.append("klv: bu_rente != 0 (KLV fuehrt die Versicherungssumme)")
    if len(bu):
        if (bu["bu_rente"] <= 0).any():
            errors.append("bu: bu_rente <= 0")
        if (bu["sum_insured"] != 0.0).any():
            errors.append("bu: sum_insured != 0 (BU fuehrt die Jahresrente)")
        if (bu["premium_duration"] != bu["duration"]).any():
            errors.append(
                "bu: premium_duration != duration (das BU-Beispielprodukt "
                "zahlt Beitraege ueber die volle Versicherungsdauer)"
            )
        if (bu["zahlweise"] != 1).any():
            errors.append(
                "bu: zahlweise != 1 (das BU-Beispielprodukt kennt nur "
                "Jahreszahlung)"
            )

    start = df["insurance_start"]
    if (df["insurance_end"] <= start).any():
        errors.append("insurance_end <= insurance_start")
    if (df["payment_end"] <= start).any():
        errors.append("payment_end <= insurance_start")
    ursprung = df["status_id"] == 1
    if not (df.loc[ursprung, "status_date"] == start[ursprung]).all():
        errors.append("status_id 1 mit status_date != insurance_start (Ursprungssatz)")
    folge = ~ursprung
    if (df.loc[folge, "status_date"] <= start[folge]).any():
        errors.append("Folgestatus mit status_date <= insurance_start")
    if (df.loc[folge, "status_date"] > df.loc[folge, "insurance_end"]).any():
        errors.append("Folgestatus mit status_date > insurance_end")
    # Der Bestandszugang liegt zwischen Vertragsbeginn und Ablauf: Vor dem
    # Beginn gibt es den Vertrag nicht, nach dem Ablauf gibt es nichts mehr
    # zu uebernehmen. Beim eigenen Geschaeft faellt er auf den Beginn.
    zugang = df["bestandszugang"]
    if zugang.isna().any():
        errors.append("bestandszugang fehlt (NaT)")
    else:
        if (zugang < start).any():
            errors.append(
                "bestandszugang < insurance_start (ein Vertrag kann nicht in "
                "die Buecher kommen, bevor er geschlossen wurde)"
            )
        if (zugang >= df["insurance_end"]).any():
            errors.append("bestandszugang >= insurance_end")
    # Monatserster-Konvention (deterministische Jahres-/Monatsarithmetik).
    for col in (
        "status_date",
        "date_of_birth",
        "insurance_start",
        "insurance_end",
        "payment_end",
        "bestandszugang",
    ):
        if not (df[col].dt.day == 1).all():
            errors.append(f"{col}: nicht auf Monatsersten normalisiert")

    # Datumsfelder muessen zu den Jahresfeldern konsistent sein (Monatszaehlung,
    # da alle Daten auf dem Monatsersten liegen).
    def _monat(col: str):
        return df[col].dt.year * 12 + df[col].dt.month

    if not (_monat("insurance_end") - _monat("insurance_start") == 12 * df["duration"]).all():
        errors.append("insurance_end != insurance_start + duration Jahre")
    if not (_monat("payment_end") - _monat("insurance_start") == 12 * df["premium_duration"]).all():
        errors.append("payment_end != insurance_start + premium_duration Jahre")
    if not (_monat("insurance_start") - _monat("date_of_birth") == 12 * df["entry_age"]).all():
        errors.append("date_of_birth passt nicht zu entry_age (Monatszaehlung)")

    return errors


def validate_statushistorie(stamm: Any, historie: Any) -> List[str]:
    """Validate a Statushistorie against its base portfolio (error-list idiom).

    A history holds only follow-up statuses (the origin row — POL at the
    insurance start — is convention, not a record): per police consecutive
    ``status_id`` starting at 2 in ``status_date``
    order, at most one PEX, at most one terminal status — and the terminal
    one is last. An empty history is valid.
    """
    errors: List[str] = []
    cols = list(historie.columns)
    if cols != list(STATUS_HISTORIE_NAMES):
        errors.append(
            f"historie: Spalten {cols} != erwartet {list(STATUS_HISTORIE_NAMES)}"
        )
        return errors
    for name, dtype in STATUS_HISTORIE_SPALTEN:
        actual = str(historie[name].dtype)
        if actual != dtype:
            errors.append(f"historie {name}: dtype {actual}, erwartet {dtype}")
    if len(historie) == 0:
        return errors

    if not historie["status_code"].isin(STATUS_CODE_VALUES).all():
        errors.append(f"historie: status_code ausserhalb {STATUS_CODE_VALUES}")
    unbekannt = set(historie["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(f"historie: police_id unbekannt: {sorted(unbekannt)[:5]}")
    if not (historie["status_date"].dt.day == 1).all():
        errors.append("historie: status_date nicht auf Monatsersten normalisiert")

    grenzen = stamm.set_index("police_id")[["insurance_start", "insurance_end"]]
    # Altbestaende (Parquet vor der Produkt-Einfuehrung) haben die Spalte
    # nicht; validate_portfolio meldet das praezise, hier darf es keinen
    # KeyError geben — sonst endet Gate P-B1 als internal_error statt als
    # Contract-Fehler.
    produkt_je_police = (
        stamm.set_index("police_id")["produkt"]
        if "produkt" in stamm.columns
        else None
    )
    for police_id, gruppe in historie.groupby("police_id", sort=False):
        g = gruppe.sort_values("status_date", kind="stable")
        prefix = f"historie police {police_id}"
        if list(g["status_id"]) != list(range(2, 2 + len(g))):
            errors.append(f"{prefix}: status_id nicht fortlaufend ab 2")
        codes = list(g["status_code"])
        terminal = [c for c in codes if c in TERMINALE_STATUS]
        if len(terminal) > 1:
            errors.append(f"{prefix}: mehr als ein terminaler Status")
        elif terminal and codes[-1] not in TERMINALE_STATUS:
            errors.append(f"{prefix}: Status nach terminalem Status")
        if codes.count("PEX") > 1:
            errors.append(f"{prefix}: PEX mehrfach")
        # Produktfremde Status sind ein harter Fehler (PEX gehoert zu KLV,
        # der Leistungsbezug BU zu BU) — sonst liefe eine vertauschte
        # Tabelle still durch die Auswertung.
        produkt = (
            str(produkt_je_police.get(police_id, "klv"))
            if produkt_je_police is not None
            else "klv"
        )
        erlaubt = PRODUKT_STATUS.get(produkt, ())
        fremd = sorted({c for c in codes if c not in erlaubt})
        if fremd:
            errors.append(f"{prefix}: Status {fremd} nicht zulaessig fuer Produkt {produkt}")
        elif produkt == "bu":
            # BU wechselt zwischen Anwaerter (POL) und Leistungsbezug (BU)
            # beliebig oft, aber strikt alternierend — zwei gleiche
            # Zustaende hintereinander waeren ein Engine-Fehler.
            zustand = "POL"
            for code in codes:
                if code in TERMINALE_STATUS:
                    break
                if code == zustand:
                    errors.append(f"{prefix}: Statuswechsel {code} -> {code} (nicht alternierend)")
                    break
                zustand = code
        if police_id in grenzen.index:
            start = grenzen.loc[police_id, "insurance_start"]
            ende = grenzen.loc[police_id, "insurance_end"]
            if (g["status_date"] <= start).any():
                errors.append(f"{prefix}: status_date vor/auf insurance_start")
            if (g["status_date"] > ende).any():
                errors.append(f"{prefix}: status_date nach insurance_end")
    return errors


def validate_stamm_journal(stamm: Any, historie: Any) -> List[str]:
    """Deckungsgleichheit von gefuehrtem Stamm und Journal (ADR-011).

    Der Stammzustand IST der juengste Journalstand: Je Police mit
    Journalzeilen muss der Stammsatz exakt die juengste Zeile tragen
    (status_id, status_code, status_date); eine Police ohne Journalzeilen
    steht im Ursprungszustand (status_id 1). Ein Stamm, der etwas anderes
    behauptet als sein Journal, ist keine Bestandsfuehrung, sondern eine
    Behauptung.
    """
    errors: List[str] = []
    if len(historie) == 0:
        juengste = None
    else:
        juengste = (
            historie.sort_values(["police_id", "status_id"], kind="stable")
            .groupby("police_id", sort=False)
            .tail(1)
            .set_index("police_id")
        )
    for zeile in stamm.itertuples(index=False):
        pid = int(zeile.police_id)
        if juengste is not None and pid in juengste.index:
            soll = juengste.loc[pid]
            ist = (int(zeile.status_id), str(zeile.status_code), zeile.status_date)
            erwartet = (
                int(soll["status_id"]),
                str(soll["status_code"]),
                soll["status_date"],
            )
            if ist != erwartet:
                errors.append(
                    f"stamm police {pid}: Zustand {ist[1]} (id {ist[0]}, "
                    f"{ist[2].date()}) weicht vom juengsten Journalstand "
                    f"{erwartet[1]} (id {erwartet[0]}, {erwartet[2].date()}) ab"
                )
        elif int(zeile.status_id) != 1:
            errors.append(
                f"stamm police {pid}: status_id {int(zeile.status_id)} ohne "
                "Journalzeilen — ein Folgezustand braucht seine Buchung"
            )
    return errors


def _nichtendlich(reihe: Any) -> bool:
    """NaN oder +/-inf in einer Zahlenreihe — beides faellt durch jede
    Bandpruefung (NaN vergleicht immer falsch, inf > 0 ist wahr)."""
    werte = reihe.to_numpy(dtype="float64")
    return bool((~_np.isfinite(werte)).any())


def weicht_ab(ist: Any, soll: Any, toleranz: float) -> bool:
    """Weichen Ist- und Soll-Wert um mehr als ``toleranz`` voneinander ab?

    Runde F, Nachbesserung (Befund F5 als Klasse): ``abs(ist - soll) > toleranz``
    ist bei NaN auf EINER der beiden Seiten immer falsch — der Wert galt als
    uebereinstimmend, und ``abs(inf - inf)`` ist NaN statt null. Die Regel:
    Ein nicht endlicher Wert (NaN, +/-inf, ein fehlender oder nicht
    umwandelbarer Wert) auf der Ist- ODER der Soll-Seite ist eine Abweichung,
    nie eine Uebereinstimmung. Die Fuehrungsprobe vergleicht Betraege NUR
    durch diese Funktion (statische Ratsche in
    ``tests/test_klasse_probe_abweichung_f.py``); wer eine weitere
    Vergleichsstelle baut, ruft sie, statt ``abs(...) > TOLERANZ`` zu schreiben.
    Ausweg fuer einen Wert, der legitim fehlen darf: vor dem Vergleich
    entscheiden und nicht vergleichen — nie ein NaN mit Absicht durchreichen.
    """
    try:
        ist, soll = float(ist), float(soll)
    except (TypeError, ValueError):
        return True
    if not (_np.isfinite(ist) and _np.isfinite(soll)):
        return True
    return bool(abs(ist - soll) > toleranz)


def validate_ledger(
    stamm: Any, ledger: Any, historie: Any = None, scheiben: Any = None,
    horizont: Any = None,
) -> List[str]:
    """Semantik des Ereignis-Ledgers gegen Stamm, Journal und Scheiben.

    Externes Review T18-06: Es gab keinen semantischen Ledger-Validator —
    ``betrag = inf``, ``betrag_art = MANIPULIERT``, eine fremde
    ``tarif_generation`` und ``vertragsjahr = 999`` passierten Gate P-B1
    mit null Befunden. Geprueft wird jetzt, was eine Buchung IST:

    * Spalten/dtypes, bekannte Police, ``ereignis`` und ``betrag_art``
      aus dem Vokabular (die Bezugsgroesse gehoert zum GeVo),
      ``betrag_herkunft`` aus ``BETRAG_HERKUNFT``;
    * ``betrag`` endlich und, ausser beim Migrations-Residuum ``MIG``,
      nicht negativ;
    * ``tarif_generation`` die des Stammsatzes;
    * ``status_date`` auf dem Monatsersten, innerhalb der Vertragslaufzeit,
      und ``vertragsjahr`` die Zahl der VOLLENDETEN Vertragsjahre an
      diesem Datum (``MIG`` ausgenommen: dort ist es das Jahr des letzten
      exakten Rechenpunkts der Quelle, nicht des Stichtags);
    * mit ``historie``: Jeder GeVo, der einen Zustand herstellt, hat
      seine Journalzeile — gleiches Datum, hergestellter Zustand. Beim
      ``PEX`` genuegt eine Beitragsfreistellung AM ODER VOR dem
      Buchungsdatum: Ein beitragsfrei uebernommener Vertrag traegt die
      Beitragsfreistellung der Quelle in der Historie und die Umbuchung
      zum Zugangsstichtag im Ledger (gates.bestand_uebernehmen). Die
      Gegenrichtung wird bewusst NICHT verlangt: Die Vorgeschichte eines
      uebernommenen Vertrags steht in der Historie, ohne Bewegung des
      aufnehmenden Unternehmens zu sein;
    * mit ``scheiben`` (externes Review T18-01): ZEILENWEISE Bindung
      statt Jahressummen — jede ``ERH``-Buchung hat genau eine Scheibe
      derselben Police am selben Datum mit demselben Betrag und
      Erhoehungsjahr, und jede Scheibe ihre Buchung. Vorher passierten
      zwei zwischen Policen vertauschte Scheibenbetraege (3.850 gegen
      2.350) mit null Befunden; der Abschluss verschob sich um 63,70 EUR,
      weil die Summen danach auf anderen Vertragsaltern lagen;
    * JEDE Buchung liegt NACH dem Bestandszugang des Vertrags und, mit
      ``horizont`` (dem im Laufmanifest BELEGTEN Horizont, nicht einem
      Aufrufwert), nicht dahinter (Pruefrunde T27, Runde C, Befund RC02,
      Runde E, Klasse geschlossen): Die Engine simuliert einen
      uebernommenen Vertrag erst ab seinem Zugangsjahr und nie ueber den
      Horizont. Eine Buchung davor ist Vorgeschichte der abgebenden
      Gesellschaft, eine dahinter ist nicht gefahren — beide sind keine
      Buchung dieses Laufs und damit unbelegt. Vorher galt die Wache nur
      fuer ``RED``: Eine Teilkuendigung vom 2025-01-01 vor dem Zugang vom
      2026-01-01 ging mit null Befunden durch und kuerzte die Summe eines
      Vertrags am Stichtag von 43.000 auf 25.800 EUR; ein Storno, Tod, Ablauf,
      eine Erhoehung oder Beitragsfreistellung am selben Ort ebenso.
      Die Menge der Ereignisarten ist ``EREIGNIS_VALUES``; ausgenommen sind
      nur die benannten Zugangsbuchungen am Zugangstag
      (:data:`ZUGANGSTAG_EREIGNISSE`) und der Zugang eines Neugeschaefts
      mit Beginn nach dem Laufdatum (:data:`ZUGANG_HINTER_HORIZONT`, hoechstens
      am Monatsersten nach dem Horizont); die gelieferte Vorgeschichte steht
      in der Historie, nicht im Ledger. Die Ausnahme-Ereignisse stehen an
      ihrem Zeitpunkt (:func:`ausnahme_ereignis_verstoesse`: ZUG einmal und am
      Zugangstag, MIG am Zugangstag eines uebernommenen Vertrags, ABL am
      Vertragsende).
      Dieselbe Regel, als :func:`buchungsfenster_verstoesse`, prueft die
      Fuehrungsprobe;
    * Paarbuchung (Runde F, Klasse): je Vorfall einer Ereignisart mit
      Beitragswirkung (:data:`BEITRAGSEREIGNISSE`, aus dem Vokabular
      hergeleitet) genau eine Summenzeile und genau eine Beitragszeile
      ``BJB`` — der Zugang eines uebernommenen Vertrags bucht nur die Summe
      (:data:`BEITRAGSEREIGNIS_OHNE_BJB_UEBERNOMMEN`). Vorher bemerkte keine
      Wache eine verdoppelte oder gestrichene Beitragszeile einer Erhoehung
      (:func:`beitragspaar_verstoesse`, ebenfalls in der Fuehrungsprobe);
    * Eindeutigkeit (Runde F, Nachbesserung): je (Police, Ereignis,
      Wirkungstag, Betragsart) genau eine Zeile, fuer jede Ereignisart
      (:func:`doppelte_buchungen`; die Beitragsereignisse zaehlt die
      Paarregel). Vorher bemerkte keine Wache eine verdoppelte Storno-, Tod-,
      Ablauf- oder Freistellungszeile.
    """
    errors: List[str] = []
    cols = list(ledger.columns)
    if cols != list(LEDGER_NAMES):
        errors.append(f"ledger: Spalten {cols} != erwartet {list(LEDGER_NAMES)}")
        return errors
    for name, dtype in LEDGER_SPALTEN:
        actual = str(ledger[name].dtype)
        if actual != dtype:
            errors.append(f"ledger {name}: dtype {actual}, erwartet {dtype}")
    if errors or len(ledger) == 0:
        return errors

    unbekannt = set(ledger["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(f"ledger: police_id unbekannt: {sorted(unbekannt)[:5]}")
        return errors

    def _policen(maske: Any) -> List[int]:
        return sorted(set(int(p) for p in ledger.loc[maske, "police_id"]))[:5]

    fremd = ~ledger["ereignis"].isin(EREIGNIS_VALUES)
    if fremd.any():
        errors.append(
            f"ledger: ereignis ausserhalb {list(EREIGNIS_VALUES)}: "
            f"{sorted(set(ledger.loc[fremd, 'ereignis']))[:5]} "
            f"(police {_policen(fremd)})"
        )
    art_falsch = ~fremd & ~ledger.apply(
        lambda z: z["betrag_art"] in BETRAG_ART_JE_EREIGNIS.get(z["ereignis"], ()),
        axis=1,
    )
    if art_falsch.any():
        beispiele = sorted(set(
            f"{e}/{a}" for e, a in zip(ledger.loc[art_falsch, "ereignis"],
                                       ledger.loc[art_falsch, "betrag_art"])
        ))[:5]
        errors.append(
            f"ledger: betrag_art passt nicht zum GeVo: {beispiele} "
            f"(police {_policen(art_falsch)})"
        )
    herkunft_falsch = ~ledger["betrag_herkunft"].isin(BETRAG_HERKUNFT)
    if herkunft_falsch.any():
        errors.append(
            f"ledger: betrag_herkunft ausserhalb {BETRAG_HERKUNFT} "
            f"(police {_policen(herkunft_falsch)})"
        )
    # Die Herkunft folgt aus dem Erzeugungspfad, sie ist kein freies
    # Etikett (Review T21-07): "geliefert" traegt genau der Zugang eines
    # UEBERNOMMENEN Vertrags (die Zugangssumme steht im Abzug der
    # abgebenden Gesellschaft); alles andere rechnet der Kern.
    stamm_idx = stamm.set_index("police_id")
    uebernommen = (
        stamm_idx.loc[ledger["police_id"].to_numpy(), "bestandszugang"].to_numpy()
        > stamm_idx.loc[ledger["police_id"].to_numpy(), "insurance_start"].to_numpy()
    )
    darf_geliefert = (ledger["ereignis"].to_numpy() == "ZUG") & uebernommen
    ist_geliefert = (ledger["betrag_herkunft"] == "geliefert").to_numpy()
    falsch_geliefert = ist_geliefert & ~darf_geliefert
    if falsch_geliefert.any():
        errors.append(
            "ledger: betrag_herkunft 'geliefert' nur fuer den Zugang eines "
            "uebernommenen Vertrags — alles andere ist 'gerechnet' (police "
            f"{_policen(falsch_geliefert)})"
        )
    fehlt_geliefert = darf_geliefert & ~ist_geliefert
    if fehlt_geliefert.any():
        errors.append(
            "ledger: Zugang eines uebernommenen Vertrags muss betrag_herkunft "
            f"'geliefert' tragen (police {_policen(fehlt_geliefert)})"
        )
    if ledger["betrag"].isna().any():
        errors.append(
            f"ledger: fehlende Werte (NaN) in betrag (police "
            f"{_policen(ledger['betrag'].isna())})"
        )
    elif _nichtendlich(ledger["betrag"]):
        unendlich = _np.isinf(ledger["betrag"].to_numpy(dtype="float64"))
        errors.append(
            f"ledger: nichtendliche Werte (inf) in betrag (police "
            f"{_policen(unendlich)}) — ein Buchungsbetrag ist endlich"
        )
    else:
        # Umbuchungen tragen ein Vorzeichen: das Migrations-Residuum (MIG)
        # und die absorbierte Korrekturschicht (dDK_absorption) — eine
        # negative Schicht ist ein negatives Residuum, kein Fehler. Der
        # Erzeuger buchte sie so, sein eigenes Gate wies den korrekten Lauf
        # ab (Angriffsrunde 2, Fund N15).
        negativ = ((ledger["betrag"] < 0.0) & (ledger["ereignis"] != "MIG")
                   & (ledger["betrag_art"] != "dDK_absorption"))
        if negativ.any():
            errors.append(
                f"ledger: betrag < 0 (police {_policen(negativ)}) — nur die "
                "Umbuchungen MIG und dDK_absorption tragen ein Vorzeichen"
            )
    if not (ledger["status_date"].dt.day == 1).all():
        errors.append("ledger: status_date nicht auf Monatsersten normalisiert")

    # Jede Buchung liegt im Lauf: echt nach dem Zugang (ausser den benannten
    # Zugangsbuchungen), nicht hinter dem belegten Horizont — fuer JEDE
    # Ereignisart (Runde E, Klasse geschlossen), nicht nur fuer RED.
    vor_zugang, hinter = buchungsfenster_verstoesse(ledger, stamm, horizont)
    arten = ledger["ereignis"].to_numpy()
    for art in sorted(set(arten[vor_zugang])):
        maske = vor_zugang & (arten == art)
        errors.append(
            f"ledger: {art}-Buchung nicht nach dem Bestandszugang des Vertrags "
            f"(police {_policen(maske)}) — Vorgeschichte der abgebenden "
            "Gesellschaft, keine Buchung dieses Laufs; die Engine simuliert "
            "einen uebernommenen Vertrag erst ab seinem Zugangsjahr. Am "
            f"Zugangstag stehen nur {sorted(ZUGANGSTAG_EREIGNISSE)}")
    if horizont is not None:
        import pandas as pd

        for art in sorted(set(arten[hinter])):
            maske = hinter & (arten == art)
            errors.append(
                f"ledger: {art}-Buchung nach dem belegten Horizont "
                f"{pd.Timestamp(horizont).date()} (police {_policen(maske)}) — "
                "der Lauf hat sie nicht gefahren, sie ist unbelegt")

    # Die Ausnahme-Ereignisse (ZUG, MIG, ABL) stehen an ihrem Zeitpunkt (Runde E,
    # Nachbesserung): eine Ausnahmemenge ohne Wache fuer ihren Grund ist keine
    # geschlossene Klasse. Zeilen, die das Fenster schon beanstandet, scheiden
    # aus — ein Fehler, ein Befund.
    ausnahmen = ausnahme_ereignis_verstoesse(ledger, stamm, vor_zugang | hinter)
    gemeldet = vor_zugang | hinter
    for regel, maske in ausnahmen.items():
        gemeldet = gemeldet | maske
        for art in sorted(set(arten[maske])):
            errors.append("ledger: " + ausnahme_ereignis_text(
                regel, str(art), _policen(maske & (arten == art))))

    # Die Paarbuchung (Runde F, Klasse): je Vorfall mit Beitragswirkung genau
    # eine Summenzeile und eine Beitragszeile. Zeilen, die eine Regel oben
    # schon beanstandet, scheiden aus — ein Fehler, ein Befund.
    for (art, verstoss), policen in sorted(
            beitragspaar_verstoesse(ledger, stamm, gemeldet).items()):
        errors.append("ledger: " + beitragspaar_text(art, verstoss, policen))

    # Die Eindeutigkeit (Runde F, Nachbesserung, Klasse): je Schluessel (Police,
    # Ereignis, Wirkungstag, Betragsart) genau eine Zeile, fuer JEDE Ereignisart.
    # Die Verdopplung der Beitragsereignisse meldet die Paarregel oben; Zeilen,
    # die eine Regel oben beanstandet, scheiden aus — ein Fehler, ein Befund.
    doppelt = doppelte_buchungen(ledger, gemeldet)
    for art in sorted(set(arten[doppelt])):
        errors.append("ledger: " + doppelte_buchung_text(
            art, _policen(doppelt & (arten == art))))

    # Zeilenweise gegen den Stammsatz: Generation, Laufzeit, Vertragsjahr.
    haupt = stamm.set_index("police_id")
    stammteil = haupt.loc[
        ledger["police_id"].to_numpy(),
        ["tarif_generation", "insurance_start", "insurance_end", "duration"],
    ].reset_index(drop=True)
    gen_falsch = ledger["tarif_generation"].to_numpy() != stammteil["tarif_generation"].to_numpy()
    if gen_falsch.any():
        errors.append(
            f"ledger: tarif_generation weicht vom Stammsatz ab (police "
            f"{_policen(gen_falsch)})"
        )
    start = stammteil["insurance_start"]
    datum = ledger["status_date"].reset_index(drop=True)
    vor_beginn = datum < start
    nach_ende = datum > stammteil["insurance_end"]
    if vor_beginn.any():
        errors.append(f"ledger: status_date vor insurance_start (police {_policen(vor_beginn.to_numpy())})")
    if nach_ende.any():
        errors.append(f"ledger: status_date nach insurance_end (police {_policen(nach_ende.to_numpy())})")
    jahr = ledger["vertragsjahr"].reset_index(drop=True)
    ausserhalb = (jahr < 0) | (jahr > stammteil["duration"])
    if ausserhalb.any():
        errors.append(
            f"ledger: vertragsjahr ausserhalb [0, duration] (police "
            f"{_policen(ausserhalb.to_numpy())})"
        )
    vollendet = (
        (datum.dt.year * 12 + datum.dt.month) - (start.dt.year * 12 + start.dt.month)
    ) // 12
    kein_mig = (ledger["ereignis"] != "MIG").reset_index(drop=True)
    unstimmig = kein_mig & ~ausserhalb & ~vor_beginn & (vollendet != jahr)
    if unstimmig.any():
        errors.append(
            "ledger: vertragsjahr ist nicht die Zahl der vollendeten "
            f"Vertragsjahre am status_date (police {_policen(unstimmig.to_numpy())})"
        )

    if historie is not None and len(historie) > 0:
        zustaende = set(zip(
            historie["police_id"].astype("int64"),
            historie["status_code"],
            historie["status_date"],
        ))
        pex_ab = (
            historie[historie["status_code"] == "PEX"]
            .groupby("police_id")["status_date"].min()
        )
        ohne_journal: List[int] = []
        for z in ledger.itertuples(index=False):
            ziel = EREIGNIS_ZUSTAND.get(str(z.ereignis))
            if ziel is None:
                continue
            pid = int(z.police_id)
            if ziel == "PEX":
                gedeckt = pid in pex_ab.index and pex_ab.loc[pid] <= z.status_date
            else:
                gedeckt = (pid, ziel, z.status_date) in zustaende
            if not gedeckt:
                ohne_journal.append(pid)
        if ohne_journal:
            errors.append(
                f"ledger: {len(ohne_journal)} GeVo(s) ohne passende "
                f"Journalzeile (Zustand und Datum), police "
                f"{sorted(set(ohne_journal))[:5]} — eine Buchung, die einen "
                "Zustand herstellt, hat ihre Historienzeile"
            )
    elif historie is not None:
        mit_zustand = ledger["ereignis"].isin(EREIGNIS_ZUSTAND)
        if mit_zustand.any():
            errors.append(
                f"ledger: {int(mit_zustand.sum())} zustandsaendernde GeVo(s) "
                "bei leerer Historie"
            )

    if scheiben is not None:
        errors.extend(_ledger_scheiben_bindung(ledger, scheiben, stamm))
    return errors


def validate_tagesjournal(
    journal: Any, sicht: Any, *, ab_tag: _dt.date, bis_tag: _dt.date
) -> List[str]:
    """Bijektion Tagesjournal <-> Buchungssicht des Ledgers (Fehlerlisten-Idiom).

    ``sicht`` ist die abgeleitete Buchungssicht JEDER Ledger-Zeile (Spalten
    wie das Tagesjournal; erzeugt von
    ``rechner_pipeline.betrieb.tagesjournal.mit_buchungstagen`` — die
    Ableitungsregeln wohnen dort, der Vertrag hier). Geprueft wird die
    Tabelle, wie sie auf der Platte liegt, fuer alle Buchungen mit
    Buchungstag in ``[ab_tag, bis_tag]`` (Betriebsbeginn bis gefuehrter
    Tag):

    * Spalten/dtypes, ``herkunft`` aus :data:`HERKUNFT_VALUES`;
    * Schluessel (police_id, ereignis, status_date, betrag_art) eindeutig — eine
      Buchung wird nicht zweimal gebucht;
    * keine Zeile nach dem gefuehrten Tag, keine vor dem Betriebsbeginn
      (die Vorgeschichte steht im Ledger, nicht im Journal);
    * die Buchungstage steigen in Dateireihenfolge — die Tabelle ist nur
      angefuegt worden;
    * jede Journalzeile verweist auf genau eine Ledger-Zeile, mit
      demselben Betrag, derselben Betragsart, demselben abgeleiteten
      Buchungstag und derselben Herkunft;
    * jede faellige Ledger-Zeile hat genau eine Journalzeile.

    Dieselbe Klasse wie die ERH-Scheiben-Bindung (T18-01) und die
    Betragsidentitaet je Buchung (T20-04): Eine Journalzeile ohne
    Ledger-Gegenstueck oder ein verschobenes Datum ist ein Befund, keine
    Sicht.
    """
    errors: List[str] = []
    cols = list(journal.columns)
    if cols != list(TAGESJOURNAL_NAMES):
        return [f"tagesjournal: Spalten {cols} != erwartet {list(TAGESJOURNAL_NAMES)}"]
    for name, dtype in TAGESJOURNAL_SPALTEN:
        actual = str(journal[name].dtype)
        if actual != dtype:
            errors.append(f"tagesjournal {name}: dtype {actual}, erwartet {dtype}")
    if errors:
        return errors
    if list(sicht.columns) != list(TAGESJOURNAL_NAMES):
        return [f"tagesjournal: Buchungssicht mit Spalten {list(sicht.columns)} "
                f"!= erwartet {list(TAGESJOURNAL_NAMES)}"]
    # Die Betragsart gehoert in den Schluessel: Ein Vorfall bewegt mehr als
    # eine Groesse (ein Zugang eine Summe UND einen Beitrag), und jede steht
    # als eigene Zeile. Ohne sie waeren zwei Zeilen desselben Vorfalls ein
    # doppelter Schluessel.
    schluessel_spalten = ["police_id", "ereignis", "status_date", "betrag_art"]

    def _schluessel(df: Any) -> Any:
        import pandas as pd

        return pd.MultiIndex.from_arrays(
            [df["police_id"].astype("int64"), df["ereignis"].astype(str),
             pd.to_datetime(df["status_date"]), df["betrag_art"].astype(str)],
            names=schluessel_spalten,
        )

    import pandas as pd

    grenze, beginn = pd.Timestamp(bis_tag), pd.Timestamp(ab_tag)
    sicht_schluessel = _schluessel(sicht)
    if sicht_schluessel.duplicated().any():
        return ["tagesjournal: Buchungssicht mit doppeltem Schluessel — der "
                "Ledger ist nicht eindeutig je (police_id, ereignis, "
                "status_date, betrag_art)"]
    faellig = sicht[(sicht["buchungsdatum"] >= beginn) & (sicht["buchungsdatum"] <= grenze)]
    if len(journal) == 0:
        if len(faellig):
            errors.append(
                f"tagesjournal: leer, aber {len(faellig)} Buchung(en) bis "
                f"{pd.Timestamp(bis_tag).date().isoformat()} faellig"
            )
        return errors

    def _policen(maske: Any) -> List[int]:
        return sorted(set(int(p) for p in journal.loc[maske, "police_id"]))[:5]

    fremd = ~journal["herkunft"].isin(HERKUNFT_VALUES)
    if fremd.any():
        errors.append(
            f"tagesjournal: herkunft ausserhalb {list(HERKUNFT_VALUES)} "
            f"(police {_policen(fremd)})"
        )
    schluessel = _schluessel(journal)
    if schluessel.duplicated().any():
        doppelt = journal[schluessel.duplicated()].iloc[0]
        errors.append(
            f"tagesjournal: Buchung doppelt (police {int(doppelt['police_id'])} "
            f"{doppelt['ereignis']} {pd.Timestamp(doppelt['status_date']).date()})"
        )
    zukunft = journal["buchungsdatum"] > grenze
    if zukunft.any():
        errors.append(
            f"tagesjournal: {int(zukunft.sum())} Buchung(en) nach dem gefuehrten "
            f"Tag {pd.Timestamp(bis_tag).date().isoformat()} (police {_policen(zukunft)})"
        )
    vorher = journal["buchungsdatum"] < beginn
    if vorher.any():
        errors.append(
            f"tagesjournal: {int(vorher.sum())} Buchung(en) vor dem Betriebsbeginn "
            f"{pd.Timestamp(ab_tag).date().isoformat()} (police {_policen(vorher)}) "
            "— die Vorgeschichte steht im Ledger, nicht im Tagesjournal"
        )
    daten = journal["buchungsdatum"].to_numpy()
    if len(daten) > 1 and (daten[1:] < daten[:-1]).any():
        stelle = int(_np.argmax(daten[1:] < daten[:-1])) + 1
        errors.append(
            f"tagesjournal: Buchungstage fallen in Zeile {stelle} "
            f"({pd.Timestamp(daten[stelle]).date()} nach "
            f"{pd.Timestamp(daten[stelle - 1]).date()}) — die Tabelle ist nicht "
            "nur angefuegt worden"
        )
    soll = sicht.set_index(sicht_schluessel)
    ohne: List[int] = []
    abweichend: List[str] = []
    for zeile, key in zip(journal.itertuples(index=False), schluessel):
        if key not in soll.index:
            ohne.append(int(zeile.police_id))
            continue
        erwartet = soll.loc[key]
        kopf = (f"police {int(zeile.police_id)} {zeile.ereignis} "
                f"{pd.Timestamp(zeile.status_date).date()}")
        if (float(erwartet["betrag"]) != float(zeile.betrag)
                or str(erwartet["betrag_art"]) != str(zeile.betrag_art)):
            abweichend.append(
                f"{kopf}: Betrag {zeile.betrag!r}/{zeile.betrag_art} statt "
                f"{float(erwartet['betrag'])!r}/{erwartet['betrag_art']}"
            )
        if pd.Timestamp(erwartet["buchungsdatum"]) != pd.Timestamp(zeile.buchungsdatum):
            abweichend.append(
                f"{kopf}: Buchungstag {pd.Timestamp(zeile.buchungsdatum).date()} "
                f"statt abgeleitet {pd.Timestamp(erwartet['buchungsdatum']).date()}"
            )
        if str(erwartet["herkunft"]) != str(zeile.herkunft):
            abweichend.append(
                f"{kopf}: herkunft {zeile.herkunft} statt {erwartet['herkunft']}"
            )
    if ohne:
        errors.append(
            f"tagesjournal: {len(ohne)} Buchung(en) ohne Ledger-Zeile (police "
            f"{sorted(set(ohne))[:5]}) — ein Journal verweist auf Wirkung, es "
            "erfindet keine"
        )
    errors.extend(f"tagesjournal: {a}" for a in abweichend[:5])
    if len(abweichend) > 5:
        errors.append(f"tagesjournal: ... und {len(abweichend) - 5} weitere Abweichungen")
    fehlt = faellig[~_schluessel(faellig).isin(schluessel)]
    if len(fehlt):
        beispiel = fehlt.iloc[0]
        errors.append(
            f"tagesjournal: {len(fehlt)} faellige Buchung(en) fehlen (z. B. police "
            f"{int(beispiel['police_id'])} {beispiel['ereignis']} mit Buchungstag "
            f"{pd.Timestamp(beispiel['buchungsdatum']).date()})"
        )
    return errors


def _ledger_scheiben_bindung(
    ledger: Any, scheiben: Any, stamm: Any = None
) -> List[str]:
    """Jede ERH-Buchung genau eine Scheibe, jede Scheibe genau eine Buchung
    — ueber Police, Datum, Betrag und Erhoehungsjahr (T18-01).

    Ausgenommen sind MITGEBRACHTE Scheiben: Die Alt-Erhoehungen eines
    uebernommenen Vertrags liegen vor seinem Bestandszugang und haben
    keine Buchung im Journal des aufnehmenden Unternehmens — die
    Vorgeschichte wird nicht nachgefahren (Grundsatzdokumentation 9.14),
    ihr Zugang bucht die Gesamtsumme. Eine Scheibe NACH dem Zugang ohne
    Buchung bleibt ein Befund.
    """
    import pandas as _pd

    errors: List[str] = []
    if list(scheiben.columns) != list(SCHEIBEN_NAMES):
        return []  # validate_scheiben meldet den Spaltenfehler
    # Die Bindung gilt zwischen der SUMMEN-Buchung und der Scheibe: Eine
    # Erhoehung bucht seit dem gebuchten Beitrag zwei Zeilen (Summe und
    # Bruttojahresbeitrag), aber nur eine davon ist die Erhoehungssumme,
    # die in der Scheibe steht. Ohne die Art waeren die zwei Zeilen eine
    # Doppelbuchung derselben Police am selben Tag.
    erh = ledger.loc[(ledger["ereignis"] == "ERH")
                     & (ledger["betrag_art"] == "VS_erhoehung"),
                     ["police_id", "status_date", "vertragsjahr", "betrag"]]
    sch = scheiben[["police_id", "erhoehung_datum", "erhoehung_jahr", "sum_insured"]]
    if stamm is not None and len(sch):
        zugang = stamm.set_index("police_id")["bestandszugang"]
        mitgebracht = (
            sch["erhoehung_datum"].to_numpy()
            <= zugang.reindex(sch["police_id"].to_numpy()).to_numpy()
        )
        sch = sch[~mitgebracht]
    doppelt_l = erh.duplicated(["police_id", "status_date"])
    if doppelt_l.any():
        errors.append(
            "ledger: zwei ERH-Buchungen derselben Police am selben Datum "
            f"(police {sorted(set(erh.loc[doppelt_l, 'police_id']))[:5]})"
        )
    doppelt_s = sch.duplicated(["police_id", "erhoehung_datum"])
    if doppelt_s.any():
        errors.append(
            "scheiben: zwei Scheiben derselben Police am selben Datum "
            f"(police {sorted(set(sch.loc[doppelt_s, 'police_id']))[:5]})"
        )
    if errors:
        return errors
    paar = _pd.merge(
        erh, sch, how="outer",
        left_on=["police_id", "status_date"],
        right_on=["police_id", "erhoehung_datum"],
        indicator=True,
    )
    nur_ledger = paar[paar["_merge"] == "left_only"]
    nur_scheibe = paar[paar["_merge"] == "right_only"]
    if len(nur_ledger):
        errors.append(
            f"ledger: {len(nur_ledger)} ERH-Buchung(en) ohne Scheibe "
            f"(police {sorted(set(nur_ledger['police_id']))[:5]})"
        )
    if len(nur_scheibe):
        errors.append(
            f"scheiben: {len(nur_scheibe)} Scheibe(n) ohne ERH-Buchung "
            f"(police {sorted(set(nur_scheibe['police_id']))[:5]})"
        )
    beide = paar[paar["_merge"] == "both"]
    # Cent-Toleranz: Der Kern schreibt beide aus demselben Wert, eine
    # Lieferung darf gerundet haben — ein vertauschter Betrag liegt weit
    # darueber.
    betrag_falsch = (beide["betrag"] - beide["sum_insured"]).abs() > 0.005
    if betrag_falsch.any():
        beispiel = beide[betrag_falsch].iloc[0]
        errors.append(
            f"ledger/scheiben: {int(betrag_falsch.sum())} ERH-Buchung(en) "
            "mit anderem Betrag als ihre Scheibe (z. B. police "
            f"{int(beispiel['police_id'])} am "
            f"{_pd.Timestamp(beispiel['status_date']).date()}: Ledger "
            f"{float(beispiel['betrag']):.2f}, Scheibe "
            f"{float(beispiel['sum_insured']):.2f})"
        )
    jahr_falsch = beide["vertragsjahr"] != beide["erhoehung_jahr"]
    if jahr_falsch.any():
        errors.append(
            f"ledger/scheiben: {int(jahr_falsch.sum())} ERH-Buchung(en) mit "
            "anderem Vertragsjahr als ihre Scheibe (police "
            f"{sorted(set(beide.loc[jahr_falsch, 'police_id']))[:5]})"
        )
    return errors


def validate_abschluss(df: Any) -> List[str]:
    """Der festgeschriebene Stand, bevor er festgeschrieben wird (T18-04).

    Ein Abschluss ist unumkehrbar; was hineingeht, muss ein Bilanzwert
    sein: eine Police je Zeile, ein Stichtag je Datei, jede Zahl endlich.
    Vorher publizierte eine Config mit ``gamma2 = nan`` 394 nichtendliche
    Zahlfelder — die Kontrolle wurde erst danach rot.
    """
    errors: List[str] = []
    cols = list(df.columns)
    # Zwei Gestalten sind gueltig: die heutige und die vor der Umstellung
    # (ohne bewertungskonvention). Eine dritte ist keine.
    if cols not in (list(ABSCHLUSS_NAMES), list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)):
        return [f"abschluss: Spalten {cols} != erwartet {list(ABSCHLUSS_NAMES)} "
                f"(oder vor der Umstellung {list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG)})"]
    if "bewertungskonvention" in cols and len(df):
        werte = sorted({str(v) for v in df["bewertungskonvention"]})
        if len(werte) != 1 or werte[0] not in BEWERTUNGSKONVENTIONEN:
            errors.append(
                f"abschluss: bewertungskonvention {werte} — erwartet genau eine aus "
                f"{list(BEWERTUNGSKONVENTIONEN)} je Datei")
    if len(df) == 0:
        # Leer ist seit ADR-020 eine gueltige Eroeffnungsbilanz (der Vertrag
        # der DATEI ist mit null Zeilen erfuellt); ob er an DIESEM Stichtag
        # legitim leer ist, entscheidet der Erzeuger, nicht der Spaltenvertrag.
        return errors
    if df["police_id"].duplicated().any():
        errors.append("abschluss: police_id nicht eindeutig")
    if df["stichtag"].nunique() != 1:
        errors.append(f"abschluss: mehrere Stichtage in einer Datei ({df['stichtag'].nunique()})")
    if not df["produkt"].isin(PRODUKT_VALUES).all():
        errors.append(f"abschluss: produkt ausserhalb {PRODUKT_VALUES}")
    if not df["status_code"].isin(AKTIVE_STATUS).all():
        errors.append(f"abschluss: status_code ausserhalb {AKTIVE_STATUS} (nur in-force-Vertraege)")
    if df["kern_version"].map(lambda v: not isinstance(v, str) or not v).any():
        errors.append("abschluss: kern_version leer")
    nichtendlich = [sp for sp in ABSCHLUSS_ZAHLEN if _nichtendlich(df[sp])]
    if nichtendlich:
        errors.append(
            f"abschluss: nichtendliche Werte in {nichtendlich} — ein "
            "Bilanzwert ist endlich"
        )
    return errors


class AbschlussKonventionFehler(ValueError):
    """Die Konvention eines gelesenen Abschlusses ist nicht zu bestimmen."""


@_dc.dataclass(frozen=True)
class AbschlussKonvention:
    """Die Bewertungskonvention eines gelesenen Abschlusses.

    ``name`` ist die Konvention, in der die Zahlen der Datei stehen und in
    der sie nachgerechnet werden (``None`` nur fuer einen leeren Abschluss:
    ohne Zeile gibt es keine Bewertung); ``herkunft`` sagt, woher die
    Aussage stammt — aus der Spalte, oder aus ihrem Fehlen.
    """

    name: Optional[str]
    herkunft: str

    @property
    def vor_umstellung(self) -> bool:
        return self.herkunft == HERKUNFT_VOR_UMSTELLUNG


def abschluss_konvention(df: Any) -> AbschlussKonvention:
    """Die Konvention eines gelesenen Abschlusses — die EINE Stelle, die sie sagt.

    Jeder Leser einer Abschlussdatei fragt hier (ueber
    ``bestand.abschluss.lies_abschluss``), keiner liest die Spalte selbst:
    Seit der Umstellung (2026-10-01) gibt es zwei Gestalten, und eine
    Reihe aus beiden ist an der Naht nicht vergleichbar.

    * Spalte vorhanden: ihr Wert — genau einer je Datei, aus
      :data:`BEWERTUNGSKONVENTIONEN`; sonst ein harter Fehler.
    * Spalte FEHLT (Gestalt :data:`ABSCHLUSS_NAMES_VOR_UMSTELLUNG`): die
      Jahreszeile, benannt als vor der Umstellung geschrieben. Das Fehlen
      ist eine Aussage ueber den Schreiber, kein Default.
    * Jede andere Spaltenmenge: harter Fehler — das ist kein Abschluss.
    """
    cols = list(df.columns)
    if cols == list(ABSCHLUSS_NAMES_VOR_UMSTELLUNG):
        if len(df) == 0:
            return AbschlussKonvention(None, HERKUNFT_LEER)
        return AbschlussKonvention(KONVENTION_JAHRESZEILE, HERKUNFT_VOR_UMSTELLUNG)
    if cols != list(ABSCHLUSS_NAMES):
        raise AbschlussKonventionFehler(
            f"abschluss: Spalten {cols} sind weder die heutige Gestalt noch die vor "
            "der Umstellung — die Bewertungskonvention ist nicht zu bestimmen")
    if len(df) == 0:
        return AbschlussKonvention(None, HERKUNFT_LEER)
    werte = sorted({str(v) for v in df["bewertungskonvention"]})
    if len(werte) != 1 or werte[0] not in BEWERTUNGSKONVENTIONEN:
        raise AbschlussKonventionFehler(
            f"abschluss: bewertungskonvention {werte} — erwartet genau eine aus "
            f"{list(BEWERTUNGSKONVENTIONEN)}; eine Datei in zwei Konventionen ist "
            "keine Bilanz")
    return AbschlussKonvention(werte[0], HERKUNFT_SPALTE)


def konventionsbruch(konventionen: Iterable[AbschlussKonvention]) -> Optional[str]:
    """Der Bruch einer Reihe von Abschluessen (None: eine Konvention).

    Wer Abschluesse verschiedener Stichtage in eine Reihe legt, fragt hier:
    Leere Abschluesse tragen keine Bewertung und brechen nichts; zwei
    verschiedene Konventionen sind ein Bruch, den der Leser kennzeichnet
    oder mit diesem Text verweigert.
    """
    namen = sorted({k.name for k in konventionen if k.name is not None})
    if len(namen) <= 1:
        return None
    return (f"Konventionsbruch: die Reihe mischt Abschluesse in {namen} — an der Naht "
            "springt das Deckungskapital ohne Geschaeftsvorfall (Umstellung "
            "2026-10-01, ADR-011 Nachtrag)")


def validate_scheiben(stamm: Any, scheiben: Any, historie: Any = None) -> List[str]:
    """Validate Erhoehungsscheiben against their base contracts (error list).

    Per police: consecutive ``scheiben_id`` starting at 1 in
    ``erhoehung_jahr`` order; each Scheibe must be arithmetically consistent
    with its Hauptvertrag (age at increase, remaining terms, anniversary
    date) and carry a positive Erhoehungssumme. With ``historie`` the
    cross-run invariant is checked too: every Erhoehung lies strictly
    before the contract's Beitragsfreistellung or terminal status (the
    engine can never produce anything else — this catches mixed-up table
    pairs). Empty Scheiben are valid.
    """
    errors: List[str] = []
    cols = list(scheiben.columns)
    if cols != list(SCHEIBEN_NAMES):
        errors.append(f"scheiben: Spalten {cols} != erwartet {list(SCHEIBEN_NAMES)}")
        return errors
    for name, dtype in SCHEIBEN_SPALTEN:
        actual = str(scheiben[name].dtype)
        if actual != dtype:
            errors.append(f"scheiben {name}: dtype {actual}, erwartet {dtype}")
    if len(scheiben) == 0:
        return errors

    unbekannt = set(scheiben["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(f"scheiben: police_id unbekannt: {sorted(unbekannt)[:5]}")
        return errors
    # NaN-Vergleiche sind immer False — fehlende Summen explizit fangen.
    if scheiben["sum_insured"].isna().any():
        errors.append("scheiben: fehlende Werte (NaN) in sum_insured")
    elif _nichtendlich(scheiben["sum_insured"]):
        # inf > 0 ist wahr — die Bandpruefung darunter liesse es durch.
        errors.append("scheiben: nichtendliche Werte (inf) in sum_insured")
    elif (scheiben["sum_insured"] <= 0).any():
        errors.append("scheiben: sum_insured <= 0")
    # gamma1 ist die Rechnungsgrundlage der Scheibe und geht in Beitrag und
    # Reserve ein. Ein Fremdwert rechnet still falsch: NaN laesst den
    # Rueckkaufswert auf 0,00 fallen statt auf NaN, ein negativer Wert
    # erzeugt einen negativen Jahresbeitrag — beides plausibel aussehende
    # Zahlen, die niemandem auffallen. WELCHER Wert richtig ist, sagt das
    # Tarifwerk der Generation (0 fuer das eigene Geschaeft, das gamma1
    # der Zelle bei uebernommenen Generationen mit voller Beitragsformel):
    # das prueft bestand.ledger_bindung.pruefe_scheiben_tarifwerk mit der
    # Config. Hier, ohne Config, bleibt die Form: endlich und nicht negativ.
    # NaN wird getrennt gemeldet, weil jeder Vergleich damit False ist.
    if scheiben["gamma1"].isna().any():
        errors.append("scheiben: fehlende Werte (NaN) in gamma1")
    elif _nichtendlich(scheiben["gamma1"]):
        errors.append(
            "scheiben: gamma1 nicht endlich (inf) — eine Rechnungsgrundlage "
            "ist eine Zahl"
        )
    elif (scheiben["gamma1"] < 0.0).any():
        abweichend = sorted(
            set(scheiben.loc[scheiben["gamma1"] < 0.0, "police_id"])
        )[:5]
        errors.append(
            "scheiben: gamma1 < 0 (ein Verwaltungskostensatz traegt kein "
            f"Vorzeichen), police {abweichend}"
        )
    if not (scheiben["erhoehung_datum"].dt.day == 1).all():
        errors.append("scheiben: erhoehung_datum nicht auf Monatsersten normalisiert")

    if historie is not None and len(historie) > 0:
        # Cross-Check gegen die Statushistorie desselben Laufs: jede
        # Erhoehung liegt strikt vor PEX bzw. terminalem Status.
        grenz_status = ("PEX",) + TERMINALE_STATUS
        grenzen_hist = (
            historie[historie["status_code"].isin(grenz_status)]
            .groupby("police_id")["status_date"]
            .min()
        )
        for police_id, gruppe in scheiben.groupby("police_id", sort=False):
            if police_id in grenzen_hist.index:
                grenze = grenzen_hist.loc[police_id]
                if (gruppe["erhoehung_datum"] >= grenze).any():
                    errors.append(
                        f"scheiben police {police_id}: Erhoehung nicht strikt "
                        f"vor Beitragsfreistellung/terminalem Status "
                        f"({grenze.date()}) — Tabellen aus demselben Lauf?"
                    )

    haupt = stamm.set_index("police_id")
    for police_id, gruppe in scheiben.groupby("police_id", sort=False):
        g = gruppe.sort_values("erhoehung_jahr", kind="stable")
        prefix = f"scheiben police {police_id}"
        if list(g["scheiben_id"]) != list(range(1, 1 + len(g))):
            errors.append(f"{prefix}: scheiben_id nicht fortlaufend ab 1")
        h = haupt.loc[police_id]
        x, n, t = int(h["entry_age"]), int(h["duration"]), int(h["premium_duration"])
        start = h["insurance_start"]
        for _, s in g.iterrows():
            j = int(s["erhoehung_jahr"])
            if not 0 < j < t:
                errors.append(f"{prefix}: erhoehung_jahr {j} ausserhalb (0, t)")
                continue
            if int(s["entry_age"]) != x + j:
                errors.append(f"{prefix}: entry_age != Hauptvertrag-Alter + {j}")
            if int(s["duration"]) != n - j:
                errors.append(f"{prefix}: duration != Restlaufzeit {n - j}")
            if int(s["premium_duration"]) != t - j:
                errors.append(f"{prefix}: premium_duration != Rest-Beitragsdauer {t - j}")
            erwartet = _dt.date(start.year + j, start.month, 1)
            if s["erhoehung_datum"].date() != erwartet:
                errors.append(f"{prefix}: erhoehung_datum != Jahrestag {erwartet}")
    return errors


# --------------------------------------------------------------------------- #
# Kernel coupling: portfolio row + generation -> ModelPoint
# --------------------------------------------------------------------------- #


def model_point_kwargs(row: Mapping[str, Any], generation: Mapping[str, Any]) -> Dict[str, Any]:
    """Join one portfolio row with its tariff generation into ModelPoint kwargs.

    ``generation`` must provide the :data:`GENERATION_FIELDS`; the row provides
    the :data:`CONTRACT_FIELDS` (with portfolio column names). Tariff knobs
    absent from ``generation`` fall back to the kernel defaults
    (:data:`GENERATION_FIELD_DEFAULTS`) — the result always covers the full
    contract.
    """
    kwargs: Dict[str, Any] = {
        "x": int(row["entry_age"]),
        "sex": str(row["sex"]),
        "n": int(row["duration"]),
        "t": int(row["premium_duration"]),
        "sum_insured": float(row["sum_insured"]),
        "zw": int(row["zahlweise"]),
    }
    for name in GENERATION_FIELDS:
        if name in generation:
            kwargs[name] = generation[name]
        elif name in GENERATION_FIELD_DEFAULTS:
            kwargs[name] = GENERATION_FIELD_DEFAULTS[name]
        else:
            raise KeyError(f"Generation-Feld fehlt ohne Default: {name}")
    return kwargs


#: BU-Kernfelder, die aus der Tarifgeneration (Config) kommen — Gegenstueck
#: zu :data:`GENERATION_FIELDS` fuer das zweite Produkt.
BU_GENERATION_FIELDS: Tuple[str, ...] = (
    "zins", "tafel_aktiv", "tafel_i", "tafel_ri", "tafel_ti", "zuschlag",
)


def bu_model_point_kwargs(
    row: Mapping[str, Any], generation: Mapping[str, Any]
) -> Dict[str, Any]:
    """Join one BU portfolio row with its generation into BUModelPoint kwargs.

    Gegenstueck zu :func:`model_point_kwargs` fuer das BU-Produkt: der
    Vertrag liefert Eintrittsalter, Geschlecht, Laufzeit und die versicherte
    Jahresrente, die Generation die Rechnungsgrundlagen (Zins, die vier
    Ausscheideordnungen, Kostenzuschlag).
    """
    kwargs: Dict[str, Any] = {
        "x": int(row["entry_age"]),
        "sex": str(row["sex"]),
        "n": int(row["duration"]),
        "bu_rente": float(row["bu_rente"]),
    }
    for name in BU_GENERATION_FIELDS:
        if name not in generation:
            raise KeyError(f"BU-Generation-Feld fehlt: {name}")
        kwargs[name] = generation[name]
    return kwargs


def validate_reduktionen(
    stamm: Any, reduktionen: Any, historie: Any = None, horizont: Any = None
) -> List[str]:
    """Herabsetzungen und Teilkuendigungen gegen den Stamm pruefen (leer = gueltig).

    Zwei Geschaeftsvorfaelle in einer Tabelle, unterschieden am Verfahren
    (ADR-023; ``reduktion_ereignis``): Die Beitragsherabsetzung (RED) liegt
    in der Beitragszahlungsdauer (``0 < Jahr < t``), die Teilkuendigung
    (TKU, Verfahren ``teilkuendigung``) in der Versicherungsdauer
    (``0 < Jahr < n``). Jede Zeile gehoert zu einem bekannten Vertrag, das
    Datum ist der Jahrestag, und der fortgefuehrte Anteil liegt echt
    zwischen 0 und 1: ``1.0`` ist kein Vorgang, ``0.0`` ist eine
    Beitragsfreistellung bzw. ein Rueckkauf.

    **Beliebig viele Vorgaenge je Police, in jeder Reihenfolge** (Entscheid
    des Maintainers 2026-10-01; klv.md 7.3). Die Tabelle fuehrt die FOLGE:
    je Police so viele Zeilen wie Vorgaenge. Der Kern faltet sie in Zustaende
    (``kern.vorgangsfolge.Vorgangsfolge``); am selben Jahrestag gilt die
    Reihenfolge der Engine (Herabsetzung vor Teilkuendigung). Eindeutig ist
    deshalb (Police, Jahr, Vorgang): Zwei gleiche Vorgaenge am selben
    Jahrestag haetten keine bestimmte Reihenfolge — ein benannter Fehler
    statt einer Zahl, die niemand herleiten kann. (Bis 2026-10-01: hoechstens
    ein Vorgang je Police, Annahme A4 — ersetzt.)

    Mit ``historie`` zusaetzlich die Reihenfolge gegen die Zustaende: Eine
    BEITRAGSHERABSETZUNG setzt einen laufenden Beitrag voraus, liegt also
    echt VOR einer Beitragsfreistellung (PEX-Jahr > Jahr; eine Herabsetzung
    nach der Beitragsfreistellung gibt es in der Welt der PLV nicht, Ausweg
    die Teilkuendigung). Die TEILKUENDIGUNG ist auch NACH einer
    Beitragsfreistellung moeglich, auch im Jahr der Freistellung selbst (sie
    folgt ihr am selben Jahrestag) — sie kuendigt einen Anteil der
    beitragsfreien Summe (klv.md 7.2). Beide liegen vor jedem Endzustand.
    (Bis 2026-10-01 schloss die Beitragsfreistellung auch die
    Teilkuendigung aus, Pruefrunde T27, Befund RC03 — der Kern hatte fuer sie
    keine Regel; die hat er jetzt, Entscheid B3 vom 2026-10-01.)

    **Der beitragsfrei AUSFINANZIERTE Nachlauf ist kein PEX.** Nach dem
    Ende der Beitragszahlung (``premium_duration`` <= Jahr < ``duration``)
    ist der Vertrag nicht beitragsfrei GESTELLT: Dort gibt es die
    Teilkuendigung, die einen Summenanteil kuendigt und keinen laufenden
    Beitrag voraussetzt (Entscheid des Maintainers 2026-10-01, klv.md 7.2);
    Kern, Engine und Bewertung tragen sie bis zur Versicherungsdauer.

    **Die Herabsetzung liegt im Lauf** (Runde C, Befund RC02): nach dem
    Bestandszugang des Vertrags (``bestandszugang``; beim eigenen Geschaeft
    der Beginn) und, mit ``horizont`` (dem im Laufmanifest belegten, nicht
    einem Aufrufwert), nicht dahinter. Was davor liegt, ist Vorgeschichte
    der abgebenden Gesellschaft; was dahinter liegt, hat der Lauf nicht
    gefahren. Beides ist keine Buchung dieses Laufs und unbelegt.
    """
    errors: List[str] = []
    cols = list(reduktionen.columns)
    if cols != list(REDUKTIONEN_NAMES):
        return [
            f"reduktionen: Spalten weichen ab: erwartet "
            f"{list(REDUKTIONEN_NAMES)}, vorhanden {cols}"
        ]
    for name, dtype in REDUKTIONEN_SPALTEN:
        actual = str(reduktionen[name].dtype)
        if actual != dtype:
            errors.append(
                f"reduktionen: Spalte {name}: dtype {actual}, erwartet {dtype}")
    if errors:
        return errors
    unbekannt = set(reduktionen["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(
            f"reduktionen: police_ids ausserhalb des Bestands: "
            f"{sorted(unbekannt)[:5]}")
    import pandas as pd

    vorgang_je_zeile = reduktionen["verfahren"].map(reduktion_ereignis)
    schluessel = pd.DataFrame({"police_id": reduktionen["police_id"],
                               "reduktion_jahr": reduktionen["reduktion_jahr"],
                               "vorgang": vorgang_je_zeile})
    if schluessel.duplicated().any():
        doppelt = schluessel[schluessel.duplicated()].head(5)
        errors.append(
            "reduktionen: zwei gleiche Vorgaenge am selben Jahrestag: "
            + ", ".join(f"police {int(p)} {v} Jahr {int(j)}" for p, j, v in zip(
                doppelt["police_id"], doppelt["reduktion_jahr"], doppelt["vorgang"]))
            + " — je Jahrestag hoechstens eine Herabsetzung und eine "
            "Teilkuendigung, sonst ist ihre Reihenfolge nicht bestimmt; Ausweg: "
            "die Anteile zu einem Vorgang zusammenfassen (f = f1 x f2)")
    ausser = [
        float(a) for a in reduktionen["anteil"] if not 0.0 < float(a) < 1.0]
    if ausser:
        errors.append(
            f"reduktionen: anteil ausserhalb (0, 1): {sorted(ausser)[:5]} — "
            "1.0 ist keine Herabsetzung, 0.0 ist eine Beitragsfreistellung "
            "und wird als PEX gefuehrt")
    fremd = sorted({
        str(v) for v in reduktionen["verfahren"]
        if not isinstance(v, str) or v not in RED_VERFAHREN})
    if fremd:
        errors.append(
            f"reduktionen: verfahren {fremd} unbekannt (bekannt: "
            f"{list(RED_VERFAHREN)})")
    import pandas as pd

    haupt = stamm.set_index("police_id")
    for pid, jahr, verfahren, datum in zip(
            reduktionen["police_id"], reduktionen["reduktion_jahr"],
            reduktionen["verfahren"], reduktionen["reduktion_datum"]):
        pid, jahr = int(pid), int(jahr)
        if pid not in haupt.index:
            continue
        if str(haupt.loc[pid].get("produkt", "klv")) != "klv":
            # Die Herabsetzung ist ein GeVo der Kapitalversicherung (klv.md
            # 7.1); eine BU fuehrt eine Jahresrente, keine Summe. Vorher
            # blieb eine RED-Zeile auf einem BU-Vertrag ungeprueft und
            # zaehlte trotzdem als hergeleitet.
            errors.append(
                f"reduktionen: police {pid}: Herabsetzung auf einem Vertrag des "
                f"Produkts {haupt.loc[pid].get('produkt')!r} — nur die "
                "Kapitalversicherung kennt sie")
            continue
        t = int(haupt.loc[pid, "premium_duration"])
        n = int(haupt.loc[pid, "duration"])
        if reduktion_ereignis(verfahren) == "TKU":
            # Teilkuendigung (eigener Vorfall, ADR-023): kuendigt einen
            # Summenanteil und setzt keinen laufenden Beitrag voraus — die
            # Grenze ist die Versicherungsdauer (Kern 3.4.0, Fund N6).
            if not 0 < jahr < n:
                errors.append(
                    f"reduktionen: police {pid}: Teilkuendigung im Jahr {jahr} "
                    f"ausserhalb der Versicherungsdauer (0, {n}) — nach dem "
                    "Ablauf gibt es nichts mehr zu kuendigen")
        elif not 0 < jahr < t:
            errors.append(
                f"reduktionen: police {pid}: Beitragsherabsetzung im Jahr {jahr} "
                f"ausserhalb der Beitragszahlungsdauer (0, {t}) — ohne laufenden "
                "Beitrag gibt es nichts herabzusetzen; Ausweg: die Teilkuendigung "
                "(Verfahren teilkuendigung, Ledger TKU)")
        # Der Wirkungstag ist der Jahrestag des Reduktionsjahres — an nichts
        # anderem haengt die Bewertung (Angriffsrunde 2, Fund N16: zwei
        # Sichten desselben Bestands zum selben Stichtag wichen um 20.880 EUR
        # ab, bei gruenem P-B1, weil das Datum frei war).
        jahrestag = reduktion_jahrestag(haupt.loc[pid, "insurance_start"], jahr)
        if pd.Timestamp(datum) != jahrestag:
            errors.append(
                f"reduktionen: police {pid}: reduktion_datum {pd.Timestamp(datum).date()} "
                f"ist nicht der Jahrestag {jahrestag.date()} des Reduktionsjahres {jahr}")
        zugang = haupt.loc[pid, "bestandszugang"]
        if pd.notna(zugang) and pd.Timestamp(datum) <= pd.Timestamp(zugang):
            errors.append(
                f"reduktionen: police {pid}: Herabsetzung am {pd.Timestamp(datum).date()} "
                f"liegt nicht nach dem Bestandszugang {pd.Timestamp(zugang).date()} — "
                "Vorgeschichte der abgebenden Gesellschaft, keine Buchung dieses "
                "Laufs; die Engine simuliert einen uebernommenen Vertrag erst ab "
                "seinem Zugangsjahr")
        if horizont is not None and pd.Timestamp(datum) > pd.Timestamp(horizont):
            errors.append(
                f"reduktionen: police {pid}: Herabsetzung am {pd.Timestamp(datum).date()} "
                f"liegt nach dem belegten Horizont {pd.Timestamp(horizont).date()} — "
                "der Lauf hat sie nicht gefahren, sie ist unbelegt")
    if historie is not None and len(historie):
        # Beitragsfrei (PEX-Jahr <= Jahr) schliesst die BEITRAGSHERABSETZUNG
        # aus — es gibt keinen Beitrag mehr (klv.md 7.1; Ausweg TKU). Die
        # Teilkuendigung kuendigt dann einen Anteil der beitragsfreien Summe
        # (klv.md 7.2, Entscheid B3 vom 2026-10-01). Der terminale Zustand schliesst beide aus.
        pex_ab = (
            historie[historie["status_code"] == "PEX"]
            .groupby("police_id")["status_date"].min()
        )
        grenzen_terminal = (
            historie[historie["status_code"].isin(TERMINALE_STATUS)]
            .groupby("police_id")["status_date"].min()
        )
        for pid, jahr, datum, verfahren in zip(reduktionen["police_id"],
                                               reduktionen["reduktion_jahr"],
                                               reduktionen["reduktion_datum"],
                                               reduktionen["verfahren"]):
            pid, jahr = int(pid), int(jahr)
            tk = str(verfahren) == "teilkuendigung"
            if not tk and pid in pex_ab.index and pid in haupt.index:
                beginn = pd.Timestamp(haupt.loc[pid, "insurance_start"])
                pex = pd.Timestamp(pex_ab.loc[pid])
                pex_jahr = ((pex.year * 12 + pex.month)
                            - (beginn.year * 12 + beginn.month)) // 12
                if pex_jahr <= jahr:
                    errors.append(
                        f"reduktionen: police {pid}: Beitragsherabsetzung im Jahr "
                        f"{jahr} liegt nicht vor dem Zustandswechsel am {pex.date()} "
                        f"(Beitragsfreistellung im Jahr {pex_jahr}) — ein "
                        "beitragsfreier Vertrag hat keinen Beitrag, den eine "
                        "Herabsetzung senken koennte; Ausweg: die Teilkuendigung "
                        "(Verfahren teilkuendigung, Ledger TKU), die einen Anteil der "
                        "beitragsfreien Summe kuendigt")
                    continue
            if pid not in grenzen_terminal.index:
                continue
            if datum >= grenzen_terminal.loc[pid]:
                errors.append(
                    f"reduktionen: police {pid}: Herabsetzung am "
                    f"{datum.date()} liegt nicht vor dem Zustandswechsel am "
                    f"{grenzen_terminal.loc[pid].date()} — "
                    + ("nach dem Ende gibt es nichts mehr zu kuendigen" if tk
                       else "eine Herabsetzung setzt einen laufenden Beitrag voraus"))
    return errors


def validate_verankerung(
    stamm: Any, verankerung: Any, historie: Any = None
) -> List[str]:
    """Verankerungsattribute gegen den Stamm pruefen (leer = gueltig).

    Jede Zeile gehoert zu einem bekannten Vertrag, je Vertrag hoechstens
    eine Verankerung, und t_a liegt INNERHALB der Vertragslaufzeit — ein
    Rechenpunkt nach dem Ablauf verankert nichts. ``dk_ta`` muss belegt
    sein: Eine Verankerung ohne Wert ist keine.

    Mit ``historie`` zusaetzlich die Invariante, dass Verankerung und
    Vorgeschichte DIESELBE Geschichte erzaehlen: Wer eine
    Beitragsfreistellung vor t_a bucht, darf t_a nicht als
    beitragspflichtig ausweisen, und umgekehrt. Die Bewertung muesste aus
    einer solchen Lieferung sonst eine Zahl machen, die aus keiner der
    beiden Aussagen folgt — je nachdem, welchen der beiden Fakten sie
    liest, kaeme ein anderer Wert heraus (Review T25-06).
    """
    errors: List[str] = []
    cols = list(verankerung.columns)
    if cols != list(VERANKERUNG_NAMES):
        return [
            f"verankerung: Spalten weichen ab: erwartet "
            f"{list(VERANKERUNG_NAMES)}, vorhanden {cols}"
        ]
    for name, dtype in VERANKERUNG_SPALTEN:
        actual = str(verankerung[name].dtype)
        if actual != dtype:
            errors.append(f"verankerung: Spalte {name}: dtype {actual}, erwartet {dtype}")
    if errors:
        return errors
    unbekannt = set(verankerung["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        errors.append(
            f"verankerung: police_ids ausserhalb des Bestands: "
            f"{sorted(unbekannt)[:5]}"
        )
    if verankerung["police_id"].duplicated().any():
        doppelt = sorted(
            verankerung.loc[verankerung["police_id"].duplicated(), "police_id"]
        )[:5]
        errors.append(
            f"verankerung: mehrere Verankerungen je Police: {doppelt} — "
            "t_a ist der EINE letzte exakte Rechenpunkt (9.12)"
        )
    if (verankerung["monate_ta"] < 0).any():
        errors.append("verankerung: monate_ta negativ")
    if verankerung["dk_ta"].isna().any():
        errors.append("verankerung: dk_ta fehlt (NaN) — eine Verankerung ohne Wert ist keine")
    if historie is not None and len(historie):
        # Vorgeschichte und Verankerungszustand muessen dieselbe Geschichte
        # erzaehlen — sonst haengt der Wert davon ab, welchen der beiden
        # Fakten ein Konsument liest (Review T25-06).
        beginn = stamm.set_index("police_id")["insurance_start"]
        pex_monate: Dict[int, int] = {}
        for pid, code, datum in zip(
            historie["police_id"], historie["status_code"],
            historie["status_date"],
        ):
            pid = int(pid)
            if code != "PEX" or pid not in beginn.index:
                continue
            b = beginn.loc[pid]
            monate = (datum.year - b.year) * 12 + (datum.month - b.month)
            pex_monate[pid] = min(monate, pex_monate.get(pid, monate))
        for pid, monate, zustand in zip(
            verankerung["police_id"], verankerung["monate_ta"],
            verankerung["zustand_ta"],
        ):
            pid, monate = int(pid), int(monate)
            if pid not in beginn.index:
                continue
            vor_ta = pid in pex_monate and pex_monate[pid] <= monate
            if vor_ta and zustand != "beitragsfrei":
                errors.append(
                    f"verankerung: police {pid}: Beitragsfreistellung im "
                    f"Vertragsmonat {pex_monate[pid]}, t_a aber bei {monate} "
                    f"mit zustand_ta {zustand!r} — die Vorgeschichte und der "
                    "Verankerungszustand widersprechen sich"
                )
            elif not vor_ta and zustand == "beitragsfrei":
                errors.append(
                    f"verankerung: police {pid}: zustand_ta 'beitragsfrei', "
                    "aber keine Beitragsfreistellung bis zum Vertragsmonat "
                    f"{monate} in der Vorgeschichte"
                )
    fremd = verankerung["zustand_ta"].map(
        lambda z: not isinstance(z, str) or z not in ZUSTAENDE_TA
    )
    if fremd.any():
        werte = sorted({str(z) for z in verankerung.loc[fremd, "zustand_ta"]})[:5]
        errors.append(
            f"verankerung: zustand_ta {werte} nicht abgebildet (bekannt: "
            f"{list(ZUSTAENDE_TA)}) — die Tabelle spricht die Sprache der "
            "Uebernahme, ein fremder Wert faellt hier und nicht erst im Kern"
        )
    if (verankerung["verweildauer_ta"] < 0).any():
        errors.append("verankerung: verweildauer_ta negativ")
    laufzeit = stamm.set_index("police_id")["duration"]
    grenze = verankerung["police_id"].map(laufzeit) * 12
    zu_spaet = verankerung["monate_ta"] > grenze
    if zu_spaet.fillna(False).any():
        betroffen = sorted(verankerung.loc[zu_spaet.fillna(False), "police_id"])[:5]
        errors.append(
            f"verankerung: monate_ta nach Vertragsablauf (z. B. police "
            f"{betroffen}) — nach dem Ablauf gibt es keinen Rechenpunkt"
        )
    zu_lang = verankerung["verweildauer_ta"] > verankerung["monate_ta"] // 12
    if zu_lang.any():
        errors.append(
            "verankerung: verweildauer_ta laenger als die Vertragszeit bis "
            "t_a — im Zustand kann niemand laenger sein als es den Vertrag gibt"
        )
    return errors


def validate_merkmale(
    stamm: Any, merkmale: Any, dimensionen: Any = None
) -> List[str]:
    """Merkmalsauspraegungen gegen Stamm und Tarifwerk pruefen.

    Ohne ``dimensionen`` bleibt es bei der Struktur: Spaltenvertrag,
    dtypes, bekannte Policen, keine doppelte Dimension je Vertrag.

    Mit ``dimensionen`` — ein Mapping Dimension auf erlaubte
    Auspraegungen, wie es die Spez der Generation fuehrt — wird das
    VOKABULAR geprueft. Genau das unterscheidet diese Tabelle von einem
    Attribut-Beutel: Wer eine Dimension erfindet oder eine Auspraegung
    schreibt, die es im Tarifwerk nicht gibt, waehlt keine Zelle, sondern
    eine Zelle, die es nicht gibt.
    """
    errors: List[str] = []
    cols = list(merkmale.columns)
    if cols != list(MERKMALE_NAMES):
        errors.append(f"merkmale: Spalten {cols} != erwartet {list(MERKMALE_NAMES)}")
        return errors
    for name, dtype in MERKMALE_SPALTEN:
        actual = str(merkmale[name].dtype)
        if actual != dtype:
            errors.append(f"merkmale {name}: dtype {actual}, erwartet {dtype}")
    if len(merkmale) == 0:
        return errors

    unbekannt = sorted(set(merkmale["police_id"]) - set(stamm["police_id"]))
    if unbekannt:
        errors.append(
            f"merkmale: {len(unbekannt)} Police(n) nicht im Stamm, z. B. "
            f"{unbekannt[:5]}")

    doppelt = merkmale.duplicated(subset=["police_id", "dimension"])
    if bool(doppelt.any()):
        betroffen = sorted(set(merkmale.loc[doppelt, "police_id"]))
        errors.append(
            f"merkmale: {len(betroffen)} Police(n) tragen eine Dimension "
            f"mehrfach, z. B. {betroffen[:5]} — eine Zelle waehlt je "
            "Dimension GENAU eine Auspraegung")

    if dimensionen is not None:
        erlaubt = {str(k): {str(v) for v in werte}
                   for k, werte in dict(dimensionen).items()}
        fremde = sorted(set(merkmale["dimension"]) - set(erlaubt))
        if fremde:
            errors.append(
                f"merkmale: Dimension(en) {fremde} sind im Tarifwerk nicht "
                f"deklariert (bekannt: {sorted(erlaubt)})")
        for dim, gueltig in erlaubt.items():
            teil = merkmale[merkmale["dimension"] == dim]
            falsch = sorted(set(teil["auspraegung"]) - gueltig)
            if falsch:
                errors.append(
                    f"merkmale {dim}: Auspraegung(en) {falsch} nicht "
                    f"deklariert (erlaubt: {sorted(gueltig)})")
    return errors


# --------------------------------------------------------------------------- #
# Korrekturschicht als Vertragsattribut (Freischaltung, Schritt 5)
# --------------------------------------------------------------------------- #


def schichten_zeile(police_id: int, beleg: Mapping[str, Any]) -> Dict[str, Any]:
    """Der ``hist``-Belegeintrag (``Schichtparameter.als_beleg()``) als Zeile."""
    import json as _json

    return {
        "police_id": int(police_id),
        "schichttyp": str(beleg["schichttyp"]),
        "verankerungszustand": str(beleg["verankerungszustand"]),
        "verweildauer": int(beleg["verweildauer"]),
        "rho": float(beleg["rho"]),
        "formfunktion": str(beleg["formfunktion"]),
        "formparameter": _json.dumps(dict(beleg.get("formparameter") or {}),
                                     sort_keys=True),
        "vererbend": _json.dumps([list(p) for p in beleg.get("vererbend") or []]),
        "kohorte": str(beleg.get("kohorte", "t_a")),
        "in_ueberschuss": bool(beleg.get("in_ueberschuss", True)),
        "in_zzr": bool(beleg.get("in_zzr", True)),
        "rumpfmonate": int(beleg.get("rumpfmonate", 0)),
    }


def validate_schichten(stamm: Any, schichten: Any, verankerung: Any) -> List[str]:
    """Schichten gegen Stamm und Verankerung (Fehlerliste, leer = ok).

    Jede Schicht gehoert zu genau einer Police des Stamms, die eine
    Verankerung traegt (ohne t_a ist eine Schicht nicht bewertbar), und
    ihre Zeile muss der Form nach ein Parametersatz sein — dieselben
    Grenzen wie die Konstruktor-Wachen von ``Schichtparameter``
    (Schichttyp, endliches rho, Verweildauer, Rumpfmonate, JSON-Felder),
    hier ohne den Kern zu importieren; die Konstruktion selbst macht
    ``bestand.schichten.schichten_je_police``.
    """
    import json as _json
    import math as _math

    errors: List[str] = []
    cols = list(schichten.columns)
    if cols != list(SCHICHTEN_NAMES):
        return [f"schichten: Spalten {cols} != erwartet {list(SCHICHTEN_NAMES)}"]
    for name, dtype in SCHICHTEN_SPALTEN:
        actual = str(schichten[name].dtype)
        if actual != dtype:
            errors.append(f"schichten {name}: dtype {actual}, erwartet {dtype}")
    if errors or len(schichten) == 0:
        return errors
    if schichten["police_id"].duplicated().any():
        errors.append("schichten: police_id nicht eindeutig (eine Schicht je Police)")
    unbekannt = sorted(set(schichten["police_id"]) - set(stamm["police_id"]))
    if unbekannt:
        errors.append(f"schichten: police_id unbekannt im Bestand: {unbekannt[:5]}")
    if verankerung is None or len(verankerung) == 0:
        errors.append(
            "schichten ohne verankerung: eine Schicht braucht ihren "
            "Verankerungszeitpunkt (verankerung.parquet)")
    else:
        ohne_anker = sorted(set(schichten["police_id"]) - set(verankerung["police_id"]))
        if ohne_anker:
            errors.append(
                f"schichten: police ohne Verankerung: {ohne_anker[:5]}")
        # Die GEGENRICHTUNG (Review T25-04): Verankerung und Schicht
        # beschreiben DIESELBE Population. Der Produzent
        # (gates.verankerung_belegen) schreibt die Tabelle nur, wenn JEDE
        # verankerte Police eine getragene Schicht hat — sonst ist der Lauf
        # rot und es entsteht keine Tabelle. Eine verankerte Police ohne
        # Schicht heisst also: Die beiden Tabellen stammen nicht aus
        # demselben Lauf, und die Bewertung dieses Vertrags rechnet ohne
        # seine Korrektur weiter, ohne dass jemand es sagt.
        ohne_schicht = sorted(set(verankerung["police_id"]) - set(schichten["police_id"]))
        if ohne_schicht:
            errors.append(
                f"verankerung: police ohne Schicht: {ohne_schicht[:5]} — "
                "Verankerung und Korrekturschicht stammen nicht aus demselben "
                "Lauf von gates.verankerung_belegen")
    for zeile in schichten.to_dict("records"):
        prefix = f"schichten police {zeile['police_id']}"
        if str(zeile["schichttyp"]) not in ("hist", "conv"):
            errors.append(f"{prefix}: schichttyp {zeile['schichttyp']!r} unbekannt")
        if str(zeile["verankerungszustand"]) not in VERANKERUNGSZUSTAENDE:
            errors.append(
                f"{prefix}: verankerungszustand {zeile['verankerungszustand']!r} "
                f"ist kein Erlebenszustand des Zustandsmodells (bekannt: "
                f"{list(VERANKERUNGSZUSTAENDE)})"
            )
        if not _math.isfinite(float(zeile["rho"])):
            errors.append(f"{prefix}: rho ist {zeile['rho']!r}")
        if int(zeile["verweildauer"]) < 0:
            errors.append(f"{prefix}: verweildauer negativ")
        if not 0 <= int(zeile["rumpfmonate"]) < 12:
            errors.append(f"{prefix}: rumpfmonate {zeile['rumpfmonate']} ausserhalb 0..11")
        for feld in ("formparameter", "vererbend"):
            try:
                _json.loads(zeile[feld])
            except (TypeError, ValueError):
                errors.append(f"{prefix}: {feld} ist kein JSON")
    return errors


# --------------------------------------------------------------------------- #
# Herabsetzung: die Soll-Buchungen und ihre Bindung — EINE Regel fuer P-B1
# und die Fuehrungsprobe (Angriffsrunde nach T27)
# --------------------------------------------------------------------------- #


def red_sollbuchungen(
    vs_neu: float, absorbiert: float, auszahlung_rechnerisch: Optional[float],
) -> Dict[str, float]:
    """Die Buchungen, die EINE registrierte Herabsetzung oder Teilkuendigung
    im Ledger haben muss — Betragsart -> Betrag. Die eine Regel fuer P-B1
    und die Fuehrungsprobe (Angriffsrunde nach T27).

    ``auszahlung_rechnerisch`` None: Beitragsherabsetzung (``RED``) — die
    neue Gesamtsumme (``VS_herabsetzung``) und, wenn eine traegt, die
    absorbierte Korrekturschicht. Sonst Teilkuendigung (``TKU``):
    ``VS_teilkuendigung``, die Schicht, die Auszahlung auf null gekappt und
    die Kappung als eigene Zeile, wenn gekappt wurde — dieselbe Regel wie in
    der Engine.
    """
    if auszahlung_rechnerisch is None:
        aus: Dict[str, float] = {"VS_herabsetzung": vs_neu}
        if absorbiert:
            aus["dDK_absorption"] = absorbiert
        return aus
    aus = {"VS_teilkuendigung": vs_neu}
    if absorbiert:
        aus["dDK_absorption"] = absorbiert
    aus["RKW_teilkuendigung"] = max(0.0, auszahlung_rechnerisch)
    if auszahlung_rechnerisch < 0.0:
        aus["Kappung_teilkuendigung"] = -auszahlung_rechnerisch
    return aus


def red_bindung_fehler(
    pid: int, jahr: int, anteil: float, verfahren: str, *,
    beitragsdauer: int, generation_verfahren: Optional[str], annahmen: Any,
) -> List[str]:
    """Vorgang, Verfahren und Anteil einer registrierten Zeile gegen das
    System — die EINE Regel fuer P-B1 und die Fuehrungsprobe.

    **Beitragsherabsetzung** (``RED``, Verfahren prospektiv/mit_abzug): Das
    Verfahren ist das der Generation (Tarifwerk ``red_verfahren``), das Jahr
    liegt in der Beitragszahlungsdauer, Rate ``annahmen.herabsetzung`` und
    Anteil ``annahmen.red_anteil`` belegen sie. Der uebernommene Tarif
    (``red_verfahren = teilkuendigung``) kennt keine Beitragsherabsetzung —
    sein einziger Vorgang ist die Teilkuendigung (Entscheid des Maintainers
    2026-10-01); eine ``RED`` dort ist ein Befund.

    **Teilkuendigung** (``TKU``): moeglich in jeder Generation; belegt allein
    durch die Rate ``annahmen.teilkuendigung`` mit dem Anteil ``tk_anteil``.
    Der fruehere zweite Weg (Herabsetzungswunsch des uebernommenen Tarifs als
    Teilkuendigung ausgefuehrt, Annahme A1) ist mit dem Entscheid vom
    2026-10-01 entfallen: Dieser Tarif zieht nur aus dem Strom der
    Teilkuendigung.

    Kennen die Annahmen den Vorgang nicht (Rate oder Anteil null), ist die
    Zeile unbelegt, nicht frei (Runde C RC05, Angriffsrunde nach T27). Kein
    Default fuer Rate und Anteil: Wer die Regel ruft, gibt die Annahmen.
    """
    fehler: List[str] = []
    red_rate = float(annahmen.herabsetzung(0.0))
    red_anteil = float(getattr(annahmen, "red_anteil", 0.0) or 0.0)
    tk_rate = float(annahmen.teilkuendigung(0.0))
    tk_anteil = float(getattr(annahmen, "tk_anteil", 0.0) or 0.0)
    if reduktion_ereignis(verfahren) == "TKU":
        if not (tk_rate and tk_anteil):
            fehler.append(
                f"reduktionen police {pid}: Teilkuendigung mit Anteil {anteil!r}, die "
                f"Annahmen kennen keine (teilkuendigung a = {tk_rate!r}, tk_anteil = "
                f"{tk_anteil!r}) — der Anteil ist unbelegt")
        elif abs(anteil - tk_anteil) > 1e-12:
            fehler.append(
                f"reduktionen police {pid}: Anteil {anteil!r} der Teilkuendigung, "
                f"die Annahmen sagen tk_anteil = {tk_anteil!r}")
        return fehler
    if generation_verfahren is not None and verfahren != generation_verfahren:
        if generation_verfahren == TEILKUENDIGUNG_VERFAHREN:
            fehler.append(
                f"reduktionen police {pid}: Beitragsherabsetzung mit Verfahren {verfahren!r} in "
                "einem Tarif, der keine Beitragsherabsetzung kennt (Tarifwerk: "
                "red_verfahren = teilkuendigung, der uebernommene Tarif) — sein "
                "einziger Vorgang ist die Teilkuendigung (TKU); was die Quelle "
                "'Herabsetzung' nennt, ist im Vokabular der PLV die Teilkuendigung")
        else:
            fehler.append(
                f"reduktionen police {pid}: Verfahren {verfahren!r}, das Tarifwerk "
                f"der Generation sagt {generation_verfahren!r}")
    if int(jahr) >= int(beitragsdauer):
        fehler.append(
            f"reduktionen police {pid}: Beitragsherabsetzung im Jahr {jahr} nach "
            f"dem Beitragsende (t = {beitragsdauer}) — es gibt keinen Beitrag; "
            "Ausweg: die Teilkuendigung (TKU)")
    if not red_anteil:
        fehler.append(
            f"reduktionen police {pid}: Herabsetzung mit Anteil {anteil!r}, die "
            "Annahmen kennen keine (red_anteil = 0) — der Anteil ist unbelegt")
    elif not red_rate:
        fehler.append(
            f"reduktionen police {pid}: Herabsetzung mit Anteil {anteil!r}, die "
            "Annahmen kennen keine (herabsetzung a = 0, die Rate ist null) — "
            "der Anteil ist unbelegt; red_anteil allein erzeugt keine Herabsetzung")
    elif abs(anteil - red_anteil) > 1e-12:
        fehler.append(
            f"reduktionen police {pid}: Anteil {anteil!r}, die Annahmen sagen "
            f"red_anteil = {red_anteil!r}")
    return fehler


def red_vollstaendigkeit_fehler(
    pid: int, jahr: int, eigene: pd.DataFrame, soll_arten: Iterable[str],
    wirkungstag: pd.Timestamp, *, ereignis: str, fremde_arten: bool = True,
) -> List[str]:
    """Die RED- bzw. TKU-Zeilen (``ereignis``) einer Police gegen die Soll-Menge: jede Soll-Art
    genau einmal, am Wirkungstag der Tabelle, und (``fremde_arten``) keine
    Art, die die Herabsetzung nicht erzeugt — P-B1 meldet diese schon als
    unbelegte Buchung und schaltet den Teil ab."""
    import pandas as pd

    fehler: List[str] = []
    falscher_tag = eigene[eigene["status_date"] != wirkungstag]
    if len(falscher_tag):
        fehler.append(
            f"police {pid} {ereignis} Jahr {jahr}: Wirkungstag der Buchung "
            f"{pd.Timestamp(falscher_tag['status_date'].iloc[0]).date()} "
            f"ist nicht der der Reduktionstabelle {pd.Timestamp(wirkungstag).date()}")
    soll_arten = list(soll_arten)
    for art in soll_arten:
        n = int((eigene["betrag_art"] == art).sum())
        if n != 1:
            fehler.append(f"police {pid} {ereignis} Jahr {jahr}: {art} "
                          + ("fehlt" if n == 0 else f"{n}-mal gebucht"))
    fremd = sorted(set(str(a) for a in eigene["betrag_art"]) - set(soll_arten))
    if fremde_arten and fremd:
        fehler.append(f"police {pid} {ereignis} Jahr {jahr}: {fremd} gehoert nicht zu dieser Herabsetzung")
    return fehler
