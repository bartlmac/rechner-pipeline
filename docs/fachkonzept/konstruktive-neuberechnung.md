---
title: "Fachkonzept: Konstruktive Neuberechnung und Korrekturschicht"
subtitle: "Bestandsmigration Leben ohne Historienmigration im Semi-Markov-Rechenkern"
lang: de-DE
date: 2026-08-26
---

| Feld | Wert |
|---|---|
| Dokumenttyp | Fachkonzept (fachlich normativ, technisch offen) |
| Status | Entwurf zur Abstimmung |
| Version | 0.2 |
| Änderungen 0.2 | Verweildauer $u_0$ im Verankerungszustand nachgezogen (Kap. 2, 4.4, 4.7, 5.4, Anhang A); neues Kap. 5.5 „Rolle der Vertragshistorie"; Archiv-Schnittstelle (1.2); Migrationskonzept in Dokumentenhierarchie (1.3); Kap. 9 Nr. 11 |
| Autor | ⟨…⟩ |
| Fachliche Freigabe | ⟨Verantwortlicher Aktuar / Fachexperte Aktuariat⟩ |
| Technische Abstimmung | ⟨Entwicklung Rechenkern⟩ |

---

## 0 Zusammenfassung

Dieses Konzept beschreibt, wie Lebensversicherungsverträge ohne Migration ihrer Vertragshistorie aktuariell konsistent in den Zielrechenkern übernommen werden. Kern der Methode ist die **konstruktive Neuberechnung**: Der Vertrag wird im Initialzustand migriert und an einem definierten Verankerungszeitpunkt unter Vorgabe anrechenbarer Werte neu gerechnet. Die dabei entstehende, vollständig determinierte Differenz zwischen geliefertem und prospektiv gerechnetem Deckungskapital wird als **Korrekturschicht** geführt — eine zusätzliche Bewertungsschicht auf dem bestehenden Zustandsraum, deren Wert über die Restlaufzeit per Konstruktion gegen Null läuft.

Nach außen sichtbare Werte bleiben unverändert: Beitrag und garantierte Leistungen (Kundensicht) sowie Deckungskapital und Rückkaufswert (Aufsichts-/Bilanzsicht).

> **Leitprinzip:** Die Korrekturschicht ist Deckungskapital und verhält sich an jedem Übergang exakt so, wie sich Deckungskapital dort verhält — angerechnet, ausgezahlt oder vererbt. Nur ihre Finanzierung ist fiktiv.

Alle weiteren Abschnitte sind Ausbuchstabierung dieses Satzes. Das Konzept ist **fachlich normativ** (Invarianten, Bewertungsdynamik, Übergangsverhalten, Dokumentations- und Testpflichten) und lässt die **technische Realisierung bewusst offen**; die Freiheitsgrade sind in Kapitel 9 benannt.

---

## 1 Zweck, Geltungsbereich, Einordnung

### 1.1 Ausgangslage und Ziel

Bei der Migration von Lebensversicherungsbeständen ist die Vertragshistorie (Bewegungsdaten seit Beginn) häufig nicht oder nicht wirtschaftlich migrierbar. Der Vertrag soll dennoch ab dem Migrationsstichtag im Zielsystem **rechenfähig** sein: künftige Geschäftsvorfälle, Fortschreibung und Bewertung laufen vollständig in der Logik des Zielrechenkerns, ohne Rückgriff auf das Quellsystem.

Harte Anforderung: Die konstruktive Neuberechnung darf keine nach außen sichtbaren Wertänderungen erzeugen.

### 1.2 Geltungsbereich und Abgrenzung

**In Scope:** klassisches und klassisch bewertbares Leben-Geschäft im Semi-Markov-Rechenkern; die aktuarielle Methodik der Übernahme (Verankerung, Korrekturschicht, Übergangsverhalten, Test).

**Out of Scope, aber als Schnittstelle benannt:**

- Datenmigrationstechnik, Mapping der Bestandsführungsattribute.
- Migration nicht-aktuarieller, aber existenzieller Vertragsattribute (Steuerkohorte, Förderstatus, Zertifizierungen). Diese dürfen durch die konstruktive Neuberechnung nicht verändert werden; ihre Übernahme ist separat zu konzipieren.
- Fehlerkorrektur im Sinne einer Veränderung von Ankerwerten (siehe 3.4).
- Historienarchiv/Auskunftssystem: Die nicht migrierte Vertragshistorie muss dauerhaft auskunftsfähig bleiben (Aufbewahrungspflichten, Auskunftsersuchen, Rückabwicklungsfälle — siehe 5.5). Das Archiv ist verpflichtendes Begleitartefakt der Migration; die Lösung wird im Migrationskonzept konzipiert, nie als Anforderung an den Rechenkern.
- Überschussguthaben/Bonussummen: werden als eigene Schicht(en) übernommen und sind **nicht** Teil der Kalibrierung der Korrekturschicht.

### 1.3 Dokumentenhierarchie

Dieses Fachkonzept steht an der Spitze einer dreistufigen Dokumentation:

1. **Fachkonzept** (dieses Dokument): Methode, Invarianten, Prozess- und Testrahmen, Freiheitsgrade.
2. **Grundsatzdokumentation** (Kap. 8.1): normative Mathematik und Numerik. *Die Implementierung folgt der Grundsatzdokumentation, nicht umgekehrt.*
3. **Produktspezifische Ausgestaltung** (Kap. 8.2): je Tarifplan des Zielsystems die konkrete Belegung aller produktabhängigen Festlegungen.

Diese drei Dokumente sind produktseitig und stabil (Freigabekreis: Aktuariat/Entwicklung). Daneben steht projektseitig das **Migrationskonzept** — je Bestand/Quellsystem instanziiert (Freigabekreis: Projekt, Quellsystem-Verantwortliche): Systemkontext Migrationssystem/Rechenkern, Datenliefervertrag und Mapping, Migrationszugangsroutine, Controlling- und Klärungsprozesse, Archivlösung. Das Migrationskonzept referenziert das Fachkonzept, nie umgekehrt.

---

## 2 Begriffe und Notation

| Symbol / Begriff | Bedeutung |
|---|---|
| $t_0$ | Migrationsstichtag (logischer Übernahmezeitpunkt im Zielsystem) |
| $t_a$ | Verankerungszeitpunkt: letzter exakter Rechenpunkt des Quellsystems (Kap. 5) |
| $T$ | Vertragsablauf |
| $(Z_t, U_t)$ | Zustand und Verweildauer des Semi-Markov-Prozesses (Biografie des Versicherten) |
| $i_0$, $u_0$ | Verankerungszustand und Verweildauer in diesem Zustand am Verankerungszeitpunkt $t_a$ — $u_0$ ist historienabgeleitetes Lieferattribut (5.4) |
| $\delta(t)$, $\mu_{ij}(t,u)$ | Zinsintensität, Übergangsintensitäten der jeweiligen Rechnungsgrundlagen |
| Anker | Wert, der durch die Migration nicht verändert werden darf (Kap. 3.2) |
| $V^{\mathrm{ist}}$ | vom Quellsystem gelieferter Deckungskapitalwert |
| $V^{\mathrm{prosp}}$ | prospektiver Wert der Basisschicht im Zielkern aus Vertragsparametern |
| $R$ | Residuum $V^{\mathrm{ist}} - V^{\mathrm{prosp}}$ am Verankerungszeitpunkt |
| $R_{\mathrm{hist}}$, $R_{\mathrm{conv}}$ | Historienresiduum (Verankerung $t_a$) bzw. Konventionsresiduum (optional, $t_0$; Kap. 5.3) |
| Korrekturschicht | Bewertungsschicht mit Zahlungsfunktionen $c_i(t,u)$, $c_{ij}(t,u)$; Wert $V^{\mathrm{korr}}$ |
| $g$, $\rho$ | Formfunktion des Amortisationsstroms und kalibrierter Skalierungsfaktor, $c_i = \rho\, g$ |
| $F_i$ | Menge der *vererbenden* Übergänge aus Zustand $i$ (Kap. 4.2) |
| $\Pi_i(t)$ | Barwert des Einheitsstroms $g$ unter der Korrekturschicht-Dynamik |
| $\mathcal{A}(t, i, R)$ | Verankerungsoperator: kalibriert $\rho$ so, dass $V^{\mathrm{korr}}(t) = R$ (Kap. 4.4) |
| Rechnender GV | Geschäftsvorfall, der im Zielsystem eine äquivalenzerhaltende Neuberechnung mit Kapitalanrechnung auslöst |

---

## 3 Methodik der konstruktiven Neuberechnung

### 3.1 Zwei-Schritt-Prinzip

1. **Migration im Initialzustand.** Der Vertrag wird mit seinen Ursprungsparametern angelegt: Versicherungsbeginn, Eintrittsalter, Tarif und **mitwandernde Rechnungsgrundlagen** (Rechnungszins, Ausscheideordnung, Kostensätze der Bestandsgruppe), ursprüngliche Summe/Beitrag, Ablauf. Keine Historie erforderlich.
2. **Konstruktive Neuberechnung am Verankerungszeitpunkt $t_a$.** Ein Geschäftsvorfall des Zielsystems rechnet den Vertrag unter **Vorgabe anrechenbarer Werte** (Anker) neu. Die Differenz zwischen geliefertem und prospektivem Deckungskapital wird über den Verankerungsoperator in die Korrekturschicht gebucht.

Grundsatz: Die Neuberechnung nutzt einen **regulären Geschäftsvorfalltyp** des Zielsystems (Neuberechnung mit Kapitalanrechnung), keinen migrationsspezifischen Sonderrechenpfad. Der Vertrag rechnet nach der Migration in derselben Logik weiter, in der er übernommen wurde.

### 3.2 Ankerhierarchie

Default-Priorisierung, finale Festlegung inkl. Toleranzen je Tarifplan in der Ausgestaltung (Kap. 8.2):

| Prio | Anker | Härte | Begründung |
|---|---|---|---|
| 1 | Garantierte Leistungen (Todesfall, Ablauf/Rente, beitragsfreie Summen) | hart | vertraglich zugesagt |
| 2 | Zahlbeitrag | hart | Kundensicht, Inkasso |
| 3 | Deckungskapital | hart | Bilanz, kein unerklärter Sprung |
| 4 | Rückkaufswert / Mindestwerte nach § 169 VVG | hart | gesetzlich |
| 5 | Künftiger Wertverlauf | weich | über Formfunktion und Tests gesteuert (Kap. 4.5, 6.3) |

Präzisierung zur DK-Invarianz: Gefordert ist **kein unerklärter Sprung** am Übernahmepunkt, **keine Unterschreitung von Mindestwerten** zu irgendeinem Zeitpunkt und **Konsistenz im Aggregat** (inkl. ZZR) — nicht bitgenaue Konstanz jedes Einzelwerts über die Laufzeit.

### 3.3 Residuum $R$: Definition und erwartete Struktur

Sind die Anker 1–3 hart, ist das Residuum vollständig determiniert:

$$R(t_a) \;=\; V^{\mathrm{ist}}(t_a) \;-\; V^{\mathrm{prosp}}(t_a;\, S, B)$$

Es existiert **kein Freiheitsgrad in der Höhe** von $R$, nur in seiner Fortschreibung (Kap. 4).

Erwartete Struktur über den Bestand: **bimodal**. Verträge ohne Geschäftsvorfallhistorie liegen bei $R \approx 0$ (prospektive Konsistenz per Konstruktion); Verträge mit GV-Historie bilden einen zweiten Cluster, getrieben v. a. durch Zillmer-Amortisationslogik des Quellsystems, Dynamik-Schichtung, Beitragsabgrenzung und Kostenentnahmen in beitragsfreien Zeiten. $R$ ist damit zugleich **Migrationsqualitätskennzahl**: Die Verteilung, geclustert nach GV-Historientyp, ist zentraler Prüfgegenstand (Kap. 6).

Die Korrekturschicht ist deshalb **Regelbestandteil jedes migrierten Vertrags** (ggf. mit $\rho = 0$), kein Ausnahmepfad für Sonderfälle.

### 3.4 Abgrenzung: Residuum vs. Fehlerkorrektur

Zwei strikt getrennte Mechanismen:

- **Korrekturschicht** absorbiert die unerklärte Bewertungsdifferenz. Anker bleiben unangetastet; Kundensicht unverändert.
- **Fehlerkorrektur** verändert einen Anker (falscher Beitrag, falsche Summe im Quellsystem). Das ist ein Kundenrechts- und Kommunikationsthema mit eigenem Prozess und läuft **niemals** über die Korrekturschicht.

Beide müssen ex post unterscheidbar bleiben; eine Vermischung macht später nicht mehr feststellbar, ob eine Differenz Modellrest oder Anspruch war.

---

## 4 Korrekturschicht

### 4.1 Architekturprinzip: Overlay auf dem Zustandsraum

Die Korrekturschicht ist ein zusätzliches Paar von Zahlungsfunktionen $c_i(t,u)$, $c_{ij}(t,u)$ auf dem **vorhandenen** Zustandsraum, ausgewertet entlang desselben realisierten Pfads $(Z_t, U_t)$ wie Basis- und Bonusschicht. Die Ströme sind **fiktiv** — reine Bewertungsgrößen ohne reale Zahlung; ihr Zweck ist, dem Korrekturwert $V^{\mathrm{korr}}$ eine wohldefinierte Thiele-Dynamik zu geben. Der „Abbau von $R$" *ist* dieser fiktive Strom.

Verbindliche Anti-Pattern:

- **Kein Zustand „migriert"** im Zustandsraum: würde die Verweildauer-Uhr zurücksetzen und die Biometrie verfälschen. Die Migration ist ein Ereignis mit statischem Attribut $t_a$ bzw. $t_0$, kein Zustand.
- **Keine dritte Uhr.** $c_i$ darf von $t$, $u$ und statischen Vertragsattributen abhängen; „Zeit seit Migration" ist $t - t_a$ und damit kein zusätzlicher Zustandsraum. Empfehlung: auf $u$-Abhängigkeit verzichten.
- **Kein skalarer Restposten** in der Datenhaltung mit tabellarischer Tilgung: erfüllt keine Thiele-Rekursion, ist bei Zustandswechseln undefiniert.

### 4.2 Bewertungsdynamik

Semi-Markov-Thiele gilt wegen Linearität des Erwartungswerts schichtweise:

$$\big(\partial_t + \partial_u\big) V_i(t,u) \;=\; \delta(t)\,V_i - b_i - \sum_{j\neq i}\mu_{ij}(t,u)\,\big[\,b_{ij} + V_j(t,0) - V_i(t,u)\,\big]$$

Für die Korrekturschicht wird jeder Übergang $i \to j$ klassifiziert:

- **Wertkontinuierlich:** Der Schichtwert geht 1:1 weiter — als Übertrag ($c_{ij}=0$, $V^{\mathrm{korr}}_j(t,0) = V^{\mathrm{korr}}_i(t,u^-)$) oder als Auszahlung/Absorption ($c_{ij} = V^{\mathrm{korr}}_i$, danach $V^{\mathrm{korr}}_j = 0$). In beiden Fällen ist der Klammerterm null: **wertkontinuierliche Übergänge fallen aus der Thiele-Gleichung heraus.**
- **Vererbend** ($j \in F_i$): Der Wert verfällt ohne Gegenleistung.

Damit kollabiert die Bewertung auf eine eindimensionale Rückwärtsgleichung (zustandsweise, mit zustandsabhängigem $F_i$):

$$\big(\partial_t + \partial_u\big) V^{\mathrm{korr}} \;=\; \Big(\delta(t) + \sum_{j\in F_i}\mu_{ij}(t,u)\Big)\, V^{\mathrm{korr}} \;-\; c_i(t,u), \qquad V^{\mathrm{korr}}(T)=0$$

Diskret ist das dieselbe Rekursionsform wie im übrigen Kernel ($e^{-\delta} \to v$, $\mu \to q$); Diskretisierung und Rundung regelt die Grundsatzdokumentation.

### 4.3 Übergangstaxonomie

| Ereignis / Übergang | Klasse | Behandlung der Korrekturschicht |
|---|---|---|
| Rechnender GV (Beitragsfreistellung, Herabsetzung, Dynamik, Zuzahlung, Teilrückkauf, Verlängerung) | A | **Absorption:** Gesamt-DK *inklusive* $V^{\mathrm{korr}}$ wird angerechnet; danach $\rho := 0$. Der Vertrag ist ab dem ersten rechnenden GV rein prospektiv („geheilt"). |
| Rückkauf | B | Wertkontinuierlich: Schicht zahlt sich im Rückkaufswert aus. Konvention: Stornoabzug trägt die Basisschicht. |
| Tod mit fester Versicherungssumme | B | **Vererbend** ($\in F_i$): Leistung ist Anker und bleibt unangetastet; der Schichtwert verfällt. Die Sterblichkeit finanziert die Amortisation anteilig mit. |
| Tod/Ablauf mit DK-bezogener Leistung | B | Wertkontinuierlich: Schicht fließt in die Leistung ein. |
| Vertragsablauf | B | Terminalbedingung $V^{\mathrm{korr}}(T)=0$; nicht verhandelbar (sonst Ablaufleistung ≠ DK). |
| Fortführender Übergang ohne Neuberechnung (z. B. Beitragsbefreiung aus BUZ, Ende Stundung) | C | Stetiger Übertrag und **Neuverankerung** im Zielzustand: $\mathcal{A}\big(t, j, V^{\mathrm{korr}}(t^-)\big)$. |

Die vollständige Klassifikation aller Übergänge des jeweiligen Zustandsgraphen ist **je Tarifplan** in der Ausgestaltung festzulegen (Kap. 8.2); die Tabelle oben ist der Default.

### 4.4 Verankerungsoperator

$$\mathcal{A}(t, i, u, R):\qquad \rho \;:=\; \frac{R}{\Pi_i(t,u)}, \qquad c_i \;=\; \rho\, g$$

$\Pi_i(t,u)$ ist der Barwert des Einheitsstroms $g$ unter der Korrekturschicht-Dynamik — die Verweildauer wirkt über die Intensitäten $\mu_{ij}(t,u)$ — numerisch identisch mit der Lösung der Rückwärtsgleichung aus 4.2 für $c = g$. Es ist **keine geschlossene Form erforderlich**; der Kernel bewertet $\Pi$ mit derselben Rekursion wie $V^{\mathrm{korr}}$ selbst.

Ein Operator, drei Aufrufkontexte:

| Kontext | Aufruf |
|---|---|
| Migration (Erstverankerung) | $\mathcal{A}\big(t_a,\, i_0,\, u_0,\, V^{\mathrm{ist}}(t_a) - V^{\mathrm{prosp}}(t_a)\big)$ |
| Klasse-C-Übergang | $\mathcal{A}\big(t,\, j,\, 0,\, V^{\mathrm{korr}}(t^-)\big)$ — Verweildauer-Reset bei Zustandseintritt |
| Klasse-A-GV | Anwendung mit $R = 0$ nach Absorption |

**Optionsunabhängigkeit:** Da alle VN-Optionsübergänge (Storno, Beitragsfreistellung, …) wertkontinuierlich sind, treten ihre Intensitäten in $\Pi$ nicht auf. $\rho$ hängt nur vom Rechnungszins und den vererbenden biometrischen Ausscheideursachen ab — Stornoannahmen spielen in der Migrationsbewertung keine Rolle.

### 4.5 Formfunktion

Anforderungen an $g$: in **allen Erlebenszuständen definiert** (Verträge können beitragsfrei oder im Rentenbezug migrieren; eine rein beitragsproportionale Form ist unvollständig) und über die Restlaufzeit integrierbar mit $\Pi > 0$.

Zulässige Kandidaten (Wahl je Tarifplan, Kap. 8.2):

1. $g \propto V^{\mathrm{base}}(t)$ — glatt, überall definiert; **Default**.
2. $g \equiv 1$ auf einem Amortisationsfenster $[t_a,\, t_a + n]$ — am leichtesten zu erklären; $n$ Produktparameter; ungeeignet bei kurzer Restlaufzeit.
3. Beitragsproportional — nur zulässig in Kombination mit einer Fortsetzungsregel für beitragsfreie Zustände.

Optional kann die Form gegen Stützstellen-DK-Verläufe des Quellsystems per Kleinste-Quadrate kalibriert werden (Approximation der Altsystemlogik statt bloßer Stichtagsrettung); ob das eingesetzt wird, ist je Bestand zu entscheiden und in der Ausgestaltung zu dokumentieren.

### 4.6 Vorzeichen und Guardrails

- **$R < 0$** (Ist unter prospektiv; typisch: nicht getilgter Abschlusskostenanteil): Pfadweise Floor-Prüfung zur Kalibrierungszeit — $V^{\mathrm{base}}(t) + V^{\mathrm{korr}}(t) \ge$ Mindestwerte (§ 169 VVG, DeckRV) **für alle $t$**, nicht nur am Verankerungspunkt. Bei Verletzung: Kappung von $R$; der gekappte Teil geht in den Fehler-/Klärungsprozess (3.4), nicht in die Schicht.
- **$R > 0$**: aufsichtsrechtlich unkritisch; beim Abbau wird Ergebnis frei, das in Rohüberschuss und Überschussbeteiligung (§ 153 VVG / RfB) läuft. Ob und wie es dem Bestand zusteht, ist Unternehmensentscheidung — der Kernel muss den Effekt **sichtbar ausweisen** können.
- **Degeneration $\Pi \to 0$** (kurze Restlaufzeit): Schwellwert definieren, unterhalb dessen $R$ sofort über das Ergebnis ausgebucht statt verrentet wird; sonst explodiert $\rho$. Konkreter Schwellwert: Implementierungsentscheidung (Kap. 9).
- **Flags:** Die Schicht ist Deckungskapital, trägt den Rechnungszins ihrer Bestandsgruppe und ist im Default in Überschussbemessung und ZZR-Ermittlung **enthalten** — beides als Konfiguration je Bestandsgruppe, nicht als Hardcode.

### 4.7 Persistenz und Reporting

Persistiert werden **Parameter, keine Zwischenwerte**: $(\text{Schichttyp},\ i_0,\ u_0,\ t_a,\ g\text{-ID inkl. Parametern},\ \rho,\ F\text{-Klassifikation},\ \text{Flags},\ \text{Kohortenkennzeichen})$. $V^{\mathrm{korr}}$ ist daraus jederzeit reproduzierbar. Die Schicht wird je Vertrag und aggregiert als **eigene Reporting-Position** ausgewiesen — nie unsichtbar im DK.

---

## 5 Verankerungszeitpunkt

### 5.1 Regel

**Verankert wird am letzten exakten Rechenpunkt des Quellsystems:**

$$t_a \;=\; \max\big(\text{letzter Vertragsstichtag},\ \text{letzter rechnender GV}\big)$$

Begründung: An Rechenpunkten vergleicht die Methode geschäftsplanmäßige Rechenwerte; am unterjährigen Migrationsstichtag verglichen würde $R$ zusätzlich Interpolationskonventionen und Beitragsabgrenzung messen und damit als Diagnoseinstrument entwertet. Am Rechenpunkt ist zudem der zu rekonstruierende Intra-Jahres-Zustand (Zillmerjahr, Dynamikofferten, verdiente Beitragsanteile) minimal, und der $t_a$-Wert entspricht der letzten Standmitteilung nach § 155 VAG — Kundenkonsistenz ist wörtlich erfüllt.

### 5.2 Nachfahren bis zum Migrationsstichtag

Der Zeitraum $[t_a, t_0]$ wird im Zielsystem nachgefahren (Fälligkeiten, ggf. Geschäftsvorfälle, Fortschreibung). Der Vergleich des nachgefahrenen Werts gegen den gelieferten $t_0$-Altwert ist ein **eingebauter Test** der Fortschreibungs- und GV-Logik am Echtbestand vor Go-Live. Abweichungen müssen je Zahlweise-/Tarifcluster **systematisch** sein (Konventionsdifferenz); unsystematische Abweichungen sind Befunde.

### 5.3 Zwei getrennte Residuen

- $R_{\mathrm{hist}}$: Verankerung bei $t_a$; enthält ausschließlich Pfad-/Historienresiduen. Primäre Qualitätskennzahl.
- $R_{\mathrm{conv}}$ (optional): Wird bitgenaue Gleichheit am $t_0$ gefordert (z. B. Bilanzstichtag), wird die Konventionsdifferenz **primär eliminiert**, indem der Zielkern die unterjährigen Rechen-/Interpolationskonventionen des Altbestands als Teil der mitwandernden Rechnungsgrundlagen implementiert. Ein danach verbleibender Rest wird per Zweitverankerung $\mathcal{A}(t_0, i, \delta_{\mathrm{conv}})$ in eine **eigene Schicht** gebucht — getrennt persistiert, getrennt reportet, mit eigener Toleranz.

Zwei benannte Residuen mit unterschiedlichen Ursachen, Verteilungen und Toleranzen sind gegenüber dem Verantwortlichen Aktuar die stärkste Position; im Kernel kostet die Zweitschicht nichts, weil der Mechanismus identisch ist.

### 5.4 Datenanforderungen und Fallback

Der Datenliefervertrag umfasst drei Lieferobjekte je Vertrag:

1. **Zustandssnapshot am $t_a$:** exakte Werte (DK gezillmert/ungezillmert, Rückkaufswert, beitragsfreie Werte, Zahlbeitrag, garantierte Leistungen, Bestandsgruppe/Rechnungsgrundlagen, Überschussguthaben separat) **einschließlich der historienabgeleiteten Zustandsattribute**: Verankerungszustand $i_0$ und Verweildauer $u_0$ (z. B. Beginn eines Leistungsbezugs), Options- und Rechtszustände (verbrauchte Nachversicherungsgarantien, ausgeübte Wahlrechte, Wartezeiten, Dynamikzähler), Restzillmerstand, Beitragsrückstände/Stundungen sowie Steueraggregate (kumulierte eingezahlte Beiträge).
2. **GV-Metadatenliste seit Vertragsbeginn:** Geschäftsvorfalltyp und Datum, ohne Werte. Grundlage für $t_a$-Ermittlung (5.1), Historien-Clusterung und Ausreißerdiagnose (Kap. 6).
3. **Voll-Bewegungsdaten nur für $[t_a, t_0]$** zum Nachfahren (5.2) — maximal ein Versicherungsjahr.

Kann die Quelle für einzelne Verträge nur den $t_0$-Snapshot liefern: Fallback auf $t_0$-Verankerung als **gekennzeichnete Kohorte** mit eigener Toleranz — niemals stillschweigend gemischt.

Die Lieferschnittstelle ist früh im Projekt zu fixieren; sie ist Voraussetzung der Methode. Konkretes Quellsystem-Mapping und Ableitungslogik sind Gegenstand des Migrationskonzepts (1.3).

### 5.5 Rolle der Vertragshistorie

Die Methode verzichtet ausschließlich auf das **Replay**: Der Zielkern rechnet den Vertrag nie ab Beginn nach und benötigt keine Bewegungsdaten vor $t_a$ als Recheninput. Die Historie entfällt damit nicht — sie wechselt die Rolle:

| Rolle | Inhalt | Adressat |
|---|---|---|
| **Zustandsextrakt** | Historien*ergebnisse* als Bestandsattribute (Lieferobjekt 1) | Rechenkern |
| **Migrationsanalytik** | GV-Metadatenliste (Lieferobjekt 2) für $t_a$-Ermittlung, Historien-Clusterung der $R_{\mathrm{hist}}$-Verteilung und Ausreißerdiagnose; Zugriff auf die Quellhistorie zur Ursachenklärung | Migrationsprojekt, Abnahme (Kap. 6) |
| **Archiv** | Vollhistorie dauerhaft auskunftsfähig: Aufbewahrungspflichten, Auskunftsersuchen, Rückabwicklung bei Widerruf — Letzteres kann ein prospektiv verankerter Vertrag konstruktionsbedingt nicht liefern | Read-only-Auskunftssystem außerhalb des Rechenkerns (1.2) |

Zwei Grundsätze sind bindend: Die **Ableitungslast liegt quellseitig bzw. im Migrationssystem** — führt das Quellsystem die abgeleiteten Attribute nicht als Bestandsfelder, berechnet sie das ETL aus der GV-Liste. Und der **Rechenkern bleibt historienfrei**: Er sieht die GV-Liste zu keinem Zeitpunkt; sein einziger Historieninput ist das Attributset aus Lieferobjekt 1.

Ohne Lieferobjekt 2 ist die Abnahme nach Kapitel 6 nicht durchführbar (keine Historien-Clusterung, keine erklärbaren Ausreißer); die GV-Metadatenliste ist deshalb Abnahmevoraussetzung, nicht Komfort.

---

## 6 Test- und Abnahmekonzept

### 6.1 Zwei Prüfebenen

| Ebene | Zeitbezug | Gegenstand | Kennzahlen (Beispiele) | Verantwortung |
|---|---|---|---|---|
| **Migrationscontrolling** | $t_0$ | Vollständigkeit, Überleitung, Bilanz | Vertrags-/Summenabstimmung, DK- und ZZR-Summen je Bestandsgruppe, $R_{\mathrm{conv}}$-Statistik, Nachfahr-Abweichungen je Cluster | Migrationsprojekt / ⟨…⟩ |
| **Aktuarieller Test** | $t_a$ | Methodische Güte | $R_{\mathrm{hist}}$-Verteilung geclustert nach GV-Historientyp, Ausreißeranalyse, Floor-Prüfungen | Aktuariat / VA |

Die Trennung ist bewusst: Das Controlling misst am Übernahmepunkt gegen die Bilanz; der aktuarielle Test misst am Rechenpunkt gegen die Methode.

### 6.2 Toleranzdefinition

Toleranzen werden auf der **Verteilung** definiert — Maximum, hohe Perzentile (z. B. 99,9 %), Betragssumme je Bestandsgruppe — niemals auf Mittelwert oder Median. Erwartet wird Bimodalität (3.3); ein unauffälliger Mittelwert bei großen Einzelmaxima ist ein Befund, keine Entwarnung. „Rundung" ist als Ursache nur für Differenzen in Cent-Größenordnung zulässig; größere Beträge erfordern eine benannte Ursache je Cluster.

### 6.3 Verlaufs- und Geschäftsvorfalltests

- **Vorwärtsrechnung** über mehrere Jahre bis Ablauf gegen Schattenrechnung des Quellsystems (soweit verfügbar) für repräsentative Cluster.
- **GV-Testmatrix** je Vertragskonstellations-Cluster: alle Klasse-A/B/C-Ereignisse mit Soll-Verhalten der Korrekturschicht gemäß 4.3.
- **Parallellauf/Schattenbetrieb** mit Delta-Reporting im Rahmen des Migrationsvorgehens (Big Bang vs. Wellen: außerhalb dieses Konzepts).

Ohne Verlaufstests gilt die Methode als nicht abgenommen; Stichtagstreue allein ist notwendig, nicht hinreichend.

---

## 7 Regulatorischer Rahmen und Verantwortlichkeiten

Für die Methode der Deckungsrückstellungsberechnung besteht kein Genehmigungsvorbehalt der BaFin; eine Abstimmung mit der Aufsicht ist möglich und ggf. sinnvoll, aber kein Safe Harbor. Verantwortlich zeichnen der **Verantwortliche Aktuar (§ 141 VAG)**, flankiert von Abschlussprüfer und interner Revision. Grundlage der Freigabe sind die Grundsatzdokumentation, die produktspezifischen Ausgestaltungen und die Residualstatistik nach Kapitel 6.

Einschlägige Randbedingungen, die die Methode einhält bzw. adressiert: § 169 VVG und DeckRV (Mindestwerte, Höchstzillmerung → 4.6), § 153 VVG (Überschussbeteiligung des $R>0$-Abbaus → 4.6), § 155 VAG (Standmitteilungskonsistenz → 5.1), § 341f HGB / ZZR (Schicht in Bestandsgruppe und ZZR-Ermittlung → 4.6), mitwandernde Rechnungsgrundlagen (→ 3.1). Nicht-aktuarielle Existenzattribute (Steuerkohorte, Förderstatus) sind Schnittstelle gemäß 1.2.

---

## 8 Zu erstellende Dokumentation

### 8.1 Grundsatzdokumentation (ein Dokument, normativ)

Charakter: Die Grundsatzdokumentation beschreibt die Mathematik und Numerik, **der die Umsetzung folgt**. Abweichungen der Implementierung sind unzulässig bzw. laufen über den Änderungsprozess der Dokumentation.

Pflichtinhalte:

1. Zustandsraum, Semi-Markov-Modell, Notation; Verhältnis der Schichten (Basis, Bonus, Korrektur, ggf. $R_{\mathrm{conv}}$).
2. Thiele-Gleichungen je Schicht; Herleitung der Übergangsklassifikation (wertkontinuierlich/vererbend) und der eindimensionalen Rückwärtsgleichung.
3. Verankerungsoperator inkl. Eigenschaften (Optionsunabhängigkeit von $\rho$), Mehrfachverankerung (Klasse C), Degenerationsbehandlung.
4. Diskretisierung, Numerik und Rundungskonventionen — verbindlich für die Implementierung.
5. Floor- und Kappungslogik (§ 169 VVG, DeckRV) inkl. Prüfzeitpunkten.
6. Behandlung der Flags (Überschussbemessung, ZZR) je Bestandsgruppe.
7. Übernommene unterjährige Rechenkonventionen des Quellsystems (falls $R_{\mathrm{conv}}$-Pfad aktiv).
8. **Abweichungsverzeichnis**: dokumentierte, entschiedene Abweichungen zwischen Konzept und Realisierung (siehe Kap. 9).
9. Versionierung und Änderungsprozess.

### 8.2 Produktspezifische Ausgestaltung (ein Dokument je Tarifplan des Zielsystems)

Template-Charakter; ohne vollständige Ausgestaltung ist ein Tarifplan nicht migrationsfähig.

| Pflichtinhalt | Bezug |
|---|---|
| Zustandsgraph des Tarifs mit **vollständiger** Übergangsklassifikation (A/B/C, $F$-Mengen je Zustand) | 4.3 |
| Ankerliste mit Härtegrad und Toleranzen | 3.2, 6.2 |
| Formfunktion $g$ inkl. Parametern (z. B. Amortisationsfenster $n$); ggf. Kalibrierungsentscheidung | 4.5 |
| Flags Überschuss/ZZR, Bestandsgruppen- und Rechnungsgrundlagenzuordnung | 4.6 |
| Produktspezifische Mindestwerte/Floors und Kappungsregel | 4.6 |
| Degenerationsschwelle und Ausbuchungsweg | 4.6, Kap. 9 |
| Behandlung von Sonderbausteinen (Dynamikschichten, Zusatzversicherungen/BUZ, Rentenübergang) | 4.3 |
| Datenlieferumfang inkl. tarifspezifischer historienabgeleiteter Zustandsattribute, $t_a$-Ermittlungsregel, Fallback-Kohorten-Kennzeichnung | 5.4–5.5 |
| Testfallkatalog je Vertragskonstellations-Cluster inkl. erwarteter $R$-Verteilung und Toleranzen | 6 |
| Freigabevermerk (Fachexperte Aktuariat, Entwicklung) | — |

---

## 9 Implementierungsfreiheiten und Konfliktregel

Dieses Konzept ist fachlich normativ; die technische Realisierung richtet sich nach der Architektur des Zielrechenkerns, dessen Details hier bewusst nicht vorweggenommen werden. Die folgenden Punkte sind **offene Entscheidungen** zwischen Entwicklung und Fachexperte/Aktuariat:

| Nr | Gegenstand | Fachliche Vorgabe (bindend) | Freiheitsgrad (offen) |
|---|---|---|---|
| 1 | Repräsentation der Schicht | Overlay-Semantik gem. 4.1; kein eigener Zustand, keine dritte Uhr | Eigenes Schichtobjekt vs. Attributsatz am Vertrag; Datenmodell |
| 2 | Numerik | Rekursionsform konsistent zur Basisschicht; Konventionen in Grundsatzdoku | Schrittweite, Löser, Rundungsimplementierung |
| 3 | GV-Integration Klasse A | Anrechnung des Gesamt-DK inkl. Schicht; danach $\rho := 0$ | Reihenfolge/Verortung in der GV-Engine, Transaktionsschnitt |
| 4 | Klasse-C-Neuverankerung | Operator $\mathcal{A}$ gem. 4.4 | Auslösemechanik im Kernel (Event-Hook vs. Neubewertung) |
| 5 | Unterjährige Altkonventionen | Als konfigurierbare Rechnungsgrundlage, nicht als Sonderlogik im Rechenpfad | Konfigurationsmodell, Granularität |
| 6 | Degenerationsfall | Schwelle muss existieren; Ausbuchung sichtbar über Ergebnis | Konkreter Schwellwert, Buchungsweg |
| 7 | Floor-Prüfung | Pfadweise zur Kalibrierungszeit gem. 4.6 | Prüfraster, Performance-Strategie |
| 8 | Persistenz | Parameter statt Werte gem. 4.7; Reproduzierbarkeit | Speichermodell, Versionierung |
| 9 | Reporting | Eigene Position je Vertrag und aggregiert; $R_{\mathrm{hist}}$/$R_{\mathrm{conv}}$ getrennt | Kontenanbindung, Berichtsformate |
| 10 | Fallback-Kohorte | Kennzeichnungspflicht gem. 5.4 | Umsetzung im Datenmodell |
| 11 | GV-Metadatenliste im Zielsystem | Lieferobjekt gem. 5.4; für die Abnahme verfügbar (5.5) | Dauerhafte Mitführung im Zielbestand als Auskunftsattribut vs. Verbleib im Migrations-Staging |

**Konfliktregel:** Weicht die Architektur des Zielrechenkerns von einer Vorgabe dieses Konzepts ab, wird die Abweichung nicht implizit aufgelöst, sondern zwischen Entwicklung und fachverantwortlichem Aktuar entschieden und im Abweichungsverzeichnis der Grundsatzdokumentation (8.1, Punkt 8) dokumentiert. Nicht verhandelbar sind die fachlichen Invarianten: Ankerhierarchie (3.2), Terminalbedingung und Übergangssemantik (4.2–4.3), Floors (4.6), Trennung Residuum/Fehlerkorrektur (3.4), die getrennte Ausweisbarkeit der Residuen (5.3) und die Historienfreiheit des Rechenkerns (5.5).

---

## Anhang A: Formelübersicht

Residuum am Verankerungszeitpunkt:

$$R(t_a) = V^{\mathrm{ist}}(t_a) - V^{\mathrm{prosp}}(t_a;\, S, B)$$

Rückwärtsgleichung der Korrekturschicht (zustandsweise, $F_i$ = vererbende Übergänge):

$$\big(\partial_t + \partial_u\big) V^{\mathrm{korr}} = \Big(\delta(t) + \sum_{j\in F_i}\mu_{ij}(t,u)\Big) V^{\mathrm{korr}} - \rho\, g(t), \qquad V^{\mathrm{korr}}(T) = 0$$

Verankerungsoperator:

$$\mathcal{A}(t, i, u, R):\quad \rho := \frac{R}{\Pi_i(t,u)}, \qquad \Pi_i(t,u) = \text{Barwert des Einheitsstroms } g \text{ unter obiger Dynamik}$$

Aufrufkontexte: Migration $\mathcal{A}(t_a, i_0, u_0, V^{\mathrm{ist}} - V^{\mathrm{prosp}})$ · Klasse C $\mathcal{A}(t, j, 0, V^{\mathrm{korr}}(t^-))$ · Klasse A: Absorption, $\rho := 0$.
