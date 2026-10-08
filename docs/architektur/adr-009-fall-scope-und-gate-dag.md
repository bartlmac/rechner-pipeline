# ADR-009: Fall-Scope und Bestands-Pflichtbelege für A-M4

**Status:** angenommen am 2026-08-20 (Maintainer).

## Kontext

A-M4 verlangte bisher für jeden Fall P-Q3, A-Q1 und die exakte Menge grüner
P-K1-Belege. Ob ein Fall zugleich einen Bestand übernimmt, war nicht
maschinenlesbar deklariert. Deshalb konnte ein Bestandsfall ohne P-B1,
vollständig geprüfte Migrationssuite und Abnahmebericht angenommen werden.
Ein pauschaler Dateiname-Check wäre die falsche Reparatur: Ein reiner
Tariffall hat diese Artefakte fachlich nicht und darf sie nicht künstlich
erzeugen müssen.

Die drei Bestandsbelege haben unterschiedliche Erzeuger. Eine bloße
Existenzprüfung belegt weder ihren Zusammenhang noch, dass sie denselben
Eingangs-, A-Box-, Code-, Bestands- und Stichtagsstand beschreiben.

## Entscheidung

1. Jeder neu angelegte Fall deklariert in `fall.json` einen Scope mit
   Schema-Version und Typ `tarif` oder `bestand`. Ein Altfall ohne Scope wird
   bei A-M4 nicht geraten und blockiert bis zur bewussten Migration seines
   Manifests.
2. Der Scope `tarif` verlangt P-Q3-Ledger, geltenden signierten A-Q1-Snapshot und
   die exakte P-K1-Belegmenge der A-Box. Bestandsartefakte sind weder Pflicht
   noch wird aus zufällig vorhandenen Dateien ein anderer Scope abgeleitet.
3. Der Scope `bestand` verlangt zusätzlich ein grünes P-B1-Ledger, eine
   vollständig geprüfte Migrationssuite und einen grün erzeugten
   HTML-Abnahmebericht.
4. P-B1 und Suite müssen denselben aktuell vorhandenen Bestand per SHA-256
   binden. P-B1 muss außerdem den aktuellen Systemstand tragen; die Suite muss
   genau die beiden chronologischen Berichtsstichtage binden.
5. `gates.abnahmebericht` erzeugt ein grünes Ledger nur mit
   Transformationsspezifikation, Transformationsergebnis und zwei vorhandenen,
   verschiedenen Vor-/Nachberichten. Alle Eingabe-, die HTML-Ausgabe- und die
   Gate-Ledger-Rolle müssen paarweise verschiedene Dateien bezeichnen;
   kanonische Pfad- und Hardlink-Aliase blockieren vor dem Rendern.
   Prüflücken, nicht kongruente
   Transformationszeilenzahlen, Transformationsbefunde und nicht entschiedene
   Konflikte blockieren den Bericht. Im Bestands-Scope bindet das grüne Ledger
   P-B1-Ledger, Suite und HTML-Bericht durch Fall-relativen Pfad und SHA-256
   gemeinsam an Eingangsregister, A-Box, Systemstand und beide Stichtage. Eine
   zweite, exakt vierteilige Rollenabbildung bindet Spec,
   Transformationsergebnis sowie Vor- und Nachbericht jeweils an sicheren
   Fallpfad und SHA-256; die Pfadschlüssel in `input_hashes` ersetzen diese
   Rollen nicht.
6. A-M4 vertraut diesem frei editierbaren Ledger nicht blind. Es prüft dessen
   Gate-Vertrag, hasht alle drei Artefakte und den von P-B1 benannten aktuellen
   Portfolio-Eingang neu und führt die produktiven P-B1-Engines auf den
   strukturiert persistierten Eingangsrollen und Optionen erneut aus. Die
   Suite wird semantisch erneut validiert; P-B1-Portfoliozeilen und
   vollständige Suite-Prüfmenge müssen exakt übereinstimmen. Schließlich
   liest A-M4 die vier Renderer-Artefakte aus ihren Rollen neu, gleicht Spec und
   Transformationsergebnis typ- und wertgenau mit dem kanonischen
   Renderer-Vertrag ab, leitet Zeilenzahlen, Befunde und Konflikte aus den
   gebundenen Inhalten neu ab und verlangt beim neu gerenderten HTML
   Bytegleichheit. P9-Snapshot-Schema v4 pinnt Scope und die exakte
   rollenbezogene Pflichtbelegmenge.

## Konsequenzen

- Ein Bestandsfall kann nicht mehr ohne P-B1, vollständige Suite und
  Abnahmebericht zu A-M4 gelangen. Das Entfernen oder Ändern eines dieser
  Belege blockiert die Annahme.
- Eine für sich grüne Suite reicht nicht für einen grünen Abnahmebericht:
  fehlende Pflichtartefakte, Prüflücken, Zeilenverlust,
  Transformationsbefunde oder nicht entschiedene Konflikte werden als
  `abnahmehindernisse` im Ledger und als roter Kopfsatz im HTML sichtbar.
  Eine Datei kann nicht durch Pfad- oder Hardlink-Aliase mehrere Pflichtrollen
  ersetzen oder durch Renderer beziehungsweise Ledger überschrieben werden.
- Ein Tariffall bleibt schlank. Sein positiver A-M4-Pfad benötigt keinerlei
  künstliche Parquet- oder Berichtsdatei.
- `fall anlegen` verwendet für Rückwärtskompatibilität den explizit im
  erzeugten Manifest gespeicherten Default `--scope tarif`. Bestandsfälle
  werden mit `--scope bestand` angelegt.
- Bestehende P9-v2/v3-Snapshots tragen noch nicht den aktuellen
  Scope-Vertrag und sind deshalb keine Belege für den v4-Vertrag. Offene
  Fälle werden nach revisionsfester
  Archivierung der alten Kette auf dem deklarierten Scope neu entschieden; es
  gibt keine stille Umdeutung.
- Das Abnahme-Ledger ist noch ein überschriebenes Latest-Ledger. A-M4 begegnet
  seiner fehlenden Authentisierung durch vollständige Revalidierung; eine
  unveränderliche Versuchshistorie gibt es weiterhin nur für grüne
  P-K1-Belege.

  *(Nachtrag 2026-08-24: Der rote Startbeleg ist im selben Stand
  umgesetzt. Jeder Gate-Lauf ersetzt den alten Beleg vor der Facharbeit
  durch einen roten Startbeleg und publiziert den Abschluss atomar
  (`gates._common.begin_gate_ledger_attempt` / `finalize_gate_ledger`). Was
  bleibt, ist die fehlende Attempt-Historie; das Latest-Ledger ist weiterhin
  überschreibbar. Eine bewusste Ausnahme liegt in `gates.abnahmebericht`:
  Kollidiert der Ledger-Pfad kanonisch mit einer Artefaktrolle, wird gar kein
  Ledger geschrieben, damit der Lauf das Pflichtartefakt nicht zerstört;
  dann kann ein älterer grüner Beleg stehen bleiben. Der Aufruf ist rot und
  A-M4 revalidiert ohnehin vollständig; wer das Abnahme-Ledger automatisiert
  auswertet, darf sich aber nicht allein auf seine Aktualität verlassen.)*

## Bewusst nicht Bestandteil dieser Entscheidung

- Ein vollständiger E2E-Durchlauf durch den Transformationsproduzenten sowie
  die Bindung von registrierter Quelle, Transformationsspec,
  Transformationsergebnis und Ziel werden separat korrigiert.
- Transformationsbefunde, Zeilenverlust und andere Prüflücken blockieren
  den Berichtserfolg. Ein weitergehendes vierstufiges Statusmodell
  wurde nicht eingeführt; der bestehende Gate-Vertrag bleibt binär und
  blockierend.
- Der Scope-Vertrag ersetzt den fachlichen Innenvertrag der Suite nicht.
  `gates.abnahmebericht` berechnet Residuen, Einzel-,
  Vertrags- und Suiteurteile aus den atomaren Fakten neu und lehnt
  widersprüchliche Ableitungen als Contract-Fehler ab.

## Verworfene Alternativen

- P-B1 und Abnahmebericht für jeden Fall verlangen: verworfen, weil ein reiner
  Tariffall dadurch inhaltslose Bestandsartefakte erzeugen müsste.
- Den Scope aus vorhandenen CSV-/Parquet-Dateien erraten: verworfen, weil
  Dateiexistenz kein fachlicher Entscheid ist und durch Löschen die
  Gate-Pflicht abschaltbar wäre.
- Einen allgemeinen Gate-DAG einführen: verworfen, weil der Befund
  (T6-03) nur die drei fehlenden Bestandsbelege nachgewiesen hat und die
  Behebung bewusst auf diesen Befund begrenzt ist.

## Nachtrag 2026-08-26 (ADR-010)

Die Pflichtbelegmenge dieses ADR beschreibt ab hier das Gate A-M4. Mit
ADR-010 wird die scope-getriebene Belegmenge je Gate aufgelöst
(`fall.BELEGROLLEN`, seit ADR-021 `models.belegrollen.BELEGROLLEN`): Das neue menschliche Gate A-M1 (aktuarielle
Abnahme) trägt eine eigene Rollenmenge: im Bestands-Scope das
Testergebnis und der Bericht des aktuariellen Tests, im Tarif-Scope
keine eigenen Rollen. A-M4 verlangt zusätzlich den geltenden
A-M1-Snapshot als Pflichtrolle (`am1_snapshot`); die erzwungene
Reihenfolge A-M1 vor A-M4 läuft über den unveränderten Kettenvertrag
aus ADR-008. Das P9-Schema hebt seine Version auf 5 (Gate-Version
0.6.0); v4-Snapshots sind keine gültigen Belege des neuen Vertrags;
Altketten werden nach dem Verfahren dieses ADR revisionsfest archiviert
und neu entschieden. Die hier verworfene Alternative eines allgemeinen
Gate-DAG bleibt verworfen: Auch die Je-Gate-Auflösung ist eine
deklarierte Tabelle, kein frei konfigurierbarer Graph. Die heute geltende
Menge steht in `models/belegrollen.py`; sie wuchs mit ADR-018 (Nachtrag
2026-10-01), ADR-025 und ADR-026.
