# Vorzeigeseite: Seitenkonzept

Beschlossen mit dem Maintainer am 2026-09-08. Massstab fuer jede Aenderung an
`vorzeige-seite/` und `werkzeuge/`; Anmerkungen werden hieran gemessen, das
Backlog (`vorzeige-backlog.md`) sammelt, was noch fehlt.

## Was die Seite ist

Die Website eines Lebensversicherers, der klassische Lebensversicherungen
verkauft und Bestaende anderer Gesellschaften uebernimmt. Sie beschreibt
die Geschaeftssituation und zeigt die Methodik der Bestandsmigrationen.
Sie ist KEINE Vorfuehrung eines Repositories.

Drei Leser: Vorstaende abgebender Gesellschaften (Kunden), Aktuare und
IT-Fachleute (Bewerber und Fachpublikum).

## Regeln

1. **Truman-Prinzip.** Das Unternehmen weiss nicht, dass es fiktiv ist.
   Kein Unternehmenstext nennt Repo, Simulation, Erzeugung, Vorfuehrung,
   Synthetik, Stands-Paket, Manifest. Die Offenlegung ist EINE Seite
   ausserhalb der Unternehmensstimme ("Hinter den Kulissen"), erreichbar
   ueber eine schmale Fusszeile auf jeder Seite. Dorthin gehoert auch die
   Dokumentation der Entwicklung (Fachkonzepte, Entstehung der Bestaende,
   Erfahrungsannahmen, Quellcode).
2. **Ein Leser je Seite.** Aktuariat und IT sind strikt getrennt.
3. **Betrieb und Migrationen je Zielgruppe.** Die Startseite trennt
   Geschaeftsentwicklung (Betrieb) und Bestandsmigrationen; Aktuariat und
   IT wiederholen diese Zweiteilung mit ihrem Fokus und ihrer Tiefe.
4. **Brauchen statt zeigen.** Inhalte werden danach ausgewaehlt, was die
   Seite fuer ihre Leser braucht — nicht danach, was das Repo hat. Die
   automatisierte Verlinkung mit der Codebasis ist zurueckgestellt, bis
   die Struktur steht; Kennzahlen bleiben erzeugt (Drift-Regel).
5. **Platzhalter sind benannt.** Was noch keine Quelle hat, steht als
   Platzhalter da, nie als Null oder Behauptung.

## Struktur

| Seite | Leser | Zweck | Inhalt (Quelle) |
|---|---|---|---|
| Startseite | alle, Vorstandsniveau | Wer wir sind, wie das Geschaeft laeuft, was wir bei Migrationen versprechen | Stammdaten (Prosa); Geschaeftsentwicklung in drei Sichten (Stands-Paket); Bestandsmigrationen: Leistungsversprechen in drei Punkten (Prosa), laufende Uebernahme (Platzhalter), fertiggestellte Uebernahmen als Bloecke (Fallmodell); Einstiege: Fuer Versicherer, Fuer Aktuare, Fuer IT |
| Geschaeftsentwicklung | Vorstand, Finanzen | Vertiefung der Startseite | Zugaenge und Leistungen, Bestand je Produkt, Monatsabschluesse mit Bestandsbericht (Stands-Paket); uebernommene Groessen der Migration (Fallmodell) |
| Bestandsmigrationen | Vorstaende abgebender Gesellschaften | Wie eine Uebernahme bei uns ablaeuft und was sie bringt | Ablauf in Stufen (Prosa); was Sie liefern, was Sie erhalten; Dauer und Kosten (Platzhalter); Kontrollen und Schranken (Prosa); Referenzen: je Uebernahme Block, Fallbericht, Abschlussbericht |
| Aktuariat | Aktuare | Fachliche Tiefe | Betrieb: Tarifwerk (Tarifplaene, Grundsatzdokumentation), Bestand (Bestand heute, Monatsabschluesse, Bestandsberichte). Migrationen: die aktuariellen Abnahmen A-M1 bis A-M4 fachlich, Toleranzen, Stichproben, Widersprueche und ihre Entscheide, Fallberichte |
| IT | IT-Fachleute | Technische Tiefe | Betrieb: Bestandsfuehrungssystem, Rechenkern (Landkarte), Techstack. Migrationen: Migrationsplattform (Agenten, Gates, Ledger, Snapshots, Signaturen), Pipeline, Pruefgates, Architekturentscheide |
| Fallbericht je Uebernahme | Vorstand bis Aktuar | Ergebnis, Widerspruch, Pruefung, Verlauf, Belege | generiert (vorzeigeseite.py) |
| Hinter den Kulissen | Besucher der Vorfuehrung | Offenlegung, ausserhalb der Fiktion | fiktives Unternehmen, synthetische Bestaende, Simulationsschluessel, Signatur nicht verifiziert; Entstehung der Bestaende, Fachkonzept Tagesbetrieb, Erfahrungsannahmen; Quellcode |

Entfallen: die Bereiche Risikomanagement und Finanzen (ihre Inhalte gehen
in Bestandsmigrationen bzw. Geschaeftsentwicklung); die Banderole am
Seitenkopf (ersetzt durch die Fusszeile).

## Offene Folgepunkte

- Der Fallbericht traegt am Kopf den Satz "Dies ist eine Vorfuehrung, kein
  echter Bestand" (Wortlaut bytegleich mit dem Branch ebenen wegen des
  Review-Befunds T19-02/T21-05). Nach dem Merge von main: den
  Verifikationssatz behalten, den Vorfuehrungssatz in die Fusszeile.
- Die Pruefgates-Seite liegt technisch unter it/ und wird auch vom
  Aktuariat verlinkt; ob sie eine fachliche Fassung braucht, entscheidet
  die naechste Sichtung.
