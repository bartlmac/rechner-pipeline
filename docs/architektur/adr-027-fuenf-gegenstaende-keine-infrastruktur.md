# ADR-027: Fünf Gegenstände des Repositorys — keine Infrastruktur

**Status:** angenommen am 2026-10-04 (Maintainer, Entscheidung vom
2026-10-03). Was umgesetzt ist, steht unter „Folgen“, was offen ist, unter
„Offen“. Die Tabelle der Gegenstände und ihre Orte sind seit 2026-10-08
durch [ADR-028](adr-028-ordnung-nach-ebenen.md) abgelöst (Ordnung nach
Ebenen); die Pfade unten nennen den Stand vom 2026-10-04.

## Kontext

Mit dem dritten Fall der Baldrian liegt im Repository mehr als ein
Migrationssystem mit seiner Vorzeige: eine Laufzeit, die ohne jede
Migration läuft, ein festgehaltener Fall zum Nachfahren, Routinen, die
daraus eine vollständige Laufzeit aufstellen, und ein Webauftritt. Die
Rahmendokumentation kannte davon nur einen Teil.

Gemessen am Stand vom 2026-10-04:

* Zwei Einteilungen standen nebeneinander: die vier Ebenen aus ADR-017
  und ein Bild mit sieben Komponenten im README. Keine von beiden nannte
  die Routinen oder die Webseite.
* Das Bild wurde über seine Nummern zitiert, an drei Stellen außerhalb
  des README. Eine geänderte Nummer hätte sie still entwertet.
* Drei Dokumente beschrieben den Kommutations-Zweitkern anders, als der
  Code ihn führte.
* Die Einrichtung einzelner Rechner war in das Repository geraten und ist
  wieder herausgenommen.

## Entscheidung

Das Repository trägt fünf Gegenstände und keine Infrastruktur.

| | Gegenstand | Was er ist | Wo |
|---|---|---|---|
| 1 | Laufzeit der PLV | die Pfefferminzia mit ihrem eigenen Geschäft; läuft ohne Migration | `src/rechner_pipeline/kern`, `bestand`, `betrieb`; `configs/` |
| 2 | Migrationssystem | das KI-System mit seinen jeweiligen Fähigkeiten | `src/rechner_pipeline/gates`, `ontologie`, `spez`, `quellen`, `qa`, `fall.py`; die Agentenrollen unter `.claude/` und `.agents/` |
| 3 | Fall-Definitionen | was man braucht, um eine Migration durchzuspielen | `lieferungen/`, `quellsystem/`, `pakete/` |
| 4 | Routinen | deterministisch eine Migration aufspielen und die aktuelle Laufzeit erzeugen | `deploy/welt/`, `deploy/plv/` |
| 5 | Webseite | Code und Werkzeuge des Auftritts: rendern, verknüpfen | `vorzeige-seite/`, `werkzeuge/` |

**Quer zu allen fünf:** `tests/`, `docs/` (Fachdokumentation, ADRs),
`dev-docs/`, `src/rechner_pipeline/models` (Datenverträge), `deploy/dev`
und `.devcontainer` (Entwicklungsumgebung), `.github/` (Prüfläufe und
Image-Bau).

**Zusammenhang.** Das Migrationssystem arbeitet auf der Laufzeit. Die
Fall-Definitionen sind seine Eingabe. Die Routinen setzen die ersten drei
zur aktuellen Laufzeit zusammen. Die Webseite zeigt Laufzeit und Fälle nach
außen. Aus `main` allein ist die Laufzeit reproduzierbar.

**Bewusst nicht im Repository:** die laufende Instanz (Rechner, Schlüssel,
Ablage), das Hosting der Seite, die Einrichtung einzelner Rechner für eine
Vorführung oder eine Schulung, und die Regie mit Drehbüchern und
Auflösungen noch nicht gefahrener Fälle. Die PLV und die Baldrian sind
erfunden; ihre Welt wird reproduziert, nicht abgelöst.

**Regel für Pull Requests.** Mehrere Gegenstände gehen nur dann in einen
Pull Request, wenn sie eine Transaktion sind: wenn `main` mit nur einem
Teil davon unerklärt wäre. Beispiel: Rückbau, dritter Fall und Routine
kamen zusammen. Die Webseite geht nie im selben Pull Request wie die
Gegenstände 1 bis 4: Sie zieht `main` nach und wird eigenständig
veröffentlicht. Infrastruktur geht nie hinein.

## Zwei Stellen, an denen ein Verzeichnis zwei Gegenstände trägt

* `werkzeuge/` trägt die Werkzeuge der Webseite (Gegenstand 5) und vier
  Werkzeuge für den Live-Lauf eines Falls, die zum Migrationssystem
  gehören: `vorfuehrung.py`, `lagebild.py`, `aufzeichnung.py`,
  `sitzungsprobe.py`.
* `deploy/welt/` trägt die Routinen (Gegenstand 4) und die Definition des
  Falls der Vorführung (`fall-baldrian-klv-tg2015.conf`, Gegenstand 3),
  dazu zwei Inhalte der PLV, die das Aufstellen einer Welt braucht: die
  aktuarielle Stellungnahme zur T-Box und die Vorlage des Mandats.

Verschoben wird dafür nichts. Die Dokumentation sagt es an Ort und Stelle.

## Verhältnis zu ADR-017

ADR-017 bleibt in Kraft. Die beiden Einteilungen beantworten verschiedene
Fragen: Die vier Ebenen sagen, wer im Paket wen importieren darf; die
Schichtenkarte misst es je Modul. Die fünf Gegenstände sagen, was im
Repository liegt und wozu.

| Gegenstand | Ebene nach ADR-017 |
|---|---|
| 1 Laufzeit der PLV | Ebene 3 (Vorzeige); die Erzeuger von Bestand, Ereignissen und Neugeschäft darin sind Ebene 4 |
| 2 Migrationssystem | Ebene 2 (KI-Tool) |
| 3 Fall-Definitionen | Ebene 3 (Lieferung, Fall) und Ebene 4 (`quellsystem/`) |
| 4 Routinen | kommt in ADR-017 nicht vor |
| 5 Webseite | in ADR-017 „die Unternehmensseite“ als Teil der Vorzeige |
| quer | Ebene 1 (Entwickler und KI); `models` zählt ADR-017 zum Tool |

„Vorzeige“ heißt in ADR-017 das fiktive Unternehmen, nicht die Webseite.

In einem Punkt ändert dieses ADR ADR-017. Dort gilt: „Regie: Mechanik im
Repo, Auflösungen lokal“. Jetzt gilt: Die Auflösung eines **gefahrenen**
Falls liegt als Paket im Repository (`pakete/`), damit der Fall ohne
Agenten nachfahrbar ist. Die Auflösungen **noch nicht gefahrener** Fälle
bleiben lokal. Eine Sitzung, die einen festgehaltenen Fall live führt,
liest nicht in `pakete/`.

## Der Stand von `main` und die abgenommenen Gegenstände

`main` trägt den Stand **nach** dem jüngsten festgehaltenen Fall: Was der
Fall am Zielsystem gebaut hat, liegt im Code. Der Stand davor ist ein
Commit der Geschichte, den das Paket nennt (`STAND`). Die Routine stellt
die Welt auf jenem Stand auf und fährt den Fall auf dem Stand des Baums
nach.

Das Nachfahren übernimmt die Urteile der Zeichnungen des festgehaltenen
Falls. Das trägt nur, wenn der Gegenstand derselbe ist. Zwei Gegenstände
sind abgenommen und dürfen sich deshalb nicht still ändern:

* der **Kernstand** (A-K2): `src/rechner_pipeline/kern`, die eingefrorenen
  Referenzwerte, die Grundsatzdokumentation;
* das **Tarifwerk** (A-T1): `docs/tarifplaene`, die Bestands-Configs.

Ein Test hält am Baum fest, dass er diese Gegenstände so trägt wie der
festgehaltene Fall (`tests/test_pakete.py`). Wer einen davon ändert, ändert
das Zielsystem: Die Änderung braucht eine Abnahme in der Linie, und das
Paket wird auf dem neuen Stand neu festgehalten.

Offen bleibt, ob die Routine einen Fall künftig auf einem Stand nachfährt,
den das Paket selbst nennt, statt auf dem Stand des Baums. Heute nennt
`STAND` nur den Stand vor dem Fall.

## Folgen

* README, `AGENTS.md` und `CONTRIBUTING.md` folgen den fünf Gegenständen.
  Das Bild mit sieben Komponenten entfällt. Ein Test hält die Tabelle der
  Gegenstände im README mit dem Baum zusammen: Jedes Verzeichnis der
  obersten Ebene ist zugeordnet (`tests/test_readme_gegenstaende.py`).
* Der Kommutations-Zweitkern (ADR-004, ADR-013) ist kein Gegenstand. Er
  ist aus dem Paket entfernt und lebt als Zeuge der Kern-Tests
  (`tests/kommutationszeuge.py`). An ihm hängt das Äquivalenzprinzip auf
  dem produktiven Beitragspfad; deshalb bleibt er als Zeuge. Der Kern des
  Quellsystems (`quellsystem/`) ist davon unberührt: Er erzeugt die
  Lieferungen.
* Der Stand vor und der Stand nach dem dritten Fall tragen Namen: die Tags
  `fall3-vor` und `fall3-nach`.
* Ein Verzeichnis der Fälle (`docs/faelle/README.md`) und eine
  Beschreibung der Pakete (`pakete/README.md`) sagen, welche Fälle es gibt
  und was davon nachfahrbar ist.

## Offen

* `deploy/plv/` trägt neben dem Image der Laufzeit die Vorlage einer
  Instanz: `compose.yml`, `env.beispiel`, einen Dienst und einen Timer. Ein
  Timer ist Betrieb einer Instanz und damit nach diesem ADR Infrastruktur.
  Die vier Dateien bleiben vorerst, weil ein Test sie an das Image bindet
  und die Bedienfolgen in `deploy/plv/README.md` auf ihnen stehen. Zu
  entscheiden ist das zusammen mit der Frage, was von `deploy/plv/` neben
  den Routinen in `deploy/welt/` noch gebraucht wird.

## Was bewusst nicht in diesem ADR steht

* Kein Verzeichnis wird verschoben oder umbenannt.
* Die Schichten im Paket und ihre Importregeln ändern sich nicht.
