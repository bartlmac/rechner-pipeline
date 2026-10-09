# ADR-028: Ordnung des Repositorys nach Ebenen

**Status:** angenommen am 2026-10-08 (Maintainer), umgesetzt in zwei
Schritten: am 2026-10-08 alles außer den abgenommenen Gegenständen, am
2026-10-09 auch diese (Nachtrag unten). Löst die Tabelle der Gegenstände aus
ADR-027 ab.

## Kontext

Mit der Veröffentlichung des dritten Falls sehen viele Menschen das
Repository zum ersten Mal. Die oberste Ebene folgte den fünf Gegenständen
aus ADR-027, aber der Baum zeigte das nicht:

* Unter `docs/` lagen Entwicklerdoku, abgenommene Dokumente der PLV,
  Berichte zu einem Fall und das Werkzeug, das Dokumente als PDF setzt.
* `deploy/` trug die Routinen der simulierten Welt und das Image der
  Laufzeit der PLV.
* `werkzeuge/` trug die Werkzeuge der Seite und vier Werkzeuge des
  Migrationssystems.

Wer wissen wollte, wozu ein Ordner gehört, musste die Tabelle in ADR-027
kennen. Die Ebenen, in denen das Ganze gedacht ist, stehen schon in ADR-017
(Entwickler und KI, KI-Tool, Vorzeige, Vorzeige-Werkzeuge); sie ordneten
bisher nur die Importe im Paket.

## Entscheidung

Die Ordner im Wurzelverzeichnis folgen den Ebenen. Es sind die aus
ADR-017, auf den Baum übertragen und benannt: Ebene 2 (KI-Tool) heißt
System, Ebene 3 (Vorzeige) teilt sich in Objekt PLV und Objekt Baldrian
bzw. Migration, Ebene 4 (Vorzeige-Werkzeuge) heißt Simulation, Ebene 1
(Entwickler und KI) liegt quer. Neu sind die Laufzeit-Artefakte. Die
Reihenfolge der Tabellen ist keine Nummerierung.

| Ebene | Was | Ordner |
|---|---|---|
| System | das Migrationssystem, die gemeinsamen Datenverträge, die Rollen der Agenten, die Werkzeuge für den Live-Lauf eines Falls und die Vorlage des Migrationskonzepts | `src/rechner_pipeline` (gates, ontologie, spez, quellen, qa, models, fall.py), `.claude/`, `.agents/`, `system/` |
| Objekt PLV | die übernehmende Gesellschaft: Rechenkern, Bestandsführung, Tagesbetrieb, ihre Parametrierung und Fachdokumente, das Image ihrer Laufzeit und ihr Auftritt | `src/rechner_pipeline` (kern, bestand, betrieb), `plv/` |
| Objekt Baldrian bzw. Migration | die abgebende Gesellschaft: ihre Lieferungen, die Falldatei der Vorführung, die Berichte zu den Fällen | `migrationen/baldrian/` |
| Simulation | Modell und Betrieb der Simulation. Modell: Verteilungen, das Erzeugen von Geschäftsvorfällen und Neugeschäft (die Module, die die Schichtenkarte der Simulation zuordnet: `bestand/generator.py`, `stochastik.py`, `ereignisse.py`, `cli_fortschreibung.py`, `betrieb/neugeschaeft.py`), das Quellsystem der Baldrian. Betrieb: eine Welt aufstellen, einen Fall nachfahren, die Seite bauen. | `werkzeuge/`, die genannten Module in `src/rechner_pipeline` |
| Laufzeit-Artefakte | was beim Laufen entsteht; im Repository nur, was das Nachfahren eines Falls braucht | `pakete/` |

Quer dazu liegen `tests/`, `docs/` (Entwicklerdoku), `dev-docs/`, die
Entwicklungsumgebung (`deploy/dev`, `.devcontainer/`) und `.github/`.
`deploy/` bleibt vorerst mit der Entwicklungsumgebung allein stehen, weil
`.devcontainer/` auf sie verweist.

Was umgezogen ist:

| bisher | jetzt |
|---|---|
| `werkzeuge/vorfuehrung.py`, `lagebild.py`, `aufzeichnung.py`, `sitzungsprobe.py` | `system/` |
| `docs/migrationskonzept/` | `system/migrationskonzept/` |
| `deploy/plv/` | `plv/betrieb/` |
| `vorzeige-seite/` | `plv/seite/` |
| `lieferungen/` | `migrationen/baldrian/lieferungen/` |
| `deploy/welt/fall-baldrian-klv-tg2015.conf` | `migrationen/baldrian/` |
| `docs/faelle/` | `migrationen/baldrian/`, die Berichte zu Lauf 2 unter `berichte/` |
| `deploy/welt/` | `werkzeuge/welt/` |
| `quellsystem/` | `werkzeuge/quellsystem/` |
| `docs/engine/` | `werkzeuge/engine/` |
| `configs/` | `plv/configs/` (2026-10-09) |
| `docs/mathematik/` | `plv/mathematik/` (2026-10-09) |
| `docs/tarifplaene/` | `plv/tarifplaene/` (2026-10-09) |

Die Werkzeuge der Seite bleiben unter `werkzeuge/`. Der Ordner der
Simulation heißt `werkzeuge/` und nicht `simulation/`, weil dieser Name für
einen lokalen, von Git ausgenommenen Ordner vergeben ist (`.gitignore`).

## Die abgenommenen Gegenstände ziehen mit (Nachtrag 2026-10-09)

Grundsatzdokumentation, Tarifpläne und Configs sind abgenommen, und ihre
Abnahme bindet den Pfad: A-T1 liest das Tarifwerk des zuletzt abgenommenen
Commits unter dem heutigen Pfad, und der Kernstand hasht Name und Inhalt
jeder Datei. Ein bloßer Umzug hätte einen falschen Beleg ergeben. Gemessen
gegen den Stand vor dem dritten Fall hieß das Tarifwerk dort leer, und alle
drei Tarifpläne und alle 24 Generationen hießen „neu“.

Entschieden ist (Maintainer, 2026-10-09): Nach dem Deployment kennt kein
Werkzeug alte Pfade, weder die Laufzeit ohne Migration noch eine Migration.
Deshalb:

* Die Abnahme bleibt, wie sie war; ihre Pfade zeigen auf `plv/`
  (`models/tarifwerkabnahme.py`, `models/kernabnahme.py`).
* Der Stand vor dem dritten Fall ist in der neuen Ordnung neu festgehalten:
  Tag `fall3-vor-ebenen` (Commit `82eea92`), abgeleitet aus `fall3-vor`.
  Was die Routinen in einem Codebaum lesen (Configs, Grundsatzdokumentation,
  Tarifpläne, Lieferungen), liegt dort am neuen Ort, und die Pfade im Code
  zeigen dorthin; Kern, Referenzwerte und Inhalte sind unverändert. Ein
  Merge nimmt ihn in die Geschichte von `main` auf, ohne den Baum von `main`
  zu ändern: So ist er Vorfahr des Stands, auf dem nachgefahren wird.
* Das Paket des dritten Falls nennt ihn als Stand vor dem Fall. Kernstand
  und Tarifwerk sind neu abgenommen, das Paket ist neu festgehalten. Im
  Beleg von A-T1 heißen die Tarifpläne „geändert“ (die redaktionelle
  Überarbeitung) und die 24 Generationen „unverändert“; ein Umzug kommt
  darin nicht vor.
* Der Originalstand bleibt unter dem Tag `fall3-vor`. Der Originalfall vom
  2026-10-02 ist in der alten Ordnung geführt; die Seite zeigt seine Belege.

Zwei Folgen davon:

* Die Erstabnahme einer Welt vergleicht ohne Angabe mit dem Stand ihres
  Codebaums selbst und nimmt ihn ab, wie er ist (`VON` in
  `werkzeuge/welt/welt_aufstellen.sh`); vorher zeigte sie die Änderung gegenüber
  `e8fa2b4`, einem Stand der früheren Ordnung. A-T1 und A-K2 verweigern
  jeden Vergleichsstand, dem ihr Gegenstand an den heutigen Pfaden fehlt,
  statt ein leeres „vorher“ zu belegen (beide Werkzeuge in Version 2.0.0).
* Die Commits, die Tarifwerk und Grundsatzdokumentation zwischen
  `fall3-vor` und dem Umzug noch am alten Ort geändert haben (6aa7c14,
  884ac7f, 081c4f9, 627de7d, b3ddf31), nennen die Belege beim Nachfahren
  nicht unter „Commits des Zweigs“; die Zeilenzahlen gegen den Stand vor
  dem Fall stimmen.

Verworfen: der Abnahme die früheren Orte beizubringen (ein älterer Commit
wird am damaligen Ort gelesen, ein Umzug heißt „verschoben“). Das trug,
ließ aber alte Pfade in Abnahme und Routinen weiterleben.

## Folgen

* Die Routinen finden ihre eigenen Dateien über ihren Ort; in einem
  Codebaum lesen sie nur Pfade der neuen Ordnung. Für den Stand vor dem
  dritten Fall gibt es dafür `fall3-vor-ebenen` (Nachtrag), auch für einen
  Live-Lauf auf diesem Stand (ONBOARDING).
* Die Lieferungen sind bytegleich umgezogen; `.gitattributes` schützt sie
  unter dem neuen Pfad vor jeder Umwandlung von Zeilenenden.
* Das Paket des dritten Falls nennt Lieferung und Config unter den neuen
  Pfaden (`fall.conf`, `rezept.sh`). Tarifwerk und Kernstand haben durch den
  Umzug neue Fingerabdrücke; das Rezept hält sie und zeichnet A-K2 und A-T1
  beim Nachfahren über diesen Stand; der Stand vor dem Fall ist
  `fall3-vor-ebenen`. Keines der 16 erwarteten Ergebnisse des Falls nennt
  einen Pfad des Repositorys.
* README, `AGENTS.md`, `CONTRIBUTING.md` und die Einstiegsseiten der Ebenen
  (`system/`, `plv/`, `migrationen/`, `werkzeuge/`, `docs/`) folgen den
  Ebenen. Ein Test hält die Tabelle im README mit dem Baum zusammen
  (`tests/test_readme_gegenstaende.py`).
* Aus ADR-027 gelten weiter: keine Infrastruktur im Repository, die Regel
  für Pull Requests, der Stand von `main` und die abgenommenen Gegenstände.
* Die Schichtenkarte und die Importregeln im Paket ändern sich nicht.

## Offen

* Die Vorlage einer Instanz unter `plv/betrieb/` (Compose, Umgebung, Dienst
  und Timer) ist nach ADR-027 Infrastruktur und dort schon als offen
  benannt. Sie bleibt, bis entschieden ist, was die Routinen davon
  brauchen.
* Skripte außerhalb des Repositorys, die alte Pfade aufrufen
  (`deploy/welt/`, `deploy/plv/`, `configs/`), `quellsystem` aus dem Wurzelverzeichnis
  importieren oder nach `lieferungen/` schreiben, müssen nachgezogen
  werden.
