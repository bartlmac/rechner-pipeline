# ADR-014: Bestandszugang getrennt vom Vertragsbeginn

**Status:** angenommen am 2026-08-31 (Maintainer), umgesetzt.

## Kontext

Der Bestandsbericht führte den übernommenen Baldrian-Bestand ab 2015 in
den Büchern der Pfefferminzia. Am Fall gemessen: zu jedem Stichtag ab
2015 standen dort alle 500 Verträge mit 38,46 Mio Euro
Versicherungssumme — elf Jahre bevor die Übernahme stattfand. Das
Jahresraster des Berichts begann 2015-01-01, der Migrationsstichtag ist
2026-01-01.

Die Ursache ist kein Rechenfehler, sondern eine fehlende
Unterscheidung. Der Stamm kannte genau ein Anfangsdatum,
`insurance_start`. Das ist der **Vertragsbeginn**, und er ist bei einem
übernommenen Vertrag korrekt 2015: Der Vertrag wurde damals
geschlossen, die Thiele-Rekursion zählt ab dort, das Eintrittsalter
bezieht sich darauf. Was nirgends stand, ist der **Bestandszugang** —
wann der Vertrag in diese Bücher kam. Beim eigenen Geschäft fallen
beide zusammen; bei übernommenem liegen elf Jahre dazwischen, in denen
der Vertrag beim abgebenden Unternehmen stand.

Solange es nur eigenes Geschäft gab, war die Gleichsetzung richtig und
unsichtbar. Mit dem ersten Migrationsfall wurde sie zu einer Aussage
über einen Bestand, den es hier nie gab.

Eine Teilkorrektur war vorausgegangen: Die ZUG-Buchung im Ledger wurde
auf den Migrationsstichtag gelegt und die historischen PEX-Ledgerzeilen
entfernt. Sie erreichte die Bewertung nicht, weil diese den Stamm liest
und nicht das Ledger. Zwei Ableitungen desselben Sachverhalts aus
verschiedenen Quellen — genau die Drift, die ADR-011 an anderer Stelle
beseitigt hat.

## Entscheidung

Der Stamm führt eine eigene Spalte `bestandszugang`
(`models/bestand.py`, `STAMM_SPALTEN`).

* **Eigenes Geschäft**: `bestandszugang == insurance_start`. Der
  Generator setzt sie, für Ursprungsbestand und simulierten Neuzugang
  gleichermaßen.
* **Übernommenes Geschäft**: `bestandszugang` ist der
  Migrationsstichtag. `gates/bestand_uebernehmen` setzt ihn.
* **Invarianten** (`validate_portfolio`, damit Gate P-B1):
  `insurance_start <= bestandszugang < insurance_end`, Monatserster,
  kein NaT. Vor dem Vertragsbeginn gibt es nichts zu übernehmen, nach
  dem Ablauf nichts mehr.

Wer liest was:

| Größe | Datum | Warum |
|---|---|---|
| Auskunfts-Schnitt (`schnitt_am`) | `bestandszugang` | Ein Vertrag, den wir noch nicht hatten, ist nicht in unserem Bestand |
| Jahresraster des Berichts | `bestandszugang` | Die Reihe beginnt, wo der Bestand beginnt |
| Bewegungskonto, Zugangsposten | `bestandszugang` | Der Zugang ist die Übernahme, nicht der Abschluss |
| Ereignis-Sicht (`ledger_mit_bestandszugang`) | `bestandszugang` | Dieselbe Spalte wie das Bewegungskonto, sonst zwei Zugangsjahre |
| `months_exp`, PEX-Jahr, Vertragsjahre | `insurance_start` | Die Rekursion rechnet den Vertrag, nicht die Zugehörigkeit |
| Berichtskopf, Zeitraum | beide | Fallen sie auseinander, sagt die Zeile es — daran erkennt der Leser das übernommene Geschäft |

## Alternativen

**Zugangsdatum an der Tarifgeneration** (`zugang_ab` in der
Bestand-Config). Billiger, ohne Schemabruch. Verworfen: Der Zugang ist
eine Eigenschaft des Vertrags, nicht des Tarifs — eine Generation kann in
mehreren Tranchen übernommen werden, und der Bericht bräuchte die
Config auch für die Strukturansichten, wo sie heute optional ist.

**Aus dem ZUG-Ereignis ableiten.** Der Ledger führt die Zugangsbuchung
bereits richtig. Verworfen: Die Grundsicht des Berichts hängt dann am
Ledger, der dort optional ist — ein Bericht ohne Ledger fällt still auf
den falschen Zeitraum zurück. Außerdem ist es dieselbe
Zwei-Quellen-Ableitung, die den Fehler erzeugt hat.

**Nebentabelle statt Spalte** (die Bauform von `merkmale.parquet`).
Verworfen, und der Unterschied ist der Punkt: Eine Nebentabelle ist
richtig, wenn die Angabe für die meisten Verträge fehlt, weil `NULL`
dort zweierlei hieße. Der Bestandszugang ist für jeden Vertrag
definiert, das eigene Geschäft eingeschlossen. Eine immer gefüllte
Spalte ist kein Sparse-Fall.

## Folgen

* **Schemabruch.** Bestehende `bestand.parquet` sind schemafremd und
  müssen neu erzeugt werden. Fail-fast statt stiller Vorgabe: Ein
  Altbestand ohne die Spalte still als „Zugang = Beginn“ zu lesen wäre
  für eigenes Geschäft richtig und für migriertes genau der Fehler,
  den dieses ADR behebt.
* **Bestehende Reihen ändern sich nicht**, solange der Bestand eigen
  ist: Dort ist der Zugang der Beginn, und jede Auswertung liefert
  dieselben Zahlen wie zuvor.
* Die Regressionsprobe steht in `tests/test_baldrian_e2e.py`
  (`test_der_uebernommene_bestand_beginnt_am_migrationsstichtag`): vor
  dem Stichtag leer, am Stichtag vollzählig.
