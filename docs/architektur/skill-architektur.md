# Skill-Architektur: die Agenten-Rollen des Gesamtsystems

Stand: 2026-08-15. Die Skills sind das Betriebsmodell des Systems: sie
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
| Fachkonflikt-Aufbereitung | `bereite-fachkonflikt-auf` | Diskrepanzen verifizieren, einordnen, Auswirkungen RECHNEN, Entscheidungs-Dossier + Empfehlung liefern, dann STOPP | entscheiden (auch nicht "offensichtliche" Faelle); Quellen-Hierarchie festlegen |
| Kern-Uebersetzung (Alt-Pfad) | `build-vergleichsrechenkern` | Sechs-Datei-Vergleichskern 1:1 aus einer Quellmappe, Gate-Kette bis zur mechanischen Abnahme | Zielkern-Aenderungen; Gate-Logik |
| Gate-Autorenschaft | `author-rechner-toolbox-gate` | neue Pruef-CLIs unter dem Ledger-/Exit-Contract | Fachlogik ausserhalb des Pruefens |

## Zusammenspiel (wer uebergibt an wen)

```
migrationsfall-durchfuehren
  |- Stufe 1: n x extrahiere-quellfragment --> deterministischer Merge
  |     Konflikt --> bereite-fachkonflikt-auf --> MENSCH (entscheide + G-1)
  |- Stufe 2/3: Gates O1/O3; Kern-Aenderung noetig?
  |     Parametrierung: quellen/tafel_import (Code, kein Skill)
  |     mehr als Parametrierung: STOPP --> G-T-Vorlage --> MENSCH
  |         danach: entwickle-im-zielsystem (unter dem G-T-Beschluss)
  |- jeder Implementierungs-Block: entwickle-im-zielsystem
  |     Abschluss: teste-adversarial --> Fixes --> Regressionstests
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
| Bestandsdaten-Extraktion | erster Fall mit Bestandsabzug als Quelle (Schema-Profiling-Vorverdichter plus Extraktions-Skill-Erweiterung) |
| Legacy-Code-Analyse | erster Fall mit Quellsystem-Code (AST/Callgraph-Vorverdichter, Terminologie-Lokalisierung, dort auch Embeddings-Freigabe) |
| Release-/Merge-Vorbereitung | Integration der O-Gates in die Team-Abnahme (nach F2-Beschluss mit Albrecht) |

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
