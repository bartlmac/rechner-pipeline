# Quellsystem — die Bestandsfuehrung der abgebenden Gesellschaft

Simulations-Tooling, **kein Teil des Systems** (Beschluss 2026-08-31:
ADRs gelten dem System — KI, Rechenkern, Bestandsfuehrung der PLV; dieses
Paket gehoert wie die Bestands-Simulation zum Gesamtbild, Komponente (5)
im README-Bild). Es ersetzt den Windows-/Excel-Umweg der
Lieferungserzeugung: Bestand aufbauen, Geschaeftsvorfaelle ueber Jahre
fuehren (auch MEHRERE je Vertrag), Lieferungen exportieren.

## Die eine harte Regel

**Kein Import aus `rechner_pipeline`.** Der Quellcode des Quellsystems
ist fuer das Migrationsprojekt unerreichbar, und die Unabhaengigkeit der
Rechenwege — Kommutation hier, Thiele im Ziel — ist der Wert der ganzen
Vorfuehrung. Ein Test haelt die Regel maschinell
(`tests/test_quellsystem_kommutation.py`).

Deshalb sind Kommutation, Tafel-Lader, Konventionen und `tafeln.xml`
**eingefrorene Kopien** (2026-08-31, Stand f0938c7) und keine Importe:
Spaetere Zielsystem-Aenderungen duerfen nicht durchsickern. Wer hier
etwas aendert, aendert das Quellsystem — nicht die PLV.

## Golden Master

Die Basiskalkulation ist gegen die **Excel-Ergebnisse** des
Quell-Tarifrechners abgenommen (`simulation/baldrian/excel_ergebnis_*.csv`,
717 Vertragszeilen): Erlebens-/Todesfall-Barwert und Rentenbarwerte
treffen Excel auf < 1e-12 relativ (reine Float-Kettenreihenfolge; der
abgenommene Vergleichsmassstab der Migration sind ohnehin die
Testtoleranzen). Excel bleibt der Tarifrechner der Quelle.

## Bauplan

1. `kommutation`/`barwerte`/`tafeln`/`konventionen` — steht (Kopie plus
   Golden-Master-Test).
2. `rechnung` + `tarifwerk` — steht: die KLV-Zielgroessen des
   Quellsystems (Bxt, BJB/BZB, kVx-Verlauf, StoAb/RKW, VS_bfr) in
   VBA-Formelform auf der Kommutation, je Tarifzelle (status x
   tarifart). Golden Master: alle 15 Blattspalten ueber 717 Zeilen;
   EUR-Spalten centgenau bis auf gezaehlte Halbcent-Kanten (33 von
   >10000, je +-0.01 — Float-Kettenreihenfolge VBA/Python).
3. `bestandsfuehrung` — steht: Verkauf (~1000 Policen ueber das
   Vertriebsfenster 2015/16, stochastisch mit Seed; der Bestand am
   Stichtag ist ERGEBNIS, keine Vorgabe) und Fuehrung je Kalenderjahr
   mit MEHREREN Vorfaellen je Vertrag — Dynamikserien (Einschluss ist
   Vertragsmerkmal), Erhoehung+PEX, Erhoehung+Herabsetzung, Dynamik
   NACH der Herabsetzung. Konventionen der Quelle, messbar getestet:
   Jahres-Batch mit Buchung am VERTRAGSJAHRESTAG (so belegt es die
   Alt-Lieferung; die Kalenderjahres-Eigenheit steckt in der
   Altersermittlung ueber die Differenz der Kalenderjahre von Beginn
   und Geburt), Stornoabzug JE SCHEIBE (die Untergrenze greift
   mehrfach; der Test misst die Differenz zur vertragsweiten Rechnung),
   Herabsetzung als TEILKUENDIGUNG MIT AUSZAHLUNG nur auf der
   Grundscheibe, Cent beim Buchen, keine Erhoehung unter fuenf Jahren
   Restlaufzeit (Tarifbestimmungen Ziffer 3 — die VBA-Formel
   amortisiert Abschlusskosten stur ueber die Zillmerdauer).
   Praezisierung am Golden Master (2026-08-31): Das Blatt rundet die
   AUSGABEZELLEN auf Cent, nicht jeden Zwischenwert — gerundet wird
   beim BUCHEN je Geschaeftsvorfall, nicht in der Rechenkette.
4. `export` + `erwartungswerte` — steht: das Lieferpaket im Format der
   Alt-Lieferung. Bestandsabzug je Stichtag (Kopfzeile, Enums,
   TT.MM.JJJJ; DECKKAP = Wert am letzten Vertragsjahrestag t_a),
   GeVo-Metadaten (Vorgeschichte der Abzugs-Policen), GeVo-Protokoll
   des Migrationsjahres (mit Betraegen, PARAM = Anteil bei RED) und die
   vier Erwartungswerte-JSONs (Stichprobe VOR den Werten gezogen,
   geschichtet je Historientyp; A-M1 Uebernahme+Fortschreibung, A-M2
   Verlauf bis Ablauf, A-M3 dDK je Vorfall aus dem Journal). Der
   Stichtagsbestand ist eine REKONSTRUKTION aus dem Journal — spaetere
   Vorfaelle sind rueckwirkend unsichtbar, getestet ueber Kreuz
   zwischen den Artefakten. STORNO_KZ bleibt im sauberen Export leer
   (das R/S-Kennzeichen der Vorfuehr-Lieferung ist Regie, M2).

## Dokumente der Quelle

Die Quelle liefert ZWEI Dokumente, sauber getrennt (Beschluss
2026-09-01; vorher stand beides vermischt in einer Datei
"Tarifbestimmungen"):

* **AVB** (`avb.md`): die vertraglichen Zusagen — rudimentaer und ohne
  eine einzige Formel (Abzug je Baustein GESONDERT, Herabsetzung als
  Teilkuendigung MIT AUSZAHLUNG, Dynamik-Schranke). AVB enthalten
  keine Aktuarik; darauf steht ein Waechter-Test.
* **Tarifplan / Mitteilung 143** (`tarifplan.md`): der aktuarielle
  Teil — Rechnungsgrundlagen, Kostensaetze je Bestandsgruppe (mehrere
  schmale Tabellen statt einer breiten), Kommutationsformeln im
  Schreibmaschinen-Bruchsatz, Rundungsvorschrift als eigener Abschnitt
  statt RUNDEN-Wrapper in den Formeln. Nachfolger des Alt-Artefakts
  `Mitteilung_143_KLV_TG2015` (dort DOCX, jetzt Markdown).

Beide haben **Markdown-Quellen** und werden ueber die gepinnte
Doku-Engine des Repos gerendert (`docs/engine/render.sh`, Quarto/Typst)
— derselbe Weg wie die Zieltarifplaene. Beschluss 2026-08-31: Word war
Bequemlichkeit; am Ende steht ohnehin ein binaeres Artefakt (PDF), und
fuer die Simulation ist eine Textquelle bequemer. Die Optik traegt das
Altsystem (Schreibmaschinenschrift, Flattersatz ohne Silbentrennung,
Absatzabstand genau eine Leerzeile — Typst-Vorspann in den Quellen).
Die Grundformeln uebernehmen die Zeichenerklaerung der Tarifmeldung
eins zu eins — einschliesslich ihres gewollten Indexfehlers
(N(x)-Summe ab j=1; Regie F3, nur in der Doku, das Rechenwerk rechnet
korrekt). `docx.py` bleibt fuer Office-Artefakte, die es als DOCX
geben muss (Notizen, Mitteilungs-Nachbauten).

Die Baldrian-REGIE (welche Defekte die Lieferung absichtlich traegt,
Seeds, Nachlieferungen) bleibt in `simulation/baldrian/` — gitignored,
Spielleiter-Bereich.
