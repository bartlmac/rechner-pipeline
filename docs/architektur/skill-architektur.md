# Skill-Architektur: die Agenten-Rollen des Gesamtsystems

Stand: 2026-11-05 (ADR-032: Aufgabenvertraege und Hosteinbindung).
Die Skills tragen das Wissen,
mit dem die Agentenrollen urteilen. Sie sind im Repository versioniert und
für beide Werkzeuge gespiegelt (`.claude/skills/` und `.agents/skills/`,
die Gleichheit prüft ein Test), und ihr Git-Stand gehört in die Herkunft
jeder Aussage eines Agenten (Akteur-Konvention
``<modell>/<skill>@<git-sha-kurz>``, P1).

## Die Verteilungsregel

Die Regel steht auch im Dokument zur Migrations-Pipeline; hier legt sie die
Grenzen der Skills fest.

Was gelten muss, lebt in Code und Gates (erzwungen, nicht empfohlen).
Was Urteilen anleitet, lebt in Skills. Was zeigt, lebt im
Präzedenzfall. Ein Skill, der versucht, Geltung zu erzeugen („bitte
halte dich an …“), ist ein Architekturfehler; die Regel gehört dann in ein
Gate oder einen Validator.

## Rollen-Katalog: die fünf Agentenrollen des KI-Tools (ADR-018)

Skills sind Fähigkeiten; Rollen sind, wer sie in welchem Auftrag ausübt.
Es gibt fünf Agentenrollen, versioniert als Definitionen unter
`.claude/agents/` (gespiegelt in `.agents/agents/`, die Gleichheit prüft
ein Test). Sie legen vor und zeichnen keine Abnahme; jede hat ein
menschliches Gegenstück, das mit seinem Schlüssel zeichnet. Es trägt seit
dem Entscheid vom 2026-09-16 denselben Namen mit dem Präfix `mensch/`:
`agent/rechenkern` legt vor, `mensch/rechenkern` zeichnet.

| Agentenrolle | Ziel (Perspektive eines laufenden Unternehmens) | Skills |
|---|---|---|
| `agent/aktuariat` | fachlich richtig abgebildet: Transformation, drei aktuarielle Abnahmen, Controlling, Bestandsfortführung | transformiere-quellbestand, extrahiere-quellfragment, bereite-fachkonflikt-auf, `aktuartest-durchfuehren`, `pruefe-migrationscontrolling` |
| `agent/architektur` | in der vorgegebenen Architektur: Schichtenkarte, Nachweiskette, Vertrauensgrenzen, Betrieb | entwickle-im-zielsystem (als Maßstab), author-rechner-toolbox-gate, teste-adversarial, integriere-migrationsinkrement, dokumentiere-system |
| `agent/rechenkern` | stabiles Zielsystem: Regressionstests, Referenzwerte, Doku, Inkremente unter ADR-007 | entwickle-im-zielsystem, integriere-migrationsinkrement, teste-adversarial, dokumentiere-system |
| `agent/betrieb` | der übernommene Bestand wird danach richtig geführt: Zugangsprobe (A-B2), Anfangsbestand einer neu aufgesetzten Ablage (A-B3), Auslieferung eines Stands (A-B1) | `uebernehme-migrationsbestand` fuer Zugang/A-B2; A-B1/A-B3 gesondert nach `plv/betrieb/README.md` |
| `agent/programmleitung` | Migration effizient geliefert; orchestriert die vier anderen, hält an jedem Gate an | `migrationsfall-durchfuehren` |

Die Gegenseite des abgebenden Hauses (`mensch/quell-aktuar`) hat kein
Agenten-Gegenstück: Sie liefert, sie zeichnet keine Abnahme des
aufnehmenden Unternehmens. In der Vorführung werden alle menschlichen
Rollen simuliert (Schlüsselklasse `simulation`); die Regie der
Vorführung hält ihre Auftragsprofile (ADR-017).

## Skill-Katalog (v1, Fähigkeiten je Skill)

| Rolle | Skill | Kern-Auftrag | Härte-Grenze (was der Skill nicht darf) |
|---|---|---|---|
| Fall-Orchestrierung | `migrationsfall-durchfuehren` | einen Migrationsfall systematisch durch die drei Stufen und Gates führen | menschliche Gates überspringen; Diskrepanzen endgültig auflösen |
| Quell-Extraktion | `extrahiere-quellfragment` | Eine Quelle in ein QuellFragment übersetzen (Structured Output, generiertes Schema) | die andere Quelle sehen; raten statt `nicht_belegt`; Rohquellen lesen |
| Entwicklung | `entwickle-im-zielsystem` | Code unter der nicht verhandelbaren Architektur bauen (Schichtenkarte, Determinismus, Fail-fast, Knoten-Annotation, Test-Pflicht); als lesender Prüfmaßstab auch Architektur-/Diffreviews | Architektur „pragmatisch“ brechen; ohne Tests committen; Kern-Verankerungen anfassen; aus einem Lesereview ein Schreibmandat ableiten |
| Qualitätssicherung | `teste-adversarial` | Blöcke adversarial reviewen (Finden -> Widerlegen -> Fixen -> Regressionstest) und die Test-Disziplin tragen (Mutations-Denken, unabhängige Kontrollrechnung); READ-ONLY-Befunde, Gegenbeispiele und Testanforderungen ohne Schreibmandat, volle Fix-/Mutations-/Reattackrunde nur mit Fix-Mandat und Nachweis | Findings ungeprüft übernehmen; grüne Suiten als Beleg für Vollständigkeit lesen; eine Vollrunde ohne ihre Nachweise behaupten |
| Dokumentation | `dokumentiere-system` | Doku unter den Repo-Regeln (generiert schlägt handgeschrieben, ein Zuhause je Typ, ADR-Format, Ehrlichkeits-Abschnitte) | Inhalte doppeln (Drift); Grenzen beschönigen |
| Quellbestand-Transformation | `transformiere-quellbestand` | Mapping des gelieferten Bestandsabzugs in die Ziel-Ontologie vorschlagen (TransformationsSpec); Berechnungen nur aus dem Katalog, Unklarheit wird offener Konflikt; autorisierter Transfer einer dokumentierten menschlichen Mappingentscheidung samt Fundstelle mit menschlichem Spec-Abgleich | Mapping anwenden oder prüfen (deterministischer Code); offene Konflikte selbst entscheiden (Mensch, A-Q1); automatischen Transfer oder Signaturnachweis behaupten; Ontologie erweitern (A-O1) |
| Fachkonflikt-Aufbereitung | `bereite-fachkonflikt-auf` | Diskrepanzen verifizieren, einordnen, Auswirkungen rechnen, Entscheidungs-Dossier mit Empfehlung liefern, dann anhalten | entscheiden (auch nicht „offensichtliche“ Fälle); Quellen-Hierarchie festlegen |
| Gate-Autorenschaft | `author-rechner-toolbox-gate` | neue Prüf-CLIs unter dem Ledger-/Exit-Contract entwerfen und ihren Vertrag read-only gegen die Konventionen prüfen (additiv zu entwickle-im-zielsystem, ohne Schreibmandat) | Fachlogik außerhalb des Prüfens; aus einem Gatevertrags-Review ein Schreibmandat ableiten |
| Aktuarieller Test | `aktuartest-durchfuehren` | die drei Abnahmen je Vertrag an seinen eigenen Rechenpunkten fahren (Engine, aktuartest-Gate) und je Abnahme eine Vorlage aufbereiten: A-M1 Stichtagstest, A-M2 Verlaufstest, A-M3 Geschäftsvorfalltest | abnehmen (Mensch, A-M1); Werte selbst rechnen; interpolieren oder summieren (Engine verbietet es); Toleranzen aufweichen |
| Migrationscontrolling | `pruefe-migrationscontrolling` | deterministisches Controlling über zwei Stichtage über den gesamten Bestand (Migrationssuite, GeVo-Vergleich, Mapping-Tabelle, Bestandsberichte vor/nach) als A-M4-Vorlage für Gate A-M4 aufbereiten | abnehmen (Mensch, A-M4); Werte selbst rechnen; Toleranzen aufweichen; Erwartungswerte „korrigieren“; allgemeine Migrations-Prüfaufträge ohne A-M4-Beleg als A-M4 laufen |
| Migrations-CI | `integriere-migrationsinkrement` | Code-Änderungen während laufender Migrationen als kleine knotengebundene Inkremente integrieren (ADR-007: Impact, Gesamt-Suite inkl. aller Fälle, benanntes Staging) | langlebige Branches oder Kern-Forks; Landung ohne fallübergreifenden Beweis; Rückgrat ohne Koordination; Push (Mensch) |
| Betriebszugang | `uebernehme-migrationsbestand` | Zugangsprobe, menschliche A-B2-Uebergabe und mandatierte Registrierung | menschliche Gateannahme; Weltaufbau/A-B3, Auslieferung/A-B1 oder Tageslauf implizit ausfuehren |

## Aufgabenvertrag und Auswahl (ADR-032)

`AGENTS.md` bestimmt den Geltungsbereich des vollstaendigen Aufgaben-/
Rueckgabevertrags: mandatierte Arbeit der fuenf KI-Tool-Rollen und Fallarbeit.
Betriebsrollenarbeit gehoert auch ohne Migrationsfall dazu; Entwicklung
durch eine Fachrolle bleibt Rollenarbeit. Eigenstaendige Entwicklung,
allgemeine Exploration und reine Dokumentation ausserhalb solcher Aufgaben
folgen den allgemeinen Repo-Regeln und dem jeweiligen Skill, ohne
obligatorischen vollstaendigen Rollen-/Fallvertrag. Die folgende
Skillauswahl gilt nach Arbeitstyp; sie erweitert keine Quellen-, Gate-
oder Mandatsrechte. Pflichtskills
und aktuelle Phasenreferenzen werden vor Arbeit geladen. Ein gesperrter
Skill blockiert; nur ein fehlendes Werkzeug erlaubt gemeldete lokale
Lektuere. Verfahrens-/Schemaunterlagen sind getrennt von fachlichen
Quellen. Genau eine Vorverdichtung je Extraktionssitzung; keine Ergebnisse
anderer Extraktionen. Ladebeleg und Selbstauskunft sind keine Anwendung
oder Abnahme. Widersprueche zwischen Auftrag und Verfahren: STOPP.

| Arbeitstyp / Modus | Pflichtskill | Ergaenzung und Halt |
|---|---|---|
| Programmleitung / Fall | `migrationsfall-durchfuehren` | Aktuelle Phasenreferenz, getrennte Fachauftraege. |
| Quellenfragment / Fall | `extrahiere-quellfragment` | Eine Quelle/Generation; Merge separat deterministisch. |
| Bestandsmapping / Fall | `transformiere-quellbestand` | Fachkonflikt mit `bereite-fachkonflikt-auf` vorbereiten; menschlich entscheiden. |
| Fachkonflikt / Fall | `bereite-fachkonflikt-auf` | Fachrolle nach Konfliktgegenstand; keine endgueltige Agentenentscheidung. |
| A-M1/A-M2/A-M3 / Fall | `aktuartest-durchfuehren` | Je Abnahme eigene Probe/Nachweise; keine A-M4-Ersatzpruefung. |
| A-M4 / Fall | `pruefe-migrationscontrolling` | Vorherige Abnahmen, Linie und Standannahmen muessen gelten. |
| Zugang/A-B2 / Betrieb | `uebernehme-migrationsbestand` | Menschliches A-B2 vor Registrierung. |
| Implementierung / Entwicklung | `entwickle-im-zielsystem` | Migrationsbedingt zusaetzlich `integriere-migrationsinkrement`; substantieller Abschluss `teste-adversarial`. |
| Gateimplementierung / Entwicklung | `entwickle-im-zielsystem` und `author-rechner-toolbox-gate` | Allgemeine Architektur plus spezielle CLI-/Ledgerkonventionen, keine gegenseitige Ausnahme. |
| Architektur-/Diffreview (read-only) / Entwicklung | `entwickle-im-zielsystem` | Als Pruefmassstab, lesend, ohne Schreibmandat; Gatevertrags-Review zusaetzlich `author-rechner-toolbox-gate`. |
| Review-/QA-Auftrag / QA | `teste-adversarial` | Read-only-Befunde/Gegenbeispiele/Testanforderungen; volle Fix-/Kalibrierungs-/Mutations-/Reattackrunde nur mit Schreibmandat und Nachweis. |
| Systemdokumentation | `dokumentiere-system` | Reine Doku erfordert keine Implementierungs-/Adversarialrunde. |

Rolle allein loest keinen Entwicklungsskill aus. Ein Pruefmassstab oder
Sitzungswechsel ist kein Entwicklermandat; das Laden eines Skills ist
keine Anwendungsfreigabe. Kein Agent schreibt waehrend laufender
Migration an T-Box/Kern, auch nicht in einer getrennten Sitzung.
Gewuenschte Komposition ist die Regel: Der Fallskill laedt seine
Phasenrouter, die Router verweisen auf Fachskills, Fachskills tragen
eigene Fachreferenzen. Solche Bezuege sind ausdrueckliche Pflicht-Skills
und benannte Referenzen im Text, keine erfundene Parent-Vererbung.

## Hosteinbindung und Quellen der Rollen

Claude nutzt `.claude/agents/` und `.claude/skills/`; `.agents/` bleibt
byteidentischer gemeinsamer Rollen-/Skillbaum. Codex-Adapter liegen unter
`.codex/agents/*.toml`, OpenCode-Adapter unter `.opencode/agents/*.md`.
Die Adapter verweisen lesend auf `.agents/agents/<rolle>.md`; dies ist
eine Promptanweisung, keine technische Vorladung. Keine Modelle oder
Permissions werden konfiguriert; Hostrechte werden geerbt und erlaubte
Arbeitsorte muessen im Auftrag begrenzt bleiben.

Programmleitung fuehrt die Hauptsitzung; Facharbeitspakete benoetigen
keine Weiterdelegation. Registrierung, Tool-/Skillzugang und native
Delegation sind je Host/Version real zu pruefen. Bis dahin ist die
native Einbindung **nicht nachgewiesen**: Der Mensch startet bei Bedarf
eine Fachsitzung mit explizitem Rollen-/Auftragsvertrag und Dateiuebergabe.
Nach Adapteraenderungen betreffende Hostsitzung neu starten.

## Zusammenspiel (wer übergibt an wen)

```
migrationsfall-durchfuehren
  |- Vorbereitung: Linie und menschliches A-M6 (Fallauftrag)
  |- Stufe 1 (Tarifparameter): n x extrahiere-quellfragment
  |     --> deterministischer Merge
  |     Konflikt --> bereite-fachkonflikt-auf --> Mensch (entscheide + A-Q1)
  |- Stufe 1b (Bestandsabzug): quellen/bestand_profil (Code, Vorverdichtung)
  |     --> transformiere-quellbestand --> TransformationsSpec
  |     --> ontologie/transformation validate_spec,
  |         gates/transformation_anwenden wende_an (Code)
  |     offener Konflikt / fehlendes Zielfeld --> Mensch (A-Q1 bzw. A-O1)
  |- Stufe 2/3: Gates P-Q3/P-K1; Kern-Änderung nötig?
  |     Parametrierung: quellen/tafel_import (Code, kein Skill)
  |     mehr als Parametrierung: Halt --> A-O1-Vorlage --> Mensch
  |         zulaessige Entwicklung gesondert mandatieren; kein Agent
  |         schreibt T-Box/Kern waehrend laufender Migration
  |     jeder Fall: Stand abgenommen? Kernstand (A-K2) und T-Box-Stand
  |         (A-O1) und Tarifwerk A-T1 — unverändert: Linienverweis;
  |         geändert: vorlegen (gates/kernstand_belegen bzw.
  |         stand_belegen tbox) --> Mensch (mensch/rechenkern bzw.
  |         mensch/architektur; Regression bis zu ihrem Werkzeug als
  |         benannte Ausnahme)
  |- Stufe 3b (übernommener Bestand), Reihenfolge erzwungen (ADR-010):
  |     1. aktuartest-durchfuehren (qa/stichprobe, qa/testprofil,
  |        qa/aktuarieller_test, gates/aktuartest) --> je Abnahme eine
  |        Vorlage --> Mensch (A-M1, A-M2, A-M3 einzeln)
  |     2. pruefe-migrationscontrolling (Gate P-B1, qa/migrationssuite,
  |        gates/abnahmebericht) --> Abnahmebericht --> Mensch (A-M4)
  |- nach A-M4: uebernehme-migrationsbestand --> Zugangsprobe
  |     --> Mensch A-B2 --> mandatierte Registrierung im Betrieb
  |- Abbruch: Vorlage A-M5 --> mensch/programmleitung; kein weiterer
  |     Entscheid im Fall nach gezeichnetem Abbruch
  |- jeder zulaessige Implementierungs-Block: entwickle-im-zielsystem
  |     Abschluss: teste-adversarial --> Fixes --> Regressionstests
  |     während laufender Fälle: integriere-migrationsinkrement
  '- Doku-Pflichten: dokumentiere-system (ADR, README, AGENTS)
```

Menschliche Gates (A-Q1/A-O1/A-K2/A-M1/A-M2/A-M3/A-M4, P9-Snapshots) sind
keine Skills; sie sind Werkzeuge für Menschen (`ontologie.entscheide`,
`gates.gate_entscheid`); wer zeichnet, wird aus dem Schlüssel über die
Zeichnungsordnung bestimmt (ADR-018). Skills bereiten sie vor und halten
an ihnen an.

## Benannte, noch nicht gebaute Rollen (mit Auslöser)

Nichts auf Vorrat: diese Rollen entstehen, wenn ihr Auslöser eintritt,
als eigener Skill mit demselben Muster:

| Rolle (geplant) | Auslöser |
|---|---|
| T-Box-Erweiterung vorbereiten | erster Fall, den die T-Box nicht ausdrückt (voraussichtlich FLV: neue Produktfamilie, A-O1-Vorlage mit Klassen-Entwurf, Migrationsplan der A-Boxen, Testabdeckungs-Impact) |
| Erweiterungsstellen implementieren | erste Spez mit offener Erweiterungsstelle (freie Implementierung am benannten Ort, unter entwickle-im-zielsystem plus fallweisen Regeln) |
| Bestandsabzug als Stufe-1-Quelle (QuellFragment) | erster Fall, der Vertragsdaten in die A-Box extrahieren muss — der Vorverdichter steht (`quellen/bestand_profil.py`) und der Weg in die Ziel-Ontologie ebenfalls (`transformiere-quellbestand` + `ontologie/transformation`); offen ist allein die Erweiterung von `extrahiere-quellfragment` um den Quelltyp Bestandsabzug |
| Legacy-Code-Analyse | erster Fall mit Quellsystem-Code (AST/Callgraph-Vorverdichter, Terminologie-Lokalisierung, dort auch Embeddings-Freigabe) |
| Release-/Merge-Vorbereitung | Grundregeln seit 2026-08-18 in `integriere-migrationsinkrement`; offen bleibt die Integration der O-Gates in die Team-Abnahme (nach F2-Beschluss im Team) |

## Pflege-Regeln

1. Skills sind aus Fällen destilliert: nach jedem abgeschlossenen Fall
   oder größeren Block werden die berührten Skills um die gelernten
   Regeln ergänzt (kleiner, begründeter Commit; Skills sind Teil der
   Nachweiskette, ihre Änderung ist sichtbar).
2. Parität `.claude`/`.agents` hält der Test
   `tests/test_agent_workflow_docs.py`; Kernregeln der Migrations-Skills
   sind dort zusätzlich maschinell gesichert (Löschen fällt rot aus).
3. Ein Skill nennt seine Grenze so präzise wie seinen Auftrag:
   „Skip for“ ist Pflicht. Gewünschte Komposition ist die Regel, kein
   Befund: Skills können sich bei verschiedenen Verantwortungsachsen
   ergänzen (Fallskill lädt Phasenrouter, Phasenrouter verweisen auf
   Fachskills, Fachskills tragen eigene Fachreferenzen). Ein Befund
   ist erst eine widersprüchliche Eigentumserklärung desselben Stoffs
   oder normative Doppelpflege derselben Regel an zwei Orten. Keine
   automatische Parent-Vererbung erfinden: Bezüge zwischen Skills sind
   ausdrückliche Pflicht-Skills und Referenzen im Text, keine
   implizite Abhängigkeit; `AGENTS.md` ist der gemeinsame Vertrag.
4. Prinzipien (P1-P10) werden in Skills zitiert, nicht dupliziert;
   die Quelle ist das Architektur-Dokument.

## Bewusst nicht umgesetzt / Nachweise offen

Keine neue technische Skill-Erzwingung, kein RPC/MCP-Weg, kein Agenten-
Runtimepfad im Pythonpaket. Native Hostproben und Linux-Referenzsuite
stehen aus. Menschliche Mappingentscheidungen werden ausdruecklich
autorisiert in die Spec uebertragen und menschlich abgeglichen;
danach Validierung/Anwendung und betroffene Belege neu erzeugen.
Dieser Verfahrensweg ist keine technische Signaturpruefung der Spec-
Entscheidungsfelder; ein `entscheider`-Text ersetzt keine Signatur.
Historische Befunde und nicht nachgemessene Ursachen bleiben als solche
im A049-Vorschlag gekennzeichnet.
