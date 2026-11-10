# Beschlussliste

Eine Zeile je Beschluss, mit Datum, neueste oben. Die Liste nimmt
Beschlüsse auf, die die Zusammenarbeit oder den Weg eines Beitrags regeln
und kein eigenes ADR brauchen. Architektur-Entscheidungen stehen als ADR im
[Index](README.md#entscheidungen); eine Zeile hier verweist auf das ADR,
statt es zu wiederholen.

Neue Zeilen trägt das Maintainer Office ein, über einen Pull Request wie
jede andere Änderung.

| Datum | Beschluss | Beleg |
|---|---|---|
| 10.11.2026 | Gemergt wird nur durch das Maintainer Office, nie durch einen Agenten. Pull Requests von Agenten gibt einer der beiden anderen Code Owners bis zum nächsten Arbeitstag um 12:00 frei. | [CONTRIBUTING.md](../../CONTRIBUTING.md#weg-eines-beitrags) |
| 10.11.2026 | Eine Karte ist fertig, wenn die fünf Punkte des Fertig-Kriteriums erfüllt sind. | [CONTRIBUTING.md](../../CONTRIBUTING.md#wann-eine-karte-fertig-ist) |
| 10.11.2026 | Anwendungsgruppen arbeiten im selben Repository per Pull Request; Excel nach Python arbeitet bis zum 27.11.2026 vorübergehend getrennt und wird bis Mitte Dezember zusammengeführt. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |
| 10.11.2026 | Getrennt heißt Vertrag statt Import, gesichert durch Wachen, dazu Landeplätze; getrennte Pakete oder Repositorys sind nicht gemeint. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |
| 10.11.2026 | Zwei Rechenkerne: der Rechenkern der Bestandsführung und eigene Rechenwerke der Cashflow-Modelle, zuerst in einem Bereich außerhalb von `src/`, zum Jahresende in einem eigenen Paket der PLV. | [ADR-007](adr-007-parallele-migrationen-ein-kern.md) |
