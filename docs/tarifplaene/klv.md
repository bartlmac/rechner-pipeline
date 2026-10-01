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

# 7 Geschäftsvorfälle (GeVo-Katalog)

Buchungskonvention und die Einordnung der
Eintrittswahrscheinlichkeiten:
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 7. Jeder Betrag kommt aus dem Kern.

| GeVo | Wirkung | Betrag |
|---|---|---|
| **ZUG** Zugang | POL-Basiszeile ab Versicherungsbeginn | $S$ (Bestandsvolumen) |
| **ERH** dynamische Erhöhung | neue Scheibe: eigener Modellpunkt mit $x' = x{+}a$, $n' = n{-}a$, $t' = t{-}a$, $S' = e \cdot S^{ges}$ (Zinseszins), ohne $\gamma_1$ (Bezugsgröße GrundVS); kein Statuswechsel | $S'$ |
| **PEX** Beitragsfreistellung | Statuswechsel; fixiert $\sum_{\text{Scheiben}} S^{bfr}_a$; danach beitragsfreier Track | $\sum S^{bfr}_a$ |
| **RED** Beitragsherabsetzung | Beitrag sinkt am Jahrestag $a_0$ auf den Anteil $f$ (7.1); nur während der Beitragszahlung ($0 < a_0 < t$) und ohne PEX — danach verweigert, Ausweg ist die Teilkündigung. Verfahren je Generation: prospektiv und mit Abzug wandeln den freiwerdenden Anteil in eine beitragsfreie Summe um (geknicktes Zahlungsprofil, der Vertrag wird nicht geteilt), es fließt kein Geld; eine Generation mit `teilkuendigung` führt den Wunsch als Teilkündigung aus (Annahme A1, 7.2). Kein Statuswechsel; Abschlusskosten folgen dem Beitrag; die Dynamik läuft weiter; eine spätere PEX fixiert die Gesamtsumme | neue Gesamtsumme (`VS_herabsetzung`); absorbierte Korrekturschicht (`dDK_absorption`) |
| **TKU** Teilkündigung | Anteil $(1-f)$ der Grundversicherungssumme gekündigt und mit dem Rückkaufswert nach Tarifwerk (Stornoabzug) ausgezahlt; in jeder Generation, beitragspflichtig wie ausfinanziert ($0 < a_0 < n$), ohne PEX; der Vertrag läuft zustandslos mit $f \cdot S$, die Scheiben unverändert (7.2). Kein Statuswechsel | neue Gesamtsumme (`VS_teilkuendigung`); absorbierte Korrekturschicht (`dDK_absorption`); Auszahlung $(1-f)\,\text{RKW}^{Grund}_{a_0}$ + Schicht (`RKW_teilkuendigung`), auf null gekappt, ein gekappter Betrag als `Kappung_teilkuendigung` |
| **STO** Rückkauf | terminal; nur beitragspflichtig, $a < n$ | $\text{RKW}_a$ (vertragsweiter StoAb) |
| **TOD** Tod | terminal | $S^{ges}$ bzw. nach PEX $\sum S^{bfr}$ |
| **ABL** Ablauf | terminal bei $a = n$ | $S^{ges}$ bzw. $\sum S^{bfr}$ |

Drei Einträge dieser Tabelle sind Tarifwerks-Eigenschaften, die eine
übernommene Generation anders tragen kann als das eigene Geschäft:
ob eine Erhöhungsscheibe $\gamma_1$ trägt (`scheiben_mit_gamma1`; die
zweite Baldrian-Lieferung rechnet jeden Baustein mit voller
Beitragsformel), ob der Stornoabzug je Baustein greift
(`stoab_je_baustein`, Abschnitt 6) und nach welchem Verfahren eine
Herabsetzung rechnet (`red_verfahren`, Abschnitt 7.1; eine Generation
mit `teilkuendigung` kennt keine Herabsetzung ohne Auszahlung und führt den
Wunsch als Teilkündigung aus, Abschnitt 7.2, Annahme A1). Alle drei stehen je Generation in der
Bestand-Config, die Führung liest sie dort, und die Freischaltung
eines Migrationsfalls überträgt sie aus den bestandenen Abnahmen
(`dev-docs/freischaltung-uebernommener-bestand.md`).

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
(7.2), die es in jeder Generation auch nach $t$ gibt. Ein übernommener
Vertrag mit einer Absetzung nach $t$ in seiner Vorgeschichte wird in den
Bestand integriert — als Teilkündigung (7.2, Annahme A2; *Entscheid des
Maintainers 2026-10-01*: „ein Problem des Ziels, nicht der Migration“).
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
bezogen auf seine herabgesetzte Summe. Die Teilkündigung (Ziffer 6)
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

Die Teilkündigung (`TKU`) kündigt den Anteil $(1-f)$ der
**Grundversicherungssumme** und zahlt seinen Rückkaufswert nach dem
Tarifwerk der Generation aus, mit deren Stornoabzug (je Vertrag oder je
Baustein, Abschnitt 6); der Vertrag läuft danach zustandslos mit
$f \cdot S$ weiter, die Erhöhungsscheiben unverändert:

$$
S_{\text{danach}} = f \cdot S + \sum_i S_i, \qquad
\text{Auszahlung} = \max\left(0,\; (1-f)\,\text{RKW}^{Grund}_{a_0} + \text{Schicht}_{a_0}\right),
$$

eine gekappte negative Summe wird als `Kappung_teilkuendigung` ausgewiesen.
Sie setzt keinen laufenden Beitrag voraus und ist in **jeder** Generation
beitragspflichtig wie ausfinanziert möglich, für $0 < a_0 < n$ — vor $t$
zahlt der Vertrag danach den Beitrag seiner fortgeführten Summe. Gebucht
wird sie unter dem eigenen Code `TKU` (`VS_teilkuendigung`,
`dDK_absorption`, `RKW_teilkuendigung`, `Kappung_teilkuendigung`), nie als
`RED`; das Bewegungskonto führt sie als eigene Position „Teilkündigung“.
Die Ereignis-Engine zieht sie mit einer eigenen Rate
`annahmen.teilkuendigung` (Vorgabe 0) und einem eigenen Anteil
`annahmen.tk_anteil` aus einem eigenen Zufallsstrom; ohne Rate rechnet
jede Generation bitgleich wie vor dem Entscheid.

Verworfen wurden:

* **ein** Vorgang mit Verfahrensschalter und stiller Umdeutung (die
  zunächst gebaute „Regel A“: nach $t$ rechnet jede Herabsetzung als
  Teilkündigung und wird als `RED` gebucht) — es sind zwei Vorgänge mit
  verschiedener Wirkung, und das Ledger muss sagen, was geschah;
* die Umwandlung des Anteils $(1-f)$ in beitragsfreie Summe auch nach $t$ —
  sie ergäbe $q = (1-f)$ und damit die volle Summe: keine Absetzung;
* die Auszahlung ohne Stornoabzug in einer Generation mit `prospektiv` —
  gekündigt wird ein Summenanteil, und der Tarif sieht für den Rückkauf den
  Abzug vor;
* eine anteilige Kündigung aller Bausteine bei dynamisierten Verträgen —
  „anteilig über alle Schichten“ begründet die Verteilung des freiwerdenden
  **Beitrags** einer Herabsetzung (7.1), nicht die Kündigung eines
  Summenanteils; die Teilkündigung des Bedingungswerks lässt die Erhöhungen
  unberührt.

**Annahmen** (im Auftrag gesetzt, nicht vom Maintainer entschieden; je
einzeln prüfbar):

* *A1 — die Generation TG2015.* Eine Generation mit
  `red_verfahren = teilkuendigung` kennt keine Herabsetzung ohne Auszahlung:
  Sie führt den Herabsetzungswunsch (`annahmen.herabsetzung`, vor $t$) als
  Teilkündigung aus und bucht `TKU`. Eigene Generationen bleiben
  `prospektiv` (Vorgabe). Ein Schalter, validiert; kein zweites Wissen.
* *A2 — die Vorgeschichte.* Eine gelieferte Absetzung ist vor $t$, was das
  Verfahren der Quelle sagt, nach $t$ immer eine Teilkündigung
  (`alt_absetzung_ist_teilkuendigung`).
* *A3 — nur die Grundversicherung.* Die Teilkündigung trifft die
  Grundversicherung; die Erhöhungsscheiben laufen unverändert.
* *A4 — ein Vorgang je Vertrag.* Die Führung trägt höchstens eine
  Herabsetzung oder Teilkündigung je Vertrag; gebaut ist nur, was der Kern
  ohne neue Regel trägt.

**Verweigert, mit der fehlenden Regel:**

| Kombination | Was fehlt |
|---|---|
| Herabsetzung ab $t$ | Ein Beitrag, den sie senken könnte — Ausweg ist die Teilkündigung. |
| Teilkündigung oder Herabsetzung nach einer Beitragsfreistellung | Eine Regel, welchen Anteil der beitragsfreien Summe eine Kündigung trifft und mit welchem Abzug; die Engine zieht für beitragsfrei gestellte Verträge nicht, das Datenmodell lehnt die Zeile ab. |
| Teilkündigung nach einer Herabsetzung | Eine Regel, wie ein Summenanteil eines geknickten Verlaufs (Beitragsteil plus umgewandelte Summe) gekündigt wird. |
| Herabsetzung nach einer Teilkündigung | Eine Regel für den zweiten Knick auf dem Folgevertrag, den der Kern als einen Verlauf mit **einem** Knick führt. |
| zweite Herabsetzung oder zweite Teilkündigung in der Führung | Die Verkettung zweier Vorgänge im Kern (`reduktionen` trägt eine Zeile je Vertrag). |

Eine Teilkündigung in der **Vorgeschichte** eines übernommenen Vertrags
zählt dabei nicht mit: Sie hinterlässt den zustandslosen Vertrag mit
$f \cdot S$ (Einzelfall) bzw. Grund $f \cdot G$ plus Scheiben (Serie), auch
mehrere hintereinander.

**Ableitung im Migrationszugang.** Geliefert ist die heutige Summe
(`ERLSUMME`). Nach einer Teilkündigung gilt $\text{ERLSUMME} = f \cdot S$:
eine Gleichung mit zwei Unbekannten, und nach $t$ keine Beitragsgleichung
(`JBRUTTO` = 0). Für den Wert des Vertrags genügt das: Er ist der
zustandslose Vertrag mit der gelieferten Summe und wird ohne Anfangszustand
übernommen. Wo der Anteil wirkt — in einer Folge aus Erhöhungen und einer
späteren Absetzung verteilt er die gelieferte Summe auf Grund und
Erhöhungen —, kommt er als registrierte Auskunft der abgebenden
Gesellschaft (`--red-anteile-datei`, `POLNR;GEVO;DATUM;ANTEIL`); mit ihm ist
$S = \text{ERLSUMME} / f$ bestimmt.

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
