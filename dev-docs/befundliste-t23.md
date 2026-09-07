# Befundliste — Runde T23 (Triage gegen ebenen b5fa737)

dev-session, 2026-09-07. Externer DORA-Review (ToDo 23) zu PR #14 / `ebenen`,
geprueft b5fa737 gegen origin/main 947dd76. Reviewer-Urteil: nicht mergebereit,
sieben hohe und zwei mittlere Befunde; Kernkritik: die T22-Reparaturen treffen
jeweils den Hauptpfad und lassen die Klasse offen, neue Positivtests frieren
zu schwache Praedikate ein.

## Methode

Je Befund ein Pruefagent (Sonnet, hohe Sorgfalt), ausschliesslich lesend per
`git show`/`git grep` auf dem reviewten Stand b5fa737; Arbeitsbaum unangetastet.
Sieben Fragen je Befund: bestaetigt? konkreter Schaden? Schwere-Zustimmung?
verletzte KLASSEN-Invariante? WEITERE STELLEN mit demselben Muster? Fix-Umfang
zum Schliessen der Klasse (nicht der Stelle) samt fangendem Test?
Abweichung auf freischaltung f7c545d?

## Ergebnis auf einen Blick

| Befund | Reviewer | Urteil | Schwere-Zustimmung | weitere Stellen | Umfang | freischaltung |
|---|---|---|---|---|---|---|
| T23-01 | hoch | bestaetigt | ja | 8 | L | identisch |
| T23-02 | hoch | bestaetigt | ja (strukturelle Zeitbombe) | 6 | M | identisch |
| T23-03 | hoch | bestaetigt | ueberwiegend ja | 0 | M | identisch |
| T23-04 | hoch | bestaetigt | ja | 4 | M | identisch |
| T23-05 | hoch | bestaetigt | ja | 4 | S-M | identisch |
| T23-06 | hoch | bestaetigt | ja | 4 | M | identisch |
| T23-07 | hoch | teilweise | ja, mit Einschraenkung | 4 | M (eng) / L (voll) | identisch |
| T23-08 | mittel | bestaetigt | mittel bestaetigt (nicht hoch) | 0 | M | identisch |
| T23-09 | mittel | bestaetigt | eher HOEHER als mittel | 1 | M | identisch |

## Kernbefund

1. Acht von neun Befunden sind am Code BESTAETIGT, einer (T23-07) TEILWEISE.
   Kein Befund ist unbegruendet.
2. Die Prozess-Kritik des Reviewers ist am Code bestaetigt: in sieben von neun
   Befunden fand die Suche nach demselben Muster WEITERE Stellen ueber die
   Reviewer-Zitate hinaus — zusammen 31 zusaetzliche Fundstellen. Die
   genannte Stelle zu flicken haette diese stehen lassen.
3. ALLE Fehlerstellen sind auf freischaltung f7c545d byte-identisch (die
   Diffs dort betreffen andere Themen). Ein Fix auf ebenen dient beiden
   Branches; keine doppelte Arbeit.
4. Abweichungen von der Reviewer-Schwere: T23-08 ist "mittel", nicht hoch
   (kein Artefakt wird korrumpiert, die Sperre laeuft nur nicht bei jedem
   Aufruf). T23-09 ist eher HOEHER als mittel: derselbe ungebundene Pfad
   trifft auch `--mandat` — das Mandatsdokument selbst hat keine
   Raumbindung. T23-07 ist nur teilweise: das Rebinding von
   `__import__`/`import_module` umgeht den Detektor real; getattr- und
   sys.modules-Zugriffe sind eine andere, groessere Klasse.

## Reparaturplan (Reviewer-Reihenfolge, durch die Triage bestaetigt)

Grundsatz je Block: EIN Commit, EIN parametrisierter KLASSEN-Test ueber alle
Instanzen (nicht ein Positivtest je Reviewer-Beispiel), Konventionspruefung
wo moeglich, damit sich das Muster nicht erneut einschleicht.

### Block 1 — Belegidentitaet (T23-01), Umfang L
Klasse: Der protokollierte Hash muss aus GENAU den Bytes stammen, die geparst/
validiert/gerendert wurden. Neun Stellen in sieben Dateien (P-Q3, 3x P-K1,
A-K1, abox_merge, abnahmebericht, aktuartest, extract als Verdachtsfall).
Fix: ein gemeinsamer Helfer "einmal lesen, daraus hashen, daraus parsen" in
gates/_common.py; alle Stellen umstellen; ein parametrisierter Tausch-Test
ueber alle Gates (Datei zwischen Hash- und Verarbeitungs-Read atomar tauschen)
nach dem Muster tests/test_bestand_review_t20.py; AST-Konventionstest gegen
"hash_files(pfad) + separates read/lade desselben Pfads". Zuerst, weil sonst
alle folgenden Reparaturen weiter andere Bytes signieren als sie pruefen.

### Block 2 — versionierter Evidence-Vertrag (T23-02, T23-03, T23-09), je M
T23-02: kein Deserialisierungs-Default gleich der aktuellen Version — bei
fehlendem Versionsschluessel hart fehlschlagen (ABox, TarifSpez, dazu
spez_version und schema_version ohne jeden Vergleich, sowie vier from_dict
in models/schemas.py); Test: je Modell ein JSON OHNE den Schluessel.
T23-03: von_version an die Vorgeschichte binden (erster A-K1 des Falls oder
== nach_version des zuletzt akzeptierten A-K1-Snapshots) plus echte
Semver-Ordnung von < nach.
T23-09: artefakt["pfad"] und `--mandat` gegen eine explizite Grenze binden
(bestehendes Muster models/zeichnung._unter bzw. _fall_scope.pruefe_artefakt_eintrag).

### Block 3 — A-M4-Vollprofil (T23-04, T23-05), M und S-M
T23-04: alle P-B1-Rollen (config, merkmale, historie, scheiben, ledger)
raeumlich oder ueber eingang.json binden — im Produzenten (bestand_validate,
cli_fortschreibung/abschluss) UND in A-M4 (_b1_fehler), nicht nur portfolio.
T23-05: Positivschwelle fuer betraege_hergeleitet plus ein Katalog
"Pflicht-positiv" in der generischen Konsistenzschleife (Geschwister-Zaehler
bewegungsjahre, sanity_baender, manifest_gebunden fachlich pruefen); Test:
Zaehler 0 muss ablehnen. Danach die drei Bestands-E2E-Fixtures nachziehen.

### Block 4 — Zeichnungsvertrag (T23-06, T23-08), je M
T23-06: die Pruefregel aus models/schemas.py (Pflicht-Keys, Schluesselklasse,
mandat_sha256 bei simulation) als validiere_zeichnung() nach models/zeichnung
extrahieren und an JEDEM Eintrittspunkt anwenden: model_validator auf
Entscheidung, validate_abox, kette.pruefe_kette, befuellung.loese_diskrepanz_auf,
betrieb/uebernahme.validate_eingang.
T23-08: die Zeichnungs-Sperre VOR den Idempotenz-Kurzschluss ziehen und
kern_inhalt um ordnung_sha256/schluesselklasse/mandat_sha256 erweitern, damit
Schreib- und Lesepfad dieselbe Semantik tragen.

### Block 5 — Import-Ratsche (T23-07), M eng / L voll
Eng (jetzt): Rebinding von builtins.__import__ und importlib.import_module
per Zuweisung/from-Import mitverfolgen; Attribut-Zweig auf
{import_module, __import__}; Docstring-Behauptung "vollstaendig" korrigieren;
Mutationstests mit Alias-/Relativimporten. Voll (getattr/sys.modules):
gesondert bewerten, ehrlich als Reichweite benennen (T22-08-Weg).
Danach Code-Karte und volle Suite.

## Abgrenzung

Nicht Teil dieser Triage: freischaltung (#17) als eigener Review-Auftrag;
#16 (bereits auf main, nicht adversarial abgenommen). Die vom Reviewer
ausdruecklich als funktionierend bestaetigten Punkte werden nicht angefasst.

## Einzelbefunde (Pruefergebnisse, wortgetreu)

### T23-01 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** Reviewer-Zeilen stimmen exakt. gates/abox_validate.py:163-168 hasht eingang.json und abox.json ueber hash_files() -> file_sha256() (liest die Bytes NUR zum Hashen, verwirft sie danach). Zeile 172 `abox = lade(fall)` ruft ontologie/abox.py:46-48 `lade()` auf, die abox_pfad(fall) intern NEU aufloest und per `pfad.read_text()` ein ZWEITES Mal von der Platte liest -> das validierte ABox-Objekt stammt aus diesem zweiten Read, nicht aus dem gehashten. Zeile 185 `register = json.loads(register_pfad.read_text(...))` liest eingang.json ebenfalls ein zweites Mal, unabhaengig vom Hash aus Zeile 164. Damit ist die Kette Hash(Read#1) -> Urteil(Read#2) fuer BEIDE Eingaben von P-Q3 gegeben, exakt wie beschrieben.

**Schaden.** Zwischen Read#1 (Hash) und Read#2 (Parse/Validierung/Kette/Coverage) kann die Datei auf der Platte ausgetauscht werden (atomarer Replace, Race mit einem parallelen Schreiber, oder ein zwischen zwei Read-Syscalls liegendes Toolaufraeumen). Der Ledger-Eintrag von P-Q3 (input_hashes) behauptet dann, GENAU diese Bytes seien gegen T-Box-Contract, Eingang-Register, Kette und Coverage geprueft worden — tatsaechlich wurde eine andere A-Box oder ein anderes eingang.json geprueft. A-K1 und A-M4 binden sich spaeter an genau diesen protokollierten Hash (vgl. gate_entscheid.py `_pruefe_o1_ledger` mit `abox_hash=`/`eingang_hash=`) und wuerden damit eine A-Box freigeben-lassen, die P-Q3 nie gesehen hat — ein gruener Beleg fuer eine ungepruefte Aenderung, exakt das im Befund benannte Schadensbild.

**Schwere.** Zustimmung: hoch, aus zwei Gruenden ueber die reine Fundstelle hinaus. Erstens: das Repo hat diese Klasse bereits einmal an genau dieser Architektur-Ebene (P-B1/T20-01) explizit erkannt, benannt und mit eigenem Regressionstest (tests/test_bestand_review_t20.py, monkeypatch-Tausch zwischen Hash- und Lese-Zeitpunkt) geschlossen — es gibt also intern schon Beweis, dass die Luecke real ausnutzbar ist, nicht nur theoretisch. Zweitens ist die Ausbreitung, die die Grep-Runde zeigt, groesser als der Reviewer vermutete: nicht nur P-Q3/P-K1/A-K1, sondern auch der A-Box-Produzent (abox_merge) und zwei weitere von Menschen gelesene Abnahme-Artefakte (Abnahmebericht fuer A-M4, aktuartest-Bericht fuer A-M1/A-M3) tragen dasselbe Muster — die Instanzen, an denen sich ein Mensch orientiert, sind am staerksten betroffen.

**Klasse (Invariante).** Ein Gate darf den Hash, der als Beleg (input_hashes/belege) fuer eine gepruefte oder geladene Datei protokolliert wird, NUR aus denselben Bytes berechnen, die tatsaechlich geparst/validiert/gerendert wurden — sobald eine Datei zweimal unabhaengig von der Platte gelesen wird (einmal zum Hashen, einmal zum Verarbeiten, in beliebiger Reihenfolge), ist der protokollierte Hash kein Beleg mehr fuer den tatsaechlich gepruepften Inhalt, sondern nur fuer irgendeinen Zustand der Datei zu irgendeinem Zeitpunkt der Ausfuehrung.

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/gates/generation_golden.py:393 (lade_spez liest spez_datei) vs. :654 (hash_files liest dieselbe spez_datei erneut fuer input_hashes) — bestaetigt die Vermutung des Reviewers zu P-K1.
- src/rechner_pipeline/gates/generation_golden.py:429 (_lese_names(names_csv) liest die Modellpunkt-Namen) vs. :653 (hash_files liest names_csv erneut) — dieselbe Klasse, zweite Instanz in P-K1.
- src/rechner_pipeline/gates/generation_golden.py:509 (roh_pfad.read_text() liefert die Rohskalare fuer die Parameter-Pruefungen, die ins GM-Urteil einfliessen) vs. :655 (hash_files liest denselben *_scalar.json-Pfad erneut) — dritte Instanz in P-K1.
- src/rechner_pipeline/gates/gate_entscheid.py:1313-1314 (register aus eingang.json geparst und fuer validate_abox verwendet) vs. :1365 (_sha256_datei(fall/'eingang.json') liest dieselbe Datei fuer den P-Q3-Ledger-Abgleich erneut) — bestaetigt die Vermutung des Reviewers zu A-K1; auffaellig, weil im selben Codeblock die A-Box-Bytes korrekt wiederverwendet werden (Kommentar Zeile 1341-1344), eingang.json aber nicht.
- src/rechner_pipeline/gates/abox_merge.py:114 (lade_fragmente liest die Fragmentdateien) und :131 (register_pfad.read_text()) vs. :152-156 (separater Hash jeder Fragmentdatei) und :171 (hash_files liest register_pfad und alle Fragmentdateien fuer input_hashes ein DRITTES Mal) — betrifft den Produzenten der A-Box selbst, also die Quelle, auf die sich P-Q3/A-K1 spaeter verlassen.
- src/rechner_pipeline/gates/abnahmebericht.py:1745 (input_hashes = hash_files(eingaben...) fuer suite/spec/transformation_ergebnis/Berichte) berechnet den Beleg-Hash VOR den eigentlichen Lese-Aufrufen bei :1789 (suite), :1806 (spec_text) und :1820 (transformation_ergebnis) — dieselbe Klasse in umgekehrter Reihenfolge (hash-dann-lesen statt lesen-dann-hash), am A-M4-Abnahmebericht, dem Dokument, auf dessen Basis der Mensch entscheidet.
- src/rechner_pipeline/gates/aktuartest.py:~989 (test = json.loads(test_pfad.read_text())) vs. :1029 (hash_files([test_pfad, ...]) fuer input_hashes) und :1074 (hash_files([test_pfad, bericht_pfad]) fuer 'belege') — test_pfad wird dreimal unabhaengig gelesen; betrifft den aktuariellen Testbericht fuer A-M1/A-M3.
- src/rechner_pipeline/gates/extract.py:331 (input_hashes = hash_files([source]...)) haengt am Quell-Workbook, das der Extraktions-Backend (COM/openpyxl) VORHER ueber einen ganz anderen Lesekanal verarbeitet hat — schwaechere/andersartige Instanz derselben Grundidee (Beleg-Hash und tatsaechlich verarbeitete Bytes koennen auseinanderlaufen), aber mechanisch nicht identisch, deshalb nur als Verdachtsfall genannt.

**Fix-Umfang.** L. Die Klasse ist NICHT mit einem lokalen Patch zu schliessen, weil sie in mindestens sieben Dateien / neun Fundstellen wiederkehrt und weil das Repo bereits zeigt, dass Einzel-Patches (P-B1/T20-01) die Klasse nicht ausrotten, nur die eine Instanz. Notwendig: (1) EIN gemeinsamer Helfer in gates/_common.py nach dem in generation_golden.py (A-Box-Zweig) und gate_entscheid.py (A-Box-Zweig) bereits vorgemachten Muster — Bytes einmal lesen, direkt daraus hashen (hashlib.sha256/file_sha256 auf dieselbe Variable), dann aus denselben Bytes parsen (json.loads(bytes)/Model.model_validate_json(bytes)) — als Ersatz fuer den Zwei-Schritt-Umweg 'hash_files(pfad) + separat read_text/read_bytes/lade()'. hash_key() (bereits vorhanden, liest NICHT) bleibt fuer den reinen Schluessel-Namen. (2) Jede der neun Fundstellen auf diesen Helfer umstellen, inklusive der Sonderfaelle 'Hash vor dem Lesen' (abnahmebericht.py) und 'Engine liest/hasht/parst' (wie bereits bei bestand_validate.py/P-B1 vorgemacht). (3) Ein generischer Konventionstest (z. B. AST-Scan ueber gates/*.py: kein Pfad, der an hash_files()/hashlib.sha256(...read_...()) UND an eine Parse-Funktion (read_text/read_bytes/json.loads/model_validate_json) getrennt uebergeben wird), damit ein zukuenftiges neues Gate die Klasse nicht erneut einschleppt — das ist der Kern dessen, was der Reviewer mit 'bisher immer nur die genannte Stelle repariert' kritisiert. Fangender Test PRO betroffenem Gate: das in tests/test_bestand_review_t20.py etablierte Muster reproduzieren — Datei zwischen Hash-Read und Verarbeitungs-Read atomar austauschen (monkeypatch oder echter Dateitausch) und pruefen, dass entweder der protokollierte Hash zu den TATSAECHLICH verarbeiteten Bytes passt oder das Gate den Lauf verweigert; als EIN parametrisierter Test ueber alle betroffenen Gate-Kommandos, nicht neun Einzeltests je Fundstelle.

**freischaltung f7c545d.** Identisch an den meisten Stellen, keine Regression, aber auch kein Fix. abox_validate.py, generation_golden.py und aktuartest.py sind zwischen b5fa737 und f7c545d BYTE-IDENTISCH (kein Diff) — die dort gefundenen Instanzen (P-Q3, alle drei P-K1-Stellen, aktuartest) bestehen auf freischaltung unveraendert fort. gate_entscheid.py, abox_merge.py und abnahmebericht.py haben zwar Diffs, aber diese betreffen ausschliesslich andere Themen (Fuehrungsprobe-Belegrolle/A-M4, Systemstand-Filter fuer Snapshot-Vertraege, Ueberschreiben-Schutz fuer entschiedene A-Boxen) — die konkret zitierten TOCTOU-Zeilen (gate_entscheid.py:1365 eingang_hash; abox_merge.py:171 register/Fragment-Rehash; abnahmebericht.py:1745 input_hashes vor dem Lesen) sind in diesen Diffs NICHT beruehrt, bleiben inhaltlich identisch. Abnahmebericht.py wird sogar leicht verschlimmert: die neue Rolle 'fuehrungsprobe' wird in dieselbe verwundbare `eingaben`-Dict aufgenommen und damit ebenfalls VOR ihrem eigentlichen Lesen gehasht (neue Instanz derselben Klasse) — bemerkenswert, weil die dort NEU geschriebene Funktion `_fuehrungsprobe_fehler` an anderer Stelle im selben Commit sehr sorgfaeltig jede Eingabe gegen den AKTUELLEN Hash nachprueft (sha256_datei je Eingabe), also erkennbar Bewusstsein fuer das Problem zeigt, es aber nicht auf den eigenen Belegpfad (input_hashes) anwendet.


### T23-02 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** src/rechner_pipeline/ontologie/tbox.py:217 `tbox_version: str = TBOX_VERSION` (Klasse ABox beginnt Zeile 211, schema_version Zeile 216 — Reviewer-Range 216-218 trifft den Block, exakte Zeile ist 217). src/rechner_pipeline/spez/schema.py:106 `tbox_version: str = TBOX_VERSION` (Klasse TarifSpez beginnt Zeile 102 — Reviewer-Range 102-107 trifft den Block, exakte Zeile ist 106). Ladepfad: ontologie/abox.py:45f `lade()` -> `ABox.model_validate_json(...)`; spez/validierung.py:48f `lade_spez()` -> `TarifSpez.model_validate_json(...)`. Beide Pydantic-Modelle haben `extra=\"forbid\"\", das verhindert nur UNBEKANNTE Felder, nicht FEHLENDE — ein JSON ohne den Schluessel \"tbox_version\" laedt anstandslos und bekommt den Default = aktuelle TBOX_VERSION zugewiesen. Die Vergleiche selbst existieren und sind fuer den EXPLIZIT-FALSCHEN Fall korrekt: abox.py:66 `if abox.tbox_version != TBOX_VERSION`, validierung.py:53 `if spez.tbox_version != abox.tbox_version or spez.tbox_version != TBOX_VERSION`. Aber fuer den FEHLENDEN Fall greifen sie nicht, weil das Feld nie \"fehlt\" nach dem Laden. Bestaetigt auch durch die Tests selbst: tests/test_tbox_version_ak1.py deckt ausschliesslich den Fall ab, dass der Schluessel im JSON auf einen FALSCHEN Wert (\"999.0.0\") gesetzt wird (`_abox_mit_version`, `model_copy(update=...)`) — keine einzige Testinstanz entfernt den Schluessel ganz. Die Commit-Botschaft von 29891ec selbst beschreibt den Ausgangsbefund exakt als \"abox_tbox 999.0.0 -> pq3_exit 0\", also nur den Mismatch-Fall, nie den Absence-Fall.

**Schaden.** Ein A-Box- oder Spez-Artefakt, das vor Einfuehrung des Feldes erzeugt wurde, von Hand bearbeitet, unvollstaendig aus einem aelteren Werkzeug exportiert oder schlicht ohne den Schluessel geschrieben wurde, wird beim Laden stillschweigend als \"spricht das aktuelle T-Box-Vokabular\" eingestuft. P-Q3 (validate_abox) und P-K1 (validate_spez) — die einzige Instanz, die genau diese Migrationsgrenze bewachen soll — melden dafuer gruen, obwohl die inhaltliche Grundlage (Struktur/Bedeutung der Aussagen) tatsaechlich aus einer aelteren, moeglicherweise unvereinbaren T-Box-Version stammt. Der falsche Beleg, der dadurch entsteht: \"diese A-Box/Spez ist unter der geltenden T-Box auslegbar\", obwohl das nie geprueft wurde — genau die Faelschung, die A-K1 verhindern sollte.

**Schwere.** Zustimmung zu \"hoch\": Der Reviewer benennt die wichtigste Migrationsgrenze zurecht als kritisch, und der Fehler liegt strukturell genau an der Stelle, wo Review T22-02 den Schutz ausdruecklich einbauen wollte — die Massnahme ist also fuer den haeufigeren, unauffaelligeren Fall (kein Feld statt falsches Feld) wirkungslos, waehrend gerade der auffaellige Fall (explizit falscher Wert) bereits abgedeckt ist. Das ist real hoch, weil derzeit ALLE erzeugten A-Boxen/Specs den Default korrekt setzen (befuellung.py:327 `ABox(...)` ohne explizites tbox_version, tests idem) und TBOX_VERSION bislang nie erhoeht wurde — die Klasse ist also aktuell noch nicht durch einen echten Vorfall ausgeloest, sondern eine strukturelle Zeitbombe, die beim naechsten T-Box-Bump oder bei der ersten Hand-Bearbeitung eines Artefakts scharf wird.

**Klasse (Invariante).** Ein Versionsfeld, dessen Deserialisierungs-Default gleich der aktuell geltenden Version ist (Pydantic-Feld-Default oder `dict.get(key, AKTUELLE_KONSTANTE)`), macht \"Version nicht deklariert\" und \"Version == aktuell\" ununterscheidbar — jeder nachgelagerte Vergleich gegen die aktuelle Konstante ist dadurch blind fuer fehlende/unvollstaendige Artefakte und schuetzt nur noch gegen explizit falsch deklarierte Versionen; die im Repo bereits vorhandene sichere Gegenprobe ist GateLedgerEntry.validate_payload (models/schemas.py), die fehlende Pflichtfelder VOR jeder Interpretation als eigenen Fehler meldet und den Wert nie mit einem Default synthetisiert.

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/spez/schema.py:105 — TarifSpez.spez_version: str = SPEZ_VERSION traegt denselben Default-Pattern, wird aber NIRGENDS mit SPEZ_VERSION verglichen (kein einziger Treffer fuer '.spez_version' ausserhalb einer Info-Fstring in fachspez.py:99) — noch staerker fail-open als der Reviewer-Fall: hier fehlt sogar der Vergleich selbst.
- src/rechner_pipeline/ontologie/tbox.py:216 — ABox.schema_version: int = 1 hat denselben Default-Pattern und wird ebenfalls nirgends gegen eine Konstante geprueft (kein Treffer fuer 'abox.schema_version' oder aequivalent) — dieselbe Klasse, noch ungeschuetzter.
- src/rechner_pipeline/models/schemas.py:241 — CommonResult.from_dict: schema_version=int(data.get('schema_version', SCHEMA_VERSION)) gefolgt von validate() Zeile ~246 'if self.schema_version != SCHEMA_VERSION' — identischer Mechanismus: ein .gate.json-Ergebnis ohne schema_version-Schluessel wird beim Laden stillschweigend auf die aktuelle Version gesetzt und besteht validate() immer.
- src/rechner_pipeline/models/schemas.py:780 — dieselbe Zeile/Pattern in einer weiteren from_dict-Methode derselben Datei (Schema um 'RunDossier'/Report-Klasse), identischer fail-open-Mechanismus.
- src/rechner_pipeline/models/schemas.py:885 — RunDossierV2Delta.from_dict: schema_version=int(data.get('schema_version', 2)), geprueft in validate() 'if self.schema_version != 2' — literal statt Konstante, aber dieselbe Klasse von Fehler.
- src/rechner_pipeline/models/schemas.py:981 — QaReport.from_dict: identisches Pattern int(data.get('schema_version', SCHEMA_VERSION)) vor validate()-Vergleich gegen SCHEMA_VERSION.

**Fix-Umfang.** M — betrifft mehrere Dateien, aber jede Aenderung ist mechanisch gleich: An jeder Ladestelle (ABox.model_validate_json, TarifSpez.model_validate_json, sowie CommonResult/QaReport/QaContract/RunDossierV2Delta.from_dict) muss VOR der Interpretation geprueft werden, ob der Versions-Schluessel im rohen JSON/dict ueberhaupt vorhanden war — Pydantic-Default durch einen Pflicht-Validator ersetzen (z. B. `@model_validator(mode='before')`, der bei fehlendem Schluessel hart fehlschlaegt, oder das Feld ohne Default deklarieren) bzw. bei den Dataclass-from_dict-Methoden dem bereits vorhandenen GateLedgerEntry.validate_payload-Muster folgen (fehlende Pflichtfelder zuerst melden, nie mit `.get(key, AKTUELLE_KONSTANTE)` synthetisieren). Fuer TarifSpez.spez_version und ABox.schema_version zusaetzlich: ueberhaupt einen Vergleich einbauen, sonst schliesst der Fix nur die Halbklasse 'Vergleich vorhanden aber blind'. Test-Klasse, die die Schwaeche faengt: eine Mutationsprobe/Parametrisierung ueber ALLE betroffenen Modelle, die je Modell ein JSON OHNE den Versions-Schluessel (nicht: mit falschem Wert) laedt und erwartet, dass das Laden/die Validierung fehlschlaegt — nicht nur der bereits vorhandene 999.0.0-Fall.

**freischaltung f7c545d.** identisch — der Diff b5fa737..f7c545d beruehrt keine der Fehlerstellen inhaltlich. Der einzige Treffer in den relevanten Dateien ist ein unabhaengiger Versionsbump in models/schemas.py (`P9_GATE_VERSION` von \"1.0.0\" auf \"2.0.0\"), der mit dem T-Box/Spez/schema_version-Default-Problem nichts zu tun hat. tbox.py, spez/schema.py, ontologie/abox.py und spez/validierung.py sind in f7c545d gegenueber b5fa737 unveraendert.


### T23-03 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** src/rechner_pipeline/gates/gate_entscheid.py:390 `von, nach = daten.get("von_version"), daten.get("nach_version")` — danach (391-394) nur Format (`_SEMVER`) und `von == nach`. Die einzige Bindung an die Realitaet betrifft ausschliesslich `nach`: Zeile 396 `if nach != tbox_modul.TBOX_VERSION:` (muss dem geladenen Code entsprechen) und Zeile 402-403 der Hash des geladenen T-Box-Moduls. `von_version` wird an NICHTS ausserhalb des Dokuments selbst gebunden — keine Versionshistorie, kein vorangegangener A-K1-Snapshot, kein Vergleich `von < nach`. Empirischer Beleg: tests/test_tbox_version_ak1.py:92 setzt `"von_version": "0.0.9"` als Fixture-Wert, obwohl `TBOX_VERSION` laut `git log -p` im gesamten Repo (main wie ebenen) nie etwas anderes als `"0.1.0"` war (git show f7c545d:src/rechner_pipeline/ontologie/tbox.py:40) — der Beleg behauptet also nachweislich eine frei erfundene Vorgeschichte, und kein Test in der Datei prueft `von_version` gegen irgendeinen echten Vorzustand (der Parametrisierungs-Test Zeile 128-136 deckt nur `tbox_sha256`, `nach_version`, `von==nach` und `begruendung` ab). Die Reviewer-Zeilenangabe (390-417) trifft den Kern der Funktion (366-418) im Wesentlichen, ist aber leicht ungenau in der BESCHREIBUNG: die Funktion prueft mehr als nur "Formatform und Ungleichheit" (auch nach_version==Code-Version, Modul-Hash, Artefakt-Existenz+Hash, nicht-leere Begruendung) — nur betreffen all diese Zusatzpruefungen ausschliesslich `nach`/das Artefakt, niemals `von`. Deshalb bleibt die Kernaussage des Befunds korrekt, auch wenn die woertliche Aufzaehlung unvollstaendig ist.

**Schaden.** A-K1 signiert (mit Freigabeschluessel, gehashtem Pflichtbeleg, P9-Historie) die Aussage "die T-Box ging von X nach Y, begruendet durch Artefakt Z" — aber X ist frei waehlbar Text im Semver-Format. Konkret moeglich: (1) ein rein erfundener Vorzustand wird als real dokumentierter Ausgangspunkt in den Pflichtbeleg-Snapshot uebernommen, obwohl die T-Box in der gesamten Repo-Historie durchgehend "0.1.0" war; (2) ein "rueckwaerts laufender" Uebergang (`von_version` semver-hoeher als `nach_version`) wird anstandslos signiert, solange `nach_version` zufaellig dem aktuell geladenen Code entspricht — die Pruefung vergleicht die Strings nie mit `packaging.version`. Der Schaden trifft nicht die Rechenergebnisse selbst (die sind ueber tbox_sha256/nach_version/artefakt-hash echt gebunden), sondern die Beweiskraft des Governance-/Audit-Datensatzes: ein Pruefer, der sich auf den A-K1-Snapshot als Nachweis eines nachvollziehbaren, kompatibilitaetsgeprueften Versionsuebergangs verlaesst, wird getaeuscht — es gibt keine Garantie, dass die behauptete Vorversion je existiert hat oder dass die Aenderung tatsaechlich vorwaerts/kompatibel war.

**Schwere.** Ueberwiegend Zustimmung zu "hoch", mit einer Einschraenkung. Das System begruendet sich explizit ueber "die Annahme RECHNET ihre Voraussetzungen — sie glaubt sie nicht" (Kommentar direkt oberhalb im selben main(), Zeile ~1345) und bindet sonst konsequent JEDE Behauptung an echte Bytes/Hashes. A-K1 bricht dieses Prinzip fuer die Haelfte seines eigenen Vertrags (die "von"-Seite) und ist damit inkonsistent zur sonst durchgehaltenen Beweislogik des Gate-Systems — das rechtfertigt "hoch" fuer ein Audit-/Provenienz-Gate. Abschwaechend: es besteht keine Downstream-Kette, die aus `von_version` etwas berechnet oder freischaltet (die tatsaechlich wirksamen Felder nach_version/tbox_sha256/artefakt-hash sind korrekt gebunden), der Schaden bleibt auf die Beweiskraft des Aenderungsvermerks selbst beschraenkt. Ich wuerde es bei "hoch" belassen, weil die Klasse (unverifizierte Vergangenheitsbehauptung in einem sonst hash-treuen Beleg-System) das Vertrauen in die gesamte A-K1-Rolle als Nachweis untergraebt, nicht nur einen Randfall.

**Klasse (Invariante).** Wenn ein Beleg eine Aussage ueber einen NICHT MEHR direkt vorliegenden, vergangenen Zustand macht (ein "von_"/"vorher"/"alt_"-Feld), darf ein Gate ihn nur dann als Nachweis werten, wenn dieser vergangene Zustand unabhaengig verankert ist (z. B. an eine fruehere, selbst bereits gebundene Signatur/Snapshot-Kette oder an ein gehashtes Artefakt jenes Standes) — pruefte das Gate stattdessen nur Formatgueltigkeit und Uebereinstimmung mit dem AKTUELLEN Zustand, kann jede beliebige, auch widerspruechliche oder rueckwaerts laufende Vorgeschichte signiert werden.

**Weitere Stellen.** keine gefunden.

**Fix-Umfang.** M. Umfang: (1) `von_version` an eine echte Vorgeschichte binden — am naheliegendsten ueber die bestehende Entscheid-/Snapshot-Kette (analog zum `vorgaenger`-Verkettungsmuster in `_lade_snapshot_kette`): der Beleg muss entweder der allererste A-K1-Uebergang des Falls/Repos sein, oder `von_version` muss exakt dem `nach_version` des zuletzt akzeptierten A-K1-Snapshots entsprechen (statt frei erfundenem String). (2) eine echte Semver-Ordnungspruefung ergaenzen (`packaging.version(nach) > packaging.version(von)`), um den rueckwaerts laufenden Fall unabhaengig vom Verkettungsfix zu schliessen. (3) neue Tests, die NICHT nur die vier bestehenden Parametrisierungsfaelle (tbox_sha256/nach_version/von==nach/begruendung) abdecken, sondern gezielt: (a) `von_version` ohne Bezug zum letzten akzeptierten A-K1-Snapshot wird abgelehnt, (b) `nach_version` < `von_version` (Semver) wird abgelehnt, obwohl `nach_version == TBOX_VERSION`. Kein reiner Ein-Zeilen-Fix (S), da eine Verkettungs-/Historienquelle fuer `von_version` erst entworfen werden muss; kein L, da nur `gate_entscheid.py` + zugehoerige Tests betroffen sind, keine Cross-Repo- oder Architekturaenderung.

**freischaltung f7c545d.** Identisch, nicht behoben. `git diff b5fa737 f7c545d -- src/rechner_pipeline/gates/gate_entscheid.py` zeigt keine Aenderung an `pruefe_tbox_aenderung` (Zeilen 366-418 byte-identisch); der einzige Diff-Hunk im Umfeld betrifft die spaeter folgende, fachlich andere Funktion `_pruefe_g2_snapshot_semantik` (bekommt ein `aktueller_systemstand`-Argument fuer eine andere Fragestellung: wachsende Pflichtbelegmengen ueber Systemstaende hinweg, nicht die Versionsuebergangs-Verifikation). `TBOX_VERSION` ist auf f7c545d weiterhin `"0.1.0"` (src/rechner_pipeline/ontologie/tbox.py:40). Der Befund gilt auf f7c545d unveraendert.


### T23-04 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** gates/abnahmebericht.py:1416-1434 (Reviewer-Zeilen stimmen): die Schleife `for name, erwartet_hash in entry.input_hashes.items(): ... rolle = ... if rolle is not None: aktuelle_eingaben[rolle] = vorhanden ... if rolle == "portfolio": try: vorhanden.relative_to(fall.resolve()) except ValueError: fehler.append("P-B1-Portfolio-Rolle liegt ausserhalb des Falls")` — der `relative_to(fall)`-Test greift NUR bei rolle=="portfolio" (Z.1430-1434); fuer "config" (und "historie"/"scheiben"/"ledger"/"merkmale") gibt es keinen aequivalenten Zweig. Unabhaengige Registrierung: portfolio wird zusaetzlich extern gebunden ueber `if portfolio_sha256 != suite.get("bestand_sha256")` (Z.1384), gespeist aus migrationssuite_lauf.py:806 `bestand_sha256=hashlib.sha256(bestand_pfad.read_bytes()).hexdigest()` — ein von P-B1 unabhaengiger Erzeuger. Fuer config existiert kein Analogon: `git grep -n "config_sha256"` in b5fa737 liefert null Treffer. eingang.json bindet laut `git grep` nur Stufe-1-Quellen (abox_validate.py, gate_entscheid.py, fall.py) — bestand-config.toml erscheint dort nie; `--config` wird in bestand_validate.py:156 und cli_fortschreibung.py:170 als freier Pfad-Parameter definiert und in bestand_validate.py:242-247 unveraendert in `eingaben[name] = Path(wert)` uebernommen, ohne Fall- oder Registrierungspruefung. Dass config die Betragspruefung DEFINIERT, zeigt vorbedingungen.py:283-317 (`pruefe_ledger_betraege(portfolio, ledger, config, ...)`, Kommentar Z. "Betragsidentitaet je Buchung (T20-04): erst mit den Rechnungsgrundlagen der Config ist der Kern herleitbar").

**Schaden.** Wer `--config` bei bestand_validate.py auf eine selbst erstellte bestand-config.toml auesserhalb des Falls (oder innerhalb, aber unregistriert) zeigen laesst, bestimmt damit die Rechnungsgrundlagen (Zins, Kosten, Sterbetafel-Varianten, Plausibilitaetsbaender), gegen die `pruefe_ledger_betraege` die "erwartete" Ledger-Buchungshoehe herleitet. Ein Ledger mit falschen/manipulierten Betraegen laesst sich so passend zu einer ebenfalls frei gewaehlten Config machen, die dann ein gruenes P-B1-Urteil und in der Folge ein gruenes A-M4-Vollprofil erzeugt. Der SHA-256-Beleg zeigt korrekt, DASS bestimmte Bytes benutzt wurden — nicht, dass diese Bytes die vereinbarte/freigegebene Rechnungsgrundlage des Falls sind. Damit kann eine Migrationsabnahme (A-M4) auf einer nie autorisierten Bewertungsbasis "belegt" werden.

**Schwere.** Zustimmung zu "hoch": (1) config ist nicht nur Dateninput sondern Teil des Pruefmassstabs selbst (Kern-Herleitung der Ledgerbetraege) — die Schwaeche wirkt direkt auf das A-M4-Urteil, nicht nur auf eine Nebenrolle. (2) Der Mechanismus, der genau dieses Risiko fuer "portfolio" bereits schliesst (Fall-Scope UND unabhaengige Suite-Bindung via bestand_sha256), liegt im selben Code-Block direkt daneben — es fehlt nicht an Erkenntnis oder Muster, sondern an konsequenter Anwendung. (3) Das Repo kennt und nutzt das richtige Gegenmittel bereits an anderer Stelle: aktuartest_lauf.py bindet Erwartungswerte/Stichprobe/Plausibilitaetsbeleg ausdruecklich ueber `fall_mod.eingang_datei`/`_lies_registriert` an die Fall-Registrierung, mit dem Docstring-Kommentar "Erwartungswerte sind eine REGISTRIERTE Quelle des Falls, kein freier Dateipfad" — das zeigt, der Standard ist im Team etabliert und wurde bei P-B1s config verfehlt.

**Klasse (Invariante).** Jede Eingabe eines Bestands-Pflichtbelegs (P-B1), die in ein A-M4-Urteil eingeht — nicht nur die Portfolio-Rolle —, muss entweder raeumlich an den Fall gebunden (innerhalb des Fall-Arbeitsbereichs, per relative_to(fall)-Test) oder ueber eine vom Pruefling nicht selbst waehlbare, unabhaengige Registrierung (eingang.json-Eintrag oder ein von einem unabhaengigen Erzeuger gehashter Referenzwert wie migrationssuite.bestand_sha256) an ihre Herkunft gebunden sein; sonst belegt der gruene P-B1-/A-M4-Beleg nur, dass bestimmte selbstgewaehlte Bytes benutzt wurden, nicht dass sie autorisiert sind.

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/gates/abnahmebericht.py:1427-1434 — dieselbe Schleife: auch "historie", "scheiben", "ledger" und "merkmale" durchlaufen denselben Zweig, bekommen aber ebenso keinen relative_to(fall)-Test (nicht nur config ist betroffen — der if-Zweig prueft explizit nur rolle=="portfolio").
- src/rechner_pipeline/gates/bestand_validate.py:242-247 — der Produzent selbst uebernimmt --historie/--scheiben/--ledger/--merkmale/--config unveraendert als `eingaben[name] = Path(wert)`, ohne jede Fall- oder Registrierungspruefung; die Luecke entsteht schon beim P-B1-Lauf, nicht erst bei A-M4s Nachpruefung.
- src/rechner_pipeline/bestand/vorbedingungen.py:283-317 — merkmale (tabellen.get("merkmale")) geht gemeinsam mit config in pruefe_ledger_betraege als Referenzgrundlage ein; laut bestand_validate.py Docstring ist --merkmale Pflicht, sobald eine Generation in Tarifzellen aufgeteilt ist und der Ledger gegen den Kern hergeleitet wird — merkmale traegt dann dieselbe Schwaeche wie config.
- Gegenbeispiel/Referenzmuster (kein Fehler, zeigt aber die fehlende Konsequenz): src/rechner_pipeline/gates/aktuartest_lauf.py:102-106,562-563,675 — _lies_registriert/fall_mod.eingang_datei binden Erwartungswerte, Stichprobe und Plausibilitaetsbeleg bewusst an eingang.json ("REGISTRIERTE Quelle des Falls, kein freier Dateipfad"); P-B1s config nutzt dieses im Projekt vorhandene Muster nicht.

**Fix-Umfang.** M: Ein einzelner relative_to-Nachtrag an der zitierten Stelle reicht nicht, weil die Klasse mehrere Rollen und mehrere Dateien betrifft. Noetig: (a) im Produzenten (bestand_validate.py, cli_fortschreibung.py/cli_abschluss.py) jede P-B1-Rolle — mindestens config und merkmale — entweder ueber fall_mod.eingang_datei/eingang.json registrieren oder wie portfolio fall-relativ erzwingen; (b) in A-M4 (_b1_fehler, abnahmebericht.py:1427-1434) den relative_to(fall)-Test auf ALLE Rollen in PB1_VOLLPROFIL ausdehnen, nicht nur portfolio; (c) eine zur Suite analoge unabhaengige Bindung fuer config einfuehren (z. B. config_sha256 in der Migrationssuite oder ein eingang.json-Eintrag) — reine Fall-Lage allein verhindert nicht, dass innerhalb des Falls eine eigene, unregistrierte Config abgelegt wird. Aufwand liegt bei M, weil mehrere Dateien/Erzeuger gemeinsam geaendert werden muessen, aber das Registrierungsmuster (eingang_datei) bereits existiert und wiederverwendet werden kann (kein Neuentwurf, daher nicht L). Fangender Test: parametrisiert ueber alle PB1_VOLLPROFIL-Rollen (nicht nur config) je eine sonst gueltige Datei AUSSERHALB des Fall-Arbeitsbereichs einspeisen und erwarten, dass A-M4 mit \"liegt ausserhalb des Falls\" (oder aequivalent) ablehnt — aktuell rot fuer historie/ledger/merkmale/config, gruen nur fuer portfolio simuliert; zusaetzlich ein Test mit einer inhaltlich veraenderten (anderer Rechnungszins), aber unregistrierten Config plus passend manipuliertem Ledger, der zeigen soll, dass A-M4 auch das ablehnt.

**freischaltung f7c545d.** Identisch. `_b1_fehler` in abnahmebericht.py ist zwischen b5fa737 und f7c545d byte-identisch (per git diff bestaetigt, kein Hunk beruehrt diese Funktion); der Diff aendert nur Umgebung davor/danach (GATE_VERSION 2.0.0->3.0.0, neue Funktion _fuehrungsprobe_fehler). f7c545d fuegt einen NEUEN, zusaetzlichen Beleg hinzu (\"Fuehrungsprobe\", Schritt 6 der Freischaltung), dessen Kommentar sogar explizit \"dasselbe Muster wie _b1_fehler\" nennt und ihre eigenen eingaben-Bytes gegen aktuelle Bytes nachhäscht (sha256_datei(pfad) != erwartet) — aber auch diese neue Pruefung bindet ihre Pfade nicht an den Fall (kein relative_to(fall)) und nicht an eingang.json, sondern nur an einen vom Beleg selbst behaupteten eingaben-Dict. Die config-Luecke ist also weder behoben noch verschoben; eine strukturell verwandte Luecke wurde beim Hinzufuegen neuer Funktionalitaet repliziert statt geschlossen.


### T23-05 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** src/rechner_pipeline/gates/abnahmebericht.py:1459-1463 (b5fa737): `if type(entry.summary.get("betraege_hergeleitet")) is not int: fehler.append("P-B1-Beleg ohne Betragsbindung: ...")` — reine Typpruefung, kein `> 0`/Wahrheitswert-Test. Reviewer-Zeilennummern stimmen exakt. Herkunft des Werts: src/rechner_pipeline/bestand/vorbedingungen.py:314-316: `geprueft["betraege_hergeleitet"] = int(ledger["ereignis"].isin(("ZUG","STO","PEX","TOD","ABL","INV","REA")).sum())` — ein reiner Zaehler, der bei 0 passenden Ledger-Zeilen legitim 0 ist UND als int weiterhin gruen durchlaeuft. Die einzige weitere Verwendung ist die generische Konsistenzschleife abnahmebericht.py:1487-1488 (`if entry.summary.get(name) != wert: fehler.append(...)`), die nur Gleichheit, nie Positivitaet prueft. Kein anderer Codepfad (weder bestand_validate.py/P-B1 selbst noch abnahmebericht.py) verlangt betraege_hergeleitet > 0 — ich habe explizit mit git grep nach jeder Verwendung des Feldes gesucht (nur die vier oben genannten Fundstellen plus Tests). Die Tests bestaetigen die Luecke: tests/test_am4_vollprofil_t22.py:76 prueft nur `isinstance(..., int)`, keine Positivitaet; kein Test im Repo uebergibt betraege_hergeleitet=0 und erwartet Ablehnung. Zusaetzlich belegt dev-docs/review-t19-befunde.md (Vorschlag zu T21-02, Zeile ~230) und dev-docs/offene-punkte.md (Zeile 67), dass die Positivschwelle `summary.geprueft.betraege_hergeleitet > 0` explizit BESCHLOSSEN war ("Ziel: ... und summary.geprueft.betraege_hergeleitet > 0 als Pflicht"), aber bei der Umsetzung in Commit 1c97707 (T22-01, als "behoben" verbucht) nicht eingebaut wurde — die Abweichung zwischen Beschluss und Code ist damit dokumentiert nachweisbar, nicht nur vermutet.

**Schaden.** Ein Bestands-Scope-Lauf, in dem im Pruefzeitraum (bis) zufaellig keine einzige ZUG/STO/PEX/TOD/ABL/INV/REA-Buchung im Ledger liegt (z. B. sehr kurzer Horizont, ruhender Bestand ohne Geschaeftsvorfaelle, oder ein Ledger, das aus einem anderen Grund leer/irrelevant ist), erzeugt trotzdem einen gruenen A-M4-Beleg mit "Vollprofil" und "Betragsbindung" im Titel — obwohl T20-04 (Betrag je Buchung gegen den Kern hergeleitet) fuer diesen Fall NIE ausgefuehrt wurde. Der Abnahmebericht behauptet damit implizit eine Pruefung, die nie stattgefunden hat; ein Mensch, der A-M4 anhand des Berichts entscheidet, haelt eine Vollprofil-Betragsbindung fuer erbracht, wo in Wahrheit 0 Buchungen kontrolliert wurden. Das ist genau die Umgehung, die T21-02/T22-01 eigentlich schliessen sollten (Teilprofil durch Weglassen von Eingaben) — nur jetzt durch eine Ledger-Konstellation statt durch fehlende CLI-Flags erreicht.

**Schwere.** Zustimmung zu "hoch". Begruendung: (1) Es ist keine hypothetische Luecke — der Beschluss, der die Positivschwelle ausdruecklich verlangt, steht bereits im Repo (dev-docs/review-t19-befunde.md, dev-docs/offene-punkte.md), wurde aber beim Umsetzen von T22-01 fallengelassen; die Diskrepanz zwischen dokumentiertem Soll und Code ist damit hart belegt. (2) Es gibt keinen zweiten Schutzwall: weder P-B1 (bestand_validate.py) noch ein anderer Test erzwingt Positivitaet; die einzige Instanz der Pruefung ist der Typcheck. (3) Der Fehlermodus ist ein stiller Gruen-Durchlauf bei einer der zentralen Abnahmegarantien (A-M4/T20-04), nicht ein Randfall einer Nebenmeldung. Einzige Relativierung: ob dieser Zustand in der Praxis leicht erreichbar ist (wie wahrscheinlich ist ein leeres relevantes Ledger im Bestands-Scope wirklich), haengt vom operativen Kontext ab — das mindert aber nur die Eintrittswahrscheinlichkeit, nicht die Schwere der fehlenden Kontrolle selbst.

**Klasse (Invariante).** Ein Beleg-Gate, das eine Zaehl-/Summary-Groesse als Nachweis dafuer verwendet, dass eine bestimmte Pruefung tatsaechlich (und nicht nur formal/typkorrekt) durchgefuehrt wurde, darf nicht nur Typ/Vorhandensein/Konsistenz dieser Groesse pruefen, sondern muss den vakuosen Fall (Zaehler == 0, "es gab nichts zu pruefen, also wurde nichts widerlegt") explizit als Ablehnungsgrund behandeln — sonst ist "Pruefung erfolgreich" ununterscheidbar von "Pruefung ist nie gelaufen".

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/bestand/vorbedingungen.py:270 (geprueft["bewegungsjahre"] = len(konto) — Zaehler der gegen Identitaet gepruefte Bewegungsjahre; wird ueber die generische Schleife abnahmebericht.py:1487-1488 nur auf Gleichheit mit dem Beleg gehalten, nirgends auf > 0 verlangt, obwohl er die eigentliche Verlaufspruefung des Bewegungskontos reprasentiert und bei bis nahe am Start (oder leerem Ledger) 0 sein kann.
- src/rechner_pipeline/bestand/vorbedingungen.py:298 (geprueft["sanity_baender"] = len(config.plausibilitaet) — Anzahl gepruefter Plausibilitaetsbaender; dieselbe Konsistenz-ohne-Positivitaet-Behandlung, bei leerer plausibilitaet-Liste in der Config waere 0 unauffaellig gruen.
- src/rechner_pipeline/bestand/vorbedingungen.py:321 (geprueft["manifest_gebunden"] = len([...]) — Anzahl der ans Manifest gebundenen Rollen; ebenfalls nur Konsistenz-, keine Positivitaetspruefung.
- src/rechner_pipeline/gates/abnahmebericht.py:1487-1488 (die generische Schleife 'for name, wert in geprueft.items(): if entry.summary.get(name) != wert' ist der gemeinsame Ort, an dem ALLE diese Geschwister-Zaehler landen — sie ist strukturell blind fuer den Wert 0, nicht nur fuer betraege_hergeleitet).

**Fix-Umfang.** S bis M. Kernaenderung (S): Zeile 1459 um eine Positivpruefung erweitern, z. B. `wert = entry.summary.get("betraege_hergeleitet"); if type(wert) is not int or wert <= 0: fehler.append(...)` mit einer Meldung, die explizit "0 hergeleitete Buchungen ist kein Beleg" sagt (deckt genau das Reviewer-Beispiel). Um die KLASSE zu schliessen statt nur die eine Stelle (M): entweder (a) einen kleinen Katalog von "Pflicht-positiv"-Feldern definieren (mindestens betraege_hergeleitet; nach fachlicher Pruefung ggf. auch bewegungsjahre/sanity_baender falls sie im Bestands-Scope tatsaechlich immer > 0 sein muessen) und die generische Konsistenzschleife (1487-1488) um eine Positivpruefung fuer genau diese Felder erweitern, oder (b) den Wertebereich jedes Zaehlers an seiner Entstehungsstelle in vorbedingungen.py dokumentieren/pruefen (0 ist erlaubt vs. verboten) und das im Gate konsequent durchsetzen. Testart, die die KLASSE faengt (nicht nur den Reviewer-Fall): eine parametrisierte Mutationsprobe/Property-Test, der fuer JEDES in PB1_VOLLPROFIL-Kontext gemeldete geprueft-Feld ein Fixture-Ledger konstruiert, in dem genau dieser Zaehler auf 0 faellt (z. B. Ledger ohne relevante Ereigniszeilen fuer betraege_hergeleitet, bis direkt am Start fuer bewegungsjahre, leere plausibilitaet-Liste fuer sanity_baender), und erwartet, dass abnahmebericht dafuer NICHT gruen wird — statt nur eines Einzeltests mit betraege_hergeleitet=0.

**freischaltung f7c545d.** identisch. In f7c545d steht an derselben Stelle (dort Zeile 1548, Verschiebung nur durch die neu eingefuegte Fuehrungsprobe-Logik weiter oben im selben Diff) exakt derselbe Code: `if type(entry.summary.get("betraege_hergeleitet")) is not int:` — keine Positivpruefung ergaenzt. Der f7c545d-Diff (git diff b5fa737 f7c545d) fuegt in diesem Bereich ausschliesslich die neue Fuehrungsprobe (--fuehrungsprobe, _fuehrungsprobe_fehler, GATE_VERSION 3.0.0) hinzu; die betraege_hergeleitet-Pruefung selbst ist unveraendert, ebenso die zugehoerigen Tests (tests/test_am4_vollprofil_t22.py, tests/test_bestand_review_t20.py) — identischer Wortlaut in beiden Commits.


### T23-06 — Reviewer hoch — Urteil: bestaetigt

**Beweis.** 1) ontologie/diskrepanz.py:50 (class Entscheidung) bis :77 (`zeichnung: Optional[Dict[str, str]] = None`) — keine Feld-Constraints (kein model_validator prueft Schluessel, schluesselklasse-Werte oder mandat_sha256-Pflicht). Der Klassenname "Entscheidung" traegt exakt dieselben Konzepte (rolle, ordnung_sha256, schluesselklasse, mandat_sha256) wie models/schemas.py:481-521, aber ohne deren Logik.
2) ontologie/diskrepanz.py:96-108 (`_konsistenz`-Validator der Diskrepanz-Klasse) prueft nur id/status/entscheidung-Konsistenz, fasst `entscheidung.zeichnung` gar nicht an.
3) ontologie/abox.py:51-161 (`validate_abox`) — komplette Funktion durchsucht; sie prueft tbox_version, Generations-IDs, widerspruechliche Aussagen, Wertebereiche, verwaiste Diskrepanzen und Eingang-Register-Bindung, aber an keiner Stelle `d.entscheidung.zeichnung`.
4) ontologie/befuellung.py:331-410 (`loese_diskrepanz_auf`) nimmt `zeichnung: Optional[Dict[str, str]] = None` entgegen und schreibt es ungeprueft in die Entscheidung (Zeile 401-410) — ist direkt aufrufbar ohne die CLI-Pruefung aus entscheide.py.
5) ontologie/kette.py:118-198 (`pruefe_kette`, die eigens gegen "eine direkt editierte A-Box passierte sonst alle Gates" gebaut wurde, Befund 45) — Kommentar Zeile 176 sagt woertlich "Status/Entscheidung sind der legitime Freiheitsgrad"; die Pruefung vergleicht nur `gewaehlter_wert` und Provenienz, nie `zeichnung`.
6) gates/abox_validate.py:85-109 (`pruefe_belege`, Gate P-Q3) rechnet nur `entscheidung.beleg.sha256` nach — analoges Feld `entscheidung.zeichnung` wird an der einzigen Stelle, die fuer JEDE A-Box laeuft (unabhaengig vom Schreibweg), nicht gegenkontrolliert.
Enforcement existiert NUR in zwei bekannten Schreibwegen: ontologie/entscheide.py:320-334 (CLI: `if schluesselklasse=="simulation" and not mandat_sha256: return 2`) und gates/gate_entscheid.py:1998-2005 (fuer das ANDERE Feld P9Snapshot.zeichnung, nicht fuer Entscheidung.zeichnung). Reviewer-Zeilenangabe 50-77 stimmt exakt (Klassenanfang bis Feldzeile).

**Schaden.** Wer die A-Box direkt schreibt oder manipuliert — Handbearbeitung, ein fehlerhafter/boesartiger Producer, ein Test-Fixture, oder ein direkter Aufruf von `loese_diskrepanz_auf()`/`Entscheidung(...)` unter Umgehung von `ontologie.entscheide` — kann eine Diskrepanz-Aufloesung mit `zeichnung={"schluesselklasse": "simulation", ...}` OHNE `mandat_sha256` (oder mit voellig frei erfundenem Inhalt, sogar leerem Dict) eintragen. `validate_abox()`, die eigens gegen genau dieses Szenario gebaute `pruefe_kette()` und Gate P-Q3 (`abox_validate`) lassen das alle durch. Der falsche Beleg, der dadurch moeglich wird: eine automatisiert/simuliert getroffene fachliche Entscheidung (Wahl zwischen zwei Lesarten bei einem Tarifkonflikt) erscheint in Fachspez (spez/fachspez.py:226-229 druckt `e.zeichnung.get('rolle')`/`'schluesselklasse'` unbesehen ab) und im Abnahme-Snapshot als ordnungsgemaess — obwohl das Vier-Rollen-Modell (ADR-018) genau verlangt, dass eine Simulationsrolle nur unter einem geprueften Mandat handelt. Die Sicherheitsannahme "jede A-Box im Fall ist entweder aus Fragmenten gemerged oder aus einer gezeichneten Aufloesung entstanden" gilt real nicht fuer den Inhalt von `zeichnung`.

**Schwere.** Zustimmung zu "hoch". Begruendung: (a) es ist keine theoretische Luecke — die exakt gleiche Fach-Regel (Simulation braucht Mandat) ist an ZWEI anderen Stellen im selben Commit bereits durchgesetzt (models/schemas.py, gate_entscheid.py), das Muster ist also bekannt und bewusst umgesetzt, nur an dieser dritten, strukturell gleichwertigen Stelle vergessen; (b) der eigens fuer "A-Box direkt editiert umgeht alle Gates" gebaute Schutzmechanismus (`pruefe_kette`, Systempruefung Befund 45) deckt diesen Fall per Kommentar explizit NICHT ab ("Status/Entscheidung sind der legitime Freiheitsgrad") — die Luecke liegt also genau in der Naht, die dieser Mechanismus eigentlich schliessen sollte; (c) kein Test im Repo konstruiert eine Entscheidung/A-Box direkt (ausserhalb der CLI) mit `schluesselklasse=simulation` ohne Mandat — die Klasse ist ungetestet. Einschraenkend: der Angriff braucht Schreibzugriff auf abox.json oder Python-Code-Aufruf innerhalb des Prozesses (kein Fernzugriff), und die Wirkung ist auf die BEWEISKRAFT der Aufloesung begrenzt (nicht auf den gewaehlten Wert selbst — der bleibt weiter an `pruefe_kette`s Lesarten/Provenienz-Pruefung gebunden). Das rechtfertigt "hoch", nicht zwingend "kritisch".

**Klasse (Invariante).** Jede Aussage im System, die behauptet "diese Entscheidung wurde von einer bestimmten Rolle mit einer bestimmten Schluesselklasse getroffen und — falls simuliert — unter einem konkreten Mandat" (das Vier-Rollen-Modell aus ADR-018), muss an JEDER Stelle, an der ein solches Objekt in den Fall-Arbeitsbereich gelangen kann, strukturell und inhaltlich erzwungen werden — durch den Pydantic-Modell-Validator selbst UND durch die Kreuz-Objekt-Gate-Pruefung, die unabhaengig vom Schreibweg laeuft; sie darf nicht ausschliesslich als Nebenbedingung in der Argumentverarbeitung einer einzelnen CLI-Funktion liegen, denn jeder Code-Pfad, der dieselbe Datenstruktur direkt konstruiert oder eine bereits vorhandene A-Box laedt, umgeht damit die Regel vollstaendig.

**Weitere Stellen mit demselben Muster.**

- ontologie/befuellung.py:331-410 (loese_diskrepanz_auf) — nimmt zeichnung als rohes Dict entgegen und schreibt es ungeprueft in die Entscheidung; direkt aufrufbar unter Umgehung von entscheide.py, exakt derselbe Bypass wie beim Modell selbst.
- ontologie/kette.py:118-198, insb. 175-198 (pruefe_kette) — der eigens gegen 'direkt editierte A-Box umgeht Gates' gebaute Schutz erklaert Entscheidung/Status per Kommentar explizit zum 'legitimen Freiheitsgrad' und prueft nie zeichnung; damit greift ausgerechnet der Mechanismus nicht, der diese Luecke schliessen sollte.
- gates/abox_validate.py:85-109 (pruefe_belege, Gate P-Q3) — rechnet beleg.sha256 nach, aber nicht das strukturell gleichwertige zeichnung-Feld derselben Entscheidung; zeigt, dass das Beleg-Feld bewusst gehaertet wurde, das Zeichnungs-Feld aber nicht.
- betrieb/uebernahme.py:166-168 (validate_eingang) — prueft fuer den Uebernahme-Eingang des Tagesbetriebs nur 'zeichnung muss eine Tabelle sein' (reiner Typ-Check), keine Rolle/Schluesselklasse/Mandat-Pruefung; zeichnung_aus_snapshot (Zeilen 72-107) uebernimmt zusaetzlich Snapshot-Inhalte, deren Signatur laut eigenem Docstring (Zeile 71: 'prueft ihre Signatur NICHT') nicht verifiziert wird — dieselbe Klasse von Schwaeche in einem anderen Teilsystem (Tagesbetrieb statt Migrationsfall), mit derselben Konsequenz: eine hand- oder fremd-geschriebene eingang.json/Snapshot-Datei kann eine beliebige schluesselklasse behaupten.

**Fix-Umfang.** M. Um die KLASSE zu schliessen (nicht nur diskrepanz.py:77): (1) die bereits vorhandene Pruefregel aus models/schemas.py:493-517 (pflicht-Keys, schluesselklasse in {mensch, simulation}, mandat_sha256 bei simulation) in models/zeichnung.py als wiederverwendbare Funktion (z. B. validiere_zeichnung(dict) -> List[str]) extrahieren, damit sie nicht ein drittes Mal separat implementiert wird; (2) Entscheidung in ontologie/diskrepanz.py bekommt einen model_validator, der diese Funktion auf zeichnung anwendet, wenn zeichnung nicht None ist; (3) validate_abox() in ontologie/abox.py ruft dieselbe Funktion zusaetzlich als Kreuz-Objekt-Pruefung ueber alle abox.diskrepanzen[*].entscheidung.zeichnung auf — als Verteidigung in der Tiefe, falls je ein Modell mit aelterer Pydantic-Fassung ungeprueft geladen wird; (4) optional gleiche Funktion in betrieb/uebernahme.py:validate_eingang() fuer eingang["zeichnung"] einsetzen, um die zweite Stelle zu schliessen. Test der KLASSE (nicht nur das Reviewer-Beispiel): ein Test, der Entscheidung(...) bzw. eine A-Box DIREKT im Python-Code konstruiert (ohne den Umweg ueber ontologie.entscheide oder gate_entscheid) mit zeichnung={'schluesselklasse': 'simulation', ...} ohne mandat_sha256 UND separat mit voellig freiem/leerem Dict, und erwartet, dass sowohl die Modellkonstruktion als auch validate_abox() das ablehnen — sowie ein weiterer Test, der eine gueltig aussehende A-Box-JSON-Datei von Hand mit genau diesem Defekt schreibt und ueber das Gate P-Q3 (abox_validate) laufen laesst, um den Kette/Gate-Bypass-Fall (nicht nur den In-Memory-Fall) abzudecken.

**freischaltung f7c545d.** identisch. `git diff b5fa737 f7c545d -- src/rechner_pipeline/ontologie/diskrepanz.py src/rechner_pipeline/ontologie/abox.py src/rechner_pipeline/ontologie/kette.py src/rechner_pipeline/betrieb/uebernahme.py` liefert keinerlei Aenderung — alle vier Dateien sind auf f7c545d byte-identisch zu b5fa737. Die 12 Commits zwischen b5fa737 und f7c545d (Freischaltung-Schritte 1-10, u. a. Fuehrungsprobe, Uebernahme-Anfangszustand, Kettenpruefung-Fix 'stand-bewusst') behandeln andere Themen (Bestandsfuehrung, Fuehrungsprobe, P9-Kettenpruefung-Versionierung) und beruehren weder Entscheidung.zeichnung noch validate_abox() noch pruefe_kette in Bezug auf dieses Feld. Die Schwaeche ist auf f7c545d unveraendert vorhanden.


### T23-07 — Reviewer hoch — Urteil: teilweise

**Beweis.** src/rechner_pipeline/ontologie/code_karte.py:339-344 (b5fa737):
```
dynamisch = (
    (isinstance(n.func, ast.Name)
     and n.func.id == "__import__")
    or (isinstance(n.func, ast.Attribute)
        and n.func.attr == "import_module")
)
```
Empirisch mit dem echten Modul geprüft (synthetisches src-Paket, kern -> kommutationskern, ADR-004/Schicht-Verstoß als Marker, 'openai' als SDK-Marker):
- `import importlib as x; x.import_module('...')` -> Kante+Befunde ERZEUGT (Zeile 342f greift auf JEDES Attribut namens import_module, unabhaengig vom Empfaenger) — Reviewer-Beispiel 1 widerlegt.
- `from .. import kommutationskern` -> Kante+Befunde ERZEUGT (ueber `_absolut()`, bereits gefixt lt. Kommentar Zeile 254-256 "Review U1, Befund Z1-09") — Reviewer-Beispiel 3 widerlegt.
- `importlib.import_module(teil1 + teil2)` -> in `dynamisch_unlesbar` HART GEBLOCKT (Zeile 355-357) — Reviewer-Beispiel 5 widerlegt (kein stiller Bypass, sondern Fail-Closed).
- `from importlib import import_module; import_module('openai')` -> kanten=[], dynamisch_unlesbar={}, extern={'importlib':[...]}, befunde=[] — STILLER BYPASS.
- `imp = __import__; imp('openai')` -> kanten=[], dynamisch_unlesbar={}, extern={}, befunde=[] — STILLER BYPASS.
- `import builtins; builtins.__import__('openai')` -> extern={'builtins':[...]}, befunde=[] — STILLER BYPASS (Attribut heisst `__import__`, Zeile 343 prueft nur `import_module`).
- `sys.modules.get('rechner_pipeline.kommutationskern.kommutation'); getattr(mod,'fuer')` (ohne begleitenden statischen Import) -> kanten=[], befunde=[] — STILLER BYPASS, entspricht Reviewer-Beispiel 4 (getattr).
Docstring-Ueberversprechen Zeile 22-26: "Dynamische Importe ... sind mitgeprueft" — stimmt nur fuer die zwei benannten Formen, nicht generell.

**Schaden.** code_karte.py ist die maschinelle Ratsche, die ADR-017 (Ebenen-Trennung Tool/Vorzeige), ADR-004 (Zweitkern-Konsument) und das SDK-Verbot (AGENTS.md: "src ist SDK-frei") "nachrechenbar statt Prosa" machen soll — ihr gruener Exit-Code (0) gilt als Beleg fuer Architektur-Konformitaet. Mit den gezeigten, voellig gewoehnlichen Python-Idiomen (`from importlib import import_module`, `imp = __import__`, `builtins.__import__`, `getattr`/`sys.modules` auf ein schon geladenes Modul) kann eine neue Kante Tool->Vorzeige, ein neuer Zweitkern-Konsument oder ein SDK-Import (`anthropic`, `openai`, `langgraph`, `langchain`) eingefuehrt werden, ohne dass die Karte es sieht — der Gate bleibt gruen, obwohl die Grenze real verletzt ist. Das ist ein falscher Beleg genau an der Stelle, die als Beweis fuer "kein SDK im Kern, Ebenen eingehalten" zitiert wird (auch gegenueber dem Maintainer/Reviewern/ADR-Abnahmen).

**Schwere.** Zustimmung zu hoch, aber mit Einschraenkung. Hoch gerechtfertigt, weil: (1) die Bypass-Formen sind keine exotische Obfuskation, sondern alltaegliche Python-Idiome, die auch unabsichtlich (z. B. von einem Agenten, der dynamisch ein Plugin laden will) entstehen koennten; (2) die Karte ist bewusst als maschineller ERSATZ fuer Prosa-Vertrauen konzipiert — eine Luecke darin untergraebt genau den Zweck, den Menschen/Gates sich auf sie verlassen. Einschraenkung: von den 5 im Befund genannten Beispielen sind 2 (aliasierter `importlib as x`, relative Imports) bereits nachweislich abgedeckt und 1 weiteres (String-Verkettung) ist kein stiller Bypass, sondern ein Hard-Block — der Reviewer hat also teils die falschen Beispiele zitiert, auch wenn die uebergeordnete These (Ratsche laesst sich mit dynamischen Importen umgehen) korrekt bleibt.

**Klasse (Invariante).** Ein AST-basierter Architektur-Detektor, der dynamische Modul-Referenzen ausschliesslich an einer festen, woertlich benannten Call-Form erkennt (hier: ast.Name mit id=="__import__" ODER ast.Attribute mit attr=="import_module"), macht jede zusaetzliche Indirektionsstufe zwischen Quelltext und tatsaechlicher Referenz — Umbenennung/Rebinding durch Zuweisung oder from-Import, einen anderen Empfaenger-Ausdruck mit gleichem Attributnamen, oder den Zugriff auf ein bereits geladenes Modulobjekt via getattr/sys.modules ganz ohne Import-Anweisung — fuer den Detektor vollstaendig unsichtbar, OHNE auch nur den eigenen Fail-Closed-Zweig (hier dynamisch_unlesbar) zu treffen; jede aus dem Graphen abgeleitete Regel (Schicht-Allowlist, Ebenen-Ratsche, Zweitkern-Regel, SDK-Verbot) gilt dann fuer diese Pfade nur behauptet, nicht erzwungen.

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/ontologie/code_karte.py:340-341 — derselbe dynamisch-Ausdruck: der Name-Zweig erkennt nur die woertliche Kette __import__, keine Umbenennung/Rebinding dieses Namens (Wurzel des Bypasses fuer imp=__import__).
- src/rechner_pipeline/ontologie/code_karte.py:342-343 — derselbe Ausdruck: der Attribut-Zweig prueft nur attr=="import_module", nicht attr=="__import__" (Wurzel des Bypasses fuer builtins.__import__).
- src/rechner_pipeline/ontologie/code_karte.py:22-26 — Docstring behauptet generelle Vollstaendigkeit ('Dynamische Importe ... sind mitgeprueft'), was fuer die oben gezeigten Formen nicht zutrifft; dieselbe Ueberversprechen-Klasse wie das eigentliche Erkennungsproblem.
- src/rechner_pipeline/ontologie/code_karte.py:329-337 (Alias-Attribut-Aufloesung fuer die Symbol-Sicht) — strukturell dieselbe Schwaeche (nur ast.Name-Empfaenger aufgeloest, getattr(...)()-Empfaenger nicht), ABER bereits im Docstring Zeile 28-31 offen als Untergrenze deklariert und wirkt sich nicht auf die Schicht-/SDK-Kanten selbst aus, sondern nur auf die feinere Symbol-Zuordnung — daher nicht dieselbe Schwere, aber dieselbe Wurzelursache (Musterabgleich statt Datenfluss).

**Fix-Umfang.** M fuer den engeren Teil (Name-/Attribut-Rebinding von __import__/import_module): so wie alias_zu_modul bereits Import-Aliase trackt, muesste ein dynamische_namen-Set zusaetzlich Bindungen von builtins.__import__ und importlib.import_module per Zuweisung/from-Import mitverfolgen, und der Attribut-Zweig muesste attr in {"import_module", "__import__"} statt nur "import_module" pruefen. L fuer den vollen Schluss der Klasse: getattr/sys.modules-Zugriff auf ein bereits geladenes, nicht in dieser Datei importiertes Modulobjekt ist aus EINER Datei nicht aufloesbar (fehlender Datenfluss zum urspruenglichen Import) — das braucht eine bewusste Policy-Entscheidung (ADR), z. B. jeden getattr-Aufruf mit literalem zweiten String-Argument bzw. jeden sys.modules[...]/sys.modules.get(...)-Zugriff in src pauschal als Befund zu fuehren (analog zum bestehenden Fail-Closed-Verhalten von dynamisch_unlesbar), da eine praezise Aufloesung eine Points-to-Analyse braeuchte, die hier bewusst nicht gebaut wird. Test, der die KLASSE faengt (nicht nur den Reviewer-Fall): parametrisierte Testmatrix mit je einem Fall pro Bindungsform (from-Import von import_module + Bare-Call, Neuzuweisung von __import__, Attributzugriff builtins.__import__, getattr/sys.modules auf ein extern geladenes Modul), jeweils mit 'openai' als SDK-Marker und Assertion, dass ein Befund entsteht — die zwei bereits vorhandenen Tests (test_karte_faengt_dynamischen_import, test_karte_meldet_unlesbaren_dynamischen_import) decken nur die 2 bereits funktionierenden Formen ab und wuerden die hier gezeigten 4 Luecken nicht faengen.

**freischaltung f7c545d.** Identisch — keine Abweichung. Der Diff b5fa737..f7c545d an src/rechner_pipeline/ontologie/code_karte.py (20 Zeilen) fuegt ausschliesslich neue Eintraege zu TOOL_NACH_VORZEIGE_ERLAUBT hinzu (Freischaltung-Feature, gates/bestand_uebernehmen.py und neues gates/fuehrungsprobe.py) und ruehrt die Dynamisch-Import-Erkennung (Zeilen 339-344) nicht an; tests/test_code_karte_und_impact.py hat 0 Zeilen Diff zwischen den beiden Commits. Die Luecke besteht auf f7c545d unveraendert fort.


### T23-08 — Reviewer mittel — Urteil: bestaetigt

**Beweis.** gates/gate_entscheid.py:1915-1938 baut `kern_inhalt` aus genau: command, gate_version, gate, entscheid, entscheider, rolle, begruendung, fall, artefakt_hashes, system (+ fall_scope/pflichtbelege bei aktuariellen Abnahmen/A-M4/A-K1, + pk1_belege bei A-M4). Zeile 1943-1951: `for pfad, daten in geltende: if all(daten.get(k) == v for k, v in kern_inhalt.items()): return ... "bereits_vorhanden": True` — der Vergleich laeuft ausschliesslich ueber diese kern_inhalt-Teilmenge, VOR jeder Zeichnungs-/Mandatspruefung. Erst danach, nur beim Bau eines NEUEN Snapshots (also wenn der Vergleich NICHT trifft), werden `zf = _zeichnungsfehler(...)` (Zeile 1982), die Simulation-ohne-Mandat-Sperre (Zeile 1996-2007) und `snapshot["zeichnung"] = zeichnung_fuer(ordnung, ordnung_sha256, schluessel_sha256, mandat_sha256)` (Zeile 1992-1995, models/zeichnung.py:206-223) sowie `snapshot["freigabe"] = _freigabe_fuer(...)` (Zeile 2009) ausgefuehrt. zeichnung_fuer liefert {rolle, ordnung_sha256, schluesselklasse, mandat_sha256}; von diesen vier Feldern steckt nur "rolle" (indirekt, als Top-Level-Feld) in kern_inhalt — ordnung_sha256, schluesselklasse und mandat_sha256 NICHT, ebenso wenig `freigabe.schluessel_sha256`/`signatur`. Ein Wiederholungsaufruf mit unveraendertem Fallstand/entscheider/begruendung, aber anderem Freigabeschluessel (anderer schluessel_sha256, andere schluesselklasse), anderer Zeichnungsordnung (anderer ordnung_sha256) oder anderem/fehlendem --mandat, der zufaellig auf dieselbe "rolle" abbildet, trifft den Idempotenz-Treffer und gibt exit 0 / bereits_vorhanden zurueck, OHNE dass _zeichnungsfehler oder die Mandatspflicht-Sperre (ADR-018, Review T22-07) fuer DIESEN Aufruf je ausgefuehrt werden. Die Lesepfad-Pruefung `_pruefe_g2_snapshot_semantik` (Zeile 418-458) prueft beim Laden nur Belegrollen/Pflichtbelege, nicht Zeichnung/Mandat — bestaetigt die vom Reviewer behauptete Schreib/Lese-Asymmetrie zusaetzlich.

**Schaden.** Ein erneuter gate_entscheid-Aufruf mit einem anderen (z.B. abgelaufenen, widerrufenen oder schlicht falschen) Freigabeschluessel, einer geaenderten Zeichnungsordnung oder einem geaenderten/fehlenden --mandat wird als "bereits_vorhanden": True mit exit 0 quittiert, sofern Fallstand, entscheider-String, begruendung und die daraus abgeleitete rolle unveraendert bleiben. Der auf der Platte liegende Snapshot bleibt zwar unveraendert (kein Ueberschreiben, keine falsche Datei), aber der AUFRUFER erhaelt eine scheinbare Bestaetigung, dass sein aktueller Schluessel/Mandat gueltig ist und die ADR-018-Mandatspflicht fuer Simulationsschluessel geprueft wurde — das ist falsch: die Pruefung lief nie fuer diesen Aufruf, sondern nur beim urspruenglichen, u.U. laengst obsoleten Snapshot. Der falsche Beleg/die falsche Annahme, die dadurch moeglich wird: "der aktuell verwendete Schluessel/das aktuelle Mandat wurde soeben gegen die Sperre geprueft und ist gueltig" — obwohl in Wahrheit nur der alte Snapshot erneut zurueckgegeben wurde.

**Schwere.** Zustimmung zu "mittel": Der Reviewer hat recht, dass die Klasse real ist und eine bewusst gebaute Sperre (ADR-018/T22-07) umgangen werden kann. Kein "hoch", weil (a) kein Artefakt korrumpiert wird — die persistierte Datei bleibt die urspruengliche, gueltig gezeichnete; (b) der Treffer eine exakte Uebereinstimmung von entscheider, begruendung, artefakt_hashes (voller Fallstand), system UND rolle voraussetzt — kein triviales Blindtreffen, sondern ein Szenario, das typischerweise nur bei einer echten Wiederholung desselben Kommandos mit rotiertem Schluessel/Mandat auftritt (genau der Fall, fuer den Idempotenz gedacht war). Kein "niedrig", weil es sich um einen stillen Bypass einer sicherheitsrelevanten, mit voller Absicht eingebauten Sperre handelt und der Fehler bei jedem --gate (nicht nur A-M4) greift.

**Klasse (Invariante).** Wenn eine Idempotenz-/Wiederholungspruefung einen NEUEN Aufruf nur gegen eine TEILMENGE der beim Neubau eines Datensatzes tatsaechlich gesetzten Felder vergleicht (hier: kern_inhalt statt des vollstaendigen Snapshots inkl. zeichnung/freigabe), dann werden alle Sperren und Validierungen, die NUR auf dem Neubau-Pfad (nach dem Vergleich) laufen, bei jedem als "inhaltlich gleich" erkannten Wiederholungsaufruf stillschweigend uebersprungen — auch wenn genau die von diesen Sperren geschuetzten Felder (hier: Zeichnungsordnung, Schluesselklasse, Mandat, Freigabeschluessel) sich zwischen den Aufrufen tatsaechlich geaendert haben.

**Weitere Stellen.** keine gefunden.

**Fix-Umfang.** M. Zwei moegliche, kombinierbare Aenderungen: (1) die Sperr-/Validierungslogik (_zeichnungsfehler, Simulation-ohne-Mandat-Sperre) VOR die Idempotenz-Kurzschlussschleife ziehen, sodass sie bei JEDEM Aufruf mit entscheid=="angenommen" laeuft, unabhaengig davon, ob am Ende ein Treffer gemeldet wird; (2) den Vergleichsschluessel kern_inhalt um die sicherheitsrelevanten Zeichnungsfelder erweitern (ordnung_sha256, schluesselklasse, mandat_sha256, ggf. freigabe.schluessel_sha256), sodass ein Aufruf mit geaendertem Schluessel/Mandat/Ordnung NICHT mehr als identisch gilt, sondern entweder eine neue (gekettete) Snapshot-Pruefung durchlaeuft oder explizit als Konflikt gemeldet wird statt als stiller bereits_vorhanden-Erfolg. Test der KLASSE (nicht nur des Reviewer-Beispiels): parametrisierter Test ueber mehrere --gate-Werte (A-Q1, A-M1, A-M4, A-K1), der zeigt, dass ein zweiter Aufruf mit identischem Fallstand/entscheider/begruendung aber (a) anderem gueltigem Freigabeschluessel derselben Rolle, (b) geaenderter Zeichnungsordnung-Datei (anderer ordnung_sha256, gleiche resultierende Rolle), und (c) fehlendem/geaendertem --mandat bei Schluesselklasse simulation NICHT als bereits_vorhanden mit exit 0 durchgeht, sondern die jeweilige Sperre bzw. einen neuen Snapshot ausloest.

**freischaltung f7c545d.** identisch — der Diff b5fa737..f7c545d auf gates/gate_entscheid.py aendert ausschliesslich _pruefe_g2_snapshot_semantik (dort kommt ein Systemstand-Gate hinzu, das den Belegrollen-Vertrag nur auf Snapshots des AKTUELLEN Standes anwendet, wegen der neu hinzugekommenen Fuehrungsprobe-Rolle) sowie die zugehoerigen _lade_snapshot_kette-Aufrufe. Der kern_inhalt-Aufbau (Zeile 1915-1938) und die Idempotenz-Kurzschlussschleife (Zeile 1943-1951) sind in f7c545d byte-identisch zu b5fa737 — die Schwaeche besteht dort unveraendert fort.


### T23-09 — Reviewer mittel — Urteil: bestaetigt

**Beweis.** src/rechner_pipeline/gates/gate_entscheid.py:406-415 (pruefe_tbox_aenderung, Funktion beginnt Zeile 366):
    artefakt = daten.get("artefakt")
    if not (isinstance(artefakt, dict) and isinstance(artefakt.get("pfad"), str)
            and isinstance(artefakt.get("sha256"), str)):
        fehler.append("artefakt {pfad, sha256} fehlt")
    else:
        kandidaten = [fall / artefakt["pfad"], Path(artefakt["pfad"])]
        datei = next((k for k in kandidaten if k.is_file()), None)
        if datei is None:
            fehler.append(f"artefakt {artefakt['pfad']!r} nicht gefunden")
        elif hashlib.sha256(datei.read_bytes()).hexdigest() != artefakt["sha256"]:
            fehler.append(f"artefakt {artefakt['pfad']!r}: Hash stimmt nicht")

Es gibt keinerlei relative_to(fall)/relative_to(repo_root)-Pruefung, keine Ablehnung absoluter Pfade, kein resolve(). Der Docstring (Zeile 372-375) behauptet "das Artefakt liegt im Fall oder im Repo" — das wird vom Code nicht erzwungen; er ist sogar schwaecher als behauptet: Der zweite Kandidat Path(artefakt["pfad"]) akzeptiert JEDEN absoluten Pfad auf dem Dateisystem, nicht nur "im Repo". Zusaetzlich verifiziert (python3 -c "print(Path('/fall')/'/etc/passwd')" -> "/etc/passwd"): Ist artefakt["pfad"] absolut, kollabiert auch der erste ("im Fall gemeinte") Kandidat fall/artefakt["pfad"] wegen der pathlib-Semantik (ein absoluter rechter Operand ueberschreibt den linken) auf denselben unbegrenzten Pfad — die vermeintliche Fall-Bindung existiert für absolute Pfade gar nicht erst. Die vom Reviewer genannte Stelle (Pfadbindung des Artefakts referenziert in abgeleitet/tbox/aenderung.json) trifft exakt zu; nur die Zeilennummer war ungenau (Reviewer nannte keine, korrekt ist 406-415, Kernzeile 410-411).

**Schaden.** Wer aenderung.json fuer A-K1 erzeugt (Mensch oder Agent mit Fall-Schreibzugriff), kann als "artefakt.pfad" einen beliebigen absoluten Pfad ausserhalb von Fall UND Repository angeben (z. B. eine Datei im eigenen Home, in /tmp, auf einem Netzlaufwerk) und deren aktuellen sha256 eintragen. Das Gate akzeptiert das als hinreichenden Beleg fuer die T-Box-Aenderungsbegruendung (ADR/Aenderungsvermerk), obwohl der Beleg gar nicht mehr im versionierten, fuer die Annahme massgeblichen Bestand (Fall-Snapshot oder Repo-Commit) liegt. Damit laesst sich eine spaeter unauffindbare, unversionierte oder nachtraeglich manipulierbare Rechtfertigung fuer eine T-Box-Version als formal gueltig durchwinken — die Zeichnung "meint" ein Artefakt, das niemand ausser dem Ersteller je wieder finden oder auf Unveraendertheit pruefen kann, weil es nicht mit dem Fall/Repo mitgezogen wird.

**Schwere.** Zustimmung, tendenziell eher hoeher als "mittel" einzuordnen. Grund: Das Repo hat fuer GENAU dieses Problem (extern referenzierter Autorisierungs-/Belegpfad) bereits zwei etablierte, sorgfaeltig gebaute Referenzmuster (Zeichnungsordnung/Freigabeschluessel: muss ausserhalb des Falls liegen, mit resolve(strict=True) + Pruefung von lexikalischem UND aufgeloestem Pfad gegen Symlink-Tricks; P-B1-Portfolio-Rolle: muss innerhalb des Falls liegen, via relative_to). pruefe_tbox_aenderung ignoriert beide Muster komplett und faellt auf einen blossen is_file()-Test zurueck — das ist kein Uebersehen einer Randbedingung, sondern das Fehlen der im selben Modul bereits vorhandenen Standard-Absicherung. Zusaetzlich fand sich eine zweite, sicherheitsrelevantere Instanz (--mandat, siehe unten), die direkt in die Signatur-/Autorisierungslogik von ADR-018 eingeht.

**Klasse (Invariante).** Jeder externe Belegpfad, der einer Gate-Annahme als Autorisierungs- oder Rechtfertigungsartefakt zugrunde liegt (ob als CLI-Argument oder als "pfad"-Feld in einem geladenen JSON-Dokument), muss gegen eine explizit definierte Fall-/Repo-Grenze gebunden sein (verpflichtend INNERHALB via relative_to(fall) wie bei P-B1-Portfolio, oder verpflichtend AUSSERHALB via die _unter/_ist_unter-Pruefung auf lexikalischem UND aufgeloestem Pfad wie bei Zeichnungsordnung/Freigabeschluessel) — ein blosser is_file()-Test auf einer Kandidatenliste unbegrenzter Pfade (inkl. absoluter Pfade) erfuellt diese Bindung nicht, gleich an welcher Stelle im Code er auftritt.

**Weitere Stellen mit demselben Muster.**

- src/rechner_pipeline/gates/gate_entscheid.py:1222-1225 — `--mandat <datei>`: `mandat_pfad = Path(args.mandat); if not mandat_pfad.is_file(): ...; mandat_sha256 = hashlib.sha256(mandat_pfad.read_bytes()).hexdigest()`. Der Hash wandert direkt in die signierte Zeichnung (`zeichnung_fuer(...)`, Zeile ~1994) und ist bei Schluesselklasse `simulation` PFLICHT (ADR-018, Review T22-07) — funktional dieselbe Rolle wie `--freigabe-schluessel`, das laut Hilfetext UND Code 'ausserhalb des Falls liegen' MUSS (Zeile ~170ff. in derselben Datei). Fuer `--mandat` fehlt diese Bindung vollstaendig: eine Datei INNERHALB des Falls wird anstandslos akzeptiert, obwohl ein Agent mit Fall-Schreibzugriff sich damit sein eigenes Mandat unterschieben koennte — dieselbe Klasse, aber sicherheitskritischer als der Reviewer-Fall, weil sie in die Signaturkette selbst eingeht, nicht nur in eine Dokumentationsreferenz.

**Fix-Umfang.** M — kein reiner Einzeiler, aber auch kein grosses Redesign, weil das korrekte Muster (models/zeichnung._unter + resolve(strict=True) auf lexikalischem UND aufgeloestem Pfad; alternativ _fall_scope.pruefe_artefakt_eintrag fuer "verpflichtend im Fall") im selben Repo bereits existiert und nur wiederverwendet/generalisiert werden muss. Noetig: (1) fuer pruefe_tbox_aenderung das artefakt["pfad"]-Feld gegen eine EXPLIZITE Grenze binden (fall/repo_root muessen dazu ueberhaupt erst in die Funktion durchgereicht werden — repo_root fehlt ihr aktuell komplett), inkl. Ablehnung absoluter Pfade und Symlink-Bindung wie im Zeichnungsordnung-Muster; (2) --mandat an dieselbe Pruefung wie --freigabe-schluessel anschliessen (oder bewusst dokumentieren+testen, warum es davon abweichen darf); (3) idealerweise einen gemeinsamen Helfer fuer "externer Autorisierungs-/Belegpfad" extrahieren, damit kuenftige Belegrollen ihn per Default bekommen statis lokal neu erfinden. Klassen-Test: ein parametrisierter Test ueber ALLE Belegstellen dieser Klasse (tbox_aenderung.artefakt, --mandat, und jede kuenftige), der fuer jede einen Pfad ausserhalb der erlaubten Grenze (z. B. eine tmp_path-Datei mit korrektem sha256, aber ausserhalb von Fall/Repo, sowie einen Symlink-Fall) einreicht und erwartet, dass das Gate ihn ABLEHNT — nicht nur ein Einzeltest fuer den vom Reviewer genannten Fall.

**freischaltung f7c545d.** Identisch — unveraendert. git diff b5fa737 f7c545d -- src/rechner_pipeline/gates/gate_entscheid.py zeigt Aenderungen nur an _pruefe_g2_snapshot_semantik (neues Systemstand-Gating) und _lade_snapshot_kette/_passende_bestandsbelege (neue Belegrolle "fuehrungsprobe"); pruefe_tbox_aenderung (Zeilen 366-419) ist im Diff nicht beruehrt, ebenso die --mandat-Verarbeitung (Zeile ~1222-1225 sowie Parser-Definition ~1121-1127) — beide Instanzen der Schwaeche bestehen auf f7c545d unveraendert fort.

## Nachtrag zur Umsetzung von Block 1 (dev-session, vor dem Bauen)

Ein Vollstaendigkeits-Grep ueber alle Lader (`lade`, `lade_spez`,
`lade_fragmente`, GM-Loader) und alle Hash-Helfer (`hash_files`,
`file_sha256`, `sha256_datei`, `_sha256_datei`) fand ueber die neun
Fundstellen der Triage hinaus weitere Instanzen derselben Klasse:

- gates/gate_entscheid.py — das P9-Gate hasht per `_sha256_datei` den
  P-Q3-Ledger (:1376), den T-Box-Aenderungsbeleg (:1392), Test und Bericht
  des Aktuartests (:1450/:1452), `fall.json` (:1731/:1798) und den
  Abnahmebericht-Ledger (:1049) — und parst jeden davon getrennt fuer die
  Validierung. Das ist die Klasse am signierenden Gate selbst.
- gates/verankerung_belegen.py:314 vs :402-403 — Spez geladen und getrennt
  gehasht (zehnte Instanz des Reviewer-Musters).
- qa/golden_master.py — `load_expected` liest `*_scalar.json` und
  `*_table_values.csv` selbst; generation_golden liest `scalar.json`
  damit DREIMAL (GM-Loader, Rohskalare, hash_files) und `table_values.csv`
  doppelt. Der Vergleich nutzt nur das Praefix des Kalkulationsblatts;
  einmaliges Lesen genau dieser beiden Dateien ist verdiktgleich.
- gates/abnahmebericht.py — die Renderer-Artefakte werden ueber
  `hash_files` UND `artefakt_eintrag` (sha256_datei) doppelt gehasht;
  zwei protokollierte Hashes derselben Datei koennen auseinanderlaufen.
- ontologie/entscheide.py — `_abox_sha256` (read_bytes) und `lade(fall)`
  (read_text) lesen die A-Box getrennt fuer Beleg-Hash und Verarbeitung.
- ontologie/kette.py `pruefe_kette` — Fragmente per `lade_fragmente`
  geparst und per `read_bytes` getrennt gehasht; ein Pruefer, der andere
  Bytes vergleicht als er hasht.
- gates/extract.py — die Quellmappe liest der Adapter (openpyxl/COM) ueber
  einen eigenen Kanal; COM kann keine Bytes annehmen. Benannte
  Reichweitengrenze (T22-08-Weg), kein Versprechen.

Schnitt des Fixes (Ebenenratsche): der Helfer "einmal lesen, hashen,
daraus parsen" (`GeleseneDatei`, `lies_gehasht`) liegt in
`models/manifest.py`; nur Gates nutzen ihn. Lader in ontologie/spez/qa
bekommen schlichte `*_aus_bytes`-Varianten (reine Bytes, kein
models-Import — spez darf models nicht importieren). Keine neue Kante.

Bei der Umsetzung zusaetzlich gefunden (durch den Lese-Zaehl-Test, der die
Gates tatsaechlich faehrt):

- quellen/formeln.py `pruefe_ratzu_staffeln` — der Formel-Check von P-Q3
  lud die A-Box fuer sich ein zweites Mal (`lade(fall)`); jetzt reicht das
  Gate die aus den gehashten Bytes geparste A-Box durch.
- gates/abox_validate.py -> ontologie/kette.py `pruefe_kette` — die
  Kettenpruefung lud die A-Box fuer den Merge-Vergleich selbst neu; auch
  hier reicht P-Q3 die geparste A-Box durch.

Umsetzungsstand Block 1: Helfer `models.manifest.GeleseneDatei` /
`lies_gehasht`, `gates._common.hashes_von`; `*_aus_bytes`-Varianten der
Lader (A-Box, Spez, Fragmente, GM-Erwartungswerte, Parquet, Fall-Manifest
ueber den gehaerteten Leser); alle genannten Gates und Pruefer umgestellt;
kein Hash-Wert aendert sich (derselbe Byte-Hash wie `file_sha256`); keine
neue Kante in der Ebenenkarte. Zwei Tests: die Konventions-Ratsche
(`tests/test_konvention_belegidentitaet.py`, je Funktion Ausdruecke, die
gehasht UND gelesen werden; Reichweite benannt) und der Lese-Zaehl-Test
(`tests/test_belegidentitaet_t23.py`, `Path.open` als Zaehlpunkt ueber
P-Q3, P-K1, abox_merge, A-K1, Aktuartest, Abnahmebericht; Ausgaben und
Quellcode ausgenommen, fall.json und verankerung_belegen als Grenze
benannt). `extract` bleibt dokumentierte Reichweitengrenze (COM-Adapter).

## Umsetzungsstand Block 2 — versionierter Evidence-Vertrag (T23-02, T23-03, T23-09)

T23-02: Der Modell-Default fuer Versionsfelder bleibt fuer die KONSTRUKTION
(eine frisch gebaute A-Box/Spez spricht das aktuelle Vokabular; befuellung,
erzeugen und Fixtures bauen ohne Angabe). Die LADER verlangen die
Deklaration im rohen JSON — `ontologie.abox.lade_aus_bytes`,
`spez.validierung.lade_spez_aus_bytes` (fail-closed nach dem Muster
`GateLedgerEntry.validate_payload`); die vier `from_dict` in
`models/schemas.py` (`CommonResult`, `QaReport`, `QaContract`,
`RunDossierV2Delta`) synthetisieren keine `schema_version` mehr
(`_pflicht_schema_version`). Bisher unverglichene Felder werden verglichen:
`spez.spez_version` gegen `SPEZ_VERSION`, `abox.schema_version` gegen
`ABOX_SCHEMA_VERSION`. Kein getracktes Artefakt war ohne Versionsschluessel
(geprueft), keine Fixture bricht.

T23-03: Der alte Stand ist im CODE nachweisbar — die T-Box deklariert ihre
Versionslinie `TBOX_VERSIONEN` (aelteste zuerst, wird bei jedem Bump
angehaengt, nie umgeschrieben). A-K1 verlangt: `nach_version` ist die
Version, die der Code traegt (wie bisher), `von_version` ist der
unmittelbare Vorgaenger von `nach` in der Linie, Semver-Ordnung aufwaerts.
Erfundene, rueckwaerts laufende und vorgaengerlose Uebergaenge werden
nicht signiert. Konsequenz, ehrlich: Die reale Linie hat ein Element
(`"0.1.0"`), es gab noch keinen Uebergang — derzeit ist kein A-K1
zeichenbar. Die A-K1-Tests tragen eine testlokale Linie
`("0.0.9", TBOX_VERSION)`, die zu ihrem Beleg passt. Die Alternative
(Versionen in den Snapshot schreiben, P9-Schema 8) wurde nach T22-07
(Schema 7) als zu schwer verworfen. Eine Kompatibilitaets-/
Migrationsaussage im Beleg (neues Pflichtfeld, Schema 2 der
Aenderungsdatei) ist NICHT Teil dieses Blocks — benannte Grenze; das
Artefakt (ADR/Aenderungsvermerk) traegt die Begruendung.

T23-09: Das A-K1-Artefakt muss ein relativer, kanonischer Pfad innerhalb
des Falls oder des Repos sein (`repo_root` wird durchgereicht); absolute
oder mit `..` hinausfuehrende Pfade werden abgewiesen. `--mandat` muss wie
Ordnung und Schluessel AUSSERHALB des Falls liegen — im P9-Gate und in
`ontologie.entscheide`, ueber `models.zeichnung.ausserhalb_des_falls`
(lexikalisch UND aufgeloest, wie bei der Ordnung).

Klassen-Test `tests/test_evidence_vertrag_t23.py`: je Leser ein JSON OHNE
Versionsschluessel (A-Box, Spez, vier Ergebnis-Schemata); die bisher
unverglichenen Felder; Linie konsistent zur Code-Version; Uebergang vom
deklarierten Vorgaenger gueltig, erfunden/rueckwaerts/vorgaengerlos
abgewiesen; Artefakt ausserhalb Fall+Repo abgewiesen, im Repo erlaubt;
Mandat im Fall verweigert (Helfer und P9-Gate).

Adversarialer Review Block 2 (ein Agent, Sonnet, Auftrag: widerlegen):
Drei Befunde, alle geschlossen, keiner blieb offen.

1. HOCH — der fail-closed Lader wurde an zwei lebenden Aufrufstellen
   umgangen: `generation_golden` (P-K1) und die P9-Annahmesperre in
   `gate_entscheid` parsten die A-Box direkt (`ABox.model_validate_json`).
   P-K1 war damit ungeschuetzt (eine A-Box ohne `tbox_version` bekam ein
   gruenes Golden-Master-Urteil), die Annahmesperre nur indirekt durch die
   P-Q3-Hashbindung gedeckt. Genau die Lektion dieser Runde: T23-02 als
   Fall (zwei Lader) haette die Luecke geschlossen, als Klasse (jeder
   Leser der Datei) nicht — der Agent fand die dritte und vierte
   Lesestelle. Beide laufen jetzt ueber `lade_aus_bytes`; der Test
   `test_pk1_laedt_die_abox_nicht_am_fail_closed_lader_vorbei` faehrt
   P-K1 gegen eine A-Box ohne Versionsdeklaration.
2. MITTEL — `ausserhalb_des_falls` las `../mandat.txt`, aus dem Fall
   heraus aufgerufen, lexikalisch als "im Fall" (pathlib.relative_to
   kollabiert `..` nicht) und wies ein legitim externes Mandat ab. Der
   Fehler war von `lade_zeichnungsordnung` geerbt (fail-safe, aber
   falsch) und mit Block 2 dupliziert. Beide Stellen normalisieren jetzt
   lexikalisch (`os.path.normpath`, ohne Symlinks aufzuloesen); die
   aufgeloeste Pruefung darunter faengt weiterhin Symlinks aus dem Fall
   hinaus. Test: `..`-Pfad nach aussen ist aussen, Symlink im Fall nach
   aussen bleibt innen.
3. Kosmetik — eine Leerzeile vor `@dataclass` in `models/schemas.py`.

Bestaetigt ohne Befund: Linie einelementig gefuehrt (kein IndexError),
Artefakt-Pfadbindung robust gegen absolute und `..`-Pfade, Produzenten
schreiben die Versionsschluessel, `from_dict`-Aufrufer ausserhalb der
Tests keine.

### Umsetzungsstand Block 3 (T23-04, T23-05) — auf ebenen nach Merge A

T23-04: Die Fallgrenze gilt fuer JEDE P-B1-Rolle des A-M4-Belegs, nicht nur
fuer das Portfolio (`abnahmebericht._b1_fehler`): Historie, Bewegungskonto
und vor allem die Config — die Rechnungsgrundlagen der Kern-Herleitung —
muessen im Fall liegen. Der P-B1-Hash belegte bisher nur, WELCHE Bytes
benutzt wurden, nicht ihre Herkunft; eine selbst gewaehlte Config konnte
Rechnungsgrundlagen und Ledgerbetraege passend machen. Konsequenz fuer
Fixtures und Faelle: die Bestand-Config liegt unter
`<fall>/abgeleitet/bestand-config.toml` (vier Fixtures umgestellt:
test_bestand_review_t20, test_pk1_am4_beweisvertrag zweimal,
test_am4_vollprofil_t22). Fuer den zweiten Lauf aendert sich nichts —
seine Zeichnungen liegen auf f7c545d; ein kuenftiger Lauf braucht die
Config im Fall (das war als "Config als registrierter Falleingang" ohnehin
offen, dev-docs/offene-punkte.md).

T23-05: Ein Zaehler, der eine Pruefung BEZEUGT, darf nicht null sein —
auch wenn Beleg und Nachrechnung sich einig sind (0 == 0 war "konsistent
gruen"). Katalog `PB1_PFLICHT_POSITIV` = portfolio_zeilen,
betraege_hergeleitet, manifest_gebunden; die Positivschwelle greift direkt
am Beleg (`betraege_hergeleitet <= 0`) und in der generischen
Vergleichsschleife fuer jeden Katalogzaehler. Fachlich geprueft und
bewusst NICHT im Katalog: historie_/scheiben_/ledger_zeilen (Bestand ohne
Vorgeschichte oder Erhoehungen ist moeglich), bewegungsjahre (ein Horizont
ohne vollstaendiges Kalenderjahr hat ein leeres Bewegungskonto — legitim,
`bewegungskonto` zaehlt nur volle Jahre) und sanity_baender (eine Config
ohne Plausibilitaetsbaender ist gueltig, `plausibilitaet` ist optional).
Ob A-M4 im Bestands-Scope Bewegungsjahre und Baender VERLANGEN soll, ist
eine fachliche Anforderung des Migrationscontrollings, kein Zaehlerbefund.
ENTSCHEID des Maintainers 2026-09-07: JA — beide sind Pflicht; ein
uebernommener Bestand wird nur abgenommen, wenn die Fortschreibung
mindestens ein volles Bewegungsjahr gegen das Bewegungskonto gehalten hat
und die Rechnungsgrundlagen Plausibilitaetsbaender tragen. Der Katalog
traegt deshalb wieder fuenf Zaehler, die Begruendung steht am Katalog.
Folge fuer Fixtures mit Uebernahme im laufenden Jahr (Horizont ohne volles
Kalenderjahr) oder Config ohne Baender: sie sind nicht abnahmereif und
muessen Horizont bzw. Config anpassen — betrifft keinen Test auf ebenen
(Suite gruen), voraussichtlich aber die Ein-Policen-Uebernahme-Fixture auf
freischaltung beim naechsten Vorwaerts-Merge (dort P-B1 mit
bewegungsjahre 0, sanity_baender 0).

Voraussetzung der Entscheidung, ausgesprochen (Fund der merge-session):
Das Bewegungskonto weist nur vollstaendige Kalenderjahre aus (Periode
(1.1.J, 1.1.J+1], ausgewiesen wenn 1.1.J+1 <= Horizont). Zwei Bestands-
Stichtage im selben Kalenderjahr koennen die Pflicht strukturell nicht
erfuellen. Der Fall-Scope prueft das jetzt am Eingang
(`_fall_scope.stichtage_fehler`: Stichtag 2 mindestens der 1. Januar des
Folgejahres von Stichtag 1), beim Erzeugen der Bindung UND bei der
Pruefung einer persistierten Bindung — fail-fast statt eines
Zaehlerbefunds am Ende. Die Nullzaehler-Meldung nennt je Zaehler Ursache
und Ausweg (`PB1_PFLICHT_POSITIV_URSACHE`). Baldrian Lauf 2 und beide
E2E-Faelle fahren 2026-01-01 -> 2027-01-01 und erfuellen die Regel; die
drei mitgelieferten Configs tragen 5-6 Plausibilitaetsbaender.
Test: tests/test_fall_scope_stichtage_t23.py.

Manifestbindung nachgerechnet (Fund des adversarialen Reviews): Das
Laufmanifest ist im P-B1-Beleg keine Eingangsrolle, sondern nur
`summary.manifest` = {sha256, horizont}. A-M4 rechnete ohne Manifest nach
— `manifest_gebunden` war im Katalog, aber unerreichbar, und die
Horizontbindung des Manifests wurde nie erneut geprueft. Jetzt sucht A-M4
das Manifest NEBEN dem Portfolio (dort schreibt es der Produzent), haelt
seine Bytes gegen den Hash des Belegs und gibt es in die Nachrechnung;
der Zaehler wird verglichen, die Schwelle greift. Kein Eingriff in den
P-B1-Vertrag; das Laden gehoert der P-B1-Engine
(`bestand.vorbedingungen.manifest_fuer_nachrechnung`), damit A-M4 keine
neue Modulkante in die Bestandsschicht braucht (Kanten-Ratsche ADR-017
unveraendert). Der zweite Lauf traegt kein Manifest (`manifest: null`),
er ist nicht betroffen.

Klassen-Test `tests/test_am4_vollprofil_t23.py`: Vollprofil im Fall ist
ein Beleg (Positivkontrolle); je Rolle (config, historie, ledger) ein
Exemplar ausserhalb des Falls wird abgewiesen; je Katalogzaehler der Fall
"Beleg und Nachrechnung sagen beide 0" ist ein Befund aus der Positiv-
schwelle, nicht aus dem Gleichheitsvergleich; das woertliche Reviewer-
Beispiel betraege_hergeleitet == 0.

Adversarialer Review Block 3 (ein Agent, Sonnet, Auftrag: widerlegen) —
drei hohe Befunde, zwei geschlossen, einer als Grenze benannt:

1. HOCH, GRENZE — die Produzentenseite von T23-04 fehlt: `bestand_validate`,
   `cli_fortschreibung` und `cli_abschluss` kennen keinen Fall (kein
   `--fall`), pruefen also keine Fallgrenze; die Klasse ist nur im
   Abnahmeschritt A-M4 geschlossen. Das ist bewusst so gelassen: P-B1
   laeuft auch im Tagesbetrieb auf einer Ablage OHNE Fall, und ein
   `--fall` an drei Produzenten waere eine Aenderung des Gate-Vertrags —
   ein Entscheid, kein Reparaturschritt. Der staerkere Mechanismus (Config
   als REGISTRIERTER Falleingang, dev-docs/offene-punkte.md) deckt die
   Herkunft am Ursprung; bis dahin gilt: A-M4 ist die Stelle, an der ein
   Fall seinen Beleg annimmt, und dort ist die Grenze vollstaendig.
   ENTSCHEID des Maintainers 2026-09-07: NEIN, keine Produzenten-
   Fallgrenze; der Weg ist "Config als registrierter Falleingang".
2. HOCH, GESCHLOSSEN — `manifest_gebunden` unerreichbar (siehe oben);
   der Test bestaetigte sich selbst, weil der Monkeypatch den Schluessel
   injizierte. Jetzt prueft der Test, dass der ECHTE Nachrechnungspfad den
   Zaehler liefert, und ein eigener Test faelscht den Zaehler und die
   Manifest-Bytes.
3. HOCH, GESCHLOSSEN — bewegungsjahre und sanity_baender legitim null;
   zunaechst aus dem Katalog genommen, Anforderung als Fachfrage benannt;
   Entscheid des Maintainers 2026-09-07: als Abnahmevoraussetzung wieder
   Pflicht (oben).
4. NIEDRIG, GESCHLOSSEN — die Meldungen nennen jetzt den Ausweg (Datei in
   den Fall legen; Nullzaehler ist ein Sachverhalt der Eingaben, kein
   Wiederholungsfall).

Bestaetigt ohne Befund: `relative_to` auf beidseitig aufgeloesten Pfaden
(Symlink/`..` gedeckt), Rollen ohne Zuordnung fallen schon am
Rollenvergleich, scheiben/merkmale laufen durch dieselbe Schleife, Bool/
None/negative Werte koennen die Schwelle nicht unterlaufen, die E2E-Faelle
legen ihre Config bereits im Fall ab.
