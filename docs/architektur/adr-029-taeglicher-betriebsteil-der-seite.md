# ADR-029: Der tägliche Betriebsteil der Seite

**Status:** angenommen. Die Grundzüge entschied der Maintainer am
2026-10-09: eigenes Repository `plv-fiktion`, Weg (C), A-B1 nur im
Betriebsteil, Takt 23:30, A-B1 durch die Routine mit dem
Simulationsschlüssel von `mensch/betrieb`. Die fünf Einzelfragen unter
„Einzelentscheide“ entschied er am 2026-10-15, alle wie empfohlen; die
fünfte (e) hatte sich erst bei der Umsetzung ergeben. Was umgesetzt ist,
steht unter „Folgen“.

## Kontext

Seit dem 2026-10-09 erscheint die Seite der Pfefferminzia im eigenen
öffentlichen Repository `bartlmac/plv-fiktion`, gebaut von GitHub Pages
über Actions. Sie ist eine feste Momentaufnahme: Sie zeigt den Stand des
Betriebs vom 2026-10-08, obwohl die Laufzeit `~/apps/plv` jeden Abend um 23:00 einen
Tag weiterführt (gemessen am 2026-10-15: jeder Tageslauf vom 09.10. bis
14.10. übernommen, P-B1 ohne Befund, Image `3ff625f83e8b`). Damit die
Seite mitwandert, muss heute ein Mensch exportieren, A-B1 zeichnen, bauen
und schieben.

Der Grundsatz des Maintainers vom 2026-10-09 lautet: Automatisch
veröffentlicht wird nur, was der Betriebsdienst erzeugt. Alles andere
kommt per Pull Request nach `plv-fiktion`, und den merged der Maintainer.

Zwei Eigenschaften des bestehenden Aufbaus bestimmen die Lösung:

* Das Stands-Paket ist der Nachweis, der Auftritt ist die
  Veröffentlichung (Fachkonzept Tagesbetrieb, Abschnitt 8.3). Tagesjournal
  und Monatsabschlüsse tragen Policennummern und werden nicht
  veröffentlicht. Bis Paketschema 5 rechnete der Bau der Seite die
  Geschäftsentwicklung und die Kennzahlen der Abschlüsse aus genau diesen
  Dateien. Wer nur die öffentlichen Dateien hat, konnte die Seite also
  nicht bauen.
* Die Auslieferungsabnahme A-B1 bindet den Ankersatz des Pakets, nicht
  `stand.json`. Bis Ankerschema 3 band der Satz die Dateiliste des Pakets,
  aber nicht `stand.json` selbst. Jede Zahl darin war nur nachrechenbar,
  solange Journal und Abschlüsse dabeilagen.

## Entscheidung

Der Server schiebt Daten, GitHub prüft und rendert sie mit festgelegtem
Code.

**Auf dem Server, 23:30.** Ein Timer `betrieb-seite.timer` startet eine
Routine. Sie hält bei jedem Fehler an und schiebt dann nichts:

1. Prüfen: Der Tageslauf hat den heutigen Tag übernommen, und die Revision
   des Laufzeit-Images ist der Code-Stand, mit dem `plv-fiktion` rendert
   (`CODESTAND` in `main`).
2. Exportieren (`python -m rechner_pipeline.betrieb.seite --auslieferung`)
   mit dem Anker im Fall-Datenraum, im Laufzeit-Image, ohne Netz.
3. A-B1 zeichnen (`gates.gate_entscheid --gate A-B1`) mit dem
   Simulationsschlüssel von `mensch/betrieb`, unter dem Mandat der
   simulierten Rolle (ADR-018), im Laufzeit-Image, ohne Netz. Die Seite
   weist die Zeichnung als Simulation aus.
4. Den Zweig `betrieb` eines Klons von `plv-fiktion` füllen: `paket/` mit
   den öffentlichen Dateien des Pakets, `anker.jsonl` und `A-B1.json`,
   sonst nichts. Ein Commit, Push mit dem Deploy-Key.

**In `plv-fiktion`.** `main` trägt den Rahmen, den Workflow und `CODESTAND`
und ändert sich nur per Pull Request. `betrieb` trägt nur die Daten des
Abends. Der Workflow läuft bei Push auf `main`, von Hand und nach
Zeitplan (nachts mehrmals, weil GitHub Zeitpläne verzögert), nie bei Push
auf `betrieb`. Er nimmt aus `betrieb` nur die drei
erlaubten Einträge, prüft das Paket, rendert den Ordner `betrieb/` der
Seite mit dem Code aus `CODESTAND`, baut mit `jekyll-build-pages` und
liefert aus. Scheitert eine Prüfung, bleibt die Seite vom Vortag stehen.
Jede Action ist auf ihren Commit gepinnt.

**Im Code: Paketschema 6 und Ankerschema 4.**

* `stand.json` trägt die Blöcke `geschaeftsentwicklung` und
  `abschluss_kennzahlen`. Der Export rechnet sie mit denselben Funktionen,
  mit denen der Konsument nachrechnet (`betrieb.seite.
  geschaeftsentwicklung`, `abschluss_kennzahlen`), aus dem geprüften
  Journal und aus den Abschlussdateien im Paket, nicht aus der Ablage.
* Der Ankersatz bindet `stand.json` (`stand_sha256`, kanonisch gerechnet
  ohne den Block `anker`, `models.anker.stand_hash`). Damit hängt jede
  Zahl in `stand.json` über den Satz an der A-B1.
* Wer die Parquet-Dateien hat, rechnet beide Blöcke nach und weist ein
  Paket ab, das abweicht. Ein Paket im Schema 6 mit einem Satz unter
  Schema 4 weist der Konsument ab; sonst entfiele die Bindung still.

**Was öffentlich wird.** Neu öffentlich ist `stand.json`. Es nennt die
letzten zwanzig Buchungen mit Policennummer und Betrag. Dieselben zwanzig
Buchungen zeigt die Tagesseite `index.html`, die schon heute unter `plv/`
veröffentlicht ist. Eine neue Art von Angabe kommt also nicht hinzu.
Tagesjournal und Monatsabschlüsse bleiben unveröffentlicht. Der einzige
Pfad in `stand.json` ist der der Ankerdatei; die Routine exportiert im
Container, er ist deshalb ein Pfad im Container und keiner des Servers.

## Bedrohungsmodell

Das Angreifermodell ist das aus dem Entscheid vom 2026-09-16: vor allem
ein Lauf oder ein Agent, der etwas Falsches stimmig hinschreibt, daneben
ein Mensch mit Absicht.

**Die Routine braucht vier Schlüssel:** den Betriebsschlüssel (zeichnet
jede Protokollzeile und den Ankersatz), den Simulationsschlüssel von
`mensch/betrieb` (zeichnet A-B1), den Simulationsschlüssel des Vorstands
(nur zum Prüfen, siehe Entscheid e) und den Deploy-Key (schreibt in
`plv-fiktion`). Alle liegen auf demselben Rechner, auf dem die Laufzeit
läuft. Wer ihn beherrscht, kann einen in sich stimmigen falschen Tag
ausliefern: Zahlen, Anker und A-B1 neu schreiben und schieben. Das ist
nicht verhindert. Die A-B1 ist eine simulierte Zeichnung, und die Seite
sagt das.

**Was der Schlüsselhalter nicht kann, gemessen am 2026-10-09
(bartl-infra, merge-session):**

* den Rahmen ändern: Ein Push mit dem Deploy-Key gilt in einem
  persönlichen Repository als Push des Besitzers. Deshalb gelten die
  Rulesets ohne Ausnahme: `main` nur per Pull Request, auch für den
  Maintainer; alle Zweige außer `betrieb`, `main` und `beitrag/**`
  gesperrt; Tags gesperrt. Die Probe, mit dem Schlüssel einen anderen
  Zweig zu schieben, wurde abgewiesen (GH013).
* ausliefern: Die Umgebung `github-pages` liefert nur aus `main`. Der
  Workflow läuft nie bei Push auf `betrieb`.
* Code oder HTML einschleusen: Der Server liefert nur Daten. Gerendert
  wird mit dem Code aus `CODESTAND`, und der steht in `main`.
* Pull Requests anlegen oder genehmigen lassen: Actions dürfen das nicht,
  das Token der Actions ist standardmäßig nur lesend.

**Was nur sichtbar ist, nicht verhindert:** Workflow-Dateien in den
Zweigen, die der Schlüssel schreiben darf (Entscheid a).

**Was der Workflow prüft:** jede Datei unter `paket/` gegen ihre
Prüfsumme in `stand.json`; den genannten Satz in `anker.jsonl`, die
Bindung des Satzes an die Dateiliste und an `stand.json`; die A-B1 in
Struktur, `snapshot_sha256` und Bindung an den Satz. Die Signaturen prüft
er nicht (Entscheid d). Er rechnet die Blöcke nicht nach, die nur Journal
und Abschlüsse tragen; dafür bindet sie der Satz.

## Verworfene Wege

* **Fertiges HTML vom Server.** Ging ohne Änderung am Code. Der Workflow
  müsste aber den gerenderten Seiten glauben, und wer den Server
  beherrscht, könnte beliebiges HTML auf die Seite bringen, auch Skript.
* **Dasselbe Repository wie der Code.** Der Schreibschlüssel läge im
  Repository des Codes. Entschieden am 2026-10-09: eigenes Repository.
* **Ziehen über das Tailnet.** GitHub holt die Daten vom Server. Dafür
  bräuchte der Workflow Zugang ins Tailnet als Secret, und der Server
  einen Weg von außen herein.
* **GitHub App statt Deploy-Key.** Ein eigener Akteur mit feinen Rechten.
  Als Ersatz des Schlüssels heute zu aufwendig (App anlegen, ihr privater
  Schlüssel liegt trotzdem auf dem Server, Tokens erneuern). Als Antwort
  auf Frage a bleibt sie eine Option.
* **Zahlen per JavaScript auf der Seite.** Wäre das erste Skript für
  Inhalt; die Prüfungen der Seite messen statisches HTML.
* **Der Simulationsschlüssel als Secret im Workflow.** Damit ließe sich
  die Signatur der A-B1 prüfen. Aber jeder, der einen Workflow in
  `plv-fiktion` laufen lässt, könnte dann selbst zeichnen.

## Einzelentscheide

Je Frage die Wege, die Empfehlung und der Entscheid des Maintainers
vom 2026-10-15.

### a) Workflow-Dateien in den Zweigen, die der Schlüssel schreibt

Ein Push auf `betrieb` startet die Workflows, die im Stand von `betrieb`
liegen, nicht die aus `main`. Legt der Schlüssel dort eine
Workflow-Datei ab, läuft ihr Code in Actions: ohne Auslieferung, mit
lesendem Token, aber mit Netz. Dasselbe gilt für `beitrag/**`: Die
Rulesets lassen diese Zweige offen, damit der Maintainer Pull Requests
schieben kann, und den Schlüssel unterscheiden sie nicht vom Maintainer.

| Weg | Wirkung | Kosten |
|---|---|---|
| 1. Pfadsperre für `.github/**` per Push-Ruleset | verhindert es | ob ein persönliches öffentliches Repository das anbietet, ist nicht gemessen; die Sperre träfe auch den Maintainer, jede Änderung an einem Workflow bräuchte ein kurzes Aufheben |
| 2. GitHub App ohne das Recht `workflows` statt Deploy-Key | verhindert es | App anlegen und betreiben (siehe oben) |
| 3. Restrisiko benennen | macht es sichtbar | der Workflow in `main` liefert nicht aus, wenn `betrieb` etwas außerhalb der drei Einträge enthält; `plv-fiktion` hält keine Secrets; einen fremden Lauf zeigt die Liste der Actions |

**Empfehlung: 3**, ergänzt um eine Messung. Wer den Schlüssel hat,
beherrscht den Server und kann ohnehin einen falschen Tag ausliefern; ein
fremder Workflow fände kein Secret und kein Schreibrecht. Gemessen werden
sollte, ob ein Push mit dem Deploy-Key überhaupt eine Workflow-Datei
schreiben darf (bartl-infra, Probe auf einem Wegwerfzweig unter
`beitrag/**`, Push durch den Maintainer). Wenn die Pfadsperre verfügbar ist, ist Weg 1 die bessere
Wahl.

**Entschieden (Maintainer, 2026-10-15): Weg 3.** Das Restrisiko ist
benannt; der Workflow liefert nicht aus, wenn `betrieb` mehr als `paket/`,
`anker.jsonl` und `A-B1.json` enthält. Die Probe macht der Maintainer mit
bartl-infra. Gibt es eine Pfadsperre für `.github/**`, wird sie genommen.

### b) Zweig `betrieb` wachsen lassen oder neu anlegen

| Weg | Wirkung |
|---|---|
| 1. ein Commit je Abend | die Geschichte des Zweigs ist die Geschichte der Auslieferungen |
| 2. jeden Abend ein einziger Commit (Force-Push) | der Zweig bleibt klein; das Ruleset müsste Force-Push auf `betrieb` erlauben, und wer den Schlüssel hat, könnte die Geschichte löschen |

Gemessen am Paket vom 2026-10-08: Die öffentlichen Dateien sind 29
Dateien mit 10,3 MB. Täglich ändern sich `stand.json`, `index.html`,
`protokoll.jsonl` und `laufmanifest.json` (gepackt zusammen rund 86 KB,
das Protokoll wächst nur um eine Zeile), monatlich kommen zwei Berichte
hinzu (gepackt rund 95 KB), jährlich ein Jahresbericht (rund 190 KB).
Das sind wenige Megabyte im Jahr.

**Empfehlung: 1.** Die Ankerreihe ist nur anfügbar; der Zweig sollte es
auch sein. Force-Push wäre die einzige Lockerung der Rulesets.

**Entschieden (Maintainer, 2026-10-15): Weg 1**, ein Commit je Abend, kein
Force-Push.

### c) A-B1-Snapshots bündeln

Die Routine zeichnet jeden Abend eine A-B1. Jeder Snapshot liegt im
Fall-Datenraum unter `entscheide/` und wird nie gelöscht (ADR-002).
Gemessen: rund 9,7 KB je Snapshot, also rund 3,5 MB im Jahr.

| Weg | Wirkung |
|---|---|
| 1. je Abend eine Datei, nichts bündeln | jede Auslieferung hat ihren eigenen Beleg; `entscheide/` wächst um 365 Dateien im Jahr |
| 2. Monatsbündel daneben | ein Archiv mehr; die Einzeldateien bleiben trotzdem, weil `entscheide/` nur wächst |

**Empfehlung: 1.** Ein Bündel spart nichts, solange die Einzeldateien
bleiben müssen. Wiedervorlage, wenn das Verzeichnis beim Lesen spürbar
langsam wird.

**Entschieden (Maintainer, 2026-10-15): Weg 1**, nicht bündeln.

### d) Die Signatur der A-B1 im Workflow

Die A-B1 ist mit HMAC gezeichnet. Prüfen kann die Signatur nur, wer den
Schlüssel hält.

| Weg | Wirkung |
|---|---|
| 1. Struktur und Bindung prüfen, die Signatur nicht | der Workflow hält keinen Schlüssel; die Seite sagt „Angaben der Snapshot-Datei“ und nicht „Signatur geprüft“ |
| 2. Simulationsschlüssel als Secret | die Signatur ist prüfbar; jeder Workflow in `plv-fiktion` könnte zeichnen |

**Empfehlung: 1.** Signaturen prüft der Server: Der Export prüft jede
Protokollzeile gegen den Betriebsschlüssel, das Gate prüft vor dem
Zeichnen die Ordnungslinie und den Fallauftrag. Ein Verfahren mit
öffentlichem Schlüssel wäre der saubere Weg zu einer prüfbaren Signatur
auf der Seite (siehe e, Weg 3).

**Entschieden (Maintainer, 2026-10-15): Weg 1.** Der Workflow prüft
Struktur und Bindung; kein Schlüssel wird als Secret abgelegt.

### e) Der Schlüssel des Vorstands in der Routine

Gemessen am 2026-10-15 mit den Schlüsseln der Testsuite: Das Gate
zeichnet A-B1 nur, wenn der Schlüssel des Vorstands im Ring liegt. Jede
gezeichnete Annahme prüft die Ordnungslinie, deren Glieder der Vorstand
zeichnet. Ohne seinen Schlüssel lautet die Meldung: „die Ordnungslinie ist
verletzt: Glied 2: der Schlüssel von mensch/vorstand … ist nicht im
Ring“. Am 2026-10-08 zeichnete der Maintainer A-B1 mit beiden
Schlüsseln im Ring, dem des Vorstands und dem von `mensch/betrieb`.

Bei HMAC prüft nur, wer den Schlüssel hält, und wer ihn hält, kann damit
auch zeichnen. Der Plan vom 2026-10-09 nannte nur den Schlüssel von
`mensch/betrieb`.

| Weg | Wirkung |
|---|---|
| 1. Vorstandsschlüssel in die Routine | wie entschieden: täglich eine A-B1. Der Schlüssel kommt als einzelne Datei, nur lesend und nur in den Container des A-B1-Schritts, ohne Netz; zeichnen tut der Schlüssel von `mensch/betrieb`, und die Routine prüft danach, dass der Snapshot diese Rolle nennt. Ein Fehler oder ein Eingriff in die Routine hätte aber einen Schlüssel zur Hand, mit dem sich Ordnung und Fallaufträge zeichnen lassen |
| 2. täglich nur eine Momentaufnahme | die Routine braucht weder Vorstand noch `mensch/betrieb`; der Ankersatz trägt die Zeichnung des Betriebsschlüssels (Urheberschaft). Die Seite zeigt den Tag als „vom Betriebsdienst exportiert“ und nennt die letzte A-B1, die der Maintainer zeichnet. Ändert den Entscheid vom 2026-10-09 |
| 3. Signaturen mit öffentlichem Schlüssel für alle Abnahmen | Prüfen ohne Zeichnungsmacht; löst auch d. Ein Umbau aller Abnahmen, eigenes ADR, mehrere Tage |

**Empfehlung: 1, mit Weg 3 als spätere Ablösung.** Auf dem Rechner liegen
alle Simulationsschlüssel heute schon im Konto des Maintainers. Neu ist,
dass ein Timer sie ohne Menschen benutzt. Die Welt ist erfunden, und die
Seite weist die Zeichnung als Simulation aus. Weg 2 hält die Schlüssel
aus dem Timer heraus, nimmt der Seite aber die tägliche Abnahme, die der
Entscheid vom 2026-10-09 wollte.

**Entschieden (Maintainer, 2026-10-15): Weg 1, später Weg 3.** Der
Schlüssel des Vorstands kommt als einzelne Datei, nur lesend und nur in
den Container des A-B1-Schritts, ohne Netz. Gezeichnet wird mit
`mensch/betrieb`; danach prüft die Routine die Rolle im Snapshot.
Signaturen mit öffentlichem Schlüssel für alle Abnahmen sind als spätere
Ablösung vorgemerkt.

## Folgen

* **Umgesetzt:** Paketschema 6 und Ankerschema 4 (Abschnitt
  „Entscheidung“, Fachkonzept Tagesbetrieb, Abschnitt 8.3). Ein Paket im
  Schema 5 nimmt der Konsument nicht mehr an; ein neuer Export heilt es.
  Dazu die Routine mit ihren Units (`plv/betrieb/betrieb_seite.sh`,
  `betrieb-seite.service`, `betrieb-seite.timer`, README dort), nicht
  eingeschaltet.
* **A-B1 im Image.** Das Image trägt kein git; der Snapshot nennt deshalb
  `system.commit` und `system.branch` „unbekannt“. Den Code bindet
  `system.quellcode_sha256`, und welches Image lief, sagt die
  Protokollzeile des Tageslaufs (`image_revision`), die die Routine vorher
  gegen das Image hält.
* **Die Laufzeit braucht ein Image mit Schema 6.** Der Export läuft im
  Laufzeit-Image. Bis die Laufzeit auf ein Image aus einem `main` mit
  Schema 6 umgestellt ist, kann die Routine kein Paket für den neuen
  Betriebsteil erzeugen.
* **`CODESTAND` zieht mit dem Image.** Jeder Wechsel des Images braucht
  einen Pull Request in `plv-fiktion`, der `CODESTAND` mitzieht. Bis dahin
  hält die Routine an, und die Seite bleibt auf dem letzten Tag stehen.
* **Feste Orte auf dem Server:** der Fall-Datenraum des Originalfalls mit
  Anker und `entscheide/` (heute im Arbeitsbaum
  `~/git/rechner-pipeline-fall3`), die Ordnungslinie, das Mandat der
  simulierten Rolle, die Schlüssel (Entscheid e), ein Klon von
  `plv-fiktion` für die Routine. Das richtet bartl-infra ein; das
  Repository nennt keine Pfade des Servers.
* **Der neue Rahmen muss in `main` von `plv-fiktion` sein, bevor die
  Automatik läuft**, sonst rendert der Workflow in einen Rahmen, der
  `betrieb/` nicht kennt.
