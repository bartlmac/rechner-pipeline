"""Aktuarielle Auswertungen der Fortschreibung — Werte aus dem stabilen Kern.

Per reporting date and contract this module pulls the calculated quantities
from the stable kernel in-process (:func:`Rechenkern.zustand_am` — the
decided standard path) and aggregates them into a per-Stichtag series for
the Bestandsbericht. It computes NOTHING actuarial of its own:

* Deckungskapital: ``kDRx_bpfl`` for premium-paying contracts; after a
  Beitragsfreistellung the paid-up reserve
  :func:`Rechenkern.reserve_beitragsfrei` (``VS_bfr(a0) * kVx_bfr(a)``).
* Rueckkaufswert: the row's ``RKW`` — premium-paying track only (the sheet
  defines no surrender rule for paid-up contracts, Stufe 1).
* Beitragsfreie Summe: ``VS_bfr`` fixed at the PEX year.

Efficiency follows the documented reuse convention: one
:class:`~rechner_pipeline.kern.Rechenkern` per contract, indexed per
Stichtag (its Verlaufszeilen are cached per instance).
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.ereignisse import bestand_mit_historie, vertrags_rkw
from rechner_pipeline.bestand.zeitscheibe import months_between, zeitscheibe
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import bu_model_point_kwargs, model_point_kwargs


def vertragswerte(
    kern: Rechenkern, months_exp: int, pex_jahr: Optional[int] = None
) -> Dict[str, Any]:
    """Aktuarielle Werte eines Vertrags am Stichtag (``months_exp`` volle Monate).

    ``pex_jahr`` ist das Vertragsjahr der Beitragsfreistellung (None =
    beitragspflichtig). Rueckkaufswert nur auf dem beitragspflichtigen Track;
    fuer beitragsfreie Vertraege ist er 0.0 (im Blatt nicht definiert).
    """
    jahr = int(months_exp) // 12
    if pex_jahr is None:
        zeile = kern.zustand_am(months_exp)
        return {
            "jahr": zeile.jahr,
            "status": "POL",
            "deckungskapital": zeile.drx_bpfl,
            "rueckkaufswert": zeile.rkw,
            "vs_bfr": 0.0,
        }
    return {
        "jahr": jahr,
        "status": "PEX",
        "deckungskapital": kern.reserve_beitragsfrei(pex_jahr, jahr),
        "rueckkaufswert": 0.0,
        "vs_bfr": kern.beitragsfreie_summe(pex_jahr),
    }


def _kerne_je_police(
    stamm: pd.DataFrame, config: BestandConfig
) -> Dict[int, Rechenkern]:
    generationen = {g.name: g.generation_fields() for g in config.generationen}
    kerne: Dict[int, Rechenkern] = {}
    for row in stamm.to_dict("records"):
        if str(row.get("produkt", "klv")) != "klv":
            continue
        name = str(row["tarif_generation"])
        if name not in generationen:
            raise ValueError(
                f"police {row['police_id']}: Tarifgeneration {name!r} nicht in "
                f"Config (bekannt: {sorted(generationen)})"
            )
        kerne[int(row["police_id"])] = Rechenkern(
            ModelPoint(**model_point_kwargs(row, generationen[name]))
        )
    return kerne


def _bu_produkte_je_police(stamm: pd.DataFrame, config: BestandConfig) -> Dict[int, Any]:
    """police_id -> BU-Produktinstanz (nur fuer BU-Vertraege)."""
    from rechner_pipeline.kern.produkte.bu import BU, BUModelPoint

    grundlagen = {
        g.name: g.bu_generation_fields()
        for g in config.generationen
        if g.produkt == "bu"
    }
    produkte: Dict[int, Any] = {}
    for row in stamm.to_dict("records"):
        if str(row.get("produkt", "klv")) != "bu":
            continue
        name = str(row["tarif_generation"])
        if name not in grundlagen:
            raise ValueError(
                f"police {row['police_id']}: BU-Tarifgeneration {name!r} nicht "
                f"in Config (bekannt: {sorted(grundlagen)})"
            )
        produkte[int(row["police_id"])] = BU(
            BUModelPoint(**bu_model_point_kwargs(row, grundlagen[name]))
        )
    return produkte


def _bu_phasenbeginne(historie: pd.DataFrame) -> Dict[int, List[_dt.date]]:
    """police_id -> Datumsstempel der Uebergaenge in den Leistungsbezug.

    Weil die Statushistorie strikt zwischen Anwaerterstand und
    Leistungsbezug alterniert, ist der juengste BU-Stempel vor einem
    Stichtag genau der Beginn der dort laufenden Leistungsphase — daraus
    folgt die BU-Dauer (volle Jahre) fuer :meth:`BU.reserve_bu`.
    """
    if historie is None or len(historie) == 0:
        return {}
    bu = historie[historie["status_code"] == "BU"]
    beginne: Dict[int, List[_dt.date]] = {}
    for pid, datum in zip(bu["police_id"], bu["status_date"]):
        beginne.setdefault(int(pid), []).append(datum.date())
    for liste in beginne.values():
        liste.sort()
    return beginne


def _pex_jahre(stamm: pd.DataFrame, historie: pd.DataFrame) -> Dict[int, int]:
    """police_id -> Vertragsjahr der Beitragsfreistellung (aus der Historie)."""
    pex = historie[historie["status_code"] == "PEX"]
    if len(pex) == 0:
        return {}
    starts = stamm.set_index("police_id")["insurance_start"]
    return {
        int(pid): months_between(starts.loc[pid].date(), datum.date()) // 12
        for pid, datum in zip(pex["police_id"], pex["status_date"])
    }


def _scheiben_kerne(
    stamm: pd.DataFrame,
    scheiben: pd.DataFrame,
    config: BestandConfig,
) -> Dict[int, List[Dict[str, Any]]]:
    """police_id -> Erhoehungsscheiben mit eigenem Rechenkern (Schichtungsprinzip)."""
    generationen = {g.name: g.generation_fields() for g in config.generationen}
    haupt = stamm.set_index("police_id")
    je_police: Dict[int, List[Dict[str, Any]]] = {}
    for s in scheiben.to_dict("records"):
        pid = int(s["police_id"])
        if pid not in haupt.index:
            raise ValueError(
                f"scheiben: police_id {pid} unbekannt im Bestand — "
                "bei Neuzugaengen den Gesamtbestand uebergeben "
                "(mit_zugaengen(stamm, zugaenge)), sonst stammen Scheiben und "
                "Bestand nicht aus demselben Lauf"
            )
        h = haupt.loc[pid]
        row = {
            "entry_age": s["entry_age"],
            "sex": h["sex"],
            "duration": s["duration"],
            "premium_duration": s["premium_duration"],
            "sum_insured": s["sum_insured"],
            "zahlweise": h["zahlweise"],
        }
        kern = Rechenkern(
            ModelPoint(**model_point_kwargs(row, generationen[str(h["tarif_generation"])]))
        )
        je_police.setdefault(pid, []).append(
            {
                "erh_jahr": int(s["erhoehung_jahr"]),
                "erh_datum": s["erhoehung_datum"],
                "kern": kern,
            }
        )
    return je_police


def auswertungs_verlauf(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtage: List[_dt.date],
    scheiben: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """Aggregierte aktuarielle Kennzahlen je Stichtag (in-force-Bestand).

    ``historie`` darf None sein (reiner Basisbestand ohne Ereignisse) —
    dann sind alle Vertraege beitragspflichtig. ``scheiben`` (dynamische
    Erhoehungen) gehen ab ihrem Erhoehungstermin in die Summen ein; nach
    einer Beitragsfreistellung laeuft jede Scheibe mit ihrem eigenen
    Jahresversatz beitragsfrei weiter. Deterministisch: die
    Summationsreihenfolge folgt der Zeitscheiben-Sortierung.
    """
    if historie is not None and len(historie) > 0:
        sicht = bestand_mit_historie(stamm, historie)
        pex_jahre = _pex_jahre(stamm, historie)
    else:
        sicht = stamm
        pex_jahre = {}
    kerne = _kerne_je_police(stamm, config)
    bu_produkte = _bu_produkte_je_police(stamm, config)
    bu_beginne = _bu_phasenbeginne(historie)
    bu_renten = (
        stamm.set_index("police_id")["bu_rente"] if len(bu_produkte) else None
    )
    scheiben_je_police: Dict[int, List[Dict[str, Any]]] = (
        _scheiben_kerne(stamm, scheiben, config)
        if scheiben is not None and len(scheiben) > 0
        else {}
    )

    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        scheibe = zeitscheibe(sicht, stichtag)
        agg: Dict[str, Any] = {
            "stichtag": stichtag.isoformat(),
            "vertraege": int(len(scheibe)),
            "deckungskapital": 0.0,
            "deckungskapital_bfr": 0.0,
            "rueckkaufswert": 0.0,
            "vs_bfr": 0.0,
            # BU-Groessen (0, solange der Bestand keine BU-Vertraege fuehrt):
            "bu_vertraege": 0,
            "bu_leistungsbezug": 0,
            "bu_jahresrente": 0.0,
            "bu_jahresrente_laufend": 0.0,
            "deckungskapital_bu": 0.0,
        }
        for pid, months_exp, status in zip(
            scheibe["police_id"], scheibe["months_exp"], scheibe["status_code"]
        ):
            pid = int(pid)
            if pid in bu_produkte:
                # BU: Reserve aus dem Zustandsmodell — im Anwaerterstand die
                # Aktivenreserve, im Leistungsbezug die Invalidenreserve mit
                # der Dauer seit Rentenbeginn (Semi-Markov).
                produkt = bu_produkte[pid]
                jahr = int(months_exp) // 12
                rente = float(bu_renten.loc[pid])
                agg["bu_vertraege"] += 1
                agg["bu_jahresrente"] += rente
                if status == "BU":
                    beginne = [d for d in bu_beginne.get(pid, ()) if d <= stichtag]
                    if not beginne:
                        raise ValueError(
                            f"police {pid}: Status BU ohne BU-Zeile in der Historie"
                        )
                    dauer = months_between(beginne[-1], stichtag) // 12
                    reserve = produkt.reserve_bu(jahr, dauer)
                    agg["bu_leistungsbezug"] += 1
                    agg["bu_jahresrente_laufend"] += rente
                    agg["deckungskapital_bu"] += reserve
                else:
                    reserve = produkt.reserve_aktiv(jahr)
                agg["deckungskapital"] += reserve
                continue
            pex_jahr = None
            if status == "PEX":
                if pid not in pex_jahre:
                    raise ValueError(
                        f"police {pid}: PEX-Status ohne PEX-Zeile in der Historie"
                    )
                pex_jahr = pex_jahre[pid]
            werte = vertragswerte(kerne[pid], int(months_exp), pex_jahr)
            # Erhoehungsscheiben des Vertrags, die am Stichtag existieren —
            # jede mit ihrem Jahresversatz (PEX-Jahr entsprechend versetzt).
            aktive = [
                s for s in scheiben_je_police.get(pid, ())
                if s["erh_datum"].date() <= stichtag
            ]
            if aktive and pex_jahr is None:
                jahr = int(months_exp) // 12
                for s in aktive:
                    werte["deckungskapital"] += (
                        s["kern"].verlaufszeile(jahr - s["erh_jahr"]).drx_bpfl
                    )
                # Stornoabschlag-Grenzen gelten je Vertrag, nicht je Scheibe:
                werte["rueckkaufswert"] = vertrags_rkw(
                    kerne[pid], [(s["erh_jahr"], s["kern"]) for s in aktive], jahr
                )
            elif aktive:
                jahr = int(months_exp) // 12
                for s in aktive:
                    pex_s = pex_jahr - s["erh_jahr"]
                    if pex_s <= 0:
                        raise ValueError(
                            f"police {pid}: Scheibe aus Vertragsjahr "
                            f"{s['erh_jahr']} liegt nicht vor der "
                            f"Beitragsfreistellung (Jahr {pex_jahr})"
                        )
                    werte["deckungskapital"] += s["kern"].reserve_beitragsfrei(
                        pex_s, jahr - s["erh_jahr"]
                    )
                    werte["vs_bfr"] += s["kern"].beitragsfreie_summe(pex_s)
            agg["deckungskapital"] += werte["deckungskapital"]
            if werte["status"] == "PEX":
                agg["deckungskapital_bfr"] += werte["deckungskapital"]
                agg["vs_bfr"] += werte["vs_bfr"]
            else:
                agg["rueckkaufswert"] += werte["rueckkaufswert"]
        reihe.append(agg)
    return reihe
