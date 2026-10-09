# ADR-025: Erstabnahme des Zielsystems — vier Gegenstände, vier Rollen, ein Ort außerhalb des Falls

**Status:** angenommen am 2026-10-01 (Maintainer), umgesetzt am selben Tag.
Die Zeichnungen der Erstabnahme sind Akte der Rollen, nicht des Codes; die
Bedienfolge steht am Ende.

## Kontext

Seit dem Nachtrag 2026-10-01 zu ADR-018 verlangt die Migrationsabnahme
`A-M4`, dass der Stand abgenommen ist, auf dem ein Fall rechnet: der
Kernstand (`A-K2`, gezeichnet von `mensch/rechenkern`) und der T-Box-Stand
(`A-O1`, `mensch/architektur`). Gezeichnet wurde das bisher im ersten Fall,
obwohl die Änderungen nicht aus dem Fall stammten: Der Kern war bis zu
diesem ADR außerhalb jedes Falls von 3.6.0 auf 3.16.0 gewachsen, die T-Box
auf 0.2.0. Einen Ort
für eine Abnahme außerhalb eines Falls gab es nicht. Das Tarifwerk der PLV
hatte keine eigene Abnahme, und der Anfangsbestand einer Ablage auch nicht.

Der Maintainer verlangte eine einheitliche Regel: entweder eine erste
Abnahme aller relevanten Stände oder keine. Entschieden wurde eine
Erstabnahme des Zielsystems außerhalb jedes Falls. Ein Fall zeichnet danach
nur, was er selbst ändert, und verweist sonst auf die Erstabnahme. Im
selben Zug wurden drei Erweiterungen beschlossen: Die Zeichnungsordnung
bekommt eine Versionslinie, deren Wurzel eine eigene Rolle verantwortet,
und der Betriebs-Agent wird definiert, damit jede fachliche Rolle der Linie
ein vorlegendes Gegenstück hat.

## Entscheidung

### 1. Eine Regel, vier Gegenstände (`models.standabnahme.GEGENSTAENDE`)

| Gegenstand | Gate | zeichnet | legt vor | Werkzeug (Beleg und Sicht) | verlangt von |
|---|---|---|---|---|---|
| Kernstand: Code des Rechenkerns, Referenzwerte, Grundsatzdokumentation | `A-K2.kernaenderung` | `mensch/rechenkern` | `agent/rechenkern` | `gates.kernstand_belegen` -> `abgeleitet/kern/aenderung.md` | A-M4 |
| T-Box-Stand | `A-O1.tbox-aenderung` | `mensch/architektur` | `agent/architektur` | `gates.stand_belegen tbox` -> `abgeleitet/tbox/aenderung.md` | A-M4 |
| Tarifwerk der PLV: Tarifpläne und Parametrierung der eigenen Tarifgenerationen | `A-T1.tarifwerk` | `mensch/aktuariat` | `agent/aktuariat` | `gates.tarifwerk_belegen` -> `abgeleitet/tarifwerk/aenderung.md` | A-M4 |
| Anfangsbestand einer Ablage | `A-B3.anfangsbestand` | `mensch/betrieb` | `agent/betrieb` | `betrieb.anfangsbestand belegen` -> `abgeleitet/anfangsbestand/beleg.md` | Betrieb |

Jedes Werkzeug zeigt die Änderung gegenüber der zuletzt abgenommenen Fassung
als lesbare Sicht, deterministisch aus dem Beleg erzeugt: den Kern je Modul
mit den Commits, die T-Box als Vergleich der Vokabulare (bei der
Erstabnahme das ganze Vokabular), das Tarifwerk je Tarifplan und je
Generation mit altem und neuem Wert, den Anfangsbestand mit Kennzahlen und,
bei einem erneuten Aufsetzen, der Abweichung zum zuletzt abgenommenen. Jedes
Gate prüft mit der Rollenregel (`models.zeichnung.zeichnende_rolle_fehler`).
`tests/test_erstabnahme_linie.py` legt die Tabelle abschließend fest.

### 2. Erstabnahme außerhalb jedes Falls: der Linienbereich

Jede Rolle zeichnet ihren Gegenstand einmal im **Linienbereich**; spätere
Änderungen zeichnet sie ebenfalls dort. Je Gegenstand entsteht eine Kette
wie im Fall, über dasselbe Kommando: `gate_entscheid --linie <linie>` ohne
`--fall`. Der Linienbereich verhält sich wie ein Fall (`entscheide/`,
`abgeleitet/`, Snapshot-Format, Signatur, Rollenregel, Kettenleser,
exklusives Schreiben), hat aber keinen Eingang einer Migration. Er wird
durch `linie.json` gekennzeichnet; seine Snapshots tragen den Scope `linie`
(P9-Schema 9) und binden `linie.json` statt `eingang.json` und A-Box.
Zeichenbar sind dort genau die vier Gegenstände, `A-B3` nur dort.

**Ort:** ein Verzeichnis `linie/`, das nicht zum Repository gehört (in
`.gitignore`; üblich ist `linie/` im Wurzelverzeichnis, eine Welt legt es
unter `<welt>/linie` an). Jedes Kommando verlangt `--linie` ausdrücklich;
eine Vorgabe gibt es nicht. Die Snapshots tragen Namen
der Entscheider, Fingerabdrücke von Schlüsseln und Mandats-Hashes einer
konkreten Installation; das gehört nicht in ein öffentliches Repository,
dieselbe Regel wie für `faelle/`. Unter `faelle/` liegt es nicht, weil der
Linienbereich kein Fall ist und jede Aufzählung der Fälle verfälschen würde.

**Schutz** wie `faelle/<fall>/entscheide/`: `entscheide/` und `ordnung/`
werden nur angefügt, nie überschrieben; derselbe Entscheid ist idempotent;
kein Kommando löscht dort. Der Betrieb liest den Linienbereich nur über den
einen Leser `uebernahme.lies_abnahme_snapshot`. Die Erstabnahmen sind die am
häufigsten referenzierten Zeichnungen des Systems; ihre Sicherung gehört zur
Sicherung der Installation.

### 3. Ein Fall zeichnet nur, was sich durch ihn ändert

`A-M4` verlangt in beiden Scopes Kernstand, T-Box-Stand und Tarifwerk
(Pflichtrollen `kernstand`, `tboxstand`, `tarifwerkstand`). Ist ein
Gegenstand gegenüber seiner geltenden Abnahme unverändert, verweist der
Fall darauf (Weg b): `stand_belegen verweisen --fall <fall> --gate <gate>
--linie <linie>` legt eine vollständige Kopie der geltenden Spitze in den
Fall. `A-M4` prüft Signatur, Rolle und Klasse und hält den Stand gegen den
lebenden. Ändert der Fall einen Gegenstand, zeichnet die zuständige Rolle
im Fall (Weg a). Eine Kette im Fall geht jedem Verweis vor.

Weg c, die Basislinie der T-Box, entfällt: Sie ersetzte eine erste Abnahme,
die es jetzt gibt. Snapshots nach Schema 8, die ihn führen, bleiben lesbar
(`WEGE_LESBAR`), entstehen aber nicht mehr.

### 4. Das Tarifwerk der PLV (`models.tarifwerkabnahme`)

Zum Tarifwerk (`TARIFWERK`) gehören `plv/tarifplaene/*` und je eigener
Generation (Knoten `<familie>/plv_<...>`) jeder Config unter
`plv/configs/*.toml` alle Felder des `[[generation]]`-Blocks außer
`NICHT_TARIFWERK` (Neuzugang, Trend, Verteilungen, Korrelationen,
Nummernkreis), samt Tarifzellen und Tarifwerks-Schaltern. Nicht dazu gehören
die Erfahrungsannahmen und die Simulation (`[annahmen]`,
`[plausibilitaet]`, `[tagesbetrieb]`): Sie beschreiben, wie sich die
simulierte Welt verhält, nicht, was ein Vertrag verspricht. Übernommene
Generationen tragen das Tarifwerk des abgebenden Hauses und werden im Fall
abgenommen. Die Auswahl ist eine Ausnahmeliste: Ein neues Feld gehört zum
Tarifwerk, bis jemand begründet, dass es Erfahrung ist. Die Tarifpläne
verlassen dafür den Kernstand (`models.kernabnahme.KERNSTAND`).

### 5. Der Anfangsbestand (`models.anfangsbestand`, `betrieb.anfangsbestand`)

Abgenommen wird der geführte Stand einer Ablage nach ihrem Aufbaulauf: Hash
je Tabelle, Config, Code-Stand, geführter Stand, registrierte Eingänge, ein
neu gefahrener Befund der Bestandswache P-B1 auf genau diesen Bytes (er muss
grün sein) und Kennzahlen. Der Beleg entsteht im Linienbereich,
`mensch/betrieb` zeichnet dort `A-B3`. Die Bindung liegt in der Ablage
(`anfangsbestand.json` neben `configs/`) und wird von `binden` geschrieben:
Es liest den A-B3-Snapshot über den einen Leser des Betriebs, hält seinen
Stand gegen den lebenden Anfangsbestand und zeichnet die Bindung mit dem
Betriebsschlüssel. Der Tageslauf kennt die Linie nicht und hält keinen
Freigabeschlüssel.

**Wann verlangt:** Der Aufbaulauf einer Ablage läuft ohne Abnahme, denn er
erzeugt erst, was abgenommen wird. Jeder weitere Lauf verlangt die
gezeichnete Bindung, sonst endet er mit Exit 2, roter Protokollzeile und
Ausweg. Eine bestehende Ablage ohne Bindung läuft nicht weiter, bis der
Betrieb ihren geführten Stand als Anfangsbestand abnimmt. Eine
Zugangsprobe auf einer Kopie der Ablage verlangt die Bindung ebenfalls;
eine `A-B2` entsteht so nur auf einer Ablage, deren Anfangsbestand
abgenommen ist. Auf einer leeren Ablage (Neuaufsetzen) wird der Zugang Teil
des Anfangsbestands und mit ihm abgenommen.

### 6. Namen nach ADR-012

`A-T1.tarifwerk`: neuer Gegenstand `T`, das Tarifwerk ist weder Rechenkern
(`K`) noch Vokabular (`O`) noch Quelle (`Q`). `A-B3.anfangsbestand`:
Gegenstand `B`, nächste freie Nummer. `A-Z1.ordnungsaenderung`: Gegenstand
`Z`, die Zeichnung eines Glieds der Ordnungslinie (Abschnitt 7). Sie ist
kein P9-Snapshot und steht deshalb nicht in `GUELTIGE_GATES`, kann aber
von einer Ordnung vergeben werden (`ZEICHENBARE_GATES`). `A-M5` ist der
Fallabbruch, `A-M6` der Fallauftrag (ADR-026).

### 7. Die Versionslinie der Zeichnungsordnung (`models.ordnungslinie`)

Jeder Snapshot pinnt `zeichnung.ordnung_sha256`, aber es war nirgends
festgehalten, welche Fassungen der Ordnung es gab. Ein Vergleich der
Hashes hätte bei jeder Erweiterung der Ordnung alle Belege entwertet.

**Die Linie** liegt im Linienbereich unter `ordnung/`, eine Datei je Glied
(`<nummer>.json`, seit dem Nachtrag Prüfrunde I, Punkt 4). Sie wird nur
angehängt, exklusiv und unter einer Sperre, und ist über Hashes verkettet.
Ein Glied trägt seine Nummer, den Hash seines Vorgängers, den SHA-256 der
Ordnungsdatei und ihren Inhalt (Rollen mit Klasse, Fingerabdruck und Gates,
keine Geheimnisse), die aus beiden Fassungen gerechnete Liste der Änderungen
(`neue_rolle`, `rolle_entfallen`, `gates_erweitert`, `gates_entzogen`,
`schluessel_gewechselt`, `klasse_geaendert`; beim Lesen nachgerechnet),
einen Zeitpunkt, einen Eintragsvermerk und die Zeichnung. Beispiel
(gekürzt):

```
{"schema_version": 2, "art": "ordnungsglied", "nummer": 2,
 "vorgaenger": "<glied_sha256 von Glied 1>",
 "ordnung_sha256": "<sha256 der Ordnungsdatei>", "ordnung_text": "{...}",
 "aenderungen": [{"art": "gates_erweitert", "rolle": "mensch/architektur",
                  "gates": ["A-K2"]},
                 {"art": "gates_entzogen", "rolle": "mensch/aktuariat",
                  "gates": ["A-T1"]}],
 "fruehere_zeichnungen": {"mensch/aktuariat": "gueltig"},
 "eingetragen_am": "2026-10-01T09:00:00+00:00",
 "eintrag": {"art": "anhang", "vermerk": "gezeichnet von ... (A-Z1) ..."},
 "zeichnung": {"gate": "A-Z1", "rolle": "mensch/vorstand", "schluesselklasse": "mensch",
               "schluessel_sha256": "<laut Glied 1>", "verfahren": "hmac-sha256-v1",
               "signatur": "..."},
 "glied_sha256": "..."}
```

**Zeichnen:** `gate_entscheid` zeichnet nur unter einer Ordnung, die die
Spitze der Linie ist, und die Zeichnung pinnt das Glied
(`zeichnung.ordnungsglied_sha256`, P9-Schema 9). **Lesen:** Wer eine Abnahme
liest, um auf ihr zu gründen, sucht das gepinnte Glied und hält Rolle, Klasse
und Gate-Berechtigung gegen dessen Ordnung: Maßgeblich ist, wer damals
zeichnen durfte. Eine spätere Erweiterung entwertet nichts; was ein späterer
Entzug bewirkt, regelt der zweite Nachtrag zu Prüfrunde H, Punkt 1. Ein Snapshot ohne
auffindbares Glied wird benannt verweigert.

**Der Schnitt:** Die Linie beginnt mit der Ordnung der Erstabnahme. Abnahmen
abgeschlossener Fälle davor gelten für ihren Fall, gründen aber keinen
neuen.

**Die Wurzel:** Das erste Glied ist unsigniert und von einem Menschen
angelegt; eine Vertrauenswurzel kann sich nicht selbst begründen. Seine
Ordnung nennt die Wurzelrolle mit ihrem Fingerabdruck. Gebunden ist es
dadurch, dass jede Zeichnung ihr Glied pinnt und die Hashes verkettet sind:
Ein ausgetauschtes erstes Glied ändert jeden Hash danach, und jede
Lesestelle verweigert. Jedes spätere Glied zeichnet die Wurzelrolle (`A-Z1`)
mit dem Schlüssel, den die bis dahin geltende Spitze ihr gibt; auch ein
Wechsel ihres Schlüssels ist ein solches Glied, gezeichnet mit dem alten.

### 8. Die Wurzelrolle: der Vorstand

Die Rolle, die Zeichnungsrechte vergibt, ist der **Vorstand**
(`mensch/vorstand`). Im Unternehmen vergibt der Vorstand die Vollmachten und
beschließt die Übernahme eines Bestands; das sind die zwei Aufgaben der
Rolle. Die Kennung steht an einer Stelle (`models.ordnungslinie.WURZELROLLE`).
Die Rolle gehört zur Linie, nicht zum Fall, und hat kein Agenten-Gegenstück:
Ein Agent vergibt keine Zeichnungsrechte. Der Maintainer des Repositorys
gehört weiterhin nicht zum Rollenmodell (ADR-018); er spielt die Wurzel in
der Vorführung wie die anderen simulierten Rollen.

Die Wurzel kann innerhalb des eigenen Hauses jeder Rolle jedes Gate geben.
Deshalb hat sie Schranken:

* (a) Eine Ordnung mit Allzweck-Rolle (`gates: ["*"]`) ist nicht anhängbar.
  Der Lader liest den Stern weiter, damit alte Ordnungen lesbar bleiben.
* (b) Jedes Glied nennt gerechnet, was es ändert, und unterscheidet eine
  neue Rolle von einer Erweiterung einer bestehenden (`gates_erweitert`).
* (c) Die Wurzel trägt genau die Gates der Wurzel (`WURZEL_GATES`: die
  Ordnungsänderung `A-Z1` und den Fallauftrag `A-M6`), keine andere Rolle
  trägt eines davon, und ein Glied, das ihr eine fachliche Abnahme gibt, ist
  nicht anhängbar. Der Fallauftrag ist keine Abnahme; er setzt die Migration
  in Gang (ADR-026). Die Wurzel kann also beauftragen und erlauben, aber
  nicht abnehmen.
* (d) Die Ordnung der PLV führt nur Rollen der PLV. Eine Rolle des
  abgebenden Hauses (`mensch/quell-aktuar`) ist nicht anhängbar; ihre
  Vollmacht kommt von ihrem eigenen Haus und würde im Fallauftrag anerkannt,
  nicht verliehen (benannt, nicht gebaut).

**Grenze:** Dieselbe Rolle verwaltet die Vertrauenswurzel und beauftragt
den Fall. Der Schlüssel, der einen Fall beauftragt, kann also ändern, wer
dessen Abnahmen zeichnen darf. In der Vorführung mit einer Person ist das
vertretbar. Ein Haus mit getrennten Funktionen führte zwei Rollen; die
Gestalt der Linie lässt das ohne Umbau zu.

### 9. Rollen und Gegenstücke

| Rolle | Linie | Fall | Gegenstück | Gates |
|---|---|---|---|---|
| `mensch/rechenkern` | ja | ja | `agent/rechenkern` | A-K2 |
| `mensch/architektur` | ja | ja | `agent/architektur` | A-O1 |
| `mensch/aktuariat` | ja | ja | `agent/aktuariat` | A-Q1, A-M1 bis A-M4, A-T1 |
| `mensch/betrieb` | ja | ja | `agent/betrieb` | A-B1, A-B2, A-B3 |
| `mensch/programmleitung` | nein | ja | `agent/programmleitung` | A-M5 Fallabbruch, Recht aus dem Fallauftrag (ADR-026) |
| `mensch/quell-aktuar` | nein | ja | keins (Rolle des abgebenden Hauses) | keine |
| `mensch/vorstand` (Wurzelrolle) | ja | nein | keins (vergibt Rechte) | A-Z1, A-M6 Fallauftrag (ADR-026) |

Die Beschreibung des Betriebs-Agenten liegt unter `.claude/agents/betrieb.md`
und gleichlautend unter `.agents/`.

### 10. Regie-Modus

Simulierte Rollen (Schlüsselklasse `simulation`) zeichnen unter Mandat wie
bisher, auch im Linienbereich und als Wurzelrolle.

## Verworfene Alternativen

* **Keine erste Abnahme**, der Stand beim ersten Fall gilt ungezeichnet: Dann
  nimmt niemand die Änderungen vor dem ersten Fall ab.
* **Im ersten Fall zeichnen:** Die Änderungen stammen nicht aus dem Fall, und
  zwei der vier Gegenstände kommen dort gar nicht vor.
* **Ort im Repository oder unter `faelle/`:** siehe Abschnitt 2.
* **Gleichheit der Ordnungs-Hashes statt einer Linie:** entwertete bei jeder
  Erweiterung alle Belege.
* **Auch das erste Glied zeichnen:** Das Recht dieser Zeichnung müsste
  wieder außerhalb der Linie begründet werden.
* **Weg c behalten:** zwei Wege für denselben Sachverhalt.

## Folgen

* **Versionen:** P9-Schema 9 und Gate-Version 4.0.0 (ein vorher grüner
  A-M4-Entscheid wird ohne abgenommenes Tarifwerk rot); Schema 6 bis 8
  bleiben lesbar. Weil die Tarifpläne den Kernstand verlassen, ändert sich
  der Hash des lebenden Kernstands; frühere A-K2-Abnahmen nehmen ihn nicht
  mehr ab. Auch deshalb beginnt die Kette mit der Erstabnahme.
* **Betrieb:** Jede bestehende Ablage braucht vor dem nächsten Lauf die
  Abnahme ihres Anfangsbestands. Registrierung, Zugangsprobe und
  Neuaufsetzen nehmen `--linie`.
* **Tests:** Die gemeinsamen Helfer zeichnen das Tarifwerk mit
  (`zeichne_stand`) und legen Beleg, A-B3 und Bindung über die echten Wege an
  (`tests/anfangsbestand_testhelfer.py`).

## Bedienfolge: Erstabnahme durchführen

Je Rolle gilt: ansehen, dann zeichnen, mit dem Schlüssel der Rolle (64 Byte,
Rechte 0600, außerhalb des Repositorys), der Zeichnungsordnung außerhalb des
Linienbereichs und bei Schlüsselklasse `simulation` dem Mandat. Hat die
Linie mehr als ein Glied, liegt vor dem zeichnenden Schlüssel auch der des
Vorstands im Ring (`--freigabe-schluessel <vorstand.key>`), denn jede
Annahme liest die Linie mit ihm (Nachtrag Prüfrunde G). `--repo-root` ist
der Baum des Pakets, das rechnet. Verweigert das Gate mit Code `sicht`,
passt die Sicht nicht zur Vorlage: Vorlage mit demselben Kommando neu
erzeugen, ansehen, zeichnen. Endet ein Produzent mit Code `ein_ausgabe`,
denselben Aufruf nach Behebung der Ursache wiederholen.

1. **Schlüssel des Vorstands anlegen** (wie die anderen):
   `head -c 64 /dev/urandom > <schluessel>/vorstand.key && chmod 600
   <schluessel>/vorstand.key && sha256sum <schluessel>/vorstand.key`.
2. **Ordnung ergänzen:** `mensch/vorstand` mit seinem Fingerabdruck und
   `"gates": ["A-Z1"]`; `mensch/aktuariat` um `A-T1`, `mensch/betrieb` um
   `A-B3`. Keine Rolle mit `"*"`.
3. **Linienbereich anlegen und erstes Glied eintragen:**
   `python -m rechner_pipeline.gates.stand_belegen linie --linie linie`
   `python -m rechner_pipeline.gates.stand_belegen ordnung --linie linie
   --ordnung <ordnung> --vorgaenger keiner`; ansehen:
   `linie/abgeleitet/ordnung/linie.md`.
4. **Kernstand** (`mensch/rechenkern`): `python -m
   rechner_pipeline.gates.kernstand_belegen --linie linie --repo-root .
   --von <letzter abgenommener Stand, fuer die Erstabnahme ausdruecklich>
   --begruendung "Erstabnahme"`; ansehen `linie/abgeleitet/kern/aenderung.md`;
   zeichnen `python -m rechner_pipeline.gates.gate_entscheid --linie linie
   --gate A-K2 --entscheid angenommen --entscheider "<Rolle>" --begruendung
   "..." --repo-root . --zeichnungsordnung <ordnung> --freigabe-schluessel
   <rechenkern.key> [--mandat <mandat>]`.
5. **T-Box** (`mensch/architektur`): `python -m
   rechner_pipeline.gates.stand_belegen tbox --linie linie --repo-root .
   --artefakt docs/architektur/adr-024-tbox-020-tarifwerk-gevo-zustandsextrakt.md
   --begruendung "Erstabnahme"`; Stellungnahme des Aktuariats nach
   `linie/abgeleitet/tbox/stellungnahme.json`; ansehen
   `linie/abgeleitet/tbox/aenderung.md`; zeichnen wie oben mit `--gate A-O1`
   und dem Schlüssel von `mensch/architektur`.
6. **Tarifwerk** (`mensch/aktuariat`): `python -m
   rechner_pipeline.gates.tarifwerk_belegen --linie linie --repo-root .
   --von <...> --begruendung "Erstabnahme"`; ansehen
   `linie/abgeleitet/tarifwerk/aenderung.md`; zeichnen mit `--gate A-T1`
   und dem Schlüssel von `mensch/aktuariat`.
7. **Anfangsbestand** (`mensch/betrieb`), je Ablage nach dem Aufbaulauf,
   bei einer bestehenden Ablage auf ihrem geführten Stand:
   `python -m rechner_pipeline.betrieb.anfangsbestand belegen --stand
   <daten> --linie linie --schluessel <betrieb.key> --zeichnungsordnung
   <betriebsordnung>`; ansehen `linie/abgeleitet/anfangsbestand/beleg.md`;
   zeichnen mit `--gate A-B3` und dem Schlüssel von `mensch/betrieb`;
   binden `python -m rechner_pipeline.betrieb.anfangsbestand binden --stand
   <daten> --linie linie --freigabe-schluessel <betrieb-freigabe.key>
   --schluessel <betrieb.key> --zeichnungsordnung <betriebsordnung>`.
8. **Jeder Fall danach:** je unverändertem Gegenstand `python -m
   rechner_pipeline.gates.stand_belegen verweisen --fall <fall> --gate
   A-K2|A-O1|A-T1 --linie linie --repo-root .`; jeden Entscheid des Falls
   mit `--linie linie` zeichnen.
9. **Eine spätere Änderung der Ordnung: erst die Vorschau, dann anhängen**
   (Nachtrag Prüfrunde I, Punkt 2). Vorschau: `python -m
   rechner_pipeline.gates.stand_belegen ordnung --linie linie --ordnung
   <neue_ordnung> --vorgaenger <spitze> --vorschau`. Sie nennt die
   Änderungen, die geminderten Rollen und je Rolle die Folge von `gueltig`
   und `verfallen` (`summary.folgen`); sie schreibt und zeichnet nichts und
   braucht keinen Schlüssel. Dann anhängen:
   `python -m rechner_pipeline.gates.stand_belegen ordnung --linie linie
   --ordnung <neue_ordnung> --vorgaenger <spitze> --vorstand-schluessel
   <vorstand.key> [--fruehere-zeichnungen <rolle>=gueltig|verfallen ...]`.
   Die Erklärung ist Pflicht für jede geminderte Rolle. Ausgabe und Sicht
   `linie/abgeleitet/ordnung/linie.md` nennen danach dieselbe Folge wie die
   Vorschau. Nach einem Wechsel des Vorstandsschlüssels werden der alte und
   der neue genannt (`--vorstand-schluessel <alt.key> --vorstand-schluessel
   <neu.key>`, der zuletzt genannte zeichnet). Fehlt die Sicht nach einem
   Ausfall, zieht derselbe Aufruf sie nach (`summary.bereits_vorhanden`),
   ohne ein zweites Glied.

## Nachträge

Die Nachträge halten Regeln fest, die nach dem Beschluss hinzukamen, die
meisten nach Prüfrunden (G bis J). Die Rundenbezeichnung dient als Adresse,
unter der Code und Tests auf die Regel verweisen. Die ausführliche
Herleitung steht in der Geschichte dieser Datei.

## Nachtrag 2026-10-01: Die Linie ist Pflicht

Die Linie wirkte zunächst nur, wenn `--linie` übergeben wurde. Ohne sie
hielt der Leser die Rolle gegen die heutige Ordnung und prüfte den
Ordnungs-Hash gar nicht.

1. **Zeichnen:** `gate_entscheid` verlangt `--linie` in Fall und
   Linienbereich, für Annahme und Ablehnung, und zeichnet eine Annahme nur
   unter der Spitze. Dasselbe gilt für Fallauftrag und Fallabbruch
   (ADR-026); `fall_belegen auftrag --linie` ist Pflicht.
2. **Gründen:** `models.zeichnung.zeichnende_rolle_fehler` hat keinen Zweig
   ohne Linie; ihr Parameter `linie` hat keinen Default.
   `tests/test_linie_pflicht.py` legt die gründenden Leser abschließend
   fest: im Gate die
   Standabnahme (Wege a und b), der Fallauftrag und die Vorbedingungen von
   A-M4 und A-B2; im Betrieb der eine Leser (`uebernahme.zeichnende_rolle`).
3. **Altbestand:** Snapshots ohne Linie (Schema bis 8) bleiben zur Anzeige
   lesbar, begründen aber nichts Neues.
4. **Betrieb:** Die Kommandos, die auf einer Abnahme gründen oder eine
   binden, verlangen `--linie` ohne Default
   (`betrieb.tageslauf.KOMMANDOS_MIT_LINIE`: Registrierung, Zugangsprobe,
   Neuaufsetzen, Anfangsbestand). Der Nachtlauf gründet auf keinem Snapshot
   und braucht die Linie nicht (`KOMMANDOS_OHNE_LINIE`).
5. **Anker des Betriebsschlüssels:** `betrieb.anfangsbestand binden` löst
   unter der Linie auf, welchen Fingerabdruck die Spitze der Betriebsrolle
   gibt, und zeichnet ihn mit dem Glied in die Bindung
   (`betriebsschluessel_sha256`, `ordnungsglied_sha256`; Bindung Schema 2).
   Der Nachtlauf hält seinen Schlüssel gegen diese Zahl. Ein Wechsel des
   Betriebsschlüssels braucht deshalb ein Glied der Linie und eine neue
   Bindung. **Grenze:** Wer die Ablage samt Bindung mit einem eigenen
   Schlüssel neu zeichnet, bleibt für den Nachtlauf allein unsichtbar; den
   Bezug nach außen liefert der Anker beim Export (ADR-018, Nachtrag
   2026-09-30).
6. **Tests:** Die gemeinsamen Helfer legen für jeden Fall eine Linie an
   (`tests/zeichnung_fixture.linie_sicherstellen`).

**Prüfbarkeit von außen:** `linie/` ist nicht eingecheckt. Ein externer
Prüfer bekommt `linie/ordnung/` und `linie/linie.json` als Prüfpaket;
`models.ordnungslinie.lade_linie_strukturell_zur_anzeige` rechnet Kette,
Nummern und Änderungslisten ohne Schlüssel nach, `models.ordnungslinie.lade_linie`
zusätzlich die Signaturen, aber nur mit dem Schlüssel des Vorstands im Ring.

## Nachtrag 2026-10-01: Prüfrunde G — Linie, Verweis, lebender Stand

**1. Die Glieder werden gegen den Vorstand geprüft.** Keine Annahme, kein
Verweis, keine Registrierung und keine Bindung gründet auf einer Linie,
deren Glieder nicht gegen den Schlüssel des Vorstands geprüft sind.
`models.ordnungslinie.lade_linie` nimmt den Ring als Pflichtargument ohne
Default; jedes Glied nach dem ersten wird gegen den Schlüssel geprüft, den
die Spitze davor dem Vorstand gibt. Wer die Linie nur zeigt, liest sie über
`lade_linie_strukturell_zur_anzeige`; darauf gründet nichts. Eine Linie mit
nur dem ersten Glied braucht keinen Vorstandsschlüssel, ab dem zweiten ist
er Pflicht. Nach einem echten Schlüsselwechsel braucht der Leser beide
Schlüssel. Zugeführt wird er wie jeder andere Schlüssel als weiterer
`--freigabe-schluessel`, im Gate und in den vier Kommandos des Betriebs mit
`--linie`; der Nachtlauf bleibt ohne ihn.

**Grenze (HMAC):** Wer die Glieder prüfen kann, hält den Schlüssel des
Vorstands und kann damit auch Glieder zeichnen und Fälle beauftragen. Die
Prüfung schützt gegen jeden, der `linie/ordnung/` beschreiben kann, ohne
den Schlüssel zu halten. Ein asymmetrisches Verfahren würde das trennen; es
wäre eine neue Abhängigkeit und ein eigenes ADR.

**2. Verwiesen wird nur auf die geltende Abnahme.**
`stand_belegen verweisen --snapshot` entfällt, `--linie` ist Pflicht. Das
Gate prüft beim Lesen, dass der verwiesene Snapshot die geltende,
angenommene Spitze der Kette seines Gates in der Linie ist. Eine im Fall
gezeichnete Änderung gilt für den Fall; für den nächsten Fall wird der Stand
in der Linie abgenommen.

**3. Der lebende Stand ist der des Codes, der rechnet.** Jedes `--repo-root`
der Schicht `gates` geht durch `gates._provenienz.lebendes_repo`. Es
verlangt, dass `<repo_root>/src/rechner_pipeline` inhaltsgleich mit dem
ausgeführten Paket ist (derselbe Hash wie `quellcode_sha256`), sonst endet
der Aufruf mit beiden Hashes und einem Ausweg. Verlangt wird der Inhalt,
nicht der Ort; einen Schalter zum Abschalten gibt es nicht.
`tests/test_repo_root_lebendes_paket.py` legt die Kommandos abschließend
fest. **Grenze:**
Configs, Tarifpläne, Referenzwerte und Grundsatzdokumentation liest der
lebende Stand weiter aus `--repo-root`.

**4. Eine Version, ein Vokabular, auch in A-M4.** `standabnahme_pruefen`
ruft die Regel aus ADR-024 (dritter Nachtrag) für A-O1 gegen Fall und Linie
der Migrationsabnahme, in beiden Wegen.

**Versionen:** `stand_belegen` 4.0.0. P9 bleibt 5.0.0, Snapshot-Schema 10.

## Nachtrag 2026-10-01: Beleg und Sicht gehören zusammen (Runde G)

Fiel bisher das Schreiben der Sicht aus, lag die neue Vorlage neben der
alten Sicht, und das Gate zeichnete eine Vorlage, die der Mensch nie gesehen
hatte.

1. **Die Regel:** Gezeichnet wird nur eine Vorlage, deren Sicht am festen
   Ort byte-gleich die aus genau dieser Vorlage erzeugte ist. Das Gate
   erzeugt die Sicht beim Zeichnen einer Annahme aus den Belegen, die es
   pinnt, mit derselben Renderfunktion wie der Produzent neu
   (`gates.sichten.sicht_fehler`, eine Stelle in `gate_entscheid.main`) und
   vergleicht. Fehlt sie oder weicht sie ab, verweigert es mit Code `sicht`
   und dem Ausweg „Vorlage neu erzeugen, ansehen, zeichnen“. Eine Ablehnung
   braucht keine Sicht.
2. **Ein Register:** `gates.sichten.SICHTEN` nennt je Gate mit Sicht die
   Pflichtbelege, den Ort der Sicht, die Renderfunktion und den
   Produzenten; `tests/test_sicht_beleg_ausfall.py` legt es abschließend
   fest. Die
   Ordnungsänderung `A-Z1` steht nicht darin; ihre Sicht zieht
   `stand_belegen ordnung` für ein schon liegendes Glied nach.
3. **Schichten:** Die Renderfunktion des Anfangsbestands liegt beim Vertrag
   (`models.anfangsbestand.rendere_sicht`), weil `gates` nicht aus
   `betrieb` importieren darf.
4. **Archiv der T-Box:** `stand_belegen tbox` schreibt zuerst die
   Archivkopie, dann Beleg und Sicht. Das Gate zeichnet A-O1 nur, wenn die
   Archivkopie des gepinnten Belegs liegt und passt
   (`stand_belegen.tbox_archiv_fehler`, eine Prüfung für Produzent und
   Gate). Das zuletzt abgenommene Vokabular liefert die jüngste A-O1-Annahme
   des Bereichs.
5. **Alter Anfangsbestand:** `betrieb.anfangsbestand belegen` meldet „erste
   Abnahme“ nur, wenn es keine Ablage davor mit Bindung gab. Eine genannte,
   aber nicht lesbare oder nicht prüfbare Bindung ist ein benannter Fehler
   (Exit 2).
6. **Ausfälle:** Jeder Produzent, den das Register nennt, beendet einen
   Ein-/Ausgabefehler wie das Gate-Ledger (`gates._common.ein_ausgabe_benannt`):
   Exit 50, Code `ein_ausgabe`, Ausweg „denselben Aufruf wiederholen“, ohne
   Traceback. `stand_belegen linie` zählt eigene Schreibreste
   (`gates._common.ist_schreibrest`) nicht als Inhalt. Das Neuaufsetzen räumt
   seine Vorbereitung auch nach einem frühen Ausfall ab.

**Nicht gebaut:** Die übrigen Produzenten unter `gates/` (unter anderem
`abox_validate`, `extract`, `aktuartest`) antworten auf einen
Ein-/Ausgabefehler weiter mit Exit 50 und Traceback; sie legen keinen Beleg
vor, den ein Mensch über eine Sicht zeichnet.

## Nachtrag 2026-10-01: Prüfrunde H — Binden des Anfangsbestands, Schreibreste, Vorbereitung

1. **`binden` rechnet den ganzen Beleg nach.** Es liest den Beleg, den der
   A-B3-Snapshot pinnt, baut ihn auf den Bytes der Ablage mit denselben
   Funktionen wie `belegen` neu und hält jedes Feld dagegen. Weicht ein Feld
   ab, wird nicht gebunden (Exit 2, Felder genannt). Welche Felder
   nachgerechnet werden, steht im Vertrag
   (`models.anfangsbestand.BELEG_BEIM_BINDEN_NACHGERECHNET`, heute alle
   zwölf; `BELEG_BEIM_BINDEN_GEGLAUBT`, heute leer); ein Test hält die
   Vereinigung gegen `BELEG_FELDER`. `BINDUNG_SCHEMA_VERSION` 3.
2. **Schreibreste:** `belegen` schreibt unter der Sperre der Ablage und räumt
   vorher die Reste desselben Ziels (`tageslauf.raeume_schreibreste_von`).
3. **Vorbereitung des Neuaufsetzens:** Unter `tageslauf.lauf_sperre` wird
   eine Vorbereitung `<daten>.neu-*` neben der Ablage erkannt. Jeder Aufruf
   hält dann benannt an, auch der Tageslauf. Nur das Neuaufsetzen räumt
   seine eigene, nie veröffentlichte Vorbereitung ab. Was veröffentlicht
   gewesen sein könnte, bleibt liegen und verlangt eine Klärung von Hand.

**Grenzen:** Im Container sieht der Tageslauf nur `daten`, nicht dessen
Geschwister. Die Nachrechnung in `binden` fährt die Bestandswache ein
zweites Mal. Zwei Schreiber des Betriebs räumen ihre Reste nach einem
Prozessende noch nicht (`seite._schreibe`, `zugangsprobe._schreibe_beleg`);
ein Test führt sie als offen.

## Nachtrag 2026-10-01: Prüfrunde H, zweiter Nachtrag — Erklärung, T-Box-Sicht, Bytecode, Zwillinge

**1. Die Erklärung im Glied.** Ein Glied, das ein Recht mindert, sagt
gezeichnet, was mit den früheren Zeichnungen geschieht. Minderungen sind
`models.ordnungslinie.MINDERUNGSARTEN` (Rolle entfällt, Schlüssel wechselt,
Klasse wechselt, Gate entzogen); reine Erweiterungen sind
`ERWEITERUNGSARTEN`. Für jede geminderte Rolle trägt das Glied genau eine
Aussage, `fruehere_zeichnungen: {rolle: "gueltig" | "verfallen"}`. Fehlt
eine, ist das Glied nicht anhängbar und beim Laden ein Fehler; einen
Vorgabewert gibt es nicht. Der Produzent nimmt sie als
`--fruehere-zeichnungen <rolle>=gueltig|verfallen` und nennt in Ausgabe und
Sicht je Rolle die Folge.

Gelesen wird an einer Stelle (`models.ordnungslinie.damalige_ordnung` ->
`abloesung_fehler`, gerufen nur aus
`models.zeichnung.zeichnende_rolle_fehler`). `verfallen` entwertet die
Abnahmen der Rolle, gleich wann sie gezeichnet wurden. `gueltig` lässt eine
Abnahme gelten, wenn sie vor dem Eintrag des mindernden Glieds gezeichnet
wurde. Wie die Rolle über spätere Glieder verfolgt wird, regelt der
Nachtrag Prüfrunde I, Punkt 1. Die Erklärung wirkt auf Abnahmen
(P9-Snapshots), nie auf die Glieder selbst; die Kette prüft `lade_linie`
Glied für Glied. Steht in Frage, ob schon frühere Glieder gefälscht sind,
ist die Antwort eine neue Linie mit neuer Wurzel.

Zwei Beispiele: `gueltig` passt, wenn eine Rolle umbenannt oder ihr
Schlüssel geordnet gewechselt wird und der Halter derselbe bleibt.
`verfallen` passt, wenn einem Schlüssel nicht mehr getraut wird; dann sind
alle früheren Abnahmen der Rolle für die betroffenen Gates neu zu zeichnen.
Beim Vorstand heißt das: Jeder Fallauftrag fällt und mit ihm jede Abnahme
jedes Falls. Deshalb steht die Folge vor der Wahl in Ausgabe und Sicht.

Glied Schema 2. `eingetragen_am` ist ein Zeitpunkt mit Zeitzone und liegt
nicht vor dem des Vorgängers.

**Grenzen:** Es gibt keine vertrauenswürdige Zeit; `entschieden_am`
schreibt der zeichnende Prozess. Wer mit dem alten Schlüssel und
zurückgestellter Uhr zeichnet, ist bei `gueltig` von einer rechtmäßigen
früheren Zeichnung nicht zu unterscheiden; bei einem Schlüssel, dem nicht
mehr getraut wird, gehört `verfallen`. Das Gate unter einer veralteten
Kopie der Linie zeichnet weiter; gefangen wird beim Lesen durch jeden, der
die echte Linie hält. Gegen den Diebstahl des geltenden Wurzelschlüssels
schützt die Erklärung nicht.

**2. Die Grundlage der T-Box-Sicht rechnet das Gate.** Die
Vergleichsgrundlage der Sicht ist die zuletzt angenommene T-Box in Fall und
Linie des Gates. Das Gate rechnet sie beim Zeichnen von A-O1 selbst, mit
derselben Funktion wie der Produzent (`stand_belegen._vorher_tbox`), und
verweigert bei Abweichung mit Code `sicht`. Eingetragen ist das als
`grundlage` von A-O1 in `gates.sichten`.

**3. Der Bytecode gehört zum lebenden Stand.**
`gates._provenienz.lebendes_repo` verlangt (`bytecode_fehler`), dass jede
pyc im ausgeführten Paket, die der Interpreter laden würde, der Code ihrer
Quelle ist. Bytecode neben den Quellen ohne gleichnamige Quelle ist
ebenfalls ein Befund. Ausweg: die `__pycache__`-Verzeichnisse des Pakets
löschen. **Grenze:** Erweiterungsmodule, Import-Hooks, `sitecustomize` und
der Interpreter selbst liegen außerhalb; im Betrieb gilt das frisch gebaute
Image ohne beschreibbares `__pycache__`.

**4. Kein Hardlink-Zwilling bleibt liegen.** Wer einen Bereich betritt oder
ein Ziel als schon vorhanden erkennt, räumt dort die Zwillinge
(`gates._common.raeume_zwillinge`): beim Eintritt in `linie`, `ordnung/`,
das Archiv und `entscheide/`. `tests/test_schreibreste_zwillinge.py` legt
die Schreib- und Räumstellen abschließend fest.

**Versionen:** `stand_belegen` 5.0.0, Glied Schema 2. P9 bleibt 5.0.0,
Snapshot-Schema 10.

## Nachtrag 2026-10-01: Prüfrunde I — Erklärung je Linie, Vorschau, Uhr, Sperre

**1. Die Erklärung trifft die Linie einer Rolle.** Die eine Bestimmung ist
`models.ordnungslinie.treffer_der_erklaerungen`. Eine Abnahme wird vom
gepinnten Glied an über jedes spätere Glied der Linie des Lesers verfolgt,
und mit ihr die Linie der zeichnenden Rolle als zwei Mengen: ihre Namen und
ihre Schlüssel (`linie_fortschreiben`; die Mengen wachsen nur).

* (a) Erklärt ein Glied `verfallen` für eine geminderte Rolle, deren Name
  zur Linie gehört, ist die Abnahme entwertet, gleich wann und mit welchem
  Schlüssel der Linie sie gezeichnet wurde. Trifft die Minderung den
  Schlüssel (`entzieht_das_vertrauen`), fällt jede Abnahme der Linie; entzieht
  sie nur Gates, nur die Abnahmen dieser Gates.
* (b) `gueltig` an dem Glied, mit dem der Schlüssel sein Gate unter keinem
  Namen der Linie mehr trägt, verlangt, dass die Abnahme vor dessen Eintrag
  gezeichnet wurde. Eine reine Umbenennung lässt die Abnahme gelten.
* (c) Die Verfolgung endet nicht beim ersten Treffer.

Die Folge, die Ausgabe, Vorschau und Sicht nennen (`folge_der_erklaerung`),
kommt aus `getroffene_abnahmen` und fragt dieselbe Funktion wie der Leser.
Ein Test hält fest, dass nur `abloesung_fehler` und `getroffene_abnahmen` die
Bestimmung rufen; ein Eigenschaftstest prüft zufällige Linien gegen eine im
Test formulierte Fassung der Regel (`tests/test_ordnungslinie_rollenlinie.py`).
Die Linie einer Rolle umfasst alle früheren Namen und Schlüssel; ein
späteres `verfallen` trifft deshalb auch Abnahmen eines früheren,
vertrauenswürdigen Halters derselben Rolle. Das ist die sichere Richtung.

**2. Die Folge vor der Wahl: die Vorschau.** `stand_belegen ordnung
--vorschau` prüft dieselben Vorbedingungen wie das Anhängen
(`ordnungslinie.pruefe_anhang`), nennt Änderungen, geminderte Rollen,
fehlende Erklärungen und je Rolle die Folge von `gueltig` und `verfallen`.
Sie schreibt nichts, zeichnet nichts und braucht keinen Schlüssel.
**Grenze:** Die Vorschau liest die Linie ohne Signaturen; auf einer
gefälschten Linie zeigte sie eine falsche Folge, das anschließende Anhängen
liest mit dem Ring und verweigert.

**3. Ein Glied wird nicht später datiert als die Uhr des Aufrufs.**
`eingetragen_am` liegt zwischen dem Eintrag der Spitze und der Uhr des
Aufrufs (`pruefe_anhang`, Parameter `uhr` ohne Vorgabe; die Uhr liest
`stand_belegen.utc_now`). Eine Toleranz gibt es nicht.

**4. Eine Sperre, und je Nummer ein Glied.** Lesen der Spitze, Prüfen des
Vorgängers und Anhängen geschehen unter einer Sperre
(`stand_belegen.sperre_der_ordnung`, `linie/.ordnung.sperre`, mit `flock`
wie der Eingang eines Falls). Ein Glied heißt nach seiner Nummer,
`ordnung/<nummer:04d>.json` (`ordnungslinie.dateiname`); ein zweites Glied
derselben Nummer lässt sich nicht exklusiv ablegen.

**Gemessen, nicht gebaut** (gehört zu `gate_entscheid`): Zwei gleichzeitige
Annahmen desselben Gates im selben Bereich können zwei Snapshots mit
demselben Vorgänger ablegen; die Kette des Gates ist danach nicht lesbar.

**Versionen:** `stand_belegen` 6.0.0. Glied Schema 2 unverändert. P9 bleibt
5.0.0, Snapshot-Schema 10.

**Grenzen:** Es gibt weiter keine vertrauenswürdige Zeit. `verfallen` an
einem Glied, das nur Gates entzieht, trifft nur diese Gates. Entfällt eine
Rolle mit `gueltig` ganz, kann kein späteres Glied sie mindern; dann führt
der Weg über das Wiedereintragen des Namens und ein Entfernen mit
`verfallen`. Die Kontinuität über den Namen ist eine Annahme des Hauses. Die
Sperre wirkt zwischen Prozessen derselben Maschine.

## Nachtrag 2026-10-02: Prüfrunde J — die Folge nennt nur, was noch trägt

Eine Abnahme, die ein früheres Glied für verfallen erklärt hat, zählt in der
Folge keines späteren Glieds mehr (`getroffene_abnahmen`), gleich ob das
spätere Glied `gueltig` oder `verfallen` erklärt. Sie trägt nichts mehr, was
ihr genommen oder gelassen werden könnte. Ein eigener Test hält die Folge je
genanntem Glied gegen die Bestimmung des Lesers. Der Wortlaut der Folge
heißt jetzt „jeder so gezeichnete Fallauftrag (A-M6; unter den genannten
Gliedern, mit einem der genannten Schlüssel)“.

Die Leseregel hielt in dieser Runde gegen eine unabhängig formulierte Fassung
der Regel auf zufälligen Linien ohne Abweichung in der Wirkung.
