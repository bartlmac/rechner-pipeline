"""``falldaten`` — das Datenmodell einer Falldarstellung aus den Artefakten.

Beobachtungshilfe, kein Gate. Sie erzeugt aus einem abgeschlossenen
Migrationsfall ein JSON, das die Darstellung trägt — und sie RECHNET
dabei nichts eigenes: Jeder Wert stammt aus einem Artefakt des Falls und
ist dort nachprüfbar.

**Warum ein Datenmodell und nicht gleich eine Seite.** Eine Falldarstellung
soll beim nächsten Lauf dieselbe Struktur mit anderen Zahlen tragen. Was
sich ändert, gehört ins Modell; was gleich bleibt, sind Feldnamen und
Beschriftungen. Erzählt wird nur, was sich nicht ableiten lässt — und das
ist wenig: ein Absatz zum Anlass und je Fund eine Wirkungszeile. Alles
Übrige, bis hin zu den Begründungen der Abnahmen, kommt aus signierten
oder registrierten Quellen.

**Sechs Gruppen, zwei Sichten.** Die Gruppen sind Daten, die Sichten sind
Projektionen darüber. Manche Gruppe speist beide: Bei den Diskrepanzen
gehören die Werte in die fachliche Darstellung und die Belegmethode in die
technische.

==============  ==================================  =========================
Gruppe          Inhalt                              Quelle
==============  ==================================  =========================
lieferung       registrierte Quellen, Nachlieferung eingang.json, entscheide
bestand         Profil, Vorgeschichte, Vorfaelle    bestand.parquet, Abzuege
transformation  Feldabbildung, Verworfenes          transformation/*.json
parameter       Generation, Diskrepanzen, Belege    abox.json, Spez, Abgleich
abnahmen        Umfang, Toleranzen, Verteilungen    berichte/*.json
kette           Gate-Laeufe und Entscheide          diagnostics/, entscheide/
umbau           Umbaubudget des Fall-Laufs          berichte/umbaubudget.json
abgrenzungen    was die Zahlen NICHT sagen          abgeleitet aus obigem
==============  ==================================  =========================

Die letzte Gruppe ist die wichtigste und die einzige, die vergleicht
statt zu lesen: Eine Einschränkung entsteht dort, wo zwei Artefaktwerte
auseinanderfallen — Prüfgesamtheit gegen Bestandsgröße, ersetzte gegen
verglichene Prüfungen, abgedeckte gegen vorhandene Tarifzellen. Sie ist
damit kein Urteil des Verfassers, sondern ein Befund der Daten.

Aufruf::

    python werkzeuge/falldaten.py --fall faelle/<fall> --out falldaten.json
"""

from __future__ import annotations

import argparse
import collections
import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

#: Die drei aktuariellen Abnahmen mit dem Dateinamen des Gates.
ABNAHMEN = (
    ("A-M1", "aktuartest", "Stichtagstest"),
    ("A-M2", "aktuartest-A-M2", "Verlaufstest"),
    ("A-M3", "aktuartest-A-M3", "Geschaeftsvorfalltest"),
)


class FalldatenFehler(RuntimeError):
    """Der Fall gibt nicht her, was die Darstellung braucht."""


def _json(pfad: Path) -> Optional[Any]:
    try:
        return json.loads(pfad.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _kennzahlen(werte: List[float]) -> Dict[str, Any]:
    """Spannweite, Median und Quartile einer Groesse."""
    if not werte:
        return {}
    s = sorted(werte)
    return {
        "anzahl": len(s),
        "min": s[0],
        "max": s[-1],
        "median": statistics.median(s),
        "q1": s[len(s) // 4],
        "q3": s[(3 * len(s)) // 4],
        "summe": sum(s),
    }


# --------------------------------------------------------------------------- #
# A — Lieferung
# --------------------------------------------------------------------------- #

def lieferung(fall: Path) -> Dict[str, Any]:
    """Die registrierten Quellen — und welche davon NACHGEREICHT wurden.

    Nachgereicht heisst hier nicht "spaet registriert", sondern: registriert,
    nachdem der Fall bereits laief. Der Vergleich gegen den fruehesten
    Gate-Lauf macht den Nachfrage-Vorgang zu einer Tabelle statt zu einer
    Erzaehlung.
    """
    reg = _json(fall / "eingang.json") or {}
    quellen = sorted(reg.get("quellen", []), key=lambda q: str(q.get("datei", "")))

    # Fruehester Gate-Lauf des Falls: alles danach Registrierte kam nach.
    diagnostics = fall / "abgeleitet" / "diagnostics"
    starts = sorted(
        str(d.get("started_at"))
        for pfad in diagnostics.glob("*.gate.json")
        for d in [_json(pfad) or {}]
        if d.get("started_at")
    )
    erster_lauf = starts[0] if starts else None

    aus = []
    for q in quellen:
        wann = str(q.get("registriert_am") or "")
        aus.append({
            "datei": q.get("datei"),
            "bytes": q.get("bytes"),
            "sha256": q.get("sha256"),
            "registriert_am": wann or None,
            "nachgereicht": bool(erster_lauf and wann and wann > erster_lauf),
        })
    return {
        "anzahl": len(aus),
        "anzahl_nachgereicht": sum(1 for q in aus if q["nachgereicht"]),
        "erster_gate_lauf": erster_lauf,
        "quellen": aus,
        "gelesen_aus": ["eingang.json", "abgeleitet/diagnostics/*.gate.json"],
    }


# --------------------------------------------------------------------------- #
# B — Bestand
# --------------------------------------------------------------------------- #

def bestand(fall: Path, abzuege: List[str]) -> Dict[str, Any]:
    """Profil des uebernommenen Bestands aus dem ZIELmodell.

    Bewusst aus dem transformierten Bestand und nicht aus dem Abzug: Die
    Zielfelder heissen in jedem Fall gleich, die Quellspalten nicht. Nur so
    traegt das Modell auch die naechste Lieferung.
    """
    try:
        from rechner_pipeline.bestand.parquet_io import read_portfolio
    except ImportError as exc:  # pragma: no cover
        raise FalldatenFehler(f"Bestandsmodul nicht ladbar: {exc}") from exc

    pfad = fall / "abgeleitet" / "bestand" / "bestand.parquet"
    if not pfad.is_file():
        return {"vorhanden": False}
    df = read_portfolio(pfad)

    verteilungen = {}
    for spalte in ("sex", "status", "tarifart", "zahlweise", "produkt",
                   "tarif_generation", "status_code"):
        if spalte in df.columns:
            verteilungen[spalte] = {
                str(k): int(v) for k, v in
                sorted(collections.Counter(df[spalte]).items(),
                       key=lambda p: str(p[0]))
            }

    groessen = {}
    for spalte in ("entry_age", "duration", "premium_duration",
                   "sum_insured", "brutto_jahresbeitrag", "deckungskapital"):
        if spalte in df.columns:
            werte = [float(x) for x in df[spalte] if x == x]
            groessen[spalte] = _kennzahlen(werte)

    # Vorgeschichte und Vorfaelle aus den registrierten Listen.
    vorgeschichte = _gevo_zaehlung(fall, "gevo_metadaten")
    vorfaelle = _gevo_zaehlung(fall, "gevo_protokoll")

    aus = {
        "vorhanden": True,
        "anzahl": int(len(df)),
        "verteilungen": verteilungen,
        "groessen": groessen,
        "vorgeschichte": vorgeschichte,
        "vorfaelle_im_zeitraum": vorfaelle,
        "abzuege": _abzugssummen(fall, abzuege),
    }
    aus["kreuzproben"] = _kreuzproben(aus)
    aus["gelesen_aus"] = [
        "abgeleitet/bestand/bestand.parquet",
        *(f"eingang/{n}" for n in abzuege),
        *(f"eingang/{v['datei']}" for v in (vorgeschichte, vorfaelle)
          if v.get("datei")),
    ]
    return aus


def _gevo_zaehlung(fall: Path, muster: str) -> Dict[str, Any]:
    """Vorfaelle je Art aus einer registrierten Liste."""
    treffer = sorted((fall / "eingang").glob(f"*{muster}*.csv"))
    if not treffer:
        return {}
    with treffer[0].open(encoding="utf-8") as datei:
        zeilen = list(csv.DictReader(datei, delimiter=";"))
    if not zeilen:
        return {}
    art_spalte = next((s for s in zeilen[0] if s.upper() == "GEVO"), None)
    betrag_spalte = next((s for s in zeilen[0] if s.upper() == "BETRAG"), None)
    if art_spalte is None:
        return {}

    je_art: Dict[str, Dict[str, Any]] = {}
    for z in zeilen:
        art = z[art_spalte]
        e = je_art.setdefault(art, {"anzahl": 0, "betraege": []})
        e["anzahl"] += 1
        if betrag_spalte and z.get(betrag_spalte):
            try:
                e["betraege"].append(abs(float(z[betrag_spalte])))
            except ValueError:
                pass
    return {
        "datei": treffer[0].name,
        "anzahl": len(zeilen),
        "je_art": {
            art: {"anzahl": e["anzahl"],
                  **({"betrag_summe": sum(e["betraege"]),
                      "betrag_min": min(e["betraege"]),
                      "betrag_max": max(e["betraege"])} if e["betraege"] else {})}
            for art, e in sorted(je_art.items())
        },
    }


def _abzugssummen(fall: Path, abzuege: List[str]) -> List[Dict[str, Any]]:
    """Summen der gelieferten Abzuege je Stichtag — die Gegenprobe."""
    aus = []
    for name in abzuege:
        pfad = fall / "eingang" / name
        if not pfad.is_file():
            continue
        with pfad.open(encoding="utf-8") as datei:
            zeilen = list(csv.DictReader(datei, delimiter=";"))
        eintrag: Dict[str, Any] = {"datei": name, "zeilen": len(zeilen)}
        # Betragsspalten mit vollen Kennzahlen, nicht nur mit der Summe:
        # Das Deckungskapital und der Beitrag sind GELIEFERTE Groessen und
        # stehen nicht im gefuehrten Stamm — dort waeren sie eine Rechnung
        # des aufnehmenden Unternehmens und kein Bestandteil der Lieferung.
        for spalte in ("DECKKAP", "ERLSUMME", "JBRUTTO"):
            if not zeilen or spalte not in zeilen[0]:
                continue
            werte = []
            for z in zeilen:
                try:
                    werte.append(float(z[spalte] or 0))
                except ValueError:
                    pass
            kennzahlen = _kennzahlen(werte)
            if kennzahlen:
                kennzahlen["summe"] = round(kennzahlen["summe"], 2)
                eintrag[spalte.lower()] = kennzahlen
        aus.append(eintrag)
    return aus


def _kreuzproben(b: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Innere Stimmigkeit: Gehen die Vorfaelle in der Bestandsdifferenz auf?

    Das ist die staerkste Aussage des Bestandsteils, weil sie zwei
    unabhaengig gelieferte Dateien gegeneinander haelt.
    """
    proben = []
    abz = b.get("abzuege") or []
    arten = ((b.get("vorfaelle_im_zeitraum") or {}).get("je_art") or {})
    if len(abz) >= 2:
        differenz = abz[0]["zeilen"] - abz[1]["zeilen"]
        beendend = sum(arten.get(a, {}).get("anzahl", 0)
                       for a in ("STO", "TOD", "ABL"))
        proben.append({
            "was": "Abgaenge gegen beendende Vorfaelle",
            "links": differenz, "rechts": beendend,
            "stimmt": differenz == beendend,
        })
    return proben


# --------------------------------------------------------------------------- #
# B2 — Transformation
# --------------------------------------------------------------------------- #

def transformation(fall: Path) -> Dict[str, Any]:
    """Das Feldmapping: was wurde wie uebersetzt, was bewusst nicht.

    Der Uebersetzungsakt ist der fachliche Kern einer Migration — und die
    Stelle, an der ein Missverstaendnis nicht auffaellt, weil hinterher
    alles rechnet. Deshalb traegt das Modell nicht nur, WAS abgebildet
    wurde, sondern auch die Begruendung je Feld und die Spalten, die
    ausdruecklich draussen blieben.

    ``nicht_uebernommen`` wird ABGELEITET: Quellspalten minus alle, die in
    einem Mapping vorkommen. Eine stillschweigend vergessene Spalte sieht
    damit genauso aus wie eine bewusst weggelassene — und faellt auf.
    """
    verzeichnis = fall / "abgeleitet" / "transformation"
    if not verzeichnis.is_dir():
        return {"vorhanden": False}

    specs = sorted(verzeichnis.glob("*.spec.json"))
    # Der Dateiname des Ergebnisses ist eine Konvention, kein Vertrag:
    # Der Lauf haengt den Stichtag an, ein Test nicht.
    ergebnisse = sorted(verzeichnis.glob("ergebnis*.json"))
    if not specs:
        return {"vorhanden": False}

    spec = _json(specs[0]) or {}
    ergebnis = _json(ergebnisse[0]) if ergebnisse else {}
    ergebnis = ergebnis if isinstance(ergebnis, dict) else {}

    felder: List[Dict[str, Any]] = []
    nicht_uebernommen: List[Dict[str, Any]] = []
    genannte_quellen = set()
    for f in spec.get("felder", []):
        quellen = list(f.get("quellen") or [])
        genannte_quellen.update(quellen)
        eintrag = {
            "quellen": quellen,
            "begruendung": f.get("begruendung"),
        }
        # Die Nichtuebernahme ist DEKLARIERT, nicht abgeleitet: Der Spec
        # fuehrt sie als eigenen Feldtyp ohne Zielfeld. Das ist die
        # staerkere Form — sie zwingt zu einer Begruendung.
        if f.get("typ") == "nicht_uebernommen":
            nicht_uebernommen.append(eintrag)
        else:
            felder.append({
                **eintrag,
                "ziel": f.get("ziel"),
                "typ": f.get("typ"),
                "berechnung": f.get("berechnung") or None,
                "kodierung": f.get("kodierung") or None,
            })

    quellspalten = list(ergebnis.get("quellspalten") or [])
    # Was in KEINEM Eintrag vorkommt — weder abgebildet noch ausdruecklich
    # verworfen. Genau das ist der gefaehrliche Fall: eine Spalte, ueber
    # die niemand nachgedacht hat, sieht sonst aus wie eine bewusst
    # weggelassene.
    stumm = [s for s in quellspalten if s not in genannte_quellen]

    konflikte = [{
        "quellspalte": k.get("quellspalte"),
        "frage": k.get("frage"),
        "entscheidung": k.get("entscheidung"),
        "entscheider": k.get("entscheider"),
    } for k in spec.get("offene_konflikte", [])]

    return {
        "vorhanden": True,
        "quelle": spec.get("quelle_datei"),
        "akteur": spec.get("akteur"),
        "quellspalten": quellspalten,
        "anzahl_quellspalten": len(quellspalten),
        "felder": felder,
        "anzahl_zielfelder": len(felder),
        "nicht_uebernommen": nicht_uebernommen,
        "stumm_weggelassen": stumm,
        "abgeleitete_felder": [f["ziel"] for f in felder
                               if len(f["quellen"]) > 1
                               or (f.get("berechnung") or "").startswith(
                                   ("alter_", "jahre_"))],
        "konflikte": konflikte,
        "zeilen_quelle": ergebnis.get("zeilen_quelle"),
        "zeilen_ziel": ergebnis.get("zeilen_ziel"),
        "befunde": ergebnis.get("befunde") or [],
        "anmerkungen": spec.get("anmerkungen") or [],
        "gelesen_aus": [f"abgeleitet/transformation/{specs[0].name}"]
                       + ([f"abgeleitet/transformation/{ergebnisse[0].name}"]
                          if ergebnisse else []),
    }


# --------------------------------------------------------------------------- #
# C — Parametrierung und Diskrepanzen
# --------------------------------------------------------------------------- #

def parameter(fall: Path) -> Dict[str, Any]:
    """Generation, aufgeloeste Diskrepanzen und ihre Belege."""
    abox = _json(fall / "abgeleitet" / "abox" / "abox.json") or {}
    generationen = [g.get("id") for g in abox.get("generationen", [])]

    diskrepanzen = []
    for d in abox.get("diskrepanzen", []):
        entscheidung = d.get("entscheidung") or {}
        lesarten = d.get("lesarten") or []
        diskrepanzen.append({
            "id": d.get("id"),
            "knoten": d.get("knoten"),
            "feld": d.get("feld"),
            "status": d.get("status"),
            "lesarten": [
                {"wert": l.get("wert"), "quelle": l.get("quelle"),
                 "fundstelle": l.get("fundstelle")}
                for l in lesarten
            ],
            "gewaehlt": entscheidung.get("wert"),
            "entscheider": entscheidung.get("entscheider"),
            "vorlaeufig": entscheidung.get("vorlaeufig"),
            "begruendung": entscheidung.get("begruendung"),
        })

    belege = _belege(fall)
    return {
        "generationen": generationen,
        "diskrepanzen": diskrepanzen,
        "anzahl_diskrepanzen": len(diskrepanzen),
        "belege": belege,
        "gelesen_aus": ["abgeleitet/abox/abox.json"]
                       + [f"abgeleitet/berichte/{n}" for n in sorted(belege)],
    }


def _belege(fall: Path) -> Dict[str, Any]:
    """Deterministische Belegrechnungen des Falls, falls vorhanden.

    Sie sind das Rueckgrat der Fundtabelle: je Lesart die Zahl der
    stuetzenden und verletzten Belege. Ohne sie bliebe eine Diskrepanz
    eine Behauptung ueber zwei Dokumente.
    """
    aus: Dict[str, Any] = {}
    berichte = fall / "abgeleitet" / "berichte"
    for name, schluessel in (("abzugsabgleich.json", "abgleiche"),
                             ("erhoehungssatz.json", "kandidaten")):
        d = _json(berichte / name)
        if not isinstance(d, dict):
            continue
        aus[name] = {
            "gegenstand": d.get("gegenstand") or d.get("beleggroesse"),
            "belegmenge": d.get("belegmenge") or d.get("belegquelle"),
            "reihenfolge": d.get("reihenfolge"),
            schluessel: d.get(schluessel),
            "hashgebunden": False,  # siehe Abgrenzungen
        }
    return aus


# --------------------------------------------------------------------------- #
# D — Abnahmen
# --------------------------------------------------------------------------- #

def abnahmen(fall: Path) -> Dict[str, Any]:
    """Die drei aktuariellen Abnahmen und das Controlling."""
    berichte = fall / "abgeleitet" / "berichte"
    aus: Dict[str, Any] = {"aktuariell": [], "controlling": None}

    for kennung, datei, titel in ABNAHMEN:
        d = _json(berichte / f"{datei}.json")
        if not isinstance(d, dict):
            continue
        stichprobe = d.get("stichprobe") or {}
        profil = d.get("profil") or {}
        aus["aktuariell"].append({
            "kennung": kennung,
            "titel": profil.get("titel") or titel,
            # Verweis auf die HTML-Vorlage des Gates, fallrelativ. Das
            # Modell LISTET nur; ob ein Verweis eine Veroeffentlichung
            # erreicht, entscheidet der Konsument (Regie-Sperre der
            # Vorzeigeseite) — die Liste hier ist kein Weg daran vorbei.
            "bericht": (f"abgeleitet/berichte/{datei}.html"
                        if (berichte / f"{datei}.html").is_file() else None),
            "anzahl": d.get("anzahl"),
            "bestanden": d.get("bestanden"),
            "fehlgeschlagen": d.get("fehlgeschlagen"),
            "urteil": d.get("test_bestanden"),
            "stichprobe": {
                "profil": stichprobe.get("profil"),
                "umfang": stichprobe.get("umfang"),
                "grundgesamtheit": stichprobe.get("grundgesamtheit"),
                "vollerhebung": stichprobe.get("vollerhebung"),
                "parameter": stichprobe.get("parameter"),
            },
            "grundtoleranz": profil.get("grundtoleranz"),
            "kriterien": profil.get("kriterien"),
            "verteilung": d.get("verteilung"),
            "je_groesse": d.get("nach_kriterium"),
            "je_anlass": d.get("nach_anlass"),
            "je_schicht": d.get("gruppen"),
            "plausibilitaets_pruefungen": d.get("plausibilitaets_pruefungen", 0),
            "plausibilitaet_vertraege": len(
                d.get("plausibilitaet_statt_vergleich") or {}),
            "red_verfahren": d.get("red_verfahren"),
            "grenzbefunde": d.get("grenzbefunde"),
            "mengenbefunde": d.get("mengenbefunde"),
            "lieferung": (d.get("transportsicherung") or {}).get("lieferung"),
        })

    s = _json(berichte / "migrationssuite.json")
    if isinstance(s, dict):
        aus["controlling"] = {
            "anzahl": s.get("anzahl"),
            "erwartete_anzahl": s.get("erwartete_anzahl"),
            "bestanden": s.get("bestanden"),
            "fehlgeschlagen": s.get("fehlgeschlagen"),
            "urteil": s.get("suite_bestanden"),
            "vollstaendig_geprueft": s.get("vollstaendig_geprueft"),
            "pruefluecken": len(s.get("pruefluecken") or []),
            "stichtag_1": s.get("stichtag_1"),
            "stichtag_2": s.get("stichtag_2"),
            "je_groesse": _suite_achsen(s),
        }
    aus["bestandsberichte"] = sorted(
        f"abgeleitet/berichte/{p.name}"
        for p in berichte.glob("bestandsbericht*.html")
    ) if berichte.is_dir() else []
    aus["gelesen_aus"] = [
        f"abgeleitet/berichte/{datei}.json"
        for _, datei, _ in ABNAHMEN
        if (berichte / f"{datei}.json").is_file()
    ] + (["abgeleitet/berichte/migrationssuite.json"]
         if (berichte / "migrationssuite.json").is_file() else [])
    return aus


def _suite_achsen(suite: Dict[str, Any]) -> Dict[str, int]:
    """Wie viele Vergleiche je Pruefgroesse — macht die Achsen sichtbar.

    Ohne diese Zaehlung liest sich "500 von 500 ueber zwei Stichtage" so,
    als waeren beide Stichtage gleich tief geprueft. Sie sind es nicht.
    """
    zaehler: collections.Counter = collections.Counter()
    for v in suite.get("vertraege", []):
        for p in v.get("pruefungen", []):
            name = p.get("groesse") or p.get("name")
            if name:
                zaehler[str(name)] += 1
    return dict(sorted(zaehler.items()))


# --------------------------------------------------------------------------- #
# E — Kette und Entscheide
# --------------------------------------------------------------------------- #

def kette(fall: Path) -> Dict[str, Any]:
    """Gate-Laeufe und menschliche Entscheide."""
    diagnostics = fall / "abgeleitet" / "diagnostics"
    gates = []
    for pfad in sorted(diagnostics.glob("*.gate.json")):
        d = _json(pfad) or {}
        gates.append({
            "kommando": d.get("command"),
            "gate": d.get("gate"),
            "status": d.get("status"),
            "gestartet": d.get("started_at"),
            "versuch": d.get("attempt"),
            "pb1_umfang": (d.get("summary") or {}).get("pb1_umfang"),
        })
    gates.sort(key=lambda g: (str(g["gestartet"]), str(g["kommando"])))

    entscheide = []
    for pfad in sorted((fall / "entscheide").glob("*.json")):
        d = _json(pfad) or {}
        freigabe = d.get("freigabe") or {}
        entscheide.append({
            "gate": d.get("gate"),
            "entscheid": d.get("entscheid"),
            "rolle": d.get("rolle"),
            "entscheider": d.get("entscheider"),
            "entschieden_am": d.get("entschieden_am"),
            "schluessel_sha256": (freigabe.get("schluessel_sha256") or "")[:16],
            "pflichtbelege": sorted(d.get("pflichtbelege") or {}),
            "artefakte_gebunden": len(d.get("artefakt_hashes") or {}),
            "begruendung": d.get("begruendung"),
        })
    entscheide.sort(key=lambda e: str(e["entschieden_am"]))

    systemstaende = sorted({
        json.dumps(d.get("system"), sort_keys=True)
        for pfad in (fall / "entscheide").glob("*.json")
        for d in [_json(pfad) or {}]
        if d.get("system")
    })
    return {
        "gates": gates,
        "entscheide": entscheide,
        "anzahl_gate_laeufe": len(gates),
        "systemstaende_der_entscheide": len(systemstaende),
        "gelesen_aus": ["abgeleitet/diagnostics/*.gate.json",
                        "entscheide/*.json"],
    }


# --------------------------------------------------------------------------- #
# F — Umbau
# --------------------------------------------------------------------------- #

def umbau(fall: Path) -> Dict[str, Any]:
    """Wie weit der Lauf das Zielsystem umgebaut hat.

    Das Budget begrenzt die Arbeit des Operators WAEHREND des Fall-Laufs
    und ist damit eine Eigenschaft der Fall-Arbeit — deshalb gehoert es
    zum Fall. Es entsteht aber nur, wenn jemand es erhoben und in den
    Fall geschrieben hat (``umbaubudget.py --json``); sein Fehlen ist
    keine Luecke des Falls, sondern eine nicht durchgefuehrte Messung.
    """
    d = _json(fall / "abgeleitet" / "berichte" / "umbaubudget.json")
    if not isinstance(d, dict):
        return {"vorhanden": False}
    return {
        "vorhanden": True,
        "basis": d.get("basis"),
        "gesamt": d.get("gesamt"),
        "befunde": d.get("befunde") or [],
        "stolperdraehte": [s.get("datei")
                           for s in d.get("stolperdraehte") or []],
        "ueberschreitung_begruendet": d.get("ueberschreitung_begruendet"),
        "gelesen_aus": ["abgeleitet/berichte/umbaubudget.json"],
    }


# --------------------------------------------------------------------------- #
# G — Abgrenzungen (abgeleitet)
# --------------------------------------------------------------------------- #

def abgrenzungen(modell: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Was die Zahlen NICHT sagen — durch Vergleich, nicht durch Meinung.

    Jede Einschraenkung entsteht, wo zwei Werte des Modells auseinander
    fallen. Deshalb kann sie beim naechsten Lauf verschwinden, ohne dass
    jemand einen Satz streichen muss.
    """
    aus: List[Dict[str, Any]] = []
    b = modell.get("bestand") or {}
    a = modell.get("abnahmen") or {}

    bestandsgroesse = b.get("anzahl")
    for t in a.get("aktuariell", []):
        stichprobe = t.get("stichprobe") or {}
        gg = stichprobe.get("grundgesamtheit")
        # Eine Vollerhebung hat ihre eigene Grundgesamtheit — der
        # Geschaeftsvorfalltest prueft ALLE Vorfaelle, nicht alle
        # Vertraege. Sie mit der Bestandsgroesse zu vergleichen erzeugte
        # eine Einschraenkung, die keine ist.
        if stichprobe.get("vollerhebung"):
            continue
        if bestandsgroesse and gg and gg != bestandsgroesse:
            aus.append({
                "sicht": "fachlich", "abnahme": t["kennung"],
                "was": "Pruefgesamtheit kleiner als der Bestand",
                "zahlen": f"{gg} von {bestandsgroesse}",
            })
        ersetzt = t.get("plausibilitaets_pruefungen") or 0
        if ersetzt:
            gesamt = (t.get("verteilung") or {}).get("anzahl_werte") or 0
            aus.append({
                "sicht": "fachlich", "abnahme": t["kennung"],
                "was": "Wertvergleich durch Plausibilitaetspruefung ersetzt",
                "zahlen": f"{ersetzt} von {gesamt + ersetzt} Pruefungen, "
                          f"{t.get('plausibilitaet_vertraege')} Vertraege",
            })

    c = a.get("controlling") or {}
    achsen = c.get("je_groesse") or {}
    if achsen:
        eins = sorted(k for k in achsen if k.endswith("_1"))
        zwei = sorted(k for k in achsen if k.endswith("_2"))
        if len(eins) != len(zwei):
            aus.append({
                "sicht": "fachlich", "abnahme": "A-M4",
                "was": "Die Stichtage sind unterschiedlich tief geprueft",
                "zahlen": f"{len(eins)} Groesse(n) am ersten, "
                          f"{len(zwei)} am zweiten Stichtag",
            })
        # Nicht jeder Vertrag erreicht den zweiten Stichtag. Die Differenz
        # ist sachlich richtig (Abgaenge werden am Abgangsbetrag geprueft),
        # taucht aber in keiner Luecken-Liste auf — der Bericht sagt
        # "vollstaendig geprueft" und meint "keine registrierte Luecke".
        breiteste = max((achsen[k] for k in eins), default=0)
        for k in zwei:
            if breiteste and achsen[k] < breiteste:
                aus.append({
                    "sicht": "fachlich", "abnahme": "A-M4",
                    "was": f"{k} liegt nicht fuer jeden Vertrag vor",
                    "zahlen": f"{achsen[k]} von {breiteste}",
                })

    tr = modell.get("transformation") or {}
    if tr.get("vorhanden"):
        quelle, ziel = tr.get("zeilen_quelle"), tr.get("zeilen_ziel")
        if quelle and ziel and quelle != ziel:
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Die Transformation hat Zeilen verloren",
                "zahlen": f"{ziel} von {quelle}",
            })
        # Eine Spalte, die weder abgebildet noch ausdruecklich verworfen
        # wurde, ist der gefaehrliche Fall — ueber sie hat niemand
        # nachgedacht, und im Ergebnis sieht das aus wie Absicht.
        if tr.get("stumm_weggelassen"):
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Quellspalten weder abgebildet noch ausdruecklich verworfen",
                "zahlen": ", ".join(tr["stumm_weggelassen"]),
            })
        ohne_grund = [n for n in tr.get("nicht_uebernommen") or []
                      if not n.get("begruendung")]
        if ohne_grund:
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Nichtuebernahme ohne Begruendung",
                "zahlen": ", ".join(
                    ", ".join(n.get("quellen") or []) for n in ohne_grund),
            })

    for name, beleg in (modell.get("parameter") or {}).get("belege", {}).items():
        if beleg.get("hashgebunden") is False:
            aus.append({
                "sicht": "technisch", "abnahme": None,
                "was": f"Belegrechnung {name} ist an keine Pruefsumme gebunden",
                "zahlen": None,
            })

    # Was die Bestandspruefung NICHT gesehen hat. Das A-M4-Ledger weist
    # den Umfang aus; hier wird daraus eine benannte Einschraenkung.
    for g in (modell.get("kette") or {}).get("gates", []):
        umfang = (g.get("pb1_umfang") or {})
        if umfang and not umfang.get("bewegungskonto_geprueft"):
            aus.append({
                "sicht": "technisch", "abnahme": "A-M4",
                "was": "Das Bewegungskonto wurde nicht geprueft",
                "zahlen": "P-B1 sah " + ", ".join(umfang.get("geprueft") or []),
            })

    k = modell.get("kette") or {}
    if k.get("systemstaende_der_entscheide", 0) > 1:
        aus.append({
            "sicht": "technisch", "abnahme": None,
            "was": "Die Entscheide beruhen auf verschiedenen Systemstaenden",
            "zahlen": f"{k['systemstaende_der_entscheide']} Staende",
        })
    return aus


# --------------------------------------------------------------------------- #

#: Was ein abgeschlossener Fall im Bestands-Scope tragen MUSS. Fehlt
#: etwas davon, ist das eine Luecke des Falls oder eine Formaenderung der
#: Pipeline — beides muss auffallen, statt einen Abschnitt still
#: verschwinden zu lassen.
ERWARTET = (
    ("lieferung", "quellen", "registrierte Quellen"),
    ("bestand", "anzahl", "uebernommener Bestand"),
    ("transformation", "felder", "Feldabbildung"),
    ("parameter", "generationen", "Tarifgeneration der A-Box"),
    ("abnahmen", "aktuariell", "aktuarielle Abnahmen"),
    ("kette", "entscheide", "menschliche Entscheide"),
)


def luecken(modell: Dict[str, Any]) -> List[Dict[str, str]]:
    """Was der Extraktor erwartet und NICHT gefunden hat.

    Der Bericht ist Konsument der Pipeline, nicht ihr Vertragsgeber: Er
    liest, was ohnehin entsteht, und verlangt von niemandem, etwas fuer
    ihn aufzuschreiben. Der Preis dafuer ist, dass eine Formaenderung ihn
    treffen kann — also muss sie WEHTUN. Ein stumm fehlender Abschnitt
    waere die schlechteste aller Varianten: Die Darstellung saehe
    vollstaendig aus und waere es nicht.
    """
    aus: List[Dict[str, str]] = []
    for gruppe, feld, was in ERWARTET:
        inhalt = modell.get(gruppe) or {}
        if not inhalt.get(feld):
            aus.append({
                "gruppe": gruppe, "feld": feld, "was": was,
                "wirkung": "Der Abschnitt fehlt in der Darstellung.",
            })
    return aus


def sammle(fall: Path, abzuege: List[str]) -> Dict[str, Any]:
    manifest = _json(fall / "fall.json") or {}
    modell: Dict[str, Any] = {
        "schema_version": 1,
        "fall": {
            "name": manifest.get("name") or fall.name,
            "beschreibung": manifest.get("beschreibung") or None,
            "scope": (manifest.get("scope") or {}).get("typ"),
        },
        "lieferung": lieferung(fall),
        "bestand": bestand(fall, abzuege),
        "transformation": transformation(fall),
        "parameter": parameter(fall),
        "abnahmen": abnahmen(fall),
        "kette": kette(fall),
        "umbau": umbau(fall),
    }
    modell["abgrenzungen"] = abgrenzungen(modell)
    modell["luecken"] = luecken(modell)
    return modell


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/falldaten.py",
        description="Datenmodell einer Falldarstellung aus den Artefakten "
                    "(Beobachtungshilfe, kein Gate).")
    p.add_argument("--fall", required=True)
    p.add_argument("--abzug", action="append", default=[],
                   help="Registrierter Bestandsabzug je Stichtag, "
                        "in zeitlicher Reihenfolge (mehrfach angebbar)")
    p.add_argument("--out", default=None, help="Zieldatei (Vorgabe: stdout)")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2
    try:
        modell = sammle(fall, args.abzug)
    except FalldatenFehler as exc:
        print(f"Nicht erhebbar: {exc}", file=sys.stderr)
        return 2

    text = json.dumps(modell, indent=2, ensure_ascii=False, sort_keys=True,
                      default=str) + "\n"
    if args.out:
        ziel = Path(args.out)
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(text, encoding="utf-8")
        felder = sum(1 for _ in text.splitlines())
        print(f"{ziel}  ({felder} Zeilen, "
              f"{len(modell['abgrenzungen'])} Abgrenzungen abgeleitet)")
    else:
        sys.stdout.write(text)

    # Fehlende Abschnitte gehen nach stderr und setzen den Exit-Code. Das
    # Modell wird trotzdem geschrieben: Wer die Luecke beheben will,
    # braucht zuerst das, was da ist.
    for l in modell["luecken"]:
        print(f"  LUECKE: {l['was']} nicht gefunden "
              f"({l['gruppe']}.{l['feld']}) — {l['wirkung']}",
              file=sys.stderr)
    return 3 if modell["luecken"] else 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
