---
title: "Tarifplan KLV — Kapitallebensversicherung (Zielrechenkern)"
lang: de
format:
  typst:
    papersize: a4
---

> Tarifplan des **Zielrechenkerns** (`rechner_pipeline.kern`, ab Version
> 2.0.0): die **Ausgestaltung** dieses Produkts. Das gemeinsame
> Rückgrat — Zustandsraum, Thiele-Rekursion, Rechnungsgrundlagen-Schicht,
> Numerik — steht einmal in der
> [Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md) und
> wird hier nicht wiederholt; die
> Gliederung ist für alle Produkte des Kerns dieselbe. Historische
> Provenienz: einmalige
> Migration aus dem Quell-Workbook (Übersetzungsbeleg: 617/617 am
> 22.07.2026 — historisch, kein laufender Referenzwert); Quellnamen
> der Größen (`Bxt`, `kVx_MRV`, …) sind bewusst erhalten
> (Provenienz-Prinzip).

# 1 Produktbeschreibung

Gemischte Kapitallebensversicherung (KLV): Die Versicherungssumme $S$
wird beim Tod der versicherten Person während der Versicherungsdauer
$n$, spätestens bei Erleben des Ablaufs fällig. Beitragszahlung über
$t \le n$ Jahre, unterjährige Zahlweise $zw \in \{1, 2, 4, 12\}$
möglich.

# 2 Zustandsmodell

Zwei Zustände, ein Übergang:

| Zustand | Bedeutung |
|---|---|
| `aktiv` | versicherte Person lebt; Vertrag in Kraft |
| `tot` | absorbierend |

| Übergang | Wahrscheinlichkeit | Rechnungsgrundlage |
|---|---|---|
| aktiv $\to$ tot | Sterblichkeit $q_x$ | `tafel`, `sex` |

Der Verbleib ist das Residuum $1 - q_x$; eine Dauerabhängigkeit gibt es
nicht (Markov, Select-Periode 0).

# 3 Bewertung

Die Bewertungsgleichung ist nicht produktspezifisch: Zustandsraum,
Thiele-Rückwärtsrekursion, Fälligkeits- und Diskontierungskonventionen
stehen in der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitte 3 und 4.

Für dieses Produkt entfällt die Dauerabhängigkeit ($d_{\max} = 0$,
Markov). Zusätzlich existiert eine Kommutations-Vergleichsschiene: Der
klassische Zweitkern (`rechner_pipeline.kommutationskern`) rechnet
dasselbe Produkt auf dem alten Weg, ausschließlich als Kreuz-Check
(`qa/ueberleitung`).

# 4 Zahlungsprofile

Die klassischen Barwert-Bausteine sind die Barwerte je eines
Zahlungsprofils auf demselben Zustandsmodell. Für Alter $y$, Dauer $m$
und Überlebenswahrscheinlichkeiten
${}_{j}p_y = \prod_{k<j}(1 - q_{y+k})$:

| Baustein | Zahlungsprofil | Barwert |
|---|---|---|
| $\ddot a_{y:m}$ | $z(\text{aktiv}, j) = 1$ für $j < m$ | $\sum_{j<m} v^j \, {}_j p_y$ |
| $A^{1}_{y:m}$ | $u(\text{aktiv}, \text{tot}, j) = 1$ | $\sum_{j<m} v^{j+1} \, {}_j p_y \, q_{y+j}$ |
| $E_{y:m}$ | Erlebensfall-Leistung bei $j = m$ | $v^m \, {}_m p_y$ |

Gemischte Versicherung: $A_{y:m} = A^{1}_{y:m} + E_{y:m}$. Unterjährige
Zahlweise über das Abzugsglied $ab(k)$ (VBA-treu):
$\ddot a^{(k)}_{y:m} = \ddot a_{y:m} - ab(k)\,(1 - E_{y:m})$.

# 5 Beiträge

Je Einheit Versicherungssumme ($\ddot a$ jeweils jährlich, $k=1$),
Bruttobeitragssatz nach dem Äquivalenzprinzip einschließlich Kosten:

$$
B_{x,t} = \frac{A_{x:n} + \gamma_1 \ddot a_{x:t} +
\gamma_2 (\ddot a_{x:n} - \ddot a_{x:t})}{(1-\beta_1)\, \ddot a_{x:t} -
\alpha t} \qquad\text{(Bxt)}
$$

$$
\text{BJB} = S \cdot B_{x,t}, \qquad
\text{BZB} = \frac{1 + r_{zw}}{zw}\,(\text{BJB} + \kappa), \qquad
P_{x,t} = \frac{A_{x:n} + t\,\alpha\,B_{x,t}}{\ddot a_{x:t}}
\;\;\text{(Netto, Pxt)}.
$$

# 6 Reserven und Verlaufswerte

Prospektiv je Vertragsjahr $a \in [0, 50]$, mit $y = x + a$ und
Restdauern $n-a$, $t-a$:

$$
{}_a V^{bpfl} = A_{y:n-a} - P_{x,t}\,\ddot a_{y:t-a} +
\gamma_2 \bigl( \ddot a_{y:n-a} -
\tfrac{\ddot a_{x:n}}{\ddot a_{x:t}}\, \ddot a_{y:t-a} \bigr),
\qquad {}_a DR^{bpfl} = S \cdot {}_a V^{bpfl}
$$

$$
{}_a V^{bfr} = A_{y:n-a} + \gamma_3\, \ddot a_{y:n-a}, \qquad
{}_a V^{MRV} = {}_a DR^{bpfl} +
\alpha\, t\, \text{BJB} \cdot
\frac{\ddot a_{y:\max(z-a,\,0)}}{\ddot a_{x:z}} .
$$

**Stornoabschlag** (Grenzen gelten je **Vertrag**, bei dynamischen
Erhöhungen also einmal über die Gesamtwerte aller Scheiben):

$$
\text{StoAb}_a = \begin{cases}
0 & a > n \text{ oder flexible Phase} \\
\min\bigl(u_{\max},\, \max(u_{\min},\, s\,(S^{ges} - DR^{ges}_a))\bigr)
& \text{sonst}
\end{cases}
$$

$$
\text{RKW}_a = \max\bigl(0,\, \textstyle\sum_{\text{Scheiben}}
{}_a V^{MRV} - \text{StoAb}_a \bigr), \qquad
S^{bfr}_a = \begin{cases}
\max\bigl(0,\, {}_a V^{MRV} / {}_a V^{bfr}\bigr) & a < t \\
S & t \le a \le n \\
0 & a > n .
\end{cases}
$$

Flexible Phase: $y \ge$ `min_alter_flex` **und**
$a \ge n -$ `min_rlz_flex`.

**Übernommene Generationen.** Die Regel "Grenzen je Vertrag" ist eine
Eigenschaft dieses Tarifwerks, nicht des Rechenkerns. Ein übernommener
Bestand behält das Bedingungswerk seiner Quelle; sieht das den Abzug
je Baustein vor (Grundversicherung und jede Erhöhungsscheibe einzeln,
mit eigenem Mindest- und Höchstbetrag, Rückkaufswert = Summe der auf
null begrenzten Baustein-Rückkaufswerte), steht das als
`stoab_je_baustein = true` in der Generation der Bestand-Config, und
die Führung rechnet so (Kern: `vertrags_monatsreserve`). Die Vorgabe
ist die Regel dieses Abschnitts. Welche übernommene Generation welche
Eigenschaft trägt, zeigt Abschnitt 13.

**Bewertung am Monatsstichtag.** Die Formeln oben gelten an den
Vertragsjahrestagen. Zwischen zwei Jahrestagen, nach $m = 12a + r$
vollen Vertragsmonaten ($0 \le r < 12$, $u = r/12$), werden die
Beträge linear gemischt:

$$
DR(m) = (1-u)\,{}_a DR^{bpfl} + u\,{}_{a+1} DR^{bpfl}, \qquad
V^{MRV}(m) = (1-u)\,{}_a V^{MRV} + u\,{}_{a+1} V^{MRV},
$$

nach einer Beitragsfreistellung im Jahr $a_0$ ebenso der beitragsfreie
Reservesatz: $S^{bfr}_{a_0} \bigl((1-u)\,{}_a V^{bfr} + u\,{}_{a+1} V^{bfr}\bigr)$.
Stornoabzug und Rückkaufswert werden aus den gemischten Beträgen neu
gerechnet, mit den Regeln des angebrochenen Jahres $a$ (flexible Phase,
Ablauf); am Jahrestag ($r = 0$) ist das genau die Jahreszeile. Bei
Erhöhungsscheiben mischt jede Scheibe an ihrem versetzten Stichtag, der
herabgesetzte Vertrag auf seinem geknickten Verlauf (7.1), die
Korrekturschicht auf ihrem eigenen Jahresgitter
([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md), 9.6).
Ein Vorgang, der am Jahrestag wirkt (Erhöhung, Freistellung,
Herabsetzung, Teilkündigung), gilt ab diesem Tag; im Jahr davor mischt
der Vertrag, wie er war.

So rechnen die Abnahmen (A-M1, Migrationscontrolling) und seit
2026-10-01 auch die Führung: Der Monatsabschluss weist Deckungskapital,
Rückkaufswert und Korrekturschicht in dieser Mischung aus (Kern:
`monatsreserve`, `monatsreserve_beitragsfrei`, `vertrags_monatsreserve`,
`vertrags_monatsreserve_reduziert`). Ein Beitragsübertrag für den bereits
gezahlten, noch nicht verdienten Beitrag ist darin **nicht** enthalten;
er ist fachlich noch nicht erarbeitet und als offener Punkt
zurückgestellt (`dev-docs/offene-punkte.md`, Fachlich). Verworfen wurde
die Treppe, nach der die Führung bis dahin den Wert des letzten
Jahrestags auswies: Sie lag unterjährig um bis zu 11/12 des
Jahreszuwachses unter der Reserve, und sie war nie eine fachliche
Entscheidung, sondern ein Erbe der jährlichen Fortschreibung.

# 7 Geschäftsvorfälle (GeVo-Katalog)

Buchungskonvention und die Einordnung der
Eintrittswahrscheinlichkeiten:
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 7. Jeder Betrag kommt aus dem Kern.

| GeVo | Wirkung | Betrag |
|---|---|---|
| **ZUG** Zugang | POL-Basiszeile ab Versicherungsbeginn | $S$ (Bestandsvolumen) |
| **ERH** dynamische Erhöhung | neue Scheibe: eigener Modellpunkt mit $x' = x{+}a$, $n' = n{-}a$, $t' = t{-}a$, $S' = e \cdot S^{ges}$ (Zinseszins), ohne $\gamma_1$ (Bezugsgröße GrundVS); kein Statuswechsel | $S'$ |
| **PEX** Beitragsfreistellung | Statuswechsel, nur solange Beiträge laufen ($0 < a_0 < t$, 7.3; danach ist der Vertrag ausfinanziert, nicht beitragsfrei gestellt); fixiert $\sum_{\text{Scheiben}} S^{bfr}_a$; danach beitragsfreier Track | $\sum S^{bfr}_a$ |
| **RED** Beitragsherabsetzung | Beitrag sinkt am Jahrestag $a_0$ auf den Anteil $f$ (7.1); nur während der Beitragszahlung ($0 < a_0 < t$) und ohne PEX — danach verweigert, Ausweg ist die Teilkündigung. Verfahren je Generation: prospektiv und mit Abzug wandeln den freiwerdenden Anteil in eine beitragsfreie Summe um (geknicktes Zahlungsprofil, der Vertrag wird nicht geteilt), es fließt kein Geld; ein Tarif mit `teilkuendigung` kennt keine Herabsetzung (7.2). Beliebig viele je Vertrag, jede auf dem Zustand davor (7.3). Kein Statuswechsel; Abschlusskosten folgen dem Beitrag; die Dynamik läuft weiter; eine spätere PEX fixiert die Gesamtsumme | neue Gesamtsumme (`VS_herabsetzung`); absorbierte Korrekturschicht (`dDK_absorption`) |
| **TKU** Teilkündigung | Anteil $(1-f)$ der betroffenen Bausteine gekündigt (Merkmal `tku_umfang`: alle Bausteine oder nur die Grundversicherung) und mit dem Rückkaufswert nach Tarifwerk (Stornoabzug) ausgezahlt; in jeder Generation, beitragspflichtig, ausfinanziert und nach PEX ($0 < a_0 < n$; nach PEX der Rückkaufswert des beitragsfreien Vertrags, B3); beliebig viele je Vertrag (7.2, 7.3). Kein Statuswechsel | neue Gesamtsumme (`VS_teilkuendigung`, nach PEX die beitragsfreie); absorbierte Korrekturschicht (`dDK_absorption`); Auszahlung $(1-f)\,\text{RKW}^{\text{betroffen}}_{a_0}$ + Schicht (`RKW_teilkuendigung`), auf null gekappt, ein gekappter Betrag als `Kappung_teilkuendigung` |
| **STO** Rückkauf | terminal, $a < n$; die Engine zieht ihn nur beitragspflichtig, geliefert nach PEX misst ihn die Prüfstrecke mit dem Rückkaufswert des beitragsfreien Vertrags (B3, 7.2) | $\text{RKW}_a$ (vertragsweiter StoAb) |
| **TOD** Tod | terminal | $S^{ges}$ bzw. nach PEX $\sum S^{bfr}$ |
| **ABL** Ablauf | terminal bei $a = n$ | $S^{ges}$ bzw. $\sum S^{bfr}$ |

Vier Einträge dieser Tabelle sind Tarifwerks-Eigenschaften, die eine
übernommene Generation anders tragen kann als das eigene Geschäft:
ob eine Erhöhungsscheibe $\gamma_1$ trägt (`scheiben_mit_gamma1`; die
zweite Baldrian-Lieferung rechnet jeden Baustein mit voller
Beitragsformel), ob der Stornoabzug je Baustein greift
(`stoab_je_baustein`, Abschnitt 6), nach welchem Verfahren eine
Herabsetzung rechnet (`red_verfahren`, Abschnitt 7.1; ein Tarif mit
`teilkuendigung` kennt keine Herabsetzung, Abschnitt 7.2) und welche
Bausteine eine Teilkündigung kürzt (`tku_umfang`, Abschnitt 7.2). Alle vier stehen je Generation in der
Bestand-Config, die Führung liest sie dort, und die Freischaltung
eines Migrationsfalls überträgt sie aus den bestandenen Abnahmen
(`dev-docs/freischaltung-uebernommener-bestand.md`).

Für eine übernommene Generation sind die vier Merkmale **Regeln ihres
Bedingungswerks, keine Einstellungen**: Sie stehen einmal, belegt, in der
A-Box des Migrationsfalls (Tarifwerk, je Merkmal mit Fundstelle) und daraus
in der Spez der Generation; ebenso, wie die abgebende Gesellschaft eine
gelieferte Absetzung gemeint hat, welchen Dynamiksatz sie anlegte, zu
welchem Zeitpunkt ihr Deckungskapital steht und wie die Korrekturschicht
ausgestaltet ist (Quellverfahren; Grundsatzdokumentation 10 Nr. 9). Im
Bestands-Scope verlangt die Quellenprüfung P-Q3 sie belegt; Übernahme,
Verankerung, aktuarieller Test, Migrationscontrolling und Führungsprobe
rechnen mit genau dieser Fassung, und die Config der Führung muss dasselbe
Tarifwerk tragen (ADR-024, Nachtrag). Die Werte des eigenen Geschäfts
oben gelten für eine übernommene Generation nicht als Vorgabe: Ein nicht
belegtes Merkmal ist eine offene Frage an die Quelle. Verworfen wurden
Schalter am Aufruf der Prüfkommandos — dieselbe Tatsache musste dort an
fünf Stellen gleich eingetippt werden, und ein vergessener Schalter
rechnete still die Regel des eigenen Geschäfts (im zweiten Baldrian-Lauf
fiel die Regel des übernommenen Tarifs erst in A-M3 auf).

## 7.1 Beitragsherabsetzung: Zahlungsprofil und Geltungsbereich

Der herabgesetzte Vertrag ist **ein** Vertrag mit geknicktem Verlauf,
nicht die Summe zweier Verträge. Ab dem Reduktionsjahr $a_0$ gilt,
relativ zur Ursprungssumme $S$:

| Größe | vor $a_0$ | ab $a_0$ |
|---|---|---|
| Beitrag | $1$ | $f$ |
| Leistung (Todes- und Erlebensfall, Ablauf) | $1$ | $f + q$ |
| beitragspflichtige Verwaltungskosten ($\gamma_2$) | $1$ | $f$ |
| beitragsfreie Verwaltungskosten ($\gamma_3$) | $0$ | $q$ |

$q$ ist die umgewandelte beitragsfreie Summe relativ zu $S$. Sie ist die
**einzige** Größe, in der sich die beiden Verfahren unterscheiden:

$$
q^{\text{prospektiv}} = (1-f)\,\frac{{}_{a_0}V^{MRV}}{S \cdot {}_{a_0}V^{bfr}},
\qquad
q^{\text{mit Abzug}} = (1-f)\,
\frac{\max(0,\, {}_{a_0}V^{MRV} - \text{StoAb}_{a_0})}{S \cdot {}_{a_0}V^{bfr}}
= (1-f)\,\frac{\text{RKW}_{a_0}}{S \cdot {}_{a_0}V^{bfr}} .
$$

Beide wandeln auf dem **Rückkaufs-Track** ${}_{a_0}V^{MRV}$ um — genau wie
die Beitragsfreistellung ($S^{bfr}_a = {}_aV^{MRV} / {}_aV^{bfr}$,
Abschnitt 6), nicht auf der Deckungsrückstellung
(Entscheid des Maintainers 2026-09-30). Das prospektive Verfahren wandelt
verlustfrei um; das Altverfahren behandelt den freiwerdenden Anteil wie
eine Teilkündigung und erhebt den anteiligen Stornoabschlag, bevor es
umwandelt: umgewandelt wird $(1-f)\,\text{RKW}$. Der Abschlag ist
höchstens der Rückkaufs-Track selbst, bei nicht positivem Wert entfällt
er, und der umgewandelte Teil ist nie negativ — wie beim Rückkaufswert;
keine Summe und keine Leistung wird negativ, auch bei nicht positiver
Rückstellung im ersten Vertragsjahr (die Untergrenze ist Teil der Regel,
sie greift an einer echten Eingabe: V^MRV ist innerhalb der Zillmerdauer
nicht für alle zulässigen Parameter positiv, siehe „Grenze der Untergrenze"
unten). „Mit Abzug" liegt damit nie über „prospektiv". Bei $f = 1$ ändert
sich nichts. Bei $f = 0$ ist die prospektive Herabsetzung die
Beitragsfreistellung (gleiche Summe, gleicher Pfad), auch innerhalb der
Zillmerdauer; die mit Abzug liegt um den Stornoabzug darunter (mit einem
Baustein mit negativem Rückkaufs-Track beim vertragsweiten Tarifwerk um
Abzug plus Saldo, siehe „Saldierung beim vertragsweiten Tarifwerk“ unten). Der
Anteil $(1-f)$ des noch nicht getilgten Abschlusskostenrests geht dabei mit in die beitragsfreie Summe (siehe „Abschlusskosten folgen
dem Beitrag" unten).
Welches Verfahren gilt, ist eine Eigenschaft des rechnenden **Systems**
und keine des Vertrags — es steht deshalb im Beleg einer Migration, nicht
im Modellpunkt.

**Grenze der Untergrenze (Runde F).** Die frühere Aussage „nach Messung
entsteht auf dem Rückkaufs-Track kein negativer Wert" stimmt nicht für alle
zulässigen Parameter: Die Config verlangt nur `zillmer_dauer > 0`, und
${}_aV^{MRV}$ ist innerhalb der Zillmerdauer negativ, wenn der noch nicht
getilgte Abschlusskostenrest die Rückstellung unterschreitet (gemessen für
Eintrittsalter 18 bis 60, Zins 0 bis 4 %, DAV2008_T, je Paar
($\alpha$, `zillmer_dauer`) 54 Vertragspunkte, Vertragsjahre $1 \le a < t$: `zillmer_dauer = 1` schon bei
$\alpha = 0{,}025$ — 9 von 54 —, bei $\alpha = 0{,}06$ noch mit
`zillmer_dauer` 2 und 3; mit `zillmer_dauer = 5` in dieser Suche nie). Die
Regel dazu ist **eine**: keine Summe der Basisschicht wird negativ
(*Entscheid des Maintainers 2026-09-30*). Sie gilt für die Beitragsfreistellung
und die Herabsetzung gleich — $S^{bfr}_a = \max(0, {}_aV^{MRV}/{}_aV^{bfr})$ für
$a < t$ (Abschnitt 6), der umgewandelte Teil $\max(0, \ldots)$ — damit
bleibt bei $f \to 0$ die prospektive Herabsetzung die Beitragsfreistellung
(gleiche Summe null) und die Ereignis-Engine bucht nie eine negative
`VS_bfr`. Eine Beitragsfreistellung in einem solchen Vertragsjahr
ist also zulässig und führt zur beitragsfreien Summe null; das ist die
Folge der Parameter, kein Fehler des Kerns.

Die Untergrenze null gilt an den **Ereignis-Anschlüssen** — der
beitragsfreien Summe einer Beitragsfreistellung, dem umgewandelten Teil
einer Herabsetzung und den Buchungen, die daraus folgen —; die Spalte
`VS_bfr` der Verlaufszeile bleibt die rohe Tarifformel (*Entscheid des
Maintainers 2026-10-01*). Verworfen wurde die Untergrenze auch in der
Verlaufszeile: Die Spalte ist die Sicht auf das Verlaufsblatt der
Tarifformel, gegen das die Abnahmen vergleichen, und eine geklemmte Spalte
verdeckte genau die Lage, die dieser Absatz benennt.

Die Config-Validierung warnt nicht vor Generationen, deren Parameter einen
negativen ${}_aV^{MRV}$ innerhalb der Zillmerdauer zulassen; die Lage ist
hier im Tarifplan benannt (*Entscheid des Maintainers 2026-10-01*).
Verworfen wurde eine Warnung der Validierung, weil sie keine Eintrittsalter
kennt: Ob die Lage eintritt, entscheidet erst der einzelne Vertrag, und eine
Warnung je Generation spräche über Verträge, die sie nicht betrifft.

**Saldierung beim vertragsweiten Tarifwerk (Runde F, Nachbesserung).** Der
Satz „die mit Abzug liegt um den Stornoabzug darunter“ gilt, solange kein
Baustein einen negativen Rückkaufs-Track hat, und beim Abzug je Baustein
auch dann. Beim **vertragsweiten** Tarifwerk (Abschnitt 6: Grenzen je
Vertrag) saldiert der Storno-Rückkaufswert die Bausteine,
$\text{RKW}^{ges} = \max(0,\, \sum_i {}_aV^{MRV}_i - \text{StoAb})$, während
die Beitragsfreistellung und die prospektive Herabsetzung **je Baustein** auf
null klemmen, $\sum_i \max(0,\, {}_aV^{MRV}_i)$. Ist ein Baustein negativ (eine
junge Scheibe innerhalb der Zillmerdauer), liegt die Herabsetzung mit Abzug
unter der prospektiven um **Abzug plus Saldo**,

$$
(1-f)\left(\text{StoAb} + \sum_i \max(0,\, -{}_aV^{MRV}_i)\right),
$$

solange $\text{RKW}^{ges} > 0$ ist (sonst um die ganze Summe
$(1-f)\sum_i \max(0,\, {}_aV^{MRV}_i)$). Beim Abzug je Baustein klemmt auch der
Storno-Rückkaufswert je Baustein, ein negativer Baustein trägt nichts bei, und
der Abstand ist $(1-f)\sum_i \min\bigl(\text{StoAb}_i,\, \max(0,\,
{}_aV^{MRV}_i)\bigr)$. Verteilt wird der umgewandelte Teil auf die Schichten
nach dem auf null begrenzten Baustein-Rückkaufswert: beim Abzug je Baustein
wandelt jeder Baustein seinen **eigenen** $\text{RKW}_i$ um, beim
vertragsweiten Abzug (der keinen Baustein-$\text{RKW}$ kennt) der Vertrags-RKW
nach dem auf null begrenzten Track der Schicht.

*Entscheid des Maintainers 2026-10-01:* (a) Die Herabsetzung mit Abzug folgt
beim vertragsweiten Tarifwerk dem **saldierten** Storno-Rückkaufswert (bei
$f \to 0$ liegt sie damit unter der Beitragsfreistellung, obwohl dort jeder
Baustein einzeln klemmt). Verworfen wurde der ungesaldierte Wert, weil „mit
Abzug" dann mehr umwandeln könnte, als ein Rückkauf am selben Tag auszahlt —
das Verfahren behandelt den freiwerdenden Anteil aber gerade wie einen
Teilrückkauf. (b) Der umgewandelte Teil fällt beim Abzug je Baustein nach dem
**eigenen** Baustein-Rückkaufswert auf die Bausteine, beim vertragsweiten
Abzug nach dem auf null begrenzten Rückkaufs-Track der Schicht. Verworfen
wurde ein gemeinsamer Anteil der Summe bzw. eine Verteilung nach einer
anderen Größe (etwa der Deckungsrückstellung oder der Summe), weil der Abzug
auf dem Rückkaufs-Track aufsitzt: Ein Baustein mit kleinerem Abzug wandelte
sonst mehr als seinen eigenen Rückkaufswert um, und ein Baustein mit
negativem Track bekäme einen negativen umgewandelten Teil. Die Summe ist von
(b) unabhängig, die Werte je Schicht (und damit eine spätere
Beitragsfreistellung je Baustein) sind es nicht.

**Grenze des Floors.** Der Floor auf null gilt für den umgewandelten Teil
der **Basisschicht**, nicht für die Korrekturschicht: Eine negative
Korrekturschicht ($\rho < 0$) kann den umgewandelten Teil darunter
drücken, und die Summe wird dann nicht geklemmt. Der Grund: Die
Korrekturschicht ist Migrationsdifferenz, keine Tarifgröße. Eine
Untergrenze, die sie einschlösse, machte aus der Differenz zwischen zwei
Systemen eine Tarifaussage und verdeckte genau die Abweichung, die die
Schicht ausweisen soll. Die Teilkündigung behandelt die Schicht anders,
weil dort Geld fließt: Die Auszahlung wird auf null gekappt und der
gekappte Betrag ausgewiesen (`Kappung_teilkuendigung`, Entscheid
2026-09-26). *Entscheid des Maintainers 2026-09-30.*

**Nach dem Beitragsende** gibt es keine Herabsetzung. Ein ausfinanzierter
Vertrag (Vertragsjahr $t \leq a_0 < n$, nicht beitragsfrei gestellt) hat
keinen Beitrag, den ein Anteil $f$ fortführen könnte; Kern, Datenmodell und
Bindung verweigern sie benannt und nennen den Ausweg: die Teilkündigung
(7.2), die es in jeder Generation auch nach $t$ gibt. Dasselbe gilt **nach
einer Beitragsfreistellung**: kein Beitrag, keine Herabsetzung — die
Teilkündigung kündigt dann einen Anteil der beitragsfreien Summe (7.2, B3).
Ein übernommener
Vertrag mit einer Absetzung nach $t$ in seiner Vorgeschichte wird in den
Bestand integriert — als Teilkündigung (7.2, Annahme A2, vom Maintainer
bestätigt; *Entscheid des Maintainers 2026-10-01*: „ein Problem des Ziels,
nicht der Migration“).
Verworfen wurde, die Herabsetzung nach $t$ als Teilkündigung zu rechnen und
als Herabsetzung zu buchen (ADR-023): Das Ledger muss sagen, was geschah.

Am **Klemmrand** — der Stornoabzug zehrt den Rückkaufs-Track auf, nichts
wird umgewandelt, geliefert ist $\text{ERLSUMME} = f \cdot S$ — verweigert die
Ableitung einer Herabsetzung mit Abzug benannt, statt $(S, f)$ zu erfinden;
mit dem Anteil als Auskunft ist $S$ bestimmt (*Entscheid des Maintainers
2026-10-01*). Verworfen wurde, eine der Lösungen auszuwählen: Jede Summe mit
${}_{a_0}V^{MRV} \le \text{StoAb}$ erzeugt dort dieselben Lieferfelder, eine
Auswahl wäre ein geratener Vertrag.

Die Reserve rechnet die Rekursion aus diesem Profil; sie skaliert keinen
Ursprungsvertrag hoch. Der Unterschied ist nicht die Schreibweise:
Skalierung setzt **Homogenität in der Versicherungssumme** voraus und
gilt nur für den ungeteilten Vertrag exakt. Ein Profil beschreibt, was
gezahlt wird, und braucht diese Voraussetzung nicht.

**Bei geschichteten Verträgen wirkt die Herabsetzung vor $t$ anteilig.**
Trägt der Vertrag dynamische Erhöhungsscheiben, so trägt jede Schicht denselben
Faktor $f$ und wandelt ihren freiwerdenden Anteil mit **ihrem eigenen**
beitragsfreien Reservesatz um; jede Schicht rechnet dabei in ihrem
eigenen Vertragsjahr $a_i = a_0 - e_i$, wobei $e_i$ ihr Erhöhungsjahr ist.

Anteilig ist keine Wahl unter mehreren, sondern die Folge der
Beitragsdefinition: Weil der Jahresbeitrag jeder Schicht proportional zu
ihrer Summe ist, ergibt derselbe Faktor je Schicht in der Summe genau den
Zielbeitrag,

$$
\sum_i f \cdot \text{BJB}_i = f \sum_i \text{BJB}_i .
$$

**Der Stornoabschlag bleibt vertragsweit** (Abschnitt 6): einmal auf den
Gesamtwerten gebildet und dann proportional zum Rückkaufs-Track der
Schicht getragen —

$$
q_i^{\text{mit Abzug}} = (1-f)\,
\frac{\text{RKW}^{ges}_{a_0}}{\sum_j \max(0,\, {}_{a_j}V^{MRV})}
\cdot\frac{\max(0,\, {}_{a_i}V^{MRV})}{S_i \cdot {}_{a_i}V^{bfr}} ,
\qquad
\sum_i S_i\,q_i^{\text{mit Abzug}}\,{}_{a_i}V^{bfr} = (1-f)\,\text{RKW}^{ges}_{a_0} .
$$

$\text{RKW}^{ges}_{a_0}$ ist der Rückkaufswert, den ein Storno am selben
Tag zahlt — nach dem Tarifwerk der Generation (Abschnitt 6: Grenzen je
Vertrag, oder je Baustein mit der Summe der auf null begrenzten
Baustein-Werte). Der Nenner ist die Summe der auf null begrenzten
Rückkaufs-Tracks, denn nur diese Summe geht in die Umwandlung ein (je
Schicht $\max(0, \ldots)$); durch die unbegrenzte Summe geteilt, wäre der
Faktor größer als eins, sobald eine junge Scheibe in der Zillmerdauer
negativ ist, und „mit Abzug" läge über „prospektiv" (Runde F, F1: Ist
334,40 statt 114,88 bei $V^{MRV}$ Grund 429,77, Scheibe −282,12). Mit
Abzug wird also nie mehr umgewandelt als $(1-f)\,\text{RKW}$, und nie mehr
als prospektiv.

Je Schicht gebildet griffen $u_{\min}$ und $u_{\max}$ mehrfach, und ein
Vertrag mit zwei Erhöhungen verlöre beim Herabsetzen mehr als den
zugesagten Abschlag.

**Abschlusskosten folgen dem Beitrag.** Der noch nicht getilgte
Abschlusskostenrest im Rückkaufs-Track (${}_a V^{MRV} - {}_a DR^{bpfl}$,
Abschnitt 6) wird bei einer Herabsetzung proportional abgeschrieben: Ab
$a_0$ trägt der fortgeführte Vertrag den Anteil $f$ des Rests, der Anteil
$(1-f)$ ist ein Verlust des Unternehmens aus der Herabsetzung — beim
Verfahren mit Abzug teilweise durch den anteiligen Stornoabschlag
gedeckt, beim prospektiven Verfahren nicht. Reserve, Rückkaufswert und
beitragsfreie Summe des herabgesetzten Vertrags rechnen mit derselben
Regel; eine Beitragsfreistellung nach der Herabsetzung ist deshalb
wertstetig.

Der Anteil gilt an **jedem** Jahrestag von $a_0$ bis zum Ablauf, auch am
Jahrestag $n$ selbst. Dort ist der Rest gewöhnlich null; nicht null ist er
bei einem Baustein, der kürzer läuft als die Zillmerdauer (eine späte
Erhöhungsscheibe, $n' = n - e < z$), und die Monatsmischung des letzten
Vertragsjahres liest ihn (*Prüfrunde G, Fund G01; Kern 3.18.0*). Bis dahin
trug der Zahlungspfad am Jahrestag $n$ den Rest ungekürzt, und der
Rückkaufswert des letzten Vertragsjahres lag um $(1-c)$ mal Rest mal
Monatsanteil zu hoch (gemessen bis rund 20 EUR je Vertrag); das
Deckungskapital war gleich. Verworfen: den Rest am Ablauf auf null zu
setzen — das wäre eine zweite Tilgungsregel neben der des Kerns, und der
unveränderte Baustein trägt ihn dort.

**Dynamik nach der Herabsetzung.** Die dynamische Erhöhung läuft nach
einer Herabsetzung weiter und bezieht sich auf die geführte Summe danach
(den fortgeführten Vertrag samt seiner Erhöhungen). Jede spätere
Erhöhung ist ein eigener, nicht herabgesetzter Baustein mit vollem
Beitrag auf ihre Summe.

**Übernommene Generationen mit Abzug je Baustein.** Führt das
Bedingungswerk einer übernommenen Generation den Stornoabschlag je
Baustein (`stoab_je_baustein`, Abschnitt 13; Bedingungswerk der zweiten
Baldrian-Lieferung, Ziffer 4), so gilt das auch **nach** einer
Herabsetzung: jeder Baustein trägt seinen Abzug mit eigenen Grenzen,
bezogen auf seine herabgesetzte Summe. Die Teilkündigung dieses Tarifs
(Ziffer 6, `tku_umfang = grundversicherung`, 7.2)
lässt die Erhöhungsscheiben unverändert; der fortgeführte Vertrag ist
die Grundversicherung mit $f \cdot S$ plus diese Scheiben, unter dem
vollständigen Tarifwerk der Generation, und sein Beitrag rechnet
komponentenweise: $f \cdot \text{BJB}_{\text{Grund}} + \sum_i
\text{BJB}_i$, die Stückkosten bleiben je Baustein fix und werden nicht
mit der Summe skaliert. Das gilt gleichermaßen für die PLV-Verfahren:
jeder Baustein zahlt den Beitrag seiner fortgeführten Summe $f \cdot
S_i$ zuzüglich seiner Stückkosten. *Präzisierung 2026-09-24 (Prüfrunde
T27, Befunde 12 und 13).*

Bei der Herabsetzung mit Abzug einer solchen Generation ist der
umgewandelte Teil $(1-f)\,\text{RKW}$ mit dem Rückkaufswert nach dem
Tarifwerk der Generation — der Summe der auf null begrenzten
Baustein-Rückkaufswerte mit je eigenem Abzug, derselben Größe, die ein
Storno am selben Tag zahlt — nicht mit einem vertragsweit gebildeten Abzug.
*Präzisierung 2026-09-30 (Prüfrunde T27, Runde D).* Auf die Schichten fällt er
je Baustein: Jeder Baustein wandelt seinen eigenen
$\text{RKW}_i = \max(0,\, {}_{a_i}V^{MRV} - \text{StoAb}_i)$ um, $(1-f)\,\text{RKW}_i$,
nicht einen gemeinsamen Anteil der Summe (Runde F, Nachbesserung 2; die Summe
ist dieselbe, die Werte je Schicht sind es nicht).

## 7.2 Teilkündigung

*Entscheid des Maintainers 2026-10-01 (ADR-023):* „Wir sollten in PLV beides
haben. Herabsetzung betrifft NUR Beiträge und macht nur Sinn, so lange ein
Beitrag bezahlt wird. Eine Teilkündigung kann immer (beitragspflichtig oder
ausfinanziert) gemacht werden, hat aber eine andere Wirkung — Teil des
Deckungskapitals wird ausgezahlt. Das sind im Grunde zwei verschiedene
Vorgänge und betreffen alle PLV-Tarife gleich.“

Die Teilkündigung (`TKU`) kündigt den Anteil $(1-f)$ der Summe der
**betroffenen Bausteine** und zahlt ihren Rückkaufswert nach dem Tarifwerk
der Generation aus, mit deren Stornoabzug (je Vertrag oder je Baustein,
Abschnitt 6). Jeder Bestandteil eines betroffenen Bausteins — fortgeführter
Teil, fixierte beitragsfreie Teilsummen, Zillmer-Rückstand — trägt danach
den Faktor $f$; der Baustein ist der gewöhnliche Baustein mit kleinerer
Summe (Homogenität, 7.3):

$$
S^{\text{danach}}_i = f \cdot S_i \;(i \text{ betroffen}), \qquad
\text{Auszahlung} = \max\left(0,\; (1-f)\,\text{RKW}^{\text{betroffen}}_{a_0} + \text{Schicht}_{a_0}\right),
$$

eine gekappte negative Summe wird als `Kappung_teilkuendigung` ausgewiesen.
Sie setzt keinen laufenden Beitrag voraus und ist in **jeder** Generation
beitragspflichtig, ausfinanziert und nach einer Beitragsfreistellung
möglich, für $0 < a_0 < n$ — vor $t$ zahlt der Vertrag danach den Beitrag
seiner fortgeführten Summe. Gebucht wird sie unter dem eigenen Code `TKU`
(`VS_teilkuendigung`, `dDK_absorption`, `RKW_teilkuendigung`,
`Kappung_teilkuendigung`), nie als `RED`; das Bewegungskonto führt sie als
eigene Position „Teilkündigung“, auf dem beitragsfreien Track ebenso. Die
Ereignis-Engine zieht sie mit einer eigenen Rate `annahmen.teilkuendigung`
(Vorgabe 0) und einem eigenen Anteil `annahmen.tk_anteil` aus einem eigenen
Zufallsstrom; ohne Rate rechnet jede Generation bitgleich wie vor dem
Entscheid.

**Welche Bausteine betroffen sind** (B1), ist ein Merkmal des Tarifwerks,
`tku_umfang`, ein Wert je Generation der Bestand-Config:

* `alle_bausteine` — die eigenen Tarife der PLV: Grundversicherung und jede
  bestehende Erhöhungsscheibe mit demselben Anteil $f$ (*Entscheid des
  Maintainers 2026-10-01*);
* `grundversicherung` — der übernommene Tarif TG2015: nur die
  Grundversicherung, die Erhöhungsscheiben laufen unverändert (Bedingungswerk
  Ziffer 6). *Entscheid des Maintainers 2026-10-01 (B1)*, verworfen: auch
  der übernommene Tarif kürzt anteilig über alle Bausteine — die Regel gehört
  zu den Vertragsbedingungen des übernommenen Tarifs, und die gelieferten
  Werte der Vorgeschichte sind nur mit ihr nachrechenbar (A-M3-Befund des
  zweiten Laufs: dDK $= -(1-f)\cdot V^{MRV}$ des Grundbausteins).

Ohne Angabe gilt der Umfang des Bedingungswerks, das `red_verfahren` nennt
(`teilkuendigung` → `grundversicherung`, sonst `alle_bausteine`); die
Generation TG2015 der Config schreibt ihn ausdrücklich hin.

**Nach der Beitragsfreistellung** (B3) kündigt die Teilkündigung den Anteil
$(1-f)$ der beitragsfreien Summe jedes betroffenen Bausteins, und die
beitragsfreie Gesamtsumme sinkt genau proportional. Ausgezahlt wird
$(1-f)$ mal der **Rückkaufswert des beitragsfreien Vertrags**: seine
Deckungsrückstellung abzüglich des Stornoabzugs nach derselben Tarifregel
wie beim beitragspflichtigen Vertrag, angewandt auf die beitragsfreie Summe
und ihre Rückstellung — Satz mal (Summe minus Rückstellung), begrenzt auf
Mindest- und Höchstbetrag, je Vertrag oder je Baustein nach dem Tarifwerk,
null in der flexiblen Phase, nie negativ. Derselbe Rückkaufswert gilt für
den Rückkauf eines beitragsfreien Vertrags; die Führungsprobe und P-B1 lesen
ihn an derselben Stelle. Die Regel sitzt am **Ereignis-Anschluss**: Die
Spalten `RKW` und `VS_bfr` der Verlaufszeile bleiben die rohe Tarifformel
und unverändert (Charakterisierung). *Entscheid des Maintainers 2026-10-01
(B3)*, verworfen: die Rückstellung ohne Abzug auszuzahlen (ein beitragsfreier
Vertrag stünde beim Teilrückkauf besser als der beitragspflichtige), und
wie bisher keinen Rückkaufswert für beitragsfreie Verträge zu kennen (die
Teilkündigung nach PEX wäre unbezahlbar). Die Ereignis-Engine zieht einen
Rückkauf nach der Beitragsfreistellung weiterhin nicht (Erfahrungsannahme);
wo er geliefert wird, misst ihn die Prüfstrecke mit dieser Regel.

Verworfen wurden außerdem:

* **ein** Vorgang mit Verfahrensschalter und stiller Umdeutung (die
  zunächst gebaute „Regel A“: nach $t$ rechnet jede Herabsetzung als
  Teilkündigung und wird als `RED` gebucht) — es sind zwei Vorgänge mit
  verschiedener Wirkung, und das Ledger muss sagen, was geschah;
* die Umwandlung des Anteils $(1-f)$ in beitragsfreie Summe auch nach $t$ —
  sie ergäbe $q = (1-f)$ und damit die volle Summe: keine Absetzung;
* die Auszahlung ohne Stornoabzug in einer Generation mit `prospektiv` —
  gekündigt wird ein Summenanteil, und der Tarif sieht für den Rückkauf den
  Abzug vor.

**Der übernommene Tarif TG2015 im Vokabular des Zielsystems.** Ab der
Migration gilt das Vokabular des Zielsystems (Grundsatzdokumentation 7.1).
Für TG2015 heißt das konkret:

* Der Tarif kennt **einen** Vorgang: Was die Quelle „Herabsetzung“ nennt
  (Code `RED` der Lieferung, Verfahren `teilkuendigung`), ist die
  Teilkündigung der PLV. Die Führung zieht ihn allein aus dem Strom der
  Teilkündigung; der Herabsetzungsstrom wird für diesen Tarif nicht gezogen,
  und das Datenmodell lehnt eine `RED`-Zeile für ihn ab („ein Tarif, der
  keine Beitragsherabsetzung kennt“). *Entscheid des Maintainers
  2026-10-01* — er ersetzt die frühere Annahme A1 (Herabsetzungswunsch als
  Teilkündigung ausgeführt); eine doppelte Rate gibt es nicht mehr.
* Der Code `RED` bleibt als Provenienzname in Lieferung und Belegen stehen.
  Die Übersetzung in den Zielvorgang ist die Regel des Grundsatzes, für
  diesen Tarif: **immer** Teilkündigung — vor und nach $t$, vor und nach
  einer Beitragsfreistellung.
* Kennt eine Quelle dagegen eine echte Beitragsherabsetzung (Verfahren
  `prospektiv` oder `mit_abzug`), war eine gelieferte Absetzung vor dem
  Beitragsende und vor einer Beitragsfreistellung eine Herabsetzung, danach
  eine Teilkündigung (*Annahme B5*, nicht vom Maintainer entschieden; die
  Fortsetzung von A2, die der Maintainer bestätigt hat: nach $t$ immer eine
  Teilkündigung).

**Annahmen** (im Auftrag gesetzt, nicht vom Maintainer entschieden; je
einzeln prüfbar):

* *B2 — proportional auf dem Zustand.* Jeder Vorgang wirkt mit seinem
  Anteil auf den Zustand, den der Vertrag gerade hat (7.3). Die Verteilung
  einer Herabsetzung auf die Bausteine folgt 7.1 (jeder Baustein mit
  demselben Faktor auf seinem fortgeführten Rückkaufs-Track).
* *B4 — Homogenität, je Größe geprüft.* Homogen in der Summe sind der
  Bruttobeitrag (Satz mal Summe), der Satzteil des Stornoabzugs und der
  Zillmer-Rückstand; die Teilkündigung skaliert sie. Nicht homogen sind die
  Stückkosten (im Zahlbeitrag, je Baustein fix), Mindest- und Höchstbetrag
  des Stornoabzugs (Pauschalbeträge des Tarifs) und die Korrekturschicht
  (ein Betrag, den der erste Vorgang vollständig aufnimmt); sie werden nie
  skaliert, sondern auf dem Zustand gebildet. Einen weiteren Pauschalabzug
  kennt das Tarifwerk nicht. Jede Größe hat ihre eigene Kontrolle
  (`tests/test_vorgangsfolge.py`, Abschnitt B4).
* *B5 — Quelle mit echter Herabsetzung*, siehe oben.

A2 (eine gelieferte Absetzung nach $t$ war eine Teilkündigung) hat der
Maintainer bestätigt; A1, A3 (nur die Grundversicherung — jetzt das Merkmal
`tku_umfang`, B1) und A4 (ein Vorgang je Vertrag) sind durch die Entscheide
vom 2026-10-01 ersetzt.

**Ableitung im Migrationszugang.** Geliefert ist die heutige Summe
(`ERLSUMME`). Nach einer Teilkündigung gilt $\text{ERLSUMME} = f \cdot S$:
eine Gleichung mit zwei Unbekannten, und nach $t$ keine Beitragsgleichung
(`JBRUTTO` = 0). Für den Wert des Vertrags genügt das: Er ist der
zustandslose Vertrag mit der gelieferten Summe und wird ohne Anfangszustand
übernommen. Wo der Anteil wirkt — in einer Folge aus Erhöhungen und einer
späteren Absetzung verteilt er die gelieferte Summe auf Grund und
Erhöhungen —, kommt er als registrierte Auskunft der abgebenden
Gesellschaft (`--red-anteile-datei`, `POLNR;GEVO;DATUM;ANTEIL`); mit ihm ist
$S = \text{ERLSUMME} / f$ bestimmt. Eine Vorgeschichte mit **mehreren**
Absetzungen, verschränkt mit Erhöhungen und einer Beitragsfreistellung,
leitet der Zugang so ab:

* mit Beitragsfreistellung: über die beitragsfreie Gesamtsumme
  (Ein-Punkt-Inversion) — auch mit Teilkündigungen danach und
  Herabsetzungen davor, denn jede erreichbare Größe ist homogen in der
  beitragsfreien Gesamtsumme;
* Teilkündigungen nur der Grundversicherung: geschlossen aus dem belegten
  Dynamiksatz (jede Folge ist linear in der Ursprungssumme);
* sonst — eine echte Herabsetzung (B5) oder Teilkündigungen über alle
  Bausteine — über die Vorgangsfolge (7.3): die Ursprungssumme, mit der die
  Folge die gelieferte Summe trifft, mit Vorwärtsprobe. Nur
  Teilkündigungen hinterlassen den zustandslosen Vertrag in IST-Summen; ein
  durch eine Herabsetzung **geteilter** Vertrag trägt seine Vorgänge, und
  die Übernahme schaltet ihn benannt nicht frei (die Führung trägt
  Vorgänge der Vorgeschichte vor dem Zugang noch nicht).

Ohne Auskunft **verweigert** die Übernahme und nennt den Ausweg; ein
Vertrag, dessen Anfangszustand nicht ableitbar ist, wird nicht mehr still
als Grundvertrag mit der gelieferten Summe weitergeführt (Prüfer-Befund B1).
Gedeckt ist ein solcher Vertrag nur durch das, was seine **Struktur**
bestimmt — die registrierte Auskunft je Ereignis. „Die Werte an den
Bewertungspunkten stimmen“ ist keine Deckung: Nach dem Beitragsende sind
die Wertvergleiche gegen die Zerlegung blind, jede Zerlegung mit derselben
Summe erzeugt dieselben Werte bis auf die Centrundung, und eine spätere
Teilkündigung zahlte trotzdem falsch aus. Ein gedeckter Vertrag ist deshalb
Pflichtziehung von A-M1, A-M2, A-M3 und der Migrationssuite; der
Übernahmebeleg nennt, wodurch er gedeckt ist (ADR-002, Nachtrag
2026-10-01).

**Grenze.** Eine registrierte Auskunft, die *falsch* ist, bestimmt eine
falsche Zerlegung mit richtiger Summe; nach $t$ sieht das keine
Wertprüfung. Eine Strukturprüfung bräuchte einen Wert, der von der
Zerlegung abhängt (etwa den Rückkaufswert je Baustein der Quelle) — die
Lieferung trägt keinen. Die Verantwortung liegt bei dem, der die Auskunft
registriert.

## 7.3 Folgen von Vorgängen

*Entscheid des Maintainers 2026-10-01:* Ein Vertrag trägt beliebig viele
Herabsetzungen und Teilkündigungen, in jeder Reihenfolge, verschränkt mit
Erhöhungen und der Beitragsfreistellung (Grundsatzdokumentation 7.2). Der
Zustand des Vertrags ist die Folge seiner Vorgänge; jeder Leser rechnet sie
über `kern/vorgangsfolge.py`.

**Darstellung.** Jeder Baustein (Grundversicherung, jede Erhöhungsscheibe)
trägt seinen wirksamen Modellpunkt (die Summe nach allen Teilkündigungen),
seinen Verlauf relativ zu diesem Modellpunkt — Abschnitte $(a, c, q)$ mit
fortgeführtem Beitragsfaktor $c$ und fixierter beitragsfreier Teilsumme $q$,
gerechnet als Zahlungspfad wie in 7.1 — und nach einer
Beitragsfreistellung seine beitragsfreie Summe.

**Regeln der Verkettung** (B2):

| Vorgang | Wirkung auf den Zustand |
|---|---|
| Herabsetzung mit Anteil $f$ (7.1) | $c \to c\,f$ je Baustein; der freiwerdende Anteil $(1-f)$ des **fortgeführten** Rückkaufs-Tracks $c\,V^{MRV}$ wird nach dem Verfahren umgewandelt und als weitere Teilsumme $q$ fixiert; schon fixierte Teile bleiben. |
| Teilkündigung mit Anteil $f$ (7.2) | jeder betroffene Baustein mit allen Bestandteilen mal $f$ (Summe, $q$, beitragsfreie Summe); Auszahlung $(1-f)$ mal Rückkaufswert des betroffenen Teils unmittelbar davor. |
| Erhöhung | ein neuer, gewöhnlicher Baustein auf $e \cdot S^{ges}$ der geführten Summe davor. |
| Beitragsfreistellung | jeder Baustein fixiert seine beitragsfreie Summe auf seinem aktuellen Verlauf. |

Am selben Jahrestag gilt die Reihenfolge Beitragsfreistellung,
Herabsetzung, Teilkündigung, Erhöhung; zwei gleiche Vorgänge an einem
Jahrestag werden benannt verweigert (Ausweg: die Anteile zu einem Vorgang
mit $f = f_1 f_2$ zusammenfassen). Ein Vertrag mit **einem** Vorgang rechnet
bitgleich wie zuvor; ein Vertrag ohne Vorgang wird nicht über die Folge
gerechnet.

**Die Menge der zulässigen Folgen.** Zulässig ist jede endliche Folge aus
Herabsetzungen (RED), Teilkündigungen (TKU), Erhöhungen (ERH) und höchstens
einer Beitragsfreistellung (PEX), geordnet nach Jahrestag und Rang des
Tages, mit jedem Vorgang im Vertragsjahr $0 < a < n$, in der

* keine Herabsetzung ab dem Beitragsende ($a \ge t$) oder ab der
  Beitragsfreistellung steht (Ausweg: Teilkündigung),
* keine Beitragsfreistellung ab dem Beitragsende ($a \ge t$) steht (der
  Vertrag ist dann ausfinanziert; eine Teilkündigung bleibt bis zum Ablauf
  möglich),
* keine Erhöhung nach der Beitragsfreistellung steht,
* keine Herabsetzung in einem Tarif steht, der sie nicht kennt (TG2015),
* an keinem Jahrestag zwei Vorgänge derselben Art stehen.

Jede Folge außerhalb dieser Menge wird benannt verweigert, mit dem Ausweg.
Die Jahresgrenzen gelten für **jeden** Vorgang, auch für die
Beitragsfreistellung: kein Vorgang im Vertragsjahr 0 (am Versicherungsbeginn
gibt es keinen Vertragsstand, den er ändern könnte — was dort gewollt ist,
ist ein anderer Vertrag; Ausweg: der Zugang mit den Werten nach dem Vorgang
oder der Vorgang am ersten Jahrestag), keine Beitragsfreistellung ab dem
Beitragsende. Sie stehen im Kern an einer Stelle
(`beitragsreduktion.pruefe_vorgangsjahr`), durch die Einzelreduktion und
jeder Vorgang der Folge gehen. *Prüfrunde G, Fund G02; Kern 3.18.0:* Bis
dahin rechnete der Kern Herabsetzung und Teilkündigung im Jahr 0 und eine
Beitragsfreistellung im Jahr 0 oder ab dem Beitragsende still; gemessen lieferte
kein Produzent solche Folgen (Engine, Übernahme, Prüfstrecke, die
Baldrian-Ketten). Verworfen: die Grenzen je Leser zu prüfen — die Leser
delegieren sie an den Kern, und eine Wache an einem von zwei Eingängen ist
keine.

*Entscheid 2026-10-01:* Eine Beitragsfreistellung gibt es nur, solange
Beiträge laufen ($0 < a < t$; GeVo-Katalog der T-Box) — dieselbe Regel wie
für die Herabsetzung, die nur Beiträge betrifft und nur Sinn ergibt, solange
ein Beitrag bezahlt wird. Nach dem Beitragsende ist der Vertrag
ausfinanziert, nicht beitragsfrei gestellt. Verworfen: die Freistellung bis
zum Ablauf zuzulassen. Sie ändert die Summe dort nicht (die beitragsfreie
Summe ist die geführte), schaltet aber den Status und damit die
Rückkaufswertregel des beitragsfreien Vertrags um, ohne dass ein Beitrag
wegfällt.
Die folgende Tabelle ist eine **Auswahl** daraus — die Folgen mit eigener
Kontrollrechnung; die Menge selbst prüfen Eigenschaftstests über erzeugte
Folgen (`tests/test_vorgangsfolge_eigenschaften.py`: nichts unter null, jede
ausgeschlossene Folge benannt verweigert, der Zustand nach jedem Vorgang ist
der, den die Bewertung liest, Teilkündigungen vertauschbar und gleich dem
Produkt der Anteile, Teilkündigung nach PEX proportional, Anteil 1 ändert
nichts) und der Zähltest durch alle Leser (`tests/test_vorgangsfolge_leser.py`,
jede zulässige geordnete Zweierfolge aus RED, TKU, PEX und ERH, Dreierfolgen,
Folgen mit Scheiben).

| Folge | Ergebnis | Kontrolle |
|---|---|---|
| RED, RED | gerechnet: die zweite wandelt $(1-f_2)$ des fortgeführten Tracks um | Verlaufszeilen: $c\,V(a) + (q_1+q_2)\,V^{bfr}(a)$ |
| TKU, TKU | gerechnet: der Vertrag mit $f_1 f_2 S$, vertauschbar | gewöhnlicher Kern mit kleinerer Summe |
| RED, TKU | gerechnet: die Herabsetzung des gekürzten Vertrags | `ReduzierterVertrag` auf $f S$ |
| TKU, RED | gerechnet: die Herabsetzung des gekürzten Vertrags (nicht vertauschbar mit RED, TKU in anderen Jahren) | Eigenschaftstest |
| ERH, TKU, alle Bausteine | gerechnet: Grund und Scheibe mit $f$ | Kern je Baustein mit $f S_i$ |
| ERH, TKU, nur Grundversicherung | gerechnet: nur der Grund mit $f$ | Kern mit $f S$ plus unveränderte Scheibe |
| RED, ERH | gerechnet: die Scheibe auf $e \cdot S^{ges}$ nach der Herabsetzung, ungekürzt | Ledger-Regel `erh_prozent` |
| RED, PEX / TKU, PEX | gerechnet: Freistellung auf dem geknickten bzw. gekürzten Verlauf | Einzelreduktion des Kerns (Weg vor der Folge) |
| PEX, TKU | gerechnet: beitragsfreie Summe mal $f$, Auszahlung $(1-f)$ RKW beitragsfrei (B3) | Tarifregel des Stornoabzugs |
| PEX, RED | verweigert: kein Beitrag, den sie senken könnte | Ausweg TKU |
| RED ab $t$ | verweigert | Ausweg TKU |
| PEX, ERH | verweigert: keine Dynamik nach der Freistellung | — |
| RED, RED am selben Jahrestag | verweigert | Ausweg $f = f_1 f_2$ |
| RED im Tarif TG2015 | verweigert: der Tarif kennt keine Herabsetzung | Ausweg TKU |
| ein Vorgang (RED, TKU, PEX, ERH) im Vertragsjahr 0 | verweigert | Ausweg: Zugang mit den Werten nach dem Vorgang, oder Vertragsjahr 1 |
| PEX ab dem Beitragsende ($a \ge t$) | verweigert: der Vertrag ist ausfinanziert | Teilkündigung bleibt bis zum Ablauf möglich |

# 8 Modellpunkt und Tarif-Stellschrauben

Alle Größen sind Felder des Modellpunkts (`ModelPoint`) — eine neue
Tarifgeneration ist eine Parametrierung, keine Formeländerung:

| Größe | Feld | Bedeutung |
|---|---|---|
| $x$, `sex`, $n$, $t$, $S$, $zw$ | Vertragsfelder | Eintrittsalter, Geschlecht, Dauern, Summe, Zahlweise |
| $q_x$ | `tafel` | Sterbetafel (z. B. DAV 1994 T, DAV 2008 T) |
| $i$ | `zins` | Rechnungszins |
| $\alpha$ | `alpha` | Abschlusskostensatz (Zillmer, je Einheit $S$ und Beitragsjahr) |
| $\beta_1$ | `beta1` | Inkassokostensatz auf den Beitrag |
| $\gamma_1, \gamma_2, \gamma_3$ | `gamma1..3` | Verwaltungskosten (beitragspflichtig, beitragsfrei) |
| $\kappa$ | `policy_fee` | Stückkosten p. a. |
| $z$ | `zillmer_dauer` | Amortisationsdauer der Abschlusskosten (Standard 5) |
| $s, u_{\min}, u_{\max}$ | `stoab_satz/min/max` | Stornoabschlag (Satz, Unter-/Obergrenze **je Vertrag**) |
| $r_{zw}$ | `ratzu_zw2/4/12` | Ratenzuschlag-Staffel |
| — | `min_alter_flex`, `min_rlz_flex` | flexible Ablaufphase |

# 9 Gültigkeitsgrenzen

* Der Verlauf ist modellpunktgetrieben ($a \in [0, n]$; seit Kern
  3.0.0 kein 51-Zeilen-Blattdeckel mehr). Das Fenster $[0, 50]$ bleibt
  als expliziter Vergleichs-Contract der `berechne()`-View erhalten
  (Zeilenformat des Quell-Verlaufsblatts, `contract_verlauf_bis`).
  Die Bestand-Engine hält ein eigenes konservatives Fenster und weist
  Laufzeiten $n > 50$ ab.
* Tafelbereich: Alter ab der Tafel-Erschöpfung (erstes Alter nach
  $q_x \ge 1$, z. B. DAV 1994 T ab Alter 101) sind fail-fast; kein
  Alter über 123.
* Kein Storno beitragsfreier Verträge (keine RKW-Regel definiert).

# 10 Abgrenzung: Bewertung und Fortschreibung

Dieser Tarifplan beschreibt die **Bewertung** auf den
Rechnungsgrundlagen erster Ordnung. Wie ein Bestand dieses Produkts im
Vorzeigebetrieb fortgeschrieben wird, ist keine Eigenschaft des Tarifs,
sondern des Simulationswerkzeugs
(`docs/simulation/erfahrungsannahmen.md`); die dort verwendeten
Annahmen wirken nie in Beitrag oder Reserve zurueck
([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 5.2).

# 11 Referenzwerte und Abnahme

Das Abnahme-Protokoll gilt für alle Produkte
([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 11). Für dieses Produkt sind
gesichert: die eingefrorenen Referenzwerte des produktiven Pfads, die
Toleranz-Überleitung gegen den Kommutations-Zweitkern
(`qa/ueberleitung`) und je Migrationsfall Gate P-K1 gegen den
Quell-Rechner. Die einmalige 617/617-Excel-Parität (22.07.2026, 4
Nachkommastellen) ist der historische Übersetzungsbeleg, kein
laufender Referenzwert.

# 12 Vorgesehene Erweiterungen

Wiederinkraftsetzung, monatsgenaues Ereignisgitter,
Überschussbeteiligung — jeweils als GeVo-Formeln in Abschnitt 7 zu
ergänzen, bevor sie implementiert werden.

Die **Beitragsherabsetzung** stand hier, zuletzt nur noch mit ihrer
Verteilungsregel für geschichtete Verträge; seit 2026-08-31 ist sie
vollständig in 7.1 zugesagt (anteilig über alle Schichten,
Stornoabschlag vertragsweit). Verworfen wurden dabei „jüngste Schicht
zuerst" — wegabhängig und ohne Regel für die teilweise zurückgenommene
Schicht — und „nur die Grundscheibe", das den Beitrag der
Erhöhungsscheiben unsenkbar ließe.

# 13 PLV-Bestandsgenerationen

Die **Pfefferminzia Lebensversicherung (PLV)** ist das fiktive
Unternehmen dieses Arbeitsraums: Zielkern und Bestand gehören ihr,
Migrationsfälle übernehmen fremde Bestände in die PLV. Ihre zehn
KLV-Bestandsgenerationen sind konstruiert (kein Migrationsfall, keine
Quell-Provenienz) und tragen — wie jede Generation, die das System
rechnet — eine **Ontologie-Knoten-ID** (Pflichtfeld `knoten` der
Bestand-Config, dieselbe Konvention wie A-Box und Gate P-K1; Wurzel =
Produktfamilie, Präfix `plv_` = PLV-eigene Generation ohne
Migrationsfall). Die Generation im Vertrieb ist KLV-2025; ihre
Rechnungsgrundlagen sind **vorläufig** (Höchstrechnungszins 2025 und die
Kosten der Vorgängergeneration), bis das Aktuariat der Vorzeige sie
festlegt (Fachkonzept Tagesbetrieb, offene Fachentscheidung):

<!-- erzeugt: python -m rechner_pipeline.bestand.tarifplan_tabellen --config configs/bestand_gesamt.toml --produkt klv -->
| Knoten | Name | gültig | Zins | Tafel | $\alpha$ | $\beta_1$ | $\gamma_{1/2/3}$ | $\kappa$ | Vertrieb |
|---|---|---|---|---|---|---|---|---|---|
| `klv/plv_1994` | KLV-1994 | 1994-07–2000-06 | 4.00% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 | Neugeschäft 100/Jahr |
| `klv/plv_2000` | KLV-2000 | 2000-07–2003-12 | 3.25% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 | Neugeschäft 80/Jahr |
| `klv/plv_2004` | KLV-2004 | 2004-01–2006-12 | 2.75% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 | Neugeschäft 87/Jahr |
| `klv/plv_2007` | KLV-2007 | 2007-01–2007-12 | 2.25% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 | Neugeschäft 70/Jahr |
| `klv/plv_2008` | KLV-2008 | 2008-01–2011-12 | 2.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 75/Jahr |
| `klv/plv_2012` | KLV-2012 | 2012-01–2014-12 | 1.75% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 80/Jahr |
| `klv/plv_2015` | KLV-2015 | 2015-01–2016-12 | 1.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 90/Jahr |
| `klv/plv_2017` | KLV-2017 | 2017-01–2021-12 | 0.90% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 50/Jahr |
| `klv/plv_2022` | KLV-2022 | 2022-01–2024-12 | 0.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 50/Jahr |
| `klv/plv_2025` | KLV-2025 | 2025-01–2035-12 | 1.00% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 | Neugeschäft 120/Jahr, Trend -4%/Jahr |

Tarifzellen der übernommenen Generation **TG2015** (`klv/tg2015`, Rechnungszins 1.25%, Zellen über `status` × `tarifart`; je Zelle nur die vom Rumpf abweichenden Felder):

| Zelle | Tafel | $\alpha$ | $\beta_1$ | $\gamma_{1/2}$ | $\kappa$ | StoAb Satz/min/max | Ratenzuschlag zw2/4/12 |
|---|---|---|---|---|---|---|---|
| nichtraucher/einzel | DAV2008_T_NR_U70 | 0.025 | 0.03 | 0.001/0.00125 | 12 | 0.005/50.0/200.0 | 0.02/0.03/0.05 |
| nichtraucher/haus | DAV2008_T_NR_U70 | 0.0 | 0.01 | 0.0008/0.001 | 0 | 0.0/0/0 | 0.0/0.0/0.0 |
| nichtraucher/kollektiv | DAV2008_T_NR_U70 | 0.015 | 0.015 | 0.0008/0.001 | 12 | 0.005/50.0/200.0 | 0.01/0.015/0.025 |
| raucher/einzel | DAV2008_T_R_U70 | 0.025 | 0.03 | 0.001/0.00125 | 12 | 0.005/50.0/200.0 | 0.02/0.03/0.05 |
| raucher/haus | DAV2008_T_R_U70 | 0.0 | 0.01 | 0.0008/0.001 | 0 | 0.0/0/0 | 0.0/0.0/0.0 |
| raucher/kollektiv | DAV2008_T_R_U70 | 0.015 | 0.015 | 0.0008/0.001 | 12 | 0.005/50.0/200.0 | 0.01/0.015/0.025 |

Tarifwerk der Generation **TG2015** (Ausgestaltung, Grundsatzdokumentation 10 Nr. 9): Erhöhungsscheiben mit $\gamma_1$: ja; Stornoabzug je Baustein: ja; Herabsetzungsverfahren: `teilkuendigung`.

Was sich von Generation zu Generation ändert (verkaufende Generationen in Verkaufsreihenfolge; leer heißt: nur das Fenster):

| Wechsel | geänderte Rechnungsgrundlagen |
|---|---|
| KLV-1994 → KLV-2000 | zins 4.00% → 3.25% |
| KLV-2000 → KLV-2004 | zins 3.25% → 2.75% |
| KLV-2004 → KLV-2007 | zins 2.75% → 2.25% |
| KLV-2007 → KLV-2008 | tafel DAV1994_T → DAV2008_T; policy_fee 24 → 30 |
| KLV-2008 → KLV-2012 | zins 2.25% → 1.75% |
| KLV-2012 → KLV-2015 | zins 1.75% → 1.25% |
| KLV-2015 → KLV-2017 | zins 1.25% → 0.90% |
| KLV-2017 → KLV-2022 | zins 0.90% → 0.25% |
| KLV-2022 → KLV-2025 | zins 0.25% → 1.00% |
<!-- /erzeugt -->

**TG2015, Teilkündigung und Abschlusskosten.** Bei der Teilkündigung gilt für den noch nicht getilgten Abschlusskostenrest dieselbe Regel wie in Abschnitt 7.1: Der fortgeführte Vertrag $f \cdot S$ trägt den Anteil $f$ des Rests, der Anteil $(1-f)$ geht mit dem gekündigten Teil (im Rückkaufswert der Auszahlung). Festlegung des Projekts, nicht Aussage der Quelle.

Migrierte Generationen kommen erst nach ihrer fachlichen Abnahme
(A-Q1/A-M1/A-M4) in eine Bestand-Config — dann mit der Knoten-ID ihres
Migrationsfalls und der durch Gate P-K1 geprüften Parametrierung. Die
erste ist die **TG2015 der Baldrian Leben** (`klv/tg2015`, Fall
`baldrian-klv-tg2015-lauf2`, A-M4 angenommen 2026-09-01): 834 Verträge,
Zugang zum 2026-01-01, seither im Tagesbetrieb der PLV im selben Strom
fortgeschrieben wie das eigene Geschäft. Sie hat keinen einen
Parametersatz, sondern sechs Tarifzellen (`status` × `tarifart`;
Rechnungszins 1,25 % nach Mitteilung, entschieden in A-Q1 gegen die 1,75 % des Tarifrechners; Tafeln DAV 2008 T Nichtraucher/Raucher U70); die
Zellen stehen in der Bestand-Config und werden nicht abgetippt. Diese
Tabelle wird maschinell gegen die Bestandskonfiguration geprüft; eine
Abweichung ist ein Fehler und blockiert.
