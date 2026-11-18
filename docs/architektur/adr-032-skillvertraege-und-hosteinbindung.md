# ADR-032: Aufgabenvertraege, Phasenreferenzen und Hosteinbindung

Status: angenommen zur Umsetzung; Ausfuehrungsnachweise der Hosts offen.
Datum: 2026-11-05.
Entscheidung: Maintainer, Zustimmung zum A049-Vorschlag und Fortsetzung
der Umsetzung in der interaktiven Sitzung. Keine fachliche Gateabnahme.

## Kontext

Der A049-Bericht zeigt berichtete Nichtnutzung trotz Werkzeugzugang
(B3). Aktuelle Rollentexte versprechen Delegation ohne explizites
Werkzeugprofil; der Fall-Skill umfasst 915 Zeilen. Die Messung betrifft
Claude Code, waehrend der Arbeitsauftrag auch Codex und OpenCode umfasst.
Skilldiscovery, Erlaubnis, Laden und Anwendung sind verschiedene Zustaende.
Historische Originalprotokolle lagen fuer die Untersuchung nicht vor;
die berichteten Befunde sind keine hier reproduzierte Nutzungsanalyse.

## Entscheidung

- `AGENTS.md` traegt den gemeinsamen Aufgaben-/Rueckgabevertrag fuer
  mandatierte Arbeit der fuenf KI-Tool-Rollen und Fallarbeit. Betriebsarbeit
  durch die Betriebsrolle gehoert auch ohne Migrationsfall dazu;
  Entwicklung durch eine Fachrolle bleibt Rollenarbeit. Eigenstaendige
  Entwicklung, allgemeine Exploration und reine Dokumentationsarbeit
  ausserhalb solcher Rollen-/Fallaufgaben folgen den allgemeinen
  Repo-Regeln und dem jeweiligen Skill, ohne obligatorischen vollstaendigen
  Rollen-/Fallvertrag. Quellen-, Gate- und Mandatsrechte werden nicht erweitert.
  Verfahrensunterlagen werden von fachlichen Quellen getrennt.
  Extraktion verarbeitet genau eine Vorverdichtung einer Quelle.
- Der Katalog ordnet Pflichtskills nach Aufgabe und Arbeitsmodus zu.
  Gateerstellung nutzt allgemeine Entwicklungsregeln und zusaetzlich
  den Gate-Skill. Widersprueche oder fehlende Mandate fuehren zum Halt.
- Programmleitung fuehrt die Hauptsitzung mit begrenzten Fachauftraegen;
  lokale Dateiuebergaben sind der ausdrueckliche Ersatzweg, wenn native
  Registrierung oder Delegation nicht verfuegbar ist.
- Der Fall-Skill behaelt universelle Grenzen und Abbruchregeln im Kern;
  Phasendetails werden ueber relative Referenzen geladen.
- Der Betrieb erhaelt einen engen Zugangsskill. A-B2 bleibt menschlich;
  Weltaufbau, A-B1 und A-B3 sind gesonderte Verfahren.
- Fachliche Rollen und Skillnamen bleiben in `.claude/` und `.agents/`
  byteidentisch. Native Codex-/OpenCode-Adapter verweisen auf diese Rollen,
  statt ihre fachlichen Regeln zu duplizieren. Keine Modelle, Provider,
  Geheimnisse oder neuen Runtimepfade im Pythonpaket.
- Ein Entwicklermandat oder Sitzungswechsel hebt das Agentenschreibverbot
  fuer T-Box/Kern waehrend einer Migration nicht auf.

## Folgen und Nachweise

Die Scopepraezisierung zu Reviewpunkt 8 ist in
[Revieweinordnung des Skillpakets](skill-paket-review-einordnung.md)
abgegrenzt. Sie ist keine Gesamtfreigabe dieses ADRs oder des Skillpakets.

Vertrag und Ladeanweisung sind Prozessregeln, keine technische
Gate-Erzwingung. Referenz-/Katalog-/Adaptertests sichern Struktur und
Spiegelung; Hostproben muessen tatsaechliche Registrierung, Laden und
Delegation separat nachweisen. Ohne diesen Nachweis bleibt die native
Einbindung unbestaetigt; der lokale Uebergabeweg ist verfuegbar.

OpenCode-Dokumentation/Schema sind versionsabhaengig. Adapter verwenden
minimale Metadaten und keine versionskritischen Permissionfelder;
sie erben Hostrechte und erzeugen keine neue Sicherheitsgrenze.
Nach Aenderungen an Hostdefinitionen ist ein Neustart der betreffenden
Sitzung erforderlich.

## Bewusst nicht umgesetzt / offene Punkte

Keine neuen Gate-Vertraege, keine Aenderung akzeptierter Gegenstaende,
keine Sicherheitsreparaturen, kein ADR-030-Umbau und keine RPC/MCP-Wege.
Der Maintainer hat den menschlich verantworteten B7-Uebertragungsweg
bestaetigt: dokumentierte Entscheidung, autorisierte Specbearbeitung,
menschlicher Abgleich, erneute Validierung/Anwendung und Belegerzeugung.
Kein automatischer Transfer oder Signaturnachweis durch Entscheidertext.
Das A-M4-Paar folgt dem bestehenden E2E-Ablauf: Uebernahmebestand bis
Stichtag 1, fortgeschriebener Gesamtbestand bis Stichtag 2; gleiche
Bewertungs-/Darstellungsregeln, bewusst unterschiedliche Horizonte.
Die Berichte sind gebundene visuelle Artefakte, keine zweite Pruefsuite.
Linux-Referenzsuite und reale Hostproben sind vor Abschluss ihrer
jeweiligen Abnahme erforderlich; Windows-Dokumentchecks ersetzen sie nicht.

## Verworfene Alternativen

Nur `Skill` freigeben beantwortet B3 nicht. Alle Skills vorladen erhoeht
Kontextkosten und vermischt Aufgaben. Drei fachliche Skillbaeume erzeugen
Drift. Verschachtelte Fachdelegation ist fuer die abgegrenzten Auftraege
nicht erforderlich.

## Nachtrag 2026-11-06 (A049-Skillorthogonalitaet, Umsetzung)

Der Fall-Skill ist umgesetzt auf **vier normative Phasenverfahren** zum
Kern hin (SKILL.md haelt universelle Grenzen, Phasentabelle und
Rueckgabe; unter `references/` pro Phase eine Datei, mit
Inhaltsverzeichnis sobald > 300 Zeilen):

- `quellen-und-transformation.md` — Fallanlage, Fallauftrag A-M6,
  Quellen -> A-Box, Bestandsabzug -> Ziel-Ontologie, Gate A-Q1
  und die Reihenfolge-Zwaenge.
- `spezifikation-und-parametrierung.md` — Stufe 2, Golden Master P-K1,
  Stand A-K2/A-O1/A-T1.
- `abnahmen-und-berichte.md` — A-M1/A-M2/A-M3, Migrationscontrolling
  A-M4, Tarifplanfestlegungen, Fallabbruch, Abbruchkriterien.
- `betriebsuebergabe.md` — Zugang nach A-M4; das vollstaendige Verfahren
  bleibt ausschliesslich im Skill `uebernehme-migrationsbestand`.

Die alte Detailreferenz `ablauf-detail.md` ist ein **Kompatibilitätsindex**:
alle vierzehn historischen Anker (`reihenfolge`, `fallanlage`,
`fallauftrag`, `quellen`, `transformation`, `aq1`, `spez`, `golden`,
`stand`, `bestandsabnahmen`, `am4`, `zugang`, `schichtbeleg`,
`tarifplanfestlegungen`) loesen weiterhin auf und verweisen je Abschnitt
eindeutig auf das neue Zuhause. Keine zweite Vollkopie; pro Abschnitt
steht eine Weiterleitung, nicht der Stoff.

Zwei neue, eigenstaendige **Fachreferenzen** sind eigene Zuhause fuer den
Stoff, den der Fallskill frueher duplizierte:

- `aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`
  (Anker `schichtbeleg`, `pflichtmengen`) — Schichtbeleg-Erzeuger
  (`gates.verankerung_belegen`) und Mengenregel der Pflichtziehung.
- `pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md`
  (Anker `fortschreibung`, `freischaltung`, `berichtspaar`,
  `abnahmebericht`) — Fortschreibung, Freischaltung mit Fuehrungsprobe,
  das Bestandsberichtspaar vor/nach und der Abnahmebericht.

Beide Fachskills laden ihre Fachreferenz sichtbar VOR der Arbeit
(Pflichtlektuere); der Fallskill verweist auf die Fachskills statt auf
den Monolith. Das A-M4-Berichtspaar bleibt wie im E2E-Ablauf: VOR aus
dem Uebernahmebestand bis Stichtag 1, NACH aus dem fortgeschriebenen
Gesamtbestand bis Stichtag 2, `stichtag_2 > stichtag_1`, gleiche
Bewertungs-/Darstellungsregeln, bewusst verschiedene Horizonte; der
Betriebsbericht mit `--berichtsstichtag` wird nicht als Fallbericht
wiederverwendet. Spiegel-Paritaet `.agents`/`.claude` (inklusive der
References) hält der bestehende Test; die Referenz-/Ankerstruktur prüft
der neu ergaenzte Referenzscanner in `tests/test_agent_workflow_docs.py`.
