# Dokumentation

Die Dokumentation für Entwickler. Was das Repository trägt und wo, steht im
[README](../README.md), nach Ebenen geordnet
([ADR-028](architektur/adr-028-ordnung-nach-ebenen.md)).

Zum Einstieg: das [Glossar](architektur/glossar.md) und der
[Ablauf eines Falls](architektur/ablauf-eines-falls.md).

| Ebene | Dokumente |
|---|---|
| System | [architektur/](architektur/README.md): Ablauf eines Falls, Prüf-Gates und ihre Versionen, Landkarte des Codes, die ADRs. Dazu [system/](../system/README.md) mit der [Vorlage des Migrationskonzepts](../system/migrationskonzept/README.md). |
| Objekt PLV | [plv/](../plv/README.md): die Fachdokumente der PLV, abgenommen ([Grundsatzdokumentation](../plv/mathematik/README.md), [Tarifpläne](../plv/tarifplaene/README.md)), die Parametrierung ([configs/](../plv/configs/README.md)), das Image der Laufzeit und der Auftritt |
| Objekt Baldrian bzw. Migration | [migrationen/](../migrationen/README.md), darin [baldrian/](../migrationen/baldrian/README.md): die Fälle, ihre Berichte und wie man Lauf 2 wiederholt |
| Simulation | [simulation/](simulation/README.md): wie Bestand und Tagesbetrieb der PLV entstehen. Die Werkzeuge liegen unter [werkzeuge/](../werkzeuge/README.md). |

Was erkannt, aber noch nicht gebaut ist, steht in
[dev-docs/](../dev-docs/README.md).
