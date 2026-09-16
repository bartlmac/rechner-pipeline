# ADR-004: Der Zielkern ist Thiele-Welt — Excel-Paritaet ist Uebersetzungsbeleg, kein laufender Referenzwert

Status: akzeptiert (Maintainer, 2026-08-16). Umgesetzt: Kern 3.0.0
(`kern/tafeln.py`, `rechner_pipeline.kommutationskern`).

> **Punkt 2 abgeloest durch [ADR-013](adr-013-kommutations-kreuzcheck-ausser-betrieb.md)
> (2026-08-28):** Der Kommutations-Zweitkern und der Kreuz-Check sind
> ausser Betrieb. Der Uebersetzungsbeleg ist erbracht und bleibt hier
> zitierbar; die Sicherung des Kernverhaltens tragen seither die
> eingefrorenen Referenzwerte. Alles Uebrige dieser Entscheidung gilt
> unveraendert.

## Kontext

Der Zielkern rechnet seit Version 2.0.0 auf einem
(Semi-)Markov-Zustandsmodell mit Thiele-Rekursion — trug aber weiter
drei Bezuege zur Excel-Historie mit sich:

1. Die **617/617-Excel-Paritaet** (einmalige Uebersetzungsabnahme vom
   22.07.2026) lief als dauerhafter Kern-Test mit eingecheckten
   Erwartungswert-Fixtures weiter — als waere sie ein laufender Referenzwert.
2. **Kommutationswerte** (D/N/C/M) lebten als `kern/kommutation.py` im
   Kern, obwohl der produktive Pfad sie nirgends braucht: das
   Zustandsmodell konsumiert ausschliesslich reine qx-Vektoren.
3. Der Verlauf war **blattfest auf 51 Zeilen (0..50)** gedeckelt — die
   Zeilenzahl des Quell-Verlaufsblatts als Domaenengrenze des Kerns.

Das widerspricht dem Zielbild: ein zielbildfaehiges Geraet fuer die
Bestandsmigration, dessen Abnahme je Migrationsfall gegen den
jeweiligen Quell-Rechner laeuft (Gate P-K1) — nicht dauerhaft gegen das
eine historische Workbook.

## Entscheidung

1. **Der Kern ist vollstaendige Zustandsmodell-Welt.** Neue unterste
   Fachschicht `kern/tafeln.py`: `Tafelbasis` = reiner qx-Vektor je
   (Geschlecht, Tafel) samt Erschoepfungsgrenze (erstes Alter nach
   qx >= 1 — nachweislich aequivalent zum frueheren Dx=0-Kriterium),
   gecacht, fail-fast bei fehlender Tafel oder Bereichsverletzung.
   `ZustandsBarwerte` und die Produkte konsumieren `Tafelbasis`,
   keine Kommutation.
2. **Kommutation wird separater Zweitkern**:
   `rechner_pipeline.kommutationskern` (Kommutationswerte + klassische
   Barwerte). Einziger Zweck ist der Kreuz-Check der Rechenschienen
   (`qa/ueberleitung`, Toleranz-Ueberleitung). Kein Modul des Zielkerns
   importiert ihn.
3. **Die 617/617-Paritaet ist Geschichte des Uebersetzungsakts.** Der
   Dauertest und die Fixtures (`tests/fixtures/kern_klv/`) sind
   entfernt; Doku nennt sie nur noch als historischen
   Uebersetzungsbeleg. Festgeschrieben ist der Kern ueber
   Charakterisierungs-Referenzwerte in voller Float-Praezision; die fachliche
   Abnahme je Migrationsfall ist Gate P-K1 gegen den Quell-Rechner.
4. **Der Verlauf ist modellpunktgetrieben** (`verlaufswerte()` bis n,
   `verlaufszeile(a)` bis zur Tafel-Erschoepfung). Das 51-Zeilen-Fenster
   bleibt als expliziter Vergleichs-Contract der `berechne()`-View
   erhalten — je Produkt deklariert (`contract_verlauf_bis`; KLV: 50,
   Zeilenformat des Quell-Verlaufsblatts; BU: n).

## Konsequenzen

- Kern-`__version__` 3.0.0; das Abnahme-Protokoll im
  `kern/__init__`-Docstring beschreibt den neuen Stand (Referenzwerte,
  Ueberleitung, algebraische Gates, Gate P-K1 je Fall).
- Rechenwerte sind unveraendert: der produktive Pfad nutzte schon
  vorher ausschliesslich qx. Beleg: alle Charakterisierungs-Referenzwerte
  bit-exakt gruen, Gate P-K1 des Praezedenzfalls klv-tg2015 weiter
  616 Werte / 0 Abweichungen.
- Die Bestand-Engine behaelt ihr Verlaufsfenster 0..50 als EIGENE
  konservative Grenze (so dokumentiert); sie ist Kandidat fuer eine
  tafelbewusste Endalter-Pruefung je Generation (Roadmap).
- `berechne()` bleibt die Golden-Master-Contract-View fuer
  Fall-Abnahmen; ihre Fensterung ist Produkt-Contract, kein Kern-Referenzwert.
- Kuenftige Produkte definieren ihren Verlaufs-Contract selbst; nichts
  zwingt sie in die Geometrie des historischen KLV-Workbooks.

## Verworfene Alternative

Kommutation als "tote" Schicht im Kern belassen und nur den 617-Test
streichen: liesse die irrefuehrende Architekturaussage stehen, der
Kern rechne auf Kommutationswerten — genau die Verwechslung von
Uebersetzungshistorie und Zielbild, die dieses ADR beendet.
