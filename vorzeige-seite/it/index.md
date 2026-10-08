# IT und Architektur

Dieselbe Eingabe ergibt dasselbe Ergebnis, und unsere Prüfungen liegen
offen. Diese Seite zeigt, wie die Systeme der Pfefferminzia
Lebensversicherung AG gebaut sind und woran sie sich prüfen lassen.

## Dasselbe Ergebnis, jedes Mal {: #reproduzierbar }

Reproduzierbarkeit ist bei uns keine Eigenschaft einzelner Programme,
sondern der Bauart. Jeder Lauf bekommt seine Eingaben mit Prüfsumme und
hinterlässt ein Protokoll; jede Prüfung schreibt ihr Urteil in ein
Ledger; jeder menschliche Entscheid wird an die Prüfsummen genau der
Belege gebunden, auf denen entschieden wurde. Ein Ergebnis lässt sich
deshalb nicht nur wiederholen, sondern auch zurückverfolgen — bis zu der
Datei, aus der es stammt.

Was daraus folgt, ist unbequem und gewollt: Ein Wert, der sich nicht
nachrechnen lässt, wird als Prüflücke ausgewiesen und nicht geschätzt.
Ein Lauf, dessen Eingaben sich geändert haben, gilt als anderer Lauf.

## Techstack {: #techstack }

[Techstack](techstack.html) — Sprache, Bibliotheken, Versionen.
