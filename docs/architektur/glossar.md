# Glossar

Die Begriffe, mit denen Code, Dokumentation und Belege arbeiten, in
alphabetischer Reihenfolge. Kennungen wie `A-M4` sind Namen von Gates;
ihre Ordnung steht in [ADR-012](adr-012-gate-namensordnung.md).

### A-Box

Die Aussagen über einen konkreten Tarif, die ein Fall aus seinen Quellen
gewinnt. Jede Aussage nennt ihre Herkunft: Datei, Prüfsumme, Fundstelle.
Das Vokabular dafür liefert die [T-Box](#t-box).

### Abnahme

Ein menschliches [Gate](#gate): Ein Mensch nimmt einen Stand an oder lehnt
ihn ab und zeichnet seinen Entscheid.

### Ablage

Das Datenverzeichnis, in dem die PLV Tag für Tag geführt wird: der Bestand,
das Journal der Geschäftsvorfälle, die [Abschlüsse](#abschluss) und die
Berichte.

### Abschluss

Der festgeschriebene Bestand zu einem Monatsersten. Er wird einmal
geschrieben und danach nie überschrieben. Berichte rechnen jederzeit neu,
Abschlüsse nicht.

### Agent

Ein KI-Werkzeug (Claude Code oder Codex) in einer festgelegten Rolle, etwa
Aktuariat, Architektur oder Rechenkern. Agenten bereiten vor und legen
vor. Zeichnen dürfen sie nicht; ein menschliches Gate können sie nur
ablehnen. Die Rollen beschreibt [skill-architektur.md](skill-architektur.md).

### Auslieferung

Geht ein Stand der [Ablage](#ablage) nach außen, zum Beispiel für die
Vorzeigeseite, zeichnet der Betrieb die Auslieferung (`A-B1`).

### Diskrepanz

Ein Widerspruch zwischen zwei Quellen. Er wird mit beiden Lesarten und
ihren Belegen festgehalten und nie still aufgelöst. Ein Mensch entscheidet
ihn am Gate `A-Q1`.

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
Der Arbeitsbereich liegt nicht im Repository
([ADR-002](adr-002-fall-arbeitsbereich.md)).

### Fallauftrag und Fallabbruch

Ein Fall beginnt mit dem Auftrag des Vorstands (`A-M6`). Scheitert er,
endet er mit dem Abbruch, den die Programmleitung zeichnet (`A-M5`)
([ADR-026](adr-026-lebenslauf-eines-falls.md)).

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
Lieferungen der Vorführung liegen unter `lieferungen/`.

### Linie

Ein Verzeichnis außerhalb jedes Falls. Es trägt die Fassungen der
[Zeichnungsordnung](#zeichnungsordnung) in ihrer Reihenfolge und die
[Erstabnahmen](#erstabnahme). Jeder Entscheid nennt die Linie, auf die er
sich bezieht.

### Migrationsabnahme

Die Abnahme der Übernahme als Ganzes (`A-M4`). Grundlage ist der
Abnahmebericht: das Deckungskapital an zwei Stichtagen und die
Geschäftsvorfälle dazwischen, geprüft gegen die gelieferten Erwartungswerte.
Vorher stehen drei aktuarielle Tests je Vertrag: Stichtagstest (`A-M1`),
Verlaufstest (`A-M2`) und Geschäftsvorfalltest (`A-M3`).

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
Leben gibt ihren Bestand ab.

### Provenienz

Die Herkunft einer Aussage oder eines Ergebnisses: aus welcher Datei mit
welcher Prüfsumme, von welchem Werkzeug, auf welchem Code-Stand.

### Registrieren

Der einzige Weg einer Datei in einen Fall.
`python -m rechner_pipeline.fall registrieren` kopiert sie nach `eingang/`,
hält ihre Prüfsumme fest und setzt sie schreibgeschützt.

### Schlüssel

Jede Rolle zeichnet mit einem eigenen Schlüssel. Seine Klasse sagt, wer
dahinter steht: ein Mensch (`mensch`), eine Vorführung (`simulation`) oder
ein Agent (`agent`). In der Vorführung tragen die menschlichen Rollen die
Klasse `simulation`, und jeder Beleg sagt das
([ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)).

### Spez

Die Parametrierung eines Tarifs für den Rechenkern. Sie wird aus der
abgenommenen [A-Box](#a-box) abgeleitet.

### Stand

Ein Code-Stand, benannt durch seinen Commit. Belege halten fest, auf welchem
Stand sie entstanden sind.

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

### Vorverdichtung

Der erste, deterministische Schritt je Quelle (Gate `P-Q1`). Inhalte aus
Excel, Word oder PDF werden in lesbare Teile zerlegt, bevor ein Agent sie
liest.

### Welt

Alles, was neben dem Code nötig ist, damit die PLV läuft und ein Fall
geführt werden kann: die [Ablage](#ablage), die [Linie](#linie), die
Schlüssel der Rollen und die Zeichnungsordnung. Je Fall gibt es eine eigene
Welt, damit er wiederholbar bleibt. Aufgestellt wird sie mit den Routinen
unter `deploy/welt/`.

### Zeichnen

Einen menschlichen Entscheid festhalten. Das Ergebnis ist ein Snapshot im
Fall: Gegenstand, Entscheid, Begründung und die Prüfsummen der Belege,
signiert mit dem Schlüssel der Rolle. Ein Snapshot wird nie geändert.

### Zeichnungsordnung

Die Datei, die festlegt, welche Rolle mit welchem Schlüssel welche Gates
zeichnen darf. Ihre Fassungen stehen in der [Linie](#linie)
([ADR-018](adr-018-rollenmodell-und-schluesselklassen.md)).

### Zugang

Der Weg des übernommenen Bestands in die [Ablage](#ablage): eine Probe auf
einer Kopie, die Abnahme durch den Betrieb (`A-B2`), das Neuaufsetzen der
Ablage und die Abnahme ihres Anfangsbestands (`A-B3`)
([ADR-022](adr-022-zugangsabnahme-a-b2.md)).
