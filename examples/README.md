# Beispiele

## Hinweis

Diese Artefakte sind **synthetische Lehrbeispiele**. Sie enthalten keine realen Kunden-, Bestands- oder Tafelwerte und dürfen frei für Demonstrationszwecke verwendet werden.

## Inhalt

- `Tarifrechner_KLV.xlsm` — KLV-Demo-Tarifrechner mit zwei Arbeitsblättern (`Kalkulation`, `Tafeln`) und VBA-Modulen. Standard-Eingabedatei für die Pipeline.
- `Tarifrechner_Pipeline.pptx` — kurzer Foliensatz, der die Pipeline-Stufen visualisiert (Begleitmaterial).

## Verwendung

Standardmäßig nutzt die Pipeline die Excel-Datei aus diesem Verzeichnis:

```powershell
python pipeline.py --excel examples/Tarifrechner_KLV.xlsm
```

Der `--excel`-Parameter ist optional; ohne Angabe wird
`examples/Tarifrechner_KLV.xlsm` relativ zum Repo-Root verwendet. Auch
explizite relative `--excel`-Pfade werden gegen das Repo-Root aufgelöst.
