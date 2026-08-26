"""Bestandsfuehrung: gefuehrter Zustand und Auskunft aus dem Journal (ADR-011).

Der Stammsatz eines Vertrags traegt seinen AKTUELLEN Zustand (Status und
seit wann); das Journal — Statushistorie und Geschaeftsvorfall-Ledger —
ist die vollstaendige, nur-anfuegbare Aufzeichnung, aus der sich der
Bestand zu jedem frueheren Tag rekonstruieren laesst. Dieses Modul ist die
eine Stelle, an der beides zusammenlaeuft:

* :func:`fuehre_fort` setzt den Stammzustand aus dem Journal — der
  gemeinsame Trichter fuer die Simulation heute und den Migrationszugang
  morgen. Zwei Schreibwege auf denselben Bestand sind der Mechanismus, aus
  dem Drift entsteht.
* :func:`bestand_am` ist die Auskunft: der gefuehrte Zustand am Tag X,
  rekonstruiert aus dem Journal, mit den abgeleiteten Stichtagsgroessen
  (Alter, verstrichene/restliche Monate). Auskunft DARF das Journal lesen —
  das ist ihr Zweck.

Die Gegenregel steht in der Bewertung: Kein Bewertungspfad liest das
Journal. Die Bewertung rechnet aus dem Zustand (dieselbe
Historienfreiheit, die das Fachkonzept "Konstruktive Neuberechnung" in
Kap. 5.5 vom Rechenkern verlangt — eine Ebene hoeher angewendet).

Der Ursprungszustand ist Konvention, kein Datensatz: Jede Police beginnt
mit (status_id 1, POL, Versicherungsbeginn). Die Auskunft synthetisiert
diese Zeile aus den Vertragsdaten, statt sie dem Stamm zu glauben — damit
funktioniert sie unabhaengig davon, ob ihr ein Basisbestand oder ein
gefuehrter Bestand uebergeben wird.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt

import pandas as pd

from rechner_pipeline.models.bestand import (
    AKTIVE_STATUS,
    BASIS_STATUS,
    STAMM_NAMES,
    ZEITSCHEIBEN_NAMES,
)


class FuehrungsError(ValueError):
    """Stamm und Journal passen nicht zusammen — fail-fast."""


# --------------------------------------------------------------------------- #
# Kalenderhelfer (Monatserster-Konvention des Bestands)
# --------------------------------------------------------------------------- #


def months_between(d1: _dt.date, d2: _dt.date) -> int:
    """Full months elapsed from ``d1`` to ``d2`` (negative if d2 < d1)."""
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return m


def derived_age(entry_age: int, months_exp: int) -> int:
    """Attained age with the reference's 6-month rounding.

    ``round((months_exp + 1) / 12 - eps)``: five completed months round down,
    six completed months round up (the +1/eps construction puts the boundary
    between five and six months, mirroring the reference implementation).
    """
    return int(entry_age + round((months_exp + 1) / 12 - 1e-12))


# --------------------------------------------------------------------------- #
# Fuehrung: Stammzustand aus dem Journal
# --------------------------------------------------------------------------- #


def fuehre_fort(stamm: pd.DataFrame, historie: pd.DataFrame) -> pd.DataFrame:
    """Den gefuehrten Bestand herstellen: Stammzustand = juengster Journalstand.

    Nimmt einen Bestand (Basiszeilen, ggf. inkl. Neuzugaenge) und das
    Status-Journal und setzt je Police die Statusspalten auf die juengste
    Journalzeile; Policen ohne Journalzeilen behalten ihren Ursprungssatz.
    Alle uebrigen Spalten bleiben byte-identisch.
    """
    unbekannt = set(historie["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        raise FuehrungsError(
            f"journal: police_id unbekannt: {sorted(unbekannt)[:5]} — bei "
            "Neuzugaengen den Gesamtbestand uebergeben "
            "(mit_zugaengen(stamm, zugaenge))"
        )
    gefuehrt = stamm.copy().reset_index(drop=True)
    if len(historie) == 0:
        return gefuehrt[list(STAMM_NAMES)]
    juengste = (
        historie.sort_values(["police_id", "status_id"], kind="stable")
        .groupby("police_id", sort=False)
        .tail(1)
        .set_index("police_id")[["status_id", "status_code", "status_date"]]
    )
    index = gefuehrt["police_id"]
    treffer = index.isin(juengste.index)
    for spalte in ("status_id", "status_code", "status_date"):
        werte = juengste[spalte].reindex(index[treffer]).to_numpy()
        gefuehrt.loc[treffer, spalte] = werte
    gefuehrt["status_id"] = gefuehrt["status_id"].astype("int64")
    return gefuehrt[list(STAMM_NAMES)]


# --------------------------------------------------------------------------- #
# Auskunft: Bestand am Tag X aus dem Journal
# --------------------------------------------------------------------------- #


def journalsicht(stamm: pd.DataFrame, historie: pd.DataFrame) -> pd.DataFrame:
    """Eine Zeile je Zustandsepoche: synthetisierter Ursprung + Journalzeilen.

    Der Ursprung wird aus den Vertragsdaten synthetisiert (POL am
    Versicherungsbeginn) und NICHT dem Stamm entnommen — der Stamm traegt
    im gefuehrten Bestand bereits den aktuellen Zustand.
    """
    unbekannt = set(historie["police_id"]) - set(stamm["police_id"])
    if unbekannt:
        raise FuehrungsError(
            f"journal: police_id unbekannt: {sorted(unbekannt)[:5]} — bei "
            "Neuzugaengen den Gesamtbestand uebergeben "
            "(mit_zugaengen(stamm, zugaenge))"
        )
    ursprung = stamm.copy()
    ursprung["status_id"] = pd.Series(1, index=ursprung.index, dtype="int64")
    ursprung["status_code"] = BASIS_STATUS[0]
    ursprung["status_date"] = ursprung["insurance_start"]
    if len(historie) == 0:
        return ursprung.reset_index(drop=True)[list(STAMM_NAMES)]
    stammdaten = ursprung.drop(columns=["status_id", "status_code", "status_date"])
    folge = historie.merge(stammdaten, on="police_id", how="left", validate="m:1")
    beide = pd.concat([ursprung, folge[list(STAMM_NAMES)]], ignore_index=True)
    return (
        beide.sort_values(["police_id", "status_id"], kind="stable")
        .reset_index(drop=True)[list(STAMM_NAMES)]
    )


def bestand_am(
    stamm: pd.DataFrame, historie: pd.DataFrame, stichtag: _dt.date
) -> pd.DataFrame:
    """Auskunft: der in-force-Bestand am ``stichtag`` mit Stichtagsgroessen.

    Komposition aus :func:`journalsicht` und :func:`schnitt_am` — wer viele
    Stichtage hintereinander braucht, baut die Sicht einmal und schneidet.
    """
    return schnitt_am(journalsicht(stamm, historie), stichtag)


def schnitt_am(sicht: pd.DataFrame, stichtag: _dt.date) -> pd.DataFrame:
    """Auskunfts-Schnitt: in-force-Zustand am ``stichtag`` aus der Journalsicht.

    Auswahl: Vertrag hat begonnen (``insurance_start <= stichtag``), ist
    nicht abgelaufen (``insurance_end > stichtag``), je Police zaehlt der
    juengste am Stichtag bekannte Zustand (``status_date <= stichtag``;
    bei Datums-Gleichstand gewinnt die hoehere ``status_id``), und dieser
    Zustand ist in-force (POL/PEX/BU). Ableitung: ``age`` (6-Monats-
    Rundung), ``months_exp``, ``months_rem`` und die ``stichtag``-Spalte.
    Invariante je Stichtag: ``months_exp + months_rem == 12 * duration``.
    """
    ts = pd.Timestamp(stichtag)
    aktiv = sicht[
        (sicht["insurance_start"] <= ts)
        & (sicht["insurance_end"] > ts)
        & (sicht["status_date"] <= ts)
    ]
    aktiv = (
        aktiv.sort_values(["police_id", "status_date"], kind="stable")
        .groupby("police_id", as_index=False, sort=False)
        .tail(1)
        .reset_index(drop=True)
    )
    aktiv = aktiv[aktiv["status_code"].isin(AKTIVE_STATUS)].reset_index(drop=True)

    months_exp = [
        months_between(s.date(), stichtag) for s in aktiv["insurance_start"]
    ]
    # Restmonate als Ceiling: volle Monate + 1 nur bei angebrochenem Monat
    # (Tag-genau; bei Stichtag auf dem Monatsersten — der Datums-Konvention
    # des Moduls — gibt es keinen Teilmonat).
    months_rem = [
        months_between(stichtag, e.date())
        + (0 if e.date().day == stichtag.day else 1)
        for e in aktiv["insurance_end"]
    ]
    age = [
        derived_age(int(a), m) for a, m in zip(aktiv["entry_age"], months_exp)
    ]

    out = aktiv.copy()
    out["stichtag"] = ts
    out["age"] = pd.Series(age, dtype="int64")
    out["months_exp"] = pd.Series(months_exp, dtype="int64")
    out["months_rem"] = pd.Series(months_rem, dtype="int64")
    return out[list(STAMM_NAMES) + list(ZEITSCHEIBEN_NAMES)]
