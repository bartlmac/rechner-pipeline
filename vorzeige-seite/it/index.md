<link rel="stylesheet" href="../assets/stil.css">
<div class="banderole">Fiktives Unternehmen — eine Vorführung agentischer
Bestandsmigration. <a href="../">Zur Startseite.</a></div>

# IT

Zwei Dinge tragen unser Geschäftsmodell: ein Rechenkern, dem man jede
Zahl nachrechnen kann, und ein Migrationsvorgehen, das die Übersetzung
fremder Bestände beherrschbar macht. Die Darstellungen auf dieser
Seite werden beim Bau **aus dem Repo erzeugt oder eingespielt** —
Beschreibung und Code können nicht auseinanderlaufen.

## Der Rechenkern

Unser Bewertungskern rechnet **deterministisch**: gleiche Eingaben,
gleiche Ergebnisse, auf den Cent. Die Bewertung folgt der
Thiele-Rekursion; jede produktive Änderung muss eine Suite von
Charakterisierungstests mit eingefrorenen Referenzwerten unverändert
bestehen. Es gibt keinen Punkt im Rechenweg, an dem geschätzt,
geglättet oder interpoliert wird — ein Wert, der nicht nachgerechnet
werden kann, wird als Befund ausgewiesen statt ersetzt. Die Mathematik
dahinter dokumentiert das Aktuariat in der
[Grundsatzdokumentation](../aktuariat/mathematik/grundsatzdokumentation.html).

Wie der Code tatsächlich geschichtet ist, zeigt die
[Landkarte](architektur/landkarte.html) — beim Bau aus dem Code
erzeugt, vom Schichten-Überblick bis auf Modulebene. Kein gepflegtes
Schaubild, sondern der gemessene Stand.

## Das KI-gestützte Migrationsvorgehen

Bestandsübernahmen übersetzen fremde Datenmodelle und
Tarifbeschreibungen in unser eigenes Rechenwerk. Dabei arbeiten
KI-Agenten und deterministische Prüfstrecken arbeitsteilig:

* **Agenten lesen und schlagen vor** — sie extrahieren
  Tarifparameter aus den gelieferten Unterlagen und entwerfen die
  Feldabbildung des Bestandsabzugs.
* **Deterministische Gates urteilen** — jede Stufe endet in einem
  maschinellen Prüfschritt, der ein Ledger schreibt; kein Agent nimmt
  selbst etwas ab.
* **Menschen entscheiden** — fachliche Widersprüche und die Abnahmen
  selbst sind menschliche Entscheide, kryptographisch gezeichnet und
  an die geprüften Artefakte gebunden.

Das Konzept dahinter ist vollständig eingespielt: die
[Migrations-Pipeline](architektur/migrations-pipeline-v01.html)
(Ontologie als Schnittstelle der Stufen, mit den Abnahme-Gates), die
nicht verhandelbaren
[Prinzipien P1–P10](architektur/prinzipien.html) und sämtliche
[Architekturentscheide (ADRs)](architektur/). Wie das im Ergebnis
aussieht, zeigt der
[Abnahmebericht der Übernahme Baldrian](../migrationen/baldrian/) —
einschließlich der Gate-Kette und der signierten Entscheide.

## Techstack

Beim Bau aus `pyproject.toml` erzeugt: [Techstack](techstack.html).
Das System selbst ist quelloffen:
[bartlmac/rechner-pipeline](https://github.com/bartlmac/rechner-pipeline).
