# ADR-021: Belegrollen-Vertrag und Freigabesignatur wohnen in `models` — der Betriebseingang liest, was das Gate liest

**Status:** angenommen am 2026-09-22 (Maintainer), umgesetzt. Anlass war
der Befund T26-03 einer externen Begutachtung (Weg 2, zusammen mit der
Zeichnungsschicht).

## Anlass

Der Gutachter meldete (T26-03): Der Betriebseingang akzeptiert semantisch
ungültige A-M4-Belege. Die Tabellenbindung ließ sich bauen; die
Rollenprüfung nicht — der Pflichtbelegrollen-Vertrag
(``fall.belegrollen``) lag in ``fall``, und die Schichtenkarte lässt
``betrieb -> fall`` und ``betrieb -> gates`` nicht zu. Der Betrieb konnte
nicht fragen, welche Rollen A-M4 im Bestands-Scope verlangt (zehn: die
drei aktuariellen Abnahmen, A-Q1, P-Q3, P-K1, P-B1, Migrationssuite,
Führungsprobe, Abnahmebericht); ein Snapshot mit der einzigen Rolle
``pb1_ledger`` trat ein. Dasselbe für die Freigabesignatur: Signieren
und Prüfen lagen im Gate, der Betrieb konnte nicht prüfen —
``signatur_verifiziert`` stand immer auf False.

## Entscheidung

Drei Mengen mit einer Wahrheit — nicht eine Kante mehr, sondern der
Vertrag am dafür vorgesehenen Ort:

1. **``models.belegrollen``** trägt ``BELEGROLLEN``, ``belegrollen``,
   ``am4_belegrollen``. ``fall`` beherbergte den Vertrag nur und nutzte
   ihn nie; es bleibt ein Blatt (``"fall": set()``). ``SCOPES`` spiegelt
   ``fall.FALL_SCOPES``, eine Ratsche hält beide gleich. Gate und
   Betriebseingang lesen denselben Vertrag; ``p9_semantik_fehler``
   prüft im Betrieb jetzt mit ``erwartete_rollen`` — exakt, nicht ``>=``.
2. **``models.freigabe``** trägt Schlüsselring laden (außerhalb des
   Vertrauensraums, 0600, keine Hardlinks, Längenband), ``freigabe_fuer``
   und ``pruefe_freigabe``. Das Gate delegiert unter seinen alten Namen.
   Der Betriebseingang prüft die Signatur bei der Registrierung
   (``--freigabe-schluessel``), verlangt Schema 7 (Zeichnung mit
   Schlüsselklasse) und schreibt ``signatur_verifiziert`` in den
   Eingang. Ohne Ring wird registriert mit ``False`` als benanntem
   Zustand — und ``lies_uebernahme`` (der Tageslauf) nimmt so einen
   Eingang nicht in die Führung.

Damit hat der Betrieb **zwei unabhängige Zeugen**: den eigenen
Vollständigkeitscheck gegen den Vertrag und das verifizierte Siegel.
Ein Beleg, der nur sich selbst bezeugt, reicht nicht — dieselbe
Hausordnung wie beim Kommutations-Zweitkern und bei T26-11.

## Warum nicht Weg 1 (``betrieb -> fall`` erlauben)

Das Verbot versteckt den Vertrag nicht; es sagt, wo er hingehört. Eine
Kante zum Werkstatt-Modul hätte die Laufzeit an dessen Layout gehängt
und den einen unabhängigen Zeugen nicht geliefert. Das Muster ist das der
P-B1-Engine: Als der Betrieb eine Gate-Prüfung brauchte, wanderte die
Prüfung nach ``bestand.vorbedingungen`` — nicht das Gate in den Betrieb.

## Folgen

* Schichtenkarte: keine neue Kante. ``gates -> models`` und
  ``betrieb -> models`` gab es; ``models`` bekommt zwei Module
  (Knoten ``system/entscheid``).
* Ein bestehender Eingang ohne verifizierte Signatur (z. B. aus einer
  Registrierung ohne Ring, oder aus einem Schema-6-Snapshot) tritt nach
  dem Merge nicht mehr in den Tageslauf ein — mit
  ``python -m rechner_pipeline.betrieb.uebernahme --freigabe-schluessel``
  neu registrieren; ``neuaufsetzen`` reicht den Ring durch.
* Tests: ein Testschlüssel (``tests/freigabe_testschluessel.py``) und eine
  conftest-Naht setzen den Ring für jede Registrierung im Testlauf; die
  Test-Snapshots sind Schema 7 mit allen zehn Rollen und echter Signatur.
  Manipulationslagen, die einen Snapshot nach dem Signieren verändern,
  signieren nach (``ueb_p9_sha``), damit sie weiter die Bindung prüfen.

## Was bewusst nicht in diesem ADR steht

Der Betrieb prüft die Signatur und die Schlüsselklasse des Snapshots,
nicht die Zeichnungsordnung (welcher Schlüssel welche Rolle trägt) —
das bleibt die Prüfung des Gates beim Zeichnen; das Siegel bürgt
transitiv dafür. Sie auch im Betrieb zu prüfen hieße, die Ordnung als
drittes Artefakt an die Laufzeit zu reichen — eine eigene Entscheidung.
