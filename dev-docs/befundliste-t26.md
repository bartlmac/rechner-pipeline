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

## Stand am Morgen des 2026-09-20

Gearbeitet in der Nacht vom 19. auf den 20.09., auf dem Zweig `dora-t26`
(abgezweigt von `berichte-monat-jahr`, das auf `origin/main` @ `f518b6a`
sitzt). Jeder Commit hat seine eigene volle Suite am Stueck gesehen, vom
ersten mit 2245 bis zum letzten mit 2337 Tests.

| | Befunde |
|---|---|
| **Geschlossen** | T26-01, T26-02, T26-04, T26-05, T26-06, T26-07, T26-08, T26-09, T26-10, T26-11, T26-13, T26-14, T26-15, T26-16 |
| **Geschlossen als dokumentierte Abweisung** | T26-12 |
| **Teilweise** | T26-03 — die Tabellenbindung steht, die Rollenpruefung braucht eine Entscheidung zur Schichtenkarte |
| **Offen** | keiner |
| **Zusaetzlich geschlossen** | N-03 (nicht vom Gutachter, von der Seiten-Session gefunden) |

**Was der Maintainer entscheiden muss**, bevor der Rest gebaut wird:

1. **Die Schichtenkarte** — darf `betrieb` den Fall lesen? Drei Wege mit
   Empfehlung stehen bei T26-03. **ENTSCHIEDEN 2026-09-22: Weg 2** — der
   Vertrag wandert nach `models`, gekoppelt mit dem Ausbau der
   Zeichnungsschicht. Noch nicht gebaut; Begruendung bei T26-03.
2. **Die Herabsetzung** — darf sie die Versicherungssumme HEBEN? Gemessen
   hebt sie sie (+202.338 ueber alle Jahre des Fixtures). Steht bei T26-11.
   **ERLEDIGT 2026-09-22: keine Entscheidung** — die Herabsetzung senkt
   (85.856); die Hebung war ein Fixture-Artefakt (`rho=0.04` statt real
   1e-8). Folgeauftrag: Fixture realistisch, nicht gebaut.
3. **Die Teilkuendigung** — Tarifplan und Kernkommentar widersprechen sich.
   Steht bei T26-12.
   **AUFGELOEST 2026-09-22: als Klasse** — Ratsche „Schalterwert ⊆
   produktiv ausfuehrbar" bei der Freischaltung, Teilkuendigung als erster
   Bauauftrag, Annahme 4 revidiert. Nichts gebaut; siehe T26-12.
4. Die fuenf Annahmen im Abschnitt darunter.

**Was noch zu bauen ist:** T26-10 (die Seite mischt bei gleichzeitigem
Tageslauf zwei Generationen). Dazu Block 5 des Gutachters — erneute Verifikation, volle
Suite in der Linux-Referenzumgebung, und die Korrektur der Aussage im PR.

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
| T26-03 | hoch | 3 | TEILWEISE | Betriebseingang akzeptiert semantisch ungueltige A-M4-Belege ohne Tabellenbindung |
| T26-04 | hoch | 3 | GESCHLOSSEN | Fuehrungsbeleg-Consumer akzeptiert selbst behauptete Ergebnisse |
| T26-05 | hoch | 3 | GESCHLOSSEN | Fuehrungsprobe bestaetigt eine von 43.000 auf 1.042.999 EUR veraenderte Stammsumme |
| T26-06 | hoch | 3 | GESCHLOSSEN | Roter Schichtbeleg fuehrt zu drei gruenen aktuariellen Vorlagenlaeufen |
| T26-07 | hoch | 3 | GESCHLOSSEN | Schichteingaben fehlen in der Bindung; ungelesenes ungueltiges JSON wird unter gruenem Urteil gehasht |
| T26-11 | hoch | 4 | GESCHLOSSEN | Bewegungsrechnung ignoriert RED; P-B1 bestaetigt die falschen Summen |
| T26-12 | mittel | 4 | GESCHLOSSEN (als Abweisung) | Tarifverfahren `teilkuendigung` scheitert im produktiven RED-Pfad |
| T26-10 | hoch | 4 | GESCHLOSSEN | Interne Seite mischt bei gleichzeitigem Tageslauf zwei Generationen |
| T26-09 | mittel | 4 | GESCHLOSSEN | Wochenzahlen und Lueckenausweis bleiben trotz korrektem Anker manipulierbar |
| T26-13 | mittel | 4 | GESCHLOSSEN | Registrierte Uebersetzung Quell- zu Zielpolicen wird nicht geprueft |
| T26-16 | mittel | 4 | GESCHLOSSEN | Anker-HMAC schuetzt Rolle und Schluesselklasse nicht |

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
ignoriert RED) und dieselbe Achse wie T24-02. Zusammen mit T26-11
bearbeitet.

**GESCHLOSSEN.** Die Ursache war die POPULATION, nicht die Pruefung: Die
Sicht zum 2025-01-01 trug eine Police, die erst 2026 in die Buecher kam —
samt ihrer uebernommenen Vorgeschichte. `bewegungskonto` schneidet seine
Population jetzt auf `bestandszugang <= bis`. Die Regel stand schon in
`jahresraster` („vom ZUGANG, nicht vom Vertragsbeginn"); sie galt nur fuer
das Jahresraster und nicht fuer die Population darunter.

Nachgemessen an der Reproduktion: Alle dreizehn Monatsstichtage rechnen jetzt
durch, vorher fiel der erste. Damit ist auch der Blocker der Seiten-Session
weg.

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
   **BESTAETIGT 2026-09-22** (Maintainer, nach Erklaerung des Eingangs;
   Widerspruch bis zum Bau moeglich).
2. **Die Staging-Wurzel heisst `uebernahme.neu`** und liegt neben
   `uebernahme` (T26-01). Jeder andere Name taete es auch; entscheidend ist,
   dass es eine ZWEITE Wurzel ist. Bestehende Laufzeitumgebungen haben dort
   nichts liegen, ein Umzug ist nicht noetig.
   **BESTAETIGT 2026-09-22** (Maintainer delegiert an dev, "wenn nicht
   kritisch, sauber"): Der Punkt ist die ZWEITE Wurzel — ein halb
   geschriebener Eingang kann strukturell nie fuer einen registrierten
   gehalten werden. Der Name ist gleichgueltig. Sauber, bestaetigt.
3. **Eine angefangene Protokollzeile wird weggeschnitten** (T26-02,
   Szenario 3), aber nur ohne abschliessenden Zeilenumbruch und nur, wenn
   ein Marker bezeugt, dass ein Publish unterwegs war.
   **BESTAETIGT 2026-09-22** (Maintainer delegiert an dev): Beide
   Bedingungen muessen gelten — ohne Zeilenumbruch UND mit Publish-Marker.
   Eine vollstaendige Zeile wird nie geschnitten; der Schnitt ist auf das
   eine Absturzszenario (T26-02 Sz. 3) begrenzt. Sauber, bestaetigt.
4. **Die Kombination `teilkuendigung` + Herabsetzungsrate > 0 wird
   ABGEWIESEN**, nicht implementiert (T26-12). Der Gutachter laesst beide
   Wege zu; ich habe den gewaehlt, der keine fachliche Entscheidung
   vorwegnimmt. Wenn die Fuehrung das Verfahren tatsaechlich fahren soll,
   ist das ein Bauauftrag und kein Fix.
   **REVIDIERT 2026-09-22:** Die Abweisung bleibt nur Notausgang bis zum
   Bau, sie ist keine Aufloesung. Aufloesung ist die Ratsche (Klasse) plus
   die Teilkuendigung als Bauauftrag — siehe T26-12.
5. **`bestand.parquet` MUSS vom Beleggraphen genannt sein**, die uebrigen
   Pflichttabellen werden geprueft, wenn der Graph sie nennt (T26-03). Ein
   aelterer P-B1-Ledger fuehrt Bestand und Historie, aber nicht jeden
   Nebenstand; ihn zur Pflicht zu machen haette bestehende Faelle
   unbrauchbar gemacht. Die Luecke wird auf stderr benannt, nicht
   verschwiegen. Wenn du es strenger willst, sag es — dann muss der
   P-B1-Ledger alle drei fuehren.
   **ENTSCHIEDEN 2026-09-22: STRENG** (Maintainer). Alle drei
   Pflichttabellen (bestand, historie, ledger) muessen vom Beleggraphen
   bezeugt sein; ein unbezeugter Ledger ist eine Luecke, keine Warnung.
   Konsequenz: `eingang_anlegen` weist unbelegte historie/ledger ab statt
   auf stderr zu warnen; aeltere P-B1-Ledger reichen nicht mehr, der
   Migrationsfall wird ohnehin auf dem neuen Stand neu gefahren und
   gezeichnet. Bau folgt mit der Ratsche (T26-12).

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

### Block 3, Teil 1 — T26-06 und T26-07

Beide sitzen am Schichtbeleg und gehoeren deshalb zusammen: der eine im
Consumer, der andere im Producer, und dazwischen dieselbe Datei.

**T26-06 — der Consumer las die Kette nach und uebersah das Urteil.**
`aktuartest_lauf._schichten` prueft Systemstand und Eingabe-Hashes und
reduziert danach direkt auf `roh["schichten"]`. `befunde` und `summary` sah
er nie. Ein echter roter Producerlauf (25 von 26 Policen getragen) fuehrte so
zu drei gruenen aktuariellen Vorlagenlaeufen.

Geprueft wird jetzt dreierlei, und jedes faengt eine andere Manipulation:
dass der Producer keine Befunde meldet, dass seine Zusammenfassung dasselbe
sagt wie seine Befundliste, und dass die Schichttabelle so viele Policen
traegt, wie die Zusammenfassung behauptet. Wer nur das erste prueft,
akzeptiert einen Beleg mit geleerter Befundliste und unveraendertem summary.

**T26-07 — zwei Haelften, eine Ursache: jeder Producer trug seine eigene
Bindung.**

*Teil a:* `verankerung_belegen` band vier Dateien und las daneben Zeilen,
Vorgeschichte und Ankerquelle, ohne sie zu nennen. Mit geaenderter
`zeilen.json` nahm der Consumer denselben alten Beleg weiter an — die
Eingaben waren fachlich wirksam, der Beleg schwieg ueber sie.

*Teil b:* `fuehrungsprobe` rief `_schichten` OHNE Bindung und hashte die
Datei danach ein zweites Mal. Gebunden wurden die Bytes der zweiten Lesung,
geprueft die der ersten. Der Gutachter hat das nachgestellt: Der Producer
band unter gruenem Urteil eine Datei, die er nie verarbeitet hatte.

Beide benutzen jetzt `gates._common.Eingangsbindung` — dieselbe Instanz wird
an `_schichten` weitergereicht, und ihr Cache garantiert, dass eine bereits
gebundene Datei nicht noch einmal gelesen wird. Der Beleg nennt, was
`als_beleg()` sagt, nicht eine ausgewaehlte Liste, die beim naechsten neuen
Parameter still unvollstaendig wird.

Damit ist auch der Backlog-Eintrag „Zwei Producer tragen ihre eigene Fassung
der Eingabenbindung" erledigt — und die Einschaetzung „gleichwertig, ohne
fachliche Aussage" widerlegt.

**Gegen Rueckbau gesichert.** Vier Urteilslagen als Tabelle (roter Beleg, nur
das summary rot, unvollstaendig, Tabelle passt nicht zur Zusammenfassung) mit
der vorhandenen Positivkontrolle daneben. Die e2e-Kette prueft, dass der
Schichtbeleg jede gelesene Eingabe nennt — Zeilen, Vorgeschichte,
Ankerquelle, Bestand, Verankerung. Dazu eine AST-Ratsche gegen eine eigene
Bindungs-Fassung in den fuenf bindenden Kommandos, mit ihrer Gegenrichtung
(jedes nennt `Eingangsbindung` auch tatsaechlich). Die Ratsche ist am ALTEN
Stand gegengeprobt: Sie findet dort `schluessel:659` und `binde:665`.

**Mutationsprobe.** Die alte, ausgewaehlte Eingabenliste wiederhergestellt:
die ganze e2e-Kette faellt.

### Block 3, Teil 2 — T26-03 (teilweise) und eine Architekturfrage

**Was gebaut ist.** Der Betriebseingang bindet die Tabellen, die er
uebernimmt, an das, was die Migrationsabnahme gesehen hat. Der A-M4-Snapshot
nennt seine Pflichtbelege als Hashes; `belegte_tabellen` sucht die
zugehoerigen Dateien im Fall, liest ihre Eingabenbloecke (`input_hashes` der
Gate-Ledger, `provenienz.eingaben` der Producer-Belege) und sammelt daraus
die Hashes der Quelltabellen. Stimmt eine Tabelle nicht mit dem ueberein,
was die Abnahme bezeugt, entsteht kein Eingang — geprueft VOR dem ersten
Seiteneffekt.

Dazu der aus dem Inhalt ableitbare Teil der Snapshot-Semantik: dass
`pflichtbelege['pk1_belege']` die Generationen-Belegmenge ist. Die Mechanik
steht jetzt in `models.schemas.p9_semantik_fehler` und wird von BEIDEN
Seiten benutzt — dem Gate und dem Betriebseingang.

**Was NICHT gebaut ist, und warum.** Der Gutachter verlangt, den vorhandenen
Gate-Lesevertrag fuer Scope, Rollen, Graph und geltende Spitze zu verwenden.
Die Rollenpruefung braucht `fall.belegrollen(gate, scope)` — und die
Schichtenkarte laesst `betrieb -> fall` und `betrieb -> gates` ausdruecklich
nicht zu (`SCHICHT_ERLAUBT`, mit dem Kommentar „keine Kante betrieb ->
gates"). Der Betriebseingang kann den Rollenvertrag also nicht erreichen.

Damit bleibt DoRAs schaerfster Einzelfall offen: ein Snapshot, dessen
einzige Pflichtrolle `pb1_ledger` ist, wird weiterhin angenommen, solange
sein Beleggraph existiert und die Tabellen stimmen.

**ENTSCHEIDUNG DES MAINTAINERS NOETIG.** Drei Wege, mit meiner Empfehlung
zuerst:

1. **`betrieb -> fall` erlauben.** Der Betriebseingang operiert ohnehin auf
   einem Fall — er liest `fall.json` und `entscheide/` schon heute, nur mit
   eigenem Wissen ueber das Layout statt ueber das Modul. Die Kante wuerde
   eine bestehende Doppelpflege beseitigen statt eine neue Abhaengigkeit
   schaffen. Ein ADR-Satz, eine Zeile in `SCHICHT_ERLAUBT`.
2. **Den Belegrollen-Vertrag nach `models` ziehen.** Fachlich richtig
   (paketuebergreifender Vertrag), aber `fall.py` darf NICHTS importieren
   (`"fall": set()`), muesste die Tabelle also selbst behalten — womit sie
   an zwei Orten staende. Das ist die Klasse, die wir gerade schliessen.
3. **So lassen und benennen.** Dann steht im Backlog, dass der
   Betriebseingang die Rollenmenge nicht prueft, und der Gutachter wird den
   Punkt zu Recht offen fuehren.

Ich habe NICHT entschieden, weil es die Schichtenkarte aendert — genau das
STOPP-Kriterium des Entwicklungs-Skills.

**ENTSCHIEDEN 2026-09-22 (Maintainer): Weg 2, gekoppelt mit der
Zeichnungsschicht — noch nicht gebaut.** Der Belegrollen-Vertrag wandert
nach `models`, die Schicht, die fuer paketuebergreifend lesbare Vertraege
da ist. Nicht `betrieb -> fall`: Das Verbot versteckt den Vertrag nicht,
es sagt, wo er hingehoert — sonst haengt die Laufzeit an einem
Werkstatt-Modul. Dasselbe Muster wie die P-B1-Engine
(`bestand.vorbedingungen`, von Gate UND Betrieb gerufen): eine Definition,
Gate und Betrieb koennen nicht auseinanderlaufen.

Der Vorbehalt oben gegen Weg 2 („fall muesste die Tabelle selbst
behalten") gilt bei Nachpruefen nicht: `fall.py` NUTZT `belegrollen`
nicht selbst, es beherbergt und exponiert es nur (`fall.py:97,254`);
Verbraucher ist das Gate (`gate_entscheid.py:914`). Mitwandern muss die
Scope-Validierung (`scope_dokument`), auf die `belegrollen` sich stuetzt.

Dazu wird die Zeichnungsschicht zu Ende gebaut (Schema 7,
Schluesselklasse, Signaturpruefung im Betriebseingang), damit der Betrieb
ZWEI unabhaengige Zeugen hat: den eigenen Vollstaendigkeitscheck gegen
den Vertrag und das verifizierte Siegel — kein Beleg, der nur sich selbst
bezeugt. Der Bau traegt sein eigenes ADR (Schichtenkarte: `belegrollen`
aus `fall` nach `models`; Kanten gates -> models und betrieb -> models
sind schon erlaubt) und die Schema-7-Arbeit des Architektur-Strangs.

**Gegen Rueckbau gesichert.** Vier Manipulationslagen als Tabelle: die nach
der Abnahme getauschte Stammtabelle (Summe 43.000 -> 1.042.999, derselbe
Griff wie in T26-05), der Snapshot ohne existierenden Beleggraphen, der sich
widersprechende Graph und die Luege in den Generationenbelegen. Jede muss
abgewiesen werden UND darf keinen halben Eingang hinterlassen.

**Mutationsproben.** Tabellenbindung entfernt: drei der vier Lagen rot.
pk1-Semantik entfernt: die vierte rot.

### Vorgezogen aus Block 4 — T26-16

Vorgezogen, weil er klein und abgeschlossen ist und weil er dieselbe Datei
betrifft wie T26-08 aus Block 1.

**Der Befund.** Die HMAC lief ueber den Ankersatz OHNE das gesamte
`zeichnung`-Objekt. Rolle und Schluesselklasse standen damit UNSIGNIERT
daneben: Aus `agent/betrieb`/`agent` wurde `mensch/betrieb`/`mensch`, und
der Schluesselring bestaetigte die Zeichnung weiterhin. Genau diese
Unterscheidung begruendet ADR-018 damit, dass sie am BELEG ablesbar sei.

**Was gebaut ist.** Das Verfahren heisst jetzt `hmac-sha256-v2` und
signiert Rolle, Klasse, Verfahren und Schluesselkennung mit; ausgenommen
ist nur das Signaturfeld selbst.

Alte Saetze bleiben PRUEFBAR — die Ankerreihe ist nur anfuegbar, und was
einmal gezeichnet wurde, bleibt stehen. `deckt_urheberschaft(zeichnung)`
sagt, ob ein Satz seine Urheberangaben unter der Signatur traegt. Ohne
diese Auskunft waere „geprueft" fuer beide Verfahren dasselbe Wort mit zwei
Bedeutungen.

**Gegen Rueckbau gesichert.** Jedes Feld der Zeichnung, das eine Aussage
ueber den Urheber traegt, wird einzeln verbogen — nicht nur die zwei
gemeldeten. Dazu die Negativkontrolle des Gutachters (eine echte
Inhaltsaenderung faellt) und ein Test, der einen v1-Satz baut, ihn erfolgreich
prueft, seine Luecke vorfuehrt und `deckt_urheberschaft` dazu befragt.

**Nebenbei erledigt:** die beiden Whitespace-Befunde aus dem Abschnitt
Verifikation (`dev-docs/review-u1-befunde.md`, `tests/test_paket_anker_t2404.py`).
`git diff --check` ist sauber.

### Vorgezogen aus Block 4 — T26-13

**Der Befund.** `policennummern.parquet` ist im Manifest verpflichtend und
gehasht — gelesen hat sie niemand gegen diesen Hash. Sie fehlte sogar in der
Schleife ueber PFLICHT/OPTIONAL, und `zielnummern` las sie unabhaengig davon.
Eine Mutation nur an der Map, Manifest unveraendert, lieferte eine falsche
Zielidentitaet; bei vollstaendigem Verlust der Bruecke blieb sogar die
Tagesfuehrung gruen.

Der Docstring versprach dabei ausdruecklich „wer sie aendert, bricht den
Hash" — ein Satz, den niemand geprueft hat. Genau die Klasse aus
[[feedback-text-driftet-code-nicht]], nur im Code statt im Backlog.

**Was gebaut ist.** Die Bruecke wird gegen ihre registrierte Summe gelesen
(einmal, aus denselben Bytes) und auf Bijektivitaet geprueft: Jede gefuehrte
Police hat genau eine Quellnummer, Zielnummern sind eindeutig, und sie liegen
im Nummernband dieses Eingangs. Eine fehlende Map faellt wie jede andere
Pflichtdatei.

**Gegen Rueckbau gesichert.** Vier Verbiegungen der registrierten Datei und
fuenf Bijektionslagen als Tabelle. Die wichtigste Zeile ist die vierte
Verbiegung: Map UND Manifest zusammen geaendert. Ohne sie pruefte nichts den
inhaltlichen Teil — die drei anderen fallen schon am Hash, und der
Tabellentest ruft die Funktion direkt auf. Ein Aufruf, der aus
`lies_uebernahme` verschwindet, faellt nur an dieser einen Zeile auf.

**Mutationsproben.** Hashpruefung entfernt: drei Verbiegungen rot.
Bijektionspruefung entfernt: die vierte rot.

**Nebenwirkung, die etwas zeigt:** Der Bandueberschneidungs-Test aus T26-14
fiel, weil seine Manipulation die Zielnummern aus dem Band schob — die neue
Pruefung sah es zuerst. Der Test manipuliert jetzt so, dass er seinen eigenen
Gegenstand trifft. Zwei Pruefungen, die sich gegenseitig fangen, sind kein
Problem, sondern der Beleg, dass beide etwas tun.

### Block 4, Teil 1 — T26-11 und N-03

**T26-11.** `vs_ges` kannte nur Stamm und Erhoehungen. Eine auf 67.606,49 EUR
herabgesetzte Police stand mit 100.000 EUR im Konto, und P-B1 bestaetigte es.
Der Grund ist die Klasse, nicht der Einzelfall: BEIDE SEITEN der Identitaet
liessen dieselbe fachliche Aenderung aus. Die Identitaet faengt so etwas
nie — sie hielt vorher genauso wie nachher.

Deshalb misst der Test gegen eine UNABHAENGIGE Quelle: die Einzelbewertung,
die den geknickten Verlauf kennt. Ihre Summe ueber die beitragspflichtigen
Vertraege ist der Endbestand, den das Konto ausweisen muss.

`vs_ges` fuehrt jetzt die Herabsetzung mit: Eine RED setzt die Summe ABSOLUT
neu (der Ledgerbetrag ist die neue Gesamtsumme, „fortgefuehrter plus
umgewandelter Teil"); Erhoehungen davor stecken in ihr, Erhoehungen danach
kommen obendrauf. Die zweite RED-Zeile `dDK_absorption` ist eine Umbuchung im
Deckungskapital und bleibt draussen.

**RICHTIGGESTELLT 2026-09-22 — keine fachliche Frage, keine Entscheidung.**
Die Aussage „die Herabsetzung HEBT die Versicherungssumme" war falsch.
Nachgemessen an Police 900002, Vertragsjahr 16, Anteil 0,6
(`kern.beitragsreduktion.reduziere`, mit und ohne `zusatz_dk`):

* OHNE Korrekturschicht: 100.000 -> **85.856** (60.000 fortgefuehrt +
  25.856 beitragsfrei). Die Herabsetzung SENKT, wie sie per Definition muss.
* MIT der Korrekturschicht des Fixtures: 113.642 — die gesamte Hebung
  (+27.787) ist die absorbierte Schicht (`dDK_absorption` 25.501).

Die Schicht des Fixtures ist unrealistisch: `_parameter(rho=0.04)` in
`tests/test_schicht_in_fuehrung.py`, darauf baut der T26-11-Test auf. Im
echten Fall (baldrian, 834 Vertraege, `abgeleitet/bestand/schichten.parquet`)
liegt `rho` bei 1e-8 bis 1e-9 — Rundungsresiduen, Cent-Betraege, genau
das, was der Entscheid vom 2026-09-15 meinte. Das Fixture ist rund vier
Millionen Mal groesser. Die +202.338 sind dieses Artefakt; ueber die
Wirklichkeit sagen sie nichts. Der Mechanismus (Schicht geht vollstaendig
in die Neuberechnung ein, Entscheid 2026-09-15) bleibt richtig; bei
Cent-Schichten hebt nichts.

Die Bewegungszeile `veraenderung_herabsetzung` traegt weiter ihr Vorzeichen
aus dem Kern; in der Wirklichkeit ist es negativ. Der Test bindet, DASS
die Aenderung gefuehrt wird — die Richtung bindet er auf diesem Fixture
nicht, weil dort die Schicht dominiert.

**Folgeauftrag (Maintainer 2026-09-22, nicht gebaut):** Das Fixture
fachlich vernuenftig ausgestalten — eine Schicht in realistischer
Groessenordnung (Rundungsresiduum), damit die Richtung der Herabsetzung
im Test bindbar wird (senkt) und die Frage bei der naechsten Pruefung
nicht wiederkommt. Die Mechanik-Probe der Absorption braucht weiter eine
sichtbare Schicht (bei 1e-8 saehe kein Test sie — Detektor ohne
Treffer); das sind zwei Fixtures, nicht eins.

**Gegen Rueckbau gesichert.** Zwei Tests: der Endbestand gegen die
Einzelbewertung (unabhaengige Quelle) und die Bewegung selbst (nicht null,
Stueck null, Identitaet in jedem Jahr). Dazu der N-03-Test, der das
Bewegungskonto auf JEDER Stichtagssicht rechnet — genau das, was der
Monatsbericht tut.

**Mutationsproben.** Populationsschnitt entfernt: der N-03-Test rot. RED in
`vs_ges` entfernt: beide T26-11-Tests rot.

### Block 3, Teil 3 — T26-05

**Der Befund.** Die Fuehrungsprobe verglich SECHS Identitaetsfelder
(`produkt`, `tarif_generation`, `date_of_birth`, `insurance_start`,
`entry_age`, `duration`). Eine von 43.000 auf 1.042.999 EUR erhoehte
Stammsumme lief durch die echte Probe und durch ihren A-M4-Consumer —
gruen, mit positivem Zaehler. Der Gutachter dazu: „Der positive Zaehler
sagt lediglich, dass eine Zeile auf sechs Attribute angesehen wurde. Er
bezeugt nicht die Uebereinstimmung des gefuehrten Vertrags."

**Die Klasse.** Eine handverlesene Liste dessen, was GEPRUEFT wird, veraltet
mit jeder neuen Spalte — und schweigt darueber. Gedreht wird die Richtung:
Benannt wird jetzt, was sich BEWEGEN darf.

Gemessen am gefahrenen Fall (500 Policen, achtzehn Stammspalten) aendert die
Fortschreibung GENAU DREI: `status_id`, `status_code`, `status_date`.
Erhoehungen leben in den Scheiben, die Herabsetzung im Ledger, die
beitragsfreie Summe in ihrer eigenen Spalte. Alles andere ist Identitaet und
wird verglichen — vierzehn Spalten statt sechs. Eine neue Stammspalte ist
damit von Anfang an geprueft.

**Gegen Rueckbau gesichert.** Ein parametrisierter Test verbiegt JEDE der
vierzehn Spalten im Endbestand des ECHTEN Laufs und verlangt, dass die Probe
faellt UND die Spalte im Befund nennt. Die unveraenderte Probe muss in
derselben Zeile bestehen — ohne diese Positivkontrolle waere eine Probe, die
alles ablehnt, nicht zu unterscheiden.

Dafuer ist das Material des echten Laufs in einen Helfer gewandert
(`_probe_material`). Ein Test, der sich seine Tabellen selbst hinlegt,
pruefte eine Welt, die der Lauf nie erzeugt hat — genau die Blindheit, an
der T25-02 haengen blieb.

**Mutationsprobe.** Zurueck auf die sechs Felder: ACHT der vierzehn Spalten
werden rot, die urspruenglichen sechs bleiben gruen. `sum_insured` — der
gemeldete Fall — ist unter den acht.

**Was darueber hinaus offen bleibt:** Der Gutachter nennt als Reparaturziel
zusaetzlich, den Soll-Endzustand aus Anfangszustand und Ereignisstrom
HERZULEITEN und gegen Endbestand, Historie, Scheiben und Ledger zu halten.
Die Buchungspruefung nach dem Stichtag tut das fuer die Buchungen bereits;
eine vollstaendige Herleitung des Endzustands ist nicht gebaut. Der gemeldete
Befund ist damit geschlossen, der weitergehende Anspruch nicht.

### Block 4, Teil 2 — T26-09

**Der Befund.** Der Konsument prueft `neugeschaeft.seit_betriebsbeginn`
gegen das Protokoll und `buchungen.gesamt`/`je_ereignis` gegen das Journal.
`neugeschaeft.woche`, `woche_summe` und `luecken` reichte er UNGEPRUEFT ins
veroeffentlichte Datenmodell weiter. Bei unveraendertem Journal,
unveraendertem Protokoll und korrekt externem, unveraendertem Anker liess
sich `woche_summe` auf 1.000.000 setzen und der Lueckenblock leeren.

Der oeffentliche Fallbericht baut seinen sichtbaren Lueckenblock aus genau
dieser Funktion: Ein geleerter Block verschweigt den
Image-Digest-Vorbehalt, den der Leser sehen soll.

**Die Klasse.** Dieselbe wie bei den Abschluessen (T24-04) und beim
Schichtbeleg (T26-06): Ein Wert, der weitergereicht statt abgeleitet wird,
ist eine Behauptung — auch wenn alles um ihn herum belegt ist. Der Anker
schuetzt die Kette, nicht jedes Feld in `stand.json`.

**Was gebaut ist.** Die Wochenableitung ist als
`seite.neugeschaeft_der_woche(journal, heute)` oeffentlich; Erzeuger und
Konsument rufen dieselbe Funktion. Der Lueckenausweis wird ueber
`seite.luecken(stand)` nachgerechnet. Beide Pruefungen stehen am ENDE der
Feldpruefung gegen das Protokoll — sonst faengt die abgeleitete Zahl einen
Befund ab, der einer bestimmten Protokollzeile gilt, und die Meldung
zeigte auf die falsche Stelle.

**Gegen Rueckbau gesichert.** Drei Manipulationen an `stand.json` allein:
`woche_summe` auf 1.000.000, `woche` durch eine erfundene Tagesreihe, und
der Lueckenblock geleert. Anker, Journal und Protokoll bleiben unangetastet
— genau die Lage des Gutachters.

**Mutationsprobe.** Beide Ableitungen ausgeschaltet: alle drei rot.

### Anmerkung zur Reihenfolge

Der Gutachter ordnet T26-04 vor T26-09 ein. Ich habe T26-09 vorgezogen,
weil bis zum Limit noch genau ein voller Suitenlauf Platz hatte und T26-04
eine Entwurfsentscheidung verlangt — ein enges, typisiertes Belegschema —,
die der Maintainer sehen sollte, bevor sie gebaut wird. Ein halb gebautes
T26-04 im Baum waere schlechter gewesen als ein geschlossenes T26-09.

### Block 4, Teil 3 — T26-12

**Der Befund.** `red_verfahren = 'teilkuendigung'` ist ein erlaubter
Schalter, die integrierte TG2015 traegt ihn, und `cfg.validate()` meldete
nichts. Der produktive Fortschreibungslauf scheitert dann beim ERSTEN
Vorfall: Er ruft grundsaetzlich `reduziere_geschichtet()`, und das
verweigert die Teilkuendigung auch ohne Schicht und ohne
Erhoehungsscheiben — „Teilkuendigung trifft NUR die Grundversicherung".

**Was gebaut ist.** Die Kombination wird VOR Laufbeginn abgewiesen, mit
einer Meldung, die den Ausweg nennt. Eine gueltige Config, die im Lauf
abbricht, ist keine gueltige.

**WARUM NICHT DIE ANDERE MOEGLICHKEIT.** Der Gutachter laesst beide zu:
„Zusage und produktiven Tarifwerkspfad konsistent implementieren ODER die
nicht tragfaehige Kombination vor Laufbeginn ausdruecklich abweisen und
dokumentieren." Die erste ist keine Reparatur, sondern eine fachliche
Entscheidung — und sie steht gegen einen WIDERSPRUCH IN UNSERER EIGENEN
DOKUMENTATION:

* `docs/tarifplaene/klv.md:165-175` sagt, die Fuehrung lese alle drei
  uebernommenen Tarifwerkschalter, diesen eingeschlossen.
* `kern/beitragsreduktion.py` erklaert das Verfahren zur Rekonstruktion der
  QUELLE und schliesst es fuer die eigene Fuehrung aus.

**FRAGE AN DAS AKTUARIAT:** Welcher der beiden Saetze gilt? Soll die
Fuehrung die Teilkuendigung fahren koennen — dann ist es ein Bauauftrag
(der produktive Pfad braucht einen Zweig fuer den Grundvertrag ohne
Scheiben-Teilung) —, oder gilt der Kernkommentar, dann gehoert der
Widerspruch aus dem Tarifplan entfernt. Bis dahin ist die Kombination
abgewiesen und niemand faehrt versehentlich in den Abbruch.

**AUFGELOEST 2026-09-22 (Maintainer) — als KLASSE, nicht als Einzelfall;
nichts davon gebaut.** Die Frage „welcher Satz gilt" war falsch gestellt.
Die Teilkuendigung ist das VERTRAGLICHE Verfahren der TG2015
(Bedingungswerk Ziffer 6, A-M3-Befund des zweiten Laufs); nach der
Uebernahme muss das Zielsystem die Vertraege nach ihrem Bedingungswerk
fuehren. Das „nicht vorgesehen" im Kern war Unfertigkeit, kein Design;
der Tarifplan (klv.md:165-175) ist der Vertrag und hat recht. Die Luecke
ist heute nur latent (herabsetzung.a = 0.0 in beiden echten Configs).

Die Klasse: Ein uebernommener Bestand bringt ein Tarifwerks-Merkmal mit,
das der produktive Pfad nicht ausfuehren kann. Heute gibt es drei Mengen,
zwei werden geprueft: (1) BEKANNT — config.py:436 prueft `red_verfahren
in VERFAHREN` (drei Werte); (2) UEBERTRAGEN — `tarifwerk_fehler`
(uebernahme.py:693) prueft Config == Uebernahmebeleg; (3) PRODUKTIV
AUSFUEHRBAR — `reduziere_geschichtet` kann nur zwei der drei, und NIEMAND
prueft Config ⊆ ausfuehrbar. Durch dieses Loch fiel die Teilkuendigung;
durch dasselbe faellt jeder kuenftige Schalterwert, den das Zielsystem
nicht kann. Der Wachposten oben kennt genau EIN Merkmal, und sein Ausweg
(„red_verfahren umstellen") ist falsch: Er hiesse, migrierte Vertraege
nach einem Verfahren zu fuehren, das nicht ihres ist.

Was sich aendert (Bauauftraege, in dieser Reihenfolge):

1. **Ratsche (die Klasse):** je Schalter EINE Deklaration dessen, was der
   produktive Pfad ausfuehrt; bei Freischaltung/Config-Validierung die
   Pruefung „jeder Schalterwert jeder uebernommenen Generation ist
   ausfuehrbar, sonst Migration blockiert mit benanntem Bauauftrag"; ein
   Test, dass die Deklaration zum Code passt. Generisch — faengt das
   naechste Merkmal ohne neuen Wachposten.
2. **Teilkuendigung im produktiven Pfad** (die erste Instanz, die die
   Ratsche anzeigt): eigener Zweig fuer den Grundvertrag ohne
   Scheiben-Teilung, Spezifikation aus Bedingungswerk Ziffer 6 /
   A-M3-Befund, mit aktuarieller Abnahme. Bis dahin blockiert die Ratsche
   TG2015 fuer Herabsetzungen — richtig so.
3. Der Ausweg des Wachpostens (config.py:1055) wird zu „Faehigkeit fehlt —
   Bauauftrag", nie „Config anpassen"; der Kernkommentar „nicht
   vorgesehen" faellt mit 2.

Entdecken bleibt Aufgabe von A-M1/2/3 (Quelle gegen Ziel auf echten
Vertraegen — so wurde die Teilkuendigung gefunden); Erzwingen macht die
Ratsche. Zusammen ist die Klasse zu.

**Reichweite heute:** Die unveraenderte PLV-Config hat Rate und `red_anteil`
null; kein aktueller Ausfall. Der Schalter ist aber erlaubt, und wer ihn
setzt, bekam bisher einen Abbruch mitten im Lauf statt einer Meldung davor.

**Gegen Rueckbau gesichert.** Vier Lagen als Tabelle, beide Richtungen: das
Verfahren MIT Rate faellt, das Verfahren OHNE Rate nicht, und die beiden
erlaubten Verfahren bleiben mit Rate erlaubt. Dazu die Forderung, dass die
Meldung einen Ausweg nennt.

**Mutationsprobe.** Pruefung entfernt: genau die eine Lage rot.

### Block 3, Teil 4 — T26-04

**Der Befund.** Ein vollstaendig selbst geschriebener Beleg kam durch:
fuenf Dateien mit gewoehnlichem Text statt Parquet, `bestanden = true`,
`befunde = []`, positive Zaehler `vertraege = 1` und
`endbestand_geprueft = 1` — und alle uebrigen geforderten Felder
vorhanden, aber `null`. Der echte A-M4-Consumer nahm ihn an.

Der Fix von T25-01 hatte die Zaehler verlangt, aber nicht GEBUNDEN. Der
Gutachter dazu: „Zaehler und Feldnamen lassen sich genauso frei schreiben
wie `bestanden`."

**Was gebaut ist — die Zaehler haengen jetzt an den Bytes.**

1. `vertraege` wird gegen die ZEILENZAHL der gebundenen
   `<uebernahme>/bestand.parquet` gehalten. Wer zaehlen muss, muss lesen —
   damit faellt derselbe Beleg zweimal: am Zaehler und daran, dass Text
   kein Parquet ist. Eine eigene Formatpruefung braucht es nicht.
2. `endbestand_geprueft` darf die Zahl der uebernommenen Vertraege nicht
   uebersteigen.
3. Die BESCHREIBENDEN Felder (`stichtag`, `generation`, `tarifwerk`) sind
   aus der Liste heraus, deren Vertrag `null` ausdruecklich zulaesst, und
   duerfen nicht leer sein; `tarifwerk` muss ein Objekt sein. Fuer die
   Zaehler bleibt `null`/`0` erlaubt — ein Horizont ohne Ereignisse hat
   null gepruefte Buchungen, und das ist eine Aussage.

**Eine Architekturgrenze dabei, die beachtet wurde:** Der erste Entwurf las
die Tabelle ueber `bestand.parquet_io` — und die Ratsche
`TOOL_NACH_VORZEIGE_ERLAUBT` (ADR-017) hat die neue Kante abgewiesen, zu
Recht. Das KI-Tool spricht das Zielsystem nur ueber die gemessene
Schnittstelle an; fuer `gates.abnahmebericht` ist diese Tuer
`bestand.vorbedingungen`. Die Zeilenzahl kommt jetzt von dort.

**Gegen Rueckbau gesichert.** Sechs Selbstbehauptungen als Tabelle — der
Gutachter hat EINE vorgefuehrt, hier steht die Familie — plus ein Test, der
die gebundene Tabelle durch Text ersetzt UND den Hash im Beleg nachzieht,
damit nicht der Hashvergleich anschlaegt, sondern die Frage, ob die Datei
eine Bestandstabelle ist.

**Mutationsprobe.** Zaehlerbindung und Leerpruefung ausgeschaltet: vier der
sieben rot.

### Block 4, Teil 4 — T26-10

**Der Befund.** Zwei autonom gueltige Generationen, zu einem Stand
vermischt, den es nie gab. Der Gutachter hat die natuerliche
Scheduling-Naht getroffen: unmittelbar NACH dem Lesen des alten Manifests
einen zweiten, voellig regulaeren Tageslauf gestartet. Der aeussere Leser
behielt alte Protokollzeile und altes Manifest im Speicher und las das
gerade veroeffentlichte NEUE Journal.

Gemessen: `mixed_model_date 2026-02-03`, `actual_stand_date 2026-02-10`,
`mixed_last_booking_date 2026-02-10`, `mixed_pb1 gruen`,
`mixed_journal_hash_matches False`. Die Seite nannte einen Tag, zeigte die
Buchungen eines anderen und einen Hash, der zu keinem von beiden passte.

**Warum keine Sperre.** Der Gutachter laesst beides zu — einmal lesen und
weiterreichen ODER Reader und Export ueber dieselbe Lauftransaktion sperren.
Eine Sperre schuetzt den Weg, den sie umschliesst; sie haette den
standalone-Seitenleser gebraucht, den Export, und jeden kuenftigen
Konsumenten. Die geprueften BYTES weiterzureichen schuetzt jeden, der die
Pruefung durchlaeuft — und niemand wertet aus, ohne sie zu durchlaufen.

**Was gebaut ist.** `pruefe_nachweis` gibt die geprueften Bytes von Manifest
und Journal zurueck, statt sie nach dem Hashen wegzuwerfen. `stand_modell`
liest daraus, nicht erneut von der Platte. Das Stands-Paket schreibt
Manifest und Journal aus denselben Bytes — vorher kopierte es sie noch
einmal, und zwischen Pruefung und Kopie passt derselbe Tageslauf. Das
Protokoll bleibt eine Kopie: Es ist nur anfuegbar, und seine Kette prueft
der Konsument selbst.

**Gegen Rueckbau gesichert.** Ein Test trifft dieselbe Naht — der zweite
Lauf startet aus dem Inneren der Nachweispruefung heraus, also genau
zwischen Pruefung und Auswertung. Geprueft wird dreierlei: Die Seite nennt
ihren Tag, ihre Provenienz nennt den Journalstand, den sie ausgewertet hat,
und ihre Buchungen enden nicht nach ihrem eigenen Stand. Dazu zwei
Positivkontrollen: Der zweite Lauf MUSS gelaufen sein, und er MUSS das
Journal veraendert haben — sonst traegt die Naht nicht.

**Mutationsprobe.** Das Journal wieder von der Platte gelesen: Der Test
faellt mit genau der Messung des Gutachters — Buchungen bis 2026-02-10 neben
einem Modell, das 2026-02-03 nennt.


---

## Was NICHT zu dieser Runde gehoert

Der PEX-Zuschlag der Uebernahme und das Laufmanifest des
Migrationszugangs sind keine Befunde des Gutachters. Sie kamen aus dem
Blocker der Vorzeige-Laufzeit und aus dem Manifest-Entscheid des
Maintainers vom 2026-09-16. Sie standen bis zum 2026-09-21 hier
angehaengt und haben damit zwei Gegenstaende in einem Dokument
vermischt; sie stehen jetzt vollstaendig in
`dev-docs/annahmen-2026-09-20.md`, zusammen mit den Entscheidungen D1
bis D4 und den Nebenentscheidungen N1 bis N5.

Beruehrungspunkt, damit beim Lesen nichts fehlt: Der Fall
`baldrian-klv-tg2015-lauf2` ist inzwischen auf einem spaeteren Stand neu
gefahren und gezeichnet. Die Befunde dieser Runde sind davon nicht
betroffen; die Zahlen in den Abschnitten oben gelten fuer den Stand, auf
dem sie gemessen wurden, und der steht dort jeweils dabei.
