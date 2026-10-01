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
  Zeichnen (das Gate rechnet es aus der Linie nach); danach nicht mehr
  gehalten: Der Stand darf sich im Fall aendern (ADR-007), A-M4 haelt den
  lebenden Stand ohnehin selbst.
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
sie steht. Eine Ablehnung braucht keinen Auftrag (ADR-008, Punkt 6).

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
  beschreiben kann, kann den Fall ohnehin unbrauchbar machen.

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
  Abbruchs je Schema 1. Der Betrieb registriert nur Snapshots des aktuellen
  Schemas (`betrieb.uebernahme`): Faelle, die vor diesem ADR gezeichnet
  wurden, werden neu beauftragt und neu gezeichnet.
* **Grenze (HMAC), benannt:** Wer in einem Fall eine Annahme zeichnet, braucht
  den Schluessel des Vorstands im Ring, um die Signatur des Auftrags zu
  pruefen — dieselbe Grenze wie bei A-M4 und den Standabnahmen
  (ADR-018, Nachtrag 2026-10-01), hier aber mit dem Wurzelschluessel: Wer ihn
  im Ring haelt, koennte Glieder der Ordnungslinie zeichnen. In der
  Vorfuehrung haelt eine Person alle Schluessel; ein Haus mit getrennten
  Funktionen braucht ein asymmetrisches Verfahren (Signatur mit privatem,
  Pruefung mit oeffentlichem Schluessel). Nicht gebaut.
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
   --uebergabe "<wohin die Uebergabe geht>"`.
2. **Ansehen:** `<fall>/abgeleitet/abbruch/fallabbruch.md`.
3. **Zeichnen** (`mensch/programmleitung`, mit dem Schluessel, den der Auftrag
   nennt): `python -m rechner_pipeline.gates.gate_entscheid --fall <fall>
   --linie linie --gate A-M5 --entscheid angenommen --entscheider "<Rolle>"
   --begruendung "..." --repo-root . --zeichnungsordnung <ordnung>
   --freigabe-schluessel <vorstand.key> --freigabe-schluessel
   <programmleitung.key> [--mandat <mandat>]`.
4. **Danach** ist im Fall nichts mehr zeichenbar. Ist die Migration schon
   abgenommen, zuerst A-M4 ablehnen.
