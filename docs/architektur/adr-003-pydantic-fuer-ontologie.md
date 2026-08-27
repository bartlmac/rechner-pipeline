# ADR-003: Pydantic fuer T-Box und A-Box

Status: akzeptiert (Bartek, D1-Entscheidung der Architektur-Fragerunde
2026-08-14). Betrifft ausschliesslich `rechner_pipeline.ontologie` und
`rechner_pipeline.spez`.

## Kontext

Das Repo-Idiom fuer Datenstrukturen ist bewusst leichtgewichtig:
dataclasses + `validate() -> List[str]` + stdlib tomllib (Beschluss zur
Bestands-Config, 2026-08-11). Die T-Box/A-Box der Migrations-Pipeline
ist aber ein anderes Objekt als eine Nutzer-Config: sie ist das
zentrale Austauschformat zwischen Agenten und Stufen, braucht
generierte JSON-Schemata (Structured-Output-Ziel der
Extraktions-Agenten), verlustfreie Roundtrip-Serialisierung und
Schema-Evolution. Zwei handgepflegte Repraesentationen desselben
Schemas (dataclass + JSON Schema) waeren genau der Drift, den dieses
Repo an anderer Stelle teuer gelernt hat.

## Entscheidung

Pydantic (exakt gepinnt, 2.13.4) fuer T-Box, A-Box und
Spez-Schema. Das uebrige Paket bleibt beim dataclasses-Idiom; die
Grenze ist die Ontologie-/Spez-Schicht. Semantische Constraints, die
ueber Feldvalidierung hinausgehen (Kreuz-Objekt-Regeln, Coverage),
bleiben im Repo-Idiom `validate() -> List[str]` AUF den
Pydantic-Objekten — Pydantic traegt Struktur und Serialisierung, nicht
die Fachlogik.

## Konsequenzen

- Sechste gepinnte Runtime-Dependency (rein, ohne Netz-/IO-Pfade;
  SDK-Freiheit unberuehrt).
- JSON-Schemata fuer Structured Output werden generiert
  (`model_json_schema()`), nie von Hand gepflegt.
- Deterministische Serialisierung bleibt Pflicht (sortierte Schluessel,
  feste Feldreihenfolge) — Tests sichern das ab.

## Verworfene Alternative

dataclasses + eigener JSON-Schema-Generator: machbar, aber wir bauten
Pydantic-Funktionalitaet nach und pflegten sie selbst — Minimalismus
heisst hier, das Werkzeug zu nehmen, nicht es nachzubauen.
