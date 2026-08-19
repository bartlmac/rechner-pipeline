# Mitwirken

Dieses Repository ist ein offener Arbeitsraum für ein **agentisches
System zur Bestandsmigration Leben und zur Entwicklung des Rechenkerns**
(siehe `README.md`) — kein Produkt. Beiträge, Rückfragen und
Diskussionsanstöße sind ausdrücklich willkommen.

## Wie ihr beitragen könnt

- **Issues** für Bugs, methodische Fragen, Stolpersteine oder „das hat mich überrascht"-Beobachtungen.
- **Pull Requests aus Forks** sind willkommen. Für größere Änderungen bitte vorher ein Issue eröffnen, damit wir den Scope gemeinsam abstimmen.
- **Projektmitglieder** pushen direkt auf Topic-Branches und mergen nach Absprache mit der Projektleitung.

## Stilrichtlinien

- Code in Englisch, Dokumentation primär in Deutsch; reiner Text ohne
  Emojis/Icons.
- Alles muss reproduzierbar end-to-end laufen (volle Test-Suite vor
  jedem Commit).
- Agenten-Anweisungen (`AGENTS.md`, die Skills unter `.claude/skills/`
  und `.agents/skills/`) sind versionierte Artefakte, keine
  Wegwerf-Prompts; die Spiegel-Parität ist test-erzwungen.
- Beispielartefakte (Excel-Rechner, Bestandsabzüge, Bestands-Configs
  der fiktiven Pfefferminzia LV) müssen **synthetisch oder öffentlich
  verfügbar** sein — keine echten Kunden- oder Bestandsdaten. Das gilt
  auch für die Rechnungsgrundlagen: die Tafelvektoren in
  `src/rechner_pipeline/kern/tafeln.xml` sind veröffentlichte
  DAV-Tafeln bzw. synthetische Vektoren; die Herkunft steht je Vektor
  als Kommentar in der Datei. Keine Klarnamen von Personen in
  eingecheckten Dateien oder Commit-Botschaften.

## Lokale Konfiguration

- Die zentrale Python-Konfiguration liegt in `pyproject.toml`. Die
  **direkten** Abhängigkeiten sind dort exakt gepinnt (plus
  `[dev]`-Extra für die Test-Toolchain); alles Transitive löst pip auf.
- `requirements.txt` / `requirements-dev.txt` pinnen zusätzlich die
  transitive Hülle. Das ist der reproduzierbare Weg und der, den die CI
  fährt:
  `python -m pip install -r requirements-dev.txt`, dann
  `python -m pip install -e . --no-deps`, dann `python -m pytest`.
- Bequemer Weg für einen schnellen Blick: `python -m venv .venv`,
  aktivieren, `python -m pip install -e ".[dev]"`, dann
  `python -m pytest`. Achtung: Die Suite läuft mit
  `filterwarnings = ["error"]` — eine neue Warnung in einer frisch
  aufgelösten Fremdbibliothek färbt sie rot, ohne dass sich hier etwas
  geändert hat. In dem Fall über die Pin-Dateien installieren und den
  Unterschied als Befund melden, nicht die Warnungs-Strenge senken.
- Das Paket ist SDK-frei: kein LLM-Key, keine `.env`, keine
  Provider-Konfiguration. Agenten arbeiten über ihre CLIs auf dem Repo
  (siehe `AGENTS.md`).

## Kontakt

Issues sind der bevorzugte Weg. Für die fachliche Einbettung im DAV-Kontext: Projekt der DAV-AG Bestandsmigration.
