# Rueckbau des zweiten Baldrian-Laufs (vor Fall 3)

Fall 3 ist die Neufassung der Uebernahme des Bestands KLV TG2015. Damit er
zeigt, was eine Uebernahme am Zielsystem veraendert, steht das Zielsystem auf
diesem Zweig so da, als haette es den uebernommenen Tarif nie gerechnet. Der
Rueckbau ist EIN Commit auf dem heutigen Stand, kein Zuruecksetzen der
Historie: Alles, was seit dem Lauf vom September gebaut und repariert wurde,
bleibt. Auftrag und Zuschnitt: Maintainer, 2026-10-01.

## Dieser Stand ist die Basis; nach main kommt er nur zusammen mit dem Fall

Berichtigt am 2026-10-02 (Entscheid des Maintainers). Die erste Fassung
dieses Abschnitts sagte, der Zweig werde nie nach main gemergt, weil main das
System sei, das die Uebernahme geleistet HAT. Das behandelte die Historie der
PLV als Aufzeichnung. Sie ist eine Erzaehlung: Die PLV ist ein fiktives
Unternehmen, und ihre Geschichte wird mit jeder Verbesserung des Systems neu
geschrieben. Eine alte Migration auf main, die sich dort nicht zurueckbauen
laesst, ist nicht der gewollte Zustand.

Das Zielbild:

- Es gibt einen stabilen Stand "PLV ohne Migrationen": die Lieferungen und die
  allgemeinen Faehigkeiten des Systems, aber kein Code einer Migration. Dieser
  Zweig ist seine erste Fassung.
- Fuer einen Fall wird aus diesem Stand eine eigene Laufzeit neben der
  produktiven aufgestellt, die den uebernommenen Bestand nicht kennt. In ihr
  laeuft die Migration, mit Pruefungen, Abnahmen und Zugang.
- Erst danach kommt der Merge nach main: der Code des Falls samt neuer
  allgemeiner und fallspezifischer Tests, und die neue Laufzeit loest die
  produktive ab. Der Rueckbau kommt nie allein nach main; main ohne den Fall
  rechnete Vertraege nicht mehr, die in der produktiven Laufzeit registriert
  sind.
- Ein besserer Fall wiederholt den Weg. Eine weitere Tranche kann auf dem
  aktuellen Stand starten, oder eine fruehere wird zurueckgerollt und beide
  laufen nacheinander.

Gebaut ist davon dieser Stand. Die zweite Laufzeit und die Abloesung sind
nicht gebaut und nicht gefahren.

## Was zurueckgebaut ist

| Gegenstand | vorher | auf diesem Stand |
|---|---|---|
| Beitragsformel je Erhoehungsbaustein (`scheiben_mit_gamma1 = true`, Kern 3.2.0) | die Scheibe traegt gamma1 | verweigert |
| Stornoabzug je Baustein (`stoab_je_baustein = true`, Kern 3.3.0 und Folgen in Vorgangsfolge und Herabsetzung) | Abzug und Rueckkaufswert je Baustein | verweigert |
| Teilkuendigung nur der Grundversicherung (`tku_umfang = grundversicherung`, Kern 3.17.0) | die Scheiben bleiben | verweigert |
| sechs Tafeln aus dem Tarifrechner der Quelle (`DAV2008_T_NR_F/M/U70`, `DAV2008_T_R_F/M/U70`) | in `kern/tafeln.xml` | entfernt (762 Zeilen) |
| Generation TG2015 in `configs/bestand_gesamt.toml` | 14 Generationen | 13 Generationen |

Gemessen an der Config vor dem Rueckbau fuehrte NUR die Generation TG2015
diese Regelwerte; die 13 eigenen Generationen tragen den jeweils anderen
Wert. Fuer sie aendert sich kein Rechenwert, und kein
Charakterisierungs-Referenzwert des Kerns bewegt sich. Kern 3.21.0.

"Verweigert" heisst: Die Regeln bleiben im Vokabular (T-Box, Spez) und in den
Signaturen. Eine Spez darf sie belegen. Erreicht ein solcher Wert den Kern,
endet die Rechnung mit `KernFaehigkeitFehlt` und der Meldung

    Tarifregel <regel> = <wert>: Der Kern rechnet diese Ausgestaltung nicht —
    keine Tarifgeneration des Zielsystems fuehrt sie. Ausweg: eine
    Kern-Erweiterung mit Entwicklermandat, abgenommen unter A-K2
    (mensch/rechenkern)

statt nach der Regel des eigenen Geschaefts zu rechnen. Das ist die Stelle,
an der Fall 3 anhaelt. Verworfen: die Regeln ganz aus Vokabular und Signaturen
zu nehmen — das zoege durch Bestand, Pruefstrecken, Gates und Spez, und die
Rueckkehr waere kein ueberschaubarer Schritt mehr.

## Was bleibt

- Die Teilkuendigung als Vorgang des eigenen Geschaefts (alle Bausteine).
- Was die Migration am Werkzeug gelehrt hat: Korrekturschicht, Verankerung,
  Serien-Rekonstruktion, Pruefstrecken, Zeichnungsordnung, Gates.
- Der Fall-Arbeitsbereich des zweiten Laufs und seine Lieferung
  (`lieferungen/baldrian-2`): Sie sind die Quelle von Fall 3.
- Die Dokumente des Laufs (`docs/faelle/baldrian-lauf2*.md`) und der
  Tarifplan: Sie sind NICHT zurueckgebaut und beschreiben weiter, was der
  uebernommene Tarif verlangt.
- In `bestand/` die Zuordnung "ein Tarif mit `red_verfahren = teilkuendigung`
  kennt keine Beitragsherabsetzung": Sie liegt nicht im Kern, und keine
  Generation fuehrt den Wert mehr.

## Die ausgesetzten Tests

Die Tests der zurueckgebauten Faehigkeiten und die Tests allgemeiner Mechanik,
die ihre Welt auf dem uebernommenen Tarif bauen (das eingefrorene
Ende-zu-Ende-Fixture des Laufs), haben auf diesem Stand keinen Gegenstand. Sie
sind nicht geloescht und nicht einzeln markiert: Ihre Kennungen stehen in
`tests/rueckbau_fall2_ausgesetzt.txt`, und `tests/conftest.py` waehlt sie beim
Sammeln ab (Mechanik: `tests/rueckbau.py`).

- Jeder Lauf nennt in seiner Zusammenfassung, wie viele Tests ausgesetzt sind.
- Eine Kennung der Liste, die es in der Suite nicht gibt, macht den Lauf zum
  Fehler.
- Die Zahl ist in `tests/test_rueckbau_fall2.py` mit `==` festgehalten.

Die Liste ist aus einem Lauf der ganzen Suite auf dem zurueckgebauten Stand
erzeugt: jeder Test, der dort rot wird. Gemessen am 2026-10-02 auf dem Stand
nach der vierten Pruefrunde: 746 von 4965 Tests in 58 Dateien. Es laufen 4217
Tests, 2 sind wie auf dem Hauptzweig uebersprungen (Regie-Dateien).

Woran sie ZUERST scheitern (kein Mass fuer das, was sie brauchen): 567 an
einer der sechs Tafeln, 132 an der benannten Verweigerung des Kerns, 5 an der
Generation TG2015, 42 am Exit-Code eines Kommandos oder an einem Vergleich mit
Config und Tarifplan. 494 scheitern schon im Aufbau ihrer Welt, 325 davon
ueber eine einzige Fixture (`gefahrener_fall` in `tests/test_baldrian2_e2e.py`,
der gefahrene Lauf 2 als Welt fuer 17 Testdateien). Das ist ein Histogramm
erster Hindernisse: Gibt man die Tafeln zurueck, treffen dieselben Tests als
Naechstes die Verweigerung des Kerns (gemessen an drei Modulen: 145 von 189).
Eine Kostenschaetzung traegt es nicht.

Die Liste ist eine Zwischenloesung mit einer Bedingung, keiner Frist. Sie
endet, wenn ihre zwei Aufgaben erledigt sind (Vorgabe des Maintainers,
2026-10-02):

1. Tests, die eine zurueckgebaute Faehigkeit ausueben, werden GELOESCHT und
   waehrend der Fallverarbeitung neu geschrieben. Das gehoert zur Entwicklung
   des Zielsystems durch einen Fall.
2. Allgemeine Tests, die nur an der Welt des uebernommenen Tarifs haengen,
   werden von ihm UNABHAENGIG gemacht: Sie bekommen eine Welt aus einer
   eigenen synthetischen Lieferung, die zum Tarifwerk des eigenen Geschaefts
   passt. Dieselbe Klasse wie die Faehigkeiten, die bleiben.

Nicht gebaut: die Zuordnung je Eintrag der Liste zu einer der zwei Aufgaben,
und die Welt fuer die zweite. Bis dahin ist auf diesem Stand ein Teil der
allgemeinen Mechanik (Registrierung, Zugangsprobe, Buchungsklassen) schwaecher
bewacht als auf dem Hauptzweig.

## Der Weg zurueck (Fall 3)

Die Kern-Aenderung von Fall 3 ist die Umkehrung dieses Commits: die drei
Ausgestaltungen im Kern, die Tafeln ueber den Tafelimport mit Provenienz, die
Generation in der Config. Zwei Wege:

1. Der Rechenkern-Agent baut sie im Fall unter Entwicklermandat neu; der
   Aenderungsbeleg von A-K2 zeigt die Kern-Aenderung. Schlussprobe: `git diff
   <stand-vor-dem-rueckbau> -- src/rechner_pipeline/kern configs` ist bis auf
   Versionsprotokoll und Versionsnummer leer. Nicht vorab gemessen: ob der
   Tafelimport den entfernten Block byte-gleich wiederherstellt (Reihenfolge,
   Provenienz-Kommentar) und ob ein neu gebauter Kernzweig zeichengleich
   ausfaellt. Weicht etwas ab, zeigt es diese Probe; massgeblich ist dann,
   dass die ausgesetzten Tests wieder laufen.
2. Rueckfall, wenn die Vorfuehrung nicht warten kann: `git revert
   <rueckbau-commit>` stellt Code, Tafeln, Config und Tests in einem Schritt
   her.

In beiden Faellen wird `tests/rueckbau_fall2_ausgesetzt.txt` geloescht; die
ausgesetzten Tests laufen dann wieder, und die Zahl in
`tests/test_rueckbau_fall2.py` steht auf null (bzw. das Modul entfaellt mit
dem Revert).

## Nicht Teil dieses Commits

- Die Laufzeit: In der produktiven Ablage ist der Zugang des zweiten Laufs
  registriert; sie bleibt unberuehrt, bis die neue sie abloest. Die zweite
  Laufzeit des Zielbilds ist nicht aufgestellt. Die Werkzeuge nehmen den Ort
  der Ablage als Argument (`tageslauf --stand`, `uebernahme --stand`); ob sich
  eine frische Ablage ohne Fall auf diesem Stand aufstellen laesst und einen
  Zugang zum Stichtag des Falls annimmt, ist nicht geprueft. Ein Storno eines
  Zugangs in einer laufenden Ablage gibt es nicht.
- Der Tarifplan und die Fachdokumente: nicht zurueckgebaut (siehe oben).
