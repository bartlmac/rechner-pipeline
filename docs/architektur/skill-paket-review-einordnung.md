# Skillpaket: Revieweinordnung und begrenzte Scopekorrektur

## Auftrag und Scope

Auftrag `PR-SKILL-DOC-FIX-02`, Modus Entwicklung, Dokumentationsvorbereitung
durch den allgemeinen Dokumentationsagenten. Die Nutzerentscheidung umfasst
die Umsetzung von Reviewpunkt 8 zum Aufgabenvertrag und die belegte
Einordnung zweier weiterer Punkte fuer die PR-Begruendung: historische
Kern-/T-Box-Rechte sowie lokal fehlende DCO-Regel und PR-Vorlage.

Dieses Dokument ist eine Revieweinordnung, keine neue Architekturentscheidung
und keine Gesamtfreigabe von ADR-032 oder des Skillpakets. Es bestaetigt
insbesondere keine historische Zustimmung zum A049-Vorschlag oder zum
Spezkonflikt-Uebertragungsweg. Als technische Folgearbeit hat die Hauptsitzung
auf Nutzerauftrag die vier Fehler des ersten Vollsuite-Laufs untersucht und
die aktive Bytecode-Provenienzpruefung korrigiert. Dieser Folgefix und seine
Nachweise sind unten erfasst. Die weiteren fachlichen Reviewforderungen
werden damit nicht umgesetzt. Rollenrechte, Kern, T-Box, menschliche Gates
und Dependency-Pins bleiben unveraendert.

## Uebernommener Reviewpunkt 8: Geltungsbereich des Aufgabenvertrags

Die Nutzerentscheidung zu Punkt 8 ist in `AGENTS.md`, Abschnitt
„Agent task and handoff contract (ADR-032)“, umgesetzt. Dort steht der
zentrale Geltungsbereich; ADR-032, Skillkatalog und Entwicklungsskill
verweisen konsistent darauf. Der Entwicklungsskill wird in beiden
Skillbaeumen mit identischem Text nachgezogen.

Der vollstaendige Aufgaben-/Rueckgabevertrag gilt fuer mandatierte Arbeit
der fuenf KI-Tool-Rollen und Fallarbeit. Die Betriebsrolle gehoert auch ohne
Migrationsfall zur Rollenarbeit. Entwicklung durch eine Fachrolle bleibt
Rollenarbeit. Eigenstaendige Entwicklung, allgemeine Exploration und reine
Dokumentationsarbeit ausserhalb solcher Rollen-/Fallaufgaben unterliegen
weiterhin den allgemeinen Repo-Regeln und dem jeweiligen Skill, aber nicht
obligatorisch dem vollstaendigen Rollen-/Fallvertrag. Daraus entstehen keine
erweiterten Quellen-, Gate- oder Mandatsrechte.

## Historische Baseline und Belege

Die Baseline ist `5880336de5587dcd325ec3b92a100198d17fcfe6`, der verifizierte
Parent des ersten Paketcommits `620571b`. Der urspruengliche PR-Stand ist
`1e401b049fe84264a2853e3beed833d02f7ba593`. Die folgenden Kurzrevisionen
bezeichnen genau diese Git-Staende, nicht einen spaeteren Arbeitsbaum.

Historische Quellen wurden als Git-Blobs gelesen. Der Vergleich
`5880336..1e401b0` zeigt keine Aenderung an ADR-018, ADR-007,
`CONTRIBUTING.md` oder `.github/`. `AGENTS.md` erhielt durch das Paket den
neuen Vertragsabschnitt; das unten zitierte Migrationsschreibverbot war
bereits in der Baseline enthalten. Ein vorhandenes getracktes spezielles
Reviewdokument wurde im Architekturverzeichnis nicht gefunden.

## Kern und T-Box: Vorher, Reviewforderung und offene Entscheidung

### Vorher: Entwurfsrechte, Migrationsgrenze und getrennte Abnahmen

Die Datierung der Belege ist zu unterscheiden: „Linie und Fall“ gehoert zum
Nachtrag vom 16.09.2026. Die ausdrueckliche Schreibregel steht im Nachtrag
vom 01.10.2026 „Der Stand des Falls ist abgenommen — A-K2 und A-O1“,
Unterabschnitt „Wer an Kern und T-Box schreibt“.

Quelle `5880336:docs/architektur/adr-018-rollenmodell-und-schluesselklassen.md`,
Nachtrag 2026-10-01, „Wer an Kern und T-Box schreibt“, exakte Zitate:

> In der Entwicklung des Werkzeugs darf
> ein Agent im Auftrag des Maintainers eine Erweiterung der T-Box oder eine
> Änderung des Kerns als Entwurf bauen.

> In einer laufenden Migration schreibt
> kein Agent an der T-Box:

> Für den Kern gilt
> dasselbe:

Die Baseline erlaubte damit Entwuerfe im Maintainerauftrag, enthielt aber
fuer laufende Migrationen die Schreibgrenze fuer beide Gegenstaende.
Quelle `5880336:AGENTS.md`, „Codex Entry Points“, exaktes Zitat:

> During a running migration no agent writes to the T-Box or the kernel:

Quelle `5880336:docs/architektur/adr-018-rollenmodell-und-schluesselklassen.md`,
Nachtrag 2026-09-16 „Die Betriebsrolle, und zwei Sorten Rollen“,
„Linie und Fall“, exakte Zitate:

> `A-O1.tbox-aenderung` (vorher `A-K1`) nimmt die Änderung der T-Box ab.
> Es zeichnet `mensch/architektur`,

> `A-K2.kernaenderung`, gezeichnet von `mensch/rechenkern`, nimmt Code und
> Dokumentation des Rechenkerns ab.

Die Abnahmen fuer Kern und T-Box waren somit bereits vorher getrennt.

Quelle `5880336:docs/architektur/adr-007-parallele-migrationen-ein-kern.md`,
„Entscheidung“, Regel 3, exaktes Zitat:

> Ein
> Inkrement darf nur landen, wenn die Gesamt-Suite grün ist,
> einschließlich der Referenzwert- und P-K1-Läufe aller anderen offenen und
> abgeschlossenen Fälle.

Dieselbe Quelle, „Konsequenzen“, exaktes Zitat:

> Der Tafel-Import bleibt die einzige zulässige dauerhafte
> Kern-Berührung vor der Abnahme (P-K1 muss rechnen können);

Zwischen Inkrementverfahren, Tafelimport und der Migrationsschreibgrenze
bestand bereits vor dem Skillpaket eine erklaerungsbeduerftige Spannung.
Dieser historische Befund widerlegt die Reviewforderung nicht.

### Reviewforderung

Das Review verlangt nun exklusives Schreiben an Kern und T-Box durch den
Rechenkern-Agenten im Entwicklermandat, auch waehrend laufender Migration:
temporaer fuer Pruefrechnungen oder dauerhaft als Vorschlag. Dauerhafte
Aenderungen sollen ADR-007 Regel 3 und `integriere-migrationsinkrement`
folgen; fuer den geaenderten Kernstand verlangt das Review menschliches
A-K2, ebenso beim scharfen Tafelimport.

Diese Forderung aendert beziehungsweise klaert die vorbestehenden Regeln.
Sie ist durch die Scopekorrektur zu Punkt 8 nicht umgesetzt oder freigegeben.

### Offen

Die kuenftige Schreibregel und ihr Verhaeltnis zur bestehenden
Migrationsgrenze beduerfen einer gesonderten Entscheidung. Fuer T-Box-
Aenderungen bleibt insbesondere zu klaeren, wie exklusives Implementieren
durch den Rechenkern-Agenten mit der bestehenden A-O1-Vorlage und Abnahme
durch die Architekturrolle zusammenspielt. A-K2 wird hier nicht als Ersatz
fuer A-O1 eingefuehrt; es wird keine neue A-O1-Entscheidung behauptet.

## DCO und PR-Vorlage: Vorher, Reviewforderung und offene Nachweise

### Vorher: begrenzter lokaler Befund

In `5880336:CONTRIBUTING.md` und `1e401b0:CONTRIBUTING.md`, jeweils im
vollstaendigen Dokument, wurde keine DCO-/Signoff-Regel gefunden. Die Datei
wurde durch das Skillpaket nicht geaendert. Beide Fassungen verlangen im
Abschnitt „Stil“ weiterhin, exakt zitiert:

> Alles muss reproduzierbar von Anfang bis Ende laufen: volle Suite vor
> jedem Commit,

Die Git-Baumlisten `5880336:.github/` und `1e401b0:.github/` enthalten jeweils
ausschliesslich:

- `.github/workflows/docs-image.yml`
- `.github/workflows/plv-image.yml`
- `.github/workflows/tests.yml`

Eine lokale PR-Vorlage ist in diesen beiden `.github/`-Baeumen nicht
vorhanden; `.github/` wurde durch das Paket nicht geaendert. Das ist ein
auf diese Repository-Staende begrenzter Befund. Eine zentrale GitHub-
Vorlage oder externe Beitragsregel ist damit nicht ausgeschlossen.
Im vorherigen Auftrag `PR-SKILL-REVIEW-DOC-01` scheiterte die lesende
PR-Abfrage mit HTTP 403. Dies ist ein damals berichteter Abrufbefund;
in diesem Auftrag wurde kein neuer GitHub-Abruf ausgefuehrt.

### Reviewforderung und offen

Die Reviewforderung nach DCO und vorlagengerechter PR-Antwort bleibt
bestehen. Das Fehlen einer lokalen Regel oder Vorlage ist weder eine
Ablehnung der DCO-Pflicht noch eine Rechtfertigung fehlender Signoffs oder
ein Entfall der Vorlagenanforderung.

Die Trailerabfrage fuer die drei Commits des urspruenglichen PR-Stands
ergab jeweils keinen `Signed-off-by`:

- `620571b` — Aufgabenvertraege und phasenweise Fachverfahren
- `a4f2ec0` — Skillkatalog und Werkzeuganzeige
- `1e401b0` — Hostadapterzuordnung im README

Offen sind die massgebliche DCO-Regel, die tatsaechliche PR-Vorlage und das
von der beitragenden Person und dem Maintainer festzulegende Vorgehen fuer
diese drei Commits. Dieses Dokument erzeugt keinen Signoff und autorisiert
keine Historyaenderung.

## Kopierbarer kurzer Reviewantworttext

> Punkt 8 zum Aufgabenvertrag ist uebernommen: Der vollstaendige Vertrag
> gilt fuer mandatierte Arbeit der fuenf KI-Tool-Rollen und Fallarbeit,
> einschliesslich Betriebsrollenarbeit ohne Migrationsfall und Entwicklung
> durch Fachrollen. Eigenstaendige Entwicklung, Exploration und reine Doku
> ausserhalb solcher Aufgaben folgen den allgemeinen Repo-Regeln und dem
> jeweiligen Skill. Die zentralen und davon abhaengigen Texte sind angepasst.
>
> Die Kern-/T-Box-Frage ist historisch eingeordnet: Entwuerfe im
> Maintainerauftrag, die Migrationsschreibgrenze und die Trennung A-K2/A-O1
> standen schon vor dem Paket in ADR-018; auch ADR-007 mit Inkrementen und
> Tafelimportgrenze ist unveraendert. Die vorbestehende Spannung widerlegt
> das Review nicht. Die geforderte neue Schreibregel und ihr Verhaeltnis
> zu A-O1 bleiben gesondert zu entscheiden.
>
> DCO-Regel und PR-Vorlage fehlen lokal sowohl in der Baseline als auch
> im urspruenglichen PR-Stand und wurden durch das Paket nicht geaendert.
> Externe Vorgaben sind damit nicht ausgeschlossen. Die drei Commits ohne
> Signoff und der Abgleich mit der massgeblichen Vorlage bleiben offen.
>
> Die technische Folgepruefung fand ein echtes Produktproblem bei aktivem
> externem Bytecode: Eine verdoppelte qx-Rechnung wurde vor dem Fix angenommen.
> Die aktive Cachepruefung ist korrigiert; rote Regressionen, gezielter
> Fixnachweis und eine Mutation in einer Wegwerf-Testkopie sind dokumentiert.
> Im neu gebauten Linux-Referenzimage ergab die volle Suite 5646 passed,
> 6 skipped in 814.23s (0:13:34), PYTEST_EXIT_CODE=0; der Baumwächter meldete
> einen unveraenderten Baum. Die sechs Skips sind unveraendert. Der Lauf
> belegt den Code-Stand vor der abschliessenden reinen Nachweiserfassung,
> nicht saemtliche danach aktualisierten Dokumentbytes. Begrenzte lesende
> Reviews ergaben PASS; eine volle adversariale Blindrunde, Gesamtfreigabe,
> DCO-Klaerung oder Hostnachweise werden damit nicht behauptet.

## Ausfuehrungsnachweis der Hauptsitzung

Die folgenden Ausfuehrungsnachweise wurden von der Hauptsitzung gemeldet;
diese reine Dokumentationsaktualisierung startet keine Tests oder Reviews.

### Fruehere gezielte Dokumentpruefung

Die Hauptsitzung meldete zunaechst folgenden partiellen Testlauf.
Umgebung: Linux-Referenzimage `rechner-pipeline-dev`, Image-ID
`sha256:613a1707cd4f0fdd1d0a6d9580b662b470143c2d978331ddb5a6cafa50a30051`,
CPython 3.11 laut Image. Auf dem Linux-Containerdateisystem unter
`/tmp/rp-review` lag eine vollstaendige Testkopie der getrackten
Arbeitsbaumdateien samt neuer Revieweinordnung und `.git`. Die Quelle war
nur lesend eingebunden; die Hauptsitzung hielt den Arbeitsbaum waehrend
der Pruefung unveraendert. Der Lauf fand extern im Wegwerfcontainer statt.

Tatsaechlich ausgefuehrtes Kommando:

```sh
python -m pytest -q -p no:cacheprovider tests/test_agent_workflow_docs.py tests/test_dokumentierte_kommandos.py tests/test_klarnamen.py
```

Exakte Ergebniszeilen und Exit-Code-Meldung:

```text
Baumwaechter: 18 Lesungen im Abstand von 0.2 s, der Baum blieb wie beim Sitzungsbeginn
141 passed in 6.74s
PYTEST_EXIT_CODE=0
```

Ein erster Vorlauf ohne `.git` ergab 140 bestandene Tests und einen Fehler,
weil `git ls-files` die benoetigte Repositoryinformation fehlte. Fuer den
finalen Lauf wurde die Testkopie um `.git` ergaenzt; dieser Lauf ist der
oben ausgewiesene Nachweis.

Zusaetzlich meldet die Hauptsitzung einen unabhaengigen READ-ONLY-Review
des begrenzten Aenderungsscopes: PASS ohne Funde. Das ist weder ein
Gesamtreview des Skillpakets noch ein Host-, Skilltrigger- oder
Delegationsnachweis. Testlauf und Review wurden von der Hauptsitzung
ausgefuehrt beziehungsweise eingeholt. Dieser partielle Nachweis wird durch
den nachfolgenden Vollsuite-Nachweis zeitlich ergaenzt.

### Erster Vollsuite-Lauf und technischer Folgefix

Der erste volle Lauf durch den allgemeinen Agenten unter dem alten Image
ergab `4 failed, 5633 passed, 6 skipped in 661.02s`, Exit-Code 1.
Das alte Image mit ID
`sha256:613a1707cd4f0fdd1d0a6d9580b662b470143c2d978331ddb5a6cafa50a30051`
enthielt veraltete Abhaengigkeiten: pypdf 6.16.2 und Pillow 12.3.0.
Die Untersuchung war jedoch nicht auf Umgebungsfehler beschraenkt:
Ein realer aktiver externer Cache mit verdoppeltem qx wurde angenommen.
Das war ein Produktproblem der Bytecode-Provenienzpruefung.

Die Hauptsitzung korrigierte
`src/rechner_pipeline/gates/_provenienz.py`: Fuer jede Quelldatei wird der
aktive Cachepfad mit `cache_from_source` bestimmt, statt sich auf lokal
per `rglob` gefundene Caches zu beschraenken. Dabei wird der aktive
Optimierungsmodus aus `sys.flags.optimize` beruecksichtigt. Die Pruefung
von Bytecode ohne Quelldatei (sourceless pyc) bleibt erhalten. Die lokale
CLI-Diagnose nennt den absoluten Cachepfad und den Ausweg auch fuer externe
Caches. Die Tests decken beide Cacheorte (`sys.pycache_prefix=None`
und externes Praefix), `-O`/`-OO` sowie nichtaktive Caches ab. Kern, T-Box und Pins
wurden fuer diesen Folgefix nicht geaendert.

Vor dem Fix ergaben die roten Regressionen
`6 failed, 2 passed in 4.66s`. Nach dem Fix ergab die gezielte Pruefung von
`tests/test_bytecode_lebendes_paket.py`,
`tests/test_repo_root_lebendes_paket.py` und
`tests/test_abhaengigkeiten.py` die Ausgabe `31 passed in 9.48s`, Exit-Code 0.
`code_index` meldete `drift: []`; `code_karte` war erfolgreich, jeweils
Exit-Code 0. Der Reviewer `gpt-6-1-reviewer` meldete fuer den begrenzten
Scope PASS. Dies war kein blinder Angriff.

### Neu gebautes Referenzimage

Die Hauptsitzung baute das Image aus dem bestehenden Dockerfile neu:

```sh
docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev:pr-skill-fix .
```

Image-ID:
`sha256:4d5aebcc06270ba1c8c566092eeca8d93594d74f224d183483182b8ab21ebb39`.
Die tatsaechliche Pythonversion war 3.11.18. Der Test der gepinnten
Abhaengigkeiten bestand; pypdf 6.21.4 und Pillow 13.0.0 blieben gepinnt.
Die Pins wurden nicht gelockert.

### Volle Suite nach dem Folgefix

Der Lauf fand unter Linux im neuen Referenzimage auf dem Containerdateisystem
unter `/tmp/rp-review` statt. Die Testkopie enthielt `.git`, die getrackten
Arbeitsbaumdateien und die neue Reviewdatei. Die Quelle war nur lesend
eingebunden; der Lauf wurde mit `flock /tmp/suite.lock` serialisiert.

Tatsaechlich ausgefuehrtes pytest-Kommando:

```sh
python -m pytest -n 12 --dist loadfile -p no:cacheprovider -ra
```

Exakte Ergebniszeilen und Exit-Code-Meldung:

```text
Baumwaechter: 3842 Lesungen im Abstand von 0.2 s, der Baum blieb wie beim Sitzungsbeginn
================= 5646 passed, 6 skipped in 814.23s (0:13:34) ==================
PYTEST_EXIT_CODE=0
```

Die sechs Skips entsprechen dem vorherigen Stand: einer fuer markdown,
zwei fuer python3markdown, einer fuer die Docker-Dokuengine und zwei fuer
simulation/baldrian. Durch den Fix kam kein Skip hinzu. Die Suite umfasste
5652 Items statt zuvor 5643; die Differenz stammt aus Testparametrisierung
und neuen Tests.

Dieser Vollsuite-Lauf belegt den Code-Stand vor der abschliessenden reinen
Nachweiserfassung. Diese Dokumentdatei wurde danach aktualisiert. Es wird
deshalb keine Vollsuite auf saemtlichen finalen Dokumentbytes behauptet.

### Mutation in der Wegwerf-Testkopie

Die Hauptsitzung setzte ausschliesslich in einer Wegwerf-Testkopie die
Produktdatei auf HEAD vor dem Fix zurueck und liess die aktuellen externen
Cachetests dagegen laufen. Ergebnis: `5 failed, 1 passed, 6 deselected in
4.67s`, `MUTATION_PYTEST_EXIT_CODE=1`. Die E2E-Probe nahm erneut die
verdoppelte qx-Rechnung an. Die Quelle wurde dabei nie veraendert.
Das ist ein gezielter Mutationsnachweis; eine vollstaendige adversariale
Blindrunde oder abschliessende Schliessung wird nicht behauptet.

## Bewusst nicht erledigte Nachweise und weiterer Halt

Die zuvor offene volle Suite ist fuer den oben abgegrenzten Code-Stand
nachgewiesen. Vor einem spaeteren Commit bleibt die Precommit-Bedingung
fuer den dann zu committen Stand zu beachten; die nachtraegliche reine
Dokumentaktualisierung ist nicht Teil des ausgewiesenen Vollsuite-Laufs.
Host-Rollensitzungen, Skilltrigger- und Delegationsproben sowie eine volle
adversariale Blindrunde sind nicht belegt. Historische Commitbotschaften
ersetzen keinen Laufnachweis fuer einen spaeter geaenderten Arbeitsstand.

Weitere Reviewpunkte, insbesondere behauptete historische Zustimmung in
ADR-032, werden hier nicht korrigiert oder bestaetigt. Die Rueckgabe geht
an die Hauptsitzung; gesonderte Regelentscheidungen und das DCO-/Vorlagen-
Vorgehen verbleiben beim Maintainer beziehungsweise Code Owner.
