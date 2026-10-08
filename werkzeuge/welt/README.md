# Eine Welt aufstellen und einen Fall darin führen

Eine **Welt** ist alles, was neben dem Code nötig ist, damit die PLV läuft
und ein Migrationsfall geführt werden kann: die Ablage des Tagesbetriebs
(`daten/`), die Linie mit ihrer Ordnungslinie und den Erstabnahmen (`linie/`)
und (außerhalb von beidem) die Schlüssel der Rollen, die
Zeichnungsordnung und das Mandat. Die Welt startet ohne übernommenen
Bestand; ein Fall bringt ihn hinein. Je Fall eine eigene Welt: So berührt
kein Fall die Laufzeit eines anderen. Der Arbeitsbereich des Falls liegt
nicht in der Welt, sondern im Codebaum unter `faelle/<name>`; ein zweiter
Lauf desselben Falls braucht deshalb einen eigenen Codebaum, oder der Fall
wird vorher nach `faelle/archiv/` verschoben.

Die Skripte hier fahren die Bedienfolgen, die in ADR-025 (Erstabnahmen),
ADR-026 (Fallauftrag) und `plv/betrieb/README.md` (Ablage) beschrieben sind:
jeden Schritt als Systemkommando, mit Halt beim ersten Fehler und einem
Protokoll in der Welt. Sie rechnen und prüfen nichts selbst.

| Datei | Zweck |
|---|---|
| `welt_aufstellen.sh` | Schlüssel und Ordnung (für eine Welt mit eigenen Schlüsseln), Ablage, Linie, Erstabnahmen |
| `fall_starten.sh` | Fall anlegen, Lieferung registrieren, Vorlage des Fallauftrags |
| `fall_zeichnen.sh` | ein Gate des Falls zeichnen, mit dem Ring, den das Gate braucht |
| `zugang.sh` | den abgenommenen Bestand des Falls in die Ablage der Welt bringen: Probe, Neuaufsetzen, Aufbaulauf, Anfangsbestand |
| `fall_nachfahren.sh` | einen festgehaltenen Fall (ein Paket) ohne Agenten nachfahren, bis zum Ende oder bis zu einem Haltepunkt |
| `paket_bauen.sh` | aus einem geführten Fall das Paket zum Nachfahren bauen |
| `laufzeit_aufstellen.sh` | Welt und festgehaltenen Fall in einem Aufruf: die Welt auf dem Stand vor dem Fall, der Fall auf dem Stand danach |
| `abgenommen.py` | der Commit, auf dem eine Linie ein Gate angenommen hat (gelesen von den Skripten) |
| `gezeichnet.py` | ob ein Mensch ein Gate schon selbst gezeichnet hat (gelesen vom Nachfahren) |
| `fall-baldrian-klv-tg2015.conf` | der Fall der Vorführung: Lieferung, Stichtag, Auftrag |
| `einstellungen.beispiel.conf` | Vorlage der Einstellungen für eine Welt mit vorhandenen Schlüsseln |
| `mandat.vorlage.txt` | Vorlage des Mandats der simulierten Rollen |
| `stellungnahme-tbox-020.json` | aktuarielle Stellungnahme zur T-Box 0.2.0, Pflichtbeleg der Erstabnahme A-O1 |

Alle Aufrufe vom Wurzelverzeichnis des Codebaums, mit eingerichtetem
`.venv`. Der Baum muss sauber sein (`git status` leer) und darf sich
während des Aufstellens nicht bewegen: Die Abnahmen pinnen seinen Stand.

## Eine Welt mit eigenen Schlüsseln

Für Vorführung, Übung und Probe. Ein Aufruf:

```
werkzeuge/welt/welt_aufstellen.sh <welt>
```

`<welt>` ist ein neues Verzeichnis außerhalb des Codebaums, etwa
`~/plv-welt`. Die vier Phasen laufen nacheinander und sind einzeln
aufrufbar (`werkzeuge/welt/welt_aufstellen.sh <welt> <phase>`):

| Phase | Was entsteht |
|---|---|
| `schluessel` | je Rolle ein Schlüssel unter `~/.plv-schluessel` (64 zufällige Byte, 0600, nie angezeigt), die Zeichnungsordnung, das Mandat `<welt>/mandate/mandat.txt`, die Einstellungen `<welt>/einstellungen.conf` |
| `ablage` | `<welt>/daten`: die Ablage der PLV ohne übernommenen Bestand, geführt bis zum Tag vor dem Zugang |
| `linie` | `<welt>/linie` mit dem ersten Glied der Ordnungslinie |
| `abnahmen` | die Erstabnahmen A-K2, A-O1, A-T1 und A-B3, der gebundene Anfangsbestand |

Die Phase `ablage` rechnet einige Minuten, die übrigen Sekunden. Am Ende
steht `WELT STEHT: ...` mit den vier Abnahmen; das Protokoll liegt unter
`<welt>/aufstellen.log`.

Was die Phase `schluessel` festlegt, lässt sich beim Aufruf setzen:
`SCHLUESSEL` (Verzeichnis der Schlüssel), `BIS` (letzter Tag der Ablage),
`VON` (Vergleichsstand der Erstabnahme), `MANDATGEBER`, `ENTSCHEIDER`.
Alle Skripte nehmen außerdem `BAUM` (der Codebaum, auf dem gerechnet
wird; Vorgabe ist der Klon, in dem das Skript liegt) und `PYTHON` (der
Interpreter; Vorgabe ist `$BAUM/.venv/bin/python`).

- **Kein Schlüssel wird überschrieben, keiner verlässt den Rechner.**
  Trägt das Schlüsselverzeichnis schon eine Ordnung, hält das Skript an;
  eine zweite Welt bekommt ein eigenes Verzeichnis (`SCHLUESSEL=...`).
- **Alle menschlichen Rollen haben die Schlüsselklasse `simulation`.** Jede
  ihrer Zeichnungen weist sich als simuliert aus und nennt das Mandat. Der
  Schlüssel des Tageslaufs hat die Klasse `betrieb` und zeichnet nur
  Urheberschaft. Die
  Schlüssel sind symmetrisch: Wer eine Zeichnung prüfen kann, kann sie auch
  leisten. Wer in einer Übung welche Rolle zeichnet, ist deshalb eine Regel
  der Leitung, keine Eigenschaft der Technik.

## Eine Welt mit vorhandenen Schlüsseln

Wer Schlüssel und Zeichnungsordnung schon hat, legt
`<welt>/einstellungen.conf` nach `einstellungen.beispiel.conf` selbst an und
ruft die Phasen `ablage`, `linie` und `abnahmen` auf. Die Phase `schluessel`
wird übersprungen, sobald die Einstellungen liegen.

## Einen Fall starten

```
werkzeuge/welt/fall_starten.sh <welt> anlegen migrationen/baldrian/fall-baldrian-klv-tg2015.conf
werkzeuge/welt/fall_starten.sh <welt> vorlage
```

`anlegen` legt den Fall unter `faelle/<name>` an und registriert die
Lieferung laut Falldatei; die Falldatei liegt danach als `<welt>/fall.conf`
in der Welt. `vorlage` erzeugt die Vorlage des Fallauftrags
(`faelle/<name>/abgeleitet/auftrag/fallauftrag.md`) und, falls er noch nicht
liegt, den Schlüssel der Programmleitung. Beides zeichnet nichts. Nach einer
Nachlieferung der Quelle erzeugt `vorlage` die Vorlage neu.

Den Auftrag zeichnet der Vorstand:

```
werkzeuge/welt/fall_zeichnen.sh <welt> A-M6 angenommen "<begruendung>"
```

## Zeichnen

```
werkzeuge/welt/fall_zeichnen.sh <welt> <gate> angenommen|abgelehnt "<begruendung>"
werkzeuge/welt/fall_zeichnen.sh <welt> ring <gate>
```

Das Skript reicht je Gate den Ring: zuerst die Schlüssel, gegen die das
Gate fremde Ketten prüft (immer der des Vorstands: Fallauftrag und Glieder
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

`ring <gate>` gibt nur die Argumente aus, für Kommandos, die denselben Ring
brauchen (`ontologie.entscheide`, die Kommandos des Zugangs). Was vor einer
Zeichnung vorliegen muss, sagt der Skill `migrationsfall-durchfuehren`; das
Gate prüft es und nennt, was fehlt.

## Der Zugang in die Ablage

Nach der Migrationsabnahme (A-M4) kommt der übernommene Bestand in die
Ablage der Welt (ADR-022; die Bedienfolge und ihre Begründung stehen in
`plv/betrieb/README.md`, „Reihenfolge des Hochziehens“):

```
werkzeuge/welt/zugang.sh <welt> probe
werkzeuge/welt/fall_zeichnen.sh <welt> A-B2 angenommen "<begruendung>"
werkzeuge/welt/zugang.sh <welt> aufsetzen
werkzeuge/welt/zugang.sh <welt> aufbau [<heute>]
werkzeuge/welt/zugang.sh <welt> belegen
werkzeuge/welt/zugang.sh <welt> ab3 "<begruendung>"
werkzeuge/welt/zugang.sh <welt> binden
```

| Phase | Was geschieht | Vor dem nächsten Schritt lesen |
|---|---|---|
| `probe` | Zugangsprobe auf einer leeren Ablage mit der Config des Falls: zwei Läufe vom Betriebsbeginn über den Stichtag, mit und ohne Zugang | `faelle/<name>/abgeleitet/berichte/zugangsprobe.json` — als Lesefassung: `python system/lagebild.py zugangsprobe --fall faelle/<name>` —, dann A-B2 zeichnen |
| `aufsetzen` | die Ablage der Welt neu aufsetzen; die bisherige wird zu `<welt>/daten.archiv-<zeit>` und bleibt der Vergleichsstand ohne den übernommenen Bestand | |
| `aufbau` | Aufbaulauf vom Betriebsbeginn bis `<heute>` (ohne Angabe: der heutige Tag) | |
| `belegen` | den Anfangsbestand der neuen Ablage belegen | `<welt>/linie/abgeleitet/anfangsbestand/beleg.md` |
| `ab3` | A-B3 in der Linie zeichnen, als Betrieb | |
| `binden` | den Anfangsbestand binden, danach ein Tageslauf | |

Am Ende steht `ZUGANG STEHT: ...` mit der Zahl der Abschlüsse; das Protokoll
liegt unter `<welt>/zugang.log`. Mit dem Bestand der Vorführung rechnet die
Probe rund 20 Minuten, der Aufbaulauf rund 11. Zwischen Probe und Aufbaulauf darf
sich der Codebaum nicht bewegen: Der erste Lauf, der den Eingang führt, hält
Config, Kernversion und Fingerabdruck des Pakets gegen die Probe.

## Einen festgehaltenen Fall nachfahren

Ein Fall, der einmal geführt wurde, lässt sich ohne Agenten wiederholen:
Was Agenten und Menschen darin erarbeitet haben, wird mitgebracht; was das
System rechnet, rechnet es neu; gezeichnet wird neu, mit den Schlüsseln der
Welt. So wird eine Laufzeit aus dem Stand des Repositorys neu aufgestellt,
ein Fall nach einer Code-Änderung gegengeprüft oder in einer Übung an
eine bestimmte Stelle „vorgespult“.

```
werkzeuge/welt/fall_nachfahren.sh <welt> <paket> [--bis <haltepunkt>] [--wechseln]
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
| `SHA256SUMS` | Prüfsummen aller Dateien des Pakets |

Im Paket liegen keine Schlüssel und keine Zeichnungen. Das Skript fährt
nur ein Paket, das seinen Prüfsummen entspricht und keine Datei darüber
hinaus trägt.

Der festgehaltene Fall 3 liegt als Paket unter
`pakete/baldrian-klv-tg2015-fall3/` (Stand vor dem Fall: `8c1bed3`). Es
trägt die Auflösung des Falls: Es ist zum Nachfahren da, nicht als
Lesestoff für einen Lauf, der denselben Fall live führt.

Im **Rezept** stehen nur diese Helfer, je Zeile einer (Fortsetzungszeilen
mit `\`); eine andere Zeile verweigert das Skript, bevor es beginnt:

| Helfer | Wirkung |
|---|---|
| `anlegen` | Fall anlegen, Lieferung laut `fall.conf` registrieren |
| `vorlage` | die Vorlage des Auftrags erzeugen (auch neu, nach einer Nachlieferung) |
| `registriere <pfad>` | `nachlieferung/<pfad>` im Fall registrieren |
| `einlegen <pfad>` | `erarbeitet/<pfad>` in den Fall legen, nie über eine andere Datei hinweg |
| `schritt "<name>" <kommando ...>` | ein Kommando fahren; ein Exit ungleich null hält an |
| `entscheide <diskrepanz> <wert> "<begruendung>" [--beleg <pfad>]` | eine Diskrepanz der Quellen endgültig auflösen, als Aktuariat |
| `entscheide_alle <quelle> "<begruendung>"` | alle vorläufig aufgelösten Diskrepanzen zur Lesart dieser Quelle entscheiden |
| `zeichne <gate> "<begruendung>"` | das Gate annehmen, mit dem Ring der Welt — es sei denn, ein Mensch hat es schon selbst gezeichnet |
| `zugang <phase> [argument]` | eine Phase des Zugangs fahren (`zugang.sh`): `probe`, `aufsetzen`, `aufbau [<heute>]`, `belegen`, `ab3 "<begruendung>"`, `binden` |
| `haltepunkt <name>` | hier endet ein Lauf mit `--bis <name>` |
| `erwarte <pfad im fall>` | die Datei gegen `ERWARTUNG` halten; andere Bytes halten an |

In den Kommandos stehen `$PY` (der Interpreter), `$F` (`faelle/<name>`),
`$A` (`$F/abgeleitet`), `$WELT`, `$LINIE`, `$ORDNUNG`, `$STICHTAG`, `$PAKET`,
`$(ring <gate>)` für Kommandos, die den Ring eines Gates brauchen, und
`$(abgenommen <gate>)` für den Commit, auf dem die Linie der Welt das Gate
zuletzt angenommen hat.

- **Nichts läuft doppelt.** Ein Lauf merkt sich, wie weit er kam
  (`<welt>/nachfahren.stand`). Derselbe Aufruf, ohne `--bis` oder mit einem
  späteren Haltepunkt, fährt hinter dem letzten erledigten Schritt weiter,
  nach einem Haltepunkt ebenso wie nach einem behobenen Fehler. Protokoll:
  `<welt>/nachfahren.log`. Die Namen der Haltepunkte nennt
  `pakete/README.md`.
- **Entscheidungen werden neu getroffen, nicht mitgebracht.** Die Auflösung
  einer Diskrepanz trägt in der A-Box die Zeichnung ihrer Rolle. Eine
  mitgebrachte A-Box trüge die Schlüssel des festgehaltenen Laufs; deshalb
  legt das Rezept die Fragmente ein, lässt zusammenführen und entscheidet
  mit `entscheide` unter den Schlüsseln der Welt.
- **Verglichen werden Ergebnisse, nicht Zeichnungen.** `erwarte` hält
  Bytes gegen den festgehaltenen Fall; Snapshots und Belege tragen die
  Schlüssel und Zeiten des Laufs und sind deshalb nie gleich.
- **Eine Zeichnung beim Nachfahren übernimmt ein Urteil, sie fällt keins.**
  Das trägt nur, wenn der Gegenstand derselbe ist. Wo das Rezept ein Gate
  zeichnet, hält es deshalb vorher den Gegenstand gegen den festgehaltenen
  Fall: mit `erwarte` (Spez, Tabellen, Abnahmebericht) oder mit einem
  Schritt, der Fingerabdrücke vergleicht (Kern, Tarifwerk). Weicht der
  Gegenstand ab, hält der Lauf; dann urteilt ein Mensch.
- **Wer selbst zeichnet, dessen Zeichnung gilt.** An einem Haltepunkt kann
  ein Mensch die Vorlage lesen und das Gate selbst zeichnen
  (`fall_zeichnen.sh <welt> <gate> angenommen "<begruendung>"`, für den
  Anfangsbestand `zugang.sh <welt> ab3 "<begruendung>"`). Fährt der Lauf
  danach weiter, zeichnet das Rezept dieses Gate nicht noch einmal: Die
  k-te Zeichnung eines Gates im Rezept gilt als geleistet, wenn im Fall k
  Annahmen liegen; der Anfangsbestand, wenn eine Annahme genau den Beleg
  pinnt, der in der Linie liegt. Ist die jüngste Zeichnung des Gates eine
  **Ablehnung**, hält der Lauf: über eine Ablehnung zeichnet das Rezept
  nie hinweg; danach führt ein Mensch den Fall weiter. Das ist eine
  Anzeige, kein Urteil: Ob eine Zeichnung gilt, prüfen die Gates der
  folgenden Schritte.
- **Das Rezept nennt keinen Commit.** Ein Beleg, der die Änderung des
  Zielsystems gegen den abgenommenen Stand zeigt (`kernstand_belegen`,
  `tarifwerk_belegen`), bekommt sein `--von` aus der Linie der Welt:
  `--von "$(abgenommen A-K2)"`. So lässt sich ein Fall in jeder Welt
  nachfahren, deren Linie auf dem Stand vor dem Fall abgenommen wurde.
- **Zwei Stände des Codebaums.** Hat der Fall das Zielsystem geändert
  (Kern, Tafeln, Config), wird die Welt auf dem Stand vor dem Fall
  aufgestellt und der Fall auf dem Stand danach nachgefahren. Die Änderung
  selbst baut das Rezept nicht: sie liegt als Commits im Codebaum, das
  Rezept belegt und zeichnet sie.
- **Der Fall der Welt.** Führt die Welt schon einen anderen Fall, hält
  das Skript an. `--wechseln` legt dessen Falldatei beiseite
  (`<welt>/fall-frueher-<name>.conf`) und macht den nachgefahrenen Fall zum
  Fall der Welt; der frühere Fall bleibt liegen. Eine Welt fährt ein Paket
  nach.

### Welt und Fall in einem Aufruf

```
werkzeuge/welt/laufzeit_aufstellen.sh <welt> <paket> [--bis <haltepunkt>]
```

Stellt die Welt auf dem Stand auf, den das Paket nennt (`STAND`), und fährt
danach das Paket auf dem Stand dieses Baums nach. Der Stand vor dem Fall
liegt dabei als eigener Baum in der Welt (`<welt>/baum-vor`, ein Klon dieses
Baums auf dem Commit); der Codebaum selbst wird nicht bewegt. Der Commit muss
ein Vorfahr des Baums sein; ein Paket aus einer anderen Geschichte des
Repositorys hält das Skript an, bevor es etwas anlegt.

Die Schlüssel der Welt liegen dabei unter `~/.plv-schluessel/<name der
welt>` (anders nur mit `SCHLUESSEL=...`): je Welt ein eigenes Verzeichnis.
Bricht das Aufstellen ab, bevor der Fall angelegt ist, beginnt ein neuer
Versuch unter einem anderen Namen der Welt; die angefangene bleibt liegen,
bis jemand sie ansieht und entfernt. Liegt der Fall schon im Codebaum,
hält ein Lauf in einer neuen Welt an: Ein Fall wird nie überschrieben.

Derselbe Aufruf ist wiederholbar: Steht die Welt schon, fährt er nur das
Paket weiter, hinter dem letzten erledigten Schritt. So wird aus dem Stand
des Repositorys und einem Paket eine Laufzeit mit übernommenem Bestand,
oder, mit `--bis`, eine Welt an der Stelle des Falls, an der eine Übung
beginnen soll.

### Das Paket bauen

```
werkzeuge/welt/paket_bauen.sh <welt> <ziel> --rezept <rezept.sh> \
    [--erarbeitet <liste>] [--erwartung <liste>] [--linie <linie>]
```

Aus dem Fall der Welt entsteht das Verzeichnis `<ziel>`: die Falldatei, das
Rezept, je Zeile der Liste `--erarbeitet` eine Datei oder ein Verzeichnis
des Falls, jede Datei des Eingangs, die nicht zur Lieferung der Falldatei
gehört (die Nachlieferungen), je Zeile der Liste `--erwartung` die
Prüfsumme der Datei im Fall, der Stand vor dem Fall und die Prüfsummen des
Pakets. Die Listen nennen Pfade relativ zum Fall, eine je Zeile.

Den Stand vor dem Fall liest das Skript aus der Linie der Welt (`<welt>/linie`
oder `--linie`): der Commit, auf dem die Linie den Kern angenommen hat, auf
den der Fallauftrag den Fall gestellt hat. Er wird gelesen, nie angegeben;
eine Linie ohne solche Annahme ergibt kein Paket, eine Welt ohne Linie ein
Paket ohne `STAND` (das sich nachfahren, aber nicht in einem Aufruf
aufstellen lässt).

Was erarbeitet ist und welche Ergebnisse byteweise gleich sein müssen,
entscheidet, wer das Rezept schreibt. Das Skript hält Rezept und Paket
zusammen: Jedes `einlegen`, `registriere` und `erwarte` des Rezepts muss im
Paket seine Datei bzw. seinen Eintrag haben, sonst entsteht kein Paket.
Zeichnungen (`entscheide/`) nimmt es nie auf, und ein vorhandenes Paket
überschreibt es nie.

Was als Erwartung taugt: Ergebnisse, die nur vom Inhalt abhängen: Tabellen,
übersetzte Zeilen, die Spez, Berichte. Belege, die Zweig und Commit des
Codebaums nennen (die Ergebnisse der Tests, der Suite, der Führungsprobe),
sind nur auf dem festgehaltenen Stand selbst byte-gleich, nicht auf einem
Stand mit demselben Inhalt unter anderem Namen; und was Zeiten, Schlüssel,
Entscheider oder Pfade des Rechners trägt, ist es nie.

## Grenzen

- Die Skripte führen einen Fall von der Lieferung bis zum gebundenen
  Anfangsbestand der Ablage. Die Veröffentlichung eines Stands (A-B1) und
  ein Glied der Ordnungslinie sind hier nicht gefasst.
- Eine Welt führt einen Fall zur Zeit. Ein zweiter bekommt eine zweite
  Welt, oder löst den ersten ab, wenn er nachgefahren wird (`--wechseln`).
- Das Skript zum Nachfahren fährt ein Paket. Das Paket von Fall 3 liegt
  unter `pakete/`. Es trägt die Auflösung des Falls und ist zum Nachfahren
  da, nicht als Lesestoff für Agenten oder Menschen, die denselben Fall
  live führen (`pakete/README.md`).
- Ein Rezept ist an ein Paket gebunden: Wird es geändert, gilt der Stand
  eines begonnenen Laufs nicht mehr, und das neue Paket braucht eine neue
  Welt.
- Mandat und Stellungnahme sind Vorlagen der Vorführung. Wer eine Welt für
  einen anderen Zweck aufstellt, schreibt beide selbst und nennt sie in den
  Einstellungen.
