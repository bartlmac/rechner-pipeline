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
| `grafik.py` | Bausteinsatz der generierten Darstellungen (Inline-SVG/HTML, modellfrei) |
| `darstellung.py` | Abbildung Modellpfad -> Baustein-Eingabe, an einer Stelle |
| `drift.py` | den veroeffentlichten Stand gegen den Entwurf halten |
| `umbaubudget.py` | wie weit ein Lauf das System umgebaut hat |
| `aufwand.py` | den Verbrauch der Agenten eines Falls aus ihren Sitzungsprotokollen festhalten (abgeleitet/aufwand.json, je Antwort einmal gezaehlt) |
| `falldaten.py` | Datenmodell einer Falldarstellung aus den Artefakten |
| `fallbericht.py` | Darstellung aus dem Datenmodell rendern |
| `vorschau.py` | den Entwurf der Seite lokal ansehen, vor dem Schieben |
| `seitenpruefung.py` | die gebaute Seite pruefen: Verweise, Paket gegen `stand.json`, jede angezeigte Kennung mit Quelle, Breite auf dem Telefon (laeuft im Bau mit) |
| `schau.py` | Screenshots der gebauten Vorschau, breit und schmal (braucht Playwright) |
| `naht.py` | meldet Bausteine, die ohne Abstand aneinanderkleben (braucht Playwright) |
| `vorfuehrung.py` | einen Fall in tmux fuehren: Cockpit und je Agentenrolle ein Fenster |
| `lagebild.py` | wo ein Fall steht — die Anzeigen der Vorfuehrung, nur lesend |
| `aufzeichnung.py` | die Vorfuehrung mitschneiden und als asciicast ausgeben |
| `sitzungsprobe.py` | ob ein Agenten-Werkzeug die Sitzungen der Vorfuehrung traegt |

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
--als-unterseite`, `unternehmensseite.py --daten`, `vorschau.py`).

Die Kennzahlen der Quellseiten sind `{{...}}`-Platzhalter und werden
beim Bau aus dem falldaten-Modell des Falls aufgeloest — generiert
statt gepflegt: Eine Zahl, die niemand abtippt, kann dem Fall nicht
davonlaufen. Ein unaufloesbarer Platzhalter bricht den Bau ab. Neben
Zahlen (`zahl`, `euro`, `datum`, `text`) gibt es generierte Bausteine
(`html:kennzahlenband`, `html:toleranz`, `html:stationen`,
`html:widerspruch`, `html:abgrenzungsband`, `html:berichte`,
`svg:gevo_je_art`, `svg:zugang_status`, `tabelle:gevo_je_art`); die
Zuordnung Modellpfad -> Baustein steht in `werkzeuge/darstellung.py`,
die Bausteine selbst in `werkzeuge/grafik.py`. Welche Stellen
automatisiert sind und welche bewusst Prosa bleiben, steht in
`dev-docs/vorzeige-statische-stellen.md`.

Drei Darstellungsregeln, die die Bausteine erzwingen: Ein bestandener
Test wird nie ohne seinen Massstab genannt (Schranke neben groesster
Abweichung, Absolutwerte auf gemeinsamer Achse — keine Ausschoepfungs-
quote als Vergleich zwischen Abnahmen); Pruefumfaenge stehen einzeln
mit Einheit, nie als Summe (die Mengen sind nicht disjunkt); und die
Grenzen stehen an fester Stelle neben dem Ergebnis — ein leeres
Abgrenzungsband nennt, was die Artefakte hergeben, und behauptet keine
Vollstaendigkeit.

`--stands-paket <verzeichnis>` gibt der Kette das Stands-Paket der
Laufzeitumgebung des Tagesbetriebs mit (`python -m
rechner_pipeline.betrieb.seite --stand <daten> --paket <verzeichnis>`,
Fachkonzept `docs/simulation/tagesbetrieb.md`, Abschnitt 8.3): Der
lebende Bestand der PLV wird ein Abschnitt des Datenmodells und des
Fallberichts — mit Stand-Datum, Manifest-Hash und der Zeichnung der
uebernommenen Faelle, aus dem Paket gelesen, nie abgetippt. Ein Paket,
dessen Stand nicht durch P-B1 ging, weist `falldaten.py` ab.

Fuer die Unternehmensseiten ist das Paket PFLICHT: Startseite,
Geschaeftsentwicklung und Finanzen zeigen den gefuehrten Bestand
(`{{...:betrieb....}}`-Kennzahlen, Tabellen `buchungen_je_art`,
`abschluesse`, `uebernahmen_im_stand`); ohne Paket bricht der Bau mit
dem Hinweis auf den Aufruf ab. Die Dateien des Pakets (Paketschema 5:
die Tagesseite "Bestand heute" als `index.html` und die bezeugten
Berichte des juengsten Abschlusses in der Wurzel, die Monatsabschluesse
unter `abschluesse/`) uebernimmt `unternehmensseite.py` byteweise nach
`<out>/plv/`, jede gegen die SHA-256 in `stand.json` gehalten, nichts
wird umgeschrieben; die Vorschau verlinkt das Verzeichnis ganz.
Bestandskennzahlen der Abschluesse und Geschaeftsentwicklung je Zeitraum
stehen NICHT in `stand.json`: `falldaten.py` rechnet sie aus den
Abschlussdateien und dem Tagesjournal des Pakets nach, nachdem es deren
Hash geprueft hat. Den Abschluss zwoelf Monate vor dem juengsten traegt
das Paket nicht; der Vorjahresvergleich entfaellt dann benannt.

Einen Stand ausserhalb der Laufzeitumgebung `~/apps/plv` (z. B. auf dem
Entwicklerrechner, Wegwerf unter `runs/`) erzeugt man so — Config
kopieren, Uebernahme registrieren, Tage fuehren, Paket exportieren:

```
mkdir -p runs/plv-stand/configs
cp configs/bestand_gesamt.toml runs/plv-stand/configs/bestand.toml
python -m rechner_pipeline.betrieb.uebernahme --stand runs/plv-stand \
    --fall faelle/<fall> --stichtag 2026-01-01
python -m rechner_pipeline.betrieb.tageslauf --stand runs/plv-stand --heute <heute>
python -m rechner_pipeline.betrieb.seite --stand runs/plv-stand \
    --paket runs/stands-paket --anker runs/anker
python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \
    --abzug ... --stands-paket runs/stands-paket --anker runs/anker/anker.jsonl
```

Der Anker liegt AUSSERHALB des Pakets (T24-04 Teil 2): Ein Paket, das nur
sich selbst belegt, kann seine eigene Herkunft behaupten. `runs/anker`
taugt dafuer nur in der Probe — `runs/` ist Wegwerf, und ein Anker in
einem Verzeichnis, das jemand planmaessig leert, ist so wenig ein Anker
wie einer im Paket. Der echte Anker gehoert in den Fall-Datenraum.

Und der Export schreibt nebenbei die Tagesseite in die Ablage — wer nur
ein Paket ziehen will, arbeitet deshalb auf einer Kopie, nicht auf der
Laufzeit.

Der Stand ist ein Datum: Jeder neue Tageslauf aendert Kennzahlen und
Paket, und `drift.py` meldet das als Abweichung — gewollt, die
veroeffentlichte Seite ist eine gestempelte Momentaufnahme.

Die Zahlen der Seite kommen aus dem Datenmodell (`falldaten.py`) —
demselben, aus dem auch der Fallbericht gerendert wird. Seite und
Bericht tragen damit dieselben Zahlen aus derselben Quelle; frueher
lasen beide die Fall-Artefakte getrennt, und zwei Leser desselben
Datenraums driften auseinander. Was die Seite selbst tut, ist
Veroeffentlichung: die Belege der Belegkette kopieren, die Regie
sperren, Systemstand und Branch stempeln, `index.md`, `_config.yml` und
`artefakte/` schreiben.

Welche Datei des Falls an welche Station gehoert, erhebt
`falldaten.belegkette` aus dem, was die Kette selbst sagt — keine Tabelle
von Hand: der Ort im Fall-Arbeitsbereich, wo kein Gate einen Erzeuger
nennt, aber nur fuer eine Datei, die die Kette fuehrt oder das
Eingangsregister traegt; Entscheid-Snapshots und Pruefprotokolle zur
Station ihres Gates; Pflichtbelege eines Entscheids ueber ihre
Pruefsumme zur Station des Gates, dessen Beleg sie sind; was ein Gate
geschrieben hat; der Beleg einer Entscheidung, den die A-Box mit Pfad
und Pruefsumme nennt, zur Quellenabnahme; was ein Gate zur Pruefung
gelesen oder mit Pruefsumme genannt hat; Geschwister daneben. Das
Protokoll einer Zeichnung zaehlt nicht als Leser. Eine Ausnahme ist
benannt: Die deterministische Vorverdichtung der Quellen
(`abgeleitet/vorverdichtung/`) bindet kein Protokoll ueber die
Pruefsumme; sie steht trotzdem an Station 2, mit dem Vermerk "nicht
gebunden". Was das Datenmodell fuer eine Zahl der Seite liest, kommt
ohne Station mit. Was keine Regel trifft — Arbeitsunterlagen der
Agenten, Reste frueherer Durchgaenge, ein Dateiname, der nach einem Gate
klingt —, kommt nicht auf die Seite und wird gezaehlt. Die Regeln stehen
im Docstring der Funktion; die Karte (`migrationen/#prozess`) und die
Fallseite lesen dieselbe Zuordnung aus dem Modell.

Die Aenderung am Zielsystem ist ein Pflichtabschnitt des Modells: Ein
abgeschlossener Fall traegt sie immer — ein Lauf, dessen Umbau niemand
gemessen hat, saehe sonst aus wie ein Lauf ohne Umbau. Seit der Abnahme
des Stands (ADR-018 Nachtrag 01.10., ADR-025) sind es die
Aenderungsbelege von Kern (A-K2) und Tarifwerk (A-T1); aeltere Laeufe
tragen ein Umbaubudget. Fehlt beides, meldet `falldaten.py` eine Luecke
(Exit 3). Das Umbaubudget eines aelteren Laufs wird so in den Fall
erhoben:

```
python werkzeuge/umbaubudget.py --basis <startpunkt> \
    --json faelle/<fall>/abgeleitet/berichte/umbaubudget.json
```

Die Seite rechnet nichts Fachliches nach. Jede Zahl steht so in einem
Artefakt, das unter `artefakte/` daneben liegt — sonst waere die
Vorfuehrung eine Behauptung ueber sich selbst. Was sie zaehlt (Belege je
Station, Kennzahlen aus den Abschlussdateien des Pakets), zaehlt sie aus
Bytes, deren Hash sie geprueft hat. Verlinkt wird nur, was die
Belegkette einer Station zuordnet und tatsaechlich kopiert ist, und die
Regie-Sperre prueft auch die Verweise aus dem Modell noch einmal selbst. Ein NICHT bestandener Test und eine
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

### Bereinigung der veroeffentlichten Belege

Es gibt zwei Wege der Veroeffentlichung: den Code (die wiederherstellbare
Routine) und die Vorzeige (die Webseite mit den Artefakten eines Falls).
Die Belege eines Laufs tragen, was ihre Kommandos gesehen haben — auch die
absoluten Pfade des Rechners, auf dem sie liefen: den Arbeitsbaum des
Falls, die Laufzeitumgebung, das Verzeichnis des Schluesselmaterials. Die
Belege sind ueber Pruefsummen gebunden und bleiben, wie sie sind; die
Behebung im Produzenten (Pfade relativ in den Ledgern, ein Herkunftsfeld
beim Registrieren) ist Arbeit fuer den naechsten Lauf. Bereinigt wird
deshalb nur die veroeffentlichte Fassung, als Stufe im Bau der Seite
(Entscheid des Maintainers, 03.10.2026; `werkzeuge/bereinigung.py`):

- **Regel statt Handarbeit.** `vorzeigeseite.py` ersetzt beim Kopieren
  jeden Hostpfad, den eine Regel kennt, durch einen benannten Platzhalter:
  `<baum>` (der Arbeitsbaum, in dem der Fall liegt — erhoben aus dem Pfad
  des Falls), `<schluesselverzeichnis>` (`~/.rechner-pipeline-schluessel`),
  `<welt>` (die Laufzeitumgebung unter `~/apps`), `<laufordner>` (ein
  Laufverzeichnis ausserhalb des Falls, `~/git/<baum>/runs/<ordner>`, wo
  Stands-Paket und Anker liegen). Deterministisch:
  dieselben Bytes ergeben dieselbe Fassung. Bereinigt wird nur Text; traegt
  eine andere Datei einen Hostpfad, haelt der Bau an.
- **Ein Entscheid-Snapshot wird nie bereinigt.** Eine Aenderung braeche
  seine Signatur und die Verweise der Folgeentscheide. Ein ueberholter
  Snapshot, der etwas traegt, das nicht auf die Seite gehoert, bleibt
  unveroeffentlicht und steht benannt da (Pruefsumme, Status "ueberholt,
  nicht veroeffentlicht"); traegt es ein geltender oder einer, den das
  Modell nicht kennt, haelt der Bau an — das entscheidet ein Mensch.
- **Das Manifest** `artefakte/bereinigung.json` nennt je bereinigter Datei
  die Pruefsumme des Originals im Fall, die Entscheide, die dieses Original
  ueber seine Pruefsumme binden, die Pruefsumme der veroeffentlichten
  Fassung und die Ersetzungen je Regel, dazu jede zurueckgehaltene Datei
  mit ihrer Pruefsumme. "Gebunden" steht nur, wo ein Entscheid die
  Pruefsumme nennt: In Fall 3 binden Entscheide das Eingangsregister, den
  Abnahmebericht und die Zugangsprobe; die Protokolle der Zeichnungen
  bindet keiner — sie entstehen mit der Zeichnung. Alle uebrigen Belege
  unter `artefakte/` sind bytegleich mit ihren Originalen im Fall; die
  Ansichten der Lieferung (`artefakte/lieferung/`) sind Ansichten — eine
  CSV als Vorschau ihrer ersten Zeilen, alles Uebrige bytegleich. Die
  Fallseite sagt das im Abschnitt "Bereinigt veroeffentlicht". Die Kette
  bleibt nachvollziehbar — ueber das Manifest statt ueber identische
  Bytes.
- **Die Wache** liest nach dem Bau jede veroeffentlichte Datei: den Namen,
  die Bytes und, wo die Seite komprimiert veroeffentlicht, den entpackten
  Inhalt (Parquet: Schema, Metadaten und jede Spalte ausser Zahlen und
  Zeiten; PDF: die Flate-Stroeme). Kein Hostpfad — `/home/`,
  `/tmp/claude`, beide auch JSON-maskiert, `/Users/`, `C:\Users\`, der
  Projektordner `-home-<benutzer>-` —, kein gesperrtes Wort. Eine Datei,
  die sie nicht lesen kann, ist ein Befund. Sie laeuft am Ende von
  `vorzeigeseite.py` und in `auftritt.py` ueber den ganzen Push-Baum,
  Stands-Paket und Fachdokumente eingeschlossen. Was keine Regel kennt,
  wird nicht still ersetzt, sondern haelt den Bau an: dann eine Regel
  ergaenzen, den Produzenten beheben oder die Datei zurueckhalten.

Nachpruefen, mit dem Fall in der Hand, aus dem Baum, in dem er liegt:

```
python werkzeuge/bereinigung.py --pruefe <seite>/migrationen/<name> --fall faelle/<fall>
python werkzeuge/bereinigung.py --wache <seite>
```

`--pruefe` rechnet die gebaute Fallseite gegen den Fall nach: Je
bereinigter Datei hat das Original im Fall die genannte Pruefsumme und die
genannten Bindungen (aus der Belegkette), die Regeln ergeben daraus die
veroeffentlichte Fassung mit denselben Ersetzungszahlen, und die Datei auf
der Seite hat deren Pruefsumme. Jede zurueckgehaltene Datei liegt mit ihrer
Pruefsumme im Fall und unter keinem Namen auf der Seite. Jede andere Datei
unter `artefakte/` hat ein Gegenstueck im Fall und ist bytegleich mit ihm;
die Vorschau einer gelieferten CSV wird neu erzeugt und verglichen; eine
Datei ohne Gegenstueck ist ein Befund. Und kein Beleg, den die Belegkette
einer Station zuordnet, fehlt auf der Seite. Liegt der Fall anderswo als
beim Bau, ergibt die Regel `<baum>` einen anderen Pfad, und die Pruefung
schlaegt an — gewollt: Sie prueft die Fassung, die gebaut wurde.

Das Stands-Paket bereinigt die Stufe nicht: Der Auftritt veroeffentlicht
es bytegleich und an seine Pruefsumme gebunden. Einen Hostpfad traegt es
nur, wenn `betrieb.seite --anker` absolut aufgerufen wurde (`stand.json`,
Feld `anker.datei`) — deshalb `--paket` und `--anker` relativ aus dem
Hauptbaum angeben.

Grenzen: Die Wache kennt die Schreibweisen oben — eine Kurzform wie `~/`
(sie steht in den Fachdokumenten erlaubt), UTF-16 oder Base64 sieht sie
nicht, und die Wortliste faengt nur, was sie kennt: Ein privater Termin in
anderer Formulierung bleibt Sache der Durchsicht von Hand vor der
Veroeffentlichung. Ein Verlaufsprotokoll (`--verlauf`) bereinigt die Stufe
nicht; es traegt Hostpfade, und die Wache haelt den Bau an.

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

### Die gebaute Seite pruefen

Mit Stands-Paket, Anker und Vorschau faehrt `auftritt.py` als letzten
Schritt `seitenpruefung.py alle`; ein Befund haelt den Bau an wie die
Wache. Einzeln, etwa fuer einen Zweitbau:

```
python werkzeuge/seitenpruefung.py alle --seite runs/<bau>/seite \
    --vorschau runs/<bau>/vorschau --fall faelle/<fall> --name <kurzname> \
    --paket <stands-paket> --anker <anker>/anker.jsonl \
    --daten runs/<bau>/falldaten.json --repo .
```

| Pruefung | Befund |
|---|---|
| `verweise` | ein relativer Verweis ohne Ziel, ein Sprungziel ohne id, ein absoluter Pfad |
| `paket` | eine Datei unter `plv/`, die von `stand.json` abweicht oder dort fehlt; ein nicht veroeffentlichter Eintrag ausser Parquet; ein Bericht unter `berichte/` ohne bytegleiche Datei im Paket |
| `pruefsummen` | eine angezeigte Kennung ohne Quelle (Datei des Falls, Manifest, Snapshot, Lieferregister, Paket, Anker, Protokoll, Commit) |
| `breite` | eine Hauptseite, die auf dem Telefon (390 px) breiter ist als der Bildschirm; die uebrigen Seiten stehen als Hinweis da (Ansicht am Schreibtisch hat Vorrang, Entscheid 04.10.2026) |

`breite` braucht Playwright wie `schau.py`; fehlt es, meldet `alle`
"NICHT GEPRUEFT" statt still zu ueberspringen.

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
Fehlt dem Fall ein Pflichtabschnitt, steht das auf der Seite im
Kleingedruckten unter "Grenzen dieses Laufs", und das Werkzeug endet mit
Exit 3 (T20-03).

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

### Ansehen, bevor man etwas meldet

Die Gestaltung laesst sich nicht rechnen, nur ansehen. `werkzeuge/schau.py`
macht Screenshots der gebauten Vorschau (breit 1280 px, schmal 720 px, je
ganzseitig):

```
.venv/bin/pip install playwright && .venv/bin/playwright install chromium
.venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau
.venv/bin/python werkzeuge/schau.py runs/vorzeige-vorschau runs/schau index.html
```

Ohne Seitenangabe nimmt es die Standardliste (Startseite, Vertiefungen,
Fallbericht); mit Angabe nur die genannten Seiten — das ist der Weg, wenn
man an einer Stelle arbeitet. Fehlt Playwright, nennt das Werkzeug den
Installationsbefehl und endet mit Status 2, statt einen ImportError zu
werfen.

Playwright ist Werkstattausruestung, keine Abhaengigkeit des Systems: Die
Suite braucht es nicht, der Bau der Seite auch nicht. Es bleibt darum aus
`requirements*.txt` heraus, und das haelt auch
`tests/test_abhaengigkeiten.py` bei seiner Aufgabe — die Closure schliesst,
was das System zum Laufen braucht, nicht was eine Werkstatt zufaellig hat.
Das Paket landet in der `.venv`, die Browser-Dateien unter
`~/.cache/ms-playwright/` (einige hundert MB, einmalig).

Fuer den zweiten Blick — die Seite auf einem anderen Geraet ansehen —
genuegt ein beliebiger statischer Webserver auf `runs/vorzeige-vorschau/`;
die Vorschau ist ein Verzeichnis gewoehnlicher Dateien.

Ganzseitige Bilder werden schnell drei- bis zehntausend Pixel hoch; wer
sie am Stueck betrachtet, sieht nichts. Ausschnitte lesen:

```
.venv/bin/python -c "from PIL import Image; b=Image.open('runs/schau/index-breit.png'); \
  b.crop((0, 700, b.width, 1700)).save('runs/schau/ausschnitt.png')"
```

(`pillow` ist bereits gepinnt — es haengt an matplotlib.)

Eine Fehlerklasse laesst sich auch messen statt betrachten:
`werkzeuge/naht.py` oeffnet jede gebaute Seite im selben Browser und
meldet Paare von Bausteinen, zwischen denen weder Leerzeichen noch Rand
steht:

```
.venv/bin/python werkzeuge/naht.py runs/vorzeige-vorschau
```

Die erzeugten Bausteine liefern ihre Teile ohne Trennzeichen — eine
Kachel schreibt Titel, Formatmarke, Kennzahl und Zweck hintereinander,
den Abstand setzt das Stylesheet. Fehlt dort eine Regel, steht auf der
Seite "A-M1 StichtagstestHTML". Rueckgabe 0 heisst sauber, 1 nennt die
Fundstellen. Treffer koennen auch aus importierten Fachdokumenten
stammen (eine Hervorhebung mitten im Wort); dann liegt die Quelle in
`docs/` und wird dort behoben, nicht auf der Seite.

Was auf diesem Weg gefunden wurde und von keinem Test gesehen wird: eine
ungueltige `font:`-Kurzform (`font: 700 1.3rem/1.3 inherit` — `inherit` ist
keine Schriftfamilie), die den ganzen Block verwirft; ein SVG ohne
Breitenanschlag, das hochskaliert und seine Schrift mitnimmt; eine
Grafik, die breiter gezeichnet ist als ihre Spalte und darum
heruntergerechnet wird, bis die Beschriftung nicht mehr lesbar ist; eine
`table` mit `width: 100 %` neben Aussenraendern, die rechts hinauslaeuft
(Prozente rechnen gegen den Elternblock, die Raender kommen obendrauf).

## Drift pruefen

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

## Einen Fall vorfuehren und aufzeichnen

```
python werkzeuge/vorfuehrung.py --fall faelle/<fall> --linie <linie> --stand <ablage> --modell <modell>
tmux attach -t vorfuehrung
```

Baut die tmux-Session `vorfuehrung`:

| Fenster | links | rechts |
|---|---|---|
| `cockpit` | Chat mit dem Programmleitungs-Agenten | Lebenslauf des Falls, die letzten Entscheide, Systemstand und Laufzeit |
| `aktuariat`, `architektur`, `rechenkern`, `betrieb` | Chat mit dem Agenten der Rolle | ihre Gates mit Stand und Belegen |
| `mensch` | leere Shell fuer die Zeichnungen | |

Die Fenster folgen den Agentendateien unter `.claude/agents/`; eine neue
Rolle bekommt ihr Fenster ohne Aenderung am Werkzeug. Die Chats starten mit
`claude --agent <rolle> --model <modell>`; `--modell` ist Pflicht und hat
keine Vorgabe (sonst erbte jeder der fuenf Chats das Modell des Kontos).
`--ohne-chat` baut nur das Geruest (Probe) und braucht kein Modell,
`--trocken` gibt die tmux-Kommandos aus. Eine Session gleichen Namens wird
nie ersetzt.

Gezeichnet wird im Fenster `mensch`, nie in einem Agentenfenster: Ein Agent
zeichnet keine Annahme, und die Schluessel liegen ausserhalb des Falls.

Die Anzeigen rechts sind `werkzeuge/lagebild.py` unter `watch`:

```
python werkzeuge/lagebild.py lebenslauf --fall faelle/<fall> --linie <linie>
python werkzeuge/lagebild.py entscheide --fall faelle/<fall> --linie <linie> -n 12
python werkzeuge/lagebild.py system --linie <linie> --stand <ablage>
python werkzeuge/lagebild.py rolle <rolle> --fall faelle/<fall> --linie <linie>
python werkzeuge/lagebild.py zugangsprobe --fall faelle/<fall>
```

Das Lagebild ist eine Anzeige, kein Urteil. Es liest die Entscheid-Snapshots
ohne Schluessel und prueft weder Signatur noch Rolle noch Beleg — das tun
die Gates. Zwei Spitzen einer Kette zeigt es als `mehrdeutig`, eine nicht
lesbare Datei als `unlesbar`, nie als `offen`.

Die Sicht `zugangsprobe` ist keine der Anzeigen rechts: Sie zeigt den Beleg
der Zugangsprobe als Lesefassung fuer die Zugangsabnahme A-B2 — Urteil,
Folgetermin und je Vergleich Soll, Ist und Differenz —, ohne die Pruefsummen
der Abschluesse, die den Beleg selbst unlesbar gross machen. "Bestanden"
steht dort nur, wenn der Beleg es woertlich sagt; ein Vergleich ohne Soll
ist als solcher ausgewiesen.

### Aufzeichnen

Aufgenommen wird mit `script` aus util-linux; auf dem Host wird dafuer
nichts installiert. tmux zeichnet das Layout selbst, die Aufnahme enthaelt
also alle Panes.

```
python werkzeuge/aufzeichnung.py aufnehmen --session vorfuehrung --out runs/fall3
python werkzeuge/aufzeichnung.py cast --basis runs/fall3
scriptreplay -T runs/fall3.tim -O runs/fall3.out
```

`aufnehmen` haengt sich an die Session und endet mit dem Abhaengen
(`Ctrl-b d`); die Session laeuft weiter. `cast` erzeugt `runs/fall3.cast`
im asciicast-Format (Version 2): klein, der Text bleibt kopierbar, die
Wiedergabe laeuft in jedem asciinema-Player, im Terminal oder im Browser.
Die Terminalgroesse kommt aus der Kopfzeile der Aufnahme und wird nie
geraten. `scriptreplay` spielt die Aufnahme ohne jedes weitere Programm ab.

Ein GIF oder Video entsteht aus der `.cast`-Datei mit `agg` und `ffmpeg`,
auf einem beliebigen Rechner oder in einem Container:

```
agg runs/fall3.cast fall3.gif
ffmpeg -i fall3.gif -movflags faststart -pix_fmt yuv420p fall3.mp4
```

Eine Aufnahme zeigt, was auf dem Bildschirm steht. Schluesseldateien werden
nur als Pfad genannt, nie ausgegeben; `runs/` ist nicht versioniert.

### Traegt ein Agenten-Werkzeug die Sitzungen?

Die Chats der Vorfuehrung starten mit Claude Code. Soll ein anderes
Agenten-Werkzeug die Rollen fuehren — oder ein Fall ohne Menschen an jeder
Station laufen, sodass eine Sitzung der anderen Auftraege ins Fenster
schreibt —, zeigt eine Probe in wenigen Minuten, ob das traegt:

```
python werkzeuge/sitzungsprobe.py probe --kommando "<start eines chats>" \
    [--session sitzungsprobe] [--bericht runs/sitzungsprobe.md]
```

Sie baut eine eigene tmux-Session mit zwei Fenstern, startet in beiden das
Werkzeug und prueft vier Schritte: START (es kommt zur Ruhe), EINGABE (eine
von aussen geschriebene Zeile wird beantwortet), RUHE (von aussen erkennbar,
wann die Sitzung fertig ist) und WEITERGABE (eine Sitzung schreibt der
anderen auf Auftrag eine Zeile ins Fenster). Der Bericht nennt je Schritt das
Urteil, die Zeilen, an denen man "arbeitet noch" sieht, und die Bildschirme —
auch den einer Rueckfrage oder einer Sandbox, an der die Weitergabe haengt.

Die Probe urteilt nach dem Bildschirm und kostet zwei kurze Chats mit
zusammen drei Einzeilern. Sie ersetzt nie eine bestehende Session und laesst
ihre eigene stehen (`tmux kill-session -t sitzungsprobe`).
