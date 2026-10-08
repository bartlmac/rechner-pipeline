# dev-docs — Planung des Entwicklerteams

Backlog und Vorhaben fuer Repo, Tooling und Arbeitsweise: groessere
Umbauten mit einer Loesungsskizze, offene Punkte aus Reviews,
Nachzuege, die auf eine Entscheidung warten. Der Zweck ist, dass ein
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
Arbeitsbereich des Maintainers. Was hier steht, ist fuer das Team.

## Ablage

| Was | Wohin |
|---|---|
| Ein groesseres Vorhaben mit Problembeschreibung und Loesungsskizze | eigene Datei, sprechender Name (`agenten-rollentrennung.md`) |
| Kleinere Punkte, Nachzuege, Reviewfunde ohne eigenen Umbau | [offene-punkte.md](offene-punkte.md) |
| Eine getroffene Entscheidung | ADR unter `docs/architektur/` — von hier wird dorthin verwiesen, der Eintrag hier wird geschlossen |

Ein Vorhaben, das umgesetzt ist, verschwindet hier und lebt in seinem
ADR, seinem Code und seinen Tests weiter. Diese Ablage waechst also
nicht monoton — sie ist eine Warteschlange, kein Archiv. Stehen bleibt
ein umgesetztes Vorhaben nur, wenn andere Dokumente darauf verweisen
oder es ausdruecklich als Herleitung gefuehrt wird; die Tabelle unten
sagt das je Dokument.

## Aufbau eines Vorhabens

Vier Abschnitte, mehr braucht es nicht:

1. **Problem** — was heute nicht stimmt, mit Beleg (Messung, Zitat,
   Fundstelle). Kein Vorschlag, nur der Befund.
2. **Warum es zaehlt** — welche Folge hat es, wenn es so bleibt.
3. **Loesungsskizze** — die Richtung, nicht der fertige Entwurf; dazu
   ausdruecklich, was die Loesung NICHT leistet.
4. **Einordnung** — Aufwand grob, Abhaengigkeiten, wer entscheidet, und
   woran man merkt, dass es faellig wird.

## Was hier liegt

| Dokument | Was es ist | Stand laut Dokument |
|---|---|---|
| [Offene Punkte](offene-punkte.md) | kleinere Vorhaben, Nachzuege, Reviewfunde | laufend |
| [Aktuarieller Test AT-1/AT-2/AT-3](aktuarieller-test-at1-at2-at3.md) | Vorhaben | gebaut am 2026-08-27; offen sind die Stichprobenprofile |
| [Korrekturschicht umsetzen](korrekturschicht-umsetzung.md) | Vorhaben | Stufe N7.1 gebaut am 2026-08-27; was fehlt, steht dort in Abschnitt 7 |
| [Zahlungspfade migrierter Vertraege](zahlungspfade-migrierter-vertraege.md) | Vorhaben | der akute Fall ist seit dem 2026-08-28 geloest (Zweiteilung des herabgesetzten Vertrags); der allgemeine Pfad ist offen |
| [Freischaltung des uebernommenen Bestands](freischaltung-uebernommener-bestand.md) | Fachkonzept mit Schrittliste | Stand je Schritt in Abschnitt 6; Tarifplan, Skills und ADR-017 verweisen darauf |
| [Rollentrennung der Agenten](agenten-rollentrennung.md) | Herleitung | entschieden und umgesetzt als ADR-017 und ADR-018 |
| [Rueckbau des zweiten Baldrian-Laufs](rueckbau-fall2.md) | Herleitung | umgesetzt; der dritte Fall hat darauf aufgesetzt (2026-10-02) |
| [Annahmen vom 2026-09-20](annahmen-2026-09-20.md), [Entscheidungsvorlage Laufmanifest](entscheidungsvorlage-am4-laufmanifest.md) | Belege zur Neuzeichnung des zweiten Laufs | vom Abschlussbericht des Laufs zitiert (`docs/faelle/baldrian-lauf2.md`) |
| [Regie](regie.md) | Stub | Konzept benannt, Dokumentation ausstehend |

Befundlisten, Reviews und Merge-Plaene abgeschlossener Runden liegen nicht
mehr hier; sie stehen in der Geschichte des Repositorys.
