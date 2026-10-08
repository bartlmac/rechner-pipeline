# ADR-006: Der Portierungs-Anwendungsfall wird ausser Betrieb genommen

Status: akzeptiert (Maintainer, 2026-08-17). Umgesetzt: Entfernung aus dem
Hauptzweig; konserviert auf Branch `parked/portierung-excel`, Tag
`portierung-excel-2026-08`. *(Nachtrag 2026-08-19: Branch und Tag
wurden vor der Veröffentlichung aus dem Arbeits-Repo entfernt — sie
zeigten in die klarnamen-bereinigte Vorgänger-Historie. Das Konservat
liegt vollständig im nicht veröffentlichten Archiv des Maintainers,
als Git-Bundle.)*

## Kontext

Das Projekt begann mit einem Beweis: Ein Coding-Agent übersetzt einen
Excel/VBA-Tarifrechner in einen Sechs-Datei-Python-Kern, und eine
deterministische Gate-Kette nimmt die funktionale Äquivalenz ab
(617/617 Werte am 22.07.2026). Dafür existierte eine vollständige
Maschinerie: die Kette `extract -> validate -> security -> conventions ->
golden_master -> algebraic -> roundtrip -> dossier`, ein
`assurance`-Orchestrator, der Sechs-Datei-Contract als Schema, ein
abgeschotteter Kindprozess je Vertrag für unreviewten Fremdcode, und
der Skill `build-vergleichsrechenkern`, der den Kern erzeugt.

Dieser Beweis ist erbracht. Was danach entstand, hat den Gegenstand
verschoben:

* Der Zielkern ist eine eigenständige, versionierte Komponente in der
  Zustandsmodell-Welt (ADR-004). Die Excel-Parität ist kein laufender Referenzwert mehr.
* Eine neue Tarifgeneration ist **Parametrierung** — der Präzedenzfall
  TG2012 -> TG2015 lief ohne eine einzige Formeländerung durch.
* Ein neues Produkt kommt über die T-Box (Gate A-O1) und wird IM
  Zielsystem entwickelt — nicht durch die Übersetzung einer weiteren
  Arbeitsmappe.

Damit erzeugt niemand mehr einen Sechs-Datei-Kern. Eine Maschinerie, die
ein Artefakt abnimmt, das nicht mehr entsteht, ist kein Sicherheitsnetz,
sondern Ballast: Sie musste bei jeder Änderung mitgepflegt werden, ihre
Doku beschrieb einen Anwendungsfall, den es nicht mehr gibt, und sie
tauchte in Gesprächen als vermeintlich lebender Pfad wieder auf.

## Entscheidung

Der Portierungs-Anwendungsfall wird aus dem Hauptzweig entfernt. Was
fällt:

* **Gates**, die einen GENERIERTEN Kern prüfen: `validate` (der
  Sechs-Datei-Contract), `security` und `conventions` (statische Prüfung
  fremden Codes), `golden_master` als eigenständiges Gate, `roundtrip`,
  `algebraic`, sowie `dossier` und `report` (Aggregation der Kette).
* **Der Orchestrator** `cli.py` mit dem Befehl `assurance` und das
  Paket `gates/orchestrate/`.
* **Die zugehörigen Engines** unter `qa/` (`security`, `conventions`,
  `roundtrip`, `algebraic`, `fs_confine`, `extraction_diff`) und das
  Schema `models/kern_output.py`.
* **Der zweite Auswertungspfad** in `bestand/kernlauf.py`
  (`run_kernel_for_contract`: abgeschotteter Kindprozess je Vertrag) samt
  `render_inputs_py` — es gibt keinen unreviewten Fremdkern mehr, also
  nichts abzuschotten.
* **Der Skill** `build-vergleichsrechenkern` (beide CLI-Verzeichnisse)
  und `qa_contract.json`.

Was ausdrücklich BLEIBT, weil es der Migration dient und nicht der
Portierung:

* **Die Vorverdichtung**: `gates/extract`, `quellen/adapters/`,
  `quellen/extract/`, `models/bundle`, `models/manifest`. Stufe 1 der
  Migrations-Pipeline liest ihre Quellen damit — ohne sie gibt es keine
  A-Box.
* **Die Vergleichs-Engine** `qa/golden_master.py`: Gate P-K1 hält damit
  den parametrierten Kern gegen den Quell-Rechner.
* **Der Ledger-Contract** in `gates/_common.py`. Der Gate-Katalog und
  `load_gate_ledger` sind aus `orchestrate/dossier` dorthin gewandert;
  er führt jetzt die Gates, die es wirklich gibt (P-Q1, P-Q2, P-Q3, P-K1, P9,
  P-B1). Bei der Gelegenheit wurde eine Schein-Unterscheidung beseitigt:
  `required` war schon immer für alle Gates wahr — das steht jetzt so
  im Code statt als Ableitung aus einer Liste, die mit sich selbst
  identisch war.

## Das algebraische Gate wird gerettet, nicht gestrichen

Gate G6 war kein Portierungs-Artefakt. Es prüft aktuarielle
Identitäten, Schranken und Rekursionen mit Hypothesis — ausdrücklich
EXCEL-UNABHAENGIG, als Gegengewicht dazu, dass ein Wertevergleich auf
vier Nachkommastellen relative Drift verstecken kann. Dieser Nutzen gilt
für den Zielkern genauso.

Die Identitäten leben deshalb weiter in
`tests/test_kern_algebraisch.py`, geprüft gegen den ZIELKERN über vier
Rechnungsbasen: Schranken für `q_x`, die Endalter-Politik, die
Barwert-Bilanz `A_x + d·ae_x = 1`, `ae_x = (1 - A_x)/d`, beide
Rekursionen, die Nettobeitrags-Definition und das Äquivalenzprinzip;
die Kommutations-Identitäten (D/N/C/M) gegen den Zweitkern.

Was entfällt, ist die VERTRAGSMECHANIK des Gates: `function_mappings`,
dynamische Auflösung per `importlib`, ein Contract-JSON. Sie existierte,
weil der zu prüfende Kern ein FREMDES Artefakt unbekannter Modulstruktur
war. Unser Kern ist unser Code — wir importieren ihn direkt. Nicht
übernommen sind die `l_x`-Identitäten: der Zielkern kennt keine
Absterbeordnung, dort wäre die Rekursion eine Tautologie über eine
Größe, die es nicht gibt.

## Konsequenzen

* Das Paket schrumpft um rund 8.000 Zeilen in 19 Modulen; die Suite von
  46 auf 35 Testmodule (720 -> 518 Tests). Es wurde keine geprüfte
  Eigenschaft des Zielsystems aufgegeben — nur Prüfungen eines
  Artefakts, das nicht mehr entsteht.
* `pip install` bringt kein Konsolen-Kommando `rechner-pipeline` mehr;
  alle Einstiege sind `python -m rechner_pipeline.<modul>`.
* README, AGENTS.md und ONBOARDING beschreiben den Portierungsakt nur
  noch als abgeschlossene Vorgeschichte mit Verweis auf den geparkten
  Branch — nicht als lebenden Pfad.
* ADR-001 und ADR-002 beschreiben Strukturen, die es teilweise nicht
  mehr gibt (`orchestrate/`, `kern_output`, `assurance --fall`). Sie
  werden NICHT umgeschrieben — ein ADR ist Protokoll, kein Handbuch —,
  sondern tragen einen Ablösungsvermerk auf dieses ADR.
* Rückweg: der konservierte Stand ist vollständig und lauffähig im
  Archiv des Maintainers erhalten (Git-Bundle, siehe Nachtrag oben).
  Sollte ein künftiger Fall doch eine Übersetzung brauchen, lässt
  er sich von dort wiederherstellen.

## Verworfene Alternative

Die Maschinerie "erstmal liegen lassen, sie stört ja nicht". Sie stört:
Sie kostet Pflege bei jeder Änderung, ihre Doku widerspricht dem
Zielbild, und sie erzeugt in jedem Gespräch den Eindruck eines zweiten,
lebenden Anwendungsfalls. Wo Code konserviert gehört, gehört er in
einen Branch — nicht in den Hauptzweig.
