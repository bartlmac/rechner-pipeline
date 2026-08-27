# ADR-005: Knoten-Hierarchie, Test-Bindung, Code-Karte und berechneter Impact

Status: akzeptiert (Bartek, 2026-08-16). Umgesetzt:
`ontologie/code_index` (erweitert), `ontologie/code_karte` (neu),
`ontologie/impact` (neu); alle Testmodule gebunden.

## Kontext

Die 1M-LOC-Mechanik war seit der Systempruefung als Konvention
angelegt (Knoten-Annotation, Index), aber nicht gebaut: der Index trug
nur Familien-Granularitaet, Tests waren an keine Knoten gebunden, die
Schichtenkarte war Prosa im Skill, und die Frage "welcher Teil der
Suite muss nach dieser Aenderung laufen?" hatte keine berechnete
Antwort. Bei ~10k LOC ist das egal (volle Suite: ~80 s); der Anspruch
des Systems ist aber, dass der Skalenschmerz BEHERRSCHBAR ist — das
muss vorfuehrbar sein, bevor er eintritt.

## Entscheidung

1. **Knoten-IDs sind hierarchisch**: `familie[/generation[/zelle]]`
   (dieselbe Konvention wie `ontologie.ids.knoten_id`, die A-Box und
   Gates schon nutzen — `klv/tg2015` ist im Index dieselbe ID wie im
   Gate O3). Die Wurzel ist validiert: T-Box-Familie, registriertes
   Kern-Produkt (Produkte ohne Migrationsfall, wie BU) oder die
   System-Wurzel `system` (Werkzeug-Straenge: `system/assurance`,
   `system/skills`, `system/architektur`, ...). Tiefere Ebenen sind
   Instanzen und bewusst offen.
2. **Code bindet an die groebste Ebene, die er fachlich traegt.** Eine
   neue Generation ist Parametrierung — kein Code; deshalb bleibt
   Produktcode familien-gebunden (`klv`, `bu`, Rueckgrat `klv, bu`),
   und Generations-Bindung tragen die Artefakte, die wirklich
   generationsspezifisch sind: Tests (`test_tafel_import.py` ->
   `klv/tg2015`, `test_formeln.py` -> `klv/tg2012, klv/tg2015`),
   Falldaten (A-Box), kuenftig Tafel-Eintraege.
3. **Jedes Testmodul erklaert seine Knoten-Bindung** (dieselbe
   `Knoten:`-Docstring-Zeile). Eine ungebundene Testdatei ist Drift
   (maschinell gesichert) — ohne Bindung kann die Impact-Berechnung den Test
   nur noch konservativ einplanen.
4. **Die Schichtenkarte ist nachrechenbar** (`code_karte`): statischer
   Import-/Aufruf-Graph (ast, deterministisch, keine Ausfuehrung) mit
   deklarativer Schicht-Allowlist, der ADR-004-Zweitkern-Regel
   (`kommutationskern` konsumiert nur `qa`) und dem SDK-Verbot (ueber
   Namensfamilien, nicht exakte Namen). Eine neue Kante zwischen
   Schichten — und ebenso eine neue Schicht, auch eine ganz ohne
   Kanten — ist damit eine bewusste Architektur-Entscheidung, kein
   Nebeneffekt. Dynamische Importe (`__import__`,
   `importlib.import_module`) sind mitgeprueft: mit String-Literal wie
   ein normaler Import, mit berechnetem Namen als eigener Befund —
   sonst waere die Kante ein Loch in allen Regeln.
5. **Impact ist berechnet, nie geraten** (`impact`): ein Test laeuft,
   wenn EINE von zwei Kopplungen greift.
   * **Fachliche Kopplung** — Lineage-Verwandtschaft der Knoten
     (gleiche Linie ja: `klv` ~ `klv/tg2015`; Geschwister nein:
     `klv/tg2012` !~ `klv/tg2015`; fremde Familie nie).
   * **Code-Kopplung** — der Test importiert das geaenderte Modul
     DIREKT, unabhaengig von seiner Knoten-Linie. Ohne diese zweite
     Quelle entstehen echte Falsch-Negative (belegt: `fall.py` traegt
     `system/fall`, wird aber von klv-gebundenen Ontologie-Tests
     benutzt — die reine Lineage-Selektion liess sie liegen).
   Bewusst NICHT transitiv: die Schliessung ueber `__init__`-
   Re-Exports zieht jede Aenderung auf "alles" (gemessen: `bu.py`
   5 -> 21 Tests) und ist Lade-Zeit-Kopplung, keine fachliche; dafuer
   steht die volle Suite in CI. Die Rueckwaerts-Schliessung bleibt
   Transparenz (`abhaengige_module`) und Knoten-Fallback fuer
   unannotierte Module.
   **Fail-safe**: laesst sich eine Aenderung keinem Knoten zuordnen
   (globale Dateien, unannotierte Insel-Module, Artefakte unter
   `src/`/`tests/` ohne Bindung, nicht repo-relativ aufloesbare
   Pfade), ist der Impact die volle Suite — mit ausgewiesenem Grund.
   Praezision ist verdient, nie vermutet. Zusaetzlich nennt der Impact
   die Faelle, deren Generationen betroffen sind (Gate O3 erneut
   fahren).
6. **Die Garantie heisst Entdeckung, nicht Vollstaendigkeit** — und
   sie ist erzwungen: jedes geaenderte Modul MUSS von mindestens einem
   selektierten Test geladen werden, sonst faellt die Auswahl
   konservativ auf die volle Suite. Damit kann kein Import-Bruch
   unsichtbar bleiben (heute haelt die Deckung fuer alle 79 Module,
   maschinell gesichert). Was die Selektion NICHT verspricht, ist die
   vollstaendige Liste aller Tests, die brechen koennten: Tests, die
   ein geaendertes Modul laden, ohne fachlich betroffen zu sein,
   stehen als `weitere_lader` im Ergebnis (bei `bu.py` heute 16 zu 5
   selektierten). Ein reiner VERHALTENS-Bruch ueber eine solche Kante
   faellt erst in der vollen Suite auf — ausgewiesen, nicht versteckt.

## Konsequenzen

- "Wo lebt X, wer testet X, was muss nach dieser Aenderung laufen?"
  sind Lookups ueber DIESELBEN Knoten-IDs, die A-Box, Spez und Gates
  verwenden — die Ontologie ist der Index der Codebasis; ein
  Graph-Store bleibt eine ableitbare Projektion (D3).
- Selektive Ausfuehrung ist ein INFORMATIONSWERKZEUG (Exit 0), kein
  Gate: CI und Vor-Commit-Disziplin fahren weiter die volle Suite.
  Die Umstellung auf selektive Gates ist ein eigener, spaeterer
  Beschluss — sie braucht Vertrauen in die Bindungsqualitaet, das
  erst durch Beobachtung entsteht.
- Beleg am heutigen Stand: Aenderung an `kern/produkte/bu.py`
  selektiert 5 von 46 Testmodulen (keine reine KLV-Datei darunter);
  `pyproject.toml` selektiert alle (konservativ, Grund ausgewiesen).

## Bekannte Grenzen (ausgewiesen)

- **Datei-Granularitaet bei Daten**: `kern/tafeln.xml` bindet als
  ganze Datei an die Tafel-Schicht (`klv, bu`); dass die U70-Tafel ein
  tg2015-Artefakt ist, sieht die Datei-Ebene nicht. Tafel-/
  Zellen-Granularitaet (Daten-Eintraege mit Knoten-Attribut) ist der
  naechste Schritt, Ausloeser Fall 2.
- **Modulebene**: ein Modul mit Bindung `klv, bu` selektiert beide
  Familien, eine Testdatei laeuft ganz. Funktions-/Testfall-Ebene
  lohnt erst bei deutlich groesseren Modulen.
- **Statik**: Registry-Dispatch (`hole(produkt)`) und Methodenaufrufe
  loest die Karte nicht auf; fuer die Schicht-Regeln sind Imports
  vollstaendig, die Symbol-Sicht ist eine Untergrenze.
- **Bindungsqualitaet ist menschlich reviewbar, nicht beweisbar**:
  eine fachlich falsche Bindung (Test an fremden Knoten) unterlaeuft
  die Selektion. Dagegen stehen Review der Annotationen (sie sind
  Code) und die weiterhin volle Suite in CI.
- **Verhaltens-Kopplung ueber Knoten-Grenzen** bleibt die getragene
  Restluecke: 34 der 79 Module werden von Tests geladen, die nicht in
  ihrer Selektion stehen (Infrastruktur wie `models/manifest.py`).
  Import-Brueche fangen die erzwungene Ladedeckung und die
  `weitere_lader`-Ausweisung ab; ein reiner Verhaltens-Bruch ueber
  eine solche Kante faellt erst in der vollen Suite auf. Die
  Alternative — Selektion ueber die volle Import-Schliessung — wurde
  gemessen und verworfen (siehe unten).

## Warum Eigenbau und nicht ein fertiges Werkzeug

Geprueft (2026-08-17, auf Nachfrage des Maintainers) gegen den
Werkzeugbestand: import-linter/grimp, tach, pytest-archon, PyTestArch,
ruff (TID251), deptry, pytest-testmon, pytest --last-failed,
tree-sitter, jedi/parso, pyan3, code2flow, Graphviz/pydeps, D3,
Cytoscape.js, vis-network/pyvis, Mermaid, viz.js.

- **Parsing**: Pythons ``ast`` bleibt. Es ist der Parser, den CPython
  selbst benutzt, also fuer unseren Ein-Sprachen-Fall genauer als
  tree-sitter und ohne kompilierte Grammatik. tree-sitter waere fuer
  ALTSYSTEM-Quellen (VBA, COBOL) interessant — dort haelt der Kern
  unsere Randbedingungen, die verfuegbaren Grammatiken aber nicht;
  erneut pruefen, wenn Stage 1 solche Quellen wirklich liest.
- **Schichtregeln**: ``import-linter`` (2.13, ueber ``grimp``) ist die
  echte Ueberschneidung mit ``code_karte``. Zwei Punkte sprachen gegen
  einen Wechsel JETZT, keiner davon gegen das Werkzeug an sich:
  (1) Sein ``forbidden``-Vertrag wertet TRANSITIVE Erreichbarkeit —
  ``cli`` "importiert" darin ``models``, weil ``gates`` es tut. Unsere
  Allowlist meint direkte Nachbarschaft (``cli`` darf ``gates``
  benutzen, und was ``gates`` intern braucht, ist dessen Sache). Beide
  Semantiken sind vertretbar, aber es sind verschiedene Fragen.
  (2) Die ILLUSTRATIONEN im Report (welche Beispielkette gezeigt wird)
  schwanken zwischen identischen Laeufen; die URTEILE selbst sind
  stabil (nachgemessen: drei ``--no-cache``-Laeufe, Verdikt-Block
  byte-identisch, 11 kept / 1 broken). Fuer unseren Gate-Contract
  hiesse das: Urteil hashen, nicht den Fliesstext.
  Der Rest unserer Regeln (Zweitkern-Regel, SDK-Namensfamilien,
  dynamische Importe) liesse sich nur teilweise abbilden.
- **Ergaenzen statt ersetzen** (Kandidaten fuer spaeter, kein
  Umbau vor dem Push): ``ruff`` TID251 fuer verbotene Importe,
  ``deptry`` fuer unbenutzte/undeklarierte Abhaengigkeiten.
- **Test-Selektion**: coverage-basierte Werkzeuge (``pytest-testmon``)
  beantworten eine andere Frage als wir — welche Tests den Code
  AUSFUEHREN, nicht welchen FACHKNOTEN eine Aenderung betrifft. Sie
  koennen weder eine Generation (``klv/tg2015``) noch ein
  Migrationsfall-Gate (O3) benennen. Als Ergaenzung gegen die
  dokumentierte Verhaltens-Restluecke bleiben sie denkbar.
- **Visualisierung**: das ZEICHNEN macht fremdes Werkzeug. Der
  Generator gibt den Graphen als **Mermaid** (GitHub zeichnet es direkt
  in Markdown), **DOT** (Graphviz) und **GraphML** (Gephi, yEd,
  Graph-Store-Import) aus — wir schreiben keine Layout-Logik.
  Entscheidend fuer das Zielbild ist nicht das Format, sondern der
  AUSSCHNITT: bei ~1 Mio. Zeilen gibt es kein Bild "der Codebasis".
  Drei Ausschnitte wachsen mit der Struktur statt mit der Codemenge —
  Schichten-Ueberblick, fachliche Knotensicht, und der Blick in EINEN
  Knoten. Ueber 60 Kaesten verweigert der Generator das Bild und nennt
  den engeren Weg (fail-fast statt Knaeuel). In der Knotensicht
  entsteht eine Kante nur bei einem echten Uebergang: ein
  Rueckgrat-Modul mit `klv, bu` macht KLV nicht von BU abhaengig.
- **Keine Layout-Engine im Repo.** Graphviz braucht ein
  System-Binary (gegen die Multiplattform-Regel); kraftbasierte
  Layouts (D3, vis-network, pyvis) sind nicht reproduzierbar und damit
  nicht diffbar; Cytoscape scheitert an der Graphgroesse, nicht an
  unseren Regeln. ``ontologie/landkarte`` rendert deshalb Tabellen,
  Matrix und Listen in EINE selbsttragende HTML-Datei, ohne neue
  Abhaengigkeit und byte-stabil.

Der unvermeidbare Eigenanteil ist die ONTOLOGIE-BINDUNG: kein
Fremdwerkzeug kennt ``klv/tg2015`` als Fachknoten oder kann sagen,
welcher Migrationsfall und welches Gate O3 nach einer Aenderung neu zu
fahren ist. Genau diese Kopplung von Codebasis und A-Box ist die
Architekturhypothese — sie ist domaenenspezifisch und bleibt es.

## Verworfene Alternativen

- **Embeddings-/Vektor-Suchindex**: zweite, nicht auditierbare
  Wahrheit neben der Ontologie; veraltet ohne Drift-Begriff.
- **Impact ueber die volle Import-Schliessung statt der Knoten der
  Aenderung**: konservativer, aber via Registry-/Re-Export-Kanten
  (`produkte/__init__`) kollabiert jede Aenderung auf "alles" — die
  Selektion wuerde nie selektiv. Gemessen am heutigen Repo: `bu.py`
  5 -> 27 Testmodule (volle Rueckwaerts-Schliessung), 5 -> 21
  (transitive Test-Ladekette), 5 -> 5 mit direkten Import-Kanten. Die
  Knoten-Semantik traegt die fachliche Aussage; die Schliessung bleibt
  als Fallback, als Transparenz und als erzwungene Ladedeckung.
- **Annotationen so weit fassen, dass sie alle Importeure ueberdecken**
  (`model_point.py` waere dann `klv, bu`): verschiebt denselben
  Praezisionsverlust in die Annotationen und macht die Knoten-Aussage
  unwahr — ein Knoten benennt, was fachlich dort lebt, nicht wer
  zufaellig importiert.
