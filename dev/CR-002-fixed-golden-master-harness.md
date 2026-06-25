# CR-002 — Fester, reviewter Golden-Master-Harness statt LLM-generiertem Test

- **Status:** Umgesetzt auf `feat/anthropic-provider` (Default `--test-mode fixed`);
  Contract mit Alexander in der Übergabe zu bestätigen; E2E-Verifikation gegen
  echten Rechenkern = 1 bezahlter Lauf ausstehend. Mechanik per Integrationstest
  (Subprozess + Confinement + Contract-Import + Vergleich) offline verifiziert.
- **Datum:** 2026-05-29
- **Branch-Kontext:** `feat/anthropic-provider`
- **Betroffen:** `prompts/v1/excel_to_py.txt` (Contract), `prompts/v1/test_advanced.txt` (entfällt),
  `src/rechner_pipeline/orchestrate/runner.py` (Test-LLM-Stufe + Compare), neuer fixer Harness
- **Abstimmung:** **mit Alexander** (Prompt-/Test-/Compare-Stufe sind seine Domäne)

## 1. Problem

Der Validierungs-Harness `test_run_advanced.py` wird **bei jedem Lauf neu vom
LLM generiert**. Folgen:

1. **Security-Idiom-Whack-a-Mole:** Jede Generierung wählt ein anderes Datei-I/O-
   Idiom (Lauf A: `os.path`+`glob`+`open`; Lauf B: `pathlib`), das am statischen
   Security-Gate hängenbleibt. Jedes Idiom einzeln freizuschalten ist endlos.
2. **Kein unabhängiges Orakel:** Rechenkern **und** Prüf-Harness stammen beide
   von Claude → die Validierung ist nicht unabhängig (Governance-/Whitebox-Lücke,
   vgl. [[project-rechner-pipeline-stand]]).
3. **Kosten:** zwei LLM-Calls pro Lauf (Haupt + Test) ≈ doppelte Kosten.

## 2. Befund zur Schnittstelle

`prompts/v1/excel_to_py.txt` fixiert **6 Dateien + Reihenfolge + Importregeln**,
aber **nicht** die Funktions-Signaturen ("saubere, parametrisierte API" — Namen
wählt das LLM). Deshalb muss der Test-Harness heute mitgeneriert werden: nur so
kennt er die gewählten Funktionsnamen.

Die **Vergleichs-Engine** selbst ist dagegen generisch: Sie liest Erwartungswerte
aus `info_from_excel/*_scalar.json` + `*_table_values.csv` und ordnet nach
**Namen** zu (Skalare; Tabellenspalten case-sensitiv) — unabhängig von
LLM-Wahl. LLM-abhängig ist nur das **Beschaffen der berechneten Werte**.

## 3. Vorschlag

**a) Stabiler Ergebnis-Contract im Haupt-Prompt.** `test_run.py` (oder ein
designiertes Modul) muss einen festen Einstiegspunkt exponieren, der die
berechneten Werte strukturiert liefert — Namen **identisch** zu den
Erwartungsdateien. Beispiel:

```python
def golden_master_outputs() -> dict:
    return {
        "scalars": {"Bxt": ..., "BJB": ..., "BZB": ..., "Pxt": ..., "ratzu": ...},
        "tables":  [ {"Axn": ..., "axn": ..., ...}, ...  ],  # je Periode ein dict
    }
```

**b) Fester, reviewter Harness** (committet, **nicht** LLM-generiert), z. B.
`src/rechner_pipeline/qa/golden_master.py`: liest die Erwartungswerte, ruft
`golden_master_outputs()` des generierten Rechenkerns, vergleicht (4-Dezimal-
Rundung, case-sensitive Namenszuordnung wie im bisherigen Test-Prompt), schreibt
Report + Exit-Code. **Das ist zugleich das unabhängige Orakel.**

**c) Runner/Pipeline:**
- **Test-LLM-Stufe (`run_test_llm`) entfällt** → ein LLM-Call weniger (~halbe Kosten).
- `run_compare` führt den **fixen** Harness aus (weiterhin unter `fs_confine`-
  Confinement als Defense-in-depth).
- Statisches Security-Gate nur noch auf den **Rechenkern** (Hauptoutput) nötig;
  der fixe Harness ist reviewter Code, kein LLM-Output.

## 4. Nutzen

- **Kein Idiom-Whack-a-Mole** mehr (fixer Harness, ein I/O-Idiom, reviewt).
- **Unabhängiges Orakel** → schließt den Governance-/Whitebox-Punkt.
- **~50 % günstiger pro Lauf** (nur noch der Haupt-LLM-Call).
- **Deterministischer** Vergleich, leichter zu warten/zu prüfen.

## 5. Migration / Schritte

1. Contract (3a) in `excel_to_py.txt` ergänzen (Alexander).
2. Fixen Harness (3b) schreiben + committen; Vergleichs-Engine aus dem bisherigen
   `test_advanced.txt`-Verhalten übernehmen (Skalare + Matrix, case-sensitiv).
3. `run_test_llm` entfernen; `run_compare` auf den fixen Harness umstellen.
4. `prompts/v1/test_advanced.txt` entfernen (oder archivieren).
5. **Ein** bezahlter Verifikationslauf: Rechenkern implementiert den Contract,
   fixer Harness läuft → echtes Pass/Fail.

## 6. Offene Fragen

1. Genaue Form des Contracts (dict-Shape; wie werden Tabellen/Perioden indexiert;
   Index-Spalte `k`, die bisher "nicht zugeordnet" blieb).
2. Rückwärtskompatibilität: alte LLM-Harness-Variante als Fallback behalten
   (`--test-mode llm|fixed`) oder hart ersetzen?
3. Wie streng wird der Contract erzwungen (Validierung, falls `golden_master_
   outputs()` fehlt/abweicht)?
4. Zusammenspiel mit der (späteren) wirklich unabhängigen Orakel-Absicherung
   (z. B. zweite Implementierung / manueller Review der erwarteten Werte).

## 8. Umsetzung (Stand 2026-05-29)

- **Fester Harness:** `src/rechner_pipeline/qa/golden_master.py` (stdlib-only,
  reviewbar): lädt Erwartungswerte, ruft `golden_master_outputs()`, vergleicht
  (4-Dezimal-Rundung, case-sensitive Spalten-Zuordnung mit Trennzeichen-Varianten),
  Report + Exit-Code.
- **Contract** in `prompts/v1/excel_to_py.txt` ergänzt (Pflicht-Funktion in
  `test_run.py`).
- **Runner:** `--test-mode {fixed,llm}` (Default `fixed`). `fixed` überspringt
  die Test-LLM-Stufe und führt den festen Harness via `fs_confine` aus. `llm` =
  bisheriges Verhalten (Fallback). **(Korrigiert 2026-06-25, s. Nachtrag.)**
- **Tests:** Vergleichs-Engine (synthetisch) + Fixed-Mode-Integration (Subprozess).
- **Noch offen:** Contract mit Alexander bestätigen; 1 bezahlter Lauf, in dem der
  generierte Rechenkern `golden_master_outputs()` implementiert; offene Punkte §6.

## 9. Nachtrag 2026-06-25 — Security-Annahme korrigiert (Review-Finding F1)

Die ursprüngliche Annahme „im `fixed`-Modus kein statisches Gate nötig, da
reviewter Code" (§3c, §8) war **zu eng** und ist korrigiert. Der feste Harness
ist zwar reviewt, **importiert und führt zur Laufzeit aber das untrusted
`generated/test_run.py` aus** (`golden_master.main()` macht `import test_run`).
Das Laufzeit-Confinement `fs_confine` deckt nur `open`/`glob` ab, nicht
`os.system`/`subprocess`/Netz — ein bösartiger Top-Level-Befehl im generierten
Contract lief dadurch im `fixed`-Modus ungeprüft durch.

**Behebung (Sitzung 2026-06-15 freigegeben, umgesetzt 2026-06-25):** `run_compare`
prüft die generierten `*.py` jetzt **auch im `fixed`-Modus** statisch, bevor der
Harness sie ausführt (der reviewte Harness liegt in `src/`, außerhalb von
`generated/`, und wird nicht gescannt). Damit gilt: statisches Gate auf den
Rechenkern **immer** vor Ausführung, unabhängig vom Testmodus. Offen als
Follow-up (kein Merge-Blocker): `fs_confine` zusätzlich um Laufzeit-Block für
`subprocess`/`os.system`/`socket` erweitern (Defense-in-depth, vgl. CR-004).

## 7. Empfehlung

Annehmen — löst gleich drei Probleme (Security-Varianz, Orakel-Unabhängigkeit,
Kosten). Schritt 1 (Contract) **mit Alexander** abstimmen, da Prompt-/Test-/
Compare-Stufe seine Domäne sind. Der Rechenkern selbst ist bereits als funktional
korrekt nachgewiesen (566/566, offline), d. h. der Umbau gefährdet kein
bestehendes Ergebnis.
