# ADR-022: Zugangsabnahme A-B2 — der Betrieb nimmt den Migrationszugang mit einer Zugangsprobe ab

**Status:** angenommen am 2026-09-30 (Maintainer), umgesetzt am 2026-10-01.

## Kontext

Die Abnahmen `A-Q1` bis `A-M4` und die Führungsprobe urteilen im Fall. Sie
belegen, dass der übernommene Bestand richtig gerechnet ist und dass
Übernahme und Fortschreibung bis zum Folgestichtag dieselbe Welt benutzen
wie die Prüfstrecke. Was danach geschieht, die Registrierung des Eingangs
in der produktiven Ablage und sein Eintritt in den Tagesbetrieb, hatte
keine Abnahme. `betrieb.uebernahme` verlangte den A-M4-Snapshot und prüfte
Struktur und Signatur, dann führte der Tageslauf den Zugang am Stichtag
ein. Ob der Zugang in der Ablage genau das bewirkt, was abgenommen wurde,
sah niemand. Die erste Gelegenheit war der folgende Monatsabschluss, und
der steht dann schon fest.

Mit dem Betriebsschlüssel (ADR-018, Nachtrag 2026-09-30) zeichnet der
Tageslauf Urheberschaft. Eine Abnahme gehört dagegen einer Rolle, die
dafür einsteht. Diese Rollen gab es schon: `mensch/betrieb` zeichnet
`A-B1`, `agent/betrieb` legt vor. Ihnen fehlte nur dieser Gegenstand.

## Entscheidung

1. **Die Zugangsprobe** (`betrieb.zugangsprobe`) fährt auf einer Kopie der
   produktiven Ablage, unter der Lauf-Sperre gezogen; das Original wird nie
   beschrieben. Mit dem produktiven Image und der produktiven Config fährt
   sie zwei Läufe vom geführten Tag über den Zugangsstichtag bis zum
   nächsten Monatsabschluss, auf Wunsch bis zum nächsten Jahrestag: einmal
   ohne den Eingang, einmal mit ihm. Beide Läufe sind deterministisch
   (ADR-020), ihre Differenz ist also eine Rechnung, keine Messung mit
   Rauschen.
2. **Die Differenz der beiden Abschlüsse ist der Beleg.** Sie muss genau
   der abgenommene Bestand sein:
   - am Zugangsstichtag: Anzahl, Versicherungssumme, Deckungskapital und
     Jahresbeitrag wie in Übernahme und Abnahme;
   - am Folgetermin, soweit er im Fenster liegt: dieselben Größen wie in
     der Migrationssuite;
   - im Bewegungskonto: Anfang + Zugang − Abgang = Ende, mit dem Zugang
     gleich der Zahl der übernommenen Verträge; keine Buchung unterscheidet
     sich zwischen beiden Läufen, außer denen der übernommenen Verträge.

   Der Beleg (`zugangsprobe.json`) bindet
   den Stand der Ablage, den Eingang, den A-M4-Snapshot, Manifest und
   Journal beider Läufe, Config, Kern-Version und Systemstand und nennt je
   Größe Soll, Ist und Differenz.
3. **Das Gate `A-B2.zugangsabnahme`** (Namensordnung nach ADR-012)
   verlangt als Pflichtbelege die Zugangsprobe, den A-M4-Snapshot und den
   Eingang. `agent/betrieb` bereitet vor und darf nur ablehnen,
   `mensch/betrieb` zeichnet; in der Vorführung mit der Schlüsselklasse
   `simulation` unter Mandat.
4. **Registriert wird nur mit angenommener `A-B2`**, wie bisher nur mit
   `A-M4`. Der Tageslauf prüft beim Eintritt des Eingangs, dass der
   A-B2-Snapshot denselben Eingang und denselben Stand der Ablage bindet,
   auf dem die Probe lief. Ein Eingang ohne `A-B2` tritt nicht ein.

**Aufwand und Nutzen.** Die Probe verdoppelt die Fortschreibung über
einen kurzen Zeitraum. Sie ersetzt nicht die Führungsprobe: Die rechnet im
Fall mit der Config des Falls, die Zugangsprobe in der Ablage mit Config,
Bestand und Kern, die produktiv laufen. Der zweite Baldrian-Lauf hat
gezeigt, dass beide auseinanderlaufen können.

## Umsetzung

`models.zeichnung.GUELTIGE_GATES` führt `A-B2`, `models.belegrollen` die
Pflichtrollen `zugangsprobe`, `am4_snapshot` und `eingang` (nur im
Bestands-Scope). Der Belegvertrag der Probe liegt in `models.zugangsprobe`,
damit Probe, Gate und Registrierung ihn ohne neue Schichtkante lesen. Die
Probe ist `betrieb.zugangsprobe`, das Gate `gates.gate_entscheid`;
`betrieb.uebernahme` und der Tageslauf verlangen die Abnahme. Die Bedienung
steht in `plv/betrieb/README.md` („Der Zugang hat drei Schritte“), für eine
Welt in `werkzeuge/welt/zugang.sh`. Die Tests stehen in
`tests/test_zugangsabnahme_ab2.py`.

## Bezug

ADR-012 (Namensordnung der Gates), ADR-018 (Rollen und Schlüsselklassen,
Nachtrag Betriebsschlüssel), ADR-020 (Bestand aus dem Zugangsstrom),
ADR-021 (Belegrollen in `models`); `gates.fuehrungsprobe` als Vorbild für
einen Beleg, den ein Gate bindet und ein Konsument nachrechnet.

## Nachträge

Die Nachträge sind nach Datum und Überschrift adressiert. Die Herleitung im
Einzelnen steht in der Geschichte dieser Datei.

## Nachtrag 2026-10-01: Umsetzung und was dabei festgelegt wurde

Was der Beschluss offenließ, wurde beim Bau so festgelegt:

1. **Der Stand der Ablage ist der geführte Stand**
   (`tageslauf.ablage_stand`): die letzte grüne Protokollzeile (über die
   Kette alles davor), das Manifest des Stands und die Config. Ein roter
   Lauf bewegt ihn nicht. Registrierte, noch nicht aufgenommene Eingänge
   gehören nicht dazu: Jeder bringt seine eigene Abnahme mit, und die
   Bindung an den Eingang (sein Nummernband) fängt, wenn ein anderer
   dazwischen registriert wurde.
2. **Aufnahme und Eintritt sind zwei Fragen.** Die Bindung an den Stand
   gilt der ersten Aufnahme durch einen grünen Lauf, geführt oder, bei
   einem Stichtag nach dem Lauftag, wartend. Wartende Eingänge tragen dafür
   ihren Hash in der Protokollzeile
   (`wartende_uebernahmen[].eingang_sha256`); sonst liefe ein
   vorausdatierter Zugang an seinem Stichtag gegen einen längst vergangenen
   Stand und träte nie ein. Beim tatsächlichen Eintritt hält der Tageslauf,
   was sich im Betrieb nicht ändert, gegen die Abnahme: Config-Hash,
   Kern-Version und Code-Stand (Image-Digest und Revision, soweit die Probe
   sie erfasst hat, und `quellcode_sha256`). Eine Abweichung wird mit
   Ausweg verweigert: Probe und `A-B2` neu.
3. **Die Bindung liegt in der Ablage,** als `zugangsabnahme.json` neben
   `eingang.json`, gezeichnet mit dem Betriebsschlüssel; der Tageslauf
   kennt den Fall nicht und hält keinen Freigabeschlüssel. Sie steht nicht
   in `dateien` von `eingang.json`, denn die Abnahme bindet den Hash von
   `eingang.json`.
4. **Derselbe Eingang heißt dieselben Bytes.** Die Probe registriert in
   ihrer Kopie über dieselbe Funktion und Serialisierung wie die echte
   Registrierung, und die Betriebszeichnung ist deterministisch. Die
   Registrierung braucht deshalb dieselben Angaben wie die Probe (`--fall`,
   `--quelle`, Stichtag, Betriebsschlüssel); die Meldung nennt abweichende
   Felder.
5. **Das Soll sind die Systemwerte der geltenden Abnahmen,** gebunden an
   ihre Bytes: `aktuartest.json` muss das Testergebnis sein, das der
   A-M1-Snapshot pinnt, den der A-M4-Snapshot pinnt, und
   `migrationssuite.json` die Suite, die der A-M4-Snapshot pinnt; beide
   Snapshots geltend und angenommen. Probe, Belegvertrag, Gate und
   Registrierung halten das mit derselben Regel
   (`models.zugangsprobe.soll_bindung_fehler`). Verglichen werden Anzahl,
   Versicherungssumme und Jahresbeitrag je Summe und je Vertrag über den
   ganzen Zugang, am Folgetermin die Anzahl in Kraft, dazu Zugänge,
   Zugangsbuchungen, Bewegungskonto und alles außerhalb des Zugangs, mit
   einer Toleranz von einem halben Cent. Jede Bewertungsspalte des
   Abschlusses ist einer verglichenen Größe zugeordnet oder mit Grund als
   nicht belegt ausgenommen (`ABSCHLUSS_VERGLICHEN`,
   `ABSCHLUSS_NICHT_BELEGT`, gehalten gegen
   `models.bestand.ABSCHLUSS_ZAHLEN`).
6. **Grenzen und Code-Stand.** Der Zugangsstichtag ist ein Monatserster,
   denn nur dort gibt es einen Abschluss, an dem die Differenz zu halten
   ist. Der Folgetermin wird verglichen, wenn er ein Abschluss im Fenster
   ist (sonst `--bis`). Die Probe hält ihren Code-Stand gegen die letzte
   grüne Protokollzeile der Ablage: Image-Digest und Revision, soweit
   erfasst, `quellcode_sha256` und Kern-Version. Jede Abweichung ist ein
   Befund, ebenso eine Zeile ohne Code-Stand; ein Versionsstring allein ist
   keine Identität.
7. **Die Kopie ist gekennzeichnet** (`zugangsprobe-kopie.json`). Nur auf ihr
   registriert die Probe ohne Abnahme und lässt ihren Eingang ohne Abnahme
   eintreten; auf einer echten Ablage verweigern beide Wege, und auf der
   Kopie verweigert jeder echte Lauf. Das Kennzeichen entsteht vor dem
   ersten kopierten Byte. Weil es eine ungezeichnete Datei ist, trägt
   zusätzlich jede Protokollzeile eines Probelaufs gezeichnet das Feld
   `zugangsprobe`. Tageslauf, Export, Tagesseite und Konsument verweigern
   eine Kette mit einer Probezeile als Kettenbruch („Probenkopie“). Die
   Ausnahme von `A-B2` hängt damit am Zeichner des Probelaufs, nicht an
   einem Parameter.
8. **Neuaufsetzen.** Der Eingang der neuen Ablage braucht seine eigene
   `A-B2`, gerechnet auf einer leeren Ablage mit der neuen Config und
   übergeben mit `--zugangsabnahme`.
9. **Tests.** Die Suite registriert an vielen Stellen, deren Gegenstand
   nicht `A-B2` ist. Für sie legt eine Naht für die ganze Sitzung
   (`uebernahme._STANDARD_ZUGANGSABNAHME`) einen synthetischen,
   gezeichneten Probenbeleg und einen signierten A-B2-Snapshot im Fall an,
   die danach wie jeder andere geprüft werden. Produktiv ist die Naht leer.
10. **Wer `A-B2` zeichnet, prüft die Registrierung.** Sie hält den
    Fingerabdruck der Freigabe gegen die Zeichnungsordnung des Betriebs: Die
    Rolle muss `A-B2` in ihrer `gates`-Liste tragen. Das Gate `A-B2` hält
    den Betriebsschlüssel nicht; es prüft Form und Rolle der
    Betriebszeichnung der Probe und sagt in seiner Ausgabe, dass es die
    Signatur nicht verifiziert hat (`betriebssignatur`). Die Registrierung
    rechnet sie nach.

Das Deckungskapital verglich die Probe zunächst nicht, weil Monatsabschluss
und Abnahme verschiedene Größen führten. Das ist mit dem Nachtrag „die
Probe vergleicht das Deckungskapital“ entschieden und gebaut.

## Nachtrag 2026-10-01: eine Rollenregel für jede Abnahme, auf der etwas gründet

Entscheid des Maintainers: Wer einen Abnahme-Snapshot liest, um darauf
etwas zu gründen, hält die zeichnende Rolle gegen die Ordnung, und die Rolle
ist die des Schlüssels, nicht die behauptete.

Vorher hielt nur die Registrierung den Fingerabdruck der A-B2-Freigabe
gegen die Ordnung. `A-M4` und den A-M1-Snapshot, den `A-M4` pinnt, las der
Betrieb ohne die Frage, ob der signierende Schlüssel einer Rolle gehört, die
das Gate zeichnen darf. So begründete ein gültig signierter A-M4-Snapshot
eines Schlüssels, dem die Ordnung nur `A-B2` gibt, eine Übernahme. Und kein
Leser verglich das Rollenfeld eines Snapshots mit der Rolle seines
Schlüssels.

Die Lesestellen:

| Lesestelle | A-Q1 | A-M1 | A-M2/A-M3 | A-M4 | A-B2 |
|---|---|---|---|---|---|
| Registrierung (`uebernahme.eingang_anlegen`) | — | ja (Soll-Bindung, unter der Sperre) | — | ja | ja |
| Registrierung in der Probenkopie (`probe_kopie`) | — | — | — | ja | — |
| Zugangsprobe (`zugangsprobe.lies_soll`) | — | ja | — | ja | — |
| Neuaufsetzen, vor dem Anlegen (`registrierung_vorbedingungen`) | — | — | — | ja | ja (`--zugangsabnahme` oder Gate-Ledger) |
| Gate A-B2 (`gates.gate_entscheid`, Soll-Bindung der Probe) | — | ja | — | ja | — |
| Gate A-M4 (Vorbedingungen) | ja | ja | ja (Bestand) | — | — |
| Eintritt im Tageslauf | — | — | — | — | — |

**Die Regel** ist eine Funktion, `models.zeichnung.zeichnende_rolle_fehler`,
in `models`, weil Gates und Betrieb sie lesen. Sie stellt vier Fragen: Gibt
die Ordnung dem Fingerabdruck der Freigabe eine Rolle? Darf diese Rolle das
Gate zeichnen? Tragen `rolle` und `zeichnung.rolle` des Snapshots genau
diese Rolle? Ist `zeichnung.schluesselklasse` die Klasse, die die Ordnung
der Rolle gibt, und trägt eine simulierte Rolle ihr Mandat? Ein Verstoß
wird mit Meldung und Ausweg verweigert. Der Betrieb ruft die Regel über
`uebernahme.zeichnende_rolle` in seinem einen Leser `lies_abnahme_snapshot`
auf (`ordnung` ist Pflicht ohne Default), das Gate an jeder fremden
Abnahme, auf die es gründet.

Beim Zeichnen bestimmt das Gate die Rolle aus dem Schlüssel und schreibt sie
in beide Felder; jeder echte Produzent erfüllt die Gleichheit also. Der
Leser hält sie gegen seine Ordnung, und das ist nicht immer dieselbe: Das
Gate hält gegen die Ordnung, unter der es gerade zeichnet, der Betrieb
gegen die Ordnung, die dem Betriebsschlüssel seine Rolle gibt. Eine Abnahme
muss also unter jeder Ordnung, die auf ihr gründet, von einer berechtigten
Rolle mit demselben Namen stammen. Nennen zwei Ordnungen dieselbe Rolle
verschieden, verweigert der Leser. Für den Betrieb heißt das: Seine Ordnung
nennt neben `betrieb/tageslauf` und `mensch/betrieb` auch die Rollen, deren
Schlüssel A-M1 und A-M4 signiert haben, unter demselben Namen wie die
Ordnung des Falls.

**Maßgeblich für den Eintritt ist die Ordnung zum Zeitpunkt der
Registrierung.** Die Registrierung hält die Rolle jeder Abnahme gegen die
Ordnung, schreibt das Ergebnis in `eingang.json` und `zugangsabnahme.json`
und zeichnet beides mit dem Betriebsschlüssel. Ein späterer Entzug der
Berechtigung wirkt nicht zurück, und der Eintritt liest keinen Snapshot.
*Verworfen:* die Neuprüfung beim Eintritt gegen die dann geltende Ordnung;
derselbe Eingang träte sonst je nach Tag ein oder nicht.

Der Präfix des Fingerabdrucks in `eingang.json` (16 Zeichen) ist Anzeige,
kein Prüfanker. Gebunden ist der volle Fingerabdruck über den vollen
Snapshot-Hash im gezeichneten Eingang.

**Neuaufsetzen.** Die Vorbedingungen der Registrierung, die keinen Ort
brauchen (`uebernahme.registrierung_vorbedingungen`), prüft
`betrieb.neuaufsetzen` vor dem Anlegen der neuen Ablage. Was nur gegen die
neue Ablage prüfbar ist, scheitert danach; dann entfernt die Routine ihre
eigene, nie veröffentlichte Vorbereitung, statt einen Rest liegen zu
lassen.

**Grenze.** Die Freigabe ist ein HMAC. Wer registriert und den Ring hält,
kann jedes Rollenfeld und jede Klasse gültig neu signieren. Die Regel
schützt gegen abweichende Ordnungen und fremde Snapshots, nicht gegen den
Inhaber des Rings.

Die Tests (`tests/test_abnahme_rolle_klasse.py`,
`tests/test_neuaufsetzen_vorbedingungen_klasse.py`) greifen je Gate und
Lesestelle an (Ordnung ohne das Gate, neu signiertes Rollenfeld oder neu
signierte Klasse, abweichend benannte Rolle, Schlüssel ohne Rolle), jeweils
jeweils mit einem Gegenbeispiel, das die Prüfung auslösen muss, und halten jedes lesende Öffnen unter `entscheide/`
gegen die erlaubten Leser.

## Nachtrag 2026-10-01: die Probe vergleicht das Deckungskapital

Bis dahin führte der Monatsabschluss das Deckungskapital zum letzten
Vertragsjahrestag, A-M1 und die Migrationssuite rechneten am Stichtag die
Monatsreserve. Der Maintainer entschied, beide Seiten auf dieselbe Größe zu
bringen:

* Der Abschluss bewertet monatsgenau (ADR-011, Nachtrag 2026-10-01) und
  nennt seine Konvention.
* Die Migrationssuite (Beleg von `A-M4`, Fassung 2) trägt je Vertrag des
  Zugangs den Führungswert: Deckungsrückstellung, Rückkaufswert und
  Korrekturschicht, die der Abschluss am Zugangs- und am Folgestichtag für
  den Vertrag führen wird, gerechnet über die Bewertungsstrecke des
  Abschlusses (`bestand.migrationszugang.fuehrungswerte`). Er ist ein
  Systemwert, kein Vergleich mit der Lieferung. `A-M4` nimmt im
  Bestands-Scope keine Suite ohne ihn ab.
* Die Probe (Beleg Fassung 2) hält Deckungskapital, Rückkaufswert und
  Korrekturschicht je Vertrag über den ganzen Zugang gegen den Führungswert
  der gepinnten Suite, am Zugangs- und am Folgestichtag; dort ohne die
  Verträge mit einem gebuchten Vorfall im Fenster, die als ausgenommen
  benannt werden. Stehen Abschluss und Führungswert in verschiedenen
  Konventionen, verweigert sie den Vergleich.

Damit sieht die Probe auch eine Führung, die einen anderen Vertrag führt
als den abgenommenen, ohne dass sich Summe oder Beitrag bewegen, etwa eine
unbekannte Korrekturschicht oder einen verschobenen Vertragsbeginn. Das
Soll kommt aus der gepinnten Abnahme, nicht aus der Ablage.

**Verworfen:** Die Probe rechnet den Abnahmewert selbst in die Konvention
des Abschlusses um. Das hätte ein zweites Rechenwissen neben der
Bewertungsstrecke aufgebaut, genau die Drift, die ADR-011 beseitigt.

## Nachtrag 2026-10-01: Anfangsbestand und Versionslinie der Ordnung (ADR-025)

**Der Anfangsbestand ist abgenommen, bevor ein Zugang abgenommen wird.**
Seit ADR-025 läuft auf einer Ablage nach ihrem Aufbaulauf kein Tag ohne die
gezeichnete Abnahme ihres Anfangsbestands (`A-B3`, Bindung
`anfangsbestand.json`). Die Probe fährt den Tageslauf auf einer Kopie und
verlangt deshalb dieselbe Bindung. Auf der leeren Ablage eines
Neuaufsetzens gibt es noch keinen Anfangsbestand; der Zugang wird dort Teil
des Anfangsbestands und mit ihm abgenommen.

**Die Ordnung zum Zeitpunkt der Registrierung wird prüfbar.** Mit der
Versionslinie der Zeichnungsordnung ist der Stand, unter dem eine Abnahme
gezeichnet wurde, auffindbar: Jede Zeichnung pinnt ihr Glied, und der Leser
hält Rolle, Klasse und Gate gegen diesen Stand. Ein späterer Entzug wirkt
nicht zurück, eine spätere Erweiterung entwertet nichts. Der Leser des
Betriebs (`uebernahme.lies_abnahme_snapshot`) nimmt die Linie als
Parameter; Registrierung, Zugangsprobe, Neuaufsetzen und die Bindung des
Anfangsbestands bekommen sie mit `--linie`.

## Nachtrag 2026-10-01: A-M4 rechnet den Führungswert nach und weist ihn aus (Prüfrunde G)

`A-M4` prüfte den Führungswert nur der Form nach: Felder, endliche Zahlen,
bekannte Konvention, Bindungshashes. Ein verdoppeltes Deckungskapital, eine
falsche Konvention und ein Vertrag, der am Folgestichtag nicht mehr in
Kraft sein sollte, gingen durch (G03). Die Zugangsprobe hätte die
Abweichung später gesehen, aber gepinnt und gezeichnet war ein falsches
Soll.

**Regel.** `A-M4` pinnt nur einen Führungswert, den es selbst
nachgerechnet hat, über denselben Weg wie die Suite
(`gates.migrationssuite_lauf.fuehrungswert_rechnen` ->
`bestand.migrationszugang.fuehrungswerte`), auf den gebundenen Bytes
(Bestand, Nebentabellen, Config), mit den Stichtagen der Suite und dem
Tarifwerk der Spez. Die Vorlage weist ihn aus, in der Zusammenfassung
(`fuehrungswert`) und im HTML je Vertrag und Termin. Bericht und Entscheid
rufen dieselbe Prüfung (`abnahmebericht._bestands_suite_fehler`);
`abnahmebericht` steht seitdem auf 10.0.0. Die Zugangsprobe bleibt Leserin
des Solls, nicht Prüferin.

**Verworfen:** den Führungswert nur auszuweisen, denn dann zeigte die
Vorlage einen Wert, den niemand nachgerechnet hat. Ebenso, die ganze Suite
in `A-M4` neu zu fahren: Für den Führungswert genügen die gebundenen
Eingaben. Die übrigen Befunde der Runde stehen in ADR-024, vierter
Nachtrag.
