"""Generische Barwert-Bausteine (VBA ``mBarwerte``) — produktunabhängig.

Kennt nur die Kommutationsbasis und den Zins, keinen Modellpunkt und kein
Produkt: die Trennlinie zwischen versicherungsmathematischen Bausteinen und
den KLV-Zielgrößen (:mod:`rechner_pipeline.kern.produkte.klv`). Die Formeln
sind unverändert aus dem promoteten Kern übernommen (Code-Motion, identische
Operationsreihenfolge); ``axn_k`` ist je Instanz memoisiert — pure Funktion,
der gecachte Wert ist bitgleich mit jedem Neuaufruf.
"""

from __future__ import annotations

from typing import Dict, Tuple

from rechner_pipeline.kern.kommutation import Kommutation


class Barwerte:
    """Barwert-Bausteine auf einer Kommutationsbasis (Zahlungsordnung k)."""

    def __init__(self, kom: Kommutation, zins: float) -> None:
        self.kom = kom
        self.zins = zins
        self._axn_cache: Dict[Tuple[int, int, int], float] = {}

    def abzugsglied(self, k: int) -> float:
        """Unterjähriges Korrekturglied (VBA ``Act_Abzugsglied``); 0 für k=1."""
        if k <= 0:
            return 0.0
        zins = self.zins
        total = 0.0
        for step in range(0, k):
            total += (step / k) / (1.0 + (step / k) * zins)
        return total * (1.0 + zins) / k

    def axn_k(self, age: int, term: int, k: int = 1) -> float:
        """Temporäre vorschüssige Rente (VBA ``Act_axn_k``)."""
        if k <= 0:
            return 0.0
        key = (age, term, k)
        cached = self._axn_cache.get(key)
        if cached is not None:
            return cached
        dx = self.kom.Dx_at(age)
        dxt = self.kom.Dx_at(age + term)
        value = (self.kom.Nx_at(age) - self.kom.Nx_at(age + term)) / dx - self.abzugsglied(
            k
        ) * (1.0 - dxt / dx)
        self._axn_cache[key] = value
        return value

    def ax_k(self, age: int, k: int = 1) -> float:
        """Lebenslange vorschüssige Rente (VBA ``Act_ax_k``)."""
        if k <= 0:
            return 0.0
        return self.kom.Nx_at(age) / self.kom.Dx_at(age) - self.abzugsglied(k)

    def nGrAx(self, age: int, term: int) -> float:
        """Temporäre Todesfallversicherung (VBA ``Act_nGrAx``)."""
        return (self.kom.Mx_at(age) - self.kom.Mx_at(age + term)) / self.kom.Dx_at(age)

    def nGrEx(self, age: int, term: int) -> float:
        """Erlebensfallversicherung (VBA ``Act_nGrEx``): D_{x+term}/D_x."""
        return self.kom.Dx_at(age + term) / self.kom.Dx_at(age)

    def endowment_benefit_pv(self, age: int, term: int) -> float:
        """Gemischte Versicherung: Todesfall- plus Erlebensfall-Barwert."""
        return self.nGrAx(age, term) + self.nGrEx(age, term)

    # ----------------------------------------------------------------- #
    # Whole-life-Bausteine (Äquivalenzprinzip-Referenz, algebraische Gates).
    # ----------------------------------------------------------------- #

    def Ax(self, age: int) -> float:
        return self.kom.Mx_at(age) / self.kom.Dx_at(age)

    def aex(self, age: int) -> float:
        return self.kom.Nx_at(age) / self.kom.Dx_at(age)

    def pv_benefits(self, age: int) -> float:
        return self.Ax(age)

    def pv_premiums(self, age: int) -> float:
        return self.aex(age)

    def net_premium(self, age: int) -> float:
        return self.pv_benefits(age) / self.pv_premiums(age)
