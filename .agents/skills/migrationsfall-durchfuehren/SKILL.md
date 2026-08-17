---
name: migrationsfall-durchfuehren
description: >-
  Run a complete migration case through the ontology pipeline (Stufe 1 Quellen->A-Box,
  Stufe 2 A-Box->Spez->Kern-Parametrierung, Stufe 3 Golden-Master-Abnahme), including the
  human gates G-1/G-2 and their P9 snapshots. Trigger when the user asks to migrate a new
  Tarifgeneration or product delivery (Tarifmeldung + Tarifrechner) into the kernel, to
  "einen Migrationsfall durchfuehren/anlegen", or names this skill. Skip for: authoring gates (use
  author-rechner-toolbox-gate) or pure read/analysis questions.
---

# Einen Migrationsfall durchfuehren

## Rolle und Ziel

Du orchestrierst einen Migrationsfall durch die Ontologie-Pipeline
(Architektur: `docs/architektur/migrations-pipeline-v01.md`). Ziel ist
ein abgenommener Kern-Parametrierungsstand: Golden Master gegen den
Quell-Rechner gruen, alle Quell-Widersprueche als Diskrepanz-Objekte
erfasst und menschlich entschieden, jeder Schritt mit Gate-Ledger.

Nicht verhandelbar (P1-P10, Kurzform):

- Kein Agent liest Rohquellen, zu denen ein strukturiertes Derivat
  existiert; keine Stufe liest Rohquellen einer frueheren Stufe.
- Widersprueche zwischen Quellen entstehen im deterministischen Merge
  und werden NIE von einem Agenten entschieden — vorlaeufige
  Aufloesungen tragen `vorlaeufig=true` und blocken jede menschliche
  Annahme.
- Jede Aussage traegt Provenienz (Quelle+SHA-256, Fundstelle, Akteur,
  Zeitpunkt). Der Akteur-String nennt Modell und Skill:
  `<modell>/<skill>@<git-sha-kurz>` (git rev-parse --short HEAD).
- LLM-Schritte schlagen vor; Vergleich, Coverage, Urteil, Abnahme sind
  Code. Wo etwas nicht pruefbar ist, wird das AUSGEWIESEN, nie still
  uebersprungen.

## Referenzfall

`faelle/klv-tg2015` ist der abgeschlossene Praezedenzfall (KLV
TG2012 -> TG2015). Bei Unsicherheit ueber Artefakt-Formate dort
nachsehen — nicht raten. Das G-1-Dokument dieses Falls
(`abgeleitet/fachspez/klv-tg2015.md`) zeigt, wie das Ergebnis von
Stufe 1+2 aussehen muss.

## Ablauf

### Stufe 0 — Fall-Arbeitsbereich

```bash
python -m rechner_pipeline.fall anlegen --fall faelle/<fall> --beschreibung "..."
python -m rechner_pipeline.fall registrieren --fall faelle/<fall> --datei <quelle>   # je Quelle
python -m rechner_pipeline.fall status --fall faelle/<fall>
```

Regeln: Eingang ist nicht regenerierbar und wird nie aufgeraeumt;
Konflikte beim Registrieren (gleicher Name, anderer Inhalt) sind ein
Vorgang fuer den Menschen, kein Overwrite.

### Stufe 1 — Quellen -> A-Box

1. Vorverdichtung (deterministisch, je Quelltyp):
   - XLSM: `python -m rechner_pipeline.gates.extract --repo-root . --input faelle/<fall>/eingang/<datei> --out-dir faelle/<fall>/abgeleitet/vorverdichtung/xlsm-<GEN> --adapter excel --diagnostics-dir faelle/<fall>/abgeleitet/diagnostics`
   - DOCX: `python -m rechner_pipeline.quellen.tarifplan_staging --docx faelle/<fall>/eingang/<datei> --out faelle/<fall>/abgeleitet/vorverdichtung/meldung-<GEN>.json`
2. Extraktion: je (Quelle x Generation) EIN Agent nach Skill
   `extrahiere-quellfragment` (Structured Output gegen das generierte
   QuellFragment-Schema; der Agent sieht NUR seine eigene Quelle).
   Fragmente als JSON unter `abgeleitet/abox/fragmente/<gen>-<art>.json`
   ablegen.
3. Verifikations-Pass: auffaellige Extraktionen (niedrige Konfidenz,
   Anmerkungen) gegen die Vorverdichtung nachpruefen; Korrekturen im
   Fragment mit Anmerkung dokumentieren, Akteur um `+verifikation`
   ergaenzen.
4. Merge (deterministisch, MIT Ledger): `fragmente/akteure.json`
   schreiben ({"<fragment>.json": "<modell>/<skill>@<git-sha>"}), dann
   `python -m rechner_pipeline.gates.abox_merge --fall faelle/<fall> --repo-root .`
   — NIE baue_abox von Hand fuer einen echten Fall: der Merge-Ledger
   bindet die A-Box an die Fragmente, Gate O1 rechnet die Kette nach.
   Widersprueche werden Diskrepanz-Objekte — erwuenscht.
5. Gate O1: `python -m rechner_pipeline.gates.abox_validate --fall faelle/<fall> --repo-root .`
   Blockt bei Coverage-Luecken und offenen Diskrepanzen. Fuer den
   Weiterbau duerfen Diskrepanzen VORLAEUFIG zur Rechner-Lesart
   aufgeloest werden (`loese_diskrepanz_auf(..., vorlaeufig=True)`,
   Begruendung: der GM reproduziert den Rechner; fachliche Entscheidung
   G-1) — niemals endgueltig durch einen Agenten.

### Gate G-1 (Mensch — hier STOPPST du und uebergibst)

Vorlegen: `abgeleitet/fachspez/<gen>.md` (Generator:
`spez.fachspez.speichere_fachspez`), Diskrepanzenliste, Coverage.
Der Mensch entscheidet mit
`python -m rechner_pipeline.ontologie.entscheide --rolle mensch ...` und
snapshottet mit `python -m rechner_pipeline.gates.gate_entscheid
--gate G-1 --rolle mensch ...`. Als Agent darfst du AUSSCHLIESSLICH
ablehnen (--rolle agent, dokumentierter Zwischenstand). Die Annahme
rechnet ihre Vorbedingungen: O1 gruen und auf dem aktuellen
A-Box-Stand verankert; G-2 verlangt zusaetzlich O3 gruen+verankert und
einen geltenden G-1-Annahme-Snapshot desselben Stands.

### Stufe 2 — A-Box -> Spez -> Kern

1. Spez: `spez.erzeugen.baue_spez(abox, <gen-id>, referenz_id=<vorgaenger>)`
   + `spez.validierung.speichere_spez`. Das Struktur-Urteil
   (Parametrierung vs. neue Produktfamilie) wird BERECHNET — nimm es
   ernst: `neue_produktfamilie` oder offene Erweiterungsstellen heissen
   STOPP und Mensch fragen (T-Box-/Kern-Erweiterung ist Gate G-T).
2. Tafel-Import: `python -m rechner_pipeline.quellen.tafel_import --fall faelle/<fall> --generation <gen-id> --dry-run`,
   pruefen, dann scharf. Konflikte (wertverschiedene Tafeln gleichen
   Namens) sind ein Provenienz-Problem fuer den Menschen.
3. Kern-Aenderungen: eine neue Generation ist PARAMETRIERUNG — kein
   Formel-Code. Neue Tafeln in `kern/tafeln.xml` sind eine fachliche
   Aenderung: Kern-`__version__` anheben, Abnahme-Protokoll des Kerns
   einhalten (bestehende Charakterisierungs-Anker muessen gruen bleiben).

### Stufe 3 — Abnahme

1. Gate O3: `python -m rechner_pipeline.gates.generation_golden --fall faelle/<fall> --generation <gen-id> --repo-root .`
   Prueft vorab, dass die Spez Projektion der A-Box ist, und vergleicht
   den Kern gegen die aus dem Quell-Rechner extrahierten
   Erwartungswerte. Beachte das Summary: `zellen_ohne_erwartungswerte`
   ehrlich weitermelden (der Quell-Rechner traegt meist nur EINEN
   Beispiel-Modellpunkt).
2. Volle Suite: `.venv/bin/python -m pytest` — bestehende Verankerungen
   duerfen sich nicht bewegen.
3. Gate G-2 (Mensch): `gate_entscheid --gate G-2 ...` — wieder
   uebergeben, nicht selbst entscheiden.

## Abbruchkriterien (STOPP und Mensch fragen)

- Struktur-Urteil != parametrierung, oder Erweiterungsstellen offen.
- Merkmalsraum-Konflikt zwischen Quellen (Dimensions-Definitionen
  widersprechen sich).
- Tafel-Konflikt (wertverschieden bei gleichem Namen) oder
  Eingang-Integritaetsverletzung.
- Eine bestehende Kern-Verankerung (Charakterisierungs-Anker) wird rot.
