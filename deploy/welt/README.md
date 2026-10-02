# Eine Welt aufstellen und einen Fall darin fuehren

Eine **Welt** ist alles, was neben dem Code noetig ist, damit die PLV laeuft
und ein Migrationsfall gefuehrt werden kann: die Ablage des Tagesbetriebs
(`daten/`), die Linie mit ihrer Ordnungslinie und den Erstabnahmen (`linie/`)
und — ausserhalb von beidem — die Schluessel der Rollen, die
Zeichnungsordnung und das Mandat. Die Welt startet OHNE uebernommenen
Bestand; ein Fall bringt ihn hinein. Je Fall eine eigene Welt: So bleibt ein
Fall wiederholbar, und kein Fall beruehrt die Laufzeit eines anderen.

Die Skripte hier fahren die Bedienfolgen, die in ADR-025 (Erstabnahmen),
ADR-026 (Fallauftrag) und `deploy/plv/README.md` (Ablage) beschrieben sind —
jeden Schritt als Systemkommando, mit Halt beim ersten Fehler und einem
Protokoll in der Welt. Sie rechnen und pruefen nichts selbst.

| Datei | Zweck |
|---|---|
| `welt_aufstellen.sh` | Schluessel und Ordnung (fuer eine Welt mit eigenen Schluesseln), Ablage, Linie, Erstabnahmen |
| `fall_starten.sh` | Fall anlegen, Lieferung registrieren, Vorlage des Fallauftrags |
| `fall_zeichnen.sh` | ein Gate des Falls zeichnen, mit dem Ring, den das Gate braucht |
| `zugang.sh` | den abgenommenen Bestand des Falls in die Ablage der Welt bringen: Probe, Neuaufsetzen, Aufbaulauf, Anfangsbestand |
| `fall_nachfahren.sh` | einen festgehaltenen Fall (ein Paket) ohne Agenten nachfahren, bis zum Ende oder bis zu einem Haltepunkt |
| `paket_bauen.sh` | aus einem gefuehrten Fall das Paket zum Nachfahren bauen |
| `laufzeit_aufstellen.sh` | Welt und festgehaltenen Fall in einem Aufruf: die Welt auf dem Stand vor dem Fall, der Fall auf dem Stand danach |
| `abgenommen.py` | der Commit, auf dem eine Linie ein Gate angenommen hat (gelesen von den Skripten) |
| `gezeichnet.py` | ob ein Mensch ein Gate schon selbst gezeichnet hat (gelesen vom Nachfahren) |
| `fall-baldrian-klv-tg2015.conf` | der Fall der Vorfuehrung: Lieferung, Stichtag, Auftrag |
| `einstellungen.beispiel.conf` | Vorlage der Einstellungen fuer eine Welt mit vorhandenen Schluesseln |
| `mandat.vorlage.txt` | Vorlage des Mandats der simulierten Rollen |
| `stellungnahme-tbox-020.json` | aktuarielle Stellungnahme zur T-Box 0.2.0, Pflichtbeleg der Erstabnahme A-O1 |

Alle Aufrufe vom Wurzelverzeichnis des Codebaums, mit eingerichtetem
`.venv`. Der Baum muss sauber sein (`git status` leer) und darf sich
waehrend des Aufstellens nicht bewegen: Die Abnahmen pinnen seinen Stand.

## Eine Welt mit eigenen Schluesseln

Fuer Vorfuehrung, Uebung und Probe. Ein Aufruf:

```
deploy/welt/welt_aufstellen.sh <welt>
```

`<welt>` ist ein neues Verzeichnis AUSSERHALB des Codebaums, etwa
`~/plv-welt`. Die vier Phasen laufen nacheinander und sind einzeln
aufrufbar (`deploy/welt/welt_aufstellen.sh <welt> <phase>`):

| Phase | Was entsteht |
|---|---|
| `schluessel` | je Rolle ein Schluessel unter `~/.plv-schluessel` (64 zufaellige Byte, 0600, nie angezeigt), die Zeichnungsordnung, das Mandat `<welt>/mandate/mandat.txt`, die Einstellungen `<welt>/einstellungen.conf` |
| `ablage` | `<welt>/daten`: die Ablage der PLV ohne uebernommenen Bestand, gefuehrt bis zum Tag vor dem Zugang |
| `linie` | `<welt>/linie` mit dem ersten Glied der Ordnungslinie |
| `abnahmen` | die Erstabnahmen A-K2, A-O1, A-T1 und A-B3, der gebundene Anfangsbestand |

Die Phase `ablage` rechnet einige Minuten, die uebrigen Sekunden. Am Ende
steht `WELT STEHT: ...` mit den vier Abnahmen; das Protokoll liegt unter
`<welt>/aufstellen.log`.

Was die Phase `schluessel` festlegt, laesst sich beim Aufruf setzen:
`SCHLUESSEL` (Verzeichnis der Schluessel), `BIS` (letzter Tag der Ablage),
`VON` (Vergleichsstand der Erstabnahme), `MANDATGEBER`, `ENTSCHEIDER`.

- **Kein Schluessel wird ueberschrieben, keiner verlaesst den Rechner.**
  Traegt das Schluesselverzeichnis schon eine Ordnung, haelt das Skript an;
  eine zweite Welt bekommt ein eigenes Verzeichnis (`SCHLUESSEL=...`).
- **Alle Rollen haben die Schluesselklasse `simulation`.** Jede Zeichnung
  dieser Welt weist sich als simuliert aus und nennt das Mandat. Die
  Schluessel sind symmetrisch: Wer eine Zeichnung pruefen kann, kann sie auch
  leisten. Wer in einer Uebung welche Rolle zeichnet, ist deshalb eine Regel
  der Leitung, keine Eigenschaft der Technik.

## Eine Welt mit vorhandenen Schluesseln

Wer Schluessel und Zeichnungsordnung schon hat, legt
`<welt>/einstellungen.conf` nach `einstellungen.beispiel.conf` selbst an und
ruft die Phasen `ablage`, `linie` und `abnahmen` auf. Die Phase `schluessel`
wird uebersprungen, sobald die Einstellungen liegen.

## Einen Fall starten

```
deploy/welt/fall_starten.sh <welt> anlegen deploy/welt/fall-baldrian-klv-tg2015.conf
deploy/welt/fall_starten.sh <welt> vorlage
```

`anlegen` legt den Fall unter `faelle/<name>` an und registriert die
Lieferung laut Falldatei; die Falldatei liegt danach als `<welt>/fall.conf`
in der Welt. `vorlage` erzeugt die Vorlage des Fallauftrags
(`faelle/<name>/abgeleitet/auftrag/fallauftrag.md`) und, falls er noch nicht
liegt, den Schluessel der Programmleitung. Beides zeichnet nichts. Nach einer
Nachlieferung der Quelle erzeugt `vorlage` die Vorlage neu.

Den Auftrag zeichnet der Vorstand:

```
deploy/welt/fall_zeichnen.sh <welt> A-M6 angenommen "<begruendung>"
```

## Zeichnen

```
deploy/welt/fall_zeichnen.sh <welt> <gate> angenommen|abgelehnt "<begruendung>"
deploy/welt/fall_zeichnen.sh <welt> ring <gate>
```

Das Skript reicht je Gate den Ring: zuerst die Schluessel, gegen die das
Gate fremde Ketten prueft (immer der des Vorstands — Fallauftrag und Glieder
der Linie), zuletzt den zeichnenden.

| Gate | zeichnet | davor im Ring |
|---|---|---|
| A-M6 | Vorstand | — |
| A-Q1, A-M1, A-M2, A-M3, A-T1 | Aktuariat | Vorstand |
| A-O1 | Architektur | Vorstand |
| A-K2 | Rechenkern | Vorstand |
| A-M4 | Aktuariat | Vorstand, Rechenkern, Architektur |
| A-B1 | Betrieb | Vorstand |
| A-B2 | Betrieb | Vorstand, Aktuariat |
| A-M5 | Programmleitung | Vorstand; dazu Aktuariat, sobald eine A-M4 im Fall liegt |

`ring <gate>` gibt nur die Argumente aus, fuer Kommandos, die denselben Ring
brauchen (`ontologie.entscheide`, die Kommandos des Zugangs). Was vor einer
Zeichnung vorliegen muss, sagt der Skill `migrationsfall-durchfuehren`; das
Gate prueft es und nennt, was fehlt.

## Der Zugang in die Ablage

Nach der Migrationsabnahme (A-M4) kommt der uebernommene Bestand in die
Ablage der Welt (ADR-022; die Bedienfolge und ihre Begruendung stehen in
`deploy/plv/README.md`, "Reihenfolge des Hochziehens"):

```
deploy/welt/zugang.sh <welt> probe
deploy/welt/fall_zeichnen.sh <welt> A-B2 angenommen "<begruendung>"
deploy/welt/zugang.sh <welt> aufsetzen
deploy/welt/zugang.sh <welt> aufbau [<heute>]
deploy/welt/zugang.sh <welt> belegen
deploy/welt/zugang.sh <welt> ab3 "<begruendung>"
deploy/welt/zugang.sh <welt> binden
```

| Phase | Was geschieht | Vor dem naechsten Schritt lesen |
|---|---|---|
| `probe` | Zugangsprobe auf einer leeren Ablage mit der Config des Falls: zwei Laeufe vom Betriebsbeginn ueber den Stichtag, mit und ohne Zugang | `faelle/<name>/abgeleitet/berichte/zugangsprobe.json` — als Lesefassung: `python werkzeuge/lagebild.py zugangsprobe --fall faelle/<name>` —, dann A-B2 zeichnen |
| `aufsetzen` | die Ablage der Welt neu aufsetzen; die bisherige wird zu `<welt>/daten.archiv-<zeit>` und bleibt der Vergleichsstand ohne den uebernommenen Bestand | |
| `aufbau` | Aufbaulauf vom Betriebsbeginn bis `<heute>` (ohne Angabe: der heutige Tag) | |
| `belegen` | den Anfangsbestand der neuen Ablage belegen | `<welt>/linie/abgeleitet/anfangsbestand/beleg.md` |
| `ab3` | A-B3 in der Linie zeichnen, als Betrieb | |
| `binden` | den Anfangsbestand binden, danach ein Tageslauf | |

Am Ende steht `ZUGANG STEHT: ...` mit der Zahl der Abschluesse; das Protokoll
liegt unter `<welt>/zugang.log`. Mit dem Bestand der Vorfuehrung rechnet die
Probe rund 20 Minuten, der Aufbaulauf rund 11. Zwischen Probe und Aufbaulauf darf
sich der Codebaum nicht bewegen: Der erste Lauf, der den Eingang fuehrt, haelt
Config, Kernversion und Fingerabdruck des Pakets gegen die Probe.

## Einen festgehaltenen Fall nachfahren

Ein Fall, der einmal gefuehrt wurde, laesst sich ohne Agenten wiederholen:
Was Agenten und Menschen darin erarbeitet haben, wird mitgebracht; was das
System rechnet, rechnet es neu; gezeichnet wird neu, mit den Schluesseln der
Welt. So wird eine Laufzeit aus dem Stand des Repositorys neu aufgestellt,
ein Fall nach einer Code-Aenderung gegengeprueft oder in einer Uebung an
eine bestimmte Stelle "vorgespult".

```
deploy/welt/fall_nachfahren.sh <welt> <paket> [--bis <haltepunkt>] [--wechseln]
```

Das **Paket** ist ein Verzeichnis:

| Im Paket | Was |
|---|---|
| `fall.conf` | der Fall: Name, Lieferung, Stichtag, Auftrag |
| `rezept.sh` | die Schritte in ihrer Reihenfolge |
| `erarbeitet/` | was im Fall erarbeitet wurde und kein Kommando neu erzeugt, unter demselben Pfad wie im Fall |
| `nachlieferung/` | was die Quelle im Lauf des Falls nachgeliefert hat |
| `ERWARTUNG` | `<sha256>  <pfad im fall>` je Ergebnis, das byteweise gleich sein muss |
| `STAND` | `VOR=<commit>`: der Stand des Codebaums, auf dem die Linie des festgehaltenen Falls abgenommen war |
| `SHA256SUMS` | Pruefsummen aller Dateien des Pakets |

Im Paket liegen keine Schluessel und keine Zeichnungen. Das Skript faehrt
nur ein Paket, das seinen Pruefsummen entspricht und keine Datei darueber
hinaus traegt.

Im **Rezept** stehen nur diese Helfer, je Zeile einer (Fortsetzungszeilen
mit `\`); eine andere Zeile verweigert das Skript, bevor es beginnt:

| Helfer | Wirkung |
|---|---|
| `anlegen` | Fall anlegen, Lieferung laut `fall.conf` registrieren |
| `vorlage` | die Vorlage des Auftrags erzeugen (auch neu, nach einer Nachlieferung) |
| `registriere <pfad>` | `nachlieferung/<pfad>` im Fall registrieren |
| `einlegen <pfad>` | `erarbeitet/<pfad>` in den Fall legen, nie ueber eine andere Datei hinweg |
| `schritt "<name>" <kommando ...>` | ein Kommando fahren; ein Exit ungleich null haelt an |
| `entscheide <diskrepanz> <wert> "<begruendung>" [--beleg <pfad>]` | eine Diskrepanz der Quellen endgueltig aufloesen, als Aktuariat |
| `entscheide_alle <quelle> "<begruendung>"` | alle vorlaeufig aufgeloesten Diskrepanzen zur Lesart dieser Quelle entscheiden |
| `zeichne <gate> "<begruendung>"` | das Gate annehmen, mit dem Ring der Welt — es sei denn, ein Mensch hat es schon selbst gezeichnet |
| `zugang <phase> [argument]` | eine Phase des Zugangs fahren (`zugang.sh`): `probe`, `aufsetzen`, `aufbau [<heute>]`, `belegen`, `ab3 "<begruendung>"`, `binden` |
| `haltepunkt <name>` | hier endet ein Lauf mit `--bis <name>` |
| `erwarte <pfad im fall>` | die Datei gegen `ERWARTUNG` halten; andere Bytes halten an |

In den Kommandos stehen `$PY` (der Interpreter), `$F` (`faelle/<name>`),
`$A` (`$F/abgeleitet`), `$WELT`, `$LINIE`, `$ORDNUNG`, `$STICHTAG`, `$PAKET`,
`$(ring <gate>)` fuer Kommandos, die den Ring eines Gates brauchen, und
`$(abgenommen <gate>)` fuer den Commit, auf dem die Linie der Welt das Gate
zuletzt angenommen hat.

- **Nichts laeuft doppelt.** Ein Lauf merkt sich, wie weit er kam
  (`<welt>/nachfahren.stand`). Derselbe Aufruf faehrt hinter dem letzten
  erledigten Schritt weiter — nach einem Haltepunkt ebenso wie nach einem
  behobenen Fehler. Protokoll: `<welt>/nachfahren.log`.
- **Entscheidungen werden neu getroffen, nicht mitgebracht.** Die Aufloesung
  einer Diskrepanz traegt in der A-Box die Zeichnung ihrer Rolle. Eine
  mitgebrachte A-Box truege die Schluessel des festgehaltenen Laufs; deshalb
  legt das Rezept die Fragmente ein, laesst zusammenfuehren und entscheidet
  mit `entscheide` unter den Schluesseln der Welt.
- **Verglichen werden Ergebnisse, nicht Zeichnungen.** `erwarte` haelt
  Bytes gegen den festgehaltenen Fall; Snapshots und Belege tragen die
  Schluessel und Zeiten des Laufs und sind deshalb nie gleich.
- **Eine Zeichnung beim Nachfahren uebernimmt ein Urteil, sie faellt keins.**
  Das traegt nur, wenn der Gegenstand derselbe ist. Wo das Rezept ein Gate
  zeichnet, haelt es deshalb vorher den Gegenstand gegen den festgehaltenen
  Fall: mit `erwarte` (Spez, Tabellen, Abnahmebericht) oder mit einem
  Schritt, der Fingerabdruecke vergleicht (Kern, Tarifwerk). Weicht der
  Gegenstand ab, haelt der Lauf — dann urteilt ein Mensch.
- **Wer selbst zeichnet, dessen Zeichnung gilt.** An einem Haltepunkt kann
  ein Mensch die Vorlage lesen und das Gate selbst zeichnen
  (`fall_zeichnen.sh <welt> <gate> angenommen "<begruendung>"`, fuer den
  Anfangsbestand `zugang.sh <welt> ab3 "<begruendung>"`). Faehrt der Lauf
  danach weiter, zeichnet das Rezept dieses Gate nicht noch einmal: Die
  k-te Zeichnung eines Gates im Rezept gilt als geleistet, wenn im Fall k
  Annahmen liegen; der Anfangsbestand, wenn eine Annahme genau den Beleg
  pinnt, der in der Linie liegt. Ist die juengste Zeichnung des Gates eine
  **Ablehnung**, haelt der Lauf — ueber eine Ablehnung zeichnet das Rezept
  nie hinweg; danach fuehrt ein Mensch den Fall weiter. Das ist eine
  Anzeige, kein Urteil: Ob eine Zeichnung gilt, pruefen die Gates der
  folgenden Schritte.
- **Das Rezept nennt keinen Commit.** Ein Beleg, der die Aenderung des
  Zielsystems gegen den abgenommenen Stand zeigt (`kernstand_belegen`,
  `tarifwerk_belegen`), bekommt sein `--von` aus der Linie der Welt:
  `--von "$(abgenommen A-K2)"`. So laesst sich ein Fall in jeder Welt
  nachfahren, deren Linie auf dem Stand vor dem Fall abgenommen wurde.
- **Zwei Staende des Codebaums.** Hat der Fall das Zielsystem geaendert
  (Kern, Tafeln, Config), wird die Welt auf dem Stand VOR dem Fall
  aufgestellt und der Fall auf dem Stand DANACH nachgefahren. Die Aenderung
  selbst baut das Rezept nicht — sie liegt als Commits im Codebaum, das
  Rezept belegt und zeichnet sie.
- **Der Fall der Welt.** Fuehrt die Welt schon einen anderen Fall, haelt
  das Skript an. `--wechseln` legt dessen Falldatei beiseite
  (`<welt>/fall-frueher-<name>.conf`) und macht den nachgefahrenen Fall zum
  Fall der Welt; der fruehere Fall bleibt liegen. Eine Welt faehrt EIN Paket
  nach.

### Welt und Fall in einem Aufruf

```
deploy/welt/laufzeit_aufstellen.sh <welt> <paket> [--bis <haltepunkt>]
```

Stellt die Welt auf dem Stand auf, den das Paket nennt (`STAND`), und faehrt
danach das Paket auf dem Stand dieses Baums nach. Der Stand vor dem Fall
liegt dabei als eigener Baum in der Welt (`<welt>/baum-vor`, ein Klon dieses
Baums auf dem Commit); der Codebaum selbst wird nicht bewegt. Der Commit muss
ein Vorfahr des Baums sein — ein Paket aus einer anderen Geschichte des
Repositorys haelt das Skript an, bevor es etwas anlegt.

Die Schluessel der Welt liegen dabei unter `~/.plv-schluessel/<name der
welt>` (anders nur mit `SCHLUESSEL=...`): je Welt ein eigenes Verzeichnis.
Bricht das Aufstellen ab, beginnt ein neuer Versuch einfach unter einem
anderen Namen der Welt; die angefangene bleibt liegen, bis jemand sie
ansieht und entfernt.

Derselbe Aufruf ist wiederholbar: Steht die Welt schon, faehrt er nur das
Paket weiter, hinter dem letzten erledigten Schritt. So wird aus dem Stand
des Repositorys und einem Paket eine Laufzeit mit uebernommenem Bestand —
oder, mit `--bis`, eine Welt an der Stelle des Falls, an der eine Uebung
beginnen soll.

### Das Paket bauen

```
deploy/welt/paket_bauen.sh <welt> <ziel> --rezept <rezept.sh> \
    [--erarbeitet <liste>] [--erwartung <liste>] [--linie <linie>]
```

Aus dem Fall der Welt entsteht das Verzeichnis `<ziel>`: die Falldatei, das
Rezept, je Zeile der Liste `--erarbeitet` eine Datei oder ein Verzeichnis
des Falls, jede Datei des Eingangs, die nicht zur Lieferung der Falldatei
gehoert (die Nachlieferungen), je Zeile der Liste `--erwartung` die
Pruefsumme der Datei im Fall, der Stand vor dem Fall und die Pruefsummen des
Pakets. Die Listen nennen Pfade relativ zum Fall, eine je Zeile.

Den Stand vor dem Fall liest das Skript aus der Linie der Welt (`<welt>/linie`
oder `--linie`): der Commit, auf dem die Linie den Kern angenommen hat, auf
den der Fallauftrag den Fall gestellt hat. Er wird gelesen, nie angegeben;
eine Linie ohne solche Annahme ergibt kein Paket, eine Welt ohne Linie ein
Paket ohne `STAND` (das sich nachfahren, aber nicht in einem Aufruf
aufstellen laesst).

Was erarbeitet ist und welche Ergebnisse byteweise gleich sein muessen,
entscheidet, wer das Rezept schreibt. Das Skript haelt Rezept und Paket
zusammen: Jedes `einlegen`, `registriere` und `erwarte` des Rezepts muss im
Paket seine Datei bzw. seinen Eintrag haben, sonst entsteht kein Paket.
Zeichnungen (`entscheide/`) nimmt es nie auf, und ein vorhandenes Paket
ueberschreibt es nie.

Was als Erwartung taugt: Ergebnisse, die nur vom Inhalt abhaengen — Tabellen,
uebersetzte Zeilen, die Spez, Berichte. Belege, die Zweig und Commit des
Codebaums nennen (die Ergebnisse der Tests, der Suite, der Fuehrungsprobe),
sind nur auf dem festgehaltenen Stand selbst byte-gleich, nicht auf einem
Stand mit demselben Inhalt unter anderem Namen; und was Zeiten, Schluessel,
Entscheider oder Pfade des Rechners traegt, ist es nie.

## Grenzen

- Die Skripte fuehren einen Fall von der Lieferung bis zum gebundenen
  Anfangsbestand der Ablage. Die Veroeffentlichung eines Stands (A-B1) und
  ein Glied der Ordnungslinie sind hier nicht gefasst.
- Eine Welt fuehrt einen Fall zur Zeit. Ein zweiter bekommt eine zweite
  Welt — oder loest den ersten ab, wenn er nachgefahren wird (`--wechseln`).
- Das Skript zum Nachfahren faehrt ein Paket. Ein Paket fuer den Fall der
  Vorfuehrung ist nicht Teil dieses Stands: Es traegt die Aufloesung des
  Falls und liegt deshalb nicht im Codebaum, auf dem derselbe Fall mit
  Agenten gefuehrt wird.
- Ein Rezept ist an EIN Paket gebunden: Wird es geaendert, gilt der Stand
  eines begonnenen Laufs nicht mehr, und das neue Paket braucht eine neue
  Welt.
- Mandat und Stellungnahme sind Vorlagen der Vorfuehrung. Wer eine Welt fuer
  einen anderen Zweck aufstellt, schreibt beide selbst und nennt sie in den
  Einstellungen.
