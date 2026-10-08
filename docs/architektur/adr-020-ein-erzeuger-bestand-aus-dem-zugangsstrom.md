# ADR-020: Der Bestand entsteht aus dem Zugangsstrom — kein gezogener Anfangsbestand

**Status:** angenommen am 2026-09-21 (Maintainer), umgesetzt.

## Kontext

Ein externer Gutachter ist im Dokument zur Bestandserzeugung an der Stelle
ausgestiegen, die den „Batch“ erklären sollte. Beim Nachlesen im Code
stellte sich heraus, dass es nicht nur die Erklärung war: Die Codebasis
kannte drei Erzeuger für eigenes Geschäft, und der Code selbst
widersprach sich im Vokabular (``generate()`` nannte den Batch eine
„Auswertung des Zugangs-Stroms“, der Nummernkreis-Kommentar dreißig
Zeilen tiefer führte Batch und Zugangsstrom als zwei Dinge).

| Erzeuger | Seed-Familie | Buchung | Nutzer |
|---|---|---|---|
| Batch (``generate``, ``sample_size``) | ``[seed, kreis-1]`` | keine | Tageslauf (Grenztag), ``cli_fortschreibung`` ohne ``--portfolio`` |
| Jährlicher Neuzugang (``neuzugaenge``) | ``[seed, 771177, kreis-1, jahr]`` | ``ZUG`` | Prüfstrecke des Migrationsfalls |
| Tagesneugeschäft (``betrieb.neugeschaeft``) | ``[seed, NEUGESCHAEFT_STREAM, name, tag]`` | ``ZUG`` | Vorzeige |

Der Batch war der einzige ohne Buchung: ein auf einmal gezogener Bestand,
der zum Stichtag „einfach da“ ist. Das Bewegungskonto kann ihn nicht
erklären, das Journal kennt ihn nicht. In einem System, dessen Zweck
Nachrechenbarkeit ist, ist ein Zustand ohne Geschichte ein Fremdkörper.

## Messung, nicht Schätzung

Bevor etwas entfernt wurde, ist gemessen worden, was der Batch tatsächlich
beiträgt (Stand 3bc7d25, 2026-09-21):

**Vorzeige** (lokaler Lauf ``runs/plv-stand-20``, nicht im Repository): 4169 Verträge, 7494 ``ZUG``-Buchungen.
Verträge ohne ``ZUG``: **genau fünf** — die KLV-1994 mit Beginn am
1994-07-01, dem Betriebsbeginn. Der Tagesgenerator verkauft ab dem
Betriebsbeginn selbst (Fenster einschließlich), mit Beginn am folgenden
Monatsersten; der Batch lieferte nur die Verträge des Grenztages.

**Prüfstrecke des Migrationsfalls** (lokaler Fall
``faelle/baldrian-klv-tg2015-lauf2/abgeleitet/bestand-nach``, nicht im
Repository): 3093 Verträge = 834 übernommen + 2259 eigenes
Geschäft, davon **2220 ohne ``ZUG``** — der Batch. Keiner dieser 2220
steht im Vorzeige-Stand (Policennummern verglichen); sie existierten nur im
Fallverzeichnis, als Kulisse für die Führungsprobe.

**Die Probe:** eine Kopie des Falls, alle ``sample_size`` auf 0, die ganze
Prüfstrecke auf demselben Stand neu gefahren:

| Schritt | mit Batch | ohne Batch |
|---|---|---|
| Fortschreibung | 3054 Basisverträge, 39 Neuzugänge | 834 Basisverträge, 39 Neuzugänge |
| P-B1 (Fortschreibung) | exit 0 | exit 0 |
| Führungsprobe | 834 Verträge, 42 Buchungen, 0 Befunde | identisch |
| Migrationssuite | 834/834, vollständig | 834/834, vollständig |
| A-M4 | passed, 0 Hindernisse | passed, 0 Hindernisse |

Die Führungsprobe prüft die 834 übernommenen Verträge; die 2220 waren
für sie Kulisse. Kein Gate hängt an ihnen.

## Entscheidung

Der Batch-Erzeuger wird ersatzlos entfernt: ``generate()``,
``_generate_generation()``, ``_draw_insurance_start()`` und das
Config-Feld ``sample_size``. Der Bestand eines Laufs entsteht
ausschließlich aus dem Zugangsstrom — jeder Vertrag mit seinem Zugang im
Journal.

* ``betrieb.tageslauf`` beginnt leer; das eigene Geschäft entsteht
  Werktag für Werktag ab ``betriebsbeginn``. Die fünf Grenztag-Verträge
  der PLV entfallen; der erste Verkaufstag ist der Betriebsbeginn, der
  erste Versicherungsbeginn der Monatserste danach.
* ``bestand.cli_fortschreibung`` beginnt ohne ``--portfolio`` leer. Was
  es führt, kommt aus ``--uebernahme`` und/oder dem Zugangsstrom ab
  ``--neuzugang-ab``. Ein Lauf ohne jede der drei Quellen hat nichts zu
  führen und sagt das (Exit 2) — statt still einen Bestand zu erfinden.
* Eine Config, die ``sample_size`` noch trägt, wird abgewiesen, nicht
  still anders gelesen: Der Schlüssel hatte eine Bedeutung, die es nicht
  mehr gibt.
* ``--neuzugang-ab`` ist der erste Tag des Stroms, einschließlich
  (``[von, bis]``). Das halboffene Intervall ``(von, bis]`` hatte seinen
  Grund im Batch: ``neuzugang_ab`` war der Referenzstichtag, bis zu dem
  der Batch besiedelte, der Strom setzte danach ein. Ohne Batch ist die
  Grenze eine Untergrenze, und die schließt ihren Tag ein — wie beim
  Tagesneugeschäft (``neugeschaeft_zwischen``, ``[von, bis]``).
* Die Nummernkreise bleiben: 1..1 Mio je Generation bleibt frei (dort
  lagen die Batch-Nummern), damit bestehende Läufe und Belege ihre
  Policennummern behalten.

## Folgen

* Jeder Vorzeige-Stand ändert sich (fünf Verträge weniger, andere
  Hashes). Ein Neuaufsetzen der Vorzeige ist ohnehin der Weg, einen
  Stand neu zu bauen (Fachkonzept Tagesbetrieb, 8.5).
* Die Prüfstrecke des Migrationsfalls führt kein Kunst-Geschäft mehr;
  ``bestand-nach`` trägt die übernommenen Verträge plus den
  Neuzugang ab Stichtag. Der Fall ist auf dem neuen Stand neu zu fahren
  und neu zu zeichnen (A-M4 bindet ``bestand-nach``).
* Das Dokument zur Bestandserzeugung
  (``docs/simulation/bestandserzeugung.md``) hat seinen Abschnitt über die
  zwei Fehllesarten verloren: Es gibt keinen Batch mehr, der eine
  Fehllesart ermöglichen könnte.
* Die Testsuite baute ihre synthetischen Bestände in 17 Modulen über
  ``generate()``. Sie bauen sie jetzt über den Zugangsstrom
  (``neuzugaenge``) — dieselbe Attributziehung, aber jeder Vertrag mit
  Beginn aus seinem Jahrgang statt gleichverteilt über das Fenster.
  Erwartungswerte, die an der alten Ziehung hingen, sind neu abgeleitet.

## Was bewusst nicht in diesem ADR steht

Es gibt weiterhin zwei Erzeuger mit Geschichte: den jährlichen
Zugangsstrom (``neuzugaenge``, Beginn gleichverteilt über die Monatsersten
eines Jahrgangs) und das Tagesneugeschäft (Werktagsgewichte,
Bernoulli-Rest, Verkaufstag im Nummernkreis). Beide buchen, beide sind
deterministisch, sie unterscheiden sich in der Auflösung. Sie zu einem
zusammenzuführen — die Prüfstrecke würde dann dieselben Verträge
führen wie die Vorzeige — ist der nächste Schritt derselben Richtung,
aber eine eigene Entscheidung mit eigener Messung: Die Seed-Ströme des
jährlichen Erzeugers stehen in gezeichneten Belegen.

## Verworfene Alternativen

**Den Batch behalten und das Dokument nachbessern.** Das Dokument war
nicht zu knapp, sondern erklärte etwas, das nicht gebraucht wird; eine
bessere Erklärung hätte den Batch nicht überflüssig gemacht.

**Die fünf Grenztag-Verträge über eine Sonderregel des
Tagesgenerators erhalten** (Beginn am Betriebsbeginn selbst statt am
Folgemonatsersten). Eine Sonderregel für einen Tag, um fünf Verträge
zu retten, an denen nichts hängt — das ist die Komplexität, die dieses
ADR entfernt.

**``sample_size`` als Test-Helfer behalten.** Ein Feld im produktiven
Datenvertrag, das nur Tests benutzen, ist ein Feld, das produktiv
irgendwann jemand setzt. Tests bauen ihre Bestände über denselben Strom
wie das System.
