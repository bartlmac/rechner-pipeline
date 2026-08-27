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
> 22.07.2026 — historisch, kein laufender Anker); Quellnamen
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
{}_a V^{MRV} / {}_a V^{bfr} & a < t \\
S & t \le a \le n \\
0 & a > n .
\end{cases}
$$

Flexible Phase: $y \ge$ `min_alter_flex` **und**
$a \ge n -$ `min_rlz_flex`.

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
| **STO** Rückkauf | terminal; nur beitragspflichtig, $a < n$ | $\text{RKW}_a$ (vertragsweiter StoAb) |
| **TOD** Tod | terminal | $S^{ges}$ bzw. nach PEX $\sum S^{bfr}$ |
| **ABL** Ablauf | terminal bei $a = n$ | $S^{ges}$ bzw. $\sum S^{bfr}$ |

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
Rechnungsgrundlagen erster Ordnung. Die Trennung zu den
Erfahrungsannahmen dritter Ordnung, aus denen die Fortschreibung ihre
Ereigniswahrscheinlichkeiten bildet, steht in der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 5.2. Für dieses Produkt liegen
die Annahmen unter `[annahmen]` der Bestands-Config.

# 11 Verankerung und Abnahme

Das Abnahme-Protokoll gilt für alle Produkte
([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 11). Für dieses Produkt sind
verankert: die Charakterisierungs-Anker des produktiven Pfads, die
Toleranz-Überleitung gegen den Kommutations-Zweitkern
(`qa/ueberleitung`) und je Migrationsfall Gate O3 gegen den
Quell-Rechner. Die einmalige 617/617-Excel-Parität (22.07.2026, 4
Nachkommastellen) ist der historische Übersetzungsbeleg, kein
laufender Anker.

# 12 Vorgesehene Erweiterungen

Beitragsreduktion, Wiederinkraftsetzung, monatsgenaues Ereignisgitter,
Überschussbeteiligung — jeweils als GeVo-Formeln in Abschnitt 7 zu
ergänzen, bevor sie implementiert werden.

# 13 PLV-Bestandsgenerationen

Die **Pfefferminzia Lebensversicherung (PLV)** ist das fiktive
Unternehmen dieses Arbeitsraums: Zielkern und Bestand gehören ihr,
Migrationsfälle übernehmen fremde Bestände in die PLV. Ihre neun
KLV-Bestandsgenerationen sind konstruiert (kein Migrationsfall, keine
Quell-Provenienz) und tragen — wie jede Generation, die das System
rechnet — eine **Ontologie-Knoten-ID** (Pflichtfeld `knoten` der
Bestand-Config, dieselbe Konvention wie A-Box und Gate O3; Wurzel =
Produktfamilie, Präfix `plv_` = PLV-eigene Generation ohne
Migrationsfall):

| Knoten | Name | gültig | Zins | Tafel | $\alpha$ | $\beta_1$ | $\gamma_{1/2/3}$ | $\kappa$ |
|---|---|---|---|---|---|---|---|---|
| `klv/plv_1994` | KLV-1994 | 1994-07–2000-06 | 4.00% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 |
| `klv/plv_2000` | KLV-2000 | 2000-07–2003-12 | 3.25% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 |
| `klv/plv_2004` | KLV-2004 | 2004-01–2006-12 | 2.75% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 |
| `klv/plv_2007` | KLV-2007 | 2007-01–2007-12 | 2.25% | DAV1994_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 24 |
| `klv/plv_2008` | KLV-2008 | 2008-01–2011-12 | 2.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 |
| `klv/plv_2012` | KLV-2012 | 2012-01–2014-12 | 1.75% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 |
| `klv/plv_2015` | KLV-2015 | 2015-01–2016-12 | 1.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 |
| `klv/plv_2017` | KLV-2017 | 2017-01–2021-12 | 0.90% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 |
| `klv/plv_2022` | KLV-2022 | 2022-01–2035-12 | 0.25% | DAV2008_T | 0.025 | 0.025 | 0.0008/0.00125/0.0025 | 30 |

Migrierte Generationen kommen erst nach ihrer fachlichen Abnahme
(G-1/G-A/G-2) in eine Bestand-Config — dann mit der Knoten-ID ihres
Migrationsfalls (z. B. `klv/tg2015`) und der durch Gate O3 geprüften
Parametrierung. Diese Tabelle ist test-verankert gegen die Config:
weicht sie ab, fällt die Suite.
