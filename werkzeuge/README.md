# Werkzeuge der Simulation

Modell und Betrieb der Simulation, die Ebene Simulation nach
[ADR-028](../docs/architektur/adr-028-ordnung-nach-ebenen.md):

| Ordner | Was |
|---|---|
| [welt/](welt/README.md) | Routinen, die Betriebsseite der Simulation: eine Welt aufstellen, einen Fall darin führen oder nachfahren, den Bestand in die Ablage bringen |
| [quellsystem/](quellsystem/README.md) | das Quellsystem der Baldrian; aus ihm entstehen die Lieferungen |
| [engine/](engine/README.md) | die Doku-Engine: setzt die Dokumente der Lieferungen als PDF (für die PLV keine) |
| hier im Ordner | die Werkzeuge, mit denen die Webseite gebaut wird, und Hilfen zum Beobachten eines Laufs |

Das Modell, Verteilungen und das Erzeugen von Geschäftsvorfällen und
Neugeschäft, liegt in einzelnen Modulen des Pakets
(`src/rechner_pipeline/bestand`, `src/rechner_pipeline/betrieb/neugeschaeft.py`)
und ist in [docs/simulation/](../docs/simulation/README.md) beschrieben. Die Werkzeuge
für den Live-Lauf eines Falls gehören zum System und liegen unter
[system/](../system/README.md).

## Die Werkzeuge der Seite

Die Werkzeuge lesen und stellen dar; die Fachlichkeit liegt unter `src/`.
`verlaufsprotokoll.py` liest dabei ein Format eines Herstellers
(Sitzungstranskripte von Claude Code). Die allgemeine Frage, was
versionierter Bestandteil des Repositorys wird und was eine
gekennzeichnete Beispielanbindung bleibt, steht in
[dev-docs/offene-punkte.md](../dev-docs/offene-punkte.md).

| Werkzeug | Zweck |
|---|---|
| `verlaufsprotokoll.py` | Sitzungstranskript zu einem lesbaren Verlauf |
| `vorzeigeseite.py` | Datenmodell und Artefakte eines Falls zu einer statischen Seite |
| `unternehmensseite.py` | die Seiten des fiktiven Unternehmens zusammenbauen |
| `auftritt.py` | den ganzen Entwurf mit einem Kommando aus den Quellen bauen, Rahmen und Betriebsteil oder einen davon (`--teil`) |
| `rahmen_pr.py` | den Rahmen der Seite als Commit auf einen Zweig `beitrag/...` im Klon von plv-fiktion legen, mit `CODESTAND` |
| `betriebszweig.py` | im Workflow von plv-fiktion: was im Zweig `betrieb` liegen darf, und dass sich außerhalb von `betrieb/` nichts geändert hat |
| `grafik.py` | Bausteinsatz der generierten Darstellungen (Inline-SVG/HTML, modellfrei) |
| `darstellung.py` | Abbildung Modellpfad -> Baustein-Eingabe, an einer Stelle |
| `drift.py` | den veröffentlichten Stand gegen den Entwurf halten |
| `umbaubudget.py` | wie weit ein Lauf das System umgebaut hat |
| `aufwand.py` | den Verbrauch der Agenten eines Falls aus ihren Sitzungsprotokollen festhalten (abgeleitet/aufwand.json, je Antwort einmal gezählt) |
| `falldaten.py` | Datenmodell einer Falldarstellung aus den Artefakten |
| `fallbericht.py` | Darstellung aus dem Datenmodell rendern |
| `vorschau.py` | den Entwurf der Seite lokal ansehen, vor dem Schieben |
| `seitenpruefung.py` | die gebaute Seite prüfen: Verweise, was Pages anders liest als die Vorschau, Paket gegen `stand.json`, jede angezeigte Kennung mit Quelle, Breite auf dem Telefon (läuft im Bau mit) |
| `schau.py` | Screenshots der gebauten Vorschau in drei Breiten (1280, 720 und 390 px; braucht Playwright) |
| `bereinigung.py` | veröffentlichte Belege von Pfaden des Rechners befreien und die gebaute Seite auf solche Pfade und gesperrte Wörter prüfen |
| `naht.py` | meldet Bausteine, die ohne Abstand aneinanderkleben (braucht Playwright) |

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
handgeschriebene, versionierte Quellen unter `plv/seite/`; die
Migrationsberichte entstehen je Fall aus den Artefakten und hängen
auf der Seite unter `migrationen/<fall>/`. Jede Unternehmensseite muss die
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
    --ab1 <ablage>/A-B1.json \
    --film <ablage>/erklaerfilm.mp4 \
    [--verlauf verlauf.md]
```

Den Fall `faelle/baldrian-klv-tg2015-fall3` legt das Nachfahren an
(README, Schnellstart); Stands-Paket und Anker entstehen mit dem Export
weiter unten. Der letzte Schritt, die Vorschau, braucht das Paket
`markdown` im System-Python (siehe „Ansehen vor dem Schieben“);
`--vorschau ''` lässt ihn aus.

`--name` ist das URL-Segment unter `migrationen/`, so wie die
Unternehmensseiten den Fall verlinken. `--film` nennt den Film der
Startseite. Seine Bytes liegen nicht im Repository; der Bau hält sie gegen
die Prüfsumme in `unternehmensseite.FILM` und hält an, wenn die Datei fehlt
oder eine andere Fassung ist. Eine neue Fassung braucht eine neue Freigabe
und eine neue Prüfsumme. Das Vorschaubild liegt unter `plv/seite/film/`. Die Schritte der Kette bleiben
einzeln aufrufbar (`falldaten.py`, `vorzeigeseite.py
--als-unterseite`, `unternehmensseite.py --teil rahmen|betrieb --daten`,
`vorschau.py`).

### Rahmen und Betriebsteil

Die Seite hat zwei Teile (Entscheid des Maintainers vom 09.10.2026). Der
Betriebsteil liegt unter `betrieb/` und ändert sich jeden Abend mit dem
geführten Bestand: die Bestandsführung (Quelle `plv/seite/betrieb/`), das
Stands-Paket unter `betrieb/plv/` mit den Kopien seiner Berichte unter
`betrieb/berichte/`, die drei Grafiken der Startseite und die geltende
Auslieferung A-B1 als `betrieb/A-B1.json`. Alles andere ist der Rahmen; er
ändert sich nur per Pull Request nach plv-fiktion.

Die alten Adressen leiten im Rahmen weiter: `geschaeftsentwicklung/`, wo
die Bestandsführung vorher stand, auf `betrieb/`, und `plv/` („Bestand
heute“) auf `betrieb/plv/` (`plv/seite/<ordner>/index.html`). Die Seiten
haben keinen Vorspann, Jekyll gibt sie also unverändert aus. Ihr Ziel prüft
`seitenpruefung.py verweise` wie jeden Verweis. Sprungziele und einzelne
Dateien unter den alten Adressen kommen nicht mit.

`auftritt.py --teil beide` (Vorgabe) baut beides und prüft die ganze Seite.
`--teil rahmen` baut nur den Rahmen, ohne Stands-Paket, und lässt Vorschau
und Seitenprüfung aus, weil die Verweise in den Betriebsteil dann kein Ziel
haben. `--teil betrieb` baut nur `betrieb/` in einen Baum, der den Rahmen
schon trägt, ohne Fall: So baut der Workflow von plv-fiktion den Abend.

Jeder Teil hat sein eigenes Datenmodell. Der Rahmen nimmt das Modell des
Falls, und das trägt kein Stands-Paket; `unternehmensseite.py --teil
rahmen` weist ein Modell mit Paket ab. Der Betriebsteil nimmt das Modell
aus `falldaten.py` ohne `--fall`, nur aus Paket, Anker und A-B1
(`--stands-paket`, `--anker`, `--ab1`). Die A-B1 ist dabei eine Datei: der
Snapshot, der den Ankersatz des Pakets bindet. `falldaten.py` prüft
Struktur, Prüfsumme des Snapshots und diese Bindung, nicht die Signatur.

Die Startseite zeigt die drei Grafiken als Bild (`{{bild:bestand}}`,
`{{bild:zugang}}`, `{{bild:leistungen}}`). Der Rahmen kennt nur die
Dateinamen (`unternehmensseite.BILDER`); der Betriebsteil schreibt je
Grafik eine SVG-Datei für breite Fenster und eine für das Telefon
(`betrieb/<name>.svg`, `betrieb/<name>-handy.svg`). Ein Bild sieht das
Stylesheet der Seite nicht; `grafik.datei` schreibt deshalb jede Farbe als
Wert und die Größe in die Datei.

Die Bestandsführung nennt jede Übernahme mit Namen und verlinkt ihre Seite.
Weil der Betriebsteil den Fall nicht kennt, stehen Name und URL-Segment in
`unternehmensseite.UEBERNAHMEN`; der Rahmen hält den Eintrag gegen den Fall,
den er baut, und eine Übernahme im Paket ohne Eintrag hält den Betriebsteil
an. Die Seite des Falls zeigt die A-B1 nicht mehr: Sie nennt an Station 13
die Zugangsabnahme A-B2 und die gelieferten Summen und verweist auf die
Bestandsführung.

Im Zweig `betrieb` von plv-fiktion liegt das Paket ohne Tagesjournal und
Monatsabschlüsse, denn beide tragen Policennummern. Dafür gibt es
`--oeffentliches-paket` (bei `falldaten.py` und `auftritt.py`): Geprüft wird
jede vorhandene Datei gegen `stand.json`, die Protokollkette und was ihre
letzte Zeile über das Paket sagt, der Anker und die A-B1. Die Zahlen, die
nur Journal und Abschlüsse tragen, rechnet niemand nach; sie gelten, weil
der Ankersatz `stand.json` als Ganzes bindet (Ankersatz-Schema 4).

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

Für den Betriebsteil ist das Paket Pflicht: Die Bestandsführung zeigt den
geführten Bestand (`{{...:betrieb....}}`-Kennzahlen, Tabellen
`buchungen_je_art`, `abschluesse`, `uebernahmen_im_stand`), die Startseite
dessen Grafiken; ohne Paket bricht der Bau mit dem Hinweis auf den Aufruf
ab. Die Dateien des Pakets (Paketschema 6: die Tagesseite „Bestand heute“
als `index.html` und die bezeugten Berichte des jüngsten Abschlusses in der
Wurzel, die Monatsabschlüsse unter `abschluesse/`) übernimmt
`unternehmensseite.py` byteweise nach `<out>/betrieb/plv/`, jede gegen die
SHA-256 in `stand.json` gehalten, nichts wird umgeschrieben; die Vorschau
verlinkt das Verzeichnis ganz.
Bestandskennzahlen der Abschlüsse und Geschäftsentwicklung je Zeitraum
stehen seit Paketschema 6 auch in `stand.json`, und der Anker bindet
`stand.json`. `falldaten.py` rechnet beide aus den Abschlussdateien und
dem Tagesjournal des Pakets nach, nachdem es deren Hash geprüft hat, und
weist das Paket ab, wenn etwas anderes herauskommt. Den Abschluss zwölf
Monate vor dem jüngsten trägt
das Paket nicht; der Vorjahresvergleich entfällt dann benannt.

Einen Stand außerhalb der Laufzeitumgebung `~/apps/plv` liefert eine
Welt (`werkzeuge/welt/laufzeit_aufstellen.sh`, siehe
[werkzeuge/welt/README.md](welt/README.md)). Aus ihrer Ablage
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
Paket. `drift.py` vergleicht deshalb nur den Rahmen; `betrieb/` und
`CODESTAND` zählen dort nicht.

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
die Karte auf der Seite (`migrationen/#prozess`) und die Fallseite lesen dieselbe
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
und echte Fälle liegen außerhalb. Deshalb baut keine GitHub-Action die
Seite aus diesem Repository: Sie sähe die Artefakte nicht. Der Weg ist:
lokal bauen und den gebauten Baum als Commit in das eigene Repository der
Seite legen, `bartlmac/plv-fiktion`. Dort baut GitHub Pages ihn über
GitHub Actions mit demselben Renderer, den die Prüfungen hier messen
(`actions/jekyll-build-pages`). Die Seite liegt unter
https://bartlmac.github.io/plv-fiktion/.

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

Im Repository `bartlmac/plv-fiktion`: Pages mit der Quelle **GitHub
Actions**. Den Workflow bringt der Rahmen mit
(`plv/seite/.github/workflows/seite.yml`, im gebauten Baum unter
`.github/`). Jekyll lässt `.github/` beim Bauen aus. Lokal genügt ein Klon
neben diesem Repository:

```
git clone git@github.com:bartlmac/plv-fiktion.git ../plv-fiktion
```

Die Basis der Seite steht in `plv/seite/_config.yml` (`baseurl:
"/plv-fiktion"`). So ergeben der lokale Bau mit dem Renderer von Pages und
die Seite im Netz dieselben Pfade.

Der Workflow läuft bei einem Push auf `main`, von Hand und nach Zeitplan
(viermal in der Nacht nach dem Tageslauf, weil GitHub Zeitpläne verzögert
oder auslässt); ein Push auf den Zweig `betrieb` startet ihn nicht. Er nimmt
den Rahmen aus `main`, prüft den Zweig `betrieb` (`betriebszweig.py zweig`:
nur `paket/` mit den öffentlichen Dateien, `anker.jsonl`, `A-B1.json`, kein
`.github/`), holt den Code des Commits aus `CODESTAND` und baut damit den
Betriebsteil (`auftritt.py --teil betrieb --oeffentliches-paket`, mit Wache
und Seitenprüfung). Danach prüft `betriebszweig.py rahmen`, dass außerhalb
von `betrieb/` jede Datei wie in `main` ist. Erst dann baut Jekyll
(`jekyll-build-pages` v1.0.13), und nur ein Lauf aus `main` liefert aus.
Scheitert ein Schritt, wird nicht ausgeliefert, und die Seite vom Vortag
bleibt stehen. Jede Action ist auf einen Commit gepinnt.

Ein Push in dieses Repository veröffentlicht nichts. Veröffentlichen ist
nach außen gerichtet und praktisch nicht zurückzunehmen (Indexierung,
Caches); es bleibt eine menschliche Handlung: der Merge eines Pull Requests
für den Rahmen und, für den Betriebsteil, die Routine des Tagesbetriebs,
die der Maintainer eingerichtet hat.

### Je Lauf

Den Rahmen bringt ein Pull Request nach plv-fiktion. `rahmen_pr.py` baut
dafür die ganze Seite aus dem Commit, auf dem dieser Baum steht (mit Wache
und Seitenprüfung), und legt den Rahmen ohne `betrieb/` als einen Commit
auf einen neuen Zweig `beitrag/...` im Klon, in einem eigenen
Arbeitsverzeichnis (git worktree); der Klon selbst bleibt auf seinem Zweig.
Was der Rahmen nicht mehr enthält, fällt dabei weg, damit keine verwaisten
Dateien öffentlich liegen bleiben. Die Datei `CODESTAND` schreibt das
Kommando selbst: den Commit, aus dem es gebaut hat. Mit diesem Code rendert
der Workflow den Betriebsteil.

```
python werkzeuge/rahmen_pr.py --klon ../plv-fiktion \
    --fall faelle/<fall> --name <kurzname> \
    --abzug <abzug-1>.csv --abzug <abzug-2>.csv --film <ablage>/erklaerfilm.mp4 \
    --stands-paket <paket> --anker <anker>.jsonl --ab1 <A-B1>.json \
    [--oeffentliches-paket] [--zweig beitrag/rahmen-JJJJ-MM-TT] [--basis main]
```

Es hält an, wenn dieser Baum Änderungen außerhalb eines Commits trägt, wenn
Bau oder Prüfung einen Befund haben, wenn der Klon nicht sauber ist, wenn
der Zweig schon besteht oder nicht unter `beitrag/` liegt, und wenn der
Rahmen `main` schon gleicht. Es schiebt nichts. Push, Pull Request und
Merge macht der Maintainer, rechner-pipeline vor dem Merge: Liegt der
Commit aus `CODESTAND` nicht auf GitHub, findet der Workflow den Code nicht.

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

Mit dem Betriebsteil und der Vorschau fährt `auftritt.py` als letzten
Schritt `seitenpruefung.py alle`; ein Befund hält den Bau an wie die
Wache. Einzeln, etwa für einen Zweitbau:

```
python werkzeuge/seitenpruefung.py alle --seite runs/<bau>/seite \
    --vorschau runs/<bau>/vorschau --fall faelle/<fall> --name <kurzname> \
    --paket <stands-paket> --anker <anker>/anker.jsonl --ab1 <A-B1>.json \
    --daten runs/<bau>/falldaten.json --repo .
```

Ohne `--fall`, `--name` und `--daten` prüft `pruefsummen` nur den
Betriebsteil, mit Paket, Anker und A-B1 als Quellen, und `breite` nimmt die
Seiten jedes Falls im Baum als Hauptseiten. So läuft die Prüfung im
Workflow von plv-fiktion; den Rahmen prüft der Bau des Pull Requests.

| Prüfung | Befund |
|---|---|
| `verweise` | ein relativer Verweis ohne Ziel (auch das Ziel einer Weiterleitung), ein Sprungziel ohne id, ein absoluter Pfad; in einem Beleg (`artefakte/`, `betrieb/plv/`) nur ein Hinweis, weil Belege unverändert erscheinen. Verweist ein Beleg vom Fallordner aus, legt der Bau dort, wohin der Browser auflöst, eine Weiterleitung ab; das Manifest der Bereinigung nennt sie |
| `pages` | was Pages (Liquid, dann kramdown) anders liest als die Vorschau: eine Überschrift, die auf eine Attributliste `{: ...}` endet (eine eigene id heißt `{#x}`); `{{` oder `{%` außerhalb von raw; jedes `$` außerhalb von Code und `$$...$$` (kramdown kennt nur `$$...$$` als Formel); eine Seite, die nicht mit einer Überschrift beginnt (dann hat sie keinen Titel); eine .md unter `artefakte/` oder `betrieb/plv/` (Pages entfernte das Original) |
| `paket` | eine Datei unter `betrieb/plv/`, die von `stand.json` abweicht oder dort fehlt; ein nicht veröffentlichter Eintrag außer Parquet; ein Bericht unter `betrieb/berichte/` ohne bytegleiche Datei im Paket |
| `pruefsummen` | eine angezeigte Kennung ohne Quelle (Datei des Falls, Manifest, Snapshot, Lieferregister, Paket, Anker, Protokoll, A-B1, Commit) |
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
python werkzeuge/drift.py --seite runs/seite [--repo ../plv-fiktion] [--ref main]
```

Vergleicht den frisch gebauten Entwurf mit dem Stand im Repository der
Seite.
Volatile Stempel (Veröffentlichungsdatum, Systemstand der
Fall-Seiten, Bau-Commit der Landkarte) zählen nicht als Drift;
sonst schlüge der Test immer, und ein Alarm, der immer schlägt,
wird abgeschaltet. Exit 1 listet die Abweichungen; aktualisiert wird
von Hand (Abschnitt „Je Lauf“).
