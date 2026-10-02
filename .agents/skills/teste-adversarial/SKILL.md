---
name: teste-adversarial
description: >-
  Quality-assure a finished block of work with the established adversarial pattern:
  independent review dimensions produce findings, every finding is adversarially
  verified against the real code (refute-first), confirmed findings become red tests
  before they are fixed, every fix gets a ratchet and a mutation probe, and the fixed
  state is attacked again blind — a finding is "closed" only after a round finds nothing.
  For external review rounds, the attacker is first calibrated blind on the pre-fix state. Also carries the repo's test-writing discipline
  (mutation thinking, independent control calculations, honest skips). Trigger after
  completing a substantial implementation block, before declaring work done, or when
  the user asks for a review/QA of changes. Skip for: trivial one-line fixes, pure
  documentation changes, running existing test suites without new work.
---

# Adversarial testen und reviewen

## Rolle

Du sicherst einen fertigen Arbeitsblock ab. Grundhaltung: Findings
wollen WIDERLEGT werden — bestaetigt ist nur, was einer adversarialen
Pruefung gegen den echten Code standhaelt. Plausibel klingende, falsche
Findings sind teurer als uebersehene.

## Warum dieses Muster so aussieht

Eine Pruefrunde, in der der Autor des Fixes auch bestimmt, was die
Klasse ist, den Test schreibt und "geschlossen" erklaert, beweist nur,
dass sein Test seinen Fix sieht. So entstand eine Runde, in der 16 von 16
Befunden als geschlossen galten und die naechste externe Pruefung 16
neue Befundgruppen fand — sieben davon durch die Fixes selbst
verursacht. "Fix entfernt, Test rot" ist eine Mutationsprobe des eigenen
Tests, kein Angriff. Das Muster unten trennt deshalb Autor und Angreifer
und misst, bevor es behauptet.

## Das Muster

1. **Kalibrieren, bevor man dem Angreifer glaubt.** Liegen Befunde einer
   externen Pruefung vor, laeuft der Angriff zuerst BLIND auf den Stand
   VOR dem Fix: unabhaengige Pruefer ohne den Pruefbericht und ohne den
   Kontext des Autors, je Pruefer eine Methode (siehe unten). Findet der
   Angreifer die bekannten Befunde seines Bereichs nicht, ist die
   METHODE verworfen, nicht der Befund — dann tragen dort nur eigene
   Nachbauten der externen Angriffe, besser die Angriffsskripte des
   Pruefers selbst, unveraendert uebernommen.
2. **Finden:** je Methode ein unabhaengiger Pruefer. Methoden, die sich
   bewaehrt haben:
   - *Unabhaengige Sollrechnung:* die fachliche Zusage aus
     Kern-Primitiven selbst bauen und JEDE ausgewiesene Groesse dagegen
     halten — mit jedem Wert jedes Schalters, an jedem Stichtag.
   - *Producer-Ausgabe verstuemmeln:* Zeilen entfernen, verdoppeln,
     Betraege aendern, Hashes korrekt nachfuehren — und die echte
     Pruef-Engine und den oeffentlichen CLI-Weg fragen.
   - *Ausfaelle an jeder Schreibstelle:* jede Schreib-/Umbenennungsstelle
     einzeln stoeren, auch zweimal hintereinander (der zweite Ausfall im
     Reparaturpfad), dann sauber wiederholen und mit dem ungestoerten
     Lauf vergleichen.
   - *Naht zwischen Pruefen und Verwenden:* Eingaben nach der Pruefung
     und vor der Verwendung tauschen; Pfadobjekte (Verzeichnis, Datei,
     Symlink, Hardlink) einzeln pruefen.
   - *Vertraege gegen Verhalten:* Datenvertraege, Kennzahlen, Dokumente
     gegen das gemessene Verhalten desselben Laufs.
   Jeder Pruefer arbeitet in einer eigenen synthetischen Welt, mit echten
   Producern und Pruef-Engines, und liefert je Finding ein lauffaehiges
   Repro mit Ist, Soll und Positivkontrolle.
3. **Verifizieren:** JEDES Finding einzeln durch einen zweiten Pruefer,
   Auftrag WIDERLEGEN; im Zweifel nicht bestaetigt. Eine Sollrechnung,
   die dieselbe Funktion ruft wie der Ist-Wert, ist keine.
4. **Roter Test vor dem Fix:** jeder bestaetigte Fund wird zuerst ein
   Test im Repo, der auf dem aktuellen Stand ROT ist. Erst dann fixen.
5. **Die Regel fixen, nicht den Fall:** Benenne die Invariante hinter
   dem Fund und baue einen Weg, durch den jeder Pfad muss. Dazu eine
   **Ratsche**: ein Test, der nicht eine Rechnung prueft, sondern die
   Bauregel festhaelt (Beispiel: ein Parameter, dessen Vergessen den
   Fehler erzeugte, bekommt keinen Standardwert, und der Test wird rot,
   sobald jemand wieder einen einfuehrt). Eine Ratsche prueft Verhalten
   an der Naht, wo moeglich; eine rein statische Ratsche wird im Test
   als solche benannt.
6. **Mutationsprobe je Fix:** den Fix gezielt zuruecknehmen, der Test
   muss rot werden; danach aus den Originalbytes wiederherstellen.
7. **Nach dem Fix erneut angreifen:** dieselben Methoden, blind, auf den
   gefixten Stand. "Geschlossen" heisst ein Befund erst, wenn eine
   solche Runde in seinem Bereich keinen bestaetigten Fund mehr liefert.
   Bis dahin heisst der Stand "Fix gebaut" (roter Test, Fix,
   Mutationsprobe, Suite) — und so steht es auch im PR.
8. **Keine Frist auf eine Fix-Runde.** Ein Merge zur Integration ist in
   Ordnung; eine Aussage "geschlossen" unter Zeitdruck nicht.

Vokabular fuer Status und PR-Text: *Fix gebaut*, *kalibriert* (der
blinde Angreifer fand den Befund vor dem Fix), *angegriffen, n Runden,
m Funde*, *geschlossen* (letzte Runde ohne Fund). Nichts anderes.

## Test-Disziplin (auch ausserhalb von Reviews)

- **Mutations-Denken:** frage je Test "welcher eingebaute Bug wuerde
  von KEINEM Test gefangen?" — Toleranz um Groessenordnungen
  verstellen, Guard entfernen, all() zu any(): das muss rot werden.
- **Unabhaengige Kontrollrechnung:** gegen einen anderen Rechenweg
  oder die Rohdaten pruefen, nie gegen denselben Code (f(x)==f(x)
  belegt nichts). Bei Fixtures: Soll-Werte von Hand oder aus der
  Quelle, nicht aus dem Prueflaeufer selbst.
- **Ehrliche Skips:** Tests, die Laufzeit-Artefakte brauchen
  (generierter Kern, Fall-Arbeitsbereich), skippen mit sprechender
  Begruendung statt gruen zu luegen (`skipif` + reason).
- **Determinismus testen:** Dump->Load->Dump byte-identisch;
  wiederholte Laeufe identisch; sortierte Ausgaben.
- **Grenzen testen:** der letzte gueltige und der erste ungueltige
  Wert (t-1/t, MAX_ALTER, Kappungen), nicht nur die Mitte.
- **Fehlerpfade testen:** jede sprechende Fehlermeldung, auf die sich
  Nutzer verlassen sollen, hat einen Test (match=...).

## Umfang kalibrieren

Kleiner Block: eine Runde mit 2-3 Methoden, Schritte 2-6. Externe
Pruefrunde, grosser Bau oder abnahmerelevanter Pfad: das volle Muster
einschliesslich Kalibrierung (1) und Angriff nach dem Fix (7). Fixes
reviewen sich nie selbst. Modell und Aufwand der Pruefer werden
ausdruecklich gesetzt, nicht geerbt; erst ein kleiner Pilot, dann die
Breite. Eine Vorlage fuer den Angriff als Workflow liegt unter
`.claude/workflows/angriff-blind.js`.
