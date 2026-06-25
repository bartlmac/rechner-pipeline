# Golden-Master: COM-Extraktion (Referenz)

Roh-Extraktion von `examples/Tarifrechner_KLV.xlsm` über das **COM-Backend**
(`--export-backend com`, Windows + Microsoft Excel + pywin32). Dient als
Referenz für `tests/test_golden_master_com.py`, das den plattformneutralen
`openpyxl`-Default gegen diese Werte prüft.

**Kuratiert:** nur die deterministischen Roh-Artefakte
(`Kalkulation.csv`, `Tafeln.csv`, `names_manager.csv`, `vba/*.txt`).
Entfernt wurden:

- `export_manifest.json` — enthält absolute Pfade + Hashes (Maschinen-/
  Lauf-spezifisch → würde churnen).
- `*_compressed.csv`, `*_scalar.json`, `*_table_values.csv` — abgeleitete
  Artefakte aus identischem pure-python-Code, backend-unabhängig und auf
  jeder Plattform regenerierbar.

Quelle ist ein **synthetisches Lehrbeispiel** ohne realen Kundenbezug
(siehe README). Bei Wechsel der Beispiel-Datei diese Fixture bewusst neu
erzeugen und committen.

## Bekannte, akzeptierte Abweichungen openpyxl ↔ COM

Der Vergleich (`rechner_pipeline.qa.extraction_diff`) trennt *materielle* von
*akzeptierten*/*kosmetischen* Unterschieden. Akzeptiert sind:

- **Präzision:** COM gibt einige berechnete Werte mit ~4 Nachkommastellen
  zurück; openpyxl liefert die volle gecachte Präzision (gleiche Zahl,
  openpyxl ist treuer).
- **Mehrzell-Namen** (`m_Tafeln`, `v_x`, `v_Tafeln`): COM evaluiert sie via
  `Application.Evaluate` zum kompletten Array; openpyxl lässt `ValueEvaluated`
  leer. Die **Referenz bleibt via `RefersTo` erhalten** (z. B.
  `Tafeln!$B$4:$E$127`), die Werte stehen in den Sheet-CSVs → kein
  Informationsverlust für die Code-Portierung.
- **Interne `_xl…`-Namen:** Excel-Artefakte ohne fachliche Bedeutung.

Kosmetisch: `int` vs `float` (`5` vs `5.0`), `$` in Adressen, führendes `=`
in `RefersTo`, CRLF vs LF.
