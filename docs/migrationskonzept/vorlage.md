---
title: "Migrationskonzept ⟨Bestand / Quellsystem⟩"
subtitle: "Vorlage — projektseitige Instanz der konstruktiven Neuberechnung"
lang: de-DE
date: 2026-08-26
---

| Feld | Wert |
|---|---|
| Dokumenttyp | Migrationskonzept (projektseitig, je Bestand/Quellsystem instanziiert) |
| Status | Vorlage v0.2 — Kapitel 6 und 7 ausgearbeitet, uebrige Kapitel Geruest |
| Normative Referenzen | **Grundsatzdokumentation** (`docs/mathematik/grundsatzdokumentation.md`) — Mathematik und Numerik des Zielrechenkerns, dort Abschnitt 9 fuer den Migrationszugang und die Korrekturschicht; Ausgestaltungen der betroffenen Tarifpläne ⟨Liste⟩ |
| Bestand / Mandant | ⟨…⟩ |
| Quellsystem | ⟨…⟩ |
| Freigabe | ⟨Projektleitung⟩, ⟨Quellsystem-Verantwortliche⟩, ⟨Fachexperte Aktuariat⟩ |

---

## Bearbeitungshinweise für die Weiterbearbeitung (Agent)

1. **Normativ ist die Grundsatzdokumentation.** Begriffe und Notation aus ihrem Abschnitt 2 gelten unverändert; nichts daraus wird hier umdefiniert, abgeschwächt oder dupliziert — es wird referenziert.
2. **Markierungen:** ⟨TODO: …⟩ = zu erarbeitender Inhalt. ⟨ENTSCHEIDUNG: …⟩ = offene menschliche Entscheidung — nicht selbst auflösen, sondern in Kap. 11 führen und zur Entscheidung vorlegen.
3. **Kapitel 5 ist fachlich vorbefüllt.** Schrittfolge, System-Zuordnungen (MIG/RK) und Fehlerausgänge sind mit der Methode abgestimmt; Änderungen daran nur nach menschlicher Freigabe (Entwicklung + Fachexperte). Technische Konkretisierungen (5.7) sind ausdrücklich erwünscht.
4. **Konflikte** zwischen diesem Dokument, der Kern-Architektur und der Grundsatzdokumentation werden nicht implizit aufgelöst: Verfahren nach Grundsatzdokumentation 9.16 (Konfliktregel), Eintrag hier in Kap. 11 und im Abweichungsverzeichnis der Grundsatzdokumentation.
5. Keine erfundenen Feldnamen, Paragraphen oder Kennzahlen — Unbekanntes bleibt ⟨TODO⟩. Dokumentsprache Deutsch.

---

## 1 Zweck und Geltungsbereich

Dieses Dokument instanziiert die Methode der Grundsatzdokumentation für die Migration des Bestands ⟨…⟩ aus dem Quellsystem ⟨…⟩ in den Zielrechenkern. Es regelt Systemkontext, Datenliefervertrag, die Migrationszugangsroutine sowie Controlling-, Abnahme-, Klärungs- und Archivprozesse dieses konkreten Migrationsvorhabens.

⟨TODO: Bestandsumfang, betroffene Bestandsgruppen, zeitlicher Rahmen, Migrationsstichtag(e)⟩

## 2 Systemkontext: zwei Objekte, eine Hülle

Zielrechenkern und Migrationssystem laufen in einer gemeinsamen Hülle, sind aber zwei getrennte Objekte mit strikter Aufgabenteilung:

- **Zielrechenkern (RK):** rechnet und bewertet. Historienfrei (Grundsatzdokumentation 9.14). Bietet ausschließlich reguläre APIs: Vertragsanlage, Geschäftsvorfälle, Verankerungsoperator $\mathcal{A}$, Bewertung und Reporting-Positionen. Es existieren keine migrationsspezifischen Sonderrechenpfade (Grundsatzdokumentation 9.1).
- **Migrationssystem (MIG):** orchestriert. Hält das Staging der Lieferobjekte 1–3 (Grundsatzdokumentation 9.12), führt Validierungen und Ableitungen aus (Grundsatzdokumentation 9.14: Ableitungslast), ruft RK-APIs auf, führt Statusmodell und Migrationsprotokoll, produziert die Datengrundlage für Controlling (Kap. 6) und Abnahme (Kap. 7).

**Grenzregel (bindend, Grundsatzdokumentation 9.14):** Die GV-Liste überschreitet die Grenze MIG → RK zu keinem Zeitpunkt. Der einzige Historieninput des RK ist das abgeleitete Attributset aus Lieferobjekt 1.

⟨TODO: konkrete Komponenten- und Schnittstellenbenennung im Zielprodukt, Deployment der gemeinsamen Hülle, Mandanten-/Berechtigungsmodell, Staging-Datenhaltung⟩

## 3 Quellsystem und Bestandsabgrenzung

⟨TODO: Quellsystembeschreibung; frühere Migrationen des Quellsystems (geerbte Residuen — Grundsatzdokumentation 9.3); Bestandsgruppen und Tarifplan-Zuordnung; Tarifpläne ohne freigegebene Ausgestaltung → nicht migrationsfähig (Grundsatzdokumentation Abschnitt 10 Nr. 9); Ausschlüsse und Sonderbestände⟩

## 4 Datenliefervertrag und Ableitungsregeln

Struktur gemäß Grundsatzdokumentation 9.12 (drei Lieferobjekte). Je Lieferobjekt: Feldliste mit Quellsystem-Mapping, Ableitungsort (quellseitig vs. ETL im MIG) und Validierungsregel.

### 4.1 Lieferobjekt 1 — Zustandssnapshot am $t_a$

| Attribut (Grundsatzdokumentation 9.12) | Quellsystemfeld | Ableitung | Validierung |
|---|---|---|---|
| ⟨TODO: je Tarifplan, inkl. $i_0$, $u_0$, Options-/Rechtszustände, Dynamikzähler, Restzillmerstand, Steueraggregate⟩ | ⟨…⟩ | ⟨quellseitig / ETL⟩ | ⟨…⟩ |

### 4.2 Lieferobjekt 2 — GV-Metadatenliste

⟨TODO: GV-Typkatalog des Quellsystems und Mapping auf die Übergangstaxonomie Grundsatzdokumentation 9.7 (Klassen A/B/C); Kennzeichnung rechnender GV für die $t_a$-Ermittlung⟩

### 4.3 Lieferobjekt 3 — Voll-Bewegungsdaten $[t_a, t_0]$

⟨TODO: Format, GV-Abbildbarkeit im RK je Typ, Behandlung schwebender Vorgänge am $t_0$⟩

### 4.4 GV-Inventur

Vorab-Inventur aller im Bestand tatsächlich vorkommenden GV-Typen und -Konstellationen gegen die Taxonomie der Ausgestaltungen (Grundsatzdokumentation Abschnitt 10 Nr. 9). Nicht abgedeckte Konstellationen sind vor Migrationsbeginn zu klären. ⟨TODO: Inventurergebnis, Lückenliste⟩

## 5 Migrationszugangsroutine *(vorbefüllt)*

### 5.1 Vorbedingungen

Je Tarifplan liegt eine freigegebene Ausgestaltung vor (Grundsatzdokumentation Abschnitt 10 Nr. 9). Die Datenlieferung ist gegen den Liefervertrag (Kap. 4) validiert. Die GV-Inventur (4.4) ist abgeschlossen und lückenfrei oder mit dokumentierten Ausschlüssen versehen.

### 5.2 Statusmodell

Hauptpfad: `angeliefert → validiert → verankert → nachgefahren → abgeglichen → migriert`. Seitenausgänge: `klärung(⟨Grund⟩)` (Rückführung in den Hauptpfad nach Behebung), `zurückgestellt` (bewusste Verschiebung, z. B. Folgelieferung). ⟨TODO: formale Zustandsmaschine, Reprocessing-Regeln, Statusreporting⟩

### 5.3 Schrittfolge je Vertrag

| Nr | Schritt | System | Inhalt | Fehlerausgang |
|---|---|---|---|---|
| 1 | Intake und Validierung | MIG | Schema-/Pflichtfeldprüfung der Lieferobjekte 1–3; Plausibilitätsregeln ⟨TODO: Regelkatalog⟩; Prüfung Tarifplan-Zulassung (5.1) | klärung(Datenlieferung) |
| 2 | $t_a$- und Kohortenbestimmung | MIG | $t_a$ gemäß Grundsatzdokumentation 9.12 aus Vertragsstichtag und letztem rechnenden GV (Lieferobjekt 2); fehlt die $t_a$-Lieferung → Fallback-Kohorte $t_0$ (Grundsatzdokumentation 9.12) | Kohorte „Fallback" |
| 3 | Zustandsextrakt | MIG | Historienabgeleitete Attribute bereitstellen bzw. per Ableitungsregel (Kap. 4) berechnen: $i_0$, $u_0$, Options-/Rechtszustände, Dynamikzähler, Restzillmerstand, Steueraggregate. GV-Liste verbleibt im MIG (Grenzregel Kap. 2) | klärung(Ableitung) |
| 4 | Initialanlage | RK | Vertragsanlage mit Ursprungsparametern und mitwandernden Rechnungsgrundlagen (Grundsatzdokumentation 9.1 Schritt 1) über die reguläre Anlage-API | klärung(Tarifabbildung) |
| 5 | Verankerung | RK | Zustand $(i_0, u_0)$ setzen; $V^{\mathrm{prosp}}$ rechnen; $R_{\mathrm{hist}} = V^{\mathrm{ist}} - V^{\mathrm{prosp}}$; Guardrails gemäß Grundsatzdokumentation 9.10 (pfadweise Floors, Degenerationsschwelle, Vorzeichen/Kappung); $\mathcal{A}(t_a, i_0, u_0, R_{\mathrm{hist}})$; Persistenz des Parametertupels (Grundsatzdokumentation 9.11) | Kappungsfall → Fehlerprozess (Kap. 8); Degeneration → Ausbuchungsweg (Grundsatzdokumentation 9.16) |
| 6 | Nachfahren $[t_a, t_0]$ | MIG → RK | Bewegungsdaten (Lieferobjekt 3) als reguläre RK-Geschäftsvorfälle; Klasse-A-GV im Nachfahrzeitraum: Absorption gemäß Grundsatzdokumentation 9.7 | klärung(GV-Inventur) |
| 7 | $t_0$-Abgleich | MIG | Nachgefahrener Wert vs. gelieferter $t_0$-Altwert; Klassifikation systematisch (Konventionsdifferenz je Cluster) vs. unsystematisch (Befund) gemäß Grundsatzdokumentation 9.12; optionale Zweitverankerung $R_{\mathrm{conv}}$ (Grundsatzdokumentation 9.13) nur falls E2 aktiviert (Kap. 11) | klärung(Befund) |
| 8 | Vertragsprüfung | MIG | Anker-Nachweis innerhalb der Toleranzen der Ausgestaltung; Reporting-Positionen belegt ($R_{\mathrm{hist}}$ / ggf. $R_{\mathrm{conv}}$ getrennt, Grundsatzdokumentation 9.11) | klärung(Prüfung) |
| 9 | Abschluss und Protokoll | MIG | Status `migriert`; Migrationsprotokoll gemäß 5.6 | — |

### 5.4 Idempotenz und Wiederanlauf

Die Routine ist je Vertrag deterministisch und wiederholbar (Datennachlieferungen, Korrekturläufe). Ein erneuter Lauf ersetzt die Verankerungsparameter vollständig — es gibt kein kumulierendes $\rho$. Nachfahren und Verankerung sind je Vertrag transaktional; ein abgebrochener Lauf hinterlässt keinen teilverankerten Vertrag. ⟨TODO: technischer Mechanismus; Transaktionsschnitt und Persistenz sind Implementierungsfreiheiten Grundsatzdokumentation 9.16⟩

### 5.5 Kohorten

Standard ($t_a$-Verankerung) · Fallback ($t_0$-Verankerung, Grundsatzdokumentation 9.12) · Kappung (Grundsatzdokumentation 9.10, im Fehlerprozess) · Befund (unsystematische Abgleichsabweichung). Kohorten werden getrennt reportet und tragen eigene Toleranzen (Grundsatzdokumentation 9.15). ⟨TODO: Kennzeichnung im Datenmodell, Grundsatzdokumentation 9.16⟩

### 5.6 Migrationsprotokoll je Vertrag

Mindestinhalte: Eingangswerte der Lieferobjekte, ermitteltes $t_a$, Kohorte, $(i_0, u_0)$, $V^{\mathrm{prosp}}$, $R_{\mathrm{hist}}$, ggf. $R_{\mathrm{conv}}$, Guardrail-Ergebnisse, Abgleichs- und Prüfergebnisse, Statusverlauf. Das Protokoll ist die Datengrundlage der Kapitel 6 und 7 und Teil der Revisionsdokumentation.

### 5.7 Offene technische Punkte

⟨TODO: Massenlaufsteuerung und Parallelisierung; Performance der pfadweisen Floor-Prüfung (Grundsatzdokumentation 9.16); Reihenfolge-Abhängigkeiten bei Vertragsbündeln (Haupt-/Zusatzversicherung); Umgang mit Verträgen mit GV zwischen Datenabzug und $t_0$⟩

## 6 Migrationscontrolling ($t_0$)

*Rahmen: Projektseitige Ausgestaltung von **Grundsatzdokumentation 9.15**, Zeile „Migrationscontrolling". Die Gate-Architektur entscheidet **ADR-010** (Trennung der Prüfebenen) und **ADR-009** (Fall-Scope und Pflichtbelege); die Handgriffe stehen im Skill `pruefe-migrationscontrolling`.*

### 6.1 Zweck und Abgrenzung

Das Migrationscontrolling misst am **Migrationsstichtag $t_0$** gegen
die Bilanz: Ist der Bestand vollständig übernommen, stimmen die Werte
zum Übernahmezeitpunkt, und schreibt das Zielsystem ihn danach fort wie
das Quellsystem? Es ist die **zweite** Prüfebene; die methodische Güte
prüft zuvor die aktuarielle Abnahme (Kapitel 7, Gate G-A).

Der Beweis endet nicht beim Stichtags-Foto. Ein Zielsystem, das den
übernommenen Bestand am $t_0$ trifft, ihn danach aber anders
fortschreibt, hat die Migration nicht bestanden. Deshalb prüft das
Controlling über **zwei Stichtage** und braucht dafür den Folge-Abzug
und das Geschäftsvorfall-Protokoll des Zwischenzeitraums.

### 6.2 Prüfgegenstand

Je Vertrag des Bestands:

1. **Deckungskapital am Migrationsstichtag** — die Bilanzgröße.
2. **Bruttojahresbeitrag am Migrationsstichtag**, sofern geliefert. Er
   ist die zweite Prüfachse gegen Parametrierungsfehler: Ein um ein Jahr
   versetztes Eintrittsalter verschiebt die Reserve oft nur um
   Bruchteile eines Cents, den Beitrag dagegen deutlich.
3. **Die Beträge der Geschäftsvorfälle** zwischen den Stichtagen
   (Storno, Tod, Ablauf, Beitragsfreistellung, dynamische Erhöhung).
4. **Deckungskapital am Folgestichtag** auf dem Track, den die
   Geschäftsvorfälle bestimmen.

Anders als der aktuarielle Test misst das Controlling **an gemeinsamen
Stichtagen** und darf dafür unterjährige Werte verwenden; die
Bilanzgröße ist am Bilanzstichtag gefragt, nicht am Vertragsjahrestag.
Genau deshalb sind es zwei Werkzeuge und nicht eines mit zwei Spalten.

### 6.3 Vollständigkeit und Prüflücken

„Vollständig geprüft" heißt hier: **jeder Vertrag des Bestands wurde
geprüft.** Ein ungeprüfter Vertrag ist eine **Prüflücke** — weder
bestanden noch fehlgeschlagen, sondern ungeprüft, und beim Lesen des
Verdikts abzuziehen. Die Prüfmenge wird zusätzlich gegen die
Zeilenzahl der Lieferung gestellt: Eine Abnahme über 400 von 500
Verträgen ist keine bestandene Abnahme, und ein dreimal gelieferter
Vertrag ist kein dreifacher Beleg.

Fehlt eine Erwartungsgröße in der Lieferung, wird sie als Lücke
ausgewiesen, nicht stillschweigend übergangen. Im Bestands-Scope
blockieren offene Prüflücken die Abnahme.

Inkonsistenzen der Lieferung — ein Geschäftsvorfall außerhalb der
Stichtage, ein Wert trotz Abgang, ein Abgang ohne Vorfall, ein Vorfall
auf dem falschen Track — sind **Befunde je Vertrag** und gehen an den
Menschen. Erwartungswerte werden nie „korrigiert", damit ein Lauf grün
wird.

### 6.4 Artefakte und Nachweiskette

1. **Das Suite-Ergebnis** (maschinenlesbar): je Vertrag die
   Einzelvergleiche, die Befunde, die Prüflücken; dazu die Bindungen an
   beide Stichtage, an die geprüfte Bestandsdatei und an den
   Systemstand.
2. **Der Abnahmebericht** (lesbarer Bericht): Verdikt, Prüfmenge,
   Prüflücken, Abnahmetests je Größe, sämtliche Einzelvergleiche,
   Fehlschläge, die Transformations-Mapping-Tabelle und die Verweise auf
   die Bestandsberichte vor und nach der Migration.
3. **Die Gate-Belege**: das Schema- und Invariantenprotokoll des
   übernommenen Bestands (Gate B1) und das Protokoll des
   Berichtslaufs.

Auch hier gilt: Der Bericht rechnet keine Fachwerte, sondern leitet
Residuen, Einzel-, Vertrags- und Suiteurteile aus den persistierten
Fakten neu ab und lehnt jede widersprüchliche Ableitung ab. Er ist
deterministisch und wird rot wie grün geschrieben.

Die SHA-256-Bindungen zwischen Bestandsdatei, Suite, Bericht und
Gate-Belegen sind **Transport- und Provenienzsicherung**: Sie belegen,
dass alle Nachweise denselben Stand meinen — sie ersetzen kein
fachliches Urteil.

### 6.5 Gate G-2: der Entscheid

Die Abnahme ist ein menschlicher Entscheid der Projektleitung auf
Grundlage des Berichts; ein grüner Berichtslauf heißt „Vorlage
vollständig", nicht „abgenommen". Der Entscheid wird als signierter
Snapshot festgehalten und pinnt die Pflichtbelege, die sich aus dem
**Fall-Scope** ergeben:

| Scope | Pflichtbelege von G-2 |
|---|---|
| Tarif | O1-Protokoll, geltender G-1-Snapshot, **geltender G-A-Snapshot**, O3-Belege je Generation |
| Bestand | zusätzlich B1-Protokoll, vollständige Suite, Abnahmebericht |

Die Annahme rechnet ihre Voraussetzungen nach: Sie hasht die
gebundenen Artefakte auf ihren aktuellen Bytes neu, validiert Suite und
Bestandsprotokoll erneut und rendert den Bericht aus der Suite
deterministisch nach, um ihn Byte für Byte zu vergleichen.

**Ohne geltende aktuarielle Abnahme (G-A) ist ein G-2-Entscheid
unmöglich** (Kapitel 7.7). Eine Ablehnung an G-2 führt zurück in die
Analyse; die Kette bildet das als neue Snapshots ab.

### 6.6 Deckungsgrad gegenüber Grundsatzdokumentation 9.15

Abgedeckt sind die Vertragsabstimmung, die Wertprüfung an beiden
Stichtagen und die Nachfahr-Abweichungen. **Nicht** abgedeckt sind die
übrigen in Grundsatzdokumentation 9.15 genannten Controlling-Kennzahlen:

* **Summen je Bestandsgruppe** (Deckungskapital, ZZR): Das Controlling
  urteilt heute je Vertrag und über die Prüfmenge, nicht über
  Bestandsgruppen-Aggregate der Bilanz.
* **$R_{conv}$-Statistik**: Der Konventionsresiduum-Pfad (Grundsatzdokumentation 9.13) ist
  nicht aktiviert; ob er für einen Bestand gefahren wird, ist eine
  Entscheidung im Kapitel „Entscheidungen und offene Punkte".
* **Überschussprojektion des Folgejahres**: als künftige Erweiterung
  benannt, nicht gebaut (ADR-010).

## 7 Aktuarielle Abnahme ($t_a$)

*Rahmen: Projektseitige Ausgestaltung von **Grundsatzdokumentation 9.15** (Prüfebene „Aktuarieller Test"), **Grundsatzdokumentation 9.15** (Toleranzdefinition auf der Verteilung) und **Grundsatzdokumentation 9.15** (Verlaufs- und Geschäftsvorfalltests). Die Gate-Architektur dahinter entscheidet **ADR-010**; die Handgriffe stehen im Skill `aktuartest-durchfuehren`. Dieses Kapitel beschreibt das Verfahren: was geprüft wird, woran das Urteil hängt, welche Nachweise entstehen und wer entscheidet.*

### 7.1 Zweck und Abgrenzung

Der aktuarielle Test misst die **methodische Güte** der konstruktiven
Neuberechnung — nicht die Bilanz. Er fragt: Rechnet das Zielsystem den
einzelnen Vertrag an dem Punkt richtig, an dem das Quellsystem ihn
zuletzt exakt gerechnet hat? Die finanzielle Frage („stimmt der Bestand
am Übernahmestichtag in Summe?") ist Gegenstand des
Migrationscontrollings (Kapitel 6).

Die Trennung ist bewusst und in der Reihenfolge bindend: **Die
aktuarielle Abnahme (Gate G-A) geht der Migrationsabnahme (Gate G-2)
voraus.** Eine finanzielle Abnahme des Gesamtbestands vor dem Nachweis
methodischer Güte nähme etwas ab, dessen Grundlage noch offen ist. Die
Reihenfolge ist technisch erzwungen, nicht empfohlen (7.7).

### 7.2 Prüfgegenstand: der Verankerungszeitpunkt je Vertrag

Geprüft wird **je Vertrag an seinem eigenen Verankerungszeitpunkt
$t_a$** (Grundsatzdokumentation 9.12: der letzte exakte Rechenpunkt des Quellsystems). $t_a$
ist damit ein **Vertragsattribut**, kein Parameter des Prüflaufs — zwei
Verträge desselben Bestands werden in aller Regel zu verschiedenen
Zeitpunkten verglichen.

Daraus folgen drei Regeln, die im Werkzeug erzwungen sind und nicht als
Konvention gelten:

1. **Keine Interpolation.** Verglichen wird am Rechenpunkt. Ein
   unterjähriger Vergleichszeitpunkt ist ein Konstruktionsfehler des
   Prüfauftrags und bricht den Lauf ab — er wird nicht als Befund
   ausgewiesen. Begründung (Grundsatzdokumentation 9.12): Ein interpolierter Wert misst die
   Interpolationskonvention mit und entwertet das Residuum als
   Diagnoseinstrument.
2. **Keine Summation der Vergleichsgrößen.** Werte zu verschiedenen
   Stichtagen zu addieren ergibt fachlich nichts. Der Test bildet
   deshalb keine Deckungskapital-Summe; er kennt ausschließlich
   Verteilungsgrößen des Residuums (7.4).
3. **Prüfsummen sind Transportsicherung.** Mitgelieferte Kontrollsummen
   und Datei-Hashes werden geprüft und **getrennt ausgewiesen**, nie
   als Teil des aktuariellen Urteils verrechnet.

### 7.3 Stichprobe

Der Test läuft auf einer **belegten Stichprobe**: benanntes Profil,
deterministisch gezogen, mit ausgewiesener Grundgesamtheit und
vollständiger Policenliste. Die Ziehung gehört zum Nachweis — ohne sie
ließe sich später nicht nachvollziehen, welche Verträge den Test
getragen haben.

„Vollständig" heißt auf dieser Prüfebene: **die Stichprobe wurde
vollständig abgearbeitet.** Die Nichtprüfung der Nicht-Stichprobe ist
kein Befund, sondern die Definition des Tests. (Im Controlling heißt
derselbe Begriff etwas anderes — dort ist jeder ungeprüfte Vertrag eine
Prüflücke, Kapitel 6.)

Der aktuelle Stand kennt genau ein Profil: **`vollbestand`** — die
Stichprobe ist der ganze Bestand. Für Bestände in der Größenordnung der
bisherigen Fälle ist das die fachlich richtige Wahl und zugleich der
Randfall der Parametrisierung. Weitere Profile (geschichtet nach
Historientyp, risikoorientiert) sind eine bewusste Erweiterungsstelle
und je Profil eine Festlegung des Aktuariats mit ADR-Nachzug.

### 7.4 Was gemessen wird

Je Vertrag und Größe wird das **Residuum** ausgewiesen:

$$R = \text{Wert des Zielsystems} - \text{Wert der Lieferung}$$

Geprüft werden die Größen, die die Lieferung zum Verankerungszeitpunkt
führt: Deckungskapital ($kVx_{MRV}$), Rückkaufswert, Bruttojahresbeitrag
und — im beitragsfreien Zustand — die beitragsfreie Summe. Eine nicht
gelieferte Größe wird nicht geprüft; eine unbekannte Größe im Auftrag
ist ein harter Fehler statt einer stillen Auslassung.

Aggregiert wird **ausschließlich über die Verteilung der Beträge
$|R|$**, geclustert nach **Historientyp** (der Übergangsklasse der
Vertragshistorie): Maximum, hohe Perzentile und Betragssumme der
Abweichungen je Cluster. Mittelwert und Median werden bewusst nicht
gebildet (Grundsatzdokumentation 9.15): Erwartet wird Bimodalität, und ein unauffälliger
Mittelwert bei großen Einzelmaxima ist ein Befund, keine Entwarnung.

**Lesehilfe für die Vorlage.** Cent-Größenordnung in den Perzentilen ist
Rundungsrauschen der Lieferung. Ein Maximum, das deutlich darüber liegt,
verlangt eine **benannte Ursache je Cluster** — „Rundung" ist als
Erklärung nur für Cent-Beträge zulässig. Ein Cluster, dessen Verteilung
sich von den anderen abhebt, zeigt auf seinen Historientyp: dort ist die
Übergangsbehandlung zu prüfen, nicht der einzelne Vertrag.

### 7.5 Befundarten

| Befund | Bedeutung | Fortgang |
|---|---|---|
| Wertabweichung außerhalb der Toleranz | Der Vergleich schlägt fehl | Ursache je Cluster benennen; Klärung mit dem abgebenden Unternehmen oder Korrektur der Methode |
| Vertrag nicht rechenbar | Lieferdaten ergeben keinen gültigen Modellpunkt | Datenklärung; der Vertrag bleibt in der Stichprobe und zählt als fehlgeschlagen |
| Stichprobe nicht abgearbeitet | Ein gezogener Vertrag hat keinen Prüfauftrag (oder ein Auftrag liegt außerhalb der Ziehung) | Der Test ist nicht bestanden — die Abdeckungsbehauptung trägt nicht |
| Konstruktionsfehler des Auftrags | Unterjähriges $t_a$, unbekannte Größe, undefinierte Zustandskombination | Lauf bricht ab; der Auftragsbau ist zu korrigieren, nicht das Ergebnis |

Toleranzen kommen aus einer Quelle und werden nie aufgeweicht, „um grün
zu werden". Stellt sich eine Toleranzfrage, ist sie eine fachliche
Entscheidung des Aktuariats und kein Parameter des Laufs.

### 7.6 Artefakte und Nachweiskette

Ein Testlauf hinterlässt drei Dinge:

1. **Das Testergebnis** (maschinenlesbar): Stichproben-Beleg samt
   Policenliste, je Vertrag die Einzelvergleiche mit Residuum und
   Urteil, die Verteilungsgrößen je Cluster, die Transportangaben und
   der Systemstand, unter dem gerechnet wurde.
2. **Die Entscheidungsvorlage** (lesbarer Bericht): dasselbe in der
   Form, in der der Verantwortliche Aktuar entscheidet — Verdikt,
   Stichprobe, Verteilung je Cluster, Fehlschläge, Einzelvergleiche,
   Transportsicherung als eigener, ausdrücklich vom Urteil getrennter
   Abschnitt.
3. **Der Gate-Beleg**: das Prüfprotokoll des Werkzeugs mit den Hashes
   von Ergebnis und Bericht.

Die Vorlage ist deterministisch: gleiche Eingaben ergeben denselben
Bericht Byte für Byte. Ein **roter** Bericht wird geschrieben wie ein
grüner — er ist das Beweisstück, nicht sein Gegenteil.

Das Werkzeug leitet das Verdikt aus dem Ergebnis **neu ab**, statt ihm
zu glauben: Einzelurteile gegen die Toleranzen, Zähler, Mengenabgleich
gegen die Stichprobe und sämtliche Verteilungsgrößen werden
nachgerechnet. Eine grüne Zusammenfassung über einem roten
Einzelvergleich ist damit ausgeschlossen.

### 7.7 Gate G-A: der Entscheid

Der Test **entscheidet nichts**. Die aktuarielle Abnahme ist ein
menschlicher Entscheid des **Verantwortlichen Aktuars** (Grundsatzdokumentation 9.15,
§ 141 VAG) auf Grundlage der Vorlage. Ein grüner Testlauf heißt „Vorlage
vollständig und Test bestanden", nicht „abgenommen".

Der Entscheid wird als unveränderlicher, signierter Snapshot
festgehalten (ADR-008). Dabei gilt:

* Eine **Annahme rechnet ihre Voraussetzungen nach**: Das Testverdikt
  wird aus dem Ergebnis neu abgeleitet, der Bericht aus dem Ergebnis
  deterministisch reproduziert und gegen die abgelegte Fassung
  verglichen, und das Ergebnis muss den Systemstand des Entscheids
  tragen. Ein nachträglich geänderter Prüfbeleg öffnet das Gate nicht.
* Die Annahme **pinnt** Testergebnis und Bericht als Pflichtbelege.
* Eine **Ablehnung ist jederzeit möglich** und ebenso ein Snapshot —
  auch über einem roten Test. Ein Agent kann an diesem Gate
  ausschließlich ablehnen.
* **Gate G-2 verlangt die geltende G-A-Annahme** auf demselben Eingangs-,
  A-Box- und Systemstand und pinnt sie als Pflichtbeleg. Ändert sich der
  Stand, ist die G-A-Annahme nicht mehr geltend — der Test wird auf dem
  neuen Stand wiederholt und neu entschieden.
* Die **Rückschleife ist zulässig**: Eine Ablehnung an G-2 führt zurück
  in Analyse und ggf. erneuten Test; die Kette bildet das als neue
  Snapshots ab. Unzulässig bleibt allein die Umkehrung der Reihenfolge.

### 7.8 Deckungsgrad gegenüber Grundsatzdokumentation 9.15

Der heutige Stand deckt Grundsatzdokumentation 9.15 (Prüfebene, Zeitbezug, Verantwortung)
und die Auswertungsform aus Grundsatzdokumentation 9.15 (Verteilung statt Mittelwert)
vollständig ab. **Nicht** abgedeckt sind:

* **Grundsatzdokumentation 9.15 — Verlaufs- und Geschäftsvorfalltests.** Vorwärtsrechnung
  über mehrere Jahre gegen eine Schattenrechnung des Quellsystems und
  die GV-Testmatrix je Vertragskonstellations-Cluster gibt es auf dieser
  Prüfebene nicht. Grundsatzdokumentation 9.15 ist hier eindeutig: *„Ohne Verlaufstests gilt
  die Methode als nicht abgenommen; Stichtagstreue allein ist notwendig,
  nicht hinreichend."* Eine G-A-Annahme auf dem heutigen Stand belegt
  also die Stichtagstreue am Rechenpunkt — sie ersetzt die Verlaufstests
  nicht und darf nicht als deren Erfüllung gelesen werden.
* **Toleranzen auf der Verteilung als Urteilskriterium.** Die Verteilung
  wird ausgewiesen, aber das maschinelle Urteil hängt heute an
  Toleranzen je Einzelwert. Eine Schwelle auf Maximum oder hohem
  Perzentil je Cluster (Grundsatzdokumentation 9.15) ist eine Festlegung des Aktuariats und
  noch nicht getroffen.
* **Das methodische Residuum $R_{hist}$.** Solange es keine
  Korrekturschicht gibt (Grundsatzdokumentation Abschnitt 9), trägt der Test den vorhandenen
  Wertvergleich — am richtigen Zeitpunkt und ohne Summen. Der Platz für
  $R_{hist}$ ist im Werkzeug benannt und leer; er wird gefüllt, wenn die
  Korrekturschicht steht, ohne dass sich Verfahren, Gate oder
  Nachweiskette ändern.
* **Floor-Prüfungen** (§ 169 VVG, Grundsatzdokumentation 9.10) als Teil des Tests.

Diese vier Punkte sind der Arbeitsvorrat dieser Prüfebene. Sie stehen
hier, damit eine Abnahme weiß, was sie abnimmt.

⟨TODO aus dem Geruest, noch offen: Clusterdefinition nach
GV-Historientyp aus Lieferobjekt 2; Ausreisser-Klaerungsworkflow mit
Zugriff auf die Quellhistorie; Stichprobenkonzept jenseits des Profils
`vollbestand`; Form des Abnahmeberichts an den Verantwortlichen
Aktuar⟩

## 8 Fehler- und Klärungsprozess

Abgrenzung bindend gemäß Grundsatzdokumentation 9.4: Die Korrekturschicht absorbiert Bewertungsdifferenzen bei unveränderten Ankern; jede Veränderung eines Ankers (Quellfehler) ist ein Kundenrechts- und Kommunikationsthema und läuft über diesen Prozess — niemals über die Schicht. ⟨TODO: Prozessdefinition, Rollen, Schwellen für Einzelfallklärung, Nachzahlungs-/Kommunikationsregeln, Schnittstelle zur Kappungs-Kohorte aus 5.5⟩

## 9 Archiv und Auskunftssystem

Anforderungen gemäß Grundsatzdokumentation 9.14 (Rolle „Archiv") und Grundsatzdokumentation 9.14: read-only, dauerhaft, auskunftsfähig für Aufbewahrungspflichten, Auskunftsersuchen und Rückabwicklungsfälle inkl. der dafür nötigen Wertehistorie. Keine Anforderung an den RK. ⟨TODO: Lösungsarchitektur, Auskunftsumfang und -fristen, Betriebsmodell, Löschkonzept⟩

## 10 Ablaufplanung

⟨TODO: Migrationsstrategie (Big Bang vs. Wellen), Generalproben, Parallellauf/Schattenbetrieb mit Delta-Reporting (Grundsatzdokumentation 9.15), Cut-over-Drehbuch, Rückfallszenario⟩

## 11 Entscheidungen und offene Punkte

| Nr | Gegenstand | Bezug | Status |
|---|---|---|---|
| E1 | GV-Metadatenliste dauerhaft im Zielbestand vs. Verbleib im Migrations-Staging | Grundsatzdokumentation 9.16 | ⟨ENTSCHEIDUNG: offen⟩ |
| E2 | Aktivierung des $R_{\mathrm{conv}}$-Pfads (Zweitverankerung am $t_0$) für diesen Bestand | Grundsatzdokumentation 9.13 | ⟨ENTSCHEIDUNG: offen⟩ |
| E3 | ⟨…⟩ | ⟨…⟩ | ⟨…⟩ |
