# Mitwirken

Dieses Repository ist ein offener Arbeitsraum für ein System, das
Lebensversicherungsbestände mit Agenten und deterministischem Code in ein
anderes System übernimmt. Es ist ein Prototyp, kein Produkt (siehe
`README.md`). Beiträge, Rückfragen und Anstöße zur Diskussion sind
willkommen.

## Beitragen

- **Issues** für Fehler, methodische Fragen, Stolpersteine oder
  Beobachtungen der Art „das hat mich überrascht“.
- **Pull Requests aus Forks** sind willkommen. Vor größeren Änderungen
  bitte ein Issue eröffnen, um den Umfang vorher abzustimmen.
- Der Maintainer pusht auf Themenzweige und führt sie über `main`
  zusammen.

## Pull Requests schneiden

Das Repository trägt fünf Gegenstände (ADR-027): die Laufzeit der PLV,
das Migrationssystem, die Fall-Definitionen, die Routinen und die
Webseite.

- Mehrere Gegenstände gehen nur dann in einen Pull Request, wenn sie
  zusammengehören: wenn `main` mit nur einem Teil davon nicht stimmig wäre.
- Die Webseite geht nie im selben Pull Request wie die anderen vier: Sie
  zieht `main` nach und wird eigenständig veröffentlicht.
- Infrastruktur einzelner Installationen gehört nicht ins Repository.
- Kern und Tarifwerk sind abgenommene Gegenstände (`src/rechner_pipeline/kern`,
  die Referenzwerte, die Grundsatzdokumentation, `docs/tarifplaene`, die
  Bestands-Configs). Eine Änderung daran ist eine Änderung des Zielsystems
  und nie Beifang eines anderen Pull Requests; `tests/test_pakete.py` wird
  sonst rot und nennt den Ausweg.

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

Issues sind der bevorzugte Weg.
