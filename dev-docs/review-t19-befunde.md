# Externes Review T19 (DORA) auf PR #11 — Befunde und Reparaturen

Externes Review vom 2026-09-04 auf Stand 730b2e9, sieben Befunde.
Diese Liste haelt fest, was daraus wurde; sie ist die Grundlage fuer
die Nachpruefung durch den Reviewer. Jeder Fix traegt seine
Befund-Nummer in der Commit-Botschaft.

| Befund | Schwere | Status |
|---|---|---|
| T19-01 `regie/` passiert die Veroeffentlichungssperre | kritisch | **behoben** (3520883) |
| T19-02 Unsignierte Roh-JSONs als gezeichnete Abnahmen | hoch | **behoben** (ec64c8a) |
| T19-03 Unvollstaendige Faelle erscheinen vollstaendig | hoch | **behoben** (ec64c8a) |
| T19-04 Dokumentierter Installationsweg nicht reproduzierbar | mittel | **offener Punkt** (Pin-Schluss, b0cb63d) |
| T19-05 A-M4-Pflichtvertrag widerspricht seinen Kommentaren | mittel | **behoben** (b82c3dd) |
| T19-06 Branch verletzt die eigene Klarnamen-Regel | mittel | **behoben** (8b3c0c6), Historie als dokumentierte Ausnahme |
| T19-07 Dokumentiertes `--sicht` existiert nicht | niedrig | **behoben** (b82c3dd) |

## Was jeweils gemacht wurde

**T19-01 — die Sperre kannte das Verzeichnis nicht.** `REGIE` trug
nur `simulation/` und `docs-local/`; der Kontrollfluss war korrekt
(die Wache laeuft vor dem Lesen). Drei Tests statt einer Zeile, weil
der alte Unit-Test den Fehler strukturell nicht finden konnte — er
prueft die Funktion mit den Werten, die die Konstante ohnehin kennt:
Parameterfall `regie/`, die Sperrliste gegen die dokumentierte
Bereichsmenge aus `dev-docs/regie.md`, und der echte CLI-Weg wie im
Review reproduziert. Alle drei per Mutation gegengeprueft.

**T19-02 — geprueft statt geglaubt.** Neu:
`gates.gate_entscheid.pruefe_snapshot_ohne_schluessel` prueft, was ohne
Geheimnis pruefbar ist — Schema, Selbstadressierung (kanonischer Hash
ueber alle Felder ausser ihm selbst) und Dateiname. Eine erfundene
oder nachtraeglich geaenderte Datei faellt daran. Die Signatur bleibt
bewusst ungeprueft, weil Schluesselmaterial nicht in ein
Darstellungswerkzeug gehoert — genau darum heisst die Kennzahl jetzt
"Abnahmen eingereicht", der Berichtsfuss nennt die Grenze, und
Snapshots mit Befund werden als solche gezeigt. Realprobe: alle 16
echten Snapshots des zweiten Laufs passieren.

**T19-03 — Mengen statt Nichtleere, Luecken ins Dokument.** Die
Vollstaendigkeitspruefung verlangt jetzt die Menge `A-M1..A-M3` plus
Controlling und je Gate einen strukturell unversehrten Entscheid; ein
Snapshot mit Befund belegt sein Gate nicht. Der Fallbericht rendert
seine Luecken als eigenen Abschnitt "Was dieser Bericht NICHT zeigt"
— vorher standen sie nur auf stderr, das Dokument sah vollstaendig
aus.

**T19-04 — als offener Punkt gefuehrt.** Der Befund ist bestaetigt
und war unabhaengig schon nach dem CI-Rot notiert: Die CI installiert
ueber die Pin-Dateien, `AGENTS.md` dokumentiert
`pip install -e ".[dev]"`, und der transitive Schluss ist
unvollstaendig. Bewusst nach dem Merge, weil die Reparatur den
Installationsvertrag beruehrt und nicht in einen laufenden Review
gehoert. (Die Team-Mail zum PR nennt bereits den funktionierenden
Weg ueber die Pin-Dateien.)

**T19-05/-07 — Doku sagt, was der Code tut.** Der Kommentar an
`BELEGROLLEN` behauptete das Gegenteil des erzwungenen
Scope-Vertrags, der Backlog fuehrte den gebauten Entscheid als
"Bau steht aus", und der Aufrufvertrag nannte eine nie gebaute
Option. Alle drei Stellen sagen jetzt dasselbe wie der Code.

**T19-06 — Regel maschinell statt als Bitte.** Der Befund nannte 9
neue Zeilen; die Pruefung am ganzen Baum zeigte 44 in 26 Dateien,
ueberwiegend aelter als dieser Branch. Alle bereinigt (Rollen statt
Namen; rein sprachlich, keine Signatur und kein Rechenwert beruehrt),
und `tests/test_klarnamen.py` macht daraus eine Wache: Wort-Hashes
gegen SHA-256-Praefixe, damit die Pruefung selbst keine Namen traegt.
Autorenfelder sind die dokumentierte Ausnahme. Fuer die
Commit-Historie hat der Maintainer die Ausnahme beschlossen (in
`AGENTS.md` an der Regel vermerkt): kein Rewrite eines gepushten
Branches, weil ein Rebase die Additiv-Regel des Merge-Plans fuer
jeden darauf gebauten Ast bricht.

## Was das Review sonst noch festhielt

- **T18-01 bis T18-07** waren auf Stand 730b2e9 unveraendert
  reproduzierbar — erwartbar, sie lagen bewusst hinter dem
  Vorfuehrfall. Nach dem Review hat der Maintainer entschieden, sie
  IN DIESEM PR zu schliessen statt in einem Folge-PR (siehe unten,
  Abschnitt T18): Der Stand soll vor der Veroeffentlichung sauber
  sein, und ein paralleler PR war unmoeglich, weil alle Zieldateien
  schon hier liegen.
- **Nachweisgrenze des Reviews**, vom Reviewer selbst gezogen:
  `docs-local/`, `simulation/` und `faelle/` lagen nicht vor. Die
  fuenf finalen Zeichnungen und die Vollbestandswerte konnten daher
  nicht kryptografisch gegen den realen Lauf geprueft werden; die
  versionierten E2E-Fixturen decken einen repraesentativen Schnitt und
  die Rechenkette ab, nicht die konkreten Snapshots.

## Nachzug: die Runde T18 (Bestandsfuehrung) in diesem PR

Sieben Befunde des Reviews vom 2026-09-01 auf dem damaligen main;
Maintainer-Entscheid 2026-09-04: in PR #11 schliessen. Nicht sieben
Flicken, sondern die drei Bewegungen aus der damaligen Antwort — die
Klasse hiess "Praedikate ueber Formen (None, leer) statt ueber die
Identitaet, die gelten muss".

| Befund | Schwere | Status |
|---|---|---|
| T18-01 ERH-Ledger und Scheiben nur ueber Jahressummen gebunden | kritisch | **behoben** (`validate_ledger`, zeilenweise Bijektion) |
| T18-02 `--bis` ist eine unbelegte Behauptung, kein Laufmanifest | kritisch | **behoben** (9a96a11, Manifest Pflicht und fail-fast) |
| T18-03 Erneutes Lesen zwischen Pruefung und Bewertung (TOCTOU) | kritisch | **behoben** (e7e9907, pruefen und zurueckgeben; Config seit 9a96a11 ebenso) |
| T18-04 `gamma2 = nan` passiert `config.validate()` | kritisch | **behoben** (Endlichkeit an Config-Eingang und Abschluss-Ausgang) |
| T18-05 Ein-Zeilen-Historie passiert `cli_report` | hoch | **behoben** (Bericht urteilt ueber die P-B1-Engine, nicht ueber einen eigenen Wachposten) |
| T18-06 Kein semantischer Ledger-Validator | hoch | **behoben** (`validate_ledger` in P-B1 verdrahtet, Gate 2.1.0) |
| T18-07 Writer folgt der beim Import gecachten umask | mittel | **behoben** (`os.open` mit 0666 ueberlaesst dem Kernel die aktuelle umask; kein Lesen, kein Fenster) |

**Bewegung 1 — Laufmanifest (T18-02).** `cli_fortschreibung` schreibt
zuletzt `laufmanifest.json`: Horizont, Neuzugangs-Stichtag, Kern-Stand,
SHA-256 der Config und jeder Ausgabe. Der Abschluss verlangt es; Gate
P-B1 bindet es mit `--manifest`. Details: ADR-011 Abschnitt 7.

**Bewegung 2 — pruefen und zurueckgeben (T18-03).** Die Engine liest
jede Datei genau einmal, hasht und parst dieselben Bytes und gibt
Tabellen UND Config an den Konsumenten heraus. Abschluss und Bericht
lesen nichts mehr selbst.

**Bewegung 3 — zeilenweise Bindung und Endlichkeit am Eingang
(T18-01, -04, -06).** `models.bestand.validate_ledger` prueft, was
eine Buchung IST (Vokabular, Betragsart zum GeVo, Endlichkeit,
Generation des Stammsatzes, Vertragsjahr = vollendete Jahre am
Datum, Journalzeile zum Zustandswechsel) und bindet jede
ERH-Buchung an genau eine Scheibe ueber Police, Datum, Betrag und
Erhoehungsjahr. Endlichkeit dort, wo Zahlen eintreten:
`config.validate()` lehnt nan/inf in jeder Rechnungsgrundlage ab
(auch in Tarifzellen und Annahmen), `validate_abschluss` haelt den
gerechneten Stand VOR dem Festschreiben an. Eine bewusste Grenze der
Ledger/Historie-Bindung: Sie gilt nur in Richtung Ledger -> Historie.
Ein uebernommener Vertrag traegt die Beitragsfreistellung der Quelle
in der Historie (ohne Bewegung des aufnehmenden Unternehmens) und die
Umbuchung zum Zugangsstichtag im Ledger — die Gegenrichtung waere
falsch, und der Test haelt genau diesen Fall als gueltig fest.

**Die zwei kleinen.** T18-05: `cli_report` ruft dieselbe Engine wie
Gate und Abschluss (ohne Config — Plausibilitaetsbaender sind ein
Gate-Kriterium, kein Berichtsverbot). T18-07: Der Writer liest die
umask nicht mehr (das ginge nur durch Setzen, nebenlaeufig unsicher),
sondern legt die temporaere Datei mit `os.open(..., 0o666)` an und
ueberlaesst dem Kernel die Anwendung; gilt fuer Parquet und Manifest.

**Nachweise.** `tests/test_bestand_manifest.py` (T18-02),
`tests/test_bestand_abschluss.py` (T18-03),
`tests/test_bestand_review_t18.py` (T18-01, -04, -05, -06, -07);
jeder stellt den Nachweis des Reviews nach. Mutationsproben je
Wache: neun Wachen einzeln entfernt (Manifestpflicht, Horizont- und
Hashpruefung, Scheibenbindung, Ledger-Verdrahtung, Config- und
Abschluss-Endlichkeit, Berichts-Befunde, Writer), jede vom Test
gefangen. Zwei Altlasten in bestehenden Tests fielen dabei auf und
wurden korrigiert: Zwei Berichtstests kombinierten den Basisbestand
(Stamm sagt POL) mit einem Journal (sagt STO) — genau der Widerspruch,
den T18-05 sichtbar macht; sie rendern jetzt den gefuehrten Stamm.

## Nachzug: die Runde T20 (DORA ToDo 20, 2026-09-05) in diesem PR

Externes Review auf Stand 6e239dc (nach T19- und T18-Nacharbeit); acht
Befunde, vier hoch, vier mittel. Maintainer-Entscheid: alle acht in
PR #11 schliessen, bevor gemergt wird. Die Runde bestaetigte, dass die
konkret demonstrierten Mutationen aus T18 und T19 gefangen sind — und
zeigte an drei tieferen Gegenbeispielen, dass die KLASSE noch nicht
geschlossen war. Der Reviewer hat das selbst so eingeordnet: T20-01 und
T20-04 sind Stellen, an denen die drei Bewegungen der T18-Antwort noch
nicht durchgezogen waren. Das trifft.

| Befund | Schwere | Status |
|---|---|---|
| T20-01 P-B1 bindet andere Bytes, als es prueft (TOCTOU zwischen Gate-Hash und Engine) | hoch | **behoben** — Gate und A-M4-Neupruefung uebernehmen die Hashes der Engine (ein Lesevorgang), `hash_key` statt `hash_files` |
| T20-02 Vorzeigeseite behauptet verifizierte Signaturwirkung | hoch | **behoben** — Pruefstand je Snapshot ("strukturell geprueft, Signatur hier nicht verifiziert"); "gezeichnet" nur bei `signatur_verifiziert` |
| T20-03 Unvollstaendige Artefakte enden gruen, Seite verbirgt Luecken, Sollmenge nicht scopebezogen | hoch | **behoben** — Lueckenabschnitt auf der Seite, Exit 3 fuer Bericht, Seite und Kette; Sollmengen aus `fall.scope` wie `gate_entscheid` |
| T20-04 Stornobetraege nicht an Police und Kern gebunden | hoch | **behoben** — `bestand.ledger_bindung`: STO/PEX/TOD/ABL/ZUG je Police gegen dieselbe Kern-Herleitung wie die Engine; BU gegen die Jahresrente; in P-B1 (mit `--config`) und Abschluss verdrahtet |
| T20-05 `sdlog = nan` passiert Config und Produzent | mittel | **behoben** — Endlichkeit aller Verteilungsparameter vor jeder Bandpruefung |
| T20-06 A-M4-Pflichtvertrag dokumentarisch widerspruechlich | mittel | **behoben** — AT-Dokument (Abschnitt als ueberholt markiert), ADR-012, `gate_entscheid`-Modulvertrag, README, ONBOARDING sagen den Scope-Vertrag |
| T20-07 Klarnamenwache uebersieht Flexionsformen | mittel | **behoben** — fuenf Genitive durch Rollen ersetzt; die Wache prueft Grundformen (Flexionsendungen abgestreift), Mutationsfaenger mit Genitiv |
| T20-08 Dokumentierter Installationsweg nicht reproduzierbar | mittel | **behoben** — ein Installationsweg (Pin-Dateien, wie CI) in AGENTS/README/ONBOARDING; neun fehlende transitive Pins ergaenzt; `tests/test_abhaengigkeiten.py` haelt den Schluss |

**Was die Runde ueber die Klasse lehrt.** T18-03 hatte den zweiten
Lesevorgang im Abschluss beseitigt; das Gate selbst hashte weiter
separat vor der Engine. T18-01/-06 banden ERH zeilenweise an die
Scheiben; STO, PEX, TOD und ABL blieben auf Jahressummen. T18-04 prufte
die direkten Zahlfelder; die Verteilungsparameter nicht. Jede Reparatur
hier heisst deshalb: Die Engine ist die einzige Lesestelle und gibt
ihre Hashes heraus (T20-01); jede hergeleitete Buchungsart ist gegen
den Kern gebunden (T20-04); Endlichkeit gilt fuer jeden Zahlparameter
der Config (T20-05). Der Vertrag steht jetzt in drei Tests, die je
Klasse eine Wache entfernen und rot werden.

**Bewusste Grenzen der Betragsbindung.** `MIG` (Residuum der
Uebernahme) und `RED` (von der Engine nicht erzeugt) werden nicht
hergeleitet; `ERH` bleibt ueber die Scheiben gebunden. Generationen in
Tarifzellen brauchen die Merkmalstabelle (neue optionale Rolle
`merkmale` in Engine, Gate und Abschluss); fehlt sie, ist das ein
benannter Fehler, keine stille Naeherung.

**Nachweise.** `tests/test_bestand_review_t20.py` (T20-01, -04, -05 mit
den Repros des Reviews), `tests/test_falldaten_verifikation.py` (T20-02,
-03: leerer Fall durch beide Renderer, Tarif-Scope-Gegenprobe,
Signaturwortlaut), `tests/test_klarnamen.py` (T20-07),
`tests/test_abhaengigkeiten.py` (T20-08). Mutationsproben: elf Wachen
einzeln entfernt (Gate- und A-M4-Hashing vor der Engine, Herleitung
nicht verdrahtet, Verteilungs-Endlichkeit, Flexion, Signaturwortlaut,
Lueckenabschnitt, drei Exit-Codes, Sollmenge), jede gefangen.
