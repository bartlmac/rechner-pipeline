# Werkzeuge der Vorfuehrung

Beobachtungshilfen, **kein Bestandteil der Migrations-Pipeline**. Sie
lesen ein Herstellerformat (Claude-Code-Sitzungstranskripte) und stellen
Laeufe dar; die Fachlichkeit liegt unter `src/`. Die Trennung ist
absichtlich sichtbar — die allgemeine Frage, was versionierter
Repo-Bestandteil wird und was eine gekennzeichnete Beispielandockung
bleibt, steht in `dev-docs/offene-punkte.md`.

| Werkzeug | Zweck |
|---|---|
| `verlaufsprotokoll.py` | Sitzungstranskript zu einem lesbaren Verlauf |
| `vorzeigeseite.py` | Datenmodell und Artefakte eines Falls zu einer statischen Seite |
| `unternehmensseite.py` | die Seiten des fiktiven Unternehmens zusammenbauen |
| `auftritt.py` | den ganzen Entwurf mit einem Kommando aus den Quellen bauen |
| `drift.py` | den veroeffentlichten Stand gegen den Entwurf halten |
| `umbaubudget.py` | wie weit ein Lauf das System umgebaut hat |
| `falldaten.py` | Datenmodell einer Falldarstellung aus den Artefakten |
| `fallbericht.py` | Darstellung aus dem Datenmodell rendern |
| `vorschau.py` | den Entwurf der Seite lokal ansehen, vor dem Schieben |

## Verlauf eines Laufs protokollieren

```
python werkzeuge/verlaufsprotokoll.py --neueste --out verlauf.md
python werkzeuge/verlaufsprotokoll.py --sitzung <uuid> --mit-denken
```

Trennt Mensch, Konsole, Operator und Werkzeug; Entscheide werden
hervorgehoben. Schluesselpfade und Geheimnisse sind redigiert.

## Die Seite bauen

Die Vorfuehrung tritt als Unternehmensauftritt der (frei erfundenen)
Pfefferminzia Lebensversicherung AG auf. Die Unternehmensseiten sind
handgeschriebene, versionierte Quellen unter `vorzeige-seite/`; die
Migrationsberichte entstehen je Fall aus den Artefakten und haengen
unter `migrationen/<fall>/`. Jede Unternehmensseite MUSS die
Fiktions-Banderole tragen — `unternehmensseite.py` baut sonst nicht.

Der Entwurf wird nicht gepflegt, sondern ERZEUGT — ein Kommando faehrt
die ganze Kette aus den aktuellen Quellen (Datenmodell, Fall-Seite,
Unternehmensseiten samt Fachdoku, Landkarte und Techstack, Vorschau).
So kann der Entwurf nicht hinter Codebasis oder Fall-Artefakten
zurueckbleiben; vor Sichtung und Veroeffentlichung einmal laufen
lassen:

```
python werkzeuge/auftritt.py --fall faelle/baldrian-uebernahme \
    --name baldrian \
    --abzug baldrian_bestandsabzug_2026-01-01.csv \
    --abzug baldrian_bestandsabzug_2027-01-01.csv \
    [--verlauf verlauf.md]
```

`--name` ist das URL-Segment unter `migrationen/`, so wie die
Unternehmensseiten den Fall verlinken. Die Schritte der Kette bleiben
einzeln aufrufbar (`falldaten.py`, `vorzeigeseite.py
--als-unterseite`, `unternehmensseite.py`, `vorschau.py`).

Die Zahlen der Seite kommen aus dem Datenmodell (`falldaten.py`) —
demselben, aus dem auch der Fallbericht gerendert wird. Seite und
Bericht tragen damit dieselben Zahlen aus derselben Quelle; frueher
lasen beide die Fall-Artefakte getrennt, und zwei Leser desselben
Datenraums driften auseinander. Was die Seite selbst tut, ist
Veroeffentlichung: Artefakte ueber die Positivliste kopieren, die Regie
sperren, Systemstand und Branch stempeln, `index.md`, `_config.yml` und
`artefakte/` schreiben.

Das Umbaubudget des Laufs ist ein Pflichtabschnitt des Modells: Ein
abgeschlossener Fall traegt die Messung immer — ein Lauf, dessen Umbau
niemand gemessen hat, saehe sonst aus wie ein Lauf ohne Umbau. Fehlt
sie, meldet `falldaten.py` eine Luecke (Exit 3). Erhoben wird sie in
den Fall:

```
python werkzeuge/umbaubudget.py --basis <startpunkt> \
    --json faelle/<fall>/abgeleitet/berichte/umbaubudget.json
```

Die Seite rechnet nichts nach. Jede Zahl steht so in einem Artefakt, das
unter `artefakte/` daneben liegt — sonst waere die Vorfuehrung eine
Behauptung ueber sich selbst. Verlinkt wird nur, was die Positivliste
tatsaechlich kopiert hat, und die Regie-Sperre prueft auch die Verweise
aus dem Modell noch einmal selbst. Ein NICHT bestandener Test und eine
gerissene Schranke werden genauso dargestellt wie ein gruener Lauf; eine
Seite, die nur den Erfolgsfall zeigen kann, waere eine Werbebroschuere.

## Umfang eines Laufs messen

```
python werkzeuge/umbaubudget.py --basis <startpunkt-des-laufs> \
    [--json runs/umbaubudget.json] \
    [--ueberschreitung-begruendet "<ein Satz>"]
```

`--basis` ist der Stand, auf dem der Lauf AUFGESETZT hat — nicht `main`,
sonst misst man die Vorgeschichte mit.

Wer einen Migrationsfall loest, darf Code aendern, die Ontologie
erweitern und Gates umbauen. Was er nicht soll, ist das System nebenbei
durch ein anderes ersetzen — etwa den Rechenkern von der
Thiele-Rekursion auf Kommutationszahlen zurueckdrehen, weil das gerade
der kuerzere Weg zum gruenen Gate waere. Absicht laesst sich nicht
abfragen, Umfang schon.

Deshalb wiegt **Loeschen schwerer als Hinzufuegen**: Hinzufuegen ist der
Auftrag, Loeschen ist Ersetzen. Das Gesamtbudget traegt viel (18.000
Zeilen in `src/` und `tests/`), die Loeschbudgets wenig und je Schicht
getrennt (`kern/` und `ontologie/` je 450, alles uebrige 1.200).

Daneben stehen **Stolperdraehte**, die keine Budgetfrage sind, sondern
eine Architekturfrage: geaenderte Charakterisierungs-Referenzwerte, eine
neue Kante in der Schicht-Allowlist, ein umgeschriebener ADR. Neu
hinzukommende Referenzwerte reissen nichts — ein Alarm, der schon beim
Danebenstellen schlaegt, wird abgeschaltet.

**Ueberschreiten ist erlaubt, Verschweigen nicht.** Ohne Begruendung
endet das Werkzeug auf 20. Mit `--ueberschreitung-begruendet` laeuft es
durch, und der Satz steht im Ergebnis und auf der Vorfuehrseite. Aus
einer Nebenwirkung von vierzig Commits wird so eine benannte
Entscheidung.

## Einen Fall darstellen

```
python werkzeuge/falldaten.py --fall faelle/<fall> \
    --abzug <registrierter-abzug-1>.csv --abzug <registrierter-abzug-2>.csv \
    --out runs/falldaten.json
python werkzeuge/fallbericht.py --daten runs/falldaten.json \
    [--texte texte.json] --out runs/fallbericht.html
```

Der erste Schritt erhebt, der zweite stellt dar. Die Trennung ist der
Zweck: Zahlen kommen aus den Artefakten und aendern sich beim naechsten
Lauf von selbst, Struktur und Beschriftungen stehen im Renderer und
bleiben.

**Was frei geschrieben wird, sind vier Stellen** — und zwei davon fuellen
sich aus den Entscheid-Snapshots und registrierten Quellen (strukturell
geprueft; die Signatur der Snapshots verifiziert das Werkzeug nicht): ein
Absatz zum Anlass, je Befund eine Wirkungszeile, die Begruendungen der
Abnahmen (aus den Entscheid-Snapshots) und Auszuege aus registrierten
Quellen. Ohne
Textdatei entsteht eine vollstaendige Seite ohne Erzaehlung; das ist
Absicht.

**Die Abgrenzungen werden ABGELEITET, nicht geschrieben.** Eine
Einschraenkung entsteht dort, wo zwei Artefaktwerte auseinanderfallen:
Pruefgesamtheit gegen Bestandsgroesse, ersetzte gegen verglichene
Pruefungen, Quellspalten ohne Entscheidung. Sie verschwindet beim
naechsten Lauf von selbst, wenn die Ursache weg ist — niemand muss einen
Satz streichen.

**Der Bericht ist Konsument, kein Vertragsgeber.** Er verlangt von keinem
Agenten, etwas fuer ihn aufzuschreiben; er liest, was ohnehin entsteht.
Der Preis dafuer ist, dass eine Formaenderung der Pipeline ihn treffen
kann — deshalb meldet `falldaten.py` fehlende Pflichtabschnitte auf
stderr und endet auf 3. Eine Darstellung, die vollstaendig aussieht und
es nicht ist, waere die schlechteste Variante.

## Veroeffentlichen

**Die Artefakte eines Laufs gehoeren nicht ins Repo.** ADR-002: "Das
Repo ist das System, nicht der Datenraum"; `faelle/` ist gitignoriert
und echte Faelle liegen ausserhalb. Deshalb kann auch keine
GitHub-Action die Seite bauen — sie sieht die Artefakte nicht. Der Weg
ist: lokal bauen, Ergebnis auf einen eigenen Branch schieben, Pages
liest diesen Branch.

### Einmalig einzurichten (Mensch)

1. Leeren Branch anlegen und schieben:

   ```
   git switch --orphan gh-pages
   git commit --allow-empty -m "Vorzeigeseite"
   git push -u origin gh-pages
   git switch <arbeitsbranch>
   ```

   Der Arbeitsbranch wird am Ende beim NAMEN genannt, nicht als
   `git switch -`: Nach einem Orphan-Wechsel gibt es kein "vorher",
   auf das `-` zeigen koennte, und die Kette bricht ab.

   `--orphan` leert das Arbeitsverzeichnis; der Wechsel zurueck fuellt
   es wieder. Gitignorierte Verzeichnisse (`faelle/`, `runs/`,
   `docs-local/`, `simulation/`) bleiben unangetastet. Ein
   uncommitteter Stand blockiert den Wechsel — vorher committen.

2. Pages einschalten. **Meist schon geschehen:** GitHub schaltet Pages
   fuer einen Branch, der woertlich `gh-pages` heisst, beim ersten Push
   von selbst ein (`build_type: legacy`). Dann fehlt in *Settings →
   Pages* die Source-Auswahl und es steht nur noch der Domain-Knopf da
   — das ist der eingerichtete Zustand, kein Fehler. Nachsehen:

   ```
   gh api repos/<owner>/<repo>/pages --jq '{status, source, html_url}'
   ```

   Fehlt Pages, dort *Source* auf **Deploy from a branch** setzen,
   Branch `gh-pages`, Ordner `/ (root)`. Kein Actions-Workflow noetig.

Bewusst KEIN Ausloeser bei jedem Push: Veroeffentlichen ist nach aussen
gerichtet und praktisch nicht zurueckzunehmen (Indexierung, Caches).
Es bleibt eine menschliche Handlung.

### Je Lauf

Die Seite in ein gitignoriertes Verzeichnis bauen, von dort schieben.
Der neue Stand ERSETZT den alten vollstaendig: Erst den Inhalt des
Pages-Worktrees leeren, dann kopieren — wer nur drueberkopiert, laesst
verwaiste Artefakte der vorigen Version oeffentlich liegen, und ein
Artefakt, auf das keine Seite mehr zeigt, ist trotzdem abrufbar.

```
python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \
    --abzug <abzug-1>.csv --abzug <abzug-2>.csv [--verlauf verlauf.md]
git worktree add /tmp/gh-pages gh-pages
git -C /tmp/gh-pages rm -rq .
cp -r runs/seite/. /tmp/gh-pages/
cd /tmp/gh-pages && git add -A && git commit -m "Lauf <datum>" && git push
cd - && git worktree remove /tmp/gh-pages
```

**Keine `index.html` in den Ausgabeordner legen.** Jekyll baut die
`index.md` zu genau diesem Namen; eine von Hand danebengelegte Datei
kollidiert mit ihr. Wer sich die Seite vor dem Schieben lokal ansehen
will, rendert sie NEBEN das Verzeichnis, nicht hinein — dafuer gibt es
ein Werkzeug:

### Ansehen vor dem Schieben

Lokal existiert die Seite nur als Quelle (`index.md` + `artefakte/`);
ihr HTML erzeugt erst Jekyll auf den GitHub-Servern. `auftritt.py`
rendert die Vorschau bereits mit; einzeln:

```
python3 werkzeuge/vorschau.py --seite runs/seite \
    --out runs/vorzeige-vorschau
```

Rendert alle Markdown-Seiten des Baums in ein eigenes Verzeichnis und
verlinkt Artefakte und Assets (Symlink, kein zweiter Datenbestand);
Zahlen, Tabellen und Links sind damit pruefbar. Eine Lesehilfe, kein Abbild
des Pages-Themas — die Optik der Live-Seite entsteht erst beim Bau.
Das Werkzeug weigert sich, ins Push-Verzeichnis zu rendern.

Angesehen wird die Vorschau im Browser ueber einen internen
Sichtungs-Server, der per Symlink auf dieses Verzeichnis zeigt — URL
und Betrieb stehen in der Infra-Doku, nicht im Repo. Zwei Regeln
daraus fuer die Seiten selbst: nur RELATIVE Links (die Sichtung
liefert unter einem Pfad-Praefix aus, absolute Pfade ab `/` brechen),
und der Vorschau-Pfad `runs/vorzeige-vorschau` bleibt stabil, weil der
Symlink des Servers darauf zeigt.

### Vorher pruefen

Das Werkzeug erzwingt zwei Dinge und laesst drei beim Menschen.

**Erzwungen:** Nichts aus `simulation/` oder `docs-local/` gelangt auf
die Seite, und `MANIPULATIONEN.md` sowie `NOTIZEN.md` sind gesperrt,
egal wo sie liegen — dort stehen die Aufloesungen des Vorfuehrfalls. Das
Werkzeug bricht ab, statt zu warnen. Ausserdem steht der
Simulationshinweis vor allem anderen: erfundene Unternehmen,
synthetische Vertraege, Entscheid-Snapshots mit dem Fingerabdruck eines
Simulationsschluessels — deren Signatur die Seite nicht verifiziert und
deshalb auch nicht "gezeichnet" nennt (T20-02). Ohne den Hinweis saehe
eine oeffentliche Seite mit aktuariellen Abnahmen aus wie eine echte.
Fehlt dem Fall ein Pflichtabschnitt, steht das auf der Seite unter "Was
diese Seite NICHT zeigt", und das Werkzeug endet mit Exit 3 (T20-03).

**Beim Menschen:** Stehen Klarnamen im Verlaufsprotokoll? Trifft der
Simulationshinweis noch zu? Traegt die Seite etwas, das die Vorfuehrung
verraet? Das Werkzeug fragt danach; beantworten muss es jemand.

**Erst der Code, dann die Seite.** Die Seite stempelt Commit und
Branch als Provenienz. Dieser Stand muss im oeffentlichen Repo
nachschlagbar sein, BEVOR die Seite live geht — eine Seite, deren
Kernversprechen die Nachpruefbarkeit ist, darf nicht auf einen Commit
zeigen, den niemand einsehen kann.

### Danach pruefen

Der Bau laeuft asynchron und braucht ein bis zwei Minuten. Er kann
fehlschlagen, ohne dass der Push es meldet:

```
gh api repos/<owner>/<repo>/pages/builds/latest --jq '{status, error}'
```

`status: built` heisst fertig, `errored` nennt den Grund im Feld
`error`. Erst danach zeigt die URL den neuen Stand — ein alter Stand im
Browser ist meist der Cache, nicht ein misslungener Bau.

### Drift pruefen

Zwischen zwei Veroeffentlichungen driftet der Live-Stand vom Repo weg.
Ob es so ist, beurteilt ein Werkzeug — es veroeffentlicht nichts:

```
python werkzeuge/drift.py --seite runs/seite [--ref gh-pages]
```

Vergleicht den frisch gebauten Entwurf mit dem `gh-pages`-Branch.
Volatile Stempel (Veroeffentlichungsdatum, Systemstand der
Fall-Seiten, Bau-Commit der Landkarte) zaehlen nicht als Drift —
sonst schluege der Test immer, und ein Alarm, der immer schlaegt,
wird abgeschaltet. Exit 1 listet die Abweichungen; aktualisiert wird
von Hand (Abschnitt "Je Lauf").
