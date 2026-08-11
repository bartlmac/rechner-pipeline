"""Modellpunkt des KLV-Rechenkerns (Vertrags-/Tarif-/Grenzdaten).

Reine Datenschicht ohne Rechenlogik. Die Feldliste ist der Input-Contract des
Kerns; das Bestandsmodul (:mod:`rechner_pipeline.models.bestand`) hält seine
``MODEL_POINT_FIELDS`` deckungsgleich dazu (per Test verankert).

Provenienz der Felder (Defined Names des Quell-Workbooks):
  x=B4, Sex=B5, n=B6, t=B7, VS=B8, zw=B9,
  Zins=E4, Tafel=E5, alpha=E6, beta1=E7, gamma1=E8, gamma2=E9, gamma3=E10,
  k(E11)=policy_fee, MinAlterFlex=H4, MinRLZFlex=H5.

Die Tarifwerk-Stellschrauben (Stornoabschlag, Zillmer-Amortisationsdauer,
Ratenzuschlag-Staffel) standen im Quell-Workbook als Formel-Literale im Blatt
(Verlaufswerte-Zeilen bzw. E12). Sie sind hier als Felder mit den Blattwerten
als Default gehoben: eine neue Tarifgeneration ist damit eine reine
Parametrierung des Modellpunkts, keine Formeländerung. Defaults unverändert
lassen == Blattverhalten (Golden-Master 617/617).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPoint:
    """Ein KLV-Vertrag (gemischte Kapitallebensversicherung) als Kern-Input."""

    # -- Vertragsdaten --
    x: int              # Eintrittsalter
    sex: str            # "M" oder "F"
    n: int              # Versicherungsdauer in Jahren
    t: int              # Beitragszahlungsdauer in Jahren
    sum_insured: float  # Versicherungssumme (VS)
    zw: int             # Zahlweise (Beitraege pro Jahr)

    # -- Tarifdaten --
    zins: float         # Rechnungszins (jaehrlich effektiv)
    tafel: str          # Sterbetafel-Id (z. B. "DAV1994_T")
    alpha: float        # Abschlusskostensatz (Zillmer)
    beta1: float        # Inkassokostensatz auf den Beitrag
    gamma1: float       # Verwaltungskostensatz 1
    gamma2: float       # Verwaltungskostensatz 2
    gamma3: float       # Verwaltungskostensatz 3 (beitragsfrei)
    policy_fee: float   # Stueckkosten k (E11)

    # -- Grenzen (flexible Phase) --
    min_alter_flex: int
    min_rlz_flex: int

    # -- Tarifwerk-Stellschrauben (Defaults = Blatt-Literale des Workbooks) --
    stoab_satz: float = 0.01    # Stornoabschlag-Satz auf (VS - kDRx_bpfl)
    stoab_min: float = 50.0     # Stornoabschlag-Untergrenze
    stoab_max: float = 150.0    # Stornoabschlag-Obergrenze
    zillmer_dauer: int = 5      # Amortisationsdauer der Zillmerung in Jahren
    ratzu_zw2: float = 0.02     # Ratenzuschlag zw=2 (E12-Staffel)
    ratzu_zw4: float = 0.03     # Ratenzuschlag zw=4
    ratzu_zw12: float = 0.05    # Ratenzuschlag zw=12


#: Produktzugehörigkeit explizit: dieser ModelPoint ist der KLV-Contract.
#: Ein späteres zweites Produkt bekommt eine eigene ModelPoint-Klasse.
KLVModelPoint = ModelPoint

#: Der Standard-Modellpunkt des Quell-Workbooks (Golden-Master-Referenzvertrag).
KLV_DEFAULT = ModelPoint(
    x=45,
    sex="M",
    n=30,
    t=20,
    sum_insured=100000.0,
    zw=12,
    zins=0.0175,
    tafel="DAV1994_T",
    alpha=0.025,
    beta1=0.025,
    gamma1=0.0008,
    gamma2=0.00125,
    gamma3=0.0025,
    policy_fee=24.0,
    min_alter_flex=60,
    min_rlz_flex=5,
)
