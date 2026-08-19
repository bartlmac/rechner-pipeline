---
name: migrationsfall-durchfuehren
description: >-
  Run a complete migration case through the ontology pipeline (Stufe 1 Quellen->A-Box
  plus Bestandsabzug->Transformation, Stufe 2 A-Box->Spez->Kern-Parametrierung, Stufe 3
  Golden-Master-Abnahme plus Bestands-Abnahme ueber zwei Stichtage), including the
  human gates G-1/G-2 and their P9 snapshots. Trigger when the user asks to migrate a new
  Tarifgeneration or product delivery (Tarifmeldung + Tarifrechner + Bestandsabzug) into the
  kernel, to "einen Migrationsfall durchfuehren/anlegen", or names this skill. Skip for:
  authoring gates (use author-rechner-toolbox-gate) or pure read/analysis questions.
---

# Einen Migrationsfall durchfuehren

## Rolle und Ziel

Du orchestrierst einen Migrationsfall durch die Ontologie-Pipeline
(Architektur: `docs/architektur/migrations-pipeline-v01.md`). Ziel ist
ein abgenommener Kern-Parametrierungsstand: Golden Master gegen den
Quell-Rechner gruen, alle Quell-Widersprueche als Diskrepanz-Objekte
erfasst und menschlich entschieden, jeder Schritt mit Gate-Ledger.

Eine Lieferung hat zwei Haelften, und der Fall ist erst mit beiden
fertig: die TARIFPARAMETER (Meldung + Rechner -> A-Box -> Spez -> Kern,
Stufen 1/2/3) und der BESTANDSABZUG (Vertraege -> Transformation ->
uebernommener Bestand -> Abnahme ueber zwei Stichtage, Stufen 1b/3b).
Enthaelt die Lieferung keinen Abzug, entfallen 1b und 3b — dann sag das
ausdruecklich, statt es unerwaehnt zu lassen.

Nicht verhandelbar (P1-P10, Kurzform):

- Kein Agent liest Rohquellen, zu denen ein strukturiertes Derivat
  existiert; keine Stufe liest Rohquellen einer frueheren Stufe.
- Widersprueche zwischen Quellen entstehen im deterministischen Merge
  und werden NIE von einem Agenten entschieden — vorlaeufige
  Aufloesungen tragen `vorlaeufig=true` und blocken jede menschliche
  Annahme.
- Jede Aussage traegt Provenienz (Quelle+SHA-256, Fundstelle, Akteur,
  Zeitpunkt). Der Akteur-String nennt Modell und Skill:
  `<modell>/<skill>@<git-sha-kurz>` (git rev-parse --short HEAD).
- LLM-Schritte schlagen vor; Vergleich, Coverage, Urteil, Abnahme sind
  Code. Wo etwas nicht pruefbar ist, wird das AUSGEWIESEN, nie still
  uebersprungen.

## Referenzfall

`faelle/archiv/baldrian-klv-tg2015` ist der Praezedenzfall: die Baldrian Leben
(fiktives abgebendes Unternehmen) liefert Tarifmeldung und Tarifrechner,
die PLV uebernimmt den KLV-Bestand (TG2012 -> TG2015).

Er dient AUSSCHLIESSLICH als Formvorlage: Artefakt-FORMATE und
Verzeichnisstruktur nachschlagen, also wie ein Fragment, eine Spez oder
ein G-1-Dokument aufgebaut ist. Werte, Lesarten, Zuordnungen oder
Entscheidungen einer anderen Migration werden NIE uebernommen — jeder
Fall wird aus seinen eigenen Quellen belegt, auch wenn er dieselbe
Generation betrifft. Ein Wert, den du nicht in deiner Quelle gefunden
hast, gehoert nach `nicht_belegt`, nicht aus dem Archiv abgeschrieben.

Untersagt der Auftraggeber den Zugriff auf archivierte Faelle, gilt
das Verbot ohne Ausnahme — auch fuer Formatfragen. Dann die Formate aus
dem generierten Schema (`model_json_schema()`) und den Docstrings der
beteiligten Module ableiten und im Zweifel den Menschen fragen.

## Ablauf

### Stufe 0 — Fall-Arbeitsbereich

```bash
python -m rechner_pipeline.fall anlegen --fall faelle/<fall> --beschreibung "..."
python -m rechner_pipeline.fall registrieren --fall faelle/<fall> --datei <quelle>   # je Quelle
python -m rechner_pipeline.fall status --fall faelle/<fall>
```

Regeln: Eingang ist nicht regenerierbar und wird nie aufgeraeumt;
Konflikte beim Registrieren (gleicher Name, anderer Inhalt) sind ein
Vorgang fuer den Menschen, kein Overwrite.

### Stufe 1 — Quellen -> A-Box

1. Vorverdichtung (deterministisch, je Quelltyp):
   - XLSM: `python -m rechner_pipeline.gates.extract --repo-root . --input faelle/<fall>/eingang/<datei> --out-dir faelle/<fall>/abgeleitet/vorverdichtung/xlsm-<GEN> --adapter excel --diagnostics-dir faelle/<fall>/abgeleitet/diagnostics`
   - DOCX: `python -m rechner_pipeline.quellen.tarifplan_staging --docx faelle/<fall>/eingang/<datei> --out faelle/<fall>/abgeleitet/vorverdichtung/meldung-<GEN>.json`
2. Extraktion: je (Quelle x Generation) EIN Agent nach Skill
   `extrahiere-quellfragment` (Structured Output gegen das generierte
   QuellFragment-Schema; der Agent sieht NUR seine eigene Quelle).
   Fragmente als JSON unter `abgeleitet/abox/fragmente/<gen>-<art>.json`
   ablegen.
3. Verifikations-Pass: auffaellige Extraktionen (niedrige Konfidenz,
   Anmerkungen) gegen die Vorverdichtung nachpruefen; Korrekturen im
   Fragment mit Anmerkung dokumentieren, Akteur um `+verifikation`
   ergaenzen.
4. Merge (deterministisch, MIT Ledger): `fragmente/akteure.json`
   schreiben ({"<fragment>.json": "<modell>/<skill>@<git-sha>"}), dann
   `python -m rechner_pipeline.gates.abox_merge --fall faelle/<fall> --repo-root .`
   — NIE baue_abox von Hand fuer einen echten Fall: der Merge-Ledger
   bindet die A-Box an die Fragmente, Gate O1 rechnet die Kette nach.
   Widersprueche werden Diskrepanz-Objekte — erwuenscht.
5. Gate O1: `python -m rechner_pipeline.gates.abox_validate --fall faelle/<fall> --repo-root .`
   Blockt bei Coverage-Luecken und offenen Diskrepanzen. Fuer den
   Weiterbau duerfen Diskrepanzen VORLAEUFIG zur Rechner-Lesart
   aufgeloest werden (`loese_diskrepanz_auf(..., vorlaeufig=True)`,
   Begruendung: der GM reproduziert den Rechner; fachliche Entscheidung
   G-1) — niemals endgueltig durch einen Agenten.

GRENZE DIESER STUFE (bewusst, v0.1 — nenne sie, statt sie zu
verschweigen): Das QuellFragment traegt PARAMETER, keine FORMELN. Ein
Widerspruch in der Formel selbst — Meldung und Rechner bestimmen
dieselbe Groesse verschieden, etwa mit anderer Bezugsgroesse oder
anderem Index — wird deshalb nie eine Diskrepanz und kann von keinem
Gate gefunden werden; O3 bleibt gruen, weil er den Rechner reproduziert.
Die Identitaet der Formeln ist heute menschliche Abnahme gegen den
Tarifplan (`docs/tarifplaene/`) im Gate G-1. Faellt dir beim Arbeiten
eine Formelabweichung auf, gehoert sie ausdruecklich in die
G-1-Vorlage (Ziffer der Meldung, Rechner-Lesart, Wirkung) — sie als
"nicht extrahierbar" zu uebergehen waere ein stiller Verlust.
Begruendung und Ausbaupfad: `docs/architektur/migrations-pipeline-v01.md`
Abschnitt 8.1.

### Stufe 1b — Bestandsabzug -> Ziel-Ontologie (wenn die Lieferung einen enthaelt)

Der Bestandsabzug laeuft NICHT durch die Fragment-Extraktion: Stufe 1
uebersetzt Tarifgroessen in die A-Box, hier werden Vertraege in das
Ziel-Datenmodell uebersetzt. Beides ist Stufe 1, weil beides aus einer
Quelle liest und beides an G-1 haengt.

1. Vorverdichtung (deterministisch, P10 — der Agent sieht nie die
   Rohdatei):
   `python -m rechner_pipeline.quellen.bestand_profil --input faelle/<fall>/eingang/<abzug>.csv --out faelle/<fall>/abgeleitet/vorverdichtung/bestand-<stichtag>.json`
   Das Profil traegt je Spalte Typ-Heuristik, Beispielwerte,
   Kardinalitaet, Leeranteil und den SHA-256 der Quelle.
2. Mapping vorschlagen: Skill `transformiere-quellbestand` — EIN Agent,
   der nur das Profil sieht und eine `TransformationsSpec` unter
   `faelle/<fall>/abgeleitet/transformation/<quelle>.spec.json` ablegt.
   Jedes Ziel-Pflichtfeld (`ontologie.transformation.ZIEL_PFLICHT`) muss
   gedeckt sein; was er nicht belegen kann, wird `OffenerKonflikt` mit
   praeziser Frage — nie eine Annahme.
3. Pruefen und anwenden (deterministisch, nie von Hand):
   `ontologie.transformation.validate_spec(spec, quellspalten)` muss
   LEER sein, danach `wende_an(spec, zeilen)`. `wende_an` gibt
   `(zeilen, befunde)` zurueck und laesst jede Zeile mit Befund WEG —
   wer nur die Zeilen nimmt, migriert stillschweigend weniger
   Vertraege. Zaehle die Klammer laut: Zeilen im Abzug -> transformierte
   Zeilen -> Befunde, und trag sie in die G-1-Vorlage und den
   Abnahmebericht (`--transformation-ergebnis`).
4. Abzugsabgleich, wo der Abzug eine offene Diskrepanz entscheiden kann
   (`qa.abzugsabgleich.gleiche_ab`): er belegt eine Lesart nur, wenn
   GENAU eine zu den gelieferten Werten passt, und niemals gegen die
   Meldung — eine verworfene Meldungs-Lesart bleibt immer beim Menschen
   (`bereite-fachkonflikt-auf`).
5. Offene Konflikte der Spec und die Befundliste gehen mit an G-1. Ein
   Ziel-Pflichtfeld, das die Quelle nicht hergibt, ist ein STOPP: die
   Ziel-Ontologie zu erweitern ist Gate G-T, nie deine Entscheidung.

Von den transformierten Zeilen zum BESTAND des Zielsystems: `wende_an`
liefert die VERTRAGSfelder (die Kern-Contract-Seite, `ZIEL_PFLICHT`).
Die Bestands-Tabellen verlangen mehr — `models/bestand.STAMM_SPALTEN`
fuehrt zusaetzlich Generations- und Statusfelder (`tarif_generation`,
`produkt`, `status_code`/`status_date`, die Datumsspalten). Die kommen
aus der Spez des Falls und aus der Lieferung, NIE aus dem Mapping (der
Abzug parametriert keine Generation).

Bereits beitragsfreie Vertraege — in einem uebernommenen Bestand IMMER
enthalten — tragen im Stamm KEIN PEX: der Stamm fuehrt den Vertrag bei
Beginn (`status_code` POL, `status_id` 1), die Beitragsfreistellung ist
eine Zeile der Statushistorie (`status_id` 2, `status_date` = Datum der
Beitragsfreistellung). Nur so finden Zeitscheibe und Auswertung den
beitragsfreien Track und sein PEX-Jahr; ein PEX im Stamm weist Gate B1
zurueck (`status_code ausserhalb ('POL',)`).

Geschrieben wird deterministisch mit
`bestand/parquet_io.write_portfolio`. Dieser Zusammenbau ist heute
fallweiser Code und kein eigenes Modul: leg ihn als Skript in den
Fall-Arbeitsbereich (`abgeleitet/skripte/`), damit er reproduzierbar
und pruefbar bleibt, und weise ihn im G-1-Dossier aus.

### Gate G-1 (Mensch — hier STOPPST du und uebergibst)

Vorlegen: `abgeleitet/fachspez/<gen>.md` (Generator:
`spez.fachspez.speichere_fachspez`), Diskrepanzenliste, Coverage — und,
wenn Stufe 1b lief, die offenen Konflikte der TransformationsSpec, die
Befunde der Anwendung und jede beim Lesen aufgefallene Formelabweichung
(siehe Grenze der Stufe 1).
Der Mensch entscheidet mit
`python -m rechner_pipeline.ontologie.entscheide --rolle mensch ...` und
snapshottet mit `python -m rechner_pipeline.gates.gate_entscheid
--gate G-1 --rolle mensch ...`. Als Agent darfst du AUSSCHLIESSLICH
ablehnen (--rolle agent, dokumentierter Zwischenstand). Die Annahme
rechnet ihre Vorbedingungen: O1 gruen und auf dem aktuellen
A-Box-Stand verankert; G-2 verlangt zusaetzlich O3 gruen+verankert und
einen geltenden G-1-Annahme-Snapshot desselben Stands.

### Stufe 2 — A-Box -> Spez -> Kern

1. Spez: `spez.erzeugen.baue_spez(abox, <gen-id>, referenz_id=<vorgaenger>)`
   + `spez.validierung.speichere_spez`. Das Struktur-Urteil
   (Parametrierung vs. neue Produktfamilie) wird BERECHNET — nimm es
   ernst: `neue_produktfamilie` oder offene Erweiterungsstellen heissen
   STOPP und Mensch fragen (T-Box-/Kern-Erweiterung ist Gate G-T).
2. Tafel-Import: `python -m rechner_pipeline.quellen.tafel_import --fall faelle/<fall> --generation <gen-id> --dry-run`,
   pruefen, dann scharf. Konflikte (wertverschiedene Tafeln gleichen
   Namens) sind ein Provenienz-Problem fuer den Menschen.
3. Kern-Aenderungen: eine neue Generation ist PARAMETRIERUNG — kein
   Formel-Code. Neue Tafeln in `kern/tafeln.xml` sind eine fachliche
   Aenderung: Kern-`__version__` anheben, Abnahme-Protokoll des Kerns
   einhalten (bestehende Charakterisierungs-Anker muessen gruen bleiben).

### Stufe 3 — Abnahme

1. Gate O3: `python -m rechner_pipeline.gates.generation_golden --fall faelle/<fall> --generation <gen-id> --repo-root .`
   Prueft vorab, dass die Spez Projektion der A-Box ist, und vergleicht
   den Kern gegen die aus dem Quell-Rechner extrahierten
   Erwartungswerte. Beachte das Summary: `zellen_ohne_erwartungswerte`
   ehrlich weitermelden (der Quell-Rechner traegt meist nur EINEN
   Beispiel-Modellpunkt).
2. Volle Suite: `.venv/bin/python -m pytest` — bestehende Verankerungen
   duerfen sich nicht bewegen.

### Stufe 3b — Abnahme des uebernommenen Bestands (wenn Stufe 1b lief)

O3 nimmt die PARAMETRIERUNG ab, nicht den Bestand. Der Beweis einer
Bestandsmigration endet nicht beim Stichtags-Foto: das Zielsystem muss
den uebernommenen Bestand auch FORTSCHREIBEN wie das Quellsystem.
Deshalb ueber ZWEI Stichtage, und deshalb braucht es dafuer den Folge-
Abzug und das GeVo-Protokoll der Lieferung. Durchgefuehrt wird das vom
Skill `pruefe-migrationsabnahme` — uebergib an ihn, statt die Schritte
selbst zu improvisieren:

1. Gate B1 auf den uebernommenen Bestand:
   `python -m rechner_pipeline.gates.bestand_validate --portfolio <bestand>.parquet --config <config>.toml --repo-root .`
   (Schema und Invarianten; Historie/Scheiben/Ledger optional
   mitgeben, wenn der Fall sie fuehrt.)
2. Abnahmesuite je Vertrag: `qa.migrationssuite.pruefe_bestand` —
   Deckungskapital am Migrationsstichtag, Bruttojahresbeitrag am
   Migrationsstichtag (`bjb_erwartet_1`, zweite Pruefachse gegen
   Parametrierungsfehler), GeVo-Betraege zwischen den Stichtagen,
   Deckungskapital am Folgestichtag auf dem richtigen Track; die
   Zeilenzahl des Abzugs geht als `erwartete_anzahl` mit (sonst ist die
   Vollstaendigkeit der Pruefmenge ungeprueft). Beides liegt im
   Bestandsabzug vor und wird durchgereicht, sonst weist der Bericht
   Pruefluecken aus. Bibliotheks-Modul ohne CLI: die
   `VertragsPruefung`-Auftraege baut der Abnahme-Skill aus den
   Fall-Artefakten. Toleranzen kommen aus `qa` und werden NIE
   aufgeweicht.
3. Bestandsberichte vor/nach mit denselben Parametern (nur so ist der
   Vergleich fair):
   `python -m rechner_pipeline.bestand.cli_report --portfolio <bestand>.parquet --stichtage <liste> --out <ziel>.html`
4. Abnahmebericht als Entscheidungsvorlage (keine Abnahme):
   `python -m rechner_pipeline.gates.abnahmebericht --fall faelle/<fall> --suite <suite>.json --titel "..." --stichtag-1 <iso> --stichtag-2 <iso> --spec <transformation>.spec.json --transformation-ergebnis <ergebnis>.json --bestandsbericht-vor <pfad> --bestandsbericht-nach <pfad>`
   Ablage mit `--fall`:
   `<fall>/abgeleitet/berichte/migrationsabnahme.html`, Ledger unter
   `<fall>/abgeleitet/diagnostics`.

### Gate G-2 (Mensch — hier STOPPST du wieder)

`python -m rechner_pipeline.gates.gate_entscheid --gate G-2 --rolle mensch ...`
— uebergeben, nicht selbst entscheiden. Vorgelegt werden O3, die volle
Suite und, wenn ein Bestand uebernommen wurde, der Abnahmebericht mit
allen Fehlschlaegen und Befunden — vollstaendig, ohne
Stichproben-Beschoenigung.

## Abbruchkriterien (STOPP und Mensch fragen)

- Struktur-Urteil != parametrierung, oder Erweiterungsstellen offen.
- Merkmalsraum-Konflikt zwischen Quellen (Dimensions-Definitionen
  widersprechen sich).
- Tafel-Konflikt (wertverschieden bei gleichem Namen) oder
  Eingang-Integritaetsverletzung.
- Eine bestehende Kern-Verankerung (Charakterisierungs-Anker) wird rot.
- Ein Ziel-Pflichtfeld der Transformation ist aus dem Abzug nicht
  ableitbar, oder die Quelle traegt ein fachlich uebernahmepflichtiges
  Merkmal, fuer das die Ziel-Ontologie kein Feld hat (Gate G-T).
- Die Abnahmesuite meldet Befunde zur Konsistenz der Lieferung
  (fehlende Vertraege ohne Abgangs-GeVo, unbekannte GeVo-Arten) — das
  ist ein Ergebnis fuer den Menschen, kein Hindernis, das du wegraeumst.
