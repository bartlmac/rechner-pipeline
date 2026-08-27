# Aktuarieller Test: AT-1, AT-2, AT-3

**Stand:** Vorschlag zur Durchsprache, 27.08.2026.
**Auftrag:** Rückmeldung zum Abnahmebericht, Punkt N4 — der aktuarielle
Test ist mit einem Stichtag nicht vollständig; er braucht drei Tests mit
je eigener Stichprobe, eigenen Abnahmekriterien und eigenem Bericht.
**Status:** nichts hiervon ist gebaut. AT-1 ist der heutige Test um einen
zweiten Zeitpunkt erweitert; AT-2 und AT-3 sind neu.

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

Die Prüfwerte je Geschäftsvorfall stehen bereits im Bewegungsjournal der
Bestandsführung, als Betragsart je Ereignis:

| Vorfall | Prüfwert | Zeitpunkt |
|---|---|---|
| STO Storno | Rückkaufswert | Wirksamkeit des Storno |
| PEX Beitragsfreistellung | beitragsfreie Versicherungssumme | Wirksamkeit der Freistellung |
| ABL Ablauf | Ablaufleistung (KLV), Jahresrente (BU) | Ablauftermin |
| TOD Tod | Todesfallleistung, Jahresrente (BU) | Todestag |
| INV Invalidität | BU-Jahresrente | Eintritt |
| REA Reaktivierung | BU-Jahresrente | Reaktivierung |
| ERH Erhöhung | erhöhte Versicherungssumme | Erhöhungstermin |

Damit ist AT-3 nicht zu erfinden, sondern abzuleiten: Der Testauftrag
liest die Vorfälle, die die Stichprobe benennt, und vergleicht je Vorfall
den Wert, den das System bildet, gegen den gelieferten.

@Claude Keine valide Prüfwerte: ABL/Jarhesrente (BU); TOD Jahresrente (BU); 
Reaktivierung BU-Jahresrente; zudem wird einmal Jahresrente (BU) und wieder 
sonst BU-Jahresrente geschrieben.  Stattdessen sollte für jeden Vorfall die
Veränderung des Deckungskapital als Prüfwerte reingeommen werden.

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

@Claude: Achtung - die Tests sind selbst separate Gates. Das ist wichtig
denn in der Praxis wird anhand der Abnahme dieses indiviudellen Tests
an anderen Stellen weiter gearbeitet (oder nicht). GeVos sind oft erst
in der späteren Phase der Migration notwendig. Wichtig also, dass wir das
als Gates trennen.

@Claude: Die Stichprobenprofile waren anders gemeint. Jeder Test hat
unterschiedliche mögliche Stichproben (von "voll" - Gesambestand oder
alle GeVos die simuliert sind; bis "sehr klein" - z. B. 1 Fall pro GeVo).
Du kannst einen Vorschlag der Ausgestaltung geben und Prozess diese für
Baldrian mit dem Windows-Werkzeug zu generieren - wenn wir den neuen
Fall vorbereiten, finalisieren wir uns nutzen wir das.

## 5 Die drei Berichte

Drei Tests, drei Abnahmen, drei Berichte. Ein zusammengefasster Bericht
wäre bequem und fachlich falsch: Der Verantwortliche Aktuar nimmt AT-1
möglicherweise ab und AT-3 nicht, und diese Entscheidung muss getrennt
dokumentiert und getrennt gezeichnet sein.

Die Berichtserzeugung selbst bleibt, wie sie ist — der Renderer bekommt
das Testergebnis und das Profil und schreibt daraus. Was hinzukommt:
Jeder Bericht weist **sein** Profil aus, mit Stichprobenziehung, Kriterien
und Abdeckung (wie viele Verträge tragen welchen Prüfpunkt).

@Claude: Die Berichte werden sehr wahrscheinlich recht unterschiedlich
sein. Bei GeVos geht es mehr um plausibilität als um eine lange Tabelle
mit "Beinahenulls", mehr Text-Prosa Beurteilung und Begründung.
Bei Verlaufsteste werden wir ggf. auch Diagrame nutzen, noch unklar.
Ehrlicherweise brauchen wir unterschiedliche Vorlagen. Gerne Vorschlag
für die inhaltliche Ausgestaltung geben!

## 6 Was das für das Gate bedeutet

Gate G-A prüft heute ein Testergebnis. Künftig prüft es drei — und die
aktuarielle Abnahme ist erst vollständig, wenn alle drei eine geltende,
gezeichnete Spitze haben. Erst dann darf G-2 (Migrationscontrolling)
laufen.

Das ist dieselbe Reihenfolge-Erzwingung, die G-A schon vor G-2 setzt, nur
eine Ebene tiefer. Die Belegrollen wachsen entsprechend: statt einer
Rolle `ga_snapshot` drei (`at1_snapshot`, `at2_snapshot`, `at3_snapshot`),
die G-2 alle drei pinnt.

## 7 Offene Entscheidungen für die Durchsprache

**E1 — Unterjährige Prüfzeitpunkte bei AT-3.** Ein Geschäftsvorfall
passiert am Wirksamkeitstag, nicht am Vertragsjahrestag. Die Invariante
aus ADR-010 lautet aber: kein unterjähriger Vergleich. Mein Vorschlag,
diese Spannung aufzulösen: Die Invariante verbietet **Interpolation** —
einen Jahreswert auf einen Zwischentermin hochzurechnen. Sie verbietet
nicht, eine Größe zu vergleichen, die das System an diesem Termin
tatsächlich bildet. Die Monatsreserve ist eine definierte Größe
(Grundsatzdokumentation Abschnitt 6 führt beide unterjährigen
Konventionen), der Rückkaufswert zum Stornotermin ebenso. AT-3 vergleicht
also gerechnete Werte, keine Interpolate. Das braucht deine Zustimmung,
weil es die Formulierung der Invariante schärft.

@Claude: ok, das ist fast selbstverständlich aber ok noch explizit.

**E2 — Was ist "die letzte technische Änderung"?** Bei AT-1 nennst du als
ersten Zeitpunkt "letzter Vertragsstichtag bzw. letzte technische
Änderung". Ist die technische Änderung ein eigener Rechenpunkt (dann
braucht der Vertrag ein Attribut dafür), oder der letzte Jahrestag davor?

@Claude: Geschäftsvorfallsdatum für GV, die nicht am Vertragsstichtag
passieren, z. B. vor der Migration wird eine Beitragsreduktion oder
Verkürzung der Dauer angestoßen (haben wir im Modell noch nicht) oder
einfach Zustandsänderung in die Invalidisierung oder Reaktivierung
(wenn wir es dann monatlich oder sogar täglich simulieren). Dann soll
dieser Wert genommen werden, denn der ist aktueller als der letzte
Vertragsstichtag. Es ist eine reine Konvention aus der Migrationspraxi
aber eine sinvolle und diese würde ich als regel ins System übernehmen.

**E3 — Stichprobenprofile.** Heute gibt es genau ein Profil
(`vollbestand`). AT-2 und AT-3 brauchen andere: AT-3 kann nicht über den
Vollbestand laufen, weil nur ein Teil der Verträge überhaupt einen
Geschäftsvorfall hat. Soll AT-3 alle Vorfälle prüfen, die es gibt, oder
eine Ziehung je Vorfallart mit Mindestabdeckung?

@Claude: Siehe meine Anmerkungen oben, das habe ich dort schon erklärt.

**E4 — Reihenfolge des Baus.** Mein Vorschlag: erst der Umbau auf
Prüfpunkte plus AT-1 (das ist der kleinste Schritt mit dem größten
Zugewinn und lässt sich sofort gegen TG2015 fahren), dann AT-3 (die
Prüfwerte liegen im Journal bereit), dann AT-2 (braucht am meisten
gelieferte Erwartungswerte und ist am ehesten von der Datenlage
abhängig).

@Claude: Ich würde das ehrlichgesagt voll durchziehen, es ist klein
genug um in einem rutsch zu bauen und zu besprechen.

## 8 Was hier NICHT steht

Die Korrekturschicht. Der Test misst heute `system - erwartet` roh; das
methodische Residuum $R$ aus Grundsatzdokumentation Abschnitt 9 ist
benannt und leer. Solange es fehlt, misst jeder der drei Tests einen
Wertvergleich, keine Methodendifferenz — bei AT-2 und AT-3 fällt das
stärker ins Gewicht als bei AT-1, weil ein nicht verankerter Verlauf über
zehn Jahre auseinanderläuft. Siehe
[korrekturschicht-umsetzung.md](korrekturschicht-umsetzung.md).
