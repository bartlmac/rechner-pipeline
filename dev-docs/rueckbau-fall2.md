# Rückbau des zweiten Baldrian-Laufs (vor Fall 3)

Fall 3 ist die Neufassung der Übernahme des Bestands KLV TG2015. Damit er
zeigt, was eine Übernahme am Zielsystem verändert, steht das Zielsystem auf
diesem Zweig so da, als hätte es den übernommenen Tarif nie gerechnet. Der
Rückbau ist EIN Commit auf dem heutigen Stand, kein Zurücksetzen der
Historie: Alles, was seit dem Lauf vom September gebaut und repariert wurde,
bleibt. Auftrag und Zuschnitt: Maintainer, 2026-10-01.

## Dieser Stand ist die Basis; nach main kommt er nur zusammen mit dem Fall

Berichtigt am 2026-10-02 (Entscheid des Maintainers). Die erste Fassung
dieses Abschnitts sagte, der Zweig werde nie nach main gemergt, weil main das
System sei, das die Übernahme geleistet HAT. Das behandelte die Historie der
PLV als Aufzeichnung. Sie ist eine Erzählung: Die PLV ist ein fiktives
Unternehmen, und ihre Geschichte wird mit jeder Verbesserung des Systems neu
geschrieben. Eine alte Migration auf main, die sich dort nicht zurückbauen
lässt, ist nicht der gewollte Zustand.

Das Zielbild:

- Es gibt einen stabilen Stand „PLV ohne Migrationen“: die Lieferungen und die
  allgemeinen Fähigkeiten des Systems, aber kein Code einer Migration. Dieser
  Zweig ist seine erste Fassung.
- Für einen Fall wird aus diesem Stand eine eigene Laufzeit neben der
  produktiven aufgestellt, die den übernommenen Bestand nicht kennt. In ihr
  läuft die Migration, mit Prüfungen, Abnahmen und Zugang.
- Erst danach kommt der Merge nach main: der Code des Falls samt neuer
  allgemeiner und fallspezifischer Tests, und die neue Laufzeit löst die
  produktive ab. Der Rückbau kommt nie allein nach main; main ohne den Fall
  rechnete Verträge nicht mehr, die in der produktiven Laufzeit registriert
  sind.
- Ein besserer Fall wiederholt den Weg. Eine weitere Tranche kann auf dem
  aktuellen Stand starten, oder eine frühere wird zurückgerollt und beide
  laufen nacheinander.

Gebaut ist davon dieser Stand. Die zweite Laufzeit und die Ablösung sind
nicht gebaut und nicht gefahren.

## Was zurückgebaut ist

| Gegenstand | vorher | auf diesem Stand |
|---|---|---|
| Beitragsformel je Erhöhungsbaustein (`scheiben_mit_gamma1 = true`, Kern 3.2.0) | die Scheibe trägt gamma1 | verweigert |
| Stornoabzug je Baustein (`stoab_je_baustein = true`, Kern 3.3.0 und Folgen in Vorgangsfolge und Herabsetzung) | Abzug und Rückkaufswert je Baustein | verweigert |
| Teilkündigung nur der Grundversicherung (`tku_umfang = grundversicherung`, Kern 3.17.0) | die Scheiben bleiben | verweigert |
| sechs Tafeln aus dem Tarifrechner der Quelle (`DAV2008_T_NR_F/M/U70`, `DAV2008_T_R_F/M/U70`) | in `kern/tafeln.xml` | entfernt (762 Zeilen) |
| Generation TG2015 in `configs/bestand_gesamt.toml` | 14 Generationen | 13 Generationen |

Gemessen an der Config vor dem Rückbau führte NUR die Generation TG2015
diese Regelwerte; die 13 eigenen Generationen tragen den jeweils anderen
Wert. Für sie ändert sich kein Rechenwert, und kein
Charakterisierungs-Referenzwert des Kerns bewegt sich. Kern 3.21.0.

„Verweigert“ heißt: Die Regeln bleiben im Vokabular (T-Box, Spez) und in den
Signaturen. Eine Spez darf sie belegen. Erreicht ein solcher Wert den Kern,
endet die Rechnung mit `KernFaehigkeitFehlt` und der Meldung

    Tarifregel <regel> = <wert>: Der Kern rechnet diese Ausgestaltung nicht —
    keine Tarifgeneration des Zielsystems fuehrt sie. Ausweg: eine
    Kern-Erweiterung mit Entwicklermandat, abgenommen unter A-K2
    (mensch/rechenkern)

statt nach der Regel des eigenen Geschäfts zu rechnen. Das ist die Stelle,
an der Fall 3 anhält. Verworfen: die Regeln ganz aus Vokabular und Signaturen
zu nehmen — das zöge durch Bestand, Prüfstrecken, Gates und Spez, und die
Rückkehr wäre kein überschaubarer Schritt mehr.

## Was bleibt

- Die Teilkündigung als Vorgang des eigenen Geschäfts (alle Bausteine).
- Was die Migration am Werkzeug gelehrt hat: Korrekturschicht, Verankerung,
  Serien-Rekonstruktion, Prüfstrecken, Zeichnungsordnung, Gates.
- Der Fall-Arbeitsbereich des zweiten Laufs und seine Lieferung
  (`migrationen/baldrian/lieferungen/baldrian-2`): Sie sind die Quelle von Fall 3.
- Die Dokumente des Laufs (`migrationen/baldrian/berichte/baldrian-lauf2*.md`, `migrationen/baldrian/baldrian-lauf2-wiederholen.md`) und der
  Tarifplan: Sie sind NICHT zurückgebaut und beschreiben weiter, was der
  übernommene Tarif verlangt.
- In `bestand/` die Zuordnung "ein Tarif mit `red_verfahren = teilkuendigung`
  kennt keine Beitragsherabsetzung": Sie liegt nicht im Kern, und keine
  Generation führt den Wert mehr.

## Die ausgesetzten Tests

Die Tests der zurückgebauten Fähigkeiten und die Tests allgemeiner Mechanik,
die ihre Welt auf dem übernommenen Tarif bauen (das eingefrorene
Ende-zu-Ende-Fixture des Laufs), haben auf diesem Stand keinen Gegenstand. Sie
sind nicht gelöscht und nicht einzeln markiert: Ihre Kennungen stehen in
`tests/rueckbau_fall2_ausgesetzt.txt`, und `tests/conftest.py` wählt sie beim
Sammeln ab (Mechanik: `tests/rueckbau.py`).

- Jeder Lauf nennt in seiner Zusammenfassung, wie viele Tests ausgesetzt sind.
- Eine Kennung der Liste, die es in der Suite nicht gibt, macht den Lauf zum
  Fehler.
- Die Zahl ist in `tests/test_rueckbau_fall2.py` mit `==` festgehalten.

Die Liste ist aus einem Lauf der ganzen Suite auf dem zurückgebauten Stand
erzeugt: jeder Test, der dort rot wird. Gemessen am 2026-10-02 auf dem Stand
nach der vierten Prüfrunde: 746 von 4965 Tests in 58 Dateien. Es laufen 4217
Tests, 2 sind wie auf dem Hauptzweig übersprungen (Regie-Dateien).

Woran sie ZUERST scheitern (kein Maß für das, was sie brauchen): 567 an
einer der sechs Tafeln, 132 an der benannten Verweigerung des Kerns, 5 an der
Generation TG2015, 42 am Exit-Code eines Kommandos oder an einem Vergleich mit
Config und Tarifplan. 494 scheitern schon im Aufbau ihrer Welt, 325 davon
über eine einzige Fixture (`gefahrener_fall` in `tests/test_baldrian2_e2e.py`,
der gefahrene Lauf 2 als Welt für 17 Testdateien). Das ist ein Histogramm
erster Hindernisse: Gibt man die Tafeln zurück, treffen dieselben Tests als
Nächstes die Verweigerung des Kerns (gemessen an drei Modulen: 145 von 189).
Eine Kostenschätzung trägt es nicht.

Die Liste ist eine Zwischenlösung mit einer Bedingung, keiner Frist. Sie
endet, wenn ihre zwei Aufgaben erledigt sind (Vorgabe des Maintainers,
2026-10-02):

1. Tests, die eine zurückgebaute Fähigkeit ausüben, werden GELOESCHT und
   während der Fallverarbeitung neu geschrieben. Das gehört zur Entwicklung
   des Zielsystems durch einen Fall.
2. Allgemeine Tests, die nur an der Welt des übernommenen Tarifs hängen,
   werden von ihm UNABHAENGIG gemacht: Sie bekommen eine Welt aus einer
   eigenen synthetischen Lieferung, die zum Tarifwerk des eigenen Geschäfts
   passt. Dieselbe Klasse wie die Fähigkeiten, die bleiben.

Nicht gebaut: die Zuordnung je Eintrag der Liste zu einer der zwei Aufgaben,
und die Welt für die zweite. Bis dahin ist auf diesem Stand ein Teil der
allgemeinen Mechanik (Registrierung, Zugangsprobe, Buchungsklassen) schwächer
bewacht als auf dem Hauptzweig.

## Der Weg zurück (Fall 3)

Die Kern-Änderung von Fall 3 ist die Umkehrung dieses Commits: die drei
Ausgestaltungen im Kern, die Tafeln über den Tafelimport mit Provenienz, die
Generation in der Config. Zwei Wege:

1. Der Rechenkern-Agent baut sie im Fall unter Entwicklermandat neu; der
   Änderungsbeleg von A-K2 zeigt die Kern-Änderung. Schlussprobe: `git diff
   <stand-vor-dem-rueckbau> -- src/rechner_pipeline/kern configs` ist bis auf
   Versionsprotokoll und Versionsnummer leer. Nicht vorab gemessen: ob der
   Tafelimport den entfernten Block byte-gleich wiederherstellt (Reihenfolge,
   Provenienz-Kommentar) und ob ein neu gebauter Kernzweig zeichengleich
   ausfällt. Weicht etwas ab, zeigt es diese Probe; maßgeblich ist dann,
   dass die ausgesetzten Tests wieder laufen.
2. Rückfall, wenn die Vorführung nicht warten kann: den Rückbau-Commit
   zurücknehmen. Gemessen am 2026-10-02 in einem eigenen Arbeitsbaum auf
   diesem Stand — es ist nicht ein Schritt, es sind drei:
   a) `git revert --no-commit <rueckbau-commit>` hält an genau einem
      Konflikt: Diese Datei wurde nach dem Rückbau geändert. `git add
      dev-docs/rueckbau-fall2.md` behält sie. Danach sind `src`, `configs`
      und `tests` gleich dem Stand vor dem Rückbau (bis auf den Test der
      Werkzeuge, der später dazukam).
   b) Das Versionsprotokoll geht nur vorwärts: Der Revert setzte die
      Kern-Version auf die Nummer vor dem Rückbau zurück. Stattdessen
      bleibt der Eintrag des Rückbaus stehen, und die Wiederherstellung
      bekommt die nächste Version mit eigenem Eintrag (`kern/__init__.py`).
   c) Volle Suite, dann committen. Gemessen auf diesem Weg: 4950 passed,
      2 skipped, Baumwächter ohne Befund, Exit 0.
   (Berichtigt: Bis zum 2026-10-02 stand hier „in einem Schritt“; das war
   nicht gemessen.)

In beiden Fällen wird `tests/rueckbau_fall2_ausgesetzt.txt` gelöscht; die
ausgesetzten Tests laufen dann wieder, und die Zahl in
`tests/test_rueckbau_fall2.py` steht auf null (bzw. das Modul entfällt mit
dem Revert).

## Nicht Teil dieses Commits

- Die Laufzeit: In der produktiven Ablage ist der Zugang des zweiten Laufs
  registriert; sie bleibt unberührt, bis die neue sie ablöst. Die Werkzeuge
  nehmen den Ort der Ablage als Argument (`tageslauf --stand`, `uebernahme
  --stand`). Gemessen am 2026-10-02: Eine frische Ablage ohne den
  übernommenen Bestand lässt sich auf diesem Stand aufstellen und bis zum
  Tag vor dem Stichtag des Falls führen (11.506 Tage, 1.696 Verträge, 378
  Monatsabschlüsse), mit eigener Linie und den vier Erstabnahmen (ADR-025).
  Nicht geprüft: der Zugang zum Stichtag des Falls in voller Größe. Er
  braucht die Generation des Falls in der Config; nach dem Handbuch
  (`plv/betrieb/README.md`) und `betrieb/neuaufsetzen.py` heißt eine
  geänderte Config eine neu gerechnete Ablage — gelesen, nicht gefahren. Ein
  Storno eines Zugangs in einer laufenden Ablage gibt es nicht.
- Der Tarifplan und die Fachdokumente: nicht zurückgebaut (siehe oben).

## Kern 3.22.0: die Umkehrung im Fall 3 (2026-10-02)

Fall 3 braucht die drei zurückgebauten Ausgestaltungen, weil das Bedingungswerk
des übernommenen Tarifs sie belegt (Ziffer 3 und 4: Erhöhung als eigener
Baustein mit voller Beitragsformel, Stornoabzug je Baustein, Rückkaufswert als
Summe; Teilkündigung nur der Grundversicherung). Entwicklermandat des
Maintainers (Punkt 9 des Fallmandats), Abnahme unter A-K2 (`mensch/rechenkern`).

Gebaut ist die Umkehrung der Kern-Anteile von `cfaef32` (`rechenkern`,
`vorgangsfolge`, `beitragsreduktion`; Zeilen wie zuvor, bitgleiche Rechnung der
früheren Fähigkeit 3.2.0, 3.3.0, 3.7.0, 3.15.0, 3.17.0). `faehigkeit_fehlt`
und `KernFaehigkeitFehlt` entfallen: keine Regel wird mehr verweigert.

Entscheide und verworfene Alternativen:

- Fähigkeit statt Annahme: Der Kern hat keine Voreinstellung; jeder Aufrufer
  nennt die Regel aus der Spez (Kern 3.20.0 bleibt). Verworfen: gamma1 der
  Scheibe als neue Voreinstellung — `scheiben_mit_gamma1` ist gelesen mit
  Konfidenz 0,7 und noch nicht bestätigt (A-Q1); eine Voreinstellung nahme die
  Entscheidung vorweg.
- Umkehrung des Kern-Codes statt Neubau: Die Rechnung ist durch die
  Prüfrunden des zweiten Laufs gelaufen. Verworfen: Neubau nach AVB — er
  hielte dieselbe Formel, ohne die Prüfhistorie.
- Config und ausgesetzte Tests: Die Generation TG2015 kommt NICHT in die
  Config zurück, die Liste der 746 ausgesetzten Tests bleibt. Verworfen:
  `git revert cfaef32` im Ganzen — er brachte Generation und Tafeln am Fall
  vorbei zurück, und Fall 3 soll die Übernahme neu belegen.
- Tafeln: Nur über `quellen.tafel_import` des Falls (nach A-Q1, Spez), nicht
  aus dem Rückbau-Commit kopiert. Gemessener Dry-run auf einer Kopie: 6
  Tafeln, 0 Konflikte, 4 Kreuzproben wertgleich.
- Tests: Die Verweigerungstests von `tests/test_rueckbau_fall2.py` sind
  Charakterisierungen der Rechnung (unabhängige Handrechnung je Merkmal,
  beidseitig); die Ratsche hält `==` null Verweigerungen.

### Tafeln (Fall 3, nach der Spez)

Die sechs Tafeln sind über `quellen.tafel_import` des Falls in
`kern/tafeln.xml` eingetragen (Dry-run: 6 einzufügen, 0 Konflikte, 4
Kreuzproben wertgleich; danach ein zweiter Dry-run: alle 6 wertgleich
vorhanden). Gemessen gegen den Stand vor dem Rückbau: Die Werte sind
gleich; es unterscheiden sich nur die Provenienz-Hashes von Tarifrechner und
Exportmanifest in den XML-Kommentaren (die Lieferung von Fall 3 ist eine
neu registrierte Datei; das Blatt Tafeln.csv hat denselben Hash). Verworfen:
die Tafeln aus `cfaef32^` zurückkopieren — sie trüge die Provenienz der alten
Registrierung.

### Generation TG2015 in der Config; Liste der ausgesetzten Tests gelöscht (Fall 3, Übergabe 10)

Die Generation TG2015 steht wieder in `configs/bestand_gesamt.toml`, am Platz
vor dem Rückbau (nach dem BU-Abschnitt, vor dem Tagesbetrieb, damit die
Reihenfolge der Generationen und mit ihr alle eingefrorenen Portfolio-Werte
unverändert bleiben). Tarifwerte und Zellen kommen aus dem Übernahme-Vorlauf
des Falls (`abgeleitet/bestand/generation-zellen.toml`, aus der Spez), nicht
abgetippt; die Strukturfelder (Nummernkreis 14, Gültigkeit 2015-01-01 bis
2017-01-01, Endalter 90, inerte Verteilungen ohne Neuzugang) stammen aus dem
Block vor dem Rückbau (`git show cfaef32^:configs/bestand_gesamt.toml`) und sind
für eine übernommene Generation ohne Neuzugang ohne Wirkung auf den
Vertragswert. Unterschied zum alten Block: nur die Schreibweise `0.0` statt `0`
bei den Haus-Stornoabzügen (aus der Spez), im Tarifplan neu erzeugt.

Gemessen in einer Kopie des Baums ohne Liste: alle früher ausgesetzten Tests
laufen grün, zwei nicht — ein Test, der die Provenienz-Hashes der FRUEHEREN
Registrierung des Tarifrechners festhielt (`test_tafel_import`), und der
Tarifplan-Block (Schreibweise). Beide sind nachgezogen, mit Grund im Commit.
Die Liste `tests/rueckbau_fall2_ausgesetzt.txt` ist gelöscht; die Mechanik
(`tests/rueckbau.py`, Hook in `tests/conftest.py`) bleibt für den nächsten
Rückbau.
