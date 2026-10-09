# Objekt PLV

Die Pfefferminzia Lebensversicherung AG (PLV), ein erfundenes Unternehmen:
die übernehmende Gesellschaft. Ihre Laufzeit läuft ohne jede Migration; ein
Fall bringt einen übernommenen Bestand in ihre Ablage.

| Was | Wo |
|---|---|
| Rechenkern, Bestandsführung und Tagesbetrieb | `src/rechner_pipeline/kern`, `src/rechner_pipeline/bestand`, `src/rechner_pipeline/betrieb` |
| Grundsatzdokumentation (abgenommen, Teil des Kernstands) | [mathematik/](mathematik/README.md) |
| Tarifpläne (abgenommen, Teil des Tarifwerks) | [tarifplaene/](tarifplaene/README.md) |
| Parametrierung der Tarifgenerationen (abgenommen, Teil des Tarifwerks) | [configs/](configs/README.md) |
| Image, Compose und Dienst der Laufzeit | [betrieb/](betrieb/README.md) |
| Quellen des Auftritts, der Vorzeigeseite | [seite/](seite/) |

Kernstand und Tarifwerk ändern sich nur mit einer neuen Abnahme (A-K2,
A-T1); auch ein Umzug ist eine Änderung
([ADR-028](../docs/architektur/adr-028-ordnung-nach-ebenen.md)).

Wie Bestand und Tagesbetrieb der PLV entstehen, beschreibt
[docs/simulation/](../docs/simulation/README.md); gebaut wird die Seite mit
den Werkzeugen unter [werkzeuge/](../werkzeuge/README.md).
