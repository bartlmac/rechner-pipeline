"""Bestand heute — die interne Sicht auf den gefuehrten Stand und das Stands-Paket.

Fachkonzept docs/simulation/tagesbetrieb.md, Abschnitt 8.3. Zwei Wege,
die sich nicht ausschliessen:

* **Interne Sicht, taeglich.** Nach jedem gruenen Lauf rendert der
  Tageslauf nach ``daten/seite/index.html`` einen Abschnitt "Bestand
  heute": Kennzahlen des gefuehrten Tags, Neugeschaeft der Woche, die
  letzten Buchungen, die Monatsabschluesse — aus dem Protokoll und dem
  Tagesjournal, ohne eine einzige neue Rechnung. Ein Caddy auf dem
  Betriebsrechner liefert das Verzeichnis read-only aus.
* **Oeffentliche Sicht, gestempelt.** ``stands_paket`` exportiert den
  Stand als Paket (``stand.json`` mit Datum, Manifest-Hash, Kennzahlen,
  Abschluessen und Provenienz, dazu die Berichte des juengsten
  Abschlusses). Die Vorzeigeseite liest ihre Kennzahlen daraus
  (``werkzeuge/falldaten.py --stands-paket``) statt aus einem Fall —
  dieselbe Drift-Regel: erzeugt, nie abgetippt. Veroeffentlicht wird
  weiterhin vom Menschen; automatisch veroeffentlicht wird nichts, was
  nicht durch P-B1 ging — und ins Paket kommt nur ein uebernommener
  (gruener) Stand.

Deterministisch: dieselben Daten ergeben dieselbe Seite und dasselbe
Paket; es gibt keinen Zeitstempel ausser dem gefuehrten Tag selbst.

Run via::

    python -m rechner_pipeline.betrieb.seite --stand <daten> [--paket <ziel>]

Knoten: klv, bu
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html as _html
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from rechner_pipeline.bestand.manifest import lies_manifest, sha256_bytes
from rechner_pipeline.bestand.parquet_io import neue_datei, read_portfolio
from rechner_pipeline.models.bestand import TAGESJOURNAL_NAMES

PAKET_SCHEMA_VERSION = 1
SEITE_DIR = "seite"
PAKET_DATEI = "stand.json"

EREIGNIS_TITEL = {
    "ZUG": "Zugang", "MIG": "Migrationszugang", "ERH": "Dynamische Erhöhung",
    "RED": "Beitragsherabsetzung", "PEX": "Beitragsfreistellung",
    "INV": "Invalidisierung", "REA": "Reaktivierung", "STO": "Storno",
    "TOD": "Tod", "ABL": "Ablauf",
}


class SeiteError(ValueError):
    """Kein uebernommener Stand — es gibt nichts zu zeigen."""


# --------------------------------------------------------------------------- #
# Das Datenmodell des Stands (dieselbe Quelle fuer Seite und Paket)
# --------------------------------------------------------------------------- #


def _protokoll(ablage, aktuelle_zeile: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Die Protokollzeilen — plus die Zeile des laufenden Tages, wenn der
    Tageslauf sie noch nicht angefuegt hat (er rendert vor dem Anfuegen,
    damit die Zeile die Seite nennt)."""
    from rechner_pipeline.betrieb.tageslauf import lies_protokoll

    zeilen = list(lies_protokoll(ablage.protokoll_pfad))
    if aktuelle_zeile is not None:
        zeilen.append(aktuelle_zeile)
    return zeilen


def _letzter_gruener(zeilen: List[Dict[str, Any]], ablage) -> Dict[str, Any]:
    gruene = [z for z in zeilen if z.get("uebernommen")]
    if not gruene:
        raise SeiteError(
            f"{ablage.protokoll_pfad}: kein uebernommener Lauf — ohne gefuehrten "
            "Stand gibt es keinen Bestand heute"
        )
    return gruene[-1]


def stand_modell(ablage, aktuelle_zeile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Datum, Kennzahlen, Neugeschaeft, Buchungen, Abschluesse, Provenienz — aus
    Protokoll, Journal und Manifest des uebernommenen Stands."""
    zeilen = _protokoll(ablage, aktuelle_zeile)
    zeile = _letzter_gruener(zeilen, ablage)
    heute = _dt.date.fromisoformat(str(zeile["heute"]))
    manifest = lies_manifest(ablage.stand)
    if str(manifest["horizont"]) != heute.isoformat():
        raise SeiteError(
            f"Stand fuehrt {manifest['horizont']}, das Protokoll {heute.isoformat()} "
            "— Stand und Nachweis passen nicht zusammen"
        )
    journal = (
        read_portfolio(ablage.tagesjournal_pfad, expected_columns=TAGESJOURNAL_NAMES)
        if ablage.tagesjournal_pfad.is_file()
        else pd.DataFrame({n: pd.Series(dtype="object") for n in TAGESJOURNAL_NAMES})
    )
    woche_ab = pd.Timestamp(heute - _dt.timedelta(days=6))
    neu = journal[(journal["herkunft"] == "neugeschaeft") & (journal["buchungsdatum"] >= woche_ab)]
    je_tag = {
        pd.Timestamp(t).date().isoformat(): int(n)
        for t, n in sorted(neu.groupby("buchungsdatum").size().items())
    }
    letzte = journal.tail(20).iloc[::-1]
    buchungen = [
        {
            "buchungsdatum": pd.Timestamp(z.buchungsdatum).date().isoformat(),
            "police_id": int(z.police_id),
            "ereignis": str(z.ereignis),
            "wirkungstag": pd.Timestamp(z.status_date).date().isoformat(),
            "betrag": float(z.betrag),
            "betrag_art": str(z.betrag_art),
            "herkunft": str(z.herkunft),
        }
        for z in letzte.itertuples(index=False)
    ]
    je_ereignis = {
        str(k): int(v) for k, v in sorted(journal["ereignis"].value_counts().items())
    } if len(journal) else {}
    # Abschluesse: aus allen uebernommenen Protokollzeilen, je Stichtag einmal.
    abschluesse: Dict[str, Dict[str, Any]] = {}
    for z in zeilen:
        if not z.get("uebernommen"):
            continue
        for a in z.get("abschluesse") or []:
            eintrag = abschluesse.setdefault(a["stichtag"], {"stichtag": a["stichtag"]})
            if a.get("neu"):
                eintrag["datei"] = a["datei"]
                eintrag["sha256"] = a.get("sha256")
            if a.get("bericht"):
                eintrag["bericht"] = a["bericht"]
            if a.get("teilbestaende"):
                eintrag["teilbestaende"] = a["teilbestaende"]
    return {
        "schema_version": PAKET_SCHEMA_VERSION,
        "stand": heute.isoformat(),
        "gefuehrt_seit": (
            zeilen[0]["nachgeholt"][0] if zeilen[0].get("nachgeholt") else zeilen[0]["heute"]
        ),
        "bestand": dict(zeile["bestand"]),
        "neugeschaeft": {
            "seit_betriebsbeginn": int(zeile.get("neugeschaeft_seit_betriebsbeginn", 0)),
            "woche": je_tag,
            "woche_summe": int(len(neu)),
        },
        "buchungen": {
            "gesamt": int(len(journal)),
            "je_ereignis": je_ereignis,
            "letzte": buchungen,
        },
        "abschluesse": [abschluesse[k] for k in sorted(abschluesse)],
        "uebernahmen": list(zeile.get("uebernahmen") or []),
        "provenienz": {
            "manifest_sha256": zeile.get("manifest_sha256"),
            "config_sha256": zeile.get("config_sha256"),
            "kern_version": zeile.get("kern_version"),
            "image_digest": zeile.get("image_digest"),
            "image_revision": zeile.get("image_revision"),
            "image_tag": zeile.get("image_tag"),
            "pb1": zeile.get("pb1", {}).get("urteil"),
            "tagesjournal_sha256": (zeile.get("tagesjournal") or {}).get("sha256"),
        },
    }


# --------------------------------------------------------------------------- #
# Bestand heute (HTML)
# --------------------------------------------------------------------------- #

_STIL = """
body{margin:0;background:#f8f8f6;color:#1b1e1c;font:15px/1.55 system-ui,sans-serif}
main{max-width:58rem;margin:0 auto;padding:2.5rem 1.2rem 5rem}
h1{font:600 2rem/1.15 Georgia,serif;margin:0 0 .3rem}
h2{font:600 1.25rem/1.25 Georgia,serif;margin:2.2rem 0 .7rem}
.unter{color:#5f6663;margin:0 0 1.8rem}
.zahlen{display:grid;gap:1px;background:#dcdfda;border:1px solid #dcdfda;border-radius:6px;
overflow:hidden;grid-template-columns:repeat(auto-fit,minmax(9rem,1fr));margin-bottom:2rem}
.zahl{background:#fff;padding:.8rem 1rem}.zahl b{display:block;font:600 1.4rem/1.1 Georgia,serif}
.zahl span{font-size:.72rem;color:#5f6663;text-transform:uppercase;letter-spacing:.05em}
table{border-collapse:collapse;width:100%;font-size:.87rem;background:#fff;
border:1px solid #dcdfda;border-radius:6px}
th{text-align:left;font-size:.7rem;text-transform:uppercase;color:#5f6663;padding:.5rem .8rem;
border-bottom:1px solid #c1c6bf}td{padding:.4rem .8rem;border-bottom:1px solid #dcdfda}
td.num{text-align:right;font-variant-numeric:tabular-nums}
.fuss{margin-top:2.5rem;color:#5f6663;font-size:.78rem;font-family:ui-monospace,monospace}
.banderole{background:#fff4e0;border:1px solid #e0c48a;padding:.6rem .9rem;border-radius:6px;font-size:.88rem}
ul{padding-left:1.1rem}
"""


def _e(x: Any) -> str:
    return _html.escape(str(x))


def _zahl(x: float, dez: int = 2) -> str:
    return f"{x:,.{dez}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def luecken(modell: Dict[str, Any]) -> List[Dict[str, str]]:
    """Was der Stand NICHT belegt — sichtbar auf der Seite, nicht nur im Protokoll.

    Dieselbe Ehrlichkeit wie die Fall-Seite (T20-03): Ein Stand ohne
    erfassten Image-Digest ist nicht auf sein Image rueckfuehrbar, eine
    Uebernahme ohne A-M4-Snapshot nicht auf ihre Abnahme, ein Altsnapshot
    ohne Schluesselklasse weist sie nicht aus, und vor dem ersten
    Monatsabschluss gibt es keinen festgeschriebenen Stand.
    """
    aus: List[Dict[str, str]] = []
    p = modell.get("provenienz") or {}
    if not p.get("image_digest") or p.get("image_digest") == "nicht erfasst":
        aus.append({"was": "Image-Digest des Laufs",
                    "wirkung": "Der Stand ist auf Kern-Version und Config, nicht auf ein "
                               "Container-Image rueckfuehrbar."})
    for u in modell.get("uebernahmen") or []:
        if not u.get("snapshot_sha256"):
            aus.append({"was": f"A-M4-Snapshot der Uebernahme {u.get('fall')}",
                        "wirkung": "Der Zugang ist nicht auf seine Abnahme rueckfuehrbar."})
        z = u.get("zeichnung") or {}
        if z.get("schluesselklasse", "nicht ausgewiesen") == "nicht ausgewiesen":
            aus.append({"was": f"Schluesselklasse der A-M4-Zeichnung ({u.get('fall')})",
                        "wirkung": "Der Snapshot fuehrt sie nicht (Altsnapshot) oder er "
                                   "fehlt; die Rolle steht, die Schluesselklasse nicht."})
    if not modell.get("abschluesse"):
        aus.append({"was": "Monatsabschluss",
                    "wirkung": "Noch kein festgeschriebener Bewertungsstand."})
    return aus


def rendere_html(modell: Dict[str, Any]) -> str:
    """Den Abschnitt "Bestand heute" als selbst-enthaltene Seite rendern."""
    b = modell["bestand"]
    n = modell["neugeschaeft"]
    p = modell["provenienz"]
    z: List[str] = [
        "<!doctype html>\n<html lang=\"de\">\n<head>\n<meta charset=\"utf-8\">\n",
        f"<title>Bestand heute — Stand {_e(modell['stand'])}</title>\n",
        f"<style>{_STIL}</style>\n</head>\n<body>\n<main>\n",
        "<p class=\"banderole\"><b>Dies ist eine Vorfuehrung, kein echter Bestand.</b> "
        "Die Pfefferminzia LV ist ein fiktives Unternehmen, ihre Vertraege sind "
        "synthetisch erzeugt, ihre Abnahmen mit einem Simulationsschluessel "
        "gezeichnet. Diese Seite verifiziert keine Signatur; sie zeigt, was "
        "Protokoll und Tagesjournal fuehren.</p>\n",
        f"<h1>Bestand heute</h1>\n<p class=\"unter\">Pfefferminzia LV, gefuehrter Stand "
        f"<b>{_e(modell['stand'])}</b> (Tagesbetrieb seit {_e(modell['gefuehrt_seit'])}) · "
        f"Manifest <code>{_e((p.get('manifest_sha256') or '')[:16])}</code> · "
        f"Wache P-B1 {_e(p.get('pb1'))}.</p>\n",
    ]
    offene = luecken(modell)
    if offene:
        z.append("<h2>Was diese Seite NICHT zeigt</h2>\n<ul>\n")
        for l in offene:
            z.append(f"<li><b>{_e(l['was'])}</b> — {_e(l['wirkung'])}</li>\n")
        z.append("</ul>\n")
    z += [
        "<div class=\"zahlen\">\n",
        f"<div class=\"zahl\"><b>{b['in_force']}</b><span>Vertraege in Kraft</span></div>\n",
    ]
    for produkt, anzahl in sorted(b.get("je_produkt", {}).items()):
        z.append(f"<div class=\"zahl\"><b>{anzahl}</b><span>{_e(produkt.upper())}</span></div>\n")
    z += [
        f"<div class=\"zahl\"><b>{b.get('uebernommen_in_force', 0)}</b><span>davon uebernommen</span></div>\n",
        f"<div class=\"zahl\"><b>{b.get('policiert_beginn_folgt', 0)}</b><span>policiert, Beginn folgt</span></div>\n",
        f"<div class=\"zahl\"><b>{n['woche_summe']}</b><span>Neugeschaeft der Woche</span></div>\n",
        f"<div class=\"zahl\"><b>{n['seit_betriebsbeginn']}</b><span>Neugeschaeft seit Betriebsbeginn</span></div>\n",
        "</div>\n",
        "<h2>Neugeschaeft der Woche</h2>\n<table><thead><tr><th>Verkaufstag</th><th>Vertraege</th></tr></thead><tbody>\n",
    ]
    for tag, anzahl in n["woche"].items():
        z.append(f"<tr><td>{_e(tag)}</td><td class=\"num\">{anzahl}</td></tr>\n")
    if not n["woche"]:
        z.append("<tr><td colspan=\"2\">kein Abschluss in den letzten sieben Tagen</td></tr>\n")
    z.append("</tbody></table>\n<h2>Letzte Buchungen</h2>\n<table><thead><tr><th>Buchungstag</th>"
             "<th>Police</th><th>Vorfall</th><th>Wirkungstag</th><th>Betrag</th><th>Herkunft</th></tr></thead><tbody>\n")
    for bu in modell["buchungen"]["letzte"]:
        z.append(
            f"<tr><td>{_e(bu['buchungsdatum'])}</td><td>{bu['police_id']}</td>"
            f"<td>{_e(EREIGNIS_TITEL.get(bu['ereignis'], bu['ereignis']))}</td>"
            f"<td>{_e(bu['wirkungstag'])}</td><td class=\"num\">{_zahl(bu['betrag'])} "
            f"({_e(bu['betrag_art'])})</td><td>{_e(bu['herkunft'])}</td></tr>\n"
        )
    z.append("</tbody></table>\n<h2>Buchungen seit Betriebsbeginn</h2>\n<table><thead><tr><th>Vorfall</th><th>Anzahl</th></tr></thead><tbody>\n")
    for ereignis, anzahl in modell["buchungen"]["je_ereignis"].items():
        z.append(f"<tr><td>{_e(EREIGNIS_TITEL.get(ereignis, ereignis))}</td><td class=\"num\">{anzahl}</td></tr>\n")
    z.append("</tbody></table>\n<h2>Monatsabschluesse</h2>\n<table><thead><tr><th>Stichtag</th><th>Abschluss</th><th>Bericht</th></tr></thead><tbody>\n")
    for a in modell["abschluesse"]:
        bericht = (
            f"<a href=\"../berichte/{_e(a['bericht'])}\">{_e(a['bericht'])}</a>" if a.get("bericht") else "—"
        )
        for t in a.get("teilbestaende") or []:
            bericht += f"<br><a href=\"../berichte/{_e(t['bericht'])}\">Teilbestand {_e(t['fall'])}</a>"
        z.append(f"<tr><td>{_e(a['stichtag'])}</td><td><code>{_e(a.get('datei', '—'))}</code> "
                 f"<small>{_e((a.get('sha256') or '')[:16])}</small></td><td>{bericht}</td></tr>\n")
    z.append("</tbody></table>\n")
    if modell["uebernahmen"]:
        z.append("<h2>Uebernahmen</h2>\n<table><thead><tr><th>Fall</th><th>Stichtag</th><th>Vertraege</th>"
                 "<th>A-M4-Snapshot</th><th>Entscheid</th><th>Rolle</th><th>Entscheider</th>"
                 "<th>Schluesselklasse</th><th>Schluessel</th></tr></thead><tbody>\n")
        for u in modell["uebernahmen"]:
            zg = u.get("zeichnung") or {}
            z.append(f"<tr><td>{_e(u['fall'])}</td><td>{_e(u['stichtag'])}</td><td class=\"num\">{u['vertraege']}</td>"
                     f"<td><small>{_e((u.get('snapshot_sha256') or 'nicht erfasst')[:16])}</small></td>"
                     f"<td>{_e(zg.get('entscheid', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('rolle', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('entscheider', 'nicht ausgewiesen'))}</td>"
                     f"<td>{_e(zg.get('schluesselklasse', 'nicht ausgewiesen'))}</td>"
                     f"<td><small>{_e(zg.get('schluessel_sha256', 'nicht ausgewiesen'))}</small></td></tr>\n")
        z.append("</tbody></table>\n<p class=\"fuss\">Angaben der Snapshot-Datei des Falls; "
                 "Signatur hier nicht verifiziert (kein Schluesselring, T19-02).</p>\n")
    z.append(
        f"<p class=\"fuss\">Stand {_e(modell['stand'])} · Wache P-B1: {_e(p.get('pb1'))} · Manifest {_e((p.get('manifest_sha256') or '')[:16])} · "
        f"Config {_e((p.get('config_sha256') or '')[:16])} · Kern {_e(p.get('kern_version'))} · "
        f"Image {_e(p.get('image_tag'))} / {_e(p.get('image_revision'))} / {_e(p.get('image_digest'))}. "
        "Erzeugt aus Protokoll und Tagesjournal des Tagesbetriebs; nichts hier ist gerechnet, alles ist gebucht.</p>\n"
        "</main>\n</body>\n</html>\n"
    )
    return "".join(z)


def _schreibe(ziel: Path, text: str) -> Path:
    ziel.parent.mkdir(parents=True, exist_ok=True)
    tmp = neue_datei(ziel.parent, ziel.name)
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, ziel)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return ziel


def rendere_bestand_heute(ablage, aktuelle_zeile: Optional[Dict[str, Any]] = None) -> Path:
    """``daten/seite/index.html`` aus dem uebernommenen Stand schreiben."""
    modell = stand_modell(ablage, aktuelle_zeile)
    return _schreibe(ablage.wurzel / SEITE_DIR / "index.html", rendere_html(modell))


# --------------------------------------------------------------------------- #
# Stands-Paket
# --------------------------------------------------------------------------- #


def stands_paket(ablage, ziel: Path) -> Path:
    """Den Stand als Paket exportieren: ``stand.json`` plus die Berichte des
    juengsten Abschlusses und die Seite "Bestand heute".

    Das Paket ist die Quelle der Vorzeigeseite (``werkzeuge/falldaten.py
    --stands-paket``). Es traegt seine Provenienz (Manifest-, Config- und
    Journal-Hash, Kern-Version, Image), damit die Seite sagen kann, von
    welchem Stand sie spricht. Ein vorhandenes Paket wird ersetzt — es ist
    eine Momentaufnahme, kein Nachweis; der Nachweis liegt in der Ablage.
    """
    modell = stand_modell(ablage)
    ziel = Path(ziel)
    if ziel.exists():
        shutil.rmtree(ziel)
    ziel.mkdir(parents=True)
    dateien: Dict[str, str] = {}
    for a in modell["abschluesse"][-1:]:
        for name in [a.get("bericht")] + [t["bericht"] for t in a.get("teilbestaende") or []]:
            if not name:
                continue
            quelle = ablage.berichte / name
            if quelle.is_file():
                shutil.copyfile(quelle, ziel / name)
                dateien[name] = sha256_bytes((ziel / name).read_bytes())
    seite = ziel / "index.html"
    _schreibe(seite, rendere_html(modell))
    dateien["index.html"] = sha256_bytes(seite.read_bytes())
    modell["dateien"] = dict(sorted(dateien.items()))
    modell["luecken"] = luecken(modell)
    _schreibe(ziel / PAKET_DATEI, json.dumps(modell, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return ziel


def main(argv: Optional[List[str]] = None) -> int:
    from rechner_pipeline.betrieb.tageslauf import Ablage, TageslaufError

    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.betrieb.seite",
        description="Bestand heute aus dem gefuehrten Stand rendern und als Stands-Paket exportieren.",
    )
    parser.add_argument("--stand", required=True, help="Datenverzeichnis der Laufzeitumgebung.")
    parser.add_argument("--paket", default=None, help="Zielverzeichnis des Stands-Pakets (optional).")
    ns = parser.parse_args(argv)
    ablage = Ablage(Path(ns.stand))
    try:
        seite = rendere_bestand_heute(ablage)
        print(f"seite: {seite}", file=sys.stderr)
        if ns.paket:
            paket = stands_paket(ablage, Path(ns.paket))
            print(f"seite: Stands-Paket -> {paket}", file=sys.stderr)
    except (SeiteError, TageslaufError, ValueError) as exc:
        print(f"seite: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
