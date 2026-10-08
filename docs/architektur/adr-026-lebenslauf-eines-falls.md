# ADR-026: Lebenslauf eines Falls — Fallauftrag und Fallabbruch

**Status:** angenommen am 2026-10-01 (Maintainer), umgesetzt am selben Tag.

## Kontext

Bis zu diesem ADR entstand ein Fall, indem jemand ihn anlegte
(`fall anlegen`, ADR-002), und der Programmleitungs-Agent führte ihn durch
die Stufen. Niemand beauftragte den Fall mit einer Zeichnung. Die Rolle
`mensch/programmleitung` war nach ADR-018 eine Fall-Rolle, hatte aber weder
ein Gate noch einen Ort, aus dem ihr Recht kam: Die Ordnung der Linie
(ADR-025) führt Rollen des Hauses, nicht Rollen eines Falls. Ein Fall, der
scheiterte, hatte kein Ende. „Abbruchkriterium“ hieß nur, dass der Agent
anhält.

Der Maintainer hielt fest, dass nur ein Mensch einen Fall beauftragen kann,
und entschied: Am Anfang eines Falls steht ein Fallauftrag als
Abnahmepunkt, gezeichnet von der Wurzelrolle `mensch/vorstand`. Jeder
weitere Abnahmepunkt setzt ihn voraus. Am Ende steht die Abnahme oder der
gezeichnete Fallabbruch.

## Entscheidung

### 1. Ein Fall beginnt mit dem Auftrag und endet mit Abnahme oder Abbruch

| Gate | Wann | zeichnet | Recht aus | Vorlage (Produzent) |
|---|---|---|---|---|
| `A-M6.fallauftrag` | am Anfang, nach der Registrierung der Lieferung | `mensch/vorstand` | der Ordnung der Linie (Gates der Wurzel) | `gates.fall_belegen auftrag` -> `abgeleitet/auftrag/fallauftrag.json` |
| `A-M5.fallabbruch` | jederzeit vor der Migrationsabnahme | `mensch/programmleitung` | dem Fallauftrag | `gates.fall_belegen abbruch` -> `abgeleitet/abbruch/fallabbruch.json` |

Beide sind Art `A` (ein Mensch entscheidet) und Gegenstand `M` (die
Migration als Ganzes). Die Nummern folgen ADR-012: `A-M5` war seit dem
2026-09-16 für den Abbruch vorgesehen, der Auftrag bekam die nächste freie
Nummer. Die Nummer gibt die Reihenfolge der Vergabe an, nicht die des
Ablaufs.

Beide brauchen weder A-Box noch `P-Q3`, denn der Auftrag steht vor der
ersten Extraktion, und ein Abbruch kann kommen, bevor es eine A-Box gibt.
Sie binden `eingang.json` und `fall.json`. Das Gate rechnet jede ableitbare
Angabe der Vorlage nach und schreibt ihren Inhalt signiert in den Snapshot
(Feld `auftrag` bzw. `abbruch`). Wer später wissen will, wer den Fall führt,
liest es dort und nicht unter `abgeleitet/`.

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
* **Lieferung:** die Bytes des Eingangs, wie der Fall sie bindet
  (`eingang.json` mit Name und SHA-256 je Quelle, ADR-002). Wird eine Quelle
  nachgereicht, gilt der Auftrag nicht mehr, und der Vorstand beauftragt neu
  (die A-M6-Kette wächst).
* **Programmleitung:** Rolle, Fingerabdruck, Schlüsselklasse und Gate. Hier
  wird die Fall-Rolle benannt. Ihr Fingerabdruck darf keiner Rolle der
  Ordnung gehören, sonst wäre die Trennung der Funktionen nur behauptet.
* **Mandate:** je simulierter Rolle der SHA-256 ihres Mandats. Die Menge
  umfasst genau die simulierten Rollen der Ordnung ohne die Wurzel, dazu die
  Programmleitung, wenn sie simuliert ist. Jede simulierte Zeichnung im Fall
  muss unter dem Mandat stehen, das der Auftrag ihrer Rolle nennt.
* **Zielsystem:** für `A-K2`, `A-O1` und `A-T1` die geltende angenommene
  Abnahme der Linie oder `null`, beim Zeichnen aus der Linie nachgerechnet.
  Danach gehalten wird die Identität der Linie (Nachtrag Prüfrunde G, b),
  nicht ihr Stand. Der darf sich im Fall ändern (ADR-007); den lebenden
  Stand hält `A-M4` über die Standabnahme.
* **Abgebendes Haus:** ein Platz für den Aktuar des abgebenden Hauses, den
  dessen eigenes Haus benennt (ADR-025, Abschnitt 8 d). Heute leer und so
  vermerkt.
* **Auftragstext:** was der Vorstand der Programmleitung aufgibt.

### 3. Eine Stelle verlangt den Auftrag für alle Gates

`gates.gate_entscheid.fallauftrag_pruefen` wird an genau einer Stelle des
Entscheid-Kommandos aufgerufen, für jede Annahme im Fall außer dem Auftrag
selbst (`A-Q1`, `A-O1`/`A-K2`/`A-T1` im Fall, `A-M1` bis `A-M5`, `A-B1`,
`A-B2`; seit Prüfrunde J auch für gezeichnete Ablehnungen). Verlangt wird
eine eindeutige, signierte Annahme von `A-M6`, deren `eingang.json` und
`fall.json` die heutigen Bytes sind, gezeichnet von einer Rolle, der die
Ordnung `A-M6` gibt. Die Stelle liegt nach den gate-eigenen
Vorbedingungen, deren Befund genauer ist, und vor jedem Schreiben. Jede
Annahme im Fall trägt danach signiert das Feld `fallauftrag`, den Snapshot
des Auftrags, auf dem sie steht. Eine unsignierte Ablehnung braucht keinen
Auftrag (ADR-008, Punkt 6). An derselben Stelle wird geprüft, dass die
Linie des Aufrufs die Linie des Auftrags ist und dass jede Annahme, auf der
der Aufruf gründet, den geltenden Auftrag nennt (Nachtrag Prüfrunde G, a
und b).

### 4. Woher eine Rolle ihr Recht hat

`models.zeichnung.zeichnende_rolle_fehler` beantwortet die Frage für jede
Zeichnung. Für die Gates aus `FALLROLLEN_GATES` (heute nur `A-M5` ->
`mensch/programmleitung`) hält sie die Rolle gegen die Ordnung, die der
geltende Fallauftrag bildet (`models.fallauftrag.rechtsordnung`), und
verlangt, dass der Snapshot genau diesen Auftrag nennt. Für jedes andere
Gate gilt die Ordnung der Linie, unter der gezeichnet wurde. Geprüft wird
jeweils dasselbe: Rolle des Schlüssels, erlaubtes Gate, Rollenfeld, Klasse
und Mandat. Das Entscheid-Kommando bestimmt die Rolle beim Zeichnen nach
derselben Unterscheidung.

* **Linien-Rollen** (`mensch/rechenkern`, `mensch/architektur`,
  `mensch/aktuariat`, `mensch/betrieb`, `mensch/vorstand`) haben ihr Recht
  aus der Ordnung der Linie.
* **Fall-Rollen** (`mensch/programmleitung`) haben ihr Recht aus dem
  Fallauftrag. Eine Ordnung kann `A-M5` niemandem geben
  (`ZEICHENBARE_GATES` ohne die Gates der Fall-Rollen; `pruefe_ordnung`
  weist es ab), und die Linie führt die Programmleitung nicht
  (`models.ordnungslinie.ROLLEN_DES_FALLS`).
* `mensch/quell-aktuar` bleibt eine Rolle des abgebenden Hauses (ADR-025),
  im Auftrag als Platz benannt.

### 5. Der Fallabbruch (`A-M5`)

Der Abbruch ist die gezeichnete Aussage „dieser Fall endet hier, ohne
Abnahme“. Die Vorlage nennt den Grund (`grund`), die gezeichneten Gates
(`gezeichnet`, aus `entscheide/` gerechnet), was mit dem Bestand geschieht
(`bestand`), wohin die Übergabe geht (`uebergabe`), den Auftrag
(`fallauftrag`) und den Stand, an dem der Fall endet (`stand`: Eingang und
Systemstand). Das Gate rechnet `gezeichnet`, `stand` und den Auftrag nach.

* Es zeichnet die Programmleitung, die der geltende Auftrag benennt, mit
  dem Schlüssel, den er ihr gibt. Ohne Auftrag gibt es keinen Abbruch:
  Abbrechen kann nur, wer den Fall führt.
* Nach einer geltenden Annahme von `A-M4` wird der Abbruch verweigert, denn
  er widerriefe die Abnahme. Der Ausweg: `A-M4` gezeichnet ablehnen
  (Nachtrag Prüfrunde I, a), dann abbrechen. Damit registriert der Betrieb
  aus einem abgebrochenen Fall nie etwas.
* Danach ist im Fall nichts mehr zeichenbar: keine Annahme, keine
  Ablehnung, kein zweiter Abbruch (`abbruch_im_fall`). Die Prüfung ist
  strukturell: Jede `A-M5-*.json`, die nicht nachweislich eine Ablehnung
  ist, sperrt den Fall. Eine Signatur verlangt sie nicht, weil eine Sperre
  die sichere Richtung ist. Die Grenze dazu steht in Nachtrag Prüfrunde G,
  e.
* Ein verletzter Eingang sperrt den Abbruch nicht; der Befund steht
  wörtlich darin (`eingang_befund`, Nachtrag Prüfrunde G, d). Den Auftrag
  sperrt er weiterhin.

### 6. Die Schranke der Wurzel

ADR-025 gab dem Vorstand genau `A-Z1`. Seit diesem ADR trägt er die Gates
der Wurzel, benannt an einer Stelle (`models.ordnungslinie.WURZEL_GATES` =
`A-Z1`, `A-M6`): `A-Z1` immer, sonst nur Gates dieser Menge, und keine
andere Rolle trägt eines davon. Ein Glied, das dem Vorstand eine fachliche
Abnahme gibt, lässt sich nicht anhängen. Eine Ordnung mit Vorstand
`["A-Z1"]` bleibt gültig; den Fallauftrag bekommt er mit einem Glied
(`gates_erweitert`).

Der Auftrag ist keine fachliche Abnahme. Eine Abnahme bezeugt, dass etwas
richtig ist. Der Auftrag bezeugt nichts über einen Gegenstand; er sagt,
dass migriert werden soll, von wem und mit welcher Lieferung. Die Trennung
aus ADR-025 bleibt damit bestehen: Die Wurzel kann beauftragen und
erlauben, aber nicht abnehmen.

### 7. Agent und Skill

`agent/programmleitung` beginnt einen Fall nur mit einem geltenden
Fallauftrag. Der Agent liest ihn, zeichnet ihn nie und legt ohne ihn die
Vorlage des Auftrags vor. Ein Abbruchkriterium führt zur Vorlage des
Fallabbruchs für `mensch/programmleitung`, nicht nur zum Anhalten.

## Verworfene Alternativen

* **Die Programmleitung beauftragt sich selbst.** Sie entsteht erst mit dem
  Fall, und ihr Recht käme aus einem Akt, den sie selbst gezeichnet hat.
* **Der Fall beginnt ohne Auftrag.** Dann führte ein Agent eine Migration
  ohne menschlichen Auftrag, gesichert allein durch seine Zurückhaltung. An
  jeder anderen Stelle hat die Architektur das durch eine Zeichnung
  ersetzt.
* **Abbruch über einen Allzweck-Schlüssel.** Eine Rolle mit `gates: ["*"]`
  wäre der Nachfolger des abgeschafften Platzhalters (ADR-018). Was fehlte,
  war die gezeichnete Aussage, und die ist ein Akt mit eigenem Gate.
* **Das Recht der Programmleitung aus der Ordnung der Linie.** Dann hätte
  jeder Fall dieselbe Programmleitung, oder die Linie wüchse mit jedem
  Fall, und der Vorstand vergäbe das Recht zweimal (Glied und Auftrag).
* **Der Auftrag bindet den Systemstand.** Im Fall wird am Zielsystem
  gearbeitet (ADR-007), jeder Commit entwertete den Auftrag. Den Stand hält
  die Standabnahme in `A-M4`.
* **`A-M0` oder ein eigener Gegenstand `F`.** ADR-012 vergibt lückenlos ab
  1, und ein eigener Gegenstand für zwei Gates, die die Migration als
  Ganzes betreffen, wäre eine Achse zu viel.

## Folgen

* **Versionen:** P9-Schema 10, Gate-Version 5.0.0 (Major, denn ein
  Entscheid ohne geltenden Fallauftrag wird rot); Schema 6 bis 9 bleiben
  lesbar. `gates.fall_belegen` steht seit Prüfrunde G auf 2.0.0, die
  Vorlage des Abbruchs auf Schema 2 (`eingang_befund`). Die späteren
  Nachträge ändern Schema und Gate-Version nicht, weil auf Schema 10
  außerhalb der Tests noch nichts gezeichnet war. Der Betrieb registriert
  nur Snapshots des aktuellen Schemas; ältere Fälle werden neu beauftragt
  und neu gezeichnet.
* **Grenze des HMAC-Verfahrens:** Wer im Fall eine Annahme zeichnet,
  braucht den Schlüssel des Vorstands im Ring, um die Signatur des Auftrags
  zu prüfen (wie bei `A-M4` und den Standabnahmen, ADR-018, Nachtrag
  2026-10-01). Weil HMAC symmetrisch ist, könnte er damit auch Glieder der
  Ordnungslinie zeichnen und Fälle beauftragen. Dasselbe gilt im
  Linienbereich ab dem zweiten Glied und für die Betriebskommandos mit
  `--linie` (Registrierung, Zugangsprobe, Neuaufsetzen, Bindung des
  Anfangsbestands). Die Prüfung schließt aus, wer `linie/ordnung/`
  beschreiben kann, ohne den Schlüssel zu halten; gegen einen Halter des
  Schlüssels schützt sie nicht. In der Vorführung hält eine Person alle
  Schlüssel. Ein Haus mit getrennten Funktionen braucht ein asymmetrisches
  Verfahren (Signatur mit privatem, Prüfung mit öffentlichem Schlüssel); es
  ist nicht gebaut. Nach einer `A-M4` braucht der Abbruch zusätzlich den
  Schlüssel von `mensch/aktuariat` im Ring (Nachtrag Prüfrunde G, c).
* **Betrieb:** Er gründet auf `A-M4` und `A-B2`, die nur unter einem
  geltenden Auftrag zeichenbar sind und ihn signiert nennen, und liest
  diesen Auftrag selbst (Nachtrag Prüfrunde I, b). Einen abgebrochenen Fall
  registriert er nicht.
* **Tests:** Der gemeinsame Weg (`tests/zeichnung_fixture.annahme_args`)
  beauftragt jeden Fall, bevor er zeichnet, mit eigenen Schlüsseln für
  Vorstand und Programmleitung. Tests mit eigenem Argumentbau holen den
  Auftrag über `auftrag_args`.

## Bedienfolge: einen Fall beauftragen

Voraussetzung: Der Fall ist angelegt und die Lieferung registriert
(`python -m rechner_pipeline.fall anlegen ...`, `... fall registrieren ...`
je Quelle). Der Vorstand hat `A-M6` in der Ordnung (ein Glied der Linie,
ADR-025, Bedienfolge Schritt 9). Die Programmleitung hat einen eigenen
Schlüssel (64 Byte, 0600, außerhalb des Repositorys), der in keiner Ordnung
steht.

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
   [--mandat <mandat>]`. Das Gate zeichnet nur eine Vorlage, deren Sicht am
   festen Ort aus ihr erzeugt ist (ADR-025, Nachtrag „Beleg und Sicht“).
   Verweigert es mit Code `sicht`, Schritt 1 wiederholen und erneut
   ansehen. Endet Schritt 1 mit Code `ein_ausgabe`, denselben Aufruf
   wiederholen.
4. **Danach** trägt jede Zeichnung im Fall den Schlüssel des Vorstands im
   Ring (`--freigabe-schluessel <vorstand.key>` vor dem zeichnenden). Wird
   eine Quelle nachgereicht, gilt der Auftrag nicht mehr: Schritte 1 bis 3
   wiederholen. Gibt ein späteres Glied der Linie den Schlüssel der
   Programmleitung einer Rolle der Ordnung, verweigert jede Annahme im Fall
   mit Code `fallauftrag`; dann Schritte 1 bis 3 mit einem neuen eigenen
   Schlüssel der Programmleitung (Nachtrag Prüfrunde I, d). Der Betrieb
   registriert nur auf Abnahmen unter dem geltenden Auftrag; seine
   Kommandos tragen deshalb ebenfalls den Schlüssel des Vorstands im Ring.

## Bedienfolge: einen Fall abbrechen

1. **Vorlage** (`agent/programmleitung` legt vor):
   `python -m rechner_pipeline.gates.fall_belegen abbruch --fall <fall>
   --repo-root . --grund "<woran der Fall scheitert>"
   --bestand "<was mit dem Bestand geschieht>"
   --uebergabe "<wohin die Uebergabe geht>"`. Das geht auch bei verletztem
   Eingang; der Befund steht dann wörtlich in der Vorlage.
2. **Ansehen:** `<fall>/abgeleitet/abbruch/fallabbruch.md` (mit dem
   Abschnitt „Der Eingang“).
3. **Zeichnen** (`mensch/programmleitung`, mit dem Schlüssel, den der
   Auftrag nennt): `python -m rechner_pipeline.gates.gate_entscheid --fall <fall>
   --linie linie --gate A-M5 --entscheid angenommen --entscheider "<Rolle>"
   --begruendung "..." --repo-root . --zeichnungsordnung <ordnung>
   --freigabe-schluessel <vorstand.key> [--freigabe-schluessel
   <aktuariat.key>] --freigabe-schluessel <programmleitung.key>
   [--mandat <mandat>]`. Der Ring trägt immer den Schlüssel des Vorstands
   (Auftrag) und, sobald eine `A-M4` im Fall liegt, auch eine abgelehnte,
   den von `mensch/aktuariat`. Fehlt er, nennt die Meldung die Rolle und
   ihren Fingerabdruck. Wie beim Auftrag heißt Code `sicht`: Vorlage neu
   erzeugen, ansehen, zeichnen.
4. **Danach** ist im Fall nichts mehr zeichenbar. Ist die Migration schon
   abgenommen, lehnt zuerst das Aktuariat `A-M4` gezeichnet ab, mit seinem
   Schlüssel zuletzt im Ring und der Ordnung der Spitze (Nachtrag
   Prüfrunde I, a): `python -m rechner_pipeline.gates.gate_entscheid --fall <fall> --linie
   linie --gate A-M4 --entscheid abgelehnt --rolle mensch/aktuariat
   --entscheider "<Name>" --begruendung "..." --repo-root .
   --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand.key>
   --freigabe-schluessel <aktuariat.key> [--mandat <mandat>]`. Danach
   Schritte 1 bis 3 mit dem Schlüssel des Aktuariats im Ring. Der Widerruf
   ist eine Zeichnung im Fall (Nachtrag Prüfrunde J): Er braucht den
   geltenden Auftrag, eine simulierte Rolle zeichnet unter dem Mandat, das
   der Auftrag ihr nennt, und der Schlüssel darf nicht der der
   Programmleitung sein. Eine Ablehnung ohne Schlüssel oder ohne Ordnung,
   etwa die eines Agenten, bleibt unsigniert und gibt den Abbruch nicht
   frei; das Gate verweigert mit Code `vorbedingung` und nennt diesen
   Ausweg. `entscheide/` wird nie bereinigt, denn ohne die A-M5-Datei trägt
   der Fall keine Spur des Abbruchs (Nachtrag Prüfrunde G, e).

## Nachträge

Die Nachträge halten Regeln fest, die nach Prüfrunden (G bis J)
hinzukamen. Rundenbezeichnung und Buchstabe des Abschnitts dienen als
Adresse, unter der Code und Tests auf die Regel verweisen; die Kennungen in
Klammern (etwa G14) sind die Befunde der Runde. Die ausführliche Herleitung
mit den Messungen steht in der Geschichte dieser Datei.

## Nachtrag 2026-10-01: Prüfrunde G — Auftrag beim Lesen, Linie des Auftrags, Ring des Abbruchs, Abbruch bei verletztem Eingang

### a) Eine Vorbedingung steht auf dem geltenden Auftrag (G14)

Die Bindung an den Auftrag galt beim Schreiben eines Snapshots, nicht beim
Lesen seiner Vorbedingungen. Nach Rückzug und Neubeauftragung nahm `A-M4`
unter dem neuen Auftrag an und stützte sich auf Vorbedingungen, die unter
dem alten gezeichnet waren.

**Regel.** Eine Annahme im Fall gründet nur auf Annahmen, die den
geltenden Auftrag nennen (`fallauftrag` gleich dem Snapshot der geltenden
A-M6-Annahme). Eine Annahme unter einem abgelösten Auftrag ist keine
Vorbedingung mehr. Die Meldung nennt das Gate, beide Aufträge und den
Ausweg, unter dem geltenden Auftrag neu zu zeichnen. Gleichheit des
Auftrags genügt, denn das Mandat hat das Gate beim Schreiben gegen genau
diesen Auftrag gehalten.

`fallauftrag_pruefen` hält die Regel an einer Stelle. Jeder gründende
Leser meldet dort an, was er gelesen hat (`vorbedingungen`: Gate ->
Snapshot, Pflichtargument ohne Standardwert).
`tests/test_lebenslauf_runde_g.py` hält die Menge der Leser fest:

| Leser | liest | gründet? |
|---|---|---|
| A-M4 | A-Q1, A-M1 (bestand: A-M2, A-M3) | ja, angemeldet |
| A-M4, `standabnahme_pruefen` Weg a | A-K2, A-O1, A-T1 im Fall | ja, angemeldet |
| A-M4, `standabnahme_pruefen` Weg b | Verweis auf eine Abnahme der Linie | nein, der Verweis trägt keinen Auftrag |
| A-B2 | A-M4, A-M1 (den A-M4 pinnt) | ja, angemeldet |
| A-M5, `_lebenslauf_vorlage` | A-M4 als Sperre | nein, sperrt nur |
| jedes Gate | seine eigene Kette | nein |
| `fallauftrag_pruefen` | A-M6 | ist der Auftrag selbst |

Was der Betrieb vom Auftrag liest, regelt Prüfrunde I, b.

**Verworfen:** die Prüfung je Gate, denn der nächste Leser vergäße sie.
Ebenso, das Mandat statt des Auftrags zu vergleichen: Gleiche Mandate
unter einem neuen Auftrag ließen Annahmen auf einer anderen Lieferung oder
unter einer anderen Programmleitung gelten.

### b) Die Linie eines Falls ist die Linie des Auftrags (G13, Teil 2)

`A-O1` im Fall ließ sich unter einer Kopie der Linie zeichnen, die
dieselben Glieder der Ordnungslinie trägt, aber keine A-O1-Kette.

**Regel.** `fallauftrag_pruefen` prüft, dass die Linie des Aufrufs die
Linie des Auftrags ist: Sie trägt den Namen aus `zielsystem.linie`, und
jede Abnahme, die `zielsystem.abnahmen` nennt, liegt in der Kette ihres
Gates (strukturell: Schema, Selbstadressierung, Graph). Neue Abnahmen der
Linie seit dem Auftrag sind erlaubt. Gehalten wird damit die Identität der
Linie, nicht die Unverändertheit ihres Stands; die hält `A-M4` über die
Standabnahme.

**Grenze.** Nennt der Auftrag keine Abnahme, bleibt allein der Name. Auch
eine ältere Kopie der Linie, der ein seither angehängtes Glied fehlt,
besteht die Prüfung; was unter ihr gezeichnet wird, fängt der nächste
Leser mit der echten Linie (Prüfrunde H, f). Eine vollständige ältere
Kopie der Abnahme-Ketten bleibt ununterscheidbar (Prüfrunde H, g).

**Verworfen:** die Linie über ihre Glieder zu identifizieren, denn genau
das tat die Kopie. Ebenso ein Hash über den ganzen Linienbereich: Jede
neue Abnahme der Linie entwertete dann jeden laufenden Auftrag.

### c) Der Ring des Abbruchs nach einer A-M4 (G15)

Der Ausweg „A-M4 ablehnen, dann abbrechen“ scheiterte mit dem Ring aus
Vorstand und Programmleitung: `_lebenslauf_vorlage` liest die A-M4-Kette
mit Signatur und braucht dafür den Schlüssel von `mensch/aktuariat`.

**Regel.** Die Signaturprüfung bleibt. Die Meldung nennt die Rolle, deren
Kette das Gate nicht prüfen kann, und ihren Fingerabdruck. Der Ring für
`A-M5` trägt neben Vorstand und Programmleitung den Schlüssel jeder Rolle,
deren Kette das Gate lesen muss, sobald eine solche Kette im Fall liegt;
heute ist das `A-M4` mit `mensch/aktuariat`. In einem Haus mit getrennten
Funktionen geht der Abbruch nach einer `A-M4` deshalb nur gemeinsam mit
dem Aktuariat. Diese Grenze fällt erst mit einem asymmetrischen Verfahren
(siehe Folgen).

**Verworfen:** die A-M4-Kette ohne Signatur zu lesen. Dann gäbe eine
untergeschobene Ablehnung den Abbruch nach der Abnahme frei. Ganz
geschlossen ist das erst mit dem gezeichneten Widerruf (Prüfrunde I, a).

Welche Schlüssel ein Aufruf außer dem zeichnenden im Ring braucht:

| Gate (Annahme) | Ketten, die es mit Signatur liest | Schlüssel im Ring |
|---|---|---|
| A-M6 | eigene Kette | wer früher A-M6 gezeichnet hat (der Vorstand) |
| A-Q1, A-M1 bis A-M3, A-B1; A-O1/A-K2/A-T1 im Fall | A-M6; eigene Kette | Vorstand |
| A-M4 | A-M6; A-Q1, A-M1 (bestand: A-M2, A-M3); A-K2, A-O1, A-T1 im Fall (Weg a) oder ihr Verweis (Weg b); eigene Kette | Vorstand, `mensch/aktuariat`, `mensch/rechenkern`, `mensch/architektur` (Weg b: die Rolle der verwiesenen Abnahme) |
| A-B2 | A-M6; A-M4; A-M1; eigene Kette | Vorstand, `mensch/aktuariat` |
| A-M5 | A-M6; A-M4, sobald eine im Fall liegt | Vorstand; `mensch/aktuariat` nach einer A-M4 |
| jede Ablehnung | eigene Kette | wer Annahmen dieses Gates gezeichnet hat |
| Linienbereich (A-K2, A-O1, A-T1, A-B3) | eigene Kette | wer früher in der Linie gezeichnet hat |

Die Registrierung (`betrieb.uebernahme`) liest A-M4, A-M1 und A-B2 mit
Signatur; ihr Ring trägt `mensch/aktuariat`, `mensch/betrieb` und den
Vorstand.

### d) Der Abbruch geht auch bei verletztem Eingang (G16)

Ein Fall, dessen registrierte Lieferung verloren ging, ließ sich weder
abbrechen noch neu beauftragen, obwohl eine verlorene Lieferung ein
typischer Grund für einen Abbruch ist.

**Regel.** `A-M5` ist auch bei verletztem Eingang zeichenbar. Die Bindung
an den Auftrag bleibt (`eingang.json` und `fall.json` byte-gleich wie im
Auftrag). Der Befund der Eingangsprüfung steht wörtlich im Abbruch: Feld
`eingang_befund` der Vorlage (Schema 2, leer heißt unversehrt), vom Gate
gegen `fall.pruefen` nachgerechnet, signiert im Snapshot und sichtbar in
`fallabbruch.md`. `A-M6` bleibt bei verletztem Eingang verweigert: Auf
einer beschädigten Lieferung wird nicht beauftragt.

**Verworfen:** die Eingangssperre für beide zu behalten, denn liefert der
Abgeber nicht neu, bliebe der Fall ohne Ende. Ebenso, den Befund nur in die
Begründung zu schreiben: Dann sagte ihn der Mensch und nicht das Gate.

### e) Ein Abbruch lässt sich durch Entfernen einer Datei zurücknehmen (G17)

Die Sperre nach dem Abbruch hängt am Vorhandensein einer `A-M5-*.json`.
Wer `entscheide/` beschreiben kann, kann einen Fall also durch eine
hingelegte Datei sperren und einen gezeichneten Abbruch durch Entfernen der
Datei ungeschehen machen. Der Fall liefe dann unter dem alten Auftrag
weiter, ohne Spur des Abbruchs. Das ist dieselbe Grenze wie bei jeder
Kette, deren Spitze man entfernt.

**Betriebsregel:** `entscheide/` wird nie gelöscht und nie bereinigt
(ADR-002).

**Nicht gebaut:** ein Anker außerhalb des Falls, etwa ein Protokoll des
Betriebs oder ein Register der Linie. Die Spuren im Fall genügen nicht: Die
Vorlage liegt schon vor der Zeichnung da, das Ledger des Gates überschreibt
der nächste Aufruf, die Historie unterscheidet Annahme und Ablehnung nicht,
und beide liegen unter `abgeleitet/`, das aufgeräumt werden darf.

Seit Prüfrunde H räumt das Gate liegengebliebene Hardlink-Zwillinge beim
Eintritt in `entscheide/`, bevor es die Sperre prüft (ADR-025, zweiter
Nachtrag zu Prüfrunde H, Punkt 4). An der Grenze ändert das nichts.

## Nachtrag 2026-10-01: Prüfrunde H — die Linie des Lesers, die Kaskade des Auftrags, die Grenze der Kopie

### f) Eine ältere Kopie der Linie trägt keine Zeichnung, die die echte Linie nicht trägt (H10, H06)

Eine Kopie der Linie, angelegt nach dem Auftrag und vor einem neuen Glied,
erfüllt Name und genannte Abnahmen, trägt aber das ablösende Glied nicht.
Unter ihr zeichnete ein Schlüssel, den der Vorstand dem Aktuariat
inzwischen entzogen hatte, und der Betrieb nahm die A-M4 unter der echten
Linie an.

**Regel** (gebaut in ADR-025, zweiter Nachtrag zu Prüfrunde H, Punkt 1): Jeder gründende Leser
hält eine Zeichnung gegen die späteren Glieder seiner Linie. Ein Glied, das
die zeichnende Rolle mindert, trägt eine gezeichnete Erklärung des
Vorstands: `verfallen` verweigert, `gueltig` trägt Zeichnungen vor der
Ablösung. Eine unter der Kopie gezeichnete Annahme fällt damit beim
nächsten Leser mit der echten Linie, beim Gate des nächsten Schritts
(`A-M4`, `A-B2`) oder im Betrieb. Das Gate, das unter der Kopie zeichnet,
sieht das Glied nicht; gefangen wird beim nächsten Leser.

**Die Kaskade des Auftrags.** Jede Annahme eines Falls gründet auf `A-M6`,
und `A-M6` zeichnet der Vorstand. Erklärt ein Glied die früheren
Zeichnungen des Vorstands für `verfallen`, trägt keine frühere A-M6 dieser
Linie mehr, unter keinem früheren Namen oder Schlüssel des Vorstands
(ADR-025, Nachtrag Prüfrunde I). Damit trägt auch keine Annahme eines
Falls, der unter ihr beauftragt ist: `fallauftrag_pruefen` verweigert mit
Code `fallauftrag`, der Betrieb verweigert Registrierung, Zugangsprobe und
Neuaufsetzen (Prüfrunde I, b). Jeder laufende Fall ist dann neu zu
beauftragen und neu zu zeichnen. Ein schon registrierter Zugang bleibt
registriert. Mit `gueltig` (Umbenennung, geordneter Wechsel, derselbe
Halter) tragen die Aufträge weiter.

### g) Grenze: die Kopie als ganze Linie (H11)

Eine vollständige ältere Kopie der Abnahme-Ketten ist ohne äußeren Anker
nicht von der Linie zu unterscheiden. Ein Beispiel: Nach einer Ablehnung
von `A-T1` in der echten Linie verweist ein Fall unter einer vorher
gezogenen Kopie auf die dort noch geltende A-T1-Annahme, und `A-M4` nimmt
unter der Kopie an. Die Regel aus f) hilft hier nicht, weil eine Ablehnung
kein Glied ist. Der Leser müsste je Verweis die Kette der echten Linie
lesen und Zeitpunkte vergleichen, für die es keine vertrauenswürdige Zeit
gibt. **Nicht gebaut.** Schließen würde es derselbe äußere Anker wie in
Prüfrunde G, e: ein Register der Linie, das jede Abnahme und Ablehnung
fortlaufend führt, oder ein Zeitstempeldienst.

## Nachtrag 2026-10-01: Prüfrunde I — der gezeichnete Widerruf, der Auftrag beim Betrieb, ein Schema, eine Trennung zu jedem Zeitpunkt

### a) Nur ein gezeichneter Widerruf gibt den Abbruch nach A-M4 frei (I06)

Eine von Hand in `entscheide/` gelegte, unsignierte Ablehnung von `A-M4`
wurde zur Spitze der Kette und gab den Abbruch frei; die abgenommene
Migration war damit verloren. Weil Ablehnungen unsigniert waren (ADR-008,
Punkt 6), half das Lesen mit Signatur nicht. Ebenso gab die unsignierte
Ablehnung eines Agenten den Abbruch frei.

**Regel.** Eine angenommene Migrationsabnahme verliert ihre Geltung für
den Abbruch nur durch einen Widerruf, den eine für `A-M4` berechtigte
Rolle gezeichnet hat. Ablehnungen bleiben im Allgemeinen unsigniert, denn
ein Agent darf ablehnen. Eine Ablehnung mit dem Schlüssel einer Rolle, die
das Gate zeichnen darf (`--freigabe-schluessel` zuletzt im Ring, dazu
`--zeichnungsordnung`), ist aber gezeichnet: Das Gate schreibt `zeichnung`
und `freigabe` in den Snapshot, mit denselben Sperren der Rollenbindung wie
bei einer Annahme. `models.freigabe.pruefe_freigabe` prüft jede Annahme und
jede Ablehnung, die eine Freigabe trägt.

Die eine Regel ist `gates.gate_entscheid.gezeichneter_widerruf_fehler`:
Nach einer Annahme in der A-M4-Kette gibt eine Ablehnung als Spitze den
Abbruch nur frei, wenn sie eine Freigabe trägt und ihre Rolle unter dem
gepinnten Glied der Linie `A-M4` zeichnen darf
(`models.zeichnung.zeichnende_rolle_fehler`). Sonst verweigert die Vorlage
mit Code `vorbedingung` und nennt den Ausweg (Bedienfolge „abbrechen“,
Schritt 4).

Von allen Kettenlesern in Gates und Betrieb gibt nur einer bei einer
Ablehnung als Spitze etwas frei: `_lebenslauf_vorlage`, die vor dem
Abbruch prüft, ob eine Migrationsabnahme gilt. Alle anderen sperren dann
(keine geltende Annahme, kein geltender Auftrag, die verwiesene Abnahme
gilt nicht mehr) oder lassen Ablehnungen außer Betracht (T-Box-Vokabular,
`abbruch_im_fall`). `tests/test_lebenslauf_runde_i.py` zählt die Aufrufer
von `gezeichneter_widerruf_fehler` und zeigt an einem Gegenbeispiel,
dass die Zählung trifft. Dass eine unsignierte Ablehnung sperren kann,
bleibt: Das ist die sichere Richtung.

**Schema und Version.** Eine Ablehnung ohne Schlüssel oder ohne Ordnung
behält ihre Gestalt. Ab Schema 10 erlaubt das Schema `freigabe` an einer
Ablehnung und verlangt dann `zeichnung`. Schema 10 und Gate 5.0.0 bleiben,
weil auf ihnen außerhalb der Tests nie gezeichnet wurde.

**Verworfen:**
* jede Ablehnung signieren: Ein Agent könnte keinen Zwischenstand mehr
  dokumentieren.
* die Rolle der Ablehnung aus dem Feld `rolle` lesen: Das Feld schreibt,
  wer die Datei schreibt.
* den Abbruch nach `A-M4` ganz verbieten: Ein Fall, dessen Abnahme sich
  als falsch erweist, bliebe ohne Ende.
* nur die Signatur prüfen, nicht die Rolle: Dann widerriefe jeder
  Schlüssel der Ordnung die Abnahme des Aktuariats.

**Grenze.** Wer den Schlüssel des Aktuariats im Ring hält, kann den
Widerruf zeichnen (HMAC, siehe Folgen). Seit Prüfrunde J trägt der
Widerruf den Auftrag, und der Leser rechnet ihn nach.

### b) Der Betrieb liest den Auftrag, den die Abnahmen nennen (I07)

Der Betrieb registrierte einen Zugang, dessen Fallauftrag durch
`verfallen` auf der Wurzel gefallen war, ebenso nach einem Rückzug oder
einem neuen Auftrag nach der Zugangsabnahme.

**Regel.** Trägt eine gelesene Abnahme das Feld `fallauftrag` (A-M4, A-M1,
A-B2), liest derselbe Leser (`betrieb.uebernahme.lies_abnahme_snapshot`)
den genannten A-M6-Snapshot mit derselben Prüfung wie jede Abnahme:
Schema, Selbstadressierung, Fall, Belegrollen, geltende Spitze der
A-M6-Kette, angenommen, Signatur über den Ring, Rollenregel unter der Linie
des Betriebs. Registrierung, Zugangsprobe und Neuaufsetzen verweigern damit
gleich: nach einem Rückzug, nach einem neuen Auftrag (erst neu gezeichnete
A-M4, A-M1 und A-B2 tragen) und nach `verfallen` auf der Wurzel. Die
Meldung nennt den Auftrag und den Ausweg. Der Ring jedes
Betriebskommandos trägt dafür den Schlüssel des Vorstands. Die
Schichtgrenze bleibt gewahrt: Der Leser arbeitet über
`models.snapshot_kette`, `models.freigabe` und `models.zeichnung` und
importiert nichts aus `gates`.

**Verworfen:** die Lücke nur zu benennen, denn sie entschied über den
Eintritt eines Zugangs. Ebenso ein zweiter Leser für A-M6 im Betrieb: Das
wären zwei Regeln für dieselbe Frage.

**Grenze.** Die Bindung des Auftrags an die Lieferung und die Identität der
Linie rechnet der Betrieb nicht nach; beides hält das Gate bei jeder
Annahme. Ein Zugang, der vor dem Rückzug oder vor `verfallen` registriert
wurde, bleibt registriert.

### c) Der Betrieb gründet nur auf dem aktuellen Schema (I08)

Eine Zugangsabnahme `A-B2` nach Schema 9 (ohne Fallauftrag) trug den
Eintritt eines Zugangs, weil die Schemaprüfung nur für A-M4 in der
Registrierung stand.

**Regel.** Jeder Snapshot, auf dem der Betrieb gründet, trägt das aktuelle
Schema. Jede gründende Lesung im Betrieb geht durch
`lies_abnahme_snapshot`, und dort steht die Schemaprüfung, genau einmal in
`betrieb/`. `tests/test_abnahme_rolle_klasse.py` zählt die Aufrufstellen,
`tests/test_lebenslauf_runde_i.py` die Schemaprüfung.

**Verworfen:** die Prüfung je Aufrufer, denn der nächste vergäße sie.

### d) Die Programmleitung gehört zu keinem Zeitpunkt einer Rolle der Ordnung (I09)

Die Trennung aus Abschnitt 2 galt nur beim Auftrag. Gab ein späteres Glied
den Schlüssel der Programmleitung dem Aktuariat, zeichnete derselbe
Schlüssel `A-Q1` als `mensch/aktuariat` und danach den Abbruch als
Programmleitung.

**Regel.** `fallauftrag_pruefen`, durch das jede Zeichnung im Fall geht,
verlangt, dass der Fingerabdruck der Programmleitung des geltenden
Auftrags unter der Ordnung der Spitze der Linie dieses Aufrufs keiner
Rolle gehört. Verweigert wird mit Code `fallauftrag` und dem Ausweg: neu
beauftragen mit einem eigenen Schlüssel der Programmleitung, oder der
Vorstand gibt der Rolle mit einem neuen Glied einen eigenen Schlüssel.

**Verworfen:** nur den zeichnenden Schlüssel zu vergleichen, denn dann
gälte die Trennung nur im Moment des Vergleichs. Ebenso, die Linie die
Schlüssel der Programmleitungen führen zu lassen: Sie führt die Rollen des
Hauses (Abschnitt 4).

**Grenze.** Gehalten wird gegen die Spitze der Linie dieses Aufrufs; für
ältere Kopien der Linie gelten Prüfrunde G, b und Prüfrunde H, g.

### e) Gleichzeitige Annahmen desselben Gates (nicht gebaut)

Zwei Prozesse, die zugleich dasselbe Gate im selben Fall annehmen, können
zwei Spitzen erzeugen. Die Kette ist danach mehrdeutig und für jeden Leser
verletzt. In Versuchen geschah das in der Hälfte der Fälle; der zweite
Prozess endete dabei mit Exit 50 (`gate_ledger`), nachdem sein Snapshot
schon geschrieben war. Die Exklusivität gilt je Dateiname, und der Name
trägt den Hash des Inhalts. `gates/` hat kein Sperrmittel, das Lesen der
Kette und Schreiben des Snapshots zusammenfasst. **Betriebsregel:** Die
Gates eines Falls laufen nacheinander.

### Versionen und Testwege

P9-Schema 10 und Gate-Version 5.0.0 bleiben (siehe a). Die Helfer der
Betriebstests legen den Fallauftrag der Suite in den Fall
(`tests/test_betrieb_uebernahme.am6_snapshot`, `lege_auftrag`).

## Nachtrag 2026-10-02: Prüfrunde J — die gezeichnete Ablehnung ist eine Zeichnung im Fall

### a) Befund und Invariante

Seit Prüfrunde I, a ist eine Ablehnung mit dem Schlüssel einer
berechtigten Rolle gezeichnet. Die Prüfungen, die an einer Zeichnung im
Fall hängen, liefen aber nur für Annahmen. So widerrief das simulierte
Aktuariat `A-M4` unter einem Mandat, das der Auftrag ihm nicht nennt (J02),
und ein Schlüssel, der nacheinander dem Aktuariat und der Programmleitung
gehörte, konnte erst widerrufen und dann abbrechen (J03).

**Invariante.** Jede Zeichnung in einem Fall, Annahme oder gezeichnete
Ablehnung, geht durch dieselben Prüfungen: geltender Fallauftrag samt
Bindung an die Lieferung und Linie des Auftrags, Trennung der
Programmleitung gegen die Ordnung der Spitze (`fallauftrag_pruefen`),
Mandat der simulierten Rolle wie im Auftrag genannt. Der Leser, dem eine
gezeichnete Ablehnung etwas freigibt, rechnet selbst nach, statt dem Gate
zu glauben.

### b) Regel

* `gates.gate_entscheid.main` ruft `fallauftrag_pruefen` für jede
  Zeichnung im Fall außer an `A-M6` (Bedingung `gezeichnet`). Damit ist
  `auftrag_spitze` auch für die gezeichnete Ablehnung gesetzt, und die
  Mandatssperre greift.
* Die gezeichnete Ablehnung im Fall trägt signiert das Feld `fallauftrag`;
  das Schema verlangt es dort (`models.schemas`, `mit_fallauftrag`). Eine
  unsignierte Ablehnung trägt es nicht.
* Verweigert eine Prüfung eine gezeichnete Ablehnung, beginnt die Meldung
  mit „Gezeichnete Ablehnung verweigert:“ und nennt neben dem Ausweg der
  Prüfung immer auch diesen: unsigniert ablehnen (ohne
  `--zeichnungsordnung` bzw. ohne den Schlüssel der Rolle). Das sperrt und
  gibt nichts frei.
* `gezeichneter_widerruf_fehler` bekommt den geltenden Auftrag;
  `_lebenslauf_vorlage` liest dafür die A-M6-Kette mit Signatur. Verlangt
  wird: Es gibt einen geltenden, angenommenen Auftrag, der Widerruf nennt
  ihn, eine simulierte Rolle zeichnete unter dem Mandat, das er ihr nennt,
  und der Schlüssel der Freigabe ist nicht der der Programmleitung dieses
  Auftrags.

### c) Welche Bedingung für Annahme oder Zeichnung gilt

In `gate_entscheid.main` ist jede Bedingung auf
`args.entscheid == "angenommen"` einzeln eingeordnet. Drei gelten jetzt
für jede Zeichnung: der Aufruf von `fallauftrag_pruefen` (J03), das Mandat
gegen den Auftrag (J02) und das Feld `fallauftrag` (Abschnitt e). Die
Meldungen aller Sperren der Zeichnung laufen über eine Weiche
(`verweigert`). Die übrigen Bedingungen bleiben bei der Annahme: Eine
Ablehnung pinnt keine Belege, bindet keine Vorlage und stiftet kein
Vokabular, und ein Agent darf weiterhin nur ablehnen (ADR-008, Punkt 6).
`tests/test_lebenslauf_runde_j.py` hält die Bedingungen fest und prüft,
dass der Aufruf von `fallauftrag_pruefen` unter `gezeichnet` steht, beides
mit einem Gegenbeispiel, das die Prüfung auslösen muss.

### d) Der Rückzug und der geltende Auftrag bei A-M6

Die Ablehnung von `A-M6`, der Rückzug, bleibt außerhalb von
`fallauftrag_pruefen`, gezeichnet wie unsigniert. Sie steht nicht unter
einem Auftrag, sie ist der Akt auf ihm. Verlangte man für sie den
geltenden Auftrag, ließe sich gerade ein Auftrag, der nicht mehr gilt,
nicht zurückziehen. Der gezeichnete Rückzug trägt deshalb kein
`fallauftrag`; seine Rolle prüft die Ordnung. Ohne geltenden Auftrag gibt
es im Fall keine gezeichnete Ablehnung; unsigniert ablehnen bleibt
möglich.

### e) Das Feld `fallauftrag` in der gezeichneten Ablehnung

Nur mit dem Feld kann der freigebende Leser nachrechnen, dass der Widerruf
unter dem geltenden Auftrag steht, samt dessen Mandaten und
Programmleitung. Ein Widerruf unter einem abgelösten Auftrag gibt den
Abbruch nicht frei; das ist dieselbe Regel wie für Vorbedingungen
(Prüfrunde G, a).

**Verworfen:** auf das Feld zu verzichten und den heute geltenden Auftrag
zu nehmen. Dann trüge ein Widerruf, der unter Auftrag 1 gezeichnet wurde,
nach einer Neubeauftragung unter Auftrag 2, dessen Mandate er nie gesehen
hat. Ebenso, das Mandat nur strukturell zu lesen: Signiert ist nur, was im
Snapshot steht.

**Version.** P9-Schema 10 und Gate 5.0.0 bleiben, mit derselben Begründung
wie in Prüfrunde G und I. Eine gezeichnete Ablehnung im Fall ohne
`fallauftrag` ist jetzt schemaverletzt.

### f) Grenzen

* Wer den Schlüssel des Aktuariats und das Mandat des Auftrags hält,
  zeichnet den Widerruf (HMAC, siehe Folgen).
* Die Trennung hält das Gate gegen die Ordnung der Spitze der Linie dieses
  Aufrufs (wie Prüfrunde I, d). Der Leser hält den Schlüssel des Widerrufs
  gegen die Programmleitung des geltenden Auftrags.
* Eine Ablehnung ohne Schlüssel sperrt weiter und gibt nichts frei.
