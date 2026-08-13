---
title: "Tarifplan KLV — Kapitallebensversicherung (Zielrechenkern)"
lang: de
format:
  typst:
    papersize: a4
---

> Tarifplan des **Zielrechenkerns** (`rechner_pipeline.kern`, ab Version
> 2.0.0). Dieses Dokument beschreibt das Produkt in der Mathematik des
> Kerns (Zustandsmodell, Thiele-Rekursion) und ist die fachliche
> Referenz für Implementierung, Abnahme und künftige marginale
> Änderungen. Historische Provenienz: einmalige Migration aus dem
> Quell-Workbook (Golden-Master 617/617); Quellnamen der Größen
> (`Bxt`, `kVx_MRV`, …) sind bewusst erhalten (Provenienz-Prinzip).

# Produktbeschreibung

Gemischte Kapitallebensversicherung (KLV): Die Versicherungssumme $S$
wird beim Tod der versicherten Person während der Versicherungsdauer
$n$, spätestens bei Erleben des Ablaufs fällig. Beitragszahlung über
$t \le n$ Jahre, unterjährige Zahlweise $zw \in \{1, 2, 4, 12\}$
möglich.

# Zustandsmodell

Das Produkt ist der Zwei-Zustands-Spezialfall des
Zustandsmodell-Rückgrats:

| Zustand | Bedeutung |
|---|---|
| `aktiv` | versicherte Person lebt; Vertrag in Kraft |
| `tot` | absorbierend |

Einziger Übergang: $\text{aktiv} \to \text{tot}$ mit der jährlichen
Sterbewahrscheinlichkeit $q_x$ der Tarif-Sterbetafel; Verbleib ist das
Residuum $1 - q_x$. Alle Barwerte entstehen über die
Thiele-Rückwärtsrekursion

$$
V_j(s) \;=\; z(s, j) \;+\; v \cdot \sum_{s'} p_{s \to s'}(x_0 + j)
\cdot \bigl( u(s, s', j) + V_{j+1}(s') \bigr),
\qquad v = \tfrac{1}{1+i},
$$

mit vorschüssigen Zustandszahlungen $z$ und nachschüssigen
Übergangszahlungen $u$ (fällig am Ende des Übergangsjahres). Die
klassische Kommutations-Schiene bleibt als permanente
Kreuz-Check-Schiene erhalten (Toleranz-Überleitung, `qa/ueberleitung`).

# Rechnungsgrundlagen und Tarif-Stellschrauben

Alle Größen sind Felder des Modellpunkts (`ModelPoint`) — eine neue
Tarifgeneration ist eine Parametrierung, keine Formeländerung:

| Größe | Feld | Bedeutung |
|---|---|---|
| $q_x$ | `tafel`, `sex` | Sterbetafel (z. B. DAV 1994 T, DAV 2008 T) |
| $i$ | `zins` | Rechnungszins |
| $\alpha$ | `alpha` | Abschlusskostensatz (Zillmer, je Einheit $S$ und Beitragsjahr) |
| $\beta_1$ | `beta1` | Inkassokostensatz auf den Beitrag |
| $\gamma_1, \gamma_2, \gamma_3$ | `gamma1..3` | Verwaltungskosten (beitragspflichtig, beitragsfrei) |
| $\kappa$ | `policy_fee` | Stückkosten p. a. |
| $z$ | `zillmer_dauer` | Amortisationsdauer der Abschlusskosten (Standard 5) |
| $s, u_{\min}, u_{\max}$ | `stoab_satz/min/max` | Stornoabschlag (Satz, Unter-/Obergrenze **je Vertrag**) |
| $r_{zw}$ | `ratzu_zw2/4/12` | Ratenzuschlag-Staffel |
| — | `min_alter_flex`, `min_rlz_flex` | flexible Ablaufphase |

# Barwert-Bausteine

Für Alter $y$, Dauer $m$, Überlebenswahrscheinlichkeiten
${}_{j}p_y = \prod_{k<j}(1 - q_{y+k})$:

$$
\ddot a_{y:m} = \sum_{j=0}^{m-1} v^j \, {}_j p_y, \qquad
A^{1}_{y:m} = \sum_{j=0}^{m-1} v^{j+1} \, {}_j p_y \, q_{y+j}, \qquad
E_{y:m} = v^m \, {}_m p_y .
$$

Gemischte Versicherung: $A_{y:m} = A^{1}_{y:m} + E_{y:m}$. Unterjährige
Zahlweise über das Abzugsglied $ab(k)$ (VBA-treu):
$\ddot a^{(k)}_{y:m} = \ddot a_{y:m} - ab(k)\,(1 - E_{y:m})$.

# Beiträge

Je Einheit Versicherungssumme ($\ddot a$ jeweils jährlich, $k=1$):

$$
B_{x,t} = \frac{A_{x:n} + \gamma_1 \ddot a_{x:t} +
\gamma_2 (\ddot a_{x:n} - \ddot a_{x:t})}{(1-\beta_1)\, \ddot a_{x:t} -
\alpha t} \qquad\text{(Bruttobeitragssatz Bxt)}
$$

$$
\text{BJB} = S \cdot B_{x,t}, \qquad
\text{BZB} = \frac{1 + r_{zw}}{zw}\,(\text{BJB} + \kappa), \qquad
P_{x,t} = \frac{A_{x:n} + t\,\alpha\,B_{x,t}}{\ddot a_{x:t}}
\;\;\text{(Netto, Pxt)}.
$$

# Verlaufswerte (Vertragsjahre $a = 0 \dots 50$)

Mit $y = x + a$ und Restdauern $n-a$, $t-a$:

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

# Geschäftsvorfälle (GeVo-Katalog)

Buchung auf Vertragsjahrestagen (Jahr $a$ wirtschaftet, Buchung am
Jahrestag $a{+}1$); jeder Betrag kommt aus dem Kern:

| GeVo | Wirkung | Betrag |
|---|---|---|
| **ZUG** Zugang | POL-Basiszeile ab Versicherungsbeginn | $S$ (Bestandsvolumen) |
| **ERH** dynamische Erhöhung | neue Scheibe: eigener Modellpunkt mit $x' = x{+}a$, $n' = n{-}a$, $t' = t{-}a$, $S' = e \cdot S^{ges}$ (Zinseszins); kein Statuswechsel | $S'$ |
| **PEX** Beitragsfreistellung | Statuswechsel; fixiert $\sum_{\text{Scheiben}} S^{bfr}_a$; danach beitragsfreier Track | $\sum S^{bfr}_a$ |
| **STO** Rückkauf | terminal; nur beitragspflichtig, $a < n$ | $\text{RKW}_a$ (vertragsweiter StoAb) |
| **TOD** Tod | terminal | $S^{ges}$ bzw. nach PEX $\sum S^{bfr}$ |
| **ABL** Ablauf | terminal bei $a = n$ | $S^{ges}$ bzw. $\sum S^{bfr}$ |

# Gültigkeitsgrenzen

* Verlaufswerte sind blattfest für $a \in [0, 50]$ verankert
  (Golden-Master-Contract, 612 Zellen). Der Kern rechnet Skalare auch
  für $n > 50$ (der Verlauf bleibt bei 51 Zeilen); die Bestand-Engine
  weist Laufzeiten $n > 50$ ab.
* Tafelbereich: Anker-Alter mit $D_x = 0$ (Tafel erschöpft, z. B.
  DAV 1994 T ab Alter 101) sind fail-fast; kein Alter über 123.
* Kein Storno beitragsfreier Verträge (keine RKW-Regel definiert).

# Verankerung und Abnahme

617/617-Excel-Parität (Migrationsbeleg, 4 Nachkommastellen),
Charakterisierungs-Anker in voller Float-Präzision (Voll-Präzisions-
Verankerung des produktiven Pfads), Toleranz-Überleitung beider
Rechenschienen (`qa/ueberleitung`). Änderungen folgen dem
Abnahme-Protokoll des Kerns (`kern/__init__`).

# Vorgesehene Erweiterungen

Beitragsreduktion, Wiederinkraftsetzung, monatsgenaues Ereignisgitter,
Überschussbeteiligung — jeweils als GeVo-Formeln in diesem Tarifplan zu
ergänzen, bevor sie implementiert werden.
