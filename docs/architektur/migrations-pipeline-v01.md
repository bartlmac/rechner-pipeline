# Migrations-Pipeline v0.1: Ontologie als Stage-Interface

Stand: 2026-08-15. Am Migrationsfall KLV TG2012 -> TG2015 MECHANISCH
abgenommen (Gate O3: 616 Werte gegen den Quell-Rechner, 0 Abweichungen);
die MENSCHLICHEN Gates G-1/G-2 des Falls stehen aus (8 vorlaeufige
Diskrepanz-Aufloesungen warten auf die fachliche Entscheidung). Dieses
Dokument beschreibt Architektur UND Ist-Stand — was v0.1 bewusst nicht
kann, steht in Abschnitt 8. Die Prinzipien in Vollform: prinzipien.md.

## 1 Idee

Eine Bestandsmigration uebersetzt heterogene Quellen (Tarifmeldungen,
Quell-Rechner, Bestandsdaten) in einen abgenommenen Rechenkern. Das
einzige Interface zwischen den Stufen ist eine Ontologie:

* **T-Box** (`ontologie/tbox.py`): das Domaenenmodell — menschlich
  verantwortet, versioniert; Agenten aendern es nie autonom (Gate G-T).
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
  Gate O1 (abox_validate): Contract + Register-Verankerung + Coverage +
                  offene Diskrepanzen blockieren

Stufe 2  A-Box -> Spez -> Kern-Parametrierung
  deterministisch: spez/erzeugen — Projektion mit hartem Vorbedingungs-Check;
                  StrukturUrteil BERECHNET (Parametrierung vs. neues Produkt);
                  spez/fachspez — das menschenlesbare G-1-Dokument (P7)
  deterministisch: quellen/tafel_import — Tafeln + Ableitungen (Unisex-
                  Mischtafel als DATEN-Regel, VBA-bit-treu) nach kern/tafeln.xml
  Gate G-1 (Mensch): Fachspez + Diskrepanzen + Coverage; Werkzeuge:
                  ontologie/entscheide (Aufloesung), gates/gate_entscheid (P9)

Stufe 3  Abnahme
  Gate O3 (generation_golden): Kern (Spez-parametriert) gegen die aus dem
                  Quell-Rechner extrahierten Erwartungswerte; prueft vorab,
                  dass die Spez gueltige Projektion der A-Box ist
  Gate G-2 (Mensch): P9-Snapshot — verweigert Annahme, solange vorlaeufige
                  Diskrepanz-Aufloesungen existieren
```

## 3 Die tragenden Objekte

| Objekt | Traegt | Prinzip |
|---|---|---|
| `Aussage` | Wert, Zustand (belegt / nicht_belegt / mehrdeutig / widerspruechlich), Konfidenz, Provenienz je Beleg (Quelle+SHA-256, Fundstelle, Akteur, Zeit); unveraenderlich nach Konstruktion | P1, P3 |
| `Diskrepanz` | beide Lesarten mit Belegen; Aufloesung nur als expliziter Vorgang (Entscheider, Begruendung, ggf. `vorlaeufig`) | P2 |
| `Parametrierungszelle` | eine Merkmalskombination; Felder = exakt die Kern-ModelPoint-Stellschrauben; Zellen decken den Merkmalsraum EXAKT | P5, P6 |
| `TarifSpez` | Parametrierung des Rueckgrats + StrukturUrteil + Tafel-Importe/-Ableitungen + benannte Erweiterungsstellen; validierbar als Projektion der A-Box (beide Richtungen) | D2 (SDD, gebunden) |
| P9-Snapshot | Entscheid, Entscheider, Begruendung, SHA-256 aller Fall-Artefakte, Git-Stand des Systems; inhaltsadressiert, nie ueberschrieben | P9, P1 |

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
nur erwaehnt — der gefaehrliche stille Fall), `widerspruechlich`. Gate O3
weist zusaetzlich aus, was der GM NICHT deckt (Zellen ohne
Erwartungswerte, uebersprungene Erwartungsreste).

## 6 Der Praezedenzfall TG2012 -> TG2015

Dirks Vorgabe — "erkennen, dass der neue Rechner strukturell zum alten
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
(der GM reproduziert den Rechner), fachliche Entscheidung im Gate G-1.

## 7 Zusammenspiel mit der bestehenden Abnahme

Die O-Gates (O1, O3) und P9-Snapshots stehen NEBEN der G0-G8-Kette und
teilen nur den Ledger-Mechanismus (`gates/_common`). Die G-Kette bleibt
der Abnahme-Weg des Sechs-Datei-Vergleichskerns; die Integration beider
Wege ist eine Team-Entscheidung nach Fall 1 (Fragerunde F2).

## 8 Bewusst nicht in v0.1

* GM deckt die BEISPIEL-Zelle des Quell-Rechners (einzel/nichtraucher);
  die uebrigen fuenf Zellen brauchen weitere Erwartungswerte
  (zusaetzliche Modellpunkte vom Lieferanten oder COM-Neuberechnung) —
  Gate O3 weist das Komplement aus.
* Der deterministische Formel-Rueck-Check (quellen/formeln.py, in Gate
  O1 verankert) deckt die IF-Staffeln; andere Formelformen prueft er
  fail-fast als "nicht pruefbar" — ein breiterer Formel-Parser bleibt
  offen.
* Kein Graph-Store, keine Embeddings, keine BU-/FLV-/Renten-Klassen in
  der T-Box (kommen mit ihren Faellen ueber G-T), kein Legacy-Code-
  Vorverdichter, keine Bestandsdaten-Quelle in Stufe 1 (Quelltyp ist im
  Schema vorgesehen).
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
* Gate O3 nimmt strukturell die RECHNER-Lesart ab (der GM reproduziert
  den Quell-Rechner). Entscheidet G-1 fachlich GEGEN den Rechner
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

## 9 Wissensverteilung: wo das Migrations-Know-how lebt

Das System wird nicht "trainiert" — sein Wissen ist verteilt auf vier
Schichten, jede versioniert, jede mit eigener Aenderungs-Disziplin:

| Schicht | Traegt | Ort | Aendert sich durch |
|---|---|---|---|
| Deterministischer Code | das Verfahren selbst: Vorverdichtung, Merge, Konfliktbildung, Coverage, Struktur-Urteil, Projektion, Tafel-Ableitung, Vergleich, Gates | `quellen/`, `ontologie/`, `spez/`, `gates/` | Commits unter Test-Pflicht |
| Contracts & T-Box | WAS zu extrahieren ist (QuellFragment-Schema, generiert), was Pflicht ist (PFLICHT_PARAMETER), wohin es mappt (ModelPoint-Felder) | `ontologie/tbox.py`, `ontologie/befuellung.py` | Gate G-T (T-Box-Aenderung, Mensch) |
| Skills (Agenten-Anweisungen) | WIE die probabilistischen Schritte urteilen: Extraktionsregeln je Quelltyp, das systematische Vorgehen eines Falls, Abbruchkriterien | `.claude/skills/` + `.agents/skills/` (Paritaet test-tragend): `migrationsfall-durchfuehren` (Runbook), `extrahiere-quellfragment` (Stage-1-Agent) | Commits; der Skill-Stand (Git-SHA) gehoert in den Akteur-String der Provenienz (P1) |
| Praezedenzfall | WIE ein fertiges Ergebnis aussieht: A-Box, Spez, Fachspez, Diskrepanzen, Gate-Ledger des Falls KLV TG2012->TG2015 | `faelle/baldrian-klv-tg2015` (lokal; echte Faelle ausserhalb des Repos) | jeder abgeschlossene Fall wird Referenz des naechsten |

Die Verteilungsregel dahinter: Wissen, das GELTEN muss, wandert in Code
und Contracts (erzwungen); Wissen, das URTEILEN anleitet, in Skills
(versioniert, in der Provenienz zitiert); Wissen, das ZEIGT, in den
Praezedenzfall. Fachliche Zuordnung der von einer Migration verlangten
Faehigkeiten: Quelldatenverarbeitung = Vorverdichter + Extraktions-Skill
+ Formel-Rueck-Check; Konsistenzchecks = Merge/Diskrepanzen + Gates
O1/O3 + Kreuzproben des Tafel-Imports; Transformation/Mapping = T-Box
(Feldnamen SIND das Mapping) + quellnamen-Erfassung + Spez-Projektion;
Coding = fuer Parametrierungs-Faelle NICHT vorgesehen (Erweiterungs-
stellen waeren der benannte Ort, mit eigenem Skill, sobald ein Fall sie
braucht); Testing/Abnahme = Gate-Kette + Suite + menschliche Gates.

## 10 Verweise

ADR-001 (Repo-Zielstruktur), ADR-002 (Fall-Arbeitsbereich), ADR-003
(Pydantic fuer die Ontologie-Schicht), ADR-004 (Thiele-Kern ohne
Excel-Anker; Kommutation als separater Zweitkern), ADR-005
(Knoten-Hierarchie, Test-Bindung, Code-Karte, Impact). Entscheidungsgrundlage: die
Architektur-Fragerunde (D1-D4, F1-F3; privat dokumentiert, Ergebnisse
in diesen ADRs).
