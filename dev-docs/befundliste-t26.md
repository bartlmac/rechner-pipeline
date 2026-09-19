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
| T26-01 | hoch | 1 | GESCHLOSSEN | Registrierung von `fall` loescht den gueltigen Eingang `fall.neu` |
| T26-02 | hoch | 1+2 | TEILWEISE | Legacy-Verlust geschlossen; drei Wiederanlaufszenarien offen (Block 2) |
| T26-08 | hoch | 1+4 | GESCHLOSSEN | Externer Anker darf im Paket/in der Ablage liegen; Reexport loescht seine Historie |
| T26-14 | mittel | 2 | OFFEN | Parallele Eingaenge erhalten dasselbe Nummernband |
| T26-15 | mittel | 2 | GESCHLOSSEN | Unpublizierter Arbeitsrest blockiert den Tagesbetrieb |
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

### Block 1, Teil 1 — T26-01, T26-15 und der Legacy-Verlust aus T26-02

**Die Klasse.** Eine Loeschung schloss aus der GESTALT eines Pfades — seinem
Namen, seiner Form — auf seinen Lebenszyklus-Zustand. Dreimal belegt, jedes
Mal mit Datenverlust:

* T24-01/T24-07: `stand` war ein haengender Symlink, also galt jedes
  `stand-*` als Waise; aufgeraeumt wurde der einzige Stand der Ablage.
* T26-01: `fall.neu` sah aus wie der Arbeitsrest eines Anlegens von `fall`.
  Es war der regulaer registrierte Eingang eines Falls, der zufaellig so
  heisst. Zwei gewoehnliche Aufrufe, keine Manipulation; geloescht wurden
  auch schreibgeschuetzte Dateien, und das Nummernband wurde wiederverwendet.
* T26-02 Szenario 2: `stand` war ein echtes Verzeichnis (unterstuetzter
  Legacy-Zustand), damit war wieder alles Waise; verschwunden ist
  `stand-erstfassung`, der letzte belegte alte Stand.

**Was gebaut ist — drei Instrumente, nicht drei Einzelfixes.**

1. *Getrennte Wurzeln statt einer Namensregel.* Ein Eingang entsteht jetzt
   unter `uebernahme.neu/<fallname>` und wird von dort nach
   `uebernahme/<fallname>` umbenannt. Solange beide dieselbe Wurzel teilten,
   war jede Unterscheidung eine Konvention ueber Namen — und ein Fallname ist
   frei waehlbar. Zwei Wurzeln machen die Ueberschneidung unmoeglich.
   Derselbe Schnitt schliesst T26-15: Der Leser sieht unter `uebernahme/`
   nur noch Veroeffentlichtes, ein abgebrochenes Anlegen blockiert den
   Tagesbetrieb nicht mehr.
2. *`ohne_marker` in `entferne_verzeichnis`.* Die Gegenrichtung des
   vorhandenen `marker`: Dieser sagt „das hier ist meins", jener sagt „das
   hier ist noch nicht veroeffentlicht". Ein Verzeichnis mit `eingang.json`
   wird nicht geloescht, auch wenn Name und Lage passen. Ein HAENGENDER
   Symlink dieses Namens zaehlt mit — er ist `exists() == False` und saehe
   sonst aus wie ein Verzeichnis ohne Marker.
3. *Die Aufraeumung fragt nach ihrer PRAEMISSE, nicht nach Ausnahmen.*
   `_verwaiste_staende_entfernen` raeumt nur, wenn `stand` ein Symlink auf
   eine Generation in der Wurzel ist. Jeder andere Zustand — fehlend,
   echtes Verzeichnis, Datei — raeumt NICHTS auf und sagt warum. Die
   Aufzaehlung der bekannten Ausnahmen war genau der Fehler: Nach T24-07
   war der haengende Symlink abgedeckt und der Legacy-Zustand nicht.

**Gegen Rueckbau gesichert.** `tests/test_lebenszyklus_vor_loeschung.py`
prueft die Klasse, nicht die Faelle: sechs Namenspaare (darunter der
gemeldete in beiden Reihenfolgen, zwei Staffelungen, ein Paar mit dem Namen
der Staging-Wurzel selbst und ein unbeteiligtes Kontrollpaar) und vier
Zustaende der Ablage, darunter einer, der nie beobachtet wurde (`stand` ist
eine Datei). Jede Wache hat ihre Positivkontrolle: Die echte Waise MUSS
verschwinden, ein Arbeitsrest ohne Marker MUSS geloescht werden — eine
Regel, die immer sperrt, waere genauso falsch wie eine, die nie sperrt.

**Mutationsproben, alle drei nachgefahren.** Staging zurueck in die
Eingangswurzel: drei Namenspaare und der Lesertest werden rot. `ohne_marker`
ausgeschaltet: beide Markertests rot. Praemisse-Wache ausgeschaltet: alle
drei Zustandsfaelle rot, die Positivkontrolle bleibt gruen.


### Block 1, Teil 2 — T26-08

**Die Klasse.** Ein Bezug, der Vertrauen stiften soll, muss ausserhalb des
Geltungsbereichs dessen liegen, der ihn belegt. Die Regel gab es schon — fuer
alles, was eine ZEICHNUNG autorisiert (Ordnung, Freigabeschluessel, Mandat,
ADR-018). Sie war aber zweimal implementiert: einmal als
`ausserhalb_des_falls`, einmal woertlich in `lade_zeichnungsordnung`. Der
ANKER eines Stands-Pakets folgt derselben Regel und war von keiner der beiden
gedeckt.

**Was der Gutachter gemessen hat.** Ein Anker im Paket: `anchor_rows_before_
reexport 2`, `anchor_rows_after_reexport 1` — die Historie, die laut Vertrag
nur wachsen darf, verschwand beim naechsten Export. Und weil der Anker mit
dem Paket reist, prueft der Konsument die Faelschung gegen ihre eigene
Beilage: `forged_in_force 1068 true_in_force 68 accepted True`. Die
Positivkontrolle mit getrennt verwahrtem Anker lehnte dieselbe Aenderung ab.

**Was gebaut ist.** Eine Implementierung, `ausserhalb_von(pfad, bereich,
muss_existieren=)`, angewandt an vier Stellen: Ordnung, Mandat (beide ueber
den unveraenderten Namen `ausserhalb_des_falls`), Ankerverzeichnis im
Erzeuger, Ankerdatei im Konsumenten. `muss_existieren` trennt zwei Faelle,
die vorher verschwommen: Ein Beleg, den es nicht gibt, autorisiert nichts und
gilt nicht als aussen; ein Verzeichnis, in das erst geschrieben wird, gibt es
bei der Pruefung noch nicht.

`ankerziel_fehler` laeuft VOR der Loeschung des Zielverzeichnisses. Der
Zeitpunkt ist der Punkt: Eine Pruefung danach haette das vorhandene Paket
schon gekostet.

**Gegen Rueckbau gesichert.** `tests/test_bezug_ausserhalb.py` prueft die
Regel als Tabelle (drinnen, gleich, ueber `..`, Symlink von innen nach
aussen, Symlink von aussen nach innen, und die Gegenprobe draussen), dann
sieben Ankerlagen gegen den Erzeuger — jedes Mal mit der Zusicherung, dass
das vorhandene Paket unangetastet bleibt —, die wachsende Ankerreihe ueber
drei Reexporte und den Konsumenten samt Positivkontrolle.

**Mutationsproben.** Ankerpruefung entfernt: zwei Erzeugertests rot.
Konsumentenpruefung entfernt: Konsumententest rot. Aufgeloeste Haelfte der
Regel entfernt: Regeltabelle und Symlink-Test rot.