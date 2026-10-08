"""Das Tarifwerk der Quelle: die sechs Zellen der TG2015.

Das QUELLSYSTEM fuehrt sein eigenes Tarifwerk — dieselben Werte, die die
Tarifmeldung an die PLV liefert (und die dort als Spez ankommen), aber
hier als eigener Bestand: Ein Quellsystem liest seine Rechnungsgrundlagen
nicht beim aufnehmenden Unternehmen nach.

Zwei Dimensionen (status x tarifart), sechs Zellen; unisex-Tafeln nach
Raucherstatus. Werte deckungsgleich mit der gelieferten Tarifmeldung
KLV TG2015 — wer hier etwas aendert, aendert die QUELLE und muss neue
Lieferungen erzeugen.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Mapping, Tuple


@dataclass(frozen=True)
class Tarifzelle:
    status: str
    tarifart: str
    tafel: str
    zins: float
    alpha: float
    beta1: float
    gamma1: float
    gamma2: float
    gamma3: float
    policy_fee: float
    min_alter_flex: int
    min_rlz_flex: int
    stoab_satz: float
    stoab_min: float
    stoab_max: float
    zillmer_dauer: int
    ratzu: Mapping[int, float]  # Zahlweise -> Zuschlag; 1 -> 0.0


def _zelle(status: str, tarifart: str, tafel: str, **felder) -> Tarifzelle:
    return Tarifzelle(status=status, tarifart=tarifart, tafel=tafel,
                      zins=0.0125, min_alter_flex=60, min_rlz_flex=5,
                      zillmer_dauer=5, gamma3=0.0025, **felder)


_EINZEL = dict(alpha=0.025, beta1=0.03, gamma1=0.001, gamma2=0.00125,
               policy_fee=12.0, stoab_satz=0.005, stoab_min=50.0,
               stoab_max=200.0, ratzu={2: 0.02, 4: 0.03, 12: 0.05})
_KOLLEKTIV = dict(alpha=0.015, beta1=0.015, gamma1=0.0008, gamma2=0.001,
                  policy_fee=12.0, stoab_satz=0.005, stoab_min=50.0,
                  stoab_max=200.0, ratzu={2: 0.01, 4: 0.015, 12: 0.025})
_HAUS = dict(alpha=0.0, beta1=0.01, gamma1=0.0008, gamma2=0.001,
             policy_fee=0.0, stoab_satz=0.0, stoab_min=0.0,
             stoab_max=0.0, ratzu={2: 0.0, 4: 0.0, 12: 0.0})

TAFEL = {"Nichtraucher": "DAV2008_T_NR_U70", "Raucher": "DAV2008_T_R_U70"}

ZELLEN: Dict[Tuple[str, str], Tarifzelle] = {
    (status, tarifart): _zelle(status, tarifart, TAFEL[status], **felder)
    for status in ("Nichtraucher", "Raucher")
    for tarifart, felder in (
        ("Einzel", _EINZEL), ("Kollektiv", _KOLLEKTIV), ("Haus", _HAUS),
    )
}


def zelle(status: str, tarifart: str) -> Tarifzelle:
    """Die Tarifzelle — fail-fast bei unbekannter Kombination."""
    schluessel = (status, tarifart)
    if schluessel not in ZELLEN:
        raise KeyError(
            f"Tarifzelle {schluessel!r} unbekannt — bekannt: "
            f"{sorted(ZELLEN)}"
        )
    return ZELLEN[schluessel]
