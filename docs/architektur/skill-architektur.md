# Skill-Architektur: die Agenten-Rollen des Gesamtsystems

Stand: 2026-09-05 (Rollen-Katalog v2 nach ADR-018; v1 vom 2026-08-19
darunter als Skill-Katalog). Die Skills sind das Betriebsmodell des Systems: sie
tragen das Urteils-Wissen der Agenten-Rollen, versioniert im Repo,
CLI-neutral gespiegelt (`.claude/skills/` + `.agents/skills/`,
Parität test-tragend), und ihr Git-Stand gehört in die Provenienz
jeder Agenten-Aussage (Akteur-Konvention
``<modell>/<skill>@<git-sha-kurz>``, P1).

## Die Verteilungsregel (Wiederholung aus dem Pipeline-Dokument, weil
sie die Skill-Grenzen definiert)

Was GELTEN muss, lebt in Code und Gates (erzwungen, nicht empfohlen).
Was URTEILEN anleitet, lebt in Skills. Was ZEIGT, lebt im
Präzedenzfall. Ein Skill, der versucht, Geltung zu erzeugen
("bitte halte dich an ..."), ist ein Architekturfehler — die Regel
gehört dann in ein Gate oder einen Validator.

## Rollen-Katalog v2: die vier Agentenrollen des KI-Tools (ADR-018)

Skills sind Fähigkeiten; Rollen sind, wer sie in welchem Auftrag
ausübt. Seit ADR-018 gibt es genau vier Agentenrollen, versioniert als
Definitionen unter `.claude/agents/` (gespiegelt in `.agents/agents/`,
Parität test-tragend). Sie legen vor und zeichnen nie; jede hat ein
menschliches Gegenstück, das mit seinem Schlüssel zeichnet. Es trägt
seit dem Entscheid vom 2026-09-16 DENSELBEN Namen mit dem Präfix
`mensch/` — `agent/rechenkern` legt vor, `mensch/rechenkern` zeichnet.

| Agentenrolle | Ziel (Perspektive eines laufenden Unternehmens) | Skills |
|---|---|---|
| `agent/aktuariat` | fachlich richtig abgebildet: Transformation, drei aktuarielle Abnahmen, Controlling, Bestandsfortführung | transformiere-quellbestand, extrahiere-quellfragment, bereite-fachkonflikt-auf, aktuartest-durchführen, prüfe-migrationscontrolling |
| `agent/architektur` | in der vorgegebenen Architektur: Schichtenkarte, Nachweiskette, Vertrauensgrenzen, Betrieb | entwickle-im-zielsystem (als Massstab), author-rechner-toolbox-gate, teste-adversarial, integriere-migrationsinkrement, dokumentiere-system |
| `agent/rechenkern` | stabiles Zielsystem: Regressionstests, Referenzwerte, Doku, Inkremente unter ADR-007 | entwickle-im-zielsystem, integriere-migrationsinkrement, teste-adversarial, dokumentiere-system |
| `agent/programmleitung` | Migration effizient geliefert; orchestriert die drei anderen, hält an jedem Gate an | migrationsfall-durchführen |

Die Gegenseite des abgebenden Hauses (`mensch/quell-aktuar`) hat kein
Agenten-Gegenstück: Sie liefert, sie zeichnet keine Abnahme des
aufnehmenden Unternehmens. In der Vorführung werden alle menschlichen
Rollen simuliert (Schlüsselklasse `simulation`); die Regie der
Vorzeige hält ihre Auftragsprofile (ADR-017).

## Skill-Katalog (v1, Fähigkeiten je Skill)

| Rolle | Skill | Kern-Auftrag | Härte-Grenze (was der Skill NICHT darf) |
|---|---|---|---|
| Fall-Orchestrierung | `migrationsfall-durchfuehren` | einen Migrationsfall systematisch durch die drei Stufen und Gates führen | menschliche Gates überspringen; Diskrepanzen endgültig auflösen |
| Quell-Extraktion | `extrahiere-quellfragment` | EINE Quelle in ein QuellFragment übersetzen (Structured Output, generiertes Schema) | die andere Quelle sehen; raten statt `nicht_belegt`; Rohquellen lesen |
| Entwicklung | `entwickle-im-zielsystem` | Code unter der nicht verhandelbaren Architektur bauen (Schichtenkarte, Determinismus, Fail-fast, Knoten-Annotation, Test-Pflicht) | Architektur "pragmatisch" brechen; ohne Tests committen; Kern-Verankerungen anfassen |
| Qualitätssicherung | `teste-adversarial` | Blöcke adversarial reviewen (Finden -> Widerlegen -> Fixen -> Regressionstest) und die Test-Disziplin tragen (Mutations-Denken, unabhängige Kontrollrechnung) | Findings ungeprüft übernehmen; grüne Suiten als Beleg für Vollständigkeit lesen |
| Dokumentation | `dokumentiere-system` | Doku unter den Repo-Regeln (generiert schlägt handgeschrieben, ein Zuhause je Typ, ADR-Format, Ehrlichkeits-Abschnitte) | Inhalte doppeln (Drift); Grenzen beschönigen |
| Quellbestand-Transformation | `transformiere-quellbestand` | Mapping des gelieferten Bestandsabzugs in die Ziel-Ontologie vorschlagen (TransformationsSpec); Berechnungen nur aus dem Katalog, Unklarheit wird offener Konflikt | Mapping anwenden/pruefen (deterministischer Code); offene Konflikte entscheiden (Mensch); Ontologie erweitern (A-O1) |
| Fachkonflikt-Aufbereitung | `bereite-fachkonflikt-auf` | Diskrepanzen verifizieren, einordnen, Auswirkungen RECHNEN, Entscheidungs-Dossier + Empfehlung liefern, dann STOPP | entscheiden (auch nicht "offensichtliche" Fälle); Quellen-Hierarchie festlegen |
| Gate-Autorenschaft | `author-rechner-toolbox-gate` | neue Prüf-CLIs unter dem Ledger-/Exit-Contract | Fachlogik ausserhalb des Prüfens |
| Aktuarieller Test | `aktuartest-durchfuehren` | die drei Abnahmen je Vertrag an seinen eigenen Rechenpunkten fahren (Engine, aktuartest-Gate) und je Abnahme eine Vorlage aufbereiten: A-M1 Stichtagstest, A-M2 Verlaufstest, A-M3 Geschäftsvorfalltest | abnehmen (Mensch, A-M1); Werte selbst rechnen; interpolieren oder summieren (Engine verbietet es); Toleranzen aufweichen |
| Migrationscontrolling | `pruefe-migrationscontrolling` | deterministisches Controlling über zwei Stichtage und jeden Vertrag (Migrationssuite, GeVo-Vergleich, Mapping-Tabelle, Bestandsberichte vor/nach) als A-M4-Vorlage aufbereiten | abnehmen (Mensch, A-M4); Werte selbst rechnen; Toleranzen aufweichen; Erwartungswerte "korrigieren" |
| Migrations-CI | `integriere-migrationsinkrement` | Code-Änderungen während laufender Migrationen als kleine knotengebundene Inkremente integrieren (ADR-007: Impact, Gesamt-Suite inkl. aller Fälle, benanntes Staging) | langlebige Branches oder Kern-Forks; Landung ohne fallübergreifenden Beweis; Rückgrat ohne Koordination; Push (Mensch) |

## Zusammenspiel (wer übergibt an wen)

```
migrationsfall-durchfuehren
  |- Stufe 1 (Tarifparameter): n x extrahiere-quellfragment
  |     --> deterministischer Merge
  |     Konflikt --> bereite-fachkonflikt-auf --> MENSCH (entscheide + A-Q1)
  |- Stufe 1b (Bestandsabzug): quellen/bestand_profil (Code, Vorverdichtung)
  |     --> transformiere-quellbestand --> TransformationsSpec
  |     --> ontologie/transformation validate_spec,
  |         gates/transformation_anwenden wende_an (Code)
  |     offener Konflikt / fehlendes Zielfeld --> MENSCH (A-Q1 bzw. A-O1)
  |- Stufe 2/3: Gates P-Q3/P-K1; Kern-Aenderung noetig?
  |     Parametrierung: quellen/tafel_import (Code, kein Skill)
  |     mehr als Parametrierung: STOPP --> A-O1-Vorlage --> MENSCH
  |         danach: entwickle-im-zielsystem (unter dem A-O1-Beschluss)
  |     JEDER Fall: Stand abgenommen? Kernstand (A-K2) und T-Box-Stand
  |         (A-O1) — unveraendert: Verweis (gates/stand_belegen, Code);
  |         geaendert: vorlegen (gates/kernstand_belegen bzw.
  |         stand_belegen tbox) --> MENSCH (mensch/rechenkern bzw.
  |         mensch/architektur; Regression bis zu ihrem Werkzeug als
  |         benannte Ausnahme)
  |- Stufe 3b (uebernommener Bestand), Reihenfolge erzwungen (ADR-010):
  |     1. aktuartest-durchfuehren (qa/stichprobe, qa/testprofil,
  |        qa/aktuarieller_test, gates/aktuartest) --> je Abnahme eine
  |        Vorlage --> MENSCH (A-M1, A-M2, A-M3 einzeln)
  |     2. pruefe-migrationscontrolling (Gate P-B1, qa/migrationssuite,
  |        gates/abnahmebericht) --> Abnahmebericht --> MENSCH (A-M4)
  |- jeder Implementierungs-Block: entwickle-im-zielsystem
  |     Abschluss: teste-adversarial --> Fixes --> Regressionstests
  |     waehrend laufender Faelle: integriere-migrationsinkrement
  '- Doku-Pflichten: dokumentiere-system (ADR, README, AGENTS)
```

Menschliche Gates (A-Q1/A-O1/A-K2/A-M1/A-M2/A-M3/A-M4, P9-Snapshots) sind
KEINE Skills — sie sind Werkzeuge fuer Menschen (`ontologie.entscheide`,
`gates.gate_entscheid`); wer zeichnet, wird aus dem Schluessel ueber die
Zeichnungsordnung bestimmt (ADR-018). Skills bereiten sie vor und halten
an ihnen an.

## Benannte, noch nicht gebaute Rollen (mit Auslöser)

Nichts auf Vorrat — diese Rollen entstehen, wenn ihr Auslöser eintritt,
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
   Regeln ergänzt (kleiner, begründeter Commit — Skills sind Teil der
   Nachweiskette, ihre Änderung ist sichtbar).
2. Parität `.claude`/`.agents` hält der Test
   `tests/test_agent_workflow_docs.py`; Kernregeln der Migrations-
   Skills sind dort zusätzlich maschinell gesichert (Löschen fällt rot aus).
3. Ein Skill nennt seine Grenze so präzise wie seinen Auftrag —
   "Skip for" ist Pflicht, Überlappungen zwischen Skills sind ein
   Befund.
4. Prinzipien (P1-P10) werden in Skills ZITIERT, nicht dupliziert;
   die Quelle ist das Architektur-Dokument.
