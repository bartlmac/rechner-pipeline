---
name: teste-adversarial
description: >-
  Quality-assure a finished block of work with the established adversarial pattern:
  independent review dimensions produce findings, every finding is adversarially
  verified against the real code (refute-first), confirmed findings are fixed and
  anchored as regression tests. Also carries the repo's test-writing discipline
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

## Das etablierte Muster (mehrfach bewaehrt in diesem Repo)

1. **Dimensionen schneiden** (3-5, je nach Block): typischerweise
   Korrektheit (Randfaelle, Zustandsmaschinen, Atomizitaet),
   Contract-Treue (Gate-/Ledger-/Exit-Konventionen, Schnittstellen),
   Test-Luecken (Mutations-Denken), Fachlichkeit (aktuarielle
   Substanz, P1-P10), Determinismus/Sicherheit.
2. **Finden:** je Dimension ein unabhaengiger Reviewer mit klarem
   Auftrag ("melde nur belegbare Defekte mit konkretem Szenario:
   Eingabe/Zustand -> falsches Verhalten"). Structured Output:
   titel, datei, zeile, problem, szenario, schwere.
3. **Verifizieren:** JEDES Finding einzeln adversarial pruefen —
   Auftrag ist WIDERLEGEN, Repro-Schnipsel gegen den echten Code
   (nur lesend im Repo, Skripte in /tmp), im Zweifel NICHT bestaetigt.
4. **Fixen:** alle bestaetigten Findings beheben; jede Fix-Klasse
   bekommt einen Regressionstest, der die vom Review nachgewiesene
   Mutation ab jetzt rot macht. Verworfene Findings mit Grund
   protokollieren.
5. **Abschluss:** volle Suite gruen; Ergebnis in einem Commit mit den
   wichtigsten Findings im Text (WARUM sie echt waren).

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

Kleiner Block: eine Runde, 2-3 Dimensionen. Grosser Bau oder
abnahmerelevanter Pfad: volle Runde + Nachreview der Teile, die NACH
dem Review entstanden sind (Fixes reviewen sich nicht selbst).
