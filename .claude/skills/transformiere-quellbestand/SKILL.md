---
name: transformiere-quellbestand
description: >-
  Map a delivered portfolio extract (Bestandsabzug) from the source insurer's
  data model into the target ontology: propose a TransformationsSpec (field
  mappings, encodings, derived calculations from a fixed catalog) that
  deterministic code then validates and applies. After a documented human
  mapping decision it also covers the explicitly authorized transfer of that
  decision (with fundstelle) into the existing spec and the human spec
  cross-check — never an automatic transfer, never a claimed signature
  security. A transfer without a documented human decision and human
  cross-check is a STOPP. Trigger when a migration case receives a
  Bestandsabzug whose field names/formats differ from the target model, or
  when the user asks to "den Quellbestand transformieren/mappen". Skip for:
  applying the mapping (deterministic code), deciding open mapping conflicts
  (human, A-Q1), tariff parameter extraction (use extrahiere-quellfragment).

---

# Quellbestand in die Ziel-Ontologie transformieren

## Rolle und Ziel

Du bist der SEMANTISCHE Teil der Datentransformation — die grosse
Migrationsaufgabe VOR der Migration. Ein abgebendes Unternehmen liefert
seinen Bestandsabzug in SEINEM Datenmodell (eigene Feldnamen,
Kodierungen, Formate). Du erkennst, was gemeint ist ("ERLSUMME" ist
unsere Versicherungssumme, "GESCHL" mit M/W ist sex mit M/F), und
schlaegst das vollstaendige Mapping als `TransformationsSpec` vor
(Schema: `ontologie/transformation.py`).

Nicht verhandelbar:

- Fachliche Quelldaten liest du NUR aus der deterministischen
  Vorverdichtung (Spaltenprofil aus `quellen/bestand_profil`), nie aus
  der Rohdatei (P10). Erlaubte Verfahrens-/Schemaunterlagen sind davon
  getrennt. Fuer den ausdruecklich autorisierten Uebertragungsschritt
  darfst du zusaetzlich die im Auftrag benannte dokumentierte menschliche
  Entscheidung samt Fundstelle und die aktuelle Spec lesen. Keine
  fremden Faelle oder Ergebnisse anderer Extraktionen; eine Entscheidung
  erweitert nicht stillschweigend den zugelassenen Quellenumfang.
- Du ERFINDEST nichts: jedes Feld-Mapping traegt eine Begruendung;
  Berechnungen kommen ausschliesslich aus dem Katalog
  (`BERECHNUNGEN` in `ontologie/transformation.py`) — du WAEHLST,
  Code RECHNET (P4).
- Unklarheit ist ein `OffenerKonflikt`, keine Annahme: eine Spalte,
  deren Bedeutung du nicht belegen kannst (undokumentierte Kennzeichen,
  mehrdeutige Betragsfelder), bekommt eine praezise FRAGE an den
  Menschen und blockiert die Anwendung, bis er entschieden hat (P2).
- Fehlt der Ziel-Ontologie ein Feld, das die Quelle traegt und das
  fachlich uebernommen werden muesste: STOPP — Ontologie-Erweiterung
  ist Gate A-O1, nie deine Entscheidung.
- Akteur-Konvention in der Spec: `<modell>/<skill>@<git-sha-kurz>`.

## Ablauf

1. Vorverdichtung lesen: Spaltenprofil (Name, Typ-Heuristik,
   Beispielwerte, Kardinalitaet, Leeranteile).
2. Je Quellspalte GENAU EINE Entscheidung: `direkt` | `kodierung`
   (vollstaendige Wertetabelle!) | `berechnung` (Katalogname +
   Quellspalten) | `nicht_uebernommen` (mit Grund) | OffenerKonflikt.
3. Ziel-Pflichtfelder gegenpruefen (`ZIEL_PFLICHT`): jedes muss gedeckt
   sein — was du nicht decken kannst, ist ein offener Konflikt, kein
   stilles Loch.
4. Spec als JSON ablegen (Fall-Artefakt:
   `<fall>/abgeleitet/transformation/<quelle>.spec.json`), dann die
   deterministische Pruefung melden lassen:
   `ontologie.transformation.validate_spec` muss leer sein, sonst
   nachbessern oder eskalieren.

## Menschliche Konfliktentscheidung in die Spec uebertragen

Ein offener Konflikt wird mit betroffenen Mappingregeln an den Menschen
bei A-Q1 uebergeben. Nach seiner dokumentierten Entscheidung uebertraegt
die ausdruecklich autorisierte Bearbeitung die festgelegte Lesart in die
Mappingregeln sowie `entscheidung` und `entscheider` des Konflikts.
Du entscheidest den Konflikt nicht selbst: deine eigene Lesart ist keine
Entscheidung und wird nicht uebertragen. Nur die im Auftrag benannte
dokumentierte menschliche Entscheidung samt Fundstelle ist die Grundlage
des Transfers.
Der Mensch prueft die Uebereinstimmung von Entscheidung und geaenderter
Spec. Halte Entscheidungsfundstelle, betroffene Regeln und geprueften
Spec-Stand im abgeleiteten Uebergabevermerk fest; nichts in `entscheide/`
von Hand aendern. Ohne Entscheidung oder menschlichen Abgleich: STOPP.

Danach Spec erneut deterministisch validieren und anwenden; betroffene
Bestands-/Pruef-/Abnahmebelege auf dem neuen Stand neu erzeugen und
erforderliche menschliche Neuzeichnungen vorlegen. Transformationsergebnis
und A-M4 binden die aktuelle Spec per Hash. A-Q1 zeichnet den A-Box-Stand;
der bestehende Code uebertraegt die Entscheidung nicht automatisch und
prueft keine Signatur auf den Spec-Entscheidungsfeldern. Ein nichtleerer
`entscheider` ist kein Signaturnachweis. Dieses Verfahren ist menschlich
verantworteter Abgleich, keine neue technische Gate-Erzwingung.

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Ziel-Pflichtfeld ist aus der Quelle nicht ableitbar.
- Zwei Quellspalten kaemen fuer dasselbe Zielfeld infrage.
- Eine Kodierung waere unvollstaendig (beobachteter Wert ohne Bedeutung).
- Die Quelle verlangt eine Berechnung, die der Katalog nicht kennt.
