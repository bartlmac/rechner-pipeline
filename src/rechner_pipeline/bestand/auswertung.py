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

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.fuehrung import bestand_am, months_between
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern
from rechner_pipeline.models.bestand import (
    STATUS_HISTORIE_SPALTEN,
    bu_model_point_kwargs,
    model_point_kwargs,
)


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


def beitraege(kern: Rechenkern, jahr: int) -> Dict[str, float]:
    """Jahresbeitrag und Beitragsvolumen eines Vertrags im Vertragsjahr ``jahr``.

    ``bjb`` ist der tarifliche Jahres-Bruttobeitrag (BJB = VS * Bxt),
    ``bzb_jahr`` das im Jahr tatsaechlich gezahlte Volumen: der Zahlbeitrag
    einer Rate mal Zahlweise, also einschliesslich Ratenzuschlag und
    Stueckkosten (BZB * zw). Beide sind Null, sobald die
    Beitragszahlungsdauer abgelaufen ist (``jahr >= t``) — ein Vertrag in
    der beitragsfreien Restlaufzeit steht weiter im Bestand, zahlt aber
    nicht mehr. Ohne diese Grenze waere die Beitragssumme systematisch zu
    hoch.
    """
    if jahr >= kern.mp.t:
        return {"bjb": 0.0, "bzb_jahr": 0.0}
    return {
        "bjb": kern.gross_annual_premium(),
        "bzb_jahr": kern.gross_payable_premium() * kern.mp.zw,
    }


def grundlagen_je_police(
    config: BestandConfig, merkmale: Optional[pd.DataFrame] = None
) -> Callable[[int, str], Dict[str, Any]]:
    """(police_id, generation) -> die Rechnungsgrundlagen dieses Vertrags.

    Eine Generation muss kein einziger Parametersatz sein. Ist sie in
    Tarifzellen aufgeteilt (``[[generation.zelle]]``), sagt
    ``merkmale.parquet``, welche Zelle ein Vertrag hat, und diese Zelle
    liefert die Grundlagen. Ohne Zellen — der Eigenbestand — bleibt es
    beim Satz der Generation; dann ist auch die Merkmalstabelle
    unerheblich.

    Fehlt die Tabelle, obwohl die Generation Zellen fuehrt, ist das ein
    harter Fehler und keine Bewertung mit dem Rumpf: Der Rumpf gilt fuer
    keinen einzigen Vertrag, und eine stille Naeherung waere hier eine
    falsche Bilanzzahl statt einer Fehlermeldung.
    """
    generationen = {g.name: g for g in config.generationen}
    hat_zellen = {n for n, g in generationen.items() if g.zellen}

    je_police: Dict[int, Dict[str, str]] = {}
    if merkmale is not None and len(merkmale):
        for pid, dim, wert in zip(
            merkmale["police_id"], merkmale["dimension"], merkmale["auspraegung"]
        ):
            je_police.setdefault(int(pid), {})[str(dim)] = str(wert)

    def aufloesen(pid: int, name: str) -> Dict[str, Any]:
        gen = generationen.get(name)
        if gen is None:
            raise ValueError(
                f"police {pid}: Tarifgeneration {name!r} nicht in Config "
                f"(bekannt: {sorted(generationen)})"
            )
        if name not in hat_zellen:
            return gen.generation_fields()
        auspraegungen = je_police.get(pid)
        if not auspraegungen:
            raise ValueError(
                f"police {pid}: Generation {name!r} ist in "
                f"{len(gen.zellen)} Tarifzellen ueber {list(gen.dimensionen())} "
                "aufgeteilt, der Vertrag traegt aber keine "
                "Merkmalsauspraegungen — merkmale.parquet mitgeben; ohne sie "
                "waere jede Zelle geraten"
            )
        return gen.felder_fuer(auspraegungen)

    return aufloesen


def _kerne_je_police(
    stamm: pd.DataFrame,
    config: BestandConfig,
    merkmale: Optional[pd.DataFrame] = None,
) -> Dict[int, Rechenkern]:
    grundlagen = grundlagen_je_police(config, merkmale)
    kerne: Dict[int, Rechenkern] = {}
    for row in stamm.to_dict("records"):
        if str(row.get("produkt", "klv")) != "klv":
            continue
        pid = int(row["police_id"])
        felder = grundlagen(pid, str(row["tarif_generation"]))
        kerne[pid] = Rechenkern(ModelPoint(**model_point_kwargs(row, felder)))
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


def _scheiben_kerne(
    stamm: pd.DataFrame,
    scheiben: pd.DataFrame,
    config: BestandConfig,
    merkmale: Optional[pd.DataFrame] = None,
) -> Dict[int, List[Dict[str, Any]]]:
    """police_id -> Erhoehungsscheiben mit eigenem Rechenkern (Schichtungsprinzip)."""
    grundlagen = grundlagen_je_police(config, merkmale)
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
        if "gamma1" not in s:
            raise ValueError(
                f"scheiben: police {pid} ohne gamma1-Spalte — Altbestand vor "
                "ADR-011; den Lauf mit der aktuellen Fortschreibung neu "
                "erzeugen (die Scheibe traegt ihre Rechnungsgrundlage selbst)"
            )
        kwargs = model_point_kwargs(
            row, grundlagen(pid, str(h["tarif_generation"])))
        # Schicht-eigene Rechnungsgrundlage der Scheibe (ADR-011): nicht aus
        # der Generation rekonstruieren — genau das hatte die Tarifwerk-Regel
        # (gamma1-Bezugsgroesse GrundVS => Scheibe 0) verloren.
        kwargs["gamma1"] = float(s["gamma1"])
        kern = Rechenkern(ModelPoint(**kwargs))
        je_police.setdefault(pid, []).append(
            {
                "erh_jahr": int(s["erhoehung_jahr"]),
                "erh_datum": s["erhoehung_datum"],
                "kern": kern,
            }
        )
    return je_police


def einzelwerte_am(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtag: _dt.date,
    scheiben: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """Einzelvertragliche Bewertung des in-force-Bestands am Stichtag.

    DIE eine Bewertungsstrecke (ADR-011): Aggregation
    (:func:`auswertungs_verlauf`), Abschluss
    (:mod:`rechner_pipeline.bestand.abschluss`) und kuenftige Leser
    konsumieren dieselben Zeilen — ein zweiter Rechenweg waere der
    Drift-Mechanismus, den dieser Umbau gerade beseitigt hat.

    Rueckgabe je Police (Reihenfolge = Auskunfts-Sortierung):
    ``police_id``, ``produkt``, ``tarif_generation``, ``status``,
    ``leistung`` (VS bzw. Jahresrente), ``deckungskapital``,
    ``rueckkaufswert``, ``vs_bfr``, ``jahresbeitrag`` (tariflicher
    Jahres-Bruttobeitrag; 0 nach Beitragsende, bei PEX und im
    BU-Leistungsbezug), ``bzb_jahr`` (gezahltes Jahresvolumen, KLV) und
    ``bu_leistungsbezug`` (bool).
    """
    if historie is None:
        # Ein gefuehrter Stamm traegt seinen aktuellen Zustand; journalsicht
        # synthetisiert den Ursprung aber unbedingt als POL am
        # Versicherungsbeginn. Ohne Journal bliebe genau diese eine Zeile
        # uebrig — stornierte und verstorbene Vertraege kehrten als
        # beitragspflichtige POL in den Bestand zurueck, und beitragsfreies
        # Geschaeft verschwaende. Derselbe Wachposten steht in Gate P-B1
        # (gates/bestand_validate: "Portfolio traegt Folgezustaende"); er
        # gehoert auch hierher, weil die Bibliothek ohne Gate aufrufbar ist.
        folge = stamm["status_id"] > 1
        if bool(folge.any()):
            betroffen = sorted(stamm.loc[folge, "police_id"])[:5]
            raise ValueError(
                f"{int(folge.sum())} Vertraege tragen einen Folgezustand "
                f"(status_id > 1, z. B. police {betroffen}), aber es wurde "
                "keine Historie uebergeben. Der gefuehrte Zustand ginge "
                "verloren und die Bewertung faende terminierte Vertraege als "
                "beitragspflichtig wieder — Journal mitgeben (ADR-011)"
            )
        journal = pd.DataFrame(
            {name: pd.Series(dtype=dtype) for name, dtype in STATUS_HISTORIE_SPALTEN}
        )
    else:
        journal = historie
    kerne = _kerne_je_police(stamm, config, merkmale)
    bu_produkte = _bu_produkte_je_police(stamm, config)
    bu_renten = (
        stamm.set_index("police_id")["bu_rente"] if len(bu_produkte) else None
    )
    scheiben_je_police: Dict[int, List[Dict[str, Any]]] = (
        _scheiben_kerne(stamm, scheiben, config, merkmale)
        if scheiben is not None and len(scheiben) > 0
        else {}
    )
    generation_je_police = stamm.set_index("police_id")["tarif_generation"]

    scheibe = bestand_am(stamm, journal, stichtag)
    zeilen: List[Dict[str, Any]] = []
    for pid, months_exp, status, status_seit, beginn in zip(
        scheibe["police_id"],
        scheibe["months_exp"],
        scheibe["status_code"],
        scheibe["status_date"],
        scheibe["insurance_start"],
    ):
        pid = int(pid)
        zeile: Dict[str, Any] = {
            "police_id": pid,
            "tarif_generation": str(generation_je_police.loc[pid]),
            "status": str(status),
            "leistung": 0.0,
            "deckungskapital": 0.0,
            "rueckkaufswert": 0.0,
            "vs_bfr": 0.0,
            "jahresbeitrag": 0.0,
            "bzb_jahr": 0.0,
            "bu_leistungsbezug": False,
        }
        if pid in bu_produkte:
            # BU: Reserve aus dem Zustandsmodell — im Anwaerterstand die
            # Aktivenreserve, im Leistungsbezug die Invalidenreserve mit
            # der Dauer seit Rentenbeginn (Semi-Markov). Die Dauer ist
            # Zustand: status_date der Auskunftszeile IST der Beginn der
            # am Stichtag laufenden Leistungsphase.
            produkt = bu_produkte[pid]
            jahr = int(months_exp) // 12
            zeile["produkt"] = "bu"
            zeile["leistung"] = float(bu_renten.loc[pid])
            if status == "BU":
                dauer = months_between(status_seit.date(), stichtag) // 12
                zeile["deckungskapital"] = produkt.reserve_bu(jahr, dauer)
                zeile["bu_leistungsbezug"] = True
            else:
                zeile["deckungskapital"] = produkt.reserve_aktiv(jahr)
                # Beitragszahlung nur im Anwaerterstand (die implizite
                # Beitragsbefreiung des Leistungsfalls steckt im Profil);
                # Beitrags- = Versicherungsdauer.
                if jahr < produkt.mp.n:
                    zeile["jahresbeitrag"] = produkt.bruttobeitrag()
            zeilen.append(zeile)
            continue
        zeile["produkt"] = "klv"
        zeile["leistung"] = float(kerne[pid].mp.sum_insured)
        pex_jahr = None
        if status == "PEX":
            # Das PEX-Jahr ist Zustand: Vertragsjahr des Statusbeginns.
            pex_jahr = months_between(beginn.date(), status_seit.date()) // 12
        werte = vertragswerte(kerne[pid], int(months_exp), pex_jahr)
        # Erhoehungsscheiben des Vertrags, die am Stichtag existieren —
        # jede mit ihrem Jahresversatz (PEX-Jahr entsprechend versetzt).
        aktive = [
            s for s in scheiben_je_police.get(pid, ())
            if s["erh_datum"].date() <= stichtag
        ]
        if pex_jahr is None:
            # Jede Erhoehungsscheibe ist ein eigener Modellpunkt mit
            # eigenem Beitrag — ohne sie waere das Beitragsvolumen so
            # zu niedrig wie das Deckungskapital ohne Scheiben.
            bt = beitraege(kerne[pid], int(months_exp) // 12)
            zeile["jahresbeitrag"] += bt["bjb"]
            zeile["bzb_jahr"] += bt["bzb_jahr"]
        if aktive and pex_jahr is None:
            jahr = int(months_exp) // 12
            for s in aktive:
                werte["deckungskapital"] += (
                    s["kern"].verlaufszeile(jahr - s["erh_jahr"]).drx_bpfl
                )
                bt = beitraege(s["kern"], jahr - s["erh_jahr"])
                zeile["jahresbeitrag"] += bt["bjb"]
                zeile["bzb_jahr"] += bt["bzb_jahr"]
                zeile["leistung"] += float(s["kern"].mp.sum_insured)
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
                zeile["leistung"] += float(s["kern"].mp.sum_insured)
        zeile["status"] = werte["status"]
        zeile["deckungskapital"] = werte["deckungskapital"]
        zeile["rueckkaufswert"] = (
            0.0 if werte["status"] == "PEX" else werte["rueckkaufswert"]
        )
        zeile["vs_bfr"] = werte["vs_bfr"] if werte["status"] == "PEX" else 0.0
        zeilen.append(zeile)
    return zeilen


def auswertungs_verlauf(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtage: List[_dt.date],
    scheiben: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
) -> List[Dict[str, Any]]:
    """Aggregierte aktuarielle Kennzahlen je Stichtag (in-force-Bestand).

    ``historie`` darf None sein (reiner Basisbestand ohne Ereignisse) —
    dann sind alle Vertraege beitragspflichtig. ``scheiben`` (dynamische
    Erhoehungen) gehen ab ihrem Erhoehungstermin in die Summen ein; nach
    einer Beitragsfreistellung laeuft jede Scheibe mit ihrem eigenen
    Jahresversatz beitragsfrei weiter. Deterministisch: die
    Summationsreihenfolge folgt der Auskunfts-Sortierung.

    Arbeitsteilung nach ADR-011: Der Zustand je Stichtag kommt aus der
    Auskunft (:func:`~rechner_pipeline.bestand.fuehrung.bestand_am`); die
    Bewertung selbst liest ausschliesslich die Zustandszeile — Verweildauer
    und PEX-Jahr folgen aus ``status_date``, nie aus einem Journal-Lauf.
    """
    reihe: List[Dict[str, Any]] = []
    for stichtag in stichtage:
        zeilen = einzelwerte_am(stamm, historie, config, stichtag,
                                scheiben=scheiben, merkmale=merkmale)
        agg: Dict[str, Any] = {
            "stichtag": stichtag.isoformat(),
            "vertraege": int(len(zeilen)),
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
            "deckungskapital_anwaerter": 0.0,
            # Beitragsgroessen: nur beitragspflichtige Vertraege innerhalb
            # ihrer Beitragszahlungsdauer; beitragsfreie (PEX) und BU-Ver-
            # traege im Leistungsbezug (Beitragsbefreiung) zahlen nicht.
            "bjb": 0.0,
            "bzb_jahr": 0.0,
            "bu_beitrag": 0.0,
        }
        for z in zeilen:
            agg["deckungskapital"] += z["deckungskapital"]
            if z["produkt"] == "bu":
                agg["bu_vertraege"] += 1
                agg["bu_jahresrente"] += z["leistung"]
                if z["bu_leistungsbezug"]:
                    agg["bu_leistungsbezug"] += 1
                    agg["bu_jahresrente_laufend"] += z["leistung"]
                    agg["deckungskapital_bu"] += z["deckungskapital"]
                else:
                    agg["deckungskapital_anwaerter"] += z["deckungskapital"]
                    agg["bu_beitrag"] += z["jahresbeitrag"]
                continue
            agg["bjb"] += z["jahresbeitrag"]
            agg["bzb_jahr"] += z["bzb_jahr"]
            if z["status"] == "PEX":
                agg["deckungskapital_bfr"] += z["deckungskapital"]
                agg["vs_bfr"] += z["vs_bfr"]
            else:
                agg["rueckkaufswert"] += z["rueckkaufswert"]
        reihe.append(agg)
    return reihe
