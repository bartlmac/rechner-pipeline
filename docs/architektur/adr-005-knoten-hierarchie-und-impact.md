# ADR-005: Knoten-Hierarchie, Test-Bindung, Code-Karte und berechneter Impact

Status: akzeptiert (Maintainer, 2026-08-16). Umgesetzt:
`ontologie/code_index` (erweitert), `ontologie/code_karte` (neu),
`ontologie/impact` (neu); alle Testmodule gebunden.

## Kontext

Die 1M-LOC-Mechanik war seit der Systemprüfung als Konvention
angelegt (Knoten-Annotation, Index), aber nicht gebaut: der Index trug
nur Familien-Granularität, Tests waren an keine Knoten gebunden, die
Schichtenkarte war Prosa im Skill, und die Frage "welcher Teil der
Suite muss nach dieser Änderung laufen?" hatte keine berechnete
Antwort. Bei ~10k LOC ist das egal (volle Suite: ~80 s); der Anspruch
des Systems ist aber, dass der Skalenschmerz BEHERRSCHBAR ist — das
muss vorführbar sein, bevor er eintritt.

## Entscheidung

1. **Knoten-IDs sind hierarchisch**: `familie[/generation[/zelle]]`
   (dieselbe Konvention wie `ontologie.ids.knoten_id`, die A-Box und
   Gates schon nutzen — `klv/tg2015` ist im Index dieselbe ID wie im
   Gate P-K1). Die Wurzel ist validiert: T-Box-Familie, registriertes
   Kern-Produkt (Produkte ohne Migrationsfall, wie BU) oder die
   System-Wurzel `system` (Werkzeug-Stränge: `system/assurance`,
   `system/skills`, `system/architektur`, ...). Tiefere Ebenen sind
   Instanzen und bewusst offen.
2. **Code bindet an die gröbste Ebene, die er fachlich trägt.** Eine
   neue Generation ist Parametrierung — kein Code; deshalb bleibt
   Produktcode familien-gebunden (`klv`, `bu`, Rückgrat `klv, bu`),
   und Generations-Bindung tragen die Artefakte, die wirklich
   generationsspezifisch sind: Tests (`test_tafel_import.py` ->
   `klv/tg2015`, `test_formeln.py` -> `klv/tg2012, klv/tg2015`),
   Falldaten (A-Box), künftig Tafel-Einträge.
3. **Jedes Testmodul erklärt seine Knoten-Bindung** (dieselbe
   `Knoten:`-Docstring-Zeile). Eine ungebundene Testdatei ist Drift
   (maschinell gesichert) — ohne Bindung kann die Impact-Berechnung den Test
   nur noch konservativ einplanen.
4. **Die Schichtenkarte ist nachrechenbar** (`code_karte`): statischer
   Import-/Aufruf-Graph (ast, deterministisch, keine Ausführung) mit
   deklarativer Schicht-Allowlist, der ADR-004-Zweitkern-Regel
   (`kommutationskern` konsumiert nur `qa`) und dem SDK-Verbot (über
   Namensfamilien, nicht exakte Namen). Eine neue Kante zwischen
   Schichten — und ebenso eine neue Schicht, auch eine ganz ohne
   Kanten — ist damit eine bewusste Architektur-Entscheidung, kein
   Nebeneffekt. Dynamische Importe (`__import__`,
   `importlib.import_module`) sind mitgeprüft: mit String-Literal wie
   ein normaler Import, mit berechnetem Namen als eigener Befund —
   sonst wäre die Kante ein Loch in allen Regeln.
5. **Impact ist berechnet, nie geraten** (`impact`): ein Test läuft,
   wenn EINE von zwei Kopplungen greift.
   * **Fachliche Kopplung** — Lineage-Verwandtschaft der Knoten
     (gleiche Linie ja: `klv` ~ `klv/tg2015`; Geschwister nein:
     `klv/tg2012` !~ `klv/tg2015`; fremde Familie nie).
   * **Code-Kopplung** — der Test importiert das geänderte Modul
     DIREKT, unabhängig von seiner Knoten-Linie. Ohne diese zweite
     Quelle entstehen echte Falsch-Negative (belegt: `fall.py` trägt
     `system/fall`, wird aber von klv-gebundenen Ontologie-Tests
     benutzt — die reine Lineage-Selektion liess sie liegen).
   Bewusst NICHT transitiv: die Schliessung über `__init__`-
   Re-Exports zieht jede Änderung auf "alles" (gemessen: `bu.py`
   5 -> 21 Tests) und ist Lade-Zeit-Kopplung, keine fachliche; dafür
   steht die volle Suite in CI. Die Rückwärts-Schliessung bleibt
   Transparenz (`abhaengige_module`) und Knoten-Fallback für
   unannotierte Module.
   **Fail-safe**: lässt sich eine Änderung keinem Knoten zuordnen
   (globale Dateien, unannotierte Insel-Module, Artefakte unter
   `src/`/`tests/` ohne Bindung, nicht repo-relativ auflösbare
   Pfade), ist der Impact die volle Suite — mit ausgewiesenem Grund.
   Präzision ist verdient, nie vermutet. Zusätzlich nennt der Impact
   die Fälle, deren Generationen betroffen sind (Gate P-K1 erneut
   fahren).
6. **Die Garantie heisst Entdeckung, nicht Vollständigkeit** — und
   sie ist erzwungen: jedes geänderte Modul MUSS von mindestens einem
   selektierten Test geladen werden, sonst fällt die Auswahl
   konservativ auf die volle Suite. Damit kann kein Import-Bruch
   unsichtbar bleiben (heute hält die Deckung für alle 79 Module,
   maschinell gesichert). Was die Selektion NICHT verspricht, ist die
   vollständige Liste aller Tests, die brechen könnten: Tests, die
   ein geändertes Modul laden, ohne fachlich betroffen zu sein,
   stehen als `weitere_lader` im Ergebnis (bei `bu.py` heute 16 zu 5
   selektierten). Ein reiner VERHALTENS-Bruch über eine solche Kante
   fällt erst in der vollen Suite auf — ausgewiesen, nicht versteckt.

## Konsequenzen

- "Wo lebt X, wer testet X, was muss nach dieser Änderung laufen?"
  sind Lookups über DIESELBEN Knoten-IDs, die A-Box, Spez und Gates
  verwenden — die Ontologie ist der Index der Codebasis; ein
  Graph-Store bleibt eine ableitbare Projektion (D3).
- Selektive Ausführung ist ein INFORMATIONSWERKZEUG (Exit 0), kein
  Gate: CI und Vor-Commit-Disziplin fahren weiter die volle Suite.
  Die Umstellung auf selektive Gates ist ein eigener, späterer
  Beschluss — sie braucht Vertrauen in die Bindungsqualität, das
  erst durch Beobachtung entsteht.
- Beleg am heutigen Stand: Änderung an `kern/produkte/bu.py`
  selektiert 5 von 46 Testmodulen (keine reine KLV-Datei darunter);
  `pyproject.toml` selektiert alle (konservativ, Grund ausgewiesen).

## Bekannte Grenzen (ausgewiesen)

- **Datei-Granularität bei Daten**: `kern/tafeln.xml` bindet als
  ganze Datei an die Tafel-Schicht (`klv, bu`); dass die U70-Tafel ein
  tg2015-Artefakt ist, sieht die Datei-Ebene nicht. Tafel-/
  Zellen-Granularität (Daten-Einträge mit Knoten-Attribut) ist der
  nächste Schritt, Auslöser Fall 2.
- **Modulebene**: ein Modul mit Bindung `klv, bu` selektiert beide
  Familien, eine Testdatei läuft ganz. Funktions-/Testfall-Ebene
  lohnt erst bei deutlich größeren Modulen.
- **Statik**: Registry-Dispatch (`hole(produkt)`) und Methodenaufrufe
  löst die Karte nicht auf; für die Schicht-Regeln sind Imports
  vollständig, die Symbol-Sicht ist eine Untergrenze.
- **Bindungsqualität ist menschlich reviewbar, nicht beweisbar**:
  eine fachlich falsche Bindung (Test an fremden Knoten) unterläuft
  die Selektion. Dagegen stehen Review der Annotationen (sie sind
  Code) und die weiterhin volle Suite in CI.
- **Verhaltens-Kopplung über Knoten-Grenzen** bleibt die getragene
  Restlücke: 34 der 79 Module werden von Tests geladen, die nicht in
  ihrer Selektion stehen (Infrastruktur wie `models/manifest.py`).
  Import-Brüche fangen die erzwungene Ladedeckung und die
  `weitere_lader`-Ausweisung ab; ein reiner Verhaltens-Bruch über
  eine solche Kante fällt erst in der vollen Suite auf. Die
  Alternative — Selektion über die volle Import-Schliessung — wurde
  gemessen und verworfen (siehe unten).

## Warum Eigenbau und nicht ein fertiges Werkzeug

Geprüft (2026-08-17, auf Nachfrage des Maintainers) gegen den
Werkzeugbestand: import-linter/grimp, tach, pytest-archon, PyTestArch,
ruff (TID251), deptry, pytest-testmon, pytest --last-failed,
tree-sitter, jedi/parso, pyan3, code2flow, Graphviz/pydeps, D3,
Cytoscape.js, vis-network/pyvis, Mermaid, viz.js.

- **Parsing**: Pythons ``ast`` bleibt. Es ist der Parser, den CPython
  selbst benutzt, also für unseren Ein-Sprachen-Fall genauer als
  tree-sitter und ohne kompilierte Grammatik. tree-sitter wäre für
  ALTSYSTEM-Quellen (VBA, COBOL) interessant — dort hält der Kern
  unsere Randbedingungen, die verfügbaren Grammatiken aber nicht;
  erneut prüfen, wenn Stage 1 solche Quellen wirklich liest.
- **Schichtregeln**: ``import-linter`` (2.13, über ``grimp``) ist die
  echte Überschneidung mit ``code_karte``. Zwei Punkte sprachen gegen
  einen Wechsel JETZT, keiner davon gegen das Werkzeug an sich:
  (1) Sein ``forbidden``-Vertrag wertet TRANSITIVE Erreichbarkeit —
  ``cli`` "importiert" darin ``models``, weil ``gates`` es tut. Unsere
  Allowlist meint direkte Nachbarschaft (``cli`` darf ``gates``
  benutzen, und was ``gates`` intern braucht, ist dessen Sache). Beide
  Semantiken sind vertretbar, aber es sind verschiedene Fragen.
  (2) Die ILLUSTRATIONEN im Report (welche Beispielkette gezeigt wird)
  schwanken zwischen identischen Läufen; die URTEILE selbst sind
  stabil (nachgemessen: drei ``--no-cache``-Läufe, Verdikt-Block
  byte-identisch, 11 kept / 1 broken). Für unseren Gate-Contract
  hiesse das: Urteil hashen, nicht den Fliesstext.
  Der Rest unserer Regeln (Zweitkern-Regel, SDK-Namensfamilien,
  dynamische Importe) liesse sich nur teilweise abbilden.
- **Ergänzen statt ersetzen** (Kandidaten für später, kein
  Umbau vor dem Push): ``ruff`` TID251 für verbotene Importe,
  ``deptry`` für unbenutzte/undeklarierte Abhängigkeiten.
- **Test-Selektion**: coverage-basierte Werkzeuge (``pytest-testmon``)
  beantworten eine andere Frage als wir — welche Tests den Code
  AUSFUEHREN, nicht welchen FACHKNOTEN eine Änderung betrifft. Sie
  können weder eine Generation (``klv/tg2015``) noch ein
  Migrationsfall-Gate (P-K1) benennen. Als Ergänzung gegen die
  dokumentierte Verhaltens-Restlücke bleiben sie denkbar.
- **Visualisierung**: das ZEICHNEN macht fremdes Werkzeug. Der
  Generator gibt den Graphen als **Mermaid** (GitHub zeichnet es direkt
  in Markdown), **DOT** (Graphviz) und **GraphML** (Gephi, yEd,
  Graph-Store-Import) aus — wir schreiben keine Layout-Logik.
  Entscheidend für das Zielbild ist nicht das Format, sondern der
  AUSSCHNITT: bei ~1 Mio. Zeilen gibt es kein Bild "der Codebasis".
  Drei Ausschnitte wachsen mit der Struktur statt mit der Codemenge —
  Schichten-Überblick, fachliche Knotensicht, und der Blick in EINEN
  Knoten. Über 60 Kästen verweigert der Generator das Bild und nennt
  den engeren Weg (fail-fast statt Knäuel). In der Knotensicht
  entsteht eine Kante nur bei einem echten Übergang: ein
  Rückgrat-Modul mit `klv, bu` macht KLV nicht von BU abhängig.
- **Keine Layout-Engine im Repo.** Graphviz braucht ein
  System-Binary (gegen die Multiplattform-Regel); kraftbasierte
  Layouts (D3, vis-network, pyvis) sind nicht reproduzierbar und damit
  nicht diffbar; Cytoscape scheitert an der Graphgröße, nicht an
  unseren Regeln. ``ontologie/landkarte`` rendert deshalb Tabellen,
  Matrix und Listen in EINE selbsttragende HTML-Datei, ohne neue
  Abhängigkeit und byte-stabil.

Der unvermeidbare Eigenanteil ist die ONTOLOGIE-BINDUNG: kein
Fremdwerkzeug kennt ``klv/tg2015`` als Fachknoten oder kann sagen,
welcher Migrationsfall und welches Gate P-K1 nach einer Änderung neu zu
fahren ist. Genau diese Kopplung von Codebasis und A-Box ist die
Architekturhypothese — sie ist domänenspezifisch und bleibt es.

## Verworfene Alternativen

- **Embeddings-/Vektor-Suchindex**: zweite, nicht auditierbare
  Wahrheit neben der Ontologie; veraltet ohne Drift-Begriff.
- **Impact über die volle Import-Schliessung statt der Knoten der
  Änderung**: konservativer, aber via Registry-/Re-Export-Kanten
  (`produkte/__init__`) kollabiert jede Änderung auf "alles" — die
  Selektion würde nie selektiv. Gemessen am heutigen Repo: `bu.py`
  5 -> 27 Testmodule (volle Rückwärts-Schliessung), 5 -> 21
  (transitive Test-Ladekette), 5 -> 5 mit direkten Import-Kanten. Die
  Knoten-Semantik trägt die fachliche Aussage; die Schliessung bleibt
  als Fallback, als Transparenz und als erzwungene Ladedeckung.
- **Annotationen so weit fassen, dass sie alle Importeure überdecken**
  (`model_point.py` wäre dann `klv, bu`): verschiebt denselben
  Präzisionsverlust in die Annotationen und macht die Knoten-Aussage
  unwahr — ein Knoten benennt, was fachlich dort lebt, nicht wer
  zufällig importiert.
