"""``darstellung`` — vom falldaten-Modell zu den Eingaben der Grafik-Bausteine.

Hier steht an EINER Stelle, welcher Modellpfad welche Darstellung
speist. ``grafik`` kennt das Modell nicht, die Seitengeneratoren
(``vorzeigeseite``, ``unternehmensseite``) kennen die Grafik nicht —
beide treffen sich hier. Aendert sich das Modell, aendert sich eine
Datei.

Alle Funktionen sind reine Abbildungen ohne Seiteneffekte; Verweise auf
Artefakte loest der Aufrufer ueber ``link(ref)`` auf, weil nur er weiss,
was tatsaechlich kopiert wurde (Regie-Sperre, Positivliste).
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import grafik

Link = Callable[[Optional[str]], Optional[str]]

ABNAHME_TITEL = {
    "A-M1": "Stichtagstest", "A-M2": "Verlaufstest",
    "A-M3": "Geschäftsvorfalltest",
}
ABNAHME_ZWECK = {
    "A-M1": "Übernahmezeitpunkt und nächster Vertragsstichtag, geschichtete Stichprobe",
    "A-M2": "fünf und zehn Jahre nach der Übernahme und der Ablauf",
    "A-M3": "jeder Geschäftsvorfall an der Änderung des Deckungskapitals, Vollerhebung",
}


def _zahl(wert: Any, dez: int = 0) -> str:
    return grafik._zahl(wert, dez)


def datum(wert: Any) -> str:
    """ISO-Datum in der Schreibweise des Auftritts. Wohnt hier, weil
    beide Erzeuger dieselben Stichtage schreiben."""
    try:
        jahr, monat, tag = str(wert).split("-")
        return f"{tag}.{monat}.{jahr}"
    except ValueError:
        return str(wert)


def _mio(wert: Any) -> str:
    return f"{_zahl(float(wert) / 1e6, 1)} Mio. €"


def gesamt_einzelwerte(modell: Dict[str, Any]) -> int:
    """Alle einzeln nachgerechneten Werte: Aktuartests plus Controlling."""
    a = modell.get("abnahmen") or {}
    werte = sum(int((t.get("verteilung") or {}).get("anzahl_werte") or 0)
                for t in a.get("aktuariell") or [])
    c = a.get("controlling") or {}
    werte += int((c.get("verteilung") or {}).get("anzahl_werte")
                 or sum((c.get("je_groesse") or {}).values()))
    return werte


def finale_zeichnungen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for e in (modell.get("kette") or {}).get("entscheide") or []
            if e.get("in_finaler_kette")]


def geltende_zeichnungen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Je Gate der geltende Entscheid: die finale Kette der Abschlussabnahme
    und dazu Fallauftrag, Abnahmen des Stands und Zugang (``falldaten.kette``)."""
    return [e for e in (modell.get("kette") or {}).get("entscheide") or []
            if e.get("geltend") or e.get("in_finaler_kette")]


def kennzahl_gruppen(modell: Dict[str, Any]) -> List[Tuple[str, List[Tuple[str, str]]]]:
    """Umfang / Prueftiefe / Verbindlichkeit — dieselbe Ordnung auf jeder Seite."""
    b = modell.get("bestand") or {}
    a = modell.get("abnahmen") or {}
    c = a.get("controlling") or {}
    k = modell.get("kette") or {}
    abzug = (b.get("abzuege") or [{}])[0]
    dk = (abzug.get("deckkap") or {}).get("summe")
    finale = finale_zeichnungen(modell)
    abschluss = [e for e in finale if e.get("gate") == "A-M4"]
    umfang: List[Tuple[str, str]] = [(_zahl(b.get("anzahl", 0)), "Verträge übernommen")]
    if dk:
        umfang.append((_mio(dk), "Deckungskapital der Lieferung"))
    vg = (b.get("vorgeschichte") or {}).get("anzahl")
    if vg:
        umfang.append((_zahl(vg), "Vorfälle der Vorgeschichte"))
    # Pruefumfaenge EINZELN mit Einheit — die Mengen sind nicht disjunkt
    # (Stichtags- und Verlaufstest fahren dieselbe Ziehung, das
    # Controlling prueft dieselben Vertraege noch einmal); eine Summe
    # waere die Doppelzaehlung, die der Auftritt ausschliesst.
    tiefe: List[Tuple[str, str]] = []
    cv = c.get("verteilung") or {}
    if cv.get("anzahl_werte"):
        tiefe.append((_zahl(cv["anzahl_werte"]),
                      f"Einzelprüfungen über alle {_zahl(c.get('anzahl', 0))} Verträge"))
    akt = [t for t in a.get("aktuariell") or [] if (t.get("verteilung") or {}).get("anzahl_werte")]
    if akt:
        tiefe.append((" · ".join(_zahl(t["verteilung"]["anzahl_werte"]) for t in akt),
                      "Einzelwerte in " + " / ".join(str(t.get("kennung")) for t in akt)))
    if c:
        tiefe.append((_zahl(c.get("pruefluecken", 0)), "Prüflücken"))
    verbindlich: List[Tuple[str, str]] = [(_zahl(len(geltende_zeichnungen(modell))), "geltende Entscheide")]
    if abschluss:
        verbindlich.append((_zahl(abschluss[0].get("artefakte_gebunden", 0)),
                            "Artefakte an die Abschlusszeichnung gebunden"))
    laeufe = sum(int(g.get("versuch") or 1) for g in k.get("gates") or [])
    if laeufe:
        verbindlich.append((_zahl(laeufe), "Prüfläufe bis zum Urteil"))
    return [("Umfang", umfang), ("Prüftiefe", tiefe), ("Verbindlichkeit", verbindlich)]


def toleranz_zeilen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gemessen gegen zugesagt, je Abnahme; das Controlling ohne feste Schranke."""
    a = modell.get("abnahmen") or {}
    zeilen = []
    for t in a.get("aktuariell") or []:
        v = t.get("verteilung") or {}
        g = t.get("grundtoleranz") or {}
        if not v:
            continue
        zeilen.append({
            "titel": f"{t.get('kennung')} {ABNAHME_TITEL.get(t.get('kennung'), t.get('titel', ''))}",
            "ist_max": v.get("max_abs_residuum") or 0,
            "ist_p95": v.get("p95_abs_residuum") or 0,
            "grenze_max": g.get("max_abs_residuum"),
            "grenze_p95": g.get("p95_abs_residuum"),
            "werte": v.get("anzahl_werte"),
        })
    c = a.get("controlling") or {}
    v = c.get("verteilung") or {}
    if v:
        zeilen.append({
            "titel": "A-M4 Migrationscontrolling",
            "ist_max": v.get("max_abs_residuum") or 0,
            "ist_p95": v.get("p95_abs_residuum") or 0,
            "grenze_max": None, "grenze_p95": None,
            "werte": v.get("anzahl_werte"),
        })
    return zeilen


def toleranz_unterzeile(modell: Dict[str, Any]) -> str:
    """Absolutwerte je Abnahme mit ihrem Umfang — keine Quote, kein
    Vergleich zwischen Abnahmen: Die Ausschoepfung ist eine Eigenschaft
    der gewaehlten Schranke, kein Guetemass."""
    a = modell.get("abnahmen") or {}
    teile = []
    for t in a.get("aktuariell") or []:
        v, g = t.get("verteilung") or {}, t.get("grundtoleranz") or {}
        if v.get("max_abs_residuum") is None:
            continue
        teile.append(
            f"{ABNAHME_TITEL.get(t.get('kennung'), t.get('kennung'))} "
            f"({_zahl(t.get('anzahl', 0))} Verträge, {_zahl(v.get('anzahl_werte', 0))} Werte): "
            f"größte Abweichung {grafik.cent(v['max_abs_residuum'])}"
            + (f" bei erlaubten {grafik.cent(g['max_abs_residuum'])}" if g.get("max_abs_residuum") else ""))
    c = a.get("controlling") or {}
    cv = c.get("verteilung") or {}
    if cv.get("max_abs_residuum") is not None:
        teile.append(
            f"Controlling ({_zahl(c.get('anzahl', 0))} Verträge, "
            f"{_zahl(cv.get('anzahl_werte', 0))} Prüfungen): größte Abweichung "
            f"{grafik.cent(cv['max_abs_residuum'])}, Schranke je Prüfung nach Bausteinen")
    return "; ".join(teile) + ("." if teile else "")


def abgrenzung_karten(modell: Dict[str, Any]) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    karten = [(a.get("was", ""), a.get("zahlen") or "", a.get("sicht", "fachlich"))
              for a in modell.get("abgrenzungen") or []]
    u = modell.get("umbau") or {}
    for befund in u.get("befunde") or []:
        grund = u.get("ueberschreitung_begruendet")
        karten.append((f"Umbau-Messung: {befund}",
                       f"begründet: „{grund}“" if grund else "ohne Begründung",
                       "technisch"))
    luecken = [l.get("was", "") for l in modell.get("luecken") or []]
    return karten, luecken


#: Beschriftung der Gates. Wohnt hier, weil beide Erzeuger sie brauchen —
#: die Unternehmensseite fuer ihre Rollenuebersicht, die Fallseite fuer
#: die Stationen.
GEGENSTAND_TEXT = {"Q": "Quellen und Ontologie", "K": "Rechenkern",
                   "B": "Bestand", "M": "die Migration als Ganzes",
                   "O": "Ontologie als Vertrag", "T": "Tarifwerk"}
GATE_TITEL = {"quellfragment": "Quellfragment", "zusammenfuehrung": "Zusammenführung",
              "fachliche-pruefung": "Fachliche Prüfung", "quellenabnahme": "Quellenabnahme",
              "tarifgeneration": "Tarifgeneration",
              "generations-golden-master": "Golden Master je Generation",
              "bestandspruefung": "Bestandsprüfung", "stichtagstest": "Stichtagstest",
              "verlaufstest": "Verlaufstest", "geschaeftsvorfalltest": "Geschäftsvorfalltest",
              "migrationscontrolling": "Migrationscontrolling",
              "fallauftrag": "Fallauftrag", "fallabbruch": "Fallabbruch",
              "tbox-aenderung": "Stand der Ontologie", "tarifwerk": "Tarifwerk",
              "kernaenderung": "Stand des Rechenkerns",
              "auslieferung": "Auslieferung", "zugangsabnahme": "Zugangsabnahme",
              "anfangsbestand": "Anfangsbestand"}
ART = {"P": "Prüfung durch das Programm, deterministisch, blockiert bei Rot",
       "A": "Abnahme durch einen Menschen, der entscheidet und zeichnet"}

#: Der Zustand eines Pflichtfelds in der Abdeckungsmessung. Die
#: Schluessel kommen aus dem Rechenkern und tragen die Repo-Umschrift;
#: auf der Seite steht Unternehmenssprache.
DECKUNG_ZUSTAND = {"belegt": "belegt", "nicht_belegt": "nicht belegt",
                   "mehrdeutig": "mehrdeutig",
                   "widerspruechlich": "widersprüchlich",
                   "fehlt_in_extraktion": "fehlt in der Extraktion"}


#: Der Weg einer Uebernahme, Station fuer Station: Nummer, Name und das
#: Gate, das dort sitzt (None, wo keines sitzt). EINE Reihenfolge fuer
#: zwei Seiten — "Der Weg der Uebernahme" erzaehlt sie, der Fallbericht
#: fuehrt sie als Tabelle und ordnet seine Abschnitte danach. Zwei
#: getrennte Listen liefen auseinander, und der Leser saehe zwei
#: Reihenfolgen fuer denselben Vorgang.
WEG_STATIONEN: Tuple[Tuple[int, str, Optional[str]], ...] = (
    # Seit ADR-026 beginnt ein Fall mit dem gezeichneten Auftrag des
    # Vorstands (A-M6) und endet mit dem Zugang, den der Betrieb abnimmt
    # (A-B2, ADR-022) — beide sitzen an den Stationen, die ihren Gegenstand
    # tragen.
    (1, "Auftrag und Lieferung", "A-M6"),
    (2, "Quellen lesen", "P-Q1"),
    (3, "Quellen zusammenführen", "P-Q2"),
    (4, "Faktenbasis prüfen", "P-Q3"),
    (5, "Quellen abnehmen", "A-Q1"),
    (6, "Bestand übersetzen", None),
    (7, "Rechenkern gegen den Quellrechner", "P-K1"),
    (8, "Bestand prüfen", "P-B1"),
    (9, "Stichtag prüfen", "A-M1"),
    (10, "Verlauf prüfen", "A-M2"),
    (11, "Geschäftsvorfälle prüfen", "A-M3"),
    (12, "Migrationscontrolling", "A-M4"),
    (13, "Zugang in die Bücher", "A-B2"),
)

#: Berichte des Aktuariats unter migrationen/baldrian/berichte/, die zu GENAU einem Fall
#: gehoeren: (Quelle relativ zu docs/, Ziel im Auftritt, Titel). Ein Bericht
#: ueber Lauf 2 ist kein Bericht ueber Fall 3 — der Auftritt zeigt ihn nur,
#: wenn er den Fall darstellt, den der Bericht wuerdigt.
FALLDOKUMENTE: Dict[str, Tuple[Tuple[str, str, str], ...]] = {
    "baldrian-klv-tg2015-lauf2": (
        ("../migrationen/baldrian/berichte/baldrian-lauf2.md", "migrationen/abschlussbericht-baldrian.md", "Abschlussbericht"),
        ("../migrationen/baldrian/berichte/baldrian-lauf2-veraenderungen.md", "migrationen/veraenderungen-baldrian.md",
         "Was sich verändert hat"),
    ),
}


def falldokumente(modell: Dict[str, Any]) -> Tuple[Tuple[str, str, str], ...]:
    """Die Berichte des Aktuariats zum dargestellten Fall — oder keine."""
    return FALLDOKUMENTE.get(str(((modell or {}).get("fall") or {}).get("name") or ""), ())


#: Abnahmen, die eine Station NEBEN ihrem Gate traegt: der Stand, auf dem
#: der Fall rechnet (A-K2 Rechenkern, A-T1 Tarifwerk, A-O1 Begriffsmodell;
#: ADR-018 Nachtrag 01.10., ADR-025), beim Rechenkern; der Abbruch eines
#: Falls (A-M5, ADR-026) beim Abschluss; die Auslieferung (A-B1) beim
#: Zugang in die Buecher. A-B1 ist ein Gate der Linie, gezeichnet wird es
#: aber im Fall (gate_entscheid --fall): Es gibt den Stand der Buecher, in
#: die der Bestand eben gegangen ist, nach aussen frei (Entscheid des
#: Maintainers, 03.10.2026).
STATION_WEITERE_GATES: Dict[int, Tuple[str, ...]] = {
    7: ("A-K2", "A-T1", "A-O1"), 12: ("A-M5",), 13: ("A-B1",)}

#: Station je Gate — abgeleitet, nicht gepflegt. Ein Gate des Registers
#: ohne Station ist ein Testbefund; das Gate der Linie A-B3 zeichnet
#: ausserhalb jedes Falls und hat keine.
GATE_STATION: Dict[str, int] = {
    **{g: n for n, _, g in WEG_STATIONEN if g},
    **{g: n for n, gs in STATION_WEITERE_GATES.items() for g in gs},
}

#: Der Anker der Station auf der Fallseite. JEDE Station hat einen —
#: die Regel der Fallseite lautet "eine Station, eine Stelle", und wer
#: in der Uebersicht auf Station 8 klickt, landet bei Station 8. Vier
#: Stationen teilten sich frueher einen Anker "wie-geprueft-wurde", fuenf
#: hatten gar keinen; dieselbe Aufteilung, die den Leser hin- und
#: herspringen liess.
STATION_ABSCHNITT = {
    1: "die-lieferung",
    2: "quellen-lesen",
    3: "quellen-zusammenfuehren",
    4: "faktenbasis-pruefen",
    5: "der-widerspruch",
    6: "die-uebersetzung-der-daten",
    7: "rechenkern-gegen-quellrechner",
    8: "bestand-pruefen",
    9: "stichtag-pruefen",
    10: "verlauf-pruefen",
    11: "geschaeftsvorfaelle-pruefen",
    12: "migrationscontrolling",
    13: "der-bestand",
}


def stationslage(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Je Station des Wegs, was der Lauf dort ergeben hat.

    Anlaeufe und Urteil kommen aus der Gate-Kette des Falls, nicht aus
    einer zweiten Zaehlung: Der juengste Lauf je Gate ist der, der zaehlt.
    """
    laeufe: Dict[str, Dict[str, Any]] = {}
    for g in (modell.get("kette") or {}).get("gates") or []:
        kennung = str(g.get("gate", "")).split(".")[0]
        if kennung.startswith(("P-", "A-")):
            laeufe[kennung] = g
    # Menschliche Abnahmen hinterlassen einen ENTSCHEID, keinen Gate-Lauf
    # (A-Q1 etwa erscheint nirgends in kette.gates). Ohne diesen Zweig
    # stuende dort "ohne Gate" — und das waere schlicht falsch: Es gibt
    # eines, es hat nur ein Mensch bedient.
    entschieden: Dict[str, Dict[str, Any]] = {}
    runden: Dict[str, int] = {}
    for e in (modell.get("kette") or {}).get("entscheide") or []:
        kennung = str(e.get("gate") or "")
        runden[kennung] = runden.get(kennung, 0) + 1
        if e.get("geltend") or e.get("in_finaler_kette") or kennung not in entschieden:
            entschieden[kennung] = e
    aus = []
    for nummer, titel, gate in WEG_STATIONEN:
        lauf = laeufe.get(gate) if gate else None
        e = entschieden.get(gate) if gate else None
        if lauf:
            versuche, urteil = lauf.get("versuch"), lauf.get("status")
        elif e:
            versuche, urteil = runden.get(gate), e.get("entscheid")
        else:
            versuche, urteil = None, None
        aus.append({
            "nummer": nummer, "titel": titel, "gate": gate,
            "versuche": versuche, "urteil": urteil,
            "gezeichnet": bool(e), "abschnitt": STATION_ABSCHNITT.get(nummer),
        })
    return aus


#: Die Station des Wegs, an der ein Bericht entsteht — Nummer und Name
#: wie auf "Der Weg der Uebernahme". Schluessel ist der Anfang des
#: Berichtstitels, weil der aus Gate-Kennung und Register kommt und
#: stabiler ist als ein Dateiname.
#:
#: Wozu: Die Belege lagen bisher in der Reihenfolge, in der der Code sie
#: anhaengt — erst die Abnahmen, dann der Umbau, dann alle drei
#: Bestandsberichte am Stueck. Ein Leser, der den Weg gelesen hat, sucht
#: sie aber dort, wo sie entstanden sind: der gelieferte Bestand bei der
#: Lieferung, der gefuehrte beim Zugang in die Buecher. Dieselbe
#: Reihenfolge auf beiden Seiten macht aus zwei Aufzaehlungen einen Weg.
_NAME = {n: t for n, t, _ in WEG_STATIONEN}
STATION = {
    "Eigener Bestand": (0, "Ausgangslage vor der Übernahme"),
    "Übernommener Bestand zum Stichtag": (8, _NAME[8]),
    "Umbau des Zielsystems": (7, _NAME[7]),
    "A-M1": (9, _NAME[9]),
    "A-M2": (10, _NAME[10]),
    "A-M3": (11, _NAME[11]),
    "A-M4": (12, _NAME[12]),
    "Übernommener Bestand, fortgeschrieben": (12, _NAME[12]),
}

#: Berichte ohne zugeordnete Station kommen ans Ende, in der Reihenfolge,
#: in der sie angehaengt wurden — sichtbar hinten statt still dazwischen.
_OHNE_STATION = 99


def _station(titel: str) -> Tuple[int, str]:
    for marke, wert in STATION.items():
        if titel.startswith(marke):
            return wert
    return (_OHNE_STATION, "")


def berichte(modell: Dict[str, Any], link: Link,
             extra: Sequence[Dict[str, Any]] = ()) -> List[Dict[str, Any]]:
    """Berichte als Anlaufstellen: Titel, Zweck, Kennzahl, Verweis.

    Sortiert nach der Station des Wegs, an der der Bericht entsteht
    (:data:`STATION`) — nicht nach der Reihenfolge, in der der Code sie
    zusammentraegt.
    """
    a = modell.get("abnahmen") or {}
    aus: List[Dict[str, Any]] = []
    for t in a.get("aktuariell") or []:
        href = link(t.get("bericht"))
        if not href:
            continue
        v = t.get("verteilung") or {}
        kennzahl = f"{_zahl(t.get('anzahl', 0))} Verträge"
        if v.get("anzahl_werte"):
            kennzahl += f" · {_zahl(v['anzahl_werte'])} Werte"
        if v.get("max_abs_residuum") is not None:
            kennzahl += f" · max {grafik.cent(v['max_abs_residuum'])}"
        kennung = t.get("kennung")
        aus.append({"titel": f"{kennung} {ABNAHME_TITEL.get(kennung, t.get('titel', ''))}",
                    "zweck": ABNAHME_ZWECK.get(kennung, ""),
                    "kennzahl": kennzahl, "href": href, "format": "HTML"})
    c = a.get("controlling") or {}
    href = link("abgeleitet/berichte/migrationsabnahme.html")
    if c and href:
        v = c.get("verteilung") or {}
        aus.append({"titel": "A-M4 Migrationscontrolling",
                    "zweck": "der ganze Bestand über zwei Stichtage",
                    "kennzahl": f"{_zahl(c.get('anzahl', 0))} Verträge · "
                                f"{_zahl(v.get('anzahl_werte', 0))} Einzelprüfungen",
                    "href": href, "format": "HTML"})
    href = link("abgeleitet/berichte/umbaubericht.html")
    u = modell.get("umbau") or {}
    if href and u.get("vorhanden"):
        gesamt = u.get("gesamt") or {}
        aus.append({"titel": "Umbau des Zielsystems",
                    "zweck": "was der Lauf am System verändert hat, mit Befunden und Begründung",
                    "kennzahl": f"{_zahl(gesamt.get('summe', 0))} von {_zahl(gesamt.get('vorgabe', 0))} Zeilen",
                    "href": href, "format": "HTML"})
    refs = list(a.get("bestandsberichte") or [])
    if any(r.startswith("abgeleitet/bestand-nach/") for r in refs):
        refs = [r for r in refs if not r.endswith("berichte/bestandsbericht-nach.html")]
    beschriftung = {
        # Was die Berichte sind, sagen sie selbst: im Rechenkern bewertet,
        # nicht aus der Lieferung uebernommen; der zweite ist die
        # Fortschreibung im Fall, nicht der gefuehrte Bestand des Betriebs.
        "bestandsbericht-vor.html": ("Übernommener Bestand zum Stichtag", "im Rechenkern bewertet, vor der Fortschreibung"),
        "bestandsbericht.html": ("Übernommener Bestand, fortgeschrieben", "Fortschreibung im Fall bis zum Kontrollstichtag"),
        "bestandsbericht-nach.html": ("Übernommener Bestand, fortgeschrieben", "Fortschreibung im Fall bis zum Kontrollstichtag"),
    }
    for ref in refs:
        href = link(ref)
        if not href:
            continue
        name = ref.rsplit("/", 1)[-1]
        titel, zweck = beschriftung.get(name, (name, ""))
        # Die Vertragszahl des Modells ist die des UEBERNOMMENEN Bestands;
        # der Eigenbestand vor der Uebernahme ist eine andere Menge, die
        # das Modell nicht zaehlt — dort keine Zahl behaupten.
        kennzahl = f"{_zahl((modell.get('bestand') or {}).get('anzahl', 0))} übernommene Verträge"
        if ref.startswith("abgeleitet/bestand-vor/"):
            titel, zweck = ("Eigener Bestand", "vor der Übernahme, ohne den Zugang — Referenzlauf")
            kennzahl = "Referenzlauf des Eigenbestands"
        aus.append({"titel": titel, "zweck": zweck, "kennzahl": kennzahl,
                    "href": href, "format": "HTML"})
    aus.extend(extra)
    for k in aus:
        nummer, name = _station(k["titel"])
        k["station"] = nummer
        # Station 0 ist keine Station des Wegs, sondern die Ausgangslage
        # davor; sie bekommt keine Nummer vorangestellt.
        if name and nummer:
            k["zweck"] = f"Station {nummer} · {name} — {k['zweck']}"
        elif name:
            k["zweck"] = f"{name} — {k['zweck']}"
    aus.sort(key=lambda k: k["station"])
    return aus


def stationen(modell: Dict[str, Any], basis: str = "") -> List[Tuple[str, str, str]]:
    """Der Fall in fuenf Stationen, jede mit Kennzahl und Sprungziel."""
    l = modell.get("lieferung") or {}
    t = modell.get("transformation") or {}
    p = modell.get("parameter") or {}
    nach = l.get("anzahl_nachgereicht") or 0
    echte = [g for g in diskrepanz_gruppen(modell) if g["wertkonflikt"]]
    c = (modell.get("abnahmen") or {}).get("controlling") or {}
    cv = c.get("verteilung") or {}
    return [
        ("Dateien geliefert" + (f", {nach} nachgefordert" if nach else ""),
         _zahl(l.get("anzahl", 0)), f"{basis}#die-lieferung"),
        ("Zielfelder übersetzt", _zahl(t.get("anzahl_zielfelder", 0)),
         f"{basis}#die-uebersetzung-der-daten"),
        ("Feststellungen gegen die gelieferten Unterlagen, alle entschieden",
         _zahl(len(echte)), f"{basis}#der-widerspruch"),
        (f"Einzelprüfungen über alle {_zahl(c.get('anzahl', 0))} Verträge",
         _zahl(cv.get("anzahl_werte", 0)), f"{basis}#das-ergebnis"),
        ("Abnahmen entschieden", _zahl(len(geltende_zeichnungen(modell))),
         f"{basis}entscheide.html"),
    ]


def diskrepanz_zeilen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Die Widersprueche der Unterlagen, je Feld und Tarifzelle.

    ``wertkonflikt`` unterscheidet echte Widersprueche von
    Namensartefakten: Eine Diskrepanz, deren Begruendung "kein eigener
    Wertkonflikt" feststellt, ist kein Widerspruch, sondern dieselbe
    Groesse in zwei Schreibweisen — sie darf die Zahl der Widersprueche
    nicht aufblaehen.
    """
    aus = []
    for d in (modell.get("parameter") or {}).get("diskrepanzen") or []:
        zelle = str(d.get("knoten") or "").split("zelle:")[-1]
        begr = str(d.get("begruendung") or "")
        aus.append({
            "feld": d.get("feld"), "zelle": zelle,
            "lesarten": [(l.get("wert"), l.get("quelle")) for l in d.get("lesarten") or []],
            "gewaehlt": d.get("gewaehlt"), "entscheider": d.get("entscheider"),
            "status": d.get("status"), "vorlaeufig": d.get("vorlaeufig"),
            "begruendung": begr,
            "wertkonflikt": not begr.lower().startswith("kein eigener wertkonflikt"),
        })
    return aus


def diskrepanz_gruppen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Je Feld eine Feststellung: welche Lesarten, wie viele Zellen,
    ob ein echter Wertkonflikt, wie entschieden."""
    gruppen: Dict[str, Dict[str, Any]] = {}
    for d in diskrepanz_zeilen(modell):
        g = gruppen.setdefault(d["feld"], {
            "feld": d["feld"], "zellen": [], "lesarten": [], "gewaehlt": set(),
            "entscheider": set(), "wertkonflikt": False, "begruendung": d["begruendung"],
        })
        g["zellen"].append(d["zelle"])
        for l in d["lesarten"]:
            if l not in g["lesarten"]:
                g["lesarten"].append(l)
        if d.get("gewaehlt") is not None:
            g["gewaehlt"].add(str(d["gewaehlt"]))
        if d.get("entscheider"):
            g["entscheider"].add(str(d["entscheider"]))
        g["wertkonflikt"] = g["wertkonflikt"] or d["wertkonflikt"]
    aus = []
    for g in gruppen.values():
        g["gewaehlt"] = sorted(g["gewaehlt"])
        g["entscheider"] = sorted(g["entscheider"])
        aus.append(g)
    return sorted(aus, key=lambda g: (not g["wertkonflikt"], g["feld"]))


#: Text je Station fuer den Prozessplan (migrationen/index.md, Abschnitt #prozess):
#: Titelzeilen (umbrochen fuer 236 px), wer handelt, zwei Zeilen dazu, die
#: Agentenrollen, die vorlegen, und die menschlichen Rollen, die zeichnen.
#: Nummer, Name und Gate kommen aus WEG_STATIONEN — eine Liste.
PROZESS_STATIONEN_TEXT = {
    1: (["Auftrag und", "Lieferung"], "Der Vorstand beauftragt;", ["die Lieferung wird mit", "Prüfsumme registriert"], ["Programmleitung"], ("Vorstand",)),
    2: (["Quellen lesen"], "Programm verdichtet vor,", ["Agent liest je Quelle,", "mit Fundstelle je Angabe"], ["Aktuariat"], ()),
    3: (["Quellen", "zusammenführen"], "Programm", ["Faktenbasis; Widersprüche", "bleiben als Diskrepanz offen"], ["Programmleitung"], ()),
    4: (["Faktenbasis prüfen"], "Programm", ["Pflichtfelder gezählt,", "nicht behauptet"], ["Programmleitung"], ()),
    5: (["Quellen abnehmen"], "Dossier je Diskrepanz:", ["beide Lesarten, Auswirkung,", "Empfehlung"], ["Aktuariat"], ("Aktuariat",)),
    6: (["Bestand übersetzen"], "Feldabbildung vorgeschlagen,", ["Programm prüft und übersetzt"], ["Aktuariat"], ()),
    7: (["Rechenkern gegen", "den Quellrechner"], "Golden Master je Generation;", ["abgenommener Stand: Kern,", "Tarifwerk, Begriffsmodell"], ["Rechenkern", "Architektur", "Aktuariat"], ("Rechenkern", "Aktuariat", "Architektur")),
    8: (["Bestand prüfen"], "Programm", ["Verankerung je Vertrag,", "Wache vor jedem Stand"], ["Programmleitung"], ()),
    9: (["Stichtag prüfen"], "je Vertrag zum Übernahme-", ["zeitpunkt, Stichprobe"], ["Aktuariat"], ("Aktuariat",)),
    10: (["Verlauf prüfen"], "Deckungsrückstellung", ["über die Laufzeit"], ["Aktuariat"], ("Aktuariat",)),
    11: (["Geschäftsvorfälle", "prüfen"], "jeder Vorfall, Vollerhebung", [], ["Aktuariat"], ("Aktuariat",)),
    12: (["Migrations-", "controlling"], "Gesamtbestand, zwei Stichtage;", ["bindet alle Belege; Snapshot", "nennt Rolle, Schlüsselklasse"], ["Aktuariat"], ("Aktuariat",)),
    13: (["Zugang in die", "Bücher"], "Zugangsprobe vor dem Zugang;", ["dann Tageslauf, Wache P-B1,", "Monatsabschluss, Freigabe A-B1"], ["Betrieb"], ("Betrieb",)),
}
#: Kuerzel der menschlichen Rolle, die zeichnet (ADR-018, ADR-022, ADR-026).
PROZESS_ZEICHNET = {"Aktuariat": "VA", "Architektur": "IT-V", "Rechenkern": "RK-V",
                    "Betrieb": "BV", "Vorstand": "VS", "Programmleitung": "PL"}
#: Funktional geteilt (Entscheid des Maintainers 04.10.2026): Auftrag und
#: Lieferung oben und der Zugang unten rahmen alles und laufen als Balken
#: ueber die ganze Breite; dazwischen drei Abschnitte. Eine Reihe mit EINER
#: Station ist ein Balken.
PROZESS_REIHEN = (("", (1,)),
                  ("Quellenanalyse", (2, 3, 4, 5)),
                  ("Transformation", (6, 7, 8)),
                  ("Aktuarielle Abnahmen", (9, 10, 11, 12)),
                  ("", (13,)))
#: Die Rollenleiste: je Agentenrolle ihre menschliche Gegenrolle; der
#: Vorstand hat kein Gegenstueck unter den Agenten.
PROZESS_ROLLEN = (
    ("Programmleitung", ("PL", "zeichnet nur den Fallabbruch A-M5"), "führt den Fall, hält an jedem Gate"),
    ("Aktuariat", ("VA", "zeichnet: Verantwortlicher Aktuar"), "liest, übersetzt, bereitet Abnahmen vor"),
    ("Architektur", ("IT-V", "zeichnet: IT-Verantwortung"), "hält die Migration in der Architektur"),
    ("Rechenkern", ("RK-V", "zeichnet: Rechenkern-Verantwortung"), "parametriert, ändert nur unter Abnahme"),
    ("Betrieb", ("BV", "zeichnet: Betriebsverantwortung"), "legt die Zugangsprobe vor"),
    (None, ("VS", "Vorstand"), "beauftragt den Fall, zeichnet A-M6"),
)


def _kurz(text: str, zeichen: int = 30) -> str:
    return text if len(text) <= zeichen else text[: zeichen - 1].rstrip() + "…"


def kasten_belege(modell: Dict[str, Any], n: int,
                  aufloesen: Callable[[str], Optional[str]],
                  station_href: str, hoechstens: int = 3) -> List[Tuple[str, Optional[str]]]:
    """Die Zeilen eines Kastens der Prozesskarte: bis zu ``hoechstens``
    Belege der Station aus der Belegkette des Modells — je Art der
    wichtigste —, dann was "In Arbeit" ist, dann der Verweis auf alle.

    Nichts davon steht in einer Tabelle von Hand: Welche Datei zu welcher
    Station gehoert, sagt ``falldaten.belegkette``. Mehrfaches (Lieferung,
    Vorverdichtung, Quellfragmente) erscheint als EINE Zeile mit Anzahl und
    fuehrt zur Station, an der alle stehen. Verlinkt wird nur, was
    ``aufloesen`` auf der Seite findet; eine Zeile ohne Ziel ist "In Arbeit".
    Ohne Modell — die Karte ohne Fall — ist der Kasten leer.
    """
    kette = (modell or {}).get("belegkette") or {}
    dateien = kette.get("dateien") or {}
    pfade = list((kette.get("je_station") or {}).get(str(n)) or [])
    import falldaten as _fd  # Arten und Rangfolge: EINE Stelle

    arten: Dict[str, List[str]] = {}
    for f in pfade:
        arten.setdefault(str(dateien[f].get("art")), []).append(f)
    zeilen: List[Tuple[str, Optional[str]]] = []
    for art in sorted(arten, key=lambda a: _fd.BELEG_ARTEN.get(a, (7, ""))[0]):
        if _fd.BELEG_ARTEN.get(art, (7, ""))[0] >= 8 or len(zeilen) == hoechstens:
            continue
        gruppe = arten[art]
        if art in _fd._MEHRFACH and len(gruppe) > 1:
            zeilen.append((f"{_fd.BELEG_ARTEN[art][1]} ({len(gruppe)})", station_href))
            continue
        # Der erste Beleg der Art, den die Seite wirklich traegt — der des
        # Haupt-Gates zuerst (an Station 13 A-B2 vor A-B1). Was nicht
        # kopiert ist, faellt weg — "In Arbeit" sagt nur die Kette selbst.
        haupt = {k: g for k, _, g in WEG_STATIONEN}.get(n)
        gruppe = sorted(gruppe, key=lambda f: not (haupt and str(
            dateien[f].get("titel") or "").endswith(f" {haupt}")))
        for f in gruppe:
            ziel = aufloesen(f)
            if ziel:
                zeilen.append((_kurz(str(dateien[f].get("titel"))), ziel))
                break
    for titel in (kette.get("in_arbeit") or {}).get(str(n)) or []:
        zeilen.append((titel, None))
    if len(pfade) > len(zeilen):
        zeilen.append((f"alle {len(pfade)} Belege der Station", station_href))
    return zeilen


def prozess_stationen(basis: str = "baldrian/", modell: Optional[Dict[str, Any]] = None,
                      aufloesen: Optional[Callable[[str], Optional[str]]] = None) -> str:
    """Der Prozessplan aus den dreizehn Stationen der Fallseite — dieselbe
    Liste, dieselben Anker. ``basis`` ist der Pfad von der bauenden Seite
    zur Fallseite; die Belege je Kasten kommen aus der Belegkette des
    ``modell`` (:func:`kasten_belege`), aufgeloest gegen die Dateien der
    gebauten Seite."""
    gate_je = {n: g for n, _, g in WEG_STATIONEN}
    aufloesen = aufloesen or (lambda ref: None)
    reihen = []
    for titel, nummern in PROZESS_REIHEN:
        kaesten = []
        for n in nummern:
            zeilen, wer, text, rollen, zeichnen = PROZESS_STATIONEN_TEXT[n]
            gate = gate_je[n]
            # Die Farbe sagt, wer an der Station entscheidet: A, sobald ein
            # Mensch abnimmt — auch neben einer Programmpruefung als
            # Haupt-Gate (Station 7: P-K1 mit A-K2, A-T1, A-O1).
            arten = {g.split("-", 1)[0] for g in (gate, *STATION_WEITERE_GATES.get(n, ())) if g}
            if arten - {"A", "P"}:
                raise ValueError(f"Prozessplan: unbekannte Gate-Art an Station {n}: {sorted(arten)}")
            href = f"{basis}#{STATION_ABSCHNITT[n]}"
            kaesten.append({"nummer": n, "zeilen": zeilen, "gate": gate,
                            "art": "A" if "A" in arten else ("P" if arten else None),
                            "wer": wer, "text": text,
                            "rollen": rollen,
                            "zeichnen": [(PROZESS_ZEICHNET[r], r) for r in zeichnen],
                            "href": href,
                            "wohin": f"Station {n} der Übernahme",
                            "artefakte": kasten_belege(modell or {}, n, aufloesen, href)})
        reihen.append({"titel": titel, "kaesten": kaesten, "balken": len(nummern) == 1})
    return grafik.prozessplan(
        reihen,
        "Rückfrageschleife: Befund oder fehlende Angabe → Agent erstellt Dossier → Mensch entscheidet oder liefert nach → "
        "registrieren → betroffene Prüfungen laufen erneut",
        PROZESS_ROLLEN,
        "Bestandsmigration in dreizehn Stationen: Auftrag und Lieferung, Quellenanalyse, "
        "Transformation, aktuarielle Abnahmen, Zugang in die Bücher")

