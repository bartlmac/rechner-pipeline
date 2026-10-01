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

import dataclasses
import datetime as _dt
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.fuehrung import bestand_am, months_between
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.bestand.schichten import schichten_je_police
from rechner_pipeline.kern.vorgangsfolge import (
    Vertragsstand,
    Vorgangsfolge,
    vorgang,
)
from rechner_pipeline.kern.korrekturschicht import (
    ab_verankerung,
    absorbierter_wert,
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.kern import ModelPoint, Rechenkern, vertrags_monatsreserve
from rechner_pipeline.models.bestand import (
    FUEHRUNGSKONVENTION,
    KONVENTION_JE_PRODUKT,
    KONVENTION_MONATSGENAU,
    STATUS_HISTORIE_SPALTEN,
    bu_model_point_kwargs,
    model_point_kwargs,
)


def monate_ta_von(schicht: Tuple[Any, int, str]) -> int:
    """Der Verankerungszeitpunkt einer Schicht in Vertragsmonaten."""
    return int(schicht[1])


def monatsgenau_fuer(konvention: str, produkt: str) -> bool:
    """Ob die Konvention fuer dieses Produkt unterjaehrig mischt.

    Die Regel steht je Produkt in ``models.bestand.KONVENTION_JE_PRODUKT``;
    eine unbekannte Konvention ist ein Aufruffehler, kein Rueckfall.
    """
    regel = KONVENTION_JE_PRODUKT.get(konvention)
    if regel is None:
        raise ValueError(
            f"Bewertungskonvention {konvention!r} unbekannt (bekannt: "
            f"{sorted(KONVENTION_JE_PRODUKT)})")
    return regel[produkt] == KONVENTION_MONATSGENAU


def vertragswerte(
    kern: Rechenkern, months_exp: int, pex_jahr: Optional[int] = None,
    *, monatsgenau: bool,
) -> Dict[str, Any]:
    """Aktuarielle Werte eines Vertrags am Stichtag (``months_exp`` volle Monate).

    ``pex_jahr`` ist das Vertragsjahr der Beitragsfreistellung (None =
    beitragspflichtig). Rueckkaufswert nur auf dem beitragspflichtigen Track;
    fuer beitragsfreie Vertraege ist er 0.0 (im Blatt nicht definiert).

    ``monatsgenau`` (seit 2026-10-01 die Fuehrungskonvention): die
    unterjaehrige Mischung des Kerns (``monatsreserve`` bzw.
    ``monatsreserve_beitragsfrei``); sonst die Zeile des angebrochenen
    Vertragsjahres, wie der Abschluss vor der Umstellung rechnete — dieser
    Zweig bleibt wortgleich, damit alte Abschluesse in ihrer Konvention
    bit-genau nachgerechnet werden.
    """
    jahr = int(months_exp) // 12
    if pex_jahr is None:
        if monatsgenau:
            reserve = kern.monatsreserve(int(months_exp))
            return {
                "jahr": jahr,
                "status": "POL",
                "deckungskapital": reserve.drx_bpfl,
                "rueckkaufswert": reserve.rkw,
                "vs_bfr": 0.0,
            }
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
        "deckungskapital": (
            kern.monatsreserve_beitragsfrei(pex_jahr, int(months_exp)) if monatsgenau
            else kern.reserve_beitragsfrei(pex_jahr, jahr)),
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


def werte_nach_vorgaengen(
    folge: Vorgangsfolge, months_exp: int, *, monatsgenau: bool,
) -> Dict[str, Any]:
    """Aktuarielle Werte eines Vertrags MIT Vorgaengen am Stichtag.

    Spiegel von :func:`vertragswerte`: der Zustand der Vorgangsfolge am
    Bewertungsmonat (``kern.vorgangsfolge`` — dieselbe Folge, die Engine,
    P-B1 und Fuehrungsprobe lesen). WO der Stornoabschlag greift, sagt das
    Tarifwerk der Generation (T27-12), und ob die Teilkuendigung jeden
    Baustein trifft, ebenso; beides traegt die Folge.

    Dieselbe Stichtagskonvention wie fuer jeden anderen Vertrag
    (Kalibrierungsfund N5 und Fund N11 der Pruefrunde T27). Der
    Bewertungsmonat ist unter ``monatsgenau`` der Stichtag selbst, sonst der
    letzte Vertragsjahrestag — beide lesen dieselben Kern-Funktionen, die
    zwischen den Jahrestagen linear mischen und auf ihnen die Jahreszeile
    treffen. Der Rueckkaufswert eines beitragsfreien Vertrags steht hier wie
    fuer jeden beitragsfreien Vertrag mit null im Ausweis (Stufe 1); die
    Teilkuendigung rechnet ihn (Entscheid B3 vom 2026-10-01).
    """
    jahr = int(months_exp) // 12
    monat = int(months_exp) if monatsgenau else 12 * jahr
    stand = folge.stand_am(monat)
    werte = stand.werte(monat)
    beitragsfrei = werte["status"] == "PEX"
    return {
        "jahr": jahr, "status": werte["status"],
        "deckungskapital": werte["deckungskapital"],
        "rueckkaufswert": 0.0 if beitragsfrei else werte["rueckkaufswert"],
        "korrekturschicht": werte["korrekturschicht"],
        "vs_bfr": werte["vs_bfr"] if beitragsfrei else 0.0,
        "leistung": werte["leistung"],
        "stand": stand,
    }


def beitraege_nach_vorgaengen(stand: Vertragsstand, jahr: int) -> Dict[str, float]:
    """Beitraege eines Vertrags mit Vorgaengen — KOMPONENTENWEISE.

    Jeder Baustein zahlt den Beitrag seines fortgefuehrten Teils (Summe
    ``c x S_i`` des Zustands, ``Baustein.beitragskern``): Herabsetzungen
    senken den Faktor c, Teilkuendigungen die wirksame Summe. Die
    Stueckkosten sind je Baustein fix und werden NICHT mit der Summe
    skaliert (Pruefrunde T27, Befund 13; Annahme B4). Der Beitrag ist der
    eines gewoehnlichen Kerns mit dieser Summe — kein zweiter Rechenweg.
    Nach der Beitragsfreistellung zahlt der Vertrag nichts.
    """
    aus = {"bjb": 0.0, "bzb_jahr": 0.0}
    for erh_jahr, kern in stand.beitragskerne(12 * int(jahr)):
        bt = beitraege(kern, int(jahr) - int(erh_jahr))
        aus = {n: aus[n] + bt[n] for n in aus}
    return aus


def pex_jahr_je_police(stamm: pd.DataFrame, historie: Optional[pd.DataFrame]) -> Dict[int, int]:
    """Das Vertragsjahr der Beitragsfreistellung je Police — aus der
    Statushistorie (erste PEX-Zeile), wie die Bewertung es am Stichtag aus
    der Zustandszeile liest."""
    if historie is None or len(historie) == 0:
        return {}
    pex = historie[historie["status_code"] == "PEX"]
    if len(pex) == 0:
        return {}
    beginn = stamm.set_index("police_id")["insurance_start"]
    aus: Dict[int, int] = {}
    for pid, datum in zip(pex["police_id"], pex["status_date"]):
        pid = int(pid)
        if pid not in beginn.index:
            continue
        j = months_between(pd.Timestamp(beginn.loc[pid]).date(),
                           pd.Timestamp(datum).date()) // 12
        aus[pid] = min(j, aus.get(pid, j))
    return aus


def _vorgangsfolgen(
    reduktionen: Optional[pd.DataFrame],
    kerne: Dict[int, Rechenkern],
    scheiben_je_police: Dict[int, List[Dict[str, Any]]],
    schicht_je_police: Dict[int, Any],
    tarifwerk_je_police: Mapping[int, Mapping[str, Any]],
    pex_je_police: Optional[Mapping[int, int]] = None,
) -> Dict[int, Vorgangsfolge]:
    """Je Police mit Vorgaengen ihre Vorgangsfolge.

    Der Kern rekonstruiert den Vertrag aus der FOLGE der Zeilen (Jahr,
    Anteil, Verfahren), den Scheiben, der Beitragsfreistellung und der
    Korrekturschicht — dieselbe Klasse wie in der Ereignis-Engine
    (``kern.vorgangsfolge``). Zwei Rechenwege waeren zwei Ergebnisse. Das
    Tarifwerk (Abzug je Baustein, Umfang der Teilkuendigung) ist das der
    Generation der Police, ohne Default (Runde D).
    """
    if reduktionen is None or len(reduktionen) == 0:
        return {}
    je_police: Dict[int, List[Any]] = {}
    for zeile in reduktionen.to_dict("records"):
        je_police.setdefault(int(zeile["police_id"]), []).append(vorgang(
            int(zeile["reduktion_jahr"]), float(zeile["anteil"]),
            str(zeile["verfahren"])))
    aus: Dict[int, Vorgangsfolge] = {}
    for pid, vorgaenge in sorted(je_police.items()):
        if pid not in kerne:
            continue
        tw = tarifwerk_je_police[pid]
        aus[pid] = Vorgangsfolge(
            kerne[pid],
            [(int(sch["erh_jahr"]), sch["kern"])
             for sch in scheiben_je_police.get(pid, ())],
            vorgaenge,
            pex_jahr=(pex_je_police or {}).get(pid),
            schicht=(schicht_je_police[pid][:2] if pid in schicht_je_police else None),
            stoab_je_baustein=bool(tw["stoab_je_baustein"]),
            tku_umfang=str(tw["tku_umfang"]))
    return aus


def _absorbiert_monatsgenau(
    schicht: Tuple[Any, int, str], grund: Rechenkern, pex_jahr: int, monate: int,
) -> float:
    """Der in die beitragsfreie Summe ueberfuehrte Schichtwert am Monatsstichtag.

    Der Kern fuehrt ihn je Vertragsjahr (``absorbierter_wert``): proportional
    zur beitragsfreien Reserve. Unterjaehrig gilt dieselbe Mischung wie fuer
    die Reserve selbst — linear zwischen den beiden Jahrestagen; weil der Wert
    linear in der Reserve ist, ist das genau der Anteil an
    ``monatsreserve_beitragsfrei`` (Kontrollrechnung im Test). Keine eigene
    Formel: zwei Kernwerte, mit dem Monatsanteil des Kerns gemischt.
    """
    parameter, monate_ta = schicht[0], int(schicht[1])
    jahr, rest = divmod(int(monate), 12)
    wert = absorbierter_wert(parameter, monate_ta, grund, pex_jahr, jahr)
    if not rest:
        return wert
    u = rest / 12.0
    return (1.0 - u) * wert + u * absorbierter_wert(
        parameter, monate_ta, grund, pex_jahr, jahr + 1)


def _klv_monatsgenau(
    grund: Rechenkern,
    aktive: List[Dict[str, Any]],
    monate: int,
    pex_jahr: Optional[int],
    schicht: Optional[Tuple[Any, int, str]],
    *,
    stoab_je_baustein: bool,
) -> Dict[str, Any]:
    """Bewertungsgroessen eines nicht herabgesetzten KLV-Vertrags, monatsgenau.

    EIN Weg fuer den gewoehnlichen Vertrag, den mit Erhoehungsscheiben und
    den beitragsfreien: die vertragsweite Monatsreserve des Kerns
    (``vertrags_monatsreserve`` — ohne Scheiben identisch zu
    ``Rechenkern.monatsreserve``; Stornoabschlag je Vertrag oder je Baustein
    nach dem Tarifwerk der Generation), nach einer Beitragsfreistellung die
    beitragsfreie Monatsreserve je Baustein. Die Korrekturschicht mischt der
    Kern ohnehin monatsgenau (``schichtwert_bei``); ihr ueberfuehrter Wert
    nach einer Freistellung folgt derselben Mischung
    (:func:`_absorbiert_monatsgenau`). Die Regeln, WANN die Schicht traegt und
    ob eine Freistellung sie ueberfuehrt, sind die der Jahreszeile darunter.
    """
    scheiben = [(int(s["erh_jahr"]), s["kern"]) for s in aktive]
    korr = 0.0
    traegt = schicht_traegt(schicht, int(monate))
    if pex_jahr is None:
        reserve = vertrags_monatsreserve(
            grund, scheiben, int(monate), stoab_je_baustein=stoab_je_baustein)
        dk, rkw = reserve.drx_bpfl, reserve.rkw
        if traegt:
            korr = schichtwert_bei(schicht[0], int(schicht[1]), grund.mp, int(monate))
            dk += korr
            rkw += korr
        return {"status": "POL", "deckungskapital": dk, "rueckkaufswert": rkw,
                "korrekturschicht": korr, "vs_bfr": 0.0}
    dk = grund.monatsreserve_beitragsfrei(pex_jahr, int(monate))
    vs_bfr = grund.beitragsfreie_summe(pex_jahr)
    for erh_jahr, kern in scheiben:
        pex_s = pex_jahr - erh_jahr
        if pex_s <= 0:
            raise ValueError(
                f"Scheibe aus Vertragsjahr {erh_jahr} liegt nicht vor der "
                f"Beitragsfreistellung (Jahr {pex_jahr})")
        dk += kern.monatsreserve_beitragsfrei(pex_s, int(monate) - 12 * erh_jahr)
        vs_bfr += kern.beitragsfreie_summe(pex_s)
    if traegt:
        if ab_verankerung(int(schicht[1]), 12 * int(pex_jahr)):
            # Freistellung am oder nach dem Verankerungspunkt: wertstetig in
            # die beitragsfreie Summe ueberfuehrt (Entscheid 2026-09-15).
            vs_bfr += zuschlag_bei_pex(schicht, grund, pex_jahr)
            korr = _absorbiert_monatsgenau(schicht, grund, pex_jahr, int(monate))
        else:
            korr = schichtwert_bei(schicht[0], int(schicht[1]), grund.mp, int(monate))
        dk += korr
    return {"status": "PEX", "deckungskapital": dk, "rueckkaufswert": 0.0,
            "korrekturschicht": korr, "vs_bfr": vs_bfr}


def einzelwerte_am(
    stamm: pd.DataFrame,
    historie: Optional[pd.DataFrame],
    config: BestandConfig,
    stichtag: _dt.date,
    scheiben: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
    schichten: Optional[pd.DataFrame] = None,
    verankerung: Optional[pd.DataFrame] = None,
    reduktionen: Optional[pd.DataFrame] = None,
    *,
    konvention: str = FUEHRUNGSKONVENTION,
) -> List[Dict[str, Any]]:
    """Einzelvertragliche Bewertung des in-force-Bestands am Stichtag.

    ``konvention`` (``models.bestand.BEWERTUNGSKONVENTIONEN``) sagt, wie
    Deckungskapital, Rueckkaufswert und Korrekturschicht am Stichtag aus dem
    Kern gelesen werden. Die Fuehrung bewertet seit 2026-10-01 monatsgenau
    (Entscheid des Maintainers): linear zwischen den beiden Vertragsjahres-
    tagen, die den Stichtag einschliessen, fuer JEDEN Vertragstyp gleich —
    gewoehnlich, mit Scheiben, beitragsfrei, herabgesetzt, teilgekuendigt,
    mit Korrekturschicht. Die BU bleibt benannt bei der Jahreszeile
    (``KONVENTION_JE_PRODUKT``: der Kern fuehrt fuer sie keine unterjaehrige
    Reserve). ``jahreszeile`` rechnet wortgleich wie vor der Umstellung —
    nur, um einen alten Abschluss in SEINER Konvention nachzurechnen.

    ``schichten``/``verankerung`` (Freischaltung, Schritt 5): die
    Korrekturschicht uebernommener Vertraege geht als eigene Position
    ``korrekturschicht`` in die Zeile ein und ist in ``deckungskapital``
    und ``rueckkaufswert`` enthalten (Grundsatzdokumentation 9.11: nie
    unsichtbar). Eine Beitragsfreistellung NACH der Verankerung hat sie
    WERTSTETIG in die beitragsfreie Summe ueberfuehrt (Klasse A; der
    ueberfuehrte Betrag bleibt ausgewiesen); eine Freistellung VOR t_a
    ist ihr Verankerungszustand, dort laeuft sie auf dem beitragsfreien
    Track.

    ``reduktionen`` sind die Herabsetzungen je Police: Ab dem
    Reduktionsjahr rechnet der Vertrag ueber seinen geknickten Verlauf
    (``kern.beitragsreduktion.ReduzierterVertrag``), und eine
    Korrekturschicht hat er nicht mehr — sie ist in die Neuberechnung
    eingegangen (Entscheid des Maintainers 2026-09-15). Ohne die Tabelle
    bewertete die Fuehrung einen herabgesetzten Vertrag wie einen
    ungekuerzten: zu hohe Summe, zu hoher Beitrag.

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
    klv_monatsgenau = monatsgenau_fuer(konvention, "klv")
    if monatsgenau_fuer(konvention, "bu"):  # pragma: no cover - Vertrag in models
        raise ValueError(
            f"Konvention {konvention!r} verlangt eine unterjaehrige BU-Reserve — der Kern "
            "fuehrt keine (kern.produkte.bu kennt nur Vertragsjahre)")
    if historie is None or len(historie) == 0:
        # Eine LEERE Historie ist keine Historie: sie ist ein DataFrame und
        # passierte den Wachposten, der nur auf None sah — derselbe Verlust
        # des gefuehrten Zustands, nur unsichtbar.
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
    tarifwerk_je_generation = {g.name: g.tarifwerk() for g in config.generationen}
    schicht_je_police = schichten_je_police(stamm, schichten, verankerung)
    folge_je_police = _vorgangsfolgen(
        reduktionen, kerne, scheiben_je_police, schicht_je_police,
        # Das Tarifwerk ist Eigenschaft der Generation der Police (Runde D):
        # dieselbe Regel wie die Engine beim Ziehen.
        {int(pid): tarifwerk_je_generation[str(generation_je_police.loc[int(pid)])]
         for pid in (reduktionen["police_id"] if reduktionen is not None else ())
         if int(pid) in generation_je_police.index},
        pex_jahr_je_police(stamm, journal))

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
            "korrekturschicht": 0.0,
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
        # Ein Vertrag mit Herabsetzungen oder Teilkuendigungen rechnet ueber
        # seine Vorgangsfolge: EIN Vertrag, alle Bausteine darin, der Zustand
        # nach allen Vorgaengen bis zum Stichtag. Deshalb ein eigener Zweig
        # statt eines Zuschlags auf die ungekuerzte Rechnung — und deshalb
        # weder Scheiben-Schleife noch Schicht-Position darunter: Beides
        # steckt schon im Zustand.
        folge = folge_je_police.get(pid)
        if folge is not None and int(months_exp) < 12 * folge.erstes_jahr:
            # Vor dem Jahrestag des ersten Vorgangs gilt der ungekuerzte
            # Vertrag — ein Stichtag davor rechnet den alten Verlauf.
            folge = None
        if folge is not None:
            werte = werte_nach_vorgaengen(
                folge, int(months_exp), monatsgenau=klv_monatsgenau)
            if (werte["status"] == "PEX") != (pex_jahr is not None):
                raise ValueError(
                    f"police {pid}: die Zustandszeile am {stichtag} sagt "
                    f"{status!r}, die Vorgangsfolge "
                    f"{werte['status']!r} — Statushistorie und Folge erzaehlen "
                    "verschiedene Geschichten")
            zeile["leistung"] = werte["leistung"]
            if pex_jahr is None:
                bt = beitraege_nach_vorgaengen(werte["stand"], int(months_exp) // 12)
                zeile["jahresbeitrag"] = bt["bjb"]
                zeile["bzb_jahr"] = bt["bzb_jahr"]
            zeile["status"] = werte["status"]
            zeile["deckungskapital"] = werte["deckungskapital"]
            zeile["rueckkaufswert"] = werte["rueckkaufswert"]
            zeile["korrekturschicht"] = werte["korrekturschicht"]
            zeile["vs_bfr"] = werte["vs_bfr"]
            zeilen.append(zeile)
            continue
        stoab_je_baustein = bool(tarifwerk_je_generation[
            str(generation_je_police.loc[pid])]["stoab_je_baustein"])
        # Erhoehungsscheiben des Vertrags, die am Stichtag existieren —
        # jede mit ihrem Jahresversatz (PEX-Jahr entsprechend versetzt).
        aktive = [
            s for s in scheiben_je_police.get(pid, ())
            if s["erh_datum"].date() <= stichtag
        ]
        if klv_monatsgenau:
            zeile.update(_klv_monatsgenau(
                kerne[pid], aktive, int(months_exp), pex_jahr,
                schicht_je_police.get(pid), stoab_je_baustein=stoab_je_baustein))
            # Beitraege und Leistung haengen nicht an der Konvention: derselbe
            # Weg in derselben Reihenfolge wie unten.
            jahr = int(months_exp) // 12
            if pex_jahr is None:
                bt = beitraege(kerne[pid], jahr)
                zeile["jahresbeitrag"] += bt["bjb"]
                zeile["bzb_jahr"] += bt["bzb_jahr"]
            for s in aktive:
                if pex_jahr is None:
                    bt = beitraege(s["kern"], jahr - s["erh_jahr"])
                    zeile["jahresbeitrag"] += bt["bjb"]
                    zeile["bzb_jahr"] += bt["bzb_jahr"]
                zeile["leistung"] += float(s["kern"].mp.sum_insured)
            zeilen.append(zeile)
            continue
        # --- Jahreszeile: wortgleich wie vor der Umstellung (2026-10-01) ---
        werte = vertragswerte(kerne[pid], int(months_exp), pex_jahr, monatsgenau=False)
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
            # Wo die Stornoabschlag-Grenzen greifen, sagt das Tarifwerk
            # der Generation (je Vertrag, oder je Baustein bei einer
            # uebernommenen Generation) — derselbe Weg wie in der Engine.
            werte["rueckkaufswert"] = vertrags_rkw(
                kerne[pid], [(s["erh_jahr"], s["kern"]) for s in aktive], jahr,
                stoab_je_baustein=bool(tarifwerk_je_generation[
                    str(generation_je_police.loc[pid])]["stoab_je_baustein"]),
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
        schicht = schicht_je_police.get(pid)
        if schicht is not None and int(months_exp) >= monate_ta_von(schicht):
            parameter, monate_ta, _zustand_ta = schicht
            # Zwei Wege, je nachdem, WANN die Beitragsfreistellung liegt.
            #
            # Ist sie der Verankerungszustand selbst, laeuft die Schicht auf
            # dem beitragsfreien Track als eigene Position weiter — wie bei
            # einem beitragspflichtigen Vertrag auch.
            #
            # Liegt sie NACH der Verankerung, hat sie die Schicht wertstetig
            # in die beitragsfreie Summe ueberfuehrt (Entscheid des
            # Maintainers 2026-09-15): Die beitragsfreie Summe ist eine
            # garantierte Leistung, die Umwandlung muss werthaltend sein.
            # Vorher liess die Bewertung den Schichtwert an dieser Naht
            # ersatzlos fallen — das Deckungskapital sprang ohne
            # Gegenbuchung nach unten.
            #
            # Der ueberfuehrte Betrag steckt danach IN vs_bfr und damit im
            # Deckungskapital; ausgewiesen wird er trotzdem weiter
            # (Grundsatzdokumentation 9.11: nie unsichtbar im
            # Deckungskapital), nur eben als ueberfuehrter Wert.
            # Der Fakt, an dem beide Zweige haengen, ist die ZEIT: Lag die
            # Freistellung am oder nach dem Verankerungspunkt? Genau
            # danach entscheidet auch die Rechnung (zuschlag_bei_pex).
            # ``zustand_ta`` sagt in stimmigen Daten dasselbe — aber die
            # Entscheidung aus einem anderen Fakt zu ziehen als die
            # Rechnung ist der Weg, auf dem die beiden auseinanderlaufen.
            absorbiert = (
                werte["status"] == "PEX"
                and pex_jahr is not None
                and 12 * int(pex_jahr) >= monate_ta
            )
            if absorbiert:
                werte["vs_bfr"] += zuschlag_bei_pex(
                    schicht, kerne[pid], pex_jahr)
                ueberfuehrt = absorbierter_wert(
                    parameter, monate_ta, kerne[pid], pex_jahr,
                    int(months_exp) // 12)
                zeile["korrekturschicht"] = ueberfuehrt
                werte["deckungskapital"] += ueberfuehrt
            else:
                korr = schichtwert_bei(
                    parameter, monate_ta, kerne[pid].mp, int(months_exp))
                zeile["korrekturschicht"] = korr
                werte["deckungskapital"] += korr
                werte["rueckkaufswert"] += korr
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
    schichten: Optional[pd.DataFrame] = None,
    verankerung: Optional[pd.DataFrame] = None,
    reduktionen: Optional[pd.DataFrame] = None,
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
                                scheiben=scheiben, merkmale=merkmale,
                                schichten=schichten, verankerung=verankerung,
                                reduktionen=reduktionen)
        agg: Dict[str, Any] = {
            "stichtag": stichtag.isoformat(),
            "vertraege": int(len(zeilen)),
            "deckungskapital": 0.0,
            # Anteil der Korrekturschicht uebernommener Vertraege am
            # Deckungskapital — im Abschluss eine eigene Position (9.11),
            # hier ebenso, damit ein Bericht MIT Schicht nicht nur andere
            # Kurven zeigt, sondern sagt, woher (N-01).
            "korrekturschicht": 0.0,
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
            # Die GEFUEHRTE Versicherungssumme (KLV): nach Herabsetzungen
            # und Erhoehungen, nicht die Stammspalte.
            "vs_klv": 0.0,
        }
        for z in zeilen:
            agg["deckungskapital"] += z["deckungskapital"]
            agg["korrekturschicht"] += z["korrekturschicht"]
            if z["produkt"] == "klv":
                agg["vs_klv"] += z["leistung"]
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
