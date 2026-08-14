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
from pathlib import Path
from typing import Dict, List, Tuple

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


def _lese_zellen(kalkulation_csv: Path) -> Dict[str, Tuple[str, str]]:
    """Zelladresse -> (Formel, Wert) aus einer Kalkulations-CSV."""
    zellen: Dict[str, Tuple[str, str]] = {}
    with kalkulation_csv.open(encoding="utf-8") as f:
        for zeile in csv.reader(f, delimiter=";"):
            if len(zeile) >= 4 and zeile[0] == "Kalkulation":
                zellen[zeile[1]] = (zeile[2], zeile[3])
    return zellen


def pruefe_ratzu_staffeln(
    fall: Path, generation: str
) -> Tuple[List[str], int]:
    """A-Box-Ratenzuschlaege gegen die IF-Formeln nachpruefen (leer = ok).

    Liest je Tarifart-Spalte der Parameter-Matrix die ratzu-Formel aus
    der Vorverdichtung, parst die Staffel deterministisch und vergleicht
    mit den ``ratzu_zw*``-Aussagen der A-Box-Zellen. Rueckgabe:
    ``(fehler, geprueft)`` — der Zaehler unterscheidet "alles gruen"
    von "nichts war pruefbar" (Generationen mit Festwerten statt
    Staffel-Formeln liefern ``geprueft == 0``; der Aufrufer entscheidet,
    was das bedeutet).
    """
    from rechner_pipeline.ontologie.abox import lade
    from rechner_pipeline.ontologie.aussage import Zustand
    from rechner_pipeline.ontologie.merge import werte_gleich

    gen_name = generation.rsplit("/", 1)[-1].upper()
    csv_pfad = (fall / "abgeleitet" / "vorverdichtung"
                / f"xlsm-{gen_name}" / "Kalkulation.csv")
    if not csv_pfad.is_file():
        return [f"{generation}: Vorverdichtung fehlt ({csv_pfad})"], 0
    zellen = _lese_zellen(csv_pfad)
    abox = lade(fall)
    gen = next((g for g in abox.generationen if g.id == generation), None)
    if gen is None:
        return [f"{generation}: nicht in der A-Box"], 0

    fehler: List[str] = []
    geprueft = 0
    for zelle in gen.zellen:
        for zw, feld in ((2, "ratzu_zw2"), (4, "ratzu_zw4"), (12, "ratzu_zw12")):
            aussage = zelle.parameter.get(feld)
            if aussage is None or aussage.zustand is not Zustand.BELEGT:
                continue
            fundstellen = {
                p.fundstelle.split("!")[-1]
                for p in aussage.provenienz
                if p.fundstelle.startswith("Kalkulation!")
            }
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
                    continue  # Festwert-Zelle: kein Staffel-Check noetig
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
    return fehler, geprueft
