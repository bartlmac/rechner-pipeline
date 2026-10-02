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

## Grenzen

- Die Skripte fuehren bis zur Zeichnung im Fall. Der Zugang des abgenommenen
  Bestands in die Ablage (Probe, A-B2, Neuaufsetzen, A-B3) ist hier nicht
  gefasst; seine Bedienfolge steht in `deploy/plv/README.md`.
- Eine Welt fuehrt einen Fall. Ein zweiter Fall bekommt eine zweite Welt.
- Mandat und Stellungnahme sind Vorlagen der Vorfuehrung. Wer eine Welt fuer
  einen anderen Zweck aufstellt, schreibt beide selbst und nennt sie in den
  Einstellungen.
