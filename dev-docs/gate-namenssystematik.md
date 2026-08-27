# Gate-Namen: Bestandsaufnahme und Systematik

**Stand:** Vorschlag zur Durchsprache, 27.08.2026.
**Auftrag:** Rückmeldung zum Abnahmebericht, Punkt N3 — die Gate-Namen
wirken zufällig und technisch; gewünscht ist eine Systematik.
**Status:** Bestandsaufnahme fertig, Systematik ist ein Vorschlag.

## 1 Was heute da ist

| Name | Wo | Art | Gegenstand |
|---|---|---|---|
| `G0.extraction-manifest` | `gates/extract.py` | maschinell | Vorverdichtung eines Quell-Werks |
| `O0.abox-merge` | `gates/abox_merge.py` | maschinell | Zusammenführung der Fragmente |
| `O1.abox-contract` | `gates/abox_validate.py` | maschinell | A-Box gegen Contract und Register |
| `O3` | `gates/generation_golden.py` | maschinell | Kern gegen die Tarif-Spez |
| `B1.bestand-contract` | `gates/bestand_validate.py` | maschinell | Bestandsabzug gegen Contract |
| `GA-vorlage.aktuarieller-test` | `gates/aktuartest.py` | Vorlage | aktuarieller Test |
| `G2-vorlage.migrationsabnahme` | `gates/abnahmebericht.py` | Vorlage | Migrationscontrolling |
| `G-1`, `G-A`, `G-2`, `G-T`, `G-K` | `fall.py`, Entscheide | menschlich | Abnahmen |

Sieben Bildungsregeln für acht Namen. Die Befunde im Einzelnen:

**Der Buchstabe sagt nichts.** `G` steht bei `G0` für eine maschinelle
Prüfung, bei `G-1` für eine menschliche Abnahme und bei `G2-vorlage` für
die Zuarbeit zu einer Abnahme. Drei verschiedene Dinge, ein Buchstabe.

**Ein Bindestrich trennt zwei Welten.** `G-2` ist die menschliche
Abnahme des Migrationscontrollings. `G2.static-security` war die
statische Sicherheitsprüfung der abgeschalteten Vergleichskern-Kette
(ADR-006). In `runs/diagnostics/security.gate.json` liegt noch ein
Beleg davon vom 17.08. — erzeugt von Code, den es nicht mehr gibt.
Zwei völlig verschiedene Prüfungen, deren Namen sich um ein Zeichen
unterscheiden.

**Die Nummern haben keine gemeinsame Achse.** `O0`, `O1`, `O3` — kein
`O2`, ohne dass irgendwo stünde, was es war. `B1` ohne `B2`. `G0` ohne
`G1` in derselben Familie (`G-1` ist etwas anderes).

**Die Vorlagen doppeln.** `GA-vorlage.aktuarieller-test` erzeugt die
Vorlage für Gate `G-A`. Zwei Schreibweisen desselben Gates in einem
System, das seine Belege über genau diese Namen bindet.

**Die Suffixe mischen Sprachen.** `.abox-contract` und
`.extraction-manifest` sind Werkzeugsprache; `.aktuarieller-test` und
`.migrationsabnahme` sind Unternehmenssprache. Ein Prüfer, der die
Ledger liest, sieht beides nebeneinander.

## 2 Was ein Gate-Name leisten muss

Die Namen stehen in signierten Belegen und in den Belegrollen, die ein
Gate für ein späteres pinnt. Wer einen Beleg liest, muss ohne
Nachschlagen erkennen: Entscheidet hier eine Maschine oder ein Mensch?
Worüber? Und wo in der Reihenfolge steht das?

Genau das leisten die heutigen Namen nicht.

## 3 Vorschlag

Zwei Achsen, beide im Namen sichtbar:

```
<Art>-<Gegenstand><Nummer>.<fachliche Kennung>
```

**Art** — wer entscheidet:

| | |
|---|---|
| `P` | Prüfung. Maschinell, deterministisch, blockiert bei Rot. Kein Mensch beteiligt. |
| `A` | Abnahme. Ein Mensch entscheidet und zeichnet; das Gate erzeugt die Vorlage und hält den Snapshot. |

Damit verschwindet die Doppelung: Es gibt kein Vorlage-Gate neben einem
Abnahme-Gate mehr, sondern **ein** Gate `A-...`, dessen Kommando die
Vorlage erzeugt und dessen Entscheid der Mensch fällt. Das entspricht
auch der Wirklichkeit im Code — `gate_entscheid` rechnet das Verdikt der
Vorlage ohnehin nach.

**Gegenstand** — worüber:

| | |
|---|---|
| `Q` | Quellen und Ontologie (Extraktion, A-Box, Register) |
| `K` | Rechenkern (Spez, Parametrierung, Golden Master) |
| `B` | Bestand (Abzug, Transformation, Fortschreibung) |
| `M` | Migration als Ganzes (aktuarielle Abnahme, Controlling) |

**Nummer** — Reihenfolge innerhalb des Gegenstands, lückenlos.

**Fachliche Kennung** — in Unternehmenssprache, weil Prüfer und Revision
die Belege lesen.

### So sähe die Landschaft aus

| heute | künftig |
|---|---|
| `G0.extraction-manifest` | `P-Q1.quellfragment` |
| `O0.abox-merge` | `P-Q2.zusammenfuehrung` |
| `O1.abox-contract` | `P-Q3.fachliche-pruefung` |
| `O3` | `P-K1.generations-golden-master` |
| `B1.bestand-contract` | `P-B1.bestandspruefung` |
| `GA-vorlage.aktuarieller-test` + `G-A` | `A-M1.aktuarieller-test` |
| `G2-vorlage.migrationsabnahme` + `G-2` | `A-M2.migrationscontrolling` |
| `G-1` | `A-Q1.quellenabnahme` |
| `G-T` | `A-K1.tarifgeneration` |

Die Reihenfolge-Erzwingung wird damit lesbar: `A-M1` vor `A-M2` ist
sichtbar dieselbe Kette, die ADR-010 fordert. Heute muss man wissen, dass
`G-A` vor `G-2` kommt.

Für die drei Tests aus dem AT-Konzept wäre es `A-M1a`, `A-M1b`, `A-M1c`
oder eine eigene Nummerierung — das entscheidet sich mit dem
AT-Konzept, nicht hier.

## 4 Der Haken, und was ich vorschlage

**Gate-Namen stehen in signierten Belegen.** Ein Rename bricht jede
bestehende Kette: Die Snapshots tragen den Namen, die Belegrollen binden
darüber, die Signatur deckt ihn mit ab. Für einen echten Bestand wäre das
ein Verlust der Nachweiskette — genau das, was das System verhindern
soll.

Deshalb schlage ich **nicht** vor, alles umzubenennen. Sondern:

1. **Verbindlich für neue Gates.** Die drei AT-Gates sind die nächsten,
   die entstehen — sie bekommen die Systematik von Anfang an. Das ist der
   Punkt, an dem die Entscheidung ohnehin fällt.
2. **Zwei Korrekturen sofort**, weil sie Verwechslung erzeugen: die
   Doppelschreibweise `GA-vorlage` / `G-A` und `G2-vorlage` / `G-2`
   zusammenführen. Beide sind noch nicht in einer echten, signierten
   Kette — es gibt bisher keinen produktiven Migrationsfall.
3. **Ein Register.** Eine Tabelle wie die in Abschnitt 1, gepflegt an
   einer Stelle, die die alten Namen mitführt und auf die neuen abbildet.
   Wer einen alten Beleg liest, findet die Zuordnung.
4. **Die tote Kette wegräumen.** `G0-G8` ist seit ADR-006 überholt; das
   verwaiste Artefakt in `runs/diagnostics/` stammt aus einem Kommando,
   das es nicht mehr gibt. Solange die Namen in der Doku stehen, sehen
   sie aus wie Teil des Systems.

## 5 Offene Entscheidungen für die Durchsprache

**N1 — Lohnt sich die Umstellung überhaupt?** Der Nutzen ist Lesbarkeit
für Prüfer und Revision. Der Preis ist eine Namensmigration in einem
System, das seine Namen signiert. Mein Vorschlag oben ist der
Mittelweg — aber wenn du sagst, das Register allein reicht und die alten
Namen bleiben, ist das eine vertretbare Antwort.

**N2 — `P` und `A` als Buchstaben.** Sie sind deutsch (Prüfung,
Abnahme) und kollidieren nicht mit den vorhandenen. Falls dir die
Herkunft der Buchstaben wichtig ist: `G` für Gate ist im Team
eingeführt, aber es ist gerade der Buchstabe, der heute drei Dinge
bedeutet.

**N3 — Die Nummerierung.** Lückenlos innerhalb des Gegenstands heißt: Ein
abgeschaltetes Gate hinterlässt eine Lücke, oder alle folgenden rutschen
nach. Ich schlage die Lücke vor (mit Vermerk im Register), weil
Nachrutschen dieselbe Verwechslung erzeugt, die wir gerade abschaffen.
