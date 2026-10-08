# ADR-028: Ordnung des Repositorys nach Ebenen

**Status:** angenommen am 2026-10-08 (Maintainer), am selben Tag umgesetzt
bis auf die abgenommenen Gegenstände (siehe „Offen“). Löst die Tabelle der
Gegenstände aus ADR-027 ab.

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
| Objekt PLV | die übernehmende Gesellschaft: Rechenkern, Bestandsführung, Tagesbetrieb, ihre Parametrierung und Fachdokumente, das Image ihrer Laufzeit und ihr Auftritt | `src/rechner_pipeline` (kern, bestand, betrieb), `configs/`, `docs/mathematik/`, `docs/tarifplaene/`, `plv/` |
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

Die Werkzeuge der Seite bleiben unter `werkzeuge/`. Der Ordner der
Simulation heißt `werkzeuge/` und nicht `simulation/`, weil dieser Name für
einen lokalen, von Git ausgenommenen Ordner vergeben ist (`.gitignore`).

## Ausnahme: die abgenommenen Gegenstände

Grundsatzdokumentation (`docs/mathematik/`), Tarifpläne
(`docs/tarifplaene/`) und `configs/` gehören zur PLV, ziehen aber noch
nicht um. Ihre Abnahme bindet den Pfad: A-T1 liest das Tarifwerk des
zuletzt abgenommenen Commits unter dem heutigen Pfad (die Pfade stehen in
`models/tarifwerkabnahme.py`, gelesen in `gates/tarifwerk_belegen.py`), und
der Kernstand hasht Name und Inhalt jeder Datei. Nach einem Umzug fände A-T1 im Stand vor dem dritten Fall
weder Tarifpläne noch Configs, und das Nachfahren des Falls hielte an der
Prüfung des Tarifwerks an.

## Folgen

* Die Routinen tragen den Umzug ohne Änderung ihrer Logik. Sie finden ihre
  eigenen Dateien über ihren Ort, und im Baum vor dem Fall lesen sie nur
  Pfade, die nicht umziehen: `src/`, `configs/`, `tests/fixtures/`,
  `docs/architektur/`, `docs/mathematik/` und `docs/tarifplaene/`. Eine
  Ausnahme ist der Live-Lauf eines Falls auf dem Stand vor dem Fall: Die
  Falldatei aus `main` nennt die Lieferung unter dem neuen Pfad, der alte
  Baum trägt sie unter `lieferungen/`. Dafür nennt das ONBOARDING einen
  absoluten Pfad.
* Die Lieferungen sind bytegleich umgezogen; `.gitattributes` schützt sie
  unter dem neuen Pfad vor jeder Umwandlung von Zeilenenden.
* Das Paket des dritten Falls nennt die Lieferung unter dem neuen Pfad
  (`fall.conf`). Das README der Tarifpläne nennt den neuen Ort der
  Doku-Engine; das ändert das Tarifwerk, das Rezept hält den neuen
  Fingerabdruck und zeichnet A-T1 beim Nachfahren über diesen Stand. Keines
  der 16 erwarteten Ergebnisse des Falls nennt einen Pfad des Repositorys.
* README, `AGENTS.md`, `CONTRIBUTING.md` und die Einstiegsseiten der Ebenen
  (`system/`, `plv/`, `migrationen/`, `werkzeuge/`, `docs/`) folgen den
  Ebenen. Ein Test hält die Tabelle im README mit dem Baum zusammen
  (`tests/test_readme_gegenstaende.py`).
* Aus ADR-027 gelten weiter: keine Infrastruktur im Repository, die Regel
  für Pull Requests, der Stand von `main` und die abgenommenen Gegenstände.
* Die Schichtenkarte und die Importregeln im Paket ändern sich nicht.

## Offen

* Der Umzug der abgenommenen Gegenstände nach `plv/`. Dafür muss A-T1 das
  Tarifwerk eines älteren Commits unter dem Pfad lesen, den es in jenem
  Commit hatte, und ein bloßer Ortswechsel darf im Beleg nicht als
  „entfallen“ und „neu“ erscheinen. Danach werden Kernstand und Tarifwerk
  neu abgenommen, und das Paket des dritten Falls wird neu festgehalten.
* Die Vorlage einer Instanz unter `plv/betrieb/` (Compose, Umgebung, Dienst
  und Timer) ist nach ADR-027 Infrastruktur und dort schon als offen
  benannt. Sie bleibt, bis entschieden ist, was die Routinen davon
  brauchen.
* Skripte außerhalb des Repositorys, die alte Pfade aufrufen
  (`deploy/welt/`, `deploy/plv/`), `quellsystem` aus dem Wurzelverzeichnis
  importieren oder nach `lieferungen/` schreiben, müssen nachgezogen
  werden.
