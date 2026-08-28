# ADR-013: Der Kommutations-Kreuzcheck wird ausser Betrieb genommen

Status: akzeptiert (Maintainer, 2026-08-28). Loest Punkt 2 von ADR-004 ab.
Umgesetzt: `rechner_pipeline.qa.ueberleitung` entfernt; der Zweitkern
`rechner_pipeline.kommutationskern` bleibt ohne Konsumenten im
Produktivpfad.

## Kontext

ADR-004 hat 2026-08-16 die Kommutation aus dem Zielkern gezogen und als
separaten Zweitkern gefuehrt, mit genau einem Zweck: dem Kreuz-Check der
beiden Rechenschienen. Der Zielkern rechnet Thiele auf einem
(Semi-)Markov-Zustandsmodell, der Zweitkern dieselbe Mathematik in der
geschlossenen Kommutationsform; `qa/ueberleitung` liess beide ueber
denselben Produktcode laufen und verglich.

Das war der **Uebersetzungsbeleg** des Backbone-Wechsels: 6170 Werte, 0
abweichend, groesste relative Abweichung 4e-13, abgenommen am
2026-08-12 (kern 2.0.0). Ein Uebersetzungsbeleg ist seiner Natur nach
einmalig. Seither laeuft der Vergleich als stehende Doppelimplementierung
mit — und kostet mehr als die Wartung zweier Pakete.

**Er formt den Zielkern.** Damit der Zweitkern eingehaengt werden kann,
haelt `ZustandsBarwerte` (`kern/zustandsmodell.py`) das
`Barwerte`-Interface aufrecht: drei EINHEITS-Barwerte — Rente,
Todesfall, Erleben. Mehr gibt die Kommutation nicht her; D/N/C/M koennen
keinen beliebigen Zahlungsverlauf ausdruecken. Der KLV-Produktcode
multipliziert diese drei Werte mit Versicherungssumme und Beitrag, und
in dieser Multiplikation steckt die Annahme, dass beide ueber die
Laufzeit konstant sind.

Das ist die Grenze des Kommutationsmodells, verpflanzt in die
Thiele-Welt. Sie blockiert konkret: Ein Vertrag, dessen Leistung oder
Beitrag sich mitten im Verlauf geaendert hat — Herabsetzung,
Beitragsfreistellung, Erhoehung, Zuzahlung — ist so nicht darstellbar.
Fuer einen Migrationskern ist das keine Randfrage, sondern der Normalfall
eines Altbestands (dev-docs/zahlungspfade-migrierter-vertraege.md).

## Entscheidung

Der Kreuz-Check wird ausser Betrieb genommen — geschnitten werden die
ANSPRUECHE des Zweitkerns an den lebenden Code, nicht der Zweitkern
selbst. Was faellt:

* `rechner_pipeline.qa.ueberleitung` samt seinen sieben Tests: die
  stehende Doppelrechnung ueber den ganzen Produktpfad.
* Die Einhaengestelle `KLV(mp, barwerte=...)`
  (`kern/produkte/klv.py`). Sie war der eigentliche Anspruch: Ueber
  ein austauschbares `Barwerte`-Rueckgrat kann nur kommen, was die
  Kommutation liefern kann — Einheitsbarwerte, also konstante Summe
  und konstanter Beitrag. Nach dem Wegfall der Ueberleitung hatte sie
  keinen Aufrufer mehr.
* Der Platz des Zweitkerns in der Hausordnung:
  `ZWEITKERN_KONSUMENTEN` steht auf `{"kommutationskern"}`, und der
  Schichtentest verlangt jetzt die UMKEHRUNG seiner frueheren
  Behauptung — er forderte die Kante `qa -> Zweitkern`, er verbietet
  sie nun.
* Die Docstrings des Zielkerns, die den Zweitkern eine lebende
  Kreuz-Check-Schiene nannten.

**Was BLEIBT: der Zweitkern selbst.** Er ist keine tote Last, sondern
ein Zeuge — `tests/test_kern_algebraisch.py` haelt die Durchreicher
`pv_benefits`/`pv_premiums`/`net_premium` des Zielkerns gegen ihn. Der
Docstring dieses Tests haelt fest, warum: *"Frueher stand hier
net_premium == pv_benefits/pv_premiums — der Methodenrumpf gegen sich
selbst, also wahr fuer JEDE A_x. Jetzt entscheidet ein zweiter,
unabhaengig gebauter Kern."* Diese Unabhaengigkeit aufzugeben waere ein
Rueckschritt hinter einen Reviewbefund.

Entscheidend ist die Art der Nutzung: Der Test BAUT den Zweitkern
testseitig selbst und vergleicht Skalare. Er haengt ihn NICHT in den
Zielkern ein. Damit hat der Zweitkern keinen Anspruch mehr an den
lebenden Code — und formt ihn auch nicht mehr. Genau das ist die
Trennlinie, um die es geht.

Was bleibt und die Sicherung traegt: die **eingefrorenen
Referenzwerte** in `tests/fixtures/kern_referenzwerte/`. Sie nageln
`berechne()` fuer sechs Modellpunkte bit-exakt fest und sind laut ihrem
eigenen Test "seit dem Backbone-Wechsel die Voll-Praezisions-Referenz
des produktiven Pfads". Ein Diff dort ist eine Verhaltensaenderung und
braucht eine bewusste, fachlich begruendete Abnahme.

**Der Nachweis nach dem Muster von ADR-006**: Es wird keine gepruefte
Eigenschaft des Zielsystems aufgegeben. Der Kreuz-Check prueft, dass
zwei Implementierungen derselben Mathematik uebereinstimmen — eine
Aussage ueber den abgeschlossenen Uebergang, nicht ueber das Verhalten
des Zielsystems. Dessen Verhalten sichern die Referenzwerte, und die
bleiben.

Der Zeitpunkt ist bewusst gewaehlt: Die anstehende Umstellung des
Bewertungspfads auf Zahlungspfade braucht die Referenzwerte als
Abnahme — sie sind dafuer das schaerfere Instrument als ein zweiter
lebender Kern, weil sie bit-exakt vergleichen statt auf Toleranz.

## Die allgemeine Regel

Diese Entscheidung ist nicht die letzte ihrer Art. Sobald die KLV auf
Zahlungspfaden rechnet, ist der skalare Pfad der stillgelegte, und
dieselbe Frage stellt sich erneut. Deshalb als Regel:

> Eine stillgelegte Rechenschiene wird vom produktiven Pfad weder
> importiert noch durch eine Schnittstelle bedient, die er ihretwegen
> aufrechterhaelt, noch durch eine Architekturregel geschuetzt. Ihr
> Beleg wird eingefroren und bleibt zitierbar; ihr Code wird geparkt
> oder entfernt. Vorher ist zu zeigen, dass keine gepruefte Eigenschaft
> des Zielsystems aufgegeben wird, sondern nur die Pruefung eines
> abgeschlossenen Uebergangs.

Der Kern der Regel ist die mittlere Bedingung. Ein ungenutztes Modul,
das nur herumliegt, stoert niemanden — was stoert, sind seine
**Ansprueche** an den lebenden Code: eine Schnittstelle, die seinetwegen
gehalten wird, eine Hausregel, die ihm einen Platz einraeumt, ein
Docstring, der ihn lebendig nennt. Wer stilllegt, schneidet die
Ansprueche; der Code folgt dann von selbst.

## Konsequenzen

* 180 Zeilen Produktionscode und sieben Tests entfallen; der Zielkern
  verliert seine Austauschstelle fuer das Rechenrueckgrat.
* Die Kommutationsform bleibt im Hauptzweig verfuegbar, aber ohne
  Anspruch: kein `src`-Modul importiert sie, keine Hausregel raeumt ihr
  einen Platz ein, kein Docstring des Zielkerns nennt sie lebendig.
* `ZustandsBarwerte` verliert seine zweite Aufgabe und ist danach eine
  reine Effizienzschicht. Gemessen 2026-08-28 an 500 Vertraegen traegt
  sie sich nicht mehr: Der Spalten-Cache bringt Faktor 14,5 gegenueber
  dem ungecachten Skalarweg, ein eigener Zahlungspfad je Vertrag ist mit
  0,03 ms gegen 0,04 ms aber sogar schneller als der gecachte — er
  rechnet eine Rekursion ueber die Vertragslaufzeit statt drei
  Einheitsspalten ueber den ganzen Altersbereich. Damit steht der
  Umstellung auf Zahlungspfade nichts mehr im Weg.
* Der Zielkern verliert den flaechendeckenden Vergleich zweier
  Implementierungen ueber den ganzen Produktpfad. Was von der
  Unabhaengigkeit bleibt, ist punktuell: die drei Durchreicher in den
  algebraischen Eigenschaftstests. Fuer das Verhalten des Zielkerns
  treten die bit-exakten Referenzwerte ein.

## Bewusst nicht Bestandteil dieser Entscheidung

* Die Umstellung des KLV-Bewertungspfads auf Zahlungspfade. Sie ist der
  Grund, warum diese Entscheidung jetzt faellt, aber ein eigenes
  Vorhaben mit eigener Abnahme
  (dev-docs/zahlungspfade-migrierter-vertraege.md).
* Der Verbleib von `ZustandsBarwerte`. Solange die KLV Einheitsbarwerte
  abfragt, bleibt die Schicht; sie faellt mit der Umstellung, nicht mit
  dieser Entscheidung.
* Die Excel-Paritaet des Quellrechners (Gate P-K1). Sie prueft eine
  LIEFERUNG gegen ihren eigenen Rechner und hat mit den internen
  Rechenschienen nichts zu tun.
