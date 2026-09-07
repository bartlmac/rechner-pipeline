"""``fuehrungsprobe`` — die Fuehrung gegen die Pruefstrecke (Freischaltung, Schritt 6).

Produzent, kein Gate (Muster ``gates.migrationssuite_lauf``): schreibt
einen JSON-Beleg, den der Abnahmebericht im Bestands-Scope bindet und
A-M4 als Pflichtbelegrolle ``fuehrungsprobe`` verlangt.

**Die Frage, die er beantwortet.** Die Abnahmen A-M1 bis A-M4 rechnen
jeden uebernommenen Vertrag auf seinem Anfangszustand mit den Schaltern
der Lieferung und der Korrekturschicht. Ob der gefuehrte Bestand diese
Welt auch benutzt, sah bis zur Freischaltung niemand: Kein Gate stellte
das Ledger der Fuehrung neben die Werte der Pruefstrecke — im zweiten
Baldrian-Fall lagen 550 von 834 Stammsummen in der falschen Welt
(dev-docs/freischaltung-uebernommener-bestand.md, Abschnitt 1.1). Hier
wird der Bestand, den die Uebernahme geschrieben hat, und das Journal,
das die Fortschreibung darauf gebucht hat, gegen die Pruefstrecken-Welt
gehalten:

1. der Uebernahmebeleg (``uebernahme.json``): materialisierter
   Anfangszustand, Tarifwerks-Schalter gleich denen der Config der
   Generation und denen dieses Laufs;
2. je Vertrag: Stammsumme, Bausteine (Scheiben mit ihrem gamma1),
   Beitragsfreistellung, Zugang und Umbuchung gegen den Anfangszustand,
   den DIESELBE Ableitung wie in den Abnahmen liefert
   (``migrationssuite_lauf.anfangszustaende_je_police``); die
   Rechnungsgrundlagen der Config gegen die Spez-Zelle des Vertrags;
3. je Buchung der Fortschreibung nach dem Stichtag (Storno, Umbuchung,
   Tod, Ablauf) den Betrag gegen die Pruefstrecken-Engine am gebuchten
   Vertragsmonat — Kern mit Bausteinen, Stornoabzug je Baustein nach
   Schalter, Korrekturschicht aus dem Schichtbeleg.

Was die Probe NICHT ist: keine zweite Abnahme. Sie rechnet mit denselben
Kern-Funktionen wie die Pruefstrecke und prueft, ob die Fuehrung sie
ruft — Materialisierung und Verdrahtung, nicht Tarifmathematik.

Knoten: klv
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline import fall as fall_mod
from rechner_pipeline.bestand.config import BestandConfig, load_config
from rechner_pipeline.bestand.parquet_io import read_portfolio
from rechner_pipeline.gates._provenienz import systemstand
from rechner_pipeline.gates.bestand_uebernehmen import GRUNDVERTRAG, MATERIALISIEREN
from rechner_pipeline.gates.migrationssuite_lauf import (
    VORGABE,
    _lies_csv,
    anfangszustaende_je_police,
    auspraegungen_je_police,
)
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe, vertrags_monatsreserve
from rechner_pipeline.kern.beitragsreduktion import PROSPEKTIV, VERFAHREN
from rechner_pipeline.kern.korrekturschicht import Schichtparameter, schichtwert_bei
from rechner_pipeline.models.bestand import (
    GENERATION_FIELDS,
    LEDGER_NAMES,
    SCHEIBEN_NAMES,
    SCHICHTEN_NAMES,
    STAMM_NAMES,
    STATUS_HISTORIE_NAMES,
    VERANKERUNG_NAMES,
    model_point_kwargs,
)
from rechner_pipeline.spez.validierung import lade_spez

#: Schema des Probe-Belegs.
SCHEMA_VERSION = 1

#: Cent-Toleranz wie in der Ledger-Herleitung von P-B1: Fuehrung und
#: Pruefstrecke rufen dieselben Kern-Funktionen; ein vertragsweiter
#: Stornoabzug der Vorgabe darf um Gleitkomma-Rauschen abweichen, eine
#: falsche Welt liegt Groessenordnungen darueber.
TOLERANZ = 0.005

GEPRUEFTE_BUCHUNGEN = ("STO", "PEX", "TOD", "ABL")


def _jahre(beginn: pd.Timestamp, datum: pd.Timestamp) -> int:
    return ((datum.year * 12 + datum.month) - (beginn.year * 12 + beginn.month)) // 12


def _zelle(spez, auspraegungen: Dict[str, str]):
    gesucht = {k: str(v).strip().lower() for k, v in auspraegungen.items() if v}
    treffer = [z for z in spez.zellen if z.auspraegungen == gesucht]
    if not treffer:
        raise SystemExit(
            f"keine Spez-Zelle fuer {gesucht!r} — vorhanden sind "
            f"{[z.auspraegungen for z in spez.zellen]}")
    return treffer[0]


def pruefe_fuehrung(
    *,
    uebernahme: Dict[str, Any],
    fortschreibung: Optional[Dict[str, Any]],
    config: BestandConfig,
    spez,
    zeilen: List[Dict[str, Any]],
    vorgeschichte: List[Dict[str, str]],
    tarifwerk: Dict[str, Any],
    erhoehungssatz: Optional[float],
    red_anteile: Dict[str, float],
    red_anteile_je_datum: Dict[str, Dict[str, float]],
    red_anteil_kandidaten: Tuple[float, ...],
    anker: Dict[str, Tuple[int, float]],
    schichtbeleg: Optional[Dict[str, Any]],
    stichtag: dt.date,
) -> Dict[str, Any]:
    """Der rechnende Kern der Probe (rein, ohne Dateisystem).

    ``uebernahme``: ``bestand``, ``historie``, ``ledger`` (DataFrames),
    optional ``scheiben``, ``verankerung``, ``schichten``, ``merkmale``,
    und ``beleg`` (``uebernahme.json`` als Dict). ``fortschreibung``:
    ``ledger``, ``scheiben``, ``historie`` des Laufs nach dem Stichtag
    oder None. ``schichtbeleg``: ``schichten`` des Schichtbelegs
    (police -> {"hist": Parameter}) oder None. Rueckgabe: der Beleg ohne
    ``system``/``provenienz`` (die setzt ``main``).
    """
    befunde: List[Dict[str, Any]] = []
    stamm: pd.DataFrame = uebernahme["bestand"]
    historie: pd.DataFrame = uebernahme["historie"]
    ledger: pd.DataFrame = uebernahme["ledger"]
    scheiben = uebernahme.get("scheiben")
    verankerung = uebernahme.get("verankerung")
    beleg = uebernahme.get("beleg") or {}
    merkmale = uebernahme.get("merkmale")

    def befund(police: Any, art: str, text: str, **rest: Any) -> None:
        befunde.append({"police_id": None if police is None else str(police),
                        "art": art, "text": text, **rest})

    # 1. Beleg und Schalter -------------------------------------------------
    modus = beleg.get("anfangszustand")
    if modus == GRUNDVERTRAG:
        befund(None, "nicht_freigeschaltet",
               f"Uebernahme fuehrt {len(beleg.get('nicht_freigeschaltet') or [])} "
               "Vertraege mit Erhoehungen/Herabsetzungen als Grundvertrag "
               f"(--anfangszustand {GRUNDVERTRAG}) — nicht freigeschaltet",
               policen=list(beleg.get("nicht_freigeschaltet") or []))
    elif modus not in (MATERIALISIEREN, "ohne_bausteine"):
        befund(None, "beleg", f"Uebernahmebeleg ohne gueltigen Modus: {modus!r}")

    generationen = sorted(set(str(g) for g in stamm["tarif_generation"]))
    if len(generationen) != 1:
        befund(None, "generation",
               f"uebernommener Bestand traegt {len(generationen)} Generationen "
               f"{generationen} — eine Uebernahme ist eine Generation")
    gen = next((g for g in config.generationen if g.name in generationen), None)
    if gen is None:
        befund(None, "config",
               f"Generation {generationen} nicht in der Config "
               f"(bekannt: {[g.name for g in config.generationen]})")
        tw_config: Dict[str, Any] = {}
    else:
        tw_config = gen.tarifwerk()
    tw_beleg = dict(beleg.get("tarifwerk") or {})
    for name, quelle, werte in (("config", "Config der Generation", tw_config),
                                ("beleg", "Uebernahmebeleg", tw_beleg)):
        if werte != tarifwerk:
            befund(None, "tarifwerk",
                   f"Tarifwerks-Schalter der {quelle} {werte} weichen von "
                   f"denen dieses Laufs {tarifwerk} ab — die Pruefstrecke hat "
                   "mit anderen Schaltern abgenommen als die Fuehrung rechnet")

    # 2. Anfangszustand je Vertrag -----------------------------------------
    auspraegungen = auspraegungen_je_police(spez, zeilen) if zeilen else {}
    if vorgeschichte:
        zustaende, warnungen = anfangszustaende_je_police(
            spez, zeilen, vorgeschichte, stamm, spalten=dict(VORGABE),
            red_verfahren=tarifwerk["red_verfahren"], red_anteile=red_anteile,
            auspraegungen=auspraegungen, erhoehungssatz=erhoehungssatz,
            anker=anker, red_anteile_je_datum=red_anteile_je_datum,
            red_anteil_kandidaten=red_anteil_kandidaten,
            scheiben_mit_gamma1=bool(tarifwerk["scheiben_mit_gamma1"]))
    else:
        zustaende, warnungen = {}, []
    ohne_zustand = set()
    for w in warnungen:
        teile = w.split()
        if len(teile) >= 2 and teile[0] == "Police":
            ohne_zustand.add(teile[1].strip(":(),"))
    ausgewiesen = {str(e.get("police_id")) for e in beleg.get("ohne_anfangszustand") or []}
    if modus == MATERIALISIEREN and ohne_zustand != ausgewiesen:
        befund(None, "ausnahmen",
               "Vertraege ohne ableitbaren Anfangszustand: Pruefstrecke "
               f"{sorted(ohne_zustand)} vs. Uebernahmebeleg {sorted(ausgewiesen)}")

    geliefert = {str(z["police_id"]): float(z["sum_insured"]) for z in zeilen}
    haupt = stamm.set_index("police_id")
    ledger_zug = ledger[ledger["ereignis"] == "ZUG"].set_index("police_id")["betrag"]
    ledger_pex = ledger[ledger["ereignis"] == "PEX"].set_index("police_id")["betrag"]
    pex_historie: Dict[int, pd.Timestamp] = {}
    if len(historie):
        for pid, datum in historie[historie["status_code"] == "PEX"][
                ["police_id", "status_date"]].itertuples(index=False):
            pex_historie[int(pid)] = min(pd.Timestamp(datum), pex_historie.get(int(pid), pd.Timestamp(datum)))
    scheiben_je_police: Dict[int, List[Dict[str, Any]]] = {}
    if scheiben is not None and len(scheiben):
        for s in scheiben.to_dict("records"):
            scheiben_je_police.setdefault(int(s["police_id"]), []).append(s)

    from rechner_pipeline.bestand.auswertung import grundlagen_je_police
    grundlagen = grundlagen_je_police(config, merkmale)

    welten: Dict[int, Dict[str, Any]] = {}
    zahlen = {"vertraege": int(len(stamm)), "mit_anfangszustand": 0,
              "scheiben": 0, "beitragsfrei": 0}
    for row in stamm.to_dict("records"):
        pid = int(row["police_id"]); police = str(pid)
        zelle_felder = dict(_zelle(spez, auspraegungen.get(police, {})).model_point)
        # Rechnungsgrundlagen der Fuehrung = die der Spez-Zelle.
        try:
            felder_config = grundlagen(pid, str(row["tarif_generation"]))
        except ValueError as exc:
            befund(pid, "grundlagen", str(exc)); continue
        abweichend = sorted(
            f for f in GENERATION_FIELDS
            if f in zelle_felder and felder_config.get(f) != zelle_felder[f])
        if abweichend:
            befund(pid, "grundlagen",
                   f"Rechnungsgrundlagen der Config weichen von der Spez-Zelle "
                   f"ab: {abweichend}")
        z = zustaende.get(police, {})
        if z:
            zahlen["mit_anfangszustand"] += 1
        if z.get("reduktion") is not None:
            befund(pid, "nicht_freigeschaltet",
                   "Herabsetzungs-Zustand der Pruefstrecke — die Fuehrung traegt "
                   "keinen geteilten Vertrag")
        erwartete_summe = float(z["sum_insured"]) if "sum_insured" in z else geliefert.get(police)
        if erwartete_summe is None:
            befund(pid, "zeilen", "keine transformierte Zeile — Summe nicht pruefbar")
            erwartete_summe = float(row["sum_insured"])
        if abs(float(row["sum_insured"]) - erwartete_summe) > TOLERANZ:
            befund(pid, "stammsumme",
                   f"Stammsumme {float(row['sum_insured']):.2f} statt "
                   f"{erwartete_summe:.2f} (Grund-/Ursprungssumme der Pruefstrecke)")
        kw = model_point_kwargs(row, zelle_felder)
        kw["sum_insured"] = erwartete_summe
        grund_mp = ModelPoint(**kw)
        # Bausteine
        erwartet_scheiben = sorted((int(j), float(s)) for j, s in z.get("scheiben", ()))
        vorhanden = sorted(
            (int(s["erhoehung_jahr"]), float(s["sum_insured"]))
            for s in scheiben_je_police.get(pid, []))
        if len(erwartet_scheiben) != len(vorhanden) or any(
                a[0] != b[0] or abs(a[1] - b[1]) > TOLERANZ
                for a, b in zip(erwartet_scheiben, vorhanden)):
            befund(pid, "scheiben",
                   f"Bausteine der Fuehrung {vorhanden} statt "
                   f"{erwartet_scheiben} (Alt-Erhoehungen der Pruefstrecke)")
        gamma1_soll = float(zelle_felder["gamma1"]) if tarifwerk["scheiben_mit_gamma1"] else 0.0
        for s in scheiben_je_police.get(pid, []):
            if float(s["gamma1"]) != gamma1_soll:
                befund(pid, "scheiben",
                       f"Scheibe {int(s['scheiben_id'])} traegt gamma1 "
                       f"{float(s['gamma1'])!r} statt {gamma1_soll!r}")
        zahlen["scheiben"] += len(erwartet_scheiben)
        teile = [(j, Rechenkern(erhoehungs_scheibe(
            grund_mp, j, s, gamma1_uebernehmen=bool(tarifwerk["scheiben_mit_gamma1"]))))
            for j, s in erwartet_scheiben]
        grund = Rechenkern(grund_mp)
        # Beitragsfreistellung
        pex_jahr = z.get("beitragsfrei_seit_jahr")
        beginn = pd.Timestamp(row["insurance_start"])
        if pex_jahr is None and pid in pex_historie and vorgeschichte:
            # PEX in der Historie ohne Zustand der Pruefstrecke: nur bei
            # einem Vertrag ohne ableitbaren Zustand zulaessig.
            if police not in ohne_zustand and not z:
                pex_jahr = _jahre(beginn, pex_historie[pid])
        if pex_jahr is not None:
            zahlen["beitragsfrei"] += 1
            if pid not in pex_historie:
                befund(pid, "beitragsfrei", "beitragsfrei nach Pruefstrecke, aber "
                       "ohne PEX-Zeile in der Historie")
            elif _jahre(beginn, pex_historie[pid]) != int(pex_jahr):
                befund(pid, "beitragsfrei",
                       f"PEX-Jahr {_jahre(beginn, pex_historie[pid])} in der "
                       f"Historie, {int(pex_jahr)} in der Pruefstrecke")
            vs_bfr = grund.beitragsfreie_summe(int(pex_jahr)) + sum(
                k.beitragsfreie_summe(int(pex_jahr) - j) for j, k in teile)
            if pid not in ledger_pex.index:
                befund(pid, "umbuchung", "keine PEX-Umbuchung im Uebernahme-Ledger")
            elif abs(float(ledger_pex.loc[pid]) - vs_bfr) > TOLERANZ:
                befund(pid, "umbuchung",
                       f"Umbuchung {float(ledger_pex.loc[pid]):.2f} statt "
                       f"{vs_bfr:.2f} (beitragsfreie Summe der Pruefstrecke)")
        gesamt = grund_mp.sum_insured + sum(k.mp.sum_insured for _, k in teile)
        if pid not in ledger_zug.index:
            befund(pid, "zugang", "keine Zugangsbuchung im Uebernahme-Ledger")
        elif abs(float(ledger_zug.loc[pid]) - gesamt) > TOLERANZ:
            befund(pid, "zugang",
                   f"Zugang {float(ledger_zug.loc[pid]):.2f} statt {gesamt:.2f} "
                   "(Gesamtsumme der Bausteine)")
        welten[pid] = {"grund": grund, "grund_mp": grund_mp, "teile": teile,
                       "pex_jahr": pex_jahr, "gesamt": gesamt, "beginn": beginn}

    # 3. Schicht ------------------------------------------------------------
    schicht_je_police: Dict[int, Tuple[Schichtparameter, int]] = {}
    if schichtbeleg:
        if verankerung is None or len(verankerung) == 0:
            befund(None, "schicht", "Schichtbeleg ohne verankerung.parquet")
        else:
            anker_ta = verankerung.set_index("police_id")["monate_ta"]
            for police, eintrag in schichtbeleg.items():
                pid = int(police)
                if "conv" in eintrag:
                    befund(pid, "nicht_freigeschaltet",
                           "Zweitschicht R_conv ist in der Fuehrung nicht freigeschaltet")
                if pid not in anker_ta.index:
                    befund(pid, "schicht", "Schicht ohne Verankerungszeitpunkt")
                    continue
                schicht_je_police[pid] = (
                    Schichtparameter(**{
                        **eintrag["hist"],
                        "vererbend": tuple(tuple(p) for p in eintrag["hist"]["vererbend"]),
                    }),
                    int(anker_ta.loc[pid]),
                )
        tabelle = uebernahme.get("schichten")
        if tabelle is None or len(tabelle) == 0:
            befund(None, "schicht",
                   "Schichtbeleg vorhanden, aber schichten.parquet fehlt im "
                   "Uebernahme-Verzeichnis — die Fuehrung kennt die Schicht nicht")
        else:
            fehlend = sorted(set(schicht_je_police) - set(int(p) for p in tabelle["police_id"]))
            if fehlend:
                befund(None, "schicht",
                       f"{len(fehlend)} Schichten des Belegs fehlen in "
                       f"schichten.parquet (z. B. {fehlend[:5]})")
            tabelle_rho = {int(z["police_id"]): float(z["rho"]) for z in tabelle.to_dict("records")}
            for pid, (param, _) in schicht_je_police.items():
                if pid in tabelle_rho and tabelle_rho[pid] != param.rho:
                    befund(pid, "schicht",
                           f"rho {tabelle_rho[pid]!r} in schichten.parquet, "
                           f"{param.rho!r} im Schichtbeleg")

    # 4. Buchungen der Fortschreibung nach dem Stichtag ---------------------
    buchungen: Dict[str, int] = {art: 0 for art in GEPRUEFTE_BUCHUNGEN}
    abweichungen = 0
    if fortschreibung is not None:
        f_ledger: pd.DataFrame = fortschreibung["ledger"]
        f_scheiben = fortschreibung.get("scheiben")
        neue_je_police: Dict[int, List[Dict[str, Any]]] = {}
        if f_scheiben is not None and len(f_scheiben):
            for s in f_scheiben.to_dict("records"):
                if pd.Timestamp(s["erhoehung_datum"]) > pd.Timestamp(stichtag):
                    neue_je_police.setdefault(int(s["police_id"]), []).append(s)
        nach = f_ledger[
            f_ledger["police_id"].isin(set(int(p) for p in stamm["police_id"]))
            & (pd.to_datetime(f_ledger["status_date"]) > pd.Timestamp(stichtag))
            & f_ledger["ereignis"].isin(GEPRUEFTE_BUCHUNGEN)
        ]
        for z in nach.to_dict("records"):
            pid, art, jahr = int(z["police_id"]), str(z["ereignis"]), int(z["vertragsjahr"])
            welt = welten.get(pid)
            if welt is None:
                continue
            teile = list(welt["teile"])
            for s in neue_je_police.get(pid, []):
                if int(s["erhoehung_jahr"]) < jahr:
                    row = {"entry_age": s["entry_age"], "sex": haupt.loc[pid, "sex"],
                           "duration": s["duration"], "premium_duration": s["premium_duration"],
                           "sum_insured": s["sum_insured"], "zahlweise": haupt.loc[pid, "zahlweise"]}
                    kw = model_point_kwargs(row, dict(_zelle(
                        spez, auspraegungen.get(str(pid), {})).model_point))
                    kw["gamma1"] = float(s["gamma1"])
                    teile.append((int(s["erhoehung_jahr"]), Rechenkern(ModelPoint(**kw))))
            teile = [(j, k) for j, k in teile if j < jahr]
            grund, grund_mp = welt["grund"], welt["grund_mp"]
            pex_jahr = welt["pex_jahr"]
            if art == "STO":
                erwartet = vertrags_monatsreserve(
                    grund, teile, 12 * jahr,
                    stoab_je_baustein=bool(tarifwerk["stoab_je_baustein"])).rkw
                schicht = schicht_je_police.get(pid)
                if schicht is not None and 12 * jahr >= schicht[1]:
                    erwartet += schichtwert_bei(schicht[0], schicht[1], grund_mp, 12 * jahr)
            elif art == "PEX":
                erwartet = grund.beitragsfreie_summe(jahr) + sum(
                    k.beitragsfreie_summe(jahr - j) for j, k in teile)
            else:
                pex_f = pex_jahr
                if pex_f is None:
                    eigene_pex = f_ledger[(f_ledger["police_id"] == pid)
                                          & (f_ledger["ereignis"] == "PEX")]
                    if len(eigene_pex):
                        pex_f = int(eigene_pex["vertragsjahr"].iloc[0])
                if pex_f is not None:
                    erwartet = grund.beitragsfreie_summe(int(pex_f)) + sum(
                        k.beitragsfreie_summe(int(pex_f) - j) for j, k in teile
                        if int(pex_f) - j > 0)
                else:
                    erwartet = grund_mp.sum_insured + sum(k.mp.sum_insured for _, k in teile)
            buchungen[art] += 1
            if abs(float(z["betrag"]) - erwartet) > TOLERANZ:
                abweichungen += 1
                befund(pid, "buchung",
                       f"{art} im Vertragsjahr {jahr}: Fuehrung {float(z['betrag']):.2f}, "
                       f"Pruefstrecke {erwartet:.2f}", ereignis=art, jahr=jahr,
                       fuehrung=float(z["betrag"]), pruefstrecke=erwartet)

    return {
        "schema_version": SCHEMA_VERSION,
        "stichtag": stichtag.isoformat(),
        "generation": generationen[0] if len(generationen) == 1 else generationen,
        "tarifwerk": tarifwerk,
        "anfangszustand": modus,
        **zahlen,
        "ohne_anfangszustand": sorted(ohne_zustand),
        "schichten": len(schicht_je_police),
        "buchungen_geprueft": buchungen,
        "buchungen_abweichend": abweichungen,
        "fortschreibung_geprueft": fortschreibung is not None,
        "befunde": befunde,
        "bestanden": not befunde,
    }


def _sha256(pfad: Path) -> str:
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.gates.fuehrungsprobe",
        description="Die Fuehrung gegen die Pruefstrecke halten "
                    "(Produzent, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--repo-root", dest="repo_root", required=True)
    p.add_argument("--generation", required=True,
                   help="Knoten-Id der Tarifgeneration, z. B. klv/tg2015")
    p.add_argument("--uebernahme", default=None,
                   help="Uebernahme-Verzeichnis (Vorgabe: <fall>/abgeleitet/bestand)")
    p.add_argument("--fortschreibung", default=None,
                   help="Laufverzeichnis der Fortschreibung des uebernommenen "
                        "Bestands (bestand_fortschreibung --uebernahme); ohne "
                        "es werden nur Uebernahme und Anfangszustand geprueft")
    p.add_argument("--config", required=True, help="Bestand-Config der Fuehrung (TOML)")
    p.add_argument("--zeilen", required=True,
                   help="transformierte Zeilen (gates.transformation_anwenden --zeilen)")
    p.add_argument("--vorgeschichte", default=None,
                   help="REGISTRIERTE Metadatenliste der Geschaeftsvorfaelle")
    p.add_argument("--stichtag", required=True, help="Migrationsstichtag (ISO)")
    p.add_argument("--schicht", default=None,
                   help="ABGELEITETER Schichtbeleg (gates.verankerung_belegen)")
    p.add_argument("--erhoehungssatz", type=float, default=None)
    p.add_argument("--red-verfahren", dest="red_verfahren", default=PROSPEKTIV,
                   choices=sorted(VERFAHREN))
    p.add_argument("--red-anteil", dest="red_anteile", action="append", default=[])
    p.add_argument("--red-anteil-kandidat", dest="red_anteil_kandidaten",
                   action="append", type=float, default=[])
    p.add_argument("--red-anteile-datei", dest="red_anteile_datei", default=None)
    p.add_argument("--anker-erwartungswerte", dest="anker_quelle", default=None)
    p.add_argument("--scheiben-mit-gamma1", dest="scheiben_mit_gamma1", action="store_true")
    p.add_argument("--stoab-je-baustein", dest="stoab_je_baustein", action="store_true")
    p.add_argument("--out", default=None,
                   help="Zielpfad (Vorgabe: <fall>/abgeleitet/berichte/fuehrungsprobe.json)")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2
    repo_root = Path(args.repo_root).resolve()
    ueber = Path(args.uebernahme).resolve() if args.uebernahme else fall / "abgeleitet" / "bestand"
    eingaben: Dict[str, Path] = {}

    def lies(pfad: Path, spalten, pflicht: bool):
        if not pfad.is_file():
            if pflicht:
                raise SystemExit(f"fuehrungsprobe: Pflichttabelle fehlt: {pfad}")
            return None
        eingaben[str(pfad.relative_to(fall))] = pfad
        return read_portfolio(pfad, expected_columns=spalten)

    try:
        uebernahme: Dict[str, Any] = {
            "bestand": lies(ueber / "bestand.parquet", STAMM_NAMES, True),
            "historie": lies(ueber / "historie.parquet", STATUS_HISTORIE_NAMES, True),
            "ledger": lies(ueber / "ledger.parquet", LEDGER_NAMES, True),
            "scheiben": lies(ueber / "scheiben.parquet", SCHEIBEN_NAMES, False),
            "verankerung": lies(ueber / "verankerung.parquet", VERANKERUNG_NAMES, False),
            "schichten": lies(ueber / "schichten.parquet", SCHICHTEN_NAMES, False),
            "merkmale": lies(ueber / "merkmale.parquet", None, False),
        }
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        return 2
    beleg_pfad = ueber / "uebernahme.json"
    if not beleg_pfad.is_file():
        print(f"fuehrungsprobe: Uebernahmebeleg fehlt: {beleg_pfad} — der Bestand "
              "hat keinen benannten Anfangszustand (gates.bestand_uebernehmen "
              "schreibt ihn)", file=sys.stderr)
        return 2
    eingaben[str(beleg_pfad.relative_to(fall))] = beleg_pfad
    uebernahme["beleg"] = json.loads(beleg_pfad.read_text(encoding="utf-8"))

    fortschreibung = None
    if args.fortschreibung:
        lauf = Path(args.fortschreibung).resolve()
        try:
            fortschreibung = {
                "ledger": lies(lauf / "ledger.parquet", LEDGER_NAMES, True),
                "scheiben": lies(lauf / "scheiben.parquet", SCHEIBEN_NAMES, False),
                "historie": lies(lauf / "historie.parquet", STATUS_HISTORIE_NAMES, False),
            }
            lies(lauf / "bestand_gesamt.parquet", STAMM_NAMES, False)
        except SystemExit as exc:
            print(str(exc), file=sys.stderr)
            return 2

    config_pfad = Path(args.config).resolve()
    config = load_config(config_pfad)
    fehler = config.validate()
    if fehler:
        print("fuehrungsprobe: Config ungueltig: " + "; ".join(fehler), file=sys.stderr)
        return 2
    eingaben["config"] = config_pfad
    spez = lade_spez(fall, args.generation)
    zeilen_pfad = Path(args.zeilen).resolve()
    zeilen = json.loads(zeilen_pfad.read_text(encoding="utf-8"))
    if not isinstance(zeilen, list):
        print(f"{args.zeilen}: erwartet wird die Zeilenliste aus "
              "gates.transformation_anwenden --zeilen", file=sys.stderr)
        return 2
    eingaben["zeilen"] = zeilen_pfad
    vorgeschichte = _lies_csv(fall, args.vorgeschichte) if args.vorgeschichte else []
    if args.vorgeschichte:
        eingaben["vorgeschichte"] = fall_mod.eingang_datei(fall, args.vorgeschichte)

    red_anteile: Dict[str, float] = {}
    red_anteile_je_datum: Dict[str, Dict[str, float]] = {}
    if args.red_anteile_datei is not None:
        for zeile in _lies_csv(fall, args.red_anteile_datei):
            if zeile.get("GEVO") == "RED" and zeile.get("ANTEIL"):
                red_anteile[str(zeile["POLNR"])] = float(zeile["ANTEIL"])
                if zeile.get("DATUM"):
                    red_anteile_je_datum.setdefault(
                        str(zeile["POLNR"]), {})[str(zeile["DATUM"])] = float(zeile["ANTEIL"])
    for eintrag in args.red_anteile:
        police, _, wert = eintrag.partition("=")
        if not police or not wert:
            print(f"--red-anteil {eintrag!r}: erwartet POLNR=ANTEIL", file=sys.stderr)
            return 2
        red_anteile[police.strip()] = float(wert)
    anker: Dict[str, Tuple[int, float]] = {}
    if args.anker_quelle is not None:
        quelle_pfad = fall_mod.eingang_datei(fall, args.anker_quelle)
        eingaben["anker_erwartungswerte"] = quelle_pfad
        quelle = json.loads(quelle_pfad.read_text(encoding="utf-8"))
        for eintrag in quelle.get("vertraege", []):
            erster = next(
                (x for x in (eintrag.get("punkte") or [])
                 if x.get("anlass") == "uebernahme"
                 and "kVx_MRV" in (x.get("erwartet") or {})), None)
            if erster:
                anker[str(eintrag["police_id"])] = (
                    int(erster["monate"]), float(erster["erwartet"]["kVx_MRV"]))

    schichtbeleg = None
    if args.schicht:
        from rechner_pipeline.gates.aktuartest_lauf import _schichten

        roh = _schichten(fall, args.schicht, repo_root=repo_root)
        schichtbeleg = {
            police: {k: (v.als_beleg() if hasattr(v, "als_beleg") else v)
                     for k, v in eintrag.items()}
            for police, eintrag in roh.items()
        }
        schicht_pfad = (fall / args.schicht) if not Path(args.schicht).is_absolute() \
            else Path(args.schicht)
        if schicht_pfad.is_file():
            eingaben["schicht"] = schicht_pfad

    tarifwerk = {
        "scheiben_mit_gamma1": bool(args.scheiben_mit_gamma1),
        "stoab_je_baustein": bool(args.stoab_je_baustein),
        "red_verfahren": str(args.red_verfahren),
    }
    ergebnis = pruefe_fuehrung(
        uebernahme=uebernahme, fortschreibung=fortschreibung, config=config,
        spez=spez, zeilen=zeilen, vorgeschichte=vorgeschichte,
        tarifwerk=tarifwerk, erhoehungssatz=args.erhoehungssatz,
        red_anteile=red_anteile, red_anteile_je_datum=red_anteile_je_datum,
        red_anteil_kandidaten=tuple(args.red_anteil_kandidaten), anker=anker,
        schichtbeleg=schichtbeleg, stichtag=dt.date.fromisoformat(args.stichtag),
    )
    ergebnis["system"] = systemstand(repo_root)
    ergebnis["provenienz"] = {
        "eingaben": {
            (str(pfad.relative_to(fall)) if fall in pfad.parents else name): _sha256(pfad)
            for name, pfad in sorted(eingaben.items())
        },
        "parameter": {
            "generation": args.generation, "erhoehungssatz": args.erhoehungssatz,
            "red_anteile": sorted(args.red_anteile),
            "red_anteil_kandidaten": sorted(args.red_anteil_kandidaten),
            "anker_erwartungswerte": args.anker_quelle,
            "vorgeschichte": args.vorgeschichte, "schicht": args.schicht,
            "uebernahme": str(ueber.relative_to(fall)) if fall in ueber.parents else str(ueber),
            "fortschreibung": args.fortschreibung,
        },
    }
    out = Path(args.out) if args.out else fall / "abgeleitet" / "berichte" / "fuehrungsprobe.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"fuehrungsprobe: {ergebnis['vertraege']} Vertraege, "
          f"{ergebnis['mit_anfangszustand']} mit Anfangszustand, "
          f"{sum(ergebnis['buchungen_geprueft'].values())} Buchungen geprueft, "
          f"{len(ergebnis['befunde'])} Befunde -> {out}")
    for b in ergebnis["befunde"][:20]:
        print(f"  BEFUND {b['police_id'] or '-'} {b['art']}: {b['text']}", file=sys.stderr)
    return 0 if ergebnis["bestanden"] else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
