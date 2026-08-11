"""Der stabile KLV-Rechenkern — versionierte Software, parametrisierte API.

Beschluss 2026-08-11 (Bartek/Leo): Der Rechenkern ist keine transiente,
pro Lauf neu generierte Ausgabe mehr, sondern **stabile, versionierte
Software** — ein Stück Software zusammen mit dem Bestand und Tests. Das
KI-System baut künftig marginale Änderungen ein (neue Tarifgeneration,
neues Produkt); die Assurance nimmt Änderungen ab.

Provenienz: Dieses Paket ist die Promotion des am 2026-07-22 agentisch aus
``examples/Tarifrechner_KLV.xlsm`` migrierten und mechanisch angenommenen
Kerns (assurance ACCEPTED, Golden-Master 617/617) — der einmalige
Übersetzungsakt der Migrationsmethode. Beim Promoten wurde die Bindung an
einen festen Modellpunkt (``inputs.DEFAULT``) durch eine **parametrisierte
API** ersetzt: jede Rechnung nimmt einen :class:`ModelPoint` entgegen;
Kommutationswerte werden je (Geschlecht, Tafel, Zins) aufgebaut und
gecacht. Die Formeln selbst sind unverändert (Excel-/VBA-treu, 16-stellige
Excel-Rundung); die Parität ist testseitig gegen die extrahierten
Erwartungswerte verankert (617/617).

Öffentliche API::

    from rechner_pipeline.kern import ModelPoint, KLV_DEFAULT, Rechenkern, berechne

    ergebnis = berechne(KLV_DEFAULT)          # {"scalars": ..., "tables": ...}
    kern = Rechenkern(mp)                     # feinere Zugriffe (reserve_row, ...)
"""

from rechner_pipeline.kern.kommutation import Kommutation, MissingMortalityTableError
from rechner_pipeline.kern.konventionen import excel_round, installment_surcharge
from rechner_pipeline.kern.model_point import KLV_DEFAULT, ModelPoint
from rechner_pipeline.kern.rechenkern import Rechenkern, berechne

__all__ = [
    "ModelPoint",
    "KLV_DEFAULT",
    "Rechenkern",
    "berechne",
    "Kommutation",
    "MissingMortalityTableError",
    "excel_round",
    "installment_surcharge",
]
