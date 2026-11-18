# Abnahmen und Berichte — Phasenverfahren des Fallskills

Normatives Phasenverfahren des `migrationsfall-durchfuehren`-Skills für
die aktuarielle Abnahme A-M1 mit A-M2/A-M3, das Migrationscontrolling
A-M4, die Schichtfestlegungen des migrierten Tarifplans und den
Fallabbruch. Die frühere Detailreferenz `ablauf-detail.md` ist seit der
Aufteilung ein Kompatibilitätsindex mit allen alten Ankern; diese Datei
ist das normative Zuhause des hier benannten Stoffs. Lade die Abschnitte,
die dein aktueller Schritt braucht, vollständig; nach einem Kontextwechsel
Auftrag, Haltpunkt und diese Referenz neu laden.

## Inhaltsverzeichnis

- [Vor den Abnahmen: Mengenregel und Schichtbeleg](#mengenregel)
- [Stufe 3b — Pruefung des uebernommenen Bestands](#bestandspruefung)
- [Aktuarieller Test: A-M1, A-M2, A-M3](#aktuartest)
- [Migrationscontrolling und Gate A-M4](#am4)
- [Ausgestaltung des migrierten Tarifplans vor A-M4](#tarifplanfestlegungen)
- [Fallabbruch (Programmleitung)](#fallabbruch)
- [Abbruchkriterien (STOPP und Mensch fragen)](#abbruchkriterien)
- [Wohin Teile der alten Detailreferenz gewandert sind](#weiterleitung)

P-K1 nimmt die PARAMETRIERUNG ab, nicht den Bestand. Der uebernommene
Bestand laeuft durch zwei getrennte Pruefebenen mit zwei menschlichen
Gates in erzwungener Reihenfolge (ADR-010): ZUERST der aktuarielle Test
(Gates A-M1/A-M2/A-M3), DANACH das Migrationscontrolling (Gate A-M4).
Ohne geltende A-M1-Annahme ist A-M4 unmoeglich; im Bestands-Scope
verlangt A-M4 zusaetzlich A-M2 und A-M3. Uebergib an die beiden
Fachskills `aktuartest-durchfuehren` und `pruefe-migrationscontrolling`,
statt die Schritte selbst zu improvisieren.

<a id="mengenregel"></a>
## Vor den Abnahmen: Mengenregel und Schichtbeleg

Schichtbelegpflicht, Pflichtziehung und allgemeine Stichprobe sind drei
verschiedene Dinge, die du nicht verwechselst:

- **Pflichtziehung (Mengenregel):** Registrierte Auskunft deckt die
  Policenmenge fuer A-M1 und A-M2; A-M3 verlangt daraus die Policen
  mit Vorfall im Pruefzeitraum. Details und normative Regeln stehen in
  `aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`
  (Anker `pflichtmengen`); A-M4 prueft diese Mengen.
- **Schichtbeleg:** Ist im festen Fallbestand `verankerung.parquet`
  vorhanden, laeuft vor A-M1/A-M2/A-M3 und vor der Suite
  `gates.verankerung_belegen` (Anker `schichtbeleg` der genannten
  Fachreferenz); alle Pruefkommandos bekommen dann `--schicht` mit
  demselben abgeleiteten Beleg.
- **Allgemeine Stichprobe:** ein drittes Profil jenseits von
  `vollbestand`/`geschichtet` ist eine Teamaufgabe, keine Abkuerzung.
  Die Mengenregel ersetzt keine stichprobenbelegte Pruefung; die
  Codepruefung bleibt massgeblich. Keine neue Vollerhebung fuer alle
  Aktuartests aus der Mengenregel ableiten.

Fehlt etwas (bestand, Spez, Erwartungswerte, Historie, eine der
vorgeschriebenen Mengen): STOPP und an den Menschen uebergeben. Befunde
niemals bereinigen; ein roter Test oder Bericht ist ein Ergebnis, kein
Auftrag zur Aufweichung von Toleranzen.

<a id="bestandspruefung"></a>
## Stufe 3b — Pruefung des uebernommenen Bestands (wenn Stufe 1b lief)

P-K1 nimmt die PARAMETRIERUNG ab, nicht den Bestand. Der uebernommene
Bestand wird ueber die beiden Pruefebenen rechnerisch nachgewiesen; der
Beweis endet nicht beim Stichtags-Foto, sondern beim Nachweis, dass das
Zielsystem den Bestand wie das Quellsystem FORTSCHREIBT. Deshalb zwei
Stichtage, ueber jeden Vertrag, mit dem Folge-Abzug und dem GeVo-Protokoll
der Lieferung.

1. **Gate P-B1** auf den uebernommenen Bestand:
   `python -m rechner_pipeline.gates.bestand_validate --portfolio <bestand>.parquet --config <config>.toml --repo-root . --diagnostics-dir faelle/<fall>/abgeleitet/diagnostics`
   (traegt der Bestand Folgezustaende — `status_id > 1` —, zusaetzlich
   `--historie <journal>.parquet`: P-B1 prueft den Stammzustand gegen den
   juengsten Journalstand, ADR-011). Historie/Scheiben/Ledger optional
   mitgeben, wenn der Fall sie fuehrt. Sein Ledger unter
   `<fall>/abgeleitet/diagnostics/bestand_validate.gate.json` ist
   Pflichtbeleg fuer A-M4; ohnte `--diagnostics-dir` fehlt er.
2. **Abnahmesuite je Vertrag** (Engine `qa.migrationssuite`, gefahren
   NUR ueber das Kommando, das die Tarifregeln aus der Spez nimmt):
   `python -m rechner_pipeline.gates.migrationssuite_lauf --fall faelle/<fall> --generation klv/tg2015 --abzug-1 <registriert>.csv --abzug-2 <registriert>.csv --gevo-protokoll <registriert>.csv --bestand <bestand>.parquet --config <bestand-config>.toml --stichtag-1 <iso> --stichtag-2 <iso>`.
   Deckungskapital am Migrationsstichtag, Bruttojahresbeitrag am
   Migrationsstichtag (`bjb_erwartet_1`), GeVo-Betraege zwischen den
   Stichtagen, Deckungskapital am Folgestichtag auf dem richtigen Track;
   die Zeilenzahl des Abzugs geht als `erwartete_anzahl` mit. Toleranzen
   aus `qa`, nie aufgeweicht; `vollstaendig_geprueft=true` im
   Bestands-Scope.
3. **Freischaltung und Fuehrungsprobe:** Der gefuehrte Bestand muss das
   rechnen, was die Abnahmen A-M1 bis A-M3 bestanden haben. Die vier
   Handgriffe (Config-Tarifwerk, Schichtbeleg, Fortschreibung,
   Fuehrungsprobe) stehen normativ mit vollstaendigen Aufrufen in
   `pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md`
   (Anker `freischaltung`). Der Beleg `fuehrungsprobe.json` ist
   Pflichtbelegrolle `fuehrungsprobe` von A-M4.
4. **Bestandsberichte vor/nach** mit denselben fachlichen Bewertungs-
   und Darstellungsregeln, aber bewusst verschiedenen Horizonten und
   Bestandsstaenden: VOR aus dem Uebernahme-Verzeichnis bis `stichtag_1`,
   NACH aus dem fortgeschriebenen Gesamtbestand bis `stichtag_2`
   (vollstaendige Aufrufe in der Fachreferenz, Anker `berichtspaar`).
   Dies ist kein Eigenbestand-Vorher/Nachher; den Betriebsbericht mit
   `--berichtsstichtag` aus Stufe 1b nicht mit diesem Fallbericht mischen.
   Die Suite liefert die vollstaendige Zwei-Stichtags-Pruefung; A-M4
   bindet die Berichtdateien, prueft aber nicht deren HTML-Semantik.
5. **Abnahmebericht** als Entscheidungsvorlage (keine Abnahme): er
   bindet Eingang, A-Box und Systemstand mit. Der vollstaendige Aufruf
   und alle Regeln (Pflichtartefakte, paarweise verschiedene Belege,
   Bindung des gruenen `abnahmebericht.gate.json`) stehen normativ in
   der Fachreferenz
   [fuehrung-und-berichtspaar.md](../../pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md#abnahmebericht),
   die der Fachskill vor dem Controlling ganz geladen hat; die Abnahme
   selbst ist Gate A-M4 (Mensch).

<a id="aktuartest"></a>
## Aktuarieller Test: A-M1, A-M2, A-M3

Vor jedem aktuariellen Test lade den Skill `aktuartest-durchfuehren`
und dessen Fachreferenz `schicht-und-pflichtmengen.md` (Anker
`pflichtmengen` und `schichtbeleg`) ganz. A-M1/A-M2/A-M3 sind DREI
getrennte Abnahmen, jede mit eigener Stichprobe, eigenen Kriterien und
eigener Unterschrift; jede laeuft fuer sich und wird einzeln gezeichnet.
Das Stichprobenprofil waehlt das Aktuariat; es ersetzt keine
Pflichtziehung auskunftsgedeckter Policen (Mengenregel oben). Rechen-
punkte liegen auf dem Vertragsjahrestag, ohne Interpolation; unterjaehrig
ist nur der Geschaeftsvorfall. Der Bericht ist die Entscheidungsvorlage;
die Abnahme selbst ist der menschliche Gate-Entscheid bei
`rechner_pipeline.gates.gate_entscheid --gate A-M1` (bzw. A-M2/A-M3).
Ohne geltende A-M1-Annahme ist keine A-M4 moeglich.

<a id="am4"></a>
## Migrationscontrolling und Gate A-M4

Vor dem Controlling lade den Skill `pruefe-migrationscontrolling` und
dessen Fachreferenz `fuehrung-und-berichtspaar.md` (Anker
`fortschreibung`, `freischaltung`, `berichtspaar`, `abnahmebericht`)
ganz. Zwingend: `stichtag_2 > stichtag_1`; VOR kommt aus dem
Uebernahmebestand bis Stichtag 1, NACH aus dem fortgeschriebenen
Gesamtbestand bis Stichtag 2. Das Kommando verweigert ein verletztes
Stichtagspaar; eine Umbenennung der Stichtage, um ein verletztes Paar
durchzureichen, ist ein Fehler, kein Weg.

`python -m rechner_pipeline.gates.gate_entscheid --gate A-M4
--zeichnungsordnung <externe-ordnung> --freigabe-schluessel <externe-datei> ...`
— uebergeben, nicht selbst entscheiden. A-M4 verlangt die geltenden,
signierten Abnahme-Snapshots desselben Stands als Vorgaenger und pinnt
sie als Rollen `am1_snapshot`/`am2_snapshot`/`am3_snapshot`: A-M1 immer
(aktuarielle vor finanzieller Abnahme, ADR-010), im Bestands-Scope auch
A-M2 und A-M3. In beiden Scopes verlangt A-M4 ausserdem, dass Kernstand,
T-Box-Stand und Tarifwerk abgenommen sind (Rollen `kernstand`, `tboxstand`,
`tarifwerkstand`; Weg und Anzeige je Gegenstand im Snapshot unter
`standabnahmen`), und rechnet die Belege nach (Phasenverfahren
`Spezifikation und Parametrierung`, Anker `stand`). A-M4 liest den Scope
aus `fall.json` und leitet seine exakte Pflichtbelegmenge je Gate aus dem
Fall-Scope ab. Im Bestands-Scope werden das Abnahme-Ledger, jedes von ihm
gebundene Artefakt und das von P-B1 benannte Portfolio gegen die aktuellen
Bytes nachgehasht; P-B1, Suite und Fuehrungsprobe werden semantisch erneut
validiert; der HTML-Bericht wird aus der Suite deterministisch neu
gerendert und bytegenau verglichen. Vorgelegt wird alles vollstaendig,
ohne Stichproben-Beschoenigung. Ein roter Bericht oder eine rote Suite
ist ein Ergebnis fuer den Menschen, kein Hindernis, das du wegraeumst.

<a id="tarifplanfestlegungen"></a>
## Ausgestaltung des migrierten Tarifplans vor A-M4

Traegt der Fall eine RECHNENDE Korrekturschicht (Residuum > 0 verankert),
legt `agent/aktuariat` VOR der A-M4-Vorlage die Schichtfestlegungen des
migrierten Tarifplans zur Zeichnung vor — sie lassen sich nicht vorab
definieren, sondern entstehen aus dem konkreten Bestand
(Grundsatzdokumentation Abschnitt 10 Nr. 9):

1. **Uebergangsklassifikation** je Geschaeftsvorfall des Produkts
   (vererbt eine Korrektur den Vorfall oder heilt er sie) — einschliesslich
   der Bestaetigung der Heilungsklassen, die heute als ungeprueft
   markiert sind (`kern.korrekturschicht.HEILUNG`, `geprueft=False`).
2. **Ankerliste**: welche Groessen an welchen Zeitpunkten verankert sind
   (t_a je Vertrag; t_0 nur bei aktiviertem R_conv-Pfad, E2).
3. **Formfunktion** des Residuen-Abbaus samt Parametern.
4. **Untergrenzen/Floors** der Schichtwerte.
5. **Testfallkatalog** der Schicht (welche Vertragslagen der aktuarielle
   Test je Abnahme abdecken muss).

Ohne rechnende Schicht (Residuum ~0 wie im ersten Baldrian-Lauf)
entfaellt der Schritt — das haeltst du im Laufprotokoll fest, statt ihn
still zu ueberspringen. Eine Schicht, die eine ungeklaerte Diskrepanz
glattzieht, ist ein Regler, kein Beleg: vor der Erzeugung alle
offenen/vorlaeufigen Diskrepanzen der Spez endgueltig aufloesen.

<a id="fallabbruch"></a>
## Fallabbruch (Programmleitung)

Laesst sich der Fall nicht zu Ende fuehren, endet er nicht im Sande, sondern
mit dem gezeichneten Satz "dieser Fall endet hier, ohne Abnahme" (`A-M5`,
ADR-026). Du legst die Vorlage vor und haeltst an:

```bash
python -m rechner_pipeline.gates.fall_belegen abbruch --fall faelle/<fall> --repo-root . \
    --grund "<woran der Fall scheitert>" --bestand "<was mit dem Bestand geschieht>" \
    --uebergabe "<wohin die Uebergabe geht>"
```

`mensch/programmleitung` prueft `abgeleitet/abbruch/fallabbruch.md` und
zeichnet `A-M5` mit dem Schluessel, den der Auftrag ihr gibt. Der Abbruch geht
auch bei verletztem Eingang (eine verlorene Lieferung ist ein typischer
Grund); der Befund der Eingangspruefung steht dann woertlich in Vorlage und
Sicht. Der Ring traegt den Schluessel des Vorstands (Auftrag) und, sobald eine
A-M4 im Fall liegt — auch eine abgelehnte —, den von `mensch/aktuariat`:
Ohne ihn verweigert das Gate und nennt die Rolle. Der Abbruch nach einer A-M4
geht deshalb nur gemeinsam mit dem Aktuariat (ADR-026, Nachtrag Runde G).
Danach ist im Fall nichts mehr zeichenbar; `entscheide/` wird nie bereinigt.
Nach einer geltenden A-M4-Annahme verweigert das Gate den Abbruch; ob A-M4
abgelehnt wird, entscheidet der Mensch. Den Abbruch gibt danach nur ein
GEZEICHNETER Widerruf frei (ADR-026, Nachtrag Pruefrunde I): das Aktuariat
lehnt mit seinem Schluessel unter der Ordnung der Spitze ab, und das Gate
zeichnet die Ablehnung:

```bash
python -m rechner_pipeline.gates.gate_entscheid --fall faelle/<fall> --linie linie \
    --gate A-M4 --entscheid abgelehnt --rolle mensch/aktuariat --entscheider "<Name>" \
    --begruendung "<warum die Abnahme widerrufen wird>" --repo-root . \
    --zeichnungsordnung <ordnung> --freigabe-schluessel <vorstand.key> \
    --freigabe-schluessel <aktuariat.key> [--mandat <mandat>]
```

Eine Ablehnung ohne Schluessel oder ohne Ordnung (auch deine,
`--rolle agent/programmleitung`) bleibt unsigniert und gibt den Abbruch nicht
frei. Gibt ein Glied der Linie den Schluessel der Programmleitung einer Rolle
der Ordnung, verweigert jede Annahme im Fall mit Code `fallauftrag`; der Fall
wird mit einem eigenen Schluessel der Programmleitung neu beauftragt.

Zieht der Vorstand den Auftrag zurueck und beauftragt neu, gelten die
Annahmen unter dem alten Auftrag nicht mehr als Vorbedingung: A-M4 und A-B2
verweigern und nennen das Gate; zeichne die Vorbedingungen unter dem neuen
Auftrag neu vor. Gezeichnet wird unter der Linie, die der Auftrag nennt — eine
Kopie der Linie ohne ihre Abnahmen verweigert das Gate.

<a id="abbruchkriterien"></a>
## Abbruchkriterien (STOPP und Mensch fragen)

- Struktur-Urteil != parametrierung, oder Erweiterungsstellen offen.
- Merkmalsraum-Konflikt zwischen Quellen (Dimensions-Definitionen
  widersprechen sich).
- Tafel-Konflikt (wertverschieden bei gleichem Namen) oder
  Eingang-Integritaetsverletzung.
- Ein bestehender Charakterisierungstest des Kerns (eingefrorene Referenzwerte) wird rot.
- Ein Ziel-Pflichtfeld der Transformation ist aus dem Abzug nicht
  ableitbar, oder die Quelle traegt ein fachlich uebernahmepflichtiges
  Merkmal, fuer das die Ziel-Ontologie kein Feld hat (Gate A-O1).
- Die Controlling-Suite (`qa.migrationssuite`) oder der aktuarielle
  Test melden Befunde zur Konsistenz der Lieferung
  (fehlende Vertraege ohne Abgangs-GeVo, unbekannte GeVo-Arten) — das
  ist ein Ergebnis fuer den Menschen, kein Hindernis, das du wegraeumst.

<a id="weiterleitung"></a>
## Wohin Teile der alten Detailreferenz gewandert sind

- Quellen -> A-Box, Bestandsabzug -> Ziel-Ontologie und Gate A-Q1:
  `quellen-und-transformation.md`.
- Spez, Golden Master und Stand A-K2/A-O1/A-T1:
  `spezifikation-und-parametrierung.md`.
- Zugang nach A-M4: `betriebsuebergabe.md` und der Skill
  `uebernehme-migrationsbestand`.
- Alle alten Anker der früheren Detailreferenz `ablauf-detail.md`
  bleiben als Kompatibilitätsindex erhalten.
