# ADR-009: Fall-Scope und deklarativer Gate-DAG fuer G-2

Status: Angenommen  
Datum: 2026-08-20  
Entscheider: Auftraggeber durch ToDo 10.3

## Kontext

G-2 verlangte bisher fuer jeden Fall O1, G-1 und die exakte Menge gruener
O3-Belege. Ob ein Fall zugleich einen Bestand uebernimmt, war nicht
maschinenlesbar deklariert. Deshalb konnte ein Bestandsfall ohne B1,
Migrationssuite, Transformationsnachweis und Abnahmebericht angenommen
werden. Ein pauschaler Dateiname-Check waere die falsche Reparatur: Ein reiner
Tariffall hat diese Artefakte fachlich nicht und darf sie nicht kuenstlich
erzeugen muessen.

Die Bestandsartefakte haben ausserdem unterschiedliche Erzeuger. Eine blosse
Existenzpruefung belegt weder ihren Zusammenhang noch, dass sie denselben
Eingangs-, A-Box-, Code- und Stichtagsstand beschreiben.

## Entscheidung

1. Jeder neu angelegte Fall deklariert in `fall.json` einen Scope mit
   Schema-Version, Typ `tarif` oder `bestand` und der verwendeten
   Gate-DAG-Version. Ein Altfall ohne Scope wird bei G-2 nicht geraten und
   blockiert bis zur bewussten Migration seines Manifests.
2. `rechner_pipeline.fall.GATE_DAG` ist die zentrale maschinenlesbare Quelle
   fuer Knoten, Kanten, Scope-Zuordnung und stabile Belegrollen. G-2
   traversiert den DAG rueckwaerts und leitet seine Pflichtrollen daraus ab.
   Eine zweite Bestands-Pflichtliste im Gate gibt es nicht.
3. Der Scope `tarif` verlangt O1-Ledger, geltenden signierten G-1-Snapshot und
   die exakte O3-Belegmenge der A-Box. Bestandsartefakte sind weder Pflicht
   noch werden zufaellig vorhandene Dateien zu einer Scope-Aenderung.
4. Der Scope `bestand` verlangt zusaetzlich eine semantisch validierte
   Transformationsspec, ein an Quelle, Spec und Ziel gebundenes
   Transformationsergebnis, ein gruenes B1-Ledger fuer genau dieses Ziel,
   eine vollstaendig gepruefte Migrationssuite fuer genau dieses Ziel und die
   beiden Stichtage, Vor- und Nachbericht sowie den HTML-Abnahmebericht.
5. `gates.abnahmebericht` validiert diese Bestandskette und schreibt nur auf
   dem gruenen Pfad einen unveraenderlichen, inhaltsadressierten Scope-Beleg.
   Er bindet jede DAG-Rolle durch Fall-relativen Pfad und SHA-256 gemeinsam an
   Eingangsregister, A-Box, Systemstand, DAG-Version und beide Stichtage.
6. G-2 validiert Schema, Gate, Command, Version, Status, Eigenhash und
   Dateinamen aller Scope-Belege neu. Fuer den aktuellen gemeinsamen Stand
   muss genau ein Beleg existieren; jeder gebundene Artefakthash wird gegen
   die aktuellen Bytes nachgerechnet. P9-Snapshot-Schema v3 pinnt Scope,
   DAG-Version und die exakte rollenbezogene Pflichtbelegmenge.

## Konsequenzen

- Ein Bestandsfall kann nicht mehr vor B1, vollstaendiger Suite,
  Transformation und Berichten zu G-2 gelangen. Das Entfernen oder Aendern
  eines gebundenen Artefakts blockiert die Annahme.
- Ein Tariffall bleibt schlank. Sein positiver G-2-Pfad benoetigt keinerlei
  kuenstliche Parquet-, Transformations- oder Berichtsdatei.
- `fall anlegen` verwendet fuer Rueckwaertskompatibilitaet den explizit im
  erzeugten Manifest gespeicherten Default `--scope tarif`. Bestandsfaelle
  werden mit `--scope bestand` angelegt.
- Bestehende P9-v2-Snapshots tragen noch keine Scope-/DAG-Bindung und sind
  deshalb keine Belege fuer den v3-Vertrag. Offene Faelle werden nach
  revisionsfester Archivierung der alten Kette auf dem deklarierten Scope neu
  entschieden; es gibt keine stille Umdeutung.
- Der Scope-Beleg ist unveraenderlich, das allgemeine Latest-Ledger aber noch
  nicht. Atomare, attempt-spezifische Ledger und sichere Latest-Verweise
  bleiben Gegenstand von ToDo 10.12.

## Bewusst nicht Bestandteil dieser Entscheidung

- Ob Transformationsbefunde, Zeilenverlust oder andere Pruefluecken einen
  differenzierten Abnahmeberichtstatus ergeben, wird in ToDo 10.5 behandelt.
  Diese Entscheidung stellt sicher, dass die Artefakte vorhanden, validiert
  und auf denselben Stand gebunden sind.
- Die atomare Neuberechnung aller Suite-Einzelurteile ist ToDo 10.4. Der
  Scope-Vertrag ersetzt diesen fachlichen Innenvertrag nicht.
- Der DAG orchestriert keine Agenten und startet keine Kommandos. Er
  beschreibt Abhaengigkeiten und Belegpflichten; Menschen entscheiden G-1
  und G-2 weiterhin selbst.

## Verworfene Alternativen

- B1 und Abnahmebericht fuer jeden Fall verlangen: verworfen, weil ein reiner
  Tariffall dadurch inhaltslose Bestandsartefakte erzeugen muesste.
- Den Scope aus vorhandenen CSV-/Parquet-Dateien erraten: verworfen, weil
  Dateiexistenz kein fachlicher Entscheid ist und durch Loeschen die
  Gate-Pflicht abschaltbar waere.
- Nur die Dateinamen im G-2-Code pruefen: verworfen, weil damit weder
  Produzentenvertrag noch gemeinsamer Stand nachgerechnet werden und die
  Pflichtmenge an mehreren Stellen driften wuerde.
