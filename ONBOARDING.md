# ONBOARDING — rechner-pipeline

Für alle, die mit dem Repository arbeiten wollen: einrichten, die Laufzeit
aufstellen, einen Fall führen, die Regeln kennen. Was das Repository ist und
wo welches Dokument liegt, steht im [README](README.md).

## 1. Was das ist

Ein System für die **Bestandsmigration Leben**, mit **keinem LLM-SDK im
Code**: Der CLI-Agent ist das Modell; Python-Code verdichtet vor, validiert,
rechnet und nimmt ab.

Das Repository trägt fünf Gegenstände (ADR-027): die Laufzeit der PLV, das
Migrationssystem, die Fall-Definitionen, die Routinen und die Webseite. Für
die Arbeit am Code sind drei Teile des Pakets wichtig:

1. **Der Zielkern** (`rechner_pipeline.kern`): ein stabiler, versionierter
   Rechenkern, ganz in der Welt des Zustandsmodells formuliert
   (Semi-Markov-Rückgrat, Thiele-Rekursion auf reinen
   Ausscheidewahrscheinlichkeiten). Zwei Produkte — die gemischte
   Versicherung (KLV) und die Berufsunfähigkeit (BU) — sind *Konfigurationen*
   dieses Rückgrats, keine eigenen Rechenwerke. Die klassische
   Kommutationsrechnung ist kein Teil des Pakets; sie lebt als unabhängiger
   Zeuge in den Tests des Kerns (`tests/kommutationszeuge.py`).
2. **Der Bestand** (`rechner_pipeline.bestand`) und der **Tagesbetrieb**
   (`rechner_pipeline.betrieb`): synthetische, fortschreibbare Bestände, die
   der Zielkern unmittelbar rechnet. Jeder Betrag kommt aus dem Kern; das
   Modul trägt keine eigenen aktuariellen Formeln.
3. **Die Migrations-Pipeline** (der Hauptpfad): heterogene Quellen
   (Tarifmeldung, Bedingungen, Tarifrechner, Bestandsabzüge) -> Ontologie
   (T-Box und A-Box mit Herkunft je Aussage und Diskrepanz-Objekten) ->
   Tarif-Spez -> parametrierter Kern -> Abnahme gegen die Lieferung, mit
   menschlichen Gates und unveränderlichen, gezeichneten Snapshots.

Zuerst lesen: `docs/architektur/ablauf-eines-falls.md`, dann den
Rollenkatalog `docs/architektur/skill-architektur.md`, dann die ADRs unter
`docs/architektur/`.

**Zur Geschichte:** Das Projekt begann mit einem einmaligen
*Übersetzungsakt* — ein Coding-Agent portierte einen Excel/VBA-Rechner in
einen Python-Kern, abgenommen von einer deterministischen Gate-Kette
(617 von 617 Werten, 2026-07-22). Dieser Beweis ist erbracht. Die
Portierungs-Mechanik ist seit dem 2026-08-17 außer Betrieb.

Was sie ersetzt, ist NICHT „jede Migration ist Parametrierung". Diese
Lesart ist in ADR-007 ausdrücklich berichtigt: Eine Generation, die das
Zielsystem schon abdeckt, ist eine Parametrierung über den Modellpunkt. Der
**Normalfall ist das Gegenteil**: Ein abgegebener Bestand bringt
Leistungsmerkmale mit, die der Kern noch nicht kennt, und die Migration ist
eine intensive, knotengebundene CODE-Erweiterung des einen Trunks — in
kleinen Inkrementen, die nur mit grüner Gesamt-Suite landen, einschließlich
der eingefrorenen Referenzwerte aller anderen Fälle
(`integriere-migrationsinkrement`). Neue Produkte kommen über die T-Box
(Gate A-O1, der T-Box-Stand, gezeichnet von `mensch/architektur`); eine
Änderung am Kern wird als Kernstand unter A-K2 abgenommen (gezeichnet von
`mensch/rechenkern`).

Ein Migrationsfall lebt in einem **Fall-Arbeitsbereich**
(`python -m rechner_pipeline.fall`, ADR-002). Die Artefakte dort gehören der
**Pfefferminzia Lebensversicherung (PLV)** — dem erfundenen Versicherer, an
dem das System vorgeführt wird. `configs/` hält die Bestands-Konfigurationen
der PLV, `tests/fixtures/` synthetische Quellmappen für die
Extraktions-Tests, `lieferungen/` die Lieferungen erfundener abgebender
Gesellschaften. Es gibt keinen impliziten Eingangskanal: In einen Fall
gelangt eine Quelle nur über die ausdrückliche Registrierung (unten).

## 2. Einrichten

Die Referenzumgebung ist **Linux mit CPython 3.11** und genau den Pins
unten — das fährt die CI, und daraus entsteht das Image der Laufzeit. Der
Code wird nicht auf andere Betriebssysteme gehärtet (Entscheid des
Maintainers 2026-09-06): Wer nicht auf Linux arbeitet, fährt alles im
Container, der die Referenzumgebung IST.

**Unter Linux**, ohne LLM-Key:
```
python -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pip install -e . --no-deps
```

**Unter Windows zuerst WSL 2 prüfen.** Die WSL-Integration von Docker
Desktop verlangt eine Distribution unter **WSL Version 2**. Ein
Windows-Rechner kann eine WSL-Umgebung tragen, die noch auf Version 1
steht; dann lässt sich die Integration gar nicht einschalten, und der
Fehler ist nicht offensichtlich. Vor dem Bauen prüfen:
```
wsl -l -v
```
Jede Distribution, die benutzt werden soll, muss `VERSION 2` zeigen. Wenn
keine das tut, eine frische installieren — diesen Weg ist ein Teammitglied
tatsächlich gegangen:
```
wsl --install -d Ubuntu
wsl -d Ubuntu
```
Eine vorhandene Distribution der Version 1 lässt sich umstellen
(`wsl --set-version <distribution> 2`, mit dem Namen aus der ersten Spalte
von `wsl -l -v`); diesen Weg ist hier noch niemand gegangen.

**Überall sonst** (Windows mit Docker Desktop und WSL 2, macOS): das
Entwicklungs-Image einmal bauen und die Suite darin fahren. Der Arbeitsbaum
ist eingehängt, Code-Änderungen brauchen also keinen neuen Bau.
```
docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev .
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev            # volle Suite
docker run --rm -it -v "$PWD":/workspace rechner-pipeline-dev bash   # Shell
```

**Gemessene Plattformen.** Der Weg über den Container ist keine Theorie;
zwei Teammitglieder sind ihn gegangen und haben die Provenienz gemeldet,
nicht nur eine Suite-Zeile:

| Plattform | Gemessen |
|---|---|
| Windows 11, WSL 2 (Ubuntu), Docker Desktop | Suite grün 2026-09-14; Provenienz 2026-09-20 auf Commit `f518b6a`: 2212 passed, 3 skipped in 908 s |
| macOS 26.6.2, arm64 | derselbe Commit `f518b6a`: 2212 passed, 3 skipped in 595 s |

Zwei Ergebnisse zählen über „es lief" hinaus. Erstens meldeten beide
Plattformen auf demselben Commit DENSELBEN `quellcode_sha256`
(`c4bffa4f...`) — der Auscheck ist also über Plattformen byte-gleich, und
das LF-Pinning in `.gitattributes` leistet, was es behauptet. Zweitens trug
`systemstand` unter Windows echte Werte, nicht `unbekannt`: Git liest den
eingehängten Baum auch dort aus dem Container heraus, also tragen
Gate-Belege, die unter Windows entstehen, dieselbe Provenienz wie unter
Linux.

**Eine Umgebung melden.** Wer einen Lauf meldet — ein neuer Rechner, eine
Plattform, die noch nicht gemessen ist —, schickt die Provenienz des Codes,
den er gefahren hat, nicht nur die Suite-Zeile. Derselbe Container, ein
Kommando:
```
docker run --rm -v "$PWD":/workspace rechner-pipeline-dev \
  python -c "import json; from pathlib import Path; from rechner_pipeline.gates._provenienz import systemstand; print(json.dumps(systemstand(Path('/workspace')), indent=2))"
```
Es gibt vier Werte aus. `quellcode_sha256` deckt die Paketquellen (`.py`
und `.xml` unter `src/rechner_pipeline/`) und sonst nichts — ein Commit, der
nur Dokumente oder Tests ändert, lässt ihn unverändert, eine Code-Änderung
bewegt ihn. `dirty` muss `nein` lauten; sonst trägt der Auscheck
uncommittete Änderungen, und der Hash ist nicht vergleichbar. Lauten
`commit` oder `branch` `unbekannt`, kann Git den Baum aus dem Container
nicht lesen — unter Linux kann es das, anderswo ist das eine Meldung wert.

Der erwartete `quellcode_sha256` steht hier absichtlich nicht: Er gehört zu
einem Commit und würde mit der nächsten Code-Änderung altern. Wer um den
Lauf bittet, nennt den Wert zusammen mit dem Commit.

Wer VS Code nutzt, öffnet das Repository mit der Erweiterung Dev
Containers; die Definition unter `.devcontainer/` baut dasselbe Image. Der
Auscheck gehört auf ein Linux-Dateisystem (das WSL-2-Home, nicht `/mnt/c`):
Die Suite prüft Dateirechte und umask, die ein NTFS-Mount nicht trägt.
Zeilenenden sind über `.gitattributes` auf LF gepinnt; Lieferungen und
Fixtures sind davon ausgenommen, weil ihre Bytes gehasht werden.

Das ist der eine dokumentierte Installationsweg, derselbe wie in der CI.
Die Pin-Dateien tragen die direkten Abhängigkeiten (`pyproject.toml`:
`openpyxl`, `oletools`, `pandas`, `pyarrow`, `matplotlib`, `pydantic`,
`pypdf`; für die Entwicklung `pytest`, `hypothesis`, `pytest-xdist`) UND
ihre vollständige transitive Hülle; `tests/test_abhaengigkeiten.py` hält
diese Hülle geschlossen. Eine Installation nur mit `pip install -e ".[dev]"`
pinnt die direkten Abhängigkeiten und lässt pip alles Transitive frisch
auflösen — mit `filterwarnings = ["error"]` färbt dann eine neue Warnung in
einer Fremdbibliothek die Suite rot, ohne dass sich hier etwas geändert
hat. Dieser Weg ist deshalb nicht dokumentiert. Neun rein transitive Pakete
(`annotated-types`, `contourpy`, `cycler`, `fonttools`, `kiwisolver`,
`pillow`, `pydantic-core`, `typing-extensions`, `typing-inspection`) löst
pip weiterhin selbst auf — die Hülle ist dicht, nicht hermetisch.

**Die Suite** läuft parallel (ADR-019), eine Testdatei je Arbeiter. Ohne
`-n` läuft sie seriell und braucht rund doppelt so lang.
```
.venv/bin/python -m pytest -n 12 --dist loadfile
```

**Zusatzwerkzeuge.** Zwei Nebenaufgaben brauchen Werkzeuge, die die
Pipeline selbst nicht braucht: die Vorzeigeseite rendern und das Ergebnis
ansehen. Sie werden bei Bedarf installiert und stehen nicht in
`requirements*.txt`; die Kommandos stehen in `werkzeuge/README.md`. Es
lohnt sich: Ohne Renderer saßen zwei Layoutfehler im Stylesheet, die kein
Test sehen kann — eine `font:`-Kurzform, die der Browser verwirft, und ein
SVG, das seine Beschriftung mit sich hochskalierte.

## 3. Ausführen

**Die Laufzeit mit einem Aufruf aufstellen.** Aus dem Stand des
Repositorys und einem festgehaltenen Fall entsteht, ohne Agenten, eine
Laufzeit mit übernommenem Bestand:
```
deploy/welt/laufzeit_aufstellen.sh ~/plv-welt pakete/baldrian-klv-tg2015-fall3
```
Das rechnet rund 45 Minuten. Mit `--bis <haltepunkt>` endet der Lauf an
einer Stelle des Falls, an der man selbst liest und zeichnet. Einzelheiten
in `deploy/welt/README.md`, zu den Paketen in `pakete/README.md`.

**Einen Fall anlegen und seine Quellen registrieren.** Die Registrierung
ist der EINZIGE Weg in einen Fall — nie Dateien von Hand nach `eingang/`
kopieren. Das Kommando nimmt die Lieferung, wo immer sie gelandet ist,
kopiert sie nach `eingang/` (mit `--als` unter anderem Namen), hält SHA-256,
Herkunft und Größe im Register `eingang.json` fest und setzt die Kopie auf
nur lesbar. Jede spätere Aussage im Fall führt auf diese Prüfsummen zurück
— die Kette der Herkunft beginnt hier:
```
python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 --scope tarif
python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
    --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm
python -m rechner_pipeline.fall status --fall faelle/klv-tg2012
```
`status` (und jeder Lauf der Pipeline) hält das Register in beide
Richtungen gegen das Dateisystem: Eine registrierte Datei, die fehlt oder
deren Inhalt von der Prüfsumme abweicht, ist ein harter Fehler, ebenso jede
von Hand kopierte Datei ohne Registereintrag. Dieselben Bytes noch einmal
zu registrieren meldet `bereits_registriert`; eine verlorene Kopie wird aus
der Quelle wiederhergestellt, ohne das Register zu berühren; derselbe Name
mit anderem Inhalt ist ein harter Konflikt, der beide Prüfsummen zeigt —
es gibt kein stilles Überschreiben. Ersetzt eine Lieferung wirklich eine
frühere, wird ein neuer Fall angelegt (oder der alte unter
`faelle/archiv/` abgelegt). Liegt der Arbeitsbereich schon, hält `anlegen`
mit einem harten Fehler an, statt hineinzuschreiben: `eingang/` ist nicht
regenerierbar (ADR-002).

Parallele Aufrufe von `fall registrieren` auf demselben Fall werden über
eine Dateisperre des Falls hintereinander ausgeführt. `eingang.json` wird
erst nach dem vollständigen Schreiben und Synchronisieren einer temporären
Datei atomar ersetzt; so verliert kein Aufruf die Quellen eines anderen,
und Leser sehen nie ein halb geschriebenes Register.

**Einen Migrationsfall führen.** Seit ADR-025 und ADR-026 braucht ein Fall
eine Welt: eine Linie mit den Erstabnahmen des Zielsystems, Schlüssel der
Rollen und den gezeichneten Auftrag des Vorstands. Die Routinen unter
`deploy/welt/` stellen das auf und starten den Fall der Vorführung, die
Übernahme des Bestands KLV TG2015 der Baldrian Leben auf der Lieferung
`lieferungen/baldrian-2/`:
```
deploy/welt/welt_aufstellen.sh <welt>
deploy/welt/fall_starten.sh <welt> anlegen deploy/welt/fall-baldrian-klv-tg2015.conf
deploy/welt/fall_starten.sh <welt> vorlage
deploy/welt/fall_zeichnen.sh <welt> A-M6 angenommen "<begruendung>"
```
Danach führen die Agenten den Fall, über ihre Skills
(`migrationsfall-durchfuehren` orchestriert; Rollenkatalog in
`docs/architektur/skill-architektur.md`): Vorverdichtung und Extraktion je
Quelle, Zusammenführung zur A-Box, Diskrepanzen an das menschliche Gate
A-Q1, Spez, Abnahme des Zielsystems, Transformation und Übernahme des
Bestands, die drei aktuariellen Tests, die Migrationssuite mit dem
HTML-Abnahmebericht für A-M4 und der Zugang in die Ablage. Die Lieferungen
dürfen absichtliche Fehler und Eigenheiten des Quellsystems enthalten — sie
zu finden IST die Vorführung.

Zwei Dinge dazu:

* `main` trägt den Stand **nach** dem dritten Fall: Der Kern kennt den
  übernommenen Tarif schon. Wer die Übernahme mit allem durchspielen will,
  was sie am Zielsystem verändert, startet auf dem Stand davor (Tag
  `fall3-vor`).
* Eine Sitzung, die diesen Fall live führt, liest nicht in `pakete/`: Dort
  liegt seine Auflösung.

Die ältere Lieferung `lieferungen/baldrian/` gehört zum ersten Durchgang
derselben Übernahme (`docs/faelle/README.md`). Sie eignet sich zum Üben von
Registrieren und Vorverdichten:
```
python -m rechner_pipeline.fall anlegen --fall faelle/baldrian-uebernahme --scope bestand
for f in lieferungen/baldrian/*.xlsm lieferungen/baldrian/Mitteilung_143_KLV_TG2015.docx \
         lieferungen/baldrian/*.csv; do
  python -m rechner_pipeline.fall registrieren --fall faelle/baldrian-uebernahme --datei "$f"
done
python -m rechner_pipeline.fall status --fall faelle/baldrian-uebernahme
```
Die Schleife nimmt eine Datei bewusst NICHT mit:
`Aktuarielle_Notiz_Beitragsabsetzung.docx`. Die Tarifmeldung beschreibt
nicht, wie eine Beitragsherabsetzung gerechnet wird, und die Lieferung ist
dort absichtlich unvollständig. Die Notiz schickt die abgebende
Gesellschaft, NACHDEM die Lücke aufgefallen ist und jemand gefragt hat —
erst dann wird sie registriert.

**Eine Quelle vorverdichten (Gate P-Q1):**
```
python -m rechner_pipeline.gates.extract --repo-root . \
    --input faelle/klv-tg2012/eingang/Tarifrechner_KLV_TG2012.xlsm \
    --out-dir faelle/klv-tg2012/abgeleitet/vorverdichtung/xlsm-TG2012 --adapter excel
```
Die Gates der Ontologie folgen auf einem frischen Fall nicht unmittelbar:
P-Q3 (`gates.abox_validate`) prüft eine A-Box, P-K1
(`gates.generation_golden`) eine Tarif-Spez — beides gibt es noch nicht.
Die A-Box entsteht aus der Extraktion der Agenten und der deterministischen
Zusammenführung (`gates.abox_merge`), die Spez aus der abgenommenen A-Box.
P-Q3 oder P-K1 auf einem nackten Fall enden **planmäßig** mit Exit 2: kein
stiller Default, die Meldung nennt, was fehlt.
```
python -m rechner_pipeline.gates.abox_validate --fall faelle/mein-fall --repo-root .   # P-Q3
python -m rechner_pipeline.quellen.tafel_import --fall faelle/mein-fall --generation klv/tgX
python -m rechner_pipeline.gates.generation_golden --fall faelle/mein-fall \
    --generation klv/tgX --repo-root .                                                 # P-K1
```

**Wo der deterministische Durchgang endet.** `anlegen`, `registrieren`,
`status` und die Vorverdichtung P-Q1 sind reines Python: Sie laufen für
jeden, der das Repository geklont hat, ohne Key und ohne Agenten. Was
danach kommt, nicht. Die Extraktion je Quelle, das Lesen der Tarifmeldung
und der Vorschlag der Übersetzung für den Bestandsabzug sind Schritte der
**Agenten** (das ist der Sinn der Architektur — das Modell schlägt vor,
deterministischer Code entscheidet), und die Abnahmen sind menschliche
Entscheidungen, keine Kommandos. Ein Durchgang ohne Agenten-CLI endet also
hier, mit einem Exit ungleich null, der der Vertrag ist und keine kaputte
Installation. Zum Weitermachen braucht es Claude Code oder Codex im
Wurzelverzeichnis und die Skills unter `.claude/skills/` bzw.
`.agents/skills/` — oder das Nachfahren eines festgehaltenen Falls (oben).

**Der Fallauftrag und die menschlichen Gates.** Wer zeichnet, steht in der
**Zeichnungsordnung** (ADR-018): Rollen heißen `mensch/<funktion>` oder
`agent/<name>`, jede trägt eine Schlüsselklasse (`mensch`, `simulation`,
`agent`) und die Gates, die sie zeichnen darf. Die Rolle wird aus dem
Schlüssel BESTIMMT, nicht behauptet, und wandert samt Klasse mitsigniert in
den Snapshot. Agentenrollen legen vor und zeichnen nie; sie können ein
menschliches Gate nur **ablehnen**. In der Vorführung tragen die
menschlichen Rollen die Schlüsselklasse `simulation`, und jeder Beleg sagt
das.
```
# der Fallauftrag (ADR-026): Vorlage, ansehen, der Vorstand zeichnet A-M6 —
# vor jedem anderen Abnahmepunkt
python -m rechner_pipeline.gates.fall_belegen auftrag --fall faelle/mein-fall \
    --linie linie --zeichnungsordnung /sicher/zeichnungsordnung.json \
    --programmleitung-schluessel /sicher/programmleitung.key \
    --programmleitung-klasse mensch --auftrag "..."
python -m rechner_pipeline.gates.gate_entscheid --fall faelle/mein-fall --gate A-M6 \
    --entscheid angenommen --entscheider ... --begruendung ... --linie linie \
    --zeichnungsordnung /sicher/zeichnungsordnung.json \
    --freigabe-schluessel /sicher/vorstand.key

# eine Diskrepanz entscheiden, dann A-Q1 zeichnen
python -m rechner_pipeline.ontologie.entscheide --fall ... --diskrepanz ... \
    --wert ... --entscheider ... --begruendung ... \
    --zeichnungsordnung /sicher/zeichnungsordnung.json \
    --freigabe-schluessel /sicher/verantwortlicher-aktuar.key
python -m rechner_pipeline.gates.gate_entscheid --fall ... --gate A-Q1 \
    --entscheid angenommen --entscheider ... --begruendung ... --linie linie \
    --zeichnungsordnung /sicher/zeichnungsordnung.json \
    --freigabe-schluessel /sicher/vorstand.key \
    --freigabe-schluessel /sicher/verantwortlicher-aktuar.key
```
Jeder Entscheid nennt die Linie (ADR-025). Der Ring trägt den Schlüssel
des Vorstands, der den Fallauftrag und die Glieder der Linie prüft
(ADR-026, ADR-025); `--repo-root` ist der Baum des Pakets, das rechnet. Ein
Abbruch läuft über `fall_belegen abbruch` und A-M5 (Bedienfolgen in
`docs/architektur/adr-026-lebenslauf-eines-falls.md`).

**Tarifregeln eines übernommenen Tarifs.** Sie stehen einmal, belegt, in
der A-Box und daraus in der Spez der Generation (ADR-024, Nachtrag): das
Tarifwerk (`scheiben_mit_gamma1`, `stoab_je_baustein`, `red_verfahren`,
`tku_umfang`) und das Verfahren der Quelle (`red_verfahren` als Lesart der
Lieferung, `erhoehungssatz`, `dk_stichtag`, `formfunktion`, `fenster`). Im
Bestands-Scope verlangt P-Q3 sie, und die fünf Kommandos der
Bestandsstrecke (`gates.bestand_uebernehmen`, `verankerung_belegen`,
`aktuartest_lauf`, `migrationssuite_lauf`, `fuehrungsprobe`) lesen sie aus
der Spez — ohne Schalter und ohne Vorgabe. Ein Dynamiksatz, den der Tarif
nicht kennt, steht in der Spez als ausdrückliche Feststellung
`"nicht_belegt"`; fehlt der Eintrag, ist er nie erhoben, und jedes Kommando
verweigert wie P-Q3.

**Auskünfte zu Herabsetzungsanteilen** (`POLNR;GEVO;DATUM;ANTEIL`,
optional `BEZUG` als Quellenangabe) kommen als registrierte Datei in den
Fall und werden in allen fünf Kommandos der Bestandsstrecke mit
`--red-anteile-datei <Dateiname>` genannt: erst `fall registrieren`, dann
der Schalter. Ein Anteil je Police am Aufruf wird nicht angenommen — er
wäre für die Zeichnung nicht bindbar. Die Belege nennen die Datei mit ihrer
Prüfsumme.

**Herabsetzung und Teilkündigung** sind zwei Geschäftsvorfälle (ADR-023;
Tarifplan KLV, Abschnitte 7.1 bis 7.3): Die Herabsetzung (`RED`) senkt den
Beitrag und gibt es nur, solange er gezahlt wird; die Teilkündigung (`TKU`)
zahlt einen Summenanteil aus und ist auch nach dem Beitragsende und nach
der Beitragsfreistellung möglich. Ein Vertrag, dessen Anfangszustand nicht
ableitbar ist, wird nicht still als Grundvertrag übernommen: Die Kommandos
verweigern und nennen `--red-anteile-datei` als Ausweg.

**Tafelimport.** Er nimmt nur eine vollständige Exportkette: Das
`export_manifest.json` muss die registrierte XLSM und die konkrete
`Tafeln.csv` mit ihren vollständigen SHA-256-Werten binden. Fehlende
Manifeste, alte Exporte oder nachträglich veränderte Blatt-CSVs blockieren
schon den `--dry-run`; dann die registrierte XLSM erneut mit P-Q1
extrahieren. P-Q1 plant die Dateinamen aller Blatt- und Folgeartefakte vor
dem ersten Blattexport kollisionsfrei; `sheet_artifacts` im Exportmanifest
bindet jeden Originalblattnamen an seinen tatsächlichen Dateinamen. Alle
Altersvektoren müssen genau die ganzzahligen Alter 0 bis 123 tragen, jeder
qx-Wert muss endlich sein und in `[0,1]` liegen — erzwungen beim Import und
erneut beim Laden des Kern-XML.

**Einen Bestand erzeugen und berichten.** Ein Bestand entsteht aus seinem
Zugangsstrom: Der Lauf beginnt leer, und jeder Vertrag tritt mit einem
datierten `ZUG`-Ereignis ein (ADR-020). `--neuzugang-ab` nennt den Tag, an
dem der Strom beginnt; `--bis` ist der Horizont der Simulation. Der
`--stichtag` des Berichts markiert nur die Grenze zwischen Historie und
Projektion; ohne Angabe gilt `meta.referenzstichtag` aus der Config. Wer
`--bis` auf „heute" setzt, schneidet die Projektion still ab.
```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config configs/bestand_gesamt.toml --neuzugang-ab 1994-07-01 \
    --bis 2046-01-01 --out-dir runs/bestand
python -m rechner_pipeline.bestand.cli_report --portfolio runs/bestand/bestand_gesamt.parquet \
    --historie runs/bestand/historie.parquet --ledger runs/bestand/ledger.parquet \
    --scheiben runs/bestand/scheiben.parquet --config configs/bestand_gesamt.toml \
    --bis 2046-01-01 --stichtag 2026-01-01 --out runs/berichte/bestandsbericht.html
```
Der Lauf schreibt auch `runs/bestand/laufmanifest.json`, seinen
Lieferschein: den simulierten Horizont, die Prüfsumme der Config und eine
SHA-256 je Ausgabe. `cli_abschluss` weist ein Laufverzeichnis ohne ihn ab,
und `--bis` muss dem Horizont gleichen, den das Manifest bezeugt. Ein Lauf,
der weder `--portfolio` noch `--uebernahme` noch `--neuzugang-ab` bekommt,
hat nichts zu tragen und sagt das (Exit 2), statt einen Bestand zu
erfinden.

Für ihr eigenes Geschäft nutzt die Vorführung dieses Kommando nicht: Die
Pfefferminzia wird Tag für Tag geführt (`betrieb.tageslauf`, derselbe
Zugangsstrom in täglicher Auflösung, siehe
`docs/simulation/tagesbetrieb.md`). `cli_fortschreibung` ist die
Prüfstrecke eines Migrationsfalls und der schnellste Weg zu einem
synthetischen Bestand mit voller Historie.

**Im Code navigieren** (Fundstellen sind abgeleitet, nicht gesucht —
ADR-005):
```
python -m rechner_pipeline.ontologie.code_index --tests tests   # Knoten <-> Modul und Test
python -m rechner_pipeline.ontologie.code_karte                 # Schichtregeln
git diff --name-only | python -m rechner_pipeline.ontologie.impact
python -m rechner_pipeline.ontologie.landkarte --out runs/landkarte.html
```

## 4. Die Gates

Jedes Gate ist ein Kommando, schreibt ein JSON auf stdout und ein Ledger
`<kommando>.gate.json` nach `--diagnostics-dir`. Ein Exit ungleich null
**blockiert** und wird nie zur Warnung abgeschwächt.

| Gate | Kommando | Belegt |
|---|---|---|
| P-Q1 | `gates.extract` | die deterministische Vorverdichtung einer Quelle |
| P-Q2 | `gates.abox_merge` | die Zusammenführung der Fragmente zur A-Box, mit einem Ketten-Ledger |
| P-Q3 | `gates.abox_validate` | die A-Box gegen die T-Box: Abdeckung, Wertebereiche, Rück-Check der Formeln |
| P-K1 | `gates.generation_golden` | den parametrierten Kern gegen die Erwartungswerte der Lieferung |
| P-B1 | `gates.bestand_validate` | den Vertrag des Bestands und die Bewegungs-Identitäten |
| P9 | `gates.gate_entscheid` | die gezeichneten Snapshots der menschlichen Gates |
| Vorlagen A-M1 bis A-M3 | `gates.aktuartest` | das Ergebnis des aktuariellen Tests, nachgerechnet, als Entscheidungsvorlage |
| Vorlage A-M4 | `gates.abnahmebericht` | den Abnahmebericht mit seinen Pflichtartefakten |

Was jedes Gate im Einzelnen hält und warum es seine Version trägt, steht in
`docs/architektur/gate-vertrag-und-versionen.md`. Wer welches menschliche
Gate zeichnet und worüber, steht in ADR-012 und ADR-018; den Ablauf zeigt
`docs/architektur/ablauf-eines-falls.md`.

Eine Annahme braucht `--freigabe-schluessel`. Die Datei verwahrt der Mensch
außerhalb des Falls und außerhalb des Agentenzugriffs; sie muss mindestens
32 kryptografisch zufällige Byte lang sein und unter POSIX die Rechte 0600
und genau einen Hardlink haben. Bei einer Schlüsselrotation wird die Option
wiederholt: alte Schlüssel zuerst, der aktive zuletzt. Weder Schlüsselbytes
noch Pfad werden gespeichert. P9 rechnet bei jedem Lesen Schema,
Inhalts-Hash, Dateinamen, Signatur sowie Existenz, Zyklen und eindeutige
Spitze der Vorgängerkette nach (ADR-008).

Für A-M4 trägt `fall.json` `scope.typ` (`tarif` oder `bestand`). Eine
fehlende Angabe wird nie aus Dateien erschlossen. Ein Tariffall braucht
keine Bestandsartefakte; ein Bestandsfall braucht ein grünes P-B1-Ledger,
eine vollständige Suite, eine bestandene Führungsprobe
(`gates.fuehrungsprobe`) und den HTML-Bericht, alle gebunden durch das
grüne Ledger des Abnahmeberichts. A-M4 hasht ihre Bytes neu, fährt die
Engines von P-B1 erneut, prüft Suite und Führungsprobe nach und rendert den
Bericht deterministisch neu für einen Bytevergleich, statt dem editierbaren
Ledger zu trauen (ADR-009).

## 5. Nicht verhandelbar

- **Deterministisch und SDK-frei** in `src/`: kein Netz, keine dynamische
  Ausführung, kein Subprozess; gleiche Eingabe -> gleiche Ausgabe; sortierte
  Serialisierung. Es gibt genau EINE Subprozess-Ausnahme, und ein Test
  begrenzt sie: Die gemeinsame Provenienz der Belege
  (`gates/_provenienz._git_lesen`) fährt nur LESENDE Git-Kommandos aus einer
  geschlossenen Liste — `rev-parse HEAD`, `rev-parse --abbrev-ref HEAD` und
  `status --porcelain` halten den Git-Stand fest, auf dem belegt oder
  entschieden wird; seit dem 2026-10-01 halten `rev-parse --verify`,
  `merge-base`, `diff --numstat`, `log`, `ls-tree`, `show` und ein auf Pfade
  begrenztes `status` die Änderungen am Kern seit dem letzten abgenommenen
  Kernstand fest (A-K2) und die Änderungen am Tarifwerk (A-T1,
  `gates.tarifwerk_belegen`). Alles nach dem Kommando ist Datum (Commits,
  Pfade) und darf nie mit einem Strich beginnen. Die Stelle rechnet und
  urteilt nichts. Ein reines Python-SHA-256 über die installierten
  Paketquellen unterscheidet verschiedene uncommittete Code-Stände. Ist Git
  nicht verfügbar, tragen seine Felder den benannten Wert `unbekannt`, nie
  einen stillen Default. Jeder weitere Subprozess-Import, jedes andere
  Kommando und jeder Prozessstart über `os` färbt
  `tests/test_fachspez_und_p9.py::test_subprozess_bleibt_auf_die_beweisprovenienz_beschraenkt`
  rot.
- **Fail fast, nie still:** kein stilles Überschreiben, kein stiller
  Default. Zweifel ist ein benannter Zustand
  (`nicht_belegt`/`mehrdeutig`/`widerspruechlich`) oder ein harter Fehler,
  dessen Meldung den Ausweg nennt.
- **Agenten entscheiden nie** Widersprüche zwischen Quellen. Vorläufige
  Auflösungen tragen `vorlaeufig=true` und blockieren jede menschliche
  Abnahme.
- **Knoten** (`Knoten: klv/tg2015`) im Docstring jedes Moduls und jedes
  Tests; dieselben Kennungen wie in der A-Box und im Gate P-K1.
  `code_index` bleibt ohne Drift, `code_karte` ohne Befund.
- **Abgenommene Gegenstände ändern sich nicht nebenbei.** Kern (das Paket
  `kern`, die eingefrorenen Referenzwerte, die Grundsatzdokumentation) und
  Tarifwerk (`docs/tarifplaene`, die Bestands-Configs) sind gezeichnet
  (A-K2, A-T1). Ein festgehaltener Fall ist nur auf einem Baum nachfahrbar,
  der sie unverändert trägt (`tests/test_pakete.py`, ADR-027).
- **Volle Suite vor jedem Commit**, parallel (Abschnitt 2). Das
  Impact-Werkzeug ist informativ — es verengt nie, was laufen muss. Die CI
  (`.github/workflows/tests.yml`) fährt die volle Suite bei jedem Push und
  jedem Pull Request. Der Pflichttest `tests/test_pk1_fixture_e2e.py` nutzt
  die versionierten, anonymisierten Daten unter
  `tests/fixtures/pk1_am4_minimal/` und fährt echte Extraktion,
  Formelprüfung und P-K1 auf einem frischen temporären Fall;
  `tests/test_pk1_am4_beweisvertrag.py` führt denselben Belegpfad bis A-M4.
  Fehlende oder im Hash abweichende Fixture-Eingaben sind ein harter
  Fehler, nie ein Skip. Lokale Fall-Arbeitsbereiche unter `faelle/` sind
  gitignoriert und keine Voraussetzung für eine grüne Suite.
- Direkte Abhängigkeiten exakt gepinnt (`pyproject.toml`), ihre transitive
  Hülle in `requirements*.txt` (Abschnitt 2); neue Abhängigkeiten nur per
  ADR. Den Push macht der Mensch.

## Laufdaten: was Wegwerf ist und was sich wehrt

`runs/` ist **Wegwerf**: Jeder darf dort löschen, nichts darin ist die
einzige Kopie von etwas Wichtigem. Was festgehalten werden soll, lebt an
zwei Orten mit eigenem Schutz:

* im **Fall** (`faelle/<fall>/` — `eingang/` und `entscheide/` sind
  unantastbar, `abgeleitet/` ist reproduzierbar), oder
* als **Abschluss** (`bestand.cli_abschluss`): Festgeschriebene Stände
  schreiben sich selbst schreibgeschützt (0444) — ein `rm` ohne `-f` fragt
  nach, ein Überschreiben scheitert. Gegen `rm -rf` schützt kein
  Dateirecht; deshalb die Verhaltensregel: vor jedem Aufräumen unter `runs/`
  prüfen, ob echte Laufdaten dort liegen — besser: Sie liegen dort gar
  nicht erst.

Anlass ist ein realer Verlust: Am 2026-06-05 hat ein aufräumendes
`rm -r runs` die Artefakte eines echten Laufs zerstört.
