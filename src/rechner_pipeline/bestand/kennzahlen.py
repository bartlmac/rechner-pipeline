"""Portfolio-Kennzahlen für den Bestandsbericht (reine Berechnung, testbar).

Alle Funktionen sind deterministisch und frei von I/O und Darstellung; der
Renderer (:mod:`rechner_pipeline.bestand.report`) konsumiert nur die hier
berechneten Strukturen. Sortierungen sind überall explizit, damit das
Rendering byte-reproduzierbar bleibt.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

import pandas as pd

from rechner_pipeline.bestand.fuehrung import schnitt_am
from rechner_pipeline.models.bestand import AKTIVE_STATUS


def jahresraster(df: pd.DataFrame) -> List[_dt.date]:
    """Jährliche Stichtage (1.1.) vom ersten Vertragsbeginn bis zum letzten Ablauf."""
    von = int(df["insurance_start"].dt.year.min())
    bis = int(df["insurance_end"].dt.year.max())
    return [_dt.date(jahr, 1, 1) for jahr in range(von, bis + 1)]


def stichtags_kennzahlen(
    scheibe: pd.DataFrame, stichtag: _dt.date, leistung: str = "sum_insured"
) -> Dict[str, Any]:
    """Kennzahlen eines Auskunfts-Schnitts (leerer Schnitt ergibt Nullwerte).

    ``leistung`` waehlt die produktfuehrende Leistungsspalte
    (:data:`~rechner_pipeline.models.bestand.LEISTUNGSSPALTE`): bei einem
    BU-Bestand traegt ``sum_insured`` strukturell 0, die Bezugsgroesse ist
    dort ``bu_rente``. ``summe_vs`` fuehrt die gewaehlte Spalte.
    """
    n = int(len(scheibe))
    generationen = {
        str(name): int(anzahl)
        for name, anzahl in sorted(
            scheibe["tarif_generation"].value_counts().items()
        )
    } if n else {}
    return {
        "stichtag": stichtag.isoformat(),
        "vertraege": n,
        "summe_vs": float(scheibe[leistung].sum()) if n else 0.0,
        "mittel_alter": float(scheibe["age"].mean()) if n else 0.0,
        "mittel_restlaufzeit_jahre": float(scheibe["months_rem"].mean() / 12.0) if n else 0.0,
        "generationen": generationen,
    }


def verlauf(
    df: pd.DataFrame, stichtage: List[_dt.date], leistung: str = "sum_insured"
) -> List[Dict[str, Any]]:
    """Kennzahlen-Reihe über eine Stichtagsliste (Bestandsverlauf)."""
    return [stichtags_kennzahlen(schnitt_am(df, s), s, leistung) for s in stichtage]


def generationsnamen(df: pd.DataFrame) -> List[str]:
    """Alle Tarifgenerationen im Bestand, stabil sortiert."""
    return sorted(str(v) for v in df["tarif_generation"].unique())


# --------------------------------------------------------------------------- #
# Ereignis-Kennzahlen (Fortschreibung: Statushistorie + Ledger)
# --------------------------------------------------------------------------- #

#: Feste fachliche Reihenfolge der Ereignisse in Tabellen und Grafiken
#: (ZUG/ERH sind Zugangs-GeVos ohne Statuswechsel, daher vorangestellt).
EREIGNIS_REIHENFOLGE = ("ZUG", "ERH", "PEX", "INV", "REA", "STO", "TOD", "ABL")

#: Klartext je Ereignis-Code (Berichts-Beschriftung).
EREIGNIS_LABELS = {
    "ZUG": "Neuzugang",
    "ERH": "Dynamische Erhöhung",
    "PEX": "Beitragsfreistellung",
    "INV": "Invalidisierung",
    "REA": "Reaktivierung",
    "STO": "Storno",
    "TOD": "Tod",
    "ABL": "Ablauf",
}


def ledger_mit_bestandszugang(
    bestand: pd.DataFrame, ledger: pd.DataFrame
) -> pd.DataFrame:
    """Ledger, ergaenzt um die Zugaenge des Ausgangsbestands.

    Die Engine schreibt eine ZUG-Zeile nur fuer *simulierte* Neuzugaenge:
    die Vertraege des Ausgangsbestands existieren bei Simulationsbeginn
    bereits und bekommen keine. Fuer eine Ereignis-Sicht ueber den
    gesamten Berichtszeitraum ist das eine Luecke mit falscher Aussage —
    alle uebrigen Ereignisse erscheinen ueber den ganzen Zeitraum, der
    Zugang erst ab dem ersten Neugeschaeftsjahr, als haette der Bestand
    davor keinen Zugang gehabt. Das Bewegungskonto leitet den Zugang
    deshalb aus ``insurance_start`` ab; diese Funktion holt dieselbe
    Ableitung fuer Ereignis-Tabelle und -Grafik nach.

    Betrag und Betrags-Art sind die der jeweiligen Versicherungsart
    (Versicherungssumme bzw. Jahresrente), wie sie die Engine fuer ihre
    eigenen Zugaenge schreibt.
    """
    from rechner_pipeline.bestand.ereignisse import BU_BETRAG_ART

    schon_gebucht = (
        set(ledger.loc[ledger["ereignis"] == "ZUG", "police_id"])
        if len(ledger) else set()
    )
    fehlend = bestand[~bestand["police_id"].isin(schon_gebucht)]
    if len(fehlend) == 0:
        return ledger
    ist_bu = (
        fehlend["produkt"] == "bu"
        if "produkt" in fehlend.columns
        else pd.Series(False, index=fehlend.index)
    )
    zugaenge = pd.DataFrame(
        {
            "police_id": fehlend["police_id"].to_numpy(),
            "tarif_generation": fehlend["tarif_generation"].to_numpy(),
            "ereignis": "ZUG",
            "vertragsjahr": 0,
            "status_date": fehlend["insurance_start"].to_numpy(),
            "betrag_art": [
                BU_BETRAG_ART if b else "VS" for b in ist_bu
            ],
            "betrag": (
                fehlend["bu_rente"].where(ist_bu, fehlend["sum_insured"])
                if "bu_rente" in fehlend.columns
                else fehlend["sum_insured"]
            ).to_numpy(float),
        }
    )
    if len(ledger) == 0:
        return zugaenge.sort_values(
            ["status_date", "police_id"]
        ).reset_index(drop=True)
    return (
        pd.concat([ledger, zugaenge[ledger.columns]], ignore_index=True)
        .sort_values(["status_date", "police_id"])
        .reset_index(drop=True)
    )


def ereignis_summen(ledger: pd.DataFrame) -> List[Dict[str, Any]]:
    """Anzahl und Betragssumme je Ereignisart und Betrags-Art.

    Gruppiert wird nach (Ereignis, ``betrag_art``) — NICHT nur nach
    Ereignis: seit dem zweiten Produkt tragen dieselben Codes zweierlei
    Bezugsgrößen (KLV zahlt Todesfall-/Ablaufleistung in Versicherungssumme,
    BU führt die betroffene Jahresrente). Eine gemeinsame Summe wäre eine
    stille Vermischung nicht addierbarer Größen unter dem Label der ersten
    Zeile. Reihenfolge: fachliche Ereignisfolge, darin die Betrags-Arten
    alphabetisch (deterministisch); Ereignisse ohne Vorkommen entfallen.
    """
    summen: List[Dict[str, Any]] = []
    for code in EREIGNIS_REIHENFOLGE:
        rows = ledger[ledger["ereignis"] == code]
        if len(rows) == 0:
            continue
        for art in sorted(set(rows["betrag_art"])):
            teil = rows[rows["betrag_art"] == art]
            summen.append(
                {
                    "ereignis": code,
                    "label": EREIGNIS_LABELS[code],
                    "anzahl": int(len(teil)),
                    "betrag_art": str(art),
                    "summe_betrag": float(teil["betrag"].sum()),
                }
            )
    return summen


def ereignisse_je_jahr(ledger: pd.DataFrame) -> List[Dict[str, Any]]:
    """Ereigniszählung je Kalenderjahr (aufsteigend, lückenlos)."""
    if len(ledger) == 0:
        return []
    jahre = ledger["status_date"].dt.year
    von, bis = int(jahre.min()), int(jahre.max())
    reihe: List[Dict[str, Any]] = []
    for jahr in range(von, bis + 1):
        im_jahr = ledger[jahre == jahr]
        eintrag: Dict[str, Any] = {"jahr": jahr}
        for code in EREIGNIS_REIHENFOLGE:
            eintrag[code] = int((im_jahr["ereignis"] == code).sum())
        reihe.append(eintrag)
    return reihe


def _nur_produkt(bestand, historie, ledger, produkt: str):
    """Bestand, Historie und Ledger auf ein Produkt einschraenken."""
    if "produkt" not in bestand.columns:
        return bestand, historie, ledger
    gefiltert = bestand[bestand["produkt"] == produkt]
    if len(gefiltert) == len(bestand):
        return bestand, historie, ledger
    ids = set(gefiltert["police_id"])
    return (
        gefiltert.reset_index(drop=True),
        historie[historie["police_id"].isin(ids)].reset_index(drop=True),
        ledger[ledger["police_id"].isin(ids)].reset_index(drop=True),
    )


def bu_bewegungskonto(
    bestand: pd.DataFrame,
    historie: pd.DataFrame,
    ledger: pd.DataFrame,
    bis: Any = None,
) -> List[Dict[str, Any]]:
    """Bewegung des BU-Bestands je Kalenderjahr (Nachweisungs-Struktur).

    Gegenstück zu :func:`bewegungskonto` für das zweite Produkt. Die
    Nachweisung trennt hier nicht beitragspflichtig/beitragsfrei, sondern
    **Anwärter** (``anwaerter``, Zustand POL) und **Leistungsbezieher**
    (``rentner``, Zustand BU) — die Aufteilung, die auch die Bilanz
    kennt. Bezugsgröße ist in beiden Tracks die versicherte
    JAHRESRENTE (nicht die Versicherungssumme), Maße sind Stück und
    Jahresrente.

    GeVo-Mapping: Zugang aus den Versicherungsbeginnen (die POL-Basiszeile
    ist der Zugangs-Satz), Invalidisierung (``INV``) ist eine Umbuchung
    Anwärter -> Rentner, Reaktivierung (``REA``) die Rückbuchung,
    ``TOD``/``ABL`` sind Abgänge aus dem Track, in dem der Vertrag zuletzt
    stand. Weil die Jahresrente je Vertrag konstant ist (keine Scheiben,
    keine Leistungsdynamik im Beispielprodukt), gilt die Identität
    Anfang + Zugang - Abgang = Ende exakt — je Jahr, Track und Maß.

    ``bis`` ist wie bei :func:`bewegungskonto` der Fortschreibungs-Horizont:
    nur vollständig simulierte Jahre werden ausgewiesen.
    """
    from rechner_pipeline.bestand.fuehrung import journalsicht

    fremd = set(ledger["police_id"]) - set(bestand["police_id"])
    if fremd:
        raise ValueError(
            f"Ledger referenziert Policen ausserhalb des Bestands: "
            f"{sorted(fremd)[:5]} — bei Neuzugaengen den Gesamtbestand "
            "uebergeben (mit_zugaengen(stamm, zugaenge))"
        )
    bestand, historie, ledger = _nur_produkt(bestand, historie, ledger, "bu")
    if len(bestand) == 0:
        return []
    sicht = journalsicht(bestand, historie)
    renten = bestand.set_index("police_id")["bu_rente"]

    def stand_am(stichtag: _dt.date) -> Dict[str, Dict[str, float]]:
        scheibe = schnitt_am(sicht, stichtag)
        anwaerter = scheibe[scheibe["status_code"] == "POL"]
        rentner = scheibe[scheibe["status_code"] == "BU"]
        return {
            track: {
                "stueck": int(len(teil)),
                "summe": float(sum(renten.loc[p] for p in teil["police_id"])),
            }
            for track, teil in (("anwaerter", anwaerter), ("rentner", rentner))
        }

    von = int((bestand["insurance_start"] - pd.Timedelta(days=1)).dt.year.min())
    letzt = int(bestand["insurance_end"].dt.year.max())
    jahre = range(von, letzt + 1)
    if bis is not None:
        grenze = pd.Timestamp(bis)
        jahre = [j for j in jahre if pd.Timestamp(_dt.date(j + 1, 1, 1)) <= grenze]

    konto: List[Dict[str, Any]] = []
    for jahr in jahre:
        anfang = stand_am(_dt.date(jahr, 1, 1))
        ende = stand_am(_dt.date(jahr + 1, 1, 1))
        von_ts = pd.Timestamp(_dt.date(jahr, 1, 1))
        bis_ts = pd.Timestamp(_dt.date(jahr + 1, 1, 1))
        periode = ledger[
            (ledger["status_date"] > von_ts) & (ledger["status_date"] <= bis_ts)
        ]

        def posten(zeilen: pd.DataFrame) -> Dict[str, float]:
            return {
                "stueck": int(len(zeilen)),
                "summe": float(sum(renten.loc[p] for p in zeilen["police_id"])),
            }

        zug = bestand[
            (bestand["insurance_start"] > von_ts)
            & (bestand["insurance_start"] <= bis_ts)
        ]
        inv = periode[periode["ereignis"] == "INV"]
        rea = periode[periode["ereignis"] == "REA"]
        terminal = periode[periode["ereignis"].isin(("TOD", "ABL"))]
        # Der Track eines Abgangs ist der Zustand VOR dem Abgang: der
        # Ledger-Betrag ist genau dann die (endende) Jahresrente, wenn der
        # Vertrag im Leistungsbezug stand — Tod/Ablauf als Anwaerter zahlen 0.
        aus_bezug = terminal["betrag"] > 0.0
        zeile: Dict[str, Any] = {
            "jahr": int(jahr),
            "anwaerter": {
                "anfang": anfang["anwaerter"],
                "zugang_neuzugang": posten(zug),
                "zugang_reaktivierung": posten(rea),
                "abgang_tod": posten(terminal[(terminal["ereignis"] == "TOD") & ~aus_bezug]),
                "abgang_ablauf": posten(terminal[(terminal["ereignis"] == "ABL") & ~aus_bezug]),
                "umbuchung_leistungsbezug": posten(inv),
                "ende": ende["anwaerter"],
            },
            "rentner": {
                "anfang": anfang["rentner"],
                "zugang_invalidisierung": posten(inv),
                "abgang_reaktivierung": posten(rea),
                "abgang_tod": posten(terminal[(terminal["ereignis"] == "TOD") & aus_bezug]),
                "abgang_ablauf": posten(terminal[(terminal["ereignis"] == "ABL") & aus_bezug]),
                "ende": ende["rentner"],
            },
        }

        def identitaet(track: Dict[str, Dict[str, float]], zu: List[str], ab: List[str]):
            ok = {}
            for mass in ("stueck", "summe"):
                bewegungen = [track[p][mass] for p in zu] + [-track[p][mass] for p in ab]
                soll = track["anfang"][mass] + sum(bewegungen)
                brutto = (
                    abs(track["anfang"][mass]) + abs(track["ende"][mass])
                    + sum(abs(x) for x in bewegungen)
                )
                toleranz = 0.0 if mass == "stueck" else max(1e-6, 1e-9 * brutto)
                ok[mass] = abs(soll - track["ende"][mass]) <= toleranz
            return ok

        zeile["identitaet"] = {
            "anwaerter": identitaet(
                zeile["anwaerter"],
                ["zugang_neuzugang", "zugang_reaktivierung"],
                ["abgang_tod", "abgang_ablauf", "umbuchung_leistungsbezug"],
            ),
            "rentner": identitaet(
                zeile["rentner"],
                ["zugang_invalidisierung"],
                ["abgang_reaktivierung", "abgang_tod", "abgang_ablauf"],
            ),
        }
        konto.append(zeile)
    return konto


def bewegungskonto(
    bestand: pd.DataFrame,
    historie: pd.DataFrame,
    ledger: pd.DataFrame,
    scheiben: Any = None,
    bis: Any = None,
) -> List[Dict[str, Any]]:
    """Bestandsbewegung der KAPITALVERSICHERUNG je Kalenderjahr.

    Struktur der BaFin-Nachweisung; seit dem zweiten Produkt ist dies die
    KLV-Nachweisung (Bezugsgröße Versicherungssumme) — BU läuft über
    :func:`bu_bewegungskonto` mit der Jahresrente, weil beide Größen nicht
    addierbar sind. Ein Bestand ohne KLV-Verträge liefert hier eine leere
    Liste (nicht etwa einen Fehler).

    Beschluss 2026-08-13: Anfangsbestand + Zugang - Abgang = Endbestand,
    getrennt nach beitragspflichtig (``bpfl``) und beitragsfrei (``bfr``),
    jeweils in Stück und Versicherungssumme. GeVo-Mapping: ZUG/ERH = Zugang
    (Erhöhungen nur Summe, kein Stück), STO/TOD/ABL = Abgang, PEX =
    Umbuchung (Abgang bpfl mit der Gesamt-VS, Zugang bfr mit der
    beitragsfreien Summe). Abgangs-Summen sind VERSICHERUNGSSUMMEN
    (inkl. Erhöhungsscheiben) bzw. beitragsfreie Summen — nicht die
    Auszahlungsbeträge des Ledgers. Dadurch gelten die Identitäten exakt
    und werden je Jahr, Track und Maß mitgeliefert (``identitaet``) —
    das Gate P-B1 prüft sie hart (Stück exakt, Summen mit einer relativ zum
    Bruttovolumen skalierten Toleranz gegen Float-Akkumulationsrauschen).
    Inkonsistente Eingaben (Ledger-Policen außerhalb des Bestands, doppelte
    PEX-Zeilen, PEX-Status ohne PEX-Ledger-Zeile) sind ein sofortiger
    ``ValueError`` — sie wären sonst stille Falschzählungen.

    ``bestand`` ist der GESAMTbestand (inkl. Neuzugängen, vgl.
    ``mit_zugaengen``); Periode eines Jahres J ist ``(1.1.J, 1.1.J+1]``
    (konsistent zur Auskunfts-Konvention ``status_date <= stichtag``).

    ``bis`` ist der Fortschreibungs-Horizont (dasselbe Datum wie beim
    ``fortschreiben``-Lauf): nur Jahre mit ``1.1.J+1 <= bis`` sind
    vollständig simuliert und werden ausgewiesen. Ohne ``bis`` läuft das
    Konto über alle Vertragsjahre — dann muss der Aufrufer sicherstellen,
    dass der Horizont alle Vertragsenden abdeckt, sonst fehlen hinter dem
    Horizont die Abläufe und die Identität ist scheinbar verletzt
    (der Auskunfts-Schnitt filtert hart auf ``insurance_end > stichtag``).
    """
    from rechner_pipeline.bestand.fuehrung import journalsicht

    fremd = set(ledger["police_id"]) - set(bestand["police_id"])
    if fremd:
        raise ValueError(
            f"Ledger referenziert Policen ausserhalb des Bestands: "
            f"{sorted(fremd)[:5]} — bei Neuzugaengen den Gesamtbestand "
            "uebergeben (mit_zugaengen(stamm, zugaenge))"
        )
    # Gemischte Bestaende: dieses Konto fuehrt die KLV-Nachweisung
    # (Bezugsgroesse Versicherungssumme); BU laeuft ueber
    # :func:`bu_bewegungskonto` mit der Jahresrente.
    bestand, historie, ledger = _nur_produkt(bestand, historie, ledger, "klv")
    if len(bestand) == 0:
        return []   # reiner BU-Bestand: die KLV-Nachweisung ist leer
    sicht = journalsicht(bestand, historie)
    stamm_vs = bestand.set_index("police_id")["sum_insured"]

    pex_zeilen = ledger[ledger["ereignis"] == "PEX"].set_index("police_id")
    if pex_zeilen.index.has_duplicates:
        doppelt = sorted(pex_zeilen.index[pex_zeilen.index.duplicated()])[:5]
        raise ValueError(
            f"Ledger enthaelt mehrere PEX-Zeilen je Police: {doppelt} — "
            "eine Police kann nur einmal beitragsfrei gestellt werden"
        )
    pex_summen = pex_zeilen["betrag"]
    pex_status = set(historie.loc[historie["status_code"] == "PEX", "police_id"])
    ohne_ledger = sorted(pex_status - set(pex_summen.index))[:5]
    if ohne_ledger:
        raise ValueError(
            f"Historie hat PEX-Status ohne PEX-Ledger-Zeile: {ohne_ledger} — "
            "Historie und Ledger stammen nicht aus demselben "
            "fortschreiben-Lauf"
        )

    scheiben_je_police: Dict[int, List] = {}
    if scheiben is not None and len(scheiben):
        for s in scheiben.to_dict("records"):
            scheiben_je_police.setdefault(int(s["police_id"]), []).append(
                (s["erhoehung_datum"], float(s["sum_insured"]))
            )

    def vs_ges(pid: int, stichtag: pd.Timestamp) -> float:
        summe = float(stamm_vs.loc[pid])
        for datum, betrag in scheiben_je_police.get(int(pid), ()):
            if datum <= stichtag:
                summe += betrag
        return summe

    def stand_am(stichtag: _dt.date) -> Dict[str, Dict[str, float]]:
        ts = pd.Timestamp(stichtag)
        scheibe = schnitt_am(sicht, stichtag)
        bpfl = scheibe[scheibe["status_code"] == "POL"]
        bfr = scheibe[scheibe["status_code"] == "PEX"]
        return {
            "bpfl": {
                "stueck": int(len(bpfl)),
                "summe": float(sum(vs_ges(p, ts) for p in bpfl["police_id"])),
            },
            "bfr": {
                "stueck": int(len(bfr)),
                "summe": float(sum(pex_summen.loc[p] for p in bfr["police_id"])),
            },
        }

    # Beginn genau am 1.1.J gehoert per Periodenkonvention (1.1.J-1, 1.1.J]
    # zur Periode J-1 — der Rasterstart rechnet deshalb einen Tag zurueck,
    # sonst erschiene ein 1.1.-Zugang des fruehesten Jahres nie als Zugang.
    von = int((bestand["insurance_start"] - pd.Timedelta(days=1)).dt.year.min())
    letzt = int(bestand["insurance_end"].dt.year.max())
    jahre = range(von, letzt + 1)
    if bis is not None:
        grenze = pd.Timestamp(bis)
        jahre = [
            j for j in jahre
            if pd.Timestamp(_dt.date(j + 1, 1, 1)) <= grenze
        ]

    konto: List[Dict[str, Any]] = []
    for jahr in jahre:
        anfang = stand_am(_dt.date(jahr, 1, 1))
        ende = stand_am(_dt.date(jahr + 1, 1, 1))
        von_ts = pd.Timestamp(_dt.date(jahr, 1, 1))
        bis_ts = pd.Timestamp(_dt.date(jahr + 1, 1, 1))
        periode = ledger[
            (ledger["status_date"] > von_ts) & (ledger["status_date"] <= bis_ts)
        ]

        def posten(auswahl: pd.DataFrame, summen: List[float]) -> Dict[str, float]:
            return {"stueck": int(len(auswahl)), "summe": float(sum(summen))}

        # Zugang aus dem BESTAND selbst (die POL-Basiszeile ist der
        # Zugangs-Satz — deckt Batch-Historie UND simulierten Neuzugang
        # einheitlich ab; die ZUG-Ledger-Zeilen sind eine Teilmenge davon):
        zug = bestand[
            (bestand["insurance_start"] > von_ts)
            & (bestand["insurance_start"] <= bis_ts)
        ]
        erh = periode[periode["ereignis"] == "ERH"]
        pex = periode[periode["ereignis"] == "PEX"]
        sto = periode[periode["ereignis"] == "STO"]
        terminal = periode[periode["ereignis"].isin(("TOD", "ABL"))]
        war_bfr = terminal["police_id"].isin(pex_summen.index)
        tod_bpfl = terminal[(terminal["ereignis"] == "TOD") & ~war_bfr]
        tod_bfr = terminal[(terminal["ereignis"] == "TOD") & war_bfr]
        abl_bpfl = terminal[(terminal["ereignis"] == "ABL") & ~war_bfr]
        abl_bfr = terminal[(terminal["ereignis"] == "ABL") & war_bfr]

        def vs_liste(zeilen: pd.DataFrame) -> List[float]:
            return [
                vs_ges(p, d)
                for p, d in zip(zeilen["police_id"], zeilen["status_date"])
            ]

        def bfr_liste(zeilen: pd.DataFrame) -> List[float]:
            return [float(pex_summen.loc[p]) for p in zeilen["police_id"]]

        zeile: Dict[str, Any] = {
            "jahr": int(jahr),
            "bpfl": {
                "anfang": anfang["bpfl"],
                "zugang_neuzugang": posten(zug, list(zug["sum_insured"])),
                "zugang_erhoehung": {"stueck": 0, "summe": float(erh["betrag"].sum())},
                "abgang_storno": posten(sto, vs_liste(sto)),
                "abgang_tod": posten(tod_bpfl, vs_liste(tod_bpfl)),
                "abgang_ablauf": posten(abl_bpfl, vs_liste(abl_bpfl)),
                "umbuchung_beitragsfrei": posten(pex, vs_liste(pex)),
                "ende": ende["bpfl"],
            },
            "bfr": {
                "anfang": anfang["bfr"],
                "zugang_umbuchung": posten(pex, list(pex["betrag"])),
                "abgang_tod": posten(tod_bfr, bfr_liste(tod_bfr)),
                "abgang_ablauf": posten(abl_bfr, bfr_liste(abl_bfr)),
                "ende": ende["bfr"],
            },
        }

        def identitaet(track: Dict[str, Dict[str, float]], zu: List[str], ab: List[str]):
            ok = {}
            for mass in ("stueck", "summe"):
                bewegungen = [track[p][mass] for p in zu] + [-track[p][mass] for p in ab]
                soll = track["anfang"][mass] + sum(bewegungen)
                # Stueck exakt; Summen mit Toleranz relativ zum Bruttovolumen:
                # Anfang/Ende summieren dieselben Gleitkommazahlen in anderer
                # Reihenfolge als die Zu-/Abgaenge, der Akkumulationsfehler
                # waechst mit der Bestandssumme (1e-9 relativ liegt Groessen-
                # ordnungen ueber dem Float-Rauschen und unter jeder realen VS).
                brutto = (
                    abs(track["anfang"][mass]) + abs(track["ende"][mass])
                    + sum(abs(x) for x in bewegungen)
                )
                toleranz = 0.0 if mass == "stueck" else max(1e-6, 1e-9 * brutto)
                ok[mass] = abs(soll - track["ende"][mass]) <= toleranz
            return ok

        zeile["identitaet"] = {
            "bpfl": identitaet(
                zeile["bpfl"],
                ["zugang_neuzugang", "zugang_erhoehung"],
                ["abgang_storno", "abgang_tod", "abgang_ablauf", "umbuchung_beitragsfrei"],
            ),
            "bfr": identitaet(
                zeile["bfr"], ["zugang_umbuchung"], ["abgang_tod", "abgang_ablauf"]
            ),
        }
        konto.append(zeile)
    return konto


def status_verlauf(
    sicht: pd.DataFrame, stichtage: List[_dt.date]
) -> List[Dict[str, Any]]:
    """In-force-Bestand je Stichtag, aufgeteilt nach Status.

    Gezählt werden ALLE in-force-Status (POL beitragspflichtig, PEX
    beitragsfrei, BU im Leistungsbezug) — die Summe der Zähler ist damit
    immer die Zahl der Verträge im Auskunfts-Schnitt. Ein fehlender Zähler
    hätte Leistungsbezieher still unterschlagen.

    ``sicht`` ist die Journalsicht aus
    :func:`rechner_pipeline.bestand.fuehrung.journalsicht`; der
    Auskunfts-Schnitt wählt je Police den jüngsten in-force-Status.
    """
    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        scheibe = schnitt_am(sicht, stichtag)
        counts = scheibe["status_code"].value_counts()
        eintrag: Dict[str, Any] = {"stichtag": stichtag.isoformat()}
        for status in AKTIVE_STATUS:
            eintrag[status] = int(counts.get(status, 0))
        reihe.append(eintrag)
    return reihe
