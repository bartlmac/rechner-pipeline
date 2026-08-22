# Fehlerkorrekturen der ToDos 10.1 bis 10.19

Stand: 21. August 2026

## Zweck und Geltungsbereich

Dieses Dokument fasst den nach den ToDos 10.1 bis 10.19 geltenden
Fehlerkorrekturstand der Migrationspipeline zusammen. Es beschreibt nur die
tatsächlich ausgeführten Korrekturen. Der vor ToDo 6.2 entstandene, zu breite
Zwischenstand von 10.3 mit einem allgemeinen Gate-DAG gehört ausdrücklich
nicht zum Ergebnis. Ebenfalls nicht Bestandteil sind die verworfenen reinen
Verbesserungsvorschläge 10.20 bis 10.22.

Die Architekturbegründung der signierten menschlichen Freigaben lebt in
`docs/architektur/adr-008-signierte-p9-freigaben.md`. Die fachlich
unterschiedlichen Pflichtbelege von Tarif- und Bestandsfällen sind in
`docs/architektur/adr-009-fall-scope-und-gate-dag.md` entschieden. Dieses
Dokument ist der zusammenhängende Fehlerkorrekturnachweis, kein Ersatz für die
ADRs, die Bedienhinweise in `README.md` oder die Pipelinebeschreibung.

## Ausgeführte Korrekturen

| ToDo | Behobener Fehler | Geltender Korrekturstand |
|---|---|---|
| 10.1 | Der letzte überschreibbare O3-Ledger konnte den exakten O3-Stand der von G-2 angenommenen A-Box-Generationen nicht beweisen. | O3 bindet die tatsächlich gelesenen A-Box-Bytes, Systemstand und Eingangsartefakte in unveränderlichen, inhaltsadressierten Belegen je Generation. G-2 verlangt exakt einen passenden grünen Beleg je aktueller Generation, hasht alle gebundenen Artefakte erneut und pinnt den verwendeten Belegsatz im G-2-Snapshot. |
| 10.2 | Frei editierbare oder nur oberflächlich geprüfte Ledger und P9-Snapshots ermöglichten manipulierte grüne G-2-Belege. | Ledger und Snapshots werden streng gegen Gate, Command, Version, Typen und Hashrollen validiert. Snapshot-Eigenhash, Vollhash-Dateiname und vollständige Vorgängerkette werden neu berechnet. Menschliche Annahmen benötigen eine HMAC-SHA-256-Freigabe mit einem außerhalb des Falls verwalteten Schlüssel; Schlüsselpfad und Schlüsselbytes werden nicht persistiert. Nichtskalare Listenwerte führen kontrolliert zu Schemafehlern statt zu Validator-Abstürzen. |
| 10.3 | G-2 unterschied reine Tarif- und Bestandsfälle nicht zuverlässig und konnte bei Bestandsfällen ohne passende Bestandsnachweise grün werden. | `fall.json` deklariert den Scope `tarif` oder `bestand`. Tariffälle benötigen O1-Ledger, G-1-Snapshot und O3-Belege. Bestandsfälle benötigen zusätzlich B1-Ledger, vollständig geprüfte Zwei-Stichtags-Migrationssuite und Abnahmebericht auf demselben Portfolio-, Fall- und Systemstand. G-2 prüft deren Hashes und Semantik erneut; ein fehlender oder nachträglich herabgestufter Scope blockiert. |
| 10.4 | Der Abnahmebericht vertraute widersprüchlichen, aus dem Suite-JSON übernommenen Einzelurteilen, Residuen, Zählern und Zusammenfassungen. | Residuen, Toleranzurteile, Vertragsurteile, Mengenbefunde, Prüflücken, Zähler und Suiteurteile werden aus den atomaren Fakten neu berechnet und typgenau abgeglichen. G-2 wiederholt die kanonische Ableitung; eine konsistent neu gehashte rote Suite kann nicht über eine alte grüne Ledger-Summary angenommen werden. |
| 10.5 | Eine grüne Suite konnte trotz Zeilenverlust, Transformationsbefunden, offenen Konflikten, Prüflücken oder fehlenden Pflichtartefakten einen erfolgreichen Abnahmebericht erzeugen. | Der Bericht bleibt binär und ist nur ohne Abnahmehindernis `passed`. Spec, Transformationsergebnis sowie verschiedene Vor- und Nachberichte sind Pflicht. HTML-Aussage, Exit-Code und Ledger entstehen aus demselben Verdikt. G-2 prüft Inhalt, Hash, kanonische Pfade und physische Disjunktheit aller Renderer-Rollen einschließlich Output und Ledger erneut; Symlink-, Hardlink- und Pfadalias-Angriffe blockieren. |
| 10.6 | Fehlende Erwartungsbeträge für STO, TOD, ABL oder PEX wurden als ausgelassene Vergleiche verschwiegen. | Für jeden fehlenden Betrag entsteht eine konkrete Prüflücke `gevo_<art>_monat_<n>`. Die fachliche Zustandswirkung bleibt erhalten, aber `vollstaendig_geprueft` wird falsch und der Abnahmebericht kann nicht grün werden. |
| 10.7 | Nach einer Konfliktentscheidung konnte O1 Provenienz aus einer verworfenen Lesart akzeptieren. | O1 erlaubt nur Belege aus Lesarten, deren Wert dem gewählten Wert entspricht, verlangt mindestens einen solchen Beleg und verbietet gemischte Provenienz mit Belegen verworfener Lesarten. |
| 10.8 | Der Tafelimport band `Tafeln.csv` nicht lückenlos an Exportmanifest und registrierte XLSM; gekürzte Hashes erschwerten den Nachweis. | Der Import prüft XLSM-Register, Manifestquelle und konkrete Blatt-CSV als geschlossene Kette aus Dateiname, Bytezahl und vollständigem SHA-256. Fehlende, alte oder manipulierte Kettenglieder blockieren auch im Dry-Run. Die sechs ausgelieferten TG2015-Tafeln tragen vollständige, aus einer reproduzierten Exportkette nachgewiesene Provenienz. |
| 10.9 | Nicht endliche oder außerhalb von `[0,1]` liegende qx-Werte sowie doppelte, nicht ganzzahlige oder lückenhafte Altersvektoren konnten importiert oder aus Kern-XML geladen werden. | Import, Dry-Run, programmatisches Einfügen und Kern-XML-Lader erzwingen endliche qx einschließlich der zulässigen Grenzen 0 und 1 sowie das exakte Altersgitter `0..123`. Select-Tafeln werden je `(Alter, Dauer)` vollständig geprüft. Der Kern wurde wegen des verschärften Ladevertrags auf Version 3.0.1 angehoben; gültige Rechenwerte blieben unverändert. |
| 10.10 | Die Quellenregistrierung konnte über gültige oder dangling Symlinks außerhalb von `eingang/` schreiben und solche Fälle anschließend als unversehrt ansehen. | Quelle, Eingangsverzeichnis, Register und Zieldatei werden an No-Follow-Grenzen geprüft. Kopien werden exklusiv und soweit verfügbar relativ zu einem geöffneten Verzeichnisdeskriptor erzeugt; Quell- und Kopierhash müssen übereinstimmen. Symlinks, schreibbar gewordene Kopien und strukturell defekte Register erzeugen kontrollierte Fallfehler. |
| 10.11 | B1 verlor unbekannte physische Parquet-Spalten durch eine frühe Spaltenauswahl und prüfte den Basisstatus unvollständig. | Das physische Arrow-Schema wird vor Pandas-Konvertierung und Auswahl rollenbezogen geprüft. Der Basisbestand verlangt `status_id == 1`, `status_code == POL`, `status_date == insurance_start` und einen Monatsersten. G-2 nutzt bei seiner erneuten B1-Prüfung denselben Vertrag. |
| 10.12 | Nach einem aktuellen Gate-Fehler oder einer Exception konnte ein älterer grüner Latest-Ledger stehen bleiben; ein Fehler beim Schreiben des neuen Belegs konnte einen grünen Ausgang maskieren. | Jeder Gate-Lauf ersetzt vor der Facharbeit den alten Beleg durch einen schema-validen roten Startbeleg. Der Abschluss wird über eine synchronisierte temporäre Datei atomar publiziert. Unerwartete Exceptions behalten die richtige Gate-Bindung; ein Schreibfehler erzwingt `failed`, Exit 50 und lässt den roten Startbeleg lesbar. |
| 10.13 | Transformationsspezifikationen akzeptierten Scheinentscheidungen, ungültige Hashes und falsche Berechnungsaritäten. Quelle, Spec, Ergebnis und geprüftes Ziel konnten nur behauptet statt physisch gebunden sein. | `validate_spec` prüft Entscheidung, Entscheider, SHA-256 und die exakte Arity jeder Berechnung. Die öffentliche API `gates.transformation_anwenden.wende_an(spec, fall)` löst ausschließlich eine registrierte, erneut integritätsgeprüfte CSV auf. Abnahmebericht und G-2 vergleichen Quellbytes, Header und Zeilenzahl, Spec, Transformationsergebnis und das von B1 und Suite geprüfte Ziel. Ein fallloser Renderer bleibt möglich, ist aber nicht autoritativ und immer rot. |
| 10.14 | Verschiedene Excel-Blattnamen konnten nach der Bereinigung dasselbe Roh- oder Folgeartefakt überschreiben. | Beide Excel-Backends planen vor dem Schreiben deterministische, plattformportable und für alle Folgeartefakte disjunkte Dateinamen. `sheet_artifacts` bindet Originalblatt und tatsächlichen Dateinamen im Manifest. Writes erfolgen atomar und folgen keinen Links; der Tafelimport löst das Originalblatt über diese Bindung auf und liest exakt die zuvor gehashten Bytes einmal. |
| 10.15 | Parallele Registrierungen konnten denselben alten Registerstand lesen und gegenseitig Einträge aus `eingang.json` verlieren. | Ein fallbezogener Betriebssystem-Lock serialisiert den gesamten Read-Modify-Write-Pfad pro Fall. Das vollständig sortierte Register wird synchronisiert und atomar per `os.replace` publiziert. Lockziele werden gegen Symlink-, Hardlink- und Sonderdatei-Aliase geschützt. |
| 10.16 | Das Bestandsprofil prüfte die Breite einzelner CSV-Datenzeilen nicht exakt und konnte fehlende oder zusätzliche Felder falsch profilieren. | Jede Datenzeile muss nach regulärem CSV-Parsing exakt so viele Felder wie der Header enthalten. Abweichungen nennen Zeilennummer sowie erwartete und gefundene Feldzahl; korrekt gequotete Felder mit Trennzeichen bleiben zulässig. |
| 10.17 | Fehlende oder ungültige Gate-CLI-Argumente endeten vor dem gemeinsamen Ergebnis- und Ledger-Vertrag. | Die sieben Gate-CLIs G0, O0, O1, O3, P9, B1 und G-2-Vorlage geben bei Usage-Fehlern genau ein strukturiertes Fehler-JSON auf stdout aus, verwenden den definierten Exit-Code und erzeugen einen aktuellen roten Beleg. `--help` bleibt Exit 0 und beginnt keinen Gate-Lauf. Ungültige dynamische P9-Gate-Namen können keinen Pfad außerhalb des Diagnostics-Ordners bilden. |
| 10.18 | Auf case-insensitiven macOS-Dateisystemen erzeugte die Code-Karte bei Symbol-/Modulkollisionen Phantomkanten und scheiterte beim Rendering mit `KeyError`. | Modulpfade werden segmentweise mit der tatsächlichen Groß-/Kleinschreibung aufgelöst. Paketsymbole wie `Rechenkern` und echte Untermodule bleiben unterscheidbar; jede Kante zeigt auf ein erfasstes Modul und alle Landkartenformate rendern portabel. |
| 10.19 | Pflicht-E2E-Tests für O3 und G-2 hingen von einem gitignorierten lokalen Archivfall ab und wurden im frischen Clone übersprungen. Das erste Ersatzfixture enthielt außerdem personenbezogene Office-Metadaten. | Ein kleines synthetisches XLSM-Fixture samt Fallvertrag, Quellhash und unabhängigen O3-Sollerwartungen ist versioniert. Fehlendes oder hashabweichendes Fixture ist ein harter Testfehler. Die verwendete XLSM liegt anonymisiert im Fixture-Verzeichnis: `lastModifiedBy`, externer Herkunftspfad und externe Office-Relationships fehlen; VBA, Formeln und Nutzblätter bleiben erhalten. Die CI führt acht benannte Pflicht-E2E-Tests vor der Vollsuite aus. |

## Auswirkungen auf Bedienung und bestehende Fälle

Die Korrekturen verschärfen vorhandene Verträge fail-fast. Für bestehende
Arbeitsbereiche sind insbesondere diese Folgen relevant:

- Eine menschliche Annahme benötigt einen extern verwalteten
  Freigabeschlüssel. Alte P9-v1-Snapshots werden nicht still migriert; sie
  werden revisionsfest archiviert, O1 wird auf dem aktuellen Stand erneut
  ausgeführt und der Mensch entscheidet neu.
- Ein Fall benötigt einen gültigen Scope. Ein Bestandsfall kann G-2 nur mit
  B1, vollständiger Zwei-Stichtags-Suite und autoritativem Abnahmebericht auf
  demselben Bestand und Systemstand erreichen. Ein reiner Tariffall benötigt
  diese Bestandsbelege bewusst nicht.
- Alte Excel-Exporte ohne die vollständige XLSM-Manifest-CSV-Hashkette werden
  aus der registrierten XLSM neu mit G0 erzeugt. Das ersetzt keine Quelle im
  Eingangsregister.
- Eine Bestandstransformation wird über die fallgebundene öffentliche API
  ausgeführt. Ein frei gewählter CSV-Pfad oder ein falllos gerenderter
  Abnahmebericht besitzt keine Abnahmeautorität.
- Jeder fehlgeschlagene Gate-Lauf hinterlässt einen aktuellen roten Beleg.
  Automatisierungen dürfen daher weder einen älteren grünen Ledger verwenden
  noch unstrukturierten Parserausgaben vertrauen.

## Bewusste Grenzen

- Die Latest-Ledger bleiben einfache aktuelle Belege. Eine vollständige
  unveränderliche Attempt-Historie mit separatem Latest-Pointer wurde für den
  reproduzierten Fehler nicht benötigt und nicht gebaut.
- Die HMAC-Freigabe bildet eine verwaltete Schlüsselrolle ab. HSM,
  Betriebssystem-Keychain, asymmetrische Signaturen und Mehrpersonenfreigaben
  bleiben eigenständige spätere Entscheidungen.
- Das versionierte O3-/G-2-Fixture belegt einen synthetischen Modellpunkt und
  eine Ratenzuschlagsstaffel. Es ersetzt keinen vollständigen realen
  Migrationsfall und enthält keine Kundendaten.
- Die Korrekturen fügen keine Netzwerk-, RPC-, Provider- oder LLM-Laufzeit in
  den deterministischen Produktcode ein.

## Abschließender Prüfstand

Der Endstand nach dem Anonymisierungs-Korrekturpass von 10.19 wurde mit
CPython 3.12.14 und den gepinnten Projektabhängigkeiten geprüft:

| Prüfung | Ergebnis |
|---|---|
| Vollständige Pytest-Suite | 917 bestanden, 0 übersprungen |
| CI-Pflichtauswahl für O3/G-2 im Arbeitsbaum | 8 bestanden |
| CI-Pflichtauswahl in einer Kopie nur aus Git-erfassbaren Dateien | 8 bestanden |
| Python-Kompilierung von `src` und `tests` | bestanden |
| `git diff --check` | bestanden |
| `code_index --tests tests` | kein Drift (`drift: []`) |
| `code_karte` | keine Architekturbefunde (`befunde: []`) |

Die früheren sechs macOS-Fehler der Code-Karte wurden durch 10.18 behoben.
Die vier früheren Archivfall-Skips wurden durch 10.19 entfernt. Damit ist die
abschließende Vollsuite grün und enthält keinen übersprungenen Test.
