---
title: "Migrationskonzept Kapitel 6 — Migrationscontrolling"
lang: de
format:
  typst:
    papersize: a4
---

> Projektseitige Ausgestaltung von **FK 6.1**, Zeile
> „Migrationscontrolling". Die Gate-Architektur entscheidet **ADR-010**
> (Trennung der Prüfebenen) und **ADR-009** (Fall-Scope und
> Pflichtbelege); die Handgriffe stehen im Skill
> `pruefe-migrationscontrolling`.

# 6.1 Zweck und Abgrenzung

Das Migrationscontrolling misst am **Migrationsstichtag $t_0$** gegen
die Bilanz: Ist der Bestand vollständig übernommen, stimmen die Werte
zum Übernahmezeitpunkt, und schreibt das Zielsystem ihn danach fort wie
das Quellsystem? Es ist die **zweite** Prüfebene; die methodische Güte
prüft zuvor die aktuarielle Abnahme (Kapitel 7, Gate G-A).

Der Beweis endet nicht beim Stichtags-Foto. Ein Zielsystem, das den
übernommenen Bestand am $t_0$ trifft, ihn danach aber anders
fortschreibt, hat die Migration nicht bestanden. Deshalb prüft das
Controlling über **zwei Stichtage** und braucht dafür den Folge-Abzug
und das Geschäftsvorfall-Protokoll des Zwischenzeitraums.

# 6.2 Prüfgegenstand

Je Vertrag des Bestands:

1. **Deckungskapital am Migrationsstichtag** — die Bilanzgröße.
2. **Bruttojahresbeitrag am Migrationsstichtag**, sofern geliefert. Er
   ist die zweite Prüfachse gegen Parametrierungsfehler: Ein um ein Jahr
   versetztes Eintrittsalter verschiebt die Reserve oft nur um
   Bruchteile eines Cents, den Beitrag dagegen deutlich.
3. **Die Beträge der Geschäftsvorfälle** zwischen den Stichtagen
   (Storno, Tod, Ablauf, Beitragsfreistellung, dynamische Erhöhung).
4. **Deckungskapital am Folgestichtag** auf dem Track, den die
   Geschäftsvorfälle bestimmen.

Anders als der aktuarielle Test misst das Controlling **an gemeinsamen
Stichtagen** und darf dafür unterjährige Werte verwenden; die
Bilanzgröße ist am Bilanzstichtag gefragt, nicht am Vertragsjahrestag.
Genau deshalb sind es zwei Werkzeuge und nicht eines mit zwei Spalten.

# 6.3 Vollständigkeit und Prüflücken

„Vollständig geprüft" heißt hier: **jeder Vertrag des Bestands wurde
geprüft.** Ein ungeprüfter Vertrag ist eine **Prüflücke** — weder
bestanden noch fehlgeschlagen, sondern ungeprüft, und beim Lesen des
Verdikts abzuziehen. Die Prüfmenge wird zusätzlich gegen die
Zeilenzahl der Lieferung gestellt: Eine Abnahme über 400 von 500
Verträgen ist keine bestandene Abnahme, und ein dreimal gelieferter
Vertrag ist kein dreifacher Beleg.

Fehlt eine Erwartungsgröße in der Lieferung, wird sie als Lücke
ausgewiesen, nicht stillschweigend übergangen. Im Bestands-Scope
blockieren offene Prüflücken die Abnahme.

Inkonsistenzen der Lieferung — ein Geschäftsvorfall außerhalb der
Stichtage, ein Wert trotz Abgang, ein Abgang ohne Vorfall, ein Vorfall
auf dem falschen Track — sind **Befunde je Vertrag** und gehen an den
Menschen. Erwartungswerte werden nie „korrigiert", damit ein Lauf grün
wird.

# 6.4 Artefakte und Nachweiskette

1. **Das Suite-Ergebnis** (maschinenlesbar): je Vertrag die
   Einzelvergleiche, die Befunde, die Prüflücken; dazu die Bindungen an
   beide Stichtage, an die geprüfte Bestandsdatei und an den
   Systemstand.
2. **Der Abnahmebericht** (lesbarer Bericht): Verdikt, Prüfmenge,
   Prüflücken, Abnahmetests je Größe, sämtliche Einzelvergleiche,
   Fehlschläge, die Transformations-Mapping-Tabelle und die Verweise auf
   die Bestandsberichte vor und nach der Migration.
3. **Die Gate-Belege**: das Schema- und Invariantenprotokoll des
   übernommenen Bestands (Gate B1) und das Protokoll des
   Berichtslaufs.

Auch hier gilt: Der Bericht rechnet keine Fachwerte, sondern leitet
Residuen, Einzel-, Vertrags- und Suiteurteile aus den persistierten
Fakten neu ab und lehnt jede widersprüchliche Ableitung ab. Er ist
deterministisch und wird rot wie grün geschrieben.

Die SHA-256-Bindungen zwischen Bestandsdatei, Suite, Bericht und
Gate-Belegen sind **Transport- und Provenienzsicherung**: Sie belegen,
dass alle Nachweise denselben Stand meinen — sie ersetzen kein
fachliches Urteil.

# 6.5 Gate G-2: der Entscheid

Die Abnahme ist ein menschlicher Entscheid der Projektleitung auf
Grundlage des Berichts; ein grüner Berichtslauf heißt „Vorlage
vollständig", nicht „abgenommen". Der Entscheid wird als signierter
Snapshot festgehalten und pinnt die Pflichtbelege, die sich aus dem
**Fall-Scope** ergeben:

| Scope | Pflichtbelege von G-2 |
|---|---|
| Tarif | O1-Protokoll, geltender G-1-Snapshot, **geltender G-A-Snapshot**, O3-Belege je Generation |
| Bestand | zusätzlich B1-Protokoll, vollständige Suite, Abnahmebericht |

Die Annahme rechnet ihre Voraussetzungen nach: Sie hasht die
gebundenen Artefakte auf ihren aktuellen Bytes neu, validiert Suite und
Bestandsprotokoll erneut und rendert den Bericht aus der Suite
deterministisch nach, um ihn Byte für Byte zu vergleichen.

**Ohne geltende aktuarielle Abnahme (G-A) ist ein G-2-Entscheid
unmöglich** (Kapitel 7.7). Eine Ablehnung an G-2 führt zurück in die
Analyse; die Kette bildet das als neue Snapshots ab.

# 6.6 Deckungsgrad gegenüber FK 6.1

Abgedeckt sind die Vertragsabstimmung, die Wertprüfung an beiden
Stichtagen und die Nachfahr-Abweichungen. **Nicht** abgedeckt sind die
übrigen in FK 6.1 genannten Controlling-Kennzahlen:

* **Summen je Bestandsgruppe** (Deckungskapital, ZZR): Das Controlling
  urteilt heute je Vertrag und über die Prüfmenge, nicht über
  Bestandsgruppen-Aggregate der Bilanz.
* **$R_{conv}$-Statistik**: Der Konventionsresiduum-Pfad (FK 5.3) ist
  nicht aktiviert; ob er für einen Bestand gefahren wird, ist eine
  Entscheidung im Kapitel „Entscheidungen und offene Punkte".
* **Überschussprojektion des Folgejahres**: als künftige Erweiterung
  benannt, nicht gebaut (ADR-010).
