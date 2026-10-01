# ADR-023: Herabsetzung und Teilkuendigung sind getrennte Geschaeftsvorfaelle

**Status:** angenommen, 2026-10-01 (Entscheid des Maintainers im Dialog).

## Kontext

Bis Kern 3.15.0 fuehrte das Zielsystem die Teilkuendigung als drittes
*Verfahren* der Beitragsherabsetzung (`red_verfahren = teilkuendigung`,
Bedingungswerk der uebernommenen Generation TG2015, Ziffer 6). Gebucht wurde
sie als `RED`, mit einer zusaetzlichen Zahlungszeile `RKW_teilkuendigung`.
Eine eigene Generation mit `prospektiv` oder `mit_abzug` kannte keine
Teilkuendigung, und nach dem Beitragsende (Vertragsjahr $\geq t$) war nur
dieses Verfahren definiert.

Der Entscheid des Maintainers vom 2026-10-01, ein ausfinanzierter Vertrag
muesse in jeder Generation herabsetzbar sein, wurde zunaechst als "Regel A"
gebaut: nach dem Beitragsende rechnet jede Herabsetzung still als
Teilkuendigung (eine Funktion im Kern deutete das Verfahren nach dem Jahr
um). Der Maintainer hat das am selben Tag ersetzt:

> Wir sollten in PLV beides haben. Herabsetzung betrifft NUR Beitraege und
> macht nur Sinn, so lange ein Beitrag bezahlt wird. Eine Teilkuendigung kann
> immer (beitragspflichtig oder ausfinanziert) gemacht werden, hat aber eine
> andere Wirkung — Teil des Deckungskapitals wird ausgezahlt. Das sind im
> Grunde zwei verschiedene Vorgaenge und betreffen alle PLV-Tarife gleich.

## Entscheid

1. **Beitragsherabsetzung (`RED`).** Der Beitrag sinkt auf den Anteil $f$,
   der freiwerdende Teil wird in beitragsfreie Summe umgewandelt
   (`prospektiv` oder `mit_abzug`); es fliesst kein Geld. Nur waehrend der
   Beitragszahlung ($0 < a_0 < t$) und ohne Beitragsfreistellung. Danach
   verweigern Kern, Datenmodell und Bindung benannt, mit dem Ausweg
   "Teilkuendigung".
2. **Teilkuendigung (`TKU`).** Der Anteil $(1-f)$ der Grundversicherung wird
   gekuendigt und mit seinem Rueckkaufswert nach dem Tarifwerk der Generation
   (mit Stornoabzug) ausgezahlt; der Vertrag laeuft mit $f \cdot S$
   zustandslos weiter. In jeder Generation, beitragspflichtig wie
   ausfinanziert ($0 < a_0 < n$). Eigener Ledger-Code, eigene Rate
   (`annahmen.teilkuendigung`), eigener Anteil (`annahmen.tk_anteil`),
   eigener Zufallsstrom (`bestand.zufallsstroeme`, `teilkuendigung`).
3. **Das Ledger sagt, was geschah.** Eine Teilkuendigung ist nie als `RED`
   gebucht. Beide Vorgaenge stehen in derselben Tabelle `reduktionen`
   (eine Zeile je Vertrag); ihr Verfahren bestimmt den Code
   (`models.bestand.reduktion_ereignis`).

Die Annahmen, unter denen gebaut ist (A1 bis A4), und die verweigerten
Kombinationen stehen im Tarifplan KLV, Abschnitt 7.2.

## Verworfene Alternative

Ein Vorgang mit Verfahrensschalter und stiller Umdeutung (die gebaute
Regel A: eine Herabsetzung nach $t$ wird als Teilkuendigung gerechnet und als
`RED` gebucht). Verworfen, weil es zwei Vorgaenge mit verschiedener Wirkung
sind — der eine senkt den Beitrag ohne Zahlung, der andere zahlt einen Teil
des Deckungskapitals aus —, und das Ledger sagen muss, was geschah; ein
Leser, der `RED` sieht, darf keine Auszahlung vermuten muessen.

## Folgen

* Ein neuer Ereigniscode `TKU` mit den Betragsarten `VS_teilkuendigung`,
  `dDK_absorption`, `RKW_teilkuendigung` und `Kappung_teilkuendigung`; die
  Herabsetzung bucht nur noch `VS_herabsetzung` und `dDK_absorption`.
  Jeder Leser (P-B1, Fuehrungsprobe, Bewegungskonto mit eigener Position
  "Teilkuendigung", Bestandsbericht, Abschluss, Betriebsseite,
  Korrekturschicht) kennt ihn; eine Ratsche ueber die Aufzaehler haelt die
  Menge fest, sodass der naechste neue Code an einer Stelle auffaellt.
* Eigene Generationen ohne Teilkuendigungsrate rechnen bitgleich wie vor
  dem Entscheid (Rate 0 als Vorgabe, Ziehung hinter der Jahresbedingung,
  eigener Strom). Eine Generation mit `red_verfahren = teilkuendigung`
  bucht ihren Herabsetzungswunsch jetzt als `TKU` statt `RED` — gleiche
  Betraege, anderer Code.
* Im Migrationszugang war eine gelieferte Absetzung nach $t$ eine
  Teilkuendigung (Annahme A2). Ein Vertrag, dessen Anfangszustand nicht
  ableitbar ist, wird verweigert statt still zustandslos uebernommen;
  gedeckt ist er nur durch eine registrierte Auskunft, und dann ist er
  Pflichtziehung der Abnahmen (ADR-002, Nachtrag 2026-10-01).
* Versionen: Kern `3.16.0`, Abnahmebericht `GATE_VERSION 7.0.0`,
  Fuehrungsprobe `SCHEMA_VERSION 4`.
