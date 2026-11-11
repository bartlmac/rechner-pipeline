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
| 11.11.2026 | Die Frist für die Freigabe eines Pull Requests von einem Agenten endet um 12:00 am ersten Arbeitstag, an dem um 12:00 seit der Anfrage mindestens 24 Stunden vergangen sind. Sie ersetzt die Frist aus der Zeile vom 10.11.2026. | [CONTRIBUTING.md](../../CONTRIBUTING.md#weg-eines-beitrags) |
| 10.11.2026 | Gemergt wird nur durch das Maintainer Office, nie durch einen Agenten. Pull Requests von Agenten gibt einer der beiden anderen Code Owners bis zum nächsten Arbeitstag um 12:00 frei oder sagt in einem Kommentar, was fehlt. | [CONTRIBUTING.md](../../CONTRIBUTING.md#weg-eines-beitrags) |
| 10.11.2026 | Eine Karte ist fertig, wenn die fünf Punkte des Fertig-Kriteriums erfüllt sind. | [CONTRIBUTING.md](../../CONTRIBUTING.md#wann-eine-karte-fertig-ist) |
| 10.11.2026 | Anwendungsgruppen arbeiten im selben Repository per Pull Request; Excel nach Python arbeitet bis zum 27.11.2026 vorübergehend getrennt und wird bis Mitte Dezember zusammengeführt. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |
| 10.11.2026 | Getrennt heißt Vertrag statt Import, gesichert durch Wachen, dazu Landeplätze; getrennte Pakete oder Repositorys sind nicht gemeint. | [ADR-028](adr-028-ordnung-nach-ebenen.md) |
| 10.11.2026 | Zwei Rechenkerne: der Rechenkern der Bestandsführung und eigene Rechenwerke der Cashflow-Modelle, zuerst in einem Bereich außerhalb von `src/`, zum Jahresende in einem eigenen Paket der PLV. | [ADR-007](adr-007-parallele-migrationen-ein-kern.md) |
| 10.11.2026 | Die Rechenwerke der Cashflow-Modelle gehören zum Objekt PLV: Sie lesen Produktdokumentation und Bestand der PLV als Daten, ihre Ergebnisse werden mit den Abschlüssen der PLV verglichen, den Rechenkern der Bestandsführung nutzen sie nicht (Wortlaut vom 11.11.2026). | [ADR-028](adr-028-ordnung-nach-ebenen.md) |
