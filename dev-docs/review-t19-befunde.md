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

- **T18-01 bis T18-06** sind auf diesem Branch unveraendert
  reproduzierbar — erwartbar und beabsichtigt: Sie liegen als eigener
  Korrektur-PR hinter dem Vorfuehrfall (Merge-Plan Schritt 6b), weil
  das Laufmanifest den Ausgabevertrag der Fortschreibung aendert und
  das mitten im Fall die gezeichneten Belege entwertet haette.
  T18-07 ist teilweise ueberholt (Abschluesse jetzt 0444; der
  generische Writer nutzt weiter die gecachte umask).
- **Nachweisgrenze des Reviews**, vom Reviewer selbst gezogen:
  `docs-local/`, `simulation/` und `faelle/` lagen nicht vor. Die
  fuenf finalen Zeichnungen und die Vollbestandswerte konnten daher
  nicht kryptografisch gegen den realen Lauf geprueft werden; die
  versionierten E2E-Fixturen decken einen repraesentativen Schnitt und
  die Rechenkette ab, nicht die konkreten Snapshots.
