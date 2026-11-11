# Schicht und Pflichtmengen — Fachreferenz des aktuartest-Skills

Normative Fachreferenz des Skills `aktuartest-durchfuehren`: Schichtbeleg-
Erzeugung und Mengenregel der Pflichtziehung für die aktuarielle Abnahme.
Diese Datei ist ein eigenes Zuhause für den hier benannten Stoff — der
`migrationsfall-durchfuehren`-Skill verweist hierauf, statt den Stoff
zu duplizieren. Lade die Abschnitte, die dein Lauf braucht, vollständig.

## Inhaltsverzeichnis

- [Schichtbeleg erzeugen (Producer)](#schichtbeleg)
- [Mengenregel: Pflichtziehung auskunftsgedeckter Policen](#pflichtmengen)

<a id="schichtbeleg"></a>
## Schichtbeleg erzeugen (Producer)

Den Schichtbeleg fuer `aktuartest_lauf --schicht`, `migrationssuite_lauf
--schicht` und `fuehrungsprobe --schicht` erzeugt das Systemkommando

```
python -m rechner_pipeline.gates.verankerung_belegen \
    --fall faelle/<fall> --repo-root . --generation <gen>
```

aus `verankerung.parquet`, Stamm, Merkmalen und der Fall-Spez — die
Formfunktion (und ggf. das Fenster) der Korrekturschicht ist Inhalt des
Tarifplans der Migration (Grundsatzdokumentation 10 Nr. 9) und steht
belegt in der Spez (`quellverfahren.formfunktion`, `.fenster`), dieselbe
Fassung, mit der die Uebernahme die PEX-Buchung rechnet — mit
Provenienzblock (Eingabe-Hashes + Systemstand), den der Testlauf
NACHRECHNET — und schreibt die Schicht zugleich als `schichten.parquet`
in das Uebernahme-Verzeichnis, wo die Fuehrung sie liest (Freischaltung).
Kein Fall-Skript, keine Registrierung von Systemartefakten in den
Eingang; nach jeder Codeaenderung neu erzeugen. Exit 0 nur bei
vollstaendiger Tabelle — Befunde entscheiden, dann neu erzeugen.

WICHTIG davor: alle offenen/vorlaeufigen Diskrepanzen der Spez endgueltig
aufloesen — eine Schicht, die eine ungeklaerte Diskrepanz glattzieht,
ist ein Regler, kein Beleg.

Im Bestands-Scope ist bei vorhandener Datei
`abgeleitet/bestand/verankerung.parquet` der Schichtbeleg Pflicht — für
A-M1, A-M2 und A-M3 gleichermaßen, und fuer die Suite (Anker
`pflichtmengen` unten): zuerst `gates.verankerung_belegen` auf dem
festen Fallbestand fahren und seinen abgeleiteten Beleg nennen. Er muss
die gebundenen Bytes von `bestand.parquet` und `verankerung.parquet`
fuehren; ein registrierter Schichtbeleg genuegt nicht. Fehlen Laufmanifest
und Verankerungsdatei beide, ist ein Lauf ohne `--schicht` moeglich.
Widersprechen sich Manifest und Datei oder ist die vorhandene Datei leer
oder beschädigt, den Migrationszugang und den Schichtbeleg neu erzeugen,
statt die Datei zu umgehen. Ein Lauf mit `--schicht` haelt den
Schichtbeleg gegen seine eigene Auskunft: Die Schicht ist auf der
Anfangslage EINER Auskunft verankert, ein Lauf mit einer anderen (oder
ohne) verweigert mit dem Ausweg — dieselbe `--red-anteile-datei` an
allen Kommandos.

<a id="pflichtmengen"></a>
## Mengenregel: Pflichtziehung auskunftsgedeckter Policen

Schichtbelegpflicht, Pflichtziehung und allgemeine Stichprobe sind
verschieden:

- **Pflichtziehung ist keine Stichprobe.** Die registrierte Auskunft
  (zu den Herabsetzungsanteilen je Police) deckt die Policenmenge, der
  die Abnahme per Vertragsrechnung gegenuebersteht: fuer A-M1 und A-M2
  die auskunftsgedeckten Policen, fuer A-M3 die davon gedeckten Policen
  mit Vorfall im Pruefzeitraum. Diese Menge geht mit in die A-M4-Suite
  und wird dort geprueft (A-M4 prueft diese Mengen).
- Die Codepruefung bleibt massgeblich; aus der Mengenregel wird KEINE
  neue Vollerhebung fuer alle Aktuartests abgeleitet.
- Die allgemeine Stichprobe (`qa.stichprobe`, `vollbestand`/`geschichtet`)
  bleibt eine eigene, belegte Ziehung; sie ersetzt die Pflichtziehung
  nicht und wird nicht durch sie ersetzt.
- Eine auskunftsgedeckte Police, die die Abnahme uebergeht, ist ein
  Pflichtziehungsfehlstand und gehoert als Befund an den Menschen —
  nie stillschweigend aus dem Pruefumfang gestrichen.

Vertrag ohne ableitbaren Anfangszustand: hält den Lauf an (kein stiller
Grundvertrag); ein Vertrag, dessen Struktur die Auskunft traegt, ist
Pflichtziehung von A-M1, A-M2 und der Suite; A-M3 verlangt daraus die
Policen mit Vorfall im Pruefzeitraum — A-M4 prueft diese Mengen.
