"""``bereinigung`` — Hostpfade aus den veroeffentlichten Belegen, als Stufe im
Bau der Seite (Entscheid des Maintainers, 03.10.2026).

Es gibt zwei Wege der Veroeffentlichung: den Code (die wiederherstellbare
Routine) und die Vorzeige (die Webseite mit den Artefakten eines Falls).
Diese Stufe betrifft nur den zweiten. Die Belege eines Laufs tragen, was
ihre Kommandos gesehen haben — auch die absoluten Pfade des Rechners, auf
dem sie liefen: den Arbeitsbaum, die Laufzeitumgebung, das Verzeichnis des
Schluesselmaterials. Die Belege eines Falls bleiben, wie sie sind; die
Behebung im Produzenten (Pfade relativ, ein Herkunftsfeld beim
Registrieren) ist Arbeit fuer den naechsten Lauf. Bereinigt wird deshalb
nur die veroeffentlichte Fassung:

* Regel statt Handarbeit: Jeder Hostpfad, den eine Regel kennt, wird durch
  einen benannten Platzhalter ersetzt (:func:`regeln`) — deterministisch,
  dieselben Bytes ergeben dieselbe Fassung. Bereinigt wird nur Text; traegt
  eine andere Datei einen Hostpfad, haelt der Bau an.
* Ein Entscheid-Snapshot wird nie bereinigt: Eine Aenderung braeche seine
  Signatur und die Verweise der Folgeentscheide. Traegt ein UEBERHOLTER
  Snapshot etwas, das nicht auf die Seite gehoert, bleibt er unveroeffentlicht
  und steht benannt da; traegt es ein geltender oder einer, den das Modell
  nicht kennt, haelt der Bau an — das entscheidet ein Mensch
  (:func:`snapshot_urteil`).
* Das Manifest (``artefakte/bereinigung.json``) nennt je bereinigter Datei
  die Pruefsumme des Originals im Fall, die Entscheide, die dieses Original
  ueber seine Pruefsumme binden (oft keiner: die Protokolle der Zeichnungen
  entstehen mit der Zeichnung), die Pruefsumme der veroeffentlichten Fassung
  und die Ersetzungen je Regel; je zurueckgehaltener Datei ihre Pruefsumme.
  Alle uebrigen Belege unter ``artefakte/`` sind bytegleich mit ihren
  Originalen im Fall; die Ansichten der Lieferung sind Ansichten (eine CSV
  als Vorschau ihrer ersten Zeilen).
* Die Wache (:func:`wache`) liest nach dem Bau jede veroeffentlichte Datei —
  Namen, Bytes und, wo die Seite komprimiert veroeffentlicht, den entpackten
  Inhalt (Parquet, die Stroeme eines PDF): kein Hostpfad (:data:`MARKEN`),
  kein Wort aus :data:`WORTE`. Was keine Regel kennt, wird nicht still
  ersetzt, sondern haelt den Bau an.

Nachpruefen, mit dem Fall in der Hand, aus dem Baum, in dem er liegt::

    python werkzeuge/bereinigung.py --pruefe <seite>/migrationen/<name> --fall faelle/<fall>
    python werkzeuge/bereinigung.py --wache <seite>

Grenzen: Die Wache kennt die Schreibweisen in :data:`MARKEN` — eine Kurzform
wie ``~/``, UTF-16 oder Base64 sieht sie nicht, und die Wortliste faengt nur,
was sie kennt. Ein privater Termin in anderer Formulierung bleibt Sache der
Durchsicht von Hand vor der Veroeffentlichung.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

#: Was nach dem Bau in keiner veroeffentlichten Datei stehen darf: Pfade
#: eines Heimatverzeichnisses und der Arbeitsverzeichnisse der Agenten, auch
#: JSON-maskiert, auf Windows und macOS, und als Name eines Projektordners
#: (``-home-<benutzer>-...``). Gemessen 03.10.2026: keine dieser Marken steht
#: in den Quellen des Auftritts oder in der Fallseite von Fall 3.
MARKEN: Tuple[bytes, ...] = (
    b"/home/", b"/tmp/claude", b"\\/home\\/", b"\\/tmp\\/claude",
    b"/Users/", b"C:\\Users\\", b"C:\\\\Users\\\\", b"-home-")

#: Woerter, die nicht auf die Seite gehoeren — ohne Ruecksicht auf Gross-
#: und Kleinschreibung. Die zweite Schreibweise steht so in einem
#: ueberholten Snapshot von Fall 3.
WORTE: Tuple[str, ...] = ("workshop", "worskhop")

#: Dateien, deren Bytes Text sind und die eine Regel deshalb bereinigen
#: darf, ohne ein Format zu zerbrechen.
TEXT_ENDUNGEN = (".json", ".jsonl", ".md", ".txt", ".csv", ".html", ".yml", ".yaml", ".toml")

#: Ein Zeichen, das einen Pfadnamen fortsetzt — eine Regel ersetzt nur bis
#: zur Grenze eines Namens, nie in einen laengeren Namen hinein.
_NAME = rb"[A-Za-z0-9_.\-]"

MANIFEST = "bereinigung.json"


def regeln(fall: Path) -> List[Tuple[str, str, "re.Pattern[bytes]"]]:
    """Die Regeln fuer die Belege eines Falls, in dieser Reihenfolge.

    ``<baum>`` — der Arbeitsbaum, in dem der Fall liegt (``<baum>/faelle/
    <fall>``), erhoben aus dem Pfad des Falls beim Bau; nur, wenn der Fall
    dort liegt, wo Faelle liegen.
    ``<schluesselverzeichnis>`` — das Verzeichnis des Schluesselmaterials
    im Heimatverzeichnis (``~/.rechner-pipeline-schluessel``).
    ``<welt>`` — die Laufzeitumgebung (``~/apps/<welt>``, deploy/plv/README.md).
    ``<laufordner>`` — ein Laufverzeichnis ausserhalb des Falls
    (``~/git/<baum>/runs/<ordner>``): dort liegen Stands-Paket und Anker, und
    das Protokoll der Auslieferungsabnahme nennt den Anker mit vollem Pfad
    (Fall 3, A-B1 vom 06.10.2026). Nach ``<baum>``, damit das Laufverzeichnis
    des eigenen Baums nicht zweimal benannt wird.
    """
    aus: List[Tuple[str, str, "re.Pattern[bytes]"]] = []
    ort = fall.resolve()
    if ort.parent.name == "faelle":
        baum = str(ort.parents[1]).encode("utf-8")
        aus.append(("<baum>", "den Arbeitsbaum, in dem der Fall liegt",
                    re.compile(re.escape(baum) + rb"(?!" + _NAME + rb")")))
    aus.append(("<schluesselverzeichnis>", "das Verzeichnis des Schlüsselmaterials",
                re.compile(rb"/home/" + _NAME + rb"+/\.rechner-pipeline-schluessel(?!" + _NAME + rb")")))
    aus.append(("<welt>", "die Laufzeitumgebung",
                re.compile(rb"/home/" + _NAME + rb"+/apps/" + _NAME + rb"+")))
    aus.append(("<laufordner>", "ein Laufverzeichnis außerhalb des Falls (Stands-Paket, Anker)",
                re.compile(rb"/home/" + _NAME + rb"+/git/" + _NAME + rb"+/runs/" + _NAME + rb"+")))
    return aus


def bereinige(daten: bytes, regelsatz: List[Tuple[str, str, "re.Pattern[bytes]"]]
              ) -> Tuple[bytes, Dict[str, int]]:
    """Jede Regel in ihrer Reihenfolge anwenden; dazu je Regel die Zahl der
    Ersetzungen (nur Regeln, die griffen)."""
    ersetzt: Dict[str, int] = {}
    for platzhalter, _, muster in regelsatz:
        daten, n = muster.subn(platzhalter.encode("utf-8"), daten)
        if n:
            ersetzt[platzhalter] = n
    return daten, ersetzt


def befunde(daten: bytes) -> List[str]:
    """Was in diesen Bytes nicht auf die Seite gehoert."""
    gefunden = [m.decode("ascii") for m in MARKEN if m in daten]
    klein = daten.lower()
    gefunden += [w for w in WORTE if w.encode("ascii") in klein]
    return gefunden


def ist_text(rel: str) -> bool:
    return rel.lower().endswith(TEXT_ENDUNGEN)


def snapshot_urteil(rel: str, daten: bytes,
                    entscheid: Optional[Dict[str, Any]]) -> Optional[str]:
    """Darf dieser Entscheid-Snapshot auf die Seite?

    ``None``: ja, unveraendert. ``"zurueckhalten"``: nein — er ist
    ueberholt und traegt etwas, das nicht auf die Seite gehoert. Ein
    geltender oder unbekannter Snapshot mit Befund ist ein ``ValueError``:
    Er wird nie bereinigt, und ob er fehlen darf, entscheidet ein Mensch.
    """
    funde = befunde(daten)
    if not funde:
        return None
    if entscheid and not (entscheid.get("geltend") or entscheid.get("in_finaler_kette")):
        return "zurueckhalten"
    raise ValueError(
        f"{rel}: {'geltender' if entscheid else 'unbekannter'} Entscheid-Snapshot traegt "
        f"{', '.join(funde)} — ein Snapshot wird nie bereinigt (seine Signatur), und ob er "
        "auf der Seite fehlen darf, entscheidet ein Mensch")


def bindung(knoten: Dict[str, Any]) -> List[str]:
    """Die Entscheide, die eine Datei der Belegkette ueber ihre Pruefsumme
    binden — als Artefakt oder als Pflichtbeleg."""
    return sorted(set(knoten.get("gebunden_von") or [])
                  | {str(g) for g, _ in knoten.get("rollen") or []})


def manifest(bereinigt: List[Dict[str, Any]], zurueckgehalten: List[Dict[str, Any]],
             regelsatz: List[Tuple[str, str, "re.Pattern[bytes]"]]) -> bytes:
    """Das Bereinigungsmanifest — ohne Zeitstempel, sortiert, damit derselbe
    Fall dieselben Bytes ergibt (drift.py vergleicht sie)."""
    return (json.dumps({
        "schema_version": 2,
        "zweck": ("Hostpfade der Belege sind in der veröffentlichten Fassung durch "
                  "benannte Platzhalter ersetzt. Je Datei: die Prüfsumme des Originals im "
                  "Fall, die Entscheide, die dieses Original über seine Prüfsumme binden "
                  "(leer: keiner), die Prüfsumme der veröffentlichten Fassung und die "
                  "Ersetzungen je Regel. Alle übrigen Belege unter artefakte/ sind bytegleich "
                  "mit ihren Originalen im Fall; die Ansichten der Lieferung "
                  "(artefakte/lieferung/) sind Ansichten — eine CSV als Vorschau ihrer "
                  "ersten Zeilen, alles Übrige bytegleich."),
        "regeln": [{"platzhalter": p, "steht_fuer": b} for p, b, _ in regelsatz],
        "bereinigt": sorted(bereinigt, key=lambda e: e["datei"]),
        "zurueckgehalten": sorted(zurueckgehalten, key=lambda e: e["original"]),
    }, ensure_ascii=False, indent=1, sort_keys=True) + "\n").encode("utf-8")


def _entpackt(pfad: Path, daten: bytes) -> Tuple[bytes, Optional[str]]:
    """Was eine Datei komprimiert traegt, als Bytes — fuer die Formate, die die
    Seite komprimiert veroeffentlicht: Parquet (Schema, Metadaten, jede Spalte
    ausser Zahlen und Zeiten) und die Flate-Stroeme eines PDF. Zurueck die
    Bytes und, wenn die Datei nicht lesbar ist, der Grund — eine Wache, die
    eine Datei nicht lesen kann, hat einen Befund, kein Urteil."""
    endung = pfad.suffix.lower()
    if endung == ".parquet":
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
            tabelle = pq.read_table(pfad)
        except Exception as exc:  # pyarrow fehlt oder die Datei ist kaputt
            return b"", f"Parquet nicht lesbar ({type(exc).__name__})"
        teile = [str(tabelle.schema).encode("utf-8"),
                 repr(tabelle.schema.metadata).encode("utf-8")]
        for spalte in tabelle.columns:
            t = spalte.type
            if (pa.types.is_integer(t) or pa.types.is_floating(t) or pa.types.is_boolean(t)
                    or pa.types.is_temporal(t) or pa.types.is_decimal(t)):
                continue
            teile.append(repr(spalte.to_pylist()).encode("utf-8"))
        return b"\n".join(teile), None
    if endung == ".pdf":
        teile = []
        for strom in re.findall(rb"stream\r?\n(.*?)\r?\nendstream", daten, re.S):
            try:
                teile.append(zlib.decompress(strom))
            except zlib.error:
                continue
        return b"\n".join(teile), None
    return b"", None


def wache(verzeichnis: Path) -> List[Tuple[str, str]]:
    """Jede Datei unter ``verzeichnis`` lesen — Name, Bytes, entpackter Inhalt;
    je Befund (Datei, Marke)."""
    aus: List[Tuple[str, str]] = []
    for pfad in sorted(p for p in verzeichnis.rglob("*") if p.is_file()):
        rel = pfad.relative_to(verzeichnis).as_posix()
        daten = pfad.read_bytes()
        entpackt, fehler = _entpackt(pfad, daten)
        if fehler:
            aus.append((rel, fehler))
        aus += [(rel, f) for f in dict.fromkeys(
            befunde(rel.encode("utf-8") + b"\n" + daten + b"\n" + entpackt))]
    return aus


def _gegenstueck(fall: Path, rel: str) -> Tuple[Optional[Path], bool]:
    """Wo eine Datei unter ``artefakte/`` im Fall herkommt, und ob sie eine
    Vorschau ist: ``lieferung/`` sind Ansichten des Eingangs (CSV als
    ``.html``-Vorschau, Markdown als ``.md.txt``), alles andere liegt im Fall
    unter demselben Pfad (Markdown als ``.md.txt``)."""
    if rel.startswith("lieferung/"):
        name = rel[len("lieferung/"):]
        if name.lower().endswith(".csv.html"):
            return fall / "eingang" / name[:-len(".html")], True
        if name.endswith(".md.txt"):
            return fall / "eingang" / name[:-len(".txt")], False
        return fall / "eingang" / name, False
    return fall / (rel[:-len(".txt")] if rel.endswith(".md.txt") else rel), False


def pruefe(seite: Path, fall: Path) -> List[str]:
    """Eine gebaute Fallseite gegen den Fall nachrechnen.

    * Je bereinigter Datei: Das Original im Fall hat die genannte Pruefsumme
      und die genannten Bindungen; die Regeln ergeben daraus die
      veroeffentlichte Fassung mit denselben Ersetzungszahlen; die Datei auf
      der Seite hat deren Pruefsumme.
    * Je zurueckgehaltener Datei: Sie liegt mit ihrer Pruefsumme im Fall und
      unter KEINEM Namen auf der Seite.
    * Jede andere Datei unter ``artefakte/`` hat ein Gegenstueck im Fall und
      ist bytegleich mit ihm; eine Vorschau der Lieferung wird neu erzeugt
      und verglichen. Eine Datei ohne Gegenstueck ist ein Befund.
    * Vollstaendig: Jeder Beleg, den die Belegkette einer Station zuordnet,
      liegt auf der Seite — ausser dem Eingang (er kommt als Ansicht) und
      dem Zurueckgehaltenen.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import falldaten  # Nachbarwerkzeug: dieselbe Belegkette wie beim Bau

    def sha(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    fehler: List[str] = []
    artefakte = seite / "artefakte"
    m = json.loads((artefakte / MANIFEST).read_text(encoding="utf-8"))
    kette = falldaten.belegkette(fall)["dateien"]
    regelsatz = regeln(fall)
    bereinigte = set()
    for e in m.get("bereinigt") or []:
        original, veroeffentlicht = fall / e["original"], seite / e["datei"]
        bereinigte.add(e["datei"])
        if sha(original) != e["sha256_original"]:
            fehler.append(f"{e['original']}: Original hat nicht die genannte Pruefsumme")
        if bindung(kette.get(e["original"]) or {}) != e.get("gebunden_von"):
            fehler.append(f"{e['original']}: die genannten Bindungen stimmen nicht mit der Belegkette")
        neu, ersetzt = bereinige(original.read_bytes(), regelsatz)
        if hashlib.sha256(neu).hexdigest() != e["sha256_veroeffentlicht"]:
            fehler.append(f"{e['datei']}: die Regeln ergeben nicht die veroeffentlichte Fassung")
        if ersetzt != e.get("ersetzungen"):
            fehler.append(f"{e['datei']}: die Ersetzungszahlen weichen ab ({ersetzt} gegen "
                          f"{e.get('ersetzungen')})")
        if not veroeffentlicht.is_file() or sha(veroeffentlicht) != e["sha256_veroeffentlicht"]:
            fehler.append(f"{e['datei']}: veroeffentlichte Datei weicht vom Manifest ab")
    zurueck = {e["sha256"]: e["original"] for e in m.get("zurueckgehalten") or []}
    for e in m.get("zurueckgehalten") or []:
        if sha(fall / e["original"]) != e["sha256"]:
            fehler.append(f"{e['original']}: zurueckgehaltene Datei hat nicht die genannte Pruefsumme")
    for pfad in sorted(p for p in artefakte.rglob("*") if p.is_file()):
        rel = pfad.relative_to(seite).as_posix()
        if sha(pfad) in zurueck:
            fehler.append(f"{rel}: traegt die Bytes der zurueckgehaltenen Datei "
                          f"{zurueck[sha(pfad)]}")
        if rel in bereinigte or rel == f"artefakte/{MANIFEST}":
            continue
        quelle, vorschau = _gegenstueck(fall, rel[len("artefakte/"):])
        if quelle is None or not quelle.is_file():
            fehler.append(f"{rel}: liegt auf der Seite, hat aber kein Gegenstueck im Fall")
        elif vorschau:
            import vorzeigeseite  # dieselbe Vorschau wie beim Bau
            if vorzeigeseite._csv_vorschau(quelle).encode("utf-8") != pfad.read_bytes():
                fehler.append(f"{rel}: die Vorschau entspricht nicht der Lieferung")
        elif sha(quelle) != sha(pfad):
            fehler.append(f"{rel}: nicht im Manifest, aber nicht bytegleich mit dem Fall")
    zurueck_rel = set(zurueck.values())
    for f, k in sorted(kette.items()):
        if not k.get("station") or f.startswith("eingang/") or f in zurueck_rel:
            continue
        if not (artefakte / (f + ".txt" if f.endswith(".md") else f)).is_file():
            fehler.append(f"{f}: Beleg der Station {k['station']} fehlt auf der Seite")
    return fehler


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(prog="python werkzeuge/bereinigung.py",
                                description="Veroeffentlichte Belege bewachen und nachpruefen.")
    p.add_argument("--wache", default=None, help="gebauter Seitenbaum: jede Datei lesen")
    p.add_argument("--pruefe", default=None, help="gebaute Fallseite (migrationen/<name>)")
    p.add_argument("--fall", default=None, help="Fall-Arbeitsbereich (mit --pruefe)")
    args = p.parse_args(argv)
    if not (args.wache or args.pruefe):
        p.error("--wache oder --pruefe")
    rc = 0
    if args.wache:
        ziel = Path(args.wache)
        funde = wache(ziel)
        for rel, marke in funde:
            print(f"WACHE: {rel} traegt {marke!r}", file=sys.stderr)
        if funde:
            print(f"ABBRUCH: {len(funde)} Befund(e) der Wache in {ziel} — nicht "
                  "veroeffentlichen; eine Regel ergaenzen oder die Datei zurueckhalten.",
                  file=sys.stderr)
            rc = 1
        else:
            print(f"Wache: {sum(1 for x in ziel.rglob('*') if x.is_file())} Dateien gelesen, "
                  "kein Hostpfad, kein gesperrtes Wort.")
    if args.pruefe:
        if not args.fall:
            p.error("--pruefe braucht --fall")
        fehler = pruefe(Path(args.pruefe), Path(args.fall))
        for f in fehler:
            print(f"PRUEFUNG: {f}", file=sys.stderr)
        if fehler:
            rc = 1
        else:
            print("Nachgerechnet: Originale mit den genannten Pruefsummen und Bindungen, die "
                  "Regeln ergeben die veroeffentlichte Fassung, alle uebrigen Belege bytegleich, "
                  "die Vorschauen der Lieferung nachgebaut, nichts Zurueckgehaltenes auf der "
                  "Seite, keine Datei ohne Gegenstueck, kein Beleg der Kette fehlt.")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
