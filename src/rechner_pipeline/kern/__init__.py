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
API** ersetzt; das anschließende Skalierungs-Refactoring hat die Schichten
für die KI-Evolution geschnitten. Die Formeln selbst sind unverändert
(Excel-/VBA-treu, 16-stellige Excel-Rundung).

Schichten::

    konventionen    Radix, Excel-Rundung, Endalter (unterste Rechenschicht)
    kommutation     Kommutationsspalten je Basis (Sex/Tafel/Zins), gecacht
    barwerte        generische Barwert-Bausteine (VBA mBarwerte), produktfrei
    zustandsmodell  (Semi-)Markov-Rechenrückgrat + ZustandsBarwerte
                    (2-Zustands-Fall, gleiches Interface wie barwerte)
    produkte/       Produkt-Registry; KLV-Zielgrößen in produkte/klv.py
    rechenkern      Fassade Rechenkern(mp) + berechne(mp, produkt="klv")

Rechenrückgrat (Beschluss 2026-08-12): Das Zustandsmodell ist das Rückgrat
des Monolithen (KLV = 2-Zustands-Spezialfall, künftige Produkte =
Konfigurationen). Der Wechsel des produktiven KLV-Pfads von der
Kommutations- auf die Zustandsmodell-Schiene wurde per Toleranz-Überleitung
abgenommen (Bartek, 2026-08-12: 6170 Werte über 10 Modellpunkte, 0
außerhalb der Rundungsklasse, max. 4e-13 relativ) — seither rechnet KLV
produktiv auf dem Zustandsmodell. Die Kommutations-Schiene bleibt dauerhaft
als Kreuz-Check-Schiene erhalten
(:mod:`rechner_pipeline.qa.ueberleitung` injiziert beide explizit).

Öffentliche API::

    from rechner_pipeline.kern import ModelPoint, KLV_DEFAULT, Rechenkern, berechne

    ergebnis = berechne(KLV_DEFAULT)          # {"scalars": ..., "tables": ...}
    kern = Rechenkern(mp)                     # feinere Zugriffe (reserve_row,
                                              # zustand_am, beitragsfreie_summe)

Namensschema (Provenienz-Prinzip):

* Fachgrößen mit Blatt-/VBA-Provenienz behalten den QUELLNAMEN — ``axn_k``,
  ``nGrAx``, ``abzugsglied``, Output-Keys ``Bxt``/``Pxt``/``kVx_MRV``/
  ``"flex. Phase"``. Das ist keine Inkonsistenz, sondern Migrations-Gold:
  der Name IST der Beleg der Herkunft.
* Ablauf-/Struktur-Namen (Klassen, neue Operationen) sind deutsch
  (``Rechenkern``, ``berechne``, ``verlaufszeile``, ``zustand_am``).
* Die Golden-Master-View (dict-Keys, Fixture-Namen) wird NIE umbenannt.

Abnahme-Protokoll für marginale Kern-Änderungen:

1. ``pytest tests/test_kern.py`` — die Excel-Parität (617/617 gegen
   ``tests/fixtures/kern_klv/``) MUSS grün bleiben; diese Fixtures zu
   ändern ist verboten (sie sind die Quelle der Wahrheit der Migration).
2. Die Charakterisierungs-Anker (``tests/fixtures/kern_anker/``) frieren
   das Verhalten weiterer Modellpunkte ein. Ein Diff dort ist erlaubt,
   braucht aber eine fachliche Begründung und wird mit der Änderung
   zusammen committet (bewusste Abnahme statt stiller Drift).
3. ``__version__`` wird bei jeder fachlichen Änderung angehoben und die
   Änderung im Commit begründet (Tarifgeneration/Produkt/Fix).
"""

from rechner_pipeline.kern.kommutation import (
    Kommutation,
    MissingMortalityTableError,
    TafelBereichError,
)
from rechner_pipeline.kern.konventionen import excel_round, installment_surcharge
from rechner_pipeline.kern.model_point import KLV_DEFAULT, KLVModelPoint, ModelPoint
from rechner_pipeline.kern.barwerte import Barwerte
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell, ZustandsBarwerte
from rechner_pipeline.kern.rechenkern import (
    Rechenkern,
    Verlaufszeile,
    berechne,
)

#: Kern-Version (Abnahme-Anker für marginale Änderungen, siehe Docstring).
#: 1.0.0 = Promotion 2026-08-11 des am 2026-07-22 migrierten Kerns
#: inklusive Skalierungs-Refactoring (verhaltensgleich, 617/617).
#: 1.0.1 = Domänengrenze: Verlaufszeilen nur im blattfest verankerten
#: Bereich 0..50 (Fail-fast statt unbelegter Werte ausserhalb des
#: Golden-Master-/Anker-Bereichs; Rechenwerte unverändert, 617/617 + Anker).
#: 1.1.0 = Zustandsmodell-Rückgrat (Semi-Markov-Engine + ZustandsBarwerte,
#: additiv; produktiver Pfad unverändert Kommutation).
#: 2.0.0 = Wechsel des produktiven KLV-Pfads auf das Zustandsmodell
#: (abgenommene Toleranz-Überleitung: 6170 Werte, 0 abweichend, max.
#: 4e-13 relativ; Anker-Fixtures mit Begründung neu eingefroren;
#: 617/617-Excel-Fixtures unverändert grün — compare rundet auf 4
#: Nachkommastellen, die Differenzen liegen bei 1e-13).
__version__ = "2.0.0"

__all__ = [
    "ModelPoint",
    "KLVModelPoint",
    "KLV_DEFAULT",
    "Rechenkern",
    "berechne",
    "Barwerte",
    "Zustandsmodell",
    "ZustandsBarwerte",
    "Verlaufszeile",
    "Kommutation",
    "MissingMortalityTableError",
    "TafelBereichError",
    "excel_round",
    "installment_surcharge",
    "__version__",
]
