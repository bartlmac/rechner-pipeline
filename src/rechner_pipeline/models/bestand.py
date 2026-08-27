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
    ("ereignis", "object"),          # PEX|STO|TOD|ABL|ERH|ZUG|INV|REA
    ("vertragsjahr", "int64"),       # booked anniversary (completed years; ZUG: 0)
    ("status_date", "datetime64[ns]"),
    # Bezugsgroesse des Betrags — je Produkt verschieden: KLV fuehrt
    # Versicherungssummen/Rueckkaufswerte, BU die betroffene Jahresrente.
    ("betrag_art", "object"),        # RKW | VS_bfr | Todesfallleistung | Ablaufleistung | VS_erhoehung | VS (ZUG) | BU_Jahresrente
    ("betrag", "float64"),
)

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

STAMM_NAMES: Tuple[str, ...] = tuple(n for n, _ in STAMM_SPALTEN)
ZEITSCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in ZEITSCHEIBEN_SPALTEN)
STATUS_HISTORIE_NAMES: Tuple[str, ...] = tuple(n for n, _ in STATUS_HISTORIE_SPALTEN)
LEDGER_NAMES: Tuple[str, ...] = tuple(n for n, _ in LEDGER_SPALTEN)
SCHEIBEN_NAMES: Tuple[str, ...] = tuple(n for n, _ in SCHEIBEN_SPALTEN)
ABSCHLUSS_NAMES: Tuple[str, ...] = tuple(n for n, _ in ABSCHLUSS_SPALTEN)


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
    # Journal prueft validate_stamm_journal (Gate B1 erzwingt sie).
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
    # Monatserster-Konvention (deterministische Jahres-/Monatsarithmetik).
    for col in (
        "status_date",
        "date_of_birth",
        "insurance_start",
        "insurance_end",
        "payment_end",
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
    # KeyError geben — sonst endet Gate B1 als internal_error statt als
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
