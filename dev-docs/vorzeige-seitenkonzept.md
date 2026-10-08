# Vorzeigeseite: Seitenkonzept

Beschlossen mit dem Maintainer am 2026-09-08. Maßstab für jede Änderung an
`plv/seite/` und `werkzeuge/`; Anmerkungen werden hieran gemessen, das
Backlog (`vorzeige-backlog.md`) sammelt, was noch fehlt.

## Was die Seite ist

Die Website eines Lebensversicherers, der klassische Lebensversicherungen
verkauft und Bestände anderer Gesellschaften übernimmt. Sie beschreibt
die Geschäftssituation und zeigt die Methodik der Bestandsmigrationen.
Sie ist KEINE Vorführung eines Repositories.

Drei Leser: Vorstände abgebender Gesellschaften (Kunden), Aktuare und
IT-Fachleute (Bewerber und Fachpublikum).

## Regeln

1. **Truman-Prinzip.** Das Unternehmen weiß nicht, dass es fiktiv ist.
   Kein Unternehmenstext nennt Repo, Simulation, Erzeugung, Vorführung,
   Synthetik, Stands-Paket, Manifest. Die Offenlegung ist EINE Seite
   außerhalb der Unternehmensstimme („Hinter den Kulissen“), erreichbar
   über eine schmale Fußzeile auf jeder Seite. Dorthin gehört auch die
   Dokumentation der Entwicklung (Fachkonzepte, Entstehung der Bestände,
   Erfahrungsannahmen, Quellcode).
2. **Ein Leser je Seite.** Aktuariat und IT sind strikt getrennt.
3. **Betrieb und Migrationen je Zielgruppe.** Die Startseite trennt
   Geschäftsentwicklung (Betrieb) und Bestandsmigrationen; Aktuariat und
   IT wiederholen diese Zweiteilung mit ihrem Fokus und ihrer Tiefe.
4. **Brauchen statt zeigen.** Inhalte werden danach ausgewählt, was die
   Seite für ihre Leser braucht — nicht danach, was das Repo hat. Die
   automatisierte Verlinkung mit der Codebasis ist zurückgestellt, bis
   die Struktur steht; Kennzahlen bleiben erzeugt (Drift-Regel).
5. **Platzhalter sind benannt.** Was noch keine Quelle hat, steht als
   Platzhalter da, nie als Null oder Behauptung.

## Struktur

| Seite | Leser | Zweck | Inhalt (Quelle) |
|---|---|---|---|
| Startseite | alle, Vorstandsniveau | Wer wir sind, wie das Geschäft läuft, was wir bei Migrationen versprechen | Stammdaten (Prosa); Geschäftsentwicklung in drei Sichten (Stands-Paket); Bestandsmigrationen: Leistungsversprechen in drei Punkten (Prosa), laufende Übernahme (Platzhalter), fertiggestellte Übernahmen als Blöcke (Fallmodell); Einstiege: Für Versicherer, Für Aktuare, Für IT |
| Geschäftsentwicklung | Vorstand, Finanzen | Vertiefung der Startseite | Zugänge und Leistungen, Bestand je Produkt, Monatsabschlüsse mit Bestandsbericht (Stands-Paket); übernommene Größen der Migration (Fallmodell) |
| Bestandsmigrationen | Vorstände abgebender Gesellschaften | Wie eine Übernahme bei uns abläuft und was sie bringt | Ablauf in Stufen (Prosa); was Sie liefern, was Sie erhalten; Dauer und Kosten (Platzhalter); Kontrollen und Schranken (Prosa); Referenzen: je Übernahme Block, Fallbericht, Abschlussbericht |
| Aktuariat | Aktuare | Fachliche Tiefe | Betrieb: Tarifwerk (Tarifpläne, Grundsatzdokumentation), Bestand (Bestand heute, Monatsabschlüsse, Bestandsberichte). Migrationen: die aktuariellen Abnahmen A-M1 bis A-M4 fachlich, Toleranzen, Stichproben, Widersprüche und ihre Entscheide, Fallberichte |
| IT | IT-Fachleute | Technische Tiefe | Betrieb: Bestandsführungssystem, Rechenkern (Landkarte), Techstack. Migrationen: Migrationsplattform (Agenten, Gates, Ledger, Snapshots, Signaturen), Pipeline, Prüfgates, Architekturentscheide |
| Fallbericht je Übernahme | Vorstand bis Aktuar | Ergebnis, Widerspruch, Prüfung, Verlauf, Belege | generiert (vorzeigeseite.py) |
| Hinter den Kulissen | Besucher der Vorführung | Offenlegung, außerhalb der Fiktion | fiktives Unternehmen, synthetische Bestände, Simulationsschlüssel, Signatur nicht verifiziert; Entstehung der Bestände, Fachkonzept Tagesbetrieb, Erfahrungsannahmen; Quellcode |

Entfallen: die Bereiche Risikomanagement und Finanzen (ihre Inhalte gehen
in Bestandsmigrationen bzw. Geschäftsentwicklung); die Banderole am
Seitenkopf (ersetzt durch die Fußzeile).

## Offene Folgepunkte

- Der Fallbericht trägt am Kopf den Satz „Dies ist eine Vorführung, kein
  echter Bestand“ (Wortlaut bytegleich mit dem Branch ebenen wegen des
  Review-Befunds T19-02/T21-05). Nach dem Merge von main: den
  Verifikationssatz behalten, den Vorführungssatz in die Fußzeile.
- Die Prüfgates-Seite liegt technisch unter it/ und wird auch vom
  Aktuariat verlinkt; ob sie eine fachliche Fassung braucht, entscheidet
  die nächste Sichtung.
