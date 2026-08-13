---
title: "Tarifplan BU — Berufsunfähigkeitsversicherung (Beispielprodukt, Zielrechenkern)"
lang: de
format:
  typst:
    papersize: a4
---

> Tarifplan des **Zielrechenkerns** für das BU-Beispielprodukt
> (`kern/produkte/bu.py`). Rechnungsgrundlagen sind seit 2026-08-13 die
> **DAV 1997 I**: `DAV1997_I` (Invalidisierung), `DAV1997_TAA`
> (Aktivensterblichkeit), `DAV1997_RI` (Reaktivierung) und `DAV1997_TI`
> (Invalidensterblichkeit) — die beiden letzten als Select-Tafeln mit
> Select-Periode 5, alle je Geschlecht und unverändert übernommen.
> **Gültigkeitsgrenze:** ab Alter 70 führt die Tafel die Invalidisierung
> als 1; als Übergangswahrscheinlichkeit ist sie dort zusammen mit der
> Aktivensterblichkeit unbrauchbar, die Engine bricht fail-fast ab. Für
> Deckungen bis Endalter 67 ist der Bereich unerreichbar.

# Produktbeschreibung

Selbständige Berufsunfähigkeitsversicherung (SBU, Beispielumfang):
jährliche BU-Rente $R$ solange Berufsunfähigkeit besteht, längstens bis
zum Ablauf nach $n$ Jahren; Beitragszahlung nur im Zustand `aktiv`
(implizite Beitragsbefreiung im Leistungsfall). Keine Karenzzeit, keine
Leistungsdynamik; Kosten als proportionaler Zuschlag.

# Zustandsmodell

Das erste Produkt, das ausschließlich als Konfiguration des
Zustandsmodell-Rückgrats existiert — drei Zustände, vier
Ausscheideordnungen:

| Übergang | Wahrscheinlichkeit | Tafel (Modellpunkt-Feld) |
|---|---|---|
| aktiv $\to$ bu | Invalidisierung $i_x$ | `tafel_i` (Alterstafel) |
| aktiv $\to$ tot | Aktivensterblichkeit $q^{a}_x$ | `tafel_aktiv` |
| bu $\to$ aktiv | Reaktivierung $r(x, d)$ | `tafel_ri` (**Select**) |
| bu $\to$ tot | Invalidensterblichkeit $q^{i}(x, d)$ | `tafel_ti` (**Select**) |

$d$ ist die Zahl voller Jahre im Zustand `bu` (Select-Dauer, gekappt
auf die Select-Periode der Tafeln — Semi-Markov über die
Zustandsraum-Erweiterung der Engine). Verbleib je Zustand ist das
Residuum; `tot` ist absorbierend.

# Zahlungsprofile und Bewertung

Je Einheit Jahresrente bzw. Jahresbeitrag, vorschüssig, Horizont $n$:

* Leistungsprofil: $z_L(s, j) = \mathbf 1\{s = \text{bu}\}$,
* Prämienprofil: $z_P(s, j) = \mathbf 1\{s = \text{aktiv}\}$.

Alle Barwerte über die Thiele-Rückwärtsrekursion des Rückgrats. Mit
$L(s_0, d_0)$ bzw. $P(s_0, d_0)$ als Barwerte der beiden Profile ab
Startzustand $s_0$ (Startdauer $d_0$):

$$
p_{\text{netto}} \;=\; R \cdot \frac{L(\text{aktiv})}{P(\text{aktiv})}
\quad\text{(Äquivalenzprinzip)}, \qquad
p_{\text{brutto}} = p_{\text{netto}} \cdot (1 + \text{zuschlag}).
$$

# Reserven

Prospektiv, je Vertragsjahr $a \in [0, n]$:

$$
V_{\text{aktiv}}(a) = R\,L_a(\text{aktiv}) - p_{\text{netto}}\,P_a(\text{aktiv}),
\qquad
V_{\text{bu}}(a, d) = R\,L_a(\text{bu}, d) - p_{\text{netto}}\,P_a(\text{bu}, d).
$$

Per Konstruktion ist $V_{\text{aktiv}}(0) = 0$. $V_{\text{bu}}$ ist im
Wesentlichen der Rentenbarwert des laufenden Leistungsfalls (abzüglich
des Barwerts möglicher Prämien nach Reaktivierung) und wächst monoton
in der Select-Dauer $d$ (geringere Reaktivierungschance).
$V_{\text{bu}}(a, d)$ ist der Anschlusspunkt der Ereignis-Engine für
BU-Bestände.

# Modellpunkt (Tarif-Stellschrauben)

`BUModelPoint`: $x$, `sex`, $n$, $R$ (`bu_rente`), $i$ (`zins`),
vier Tafelnamen, `zuschlag`. Beispielpunkt: $x=35$, $n=30$,
$R = 12\,000$, $i = 1{,}75\,\%$.

# Gültigkeitsgrenzen

* Alter $x + n - 1 \le 123$ (Tafelbereich, fail-fast); die
  Invalidisierung ist außerhalb des Erwerbsalters (18–66) null — ein
  Modellpunkt ohne jede Leistungsmöglichkeit (Leistungsbarwert 0, z. B.
  Start nach dem Erwerbsalter oder $n = 1$ im Jahresmodell) ist
  fail-fast „nicht tarifierbar".
* Reserven im Zustand `bu`: fachliche Grenze $d \le a - 1$ (frühester
  BU-Eintritt am Ende von Jahr 0; unmögliche Kombinationen fail-fast);
  oberhalb der Select-Periode wird auf deren Ultimate-Stufe gekappt
  (Beispieltafeln: 5 Jahre). Ungleiche Select-Perioden von RI/TI sind
  fail-fast (sonst blieben Tafeldaten still unbenutzt).
* Wegzugsummen je Zustand müssen $\le 1$ sein (Engine fail-fast;
  Datenprüfung beider Zustände über alle Aktiventafeln testseitig
  verankert).

# Verankerung und Abnahme

Charakterisierungs-Anker `anker_bu_beispiel.json` (volle
Float-Präzision, Provenienz „DAV 1997 I"); Engine-Selbsttest
Vorwärts- gegen Rückwärtsbewertung auf der echten BU-Konfiguration.
Änderungen folgen dem Abnahme-Protokoll des Kerns.

# Vorgesehene Erweiterungen

Karenzzeit, Leistungsdynamik und Beitragsdynamik, Kostenstruktur
($\alpha/\beta/\gamma$ statt Pauschalzuschlag), unterjährige Zahlweise,
Rückkauf-/Beitragsfreistellungsregeln. **Erledigt:** echte
DAV-Ausscheideordnungen (2026-08-13) und die BU-GeVos der Ereignis-Engine
(Invalidisierung/Reaktivierung als Statuswechsel, siehe Bestandsmodul).

Offener Punkt zur Prämienstruktur: bei konstanter Nettoprämie über die
volle Laufzeit wird die Anwärterreserve in den letzten Vertragsjahren
leicht negativ (der Wert einer Invalidisierung fällt mit der Restlaufzeit
schneller, als das Invalidisierungsrisiko steigt). Rechnerisch korrekt
($V(0) = V(n) = 0$), bilanziell nicht ansetzbar — Feinschliff der
Produktdefinition ist bewusst zurückgestellt.
