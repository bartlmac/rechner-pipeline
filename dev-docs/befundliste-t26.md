# Befundliste T26 — Pruefrunde des externen Gutachters

**Quelle.** Pruefbericht zu ToDo 26 vom 2026-09-17, 20:52 CEST, geprueft auf
`main` @ `f518b6a`, CPython 3.11.16 auf macOS/arm64 ohne Docker. Reine
Pruefbefugnis: keine Produktdatei angefasst, kein Commit. Methode ist unser
eigener Skill `teste-adversarial`. Der Volltext liegt ausserhalb des Repos in
der Korrespondenzablage des Wissens-Graphen.

**Gesamturteil des Gutachters.** „Der integrierte Hauptstand ist weiterhin
nicht ausreichend abgesichert fuer eine belastbare produktive Migration und
Betriebsfreigabe." Die Entwickleraussage „Alle zwanzig Befunde beider Runden
sind abgeschlossen" wird durch die Gegenproben nicht bestaetigt.

**16 bestaetigte Befundgruppen: zehn hoch, sechs mittel.** Die volle Suite war
dabei gruen (2212 passed, 3 skipped) — das widerlegt nichts: Die Gegenproben
treffen Vertragsgrenzen, die die vorhandenen Tests nicht abdecken.

**Auftrag des Maintainers (2026-09-19, nachts).** Die Befunde in der vom
Gutachter vorgegebenen Reihenfolge reparieren, ohne Unterbrechung, bis alle
geschlossen sind. Ausdrueckliche Vorgaben: **nicht den Einzelfall, sondern die
KLASSE** schliessen — also jeweils auch die analogen Stellen suchen; jede
Pruefung **mit Abweichungen und an ihren Grenzen in beide Richtungen** testen;
Tests so bauen, dass sie eine **Auspraegung von Problemfaellen** abdecken und
nicht einen bestimmten Fall. Fachliche Annahmen werden hier angeschrieben und
nach der Umsetzung vom Maintainer bestaetigt.

## Der Massstabsunterschied — der eigentliche Punkt

Wir haben einen Befund geschlossen, wenn der GEMELDETE FALL behoben war. Der
Gutachter prueft, ob die INVARIANTE unter gezielter Gegenprobe haelt. Nach
seinem Massstab war unsere Aussage zu stark. Diese Runde arbeitet deshalb
durchgehend auf Klassenebene; jeder Eintrag unten nennt die Klasse
ausdruecklich, nicht nur den Fall.

## Reihenfolge (vom Gutachter vorgegeben, vom Maintainer bestaetigt)

| Block | Inhalt | Befunde |
|---|---|---|
| 1 | Dateien erhalten | T26-01, Legacy-Verlust aus T26-02, Ankerhistorie aus T26-08 |
| 2 | Wiederanlauf und Publikation | T26-02 (Rest), T26-14, T26-15 |
| 3 | Abnahmegegenstand nachweisen — gemeinsam entlang derselben validierten Eingaben | T26-03, -04, -05, -06, -07 |
| 4 | Aussagen angleichen | T26-11, T26-12, T26-10, T26-09, T26-13, T26-16 |
| 5 | Erneut verifizieren | volle Suite in der Linux-Referenzumgebung, gezielte Gegenproben an den Commit-/Lese-/Abnahmegrenzen |

Sein Schlusssatz dazu: „Eine Betriebsfreigabe folgt nicht allein aus dem
Schliessen der Dokumentationsliste."

## Stand je Befund

Legende: OFFEN — noch nicht angefasst. IN ARBEIT — Klasse benannt, Bau laeuft.
GESCHLOSSEN — Fix gebaut, Klassentest gruen, Grenzen in beide Richtungen
mutiert.

| ID | Schwere | Block | Stand | Kurz |
|---|---|---|---|---|
| T26-01 | hoch | 1 | OFFEN | Registrierung von `fall` loescht den gueltigen Eingang `fall.neu` |
| T26-02 | hoch | 1+2 | OFFEN | Vier Wiederanlaufszenarien defekt; Legacy-Uebergang loescht den letzten belegten alten Stand |
| T26-08 | hoch | 1+4 | OFFEN | Externer Anker darf im Paket/in der Ablage liegen; Reexport loescht seine Historie |
| T26-14 | mittel | 2 | OFFEN | Parallele Eingaenge erhalten dasselbe Nummernband |
| T26-15 | mittel | 2 | OFFEN | Unpublizierter Arbeitsrest blockiert den Tagesbetrieb |
| T26-03 | hoch | 3 | OFFEN | Betriebseingang akzeptiert semantisch ungueltige A-M4-Belege ohne Tabellenbindung |
| T26-04 | hoch | 3 | OFFEN | Fuehrungsbeleg-Consumer akzeptiert selbst behauptete Ergebnisse |
| T26-05 | hoch | 3 | OFFEN | Fuehrungsprobe bestaetigt eine von 43.000 auf 1.042.999 EUR veraenderte Stammsumme |
| T26-06 | hoch | 3 | OFFEN | Roter Schichtbeleg fuehrt zu drei gruenen aktuariellen Vorlagenlaeufen |
| T26-07 | hoch | 3 | OFFEN | Schichteingaben fehlen in der Bindung; ungelesenes ungueltiges JSON wird unter gruenem Urteil gehasht |
| T26-11 | hoch | 4 | OFFEN | Bewegungsrechnung ignoriert RED; P-B1 bestaetigt die falschen Summen |
| T26-12 | mittel | 4 | OFFEN | Tarifverfahren `teilkuendigung` scheitert im produktiven RED-Pfad |
| T26-10 | hoch | 4 | OFFEN | Interne Seite mischt bei gleichzeitigem Tageslauf zwei Generationen |
| T26-09 | mittel | 4 | OFFEN | Wochenzahlen und Lueckenausweis bleiben trotz korrektem Anker manipulierbar |
| T26-13 | mittel | 4 | OFFEN | Registrierte Uebersetzung Quell- zu Zielpolicen wird nicht geprueft |
| T26-16 | mittel | 4 | OFFEN | Anker-HMAC schuetzt Rolle und Schluesselklasse nicht |

## Annahmen, die der Maintainer bestaetigen muss

Hier stehen fachliche und Zuschnitt-Entscheidungen, die ich waehrend der
Reparatur getroffen habe, weil niemand erreichbar war. Sie sind umgesetzt und
stehen zur Bestaetigung; sieht der Maintainer Korrekturbedarf, folgt eine
zweite Runde.

(noch keine — wird waehrend der Arbeit gefuellt)

## Die Befunde im Einzelnen

Je Befund: was der Gutachter nachgewiesen hat, welche KLASSE dahinter steht,
was gebaut wurde, und womit die Klasse gegen einen Rueckbau gesichert ist.

(wird waehrend der Arbeit gefuellt)
