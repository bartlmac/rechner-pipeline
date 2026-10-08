# Bestandsmigrationen

Für Gesellschaften, die einen Lebensversicherungsbestand abgeben: wie
eine Übernahme bei uns abläuft, was Sie liefern und was Sie
zurückerhalten.

Woran sich eine Übernahme messen lassen muss, steht nicht in unserem
Ermessen — den Maßstab setzen Aufsichtsrecht und Marktpraxis. Er ist
unter [Woran sich eine Bestandsübernahme messen lassen muss](massstab.html)
zusammengefasst. Diese Seite sagt, wie wir ihn erfüllen.

## Der Prozess in dreizehn Stationen {: #prozess }

Den Fall führt die Programmleitung, ein KI-Agent, von der Lieferung bis
zum Zugang. Sie verteilt die Arbeit an die anderen Agentenrollen und
hält an jeder Abnahme an, um dem zuständigen Menschen die Entscheidung
vorzulegen — [wer vorlegt, wer zeichnet](ki.html#rollen).

Von oben nach unten: Auftrag und Lieferung, dann Quellenanalyse,
Transformation und aktuarielle Abnahmen, zuletzt der Zugang in die
Bücher. Gelb sind die Stationen, an denen ein Mensch abnimmt und mit
Schlüssel zeichnet (A), grün die, an denen nur das Programm prüft (P) —
deterministisch, bestanden oder nicht bestanden —, grau die Station
ohne eigenes Gate. In jedem Kasten steht, welche Agentenrolle vorlegt
(farbiges Kürzel) und wer zeichnet (weiße Marke); die Leiste darunter
löst die Kürzel auf.

<div class="schaubild">{{html:prozess_stationen}}</div>

Die unterstrichenen Zeilen in den Kästen führen zu den Belegen der
Übernahme Baldrian, an der wir es zeigen; der Kasten selbst führt zu [der
Station der Übernahme](baldrian/), an der alle Belege zusammenstehen.
„In Arbeit" heißt: Diesen Beleg führt der Lauf noch nicht. Auf dem
Telefon lässt sich das Schaubild seitwärts verschieben.

Der Prozess ist nicht nur Weg, sondern auch Nachweis: Die
Abschlussabnahme A-M4 bindet die Belege aller vorangehenden Stationen
auf demselben Stand — fehlt einer, ist sie nicht zeichenbar. Sie
verlangt außerdem, dass der Stand abgenommen ist, auf dem der Fall
rechnet: der Rechenkern (A-K2), das Tarifwerk (A-T1) und das
Begriffsmodell (A-O1), jeweils im Fall abgenommen oder per Verweis auf
eine frühere Abnahme. Welcher Weg es bei der Übernahme Baldrian war, steht an
[Station 7](baldrian/#rechenkern-gegen-quellrechner) wörtlich so, wie
der Entscheid es festhält.

## So läuft eine Übernahme ab {: #ablauf }

1. **Auftrag, Lieferung und Registrierung.** Unser Vorstand beauftragt
   die Übernahme. Sie übergeben Bestandsabzug, Tarifbeschreibung und
   Tarifrechner; jede Datei wird mit Prüfsumme registriert, einen
   impliziten Eingangskanal gibt es nicht.
2. **Übersetzung.** Tarifparameter und Feldabbildung werden aus Ihren
   Unterlagen extrahiert, jeder Wert mit Fundstelle. Widersprechen sich
   Ihre Unterlagen, wird das festgehalten und von unserem Aktuariat
   entschieden, nicht stillschweigend aufgelöst.
3. **Nachrechnung.** Unser Rechenkern rechnet Ihren Bestand nach: gegen
   Ihren Tarifrechner, je Vertrag am Stichtag, über den Verlauf und je
   Geschäftsvorfall, dann der ganze Bestand über zwei Stichtage.
4. **Abnahmen.** Vier Abnahmen unseres Aktuariats, jede signiert und an
   die geprüften Belege gebunden; zuletzt das Migrationscontrolling, das
   alle Belege noch einmal auf demselben Stand prüft.
5. **Zugang in die Bücher.** Vor dem Zugang fährt eine Zugangsprobe den
   Tagesbetrieb auf einer Kopie unserer Ablage, mit und ohne Ihren
   Bestand; erst dann nimmt unsere Betriebsverantwortung den Zugang ab.
   Ihr Bestand tritt zum Stichtag in unseren geführten Bestand ein und
   wird ab dann wie eigenes Geschäft fortgeschrieben.

Technisch sind das drei Stufen: von Ihren Quellen zur Faktenbasis, von
der Faktenbasis zur Spezifikation und Parametrierung des Rechenkerns,
dann die Abnahme. Zwischen den Stufen sitzen Gates: Sie prüfen
deterministisch und blockieren bei Rot, oder sie bereiten den
menschlichen Entscheid auf. Die einzelnen Gates stehen unter
[Prüfgates](pruefgates.html), den Ablauf zeigt das
[Schaubild oben](#prozess).

**Was Sie liefern:** Bestandsabzug zu zwei Stichtagen, Tarifbeschreibung,
Tarifrechner, Erwartungswerte für die Nachrechnung; auf Nachfrage
Auskünfte zu Unklarheiten.
**Was Sie erhalten:** die Dokumentation jeder Prüfung und jedes
Entscheids, den Abschlussbericht des Aktuariats, die Belege mit
Prüfsummen.

## Die aktuariellen Abnahmen {: #abnahmen }

Jede Übernahme durchläuft vier Abnahmen des Aktuariats; keine kann eine
andere ersetzen. Kein Agent nimmt etwas ab.

| Abnahme | Was geprüft wird |
|---|---|
| A-M1 Stichtagstest | je Vertrag am eigenen Verankerungszeitpunkt, auf einer geschichteten Stichprobe |
| A-M2 Verlaufstest | die Deckungsrückstellung über die Laufzeit gegen die Referenz |
| A-M3 Geschäftsvorfalltest | jeder Geschäftsvorfall an der Änderung des Deckungskapitals, als Vollerhebung |
| A-M4 Migrationscontrolling | der ganze Bestand über zwei Stichtage; bindet die Belege aller vorangehenden Abnahmen |

Die Toleranzen sind Cent-Schranken auf den Vertragswert; ein Wert, der
nicht nachgerechnet werden kann, ist eine ausgewiesene Prüflücke. Die
Ergebnisse jeder Abnahme mit Verteilung der Abweichungen, Stichprobe und
Bericht stehen unter [Das Ergebnis der Übernahme](baldrian/#das-ergebnis).

## Widersprüche und Entscheide {: #widersprueche }

Widersprechen sich Tarifbeschreibung und Tarifrechner der abgebenden
Gesellschaft, wird das je Tarifzelle festgehalten und vom Aktuariat
entschieden — mit beiden Lesarten, Quelle und Begründung
([Der Widerspruch](baldrian/#der-widerspruch)).

## Kontrollen und Schranken {: #kontrollen }

* **Menschliche Entscheide, signiert.** Kein Agent nimmt etwas ab. Jede
  Abnahme ist ein Entscheid unseres Aktuariats, an die Prüfsummen genau
  der Belege gebunden, auf denen entschieden wurde.
* **Umbaubudget.** Wer eine Übernahme bearbeitet, darf unser System
  erweitern, nicht nebenbei ersetzen. Der Umfang jeder Änderung wird
  gemessen; Überschreiten ist erlaubt, Verschweigen nicht.
* **Prüfung ohne Glättung.** Ein Wert, der nicht nachgerechnet werden
  kann, ist eine ausgewiesene Prüflücke, kein geschätzter Ersatz. Eine
  Übernahme mit Befund wird genauso dargestellt wie eine ohne.
