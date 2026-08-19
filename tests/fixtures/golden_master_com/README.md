# COM-Extraktion: historisches Referenzmaterial

Roh-Extraktion von `tests/fixtures/Tarifrechner_KLV_TG2012.xlsm` über das
**COM-Backend** (`--export-backend com`, Windows + Microsoft Excel +
pywin32), aufgehoben aus der Zeit, als der plattformneutrale
`openpyxl`-Default gegen diese Werte geprüft wurde.

**Kein aktiver Testpfad.** Der zugehörige Vergleichstest und die
Vergleichs-Engine `qa/extraction_diff` sind mit der Ausserbetriebnahme des
Portierungspfads entfallen (ADR-006); kein Test liest diese Mappe heute.
Sie bleibt als Beleg dafür liegen, wie die beiden Extraktions-Backends
sich zueinander verhalten haben — nachvollziehbar, aber unverbindlich.

**Kuratiert:** nur die deterministischen Roh-Artefakte
(`Kalkulation.csv`, `Tafeln.csv`, `names_manager.csv`, `vba/*.txt`).
Nicht aufgehoben wurden:

- `export_manifest.json` — enthält absolute Pfade + Hashes (Maschinen-/
  Lauf-spezifisch → würde churnen).
- `*_compressed.csv`, `*_scalar.json`, `*_table_values.csv` — abgeleitete
  Artefakte aus identischem pure-python-Code, backend-unabhängig und auf
  jeder Plattform regenerierbar.

Quelle ist ein **synthetisches Lehrbeispiel** ohne realen Kundenbezug.

## Damals bekannte, akzeptierte Abweichungen openpyxl ↔ COM

Der historische Vergleich trennte *materielle* von *akzeptierten*/
*kosmetischen* Unterschieden. Akzeptiert waren:

- **Präzision:** COM gibt einige berechnete Werte mit ~4 Nachkommastellen
  zurück; openpyxl liefert die volle gecachte Präzision (gleiche Zahl,
  openpyxl ist treuer).
- **Mehrzell-Namen** (`m_Tafeln`, `v_x`, `v_Tafeln`): COM evaluiert sie via
  `Application.Evaluate` zum kompletten Array; openpyxl lässt `ValueEvaluated`
  leer. Die **Referenz bleibt via `RefersTo` erhalten** (z. B.
  `Tafeln!$B$4:$E$127`), die Werte stehen in den Sheet-CSVs → kein
  Informationsverlust.
- **Interne `_xl…`-Namen:** Excel-Artefakte ohne fachliche Bedeutung.

Kosmetisch: `int` vs `float` (`5` vs `5.0`), `$` in Adressen, führendes `=`
in `RefersTo`, CRLF vs LF.
