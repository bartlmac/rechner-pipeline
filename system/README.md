# System

Das Migrationssystem: Es führt einen Migrationsfall vom Auftrag bis in die
Ablage, mit Agenten für die Vorarbeit und deterministischem Code für alles,
was geprüft und abgenommen wird
([ADR-028](../docs/architektur/adr-028-ordnung-nach-ebenen.md)).

| Was | Wo |
|---|---|
| Quellen vorverdichten, Aussagen mit Herkunft führen, Tarife parametrieren, prüfen und abnehmen | `src/rechner_pipeline/quellen`, `src/rechner_pipeline/ontologie`, `src/rechner_pipeline/spez`, `src/rechner_pipeline/qa`, `src/rechner_pipeline/gates`, `src/rechner_pipeline/fall.py` |
| die Rollen der Agenten und ihre Skills | `.claude/agents/`, `.claude/skills/`, gespiegelt in `.agents/` |
| Architektur und Entscheidungen | [docs/architektur/](../docs/architektur/README.md) |
| die Vorlage des Migrationskonzepts | [migrationskonzept/](migrationskonzept/README.md) |
| Werkzeuge für den Live-Lauf eines Falls | `vorfuehrung.py`, `lagebild.py`, `aufzeichnung.py`, `sitzungsprobe.py` (hier) |

| Werkzeug | Zweck |
|---|---|
| `vorfuehrung.py` | einen Fall in tmux führen: Cockpit und je Agentenrolle ein Fenster |
| `lagebild.py` | wo ein Fall steht: die Anzeigen der Vorführung, nur lesend |
| `aufzeichnung.py` | die Vorführung mitschneiden und als asciicast ausgeben |
| `sitzungsprobe.py` | ob ein Agenten-Werkzeug die Sitzungen der Vorführung trägt |

## Einen Fall vorführen und aufzeichnen

```
python system/vorfuehrung.py --fall faelle/<fall> --linie <linie> --stand <ablage> --modell <modell>
tmux attach -t vorfuehrung
```

Baut die tmux-Session `vorfuehrung`:

| Fenster | links | rechts |
|---|---|---|
| `cockpit` | Chat mit dem Programmleitungs-Agenten | Lebenslauf des Falls, die letzten Entscheide, Systemstand und Laufzeit |
| `aktuariat`, `architektur`, `rechenkern`, `betrieb` | Chat mit dem Agenten der Rolle | ihre Gates mit Stand und Belegen |
| `mensch` | leere Shell für die Zeichnungen | |

Die Fenster folgen den Agentendateien unter `.claude/agents/`; eine neue
Rolle bekommt ihr Fenster ohne Änderung am Werkzeug. Die Chats starten mit
`claude --agent <rolle> --model <modell>`; `--modell` ist Pflicht und hat
keine Vorgabe (sonst erbte jeder der fünf Chats das Modell des Kontos).
`--ohne-chat` baut nur das Gerüst (Probe) und braucht kein Modell,
`--trocken` gibt die tmux-Kommandos aus. Eine Session gleichen Namens wird
nie ersetzt.

Gezeichnet wird im Fenster `mensch`, nie in einem Agentenfenster: Ein Agent
zeichnet keine Annahme, und die Schlüssel liegen außerhalb des Falls.

Die Anzeigen rechts sind `system/lagebild.py` unter `watch`:

```
python system/lagebild.py lebenslauf --fall faelle/<fall> --linie <linie>
python system/lagebild.py entscheide --fall faelle/<fall> --linie <linie> -n 12
python system/lagebild.py system --linie <linie> --stand <ablage>
python system/lagebild.py rolle <rolle> --fall faelle/<fall> --linie <linie>
python system/lagebild.py zugangsprobe --fall faelle/<fall>
```

Das Lagebild ist eine Anzeige, kein Urteil. Es liest die Entscheid-Snapshots
ohne Schlüssel und prüft weder Signatur noch Rolle noch Beleg; das tun
die Gates. Zwei Spitzen einer Kette zeigt es als `mehrdeutig`, eine nicht
lesbare Datei als `unlesbar`, nie als `offen`.

Die Sicht `zugangsprobe` ist keine der Anzeigen rechts: Sie zeigt den Beleg
der Zugangsprobe als Lesefassung für die Zugangsabnahme A-B2 (Urteil,
Folgetermin und je Vergleich Soll, Ist und Differenz), ohne die Prüfsummen
der Abschlüsse, die den Beleg selbst unlesbar groß machen. „Bestanden“
steht dort nur, wenn der Beleg es wörtlich sagt; ein Vergleich ohne Soll
ist als solcher ausgewiesen.

### Aufzeichnen

Aufgenommen wird mit `script` aus util-linux; auf dem Host wird dafür
nichts installiert. tmux zeichnet das Layout selbst, die Aufnahme enthält
also alle Panes.

```
python system/aufzeichnung.py aufnehmen --session vorfuehrung --out runs/fall3
python system/aufzeichnung.py cast --basis runs/fall3
scriptreplay -T runs/fall3.tim -O runs/fall3.out
```

`aufnehmen` hängt sich an die Session und endet mit dem Abhängen
(`Ctrl-b d`); die Session läuft weiter. `cast` erzeugt `runs/fall3.cast`
im asciicast-Format (Version 2): klein, der Text bleibt kopierbar, die
Wiedergabe läuft in jedem asciinema-Player, im Terminal oder im Browser.
Die Terminalgröße kommt aus der Kopfzeile der Aufnahme und wird nie
geraten. `scriptreplay` spielt die Aufnahme ohne jedes weitere Programm ab.

Ein GIF oder Video entsteht aus der `.cast`-Datei mit `agg` und `ffmpeg`,
auf einem beliebigen Rechner oder in einem Container:

```
agg runs/fall3.cast fall3.gif
ffmpeg -i fall3.gif -movflags faststart -pix_fmt yuv420p fall3.mp4
```

Eine Aufnahme zeigt, was auf dem Bildschirm steht. Schlüsseldateien werden
nur als Pfad genannt, nie ausgegeben; `runs/` ist nicht versioniert.

### Trägt ein Agenten-Werkzeug die Sitzungen?

Die Chats der Vorführung starten mit Claude Code. Soll ein anderes
Agenten-Werkzeug die Rollen führen (oder ein Fall ohne Menschen an jeder
Station laufen, sodass eine Sitzung der anderen Aufträge ins Fenster
schreibt), zeigt eine Probe in wenigen Minuten, ob das trägt:

```
python system/sitzungsprobe.py probe --kommando "<start eines chats>" \
    [--session sitzungsprobe] [--bericht runs/sitzungsprobe.md]
```

Sie baut eine eigene tmux-Session mit zwei Fenstern, startet in beiden das
Werkzeug und prüft vier Schritte: START (es kommt zur Ruhe), EINGABE (eine
von außen geschriebene Zeile wird beantwortet), RUHE (von außen erkennbar,
wann die Sitzung fertig ist) und WEITERGABE (eine Sitzung schreibt der
anderen auf Auftrag eine Zeile ins Fenster). Der Bericht nennt je Schritt das
Urteil, die Zeilen, an denen man „arbeitet noch“ sieht, und die Bildschirme,
auch den einer Rückfrage oder einer Sandbox, an der die Weitergabe hängt.

Die Probe urteilt nach dem Bildschirm und kostet zwei kurze Chats mit
zusammen drei Einzeilern. Sie ersetzt nie eine bestehende Session und lässt
ihre eigene stehen (`tmux kill-session -t sitzungsprobe`).
