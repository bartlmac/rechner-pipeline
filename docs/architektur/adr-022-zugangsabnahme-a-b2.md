# ADR-022: Zugangsabnahme A-B2 — der Betrieb nimmt den Migrationszugang mit einer Zugangsprobe ab

**Status:** angenommen, 2026-09-30 (Entscheid des Maintainers im Dialog);
Bauauftrag offen, Ziel: fliesst in Fall 3 ein.

## Anlass

Die Abnahmen A-Q1 bis A-M4 und die Fuehrungsprobe urteilen im Fall:
Sie belegen, dass der uebernommene Bestand richtig gerechnet ist und dass
Uebernahme und Fortschreibung bis zum Folgestichtag dieselbe Welt
benutzen wie die Pruefstrecke. Was danach geschieht — die Registrierung
des Eingangs in der produktiven Ablage und sein Eintritt in den
Tagesbetrieb — hat bisher keine Abnahme. ``betrieb.uebernahme`` verlangt
den A-M4-Snapshot, prueft Struktur und Signatur, und der Tageslauf fuehrt
den Zugang am Stichtag ein. Ob der Zugang in der produktiven Ablage genau
das bewirkt, was abgenommen wurde, sieht niemand; der erste
Monatsabschluss danach ist die erste Gelegenheit, und dann steht er schon
fest.

Mit dem Betriebsschluessel (ADR-018, Nachtrag 2026-09-30) zeichnet der
Tageslauf Urheberschaft. Eine Abnahme ist etwas anderes: Sie gehoert einer
Rolle, die dafuer einsteht. Die Rollen dafuer gibt es bereits —
``mensch/betrieb`` (zeichnet A-B1) und ``agent/betrieb`` (legt vor,
zeichnet nie) —, sie hatten nur diesen Gegenstand noch nicht.

## Entscheidung

1. **Ein Producer ``betrieb.zugangsprobe``** faehrt auf einer Kopie der
   produktiven Ablage (unter der Lauf-Sperre gezogen; das Original wird
   nie beschrieben), mit dem produktiven Image und der produktiven
   Config, zwei Laeufe vom gefuehrten Tag ueber den Zugangsstichtag bis
   zum naechsten Monatsabschluss, auf Wunsch bis zum naechsten Jahrestag:
   einmal **ohne** den Eingang, einmal **mit** ihm. Beide Laeufe sind
   deterministisch (ADR-020: der Bestand entsteht aus dem gesaeten
   Zugangsstrom), also ist ihre Differenz eine Rechnung, keine Messung mit
   Rauschen.
2. **Die Differenz der beiden Abschluesse ist der Beleg.** Sie muss
   exakt der abgenommene Bestand sein:
   - am Zugangsstichtag: Anzahl in Kraft, Versicherungssumme,
     Deckungskapital und Jahresbeitrag gleich den Werten, die die
     Uebernahme geschrieben und A-M1 gezeichnet hat (``bestand.parquet``
     der Uebernahme, Stichtagswerte des aktuariellen Tests);
   - am Folgetermin: dieselben Groessen gleich dem, was die
     Migrationssuite fuer den Folgestichtag belegt (``dk_stichtag_2`` je
     Vertrag, aggregiert), soweit der Termin gedeckt ist;
   - Bewegungskonto: Anfang + Zugang - Abgang = Ende mit Zugang gleich
     der Anzahl der uebernommenen Vertraege, und keine Buchung, die sich
     zwischen "mit" und "ohne" unterscheidet, ausser den Buchungen der
     uebernommenen Vertraege selbst.
   Der Beleg (``zugangsprobe.json``) bindet: Hash des Ablage-Stands, den
   Eingang (``eingang.json`` mit Betriebszeichnung), den A-M4-Snapshot des
   Falls, Manifest und Journal beider Laeufe, Config und Kern-Version,
   Systemstand; je Groesse Soll, Ist, Differenz.
3. **Ein Gate ``A-B2.zugangsabnahme``** (Namensordnung ADR-012 wie
   ``A-B1.auslieferung``): ``gates.gate_entscheid --gate A-B2`` verlangt
   als Pflichtbelege den Zugangsprobe-Beleg, den A-M4-Snapshot und den
   Eingang; ``agent/betrieb`` bereitet vor und darf nur ablehnen,
   ``mensch/betrieb`` zeichnet; in der Vorfuehrung mit der
   Schluesselklasse ``simulation`` unter Mandat (Regie-Modus), wie bei den
   anderen menschlichen Rollen.
4. **``betrieb.uebernahme`` registriert nur mit angenommenem A-B2**, so
   wie es heute den A-M4 verlangt; der Tageslauf prueft beim Eintritt des
   Eingangs, dass der A-B2-Snapshot denselben Eingang und denselben
   Ablage-Stand bindet, auf dem die Probe lief. Ein Eingang ohne A-B2
   tritt nicht ein.

## Was es kostet, wenn es falsch ist

Die Probe verdoppelt die Fortschreibung ueber wenige Tage bis zu einem
Jahrestag; das sind Minuten, keine Stunden. Ein A-B2, das den falschen
Stand bindet (Probe auf einer Ablage, die danach weiterlief), ist der
Nachbarfall — deshalb bindet der Snapshot den Ablage-Stand, und der
Tageslauf haelt ihn beim Eintritt dagegen. Wer die Probe fuer nutzlos
haelt, weil die Fuehrungsprobe schon geprueft hat: Die Fuehrungsprobe
rechnet im Fall, mit der Config des Falls; die Zugangsprobe rechnet in
der Ablage, mit der Config, dem Bestand und dem Kern, die produktiv
laufen. Der zweite Baldrian-Lauf hat gezeigt, dass beide Welten
auseinanderlaufen koennen (Korrektur 24).

## Bauauftrag

1. ``models.zeichnung.GUELTIGE_GATES`` um ``A-B2``; ``models.belegrollen``
   um die Pflichtbelegrollen von A-B2 (``zugangsprobe``, ``am4_snapshot``,
   ``eingang``); Zeichnungsordnung: ``mensch/betrieb`` bekommt ``A-B2``
   in seine gates-Liste (Ordnung des Maintainers, nicht Code).
2. ``betrieb/zugangsprobe.py``: Kopie der Ablage unter Sperre, zwei
   Laeufe, Differenz, Beleg; CLI ``python -m rechner_pipeline.betrieb.zugangsprobe
   --stand <dir> --fall <fall> --stichtag <iso> [--bis <iso>] --schluessel
   <betriebsschluessel> --zeichnungsordnung <ordnung> --out <beleg>``.
   Der Beleg traegt die Betriebszeichnung (Urheberschaft), nicht die
   Abnahme.
3. ``gates.gate_entscheid``: A-B2 mit Pflichtbelegen und der Bindung an
   Eingang und Ablage-Stand; ``betrieb.uebernahme`` und der Eintritt im
   Tageslauf verlangen den Snapshot.
4. Tests nach dem Muster der drei Instrumente: Ratsche ueber die
   Belegrollen, Zaehltest ueber jede verglichene Groesse (Mutation je
   Groesse: ein Cent im Ledger der "mit"-Kopie -> Probe rot), ein
   adversarialer Angriff auf Probe und Gate vor dem Merge.
5. ``deploy/plv/README.md`` und ``docs/simulation/tagesbetrieb.md``:
   der Zugang hat drei Schritte — Probe, Abnahme A-B2, Registrierung.

## Bezug

ADR-012 (Namensordnung der Gates), ADR-018 (Rollen und
Schluesselklassen, Nachtrag Betriebsschluessel), ADR-020 (Bestand aus dem
Zugangsstrom, Determinismus), ADR-021 (Belegrollen in ``models``);
``gates.fuehrungsprobe`` als Vorbild fuer einen Beleg, den ein Gate
bindet und ein Konsument nachrechnet.
