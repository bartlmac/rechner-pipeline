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
from typing import Any, Dict, List, Mapping, Tuple

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
    ("ereignis", "object"),          # PEX|STO|TOD|ABL|ERH|ZUG|INV|REA|RED
    ("vertragsjahr", "int64"),       # booked anniversary (completed years; ZUG: 0)
    ("status_date", "datetime64[ns]"),
    # Bezugsgroesse des Betrags — je Produkt verschieden: KLV fuehrt
    # Versicherungssummen/Rueckkaufswerte, BU die betroffene Jahresrente.
    ("betrag_art", "object"),        # RKW | VS_bfr | Todesfallleistung | Ablaufleistung | VS_erhoehung | VS_herabsetzung | VS (ZUG) | BU_Jahresrente
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
    "ZUG", "MIG", "ERH", "RED", "PEX", "INV", "REA", "STO", "TOD", "ABL",
)

#: Welche Bezugsgroesse ein GeVo bucht — die Betragsart ist Teil der
#: Buchung, nicht freier Text: Ein ``STO`` mit ``Todesfallleistung`` oder
#: ein ``ERH`` mit ``RKW`` ist keine andere Sicht, sondern ein Fehler.
#: Zwei Werte, wo zwei Produkte denselben GeVo buchen (KLV-Summe gegen
#: BU-Jahresrente) oder die Uebernahme eine Umbuchung mit der gelieferten
#: Bezugsgroesse bucht (``PEX`` mit ``VS``, gates.bestand_uebernehmen).
BETRAG_ART_JE_EREIGNIS: Dict[str, Tuple[str, ...]] = {
    "ZUG": ("VS", "BU_Jahresrente"),
    "MIG": ("dDK_uebernahme",),
    "ERH": ("VS_erhoehung",),
    "RED": ("VS_herabsetzung",),
    "PEX": ("VS_bfr", "VS"),
    "INV": ("BU_Jahresrente",),
    "REA": ("BU_Jahresrente",),
    "STO": ("RKW",),
    "TOD": ("Todesfallleistung", "BU_Jahresrente"),
    "ABL": ("Ablaufleistung", "BU_Jahresrente"),
}

#: Welchen Zustand ein GeVo herstellt (Historienzeile desselben Datums).
#: ERH, RED, ZUG und MIG stellen keinen her: Sie aendern Summe, Beitrag
#: oder Zugehoerigkeit, nicht den Zustand.
EREIGNIS_ZUSTAND: Dict[str, str] = {
    "PEX": "PEX", "STO": "STO", "TOD": "TOD", "ABL": "ABL",
    "INV": "BU", "REA": "POL",
}

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
    ("vs_bfr", "float64"),
    ("jahresbeitrag", "float64"),
    ("kern_version", "object"),
)

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
MERKMALE_NAMES: Tuple[str, ...] = tuple(n for n, _ in MERKMALE_SPALTEN)
VERANKERUNG_NAMES: Tuple[str, ...] = tuple(n for n, _ in VERANKERUNG_SPALTEN)
TAGESJOURNAL_NAMES: Tuple[str, ...] = tuple(n for n, _ in TAGESJOURNAL_SPALTEN)


def stamm_dtypes() -> Dict[str, str]:
    return dict(STAMM_SPALTEN)


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


def validate_ledger(
    stamm: Any, ledger: Any, historie: Any = None, scheiben: Any = None
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
      weil die Summen danach auf anderen Vertragsaltern lagen.
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
        negativ = (ledger["betrag"] < 0.0) & (ledger["ereignis"] != "MIG")
        if negativ.any():
            errors.append(
                f"ledger: betrag < 0 (police {_policen(negativ)}) — nur das "
                "Migrations-Residuum MIG traegt ein Vorzeichen"
            )
    if not (ledger["status_date"].dt.day == 1).all():
        errors.append("ledger: status_date nicht auf Monatsersten normalisiert")

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
        errors.extend(_ledger_scheiben_bindung(ledger, scheiben))
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
    * Schluessel (police_id, ereignis, status_date) eindeutig — eine
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
    schluessel_spalten = ["police_id", "ereignis", "status_date"]

    def _schluessel(df: Any) -> Any:
        import pandas as pd

        return pd.MultiIndex.from_arrays(
            [df["police_id"].astype("int64"), df["ereignis"].astype(str),
             pd.to_datetime(df["status_date"])],
            names=schluessel_spalten,
        )

    import pandas as pd

    grenze, beginn = pd.Timestamp(bis_tag), pd.Timestamp(ab_tag)
    sicht_schluessel = _schluessel(sicht)
    if sicht_schluessel.duplicated().any():
        return ["tagesjournal: Buchungssicht mit doppeltem Schluessel — der "
                "Ledger ist nicht eindeutig je (police_id, ereignis, status_date)"]
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


def _ledger_scheiben_bindung(ledger: Any, scheiben: Any) -> List[str]:
    """Jede ERH-Buchung genau eine Scheibe, jede Scheibe genau eine Buchung
    — ueber Police, Datum, Betrag und Erhoehungsjahr (T18-01)."""
    import pandas as _pd

    errors: List[str] = []
    if list(scheiben.columns) != list(SCHEIBEN_NAMES):
        return []  # validate_scheiben meldet den Spaltenfehler
    erh = ledger.loc[ledger["ereignis"] == "ERH",
                     ["police_id", "status_date", "vertragsjahr", "betrag"]]
    sch = scheiben[["police_id", "erhoehung_datum", "erhoehung_jahr", "sum_insured"]]
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
    if cols != list(ABSCHLUSS_NAMES):
        return [f"abschluss: Spalten {cols} != erwartet {list(ABSCHLUSS_NAMES)}"]
    if len(df) == 0:
        return ["abschluss: leer — kein festgeschriebener Stand"]
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
    zahlen = ("leistung", "deckungskapital", "rueckkaufswert", "vs_bfr", "jahresbeitrag")
    nichtendlich = [sp for sp in zahlen if _nichtendlich(df[sp])]
    if nichtendlich:
        errors.append(
            f"abschluss: nichtendliche Werte in {nichtendlich} — ein "
            "Bilanzwert ist endlich"
        )
    return errors


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
    # Reserve ein. Die Tarifwerk-Regel setzt sie auf null, weil die
    # Bezugsgroesse der Verwaltungskosten die GrundVS bleibt
    # (kern.rechenkern.erhoehungs_scheibe). Ein anderer Wert rechnet still
    # falsch: NaN laesst den Rueckkaufswert auf 0,00 fallen statt auf NaN,
    # ein negativer Wert erzeugt einen negativen Jahresbeitrag — beides
    # plausibel aussehende Zahlen, die niemandem auffallen.
    # NaN wird getrennt gemeldet, weil jeder Vergleich damit False ist;
    # das != 0.0 danach faengt Unendlich und jeden Fremdwert mit.
    if scheiben["gamma1"].isna().any():
        errors.append("scheiben: fehlende Werte (NaN) in gamma1")
    elif (scheiben["gamma1"] != 0.0).any():
        abweichend = sorted(
            set(scheiben.loc[scheiben["gamma1"] != 0.0, "police_id"])
        )[:5]
        errors.append(
            "scheiben: gamma1 != 0 (Tarifwerk-Regel: die Bezugsgroesse der "
            f"Verwaltungskosten bleibt die GrundVS), police {abweichend}"
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


def validate_verankerung(stamm: Any, verankerung: Any) -> List[str]:
    """Verankerungsattribute gegen den Stamm pruefen (leer = gueltig).

    Jede Zeile gehoert zu einem bekannten Vertrag, je Vertrag hoechstens
    eine Verankerung, und t_a liegt INNERHALB der Vertragslaufzeit — ein
    Rechenpunkt nach dem Ablauf verankert nichts. ``dk_ta`` muss belegt
    sein: Eine Verankerung ohne Wert ist keine.
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
    leer = verankerung["zustand_ta"].map(
        lambda z: not isinstance(z, str) or not z.strip()
    )
    if leer.any():
        errors.append("verankerung: zustand_ta leer")
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
