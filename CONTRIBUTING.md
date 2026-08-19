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
  der fiktiven Pfefferminzia LV) müssen synthetisch sein — keine echten
  Kunden- oder Bestandsdaten. Keine Klarnamen von Personen in
  eingecheckten Dateien oder Commit-Botschaften. Für die
  Rechnungsgrundlagen gilt das ausdrücklich **nicht**: die
  Tafelvektoren in `src/rechner_pipeline/kern/tafeln.xml` sind
  teilweise Drittmaterial (DAV-Tafeln) — siehe `NOTICE.md`, bevor dort
  etwas ergänzt wird.

## Lokale Konfiguration

- Die zentrale Python-Konfiguration liegt in `pyproject.toml`
  (Abhängigkeits-Bereiche plus `[dev]`-Extra für die Test-Toolchain).
  `requirements.txt` und `requirements-dev.txt` sind die exakt
  gepinnten Stände für reproduzierbare Installationen.
- Standard-Setup: `python -m venv .venv`, aktivieren,
  `python -m pip install -e ".[dev]"`, dann `python -m pytest`.
- Das Paket ist SDK-frei: kein LLM-Key, keine `.env`, keine
  Provider-Konfiguration. Agenten arbeiten über ihre CLIs auf dem Repo
  (siehe `AGENTS.md`).

## Kontakt

Issues sind der bevorzugte Weg. Für die fachliche Einbettung im DAV-Kontext: Projekt der DAV-AG Bestandsmigration.
