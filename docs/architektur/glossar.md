# Glossar

Die Begriffe, mit denen Code, Dokumentation und Belege arbeiten, in
alphabetischer Reihenfolge. Kennungen wie `A-M4` sind Namen von Gates;
ihre Ordnung steht in [ADR-012](adr-012-gate-namensordnung.md).

### A-Box

Die Aussagen über einen konkreten Tarif, die ein Fall aus seinen Quellen
gewinnt. Jede Aussage nennt ihre Herkunft: Datei, Prüfsumme, Fundstelle.
Das Vokabular dafür liefert die [T-Box](#t-box).

### Ablage

Das Datenverzeichnis, in dem die PLV Tag für Tag geführt wird: der Bestand,
das Journal der Geschäftsvorfälle, die [Abschlüsse](#abschluss) und die
Berichte.

### Abnahme

Ein menschliches [Gate](#gate): Ein Mensch nimmt einen Stand an oder lehnt
ihn ab und zeichnet seinen Entscheid.

### Abschluss

Der festgeschriebene Bestand zu einem Monatsersten. Er wird einmal
geschrieben und danach nie überschrieben. Berichte rechnen jederzeit neu,
Abschlüsse nicht.

### Agent

Ein KI-Werkzeug (Claude Code oder Codex) in einer festgelegten Rolle, etwa
Aktuariat, Architektur oder Betrieb. Agenten bereiten vor und legen vor.
Eine Abnahme zeichnen dürfen sie nicht, ein menschliches Gate können sie
nur ablehnen. Zeichnen dürfen sie nur Urheberschaft, etwa den Ankersatz
eines Stands-Pakets. Die Rollen beschreibt
[skill-architektur.md](skill-architektur.md).

### Anker

Ein Satz, den der Export eines [Stands-Pakets](#stands-paket) außerhalb
des Pakets ablegt (`--anker`, Datei `anker.jsonl`). Er bindet das Paket an
einen Ort, den der Tagesbetrieb nicht anfasst: Ein Paket, das nur sich
selbst belegt, könnte seine Herkunft behaupten.

### Auslieferung

Geht ein Stand der [Ablage](#ablage) nach außen, zum Beispiel für die
Vorzeigeseite, zeichnet der Betrieb die Auslieferung (`A-B1`).

### Diskrepanz

Ein Widerspruch zwischen zwei Quellen. Er wird mit beiden Lesarten und
ihren Belegen festgehalten und nie still aufgelöst. Ein Mensch entscheidet
ihn am Gate `A-Q1`.

### Ebene

Die Gliederung aus ADR-017: die Entwicklung (Entwickler und KI), das
Migrationssystem, die [Vorzeige](#vorzeige) und die Werkzeuge, mit denen
die Vorzeige hergestellt wird. In ADR-017 und ADR-018 heißt das
Migrationssystem „KI-Tool“. Seit ADR-028 ordnen die Ebenen auch den Baum:
System, Objekt PLV, Objekt Baldrian bzw. Migration, Simulation und
Laufzeit-Artefakte. Die Ebenen der Module misst weiter die Schichtenkarte
(`ontologie.code_karte`).

### Erstabnahme

Die einmalige Abnahme des Zielsystems außerhalb jedes Falls: Kernstand,
T-Box-Stand, Tarifwerk und Anfangsbestand der Ablage. Ein Fall zeichnet
danach nur, was er selbst ändert, und verweist sonst auf die Erstabnahme
([ADR-025](adr-025-erstabnahme-des-zielsystems.md)).

### Fall

Eine Übernahme, von der Lieferung bis zum Zugang in die Ablage. Ein Fall
lebt in einem Arbeitsbereich `faelle/<name>/` mit drei Teilen: `eingang/`
(die registrierte Lieferung, unveränderlich), `abgeleitet/`
(reproduzierbare Ergebnisse) und `entscheide/` (die gezeichneten Belege).
Der Arbeitsbereich liegt im Klon, ist aber nicht eingecheckt
([ADR-002](adr-002-fall-arbeitsbereich.md)). Gelöscht wird ein Fall nie;
nicht mehr gebrauchte Fälle wandern nach `faelle/archiv/`.

### Fallauftrag und Fallabbruch

Den Fall beauftragt der Vorstand (`A-M6`), nachdem die Lieferung
registriert ist. Scheitert der Fall, endet er mit dem Abbruch, den die
Programmleitung zeichnet (`A-M5`)
([ADR-026](adr-026-lebenslauf-eines-falls.md)).

### Führungsprobe

Prüft, ob der geführte Bestand mit derselben Rechnung arbeitet wie die
Prüfstrecke der Abnahmen: den Anfangszustand je Vertrag und jede Buchung
der Fortschreibung bis zum Folgestichtag (`gates.fuehrungsprobe`). Im
Bestands-Scope ist sie ein Pflichtbeleg der Migrationsabnahme.

### Gate

Ein Prüfpunkt. Es gibt zwei Arten:

- **Prüf-Gates** (Kennung `P-…`, etwa `P-Q1`, `P-K1`) sind Kommandos. Sie
  prüfen deterministisch, schreiben ein [Ledger](#ledger) und blockieren
  mit einem Exit-Code ungleich null.
- **Menschliche Gates** (Kennung `A-…`, etwa `A-Q1`, `A-M4`) sind
  Abnahmen. Ein Mensch zeichnet sie mit seinem [Schlüssel](#schlüssel).

### Kernstand

Der abgenommene Stand des Rechenkerns: sein Code, die eingefrorenen
Referenzwerte und die Grundsatzdokumentation. Ein Fall, der den Kern ändert,
lässt den neuen Kernstand abnehmen (`A-K2`). Die Abnahme bindet den Stand
über Prüfsummen.

### Knoten

Die fachliche Kennung, an die Code, Tests und Aussagen gebunden sind, etwa
`klv/tg2015` für eine Tarifgeneration der KLV. Jedes Modul und jeder Test
nennt seinen Knoten ([ADR-005](adr-005-knoten-hierarchie-und-impact.md)).

### Ledger

Die JSON-Datei, die ein Prüf-Gate über seinen Lauf schreibt
(`<kommando>.gate.json`): Eingaben mit Prüfsummen, Ergebnis, Version des
Gates.

### Lieferung

Die Dateien, die die abgebende Gesellschaft schickt: Tarifrechner,
Tarifbeschreibung, Bedingungen, Bestandsabzüge, Erwartungswerte. Die
Lieferungen der Vorführung liegen unter `migrationen/baldrian/lieferungen/`.

### Linie

Ein Verzeichnis außerhalb jedes Falls und außerhalb des Repositorys (in
einer Welt `<welt>/linie`). Es trägt die Fassungen der
[Zeichnungsordnung](#zeichnungsordnung) in ihrer Reihenfolge und die
[Erstabnahmen](#erstabnahme). Jede Fassung heißt **Glied**; das jüngste
Glied ist die **Spitze**. Das erste Glied legt ein Mensch außerhalb jedes
Gates an; es ist unsigniert und die Vertrauenswurzel der Linie. Jedes
weitere Glied zeichnet der Vorstand, die **Wurzelrolle**. Jeder Entscheid
nennt die Linie und das Glied, unter dem er gezeichnet wurde.

### Mandat

Das Dokument, mit dem die Leitung einer [Vorführung](#vorführung) einer
simulierten Rolle das Zeichnen überträgt. Seine Prüfsumme steht in jeder
Zeichnung dieser Rolle (Vorlage `werkzeuge/welt/mandat.vorlage.txt`,
[ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)).

### Migrationsabnahme

Die Abnahme der Übernahme als Ganzes (`A-M4`). Grundlage ist der
Abnahmebericht: das Deckungskapital an zwei Stichtagen und die
Geschäftsvorfälle dazwischen, geprüft gegen die gelieferten Erwartungswerte.
Vorher stehen drei aktuarielle Tests je Vertrag: Stichtagstest (`A-M1`),
Verlaufstest (`A-M2`) und Geschäftsvorfalltest (`A-M3`).

### Migrationssuite

Die Abnahmetests des Migrationscontrollings, auf denen die
Migrationsabnahme steht: Deckungskapital an zwei Stichtagen, Jahresbeitrag
und Geschäftsvorfälle je Vertrag, gegen die gelieferten Erwartungswerte
(`qa.migrationssuite`).

### Nachfahren

Einen abgeschlossenen Fall aus seinem [Paket](#paket) ohne Agenten
wiederholen. Die Ergebnisse müssen Byte für Byte mit dem Original
übereinstimmen.

### Paket

Ein abgeschlossener Fall zum [Nachfahren](#nachfahren), abgelegt unter
`pakete/`: das Rezept der Schritte, die Nachlieferungen, die im Fall
erarbeiteten Dateien und die erwarteten Prüfsummen. Schlüssel und
Zeichnungen enthält es nicht; wer nachfährt, zeichnet selbst.

### PLV und Baldrian

Die erfundenen Unternehmen der Vorführung. Die Pfefferminzia
Lebensversicherung (PLV) ist das Zielsystem und übernimmt. Die Baldrian
Lebensversicherung a. G., kurz Baldrian Leben, gibt ihren Bestand ab.

### Provenienz

Die Herkunft einer Aussage oder eines Ergebnisses: aus welcher Datei mit
welcher Prüfsumme, von welchem Werkzeug, auf welchem Code-Stand.

### Prüfrunde

Eine unabhängige Durchsicht eines Bauabschnitts vor dem Merge. Prüfer
suchen Fehler, jeder Fund wird gegen den Code bestätigt oder widerlegt, und
bestätigte Funde werden behoben. Die Runden tragen Buchstaben (G bis J),
ihre Funde Buchstabe und Nummer (etwa G14). Ältere Durchsichten des
Gesamtstands tragen ein T und eine Nummer (etwa T22), ihre Funde
zusätzlich eine laufende Nummer (Befund T22-02); die Runden G bis J
gehören zur Durchsicht T27. Unter diesen Kennungen verweisen ADRs, Code
und Tests auf die Regeln, die eine Runde hinzugefügt hat.

### Regie

Die Spielleitung einer [Vorführung](#vorführung): Drehbücher und die
Auflösungen der noch nicht gefahrenen Fälle. Sie liegt nicht im
Repository; die Auflösung eines gefahrenen Falls steht in seinem
[Paket](#paket).

### Registrieren

Der einzige Weg einer Datei in einen Fall.
`python -m rechner_pipeline.fall registrieren` kopiert sie nach `eingang/`,
hält ihre Prüfsumme fest und setzt sie schreibgeschützt.

### Ring

Die Schlüssel, die ein Aufruf mitbringt (`--freigabe-schluessel`,
mehrfach): zuerst die, mit denen er fremde Signaturen prüft, zuletzt der
zeichnende. Die Signatur ist symmetrisch (HMAC): Wer einen Schlüssel im
Ring hält, kann mit ihm auch zeichnen.

### Schlüssel

Jede Rolle zeichnet mit einem eigenen Schlüssel. Seine Klasse sagt, wer
dahinter steht: ein Mensch (`mensch`), eine Vorführung (`simulation`), ein
Agent (`agent`) oder der Tageslauf des Betriebs (`betrieb`). In der
Vorführung tragen die menschlichen Rollen die Klasse `simulation`, und
jeder Beleg sagt das
([ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)).

### Spez

Die Parametrierung eines Tarifs für den Rechenkern. Sie wird aus der
abgenommenen [A-Box](#a-box) abgeleitet.

### Stand

Ein Code-Stand, benannt durch seinen Commit. Belege halten fest, auf welchem
Stand sie entstanden sind.

### Stands-Paket

Der Export der geführten [Ablage](#ablage) für die Webseite
(`python -m rechner_pipeline.betrieb.seite --paket`): die Tagesseite
„Bestand heute“, die Berichte der Abschlüsse und `stand.json` mit der
Prüfsumme jeder Datei. Ein Paket, dessen Stand nicht durch P-B1 ging,
weisen die Werkzeuge der Seite ab.

### T-Box

Das Vokabular, in dem die A-Box Tarife beschreibt: welche Merkmale es gibt
und welche Werte sie annehmen dürfen. Es ist versioniert und wird am Gate
`A-O1` abgenommen.

### Tagesbetrieb

Die PLV wird jeden Tag fortgeschrieben: Neugeschäft, Geschäftsvorfälle,
Journal und zum Monatsersten ein [Abschluss](#abschluss). Das Konzept steht
in [docs/simulation/tagesbetrieb.md](../simulation/tagesbetrieb.md).

### Tarifwerk

Was die PLV ihren Kunden verspricht und wie sie es parametriert: die
Tarifpläne unter `docs/tarifplaene/` und die eigenen Generationen in den
Bestands-Configs. Abgenommen wird es am Gate `A-T1`, gebunden über
Prüfsummen.

### Vorführung

Ein Fall oder Betrieb, in dem die menschlichen Rollen simuliert sind, etwa
für die Vorzeigeseite oder beim [Nachfahren](#nachfahren). Die Rollen
zeichnen dann mit Schlüsseln der Klasse `simulation` unter einem
[Mandat](#mandat).

### Vorverdichtung

Der erste, deterministische Schritt je Quelle: Excel-Mappen über das Gate
`P-Q1` (`gates.extract`), Word und Text-PDF über
`quellen.tarifplan_staging`, CSV-Bestandsabzüge über
`quellen.bestand_profil`. Die Inhalte werden in lesbare Teile zerlegt,
bevor ein Agent sie liest.

### Vorzeige

In ADR-017 und älteren Dokumenten das fiktive Unternehmen PLV mit
Rechenkern, Produkten, Bestand und Bestandsführung, an dem sich das
Migrationssystem zeigt (siehe [Ebene](#ebene)). Die Vorzeigeseite ist
seine Webseite.

### Welt

Alles, was neben dem Code nötig ist, damit die PLV läuft und ein Fall
geführt werden kann: die [Ablage](#ablage), die [Linie](#linie), die
Schlüssel der Rollen und die Zeichnungsordnung. Je Fall gibt es eine eigene
Welt, damit kein Fall die Laufzeit eines anderen berührt. Aufgestellt wird
sie mit den Routinen unter `werkzeuge/welt/`. Der Arbeitsbereich des Falls
liegt nicht in der Welt, sondern im Klon.

### Zeichnen

Einen menschlichen Entscheid festhalten. Das Ergebnis ist ein Snapshot im
Fall: Gegenstand, Entscheid, Begründung und die Prüfsummen der Belege,
signiert mit dem Schlüssel der Rolle. Ein Snapshot wird nie geändert.

### Zeichnungsordnung

Die Datei, die festlegt, welche Rolle mit welchem Schlüssel welche Gates
zeichnen darf. Ihre Fassungen stehen in der [Linie](#linie)
([ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)).

### Zugang

Der Weg des übernommenen Bestands in die [Ablage](#ablage): eine Probe (auf
einer Kopie der laufenden Ablage; wird die Ablage neu aufgesetzt, auf einem
leeren Verzeichnis), die Abnahme durch den Betrieb (`A-B2`), danach die
Registrierung oder das Neuaufsetzen der Ablage mit der Abnahme ihres
Anfangsbestands (`A-B3`) ([ADR-022](adr-022-zugangsabnahme-a-b2.md)).
