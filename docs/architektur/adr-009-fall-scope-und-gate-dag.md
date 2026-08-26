# ADR-009: Fall-Scope und Bestands-Pflichtbelege fuer G-2

Status: Angenommen  
Datum: 2026-08-20  
Entscheider: Auftraggeber durch ToDo 10.3 und Praezisierung in ToDo 6.2

## Kontext

G-2 verlangte bisher fuer jeden Fall O1, G-1 und die exakte Menge gruener
O3-Belege. Ob ein Fall zugleich einen Bestand uebernimmt, war nicht
maschinenlesbar deklariert. Deshalb konnte ein Bestandsfall ohne B1,
vollstaendig gepruefte Migrationssuite und Abnahmebericht angenommen werden.
Ein pauschaler Dateiname-Check waere die falsche Reparatur: Ein reiner
Tariffall hat diese Artefakte fachlich nicht und darf sie nicht kuenstlich
erzeugen muessen.

Die drei Bestandsbelege haben unterschiedliche Erzeuger. Eine blosse
Existenzpruefung belegt weder ihren Zusammenhang noch, dass sie denselben
Eingangs-, A-Box-, Code-, Bestands- und Stichtagsstand beschreiben.

## Entscheidung

1. Jeder neu angelegte Fall deklariert in `fall.json` einen Scope mit
   Schema-Version und Typ `tarif` oder `bestand`. Ein Altfall ohne Scope wird
   bei G-2 nicht geraten und blockiert bis zur bewussten Migration seines
   Manifests.
2. Der Scope `tarif` verlangt O1-Ledger, geltenden signierten G-1-Snapshot und
   die exakte O3-Belegmenge der A-Box. Bestandsartefakte sind weder Pflicht
   noch wird aus zufaellig vorhandenen Dateien ein anderer Scope abgeleitet.
3. Der Scope `bestand` verlangt zusaetzlich ein gruenes B1-Ledger, eine
   vollstaendig gepruefte Migrationssuite und einen gruen erzeugten
   HTML-Abnahmebericht.
4. B1 und Suite muessen denselben aktuell vorhandenen Bestand per SHA-256
   binden. B1 muss ausserdem den aktuellen Systemstand tragen; die Suite muss
   genau die beiden chronologischen Berichtsstichtage binden.
5. `gates.abnahmebericht` erzeugt ein gruenes Ledger nur mit
   Transformationsspecifikation, Transformationsergebnis und zwei vorhandenen,
   verschiedenen Vor-/Nachberichten. Alle Eingabe-, die HTML-Ausgabe- und die
   Gate-Ledger-Rolle muessen paarweise verschiedene Dateien bezeichnen;
   kanonische Pfad- und Hardlink-Aliase blockieren vor dem Rendern.
   Pruefluecken, nicht kongruente
   Transformationszeilenzahlen, Transformationsbefunde und nicht entschiedene
   Konflikte blockieren den Bericht. Im Bestands-Scope bindet das gruene Ledger
   B1-Ledger, Suite und HTML-Bericht durch Fall-relativen Pfad und SHA-256
   gemeinsam an Eingangsregister, A-Box, Systemstand und beide Stichtage. Eine
   zweite, exakt vierteilige Rollenabbildung bindet Spec,
   Transformationsergebnis sowie Vor- und Nachbericht jeweils an sicheren
   Fallpfad und SHA-256; die Pfadschluessel in `input_hashes` ersetzen diese
   Rollen nicht.
6. G-2 vertraut diesem frei editierbaren Ledger nicht blind. Es prueft dessen
   Gate-Vertrag, hasht alle drei Artefakte und den von B1 benannten aktuellen
   Portfolio-Eingang neu und fuehrt die produktiven B1-Engines auf den
   strukturiert persistierten Eingangsrollen und Optionen erneut aus. Die
   Suite wird semantisch erneut validiert; B1-Portfoliozeilen und
   vollstaendige Suite-Pruefmenge muessen exakt uebereinstimmen. Schliesslich
   liest G-2 die vier Renderer-Artefakte aus ihren Rollen neu, gleicht Spec und
   Transformationsergebnis typ- und wertgenau mit dem kanonischen
   Renderer-Vertrag ab, leitet Zeilenzahlen, Befunde und Konflikte aus den
   gebundenen Inhalten neu ab und verlangt beim neu gerenderten HTML
   Bytegleichheit. P9-Snapshot-Schema v4 pinnt Scope und die exakte
   rollenbezogene Pflichtbelegmenge.

## Konsequenzen

- Ein Bestandsfall kann nicht mehr ohne B1, vollstaendige Suite und
  Abnahmebericht zu G-2 gelangen. Das Entfernen oder Aendern eines dieser
  Belege blockiert die Annahme.
- Eine fuer sich gruene Suite reicht nicht fuer einen gruenen Abnahmebericht:
  fehlende Pflichtartefakte, Pruefluecken, Zeilenverlust,
  Transformationsbefunde oder nicht entschiedene Konflikte werden als
  `abnahmehindernisse` im Ledger und als roter Kopfsatz im HTML sichtbar.
  Eine Datei kann nicht durch Pfad- oder Hardlink-Aliase mehrere Pflichtrollen
  ersetzen oder durch Renderer beziehungsweise Ledger ueberschrieben werden.
- Ein Tariffall bleibt schlank. Sein positiver G-2-Pfad benoetigt keinerlei
  kuenstliche Parquet- oder Berichtsdatei.
- `fall anlegen` verwendet fuer Rueckwaertskompatibilitaet den explizit im
  erzeugten Manifest gespeicherten Default `--scope tarif`. Bestandsfaelle
  werden mit `--scope bestand` angelegt.
- Bestehende P9-v2/v3-Snapshots tragen noch nicht den aktuellen
  Scope-Vertrag und sind deshalb keine Belege fuer den v4-Vertrag. Offene
  Faelle werden nach revisionsfester
  Archivierung der alten Kette auf dem deklarierten Scope neu entschieden; es
  gibt keine stille Umdeutung.
- Das Abnahme-Ledger ist noch ein ueberschriebenes Latest-Ledger. G-2 begegnet
  seiner fehlenden Authentisierung durch vollstaendige Revalidierung; eine
  unveraenderliche Versuchshistorie gibt es weiterhin nur fuer gruene
  O3-Belege.

  *(Nachtrag 2026-08-24: ToDo 10.12 ist im selben Stand umgesetzt und nicht
  mehr offen — jeder Gate-Lauf ersetzt den alten Beleg vor der Facharbeit
  durch einen roten Startbeleg und publiziert den Abschluss atomar
  (`gates._common.begin_gate_ledger_attempt` / `finalize_gate_ledger`). Was
  bleibt, ist die fehlende Attempt-Historie; das Latest-Ledger ist weiterhin
  ueberschreibbar. Eine bewusste Ausnahme liegt in `gates.abnahmebericht`:
  Kollidiert der Ledger-Pfad kanonisch mit einer Artefaktrolle, wird gar kein
  Ledger geschrieben, damit der Lauf das Pflichtartefakt nicht zerstoert —
  dann kann ein aelterer gruener Beleg stehen bleiben. Der Aufruf ist rot und
  G-2 revalidiert ohnehin vollstaendig; wer das Abnahme-Ledger automatisiert
  auswertet, darf sich aber nicht allein auf seine Aktualitaet verlassen.)*

## Bewusst nicht Bestandteil dieser Entscheidung

- Ein vollstaendiger E2E-Durchlauf durch den Transformationsproduzenten sowie
  die Bindung von registrierter Quelle, Transformationsspec,
  Transformationsergebnis und Ziel werden separat in ToDo 10.13 korrigiert.
- Transformationsbefunde, Zeilenverlust und andere Pruefluecken blockieren seit
  ToDo 10.5 den Berichtserfolg. Ein weitergehendes vierstufiges Statusmodell
  wurde nicht eingefuehrt; der bestehende Gate-Vertrag bleibt binär und
  blockierend.
- Der Scope-Vertrag ersetzt den fachlichen Innenvertrag der Suite nicht.
  `gates.abnahmebericht` berechnet seit ToDo 10.4 Residuen, Einzel-,
  Vertrags- und Suiteurteile aus den atomaren Fakten neu und lehnt
  widerspruechliche Ableitungen als Contract-Fehler ab.

## Verworfene Alternativen

- B1 und Abnahmebericht fuer jeden Fall verlangen: verworfen, weil ein reiner
  Tariffall dadurch inhaltslose Bestandsartefakte erzeugen muesste.
- Den Scope aus vorhandenen CSV-/Parquet-Dateien erraten: verworfen, weil
  Dateiexistenz kein fachlicher Entscheid ist und durch Loeschen die
  Gate-Pflicht abschaltbar waere.
- Einen allgemeinen Gate-DAG einfuehren: verworfen, weil T6-03 nur die drei
  fehlenden Bestandsbelege nachgewiesen hat und ToDo 6.2 den Fehlerfix bewusst
  auf diesen Befund begrenzt.

## Nachtrag 2026-08-26 (ADR-010)

Die Pflichtbelegmenge dieses ADR beschreibt ab hier das Gate G-2. Mit
ADR-010 wird die scope-getriebene Belegmenge JE GATE aufgeloest
(`fall.BELEGROLLEN`): Das neue menschliche Gate G-A (aktuarielle
Abnahme) traegt eine eigene Rollenmenge — im Bestands-Scope das
Testergebnis und der Bericht des aktuariellen Tests, im Tarif-Scope
keine eigenen Rollen. G-2 verlangt zusaetzlich den geltenden
G-A-Snapshot als Pflichtrolle (`ga_snapshot`); die erzwungene
Reihenfolge G-A vor G-2 laeuft ueber den unveraenderten Kettenvertrag
aus ADR-008. Das P9-Schema hebt seine Version auf 5 (Gate-Version
0.6.0); v4-Snapshots sind keine gueltigen Belege des neuen Vertrags —
Altketten werden nach dem Verfahren dieses ADR revisionsfest archiviert
und neu entschieden. Die hier verworfene Alternative eines allgemeinen
Gate-DAG bleibt verworfen: Auch die Je-Gate-Aufloesung ist eine
deklarierte Tabelle, kein frei konfigurierbarer Graph.
