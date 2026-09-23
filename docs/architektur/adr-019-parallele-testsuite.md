# ADR-019: Die Testsuite laeuft parallel (pytest-xdist)

**Status:** angenommen, 2026-09-20
**Entscheidung des Maintainers**, umgesetzt in der dev-Session.

## Anlass

Die Suite ist auf 2373 Tests gewachsen und braucht am Stueck **20:30**.
Als Vorbedingung JEDES Commits (nicht verhandelbare Regel 6) ist das
untragbar geworden: Eine Codeaenderung kostet eine halbe Stunde, bevor
sie festgeschrieben werden darf, und zwei Mitwirkende verdraengen sich
auf demselben Rechner.

## Messung, nicht Schaetzung

Gemessen mit `pytest --durations` auf dem Entwicklungsrechner
(28 Kerne), Stand 1f6a773:

| Was | Zeit |
|---|---|
| Volle Suite, seriell | 1230 s (20:30) |
| Volle Suite, `-n 12 --dist loadfile` | 446 s (7:25) |

Beide Laeufe: 2373 passed, 0 failed — gleiche Menge, gleiches Urteil.

Die Last ist stark konzentriert. Die vierzig langsamsten Tests tragen
rund die Haelfte der Laufzeit, und sie liegen fast alle in zwei Dateien:

| Datei | Anteil in den Top 40 |
|---|---|
| `tests/test_betrieb_tageslauf.py` | 337 s |
| `tests/test_betrieb_drift_n01.py` | 151 s (EIN Test) |
| `tests/test_bestand_report.py` | 63 s |

Der Grund ist kein ineffizienter Test, sondern die Sache selbst: Diese
Module fahren echte Tagesläufe und Kern-Projektionen ueber viele
Vertraege. Sie sind teuer, weil sie etwas Teures pruefen.

## Entscheidung

`pytest-xdist` wird als **Entwicklungs-Abhaengigkeit** aufgenommen,
exakt gepinnt (`pytest-xdist==3.6.1`). Die Vorgabe fuer den vollen Lauf
ist `-n 12 --dist loadfile`.

**Warum `--dist loadfile` und nicht `--dist load`:** `loadfile` gibt eine
ganze Testdatei an EINEN Arbeiter. Damit bleiben die 61
modul-gebundenen Fixtures der Suite das, was sie sind — einmal gebaut je
Modul. Mit `load` wuerde jeder Arbeiter, der einen Test aus einem Modul
bekommt, dessen Fixture neu bauen; bei den e2e-Ketten hiesse das, die
ganze Migrationskette mehrfach zu fahren.

**Warum 12 und nicht 28:** Die Wand ist nicht die Kernzahl, sondern die
groesste Datei — `loadfile` kann sie nicht teilen. Mehr Arbeiter als
teure Dateien bringen nichts und kosten Speicher; der Rechner hat heute
schon zweimal einen Lauf wegen Speicherdrucks abgebrochen.

## Warum das hier ueberhaupt geht

Parallelitaet ist in dieser Codebasis nicht selbstverstaendlich: Zwei
Suiten im selben Arbeitsbaum kollidieren ueber den Systemstand-Hash
(Betriebsbefund, deshalb die Worktree-Regel). Geprueft wurde deshalb
vorher, ob TESTS untereinander kollidieren koennen:

* Jedes Testmodul arbeitet unter `tmp_path` bzw. `tmp_path_factory`.
* Kein Test schreibt in einen festen Repo-Pfad. Die einzige Datei ohne
  `tmp_path` ist `tests/zeichnung_fixture.py`, ein Helfer, der seinen
  Zielpfad als Argument bekommt.
* Die zwei Zugriffe auf `REPO_ROOT` in Tests sind Lesezugriffe.

Die Worktree-Regel bleibt davon unberuehrt: Sie gilt fuer ZWEI SUITEN
in einem Baum, nicht fuer die Arbeiter EINER Suite.

## Folgen

* `pyproject.toml`: `pytest-xdist==3.6.1` im `dev`-Extra.
* `AGENTS.md` nennt die Kommandos.
* Die Regel bleibt: volle Suite gruen VOR dem Commit. Sie dauert jetzt
  sieben statt zwanzig Minuten.
* Ein Test, der von der Reihenfolge anderer Tests abhaengt, faellt ab
  jetzt auf — das ist ein Gewinn, kein Risiko.

## Zwei Suiten auf einem Rechner: der Lock gehoert in EINEN Aufruf

Wer neben einer anderen Session arbeitet, klammert seinen Lauf in
`flock /tmp/suite.lock`. Das allein reicht nicht — es muss EIN Aufruf
sein:

    # richtig
    flock /tmp/suite.lock python -m pytest -q modul_a.py modul_b.py modul_c.py

    # falsch, obwohl jeder Aufruf den Lock nimmt
    flock /tmp/suite.lock python -m pytest -q modul_a.py
    flock /tmp/suite.lock python -m pytest -q modul_b.py
    flock /tmp/suite.lock python -m pytest -q modul_c.py

`flock` ist NICHT fair: Es gibt keine Warteschlange, sondern vergibt den
Lock an irgendeinen Wartenden. Eine Folge kurzer Laeufe gibt ihn jedes
Mal frei und nimmt ihn sofort wieder — fuer einen langen Lauf daneben
sieht das aus wie Dauerbesitz, und er verhungert.

Gemessen am 2026-09-20: Zwei Sessions, beide korrekt mit `flock`, eine
mit acht bis zehn Einzelmodul-Laeufen. Der volle Lauf der anderen wartete
21 Minuten und schrieb in dieser Zeit keine Zeile. Beide Seiten hielten
sich an die Regel; die Regel war unvollstaendig.

## Was als Naechstes den Boden senkt

Der Boden liegt bei der groessten Datei. `test_betrieb_tageslauf.py`
allein traegt ueber 337 s, davon rund 150 s in dreizehn
Parametrisierungen desselben Wiederanlauf-Tests, die jede fuer sich den
Ausgangszustand neu bauen. Ein gemeinsamer, einmal gebauter
Ausgangszustand je `zustand`-Wert — kopiert statt neu gefahren — oder
ein Schnitt der Datei in zwei Module senkt den Boden auf etwa die
Haelfte. Das ist eine eigene Aenderung mit eigener Messung und steht
bewusst nicht in diesem ADR.

## Verworfene Alternativen

**Die volle Suite vor dem Commit aufgeben.** Sie ist die einzige
Zusicherung, die in dieser Codebasis nicht umgangen werden kann; sie zu
lockern haette genau die Sorte Luecke erzeugt, die diese Runde
mehrfach gefunden hat.

**Nur Teillaeufe nach Impact.** `ontologie.impact` rechnet geaenderte
Dateien auf betroffene Testmodule um und gibt fertige `pytest_args`
aus — ein sehr gutes Werkzeug fuer die Schleife beim Bauen, aber keine
Commit-Vorbedingung: Es kennt Import- und Knoten-Kanten, nicht jede
Wirkung.

**Tests loeschen oder zusammenlegen.** Die teuren Module pruefen die
teuren Aussagen (Tagesläufe, Wiederanlauf an jeder Naht,
Kern-Projektionen). Sie sind nicht das Problem, sie sind der Zweck.
