# Mitwirken

Dieses Repository ist ein **methodischer Referenzrahmen** für KI-gestützte Rechenkernentwicklung — kein Produkt, sondern ein offener Arbeitsraum, in dem wir Vorgehen, Leitplanken und Werkzeuge gemeinsam erproben. Beiträge, Rückfragen und Diskussionsanstöße sind ausdrücklich willkommen.

## Wie ihr beitragen könnt

- **Issues** für Bugs, methodische Fragen, Stolpersteine oder „das hat mich überrascht"-Beobachtungen.
- **Pull Requests aus Forks** sind willkommen. Für größere Änderungen bitte vorher ein Issue eröffnen, damit wir den Scope gemeinsam abstimmen.
- **Projektmitglieder** pushen direkt auf Topic-Branches und mergen nach Absprache mit der Projektleitung.

## Stilrichtlinien

- Code in Englisch, Dokumentation primär in Deutsch.
- Pipeline muss reproduzierbar end-to-end laufen.
- LLM-Prompts sind versionierte Artefakte, keine Wegwerf-Strings.
- Demo- und Beispielartefakte (Excel-Rechner, Tafeln) müssen synthetisch sein — keine echten Kunden- oder Bestandsdaten.

## Lokale Konfiguration

- Die zentrale Python-Konfiguration liegt in `pyproject.toml`.
  `requirements.txt` verweist nur auf `pip install -e ".[all]"` für den
  vollständigen Demo-Lauf.
- Für reine CLI-/Import- und Hilfsfunktionstests genügt `pip install -e .`.
  Für klassische Pipeline-Läufe `pip install -e ".[llm,export]"`, für die
  agentische Variante zusätzlich `agentic`, und für Tests `dev`.
- Secrets werden nicht eingecheckt. Für lokale Läufe kann `.env.example` nach
  `.env` kopiert und dort `OPENAI_API_KEY` gesetzt werden.
- Die Pipeline lädt `.env` aus dem Repository-Root erst beim ersten LLM-Schritt.
  Echte Umgebungsvariablen behalten Vorrang vor Einträgen in `.env`.
- CLI-Hilfe, Importtests und deterministische Hilfsfunktionen müssen ohne
  `OPENAI_API_KEY` und ohne `.env` lauffähig bleiben.

## Kontakt

Issues sind der bevorzugte Weg. Für die fachliche Einbettung im DAV-Kontext: Projekt der DAV-AG Bestandsmigration.
