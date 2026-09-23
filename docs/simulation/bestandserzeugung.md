---
title: "Bestandserzeugung und Fortschreibung"
lang: de
format:
  typst:
    papersize: a4
---

> Die Antwort auf die Frage „wie erstelle ich diesen Bestand?" — vom
> leeren Verzeichnis bis zum geführten Bestand mit Bericht. Ein
> Befehl, sechs Ausgaben, zwei Daten. Alles Weitere ist Verweis.

# 1 Ein Werkzeug, zwei Aufgaben

Den Zielbestand erzeugt und bewegt **ein** Kommando:

```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config configs/bestand_gesamt.toml --neuzugang-ab 1994-07-01 \
    --bis 2046-01-01 --out-dir runs/bestand
```

Der Name benennt nur die zweite Hälfte. Tatsächlich macht der Lauf
beides, in dieser Reihenfolge:

1. **Bestand aufbauen** — jeder eigene Vertrag entsteht als datierter
   Zugang im **Zugangsstrom** ab `--neuzugang-ab` (Attribute aus den
   Verteilungen der Config, deterministisch je Seed); ein übernommener
   Bestand kommt über `--uebernahme` dazu. Einen auf einmal gezogenen
   Anfangsbestand gibt es nicht mehr (ADR-020): Jeder Vertrag trägt
   seinen Zugang im Journal, kein Zustand steht ohne Geschichte da. Ohne
   Quelle — weder `--neuzugang-ab` noch `--uebernahme` noch
   `--portfolio` — hat der Lauf nichts zu führen und sagt das (Exit 2),
   statt still einen Bestand zu erfinden.
2. **Fortschreibung** — ein Strom datierter Geschäftsvorfälle
   (Storno, Tod, Beitragsfreistellung, dynamische Erhöhungen,
   Neuzugang) bewegt diesen Bestand bis zum Horizont `--bis`.

Eine eigene „Simulations-CLI" daneben gibt es nicht; wer sie sucht,
sucht dieses Kommando. Es ist ein **Produzent, kein Gate**: Es
schreibt keinen Ledger-Eintrag der Abnahme und hält niemanden auf.
Jeder Betrag kommt auch hier aus dem Rechenkern — die Simulation
entscheidet nur, **wann** etwas passiert, nie **wieviel** etwas wert
ist ([Erfahrungsannahmen](erfahrungsannahmen.md); die Trennung
begründet das [Simulations-README](README.md)).

# 2 Die Ausgaben

Alle unter `--out-dir`. Sechs schreibt jeder Lauf:

| Datei | Rolle |
|---|---|
| `bestand.parquet` | der Basisbestand: die übernommenen Verträge, sonst leer (ADR-020); `--portfolio` reicht stattdessen einen fertigen Bestand herein |
| `historie.parquet` | Statushistorie je Vertrag — erklärt den Zustand, trägt die Bewertung |
| `ledger.parquet` | das Bewegungsjournal: ein datierter Geschäftsvorfall je Zeile |
| `scheiben.parquet` | dynamische Erhöhungen als eigene Bausteine |
| `zugaenge.parquet` | Neuzugänge des Zugangsstroms (siehe Abschnitt 3) |
| `bestand_gesamt.parquet` | der **geführte** Gesamtbestand (ADR-011): Basis plus Neuzugänge, Statusspalten auf dem Stand des Horizonts — der Eingang für Auskunft, Auswertung und `cli_report` |

Dazu kommen **bedingte** Ausgaben — sie fehlen nicht aus Versehen,
sondern weil dieser Lauf sie nicht kennt. Keine Datei heißt „dieser
Lauf führt keine", eine leere Datei hieße „geprüft und keine
gefunden":

| Datei | Wann |
|---|---|
| `reduktionen.parquet` | wenn der Lauf Herabsetzungen gebucht hat |
| `merkmale.parquet`, `schichten.parquet`, `verankerung.parquet` | mit `--uebernahme`, wenn der übernommene Bestand sie trägt (Tarifzellen, Korrekturschicht, Verankerung) |

Und zuletzt, kein Parquet: `laufmanifest.json` — der Lieferschein
über die Bytes, die tatsächlich auf der Platte liegen. Er nennt den
Horizont und bindet jede Ausgabe mit ihrem SHA-256. Die Gates lesen
ihn; ohne ihn ist ein Lauf für die Abnahme kein Lauf, sondern eine
Ansammlung von Dateien.

# 3 Die zwei Daten — und der Zugangsstrom

`--bis` und `--stichtag` sind **verschiedene** Daten:

- `--bis` ist der **Simulationshorizont**: bis wohin Ereignisse
  projiziert werden.
- `--stichtag` gehört zum **Bericht** und markiert dort nur die
  Grenze zwischen Historie und Projektion. Er ist optional: Ohne ihn
  nimmt der Bericht `meta.referenzstichtag` aus der Config — der
  Referenzstichtag ist eine Eigenschaft des Bestands, das Flag
  übersteuert ihn nur.

**Fehllesart:** `--bis` auf „heute" zu setzen würgt die Projektion
still ab — jenseits des Referenzstichtags bleibt dann nur geplantes
Neugeschäft übrig.

**`--neuzugang-ab` ist die Quelle des eigenen Geschäfts.** Ab diesem
Tag — einschließlich, das Intervall ist `[von, bis]` (ADR-020) — zieht
der Zugangsstrom je Generation und Jahrgang seine Verträge, jeder als
eigener `ZUG`-Geschäftsvorfall im Journal. Voreingestellt ist der
`referenzstichtag` der Config; wer den **ganzen** Verlauf aus dem Strom
baut, setzt ihn auf den ersten Verkaufstag (hier `1994-07-01`). Der Lauf
weist die Abweichung vom Referenzstichtag dann als Hinweis aus — sie
gehört begründet, weil der Referenzstichtag sonst der Beginn des
simulierten Neuzugangs ist. Einen Batch, der das Verkaufsfenster still
auf einmal auffüllt, gibt es nicht mehr (ADR-020): `0 Neuzugänge` im
Laufprotokoll heißt jetzt, dass wirklich keiner ankam — nicht, dass ein
Batch die Jahrgänge schon vorab in den Basisbestand gelegt hätte.

# 4 Vom leeren Verzeichnis zum Bericht

```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config configs/bestand_gesamt.toml --neuzugang-ab 1994-07-01 \
    --bis 2046-01-01 --out-dir runs/bestand

python -m rechner_pipeline.bestand.cli_report \
    --portfolio runs/bestand/bestand_gesamt.parquet \
    --historie runs/bestand/historie.parquet \
    --ledger runs/bestand/ledger.parquet \
    --scheiben runs/bestand/scheiben.parquet \
    --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --stichtag 2026-01-01 \
    --out runs/berichte/bestandsbericht.html
```

Der erste Lauf erzeugt und bewegt den Bestand, der zweite liest die
Tabellen und schreibt den Bestandsbericht. `--merkmale` gibt nur mit,
wer Tarifzellen führt (ein übernommener Bestand); Schicht, Verankerung
und Herabsetzungen sucht `cli_report` selbst im Verzeichnis neben
`--scheiben` — wer sie weglässt, bekommt keinen Fehler, sondern einen
Bericht ohne sie. `runs/` ist Wegwerf-Arbeitsfläche: Was bleiben soll,
lebt im Fall oder als schreibgeschützter Abschluss.

# 5 Nach einer Migration

`--uebernahme faelle/<fall>/abgeleitet/bestand` nimmt das Erzeugnis
der Bestandsübernahme in den Lauf: Der übernommene Bestand wird dem
eigenen **vorangestellt** und im **selben** Fortschreibungslauf
mitgefahren — ein Geschäftsvorfall-Strom, ein Erzeuger, auch nach
einer Migration (ADR-015). Die Buchungen der Übernahme (Zugang,
Umbuchungen beitragsfrei ankommender Verträge) stehen dem Journal
voran, denn sie liegen vor dessen erstem simulierten Jahr. Eine
Übernahme ist zugleich eine der drei Quellen, die den leeren Lauf
(Exit 2, Abschnitt 1) füllen: `--uebernahme` allein trägt einen
Bestand, auch ohne eigenen Zugangsstrom.

# 6 Der Quellbestand

Die Lieferungen der fiktiven abgebenden Unternehmen erzeugt
`quellsystem/` — ein **eigenständiger Zweitkern** (Kommutations-Kopie)
mit den fremden Konventionen der Quelle (Stornoabzug je Scheibe,
eigene Rundungs- und Kalenderlogik). Er importiert bewusst nichts aus
dem Zielsystem: Was die Migration später feststellen muss, darf ihr
nicht vorab in den Code gereicht werden. Sein Export legt die
Lieferungen versioniert unter `lieferungen/` ab — von dort schneiden
auch die E2E-Fixturen. Die Fall-Regie (Seeds, Drehbücher,
Auflösungen der Vorführfälle) bleibt außerhalb des Repos.

# 7 Was die Simulation nicht ist

Keine Prüfung, kein Gate, kein Teil der Abnahme. Sie bewertet nichts
(das tut der Rechenkern auf Rechnungsgrundlagen erster Ordnung) und
ihre Annahmen wirken nie in die Bewertung zurück. Sie ist je
Vorzeigeobjekt verzichtbar, ohne dass das System etwas verliert —
genau deshalb steht sie im Komponentenbild neben dem System, nicht
darin.
