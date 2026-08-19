"""Deterministischer Rueck-Check LLM-extrahierter Formelwerte.

Der Extraktions-Agent liest Staffeln aus Excel-Formeltexten (z. B. die
Ratenzuschlaege je Zahlweise aus verschachtelten IFs). Das ist ein
LLM-Urteil — dieser Modul prueft es deterministisch nach (P4): ein
kleiner Parser fuer die eine Formelform, die vorkommt, fail-fast bei
allem anderen. Kein allgemeiner Excel-Parser; wo die Form nicht passt,
ist das Ergebnis "nicht pruefbar" statt einer stillen Annahme.

Form: ``=IF(var=k1,w1,IF(var=k2,w2,...,default))`` mit numerischen
Schluesseln und Werten wie ``5%``, ``0.05`` oder ``1.5%``.

Knoten: klv
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rechner_pipeline.quellen.vorverdichtung import (
    VorverdichtungFehler,
    VorverdichtungFehlt,
    lies_vorverdichtung,
    verzeichnis_der_generation,
)

_ZWEIG = re.compile(
    r"IF\(\s*(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<schluessel>\d+)\s*,"
    r"\s*(?P<wert>[0-9.]+%?)\s*,",
)
_REST = re.compile(r",\s*(?P<default>[0-9.]+%?)\s*\)+\s*$")


class FormelCheckFehler(ValueError):
    """Formel entspricht nicht der pruefbaren Form (fail-fast)."""


def _zahl(roh: str) -> float:
    try:
        if roh.endswith("%"):
            return float(roh[:-1]) / 100.0
        return float(roh)
    except ValueError as exc:
        raise FormelCheckFehler(f"unparsebarer Zahlwert {roh!r}") from exc


def lese_if_staffel(formel: str, variable: str) -> Tuple[Dict[int, float], float]:
    """Staffel aus einer verschachtelten IF-Formel lesen.

    Rueckgabe: (``{schluessel: wert}``, Default-Wert). Fail-fast, wenn
    die Formel eine andere Variable prueft oder die Form nicht passt.
    """
    # Streng: die Formel MUSS mit der Staffel beginnen — Praefix- oder
    # Wrapper-Formeln (=2*IF(...), =ROUND(IF(...))) wuerden sonst still
    # als reine Staffel gelesen.
    rumpf = formel.lstrip("=").lstrip()
    if not rumpf.startswith("IF("):
        raise FormelCheckFehler(
            f"keine reine IF-Staffel (beginnt nicht mit IF): {formel!r}"
        )
    zweige = list(_ZWEIG.finditer(formel))
    if not zweige:
        raise FormelCheckFehler(
            f"keine IF-Staffel ueber {variable!r} erkennbar: {formel!r}"
        )
    if rumpf.upper().count("IF(") != len(zweige):
        raise FormelCheckFehler(
            f"IF-Zweige nicht vollstaendig parsebar: {formel!r}"
        )
    staffel: Dict[int, float] = {}
    for zweig in zweige:
        if zweig.group("var") != variable:
            raise FormelCheckFehler(
                f"Staffel prueft {zweig.group('var')!r}, erwartet "
                f"{variable!r}: {formel!r}"
            )
        schluessel = int(zweig.group("schluessel"))
        if schluessel in staffel:
            raise FormelCheckFehler(
                f"Schluessel {schluessel} doppelt in {formel!r}"
            )
        staffel[schluessel] = _zahl(zweig.group("wert"))
    rest = _REST.search(formel)
    if rest is None:
        raise FormelCheckFehler(f"kein Default-Zweig erkennbar: {formel!r}")
    return staffel, _zahl(rest.group("default"))


def _lese_zellen(blatt_csv: Path, blattname: str) -> Dict[str, Tuple[str, str]]:
    """Zelladresse -> (Formel, Wert) einer Blatt-CSV der Vorverdichtung."""
    zellen: Dict[str, Tuple[str, str]] = {}
    with blatt_csv.open(encoding="utf-8") as f:
        for zeile in csv.reader(f, delimiter=";"):
            if len(zeile) >= 4 and zeile[0] == blattname:
                zellen[zeile[1]] = (zeile[2], zeile[3])
    return zellen


@dataclass(frozen=True)
class FormelPruefung:
    """Ergebnis des Rueck-Checks fuer EINE Generation.

    ``status`` trennt die Lagen, die frueher alle als ``geprueft == 0``
    bzw. ``nicht_pruefbar`` zusammenfielen und damit unsichtbar waren:

    * ``nicht_pruefbar`` — es gibt keine Vorverdichtung (ehrlich nichts
      nachzurechnen),
    * ``keine_aussagen`` — Vorverdichtung da, aber die A-Box behauptet
      keinen ratzu-Wert (nichts behauptet, nichts zu pruefen),
    * ``geprueft`` — mindestens eine Formel wurde nachgerechnet,
    * ``befund`` — Vorverdichtung UND Aussagen da, aber keine einzige
      war nachrechenbar. Das ist der stille Ausfall, der frueher als
      Null durchlief; der Grund steht in ``befunde`` (nicht
      durchgefuehrt) bzw. in ``fehler`` (harte Verletzung).

    ``fehler`` sind inhaltliche Verletzungen und gehoeren ins Gate als
    Fehler; ``befunde`` sind ausgefallene Pruefungen und gehoeren ins
    Gate als sichtbare Warnung — schweigen darf keine von beiden.
    """

    status: str
    geprueft: int
    fehler: Tuple[str, ...] = ()
    befunde: Tuple[str, ...] = ()
    blatt: Optional[str] = None


def pruefe_ratzu_staffeln(fall: Path, generation: str) -> FormelPruefung:
    """A-Box-Ratenzuschlaege gegen die IF-Formeln nachpruefen.

    Liest je Tarifart-Spalte der Parameter-Matrix die ratzu-Formel aus
    der Vorverdichtung, parst die Staffel deterministisch und vergleicht
    mit den ``ratzu_zw*``-Aussagen der A-Box-Zellen.

    Das Kalkulationsblatt wird aus der Vorverdichtung ERMITTELT
    (:mod:`rechner_pipeline.quellen.vorverdichtung`), nicht angenommen:
    ein hart verdrahteter Blattname liess den Check bei jedem
    Quellsystem ausfallen, das sein Blatt anders nennt — unsichtbar,
    weil das Gate gruen blieb.
    """
    from rechner_pipeline.ontologie.abox import lade
    from rechner_pipeline.ontologie.aussage import Zustand
    from rechner_pipeline.ontologie.merge import werte_gleich

    verzeichnis = verzeichnis_der_generation(fall, generation)
    try:
        vv = lies_vorverdichtung(verzeichnis)
        blatt = vv.kalkulationsblatt
    except VorverdichtungFehlt:
        return FormelPruefung(status="nicht_pruefbar", geprueft=0)
    except VorverdichtungFehler as exc:
        # Vorverdichtung da, aber nicht auswertbar: KEIN stilles
        # nicht_pruefbar — der Aufrufer muss das sehen.
        return FormelPruefung(
            status="befund", geprueft=0, befunde=(f"{generation}: {exc}",)
        )
    zellen = _lese_zellen(blatt.csv, blatt.name)
    abox = lade(fall)
    gen = next((g for g in abox.generationen if g.id == generation), None)
    if gen is None:
        return FormelPruefung(
            status="befund",
            geprueft=0,
            fehler=(f"{generation}: nicht in der A-Box",),
            blatt=blatt.name,
        )

    fehler: List[str] = []
    befunde: List[str] = []
    aussagen = 0
    geprueft = 0
    festwerte = 0
    for zelle in gen.zellen:
        for zw, feld in ((2, "ratzu_zw2"), (4, "ratzu_zw4"), (12, "ratzu_zw12")):
            aussage = zelle.parameter.get(feld)
            if aussage is None or aussage.zustand is not Zustand.BELEGT:
                continue
            aussagen += 1
            praefix = f"{blatt.name}!"
            fundstellen = {
                p.fundstelle.split("!")[-1]
                for p in aussage.provenienz
                if p.fundstelle.startswith(praefix)
            }
            if not fundstellen:
                # Die Aussage belegt sich nicht auf dem Kalkulationsblatt
                # (andere Quelle oder anderes Blatt) — ausgewiesen, damit
                # der ausgefallene Rueck-Check sichtbar bleibt.
                fremde = sorted({p.fundstelle for p in aussage.provenienz})
                befunde.append(
                    f"{gen.id}/{zelle.id}/{feld}: keine Fundstelle auf dem "
                    f"Kalkulationsblatt {blatt.name!r} — belegt mit "
                    f"{fremde}"
                )
                continue
            for adresse in sorted(fundstellen):
                eintrag = zellen.get(adresse)
                if eintrag is None:
                    fehler.append(
                        f"{gen.id}/{zelle.id}/{feld}: Fundstelle "
                        f"{adresse} nicht in der Vorverdichtung"
                    )
                    continue
                formel = eintrag[0]
                if not formel.startswith("="):
                    # Festwert-Zelle: es gibt keine Staffel zu parsen. Das
                    # ist eine erwartbare Form, aber eben AUCH keine
                    # Nachrechnung — gezaehlt, damit "nichts geprueft"
                    # nicht als Erfolg gelesen wird.
                    festwerte += 1
                    continue
                try:
                    staffel, _ = lese_if_staffel(formel, "zw")
                except FormelCheckFehler as exc:
                    fehler.append(f"{gen.id}/{zelle.id}/{feld}: {exc}")
                    continue
                geprueft += 1
                if zw not in staffel:
                    fehler.append(
                        f"{gen.id}/{zelle.id}/{feld}: Formel {adresse} "
                        f"kennt zw={zw} nicht"
                    )
                elif not werte_gleich(staffel[zw], aussage.wert):
                    fehler.append(
                        f"{gen.id}/{zelle.id}/{feld}: Agent las "
                        f"{aussage.wert!r}, Formel {adresse} sagt "
                        f"{staffel[zw]!r}"
                    )

    if geprueft:
        status = "geprueft"
    elif not aussagen:
        status = "keine_aussagen"
    else:
        status = "befund"
        if not befunde:
            befunde.append(
                f"{gen.id}: {aussagen} ratzu-Aussage(n), davon "
                f"{festwerte} auf Festwert-Zellen des Blatts "
                f"{blatt.name!r} — keine Staffel nachrechenbar"
            )
    return FormelPruefung(
        status=status,
        geprueft=geprueft,
        fehler=tuple(fehler),
        befunde=tuple(befunde),
        blatt=blatt.name,
    )
