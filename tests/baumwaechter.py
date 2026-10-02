"""Baumwaechter: die Suite veraendert ihren eigenen Arbeitsbaum nicht.

Invariante: Waehrend eine Suite laeuft, bleibt ``git status --porcelain``
ihres Baums so, wie es beim Sitzungsbeginn war.

Warum das eine Zusicherung der Suite ist und keine Hausordnung: Der
Systemstand (``gates._provenienz.systemstand``) liest ``commit``, ``branch``,
``dirty`` und den Quellcode-Hash vom LEBENDEN Baum, und jedes Gate haelt den
Stand seiner Belege gegen den eigenen. Legt ein Test waehrend des Laufs eine
nicht ignorierte Datei in den Baum, kippt ``dirty`` in einem sauberen Baum
von ``nein`` auf ``ja`` — und ein Fixture eines ANDEREN Workers, das gerade
einen Beleg erzeugt und gleich wieder liest, bricht mit "traegt einen anderen
Systemstand". Gemessen am 2026-10-01: zwei Laeufe, ein und zwei Errors,
jedes Mal andere Fixtures; Verursacher waren ein Arbeitsverzeichnis im
Repo-Root und eine Zwischendatei der Doku-Engine.

Warum ein Zeitgeber und kein Vorher-Nachher-Vergleich je Test: Beide
Verursacher raeumten hinter sich auf (Kontextmanager). Vor und nach dem Test
war der Baum gleich; schmutzig war er nur dazwischen, und genau dazwischen
lesen die anderen Worker.

Warum gegen den Sitzungsbeginn und nicht gegen "leer": Auf dem
Entwicklerrechner ist der Baum meist schon schmutzig, ``dirty`` kippt dort
gar nicht, und das Rennen bleibt unsichtbar. Der Vergleich gegen den
Ausgangsstand findet den Verursacher auch dort.

Grenze, benannt: Es ist eine Stichprobe. Eine Datei, die kuerzer lebt als
der Abtastabstand, kann durchrutschen. Der Waechter faengt die langlebigen
Verursacher; flattert es wieder, sind die kurzlebigen der Ort, an dem zu
suchen ist.

Knoten: system/architektur
"""

from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

#: Abstand der Lesungen in Sekunden.
ABSTAND = 0.2
#: Hoechstzahl festgehaltener Funde (der erste nennt den Verursacher).
HOECHSTENS = 50


def abweichung(ausgang: str, jetzt: str) -> List[str]:
    """Die Zeilen, in denen sich zwei ``git status --porcelain`` unterscheiden."""
    a, j = set(ausgang.splitlines()), set(jetzt.splitlines())
    return sorted(f"+ {z}" for z in j - a) + sorted(f"- {z}" for z in a - j)


class Baumwaechter:
    """Liest den Baumzustand im Abstand und haelt jede Abweichung vom
    Ausgangsstand mit Zeitpunkt fest."""

    def __init__(self, baum: Path, abstand: float = ABSTAND) -> None:
        self.baum = Path(baum)
        self.abstand = abstand
        self.ausgang: Optional[str] = None
        self.grund_inaktiv: Optional[str] = None
        self.lesungen = 0
        #: (Sekunden seit Start, Uhrzeit, abweichende Zeilen)
        self.funde: List[Tuple[float, str, List[str]]] = []
        self._zuletzt: Optional[str] = None
        self._ende = threading.Event()
        self._faden: Optional[threading.Thread] = None
        self._beginn = 0.0

    @property
    def aktiv(self) -> bool:
        return self.ausgang is not None

    def lies(self) -> Optional[str]:
        """``git status --porcelain`` des Baums (None = nicht lesbar)."""
        try:
            lauf = subprocess.run(
                ["git", "--no-optional-locks", "status", "--porcelain"],
                cwd=self.baum, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as exc:
            self.grund_inaktiv = f"git nicht ausfuehrbar ({type(exc).__name__})"
            return None
        if lauf.returncode != 0:
            self.grund_inaktiv = "kein Git-Arbeitsbaum"
            return None
        return lauf.stdout

    def start(self) -> None:
        self.ausgang = self.lies()
        if self.ausgang is None:
            return
        self._zuletzt = self.ausgang
        self._beginn = time.monotonic()
        self._faden = threading.Thread(target=self._lauf, name="baumwaechter", daemon=True)
        self._faden.start()

    def _lauf(self) -> None:
        while not self._ende.wait(self.abstand):
            self._pruefe()

    def _pruefe(self) -> None:
        jetzt = self.lies()
        if jetzt is None or self.ausgang is None:
            return
        self.lesungen += 1
        if jetzt != self._zuletzt and jetzt != self.ausgang and len(self.funde) < HOECHSTENS:
            self.funde.append((time.monotonic() - self._beginn, time.strftime("%H:%M:%S"),
                               abweichung(self.ausgang, jetzt)))
        self._zuletzt = jetzt

    def stop(self) -> None:
        if self._faden is None:
            return
        self._ende.set()
        self._faden.join(timeout=60)
        self._faden = None
        # Eine letzte Lesung: Was am Ende liegen geblieben ist, zaehlt auch.
        self._pruefe()

    def bericht(self) -> List[str]:
        """Die Zeilen fuer die Zusammenfassung des Laufs."""
        if not self.aktiv:
            return [f"Baumwaechter NICHT AKTIV: {self.grund_inaktiv} — ob die Suite ihren "
                    "Baum veraendert hat, ist in diesem Lauf nicht geprueft"]
        if not self.funde:
            return [f"Baumwaechter: {self.lesungen} Lesungen im Abstand von {self.abstand} s, "
                    "der Baum blieb wie beim Sitzungsbeginn"]
        zeilen = [
            f"Baumwaechter: der Arbeitsbaum hat sich waehrend des Laufs {len(self.funde)}-mal "
            "veraendert. Jedes Ergebnis, das am Systemstand haengt, ist damit Zufall "
            "(tests/baumwaechter.py). Ein Test, der im Repo-Baum schreibt, gehoert nach "
            "tmp_path; wer waehrend einer Suite im selben Baum arbeitet, entwertet sie."]
        for sekunden, uhrzeit, diff in self.funde:
            zeilen.append(f"  {uhrzeit} (+{sekunden:.1f} s): " + "; ".join(diff[:6])
                          + (f"; ... {len(diff) - 6} weitere" if len(diff) > 6 else ""))
        return zeilen


def urteil(waechter: Baumwaechter, exitstatus: int) -> int:
    """Der Exit-Code des Laufs: ein gruener Lauf mit Funden ist rot."""
    return 1 if waechter.funde and exitstatus == 0 else exitstatus
