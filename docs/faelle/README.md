# Die Migrationsfälle

Die Pfefferminzia hat bisher einen Bestand übernommen: KLV, Tarifgeneration
TG2015, der Baldrian Leben, zum Stichtag 01.01.2026. Diese eine Übernahme
wurde dreimal geführt. Jeder Durchgang ersetzt den vorigen; beide
Unternehmen sind erfunden, und ihre Geschichte wird mit dem System neu
geschrieben.

| Durchgang | Lieferung | Was er ist | Im Repository | Nachfahren |
|---|---|---|---|---|
| **Lauf 1** (Fall `baldrian-uebernahme`) | `lieferungen/baldrian/` | der erste durchgängige Fall | die Lieferung | von Hand und mit Agenten, nach `ONBOARDING.md`, Abschnitt 3. Ob er auf dem heutigen Stand durchläuft, ist nicht gemessen. |
| **Lauf 2** | `lieferungen/baldrian-2/` | derselbe Bestand auf einer neuen, umfangreicheren Lieferung; gezeichnet am 02.09.2026 | die Lieferung, der [Abschlussbericht](baldrian-lauf2.md), [was die Übernahme verändert hat](baldrian-lauf2-veraenderungen.md) | auf dem Stand, auf dem er gezeichnet wurde: [baldrian-lauf2-wiederholen.md](baldrian-lauf2-wiederholen.md) |
| **Fall 3** (`baldrian-klv-tg2015-fall3`) | dieselbe Lieferung `lieferungen/baldrian-2/`, dazu die Nachlieferungen des Falls | die Neufassung, vom Auftrag des Vorstands bis zum gebundenen Anfangsbestand in der Ablage; geführt am 02.10.2026 | das Paket [pakete/baldrian-klv-tg2015-fall3](../../pakete/README.md) | mit einem Aufruf, ohne Agenten |

## Warum es Fall 3 gibt

Lauf 2 hatte dem Zielsystem beigebracht, den übernommenen Tarif zu rechnen.
Damit ein neuer Fall zeigt, was eine Übernahme am Zielsystem verändert,
wurde das wieder zurückgebaut: Das Zielsystem stand danach so da, als hätte
es diesen Tarif nie gerechnet. Auf diesem Stand begann Fall 3 und führte die
Übernahme von vorn — mit dem Fallauftrag des Vorstands (ADR-026), der Linie
der Erstabnahmen (ADR-025) und dem Zugang in die Ablage (ADR-022), die es
bei Lauf 2 noch nicht gab.

Der Stand vor Fall 3 und der Stand danach tragen die Tags `fall3-vor` und
`fall3-nach`. `main` trägt den Stand danach.

## Fall 3 in Zahlen

| | |
|---|---|
| Übernommene Verträge | 834 |
| Abnahmen | A-M6, A-Q1, A-K2, A-O1 (Verweis), A-M1 bis A-M3, A-T1, A-M4, A-B2, A-B3 |
| Zielsystem | Rechenkern 3.21.0 vor dem Fall, 3.22.0 danach |
| Ablage nach dem Zugang | 388 Monatsabschlüsse, der jüngste zum 01.10.2026 |
| Schritte des Rezepts | 112 |

Die Ergebnisse des Falls — Abnahmebericht, die drei Berichte der
aktuariellen Tests, die Bestandsberichte vor und nach — entstehen beim
Nachfahren im Fall-Arbeitsbereich (`faelle/baldrian-klv-tg2015-fall3/`) und
in der Ablage der Welt.

## Wo die Teile liegen

| Was | Wo |
|---|---|
| Lieferungen der abgebenden Gesellschaft | [lieferungen/](../../lieferungen/README.md) |
| Das Werkzeug, das die Lieferungen erzeugt | [quellsystem/](../../quellsystem/README.md) |
| Festgehaltene Fälle | [pakete/](../../pakete/README.md) |
| Die Definition für einen frischen Start desselben Falls | `deploy/welt/fall-baldrian-klv-tg2015.conf` |
| Routinen: Welt aufstellen, Fall starten, nachfahren | [deploy/welt/](../../deploy/welt/README.md) |
| Ablauf eines Falls | [docs/architektur/ablauf-eines-falls.md](../architektur/ablauf-eines-falls.md) |

Der Arbeitsbereich eines Falls (`faelle/<name>/`) liegt nicht im Repository:
Er ist der lokale Datenraum mit dem unantastbaren Eingang und den
Zeichnungen (ADR-002).
