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
2. `rechnung` — die KLV-Zielgroessen des Quellsystems (Bxt, BJB/BZB,
   kVx-Verlauf, StoAb/RKW, VS_bfr) in VBA-Formelform auf der
   Kommutation, je Tarifzelle (status x tarifart); Golden Master sind
   dieselben CSVs, Spalte fuer Spalte.
3. `bestandsfuehrung` — Stamm + Journal der Quelle mit den ABWEICHENDEN
   Konventionen (StoAb je Scheibe, RED mit Abzug, Rundung je
   Zwischenschritt, Kalenderjahr-Logik, VS_bfr auf Vormonat);
   GeVo-Simulation mit mehreren Vorfaellen je Vertrag.
4. `export` — Bestandsabzug, GeVo-Metadaten, Protokoll und
   Erwartungswerte im Lieferformat (POLNR;...;DECKKAP), einschliesslich
   t_a/dk_ta je Vertrag fuer die Verankerung.

Die Baldrian-REGIE (welche Defekte die Lieferung absichtlich traegt,
Seeds, Nachlieferungen) bleibt in `simulation/baldrian/` — gitignored,
Spielleiter-Bereich.
