# Künstliche Intelligenz in unseren Migrationen

Unsere Bestandsübernahmen werden von KI-Agenten vorbereitet. Sie lesen
die gelieferten Unterlagen, rechnen nach und legen vor. Urteilen tun
sie nicht: Das tun Prüfstrecken, die deterministisch laufen. Und
zeichnen tun sie erst recht nicht: Das tun Menschen, je Abnahme die
zuständige Rolle.

Diese Seite sagt, was die Agenten bei uns dürfen, und zeigt an der
Übernahme Baldrian, wie es aussieht.

## Was ein Agent darf und was nicht {#was-agenten-duerfen}

Der Unterschied zwischen Vorschlag und Urteil ist bei uns keine
Hausregel, sondern in der Bauart festgelegt: Ein Agent kann einen Lauf
ablehnen, aber keinen freigeben. Eine Freigabe braucht einen Schlüssel,
und Schlüssel haben Menschen. Wer gezeichnet hat, wird nicht behauptet,
sondern aus dem Schlüssel bestimmt, und jeder Entscheid-Snapshot trägt
Rolle und Schlüsselklasse. Ob je eine Agentenrolle einen Entscheid
trägt, ist an den Snapshots gemessen, nicht behauptet — die Antwort
muss nein lauten.

## Wer legt vor, wer zeichnet {#rollen}

Das KI-Werkzeug arbeitet mit Agentenrollen, versioniert mit Aufgabe,
Fähigkeiten und Werkzeugliste; die Liste unten ist aus den Definitionen
erhoben, nicht abgeschrieben. Jeder Agentenrolle steht eine menschliche
Rolle des Unternehmens gegenüber, die zeichnet — mit demselben Namen,
damit die Paarung ablesbar ist. Den Auftrag eines Falls zeichnet der
Vorstand; ihm steht kein Agent gegenüber. Danach: welche Fähigkeiten eine
Rolle hat (das sagt ihre Definition), womit das System die Unterlagen
liest, und welche Rolle welches Gate zeichnet — für die Gates der
Übernahme Baldrian sagt es der jeweilige Entscheid-Snapshot selbst.

{{html:rollen}}

Wo die Rollen im Ablauf stehen, zeigt [Der Prozess in dreizehn Stationen](./#prozess).

## Wie ein Gate heißt {#kennung}

Eine Bestandsübernahme durchläuft bei uns Stationen, und an den meisten
sitzt ein Gate. Sein Name ist eine Kennung aus vier Teilen:

<div class="kennung-zerlegung">
<span class="teil"><b>P</b><small>1</small></span><span class="trenner">-</span><span class="teil"><b>Q</b><small>2</small></span><span class="teil"><b>3</b><small>3</small></span><span class="trenner">.</span><span class="teil"><b>fachliche-pruefung</b><small>4</small></span>
</div>
<ol class="kennung-legende">
<li><b>Art</b>, wer entscheidet: P Prüfung durch das Programm · A Abnahme durch einen Menschen</li>
<li><b>Gegenstand</b>: Q Quellen · K Rechenkern · B Bestand · M Migration als Ganzes</li>
<li><b>Nummer</b>, laufend innerhalb des Gegenstands</li>
<li><b>Fachliche Kennung</b>, so steht sie im Ledger</li>
</ol>

Vor dem Bindestrich steht, wer entscheidet: **P** für eine Prüfung durch
das Programm, deterministisch, sie blockiert bei Rot; **A** für eine
Abnahme durch einen Menschen, der entscheidet und zeichnet, das Gate
erzeugt die Vorlage und hält den signierten Entscheid. Dahinter der
Gegenstand: **Q** Quellen, **K** Rechenkern, **B** Bestand, **M** die
Migration als Ganzes. Die Ziffer nummeriert innerhalb des Gegenstands.

Das Kontrastpaar macht die erste Stelle sofort verständlich: P-Q3 prüft
die Quellen maschinell, A-Q1 nimmt sie ab, gleicher Gegenstand, andere
Art, dort entscheidet und zeichnet ein Mensch. Die Nummern haben Lücken,
und das ist gewollt: Ein abgeschaltetes Gate hinterlässt eine Lücke, es
rückt nichts nach, sonst entstünde genau die Verwechslung, die diese
Ordnung abschaffen soll. Deshalb gibt es A-M1 und A-M4, und A-M2 und
A-M3 dazwischen sind eigene Gates.

## An einer gefahrenen Übernahme {#beispiel}

Wie das bei der Übernahme Baldrian aussieht — an jeder
Station das Gate, was es prüft, was es hinterlässt und was der Lauf dort
ergab —, zeigt [Die Übernahme Baldrian](baldrian/): eine Seite, von der
Lieferung bis zum Zugang in die Bücher, mit den Zahlen und Belegen jeder
Station.

## Feststellungen des Aktuariats {#feststellungen}

Die Feststellungen zu den gelieferten Unterlagen und die Entscheidung zu
jeder Diskrepanz stehen auf der Seite der Übernahme an der Station
[Quellen abnehmen](baldrian/#der-widerspruch), mit beiden Lesarten und
dem Dossier, das der Agent dafür vorgelegt hat; was sich durch die
Übernahme an Rechenkern und Tarifwerk geändert hat, unter [Was sich am
System änderte](baldrian/#umbau).

Zurück zum Verfahren: [Bestandsmigrationen](./).
