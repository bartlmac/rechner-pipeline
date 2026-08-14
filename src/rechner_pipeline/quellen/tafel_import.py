"""Deterministischer Tafel-Import: Vorverdichtung -> kern/tafeln.xml.

Traegt die von einer Tarif-Spez angeforderten Sterbetafel-Vektoren aus
der Tafeln-CSV einer Vorverdichtung in die Rechnungsgrundlagen des
Kerns ein und rechnet die Unisex-Ableitungen der Spez aus — die
VBA-Mischformel als einmalige DATEN-Ableitung::

    qx_U = min(1, f * qx_M + (1 - f) * qx_F)    je Alter

Regeln:

* Kein stiller Overwrite (P2): fuehrt der Kern eine angeforderte Tafel
  bereits, muss sie WERTGLEICH sein — sonst harter Konflikt mit beiden
  Quellen in der Meldung. Gleiches gilt fuer Kontrollvektoren, die in
  Quelle und Kern liegen (Provenienz-Kreuzprobe).
* Provenienz je Tafel (P1): Quelldatei + SHA-256 + Fundstellen-Bereich
  bzw. Ableitungsregel als XML-Kommentar direkt an der Tafel.
* Deterministisch: gleiche Eingaben ergeben byte-gleiches XML (neue
  Tafeln alphabetisch sortiert vor ``</tafeln>`` eingefuegt).

Producer-CLI (kein Gate)::

    python -m rechner_pipeline.quellen.tafel_import \\
        --fall faelle/klv-tg2015 --generation klv/tg2015 \\
        [--tafeln-xml src/rechner_pipeline/kern/tafeln.xml] [--dry-run]

Knoten: klv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER


class TafelImportFehler(ValueError):
    """Fachlicher Fehler beim Import (fail-fast, kein stiller Zustand)."""


def lese_tafel_vektoren(tafeln_csv: Path) -> Dict[str, Dict[int, float]]:
    """Alle benannten qx-Vektoren einer Tafeln-CSV (Blatt;Adresse;Formel;Wert).

    Kopfzeile ist Zeile 3 (Vektornamen je Spalte), die Alter stehen in
    Spalte A ab Zeile 4. Luecken sind fail-fast — ein Vektor mit Loch
    ist keine Tafel.
    """
    zellen: Dict[Tuple[str, int], str] = {}
    with tafeln_csv.open(encoding="utf-8") as f:
        for zeile in csv.reader(f, delimiter=";"):
            if len(zeile) < 4 or zeile[0] != "Tafeln":
                continue
            m = re.match(r"^\$([A-Z]+)\$(\d+)$", zeile[1])
            if m:
                zellen[(m.group(1), int(m.group(2)))] = zeile[3]

    spalten = sorted({s for (s, z) in zellen if z == 3 and s != "A"})
    alter_zeilen = sorted(z for (s, z) in zellen if s == "A" and z >= 4)
    vektoren: Dict[str, Dict[int, float]] = {}
    for spalte in spalten:
        name = zellen[(spalte, 3)]
        werte: Dict[int, float] = {}
        for z in alter_zeilen:
            alter = int(float(zellen[("A", z)]))
            roh = zellen.get((spalte, z))
            if roh is None or roh == "":
                raise TafelImportFehler(
                    f"Vektor {name!r}: Alter {alter} (Zeile {z}) ohne Wert — "
                    "eine Tafel mit Loch wird nicht importiert"
                )
            werte[alter] = float(roh)
        vektoren[name] = werte
    return vektoren


def leite_unisex_ab(
    qx_m: Dict[int, float], qx_f: Dict[int, float], maenneranteil: float
) -> Dict[int, float]:
    """Die VBA-Mischformel, einmal ausgerechnet (bit-treu: gleiche Doubles)."""
    if set(qx_m) != set(qx_f):
        raise TafelImportFehler("Unisex-Ableitung: M/F-Altersbereiche ungleich")
    return {
        alter: min(1.0, maenneranteil * qx_m[alter]
                   + (1.0 - maenneranteil) * qx_f[alter])
        for alter in sorted(qx_m)
    }


def _lade_bestehende(tafeln_xml: Path) -> Dict[str, Dict[int, float]]:
    import xml.etree.ElementTree as ET

    root = ET.fromstring(tafeln_xml.read_text(encoding="utf-8"))
    bestehende: Dict[str, Dict[int, float]] = {}
    for table in root.findall("table"):
        name = table.get("name")
        eintraege = {
            int(e.get("age")): float(e.get("qx"))
            for e in table.findall("entry")
            if e.get("dauer") is None
        }
        if eintraege:
            bestehende[name] = eintraege
    return bestehende


def _pruefe_wertgleich(
    name: str, neu: Dict[int, float], vorhanden: Dict[int, float]
) -> List[str]:
    fehler = []
    gemeinsame = sorted(set(neu) & set(vorhanden))
    for alter in gemeinsame:
        if neu[alter] != vorhanden[alter]:
            fehler.append(
                f"Tafel {name!r}, Alter {alter}: Quelle {neu[alter]!r} != "
                f"Kern {vorhanden[alter]!r} — kein stiller Overwrite; erst "
                "die Provenienz klaeren"
            )
    return fehler


def _qx_repr(wert: float) -> str:
    return repr(wert)


def fuege_tafeln_ein(
    tafeln_xml: Path,
    neue: Dict[str, Dict[int, float]],
    provenienz: Dict[str, str],
) -> List[str]:
    """Neue Tafeln deterministisch einfuegen; Rueckgabe = eingefuegte Namen.

    Textbasiertes Einfuegen vor ``</tafeln>`` (kein Re-Serialisieren des
    Bestands — bestehende Zeilen bleiben byte-identisch, der Diff zeigt
    nur die Ergaenzung).
    """
    bestehende = _lade_bestehende(tafeln_xml)
    konflikte: List[str] = []
    einzufuegen: Dict[str, Dict[int, float]] = {}
    for name in sorted(neue):
        if name in bestehende:
            konflikte.extend(_pruefe_wertgleich(name, neue[name], bestehende[name]))
            continue  # wertgleich vorhanden: nichts zu tun
        einzufuegen[name] = neue[name]
    if konflikte:
        raise TafelImportFehler("; ".join(konflikte[:5]))

    if not einzufuegen:
        return []
    text = tafeln_xml.read_text(encoding="utf-8")
    schluss = "</tafeln>"
    if schluss not in text:
        raise TafelImportFehler(f"{tafeln_xml}: kein {schluss}-Schluss gefunden")
    bloecke: List[str] = []
    for name in sorted(einzufuegen):
        zeilen = [f"  <!-- {provenienz[name]} -->", f'  <table name="{name}">']
        for alter in sorted(einzufuegen[name]):
            zeilen.append(
                f'    <entry age="{alter}" qx="{_qx_repr(einzufuegen[name][alter])}" />'
            )
        zeilen.append("  </table>")
        bloecke.append("\n".join(zeilen))
    text = text.replace(schluss, "\n".join(bloecke) + "\n" + schluss, 1)
    tafeln_xml.write_text(text, encoding="utf-8")
    return sorted(einzufuegen)


def importiere_fuer_spez(
    fall: Path,
    generation: str,
    tafeln_xml: Path,
    dry_run: bool = False,
) -> Dict[str, object]:
    """Tafel-Importe und -Ableitungen einer Spez anwenden."""
    from rechner_pipeline.spez.validierung import lade_spez

    spez = lade_spez(fall, generation)
    gen_name = generation.rsplit("/", 1)[-1].upper()
    quelle_datei = f"Tarifrechner_KLV_{gen_name}.xlsm"
    tafeln_csv = (
        fall / "abgeleitet" / "vorverdichtung" / f"xlsm-{gen_name}" / "Tafeln.csv"
    )
    if not tafeln_csv.is_file():
        raise TafelImportFehler(f"Vorverdichtung fehlt: {tafeln_csv}")
    register = json.loads((fall / "eingang.json").read_text(encoding="utf-8"))
    sha = {q["datei"]: q["sha256"] for q in register.get("quellen", [])}.get(
        quelle_datei
    )
    if sha is None:
        raise TafelImportFehler(
            f"{quelle_datei!r} nicht im Eingang-Register — Import nur aus "
            "registrierten Quellen (P1)"
        )

    vektoren = lese_tafel_vektoren(tafeln_csv)
    neue: Dict[str, Dict[int, float]] = {}
    provenienz: Dict[str, str] = {}
    for name in spez.tafel_importe:
        if name not in vektoren:
            raise TafelImportFehler(
                f"Spez verlangt Tafel {name!r}, die Vorverdichtung "
                f"({tafeln_csv.name}) kennt sie nicht "
                f"(vorhanden: {sorted(vektoren)})"
            )
        neue[name] = vektoren[name]
        provenienz[name] = (
            f"Provenienz: {quelle_datei} (sha256 {sha[:16]}...), "
            f"Blatt Tafeln, Vektor {name}; importiert via "
            "quellen.tafel_import"
        )
    for ableitung in spez.tafel_ableitungen:
        qx_m = neue.get(ableitung.basis_m) or vektoren.get(ableitung.basis_m)
        qx_f = neue.get(ableitung.basis_f) or vektoren.get(ableitung.basis_f)
        if qx_m is None or qx_f is None:
            raise TafelImportFehler(
                f"Ableitung {ableitung.name!r}: Basis {ableitung.basis_m!r}/"
                f"{ableitung.basis_f!r} nicht verfuegbar"
            )
        neue[ableitung.name] = leite_unisex_ab(
            qx_m, qx_f, ableitung.maenneranteil
        )
        provenienz[ableitung.name] = (
            f"Abgeleitet: min(1, {ableitung.maenneranteil}*qx[{ableitung.basis_m}] "
            f"+ {1.0 - ableitung.maenneranteil}*qx[{ableitung.basis_f}]) je Alter "
            f"(VBA-Mischformel {spez.unisex}); Basen aus {quelle_datei} "
            f"(sha256 {sha[:16]}...); abgeleitet via quellen.tafel_import"
        )

    # Kreuzprobe: Vektoren, die Quelle UND Kern fuehren, muessen wertgleich
    # sein — auch wenn die Spez sie nicht anfordert (stiller Drift der
    # Rechnungsgrundlagen zwischen Generationen waere sonst unsichtbar).
    bestehende = _lade_bestehende(tafeln_xml)
    kreuzprobe = sorted(set(vektoren) & set(bestehende))
    konflikte: List[str] = []
    for name in kreuzprobe:
        konflikte.extend(_pruefe_wertgleich(name, vektoren[name], bestehende[name]))
    if konflikte:
        raise TafelImportFehler("; ".join(konflikte[:5]))

    if dry_run:
        eingefuegt: List[str] = []
    else:
        eingefuegt = fuege_tafeln_ein(tafeln_xml, neue, provenienz)
    return {
        "generation": generation,
        "quelle": quelle_datei,
        "angefordert": sorted(neue),
        "eingefuegt": eingefuegt,
        "bereits_vorhanden_wertgleich": sorted(set(neue) & set(bestehende)),
        "kreuzprobe_wertgleich": kreuzprobe,
        "tafeln_xml": str(tafeln_xml),
        "dry_run": dry_run,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m rechner_pipeline.quellen.tafel_import",
        description="Tafel-Vektoren einer Spez in kern/tafeln.xml eintragen.",
    )
    parser.add_argument("--fall", required=True)
    parser.add_argument("--generation", required=True, help="z. B. klv/tg2015")
    parser.add_argument(
        "--tafeln-xml",
        default="src/rechner_pipeline/kern/tafeln.xml",
        help="Ziel-XML (Default: die Paket-Rechnungsgrundlagen).",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        ergebnis = importiere_fuer_spez(
            Path(args.fall), args.generation, Path(args.tafeln_xml),
            dry_run=args.dry_run,
        )
    except TafelImportFehler as exc:
        print(f"tafel_import: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
