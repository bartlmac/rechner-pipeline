---
name: migrationsfall-durchfuehren
description: >-
  Run a complete migration case through the ontology pipeline (Stufe 1 Quellen->A-Box
  plus Bestandsabzug->Transformation, Stufe 2 A-Box->Spez->Kern-Parametrierung, Stufe 3
  Golden-Master-Abnahme plus aktuarieller Test und Bestands-Controlling ueber zwei
  Stichtage), including the human gates A-Q1/A-M1/A-M4 and their P9 snapshots. Trigger when the user asks to migrate a new
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

`faelle/archiv/baldrian-uebernahme-2026-08-18` ist der Praezedenzfall:
die Baldrian Leben (fiktives abgebendes Unternehmen) liefert Tarifmeldung
und Tarifrechner, die PLV uebernimmt den KLV-Bestand (TG2012 -> TG2015).

Er deckt nur Stufe 1 ab: Fragmente, Vorverdichtung, TransformationsSpec
und vier Gate-Ledger. A-Box, Spez, Fachspez, Berichte, Bestand und
Entscheide fehlen — als Formvorlage fuer Stufe 2, 3 und 3b ist er leer.
Seine Spec passt ausserdem nicht mehr auf die heutige Lieferung
(abweichender `quelle_sha256`), Werte waeren also auch dann nicht
uebertragbar, wenn man es duerfte.

Er dient AUSSCHLIESSLICH als Formvorlage: Artefakt-FORMATE und
Verzeichnisstruktur nachschlagen, also wie ein Fragment, eine Spez oder
ein A-Q1-Dokument aufgebaut ist. Werte, Lesarten, Zuordnungen oder
Entscheidungen einer anderen Migration werden NIE uebernommen — jeder
Fall wird aus seinen eigenen Quellen belegt, auch wenn er dieselbe
Generation betrifft. Ein Wert, den du nicht in deiner Quelle gefunden
hast, gehoert nach `nicht_belegt`, nicht aus dem Archiv abgeschrieben.

Untersagt der Auftraggeber den Zugriff auf archivierte Faelle, gilt
das Verbot ohne Ausnahme — auch fuer Formatfragen. Dann die Formate aus
dem generierten Schema (`model_json_schema()`) und den Docstrings der
beteiligten Module ableiten und im Zweifel den Menschen fragen.

## Reihenfolge-Zwaenge (was Belege rueckwirkend entwertet)

Erzwungen ist im Code nur zweierlei: **A-Q1 und A-M1 gehen A-M4
voraus** — beide als Pflichtrollen im A-M4-Snapshot. Alles andere ist
Datenabhaengigkeit ohne Gate-DAG; wer sie missachtet, bekommt keinen
Fehler, sondern einen Beleg, der spaeter nicht mehr gilt.

Drei Dinge entwerten rueckwirkend, was schon gezeichnet war:

*Eine neu registrierte Quelle.* A-Q1 und A-M1 binden `eingang.json`
ueber ihre Artefakt-Hashes, und A-M4 vergleicht diesen Hash in beiden
Snapshots. Wer nach dem A-Q1-Entscheid noch eine Datei registriert —
etwa eine nachgereichte aktuarielle Notiz —, muss A-Q1 und A-M1 neu
zeichnen lassen. Registriere deshalb alles, was die Lieferung hergibt,
BEVOR du zeichnest; kommt spaeter etwas nach, ist die Neuzeichnung der
Preis und keine Panne.

*Jede Codeaenderung und jeder Tafel-Import.* Der Systemstand hasht ALLE
`.py`- und `.xml`-Dateien des installierten Pakets — ein Tafel-Import
schreibt nach `kern/tafeln.xml`, ein Testfix aendert eine `.py`. Danach
tragen P-K1-Belege und menschliche Snapshots einen Systemstand, den
A-M4 als abweichend zurueckweist. Also: erst alle Kern-, Tafel- und
Codeaenderungen abschliessen, dann P-K1, dann die menschlichen Gates.
Wer waehrend der Abnahmephase noch einen Bug fixt, faengt die Abnahme
von vorn an.

*Jede Diskrepanz-Aufloesung.* `ontologie.entscheide` schreibt die A-Box
neu. Jede Annahme prueft danach das P-Q3-Ledger gegen den AKTUELLEN
Stand von `eingang.json` und `abox.json`. Nach jeder Aufloesung laeuft
P-Q3 also erneut, sonst scheitert der naechste Entscheid an
"Gate P-Q3 verletzt den Ledger-/Provenienzvertrag".

Dazu drei Stellen, an denen ein Pfad ein VERTRAG ist und kein
Vorschlag:

- Die Vorverdichtung muss unter
  `<fall>/abgeleitet/vorverdichtung/xlsm-<GENERATION GROSS>` liegen,
  sonst findet P-K1 sie nicht.
- A-M1 verlangt im Bestands-Scope exakt
  `<fall>/abgeleitet/berichte/aktuartest.json` und `.html` sowie
  `<fall>/abgeleitet/diagnostics/aktuartest.gate.json`. Wer `--out`
  oder `--bericht` umbiegt, macht A-M1 unentscheidbar.
- `gates.bestand_validate` schreibt seinen Ledger per Vorgabe nach
  `./runs/diagnostics`. A-M4 sucht ihn unter
  `<fall>/abgeleitet/diagnostics`. Ohne `--diagnostics-dir` fehlt der
  P-B1-Pflichtbeleg.

Und eine Reihenfolge, die man leicht falsch herum macht: Der
**Abnahmebericht** bindet Eingang, A-Box und Systemstand mit. Er
entsteht deshalb NACH der letzten A-Box-Aenderung, nicht davor.

## Ablauf

### Stufe 0 — Fall-Arbeitsbereich

```bash
python -m rechner_pipeline.fall anlegen --fall faelle/<fall> --scope <tarif|bestand> --beschreibung "..."
python -m rechner_pipeline.fall registrieren --fall faelle/<fall> --datei <quelle>   # je Quelle
python -m rechner_pipeline.fall status --fall faelle/<fall>
```

Regeln: Eingang ist nicht regenerierbar und wird nie aufgeraeumt;
Konflikte beim Registrieren (gleicher Name, anderer Inhalt) sind ein
Vorgang fuer den Menschen, kein Overwrite.
Der Scope ist ein fachlicher Entscheid: `tarif` ohne Bestandsuebernahme,
`bestand` mit Bestandsabzug/-uebernahme. Nie aus zufaellig vorhandenen Dateien
erraten oder spaeter zur Umgehung einer Gate-Pflicht umetikettieren.

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
   bindet die A-Box an die Fragmente, Gate P-Q3 rechnet die Kette nach.
   Widersprueche werden Diskrepanz-Objekte — erwuenscht.
5. Gate P-Q3: `python -m rechner_pipeline.gates.abox_validate --fall faelle/<fall> --repo-root .`
   Blockt bei Coverage-Luecken und offenen Diskrepanzen. Fuer den
   Weiterbau duerfen Diskrepanzen VORLAEUFIG zur Rechner-Lesart
   aufgeloest werden (`loese_diskrepanz_auf(..., vorlaeufig=True)`,
   Begruendung: der GM reproduziert den Rechner; fachliche Entscheidung
   A-Q1) — niemals endgueltig durch einen Agenten.

GRENZE DIESER STUFE (bewusst, v0.1 — nenne sie, statt sie zu
verschweigen): Das QuellFragment traegt PARAMETER, keine FORMELN. Ein
Widerspruch in der Formel selbst — Meldung und Rechner bestimmen
dieselbe Groesse verschieden, etwa mit anderer Bezugsgroesse oder
anderem Index — wird deshalb nie eine Diskrepanz und kann von keinem
Gate gefunden werden; P-K1 bleibt gruen, weil er den Rechner reproduziert.
Die Identitaet der Formeln ist heute menschliche Abnahme gegen den
Tarifplan (`docs/tarifplaene/`) im Gate A-Q1. Faellt dir beim Arbeiten
eine Formelabweichung auf, gehoert sie ausdruecklich in die
A-Q1-Vorlage (Ziffer der Meldung, Rechner-Lesart, Wirkung) — sie als
"nicht extrahierbar" zu uebergehen waere ein stiller Verlust.
Begruendung und Ausbaupfad: `docs/architektur/migrations-pipeline-v01.md`
Abschnitt 8.1.

### Stufe 1b — Bestandsabzug -> Ziel-Ontologie (wenn die Lieferung einen enthaelt)

Der Bestandsabzug laeuft NICHT durch die Fragment-Extraktion: Stufe 1
uebersetzt Tarifgroessen in die A-Box, hier werden Vertraege in das
Ziel-Datenmodell uebersetzt. Beides ist Stufe 1, weil beides aus einer
Quelle liest und beides an A-Q1 haengt.

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
   LEER sein, danach
   `gates.transformation_anwenden.wende_an(spec, fall_pfad)`. `wende_an` loest
   `spec.quelle_datei` selbst ueber das Fallregister auf, liest die zu
   transformierenden Zeilen aus diesem registrierten Eingang und prueft
   SHA-256 der Spec sowie deren physische
   Quellspalten erneut und gibt
   `(zeilen, befunde)` zurueck und laesst jede Zeile mit Befund WEG —
   wer nur die Zeilen nimmt, migriert stillschweigend weniger
   Vertraege. Zaehle die Klammer laut: Zeilen im Abzug -> transformierte
   Zeilen -> Befunde, und trag sie in die A-Q1-Vorlage und den
   Abnahmebericht (`--transformation-ergebnis`).
   Das persistierte Ergebnis ist ein JSON-Objekt mit exakt
   `schema_version`, `spec_sha256`, `quelle_sha256`, `quellspalten`,
   `ziel_datei` (Fall-relativ), `ziel_sha256`, `zeilen_quelle`,
   `zeilen_ziel` und `befunde`. Der Abnahmebericht rechnet Spec-Abdeckung
   und alle vier Hashbindungen nach; handgeschriebene Kurzsummaries sind im
   Bestands-Scope kein Beleg.

   Als Kommando:
   `python -m rechner_pipeline.gates.transformation_anwenden --fall faelle/<fall> --spec <spec>.json --anwenden --zeilen <zeilen>.json`

   Es laeuft ZWEIMAL. Zuerst so, um die Zeilen fuer die Uebernahme zu
   erzeugen. Nach der Uebernahme erneut mit
   `--ziel <bestand>.parquet --ergebnis <ergebnis>.json`, weil
   `ziel_datei` und `ziel_sha256` auf den fertigen Bestand zeigen — den
   es beim ersten Lauf noch nicht gibt. Ohne `--ziel` bleiben beide leer,
   und A-M4 verwirft das Ergebnis.
4. Abzugsabgleich, wo der Abzug eine offene Diskrepanz entscheiden kann
   (`qa.abzugsabgleich.gleiche_ab`): er belegt eine Lesart nur, wenn
   GENAU eine zu den gelieferten Werten passt, und niemals gegen die
   Meldung — eine verworfene Meldungs-Lesart bleibt immer beim Menschen
   (`bereite-fachkonflikt-auf`).
5. Offene Konflikte der Spec und die Befundliste gehen mit an A-Q1. Ein
   Ziel-Pflichtfeld, das die Quelle nicht hergibt, ist ein STOPP: die
   Ziel-Ontologie zu erweitern ist Gate A-K1, nie deine Entscheidung.

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
beitragsfreien Track und sein PEX-Jahr; ein PEX im Stamm weist Gate P-B1
zurueck (`status_code ausserhalb ('POL',)`).

Diesen Zusammenbau macht ein Kommando, kein fallweises Skript:

```
python -m rechner_pipeline.gates.bestand_uebernehmen \
    --fall faelle/<fall> --zeilen <zeilen>.json \
    --tarif-generation klv/tg2015 --stichtag <iso> \
    --vorgeschichte <registrierte-gevo-metadaten>.csv \
    --generation-spez klv/tg2015 \
    --out-dir faelle/<fall>/abgeleitet/bestand
```

Es schreibt `bestand.parquet`, `historie.parquet` und `ledger.parquet`
deterministisch ueber `bestand/parquet_io.write_portfolio` und setzt die
Statusregel von oben um: Stamm bei Beginn, Folgezustaende in der
Historie. `--vorgeschichte` liest die REGISTRIERTE Metadatenliste der
Geschaeftsvorfaelle vor dem Stichtag; ohne sie ist der
Verankerungszeitpunkt nicht bestimmbar.

**Fortschreibung.** Der uebernommene Bestand lebt in den Buechern des
aufnehmenden Unternehmens weiter — er altert, storniert, laeuft ab. Das
faehrt `bestand.cli_fortschreibung` auf dem uebernommenen Stamm; die
Engine setzt am Bestandszugang an und im Zustand, den der Vertrag
mitbringt (ADR-015). Die Buchungen der Uebernahme selbst (Zugang, bei
beitragsfrei ankommenden Vertraegen die Umbuchung) stehen bereits im
Ledger und werden dem Fortschreibungs-Ledger vorangestellt. Ohne diesen
Schritt fehlen den uebernommenen Vertraegen die Abgangsbuchungen, und
die Bestandsbewegung des Gesamtbestands geht nicht auf.

**Tarifzellen.** Fuehrt die Spez mehr als eine Zelle, kommen zwei
weitere Ausgaben dazu: `merkmale.parquet` (je Vertrag und Dimension die
gewaehlte Auspraegung — die Nebentabelle zur Zellwahl) und
`generation-zellen.toml` (die Rechnungsgrundlagen der Zellen als
Abschnitt fuer die Bestand-Config). Beide gehoeren zusammen: die eine
sagt WELCHE Zelle, die andere WAS darin gilt. Der Abschnitt wird in die
Config uebernommen, der Bericht bekommt `--merkmale
<...>/merkmale.parquet`. Ohne diese Kette bewertet der Bericht alle
uebernommenen Vertraege mit EINEM Parametersatz — bei der TG2015 mit der
Nichtrauchertafel auch die Raucher. Eine aufgeteilte Generation ohne
Merkmalstabelle bricht die Bewertung hart ab; sie faellt nicht still auf
den gemeinsamen Rumpf zurueck, denn der gilt fuer keinen Vertrag.

### Gate A-Q1 (Mensch — hier STOPPST du und uebergibst)

Vorlegen: `abgeleitet/fachspez/<gen>.md` (Generator:
`spez.fachspez.speichere_fachspez`), Diskrepanzenliste, Coverage — und,
wenn Stufe 1b lief, die offenen Konflikte der TransformationsSpec, die
Befunde der Anwendung und jede beim Lesen aufgefallene Formelabweichung
(siehe Grenze der Stufe 1).
Der Mensch entscheidet mit
`python -m rechner_pipeline.ontologie.entscheide --rolle mensch ...` und
snapshottet mit `python -m rechner_pipeline.gates.gate_entscheid
--gate A-Q1 --rolle mensch --freigabe-schluessel <externe-datei> ...`.
Der Freigabeschluessel gehoert ausserhalb des Falls und ausserhalb des
Agentenzugriffs in die Autoritaetsumgebung des Menschen (mindestens 32
kryptografisch zufaellige Byte, POSIX 0600, genau ein Hardlink). DU liest,
erzeugst oder kopierst ihn nicht; der Mensch fuehrt den
Annahmeaufruf aus. Bei Rotation werden alte Schluessel zuerst und der aktive
zuletzt mit wiederholtem Flag uebergeben. Als Agent darfst du AUSSCHLIESSLICH
ablehnen (--rolle agent, dokumentierter Zwischenstand). Die Annahme
rechnet ihre Vorbedingungen: das P-Q3-Ledger ist schema-, Gate-, Command-,
Versions- und hashrollengenau an den aktuellen A-Box-Stand gebunden; P9
validiert Snapshot-Schema, Vollhash-Dateiname, Freigabesignatur und die
zyklenfreie Kette mit genau einer Spitze. A-M4 verlangt zusaetzlich fuer exakt
jede Generation der A-Box einen inhaltsadressierten gruenen P-K1-Beleg desselben
A-Box- und Systemstands, einen geltenden signierten A-Q1-Annahme-Snapshot
   desselben Stands UND einen geltenden signierten A-M1-Annahme-Snapshot
   (aktuarielle Abnahme — A-M1 geht A-M4 zwingend voraus, ADR-010). Die
   Pflichtbelege werden JE GATE aus dem Scope abgeleitet
   (`fall.BELEGROLLEN`): Im Scope `bestand` verlangt A-M1 Testergebnis und
   Bericht des aktuariellen Tests, A-M4 zusaetzlich die Belege fuer P-B1,
   vollstaendige Suite und Abnahmebericht; ein Scope `tarif` verlangt
   beides nicht.

### Stufe 2 — A-Box -> Spez -> Kern

1. Spez: `spez.erzeugen.baue_spez(abox, <gen-id>, referenz_id=<vorgaenger>)`
   + `spez.validierung.speichere_spez`. Das Struktur-Urteil
   (Parametrierung vs. neue Produktfamilie) wird BERECHNET — nimm es
   ernst: `neue_produktfamilie` oder offene Erweiterungsstellen heissen
   STOPP und Mensch fragen (T-Box-/Kern-Erweiterung ist Gate A-K1).
2. Tafel-Import: `python -m rechner_pipeline.quellen.tafel_import --fall faelle/<fall> --generation <gen-id> --dry-run`,
   pruefen, dann scharf. Konflikte (wertverschiedene Tafeln gleichen
   Namens) sind ein Provenienz-Problem fuer den Menschen.
3. Kern-Aenderungen: eine neue Generation ist PARAMETRIERUNG — kein
   Formel-Code. Neue Tafeln in `kern/tafeln.xml` sind eine fachliche
   Aenderung: Kern-`__version__` anheben, Abnahme-Protokoll des Kerns
   einhalten (bestehende Charakterisierungstests muessen gruen bleiben).

### Stufe 3 — Abnahme

1. Gate P-K1: `python -m rechner_pipeline.gates.generation_golden --fall faelle/<fall> --generation <gen-id> --repo-root .`
   Prueft vorab, dass die Spez Projektion der A-Box ist, und vergleicht
   den Kern gegen die aus dem Quell-Rechner extrahierten
   Erwartungswerte. Ein gruener Lauf schreibt neben dem Latest-Ledger
   einen unveraenderlichen, inhaltsadressierten Beleg fuer diese Generation;
   alle A-Box-Generationen muessen auf demselben A-Box- und Systemstand
   gelaufen sein. Beachte das Summary: `zellen_ohne_erwartungswerte`
   ehrlich weitermelden (der Quell-Rechner traegt meist nur EINEN
   Beispiel-Modellpunkt).
2. Volle Suite: `.venv/bin/python -m pytest` — bestehende Referenzwerte
   duerfen sich nicht bewegen.

### Stufe 3b — Pruefung des uebernommenen Bestands (wenn Stufe 1b lief)

P-K1 nimmt die PARAMETRIERUNG ab, nicht den Bestand. Der uebernommene
Bestand laeuft durch ZWEI getrennte Pruefebenen mit ZWEI menschlichen
Gates in erzwungener Reihenfolge (ADR-010):

ZUERST der AKTUARIELLE TEST (Skill `aktuartest-durchfuehren`, Gate
A-M1): je Vertrag am eigenen Verankerungszeitpunkt, am Rechenpunkt ohne
Interpolation, ohne Summation — auf einer belegten Stichprobe
(`qa.stichprobe`, v0: `vollbestand`). Die Engine
`qa.aktuarieller_test` schreibt das Ergebnis-JSON, das Gate
`gates.aktuartest` rendert die A-M1-Vorlage. Der Verantwortliche Aktuar
entscheidet A-M1 (`gate_entscheid --gate A-M1`); ohne geltende
A-M1-Annahme ist A-M4 unmoeglich.

DANACH das MIGRATIONSCONTROLLING (Skill `pruefe-migrationscontrolling`,
Gate A-M4): der Beweis einer Bestandsmigration endet nicht beim
Stichtags-Foto — das Zielsystem muss den uebernommenen Bestand auch
FORTSCHREIBEN wie das Quellsystem. Deshalb ueber ZWEI Stichtage und
ueber JEDEN Vertrag, und deshalb braucht es dafuer den Folge-Abzug und
das GeVo-Protokoll der Lieferung. Uebergib an die beiden Skills, statt
die Schritte selbst zu improvisieren:

1. Gate P-B1 auf den uebernommenen Bestand:
   `python -m rechner_pipeline.gates.bestand_validate --portfolio <bestand>.parquet --config <config>.toml --repo-root . --diagnostics-dir faelle/<fall>/abgeleitet/diagnostics
   (trägt der Bestand Folgezustände — `status_id > 1` —, zusätzlich
   `--historie <journal>.parquet`: P-B1 prüft den Stammzustand gegen den
   jüngsten Journalstand, ADR-011)`
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
   Pruefluecken aus und blockiert. Bibliotheks-Modul ohne CLI: die
   `VertragsPruefung`-Auftraege baut das Kommando
   `python -m rechner_pipeline.gates.migrationssuite_lauf --fall faelle/<fall> --generation klv/tg2015 --abzug-1 <registriert>.csv --abzug-2 <registriert>.csv --gevo-protokoll <registriert>.csv --bestand <bestand>.parquet --stichtag-1 <iso> --stichtag-2 <iso>`
   aus den Fall-Artefakten; die Spaltennamen der Lieferung sind
   Parameter (`--spalte-*`), keine Systemeigenschaft. Toleranzen kommen
   aus `qa` und werden NIE aufgeweicht. Das persistierte Suite-JSON bindet zusaetzlich
   `stichtag_1`, `stichtag_2`, `bestand_sha256` und den Systemstand; im
   Bestands-Scope muss `vollstaendig_geprueft=true` sein.
3. Bestandsberichte vor/nach mit denselben Parametern (nur so ist der
   Vergleich fair):
   `python -m rechner_pipeline.bestand.cli_report --portfolio <bestand>.parquet --stichtage <liste> --out <ziel>.html`
4. Abnahmebericht als Entscheidungsvorlage (keine Abnahme):
   `python -m rechner_pipeline.gates.abnahmebericht --fall faelle/<fall> --suite <suite>.json --titel "..." --stichtag-1 <iso> --stichtag-2 <iso> --spec <transformation>.spec.json --transformation-ergebnis <ergebnis>.json --bestandsbericht-vor <pfad> --bestandsbericht-nach <pfad>`
   Alle vier nach der Suite genannten Artefakte sind Pflicht. Zeilenverlust,
   Transformationsbefunde und nicht entschiedene Konflikte erzeugen einen roten
   Bericht und einen blockierenden Exit-Code. Suite, Pflichtartefakte,
   HTML-Ausgabe und Gate-Ledger muessen paarweise verschiedene Dateien sein;
   Pfad- und Hardlink-Aliase sind keine getrennten Belege.
   Ablage mit `--fall`:
   `<fall>/abgeleitet/berichte/migrationsabnahme.html`, Ledger unter
   `<fall>/abgeleitet/diagnostics`. Das gruene
   `abnahmebericht.gate.json` bindet P-B1, Suite und HTML-Bericht an Eingang,
   A-Box, System, den von P-B1 benannten Bestand und beide Stichtage; ohne diese
   konsistente Bindung darf A-M4 im Bestands-Scope nicht angenommen werden.

### Gate A-M4 (Mensch — hier STOPPST du wieder)

`python -m rechner_pipeline.gates.gate_entscheid --gate A-M4 --rolle mensch
--freigabe-schluessel <externe-datei> ...`
— uebergeben, nicht selbst entscheiden. A-M4 verlangt den geltenden,
signierten A-M1-Snapshot desselben Stands als Vorgaenger und pinnt ihn
als Rolle `am1_snapshot` (aktuarielle vor finanzieller Abnahme,
ADR-010). A-M4 liest den Scope aus `fall.json`
und leitet seine exakte Pflichtbelegmenge je Gate aus dem Fall-Scope ab. Im
Bestands-Scope werden das Abnahme-Ledger, jedes von ihm gebundene Artefakt und
das von P-B1 benannte Portfolio gegen die aktuellen Bytes nachgehasht. P-B1 und
Suite werden semantisch erneut validiert; der HTML-Bericht wird aus der Suite
deterministisch neu gerendert und bytegenau verglichen. Vorgelegt wird alles
vollstaendig, ohne Stichproben-Beschoenigung.

## Abbruchkriterien (STOPP und Mensch fragen)

- Struktur-Urteil != parametrierung, oder Erweiterungsstellen offen.
- Merkmalsraum-Konflikt zwischen Quellen (Dimensions-Definitionen
  widersprechen sich).
- Tafel-Konflikt (wertverschieden bei gleichem Namen) oder
  Eingang-Integritaetsverletzung.
- Ein bestehender Charakterisierungstest des Kerns (eingefrorene Referenzwerte) wird rot.
- Ein Ziel-Pflichtfeld der Transformation ist aus dem Abzug nicht
  ableitbar, oder die Quelle traegt ein fachlich uebernahmepflichtiges
  Merkmal, fuer das die Ziel-Ontologie kein Feld hat (Gate A-K1).
- Die Controlling-Suite (`qa.migrationssuite`) oder der aktuarielle
  Test melden Befunde zur Konsistenz der Lieferung
  (fehlende Vertraege ohne Abgangs-GeVo, unbekannte GeVo-Arten) — das
  ist ein Ergebnis fuer den Menschen, kein Hindernis, das du wegraeumst.
