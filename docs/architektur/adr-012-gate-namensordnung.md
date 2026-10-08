# ADR-012: Gate-Namen sagen, wer entscheidet und worüber

**Status:** angenommen am 2026-08-27 (Maintainer), am selben Tag
umgesetzt: Alle Gate-Namen in Code, Ledgern, Tests, Dokumentation und
Skills sind umgestellt.

## Kontext

Die Gate-Namen sind historisch gewachsen: acht Namen nach sieben
verschiedenen Bildungsregeln. Der Befund im Einzelnen:

**Der Buchstabe sagt nichts.** `G` stand bei `G0.extraction-manifest`
für eine maschinelle Prüfung, bei `G-1` für eine menschliche Abnahme
und bei `G2-vorlage.migrationsabnahme` für die Zuarbeit zu einer
Abnahme. Drei verschiedene Dinge, ein Buchstabe.

**Ein Bindestrich trennte zwei Welten.** `G-2` war die menschliche
Abnahme des Migrationscontrollings; `G2.static-security` war die
statische Sicherheitsprüfung der mit ADR-006 abgeschalteten
Vergleichskern-Kette. Zwei völlig verschiedene Prüfungen, deren Namen
sich um ein Zeichen unterschieden.

**Die Nummern hatten keine gemeinsame Achse.** `O0`, `O1`, `O3` ohne
`O2`, ohne dass irgendwo stand, was `O2` war. `B1` ohne `B2`. `G0` ohne
`G1` in derselben Familie, denn `G-1` war etwas anderes.

**Die Vorlagen doppelten.** `GA-vorlage.aktuarieller-test` erzeugte die
Vorlage für Gate `G-A`: zwei Schreibweisen desselben Gates in einem
System, das seine Belege über genau diese Namen bindet.

**Die Suffixe mischten Sprachen.** `.abox-contract` und
`.extraction-manifest` sind Werkzeugsprache, `.aktuarieller-test` und
`.migrationsabnahme` sind Unternehmenssprache. Wer die Ledger liest,
sah beides nebeneinander.

Kritik daran kam aus mehreren Richtungen. Der Zeitpunkt der Umstellung
ist jetzt: Das System ist im Anfangsstadium, es ist nie eine Migration
nach außen gelaufen, der einzige Vorführfall wird ohnehin neu
aufgesetzt (das Snapshot-Schema ist mit ADR-010 auf Version 5
gestiegen), und mit dem Ausbau des aktuariellen Tests kommen weitere
Gates hinzu. Jedes Gate, das vor der Umstellung entsteht, verteuert sie.

## Entscheidung

### 1. Zwei Achsen, beide im Namen sichtbar

```
<Art>-<Gegenstand><Nummer>.<fachliche Kennung>
```

**Art** (wer entscheidet):

| | |
|---|---|
| `P` | **Prüfung.** Maschinell, deterministisch, blockiert bei Rot. Kein Mensch beteiligt. |
| `A` | **Abnahme.** Ein Mensch entscheidet und zeichnet; das Gate erzeugt die Vorlage und hält den Snapshot. |

**Gegenstand** (worüber):

| | |
|---|---|
| `Q` | Quellen und ihre A-Box |
| `O` | Ontologie: die T-Box, das Vokabular des Zielsystems |
| `K` | Rechenkern |
| `B` | Bestand |
| `M` | Migration als Ganzes |
| `T` | Tarifwerk des Zielsystems (seit ADR-025) |
| `Z` | Zeichnungsordnung (seit ADR-025) |

**Nummer**: Reihenfolge innerhalb des Gegenstands, lückenlos vergeben.
Ein abgeschaltetes Gate hinterlässt eine Lücke; es rutscht nichts nach,
weil Nachrutschen genau die Verwechslung erzeugt, die diese Ordnung
abschafft.

**Fachliche Kennung** in Unternehmenssprache, weil Prüfer und Revision
die Belege lesen.

### 2. Das Register

| bisher | jetzt | Gegenstand |
|---|---|---|
| `G0.extraction-manifest` | `P-Q1.quellfragment` | Vorverdichtung eines Quell-Werks |
| `O0.abox-merge` | `P-Q2.zusammenfuehrung` | Zusammenführung der Fragmente |
| `O1.abox-contract` | `P-Q3.fachliche-pruefung` | A-Box gegen Contract und Register |
| `O3.generation-golden-master` | `P-K1.generations-golden-master` | Kern gegen die Tarif-Spez |
| `B1.bestand-contract` | `P-B1.bestandspruefung` | Bestandsabzug gegen Contract |
| `GA-vorlage.aktuarieller-test` | `A-M1.stichtagstest` | Vorlage der aktuariellen Abnahme |
| `G2-vorlage.migrationsabnahme` | `A-M4.migrationscontrolling` | Vorlage der Controlling-Abnahme |
| `G-1` | `A-Q1` | Quellenabnahme |
| `G-T` | `A-K1`, dann `A-O1` | T-Box-Änderung (siehe unten) |
| `G-A` | `A-M1` | Stichtagstest |
| `G-2` | `A-M4` | Migrationscontrolling |
| (neu) | `A-B1.auslieferung` | Auslieferung eines Stands-Pakets |
| (neu) | `A-K2.kernaenderung` | Änderung am Rechenkern |
| (neu) | `A-B2.zugangsabnahme` | Zugang eines abgenommenen Bestands in die produktive Ablage (ADR-022) |
| (neu) | `A-T1.tarifwerk` | Tarifwerk der PLV: Tarifpläne und Parametrierung der eigenen Generationen (ADR-025) |
| (neu) | `A-B3.anfangsbestand` | Anfangsbestand einer aufgesetzten Ablage (ADR-025) |
| (neu) | `A-Z1.ordnungsaenderung` | ein Glied der Versionslinie der Zeichnungsordnung (ADR-025; kein P9-Snapshot) |
| (neu) | `A-M6.fallauftrag` | Auftrag eines Falls durch den Vorstand (ADR-026) |
| (neu) | `A-M5.fallabbruch` | gezeichnetes Ende eines Falls ohne Abnahme (ADR-026) |
| `A-K1` | `A-O1.tbox-aenderung` | T-Box-Änderung (Gegenstand `O`) |
| `P9.gate-entscheid` | `entscheid.vollzug` | das Entscheid-Kommando |
| `P9.<gate>` | `entscheid.<abnahme>` | Ledger-Eintrag eines Vollzugs |

**`A-O1.tbox-aenderung`** (Entscheid des Maintainers 2026-09-16) ist die
Abnahme einer T-Box-Änderung. Sie hieß bis dahin `A-K1` und lag damit
unter dem Gegenstand `K`, dem Rechenkern, mit dem sie nichts zu tun
hat. Der Rechner rechnet; die T-Box legt fest, welche Begriffe das
Zielsystem überhaupt kennt.

Der alte Name war ein unbereinigter Rest: `G-T` hieß „Gate Tarif“ und
nahm wirklich eine Tarifgeneration ab. Seit Befund T22-02 verlangt der
Belegvertrag aber `tbox_aenderung`, und die Tarifgeneration wird von
`P-K1` und `A-M4` abgenommen. Register und Beleg sagten seither
Verschiedenes; jetzt sagen sie dasselbe.

Dafür bekommt die Ontologie einen eigenen Gegenstand `O`, und `Q`
schärft sich auf „Quellen und ihre A-Box“. Das ist keine Spitzfindigkeit:
Die A-Box sind die Instanzen, die aus einer Quelle kommen, je Fall; die
T-Box ist das Vokabular des Zielsystems, fallübergreifend. `P-Q1` bis
`P-Q3` und `A-Q1` bleiben deshalb, wo sie sind: sie betreffen wirklich
die Quelle.

Gezeichnet wird `A-O1` von `mensch/architektur`: Wer verantwortet, welche
Begriffe das Zielsystem führt, verantwortet sein Datenmodell. Die
fachliche Seite der Frage (ist das Feld tarif- oder bewertungswirksam,
was geht verloren, wenn es entfällt) gehört aber dem Aktuariat, und
deshalb verlangt der Belegvertrag zusätzlich dessen Stellungnahme.
Dasselbe Muster wie bei `A-B1`: Die Unterschrift gehört einer Rolle,
der Beleg kommt aus einer anderen. Eine Doppelunterschrift kennt das
System nicht; geteilte Verantwortung ist keine.

**`A-K2.kernaenderung`** (Entscheid des Maintainers 2026-09-16) nimmt
eine Änderung an Code oder Dokumentation des Rechenkerns ab. Art `A`,
weil ein Mensch zeichnet; Gegenstand `K`, weil der Rechenkern gemeint
ist; Nummer 2, weil die 1 unter `K` vergeben war: sie gehörte dem
Gate, das heute `A-O1` heißt. Nach der Regel dieses ADR rutscht
nichts nach: `A-K1` bleibt eine Lücke.
Gezeichnet wird sie von `mensch/rechenkern`; bis dahin war das
folgenreichste, was am Zielsystem geschieht, nur durch Commit-Disziplin
geregelt (Abnahme-Protokoll in `kern/__init__`): keine Zeichnung, kein
Schlüssel, kein Snapshot.

Auslöser ist die Änderung am Kern, gleich aus welchem Anlass. Eine
neue Tarifgeneration löst sie ausdrücklich nicht aus: Sie ist
Parametrierung (ADR-006: „der Präzedenzfall TG2012 -> TG2015 lief ohne
eine einzige Formeländerung durch“) und wird von `P-K1` deterministisch
und von `A-M4` menschlich abgenommen, das `pk1_belege` in beiden Scopes
pinnt. Machte man sie zum Auslöser, entstünde regelmäßig eine
Unterschrift über einen unveränderten Kern.

Sie trägt `regression` als PFLICHTbeleg: jeder Vertrag mit altem und
neuem Kern durchgerechnet, Differenz je Vertrag. Solange es den
Produzenten dafür nicht gibt, ist A-K2 nicht zeichenbar. Das ist gewollt, denn
der geänderte Kern bewertet nach der Migration den laufenden Bestand
weiter, und diese Wirkung sieht sonst niemand.

**Nachtrag 2026-10-01** (Entscheid des Maintainers, ADR-018 Nachtrag
2026-10-01): A-K2 ist Teil des Ablaufs. Gegenstand ist der Kernstand, auf
dem ein Fall rechnet, einschließlich der Änderungen außerhalb eines
Falls. `A-M4` verlangt in beiden Scopes, dass er abgenommen ist
(Pflichtrolle `kernstand`): im Fall gezeichnet, oder bei unverändertem
Stand „keine Änderung seit Abnahme <snapshot>“ über einen Verweis auf
einen früher angenommenen A-K2-Snapshot. Dieselbe Regel gilt für
`A-O1` und den T-Box-Stand (Pflichtrolle `tboxstand`; zusätzlich die
Basislinie: eine Versionslinie mit einem Element hat keinen Übergang).
Damit gilt der Satz oben „löst eine Tarifgeneration nicht aus“ weiter
für den Anlass (eine Tarifgeneration erzwingt keine Kernänderung),
aber jeder Fall rechnet auf einem abgenommenen Kernstand. Zwei Prüfungen: die
qualitative Prüfung der Änderungen entlang der Module mit den Commits
des Zweigs (Produzent `gates.kernstand_belegen`, das Gate rechnet nach)
und die Regression. Die Regression ist bis zu ihrem Produzenten eine
benannte Ausnahme („nicht gefahren, Werkzeug noch nicht erstellt“),
nie ein Ergebnis; A-K2 ist damit zeichenbar, und die Zeichnung deckt
ausdrücklich nur die qualitative Prüfung. Der folgende Absatz zum
alten Kern gilt mit einer Änderung: Der Vergleichsstand ist der
ausdrücklich genannte, zuletzt abgenommene Kernstand (`--von`, statt
fest `origin/main`), und `dirty` sperrt nur noch die Regression.

**Woher der alte Kern kommt** (Entscheid des Maintainers 2026-09-16):
Entwicklung im Fall läuft auf einem Branch, der produktive Kern liegt
auf `main`. Damit ist die Vorher-Seite nicht erfunden, sondern
benennbar, und der Beleg trägt beide Kern-Hashes plus den Git-Stand.
Zwei Bedingungen machen den Vergleich erst ehrlich, und beide sperren:
`dirty` muss `nein` sein (eine Regression gegen uncommittete
Änderungen ist nicht reproduzierbar), und der Zweig muss auf der
Spitze von `main` liegen (`merge_base == referenz_commit`). Läuft
`main` weiter, mischt die Differenz die eigene Änderung mit einer
fremden; dann wird der Zweig auf die neue Spitze gesetzt und neu
gerechnet.

Der Git-Stand im Beleg wird gegen den lebenden Stand gehalten, nicht nur
gegen sich selbst: Ein Beleg, der einen fremden, in sich schlüssigen
Commit nennt, fällt auf (Befund T24-04).

Zwei Kernstände in einem Lauf gibt es dabei nicht: Dynamische Lader
sind in `src` ein Befund der Code-Karte, weil sie ein Modul an jeder
Kante vorbeiholen. Der Produzent rechnet deshalb zweimal (im
`main`-Worktree und im Branch) und ein Vergleicher, der nur Daten liest
und keinen Kern importiert, bildet die Differenz.

**`A-B1.auslieferung`** (Entscheid des Maintainers 2026-09-16) ist die
erste Abnahme mit Gegenstand `B`: Sie zeichnet den Moment, in dem ein
Stands-Paket nach außen sichtbar wird. Die Nummer 1 ist frei, weil die
Nummern je Art und Gegenstand laufen: `P-B1.bestandspruefung` ist eine
Prüfung, `A-B1.auslieferung` eine Abnahme. Gezeichnet wird sie von
`mensch/betrieb`, einer fachlichen Rolle (Kundenservice-Verantwortung
für die Bestandsführung), nicht von der IT: Was ausgeliefert wird,
verantwortet der Betrieb, nicht der, der die Maschine betreibt.

**`A-M2` (Verlaufstest) und `A-M3` (Geschäftsvorfalltest)** waren bei
Abfassung reserviert; sie sind inzwischen vergeben und gebaut
(`gates.aktuartest --abnahme A-M2|A-M3`, Snapshots über
`gates.gate_entscheid`). Der aktuarielle Test ist mit einem Stichtag
nicht vollständig; er besteht aus drei Abnahmen, die im Bestands-Scope
dem Controlling A-M4 alle drei als Pflichtvorgänger vorausgehen (im
Tarif-Scope nur A-M1; Entscheidung des Auftraggebers 2026-08-31,
erzwungen in `gate_entscheid`). Die Nummern standen vorab fest, damit
nichts nachrutscht.

### 3. Warum der Entscheid-Vollzug nicht mehr `P9` heißt

Das Entscheid-Kommando baute seinen Ledger-Namen bisher dynamisch als
`P9.<gate>`; `P9` ist das Kürzel des Prinzips „unveränderliche
Gate-Snapshots“ aus `prinzipien.md`. Mit `P` als Kürzel für Prüfung
hätte `P9.A-M1` zwei verschiedene `P` in einem Namen.

Aufgelöst wird das zugunsten der Lesbarkeit: Ein Ledger-Name sagt, was
der Eintrag **ist**, nicht welches Prinzip er erfüllt. Der Vollzug einer
Abnahme heißt deshalb `entscheid.A-M1`. Das Prinzip P9 bleibt
unverändert in Kraft und steht dort, wo Prinzipien stehen.

### 4. Vorlage und Vollzug sind derselbe Gegenstand

Bisher gab es für eine Abnahme zwei Namen: das Vorlagen-Kommando
(`GA-vorlage.aktuarieller-test`) und das Gate (`G-A`). Künftig trägt
beides dieselbe Kennung: Das Kommando schreibt `A-M1.stichtagstest`, der
Vollzug schreibt `entscheid.A-M1`. Wer einen Beleg liest, sieht ohne
Nachschlagen, dass beide zur Abnahme `A-M1` gehören.

### 5. Die Reihenfolge wird lesbar

`A-M1` vor `A-M4` ist sichtbar dieselbe Kette, die ADR-010 fordert.
Bisher musste man wissen, dass `G-A` vor `G-2` kommt.

## Folgen

* Alle Ledger-, Snapshot- und Belegrollen-Namen ändern sich. Bestehende
  Ledger und Snapshots des lokalen Vorführfalls sind damit keine
  gültigen Belege mehr. Das ist hinnehmbar und war bereits durch das
  Schema Version 5 aus ADR-010 der Fall: Der Fall wird neu aufgesetzt.
* Das CLI-Argument `--gate` nimmt die neuen Werte; die Skills, die es
  aufrufen, sind mitgezogen.
* Der Gate-Katalog (`gates/_common.ALL_GATES`) bleibt die eine Quelle.
  Ein Gate, das dort fehlt, gilt weiterhin als `required`.
* Zehn ältere ADRs nennen Gate-Namen im Text. Sie sind auf die neuen
  Namen umgestellt, nicht mit einem Übersetzungsvermerk versehen: Ein
  ADR, das ein Gate nennt, das es nicht mehr gibt, zwingt jeden Leser zum
  Übersetzen. Die Beschlüsse selbst sind unverändert; das hält der
  Hinweis in `docs/architektur/README.md` für die ganze Sammlung fest,
  damit nicht zehn Dokumente denselben Vermerk tragen.

## Nachtrag 2026-10-01: drei Namen der Erstabnahme (ADR-025)

* **`A-T1.tarifwerk`**: ein neuer Gegenstand `T`, Nummer 1: Das Tarifwerk
  der PLV ist weder Rechenkern (`K`) noch Vokabular (`O`) noch eine Quelle
  (`Q`). Es lief bis hierher im Kernstand mit und wurde von der falschen
  Rolle gezeichnet; jetzt zeichnet `mensch/aktuariat`.
* **`A-B3.anfangsbestand`**: Gegenstand `B`, die nächste freie Nummer.
* **`A-Z1.ordnungsaenderung`**: ein neuer Gegenstand `Z` (die
  Zeichnungsordnung), Nummer 1: die Zeichnung eines Glieds ihrer
  Versionslinie durch die Wurzelrolle. Kein P9-Snapshot, deshalb nicht im
  Entscheid-Kommando; aber eine Kennung, die eine Ordnung vergeben kann.

Der künftige Fallauftrag bekommt einen eigenen Namen; `A-M5` bleibt dem
Fallabbruch vorbehalten.

## Nachtrag 2026-10-01: Auftrag und Abbruch eines Falls (ADR-026)

* **`A-M5.fallabbruch`**: wie am 2026-09-16 vorgesehen: Art `A`, Gegenstand
  `M` (die Migration als Ganzes), Nummer 5. Gezeichnet von der Programmleitung
  des Falls.
* **`A-M6.fallauftrag`**: Art `A`, Gegenstand `M`, die nächste freie Nummer.
  Der Auftrag betrifft die Migration als Ganzes wie der Abbruch; beide Enden
  des Lebenslaufs stehen unter demselben Gegenstand. Die Nummer sagt die
  Reihenfolge der Vergabe, nicht die des Ablaufs: Der Auftrag kommt im Ablauf
  zuerst, vergeben wurde zuerst `A-M5`. Verworfen: `A-M0` (die Nummern
  beginnen bei 1) und ein eigener Gegenstand für zwei Gates, die beide die
  Migration als Ganzes betreffen.

Beide stehen im Register (Abschnitt 2).

## Nachtrag 2026-09-05: Versionierungsregel der Gates

Beschluss des Maintainers nach Befund T21-09 einer externen Prüfung
(P-B1 hatte seine Akzeptanzmenge geändert und trug weiter `2.1.0`); die
Regel war seit Längerem als Folgearbeit notiert und wurde dreimal als
Befund gemeldet. Jedes Gate trägt eine `GATE_VERSION` nach dieser Regel:

* **Major** (`x.0.0`), wenn sich die Akzeptanzmenge ändert: ein vorher
  grüner Beleg kann rot werden oder umgekehrt. Dazu zählt jede neue
  Pflichtprüfung, jede Verschärfung einer bestehenden und jede neue
  Pflichtrolle.
* **Minor** (`0.x.0`), wenn eine optionale Rolle oder Prüfung
  hinzukommt, die bestehende Belege nicht berührt (ein Beleg ohne die
  neue Rolle bleibt, was er war).
* **Patch** (`0.0.x`) für Meldetexte und Summary-Felder ohne Wirkung
  auf das Urteil.

Jede Änderung der Version nennt im Commit den Grund und in
`docs/architektur/gate-vertrag-und-versionen.md` (bis ADR-027 im README)
im Abschnitt des Gates: Was hat sich geändert, warum dieser Sprung.
`tests/test_gate_versionsregel.py` hält die Version der Tabellenzeile und
das Modul zusammen: Trägt eine Zeile dieser Tabelle eine Version, muss sie der
`GATE_VERSION` des Moduls entsprechen. Was die Regel nicht
leistet: Sie erkennt eine geänderte Akzeptanzmenge nicht selbst;
das bleibt Urteil des Autors und Gegenstand des Reviews.

## Verworfene Alternativen

* **`G` für menschliche Abnahmen behalten** (`G-M1` statt `A-M1`).
  Hätte das eingeführte Team-Vokabular geschont und den Satz „G heißt:
  ein Mensch entscheidet“ erst wahr gemacht. Verworfen, weil `P` und `A`
  symmetrisch nebeneinander stehen und kein Buchstabe eine Altlast
  trägt: `G` hatte drei Bedeutungen, und eine davon zu behalten hätte
  die anderen beiden als Gedächtnisrest zurückgelassen.
* **Sprechende Namen ohne Kürzel** (`abnahme.aktuarieller-test`).
  Lesbar ohne Schlüssel, aber ohne kurzes Wort fürs Gespräch und ohne
  sichtbare Reihenfolge.
* **Nur neue Gates auf die Systematik verpflichten, alte lassen.** Hätte
  eine Umbenennung in signierten Ketten vermieden, aber es gibt keine
  solche Kette: nach außen ist nie eine Migration gelaufen. Der
  Mischzustand wäre dauerhaft gewesen und hätte die Verwechslung
  konserviert, die abgeschafft werden sollte.
* **Nummerierung nach Ablaufreihenfolge statt nach Gegenstand**
  (`P1`..`P5`, `A1`..`A4`). Die Gates laufen nicht streng linear; eine
  Ablaufnummer hätte eine Kette suggeriert, die es seit ADR-006 nicht
  mehr gibt.
