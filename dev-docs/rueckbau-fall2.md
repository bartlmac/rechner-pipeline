# Rueckbau des zweiten Baldrian-Laufs (vor Fall 3)

Fall 3 ist die Neufassung der Uebernahme des Bestands KLV TG2015. Damit er
zeigt, was eine Uebernahme am Zielsystem veraendert, steht das Zielsystem auf
diesem Zweig so da, als haette es den uebernommenen Tarif nie gerechnet. Der
Rueckbau ist EIN Commit auf dem heutigen Stand, kein Zuruecksetzen der
Historie: Alles, was seit dem Lauf vom September gebaut und repariert wurde,
bleibt. Auftrag und Zuschnitt: Maintainer, 2026-10-01.

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
nach der vierten Pruefrunde: 746 von 4965 Tests in 58 Dateien. Nach dem Grund
ihres Scheiterns: 567 brauchen eine der sechs Tafeln (sie bauen ihre Welt auf
dem uebernommenen Tarif), 132 erreichen eine benannte Verweigerung des Kerns,
5 nennen die Generation TG2015, 42 scheitern am Exit-Code eines Kommandos
oder an einem Vergleich mit Config und Tarifplan, ohne den Grund im Text zu
tragen (nicht einzeln nachverfolgt). Es laufen 4217 Tests, 2 sind wie auf
dem Hauptzweig uebersprungen (Regie-Dateien).

Folge, die man kennen muss: Auf diesem Zweig ist ein Teil der allgemeinen
Mechanik (Registrierung, Zugangsprobe, Buchungsklassen) schwaecher bewacht als
auf dem Hauptzweig, solange die Liste besteht.

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

- Die Laufzeit: Der Zugang des zweiten Laufs ist dort registriert. Das
  Neuaufsetzen verlangt einen Fall (`--fall`); der Rueckbau in der Laufzeit
  und der Eintritt von Fall 3 sind deshalb ein Schritt (die alte Ablage wird
  archiviert, nichts geloescht). Ein Storno eines Zugangs in der laufenden
  Ablage als eigenes Verfahren gibt es nicht.
- Der Tarifplan und die Fachdokumente: nicht zurueckgebaut (siehe oben).
