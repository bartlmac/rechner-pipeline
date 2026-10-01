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
  die Abnahme. Ausweg: A-M4 ablehnen (neue Spitze), dann abbrechen. Damit
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
* **Betrieb:** Er rechnet den Auftrag nicht nach. Er gruendet auf A-M4 und
  A-B2, die ohne geltenden Auftrag nicht zeichenbar sind und ihn signiert
  nennen; einen abgebrochenen Fall registriert er nicht, weil der Abbruch
  nach einer geltenden A-M4 verweigert wird.
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
   [--mandat <rolle>=<mandat> je simulierter Rolle] --auftrag "<Auftrag>"`.
2. **Ansehen:** `<fall>/abgeleitet/auftrag/fallauftrag.md`.
3. **Zeichnen** (der Vorstand): `python -m rechner_pipeline.gates.gate_entscheid
   --fall <fall> --linie linie --gate A-M6 --entscheid angenommen
   --entscheider "<Rolle>" --begruendung "..." --repo-root .
   --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand.key>
   [--mandat <mandat>]`.
4. **Danach** traegt jede Zeichnung im Fall den Schluessel des Vorstands im
   Ring (`--freigabe-schluessel <vorstand.key>` vor dem zeichnenden).
   Wird eine Quelle nachgereicht, gilt der Auftrag nicht mehr: Schritte 1 bis 3
   wiederholen.

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
4. **Danach** ist im Fall nichts mehr zeichenbar. Ist die Migration schon
   abgenommen, zuerst A-M4 ablehnen (das Aktuariat, mit seinem Schluessel),
   dann Schritt 3 mit dem Schluessel des Aktuariats im Ring. `entscheide/`
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
dem Auftrag, unter dem A-B2 gezeichnet wurde. Was das NICHT abdeckt, benannt:
Zieht der Vorstand den Auftrag erst NACH der Zugangsabnahme zurueck, bleibt
A-B2 gezeichnet, und der Betrieb registriert (nicht gebaut; eine Ablehnung von
A-M6 nach einer geltenden A-M4 zu verweigern, waere das Gegenstueck zur Regel
fuer den Abbruch in Abschnitt 5 und ist offen).

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
Dateiablage abschaltbar.

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
A-M1 und A-B2 mit Signatur: Ring mit `mensch/aktuariat` und `mensch/betrieb`.

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
