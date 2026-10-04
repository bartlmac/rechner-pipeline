# Ablauf eines Migrationsfalls

Ein Fall beginnt mit dem Auftrag des Vorstands und endet mit dem gebundenen
Anfangsbestand in der Ablage — oder mit dem gezeichneten Abbruch. Dazwischen
schlagen Agenten vor, deterministischer Code entscheidet, und Menschen
zeichnen. Dieses Dokument ist die Übersicht; die Entscheidungen dahinter
stehen in [ADR-026](adr-026-lebenslauf-eines-falls.md) (Auftrag und Abbruch),
[ADR-025](adr-025-erstabnahme-des-zielsystems.md) (Abnahme des Zielsystems
in der Linie), [ADR-010](adr-010-aktuarieller-test-und-controlling.md)
(aktuarielle Tests und Controlling) und
[ADR-022](adr-022-zugangsabnahme-a-b2.md) (Zugang).

## Vom Auftrag bis zur Migrationsabnahme

1. Fall-Arbeitsbereich anlegen und Quellen registrieren (`eingang/` mit
   SHA-256-Register, nie still überschrieben — hier beginnt die
   Provenienzkette)
2. **Fallauftrag** `A-M6`: der Vorstand beauftragt den Fall, benennt die
   Programmleitung und bindet die Lieferung; jeder weitere Abnahmepunkt
   setzt ihn voraus, ein scheiternder Fall endet mit dem gezeichneten
   **Fallabbruch** `A-M5` der Programmleitung (ADR-026)
3. je Quelle Vorverdichtung und Agenten-Extraktion
4. deterministischer Merge zur A-Box
5. Diskrepanzen als Entscheidungs-Dossier an den Menschen (Gate A-Q1)
6. Spez
7. parametrierter Kern
8. Abnahme gegen die Lieferung (Gate P-K1, Bestandsabzugs-Abgleich)
9. Transformation und Übernahme des Bestands
10. **aktuarieller Test je Vertrag an seinen eigenen Rechenpunkten** auf
    belegten Stichproben (`qa/aktuarieller_test`, `qa/testprofil`,
    `gates/aktuartest`) in drei einzeln gezeichneten Abnahmen — `A-M1`
    Stichtagstest, `A-M2` Verlaufstest, `A-M3` Geschäftsvorfalltest —, die
    dem Controlling `A-M4` vorausgehen (ADR-010, ADR-012), ebenso wie die
    Abnahme des Stands, auf dem der Fall rechnet — Kernstand `A-K2`,
    T-Box-Stand `A-O1`, Tarifwerk `A-T1`; einmal außerhalb jedes Falls im
    Linienbereich abgenommen (Erstabnahme, ADR-025), im Fall nur, was sich
    durch ihn ändert, sonst belegt durch einen Verweis auf die geltende
    Abnahme (ADR-018, Nachtrag 2026-10-01)
11. **Migrationscontrolling über zwei Stichtage**: Deckungskapital am
    Migrations- und am Folgestichtag plus die Geschäftsvorfälle dazwischen,
    gegen die gelieferten Erwartungswerte (`qa/migrationssuite`),
    zusammengefasst im HTML-Abnahmebericht (`gates/abnahmebericht`) mit
    Transformationsspecifikation, Transformationsergebnis und
    Bestandsberichten vor/nach als Pflichtartefakte — als Vorlage für das
    menschliche Gate A-M4.

## Was die Migrationsabnahme bindet

Prüflücken, Zeilenverlust, Transformationsbefunde oder nicht entschiedene
Konflikte ergeben einen roten Kopfsatz, ein fehlgeschlagenes Ledger und
einen blockierenden Exit-Code. Jede Eingabe-, Ausgabe- und Ledgerrolle muss
dabei eine eigene Datei bezeichnen; Pfad- oder Hardlink-Aliase blockieren
vor dem Rendern. Der in `fall.json` deklarierte Scope unterscheidet dabei
reine Tariffälle von Bestandsfällen: Nur der Bestands-Scope verlangt und
bindet P-B1, eine vollständig geprüfte Suite und den Abnahmebericht auf
denselben Stand.

`gates.transformation_anwenden.wende_an(spec, fall)` löst die Quelle anhand
von `spec.quelle_datei` selbst über das Fallregister auf, liest die
registrierte CSV und führt `validate_spec` gegen deren physischen Header
aus; SHA-256 und Spalten müssen zur Spec passen. Ein frei übergebbarer
Dateipfad ist damit kein Transformations-Eingang mehr. Berechnungen haben
katalogspezifisch exakt einen oder zwei Operanden, und eine
Konfliktentscheidung gilt nur mit nichtleerem Entscheid und Entscheider. Das
persistierte Transformationsergebnis bindet Quell-, Spec- und Ziel-SHA-256,
Quellspalten sowie Quell-/Zielzeilenzahl.

Der Abnahmebericht liest die Quelle über `eingang.json` erneut und rechnet
diese Bindungen nach; ohne diese physische Fallbindung bleibt auch ein
ansonsten grüner Renderer-Aufruf ausdrücklich rot und nichtautoritativ. Im
Bestands-Scope verlangt er als Ziel genau den von Suite und P-B1 geprüften
Bestand. A-M4 wiederholt diese Prüfung, verlangt Spec,
Transformationsergebnis sowie Vor-/Nachbericht unter vier festen
Pfad-/SHA-256-Rollen und rendert den Bericht aus den erneut gelesenen
Inhalten zum Bytevergleich neu (ADR-009).

## Zugang in die Ablage

Nach der Migrationsabnahme kommt der übernommene Bestand in die Ablage, in
der die PLV Tag für Tag geführt wird (ADR-022):

1. **Zugangsprobe:** zwei Läufe vom Betriebsbeginn über den Stichtag, mit
   und ohne den Zugang. Ihre Differenz wird gegen den abgenommenen Bestand
   gehalten.
2. **Zugangsabnahme `A-B2`:** Der Betrieb liest den Beleg der Probe und
   zeichnet, bevor der Bestand registriert wird.
3. **Neuaufsetzen:** Die Ablage wird neu aufgesetzt und vom Betriebsbeginn
   an aufgebaut, diesmal mit dem übernommenen Bestand. Die bisherige Ablage
   bleibt als Archiv und als Vergleichsstand ohne ihn.
4. **Anfangsbestand `A-B3`:** Der Anfangsbestand der neuen Ablage wird
   belegt, in der Linie gezeichnet und gebunden. Danach läuft der
   Tagesbetrieb auf ihr weiter.

Damit ist der Fall abgeschlossen. Scheitert er vorher, endet er mit dem
Fallabbruch `A-M5`, den die Programmleitung zeichnet; danach ist im Fall
nichts mehr zeichenbar.

## Auslieferung eines Stands

Geht ein Stand der Ablage nach außen — als Stands-Paket für einen Bericht
oder den Webauftritt —, zeichnet der Betrieb die Auslieferung `A-B1`. Sie
bindet den Ankersatz des Pakets, also genau den Stand, der hinausgeht. Was
fachlich abgenommen ist, steht bereits gezeichnet im Paket; `A-B1` zeichnet
den Akt.

## Bedienung

| Wer | Wo |
|---|---|
| ein Agent, der einen Fall führt | Skill `migrationsfall-durchfuehren`; Rollenkatalog in [skill-architektur.md](skill-architektur.md) |
| ein Mensch, der eine Welt aufstellt, einen Fall startet oder nachfährt | `deploy/welt/README.md` |
| wer die einzelnen Bedienfolgen nachlesen will | ADR-025 und ADR-026 |
