# ADR-019: Die Testsuite läuft parallel (pytest-xdist)

**Status:** angenommen am 2026-09-20 (Maintainer), umgesetzt.

## Anlass

Die Suite ist auf 2373 Tests gewachsen und braucht am Stück **20:30**.
Als Vorbedingung jedes Commits (nicht verhandelbare Regel 6) ist das
untragbar geworden: Eine Codeänderung kostet eine halbe Stunde, bevor
sie festgeschrieben werden darf, und zwei Mitwirkende verdrängen sich
auf demselben Rechner.

## Messung, nicht Schätzung

Gemessen mit `pytest --durations` auf dem Entwicklungsrechner
(28 Kerne), Stand 1f6a773:

| Was | Zeit |
|---|---|
| Volle Suite, seriell | 1230 s (20:30) |
| Volle Suite, `-n 12 --dist loadfile` | 446 s (7:25) |

Beide Läufe: 2373 passed, 0 failed — gleiche Menge, gleiches Urteil.

Die Last ist stark konzentriert. Die vierzig langsamsten Tests tragen
rund die Hälfte der Laufzeit, und sie liegen fast alle in zwei Dateien:

| Datei | Anteil in den Top 40 |
|---|---|
| `tests/test_betrieb_tageslauf.py` | 337 s |
| `tests/test_betrieb_drift_n01.py` | 151 s (ein Test) |
| `tests/test_bestand_report.py` | 63 s |

Der Grund ist kein ineffizienter Test, sondern die Sache selbst: Diese
Module fahren echte Tagesläufe und Kern-Projektionen über viele
Verträge. Sie sind teuer, weil sie etwas Teures prüfen.

## Entscheidung

`pytest-xdist` wird als **Entwicklungs-Abhängigkeit** aufgenommen,
exakt gepinnt (`pytest-xdist==3.6.1`). Die Vorgabe für den vollen Lauf
ist `-n 12 --dist loadfile`.

**Warum `--dist loadfile` und nicht `--dist load`:** `loadfile` gibt eine
ganze Testdatei an einen Arbeiter. Damit bleiben die 61
modul-gebundenen Fixtures der Suite das, was sie sind — einmal gebaut je
Modul. Mit `load` würde jeder Arbeiter, der einen Test aus einem Modul
bekommt, dessen Fixture neu bauen; bei den e2e-Ketten hieße das, die
ganze Migrationskette mehrfach zu fahren.

**Warum 12 und nicht 28:** Die Wand ist nicht die Kernzahl, sondern die
größte Datei — `loadfile` kann sie nicht teilen. Mehr Arbeiter als
teure Dateien bringen nichts und kosten Speicher; der Rechner hat heute
schon zweimal einen Lauf wegen Speicherdrucks abgebrochen.

## Warum das hier überhaupt geht

Parallelität ist in dieser Codebasis nicht selbstverständlich: Zwei
Suiten im selben Arbeitsbaum kollidieren über den Systemstand-Hash
(Betriebsbefund, deshalb die Worktree-Regel). Geprüft wurde deshalb
vorher, ob Tests untereinander kollidieren können:

* Jedes Testmodul arbeitet unter `tmp_path` bzw. `tmp_path_factory`.
* Kein Test schreibt in einen festen Repo-Pfad. Die einzige Datei ohne
  `tmp_path` ist `tests/zeichnung_fixture.py`, ein Helfer, der seinen
  Zielpfad als Argument bekommt.
* Die zwei Zugriffe auf `REPO_ROOT` in Tests sind Lesezugriffe.

Die Worktree-Regel bleibt davon unberührt: Sie gilt für zwei Suiten
in einem Baum, nicht für die Arbeiter einer Suite.

## Folgen

* `pyproject.toml`: `pytest-xdist==3.6.1` im `dev`-Extra.
* `AGENTS.md` nennt die Kommandos.
* Die Regel bleibt: volle Suite grün vor dem Commit. Sie dauert jetzt
  sieben statt zwanzig Minuten.
* Ein Test, der von der Reihenfolge anderer Tests abhängt, fällt ab
  jetzt auf — das ist ein Gewinn, kein Risiko.
* Nachtrag 2026-10-03: Die CI fährt die volle Suite ebenso parallel
  (`-n auto --dist loadfile`, so viele Arbeiter, wie der Runner Kerne
  hat). Seriell war sie dort nie entschieden, nur nie umgestellt. Mit
  der Suite nach T27 (5108 Tests) brauchte der serielle Lauf 49 bis 58
  Minuten; je Test 0,56 bis 0,71 s wie am 23.09. mit 2399 Tests in 22
  Minuten. Die Dauer wuchs mit der Testzahl, nicht mit der Last.

## Zwei Suiten auf einem Rechner: der Lock gehört in einen Aufruf

Wer neben einer anderen Session arbeitet, klammert seinen Lauf in
`flock /tmp/suite.lock`. Das allein reicht nicht — es muss ein Aufruf
sein:

    # richtig
    flock /tmp/suite.lock python -m pytest -q modul_a.py modul_b.py modul_c.py

    # falsch, obwohl jeder Aufruf den Lock nimmt
    flock /tmp/suite.lock python -m pytest -q modul_a.py
    flock /tmp/suite.lock python -m pytest -q modul_b.py
    flock /tmp/suite.lock python -m pytest -q modul_c.py

`flock` ist nicht fair: Es gibt keine Warteschlange, sondern vergibt den
Lock an irgendeinen Wartenden. Eine Folge kurzer Läufe gibt ihn jedes
Mal frei und nimmt ihn sofort wieder — für einen langen Lauf daneben
sieht das aus wie Dauerbesitz, und er verhungert.

Gemessen am 2026-09-20: Zwei Sessions, beide korrekt mit `flock`, eine
mit acht bis zehn Einzelmodul-Läufen. Der volle Lauf der anderen wartete
21 Minuten und schrieb in dieser Zeit keine Zeile. Beide Seiten hielten
sich an die Regel; die Regel war unvollständig.

## Was als Nächstes den Boden senkt

Der Boden liegt bei der größten Datei. `test_betrieb_tageslauf.py`
allein trägt über 337 s, davon rund 150 s in dreizehn
Parametrisierungen desselben Wiederanlauf-Tests, die jede für sich den
Ausgangszustand neu bauen. Ein gemeinsamer, einmal gebauter
Ausgangszustand je `zustand`-Wert — kopiert statt neu gefahren — oder
ein Schnitt der Datei in zwei Module senkt den Boden auf etwa die
Hälfte. Das ist eine eigene Änderung mit eigener Messung und steht
bewusst nicht in diesem ADR.

## Verworfene Alternativen

**Die volle Suite vor dem Commit aufgeben.** Sie ist die einzige
Zusicherung, die in dieser Codebasis nicht umgangen werden kann; sie zu
lockern hätte genau die Sorte Lücke erzeugt, die diese Runde
mehrfach gefunden hat.

**Nur Teilläufe nach Impact.** `ontologie.impact` rechnet geänderte
Dateien auf betroffene Testmodule um und gibt fertige `pytest_args`
aus — ein sehr gutes Werkzeug für die Schleife beim Bauen, aber keine
Commit-Vorbedingung: Es kennt Import- und Knoten-Kanten, nicht jede
Wirkung.

**Tests löschen oder zusammenlegen.** Die teuren Module prüfen die
teuren Aussagen (Tagesläufe, Wiederanlauf an jeder Naht,
Kern-Projektionen). Sie sind nicht das Problem, sie sind der Zweck.
