# Ablauf eines Migrationsfalls

Ein Fall beginnt mit der Registrierung der Lieferung und dem Auftrag des
Vorstands. Er endet mit dem gebundenen Anfangsbestand in der Ablage oder mit
dem gezeichneten Abbruch. Dazwischen
schlagen Agenten vor, deterministischer Code prüft, und Menschen zeichnen.
Dieses Dokument ist die Übersicht. Die Entscheidungen dahinter stehen in
[ADR-026](adr-026-lebenslauf-eines-falls.md) (Auftrag und Abbruch),
[ADR-025](adr-025-erstabnahme-des-zielsystems.md) (Abnahme des Zielsystems),
[ADR-010](adr-010-aktuarieller-test-und-controlling.md) (aktuarielle Tests
und Controlling) und [ADR-022](adr-022-zugangsabnahme-a-b2.md) (Zugang).
Die Begriffe erklärt das [Glossar](glossar.md).

## Vom Auftrag bis zur Migrationsabnahme

1. **Fall anlegen und Quellen registrieren.** Jede Datei der Lieferung kommt
   mit ihrer Prüfsumme in `eingang/` und wird nie überschrieben. Hier beginnt
   die Kette der Herkunft.
2. **Fallauftrag `A-M6`.** Der Vorstand beauftragt den Fall, benennt die
   Programmleitung und bindet die Lieferung. Jeder weitere Abnahmepunkt setzt
   den Auftrag voraus. Scheitert der Fall, endet er mit dem Fallabbruch
   `A-M5`, den die Programmleitung zeichnet.
3. **Vorverdichtung und Extraktion.** Jede Quelle wird deterministisch
   vorverdichtet: Excel-Mappen über `P-Q1` (`gates.extract`), Word und
   Text-PDF über `quellen.tarifplan_staging`, CSV-Bestandsabzüge über
   `quellen.bestand_profil`. Dann liest ein Agent sie und schlägt Aussagen
   vor.
4. **Zusammenführung zur A-Box.** Code führt die Aussagen aller Quellen
   zusammen (`P-Q2`) und prüft sie gegen die T-Box (`P-Q3`).
5. **Entscheidung der Widersprüche `A-Q1`.** Widersprüche zwischen Quellen
   gehen als Dossier an einen Menschen.
6. **Spez und parametrierter Kern.** Aus der abgenommenen A-Box entsteht die
   Parametrierung des Tarifs.
7. **Abnahme gegen die Lieferung `P-K1`.** Der parametrierte Kern rechnet die
   Erwartungswerte der Lieferung nach.
8. **Transformation und Übernahme des Bestands.**
9. **Aktuarielle Tests `A-M1` bis `A-M3`.** Jeder Vertrag einer belegten
   Stichprobe wird an seinen eigenen Rechenpunkten geprüft: zum Stichtag
   (`A-M1`), im Verlauf (`A-M2`) und an seinen Geschäftsvorfällen (`A-M3`).
   Jeder Test wird einzeln gezeichnet.
10. **Abnahme des Zielsystems.** Der Stand, auf dem der Fall rechnet, muss
    abgenommen sein: Kernstand (`A-K2`), T-Box-Stand (`A-O1`) und Tarifwerk
    (`A-T1`). Das geschieht einmal außerhalb jedes Falls (Erstabnahme,
    ADR-025). Im Fall wird nur gezeichnet, was der Fall selbst ändert; sonst
    verweist er auf die geltende Abnahme.
11. **Migrationscontrolling und Migrationsabnahme `A-M4`.** Das
    Deckungskapital am Migrations- und am Folgestichtag und die
    Geschäftsvorfälle dazwischen werden gegen die gelieferten Erwartungswerte
    geprüft. Das Ergebnis steht im Abnahmebericht (HTML), der die
    Transformation, ihr Ergebnis und die Bestandsberichte vor und nach der
    Übernahme als Pflichtbelege trägt. Ein Mensch zeichnet `A-M4`.

## Was die Migrationsabnahme prüft

Der Abnahmebericht vertraut keinem früheren Ergebnis. Er liest die Quelle
über das Register des Falls neu, rechnet die Bindungen zwischen Quelle,
Spezifikation und Ziel nach und rendert sich selbst neu, um Byte für Byte zu
vergleichen. Prüflücken, verlorene Zeilen oder offene Widersprüche ergeben
einen roten Bericht und einen blockierenden Exit-Code. Ein Bestandsfall
verlangt zusätzlich die Prüfung des Bestands (`P-B1`), die Migrationssuite
über den vollen Bestand und die Führungsprobe auf demselben Stand. Die Einzelheiten stehen in
[ADR-009](adr-009-fall-scope-und-gate-dag.md) und im
[Vertrag der Prüf-Gates](gate-vertrag-und-versionen.md).

## Zugang in die Ablage

Nach der Migrationsabnahme kommt der übernommene Bestand in die Ablage, in
der die PLV Tag für Tag geführt wird (ADR-022):

1. **Zugangsprobe.** Zwei Läufe auf einem leeren Verzeichnis vom
   Betriebsbeginn über den Stichtag, mit und ohne den Zugang. Ihre Differenz
   wird gegen den abgenommenen Bestand gehalten.
2. **Zugangsabnahme `A-B2`.** Der Betrieb liest den Beleg der Probe und
   zeichnet, bevor der Bestand registriert wird.
3. **Neuaufsetzen.** Die Ablage wird neu aufgesetzt und vom Betriebsbeginn an
   aufgebaut, diesmal mit dem übernommenen Bestand. Die bisherige Ablage
   bleibt als Archiv erhalten.
4. **Anfangsbestand `A-B3`.** Der Anfangsbestand der neuen Ablage wird
   belegt, gezeichnet und gebunden. Danach läuft der Tagesbetrieb auf ihr
   weiter.

So läuft der Zugang in einer Welt, deren Ablage neu aufgesetzt wird
(`deploy/welt/zugang.sh`). In eine laufende Ablage kann ein Zugang auch
direkt registriert werden; dann fährt die Probe auf einer Kopie der Ablage
vom zuletzt geführten Tag an, und auf `A-B2` folgt die Registrierung
(`deploy/plv/README.md`).

Damit ist der Fall abgeschlossen. Nach einem Fallabbruch (`A-M5`) ist im
Fall nichts mehr zeichenbar.

## Auslieferung eines Stands

Geht ein Stand der Ablage nach außen, etwa als Stands-Paket für die
Vorzeigeseite, zeichnet der Betrieb die Auslieferung `A-B1`. Sie bindet genau
den Stand, der hinausgeht. Was fachlich abgenommen ist, steht bereits
gezeichnet im Paket; `A-B1` zeichnet den Akt der Auslieferung.

## Bedienung

| Wer | Wo |
|---|---|
| ein Agent, der einen Fall führt | Skill `migrationsfall-durchfuehren`; Rollenkatalog in [skill-architektur.md](skill-architektur.md) |
| ein Mensch, der eine Welt aufstellt, einen Fall startet oder nachfährt | `deploy/welt/README.md` |
| wer die einzelnen Bedienfolgen nachlesen will | ADR-025 und ADR-026 |
