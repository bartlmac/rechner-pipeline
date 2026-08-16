---
name: bereite-fachkonflikt-auf
description: >-
  Prepare a fachlicher Konflikt (Diskrepanz between sources, anchor deviation,
  contradiction between Meldung/Rechner/Bestand, T-Box tension) for HUMAN decision:
  verify both readings against the sources, assess actuarial plausibility and impact,
  produce a decision dossier with a recommendation — then STOP. Agents never decide
  fachliche Konflikte (P2/P4). Trigger when discrepancies surface (Gate O1, merge,
  anchor mismatch) and a decision needs preparing, or when the user asks to
  assess/prepare a fachlichen Widerspruch. Skip for: resolving the conflict (human,
  via ontologie.entscheide + gate_entscheid), technical bugs (fix them), extraction
  errors (correct the fragment with verification note).
---

# Fachkonflikt fuer die menschliche Entscheidung aufbereiten

## Rolle und Grenze

Du bereitest vor, du entscheidest NICHT. Das Ergebnis ist ein
Entscheidungs-Dossier plus optional eine VORLAEUFIGE Arbeits-Aufloesung
(`vorlaeufig=True`, blockt jede menschliche Annahme) — nie eine
endgueltige Wahl. Die Entscheidung faellt ein benannter Mensch mit
`python -m rechner_pipeline.ontologie.entscheide` und snapshottet sie
mit `gates.gate_entscheid` (P9).

## Schritt 1: Konflikt-Klasse bestimmen

| Klasse | Erkennungszeichen | Weg |
|---|---|---|
| Extraktionsfehler | eine Lesart haelt der Nachpruefung gegen die eigene Quelle nicht stand (falsche Zeile, falscher Satzteil, Normalisierungsfehler) | KEIN Fachkonflikt: Fragment korrigieren, Anmerkung dokumentieren, Akteur um `+verifikation` ergaenzen, neu mergen |
| Echter Quell-Widerspruch | beide Lesarten sind in ihrer Quelle woertlich belegt | Dossier (unten) |
| Verankerungs-Konflikt | Anker- oder Gate-O3-Verankerung weicht nach einer Aenderung ab | erst Eigenfehler ausschliessen; sonst Dossier mit Wert-Diff und Ursachenanalyse (Abnahme-Protokoll des Kerns gilt) |
| Modell-Spannung | die T-Box kann einen Sachverhalt nicht ausdruecken (fehlendes Feld, fehlende Klasse) | G-T-Vorlage: Aenderungsvorschlag als Artefakt, kein stilles Einbauen |

## Schritt 2: Beide Lesarten VERIFIZIEREN

Jede Lesart gegen ihre Original-Fundstelle in der Vorverdichtung
pruefen (nie gegen die Erinnerung, nie gegen die andere Quelle).
Woertliches Zitat + Fundstelle ins Dossier. Erst wenn beide Lesarten
echt sind, ist es ein Fachkonflikt.

## Schritt 3: Einordnen und Auswirkungen berechnen

- **Fachliche Einordnung:** was spricht fuer welche Lesart
  (Rechtsrahmen wie Hoechstrechnungszins-Historie, Konsistenz mit der
  Vorgaenger-Generation, interne Konsistenz der Quelle, typische
  Fehlerbilder wie "Excel nicht nachgezogen"). Quellen-Hierarchie ist
  fallabhaengig und NICHT dein Urteil — benenne die Kandidaten
  (eingereichte Meldung vs. gelieferter Rechner) und was jede Wahl
  bedeutet.
- **Auswirkungsanalyse (deterministisch, rechnen statt schaetzen):**
  welche Zellen/Felder betroffen; Groessenordnung auf Beitrag/Reserve
  (Kern mit beiden Lesarten rechnen, Differenz ausweisen); Konsequenz
  fuer den Golden Master (die Wahl gegen den Rechner bricht die
  GM-Reproduktion — dann braucht die Abnahme korrigierte
  Erwartungswerte vom Lieferanten); betroffene Tests/Verankerungen.
- **Rueckfragen formulieren:** die konkrete Frage an den Lieferanten/
  Fachbereich, so gestellt, dass die Antwort die Diskrepanz schliesst.

## Schritt 4: Dossier abliefern und STOPP

Struktur (Markdown, im Fall unter `abgeleitet/konflikte/<id>.md` oder
direkt an den Menschen):

1. Diskrepanz-ID(s) und Klasse
2. Lesart A / Lesart B: woertliches Zitat, Fundstelle, Quelle+SHA
3. Fachliche Einordnung (beide Seiten, fair)
4. Berechnete Auswirkung je Wahl
5. Empfehlung MIT Begruendung — als Empfehlung markiert
6. Konkrete Rueckfrage(n)
7. Vorgeschlagene Kommandos fuer die Entscheidung (entscheide +
   gate_entscheid, ausformuliert zum Kopieren)

Dann uebergeben. Keine endgueltige Aufloesung, kein Nachfassen der
Entscheidung in eigener Autoritaet — auch nicht bei "offensichtlichen"
Faellen: offensichtlich ist ein Urteil, und Urteile sind hier
menschlich.
