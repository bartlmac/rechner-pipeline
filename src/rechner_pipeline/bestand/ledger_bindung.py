"""Jede Buchung folgt aus ihrer Police und dem Kern — policenweise (T20-04).

Der Ledger ist definiert als "one row per booked event with its
kernel-computed amount". ``validate_ledger`` (models.bestand) prueft
Form und Semantik jeder Zeile und bindet ERH-Buchungen zeilenweise an
die Scheiben. Was dort fehlte (externes Review T20-04): Fuer STO, PEX,
TOD, ABL und ZUG wurde nicht geprueft, ob der BETRAG fuer genau diese
Police aus dem Kern folgt. Zwei Stornobetraege desselben Jahres,
zwischen zwei Policen vertauscht — Code, Betragsart, Datum, Generation,
Zeilenzahl und Jahressumme unveraendert — passierten P-B1 mit null
Befunden; das Bewegungskonto sieht nur Jahressummen. Aggregatgleichheit
ersetzt keine Buchungsidentitaet.

Hier wird jede Buchung mit gerechnetem Betrag gegen dieselbe
Kern-Herleitung gestellt, mit der die Ereignis-Engine sie erzeugt hat
(:mod:`rechner_pipeline.bestand.ereignisse`): Rueckkaufswert,
beitragsfreie Summe, Todesfall- und Ablaufleistung des Vertrags im
gebuchten Vertragsjahr, ueber Grundscheibe und die bis dahin bestehenden
Erhoehungsscheiben. Ein Betrag, der zu einer anderen Police gehoert,
faellt daran — unabhaengig davon, ob die Jahressumme aufgeht.

Bewusste Grenzen: ``MIG`` (Residuum der Uebernahme) und ``RED``
(Herabsetzung, von der Engine nicht erzeugt) werden nicht hergeleitet;
``ERH`` ist ueber die Scheiben gebunden. Beim BU-Beispielprodukt folgt der
Betrag eines Todes- oder Ablaufereignisses aus dem ZUSTAND unmittelbar
davor (Review T21-01): im Leistungsbezug die Jahresrente, als Anwaerter
null — hergeleitet aus der geordneten Statushistorie, nicht aus dem zu
pruefenden Betrag. Vorher genuegte "null oder Rente", und zwei
BU-Ablaeufe gleicher Rente liessen sich zwischen einer aktiven und einer
invaliden Police tauschen.

Knoten: klv, bu
"""

from __future__ import annotations

import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from rechner_pipeline.bestand.auswertung import grundlagen_je_police
from rechner_pipeline.bestand.config import BestandConfig
from rechner_pipeline.bestand.kernlauf import vertrags_rkw
from rechner_pipeline.kern import ModelPoint, Rechenkern, erhoehungs_scheibe
from rechner_pipeline.bestand.schichten import schichten_je_police
from rechner_pipeline.kern.beitragsreduktion import (
    TEILKUENDIGUNG,
    absorbierte_schicht,
    reduzierte_teile,
    vertrags_monatsreserve_reduziert,
)
from rechner_pipeline.kern.korrekturschicht import (
    schicht_traegt,
    schichtwert_bei,
    zuschlag_bei_pex,
)
from rechner_pipeline.models.bestand import (
    model_point_kwargs,
    red_bindung_fehler,
    red_sollbuchungen,
    red_vollstaendigkeit_fehler,
    unbelegte_ereignisse,
    unbelegte_ereignisse_text,
    unzugeordnete_ereignisse,
)

#: Cent-Toleranz: Der Kern schreibt Buchung und Herleitung aus demselben
#: Wert; eine Lieferung darf auf Cent gerundet haben. Ein vertauschter
#: Betrag liegt Groessenordnungen darueber.
TOLERANZ = 0.005

#: Ereignisse, deren Betrag hier hergeleitet wird (KLV).
HERGELEITET = ("ZUG", "STO", "PEX", "TOD", "ABL", "ERH", "RED")
#: Betragsart des gebuchten Bruttojahresbeitrags. Er folgt aus dem Kern
#: derselben Police (VS mal Bxt) — deshalb wird er hergeleitet wie jeder
#: andere Betrag, nicht geglaubt. Ohne die Unterscheidung nach Art haette
#: die Herleitung den Beitrag gegen die Versicherungssumme gehalten.
BJB_ART = "BJB"


def _bjb_aus(kern: Rechenkern) -> float:
    """Der tarifliche Bruttojahresbeitrag einer Scheibe im Jahr ihres Zugangs.

    Dieselbe Groesse, die Engine und Bewertung fuehren: VS mal Bxt, null
    ohne laufende Beitragszahlungsdauer.
    """
    if kern.mp.t <= 0:
        return 0.0
    return float(kern.gross_annual_premium())


def _vollendete_jahre(start: pd.Timestamp, datum: pd.Timestamp) -> int:
    return ((datum.year * 12 + datum.month) - (start.year * 12 + start.month)) // 12


class _Herleitung:
    """Grundscheibe und Erhoehungsscheiben einer Police als Rechenkerne."""

    def __init__(self, row: Dict[str, Any], felder: Dict[str, Any],
                 scheiben: List[Tuple[int, float]],
                 tarifwerk: Optional[Dict[str, Any]] = None) -> None:
        self.grund_mp = ModelPoint(**model_point_kwargs(row, felder))
        self.grund = Rechenkern(self.grund_mp)
        self.tarifwerk = dict(tarifwerk or {
            "scheiben_mit_gamma1": False, "stoab_je_baustein": False})
        # Dieselbe Scheiben-Regel wie die Engine (erhoehungs_scheibe): Die
        # Scheibe ist aus Grundscheibe, Erhoehungsjahr und Summe
        # reproduzierbar; ob sie gamma1 traegt, sagt das Tarifwerk der
        # Generation (pruefe_scheiben_tarifwerk haelt die Scheibenzeile
        # dagegen).
        self.scheiben = [
            (jahr, vs, Rechenkern(erhoehungs_scheibe(
                self.grund_mp, jahr, vs,
                gamma1_uebernehmen=bool(self.tarifwerk["scheiben_mit_gamma1"]))))
            for jahr, vs in sorted(scheiben)
        ]
        self.reduktion: Optional[Tuple[int, float, str]] = None
        self.reduziert: List[Tuple[int, Any]] = []

    def setze_reduktion(self, jahr, anteil, verfahren, schicht) -> None:
        """Den herabgesetzten Verlauf setzen — dieselbe Rekonstruktion wie
        in der Engine und in der Bewertung (``kernlauf.reduzierte_teile``).
        Ein zweiter Rechenweg waere hier besonders schaedlich: Die
        Herleitung soll die Buchung WIDERLEGEN koennen, nicht sie
        nachplappern."""
        self.reduktion = (int(jahr), float(anteil), str(verfahren))
        self.reduziert = reduzierte_teile(
            self.grund, [(j, k) for j, _, k in self.scheiben],
            int(jahr), float(anteil), str(verfahren), schicht=schicht,
            stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"]))

    def _bis(self, jahr: int):
        # Die Engine bucht STO/PEX/TOD des Jahres j+1 VOR der Erhoehung
        # desselben Jahres: Es zaehlen die Scheiben mit Erhoehungsjahr < jahr.
        return [(j, vs, k) for j, vs, k in self.scheiben if j < jahr]

    def ist_reduziert(self, jahr: int) -> bool:
        return bool(self.reduziert) and jahr >= self.reduktion[0]

    def _reduziert_bis(self, jahr: int):
        # Wie _bis: STO/PEX/TOD/RED des Jahres stehen VOR der Erhoehung
        # desselben Jahres — es zaehlen Bausteine mit Erhoehungsjahr < jahr
        # (die Grundscheibe traegt 0).
        return [(e, v) for e, v in self.reduziert if e == 0 or e < jahr]

    def gesamt_vs(self, jahr: int) -> float:
        if self.ist_reduziert(jahr):
            return sum(v.reduktion.vs_neu for _, v in self._reduziert_bis(jahr))
        return self.grund_mp.sum_insured + sum(vs for _, vs, _ in self._bis(jahr))

    def rkw(self, jahr: int) -> float:
        if self.ist_reduziert(jahr):
            return vertrags_monatsreserve_reduziert(
                self._reduziert_bis(jahr), 12 * jahr,
                stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"])).rkw
        return vertrags_rkw(
            self.grund, [(j, k) for j, _, k in self._bis(jahr)], jahr,
            stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"]))

    def beitragsfreie_summe(self, jahr: int) -> float:
        if self.ist_reduziert(jahr):
            return sum(
                v.beitragsfreie_summe(jahr - erh_jahr)
                for erh_jahr, v in self._reduziert_bis(jahr))
        return self.grund.beitragsfreie_summe(jahr) + sum(
            k.beitragsfreie_summe(jahr - j) for j, _, k in self._bis(jahr)
        )


    def red_buchungen(self, schicht) -> Dict[str, float]:
        """Die Buchungen, die die registrierte Herabsetzung dieser Police im
        Ledger haben MUSS — Betragsart -> Betrag, hergeleitet wie in der
        Engine (``_Vertrag.herabsetzen``): die neue Gesamtsumme immer; die
        absorbierte Korrekturschicht, wenn eine traegt; bei der
        Teilkuendigung die Auszahlung des gekuendigten Grundanteils, wenn
        sie positiv ist (der Grund-Rueckkaufswert kann in fruehen Jahren
        null sein, dann bucht die Engine keine Zeile).

        EINE Menge fuer beide Richtungen: Jede RED-Zeile muss darin stehen,
        und jeder Eintrag muss genau einmal gebucht sein. Bisher prueften
        wir nur die Zeilen, die da waren — 28 Teilkuendigungen ohne eine
        einzige Auszahlung passierten mit leerer Fehlerliste (Pruefrunde
        T27, Befund 14).
        """
        if self.reduktion is None:
            return {}
        jahr, anteil, verfahren = self.reduktion
        absorbiert = absorbierte_schicht(self.grund, jahr, schicht)
        rechnerisch = None
        if verfahren == TEILKUENDIGUNG:
            rechnerisch = (1.0 - anteil) * vertrags_rkw(
                self.grund, [], jahr,
                stoab_je_baustein=bool(self.tarifwerk["stoab_je_baustein"]),
            ) + absorbiert
        return red_sollbuchungen(self.gesamt_vs(jahr), absorbiert, rechnerisch)


#: Zustaende, die eine Police beenden — eine Zeile mit diesem Code am
#: Ereignisdatum IST das Ereignis, nicht sein Vorzustand.
ENDZUSTAENDE = ("TOD", "ABL", "STO")


def zustand_vor(
    historie: Optional[pd.DataFrame], pid: int, datum: pd.Timestamp
) -> str:
    """Der Zustand einer Police unmittelbar VOR ihrem Ereignis an ``datum``.

    Aus der geordneten Statushistorie (status_date, status_id): die
    juengste Zeile bis einschliesslich ``datum``, wobei die Endzustands-
    Zeile desselben Datums (das Ereignis selbst) nicht zaehlt. Der Ledger
    traegt keine status_id, deshalb entscheidet der Code, nicht die
    Reihenfolge. Faellt eine Invalidisierung mit dem Ablauf auf dasselbe
    Datum (letztes Vertragsjahr), ist der Vorzustand des Ablaufs BU.
    Ohne Historie oder Zeile gilt der Ursprungszustand POL. Dieselbe
    Herleitung nutzt das Bewegungskonto (kennzahlen).
    """
    if historie is None or len(historie) == 0:
        return "POL"
    zeilen = historie[(historie["police_id"] == pid) & (historie["status_date"] <= datum)]
    zeilen = zeilen[~((zeilen["status_date"] == datum)
                      & zeilen["status_code"].isin(ENDZUSTAENDE))]
    if len(zeilen) == 0:
        return "POL"
    juengste = zeilen.sort_values(["status_date", "status_id"], kind="stable").iloc[-1]
    return str(juengste["status_code"])


def pruefe_ledger_betraege(
    stamm: pd.DataFrame,
    ledger: pd.DataFrame,
    config: BestandConfig,
    *,
    scheiben: Optional[pd.DataFrame] = None,
    historie: Optional[pd.DataFrame] = None,
    merkmale: Optional[pd.DataFrame] = None,
    schichten: Optional[pd.DataFrame] = None,
    verankerung: Optional[pd.DataFrame] = None,
    reduktionen: Optional[pd.DataFrame] = None,
) -> List[str]:
    """Betrag jeder Buchung gegen die Kern-Herleitung DIESER Police.

    ``schichten``/``verankerung`` (Freischaltung, Schritt 5): Storno
    eines uebernommenen Vertrags zahlt Basiswert plus Korrekturschicht —
    dieselbe Herleitung wie in der Engine.

    Rueckgabe: Fehlerliste (leer = jede hergeleitete Buchung stimmt).
    Voraussetzung ist ein formal gueltiger Ledger (``validate_ledger``);
    unbekannte Policen oder Generationen werden als Fehler gemeldet, nicht
    als Ausnahme.
    """
    errors: List[str] = []
    if len(ledger) == 0:
        return errors
    grundlagen = grundlagen_je_police(config, merkmale)
    tarifwerk_je_generation = {g.name: g.tarifwerk() for g in config.generationen}
    haupt = stamm.set_index("police_id")
    for feld, eintraege in sorted(unbelegte_ereignisse(
            stamm, ledger, config.annahmen,
            leistungsbezug=lambda pid, datum: zustand_vor(historie, pid, datum) == "BU",
    ).items()):
        errors.append(unbelegte_ereignisse_text(feld, eintraege))
    errors.extend(unzugeordnete_ereignisse(stamm, ledger))
    try:
        schicht_je_police = schichten_je_police(stamm, schichten, verankerung)
    except ValueError as exc:
        return [f"schichten: {exc}"]
    reduktion_je_police: Dict[int, Tuple[int, float, str]] = {}
    reduktion_datum: Dict[int, pd.Timestamp] = {}
    if reduktionen is not None and len(reduktionen):
        for z in reduktionen.to_dict("records"):
            reduktion_je_police[int(z["police_id"])] = (
                int(z["reduktion_jahr"]), float(z["anteil"]),
                str(z["verfahren"]))
            reduktion_datum[int(z["police_id"])] = pd.Timestamp(z["reduktion_datum"])
    # Verfahren und Anteil sind Eigenschaften des Systems, nicht der
    # Tabelle: das Verfahren steht im Tarifwerk der Generation, der Anteil
    # einer gerechneten Herabsetzung in den Annahmen (Angriffsrunde
    # 2026-09-26: eine als prospektiv eingetragene Teilkuendigung liess
    # Auszahlung und Kappung ohne Befund verschwinden).
    red_anteil = float(getattr(config.annahmen, "red_anteil", 0.0) or 0.0)
    # Die Rate, mit der die Engine zieht (Runde C RC05): ohne sie belegte ein
    # stehengebliebener red_anteil jede Herabsetzung.
    red_rate = float(config.annahmen.herabsetzung(0.0))
    for pid, (_jahr, anteil, verfahren) in sorted(reduktion_je_police.items()):
        if pid not in haupt.index:
            continue
        tw = tarifwerk_je_generation.get(str(haupt.loc[pid, "tarif_generation"])) or {}
        soll_verfahren = tw.get("red_verfahren")
        errors.extend(red_bindung_fehler(
            pid, anteil, verfahren, soll_verfahren, red_anteil, red_rate))

    scheiben_je_police: Dict[int, List[Tuple[int, float]]] = {}
    if scheiben is not None:
        for pid, jahr, vs in zip(scheiben["police_id"], scheiben["erhoehung_jahr"],
                                 scheiben["sum_insured"]):
            scheiben_je_police.setdefault(int(pid), []).append((int(jahr), float(vs)))

    # Beitragsfreistellung je Police: das Vertragsjahr, in dem die
    # beitragsfreie Summe fixiert wurde. Aus der Historie (auch die
    # Vorgeschichte eines uebernommenen Vertrags steht dort), sonst aus der
    # eigenen PEX-Buchung.
    pex_jahr: Dict[int, int] = {}
    if historie is not None and len(historie):
        pex = historie[historie["status_code"] == "PEX"]
        for pid, datum in zip(pex["police_id"], pex["status_date"]):
            pid = int(pid)
            if pid in haupt.index:
                j = _vollendete_jahre(haupt.loc[pid, "insurance_start"], datum)
                pex_jahr[pid] = min(j, pex_jahr.get(pid, j))
    for pid, jahr in zip(ledger.loc[ledger["ereignis"] == "PEX", "police_id"],
                         ledger.loc[ledger["ereignis"] == "PEX", "vertragsjahr"]):
        pex_jahr.setdefault(int(pid), int(jahr))

    # Eine Herabsetzung auf einem beitragsfreien Vertrag ist ein Widerspruch,
    # kein Vertrag, dessen Soll man aus der beitragspflichtigen Fassung
    # herleitet (Pruefrunde T27, Runde C, Befund RC03): Die Engine zieht fuer
    # beitragsfreie Vertraege keine Herabsetzung, und die Bewertung bricht
    # ab. Die Herleitung ignorierte pex_jahr und nahm eine Auszahlung vom
    # 4,6-fachen der beitragsfreien Reserve als Soll an. Jetzt wird der
    # Widerspruch gemeldet und fuer diese Police NICHTS hergeleitet, was auf
    # der Herabsetzung beruht (ab dem Reduktionsjahr ist der Vertrag
    # undefiniert).
    widerspruch: Dict[int, int] = {}
    for pid, (r_jahr, _anteil, verfahren) in sorted(reduktion_je_police.items()):
        p_jahr = pex_jahr.get(pid)
        if pid in haupt.index and p_jahr is not None and p_jahr <= r_jahr:
            widerspruch[pid] = r_jahr
            errors.append(
                f"reduktionen police {pid}: "
                f"{'Teilkuendigung' if verfahren == TEILKUENDIGUNG else 'Herabsetzung'} "
                f"im Jahr {r_jahr} auf einem beitragsfrei gestellten Vertrag "
                f"(Beitragsfreistellung im Jahr {p_jahr}) — die Engine zieht fuer "
                "beitragsfreie Vertraege keine Herabsetzung und die Bewertung bricht "
                "ab; ein Soll wird nicht hergeleitet. Ausweg: die Herabsetzung vor "
                "der Beitragsfreistellung registrieren oder die Buchung streichen")

    herleitungen: Dict[int, _Herleitung] = {}
    abweichungen: List[str] = []
    unbelegt: List[str] = []

    def _herleitung(pid: int, h: Any) -> Optional[_Herleitung]:
        """Grund- und Erhoehungsscheiben der Police als Rechenkerne, samt
        registrierter Herabsetzung — einmal je Police, fuer die Zeilen
        der Schleife und fuer die Vollstaendigkeitspruefung darunter."""
        if pid not in herleitungen:
            try:
                felder = grundlagen(pid, str(h["tarif_generation"]))
                herleitungen[pid] = _Herleitung(
                    h.to_dict() | {"police_id": pid}, felder,
                    scheiben_je_police.get(pid, []),
                    tarifwerk_je_generation.get(str(h["tarif_generation"])))
                if pid in reduktion_je_police:
                    herleitungen[pid].setze_reduktion(
                        *reduktion_je_police[pid],
                        schicht_je_police.get(pid))
            except (KeyError, ValueError) as exc:
                errors.append(f"ledger police {pid}: Kern nicht herleitbar: {exc}")
                return None
        return herleitungen[pid]

    for z in ledger.itertuples(index=False):
        pid = int(z.police_id)
        art = str(z.ereignis)
        if pid not in haupt.index:
            errors.append(f"ledger police {pid}: nicht im Stamm")
            continue
        h = haupt.loc[pid]
        produkt = str(h.get("produkt", "klv"))
        jahr = int(z.vertragsjahr)
        if pid in widerspruch and jahr >= widerspruch[pid]:
            continue                         # oben als Widerspruch gemeldet
        betrag = float(z.betrag)
        betrag_art = str(z.betrag_art)
        erwartet: Optional[float] = None
        if betrag_art == BJB_ART:
            # Ein Vorfall bewegt Summe UND Beitrag; die Zeilen tragen
            # dieselbe Police und denselben Tag, aber verschiedene Groessen.
            # Der Beitrag des Zugangs ist der der Grundscheibe, der Beitrag
            # einer Erhoehung der ihrer neuen Scheibe.
            if produkt == "bu":
                continue                     # BU-Beitrag: eigene Groesse, spaeter
            v = _herleitung(pid, h)
            if v is None:
                continue
            if art == "ZUG":
                erwartet = _bjb_aus(v.grund)
            else:
                scheibe = next((k for j, _, k in v.scheiben if j == jahr), None)
                if scheibe is None:
                    errors.append(
                        f"ledger police {pid}: ERH-Beitrag im Vertragsjahr {jahr} "
                        "ohne zugehoerige Scheibe"
                    )
                    continue
                erwartet = _bjb_aus(scheibe)
        elif produkt == "bu":
            rente = float(h["bu_rente"])
            if art in ("INV", "REA", "ZUG"):
                erwartet = rente
            elif art in ("TOD", "ABL"):
                # Der Zustand VOR dem Ereignis entscheidet, nicht der Betrag
                # (T21-01): Leistungsbezug -> Rente endet; Anwaerter -> 0.
                im_bezug = zustand_vor(historie, pid, z.status_date) == "BU"
                erwartet = rente if im_bezug else 0.0
            elif art == "RED":
                # Eine BU kennt keine Herabsetzung — eine RED-Zeile darauf ist
                # unbelegt, nicht "nicht hergeleitet" (vorher: still
                # uebersprungen und trotzdem als hergeleitet gezaehlt).
                unbelegt.append(f"police {pid} RED Jahr {jahr} {betrag_art} (Produkt bu)")
                continue
            else:
                continue
        else:
            if art == "ERH" and betrag_art == "VS_erhoehung" and str(
                    getattr(z, "betrag_herkunft", "")) == "gerechnet":
                # Die HOEHE einer gerechneten Erhoehung folgt aus der Regel
                # der Annahmen: erh_prozent der gefuehrten Summe davor —
                # auch nach einer Herabsetzung (dann der Summe danach).
                # Vorher leitete P-B1 nur den Beitrag der Scheibe her; eine
                # Erhoehung mit falschem Bezug (5 % der ungekuerzten Summe)
                # passierte, wenn Ledger und Scheibe zusammen falsch waren.
                v = _herleitung(pid, h)
                if v is None:
                    continue
                erwartet = float(config.annahmen.erh_prozent) * v.gesamt_vs(jahr)
                if abs(betrag - erwartet) > TOLERANZ:
                    abweichungen.append(
                        f"police {pid} ERH Jahr {jahr}: Ledger {betrag:.2f}, "
                        f"Regel {erwartet:.2f} (erh_prozent der gefuehrten Summe)")
                continue
            if art not in HERGELEITET or art == "ERH":
                continue                     # ERH: nur der Beitrag ist hergeleitet
            if art == "ZUG":
                # Der Zugang bucht die Versicherungssumme MIT den
                # mitgebrachten Bausteinen: Ein uebernommener Vertrag
                # tritt mit seinen Alt-Erhoehungen ein (Freischaltung,
                # Schritt 3); der eigene Zugang im Vertragsjahr 0 hat
                # noch keine.
                erwartet = float(h["sum_insured"]) + sum(
                    vs for j, vs in scheiben_je_police.get(pid, []) if j <= jahr
                )
            else:
                v = _herleitung(pid, h)
                if v is None:
                    continue
                bfr_ab = pex_jahr.get(pid)
                # NACH einer Herabsetzung traegt der Vertrag keine Schicht
                # mehr — sie ist in die Neuberechnung eingegangen und
                # steckt in seiner neuen Basis. Sie hier noch einmal zu
                # addieren hiesse, denselben Betrag zweimal zu fuehren.
                schicht_jetzt = (
                    None if v.ist_reduziert(jahr)
                    else schicht_je_police.get(pid))
                if art == "STO":
                    erwartet = v.rkw(jahr)
                    if schicht_traegt(schicht_jetzt, 12 * jahr):
                        erwartet += schichtwert_bei(
                            schicht_jetzt[0], schicht_jetzt[1], v.grund_mp,
                            12 * jahr)
                elif art == "PEX":
                    # Uebernommene Vertraege buchen die Umbuchung zum
                    # Zugangsstichtag, die Summe wurde im Jahr der
                    # Beitragsfreistellung fixiert (gates.bestand_uebernehmen).
                    pex_j = (bfr_ab if bfr_ab is not None and bfr_ab <= jahr
                             else jahr)
                    erwartet = v.beitragsfreie_summe(pex_j) + zuschlag_bei_pex(
                        schicht_jetzt, v.grund, pex_j)
                elif art == "RED":
                    # Die Buchungen einer Herabsetzung folgen aus der
                    # registrierten Reduktion — Soll-Menge UND Betraege aus
                    # EINER Herleitung (red_buchungen); dieselbe Menge
                    # prueft unten die Vollstaendigkeit (T27-14). Eine
                    # RED-Zeile, die keine registrierte Herabsetzung
                    # erzeugt, ist unbelegt — nicht "Betrag 0".
                    soll = v.red_buchungen(schicht_je_police.get(pid))
                    if (v.reduktion is None or jahr != v.reduktion[0]
                            or betrag_art not in soll):
                        unbelegt.append(
                            f"police {pid} RED Jahr {jahr} {betrag_art}")
                        continue
                    erwartet = soll[betrag_art]
                elif art in ("TOD", "ABL"):
                    if bfr_ab is not None and bfr_ab <= jahr:
                        # Nach einer absorbierenden Freistellung ist der
                        # ueberfuehrte Wert Teil der GARANTIERTEN Summe —
                        # die Todesfall-/Ablaufleistung traegt ihn mit.
                        erwartet = v.beitragsfreie_summe(bfr_ab) + zuschlag_bei_pex(
                            schicht_jetzt, v.grund, bfr_ab)
                    else:
                        erwartet = v.gesamt_vs(jahr)
        if erwartet is not None and abs(betrag - erwartet) > TOLERANZ:
            abweichungen.append(
                f"police {pid} {art} Jahr {jahr}: Ledger {betrag:.2f}, "
                f"Kern {erwartet:.2f}")

    # Vollstaendigkeit (T27-14): Jede registrierte Herabsetzung hat ihre
    # Buchungen — GENAU EINMAL. Die Soll-Menge ist dieselbe, aus der oben
    # die Betraege kommen; fehlt eine Zeile, fehlt sie hier.
    fehlend: List[str] = []
    red_zeilen = ledger[ledger["ereignis"] == "RED"]
    for pid, (jahr, _anteil, _verfahren) in sorted(reduktion_je_police.items()):
        if pid not in haupt.index:
            errors.append(f"reduktionen police {pid}: nicht im Stamm")
            continue
        h = haupt.loc[pid]
        if str(h.get("produkt", "klv")) == "bu":
            continue
        if pid in widerspruch:
            continue                         # oben als Widerspruch gemeldet
        v = _herleitung(pid, h)
        if v is None:
            continue
        eigene = red_zeilen[(red_zeilen["police_id"] == pid)
                            & (red_zeilen["vertragsjahr"] == jahr)]
        # Der Wirkungstag der Buchung IST der Wirkungstag der Tabelle —
        # sonst bewerten zwei Sichten denselben Bestand verschieden (N16).
        fehlend.extend(red_vollstaendigkeit_fehler(
            pid, jahr, eigene, v.red_buchungen(schicht_je_police.get(pid)),
            reduktion_datum[pid], fremde_arten=False))
    if fehlend:
        errors.append(
            f"ledger: {len(fehlend)} Buchung(en) registrierter Herabsetzungen "
            "fehlen oder sind mehrfach gebucht — z. B. "
            + "; ".join(fehlend[:3])
            + (" ..." if len(fehlend) > 3 else "")
            + ". Die Reduktionstabelle kennt die Herabsetzung, der Ledger "
            "muss jede ihrer Buchungen genau einmal tragen"
        )
    if unbelegt:
        errors.append(
            f"ledger: {len(unbelegt)} RED-Buchung(en), die keine registrierte "
            "Herabsetzung erzeugt — z. B. " + "; ".join(unbelegt[:3])
            + (" ..." if len(unbelegt) > 3 else "")
        )
    if abweichungen:
        errors.append(
            f"ledger: {len(abweichungen)} Buchung(en), deren Betrag nicht aus "
            "dem Kern fuer diese Police folgt — z. B. "
            + "; ".join(abweichungen[:3])
            + (" ..." if len(abweichungen) > 3 else "")
            + ". Ein Betrag, der zu einer anderen Police gehoert, ist keine "
            "Buchung dieser Police, auch wenn die Jahressumme aufgeht"
        )
    return errors


def pruefe_scheiben_tarifwerk(
    stamm: pd.DataFrame,
    scheiben: Optional[pd.DataFrame],
    config: BestandConfig,
    *,
    merkmale: Optional[pd.DataFrame] = None,
) -> List[str]:
    """Das gamma1 jeder Scheibe ist das, das das Tarifwerk ihrer
    Generation vorgibt — null oder das gamma1 der Zelle.

    Die Scheibe traegt ihre Rechnungsgrundlage selbst (ADR-011), und
    die Form prueft ``validate_scheiben`` ohne Config. WELCHER Wert
    richtig ist, weiss nur die Generation: Das eigene Geschaeft rechnet
    Erhoehungsscheiben ohne gamma1 (Tarifplan KLV 7, Bezugsgroesse
    GrundVS); eine uebernommene Generation mit ``scheiben_mit_gamma1``
    rechnet jeden Baustein mit der vollen Beitragsformel, also mit dem
    gamma1 seiner Zelle (Freischaltung, Schritt 2 und 4). Ein anderer
    Wert waere ein Fremdwert, der still einen anderen Beitrag und eine
    andere Reserve erzeugt.
    """
    errors: List[str] = []
    if scheiben is None or len(scheiben) == 0:
        return errors
    generationen = {g.name: g for g in config.generationen}
    grundlagen = grundlagen_je_police(config, merkmale)
    haupt = stamm.set_index("police_id")
    falsch: List[str] = []
    for s in scheiben.itertuples(index=False):
        pid = int(s.police_id)
        if pid not in haupt.index:
            continue    # validate_scheiben meldet die fremde Police
        name = str(haupt.loc[pid, "tarif_generation"])
        gen = generationen.get(name)
        if gen is None:
            errors.append(
                f"scheiben police {pid}: Tarifgeneration {name!r} nicht in "
                f"Config (bekannt: {sorted(generationen)})")
            continue
        try:
            erwartet = (
                float(grundlagen(pid, name)["gamma1"])
                if gen.tarifwerk()["scheiben_mit_gamma1"] else 0.0
            )
        except ValueError as exc:
            errors.append(f"scheiben police {pid}: {exc}")
            continue
        if float(s.gamma1) != erwartet:
            falsch.append(
                f"police {pid} Scheibe {int(s.scheiben_id)}: gamma1 "
                f"{float(s.gamma1)!r}, Tarifwerk der Generation {name} "
                f"verlangt {erwartet!r}")
    if falsch:
        errors.append(
            f"scheiben: {len(falsch)} Scheibe(n) mit gamma1 ausserhalb des "
            "Tarifwerks ihrer Generation (scheiben_mit_gamma1 der Config "
            "entscheidet: 0 oder das gamma1 der Zelle) — z. B. "
            + "; ".join(falsch[:3]) + (" ..." if len(falsch) > 3 else "")
        )
    return errors
