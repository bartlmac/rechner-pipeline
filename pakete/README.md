# Pakete — festgehaltene Fälle zum Nachfahren

Ein Paket hält einen geführten Migrationsfall so fest, dass er sich ohne
Agenten deterministisch nachfahren lässt: Aus dem Stand des Repositorys und
einem Paket entsteht mit einem Aufruf eine Laufzeit mit übernommenem
Bestand.

```
deploy/welt/laufzeit_aufstellen.sh <welt> pakete/<paket> [--bis <haltepunkt>]
```

Wie der Aufruf arbeitet und wie man an einem Haltepunkt selbst zeichnet,
steht in [deploy/welt/README.md](../deploy/welt/README.md). Ein Lauf mit
`--bis <haltepunkt>` endet am genannten Haltepunkt; derselbe Aufruf ohne
`--bis` (oder mit einem späteren Haltepunkt) fährt weiter.

Die Haltepunkte von `baldrian-klv-tg2015-fall3`, in ihrer Reihenfolge:

| Haltepunkt | Was dann zum Lesen bereitliegt |
|---|---|
| `auftrag` | der angelegte Fall mit registrierter Lieferung und die Vorlage des Fallauftrags |
| `eingang` | der gezeichnete Auftrag und die Nachlieferungen der Quelle |
| `diskrepanzen` | die A-Box aus den Fragmenten mit den offenen Widersprüchen der Quellen |
| `vor-A-K2` | die entschiedenen Diskrepanzen, Spez und Fachspez der Generation und die Vorlage der Kernabnahme `A-K2` |
| `vor-A-Q1` | Spez, Übernahme, Transformation und die Vorlagen der aktuariellen Tests `A-M1` bis `A-M3` |
| `vor-A-M4` | die gezeichneten Abnahmen der Quellen, der Tests und des Tarifwerks; der Abnahmebericht |
| `abgenommen` | die gezeichnete Migrationsabnahme |
| `vor-A-B2` | der Beleg der Zugangsprobe |
| `vor-A-B3` | die neu aufgesetzte Ablage nach dem Aufbaulauf und der Beleg ihres Anfangsbestands |
| `zugang` | die Ablage mit gebundenem Anfangsbestand: das Ende des Laufs |

## Was in einem Paket liegt

| Datei | Inhalt |
|---|---|
| `fall.conf` | die Definition des Falls: Name, Lieferung, Stichtag, Auftrag |
| `rezept.sh` | die Endfassung des Falls als Folge von Schritten: je Artefakt das Kommando, das es zuletzt erzeugt hat, in der Reihenfolge des Laufs, dazu die Haltepunkte |
| `erarbeitet/` | was im Fall die Agenten erarbeitet haben und kein Kommando erzeugt: die Fragmente der Extraktion, die Übersetzungsvorschrift für den Bestandsabzug, der Abzugsabgleich |
| `nachlieferung/` | was die abgebende Gesellschaft im Lauf des Falls auf Rückfrage geliefert hat, und Festlegungen der übernehmenden |
| `ERWARTUNG` | Prüfsummen der Ergebnisse, die beim Nachfahren byte-gleich entstehen müssen |
| `STAND` | der Commit, auf dem die Welt vor dem Fall aufgestellt wird |
| `SHA256SUMS` | die Prüfsummen des Pakets selbst |

Ein Paket trägt keine Schlüssel, keine Zeichnungen und keine Ablage. Die
entstehen beim Nachfahren neu, mit den Schlüsseln der jeweiligen Welt.

## Ein Paket trägt die Auflösung seines Falls

In `erarbeitet/` und `nachlieferung/` steht, was im Fall erst gefunden,
erfragt und entschieden werden musste: die Widersprüche der Quellen, die
Antworten der abgebenden Gesellschaft, die Übersetzung ihres Datenmodells.
Deshalb gilt: **Wer einen dieser Fälle live führt, ob Agent oder Mensch,
liest hier nicht.** Sonst wird der Fall nicht geführt, sondern sein
Ergebnis abgeschrieben.

## Nachfahren übernimmt Urteile

Das Rezept zeichnet beim Nachfahren die Gates des Falls, ohne neu zu prüfen:
Es übernimmt das Urteil der Zeichnung im festgehaltenen Fall. Das trägt nur,
wenn der Gegenstand derselbe ist. Deshalb hält das Rezept vor jeder solchen
Zeichnung den Gegenstand gegen den festgehaltenen Fall (Kern und Tarifwerk
über ihre Fingerabdrücke, die Ergebnisse über `ERWARTUNG`) und hält an,
wenn etwas abweicht.

Wer an einem Haltepunkt selbst zeichnet, dessen Zeichnung gilt: Das Rezept
zeichnet dann nicht noch einmal, und über eine Ablehnung zeichnet es nie
hinweg.

## Auf welchem Stand

`STAND` nennt den Commit vor dem Fall. Die Routine stellt die Welt auf ihm
auf und fährt den Fall auf dem Stand des Baums nach. Der Baum muss dazu Kern
und Tarifwerk so tragen wie der festgehaltene Fall; ein Test hält das fest
(`tests/test_pakete.py`). Ändert sich einer der beiden Gegenstände, ist das
Paket auf dem neuen Stand nicht mehr nachfahrbar und wird neu festgehalten
(ADR-027).

## Die Pakete

| Paket | Fall | Lieferung | Stand davor | Stand danach |
|---|---|---|---|---|
| `baldrian-klv-tg2015-fall3` | Übernahme des Bestands KLV TG2015 der Baldrian Leben zum 01.01.2026, festgehalten am 02.10.2026: 834 Verträge, 112 Schritte | `lieferungen/baldrian-2` und die Nachlieferungen im Paket | Tag `fall3-vor` | Tag `fall3-nach` |

Welche Fälle es außerdem gab und in welchem Verhältnis sie stehen:
[docs/faelle/README.md](../docs/faelle/README.md).

## Ein Paket bauen

Aus einem geführten Fall baut `deploy/welt/paket_bauen.sh` das Paket; der
Abschnitt „Das Paket bauen“ in
[deploy/welt/README.md](../deploy/welt/README.md) beschreibt es. Im
Repository liegt ein Paket nur, wenn es seinen Prüfsummen entspricht und
keine Datei darüber hinaus trägt.
