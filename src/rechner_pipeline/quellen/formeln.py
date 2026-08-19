"""Deterministischer Rueck-Check LLM-extrahierter Formelwerte.

Der Extraktions-Agent liest Staffeln aus Excel-Formeltexten (z. B. die
Ratenzuschlaege je Zahlweise aus verschachtelten IFs). Das ist ein
LLM-Urteil — dieser Modul prueft es deterministisch nach (P4): ein
kleiner Parser fuer die eine Formelform, die vorkommt, fail-fast bei
allem anderen. Kein allgemeiner Excel-Parser; wo die Form nicht passt,
ist das Ergebnis ein benannter Zustand statt einer stillen Annahme —
und jeder Zustand, in dem NICHTS nachgerechnet wurde, sagt warum.

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
    zusammenfielen und damit unsichtbar waren:

    * ``keine_vorverdichtung`` — es gibt keine Vorverdichtung. Nichts
      nachzurechnen, aber NICHT dasselbe wie "nichts zu pruefen": der
      Rueck-Check faellt hier komplett aus, und das muss man sehen
      (:attr:`hinweise` traegt das Kommando, das die Vorverdichtung
      erzeugt),
    * ``keine_aussagen`` — Vorverdichtung da, aber die A-Box behauptet
      keinen ratzu-Wert, der sich auf den Tarifrechner beruft (nichts
      behauptet, nichts zu pruefen),
    * ``geprueft`` — mindestens eine Formel wurde nachgerechnet,
    * ``befund`` — Vorverdichtung UND Rechner-Aussagen da, aber keine
      einzige war nachrechenbar. Das ist der stille Ausfall, der frueher
      als Null durchlief; der Grund steht in ``befunde`` (nicht
      durchgefuehrt) bzw. in ``fehler`` (harte Verletzung).

    ``fehler`` sind inhaltliche Verletzungen und gehoeren ins Gate als
    Fehler; ``befunde`` sind einzelne ausgefallene Pruefungen,
    ``hinweise`` ist der als Ganzes ausgefallene Check — beide gehoeren
    ins Gate als sichtbare Warnung. Schweigen darf keine der drei.

    ``ausserhalb`` zaehlt Aussagen, die sich NICHT auf den Tarifrechner
    berufen (rein aus der Tarifmeldung belegt). Sie sind belegt, nur
    eben nicht hier nachrechenbar — eine Zaehlung, kein Befund.
    """

    status: str
    geprueft: int
    fehler: Tuple[str, ...] = ()
    befunde: Tuple[str, ...] = ()
    hinweise: Tuple[str, ...] = ()
    ausserhalb: int = 0
    blatt: Optional[str] = None


def _hinweis_ohne_vorverdichtung(
    fall: Path, generation: str, verzeichnis: Path, rechner_dateien: List[str]
) -> str:
    """Meldung fuer den Zustand "gar keine Vorverdichtung".

    Fail-fast-Idiom: die Meldung nennt den Ausweg. Gibt es genau eine
    registrierte Rechner-Quelle, steht das vollstaendige extract-Kommando
    da; sonst bleibt die Datei ein Platzhalter, weil WELCHER Rechner
    verdichtet werden soll dann eine fachliche Auswahl ist.
    """
    kopf = (
        f"{generation}: keine Vorverdichtung unter {verzeichnis} — der "
        "Rueck-Check der Formel-Staffeln faellt vollstaendig aus"
    )
    if not rechner_dateien:
        return (
            f"{kopf}; die Generation nennt ueberdies keine Quelle der Art "
            "'tarifrechner' (synthetische A-Box?) — ohne Quellrechner "
            "kann kein Formelwert nachgerechnet werden"
        )
    if len(rechner_dateien) == 1:
        datei = rechner_dateien[0]
    else:
        datei = "<rechner-datei>"
        kopf += f" (registrierte Rechner-Quellen: {rechner_dateien})"
    return (
        f"{kopf}; erzeugen mit: python -m rechner_pipeline.gates.extract "
        f"--repo-root . --input {fall}/eingang/{datei} "
        f"--out-dir {verzeichnis} --adapter excel"
    )


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

    Zustaendig ist der Check ausschliesslich fuer Aussagen, die sich auf
    eine Quelle der Art ``tarifrechner`` berufen. Eine nur aus der
    Tarifmeldung belegte Aussage ist belegt, aber hier nicht
    nachrechenbar — sie wird gezaehlt (``ausserhalb``), nicht bemaengelt.
    """
    from rechner_pipeline.ontologie.abox import lade
    from rechner_pipeline.ontologie.aussage import Zustand
    from rechner_pipeline.ontologie.merge import werte_gleich

    verzeichnis = verzeichnis_der_generation(fall, generation)
    abox = lade(fall)
    gen = next((g for g in abox.generationen if g.id == generation), None)
    if gen is None:
        return FormelPruefung(
            status="befund",
            geprueft=0,
            fehler=(f"{generation}: nicht in der A-Box",),
        )
    # Nachrechenbar ist nur, was der TARIFRECHNER behauptet — die
    # Vorverdichtung ist seine Verdichtung. Welche Quellen das sind,
    # sagt die A-Box selbst (Quelle.art), es wird nicht geraten.
    rechner_dateien = {q.datei for q in gen.quellen if q.art == "tarifrechner"}

    try:
        vv = lies_vorverdichtung(verzeichnis)
        blatt = vv.kalkulationsblatt
    except VorverdichtungFehlt:
        # Gar keine Vorverdichtung: nichts nachgerechnet, aber das ist
        # ein AUSFALL des Checks und kein "es gab nichts zu pruefen" —
        # als Hinweis mit Ausweg sichtbar (Review-Befund C6).
        return FormelPruefung(
            status="keine_vorverdichtung",
            geprueft=0,
            hinweise=(
                _hinweis_ohne_vorverdichtung(
                    fall, generation, verzeichnis, sorted(rechner_dateien)
                ),
            ),
        )
    except VorverdichtungFehler as exc:
        # Vorverdichtung da, aber nicht auswertbar: KEIN stilles
        # "nichts zu pruefen" — der Aufrufer muss das sehen.
        return FormelPruefung(
            status="befund", geprueft=0, befunde=(f"{generation}: {exc}",)
        )
    zellen = _lese_zellen(blatt.csv, blatt.name)

    fehler: List[str] = []
    befunde: List[str] = []
    aussagen = 0
    geprueft = 0
    festwerte = 0
    ausserhalb = 0
    for zelle in gen.zellen:
        for zw, feld in ((2, "ratzu_zw2"), (4, "ratzu_zw4"), (12, "ratzu_zw12")):
            aussage = zelle.parameter.get(feld)
            if aussage is None or aussage.zustand is not Zustand.BELEGT:
                continue
            rechner_belege = [
                p for p in aussage.provenienz
                if p.quelle_datei in rechner_dateien
            ]
            if not rechner_belege:
                # Rein aus der Tarifmeldung belegt: die Aussage ist
                # belegt, nur nicht im Rechner. Der Rueck-Check kann sie
                # nicht nachrechnen, aber sie ist kein Befund — das waere
                # ein Falsch-Positiv gegen einen fachlich korrekten Fall
                # (Review-Befund C7). Nur gezaehlt.
                ausserhalb += 1
                continue
            aussagen += 1
            praefix = f"{blatt.name}!"
            fundstellen = {
                p.fundstelle.split("!")[-1]
                for p in rechner_belege
                if p.fundstelle.startswith(praefix)
            }
            if not fundstellen:
                # Im Rechner belegt, aber auf einem anderen Blatt als dem
                # ermittelten Kalkulationsblatt: hier faellt eine
                # MOEGLICHE Nachrechnung aus — ausgewiesen.
                fremde = sorted({p.fundstelle for p in rechner_belege})
                befunde.append(
                    f"{gen.id}/{zelle.id}/{feld}: im Tarifrechner belegt, "
                    f"aber keine Fundstelle auf dem ermittelten "
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
                f"{gen.id}: {aussagen} ratzu-Aussage(n) aus dem "
                f"Tarifrechner, davon {festwerte} auf Festwert-Zellen des "
                f"Blatts {blatt.name!r} — keine Staffel nachrechenbar"
            )
    return FormelPruefung(
        status=status,
        geprueft=geprueft,
        fehler=tuple(fehler),
        befunde=tuple(befunde),
        ausserhalb=ausserhalb,
        blatt=blatt.name,
    )
