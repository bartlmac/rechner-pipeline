"""Zustandsmodell (Semi-Markov) — das allgemeine Rechenrückgrat des Monolithen.

Beschluss 2026-08-12 (Bartek, operative Entscheidung, gedeckt vom
Team-Beschluss „monolithischer, möglichst flexibler Kern"): Das
Zustandsmodell ist das Ziel-Rückgrat der Personenversicherungsmathematik in
diesem Kern — KLV ist sein 2-Zustands-Spezialfall (aktiv/tot), BU/Pflege
werden Konfigurationen (Zustände x Übergänge x Tafeln), keine neuen Engines.

Mathematischer Rahmen:

* Zustandsraum S (klein, benannte Zustände); jährliche Übergänge mit
  Wahrscheinlichkeiten ``uebergang(von, nach, alter, dauer)``. Der Verbleib
  im Zustand ist das Residuum ``1 - Summe der Wegzüge`` (fail-fast, wenn die
  Wegzüge 1 übersteigen).
* Semi-Markov über Zustandsraum-Erweiterung: ``dauer`` ist die Zahl voller
  Jahre im aktuellen Zustand, gekappt bei ``max_dauer`` (Select-Perioden-
  Prinzip der DAV-Tafeln); ``max_dauer=0`` ist der homogene Markov-Fall.
* Zahlungen: vorschüssig auf Zuständen (``zahlung_zustand(zustand, jahr)``)
  und nachschüssig auf Übergängen (``zahlung_uebergang(von, nach, jahr)``,
  fällig am Jahresende des Übergangsjahres). Diskontierung mit konstantem
  Rechnungszins.
* Bewertung über Thiele-Rückwärtsrekursion (:meth:`Zustandsmodell.barwert`);
  die Vorwärts-Zustandsverteilung (:meth:`Zustandsmodell.verteilung`) dient
  als unabhängiger Selbsttest (Vorwärts- == Rückwärtsbewertung, testseitig
  verankert).

Abgrenzung zur Kommutations-Schiene (:mod:`rechner_pipeline.kern.barwerte`):
Die Kommutation ist die geschlossene Summenform des 2-Zustands-Falls mit den
Excel-Rundungsartefakten des migrierten Quell-Workbooks. Das Zustandsmodell
rechnet dieselbe Mathematik ohne diese Artefakte — Abweichungen sind reine
Rundungsreihenfolgen-Differenzen und werden über die Toleranz-Überleitung
(:mod:`rechner_pipeline.qa.ueberleitung`) klassifiziert. Der Wechsel des
produktiven KLV-Pfads auf diese Schiene wurde am 2026-08-12 abgenommen
(kern 2.0.0); die Kommutation bleibt dauerhaft als Kreuz-Check-Schiene.
Die klassische Tafel-Domäne gilt unverändert: Anker-Alter mit Dx = 0
(Tafel erschöpft) sind fail-fast (:class:`TafelBereichError`) statt
stiller bedingter Werte.

Stdlib-only (bewusst kein numpy): kleine Zustandsräume, deterministische
Reihenfolgen.

Knoten: klv, bu
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from rechner_pipeline.kern.konventionen import MAX_ALTER
from rechner_pipeline.kern.tafeln import Tafelbasis, TafelBereichError

#: Signatur der Übergangswahrscheinlichkeiten: (von, nach, alter, dauer) -> p.
UebergangsFunktion = Callable[[str, str, int, int], float]


class Zustandsmodell:
    """Bewertung von Zahlungsströmen auf einem (Semi-)Markov-Zustandsraum."""

    def __init__(
        self,
        zustaende: Tuple[str, ...],
        zins: float,
        uebergang: UebergangsFunktion,
        *,
        max_dauer: int = 0,
    ) -> None:
        if len(zustaende) != len(set(zustaende)) or not zustaende:
            raise ValueError(f"Zustände nicht eindeutig oder leer: {zustaende}")
        if max_dauer < 0:
            raise ValueError("max_dauer < 0")
        self.zustaende = tuple(zustaende)
        self.zins = zins
        self.v = 1.0 / (1.0 + zins)
        self.uebergang = uebergang
        self.max_dauer = max_dauer

    def _wegzuege(self, von: str, alter: int, dauer: int) -> Dict[str, float]:
        """Übergänge aus ``von`` heraus plus Verbleib als Residuum."""
        p: Dict[str, float] = {}
        summe = 0.0
        for nach in self.zustaende:
            if nach == von:
                continue
            w = self.uebergang(von, nach, alter, dauer)
            if w < 0.0:
                raise ValueError(
                    f"Übergang {von}->{nach} (Alter {alter}, Dauer {dauer}): "
                    f"Wahrscheinlichkeit {w} < 0"
                )
            if w > 0.0:
                p[nach] = w
                summe += w
        if summe > 1.0 + 1e-12:
            raise ValueError(
                f"Wegzüge aus {von} (Alter {alter}, Dauer {dauer}) "
                f"summieren auf {summe} > 1"
            )
        if summe > 1.0:
            # Float-Epsilon-Fenster (1, 1+1e-12]: renormieren statt still
            # Gesamtmasse > 1 zu akzeptieren (Review-Fix; im 2-Zustands-Fall
            # mit summe = qx <= 1 nie erreicht).
            for nach in p:
                p[nach] /= summe
            p[von] = 0.0
            return p
        p[von] = 1.0 - summe
        return p

    def _folgedauer(self, von: str, nach: str, dauer: int) -> int:
        if nach != von:
            return 0
        return min(dauer + 1, self.max_dauer)

    def _pruefe_start(self, startzustand: str, start_dauer: int) -> None:
        """Fail-fast für Start-Parameter (Review-Fix: vorher lieferte ein
        ungültiges ``start_dauer`` still den Barwert 0.0 — für künftige
        Select-Konfigurationen wie BU ein stiller Reserven-Nuller)."""
        if startzustand not in self.zustaende:
            raise ValueError(f"Unbekannter Startzustand {startzustand!r}")
        if not 0 <= start_dauer <= self.max_dauer:
            raise ValueError(
                f"start_dauer {start_dauer} ausserhalb 0..{self.max_dauer} "
                "(Dauer beim Aufrufer auf max_dauer kappen — Select-Periode)"
            )

    def barwert(
        self,
        startzustand: str,
        alter0: int,
        horizont: int,
        zahlung_zustand: Optional[Callable[[str, int], float]] = None,
        zahlung_uebergang: Optional[Callable[[str, str, int], float]] = None,
        *,
        start_dauer: int = 0,
    ) -> float:
        """Barwert über ``horizont`` Jahre (Thiele-Rückwärtsrekursion).

        Vorschüssige Zustandszahlungen in den Jahren ``0..horizont-1`` und
        nachschüssige Übergangszahlungen am Ende des jeweiligen Jahres,
        diskontiert auf den Beginn von Jahr 0.
        """
        self._pruefe_start(startzustand, start_dauer)
        zz = zahlung_zustand or (lambda zustand, jahr: 0.0)
        zu = zahlung_uebergang or (lambda von, nach, jahr: 0.0)

        return self._rueckwaerts(
            startzustand, alter0, horizont, zz, zu, start_dauer, sammeln=False
        )

    def barwert_verlauf(
        self,
        startzustand: str,
        alter0: int,
        horizont: int,
        zahlung_zustand: Optional[Callable[[str, int], float]] = None,
        zahlung_uebergang: Optional[Callable[[str, str, int], float]] = None,
        *,
        start_dauer: int = 0,
    ) -> list:
        """Wie :meth:`barwert`, liefert aber den Wert zu JEDEM Jahresbeginn.

        ``werte[j]`` ist der Barwert des Restproblems ab Jahr ``j`` (Alter
        ``alter0 + j``, Zahlungen weiterhin an absoluten Jahren) —
        bit-identisch zum Einzelaufruf über denselben Suffix, weil derselbe
        Rekursionsschritt läuft. Grundlage des Spalten-Cachings in
        :class:`ZustandsBarwerte`; ``werte[horizont] == 0.0``.
        """
        self._pruefe_start(startzustand, start_dauer)
        zz = zahlung_zustand or (lambda zustand, jahr: 0.0)
        zu = zahlung_uebergang or (lambda von, nach, jahr: 0.0)
        return self._rueckwaerts(
            startzustand, alter0, horizont, zz, zu, start_dauer, sammeln=True
        )

    def _rueckwaerts(self, startzustand, alter0, horizont, zz, zu, start_dauer, sammeln):
        werte = [0.0] * (horizont + 1) if sammeln else None
        naechste: Dict[Tuple[str, int], float] = {}
        for jahr in range(horizont - 1, -1, -1):
            aktuelle: Dict[Tuple[str, int], float] = {}
            for zustand in self.zustaende:
                for dauer in range(0, self.max_dauer + 1):
                    p = self._wegzuege(zustand, alter0 + jahr, dauer)
                    zukunft = 0.0
                    for nach, w in p.items():
                        if w == 0.0:
                            continue
                        beitrag = naechste.get(
                            (nach, self._folgedauer(zustand, nach, dauer)), 0.0
                        )
                        if nach != zustand:
                            beitrag += zu(zustand, nach, jahr)
                        zukunft += w * beitrag
                    aktuelle[(zustand, dauer)] = (
                        zz(zustand, jahr) + self.v * zukunft
                    )
            naechste = aktuelle
            if sammeln:
                werte[jahr] = aktuelle.get((startzustand, start_dauer), 0.0)
        if sammeln:
            return werte
        return naechste.get((startzustand, start_dauer), 0.0)

    def verteilung(
        self, startzustand: str, alter0: int, jahre: int, *, start_dauer: int = 0
    ) -> Dict[Tuple[str, int], float]:
        """Zustandsverteilung nach ``jahre`` Jahren (Vorwärts-Selbsttest)."""
        self._pruefe_start(startzustand, start_dauer)
        aktuell: Dict[Tuple[str, int], float] = {(startzustand, start_dauer): 1.0}
        for jahr in range(jahre):
            naechste: Dict[Tuple[str, int], float] = {}
            for (zustand, dauer), masse in aktuell.items():
                if masse == 0.0:
                    continue
                for nach, w in self._wegzuege(zustand, alter0 + jahr, dauer).items():
                    if w == 0.0:
                        continue
                    ziel = (nach, self._folgedauer(zustand, nach, dauer))
                    naechste[ziel] = naechste.get(ziel, 0.0) + masse * w
            aktuell = naechste
        return aktuell


#: Spalten-Cache der 2-Zustands-Pässe je Basis (Analogon zum
#: Kommutations-Spaltenapparat, aber ohne Excel-Rundung): ein
#: Rückwärts-Pass je (Basis, Zahlungsart, Endalter) liefert die Werte für
#: ALLE Startalter — bit-identisch zu Einzelaufrufen (gleiche
#: Suffix-Rekursion). Unbegrenzt wie kommutation._CACHE.
_PASS_CACHE: Dict[Tuple, list] = {}


class ZustandsBarwerte:
    """Barwert-Bausteine auf dem Zustandsmodell — Interface wie ``Barwerte``.

    Der 2-Zustands-Spezialfall (aktiv/tot) auf einer
    :class:`~rechner_pipeline.kern.tafeln.Tafelbasis` (reine qx, fail-fast
    Tafelzugriff) — Ueberlebenswahrscheinlichkeiten sind reine
    (1-qx)-Produkte, ohne Kommutations-Ableitungen. Der separate
    Kommutationskern dient nur der Kreuz-Schiene
    (Toleranz-Überleitung: :mod:`rechner_pipeline.qa.ueberleitung`).

    Performance über Spalten-Pässe: je (Basis, Zahlungsart, Endalter) läuft
    die Thiele-Rekursion genau einmal (:meth:`Zustandsmodell.barwert_verlauf`)
    und bedient alle Startalter aus dem Cache.
    """

    AKTIV = "aktiv"
    TOT = "tot"

    def __init__(self, basis: Tafelbasis, zins: float) -> None:
        self.basis = basis
        self.zins = zins
        self.modell = Zustandsmodell(
            (self.AKTIV, self.TOT), zins, self._uebergang
        )
        self._axn_cache: Dict[Tuple[int, int, int], float] = {}
        self._basis = (*basis.key, zins)

    def _pass(self, art: str, endalter: int) -> list:
        """Wertespalte einer Zahlungsart bis ``endalter`` (gecacht je Basis)."""
        key = (self._basis, art, endalter)
        werte = _PASS_CACHE.get(key)
        if werte is not None:
            return werte
        if art == "annuitaet":
            werte = self.modell.barwert_verlauf(
                self.AKTIV, 0, endalter, zahlung_zustand=self._nur_aktiv
            )
        elif art == "tod":
            werte = self.modell.barwert_verlauf(
                self.AKTIV, 0, endalter, zahlung_uebergang=self._todesfall
            )
        elif art == "erleben":
            werte = self.modell.barwert_verlauf(
                self.AKTIV,
                0,
                endalter + 1,
                zahlung_zustand=lambda zustand, jahr: (
                    1.0 if zustand == self.AKTIV and jahr == endalter else 0.0
                ),
            )
        else:  # pragma: no cover - interne Nutzung
            raise ValueError(f"Unbekannte Zahlungsart {art!r}")
        _PASS_CACHE[key] = werte
        return werte

    def _uebergang(self, von: str, nach: str, alter: int, dauer: int) -> float:
        if von == self.AKTIV and nach == self.TOT:
            return self.basis.qx_at(alter)
        return 0.0

    def _pruefe_domaene(self, age: int, hoechstes_alter: int) -> None:
        """Tafel-Domaene durchsetzen (fail-fast).

        Jenseits der Tafel-Erschoepfung (ab dem ersten Alter nach qx = 1,
        z. B. DAV1994_T ab Alter 101) sind bedingte Barwerte nicht
        definiert — sprechender :class:`TafelBereichError` statt stiller
        bedingter Werte; das hoechste referenzierte Alter laeuft durch
        den Tafelbereichs-Check.
        """
        self.basis.pruefe_alter(age, hoechstes_alter)

    def _nur_aktiv(self, zustand: str, jahr: int) -> float:
        return 1.0 if zustand == self.AKTIV else 0.0

    def _todesfall(self, von: str, nach: str, jahr: int) -> float:
        return 1.0 if nach == self.TOT else 0.0

    def abzugsglied(self, k: int) -> float:
        """Unterjähriges Korrekturglied — Formel identisch zu ``Barwerte``."""
        if k <= 0:
            return 0.0
        zins = self.zins
        total = 0.0
        for step in range(0, k):
            total += (step / k) / (1.0 + (step / k) * zins)
        return total * (1.0 + zins) / k

    def axn_k(self, age: int, term: int, k: int = 1) -> float:
        """Temporäre vorschüssige Rente (Zustands-Annuität auf ``aktiv``)."""
        if k <= 0:
            return 0.0
        key = (age, term, k)
        cached = self._axn_cache.get(key)
        if cached is not None:
            return cached
        self._pruefe_domaene(age, age + term)
        annuitaet = self._pass("annuitaet", age + term)[age]
        value = annuitaet - self.abzugsglied(k) * (1.0 - self.nGrEx(age, term))
        self._axn_cache[key] = value
        return value

    def ax_k(self, age: int, k: int = 1) -> float:
        """Lebenslange vorschüssige Rente."""
        if k <= 0:
            return 0.0
        return self.aex(age) - self.abzugsglied(k)

    def nGrAx(self, age: int, term: int) -> float:
        """Temporäre Todesfallversicherung (Übergangszahlung aktiv->tot)."""
        self._pruefe_domaene(age, age + term)
        return self._pass("tod", age + term)[age]

    def nGrEx(self, age: int, term: int) -> float:
        """Erlebensfallversicherung: Zahlung bei Erleben des Jahres ``term``."""
        self._pruefe_domaene(age, age + term)
        return self._pass("erleben", age + term)[age]

    def endowment_benefit_pv(self, age: int, term: int) -> float:
        """Gemischte Versicherung: Todesfall- plus Erlebensfall-Barwert."""
        return self.nGrAx(age, term) + self.nGrEx(age, term)

    # ----------------------------------------------------------------- #
    # Whole-life-Bausteine (Äquivalenzprinzip-Referenz, algebraische Gates).
    # ----------------------------------------------------------------- #

    def Ax(self, age: int) -> float:
        self._pruefe_domaene(age, age)
        return self._pass("tod", MAX_ALTER + 1)[age]

    def aex(self, age: int) -> float:
        self._pruefe_domaene(age, age)
        return self._pass("annuitaet", MAX_ALTER + 1)[age]

    def pv_benefits(self, age: int) -> float:
        return self.Ax(age)

    def pv_premiums(self, age: int) -> float:
        return self.aex(age)

    def net_premium(self, age: int) -> float:
        return self.pv_benefits(age) / self.pv_premiums(age)
