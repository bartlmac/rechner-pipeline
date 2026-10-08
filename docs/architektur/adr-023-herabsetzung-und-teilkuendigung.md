# ADR-023: Herabsetzung und Teilkündigung sind getrennte Geschäftsvorfälle

**Status:** angenommen am 2026-10-01 (Maintainer).

## Kontext

Bis Kern 3.15.0 führte das Zielsystem die Teilkündigung als drittes
*Verfahren* der Beitragsherabsetzung (`red_verfahren = teilkuendigung`,
Bedingungswerk der übernommenen Generation TG2015, Ziffer 6). Gebucht wurde
sie als `RED`, mit einer zusätzlichen Zahlungszeile `RKW_teilkuendigung`.
Eine eigene Generation mit `prospektiv` oder `mit_abzug` kannte keine
Teilkündigung, und nach dem Beitragsende (Vertragsjahr $\geq t$) war nur
dieses Verfahren definiert.

Der Entscheid des Maintainers vom 2026-10-01, ein ausfinanzierter Vertrag
müsse in jeder Generation herabsetzbar sein, wurde zunächst als "Regel A"
gebaut: nach dem Beitragsende rechnet jede Herabsetzung still als
Teilkündigung (eine Funktion im Kern deutete das Verfahren nach dem Jahr
um). Der Maintainer hat das am selben Tag ersetzt:

> Wir sollten in PLV beides haben. Herabsetzung betrifft nur Beiträge und
> macht nur Sinn, so lange ein Beitrag bezahlt wird. Eine Teilkündigung kann
> immer (beitragspflichtig oder ausfinanziert) gemacht werden, hat aber eine
> andere Wirkung — Teil des Deckungskapitals wird ausgezahlt. Das sind im
> Grunde zwei verschiedene Vorgänge und betreffen alle PLV-Tarife gleich.

## Entscheid

1. **Beitragsherabsetzung (`RED`).** Der Beitrag sinkt auf den Anteil $f$,
   der freiwerdende Teil wird in beitragsfreie Summe umgewandelt
   (`prospektiv` oder `mit_abzug`); es fließt kein Geld. Nur während der
   Beitragszahlung ($0 < a_0 < t$) und ohne Beitragsfreistellung. Danach
   verweigern Kern, Datenmodell und Bindung benannt, mit dem Ausweg
   "Teilkündigung".
2. **Teilkündigung (`TKU`).** Der Anteil $(1-f)$ der Grundversicherung wird
   gekündigt und mit seinem Rückkaufswert nach dem Tarifwerk der Generation
   (mit Stornoabzug) ausgezahlt; der Vertrag läuft mit $f \cdot S$
   zustandslos weiter. In jeder Generation, beitragspflichtig wie
   ausfinanziert ($0 < a_0 < n$). Eigener Ledger-Code, eigene Rate
   (`annahmen.teilkuendigung`), eigener Anteil (`annahmen.tk_anteil`),
   eigener Zufallsstrom (`bestand.zufallsstroeme`, `teilkuendigung`).
3. **Das Ledger sagt, was geschah.** Eine Teilkündigung ist nie als `RED`
   gebucht. Beide Vorgänge stehen in derselben Tabelle `reduktionen`
   (seit dem Nachtrag beliebig viele Zeilen je Vertrag); ihr Verfahren bestimmt den Code
   (`models.bestand.reduktion_ereignis`).

Die Annahmen, unter denen gebaut ist (A1 bis A4), und die verweigerten
Kombinationen stehen im Tarifplan KLV, Abschnitt 7.2.

## Verworfene Alternative

Ein Vorgang mit Verfahrensschalter und stiller Umdeutung (die gebaute
Regel A: eine Herabsetzung nach $t$ wird als Teilkündigung gerechnet und als
`RED` gebucht). Verworfen, weil es zwei Vorgänge mit verschiedener Wirkung
sind — der eine senkt den Beitrag ohne Zahlung, der andere zahlt einen Teil
des Deckungskapitals aus —, und das Ledger sagen muss, was geschah; ein
Leser, der `RED` sieht, darf keine Auszahlung vermuten müssen.

## Folgen

* Ein neuer Ereigniscode `TKU` mit den Betragsarten `VS_teilkuendigung`,
  `dDK_absorption`, `RKW_teilkuendigung` und `Kappung_teilkuendigung`; die
  Herabsetzung bucht nur noch `VS_herabsetzung` und `dDK_absorption`.
  Jeder Leser (P-B1, Führungsprobe, Bewegungskonto mit eigener Position
  "Teilkündigung", Bestandsbericht, Abschluss, Betriebsseite,
  Korrekturschicht) kennt ihn; eine Ratsche über die Aufzähler hält die
  Menge fest, sodass der nächste neue Code an einer Stelle auffällt.
* Eigene Generationen ohne Teilkündigungsrate rechnen bitgleich wie vor
  dem Entscheid (Rate 0 als Vorgabe, Ziehung hinter der Jahresbedingung,
  eigener Strom). Eine Generation mit `red_verfahren = teilkuendigung`
  bucht ihren Herabsetzungswunsch jetzt als `TKU` statt `RED` — gleiche
  Beträge, anderer Code.
* Im Migrationszugang war eine gelieferte Absetzung nach $t$ eine
  Teilkündigung (Annahme A2). Ein Vertrag, dessen Anfangszustand nicht
  ableitbar ist, wird verweigert statt still zustandslos übernommen;
  gedeckt ist er nur durch eine registrierte Auskunft, und dann ist er
  Pflichtziehung der Abnahmen (ADR-002, Nachtrag 2026-10-01).
* Versionen: Kern `3.16.0`, Abnahmebericht `GATE_VERSION 7.0.0`,
  Führungsprobe `SCHEMA_VERSION 4`.


## Nachtrag 2026-10-01: Folgen von Vorgängen, ein Vokabular

**Entscheide des Maintainers (2026-10-01).** Sie ersetzen die Annahmen A1,
A3 und A4 und die Verweigerungen der ersten Fassung:

* Ein Vertrag trägt **beliebig viele** Herabsetzungen und Teilkündigungen,
  in **jeder Reihenfolge**, verschränkt mit Erhöhungen und der
  Beitragsfreistellung; jeder Vorgang wirkt auf den Zustand, den der Vertrag
  gerade hat. Der Zustand ist die Folge seiner Vorgänge (Grundsatzdokumentation
  7.2), und es gibt **eine** Darstellung davon im Kern
  (`kern/vorgangsfolge.py`), die jeder Leser rechnet — Ereignis-Engine,
  Bewertung und Abschluss, Ledger-Herleitung (P-B1), Bewegungskonto,
  Führungsprobe, Migrationssuite samt Führungswert, aktuarieller Test,
  Verankerung. Die Tabelle `reduktionen` trägt beliebig viele Zeilen je
  Vertrag (eindeutig je Police, Jahr und Vorgang).
* Die Herabsetzung gilt nur, solange Beitrag gezahlt wird — nicht ab dem
  Beitragsende, nicht nach der Beitragsfreistellung (verweigert, Ausweg
  Teilkündigung). Die Teilkündigung gilt bis zum Ablauf, auch nach der
  Beitragsfreistellung; dort zahlt sie den Rückkaufswert des beitragsfreien
  Vertrags aus (B3: Rückstellung abzüglich des Stornoabzugs nach derselben
  Tarifregel auf der beitragsfreien Summe).
* Die Teilkündigung der eigenen Tarife kürzt **alle Bausteine**
  anteilig; der übernommene Tarif TG2015 kündigt nur die Grundversicherung
  (B1). Beides ist **ein** Merkmal des Tarifwerks je Generation,
  `tku_umfang`.
* Der übernommene Tarif kennt **einen** Vorgang: Seine "Herabsetzung" ist
  die Teilkündigung der PLV und kommt allein aus deren Rate (die frühere
  Annahme A1 und ihre zweite Rate entfallen). Der Code `RED` der Quelle
  bleibt Provenienzname; ab der Migration gilt das Vokabular des
  Zielsystems (Grundsatzdokumentation 7.1), die Übersetzung ist eine
  benannte Regel an einer Stelle (`models.bestand.alt_absetzung_ist_teilkuendigung`,
  in der Form des Verfahrens `zielverfahren`), für diesen Tarif immer
  Teilkündigung. A2 ist bestätigt.

Als Annahmen gebaut und im Tarifplan KLV (Abschnitte 7.2 und 7.3) mit der
verworfenen Alternative benannt: B2 (jeder Vorgang proportional auf dem
Zustand), B4 (Homogenität, je Größe geprüft: Stückkosten, Grenzen des
Stornoabzugs und Korrekturschicht werden nie skaliert) und B5 (eine Quelle
mit echter Herabsetzung: vor dem Beitragsende Herabsetzung, danach und nach
der Beitragsfreistellung Teilkündigung). Die Tabelle der Kombinationen im
Tarifplan ist eine Auswahl; die Menge der zulässigen Folgen beschreibt eine
Regel dort, und Eigenschaftstests über erzeugte Folgen halten sie.

**Verworfene Alternative.** Die Verkettung je Leser nachzubauen (jeder Leser
erweitert seinen Einzelvorgang-Weg um "zweiter Vorgang"). Verworfen, weil
genau das die Klasse war, die die erste Fassung verweigern ließ: Jeder Leser
hatte seine eigene Rekonstruktion, und eine Regel, die nur in einem Leser
steht, läuft den anderen davon. Eine Ratsche
(`tests/test_vorgangsfolge_ratsche.py`) hält fest, dass kein Leser mehr einen
einzelnen Vorgang annimmt.

**Folgen.**

* Verträge ohne Vorgang rechnen unverändert (sie laufen nicht über die
  Folge); Verträge mit genau einem Vorgang bitgleich wie zuvor. Es bewegen
  sich: Verträge mit mehr als einem Vorgang, Teilkündigungen eigener Tarife
  mit Erhöhungsscheiben (jetzt anteilig über alle Bausteine) und
  Teilkündigungen nach der Beitragsfreistellung (jetzt gezogen).
* Die Prüfstrecke rechnet Folge-Geschäftsvorfälle, statt sie als "nicht
  abgebildet" zu melden; ein Rückkauf nach der Beitragsfreistellung wird
  gemessen statt als "nicht definiert" gemeldet. Die Übernahme führt eine
  Vorgeschichte mit mehreren Absetzungen; einen durch eine Herabsetzung der
  Vorgeschichte geteilten Vertrag schaltet sie weiter benannt nicht frei.
* Versionen: Kern `3.17.0`.
