# Mitwirken

Dieses Repository ist ein offener Arbeitsraum für ein **agentisches
System zur Bestandsmigration Leben und zur Entwicklung des Rechenkerns**
(siehe `README.md`) — kein Produkt. Beiträge, Rückfragen und
Diskussionsanstöße sind ausdrücklich willkommen.

## Wie ihr beitragen könnt

- **Issues** für Bugs, methodische Fragen, Stolpersteine oder „das hat mich überrascht"-Beobachtungen.
- **Pull Requests aus Forks** sind willkommen. Für größere Änderungen bitte vorher ein Issue eröffnen, damit wir den Scope gemeinsam abstimmen.
- **Projektmitglieder** pushen direkt auf Topic-Branches und mergen nach Absprache mit der Projektleitung.

## Pull Requests schneiden

Das Repository trägt fünf Gegenstände (ADR-027): die Laufzeit der PLV,
das Migrationssystem, die Fall-Definitionen, die Routinen und die
Webseite.

- Mehrere Gegenstände gehen nur dann in einen Pull Request, wenn sie eine
  Transaktion sind — wenn `main` mit nur einem Teil davon unerklärt wäre.
- Die Webseite geht nie im selben Pull Request wie die anderen vier: Sie
  zieht `main` nach und wird eigenständig veröffentlicht.
- Infrastruktur einzelner Installationen gehört nicht ins Repository.
- Kern und Tarifwerk sind abgenommene Gegenstände (`src/rechner_pipeline/kern`,
  die Referenzwerte, die Grundsatzdokumentation, `docs/tarifplaene`, die
  Bestands-Configs). Eine Änderung daran ist eine Änderung des Zielsystems
  und nie Beifang eines anderen Pull Requests; `tests/test_pakete.py` wird
  sonst rot und nennt den Ausweg.

## Stilrichtlinien

- Code in Englisch, Dokumentation primär in Deutsch; reiner Text ohne
  Emojis/Icons.
- Alles muss reproduzierbar end-to-end laufen (volle Test-Suite vor
  jedem Commit, parallel: `python -m pytest -n auto --dist loadfile`,
  ADR-019).
- Agenten-Anweisungen (`AGENTS.md`, die Skills unter `.claude/skills/`
  und `.agents/skills/`) sind versionierte Artefakte, keine
  Wegwerf-Prompts; die Spiegel-Parität ist test-erzwungen.
- Beispielartefakte (Excel-Rechner, Bestandsabzüge, Bestands-Configs
  der fiktiven Pfefferminzia LV) müssen **synthetisch oder öffentlich
  verfügbar** sein — keine echten Kunden- oder Bestandsdaten. Das gilt
  auch für die Rechnungsgrundlagen: die Tafelvektoren in
  `src/rechner_pipeline/kern/tafeln.xml` sind veröffentlichte
  DAV-Tafeln bzw. synthetische Vektoren. Die Herkunft steht bei den
  meisten Vektoren in der Datei (Provenienz-Kommentar oder
  `quelle`-Attribut); vier Vektoren aus dem Anfangsbestand des Kerns
  (DAV1994_T_F/M, DAV2008_T_F/M) tragen sie noch nicht — beim Ergänzen
  gilt: neue Vektoren nur mit Herkunftsangabe. Keine Klarnamen von
  Personen in eingecheckten Dateien oder Commit-Botschaften.

## Lokale Konfiguration

- Die zentrale Python-Konfiguration liegt in `pyproject.toml`. Die
  **direkten** Abhängigkeiten sind dort exakt gepinnt (plus
  `[dev]`-Extra für die Test-Toolchain); alles Transitive löst pip auf.
- `requirements.txt` / `requirements-dev.txt` pinnen zusätzlich die
  transitive Hülle. Das ist der reproduzierbare Weg und der, den die CI
  fährt:
  `python -m pip install -r requirements-dev.txt`, dann
  `python -m pip install -e . --no-deps`, dann die Suite.
- Nur die direkten Abhängigkeiten zu installieren
  (`python -m pip install -e ".[dev]"`) ist kein dokumentierter Weg: Die
  Suite läuft mit `filterwarnings = ["error"]` — eine neue Warnung in
  einer frisch aufgelösten Fremdbibliothek färbt sie rot, ohne dass sich
  hier etwas geändert hat. In dem Fall über die Pin-Dateien installieren
  und den Unterschied als Befund melden, nicht die Warnungs-Strenge
  senken.
- Das Paket ist SDK-frei: kein LLM-Key, keine `.env`, keine
  Provider-Konfiguration. Agenten arbeiten über ihre CLIs auf dem Repo
  (siehe `AGENTS.md`).

## Kontakt

Issues sind der bevorzugte Weg.
