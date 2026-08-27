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
nicht monoton — sie ist eine Warteschlange, kein Archiv.

## Aufbau eines Vorhabens

Vier Abschnitte, mehr braucht es nicht:

1. **Problem** — was heute nicht stimmt, mit Beleg (Messung, Zitat,
   Fundstelle). Kein Vorschlag, nur der Befund.
2. **Warum es zaehlt** — welche Folge hat es, wenn es so bleibt.
3. **Loesungsskizze** — die Richtung, nicht der fertige Entwurf; dazu
   ausdruecklich, was die Loesung NICHT leistet.
4. **Einordnung** — Aufwand grob, Abhaengigkeiten, wer entscheidet, und
   woran man merkt, dass es faellig wird.

## Aktuelle Vorhaben

| Vorhaben | Stand |
|---|---|
| [Aktuarieller Test AT-1/AT-2/AT-3](aktuarieller-test-at1-at2-at3.md) | Konzept, wartet auf Durchsprache |
| [Korrekturschicht umsetzen](korrekturschicht-umsetzung.md) | Umsetzungsvorschlag, wartet auf Durchsprache |
| [Rollentrennung der Agenten](agenten-rollentrennung.md) | Skizze, wartet auf Entscheidung |
| [Offene Punkte](offene-punkte.md) | laufend |
