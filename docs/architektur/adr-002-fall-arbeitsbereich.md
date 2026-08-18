# ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum

Status: akzeptiert (Bartek, 2026-08-14). Umgesetzt:
`rechner_pipeline.fall` + `assurance --fall`.

> **Teilweise abgeloest durch [ADR-006](adr-006-portierung-ausser-betrieb.md)**
> (2026-08-17): Den Befehl `assurance --fall` gibt es nicht mehr. Der
> Fall-Arbeitsbereich und seine Regeln gelten unveraendert; die Gates
> operieren einzeln auf dem Fall (`--fall <pfad>`).

## Kontext

Bisher formulierten README und AGENTS.md den Einstieg als
`--input examples/...` plus drei lose Verzeichnis-Flags. Das verwechselt
Demo-Material mit dem Eingangskanal des Systems: einem Kunden laesst
sich nicht erklaeren, dass `examples/` "das Input-Verzeichnis" sei, und
ob eine Quelle synthetisch oder echt ist, ist fuer den Code irrelevant —
relevant ist nur, was in ein oeffentliches Repo darf. Es fehlte der Ort,
an dem ein Migrationsfall lebt.

## Entscheidung

Ein **Fall** (ein Migrationsprojekt) lebt in einem eigenen
Arbeitsbereich mit zwei strikt getrennten Zonen:

```
<arbeitsbereich>/            im echten Einsatz AUSSERHALB des Repos;
  fall.json                  faelle/ im Repo ist nur der gitignorierte
  eingang.json               Default fuer lokale Demo-Faelle
  eingang/                   registrierte Quellen — NICHT regenerierbar
  entscheide/                P9-Snapshots menschlicher Gates — NICHT
                             regenerierbar (wie der Eingang)
  abgeleitet/                alles Regenerierbare
    info_from_excel/  generated/  diagnostics/  berichte/
    abox/  spez/  fachspez/
```

Einschraenkung in v0.1: ``abgeleitet/abox/abox.json`` traegt nach dem
Gate G-1 auch die menschlichen Diskrepanz-Entscheidungen und ist damit
nicht mehr frei regenerierbar — bis die Entscheidungs-Wiederanwendung
aus den P9-Snapshots gebaut ist, gilt: abox.json nicht loeschen.

- **Eingang:** Quellen werden registriert (`fall registrieren`) —
  unter ihrem Namen schreibgeschuetzt abgelegt, mit SHA-256, Herkunft
  und Zeitpunkt im Register `eingang.json` (der Hash identifiziert den
  Inhalt, die Ablage bleibt namensbasiert; Eingangsnamen sind flach und
  ohne Pfadanteil). Hier beginnt die
  Provenance-Kette (P1). Gleicher Name mit anderem Inhalt ist ein
  harter Konflikt mit beiden Hashes in der Meldung — kein stiller
  Overwrite (P2). Kein Werkzeug dieses Repos raeumt den Eingang auf.
- **Abgeleitet:** darf jederzeit geloescht und aus Eingang + System neu
  erzeugt werden.
- **Die Pipeline operiert auf dem Fall:** `assurance --fall <pfad>
  --quelle <name>` prueft den Eingang VOR dem Lauf gegen das Register
  (kein Lauf auf unklarem Eingang) und legt alle Ausgaben unter
  `abgeleitet/` ab. Explizite Verzeichnis-Flags bleiben verfuegbar und
  uebersteuern (Entwickler-Kurzweg).
- **`examples/` ist Demo-Material:** oeffentliche Beispielquellen, aus
  denen sich ein Demo-Fall instanziieren laesst, plus Test-Fixtures.
  Kein Eingangskanal. *(Nachtrag 2026-08-19: `examples/` wurde
  aufgeloest — Bestands-Konfigurationen nach `configs/`,
  Extraktions-Fixtures nach `tests/fixtures/`, historische
  Quelldokumente aus dem Repo entfernt. Die Kein-Eingangskanal-Regel
  gilt unveraendert.)*

## Konsequenzen

- Der dokumentierte Einstieg (README, AGENTS.md) ist der Fall-Weg;
  einem Kunden zeigt man `fall anlegen / registrieren / assurance
  --fall`, nicht ein Repo-Verzeichnis.
- Echte Faelle liegen ausserhalb des Repos (Pfad frei waehlbar) mit
  eigener Versionierung und eigenem Zugriffsschutz; ins oeffentliche
  Repo kommt nie Kundenmaterial.
- Der Eingang-Schutz ist Architekturregel statt Vorsicht: registrierte
  Dateien sind schreibgeschuetzt, Integritaetsverletzungen blocken den
  Lauf, Aufraeum-Werkzeuge fassen `eingang/` nie an.
- Der Architektur-Entwurf (Ontologie-Pipeline) baut auf dem Fall auf:
  A-Box, Spezifikation und Gate-Snapshots eines Falls liegen in dessen
  Arbeitsbereich; das Layout unter `abgeleitet/` waechst dort weiter.
- `runs/` bleibt fuer lose Entwickler-Laeufe ausserhalb eines Falls
  (regenerierbar, aufraeumbar).

## Bekannte Einschraenkung

Die Gate-Kette verlangt heute den InputBundle-Ordner unterhalb von
`--repo-root` (G5/G7 brechen sonst ab). Ein Fall ausserhalb der
Repo-Wurzel wird deshalb vor dem Lauf mit einer Anweisung abgewiesen
statt mitten im Lauf zu scheitern. Das steht der Zielaussage "echte
Faelle liegen ausserhalb des Repos" entgegen und wird im
Pipeline-Entwurf aufgeloest (die Repo-Wurzel ist dort der Ort des
Systems, nicht der Ort der Daten).

## Verworfene Alternative

Nur eine Verzeichnis-Konvention ohne Werkzeug: die Struktur existierte
dann, aber Registrierung, Hashes, Schreibschutz und die
Vor-Lauf-Pruefung blieben Handarbeit und Prosa — nichts machte die
Regeln wahr.
