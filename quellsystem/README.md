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
   mit MEHREREN Vorfaellen je Vertrag — Dynamikserien, Erhoehung+PEX,
   Erhoehung+Herabsetzung, Dynamik NACH der Herabsetzung. Konventionen
   der Quelle, messbar getestet: Vorfaelle am 1. Januar
   (Kalenderjahres-Logik — daraus entstehen die unterjaehrigen t_a),
   Stornoabzug JE SCHEIBE (die Untergrenze greift mehrfach; der Test
   misst die Differenz zur vertragsweiten Rechnung), Herabsetzung als
   TEILKUENDIGUNG MIT AUSZAHLUNG nur auf der Grundscheibe, Cent beim
   Buchen. Praezisierung am Golden Master (2026-08-31): Das Blatt
   rundet die AUSGABEZELLEN auf Cent, nicht jeden Zwischenwert —
   gerundet wird beim BUCHEN je Geschaeftsvorfall, nicht in der
   Rechenkette.
4. `export` — Bestandsabzug, GeVo-Metadaten, Protokoll und
   Erwartungswerte im Lieferformat (POLNR;...;DECKKAP), einschliesslich
   t_a/dk_ta je Vertrag fuer die Verankerung.

Die Baldrian-REGIE (welche Defekte die Lieferung absichtlich traegt,
Seeds, Nachlieferungen) bleibt in `simulation/baldrian/` — gitignored,
Spielleiter-Bereich.
