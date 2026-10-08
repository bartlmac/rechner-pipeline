# Dokumentation

Die Dokumentation für Entwickler. Was das Repository trägt und wo, steht im
[README](../README.md), nach Ebenen geordnet
([ADR-028](architektur/adr-028-ordnung-nach-ebenen.md)).

Zum Einstieg: das [Glossar](architektur/glossar.md) und der
[Ablauf eines Falls](architektur/ablauf-eines-falls.md).

| Ebene | Dokumente |
|---|---|
| System | [architektur/](architektur/README.md): Ablauf eines Falls, Prüf-Gates und ihre Versionen, Landkarte des Codes, die ADRs. Die Vorlage des Migrationskonzepts liegt unter [system/](../system/README.md). |
| Objekt PLV | [mathematik/](mathematik/README.md) (Grundsatzdokumentation) und [tarifplaene/](tarifplaene/README.md): die Fachdokumente der PLV, abgenommen. Sie ziehen nach `plv/` um, sobald die Abnahme einen Ortswechsel verfolgen kann. |
| Objekt Baldrian bzw. Migration | [migrationen/baldrian/](../migrationen/baldrian/README.md): die Fälle, ihre Berichte und wie man Lauf 2 wiederholt |
| Simulation | [simulation/](simulation/README.md): wie Bestand und Tagesbetrieb der PLV entstehen. Die Werkzeuge liegen unter [werkzeuge/](../werkzeuge/README.md). |

Was erkannt, aber noch nicht gebaut ist, steht in
[dev-docs/](../dev-docs/README.md).
