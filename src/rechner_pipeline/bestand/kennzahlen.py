"""Portfolio-Kennzahlen für den Bestandsbericht (reine Berechnung, testbar).

Alle Funktionen sind deterministisch und frei von I/O und Darstellung; der
Renderer (:mod:`rechner_pipeline.bestand.report`) konsumiert nur die hier
berechneten Strukturen. Sortierungen sind überall explizit, damit das
Rendering byte-reproduzierbar bleibt.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List

import pandas as pd

from rechner_pipeline.bestand.zeitscheibe import zeitscheibe


def jahresraster(df: pd.DataFrame) -> List[_dt.date]:
    """Jährliche Stichtage (1.1.) vom ersten Vertragsbeginn bis zum letzten Ablauf."""
    von = int(df["insurance_start"].dt.year.min())
    bis = int(df["insurance_end"].dt.year.max())
    return [_dt.date(jahr, 1, 1) for jahr in range(von, bis + 1)]


def stichtags_kennzahlen(scheibe: pd.DataFrame, stichtag: _dt.date) -> Dict[str, Any]:
    """Kennzahlen einer Zeitscheibe (leere Scheibe ergibt Nullwerte)."""
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
        "summe_vs": float(scheibe["sum_insured"].sum()) if n else 0.0,
        "mittel_alter": float(scheibe["age"].mean()) if n else 0.0,
        "mittel_restlaufzeit_jahre": float(scheibe["months_rem"].mean() / 12.0) if n else 0.0,
        "generationen": generationen,
    }


def verlauf(df: pd.DataFrame, stichtage: List[_dt.date]) -> List[Dict[str, Any]]:
    """Kennzahlen-Reihe über eine Stichtagsliste (Bestandsverlauf)."""
    return [stichtags_kennzahlen(zeitscheibe(df, s), s) for s in stichtage]


def generationsnamen(df: pd.DataFrame) -> List[str]:
    """Alle Tarifgenerationen im Bestand, stabil sortiert."""
    return sorted(str(v) for v in df["tarif_generation"].unique())


# --------------------------------------------------------------------------- #
# Ereignis-Kennzahlen (Fortschreibung: Statushistorie + Ledger)
# --------------------------------------------------------------------------- #

#: Feste fachliche Reihenfolge der Ereignisse in Tabellen und Grafiken
#: (ZUG/ERH sind Zugangs-GeVos ohne Statuswechsel, daher vorangestellt).
EREIGNIS_REIHENFOLGE = ("ZUG", "ERH", "PEX", "STO", "TOD", "ABL")

#: Klartext je Ereignis-Code (Berichts-Beschriftung).
EREIGNIS_LABELS = {
    "ZUG": "Neuzugang",
    "ERH": "Dynamische Erhöhung",
    "PEX": "Beitragsfreistellung",
    "STO": "Storno",
    "TOD": "Tod",
    "ABL": "Ablauf",
}


def ereignis_summen(ledger: pd.DataFrame) -> List[Dict[str, Any]]:
    """Anzahl und Betragssumme je Ereignisart (feste Reihenfolge).

    ``betrag_art`` ist je Ereignis einheitlich (RKW, VS_bfr, ...); Ereignisse
    ohne Vorkommen werden ausgelassen.
    """
    summen: List[Dict[str, Any]] = []
    for code in EREIGNIS_REIHENFOLGE:
        rows = ledger[ledger["ereignis"] == code]
        if len(rows) == 0:
            continue
        summen.append(
            {
                "ereignis": code,
                "label": EREIGNIS_LABELS[code],
                "anzahl": int(len(rows)),
                "betrag_art": str(rows["betrag_art"].iloc[0]),
                "summe_betrag": float(rows["betrag"].sum()),
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


def bewegungskonto(
    bestand: pd.DataFrame,
    historie: pd.DataFrame,
    ledger: pd.DataFrame,
    scheiben: Any = None,
    jahre: Any = None,
    bis: Any = None,
) -> List[Dict[str, Any]]:
    """Bestandsbewegung je Kalenderjahr in der Struktur der BaFin-Nachweisung.

    Beschluss 2026-08-13: Anfangsbestand + Zugang - Abgang = Endbestand,
    getrennt nach beitragspflichtig (``bpfl``) und beitragsfrei (``bfr``),
    jeweils in Stück und Versicherungssumme. GeVo-Mapping: ZUG/ERH = Zugang
    (Erhöhungen nur Summe, kein Stück), STO/TOD/ABL = Abgang, PEX =
    Umbuchung (Abgang bpfl mit der Gesamt-VS, Zugang bfr mit der
    beitragsfreien Summe). Abgangs-Summen sind VERSICHERUNGSSUMMEN
    (inkl. Erhöhungsscheiben) bzw. beitragsfreie Summen — nicht die
    Auszahlungsbeträge des Ledgers. Dadurch gelten die Identitäten exakt
    und werden je Jahr, Track und Maß mitgeliefert (``identitaet``) —
    das Gate B1 prüft sie hart.

    ``bestand`` ist der GESAMTbestand (inkl. Neuzugängen, vgl.
    ``mit_zugaengen``); Periode eines Jahres J ist ``(1.1.J, 1.1.J+1]``
    (konsistent zur Zeitscheiben-Konvention ``status_date <= stichtag``).

    ``bis`` ist der Fortschreibungs-Horizont (dasselbe Datum wie beim
    ``fortschreiben``-Lauf): nur Jahre mit ``1.1.J+1 <= bis`` sind
    vollständig simuliert und werden ausgewiesen. Ohne ``bis`` läuft das
    Konto über alle Vertragsjahre — dann muss der Aufrufer sicherstellen,
    dass der Horizont alle Vertragsenden abdeckt, sonst fehlen hinter dem
    Horizont die Abläufe und die Identität ist scheinbar verletzt
    (Zeitscheibe filtert hart auf ``insurance_end > stichtag``).
    """
    from rechner_pipeline.bestand.ereignisse import bestand_mit_historie
    from rechner_pipeline.bestand.zeitscheibe import zeitscheibe as _zeitscheibe

    sicht = bestand_mit_historie(bestand, historie)
    stamm_vs = bestand.set_index("police_id")["sum_insured"]

    pex_zeilen = ledger[ledger["ereignis"] == "PEX"].set_index("police_id")
    pex_summen = pex_zeilen["betrag"]

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

    def bestand_am(stichtag: _dt.date) -> Dict[str, Dict[str, float]]:
        ts = pd.Timestamp(stichtag)
        scheibe = _zeitscheibe(sicht, stichtag)
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

    if jahre is None:
        von = int(bestand["insurance_start"].dt.year.min())
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
        anfang = bestand_am(_dt.date(jahr, 1, 1))
        ende = bestand_am(_dt.date(jahr + 1, 1, 1))
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
            for mass, toleranz in (("stueck", 0.0), ("summe", 1e-6)):
                soll = (
                    track["anfang"][mass]
                    + sum(track[p][mass] for p in zu)
                    - sum(track[p][mass] for p in ab)
                )
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
    """In-force-Bestand je Stichtag, aufgeteilt nach Status (POL/PEX).

    ``sicht`` ist die Mehrzeilen-Sicht aus
    :func:`rechner_pipeline.bestand.ereignisse.bestand_mit_historie`; die
    Zeitscheibe wählt je Police den jüngsten in-force-Status.
    """
    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        scheibe = zeitscheibe(sicht, stichtag)
        counts = scheibe["status_code"].value_counts()
        reihe.append(
            {
                "stichtag": stichtag.isoformat(),
                "POL": int(counts.get("POL", 0)),
                "PEX": int(counts.get("PEX", 0)),
            }
        )
    return reihe
