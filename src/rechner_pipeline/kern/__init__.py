"""Der stabile Rechenkern — Thiele-/Zustandsmodell-Welt, parametrisierte API.

Beschluss Projektleitung/Aktuariat 2026-08-11: Der Rechenkern ist stabile,
versionierte Software; das KI-System baut marginale Aenderungen ein
(neue Tarifgeneration = Parametrierung, neues Produkt = Konfiguration
des Rueckgrats), die Abnahme-Gates nehmen sie ab.

Beschluss 2026-08-16 (Bartek): Der Kern ist vollstaendig in der
Zustandsmodell-Welt — die historische Excel-Paritaet (617/617) war die
EINMALIGE Abnahme des Uebersetzungsakts und ist KEIN Anker des Kerns
mehr; die klassischen Kommutationsspalten sind kein Bestandteil des
Kerns, sondern leben als separater Zweitkern
(:mod:`rechner_pipeline.kommutationskern`) ausschliesslich fuer die
Kreuz-Rechenschiene der QA.

Schichten::

    konventionen    Rundung, Endalter, Zahlweise-Staffel (unterste Schicht)
    tafeln          Rechnungsgrundlagen: tafeln.xml, Tafelbasis (reine qx),
                    Erschoepfungs-Domaene, Select-Tafeln
    zustandsmodell  (Semi-)Markov-Rueckgrat: Thiele-Rueckwaertsrekursion,
                    ZustandsBarwerte (Barwert-Bausteine auf dem Rueckgrat)
    produkte/       Produkt-Registry; Zielgroessen in produkte/<produkt>.py
    rechenkern      Fassade Rechenkern(mp) + berechne(mp, produkt=...)

Oeffentliche API::

    from rechner_pipeline.kern import ModelPoint, Rechenkern, berechne

Namensschema (Provenienz-Prinzip): Fachgroessen mit Quell-Provenienz
behalten den Quellnamen (``Bxt``, ``kVx_MRV``, ``axn_k``) — der Name IST
der Herkunftsbeleg; Ablauf-/Strukturnamen sind deutsch.

Abnahme-Protokoll fuer Kern-Aenderungen:

1. Die Charakterisierungs-Anker (``tests/fixtures/kern_anker/``) frieren
   das Verhalten repraesentativer Modellpunkte in VOLLER Float-Praezision
   ein — sie sind die Regressions-Verankerung des Kerns. Ein Diff dort
   braucht eine fachliche Begruendung im selben Commit (bewusste Abnahme
   statt stiller Drift).
2. Die Toleranz-Ueberleitung (:mod:`rechner_pipeline.qa.ueberleitung`)
   gegen den separaten Kommutationskern muss in der Rundungsklasse
   bleiben — zwei unabhaengige Rechenwege, eine Toleranz.
3. Die algebraischen Eigenschaften (qa_contract, Hypothesis) muessen
   halten.
4. Je MIGRATIONSFALL gilt der Generations-Golden-Master (Gate O3):
   der Kern, parametriert ueber die Tarif-Spez, reproduziert die
   Erwartungswerte des jeweiligen QUELL-Rechners — das ist Fall-Abnahme,
   kein Kern-Anker.
5. ``__version__`` wird bei jeder fachlichen Aenderung angehoben und im
   Commit begruendet.

Knoten: klv, bu
"""

from rechner_pipeline.kern.konventionen import excel_round, installment_surcharge
from rechner_pipeline.kern.model_point import KLV_DEFAULT, KLVModelPoint, ModelPoint
from rechner_pipeline.kern.tafeln import (
    MissingMortalityTableError,
    TafelBereichError,
    Tafelbasis,
)
from rechner_pipeline.kern.zustandsmodell import Zustandsmodell, ZustandsBarwerte
from rechner_pipeline.kern.rechenkern import (
    Monatsreserve,
    Rechenkern,
    Verlaufszeile,
    berechne,
    erhoehungs_scheibe,
    vertrags_monatsreserve,
)

#: Kern-Version (Abnahme-Anker, siehe Docstring).
#: 1.x/2.x = Migrations- und Backbone-Aera (Historie in Git).
#: 3.0.0 = Zielbild-Schnitt (Beschluss Bartek 2026-08-16): Kern
#: vollstaendig in der Zustandsmodell-Welt; Kommutation als separater
#: Zweitkern (rechner_pipeline.kommutationskern) nur noch Kreuzschiene;
#: Excel-Paritaet 617/617 als Kern-Anker entfernt (sie war die einmalige
#: Abnahme des Uebersetzungsakts); Tafel-Schicht eigenstaendig
#: (kern/tafeln.py, Erschoepfungs-Domaene rein aus qx); Verlaufswerte
#: modellpunktgetrieben statt blattfest 0..50. Rechenwerte unveraendert
#: (reiner Schnitt: qx-Pfad identisch, Anker gruen).
#: 3.0.1 = Kern-XML-Ladevertrag prueft qx-Domaene und den exakten
#: Altersbereich fail-fast; Rechenwerte und Tafelbytes bleiben unveraendert.
__version__ = "3.0.1"

__all__ = [
    "ModelPoint",
    "KLVModelPoint",
    "KLV_DEFAULT",
    "Rechenkern",
    "berechne",
    "Zustandsmodell",
    "ZustandsBarwerte",
    "Verlaufszeile",
    "Monatsreserve",
    "erhoehungs_scheibe",
    "vertrags_monatsreserve",
    "Tafelbasis",
    "MissingMortalityTableError",
    "TafelBereichError",
    "excel_round",
    "installment_surcharge",
    "__version__",
]
