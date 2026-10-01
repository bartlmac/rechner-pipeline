# ADR-025: Erstabnahme des Zielsystems — vier Gegenstaende, vier Rollen, ein Ort ausserhalb des Falls

**Status:** angenommen 2026-10-01 (Entscheide des Maintainers im Dialog),
gebaut 2026-10-01. Die Zeichnungen selbst stehen aus: Die Erstabnahme ist
ein Akt der Rollen, nicht des Codes (Bedienfolge am Ende).

## Kontext

Seit dem Nachtrag 2026-10-01 zu ADR-018 verlangt `A-M4`, dass der Stand,
auf dem ein Fall rechnet, abgenommen ist: der Kernstand (`A-K2`,
`mensch/rechenkern`) und der T-Box-Stand (`A-O1`, `mensch/architektur`) —
im Fall gezeichnet (Weg a), per Verweis auf eine fruehere Abnahme (Weg b)
oder, nur fuer die T-Box, auf der Basislinie (Weg c). Der Befund des
Maintainers dazu, woertlich:

> "Zum Zeichnen der T-Box am Anfang des Falls — so richtig verstehe ich es
> nicht. Rechenkern muss ich nicht zeichnen, warum denn T-Box. Entweder gibt
> es eine Initialzeichnung an allen relevanten Zustaenden (Rechenkern,
> Tarifwerk — Aktuar, T-Box — Architekt, Bestand — Bestand) oder gar nicht.
> Sonst ist das inkonsistent."

Gemessen war die Lage so: Kern und T-Box mussten im ERSTEN Fall gezeichnet
werden, obwohl ihre Aenderungen nicht aus dem Fall stammten (der Kern ist
ausserhalb jedes Falls von 3.6.0 auf 3.16.0 gewachsen, die T-Box in der
Entwicklung auf 0.2.0); einen Ort fuer eine Abnahme ausserhalb eines Falls
gab es nicht (`gate_entscheid` verlangte `--fall`, ADR-018 nannte den "Ort
der Linien-Snapshots" offen). Das Tarifwerk der PLV hatte keine eigene
Abnahme — die Tarifplaene liefen im Kernstand mit und wurden von der
Rechenkern-Verantwortung gezeichnet, die Parametrierung der eigenen
Generationen in den Configs von niemandem. Der Anfangsbestand einer Ablage
hatte keine Abnahme; gezeichnet wurde nur jeder Zugang (`A-B2`) und die
Auslieferung (`A-B1`).

Auf den Vorschlag "eine Erstabnahme des Zielsystems, ausserhalb jedes
Falls; ein Fall zeichnet danach nur, was sich durch ihn aendert, und
verweist sonst auf die Erstabnahme" entschied der Maintainer: "ja, alle".
Zeitpunkt: vor dem Merge und vor dem naechsten Fall. Im selben Zug
entschied er drei Erweiterungen: Die Zeichnungsordnung bekommt eine
Versionslinie, bevor die Erstabnahmen gezeichnet werden; die Wurzel dieser
Linie verantwortet eine eigene Rolle; der Betriebs-Agent wird definiert,
damit jede fachliche Linienrolle ihr vorlegendes Gegenstueck hat.

## Entscheidung

### 1. Eine Regel, vier Gegenstaende (`models.standabnahme.GEGENSTAENDE`)

| Gegenstand | Gate | zeichnet | legt vor | Werkzeug (Beleg und Sicht) | verlangt von |
|---|---|---|---|---|---|
| Kernstand: Code des Rechenkerns, Referenzwerte, Grundsatzdokumentation | `A-K2.kernaenderung` | `mensch/rechenkern` | `agent/rechenkern` | `gates.kernstand_belegen` -> `abgeleitet/kern/aenderung.md` | A-M4 |
| T-Box-Stand | `A-O1.tbox-aenderung` | `mensch/architektur` | `agent/architektur` | `gates.stand_belegen tbox` -> `abgeleitet/tbox/aenderung.md` | A-M4 |
| Tarifwerk der PLV: Tarifplaene und Parametrierung der eigenen Tarifgenerationen | `A-T1.tarifwerk` (neu) | `mensch/aktuariat` | `agent/aktuariat` | `gates.tarifwerk_belegen` -> `abgeleitet/tarifwerk/aenderung.md` | A-M4 |
| Anfangsbestand einer Ablage | `A-B3.anfangsbestand` (neu) | `mensch/betrieb` | `agent/betrieb` | `betrieb.anfangsbestand belegen` -> `abgeleitet/anfangsbestand/beleg.md` | Betrieb |

Jedes Werkzeug zeigt die Aenderung gegenueber der zuletzt abgenommenen
Fassung als lesbare Sicht, deterministisch aus dem Beleg erzeugt: der Kern
je Modul mit den Commits des Zweigs; die T-Box als Vokabular-Diff gegen das
Vokabular des zuletzt abgenommenen Belegs (bei der Erstabnahme das ganze
Vokabular — fruehere Versionen sind nicht als Vokabular belegt); das
Tarifwerk je Tarifplan und je Tarifgeneration jeder Config, jedes geaenderte
Feld mit altem und neuem Wert, mit den Commits; der Anfangsbestand mit
Kennzahlen und, bei einem erneuten Aufsetzen, der Abweichung zum zuletzt
abgenommenen. Jedes Gate prueft mit der Rollenregel
(`models.zeichnung.zeichnende_rolle_fehler`). `tests/test_erstabnahme_linie.py`
haelt die Tabelle mit `==`.

### 2. Erstabnahme ausserhalb jedes Falls: der Linienbereich

Jede Rolle zeichnet ihren Gegenstand einmal im LINIENBEREICH; spaetere
Aenderungen in der Entwicklung zeichnet dieselbe Rolle ebenfalls dort. Je
Gegenstand entsteht eine Kette wie im Fall (Vorgaenger, geltende Spitze),
ueber dasselbe Entscheid-Kommando: `gate_entscheid --linie <linie>` ohne
`--fall`. Der Linienbereich verhaelt sich wie ein Fall (`entscheide/`,
`abgeleitet/`, Snapshot-Format, Signatur, Rollenregel, Kettenleser,
exklusives Schreiben, Idempotenz), hat aber keinen Eingang einer Migration:
Seine Kennzeichnung ist `linie.json` (Name, Zweck), seine Snapshots tragen
den Scope `linie` (`fall_scope`, P9-Schema 9) und binden `linie.json` statt
`eingang.json` und A-Box. Zeichenbar sind dort genau die vier Gegenstaende;
`A-B3` NUR dort (der Anfangsbestand gehoert einer Ablage, keinem Fall).

**Ort: ein neues Top-Level-Verzeichnis `linie/`, gitignored** (Vorgabe:
`stand_belegen linie --linie linie`). Begruendung: Die Snapshots tragen den
Namen des Entscheiders, Schluessel-Fingerabdruecke und Mandats-Hashes einer
konkreten Installation — Klarnamen und installationsgebundenes Material
gehoeren nicht in ein oeffentliches Repository; dieselbe Regel wie fuer
`faelle/`. Nicht unter `faelle/`, weil der Linienbereich kein Fall ist und
dort jede Aufzaehlung der Faelle verfaelschte (gemessen: `ontologie.impact`
zaehlt `faelle/*/abgeleitet/abox/abox.json`, die Werkzeuge nehmen den Fall
ausdruecklich; ein Bereich ohne A-Box fiele heute nicht auf, eine kuenftige
Aufzaehlung ueber `faelle/*` aber schon). Eingecheckt sind nur Code,
Vertraege und diese Dokumentation; die Zeichnungen nicht. **Schutz:**
mindestens derselbe wie `faelle/<fall>/entscheide/` — `entscheide/` und
`ordnung/` sind nur-anfuegbar (Snapshots und Glieder werden exklusiv
geschrieben, nie ueberschrieben; derselbe Entscheid ist idempotent; die
Kette pinnt jeden Vorgaenger), kein Kommando loescht dort, und die
Ratschen ueber das Lesen von `entscheide/` im Betrieb gelten
unveraendert, weil der Betrieb den Linienbereich nur ueber den einen
Leser `uebernahme.lies_abnahme_snapshot` liest. Die Erstabnahmen sind die
am haeufigsten referenzierten Zeichnungen des Systems — jeder kuenftige
Fall verweist darauf; ihre Sicherung gehoert in die Sicherung der
Installation wie die der Faelle.

*Verworfen:* eingecheckt im Repository (Klarnamen, installationsgebunden,
und ein Repository-Stand, der seine eigene Abnahme traegt, belegte sich
selbst); ein Bereich unter `faelle/` (verfaelscht Aufzaehlungen, ist kein
Fall); ein zweites Zeichnungswerkzeug (zwei Regeln fuer dieselbe Sache).

### 3. Ein Fall zeichnet nur, was sich durch ihn aendert

A-M4 verlangt in beiden Scopes Kernstand, T-Box-Stand UND Tarifwerk
(Pflichtrollen `kernstand`, `tboxstand`, `tarifwerkstand`). Ist ein
Gegenstand gegenueber seiner geltenden Abnahme unveraendert, verweist der
Fall darauf: `stand_belegen verweisen --fall <fall> --gate <gate> --linie
<linie>` legt die vollstaendige Kopie der geltenden Spitze der Linie an
den festen Ort im Fall; A-M4 prueft Signatur, Rolle, Klasse und haelt den
Stand per `==` gegen den lebenden — "keine Aenderung seit Abnahme
<snapshot> (Linie <name>, ...)". Der Fall bleibt in sich pruefbar.
Aendert der Fall einen Gegenstand (etwa eine T-Box-Erweiterung, die der Fall
erzwingt), zeichnet die zustaendige Rolle im Fall (Weg a). Eine Kette im
Fall geht jedem Verweis vor.

**Weg (c) entfaellt.** Die Basislinie der T-Box ersetzte deren erste
Abnahme; die gibt es jetzt. Gemessen: Seit T-Box 0.2.0 hat die
Versionslinie zwei Elemente, Weg (c) griff real nicht mehr; ein Leser
braucht ihn noch — ein A-M4-Snapshot nach Schema 8, der ihn fuehrt, bleibt
ein gueltiges Glied seiner Kette. Er ist deshalb fuer Schema 8 lesbar
(`WEGE_LESBAR`), nicht mehr erzeugbar.

### 4. Das Tarifwerk der PLV (`models.tarifwerkabnahme`)

Gegenstand, einmal bestimmt (`TARIFWERK`): `docs/tarifplaene/*` und je
eigener Generation (Knoten `<familie>/plv_<...>`) jeder Config unter
`configs/*.toml` alle Felder des `[[generation]]`-Blocks AUSSER
`NICHT_TARIFWERK` (Neuzugang, Trend, Verteilungen, Korrelationen,
Nummernkreis), samt Tarifzellen und Tarifwerks-Schaltern. **Die Grenze:**
Die Erfahrungsannahmen und die Simulation der Vorfuehrung (`[annahmen]`,
`[plausibilitaet]`, `[tagesbetrieb]`, Neugeschaeftsvolumen, Verteilungen)
sagen, wie sich die simulierte Welt verhaelt, nicht, was ein Vertrag
verspricht — kein Vertragswert aendert sich mit ihnen; der Nummernkreis ist
Identitaet der Policen (Betrieb); uebernommene Generationen tragen das
Tarifwerk des abgebenden Hauses und werden im Fall abgenommen. Die Auswahl
ist eine Ausnahmeliste: Ein neues Feld gehoert zum Tarifwerk, bis jemand
begruendet, dass es Erfahrung ist — eine vergessene Einordnung faellt als
Abnahme auf, nicht als stille Luecke. Die Tarifplaene verlassen dafuer den
Kernstand (`models.kernabnahme.KERNSTAND`; Schema des Kern-Belegs 4).

### 5. Der Anfangsbestand (`models.anfangsbestand`, `betrieb.anfangsbestand`)

Abgenommen wird der GEFUEHRTE Stand einer Ablage nach ihrem Aufbaulauf:
Hash je Tabelle des Stands, Config, Code-Stand (Kern-Version, Paket-Hash,
Image), gefuehrter Stand (`tageslauf.ablage_stand`), registrierte
Eingaenge, ein NEU gefahrener Befund der Bestandswache P-B1 auf genau diesen
Bytes (Voraussetzung: gruen), Kennzahlen zur Ansicht. Der Beleg entsteht im
Linienbereich, `mensch/betrieb` zeichnet `A-B3` dort; das Gate prueft Form,
Urteil und innere Ableitungen (es sieht die Ablage nicht). Die Bindung liegt
IN DER ABLAGE (`anfangsbestand.json` neben `configs/`, wie
`zugangsabnahme.json` neben dem Eingang), geschrieben von `binden`: Es liest
den A-B3-Snapshot ueber den einen Leser des Betriebs (Kette, Signatur,
Rollenregel), haelt seinen Stand per `==` gegen den lebenden Anfangsbestand
der Ablage und zeichnet die Bindung mit dem Betriebsschluessel — der
Tageslauf kennt die Linie nicht und haelt keinen Freigabeschluessel.

**Wann verlangt.** Das Neuaufsetzen bereitet vor (es nennt die Schritte);
der Aufbaulauf (erster Lauf einer Ablage ohne gruene Zeile) laeuft ohne
Abnahme — er erzeugt erst, was abgenommen wird; jeder weitere Lauf verlangt
die gezeichnete Bindung, deren Stand eine gruene Zeile DIESER Ablage ist,
sonst Exit 2 mit roter Protokollzeile und Ausweg. **Bestehende Ablagen ohne
Bindung** sind ein benannter Zustand: Sie laufen nicht weiter, bis der
Betrieb ihren gefuehrten Stand nachtraeglich als Anfangsbestand abnimmt
(dieselben drei Kommandos). Das trifft jede produktive Ablage beim ersten
Lauf nach dem Einspielen — gewollt, kein stiller Durchlass. **Zugang:** Eine
Zugangsprobe faehrt den Tageslauf auf einer Kopie der Ablage; traegt die
Ablage gruene Zeilen, verlangt dieser Lauf die Bindung (die Kopie traegt
sie mit) — eine A-B2 entsteht so nur auf einer Ablage, deren Anfangsbestand
abgenommen ist. Auf einer LEEREN Ablage (Neuaufsetzen) wird der Zugang Teil
des Anfangsbestands und mit ihm abgenommen.

*Annahme (benannt):* Der Beleg des Anfangsbestands traegt keine eigene
Betriebszeichnung — die A-B3-Signatur pinnt seinen Hash, und `binden`
rechnet den Stand gegen die Ablage nach.

### 6. Namen nach ADR-012

`A-T1.tarifwerk`: Art A, ein neuer Gegenstand `T` (das Tarifwerk), Nummer 1
— das Tarifwerk ist weder Rechenkern (`K`) noch Vokabular (`O`) noch eine
Quelle (`Q`). `A-B3.anfangsbestand`: Gegenstand `B`, naechste freie Nummer.
`A-Z1.ordnungsaenderung`: Gegenstand `Z` (die Zeichnungsordnung), Nummer 1
— die Zeichnung eines Glieds der Ordnungslinie (Abschnitt 7), kein
P9-Snapshot und deshalb nicht in `GUELTIGE_GATES`, aber eine Gate-Kennung,
die eine Ordnung vergeben kann (`ZEICHENBARE_GATES`). Der kuenftige
Fallauftrag (eigener Block) bekommt einen eigenen Namen; `A-M5` ist fuer
den Fallabbruch vorgesehen (dev-docs/offene-punkte.md).

### 7. Die Versionslinie der Zeichnungsordnung (`models.ordnungslinie`)

Jeder Snapshot pinnt `zeichnung.ordnung_sha256`, aber nirgends stand, welche
Ordnungsstaende es je gab; die Rollenregel hielt eine fruehere Abnahme gegen
die HEUTIGE Ordnung, ihren Ordnungs-Hash gegen nichts. Ein
Gleichheitsvergleich waere die falsche Reparatur gewesen: Die Ordnung
aendert sich oefter, als gezeichnet wird, jede Erweiterung entwertete alle
Belege.

**Die Linie** liegt im Linienbereich unter `ordnung/`, je Glied eine Datei
`<nummer>-<glied_sha256>.json`, angehaengt, nie umgeschrieben (exklusiv
geschrieben), hash-verkettet. Ein Glied traegt Nummer, Vorgaenger (Hash des
Glieds davor), den SHA-256 der Ordnungsdatei und ihren INHALT Byte fuer
Byte (Rollen mit Klasse, Fingerabdruck und Gates — keine Geheimnisse),
die aus beiden Staenden GERECHNETE Aenderungsliste (`neue_rolle`,
`rolle_entfallen`, `gates_erweitert`, `gates_entzogen`,
`schluessel_gewechselt`, `klasse_geaendert`; beim Lesen nachgerechnet, nie
behauptet), einen injizierten Zeitpunkt, den Eintragsvermerk und die
Zeichnung. Beispiel (gekuerzt):

```
{"schema_version": 1, "art": "ordnungsglied", "nummer": 2,
 "vorgaenger": "<glied_sha256 von Glied 1>",
 "ordnung_sha256": "<sha256 der Ordnungsdatei>", "ordnung_text": "{...}",
 "aenderungen": [{"art": "gates_erweitert", "rolle": "mensch/architektur",
                  "gates": ["A-K2"]}],
 "eingetragen_am": "2026-10-01T09:00:00+00:00",
 "eintrag": {"art": "anhang", "vermerk": "gezeichnet von ... (A-Z1) ..."},
 "zeichnung": {"gate": "A-Z1", "rolle": "mensch/vorstand", "schluesselklasse": "mensch",
               "schluessel_sha256": "<laut Glied 1>", "verfahren": "hmac-sha256-v1",
               "signatur": "..."},
 "glied_sha256": "..."}
```

**Zeichnen:** Mit `--linie` zeichnet `gate_entscheid` nur unter einer
Ordnung, die die SPITZE der Linie ist (sonst Verweigerung mit dem Ausweg
"Ordnung in die Linie eintragen"), und die Zeichnung pinnt das GLIED
(`zeichnung.ordnungsglied_sha256`, P9-Schema 9). Im Linienbereich ist die
Linie Pflicht. **Lesen:** Wer eine Abnahme liest, um darauf zu gruenden
(Vorbedingungen von A-M4, Soll der Zugangsprobe in A-B2, Standabnahme Weg a
und b im Gate; im Betrieb der eine Leser, ueber `ordnungslinie` von
`lies_abnahme_snapshot`), lokalisiert das gepinnte Glied und haelt Rolle,
Klasse und Gate-Berechtigung gegen DESSEN Ordnung — "wer durfte damals
zeichnen". Eine spaetere Erweiterung entwertet nichts; ein spaeterer Entzug
wirkt nicht zurueck. Das aendert die Konvention aus ADR-022 (Nachtrag
2026-10-01, "massgeblich ist die Ordnung zum Zeitpunkt der Registrierung")
nicht im Ergebnis, macht sie aber PRUEFBAR: massgeblich ist der Stand der
Ordnung, unter dem gezeichnet wurde, und der ist jetzt auffindbar. Ein
Snapshot ohne lokalisierbares Glied wird benannt verweigert. Ohne `--linie`
(Tests, alte Faelle) gilt der bisherige Weg — die Ordnung des Aufrufs —,
und die Ausgabe sagt es (`ordnungslinie: keine — bisheriger Weg`).

**Der Schnitt** ist ein Entscheid, kein Verlust: Die Linie beginnt mit der
Ordnung der Erstabnahme. Davor existieren gezeichnete Abnahmen
abgeschlossener Faelle — im zweiten Baldrian-Lauf 30 Snapshots unter drei
abgeloesten Ordnungsstaenden, darunter 16 im alten Schema unter einer
Ordnung mit Allzweck-Rolle. Sie gelten fuer IHREN Fall (abgeschlossene
Faelle bleiben auf ihrem Stand, ADR-011) und sind als Grundlage eines neuen
Falls nicht verwendbar. Die Hashes der betriebenen Ordnung stehen in keiner
eingecheckten Datei.

**Die Wurzel.** Wer an die Linie anhaengen darf, bestimmt, wer kuenftig
zeichnen darf. Verlangte das ERSTE Glied eine Signatur, kaeme das Recht des
Signierenden aus der Linie selbst — eine Vertrauenswurzel kann sich nicht
selbst begruenden. Das erste Glied ist deshalb ausdruecklich unsigniert und
menschlich angelegt (das Glied sagt es woertlich, dieselbe Haltung wie die
benannte Regressions-Ausnahme von A-K2); seine Ordnung benennt die
Wurzelrolle mit ihrem Fingerabdruck. Gebunden ist es nicht durch eine
Signatur, sondern dadurch, dass jede Zeichnung das Glied pinnt: Die
Glied-Hashes sind verkettet, ein ausgetauschtes erstes Glied (anderer
Inhalt, gleiche Form) aendert jeden Hash danach, und jede Lesestelle
verweigert. Jedes SPAETERE Glied zeichnet die Wurzelrolle (`A-Z1`) mit dem
Schluessel, den die bis dahin geltende Spitze ihr gibt — auch ein Wechsel
ihres Schluessels ist ein solches Glied, gezeichnet vom alten; ohne diese
Zeichnung ist ein Glied nicht anhaengbar.

### 8. Die Wurzelrolle: der Vorstand

Die Versionslinie braucht eine Instanz, die Zeichnungsrechte vergibt. Im
Unternehmen ist das der **Vorstand** (`mensch/vorstand`, Anzeige
"Vorstand"; Entscheid des Maintainers 2026-10-01): In einem Versicherer
vergibt der Vorstand die Vollmachten und beschliesst die Uebernahme eines
Bestands — genau die zwei Aufgaben der Rolle (die Zeichnungsordnung
verantworten; kuenftig den Fall beauftragen, eigener Block). Die Kennung
steht an genau einer Stelle (`models.ordnungslinie.WURZELROLLE`); Leser,
Tests und Texte beziehen sie von dort.

Damit bleibt der Satz aus ADR-018 wahr — "Nicht Teil des Rollenmodells ist
der Maintainer dieses Repos; er gehoert zur Entwicklungsumgebung des
Werkzeugs, nicht zum Unternehmen" — und wird nicht umgekehrt: Die Wurzel ist
eine Rolle des Unternehmens, kein Nachfolger des Allzweck-Platzhalters; der
Maintainer des Repos spielt sie im Regie-Modus wie die anderen simulierten
Rollen. Sie ist eine Rolle der LINIE (Tabelle Linie/Fall in ADR-018: Linie
ja, Fall nein). Sie hat KEIN Agenten-Gegenstueck: Ein Agent vergibt keine
Zeichnungsrechte — wer vorschlaegt, wer zeichnen darf, und es dann selbst
einrichtet, hat die Trennung zwischen Vorlage und Zeichnung aufgehoben.

**Ihre Macht, beschrieben statt gezaehlt.** Die Wurzelrolle ist die
Vertrauenswurzel. Ihre Gates sind wenige (`A-Z1`); ihre Wirkung ist
unbegrenzt INNERHALB DES EIGENEN HAUSES — mit einem Glied der Linie kann sie
jeder Rolle der PLV jedes Gate geben — und endet an der Hausgrenze: Eine
fremde Vollmacht (der Aktuar des abgebenden Hauses) wird im Fallauftrag
ANERKANNT, nicht verliehen. Eine Wurzel, die fremde Vollmachten verleihen
koennte, waere ein Konstruktionsfehler. Das ist mehr, als der abgeschaffte
Platzhalter konnte (der alles zeichnen, aber niemandem etwas erlauben
konnte), und deshalb hat sie Schranken (gebaut):

* (a) Eine Ordnung mit Allzweck-Rolle (`gates: ["*"]`) ist nicht
  anhaengbar — unter der Linie zeichnet niemand mit Stern. Der Lader
  (`lade_zeichnungsordnung`) liest den Stern weiter, damit alte Ordnungen
  lesbar bleiben: Der offene Punkt ist fuer die Linie geschlossen, fuer den
  Lader bleibt er Lesefaehigkeit des Altbestands.
* (b) Jedes Glied benennt lesbar und GERECHNET, was es gegenueber dem
  Vorgaenger aendert, und unterscheidet eine neue Rolle von einer stillen
  Verbreiterung einer bestehenden (`gates_erweitert`); eine behauptete
  Liste bricht die Linie.
* (c) Die Wurzel kann Vollmachten vergeben, aber keine fachliche an sich
  selbst: Sie traegt genau die Gates der Wurzel (`WURZEL_GATES`, an einer
  Stelle benannt: die Ordnungsaenderung `A-Z1` und, seit ADR-026, den
  Fallauftrag `A-M6`; `A-Z1` immer), keine andere Rolle traegt eines davon,
  und ein Glied, das ihr eine fachliche Abnahme gibt, ist nicht anhaengbar.
  Der Fallauftrag ist keine Abnahme: Er bezeugt nichts ueber einen
  Gegenstand, er setzt die Migration in Gang (ADR-026, Abschnitt 6). Das ist
  die Trennung, die den Rest tragbar macht — sonst koennte sie beauftragen,
  erlauben und abnehmen in einer Hand; so kann sie beauftragen und erlauben,
  aber nicht abnehmen.
* (d) Die Ordnung der PLV fuehrt nur Rollen der PLV: Eine Rolle des
  abgebenden Hauses (`mensch/quell-aktuar`) ist in einem Glied nicht
  anhaengbar (benannte Meldung). Gemessen: Sie zeichnet heute kein Gate, hat
  keinen Schluessel und steht in keiner Ordnung. Ihre Vollmacht kaeme von
  ihrem eigenen Haus; sollte sie kuenftig etwas zeichnen, benennt sie das
  abgebende Haus in der Lieferung, und der Fallauftrag der PLV haelt die
  Benennung fest — die PLV erkennt sie an, sie verleiht sie nicht (nicht
  gebaut, nur benannt).

**Gewaltenteilung, als Grenze benannt.** Dieselbe Rolle verwaltet die
Vertrauenswurzel (administrativ) und beauftragt den Fall (fachlich; gebaut mit
ADR-026, Gate `A-M6`). Der Schluessel, der einen Fall beauftragt, kann damit aendern,
wer dessen Abnahmen zeichnen darf. Hier ist das vertretbar: eine Person,
Vorfuehrung, kein Vier-Augen-Umfeld — eine Trennung, die mit einer Person
nur Schein waere, wird nicht gebaut. Ein Haus mit getrennten Funktionen
fuehrte zwei Rollen statt einer (eine fuer die Ordnung, eine fuer den
Auftrag); die Gestalt der Linie laesst das ohne Umbau zu.

### 9. Rollen und Gegenstuecke

| Rolle | Linie | Fall | Gegenstueck | Gates |
|---|---|---|---|---|
| `mensch/rechenkern` | ja | ja | `agent/rechenkern` | A-K2 |
| `mensch/architektur` | ja | ja | `agent/architektur` | A-O1 |
| `mensch/aktuariat` | ja | ja | `agent/aktuariat` | A-T1, A-M1 bis A-M4 |
| `mensch/betrieb` | ja | ja | `agent/betrieb` (neu definiert) | A-B1, A-B2, A-B3 |
| `mensch/programmleitung` | nein | ja | `agent/programmleitung` | A-M5 Fallabbruch, Recht aus dem Fallauftrag (ADR-026) |
| `mensch/quell-aktuar` | nein | ja | keins (Rolle des abgebenden Hauses) | keine (Vollmacht vom eigenen Haus, Abschnitt 8 d) |
| `mensch/vorstand` (Vorstand, Wurzelrolle) | ja | nein | keins (vergibt Rechte) | A-Z1, A-M6 Fallauftrag (ADR-026) |

Mit `.claude/agents/betrieb.md` (byte-gleich unter `.agents/`) hat jede
fachliche Linienrolle ihr vorlegendes Gegenstueck; ohne Gegenstueck bleiben
begruendet der Vorstand und `mensch/quell-aktuar`.

### 10. Regie-Modus

Simulierte Rollen (Schluesselklasse `simulation`) zeichnen unter Mandat wie
bisher, auch im Linienbereich und als Wurzelrolle; nichts Neues.

## Verworfene Alternativen

* **Gar keine Initialzeichnung: der Stand beim ersten Fall gilt
  ungezeichnet.** Verworfen, weil dann niemand die Aenderungen vor dem
  ersten Fall abnimmt — der Kern waere mit neun Minor-Versionen ohne
  Abnahme in die Produktion gegangen, das Tarifwerk nie.
* **Im ersten Fall zeichnen** (der Stand bis hierher). Verworfen, weil die
  Aenderungen nicht aus dem Fall stammen und zwei der vier Gegenstaende
  dort gar nicht vorkommen (das Tarifwerk der eigenen Generationen, der
  Anfangsbestand einer Ablage).
* **Ort im Repository eingecheckt** und **Ort unter `faelle/`**: siehe
  Abschnitt 2.
* **Hash-Gleichheit der Ordnung statt einer Linie**: entwertete bei jeder
  Erweiterung alle Belege (Abschnitt 7).
* **Jedes Glied der Linie mit eigener Rolle gezeichnet, auch das erste**:
  das Recht dieser Rolle muesste dann ebenfalls ausserhalb der Linie
  begruendet werden — die Wurzel verschoebe sich nur.
* **Die Basislinie (Weg c) behalten**: sie ersetzte eine Abnahme, die es
  jetzt gibt; zwei Wege fuer denselben Sachverhalt sind zwei Regeln.

## Folgen

* **Versionen:** P9-Schema 9 und Gate-Version 4.0.0 (Major: ein vorher
  gruener A-M4-Entscheid wird ohne abgenommenes Tarifwerk rot); Schema 6
  bis 8 bleiben lesbar. T-Box-Aenderungsbeleg Schema 2 (mit Vokabular),
  Kern-Aenderungsbeleg Schema 4 (ohne Tarifplaene), `stand_belegen` 2.0.0,
  neu `tarifwerk_belegen` 1.0.0, Beleg und Bindung des Anfangsbestands
  Schema 1, Glied der Ordnungslinie Schema 1. Der lebende Kernstand
  (`kernstand_sha256`) aendert sich, weil die Tarifplaene ihn verlassen:
  Fruehere A-K2-Abnahmen nehmen nicht mehr den heutigen Stand ab — auch
  deshalb beginnt die Kette mit der Erstabnahme.
* **Betrieb:** Jede bestehende Ablage braucht vor dem naechsten Lauf ihre
  Abnahme des Anfangsbestands. `tageslauf.SCHREIBZIELE` fuehrt die Bindung.
* **Tests:** Die gemeinsamen Helfer zeichnen das Tarifwerk mit
  (`zeichne_stand`); eine sessionweite Naht legt Beleg, A-B3 und Bindung
  ueber die echten Wege an (`tests/anfangsbestand_testhelfer.py`); wer eine
  Linie anlegt (`linie_anlegen`), zeichnet und liest ueber
  `annahme_args` unter ihrer Ordnungslinie — die uebrigen Wege der Suite
  laufen benannt ohne Linie.
* **Betrieb:** Registrierung, Zugangsprobe und Neuaufsetzen nehmen
  `--linie` (der Zeichner des Betriebs laedt die Ordnungslinie, der eine
  Leser haelt jede Abnahme gegen den damaligen Stand); ohne `--linie` der
  bisherige Weg. Ob die Linie dort Pflicht wird, entscheidet der Betrieb
  mit dem ersten Fall nach der Erstabnahme.
* **Erledigt (ADR-026):** der Fallauftrag als Gate am Anfang des Falls
  (`A-M6`) und der Fallabbruch (`A-M5`).

## Bedienfolge: Erstabnahme durchfuehren

Je Rolle "ansehen, zeichnen" — mit dem Schluessel der Rolle (64 Byte, 0600,
ausserhalb des Repos), der Zeichnungsordnung ausserhalb des Linienbereichs
und bei Schluesselklasse `simulation` dem Mandat. Hat die Linie mehr als ein
Glied, steht vor dem zeichnenden Schluessel auch der des Vorstands im Ring
(`--freigabe-schluessel <vorstand.key>`): Jede Annahme liest die Linie mit
ihm (Nachtrag Pruefrunde G). `--repo-root` ist der Baum des Pakets, das
rechnet (Nachtrag Pruefrunde G).
Gezeichnet wird nur, was
angesehen werden konnte (Nachtrag "Beleg und Sicht" unten): Verweigert das
Gate mit Code `sicht`, ist die Sicht nicht die aus der Vorlage erzeugte —
die Vorlage mit demselben Kommando neu erzeugen, erneut ansehen, dann
zeichnen. Endet ein Produzent mit Code `ein_ausgabe`, denselben Aufruf nach
Behebung der Ursache wiederholen; er liefert den Zustand des ungestoerten
Laufs.

1. **Schluessel des Vorstands anlegen** (wie die anderen):
   `head -c 64 /dev/urandom > <schluessel>/vorstand.key && chmod 600
   <schluessel>/vorstand.key && sha256sum <schluessel>/vorstand.key`.
2. **Ordnung ergaenzen:** `mensch/vorstand` mit seinem Fingerabdruck und
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
   und dem Schluessel von `mensch/architektur`.
6. **Tarifwerk** (`mensch/aktuariat`): `python -m
   rechner_pipeline.gates.tarifwerk_belegen --linie linie --repo-root .
   --von <...> --begruendung "Erstabnahme"`; ansehen
   `linie/abgeleitet/tarifwerk/aenderung.md`; zeichnen mit `--gate A-T1`
   und dem Schluessel von `mensch/aktuariat`.
7. **Anfangsbestand** (`mensch/betrieb`), je Ablage nach dem Aufbaulauf
   (bei einer bestehenden Ablage: jetzt, auf ihrem gefuehrten Stand):
   `python -m rechner_pipeline.betrieb.anfangsbestand belegen --stand
   <daten> --linie linie --schluessel <betrieb.key> --zeichnungsordnung
   <betriebsordnung>`; ansehen `linie/abgeleitet/anfangsbestand/beleg.md`;
   zeichnen mit `--gate A-B3` und dem Schluessel von `mensch/betrieb`;
   binden `python -m rechner_pipeline.betrieb.anfangsbestand binden --stand
   <daten> --linie linie --freigabe-schluessel <betrieb-freigabe.key>
   --schluessel <betrieb.key> --zeichnungsordnung <betriebsordnung>
   [--ordnungslinie]`.
8. **Jeder Fall danach:** je unveraendertem Gegenstand `python -m
   rechner_pipeline.gates.stand_belegen verweisen --fall <fall> --gate
   A-K2|A-O1|A-T1 --linie linie --repo-root .`; jeden Entscheid des Falls
   mit `--linie linie` zeichnen.
9. **Eine Ordnungsaenderung spaeter:** `... stand_belegen ordnung --linie
   linie --ordnung <neue ordnung> --vorgaenger <glied_sha256 der Spitze>
   --vorstand-schluessel <vorstand.key>`; ansehen, was sich aendert:
   `linie/abgeleitet/ordnung/linie.md`. Nach einem Wechsel des
   Vorstandsschluessels werden der alte UND der neue genannt
   (`--vorstand-schluessel <alt.key> --vorstand-schluessel <neu.key>`, der
   zuletzt genannte zeichnet): Der Produzent liest die Linie mit beiden. Fehlt die Sicht nach einem Ausfall,
   zieht derselbe Aufruf sie nach (`summary.bereits_vorhanden`), ohne ein
   zweites Glied.

## Nachtrag 2026-10-01: Die Linie ist Pflicht

**Befund.** Mit diesem ADR wirkte die Versionslinie nur, wenn `--linie`
uebergeben wurde: `gate_entscheid` nahm sie mit `default=None`, ohne sie
galt "benannt der bisherige Weg" — die Rolle wurde gegen die HEUTIGE
Ordnung des Lesers gehalten, der `ordnung_sha256` des Snapshots gegen
nichts. 27 Test-Wege liefen so, im Betrieb war `--linie` optional; die
gruene Suite bezeugte ueberwiegend den Zustand OHNE Wurzel. Das ist
woertlich das Loch, das dieses Repo am 2026-09-16 schon einmal geschlossen
hat (`dev-docs/offene-punkte.md`: "`summary.manifest` von OPTIONAL auf
PFLICHT gestellt — das war das eigentliche Loch: Jede Aussage, die nur im
Manifest steht, liess sich durch Weglassen von `--manifest` abschalten").
Eine Wurzel, die man weglassen kann, ist keine.

**Entscheid.**

1. **Zeichnen.** Kein Entscheid ohne Linie: `gate_entscheid` verlangt
   `--linie` (Fall und Linienbereich, Annahme und Ablehnung) und zeichnet
   eine Annahme nur unter der Spitze; ohne Linie Verweigerung mit Ausweg
   ("Linienbereich anlegen, Ordnung eintragen", Bedienfolge oben). Dasselbe
   fuer Fallauftrag und Fallabbruch (ADR-026); die Vorlage des Auftrags
   verweist auf die Abnahmen der Linie (`fall_belegen auftrag --linie`,
   Pflicht).
2. **Gruenden.** Die Regel `models.zeichnung.zeichnende_rolle_fehler` hat
   keinen Zweig ohne Linie mehr: Ihr Parameter `linie` hat keinen Default,
   und ohne Linie (None oder leer) begruendet eine Abnahme nichts. Die
   gruendenden Leser sind gemessen und gehalten (`tests/test_linie_pflicht.py`,
   `==`): im Gate die Standabnahme (Wege a und b), der Fallauftrag und die
   Vorbedingungen von A-M4 und A-B2; im Betrieb der eine Leser
   (`uebernahme.zeichnende_rolle`), durch den Registrierung, Zugangsprobe
   (`lies_soll`), Neuaufsetzen und die Bindung des Anfangsbestands gehen.
   Deren Parameter `ordnungslinie` hat ebenfalls keinen Default.
3. **Altbestand.** Snapshots, die ohne Linie entstanden (Schema bis 8,
   abgeschlossene Faelle), bleiben fuer ihre ANZEIGE lesbar (Fallbericht,
   Falldaten, Seite: `pruefe_snapshot_ohne_schluessel`,
   `uebernahme.zeichnung_aus_snapshot`), begruenden aber nichts Neues — der
   Schnitt aus Abschnitt 7. Die anzeigenden Werkzeuge rufen die Regel nicht
   (Ratsche).
4. **Betrieb.** Die Kommandos, die auf einer Abnahme gruenden oder eine
   binden, verlangen `--linie` ohne Default
   (`betrieb.tageslauf.KOMMANDOS_MIT_LINIE`: Registrierung, Zugangsprobe,
   Neuaufsetzen, Anfangsbestand). Der Nachtlauf nicht
   (`KOMMANDOS_OHNE_LINIE`, mit der Seite): Er zeichnet Protokollzeilen und
   haelt beim Eintritt nur die betriebsgezeichneten Saetze der
   Registrierung; er gruendet auf keinem Snapshot. Den Ort erfaehrt der
   Betrieb nur ueber den ausdruecklichen Schalter (`--linie
   ~/apps/plv/linie`, `deploy/plv/README.md`); eine Umgebungsvorgabe waere
   wieder ein Schalter, der fehlen kann.
5. **Der Anker des Betriebsschluessels.** Der Nachtlauf haelt seine Rolle
   gegen die Ordnungsdatei, die ihm uebergeben wird; wer sie austauscht,
   tauscht die Rolle. `betrieb.anfangsbestand binden` loest deshalb UNTER der
   Linie einmal auf, welchen Fingerabdruck die Spitze der Betriebsrolle gibt
   (verweigert, wenn die Ordnungsdatei des Betriebs einen anderen nennt), und
   zeichnet ihn mit dem Glied in die Bindung (`betriebsschluessel_sha256`,
   `ordnungsglied_sha256`; Bindung Schema 2). Der Nachtlauf haelt seinen
   Schluessel gegen diese gezeichnete Zahl. Gemessen: Ein Lauf mit
   ausgetauschter Ordnungsdatei und anderem Schluessel hielt schon vorher an
   — die Protokollkette und die Bindung sind mit dem alten Schluessel
   gezeichnet. Der Anker macht daraus eine benannte Aussage, die an der
   Linie haengt, und faengt die ausgetauschte Ordnungsdatei schon beim
   Binden. **Grenze:** Wer die Ablage samt Bindung mit einem eigenen
   Schluessel neu zeichnet, bleibt fuer den Nachtlauf allein unsichtbar; den
   Bezug nach aussen liefert der Anker beim Export (Nachtrag 2026-09-30 zu
   ADR-018). **Folge:** Ein Wechsel des Betriebsschluessels braucht ein Glied
   der Linie UND eine neue Bindung; Bindungen nach Schema 1 werden neu
   gebunden.
6. **Tests.** Die gemeinsamen Helfer legen fuer jeden Fall eine Linie an
   (`tests/zeichnung_fixture.linie_sicherstellen`: das erste Glied ist die
   Ordnung des Betriebs der Suite, die Ordnung des Falls haengt der Vorstand
   an); der Normalweg der Suite ist der mit Wurzel. Tests, die das Verhalten
   ohne Linie pruefen, pruefen die Verweigerung.

**Pruefbarkeit von aussen, als Grenze benannt.** `linie/` ist nicht
eingecheckt (Entscheidernamen, installationsgebundene Fingerabdruecke —
Abschnitt 2). Ein externer Gutachter sieht die Vertrauenswurzel einer
Installation deshalb nicht im Repository, nur ihre Hashes in den Snapshots
(`zeichnung.ordnung_sha256`, `zeichnung.ordnungsglied_sha256`). Das ist eine
Aussage ueber die Pruefbarkeit, nicht ueber die Datenhygiene. Der Weg, sie
ihm vorzulegen: das Verzeichnis `linie/ordnung/` (die Glieder, mit den
Ordnungen im Klartext und ohne Geheimnisse) und `linie/linie.json` als
Pruefpaket; `models.ordnungslinie.lade_linie_strukturell_zur_anzeige`
rechnet Hash-Kette, Nummern und Aenderungslisten ohne Schluessel nach,
`models.ordnungslinie.lade_linie` dazu die Signaturen der Glieder — nur mit
dem Schluessel des Vorstands im Ring (HMAC; ohne ihn verweigert sie ab dem
zweiten Glied, Nachtrag Pruefrunde G); jeder Snapshot der Installation
laesst sich damit in der Linie lokalisieren.

*Verworfen:* **die Linie optional lassen** ("ohne Linie der bisherige Weg,
benannt"). Benannt ist nicht erzwungen: Jede Lesestelle mit einem Zweig
ohne Linie macht die Wurzel durch Weglassen abschaltbar, und die Suite
bezeugte genau diesen Zweig. Dieselbe Abwaegung wie am 2026-09-16 beim
Manifest.

## Nachtrag 2026-10-01: Pruefrunde G — die Linie wird mit dem Schluessel des Vorstands gelesen, verwiesen wird nur auf die geltende Abnahme, gerechnet wird der Stand des Codes, der rechnet

Befunde der blinden Pruefrunde G (Linse "Abnahme-Beleg"), bestaetigt vom
Widerleger; gebaut nach den Entscheiden des Maintainers.

**1. Die Glieder der Linie werden gegen den Vorstand geprueft (G09, hoch).**
`lade_linie` pruefte die Signatur eines Glieds nur, wenn ihr ein Ring
uebergeben wurde — und kein gruendender Leser uebergab einen, auch das Gate
nicht, das den Schluessel des Vorstands fuer jede Annahme im Fall ohnehin
haelt (der Fallauftrag wird damit geprueft, ADR-026). Gemessen: Ein Glied
mit richtigem Fingerabdruck und geratener Signatur wurde Spitze; darunter
vergab sich ein fremder Schluessel die Rolle `mensch/rechenkern`, zeichnete
A-K2, und A-M4 nahm an. Abschnitt 7 ("ohne diese Zeichnung ist ein Glied
nicht anhaengbar") galt nur fuer den Produzenten, nicht fuer die Leser.

*Regel.* Keine Annahme, kein Verweis, keine Registrierung und keine Bindung
gruendet auf einer Linie, deren Glieder nicht gegen den Schluessel des
Vorstands geprueft sind. `models.ordnungslinie.lade_linie` nimmt den Ring als
Pflichtargument ohne Default (`ring=None` ist ein Fehler); jedes Glied nach
dem ersten wird gegen den Schluessel geprueft, den die Spitze davor dem
Vorstand gibt; liegt er nicht im Ring, ist die Linie nicht verwendbar — eine
benannte Verweigerung mit Ausweg, kein "ohne Ring nur Form". Wer die Linie
nur ZEIGT, liest sie ueber den benannten zweiten Einstieg
`lade_linie_strukturell_zur_anzeige` (Form, Kette, gerechnete
Aenderungslisten, Fingerabdruck und Klasse der Zeichnung — keine Signatur);
darauf gruendet nichts. Die gruendenden Leser sind gemessen und gehalten
(`tests/test_linie_pflicht.py`, `==`): das Gate (jede Annahme), der
Produzent eines Glieds (`stand_belegen ordnung`), der Zeichner des Betriebs
(Registrierung, Zugangsprobe, Neuaufsetzen) und die Bindung des
Anfangsbestands. Den strukturellen Einstieg nutzt nur die Ablehnung im Gate:
Sie zeichnet nichts und gruendet nichts, die Linie steht nur in ihrer
Ausgabe.

*Was das fuer die Wurzel heisst.* Eine Linie mit genau einem Glied hat nichts
zu pruefen: Die Wurzel ist unsigniert (Abschnitt 7), ihr Inhalt ist durch die
Glied-Pins der Zeichnungen gebunden, nicht durch eine Signatur. Solange die
Linie nur die Wurzel traegt, braucht kein Leser den Vorstandsschluessel —
und eine ausgetauschte Wurzel faellt weiter nur ueber die Pins auf. Ab dem
zweiten Glied ist der Schluessel Pflicht, auch im Linienbereich.

*Ein Glied, das den Vorstand selbst austauscht* (vom Pruefer abgeleitet,
nicht gemessen; jetzt gemessen): Das gefaelschte Glied gibt der Wurzelrolle
einen fremden Schluessel, jedes Glied danach zeichnet der Faelscher "richtig".
Gefangen wird es am gefaelschten Glied — seine Signatur prueft der Schluessel
des alten Vorstands, den der Ring traegt; den Faelscherschluessel im Ring zu
halten, aendert daran nichts. Nach einem echten Schluesselwechsel braucht der
Leser beide Schluessel: den alten fuer die Glieder bis zum Wechsel, den
neuen danach (`stand_belegen ordnung --vorstand-schluessel` ist dafuer
wiederholbar, der zuletzt genannte zeichnet).

*Zufuehrung.* Auf demselben Weg wie jeder andere Schluessel, den ein Leser
zum Pruefen braucht: als weiterer `--freigabe-schluessel` — im Gate (im Fall
lag er schon im Ring, im Linienbereich wird er Pflicht, sobald die Linie mehr
als ein Glied hat) und in den vier Kommandos des Betriebs mit `--linie`
(Registrierung, Zugangsprobe, Neuaufsetzen, `anfangsbestand binden`). Der
Nachtlauf braucht die Linie nicht (`tageslauf.KOMMANDOS_OHNE_LINIE`) und
bleibt ohne Vorstandsschluessel. Bedienfolge: `deploy/plv/README.md`.

*Verworfen:* **die Signatur nur pruefen, wenn der Schluessel zufaellig im
Ring liegt** (der Stand vorher) — ein Default, der beim Weglassen still auf
"nur Form" faellt, ist das Loch vom 2026-09-16 noch einmal. **Ein eigener
Schalter `--vorstand-schluessel` an jedem Leser** — zwei Wege fuer dieselbe
Sache; der Ring ist die eine Stelle, an der ein Leser Schluessel bekommt.
**Ein asymmetrisches Verfahren fuer die Glieder** (Pruefen ohne
Zeichenrecht): richtig, aber eine neue Abhaengigkeit und ein eigener ADR;
bis dahin gilt die Grenze unten.

**Grenze (HMAC), benannt.** Wer die Glieder pruefen kann, haelt den
Schluessel des Vorstands — und kann damit auch Glieder zeichnen und Faelle
beauftragen. Die Pruefung schuetzt gegen jeden, der `linie/ordnung/`
beschreiben kann, ohne den Schluessel zu halten; sie schuetzt nicht gegen
einen Leser, der ihn haelt. Dieselbe Grenze wie bei A-M4 und den
Standabnahmen (ADR-018) und beim Fallauftrag (ADR-026), hier mit dem
Wurzelschluessel: Er liegt jetzt in mehr Ringen als vorher (in jedem Ring des
Betriebs, der eine Linie mit zwei Gliedern liest). Ein externer Gutachter
ohne den Schluessel liest die Linie mit dem strukturellen Einstieg und
bekommt Form, Kette und Fingerabdruecke, nicht die Signaturen
("Pruefbarkeit von aussen" oben).

**2. Weg (b) verweist nur auf die GELTENDE Abnahme der Linie (G11).** Der
Verweis wurde auf Echtheit geprueft (Signatur, Rolle, Stand), nicht auf
Gueltigkeit: Ein Verweis auf eine Erstabnahme, die in der Linie inzwischen
durch eine Ablehnung (oder eine neuere Annahme) abgeloest ist, trug A-M4;
`verweisen --snapshot <datei>` nahm jeden frueheren Snapshot, auch den eines
anderen Falls.

*Regel.* (1) `stand_belegen verweisen --snapshot` entfaellt; der Aufruf
verweigert sprechend und nennt den Weg (wie die entfallenen Tarifschalter).
`--linie` ist Pflicht. (2) Das Gate (`standabnahme_pruefen`, Weg b) haelt
beim Lesen nach, dass der verwiesene Snapshot die geltende, angenommene Spitze
der Kette seines Gates in der Linie ist, die das Gate bekommt — gelesen mit
Signaturpruefung, ueber denselben Kettenleser wie jede Kette im Fall. Eine im
Fall gezeichnete Aenderung (Weg a) gilt fuer den Fall; fuer den naechsten
Fall wird der Stand in der Linie abgenommen. Dieselbe Invariante
"Gueltigkeit, nicht nur Echtheit" haelt der Betrieb schon
(`betrieb.uebernahme`, Pruefrunde T27 Befund 05).

*Verworfen:* **Verweis auf den Snapshot eines frueheren Falls** (der Weg
`--snapshot`): Seine Herkunftskette ist vom Gate aus nicht pruefbar — das
Gate bekommt die Linie, nicht den frueheren Fall; ob dort eine Ablehnung oder
ein Abbruch folgte, sieht es nicht. **Die Kette des frueheren Falls
mitliefern**: verschoebe die Frage nur (welcher Fall, welche Kette, wer
haelt sie) und machte den Fall zum Gegenstand fremder Abnahmen.

**3. Der lebende Stand ist der des Codes, der rechnet (G12).** Der lebende
Stand von Kern (A-K2) und Tarifwerk (A-T1) wurde aus den Dateien unter
`--repo-root` gerechnet, Commit und `dirty` des Systemstands ebenfalls — das
Paket, das rechnete, kam ueber `PYTHONPATH` von woanders. Gemessen: Klon mit
verdoppeltem Stornoabzug ausgefuehrt, `--repo-root` auf das Original, A-M4
"keine Aenderung seit Abnahme". A-O1 nahm schon das importierte Modul.

*Regel.* EINE Stelle, durch die jeder Pfad muss: `--repo-root` wird in jedem
Kommando der Schicht gates ueber `gates._provenienz.lebendes_repo` aufgeloest
(der `type` des Arguments; auch ein Wert aus `--request-json` geht durch ihn).
Sie verlangt, dass `<repo_root>/src/rechner_pipeline` INHALTSGLEICH mit dem
ausgefuehrten Paket ist (derselbe Hash wie `quellcode_sha256` im
Systemstand), sonst Aufruffehler mit beiden Hashes und dem Ausweg. Verlangt
wird der Inhalt, nicht der Ort — ein nicht editierbar installiertes Paket
neben seinem Repo bleibt moeglich. Kein Schalter zum Abschalten. Die
Kommandos sind gemessen und gehalten (`tests/test_repo_root_lebendes_paket.py`,
`==`); `ontologie.landkarte` und `ontologie.impact` lesen den Baum als
Gegenstand (eine Karte des Codes, der dort liegt) und weisen keinen Stand
aus — benannte Ausnahmen.

*Grenze, benannt.* Gehalten wird das Paket. Was der lebende Stand ausserhalb
des Pakets liest — Configs und Tarifplaene (A-T1), Referenzwerte und
Grundsatzdokumentation (A-K2) —, liest er weiter aus `--repo-root`.

*Verworfen:* **den lebenden Stand aus dem importierten Paket rechnen statt aus
`--repo-root`** — fuer Code moeglich, fuer Configs, Referenzwerte und die
Commit-Angaben nicht; die zwei Quellen fielen nur anders auseinander. **Ein
Schalter fuer Tests mit fremdem Repo** — eine Regel mit Schalter ist keine;
die eine Probe, die ein fremdes Repo braucht, bekommt eine inhaltsgleiche
Kopie des Pakets.

**4. Eine Version, ein Vokabular — auch in A-M4 (G13, Teil 1).** Die Regel
(ADR-024, dritter Nachtrag) lief nur beim Zeichnen von A-O1, gegen die
Bereiche DIESES Zeichnens. Unter einer Kopie der Linie ohne Entscheide
(dieselben Glieder, also lokalisierbar) zeichnete ein Fall A-O1 mit einem
zweiten Vokabular unter der in der Linie abgenommenen Version, und A-M4 mit
der echten Linie nahm an. Jetzt ruft `standabnahme_pruefen` die Regel fuer
A-O1 gegen Fall UND die Linie, die A-M4 bekommt, in beiden Wegen.

**Versionen.** `stand_belegen` 4.0.0 (Major: `verweisen --snapshot` und ein
fremder `--repo-root` waren gruen). Die Gate-Version P9 bleibt 5.0.0 und das
Snapshot-Schema 10: Die Gestalt des Snapshots aendert sich nicht, und unter
5.0.0 ist noch nichts gezeichnet. Die uebrigen Kommandos mit `--repo-root`
behalten ihre Versionen: Rot wird nur ein Aufruf, dessen Stand nie der des
rechnenden Codes war.

## Nachtrag 2026-10-01: Beleg und Sicht gehoeren zusammen (Runde G)

**Befund** (blinde Pruefrunde G, Linse "Ausfaelle an den Schreibstellen").
Jeder Produzent eines Belegs, den ein Mensch zeichnet, schrieb erst den
Beleg bzw. die Vorlage und danach die lesbare Sicht. Fiel das Schreiben der
Sicht aus (volle Platte), lag die neue Vorlage neben der alten Sicht, und das
Gate zeichnete die neue Vorlage, die der Mensch nie gesehen hatte. Gemessen
fuer A-K2, A-O1, A-T1, A-B3 (die Sicht zeigte eine andere Ablage) und fuer
Fallauftrag und Fallabbruch (ADR-026; die Sicht nannte eine andere
Programmleitung als die, die das Recht auf den Abbruch bekam). Kein Gate
pinnte oder pruefte die Sicht. Vier Nachbarn derselben Linse: (a) fehlte die
Archivkopie des T-Box-Belegs, nahm das Gate A-O1 trotzdem an, und die
naechste Vorlage behauptete still "Erstabnahme"; (b) eine vorhandene, aber
nicht lesbare oder nicht pruefbare Bindung des alten Anfangsbestands wurde
zu "erste Abnahme dieser Ablage" mit Exit 0; (c) ein Schreibrest von
`linie.json` sperrte die Wiederholung von `stand_belegen linie`; (d) ein
Ein-/Ausgabefehler bei der Provenienz oder der ersten Umbenennung liess die
Vorbereitung `daten.neu-<zeit>` des Neuaufsetzens ungenannt liegen. Die
Produzenten unter `gates/` antworteten auf einen Ein-/Ausgabefehler mit
Exit 50 und Traceback.

**Entscheid.**

1. **Die Invariante:** Gezeichnet wird nur eine Vorlage, deren Sicht am
   festen Ort byte-gleich die aus genau dieser Vorlage erzeugte ist
   (Abschnitt 1: "deterministisch aus dem Beleg erzeugt"; ADR-026: erst
   ansehen, dann zeichnen). EINE Regel im Gate beim Zeichnen einer Annahme
   (`gates.sichten.sicht_fehler`, eine Stelle in `gate_entscheid.main`, nach
   allen Vorbedingungen, die die Pins bestimmen): Das Gate erzeugt die Sicht
   aus den Belegen, die es pinnt, mit derselben Renderfunktion wie der
   Produzent neu — aus den Bytes seiner EINEN Lesung, die den Pin ergab
   (Review T23-01: eine Datei, deren Hash im Beleg steht, wird genau einmal
   gelesen; die Pruefer der Belege reichen die geparsten Belege dafuer
   durch) — und vergleicht sie mit der Datei am festen Ort; fehlt sie
   oder weicht sie ab, verweigert es mit Code `sicht` und dem Ausweg
   "Vorlage neu erzeugen, ansehen, zeichnen". Die Regel faengt beide
   Richtungen (Beleg neu und Sicht alt, Sicht neu und Beleg alt) und die
   fehlende Sicht; die Schreibreihenfolge im Produzenten ist unerheblich.
   Eine Ablehnung zeichnet nichts ab und braucht keine Sicht. Die
   Produzenten erzeugen die Sicht aus den Bytes, die sie schreiben, nicht
   aus dem Objekt davor — derselbe Weg wie das Gate.
2. **Ein Register an einer Stelle** (`gates.sichten.SICHTEN`): je Gate mit
   Sicht die Pflichtbelege (Rolle, fester Ort), der Ort der Sicht, die
   Renderfunktion, der Produzent; A-O1 dazu die Archivpruefung. Die Ratsche
   haelt es mit `==` gegen die Menge der Gates, deren Produzent eine Sicht
   schreibt (Tabelle der Gegenstaende und die Vorlagen des Lebenslaufs), und
   gegen jede Konstante `*SICHT_RELATIV` des Pakets
   (`tests/test_sicht_beleg_ausfall.py`). Die Ordnungsaenderung A-Z1 steht
   nicht darin: Sie ist kein Gate dieses Kommandos, der Vorstand zeichnet das
   Glied im Produzenten; ihre Sicht zieht derselbe Aufruf fuer das schon
   liegende Glied nach (`stand_belegen ordnung`, `summary.bereits_vorhanden`),
   statt mit "Vorgaenger ist nicht die Spitze" zu enden.
3. **Schichten.** Die Renderfunktion des Anfangsbestands wohnt beim Vertrag
   (`models.anfangsbestand.rendere_sicht`): `gates` darf `betrieb` nicht
   importieren, beide erreichen `models`, keine neue Kante. Sie braucht nichts
   als den Beleg; dieselbe Art Funktion steht dort schon
   (`anzeige_bindung`).
4. **Das Archiv der T-Box.** `stand_belegen tbox` schreibt die Archivkopie
   ZUERST, dann Beleg und Sicht: Was am festen Ort gezeichnet werden kann,
   hat seine Archivkopie, und ein Ausfall am Archiv bewegt nichts. Das Gate
   zeichnet A-O1 nur, wenn die Archivkopie des gepinnten Belegs liegt und zum
   Pin passt (`stand_belegen.tbox_archiv_fehler`, EINE Pruefung fuer
   Produzent und Gate). Das zuletzt abgenommene Vokabular liefert die
   juengste A-O1-ANNAHME des Bereichs (eine Ablehnung als Spitze aendert
   nichts daran); "es gibt keine Annahme" ist der einzige Weg zu
   "Erstabnahme". Fehlt ihr gepinnter Beleg im Archiv, passt er nicht zum Pin
   oder fuehrt er kein Vokabular, verweigert der Produzent benannt mit dem
   Ausweg "die gepinnte Fassung im Archiv wiederherstellen" (liegt sie noch
   am festen Ort, sagt die Meldung das). Gate-Version von `stand_belegen`:
   4.0.0 (ein vorher gruener Aufruf wird rot).
5. **Der alte Anfangsbestand.** `betrieb.anfangsbestand belegen` sagt "erste
   Abnahme" nur, wenn es keine Ablage davor gab (keine Provenienz, oder sie
   nennt kein Archiv) oder keine Ablage der Kette davor eine Bindung traegt
   (eine archivierte Ablage ohne Bindung hatte hoechstens ihren Aufbaulauf;
   dann gilt die Bindung ihrer Vorgaengerin). Eine Provenienz, ein Archiv oder
   eine Bindung, die genannt bzw. da, aber nicht lesbar oder nicht pruefbar
   ist, ist ein benannter Fehler mit Ausweg (Exit 2).
6. **Ausfaelle sind benannt und wiederholbar.** Jeder Produzent unter
   `gates/`, den das Register nennt, beendet einen Ein-/Ausgabefehler wie das
   Gate-Ledger (`gates._common.ein_ausgabe_benannt`, derselbe Weg wie
   `_ledger_write_failure`): Exit 50, Code `ein_ausgabe`, Ausweg "denselben
   Aufruf wiederholen", kein Traceback. `stand_belegen linie` zaehlt den
   eigenen Schreibrest von `linie.json` (`gates._common.ist_schreibrest`)
   nicht als Inhalt. Das Neuaufsetzen raeumt seine Vorbereitung auch bei
   einem Ausfall an der Provenienz oder der ersten Umbenennung ab (die alte
   Ablage liegt dann an ihrem Ort; die Identitaet der Vorbereitung steht
   fest, weil dieser Aufruf sie unter einem vorher nicht existierenden
   Namen angelegt hat) und nennt den Rest, wo das nicht geht.

*Verworfen:* (i) **die Sicht als weiteren Pflichtbeleg pinnen** — das bindet
die alte Sicht an den Snapshot, prueft aber nicht, dass sie zur Vorlage
gehoert; der Fund bliebe bestehen, nur gezeichnet. (ii) **nur die
Schreibreihenfolge drehen** (Sicht vor Beleg) — das schliesst eine Richtung;
ein Ausfall am Beleg liesse dann die neue Sicht neben der alten Vorlage
stehen. (iii) Fuer das Archiv: **das Gate schreibt die Archivkopie beim
Zeichnen selbst** — ein Gate schreibt Snapshot und Ledger, keine Belege
eines Produzenten; ein Ausfall an dieser Stelle waere ein neuer halber
Zustand im Gate, und die Archivkopie entstuende aus Bytes, deren Ablage der
Produzent nicht bezeugt hat. Gewaehlt: Produzent schreibt zuerst, Gate
prueft.

*Nicht gebaut, benannt:* Die anderen Produzenten unter `gates/`, die in
`main` schreiben (unter anderem `abox_validate`, `extract`, `aktuartest`,
`bestand_uebernehmen`, `transformation_anwenden`, `verankerung_belegen`,
`fuehrungsprobe`), antworten auf einen Ein-/Ausgabefehler weiterhin ueber
`run_command` mit Exit 50 und Traceback; sie legen keinen Beleg vor, den
ein Mensch ueber eine Sicht zeichnet.
