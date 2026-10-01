# ADR-026: Lebenslauf eines Falls — Fallauftrag und Fallabbruch

**Status:** angenommen 2026-10-01 (Entscheid des Maintainers), gebaut
2026-10-01, vor dem Merge.

## Kontext

Die Frage des Maintainers, woertlich:

> "Noch Frage: wer beauftragt einen Fall ...? Startet ja der Orchestrator
> Programmleiter, aber jemand muss es beauftragen und dem Programmleiter den
> Auftrag geben und das kann nur ein Mensch sein (Auftrag zeichnen)."

Gemessen war die Lage so: Ein Fall entstand, indem jemand ihn anlegte
(`fall anlegen`, ADR-002), und der Programmleitungs-Agent fuhr ihn durch die
Stufen. Niemand beauftragte den Fall mit einer Zeichnung. Die Rolle
`mensch/programmleitung` war nach ADR-018 eine Fall-Rolle ("entsteht mit
einem Fall und endet mit ihm"), hatte aber kein Gate und keinen Ort, aus dem
ihr Recht kam — die Ordnung der Linie (ADR-025) fuehrt Rollen des Hauses,
nicht Rollen eines Falls. Und ein Fall, der scheitert, verlief im Sande:
"Abbruchkriterium" hiess im Agenten und im Skill nur, dass der Agent anhaelt
(`dev-docs/offene-punkte.md`, `A-M5.fallabbruch`, Entscheid 2026-09-16).

Auf den Vorschlag "Fallauftrag als Abnahmepunkt am Anfang des Falls,
gezeichnet von der Wurzelrolle; jeder weitere Abnahmepunkt setzt ihn voraus;
das Gegenstueck am Ende ist der gezeichnete Fallabbruch" entschied der
Maintainer: "Ja beides vor dem merge, das sind wichtige Voraussetzungen fuer
einen sauberen Lauf." Die Wurzelrolle heisst `mensch/vorstand`.

## Entscheidung

### 1. Ein Fall beginnt mit dem Auftrag und endet mit Abnahme oder Abbruch

| Gate | Wann | zeichnet | Recht aus | Vorlage (Produzent) |
|---|---|---|---|---|
| `A-M6.fallauftrag` | am Anfang, nach der Registrierung der Lieferung | `mensch/vorstand` | der Ordnung der Linie (Gates der Wurzel) | `gates.fall_belegen auftrag` -> `abgeleitet/auftrag/fallauftrag.json` |
| `A-M5.fallabbruch` | jederzeit vor der Migrationsabnahme | `mensch/programmleitung` | dem Fallauftrag | `gates.fall_belegen abbruch` -> `abgeleitet/abbruch/fallabbruch.json` |

Beide sind Art `A` (ein Mensch entscheidet), Gegenstand `M` (die Migration
als Ganzes): Der Auftrag beauftragt die Migration als Ganzes, der Abbruch
beendet sie als Ganzes — beide Enden des Lebenslaufs stehen unter demselben
Gegenstand. Die Nummer folgt ADR-012: lueckenlos vergeben, nichts rutscht
nach. `A-M5` ist seit dem 2026-09-16 dem Abbruch vorbehalten; der Auftrag
bekommt die naechste freie, `A-M6`. Die Nummer sagt die Reihenfolge der
VERGABE, nicht die des Ablaufs — wie schon `A-K2` vor `A-O1`.

Beide brauchen weder A-Box noch P-Q3: Der Auftrag steht vor der ersten
Extraktion, der Abbruch kann kommen, bevor es eine A-Box gibt. Sie binden
`eingang.json` und `fall.json`. Das Gate rechnet jede ableitbare Angabe der
Vorlage nach (statt ihr zu glauben) und schreibt ihren Inhalt SIGNIERT in den
Snapshot (Feld `auftrag` bzw. `abbruch`); wer spaeter liest, wer den Fall
fuehrt, liest es dort, nicht in einer Datei unter `abgeleitet/`.

### 2. Was der Fallauftrag sagt und bindet (`models.fallauftrag`)

```
{"schema_version": 1, "art": "fallauftrag",
 "fall": {"name": "<fall>", "scope": "bestand"},
 "lieferung": {"eingang_sha256": "<sha256 von eingang.json>",
               "quellen": [{"datei": "<quelle>", "sha256": "<sha256>"}, ...]},
 "programmleitung": {"rolle": "mensch/programmleitung",
                     "schluessel_sha256": "<fingerabdruck>",
                     "schluesselklasse": "mensch", "gates": ["A-M5"]},
 "mandate": {"mensch/aktuariat": "<sha256 des Mandats>", ...},
 "zielsystem": {"linie": "<linie>",
                "abnahmen": {"A-K2": "<snapshot>", "A-O1": "<snapshot>", "A-T1": null}},
 "abgebendes_haus": {"aktuar": null, "vermerk": "nicht benannt: ..."},
 "auftrag": "<Auftragstext des Vorstands>"}
```

* **Fall:** Name und Scope, nachgerechnet gegen `fall.json`.
* **Lieferung:** die Bytes des Eingangs, wie der Fall sie heute bindet
  (ADR-002: `eingang.json` mit je Quelle Name und SHA-256). Das ist dieselbe
  Bindung, die A-M4 seit jeher an die A-Q1-Annahme haelt
  (`artefakt_hashes['eingang.json']`) — der Auftrag schliesst dort an.
  Aendert sich der Eingang (eine nachgereichte Quelle), gilt der Auftrag
  nicht mehr; der Vorstand beauftragt neu (die A-M6-Kette waechst).
* **Programmleitung:** Rolle, Fingerabdruck, Schluesselklasse und ihr Gate.
  HIER wird die Fall-Rolle benannt. Ihr Fingerabdruck darf keiner Rolle der
  Ordnung gehoeren — die Trennung der Operatoren waere sonst nur behauptet.
* **Mandate:** je simulierter Rolle der SHA-256 ihres Mandats (heute in
  `zeichnung.mandat_sha256` jeder Zeichnung gefuehrt). Die Menge ist genau die
  der simulierten Rollen der Ordnung ohne die Wurzel, dazu die Programmleitung,
  wenn sie simuliert ist. Jede simulierte Zeichnung im Fall muss unter genau
  dem Mandat stehen, das der Auftrag ihrer Rolle nennt.
* **Zielsystem:** je Gegenstand, den A-M4 verlangt (A-K2, A-O1, A-T1), die
  geltende angenommene Abnahme der Linie — oder `null`. Gebunden beim
  Zeichnen (das Gate rechnet es aus der Linie nach). Danach gehalten wird
  die IDENTITAET der Linie: Jede Annahme des Falls verlangt, dass die Linie
  ihres Aufrufs den genannten Namen traegt und jede genannte Abnahme in der
  Kette ihres Gates fuehrt (Nachtrag Runde G, b). Nicht gehalten wird, dass
  der Stand seit dem Auftrag unveraendert blieb: Er darf sich im Fall aendern
  (ADR-007), A-M4 haelt den lebenden Stand ueber die Standabnahme selbst.
* **Abgebendes Haus:** ein benannter Platz fuer die Benennung des Aktuars des
  abgebenden Hauses durch dessen eigenes Haus — anerkannt, nicht verliehen
  (ADR-025, Abschnitt 8 d). Heute leer und so benannt; nicht mehr gebaut als
  der Platz.
* **Auftragstext:** was der Vorstand der Programmleitung aufgibt.

### 3. EINE Stelle verlangt den Auftrag fuer alle Gates

`gates.gate_entscheid.fallauftrag_pruefen` — aufgerufen an genau einer
Stelle des Entscheid-Kommandos, fuer jede Annahme eines Falls ausser dem
Auftrag selbst (A-Q1, A-O1/A-K2/A-T1 im Fall, A-M1 bis A-M5, A-B1, A-B2).
Verlangt wird eine eindeutige, signierte Annahme von A-M6 (derselbe
Kettenleser wie fuer jedes Gate), deren `eingang.json` und `fall.json` die
heutigen Bytes sind, gezeichnet von einer Rolle, der die Ordnung A-M6 gibt
(Rollenregel). Die Stelle liegt nach den gate-eigenen Vorbedingungen (deren
Befund ist genauer) und vor jedem Schreiben. Jede Annahme eines Falls traegt
danach signiert das Feld `fallauftrag` — den Snapshot des Auftrags, auf dem
sie steht. Eine Ablehnung braucht keinen Auftrag (ADR-008, Punkt 6). An
derselben Stelle gilt: Die Linie des Aufrufs ist die Linie des Auftrags, und
jede Annahme des Falls, auf der der Aufruf gruendet, nennt den GELTENDEN
Auftrag (Nachtrag Runde G, a und b).

### 4. Woher eine Rolle ihr Recht hat — eine Regel

`models.zeichnung.zeichnende_rolle_fehler` beantwortet die Frage fuer jede
Zeichnung: Fuer die Gates aus `FALLROLLEN_GATES` (heute nur `A-M5` ->
`mensch/programmleitung`) haelt sie die Rolle gegen die Ordnung, die der
geltende Fallauftrag bildet (`models.fallauftrag.rechtsordnung`), und
verlangt, dass der Snapshot genau diesen Auftrag nennt; fuer jedes andere Gate
gegen die Ordnung der Linie (mit Linie: die, unter der gezeichnet wurde). Die
vier Fragen — Rolle des Schluessels, Gate erlaubt, Rollenfeld, Klasse und
Mandat — bleiben dieselben. Das Entscheid-Kommando bestimmt die Rolle beim
Zeichnen nach derselben Unterscheidung. Folgen:

* **Linien-Rollen** (`mensch/rechenkern`, `mensch/architektur`,
  `mensch/aktuariat`, `mensch/betrieb`, `mensch/vorstand`) haben ihr Recht aus
  der Ordnung der Linie.
* **Fall-Rollen** (`mensch/programmleitung`) haben ihr Recht aus dem
  Fallauftrag. Eine Ordnung kann `A-M5` niemandem geben
  (`ZEICHENBARE_GATES` ohne die Gates der Fall-Rollen; `pruefe_ordnung` weist
  es mit Meldung ab), und die Linie fuehrt die Programmleitung nicht
  (`models.ordnungslinie.ROLLEN_DES_FALLS`).
* `mensch/quell-aktuar` bleibt, was ADR-025 sagt: eine Rolle des abgebenden
  Hauses, im Auftrag als Platz benannt.

### 5. Der Fallabbruch (`A-M5`)

Der positive, gezeichnete Satz "dieser Fall endet hier, ohne Abnahme". Die
Vorlage sagt, woran der Fall scheitert (`grund`), welche Gates gezeichnet
waren (`gezeichnet`, aus `entscheide/` gerechnet: Gate, Entscheid, Snapshot),
was mit dem Bestand geschieht (`bestand`), wohin die Uebergabe geht
(`uebergabe`), auf welchem Auftrag er steht (`fallauftrag`) und an welchem
Stand er endet (`stand`: Eingang und Systemstand). Das Gate rechnet
`gezeichnet`, `stand` und den Auftrag nach.

* Gezeichnet von der Programmleitung, die der geltende Auftrag benennt, mit
  dem Schluessel, den er ihr gibt. Ohne Auftrag kein Abbruch: Abbrechen kann
  nur, wer den Fall fuehrt, und gefuehrt wird ein Fall nur mit Auftrag.
* Nach einer geltenden A-M4-Annahme verweigert: Ein Abbruch danach widerriefe
  die Abnahme. Ausweg: A-M4 GEZEICHNET ablehnen (das Aktuariat mit seinem
  Schluessel, neue Spitze; Nachtrag Pruefrunde I), dann abbrechen. Damit
  registriert der Betrieb aus einem abgebrochenen Fall nie etwas — die
  Registrierung verlangt die geltende angenommene A-M4.
* **Danach ist im Fall nichts mehr zeichenbar**, benannt verweigert: keine
  Annahme, keine Ablehnung, kein zweiter Abbruch (`abbruch_im_fall`). Die
  Pruefung ist strukturell und fail-closed: Jede `A-M5-*.json`, die nicht
  nachweislich eine Ablehnung ist, sperrt den Fall. Sie verlangt keine
  Signatur — die Sperre ist die sichere Richtung, und wer `entscheide/`
  beschreiben kann, kann den Fall ohnehin unbrauchbar machen. Die Grenze gilt
  in BEIDEN Richtungen: Wer die eine Datei entfernt, nimmt den Abbruch
  zurueck (Nachtrag Runde G, e).
* **Auch bei verletztem Eingang** (Nachtrag Runde G, d): Der Befund der
  Eingangspruefung sperrt den Abbruch nicht, er steht woertlich darin
  (`eingang_befund`). Den Auftrag sperrt er weiter.

### 6. Die Schranke der Wurzel

ADR-025 gab dem Vorstand genau `A-Z1`. Jetzt traegt er die **Gates der
Wurzel**, an einer Stelle benannt (`models.ordnungslinie.WURZEL_GATES` =
`A-Z1`, `A-M6`): `A-Z1` immer (ohne sie zeichnet niemand das naechste Glied),
sonst nur Gates dieser Menge; keine andere Rolle traegt eines davon. Ein Glied,
das ihm eine fachliche Abnahme gibt, bleibt nicht anhaengbar. Eine Ordnung
mit Vorstand `["A-Z1"]` bleibt gueltig (das ist der Stand vor diesem ADR);
den Fallauftrag bekommt er mit einem Glied (`gates_erweitert`).

**Warum der Auftrag keine fachliche Abnahme ist.** Eine Abnahme bezeugt, dass
etwas richtig ist: Der Verantwortliche Aktuar steht fuer den Bestand ein, die
Rechenkern-Verantwortung fuer den Kern. Der Auftrag bezeugt nichts ueber
einen Gegenstand; er sagt, dass migriert werden SOLL, von wem, mit welcher
Lieferung. Er nimmt keine Arbeit ab, er setzt sie in Gang. Die Trennung aus
ADR-025 bleibt damit bestehen: Die Wurzel kann beauftragen und erlauben,
aber nicht abnehmen.

### 7. Agent und Skill

`agent/programmleitung` beginnt einen Fall nur mit einem geltenden
Fallauftrag; es liest ihn (die A-M6-Annahme im Fall), es zeichnet ihn nie,
und ohne ihn haelt es an und legt die Vorlage des Auftrags vor. Ein
Abbruchkriterium fuehrt zur VORLAGE des Fallabbruchs fuer
`mensch/programmleitung`, nicht mehr nur zum Anhalten.

## Verworfene Alternativen

* **Die Programmleitung beauftragt sich selbst.** Verworfen: Sie entsteht erst
  mit dem Fall. Ein Auftrag, den der Beauftragte zeichnet, beauftragt
  niemanden — und ihr Recht kaeme aus dem Akt, den sie selbst gezeichnet hat.
* **Der Fall beginnt ohne Auftrag, wie bisher.** Verworfen: Dann faehrt ein
  Agent ohne menschlichen Auftrag eine Migration. Die Zurueckhaltung des
  Agenten waere die einzige Sicherung — dieselbe Lage, die die Architektur an
  jeder anderen Stelle durch eine Zeichnung ersetzt hat.
* **Abbruch ueber einen Allzweck-Schluessel.** Verworfen (ADR-018): Eine
  Rolle mit `gates: ["*"]` waere der Nachfolger des abgeschafften
  Platzhalters. Eine Ablehnung braucht ohnehin keine Signatur; was fehlte,
  war der positive Satz, und der ist EIN Akt mit eigenem Gate.
* **Das Recht der Programmleitung aus der Ordnung der Linie.** Verworfen: Die
  Linie fuehrt die Rollen des Hauses; eine Fall-Rolle darin hiesse, dass
  jeder Fall dieselbe Programmleitung haette oder die Linie mit jedem Fall
  wuechse. Und der Vorstand vergaebe der Programmleitung ihr Recht zweimal
  (Glied und Auftrag).
* **Der Auftrag bindet den Systemstand.** Verworfen: Im Fall wird am
  Zielsystem gearbeitet (ADR-007); jeder Commit entwertete den Auftrag. Der
  Stand ist Sache der Standabnahme in A-M4.
* **`A-M0` (Nummer vor A-M1) oder ein eigener Gegenstand `F`.** Verworfen:
  ADR-012 vergibt lueckenlos ab 1; ein eigener Gegenstand fuer zwei Gates, die
  die Migration als Ganzes betreffen, waere eine Achse zu viel.

## Folgen

* **Versionen:** P9-Schema 10, Gate-Version 5.0.0 (Major: ein vorher gruener
  Entscheid wird ohne geltenden Fallauftrag rot); Schema 6 bis 9 bleiben
  lesbar. Neu: `gates.fall_belegen` 1.0.0, Vorlage des Auftrags und des
  Abbruchs je Schema 1; seit dem Nachtrag Runde G `gates.fall_belegen`
  2.0.0 und die Vorlage des Abbruchs Schema 2 (`eingang_befund`; Schema 1 war
  nie gezeichnet und wird nicht mehr gelesen). Die Gate-Version bleibt 5.0.0:
  Sie ist an P9-Schema 10 gebunden, und darauf ist vor dem Merge nichts
  gezeichnet. Der Betrieb registriert nur Snapshots des aktuellen
  Schemas (`betrieb.uebernahme`): Faelle, die vor diesem ADR gezeichnet
  wurden, werden neu beauftragt und neu gezeichnet.
* **Grenze (HMAC), benannt:** Wer in einem Fall eine Annahme zeichnet, braucht
  den Schluessel des Vorstands im Ring, um die Signatur des Auftrags zu
  pruefen — dieselbe Grenze wie bei A-M4 und den Standabnahmen
  (ADR-018, Nachtrag 2026-10-01), hier aber mit dem Wurzelschluessel: Wer ihn
  im Ring haelt, koennte Glieder der Ordnungslinie zeichnen. In der
  Vorfuehrung haelt eine Person alle Schluessel; ein Haus mit getrennten
  Funktionen braucht ein asymmetrisches Verfahren (Signatur mit privatem,
  Pruefung mit oeffentlichem Schluessel). Nicht gebaut. Fuer den Abbruch
  gilt dasselbe mit einem weiteren Schluessel: Liegt eine A-M4 im Fall, auch
  eine abgelehnte, braucht A-M5 den Schluessel von `mensch/aktuariat` im Ring
  — der Abbruch nach einer A-M4 geht in einem Haus mit getrennten Funktionen
  nur gemeinsam mit dem Aktuariat. Welches Gate welche Schluessel braucht,
  steht in der Tabelle des Nachtrags Runde G, c.
  **Fortgeschrieben (Pruefrunde G, G09):** Seit jeder gruendende Leser die
  Glieder der Ordnungslinie gegen den Vorstand prueft (ADR-025, Nachtrag
  Pruefrunde G), liegt der Wurzelschluessel nicht nur im Ring jeder Annahme
  im Fall, sondern auch im Linienbereich (ab dem zweiten Glied) und in den
  Ringen der Betriebskommandos mit `--linie` (Registrierung, Zugangsprobe,
  Neuaufsetzen, Bindung des Anfangsbestands). Jeder dieser Aufrufer kann
  damit pruefen — und, weil HMAC, auch Glieder zeichnen und Faelle
  beauftragen. Die Pruefung schliesst den Faelscher aus, der `linie/ordnung/`
  beschreiben kann, ohne den Schluessel zu halten; gegen einen Halter des
  Schluessels schuetzt sie nicht.
* **Betrieb:** Er gruendet auf A-M4 und A-B2, die ohne geltenden Auftrag
  nicht zeichenbar sind und ihn signiert nennen, und liest seit dem Nachtrag
  Pruefrunde I (I07) diesen Auftrag selbst: Er muss die geltende, angenommene
  Spitze der A-M6-Kette sein, echt signiert, von einer Rolle mit A-M6 unter
  der Linie des Betriebs. Die Bindung des Auftrags an die Lieferung rechnet er
  nicht nach (das Gate hat sie beim Zeichnen gehalten). Einen abgebrochenen
  Fall registriert er nicht, weil der Abbruch nach einer geltenden A-M4
  verweigert wird.
* **Tests:** Der gemeinsame Weg (`tests/zeichnung_fixture.annahme_args`)
  beauftragt jeden Fall, bevor er zeichnet, mit eigenen Schluesseln fuer
  Vorstand und Programmleitung; Tests mit eigenem Argumentbau holen den
  Auftrag ueber `auftrag_args`.
* **Offene Punkte:** `A-M5.fallabbruch bauen` ist erledigt.

## Bedienfolge: einen Fall beauftragen

Voraussetzung: der Fall ist angelegt und die Lieferung registriert
(`python -m rechner_pipeline.fall anlegen ...`, `... fall registrieren ...` je
Quelle); der Vorstand hat `A-M6` in der Ordnung (ein Glied der Linie, ADR-025,
Bedienfolge Schritt 9); die Programmleitung hat einen eigenen Schluessel
(64 Byte, 0600, ausserhalb des Repos), der in keiner Ordnung steht.

1. **Vorlage** (`agent/programmleitung` legt vor, oder der Vorstand selbst):
   `python -m rechner_pipeline.gates.fall_belegen auftrag --fall <fall>
   --linie linie --zeichnungsordnung <ordnung>
   --programmleitung-schluessel <programmleitung.key>
   --programmleitung-klasse mensch|simulation
   [--mandat <rolle>=<mandat> ...] --auftrag "<Auftrag>"` (ein `--mandat`
   je simulierter Rolle).
2. **Ansehen:** `<fall>/abgeleitet/auftrag/fallauftrag.md`.
3. **Zeichnen** (der Vorstand): `python -m rechner_pipeline.gates.gate_entscheid
   --fall <fall> --linie linie --gate A-M6 --entscheid angenommen
   --entscheider "<Rolle>" --begruendung "..." --repo-root .
   --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand.key>
   [--mandat <mandat>]`. Das Gate zeichnet nur die Vorlage, deren Sicht am
   festen Ort die aus ihr erzeugte ist (ADR-025, Nachtrag "Beleg und Sicht");
   verweigert es mit Code `sicht`, Schritt 1 wiederholen und erneut ansehen.
   Endet Schritt 1 mit Code `ein_ausgabe`, denselben Aufruf wiederholen.
4. **Danach** traegt jede Zeichnung im Fall den Schluessel des Vorstands im
   Ring (`--freigabe-schluessel <vorstand.key>` vor dem zeichnenden).
   Wird eine Quelle nachgereicht, gilt der Auftrag nicht mehr: Schritte 1 bis 3
   wiederholen. Gibt ein spaeteres Glied der Linie den Schluessel der
   Programmleitung einer Rolle der Ordnung, verweigert jede Annahme im Fall
   (Code `fallauftrag`): Schritte 1 bis 3 mit einem neuen eigenen Schluessel
   der Programmleitung (Nachtrag Pruefrunde I). Der Betrieb registriert nur
   auf Abnahmen unter dem GELTENDEN Auftrag; seine Kommandos tragen deshalb
   den Schluessel des Vorstands im Ring.

## Bedienfolge: einen Fall abbrechen

1. **Vorlage** (`agent/programmleitung` legt vor):
   `python -m rechner_pipeline.gates.fall_belegen abbruch --fall <fall>
   --repo-root . --grund "<woran der Fall scheitert>"
   --bestand "<was mit dem Bestand geschieht>"
   --uebergabe "<wohin die Uebergabe geht>"`. Das geht auch bei verletztem
   Eingang; der Befund steht dann woertlich in der Vorlage.
2. **Ansehen:** `<fall>/abgeleitet/abbruch/fallabbruch.md` (mit dem Abschnitt
   "Der Eingang").
3. **Zeichnen** (`mensch/programmleitung`, mit dem Schluessel, den der Auftrag
   nennt): `python -m rechner_pipeline.gates.gate_entscheid --fall <fall>
   --linie linie --gate A-M5 --entscheid angenommen --entscheider "<Rolle>"
   --begruendung "..." --repo-root . --zeichnungsordnung <ordnung>
   --freigabe-schluessel <vorstand.key> [--freigabe-schluessel
   <aktuariat.key>] --freigabe-schluessel <programmleitung.key>
   [--mandat <mandat>]`. Der Ring traegt den Schluessel jeder Rolle, deren
   Kette das Gate lesen muss: immer den des Vorstands (Auftrag), und sobald
   eine A-M4 im Fall liegt — auch eine abgelehnte — den von
   `mensch/aktuariat`. Fehlt er, nennt die Meldung die Rolle und ihren
   Fingerabdruck. In einem Haus mit getrennten Funktionen geht der Abbruch
   nach einer A-M4 deshalb nur gemeinsam mit dem Aktuariat (benannte Grenze,
   Nachtrag Runde G, c).
   Wie beim Auftrag: Code `sicht` heisst Vorlage neu erzeugen, ansehen,
   zeichnen.
4. **Danach** ist im Fall nichts mehr zeichenbar. Ist die Migration schon
   abgenommen, zuerst A-M4 GEZEICHNET ablehnen — das Aktuariat, mit seinem
   Schluessel zuletzt im Ring und der Ordnung der Spitze (Nachtrag Pruefrunde
   I): `python -m rechner_pipeline.gates.gate_entscheid --fall <fall> --linie
   linie --gate A-M4 --entscheid abgelehnt --rolle mensch/aktuariat
   --entscheider "<Name>" --begruendung "..." --repo-root .
   --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand.key>
   --freigabe-schluessel <aktuariat.key> [--mandat <mandat>]` — dann
   Schritte 1 bis 3 mit dem Schluessel des Aktuariats im Ring. Der Widerruf
   ist eine Zeichnung im Fall (Nachtrag Pruefrunde J): Er braucht den
   geltenden Auftrag, eine simulierte Rolle zeichnet unter dem Mandat, das
   der Auftrag ihr nennt, und der Schluessel ist nicht der der
   Programmleitung. Eine Ablehnung
   ohne Schluessel oder ohne Ordnung (etwa die eines Agenten) bleibt
   unsigniert und gibt den Abbruch nicht frei; das Gate verweigert mit Code
   `vorbedingung` und nennt diesen Ausweg. `entscheide/`
   wird nie bereinigt: Ohne die A-M5-Datei traegt der Fall keine Spur des
   Abbruchs (Nachtrag Runde G, e).

## Nachtrag 2026-10-01: Pruefrunde G — Auftrag beim Lesen, Linie des Auftrags, Ring des Abbruchs, Abbruch bei verletztem Eingang

Eine blinde Pruefrunde (Linse "Lebenslauf") fand fuenf Stellen, an denen das
Gebaute weniger hielt, als Abschnitte 2, 3 und 5 sagen. Je Entscheid Regel,
Grund und verworfene Alternative.

### a) Eine Vorbedingung steht auf dem geltenden Auftrag (G14)

**Befund.** Die Bindung an den Auftrag galt beim SCHREIBEN eines Snapshots,
nicht beim LESEN seiner Vorbedingungen. Gemessen: Auftrag A1, darunter A-Q1,
A-O1, A-T1, A-K2, A-M1; der Vorstand zieht A1 zurueck (A-M6 abgelehnt) und
beauftragt neu (A2) mit einem anderen Mandat; A-M4 nahm an, nannte A2 und
pinnte Vorbedingungen, die A1 und das alte Mandat trugen.

**Regel.** Eine Annahme des Falls gruendet nur auf Annahmen des Falls, die den
GELTENDEN Auftrag nennen (`fallauftrag` == Snapshot der geltenden
A-M6-Annahme). Eine Annahme unter einem abgeloesten Auftrag ist keine
Vorbedingung mehr; die Meldung nennt das Gate, beide Auftraege und den
Ausweg: unter dem geltenden Auftrag neu zeichnen. Gleichheit des Auftrags
genuegt — das Mandat einer Annahme hat das Gate beim Schreiben gegen genau
diesen Auftrag gehalten.

**Eine Stelle.** `fallauftrag_pruefen` (Abschnitt 3) haelt die Regel; jeder
gruendende Leser meldet dort an, was er gelesen hat (`vorbedingungen`:
Gate -> Snapshot, Pflicht-Schluesselwort ohne Standardwert). Die Menge,
gemessen und als Ratsche mit `==` festgehalten
(`tests/test_lebenslauf_runde_g.py`):

| Leser | liest | gruendet? |
|---|---|---|
| A-M4 | A-Q1, A-M1 (bestand: A-M2, A-M3) | ja, angemeldet |
| A-M4, `standabnahme_pruefen` Weg a | A-K2, A-O1, A-T1 im Fall | ja, angemeldet |
| A-M4, `standabnahme_pruefen` Weg b | Verweis auf eine Abnahme der LINIE | nein: traegt keinen Auftrag, ausgenommen |
| A-B2 | A-M4, A-M1 (den A-M4 pinnt) | ja, angemeldet |
| A-M5, `_lebenslauf_vorlage` | A-M4 als Sperre | nein: sperrt, gruendet nichts |
| jedes Gate | seine eigene Kette (Vorgaenger) | nein |
| `fallauftrag_pruefen` | A-M6 | ist der Auftrag selbst |

**Betrieb.** `betrieb.uebernahme` liest beim Registrieren A-M4, A-M1 (ueber
den Pin von A-M4) und A-B2. Er rechnet den Auftrag weiter nicht nach, und das
genuegt: A-B2 ist ohne geltenden Auftrag nicht zeichenbar und haelt jetzt den
Auftrag von A-M4 und A-M1 gegen den geltenden; A-M4 haelt ihn fuer jede seiner
Vorbedingungen. Wer registriert, gruendet damit transitiv auf Annahmen unter
dem Auftrag, unter dem A-B2 gezeichnet wurde. Was das NICHT abdeckte, benannt:
Zog der Vorstand den Auftrag erst NACH der Zugangsabnahme zurueck, blieb
A-B2 gezeichnet, und der Betrieb registrierte. *Berichtigt (Pruefrunde I,
I07):* Der Betrieb liest jetzt den Auftrag, den A-M4, A-M1 und A-B2 nennen,
auf Gueltigkeit; ein Rueckzug oder ein neuer Auftrag nach A-B2 verweigert die
Registrierung (Nachtrag Pruefrunde I, b).

**Verworfen: die Pruefung je Gate.** Jeder Leser haette sein eigenes
`spitze["fallauftrag"] == ...` getragen; der naechste Leser vergaesse es, und
die Runde fand genau so den Fund. Eine Stelle mit Anmeldung und Ratsche
zaehlt die Leser, statt sich auf sie zu verlassen. **Verworfen: das Mandat
statt des Auftrags vergleichen.** Gleiche Mandate unter einem neuen Auftrag
liessen Annahmen auf einer anderen Lieferung oder unter einer anderen
Programmleitung gelten; der Auftrag ist die Einheit, die der Vorstand
zeichnet.

### b) Die Linie eines Falls ist die Linie des Auftrags (G13, Teil 2)

**Befund.** A-O1 im Fall liess sich unter einer KOPIE der Linie zeichnen, die
dieselben Glieder der Ordnungslinie traegt, aber keine A-O1-Kette; die Regel
"eine Version, ein Vokabular" (ADR-024) sah die Abnahme der echten Linie dann
nicht.

**Regel.** `fallauftrag_pruefen` haelt nach, dass die Linie, die das Gate
jetzt bekommt, die Linie des Auftrags ist: Sie traegt den Namen, den
`zielsystem.linie` nennt, und jede Abnahme, die `zielsystem.abnahmen` aus ihr
nennt, liegt in der Kette ihres Gates (strukturell: Schema,
Selbstadressierung, Graph). Fehlt eine, wird benannt verweigert. Neue
Abnahmen der Linie seit dem Auftrag sind erlaubt. Abschnitt 2 sagte zum
Zielsystem "danach nicht mehr gehalten"; praezise heisst das jetzt:
GEHALTEN wird die Identitaet der Linie; NICHT gehalten wird, dass ihr Stand
seit dem Auftrag unveraendert blieb — das haelt A-M4 ueber die
Standabnahme.

**Grenze, benannt.** Nennt der Auftrag keine Abnahme der Linie (eine Linie
ohne Erstabnahme), bleibt allein der Name; eine Kopie mit demselben Namen
und denselben Gliedern ist dann nicht von der Linie zu unterscheiden. Die
Grenze reicht weiter (Pruefrunde H): Auch eine Kopie, der ein seither
angehaengtes Glied fehlt, besteht die Pruefung — was unter ihr gezeichnet
wird, faengt seitdem der naechste Leser mit der echten Linie (Nachtrag
Pruefrunde H, f); eine vollstaendige aeltere Kopie der Abnahme-Ketten bleibt
ununterscheidbar (g). Die
Signatur der genannten Abnahme haelt hier niemand nach (sie liegt in der
Linie und wird gelesen, wo sie traegt: im Verweis, Weg b). Dass A-M4 die
Vokabular-Regel gegen seine eigene Linie selbst haelt, ist Teil 1 desselben
Befunds und nicht Gegenstand dieses Abschnitts.

**Verworfen: die Linie ueber ihre Glieder identifizieren.** Genau das tat die
Kopie: Glieder sind die Ordnung, nicht die Abnahmen. **Verworfen: einen
Hash ueber den ganzen Linienbereich binden.** Jede neue Abnahme der Linie
entwertete jeden laufenden Auftrag.

### c) Der Ring des Abbruchs nach einer A-M4 (G15)

**Befund.** Der Ausweg "A-M4 ablehnen, dann abbrechen" scheiterte mit dem Ring
der Bedienfolge (Vorstand, Programmleitung): `_lebenslauf_vorlage` liest die
A-M4-Kette mit Signatur, und eine A-M4-Annahme im Fall — auch eine schon
abgelehnte — braucht den Schluessel von `mensch/aktuariat`.

**Regel.** Die Signaturpruefung bleibt. Geaendert sind Vertrag und Meldung:
Die Meldung nennt die Rolle, deren Kette das Gate nicht pruefen kann, ihren
Fingerabdruck und dass ihr Schluessel in den Ring gehoert. Der Ring fuer A-M5
traegt neben Vorstand und Programmleitung den Schluessel jeder Rolle, deren
Kette das Gate lesen muss, sobald eine solche Kette im Fall liegt — heute
A-M4, `mensch/aktuariat`. Fuer ein Haus mit getrennten Funktionen heisst
das: Der Abbruch nach einer A-M4 geht nur gemeinsam mit dem Aktuariat (bei
HMAC haelt, wer den Schluessel im Ring hat, das Geheimnis, mit dem das
Aktuariat zeichnet). Das ist eine Grenze, benannt, nicht versteckt; sie
faellt mit einem asymmetrischen Verfahren (siehe "Grenze (HMAC)").

**Verworfen: die A-M4-Kette strukturell lesen.** Ohne Signatur gaebe eine
untergeschobene Ablehnung (eine Datei in `entscheide/`) den Abbruch nach der
Abnahme frei — die Sperre "nach einer geltenden A-M4 kein Abbruch" waere per
Dateiablage abschaltbar. *Berichtigt (Pruefrunde I, I06):* Das Lesen mit
Signatur allein leistete das nicht, denn Ablehnungen waren unsigniert
(ADR-008, Punkt 6); geschlossen ist es erst mit dem gezeichneten Widerruf
(Nachtrag Pruefrunde I, a).

**Die Klasse, gemessen** (`gates.gate_entscheid`, Leser mit Signatur ueber
den Ring dieses Aufrufs; "eigene Kette" = die Kette des Gates selbst, die
jeder Aufruf liest, auch eine Ablehnung):

| Gate (Annahme) | Ketten, die es mit Signatur liest | Schluessel im Ring (ausser dem zeichnenden) | sagt es die Bedienfolge? |
|---|---|---|---|
| A-M6 | eigene Kette | wer frueher A-M6 gezeichnet hat (der Vorstand) | ja (der zeichnende) |
| A-Q1, A-M1 bis A-M3, A-B1; A-O1/A-K2/A-T1 im Fall | A-M6; eigene Kette | Vorstand | ja (Bedienfolge "beauftragen", Schritt 4) |
| A-M4 | A-M6; A-Q1, A-M1 (bestand: A-M2, A-M3); A-K2, A-O1, A-T1 im Fall (Weg a) oder ihr Verweis (Weg b); eigene Kette | Vorstand, `mensch/aktuariat`, `mensch/rechenkern`, `mensch/architektur` (Weg b: die Rolle der verwiesenen Abnahme) | ja (ADR-018, Nachtrag 2026-10-01, "Grenze") |
| A-B2 | A-M6; A-M4; A-M1; eigene Kette | Vorstand, `mensch/aktuariat` | bisher nicht ausdruecklich; jetzt hier |
| A-M5 | A-M6; A-M4, sobald eine im Fall liegt | Vorstand; `mensch/aktuariat` nach einer A-M4 | bisher nein; jetzt Bedienfolge "abbrechen", Schritt 3 |
| jede Ablehnung | eigene Kette | wer Annahmen dieses Gates gezeichnet hat | jetzt hier |
| Linienbereich (A-K2, A-O1, A-T1, A-B3) | eigene Kette | wer frueher in der Linie gezeichnet hat | ja (ADR-025) |

Ausserhalb der Gates liest die Registrierung (`betrieb.uebernahme`) A-M4,
A-M1 und A-B2 mit Signatur: Ring mit `mensch/aktuariat` und `mensch/betrieb`,
seit Pruefrunde I (I07) immer auch mit dem Vorstand (der Fallauftrag, den die
Abnahmen nennen).

### d) Der Abbruch geht auch bei verletztem Eingang (G16)

**Befund.** A-M5 verlangte wie A-M6 einen Eingang ohne Befund. Ein Fall, dessen
registrierte Lieferung verloren ging, liess sich weder abbrechen noch neu
beauftragen — er blieb offen, ohne Abnahme und ohne Abbruch, obwohl der
Abbruch "jederzeit vor der Migrationsabnahme" kommen kann und eine verlorene
Lieferung ein typischer Grund ist.

**Regel.** A-M5 ist auch bei verletztem Eingang zeichenbar. Die Bindung an den
Auftrag bleibt (`eingang.json` und `fall.json` byte-gleich wie im Auftrag,
`fallauftrag_pruefen`). Der Befund der Eingangspruefung blockiert nicht,
sondern steht woertlich im Abbruch: Feld `eingang_befund` der Vorlage (Schema
2, leer = unversehrt), vom Gate gegen `fall.pruefen` nachgerechnet, signiert
im Snapshot, sichtbar in `fallabbruch.md`. A-M6 bleibt bei verletztem Eingang
verweigert: Auf einer beschaedigten Lieferung wird nicht beauftragt.

**Verworfen: die Eingangssperre fuer beide behalten und auf "registrieren
stellt wieder her" verweisen.** Liefert der Abgeber nicht neu, gibt es nichts
wiederherzustellen; der Fall bliebe ohne Ende. **Verworfen: den Befund nur in
die Begruendung schreiben lassen.** Dann sagte ihn der Mensch, nicht das Gate,
und eine Vorlage, die ihn verschweigt, ginge durch.

### e) Ein Abbruch laesst sich durch Entfernen einer Datei zuruecknehmen (G17)

**Befund.** Die Sperre nach dem Abbruch haengt am Vorhandensein einer
`A-M5-*.json`. Abschnitt 5 benannte die Grenze nur in der Sperrrichtung.

**Die Grenze in beiden Richtungen.** Wer `entscheide/` beschreiben kann, kann
den Fall durch eine hingelegte Datei sperren — und einen gezeichneten Abbruch
durch Entfernen der einen Datei ungeschehen machen; der Fall laeuft dann unter
dem alten Auftrag weiter, und kein spaeter gezeichneter Snapshot haelt fest,
dass es einen Abbruch gab. Das ist dieselbe Klasse wie das Kuerzen jeder
P9-Kette um ihre Spitze (etwa eine A-M4-Ablehnung entfernen). Fuer den
Betrieb heisst das: `entscheide/` wird nie geloescht und nie bereinigt
(ADR-002); ein Fall, dessen Abbruch-Datei fehlt, traegt keine Spur des
Abbruchs. Ein Anker ausserhalb des Falls (ein Protokoll, das der Betrieb
fuehrt, oder ein Register der Linie) waere die Antwort; er ist nicht gebaut.

**Ein billiger Halt im Fall — nicht gebaut**, gemessen:
* Die Vorlage `abgeleitet/abbruch/fallabbruch.json` bleibt nach der Zeichnung
  liegen, aber sie liegt dort schon VOR der Zeichnung (Schritt 1 der
  Bedienfolge). Eine Sperre auf ihr sperrte einen vorbereiteten, nicht
  gezeichneten Abbruch.
* Das Gate-Ledger `abgeleitet/diagnostics/gate_entscheid_am5.gate.json`
  ueberschreibt der naechste Aufruf desselben Gates, auch ein verweigerter
  (gemessen: nach der Zeichnung und einem zweiten, verweigerten A-M5 traegt es
  `failed` und keinen Snapshot).
* Die Historie `gate_entscheid_am5.historie.jsonl` behaelt eine Zeile
  `passed`, aber weder Entscheid noch Snapshot; eine angenommene und eine
  abgelehnte A-M5 sind darin nicht zu unterscheiden. Und beide liegen in der
  aufraeumbaren Zone `abgeleitet/`.
* Kein spaeterer Snapshot nennt den Abbruch — nach ihm ist nichts zeichenbar.

*Nachgetragen (Pruefrunde H, H16):* Ein Ausfall zwischen dem Einhaengen des
A-M5-Snapshots und dem Entfernen seiner Tempdatei liess dessen
Hardlink-Zwilling in `entscheide/` liegen, und jeder weitere Aufruf endete an
der Sperre, bevor er raeumte. Das Gate raeumt die Zwillinge jetzt beim
Eintritt in `entscheide/`, VOR der Sperre (ADR-025, Nachtrag Pruefrunde H,
Punkt 4). Die Grenze dieses Abschnitts aendert das nicht.

## Nachtrag 2026-10-01: Pruefrunde H — die Linie des Lesers, die Kaskade des Auftrags, die Grenze der Kopie

### f) Eine aeltere Kopie der Linie traegt keine Zeichnung mehr, die die echte Linie nicht traegt (H10, H06)

**Befund.** Die Identitaet der Linie (Nachtrag b) ist Name plus genannte
Abnahmen. Eine Kopie der Linie, angelegt NACH dem Auftrag und VOR einem
neuen Glied, erfuellt beides und hat das abloesende Glied nicht. Gemessen:
Der Vorstand entzog mit Glied 2 dem Aktuariat den Schluessel; unter der
Kopie zeichnete der entzogene Schluessel A-Q1, A-M1 und A-M4, und der Leser
des Betriebs nahm die A-M4 unter der echten Linie an. Die Grenze in Nachtrag b
("Auftrag ohne Abnahmen; Kopie mit denselben Gliedern") reichte weiter als
beschrieben: Hier nennt der Auftrag Abnahmen, und der Kopie fehlt ein Glied.

**Regel** (gebaut in ADR-025, Nachtrag Pruefrunde H, Punkt 1): Jeder
gruendende Leser haelt eine Zeichnung gegen die spaeteren Glieder SEINER
Linie; ein Glied, das die zeichnende Rolle mindert, traegt die gezeichnete
Erklaerung des Vorstands — `verfallen` verweigert, `gueltig` traegt
Zeichnungen vor der Abloesung. Damit faellt eine unter der Kopie gezeichnete
Annahme beim naechsten Leser mit der echten Linie: beim Gate des naechsten
Schritts (A-M4, A-B2) und beim Betrieb (Registrierung, Zugangsprobe,
Neuaufsetzen, Bindung). Das Gate, das UNTER der Kopie zeichnet, sieht das
Glied nicht und zeichnet weiter; das ist die Naht, an der gefangen wird.

**Die Kaskade des Auftrags.** Jede Annahme eines Falls gruendet auf A-M6
(Abschnitt 3), A-M6 zeichnet der Vorstand. Erklaert ein Glied die frueheren
Zeichnungen des Vorstands fuer `verfallen` (sein Schluessel ist nicht mehr
vertrauenswuerdig), traegt keine A-M6 der Linie des Vorstands mehr — seit
Pruefrunde I jede fruehere A-M6 unter jedem frueheren Namen und Schluessel
dieser Linie, nicht nur die des zuletzt gehaltenen Schluessels (ADR-025,
Nachtrag Pruefrunde I) — und keine
Annahme eines Falls, der unter ihr beauftragt ist: `fallauftrag_pruefen`
verweigert mit Code `fallauftrag`, der Betrieb verweigert Registrierung,
Zugangsprobe und Neuaufsetzen (Nachtrag Pruefrunde I, I07). Jeder laufende
Fall ist neu zu beauftragen und neu zu zeichnen; ein Zugang, der vorher schon
registriert wurde, bleibt registriert. Mit `gueltig` (Umbenennung, geordneter Wechsel, derselbe
Halter) tragen die Auftraege weiter.

### g) Grenze, benannt: die Kopie als ganze Linie (H11, vom Widerleger nicht bestaetigt)

Die Identitaet der Linie ist Name plus genannte Abnahmen. Eine VOLLSTAENDIGE
aeltere Kopie der Abnahme-Ketten ist ohne aeusseren Anker nicht von der Linie
zu unterscheiden. Gemessen vom Pruefer: Nach einer Ablehnung von A-T1 in der
echten Linie verwies ein Fall unter einer vorher gezogenen Kopie (Weg b) auf
die dort noch geltende A-T1-Annahme; A-M4 nahm unter der Kopie an, und der
Leser des Betriebs sah es nicht — er rechnet die Standabnahmen der A-M4 nicht
nach. Die Regel aus f) faengt das nicht: Sie haelt die Glieder der
Ordnungslinie, keine Abnahme-Ketten; eine Ablehnung ist kein Glied. Billig an
derselben Stelle ginge es nicht: Der Leser muesste je Verweis die Kette der
echten Linie lesen und entscheiden, ob die verwiesene Abnahme VOR dem
`entschieden_am` der lesenden A-M4 abgeloest wurde — ein zweiter Leser im
Betrieb, gegen dessen Zeitvergleich dieselbe Grenze gilt (keine
vertrauenswuerdige Zeit). **Nicht gebaut.** Schliessen wuerde es ein Anker
ausserhalb des Falls (ein Register der Linie, das jede Abnahme und Ablehnung
fortlaufend fuehrt, oder ein Zeitstempeldienst) — derselbe Anker, den
Abschnitt e fuer den entfernten Abbruch nennt.

## Nachtrag 2026-10-01: Pruefrunde I — der gezeichnete Widerruf, der Auftrag beim Betrieb, ein Schema, eine Trennung zu jedem Zeitpunkt

Befunde der blinden Pruefrunde I (Linse "Lebenslauf-Beleg"), bestaetigt vom
Widerleger. Je Entscheid Regel, Grund, verworfene Alternative, Grenze.

### a) Nur ein gezeichneter Widerruf gibt den Abbruch nach A-M4 frei (I06)

**Befund.** Eine von Hand in `entscheide/` gelegte, unsignierte A-M4-Ablehnung
(Hash nachgefuehrt, kein Schluessel) machte sie zur Spitze der A-M4-Kette;
die Vorlage und die Zeichnung des Abbruchs nahmen an, die abgenommene
Migration war tot (ein Abbruch ist nicht rueckholbar). Das Lesen mit
Signatur (Nachtrag Runde G, c) hielt das nicht: `models.freigabe.pruefe_freigabe`
lieferte fuer jede Ablehnung keinen Befund, und Ablehnungen sind nach
ADR-008, Punkt 6, unsigniert. Ebenso gab die unsignierte Ablehnung eines
Agenten ueber das Gate den Abbruch frei.

**Invariante.** Eine ANGENOMMENE Migrationsabnahme verliert ihre Geltung fuer
den Abbruch nur durch einen Widerruf, den eine fuer A-M4 berechtigte Rolle
GEZEICHNET hat.

**Regel.** Ablehnungen bleiben im Allgemeinen unsigniert (ein Agent darf
ablehnen). Aber eine Ablehnung mit dem Schluessel einer Rolle, die das Gate
zeichnen darf (`--freigabe-schluessel`, zuletzt im Ring, und
`--zeichnungsordnung`), ist GEZEICHNET: Das Gate schreibt `zeichnung` (unter
dem Glied der Spitze, mit Klasse und bei Simulation dem Mandat) und
`freigabe` in den Snapshot, mit denselben Sperren der Rollenbindung wie bei
einer Annahme. Jede getragene Freigabe pruefen die Kettenleser ueber den Ring
(`pruefe_freigabe` prueft jetzt jede Annahme UND jede Ablehnung, die eine
Freigabe traegt). Die eine Regel `gates.gate_entscheid.gezeichneter_widerruf_fehler`:
Nach einer Annahme in der A-M4-Kette gibt eine Ablehnung als Spitze den
Abbruch nur frei, wenn sie eine Freigabe traegt und ihre Rolle unter dem
gepinnten Glied der Linie A-M4 zeichnen darf (`models.zeichnung.zeichnende_rolle_fehler`,
samt Abloesung durch spaetere Glieder). Sonst verweigert die Vorlage mit
Code `vorbedingung` und nennt den Ausweg: das Aktuariat lehnt A-M4 mit seinem
Schluessel ab (Bedienfolge "abbrechen", Schritt 4).

**Die Klasse, gemessen.** Gefragt war: Wo hebt eine Ablehnung als Spitze die
Wirkung einer signierten Annahme fuer einen NACHFOLGENDEN Leser auf, sodass
etwas FREIGEGEBEN wird? Gelesen wurden alle Kettenleser (`gates.gate_entscheid`:
neun Aufrufe von `_lade_snapshot_kette`, dazu `fallauftrag_pruefen` und
`_verweis_gilt_fehler`; `gates.stand_belegen`: `_lade_kette` dreimal und
`geltende_spitze`; `gates.fall_belegen`: zweimal `geltende_spitze`;
`betrieb.uebernahme._pruefe_geltende_spitze` fuer A-M4, A-M1, A-B2, A-B3 und
jetzt A-M6; `abbruch_im_fall`).

| Leser | Ablehnung als Spitze | Richtung |
|---|---|---|
| A-M4 (A-Q1, A-M1..A-M3, Standabnahme Weg a), A-B2 (A-M4, A-M1) | keine geltende Annahme | sperrt |
| `fallauftrag_pruefen` (A-M6), `fall_belegen` (Auftrag fuer den Abbruch) | kein geltender Auftrag | sperrt |
| Verweis Weg b (`_verweis_gilt_fehler`, `stand_belegen` Verweis) | die verwiesene Abnahme gilt nicht mehr | sperrt |
| T-Box: `tbox_vokabular_fehler`, `_zuletzt_angenommen` | Ablehnungen zaehlen nicht | weder noch |
| Betrieb: A-M4, A-M1, A-B2, A-B3, A-M6 (`_pruefe_geltende_spitze`) | der Snapshot ist nicht die Spitze | sperrt |
| `abbruch_im_fall` (A-M5) | eine A-M5-Ablehnung sperrt nicht; eine A-M5-Annahme bleibt sperrend | weder noch |
| **A-M5: `_lebenslauf_vorlage` (A-M4)** | **die Abnahme gilt nicht mehr** | **gibt frei** |

Eine Stelle gibt frei; sie geht durch die eine Regel. Ratsche mit `==` ueber
die Aufrufer von `gezeichneter_widerruf_fehler`, mit Positivkontrolle
(`tests/test_lebenslauf_runde_i.py`). Sperren durch eine unsignierte
Ablehnung bleibt: Das ist die sichere Richtung, und wer `entscheide/`
beschreiben kann, kann den Fall ohnehin unbrauchbar machen.

**Gestalt und Version.** Eine Ablehnung ohne Schluessel oder ohne Ordnung
behaelt ihre Gestalt (kein `freigabe`, kein `zeichnung`). Neu ist eine
Ablehnung MIT `freigabe` und `zeichnung`; das Schema laesst `freigabe` an
einer Ablehnung zu, verlangt dann `zeichnung` und erst ab Schema 10. Kein
neues Schema: Schema 10 und Gate 5.0.0 sind ausserhalb der Tests nie
gezeichnet (dieselbe Begruendung wie im Nachtrag Runde G); ein Schema 11
haette ein Schema eingefuehrt, das kein Vorgaenger je getragen hat. Ein vorher
gruener Aufruf wird rot (Abbruch nach einer unsignierten A-M4-Ablehnung) —
die Gate-Version bleibt aus demselben Grund 5.0.0. Gemessen vor der
Verschaerfung: In der Suite liefen 28 Ablehnungen, 10 davon mit dem
Schluessel einer berechtigten Rolle und Ordnung (sie sind jetzt gezeichnet);
eine davon (A-M6, simulierter Vorstand) trug kein Mandat und wurde
umgestellt, ebenso der Test des Abbruchs nach abgelehnter A-M4 (G15), der
die Ablehnung jetzt gezeichnet vornimmt.

**Verworfen:** *jede Ablehnung signieren.* Ein Agent haette keinen Weg mehr,
einen Zwischenstand zu dokumentieren (ADR-008, Punkt 6). *Die Rolle der
Ablehnung strukturell lesen* (Feld `rolle` gleich `mensch/aktuariat`) —
das Feld schreibt, wer die Datei schreibt. *Den Abbruch nach einer A-M4
ganz verbieten* — dann bliebe ein Fall, dessen Abnahme sich als falsch
erweist, ohne Ende. *Nur die Signatur der Ablehnung pruefen, nicht die
Rolle* — dann widerriefe jeder Schluessel der Ordnung die Abnahme des
Aktuariats.

**Grenze, benannt.** Die HMAC-Grenze bleibt: Wer den Schluessel des
Aktuariats im Ring haelt (der Abbruch nach A-M4 verlangt ihn ohnehin), kann
den Widerruf zeichnen. Der Widerruf traegt keinen Fallauftrag; dass er
unter dem geltenden Auftrag steht, haelt der Abbruch selbst
(`fallauftrag_pruefen`). (Ueberholt durch Nachtrag Pruefrunde J: Der
gezeichnete Widerruf traegt den Auftrag, und der Leser rechnet ihn nach.)

### b) Der Betrieb liest den Auftrag, den die Abnahmen nennen (I07)

**Befund.** Der Betrieb registrierte einen Zugang, dessen Fallauftrag durch
`verfallen` auf der Wurzel gefallen war; der Produzent der Ordnungslinie
verspricht als Folge "jede Annahme jedes Falls". Ebenso registrierte er nach
einem Rueckzug oder einem neuen Auftrag NACH der Zugangsabnahme (im Nachtrag
Runde G, a als offen benannt). Beides bewegt eine Entscheidung (den Eintritt
eines Zugangs) und ist keine zulaessige Grenze.

**Gemessen.** Die Schichtgrenze ist kein Hindernis: Der eine Leser
`betrieb.uebernahme.lies_abnahme_snapshot` liest Ketten, Signaturen und die
Rollenregel ueber `models.snapshot_kette`, `models.freigabe` und
`models.zeichnung`; `gates` wird nicht importiert (`code_karte` befundfrei).

**Regel.** Traegt eine gelesene Abnahme das Feld `fallauftrag` (A-M4, A-M1,
A-B2 nach Schema 10), liest derselbe Leser den genannten A-M6-Snapshot mit
derselben Pruefung wie jede Abnahme: Schema, Selbstadressierung, Fall,
Belegrollen, GELTENDE Spitze der A-M6-Kette, angenommen, Signatur ueber den
Ring, Rollenregel unter der Linie des Betriebs. Damit verweigern
Registrierung, Zugangsprobe und Neuaufsetzen gleich: nach einem Rueckzug
(Spitze ist eine Ablehnung), nach einem neuen Auftrag (der genannte ist
nicht mehr Spitze; erst neu gezeichnete A-M4, A-M1 und A-B2 tragen), nach
`verfallen` auf der Wurzel. Die Meldung nennt den Auftrag und den Ausweg.
Der Ring jedes Betriebskommandos traegt dafuer den Schluessel des Vorstands.

**Verworfen:** *die Grenze benennen und nicht bauen* — sie bewegte eine
Entscheidung. *Einen zweiten Leser fuer A-M6 im Betrieb* — zwei Regeln fuer
dieselbe Frage; der eine Leser liest sich selbst.

**Grenze, benannt.** Nicht nachgerechnet wird beim Betrieb die Bindung des
Auftrags an die Lieferung (`eingang.json`, `fall.json`) und die Identitaet
der Linie des Auftrags; beides haelt das Gate bei jeder Annahme. Ein Zugang,
der VOR dem Rueckzug oder vor `verfallen` registriert wurde, bleibt
registriert: Wer ihn zuruecknimmt, entscheidet nicht dieser Leser (dieselbe
Grenze wie bei der A-M4-Ablehnung nach der Registrierung).

### c) Der Betrieb gruendet nur auf dem aktuellen Schema (I08)

**Befund.** Eine Zugangsabnahme A-B2 nach Schema 9 (Gate 4.0.0, ohne
Fallauftrag) trug den Eintritt; die Schema-Pruefung stand nur fuer A-M4 in
der Registrierung.

**Invariante und Menge.** Jeder Snapshot, auf dem der Betrieb gruendet,
traegt das aktuelle Schema. Gemessen (AST): Jede gruendende Lesung im
Betrieb geht durch `lies_abnahme_snapshot` — neun Aufrufstellen in
`betrieb/` (A-M4 viermal, A-M1 zweimal, A-B2 zweimal, A-B3 einmal) und der
Fallauftrag im Leser selbst; Ratsche mit `==` in
`tests/test_abnahme_rolle_klasse.py`. Die Schema-Pruefung steht jetzt dort,
genau einmal in `betrieb/` (Ratsche mit `==` und Positivkontrolle in
`tests/test_lebenslauf_runde_i.py`); die Pruefung in der Registrierung
entfaellt.

**Verworfen:** *die Pruefung je Aufrufer* — der naechste vergaesse sie,
genau so entstand der Fund.

### d) Die Programmleitung gehoert keiner Rolle der Ordnung — zu jedem Zeitpunkt (I09)

**Befund.** Die Trennung (Abschnitt 2) hielt nur die Vorlage des Auftrags.
Gab ein spaeteres Glied den Schluessel der Programmleitung dem Aktuariat,
zeichnete derselbe Schluessel A-Q1 als `mensch/aktuariat` und danach den
Abbruch als Programmleitung.

**Regel.** `fallauftrag_pruefen` — die Stelle, durch die jede Annahme des
Falls geht, den Abbruch eingeschlossen — verlangt, dass der Fingerabdruck der
Programmleitung des geltenden Auftrags unter der Ordnung der SPITZE der Linie
dieses Aufrufs keiner Rolle gehoert. Das schliesst "der zeichnende Schluessel
einer Annahme ist nicht der der Programmleitung" ein: Er gehoerte sonst
einer Rolle der Ordnung. Verweigert mit Code `fallauftrag` und dem Ausweg:
neu beauftragen mit einem eigenen Schluessel der Programmleitung, oder der
Vorstand gibt der Rolle mit einem neuen Glied einen eigenen Schluessel.
Gemessen vor der Verschaerfung: In 753 Annahmen der Suite gehoerte der
Schluessel der Programmleitung nie einer Rolle; kein Testweg umgestellt.

**Verworfen:** *nur den zeichnenden Schluessel vergleichen* — dann zeichnete
die Rolle, der das Glied den Schluessel gab, mit ihm weiter, solange ein
anderer Schluessel derselben Ordnung zeichnete; die Trennung waere nur fuer
den Moment des Vergleichs behauptet. *Die Linie die Schluessel der
Programmleitungen fuehren lassen* — sie fuehrt die Rollen des Hauses
(Abschnitt 4).

**Grenze, benannt.** Gehalten wird gegen die Spitze der Linie DIESES
Aufrufs; eine aeltere Kopie der Linie bleibt die Grenze aus Nachtrag b und g.

### e) Gleichzeitige Annahmen desselben Gates — gemessen, nicht gebaut

Gemessen (zehn Versuche, je zwei Prozesse, die per Barriere zugleich A-Q1
im selben Fall annehmen): In 5 von 10 Versuchen entstanden zwei Spitzen —
beide Snapshots eingehaengt, die Kette danach mehrdeutig und fuer jeden
Leser verletzt. In keinem Versuch endeten beide mit Exit 0: Der zweite
Prozess endete jeweils mit Exit 50 (`gate_ledger`), weil das Aufraeumen der
Schreibreste des einen die Tempdatei des Ledgers des anderen traf — NACHDEM
sein Snapshot schon eingehaengt war. In den uebrigen 5 Versuchen scheiterte
der zweite am Start des Ledgers, bevor er schrieb. Dieselbe Bauform wie bei
den Gliedern der Ordnungslinie: Die Exklusivitaet gilt je Dateiname, und der
Name traegt den Hash des Inhalts. `gates/` hat kein Sperrmittel (nur
`schreibe_exklusiv`, exklusiv je Name); eine Sperre ueber Lesen der Kette und
Schreiben des Snapshots waere ein neues Mittel. **Nicht gebaut.** Betriebsregel
bleibt: Die Gates eines Falls laufen nacheinander.

### Versionen und Testwege

P9-Schema 10 und Gate-Version 5.0.0 bleiben (siehe a). Kein Produzent
aendert seine Gestalt. Umgestellt: die Helfer der Betriebstests legen den
Fallauftrag der Suite in den Fall (`tests/test_betrieb_uebernahme.am6_snapshot`,
`lege_auftrag`; A-M4, A-M1 und A-B2 nennen ihn) — vorher nannten 196
Testwege in 24 Modulen einen Auftrag, der nicht im Fall lag; dazu drei
Fallbauer mit eigener Schreibstelle, das Neuzeichnen unter einem anderen
Glied, drei Ringe ohne den Vorstand, der Test G15, der Rueckzug mit Mandat
und die Meldung des Altsnapshots (Schema 6).

## Nachtrag 2026-10-02: Pruefrunde J — die gezeichnete Ablehnung ist eine Zeichnung im Fall

Befunde der blinden Pruefrunde J (J02, J03, beide mittel, eine Klasse),
bestaetigt vom Widerleger. Je Entscheid Regel, Grund, verworfene Alternative,
Grenze.

### a) Befund und Invariante

**Befund.** Seit Nachtrag I a ist eine Ablehnung mit dem Schluessel einer
berechtigten Rolle GEZEICHNET. Die Pruefungen, die an einer Zeichnung im Fall
haengen, liefen aber nur fuer `--entscheid angenommen`: (J02) Das simulierte
Aktuariat widerrief A-M4 gezeichnet unter einem Mandat, das der Fallauftrag
ihm nicht nennt — Exit 0, danach ging der Abbruch A-M5. (J03) Gab ein
spaeteres Glied den Schluessel der Programmleitung dem Aktuariat, widerrief
dieser Schluessel A-M4 als `mensch/aktuariat` (Exit 0); nach einem weiteren
Glied brach derselbe Schluessel als Programmleitung ab. Abschnitt 2 (Mandate)
und Nachtrag I d (Trennung "zu jedem Zeitpunkt") galten nur fuer Annahmen.

**Invariante.** Jede Zeichnung in einem Fall — Annahme ODER gezeichnete
Ablehnung — geht durch dieselben Pruefungen des Falls: geltender Fallauftrag
samt Bindung an die Lieferung und Linie des Auftrags, Trennung der
Programmleitung gegen die Ordnung der Spitze (`fallauftrag_pruefen`), Mandat
der simulierten Rolle genau wie im Auftrag genannt. Und der Leser, dem eine
gezeichnete Ablehnung etwas FREIGIBT, rechnet nach, was er nachrechnen kann,
statt dem Gate zu glauben.

### b) Regel

* `gates.gate_entscheid.main` ruft `fallauftrag_pruefen` fuer jede Zeichnung
  im Fall ausser an A-M6 (Bedingung `gezeichnet`, nicht mehr "angenommen").
  Damit ist `auftrag_spitze` auch fuer die gezeichnete Ablehnung gesetzt, und
  die Mandatssperre (gegen den Auftrag) greift fuer sie.
* Die gezeichnete Ablehnung im Fall traegt signiert das Feld `fallauftrag`
  (den SHA-256 des geltenden A-M6-Snapshots); das Schema verlangt es dort
  (`models.schemas`, `mit_fallauftrag`). Eine unsignierte Ablehnung traegt es
  nicht.
* Verweigert eine Pruefung eine gezeichnete Ablehnung, beginnt die Meldung mit
  "Gezeichnete Ablehnung verweigert:" (eine Weiche fuer alle Sperren der
  Zeichnung) und nennt neben dem Ausweg der Pruefung (unter dem genannten
  Mandat zeichnen, neu beauftragen, ...) immer: unsigniert ablehnen (ohne
  `--zeichnungsordnung` bzw. ohne den Schluessel der Rolle) — das sperrt und
  gibt nichts frei.
* Der Leser `gezeichneter_widerruf_fehler` (einziger freigebender Leser, nur
  der Abbruch nach A-M4) bekommt den geltenden Auftrag — `_lebenslauf_vorlage`
  liest dafuer die A-M6-Kette mit Signatur ueber den Ring, nicht die
  Behauptung der Vorlage — und verlangt zusaetzlich: es gibt einen geltenden,
  angenommenen Auftrag; der Widerruf nennt ihn (`fallauftrag`); eine simulierte
  Rolle zeichnete unter dem Mandat, das er ihr nennt; der Schluessel der
  Freigabe ist nicht der der Programmleitung dieses Auftrags. Die letzte
  Pruefung haelt auch den Fall, dass ein spaeteres Glied dem Aktuariat einen
  eigenen Schluessel gibt und fruehere Zeichnungen fuer gueltig erklaert:
  Dann laesst die Annahme des Abbruchs die Trennung unter der Spitze zu, der
  Widerruf aber wurde mit dem Schluessel der Programmleitung gezeichnet.

### c) Die Menge, gemessen (AST)

Jede Bedingung auf `args.entscheid == "angenommen"` in
`gate_entscheid.main`: 14 auf 90ee7e9, dazu zwei gleichwertige
(`auftrag_spitze is not None`, gesetzt nur fuer Annahmen). Je Stelle:

| Stelle (Bedingung) | gilt | Grund |
|---|---|---|
| Agentenrolle darf nicht annehmen | nur Annahme | ein Agent darf ablehnen (ADR-008, Punkt 6) |
| Definition `gezeichnet` | Zeichnung | sie IST die Unterscheidung |
| Vorlage von A-M6/A-M5 (`LEBENSLAUF_GATES`) | nur Annahme | eine Ablehnung bindet keine Vorlage; A-M5 wird nie gezeichnet abgelehnt (`FALLROLLEN_GATES`) |
| A-O1: eine Version, ein Vokabular | nur Annahme | nur Angenommenes wird Vokabular |
| Linienbereich: Belege | nur Annahme | eine Ablehnung pinnt keine Belege; im Linienbereich gibt es keinen Auftrag |
| Fall: Eingang, A-Box, gate-eigene Vorbedingungen, Pflichtbelege | nur Annahme | eine Ablehnung pinnt nichts; die Bindung an die Lieferung haelt fuer die Zeichnung `fallauftrag_pruefen` |
| **`fallauftrag_pruefen`** (Auftrag, Lieferung, Linie, Trennung) | **Zeichnung — umgestellt** | J03 |
| Sicht der gepinnten Belege | nur Annahme | eine Ablehnung pinnt keine Belege, es gibt nichts zu sehen |
| Schluessel ohne Rolle (`bestimmt is None`) | nur Annahme | bei der gezeichneten Ablehnung per Konstruktion bestimmt (dieselbe Ordnung, derselbe letzte Schluessel) |
| Meldungsweiche Spitze der Linie, Mandatspflicht | Zeichnung (Wortlaut) | jetzt EINE Weiche `verweigert` fuer alle Sperren der Zeichnung |
| **Mandat gegen den Auftrag** (`auftrag_spitze is not None`) | **Zeichnung — umgestellt** | J02 |
| **Feld `fallauftrag`** (`auftrag_spitze is not None`) | **Zeichnung — umgestellt** | Abschnitt d |
| Inhalt von Auftrag/Abbruch im Snapshot | nur Annahme | der Inhalt ist der der Annahme |
| Ausgabe A-M6 (Programmleitung), A-M5 (Anzeige) | nur Annahme | Ausgabe der Annahme |

Ratsche mit `==` ueber die Bedingungen (Quelltext) und eine zweite, dass der
Aufruf von `fallauftrag_pruefen` unter `gezeichnet` steht, je mit
Positivkontrolle des Detektors (`tests/test_lebenslauf_runde_j.py`). Nachgezogen:
die Zaehlung der Kettenleser (`AUFTRAG_GATE` zweimal,
`tests/test_abnahme_rolle_klasse.py`; `_lebenslauf_vorlage` liest zwei Ketten,
`tests/test_lebenslauf_runde_g.py`).

Gemessen vor der Verschaerfung (instrumentierter Suitenlauf): 32 Ablehnungen
erreichten das Schreiben, 14 davon gezeichnet (4 im Linienbereich, 2 an A-M6,
8 im Fall); alle 8 bestanden Auftrag, Trennung und Mandat. Kein Testweg
umgestellt.

### d) Der Rueckzug und "geltender Auftrag" bei A-M6

Die Ablehnung von A-M6 (der Rueckzug) bleibt ausserhalb von
`fallauftrag_pruefen`, gezeichnet wie unsigniert. Grund: Sie steht nicht
UNTER einem Auftrag, sie ist der Akt AUF ihm — wie die Annahme von A-M6.
Verlangte man fuer sie den geltenden Auftrag, liesse sich gerade ein Auftrag,
der nicht mehr gilt (Lieferung geaendert, Linie verfallen), nicht
zurueckziehen. Der gezeichnete Rueckzug traegt deshalb kein `fallauftrag`;
seine Rolle prueft die Ordnung (A-M6 hat der Vorstand). Getestet mit
geaenderter Lieferung, gezeichnet und unsigniert.

Ohne geltenden Auftrag (nie beauftragt, zurueckgezogen) gibt es im Fall keine
gezeichnete Ablehnung mehr; unsigniert ablehnen bleibt (die Meldung nennt es).

### e) Feld `fallauftrag` in der gezeichneten Ablehnung — Version

**Entschieden:** Die gezeichnete Ablehnung im Fall traegt `fallauftrag`.
Grund: Nur so kann der freigebende Leser nachrechnen, dass der Widerruf unter
dem GELTENDEN Auftrag steht (und gegen dessen Mandate und Programmleitung) —
ein Widerruf unter einem abgeloesten Auftrag gibt den Abbruch nicht frei,
dieselbe Regel wie fuer Vorbedingungen (Nachtrag G a).

**Verworfen:** *kein Feld, der Leser nimmt den heute geltenden Auftrag* — dann
truege ein Widerruf, der unter Auftrag 1 gezeichnet wurde, nach einer
Neubeauftragung unter Auftrag 2, dessen Mandate er nie gesehen hat; der Leser
glaubte dem Zeitpunkt statt dem Beleg (die Grenze, die Nachtrag I a noch
benannte, ist damit gebaut). *Den Widerruf aus der Freigabe herausrechnen
(Mandat nur strukturell lesen)* — das Feld schreibt, wer die Datei schreibt;
signiert ist nur, was im Snapshot steht.

**Version.** P9-Schema 10 und Gate 5.0.0 bleiben, mit derselben Begruendung
wie in den Nachtraegen G und I: Schema 10 und Gate 5.0.0 sind ausserhalb der
Tests nie gezeichnet, die gezeichnete Ablehnung gibt es erst seit Pruefrunde
I. Eine gezeichnete Ablehnung im Fall ohne `fallauftrag` (Form von 90ee7e9)
ist jetzt schemaverletzt; dass ausserhalb der Tests keine liegt, folgt aus der
Begruendung oben und ist nicht gesondert nachgemessen (die Falldatenraeume
liest diese Runde nicht).

### f) Grenzen, benannt

* Die HMAC-Grenze bleibt: Wer den Schluessel des Aktuariats und das Mandat
  des Auftrags haelt, zeichnet den Widerruf.
* Die Trennung haelt das Gate gegen die Ordnung der SPITZE der Linie dieses
  Aufrufs (wie Nachtrag I d); der Leser haelt den Schluessel des Widerrufs
  gegen die Programmleitung des geltenden Auftrags. Dass ein Schluessel einer
  ANDEREN Rolle als der Programmleitung unter einem spaeteren Glied doppelt
  besetzt wird, ist keine Frage dieser Klasse.
* Eine Ablehnung ohne Schluessel sperrt weiter und gibt nichts frei; wer
  `entscheide/` beschreiben kann, kann den Fall ohnehin unbrauchbar machen.
