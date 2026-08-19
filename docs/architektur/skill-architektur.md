# Skill-Architektur: die Agenten-Rollen des Gesamtsystems

Stand: 2026-08-19. Die Skills sind das Betriebsmodell des Systems: sie
tragen das Urteils-Wissen der Agenten-Rollen, versioniert im Repo,
CLI-neutral gespiegelt (`.claude/skills/` + `.agents/skills/`,
Paritaet test-tragend), und ihr Git-Stand gehoert in die Provenienz
jeder Agenten-Aussage (Akteur-Konvention
``<modell>/<skill>@<git-sha-kurz>``, P1).

## Die Verteilungsregel (Wiederholung aus dem Pipeline-Dokument, weil
sie die Skill-Grenzen definiert)

Was GELTEN muss, lebt in Code und Gates (erzwungen, nicht empfohlen).
Was URTEILEN anleitet, lebt in Skills. Was ZEIGT, lebt im
Praezedenzfall. Ein Skill, der versucht, Geltung zu erzeugen
("bitte halte dich an ..."), ist ein Architekturfehler — die Regel
gehoert dann in ein Gate oder einen Validator.

## Rollen-Katalog v1

| Rolle | Skill | Kern-Auftrag | Haerte-Grenze (was der Skill NICHT darf) |
|---|---|---|---|
| Fall-Orchestrierung | `migrationsfall-durchfuehren` | einen Migrationsfall systematisch durch die drei Stufen und Gates fuehren | menschliche Gates ueberspringen; Diskrepanzen endgueltig aufloesen |
| Quell-Extraktion | `extrahiere-quellfragment` | EINE Quelle in ein QuellFragment uebersetzen (Structured Output, generiertes Schema) | die andere Quelle sehen; raten statt `nicht_belegt`; Rohquellen lesen |
| Entwicklung | `entwickle-im-zielsystem` | Code unter der nicht verhandelbaren Architektur bauen (Schichtenkarte, Determinismus, Fail-fast, Knoten-Annotation, Test-Pflicht) | Architektur "pragmatisch" brechen; ohne Tests committen; Kern-Verankerungen anfassen |
| Qualitaetssicherung | `teste-adversarial` | Bloecke adversarial reviewen (Finden -> Widerlegen -> Fixen -> Regressionstest) und die Test-Disziplin tragen (Mutations-Denken, unabhaengige Kontrollrechnung) | Findings ungeprueft uebernehmen; gruene Suiten als Beleg fuer Vollstaendigkeit lesen |
| Dokumentation | `dokumentiere-system` | Doku unter den Repo-Regeln (generiert schlaegt handgeschrieben, ein Zuhause je Typ, ADR-Format, Ehrlichkeits-Abschnitte) | Inhalte doppeln (Drift); Grenzen beschoenigen |
| Quellbestand-Transformation | `transformiere-quellbestand` | Mapping des gelieferten Bestandsabzugs in die Ziel-Ontologie vorschlagen (TransformationsSpec); Berechnungen nur aus dem Katalog, Unklarheit wird offener Konflikt | Mapping anwenden/pruefen (deterministischer Code); offene Konflikte entscheiden (Mensch); Ontologie erweitern (G-T) |
| Fachkonflikt-Aufbereitung | `bereite-fachkonflikt-auf` | Diskrepanzen verifizieren, einordnen, Auswirkungen RECHNEN, Entscheidungs-Dossier + Empfehlung liefern, dann STOPP | entscheiden (auch nicht "offensichtliche" Faelle); Quellen-Hierarchie festlegen |
| Gate-Autorenschaft | `author-rechner-toolbox-gate` | neue Pruef-CLIs unter dem Ledger-/Exit-Contract | Fachlogik ausserhalb des Pruefens |
| Migrations-Abnahme | `pruefe-migrationsabnahme` | deterministische Abnahmepruefung ueber zwei Stichtage (Migrationssuite, GeVo-Vergleich, Mapping-Tabelle, Bestandsberichte vor/nach) als G-2-Vorlage aufbereiten | abnehmen (Mensch, G-2); Werte selbst rechnen; Toleranzen aufweichen; Erwartungswerte "korrigieren" |
| Migrations-CI | `integriere-migrationsinkrement` | Code-Aenderungen waehrend laufender Migrationen als kleine knotengebundene Inkremente integrieren (ADR-007: Impact, Gesamt-Suite inkl. aller Faelle, benanntes Staging) | langlebige Branches oder Kern-Forks; Landung ohne falluebergreifenden Beweis; Rueckgrat ohne Koordination; Push (Mensch) |

## Zusammenspiel (wer uebergibt an wen)

```
migrationsfall-durchfuehren
  |- Stufe 1 (Tarifparameter): n x extrahiere-quellfragment
  |     --> deterministischer Merge
  |     Konflikt --> bereite-fachkonflikt-auf --> MENSCH (entscheide + G-1)
  |- Stufe 1b (Bestandsabzug): quellen/bestand_profil (Code, Vorverdichtung)
  |     --> transformiere-quellbestand --> TransformationsSpec
  |     --> ontologie/transformation validate_spec + wende_an (Code)
  |     offener Konflikt / fehlendes Zielfeld --> MENSCH (G-1 bzw. G-T)
  |- Stufe 2/3: Gates O1/O3; Kern-Aenderung noetig?
  |     Parametrierung: quellen/tafel_import (Code, kein Skill)
  |     mehr als Parametrierung: STOPP --> G-T-Vorlage --> MENSCH
  |         danach: entwickle-im-zielsystem (unter dem G-T-Beschluss)
  |- Stufe 3b (uebernommener Bestand): pruefe-migrationsabnahme
  |     (Gate B1, qa/migrationssuite, gates/abnahmebericht)
  |     --> Abnahmebericht --> MENSCH (G-2)
  |- jeder Implementierungs-Block: entwickle-im-zielsystem
  |     Abschluss: teste-adversarial --> Fixes --> Regressionstests
  |     waehrend laufender Faelle: integriere-migrationsinkrement
  '- Doku-Pflichten: dokumentiere-system (ADR, README, AGENTS)
```

Menschliche Gates (G-1/G-2/G-T, P9-Snapshots) sind KEINE Skills — sie
sind Werkzeuge fuer Menschen (`ontologie.entscheide`,
`gates.gate_entscheid`). Skills bereiten sie vor und halten an ihnen an.

## Benannte, noch nicht gebaute Rollen (mit Ausloeser)

Nichts auf Vorrat — diese Rollen entstehen, wenn ihr Ausloeser eintritt,
als eigener Skill mit demselben Muster:

| Rolle (geplant) | Ausloeser |
|---|---|
| T-Box-Erweiterung vorbereiten | erster Fall, den die T-Box nicht ausdrueckt (voraussichtlich FLV: neue Produktfamilie, G-T-Vorlage mit Klassen-Entwurf, Migrationsplan der A-Boxen, Testabdeckungs-Impact) |
| Erweiterungsstellen implementieren | erste Spez mit offener Erweiterungsstelle (freie Implementierung am benannten Ort, unter entwickle-im-zielsystem plus fallweisen Regeln) |
| Bestandsabzug als Stufe-1-Quelle (QuellFragment) | erster Fall, der Vertragsdaten in die A-Box extrahieren muss — der Vorverdichter steht (`quellen/bestand_profil.py`) und der Weg in die Ziel-Ontologie ebenfalls (`transformiere-quellbestand` + `ontologie/transformation`); offen ist allein die Erweiterung von `extrahiere-quellfragment` um den Quelltyp Bestandsabzug |
| Legacy-Code-Analyse | erster Fall mit Quellsystem-Code (AST/Callgraph-Vorverdichter, Terminologie-Lokalisierung, dort auch Embeddings-Freigabe) |
| Release-/Merge-Vorbereitung | Grundregeln seit 2026-08-18 in `integriere-migrationsinkrement`; offen bleibt die Integration der O-Gates in die Team-Abnahme (nach F2-Beschluss im Team) |

## Pflege-Regeln

1. Skills sind aus Faellen destilliert: nach jedem abgeschlossenen Fall
   oder groesseren Block werden die beruehrten Skills um die gelernten
   Regeln ergaenzt (kleiner, begruendeter Commit — Skills sind Teil der
   Nachweiskette, ihre Aenderung ist sichtbar).
2. Paritaet `.claude`/`.agents` haelt der Test
   `tests/test_agent_workflow_docs.py`; Kernregeln der Migrations-
   Skills sind dort zusaetzlich verankert (Loeschen faellt rot aus).
3. Ein Skill nennt seine Grenze so praezise wie seinen Auftrag —
   "Skip for" ist Pflicht, Ueberlappungen zwischen Skills sind ein
   Befund.
4. Prinzipien (P1-P10) werden in Skills ZITIERT, nicht dupliziert;
   die Quelle ist das Architektur-Dokument.
