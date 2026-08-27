# Migrations-Pipeline v0.1: Ontologie als Stage-Interface

> **Teilweise ueberholt (Stand des Dokuments: 2026-08-15).** Es
> beschreibt den Stand VOR
> [ADR-006](adr-006-portierung-ausser-betrieb.md) (Portierung ausser
> Betrieb) und [ADR-007](adr-007-parallele-migrationen-ein-kern.md)
> (parallele Migrationen in einem Kern). Ueberholt sind insbesondere:
> die G0-G8-Abnahmekette des Sechs-Datei-Vergleichskerns (Abschnitt 7)
> — sie existiert nicht mehr, heute gibt es nur noch die Gates
> `extract`, `abox_merge`, `abox_validate`, `generation_golden`,
> `gate_entscheid`, `bestand_validate`, `aktuartest` und
> `abnahmebericht`; die
> Aussage, in Stufe 1 gebe es keine Bestandsdaten-Quelle (Abschnitt 8);
> der Skill-Zuschnitt (Abschnitt 9); und die ADR-Liste (Abschnitt 10).
> Die Prinzipien, die Stufenlogik und die Objektmodelle gelten
> unveraendert — mit einer Erweiterung: ADR-010 schaltet dem Gate A-M4
> das menschliche Gate A-M1 (aktuarielle Abnahme, Vorlage
> `gates.aktuartest`) zwingend vor. Aktueller Rollen-Katalog:
> [skill-architektur.md](skill-architektur.md).

Stand: 2026-08-15. Am Migrationsfall KLV TG2012 -> TG2015 MECHANISCH
abgenommen (Gate P-K1: 616 Werte gegen den Quell-Rechner, 0 Abweichungen);
die MENSCHLICHEN Gates A-Q1/A-M1/A-M4 des Falls stehen aus (8 vorlaeufige
Diskrepanz-Aufloesungen warten auf die fachliche Entscheidung). Dieses
Dokument beschreibt Architektur UND Ist-Stand — was v0.1 bewusst nicht
kann, steht in Abschnitt 8. Die Prinzipien in Vollform: prinzipien.md.

## 1 Idee

Eine Bestandsmigration uebersetzt heterogene Quellen (Tarifmeldungen,
Quell-Rechner, Bestandsdaten) in einen abgenommenen Rechenkern. Das
einzige Interface zwischen den Stufen ist eine Ontologie:

* **T-Box** (`ontologie/tbox.py`): das Domaenenmodell — menschlich
  verantwortet, versioniert; Agenten aendern es nie autonom (Gate A-K1).
* **A-Box** (Instanzen eines Falls): von Agenten befuellt, von
  deterministischem Code gemergt und validiert; Single Source of Truth
  fuer alles Nachgelagerte. Kanonischer Speicher ist deterministisches
  JSON im Fall-Arbeitsbereich (ADR-002); ein Graph-Store waere eine
  jederzeit neu baubare Projektion.

Kein Agent einer spaeteren Stufe liest Rohquellen einer frueheren.

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
  Gate A-M4 (Mensch): P9-Snapshot — verlangt die Pflichtbelege je Gate
                  und Scope. Tarif: P-Q3/A-Q1/A-M1/P-K1. Bestand zusaetzlich:
                  P-B1, vollstaendige Zwei-Stichtags-Suite und gruener
                  Abnahmebericht; A-M4 revalidiert alles auf demselben
                  Eingangs-, A-Box-, System-, Bestands- und Stichtagsstand
```

## 3 Die tragenden Objekte

| Objekt | Traegt | Prinzip |
|---|---|---|
| `Aussage` | Wert, Zustand (belegt / nicht_belegt / mehrdeutig / widerspruechlich), Konfidenz, Provenienz je Beleg (Quelle+SHA-256, Fundstelle, Akteur, Zeit); unveraenderlich nach Konstruktion | P1, P3 |
| `Diskrepanz` | beide Lesarten mit Belegen; Aufloesung nur als expliziter Vorgang (Entscheider, Begruendung, ggf. `vorlaeufig`) | P2 |
| `Parametrierungszelle` | eine Merkmalskombination; Felder = exakt die Kern-ModelPoint-Stellschrauben; Zellen decken den Merkmalsraum EXAKT | P5, P6 |
| `TarifSpez` | Parametrierung des Rueckgrats + StrukturUrteil + Tafel-Importe/-Ableitungen + benannte Erweiterungsstellen; validierbar als Projektion der A-Box (beide Richtungen) | D2 (SDD, gebunden) |
| P9-Snapshot | Schema, Gate/Command/Version, Entscheid, Entscheider, Begruendung, SHA-256 aller Fall-Artefakte, Git-Stand und Vorgaenger; A-M1 und A-M4 pinnen zusaetzlich Scope und rollenbezogene Pflichtbelege je Gate; vollstaendig inhaltsadressiert, nie ueberschrieben; eine Annahme traegt eine HMAC-Freigabe aus einem extern verwahrten Schluessel | P9, P1 |

## 4 Deterministisch / LLM — die Trennlinie (P4)

LLM-Agenten tun genau eines: die Vorverdichtung EINER Quelle lesen und
ein Fragment vorschlagen (mit Fundstellen, Konfidenz, explizitem
"gesucht, nicht gefunden"). Alles andere ist Code: Merge, Konflikt,
Coverage, Struktur-Urteil, Projektion, Tafel-Ableitung, Vergleich,
Gates. Ein Widerspruch zwischen Quellen entsteht im Merge-Code, nie im
Agenten-Urteil; die Aufloesung ist ein Mensch.

## 5 Coverage statt Plausibilitaet (P6)

Gemessen wird gegen den PFLICHTUMFANG der T-Box, nicht gegen das
zufaellig Extrahierte. Drei unterscheidbare Fehl-Zustaende: `nicht_belegt`
(Agent hat gesucht), `fehlt_in_extraktion` (kein Agent hat das Feld auch
nur erwaehnt — der gefaehrliche stille Fall), `widerspruechlich`. Gate P-K1
weist zusaetzlich aus, was der GM NICHT deckt (Zellen ohne
Erwartungswerte, uebersprungene Erwartungsreste).

## 6 Der Praezedenzfall TG2012 -> TG2015

Die fachliche Vorgabe — "erkennen, dass der neue Rechner strukturell zum alten
passt, und integrieren statt duplizieren" — ist als BERECHNETES
StrukturUrteil umgesetzt: `parametrierung`, mit zwei neuen
Merkmalsdimensionen (Tarifart, Raucherstatus), neun geaenderten
Parametern und sechs Tafel-Anforderungen. Die Unisex-Vorgabe U70 wurde
zur abgeleiteten Mischtafel (`qx = min(1, 0.7*qx_M + 0.3*qx_F)`,
Double-Arithmetik VBA-treu) — NULL Kern-Formelaenderung, weil die exakte
Tafelnamens-Aufloesung des Kerns genau dafuer vorgesehen war. U70 ist
eine KALKULATIONS-Vorgabe (alle Vertraege werden unisex bewertet); das
Geschlecht bleibt Bestandsmerkmal ohne Tarifwirkung.
Nebenbefund der Pipeline: Meldung und Rechner widersprechen sich real
(Rechnungszins 1,25 % gegen 1,75 %; beta1 Haustarif 1,0 % gegen 0) —
als Diskrepanz-Objekte erfasst, vorlaeufig zur Rechner-Lesart geloest
(der GM reproduziert den Rechner), fachliche Entscheidung im Gate A-Q1.

## 7 Zusammenspiel mit der bestehenden Abnahme

Die O-Gates (P-Q3, P-K1) und P9-Snapshots stehen NEBEN der G0-G8-Kette und
teilen nur den Ledger-Mechanismus (`gates/_common`). Die G-Kette bleibt
der Abnahme-Weg des Sechs-Datei-Vergleichskerns; die Integration beider
Wege ist eine Team-Entscheidung nach Fall 1 (Fragerunde F2).

**Ueberholt seit ADR-006:** die G0-G8-Kette und der
Sechs-Datei-Vergleichskern sind ausser Betrieb — `gates.validate`,
`gates.security` und `gates.dossier` gibt es nicht mehr; erhalten
blieben nur `gates.extract` (P-Q1) und der Ledger-Mechanismus. Die
Frage der Integration beider Wege hat sich damit erledigt: es gibt nur
noch den O-/P9-Weg auf dem stabilen Zielkern.

## 8 Bewusst nicht in v0.1

* GM deckt die BEISPIEL-Zelle des Quell-Rechners (einzel/nichtraucher);
  die uebrigen fuenf Zellen brauchen weitere Erwartungswerte
  (zusaetzliche Modellpunkte vom Lieferanten oder COM-Neuberechnung) —
  Gate P-K1 weist das Komplement aus.
* Der deterministische Formel-Rueck-Check (quellen/formeln.py, in Gate
  P-Q3 eingebaut) deckt die IF-Staffeln; andere Formelformen prueft er
  fail-fast als "nicht pruefbar" — ein breiterer Formel-Parser bleibt
  offen.
* Kein Graph-Store, keine Embeddings, keine BU-/FLV-/Renten-Klassen in
  der T-Box (kommen mit ihren Faellen ueber A-K1), kein Legacy-Code-
  Vorverdichter, keine Bestandsdaten-Quelle in Stufe 1 (Quelltyp ist im
  Schema vorgesehen).
  UEBERHOLT, soweit es die Bestandsdaten betrifft: den Quelltyp
  Bestandsabzug/CSV gibt es inzwischen als eigenen Vorverdichter
  (`quellen/bestand_profil.py`), auf dem der Skill
  `transformiere-quellbestand` arbeitet.
* Fall-Artefakte (A-Box, Spez, Entscheide) liegen im gitignorierten
  Fall-Arbeitsbereich — die Versionierung echter Faelle ausserhalb des
  Repos ist ADR-002-Zielbild, in v0.1 nicht ausgebaut. Die
  Nachweiskette endet damit an einem Einzelplatz (Systempruefung 21):
  ein geteilter, versionierter Fall-Speicher ist Team-Entscheidung.
* Das Struktur-Urteil arbeitet INNERHALB einer menschlich vorgegebenen
  Produktfamilie: es kann Parametrierung von Erweiterung unterscheiden,
  aber 'neue Produktfamilie' nicht selbst feststellen — die T-Box
  kennt kein Leistungsversprechen/Zahlungsprofil (Systempruefung 5/29).
  Kommt mit Fall 2 (Risiko/Rente zwingen Zahlungsprofile in T-Box und
  Spez — die 'gebundene Spez' der D2-Entscheidung ist erst zur Haelfte
  gebaut: Zustandsraum, Zahlungsprofile, GeVo-Katalog fehlen).
* Gate P-K1 nimmt strukturell die RECHNER-Lesart ab (der GM reproduziert
  den Quell-Rechner). Entscheidet A-Q1 fachlich GEGEN den Rechner
  (z. B. Zins 1,25 % der Meldung), braucht die Abnahme korrigierte
  Erwartungswerte des Lieferanten — diesen Pfad gibt es noch nicht
  (Systempruefung 23).
* Die 1M-LOC-Mechanik ist seit ADR-005 gebaut: hierarchische Knoten
  (`familie[/generation]`, Wurzel validiert), Test-Knoten-Bindung
  (jede Testdatei, drift-geprueft), nachrechenbare Schichtenkarte
  (`ontologie.code_karte`, inkl. ADR-004-Zweitkern-Regel) und
  berechneter Aenderungs-Impact (`ontologie.impact`, Lineage-Selektion,
  konservativ bei jeder Unsicherheit). NOCH NICHT gebaut: Tafel-/
  Zellen-Granularitaet der Daten und die Verdrahtung als selektive
  Gates — CI und Vor-Commit fahren weiter die volle Suite
  (Systempruefung 6/13/28, Rest-Ausloeser Fall 2).
* P10 ist fuer Extraktions-Agenten instruiert (Skill), nicht technisch
  erzwungen (kein Sandbox-Zwang auf die Vorverdichtung).

### 8.1 Die A-Box traegt Parameter, keine Formeln — Formelidentitaet ist in v0.1 Menschensache

Das ist die wichtigste bewusste Grenze der Version, weil sie leicht mit
einem Versehen verwechselt wird. Sie ist keines.

**Was der Contract traegt.** Ein `QuellFragment` fuehrt je Zelle
`auspraegungen` und `parameter` — Zahlen und Zeichenketten, die in die
Stellschrauben des Kern-ModelPoints muenden. Ein Feld fuer FORMELN gibt
es nicht. Der Merge vergleicht folglich Parameterwerte: Rechnungszins
gegen Rechnungszins, Kostensatz gegen Kostensatz. Zwei Quellen, die
dieselbe Groesse nach VERSCHIEDENEN Formeln bestimmen, aber gleich
parametrisiert sind, erzeugen keine Diskrepanz — und was keine
Diskrepanz ist, kann kein Gate finden und kein Gate an A-Q1 vorlegen.

**Was daraus folgt.** Gate P-K1 belegt, dass der Kern denselben Wertepfad
liefert wie der Quell-Rechner (auf den Cent). Er belegt NICHT, dass die
Tarifmeldung dieselbe Formel meint. Weicht die Meldung vom Rechner in
der Formel ab, bleibt P-K1 gruen. Im Praezedenzfall TG2015 sind beim
menschlichen Lesen genau solche Stellen aufgefallen — Ziffer 3.2 leitet
die praemienfreie Leistung aus dem Rueckkaufswert (also nach
Stornoabschlag) ab, waehrend Rechner und Kern
`VS_bfr = kVx_MRV / kVx_bfr` rechnen; Ziffer 5.2.1 schreibt die
normierte Reservepraemie mit `B_{x,n}`, waehrend Ziffer 3.1 und der
Rechner mit `B_{x,t}` arbeiten. Gefunden hat das ein Mensch, nicht die
Pipeline. Solche Stellen gehoeren als benannte Abweichung in die
A-Q1-Vorlage, nicht in eine Fussnote.

**Warum bewusst so entschieden.** Ein Formelvergleich zwischen der
Meldung (OMML-Formeln in Word) und dem Rechner (Excel-Zellformeln) ist
kein Zeichenketten-Vergleich, sondern eine Aequivalenzfrage ueber zwei
verschiedene Sprachen mit verschiedenen Bezugsgroessen und
Indexkonventionen. Ein halber Vergleich waere schlimmer als keiner: er
produziert entweder Falsch-Alarme oder — gefaehrlicher — gruene Balken
fuer eine Identitaet, die er nie geprueft hat. v0.1 nimmt deshalb die
PARAMETRIERUNG maschinell ab und weist die Formelidentitaet
ausdruecklich dem Menschen zu: Abnahme gegen den Tarifplan
(`docs/tarifplaene/`) im Gate A-Q1. Der vorhandene deterministische
Rueck-Check (`quellen/formeln.py`, in Gate P-Q3) ist die einzige
Ausnahme und beschreibt seinen Umfang selbst ehrlich: er prueft die
IF-Staffeln des Rechners gegen die extrahierten Werte und meldet jede
andere Formelform als "nicht pruefbar" — er vergleicht also innerhalb
EINER Quelle, nicht zwischen zweien.

**Ausbaupfad (nicht in v0.1).** Feld `formeln` im QuellFragment
(Zeichenkette plus Fundstelle je Ziffer), dazu ein Gate, das die
extrahierten Formeln je Ziffer gegen die Paragrafen des Tarifplans
stellt. Das aendert den Contract und ist damit eine T-Box-Frage
(Gate A-K1). Ausloeser: der erste Fall, in dem der Quell-Rechner NICHT
die abzunehmende Lesart ist — etwa eine Lieferung ohne Rechner oder
eine A-Q1-Entscheidung gegen den Rechner.

## 9 Wissensverteilung: wo das Migrations-Know-how lebt

Das System wird nicht "trainiert" — sein Wissen ist verteilt auf vier
Schichten, jede versioniert, jede mit eigener Aenderungs-Disziplin:

| Schicht | Traegt | Ort | Aendert sich durch |
|---|---|---|---|
| Deterministischer Code | das Verfahren selbst: Vorverdichtung, Merge, Konfliktbildung, Coverage, Struktur-Urteil, Projektion, Tafel-Ableitung, Vergleich, Gates | `quellen/`, `ontologie/`, `spez/`, `gates/` | Commits unter Test-Pflicht |
| Contracts & T-Box | WAS zu extrahieren ist (QuellFragment-Schema, generiert), was Pflicht ist (PFLICHT_PARAMETER), wohin es mappt (ModelPoint-Felder) | `ontologie/tbox.py`, `ontologie/befuellung.py` | Gate A-K1 (T-Box-Aenderung, Mensch) |
| Skills (Agenten-Anweisungen) | WIE die probabilistischen Schritte urteilen: Extraktionsregeln je Quelltyp, das systematische Vorgehen eines Falls, Abbruchkriterien | `.claude/skills/` + `.agents/skills/` (Paritaet test-tragend): `migrationsfall-durchfuehren` (Runbook), `extrahiere-quellfragment` (Stage-1-Agent) | Commits; der Skill-Stand (Git-SHA) gehoert in den Akteur-String der Provenienz (P1) |
| Praezedenzfall | WIE ein fertiges Ergebnis aussieht: A-Box, Spez, Fachspez, Diskrepanzen, Gate-Ledger des Falls KLV TG2012->TG2015 | `faelle/baldrian-klv-tg2015` (lokal; echte Faelle ausserhalb des Repos) | jeder abgeschlossene Fall wird Referenz des naechsten |

UEBERHOLT ist die Skill-Zeile in ihrem Umfang: aus den zwei genannten
Skills sind inzwischen zehn geworden (Extraktion, Runbook, Transformation
des Quellbestands, Konfliktaufbereitung, Migrationsabnahme, Entwicklung
im Zielsystem, Gate-Autorenschaft, Inkrement-Integration, Doku,
adversariales Testen). Verbindlicher Katalog mit Rollen und Grenzen:
[skill-architektur.md](skill-architektur.md).

Die Verteilungsregel dahinter: Wissen, das GELTEN muss, wandert in Code
und Contracts (erzwungen); Wissen, das URTEILEN anleitet, in Skills
(versioniert, in der Provenienz zitiert); Wissen, das ZEIGT, in den
Praezedenzfall. Fachliche Zuordnung der von einer Migration verlangten
Faehigkeiten: Quelldatenverarbeitung = Vorverdichter + Extraktions-Skill
+ Formel-Rueck-Check; Konsistenzchecks = Merge/Diskrepanzen + Gates
P-Q3/P-K1 + Kreuzproben des Tafel-Imports; Transformation/Mapping = T-Box
(Feldnamen SIND das Mapping) + quellnamen-Erfassung + Spez-Projektion;
Coding = fuer Parametrierungs-Faelle NICHT vorgesehen (Erweiterungs-
stellen waeren der benannte Ort, mit eigenem Skill, sobald ein Fall sie
braucht); Testing/Abnahme = Gate-Kette + Suite + menschliche Gates.

## 10 Verweise

ADR-001 (Repo-Zielstruktur), ADR-002 (Fall-Arbeitsbereich), ADR-003
(Pydantic fuer die Ontologie-Schicht), ADR-004 (Thiele-Kern ohne
Excel-Referenzwerte; Kommutation als separater Zweitkern), ADR-005
(Knoten-Hierarchie, Test-Bindung, Code-Karte, Impact). Hinzugekommen
seit Redaktionsschluss dieses Dokuments — und fuer den heutigen Stand
massgeblich: ADR-006 (Portierungs-Anwendungsfall ausser Betrieb; die
G-Kette entfaellt), ADR-007 (parallele Migrationen in einem Kern;
knotengebundene Inkremente auf einem Trunk), ADR-008 (signierte
P9-Freigaben) und ADR-009 (Fall-Scope und Bestands-Pflichtbelege).
Entscheidungsgrundlage: die
Architektur-Fragerunde (D1-D4, F1-F3; privat dokumentiert, Ergebnisse
in diesen ADRs).
