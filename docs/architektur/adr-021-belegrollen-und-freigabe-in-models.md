# ADR-021: Belegrollen-Vertrag und Freigabesignatur wohnen in `models` — der Betriebseingang liest, was das Gate liest

**Status:** angenommen, 2026-09-22
**Entscheidung des Maintainers** (Befund T26-03 des externen Gutachters, Weg 2, gekoppelt mit der Zeichnungsschicht), umgesetzt in der dev-Session.

## Anlass

Der Gutachter meldete (T26-03): Der Betriebseingang akzeptiert semantisch
ungueltige A-M4-Belege. Die Tabellenbindung liess sich bauen; die
Rollenpruefung nicht — der Pflichtbelegrollen-Vertrag
(``fall.belegrollen``) lag in ``fall``, und die Schichtenkarte laesst
``betrieb -> fall`` und ``betrieb -> gates`` nicht zu. Der Betrieb konnte
nicht fragen, welche Rollen A-M4 im Bestands-Scope verlangt (zehn: die
drei aktuariellen Abnahmen, A-Q1, P-Q3, P-K1, P-B1, Migrationssuite,
Fuehrungsprobe, Abnahmebericht); ein Snapshot mit der einzigen Rolle
``pb1_ledger`` trat ein. Dasselbe fuer die Freigabesignatur: Signieren
und Pruefen lagen im Gate, der Betrieb konnte nicht pruefen —
``signatur_verifiziert`` stand immer auf False.

## Entscheidung

Drei Mengen mit einer Wahrheit — nicht eine Kante mehr, sondern der
Vertrag am dafuer vorgesehenen Ort:

1. **``models.belegrollen``** traegt ``BELEGROLLEN``, ``belegrollen``,
   ``am4_belegrollen``. ``fall`` beherbergte den Vertrag nur und nutzte
   ihn nie; es bleibt ein Blatt (``"fall": set()``). ``SCOPES`` spiegelt
   ``fall.FALL_SCOPES``, eine Ratsche haelt beide gleich. Gate und
   Betriebseingang lesen denselben Vertrag; ``p9_semantik_fehler``
   prueft im Betrieb jetzt mit ``erwartete_rollen`` — exakt, nicht ``>=``.
2. **``models.freigabe``** traegt Schluesselring laden (ausserhalb des
   Vertrauensraums, 0600, keine Hardlinks, Laengenband), ``freigabe_fuer``
   und ``pruefe_freigabe``. Das Gate delegiert unter seinen alten Namen.
   Der Betriebseingang prueft die Signatur bei der Registrierung
   (``--freigabe-schluessel``), verlangt Schema 7 (Zeichnung mit
   Schluesselklasse) und schreibt ``signatur_verifiziert`` in den
   Eingang. Ohne Ring wird registriert mit ``False`` als benanntem
   Zustand — und ``lies_uebernahme`` (der Tageslauf) nimmt so einen
   Eingang nicht in die Fuehrung.

Damit hat der Betrieb **zwei unabhaengige Zeugen**: den eigenen
Vollstaendigkeitscheck gegen den Vertrag und das verifizierte Siegel.
Ein Beleg, der nur sich selbst bezeugt, reicht nicht — dieselbe
Hausordnung wie beim Kommutations-Zweitkern und bei T26-11.

## Warum nicht Weg 1 (``betrieb -> fall`` erlauben)

Das Verbot versteckt den Vertrag nicht; es sagt, wo er hingehoert. Eine
Kante zum Werkstatt-Modul haette die Laufzeit an dessen Layout gehaengt
und den einen unabhaengigen Zeugen nicht geliefert. Das Muster ist das der
P-B1-Engine: Als der Betrieb eine Gate-Pruefung brauchte, wanderte die
Pruefung nach ``bestand.vorbedingungen`` — nicht das Gate in den Betrieb.

## Folgen

* Schichtenkarte: keine neue Kante. ``gates -> models`` und
  ``betrieb -> models`` gab es; ``models`` bekommt zwei Module
  (Knoten ``system/entscheid``).
* Ein bestehender Eingang ohne verifizierte Signatur (z. B. aus einer
  Registrierung ohne Ring, oder aus einem Schema-6-Snapshot) tritt nach
  dem Merge nicht mehr in den Tageslauf ein — mit
  ``python -m rechner_pipeline.betrieb.uebernahme --freigabe-schluessel``
  neu registrieren; ``neuaufsetzen`` reicht den Ring durch.
* Tests: ein Testschluessel (``tests/freigabe_testschluessel.py``) und eine
  conftest-Naht setzen den Ring fuer jede Registrierung im Testlauf; die
  Test-Snapshots sind Schema 7 mit allen zehn Rollen und echter Signatur.
  Manipulationslagen, die einen Snapshot NACH dem Signieren veraendern,
  signieren nach (``ueb_p9_sha``), damit sie weiter die Bindung pruefen.

## Was bewusst nicht in diesem ADR steht

Der Betrieb prueft die Signatur und die Schluesselklasse des Snapshots,
NICHT die Zeichnungsordnung (welcher Schluessel welche Rolle traegt) —
das bleibt die Pruefung des Gates beim Zeichnen; das Siegel buergt
transitiv dafuer. Sie auch im Betrieb zu pruefen hiesse, die Ordnung als
drittes Artefakt an die Laufzeit zu reichen — eine eigene Entscheidung.
