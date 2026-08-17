# ADR-006: Der Portierungs-Anwendungsfall wird ausser Betrieb genommen

Status: akzeptiert (Bartek, 2026-08-17). Umgesetzt: Entfernung aus dem
Hauptzweig; konserviert auf Branch `parked/portierung-excel`, Tag
`portierung-excel-2026-08`.

## Kontext

Das Projekt begann mit einem Beweis: Ein Coding-Agent uebersetzt einen
Excel/VBA-Tarifrechner in einen Sechs-Datei-Python-Kern, und eine
deterministische Gate-Kette nimmt die funktionale Aequivalenz ab
(617/617 Werte am 22.07.2026). Dafuer existierte eine vollstaendige
Maschinerie: die Kette `extract -> validate -> security -> conventions ->
golden_master -> algebraic -> roundtrip -> dossier`, ein
`assurance`-Orchestrator, der Sechs-Datei-Contract als Schema, ein
abgeschotteter Kindprozess je Vertrag fuer unreviewten Fremdcode, und
der Skill `build-vergleichsrechenkern`, der den Kern erzeugt.

Dieser Beweis ist erbracht. Was danach entstand, hat den Gegenstand
verschoben:

* Der Zielkern ist eine eigenstaendige, versionierte Komponente in der
  Zustandsmodell-Welt (ADR-004). Die Excel-Paritaet ist kein Anker mehr.
* Eine neue Tarifgeneration ist **Parametrierung** — der Praezedenzfall
  TG2012 -> TG2015 lief ohne eine einzige Formelaenderung durch.
* Ein neues Produkt kommt ueber die T-Box (Gate G-T) und wird IM
  Zielsystem entwickelt — nicht durch die Uebersetzung einer weiteren
  Arbeitsmappe.

Damit erzeugt niemand mehr einen Sechs-Datei-Kern. Eine Maschinerie, die
ein Artefakt abnimmt, das nicht mehr entsteht, ist kein Sicherheitsnetz,
sondern Ballast: Sie musste bei jeder Aenderung mitgepflegt werden, ihre
Doku beschrieb einen Anwendungsfall, den es nicht mehr gibt, und sie
tauchte in Gespraechen als vermeintlich lebender Pfad wieder auf.

## Entscheidung

Der Portierungs-Anwendungsfall wird aus dem Hauptzweig entfernt. Was
faellt:

* **Gates**, die einen GENERIERTEN Kern pruefen: `validate` (der
  Sechs-Datei-Contract), `security` und `conventions` (statische Pruefung
  fremden Codes), `golden_master` als eigenstaendiges Gate, `roundtrip`,
  `algebraic`, sowie `dossier` und `report` (Aggregation der Kette).
* **Der Orchestrator** `cli.py` mit dem Befehl `assurance` und das
  Paket `gates/orchestrate/`.
* **Die zugehoerigen Engines** unter `qa/` (`security`, `conventions`,
  `roundtrip`, `algebraic`, `fs_confine`, `extraction_diff`) und das
  Schema `models/kern_output.py`.
* **Der zweite Auswertungspfad** in `bestand/kernlauf.py`
  (`run_kernel_for_contract`: abgeschotteter Kindprozess je Vertrag) samt
  `render_inputs_py` — es gibt keinen unreviewten Fremdkern mehr, also
  nichts abzuschotten.
* **Der Skill** `build-vergleichsrechenkern` (beide CLI-Verzeichnisse)
  und `qa_contract.json`.

Was ausdruecklich BLEIBT, weil es der Migration dient und nicht der
Portierung:

* **Die Vorverdichtung**: `gates/extract`, `quellen/adapters/`,
  `quellen/extract/`, `models/bundle`, `models/manifest`. Stufe 1 der
  Migrations-Pipeline liest ihre Quellen damit — ohne sie gibt es keine
  A-Box.
* **Die Vergleichs-Engine** `qa/golden_master.py`: Gate O3 haelt damit
  den parametrierten Kern gegen den Quell-Rechner.
* **Der Ledger-Contract** in `gates/_common.py`. Der Gate-Katalog und
  `load_gate_ledger` sind aus `orchestrate/dossier` dorthin gewandert;
  er fuehrt jetzt die Gates, die es wirklich gibt (G0, O0, O1, O3, P9,
  B1). Bei der Gelegenheit wurde eine Schein-Unterscheidung beseitigt:
  `required` war schon immer fuer alle Gates wahr — das steht jetzt so
  im Code statt als Ableitung aus einer Liste, die mit sich selbst
  identisch war.

## Das algebraische Gate wird gerettet, nicht gestrichen

Gate G6 war kein Portierungs-Artefakt. Es prueft aktuarielle
Identitaeten, Schranken und Rekursionen mit Hypothesis — ausdruecklich
EXCEL-UNABHAENGIG, als Gegengewicht dazu, dass ein Wertevergleich auf
vier Nachkommastellen relative Drift verstecken kann. Dieser Nutzen gilt
fuer den Zielkern genauso.

Die Identitaeten leben deshalb weiter in
`tests/test_kern_algebraisch.py`, geprueft gegen den ZIELKERN ueber vier
Rechnungsbasen: Schranken fuer `q_x`, die Endalter-Politik, die
Barwert-Bilanz `A_x + d·ae_x = 1`, `ae_x = (1 - A_x)/d`, beide
Rekursionen, die Nettobeitrags-Definition und das Aequivalenzprinzip;
die Kommutations-Identitaeten (D/N/C/M) gegen den Zweitkern.

Was entfaellt, ist die VERTRAGSMECHANIK des Gates: `function_mappings`,
dynamische Aufloesung per `importlib`, ein Contract-JSON. Sie existierte,
weil der zu pruefende Kern ein FREMDES Artefakt unbekannter Modulstruktur
war. Unser Kern ist unser Code — wir importieren ihn direkt. Nicht
uebernommen sind die `l_x`-Identitaeten: der Zielkern kennt keine
Absterbeordnung, dort waere die Rekursion eine Tautologie ueber eine
Groesse, die es nicht gibt.

## Konsequenzen

* Das Paket schrumpft um rund 8.000 Zeilen in 19 Modulen; die Suite von
  46 auf 35 Testmodule (720 -> 518 Tests). Es wurde keine gepruefte
  Eigenschaft des Zielsystems aufgegeben — nur Pruefungen eines
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
* Rueckweg: `git checkout parked/portierung-excel` bzw. der Tag. Sollte
  ein kuenftiger Fall doch eine Uebersetzung brauchen, ist der Stand
  vollstaendig und lauffaehig konserviert.

## Verworfene Alternative

Die Maschinerie "erstmal liegen lassen, sie stoert ja nicht". Sie stoert:
Sie kostet Pflege bei jeder Aenderung, ihre Doku widerspricht dem
Zielbild, und sie erzeugt in jedem Gespraech den Eindruck eines zweiten,
lebenden Anwendungsfalls. Wo Code konserviert gehoert, gehoert er in
einen Branch — nicht in den Hauptzweig.
