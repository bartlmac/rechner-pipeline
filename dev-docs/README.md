# dev-docs — Planung des Entwicklerteams

Backlog und Vorhaben für Repo, Tooling und Arbeitsweise: größere
Umbauten mit einer Lösungsskizze, offene Punkte aus Reviews,
Nachzüge, die auf eine Entscheidung warten. Der Zweck ist, dass ein
erkanntes Problem nicht in einer Besprechung oder einem Commit-Text
verschwindet.

Hier arbeitet das **Entwicklerteam an diesem Repository** — Sprints,
Backlog, Refactorings, CI, Skills. Das ist eine andere Welt als das
Versicherungsunternehmen, das dieses System abbildet: Dessen
Fachdokumentation (`docs/mathematik/`, `docs/tarifplaene/`,
`docs/migrationskonzept/`) spricht die Sprache des Unternehmens und
kennt weder Repos noch Sprints. Hier gilt das nicht — hier ist
Werkzeugsprache die richtige Sprache.

Abzugrenzen ist nur `docs-local/`: der private, nicht eingecheckte
Arbeitsbereich des Maintainers. Was hier steht, ist für das Team.

## Ablage

| Was | Wohin |
|---|---|
| Ein größeres Vorhaben mit Problembeschreibung und Lösungsskizze | eigene Datei, sprechender Name (`agenten-rollentrennung.md`) |
| Kleinere Punkte, Nachzüge, Reviewfunde ohne eigenen Umbau | [offene-punkte.md](offene-punkte.md) |
| Eine getroffene Entscheidung | ADR unter `docs/architektur/` — von hier wird dorthin verwiesen, der Eintrag hier wird geschlossen |

Ein Vorhaben, das umgesetzt ist, verschwindet hier und lebt in seinem
ADR, seinem Code und seinen Tests weiter. Diese Ablage wächst also
nicht monoton — sie ist eine Warteschlange, kein Archiv. Stehen bleibt
ein umgesetztes Vorhaben nur, wenn andere Dokumente darauf verweisen
oder es ausdrücklich als Herleitung geführt wird; die Tabelle unten
sagt das je Dokument.

## Aufbau eines Vorhabens

Vier Abschnitte, mehr braucht es nicht:

1. **Problem** — was heute nicht stimmt, mit Beleg (Messung, Zitat,
   Fundstelle). Kein Vorschlag, nur der Befund.
2. **Warum es zählt** — welche Folge hat es, wenn es so bleibt.
3. **Lösungsskizze** — die Richtung, nicht der fertige Entwurf; dazu
   ausdrücklich, was die Lösung nicht leistet.
4. **Einordnung** — Aufwand grob, Abhängigkeiten, wer entscheidet, und
   woran man merkt, dass es fällig wird.

## Was hier liegt

| Dokument | Was es ist | Stand laut Dokument |
|---|---|---|
| [Offene Punkte](offene-punkte.md) | kleinere Vorhaben, Nachzüge, Reviewfunde | laufend |
| [Aktuarieller Test AT-1/AT-2/AT-3](aktuarieller-test-at1-at2-at3.md) | Vorhaben | gebaut am 2026-08-27; offen sind die Stichprobenprofile |
| [Korrekturschicht umsetzen](korrekturschicht-umsetzung.md) | Vorhaben | Stufe N7.1 gebaut am 2026-08-27; was fehlt, steht dort in Abschnitt 7 |
| [Zahlungspfade migrierter Verträge](zahlungspfade-migrierter-vertraege.md) | Vorhaben | der akute Fall ist seit dem 2026-08-28 gelöst (Zweiteilung des herabgesetzten Vertrags); der allgemeine Pfad ist offen |
| [Freischaltung des übernommenen Bestands](freischaltung-uebernommener-bestand.md) | Fachkonzept mit Schrittliste | Stand je Schritt in Abschnitt 6; Tarifplan, Skills und ADR-017 verweisen darauf |
| [Rollentrennung der Agenten](agenten-rollentrennung.md) | Herleitung | entschieden und umgesetzt als ADR-017 und ADR-018 |
| [Rückbau des zweiten Baldrian-Laufs](rueckbau-fall2.md) | Herleitung | umgesetzt; der dritte Fall hat darauf aufgesetzt (2026-10-02) |
| [Annahmen vom 2026-09-20](annahmen-2026-09-20.md), [Entscheidungsvorlage Laufmanifest](entscheidungsvorlage-am4-laufmanifest.md) | Belege zur Neuzeichnung des zweiten Laufs | vom Abschlussbericht des Laufs zitiert (`docs/faelle/baldrian-lauf2.md`) |
| [Regie](regie.md) | Platzhalter | die Spielleitung der Vorführung: Drehbücher und Auflösungen der Fälle, nicht im Repository; Dokumentation ausstehend |
| [Fallseite: Konzept](fallseite-konzept.md) | wie eine Bestandsübernahme auf dem Auftritt erzählt wird | Stand 2026-09-22 |
| [Vorzeigeseite: Seitenkonzept](vorzeige-seitenkonzept.md) | Maßstab für `vorzeige-seite/` und `werkzeuge/` | beschlossen am 2026-09-08 |
| [Vorzeigeseite: Backlog](vorzeige-backlog.md) | Vorhaben für den Auftritt; Erledigtes wird gelöscht | laufend |
| [Vorzeigeseite: statische Stellen](vorzeige-statische-stellen.md) | statische Stellen der Seite und ihre Automatisierung | erhoben 2026-09-02, gelesen nach dem Seitenkonzept |
| [Zielbild der Vorzeige](vorzeige-zielbild-artefakte.md) | was ein Lauf für die Webseite liefern muss | Stand 2026-09-22 |

Befundlisten, Reviews und Merge-Pläne abgeschlossener Runden liegen nicht
mehr hier; sie stehen in der Geschichte des Repositorys.
