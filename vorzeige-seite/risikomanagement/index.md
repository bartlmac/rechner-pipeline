<link rel="stylesheet" href="../assets/stil.css">
<div class="banderole">Fiktives Unternehmen — eine Vorführung agentischer
Bestandsmigration. <a href="../">Zur Startseite.</a></div>

# Risikomanagement

Eine Bestandsmigration ist vor allem ein Änderungsrisiko: Ein fremder
Bestand, ein fremdes Datenmodell und ein System, das während des
Vorhabens selbst weiterentwickelt wird. Unsere Antwort sind drei
Schranken, die nicht empfehlen, sondern erzwingen.

## Menschliche Entscheide, kryptographisch gezeichnet

Kein Agent nimmt etwas ab. Jede Abnahme ist ein menschlicher
Entscheid, HMAC-signiert mit einem Schlüssel außerhalb des Falls und
an die Prüfsummen genau der Artefakte gebunden, auf denen entschieden
wurde — ein Fall kann seine eigene Freigabe nicht behaupten
([ADR-008](../it/architektur/adr-008-signierte-p9-freigaben.html)).
Sichtbar in jedem [Migrationsbericht](../migrationen/), Entscheid für
Entscheid mit Schlüssel-Fingerabdruck.

## Umbaubudget und Stolperdrähte

Wer einen Migrationsfall löst, darf das System erweitern — was er
nicht soll, ist es nebenbei durch ein anderes ersetzen. Deshalb wird
der Umfang jedes Fall-Laufs gemessen: Löschen wiegt schwerer als
Hinzufügen (Hinzufügen ist der Auftrag, Löschen ist Ersetzen), die
Löschbudgets sind je Schicht getrennt, und geänderte Referenzwerte
oder neue Kanten im Schichtgefüge reißen einen Stolperdraht.
**Überschreiten ist erlaubt, Verschweigen nicht** — ohne begründeten
Satz endet die Messung mit Befund, und der Satz steht im Bericht. Die
Messung des aktuellen Falls:
[umbaubudget.json](../migrationen/baldrian/artefakte/abgeleitet/berichte/umbaubudget.json).

## Prüfung ohne Glättung

Das Migrationscontrolling prüft den ganzen Bestand über zwei
Stichtage. Ein Wert, der nicht nachgerechnet werden kann, ist eine
ausgewiesene **Prüflücke**, kein geschätzter Ersatz — ein geglätteter
Wert wäre eine Behauptung ohne Rechnung. Ein Lauf mit Befund wird
genauso dargestellt wie ein grüner: Ein Bericht, der nur den
Erfolgsfall zeigen könnte, wäre eine Werbebroschüre. Das Ergebnis der
aktuellen Tranche steht im
[Abnahmebericht](../migrationen/baldrian/).
