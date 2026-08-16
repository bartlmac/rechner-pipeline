"""Toleranz-Überleitung zweier Rechenrückgrate (Kreuz-Modell-Gate).

Zwei unabhängige Rechenwege müssen bis auf definierte Toleranz
übereinstimmen: der SEPARATE Kommutationskern
(:mod:`rechner_pipeline.kommutationskern` — kein Bestandteil des
Zielkerns) gegen das Zustandsmodell-Rückgrat des Kerns
(:mod:`rechner_pipeline.kern.zustandsmodell`). Jeder verglichene Wert wird
klassifiziert:

* ``exakt`` — bitgleich;
* ``rundung`` — innerhalb der Toleranz ``|a-b| <= atol + rtol*max(|a|,|b|)``
  (erwartete Klasse: die Backbones unterscheiden sich nur um
  Rundungsreihenfolgen — Excel-Rundung der Kommutationsspalten vs. reine
  Float-Produkte);
* ``abweichend`` — außerhalb der Toleranz; jede solche Abweichung wird
  einzeln ausgewiesen (Modellpunkt, Ort, beide Werte).

Der Bericht war die Abnahme-Grundlage für den Wechsel des produktiven
KLV-Pfads auf das Zustandsmodell (abgenommen 2026-08-12, kern 2.0.0);
seither ist das Gate der dauerhafte Kreuz-Check beider Schienen (beide
werden EXPLIZIT injiziert — es prüft die Schienen-Äquivalenz, nicht den
produktiven Default; dessen Voll-Präzisions-Verankerung sind die
Anker-Fixtures). Bekannte gemeinsame blinde Stelle beider Schienen: die
letzte Tafelzelle (Kommutation füllt tx/cx am Endalter 123 nie; für die
ausgelieferten Tafeln ist die Differenz exakt 0, weil lx dort bereits 0
ist).
"""

from __future__ import annotations

import dataclasses
from typing import Any, Dict, Iterable, List

from rechner_pipeline.kommutationskern import kommutation
from rechner_pipeline.kommutationskern.barwerte import Barwerte
from rechner_pipeline.kern.model_point import ModelPoint
from rechner_pipeline.kern.produkte.klv import KLV
from rechner_pipeline.kern import tafeln
from rechner_pipeline.kern.zustandsmodell import ZustandsBarwerte

#: Toleranz der Rundungsklasse (relative + absolute Komponente). Die
#: absolute Komponente skaliert mit der Versicherungssumme des Modellpunkts
#: (Betragswerte und ihre Ausloeschungs-Residuen wachsen mit der VS; ein
#: festes atol waere stillschweigend auf die 1e5-Skala des Quell-Workbooks
#: kalibriert — Review-Fix: False-Positives ab VS ~1e9, irrefuehrende
#: Headline-Kennzahl ab VS ~5e7). rtol ist bewusst deutlich straffer als
#: die 4-Nachkommastellen-Kante des Golden-Master-Vergleichs.
RTOL_RUNDUNG = 1e-11
ATOL_RUNDUNG = 1e-9  # je Modellpunkt skaliert: atol * max(1, VS / 1e5)


def _atol_fuer(mp: ModelPoint, atol: float) -> float:
    return atol * max(1.0, mp.sum_insured / 1e5)


def _klassifiziere(a: float, b: float, rtol: float, atol: float) -> str:
    if a == b:
        return "exakt"
    if abs(a - b) <= atol + rtol * max(abs(a), abs(b)):
        return "rundung"
    return "abweichend"


def _relative_abweichung(a: float, b: float) -> float:
    nenner = max(abs(a), abs(b))
    return abs(a - b) / nenner if nenner else 0.0


def ueberleitung_klv(
    modellpunkte: Iterable[ModelPoint],
    *,
    rtol: float = RTOL_RUNDUNG,
    atol: float = ATOL_RUNDUNG,
) -> Dict[str, Any]:
    """Überleitung Kommutation vs. Zustandsmodell über eine Modellpunkt-Liste.

    Vergleicht je Modellpunkt alle Golden-Contract-Skalare und alle
    Verlaufswerte-Zellen beider Rückgrate. Rückgabe: Bericht-Dict mit
    Klassen-Zählern, maximaler relativer Abweichung (mit Fundort) und der
    vollständigen Liste der ``abweichend``-Fälle (leer = Gate bestanden).
    """
    werte_verglichen = 0
    klassen = {"exakt": 0, "rundung": 0, "abweichend": 0}
    abweichende: List[Dict[str, Any]] = []
    max_rel = 0.0
    max_rel_ort: Dict[str, Any] = {}

    def vergleiche(
        mp_index: int, mp: ModelPoint, atol_mp: float, ort: str, a: float, b: float
    ) -> None:
        nonlocal werte_verglichen, max_rel, max_rel_ort
        werte_verglichen += 1
        klasse = _klassifiziere(a, b, rtol, atol_mp)
        klassen[klasse] += 1
        rel = _relative_abweichung(a, b)
        # Kennzahl nur ueber signifikante Werte (numerische Nullen wuerden
        # die relative Abweichung sinnlos aufblasen; sie sind ueber das
        # VS-skalierte atol bereits korrekt klassifiziert):
        if rel > max_rel and max(abs(a), abs(b)) > atol_mp:
            max_rel = rel
            max_rel_ort = {
                "modellpunkt": mp_index, "ort": ort,
                "kommutation": a, "zustandsmodell": b,
            }
        if klasse == "abweichend":
            abweichende.append(
                {
                    "modellpunkt": mp_index,
                    "x": mp.x, "sex": mp.sex, "n": mp.n, "t": mp.t,
                    "ort": ort,
                    "kommutation": a, "zustandsmodell": b,
                    "relativ": rel,
                }
            )

    anzahl_mps = 0
    for mp_index, mp in enumerate(modellpunkte):
        anzahl_mps += 1
        atol_mp = _atol_fuer(mp, atol)
        kom = kommutation.fuer(mp.sex, mp.tafel, mp.zins)
        # Beide Schienen EXPLIZIT injizieren — das Gate ist unabhaengig davon,
        # welche Schiene gerade der produktive Default ist.
        klassisch = KLV(mp, barwerte=Barwerte(kom, mp.zins))
        zustand = KLV(mp, barwerte=ZustandsBarwerte(
            tafeln.basis(mp.sex, mp.tafel), mp.zins))
        for name, a in klassisch.scalars().items():
            vergleiche(mp_index, mp, atol_mp, f"scalar {name}", a, zustand.scalars()[name])
        for jahr, (zeile_a, zeile_b) in enumerate(
            zip(klassisch.verlaufswerte(bis=50), zustand.verlaufswerte(bis=50))
        ):
            for spalte, a in zeile_a.items():
                vergleiche(
                    mp_index, mp, atol_mp,
                    f"jahr {jahr} spalte {spalte}", a, zeile_b[spalte],
                )

    return {
        "modellpunkte": anzahl_mps,
        "werte_verglichen": werte_verglichen,
        "klassen": klassen,
        "rtol": rtol,
        "atol": atol,
        "max_relative_abweichung": max_rel,
        "max_relative_abweichung_ort": max_rel_ort,
        "abweichende": abweichende,
        "bestanden": not abweichende,
    }


def standard_modellpunkte(basis: ModelPoint) -> List[ModelPoint]:
    """Der Standard-Sweep der Überleitung: Basis plus systematische Varianten.

    Deckt beide Tafeln, beide Geschlechter, Zahlweisen, Grenzfälle t=n,
    junge/alte Eintrittsalter, die Hochalter-Region auf DAV2008 (bis Alter
    119, nahe der Tafelgrenze), Zins-Extreme und grosse Versicherungssummen
    ab (alle im rechenbaren Tafelbereich; DAV1994 ist durch das
    51-Zeilen-Vergleichsfenster der Ueberleitung strukturell bei x=50
    gedeckelt).
    """
    r = dataclasses.replace
    return [
        basis,
        r(basis, sex="F"),
        r(basis, zins=0.0225, tafel="DAV2008_T"),
        r(basis, sex="F", zins=0.0225, tafel="DAV2008_T"),
        r(basis, zw=1),
        r(basis, zw=4),
        r(basis, zw=2),
        r(basis, t=basis.n),
        r(basis, x=25, n=40, t=40, sum_insured=50000.0),
        r(basis, x=50, n=20, t=15),
        r(basis, x=20, n=45, t=35, sum_insured=250000.0),
        r(basis, x=60, n=40, t=30, zins=0.0225, tafel="DAV2008_T"),
        r(basis, x=69, n=30, t=25, sex="F", zins=0.0225, tafel="DAV2008_T"),
        r(basis, zins=0.0),
        r(basis, zins=0.04),
        r(basis, sum_insured=5e7),
    ]
