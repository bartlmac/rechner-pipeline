## Bezug

Issue: #<Nummer> (mit `Schließt #<Nummer>`, wenn dieser Pull Request das Issue erledigt)

## Was sich ändert

<Was ändert sich, und warum? Welche Module und Verzeichnisse sind berührt?>

## Testnachweis

- Suite: `python -m pytest -q -rs -n auto --dist loadfile`
- Lauf: <wo und auf welchem Stand, zum Beispiel lokal auf Commit abc1234>
- Ergebnis: <Ergebniszeile wörtlich>, Exit-Code <0>
- Weitere Läufe, falls nötig (zum Beispiel Fall 3 nachgefahren): <Lauf und Ergebnis>

## Checkliste

- [ ] Die volle Suite ist grün (Ergebniszeile und Exit-Code stehen oben).
- [ ] Die Doku ist nachgezogen (eine Zeile im CHANGELOG oder im betroffenen Dokument), oder es steht hier, warum keine nötig ist.
- [ ] Reviewer genannt: <Konto>
- [ ] Jeder Commit trägt den Sign-off nach DCO (`git commit -s`).
- [ ] Nichts aus „Was nicht ins Repository gehört“ (CONTRIBUTING.md) ist enthalten.

## Agenten

Code aus Agenten geht denselben Weg wie jeder andere Beitrag: Ein Mensch reviewt ihn, bevor er gemergt wird. Ist dieser Pull Request ganz oder teilweise von einem Agenten geschrieben, steht hier, von welchem und in wessen Auftrag:

<Agent und Auftraggeber, oder „kein Agent“>
