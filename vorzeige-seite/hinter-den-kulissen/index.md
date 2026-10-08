# Hinter den Kulissen

Diese Seite spricht nicht mit der Stimme des Unternehmens. Die
Pfefferminzia Lebensversicherung AG ist frei erfunden; der Name ist der
des klassischen Lehrbuch-Versicherers der deutschen Assekuranz. Die
Seiten davor zeigen, wie eine agentische Bestandsmigration abläuft — an
einem Unternehmen, das sich selbst für real hält.

## Was erfunden ist

* Alle Gesellschaften, alle Verträge, alle Personen. Die Bestände sind
  synthetisch erzeugt und werden von einem simulierten Tagesbetrieb
  fortgeschrieben.
* Die aktuariellen Abnahmen tragen den Fingerabdruck eines
  **Simulationsschlüssels**, nicht den eines Verantwortlichen Aktuars.
  Die Seiten prüfen an den Entscheid-Snapshots Schema, Selbstadressierung
  und Dateinamen; die Signatur selbst verifizieren sie nicht.
* Die Kennzahlen der Seiten werden beim Bau aus den Prüfartefakten der
  Migrationsfälle und dem Stands-Paket des Tagesbetriebs erzeugt, nicht
  gepflegt. Was noch keine Quelle hat, steht als Platzhalter da.

## Wie die Bestände und der Betrieb entstehen

* [Wie die Bestände entstehen](simulation/) — die Erzeugung der
  Vorzeigebestände.
* [Erfahrungsannahmen der Bestandssimulation](simulation/erfahrungsannahmen.html).
* [Fachkonzept: die PLV als laufendes Unternehmen](simulation/tagesbetrieb.html) —
  täglicher Bestandsbetrieb, Zeitmodell, Neugeschäft, Laufzeitumgebung.

## Das System

Das erzeugende System ist quelloffen:
[bartlmac/rechner-pipeline](https://github.com/bartlmac/rechner-pipeline).
Seine Architektur, wie das Repository sie dokumentiert:

* [Architekturentscheide](architektur/) — jede Festlegung mit Anlass,
  Alternativen und Folgen.
* [Prinzipien](architektur/prinzipien.html) — was für jede Änderung gilt.
* [Landkarte](architektur/landkarte.html) — die Schichtung des Codes,
  erzeugt aus dem Code selbst.
* [Migrations-Pipeline](architektur/migrations-pipeline-v01.html) — die
  Stufen einer Übernahme, die Ontologie als Schnittstelle, die Gates je
  Stufe.
