# Werkzeuge der Vorführung

Die Werkzeuge, mit denen die Webseite gebaut wird, und Hilfen zum
Beobachten eines Laufs (Gegenstand 5 nach ADR-027). Vier davon,
`vorfuehrung.py`, `lagebild.py`, `aufzeichnung.py` und `sitzungsprobe.py`,
gehören zum Migrationssystem: Sie dienen dem Live-Lauf eines Falls. Die
Werkzeuge lesen und stellen dar; die Fachlichkeit liegt unter `src/`.
`verlaufsprotokoll.py` liest dabei ein Format eines Herstellers
(Sitzungstranskripte von Claude Code). Die allgemeine Frage, was
versionierter Bestandteil des Repositorys wird und was eine
gekennzeichnete Beispielanbindung bleibt, steht in
`dev-docs/offene-punkte.md`.

| Werkzeug | Zweck |
|---|---|
| `verlaufsprotokoll.py` | Sitzungstranskript zu einem lesbaren Verlauf |
| `vorzeigeseite.py` | Datenmodell und Artefakte eines Falls zu einer statischen Seite |
| `unternehmensseite.py` | die Seiten des fiktiven Unternehmens zusammenbauen |
| `auftritt.py` | den ganzen Entwurf mit einem Kommando aus den Quellen bauen |
| `grafik.py` | Bausteinsatz der generierten Darstellungen (Inline-SVG/HTML, modellfrei) |
| `darstellung.py` | Abbildung Modellpfad -> Baustein-Eingabe, an einer Stelle |
| `drift.py` | den veröffentlichten Stand gegen den Entwurf halten |
| `umbaubudget.py` | wie weit ein Lauf das System umgebaut hat |
| `aufwand.py` | den Verbrauch der Agenten eines Falls aus ihren Sitzungsprotokollen festhalten (abgeleitet/aufwand.json, je Antwort einmal gezählt) |
| `falldaten.py` | Datenmodell einer Falldarstellung aus den Artefakten |
| `fallbericht.py` | Darstellung aus dem Datenmodell rendern |
| `vorschau.py` | den Entwurf der Seite lokal ansehen, vor dem Schieben |
| `seitenpruefung.py` | die gebaute Seite prüfen: Verweise, Überschriften, Paket gegen `stand.json`, jede angezeigte Kennung mit Quelle, Breite auf dem Telefon (läuft im Bau mit) |
| `schau.py` | Screenshots der gebauten Vorschau in drei Breiten (1280, 720 und 390 px; braucht Playwright) |
| `bereinigung.py` | veröffentlichte Belege von Pfaden des Rechners befreien und die gebaute Seite auf solche Pfade und gesperrte Wörter prüfen |
| `naht.py` | meldet Bausteine, die ohne Abstand aneinanderkleben (braucht Playwright) |
| `vorfuehrung.py` | einen Fall in tmux führen: Cockpit und je Agentenrolle ein Fenster |
| `lagebild.py` | wo ein Fall steht — die Anzeigen der Vorführung, nur lesend |
| `aufzeichnung.py` | die Vorführung mitschneiden und als asciicast ausgeben |
| `sitzungsprobe.py` | ob ein Agenten-Werkzeug die Sitzungen der Vorführung trägt |

## Verlauf eines Laufs protokollieren

```
python werkzeuge/verlaufsprotokoll.py --neueste --out verlauf.md
python werkzeuge/verlaufsprotokoll.py --sitzung <uuid> --mit-denken
```

Trennt Mensch, Konsole, Operator und Werkzeug; Entscheide werden
hervorgehoben. Schlüsselpfade und Geheimnisse sind redigiert.

## Die Seite bauen

Die Vorführung tritt als Unternehmensauftritt der (frei erfundenen)
Pfefferminzia Lebensversicherung AG auf. Die Unternehmensseiten sind
handgeschriebene, versionierte Quellen unter `vorzeige-seite/`; die
Migrationsberichte entstehen je Fall aus den Artefakten und hängen
unter `migrationen/<fall>/`. Jede Unternehmensseite muss die
Fiktions-Banderole tragen; `unternehmensseite.py` baut sonst nicht.

Der Entwurf wird nicht gepflegt, sondern erzeugt: ein Kommando fährt
die ganze Kette aus den aktuellen Quellen (Datenmodell, Fall-Seite,
Unternehmensseiten samt Fachdoku, Landkarte und Techstack, Vorschau).
So kann der Entwurf nicht hinter Codebasis oder Fall-Artefakten
zurückbleiben; vor Sichtung und Veröffentlichung einmal laufen
lassen:

```
python werkzeuge/auftritt.py --fall faelle/baldrian-klv-tg2015-fall3 \
    --name baldrian \
    --abzug baldrian_bestandsabzug_2026-01-01.csv \
    --abzug baldrian_bestandsabzug_2027-01-01.csv \
    --stands-paket runs/stands-paket \
    --anker faelle/baldrian-klv-tg2015-fall3/abgeleitet/anker/anker.jsonl \
    [--verlauf verlauf.md]
```

Den Fall `faelle/baldrian-klv-tg2015-fall3` legt das Nachfahren an
(README, Schnellstart); Stands-Paket und Anker entstehen mit dem Export
weiter unten. Der letzte Schritt, die Vorschau, braucht das Paket
`markdown` im System-Python (siehe „Ansehen vor dem Schieben“);
`--vorschau ''` lässt ihn aus.

`--name` ist das URL-Segment unter `migrationen/`, so wie die
Unternehmensseiten den Fall verlinken. Die Schritte der Kette bleiben
einzeln aufrufbar (`falldaten.py`, `vorzeigeseite.py
--als-unterseite`, `unternehmensseite.py --daten`, `vorschau.py`).

Die Kennzahlen der Quellseiten sind `{{...}}`-Platzhalter. Der Bau löst
sie aus dem falldaten-Modell des Falls auf, damit sie nicht von den
Artefakten abweichen. Ein unauflösbarer Platzhalter bricht den Bau ab. Neben
Zahlen (`zahl`, `euro`, `datum`, `text`) gibt es generierte Bausteine
(`html:kennzahlenband`, `html:toleranz`, `html:stationen`,
`html:widerspruch`, `html:abgrenzungsband`, `html:berichte`,
`svg:gevo_je_art`, `svg:zugang_status`, `tabelle:gevo_je_art`); die
Zuordnung Modellpfad -> Baustein steht in `werkzeuge/darstellung.py`,
die Bausteine selbst in `werkzeuge/grafik.py`. Welche Stellen
automatisiert sind und welche bewusst Prosa bleiben, steht in
`dev-docs/vorzeige-statische-stellen.md`.

Drei Darstellungsregeln, die die Bausteine erzwingen: Ein bestandener
Test wird nie ohne seinen Maßstab genannt (Schranke neben größter
Abweichung, Absolutwerte auf gemeinsamer Achse; keine Ausschöpfungsquote
als Vergleich zwischen Abnahmen); Prüfumfänge stehen einzeln
mit Einheit, nie als Summe (die Mengen sind nicht disjunkt); und die
Grenzen stehen an fester Stelle neben dem Ergebnis: ein leeres
Abgrenzungsband nennt, was die Artefakte hergeben, und behauptet keine
Vollständigkeit.

`--stands-paket <verzeichnis>` gibt der Kette das Stands-Paket der
Laufzeitumgebung des Tagesbetriebs mit (exportiert mit
`python -m rechner_pipeline.betrieb.seite`, siehe unten; Fachkonzept
`docs/simulation/tagesbetrieb.md`, Abschnitt 8.3): Der
lebende Bestand der PLV wird ein Abschnitt des Datenmodells und des
Fallberichts, mit Stand-Datum, Manifest-Hash und der Zeichnung der
übernommenen Fälle, aus dem Paket gelesen, nie abgetippt. Ein Paket,
dessen Stand nicht durch P-B1 ging, weist `falldaten.py` ab.

Für die Unternehmensseiten ist das Paket Pflicht: Startseite,
Geschäftsentwicklung und Finanzen zeigen den geführten Bestand
(`{{...:betrieb....}}`-Kennzahlen, Tabellen `buchungen_je_art`,
`abschluesse`, `uebernahmen_im_stand`); ohne Paket bricht der Bau mit
dem Hinweis auf den Aufruf ab. Die Dateien des Pakets (Paketschema 5:
die Tagesseite „Bestand heute“ als `index.html` und die bezeugten
Berichte des jüngsten Abschlusses in der Wurzel, die Monatsabschlüsse
unter `abschluesse/`) übernimmt `unternehmensseite.py` byteweise nach
`<out>/plv/`, jede gegen die SHA-256 in `stand.json` gehalten, nichts
wird umgeschrieben; die Vorschau verlinkt das Verzeichnis ganz.
Bestandskennzahlen der Abschlüsse und Geschäftsentwicklung je Zeitraum
stehen nicht in `stand.json`: `falldaten.py` rechnet sie aus den
Abschlussdateien und dem Tagesjournal des Pakets nach, nachdem es deren
Hash geprüft hat. Den Abschluss zwölf Monate vor dem jüngsten trägt
das Paket nicht; der Vorjahresvergleich entfällt dann benannt.

Einen Stand außerhalb der Laufzeitumgebung `~/apps/plv` liefert eine
Welt (`deploy/welt/laufzeit_aufstellen.sh`, siehe
[deploy/welt/README.md](../deploy/welt/README.md)). Aus ihrer Ablage
exportiert dieses Kommando das Stands-Paket; die Pfade von
Betriebsschlüssel und Zeichnungsordnung stehen in
`<welt>/einstellungen.conf` (`BETRIEB_KEY`, `ORDNUNG`):

```
python -m rechner_pipeline.betrieb.seite --stand <welt>/daten \
    --paket runs/stands-paket \
    --anker faelle/<fall>/abgeleitet/anker \
    --betriebsschluessel <BETRIEB_KEY> --zeichnungsordnung <ORDNUNG>
```

Der Anker liegt außerhalb des Pakets, denn ein Paket, das nur sich selbst
belegt, kann seine eigene Herkunft behaupten. `runs/anker`
taugt dafür nur in der Probe: `runs/` ist Wegwerf, und ein Anker in
einem Verzeichnis, das jemand planmäßig leert, ist so wenig ein Anker
wie einer im Paket. Der echte Anker gehört in den Fall-Datenraum.

Und der Export schreibt nebenbei die Tagesseite in die Ablage; wer nur
ein Paket ziehen will, arbeitet deshalb auf einer Kopie, nicht auf der
Laufzeit.

Der Stand ist ein Datum: Jeder neue Tageslauf ändert Kennzahlen und
Paket, und `drift.py` meldet das als Abweichung. Das ist gewollt: Die
veröffentlichte Seite ist eine gestempelte Momentaufnahme.

Die Zahlen der Seite kommen aus dem Datenmodell (`falldaten.py`),
demselben, aus dem auch der Fallbericht gerendert wird. Seite und
Bericht tragen damit dieselben Zahlen aus derselben Quelle; früher
lasen beide die Fall-Artefakte getrennt, und zwei Leser desselben
Datenraums driften auseinander. Was die Seite selbst tut, ist
Veröffentlichung: die Belege der Belegkette kopieren, die Regie
sperren, Systemstand und Branch stempeln, `index.md`, `_config.yml` und
`artefakte/` schreiben.

Welche Datei des Falls an welche Station gehört, erhebt
`falldaten.belegkette` aus dem, was die Kette selbst sagt, nicht aus einer
Tabelle von Hand. Die erste Regel, die trifft, gilt:

1. Der Ort im Fall-Arbeitsbereich, wo die Kette keinen Erzeuger kennt,
   aber nur für eine Datei, die die Kette führt oder das Eingangsregister
   trägt. Ausnahme: Die deterministische Vorverdichtung der Quellen
   (`abgeleitet/vorverdichtung/`) steht auch ungebunden an Station 2, mit
   dem Vermerk „nicht gebunden“.
2. Entscheid-Snapshots und Prüfprotokolle gehören zur Station ihres Gates.
3. Ein Pflichtbeleg eines Entscheids gehört, über seine Prüfsumme
   gefunden, zur Station des Gates, dessen Beleg er ist.
4. Was ein Gate geschrieben hat, gehört zu dessen Station.
5. Der Beleg einer Entscheidung, den die A-Box mit Pfad und Prüfsumme
   nennt, gehört zur Quellenabnahme.
6. Was ein Gate zur Prüfung gelesen oder nur mit seiner Prüfsumme genannt
   hat, gehört zu dessen Station. Das Protokoll einer Zeichnung zählt
   dabei nicht als Leser.
7. Geschwister liegen neben ihrem Beleg.

Was das Datenmodell für eine Zahl der Seite liest, kommt ohne Station mit.
Was keine Regel trifft (Arbeitsunterlagen der Agenten, Reste früherer
Durchgänge, ein Dateiname, der nur nach einem Gate klingt), kommt nicht auf
die Seite und wird gezählt. Die Regeln stehen im Docstring der Funktion;
die Karte (`migrationen/#prozess`) und die Fallseite lesen dieselbe
Zuordnung aus dem Modell.

Die Änderung am Zielsystem ist ein Pflichtabschnitt des Modells: Ein
abgeschlossener Fall trägt sie immer: ein Lauf, dessen Umbau niemand
gemessen hat, sähe sonst aus wie ein Lauf ohne Umbau. Seit der Abnahme
des Stands (ADR-018 Nachtrag 01.10., ADR-025) sind es die
Änderungsbelege von Kern (A-K2) und Tarifwerk (A-T1); ältere Läufe
tragen ein Umbaubudget. Fehlt beides, meldet `falldaten.py` eine Lücke
(Exit 3). Das Umbaubudget eines älteren Laufs wird so in den Fall
erhoben:

```
python werkzeuge/umbaubudget.py --basis <startpunkt> \
    --json faelle/<fall>/abgeleitet/berichte/umbaubudget.json
```

Die Seite rechnet nichts Fachliches nach. Jede Zahl steht so in einem
Artefakt, das unter `artefakte/` daneben liegt; sonst wäre die
Vorführung eine Behauptung über sich selbst. Was sie zählt (Belege je
Station, Kennzahlen aus den Abschlussdateien des Pakets), zählt sie aus
Bytes, deren Hash sie geprüft hat. Verlinkt wird nur, was die
Belegkette einer Station zuordnet und tatsächlich kopiert ist, und die
Regie-Sperre prüft auch die Verweise aus dem Modell noch einmal selbst. Ein nicht bestandener Test und eine
gerissene Schranke werden genauso dargestellt wie ein grüner Lauf; eine
Seite, die nur den Erfolgsfall zeigen kann, sagt nichts über die Prüfung.

## Umfang eines Laufs messen

```
python werkzeuge/umbaubudget.py --basis <startpunkt-des-laufs> \
    [--json runs/umbaubudget.json] \
    [--ueberschreitung-begruendet "<ein Satz>"]
```

`--basis` ist der Stand, auf dem der Lauf aufgesetzt hat, nicht `main`,
sonst misst man die Vorgeschichte mit.

Wer einen Migrationsfall löst, darf Code ändern, die Ontologie
erweitern und Gates umbauen. Was er nicht soll, ist das System nebenbei
durch ein anderes ersetzen, etwa den Rechenkern von der
Thiele-Rekursion auf Kommutationszahlen zurückdrehen, weil das gerade
der kürzere Weg zum grünen Gate wäre. Die Absicht lässt sich nicht
prüfen, der Umfang schon.

Deshalb wiegt **Löschen schwerer als Hinzufügen**: Hinzufügen ist der
Auftrag, Löschen ist Ersetzen. Das Gesamtbudget trägt viel (18.000
Zeilen in `src/` und `tests/`), die Löschbudgets wenig und je Schicht
getrennt (`kern/` und `ontologie/` je 450, alles übrige 1.200).

Daneben stehen **Stolperdrähte**, die keine Budgetfrage sind, sondern
eine Architekturfrage: geänderte Charakterisierungs-Referenzwerte, eine
neue Kante in der Schicht-Allowlist, ein umgeschriebener ADR. Neu
hinzukommende Referenzwerte reißen nichts: ein Alarm, der schon beim
Danebenstellen schlägt, wird abgeschaltet.

**Überschreiten ist erlaubt, Verschweigen nicht.** Ohne Begründung
endet das Werkzeug auf 20. Mit `--ueberschreitung-begruendet` läuft es
durch, und der Satz steht im Ergebnis und auf der Vorführseite. Aus
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
Zweck: Zahlen kommen aus den Artefakten und ändern sich beim nächsten
Lauf von selbst, Struktur und Beschriftungen stehen im Renderer und
bleiben.

**Was frei geschrieben wird, sind vier Stellen**, und zwei davon füllen
sich aus den Entscheid-Snapshots und registrierten Quellen (strukturell
geprüft; die Signatur der Snapshots verifiziert das Werkzeug nicht): ein
Absatz zum Anlass, je Befund eine Wirkungszeile, die Begründungen der
Abnahmen (aus den Entscheid-Snapshots) und Auszüge aus registrierten
Quellen. Ohne
Textdatei entsteht eine vollständige Seite ohne Erzählung; das ist
Absicht.

**Die Abgrenzungen werden abgeleitet, nicht geschrieben.** Eine
Einschränkung entsteht dort, wo zwei Artefaktwerte auseinanderfallen:
Prüfgesamtheit gegen Bestandsgröße, ersetzte gegen verglichene
Prüfungen, Quellspalten ohne Entscheidung. Sie verschwindet beim
nächsten Lauf von selbst, wenn die Ursache weg ist; niemand muss einen
Satz streichen.

**Der Bericht ist Konsument, kein Vertragsgeber.** Er verlangt von keinem
Agenten, etwas für ihn aufzuschreiben; er liest, was ohnehin entsteht.
Der Preis dafür ist, dass eine Formänderung der Pipeline ihn treffen
kann; deshalb meldet `falldaten.py` fehlende Pflichtabschnitte auf
stderr und endet auf 3. Eine Darstellung, die vollständig aussieht und
es nicht ist, wäre die schlechteste Variante.

## Veröffentlichen

**Die Artefakte eines Laufs gehören nicht ins Repo.** ADR-002: „Das
Repo ist das System, nicht der Datenraum“; `faelle/` ist gitignoriert
und echte Fälle liegen außerhalb. Deshalb kann auch keine
GitHub-Action die Seite bauen: sie sieht die Artefakte nicht. Der Weg
ist: lokal bauen, Ergebnis auf einen eigenen Branch schieben, Pages
liest diesen Branch.

### Bereinigung der veröffentlichten Belege

Es gibt zwei Wege der Veröffentlichung: den Code (die wiederherstellbare
Routine) und die Webseite (mit den Artefakten eines Falls).
Die Belege eines Laufs tragen, was ihre Kommandos gesehen haben, auch die
absoluten Pfade des Rechners, auf dem sie liefen: den Arbeitsbaum des
Falls, die Laufzeitumgebung, das Verzeichnis des Schlüsselmaterials. Die
Belege sind über Prüfsummen gebunden und bleiben, wie sie sind; die
Behebung im Produzenten (Pfade relativ in den Ledgern, ein Herkunftsfeld
beim Registrieren) ist Arbeit für den nächsten Lauf. Bereinigt wird
deshalb nur die veröffentlichte Fassung, als Stufe im Bau der Seite
(Entscheid des Maintainers, 03.10.2026; `werkzeuge/bereinigung.py`):

- **Regel statt Handarbeit.** `vorzeigeseite.py` ersetzt beim Kopieren
  jeden Hostpfad, den eine Regel kennt, durch einen benannten Platzhalter:
  `<baum>` (der Arbeitsbaum, in dem der Fall liegt, erhoben aus dem Pfad
  des Falls), `<schluesselverzeichnis>` (`~/.rechner-pipeline-schluessel`),
  `<welt>` (die Laufzeitumgebung unter `~/apps`), `<laufordner>` (ein
  Laufverzeichnis außerhalb des Falls, `~/git/<baum>/runs/<ordner>`, wo
  Stands-Paket und Anker liegen). Deterministisch:
  dieselben Bytes ergeben dieselbe Fassung. Bereinigt wird nur Text; trägt
  eine andere Datei einen Hostpfad, hält der Bau an.
- **Ein Entscheid-Snapshot wird nie bereinigt.** Eine Änderung bräche
  seine Signatur und die Verweise der Folgeentscheide. Ein überholter
  Snapshot, der etwas trägt, das nicht auf die Seite gehört, bleibt
  unveröffentlicht und steht benannt da (Prüfsumme, Status „überholt,
  nicht veröffentlicht“); trägt es ein geltender oder einer, den das
  Modell nicht kennt, hält der Bau an; das entscheidet ein Mensch.
- **Das Manifest** `artefakte/bereinigung.json` nennt je bereinigter Datei
  die Prüfsumme des Originals im Fall, die Entscheide, die dieses Original
  über seine Prüfsumme binden, die Prüfsumme der veröffentlichten
  Fassung und die Ersetzungen je Regel, dazu jede zurückgehaltene Datei
  mit ihrer Prüfsumme. „Gebunden“ steht nur, wo ein Entscheid die
  Prüfsumme nennt: In Fall 3 binden Entscheide das Eingangsregister, den
  Abnahmebericht und die Zugangsprobe; die Protokolle der Zeichnungen
  bindet keiner: sie entstehen mit der Zeichnung. Alle übrigen Belege
  unter `artefakte/` sind bytegleich mit ihren Originalen im Fall; die
  Ansichten der Lieferung (`artefakte/lieferung/`) sind Ansichten: eine
  CSV als Vorschau ihrer ersten Zeilen, alles Übrige bytegleich. Die
  Fallseite sagt das im Abschnitt „Bereinigt veröffentlicht“. Die Kette
  bleibt nachvollziehbar, über das Manifest statt über identische
  Bytes.
- **Die Wache** liest nach dem Bau jede veröffentlichte Datei: den Namen,
  die Bytes und, wo die Seite komprimiert veröffentlicht, den entpackten
  Inhalt (Parquet: Schema, Metadaten und jede Spalte außer Zahlen und
  Zeiten; PDF: die Flate-Ströme). Kein Hostpfad (`/home/`,
  `/tmp/claude`, beide auch JSON-maskiert, `/Users/`, `C:\Users\`, der
  Projektordner `-home-<benutzer>-`), kein gesperrtes Wort. Eine Datei,
  die sie nicht lesen kann, ist ein Befund. Sie läuft am Ende von
  `vorzeigeseite.py` und in `auftritt.py` über den ganzen Push-Baum,
  Stands-Paket und Fachdokumente eingeschlossen. Was keine Regel kennt,
  wird nicht still ersetzt, sondern hält den Bau an: dann eine Regel
  ergänzen, den Produzenten beheben oder die Datei zurückhalten.

Nachprüfen, mit dem Fall in der Hand, aus dem Baum, in dem er liegt:

```
python werkzeuge/bereinigung.py --pruefe <seite>/migrationen/<name> --fall faelle/<fall>
python werkzeuge/bereinigung.py --wache <seite>
```

`--pruefe` rechnet die gebaute Fallseite gegen den Fall nach: Je
bereinigter Datei hat das Original im Fall die genannte Prüfsumme und die
genannten Bindungen (aus der Belegkette), die Regeln ergeben daraus die
veröffentlichte Fassung mit denselben Ersetzungszahlen, und die Datei auf
der Seite hat deren Prüfsumme. Jede zurückgehaltene Datei liegt mit ihrer
Prüfsumme im Fall und unter keinem Namen auf der Seite. Jede andere Datei
unter `artefakte/` hat ein Gegenstück im Fall und ist bytegleich mit ihm;
die Vorschau einer gelieferten CSV wird neu erzeugt und verglichen; eine
Datei ohne Gegenstück ist ein Befund. Und kein Beleg, den die Belegkette
einer Station zuordnet, fehlt auf der Seite. Liegt der Fall anderswo als
beim Bau, ergibt die Regel `<baum>` einen anderen Pfad, und die Prüfung
schlägt an. Das ist gewollt: Sie prüft die Fassung, die gebaut wurde.

Das Stands-Paket bereinigt die Stufe nicht: Der Auftritt veröffentlicht
es bytegleich und an seine Prüfsumme gebunden. Einen Hostpfad trägt es
nur, wenn `betrieb.seite --anker` absolut aufgerufen wurde (`stand.json`,
Feld `anker.datei`); deshalb `--paket` und `--anker` relativ aus dem
Hauptbaum angeben.

Grenzen: Die Wache kennt die Schreibweisen oben; eine Kurzform wie `~/`
(sie steht in den Fachdokumenten erlaubt), UTF-16 oder Base64 sieht sie
nicht, und die Wortliste fängt nur, was sie kennt: Ein privater Termin in
anderer Formulierung bleibt Sache der Durchsicht von Hand vor der
Veröffentlichung. Ein Verlaufsprotokoll (`--verlauf`) bereinigt die Stufe
nicht; es trägt Hostpfade, und die Wache hält den Bau an.

### Einmalig einzurichten (Mensch)

1. Leeren Branch anlegen und schieben:

   ```
   git switch --orphan gh-pages
   git commit --allow-empty -m "Vorzeigeseite"
   git push -u origin gh-pages
   git switch <arbeitsbranch>
   ```

   Der Arbeitsbranch wird am Ende beim Namen genannt, nicht als
   `git switch -`: Nach einem Orphan-Wechsel gibt es kein „vorher“,
   auf das `-` zeigen könnte, und die Kette bricht ab.

   `--orphan` leert das Arbeitsverzeichnis; der Wechsel zurück füllt
   es wieder. Gitignorierte Verzeichnisse (`faelle/`, `runs/`,
   `docs-local/`, `simulation/`) bleiben unangetastet. Ein
   uncommitteter Stand blockiert den Wechsel; vorher committen.

2. Pages einschalten. **Meist schon geschehen:** GitHub schaltet Pages
   für einen Branch, der wörtlich `gh-pages` heißt, beim ersten Push
   von selbst ein (`build_type: legacy`). Dann fehlt in *Settings →
   Pages* die Source-Auswahl und es steht nur noch der Domain-Knopf da;
   das ist der eingerichtete Zustand, kein Fehler. Nachsehen:

   ```
   gh api repos/<owner>/<repo>/pages --jq '{status, source, html_url}'
   ```

   Fehlt Pages, dort *Source* auf **Deploy from a branch** setzen,
   Branch `gh-pages`, Ordner `/ (root)`. Kein Actions-Workflow nötig.

Bewusst kein Auslöser bei jedem Push: Veröffentlichen ist nach außen
gerichtet und praktisch nicht zurückzunehmen (Indexierung, Caches).
Es bleibt eine menschliche Handlung.

### Je Lauf

Die Seite in ein gitignoriertes Verzeichnis bauen, von dort schieben.
Der neue Stand ersetzt den alten vollständig: Erst den Inhalt des
Pages-Worktrees leeren, dann kopieren. Wer nur drüberkopiert, lässt
verwaiste Artefakte der vorigen Version öffentlich liegen, und ein
Artefakt, auf das keine Seite mehr zeigt, ist trotzdem abrufbar.

```
python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \
    --abzug <abzug-1>.csv --abzug <abzug-2>.csv \
    --stands-paket runs/stands-paket \
    --anker faelle/<fall>/abgeleitet/anker/anker.jsonl [--verlauf verlauf.md]
git worktree add /tmp/gh-pages gh-pages
git -C /tmp/gh-pages rm -rq .
cp -r runs/seite/. /tmp/gh-pages/
cd /tmp/gh-pages && git add -A && git commit -m "Lauf <datum>" && git push
cd - && git worktree remove /tmp/gh-pages
```

**Keine `index.html` in den Ausgabeordner legen.** Jekyll baut die
`index.md` zu genau diesem Namen; eine von Hand danebengelegte Datei
kollidiert mit ihr. Wer sich die Seite vor dem Schieben lokal ansehen
will, rendert sie neben das Verzeichnis, nicht hinein; dafür gibt es
ein Werkzeug:

### Ansehen vor dem Schieben

Lokal existiert die Seite nur als Quelle (`index.md` + `artefakte/`);
ihr HTML erzeugt erst Jekyll auf den GitHub-Servern. `auftritt.py`
rendert die Vorschau bereits mit; einzeln:

```
python3 werkzeuge/vorschau.py --seite runs/seite \
    --out runs/vorzeige-vorschau
```

`vorschau.py` läuft mit dem System-Python und braucht dort das Paket
`markdown` (Debian: `apt install python3-markdown`); es ist nicht gepinnt,
weil es nicht zum System gehört. Alle übrigen Werkzeuge laufen in der
`.venv`.

Rendert alle Markdown-Seiten des Baums in ein eigenes Verzeichnis und
verlinkt Artefakte und Assets (Symlink, kein zweiter Datenbestand);
Zahlen, Tabellen und Links sind damit prüfbar. Eine Lesehilfe, kein Abbild
des Pages-Themas: die Optik der Live-Seite entsteht erst beim Bau.
Das Werkzeug weigert sich, ins Push-Verzeichnis zu rendern.

Zum Ansehen genügt ein statischer Webserver auf
`runs/vorzeige-vorschau/`. Die Seiten verwenden nur relative Links, denn
eine Sichtung kann unter einem Pfad-Präfix ausliefern, und absolute Pfade
ab `/` brechen dann.

### Die gebaute Seite prüfen

Mit Stands-Paket, Anker und Vorschau fährt `auftritt.py` als letzten
Schritt `seitenpruefung.py alle`; ein Befund hält den Bau an wie die
Wache. Einzeln, etwa für einen Zweitbau:

```
python werkzeuge/seitenpruefung.py alle --seite runs/<bau>/seite \
    --vorschau runs/<bau>/vorschau --fall faelle/<fall> --name <kurzname> \
    --paket <stands-paket> --anker <anker>/anker.jsonl \
    --daten runs/<bau>/falldaten.json --repo .
```

| Prüfung | Befund |
|---|---|
| `verweise` | ein relativer Verweis ohne Ziel, ein Sprungziel ohne id, ein absoluter Pfad |
| `ueberschriften` | eine Überschrift, die auf eine Attributliste `{: ...}` endet: Die Vorschau liest sie als id, Pages zeigt sie als Text. Eine eigene id heißt `{#x}`, das lesen beide. |
| `paket` | eine Datei unter `plv/`, die von `stand.json` abweicht oder dort fehlt; ein nicht veröffentlichter Eintrag außer Parquet; ein Bericht unter `berichte/` ohne bytegleiche Datei im Paket |
| `pruefsummen` | eine angezeigte Kennung ohne Quelle (Datei des Falls, Manifest, Snapshot, Lieferregister, Paket, Anker, Protokoll, Commit) |
| `breite` | eine Hauptseite, die auf dem Telefon (390 px) breiter ist als der Bildschirm; die übrigen Seiten stehen als Hinweis da (Ansicht am Schreibtisch hat Vorrang, Entscheid 04.10.2026) |

`breite` braucht Playwright wie `schau.py`; fehlt es, meldet `alle`
„NICHT GEPRUEFT“ statt still zu überspringen.

### Vorher prüfen

Das Werkzeug erzwingt zwei Dinge und lässt drei beim Menschen.

**Erzwungen:** Nichts aus den lokalen, nicht eingecheckten
Arbeitsbereichen des Maintainers (`simulation/`, `docs-local/`) gelangt auf
die Seite, und Dateien namens `MANIPULATIONEN.md` oder `NOTIZEN.md` sind
gesperrt, egal wo sie liegen: Dort stehen die Auflösungen des
Vorführfalls. Das
Werkzeug bricht ab, statt zu warnen. Außerdem steht der
Simulationshinweis vor allem anderen: erfundene Unternehmen,
synthetische Verträge, Entscheid-Snapshots mit dem Fingerabdruck eines
Simulationsschlüssels, deren Signatur die Seite nicht verifiziert und
deshalb auch nicht „gezeichnet“ nennt. Ohne den Hinweis sähe
eine öffentliche Seite mit aktuariellen Abnahmen aus wie eine echte.
Fehlt dem Fall ein Pflichtabschnitt, steht das auf der Seite im
Kleingedruckten unter „Grenzen dieses Laufs“, und das Werkzeug endet mit
Exit 3.

**Beim Menschen:** Stehen Klarnamen im Verlaufsprotokoll? Trifft der
Simulationshinweis noch zu? Trägt die Seite etwas, das die Vorführung
verrät? Das Werkzeug fragt danach; beantworten muss es jemand.

**Erst der Code, dann die Seite.** Die Seite stempelt Commit und
Branch als Provenienz. Dieser Stand muss im öffentlichen Repo
nachschlagbar sein, bevor die Seite live geht: eine Seite, deren
Kernversprechen die Nachprüfbarkeit ist, darf nicht auf einen Commit
zeigen, den niemand einsehen kann.

### Danach prüfen

Der Bau läuft asynchron und braucht ein bis zwei Minuten. Er kann
fehlschlagen, ohne dass der Push es meldet:

```
gh api repos/<owner>/<repo>/pages/builds/latest --jq '{status, error}'
```

`status: built` heißt fertig, `errored` nennt den Grund im Feld
`error`. Erst danach zeigt die URL den neuen Stand; ein alter Stand im
Browser ist meist der Cache, nicht ein misslungener Bau.

### Ansehen, bevor man etwas meldet

Die Gestaltung lässt sich nicht rechnen, nur ansehen. `werkzeuge/schau.py`
macht Screenshots der gebauten Vorschau in drei Breiten (breit 1280 px,
schmal 720 px, handy 390 px, je ganzseitig):

```
.venv/bin/pip install playwright && .venv/bin/playwright install chromium
.venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau
.venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau index.html
```

Ohne Seitenangabe nimmt es die Standardliste (Startseite, Vertiefungen,
Fallbericht); mit Angabe nur die genannten Seiten; das ist der Weg, wenn
man an einer Stelle arbeitet. Fehlt Playwright, nennt das Werkzeug den
Installationsbefehl und endet mit Status 2, statt einen ImportError zu
werfen.

Playwright ist Werkstattausrüstung, keine Abhängigkeit des Systems: Die
Suite braucht es nicht, der Bau der Seite auch nicht. Es bleibt darum aus
`requirements*.txt` heraus, und das hält auch
`tests/test_abhaengigkeiten.py` bei seiner Aufgabe: die Closure schließt,
was das System zum Laufen braucht, nicht was eine Werkstatt zufällig hat.
Das Paket landet in der `.venv`, die Browser-Dateien unter
`~/.cache/ms-playwright/` (einige hundert MB, einmalig).

Für den zweiten Blick (die Seite auf einem anderen Gerät ansehen)
genügt ein beliebiger statischer Webserver auf `runs/vorzeige-vorschau/`;
die Vorschau ist ein Verzeichnis gewöhnlicher Dateien.

Ganzseitige Bilder werden schnell drei- bis zehntausend Pixel hoch; wer
sie am Stück betrachtet, sieht nichts. Ausschnitte lesen:

```
.venv/bin/python -c "from PIL import Image; b=Image.open('runs/schau/index-breit.png'); \
  b.crop((0, 700, b.width, 1700)).save('runs/schau/ausschnitt.png')"
```

(`pillow` ist bereits gepinnt; es hängt an matplotlib.)

Eine Fehlerklasse lässt sich auch messen statt betrachten:
`werkzeuge/naht.py` öffnet jede gebaute Seite im selben Browser und
meldet Paare von Bausteinen, zwischen denen weder Leerzeichen noch Rand
steht:

```
.venv/bin/python werkzeuge/naht.py runs/vorzeige-vorschau
```

Die erzeugten Bausteine liefern ihre Teile ohne Trennzeichen: eine
Kachel schreibt Titel, Formatmarke, Kennzahl und Zweck hintereinander,
den Abstand setzt das Stylesheet. Fehlt dort eine Regel, steht auf der
Seite „A-M1 StichtagstestHTML“. Rückgabe 0 heißt sauber, 1 nennt die
Fundstellen. Treffer können auch aus importierten Fachdokumenten
stammen (eine Hervorhebung mitten im Wort); dann liegt die Quelle in
`docs/` und wird dort behoben, nicht auf der Seite.

Auf diesem Weg wurden Fehler gefunden, die kein Test sieht:

- eine ungültige `font:`-Kurzform (`font: 700 1.3rem/1.3 inherit`;
  `inherit` ist keine Schriftfamilie), die den ganzen Block verwirft;
- ein SVG ohne Breitenanschlag, das hochskaliert und seine Schrift
  mitnimmt;
- eine Grafik, die breiter gezeichnet ist als ihre Spalte und darum
  heruntergerechnet wird, bis die Beschriftung nicht mehr lesbar ist;
- eine `table` mit `width: 100%` neben Außenrändern, die rechts
  hinausläuft (Prozente rechnen gegen den Elternblock, die Ränder kommen
  obendrauf).

## Drift prüfen

Zwischen zwei Veröffentlichungen driftet der Live-Stand vom Repo weg.
Ob es so ist, beurteilt ein Werkzeug; es veröffentlicht nichts:

```
python werkzeuge/drift.py --seite runs/seite [--ref gh-pages]
```

Vergleicht den frisch gebauten Entwurf mit dem `gh-pages`-Branch.
Volatile Stempel (Veröffentlichungsdatum, Systemstand der
Fall-Seiten, Bau-Commit der Landkarte) zählen nicht als Drift;
sonst schlüge der Test immer, und ein Alarm, der immer schlägt,
wird abgeschaltet. Exit 1 listet die Abweichungen; aktualisiert wird
von Hand (Abschnitt „Je Lauf“).

## Einen Fall vorführen und aufzeichnen

```
python werkzeuge/vorfuehrung.py --fall faelle/<fall> --linie <linie> --stand <ablage> --modell <modell>
tmux attach -t vorfuehrung
```

Baut die tmux-Session `vorfuehrung`:

| Fenster | links | rechts |
|---|---|---|
| `cockpit` | Chat mit dem Programmleitungs-Agenten | Lebenslauf des Falls, die letzten Entscheide, Systemstand und Laufzeit |
| `aktuariat`, `architektur`, `rechenkern`, `betrieb` | Chat mit dem Agenten der Rolle | ihre Gates mit Stand und Belegen |
| `mensch` | leere Shell für die Zeichnungen | |

Die Fenster folgen den Agentendateien unter `.claude/agents/`; eine neue
Rolle bekommt ihr Fenster ohne Änderung am Werkzeug. Die Chats starten mit
`claude --agent <rolle> --model <modell>`; `--modell` ist Pflicht und hat
keine Vorgabe (sonst erbte jeder der fünf Chats das Modell des Kontos).
`--ohne-chat` baut nur das Gerüst (Probe) und braucht kein Modell,
`--trocken` gibt die tmux-Kommandos aus. Eine Session gleichen Namens wird
nie ersetzt.

Gezeichnet wird im Fenster `mensch`, nie in einem Agentenfenster: Ein Agent
zeichnet keine Annahme, und die Schlüssel liegen außerhalb des Falls.

Die Anzeigen rechts sind `werkzeuge/lagebild.py` unter `watch`:

```
python werkzeuge/lagebild.py lebenslauf --fall faelle/<fall> --linie <linie>
python werkzeuge/lagebild.py entscheide --fall faelle/<fall> --linie <linie> -n 12
python werkzeuge/lagebild.py system --linie <linie> --stand <ablage>
python werkzeuge/lagebild.py rolle <rolle> --fall faelle/<fall> --linie <linie>
python werkzeuge/lagebild.py zugangsprobe --fall faelle/<fall>
```

Das Lagebild ist eine Anzeige, kein Urteil. Es liest die Entscheid-Snapshots
ohne Schlüssel und prüft weder Signatur noch Rolle noch Beleg; das tun
die Gates. Zwei Spitzen einer Kette zeigt es als `mehrdeutig`, eine nicht
lesbare Datei als `unlesbar`, nie als `offen`.

Die Sicht `zugangsprobe` ist keine der Anzeigen rechts: Sie zeigt den Beleg
der Zugangsprobe als Lesefassung für die Zugangsabnahme A-B2 (Urteil,
Folgetermin und je Vergleich Soll, Ist und Differenz), ohne die Prüfsummen
der Abschlüsse, die den Beleg selbst unlesbar groß machen. „Bestanden“
steht dort nur, wenn der Beleg es wörtlich sagt; ein Vergleich ohne Soll
ist als solcher ausgewiesen.

### Aufzeichnen

Aufgenommen wird mit `script` aus util-linux; auf dem Host wird dafür
nichts installiert. tmux zeichnet das Layout selbst, die Aufnahme enthält
also alle Panes.

```
python werkzeuge/aufzeichnung.py aufnehmen --session vorfuehrung --out runs/fall3
python werkzeuge/aufzeichnung.py cast --basis runs/fall3
scriptreplay -T runs/fall3.tim -O runs/fall3.out
```

`aufnehmen` hängt sich an die Session und endet mit dem Abhängen
(`Ctrl-b d`); die Session läuft weiter. `cast` erzeugt `runs/fall3.cast`
im asciicast-Format (Version 2): klein, der Text bleibt kopierbar, die
Wiedergabe läuft in jedem asciinema-Player, im Terminal oder im Browser.
Die Terminalgröße kommt aus der Kopfzeile der Aufnahme und wird nie
geraten. `scriptreplay` spielt die Aufnahme ohne jedes weitere Programm ab.

Ein GIF oder Video entsteht aus der `.cast`-Datei mit `agg` und `ffmpeg`,
auf einem beliebigen Rechner oder in einem Container:

```
agg runs/fall3.cast fall3.gif
ffmpeg -i fall3.gif -movflags faststart -pix_fmt yuv420p fall3.mp4
```

Eine Aufnahme zeigt, was auf dem Bildschirm steht. Schlüsseldateien werden
nur als Pfad genannt, nie ausgegeben; `runs/` ist nicht versioniert.

### Trägt ein Agenten-Werkzeug die Sitzungen?

Die Chats der Vorführung starten mit Claude Code. Soll ein anderes
Agenten-Werkzeug die Rollen führen (oder ein Fall ohne Menschen an jeder
Station laufen, sodass eine Sitzung der anderen Aufträge ins Fenster
schreibt), zeigt eine Probe in wenigen Minuten, ob das trägt:

```
python werkzeuge/sitzungsprobe.py probe --kommando "<start eines chats>" \
    [--session sitzungsprobe] [--bericht runs/sitzungsprobe.md]
```

Sie baut eine eigene tmux-Session mit zwei Fenstern, startet in beiden das
Werkzeug und prüft vier Schritte: START (es kommt zur Ruhe), EINGABE (eine
von außen geschriebene Zeile wird beantwortet), RUHE (von außen erkennbar,
wann die Sitzung fertig ist) und WEITERGABE (eine Sitzung schreibt der
anderen auf Auftrag eine Zeile ins Fenster). Der Bericht nennt je Schritt das
Urteil, die Zeilen, an denen man „arbeitet noch“ sieht, und die Bildschirme,
auch den einer Rückfrage oder einer Sandbox, an der die Weitergabe hängt.

Die Probe urteilt nach dem Bildschirm und kostet zwei kurze Chats mit
zusammen drei Einzeilern. Sie ersetzt nie eine bestehende Session und lässt
ihre eigene stehen (`tmux kill-session -t sitzungsprobe`).
