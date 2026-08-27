# Korrekturschicht: Umsetzungsvorschlag

**Stand:** Vorschlag zur Durchsprache, 27.08.2026.
**Auftrag:** Rückmeldung zum Abnahmebericht, Punkt N7 — die Mathematik
der Korrekturschicht steht in der Grundsatzdokumentation Abschnitt 9
vollständig; sie soll analog zur Thiele-Engine im Rechenkern umgesetzt
werden.
**Status:** nichts gebaut. Der aktuarielle Test misst heute
`system - erwartet` roh; der Platz für das methodische Residuum ist
benannt und leer.

## 1 Der eine Satz, aus dem alles folgt

Die Grundsatzdokumentation sagt es in 9.6 selbst:

> Die Korrekturschicht ist kein zweiter Rechenweg, sondern dieselbe
> Rekursion mit anderen Zahlungen.

Das ist keine schöne Formulierung, sondern die Bauanleitung. Es gibt
**keine zweite Engine**. Es gibt die vorhandene Thiele-Rekursion, die
zweimal mit anderen Argumenten läuft.

## 2 Warum die Kollapsform ein Spezialfall der vorhandenen Rekursion ist

Die Bewertungsdynamik der Schicht kollabiert auf (9.6):

$$V^{\mathrm{korr}}_j(s, d) \;=\; c_s(j, d) \;+\; v \cdot
( 1 - \sum_{s' \in F_s} p_{s \to s'} ) \cdot
V^{\mathrm{korr}}_{j+1}(s,\, d^{+})$$

Kein Zustandswechsel, kein Übergangsterm — nur ein Überlebensfaktor über
die **vererbenden** Ausscheideursachen $F_s$.

Die vorhandene Rekursion in `kern/zustandsmodell.py` rechnet allgemeiner:
Sie summiert über alle Nachfolgezustände, addiert Übergangszahlungen und
trägt den Wert in den Folgezustand. Die Kollapsform entsteht daraus durch
**Weglassen der wertkontinuierlichen Übergänge** — und zwar exakt, nicht
näherungsweise:

Die Residuum-Regel des Zustandsmodells hält die nicht verbrauchte
Wahrscheinlichkeitsmasse im Zustand ($p_{s \to s} = 1 - \sum_{s' \neq s}
p_{s \to s'}$). Lässt man die wertkontinuierlichen Übergänge in der
Übergangsfunktion weg, bleibt ihre Masse im Zustand $s$ — und genau das
ist die richtige Dynamik: Ein wertkontinuierlicher Übergang trägt den
Schichtwert eins zu eins weiter, der Wert verhält sich also, als wäre der
Vertrag geblieben. Die vererbenden Übergänge dagegen führen in einen
absorbierenden Zustand mit Wert null, und ihr Anteil zehrt am Wert.

Deshalb genügt eine Ableitung der Übergangsfunktion:

```python
def vererbende_dynamik(uebergang, vererbend):
    """Übergangsfunktion, in der nur die vererbenden Ursachen wirken.

    ``vererbend`` ist die Menge der (von, nach)-Paare der Klasse
    "vererbend" (Grundsatzdokumentation 9.7). Alles andere wird
    weggelassen; seine Wahrscheinlichkeitsmasse bleibt per
    Residuum-Regel im Zustand — das ist die Kollapsform aus 9.6.
    """
    def reduziert(von: str, alter: int, dauer: int):
        p = uebergang(von, alter, dauer)
        return {nach: w for nach, w in p.items() if (von, nach) in vererbend}
    return reduziert
```

Der Rest ist ein Aufruf des vorhandenen `Zustandsmodell` mit dieser
Funktion und einer Zustandszahlung, die die Formfunktion trägt. **Kein
neuer Rekursionscode.**

Der Nebeneffekt ist der Beweis für die Optionsunabhängigkeit aus 9.8:
Storno und Beitragsfreistellung sind wertkontinuierlich, fallen also aus
der reduzierten Übergangsfunktion heraus und können $\rho$ gar nicht
beeinflussen. Was in der Grundsatzdokumentation eine Aussage ist, wird im
Code eine Eigenschaft der Konstruktion — und ist damit prüfbar.

## 3 Der Verankerungsoperator

$\mathcal{A}(t, s, d, R)$ braucht zwei Bewertungen derselben Rekursion:

```python
def verankere(modell, form, t, s, d, R, horizont):
    """Kalibrierungsfaktor rho = R / Pi (Grundsatzdokumentation 9.8)."""
    pi = modell.barwert(s, alter0=t, horizont=horizont,
                        zahlung_zustand=form.einheitsstrom, start_dauer=d)
    if pi < DEGENERATIONS_SCHWELLE:
        raise Degeneration(...)      # R wird ausgebucht, nicht verrentet
    return R / pi
```

$\Pi$ ist der Barwert des Einheitsstroms $g$ unter derselben Dynamik —
die Grundsatzdokumentation sagt ausdrücklich, dass keine geschlossene
Form nötig ist. Das ist hier wörtlich umsetzbar: derselbe
`barwert`-Aufruf, einmal mit $g$, einmal mit $\rho g$. Und weil die
Rekursion linear in der Zahlung ist, gilt sogar
$V^{\mathrm{korr}} = \rho \cdot \Pi$ am Verankerungspunkt — ein
Selbsttest, der ohne Zusatzaufwand mitläuft.

## 4 Was persistiert wird

Die Grundsatzdokumentation ist hier hart (9.11): **Parameter, keine
Zwischenwerte.** Das ergibt einen kleinen, serialisierbaren Datensatz je
Vertrag:

```python
@dataclass(frozen=True)
class Schichtparameter:
    """Alles, woraus V_korr jederzeit reproduzierbar ist (9.11)."""

    schichttyp: str              # "hist" | "conv"
    t_a: int                     # Verankerungszeitpunkt (Vertragsmonate)
    verankerungszustand: str     # s_0
    verweildauer: int            # d_0
    formfunktion: str            # Kennung
    formparameter: Mapping[str, float]
    rho: float                   # Kalibrierungsfaktor
    vererbend: Tuple[Tuple[str, str], ...]   # die F-Klassifikation
    kohorte: str                 # "t_a" | "t_0-fallback" (9.12)
    in_ueberschuss: bool         # Flags je Bestandsgruppe (9.10)
    in_zzr: bool
```

Damit bleibt der Rechenkern historienfrei (9.14): Er sieht kein Journal,
sondern bekommt diesen Parametersatz als Vertragsattribut — genauso wie
Eintrittsalter und Versicherungssumme. Wer die Parameter ableitet, ist
die Übernahmestrecke, nicht der Kern.

## 5 Die Formfunktion

Drei zulässige Kandidaten (9.9), Wahl je Tarifplan. Als Protokoll mit
einer Registry, wie bei den Produkten:

```python
class Formfunktion(Protocol):
    kennung: str
    def einheitsstrom(self, zustand: str, jahr: int) -> float: ...
```

Für die erste Ausbaustufe genügt der Default $g \propto
V^{\mathrm{base}}(t)$: glatt, in allen Erlebenszuständen definiert, kein
zusätzlicher Produktparameter. Das konstante Fenster und die
beitragsproportionale Form kommen dazu, wenn ein Tarifplan sie fordert —
nicht auf Vorrat.

Die Kleinste-Quadrate-Kalibrierung gegen Stützstellen des Quellsystems
(9.9, optional) gehört ausdrücklich **nicht** in die erste Stufe: Sie
setzt gelieferte Verlaufsstützstellen voraus, die wir für TG2015 noch
nicht haben.

## 6 Guardrails

Zwei davon sind blockierend und müssen von Anfang an stehen:

**Pfadweiser Floor bei $R < 0$.** Basis plus Korrektur muss § 169 VVG und
DeckRV **für alle Zeitpunkte** einhalten, nicht nur am
Verankerungspunkt. Das ist eine Prüfung über den ganzen Verlauf zur
Kalibrierungszeit — mit `barwert_verlauf` in einem Durchlauf zu haben,
weil die Methode ohnehin den Wert zu jedem Jahresbeginn liefert. Bei
Verletzung wird $R$ gekappt, und der gekappte Teil geht in den Fehler-
und Klärungsprozess, nie in die Schicht.

**Degeneration $\Pi \to 0$.** Unterhalb einer Schwelle wird $R$ sofort
über das Ergebnis ausgebucht. Dass es die Schwelle gibt und die
Ausbuchung sichtbar ist, ist bindend; ihr Wert ist in 9.16 als offener
Freiheitsgrad ausgewiesen und braucht eine Entscheidung, bevor der
erste echte Bestand läuft.

## 7 Ausbaustufen

**N7.1 — die Stufe, die TG2015 tragen kann.** Erstverankerung bei $t_a$,
Formfunktion Default, vererbend nur "Tod mit fester Versicherungssumme"
(der KLV-Default aus 9.7), beide Guardrails, Parameter-Persistenz. Damit
misst der aktuarielle Test statt eines rohen Wertvergleichs ein
verankertes Residuum — der Punkt, an dem die Methode zum ersten Mal
wirklich läuft.

**N7.2 — Übergangsklassifikation je Produkt.** Die Tabelle aus 9.7 ist
der Default; die vollständige Klassifikation gehört je Produkt in den
Tarifplan. Das ist die Stelle, an der KLV und BU auseinandergehen, und
sie braucht je Tarifplan eine Entscheidung.

**N7.3 — Klasse-A-Absorption und Klasse-C-Neuverankerung.** Der erste
rechnende Geschäftsvorfall heilt den Vertrag ($\rho \to 0$); ein
fortführender Übergang verankert im Zielzustand neu. Beides ist
derselbe Operator mit anderen Argumenten — der Code dafür steht nach
N7.1 schon.

**N7.4 — Zweitverankerung für das Konventionsresiduum.** Nur nötig, wenn
bitgenaue Gleichheit am Migrationsstichtag gefordert wird. Kostet im Kern
nichts, weil der Mechanismus identisch ist.

## 8 Wie das mit dem aktuariellen Test zusammenhängt

Heute vergleicht der Test `system - erwartet`. Mit der Schicht vergleicht
er `system + V_korr` gegen `erwartet` — und das Residuum wird von einer
Restgröße zu einer **kalibrierten Größe**: Bei $t_a$ ist es
konstruktionsbedingt null, und interessant wird, was **daneben** passiert
(der zweite Zeitpunkt von AT-1, der Verlauf von AT-2, die
Geschäftsvorfälle von AT-3).

Das ist die eigentliche Verzahnung der beiden Vorhaben: Ohne
Korrekturschicht misst AT-2 über zehn Jahre einen Fehler, der bei $t_a$
schon dastand und einfach mitläuft. Mit ihr misst AT-2, ob die
**Amortisationsform** stimmt — die Frage, auf die es ankommt.

Siehe [aktuarieller-test-at1-at2-at3.md](aktuarieller-test-at1-at2-at3.md).

## 9 Offene Entscheidungen für die Durchsprache

**K1 — Reihenfolge gegen AT.** Mein Vorschlag: N7.1 vor dem AT-Umbau. Der
Grund ist der Absatz oben — ein Verlaufstest ohne Korrekturschicht misst
zum großen Teil das Stichtagsresiduum nochmal. Das kostet aber
Vorlaufzeit, bevor AT-1 gegen TG2015 laufen kann. Die Gegenrichtung wäre:
erst AT-1 mit rohem Vergleich fahren, um die Datenlage zu sehen, dann
N7.1.

**K2 — Die Degenerationsschwelle.** In 9.16 als offen ausgewiesen. Sie
braucht eine Zahl, bevor ein echter Bestand läuft, und sie ist eine
fachliche Entscheidung, keine technische.

**K3 — Wo die Schichtparameter herkommen.** Der Kern bekommt sie als
Attribut (9.14: die Ableitungslast liegt quellseitig oder in der
Übernahmestrecke). Für TG2015 heißt das konkret: Die Transformation muss
$s_0$, $d_0$ und $t_a$ je Vertrag liefern. ADR-011 nennt die fehlenden
Verankerungsattribute schon als Lücke — das ist dieselbe Lücke, und sie
wird hier blockierend.

**K4 — Ausweis in Überschuss und ZZR.** Die Flags stehen im
Parametersatz und sind laut 9.10 Konfiguration je Bestandsgruppe. Für
Pfefferminzia braucht es dazu eine Festlegung, sonst ist der Default
eine stillschweigende Unternehmensentscheidung.
