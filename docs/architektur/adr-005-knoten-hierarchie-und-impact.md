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
   (test-verankert) — ohne Bindung kann die Impact-Berechnung den Test
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
   test-verankert). Was die Selektion NICHT verspricht, ist die
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
