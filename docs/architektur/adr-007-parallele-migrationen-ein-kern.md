# ADR-007: Parallele Migrationen in einem Kern — Trunk, knotengebundene Inkremente, Knoten-Lebenszyklus

Status: akzeptiert (Bartek, 2026-08-18).

## Kontext

Mit dem zweiten Baldrian-Fall existieren erstmals zwei Migrationsfaelle
nebeneinander. Das wirft die strategische Frage auf, wie zwei (oder
mehr) UNFERTIGE Migrationen im selben Zielsystem unterschieden werden,
ohne dass der Betrieb im Chaos endet.

Eine naheliegende, aber falsche Verengung stand im Raum (und klingt in
ADR-006 an, wo der Praezedenzfall TG2012 -> TG2015 als "Parametrierung"
beschrieben ist): Migration sei im Wesentlichen Parametrierung des
vorhandenen Kerns. Das gilt nur fuer den konstruierten Sonderfall. Der
reale Fall ist das Gegenteil: Ein uebernommener Bestand bringt
Tarifgenerationen mit Leistungsmerkmalen, die das Zielsystem nicht
kennt — Migration ist im Normalfall eine intensive CODE-Erweiterung
des Kerns, die sich ueber Monate zieht, waehrend parallel die naechste
Uebernahme anlaeuft.

Randbedingungen:

* Team-Beschluss "Zielsystem fuehrt": EIN monolithischer Kern
  (DAV-Standardansatz). Forks des Kerns je Migration sind damit
  ausgeschlossen.
* Auch ein langlebiger Git-Branch je Migration waere keine Loesung:
  Zwei Branches, die monatelang denselben Monolithen erweitern,
  divergieren zwangslaeufig; der Merge am Ende ist genau das Chaos,
  das vermieden werden soll.
* Die ADR-005-Mechanik existiert bereits: Jeder Baustein traegt einen
  Ontologie-Knoten, jeder Test ist knotengebunden, `impact` berechnet
  Beruehrungsmengen, Referenzwert- und P-K1-Gates beweisen Wertidentitaet.

## Entscheidung

**Regel 1 — Ein Kern, ein Trunk.** Es gibt weder Kern-Forks noch
langlebige Branches je Migration. Branches bleiben das Arbeitsvehikel,
aber je INKREMENT (Lebensdauer Tage, nicht Monate).

**Regel 2 — Die Trennung leistet die Ontologie, nicht Git.** Eine
Migration erweitert den Kern um IHRE Knoten (neue Generationen, im
A-K1-Fall neue Familien). Neuer knotengebundener Code ist fuer alle
anderen Faelle inert: Er wird erst wirksam, wenn die Spez eines Falls
ihn parametriert. Die Frage "zu welcher unfertigen Migration gehoert
dieser Baustein?" beantwortet der Knoten, nicht die Branch-Historie.

**Regel 3 — Inkremente landen klein und frueh auf dem Trunk, und jede
Landung beweist die Nicht-Beruehrung der anderen Faelle.** Ein
Inkrement darf nur landen, wenn die Gesamt-Suite gruen ist —
einschliesslich der Referenzwert- und P-K1-Laeufe ALLER anderen offenen und
abgeschlossenen Faelle. Dass Migration A Migration B nicht veraendert
hat, wird bei jeder Landung maschinell bewiesen, nicht per Disziplin
gehofft. Der fachliche Zustand einer laufenden Migration (A-Box,
Entscheide, Spez, Abgleiche) lebt derweil vollstaendig im
Fall-Arbeitsbereich `faelle/<name>/` (ADR-002).

**Regel 4 — Knoten-Lebenszyklus.** Ein Generation-Knoten traegt einen
Status: `in_migration` (mit Verweis auf den offenen Fall; Werte duerfen
sich noch aendern) oder `abgenommen` (durch Referenzwerte gesichert, Werte
eingefroren). Damit ist jederzeit ablesbar, welche Teile des Kerns zu
welcher unfertigen Migration gehoeren. Der echte Konfliktfall wird
benennbar und ist ein KOORDINATIONSPUNKT mit menschlicher Entscheidung,
kein Git-Merge-Zufall:

* Zwei offene Faelle am SELBEN Knoten werden serialisiert (der aeltere
  wird abgeschlossen oder archiviert, oder der neue wartet).
* Aenderungen am gemeinsamen Rueckgrat (Thiele-Rekursion, Tafelwerk,
  Bestand) brauchen die gruenen Gates ALLER Faelle.

**Konvention Archiv:** Abgeschlossene oder als Vorlauf beendete Faelle
wandern nach `faelle/archiv/<name>/` — vollstaendig erhalten
(insbesondere `eingang/` und die nicht regenerierbaren `entscheide/`),
aber ausserhalb der aktiven Scans (Impact-Fallsuche, P-K1-Zuordnung
arbeiten auf `faelle/<name>/`, eine Ebene tief).

## Konsequenzen

* Der Tafel-Import bleibt die einzige zulaessige dauerhafte
  Kern-Beruehrung VOR der Abnahme (P-K1 muss rechnen koennen); er ist
  additiv, provenienzpflichtig, und gleicher Name mit anderen Werten
  ist ein harter Fail-fast — das serialisiert konkurrierende Faelle
  automatisch.
* Der Knoten-Status (Regel 4) ist in der T-Box noch nicht umgesetzt;
  Umsetzung als offener Punkt nach dem 2026-08-19 (zusammen mit den
  Tarifplan-Drift-Tests).
* Der erste Baldrian-Fall (`baldrian-klv-tg2015`) wird als Vorlauf
  archiviert; der offene Fall zur Generation `klv/tg2015` ist
  `baldrian-uebernahme`.
* ADR-006 bleibt gueltig; sein Satz zur "Parametrierung" beschreibt den
  dortigen Praezedenzfall, nicht den Normalfall einer Migration.
