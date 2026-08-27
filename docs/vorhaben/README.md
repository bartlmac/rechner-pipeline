# Vorhaben — was ansteht und warum

Hier steht Arbeit, die **erkannt und eingeplant, aber nicht umgesetzt**
ist: groessere Umbauten mit einer Loesungsskizze, offene Punkte aus
Reviews, Nachzuege, die auf eine Entscheidung warten. Der Zweck ist,
dass ein erkanntes Problem nicht in einer Besprechung oder einem
Commit-Text verschwindet.

Das ist **keine** Systemdokumentation: Was das System ist und rechnet,
steht in `docs/architektur/`, `docs/mathematik/`, `docs/tarifplaene/`
und `docs/migrationskonzept/`. Und es ist nicht `docs-local/` — das ist
der private Arbeitsbereich des Maintainers. Was hier steht, ist fuer
das Team.

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
| [Rollentrennung der Agenten](agenten-rollentrennung.md) | Skizze, wartet auf Entscheidung |
| [Offene Punkte](offene-punkte.md) | laufend |
