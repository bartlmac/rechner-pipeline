# ADR-020: Der Bestand entsteht aus dem Zugangsstrom — kein gezogener Anfangsbestand

**Status:** angenommen, 2026-09-21
**Entscheidung des Maintainers**, umgesetzt in der dev-Session.

## Anlass

Ein externer Gutachter ist im Dokument zur Bestandserzeugung an der Stelle
ausgestiegen, die den "Batch" erklaeren sollte. Beim Nachlesen im Code
stellte sich heraus, dass es nicht nur die Erklaerung war: Die Codebasis
kannte DREI Erzeuger fuer eigenes Geschaeft, und der Code selbst
widersprach sich im Vokabular (``generate()`` nannte den Batch eine
"Auswertung des Zugangs-Stroms", der Nummernkreis-Kommentar dreissig
Zeilen tiefer fuehrte Batch und Zugangsstrom als zwei Dinge).

| Erzeuger | Seed-Familie | Buchung | Nutzer |
|---|---|---|---|
| Batch (``generate``, ``sample_size``) | ``[seed, kreis-1]`` | keine | Tageslauf (Grenztag), ``cli_fortschreibung`` ohne ``--portfolio`` |
| Jaehrlicher Neuzugang (``neuzugaenge``) | ``[seed, 771177, kreis-1, jahr]`` | ``ZUG`` | Pruefstrecke des Migrationsfalls |
| Tagesneugeschaeft (``betrieb.neugeschaeft``) | ``[seed, NEUGESCHAEFT_STREAM, name, tag]`` | ``ZUG`` | Vorzeige |

Der Batch war der einzige ohne Buchung: ein auf einmal gezogener Bestand,
der zum Stichtag "einfach da" ist. Das Bewegungskonto kann ihn nicht
erklaeren, das Journal kennt ihn nicht. In einem System, dessen Zweck
Nachrechenbarkeit ist, ist ein Zustand ohne Geschichte ein Fremdkoerper.

## Messung, nicht Schaetzung

Bevor etwas entfernt wurde, ist gemessen worden, was der Batch tatsaechlich
beitraegt (Stand 3bc7d25, 2026-09-21):

**Vorzeige** (``runs/plv-stand-20``): 4169 Vertraege, 7494 ``ZUG``-Buchungen.
Vertraege ohne ``ZUG``: **genau fuenf** — die KLV-1994 mit Beginn am
1994-07-01, dem Betriebsbeginn. Der Tagesgenerator verkauft ab dem
Betriebsbeginn selbst (Fenster einschliesslich), mit Beginn am folgenden
Monatsersten; der Batch lieferte nur die Vertraege des Grenztages.

**Pruefstrecke des Migrationsfalls** (``faelle/baldrian-klv-tg2015-lauf2/
abgeleitet/bestand-nach``): 3093 Vertraege = 834 uebernommen + 2259 eigenes
Geschaeft, davon **2220 ohne ``ZUG``** — der Batch. Keiner dieser 2220
steht im Vorzeige-Stand (Policennummern verglichen); sie existierten nur im
Fallverzeichnis, als Kulisse fuer die Fuehrungsprobe.

**Die Probe:** eine Kopie des Falls, alle ``sample_size`` auf 0, die ganze
Pruefstrecke auf demselben Stand neu gefahren:

| Schritt | mit Batch | ohne Batch |
|---|---|---|
| Fortschreibung | 3054 Basisvertraege, 39 Neuzugaenge | 834 Basisvertraege, 39 Neuzugaenge |
| P-B1 (Fortschreibung) | exit 0 | exit 0 |
| Fuehrungsprobe | 834 Vertraege, 42 Buchungen, 0 Befunde | identisch |
| Migrationssuite | 834/834, vollstaendig | 834/834, vollstaendig |
| A-M4 | passed, 0 Hindernisse | passed, 0 Hindernisse |

Die Fuehrungsprobe prueft die 834 uebernommenen Vertraege; die 2220 waren
fuer sie Kulisse. Kein Gate haengt an ihnen.

## Entscheidung

Der Batch-Erzeuger wird ersatzlos entfernt: ``generate()``,
``_generate_generation()``, ``_draw_insurance_start()`` und das
Config-Feld ``sample_size``. Der Bestand eines Laufs entsteht
ausschliesslich aus dem Zugangsstrom — jeder Vertrag mit seinem Zugang im
Journal.

* ``betrieb.tageslauf`` beginnt leer; das eigene Geschaeft entsteht
  Werktag fuer Werktag ab ``betriebsbeginn``. Die fuenf Grenztag-Vertraege
  der PLV entfallen; der erste Verkaufstag ist der Betriebsbeginn, der
  erste Versicherungsbeginn der Monatserste danach.
* ``bestand.cli_fortschreibung`` beginnt ohne ``--portfolio`` leer. Was
  es fuehrt, kommt aus ``--uebernahme`` und/oder dem Zugangsstrom ab
  ``--neuzugang-ab``. Ein Lauf ohne jede der drei Quellen hat nichts zu
  fuehren und sagt das (Exit 2) — statt still einen Bestand zu erfinden.
* Eine Config, die ``sample_size`` noch traegt, wird ABGEWIESEN, nicht
  still anders gelesen: Der Schluessel hatte eine Bedeutung, die es nicht
  mehr gibt.
* ``--neuzugang-ab`` ist der ERSTE Tag des Stroms, einschliesslich
  (``[von, bis]``). Das halboffene Intervall ``(von, bis]`` hatte seinen
  Grund im Batch: ``neuzugang_ab`` war der Referenzstichtag, bis zu dem
  der Batch besiedelte, der Strom setzte DANACH ein. Ohne Batch ist die
  Grenze eine Untergrenze, und die schliesst ihren Tag ein — wie beim
  Tagesneugeschaeft (``neugeschaeft_zwischen``, ``[von, bis]``).
* Die Nummernkreise bleiben: 1..1 Mio je Generation bleibt frei (dort
  lagen die Batch-Nummern), damit bestehende Laeufe und Belege ihre
  Policennummern behalten.

## Folgen

* Jeder Vorzeige-Stand aendert sich (fuenf Vertraege weniger, andere
  Hashes). Ein Neuaufsetzen der Vorzeige ist ohnehin der Weg, einen
  Stand neu zu bauen (Fachkonzept Tagesbetrieb, 8.5).
* Die Pruefstrecke des Migrationsfalls fuehrt kein Kunst-Geschaeft mehr;
  ``bestand-nach`` traegt die uebernommenen Vertraege plus den
  Neuzugang ab Stichtag. Der Fall ist auf dem neuen Stand neu zu fahren
  und neu zu zeichnen (A-M4 bindet ``bestand-nach``).
* Das Dokument zur Bestandserzeugung (``docs/simulation/
  bestandserzeugung.md``, Zweig ``doku/bestandssimulation``) verliert
  seinen Abschnitt 3 ("die zwei Fehllesarten"): Es gibt keinen Batch
  mehr, der eine Fehllesart ermoeglichen koennte.
* Die Testsuite baute ihre synthetischen Bestaende in 17 Modulen ueber
  ``generate()``. Sie bauen sie jetzt ueber den Zugangsstrom
  (``neuzugaenge``) — dieselbe Attributziehung, aber jeder Vertrag mit
  Beginn aus seinem Jahrgang statt gleichverteilt ueber das Fenster.
  Erwartungswerte, die an der alten Ziehung hingen, sind neu abgeleitet.

## Was bewusst NICHT in diesem ADR steht

Es gibt weiterhin ZWEI Erzeuger mit Geschichte: den jaehrlichen
Zugangsstrom (``neuzugaenge``, Beginn gleichverteilt ueber die Monatsersten
eines Jahrgangs) und das Tagesneugeschaeft (Werktagsgewichte,
Bernoulli-Rest, Verkaufstag im Nummernkreis). Beide buchen, beide sind
deterministisch, sie unterscheiden sich in der Aufloesung. Sie zu einem
zusammenzufuehren — die Pruefstrecke wuerde dann dieselben Vertraege
fuehren wie die Vorzeige — ist der naechste Schritt derselben Richtung,
aber eine eigene Entscheidung mit eigener Messung: Die Seed-Stroeme des
jaehrlichen Erzeugers stehen in gezeichneten Belegen.

## Verworfene Alternativen

**Den Batch behalten und das Dokument nachbessern.** Das Dokument war
nicht zu knapp, sondern erklaerte etwas, das nicht gebraucht wird. Eine
bessere Erklaerung eines Fremdkoerpers macht ihn nicht weniger fremd.

**Die fuenf Grenztag-Vertraege ueber eine Sonderregel des
Tagesgenerators erhalten** (Beginn am Betriebsbeginn selbst statt am
Folgemonatsersten). Eine Sonderregel fuer einen Tag, um fuenf Vertraege
zu retten, an denen nichts haengt — das ist die Komplexitaet, die dieses
ADR entfernt.

**``sample_size`` als Test-Helfer behalten.** Ein Feld im produktiven
Datenvertrag, das nur Tests benutzen, ist ein Feld, das produktiv
irgendwann jemand setzt. Tests bauen ihre Bestaende ueber denselben Strom
wie das System.
