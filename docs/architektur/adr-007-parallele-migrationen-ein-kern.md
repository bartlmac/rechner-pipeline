# ADR-007: Parallele Migrationen in einem Kern — ein Hauptzweig, knotengebundene Inkremente, Knoten-Lebenszyklus

**Status:** angenommen am 2026-08-18 (Maintainer).

## Kontext

Mit dem zweiten Baldrian-Fall existieren erstmals zwei Migrationsfälle
nebeneinander. Das wirft die strategische Frage auf, wie zwei (oder
mehr) unfertige Migrationen im selben Zielsystem unterschieden werden,
ohne dass der Betrieb im Chaos endet.

Eine naheliegende, aber falsche Verengung stand im Raum (und klingt in
ADR-006 an, wo der Präzedenzfall TG2012 -> TG2015 als „Parametrierung“
beschrieben ist): Migration sei im Wesentlichen Parametrierung des
vorhandenen Kerns. Das gilt nur für den konstruierten Sonderfall. Der
reale Fall ist das Gegenteil: Ein übernommener Bestand bringt
Tarifgenerationen mit Leistungsmerkmalen, die das Zielsystem nicht
kennt — Migration ist im Normalfall eine intensive Code-Erweiterung
des Kerns, die sich über Monate zieht, während parallel die nächste
Übernahme anläuft.

Randbedingungen:

* Team-Beschluss „Zielsystem führt“: Ein monolithischer Kern
  (DAV-Standardansatz). Forks des Kerns je Migration sind damit
  ausgeschlossen.
* Auch ein langlebiger Git-Branch je Migration wäre keine Lösung:
  Zwei Branches, die monatelang denselben Monolithen erweitern,
  divergieren zwangsläufig; der Merge am Ende ist genau das Chaos,
  das vermieden werden soll.
* Die ADR-005-Mechanik existiert bereits: Jeder Baustein trägt einen
  Ontologie-Knoten, jeder Test ist knotengebunden, `impact` berechnet
  Berührungsmengen, Referenzwert- und P-K1-Gates beweisen Wertidentität.

## Entscheidung

**Regel 1 — Ein Kern, ein Hauptzweig.** Es gibt weder Kern-Forks noch
langlebige Branches je Migration. Branches bleiben das Arbeitsvehikel,
aber je Inkrement (Lebensdauer Tage, nicht Monate).

**Regel 2 — Die Trennung leistet die Ontologie, nicht Git.** Eine
Migration erweitert den Kern um ihre Knoten (neue Generationen, im
A-O1-Fall neue Familien). Neuer knotengebundener Code ist für alle
anderen Fälle inert: Er wird erst wirksam, wenn die Spez eines Falls
ihn parametriert. Die Frage „zu welcher unfertigen Migration gehört
dieser Baustein?“ beantwortet der Knoten, nicht die Branch-Historie.

**Regel 3 — Inkremente landen klein und früh auf dem Hauptzweig, und jede
Landung beweist die Nicht-Berührung der anderen Fälle.** Ein
Inkrement darf nur landen, wenn die Gesamt-Suite grün ist —
einschließlich der Referenzwert- und P-K1-Läufe aller anderen offenen und
abgeschlossenen Fälle. Dass Migration A Migration B nicht verändert
hat, wird bei jeder Landung maschinell bewiesen, nicht per Disziplin
gehofft. Der fachliche Zustand einer laufenden Migration (A-Box,
Entscheide, Spez, Abgleiche) lebt derweil vollständig im
Fall-Arbeitsbereich `faelle/<name>/` (ADR-002).

**Regel 4 — Knoten-Lebenszyklus.** Ein Generation-Knoten trägt einen
Status: `in_migration` (mit Verweis auf den offenen Fall; Werte dürfen
sich noch ändern) oder `abgenommen` (durch Referenzwerte gesichert, Werte
eingefroren). Damit ist jederzeit ablesbar, welche Teile des Kerns zu
welcher unfertigen Migration gehören. Der echte Konfliktfall wird
benennbar und ist ein Koordinationspunkt mit menschlicher Entscheidung,
kein Git-Merge-Zufall:

* Zwei offene Fälle am selben Knoten werden serialisiert (der ältere
  wird abgeschlossen oder archiviert, oder der neue wartet).
* Änderungen am gemeinsamen Rückgrat (Thiele-Rekursion, Tafelwerk,
  Bestand) brauchen die grünen Gates aller Fälle.

**Konvention Archiv:** Abgeschlossene oder als Vorlauf beendete Fälle
wandern nach `faelle/archiv/<name>/` — vollständig erhalten
(insbesondere `eingang/` und die nicht regenerierbaren `entscheide/`),
aber außerhalb der aktiven Scans (Impact-Fallsuche, P-K1-Zuordnung
arbeiten auf `faelle/<name>/`, eine Ebene tief).

## Konsequenzen

* Der Tafel-Import bleibt die einzige zulässige dauerhafte
  Kern-Berührung vor der Abnahme (P-K1 muss rechnen können); er ist
  additiv, provenienzpflichtig, und gleicher Name mit anderen Werten
  ist ein harter Fail-fast — das serialisiert konkurrierende Fälle
  automatisch.
* Der Knoten-Status (Regel 4) ist bis heute nicht gebaut: Die T-Box
  kennt keinen Status `in_migration` oder `abgenommen` (Stand
  2026-10-08).
* Der erste Baldrian-Fall (`baldrian-klv-tg2015`) wird als Vorlauf
  archiviert; der offene Fall zur Generation `klv/tg2015` ist
  `baldrian-uebernahme`.
* ADR-006 bleibt gültig; sein Satz zur „Parametrierung“ beschreibt den
  dortigen Präzedenzfall, nicht den Normalfall einer Migration.
