# ADR-013: Der Kommutations-Kreuzcheck wird außer Betrieb genommen

**Status:** angenommen am 2026-08-28 (Maintainer). Löst Punkt 2 von
ADR-004 ab. Umgesetzt: `rechner_pipeline.qa.ueberleitung` ist entfernt.
Der Zweitkern `rechner_pipeline.kommutationskern` blieb zunächst ohne
Konsumenten im Paket; seit dem Nachtrag 2026-10-04 liegt er nicht mehr in
`src`, sondern dient den Tests als Zeuge.

## Kontext

ADR-004 hat 2026-08-16 die Kommutation aus dem Zielkern gezogen und als
separaten Zweitkern geführt, mit genau einem Zweck: dem Kreuz-Check der
beiden Rechenschienen. Der Zielkern rechnet Thiele auf einem
(Semi-)Markov-Zustandsmodell, der Zweitkern dieselbe Mathematik in der
geschlossenen Kommutationsform; `qa/ueberleitung` ließ beide über
denselben Produktcode laufen und verglich.

Das war der **Übersetzungsbeleg** des Backbone-Wechsels: 6170 Werte, 0
abweichend, größte relative Abweichung 4e-13, abgenommen am
2026-08-12 (kern 2.0.0). Ein Übersetzungsbeleg ist seiner Natur nach
einmalig. Seither läuft der Vergleich als stehende Doppelimplementierung
mit — und kostet mehr als die Wartung zweier Pakete.

**Er formt den Zielkern.** Damit der Zweitkern eingehängt werden kann,
hält `ZustandsBarwerte` (`kern/zustandsmodell.py`) das
`Barwerte`-Interface aufrecht: drei Einheits-Barwerte — Rente,
Todesfall, Erleben. Mehr gibt die Kommutation nicht her; D/N/C/M können
keinen beliebigen Zahlungsverlauf ausdrücken. Der KLV-Produktcode
multipliziert diese drei Werte mit Versicherungssumme und Beitrag, und
in dieser Multiplikation steckt die Annahme, dass beide über die
Laufzeit konstant sind.

Das ist die Grenze des Kommutationsmodells, verpflanzt in die
Thiele-Welt. Sie blockiert konkret: Ein Vertrag, dessen Leistung oder
Beitrag sich mitten im Verlauf geändert hat — Herabsetzung,
Beitragsfreistellung, Erhöhung, Zuzahlung — ist so nicht darstellbar.
Für einen Migrationskern ist das keine Randfrage, sondern der Normalfall
eines Altbestands (dev-docs/zahlungspfade-migrierter-vertraege.md).

## Entscheidung

Der Kreuz-Check wird außer Betrieb genommen — geschnitten werden die
Ansprüche des Zweitkerns an den lebenden Code, nicht der Zweitkern
selbst. Was fällt:

* `rechner_pipeline.qa.ueberleitung` samt seinen sieben Tests: die
  stehende Doppelrechnung über den ganzen Produktpfad.
* Die Einhängestelle `KLV(mp, barwerte=...)`
  (`kern/produkte/klv.py`). Sie war der eigentliche Anspruch: Über
  ein austauschbares `Barwerte`-Rückgrat kann nur kommen, was die
  Kommutation liefern kann — Einheitsbarwerte, also konstante Summe
  und konstanter Beitrag. Nach dem Wegfall der Überleitung hatte sie
  keinen Aufrufer mehr.
* Der Platz des Zweitkerns in der Hausordnung:
  `ZWEITKERN_KONSUMENTEN` steht auf `{"kommutationskern"}`, und der
  Schichtentest verlangt jetzt die Umkehrung seiner früheren
  Behauptung — er forderte die Kante `qa -> Zweitkern`, er verbietet
  sie nun.
* Die Docstrings des Zielkerns, die den Zweitkern eine lebende
  Kreuz-Check-Schiene nannten.

**Was bleibt: der Zweitkern selbst.** Er ist keine tote Last, sondern
ein Zeuge — `tests/test_kern_algebraisch.py` hält die Durchreicher
`pv_benefits`/`pv_premiums`/`net_premium` des Zielkerns gegen ihn. Der
Docstring dieses Tests hält fest, warum: *"Früher stand hier
net_premium == pv_benefits/pv_premiums — der Methodenrumpf gegen sich
selbst, also wahr für jede A_x. Jetzt entscheidet ein zweiter,
unabhängig gebauter Kern."* Diese Unabhängigkeit aufzugeben wäre ein
Rückschritt hinter einen Reviewbefund.

Entscheidend ist die Art der Nutzung: Der Test baut den Zweitkern
testseitig selbst und vergleicht Skalare. Er hängt ihn nicht in den
Zielkern ein. Damit stellt der Zweitkern keine Anforderungen mehr an den
lebenden Code und prägt ihn nicht mehr.

Was bleibt und die Sicherung trägt: die **eingefrorenen
Referenzwerte** in `tests/fixtures/kern_referenzwerte/`. Sie nageln
`berechne()` für sechs Modellpunkte bit-exakt fest und sind laut ihrem
eigenen Test „seit dem Backbone-Wechsel die Voll-Präzisions-Referenz
des produktiven Pfads“. Ein Diff dort ist eine Verhaltensänderung und
braucht eine bewusste, fachlich begründete Abnahme.

**Der Nachweis nach dem Muster von ADR-006**: Es wird keine geprüfte
Eigenschaft des Zielsystems aufgegeben. Der Kreuz-Check prüft, dass
zwei Implementierungen derselben Mathematik übereinstimmen — eine
Aussage über den abgeschlossenen Übergang, nicht über das Verhalten
des Zielsystems. Dessen Verhalten sichern die Referenzwerte, und die
bleiben.

Der Zeitpunkt ist bewusst gewählt: Die anstehende Umstellung des
Bewertungspfads auf Zahlungspfade braucht die Referenzwerte als
Abnahme — sie sind dafür das schärfere Instrument als ein zweiter
lebender Kern, weil sie bit-exakt vergleichen statt auf Toleranz.

## Die allgemeine Regel

Diese Entscheidung ist nicht die letzte ihrer Art. Sobald die KLV auf
Zahlungspfaden rechnet, ist der skalare Pfad der stillgelegte, und
dieselbe Frage stellt sich erneut. Deshalb als Regel:

> Eine stillgelegte Rechenschiene wird vom produktiven Pfad weder
> importiert noch durch eine Schnittstelle bedient, die er ihretwegen
> aufrechterhält, noch durch eine Architekturregel geschützt. Ihr
> Beleg wird eingefroren und bleibt zitierbar; ihr Code wird geparkt
> oder entfernt. Vorher ist zu zeigen, dass keine geprüfte Eigenschaft
> des Zielsystems aufgegeben wird, sondern nur die Prüfung eines
> abgeschlossenen Übergangs.

Der Kern der Regel ist die mittlere Bedingung. Ein ungenutztes Modul,
das nur herumliegt, stört niemanden — was stört, sind seine
**Ansprüche** an den lebenden Code: eine Schnittstelle, die seinetwegen
gehalten wird, eine Hausregel, die ihm einen Platz einräumt, ein
Docstring, der ihn lebendig nennt. Wer stilllegt, schneidet die
Ansprüche; der Code folgt dann von selbst.

## Konsequenzen

* 180 Zeilen Produktionscode und sieben Tests entfallen; der Zielkern
  verliert seine Austauschstelle für das Rechenrückgrat.
* Die Kommutationsform bleibt im Hauptzweig verfügbar, aber ohne
  Anspruch: kein `src`-Modul importiert sie, keine Hausregel räumt ihr
  einen Platz ein, kein Docstring des Zielkerns nennt sie lebendig.
* `ZustandsBarwerte` verliert seine zweite Aufgabe und ist danach eine
  reine Effizienzschicht. Gemessen 2026-08-28 an 500 Verträgen trägt
  sie sich nicht mehr: Der Spalten-Cache bringt Faktor 14,5 gegenüber
  dem ungecachten Skalarweg, ein eigener Zahlungspfad je Vertrag ist mit
  0,03 ms gegen 0,04 ms aber sogar schneller als der gecachte — er
  rechnet eine Rekursion über die Vertragslaufzeit statt drei
  Einheitsspalten über den ganzen Altersbereich. Damit steht der
  Umstellung auf Zahlungspfade nichts mehr im Weg.
* Der Zielkern verliert den flächendeckenden Vergleich zweier
  Implementierungen über den ganzen Produktpfad. Was von der
  Unabhängigkeit bleibt, ist punktuell: die drei Durchreicher in den
  algebraischen Eigenschaftstests. Für das Verhalten des Zielkerns
  treten die bit-exakten Referenzwerte ein.

## Bewusst nicht Bestandteil dieser Entscheidung

* Die Umstellung des KLV-Bewertungspfads auf Zahlungspfade. Sie ist der
  Grund, warum diese Entscheidung jetzt fällt, aber ein eigenes
  Vorhaben mit eigener Abnahme
  (dev-docs/zahlungspfade-migrierter-vertraege.md).
* Der Verbleib von `ZustandsBarwerte`. Solange die KLV Einheitsbarwerte
  abfragt, bleibt die Schicht; sie fällt mit der Umstellung, nicht mit
  dieser Entscheidung.
* Die Excel-Parität des Quellrechners (Gate P-K1). Sie prüft eine
  Lieferung gegen ihren eigenen Rechner und hat mit den internen
  Rechenschienen nichts zu tun.

## Nachtrag 2026-10-04: Der Zweitkern liegt nicht mehr im Paket

Mit ADR-027 ist `rechner_pipeline.kommutationskern` aus `src` entfernt. Der
Code lebt als Zeuge der Kern-Tests weiter (`tests/kommutationszeuge.py`):
Die algebraischen Tests halten die Whole-Life-Durchreicher und das
Äquivalenzprinzip auf dem produktiven Beitragspfad weiterhin gegen diesen
zweiten, unabhängig gebauten Rechenweg.

Die Sonderregel der Schichtenkarte (`ZWEITKERN_KONSUMENTEN`) entfällt mit
der Schicht. Kehrte ein solches Paket nach `src` zurück, wäre es eine
Schicht ohne Regel-Eintrag und damit ein Befund der Karte.

Im Kern selbst, in der Grundsatzdokumentation und im Tarifplan KLV wird der
Zweitkern noch genannt. Diese Dateien sind abgenommene Gegenstände
(Kernstand, Tarifwerk) und werden mit ihrer nächsten Abnahme nachgezogen
(`dev-docs/offene-punkte.md`).
