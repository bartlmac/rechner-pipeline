"""Ausgesetzte Tests des Rueckbaus von Fall 2 — die Mechanik.

Der Rueckbau (Kern 3.21.0) nimmt aus dem Kern, was nur der uebernommene
Tarif TG2015 braucht, samt seiner sechs Tafeln und seinem Abschnitt der
Config. Die Tests dieser Faehigkeiten — und die Tests allgemeiner Mechanik,
die ihre Welt auf dem uebernommenen Tarif bauen — haben auf diesem Stand
keinen Gegenstand. Sie werden nicht geloescht und nicht einzeln markiert,
sondern stehen mit ihrer Kennung in EINER Liste
(``tests/rueckbau_fall2_ausgesetzt.txt``) und werden beim Sammeln
abgewaehlt. Wer die Faehigkeiten zurueckbringt (Fall 3, Gate A-K2), loescht
die Liste; dann laufen sie wieder.

Drei Zusicherungen gegen eine Liste, die still mehr verschweigt als gemeint:

* Jeder Lauf nennt in seiner Zusammenfassung, wie viele Tests die Liste
  aussetzt.
* Eine Kennung der Liste, die es beim Sammeln der ganzen Suite nicht gibt,
  ist ein Fehler (ein umbenannter Test verschwaende sonst aus beiden Welten).
* Die Zahl der Eintraege ist in ``tests/test_rueckbau_fall2.py`` mit ``==``
  festgehalten; die Liste waechst nicht unbemerkt.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

LISTE = Path(__file__).resolve().parent / "rueckbau_fall2_ausgesetzt.txt"


def ausgesetzt(pfad: Path = LISTE) -> List[str]:
    """Die Kennungen der Liste, in ihrer Reihenfolge (ohne Leer- und
    Kommentarzeilen). Fehlt die Liste, ist nichts ausgesetzt."""
    if not pfad.is_file():
        return []
    return [z.strip() for z in pfad.read_text(encoding="utf-8").splitlines()
            if z.strip() and not z.lstrip().startswith("#")]


def teile(kennungen: List[str], liste: List[str]) -> Tuple[List[int], List[str]]:
    """``(Stellen der ausgesetzten Tests, Eintraege der Liste ohne Test)``."""
    menge = set(liste)
    stellen = [i for i, k in enumerate(kennungen) if k in menge]
    gefunden = {kennungen[i] for i in stellen}
    return stellen, sorted(menge - gefunden)


def bericht(pfad: Path = LISTE) -> List[str]:
    liste = ausgesetzt(pfad)
    if not liste:
        return []
    return [f"Rueckbau Fall 2: {len(liste)} Tests ausgesetzt ({pfad.name}) — sie pruefen, was "
            "der Kern auf diesem Stand nicht rechnet, und laufen wieder, sobald die "
            "Faehigkeiten zurueck sind (Fall 3, A-K2) und die Liste geloescht ist"]
