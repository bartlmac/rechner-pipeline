# Spezifikation und Parametrierung — Phasenverfahren des Fallskills

Normatives Phasenverfahren des `migrationsfall-durchfuehren`-Skills für
Spezbildung, Golden Master und die Standabnahmen A-K2/A-O1/A-T1. Die
frühere Detailreferenz `ablauf-detail.md` ist seit der Aufteilung ein
Kompatibilitätsindex mit allen alten Ankern; diese Datei ist das
normative Zuhause des hier benannten Stoffs. Lade die Abschnitte, die
dein aktueller Schritt braucht, vollständig; nach einem Kontextwechsel
Auftrag, Haltpunkt und diese Referenz neu laden.

## Inhaltsverzeichnis

- [Stufe 2 — A-Box -> Spez -> Kern](#spez)
- [Stufe 3 — Golden Master](#golden)
- [Der Stand des Falls — A-K2, A-O1, A-T1](#stand)
- [Wohin Teile der alten Detailreferenz gewandert sind](#weiterleitung)

<a id="spez"></a>
## Stufe 2 — A-Box -> Spez -> Kern

1. Spez: `spez.erzeugen.baue_spez(abox, <gen-id>, referenz_id=<vorgaenger>)`
   + `spez.validierung.speichere_spez`. Das Struktur-Urteil
   (Parametrierung vs. neue Produktfamilie) wird BERECHNET — nimm es
   ernst: `neue_produktfamilie` oder offene Erweiterungsstellen heissen
   STOPP und Mensch fragen (eine T-Box-Erweiterung ist Gate A-O1, eine
   Kern-Aenderung Gate A-K2).
2. Tafel-Importbedarf (`python -m rechner_pipeline.quellen.tafel_import
   --fall faelle/<fall> --generation <gen-id> --dry-run`) pruefen und
   uebergeben: Der DRY-RUN ist eine Bedarfspruefung und laeuft als
   Systemkommando; der SCHARFE Import schreibt in den Kern und wird
   waehrend einer laufenden Migration nicht durch einen Agenten
   ausgefuehrt. Konflikte (wertverschiedene Tafeln gleichen Namens)
   sind ein Provenienz-Problem fuer den Menschen.
3. Kern-Aenderungen: eine neue Generation ist PARAMETRIERUNG — kein
   Formel-Code. Neue Tafeln in `kern/tafeln.xml` sind eine fachliche
   Aenderung: Kern-`__version__` anheben, Abnahme-Protokoll des Kerns
   einhalten (bestehende Charakterisierungstests muessen gruen bleiben).

Kein Agent schreibt waehrend einer laufenden Migration an T-Box oder
Kern, auch nicht in einer gesonderten Entwicklungssitzung und nicht
unter einem Entwicklermandat: Aenderungsbedarf PRAESENTIEREN, der Mensch
prueft die Diffs und zeichnet (im Regie-Modus die simulierte Rolle unter
Mandat). Fuer zulaessige Entwicklung ladest du `entwickle-im-zielsystem`;
bei migrationsbedingter Codearbeit zusaetzlich
`integriere-migrationsinkrement`. Vor einer neuen Gateimplementierung
zusaetzlich `author-rechner-toolbox-gate`.

<a id="golden"></a>
## Stufe 3 — Golden Master (Abnahme der Parametrierung)

1. Gate P-K1: `python -m rechner_pipeline.gates.generation_golden --fall faelle/<fall> --generation <gen-id> --repo-root .`
   Prueft vorab, dass die Spez Projektion der A-Box ist, und vergleicht
   den Kern gegen die aus dem Quell-Rechner extrahierten
   Erwartungswerte. Ein gruener Lauf schreibt neben dem Latest-Ledger
   einen unveraenderlichen, inhaltsadressierten Beleg fuer diese Generation;
   alle A-Box-Generationen muessen auf demselben A-Box- und Systemstand
   gelaufen sein. Beachte das Summary: `zellen_ohne_erwartungswerte`
   ehrlich weitermelden (der Quell-Rechner traegt meist nur EINEN
   Beispiel-Modellpunkt). Pruefe jede Generation; Zellen ohne
   Erwartungswerte sind ein auszuweisender Befund, kein Bestehen.
2. Volle Suite: `.venv/bin/python -m pytest` — bestehende Referenzwerte
   duerfen sich nicht bewegen.

P-K1 nimmt die PARAMETRIERUNG ab, nicht den Bestand; der Bestand laeuft
durch die Abnahmen des Phasenverfahrens "Abnahmen und Berichte".

<a id="stand"></a>
## Der Stand des Falls — A-K2, A-O1, A-T1 (Mensch; hier STOPPST du, wenn sich etwas geaendert hat)

A-M4 verlangt in beiden Scopes, dass der Stand, auf dem der Fall laeuft,
abgenommen ist — der KERNSTAND (A-K2, gezeichnet von `mensch/rechenkern`),
der T-BOX-STAND (A-O1, `mensch/architektur`) und das TARIFWERK der PLV
(A-T1, `mensch/aktuariat`), nach EINER Regel (ADR-018, Nachtrag
2026-10-01; ADR-025). Jeder Gegenstand ist einmal AUSSERHALB jedes Falls
abgenommen — die Erstabnahme im Linienbereich `linie/` (Bedienfolge in
ADR-025). Ein Fall zeichnet nur, was sich DURCH IHN aendert. Je Gegenstand
gilt genau einer von zwei Wegen:

1. **Keine Aenderung** (der Normalfall) — der Stand ist identisch zu dem,
   den die geltende Abnahme der Linie abgenommen hat:
   `python -m rechner_pipeline.gates.stand_belegen verweisen --fall faelle/<fall> --gate A-K2|A-O1|A-T1 --linie linie --repo-root .`
   legt die Kopie ihrer geltenden Spitze an den festen Ort. Verwiesen wird
   NUR auf die geltende Abnahme der Linie (Pruefrunde G): `--snapshot` auf
   einen frueheren Fall ist entfallen — dessen Herkunftskette kann A-M4 nicht
   pruefen. Kein neuer Entscheid; A-M4 prueft Signatur, Rolle, Klasse und
   Stand, haelt nach, dass der Verweis noch die geltende Spitze der Linie
   ist (eine spaetere Ablehnung oder Annahme dort loest ihn ab — dann neu
   verweisen oder im Fall abnehmen), und fuehrt woertlich "keine Aenderung
   seit Abnahme <snapshot> (Linie ...)". Was der Fall selbst aendert (Weg 2),
   gilt fuer diesen Fall; fuer den naechsten Fall nimmt die Rolle den Stand
   in der Linie ab. `--repo-root` ist der Baum des Pakets, das rechnet:
   Jedes Kommando verweigert einen Baum mit anderem Paket.
2. **Abnahme im Fall** — der Fall erzwingt eine Aenderung (etwa eine
   T-Box-Erweiterung). Kern: Der Rechenkern-Agent legt vor mit
   `python -m rechner_pipeline.gates.kernstand_belegen --fall faelle/<fall> --repo-root . --von <zuletzt abgenommener Kernstand> --begruendung "<Kurzbegruendung>"`
   (Sicht `abgeleitet/kern/aenderung.md`; die Regression ist bis zu ihrem
   Werkzeug die benannte AUSNAHME "Regression: Ausnahme — nicht gefahren,
   Werkzeug noch nicht erstellt"; gib sie genau so weiter, nie als
   bestanden). T-Box: Der Architektur-Agent legt vor mit
   `python -m rechner_pipeline.gates.stand_belegen tbox --fall faelle/<fall> --repo-root . --artefakt <vermerk> --begruendung "<text>" --vorher-linie linie`
   (Sicht `abgeleitet/tbox/aenderung.md`: Vokabular-Diff; `--vorher-linie`
   ist die Linie, die das Gate bekommt: Das Gate rechnet die
   Vergleichsgrundlage selbst nach und verweigert sonst mit Code `sicht`),
   das Aktuariat
   legt `abgeleitet/tbox/stellungnahme.json` daneben. Tarifwerk: Der
   Aktuariats-Agent legt vor mit
   `python -m rechner_pipeline.gates.tarifwerk_belegen --fall faelle/<fall> --repo-root . --von <zuletzt abgenommener Stand> --begruendung "<text>"`
   (Sicht `abgeleitet/tarifwerk/aenderung.md`). Der Mensch prueft die
   Sicht und zeichnet: `gate_entscheid --gate A-K2|A-O1|A-T1` mit dem
   Schluessel seiner Rolle — uebergeben, nicht selbst entscheiden. Gehoeren
   Beleg und Sicht nicht zusammen (Code `sicht`; bei A-O1 auch eine fehlende
   Archivkopie unter `abgeleitet/tbox/archiv/`), Vorlage neu erzeugen und
   erneut uebergeben. Verweigert `stand_belegen tbox`, weil das Archiv einer
   abgenommenen T-Box fehlt, ist das kein Anlass fuer "Erstabnahme": die
   gepinnte Fassung wiederherstellen (die Meldung nennt sie).

Liegt im Fall eine Kette des Gates, gilt nur Weg 2 — eine Ablehnung wird
nicht durch einen Verweis umgangen. Die fruehere Basislinie der T-Box gibt
es nicht mehr. Jeden Entscheid des Falls zeichnet der Mensch mit
`--linie linie`: Gezeichnet wird nur unter der Spitze der Versionslinie
der Zeichnungsordnung, und jede Vorbedingung wird gegen die Ordnung
gelesen, unter der sie gezeichnet wurde (ADR-025).

**In der Laufzeit einer Migration schreibst du nicht an der T-Box und
nicht am Kern.** Du legst den Aenderungsvorschlag vor; der Mensch prueft
die Diffs und zeichnet (im Regie-Modus die simulierte Rolle unter Mandat).
Auch eine getrennte Entwicklungssitzung oder ein Entwicklermandat hebt
dieses Agentenschreibverbot waehrend einer laufenden Migration nicht auf.
Zulaessige migrationsbedingte Codearbeit folgt zusaetzlich verpflichtend
`integriere-migrationsinkrement`.

<a id="weiterleitung"></a>
## Wohin Teile der alten Detailreferenz gewandert sind

- Quellen -> A-Box, Bestandsabzug -> Ziel-Ontologie und Gate A-Q1:
  `quellen-und-transformation.md`.
- Abnahmen A-M1 bis A-M4, Schicht und Pflichtmengen, Fuehrungsprobe,
  Fallabbruch und Abbruchkriterien: `abnahmen-und-berichte.md` und die
  dort benannten Fachreferenzen.
- Zugang nach A-M4: `betriebsuebergabe.md` und der Skill
  `uebernehme-migrationsbestand`.
- Alle alten Anker der früheren Detailreferenz `ablauf-detail.md`
  bleiben als Kompatibilitätsindex erhalten.
