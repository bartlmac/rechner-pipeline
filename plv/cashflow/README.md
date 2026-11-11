# Landeplatz der Cashflow-Modelle

Hier docken die eigenen Rechenwerke der Cashflow-Modelle an
([ADR-007](../../docs/architektur/adr-007-parallele-migrationen-ein-kern.md),
Nachtrag vom 10.11.2026). Der Bereich liegt zuerst außerhalb von `src/`,
damit die Arbeit an den Cashflow-Modellen nicht auf einen Umbau des Pakets
warten muss. Zum Jahresende zieht er in ein eigenes Paket der PLV um.

## Einordnung

Der Anwendungsfall Cashflow-Modelle verteilt sich auf dieselben Ebenen wie
die Migration ([ADR-028](../../docs/architektur/adr-028-ordnung-nach-ebenen.md)):

- System: ein System, das Cashflow-Modelle aufbaut und prüft, analog zur
  Migrationspipeline oder als ihre Erweiterung. Das ist noch offen und wird
  eigens entschieden.
- Objekt PLV: das Cashflow-Modell selbst mit seinen eigenen Rechenwerken. Es
  gehört zur PLV und ist eng auf sie abgestimmt, wie in der Praxis: Es liest
  ihre Produktdokumentation und ihren Bestand als Daten, und seine Ergebnisse
  werden mit ihren Abschlüssen verglichen. Den Rechenkern der Bestandsführung
  nutzt es nicht. Dieser Bereich ist sein Landeplatz.
- Simulation: ein Werkzeug, das Eingaben für das Cashflow-Modell simuliert,
  analog zur Simulation des Bestands und der Quelle bei der Migration. Das
  ist noch offen.

## Stand

`probe.py` ist eine Probe, kein Rechenwerk. Sie liest eine Tabelle und
summiert eine Beitragsspalte je Jahr, ohne Zins und ohne Sterblichkeit. Sie
zeigt, dass der Ort angebunden und bewacht ist; eine aktuarielle Aussage
macht sie nicht.

Die Probe legt kein Format für den Bestandsabzug fest; die Spalten nennt der
Aufrufer. Das Format bestimmen die Bestandsführung, die die Bereitstellung
baut, und die Cashflow-Gruppe, die die Spezifikation schreibt.

## Regeln

Die Wache in `tests/test_landeplatz_cashflow.py` prüft zwei Regeln:

1. Code in diesem Bereich importiert kein Modul aus `rechner_pipeline`,
   also auch nicht den Rechenkern. Die Daten kommen als Dateien.
2. Kein Modul in `src/`, `werkzeuge/` oder `system/` importiert diesen
   Bereich.

Code hier liest seine Eingaben nur. Der Test prüft das an der Probe: Die
Eingabedatei ist nach dem Lauf bytegleich.

Die Schichtenkarte (`ontologie/code_karte.py`) sieht diesen Bereich noch
nicht. Das kommt mit der Wache für den Code außerhalb von `src/` (#67); bis
dahin steht die Wache im Test.
