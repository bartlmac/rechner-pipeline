---
name: transformiere-quellbestand
description: >-
  Map a delivered portfolio extract (Bestandsabzug) from the source insurer's
  data model into the target ontology: propose a TransformationsSpec (field
  mappings, encodings, derived calculations from a fixed catalog) that
  deterministic code then validates and applies. Trigger when a migration case
  receives a Bestandsabzug whose field names/formats differ from the target
  model, or when the user asks to "den Quellbestand transformieren/mappen".
  Skip for: applying the mapping (deterministic code), resolving open mapping
  conflicts (human), tariff parameter extraction (use extrahiere-quellfragment).

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

- Du liest NUR die deterministische Vorverdichtung (das Spaltenprofil
  aus `quellen/bestand_profil`), nie die Rohdatei (P10).
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
  ist Gate G-T, nie deine Entscheidung.
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

## Abbruchkriterien (STOPP und Mensch fragen)

- Ein Ziel-Pflichtfeld ist aus der Quelle nicht ableitbar.
- Zwei Quellspalten kaemen fuer dasselbe Zielfeld infrage.
- Eine Kodierung waere unvollstaendig (beobachteter Wert ohne Bedeutung).
- Die Quelle verlangt eine Berechnung, die der Katalog nicht kennt.
