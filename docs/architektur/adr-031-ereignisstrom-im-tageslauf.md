# ADR-031: Der Ereignisstrom als Eingang der Buchung

**Status:** angenommen am 2026-10-29 (Maintainer): Option B mit zwei
Sichten auf die Config, bitgleich auch auf der laufenden Ablage; drei
benannte Kanten in der Ratsche statt einer. Entwurf vom 2026-10-22 aus
Befund A29-03 der externen Prüfrunde vom 2026-10-14; Nachzug nach der
Merge-Prüfung am 2026-10-30 (Zustandsregeln der Buchung, Tests der
Sichten, Folgepunkte).

## Kontext

ADR-017 trennt die Vorzeige (Ebene 3: Rechenkern, Bestand,
Bestandsführung) von den Vorzeige-Werkzeugen (Ebene 4: was die Vorzeige
herstellt und in der Wirklichkeit ein Unternehmen oder Quellsystem liefern
würde). Im Paket ist diese Grenze eine Ratsche:
`VORZEIGE_NACH_WERKZEUG_ERLAUBT` in `ontologie/code_karte.py` erlaubte
fünf Kanten aus der Führung in die Simulation.

Der externe Prüfer urteilte (ToDo 29, A29-03): Simulation und PLV-Betrieb
sind deklariert getrennt, aber funktional verbunden. Der Tageslauf erzeugt
Neugeschäft und ruft die Simulationsfortschreibung direkt; `BestandConfig`
trägt Tarifgenerationen, Seed, Verteilungen, Erfahrungsannahmen und
Tagesbetrieb zusammen. Seine Empfehlung: ein Führungslauf verarbeitet
einen ausdrücklichen Ereignisstrom, und die Simulation kann einen solchen
Strom liefern. Sein Prüfkriterium: Eine neue Anwendung, etwa ein
Cashflow-Lauf, braucht keine Simulation des Tagesbetriebs mehr.

Gemessen am Stand 0b6470c, vor dem Bau:

* Die Engine `bestand/ereignisse.py` zog je Vertragsjahr aus ihren
  Strömen und buchte im selben Schritt mit Beträgen aus dem Kern. Ob
  gezogen wird, hing nie von einem Betrag ab: Die Bedingungen der
  Ziehungen sind der Zustand (beitragsfrei oder nicht), das Vertragsjahr
  gegen Laufzeit und Beitragsdauer, der Tarifwerk-Schalter
  `red_verfahren`, die Annahmen und für den Tod die Rechnungsgrundlage
  `qx` der Tafel.
* Eine sechste Kopplung stand nicht in der Ratsche: Das Tagesjournal zog
  den Meldeverzug eines Todesfalls selbst (Strom `meldeverzug`), und die
  Ratsche sah es nicht, weil `zufallsstroeme` nicht als Werkzeugmodul
  geführt war.
* 107 Testdateien nennen Tageslauf oder Fortschreibung; über dreißig
  importieren `fortschreiben` aus `bestand.ereignisse`, vier rufen Funktionen des
  Tagesjournals mit der Config allein, ohne Liste. Ein AST-Inventar
  (`tests/test_herabsetzung_und_teilkuendigung.py`) hält die
  Buchungsliterale je Modul fest, darunter die von `ereignisse.py`.

Was gewollt ist, bleibt: Die PLV ist eine Simulation; dass der Tageslauf
Neugeschäft und Ereignisse selbst erzeugt, ist für das vorgeführte
Unternehmen gewollt. Die Frage war, ob die Naht zwischen „was in der
Welt passiert" und „was die Führung damit tut" im Code liegt statt nur in
der Verabredung.

## Entscheidung

**Ziehen und Buchen sind im Code getrennt, im selben Lauf.** Dazwischen
liegt genau ein Datentyp, die Ereignisliste. Ihr Vertrag (Codes, Schema,
Fehler, dazu die Zugangslage eines Vertrags) liegt heute im Modul der
Welt, und die Buchung importiert ihn von dort; ihn in ein Modul der
Führung oder nach `models/` zu legen, ist ein Folgepunkt (ein reiner
Umzug, bitgleich).

* Die **Ziehung** (`bestand/ziehung.py`, Ebene 4) führt je Vertrag den
  Zustand mit und liefert eine `Ereignisliste`: je Zeile Police, laufende
  Nummer (die Reihenfolge der Ziehung), Vertragsjahr, Ereignis,
  Wirkungstag und die gezogenen Parameter — den fortgeführten Anteil und
  das Verfahren einer Herabsetzung oder Teilkündigung, den Erhöhungssatz
  einer dynamischen Erhöhung. Dazu die Zugänge des Neugeschäfts als
  POL-Basiszeilen. Sie liest Rechnungsgrundlagen (die Tafelbasis, die
  Übergangswahrscheinlichkeiten des BU-Produkts), nie einen Rechenwert.
  Für die KLV baut sie keinen Rechenkern; für die BU baut sie das Produkt
  aus `kern/` und liest seine Übergänge, rechnet aber keinen Betrag. Der
  Ablauf ist kein gezogenes Ereignis: Ihn bucht die Führung aus den
  Vertragsdaten.
* Die **Buchung** (`bestand/ereignisse.py`, Ebene 3, `buche`) wendet die
  Liste mit Beträgen aus dem Kern an und schreibt Statushistorie, Ledger,
  Scheiben, Zugänge und Reduktionen. Jedes Ereignis der Liste kommt in
  die Bücher oder ist ein Fehler — nach dem Ende des Vertrags, jenseits
  des Horizonts, für eine fremde Police oder im falschen Zustand. Vor dem
  ersten Kernaufruf hält die Buchung die Liste gegen die Regeln der Welt:
  Wirkungstag am Jahrestag des Vertragsjahrs, Beitragsfreistellung
  höchstens einmal und nur beitragspflichtig, danach kein Storno, keine
  Erhöhung und keine Herabsetzung, kein Storno im Ablaufjahr, keine
  Erhöhung nach dem Beitragsende, und die Form der Einträge (Anteil und
  Verfahren nur bei Herabsetzung und Teilkündigung, der Satz bei der
  Erhöhung). Eine Liste in Zugreihenfolge, die mehr behauptet, als die
  Welt zieht, wird nicht still gebucht; die Reihenfolge selbst und
  Doppelungen im selben Vertragsjahr prüft die Buchung noch nicht
  (Folgepunkt). Die Buchung kennt weder Seed noch Annahmen.
* `fortschreiben` bleibt als **Fassade** (ziehen, dann buchen in einem
  Aufruf) — die Schnittstelle vor diesem ADR, unverändert in Signatur und
  Ergebnis. `_simuliere_vertrag` ebenso je Vertrag.
* Der **Tagesstrom** (`betrieb/ziehung.py`, Ebene 4) liefert dem
  Tageslauf in einem Aufruf das Neugeschäft seit dem Betriebsbeginn, die
  Ereignisliste und die **Meldetage** der Todesfälle (der Meldeverzug,
  bis hierher vom Tagesjournal gezogen) — auch der Tode, die eine
  Übernahme mitbringt. Der Tageslauf ruft erst den Strom, dann die
  Buchung, dann das Tagesjournal mit den Meldetagen aus dem Strom. Dass
  der Tageslauf die Meldetage weitergibt, hält noch kein Test; ohne sie
  zöge das Journal über die dritte Kante selbst, mit denselben Werten
  (Folgepunkt: ein Test, der den Rückfallzweig während eines Tageslaufs
  verweigert). Die
  Arithmetik der Nummernkreise (Verkaufstag aus der Police-Nummer) zieht
  in `betrieb/nummernkreis.py` zur Führung; das Neugeschäft der Welt
  vergibt die Nummern nach derselben Regel.
* **Zwei typisierte Sichten** auf `BestandConfig` (`config.fuehrung()`,
  `config.welt()`): die Führung (Tarifwerk je Generation, Betriebsbeginn,
  Nummernkreise, Berichtsfelder) und die Welt (Seed, Annahmen,
  Plausibilität, Referenzstichtag, Verteilungen, Neuzugang,
  Wochentagsgewichte, Meldeverzug). Die Grenze folgt A-T1
  (`NICHT_TARIFWERK`); `SICHT_FELDER` ordnet jedes Feld genau einer
  Sicht zu, ein Test hält die Zuordnung vollständig. Die Datei bleibt
  eine, die laufende Ablage hält nicht an, A-T1 bleibt gültig. Die
  Buchung bucht mit der Führungssicht allein; die Welt liest das
  Tarifwerk der Führung, nicht umgekehrt.
* **Die Ratsche hat drei benannte Kanten** aus der Führung in die Welt,
  statt fünf: der Tageslauf zum Tagesstrom; die Fassade `fortschreiben`
  zur Ziehung; das Tagesjournal zum Meldeverzug, wenn kein Strom
  übergeben wird. `zufallsstroeme`, `bestand/ziehung` und
  `betrieb/ziehung` sind Werkzeugmodule, damit die Ratsche den
  Meldeverzug sieht. Eine einzige Kante wäre nur mit Änderung von etwa
  vierzig Testdateien zu haben gewesen; der Maintainer entschied, die
  Tests unverändert zu lassen und die drei Kanten zu benennen.
* **Prüfkriterium: bitgleich.** Für die Testwelten und für eine Kopie der
  laufenden Ablage entstehen Stand, Tagesjournal, Abschlüsse und
  Übernahmen Byte für Byte wie vorher; die Protokollzeile unterscheidet
  sich nur in Code-Hash und Zeichnung. Nachweis siehe unten.

### Verworfen

* **A, so lassen und vollständig messen:** der Befund bliebe; ein
  Cashflow-Lauf müsste weiter durch Code, der würfelt.
* **C, der Strom als Datei in der Ablage** (`ereignisse/<tag>.parquet`,
  zwei Befehle, Ereignisprüfung): ändert die Laufzeit und bringt neuen
  Code mit eigener Angriffsfläche. Nach B ist C kleiner, weil der
  Datentyp steht; darüber wird neu entschieden, wenn die Regie Szenarien
  als Daten einspielen soll.
* **D, die Config teilen:** Die Bytes der Config änderten sich, die
  laufende Ablage hielte an (Config-Wechsel), der einzige Ausweg wäre das
  Neuaufsetzen mit Verlust der geführten Geschichte. Statt dessen die
  zwei Sichten auf dieselbe Datei.

## Konsequenzen

* **Ebenen (ADR-017, ADR-028):** `bestand/ereignisse.py` ist Vorzeige
  (Ebene 3); `bestand/ziehung.py`, `betrieb/ziehung.py` und
  `bestand/zufallsstroeme.py` sind Vorzeige-Werkzeuge (Ebene 4). Die
  Modulliste der Simulation in ADR-028 ist damit überholt (Nachtrag
  dort). Die Kante `config -> stochastik` entfällt: Die
  Korrelationsmatrix wird in der Config gebaut und geprüft (Weltsicht),
  die Copula der Simulation zieht auf ihr.
* **Gezeichnete Gegenstände:** Kern, Referenzwerte, `plv/mathematik`,
  `plv/tarifplaene` und `plv/configs` sind unberührt. Keine Gate-Version
  ändert sich.
* **Laufende Ablage:** keine Umstellung über das Image hinaus; der
  nächste Image-Wechsel folgt dem eingeübten Weg (Probe auf Kopien der
  Ablage, Umstellen, Tageslauf, Timer).
* **Tests:** Die bestehenden Testdateien zu Tageslauf und Fortschreibung
  sind unverändert; das ist Teil des Nachweises. Neu:
  `tests/test_ereignisstrom_adr031.py` — die Liste entsteht ohne Kern,
  die Buchung aus einer gegebenen Liste ist die Fortschreibung Byte für
  Byte (KLV und BU), eine Mutation der Ziehung wird sichtbar oder ist
  ein Fehler, die Buchung hält die Liste gegen die Regeln der Welt (je
  Befund der Merge-Prüfung ein Test; acht Zweige der Regeln sind noch
  ungetestet, Folgepunkt), der Tagesstrom nennt jeden Tod, das Tagesjournal nimmt
  die Meldetage aus dem Strom, jede Generation steht mit ihrem Tarifwerk
  in der Führungssicht, die Buchung kommt ohne jedes Weltfeld aus, die
  Sichten decken jedes Feld, die Ratsche nennt genau drei Kanten, und ein
  Fingerabdruck hält die geteilte Engine gegen die Engine vor diesem ADR.
* **PLV bleibt Simulation:** Der Strom kommt aus der Simulation; es gibt
  keinen Weg für echte Kundenereignisse. Die Naht ist kein Produktivweg.

## Nachweis bitgleich

Werkzeuge: zwei Vergleichsskripte im Arbeitsbaum des Maintainers (nicht
im Repository). Das erste führt `cli_fortschreibung` und die Phase ablage
von `werkzeuge/welt/welt_aufstellen.sh` mit altem und neuem Codebaum und
vergleicht die Ausgaben; das zweite kopiert die laufende Ablage zweimal,
führt auf beiden Kopien den Tageslauf mit altem und neuem Codebaum und
vergleicht Stand, Tagesjournal, Abschlüsse und Übernahmen sowie die
Protokollzeile ohne Code-Hash und Zeichnung. Beides auf dem Host,
29.10.2026. Alt ist der Stand vor diesem ADR (c58605e), neu der Stand mit
Ziehung, Tagesstrom und Sichten (11c3e6c); die Zustandsregeln der Buchung
kamen am 30.10.2026 mit einem weiteren Vergleichslauf hinzu. Eine
Nullmessung alt gegen alt ging voraus und war ebenfalls bitgleich; die
Merge-Prüfung hat beide Vergleiche unabhängig wiederholt.

**Testwelten** (erstes Skript, `bis` 2026-10-29):

* `cli_fortschreibung` über die drei Configs in `plv/configs` (gesamt,
  klv, bu), Bestand aus dem Nichts ab dem ersten Verkaufstag der ältesten
  Generation (1994-07-01 bzw. 2000-01-01), je ein bis drei Sekunden: alle
  Parquet-Tabellen Byte für Byte gleich, `laufmanifest.json` ohne
  abweichenden Schlüssel.
* `werkzeuge/welt/welt_aufstellen.sh`, Phase ablage, mit denselben
  Schlüsseln für beide Seiten (Config `bestand_gesamt.toml`, Tageslauf
  vom Betriebsbeginn 1994-07-01 bis 2026-10-29 in einem Lauf: 3346
  Verträge Neugeschäft, 12354 Geschäftsvorfälle, 388 Monatsabschlüsse):
  beide Seiten je rund 520 Sekunden, 22648 Buchungen im Tagesjournal, 1735
  Verträge in Kraft, Stand `stand-1bb514562334e806`; Stand, Tagesjournal
  und Abschlüsse Byte für Byte gleich, dazu Berichte und Seite. Die neue
  Seite wurde nach einem Halt des Skripts (ein uncommitteter Test im
  Codebaum, den das Welt-Skript zu Recht verweigert) mit denselben
  Schlüsseln und Einstellungen als Phase ablage von Hand wiederholt.

**Kopie der laufenden Ablage** (zweites Skript, 29.10.2026 21:29 CET):
zwei Kopien der laufenden Ablage (Stand
`stand-00280e615a39ea3c`, geführt bis 2026-10-29, Config
`bestand_gesamt.toml`, Betriebsbeginn 1994-07-01, eine Übernahme mit 834
Verträgen), Tageslauf auf dem Host mit dem Stand davor (c58605e) und mit
diesem Stand (11c3e6c), `--heute 2026-11-01` (Nachholen des 30. und 31.
Oktober, Monatsabschluss zum 1. November). Beide Läufe 53 Sekunden, 2553
Verträge in Kraft, Stand `stand-a2e9f246f7e04611`; Byte für Byte gleich:
der Stand (alle Tabellen samt Laufmanifest), `tagesjournal.parquet`,
`abschluesse/`, `uebernahme/`, dazu `berichte/` und `seite/`; die
Protokollzeile gleich bis auf Code-Hash und Zeichnung.

Die Protokollzeile unterscheidet sich in allen Läufen nur im Code-Hash
und in der Zeichnung; `image_*` ist auf dem Host nicht erfasst. Die
Mutationsproben (Buchung ohne Beitragsfreistellung der Liste, Ziehung mit
vertauschter Draw-Reihenfolge, Tagesjournal ohne die Meldetage der Liste)
machen jeweils mindestens einen Test rot; die Ziehung selbst pinnt der
Fingerabdruck-Test gegen die Engine vor diesem ADR
(`FINGERABDRUCK_VOR_ADR031`, auf c58605e gerechnet).

## Folgepunkte

Aus den zwei Merge-Prüfungen, heute ohne Folge, weil die Liste im selben
Lauf aus der Ziehung kommt, in Zugreihenfolge:

* **Reihenfolge und Doppelungen in der Liste.** Die Regeln der Buchung
  laufen in Listenreihenfolge und setzen die Zugreihenfolge voraus; ein
  späteres Ereignis, das vor der Beitragsfreistellung in der Liste steht,
  umgeht sie, und eine zweite Erhöhung oder Teilkündigung im selben
  Vertragsjahr, die die Welt nie zieht, wird gebucht. Eine gültige Liste
  in anderer Reihenfolge wird mit falscher Begründung abgelehnt. Die
  Klasse schließt eine Formregel: je Vertrag das Vertragsjahr nicht
  fallend in der laufenden Nummer, je Jahr höchstens eine
  Beitragsfreistellung, Herabsetzung, Teilkündigung und Erhöhung.
* **Ungetestete Zweige der Regeln.** Ohne eigenen Test sind der
  Wirkungstag innerhalb des Jahres, Erhöhung und Herabsetzung nach dem
  Beitragsende (die Erhöhung fängt zusätzlich der Kern), die Herabsetzung
  in einem Tarif ohne Herabsetzung, die Teilkündigung im Ablaufjahr, eine
  Beitragsfreistellung mit Anteil, die Formregel der BU und der
  beitragsfrei übernommene Vertrag als Startzustand. Die Gegenrichtung
  ist gedeckt: Eine Regel, die strenger ist als die Welt, macht die Suite
  rot.
* **Der Vertrag der Liste** (Codes, Schema, Fehler und die Zugangslage
  eines Vertrags) zieht aus dem Modul der Welt in ein Modul der Führung
  oder nach `models/`; die Ziehung importiert ihn dann von dort. Ein reiner
  Umzug, bitgleich; danach trägt nur noch die Fassade die zweite Kante.
* **Die Weitergabe der Meldetage** im Tageslauf bekommt einen Test, der
  den Rückfallzweig des Tagesjournals während eines Tageslaufs verweigert.

## Bewusst nicht Bestandteil

* echte Ereignisse von außen, Schnittstellen zu Kunden oder Außendienst;
* eine inkrementelle Führung (Stand von gestern plus Ereignisse von
  heute) statt der Neuberechnung seit Betriebsbeginn;
* der Strom als Datei der Ablage (Option C);
* die Bewertungsannahmen eines Cashflow-Modells;
* der Zielvertrag zwischen Tool und PLV (ADR-030, vorgesehen).
