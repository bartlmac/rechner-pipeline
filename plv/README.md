# Objekt PLV

Die Pfefferminzia Lebensversicherung AG (PLV), ein erfundenes Unternehmen:
die übernehmende Gesellschaft. Ihre Laufzeit läuft ohne jede Migration; ein
Fall bringt einen übernommenen Bestand in ihre Ablage.

| Was | Wo |
|---|---|
| Rechenkern, Bestandsführung und Tagesbetrieb | `src/rechner_pipeline/kern`, `src/rechner_pipeline/bestand`, `src/rechner_pipeline/betrieb` |
| Parametrierung der Tarifgenerationen (abgenommen, Teil des Tarifwerks) | [configs/](../configs/README.md) |
| Grundsatzdokumentation (abgenommen, Teil des Kernstands) | [docs/mathematik/](../docs/mathematik/README.md) |
| Tarifpläne (abgenommen, Teil des Tarifwerks) | [docs/tarifplaene/](../docs/tarifplaene/README.md) |
| Image, Compose und Dienst der Laufzeit | [betrieb/](betrieb/README.md) |
| Quellen des Auftritts, der Vorzeigeseite | [seite/](seite/) |

Configs, Grundsatzdokumentation und Tarifpläne liegen noch an ihrem
bisherigen Ort, weil ihre Abnahme den Pfad bindet. Sie ziehen hierher um,
sobald die Abnahme einen Ortswechsel verfolgen kann
([ADR-028](../docs/architektur/adr-028-ordnung-nach-ebenen.md)).

Wie Bestand und Tagesbetrieb der PLV entstehen, beschreibt
[docs/simulation/](../docs/simulation/README.md); gebaut wird die Seite mit
den Werkzeugen unter [werkzeuge/](../werkzeuge/README.md).
