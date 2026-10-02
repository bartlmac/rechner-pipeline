# Arbeitsumgebung auf einem fremden Rechner

Wer einen Fall vorfuehrt oder in einem Workshop selbst faehrt, braucht das
System auf einem Rechner, der weder dieses Repository noch einen Zugang zu
dessen Herkunft hat. Dieses Verzeichnis liefert dafuer eine **Installation
in einer Datei**: ein Abbild mit Betriebssystem, Python, den gepinnten
Abhaengigkeiten, den Werkzeugen und den Code-Baeumen auf festen Marken.
Auf dem Zielrechner richtet ein Skript das Abbild ein — unter Windows als
eigene WSL-Distribution. Danach braucht der Rechner kein Netz.

| Datei | Zweck |
|---|---|
| `Dockerfile` | die Umgebung: Debian 12 mit dessen Python 3.11, Installation der Pins wie die CI, git, tmux, watch, script, ein unprivilegierter Benutzer `plv` |
| `einrichten.sh` | laeuft IN der Umgebung (dort als `plv-einrichten`): Code-Baeume anlegen, auf eine neue Marke ziehen, Selbstpruefung |
| `abbild_bauen.sh` | baut das Image, legt darin die Baeume an, prueft sie in einem Container ohne Netz und exportiert das Dateisystem als `tar.gz` |
| `einrichten.ps1` | richtet einen Windows-Rechner ein: WSL 2 pruefen bzw. einschalten, Abbild importieren, Selbstpruefung, Verknuepfung |
| `wsl.conf`, `profil.sh` | Anmeldebenutzer und Shell-Umgebung der Distribution |

## Was im Abbild liegt — und was nicht

Im Abbild liegen:

- Debian 12 mit Python 3.11 der Distribution und den exakt gepinnten
  Abhaengigkeiten aus `requirements-dev.txt`. Das ist das System der
  Beispielumgebung: Ein eingerichteter Rechner haelt seine Ergebnisse
  byteweise gegen die dort gerechneten.
- `~/rechner-pipeline`, der Code-Baum auf der genannten Marke, und auf
  Wunsch `~/rechner-pipeline-basis`, ein zweiter Baum auf einer zweiten
  Marke (der Stand, auf dem ein Fall live startet). Jeder Baum hat sein
  eigenes `.venv`; das Paket kommt aus genau diesem Baum.
- Von der Geschichte des Repositorys nur die der genannten Marken. `origin`
  nennt die oeffentliche Adresse, wird aber nie gebraucht.
- Auf Wunsch ein **Paket**: ein festgehaltener Fall zum Nachfahren, unter
  `~/pakete/<name>` — neben den Baeumen, nicht darin. Aus Baum und Paket
  stellt ein Aufruf auf dem Zielrechner die Laufzeit auf (siehe unten).

Im Abbild liegen NICHT:

- **Schluessel.** Jeder Rechner erzeugt seine eigenen
  (`deploy/welt/welt_aufstellen.sh`); kein Schluessel reist.
- **Welt und gefuehrte Faelle** (Linie, Ablage, Falldaten, Zeichnungen).
  Sie entstehen auf dem Rechner, auf dem gearbeitet wird — mit den Skripten
  unter `deploy/welt/` (`deploy/welt/README.md`). Ein Paket ist kein
  gefuehrter Fall: Es traegt, was erarbeitet und nachgeliefert wurde, aber
  keine Zeichnung und keinen Schluessel.
- **Unveroeffentlichte Arbeit**, es sei denn, der Bau wurde ausdruecklich
  so aufgerufen (`--unveroeffentlicht`).
- Ein Agenten-Werkzeug (Claude Code, Codex). Wer agentisch arbeitet,
  installiert es in der Umgebung und meldet sich dort an. Ob es die
  Sitzungen der Vorfuehrung traegt, zeigt `werkzeuge/sitzungsprobe.py`
  (`werkzeuge/README.md`).

## Das Abbild bauen

Vom Repo-Wurzelverzeichnis, auf einem Linux-Rechner mit Docker:

```
deploy/workshop/abbild_bauen.sh --marke <tag|zweig> [--basis <tag|zweig>] [--paket <verzeichnis>]
```

Das Ergebnis liegt unter `runs/workshop/` (nicht versioniert):
`plv-arbeitsumgebung-<marke>.tar.gz` und daneben die Pruefsumme
`...tar.gz.sha256`. Beide Dateien gehoeren zusammen auf den Datentraeger
oder die Freigabe, von der die Zielrechner sie holen.

- Die Baeume entstehen in einem Container **ohne Netz**, und die
  Selbstpruefung laeuft dort mit: Ein Abbild, das der Bau schreibt, hat sie
  bestanden.
- Eine Marke, die nicht in `origin/main` liegt, haelt den Bau an. Fuer eine
  Probe auf dem eigenen Rechner gibt es `--unveroeffentlicht` — das Abbild
  traegt dann unveroeffentlichte Arbeit und gehoert nicht auf fremde Rechner,
  solange das niemand so entschieden hat.
- Ein vorhandenes Abbild wird nie ueberschrieben.
- Ein Paket (`--paket`) reist nur mit, wenn es seinen Pruefsummen
  entspricht; geprueft wird vor dem Bau und noch einmal im Abbild. Ein Paket
  traegt die Aufloesung seines Falls — wer denselben Fall auf dem Zielrechner
  mit Agenten fuehren laesst, baut das Abbild ohne.

## Einen Windows-Rechner einrichten

Voraussetzungen: Windows 11 oder Windows 10 ab Version 2004, eingeschaltete
Virtualisierung in der Firmware (BIOS/UEFI), einmalig Administratorrechte.
Auf dem Rechner liegen drei Dateien nebeneinander: `einrichten.ps1`, das
Abbild und seine `.sha256`.

1. Nur wenn WSL auf dem Rechner noch fehlt — in einer PowerShell
   **"Als Administrator"**:

   ```
   powershell -ExecutionPolicy Bypass -File einrichten.ps1 -Abbild <abbild.tar.gz>
   ```

   Das Skript schaltet WSL ein und haelt an. **Rechner neu starten.**

2. In einer gewoehnlichen PowerShell (ohne Administrator) derselbe Aufruf.
   Das Skript prueft die Pruefsumme, importiert das Abbild als Distribution
   `PLV-Arbeitsumgebung`, faehrt die Selbstpruefung und legt eine
   Verknuepfung auf den Schreibtisch.

Statt der lokalen Datei nimmt das Skript eine Adresse (`-AbbildUrl <adresse>
-Pruefsumme <sha256>`); ein Freigabelink muss die Datei selbst liefern, nicht
eine Vorschauseite.

Gestartet wird die Umgebung ueber die Verknuepfung oder mit
`wsl -d PLV-Arbeitsumgebung`. Darin:

```
cd ~/rechner-pipeline
source .venv/bin/activate
```

Gibt es die Distribution schon, haelt das Skript an. `-Ersetzen` entfernt
sie **samt allem, was darin liegt** (Faelle, Schluessel, eigene Arbeit) und
importiert neu. Entfernen ohne neuen Import: `wsl --unregister
PLV-Arbeitsumgebung`.

## Die Laufzeit aufstellen

Liegt ein Paket im Abbild, entsteht auf dem eingerichteten Rechner die
Laufzeit mit dem uebernommenen Bestand in einem Aufruf — mit eigenen
Schluesseln, ohne Netz, ohne Agenten:

```
cd ~/rechner-pipeline
deploy/welt/laufzeit_aufstellen.sh ~/plv-welt ~/pakete/<name>
```

Das rechnet rund eine Dreiviertelstunde (Welt aufstellen, Fall nachfahren,
Zugang). Mit `--bis <haltepunkt>` endet der Lauf an einer Stelle des Falls,
etwa vor einer Abnahme; derselbe Aufruf ohne `--bis` faehrt spaeter weiter.
Welche Haltepunkte es gibt, steht im Rezept des Pakets
(`grep haltepunkt ~/pakete/<name>/rezept.sh`). Einzelheiten:
`deploy/welt/README.md`.

## Selbstpruefung

```
plv-einrichten pruefen               # Sekunden
plv-einrichten pruefen --gruendlich  # volle Suite je Baum, einige Minuten
```

Geprueft wird: Python 3.11, die Werkzeuge, und je Baum der Stand gegen seine
Marke, dass das Paket aus DIESEM Baum geladen wird (die Falle zweier Baeume
nebeneinander), die Geschlossenheit der Abhaengigkeiten und die Referenzwerte
des Rechenkerns. `ERGEBNIS: bereit` und Exit 0 heisst: Dieser Rechner rechnet,
was die Referenzwerte verlangen.

## Einen Baum auf eine neue Marke ziehen

Ohne neues Abbild, in der Umgebung:

```
plv-einrichten baum --quelle <adresse|pfad|buendel> --marke <tag|zweig> [--name rechner-pipeline]
```

`--quelle` ist eine Git-Adresse, ein Pfad oder eine Buendeldatei
(`git bundle create stand.bundle <marke>` auf dem Quellrechner; unter
Windows abgelegte Dateien liegen in der Umgebung unter `/mnt/c/...`). So
kommt ein neuer Stand auch ohne Netz auf den Rechner.

Nachgezogen wird nur ein unberuehrter Baum. Liegt darin nicht committete
Arbeit oder ein eigener Commit, haelt das Skript an und laesst alles, wie es
ist; fuer die neue Marke legt man dann mit `--name` einen zweiten Baum an.
Von git ignorierte Verzeichnisse (`faelle/`, `runs/`) bleiben beim
Nachziehen liegen.

## Grenzen

- Der Windows-Teil (`einrichten.ps1`) laesst sich in der Suite nicht fahren.
  Vor dem Einsatz auf mehreren Rechnern einmal auf einem Rechner derselben
  Bauart einrichten.
- Gleiche Ergebnisse folgen aus dem gleichen System, nicht aus einer
  Zusicherung. Die Selbstpruefung haelt die Referenzwerte des Rechenkerns;
  dass ein ganzer Fall auf einem eingerichteten Rechner dieselben Bytes
  ergibt wie in der Beispielumgebung, belegt sie nicht. Das belegt erst das
  Nachfahren eines Pakets: Es haelt an, sobald ein Ergebnis andere Bytes
  traegt als im festgehaltenen Fall (die Erwartung des Pakets).
- Die Umgebung ist fuer Vorfuehrung und Uebung gedacht. Der Tagesbetrieb
  laeuft aus dem Laufzeit-Image (`deploy/plv/`).
