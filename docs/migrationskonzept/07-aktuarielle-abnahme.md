---
title: "Migrationskonzept Kapitel 7 — Aktuarielle Abnahme"
lang: de
format:
  typst:
    papersize: a4
---

> Projektseitige Ausgestaltung von **FK 6.1** (Prüfebene „Aktuarieller
> Test"), **FK 6.2** (Toleranzdefinition auf der Verteilung) und
> **FK 6.3** (Verlaufs- und Geschäftsvorfalltests). Die
> Gate-Architektur dahinter entscheidet **ADR-010**; die Handgriffe
> stehen im Skill `aktuartest-durchfuehren`. Dieses Kapitel beschreibt
> das Verfahren: was geprüft wird, woran das Urteil hängt, welche
> Nachweise entstehen und wer entscheidet.

# 7.1 Zweck und Abgrenzung

Der aktuarielle Test misst die **methodische Güte** der konstruktiven
Neuberechnung — nicht die Bilanz. Er fragt: Rechnet das Zielsystem den
einzelnen Vertrag an dem Punkt richtig, an dem das Quellsystem ihn
zuletzt exakt gerechnet hat? Die finanzielle Frage („stimmt der Bestand
am Übernahmestichtag in Summe?") ist Gegenstand des
Migrationscontrollings (Kapitel 6).

Die Trennung ist bewusst und in der Reihenfolge bindend: **Die
aktuarielle Abnahme (Gate G-A) geht der Migrationsabnahme (Gate G-2)
voraus.** Eine finanzielle Abnahme des Gesamtbestands vor dem Nachweis
methodischer Güte nähme etwas ab, dessen Grundlage noch offen ist. Die
Reihenfolge ist technisch erzwungen, nicht empfohlen (7.7).

# 7.2 Prüfgegenstand: der Verankerungszeitpunkt je Vertrag

Geprüft wird **je Vertrag an seinem eigenen Verankerungszeitpunkt
$t_a$** (FK 5.1: der letzte exakte Rechenpunkt des Quellsystems). $t_a$
ist damit ein **Vertragsattribut**, kein Parameter des Prüflaufs — zwei
Verträge desselben Bestands werden in aller Regel zu verschiedenen
Zeitpunkten verglichen.

Daraus folgen drei Regeln, die im Werkzeug erzwungen sind und nicht als
Konvention gelten:

1. **Keine Interpolation.** Verglichen wird am Rechenpunkt. Ein
   unterjähriger Vergleichszeitpunkt ist ein Konstruktionsfehler des
   Prüfauftrags und bricht den Lauf ab — er wird nicht als Befund
   ausgewiesen. Begründung (FK 5.1): Ein interpolierter Wert misst die
   Interpolationskonvention mit und entwertet das Residuum als
   Diagnoseinstrument.
2. **Keine Summation der Vergleichsgrößen.** Werte zu verschiedenen
   Stichtagen zu addieren ergibt fachlich nichts. Der Test bildet
   deshalb keine Deckungskapital-Summe; er kennt ausschließlich
   Verteilungsgrößen des Residuums (7.4).
3. **Prüfsummen sind Transportsicherung.** Mitgelieferte Kontrollsummen
   und Datei-Hashes werden geprüft und **getrennt ausgewiesen**, nie
   als Teil des aktuariellen Urteils verrechnet.

# 7.3 Stichprobe

Der Test läuft auf einer **belegten Stichprobe**: benanntes Profil,
deterministisch gezogen, mit ausgewiesener Grundgesamtheit und
vollständiger Policenliste. Die Ziehung gehört zum Nachweis — ohne sie
ließe sich später nicht nachvollziehen, welche Verträge den Test
getragen haben.

„Vollständig" heißt auf dieser Prüfebene: **die Stichprobe wurde
vollständig abgearbeitet.** Die Nichtprüfung der Nicht-Stichprobe ist
kein Befund, sondern die Definition des Tests. (Im Controlling heißt
derselbe Begriff etwas anderes — dort ist jeder ungeprüfte Vertrag eine
Prüflücke, Kapitel 6.)

Der aktuelle Stand kennt genau ein Profil: **`vollbestand`** — die
Stichprobe ist der ganze Bestand. Für Bestände in der Größenordnung der
bisherigen Fälle ist das die fachlich richtige Wahl und zugleich der
Randfall der Parametrisierung. Weitere Profile (geschichtet nach
Historientyp, risikoorientiert) sind eine bewusste Erweiterungsstelle
und je Profil eine Festlegung des Aktuariats mit ADR-Nachzug.

# 7.4 Was gemessen wird

Je Vertrag und Größe wird das **Residuum** ausgewiesen:

$$R = \text{Wert des Zielsystems} - \text{Wert der Lieferung}$$

Geprüft werden die Größen, die die Lieferung zum Verankerungszeitpunkt
führt: Deckungskapital ($kVx_{MRV}$), Rückkaufswert, Bruttojahresbeitrag
und — im beitragsfreien Zustand — die beitragsfreie Summe. Eine nicht
gelieferte Größe wird nicht geprüft; eine unbekannte Größe im Auftrag
ist ein harter Fehler statt einer stillen Auslassung.

Aggregiert wird **ausschließlich über die Verteilung der Beträge
$|R|$**, geclustert nach **Historientyp** (der Übergangsklasse der
Vertragshistorie): Maximum, hohe Perzentile und Betragssumme der
Abweichungen je Cluster. Mittelwert und Median werden bewusst nicht
gebildet (FK 6.2): Erwartet wird Bimodalität, und ein unauffälliger
Mittelwert bei großen Einzelmaxima ist ein Befund, keine Entwarnung.

**Lesehilfe für die Vorlage.** Cent-Größenordnung in den Perzentilen ist
Rundungsrauschen der Lieferung. Ein Maximum, das deutlich darüber liegt,
verlangt eine **benannte Ursache je Cluster** — „Rundung" ist als
Erklärung nur für Cent-Beträge zulässig. Ein Cluster, dessen Verteilung
sich von den anderen abhebt, zeigt auf seinen Historientyp: dort ist die
Übergangsbehandlung zu prüfen, nicht der einzelne Vertrag.

# 7.5 Befundarten

| Befund | Bedeutung | Fortgang |
|---|---|---|
| Wertabweichung außerhalb der Toleranz | Der Vergleich schlägt fehl | Ursache je Cluster benennen; Klärung mit dem abgebenden Unternehmen oder Korrektur der Methode |
| Vertrag nicht rechenbar | Lieferdaten ergeben keinen gültigen Modellpunkt | Datenklärung; der Vertrag bleibt in der Stichprobe und zählt als fehlgeschlagen |
| Stichprobe nicht abgearbeitet | Ein gezogener Vertrag hat keinen Prüfauftrag (oder ein Auftrag liegt außerhalb der Ziehung) | Der Test ist nicht bestanden — die Abdeckungsbehauptung trägt nicht |
| Konstruktionsfehler des Auftrags | Unterjähriges $t_a$, unbekannte Größe, undefinierte Zustandskombination | Lauf bricht ab; der Auftragsbau ist zu korrigieren, nicht das Ergebnis |

Toleranzen kommen aus einer Quelle und werden nie aufgeweicht, „um grün
zu werden". Stellt sich eine Toleranzfrage, ist sie eine fachliche
Entscheidung des Aktuariats und kein Parameter des Laufs.

# 7.6 Artefakte und Nachweiskette

Ein Testlauf hinterlässt drei Dinge:

1. **Das Testergebnis** (maschinenlesbar): Stichproben-Beleg samt
   Policenliste, je Vertrag die Einzelvergleiche mit Residuum und
   Urteil, die Verteilungsgrößen je Cluster, die Transportangaben und
   der Systemstand, unter dem gerechnet wurde.
2. **Die Entscheidungsvorlage** (lesbarer Bericht): dasselbe in der
   Form, in der der Verantwortliche Aktuar entscheidet — Verdikt,
   Stichprobe, Verteilung je Cluster, Fehlschläge, Einzelvergleiche,
   Transportsicherung als eigener, ausdrücklich vom Urteil getrennter
   Abschnitt.
3. **Der Gate-Beleg**: das Prüfprotokoll des Werkzeugs mit den Hashes
   von Ergebnis und Bericht.

Die Vorlage ist deterministisch: gleiche Eingaben ergeben denselben
Bericht Byte für Byte. Ein **roter** Bericht wird geschrieben wie ein
grüner — er ist das Beweisstück, nicht sein Gegenteil.

Das Werkzeug leitet das Verdikt aus dem Ergebnis **neu ab**, statt ihm
zu glauben: Einzelurteile gegen die Toleranzen, Zähler, Mengenabgleich
gegen die Stichprobe und sämtliche Verteilungsgrößen werden
nachgerechnet. Eine grüne Zusammenfassung über einem roten
Einzelvergleich ist damit ausgeschlossen.

# 7.7 Gate G-A: der Entscheid

Der Test **entscheidet nichts**. Die aktuarielle Abnahme ist ein
menschlicher Entscheid des **Verantwortlichen Aktuars** (FK Kap. 7,
§ 141 VAG) auf Grundlage der Vorlage. Ein grüner Testlauf heißt „Vorlage
vollständig und Test bestanden", nicht „abgenommen".

Der Entscheid wird als unveränderlicher, signierter Snapshot
festgehalten (ADR-008). Dabei gilt:

* Eine **Annahme rechnet ihre Voraussetzungen nach**: Das Testverdikt
  wird aus dem Ergebnis neu abgeleitet, der Bericht aus dem Ergebnis
  deterministisch reproduziert und gegen die abgelegte Fassung
  verglichen, und das Ergebnis muss den Systemstand des Entscheids
  tragen. Ein nachträglich geänderter Prüfbeleg öffnet das Gate nicht.
* Die Annahme **pinnt** Testergebnis und Bericht als Pflichtbelege.
* Eine **Ablehnung ist jederzeit möglich** und ebenso ein Snapshot —
  auch über einem roten Test. Ein Agent kann an diesem Gate
  ausschließlich ablehnen.
* **Gate G-2 verlangt die geltende G-A-Annahme** auf demselben Eingangs-,
  A-Box- und Systemstand und pinnt sie als Pflichtbeleg. Ändert sich der
  Stand, ist die G-A-Annahme nicht mehr geltend — der Test wird auf dem
  neuen Stand wiederholt und neu entschieden.
* Die **Rückschleife ist zulässig**: Eine Ablehnung an G-2 führt zurück
  in Analyse und ggf. erneuten Test; die Kette bildet das als neue
  Snapshots ab. Unzulässig bleibt allein die Umkehrung der Reihenfolge.

# 7.8 Deckungsgrad gegenüber FK Kapitel 6

Der heutige Stand deckt FK 6.1 (Prüfebene, Zeitbezug, Verantwortung)
und die Auswertungsform aus FK 6.2 (Verteilung statt Mittelwert)
vollständig ab. **Nicht** abgedeckt sind:

* **FK 6.3 — Verlaufs- und Geschäftsvorfalltests.** Vorwärtsrechnung
  über mehrere Jahre gegen eine Schattenrechnung des Quellsystems und
  die GV-Testmatrix je Vertragskonstellations-Cluster gibt es auf dieser
  Prüfebene nicht. FK 6.3 ist hier eindeutig: *„Ohne Verlaufstests gilt
  die Methode als nicht abgenommen; Stichtagstreue allein ist notwendig,
  nicht hinreichend."* Eine G-A-Annahme auf dem heutigen Stand belegt
  also die Stichtagstreue am Rechenpunkt — sie ersetzt die Verlaufstests
  nicht und darf nicht als deren Erfüllung gelesen werden.
* **Toleranzen auf der Verteilung als Urteilskriterium.** Die Verteilung
  wird ausgewiesen, aber das maschinelle Urteil hängt heute an
  Toleranzen je Einzelwert. Eine Schwelle auf Maximum oder hohem
  Perzentil je Cluster (FK 6.2) ist eine Festlegung des Aktuariats und
  noch nicht getroffen.
* **Das methodische Residuum $R_{hist}$.** Solange es keine
  Korrekturschicht gibt (FK Kap. 3-5), trägt der Test den vorhandenen
  Wertvergleich — am richtigen Zeitpunkt und ohne Summen. Der Platz für
  $R_{hist}$ ist im Werkzeug benannt und leer; er wird gefüllt, wenn die
  Korrekturschicht steht, ohne dass sich Verfahren, Gate oder
  Nachweiskette ändern.
* **Floor-Prüfungen** (§ 169 VVG, FK 4.6) als Teil des Tests.

Diese vier Punkte sind der Arbeitsvorrat dieser Prüfebene. Sie stehen
hier, damit eine Abnahme weiß, was sie abnimmt.
