"""Leistungs- und Beitragsprofil eines Vertrags — die allgemeine Form.

Das Zustandsmodell nimmt Zahlungen als Funktionen des Jahres entgegen
und kann damit jeden Leistungs- und Beitragsverlauf bewerten. Die
KLV-Schicht fragt es heute aber nur nach drei EINHEITS-Barwerten (Rente,
Todesfall, Erleben) und skaliert sie mit Versicherungssumme und Beitrag.
In dieser Skalierung steckt die Annahme, dass beide ueber die Laufzeit
konstant sind — die Grenze des Kommutationsmodells, die der Thiele-Kern
mitgeschleppt hat (ADR-013).

Dieses Modul hebt sie auf, ohne die Arithmetik zu verschieben.

**Relative Profile, Skalare aussen.** Ein Pfad beschreibt den Verlauf
RELATIV zur Grundsumme und zum Grundbeitrag: Der unveraenderte Vertrag
ist ueberall ``1.0``. Ein in Jahr 5 auf 60 Prozent herabgesetzter
Vertrag traegt ab dort andere Faktoren. Die Versicherungssumme und der
Beitragssatz bleiben AUSSERHALB der Rekursion, wo sie heute schon sind.

Das ist keine Stilfrage, sondern die Bedingung fuer die Abnahme: Zieht
man die Versicherungssumme in die Zahlungsfunktion, weichen die Werte in
der letzten Stelle ab (gemessen: 15 von 31 Vertragsjahren, a=0
65083.534357923694 statt 65083.53435792371), und die eingefrorenen
Referenzwerte vergleichen bit-exakt. Dasselbe gilt fuer das
Zusammenlegen von Todesfall- und Ablaufbein in einen Pass (24 von 31
Jahren). Die Summationsreihenfolge ist Teil dessen, was die Referenzen
festhalten.

**Fuenf getrennte Paesse**, je Vertrag einmal:

===========  =========================================================
``axn``      Rente ueber die Versicherungsdauer, Horizont ``n``
``axt``      Rente ueber die Beitragszahlungsdauer, Horizont ``t``
``azd``      Rente ueber die Zillmerdauer, Horizont ``zillmer_dauer``
``tod``      Todesfall, Uebergangszahlung, Horizont ``n``
``erleben``  Ablauf, ZUSTANDSzahlung im Jahr ``n``, Horizont ``n + 1``
===========  =========================================================

Drei Fallen stecken in dieser Tabelle, alle nachgerechnet:

*Der Horizont des Ablaufs ist ``n + 1``.* ``werte[horizont]`` ist immer
``0.0``; mit Horizont ``n`` kommt fuer den Erlebensfall exakt null
heraus statt 0,301.

*Der Ablauf ist eine ZUSTANDSzahlung.* Uebergangszahlungen werden ein
Jahr abgezinst, Zustandszahlungen nicht. Als Uebergangszahlung gestellt,
faellt der Wert um genau einen Zinsschritt daneben.

*Die Todesfalldeckung laeuft ueber die Jahre 0 bis n-1.* Wird der
Horizont fuer den Ablauf auf ``n + 1`` gezogen und zahlt das
Leistungsprofil dann auch im Jahr ``n``, kommt ein Jahr Deckung dazu.

Knoten: klv
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

from rechner_pipeline.kern.model_point import ModelPoint
from rechner_pipeline.kern.tafeln import Tafelbasis
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell

AKTIV = "aktiv"
TOT = "tot"


class ZahlungspfadFehler(ValueError):
    """Pfad passt nicht zum Vertrag — fail-fast statt stiller Naeherung."""


@dataclass(frozen=True)
class Zahlungspfad:
    """Der Verlauf eines Vertrags, relativ zu seinen Grundgroessen.

    ``leistung[j]`` ist der Faktor auf die Todesfallleistung im
    Vertragsjahr ``j`` (``0 <= j < n``), ``ablauf`` der Faktor auf die
    Erlebensfallleistung im Jahr ``n``, ``beitrag[j]`` der Faktor auf den
    Beitrag im Jahr ``j`` (``0 <= j < t``).

    Der unveraenderte Vertrag ist ueberall ``1.0``
    (:func:`standardpfad`). Eine Beitragsfreistellung ab Jahr ``a`` setzt
    ``beitrag[j] = 0`` fuer ``j >= a``; eine Herabsetzung auf den
    fortgefuehrten Anteil ``f`` setzt dort ``f``.
    """

    leistung: Tuple[float, ...]
    ablauf: float
    beitrag: Tuple[float, ...]

    def pruefe(self, mp: ModelPoint) -> None:
        if len(self.leistung) != mp.n:
            raise ZahlungspfadFehler(
                f"Leistungsprofil hat {len(self.leistung)} Jahre, der "
                f"Vertrag laeuft {mp.n} — die Deckung laeuft ueber die "
                "Jahre 0 bis n-1, der Ablauf steht getrennt in 'ablauf'"
            )
        if len(self.beitrag) != mp.t:
            raise ZahlungspfadFehler(
                f"Beitragsprofil hat {len(self.beitrag)} Jahre, die "
                f"Beitragszahlungsdauer betraegt {mp.t}"
            )

    @property
    def ist_konstant(self) -> bool:
        """Ob der Pfad der unveraenderte Vertrag ist.

        Nur dann ist der skalare Weg gleichwertig — und nur dann gibt es
        ueberhaupt einen eingefrorenen Referenzwert, gegen den sich
        pruefen laesst.
        """
        return (
            all(w == 1.0 for w in self.leistung)
            and self.ablauf == 1.0
            and all(w == 1.0 for w in self.beitrag)
        )


def standardpfad(mp: ModelPoint) -> Zahlungspfad:
    """Der unveraenderte Vertrag: ueberall Faktor eins."""
    return Zahlungspfad(
        leistung=(1.0,) * mp.n, ablauf=1.0, beitrag=(1.0,) * mp.t
    )


def _modell(basis: Tafelbasis, zins: float) -> Zustandsmodell:
    def uebergang(von: str, nach: str, alter: int, dauer: int) -> float:
        return basis.qx_at(alter) if (von, nach) == (AKTIV, TOT) else 0.0

    return Zustandsmodell((AKTIV, TOT), zins, uebergang)


def _rentenpass(
    modell: Zustandsmodell, x: int, horizont: int, profil: Sequence[float]
) -> List[float]:
    """Vorschuessige Rente ueber ``horizont`` Jahre mit dem Profil."""
    if horizont <= 0:
        return [0.0]
    return modell.barwert_verlauf(
        AKTIV, x, horizont,
        zahlung_zustand=lambda zustand, jahr: (
            profil[jahr] if zustand == AKTIV and jahr < len(profil) else 0.0
        ),
    )


@dataclass(frozen=True)
class Barwertpaesse:
    """Die fuenf Paesse eines Vertrags, je Vertragsjahr.

    Jede Liste traegt den Wert am ANFANG des jeweiligen Vertragsjahres.
    Jenseits ihres Horizonts ist der Wert null; ``wert()`` setzt das ein,
    statt eine IndexError zu werfen.
    """

    axn: Tuple[float, ...]
    axt: Tuple[float, ...]
    azd: Tuple[float, ...]
    tod: Tuple[float, ...]
    erleben: Tuple[float, ...]

    @staticmethod
    def _wert(werte: Tuple[float, ...], a: int) -> float:
        return werte[a] if 0 <= a < len(werte) else 0.0

    def rente_n(self, a: int) -> float:
        return self._wert(self.axn, a)

    def rente_t(self, a: int) -> float:
        return self._wert(self.axt, a)

    def rente_zd(self, a: int) -> float:
        return self._wert(self.azd, a)

    def leistungsbarwert(self, a: int) -> float:
        """Todesfall PLUS Ablauf — die Addition AUSSERHALB der Rekursion.

        Beide Beine in EINEN Pass zu legen bricht die Bit-Exaktheit
        (gemessen: 24 von 31 Vertragsjahren weichen ab).
        """
        return self._wert(self.tod, a) + self._wert(self.erleben, a)


def paesse(mp: ModelPoint, pfad: Zahlungspfad, basis: Tafelbasis) -> Barwertpaesse:
    """Die fuenf Barwertpaesse eines Vertrags mit seinem Zahlungspfad."""
    pfad.pruefe(mp)
    modell = _modell(basis, mp.zins)
    x, n, t, zd = mp.x, mp.n, mp.t, mp.zillmer_dauer

    tod = modell.barwert_verlauf(
        AKTIV, x, n,
        zahlung_uebergang=lambda von, nach, jahr: (
            pfad.leistung[jahr]
            if nach == TOT and jahr < len(pfad.leistung) else 0.0
        ),
    )
    # Horizont n + 1: werte[horizont] ist immer 0.0, und die
    # Ablaufleistung faellt im Jahr n an.
    erleben = modell.barwert_verlauf(
        AKTIV, x, n + 1,
        zahlung_zustand=lambda zustand, jahr: (
            pfad.ablauf if zustand == AKTIV and jahr == n else 0.0
        ),
    )
    return Barwertpaesse(
        # Die Rente ueber die Versicherungsdauer traegt die
        # Verwaltungskosten gamma2 und gamma3 — sie haengen an der
        # Vertragsdauer, nicht am Beitrag, und laufen deshalb mit
        # konstantem Profil. Ob sie bei einem herabgesetzten Vertrag der
        # Summe folgen sollten, ist eine Frage des Tarifwerks und
        # ausdruecklich offen (dev-docs/zahlungspfade-migrierter-
        # vertraege.md); bis sie entschieden ist, bleibt es beim
        # heutigen Verhalten.
        axn=tuple(_rentenpass(modell, x, n, [1.0] * n)),
        axt=tuple(_rentenpass(modell, x, t, pfad.beitrag)),
        azd=tuple(_rentenpass(modell, x, zd, [1.0] * max(zd, 0))),
        tod=tuple(tod),
        erleben=tuple(erleben),
    )


# --------------------------------------------------------------------------- #
# Die zusammengesetzte Reserve
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Pfadzeile:
    """Die Reservegroessen eines Vertragsjahres auf dem Pfadweg.

    Dieselben Groessen wie ``produkte.klv.Verlaufszeile``, nur aus
    Zahlungspfaden statt aus Einheitsbarwerten gebildet. Fuer den
    unveraenderten Vertrag sind beide bit-identisch — das ist die
    Abnahme, ohne die dieser Weg nicht produktiv werden darf.
    """

    jahr: int
    leistungsbarwert: float
    axn: float
    axt: float
    vx_bpfl: float
    drx_bpfl: float
    vx_bfr: float
    vx_mrv: float


def verlaufszeile(
    mp: ModelPoint, pfad: Zahlungspfad, basis: Tafelbasis, a: int,
    *, skalare: Optional[Dict[str, float]] = None,
) -> Pfadzeile:
    """Die Reserve im Vertragsjahr ``a``, gebildet aus dem Zahlungspfad.

    ``skalare`` traegt die vier Vertragskonstanten ``pxt``, ``bjb``,
    ``axn_full``, ``axt_full`` und ``azd_full``. Sie stehen AUSSERHALB
    der Rekursion und werden am unveraenderten Vertrag bestimmt: Der
    Beitragssatz wurde bei Abschluss festgelegt und aendert sich durch
    eine spaetere Herabsetzung nicht — geaendert hat sich, wie viel
    davon tatsaechlich gezahlt wird, und genau das steht im Pfad.

    Ohne ``skalare`` werden sie aus dem Standardpfad des Modellpunkts
    gerechnet; das ist der Normalfall.
    """
    p = paesse(mp, pfad, basis)
    if skalare is None:
        skalare = vertragskonstanten(mp, basis)

    axn = p.rente_n(a)
    axt = p.rente_t(a)
    azd = p.rente_zd(a)
    leistung = p.leistungsbarwert(a) if a <= mp.n else 0.0

    kvx_bpfl = (
        leistung
        - skalare["pxt"] * axt
        + mp.gamma2 * (axn - (skalare["axn_full"] / skalare["axt_full"]) * axt)
    )
    kdrx_bpfl = mp.sum_insured * kvx_bpfl
    kvx_bfr = leistung + mp.gamma3 * axn
    kvx_mrv = kdrx_bpfl + (
        mp.alpha * mp.t * skalare["bjb"] * azd / skalare["azd_full"]
    )
    return Pfadzeile(
        jahr=a, leistungsbarwert=leistung, axn=axn, axt=axt,
        vx_bpfl=kvx_bpfl, drx_bpfl=kdrx_bpfl, vx_bfr=kvx_bfr, vx_mrv=kvx_mrv,
    )


def vertragskonstanten(mp: ModelPoint, basis: Tafelbasis) -> Dict[str, float]:
    """Die Skalare des UNVERAENDERTEN Vertrags.

    Sie beschreiben die Preisbildung bei Abschluss und bleiben von einer
    spaeteren Herabsetzung unberuehrt. Sie kommen aus dem KLV-Produkt,
    damit es genau eine Wahrheit dafuer gibt — der Pfadweg baut die
    Beitragsermittlung nicht ein zweites Mal nach.
    """
    from rechner_pipeline.kern.produkte.klv import KLV

    kern = KLV(mp)
    p = paesse(mp, standardpfad(mp), basis)
    return {
        "pxt": kern.net_premium_rate(),
        "bjb": kern.gross_annual_premium(),
        "axn_full": p.rente_n(0),
        "axt_full": p.rente_t(0),
        "azd_full": p.rente_zd(0),
    }
