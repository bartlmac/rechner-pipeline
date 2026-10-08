"""``unternehmensseite`` — die Seiten des fiktiven Unternehmens zusammenbauen.

Die Vorfuehrung tritt als Unternehmensauftritt der (frei erfundenen)
Pfefferminzia Lebensversicherung AG auf: eine Startseite, Bereiche
(Aktuariat, IT, ...) und darunter die generierten Migrationsberichte
(``vorzeigeseite.py``, je Fall unter ``migrationen/<fall>/``).

Die Unternehmensseiten sind HANDGESCHRIEBENE, versionierte Quellen
unter ``plv/seite/`` — im Gegensatz zu den Fall-Seiten, die je
Lauf aus den Artefakten entstehen. Dieses Werkzeug kopiert sie in den
Push-Baum und erzwingt dabei zwei Dinge:

*Die Banderole.* Je echter der Auftritt wirkt, desto wichtiger die
Kennzeichnung: JEDE Seite muss den Fiktions-Hinweis tragen. Eine Seite
ohne ihn wird nicht gebaut — eine oeffentliche Seite, die wie ein
echter Versicherer aussieht, waere keine Vorfuehrung mehr, sondern
eine Behauptung.

*Die Regie-Sperre.* Wie bei der Fall-Seite gelangt nichts aus den
Spielleiter-Bereichen in die Veroeffentlichung.

Aufruf (nach dem Bau der Fall-Seiten in denselben Baum)::

    python werkzeuge/unternehmensseite.py --quellen plv/seite \\
        --out runs/seite
"""

from __future__ import annotations

import argparse
import json
import html
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import darstellung
import grafik
import vorzeigeseite
from vorzeigeseite import VeroeffentlichungFehler, _pruefe_regie

#: Jede Unternehmensseite muss diesen Hinweis woertlich tragen — die
#: Banderole oben auf der Seite. Fehlt er, wird nicht gebaut.
BANDEROLE = "Fiktives Unternehmen"

#: Kennzahl-Platzhalter der Quellseiten: ``{{art:pfad}}``. Die Werte
#: kommen beim Bau aus dem falldaten-Modell des aktuellen Falls —
#: generiert statt gepflegt: Eine Zahl, die niemand abtippt, kann dem
#: Fall nicht davonlaufen. Ein unaufloesbarer Platzhalter bricht den
#: Bau ab; eine Seite, die "{{...}}" zeigt, waere schlimmer.
KENNZAHL = re.compile(r"\{\{(zahl|euro|datum|text|hash|svg|tabelle|html):([a-z0-9_.]+)\}\}")

#: Verzeichnis des Stands-Pakets im Push-Baum (``betrieb.seite --paket``):
#: die Tagesseite "Bestand heute" und die Berichte der Monatsabschluesse,
#: byteweise gegen die Summen in stand.json gehalten.
STAND_DIR = "plv"

GEVO_TITEL = {"ERH": "Erhöhung", "PEX": "Beitragsfreist.",
              "RED": "Absetzung", "STO": "Rückkauf",
              "TOD": "Todesfall", "ABL": "Ablauf",
              "ZUG": "Zugang", "MIG": "Migrationszugang",
              "INV": "Invalidisierung", "REA": "Reaktivierung"}
PRODUKT_TITEL = {"klv": "KLV", "bu": "BU"}
BETRAGSART_TITEL = {"VS": "Versicherungssumme", "VS_bfr": "beitragsfreie Summe", "BJB": "Bruttojahresbeitrag",
                    "VS_erhoehung": "Erhöhungssumme", "RKW": "Rückkaufswert",
                    "Ablaufleistung": "Ablaufleistung", "Todesfallleistung": "Todesfallleistung",
                    "BU_Jahresrente": "BU-Jahresrente"}
#: Der Reiter der Startseite fuehrt zu ihren eigenen Abschnitten, nicht in
#: die Tiefe: Wer oben klickt, will sehen, was diese Seite zu bieten hat,
#: und nicht sofort woanders landen. Jede andere Seite traegt nur den Weg
#: zurueck; ihre eigene Gliederung kommt, wenn sie steht.
REITER = (("ueber-uns", "Über uns"), ("unser-bestand", "Unser Bestand"),
          ("geschaeftsentwicklung", "Geschäftsentwicklung"),
          ("bestandsmigrationen", "Bestandsmigrationen"),
          ("know-how", "Unser Know-how"))
#: Die Kennzahlen der Geschaeftsentwicklung: (Zeile, Vorfallart, Herkunft
#: oder None, gewuenschte Betragsgroesse, Betragsarten des Journals, die
#: diese Groesse tragen — leer = das Journal traegt sie nicht).
GESCHAEFTSENTWICKLUNG = (
    ("Neuzugang", (
        ("Neugeschäft", "ZUG", "neugeschaeft", "Bruttojahresbeitrag", ("BJB",)),
        ("Erhöhungen", "ERH", None, "Bruttojahresbeitrag", ("BJB",)),
        # Der uebernommene Bestand traegt den Beitrag nicht: sein Ledger kommt
        # aus dem Fall und ist aelter als die Beitragsbuchung. Ein "0 EUR"
        # waere hier eine Behauptung — die Stelle bleibt bis zum naechsten
        # Fall-Lauf ein benannter Platzhalter.
        ("Migrationen", "ZUG", "uebernahme", "Bruttojahresbeitrag", ("BJB",)),
    )),
    # Als Leistung gilt, was ausgezahlt wurde. Die BU-Jahresrente ist eine
    # Zusage, keine Zahlung — sie erscheint hier nicht als Betrag; die
    # ausgezahlten Renten fuehrt das Journal noch nicht.
    ("Leistungen", (
        ("Ablauf", "ABL", None, "ausgezahlte Leistung", ("Ablaufleistung",)),
        ("Rückkauf", "STO", None, "ausgezahlte Leistung", ("RKW",)),
        ("Todesfall", "TOD", None, "ausgezahlte Leistung", ("Todesfallleistung",)),
        ("Invalidisierung", "INV", None, "ausgezahlte Leistung", ()),
        ("Reaktivierung", "REA", None, "ausgezahlte Leistung", ()),
    )),
)
ZEITRAUM_TITEL = {"letztes_jahr": "Letztes Jahr", "vorjahr_bis_heute": "Vorjahr, gleicher Zeitraum",
                  "aktuelles_jahr": "Aktuelles Jahr", "aktueller_monat": "Aktueller Monat"}
#: Die zwei Sichten der Startseite: das laufende Jahr gegen denselben
#: Abschnitt des Vorjahres — ein ganzes Vorjahr daneben saehe wie ein
#: Einbruch aus.
VERGLEICH = ("vorjahr_bis_heute", "aktuelles_jahr")
#: Zugangsquellen und Leistungsarten der Startseiten-Diagramme.
ZUGANGSQUELLEN = (("Neugeschäft", "ZUG", "neugeschaeft"), ("Erhöhungen", "ERH", None),
                  ("Migrationen", "ZUG", "uebernahme"))
LEISTUNGSARTEN = (("Ablauf", "ABL"), ("Rückkauf", "STO"), ("Todesfall", "TOD"),
                  ("Invalidisierung", "INV"), ("Reaktivierung", "REA"))


def reiter(wurzel: str, aktiv: str = "") -> str:
    """Der Reiter (Navigation) einer Seite.

    Auf der Startseite (``wurzel`` leer) sind es ihre Abschnitte als
    Sprungmarken; auf jeder anderen Seite genuegt der Weg zurueck.
    """
    if wurzel:
        return f'<nav class="kopf"><a href="{wurzel}">← Startseite</a></nav>'
    teile = [f'<a href="#{anker}">{titel}</a>' for anker, titel in REITER]
    return '<nav class="kopf">' + "".join(teile) + "</nav>"


def fusszeile(wurzel: str) -> str:
    """Die Kennzeichnung der Vorfuehrung: eine schmale Fusszeile auf jeder
    Seite, ausserhalb der Unternehmensstimme (Seitenkonzept, Regel 1)."""
    return (f'<div class="fuss-fiktion">{BANDEROLE} — '
            f'<a href="{wurzel}hinter-den-kulissen/">Hinter den Kulissen</a></div>')


def _mit_reiter(text: str, wurzel: str, aktiv: str) -> str:
    """Den Reiter UNTER die Ueberschrift setzen — wie ein Kopfbogen.

    Ueber der Ueberschrift stuende eine Navigationsleiste ohne Kontext:
    Man liest, wohin man springen kann, bevor man weiss, wo man ist.
    """
    if 'class="kopf"' in text:
        return text
    treffer = re.search(r"^# .+$", text, flags=re.M)
    if treffer:
        return (text[:treffer.end()] + "\n\n" + reiter(wurzel, aktiv)
                + text[treffer.end():])
    return reiter(wurzel, aktiv) + "\n" + text


def _mit_fusszeile(text: str, wurzel: str) -> str:
    """Die Fusszeile ans Ende jeder Seite — der Bau garantiert die
    Kennzeichnung, nicht der Autor der Seite."""
    if 'class="fuss-fiktion"' in text:
        return text
    return text.rstrip("\n") + "\n\n" + fusszeile(wurzel) + "\n"
STATUS_TITEL = {"POL": "beitragspflichtig", "PEX": "beitragsfrei",
                "BU": "BU-Leistung"}
FARBEN = ("#2f5d62", "#8c4a2f", "#5f6663")


def _zahl_de(wert: Any, dez: int = 0) -> str:
    text = f"{float(wert):,.{dez}f}"
    return text.replace(",", "@").replace(".", ",").replace("@", ".")


def _aufloesen(modell: Dict[str, Any], pfad: str) -> Any:
    if pfad.startswith("betrieb."):
        _betrieb(modell)  # fehlt das Paket: Abbruch mit Hinweis auf den Aufruf
    wert: Any = modell
    for teil in pfad.split("."):
        if isinstance(wert, list):
            wert = wert[int(teil)]
        elif isinstance(wert, dict) and teil in wert:
            wert = wert[teil]
        else:
            raise KeyError(pfad)
    if wert is None:
        raise KeyError(pfad)
    return wert


def _betrieb(modell: Dict[str, Any]) -> Dict[str, Any]:
    """Der lebende Bestand aus dem Stands-Paket — oder ein klarer Abbruch.

    Die Unternehmensseiten zeigen den gefuehrten Bestand nur aus dem
    Paket der Laufzeitumgebung (Fachkonzept Tagesbetrieb, 8.3). Fehlt es,
    bricht der Bau mit dem Hinweis auf den Aufruf ab, statt eine leere
    oder gepflegte Zahl zu zeigen.
    """
    b = modell.get("betrieb") or {}
    if not b.get("vorhanden"):
        raise KeyError("betrieb: kein Stands-Paket im Modell — auftritt.py "
                       "--stands-paket <verzeichnis> (betrieb.seite --paket)")
    return b


def _buchungs_eintraege(modell: Dict[str, Any]) -> List[Tuple[str, int]]:
    je = _betrieb(modell).get("buchungen", {}).get("je_ereignis") or {}
    return sorted(((GEVO_TITEL.get(art, art), int(anzahl))
                   for art, anzahl in je.items()),
                  key=lambda paar: (-paar[1], paar[0]))


def _gevo_eintraege(modell: Dict[str, Any]) -> List[Tuple[str, int]]:
    je_art = _aufloesen(modell, "bestand.vorfaelle_im_zeitraum.je_art")
    return sorted(
        ((GEVO_TITEL.get(art, art), eintrag["anzahl"])
         for art, eintrag in je_art.items()),
        key=lambda paar: (-paar[1], paar[0]))


def _generiert(art: str, name: str, modell: Dict[str, Any],
               ziel: Optional[Path] = None, wurzel: str = "") -> str:
    """``wurzel`` ist der Pfad von der bauenden Seite zur Auftritts-Wurzel
    (``""`` auf der Startseite, ``"../"`` eine Ebene tiefer) — generierte
    Verweise auf Dateien des Baums werden damit relativ gesetzt."""
    if art == "svg" and name == "gevo_je_art":
        return grafik.balken(_gevo_eintraege(modell))
    if art == "svg" and name == "gevo_je_art_mit_betrag":
        je_art = _aufloesen(modell, "bestand.vorfaelle_im_zeitraum.je_art")
        betraege = {GEVO_TITEL.get(art_, art_): e.get("betrag_summe")
                    for art_, e in je_art.items() if e.get("betrag_summe")}
        return grafik.balken(_gevo_eintraege(modell), betraege)
    if art == "svg" and name == "zugang_status":
        verteilung = _aufloesen(modell, "bestand.verteilungen.status_code")
        paare = [(STATUS_TITEL.get(code, code), verteilung[code])
                 for code in ("POL", "PEX", "BU") if code in verteilung]
        return grafik.gestapelt(paare)
    if art == "svg" and name == "buchungen_je_art":
        return grafik.balken(_buchungs_eintraege(modell))
    if art == "svg" and name == "bestand_vergleich":
        return _bestand_vergleich(modell)
    if art == "svg" and name == "bestand_vergleich_tief":
        return _bestand_vergleich(modell, BESTAND_KENNZAHLEN_TIEF)
    if art == "svg" and name == "zugang_vergleich":
        return _bewegung_vergleich(modell, ZUGANGSQUELLEN, "Verträge", "Zugang")
    if art == "svg" and name == "leistungen_vergleich":
        return _bewegung_vergleich(modell, [(t, e, None) for t, e in LEISTUNGSARTEN],
                                   "Vorfälle", "Leistungen")
    if art == "svg" and name == "bestand_je_produkt":
        je = _betrieb(modell).get("bestand", {}).get("je_produkt") or {}
        return grafik.gestapelt([(PRODUKT_TITEL.get(k, k), int(v))
                                 for k, v in sorted(je.items())])
    if art == "tabelle" and name == "buchungen_je_art":
        zeilen = ["| Art | Geschäftsvorfälle |", "|---|---:|"]
        zeilen += [f"| {titel} | {_zahl_de(wert)} |"
                   for titel, wert in _buchungs_eintraege(modell)]
        return "\n".join(zeilen)
    if art == "tabelle" and name == "bestand_kennzahlen":
        k = _betrieb(modell).get("abschluss_kennzahlen") or {}
        if not k.get("aktuell"):
            raise KeyError("betrieb.abschluss_kennzahlen: kein Monatsabschluss im Stands-Paket")
        zeilen = ["| Zum Monatsabschluss | Verträge | Bruttojahresbeitrag | Deckungskapital |",
                  "|---|---:|---:|---:|"]
        produkte = sorted({p for r in k.values() for p in (r.get("je_produkt") or {})})
        for produkt in produkte + ["gesamt"]:
            for rolle in ("aktuell", "vorjahr"):
                r = k.get(rolle)
                if not r:
                    continue
                e = r["gesamt"] if produkt == "gesamt" else (r.get("je_produkt") or {}).get(produkt)
                if not e:
                    continue
                titel = "Gesamt" if produkt == "gesamt" else PRODUKT_TITEL.get(produkt, produkt.upper())
                zeilen.append(f"| {titel}, {_datum_de(r['stichtag'])} | {_zahl_de(e['vertraege'])} "
                              f"| {_zahl_de(e['jahresbeitrag'], 2)} € | {_zahl_de(e['deckungskapital'], 2)} € |")
        bruch = _dk_bruch(k["aktuell"], k.get("vorjahr"))
        if bruch:
            zeilen.append(f"\n*{bruch}.*")
        return "\n".join(zeilen)
    if art == "tabelle" and name == "abschluesse":
        b = _betrieb(modell)
        alle = list(b.get("abschluesse") or [])
        # Dateiname und Pruefsumme des Abschlusses gehoeren in den Nachweis,
        # nicht auf die Unternehmensseite: Der Leser sucht den Bericht zum
        # Monat, nicht den Namen einer Datei. Dafuer die Zahlen des Monats,
        # sobald das Paket sie traegt — und keine Spalte "Vorfaelle gesamt":
        # eine Beitragsfreistellung ist weder Zugang noch Leistung, die
        # beiden Spalten summieren sich also nicht auf alle Vorfaelle.
        juengste = alle[-12:]  # eine Historie seit 1994 wuerde die Seite sprengen
        mit_zahlen = any(a.get(f) is not None
                         for a in juengste for f in ("in_kraft", "zugaenge", "leistungen"))
        if mit_zahlen:
            # "Vertraege in Kraft" ist eine Bestandsgroesse, Zugaenge und
            # Leistungen sind Geschaeftsvorfaelle des Monats. Die Spalten
            # heissen deshalb verschieden: Sonst rechnet der erste Leser
            # 2548 + 43 - 7 und wundert sich, dass 2550 nicht herauskommt.
            # Eine Erhoehung ist ein Zugang, ohne dass ein Vertrag hinzukommt.
            zeilen = ["| Stichtag | Verträge in Kraft | Zugänge | Leistungen | Bericht |",
                      "|---|---:|---:|---:|---|"]
        else:
            zeilen = ["| Stichtag | Bericht |", "|---|---|"]
        for a in juengste:
            teile = []
            # Der Bericht steht im Modell, sobald der Tagesbetrieb ihn
            # protokolliert. Solange er nur im Paket liegt (aus dem Stand
            # gerendert, noch nicht ueber das Protokoll gebunden), findet
            # ihn der Konventionsname — verlinkt wird ohnehin nur, was im
            # Push-Baum wirklich liegt.
            bericht = a.get("bericht") or f"bestandsbericht_{a.get('stichtag')}.html"
            if bericht and _stand_href(ziel, bericht):
                teile.append(f"[Monatsbericht zum {_datum_de(a.get('stichtag'))}]"
                             f"({wurzel}{_stand_href(ziel, bericht)})")
            # Zum Jahreswechsel steht der Jahresbericht daneben: zwei
            # Dokumente zu einem Stichtag — der Monatsbericht zwoelf Monate,
            # der Jahresbericht die Entwicklung seit Betriebsbeginn.
            jahr_vor = str(int(str(a.get("stichtag", "0"))[:4]) - 1) if str(a.get("stichtag", ""))[:4].isdigit() else ""
            jahresbericht = a.get("jahresbericht") or (
                f"jahresbericht_{jahr_vor}.html"
                if str(a.get("stichtag", "")).endswith("-01-01") else None)
            if jahresbericht and _stand_href(ziel, jahresbericht):
                jahr = str(a.get("stichtag", ""))[:4]
                jahr = str(int(jahr) - 1) if jahr.isdigit() else ""
                teile.append(f"[Jahresbericht {jahr}]"
                             f"({wurzel}{_stand_href(ziel, jahresbericht)})")
            # Ohne Bericht bleibt die Zelle leer: "in Arbeit" behauptete einen
            # Bericht, den der Tageslauf fuer aeltere Abschluesse nie rendert.
            link = " · ".join(teile)
            if mit_zahlen:
                # Ein fehlendes Feld ist eine Luecke, keine Null: Ein Altlauf,
                # der die Zahl nicht kennt, darf nicht "0 Zugaenge" behaupten.
                zahlen = "".join(f" {_zahl_de(a[f]) if a.get(f) is not None else ''} |"
                                 for f in ("in_kraft", "zugaenge", "leistungen"))
                zeilen.append(f"| {_datum_de(a.get('stichtag'))} |{zahlen} {link} |")
            else:
                zeilen.append(f"| {_datum_de(a.get('stichtag'))} | {link} |")
        if len(alle) > 12:
            zeilen.append(f"\n*{_zahl_de(len(alle))} Monatsabschlüsse seit {_datum_de(alle[0].get('stichtag'))}.*")
        return "\n".join(zeilen)
    if art == "tabelle" and name == "uebernahmen_im_stand":
        b = _betrieb(modell)
        # Kennung und Pruefsumme der Abnahme gehoeren in den Nachweis des
        # Falls, nicht auf die Unternehmensseite: Der Leser sieht, welcher
        # Bestand wann in die Buecher kam, nicht mit welchem Gate.
        zeilen = ["| Übernahme | Zugang zum | Verträge |", "|---|---|---:|"]
        eigener = str((modell.get("fall") or {}).get("name") or "")
        for u in b.get("uebernahmen") or []:
            name = _fallname(modell) if eigener and u.get("fall") == eigener else u.get("fall")
            zeilen.append(f"| {name} | {_datum_de(u.get('stichtag'))} "
                          f"| {_zahl_de(u.get('vertraege'))} |")
        return "\n".join(zeilen)
    if art == "html":
        return _html_baustein(name, modell, ziel, wurzel)
    if art == "tabelle" and name == "gevo_je_art":
        zeilen = ["| Art | Anzahl |", "|---|---:|"]
        zeilen += [f"| {titel} | {_zahl_de(wert)} |"
                   for titel, wert in _gevo_eintraege(modell)]
        return "\n".join(zeilen)
    raise KeyError(f"{art}:{name}")


#: Beide Erzeuger schreiben dieselben Stichtage; das Format wohnt in
#: ``darstellung``.
_datum_de = darstellung.datum


def _stand_href(ziel: Optional[Path], datei: Optional[str]) -> str:
    """Verweis auf einen Bericht — nur, wenn er im geprueften Paket liegt.

    Ausschliesslich unter ``plv/``: Das Paket traegt, was ``stand.json``
    mit Hash nennt, und ein Verweis von der Unternehmensseite soll nichts
    anderes erreichen. Eine Weile gab es hier einen zweiten Ort — Berichte,
    die aus dem gefuehrten Stand gerendert, aber noch nicht protokolliert
    waren. Der Umweg war noetig, solange der Tagesbetrieb den Stand wegen
    offener Befunde nicht uebernehmen konnte; seit er es wieder tut,
    schreibt er die Berichte selbst und der Export nimmt sie mit. Ein
    Ausweichpfad, den niemand mehr braucht, ist kein Sicherheitsnetz,
    sondern eine zweite Wahrheit.
    """
    if not datei or ziel is None:
        return ""
    # Paketschema 5: Die bezeugten Berichte liegen in der Wurzel des Pakets.
    if (ziel / STAND_DIR / datei).is_file():
        return f"{STAND_DIR}/{datei}"
    return ""


def stand(modell: Dict[str, Any], ziel: Path) -> List[str]:
    """Das Stands-Paket in den Push-Baum uebernehmen (``plv/``).

    Jede Datei wird gegen die SHA-256 in ``stand.json`` gehalten und
    byteweise uebernommen — was nicht stimmt, wird nicht veroeffentlicht,
    und nichts wird umgeschrieben. Das Paket spiegelt die Ablage des
    Tagesbetriebs (``index.html`` und die bezeugten Berichte des juengsten
    Abschlusses in der Wurzel, ``abschluesse/…``), seine Verweise loesen im
    Baum unter ``plv/`` unveraendert auf.

    NICHT veroeffentlicht werden Belege auf VERTRAGSEBENE (``.parquet``,
    heute das Tagesjournal mit Police, Betrag und Buchungstag je Buchung):
    Das Paket ist der Nachweis und geht an den Menschen, der es
    exportiert; der Auftritt ist die Veroeffentlichung. Ein Versicherer
    legt sein Ledger nicht vertragsweise offen — dass die Vorfuehrung es
    koennte, weil ihre Daten erfunden sind, macht es nicht zum Muster.
    Geprueft wird die Datei trotzdem: Ein Beleg, der nicht zu stand.json
    passt, bricht den Bau, auch wenn er im Baum nicht erscheint.
    Protokoll und Manifest bleiben oeffentlich — sie tragen Zaehlungen,
    Hashes und Urteile, keinen einzigen Vertrag, und sie sind es, an denen
    die Seite ihre eigene Kette zeigt.
    """
    b = modell.get("betrieb") or {}
    if not b.get("vorhanden"):
        return []
    quelle = Path(b.get("quelle") or "")
    dateien = b.get("dateien") or {}
    if not quelle.is_dir() or not dateien:
        raise VeroeffentlichungFehler(
            f"Stands-Paket {quelle} nicht lesbar oder ohne Dateiliste.")
    import hashlib
    aus = ziel / STAND_DIR
    # Das Verzeichnis ist das Paket, nichts sonst: Reste eines frueheren
    # Stands wuerden sonst neben dem aktuellen weiterveroeffentlicht.
    if aus.exists():
        shutil.rmtree(aus)
    aus.mkdir(parents=True)
    uebernommen: List[str] = []
    for name, summe in sorted(dateien.items()):
        daten = (quelle / name).read_bytes()
        ist = hashlib.sha256(daten).hexdigest()
        if ist != summe:
            raise VeroeffentlichungFehler(
                f"Stands-Paket: {name} weicht von stand.json ab "
                f"({ist[:16]} statt {summe[:16]}) — nicht veroeffentlicht.")
        zielpfad = aus / name
        if ".." in Path(name).parts or Path(name).is_absolute():
            raise VeroeffentlichungFehler(f"Stands-Paket: unzulaessiger Pfad {name!r}.")
        if Path(name).suffix == ".parquet":
            continue  # geprueft, aber nicht veroeffentlicht (Vertragsebene)
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        if zielpfad.exists():
            zielpfad.unlink()
        zielpfad.write_bytes(daten)
        uebernommen.append(f"{STAND_DIR}/{name}")
    # Die Betriebssicht verlinkt ihre Berichte so, wie die Ablage des
    # Tagesbetriebs sie fuehrt (``../berichte/<name>``), das Paket aber ist
    # flach. Damit ihre Verweise im Auftritt aufloesen, liegt jeder so
    # verlinkte Bericht des Pakets zusaetzlich dort — dieselben, eben
    # geprueften Bytes, nichts umgeschrieben (bis 04.10.2026 fuehrten die
    # Berichtslinks der Betriebssicht ins Leere; der Erzeuger ist gemeldet).
    index = aus / "index.html"
    if index.is_file():
        for rel in sorted(set(re.findall(r'href="\.\./([^"#?]+)"',
                                         index.read_text(encoding="utf-8", errors="replace")))):
            teile = Path(rel).parts
            if (".." in teile or teile[0] == STAND_DIR or teile[-1] not in dateien
                    or Path(rel).suffix == ".parquet"):
                continue
            kopie = ziel / rel
            kopie.parent.mkdir(parents=True, exist_ok=True)
            kopie.write_bytes((aus / teile[-1]).read_bytes())
            uebernommen.append(rel)
    return uebernommen


def _fallbasis(ziel: Optional[Path]) -> str:
    """Pfad des eingehaengten Migrationsberichts, relativ zur Wurzel."""
    if ziel is None:
        return ""
    faelle = sorted((ziel / "migrationen").glob("*/index.md")) if (
        ziel / "migrationen").is_dir() else []
    return f"migrationen/{faelle[0].parent.name}/" if faelle else ""


def _euro_kurz(wert: float) -> str:
    return _zahl_de(wert, 2) + " €"


def _jahr_titel(zr: Dict[str, Any]) -> str:
    """Kurzes Label eines Zeitraums: Jahr, bei Teiljahren mit Enddatum."""
    von, bis = str(zr.get("von") or ""), str(zr.get("bis") or "")
    if not von or not bis:
        return "—"
    if von.endswith("-01-01") and bis.endswith("-12-31"):
        return von[:4]
    return f"{von[:4]} bis {_datum_de(bis)[:6]}"


#: Kennzahlen des Bestandsvergleichs: (Feld, Ueberschrift, Stueckzahl?).
#: Die Startseite zeigt nur die Vertragszahl — Beitrag und Deckungskapital
#: stehen in der Vertiefung; drei Diagramme uebereinander sind dort richtig,
#: hier waeren sie eine Wand.
BESTAND_KENNZAHLEN = (("vertraege", "Verträge in Kraft", True),)
BESTAND_KENNZAHLEN_TIEF = (("vertraege", "Verträge in Kraft", True),
                           ("jahresbeitrag", "Bruttojahresbeitrag", False),
                           ("deckungskapital", "Deckungskapital", False))


def _delta(jetzt: float, frueher: Optional[float], stueck: bool) -> Tuple[str, str]:
    """Veraenderung gegen den Vorjahreswert: Text und Richtung."""
    if frueher in (None, 0):
        return "", ""
    unterschied = float(jetzt) - float(frueher)
    anteil_text = f" ({unterschied / float(frueher) * 100:+.0f} %)".replace("+-", "-")
    return (grafik.kurz(abs(unterschied), stueck) + anteil_text,
            "auf" if unterschied >= 0 else "ab")


#: Lesbare Namen der Konventionen des Deckungskapitals im Abschluss.
DK_KONVENTION_TITEL = {"jahreszeile": "Wert des letzten Jahrestags",
                       "monatsgenau": "monatsgenau"}


def _dk_bruch(jetzt: Dict[str, Any], frueher: Optional[Dict[str, Any]]) -> Optional[str]:
    """Der Satz, warum zwei Abschluesse im Deckungskapital nicht vergleichbar
    sind — oder None, wenn sie es sind.

    Zwei Abschluesse in verschiedener Konvention (Jahreszeile gegen
    monatsgenau) zeigen eine Differenz, die keine Bewegung des Bestands ist.
    Eine Veraenderung daraus waere eine falsche Zahl ohne sichtbaren Knick;
    sie wird deshalb nicht ausgewiesen, sondern benannt.
    """
    if not frueher:
        return None
    a, b = frueher.get("dk_konvention"), jetzt.get("dk_konvention")
    # Ein leerer Abschluss hat keine Konvention (None) und damit keine Naht.
    if a is None or b is None or a == b:
        return None
    return (f"Deckungskapital zum {_datum_de(frueher.get('stichtag'))} als "
            f"{DK_KONVENTION_TITEL.get(str(a), str(a))}, zum "
            f"{_datum_de(jetzt.get('stichtag'))} {DK_KONVENTION_TITEL.get(str(b), str(b))} "
            "gefuehrt — die Differenz ist keine Bewegung des Bestands und wird "
            "nicht als Veraenderung ausgewiesen")


def _bestand_vergleich(modell: Dict[str, Any], kennzahlen=None) -> str:
    """Der Bestand als Kennzahl-Kacheln, nicht als Tabelle.

    Ein aktueller Wert mit Vergleich zum Vorjahr ist eine Kachel: Zahl,
    Veraenderung, Stichtag. Die Aufteilung nach Produkt steht als schlanker
    Anteilsbalken darunter — ein Balkendiagramm mit einem Balken je Zahl
    saehe nach Diagramm aus, ohne mehr zu sagen.
    """
    k = _betrieb(modell).get("abschluss_kennzahlen") or {}
    if not k.get("aktuell"):
        raise KeyError("betrieb.abschluss_kennzahlen: kein Monatsabschluss im Stands-Paket")
    jetzt, frueher = k["aktuell"], k.get("vorjahr")
    # Eine Kachel steht neben dem Anteilsbalken; drei stehen ueber ihm.
    # Nebeneinander waeren drei gestapelte Kacheln so hoch, dass der
    # Balken in einer fast leeren Karte schwimmt.
    reihe = "bestand-kopf" if len(kennzahlen or BESTAND_KENNZAHLEN) == 1 else "bestand-kopf breit"
    z = [f'<div class="{reihe}"><div class="kennzahlen-reihe">']
    bruch = _dk_bruch(jetzt, frueher)
    for feld, titel, stueck in (kennzahlen or BESTAND_KENNZAHLEN):
        wert = (jetzt.get("gesamt") or {}).get(feld, 0)
        vor = (frueher.get("gesamt") or {}).get(feld) if frueher else None
        if feld == "deckungskapital" and bruch:
            text, richtung, unter = "", "", "Konvention gewechselt, kein Vergleich"
        else:
            text, richtung = _delta(wert, vor, stueck)
            unter = (text + f" ggü. {_datum_de(frueher['stichtag'])}") if text else None
        z.append(grafik.stat_tile(
            titel, grafik.kurz(wert, stueck) + ("" if stueck else " €"),
            unter, richtung, f"Stand {_datum_de(jetzt.get('stichtag'))}"))
    z.append("</div>")
    produkte = sorted((jetzt.get("je_produkt") or {}).items(),
                      key=lambda e: -int((e[1] or {}).get(
                          (kennzahlen or BESTAND_KENNZAHLEN)[0][0], 0)))
    feld = (kennzahlen or BESTAND_KENNZAHLEN)[0][0]
    if produkte:
        paare = [(PRODUKT_TITEL.get(p, p.upper()), int(w.get(feld, 0))) for p, w in produkte]
        voll = grafik.BREITE_SCHMAL if reihe.endswith("kopf") else grafik.BREITE
        z.append('<figure class="reihe"><figcaption>Zusammensetzung nach Produkt</figcaption>'
                 + grafik.responsiv(grafik.anteil(paare, "Verträge", breite=voll),
                                    grafik.anteil(paare, "Verträge",
                                                  breite=grafik.BREITE_HANDY))
                 + "</figure>")
    z.append("</div>")
    if bruch and any(f == "deckungskapital" for f, _, _ in (kennzahlen or BESTAND_KENNZAHLEN)):
        z.append(f'<p class="unterzeile">{html.escape(bruch)}.</p>')
    if not frueher:
        # Kein Vorjahreswert, weil sein Abschluss nicht im Paket liegt: Das
        # steht da, statt dass der Vergleich still fehlt (Entscheid des
        # Maintainers 03.10.2026: den Vergleich benannt weglassen).
        z.append(f'<p class="unterzeile">{html.escape(_ohne_vorjahr(modell, jetzt))}</p>')
    return "".join(z)


def _ohne_vorjahr(modell: Dict[str, Any], jetzt: Dict[str, Any]) -> str:
    """Warum die Kacheln keinen Vorjahreswert tragen — gemessen am Paket,
    gesagt in der Stimme des Hauses (veroeffentlichte Monatsabschluesse)."""
    import datetime as _dt
    j = _dt.date.fromisoformat(str(jetzt.get("stichtag")))
    try:
        vorjahr = j.replace(year=j.year - 1)
    except ValueError:
        vorjahr = j.replace(year=j.year - 1, day=28)
    n = sum(1 for d in (_betrieb(modell).get("dateien") or {}) if str(d).startswith("abschluesse/"))
    return (f"Ohne Vergleich mit dem Vorjahr: Veröffentlicht sind {n} Monatsabschlüsse, "
            f"der jüngste zum {_datum_de(j.isoformat())}; der Abschluss zum "
            f"{_datum_de(vorjahr.isoformat())} gehört nicht dazu.")


def _bewegung_vergleich(modell: Dict[str, Any], reihen, einheit: str,
                        titel: str = "") -> str:
    """Eine Diagrammreihe der Geschaeftsentwicklung: je Quelle bzw. Art ein
    Balkenpaar, laufendes Jahr gegen denselben Abschnitt des Vorjahres."""
    b = _betrieb(modell)
    ge = b.get("geschaeftsentwicklung") or {}
    zeitraeume, je = ge.get("zeitraeume") or {}, ge.get("je_zeitraum") or {}
    if not zeitraeume.get("vorjahr_bis_heute"):
        raise KeyError("betrieb.geschaeftsentwicklung: kein Vorjahres-Vergleichszeitraum "
                       "im Stands-Paket (betrieb.seite ab 2026-09-17 exportieren)")
    titel_zeitraum = [_jahr_titel(zeitraeume.get(k) or {}) for k in VERGLEICH]
    kategorien = []
    for name, ereignis, herkunft in reihen:
        werte = []
        for schluessel in VERGLEICH:
            e = (je.get(schluessel) or {}).get(ereignis) or {}
            werte.append((e.get("je_herkunft") or {}).get(herkunft, 0) if herkunft
                         else e.get("anzahl", 0))
        kategorien.append((name, werte))
    kurz_zahl = lambda w: grafik.kurz(w, stueck=True)
    # Beide Diagrammreihen der Startseite starten an derselben Kante: Die
    # Labelspalte misst sich ueber BEIDE Kategorienlisten, nicht je Bild.
    label = grafik.labelbreite([n for n, _, _ in ZUGANGSQUELLEN],
                               [n for n, _ in LEISTUNGSARTEN])
    bild = grafik.responsiv(
        grafik.gruppiert(kategorien, titel_zeitraum, einheit, kurz_zahl, label=label),
        grafik.gruppiert(kategorien, titel_zeitraum, einheit, kurz_zahl,
                         breite=grafik.BREITE_HANDY, label=label))
    if not titel:
        return bild
    return (f'<figure class="reihe"><figcaption>{titel} · {einheit}</figcaption>'
            f"{bild}</figure>")


def _geschaeftsentwicklung(modell: Dict[str, Any]) -> str:
    """Zugaenge und Leistungen je Zeitraum, je Bezugsgroesse eine Tabelle.

    Anzahl und Betrag stehen in GETRENNTEN Tabellen, nicht gross und klein
    in derselben Zelle: Zwei Zahlenwerke uebereinander liest niemand, und
    welche der beiden gemeint ist, muss man raten. Ein Betrag, den die
    Buchfuehrung nicht traegt, bleibt eine benannte Luecke.
    """
    b = _betrieb(modell)
    ge = b.get("geschaeftsentwicklung") or {}
    zeitraeume = ge.get("zeitraeume") or {}
    if not zeitraeume:
        raise KeyError("betrieb.geschaeftsentwicklung: das Stands-Paket traegt keine "
                       "Geschaeftsentwicklung (betrieb.seite ab 2026-09-07 exportieren)")
    je = ge.get("je_zeitraum") or {}
    sichten = [k for k in ("letztes_jahr", "aktuelles_jahr", "aktueller_monat")
               if zeitraeume.get(k)]

    def werte(zeile, schluessel: str):
        """(Anzahl, Betrag oder None) einer Zelle."""
        _titel, ereignis, herkunft, _groesse, arten = zeile
        e = (je.get(schluessel) or {}).get(ereignis) or {}
        if herkunft:
            anzahl = (e.get("je_herkunft") or {}).get(herkunft, 0)
            betraege = (e.get("betraege_je_herkunft") or {}).get(herkunft) or {}
        else:
            anzahl = e.get("anzahl", 0)
            betraege = e.get("betraege") or {}
        # Nur die Betragsarten DIESER Bezugsgroesse; eine fremde Groesse
        # ersatzweise zu zeigen, verwirrt mehr als eine Luecke.
        gebucht = [a for a in arten if a in betraege]
        return anzahl, (sum(float(betraege[a]) for a in gebucht) if gebucht else None)

    z = ['<div class="ge">']
    for blocktitel, zeilen in GESCHAEFTSENTWICKLUNG:
        groesse = zeilen[0][3]
        for spalte, titel in (("anzahl", f"{blocktitel} — Anzahl"),
                              ("betrag", f"{blocktitel} — {groesse}")):
            z.append(f'<table class="kpi gleich"><caption>{titel}</caption><thead><tr>')
            z.append(f"<th>{blocktitel}</th>")
            for k in sichten:
                zr = zeitraeume.get(k) or {}
                z.append(f'<th>{ZEITRAUM_TITEL[k]}'
                         f'<small>{_datum_de(zr.get("von"))} – {_datum_de(zr.get("bis"))}</small></th>')
            z.append("</tr></thead><tbody>")
            for zeile in zeilen:
                z.append(f"<tr><td>{zeile[0]}</td>")
                for k in sichten:
                    if (zeitraeume.get(k) or {}).get("ausserhalb_betrieb"):
                        z.append('<td><span class="platzhalter">vor Betriebsbeginn</span></td>')
                        continue
                    anzahl, betrag = werte(zeile, k)
                    if spalte == "anzahl":
                        z.append(f"<td><b>{_zahl_de(anzahl)}</b></td>")
                    elif betrag is not None:
                        z.append(f"<td><b>{grafik.kurz(betrag)} €</b></td>")
                    elif anzahl:
                        z.append('<td><span class="platzhalter">nicht gebucht</span></td>')
                    else:
                        z.append("<td>—</td>")
                z.append("</tr>")
            z.append("</tbody></table>")
    z.append('<p class="quelle">Zugänge zählen neu abgeschlossene Verträge und Erhöhungen '
             'mit ihrem Bruttojahresbeitrag; ein übernommener Bestand bringt seinen '
             'Beitrag aus dem Quellsystem noch nicht mit. Bei den Leistungen ist der '
             'Betrag die ausgezahlte Leistung — für Berufsunfähigkeitsrenten weist die '
             'Buchführung die laufenden Zahlungen noch nicht aus, deshalb steht dort '
             'nur die Zahl der Fälle.</p>')
    z.append("</div>")
    return "".join(z)


def _fallname(modell: Dict[str, Any]) -> str:
    """Anzeigename einer Uebernahme aus dem Modell: abgebende Gesellschaft
    (erster Namensteil des Falls), Produkt und Tarifgeneration der Lieferung."""
    name = str((modell.get("fall") or {}).get("name") or "")
    gesellschaft = name.split("-")[0].capitalize() if name else "?"
    verteilungen = (modell.get("bestand") or {}).get("verteilungen") or {}
    teile = [gesellschaft] + [p.upper() for p in sorted(verteilungen.get("produkt") or {})]
    teile += sorted(verteilungen.get("tarif_generation") or {})
    return " ".join(teile)


def _migrationen_bloecke(modell: Dict[str, Any], ziel: Optional[Path], wurzel: str) -> str:
    """Je fertiggestellter Uebernahme ein Block: Eckdaten, Struktur,
    Deckungskapital, Dauer und Aufwand (falldaten.aufwand) und die Kennzahlen der
    Abnahmen — aus dem Modell des Falls. Heute EIN Modell = ein Block;
    ein Portfolio mehrerer Faelle steht im Backlog."""
    basis = _fallbasis(ziel)
    bestand = modell.get("bestand") or {}
    abn = modell.get("abnahmen") or {}
    ctrl = abn.get("controlling") or {}
    dk = ((bestand.get("abzuege") or [{}])[0].get("deckkap") or {}).get("summe")
    z = ['<div class="migration">']
    z.append(f"<h3>{_fallname(modell)}<small>abgeschlossen</small></h3>")
    z.append('<table class="eckdaten"><tbody>')
    z.append(f"<tr><td>Zugangsdatum</td><td>{_datum_de(ctrl.get('stichtag_1'))}</td></tr>")
    z.append("<tr><td>Übernommene Verträge</td>"
             f"<td>{grafik.kurz(bestand.get('anzahl', 0), stueck=True)}</td></tr>")
    z.append("<tr><td>Deckungskapital</td>"
             f"<td>{grafik.kurz(dk) + ' €' if dk is not None else '—'}</td></tr>")
    # Dauer und Aufwand aus dem Modell (falldaten.aufwand): die Dauer an den
    # Entscheid-Snapshots gemessen, der Aufwand aus abgeleitet/aufwand.json.
    # Was fehlt, bleibt offen; die Einheit kommt mit der Zahl, nicht vorher —
    # "Stunden" neben einem Platzhalter waere eine Ankuendigung, keine Angabe.
    offen = '<td><span class="platzhalter">noch nicht erfasst</span></td></tr>'
    auf = modell.get("aufwand") or {}
    dauer = auf.get("dauer")
    if dauer:
        minuten = int(dauer["sekunden"]) // 60
        z.append(f"<tr><td>Dauer</td><td>{minuten // 60} h {minuten % 60} min, "
                 "vom ersten Fallauftrag bis zur Zugangsabnahme</td></tr>")
    else:
        z.append("<tr><td>Dauer</td>" + offen)
    summe = (auf.get("agenten") or {}).get("summe")
    if summe:
        gelesen = sum(int(summe.get(k) or 0) for k in ("eingabe", "cache_schreiben", "cache_lesen"))
        # Die Vertiefung je Rolle steht auf der Fallseite (Abschnitt aufwand),
        # der Beleg dort; hierher gehoert nur der Weg dorthin.
        # _fallbasis nennt nur eine Fallseite, die im Baum liegt.
        verweis = f' (<a href="{wurzel}{basis}#aufwand">je Rolle</a>)' if basis else ""
        z.append("<tr><td>Aufwand der Agenten</td>"
                 f"<td>{grafik.kurz(summe.get('ausgabe'), stueck=True)} Tokens erzeugt, "
                 f"{grafik.kurz(gelesen, stueck=True)} gelesen, im ganzen Fall{verweis}</td></tr>")
    else:
        z.append("<tr><td>Aufwand der Agenten</td>" + offen)
    # Kosten: keine Zeile, solange kein Preissatz beschlossen ist (Maintainer
    # 05.10.2026: eine Zeile, die nie gefuellt ist, wird weggelassen).
    z.append("</tbody></table>")
    verweise = []
    if basis:
        verweise.append(f'<a href="{wurzel}{basis}">Die Übernahme Station für Station</a>')
    if ziel is not None and (ziel / "migrationen" / "ki.md").is_file():
        verweise.append(f'<a href="{wurzel}migrationen/ki.html">Künstliche Intelligenz in Migrationen</a>')
    # Die Berichte des Aktuariats nur zu dem Fall, den sie wuerdigen.
    for _, datei, titel in darstellung.falldokumente(modell):
        verweise.append(f'<a href="{wurzel}{datei[:-3]}.html">{titel}</a>')
    if verweise:
        z.append("<p>" + " · ".join(verweise) + "</p>")
    z.append("</div>")
    return "".join(z)


#: Die Unternehmensfassung jeder Agentenrolle: Titel und was sie vorlegt.
#: Die Definitionen unter .claude/agents/ beschreiben sich auf Englisch; der
#: Satz hier ist die Fassung der Seite. Eine Rolle ohne Satz bricht den Bau
#: ab (bis 04.10.2026 stand der Betrieb mit der englischen Rohbeschreibung
#: auf der KI-Seite).
ROLLEN_TITEL = {
    "programmleitung": ("Programmleitung", "führt einen Migrationsfall von Anfang bis Ende, steuert die anderen Rollen durch die Stufen und hält an jedem menschlichen Gate an: Sie übergibt Entscheidungsvorlagen."),
    "aktuariat": ("Aktuariat", "bereitet alles vor, was das Aktuariat des aufnehmenden Unternehmens zeichnen muss: Feldabbildung, die drei aktuariellen Abnahmen, die Vorlage des Migrationscontrollings, die Fortführung des Bestands nach der Übernahme."),
    "architektur": ("Architektur", "hält die Migration in der vorgeschriebenen Architektur: Schichten, Determinismus, Gate- und Ledger-Verträge, Beweiskette aus Prüfsummen, Snapshots und Manifesten, Sicherheitsgrenzen. Bereitet Architekturentscheide vor."),
    "rechenkern": ("Rechenkern", "die Entwicklungsrolle im Zielsystem: setzt beschlossene Änderungen am Rechenkern und Tarifparametrierungen um und hält Referenzwerte, Regressionstests und Dokumentation intakt."),
    "betrieb": ("Betrieb", "bereitet vor, was die Betriebsverantwortung für den Bestand zeichnen muss, den sie jeden Tag führt: die Zugangsprobe und die Vorlage der Zugangsabnahme A-B2, das Stands-Paket für die Auslieferung A-B1 und den Nachweis des Anfangsbestands eines neu eingerichteten Bestands für A-B3."),
}

#: Gegen welche Fassung ihrer Definition jeder Satz oben geschrieben ist
#: (``falldaten.fingerabdruck`` der Beschreibung). Aendert sich eine
#: Definition, wird test_werkzeuge rot: erst den Satz pruefen, dann den
#: Fingerabdruck nachziehen — die Verankerung, die der KI-Seite fehlte.
ROLLEN_STAND = {
    "aktuariat": "4a8fa61d0d00",
    "architektur": "1507b2b42128",
    "betrieb": "f6c34cada7d1",
    "programmleitung": "a7ad05fa9688",
    "rechenkern": "8f3a1b539872",
}

#: Die menschlichen Rollen (ADR-018 §1 und Nachtrag 2026-09-16). Die
#: Kennung traegt das Fachgebiet und ist DIESELBE wie die der
#: Agentenrolle, die ihr zuarbeitet — die Paarung steckt im Namen; der
#: Titel ist der gesetzliche bzw. betriebliche Name.
MENSCH_TITEL = {
    "mensch/aktuariat": "Verantwortlicher Aktuar",
    "mensch/architektur": "IT-Verantwortung",
    "mensch/rechenkern": "Rechenkern-Verantwortung",
    "mensch/betrieb": "Betriebsverantwortung",
    "mensch/programmleitung": "Programmleitung",
    "mensch/vorstand": "Vorstand",
    "mensch/quell-aktuar": "Aktuar des abgebenden Hauses",
}

#: Welche menschliche Rolle ein zeichenbares Gate zeichnet, mit Quelle.
#:
#: Das Gate-Register kennt je Gate die Art (P oder A), aber nicht die
#: Rolle; die Zuordnung steht in den ADRs und im Entscheid-Kommando, nicht
#: als Daten. Solange das so ist, pflegt die Seite sie hier — und
#: test_werkzeuge haelt die Liste gegen GUELTIGE_GATES, damit ein neues
#: Gate hier auffaellt statt still zu fehlen.
GATE_ZEICHNER = {
    "A-Q1": ("mensch/aktuariat", "ADR-010; im Fall Baldrian so entschieden"),
    "A-M1": ("mensch/aktuariat", "ADR-010"),
    "A-M2": ("mensch/aktuariat", "ADR-010"),
    "A-M3": ("mensch/aktuariat", "ADR-010"),
    "A-M4": ("mensch/aktuariat", "ADR-010"),
    "A-O1": ("mensch/architektur", "ADR-012"),
    "A-K2": ("mensch/rechenkern", "ADR-018, Nachtrag 2026-09-16"),
    "A-T1": ("mensch/aktuariat", "ADR-025"),
    "A-M6": ("mensch/vorstand", "ADR-026"),
    "A-M5": ("mensch/programmleitung", "ADR-026"),
    "A-B1": ("mensch/betrieb", "ADR-018, Nachtrag 2026-09-16"),
    "A-B2": ("mensch/betrieb", "ADR-022"),
    "A-B3": ("mensch/betrieb", "ADR-025"),
}

#: Was eine Faehigkeit tut, in einem Satz. Die Definitionen unter
#: .claude/skills/ beschreiben sich auf Englisch; der Satz hier ist die
#: Unternehmensfassung. Welche Rolle eine Faehigkeit hat, steht NICHT
#: hier — das misst falldaten an den Agentendefinitionen.
SKILL_TITEL = {
    "extrahiere-quellfragment": "liest eine gelieferte Quelle (Tarifbeschreibung, Tarifrechner) in ein Quellfragment; was nicht belegt ist, bleibt offen statt geraten",
    "transformiere-quellbestand": "schlägt die Abbildung des gelieferten Bestandsabzugs auf unser Datenmodell vor; jede Unklarheit wird ein offener Konflikt",
    "bereite-fachkonflikt-auf": "bereitet einen Widerspruch zwischen Unterlagen zur menschlichen Entscheidung auf: beide Lesarten, Auswirkung, Empfehlung",
    "aktuartest-durchfuehren": "fährt die drei aktuariellen Abnahmen A-M1 bis A-M3 und bereitet je Abnahme die Entscheidungsvorlage auf",
    "pruefe-migrationscontrolling": "fährt das Controlling über zwei Stichtage und bereitet die Vorlage für A-M4 auf",
    "migrationsfall-durchfuehren": "führt einen Fall durch die drei Stufen und hält an jedem menschlichen Gate an",
    "entwickle-im-zielsystem": "der Rahmen jeder Änderung am Zielsystem: Schichten, Determinismus, Test-Pflicht",
    "integriere-migrationsinkrement": "bringt Änderungen während eines laufenden Falls in kleinen, geprüften Schritten ein",
    "author-rechner-toolbox-gate": "entwirft den Vertrag eines neuen Prüfkommandos: eine Ausgabe, feste Rückgabewerte, ein Ledger-Eintrag",
    "teste-adversarial": "prüft einen fertigen Block gegen den Strich: Befunde finden, widerlegen, als Regressionstest festhalten",
    "dokumentiere-system": "hält die Dokumentation nach den Regeln des Systems nach: erzeugt schlägt handgeschrieben",
}

#: Gegen welche Fassung ihrer Definition jeder Satz oben geschrieben ist —
#: dieselbe Verankerung wie ROLLEN_STAND (abgeglichen am 04.10.2026).
SKILL_STAND = {
    "aktuartest-durchfuehren": "348cf6b0023a",
    "author-rechner-toolbox-gate": "78f88225c1a9",
    "bereite-fachkonflikt-auf": "07237e41f06c",
    "dokumentiere-system": "f275b3c8b9cf",
    "entwickle-im-zielsystem": "0c2ef08b8163",
    "extrahiere-quellfragment": "780c9692bfaf",
    "integriere-migrationsinkrement": "5cea17af20d4",
    "migrationsfall-durchfuehren": "49bb33882750",
    "pruefe-migrationscontrolling": "abbcb6a8cd3d",
    "teste-adversarial": "5e0adfad86a8",
    "transformiere-quellbestand": "833adb308688",
}

#: Was ein Werkzeug einer Agentenrolle tut, in der Sprache des Hauses —
#: die Definitionen nennen es mit seinem technischen Namen.
WERKZEUG_TEXT = {"Read": "lesen", "Grep": "suchen", "Glob": "suchen",
                 "Bash": "Kommandos ausführen", "Write": "schreiben", "Edit": "ändern"}

#: Wofuer eine Laufzeitbibliothek eingesetzt wird — in welchen Modulen,
#: misst falldaten an den Importen.
BIBLIOTHEK_ZWECK = {
    "openpyxl": "liest die gelieferten Excel-Tarifrechner (Zellen, Formeln, Namen)",
    "oletools": "liest die VBA-Makros der Tarifrechner, ohne Excel",
    "pypdf": "liest die gelieferten Tarifbeschreibungen und Mitteilungen (PDF)",
    "pandas": "hält Bestände, Journale und Abschlüsse als Tabellen",
    "pyarrow": "schreibt und liest die festgeschriebenen Abschlüsse (Parquet)",
    "matplotlib": "zeichnet die Grafiken der Bestandsberichte",
    "pydantic": "prüft die Form jeder Aussage der Faktenbasis",
}


def _rollen(modell: Dict[str, Any]) -> str:
    """Wer legt vor, wer zeichnet.

    Drei Dinge, jedes aus seiner Quelle: die Agentenrollen aus ihren
    versionierten Definitionen, je Rolle mit der menschlichen Gegenrolle
    (ADR-018: derselbe Name, andere Ebene); je zeichenbarem Gate die
    zeichnende Rolle — fuer die Gates dieses Falls GEMESSEN aus den
    Snapshots (Entscheid, Datum, Rolle), fuer die uebrigen laut ADR; und
    die Messung, dass kein Entscheid der finalen Kette eine Agentenrolle
    oder einen Agentenschluessel traegt.

    Die Seite spricht mit der Stimme des Unternehmens (Entscheid des
    Maintainers 04.10.2026): Schluesselklasse und Mandat eines Entscheids
    stehen im Snapshot, nicht auf der Seite.

    Bis 2026-09-22 zeigte die Seite hier eine Zeichnungsordnung nach
    Schema 1 (plv-aktuar, plv-it, "mensch" mit allen Gates, Gate A-K1) —
    Rollen und ein Gate, die es seit ADR-018/ADR-012 nicht mehr gibt.
    """
    r = modell.get("rollen") or {}
    if not r.get("vorhanden"):
        raise KeyError("rollen: Agentenrollen fehlen im Modell")
    ohne_satz = [a["name"] for a in r.get("agenten") or [] if a["name"] not in ROLLEN_TITEL]
    if ohne_satz:
        raise VeroeffentlichungFehler(
            f"Agentenrolle ohne Seitentext: {', '.join(ohne_satz)} — ROLLEN_TITEL und "
            "ROLLEN_STAND ergänzen")
    try:
        from rechner_pipeline.models.zeichnung import GUELTIGE_GATES
    except ImportError as exc:  # pragma: no cover
        raise VeroeffentlichungFehler(f"Rollenmodell nicht ladbar: {exc}") from exc
    z = ['<div class="rollen">']
    z.append('<table class="agenten"><thead><tr><th>Agentenrolle</th><th>legt vor</th>'
             '<th>Menschliche Rolle, die zeichnet</th></tr></thead><tbody>')
    for a in r.get("agenten") or []:
        titel, aufgabe = ROLLEN_TITEL[a["name"]]
        gegen = f"mensch/{a['name']}"
        z.append(f"<tr><td><b>{titel}</b><small>{a.get('kennung')}</small></td><td>{aufgabe}</td>"
                 f"<td><b>{MENSCH_TITEL.get(gegen, gegen)}</b><small>{gegen}</small></td></tr>")
    z.append("</tbody></table>")
    agenten_namen = {a["name"] for a in r.get("agenten") or []}
    ohne = [(k, t) for k, t in MENSCH_TITEL.items() if k.split("/", 1)[1] not in agenten_namen]
    z.append('<p class="quelle">Die Paarung steckt im Namen: Die Agentenrolle und die menschliche '
             "Rolle tragen dieselbe Kennung, nur die Ebene davor ist eine andere — "
             "<code>agent/rechenkern</code> legt vor, <code>mensch/rechenkern</code> zeichnet. "
             + ("Ohne Agenten-Gegenstück im Werkzeug: "
                + ", ".join(f"{t} (<code>{k}</code>)" for k, t in ohne) + ".") + "</p>")
    # Faehigkeiten je Rolle — gemessen an den Definitionen, nicht an
    # einer Liste: Eine Rolle hat die Skills, die ihr Text ihr gibt.
    faeh = r.get("faehigkeiten") or []
    if faeh:
        rollen_je_skill: Dict[str, List[str]] = {}
        for a in r.get("agenten") or []:
            for sk in a.get("skills") or []:
                rollen_je_skill.setdefault(sk, []).append(
                    ROLLEN_TITEL.get(a["name"], (a["name"], ""))[0])
        z.append(f'<h3 id="faehigkeiten">Fähigkeiten</h3><p>{_zahl_de(len(faeh))} versionierte '
                 "Fähigkeiten; welche Rolle welche hat, sagt ihre Definition.</p>")
        z.append('<table class="faehigkeiten"><thead><tr><th>Fähigkeit</th><th>Rolle</th>'
                 '<th>was sie tut</th></tr></thead><tbody>')
        for sk in faeh:
            rollen_text = ", ".join(rollen_je_skill.get(sk) or ["—"])
            z.append(f"<tr><td><code>{sk}</code></td><td>{rollen_text}</td>"
                     f"<td>{SKILL_TITEL.get(sk, '')}</td></tr>")
        z.append("</tbody></table>")
        ohne = r.get("skills_ohne_rolle") or []
        unbekannt = r.get("skills_unbekannt") or []
        if ohne or unbekannt:
            z.append('<p class="befund"><b>Befund:</b> '
                     + (f"Fähigkeiten ohne Rolle: {', '.join(ohne)}. " if ohne else "")
                     + (f"Rollen nennen unbekannte Fähigkeiten: {', '.join(unbekannt)}." if unbekannt else "")
                     + "</p>")
    # Werkzeuge: was ein Agent bedienen darf (seine Definition) und womit
    # das System Lieferungen liest (die Laufzeit, gemessen an den Importen).
    z.append('<h3 id="werkzeuge">Werkzeuge</h3>')
    bedien = []
    for a in r.get("agenten") or []:
        w = a.get("werkzeuge") or []
        titel = ROLLEN_TITEL.get(a["name"], (a["name"], ""))[0]
        bedien.append(f"{titel}: " + ("alle Werkzeuge" if w == ["*"] else ", ".join(
            dict.fromkeys(WERKZEUG_TEXT.get(x, x) for x in w))))
    z.append("<p>Was eine Agentenrolle bedienen darf, legt ihre Definition "
             "fest — " + "; ".join(bedien) + ". Womit das System die gelieferten Unterlagen "
             "liest, ist keine Frage der Rolle, sondern der Laufzeit: Dieselben Bibliotheken, "
             "gepinnt im <a href=\"../it/techstack.html\">Techstack</a>, stehen jeder Rolle "
             "zur Verfügung.</p>")
    bibs = r.get("bibliotheken") or []
    if bibs:
        z.append('<table class="werkzeuge"><thead><tr><th>Bibliothek</th><th>eingesetzt für</th>'
                 '<th>verwendet in</th></tr></thead><tbody>')
        for b in bibs:
            n = len(b.get("module") or [])
            wo = (f"{_zahl_de(n)} Modul{'en' if n != 1 else ''}" + (
                  " (" + ", ".join(f"<code>{m}</code>" for m in b["module"][:2])
                  + (", …" if n > 2 else "") + ")" if n else ""))
            z.append(f"<tr><td><code>{b['name']}</code><small>{b.get('version', '')}</small></td>"
                     f"<td>{BIBLIOTHEK_ZWECK.get(b['name'], '')}</td><td>{wo}</td></tr>")
        z.append("</tbody></table>")
    z.append('<h3 id="gates-und-rollen">Wer welches Gate zeichnet</h3>')
    # Je Gate die zeichnende Rolle: gemessen, wo der Fall es hergibt.
    im_fall = {}
    for e in r.get("zeichnungen") or []:
        im_fall.setdefault(str(e.get("gate")), e)
    z.append('<table class="zeichnung"><thead><tr><th>Gate</th><th>zeichnet</th>'
             '<th>in dieser Übernahme</th></tr></thead><tbody>')
    for gate in GUELTIGE_GATES:
        rolle, quelle = GATE_ZEICHNER.get(gate, ("—", "nicht zugeordnet"))
        e = im_fall.get(gate)
        if e:
            wer = (f"<b>{e.get('entscheid')}</b> am {_datum_de(e.get('entschieden_am'))} "
                   f"durch <code>{e.get('rolle')}</code>")
        else:
            wer = '<span class="platzhalter">kein Gegenstand dieser Übernahme</span>'
        z.append(f"<tr><td><code>{gate}</code></td><td><b>{MENSCH_TITEL.get(rolle, rolle)}</b>"
                 f"<small>{rolle}</small></td><td>{wer}</td></tr>")
    z.append("</tbody></table>")
    finale = r.get("zeichnungen") or []
    befund = r.get("agenten_gezeichnet") or []
    if befund:
        z.append(f'<p class="befund"><b>Befund:</b> Entscheid(e) durch eine Agentenrolle oder einen '
                 f'Agentenschlüssel: {", ".join(befund)}.</p>')
    elif finale:
        z.append(f'<p class="pointe"><b>{_zahl_de(len(finale))} geltende Entscheide in diesem Fall, jeder '
                 "von einer menschlichen Rolle, keiner mit der Schlüsselklasse agent</b> — gemessen an "
                 "den Snapshots, nicht behauptet.</p>")
    else:
        z.append('<p class="quelle">Noch kein geltender Entscheid in diesem Fall.</p>')
    z.append("</div>")
    return "".join(z)


def _html_baustein(name: str, modell: Dict[str, Any],
                   ziel: Optional[Path], wurzel: str = "") -> str:
    """Generierte HTML-Bausteine der Unternehmensseiten.

    Verweise auf Artefakte gelten nur, wenn die Datei im gebauten Baum
    liegt — die Fall-Seite hat sie vorher ueber die Positivliste
    kopiert; was dort fehlt, wird nicht verlinkt.
    """
    basis = _fallbasis(ziel)
    if name == "geschaeftsentwicklung":
        return _geschaeftsentwicklung(modell)
    if name == "prozess_stationen":
        # Die Belege je Kasten kommen aus der Belegkette des Modells; verlinkt
        # wird nur, was die Fallseite wirklich kopiert hat. Die Lieferung
        # liegt als Ansicht unter lieferung/ (.csv als .csv.html, .md als
        # .md.txt), Markdown der Kette als .md.txt.
        def artefakt(ref: str) -> Optional[str]:
            if not ref or ziel is None or not basis:
                return None
            ordner = ziel / basis / "artefakte"
            rel = ("lieferung/" + ref[len("eingang/"):]) if ref.startswith("eingang/") else ref
            for kandidat in (rel, f"{rel}.txt", f"{rel}.html"):
                if (ordner / kandidat).is_file():
                    return f"{wurzel}{basis}artefakte/{kandidat}"
            return None
        return darstellung.prozess_stationen(
            f"{wurzel}{basis}" if basis else "baldrian/", modell, artefakt)
    if name == "migrationen_bloecke":
        return _migrationen_bloecke(modell, ziel, wurzel)
    if name == "rollen":
        return _rollen(modell)

    def link(ref: Optional[str]) -> Optional[str]:
        if not ref or ziel is None or not basis:
            return None
        return (f"{basis}artefakte/{ref}"
                if (ziel / basis / "artefakte" / ref).is_file() else None)

    if name == "kennzahlenband":
        # Auf der Unternehmensseite ist das Band ausdruecklich das der
        # laufenden Uebernahme — nicht die Kennzahl des Hauses.
        fallname = (modell.get("fall") or {}).get("name") or "Fall"
        return grafik.kennzahlenband(darstellung.kennzahl_gruppen(modell),
                                     titel=f"Übernahme {fallname}")
    if name == "toleranz":
        zeilen = darstellung.toleranz_zeilen(modell)
        if not zeilen:
            raise KeyError("toleranz: keine Verteilungen im Modell")
        return ('<div class="leitgrafik">' + grafik.toleranz(zeilen)
                + "</div>"
                + (f'<p class="unterzeile">{darstellung.toleranz_unterzeile(modell)}</p>'
                   if darstellung.toleranz_unterzeile(modell) else ""))
    if name == "abgrenzungsband":
        karten, luecken = darstellung.abgrenzung_karten(modell)
        return grafik.abgrenzungsband(karten, luecken)
    if name == "stationen":
        return grafik.stationen(darstellung.stationen(modell, basis))
    if name == "berichte":
        fall = (modell.get("fall") or {}).get("name") or "Fall"
        dokumente = {titel: datei for _, datei, titel in darstellung.falldokumente(modell)}
        extra = [
            {"titel": "Abschlussbericht", "zweck": "die fachliche Würdigung des Falls",
             "kennzahl": fall, "href": "migrationen/abschlussbericht-baldrian.html",
             "format": "Text"},
            {"titel": "Prüfbericht des Laufs", "zweck": "das Erzeugnis der Prüfstrecke, mit allen Belegen",
             "kennzahl": f"{darstellung._zahl(len((modell.get('kette') or {}).get('gates') or []))} Gate-Läufe",
             "href": basis or "migrationen/", "format": "Bericht"},
            {"titel": "Übersetzungsbericht", "zweck": "die Feldabbildung mit Begründungen",
             "kennzahl": f"{darstellung._zahl((modell.get('transformation') or {}).get('anzahl_zielfelder', 0))} Zielfelder",
             "href": f"{basis}uebersetzung.html", "format": "HTML"},
            {"titel": "Was sich verändert hat", "zweck": "Tarifwerk, Rechenkern, Prüfstrecken, Einzelentscheide",
             "kennzahl": "vier Dimensionen", "href": "migrationen/veraenderungen-baldrian.html",
             "format": "Text"},
        ]
        # Der Abschlussbericht entsteht spaeter im selben Bau (Abbruch,
        # wenn er fehlt; die Landkarte steht seit 04.10.2026 hinter den
        # Kulissen, nicht in dieser Liste); nur der Uebersetzungsbericht ist
        # optional und wird auf Existenz geprueft.
        extra = [e for e in extra
                 if (not e["href"].endswith("uebersetzung.html")
                     or ziel is None or (ziel / e["href"]).is_file())
                 and (e["titel"] not in ("Abschlussbericht", "Was sich verändert hat")
                      or e["titel"] in dokumente)]
        return grafik.kacheln(darstellung.berichte(modell, link, extra))
    if name == "widerspruch":
        zeilen = darstellung.diskrepanz_zeilen(modell)
        zins = [d for d in zeilen if d.get("feld") == "zins"] or zeilen
        if not zins:
            raise KeyError("widerspruch: keine Diskrepanzen im Modell")
        d = zins[0]
        lesarten = [(vorzeigeseite._lesart_text(d["feld"], w), q)
                    for w, q in d["lesarten"] if q]
        feld = vorzeigeseite.FELD_TITEL.get(d["feld"], d["feld"])
        teile = " — ".join(f"{q}: <b>{w}</b>" for w, q in lesarten)
        gew = vorzeigeseite._lesart_text(d["feld"], d.get("gewaehlt"))
        echte = [g for g in darstellung.diskrepanz_gruppen(modell) if g["wertkonflikt"]]
        zellen = sorted({zelle for g in echte for zelle in g["zellen"]})
        return (f'<div class="widerspruch"><p>Beim {feld} widersprachen sich '
                f"die Unterlagen: {teile}. Gewählt wurde {gew}, entschieden "
                f"von einem Menschen — ein Agent darf das "
                f"nicht entscheiden.</p><p>{len(echte)} Feststellungen"
                + (f" über {len(zellen)} Tarifzellen" if zellen else "")
                + ", jede mit Quelldokument und Entscheid: "
                f'<a href="{basis}#der-widerspruch">an Station 5 der Übernahme</a>.</p></div>')
    raise KeyError(f"html:{name}")


def _kennzahlen(text: str, modell: Dict[str, Any], seite: str,
                ziel: Optional[Path] = None) -> str:
    wurzel = "../" * (len(Path(seite).parts) - 1)

    def ersetze(treffer: re.Match) -> str:
        art, pfad = treffer.group(1), treffer.group(2)
        try:
            if art in ("svg", "tabelle", "html"):
                return _generiert(art, pfad, modell, ziel, wurzel)
            wert = _aufloesen(modell, pfad)
            if art == "zahl":
                return _zahl_de(wert)
            if art == "euro":
                return _zahl_de(wert, 2)
            if art == "hash":
                return str(wert)[:16]
            if art == "datum":
                jahr, monat, tag = str(wert).split("-")
                return f"{tag}.{monat}.{jahr}"
            return str(wert)
        except (KeyError, ValueError, TypeError, IndexError) as exc:
            raise VeroeffentlichungFehler(
                f"{seite}: Kennzahl {{{{{art}:{pfad}}}}} ist aus dem "
                f"Modell nicht aufloesbar ({exc}). Eine Seite mit "
                "Platzhalter wird nicht gebaut.") from exc

    ergebnis = KENNZAHL.sub(ersetze, text)
    rest = re.search(r"\{\{[^}]*\}\}", ergebnis)
    if rest:
        raise VeroeffentlichungFehler(
            f"{seite}: unbekannter Platzhalter {rest.group(0)!r}.")
    return ergebnis

#: Fachdokumente, die der Auftritt beim Bau importiert: (Quelle unter
#: docs/, Ziel im Auftritt, Rueckverweis-Beschriftung, Rueckverweis-
#: Ziel). Eine Quelle, eine Heimat (``docs/``) — der Auftritt kopiert
#: beim Bau, statt eine zweite Fassung zu pflegen. Die Aktuariats-
#: Dokumente spiegeln den Pfad unter docs/, damit ihre relativen
#: Querverweise untereinander unveraendert gueltig bleiben.
FACHDOKUMENTE = (
    ("tarifplaene/klv.md",
     "aktuariat/tarifplaene/klv.md", "Rechenkern und Tarifwerk", "../"),
    ("tarifplaene/bu.md",
     "aktuariat/tarifplaene/bu.md", "Rechenkern und Tarifwerk", "../"),
    ("mathematik/grundsatzdokumentation.md",
     "aktuariat/mathematik/grundsatzdokumentation.md", "Rechenkern und Tarifwerk", "../"),
    # Die Berichte zu einem Fall (migrationen/baldrian/berichte/) kommen je Fall dazu:
    # darstellung.FALLDOKUMENTE.
    # Hinter den Kulissen (ausserhalb der Fiktion): Entstehung der
    # Bestaende, Fachkonzept Tagesbetrieb, Erfahrungsannahmen. Ihre
    # Verweise auf mathematik/ und tarifplaene/ werden auf den Ort der
    # Aktuariats-Dokumente umgeschrieben (fuenftes Tupel-Element).
    ("simulation/README.md",
     "hinter-den-kulissen/simulation/index.md", "Hinter den Kulissen", "../",
     (("](../mathematik/", "](../../aktuariat/mathematik/"),
      ("](../tarifplaene/", "](../../aktuariat/tarifplaene/"))),
    ("simulation/tagesbetrieb.md",
     "hinter-den-kulissen/simulation/tagesbetrieb.md", "Hinter den Kulissen", "../"),
    ("simulation/bestandserzeugung.md",
     "hinter-den-kulissen/simulation/bestandserzeugung.md", "Hinter den Kulissen", "../",
     (("](README.md)", "](./)"),)),
    ("simulation/erfahrungsannahmen.md",
     "hinter-den-kulissen/simulation/erfahrungsannahmen.md", "Hinter den Kulissen", "../",
     (("](../mathematik/", "](../../aktuariat/mathematik/"),)),
)

#: MathJax fuer Fachdokumente mit TeX-Formeln. kramdown reicht die Formeln
#: als ``\\(...\\)`` und ``\\[...\\]`` weiter (:func:`_fuer_pages`).
MATHJAX = (
    '<script>window.MathJax={tex:{inlineMath:[["$","$"],'
    '["\\\\(","\\\\)"]]}};</script>\n'
    '<script defer src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/'
    'tex-mml-chtml.js"></script>\n'
)


#: Liquid laeuft auf Pages vor kramdown ueber jede Seite; auch eine .md ohne
#: Vorspann ist eine Seite (jekyll-optional-front-matter, auf Pages Standard).
#: Ein importiertes Dokument ist nicht fuer Liquid geschrieben: "{{" in einer
#: Formel des KLV-Tarifplans brach den ganzen Pages-Build ab (gemessen mit dem
#: Renderer von Pages am 08.10.2026). Sein Rumpf steht deshalb in raw. Die
#: Ueberschrift aus dem Vorspann bleibt davor, denn jekyll-titles-from-headings
#: nimmt den Seitentitel nur aus einer Ueberschrift am Anfang der Seite.
ROH_AUF, ROH_ZU = "{% raw %}", "{% endraw %}"

#: Im Rumpf eines importierten Dokuments: ein Codeblock, ein Codespan, eine
#: Formel in ``$$...$$`` oder eine in ``$...$`` (Gruppe ``formel``).
_FORMEL_ODER_CODE = re.compile(
    r"^(?P<zaun>```|~~~)[^\n]*\n.*?^(?P=zaun)[ \t]*$"
    r"|(?P<striche>`+)(?:(?!\n[ \t]*\n).)+?(?<!`)(?P=striche)(?!`)"
    r"|\$\$.+?\$\$"
    r"|\$(?P<formel>[^$\n]+?)\$",
    re.S | re.M)


def _fuer_pages(rumpf: str) -> str:
    """Den Rumpf eines importierten Dokuments so ablegen, wie Pages ihn liest.

    kramdown kennt als Mathematik nur ``$$...$$`` und reicht sie unveraendert
    an MathJax weiter, im Text als ``\\(...\\)``, als eigener Absatz als
    ``\\[...\\]``. ``$...$`` ist fuer kramdown Text: Escapes, Hervorhebung und
    Typografie laufen darueber, bevor MathJax es sieht. Gemessen am 08.10.2026
    kamen so 35 von 489 Formeln veraendert an: aus ``\\{`` wurde ``{``,
    ``A^{1}_{y:m} + E_{y:m}`` bekam ein ``<em>``, aus ``s'`` wurde ``s’``.
    Deshalb wird jede Formel ``$$...$$``; Codeblock und Codespan bleiben, wie
    sie sind. Dazu steht der Rumpf in raw (:data:`ROH_AUF`)."""
    rumpf = _FORMEL_ODER_CODE.sub(
        lambda m: m.group(0) if m.group("formel") is None else f"$${m.group('formel')}$$",
        rumpf)
    return f"{ROH_AUF}\n{rumpf}\n{ROH_ZU}\n"


def _titel_und_rumpf(text: str) -> tuple:
    """YAML-Vorspann eines Fachdokuments abtrennen.

    Der Titel des Vorspanns wird zur Ueberschrift der importierten
    Seite; der Rest des Vorspanns (Druckformat u. ae.) betrifft nur die
    Dokument-Erzeugung und faellt weg.
    """
    if not text.startswith("---\n"):
        return "", text
    kopf, _, rumpf = text[4:].partition("\n---\n")
    zeilen = kopf.splitlines()
    for i, zeile in enumerate(zeilen):
        if not zeile.startswith("title:"):
            continue
        wert = zeile.split(":", 1)[1].strip()
        # Ein YAML-Titel darf umbrochen sein — Folgezeilen anhaengen,
        # bis das schliessende Anfuehrungszeichen erreicht ist.
        while not (len(wert) > 1 and wert.endswith('"')):
            i += 1
            wert += " " + zeilen[i].strip()
        return wert.strip('"'), rumpf
    return "", rumpf


def _vorspann(rel: Path, titel: str, mit_mathe: bool,
              zurueck: tuple = ("Rechenkern und Tarifwerk", "../")) -> str:
    """Kopf einer importierten Seite: Stil, Banderole, Titel, MathJax.

    ``rel`` ist der Zielpfad RELATIV ZUR AUFTRITTS-WURZEL — daraus
    ergibt sich die Tiefe fuer Stylesheet- und Startseiten-Verweis.
    """
    wurzel = "../" * (len(rel.parts) - 1)
    # Reihenfolge wie auf den uebrigen Seiten: erst die Ueberschrift, dann
    # die Navigation. Das Stylesheet zieht beide ueber die volle Breite
    # und macht daraus das Kopfband — steht die Navigation davor, faellt
    # das Band aus und die Seite sieht aus wie aus einem anderen Haus.
    # Und EIN Band statt zweier Ruecksprünge untereinander: Der Weg
    # zurueck ist eine Zeile, nicht zwei.
    z: List[str] = []
    if titel:
        z.append(f"# {titel}")
        z.append("")
    schritte = [(wurzel or "./", "Startseite")]
    if zurueck and zurueck[0]:
        schritte.append((zurueck[1], zurueck[0]))
    z.append('<nav class="kopf">'
             + "".join(f'<a href="{ziel}">← {name}</a>' for ziel, name in schritte)
             + "</nav>")
    if mit_mathe:
        z.append(MATHJAX.rstrip("\n"))
    z.append("")
    return "\n".join(z) + "\n"


def fachdokumente(docs: Path, ziel: Path,
                  dokumente=FACHDOKUMENTE) -> List[tuple]:
    """Die Fachdokumente unter ``aktuariat/`` in den Auftritt einbinden.

    Ein gelistetes Dokument, das fehlt, bricht den Bau ab: Eine Seite,
    die still ohne ihre Tarifplaene erschiene, saehe vollstaendig aus
    und waere es nicht.
    """
    aus: List[tuple] = []
    for eintrag in dokumente:
        name, zielname, zurueck_titel, zurueck_ziel = eintrag[:4]
        ersetzungen = eintrag[4] if len(eintrag) > 4 else ()
        quelle = docs / name
        if not quelle.is_file():
            raise VeroeffentlichungFehler(
                f"Fachdokument fehlt: {quelle}. Der Auftritt wuerde ohne "
                "es vollstaendig aussehen und waere es nicht.")
        _pruefe_regie(quelle)
        text = quelle.read_text(encoding="utf-8")
        titel, rumpf = _titel_und_rumpf(text)
        rel = Path(zielname)
        zielpfad = ziel / rel
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        for alt, neu in ersetzungen:
            rumpf = rumpf.replace(alt, neu)
        zielpfad.write_text(
            _vorspann(rel, titel, "$" in rumpf,
                      zurueck=(zurueck_titel, zurueck_ziel)) + _fuer_pages(rumpf)
            + "\n" + fusszeile("../" * (len(rel.parts) - 1)) + "\n",
            encoding="utf-8")
        aus.append((zielname, titel))
    _tarifplan_uebersicht(ziel, aus)
    return aus


def _tarifplan_uebersicht(ziel: Path, importiert: List[tuple]) -> None:
    """Generierte Uebersichtsseite der importierten Tarifplaene."""
    plaene = [(Path(name), titel) for name, titel in importiert
              if name.startswith("aktuariat/tarifplaene/")]
    if not plaene:
        return
    z = [reiter("../../", "aktuariat"),
         "", "[← Aktuariat](../)", "", "# Tarifpläne", "",
         "Die Bewertung jedes Vertrags folgt einem dokumentierten",
         "Tarifplan. Die geführten Tarifgenerationen:", ""]
    for pfad, titel in plaene:
        z.append(f"* [{titel or pfad.stem}]({pfad.stem}.html)")
    z += ["",
          "Das gemeinsame mathematische Rückgrat — Zustandsraum,",
          "Thiele-Rekursion, Rechnungsgrundlagen — steht einmal in der",
          "[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.html).",
          ""]
    pfad = ziel / "aktuariat" / "tarifplaene" / "index.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z) + "\n" + fusszeile("../../") + "\n", encoding="utf-8")


def architektur(docs: Path, ziel: Path) -> int:
    """``docs/architektur`` unter ``hinter-den-kulissen/architektur/`` einspielen.

    Vollstaendig — ADRs, Prinzipien, Migrations-Pipeline —, damit die
    Querverweise der Dokumente untereinander gelten. ``README.md`` wird
    zur Uebersicht ``index.md``. Nur ``landkarte.md`` bleibt draussen:
    Die Landkarte wird beim Bau FRISCH aus dem Code erzeugt
    (``landkarten``); eine eingecheckte Fassung zu kopieren waere
    genau die Drift, die der Import vermeiden soll.
    """
    verzeichnis = docs / "architektur"
    if not verzeichnis.is_dir():
        raise VeroeffentlichungFehler(
            f"Architektur-Dokumente fehlen: {verzeichnis}")
    anzahl = 0
    for quelle in sorted(verzeichnis.glob("*.md")):
        if quelle.name == "landkarte.md":
            continue
        _pruefe_regie(quelle)
        titel, rumpf = _titel_und_rumpf(
            quelle.read_text(encoding="utf-8"))
        # Verweise auf die eingecheckte Landkarte zeigen im Auftritt auf
        # die beim Bau frisch erzeugte Fassung.
        rumpf = rumpf.replace("](landkarte.md)", "](landkarte.html)")
        name = "index.md" if quelle.name == "README.md" else quelle.name
        rel = Path("hinter-den-kulissen") / "architektur" / name
        zielpfad = ziel / rel
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        zielpfad.write_text(
            _vorspann(rel, titel, "$" in rumpf,
                      zurueck=("Hinter den Kulissen", "../")) + _fuer_pages(rumpf)
            + "\n" + fusszeile("../../") + "\n",
            encoding="utf-8")
        anzahl += 1
    return anzahl


def landkarten(repo: Path, ziel: Path) -> None:
    """Die Landkarte des Codes beim Bau frisch erzeugen.

    ``ontologie.landkarte`` liefert EIN selbsttragendes HTML-Artefakt,
    das alle Umfaenge (Schichten bis Module) selbst enthaelt; als Stand
    wird der Commit gestempelt, aus dem gebaut wurde. Ein
    fehlgeschlagener Lauf bricht den Bau ab — eine IT-Seite mit einer
    Landkarte von vorgestern waere Drift mit Ansage.
    """
    import subprocess
    stand = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=repo,
        capture_output=True, text=True).stdout.strip()
    aus = ziel / "hinter-den-kulissen" / "architektur" / "landkarte.html"
    aus.parent.mkdir(parents=True, exist_ok=True)
    lauf = subprocess.run(
        [sys.executable, "-m", "rechner_pipeline.ontologie.landkarte",
         "--format", "html", "--stand", stand, "--out", str(aus)],
        cwd=repo, capture_output=True, text=True)
    if lauf.returncode != 0:
        raise VeroeffentlichungFehler(
            "Die Landkarte liess sich nicht erzeugen: "
            f"{lauf.stderr.strip()[:300]}")


def pruefgates(repo: Path, ziel: Path) -> None:
    """``migrationen/pruefgates.md`` beim Bau aus dem Gate-Register erzeugen.

    ``gates.register`` ist die Lesefassung der Gate-Namensordnung als
    Code; seine Tests binden die Namen an die Gate-Module und die
    Vorgaenger an das, was die Abschlussabnahme erzwingt. Die Seite
    entsteht je Bau aus dem Register — abgetippt wird nichts, ein
    fehlgeschlagener Lauf bricht den Bau ab.
    """
    import subprocess
    lauf = subprocess.run(
        [sys.executable, "-m", "rechner_pipeline.gates.register",
         "--format", "markdown"],
        cwd=repo, capture_output=True, text=True)
    if lauf.returncode != 0 or "| **P-Q1**" not in lauf.stdout:
        raise VeroeffentlichungFehler(
            "Das Gate-Register liess sich nicht ausgeben: "
            f"{lauf.stderr.strip()[:300]}")
    # Je Gate ein Sprungziel: Die Fallseite verweist von jeder Station auf
    # die Zeile ihres Gates (Maintainer 06.10.2026, Register statt Kaesten).
    tabelle = re.sub(r"^\| \*\*([A-Z]-[A-Z]\d)\*\* ",
                     lambda m: f'| <span id="{m.group(1)}"></span>**{m.group(1)}** ',
                     lauf.stdout.rstrip("\n"), flags=re.M)
    # Lesbar fuer Menschen (Maintainer 06.10.2026): ohne die Spalte Werkzeug
    # (Modulnamen, Entwicklersicht) und mit Umlauten statt Repo-Umschrift.
    zeilen_t = []
    for zeile in tabelle.splitlines():
        zellen = [c.strip() for c in zeile.strip().strip("|").split("|")]
        if len(zellen) != 7:
            raise VeroeffentlichungFehler(f"Gate-Register: Zeile mit {len(zellen)} Spalten statt 7: {zeile[:80]}")
        del zellen[4]
        zeilen_t.append("| " + " | ".join(zellen) + " |")
    tabelle = "\n".join(zeilen_t)
    for roh, schoen in (("Was geprueft bzw. abgenommen wird", "Was geprüft bzw. abgenommen wird"),
                        ("Hinterlaesst", "Hinterlässt"), ("Vorgaenger", "Vorgänger"),
                        ("Pruefung durch das Programm", "Prüfung durch das Programm")):
        tabelle = tabelle.replace(roh, schoen)
    z = [_vorspann(Path("migrationen") / "pruefgates.md", "Unsere Prüfgates", False,
                   zurueck=("Bestandsmigrationen", "./")).rstrip("\n"), ""]
    z += [
        "Jede Stufe einer Bestandsübernahme endet in einem Gate. Der Name",
        "sagt, wer entscheidet und worüber: **P** ist eine Prüfung durch das",
        "Programm — deterministisch, sie blockiert bei Rot, kein Mensch ist",
        "beteiligt; **A** ist eine Abnahme durch einen Menschen — das Gate",
        "erzeugt die Vorlage und hält den signierten Entscheid-Snapshot.",
        "Der Buchstabe danach nennt den Gegenstand: **Q** Quellen und",
        "Ontologie, **K** Rechenkern, **B** Bestand, **M** die Migration als",
        "Ganzes. Die Nummer ist die Reihenfolge innerhalb des Gegenstands;",
        "ein abgeschaltetes Gate hinterlässt eine Lücke, es rückt nichts nach.", "",
        "Die Stufen: **1** Quellen werden zur Faktenbasis, **2** die",
        "Faktenbasis wird zur Spezifikation und Parametrierung des",
        "Rechenkerns, **3** Abnahme — Rechenkern, Bestand und die drei",
        "aktuariellen Tests, zuletzt das Migrationscontrolling A-M4, das die",
        "Belege aller vorangehenden Gates bindet.",
        "Die Spalte Vorgänger nennt nur, was das Gate tatsächlich verlangt;",
        "im Tarif-Scope weniger als im Bestands-Scope.", "",
        "Die Tabelle stammt aus dem Gate-Register unseres Systems, nicht aus",
        "einer Abschrift.", "",
        tabelle, "",
        "Wie die Gates in einem Fall gelaufen sind, zeigt die Seite der",
        "jeweiligen Übernahme unter [Bestandsmigrationen](./): je Station",
        "der Lauf, der zählt, und im Verzeichnis der Belege alle Prüfläufe",
        "und Entscheide.", "",
    ]
    aus = ziel / "migrationen" / "pruefgates.md"
    aus.parent.mkdir(parents=True, exist_ok=True)
    aus.write_text("\n".join(z) + fusszeile("../") + "\n", encoding="utf-8")


def techstack(repo: Path, ziel: Path) -> None:
    """``it/techstack.md`` beim Bau aus ``pyproject.toml`` erzeugen."""
    import tomllib
    with (repo / "pyproject.toml").open("rb") as datei:
        projekt = tomllib.load(datei)["project"]

    z = [_vorspann(Path("it") / "techstack.md", "Techstack", False,
                   zurueck=("IT", "./")).rstrip("\n"), ""]
    z += ["Sprache, Bibliotheken und Versionen des Systems, wie sie",
          "im Betrieb gepinnt sind.", "",
          f"Python {projekt.get('requires-python', '?')}, keine",
          "Laufzeit-Abhaengigkeit zu Office-Produkten oder zu",
          "KI-Diensten: Der Rechenkern und alle Gates laufen ohne",
          "Netz. Versionen exakt gepinnt:", "",
          "| Laufzeit | Version |", "|---|---|"]
    for eintrag in projekt.get("dependencies", []):
        name, _, version = eintrag.partition("==")
        z.append(f"| `{name}` | {version or '—'} |")
    z += ["", "| Entwicklung | Version |", "|---|---|"]
    for eintrag in (projekt.get("optional-dependencies") or {}).get("dev", []):
        name, _, version = eintrag.partition("==")
        z.append(f"| `{name}` | {version or '—'} |")
    z += ["",
          "Die KI-Agenten arbeiten AUSSERHALB dieser Laufzeit: Sie lesen",
          "Lieferungen und schlagen vor; gerechnet und geurteilt wird",
          "ausschliesslich im deterministischen Kern.", ""]
    pfad = ziel / "it" / "techstack.md"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text("\n".join(z) + "\n" + fusszeile("../") + "\n", encoding="utf-8")


def baue(quellen: Path, ziel: Path, modell: Dict[str, Any]) -> List[str]:
    """Die Quellseiten in den Push-Baum spiegeln, mit drei Zwaengen:
    Regie-Sperre, Banderole, aufgeloeste Kennzahlen."""
    if not (quellen / "index.md").is_file():
        raise VeroeffentlichungFehler(
            f"Keine Unternehmensseiten unter {quellen} (index.md fehlt).")
    if not (quellen / "_config.yml").is_file():
        raise VeroeffentlichungFehler(
            f"{quellen}/_config.yml fehlt — ohne Jekyll-Konfiguration "
            "nimmt GitHub Pages ein Vorgabethema, das die Seiten bricht.")

    kopiert: List[str] = []
    for datei in sorted(quellen.rglob("*")):
        if not datei.is_file():
            continue
        _pruefe_regie(datei)
        zielpfad = ziel / datei.relative_to(quellen)
        zielpfad.parent.mkdir(parents=True, exist_ok=True)
        if datei.suffix == ".md":
            rel = datei.relative_to(quellen)
            text = _kennzahlen(
                datei.read_text(encoding="utf-8"), modell, str(rel), ziel)
            wurzel = "../" * (len(rel.parts) - 1)
            text = _mit_reiter(text, wurzel, rel.parts[0] if len(rel.parts) > 1 else "")
            text = _mit_fusszeile(text, wurzel)
            if BANDEROLE not in text:
                raise VeroeffentlichungFehler(
                    f"{datei.relative_to(quellen)} traegt die Banderole "
                    f"({BANDEROLE!r}) nicht. Jede Unternehmensseite muss "
                    "den Fiktions-Hinweis tragen — sonst saehe der "
                    "Auftritt aus wie ein echter Versicherer.")
            zielpfad.write_text(text, encoding="utf-8")
        else:
            shutil.copy2(datei, zielpfad)
        kopiert.append(str(zielpfad.relative_to(ziel)))
    return kopiert


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        prog="python werkzeuge/unternehmensseite.py",
        description="Unternehmensseiten der Vorfuehrung in den Push-Baum "
                    "zusammenbauen.")
    p.add_argument("--quellen", default="plv/seite",
                   help="versionierte Quellseiten (Vorgabe: plv/seite)")
    p.add_argument("--daten", required=True,
                   help="falldaten-Modell des aktuellen Falls — Quelle "
                        "der {{...}}-Kennzahlen in den Quellseiten")
    p.add_argument("--docs", default="docs",
                   help="Wurzel der Fachdokumente (Vorgabe: docs); von "
                        "dort werden Tarifplaene und Grundsatz-"
                        "dokumentation importiert")
    p.add_argument("--repo", default=".",
                   help="Repo-Wurzel (pyproject.toml, Landkarten-Erzeugung)")
    p.add_argument("--out", required=True,
                   help="Push-Baum der Seite; die Fall-Seiten liegen dort "
                        "unter migrationen/<fall>/")
    args = p.parse_args(argv)

    quellen = Path(args.quellen).resolve()
    repo = Path(args.repo).resolve()
    ziel = Path(args.out).resolve()
    ziel.mkdir(parents=True, exist_ok=True)
    try:
        modell = json.loads(Path(args.daten).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Kein Falldaten-Modell: {args.daten} ({exc})",
              file=sys.stderr)
        return 2
    try:
        paket = stand(modell, ziel)
        kopiert = baue(quellen, ziel, modell)
        doku = fachdokumente(Path(args.docs).resolve(), ziel, FACHDOKUMENTE + tuple(
            (quelle, ziel_name, "Unsere Bestandsmigrationen", "./")
            for quelle, ziel_name, _ in darstellung.falldokumente(modell)))
        adrs = architektur(Path(args.docs).resolve(), ziel)
        landkarten(repo, ziel)
        pruefgates(repo, ziel)
        techstack(repo, ziel)
    except VeroeffentlichungFehler as exc:
        print(f"ABBRUCH: {exc}", file=sys.stderr)
        return 1

    print(f"{ziel}: {len(kopiert)} Unternehmensseiten-Dateien, "
          f"{len(doku)} Fachdokumente, {adrs} Architektur-Dokumente, "
          "Landkarte, Pruefgates und Techstack erzeugt")
    if paket:
        print(f"  Stands-Paket uebernommen: {len(paket)} Dateien unter {STAND_DIR}/ "
              f"(Stand {modell['betrieb'].get('stand')})")
    else:
        print("  KEIN Stands-Paket — die Unternehmensseiten zeigen keinen "
              "gefuehrten Bestand (auftritt.py --stands-paket)")
    faelle = sorted(
        p.parent.name for p in (ziel / "migrationen").glob("*/index.md")
    ) if (ziel / "migrationen").is_dir() else []
    if faelle:
        print(f"  eingehaengte Migrationsberichte: {', '.join(faelle)}")
    else:
        print("  noch KEIN Migrationsbericht eingehaengt "
              "(vorzeigeseite.py --out <ziel>/migrationen/<fall>)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
