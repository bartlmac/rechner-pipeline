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
import datetime as _dt
import csv
import hashlib
import json
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

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
        herkunft = str(q.get("quelle_pfad") or "")
        aus.append({
            "datei": q.get("datei"),
            "bytes": q.get("bytes"),
            "sha256": q.get("sha256"),
            "registriert_am": wann or None,
            "nachgereicht": bool(erster_lauf and wann and wann > erster_lauf),
            # Registriert, aber aus dem EIGENEN Arbeitsbereich des Falls
            # (etwa eine Festlegung des uebernehmenden Hauses): keine
            # Unterlage der abgebenden Gesellschaft. Gelesen am Herkunfts-
            # pfad, den das Register selbst fuehrt.
            "eigenes_haus": f"faelle/{fall.name}/" in herkunft.replace("\\", "/"),
        })
    return {
        "anzahl": len(aus),
        "anzahl_nachgereicht": sum(1 for q in aus if q["nachgereicht"]),
        "anzahl_eigenes_haus": sum(1 for q in aus if q["eigenes_haus"]),
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
            "was": "Abgänge gegen beendende Vorfälle",
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
    # Der Dateiname des Ergebnisses ist eine Konvention, kein Vertrag —
    # und die Konvention hat sich bewegt: Lauf 1 schrieb
    # ergebnis[-<stichtag>].json, Lauf 2 schreibt <quelle>.ergebnis.json.
    # Der Leser akzeptiert beide.
    ergebnisse = sorted(set(verzeichnis.glob("ergebnis*.json"))
                        | set(verzeichnis.glob("*.ergebnis.json")))
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

def _lesart(l: Dict[str, Any]) -> Dict[str, Any]:
    """Eine Lesart samt Herkunft.

    Quelle und Fundstelle stehen in der A-Box nicht am Wert, sondern in
    seiner Provenienz-Liste (erster Eintrag: wer den Wert wo erhoben
    hat). Ohne diese Herkunft bliebe "1,25 gegen 1,75" eine Behauptung
    ueber zwei Zahlen statt ueber zwei Dokumente.
    """
    prov = (l.get("provenienz") or [{}])[0]
    return {
        "wert": l.get("wert"),
        "quelle": l.get("quelle") or prov.get("quelle_datei"),
        "fundstelle": l.get("fundstelle") or prov.get("fundstelle"),
    }


def _golden_master(fall: Path) -> Dict[str, Any]:
    """Die Nachrechnung des Quell-Tarifrechners aus dem P-K1-Ledger.

    "616/616" steht sonst nur in Entscheid-Begruendungen; das Ledger
    traegt die Zahlen strukturiert — samt der ehrlichen Angabe, wie
    viele Tarifzellen ueberhaupt Erwartungswerte hatten.
    """
    for pfad in sorted((fall / "abgeleitet" / "diagnostics").glob("*.gate.json")):
        d = _json(pfad) or {}
        if not str(d.get("gate", "")).endswith("golden-master"):
            continue
        s = d.get("summary") or {}
        return {
            "vorhanden": True,
            "generation": s.get("generation"),
            "werte_verglichen": s.get("werte_verglichen"),
            "abweichungen": s.get("abweichungen"),
            "skalare_verglichen": s.get("skalare_verglichen"),
            "tabellen_zeilen": s.get("tabellen_zeilen"),
            "zellen_gesamt": s.get("zellen_gesamt"),
            "zellen_ohne_erwartungswerte": len(
                s.get("zellen_ohne_erwartungswerte") or []),
            # Fuer den Vergleich rechnet der Kern mit der Lesart des
            # Rechners; wo die entschiedene Spez davon abweicht, steht es
            # hier je Feld (rechner_wert gegen spez_wert).
            "gegenprobe": {str(f): {"rechner_wert": v.get("rechner_wert"),
                                    "spez_wert": v.get("spez_wert")}
                           for f, v in (s.get("gegenprobe_gegen_rechner_lesart") or {}).items()
                           if isinstance(v, dict)},
            "status": d.get("status"),
            "ledger": f"abgeleitet/diagnostics/{pfad.name}",
        }
    return {"vorhanden": False}


def _deckung(fall: Path) -> Dict[str, Any]:
    """Die Deckungsmessung der Faktenbasis (abgeleitet/abox/coverage.json):
    Pflichtfelder aus der T-Box mal Zellen aus den Quellen, je Zustand
    gezaehlt — Vollstaendigkeit wird gezaehlt, nicht behauptet."""
    cov = _json(fall / "abgeleitet" / "abox" / "coverage.json") or {}
    gens = cov.get("generationen") or []
    if not gens:
        return {"vorhanden": False}
    g = gens[0]
    return {
        "vorhanden": True,
        "generation": g.get("generation"),
        "pflichtfelder": g.get("pflichtfelder"),
        "zellen": len(g.get("zellen") or {}),
        "pflicht_gesamt": g.get("pflicht_gesamt"),
        "belegt_quote": g.get("belegt_quote"),
        "zaehler": dict(g.get("zaehler") or {}),
        "vollstaendig": bool(g.get("vollstaendig")),
        "tbox_version": cov.get("tbox_version"),
    }


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
            "lesarten": [_lesart(l) for l in lesarten],
            # Die A-Box nennt den gewaehlten Wert "gewaehlter_wert";
            # aeltere Faelle schrieben "wert".
            "gewaehlt": entscheidung.get("gewaehlter_wert",
                                         entscheidung.get("wert")),
            "entscheider": entscheidung.get("entscheider"),
            "entschieden_am": entscheidung.get("entschieden_am"),
            "vorlaeufig": entscheidung.get("vorlaeufig"),
            "begruendung": entscheidung.get("begruendung"),
        })

    belege = _belege(fall)
    golden = _golden_master(fall)
    return {
        "generationen": generationen,
        "deckung": _deckung(fall),
        "diskrepanzen": diskrepanzen,
        "anzahl_diskrepanzen": len(diskrepanzen),
        "belege": belege,
        "golden_master": golden,
        "gelesen_aus": ["abgeleitet/abox/abox.json"]
                       + [f"abgeleitet/berichte/{n}" for n in sorted(belege)]
                       + ([golden["ledger"]] if golden.get("ledger") else []),
    }


def _belege(fall: Path) -> Dict[str, Any]:
    """Deterministische Belegrechnungen des Falls, falls vorhanden.

    Sie sind das Rueckgrat der Fundtabelle: je Lesart die Zahl der
    stuetzenden und verletzten Belege. Ohne sie bliebe eine Diskrepanz
    eine Behauptung ueber zwei Dokumente.
    """
    import hashlib

    aus: Dict[str, Any] = {}
    berichte = fall / "abgeleitet" / "berichte"
    # Gebunden ist eine Belegrechnung, wenn eine Entscheidung der A-Box sie
    # mit Pfad UND Pruefsumme nennt — und die Datei genau diese Bytes hat.
    # Die A-Box selbst bindet die Quellenabnahme (A-Q1) ueber ihren Hash.
    abox = _json(fall / "abgeleitet" / "abox" / "abox.json") or {}
    genannt = {(str((d.get("entscheidung") or {}).get("beleg", {}).get("datei")),
                str((d.get("entscheidung") or {}).get("beleg", {}).get("sha256")))
               for d in abox.get("diskrepanzen") or [] if isinstance(d, dict)
               and isinstance((d.get("entscheidung") or {}).get("beleg"), dict)}
    for name, schluessel in (("abzugsabgleich.json", "abgleiche"),
                             ("erhoehungssatz.json", "kandidaten")):
        d = _json(berichte / name)
        if not isinstance(d, dict):
            continue
        h = hashlib.sha256((berichte / name).read_bytes()).hexdigest()
        aus[name] = {
            "gegenstand": d.get("gegenstand") or d.get("beleggroesse"),
            "belegmenge": d.get("belegmenge") or d.get("belegquelle"),
            "reihenfolge": d.get("reihenfolge"),
            schluessel: d.get(schluessel),
            "hashgebunden": (f"abgeleitet/berichte/{name}", h) in genannt,
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
            "verteilung": _suite_verteilung(s),
        }
    # Der Anker ist der DATEINAME, nicht das Verzeichnis: Ein
    # Bestandsbericht heisst in jedem Erzeuger bestandsbericht*.html,
    # die Verzeichnisse darunter wechseln (berichte/ fuer die
    # Vergleichsberichte, bestand-nach/ fuer die Fortschreibung).
    abgeleitet = fall / "abgeleitet"
    aus["bestandsberichte"] = sorted(
        str(p.relative_to(fall))
        for p in abgeleitet.rglob("bestandsbericht*.html")
    ) if abgeleitet.is_dir() else []
    aus["kernstand"] = kernstand(fall)
    aus["standabnahmen"] = standabnahmen(fall)
    aus["gelesen_aus"] = [
        f"abgeleitet/berichte/{datei}.json"
        for _, datei, _ in ABNAHMEN
        if (berichte / f"{datei}.json").is_file()
    ] + (["abgeleitet/berichte/migrationssuite.json"]
         if (berichte / "migrationssuite.json").is_file() else []) + (
        (aus["kernstand"] or {}).get("gelesen_aus") or [])
    return aus


def _suite_verteilung(suite: Dict[str, Any]) -> Dict[str, Any]:
    """Residuen-Verteilung des Controllings, wie bei den Aktuartests.

    Die Suite traegt je Pruefung das Residuum, aber keine Verteilung;
    ohne sie stuende das Controlling als einzige Abnahme nur mit
    Zaehlung da — "834/834" ohne die Frage, wie knapp.
    """
    werte = sorted(
        abs(float(p["residuum"]))
        for v in suite.get("vertraege", [])
        for p in v.get("pruefungen", [])
        if p.get("residuum") is not None)
    if not werte:
        return {}
    return {
        "anzahl_werte": len(werte),
        "max_abs_residuum": werte[-1],
        "p95_abs_residuum": werte[min(len(werte) - 1, int(0.95 * len(werte)))],
        "p99_abs_residuum": werte[min(len(werte) - 1, int(0.99 * len(werte)))],
        "summe_abs_residuum": sum(werte),
    }


def standabnahmen(fall: Path) -> List[Dict[str, Any]]:
    """Je Gegenstand, den A-M4 verlangt (Kernstand A-K2, T-Box-Stand A-O1,
    Tarifwerk A-T1), auf welchem Weg der Stand des Falls abgenommen ist —
    woertlich aus dem A-M4-Snapshot, der es signiert (ADR-018, Nachtrag
    2026-10-01; ADR-025): "abgenommen im Fall" oder "keine Aenderung seit
    Abnahme <snapshot> (<Herkunft>)" — die Herkunft nennt die Linie der
    Erstabnahme oder einen frueheren Fall; aeltere Snapshots fuehren noch die
    Basislinie der T-Box. Gelesen wird der juengste strukturell unversehrte,
    angenommene A-M4-Snapshot; die Signatur prueft dieses Werkzeug nicht
    (T19-02)."""
    from rechner_pipeline.models import standabnahme as sa

    kandidaten = []
    for pfad in sorted((fall / "entscheide").glob("A-M4-*.json")):
        d = _json(pfad)
        if (isinstance(d, dict) and d.get("entscheid") == "angenommen"
                and not _verifiziere_snapshot(d, pfad.name)):
            kandidaten.append(d)
    if not kandidaten:
        return []
    juengster = max(kandidaten, key=lambda d: str(d.get("entschieden_am")))
    eintraege = juengster.get("standabnahmen") or {}
    return [{"gate": g.gate, "titel": g.titel,
             "weg": (eintraege.get(g.rolle) or {}).get("weg"),
             "anzeige": (eintraege.get(g.rolle) or {}).get("anzeige")
             or "im Snapshot nicht ausgewiesen (Schema vor 8 bzw. vor 9)"}
            for g in sa.AM4_GEGENSTAENDE]


def kernstand(fall: Path) -> Optional[Dict[str, Any]]:
    """Die Kernabnahme A-K2 des Falls: was sich am Rechenkern seit dem
    zuletzt abgenommenen Kernstand geaendert hat, und was die Zeichnung
    NICHT deckt (ADR-018, Nachtrag 2026-10-01).

    Die Regression steht hier so, wie der Beleg sie fuehrt — als benannte
    Ausnahme, solange das Werkzeug fehlt, woertlich aus
    ``models.kernabnahme``; nie als Urteil.
    """
    from rechner_pipeline.models import kernabnahme as ka

    d = _json(fall / ka.AENDERUNG_RELATIV)
    if not isinstance(d, dict):
        return None
    r = _json(fall / ka.REGRESSION_RELATIV)
    git = d.get("git") if isinstance(d.get("git"), dict) else {}
    module = [m for m in d.get("module") or [] if isinstance(m, dict)]
    geaendert = [str(m.get("modul")) for m in module
                 if m.get("hinzu") or m.get("weg") or m.get("commits")
                 or m.get("nicht_committet")]
    if ka.ist_ausnahme(r):
        regression = ka.ANZEIGE_REGRESSION
    elif isinstance(r, dict):
        regression = (f"Regression: {r.get('vertraege_geprueft')} von "
                      f"{r.get('vertraege_gesamt')} Vertraegen durchgerechnet, "
                      f"{len(r.get('abweichungen') or [])} Abweichung(en)")
    else:
        regression = "Regression: kein Beleg"
    return {
        "von": git.get("referenz"),
        "von_commit": str(git.get("referenz_commit") or "")[:12],
        "von_version": d.get("von_version"),
        "nach_version": d.get("nach_version"),
        "veraendert": d.get("veraendert"),
        "module": len(module),
        "module_geaendert": geaendert,
        "commits": len(d.get("commits") or []),
        "regression": regression,
        "deckung": ka.DECKUNG_UNTER_AUSNAHME if ka.ist_ausnahme(r) else None,
        "sicht": (ka.SICHT_RELATIV if (fall / ka.SICHT_RELATIV).is_file() else None),
        "gelesen_aus": [p for p in (ka.AENDERUNG_RELATIV, ka.REGRESSION_RELATIV)
                        if (fall / p).is_file()],
    }


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

def _verifiziere_snapshot(daten: Any, dateiname: str) -> List[str]:
    """Einen Entscheid-Snapshot pruefen, soweit es ohne Schluessel geht.

    Externes Review T19-02: Dieses Werkzeug las die Dateien roh und die
    Darstellung nannte sie "gezeichnet" — eine frei erfundene Datei
    erschien so als Abnahme. Geprueft werden jetzt Schema,
    Selbstadressierung und Dateiname (``gates.gate_entscheid``); die
    SIGNATUR bleibt ungeprueft, denn Schluesselmaterial gehoert nicht in
    ein Darstellungswerkzeug. Wer diese Ausgabe rendert, schreibt
    deshalb "Signatur hier nicht verifiziert" — nie "gezeichnet".

    Faellt der Import aus (Werkzeug ohne installiertes Paket), ist das
    ein BEFUND und kein stilles Durchwinken.
    """
    try:
        from rechner_pipeline.gates.gate_entscheid import (
            pruefe_snapshot_ohne_schluessel,
        )
    except ImportError as exc:  # pragma: no cover - Umgebungsfehler
        return [f"Verifikation nicht moeglich (Paket fehlt): {exc}"]
    return list(pruefe_snapshot_ohne_schluessel(daten, dateiname))


def _staende_der_abnahmen(entscheide: List[Dict[str, Any]],
                          rohe: List[Tuple[Path, Dict[str, Any]]]) -> int:
    """Auf wie vielen Systemstaenden die GELTENDEN Abnahmen liegen — nach
    Commit und Quellcode-Hash, nicht nach dem ganzen system-Objekt (ein
    anderer Zweigname ist kein anderer Stand). Der Fallauftrag (A-M6) zaehlt
    nicht: Er bindet die Lieferung, nicht den Stand."""
    roh_je_datei = {f"entscheide/{pfad.name}": d for pfad, d in rohe}
    return len({(str(s.get("commit") or ""), str(s.get("quellcode_sha256") or ""))
                for e in entscheide if e.get("geltend") and str(e["gate"]) != "A-M6"
                for s in [(roh_je_datei.get(e["snapshot_datei"]) or {}).get("system") or {}]
                if s})


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
            "ledger": f"abgeleitet/diagnostics/{pfad.name}",
            "pb1_umfang": (d.get("summary") or {}).get("pb1_umfang"),
        })
    gates.sort(key=lambda g: (str(g["gestartet"]), str(g["kommando"])))

    rohe = [(pfad, d)
            for pfad in sorted((fall / "entscheide").glob("*.json"))
            for d in [_json(pfad)] if isinstance(d, dict)]

    # Finale Zeichnungskette, ABGELEITET statt kuratiert: Der juengste
    # Abschluss-Snapshot (A-M4) bindet in seinen Pflichtbelegen die
    # Snapshots der vorangehenden Zeichnungen (*_snapshot). Ueberholte
    # Zeichnungsrunden bleiben als Historie erhalten — entscheide/ wird
    # nie kuratiert, nur die Darstellung unterscheidet.
    final: set = set()
    abschluesse = sorted(
        (d for _, d in rohe if d.get("gate") == "A-M4"
         and d.get("snapshot_sha256")),
        key=lambda d: str(d.get("entschieden_am")))
    if abschluesse:
        letzter = abschluesse[-1]
        final = {letzter["snapshot_sha256"]} | {
            beleg
            for name, belege in (letzter.get("pflichtbelege") or {}).items()
            if name.endswith("_snapshot")
            for beleg in (belege if isinstance(belege, list) else [belege])
        }

    entscheide = []
    for pfad, d in rohe:
        freigabe = d.get("freigabe") or {}
        # Beide Seiten haben denselben Eintrag erweitert, um
        # verschiedene Dinge: die Seiten-Fassung um die Herkunft des
        # Snapshots und seine Stellung in der finalen Kette, der
        # Tagesbetrieb um die schluessellose Verifikation aus T19-02.
        # Beides bleibt — die Felder unten brauchen beide Groessen.
        snapshot = d.get("snapshot_sha256") or ""
        befunde = _verifiziere_snapshot(d, pfad.name)
        entscheide.append({
            "snapshot_datei": f"entscheide/{pfad.name}",
            "gate": d.get("gate"),
            "entscheid": d.get("entscheid"),
            "rolle": d.get("rolle"),
            # Besetzung der Rolle (ADR-018): aus der mitsignierten
            # Zeichnung. Altsnapshots (Schema 6) tragen sie nicht — das
            # steht dann so da, statt eine Klasse zu erfinden.
            "schluesselklasse": (d.get("zeichnung") or {}).get(
                "schluesselklasse")
            or ("nicht ausgewiesen (Schema 6)" if d.get("schema_version") == 6
                else None),
            "mandat_sha256": (d.get("zeichnung") or {}).get("mandat_sha256"),
            "entscheider": d.get("entscheider"),
            "entschieden_am": d.get("entschieden_am"),
            "schluessel_sha256": (freigabe.get("schluessel_sha256") or "")[:16],
            "snapshot_sha256": snapshot[:16],
            "in_finaler_kette": bool(final) and snapshot in final,
            "pflichtbelege": sorted(d.get("pflichtbelege") or {}),
            # Was die Zeichnung NICHT deckt, woertlich aus dem Snapshot
            # (A-K2 ab Schema 8, ADR-018 Nachtrag 2026-10-01).
            "ausnahmen": dict(d.get("ausnahmen") or {}),
            "artefakte_gebunden": len(d.get("artefakt_hashes") or {}),
            "begruendung": d.get("begruendung"),
            # Was dieses Werkzeug OHNE Schluessel pruefen kann (T19-02):
            # Schema, Selbstadressierung, Dateiname. Die Signatur nicht —
            # ein Darstellungswerkzeug bekommt keinen Schluesselring.
            "strukturell_verifiziert": not befunde,
            "verifikationsbefunde": befunde,
            "signatur_verifiziert": False,
        })
    entscheide.sort(key=lambda e: str(e["entschieden_am"]))
    # GELTEND ist je Gate der Entscheid der finalen Kette — oder, wo die
    # Kette ein Gate nicht fuehrt (Fallauftrag, Abnahmen des Stands, Zugang),
    # der juengste strukturell unversehrte. Die finale Kette folgt den
    # Vorgaengern der Abschlussabnahme; der Fallauftrag und der Zugang
    # stehen davor und danach und waeren sonst "nicht final" — ein Wort,
    # das hier nach "ueberholt" klingt und nicht stimmt.
    in_kette = {str(e["gate"]) for e in entscheide if e["in_finaler_kette"]}
    for e in entscheide:
        e["geltend"] = bool(e["in_finaler_kette"])

    # Welche Snapshots anderer Gates ein Entscheid BINDET — gemessen: Die
    # Pruefsumme der Snapshot-Datei oder seine Selbstadresse steht irgendwo
    # im Entscheid (Pflichtbelege, Artefakt-Hashes, Auftrag, Stand). Die
    # Seite sagt dann, welche es sind, statt "alle vorangehenden" zu
    # behaupten.
    def _hashes(x: Any) -> set:
        if isinstance(x, dict):
            return set().union(*(_hashes(v) for v in x.values())) if x else set()
        if isinstance(x, list):
            return set().union(*(_hashes(v) for v in x)) if x else set()
        return {x} if isinstance(x, str) and re.fullmatch(r"[0-9a-f]{64}", x) else set()

    adressen = {f"entscheide/{pfad.name}": {hashlib.sha256(pfad.read_bytes()).hexdigest(),
                                            str(d.get("snapshot_sha256") or "")} - {""}
                for pfad, d in rohe}
    nennt = {f"entscheide/{pfad.name}": _hashes({k: v for k, v in d.items() if k != "snapshot_sha256"})
             for pfad, d in rohe}
    for e in entscheide:
        e["snapshots_gebunden"] = list(dict.fromkeys(
            str(o["gate"]) for o in entscheide
            if str(o["gate"]) != str(e["gate"])
            and adressen.get(o["snapshot_datei"], set()) & nennt.get(e["snapshot_datei"], set())))
    for g in sorted({str(e["gate"]) for e in entscheide} - in_kette):
        kandidaten = [e for e in entscheide if str(e["gate"]) == g and e["strukturell_verifiziert"]]
        if kandidaten:
            kandidaten[-1]["geltend"] = True

    systemstaende = sorted({
        json.dumps(d.get("system"), sort_keys=True)
        for _, d in rohe if d.get("system")
    })
    # Der Systemstand, auf dem die FINALE Kette gezeichnet wurde — ein
    # einziger, wenn die Zeichnungsordnung eingehalten ist.
    finale_staende = sorted({
        str((d.get("system") or {}).get("commit") or "")[:12]
        for _, d in rohe
        if d.get("snapshot_sha256") in final and d.get("system")
    })
    # Auf wie vielen Systemstaenden die GELTENDEN Abnahmen liegen. Der
    # Fallauftrag (A-M6) bindet die Lieferung, nicht den Systemstand: seine
    # Fortschreibungen duerfen auf frueheren Staenden liegen, waehrend A-M4
    # fuer die Abnahmen denselben Stand verlangt. Gezaehlt wird nach Commit
    # und Quellcode-Hash — ein anderer Zweigname ist kein anderer Stand.
    abnahme_staende = _staende_der_abnahmen(entscheide, rohe)
    unversehrt = [e for e in entscheide if e["strukturell_verifiziert"]]
    return {
        "gates": gates,
        "entscheide": entscheide,
        "anzahl_gate_laeufe": len(gates),
        "finale_kette_ableitbar": bool(final),
        "systemstand_final": (finale_staende[0]
                              if len(finale_staende) == 1 else None),
        "systemstaende_final": len(finale_staende),
        "systemstaende_der_entscheide": len(systemstaende),
        "systemstaende_der_abnahmen": abnahme_staende,
        # Der Zaehler, den die Darstellung benutzen darf: strukturell
        # unversehrte Snapshots. NICHT "gezeichnet" — die Signatur
        # prueft dieses Werkzeug nicht (T19-02).
        "entscheide_strukturell_verifiziert": len(unversehrt),
        "entscheide_mit_befund": len(entscheide) - len(unversehrt),
        "signaturpruefung": "nicht durchgefuehrt (kein Schluesselring "
                            "im Darstellungswerkzeug)",
        "gelesen_aus": ["abgeleitet/diagnostics/*.gate.json",
                        "entscheide/*.json"],
    }


# --------------------------------------------------------------------------- #
# E2 — Verankerung (die Korrekturschicht)
# --------------------------------------------------------------------------- #

def verankerung(fall: Path) -> Dict[str, Any]:
    """Wie viel Korrektur der uebernommene Bestand braucht.

    Das Zielsystem rechnet jeden Vertrag aus seinen Ursprungsparametern
    selbst; der gelieferte Stand geht nur in ein Verankerungs-Residuum
    ein, das eine Korrekturschicht traegt. Ist diese Schicht ueber den
    ganzen Bestand nahezu leer, ist die Migration eine Nachrechnung und
    keine Datenkopie mit Differenzkonto — die staerkste Einzelaussage
    eines Falls, und sie steht im Schichtbeleg, nicht in einem Bericht.
    """
    pfad = fall / "abgeleitet" / "schichten" / "verankerung_schichten.json"
    d = _json(pfad)
    if not isinstance(d, dict):
        return {"vorhanden": False}
    s = d.get("summary") or {}
    return {
        "vorhanden": True,
        "vertraege": s.get("vertraege"),
        "getragen": s.get("getragen"),
        "residuum_summe": s.get("residuum_summe"),
        "residuum_max_abs": s.get("residuum_max_abs"),
        "befunde": s.get("befunde"),
        "gelesen_aus": ["abgeleitet/schichten/verankerung_schichten.json"],
    }


# --------------------------------------------------------------------------- #
# F — Umbau
# --------------------------------------------------------------------------- #

def umbau(fall: Path) -> Dict[str, Any]:
    """Wie weit der Lauf das Zielsystem umgebaut hat.

    Das Budget begrenzt die Arbeit des Operators WAEHREND des Fall-Laufs
    und ist damit eine Eigenschaft der Fall-Arbeit — deshalb gehoert es
    zum Fall, und ein abgeschlossener Fall muss die Messung tragen
    (ERWARTET): Ein Lauf, dessen Umbau niemand gemessen hat, sieht sonst
    aus wie ein Lauf ohne Umbau. Erhoben wird sie mit
    ``umbaubudget.py --json`` in den Fall.
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

#: Die Groessen des Migrationscontrollings (A-M4) in Unternehmenssprache:
#: Name, mit Artikel im Akkusativ, die gelieferte Groesse zu einem Datum und
#: die Spalte des Bestandsabzugs, an der man sieht, ob sie geliefert ist.
CONTROLLING_GROESSE = {
    "dk": ("Deckungskapital", "das Deckungskapital",
           "das zum {datum} gelieferte Deckungskapital", "deckkap"),
    "bjb": ("Jahresbeitrag", "den Jahresbeitrag",
            "den zum {datum} gelieferten Jahresbeitrag", "jbrutto"),
}
#: Beendende Geschaeftsvorfaelle, in der Folge der Darstellung: Einzahl, Mehrzahl.
ABGANG_TEXT = {"STO": ("Rückkauf", "Rückkäufe"), "ABL": ("Ablauf", "Abläufe"),
               "TOD": ("Todesfall", "Todesfälle")}


def _controlling_umfang(c: Dict[str, Any], bestand: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Was das Migrationscontrolling an seinen zwei Stichtagen verglichen hat —
    eine Einschraenkung nur, wo eine Groesse am zweiten Stichtag fehlt oder
    Vertraege ohne Abgang keinen Vergleich haben.

    Gelesen ueber das Muster der Schluessel ("<groesse>_stichtag_<n>",
    "gevo_<art>_monat_<m>"), nicht ueber die Endung: "gevo_x_monat_1" ist
    kein Stichtag. Ein Vertrag, der vor dem zweiten Stichtag ausscheidet,
    hat dort kein Deckungskapital mehr; A-M4 rechnet fuer ihn die Leistung
    beim Ausscheiden nach (qa.migrationssuite, TERMINAL). Das ist keine
    Luecke — in Fall 3 gemessen: die 23 fehlenden Vertraege sind genau die
    14 Rueckkaeufe, 7 Ablaeufe und 2 Todesfaelle.
    """
    from rechner_pipeline.qa.migrationssuite import TERMINAL

    je_stichtag: Dict[int, Dict[str, int]] = {}
    abgaenge: Dict[str, int] = {}
    for schluessel, anzahl in (c.get("je_groesse") or {}).items():
        m = re.fullmatch(r"([a-z]+)_stichtag_(\d+)", str(schluessel))
        if m:
            je_stichtag.setdefault(int(m.group(2)), {})[m.group(1)] = int(anzahl or 0)
            continue
        m = re.fullmatch(r"gevo_([a-z]+)_monat_\d+", str(schluessel))
        if m and m.group(1).upper() in TERMINAL:
            abgaenge[m.group(1).upper()] = abgaenge.get(m.group(1).upper(), 0) + int(anzahl or 0)
    eins, zwei = je_stichtag.get(1) or {}, je_stichtag.get(2) or {}
    if not eins or not zwei:
        return None

    def text(g: str, form: int, datum: str = "") -> str:
        name, akk, geliefert, _ = CONTROLLING_GROESSE.get(
            g, (f"Größe {g}", f"die Größe {g}", f"die zum {{datum}} gelieferte Größe {g}", ""))
        return (name, akk, geliefert)[form].format(datum=datum)

    def folge(gs: Any) -> List[str]:
        return sorted(gs, key=lambda g: (list(CONTROLLING_GROESSE).index(g)
                                         if g in CONTROLLING_GROESSE else len(CONTROLLING_GROESSE), g))

    def datum(iso: Any) -> str:
        try:
            return _dt.date.fromisoformat(str(iso)[:10]).strftime("%d.%m.%Y")
        except ValueError:
            return str(iso)

    d1, d2 = datum(c.get("stichtag_1")), datum(c.get("stichtag_2"))
    alle, noch = max(eins.values()), min(zwei.values())
    fehlen, ausgeschieden = alle - noch, sum(abgaenge.values())
    abzuege = bestand.get("abzuege") or []
    zweiter = abzuege[1] if len(abzuege) > 1 else {}
    nur_eins = [g for g in folge(eins) if g not in zwei]
    geliefert = [g for g in nur_eins
                 if ((zweiter.get(CONTROLLING_GROESSE.get(g, ("", "", "", ""))[3]) or {})
                     .get("anzahl") or 0) > 0]
    if not nur_eins and fehlen == ausgeschieden:
        return None

    saetze = [f"Am Übernahmestichtag, dem {d1}, haben wir "
              + " und ".join(text(g, 0) for g in folge(eins))
              + f" aller {alle} Verträge nachgerechnet und mit den Werten der abgebenden "
              "Gesellschaft verglichen."]
    zwei_text = " und ".join(text(g, 1) for g in folge(zwei))
    satz = (f"Zum Kontrollstichtag, dem {d2}, haben wir " + ("nur noch " if nur_eins else "")
            + f"{zwei_text} verglichen, für die {noch} Verträge, die dann noch bestanden")
    if ausgeschieden:
        arten = ", ".join(f"{abgaenge[a]} {ABGANG_TEXT[a][abgaenge[a] != 1]}"
                          for a in ABGANG_TEXT if abgaenge.get(a))
        satz += (f"; für die {ausgeschieden} ausgeschiedenen ({arten}) haben wir die Leistung "
                 "beim Ausscheiden nachgerechnet")
    saetze.append(satz + ".")
    if fehlen > ausgeschieden:
        saetze.append(f"Für {fehlen - ausgeschieden} Verträge, die nicht ausgeschieden sind, "
                      f"fehlt der Vergleich zum {d2}.")
    elif fehlen < ausgeschieden:
        saetze.append(f"Ausgeschieden sind {ausgeschieden} Verträge, ohne Vergleich zum {d2} "
                      f"sind aber nur {fehlen}.")
    if geliefert:
        saetze.append("Nicht verglichen haben wir "
                      + " und ".join(text(g, 2, d2) for g in geliefert) + ".")
    ungeliefert = [g for g in nur_eins if g not in geliefert]
    if ungeliefert:
        saetze.append(f"Zum {d2} hat die abgebende Gesellschaft "
                      + " und ".join(text(g, 1) for g in ungeliefert) + " nicht geliefert.")
    return {
        "sicht": "fachlich", "abnahme": "A-M4",
        "was": ("Die Stichtage sind unterschiedlich tief geprüft" if nur_eins
                else "Vergleich zum zweiten Stichtag nicht für jeden Vertrag"),
        "zahlen": (f"{len(eins)} Größe(n) am ersten, {len(zwei)} am zweiten Stichtag" if nur_eins
                   else f"{noch} von {alle}"),
        "satz": " ".join(saetze),
    }


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
                "satz": f"Die Abnahme {t['kennung']} zieht ihre Stichprobe aus {gg} der "
                        f"{bestandsgroesse} Verträge, nicht aus dem ganzen Bestand.",
            })
        ersetzt = t.get("plausibilitaets_pruefungen") or 0
        if ersetzt:
            gesamt = (t.get("verteilung") or {}).get("anzahl_werte") or 0
            aus.append({
                "sicht": "fachlich", "abnahme": t["kennung"],
                "was": "Wertvergleich durch Plausibilitaetspruefung ersetzt",
                "zahlen": f"{ersetzt} von {gesamt + ersetzt} Pruefungen, "
                          f"{t.get('plausibilitaet_vertraege')} Vertraege",
                "satz": f"In der Abnahme {t['kennung']} sind {ersetzt} von {gesamt + ersetzt} "
                        f"Prüfungen an {t.get('plausibilitaet_vertraege')} Verträgen keine "
                        "Wertvergleiche, sondern Plausibilitätsprüfungen.",
            })

    umfang = _controlling_umfang(a.get("controlling") or {}, b)
    if umfang:
        aus.append(umfang)

    tr = modell.get("transformation") or {}
    if tr.get("vorhanden"):
        quelle, ziel = tr.get("zeilen_quelle"), tr.get("zeilen_ziel")
        if quelle and ziel and quelle != ziel:
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Die Transformation hat Zeilen verloren",
                "zahlen": f"{ziel} von {quelle}",
                "satz": f"Bei der Übersetzung des Bestands sind aus {quelle} gelieferten "
                        f"Zeilen {ziel} geworden.",
            })
        # Eine Spalte, die weder abgebildet noch ausdruecklich verworfen
        # wurde, ist der gefaehrliche Fall — ueber sie hat niemand
        # nachgedacht, und im Ergebnis sieht das aus wie Absicht.
        if tr.get("stumm_weggelassen"):
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Quellspalten weder abgebildet noch ausdruecklich verworfen",
                "zahlen": ", ".join(tr["stumm_weggelassen"]),
                "satz": "Diese Spalten der Lieferung haben wir weder übernommen noch "
                        "ausdrücklich verworfen: " + ", ".join(tr["stumm_weggelassen"]) + ".",
            })
        ohne_grund = [n for n in tr.get("nicht_uebernommen") or []
                      if not n.get("begruendung")]
        if ohne_grund:
            aus.append({
                "sicht": "fachlich", "abnahme": None,
                "was": "Nichtuebernahme ohne Begruendung",
                "zahlen": ", ".join(
                    ", ".join(n.get("quellen") or []) for n in ohne_grund),
                "satz": "Diese Angaben der Lieferung übernehmen wir nicht, ohne dass ein Grund "
                        "festgehalten ist: " + ", ".join(
                            ", ".join(n.get("quellen") or []) for n in ohne_grund) + ".",
            })

    for name, beleg in (modell.get("parameter") or {}).get("belege", {}).items():
        if beleg.get("hashgebunden") is False:
            aus.append({
                "sicht": "technisch", "abnahme": None,
                "was": f"Belegrechnung {name} ist an keine Prüfsumme gebunden",
                "zahlen": None,
                "satz": f"Die Belegrechnung {name} ist an keine Prüfsumme gebunden.",
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
                "satz": "Das Bewegungskonto hat die Bestandsprüfung nicht geprüft; geprüft hat "
                        "sie " + ", ".join(umfang.get("geprueft") or []) + ".",
            })

    # Gezaehlt werden die Staende der geltenden Abnahmen, nicht aller
    # Snapshots: Der Fallauftrag und seine Fortschreibungen binden die
    # Lieferung und duerfen auf frueheren Staenden liegen (in Fall 3 zwei,
    # waehrend alle neun Abnahmen auf einem liegen).
    k = modell.get("kette") or {}
    if k.get("systemstaende_der_abnahmen", 0) > 1:
        n = k["systemstaende_der_abnahmen"]
        aus.append({
            "sicht": "technisch", "abnahme": None,
            "was": "Die geltenden Abnahmen beruhen auf verschiedenen Systemständen",
            "zahlen": f"{n} Stände",
            "satz": f"Die geltenden Abnahmen dieses Falls beruhen auf {n} verschiedenen "
                    "Ständen unseres Systems.",
        })
    return aus


# --------------------------------------------------------------------------- #

#: Was ein abgeschlossener Fall im Bestands-Scope tragen MUSS. Fehlt
#: etwas davon, ist das eine Luecke des Falls oder eine Formaenderung der
#: Pipeline — beides muss auffallen, statt einen Abschnitt still
#: verschwinden zu lassen.
ERWARTET = (
    ("fall", "scope", "Fall-Scope (tarif oder bestand), streng gelesen"),
    ("lieferung", "quellen", "registrierte Quellen"),
    ("bestand", "anzahl", "uebernommener Bestand"),
    ("transformation", "felder", "Feldabbildung"),
    ("parameter", "generationen", "Tarifgeneration der A-Box"),
    ("abnahmen", "aktuariell", "aktuarielle Abnahmen"),
    ("abnahmen", "controlling", "Migrationscontrolling (A-M4)"),
    ("kette", "entscheide", "Entscheid-Snapshots der Gates"),
    # Was der Fall am Zielsystem geaendert hat: frueher das Umbaubudget des
    # Laufs, seit der Abnahme des Stands (ADR-018 Nachtrag 01.10., ADR-025)
    # die Aenderungsbelege von Kern (A-K2) und Tarifwerk (A-T1).
    ("systemaenderung", "vorhanden", "Änderung am Zielsystem (Umbaubudget oder Änderungsbelege)"),
)

#: Die aktuariellen Abnahmen eines Bestands-Falls — als MENGE, nicht als
#: "irgendeine nichtleere Liste". Externes Review T19-03: Die alte
#: Pruefung war schwaecher als der reale Scope, der A-M1..A-M3 vor A-M4
#: erzwingt (gates.gate_entscheid) — ein Fall mit nur A-M1 galt als
#: vollstaendig. Was der Fall-Scope verlangt, muss die Darstellung
#: verlangen, sonst behauptet sie Vollstaendigkeit, die keine ist.
ERWARTETE_ABNAHMEN = ("A-M1", "A-M2", "A-M3")

#: Pflichtrollen von A-M4, die ein Entscheid-Snapshot sind
#: (``a<gegenstand><nummer>_snapshot``, models.belegrollen).
_SNAPSHOTROLLE = re.compile(r"^a([a-z])(\d)_snapshot$")

#: Gruppen des Modells, die es nur im Bestands-Scope gibt: Ein Tarif-Fall
#: hat keinen Bestand, keine Transformation und kein Zwei-Stichtags-
#: Controlling (gates.gate_entscheid verlangt dort nur A-M1 vor A-M4).
NUR_BESTAND = {("bestand", "anzahl"), ("transformation", "felder"),
               ("abnahmen", "controlling")}


def erwartete_abnahmen(scope: Optional[str]) -> Tuple[str, ...]:
    """Die Sollmenge folgt dem Fall-Scope — derselben Vertragsquelle wie
    gates.gate_entscheid (Review T20-03: die globale Menge erklaerte einen
    vertragsgemaessen Tarif-Fall fuer unvollstaendig)."""
    return ERWARTETE_ABNAHMEN if scope == "bestand" else ("A-M1",)


def erwartete_entscheide(scope: Optional[str]) -> Tuple[str, ...]:
    """Die Entscheide eines abgeschlossenen Falls: was A-M4 als Vorbedingung
    pinnt, und A-M4 selbst.

    ABGELEITET aus dem Belegvertrag (``models.belegrollen``), nicht
    abgetippt: Bis 2026-10-01 stand hier eine Liste A-M1..A-M4 — ohne A-Q1,
    das A-M4 seit jeher verlangt. Eine Menge, die die eine Seite erweitert
    und die andere aufzaehlt, laeuft auseinander. Unbekannter Scope: das
    volle Bestandsprofil (fail-closed, Review T21-04).

    Die Standabnahmen (A-K2 Kernstand, A-O1 T-Box-Stand; Entscheid
    2026-10-01) sind KEINE Pflicht-Entscheide im Fall: Bei unveraendertem
    Stand gilt eine fruehere Abnahme ("keine Aenderung"). Wie sie erfuellt
    sind, zeigt :func:`standabnahmen` aus dem A-M4-Snapshot.
    """
    from rechner_pipeline.models.belegrollen import am4_belegrollen
    from rechner_pipeline.models.zeichnung import AUFTRAG_GATE

    rollen = am4_belegrollen(scope if scope in ("tarif", "bestand") else "bestand")
    vorher = tuple(f"A-{m.group(1).upper()}{m.group(2)}"
                   for m in map(_SNAPSHOTROLLE.match, rollen) if m)
    # Der Fallauftrag (ADR-026) ist Pflicht-Entscheid jedes Falls: Jede
    # Annahme nennt ihn signiert (Feld ``fallauftrag``), keine Belegrolle.
    return (AUFTRAG_GATE,) + vorher + ("A-M4",)


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
    # Die Luecken des Betriebsstands wandern in die Darstellung mit (T22-05).
    for l in (modell.get("betrieb") or {}).get("luecken") or []:
        aus.append({"gruppe": "betrieb", "feld": str(l.get("was")), "was": str(l.get("was")),
                    "wirkung": str(l.get("wirkung"))})
    scope = (modell.get("fall") or {}).get("scope")
    if scope not in ("tarif", "bestand"):
        # Fail-closed (Review T21-04): Ein fehlender oder unbekannter Scope
        # ist eine Luecke (unten, Gruppe fall) und wird mit dem VOLLEN
        # Profil geprueft — nicht still wie ein Tarif-Fall, dem am
        # wenigsten fehlen kann.
        scope_luecke = True
        scope = "bestand"
    else:
        scope_luecke = False
    for gruppe, feld, was in ERWARTET:
        if scope != "bestand" and (gruppe, feld) in NUR_BESTAND:
            continue
        inhalt = modell.get(gruppe) or {}
        if (gruppe, feld) == ("fall", "scope"):
            if scope_luecke:
                aus.append({
                    "gruppe": gruppe, "feld": feld, "was": was,
                    "wirkung": (inhalt.get("scope_befund")
                                or "Der Fall sagt nicht, ob er Tarif- oder "
                                   "Bestandsfall ist") + " — die Darstellung "
                               "verlangt deshalb das volle Bestandsprofil.",
                })
            continue
        if not inhalt.get(feld):
            aus.append({
                "gruppe": gruppe, "feld": feld, "was": was,
                "wirkung": "Der Abschnitt fehlt in der Darstellung.",
            })

    # Mengen statt Nichtleere (T19-03): Eine Abnahme zu haben ist nicht
    # dasselbe wie DIE Abnahmen zu haben.
    abnahmen = modell.get("abnahmen") or {}
    vorhanden = {str(a.get("kennung")) for a in (abnahmen.get("aktuariell")
                                                 or [])}
    for kennung in erwartete_abnahmen(scope):
        if kennung not in vorhanden:
            aus.append({
                "gruppe": "abnahmen", "feld": f"aktuariell:{kennung}",
                "was": f"aktuarielle Abnahme {kennung}",
                "wirkung": "Die Abnahme fehlt — der Fall ist nicht "
                           "vollstaendig abgenommen.",
            })

    kette = modell.get("kette") or {}
    entschieden = {str(e.get("gate")) for e in (kette.get("entscheide") or [])
                   if e.get("strukturell_verifiziert") is not False}
    for gate in erwartete_entscheide(scope):
        if gate not in entschieden:
            aus.append({
                "gruppe": "kette", "feld": f"entscheide:{gate}",
                "was": f"Entscheid-Snapshot zu {gate}",
                "wirkung": "Kein strukturell unversehrter Snapshot fuer "
                           "dieses Gate — die Abnahme ist nicht belegt.",
            })

    mit_befund = kette.get("entscheide_mit_befund") or 0
    if mit_befund:
        aus.append({
            "gruppe": "kette", "feld": "verifikation",
            "was": f"{mit_befund} Entscheid-Snapshot(s) mit Befund",
            "wirkung": "Schema, Selbstadressierung oder Dateiname passen "
                       "nicht — solche Dateien belegen nichts.",
        })
    return aus


def _pruefe_stands_paket(paket: Path, stand: Dict[str, Any], prov: Dict[str, Any],
                         protokoll_roh: Optional[bytes] = None) -> bytes:
    """Das Paket gegen seine eigenen Belege halten (Review T22-05).

    Vorher genuegte der freie String ``pb1 == "gruen"`` in stand.json — ein
    komplett erfundenes Paket wurde veroeffentlicht. Jetzt muss jede in
    ``dateien`` genannte Datei da sein und ihren Hash tragen; das
    Protokoll muss eine ungebrochene Kette sein (``lies_protokoll`` prueft
    sie); seine letzte gruene Zeile muss den Stand, das Urteil, den
    Manifest-Hash und den Journal-Hash nennen, die stand.json behauptet.
    Die Signatur eines Snapshots prueft auch das nicht — aber ein Paket,
    das sich selbst widerspricht, kommt nicht mehr auf die Seite.
    """
    import hashlib

    from rechner_pipeline.betrieb.seite import PAKET_MANIFEST
    from rechner_pipeline.betrieb.tageslauf import TageslaufError, lies_protokoll_text

    # EINE Lesung des Protokolls (Angriffsrunde nach T27): Hash, Kette,
    # Felder und Anker laufen auf denselben Bytes. Vorher las jede Pruefung
    # die Datei selbst, und ein Tausch zwischen den Lesungen liess ein
    # gefaelschtes Paket durch. Rueckgabe: diese Bytes, fuer den Anker.
    if protokoll_roh is None and (paket / "protokoll.jsonl").is_file():
        protokoll_roh = (paket / "protokoll.jsonl").read_bytes()
    dateien = stand.get("dateien") or {}
    for name in ("protokoll.jsonl", "laufmanifest.json", "tagesjournal.parquet", "index.html"):
        if name not in dateien:
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} fehlt in stand.json")
    for name, soll in sorted(dateien.items()):
        datei = paket / name
        if not datei.is_file():
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} fehlt")
        roh = protokoll_roh if name == "protokoll.jsonl" and protokoll_roh is not None else datei.read_bytes()
        ist = hashlib.sha256(roh).hexdigest()
        if ist != soll:
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} hat nicht den Hash aus stand.json")
    try:
        zeilen = lies_protokoll_text(protokoll_roh.decode("utf-8"), str(paket / "protokoll.jsonl"))
    except (TageslaufError, UnicodeDecodeError) as exc:
        raise FalldatenFehler(f"{paket}: Protokollkette: {exc}") from exc
    gruene = [z for z in zeilen if z.get("uebernommen")]
    if not gruene:
        raise FalldatenFehler(f"{paket}: das Protokoll kennt keinen uebernommenen Lauf")
    letzte = gruene[-1]
    if letzte.get("heute") != stand.get("stand"):
        raise FalldatenFehler(
            f"{paket}: stand.json behauptet Stand {stand.get('stand')!r}, die letzte "
            f"gruene Protokollzeile fuehrt {letzte.get('heute')!r}")
    urteil = (letzte.get("pb1") or {}).get("urteil")
    if urteil != "gruen" or prov.get("pb1") != "gruen":
        raise FalldatenFehler(
            f"{paket}: der Stand ist nicht durch P-B1 gegangen "
            f"(Protokoll {urteil!r}, stand.json {prov.get('pb1')!r}) — veroeffentlicht "
            "wird nichts, was die Wache nicht passiert hat")
    manifest_hash = dateien.get(PAKET_MANIFEST)
    if letzte.get("manifest_sha256") != manifest_hash or prov.get("manifest_sha256") != manifest_hash:
        raise FalldatenFehler(
            f"{paket}: Manifest-Hash von Protokoll, stand.json und Belegdatei stimmen nicht ueberein")
    manifest = _json(paket / PAKET_MANIFEST) or {}
    if str(manifest.get("horizont")) != str(stand.get("stand")):
        raise FalldatenFehler(
            f"{paket}: das Manifest fuehrt {manifest.get('horizont')!r}, stand.json {stand.get('stand')!r}")
    # Herkunft und Eingaenge der letzten Zeile gegen das mitgelieferte
    # Manifest (Runde C, RC13/RC14): ohne Schluessel und ohne Ablage
    # rechenbar. Die Zeichnung der Zeilen kann der Konsument NICHT pruefen —
    # er haelt keinen Betriebsschluessel und behauptet sie nicht.
    from rechner_pipeline.betrieb.tageslauf import zeile_gegen_manifest

    abweichend = zeile_gegen_manifest(letzte, manifest)
    if abweichend:
        raise FalldatenFehler(
            f"{paket}: die letzte gruene Protokollzeile sagt ueber {abweichend} "
            "etwas anderes als das Manifest des Stands, das sie bindet — die Zeile "
            "wurde veraendert oder gehoert zu einem anderen Stand")
    journal_hash = (letzte.get("tagesjournal") or {}).get("sha256")
    if prov.get("tagesjournal_sha256") != journal_hash:
        raise FalldatenFehler(f"{paket}: Journal-Hash von Protokoll und stand.json stimmen nicht ueberein")
    if dateien.get("tagesjournal.parquet") != journal_hash:
        raise FalldatenFehler(
            f"{paket}: die Belegdatei 'tagesjournal.parquet' ist nicht das Journal, "
            "auf das die letzte gruene Protokollzeile sich festgelegt hat")
    _pruefe_abschluesse_gegen_das_protokoll(paket, stand, dateien)
    _pruefe_buchungen_gegen_das_journal(paket, stand)
    _pruefe_felder_gegen_das_protokoll(paket, stand, prov, zeilen, gruene, letzte)
    return protokoll_roh


def _pruefe_abschluesse_gegen_das_protokoll(
    paket: Path, stand: Dict[str, Any], dateien: Dict[str, str],
) -> None:
    """Die mitgelieferten Monatsabschluesse haengen am Hash, den die
    Protokollzeile ihres Stichtags nennt — nicht nur an stand.json.

    Bis zur Pruefrunde T27 (Befund 10) wurde jede Abschlussdatei nur gegen
    ``stand.json["dateien"]`` gehalten, und die schreibt der Erzeuger des
    Pakets selbst: Ein Abschluss mit 16 Vertraegen liess sich durch eine
    leere Tabelle ersetzen, der Dateihash nachziehen, und das Paket ging
    mit "16 Vertraegen neben null Abschlusszeilen" durch. Der Hash, den
    ``stand.json["abschluesse"][i]["sha256"]`` nennt, stammt dagegen aus
    der verketteten und extern verankerten Protokollzeile — DAS ist die
    Bindung, dieselbe Figur wie beim Tagesjournal darueber. Und die
    Auswahl, die der Export mitliefert (die juengsten Abschluesse), muss
    vollstaendig da sein: fehlende Abschlussdateien sind keine Auslassung,
    sondern ein Paket, das seine Vertragszahlen nicht belegt.
    """
    from rechner_pipeline.betrieb.seite import PAKET_ABSCHLUESSE_DIR, juengste_abschluesse

    ohne_datei = [a.get("stichtag") for a in (stand.get("abschluesse") or [])
                  if a.get("in_kraft") is not None and not a.get("datei")]
    if ohne_datei:
        raise FalldatenFehler(
            f"{paket}: Abschluss {ohne_datei[0]!r} nennt eine Vertragszahl ohne "
            "Abschlussdatei — eine Zahl ohne Beleg wird nicht veroeffentlicht")
    erwartet = juengste_abschluesse(list(stand.get("abschluesse") or []))
    for a in erwartet:
        name = f"{PAKET_ABSCHLUESSE_DIR}/{a.get('datei')}"
        if name not in dateien:
            raise FalldatenFehler(
                f"{paket}: der Abschluss {a.get('datei')!r} zum {a.get('stichtag')!r} "
                "fehlt im Paket — ein Paket ohne seine juengsten Abschluesse belegt "
                "seine Vertragszahlen nicht")
        if dateien[name] != a.get("sha256"):
            raise FalldatenFehler(
                f"{paket}: die Abschlussdatei {name!r} ist nicht der Abschluss, den die "
                f"Protokollzeile zum {a.get('stichtag')!r} bezeugt "
                f"({str(dateien[name])[:16]}… statt {str(a.get('sha256'))[:16]}…)")


def _pruefe_felder_gegen_das_protokoll(
    paket: Path, stand: Dict[str, Any], prov: Dict[str, Any],
    zeilen: List[Dict[str, Any]], gruene: List[Dict[str, Any]], letzte: Dict[str, Any],
) -> None:
    """Die protokollgespeisten Bloecke von stand.json nachrechnen (Review T24-04).

    Geprueft waren bisher Stand, Urteil, Manifest- und Journal-Hash. Alles
    andere, was aus der Protokollzeile stammt — Bestandszahlen, Uebernahmen,
    Verankerung, Abschluesse, Neugeschaeft und die uebrigen
    Provenienzfelder — stand ungeprueft daneben: Wer das Paket las, musste
    dem Feld glauben, obwohl der Beleg daneben lag. Nachgemessen ging ein
    Paket durch, in dem in_force von 68 auf 1067 gesetzt war.

    Die Abschluesse kommen aus derselben Funktion, die der Erzeuger
    benutzt (``seite.abschluesse_aus_protokoll``) — zwei Ableitungen
    waeren zwei Regeln, die auseinanderlaufen.

    Ihre Quellen kommen aus dem PAKET, nicht aus einer Ablage: Journal
    und die juengsten Monatsabschluesse liegen seit Schema 5 dabei und
    haengen ueber ``dateien`` mit Hash an der Kette. Wer hier stattdessen
    die Ablage des Erzeugers laese, pruefte das Paket gegen etwas, das
    gar nicht im Paket steht.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.betrieb.seite import (
        PAKET_ABSCHLUESSE_DIR, PAKET_JOURNAL, abschluesse_aus_protokoll,
    )
    from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

    journal_pfad = paket / PAKET_JOURNAL
    journal = (
        read_portfolio(journal_pfad, expected_columns=TAGESJOURNAL_NAMES)
        if journal_pfad.is_file() else None
    )
    from rechner_pipeline.betrieb.seite import SeiteError

    try:
        abschluesse = abschluesse_aus_protokoll(
            zeilen, journal=journal, abschluesse_dir=paket / PAKET_ABSCHLUESSE_DIR)
    except SeiteError as exc:
        raise FalldatenFehler(f"{paket}: {exc}") from exc
    erwartet = {
        "bestand": dict(letzte.get("bestand") or {}),
        "uebernahmen": list(letzte.get("uebernahmen") or []),
        "verankerung": dict(letzte.get("verankerung") or {}),
        "abschluesse": abschluesse,
        "gefuehrt_seit": (
            gruene[0]["nachgeholt"][0] if gruene[0].get("nachgeholt") else gruene[0]["heute"]
        ),
    }
    for feld, soll in erwartet.items():
        if stand.get(feld) != soll:
            raise FalldatenFehler(
                f"{paket}: stand.json und das Protokoll sagen Verschiedenes ueber "
                f"{feld!r} — das Paket widerspricht seinem eigenen Beleg")
    neu_soll = int(letzte.get("neugeschaeft_seit_betriebsbeginn", 0))
    if (stand.get("neugeschaeft") or {}).get("seit_betriebsbeginn") != neu_soll:
        raise FalldatenFehler(
            f"{paket}: stand.json meldet ein anderes Neugeschaeft seit "
            "Betriebsbeginn als die Protokollzeile")
    for feld, quelle in (("config_sha256", "config_sha256"), ("kern_version", "kern_version"),
                         ("image_digest", "image_digest"), ("image_revision", "image_revision"),
                         ("image_tag", "image_tag")):
        if prov.get(feld) != letzte.get(quelle):
            raise FalldatenFehler(
                f"{paket}: provenienz.{feld} steht nicht so in der letzten gruenen "
                "Protokollzeile — die Herkunft ist behauptet, nicht belegt")

    # Die WOCHENZAHLEN und der LUECKENAUSWEIS wurden bisher ungeprueft ins
    # veroeffentlichte Datenmodell uebernommen (Befund T26-09): Bei
    # unveraendertem Journal, unveraendertem Protokoll und korrekt
    # externem, unveraendertem Anker liess sich woche_summe auf 1.000.000
    # setzen und der Luecken-Block leeren — und der oeffentliche Bericht
    # baut seinen sichtbaren Lueckenblock aus genau dieser Funktion.
    #
    # Abgeleitet wird mit DERSELBEN Funktion wie beim Erzeuger; zwei
    # Ableitungen waeren zwei Regeln, die auseinanderlaufen.
    from rechner_pipeline.betrieb.seite import luecken as _luecken
    from rechner_pipeline.betrieb.seite import neugeschaeft_der_woche

    neugeschaeft = stand.get("neugeschaeft") or {}
    soll_woche = neugeschaeft_der_woche(
        journal, _dt.date.fromisoformat(str(stand.get("stand"))))
    for feld, soll in soll_woche.items():
        if neugeschaeft.get(feld) != soll:
            raise FalldatenFehler(
                f"{paket}: neugeschaeft.{feld} steht nicht so im Tagesjournal "
                f"— stand.json sagt {neugeschaeft.get(feld)!r}, gerechnet "
                f"{soll!r}")
    soll_luecken = _luecken(stand)
    if list(stand.get("luecken") or []) != soll_luecken:
        raise FalldatenFehler(
            f"{paket}: der Lueckenausweis stimmt nicht mit dem Stand ueberein "
            f"— stand.json nennt {len(stand.get('luecken') or [])} Luecke(n), "
            f"abgeleitet sind es {len(soll_luecken)}. Ein geleerter Block "
            "verschweigt genau das, was der Bericht ausweisen soll")


def _pruefe_buchungen_gegen_das_journal(paket: Path, stand: Dict[str, Any]) -> None:
    """Die journalgespeisten Zahlen gegen die Zeilen halten (Review T24-04, Teil 1).

    Bis Paketschema 2 lagen Protokoll und Manifest als Belege im Paket —
    damit waren die protokollgespeisten Bloecke von stand.json gedeckt.
    ``buchungen.*`` kommt aber aus dem Tagesjournal, das nicht mitkam: Die
    Zahl stand da und war zu glauben. Seit Schema 3 liegt das Journal
    dabei, seine Bytes haengen ueber den Protokoll-Hash an der Kette, und
    hier wird nachgerechnet.

    Gezaehlt wird wie beim Erzeuger: ``gesamt`` sind ZEILEN, ``je_ereignis``
    sind VORFAELLE (police_id, ereignis, status_date) — seit dem gebuchten
    Bruttojahresbeitrag bucht ein Zugang zwei Zeilen, und wer hier Zeilen
    zaehlte, meldete doppelt so viele Vorfaelle, wie es gab.
    """
    from rechner_pipeline.bestand.parquet_io import read_portfolio
    from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

    journal = read_portfolio(paket / "tagesjournal.parquet",
                             expected_columns=TAGESJOURNAL_NAMES)
    buchungen = stand.get("buchungen") or {}
    if buchungen.get("gesamt") != len(journal):
        raise FalldatenFehler(
            f"{paket}: stand.json meldet {buchungen.get('gesamt')!r} Buchungen, das "
            f"Tagesjournal traegt {len(journal)} Zeilen")
    vorfaelle = journal[["police_id", "ereignis", "status_date"]].drop_duplicates()
    gezaehlt = {str(k): int(v) for k, v in sorted(vorfaelle["ereignis"].value_counts().items())}
    if (buchungen.get("je_ereignis") or {}) != gezaehlt:
        raise FalldatenFehler(
            f"{paket}: die Vorfaelle je Ereignis in stand.json stimmen nicht mit dem "
            f"Tagesjournal ueberein (stand.json {buchungen.get('je_ereignis')!r}, "
            f"Journal {gezaehlt!r})")


def _pruefe_auslieferung(paket: Path, fall: Optional[Path],
                         satz_sha256: str) -> Dict[str, Any]:
    """Eine AUSLIEFERUNG braucht die menschliche Abnahme A-B1.

    Der Export zeichnet den Ankersatz — das sagt, WER das Paket erzeugt
    hat, und ein Agent darf es sagen. Was nach aussen geht, verantwortet
    dagegen ein Mensch: die fachliche Rolle mensch/betrieb, im
    Vorzeigebetrieb ihr simuliertes Gegenstueck (Entscheid des
    Maintainers 2026-09-16).

    Geprueft wird der Snapshot STRUKTURELL und seine Bindung an genau
    diesen Ankersatz — nicht die Signatur: Dafuer braeuchte es den
    Schluesselring, den ein Konsument nicht hat. Deshalb heisst es hier
    "Angaben der Snapshot-Datei" und nie "gezeichnet" (dieselbe
    Ehrlichkeit wie im Betriebseingang, T19-02).
    """
    from rechner_pipeline.models.schemas import P9Snapshot, p9_snapshot_sha256

    if fall is None:
        raise FalldatenFehler(
            f"{paket}: ausgeliefert, aber ohne Fall — die Abnahme A-B1 liegt "
            "im Fall unter entscheide/, und ohne ihn ist sie nicht auffindbar")
    verzeichnis = Path(fall) / "entscheide"
    treffer = sorted(verzeichnis.glob("A-B1-*.json")) if verzeichnis.is_dir() else []
    for pfad in treffer:
        try:
            daten = json.loads(pfad.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if P9Snapshot.validate_payload(daten):
            continue
        if daten.get("snapshot_sha256") != p9_snapshot_sha256(daten):
            continue
        if daten.get("gate") != "A-B1" or daten.get("entscheid") != "angenommen":
            continue
        belege = (daten.get("pflichtbelege") or {}).get("anker") or []
        if satz_sha256 in [str(b) for b in belege]:
            zeichnung = daten.get("zeichnung") or {}
            return {
                "snapshot_sha256": daten.get("snapshot_sha256"),
                "rolle": zeichnung.get("rolle"),
                "schluesselklasse": zeichnung.get("schluesselklasse"),
                "entscheider": daten.get("entscheider"),
            }
    raise FalldatenFehler(
        f"{paket}: das Paket ist als AUSLIEFERUNG ausgewiesen, aber keine "
        f"angenommene A-B1-Abnahme im Fall bindet seinen Ankersatz "
        f"({satz_sha256[:16]}…). Was nach aussen geht, zeichnet ein Mensch — "
        "gates.gate_entscheid --gate A-B1")


def _pruefe_anker(paket: Path, stand: Dict[str, Any],
                  anker_datei: Optional[Path],
                  fall: Optional[Path] = None,
                  protokoll_roh: Optional[bytes] = None,
                  ort: Optional[Path] = None) -> Dict[str, Any]:
    """Das Paket gegen einen Anker AUSSERHALB des Pakets halten (T24-04 b).

    Das Paket belegt sich bis hierher selbst: Jede Kennzahl ist aus
    seinen Belegen nachgerechnet, die Protokollkette ist ungebrochen. Was
    dabei NICHT geprueft werden kann, ist die letzte Zeile der Kette —
    sie hat keinen Nachfolger, der sie bindet, und genau aus ihr leitet
    stand.json ab. Wer beide zusammen umschreibt, kommt hier durch.

    Der Anker schliesst das: ein Hash derselben Zeile, abgelegt an einem
    Ort, den der schreibende Prozess nicht anfasst.
    """
    from rechner_pipeline.models.anker import (
        AnkerFehler,
        lies_anker,
        pruefe,
        satz_hash,
    )

    from rechner_pipeline.models.zeichnung import ausserhalb_von

    # ``ort``: das Paket, wie es auf der Platte liegt — geprueft wird aus
    # einer eingefrorenen Kopie, aber "liegt der Anker im Paket?" fragt
    # nach dem Original.
    if anker_datei is not None and not ausserhalb_von(Path(anker_datei), Path(ort or paket)):
        raise FalldatenFehler(
            f"{paket}: der Anker {anker_datei} liegt IM Paket — ein Bezug, der "
            "mit dem Paket kommt, bindet es nicht: Er wird mit ihm geschrieben "
            "und mit ihm ersetzt. Ein Anker ausserhalb des Pakets waehlen "
            "(Befund T26-08)."
        )
    if anker_datei is None:
        raise FalldatenFehler(
            f"{paket}: kein Anker uebergeben. Ein Stands-Paket wird gegen "
            "einen Bezug AUSSERHALB des Pakets geprueft — ohne ihn belegt es "
            "nur sich selbst (Review T24-04, Teil 2). Aufruf mit "
            "--anker <datei>; geschrieben hat sie der Export."
        )
    try:
        satz = pruefe(paket, stand, paket / "protokoll.jsonl",
                      lies_anker(Path(anker_datei)),
                      protokoll_text=(protokoll_roh.decode("utf-8")
                                      if protokoll_roh is not None else None))
    except AnkerFehler as exc:
        raise FalldatenFehler(str(exc)) from exc
    art = str(satz.get("art") or "momentaufnahme")
    verankerung = {
        "datei": str(anker_datei),
        "stand": satz.get("stand"),
        "erstellt": satz.get("erstellt"),
        "art": art,
        # Ausgewiesen, nicht behauptet: Wer den Ankersatz gezeichnet hat,
        # steht hier — mit seiner Klasse, damit man Mensch und Agent
        # unterscheiden kann (ADR-018).
        "zeichnung": satz.get("zeichnung"),
    }
    if art == "auslieferung":
        verankerung["abnahme"] = _pruefe_auslieferung(
            paket, fall, satz_hash(satz))
    return verankerung


def _zeitraeume(heute: _dt.date, gefuehrt_seit: _dt.date) -> Dict[str, Dict[str, Any]]:
    """Die Sichten der Geschaeftsentwicklung, relativ zum Stand des Pakets.

    Ein Zeitraum, der ganz vor dem Betriebsbeginn liegt, traegt
    ``ausserhalb_betrieb`` — das Journal kann ihn nicht belegen; die Seite
    zeigt dann einen benannten Platzhalter statt einer Null.
    """
    jahr, monat = heute.year, heute.month
    try:
        vorjahr_bis = heute.replace(year=jahr - 1)
    except ValueError:  # 29. Februar
        vorjahr_bis = heute.replace(year=jahr - 1, day=28)
    aus = {
        "letztes_jahr": (_dt.date(jahr - 1, 1, 1), _dt.date(jahr - 1, 12, 31)),
        # Der VERGLEICHBARE Zeitraum: gleicher Jahresabschnitt im Vorjahr.
        # Ein ganzes Vorjahr gegen ein angebrochenes Jahr zu stellen, waere
        # eine Verzerrung, die wie ein Rueckgang aussieht.
        "vorjahr_bis_heute": (_dt.date(jahr - 1, 1, 1), vorjahr_bis),
        "aktuelles_jahr": (_dt.date(jahr, 1, 1), heute),
        "aktueller_monat": (_dt.date(jahr, monat, 1), heute),
    }
    return {
        k: {"von": von.isoformat(), "bis": bis.isoformat(),
            "ausserhalb_betrieb": bis < gefuehrt_seit}
        for k, (von, bis) in aus.items()
    }


def _geschaeftsentwicklung(journal: Any, heute: _dt.date,
                           gefuehrt_seit: _dt.date) -> Dict[str, Any]:
    """Buchungen je Zeitraum und Vorfallart: Anzahl, Herkunft, Betraege —
    nachgerechnet aus dem Tagesjournal des Pakets.

    Bis zum Nachzug vom 03.10.2026 schrieb der Erzeuger diesen Block nach
    stand.json, und die Seite glaubte ihn, obwohl das Journal im selben
    Paket lag (dieselbe Figur wie ``in_force`` vor T24-04). Jetzt rechnet
    der Konsument aus den Bytes, deren Hash er geprueft hat; der Erzeuger
    behauptet nichts mehr darueber.

    Die Betraege sind die des Journals je Betragsart — was das Journal nicht
    traegt (etwa einen Bruttojahresbeitrag), steht hier auch nicht.
    """
    import pandas as pd

    zeitraeume = _zeitraeume(heute, gefuehrt_seit)
    je_zeitraum: Dict[str, Dict[str, Any]] = {}
    datum = (pd.to_datetime(journal["buchungsdatum"]) if len(journal)
             else pd.Series(dtype="datetime64[ns]"))
    for k, zr in zeitraeume.items():
        if zr["ausserhalb_betrieb"]:
            je_zeitraum[k] = {}
            continue
        maske = (datum >= pd.Timestamp(zr["von"])) & (datum <= pd.Timestamp(zr["bis"]))
        teil = journal[maske.values] if len(journal) else journal
        block: Dict[str, Any] = {}
        for ereignis, gruppe in teil.groupby("ereignis"):
            # GEZAEHLT werden Vorfaelle, nicht Journalzeilen: Ein Zugang bucht
            # seit der Beitragsbuchung zwei Zeilen (Summe und Beitrag).
            vorfaelle = gruppe.drop_duplicates(subset=["police_id", "ereignis", "status_date"])
            block[str(ereignis)] = {
                "anzahl": int(len(vorfaelle)),
                "zeilen": int(len(gruppe)),
                "je_herkunft": {str(h): int(n)
                                for h, n in sorted(vorfaelle["herkunft"].value_counts().items())},
                "betraege": {str(a): round(float(v), 2)
                             for a, v in sorted(gruppe.groupby("betrag_art")["betrag"].sum().items())},
                "betraege_je_herkunft": {
                    str(h): {str(a): round(float(v), 2)
                             for a, v in sorted(g2.groupby("betrag_art")["betrag"].sum().items())}
                    for h, g2 in gruppe.groupby("herkunft")},
            }
        je_zeitraum[k] = block
    return {"zeitraeume": zeitraeume, "je_zeitraum": je_zeitraum,
            "gelesen_aus": ["tagesjournal.parquet (Stands-Paket)"]}


def _abschluss_kennzahlen(abschluesse_dir: Path,
                          abschluesse: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Bestandskennzahlen aus den Monatsabschluessen, die das Paket TRAEGT.

    Der juengste Abschluss und der zwoelf Monate davor — der aeltere nur,
    wenn seine Datei im Paket liegt. Das Paket traegt zwoelf Monate
    (``PAKET_ABSCHLUESSE_ANZAHL``); der Abschluss zwoelf Monate vor dem
    juengsten ist damit der dreizehnte und fehlt. Er wird dann weggelassen
    und nicht aus einer anderen Quelle ersetzt — der Erzeuger hatte ihn
    frueher aus der Ablage gelesen, und die Seite glaubte die Zahl.

    Je Abschluss steht die Konvention des Deckungskapitals dabei; ein
    Vergleich ueber zwei Konventionen ist keine Veraenderung des Bestands.
    Gelesen wird jede Datei ueber ``bestand.abschluss.lies_abschluss``, die
    EINE Stelle, die die Konvention sagt (``models.bestand.
    abschluss_konvention``): die Spalte ``bewertungskonvention``, bei ihrem
    Fehlen die Jahreszeile (geschrieben vor der Umstellung), ``None`` fuer
    einen leeren Abschluss. Vorher las die Seite eine Spalte
    ``dk_konvention``, die kein Abschluss traegt, und nannte so jeden
    Abschluss "jahreszeile" — Vorjahr und Stand verglichen sich gleich
    falsch, ein Wechsel blieb unsichtbar.
    """
    from rechner_pipeline.bestand.abschluss import lies_abschluss
    from rechner_pipeline.models.bestand import AbschlussKonventionFehler

    liegen = {str(a.get("stichtag")): a for a in abschluesse
              if a.get("datei") and (abschluesse_dir / str(a["datei"])).is_file()}
    if not liegen:
        return {}
    juengster = max(liegen)
    j = _dt.date.fromisoformat(juengster)
    try:
        vorjahr = j.replace(year=j.year - 1).isoformat()
    except ValueError:
        vorjahr = j.replace(year=j.year - 1, day=28).isoformat()
    aus: Dict[str, Any] = {}
    for rolle, stichtag in (("aktuell", juengster), ("vorjahr", vorjahr)):
        if stichtag not in liegen:
            continue
        datei = str(liegen[stichtag]["datei"])
        try:
            df, konvention = lies_abschluss(abschluesse_dir / datei)
        except AbschlussKonventionFehler as exc:
            raise FalldatenFehler(f"{datei}: {exc}") from exc
        je_produkt = {
            str(produkt): {
                "vertraege": int(len(teil)),
                "jahresbeitrag": round(float(teil["jahresbeitrag"].sum()), 2),
                "deckungskapital": round(float(teil["deckungskapital"].sum()), 2),
            }
            for produkt, teil in df.groupby("produkt")
        }
        aus[rolle] = {
            "stichtag": stichtag,
            "datei": f"abschluesse/{datei}",
            "dk_konvention": konvention.name,
            "je_produkt": dict(sorted(je_produkt.items())),
            "gesamt": {
                "vertraege": int(len(df)),
                "jahresbeitrag": round(float(df["jahresbeitrag"].sum()), 2),
                "deckungskapital": round(float(df["deckungskapital"].sum()), 2),
            },
        }
    return aus


# --------------------------------------------------------------------------- #
# Die Belegkette: welche Datei des Falls zu welcher Station gehoert
# --------------------------------------------------------------------------- #
#
# Wird in werkzeuge/falldaten.py eingesetzt (Abschnitt "Belegkette").

#: Station je Gate: aus den dreizehn Stationen der Darstellung
#: (``darstellung.GATE_STATION``) — EINE Quelle fuer Karte, Fallseite und
#: Kette.
#: Gates der Linie, nicht des Falls: Sie zeichnen ausserhalb jedes Falls
#: (ADR-025) und haben deshalb keine Station. A-B1 gehoert nicht dazu,
#: obwohl es die Linie abnimmt: Sein Snapshot liegt im Fall und steht an
#: Station 13 (darstellung.STATION_WEITERE_GATES).
GATES_DER_LINIE = ("A-B3",)

#: Wo die Kette keinen Erzeuger nennt, sagt der Ort im Fall-Arbeitsbereich
#: (ADR-002), zu welcher Station eine Datei gehoert: die Lieferung und ihr
#: Register, der Fallauftrag, die Vorverdichtung der Dokumente, die
#: Quellfragmente der Agenten, die Faktenbasis, die Fachspezifikation, die
#: Uebersetzung des Bestands. Der laengste Praefix gewinnt.
ORT_STATION: Tuple[Tuple[str, int], ...] = (
    ("fall.json", 1), ("eingang.json", 1), ("eingang/", 1), ("abgeleitet/auftrag/", 1),
    ("abgeleitet/vorverdichtung/", 2), ("abgeleitet/abox/fragmente/", 2),
    ("abgeleitet/abox/", 3), ("abgeleitet/abox/coverage.json", 4), ("abgeleitet/fachspez/", 5),
    ("abgeleitet/transformation/", 6), ("abgeleitet/abbruch/", 12),
)

#: Titel je Belegrolle (``models.belegrollen.BELEGROLLEN``) — ein
#: geschlossenes Vokabular: Eine Rolle ohne Titel ist ein Testbefund, kein
#: roher Name auf der Seite.
ROLLE_TITEL: Dict[str, str] = {
    "aktuartest": "Ergebnis A-M1", "aktuartest_bericht": "Bericht A-M1",
    "aktuartest_am2": "Ergebnis A-M2", "aktuartest_am2_bericht": "Bericht A-M2",
    "aktuartest_am3": "Ergebnis A-M3", "aktuartest_am3_bericht": "Bericht A-M3",
    "abnahmebericht": "Prüfprotokoll A-M4", "migrationssuite": "Migrationssuite",
    "fuehrungsprobe": "Führungsprobe", "kernaenderung": "Änderungsbeleg Kern",
    "regression": "Regressionsbeleg", "tarifwerk_aenderung": "Änderungsbeleg Tarifwerk",
    "tbox_aenderung": "Änderungsbeleg T-Box", "stellungnahme_aktuariat": "Stellungnahme Aktuariat",
    "fallauftrag": "Fallauftrag", "fallabbruch": "Fallabbruch", "zugangsprobe": "Zugangsprobe",
    "eingang": "Eingangsregister", "anker": "Anker des Stands", "anfangsbestand": "Anfangsbestand",
    "pq3_ledger": "Prüfprotokoll P-Q3", "pb1_ledger": "Prüfprotokoll P-B1",
    "pk1_belege": "Golden-Master-Beleg", "kernstand": "Kernstand", "tboxstand": "Verweis T-Box",
    "tarifwerkstand": "Stand des Tarifwerks", "aq1_snapshot": "Snapshot A-Q1",
    "am1_snapshot": "Snapshot A-M1", "am2_snapshot": "Snapshot A-M2",
    "am3_snapshot": "Snapshot A-M3", "am4_snapshot": "Snapshot A-M4",
    "schichten": "Schichtbeleg", "verankerung": "Verankerung je Vertrag",
}

#: Arten von Belegen, wie die Seite sie ordnet; die kleinste Zahl zuerst.
#: Was mehrfach an einer Station liegt (die Lieferung, die Vorverdichtung,
#: die Quellfragmente), erscheint auf der Karte als EINE Zeile mit Anzahl.
BELEG_ARTEN: Dict[str, Tuple[int, str]] = {
    "entscheid": (1, "Entscheid-Snapshots"), "bericht": (2, "Berichte"),
    "beleg": (3, "Belege"), "lieferung": (3, "Lieferung"),
    "vorverdichtung": (3, "Vorverdichtung"), "fragment": (3, "Quellfragmente"),
    "pruefprotokoll": (4, "Prüfprotokolle"), "daten": (6, "Tabellen und Daten"),
    "verlauf": (9, "Verläufe der Anläufe"), "frueher": (9, "frühere Runden"),
}
_MEHRFACH = ("lieferung", "vorverdichtung", "fragment", "daten")

#: Orte, deren Dateien auch OHNE Bindung durch die Kette auf die Seite
#: duerfen: die deterministische Vorverdichtung der Quellen (Station 2).
#: Ihre Kommandos schreiben kein Protokoll, das sie ueber die Pruefsumme
#: bindet — ein Befund am System, kein Grund, die Extraktion zu
#: verschweigen. Die Seite kennzeichnet sie als nicht gebunden.
ORT_AUCH_UNGEBUNDEN = ("abgeleitet/vorverdichtung/",)


def _gate_station() -> Dict[str, int]:
    import darstellung

    return darstellung.GATE_STATION


def _gate_von(kennung: Any) -> Optional[str]:
    """``P-Q2.zusammenfuehrung`` -> ``P-Q2``, ``entscheid.A-Q1`` -> ``A-Q1``."""
    m = re.search(r"\b([PA]-[A-Z][0-9])\b", str(kennung or ""))
    return m.group(1) if m else None


def _beleg_titel(pfad: str, e: Dict[str, Any], kette: Dict[str, Dict[str, Any]]) -> Tuple[str, str]:
    """(Titel, Art) einer Datei der Kette — aus dem, was die Kette ueber sie
    sagt (Entscheid, Protokoll, Rolle, Erzeuger), sonst aus ihrem Ort."""
    name = pfad.rsplit("/", 1)[-1]
    if e.get("entscheid_von"):
        return (f"Snapshot {e['entscheid_von']}", "entscheid" if e.get("final") else "frueher")
    if pfad.endswith(".historie.jsonl"):
        return (f"Verlauf {name.split('.')[0]}", "verlauf")
    if e.get("protokoll_von"):
        return (f"Prüfprotokoll {e['protokoll_von']}", "pruefprotokoll")
    for _, rolle in e.get("rollen") or []:
        if rolle in ROLLE_TITEL and not rolle.endswith(("_ledger", "_snapshot")):
            return (ROLLE_TITEL[rolle], "bericht" if name.endswith((".html", ".md")) else "beleg")
    if e.get("ableitung_von") in kette:
        titel, _ = _beleg_titel(e["ableitung_von"], kette[e["ableitung_von"]], kette)
        return (f"{titel}, lesbar", "bericht")
    if pfad in ("eingang.json",):
        return ("Eingangsregister", "beleg")
    if pfad == "fall.json":
        return ("Fallmanifest", "beleg")
    if pfad.startswith("eingang/"):
        return (name, "lieferung")
    if pfad.startswith("abgeleitet/auftrag/"):
        return ("Fallauftrag" + (", lesbar" if name.endswith(".md") else ""),
                "bericht" if name.endswith(".md") else "beleg")
    if pfad.startswith("abgeleitet/vorverdichtung/"):
        return (pfad[len("abgeleitet/vorverdichtung/"):], "vorverdichtung")
    if pfad.startswith("abgeleitet/abox/fragmente/"):
        return (name, "fragment")
    if name == "abox.json":
        return ("A-Box, die Faktenbasis", "beleg")
    if name == "coverage.json":
        return ("Abdeckung je Pflichtfeld", "beleg")
    if pfad.startswith("abgeleitet/fachspez/"):
        return ("Fachspezifikation", "bericht")
    if pfad.startswith("abgeleitet/spez/"):
        return ("Tarifspezifikation", "beleg")
    if "-dossier" in name:
        return ("Dossier je Diskrepanz", "bericht")
    if pfad.startswith("abgeleitet/transformation/"):
        if ".spec." in name:
            return ("Übersetzungsvorschrift", "beleg")
        if ".ergebnis." in name:
            return ("Übersetzungsergebnis", "beleg")
        return (pfad[len("abgeleitet/"):], "daten")
    if ".beleg." in name:
        return ("Golden-Master-Beleg", "beleg")
    if name.endswith(".html"):
        erzeuger = sorted(set(e.get("geschrieben_von") or []))
        if erzeuger:
            return (f"Bericht {erzeuger[0]}", "bericht")
        return (name[:-5].replace("-", " ").replace("_", " ").capitalize(), "bericht")
    return (pfad[len("abgeleitet/"):] if pfad.startswith("abgeleitet/") else pfad, "daten")


def _anzahl(wert: Any) -> int:
    """Eine Zaehlung aus einem Beleg: eine Zahl oder eine Liste (deren Laenge)."""
    if isinstance(wert, (list, tuple, dict)):
        return len(wert)
    try:
        return int(wert or 0)
    except (TypeError, ValueError):
        return 0


def systemaenderung(fall: Path, umbau_modell: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Was der Fall am Zielsystem geaendert hat — aus den Aenderungsbelegen,
    die A-K2 (Rechenkern) und A-T1 (Tarifwerk) abnehmen, je Modul bzw. je
    Teil mit den Zeilen, die dazukamen und wegfielen. Ein Lauf mit
    Umbaubudget (vor der Abnahme des Stands) traegt es dort; beides zusammen
    ist die Gruppe.

    Gezeigt werden Zahlen je Datei, nicht die Betreffzeilen der Commits: Die
    sind Sprache der Entwicklung und stehen woertlich im lesbaren
    Aenderungsbeleg, der an Station 7 verlinkt ist."""
    from rechner_pipeline.models import kernabnahme as ka
    from rechner_pipeline.models import tarifwerkabnahme as ta

    aus: Dict[str, Any] = {"umbaubudget": bool((umbau_modell or {}).get("vorhanden"))}
    kern = _json(fall / ka.AENDERUNG_RELATIV)
    if isinstance(kern, dict):
        module = [m for m in kern.get("module") or [] if isinstance(m, dict)]
        aus["kern"] = {
            "von_version": kern.get("von_version"), "nach_version": kern.get("nach_version"),
            "veraendert": bool(kern.get("veraendert")),
            "module_gesamt": len(module),
            "module": [{"modul": str(m.get("modul")), "hinzu": _anzahl(m.get("hinzu")),
                        "weg": _anzahl(m.get("weg")), "commits": _anzahl(m.get("commits"))}
                       for m in module
                       if m.get("hinzu") or m.get("weg") or m.get("commits") or m.get("nicht_committet")],
            "commits": len(kern.get("commits") or []),
            "sicht": ka.SICHT_RELATIV if (fall / ka.SICHT_RELATIV).is_file() else None,
        }
    tw = _json(fall / ta.AENDERUNG_RELATIV)
    if isinstance(tw, dict):
        aus["tarifwerk"] = {
            "veraendert": bool(tw.get("veraendert")),
            "tarifplaene": [str(t.get("pfad")) for t in tw.get("tarifplaene") or []
                            if isinstance(t, dict) and t.get("zustand") not in (None, "unveraendert")],
            "teile": [{"pfad": str(t.get("pfad")), "hinzu": _anzahl(t.get("hinzu")),
                       "weg": _anzahl(t.get("weg"))}
                      for t in tw.get("teile") or []
                      if isinstance(t, dict) and (t.get("hinzu") or t.get("weg") or t.get("nicht_committet"))],
            "generationen": [{"generation": g.get("generation"), "config": g.get("config"),
                              "felder": len(g.get("felder") or [])}
                             for g in tw.get("generationen") or []
                             if isinstance(g, dict) and g.get("zustand") not in (None, "unveraendert")],
            "commits": len(tw.get("commits") or []),
            "sicht": ta.SICHT_RELATIV if (fall / ta.SICHT_RELATIV).is_file() else None,
        }
    aus["vorhanden"] = bool(aus["umbaubudget"] or aus.get("kern") or aus.get("tarifwerk"))
    aus["gelesen_aus"] = [p for p in (ka.AENDERUNG_RELATIV, ta.AENDERUNG_RELATIV) if (fall / p).is_file()]
    return aus


def _gelesen_aus(knoten: Any) -> set:
    """Alle fallrelativen Pfade, die ein Abschnitt des Modells unter
    ``gelesen_aus`` nennt (ohne Muster)."""
    aus: set = set()
    if isinstance(knoten, dict):
        for k, v in knoten.items():
            if k == "gelesen_aus" and isinstance(v, list):
                aus |= {str(x) for x in v if isinstance(x, str) and "*" not in x and " " not in x}
            else:
                aus |= _gelesen_aus(v)
    elif isinstance(knoten, list):
        for v in knoten:
            aus |= _gelesen_aus(v)
    return aus


def fallauftrag(fall: Path) -> Dict[str, Any]:
    """Der Auftrag des Falls (ADR-026), wie der Vorlagen-Erzeuger ihn ablegt
    und der Vorstand ihn mit A-M6 zeichnet — Text, abgebendes Haus und die
    Rolle, die den Fall fuehrt. Gezeichnet ist der Inhalt im Snapshot; hier
    steht, was die Vorlage sagt."""
    from rechner_pipeline.models import fallauftrag as fa

    d = _json(fall / fa.AUFTRAG_RELATIV)
    if not isinstance(d, dict):
        return {"vorhanden": False}
    pl = d.get("programmleitung") if isinstance(d.get("programmleitung"), dict) else {}
    return {"vorhanden": True, "auftrag": d.get("auftrag"),
            "abgebendes_haus": d.get("abgebendes_haus"),
            "programmleitung": pl.get("rolle"),
            "mandate": sorted((d.get("mandate") or {}).keys()),
            "gelesen_aus": [fa.AUFTRAG_RELATIV]}


def zugangsprobe(fall: Path) -> Dict[str, Any]:
    """Die Zugangsprobe (ADR-022): zwei Laeufe auf einer Kopie der Ablage,
    mit und ohne den Eingang, und was sie verglichen haben."""
    from rechner_pipeline.models import zugangsprobe as zp

    d = _json(fall / zp.BELEG_RELATIV)
    if not isinstance(d, dict):
        return {"vorhanden": False}
    vergleiche = [v for v in d.get("vergleiche") or [] if isinstance(v, dict)]
    mit_soll = [v for v in vergleiche if v.get("ok") is not None]
    folge = d.get("folgetermin") if isinstance(d.get("folgetermin"), dict) else {}
    return {"vorhanden": True, "bestanden": d.get("bestanden"),
            "stichtag": d.get("stichtag"), "bis": d.get("bis"),
            # Ein Wert ohne Soll (ok = null) ist ausgewiesen, nicht verglichen.
            "vergleiche": len(mit_soll),
            "ohne_soll": len(vergleiche) - len(mit_soll),
            "vergleiche_ok": sum(1 for v in mit_soll if v.get("ok") is True),
            "folgetermin": {"stichtag": folge.get("stichtag"), "gedeckt": folge.get("gedeckt"),
                            "grund": folge.get("grund")} if folge else None,
            "groessen": sorted({str(v.get("groesse")) for v in vergleiche if v.get("groesse")}),
            "befunde": len(d.get("befunde") or []),
            "gelesen_aus": [zp.BELEG_RELATIV]}


def belegkette(fall: Path, kette_modell: Optional[Dict[str, Any]] = None,
               quellen_der_darstellung: Sequence[str] = ()) -> Dict[str, Any]:
    """Je Datei des Falls die Station, an der sie Beleg ist — erhoben aus
    dem, was die Kette selbst sagt, nicht aus einer Liste.

    Die Seite trug die Artefakte je Station bis zum 03.10.2026 in einer
    Tabelle von Hand (``darstellung.PROZESS_ARTEFAKTE``) und kopierte nach
    einer Positivliste von Ordnern. Ein neuer Beleg — der Aenderungsbeleg
    des Kerns, der Fallauftrag, die Zugangsprobe — fehlte, bis ihn jemand
    nachtrug. Jetzt gilt in dieser Reihenfolge, die erste Regel trifft:

    1. Der Ort im Fall-Arbeitsbereich, wo die Kette keinen Erzeuger kennt
       (:data:`ORT_STATION`) — aber nur fuer eine Datei, die die Kette
       ueberhaupt fuehrt (gelesen, geschrieben, genannt, gebunden) oder die
       das Eingangsregister traegt. Ein Arbeitsstand neben dem Beleg ist kein
       Beleg, auch wenn er im selben Ordner liegt. Benannte Ausnahme: die
       deterministische Vorverdichtung der Quellen
       (:data:`ORT_AUCH_UNGEBUNDEN`) steht auch ungebunden an ihrem Ort,
       markiert als ``ungebunden``.
    2. Ein Entscheid-Snapshot gehoert zur Station seines Gates.
    3. Ein Pruefprotokoll (``*.gate.json``) zur Station seines Gates.
    4. Ein Pflichtbeleg eines Snapshots — ueber seine PRUEFSUMME gefunden,
       nicht ueber einen Namen — zur Station des Gates, dessen Beleg er ist
       (die Belege der Abschlussabnahme zur Station ihres eigenen Gates).
    5. Was ein Gate laut Protokoll geschrieben hat, zur Station des Gates.
    6. Der Beleg einer Entscheidung, den die A-Box mit Pfad und Pruefsumme
       nennt, zur Quellenabnahme (A-Q1).
    7. Was ein Gate zur Pruefung gelesen hat, zur fruehesten Station, die
       es liest. Das Protokoll einer ZEICHNUNG zaehlt hier nicht: Es nennt
       alles, was der Entscheid bindet, und prueft nichts.
    8. Was ein Pruefprotokoll nur mit seiner Pruefsumme nennt, zur Station
       des Gates — nach dem Lesen, denn ein Gate, das eine Datei liest,
       sagt mehr ueber sie als eines, das ihren Hash festhaelt.
    9. Geschwister: der Verlauf neben dem Protokoll, der Beleg eines
       Kommandos neben seinem Protokoll, die lesbare Fassung neben ihrem
       Beleg.

    Dazu die Quellen der Darstellung: Was das Datenmodell zu einer Zahl der
    Seite liest (``gelesen_aus``), kommt mit — ohne Station, im Verzeichnis
    —, damit jede Zahl ein Artefakt daneben hat.

    Was keine Regel trifft, gehoert zu keiner Station und kommt nicht auf
    die Seite: die Arbeitsunterlagen der Agenten, Reste frueherer
    Durchgaenge. Gezaehlt wird es trotzdem — als Zahl je Ordner.
    """
    fall = Path(fall)
    praefix = f"faelle/{fall.name}/"
    finale = {str(e.get("snapshot_datei")) for e in (kette_modell or {}).get("entscheide") or []
              if e.get("geltend")}
    pfade: Dict[str, Path] = {}
    for p in sorted(fall.rglob("*")):
        if p.is_file() and not p.name.startswith("."):
            pfade[p.relative_to(fall).as_posix()] = p
    hashes = {r: hashlib.sha256(p.read_bytes()).hexdigest() for r, p in pfade.items()}
    je_hash: Dict[str, List[str]] = {}
    for r, h in hashes.items():
        je_hash.setdefault(h, []).append(r)
    kette: Dict[str, Dict[str, Any]] = {
        r: {"sha256": h, "station": None, "regel": None, "rollen": [],
            "gelesen_von": [], "geschrieben_von": [], "genannt_von": [], "gebunden_von": []}
        for r, h in hashes.items()}
    ausserhalb: Dict[str, List[str]] = {}

    def fallrelativ(k: Any) -> Optional[str]:
        k = str(k)
        if k.startswith("/"):
            i = k.find(praefix)
            return k[i + len(praefix):] if i >= 0 else None
        if k.startswith(praefix):
            return k[len(praefix):]
        return k if k in kette else None

    for r in sorted(pfade):
        if not re.match(r"abgeleitet/diagnostics[^/]*/[^/]+\.gate\.json$", r):
            continue
        d = _json(pfade[r])
        g = _gate_von((d or {}).get("gate")) if isinstance(d, dict) else None
        if not g:
            continue
        kette[r]["protokoll_von"] = g
        zeichnung = str(d.get("gate", "")).startswith("entscheid.")
        summary = d.get("summary") if isinstance(d.get("summary"), dict) else {}
        if not zeichnung:
            for k in d.get("input_hashes") or {}:
                f = fallrelativ(k)
                if f in kette:
                    kette[f]["gelesen_von"].append(g)
                elif not str(k).startswith(("/", praefix)):
                    ausserhalb.setdefault(str(k), []).append(g)
            # Pruefsummen, die das Protokoll nennt (Laufmanifest, Beleg):
            for h in set(re.findall(r"\b[0-9a-f]{64}\b", json.dumps(summary))):
                for f in je_hash.get(h, []):
                    if f != r:
                        kette[f]["genannt_von"].append(g)
        geschrieben = list(summary.get("output_hashes") or {}) + (
            list(summary["belege"]) if isinstance(summary.get("belege"), dict) else [])
        for k in geschrieben:
            f = fallrelativ(k)
            if f in kette and not f.startswith("entscheide/"):
                kette[f]["geschrieben_von"].append(g)

    for r in sorted(pfade):
        if not re.match(r"entscheide/[A-Z]-[A-Z][0-9]-[0-9a-f]{64}\.json$", r):
            continue
        d = _json(pfade[r])
        g = _gate_von((d or {}).get("gate")) if isinstance(d, dict) else None
        if not g:
            continue
        kette[r]["entscheid_von"] = g
        kette[r]["final"] = (not finale) or r in finale
        for rolle, belege in (d.get("pflichtbelege") or {}).items():
            for h in belege or []:
                for f in je_hash.get(str(h), []):
                    if f != r:
                        kette[f]["rollen"].append((g, str(rolle)))
        for k, h in (d.get("artefakt_hashes") or {}).items():
            f = fallrelativ(k)
            if f in kette and kette[f]["sha256"] == h:
                kette[f]["gebunden_von"].append(g)

    from rechner_pipeline.gates.register import _BELEGROLLE_GATE

    def setze(f: str, station: Optional[int], regel: str) -> None:
        if station and kette[f]["station"] is None:
            kette[f]["station"], kette[f]["regel"] = station, regel

    # Belege einer Entscheidung, die die A-Box mit Pfad und Pruefsumme nennt.
    abox = _json(fall / "abgeleitet" / "abox" / "abox.json") or {}
    for d in abox.get("diskrepanzen") or []:
        beleg = (d.get("entscheidung") or {}).get("beleg") if isinstance(d, dict) else None
        if isinstance(beleg, dict) and str(beleg.get("datei")) in kette \
                and kette[str(beleg.get("datei"))]["sha256"] == beleg.get("sha256"):
            kette[str(beleg["datei"])]["entscheidungsbeleg"] = True

    registriert = {f"eingang/{q.get('datei')}" for q in (_json(fall / "eingang.json") or {}).get("quellen") or []
                   if isinstance(q, dict)} | {"eingang.json", "fall.json"}

    def gefuehrt(f: str, e: Dict[str, Any]) -> bool:
        return bool(f in registriert or e["gelesen_von"] or e["geschrieben_von"] or e["genannt_von"]
                    or e["rollen"] or e["gebunden_von"] or e.get("entscheid_von")
                    or e.get("protokoll_von") or e.get("entscheidungsbeleg"))

    orte = sorted(ORT_STATION, key=lambda e: -len(e[0]))
    for f, e in kette.items():
        fuehrt = gefuehrt(f, e)
        if fuehrt or f.startswith(ORT_AUCH_UNGEBUNDEN):
            for ort, station in orte:
                if f == ort or (ort.endswith("/") and f.startswith(ort)):
                    setze(f, station, "Ort im Fall")
                    if not fuehrt:
                        e["ungebunden"] = True
                    break
        setze(f, _gate_station().get(e.get("entscheid_von") or ""), "Entscheid")
        setze(f, _gate_station().get(e.get("protokoll_von") or ""), "Pruefprotokoll")
        for g, rolle in e["rollen"]:
            setze(f, _gate_station().get(_BELEGROLLE_GATE.get(rolle) or g), "Pflichtbeleg")
        for g in e["geschrieben_von"]:
            setze(f, _gate_station().get(g), "geschrieben")
        if e.get("entscheidungsbeleg"):
            setze(f, _gate_station().get("A-Q1"), "Beleg einer Entscheidung")
    for f, e in kette.items():
        if e["station"] is None and e["gelesen_von"]:
            setze(f, min(_gate_station().get(g, 99) for g in e["gelesen_von"]), "gelesen")
            if kette[f]["station"] == 99:
                kette[f]["station"] = None
    for f, e in kette.items():
        for g in e["genannt_von"]:
            setze(f, _gate_station().get(g), "im Protokoll genannt")
    for f, e in kette.items():
        if e["station"] is not None:
            continue
        ordner, _, name = f.rpartition("/")
        geschwister = []
        if name.endswith(".historie.jsonl"):
            geschwister.append(f"{ordner}/{name[:-len('.historie.jsonl')]}.gate.json")
        if ordner.startswith("abgeleitet/diagnostics") and "." in name:
            geschwister.append(f"{ordner}/{name.split('.', 1)[0]}.gate.json")
        if name.endswith(".md"):
            geschwister.append(f[:-3] + ".json")
            e["ableitung_von"] = f[:-3] + ".json"
        for b in geschwister:
            if b in kette and kette[b]["station"]:
                setze(f, kette[b]["station"], "Geschwister")
                break
    for f in quellen_der_darstellung:
        if f in kette and kette[f]["station"] is None:
            kette[f]["quelle_der_darstellung"] = True

    # Dieselben Bytes zweimal im Fall (eine Kopie in einem Arbeitsordner):
    # Es bleibt die Fassung, deren Station die staerkere Regel traegt — ein
    # Pfad, den die Kette ausdruecklich nennt, schlaegt einen, der nur ueber
    # seine Pruefsumme mitgefunden wurde; ein Arbeitsordner der Agenten
    # verliert. Die andere ist eine Doublette und kommt nicht auf die Seite.
    staerke = {"Ort im Fall": 1, "Entscheid": 1, "Pruefprotokoll": 1, "geschrieben": 2,
               "gelesen": 2, "Pflichtbeleg": 3, "Beleg einer Entscheidung": 3,
               "im Protokoll genannt": 4, "Geschwister": 5}
    gesehen: Dict[str, str] = {}
    for f in sorted(kette, key=lambda f: (staerke.get(str(kette[f]["regel"]), 9),
                                           f.startswith("abgeleitet/protokoll/"), len(f), f)):
        e = kette[f]
        if not e["station"]:
            continue
        if e["sha256"] in gesehen:
            e["station"], e["regel"], e["doublette_von"] = None, None, gesehen[e["sha256"]]
        else:
            gesehen[e["sha256"]] = f
    for f, e in kette.items():
        e["titel"], e["art"] = _beleg_titel(f, e, kette)
        if e.get("ableitung_von") not in kette:
            e.pop("ableitung_von", None)
    je_station: Dict[str, List[str]] = {}
    for f in sorted(kette, key=lambda f: (BELEG_ARTEN[kette[f]["art"]][0], kette[f]["titel"], f)):
        if kette[f]["station"]:
            je_station.setdefault(str(kette[f]["station"]), []).append(f)
    ohne: Dict[str, int] = {}
    for f, e in kette.items():
        if not e["station"]:
            ohne[f.rsplit("/", 1)[0] if "/" in f else "."] = ohne.get(f.rsplit("/", 1)[0] if "/" in f else ".", 0) + 1
    # In Arbeit, aus der Kette: eine Station ohne Gate hat keine Pruefung
    # und keine Abnahme; ein Pflichtbeleg, der als Ausnahme gefuehrt wird,
    # ist da, aber nicht gefahren.
    mit_gate = set(_gate_station().values())
    in_arbeit: Dict[str, List[str]] = {}
    for n in range(1, 14):
        if n not in mit_gate:
            in_arbeit.setdefault(str(n), []).append("Prüfung und Abnahme")
    try:
        from rechner_pipeline.models import kernabnahme as ka
        reg = _json(fall / ka.REGRESSION_RELATIV)
        if ka.ist_ausnahme(reg):
            in_arbeit.setdefault(str(_gate_station()["A-K2"]), []).append("Regression")
    except ImportError:  # pragma: no cover
        pass
    return {
        "dateien": kette,
        "je_station": je_station,
        "in_arbeit": in_arbeit,
        "ohne_station": dict(sorted(ohne.items())),
        "ausserhalb": {k: sorted(set(v)) for k, v in sorted(ausserhalb.items())},
        "gelesen_aus": ["abgeleitet/diagnostics*/*.gate.json", "entscheide/*.json",
                        "Pruefsummen aller Dateien des Falls"],
    }


def betrieb(paket: Optional[Path],
            anker_datei: Optional[Path] = None,
            fall: Optional[Path] = None) -> Dict[str, Any]:
    """Der lebende Bestand aus dem Stands-Paket der Laufzeitumgebung.

    Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8.3: Die
    oeffentliche Seite bleibt eine gestempelte Momentaufnahme; ihre
    Kennzahlen zum laufenden Bestand kommen aus einem exportierten
    Stands-Paket (``python -m rechner_pipeline.betrieb.seite --paket``),
    nicht aus einem Fall — erzeugt, nie abgetippt. Ohne Paket bleibt der
    Abschnitt weg; er ist kein Pflichtabschnitt eines Falls.
    """
    if paket is None:
        return {"vorhanden": False}
    paket = Path(paket)
    stand = _json(paket / "stand.json")
    # Schema 5: das Paket traegt Tagesjournal (seit 3), Anker (seit 4) und
    # die juengsten Monatsabschluesse. Ein aelteres Paket belegt jeweils
    # einen Teil seiner eigenen Zahlen nicht und wird deshalb nicht
    # veroeffentlicht — wie schon die Erstfassung ohne Belegdateien.
    if not isinstance(stand, dict) or stand.get("schema_version") != 5:
        raise FalldatenFehler(
            f"{paket}: kein Stands-Paket (stand.json mit schema_version 5 fehlt; "
            "ein aelteres Paket nennt keinen Anker oder keine Abschluesse und "
            "belegt damit einen Teil seiner Zahlen nicht — die Protokollkette "
            "schuetzt ihre letzte Zeile nicht, und genau aus ihr leitet "
            "stand.json ab) — ein neuer Export heilt es: "
            "python -m rechner_pipeline.betrieb.seite --stand <daten> "
            "--paket <ziel> --anker <verzeichnis>"
        )
    prov = stand.get("provenienz") or {}
    # EINE Lesung je Datei (Angriffsrunde nach T27): Jede Pruefung las ihre
    # Datei selbst — gehasht wurde das Tagesjournal auf der ersten Lesung,
    # gezaehlt auf der zweiten, und ein Schreiber dazwischen verdoppelte
    # die veroeffentlichten Buchungen. Das Paket wird deshalb einmal
    # gelesen, jede Datei gegen ihren Hash gehalten und in ein privates
    # Verzeichnis eingefroren; ALLE Pruefungen laufen dort.
    import tempfile

    with tempfile.TemporaryDirectory(prefix="stands-paket-") as tmp:
        eingefroren = _friere_paket_ein(paket, stand, Path(tmp))
        try:
            protokoll_roh = _pruefe_stands_paket(eingefroren, stand, prov)
            verankerung = _pruefe_anker(eingefroren, stand, anker_datei, fall, protokoll_roh,
                                        ort=paket)
            # Nachgerechnet, nicht uebernommen: Geschaeftsentwicklung und
            # Bestandskennzahlen aus den Bytes, die eben gegen ihren Hash
            # gingen. stand.json behauptet darueber nichts.
            from rechner_pipeline.bestand.parquet_io import read_portfolio
            from rechner_pipeline.betrieb.seite import PAKET_ABSCHLUESSE_DIR, PAKET_JOURNAL
            from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

            journal = read_portfolio(eingefroren / PAKET_JOURNAL,
                                     expected_columns=TAGESJOURNAL_NAMES)
            entwicklung = _geschaeftsentwicklung(
                journal, _dt.date.fromisoformat(str(stand.get("stand"))),
                _dt.date.fromisoformat(str(stand.get("gefuehrt_seit"))))
            kennzahlen = _abschluss_kennzahlen(
                eingefroren / PAKET_ABSCHLUESSE_DIR, list(stand.get("abschluesse") or []))
        except FalldatenFehler as exc:
            raise FalldatenFehler(str(exc).replace(str(eingefroren), str(paket))) from exc
    return {
        "vorhanden": True,
        "stand": stand.get("stand"),
        "gefuehrt_seit": stand.get("gefuehrt_seit"),
        "bestand": stand.get("bestand") or {},
        "neugeschaeft": stand.get("neugeschaeft") or {},
        "buchungen": {
            "gesamt": (stand.get("buchungen") or {}).get("gesamt"),
            "je_ereignis": (stand.get("buchungen") or {}).get("je_ereignis") or {},
        },
        "geschaeftsentwicklung": entwicklung,
        "abschluss_kennzahlen": kennzahlen,
        "abschluesse": stand.get("abschluesse") or [],
        "uebernahmen": stand.get("uebernahmen") or [],
        "provenienz": prov,
        "dateien": stand.get("dateien") or {},
        # Die Luecken des Stands (T22-05: gingen beim Import verloren).
        "luecken": list(stand.get("luecken") or []),
        "quelle": str(paket),
        "verankerung": verankerung,
        # Ausgewiesen, nicht behauptet (Runde C): Die Protokollzeilen sind mit
        # dem Betriebsschluessel gezeichnet; wer ihn nicht haelt, kann die
        # Signatur nicht nachrechnen. Geprueft sind Kette, Schema-Folge,
        # Form der Zeichnung und Vorlauf-Pin — die Signatur prueft der Export.
        "protokoll_zeichnung": {
            "signatur": "nicht pruefbar",
            "grund": "der Konsument haelt keinen Betriebsschluessel; die Signatur "
                     "jeder Zeile prueft der Export vor dem Verankern",
        },
    }


_SKILL_MARKE = re.compile(r"``([a-z][a-z0-9-]*)``")


def _skills_aus_definition(text: str) -> List[str]:
    """Die Skills, die eine Agentendefinition unter "Was du tust (Skills)"
    nennt — in der Reihenfolge der Nennung, ohne Dubletten. Gemessen am
    Text, nicht behauptet: Eine Rolle hat die Faehigkeiten, die ihre
    Definition ihr gibt."""
    if "## Was du tust (Skills)" not in text:
        return []
    abschnitt = text.split("## Was du tust (Skills)", 1)[1]
    abschnitt = abschnitt.split("\n## ", 1)[0]
    aus: List[str] = []
    for name in _SKILL_MARKE.findall(abschnitt):
        if name not in aus:
            aus.append(name)
    return aus


def _bibliotheken(repo: Path) -> List[Dict[str, Any]]:
    """Die Laufzeitbibliotheken aus pyproject.toml, je Bibliothek die
    Module des Systems, die sie importieren — die Werkzeuge, mit denen
    Lieferungen gelesen werden (Excel, PDF, Parquet), gemessen an den
    Importen, nicht an einer Liste."""
    import tomllib
    try:
        daten = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return []
    aus: List[Dict[str, Any]] = []
    quelltexte = {q: q.read_text(encoding="utf-8", errors="replace")
                  for q in (repo / "src" / "rechner_pipeline").rglob("*.py")}
    for eintrag in (daten.get("project") or {}).get("dependencies") or []:
        name, _, version = str(eintrag).partition("==")
        muster = re.compile(rf"^\s*(import|from)\s+{re.escape(name)}\b", re.M)
        module = sorted(str(q.relative_to(repo / "src" / "rechner_pipeline"))[:-3]
                        for q, t in quelltexte.items() if muster.search(t))
        aus.append({"name": name, "version": version, "module": module})
    return aus


def beschreibung(text: str) -> str:
    """Die Beschreibung (``description:``) im Kopf einer Agenten- oder
    Skill-Definition, Zeilen zu einem Leerraum zusammengezogen."""
    kopf = text.split("---")[1] if text.startswith("---") else ""
    if "description:" not in kopf:
        return ""
    return " ".join(
        zeile.strip() for zeile in kopf.split("description:")[-1].split("tools:")[0].splitlines()
    ).lstrip(">- ").strip()


def fingerabdruck(text: str) -> str:
    """Der Stand, gegen den ein Seitentext geschrieben ist: die ersten zwoelf
    Stellen des SHA-256 der Beschreibung seiner Definition."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def rollen(fall: Path, kette_modell: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Wer legt vor, wer zeichnet — aus den Agentendefinitionen und den
    Entscheid-Snapshots des Falls.

    Die Agentenrollen des Werkzeugs stehen versioniert unter
    .claude/agents/<rolle>.md (Name, Beschreibung, Werkzeugliste). Wer im
    Fall gezeichnet hat, sagt jeder Snapshot selbst: Rolle (aus dem
    Schluessel bestimmt), Schluesselklasse und Mandat (ADR-018). Dass keine
    Agentenrolle einen Entscheid traegt, wird hier an den Snapshots
    GEMESSEN, nicht behauptet.

    Bis 2026-09-22 las diese Funktion faelle/zeichnungsordnung.json — eine
    Ordnung nach Schema 1, die models.zeichnung seit ADR-018 ausdruecklich
    abweist. Die Seite zeigte damit Rollen, die es nicht mehr gibt
    (plv-aktuar, plv-it, der Platzhalter "mensch" mit allen Gates), und
    ein Gate, das es nicht mehr gibt (A-K1). Die Ordnung, mit der die
    Entscheide wirklich gezeichnet wurden, liegt ausserhalb des Repos; ihr
    Hash steht in jedem Snapshot, und mehr braucht die Seite nicht.
    """
    repo = Path(__file__).resolve().parent.parent
    agenten: List[Dict[str, Any]] = []
    for pfad in sorted((repo / ".claude" / "agents").glob("*.md")):
        text = pfad.read_text(encoding="utf-8")
        kopf = text.split("---")[1] if text.startswith("---") else ""
        name = pfad.stem
        satz = beschreibung(text)
        werkzeuge = [w.strip() for w in kopf.split("tools:")[-1].splitlines()[0].split(",")] if "tools:" in kopf else []
        agenten.append({
            "name": name,
            "kennung": f"agent/{name}",
            "beschreibung": satz,
            # Ohne tools:-Zeile hat eine Definition ALLE Werkzeuge — das
            # ist kein leerer Werkzeugkasten.
            "werkzeuge": [w for w in werkzeuge if w] if "tools:" in kopf else ["*"],
            # Was die Definition ueber sich selbst sagt — woertlich, nicht interpretiert.
            "zeichnet_nie": "never signs" in satz.lower(),
            "entscheidet_nie": ("does not decide" in satz.lower()
                                or "never decides" in satz.lower()),
            "skills": _skills_aus_definition(text),
        })
    faehigkeiten = sorted(p.name for p in (repo / ".claude" / "skills").iterdir() if p.is_dir())
    genannt = {sk for a in agenten for sk in a["skills"]}
    # Die GELTENDEN Entscheide je Gate (``kette``): die finale Kette der
    # Abschlussabnahme und dazu Fallauftrag, Abnahmen des Stands und Zugang.
    finale = [e for e in (kette_modell or {}).get("entscheide") or []
              if e.get("geltend") or e.get("in_finaler_kette")]
    zeichnungen = [{
        "gate": e.get("gate"),
        "rolle": e.get("rolle"),
        "schluesselklasse": e.get("schluesselklasse"),
        "mandat": bool(e.get("mandat_sha256")),
        "entscheid": e.get("entscheid"),
        "entschieden_am": str(e.get("entschieden_am") or "")[:10],
    } for e in finale]
    return {
        "vorhanden": bool(agenten),
        "agenten": agenten,
        "faehigkeiten": faehigkeiten,
        # Beides muss leer sein: ein Skill, den keine Rolle nennt, und
        # eine Rolle, die einen Skill nennt, den es nicht gibt.
        "skills_ohne_rolle": sorted(set(faehigkeiten) - genannt),
        "skills_unbekannt": sorted(genannt - set(faehigkeiten)),
        "bibliotheken": _bibliotheken(repo),
        "zeichnungen": zeichnungen,
        # Gates der finalen Kette, die eine Agentenrolle oder ein
        # Agentenschluessel entschieden hat — muss leer sein (ADR-018).
        "agenten_gezeichnet": sorted({str(z["gate"]) for z in zeichnungen
                                      if str(z.get("rolle") or "").startswith("agent/")
                                      or z.get("schluesselklasse") == "agent"}),
        "gelesen_aus": [".claude/agents/*.md", "entscheide/*.json (geltende Entscheide)",
                        ".claude/skills/", "pyproject.toml", "src/rechner_pipeline/**/*.py"],
    }
def _friere_paket_ein(paket: Path, stand: Dict[str, Any], ziel: Path) -> Path:
    """Jede in stand.json genannte Datei EINMAL lesen, gegen ihren Hash
    halten und nach ``ziel`` schreiben; stand.json dazu. Rueckgabe: das
    eingefrorene Paket."""
    import hashlib

    eingefroren = ziel / "paket"
    eingefroren.mkdir()
    (eingefroren / "stand.json").write_text(
        json.dumps(stand, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    for name, soll in sorted((stand.get("dateien") or {}).items()):
        quelle = paket / str(name)
        if Path(str(name)).is_absolute() or ".." in Path(str(name)).parts:
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} liegt nicht im Paket")
        if not quelle.is_file():
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} fehlt")
        roh = quelle.read_bytes()
        if hashlib.sha256(roh).hexdigest() != soll:
            raise FalldatenFehler(f"{paket}: Belegdatei {name!r} hat nicht den Hash aus stand.json")
        ziel_datei = eingefroren / str(name)
        ziel_datei.parent.mkdir(parents=True, exist_ok=True)
        ziel_datei.write_bytes(roh)
    return eingefroren


AUFWAND_DATEI = "abgeleitet/aufwand.json"


def aufwand(fall: Path, kette_modell: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Dauer und Aufwand der Uebernahme.

    Die Dauer ist Uhrzeit vom ersten Fallauftrag (fruehester
    Entscheid-Snapshot A-M6) bis zur Zugangsabnahme (geltender Entscheid A-B2),
    Wartezeit auf Entscheide eingeschlossen — gemessen an den Snapshots
    (Entscheid des Maintainers 05.10.2026). Die Zugangsabnahme ist die letzte
    Abnahme vor dem Zugang; der Zugang selbst ist ein Vorgang der Laufzeit
    und zaehlt nicht mehr dazu (verworfen: Ende, wenn der Zugang steht — in
    Fall 3 knapp 14 Minuten spaeter, belegt nur im Protokoll der Laufzeit).
    Den Verbrauch der Agenten haelt ``werkzeuge/aufwand.py`` in
    ``abgeleitet/aufwand.json`` fest; fehlt die Datei, bleibt der Aufwand
    offen, statt geschaetzt zu werden.
    """
    import datetime as _dt

    def zeit(e: Dict[str, Any]) -> Optional[_dt.datetime]:
        try:
            t = _dt.datetime.fromisoformat(str(e.get("entschieden_am")).replace("Z", "+00:00"))
        except ValueError:
            return None
        if t.tzinfo is None:
            raise FalldatenFehler(f"{e.get('gate')}: entschieden_am ohne Zeitzone — die Dauer "
                                  "waere nicht eindeutig")
        return t

    # Nur unversehrte Snapshots: Ein verletzter A-M6 mit frueherem Datum
    # verlaengerte sonst die Dauer (der geltende A-B2 ist ohnehin geprueft).
    entscheide = [e for e in (kette_modell or {}).get("entscheide") or []
                  if e.get("strukturell_verifiziert") is not False]
    auftraege = sorted(t for t in (zeit(e) for e in entscheide if e.get("gate") == "A-M6") if t)
    zugaenge = sorted(t for t in (zeit(e) for e in entscheide if e.get("gate") == "A-B2"
                                  and (e.get("geltend") or e.get("in_finaler_kette"))) if t)
    dauer = None
    if auftraege and zugaenge and zugaenge[-1] > auftraege[0]:
        dauer = {"von_gate": "A-M6", "bis_gate": "A-B2",
                 "von": auftraege[0].isoformat(), "bis": zugaenge[-1].isoformat(),
                 "sekunden": int((zugaenge[-1] - auftraege[0]).total_seconds())}
    agenten = None
    if (fall / AUFWAND_DATEI).exists():
        daten = _json(fall / AUFWAND_DATEI)
        summe = daten.get("summe") if isinstance(daten, dict) else None
        felder = ("antworten", "eingabe", "cache_schreiben", "cache_lesen", "ausgabe")
        # Jede Summe eine ganze Zahl ab null — eine fehlende oder kaputte zeigte
        # sonst 0 oder einen negativen Wert als Angabe (Gegenlesen 05.10.2026).
        if not (isinstance(daten, dict) and daten.get("art") == "aufwand" and isinstance(summe, dict)
                and all(type(summe.get(f)) is int and summe[f] >= 0 for f in felder)):
            raise FalldatenFehler(f"{AUFWAND_DATEI}: kein Aufwand nach Schema (art, summe mit "
                                  f"{', '.join(felder)} als ganze Zahlen ab null)")
        je_rolle = daten.get("je_rolle") or {}
        # Die Tabelle je Rolle steht auf der Seite: dieselbe Pruefung, und die
        # Rollen ergeben zusammen genau die Summe.
        if not (isinstance(je_rolle, dict) and je_rolle
                and all(isinstance(w, dict) and all(type(w.get(f)) is int and w[f] >= 0 for f in felder)
                        for w in je_rolle.values())
                and all(sum(w[f] for w in je_rolle.values()) == summe[f] for f in felder)):
            raise FalldatenFehler(f"{AUFWAND_DATEI}: je_rolle fehlt, ist unvollstaendig oder ergibt "
                                  "nicht die Summe")
        agenten = {"summe": {f: summe[f] for f in felder},
                   "je_rolle": {r: {f: w[f] for f in felder} for r, w in je_rolle.items()},
                   "sitzungen": len(daten.get("sitzungen") or [])}
    return {"vorhanden": bool(dauer or agenten), "dauer": dauer, "agenten": agenten,
            "gelesen_aus": [AUFWAND_DATEI] if agenten else []}


def sammle(fall: Path, abzuege: List[str],
           stands_paket: Optional[Path] = None,
           anker: Optional[Path] = None) -> Dict[str, Any]:
    manifest = _json(fall / "fall.json") or {}
    # Der Scope kommt aus demselben strengen Vertrag wie bei den Gates
    # (fall.lade_scope, T21-04) — nicht aus dem roh gelesenen Manifest.
    from rechner_pipeline.fall import FallFehler, lade_scope

    scope: Optional[str] = None
    scope_befund: Optional[str] = None
    try:
        scope = lade_scope(fall)
    except FallFehler as exc:
        scope_befund = f"Fall-Scope ungueltig: {exc}"
    # Die Kette zuerst: Die Rollen lesen, wer in ihr gezeichnet hat.
    kette_modell = kette(fall)
    modell: Dict[str, Any] = {
        "schema_version": 1,
        "fall": {
            "name": manifest.get("name") or fall.name,
            "beschreibung": manifest.get("beschreibung") or None,
            "scope": scope,
            "scope_befund": scope_befund,
        },
        "lieferung": lieferung(fall),
        "bestand": bestand(fall, abzuege),
        "transformation": transformation(fall),
        "parameter": parameter(fall),
        "abnahmen": abnahmen(fall),
        "kette": kette_modell,
        "verankerung": verankerung(fall),
        "umbau": umbau(fall),
        "betrieb": betrieb(stands_paket, anker, fall),
        "rollen": rollen(fall, kette_modell),
        "fallauftrag": fallauftrag(fall),
        "zugangsprobe": zugangsprobe(fall),
        "aufwand": aufwand(fall, kette_modell),
    }
    modell["systemaenderung"] = systemaenderung(fall, modell["umbau"])
    # Die Kette zuletzt: Sie nimmt mit, was die Darstellung liest.
    modell["belegkette"] = belegkette(fall, kette_modell, sorted(_gelesen_aus(modell)))
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
    p.add_argument("--anker", dest="anker", default=None,
                   help="Ankerdatei des Stands-Pakets (Pflicht mit "
                        "--stands-paket). Sie liegt AUSSERHALB des Pakets — "
                        "das ist der Punkt.")
    p.add_argument("--stands-paket", dest="stands_paket", default=None,
                   help="Stands-Paket der Laufzeitumgebung (betrieb.seite "
                        "--paket): der lebende Bestand als Abschnitt der "
                        "Darstellung")
    args = p.parse_args(argv)

    fall = Path(args.fall).resolve()
    if not (fall / "fall.json").is_file():
        print(f"Kein Fall-Arbeitsbereich: {fall}", file=sys.stderr)
        return 2
    try:
        modell = sammle(
            fall, args.abzug,
            Path(args.stands_paket) if args.stands_paket else None,
            Path(args.anker) if args.anker else None)
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
