# ADR-021: Belegrollen-Vertrag und Freigabesignatur liegen in `models` — der Betriebseingang liest, was das Gate liest

**Status:** angenommen am 2026-09-22 (Maintainer), umgesetzt. Anlass war
der Befund T26-03 einer externen Begutachtung (Weg 2, zusammen mit der
Zeichnungsschicht).

## Kontext

Die Begutachtung meldete: Der Betriebseingang akzeptiert inhaltlich
ungültige A-M4-Belege. Die Bindung der Tabellen ließ sich bauen, die
Prüfung der Rollen nicht. Der Vertrag der Pflichtbelegrollen
(``fall.belegrollen``) lag in ``fall``, und die Schichtenkarte erlaubt
weder ``betrieb -> fall`` noch ``betrieb -> gates``. Der Betrieb konnte
also nicht fragen, welche Rollen A-M4 im Bestands-Scope verlangt (damals
zehn: die drei aktuariellen Abnahmen, A-Q1, P-Q3, P-K1, P-B1,
Migrationssuite, Führungsprobe, Abnahmebericht; heute dreizehn, siehe
`models/belegrollen.py`), und ein Snapshot mit der einzigen Rolle
``pb1_ledger`` trat ein. Ebenso die Freigabesignatur: Signieren und Prüfen
lagen im Gate, der Betrieb konnte nicht prüfen, und
``signatur_verifiziert`` stand immer auf False.

## Entscheidung

Belegrollen und Freigabesignatur ziehen nach `models`, das Gate und
Betrieb beide importieren dürfen. Es entsteht keine neue Kante zwischen
Schichten.

1. **``models.belegrollen``** trägt ``BELEGROLLEN``, ``belegrollen`` und
   ``am4_belegrollen``. ``fall`` hatte den Vertrag nur beherbergt und nie
   benutzt; es bleibt ein Blatt (``"fall": set()``). ``SCOPES`` spiegelt
   ``fall.FALL_SCOPES``, ein Test hält beide gleich. Gate und
   Betriebseingang lesen denselben Vertrag; ``p9_semantik_fehler`` prüft
   im Betrieb mit ``erwartete_rollen``, und zwar auf Gleichheit, nicht mit
   ``>=``.
2. **``models.freigabe``** lädt den Schlüsselring (außerhalb von Fall und
   Ablage, Modus 0600, keine weiteren Hardlinks, Länge in festen Grenzen) und trägt
   ``freigabe_fuer`` und ``pruefe_freigabe``. Das Gate delegiert unter
   seinen alten Namen. Der Betriebseingang prüft die Signatur bei der
   Registrierung (``--freigabe-schluessel``), verlangt Schema 7
   (Zeichnung mit Schlüsselklasse; heute das jeweils aktuelle Schema,
   ADR-026) und schreibt ``signatur_verifiziert``
   in den Eingang. Ohne Ring wird mit ``False`` registriert, als benannter
   Zustand, und ``lies_uebernahme`` (der Tageslauf) nimmt einen solchen
   Eingang nicht in die Führung.

Der Betrieb prüft damit zweierlei unabhängig voneinander: die
Vollständigkeit der Belege gegen den Vertrag und die Signatur. Ein Beleg,
der nur sich selbst bezeugt, reicht nicht.

## Warum nicht Weg 1 (``betrieb -> fall`` erlauben)

Das Verbot versteckt den Vertrag nicht, es sagt, wo er hingehört. Eine
Kante zu `fall` hätte die Laufzeit an dessen Aufbau gebunden und die
unabhängige Prüfung trotzdem nicht geliefert. Dasselbe Muster gab es schon
bei der P-B1-Engine: Als der Betrieb eine Prüfung des Gates brauchte,
wanderte die Prüfung nach ``bestand.vorbedingungen``, nicht das Gate in den
Betrieb.

## Folgen

* Schichtenkarte: keine neue Kante. ``gates -> models`` und
  ``betrieb -> models`` gab es schon; ``models`` bekommt zwei Module
  (Knoten ``system/entscheid``).
* Ein bestehender Eingang ohne verifizierte Signatur (etwa aus einer
  Registrierung ohne Ring oder aus einem Snapshot nach Schema 6) tritt
  nicht mehr in den Tageslauf ein. Ausweg: mit
  ``python -m rechner_pipeline.betrieb.uebernahme --freigabe-schluessel``
  neu registrieren; ``neuaufsetzen`` reicht den Ring durch.
* Tests: Ein Testschlüssel (``tests/freigabe_testschluessel.py``) und eine
  Naht in ``conftest`` setzen den Ring für jede Registrierung im Testlauf;
  die Snapshots der Tests sind Schema 7 mit allen zehn Rollen und echter
  Signatur. Tests, die einen Snapshot nach dem Signieren verändern,
  signieren ihn neu (``ueb_p9_sha``), damit sie weiter die Bindung prüfen.

## Was dieses ADR nicht regelt

Der Betrieb prüfte hier Signatur und Schlüsselklasse des Snapshots, nicht
die Zeichnungsordnung, also welcher Schlüssel welche Rolle trägt. Das hat
ADR-022 nachgezogen (Nachtrag „eine Rollenregel für jede Abnahme, auf der
etwas gründet“): Seitdem hält auch der Betrieb die zeichnende Rolle gegen
seine Ordnung.
