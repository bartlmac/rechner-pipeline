# Quellsystem — die Bestandsführung der abgebenden Gesellschaft

Simulations-Tooling, **kein Teil des Systems** (Beschluss 2026-08-31:
ADRs gelten dem System: KI, Rechenkern, Bestandsführung der PLV; dieses
Paket gehört zu den Fall-Definitionen, Gegenstand 3 nach ADR-027: Es
erzeugt die Lieferungen). Es ersetzt den Windows-/Excel-Umweg der
Lieferungserzeugung: Bestand aufbauen, Geschäftsvorfälle über Jahre
führen (auch mehrere je Vertrag), Lieferungen exportieren.

## Die eine harte Regel

**Kein Import aus `rechner_pipeline`.** Der Quellcode des Quellsystems
ist für das Migrationsprojekt unerreichbar, und die Unabhängigkeit der
Rechenwege (Kommutation hier, Thiele im Ziel) ist der Wert der ganzen
Vorführung. Ein Test hält die Regel maschinell
(`tests/test_quellsystem_kommutation.py`).

Deshalb sind Kommutation, Tafel-Lader, Konventionen und `tafeln.xml`
**eingefrorene Kopien** (2026-08-31, Stand f0938c7) und keine Importe:
Spätere Zielsystem-Änderungen dürfen nicht durchsickern. Wer hier
etwas ändert, ändert das Quellsystem, nicht die PLV.

## Golden Master

Die Basiskalkulation ist gegen die **Excel-Ergebnisse** des
Quell-Tarifrechners abgenommen (`simulation/baldrian/excel_ergebnis_*.csv`,
717 Vertragszeilen; diese Dateien liegen nicht im Repository, die
zugehörigen Tests werden ohne sie übersprungen): Erlebens-/Todesfall-Barwert und Rentenbarwerte
treffen Excel auf < 1e-12 relativ (reine Float-Kettenreihenfolge; der
abgenommene Vergleichsmaßstab der Migration sind ohnehin die
Testtoleranzen). Excel bleibt der Tarifrechner der Quelle.

## Bauplan

1. `kommutation`/`barwerte`/`tafeln`/`konventionen` (fertig): Kopie plus
   Golden-Master-Test.
2. `rechnung` + `tarifwerk` (fertig): die KLV-Zielgrößen des
   Quellsystems (Bxt, BJB/BZB, kVx-Verlauf, StoAb/RKW, VS_bfr) in
   VBA-Formelform auf der Kommutation, je Tarifzelle (status x
   tarifart). Golden Master: alle 15 Blattspalten über 717 Zeilen;
   EUR-Spalten centgenau bis auf gezählte Halbcent-Kanten (33 von
   >10000, je +-0.01: Float-Kettenreihenfolge VBA/Python).
3. `bestandsfuehrung` (fertig): Verkauf (~1000 Policen über das
   Vertriebsfenster 2015/16, stochastisch mit Seed; der Bestand am
   Stichtag ist Ergebnis, keine Vorgabe) und Führung je Kalenderjahr
   mit mehreren Vorfällen je Vertrag: Dynamikserien (Einschluss ist
   Vertragsmerkmal), Erhöhung+PEX, Erhöhung+Herabsetzung, Dynamik
   nach der Herabsetzung. Konventionen der Quelle, messbar getestet:
   - Jahres-Batch mit Buchung am Vertragsjahrestag (so belegt es die
     Alt-Lieferung; die Kalenderjahres-Eigenheit steckt in der
     Altersermittlung über die Differenz der Kalenderjahre von Beginn
     und Geburt);
   - Stornoabzug je Scheibe (die Untergrenze greift mehrfach; der Test
     misst die Differenz zur vertragsweiten Rechnung);
   - Herabsetzung als Teilkündigung mit Auszahlung nur auf der
     Grundscheibe;
   - Cent beim Buchen;
   - keine Erhöhung unter fünf Jahren Restlaufzeit (Tarifbestimmungen
     Ziffer 3; die VBA-Formel tilgt die Abschlusskosten immer über die
     ganze Zillmerdauer).

   Präzisierung am Golden Master (2026-08-31): Das Blatt rundet die
   Ausgabezellen auf Cent, nicht jeden Zwischenwert; gerundet wird
   beim Buchen je Geschäftsvorfall, nicht in der Rechenkette.
4. `export` + `erwartungswerte` (fertig): das Lieferpaket im Format der
   Alt-Lieferung. Bestandsabzug je Stichtag (Kopfzeile, Enums,
   TT.MM.JJJJ; DECKKAP = Wert am letzten Vertragsjahrestag t_a),
   GeVo-Metadaten (Vorgeschichte der Abzugs-Policen), GeVo-Protokoll
   des Migrationsjahres (mit Beträgen, PARAM = Anteil bei RED) und die
   vier Erwartungswerte-JSONs (Stichprobe vor den Werten gezogen,
   geschichtet je Historientyp; A-M1 Übernahme+Fortschreibung, A-M2
   Verlauf bis Ablauf, A-M3 dDK je Vorfall aus dem Journal). Der
   Stichtagsbestand ist eine Rekonstruktion aus dem Journal: spätere
   Vorfälle sind rückwirkend unsichtbar, getestet über Kreuz
   zwischen den Artefakten. STORNO_KZ bleibt im sauberen Export leer
   (das R/S-Kennzeichen der Vorführ-Lieferung ist eine bewusst
   eingebaute Abweichung).

## Dokumente der Quelle

Die Quelle liefert zwei Dokumente, sauber getrennt (Beschluss
2026-09-01; vorher stand beides vermischt in einer Datei
„Tarifbestimmungen“):

* **AVB** (`avb.md`): die vertraglichen Zusagen, rudimentär und ohne
  eine einzige Formel (Abzug je Baustein gesondert, Herabsetzung als
  Teilkündigung mit Auszahlung, Dynamik-Schranke). AVB enthalten
  keine Aktuarik; darauf steht ein Wächter-Test.
* **Tarifplan / Mitteilung 143** (`tarifplan.md`): der aktuarielle
  Teil: Rechnungsgrundlagen, Kostensätze je Bestandsgruppe (mehrere
  schmale Tabellen statt einer breiten), Kommutationsformeln im
  Schreibmaschinen-Bruchsatz, Rundungsvorschrift als eigener Abschnitt
  statt RUNDEN-Wrapper in den Formeln. Nachfolger des Alt-Artefakts
  `Mitteilung_143_KLV_TG2015` (dort DOCX, jetzt Markdown).

Beide haben **Markdown-Quellen** und werden über die gepinnte
Doku-Engine des Repos gerendert (`docs/engine/render.sh`, Quarto/Typst),
derselbe Weg wie die Zieltarifpläne. Beschluss 2026-08-31: Word war
Bequemlichkeit; am Ende steht ohnehin ein binäres Artefakt (PDF), und
für die Simulation ist eine Textquelle bequemer. Die Optik trägt das
Altsystem (Schreibmaschinenschrift, Flattersatz ohne Silbentrennung,
Absatzabstand genau eine Leerzeile; Typst-Vorspann in den Quellen).
Die Grundformeln übernehmen die Zeichenerklärung der Tarifmeldung
eins zu eins, einschließlich ihres gewollten Indexfehlers
(N(x)-Summe ab j=1; der Fehler steht absichtlich nur in der Doku, das
Rechenwerk rechnet korrekt). `docx.py` bleibt für Office-Artefakte, die es als DOCX
geben muss (Notizen, Mitteilungs-Nachbauten).

Die Regie der Baldrian (welche Defekte die Lieferung absichtlich trägt,
Seeds, Nachlieferungen) liegt in `simulation/baldrian/` und gehört nicht
zum Repository.
