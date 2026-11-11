---
name: migrationsfall-durchfuehren
description: >-
  Fuehrt einen Migrationsfall durch Tarifquellen, Bestandsmapping,
  Spezifikation, Golden Master, A-M1/A-M2/A-M3 und Migrationscontrolling
  A-M4 bis zur Betriebsuebergabe. Verwende bei "Migrationsfall anlegen",
  "Tarifgeneration migrieren" oder einer Lieferung aus Tarifmeldung,
  Tarifrechner und Bestandsabzug. Nicht fuer reine Analyse, Gateauthoring
  oder selbststaendige Entwicklungsarbeit; dafuer die jeweiligen Skills.
---

# Einen Migrationsfall durchfuehren

## Auftrag und universelle Grenzen

Du fuehrst als `agent/programmleitung` die Hauptsitzung. Der
Aufgaben-/Rueckgabevertrag in `AGENTS.md` gilt vor jedem Arbeitsschritt.
Rolle und Mandat sind keine fachliche Quelle und keine Annahme.

- Ein Fall beginnt erst mit geltendem menschlich gezeichnetem A-M6;
  Fallanlage und registrierte Lieferung dienen dessen Vorbereitung.
  Scope `tarif` oder `bestand` bestimmt der Mensch, nie ein Dateifund.
  Linie ist Pflicht. Nach A-M5 wird nichts im Fall angenommen.
- LLM-Schritte schlagen vor; deterministischer Code entscheidet Merge,
  Coverage, Vergleich und Transformation. Menschen entscheiden jeden
  Fachkonflikt und jedes menschliche Gate. Du zeichnest nie eine Annahme.
- GENAU EINE Quelle je Extraktionssitzung und Tarifgeneration, nur deren
  Vorverdichtung. Verfahrens-/Schemaunterlagen getrennt erlauben;
  keine Ergebnisse anderer Extraktionen und keine fremden Fallwerte.
- Pflichtskills und aktuelle Phasenreferenz vor der Arbeit laden. Fehlt
  das Skillwerkzeug, lokalen Ladeweg melden; eine Sperre niemals umgehen.
  Ein Prompt oder Ladebeleg allein beweist keine Anwendung.
- Kein Agent schreibt waehrend einer laufenden Migration an T-Box oder
  Kern; ein Entwicklermandat oder Sitzungswechsel hebt dies nicht auf.
  Aenderungsbedarf vorlegen und menschlich klaeren. Zulaessige
  migrationsbedingte Codearbeit folgt `integriere-migrationsinkrement`.
- Eingang nie ueberschreiben oder bereinigen, Entscheidungen append-only;
  Agentenartefakte nur in erlaubten abgeleiteten Arbeitsorten.
  Keine Schluessel oder Zeichnungsordnungen lesen, erzeugen oder kopieren.
- Jede Aussage nennt Quelle/Hash, Fundstelle und Akteur
  `<modell>/<skill>@<git-sha-kurz>`. Fehlende Belege ausweisen.

## Phasenauswahl und verbindliche Lektuere

Lade die Referenz **vor** dem jeweiligen Schritt: die Tabelle nennt je
Phase das normative Phasenverfahren (unter `references/`) bzw. den
Fachskill oder die Fachreferenz. Lies die Abschnitte, die dein
aktueller Schritt braucht, vollstaendig, mit weiteren Lesefenstern
falls das Werkzeug kuerzt. Nach Kontextwechsel: Auftrag, Haltpunkt und
aktuelle Phasenreferenz neu laden. Nicht ein ganzes Phasenverfahren
pauschal laden, ohne den Abschnitt deines Schritts zu bestimmen.
`references/ablauf-detail.md` ist kein Pflichtverfahren: der alte
Ankerkompatibilitaetsindex loest nur noch alte Verweise auf.

| Phase | Zuerst laden | Uebergabe / Halt |
|---|---|---|
| Fallanlage, A-M6, Tarifquellen, Mapping und A-Q1 | [Quellen und Transformation](references/quellen-und-transformation.md) | getrennte Extraktion/Mappings; Fachkonflikte menschlich |
| Spez, P-K1, A-K2/A-O1/A-T1 | [Spez und Parametrierung](references/spezifikation-und-parametrierung.md) | Aenderungsbedarf und Standvorlagen; kein Kernschreiben |
| A-M1/A-M2/A-M3, Schicht, Fuehrungsprobe und A-M4 | [Abnahmen und Berichte](references/abnahmen-und-berichte.md) | je Abnahme eigene menschliche Entscheidung |
| Zugang nach A-M4 | [Betriebsuebergabe](references/betriebsuebergabe.md) | Betriebsskill, Zugangsprobe, STOPP A-B2, danach mandatierte Uebernahme |

Die fachliche Auswahl-/Overlapmatrix steht einmal in
`docs/architektur/skill-architektur.md`. Bei unpassendem Auftrag oder
widerspruechlicher Referenz: Halt, Fundstellen an Auftraggeber uebergeben.
Native Fachdelegation ist host-/versionsabhaengig. Ohne Nachweis startet
der Mensch eine Fachsitzung mit demselben Auftrag und lokalen Dateien.

## Reihenfolge und Belegkontinuitaet

Der A-Box-Merge laeuft einmal; spaetere Aufloesungen leben in der A-Box.
Neuer Merge ersetzt sie und ist kein Weg zur stillen Neuzeichnung.
Registrierte Nachlieferung, Code-/Tafelaenderung oder Diskrepanzaufloesung
kann Belege entwerten: betroffene Gates neu fahren, menschliche
Neuzeichnung vorlegen. A-Q1 und A-M1, im Bestands-Scope auch A-M2/A-M3,
gehen A-M4 voraus; A-K2/A-O1/A-T1 muessen gelten.

Vorlaeufige A-Box-Aufloesung ist nur ein ausdruecklich mandatierter
Weiterbauweg: `ontologie.entscheide --vorlaeufig --akteur ...` nach
der Quellenreferenz; niemals eine endgueltige Agentenentscheidung.
`vorlaeufig=true` blockiert menschliche Annahme. Transformationskonflikte
haben keinen hier belegten automatischen Transferweg von der menschlichen
A-Box-Entscheidung in die Spec: dokumentierte menschliche Entscheidung,
autorisierte Uebertragung und menschlicher Spec-Abgleich gemaess
`transformiere-quellbestand`, dann Validierung/Anwendung und Belege neu.
Ein `entscheider`-Text ist kein Signaturnachweis.

## STOPP und menschliche Uebergabe

An jedem menschlichen Gate uebergibst du die Vorlage. Nur unsignierte
Ablehnung unter deiner Agentenrolle ist moeglich, nie Annahme; die
Bedienfolge `gate_entscheid` fuehrt der berechtigte Mensch aus.
Der Freigabering und die Linie sind Eingaben der menschlichen
Autoritaetsumgebung, keine Agentenkompetenz.

STOPP bei fehlendem Mandat/Skill/Referenz, Rohquellenbedarf,
Quellen-/Dimensions-/Tafelkonflikt, Eingangsintegritaetsverletzung,
offener Erweiterungsstelle, nicht ableitbarem Pflichtfeld, rotem
eingefrorenem Kernreferenzwert oder Lieferungsinkonsistenz.
Ein roter Test oder Bericht ist ein Befund, kein Auftrag zur Aufweichung
von Toleranzen, Erwartungswerten oder Pflichtbelegen.

Kann der Fall nicht abgeschlossen werden: die Abschnitte
"Fallabbruch (Programmleitung)" und "Abbruchkriterien" liegen normativ im
Phasenverfahren [Abnahmen und Berichte](references/abnahmen-und-berichte.md#fallabbruch)
— lade sie vollstaendig, bevor du den Abbruch vorbereitest. Darin steht
auch der gezeichnete Widerruf einer geltenden A-M4 (nur der berechtigte
Mensch kann das; eine Agentenablehnung gibt keinen Abbruch frei).
Die alten Anker der aufgeteilten Datei bleiben als
[Kompatibilitätsindex](references/ablauf-detail.md) erhalten.
Kein Bereinigen von Entscheiden.

## Rueckgabe

Auftrag-ID, geladene Skills/Referenzen und Ladeweg, Artefaktpfade,
ausgefuehrte Checks mit Ergebnissen, unausgefuehrte Checks, offene Punkte,
Haltgrund und Empfaenger nennen. Native Aufrufe nur mit Sitzungsnachweis
behaupten. Kein Selbstbericht ist eine menschliche Abnahme.
