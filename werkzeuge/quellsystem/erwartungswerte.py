"""Die Erwartungswerte der Lieferung: was die Quelle selbst erwartet.

Zur Lieferung gehoeren vier JSON-Dateien im Format der Alt-Lieferung —
das abgestimmte Pruefprogramm der Migrationsabnahme:

* ``stichprobe``: WELCHE Vertraege geprueft werden. Die Ziehung ist
  geschichtet nach Historientyp (fuer A-M1/A-M2) bzw. Vollerhebung der
  Vorfaelle des Migrationsjahres (A-M3) und passiert VOR der Berechnung
  der Vergleichswerte — andersherum liesse sich die Stichprobe nach
  ihren Ergebnissen aussuchen.
* ``stichtag`` (A-M1): je Vertrag der Wert am Uebernahmepunkt t_a und
  am naechsten Jahresgitterpunkt (Fortschreibungsregel).
* ``verlauf`` (A-M2): Punkte bei t_a + 5 und + 10 Jahren sowie am
  Ablauf, beschnitten auf die Restlaufzeit.
* ``geschaeftsvorfaelle`` (A-M3): je Vorfall des Migrationsjahres die
  DK-Wirkung (dDK) aus dem Journal der Fuehrung.

Alle Werte kommen aus DERSELBEN Strecke wie der Bestandsabzug
(:func:`quellsystem.export.werte_am` auf dem rekonstruierten
Stichtagszustand): Der Uebernahmepunkt IST das gelieferte DECKKAP.
Historientypen sind eine Klassifikation der Vorgeschichte am Stichtag —
bei mehreren Vorfallarten je Vertrag benennt der Typ, was die Bewertung
am staerksten praegt (beitragsfrei vor reduziert vor dynamik).
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from quellsystem.bestandsfuehrung import Police, _volle_jahre
from quellsystem.export import Export, werte_am

HISTORIENTYPEN = ("ohne_vorgeschichte", "dynamik", "beitragsfrei",
                  "reduziert")

#: Pruefprofile der Abnahmen — Toleranzen wie in der Alt-Lieferung
#: etabliert. Der Verlaufstest traegt die weiteren Grenzen (lange
#: Projektion), der Geschaeftsvorfalltest ein enges ERH-Kriterium (die
#: neue Scheibe traegt am Buchungstag keine Reserve).
GRUNDTOLERANZ = {"abs_tol": 0.01, "max_abs_residuum": 0.05,
                 "p95_abs_residuum": 0.02, "rel_tol": 1e-09}
VERLAUFSTOLERANZ = {"abs_tol": 0.05, "max_abs_residuum": 1.0,
                    "p95_abs_residuum": 0.25, "rel_tol": 1e-07}
ERH_KRITERIUM = {"abs_tol": 0.001, "max_abs_residuum": 0.005,
                 "p95_abs_residuum": 0.005, "rel_tol": 1e-09}

HINWEIS_ZIEHUNG = (
    "Die Stichproben sind gezogen, BEVOR die Vergleichswerte vorlagen. "
    "Andersherum liesse sich die Stichprobe nach ihren Ergebnissen "
    "aussuchen.")

BEMERKUNG_STICHTAG = (
    "Beide Punkte vergleichen zum selben Zeitpunkt gegen einen "
    "gelieferten Wert; es trennt sie nur die Rundung. Eine "
    "Unterscheidung je Groesse ist deshalb nicht begruendet — kVx_MRV, "
    "RKW, BJB und VS_bfr tragen dieselbe Grenze. Der Uebernahmepunkt "
    "ist bei gefuehrter Korrekturschicht konstruktionsbedingt null; "
    "aussagekraeftig ist der zweite Punkt, der die Fortschreibungsregel "
    "prueft.")

BEMERKUNG_VERLAUF = (
    "Die Verlaufspunkte liegen bei t_a + 5 und + 10 Jahren sowie am "
    "Ablauf, beschnitten auf die Restlaufzeit; faellt ein Zwischenpunkt "
    "auf den Ablauf, erscheint er einmal. Vertraege mit kurzer "
    "Restlaufzeit tragen entsprechend weniger Punkte; der Ablauf ist "
    "immer dabei. Zum Ablauf ist der Wert keine Rechengroesse mehr, "
    "sondern die Zahlung an den Kunden — er verdiente eine engere "
    "Grenze als die Zwischenpunkte. Die Engine schluesselt die "
    "Kriterien dieses Tests aber nach Vergleichsgroesse, nicht nach "
    "Anlass; wer den Ablauf enger fahren will, prueft ihn heute als "
    "eigenen Lauf. Das ist eine bekannte Enge der Profilstruktur, keine "
    "fachliche Aussage. Nach der Beitragszeit einer Scheibe zaehlt ihr "
    "Beitrag nicht mehr — BJB ist der am Punkt gezahlte Jahresbeitrag.")

BEMERKUNG_GEVO = (
    "Rueckkauf, Tod und Ablauf beenden den Vertrag und raeumen die "
    "gefuehrte Reserve; dDK ist die Wirkung des Vorfalls auf das "
    "Deckungskapital im Buch der Quelle, festgehalten am Buchungstag. "
    "Die Quelle rechnet Beitragsfreistellung und Herabsetzung MIT "
    "Stornoabzug (je Baustein beziehungsweise anteilig auf der "
    "Grundscheibe); rechnet das Zielsystem verlustfrei um, weicht dDK "
    "um genau diese Abzuege ab. Diese Grenze aufzuweiten, um den Befund "
    "verschwinden zu lassen, waere falsch — die Abweichung ist der "
    "Sachverhalt, den die Abnahme sehen soll. Sie gehoert in die "
    "Abnahmeentscheidung, belegt durch die Beschreibung des "
    "Quellverfahrens, nicht in eine stillere Toleranz. Die Dynamik "
    "traegt am Buchungstag noch keine Reserve — ihr Kriterium ist "
    "entsprechend eng.")


def _json(pfad: Path, inhalt: dict) -> Path:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps(inhalt, ensure_ascii=False, indent=1, sort_keys=True)
        + "\n", encoding="utf-8")
    return pfad


class Erwartungswerte:
    """Die vier Erwartungswerte-Dateien eines Migrationsstichtags."""

    def __init__(
        self,
        export: Export,
        stichtag: dt.date,
        stichtag2: dt.date,
        *,
        saat: str = "baldrian-uebernahme-2026",
        je_schicht: int = 25,
    ) -> None:
        self.export = export
        self.stichtag = stichtag
        self.stichtag2 = stichtag2
        self.saat = saat
        self.je_schicht = je_schicht
        self._abzug = export._im_abzug(stichtag)
        self._cluster: Dict[str, List[int]] = {t: [] for t in HISTORIENTYPEN}
        for p in self._abzug:
            self._cluster[self.historientyp(p)].append(p.polnr)
        self._gezogen = self._ziehe()

    # -- Klassifikation und Ziehung ----------------------------------------- #

    def historientyp(self, police: Police) -> str:
        s1 = self.stichtag
        pex = self.export._pex.get(police.polnr)
        if pex is not None and pex <= s1:
            return "beitragsfrei"
        if any(datum <= s1 for datum, _ in police.herabsetzungen):
            return "reduziert"
        if any(s.beginn <= s1 for s in police.scheiben[1:]):
            return "dynamik"
        return "ohne_vorgeschichte"

    def _ziehe(self) -> List[int]:
        """Geschichtete Ziehung, deterministisch aus der Saat.

        Je Historientyp hoechstens ``je_schicht`` Policen; ein Cluster
        mit weniger Vertretern geht vollstaendig ein.
        """
        rnd = random.Random(self.saat)
        gezogen: List[int] = []
        for typ in HISTORIENTYPEN:
            ids = sorted(self._cluster[typ])
            gezogen.extend(rnd.sample(ids, min(self.je_schicht, len(ids))))
        return gezogen

    def _stichproben_block(self) -> dict:
        return {
            "profil": "geschichtet",
            "police_ids": [str(n) for n in self._gezogen],
            "umfang": len(self._gezogen),
            "grundgesamtheit": len(self._abzug),
            "vollerhebung": len(self._gezogen) == len(self._abzug),
            "parameter": {
                "saat": self.saat,
                "je_schicht": self.je_schicht,
                "abdeckung": {
                    typ: {
                        "vorhanden": len(self._cluster[typ]),
                        "gezogen": min(self.je_schicht,
                                       len(self._cluster[typ])),
                    }
                    for typ in HISTORIENTYPEN
                },
            },
        }

    def _vorfall_polnrs(self) -> List[int]:
        return sorted({
            b.polnr for b in self.export.buch.journal
            if b.art != "ZUG" and self.stichtag < b.datum <= self.stichtag2
        })

    def _vollbestand_block(self) -> dict:
        polnrs = self._vorfall_polnrs()
        return {
            "profil": "vollbestand",
            "police_ids": [str(n) for n in polnrs],
            "umfang": len(polnrs),
            "grundgesamtheit": len(polnrs),
            "vollerhebung": True,
            "parameter": {},
        }

    # -- Vertragseintraege --------------------------------------------------- #

    def _kopf(self, police: Police) -> dict:
        pex = self.export._pex.get(police.polnr)
        beitragsfrei_seit_jahr: Optional[int] = None
        if pex is not None and pex <= self.stichtag:
            beitragsfrei_seit_jahr = _volle_jahre(police.grund.beginn, pex)
        return {
            "police_id": str(police.polnr),
            "historientyp": self.historientyp(police),
            "monate_ta": 12 * _volle_jahre(police.grund.beginn,
                                           self.stichtag),
            "beitragsfrei_seit_jahr": beitragsfrei_seit_jahr,
        }

    def _punkt(self, police: Police, anlass: str, monate: int) -> dict:
        stand = self.export.stand_am(police, self.stichtag)
        werte = werte_am(stand, monate)
        groessen = (["kVx_MRV", "VS_bfr"] if stand.beitragsfrei
                    else ["kVx_MRV", "RKW", "BJB"])
        return {
            "anlass": anlass,
            "monate": monate,
            "groessen": groessen,
            "erwartet": {g: werte[g] for g in groessen},
        }

    def _vertraege(self, punkte_je_police) -> List[dict]:
        vertraege = []
        for polnr in self._gezogen:
            police = self.export.buch.policen[polnr]
            eintrag = self._kopf(police)
            eintrag["punkte"] = punkte_je_police(police,
                                                 eintrag["monate_ta"])
            vertraege.append(eintrag)
        return vertraege

    # -- Die vier Dateien ---------------------------------------------------- #

    def stichtag_json(self, pfad: Path) -> Path:
        def punkte(police: Police, monate_ta: int) -> List[dict]:
            return [
                self._punkt(police, "uebernahme", monate_ta),
                self._punkt(police, "fortschreibung", monate_ta + 12),
            ]

        return _json(pfad, {
            "test": "A-M1",
            "profil": {
                "kennung": "A-M1",
                "titel": "Stichtagstest",
                "weite": (f"geschichtet, {self.je_schicht} je "
                          "Historientyp-Cluster"),
                "grundtoleranz": GRUNDTOLERANZ,
                "kriterien": {},
                "bemerkung": BEMERKUNG_STICHTAG,
            },
            "stichprobe": self._stichproben_block(),
            "vertraege": self._vertraege(punkte),
        })

    def verlauf_json(self, pfad: Path) -> Path:
        def punkte(police: Police, monate_ta: int) -> List[dict]:
            ablauf = 12 * police.grund.n
            kandidaten = sorted({
                m for m in (monate_ta + 60, monate_ta + 120, ablauf)
                if m <= ablauf
            })
            return [self._punkt(police, "verlauf", m) for m in kandidaten]

        return _json(pfad, {
            "test": "A-M2",
            "profil": {
                "kennung": "A-M2",
                "titel": "Verlaufstest",
                "weite": (f"geschichtet, {self.je_schicht} je "
                          "Historientyp-Cluster"),
                "grundtoleranz": VERLAUFSTOLERANZ,
                "kriterien": {},
                "bemerkung": BEMERKUNG_VERLAUF,
            },
            "stichprobe": self._stichproben_block(),
            "vertraege": self._vertraege(punkte),
        })

    def geschaeftsvorfaelle_json(self, pfad: Path) -> Path:
        anteile = {
            (p.polnr, datum): f
            for p in self.export.buch.policen.values()
            for datum, f in p.herabsetzungen
        }
        vertraege = []
        for polnr in self._vorfall_polnrs():
            police = self.export.buch.policen[polnr]
            kopf = self._kopf(police)
            kopf.pop("beitragsfrei_seit_jahr")
            punkte = []
            for b in self.export.buch.journal:
                if (b.polnr != polnr or b.art == "ZUG"
                        or not (self.stichtag < b.datum <= self.stichtag2)):
                    continue
                punkt = {
                    "anlass": b.art,
                    "monate": 12 * _volle_jahre(police.grund.beginn,
                                                b.datum),
                    "groessen": ["dDK"],
                    "erwartet": {"dDK": b.dk_delta},
                }
                if b.art == "RED":
                    punkt["parameter"] = {
                        "anteil": anteile[(polnr, b.datum)]}
                punkte.append(punkt)
            kopf["punkte"] = sorted(punkte, key=lambda p: p["monate"])
            vertraege.append(kopf)
        return _json(pfad, {
            "test": "A-M3",
            "profil": {
                "kennung": "A-M3",
                "titel": "Geschaeftsvorfalltest",
                "weite": "alle Geschaeftsvorfaelle des Migrationsjahres",
                "grundtoleranz": GRUNDTOLERANZ,
                "kriterien": {"ERH": ERH_KRITERIUM},
                "bemerkung": BEMERKUNG_GEVO,
            },
            "stichprobe": self._vollbestand_block(),
            "vertraege": vertraege,
        })

    def stichprobe_json(self, pfad: Path) -> Path:
        return _json(pfad, {
            "bestand":
                f"baldrian_bestandsabzug_{self.stichtag.isoformat()}.csv",
            "gezogen_am": self.stichtag.isoformat(),
            "hinweis": HINWEIS_ZIEHUNG,
            "A-M1_A-M2": self._stichproben_block(),
            "A-M3": self._vollbestand_block(),
        })

    def schreibe(self, ziel: Path) -> List[Path]:
        ziel = Path(ziel)
        return [
            self.stichprobe_json(
                ziel / "baldrian_erwartungswerte_stichprobe.json"),
            self.stichtag_json(
                ziel / "baldrian_erwartungswerte_stichtag.json"),
            self.verlauf_json(
                ziel / "baldrian_erwartungswerte_verlauf.json"),
            self.geschaeftsvorfaelle_json(
                ziel / "baldrian_erwartungswerte_geschaeftsvorfaelle.json"),
        ]
