# ADR-012: Gate-Namen sagen, wer entscheidet und worueber

Status: angenommen (Beschluss Auftraggeber 2026-08-27), Umsetzung
2026-08-27 — vollstaendige Umstellung aller Gate-Namen in Code, Ledgern,
Tests, Dokumentation und Skills.

## Kontext

Die Gate-Namen sind historisch gewachsen: acht Namen nach sieben
verschiedenen Bildungsregeln. Der Befund im Einzelnen:

**Der Buchstabe sagt nichts.** `G` stand bei `G0.extraction-manifest`
fuer eine maschinelle Pruefung, bei `G-1` fuer eine menschliche Abnahme
und bei `G2-vorlage.migrationsabnahme` fuer die Zuarbeit zu einer
Abnahme. Drei verschiedene Dinge, ein Buchstabe.

**Ein Bindestrich trennte zwei Welten.** `G-2` war die menschliche
Abnahme des Migrationscontrollings; `G2.static-security` war die
statische Sicherheitspruefung der mit ADR-006 abgeschalteten
Vergleichskern-Kette. Zwei voellig verschiedene Pruefungen, deren Namen
sich um ein Zeichen unterschieden.

**Die Nummern hatten keine gemeinsame Achse.** `O0`, `O1`, `O3` ohne
`O2`, ohne dass irgendwo stand, was `O2` war. `B1` ohne `B2`. `G0` ohne
`G1` in derselben Familie, denn `G-1` war etwas anderes.

**Die Vorlagen doppelten.** `GA-vorlage.aktuarieller-test` erzeugte die
Vorlage fuer Gate `G-A` — zwei Schreibweisen desselben Gates in einem
System, das seine Belege ueber genau diese Namen bindet.

**Die Suffixe mischten Sprachen.** `.abox-contract` und
`.extraction-manifest` sind Werkzeugsprache, `.aktuarieller-test` und
`.migrationsabnahme` sind Unternehmenssprache. Wer die Ledger liest,
sah beides nebeneinander.

Kritik daran kam aus mehreren Richtungen. Der Zeitpunkt der Umstellung
ist jetzt: Das System ist im Anfangsstadium, es ist nie eine Migration
nach aussen gelaufen, der einzige Vorfuehrfall wird ohnehin neu
aufgesetzt (das Snapshot-Schema ist mit ADR-010 auf Version 5
gestiegen), und mit dem Ausbau des aktuariellen Tests kommen weitere
Gates hinzu. Jedes Gate, das vor der Umstellung entsteht, verteuert sie.

## Entscheidung

### 1. Zwei Achsen, beide im Namen sichtbar

```
<Art>-<Gegenstand><Nummer>.<fachliche Kennung>
```

**Art** — wer entscheidet:

| | |
|---|---|
| `P` | **Pruefung.** Maschinell, deterministisch, blockiert bei Rot. Kein Mensch beteiligt. |
| `A` | **Abnahme.** Ein Mensch entscheidet und zeichnet; das Gate erzeugt die Vorlage und haelt den Snapshot. |

**Gegenstand** — worueber:

| | |
|---|---|
| `Q` | Quellen und Ontologie |
| `K` | Rechenkern |
| `B` | Bestand |
| `M` | Migration als Ganzes |

**Nummer** — Reihenfolge innerhalb des Gegenstands, lueckenlos vergeben.
Ein abgeschaltetes Gate hinterlaesst eine Luecke; es rutscht nichts nach,
weil Nachrutschen genau die Verwechslung erzeugt, die diese Ordnung
abschafft.

**Fachliche Kennung** in Unternehmenssprache, weil Pruefer und Revision
die Belege lesen.

### 2. Das Register

| bisher | jetzt | Gegenstand |
|---|---|---|
| `G0.extraction-manifest` | `P-Q1.quellfragment` | Vorverdichtung eines Quell-Werks |
| `O0.abox-merge` | `P-Q2.zusammenfuehrung` | Zusammenfuehrung der Fragmente |
| `O1.abox-contract` | `P-Q3.fachliche-pruefung` | A-Box gegen Contract und Register |
| `O3.generation-golden-master` | `P-K1.generations-golden-master` | Kern gegen die Tarif-Spez |
| `B1.bestand-contract` | `P-B1.bestandspruefung` | Bestandsabzug gegen Contract |
| `GA-vorlage.aktuarieller-test` | `A-M1.stichtagstest` | Vorlage der aktuariellen Abnahme |
| `G2-vorlage.migrationsabnahme` | `A-M4.migrationscontrolling` | Vorlage der Controlling-Abnahme |
| `G-1` | `A-Q1` | Quellenabnahme |
| `G-T` | `A-K1` | Tarifgeneration |
| `G-A` | `A-M1` | Stichtagstest |
| `G-2` | `A-M4` | Migrationscontrolling |
| `P9.gate-entscheid` | `entscheid.vollzug` | das Entscheid-Kommando |
| `P9.<gate>` | `entscheid.<abnahme>` | Ledger-Eintrag eines Vollzugs |

**`A-M2` (Verlaufstest) und `A-M3` (Geschaeftsvorfalltest)** waren bei
Abfassung reserviert; sie sind inzwischen vergeben und gebaut
(`gates.aktuartest --abnahme A-M2|A-M3`, Snapshots ueber
`gates.gate_entscheid`). Der aktuarielle Test ist mit einem Stichtag
nicht vollstaendig; er besteht aus drei Abnahmen, die im Bestands-Scope
dem Controlling A-M4 alle drei als Pflichtvorgaenger vorausgehen (im
Tarif-Scope nur A-M1; Entscheidung des Auftraggebers 2026-08-31,
erzwungen in `gate_entscheid`). Die Nummern standen vorab fest, damit
nichts nachrutscht.

### 3. Warum der Entscheid-Vollzug nicht mehr `P9` heisst

Das Entscheid-Kommando baute seinen Ledger-Namen bisher dynamisch als
`P9.<gate>` — `P9` ist das Kuerzel des Prinzips „unveraenderliche
Gate-Snapshots" aus `prinzipien.md`. Mit `P` als Kuerzel fuer Pruefung
haette `P9.A-M1` zwei verschiedene `P` in einem Namen.

Aufgeloest wird das zugunsten der Lesbarkeit: Ein Ledger-Name sagt, was
der Eintrag **ist**, nicht welches Prinzip er erfuellt. Der Vollzug einer
Abnahme heisst deshalb `entscheid.A-M1`. Das Prinzip P9 bleibt
unveraendert in Kraft und steht dort, wo Prinzipien stehen.

### 4. Vorlage und Vollzug sind derselbe Gegenstand

Bisher gab es fuer eine Abnahme zwei Namen: das Vorlagen-Kommando
(`GA-vorlage.aktuarieller-test`) und das Gate (`G-A`). Kuenftig traegt
beides dieselbe Kennung: Das Kommando schreibt `A-M1.stichtagstest`, der
Vollzug schreibt `entscheid.A-M1`. Wer einen Beleg liest, sieht ohne
Nachschlagen, dass beide zur Abnahme `A-M1` gehoeren.

### 5. Die Reihenfolge wird lesbar

`A-M1` vor `A-M4` ist sichtbar dieselbe Kette, die ADR-010 fordert.
Bisher musste man wissen, dass `G-A` vor `G-2` kommt.

## Folgen

* Alle Ledger-, Snapshot- und Belegrollen-Namen aendern sich. Bestehende
  Ledger und Snapshots des lokalen Vorfuehrfalls sind damit keine
  gueltigen Belege mehr. Das ist hinnehmbar und war bereits durch das
  Schema Version 5 aus ADR-010 der Fall: Der Fall wird neu aufgesetzt.
* Das CLI-Argument `--gate` nimmt die neuen Werte; die Skills, die es
  aufrufen, sind mitgezogen.
* Der Gate-Katalog (`gates/_common.ALL_GATES`) bleibt die eine Quelle.
  Ein Gate, das dort fehlt, gilt weiterhin als `required`.
* Zehn aeltere ADRs nennen Gate-Namen im Text. Sie sind auf die neuen
  Namen umgestellt, nicht mit einem Uebersetzungsvermerk versehen: Ein
  ADR, das ein Gate nennt, das es nicht mehr gibt, zwingt jeden Leser zum
  Uebersetzen. Die Beschluesse selbst sind unveraendert; das haelt der
  Hinweis in `docs/architektur/README.md` fuer die ganze Sammlung fest,
  damit nicht zehn Dokumente denselben Vermerk tragen.

## Nachtrag 2026-09-05: Versionierungsregel der Gates

Beschluss des Maintainers nach dem externen Review T21-09 (P-B1 hatte
seine Akzeptanzmenge geaendert und trug weiter `2.1.0`); die Regel war
seit der Runde T16 als Folgearbeit notiert und wurde dreimal als Befund
gemeldet. Jedes Gate traegt eine `GATE_VERSION` nach dieser Regel:

* **Major** (`x.0.0`), wenn sich die Akzeptanzmenge aendert: ein vorher
  gruener Beleg kann rot werden oder umgekehrt. Dazu zaehlt jede neue
  Pflichtpruefung, jede Verschaerfung einer bestehenden und jede neue
  Pflichtrolle.
* **Minor** (`0.x.0`), wenn eine optionale Rolle oder Pruefung
  hinzukommt, die bestehende Belege nicht beruehrt (ein Beleg ohne die
  neue Rolle bleibt, was er war).
* **Patch** (`0.0.x`) fuer Meldetexte und Summary-Felder ohne Wirkung
  auf das Urteil.

Jede Aenderung der Version nennt im Commit den Grund und in der
Gate-Tabelle des README die Zeile des Gates (Was hat sich geaendert,
warum dieser Sprung). `tests/test_gate_versionsregel.py` haelt Version
und README-Zeile zusammen: Traegt eine README-Zeile eine Version, muss
sie der `GATE_VERSION` des Moduls entsprechen. Was die Regel NICHT
leistet: Sie erkennt eine geaenderte Akzeptanzmenge nicht selbst —
das bleibt Urteil des Autors und Gegenstand des Reviews.

## Verworfene Alternativen

* **`G` fuer menschliche Abnahmen behalten** (`G-M1` statt `A-M1`).
  Haette das eingefuehrte Team-Vokabular geschont und den Satz „G heisst:
  ein Mensch entscheidet" erst wahr gemacht. Verworfen, weil `P` und `A`
  symmetrisch nebeneinander stehen und kein Buchstabe eine Altlast
  traegt: `G` hatte drei Bedeutungen, und eine davon zu behalten haette
  die anderen beiden als Gedaechtnisrest zurueckgelassen.
* **Sprechende Namen ohne Kuerzel** (`abnahme.aktuarieller-test`).
  Lesbar ohne Schluessel, aber ohne kurzes Wort fuers Gespraech und ohne
  sichtbare Reihenfolge.
* **Nur neue Gates auf die Systematik verpflichten, alte lassen.** Haette
  eine Umbenennung in signierten Ketten vermieden — aber es gibt keine
  solche Kette: nach aussen ist nie eine Migration gelaufen. Der
  Mischzustand waere dauerhaft gewesen und haette die Verwechslung
  konserviert, die abgeschafft werden sollte.
* **Nummerierung nach Ablaufreihenfolge statt nach Gegenstand**
  (`P1`..`P5`, `A1`..`A4`). Die Gates laufen nicht streng linear; eine
  Ablaufnummer haette eine Kette suggeriert, die es seit ADR-006 nicht
  mehr gibt.
