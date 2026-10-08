# Migrations-Pipeline v0.1: Ontologie als Stage-Interface

> **Teilweise überholt (Stand des Dokuments: 2026-08-15, einzelne
> Ergänzungen bis 2026-10-01).** Es
> beschreibt den Stand vor
> [ADR-006](adr-006-portierung-ausser-betrieb.md) (Portierung außer
> Betrieb) und [ADR-007](adr-007-parallele-migrationen-ein-kern.md)
> (parallele Migrationen in einem Kern). Überholt sind insbesondere:
> die G0-G8-Abnahmekette des Sechs-Datei-Vergleichskerns (Abschnitt 7)
> — sie existiert nicht mehr, heute gibt es nur noch die Gates
> `extract`, `abox_merge`, `abox_validate`, `generation_golden`,
> `gate_entscheid`, `bestand_validate`, `aktuartest` und
> `abnahmebericht`; die
> Aussage, in Stufe 1 gebe es keine Bestandsdaten-Quelle (Abschnitt 8);
> der Skill-Zuschnitt (Abschnitt 9); und die ADR-Liste (Abschnitt 10).
> Die Prinzipien, die Stufenlogik und die Objektmodelle gelten
> unverändert. Seit diesem Stand kamen hinzu: die aktuariellen Abnahmen
> A-M1 bis A-M3 vor A-M4 (ADR-010, ADR-012), der abgenommene Stand des
> Zielsystems aus Kern, T-Box und Tarifwerk (ADR-018, ADR-025), der
> Fallauftrag (ADR-026) und der Zugang in die Ablage (ADR-022). Die
> Pflichtbelege je Gate stehen in
> [gate-vertrag-und-versionen.md](gate-vertrag-und-versionen.md), der
> aktuelle Rollen-Katalog in [skill-architektur.md](skill-architektur.md).

Stand: 2026-08-15, einzelne Ergänzungen bis 2026-10-01. Am Migrationsfall KLV TG2012 -> TG2015 maschinell
abgenommen (Gate P-K1: 616 Werte gegen den Quell-Rechner, 0 Abweichungen);
die menschlichen Gates A-Q1/A-M1/A-M4 des Falls stehen aus (8 vorläufige
Diskrepanz-Auflösungen warten auf die fachliche Entscheidung). Dieses
Dokument beschreibt Architektur und Ist-Stand — was v0.1 bewusst nicht
kann, steht in Abschnitt 8. Die Prinzipien in Vollform: prinzipien.md.

## 1 Idee

Eine Bestandsmigration übersetzt heterogene Quellen (Tarifmeldungen,
Quell-Rechner, Bestandsdaten) in einen abgenommenen Rechenkern. Das
einzige Interface zwischen den Stufen ist eine Ontologie:

* **T-Box** (`ontologie/tbox.py`): das Domänenmodell — menschlich
  verantwortet, versioniert; Agenten ändern es nie autonom (Gate A-O1).
* **A-Box** (Instanzen eines Falls): von Agenten befüllt, von
  deterministischem Code gemergt und validiert; Single Source of Truth
  für alles Nachgelagerte. Kanonischer Speicher ist deterministisches
  JSON im Fall-Arbeitsbereich (ADR-002); ein Graph-Store wäre eine
  jederzeit neu baubare Projektion.

Kein Agent einer späteren Stufe liest Rohquellen einer früheren.

## 2 Die drei Stufen am realen Fall

```
Fall-Arbeitsbereich (ADR-002): eingang/ (registriert, SHA-256) -> abgeleitet/

Stufe 1  Quellen -> A-Box
  deterministisch: quellen/extract (XLSM), quellen/tarifplan_staging (DOCX)
  LLM:            je (Quelle x Generation) EIN Extraktions-Agent,
                  Structured Output gegen das generierte QuellFragment-Schema;
                  der Agent sieht NIE die andere Quelle
  deterministisch: ontologie/befuellung — Provenienz-Anreicherung aus dem
                  Eingang-Register, Merge (Widerspruch => Diskrepanz-Objekt),
                  Coverage gegen den T-Box-Pflichtumfang
  Gate P-Q3 (abox_validate): Contract + Register-Bindung + Coverage +
                  offene Diskrepanzen blockieren

Stufe 2  A-Box -> Spez -> Kern-Parametrierung
  deterministisch: spez/erzeugen — Projektion mit hartem Vorbedingungs-Check;
                  StrukturUrteil BERECHNET (Parametrierung vs. neues Produkt);
                  spez/fachspez — das menschenlesbare A-Q1-Dokument (P7)
  deterministisch: quellen/tafel_import — Tafeln + Ableitungen (Unisex-
                  Mischtafel als DATEN-Regel, VBA-bit-treu) nach kern/tafeln.xml;
                  bindet registrierte XLSM, Exportmanifest und konkrete
                  Blatt-CSV ueber vollstaendige SHA-256-Werte; erzwingt exakt
                  die Alter 0..123 sowie endliche qx in [0,1] an Import- und
                  Kern-XML-Ladegrenze
  Gate A-Q1 (Mensch): Fachspez + Diskrepanzen + Coverage; Werkzeuge:
                  ontologie/entscheide (Aufloesung), gates/gate_entscheid (P9)

Stufe 3  Abnahme
  Gate P-K1 (generation_golden): Kern (Spez-parametriert) gegen die aus dem
                  Quell-Rechner extrahierten Erwartungswerte; prueft vorab,
                  dass die Spez gueltige Projektion der A-Box ist; schreibt
                  je Generation einen inhaltsadressierten Beleg mit A-Box-
                  und Systemstand
  Gate A-M1 (Mensch): aktuarielle Abnahme VOR A-M4 (ADR-010) — Vorlage
                  `gates.aktuartest` (Test je Vertrag am eigenen
                  Verankerungszeitpunkt, belegte Stichprobe); im
                  Bestands-Scope pinnt A-M1 Testergebnis und Bericht
  Stand des Falls (ADR-018, Nachtrag 2026-10-01): Kernstand (Gate A-K2,
                  mensch/rechenkern, Vorlage `gates.kernstand_belegen`)
                  und T-Box-Stand (Gate A-O1, mensch/architektur) sind
                  abgenommen — im Fall gezeichnet, "keine Aenderung"
                  ueber einen Verweis (`gates.stand_belegen`) oder
                  (T-Box) Basislinie
  Gate A-M4 (Mensch): P9-Snapshot — verlangt die Pflichtbelege je Gate
                  und Scope. Tarif: P-Q3/A-Q1/A-M1/P-K1 und der Stand des
                  Falls (kernstand, tboxstand). Bestand zusaetzlich:
                  P-B1, vollstaendige Zwei-Stichtags-Suite und gruener
                  Abnahmebericht; A-M4 revalidiert alles auf demselben
                  Eingangs-, A-Box-, System-, Bestands- und Stichtagsstand
```

## 3 Die tragenden Objekte

| Objekt | Trägt | Prinzip |
|---|---|---|
| `Aussage` | Wert, Zustand (belegt / nicht_belegt / mehrdeutig / widersprüchlich), Konfidenz, Provenienz je Beleg (Quelle+SHA-256, Fundstelle, Akteur, Zeit); unveränderlich nach Konstruktion | P1, P3 |
| `Diskrepanz` | beide Lesarten mit Belegen; Auflösung nur als expliziter Vorgang (Entscheider, Begründung, ggf. `vorlaeufig`) | P2 |
| `Parametrierungszelle` | eine Merkmalskombination; Felder = exakt die Kern-ModelPoint-Stellschrauben; Zellen decken den Merkmalsraum exakt | P5, P6 |
| `Tarifgeneration.tarifwerk` / `.quellverfahren` (T-Box 0.2.0, ADR-024) | generationsweite Aussagen: wie die Generation erhöht, zurückkauft, herabsetzt (Namen der Bestand-Config), und wie die Quelle eine gelieferte Absetzung gemeint hat; Widerspruch = Diskrepanz am Knoten `<generation>/<block>`; in der Coverage ausgewiesen, nicht blockierend | P1, P2, P6 |
| `TarifSpez` | Parametrierung des Rückgrats + StrukturUrteil + Tafel-Importe/-Ableitungen + benannte Erweiterungsstellen; validierbar als Projektion der A-Box (beide Richtungen) | D2 (SDD, gebunden) |
| P9-Snapshot | Schema, Gate/Command/Version, Entscheid, Entscheider, Begründung, SHA-256 aller Fall-Artefakte, Git-Stand und Vorgänger; A-M1 und A-M4 pinnen zusätzlich Scope und rollenbezogene Pflichtbelege je Gate; vollständig inhaltsadressiert, nie überschrieben; eine Annahme trägt eine HMAC-Freigabe aus einem extern verwahrten Schlüssel | P9, P1 |

## 4 Deterministisch / LLM — die Trennlinie (P4)

LLM-Agenten tun genau eines: die Vorverdichtung einer Quelle lesen und
ein Fragment vorschlagen (mit Fundstellen, Konfidenz, explizitem
„gesucht, nicht gefunden“). Alles andere ist Code: Merge, Konflikt,
Coverage, Struktur-Urteil, Projektion, Tafel-Ableitung, Vergleich,
Gates. Ein Widerspruch zwischen Quellen entsteht im Merge-Code, nie im
Agenten-Urteil; die Auflösung ist ein Mensch.

## 5 Coverage statt Plausibilität (P6)

Gemessen wird gegen den Pflichtumfang der T-Box, nicht gegen das
zufällig Extrahierte. Drei unterscheidbare Fehl-Zustände: `nicht_belegt`
(Agent hat gesucht), `fehlt_in_extraktion` (kein Agent hat das Feld auch
nur erwähnt — der gefährliche stille Fall), `widerspruechlich`. Gate P-K1
weist zusätzlich aus, was der GM nicht deckt (Zellen ohne
Erwartungswerte, übersprungene Erwartungsreste).

## 6 Der Präzedenzfall TG2012 -> TG2015

Die fachliche Vorgabe — „erkennen, dass der neue Rechner strukturell zum alten
passt, und integrieren statt duplizieren“ — ist als berechnetes
StrukturUrteil umgesetzt: `parametrierung`, mit zwei neuen
Merkmalsdimensionen (Tarifart, Raucherstatus), neun geänderten
Parametern und sechs Tafel-Anforderungen. Die Unisex-Vorgabe U70 wurde
zur abgeleiteten Mischtafel (`qx = min(1, 0.7*qx_M + 0.3*qx_F)`,
Double-Arithmetik VBA-treu), ohne eine Formeländerung am Kern, weil die exakte
Tafelnamens-Auflösung des Kerns genau dafür vorgesehen war. U70 ist
eine Kalkulations-Vorgabe (alle Verträge werden unisex bewertet); das
Geschlecht bleibt Bestandsmerkmal ohne Tarifwirkung.
Nebenbefund der Pipeline: Meldung und Rechner widersprechen sich real
(Rechnungszins 1,25 % gegen 1,75 %; beta1 Haustarif 1,0 % gegen 0) —
als Diskrepanz-Objekte erfasst, vorläufig zur Rechner-Lesart gelöst
(der GM reproduziert den Rechner), fachliche Entscheidung im Gate A-Q1.

## 7 Zusammenspiel mit der bestehenden Abnahme

Die O-Gates (P-Q3, P-K1) und P9-Snapshots stehen neben der G0-G8-Kette und
teilen nur den Ledger-Mechanismus (`gates/_common`). Die G-Kette bleibt
der Abnahme-Weg des Sechs-Datei-Vergleichskerns; die Integration beider
Wege ist eine Team-Entscheidung nach Fall 1.

**Überholt seit ADR-006:** die G0-G8-Kette und der
Sechs-Datei-Vergleichskern sind außer Betrieb — `gates.validate`,
`gates.security` und `gates.dossier` gibt es nicht mehr; erhalten
blieben nur `gates.extract` (P-Q1) und der Ledger-Mechanismus. Die
Frage der Integration beider Wege hat sich damit erledigt: es gibt nur
noch den O-/P9-Weg auf dem stabilen Zielkern.

## 8 Bewusst nicht in v0.1

* GM deckt die Beispiel-Zelle des Quell-Rechners (einzel/nichtraucher);
  die übrigen fünf Zellen brauchen weitere Erwartungswerte
  (zusätzliche Modellpunkte vom Lieferanten oder COM-Neuberechnung) —
  Gate P-K1 weist das Komplement aus.
* Der deterministische Formel-Rück-Check (quellen/formeln.py, in Gate
  P-Q3 eingebaut) deckt die IF-Staffeln; andere Formelformen prüft er
  fail-fast als „nicht prüfbar“ — ein breiterer Formel-Parser bleibt
  offen.
* Kein Graph-Store, keine Embeddings, keine BU-/FLV-/Renten-Klassen in
  der T-Box (kommen mit ihren Fällen über A-O1), kein Legacy-Code-
  Vorverdichter, keine Bestandsdaten-Quelle in Stufe 1 (Quelltyp ist im
  Schema vorgesehen).
  Überholt, soweit es die Bestandsdaten betrifft: den Quelltyp
  Bestandsabzug/CSV gibt es inzwischen als eigenen Vorverdichter
  (`quellen/bestand_profil.py`), auf dem der Skill
  `transformiere-quellbestand` arbeitet.
  T-Box 0.2.0 (ADR-024): Die BU steht als
  Vokabular in der T-Box (Zustände, Leistungsgröße,
  Rechnungsgrundlagen, ihre Geschäftsvorfälle), instanziierbar bleibt
  in der A-Box nur die KLV (`ABOX_FAMILIEN`) — Extraktion, Spez und P-K1
  für das Zustandsmodell kommen mit dem ersten BU-Fall. Neu sind
  Tarifwerk und Quellverfahren je Generation als belegte Aussagen, der
  Katalog der Geschäftsvorfälle, das Vertragsvokabular einer Lieferung
  und der Zustandsextrakt der Migration; jede dieser Mengen ist ein
  test-gebundener Spiegel des Codes, nicht eine zweite Wahrheit.
* Fall-Artefakte (A-Box, Spez, Entscheide) liegen im gitignorierten
  Fall-Arbeitsbereich — die Versionierung echter Fälle außerhalb des
  Repos ist ADR-002-Zielbild, in v0.1 nicht ausgebaut. Die
  Nachweiskette endet damit an einem Einzelplatz; ein geteilter,
  versionierter Fall-Speicher ist Team-Entscheidung.
* Das Struktur-Urteil arbeitet innerhalb einer menschlich vorgegebenen
  Produktfamilie: es kann Parametrierung von Erweiterung unterscheiden,
  aber „neue Produktfamilie“ nicht selbst feststellen — die T-Box
  kennt kein Leistungsversprechen/Zahlungsprofil. Kommt mit Fall 2
  (Risiko/Rente zwingen Zahlungsprofile in T-Box und Spez — die
  gebundene Spez ist erst zur Hälfte gebaut: Zustandsraum,
  Zahlungsprofile, GeVo-Katalog fehlen).
* Gate P-K1 nimmt strukturell die Rechner-Lesart ab (der GM reproduziert
  den Quell-Rechner). Entscheidet A-Q1 fachlich gegen den Rechner
  (z. B. Zins 1,25 % der Meldung), braucht die Abnahme korrigierte
  Erwartungswerte des Lieferanten — diesen Pfad gibt es noch nicht.
* Die 1M-LOC-Mechanik ist seit ADR-005 gebaut: hierarchische Knoten
  (`familie[/generation]`, Wurzel validiert), Test-Knoten-Bindung
  (jede Testdatei, drift-geprüft), nachrechenbare Schichtenkarte
  (`ontologie.code_karte`; die Zweitkern-Regel aus ADR-004 entfiel mit
  dem Zweitkern, siehe Nachtrag in ADR-013) und
  berechneter Änderungs-Impact (`ontologie.impact`, Lineage-Selektion,
  konservativ bei jeder Unsicherheit). Noch nicht gebaut: Tafel-/
  Zellen-Granularität der Daten und die Verdrahtung als selektive
  Gates — CI und Vor-Commit fahren weiter die volle Suite (der Rest
  folgt mit Fall 2).
* P10 ist für Extraktions-Agenten instruiert (Skill), nicht technisch
  erzwungen (kein Sandbox-Zwang auf die Vorverdichtung).

### 8.1 Die A-Box trägt Parameter, keine Formeln — Formelidentität ist in v0.1 Menschensache

Das ist die wichtigste bewusste Grenze der Version, weil sie leicht mit
einem Versehen verwechselt wird. Sie ist keines.

**Was der Contract trägt.** Ein `QuellFragment` führt je Zelle
`auspraegungen` und `parameter` — Zahlen und Zeichenketten, die in die
Stellschrauben des Kern-ModelPoints münden. Ein Feld für Formeln gibt
es nicht. Der Merge vergleicht folglich Parameterwerte: Rechnungszins
gegen Rechnungszins, Kostensatz gegen Kostensatz. Zwei Quellen, die
dieselbe Größe nach verschiedenen Formeln bestimmen, aber gleich
parametrisiert sind, erzeugen keine Diskrepanz — und was keine
Diskrepanz ist, kann kein Gate finden und kein Gate an A-Q1 vorlegen.

**Was daraus folgt.** Gate P-K1 belegt, dass der Kern denselben Wertepfad
liefert wie der Quell-Rechner (auf den Cent). Er belegt nicht, dass die
Tarifmeldung dieselbe Formel meint. Weicht die Meldung vom Rechner in
der Formel ab, bleibt P-K1 grün. Im Präzedenzfall TG2015 sind beim
menschlichen Lesen genau solche Stellen aufgefallen — Ziffer 3.2 leitet
die prämienfreie Leistung aus dem Rückkaufswert (also nach
Stornoabschlag) ab, während Rechner und Kern
`VS_bfr = kVx_MRV / kVx_bfr` rechnen; Ziffer 5.2.1 schreibt die
normierte Reserveprämie mit `B_{x,n}`, während Ziffer 3.1 und der
Rechner mit `B_{x,t}` arbeiten. Gefunden hat das ein Mensch, nicht die
Pipeline. Solche Stellen gehören als benannte Abweichung in die
A-Q1-Vorlage, nicht in eine Fußnote.

**Warum bewusst so entschieden.** Ein Formelvergleich zwischen der
Meldung (OMML-Formeln in Word) und dem Rechner (Excel-Zellformeln) ist
kein Zeichenketten-Vergleich, sondern eine Äquivalenzfrage über zwei
verschiedene Sprachen mit verschiedenen Bezugsgrößen und
Indexkonventionen. Ein halber Vergleich wäre schlimmer als keiner: er
produziert entweder Falsch-Alarme oder — gefährlicher — grüne Balken
für eine Identität, die er nie geprüft hat. v0.1 nimmt deshalb die
Parametrierung maschinell ab und weist die Formelidentität
ausdrücklich dem Menschen zu: Abnahme gegen den Tarifplan
(`docs/tarifplaene/`) im Gate A-Q1. Der vorhandene deterministische
Rück-Check (`quellen/formeln.py`, in Gate P-Q3) ist die einzige
Ausnahme und beschreibt seinen Umfang selbst ehrlich: er prüft die
IF-Staffeln des Rechners gegen die extrahierten Werte und meldet jede
andere Formelform als „nicht prüfbar“ — er vergleicht also innerhalb
einer Quelle, nicht zwischen zweien.

**Ausbaupfad (nicht in v0.1).** Feld `formeln` im QuellFragment
(Zeichenkette plus Fundstelle je Ziffer), dazu ein Gate, das die
extrahierten Formeln je Ziffer gegen die Paragrafen des Tarifplans
stellt. Das ändert den Contract und ist damit eine T-Box-Frage
(Gate A-O1). Auslöser: der erste Fall, in dem der Quell-Rechner nicht
die abzunehmende Lesart ist — etwa eine Lieferung ohne Rechner oder
eine A-Q1-Entscheidung gegen den Rechner.

## 9 Wissensverteilung: wo das Migrations-Know-how lebt

Das System wird nicht „trainiert“ — sein Wissen ist verteilt auf vier
Schichten, jede versioniert, jede mit eigener Änderungs-Disziplin:

| Schicht | Trägt | Ort | Ändert sich durch |
|---|---|---|---|
| Deterministischer Code | das Verfahren selbst: Vorverdichtung, Merge, Konfliktbildung, Coverage, Struktur-Urteil, Projektion, Tafel-Ableitung, Vergleich, Gates | `quellen/`, `ontologie/`, `spez/`, `gates/` | Commits unter Test-Pflicht |
| Contracts & T-Box | Was zu extrahieren ist (QuellFragment-Schema, generiert), was Pflicht ist (PFLICHT_PARAMETER), wohin es mappt (ModelPoint-Felder) | `ontologie/tbox.py`, `ontologie/befuellung.py` | Gate A-O1 (T-Box-Änderung, Mensch) |
| Skills (Agenten-Anweisungen) | Wie die probabilistischen Schritte urteilen: Extraktionsregeln je Quelltyp, das systematische Vorgehen eines Falls, Abbruchkriterien | `.claude/skills/` + `.agents/skills/` (Parität test-tragend): `migrationsfall-durchfuehren` (Runbook), `extrahiere-quellfragment` (Stage-1-Agent) | Commits; der Skill-Stand (Git-SHA) gehört in den Akteur-String der Provenienz (P1) |
| Präzedenzfall | Wie ein fertiges Ergebnis aussieht: A-Box, Spez, Fachspez, Diskrepanzen, Gate-Ledger des Falls KLV TG2012->TG2015 | `faelle/baldrian-klv-tg2015` (lokal; echte Fälle außerhalb des Repos) | jeder abgeschlossene Fall wird Referenz des nächsten |

Überholt ist die Skill-Zeile in ihrem Umfang: Aus den zwei genannten
Skills sind inzwischen elf geworden (Extraktion, Runbook, Transformation
des Quellbestands, Konfliktaufbereitung, aktuarieller Test,
Migrationscontrolling, Entwicklung im Zielsystem, Gate-Autorenschaft,
Inkrement-Integration, Doku, adversariales Testen). Verbindlicher Katalog mit Rollen und Grenzen:
[skill-architektur.md](skill-architektur.md).

Die Verteilungsregel dahinter: Wissen, das gelten muss, wandert in Code
und Contracts (erzwungen); Wissen, das Urteilen anleitet, in Skills
(versioniert, in der Provenienz zitiert); Wissen, das zeigt, in den
Präzedenzfall. Fachliche Zuordnung der von einer Migration verlangten
Fähigkeiten: Quelldatenverarbeitung = Vorverdichter + Extraktions-Skill
+ Formel-Rück-Check; Konsistenzchecks = Merge/Diskrepanzen + Gates
P-Q3/P-K1 + Kreuzproben des Tafel-Imports; Transformation/Mapping = T-Box
(Feldnamen sind das Mapping) + quellnamen-Erfassung + Spez-Projektion;
Coding = für Parametrierungs-Fälle nicht vorgesehen (Erweiterungs-
stellen wären der benannte Ort, mit eigenem Skill, sobald ein Fall sie
braucht); Testing/Abnahme = Gate-Kette + Suite + menschliche Gates.

## 10 Verweise

ADR-001 (Repo-Zielstruktur), ADR-002 (Fall-Arbeitsbereich), ADR-003
(Pydantic für die Ontologie-Schicht), ADR-004 (Thiele-Kern ohne
Excel-Referenzwerte; Kommutation als separater Zweitkern), ADR-005
(Knoten-Hierarchie, Test-Bindung, Code-Karte, Impact). Hinzugekommen
seit Redaktionsschluss dieses Dokuments — und für den heutigen Stand
maßgeblich: ADR-006 (Portierungs-Anwendungsfall außer Betrieb; die
G-Kette entfällt), ADR-007 (parallele Migrationen in einem Kern;
knotengebundene Inkremente auf einem Hauptzweig), ADR-008 (signierte
P9-Freigaben) und ADR-009 (Fall-Scope und Bestands-Pflichtbelege).
Entscheidungsgrundlage war eine Fragerunde zur Architektur; ihre
Ergebnisse stehen in diesen ADRs.
