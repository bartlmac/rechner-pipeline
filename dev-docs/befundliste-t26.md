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
| T26-02 | hoch | 1+2 | GESCHLOSSEN | alle vier Szenarien; Naht-Matrix auf 21 Kombinationen erweitert |
| T26-08 | hoch | 1+4 | GESCHLOSSEN | Externer Anker darf im Paket/in der Ablage liegen; Reexport loescht seine Historie |
| T26-14 | mittel | 2 | GESCHLOSSEN | Parallele Eingaenge erhalten dasselbe Nummernband |
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

## Neue Befunde, waehrend dieser Runde gefunden

Nicht vom Gutachter gemeldet, sondern beim Arbeiten aufgefallen. Sie stehen
hier, damit sie nicht in einer Nachricht verschwinden.

### N-03 — Das Bewegungskonto setzt eine Praemisse voraus, die bei einem uebernommenen Bestand nicht gilt

**Gefunden** 2026-09-20 von der Seiten-Session, beim Versuch, Berichte fuer
aeltere Stichtage zu rendern. Von mir am Code nachgemessen.

**Was passiert.** `bewegungskonto` bricht ab mit „Historie hat PEX-Status
ohne PEX-Ledger-Zeile: [3] — Historie und Ledger stammen nicht aus demselben
fortschreiben-Lauf". Gemessen an der Reproduktion (Betriebsbeginn 2025-01-01,
Zugang 2026-01-01, Lauf bis 2026-01-09), Stichtagssicht zum 2025-01-01:

* Historie der Police 3: `PEX` mit `status_date = 2023-11-01`
* Ledger derselben Police: `PEX` mit `status_date = 2026-01-01`

**Die Ursache ist nicht der Schnitt der Sicht.** Beide Zeilen sind richtig.
Die uebernommene Historie traegt die Vorgeschichte des ABGEBENDEN
Unternehmens an ihren echten Daten; der Ledger bucht dieselbe Tatsache am
Migrationsstichtag, weil unsere Buecher dort beginnen. Die Praemisse „beide
stammen aus demselben fortschreiben-Lauf" gilt fuer einen uebernommenen
Bestand schlicht nicht.

**Reichweite — ungeklaert und groesser als ein Renderer-Befund.** Der
Abschluss zu demselben Stichtag entsteht anstandslos, weil er diese Pruefung
nicht hat. Ob seine Zahlen richtig sind, ist damit NICHT gesagt: Die
Stichtagssicht zum 2025-01-01 traegt eine Police, die erst 2026 in die
Buecher kam. `jahresraster` kennt die richtige Regel bereits („vom ZUGANG,
nicht vom Vertragsbeginn"); `bewegungskonto` wendet sie auf seine Population
nicht an.

**Einordnung.** Dieselbe Funktionsfamilie wie T26-11 (Bewegungsrechnung
ignoriert RED) und dieselbe Achse wie T24-02. Wird deshalb zusammen mit
T26-11 in Block 4 bearbeitet, nicht davor — die Reihenfolge des Gutachters
bleibt.

## Annahmen, die der Maintainer bestaetigen muss

Hier stehen fachliche und Zuschnitt-Entscheidungen, die ich waehrend der
Reparatur getroffen habe, weil niemand erreichbar war. Sie sind umgesetzt und
stehen zur Bestaetigung; sieht der Maintainer Korrekturbedarf, folgt eine
zweite Runde.

1. **Eingang gilt als eingerechnet, wenn der Abschluss seine Zielnummern
   traegt** (T26-02, Szenario 4). Alternative waere ein neues Feld im
   Abschluss gewesen, das die absorbierten Eingaenge nennt — das haette das
   Abschlussformat geaendert, das 0444 geschrieben und in A-B1 gehasht wird.
   Die gewaehlte Loesung fragt die vorhandene Tabelle. Benannte Grenze steht
   im Docstring.
2. **Die Staging-Wurzel heisst `uebernahme.neu`** und liegt neben
   `uebernahme` (T26-01). Jeder andere Name taete es auch; entscheidend ist,
   dass es eine ZWEITE Wurzel ist. Bestehende Laufzeitumgebungen haben dort
   nichts liegen, ein Umzug ist nicht noetig.
3. **Eine angefangene Protokollzeile wird weggeschnitten** (T26-02,
   Szenario 3), aber nur ohne abschliessenden Zeilenumbruch und nur, wenn
   ein Marker bezeugt, dass ein Publish unterwegs war.

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

### Block 2, Teil 1 — T26-02 vollstaendig

**Die Klasse.** Die Wiederanlauf-Zustandsmaschine kannte genau EINEN
Ausgangszustand und EINE Abbruchstelle. Sichtbar war das an den Tests: Sie
legten immer zuerst einen gruenen Symlink-Stand an und injizierten den
Fehler nur VOR dem ersten Schreibvorgang. Was ausserhalb dieser einen Spalte
lag, war nie gelaufen — und "gruen" und "nie gelaufen" sehen gleich aus.

**Die vier Szenarien und was jeweils fehlte.**

1. *Erstbefuellung.* `stand_vorher` ist None; die einzige Ruecksetzbedingung
   verlangte einen vorherigen Stand. Journal und Marker wurden
   zurueckgenommen, der neue Stand blieb stehen — danach meldete jeder Lauf
   dauerhaft "Protokoll kennt keinen uebernommenen Lauf". Jetzt nimmt die
   Ruecknahme auch den neuen Stand zurueck, und zwar mit FESTSTEHENDER
   Identitaet: Der Marker nennt die Generation, der Symlink zeigt auf sie.
2. *Legacy-Verzeichnis.* `stand_vorher == "stand"` wurde ausdruecklich
   uebersprungen. Der Erstuebergang schiebt das echte Verzeichnis nach
   `stand-erstfassung` und setzt den Symlink; zurueckgenommen ist das erst,
   wenn beides wieder steht. Zwei Abbruchstellen fallen darunter und sehen
   verschieden aus — `stand` fehlt, oder `stand` ist ein Symlink —, deshalb
   fragt der Code, ob `stand` noch das echte Verzeichnis von vorher ist.
   (Der Datenverlust desselben Szenarios steckte in der Aufraeumung und ist
   in Block 1 geschlossen.)
3. *Angefangene Protokollzeile.* Die Ruecknahme liest das Protokoll, bevor
   sie irgendetwas zuruecksetzen kann — und starb am JSON-Fehler der
   Teilzeile. Jetzt wird ein Fragment OHNE Zeilenumbruch weggeschnitten: Es
   ist nie eine Zeile geworden. Bewusst eng — eine vollstaendige Zeile, die
   kein JSON ist, bleibt ein Fehler, denn dort gibt es keinen Ausweg, der
   nicht Beweismaterial vernichtet.
4. *Abschluss geschrieben, Bericht gescheitert.* Zwei Fehler in einem. Der
   Marker lag HINTER der Abschluss-Schleife und behauptete im Kommentar,
   er stehe davor; er steht jetzt davor, denn der Abschluss ist der erste
   unwiderrufliche Schritt (0444, nie neu gerechnet). Und die Frage "ist
   dieser Eingang schon eingerechnet" ging an einen STELLVERTRETER — das
   Protokoll —, obwohl die Sache selbst danebenliegt: Der Abschluss traegt
   die Zielnummern des Eingangs oder er traegt sie nicht. Gefragt wird
   jetzt die Tabelle.

**Gegen Rueckbau gesichert.** Die Naht-Matrix steht auf 21 Kombinationen
statt vier: sieben Abbruchstellen (Abschluss, Bericht, Journal, Generation,
Symlink, Protokoll, Protokoll-Teilwrite) mal drei Ausgangszustaenden (leer,
Legacy-Verzeichnis, Symlink). Jede Kombination verlangt, dass der Retry
gelingt, der gefuehrte Tag stimmt, Marker und Journalkopie aufgeraeumt sind
und die Protokollkette wieder ungebrochen ist. Dazu zwei gezielte Tests fuer
Szenario 4 — einer fuer den Retry, einer fuer die Gegenrichtung: Ein
Eingang, den der Abschluss NICHT kennt, bleibt abgewiesen (ADR-011).

**Mutationsproben.** Abschluss-Frage entfernt: Szenario-4-Test rot, die
Gegenrichtung bleibt gruen. Teilzeilen-Schnitt entfernt: alle drei
Teilwrite-Kombinationen rot.

**Annahme zur Bestaetigung (siehe oben):** Ein Eingang gilt als
eingerechnet, wenn der juengste festgeschriebene Abschluss MINDESTENS EINE
seiner Zielnummern traegt. Ein Eingang, dessen Vertraege am Stichtag alle
schon beendet waeren, hinterliesse keine Zeile und zaehlte als unbekannt —
fuer einen Zugang zum eigenen Stichtag kann das nicht eintreten.

### Block 2, Teil 2 — T26-14

**Die Klasse.** Das Register der Nummernbaender ist die Summe der Eingaenge
selbst: Jeder nennt sein Band in `eingang.json`, und das naechste wird daraus
abgeleitet. Lesen und Fortschreiben sind damit ZWEI Schritte, und was
dazwischen passiert, hat niemand verhindert. Zwei gleichzeitige
Registrierungen bekamen dasselbe Band und veroeffentlichten beide;
aufgefallen ist es erst Tage spaeter im Tagesbetrieb als
Policennummern-Kollision. Die Trennung der Zahlenraeume war bis dahin
behauptet, nicht gesichert.

**Was gebaut ist — beide Seiten, wie der Gutachter verlangt.**

1. *Eine Sperre um Lesen und Veroeffentlichen.* `eingang_sperre(stand)`,
   nicht blockierend wie die Laufsperre, mit Meldung. Sie umschliesst die
   Bandberechnung UND die Publikation, also genau das Fenster, in dem der
   Befund sass.
2. *Die Nachrechnung beim Lesen.* `lies_uebernahmen` prueft jetzt, dass die
   Baender paarweise disjunkt sind. Eine Sperre schuetzt nur Prozesse, die
   sie nehmen; ob die Baender disjunkt SIND, steht in den Eingaengen und
   laesst sich jederzeit nachrechnen. Dafuer traegt `Uebernahme` ihr Band.

**Gegen Rueckbau gesichert.** `tests/test_nummernband_disjunkt.py`: zehn
Bandlagen als Tabelle, darunter die Grenze in beide Richtungen — buendig
aneinander ist erlaubt, um genau eins ueberlappend nicht. Dazu die
Sperre deterministisch geprueft (im Test gehalten, kein Zeitfenster) und
der Befund von innen nachgestellt: Waehrend der erste Schreiber im Register
liest, versucht ein zweiter zu registrieren — ohne Sperre kommt er durch.
Die Leserpruefung mit Positivkontrolle.

**Mutationsproben.** Sperre ausgeschaltet: beide Sperrtests rot, und der
Zwischenruf meldet "durchgekommen" — der Befund selbst. Leserpruefung
ausgeschaltet: Lesertest rot.