"""Der stabile Rechenkern — Thiele-/Zustandsmodell-Welt, parametrisierte API.

Beschluss Projektleitung/Aktuariat 2026-08-11: Der Rechenkern ist stabile,
versionierte Software; das KI-System baut marginale Aenderungen ein
(neue Tarifgeneration = Parametrierung, neues Produkt = Konfiguration
des Rueckgrats), die Abnahme-Gates nehmen sie ab.

Beschluss 2026-08-16 (Maintainer): Der Kern ist vollstaendig in der
Zustandsmodell-Welt — die historische Excel-Paritaet (617/617) war die
EINMALIGE Abnahme des Uebersetzungsakts und ist KEIN laufender Referenzwert
mehr; die klassischen Kommutationsspalten sind kein Bestandteil des
Kerns, sondern leben als separater Zweitkern
(:mod:`rechner_pipeline.kommutationskern`). Seit ADR-013 hat er KEINEN
Konsumenten im Produktivpfad mehr: Die Toleranz-Ueberleitung ist ausser
Betrieb, und der Zweitkern lebt nur noch als unabhaengiger Zeuge der
algebraischen Eigenschaftstests, die ihn testseitig direkt bauen.

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

1. Die eingefrorenen Referenzwerte (``tests/fixtures/kern_referenzwerte/``) halten
   das Verhalten repraesentativer Modellpunkte in VOLLER Float-Praezision
   — sie sind die Regressionssicherung des Kerns. Ein Diff dort
   braucht eine fachliche Begruendung im selben Commit (bewusste Abnahme
   statt stiller Drift).
2. *(entfallen mit ADR-013.)* Die Toleranz-Ueberleitung gegen den
   Kommutationskern war der Uebersetzungsbeleg des Backbone-Wechsels
   und ist erbracht. Was von der Unabhaengigkeit bleibt, steht in den
   algebraischen Eigenschaftstests: Sie halten die Durchreicher
   ``pv_benefits``/``pv_premiums``/``net_premium`` gegen den Zweitkern,
   damit dort nicht der Methodenrumpf gegen sich selbst prueft.
3. Die algebraischen Eigenschaften (qa_contract, Hypothesis) muessen
   halten.
4. Je MIGRATIONSFALL gilt der Generations-Golden-Master (Gate P-K1):
   der Kern, parametriert ueber die Tarif-Spez, reproduziert die
   Erwartungswerte des jeweiligen QUELL-Rechners — das ist Fall-Abnahme,
   kein Referenzwert des Kerns.
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

#: Kern-Version (Abnahme-Referenz, siehe Docstring).
#: 1.x/2.x = Migrations- und Backbone-Aera (Historie in Git).
#: 3.0.0 = Zielbild-Schnitt (Beschluss Maintainer 2026-08-16): Kern
#: vollstaendig in der Zustandsmodell-Welt; Kommutation als separater
#: Zweitkern (rechner_pipeline.kommutationskern), seit ADR-013 ohne
#: Konsumenten im Produktivpfad und nur noch Zeuge der algebraischen
#: Eigenschaftstests;
#: Excel-Paritaet 617/617 als Kern-Referenzwert entfernt (sie war die einmalige
#: Abnahme des Uebersetzungsakts); Tafel-Schicht eigenstaendig
#: (kern/tafeln.py, Erschoepfungs-Domaene rein aus qx); Verlaufswerte
#: modellpunktgetrieben statt blattfest 0..50. Rechenwerte unveraendert
#: (reiner Schnitt: qx-Pfad identisch, Referenzwerte gruen).
#: 3.0.1 = Kern-XML-Ladevertrag prueft qx-Domaene und den exakten
#: Altersbereich fail-fast; Rechenwerte und Tafelbytes bleiben unveraendert.
#: 3.1.0 = Folgebewertung herabgesetzter Vertraege (beitragsreduktion.
#: ReduzierterVertrag): Zweiteilung in fortgefuehrten Anteil und fixierte
#: beitragsfreie Summe, vertragsweiter Stornoabschlag auf der neuen
#: Gesamtsumme, spaetere Beitragsfreistellung und terminale Leistungen.
#: Additive Faehigkeit fuer migrierte Bestaende mit RED-Vorgeschichte
#: (Baldrian-Uebernahme); bestehende Rechenwerte unveraendert.
#: 3.2.0 = Scheiben-gamma1 als Tarifwerks-Eigenschaft der Lieferung
#: (erhoehungs_scheibe, Parameter gamma1_uebernehmen; Vorgabe =
#: GrundVS-Regel der ersten Lieferung); Rechenwerte der Vorgabe
#: unveraendert.
#: 3.3.0 = Stornoabschlag-Grenzen wahlweise JE BAUSTEIN
#: (vertrags_monatsreserve, Parameter stoab_je_baustein; Vorgabe =
#: vertragsweit, Tarifplan 6): Abzug je Grund- und Erhoehungsscheibe
#: einzeln geklemmt, RKW = Summe der auf null begrenzten
#: Baustein-Rueckkaufswerte (Bedingungswerk der zweiten
#: Baldrian-Lieferung, Ziffer 4); Rechenwerte der Vorgabe unveraendert.
#: 3.4.0 = Teilkuendigung auch im beitragsfreien Nachlauf (t <= jahr
#: < n): Ziffer 6 kuendigt einen Summen-Anteil und setzt keinen
#: laufenden Beitrag voraus — die Beitragsende-Wache gilt nur den
#: beitragssenkenden Verfahren; alle bestehenden Rechenwerte
#: unveraendert.
__version__ = "3.4.0"

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
