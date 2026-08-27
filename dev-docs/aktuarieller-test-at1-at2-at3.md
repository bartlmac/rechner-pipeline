# Aktuarieller Test: AT-1, AT-2, AT-3

**Stand:** gebaut am 27.08.2026, Suite 1021 grün.
**Auftrag:** Rückmeldung zum Abnahmebericht, Punkt N4 — der aktuarielle
Test ist mit einem Stichtag nicht vollständig; er braucht drei Tests mit
je eigener Stichprobe, eigenen Abnahmekriterien und eigenem Bericht.
**Status:** Die Engine trägt Prüfpunkte, `dDK` ist als Prüfwert je
Geschäftsvorfall gebaut, die drei Abnahmen `A-M1`/`A-M2`/`A-M3` sind
eigene, einzeln zeichenbare Gates (ADR-012), und jede rendert einen
Bericht mit eigenem Schwerpunkt. Offen und unten beschrieben: die
Stichprobenprofile und ihr Erzeugungsweg für den Baldrian-Fall.

## 1 Das Problem

Der heutige Test misst jeden Vertrag an **einem** Zeitpunkt: seinem
Verankerungszeitpunkt $t_a$. Das beantwortet genau eine Frage — hat der
Vertrag den Sprung ins Zielsystem wertgetreu überstanden?

Drei Fragen bleiben offen, und jede davon kann eine Migration kippen:

1. **Rechnet das System ab morgen richtig weiter?** Ein Vertrag kann bei
   $t_a$ exakt stimmen und beim nächsten Vertragsstichtag falsch
   fortgeschrieben sein — falsche Zillmerung, falscher Zinsschritt,
   falsch übernommener Beitragsstatus.
2. **Stimmt der ganze Verlauf, nicht nur der nächste Schritt?** Ein
   Fehler in der Ausscheideordnung oder im Kostenverlauf zeigt sich
   nicht nach einem Jahr, sondern nach zehn — oder erst zum Ablauf, wenn
   die abgelaufene Leistung um einen Betrag danebenliegt, den der Kunde
   sieht.
3. **Rechnet das System die Geschäftsvorfälle richtig?** Storno,
   Beitragsfreistellung, Tod, Erhöhung: Jeder davon bildet einen Wert,
   der ausgezahlt oder gutgeschrieben wird. Ein migrierter Bestand, der
   am Stichtag stimmt und beim ersten Rückkauf falsche Werte zahlt, ist
   nicht abgenommen — er ist ein Schaden mit Vorlaufzeit.

Der aktuarielle Test ist erst vollständig, wenn alle drei beantwortet
sind. Danach — nicht davor — hat das Migrationscontrolling über den
vollen Bestand einen Sinn.

## 2 Die drei Tests

| | Frage | Zeitpunkte je Vertrag | Prüfwerte |
|---|---|---|---|
| **AT-1** Stichtagstest | Ist der Übernahmestand wertgetreu und schreibt er sich richtig fort? | zwei: letzter Vertragsstichtag bzw. letzte technische Änderung, und nächster Vertragsstichtag laut Fortschreibung | Bruttobeitrag, Deckungskapital, Leistungswerte |
| **AT-2** Verlaufstest | Stimmt der Verlauf über die Restlaufzeit? | drei: nach 5 Jahren, nach 10 Jahren, zum Ablauf | dieselben wie AT-1 |
| **AT-3** GeVo-Test | Rechnet das System jeden Geschäftsvorfall richtig? | einer je Geschäftsvorfall, Zeitpunkt vom Vorfall bestimmt | je Vorfall verschieden (siehe 2.3) |

### 2.1 AT-1 — Stichtagstest

Der erste Zeitpunkt ist der heutige Test: der letzte exakte Rechenpunkt
des Quellsystems. Der zweite ist neu und der eigentliche Zugewinn — er
prüft nicht den Übernahmeakt, sondern die **Fortschreibungsregel**.

Ein Vertrag besteht AT-1 nur, wenn er an **beiden** Zeitpunkten
besteht. Das ist keine Verschärfung um ihrer selbst willen: Ein Vertrag,
der bei $t_a$ stimmt und beim nächsten Stichtag nicht, hat einen Fehler,
den die Korrekturschicht verdeckt hätte.

### 2.2 AT-2 — Verlaufstest

Nach 5 Jahren, nach 10 Jahren, zum Ablauf. Der Ablauf ist der wichtigste
der drei: Dort ist der Wert eine Zahlung an den Kunden, und dort
kumuliert jeder systematische Fehler des Verlaufs.

Verträge mit einer Restlaufzeit unter 5 bzw. 10 Jahren haben die
entsprechenden Zeitpunkte schlicht nicht. Das ist **kein Befund** — die
Stichprobe muss dann aber ausweisen, wie viele Verträge welchen Zeitpunkt
tragen, sonst sieht ein grünes Ergebnis über 200 Verträge nach mehr aus,
als es ist.

### 2.3 AT-3 — GeVo-Test

Der tragende Prüfwert ist für **jeden** Vorfall derselbe: die
**Veränderung des Deckungskapitals**, die er auslöst (`dDK`).

Der erste Entwurf hatte je Vorfall die ausgezahlte Leistung genannt und
bei ABL, TOD und REA die BU-Jahresrente. Das ist kein gültiger Prüfwert:
Eine laufende Rente ist keine Größe zu *einem* Zeitpunkt, und bei Ablauf,
Tod und Reaktivierung wird sie nicht ausgezahlt, sondern eine bestehende
endet. Die Veränderung des Deckungskapitals dagegen ist für jeden Vorfall
definiert — und sie ist genau das, was der Vorfall im Bestand bewirkt.

| Vorfall | ΔDK | zusätzlicher Leistungswert | Zeitpunkt |
|---|---|---|---|
| STO Storno | −DK (Vertrag endet) | Rückkaufswert | Wirksamkeit |
| PEX Beitragsfreistellung | DK<sub>bfr</sub> − DK<sub>bpfl</sub> | beitragsfreie Summe | Wirksamkeit |
| ABL Ablauf | −DK | Ablaufleistung (KLV) | Ablauftermin |
| TOD Tod | −DK | Todesfallleistung | Todestag |
| ERH Erhöhung | 0 (neue Scheibe startet bei null) | erhöhte Summe | Erhöhungstermin |
| INV Invalidität | Zustandswechsel im BU-Graph | — | Eintritt |
| REA Reaktivierung | Zustandswechsel im BU-Graph | — | Reaktivierung |

Zwei Fälle sind dabei besonders aufschlussreich: Bei der
Beitragsfreistellung ist ΔDK bei verlustfreier Umwandlung **null**; ein
Abzug macht sie negativ — genau der Prüfwert, um den es geht. Bei der
Erhöhung muss ΔDK null sein, weil die neue Scheibe bei null beginnt; ein
anderer Wert ist ein Befund.

Invalidisierung und Reaktivierung wechseln den Zustand des
BU-Zustandsgraphen. Die Engine **lehnt sie ab**, statt einen KLV-Wert
auszugeben, der wie ein BU-Wert aussähe. Sie kommen dazu, wenn die
BU-Zustandsbewertung angeschlossen ist.

Damit ist AT-3 nicht zu erfinden, sondern abzuleiten: Der Testauftrag
liest die Vorfälle, die die Stichprobe benennt, und vergleicht je Vorfall
die Veränderung, die das System bildet, gegen die gelieferte.


## 3 Die gemeinsame Struktur

Alle drei Tests sind derselbe Vorgang mit anderer Bestückung: **ein
Vertrag, eine Menge von Prüfpunkten, je Prüfpunkt erwartete Werte.**
Der heutige Test ist der Sonderfall mit genau einem Prüfpunkt.

Das ist der ganze Umbau. Es braucht keine drei Engines, sondern eine, die
eine Liste von Prüfpunkten statt eines einzelnen Zeitpunkts trägt:

```python
@dataclass(frozen=True)
class Pruefpunkt:
    """Ein Vergleich: ein Zeitpunkt und die dort erwarteten Werte."""

    monate: int                    # volle Vertragsmonate seit Beginn
    erwartet: Dict[str, float]
    anlass: str                    # "uebernahme" | "fortschreibung"
                                   # | "verlauf" | GeVo-Code ("STO", ...)


@dataclass(frozen=True)
class Vertragspruefung:
    """Ein Vertrag mit allen Prüfpunkten, die ein Test an ihm hat."""

    police_id: str
    model_point: Dict[str, Any]
    historientyp: str
    punkte: Tuple[Pruefpunkt, ...]
    scheiben: Tuple[Tuple[int, float], ...] = ()
    beitragsfrei_seit_jahr: Optional[int] = None
```

`VerankerungsPruefung` wird damit ersetzt, nicht ergänzt: Zwei
nebeneinanderlaufende Auftragsformen sind eine Drift-Quelle, und die
heutigen Aufrufer sind an einer Hand abzuzählen.

Die Verteilungsauswertung bekommt eine Achse dazu. Heute clustert sie
nach Historientyp; künftig nach **Historientyp und Anlass**, denn ein
Residuum bei der Übernahme und eines beim Ablauf sind verschiedene
Befunde und dürfen nicht in denselben Topf.

## 4 Testprofil: Stichprobe und Abnahmekriterien

Deine Vorgabe: Stichproben je Test unterschiedlich, Abnahmekriterien je
Test konfigurierbar, bei AT-3 je Geschäftsvorfall. Das bündelt ein
Testprofil:

```python
@dataclass(frozen=True)
class Testprofil:
    kennung: str                        # "AT-1" | "AT-2" | "AT-3"
    titel: str
    stichprobe: Stichprobe              # eigene Ziehung je Test
    kriterien: Mapping[str, Kriterium]  # Schlüssel: Größe, bei AT-3 GeVo-Code
```

Ein Kriterium trägt beides — wann ein einzelner Wert stimmt, und wann die
Verteilung insgesamt abnahmefähig ist:

```python
@dataclass(frozen=True)
class Kriterium:
    abs_tol: float             # Einzelwert
    rel_tol: float             # Einzelwert
    max_abs_residuum: float    # Abnahmegrenze auf der Verteilung
    p95_abs_residuum: float    # Abnahmegrenze auf dem 95er-Perzentil
```

**Warum die Kriterien nicht aus dem Abzugsabgleich kommen dürfen:** Heute
zieht die Engine ihre Toleranzen aus `qa.abzugsabgleich` — eine Quelle,
nie aufgeweicht. Das war richtig, solange es einen Test gab. Bei drei
Tests mit verschiedenen Fragen ist es falsch: Eine Ablaufleistung in zehn
Jahren darf eine andere Toleranz haben als ein Deckungskapital am
Übernahmestichtag. Die Kriterien gehören deshalb in das Profil und in den
Beleg — nicht in eine Konstante, die niemand im Bericht sieht.

**Wo die Untergrenze liegt:** Die Auswertung des Demolaufs hat gezeigt,
dass sämtliche Differenzen reine Cent-Rundung sind — ohne Rundung sind
1789 von 1794 Werten exakt null, der Median der Abweichungen liegt bei
0,0024 und ist damit der Fingerabdruck der Rundung, nicht ein Fehler.
Jede Toleranz muss über diesem Rauschen liegen, sonst misst der Test die
Darstellungskonvention statt der Rechnung.

### 4.1 Stichprobenweite: eine Skala, keine feste Zuordnung

Die Weite ist keine Eigenschaft des Tests, sondern eine Entscheidung je
Migrationsfall: Ein Erstlauf gegen eine unbekannte Lieferung fährt eng,
eine Abnahme fährt weit. Deshalb trägt jedes Profil seine Weite im
Klartext, und sie steht im Bericht — ein grüner Test über zwei Verträge
sagt etwas anderes als derselbe Test über achthundert.

Vorschlag für die vier Stufen:

| Stufe | AT-1 Stichtag | AT-2 Verlauf | AT-3 Geschäftsvorfall |
|---|---|---|---|
| **voll** | ganzer Bestand | ganzer Bestand, jeder mit seinen Zeitpunkten | alle vorhandenen Vorfälle |
| **geschichtet** | Mindestzahl je Historientyp | Mindestzahl je Restlaufzeit-Klasse | Mindestzahl je Vorfallart |
| **eng** | je Historientyp einige | je Restlaufzeit-Klasse einige | je Vorfallart einige |
| **minimal** | ein Vertrag je Historientyp | ein Vertrag je Restlaufzeit-Klasse | **ein Fall je Vorfallart** |

Die Schichtungsachse ist je Test eine andere, und das ist der Punkt: Bei
AT-1 entscheidet die Historie über das Residuum, bei AT-2 die
Restlaufzeit (wer nur noch drei Jahre läuft, hat den 5-Jahres-Punkt
nicht), bei AT-3 die Vorfallart.

Für die minimale Stufe gilt eine Warnung, die der Bericht auch ausgibt:
Bei weniger als drei Fällen je Ausprägung trägt die Aussage nicht weit.
Der Geschäftsvorfall-Bericht weist deshalb je Vorfallart aus, wie viele
Fälle sie stützen — und welche Vorfallart die Stichprobe gar nicht
enthält.

### 4.2 Wie die Stichproben für den Baldrian-Fall entstehen

Der Weg über das Windows-Werkzeug, wenn wir den Fall aufsetzen:

1. **Grundgesamtheit feststellen.** Aus dem gelieferten Bestandsabzug für
   AT-1 und AT-2, aus dem gelieferten Bewegungsprotokoll für AT-3. Für
   AT-3 ist die Grundgesamtheit nicht der Bestand, sondern die Menge der
   Vorfälle — nur ein Teil der Verträge hat überhaupt einen.
2. **Schichten bilden** nach der jeweiligen Achse (Historientyp,
   Restlaufzeit-Klasse, Vorfallart) und die Besetzung je Schicht
   auszählen. Dünn besetzte Schichten fallen hier auf, bevor gezogen wird.
3. **Ziehen** mit dokumentiertem Startwert; dieselbe Grundgesamtheit und
   derselbe Startwert ergeben dieselbe Stichprobe.
4. **Auftrag an das abgebende Unternehmen** formulieren: Für genau diese
   Policen und genau diese Zeitpunkte werden Vergleichswerte erbeten —
   bei AT-2 einschließlich der Werte nach fünf und zehn Jahren sowie zum
   Ablauf, bei AT-3 je Vorfall die Veränderung des Deckungskapitals.
   Dieser Auftrag ist der eigentliche Zweck der Ziehung: Er sagt der
   Gegenseite, was sie liefern soll, und wir bekommen nicht mehr Daten
   als nötig.
5. **Zurückspielen** und den Test fahren; die Stichprobe geht als Beleg
   mit in das Ergebnis.

Schritt 4 ist der, der die Weite bestimmt: Was wir nicht erbitten, kann
später nicht geprüft werden. Deshalb sollte die Weite feststehen, bevor
der Auftrag rausgeht — nicht danach.

## 5 Die drei Berichte

Drei Tests, drei Abnahmen, drei Berichte. Ein zusammengefasster Bericht
wäre bequem und fachlich falsch: Der Verantwortliche Aktuar nimmt AT-1
möglicherweise ab und AT-3 nicht, und diese Entscheidung muss getrennt
dokumentiert und getrennt gezeichnet sein.

Gemeinsam ist allen dreien nur das Gerüst: Urteil, Testprofil mit Weite
und Kriterien, Stichprobenbeleg, Residuum nach Historientyp, Residuum
nach Anlass, Fehlschläge, Transportsicherung, Systemstand. Der
Schwerpunkt ist je Bericht ein anderer — **gebaut** ist:

**A-M1 Stichtagstest: Übernahme und Fortschreibung nebeneinander.** Der
Bericht stellt die beiden Zeitpunkte direkt gegenüber, weil genau die
Differenz zwischen ihnen die neue Aussage ist. Enthält ein Lauf nur den
Übernahmestichtag, sagt der Bericht das ausdrücklich: Er belegt dann den
Übernahmeakt, aber nicht die Fortschreibungsregel.

**A-M2 Verlaufstest: Entwicklung über die Prüfzeitpunkte.** Eine Zeile je
Zeitpunkt mit dem größten Residuum und der Zahl der Verträge, die diesen
Punkt überhaupt tragen. Wächst das Residuum von Punkt zu Punkt, liegt der
Verdacht auf der Ausscheideordnung oder dem Kostenverlauf statt auf dem
Übernahmestand — das ist die Frage, die der Verlaufstest beantwortet.

**A-M3 Geschäftsvorfalltest: Beurteilung statt Wertetabelle.** Eine Zeile
je Vorfallart mit Fallzahl, größtem Residuum und einem Urteilssatz:
„exakt getroffen", „im Rundungsrauschen der Lieferung", „Abweichung über
dem Rundungsrauschen — begründen", jeweils mit dem Zusatz „nur N Fälle —
schmale Grundlage", wo die Stichprobe dünn ist. Nicht getroffene
Vorfallarten stehen ausdrücklich als solche da, mit dem Satz, dass der
Test über sie nichts sagt.

**Offen, bewusst nicht gebaut:** Diagramme im Verlaufsbericht. Ein
Residuum-über-Zeit-Verlauf wäre dort naheliegend, aber solange die
Berichte deterministisch und ohne externe Abhängigkeiten sein müssen,
käme nur eine selbst erzeugte SVG-Kurve in Frage. Das ist machbar und
lohnt sich, sobald ein echter Lauf mit mehreren Zeitpunkten vorliegt —
an synthetischen Nullen zeigt eine Kurve nichts.

## 6 Was das für das Gate bedeutet

Gate G-A prüft heute ein Testergebnis. Künftig prüft es drei — und die
aktuarielle Abnahme ist erst vollständig, wenn alle drei eine geltende,
gezeichnete Spitze haben. Erst dann darf G-2 (Migrationscontrolling)
laufen.

Das ist dieselbe Reihenfolge-Erzwingung, die G-A schon vor G-2 setzt, nur
eine Ebene tiefer. Die Belegrollen wachsen entsprechend: statt einer
Rolle `ga_snapshot` drei (`at1_snapshot`, `at2_snapshot`, `at3_snapshot`),
die G-2 alle drei pinnt.

## 7 Entschieden und umgesetzt

**E1 — Unterjährige Prüfzeitpunkte bei AT-3: zugelassen.** Ein
Geschäftsvorfall setzt selbst den Rechenpunkt; Stichtags- und
Verlaufspunkte liegen weiterhin auf dem Vertragsjahrestag, und ein Wert
dazwischen ist dort ein harter Fehler.

**Dazu ein Befund, der die Begründung zurechtgerückt hat.** Der erste
Entwurf argumentierte, die Monatsreserve sei „eine gerechnete Größe, kein
Interpolat". Ein Test, der genau das nachweisen sollte, ist rot geworden:
Die Monatsreserve des Kerns ist ausdrücklich **linear zwischen den
Vertragsjahrestagen gemischt** (`klv.monatsreserve`, Grundsatzdokumentation
Abschnitt 6). Unterjährig wird also sehr wohl gegen einen interpolierten
Wert verglichen.

Zulässig ist es trotzdem, aber aus einem anderen Grund: Beim
Geschäftsvorfall **ist** dieser Betrag die Auszahlung. Rechnet das
Quellsystem unterjährig anders — etwa mit Zinseszins statt linear —, ist
die Differenz eine echte Konventionsdifferenz mit Zahlungswirkung, und
genau die soll der Geschäftsvorfalltest finden. Am Migrationsstichtag
dagegen bleibt der unterjährige Vergleich verboten, weil dort alle
Verträge gleichzeitig verglichen würden und die Mischungskonvention die
Methode verdecken würde. Docstrings, Fehlermeldung und ein eigener Test
halten diese Unterscheidung fest.

**E2 — Der Verankerungszeitpunkt ist das Geschäftsvorfallsdatum, wo es
eines gibt.** Fällt ein rechnender Geschäftsvorfall nicht auf den
Vertragsstichtag (Beitragsreduktion, Dauerverkürzung, Invalidisierung,
Reaktivierung), gilt sein Datum, weil es aktueller ist als der letzte
Vertragsstichtag. Das ist die Konvention der Migrationspraxis und deckt
sich mit Grundsatzdokumentation 9.12:
$t_a = \max(\text{letzter Vertragsstichtag},\ \text{letzter rechnender
Geschäftsvorfall})$. Die Engine setzt das um, indem sie unterjährige
Punkte mit Vorfall-Anlass zulässt.

Zwei der genannten Vorfälle gibt es im Modell noch nicht
(Beitragsreduktion, Dauerverkürzung) und zwei kann die Engine noch nicht
bewerten (Invalidisierung, Reaktivierung — sie brauchen die
BU-Zustandsbewertung). Für beide gilt: Sie werden hart abgelehnt, nicht
still mit einem KLV-Wert bedient.

**E3 — Stichprobenweite ist eine Skala je Test**, siehe 4.1 und 4.2. Die
Weite steht im Profil und im Bericht; die Ziehung selbst und der
Erzeugungsweg für den Baldrian-Fall sind dort beschrieben.

**E4 — In einem Zug gebaut.** Engine, Profile, drei Gates, drei Berichte,
22 neue Tests, Suite 1021 grün.

## 7a Was noch offen ist

* **Die Stichprobenprofile in `qa.stichprobe`** kennen weiterhin nur
  `vollbestand`. Die Skala aus 4.1 ist beschrieben, aber die Ziehung nach
  Historientyp, Restlaufzeit-Klasse und Vorfallart ist nicht gebaut — sie
  wird fällig, wenn der Baldrian-Fall aufgesetzt wird, und braucht dann
  den Auftrag an das Windows-Werkzeug aus 4.2.
* **Invalidisierung und Reaktivierung** im Geschäftsvorfalltest, sobald
  die BU-Zustandsbewertung angeschlossen ist.
* **Diagramme im Verlaufsbericht**, sobald ein echter Lauf mit mehreren
  Zeitpunkten vorliegt.
* **`A-M2` und `A-M3` sind keine Pflichtbelege von `A-M4`.** Das ist
  Absicht: Verlaufs- und Geschäftsvorfallwerte liefert ein abgebendes
  Unternehmen oft erst später, während die Migration auf dem belegten
  Stichtagstest schon läuft. Ob ein Fall ohne sie abgenommen wird, ist
  eine Entscheidung des Aktuariats je Fall — die Gate-Kette nimmt sie
  niemandem ab.

## 8 Was hier NICHT steht

Die Korrekturschicht. Der Test misst heute `system - erwartet` roh; das
methodische Residuum $R$ aus Grundsatzdokumentation Abschnitt 9 ist
benannt und leer. Solange es fehlt, misst jeder der drei Tests einen
Wertvergleich, keine Methodendifferenz — bei AT-2 und AT-3 fällt das
stärker ins Gewicht als bei AT-1, weil ein nicht verankerter Verlauf über
zehn Jahre auseinanderläuft. Siehe
[korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md).
