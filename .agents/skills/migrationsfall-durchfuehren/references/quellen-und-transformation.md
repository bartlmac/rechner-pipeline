# Quellen und Transformation — Phasenverfahren des Fallskills

Normatives Phasenverfahren des `migrationsfall-durchfuehren`-Skills für
Fallanlage und Fallauftrag, Tarifquellen -> A-Box, Bestandsabzug -> Ziel-
Ontologie und das Gate A-Q1. Die frühere Detailreferenz `ablauf-detail.md`
ist seit der Aufteilung ein Kompatibilitätsindex mit allen alten Ankern;
diese Datei ist das normative Zuhause des hier benannten Stoffs. Lade die
Abschnitte, die dein aktueller Schritt braucht, vollständig; nach einem
Kontextwechsel Auftrag, Haltpunkt und diese Referenz neu laden.

## Inhaltsverzeichnis

- [Rolle und Ziel; zwei Hälften der Lieferung](#rolle-und-ziel)
- [Referenzfall (Formvorlage, nie Werte)](#referenzfall)
- [Reihenfolge-Zwänge (was Belege rückwirkend entwertet)](#reihenfolge)
- [Stufe 0 — Fall-Arbeitsbereich](#fallanlage)
- [Stufe 0b — Fallauftrag](#fallauftrag)
- [Stufe 1 — Quellen -> A-Box](#quellen)
- [Stufe 1b — Bestandsabzug -> Ziel-Ontologie](#transformation)
- [Gate A-Q1](#aq1)
- [Wohin Teile der alten Detailreferenz gewandert sind](#weiterleitung)

<a id="rolle-und-ziel"></a>
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

<a id="referenzfall"></a>
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

<a id="reihenfolge"></a>
## Reihenfolge-Zwaenge (was Belege rueckwirkend entwertet)

**Der A-Box-Merge laeuft EINMAL.** `gates.abox_merge` baut die A-Box frisch
aus den Fragmenten; die Aufloesungen der Diskrepanzen (A-Q1) leben nur in
`abgeleitet/abox/abox.json`. Bei einer Neuzeichnung auf neuem Systemstand
werden die Pruef-Gates neu gefahren (P-Q3, P-K1, P-B1, die Abnahmen), nie
der Merge — er verweigert bei aufgeloesten Diskrepanzen den Lauf, und
`--ueberschreiben` heisst: A-Q1 wird neu entschieden (Vorfall 2026-09-07).

Zu den nachgewiesenen Vorbedingungen gehoeren: **A-Q1 und A-M1 gehen A-M4
voraus** (im Bestands-Scope auch A-M2 und A-M3), und **der Stand des
Falls ist abgenommen** (Kernstand A-K2, T-Box-Stand A-O1, Tarifwerk A-T1) — als
Pflichtrollen im A-M4-Snapshot. Hinzu kommen der geltende Fallauftrag
A-M6 und die Linie gemaess ADR-025/026. Diese Liste ist keine
vollstaendige Beschreibung aller Codepruefungen. Datenabhaengigkeiten
muessen ebenfalls eingehalten werden: Aenderungen koennen vorhandene
Belege entwerten.

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

<a id="fallanlage"></a>
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

<a id="fallauftrag"></a>
### Stufe 0b — Fallauftrag (Vorstand; hier STOPPST du, bis er gezeichnet ist)

Ein Fall wird nur mit einem gezeichneten Auftrag gefuehrt (ADR-026). Nach der
Registrierung der Lieferung legst du die Vorlage vor und haeltst an:

```bash
python -m rechner_pipeline.gates.fall_belegen auftrag --fall faelle/<fall> \
    --linie linie --zeichnungsordnung <ordnung> \
    --programmleitung-schluessel <schluessel der programmleitung> \
    --programmleitung-klasse mensch|simulation \
    [--mandat <rolle>=<mandat> ...] --auftrag "<Auftrag>"
```

(`--mandat` einmal je simulierter Rolle.)

Der Vorstand prueft `abgeleitet/auftrag/fallauftrag.md` und zeichnet
`A-M6` (`gates.gate_entscheid --gate A-M6`). Erst dann beginnt Stufe 1. Jede
Annahme im Fall setzt den geltenden Auftrag voraus und nennt ihn; der
Schluessel des Vorstands gehoert deshalb in jeden Ring
(`--freigabe-schluessel`, vor dem zeichnenden). Wird eine Quelle nachgereicht,
gilt der Auftrag nicht mehr — Vorlage neu, der Vorstand zeichnet neu.
Das Gate zeichnet nur eine Vorlage, deren Sicht am festen Ort die aus ihr
erzeugte ist (ADR-025, Nachtrag "Beleg und Sicht"); verweigert es mit Code
`sicht`, legst du die Vorlage mit demselben Kommando neu vor und haeltst
wieder an — die Sicht reparierst du nie von Hand. Endet ein Produzent mit
Code `ein_ausgabe` (etwa volle Platte), wiederholst du denselben Aufruf,
sobald die Ursache behoben ist.

<a id="quellen"></a>
### Stufe 1 — Quellen -> A-Box

1. Vorverdichtung (deterministisch, je Quelltyp):
   - XLSM: `python -m rechner_pipeline.gates.extract --repo-root . --input faelle/<fall>/eingang/<datei> --out-dir faelle/<fall>/abgeleitet/vorverdichtung/xlsm-<GEN> --adapter excel --diagnostics-dir faelle/<fall>/abgeleitet/diagnostics`
   - DOCX/PDF (Textlayer; ADR-016 — ein Scan ohne Textlayer blockiert hart, OCR extern): `python -m rechner_pipeline.quellen.tarifplan_staging --input faelle/<fall>/eingang/<datei> --out faelle/<fall>/abgeleitet/vorverdichtung/meldung-<GEN>.json`
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
   aufgeloest werden — als Kommando, nie als Skript:
   `python -m rechner_pipeline.ontologie.entscheide --fall faelle/<fall>
   --vorlaeufig --akteur <modell>/<skill>@<git-sha> --alle-offenen
   --quelle <rechner>.xlsm --begruendung "GM reproduziert den Rechner;
   fachliche Entscheidung A-Q1"` (protokolliert unter
   abgeleitet/protokoll/vorlaeufige_entscheide.jsonl) — niemals
   endgueltig durch einen Agenten.

GRENZE DIESER STUFE (bewusst, v0.1 — nenne sie, statt sie zu
verschweigen): Das QuellFragment traegt PARAMETER, keine FORMELN. Ein
Widerspruch in der Formel selbst — Meldung und Rechner bestimmen
dieselbe Groesse verschieden, etwa mit anderer Bezugsgroesse oder
anderem Index — wird deshalb nie eine Diskrepanz und kann von keinem
Gate gefunden werden; P-K1 bleibt gruen, weil er den Rechner reproduziert.
Die Identitaet der Formeln ist heute menschliche Abnahme gegen den
Tarifplan (`plv/tarifplaene/`) im Gate A-Q1. Faellt dir beim Arbeiten
eine Formelabweichung auf, gehoert sie ausdruecklich in die
A-Q1-Vorlage (Ziffer der Meldung, Rechner-Lesart, Wirkung) — sie als
"nicht extrahierbar" zu uebergehen waere ein stiller Verlust.
Begruendung und Ausbaupfad: `docs/architektur/migrations-pipeline-v01.md`
Abschnitt 8.1.

<a id="transformation"></a>
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
   Ziel-Ontologie zu erweitern ist Gate A-O1, nie deine Entscheidung.

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
    --tarif-generation TG2015 --stichtag <iso> \
    --vorgeschichte <registrierte-gevo-metadaten>.csv \
    --generation-spez klv/tg2015 \
    --anfangszustand materialisieren \
    [--red-anteile-datei <registrierte-auskunft>.csv] \
    [--red-anteil-kandidat <anteil> ...] \
    [--anker-erwartungswerte <registriert>.json] \
    --out-dir faelle/<fall>/abgeleitet/bestand
```

`--tarif-generation` ist der NAME der Generation in der Bestand-Config
(Stammspalte `tarif_generation`), nicht der Knoten. `--generation-spez` ist
Pflicht: **Die Tarifregeln stehen in der Spez, nicht am Aufruf** (ADR-024,
Nachtrag). Tarifwerk (`scheiben_mit_gamma1`, `stoab_je_baustein`,
`red_verfahren`, `tku_umfang`) und Quellverfahren (`red_verfahren` als
Lesart der Lieferung, `erhoehungssatz`, `dk_stichtag`, `formfunktion`,
`fenster`) erhebst du in Stufe 1 aus Bedingungswerk und Tarifmeldung
(Skill `extrahiere-quellfragment`), P-Q3 verlangt sie im Scope `bestand`,
und alle fuenf Kommandos der Bestandsstrecke (Uebernahme, Verankerung,
aktuarieller Test, Migrationscontrolling, Fuehrungsprobe) lesen sie aus
derselben Spez. Die frueheren Schalter (`--red-verfahren`,
`--stoab-je-baustein`, `--scheiben-mit-gamma1`, `--tku-umfang`,
`--erhoehungssatz`, `--dk-stichtag`, `--formfunktion`, `--fenster`) werden
verweigert und nennen den Abschnitt der Spez; eine andere Regel heisst:
in der A-Box belegen, P-Q3, Spez neu erzeugen — nie am Aufruf ueberstimmen.
Kennt der Tarif keinen Dynamiksatz, stellst du das ausdruecklich fest
(`nicht_belegt` mit Fundstelle); die Spez traegt dann
`quellverfahren.erhoehungssatz = "nicht_belegt"`, ein fehlender Eintrag ist
"nie erhoben" und wird verweigert. Die Kommandos der Bestandsstrecke laufen
nur in einem Fall mit Scope `bestand` (ADR-024, vierter Nachtrag).
Am Aufruf bleiben nur Eingaben (registrierte Auskunft, Ankerquelle) und
die Arbeitsannahme des Laufs (`--red-anteil-kandidat`). Die Uebernahme
rechnet den Anfangszustand mit derselben Ableitung wie die Abnahmen und
schreibt ihn in die Tabellen (Freischaltung,
dev-docs/freischaltung-uebernommener-bestand.md).
`--anfangszustand` ist Pflicht, sobald die Vorgeschichte Erhoehungen
oder Herabsetzungen traegt: `materialisieren` (Grundsumme im Stamm,
Alt-Erhoehungen als `scheiben.parquet`, Ursprungssumme beitragsfreier
Vertraege, Zugang ueber die Gesamtsumme) oder `grundvertrag` (nicht
freigeschaltet, im Beleg `uebernahme.json` namentlich ausgewiesen —
dann besteht die Fuehrungsprobe nicht, und A-M4 ist im Bestands-Scope
unmoeglich). Ab der Migration gilt das Vokabular des Zielsystems
(Grundsatzdokumentation 7.1): Welcher Vorgang eine gelieferte Absetzung
(`RED` der Quelle, Provenienzname) war, sagt EINE Regel — im
uebernommenen Tarif TG2015 (Quellverfahren `teilkuendigung`) immer die
Teilkuendigung; bei einer Quelle mit echter Herabsetzung vor dem
Beitragsende und vor einer Beitragsfreistellung die Herabsetzung, danach
die Teilkuendigung (Tarifplan KLV 7.2, Annahme B5; A2 bestaetigt).
Herabsetzung und Teilkuendigung sind zwei Geschaeftsvorfaelle (ADR-023,
Nachtrag 2026-10-01), beliebig viele je Vertrag in jeder Reihenfolge
(Tarifplan KLV 7.3). `tarifwerk.tku_umfang` nennt, welche Bausteine die
Teilkuendigung des Tarifs kuerzt (TG2015: `grundversicherung`, Entscheid
des Maintainers) — belegt, ohne Vorgabe, und weil es in der Spez steht, in
jedem Kommando der Pruefstrecke derselbe Wert. Eine Vorgeschichte aus Teilkuendigungen (auch mehreren, auch nach
Erhoehungen oder nach der Beitragsfreistellung) fuehrt zustandslos mit der
gelieferten Summe weiter; eine echte Herabsetzung der Vorgeschichte
hinterlaesst einen GETEILTEN Vertrag, den die Pruefstrecke rechnet, die
Fuehrung aber noch nicht traegt — die Uebernahme haelt dort benannt an.
Folgt eine Absetzung dynamischen Erhoehungen (Serie),
braucht die Ableitung den fortgefuehrten Anteil als Auskunft (unten);
ohne sie verweigert die Uebernahme und nennt `--red-anteile-datei`. Ein
Vertrag ohne ableitbaren Anfangszustand haelt den Lauf an (kein stiller
Grundvertrag); ein Vertrag, dessen Struktur die Auskunft traegt, ist
Pflichtziehung von A-M1, A-M2 und der Migrationssuite, A-M3 verlangt
daraus die Policen mit Vorfall im Pruefzeitraum — die Mengenregel und
der Schichtbeleg-Erzeuger stehen normativ unter
`aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`;
A-M4 prueft diese Mengen.

**Auskunft der Quelle je Police: registrieren, dann `--red-anteile-datei`.**
Der fortgefuehrte Beitragsanteil einer Alt-Herabsetzung, dessen
Beitragsgleichung entfaellt, ist eine Auskunft der abgebenden
Gesellschaft (oder, wo sie fehlt, eine dokumentierte Arbeits-Lesart des
Aktuars). Sie kommt als REGISTRIERTE Datei in den Fall — nie als
Wert am Aufruf (`--red-anteil POLNR=ANTEIL` gibt es nicht mehr; Entscheid
des Maintainers 2026-09-30): Die Zeichnung hasht den Eingang, nicht den
Aufruf. Format, CSV mit `;`: `POLNR;GEVO;DATUM;ANTEIL` und optional
`BEZUG` (Freitext: Auskunftsschreiben oder Arbeits-Lesart, wird in die
Provenienz uebernommen), eine Zeile je Police und Herabsetzung mit
`GEVO = RED`:

```
POLNR;GEVO;DATUM;ANTEIL;BEZUG
7000396;RED;01.10.2019;0.60;Arbeits-Lesart des Aktuars, Auskunft 2/4
```

Ablauf: `python -m rechner_pipeline.fall registrieren --fall <fall>
--datei <auskunft>.csv`, dann in JEDEM der fuenf Kommandos, die
Herabsetzungsanteile verarbeiten (`bestand_uebernehmen`,
`verankerung_belegen`, `aktuartest_lauf`, `migrationssuite_lauf`,
`fuehrungsprobe`), dieselbe `--red-anteile-datei <Dateiname>`. Eine nur
im Dateisystem liegende Datei verweigert das Kommando mit dem Ausweg; ein
Widerspruch in der Datei (zwei Anteile fuer dieselbe Police und dasselbe
Datum) ebenso, ein Anteil ausserhalb von 0 bis 1 (nur echte Bruchteile,
keine Prozentwerte) und eine RED-Zeile, die keinem RED-Ereignis der
Vorgeschichte entspricht (Police, und mit DATUM das Datum im selben
Wortlaut wie dort) — eine solche Zeile bliebe ohne Wirkung und stuende
doch im Beleg. Der Beleg nennt die Datei mit Hash unter seinen Eingaben;
Uebernahmebeleg, Schichtbeleg, Fuehrungsprobe, aktuarieller Test und
Migrationscontrolling fuehren sie zusaetzlich als `red_anteile_datei`
(Name, SHA-256, Bezug je Police; `null`, wenn keine genannt wurde).
Ein Lauf mit `--schicht` (`aktuartest_lauf`, `migrationssuite_lauf`,
`fuehrungsprobe`) rechnet diese Aussage gegen die Eingaben des
Schichtbelegs nach UND haelt sie gegen seine eigene Auskunft: Die Schicht
ist auf der Anfangslage EINER Auskunft verankert, ein Lauf mit einer
anderen (oder ohne) verweigert mit dem Ausweg — dieselbe
`--red-anteile-datei` an allen Kommandos. Der Abnahmebericht (A-M4)
verlangt das Feld in der Suite und haelt Suite und Fuehrungsprobe auf
derselben Auskunft. Die Anteile wirken mit `--vorgeschichte` (bei der
Uebernahme mit `--anfangszustand materialisieren`); ohne sie haelt das
Kommando an, statt die Auskunft still zu ueberlesen.

Es schreibt `bestand.parquet`, `historie.parquet` und `ledger.parquet`
deterministisch ueber `bestand/parquet_io.write_portfolio` und setzt die
Statusregel von oben um: Stamm bei Beginn, Folgezustaende in der
Historie. `--vorgeschichte` liest die REGISTRIERTE Metadatenliste der
Geschaeftsvorfaelle vor dem Stichtag; ohne sie ist der
Verankerungszeitpunkt nicht bestimmbar.

**Fortschreibung, Bestandsbericht der Stufe 1b und Freischaltung:** Der
uebernommene Bestand lebt in den Buechern weiter. Normativ stehen die
Fortschreibung (`cli_fortschreibung --uebernahme`, eigener und
uebernommener Bestand in EINEM Lauf), der Bestandsbericht der Stufe 1b
(`--berichtsstichtag` statt `--bis`/`--stichtag`, eigener separierter
Aufruf, Anker `fortschreibung`) und die Freischaltung
(Config-Tarifwerk, Schichtbeleg, Fortschreibung, Fuehrungsprobe) in
`pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md`.

**Verankerungsattribute.** Traegt die transformierte Zeile ``monate_ta``
und ``dk_ta`` (der letzte exakte Rechenpunkt des Quellsystems und der
dort gelieferte Wert, Grundsatzdokumentation 9.12), schreibt die
Uebernahme zusaetzlich ``verankerung.parquet`` — Zustand und
Verweildauer am t_a leitet sie aus der registrierten Vorgeschichte ab.
Alle Vertraege oder keiner; eine halbe Tabelle liesse die
Korrekturschicht den Rest fuer verankerungsfrei halten. Die
Korrekturschicht und der aktuarielle Test koennen die Attribute damit
als VERTRAGSMERKMALE lesen, statt sie je Lauf aus den Erwartungswerten
zu rekonstruieren.

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
**Freischaltung (Schritt vor A-M4)** — normativ in `pruefe-
migrationscontrolling/references/fuehrung-und-berichtspaar.md`: vier
Handgriffe, dann stellt die Fuehrungsprobe den gefuehrten Bestand gegen
die Pruefstrecke.

<a id="aq1"></a>
### Gate A-Q1 (Mensch — hier STOPPST du und uebergibst)

Vorlegen: `abgeleitet/fachspez/<gen>.md` (Generator:
`spez.fachspez.speichere_fachspez`), Diskrepanzenliste, Coverage — und,
wenn Stufe 1b lief, die offenen Konflikte der TransformationsSpec, die
Befunde der Anwendung und jede beim Lesen aufgefallene Formelabweichung
(siehe Grenze der Stufe 1).
Der Mensch entscheidet mit
`python -m rechner_pipeline.ontologie.entscheide --zeichnungsordnung
<externe-ordnung> --freigabe-schluessel <externe-datei> ...` und
snapshottet mit `python -m rechner_pipeline.gates.gate_entscheid
--gate A-Q1 --zeichnungsordnung <externe-ordnung> --freigabe-schluessel
<externe-datei> ...` — die zeichnende Rolle (`mensch/aktuariat`)
wird aus dem Schluessel bestimmt, nicht behauptet (ADR-018).
Nach dokumentierter menschlicher Entscheidung der Mappingkonflikte folgt
die autorisierte Uebertragung in die Spec und der menschliche Abgleich
gemaess `transformiere-quellbestand`. Danach Validierung/Anwendung und
betroffene Belege neu erzeugen. Der A-Q1-Snapshot bindet die A-Box,
nicht technisch die Entscheidungsfelder der Spec; deren Hashbindung
im Transformationsergebnis/A-M4 ersetzt diesen menschlichen Abgleich nicht.
Du selbst kannst ein Gate nur ABLEHNEN: `--entscheid abgelehnt --rolle
agent/programmleitung` dokumentiert den Zwischenstand.
Der Freigabeschluessel gehoert ausserhalb des Falls und ausserhalb des
Agentenzugriffs in die Autoritaetsumgebung des Menschen (mindestens 32
kryptografisch zufaellige Byte, POSIX 0600, genau ein Hardlink).

**Die Linie ist Pflicht** (ADR-025, Nachtrag 2026-10-01): Jeder Entscheid-Aufruf nennt `--linie <linienbereich>`; gezeichnet wird nur unter der Spitze ihrer Ordnungslinie (`--zeichnungsordnung` ist die Ordnung der Spitze), und jede Vorbedingung wird gegen die Ordnung gelesen, unter der sie gezeichnet wurde. Ohne Linie verweigert das Gate mit Ausweg; eine Ordnung mit `"*"` kommt nicht in die Linie und zeichnet deshalb nicht mehr.

Zeichnet in der Vorzeige eine SIMULIERTE menschliche Rolle (Schluesselklasse `simulation` in der Zeichnungsordnung), ist `--mandat <datei>` Pflicht: Das Gate verweigert die Annahme ohne Mandat (ADR-018). Das Mandat ist das Dokument der Regie, unter dem die Rolle handelt; sein Hash steht mitsigniert im Snapshot.

**Zeichnungsordnung (ADR-018/025/026).**
Menschliche Rollen zeichnen ausschliesslich die ihnen zugeordneten Gates;
Agentenrollen bereiten vor und koennen nur ablehnen. Der Vorstand zeichnet
Ordnung und Fallauftrag, das Aktuariat A-Q1/A-M1..M4 und A-T1,
die Architektur A-O1, der Rechenkern A-K2, der Betrieb A-B1..B3.
JEDER Entscheid-Aufruf nennt Linie und `--zeichnungsordnung <datei>`: ein JSON
AUSSERHALB des Falls, das Rollen an Schluessel-Fingerabdruecke und Gates
an Rollen bindet. Mit Ordnung prueft gate_entscheid die Annahme UND jede
Vorbedingungs-Annahme der Kette; die Rolle wandert mitsigniert in den
Snapshot (`zeichnung`). Zwei Rollen mit demselben Schluessel sind ein
Fehler. Der Mensch steigt nur nach Abbruchkriterium ein: klarer
Systemfehler (durch Agenten/Operatoren nicht heilbar), Zirkelreferenz,
drei fruchtlose Q&A-Schleifen zum selben Thema, Budget ueberschritten. DU liest,
erzeugst oder kopierst ihn nicht; der Mensch fuehrt den
Annahmeaufruf aus. Bei Rotation werden alte Schluessel zuerst und der aktive
zuletzt mit wiederholtem Flag uebergeben. Als Agent darfst du AUSSCHLIESSLICH
ablehnen (--rolle agent/programmleitung, dokumentierter Zwischenstand). Die Annahme
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

<a id="weiterleitung"></a>
## Wohin Teile der alten Detailreferenz gewandert sind

- Reihenfolge-Zwaenge und Belegentwertung: dieser Abschnitt oben.
- Spezifikation und Parametrierung (Spez, P-K1, Stand A-K2/A-O1/A-T1):
  `spezifikation-und-parametrierung.md`.
- Abnahmenkoordinierung A-M1 bis A-M4 samt A-M4-Gate und Fallabbruch:
  `abnahmen-und-berichte.md`; Schichtbeleg und Pflichtmengen:
  `aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`;
  Fortschreibung, Freischaltung und Berichtspaar:
  `pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md`.
- Zugang nach A-M4: `betriebsuebergabe.md`; das vollstaendige Verfahren
  bleibt ausschliesslich im Skill `uebernehme-migrationsbestand`.
