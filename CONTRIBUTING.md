# Mitwirken

Dieses Repository ist ein offener Arbeitsraum für ein System, das
Lebensversicherungsbestände mit Agenten und deterministischem Code in ein
anderes System übernimmt. Es ist ein Prototyp, kein Produkt (siehe
`README.md`). Beiträge, Rückfragen und Anstöße zur Diskussion sind
willkommen.

## Einstieg in drei Schritten

1. **Repository klonen:**
   ```
   git clone https://github.com/bartlmac/rechner-pipeline.git
   cd rechner-pipeline
   ```
2. **Umgebung einrichten** (Python 3.11, über die Pin-Dateien wie die CI):
   ```
   python3.11 -m venv .venv
   .venv/bin/python -m pip install -r requirements-dev.txt
   .venv/bin/python -m pip install -e . --no-deps
   ```
   Unter Windows mit Git Bash heißt der Interpreter `.venv/Scripts/python`.
   Den Weg über Docker und den Entwicklungs-Container beschreibt
   [ONBOARDING.md](ONBOARDING.md).
3. **Der 20-Minuten-Test:** die volle Suite, so wie die CI sie fährt.
   ```
   .venv/bin/python -m pytest -q -rs -n auto --dist loadfile
   ```
   Alles läuft, wenn die Ergebniszeile kein `failed` und kein `error` nennt
   und der Exit-Code 0 ist. Einige Tests werden übersprungen; `-rs` nennt
   je Test den Grund. Parallel dauert die Suite auf zwölf Kernen etwa sieben
   Minuten, seriell 13 bis 14. Wer mehr sehen will, fährt danach
   freiwillig den dritten Fall nach (etwa 45 Minuten, ONBOARDING.md,
   Abschnitt 3).

## Module

Die Arbeit ist in fünf Module geteilt. Jedes hat ein Label gleichen Namens.
Die Module ordnen Zuständigkeiten; freigegeben wird jeder Pull Request
vom Maintainer Office, gleich welches Modul er berührt
([.github/CODEOWNERS](.github/CODEOWNERS)).
Die Module liegen quer zu den Ebenen des Repositorys
([README.md](README.md), ADR-028).

| Modul | Verzeichnisse |
|---|---|
| Maintainer Office | `.github/`, `CONTRIBUTING.md`, `SECURITY.md`, `README.md`, `ONBOARDING.md`, `AGENTS.md`, `CHANGELOG.md`, `pyproject.toml`, `requirements*.txt`, `deploy/`, die Beschlussliste; dazu alles, was keinem anderen Modul gehört |
| Agentisches System | `.claude/`, `.agents/`, `system/`, `src/rechner_pipeline/` mit `ontologie`, `spez`, `gates`, `qa`, `models`, `zielsystem` und `fall.py` |
| Bestandsmigration | `src/rechner_pipeline/bestand`, `src/rechner_pipeline/betrieb`, `migrationen/`, `pakete/` |
| Cashflow-Modelle | `src/rechner_pipeline/kern`, `plv/mathematik`, `plv/tarifplaene`, `plv/configs` |
| Excel-Landschaften | `src/rechner_pipeline/quellen`, `werkzeuge/quellsystem` |

## Weg eines Beitrags

1. **Issue:** Jede Arbeit beginnt mit einem Issue nach Vorlage (Aufgabe
   oder Fehler), mit dem Modul. Den Meilenstein setzt das Maintainer
   Office.
2. **Zweig:** ein kurzlebiger Zweig von `main`, ein Thema je Zweig.
   Pull Requests aus Forks sind willkommen.
3. **Pull Request** nach Vorlage, mit Bezug auf das Issue und dem
   Testnachweis.
4. **Review:** Ein Mensch reviewt, in der Regel der Verantwortliche des
   Moduls. Freigeben muss das Maintainer Office (CODEOWNERS). Die
   Pflicht-Checks müssen grün sein. Einen Pull Request, den ein Agent
   gestellt hat, gibt einer der beiden anderen Code Owners frei, nicht der
   Mensch, für den der Agent arbeitet. Die Frist endet um 12:00 am ersten
   Arbeitstag, an dem um 12:00 seit der Anfrage mindestens 24 Stunden
   vergangen sind. Bis dahin gibt er frei oder sagt in einem Kommentar, was
   fehlt.
5. **Merge** durch das Maintainer Office. `main` ist geschützt; niemand
   schreibt direkt darauf. Ein Agent mergt nie, auch nicht auf Anweisung;
   er meldet, dass der Pull Request bereit zum Merge ist.

Code aus Agenten geht denselben Weg: Issue, Zweig, Pull Request, Review
durch einen Menschen. Push und Merge macht ein Mensch.

## Sign-off nach DCO

Es gibt kein CLA. Stattdessen trägt jeder Commit einen Sign-off nach dem
[Developer Certificate of Origin 1.1](https://developercertificate.org/):
```
git commit -s
```
Die Zeile `Signed-off-by: <Name> <Adresse>` bestätigt, dass man den Beitrag
einbringen darf. Signiert wird mit der Git-Identität, unter der man
beiträgt: Konto-Name und Adresse, auch die noreply-Adresse von GitHub. Ein
bürgerlicher Name wird nicht verlangt; Klarnamen gehören nicht in
Commit-Botschaften (siehe Stil).

Der Sign-off ist immer der eines Menschen. Ein Agent setzt ihn nur im Namen
des Menschen, der den Auftrag gegeben und abgestimmt hat, und mit dessen
Git-Identität; dieser Mensch steht damit für den Beitrag ein. Die Zeilen,
mit denen ein Werkzeug seinen Anteil nennt, bleiben zusätzlich stehen.

Commits vor der Einführung des Sign-offs tragen keinen; die Historie wird
nicht umgeschrieben.

## Was nicht ins Repository gehört

- Nichts aus den Häusern der Mitwirkenden: keine internen Dokumente,
  Rechner, Tarifwerke oder Daten des eigenen Arbeitgebers.
- Keine echten Bestände. Beispielartefakte sind synthetisch oder öffentlich
  verfügbar (siehe Stil).
- Keine Zugangsdaten: keine Passwörter, Tokens, API-Schlüssel oder
  Signaturschlüssel. Schlüssel liegen außerhalb des Repositorys (ADR-008).
- Keine personenbezogenen Daten und keine Klarnamen.
- Keine Infrastruktur einzelner Installationen (ADR-027).
- Sicherheitslücken nicht als öffentliches Issue, sondern auf dem Weg aus
  [SECURITY.md](SECURITY.md).

## Pull Requests schneiden

Das Repository ist nach Ebenen geordnet (ADR-028): System, Objekt PLV,
Objekt Baldrian bzw. Migration, Simulation und Laufzeit-Artefakte. Für Pull
Requests gilt, was ADR-027 festgelegt hat:

- Änderungen an mehreren Ebenen gehen nur dann in einen Pull Request, wenn
  sie zusammengehören: wenn `main` mit nur einem Teil davon nicht stimmig
  wäre.
- Die Webseite (ihre Quellen und die Werkzeuge, die sie bauen) geht nie im
  selben Pull Request wie der Rest: Sie zieht `main` nach und wird
  eigenständig veröffentlicht.
- Infrastruktur einzelner Installationen gehört nicht ins Repository.
- Kern und Tarifwerk sind abgenommene Gegenstände (`src/rechner_pipeline/kern`,
  die Referenzwerte, die Grundsatzdokumentation, `plv/tarifplaene`, die
  Bestands-Configs). Eine Änderung daran ist eine Änderung des Zielsystems
  und nie Beifang eines anderen Pull Requests; `tests/test_pakete.py` wird
  sonst rot und nennt den Ausweg.

## Wann eine Karte fertig ist

Eine Karte auf dem Projektboard ist fertig, wenn alle fünf Punkte erfüllt
sind:

1. Das Ergebnis liegt über einen gemergten Pull Request auf `main`; ein
   Konzept liegt als Dokument im Repository.
2. Die Pflicht-Checks sind grün, und keine Wache ist rot.
3. Jede neue Regel oder Grenze hat einen Test, der ohne sie rot wird.
4. Dokumentation, [Glossar](docs/architektur/glossar.md) und die
   betroffenen ADRs sind nachgezogen.
5. Das Ergebnis wurde im Sync des Teams gezeigt.

## Stil

- Bezeichner, Kommentare und Docstrings sind überwiegend deutsch und in
  ASCII geschrieben (ae, oe, ue, ss); neuer Code folgt dem. Die
  Dokumentation ist deutsch, mit Umlauten. Reiner Text, ohne Emojis und
  Icons.
- Alles muss reproduzierbar von Anfang bis Ende laufen: volle Suite vor
  jedem Commit, parallel mit `python -m pytest -n auto --dist loadfile`
  (ADR-019).
- Die Anweisungen an Agenten (`AGENTS.md`, die Skills unter
  `.claude/skills/` und `.agents/skills/`) sind versioniert und werden wie
  Code behandelt; ein Test stellt sicher, dass `.claude/` und `.agents/`
  byte-gleich sind.
- Beispielartefakte (Excel-Rechner, Bestandsabzüge, Bestands-Configs der
  erfundenen Pfefferminzia LV) müssen synthetisch oder öffentlich verfügbar
  sein, ohne echte Kunden- oder Bestandsdaten. Das gilt auch für die
  Rechnungsgrundlagen: Die Tafelvektoren in
  `src/rechner_pipeline/kern/tafeln.xml` sind veröffentlichte DAV-Tafeln
  oder synthetische Vektoren. Bei den meisten steht die Herkunft in der
  Datei (Kommentar oder Attribut `quelle`); vier Vektoren aus dem
  Anfangsbestand des Kerns (DAV1994_T_F/M, DAV2008_T_F/M) tragen sie noch
  nicht. Neue Vektoren kommen nur mit Herkunftsangabe dazu.
- Keine Klarnamen von Personen in eingecheckten Dateien oder
  Commit-Botschaften.

## Lokale Konfiguration

- Die zentrale Python-Konfiguration liegt in `pyproject.toml`. Die
  direkten Abhängigkeiten sind dort exakt gepinnt (dazu das Extra `[dev]`
  für die Testwerkzeuge); alles Transitive löst pip auf.
- `requirements.txt` und `requirements-dev.txt` pinnen zusätzlich die
  transitive Hülle. Das ist der reproduzierbare Weg und der, den die CI
  fährt: `python -m pip install -r requirements-dev.txt`, dann
  `python -m pip install -e . --no-deps`, dann die Suite.
- Nur die direkten Abhängigkeiten zu installieren
  (`python -m pip install -e ".[dev]"`) ist kein dokumentierter Weg. Die
  Suite läuft mit `filterwarnings = ["error"]`, und eine neue Warnung in
  einer frisch aufgelösten Bibliothek färbt sie rot, ohne dass sich hier
  etwas geändert hat. In dem Fall über die Pin-Dateien installieren und den
  Unterschied als Befund melden, statt die Strenge der Warnungen zu senken.
- Das Paket braucht kein Sprachmodell: keinen API-Schlüssel und keine
  Konfiguration eines Anbieters. Agenten arbeiten über ihre
  Kommandozeilen-Werkzeuge auf dem Repository (siehe `AGENTS.md`).

## Kontakt

Issues sind der bevorzugte Weg. Sicherheitslücken gehen privat, wie in
[SECURITY.md](SECURITY.md) beschrieben.
