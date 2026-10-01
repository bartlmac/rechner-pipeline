# ADR-022: Zugangsabnahme A-B2 — der Betrieb nimmt den Migrationszugang mit einer Zugangsprobe ab

**Status:** umgesetzt, 2026-10-01 (angenommen 2026-09-30, Entscheid des
Maintainers im Dialog; Umsetzung siehe Nachtrag unten).

## Anlass

Die Abnahmen A-Q1 bis A-M4 und die Fuehrungsprobe urteilen im Fall:
Sie belegen, dass der uebernommene Bestand richtig gerechnet ist und dass
Uebernahme und Fortschreibung bis zum Folgestichtag dieselbe Welt
benutzen wie die Pruefstrecke. Was danach geschieht — die Registrierung
des Eingangs in der produktiven Ablage und sein Eintritt in den
Tagesbetrieb — hat bisher keine Abnahme. ``betrieb.uebernahme`` verlangt
den A-M4-Snapshot, prueft Struktur und Signatur, und der Tageslauf fuehrt
den Zugang am Stichtag ein. Ob der Zugang in der produktiven Ablage genau
das bewirkt, was abgenommen wurde, sieht niemand; der erste
Monatsabschluss danach ist die erste Gelegenheit, und dann steht er schon
fest.

Mit dem Betriebsschluessel (ADR-018, Nachtrag 2026-09-30) zeichnet der
Tageslauf Urheberschaft. Eine Abnahme ist etwas anderes: Sie gehoert einer
Rolle, die dafuer einsteht. Die Rollen dafuer gibt es bereits —
``mensch/betrieb`` (zeichnet A-B1) und ``agent/betrieb`` (legt vor,
zeichnet nie) —, sie hatten nur diesen Gegenstand noch nicht.

## Entscheidung

1. **Ein Producer ``betrieb.zugangsprobe``** faehrt auf einer Kopie der
   produktiven Ablage (unter der Lauf-Sperre gezogen; das Original wird
   nie beschrieben), mit dem produktiven Image und der produktiven
   Config, zwei Laeufe vom gefuehrten Tag ueber den Zugangsstichtag bis
   zum naechsten Monatsabschluss, auf Wunsch bis zum naechsten Jahrestag:
   einmal **ohne** den Eingang, einmal **mit** ihm. Beide Laeufe sind
   deterministisch (ADR-020: der Bestand entsteht aus dem gesaeten
   Zugangsstrom), also ist ihre Differenz eine Rechnung, keine Messung mit
   Rauschen.
2. **Die Differenz der beiden Abschluesse ist der Beleg.** Sie muss
   exakt der abgenommene Bestand sein:
   - am Zugangsstichtag: Anzahl in Kraft, Versicherungssumme,
     Deckungskapital und Jahresbeitrag gleich den Werten, die die
     Uebernahme geschrieben und A-M1 gezeichnet hat (``bestand.parquet``
     der Uebernahme, Stichtagswerte des aktuariellen Tests);
   - am Folgetermin: dieselben Groessen gleich dem, was die
     Migrationssuite fuer den Folgestichtag belegt (``dk_stichtag_2`` je
     Vertrag, aggregiert), soweit der Termin gedeckt ist;
   - Bewegungskonto: Anfang + Zugang - Abgang = Ende mit Zugang gleich
     der Anzahl der uebernommenen Vertraege, und keine Buchung, die sich
     zwischen "mit" und "ohne" unterscheidet, ausser den Buchungen der
     uebernommenen Vertraege selbst.
   Der Beleg (``zugangsprobe.json``) bindet: Hash des Ablage-Stands, den
   Eingang (``eingang.json`` mit Betriebszeichnung), den A-M4-Snapshot des
   Falls, Manifest und Journal beider Laeufe, Config und Kern-Version,
   Systemstand; je Groesse Soll, Ist, Differenz.
3. **Ein Gate ``A-B2.zugangsabnahme``** (Namensordnung ADR-012 wie
   ``A-B1.auslieferung``): ``gates.gate_entscheid --gate A-B2`` verlangt
   als Pflichtbelege den Zugangsprobe-Beleg, den A-M4-Snapshot und den
   Eingang; ``agent/betrieb`` bereitet vor und darf nur ablehnen,
   ``mensch/betrieb`` zeichnet; in der Vorfuehrung mit der
   Schluesselklasse ``simulation`` unter Mandat (Regie-Modus), wie bei den
   anderen menschlichen Rollen.
4. **``betrieb.uebernahme`` registriert nur mit angenommenem A-B2**, so
   wie es heute den A-M4 verlangt; der Tageslauf prueft beim Eintritt des
   Eingangs, dass der A-B2-Snapshot denselben Eingang und denselben
   Ablage-Stand bindet, auf dem die Probe lief. Ein Eingang ohne A-B2
   tritt nicht ein.

## Was es kostet, wenn es falsch ist

Die Probe verdoppelt die Fortschreibung ueber wenige Tage bis zu einem
Jahrestag; das sind Minuten, keine Stunden. Ein A-B2, das den falschen
Stand bindet (Probe auf einer Ablage, die danach weiterlief), ist der
Nachbarfall — deshalb bindet der Snapshot den Ablage-Stand, und der
Tageslauf haelt ihn beim Eintritt dagegen. Wer die Probe fuer nutzlos
haelt, weil die Fuehrungsprobe schon geprueft hat: Die Fuehrungsprobe
rechnet im Fall, mit der Config des Falls; die Zugangsprobe rechnet in
der Ablage, mit der Config, dem Bestand und dem Kern, die produktiv
laufen. Der zweite Baldrian-Lauf hat gezeigt, dass beide Welten
auseinanderlaufen koennen (Korrektur 24).

## Bauauftrag

1. ``models.zeichnung.GUELTIGE_GATES`` um ``A-B2``; ``models.belegrollen``
   um die Pflichtbelegrollen von A-B2 (``zugangsprobe``, ``am4_snapshot``,
   ``eingang``); Zeichnungsordnung: ``mensch/betrieb`` bekommt ``A-B2``
   in seine gates-Liste (Ordnung des Maintainers, nicht Code).
2. ``betrieb/zugangsprobe.py``: Kopie der Ablage unter Sperre, zwei
   Laeufe, Differenz, Beleg; CLI ``python -m rechner_pipeline.betrieb.zugangsprobe
   --stand <dir> --fall <fall> --stichtag <iso> [--bis <iso>] --schluessel
   <betriebsschluessel> --zeichnungsordnung <ordnung> --out <beleg>``.
   Der Beleg traegt die Betriebszeichnung (Urheberschaft), nicht die
   Abnahme.
3. ``gates.gate_entscheid``: A-B2 mit Pflichtbelegen und der Bindung an
   Eingang und Ablage-Stand; ``betrieb.uebernahme`` und der Eintritt im
   Tageslauf verlangen den Snapshot.
4. Tests nach dem Muster der drei Instrumente: Ratsche ueber die
   Belegrollen, Zaehltest ueber jede verglichene Groesse (Mutation je
   Groesse: ein Cent im Ledger der "mit"-Kopie -> Probe rot), ein
   adversarialer Angriff auf Probe und Gate vor dem Merge.
5. ``deploy/plv/README.md`` und ``docs/simulation/tagesbetrieb.md``:
   der Zugang hat drei Schritte — Probe, Abnahme A-B2, Registrierung.

## Bezug

ADR-012 (Namensordnung der Gates), ADR-018 (Rollen und
Schluesselklassen, Nachtrag Betriebsschluessel), ADR-020 (Bestand aus dem
Zugangsstrom, Determinismus), ADR-021 (Belegrollen in ``models``);
``gates.fuehrungsprobe`` als Vorbild fuer einen Beleg, den ein Gate
bindet und ein Konsument nachrechnet.

## Nachtrag 2026-10-01: Umsetzung und was dabei festgelegt wurde

Gebaut nach dem Bauauftrag: ``models.zeichnung.GUELTIGE_GATES`` fuehrt
``A-B2``, ``models.belegrollen`` die Pflichtrollen ``zugangsprobe``,
``am4_snapshot``, ``eingang`` (nur Bestands-Scope); der Beleg-Vertrag der
Probe wohnt in ``models.zugangsprobe`` (Producer, Gate und Registrierung
lesen ihn, keine neue Schichtkante); der Producer ist
``betrieb.zugangsprobe``; ``gates.gate_entscheid`` nimmt A-B2 ab;
``betrieb.uebernahme`` und der Tageslauf verlangen sie. Tests:
``tests/test_zugangsabnahme_ab2.py`` (Ratsche, Zaehltest je Groesse,
Positivkontrolle, Registrierung und Eintritt, Gate). Was der Bauauftrag
offenliess und hier festgelegt wurde — jeweils mit Grund:

1. **Der Stand der Ablage ist der GEFUEHRTE Stand**
   (``tageslauf.ablage_stand``): letzte gruene Protokollzeile (ueber die
   Kette alles davor), Manifest des Stands, Config. Ein roter Lauf bewegt
   ihn nicht — der Wiederanlauf nach einem gescheiterten Bericht (T26-02)
   bleibt auf demselben Stand. Registrierte, noch nicht aufgenommene
   Eingaenge gehoeren nicht dazu: Jeder bringt seine eigene Abnahme mit,
   und zwei Registrierungen vor demselben Lauf entziehen einander nicht
   die Abnahme; die Bindung an den Eingang (sein Nummernband) faengt, wenn
   ein anderer dazwischen registriert wurde.
2. **Aufnahme und Eintritt sind zwei Fragen.** Die Stand-Bindung gilt
   der ersten Aufnahme durch einen gruenen Lauf — gefuehrt oder, bei einem
   Stichtag nach dem Lauftag, wartend. Wartende Eingaenge tragen dafuer
   ihren Hash in der Protokollzeile (``wartende_uebernahmen[].eingang_sha256``).
   Sonst liefe ein vorausdatierter Zugang an seinem Stichtag gegen einen
   laengst vergangenen Stand und traete nie ein. Am TATSAECHLICHEN Eintritt
   (dem ersten Lauf, der ihn fuehrt) haelt der Tageslauf, was sich durch
   den Betrieb nicht aendert, gegen die Abnahme: Config-Hash, Kern-Version
   und Code-Stand (Image-Digest und Revision, soweit die Probe sie erfasst
   hat, und der Hash des Pakets, ``quellcode_sha256``). Abweichung heisst
   Verweigerung mit Ausweg (Probe und A-B2 neu). Danach fragt kein Lauf
   mehr.
3. **Die Bindung liegt in der Ablage** als ``zugangsabnahme.json`` neben
   ``eingang.json``, gezeichnet mit dem Betriebsschluessel — der Tageslauf
   kennt den Fall nicht und haelt keinen Freigabeschluessel. Sie steht
   nicht in ``dateien`` von eingang.json: Die Abnahme bindet den Hash von
   eingang.json, eingang.json kann ihren Hash nicht zugleich tragen.
4. **Derselbe Eingang heisst dieselben Bytes.** Die Probe registriert in
   ihrer Kopie ueber dieselbe Funktion und dieselbe Serialisierung wie die
   Registrierung; die Betriebszeichnung ist deterministisch. Deshalb
   braucht die Registrierung dieselben Angaben wie die Probe (``--fall``,
   ``--quelle``, Stichtag, Betriebsschluessel); die Meldung nennt die
   abweichenden Felder.
5. **Das Soll sind die SYSTEMWERTE der geltenden Abnahmen**, gebunden an
   ihre Bytes: ``aktuartest.json`` muss das Testergebnis sein, das der
   A-M1-Snapshot pinnt, den der A-M4-Snapshot pinnt, ``migrationssuite.json``
   die Suite, die der A-M4-Snapshot pinnt — beide Snapshots geltend und
   angenommen. Probe, Beleg-Vertrag, Gate und Registrierung halten das
   gegen dieselbe Regel (``models.zugangsprobe.soll_bindung_fehler``); das
   Gate zusaetzlich die Bytes am festen Ort. Abweichung ist Verweigerung:
   Die Dateien liegen ohne Schluessel beschreibbar im Fall, und gegen ein
   fremdes Soll gibt es nichts zu rechnen. Verglichen werden Anzahl,
   Versicherungssumme (aus der Uebernahme) und Jahresbeitrag
   (``bjb_stichtag_1`` der Migrationssuite) je Summe UND je Vertrag ueber
   den GANZEN Zugang, am Folgetermin die Anzahl in Kraft; dazu Zugaenge,
   Zugangsbuchungen, Bewegungskonto und alles ausserhalb des Zugangs.
   Toleranz ein halber Cent. Jede Bewertungsspalte des Abschlusses ist
   entweder einer verglichenen Groesse zugeordnet oder mit Grund als
   "nicht belegt" ausgenommen (``ABSCHLUSS_VERGLICHEN``,
   ``ABSCHLUSS_NICHT_BELEGT``, Ratsche mit ``==`` gegen
   ``models.bestand.ABSCHLUSS_ZAHLEN``).
6. **Benannte Grenzen und der Code-Stand.** Der Zugangsstichtag ist ein
   Monatserster (nur dort gibt es einen Abschluss, an dem die Differenz
   gegen die Uebernahme zu halten ist). Der Folgetermin wird verglichen,
   wenn er ein Abschluss im Fenster ist (sonst ``--bis``). Die Probe haelt
   ihren Code-Stand gegen die letzte gruene Protokollzeile der Ablage:
   Image-Digest und Revision, soweit die Zeile sie erfasst hat, und den
   Hash des Pakets (``quellcode_sha256``, seit dieser Nachbesserung in
   jeder Zeile), dazu die Kern-Version. Jede Abweichung ist ein Befund,
   ebenso eine Zeile, die gar keinen Code-Stand belegt. Ein
   Versionsstring allein ist keine Identitaet.
7. **Die Kopie ist gekennzeichnet** (``zugangsprobe-kopie.json``): Nur auf
   ihr registriert die Probe ohne Abnahme und laesst ihren Eingang ohne
   Abnahme eintreten; auf einer echten Ablage verweigern beide Wege, und
   auf der Kopie verweigert jeder echte Lauf. Das Kennzeichen entsteht vor
   dem ersten kopierten Byte (Runde F, F6). Weil es eine ungezeichnete
   Datei ist, traegt zusaetzlich jede Protokollzeile eines Probelaufs
   gezeichnet das Feld ``zugangsprobe`` (Fall, Kennung, Kopie, Zeitpunkt;
   Runde F, F9): Tageslauf, Export, Tagesseite und Konsument verweigern
   eine Kette mit einer Probezeile als Kettenbruch ("Probenkopie"),
   Registrierung, Neuaufsetzen und die Probe selbst verweigern Kennzeichen
   oder Probezeile. Entfernt jemand das Feld ohne Schluessel, bricht die
   Signatur. Die Ausnahme vom A-B2 haengt am Zeichner des Probelaufs, nicht
   an einem Parameter: Ein Eingang tritt ohne Abnahme nur in einer Zeile
   ein, die als Probezeile gezeichnet ist.
8. **Neuaufsetzen**: Der Eingang der neuen Ablage braucht seine eigene
   A-B2, gerechnet auf einer leeren Ablage mit der neuen Config (deren
   gefuehrter Stand ist genau das), uebergeben mit ``--zugangsabnahme``.
9. **Tests**: Die Suite registriert an vielen Stellen, deren Gegenstand
   nicht A-B2 ist. Fuer sie legt eine sessionweite Naht
   (``uebernahme._STANDARD_ZUGANGSABNAHME``, Muster der Naht des
   Betriebsschluessels) einen synthetischen, gezeichneten Probenbeleg und
   einen signierten A-B2-Snapshot im Fall an; geprueft wird er danach wie
   jeder andere. Produktiv ist sie leer.

10. **Wer A-B2 zeichnet, prueft die Registrierung.** Sie haelt den
    Fingerabdruck der Freigabe gegen die Zeichnungsordnung des Betriebs
    (``--zeichnungsordnung``): Die Rolle muss A-B2 in ihrer gates-Liste
    tragen (seit dem Nachtrag 2026-10-01 dieselbe Regel fuer A-M4 und
    A-M1). Das Gate A-B2 dagegen haelt den Betriebsschluessel nicht; es
    prueft Form und Rolle der Betriebszeichnung der Probe und sagt in
    seiner Ausgabe, dass es die Signatur nicht verifiziert hat
    (``betriebssignatur``) — die Registrierung rechnet sie nach.

**Offen, fachlich (nicht entschieden):** Das Deckungskapital eines
Monatsabschlusses ist der Jahreswert zum letzten Vertragsjahrestag
(``zustand_am``), der Systemwert des aktuariellen Tests und der
Migrationssuite am Stichtag die Monatsreserve plus Schicht. Bis zum
Entscheid des Maintainers vergleicht die Probe das Deckungskapital NICHT;
sie fuehrt es an jedem Termin mit dem Grund "nicht vergleichbar:
Konvention Jahreswert vs. Monatsreserve, Entscheid offen" im Beleg
(``models.zugangsprobe.NICHT_VERGLICHEN``). Ein Beleg, der es gruen
verglichen fuehrt, besteht nicht — ein Vergleich ungleicher Groessen ist
kein Nachweis. Die Stelle, an der danach je Vertrag ueber den ganzen
Zugang verglichen wird, ist vorbereitet
(``DK_KONVENTION_ENTSCHIEDEN``), der Test dafuer ebenso (xfail, strict).
Ob Abschluss oder Abnahme die Konvention wechselt, entscheidet das
Aktuariat, nicht die Probe.

## Nachtrag 2026-10-01: eine Rollenregel fuer jede Abnahme, auf der etwas gruendet

Entscheid des Maintainers: Die Rollenpruefung der A-M4-Freigabe wird an
die der A-B2-Freigabe angeglichen, als Klasse. Die Invariante: **Wer einen
Abnahme-Snapshot liest, um darauf etwas zu gruenden, haelt die ZEICHNENDE
Rolle gegen die Ordnung — und die Rolle ist die des Schluessels, nicht die
behauptete.**

Vorher hielt nur die Registrierung den Fingerabdruck der A-B2-Freigabe
gegen die Zeichnungsordnung (Punkt 10). A-M4 und den A-M1-Snapshot, den
A-M4 pinnt, las der Betrieb mit Schema, Kette, Belegrollenmenge und
Freigabesignatur — aber nicht mit der Frage, ob der signierende Schluessel
einer Rolle gehoert, die das Gate zeichnen darf. Ein gueltig signierter
A-M4-Snapshot eines Schluessels, dem die Ordnung nur A-B2 gibt,
begruendete eine Uebernahme. Das Gate A-B2 las A-M4 und A-M1 fuer die
Soll-Bindung der Probe ganz ohne Rollenpruefung, das Gate A-M4 seine
Vorbedingungen (A-Q1, A-M1, im Bestands-Scope A-M2, A-M3) mit Rollen-,
aber ohne Rollenfeldpruefung. Und kein Leser verglich das Rollenfeld eines
Snapshots mit der Rolle seines Schluessels.

Die Menge (Gate x Lesestelle):

| Lesestelle | A-Q1 | A-M1 | A-M2/A-M3 | A-M4 | A-B2 |
|---|---|---|---|---|---|
| Registrierung (``uebernahme.eingang_anlegen``) | — | ja (Soll-Bindung, unter der Sperre) | — | ja | ja |
| Registrierung in der Probenkopie (``probe_kopie``) | — | — | — | ja | — |
| Zugangsprobe (``zugangsprobe.lies_soll``) | — | ja | — | ja | — |
| Neuaufsetzen, vor dem Anlegen (``registrierung_vorbedingungen``) | — | — | — | ja | ja (``--zugangsabnahme`` oder Gate-Ledger) |
| Gate A-B2 (``gates.gate_entscheid``, Soll-Bindung der Probe) | — | ja | — | ja | — |
| Gate A-M4 (Vorbedingungen) | ja | ja | ja (Bestand) | — | — |
| Eintritt im Tageslauf | — | — | — | — | — |

In der Probenkopie gibt es noch keine A-B2 und keine Soll-Bindung; A-M1
liest dort erst ``lies_soll``. Nach der Vorpruefung registriert das
Neuaufsetzen wie jede Registrierung (erste Zeile).

**Die Regel** ist EINE Funktion, ``models.zeichnung.zeichnende_rolle_fehler``
— in ``models``, weil zwei Schichten sie lesen (Gates und Betrieb; keine
neue Kante, ``code_karte`` befundfrei). Vier Fragen: Gibt die Ordnung dem
Fingerabdruck der Freigabe eine Rolle (ohne Ordnung: keine Antwort, keine
Abnahme)? Darf die Rolle das Gate zeichnen? Tragen ``rolle`` und
``zeichnung.rolle`` des Snapshots genau diese Rolle? Ist
``zeichnung.schluesselklasse`` die Klasse, die die Ordnung der Rolle gibt,
und traegt eine laut Ordnung simulierte Rolle ihr Mandat? Verstoss ist
Verweigerung mit Meldung (beide Rollen bzw. Klassen, die laut Ordnung
berechtigten Rollen) und Ausweg. Die vierte Frage kam in der Angriffsrunde
desselben Tages dazu: Vorher kam die Klasse aus dem Snapshot. Gab die
Ordnung ``simulation`` und behauptete der Snapshot ``mensch`` ohne Mandat,
wurde registriert, die Mandatspflicht griff nie, und Eingang und Seite
meldeten eine menschliche Zeichnung. Das Gate schreibt beim Zeichnen die
Klasse der Ordnung (``zeichnung_fuer``); der Leser ist auch hier die
zweite Haelfte. Der Betrieb ruft sie ueber
``uebernahme.zeichnende_rolle`` in seinem einen Leser
``lies_abnahme_snapshot`` (``ordnung`` Pflicht ohne Default), das Gate an
jeder fremden Abnahme, auf die es gruendet.

**Die dritte Frage ist die zweite Haelfte einer Regel, die es schon gab.**
Beim Zeichnen bestimmt das Gate die Rolle aus dem Schluessel und schreibt
sie in beide Felder (``gates.gate_entscheid``: ``rolle = bestimmt``;
``zeichnung_fuer``; ein widersprechendes ``--rolle`` ist ein
Bedienfehler). Jeder echte Produzent erfuellt die Gleichheit also. Der
Leser haelt sie gegen SEINE Ordnung — und das ist nicht immer dieselbe:

* Das Gate haelt gegen die Ordnung, unter der es gerade zeichnet
  (``--zeichnungsordnung`` des Gate-Aufrufs: bei A-B2 die Ordnung der
  zeichnenden Rolle ``mensch/betrieb``, bei A-M4 die des Aktuars).
* Der Betrieb haelt gegen die Ordnung, die dem Betriebsschluessel seine
  Rolle gibt (``--zeichnungsordnung`` von Registrierung und Probe).

Eine Abnahme muss also unter JEDER Ordnung, die auf ihr gruendet, von
einer berechtigten Rolle mit demselben Namen stammen. Nennen zwei
Ordnungen dieselbe Rolle verschieden, verweigert der Leser — er kann
nicht wissen, welche recht hat. Fuer den Betrieb heisst das: Seine Ordnung
nennt neben ``betrieb/tageslauf`` und ``mensch/betrieb`` (A-B2) auch die
Rolle(n), deren Schluessel A-M1 und A-M4 signiert haben, unter demselben
Namen wie die Ordnung des Falls. Bereits registrierte Eingaenge sind nicht
betroffen; Neuregistrierung und Neuaufsetzen schon.

**Konvention fuer den Eintritt (entschieden, nicht gebaut).** Massgeblich
ist die Ordnung zum Zeitpunkt der Registrierung. Die Registrierung haelt
die Rolle jeder Abnahme gegen die Ordnung, schreibt das Ergebnis in
``eingang.json`` (A-M4: Rolle, die nach der Regel die des Schluessels IST,
und Praefix des Fingerabdrucks) und ``zugangsabnahme.json`` (A-B2:
``freigabe_rolle``) und zeichnet beides mit dem Betriebsschluessel. Ein
spaeterer Entzug der Berechtigung wirkt nicht zurueck — wie bei jeder
Zeichnung. Der Eintritt liest keinen Snapshot; eine Ratsche haelt das.
*Verworfen:* die Neupruefung beim Eintritt gegen die dann geltende Ordnung.
Sie machte einen bereits gezeichneten Satz von einer spaeter geaenderten
Datei abhaengig: Derselbe Eingang traete je nach Tag ein oder nicht, und
der Betrieb haette zwei Wahrheiten ueber dieselbe Registrierung.

*Der 16-Zeichen-Praefix* (``eingang.json``, ``zeichnung.schluessel_sha256``)
ist dabei keine Schwaeche: Er ist Anzeige, kein Pruefanker. Gebunden ist
der volle Fingerabdruck ueber den vollen Snapshot-Hash im gezeichneten
Eingang — der Snapshot traegt ihn in seiner signierten Freigabe. Eine
Verwechslung zweier Schluessel ueber 64 Bit setzte voraus, dass jemand
einen zweiten Schluessel mit gleichem Praefix erzeugt UND der Leser den
Praefix als Anker nimmt; keiner tut das. Ein Feld mit dem vollen
Fingerabdruck waere eine zusaetzliche Angabe im Eingang (ohne Schemabruch
moeglich), wird aber erst gebraucht, wenn jemand aus der Ablage allein
ohne den Fall pruefen soll — dann als eigener Vorschlag.

**Test-Schluessel.** Die Suite bildet die produktive Lage ab: getrennte
Schluessel fuer ``mensch/aktuariat`` (A-M1 bis A-M4) und ``mensch/betrieb``
(A-B2), die Snapshots tragen das Rollenfeld ihres Schluessels
(``tests/freigabe_testschluessel.py``). Die Standardrolle der Gate-Tests
zeichnet die Gates des Falls, nicht A-B1/A-B2.

Kein Vertrag aendert sich: Snapshot, ``eingang.json`` und
``zugangsabnahme.json`` behalten Form und Schema-Version; verschaerft ist,
welche Snapshots Gate und Betrieb als Grundlage annehmen. Die Felder
``rolle`` und ``schluesselklasse`` im Eingang behalten Form und
Wertebereich; fuer neu registrierte Eingaenge sind sie zusaetzlich die der
Ordnung zum Zeitpunkt der Registrierung. Ein Eingang aus der Zeit davor
traegt die Angabe seines Snapshots; kein Leser behandelt beide
verschieden, deshalb keine neue Schema-Version.

**Neuaufsetzen.** Die Vorbedingungen der Registrierung, die keinen Ort
brauchen (``uebernahme.registrierung_vorbedingungen``: A-M4 und A-B2 samt
Regel, Schema, Tabellen und Uebernahmebeleg gegen den Beleggraphen), prueft
``betrieb.neuaufsetzen`` VOR dem Anlegen der neuen Ablage — dieselbe
Funktion, die ``eingang_anlegen`` ruft. Was nur gegen die neue Ablage
pruefbar ist (Bindung der A-B2 an Eingang und Stand, A-M1 der
Soll-Bindung, Nebentabellen, P-B1, Lesbarkeit), scheitert danach; dann
entfernt die Routine ihre eigene, nie veroeffentlichte Vorbereitung
(``betrieb._loeschen``, Name dieses Aufrufs, ohne Provenienz). Vorher blieb
``<stand>.neu-<stempel>`` liegen, und der naechste Aufruf verweigerte mit
"Rest eines abgebrochenen Aufbaus". ``tageslauf.SCHREIBZIELE`` deckt dieses
Staging nicht ab: Die Tabelle gilt den atomaren Schreibern UNTER der
Ablage; die Vorbereitung liegt daneben und gehoert keinem Lauf.

**Grenze der Aussage.** Die Freigabe ist ein HMAC. Wer registriert und den
Ring haelt, kann jedes Rollenfeld und jede Klasse gueltig neu signieren:
Die Regel schuetzt gegen abweichende Ordnungen und fremde Snapshots, nicht
gegen den Inhaber des Rings.

Instrumente (``tests/test_abnahme_rolle_klasse.py``,
``tests/test_neuaufsetzen_vorbedingungen_klasse.py``): je Gate und
Lesestelle Angriffe (Ordnung ohne das Gate; gefaelschtes, neu signiertes
Rollenfeld oder Klasse; eine Ordnung, die die Rolle anders nennt oder ihr
eine andere Klasse gibt; Schluessel ohne Rolle) mit Positivkontrollen; ein
Zaehltest, der Registrierung, Probe, Eintritt, Export und Neuaufsetzen
faehrt und jedes lesende Oeffnen unter ``entscheide/`` seinem Aufrufer
zuschreibt (``==`` gegen die erlaubten Leser; Positivkontrolle: ein
kuenstlicher Leser mit Konkatenation und glob); Ratschen mit ``==`` ueber
die Leseraufrufe des Betriebs, die Regel- und Kettenaufrufe im Gate, jede
Erwaehnung von ``entscheide`` im Betrieb und die Test-Ordnungen (kein
Schluessel fuer Fall- und Betriebsabnahmen zugleich, kein neuer ``'*'``),
je mit Positivkontrolle; je Verweigerungsursache des Neuaufsetzens ein
Zaehltest der Reste (``==``); Mutationsproben je Regelstelle.
