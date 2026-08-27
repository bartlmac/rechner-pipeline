---
title: "Tarifplan BU — Berufsunfähigkeitsversicherung (Beispielprodukt,
Zielrechenkern)"
lang: de
format:
  typst:
    papersize: a4
---

> Tarifplan des **Zielrechenkerns** für das BU-Beispielprodukt
> (`kern/produkte/bu.py`): die **Ausgestaltung** dieses Produkts. Das
> gemeinsame Rückgrat — Zustandsraum, Thiele-Rekursion,
> Rechnungsgrundlagen-Schicht, Numerik — steht einmal in der
> [Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md) und
> wird hier nicht wiederholt; die Gliederung ist für
> alle Produkte des Kerns dieselbe. Rechnungsgrundlagen sind die
> **DAV 1997 I** (unverändert übernommen, je Geschlecht).

# 1 Produktbeschreibung

Selbständige Berufsunfähigkeitsversicherung (SBU, Beispielumfang):
jährliche BU-Rente $R$ solange Berufsunfähigkeit besteht, längstens bis
zum Ablauf nach $n$ Jahren; Beitragszahlung nur im Zustand `aktiv`
(implizite Beitragsbefreiung im Leistungsfall). Keine Karenzzeit, keine
Leistungsdynamik; Kosten als proportionaler Zuschlag. Weder Todesfall-
noch Erlebensfallleistung.

# 2 Zustandsmodell

Drei Zustände, vier Übergänge:

| Zustand | Bedeutung |
|---|---|
| `aktiv` | erwerbsfähig, beitragszahlend (Anwärter) |
| `bu` | berufsunfähig, Rentenbezug |
| `tot` | absorbierend |

| Übergang | Wahrscheinlichkeit | Rechnungsgrundlage |
|---|---|---|
| aktiv $\to$ bu | Invalidisierung $i_x$ | `tafel_i` = DAV1997\_I |
| aktiv $\to$ tot | Aktivensterblichkeit $q^{a}_x$ | `tafel_aktiv` = DAV1997\_TAA |
| bu $\to$ aktiv | Reaktivierung $r(x, d)$ | `tafel_ri` = DAV1997\_RI (**Select**) |
| bu $\to$ tot | Invalidensterblichkeit $q^{i}(x, d)$ | `tafel_ti` = DAV1997\_TI (**Select**) |

$d$ ist die Zahl voller Jahre im Zustand `bu` (Select-Dauer, gekappt auf
die Select-Periode der Tafeln — hier 5). Der Verbleib je Zustand ist das
Residuum.

# 3 Bewertung

Die Bewertungsgleichung ist nicht produktspezifisch: Zustandsraum,
Thiele-Rückwärtsrekursion, Fälligkeits- und Diskontierungskonventionen
stehen in der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitte 3 und 4.

Für dieses Produkt ist die **Dauerabhängigkeit im Zustand `bu`
wesentlich**: Reaktivierung und Invalidensterblichkeit sind
Select-Grundlagen, die Verweildauer wird auf die Select-Periode der
Tafeln gekappt (hier 5 Jahre).

# 4 Zahlungsprofile

Je Einheit Jahresrente bzw. Jahresbeitrag, vorschüssig, Horizont $n$;
Übergangszahlungen gibt es keine ($u \equiv 0$):

| Baustein | Zahlungsprofil | Barwert |
|---|---|---|
| $L(s_0, d_0)$ | $z(\text{bu}, j) = 1$ | Rentenbarwert ab $(s_0, d_0)$ |
| $P(s_0, d_0)$ | $z(\text{aktiv}, j) = 1$ | Beitragsbarwert ab $(s_0, d_0)$ |

Die implizite Beitragsbefreiung steckt im Prämienprofil: im Zustand
`bu` wird nicht gezahlt.

# 5 Beiträge

Nach dem Äquivalenzprinzip, Kosten als proportionaler Zuschlag:

$$
p_{\text{netto}} \;=\; R \cdot \frac{L(\text{aktiv})}{P(\text{aktiv})},
\qquad
p_{\text{brutto}} \;=\; p_{\text{netto}} \cdot (1 + \text{zuschlag}).
$$

# 6 Reserven und Verlaufswerte

Prospektiv je Vertragsjahr $a \in [0, n]$, im Leistungsbezug zusätzlich
nach der Select-Dauer $d$:

$$
V_{\text{aktiv}}(a) = R\,L_a(\text{aktiv}) -
p_{\text{netto}}\,P_a(\text{aktiv}),
\qquad
V_{\text{bu}}(a, d) = R\,L_a(\text{bu}, d) -
p_{\text{netto}}\,P_a(\text{bu}, d).
$$

Per Konstruktion ist $V_{\text{aktiv}}(0) = 0$. $V_{\text{bu}}$ ist im
Wesentlichen der Rentenbarwert des laufenden Leistungsfalls (abzüglich
des Barwerts möglicher Prämien nach Reaktivierung) und wächst monoton
in der Select-Dauer $d$ (geringere Reaktivierungschance).

Hinweis zur Prämienstruktur: bei konstanter Nettoprämie über die volle
Laufzeit wird $V_{\text{aktiv}}$ in den letzten Vertragsjahren leicht
negativ — der Wert einer Invalidisierung fällt mit der Restlaufzeit
schneller, als das Invalidisierungsrisiko steigt. Rechnerisch korrekt
($V(0) = V(n) = 0$), bilanziell nicht ansetzbar; der Feinschliff der
Produktdefinition ist zurückgestellt.

# 7 Geschäftsvorfälle (GeVo-Katalog)

Buchungskonvention und die Einordnung der
Eintrittswahrscheinlichkeiten:
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 7. Der Betrag ist hier die vom GeVo betroffene
**Jahresrente** (Bezugsgröße der Nachweisung), nicht eine Auszahlung:
Todesfall- und Erlebensfallleistung kennt das Produkt nicht.

| GeVo | Wirkung | Betrag |
|---|---|---|
| **ZUG** Zugang | POL-Basiszeile ab Versicherungsbeginn | $R$ (Bestandsvolumen) |
| **INV** Invalidisierung | Statuswechsel aktiv $\to$ bu; Rentenbezug beginnt, Beitragsbefreiung greift; Reserve wechselt auf $V_{\text{bu}}(a, 0)$ | $R$ (beginnende Rente) |
| **REA** Reaktivierung | Statuswechsel bu $\to$ aktiv; Rente endet, Beitragspflicht lebt auf; Select-Dauer wird zurückgesetzt | $R$ (endende Rente) |
| **TOD** Tod | terminal | $R$ aus `bu`, sonst $0$ |
| **ABL** Ablauf | terminal bei $a = n$; eine laufende Rente endet mit dem Vertrag | $R$ aus `bu`, sonst $0$ |

Storno, Beitragsfreistellung und dynamische Erhöhung kennt das
Beispielprodukt nicht.

# 8 Modellpunkt und Tarif-Stellschrauben

Alle Größen sind Felder des Modellpunkts (`BUModelPoint`):

| Größe | Feld | Bedeutung |
|---|---|---|
| $x$, `sex`, $n$ | Vertragsfelder | Eintrittsalter, Geschlecht, Versicherungs- = Beitragsdauer |
| $R$ | `bu_rente` | versicherte Jahresrente |
| $i$ | `zins` | Rechnungszins |
| $i_x$ | `tafel_i` | Invalidisierung |
| $q^{a}_x$ | `tafel_aktiv` | Aktivensterblichkeit |
| $r(x,d)$ | `tafel_ri` | Reaktivierung (Select) |
| $q^{i}(x,d)$ | `tafel_ti` | Invalidensterblichkeit (Select) |
| — | `zuschlag` | proportionaler Kostenzuschlag |

Beispielpunkt: $x=35$, $n=30$, $R = 12\,000$, $i = 1{,}75\,\%$.

# 9 Gültigkeitsgrenzen

* **Tafelgrenze:** ab Alter 70 führt die DAV 1997 I die Invalidisierung
  als 1 (Tafelende, keine Übergangswahrscheinlichkeit); zusammen mit
  der Aktivensterblichkeit übersteigt die Wegzugsumme dort 1, und die
  Engine bricht fail-fast ab. Für Deckungen bis Endalter 67 ist der
  Bereich unerreichbar; die Bestands-Config prüft die Grenze beim Laden.
  Eine Erfahrungsannahme darf diese Grenze nicht wegtransformieren —
  die Prüfung läuft auf der untransformierten Tafel.
* Ein Modellpunkt ohne Leistungsmöglichkeit (Leistungsbarwert 0, z. B.
  $n = 1$ im Jahresmodell) ist fail-fast „nicht tarifierbar".
* Reserven im Zustand `bu`: fachliche Grenze $d \le a - 1$ (frühester
  BU-Eintritt am Ende von Jahr 0); oberhalb der Select-Periode wird auf
  deren Ultimate-Stufe gekappt. Ungleiche Select-Perioden von RI/TI sind
  fail-fast (sonst blieben Tafeldaten still unbenutzt).

# 10 Abgrenzung: Bewertung und Fortschreibung

Dieser Tarifplan beschreibt die **Bewertung** auf den
Rechnungsgrundlagen erster Ordnung. Die Trennung zu den
Erfahrungsannahmen dritter Ordnung steht in der
[Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 5.2. Für dieses Produkt ist die
Richtung der Transformation je Ausscheideordnung verschieden:
belastende Ordnungen (Invalidisierung) tragen $b < 1$, entlastende
(Reaktivierung) $b > 1$. Die Annahmen liegen unter `[annahmen]` der
Bestands-Config.

# 11 Verankerung und Abnahme

Das Abnahme-Protokoll gilt für alle Produkte
([Grundsatzdokumentation](../mathematik/grundsatzdokumentation.md),
Abschnitt 11). Für dieses Produkt sind
verankert: der Charakterisierungs-Anker `anker_bu_beispiel.json` (volle
Float-Präzision, Provenienz „DAV 1997 I"), der Engine-Selbsttest
Vorwärts- gegen Rückwärtsbewertung auf der echten BU-Konfiguration und
der Monte-Carlo-Abgleich der Bestandssimulation gegen die
Zustandsverteilung derselben Ordnung.

# 12 Vorgesehene Erweiterungen

Karenzzeit, Leistungsdynamik und Beitragsdynamik, Kostenstruktur
($\alpha/\beta/\gamma$ statt Pauschalzuschlag), unterjährige Zahlweise,
Rückkauf- und Beitragsfreistellungsregeln — jeweils als GeVo-Formeln in
Abschnitt 7 zu ergänzen, bevor sie implementiert werden.

# 13 PLV-Bestandsgenerationen

Die beiden BU-Bestandsgenerationen der Pfefferminzia LV (fiktives
Unternehmen dieses Arbeitsraums, siehe KLV-Tarifplan § 13) sind
konstruiert und tragen ihre Ontologie-Knoten-ID (Pflichtfeld `knoten`;
Präfix `plv_` = PLV-eigene Generation ohne Migrationsfall):

| Knoten | Name | gültig | Zins | Tafeln (aktiv/i/ri/ti) | Zuschlag |
|---|---|---|---|---|---|
| `bu/plv_2000` | BU-2000 | 2000-01–2016-12 | 1.75% | DAV1997_TAA/DAV1997_I/DAV1997_RI/DAV1997_TI | 0.05 |
| `bu/plv_2017` | BU-2017 | 2017-01–2035-12 | 0.90% | DAV1997_TAA/DAV1997_I/DAV1997_RI/DAV1997_TI | 0.05 |

Diese Tabelle wird maschinell gegen die Bestandskonfiguration
geprüft; eine Abweichung ist ein Fehler und blockiert.
