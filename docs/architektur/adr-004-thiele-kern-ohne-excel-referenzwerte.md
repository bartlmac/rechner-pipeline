# ADR-004: Der Zielkern ist Thiele-Welt — Excel-Parität ist Übersetzungsbeleg, kein laufender Referenzwert

Status: akzeptiert (Maintainer, 2026-08-16). Umgesetzt: Kern 3.0.0
(`kern/tafeln.py`, `rechner_pipeline.kommutationskern`).

> **Punkt 2 abgelöst durch [ADR-013](adr-013-kommutations-kreuzcheck-ausser-betrieb.md)
> (2026-08-28):** Der Kommutations-Zweitkern und der Kreuz-Check sind
> ausser Betrieb. Der Übersetzungsbeleg ist erbracht und bleibt hier
> zitierbar; die Sicherung des Kernverhaltens tragen seither die
> eingefrorenen Referenzwerte. Alles Übrige dieser Entscheidung gilt
> unverändert.

## Kontext

Der Zielkern rechnet seit Version 2.0.0 auf einem
(Semi-)Markov-Zustandsmodell mit Thiele-Rekursion — trug aber weiter
drei Bezüge zur Excel-Historie mit sich:

1. Die **617/617-Excel-Paritaet** (einmalige Übersetzungsabnahme vom
   22.07.2026) lief als dauerhafter Kern-Test mit eingecheckten
   Erwartungswert-Fixtures weiter — als wäre sie ein laufender Referenzwert.
2. **Kommutationswerte** (D/N/C/M) lebten als `kern/kommutation.py` im
   Kern, obwohl der produktive Pfad sie nirgends braucht: das
   Zustandsmodell konsumiert ausschliesslich reine qx-Vektoren.
3. Der Verlauf war **blattfest auf 51 Zeilen (0..50)** gedeckelt — die
   Zeilenzahl des Quell-Verlaufsblatts als Domänengrenze des Kerns.

Das widerspricht dem Zielbild: ein zielbildfähiges Gerät für die
Bestandsmigration, dessen Abnahme je Migrationsfall gegen den
jeweiligen Quell-Rechner läuft (Gate P-K1) — nicht dauerhaft gegen das
eine historische Workbook.

## Entscheidung

1. **Der Kern ist vollständige Zustandsmodell-Welt.** Neue unterste
   Fachschicht `kern/tafeln.py`: `Tafelbasis` = reiner qx-Vektor je
   (Geschlecht, Tafel) samt Erschöpfungsgrenze (erstes Alter nach
   qx >= 1 — nachweislich äquivalent zum früheren Dx=0-Kriterium),
   gecacht, fail-fast bei fehlender Tafel oder Bereichsverletzung.
   `ZustandsBarwerte` und die Produkte konsumieren `Tafelbasis`,
   keine Kommutation.
2. **Kommutation wird separater Zweitkern**:
   `rechner_pipeline.kommutationskern` (Kommutationswerte + klassische
   Barwerte). Einziger Zweck ist der Kreuz-Check der Rechenschienen
   (`qa/ueberleitung`, Toleranz-Überleitung). Kein Modul des Zielkerns
   importiert ihn.
3. **Die 617/617-Paritaet ist Geschichte des Übersetzungsakts.** Der
   Dauertest und die Fixtures (`tests/fixtures/kern_klv/`) sind
   entfernt; Doku nennt sie nur noch als historischen
   Übersetzungsbeleg. Festgeschrieben ist der Kern über
   Charakterisierungs-Referenzwerte in voller Float-Präzision; die fachliche
   Abnahme je Migrationsfall ist Gate P-K1 gegen den Quell-Rechner.
4. **Der Verlauf ist modellpunktgetrieben** (`verlaufswerte()` bis n,
   `verlaufszeile(a)` bis zur Tafel-Erschöpfung). Das 51-Zeilen-Fenster
   bleibt als expliziter Vergleichs-Contract der `berechne()`-View
   erhalten — je Produkt deklariert (`contract_verlauf_bis`; KLV: 50,
   Zeilenformat des Quell-Verlaufsblatts; BU: n).

## Konsequenzen

- Kern-`__version__` 3.0.0; das Abnahme-Protokoll im
  `kern/__init__`-Docstring beschreibt den neuen Stand (Referenzwerte,
  Überleitung, algebraische Gates, Gate P-K1 je Fall).
- Rechenwerte sind unverändert: der produktive Pfad nutzte schon
  vorher ausschliesslich qx. Beleg: alle Charakterisierungs-Referenzwerte
  bit-exakt grün, Gate P-K1 des Präzedenzfalls klv-tg2015 weiter
  616 Werte / 0 Abweichungen.
- Die Bestand-Engine behält ihr Verlaufsfenster 0..50 als EIGENE
  konservative Grenze (so dokumentiert); sie ist Kandidat für eine
  tafelbewusste Endalter-Prüfung je Generation (Roadmap).
- `berechne()` bleibt die Golden-Master-Contract-View für
  Fall-Abnahmen; ihre Fensterung ist Produkt-Contract, kein Kern-Referenzwert.
- Künftige Produkte definieren ihren Verlaufs-Contract selbst; nichts
  zwingt sie in die Geometrie des historischen KLV-Workbooks.

## Verworfene Alternative

Kommutation als "tote" Schicht im Kern belassen und nur den 617-Test
streichen: liesse die irreführende Architekturaussage stehen, der
Kern rechne auf Kommutationswerten — genau die Verwechslung von
Übersetzungshistorie und Zielbild, die dieses ADR beendet.
