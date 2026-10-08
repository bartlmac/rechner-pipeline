# Rechner-Pipeline

> **Status:** öffentlicher Prototyp und Arbeitsstand. Er läuft von der
> Lieferung bis zum übernommenen Bestand durch, ist aber noch nicht
> produktiv einsetzbar. Was der Stand kann und was nicht, steht im
> [CHANGELOG](CHANGELOG.md).

Die Rechner-Pipeline übernimmt den Bestand eines Lebensversicherers in ein
anderes System: Tarife und Verträge, jeden Vertrag mit dem Zustand, den
seine Geschichte hinterlassen hat. KI-Agenten lesen die
gelieferten Unterlagen und machen Vorschläge. Deterministischer Code prüft
und rechnet. Wo Quellen sich widersprechen oder das Zielsystem erweitert
werden muss, entscheidet ein Mensch.

Gezeigt wird das an zwei erfundenen Unternehmen: Die Pfefferminzia
Lebensversicherung (PLV) übernimmt den Bestand der Baldrian Leben. Im
Repository liegen keine echten Kunden- oder Vertragsdaten.

**Für Fachleute und Interessierte** erklärt die
[Vorzeigeseite](https://bartlmac.github.io/rechner-pipeline/), wie eine
Migration abläuft, was der Rechenkern rechnet und wie die PLV ihre Tarife
dokumentiert. **Dieses Repository ist für Entwickler:** Code, Tests und die
Routinen, mit denen sich jeder Stand nachbauen lässt.

## Schnellstart

Voraussetzungen: Linux mit Python 3.11 und git (die CI und das Image
laufen unter 3.11; neuere Versionen sind nicht erprobt). Unter Windows
und macOS läuft die Suite im Entwicklungs-Container, siehe
[ONBOARDING](ONBOARDING.md); das Nachfahren eines Falls ist bisher nur
unter Linux erprobt. Ein Schlüssel für ein Sprachmodell ist nicht nötig.

```bash
git clone https://github.com/bartlmac/rechner-pipeline.git
cd rechner-pipeline
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps
.venv/bin/python -m pytest -n auto --dist loadfile
```

Die Suite läuft parallel; jede Testdatei läuft ganz in einem Prozess
([ADR-019](docs/architektur/adr-019-parallele-testsuite.md)). Mit zwölf
Prozessen dauert sie etwa sieben Minuten; bei knappem Arbeitsspeicher
weniger Prozesse wählen, etwa `-n 4`. Ist sie grün, stimmt die
Installation.

**Einen Fall nachfahren.** Ein Aufruf baut eine eigene Umgebung auf (eine
[Welt](docs/architektur/glossar.md#welt)) und spielt die abgeschlossene
Übernahme der Baldrian ohne Agenten nach (Fall 3, siehe
[migrationen/baldrian/](migrationen/baldrian/README.md)). Das dauert etwa 45 Minuten:

```bash
werkzeuge/welt/laufzeit_aufstellen.sh ~/plv-welt pakete/baldrian-klv-tg2015-fall3
```

Danach liegen die Monatsabschlüsse und Berichte der PLV mit dem übernommenen
Bestand unter `~/plv-welt/daten/`. Der Fall selbst liegt im Klon unter
`faelle/baldrian-klv-tg2015-fall3/`, sein Abnahmebericht unter
`abgeleitet/berichte/migrationsabnahme.html`. Beim Nachfahren zeichnet das
Rezept alle Gates selbst, mit Schlüsseln der Klasse `simulation`, die der
Aufruf neu erzeugt: Jede Zeichnung weist sich als simuliert aus, und das
Urteil des festgehaltenen Falls wird übernommen, nicht neu gefällt. Die
Schlüssel legt der Aufruf außerhalb des Klons ab, unter
`~/.plv-schluessel/<name der Welt>`.

Ein zweites Nachfahren in einer neuen Welt hält an, solange der Fall im Klon
liegt. Dann einen frischen Klon nehmen oder den Fall vorher nach
`faelle/archiv/` verschieben; gelöscht wird ein Fall nie. Wie man an einem
Haltepunkt anhält und selbst entscheidet, steht in
[werkzeuge/welt/README.md](werkzeuge/welt/README.md).

**Das Container-Image.** Ändert ein Push auf `main` den Code,
`requirements.txt` oder `plv/betrieb/`, baut die CI das Image
`ghcr.io/bartlmac/rechner-pipeline-plv`. Es dient dem Betrieb einer
Laufzeit, nicht der Entwicklung: Es enthält nur das Paket und führt den
Tageslauf einer bestehenden Ablage aus, im Betrieb jede Nacht über einen
Timer. Die Tests, die Skripte unter `werkzeuge/welt/` und die Pakete der Fälle
sind nicht darin, dafür braucht es den Klon. Wie eine Laufzeit mit dem
Image betrieben wird, steht in [plv/betrieb/README.md](plv/betrieb/README.md).

## Wie das System arbeitet

Eine Übernahme ist ein **Fall**. Er läuft in fünf Abschnitten:

1. **Lieferung registrieren.** Die abgebende Gesellschaft liefert
   Tarifrechner, Tarifbeschreibung, Bedingungen und Bestandsabzüge. Jede
   Datei kommt mit ihrer Prüfsumme in den Fall und ändert sich danach nicht
   mehr.
2. **Quellen lesen.** Agenten ziehen aus jeder Quelle die Aussagen heraus,
   Code führt sie zusammen. Widersprechen sich zwei Quellen, entscheidet ein
   Mensch.
3. **Zielsystem anpassen.** Kennt der Rechenkern die Leistungen des Tarifs
   schon, wird er nur parametriert. Sonst wird er erweitert, und die
   Erweiterung wird abgenommen.
4. **Bestand übernehmen und prüfen.** Die Verträge werden übertragen und
   gegen die gelieferten Erwartungswerte geprüft. Am Ende steht die
   Migrationsabnahme.
5. **Zugang in den Betrieb.** Der übernommene Bestand kommt in die Ablage,
   in der die PLV Tag für Tag geführt wird.

Jede menschliche Entscheidung ist ein **Gate** mit einer Kennung,
zum Beispiel `A-M4` für die Migrationsabnahme. Sie wird mit einem Schlüssel
gezeichnet und als unveränderlicher Beleg im Fall abgelegt. Agenten legen
nur vor; eine Abnahme zeichnet nur ein Mensch, in der Vorführung eine
simulierte Rolle unter Mandat. Den ganzen Ablauf mit allen Gates
beschreibt [docs/architektur/ablauf-eines-falls.md](docs/architektur/ablauf-eines-falls.md),
die Begriffe erklärt das [Glossar](docs/architektur/glossar.md).

## Was dieses Repository ist

Das Repository ist nach Ebenen geordnet
([ADR-028](docs/architektur/adr-028-ordnung-nach-ebenen.md)): das System,
die beiden erfundenen Unternehmen, an denen es arbeitet, die Simulation,
die Bestände, Lieferungen und Welten erzeugt, und was beim Laufen entsteht.
Der Code von System, PLV und den Erzeugern der Simulation liegt in einem
Python-Paket unter `src/`; welche Ebene ein Modul trägt, misst die
Schichtenkarte ([ADR-017](docs/architektur/adr-017-vier-ebenen.md)).
Skripte und das Quellsystem liegen bei ihrer Ebene unter `system/` und
`werkzeuge/`.

| Ebene | Was | Wo |
|---|---|---|
| **System** | das Migrationssystem: Quellen vorverdichten, Aussagen mit Herkunft führen, Tarife parametrieren, prüfen und Abnahmen vorbereiten; die gemeinsamen Datenverträge; die Rollen der Agenten; Werkzeuge für den Live-Lauf eines Falls | `src/rechner_pipeline/quellen`, `src/rechner_pipeline/ontologie`, `src/rechner_pipeline/spez`, `src/rechner_pipeline/qa`, `src/rechner_pipeline/gates`, `src/rechner_pipeline/models`, `src/rechner_pipeline/fall.py`, `.claude/`, `.agents/`, [`system/`](system/README.md) |
| **Objekt PLV** | die übernehmende Gesellschaft: Rechenkern, Bestandsführung und Tagesbetrieb, ihre Parametrierung und Fachdokumente, das Image ihrer Laufzeit und ihr Auftritt | `src/rechner_pipeline/kern`, `src/rechner_pipeline/bestand`, `src/rechner_pipeline/betrieb`, `configs/`, `docs/mathematik/`, `docs/tarifplaene/`, [`plv/`](plv/README.md) |
| **Objekt Baldrian bzw. Migration** | die abgebende Gesellschaft: ihre Lieferungen, die Falldatei der Vorführung und die Berichte zu den Fällen | [`migrationen/`](migrationen/README.md) |
| **Simulation** | ihr Modell (Verteilungen, das Erzeugen von Geschäftsvorfällen und Neugeschäft, in einzelnen Modulen von `bestand` und `betrieb`) und ihr Betrieb: das Quellsystem der Baldrian, eine Welt aufstellen, einen Fall nachfahren, die Seite bauen | [`werkzeuge/`](werkzeuge/README.md) |
| **Laufzeit-Artefakte** | was beim Laufen entsteht; im Repository liegt davon nur der dritte Fall, eingefroren, damit er nachfahrbar ist | [`pakete/`](pakete/README.md) |

Quer zu den Ebenen liegen `tests/`, `docs/` (Entwicklerdoku), `dev-docs/`
(geplante Vorhaben), `deploy/dev` und `.devcontainer/`
(Entwicklungsumgebung) sowie `.github/` (CI).

Grundsatzdokumentation, Tarifpläne und Configs gehören zur PLV, liegen aber
noch an ihrem bisherigen Ort: Ihre Abnahme bindet den Pfad mit. Sie ziehen
nach `plv/` um, sobald die Abnahme einen Ortswechsel verfolgen kann.

Nicht im Repository liegen die laufenden Instanzen mit ihren Schlüsseln und
Daten, die Arbeitsbereiche der Fälle und die Läufe (lokal, von Git
ausgenommen), das Hosting der
Seite und die Einrichtung einzelner Rechner.

## Wo was steht

| Frage | Dokument |
|---|---|
| Wie richte ich mich ein, und welche Regeln gelten? | [ONBOARDING.md](ONBOARDING.md), [CONTRIBUTING.md](CONTRIBUTING.md) |
| Wo fange ich in der Dokumentation an? | [docs/](docs/README.md) |
| Was bedeuten Fall, Gate, Welt, Linie, A-Box …? | [Glossar](docs/architektur/glossar.md) |
| Wie läuft ein Fall ab, und wer zeichnet welches Gate? | [docs/architektur/ablauf-eines-falls.md](docs/architektur/ablauf-eines-falls.md) |
| Welche Architektur-Entscheidungen gelten? | [docs/architektur/](docs/architektur/README.md) |
| Was prüft ein Gate, und warum trägt es eine Version? | [docs/architektur/gate-vertrag-und-versionen.md](docs/architektur/gate-vertrag-und-versionen.md) |
| Welche Mathematik rechnet der Kern? Welche Tarife hat die PLV? | [docs/mathematik/](docs/mathematik/README.md), [docs/tarifplaene/](docs/tarifplaene/README.md) |
| Wie entstehen Bestand und Tagesbetrieb der PLV? | [docs/simulation/](docs/simulation/README.md) |
| Welche Fälle gibt es, und was lässt sich nachfahren? | [migrationen/baldrian/](migrationen/baldrian/README.md), [pakete/](pakete/README.md) |
| Wie stelle ich eine Welt auf? Wie läuft die Laufzeit im Betrieb? | [werkzeuge/welt/](werkzeuge/welt/README.md), [plv/betrieb/](plv/betrieb/README.md) |
| Wie entsteht die Vorzeigeseite? | [werkzeuge/](werkzeuge/README.md) |
| Wie führe ich einen Fall live vor? | [system/](system/README.md) |
| Wie arbeiten Agenten im Repository? | [AGENTS.md](AGENTS.md), [docs/architektur/skill-architektur.md](docs/architektur/skill-architektur.md) |
| Was ist erkannt, aber noch nicht gebaut? | [dev-docs/](dev-docs/README.md) |

## Grundsätze

- **Deterministisch:** Gleiche Eingaben ergeben byte-gleiche Ergebnisse.
  Zufall kommt aus Seeds in den Configs.
- **Kein Sprachmodell im Code:** Unter `src/` gibt es keinen Aufruf eines
  Modells. Agenten arbeiten über ihre Kommandozeilen-Werkzeuge auf dem
  Repository; Claude Code liest `.claude/`, Codex liest `AGENTS.md` und
  `.agents/`.
- **Fehler halten an:** Fehlende Daten, verletzte Regeln und Widersprüche
  ergeben einen benannten Fehler mit Ausweg, keinen stillen Ersatzwert.
- **Abgenommenes bleibt nachfahrbar:** Fall 3 hat den Stand von Rechenkern
  und Tarifwerk abgenommen und über Prüfsummen gebunden. `tests/test_pakete.py`
  hält fest, dass der Baum diesen Stand trägt. Wer Kern, Grundsatzdokumentation
  oder Tarifpläne ändert, braucht eine neue Abnahme.
- **Gepinnte Abhängigkeiten:** die direkten in `pyproject.toml`, die
  transitive Hülle in `requirements*.txt`; ein Test hält sie geschlossen.

Was daraus für die Arbeit am Code folgt, steht in
[ONBOARDING](ONBOARDING.md), Abschnitt 4.

## Mitwirken

Beiträge sind als Pull Request willkommen; vor größeren Änderungen bitte
ein Issue, siehe [CONTRIBUTING.md](CONTRIBUTING.md). Vor jedem Commit läuft
die volle Suite.

## Lizenz

MIT, siehe `LICENSE`. Die Rechnungsgrundlagen in
`src/rechner_pipeline/kern/tafeln.xml` sind veröffentlichte DAV-Tafeln oder
synthetische Vektoren. Bei den meisten steht die Herkunft in der Datei
selbst (siehe [CONTRIBUTING.md](CONTRIBUTING.md)).
