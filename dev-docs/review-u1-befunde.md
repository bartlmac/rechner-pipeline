# Unabhaengiges Review T20: Ontologie, Fall-Dokumentation, agentisches Modell

Auftrag des Maintainers vom 2026-09-05: ein umfangreiches, unabhaengiges,
adversariales Review gegen drei vorgegebene Ziele — bewusst OHNE den Kontext
der laufenden Entwicklungssitzung. Durchgefuehrt als Workflow mit 13 Agenten
(Pilot plus Vollausbau) auf dem Stand 6e239dc (Branch fallbericht, PR #11):
Sammler auf Sonnet (effort medium, rein lesend, nur Belege), adversariale
Pruefer, Skeptiker und Synthese auf Fable (effort high). Jeder Befund wurde
mit refute-first erhoben; die schwersten zwei je Ziel wurden von einem
unabhaengigen Skeptiker verifiziert (Default bei Unsicherheit: widerlegt).
Spielleiter-Bereiche (docs-local/, simulation/, regie/) waren tabu; der
lokale Fall faelle/baldrian-klv-tg2015-lauf2 durfte gelesen werden.

Verbrauch: Pilot 191k Tokens (Sonnet), Vollausbau 1,51 Mio Tokens gesamt
(336k Ausgabe), 47 Minuten, Hard-Cap 600k Ausgabe-Tokens nicht erreicht.
Rohdaten aller Agenten: `dev-docs/review-t20-ergebnis.json`.

Dieses Dokument ist die Befundliste, kein Reparaturstand. Der Stand je
Befund wird hier nachgetragen, wenn der Maintainer entschieden hat.

## Die drei Ziele


- **Z1 — Ontologiemodell.** Schaerfung und Erhaertung des Ontologiemodells inklusive seiner Dokumentation und Darstellung.
- **Z2 — Fall-Dokumentation fuer Bereichsleiter Fach und IT.** Qualitaet der Dokumentation eines Migrationsfalls — Design, Architektur, Werkzeuge, Ausgabeformate und Vorlagen — in Richtung Demonstration an Fachbereiche und IT-Bereiche. Konsumentenebene: Bereichsleiter bzw. Fuehrungskraft im Fach- oder IT-Bereich, mit je eigenem Format- und Sprachbedarf.
- **Z3 — Agentisches Modell Ende-zu-Ende.** Das agentische Modell fuer einen Migrationsfall Ende-zu-Ende: Ziele, Rollen, Skills, Werkzeuge, Zeichnungen, Dokumentation des KI-Systems.

## Synthese

Der Kern traegt: Aussage mit Provenienz, Widerspruch als Objekt, deterministischer Merge, Spez als validierte Projektion, Gates mit gerechneten Vorbedingungen, HMAC-Zeichnungsordnung und P9-Snapshots sind erzwungen und im Vorfuehrfall lueckenlos nachweisbar. Der schwerste Vorwurf beider Nachweis-Pruefer (B1, Z3-04: 'gezeichnet auf nicht rekonstruierbarem Code') ist widerlegt — ich habe die Nachrechnung wiederholt: alle sechs sauberen Commit-Baeume liefern byte-genau die Quelltext-Pruefsummen der 16 Snapshots (101 Paketdateien je Stand); das dirty-Flag stammt aus Aenderungen ausserhalb des Pakets, der Bericht sagt an dieser Stelle die Wahrheit. Was nicht traegt, ist die Frage 'wer entscheidet': Der Code laesst seit 404974d die aus dem Schluessel bestimmte Rolle endgueltig entscheiden und zeichnen (entscheide.py Z. 5-12), diese Rolle war im Lauf eine KI-Session im Mandat, und P2, ADR-008 Z. 50, AGENTS.md, README und drei Skills sagen weiter 'Mensch' — waehrend ein Skill und ein Docstring sogar eine Aufloesung 'OHNE Menschen' erlauben, die kein Code kennt (Z1-01, Z3-01, Z3-02, alle verifiziert). Die zweite Schwaeche ist eine Klasse nominaler Modellteile: 'mehrdeutig' ohne Produzent, TBOX_VERSION seit 0f65e93 nie gesprungen und nie geprueft, A-K1 ohne eigenen Zweig in gate_entscheid und im Lauf nie gezeichnet, obwohl 23 Systemaenderungen stattfanden — bestaetigt per Stichprobe. Drittens erzeugt das Modell Scheinwidersprueche, weil Parameter keine Normalform haben (6 von 14 Diskrepanzen), und die Darstellung traegt diese Unterscheidung nicht — dieselbe Ursache erklaert die abweichenden Diskrepanz-Zaehlungen zwischen Bericht und Seite. Viertens sind die an Fuehrung und Pruefer adressierten Dokumente glatter als die Artefakte: kein Wort zu KI-Beteiligung, Simulationscharakter, Golden-Master-Abdeckung 1/6, A-M2-Toleranz, Systemaenderungen im Lauf; dazu Rollen-IDs, Feldnamen und ASCII-Umschrift im Fachtext. Fuenftens beschreibt die Rahmen-Doku (ONBOARDING, pipeline-v01, Skill-Texte) den Stand vor dem Lauf. Zuerst gehoert die Governance-Frage in ein ADR und der Fachbericht um seine Abgrenzungen ergaenzt — beides ist Schreibarbeit von ein bis zwei Tagen und muss vor der naechsten Veroeffentlichung liegen; dann Snapshot-Schema um Besetzung und Mandat, Einstiegsdoku, der eine echte latente Bug (code_karte paketpfad); die Modell-Erhaertung (Parameter-Katalog, Versionsvertrag, Uebergangstabellen) kann danach folgen und ist zugleich der erste echte Anwendungsfall fuer den fehlenden Versions- und A-K1-Vertrag. Widerlegt und aus dem Plan gestrichen: B1 und der Reproduzierbarkeitskern von Z3-04; herabgestuft: Z1-02 (mittel), Z3-01 (hoch), B2 (mittel).

### Befund-Klassen und ihre Invarianten

Die Massnahme ist die Klasse; die Einzelbefunde sind Belege.

**K1 Autoritaet ohne Ausweis: 'wer entscheidet' hat drei Antworten, die Besetzung der Rolle ist im Beleg unsichtbar**  
Befunde: Z1-01 (verifiziert, hoch), Z3-01 (verifiziert, hoch), Z3-02 (verifiziert, hoch), Z3-06 (mittel), Z3-03 (hoch), Z3-08 (mittel), B2-Teil Rollen-ID (verifiziert, mittel)  
Invariante: Fuer jede Handlung, die eine Aussage endgueltig macht oder ein Gate annimmt, ist aus dem signierten Beleg allein ableitbar: welche Rolle (aus dem Schluessel), wie besetzt (natuerliche Person oder KI-Session), aus welchem signierten Mandat — und es gibt genau EINE normative Quelle (ADR), die dasselbe sagt wie der Code; Prinzipien, AGENTS.md, README und Skills zitieren sie.

**K2 Nominale Modellteile: Zustaende, Versionen und Gates ohne Produzent, Uebergang und Test**  
Befunde: Z1-02 (verifiziert, mittel), Z1-04 (hoch; Stichprobe bestaetigt: kein A-K1-Zweig, Version seit 0f65e93 unveraendert, tbox_version nur durchgereicht), Z1-05 (mittel), Z3-07 (mittel), Z1-07 (mittel)  
Invariante: Jeder Enum-Wert, jede Versionsnummer, jedes Gate und jede Evidenzart der Ontologie hat einen Code-Produzenten, einen Konsumenten, einen definierten Ein- und Austritt und mindestens einen Test, der ihn uebt; was das nicht hat, existiert im Modell nicht (streichen) oder ist in Abschnitt 8/ADR als bewusste Grenze ausgewiesen.

**K3 Repraesentation gegen Bedeutung: Parameter ohne Normalform erzeugen Scheinwidersprueche und Zaehl-Inkonsistenzen**  
Befunde: Z1-03 (hoch), B5 Punkt d (hoch, unverifiziert), B2-Teil '0.0125 neben 1,25 %' (verifiziert, mittel)  
Invariante: Jeder T-Box-Parameter hat genau eine kanonische Darstellung im Modell (Typ, Einheit, Normalform als Code) und je Zielgruppe genau eine Anzeigeform aus einer Quelle; zwei Darstellungen desselben Werts sind eine Diskrepanz der Klasse 'repraesentation', die ohne Verwerfen einer Lesart aufgeloest wird und in jeder Darstellung von einem Wertkonflikt unterscheidbar bleibt.

**K4 Handgepflegte Rahmen- und Skill-Doku driftet gegen Code**  
Befunde: B3 (hoch), Z3-09 (niedrig), Z1-10 (niedrig), Z1-11 (niedrig), Z1-02 Doku-Teil (Abschn. 3 vs. 5), Z3-02 Doku-Teil (Abschn. 4, README --rolle)  
Invariante: Jede normative Aussage ueber Gate-Menge, Rollen, Zustaende, Versionen, Skill-Zahl und Modulzahl hat genau eine Quelle (Code oder generiertes Dokument); Prosa zitiert sie oder ist an einen benannten Commit gebunden, und ein Drift-Test schlaegt an, wenn Prosa und Quelle auseinanderlaufen (wie heute schon fuer landkarte.md).

**K5 Fachdokumente verschweigen Rahmenbedingungen; das Restrisiko-Bild haengt vom zuerst gelesenen Dokument ab**  
Befunde: B5 (hoch), B8 (mittel), Z3-05 (hoch), Z3-01 Fachbericht-Teil, Z3-07 Merge-Stand-Teil, B9 (hoch), B6 (hoch), B1-Rest ('unveraendert')  
Invariante: Der an Fuehrung oder Pruefer adressierte Bericht enthaelt alle Abgrenzungen, die die Artefakte tragen — Fiktion/Simulationsschluessel, KI-Besetzung und Mandate, Pruefabdeckung (Zellen, Stichtagsgroessen), Toleranzen mit Grund, Systemaenderungen im Lauf und Stand der Uebernahme — an einem Ort; keine Abgrenzung erscheint nur in der Seite oder nur im Bericht.

**K6 Register der Konsumenten-Dokumente: Entwickler-Bezeichner, ASCII-Umschrift, zwei Werkzeuggenerationen**  
Befunde: B2 (verifiziert, mittel), B7 (mittel), B4 (mittel)  
Invariante: Konsumentenseitige Texte zeigen keinen Bezeichner, dessen Aufloesung nur im Code steht (Beschriftung deterministisch aus einem Woerterbuch), tragen Unternehmensorthographie und werden auf dem Branch erzeugt, der veroeffentlicht wird — eingecheckte Zahlen kommen aus demselben Datenmodell wie die generierten.

**K7 Nebenpfade der Nachweiskette: Mutationen ohne Kommando und Ledger, Werkzeugpfade ohne Test**  
Befunde: Z1-06 (mittel), Z3-04-Rest (Kaskaden-Aufruf, vorlaeufige Aufloesungen), Z3-06 (mittel), Z1-09 (mittel; bestaetigt: 'paketpfad' undefiniert, 0 relative Importe in src/), Z3-07 Korrektur-Protokoll nicht gepinnt  
Invariante: Jede Mutation eines Fall-Artefakts (auch vorlaeufig, auch ein Mandat) geschieht ueber ein Kommando mit Akteur-Konvention und Ledger-Eintrag; jeder Zweig eines Pruef- oder Kartenwerkzeugs wird von mindestens einem Test durchlaufen, sodass es urteilt statt abbricht.

### Abhaengigkeiten zwischen den Zielen

- **Z3-04 (Z3) -> B1 (Z2, widerlegt)** (gleiche Behauptung, gleiche Widerlegung): Z3-04 wiederholt B1 ('reproduzierbar ist er aus Git nicht') und war unverifiziert. Die B1-Widerlegung gilt eins zu eins; eigene Nachrechnung: sechs Commits (8c5698c, abd31ca, bd41f56, 1bb4e3d, e4230e9, 4b1abf0) ergeben exakt die quellcode_sha256 der 16 Snapshots. Rest von Z3-04 (Kaskaden-Aufruf nicht persistiert, vorlaeufige Aufloesungen nicht im Rechenlauf ausgewiesen) wandert zu Z1-06/Z3-06.
- **Z1-01 (Z1) -> Z3-02 (Z3)** (gemeinsame Ursache: 'wer entscheidet' hat drei Antworten): Z1-01 findet 'OHNE Menschen' (Skill/Docstring) gegen 'nur Mensch' (P2); Z3-02 findet 'zeichnende Rolle per Schluessel' (Code) gegen 'nur Mensch' (P2). Der Z1-Skeptiker schrieb 'der Code ist eindeutig (nur Mensch)' — das ist ungenau: entscheide.py Z. 5-12 laesst mit --zeichnungsordnung jede A-Q1-zeichnende Rolle endgueltig entscheiden; nur der Alt-Weg ohne Ordnung ist 'mensch'. Ein ADR loest beide Befunde.
- **Z3-01 (Z3) -> Z1-08 (Z1) und B2 (Z2)** (Rollen-/Besetzungsluecke des Modells erscheint als Darstellungsluecke): Die Fachspez rendert je Entscheidung nur Wert und Entscheider (fachspez.py Z. 225), die Fall-Seite die Rollen-ID 'plv-aktuar'. Solange Snapshot und Entscheidung keine Besetzungsart und kein Mandat tragen, KANN keine Darstellung zeigen, dass eine KI-Session im Mandat zeichnete — die Doku-Luecke ist erst nach der Schema-Erweiterung schliessbar.
- **Z1-03 (Z1) -> B5 Punkt d (Z2)** (Ontologie-Unschaerfe macht Fall-Doku inkonsistent): Weil die Diskrepanz keine Klasse (wertkonflikt/repraesentation) kennt, zaehlt die Seite '2 Feststellungen ueber 6 Zellen + 6 Stellen in zwei Schreibweisen' und der Bericht 'drei Typen, vierzehn Einzelentscheide'. Mit einer Klassifikation im Modell haben beide dieselbe Zaehlbasis; ohne sie bleibt jede Angleichung Handarbeit.
- **Z1-03 (Z1) -> B2 (Z2, '0.0125 neben 1,25 %')** (fehlende Normalform erscheint als Formatierungsdefekt): Der Renderer formatiert Lesarten, aber nicht den gewaehlten Wert (darstellung.py Z. 290 stringifiziert vorher). Ein Parameter-Katalog mit Einheit und Anzeigeform in tbox.py wuerde beide Stellen aus einer Quelle speisen statt zwei Formatierpfade zu pflegen.
- **Z1-04 (Z1) -> Z3-07 (Z3)** (Gate ohne Inhalt erklaert Gate ohne Beleg): A-K1 hat in gate_entscheid.py keinen gate-spezifischen Zweig (Stichprobe: nur A-M1/A-M4/AKTUARIELLE_ABNAHMEN verzweigen), TBOX_VERSION wurde nie angehoben. Dass im Lauf 23 Aenderungen inkl. BREAKING ohne A-K1 durchgingen und die Agenten die Klasse 'Parametrierung vs. Erweiterung' selbst zogen, ist die Folge: Es gibt nichts, was A-K1 pruefen wuerde.
- **Z3-03 (Z3) -> B2 (Z2, Rollen-Glossar) und Z3-09 (plv-va/plv-aktuar)** (Rollenluecke des agentischen Modells erscheint als Doku-Luecke): Es gibt kein versioniertes Rollen-Register; die Zuordnung plv-aktuar -> 'Verantwortlicher Aktuar' steht nur in dev-docs/regie.md (Stub). Deshalb kann weder die Seite einen Klartext rendern noch der Skill einen einheitlichen Namen zitieren.
- **Z3-05 (Z3) -> B9 (Z2)** (dieselbe Luecke fuer zwei Zielgruppen): Das fehlende Pruefer-Dossier (Ziele, Rollen Mensch/KI, Modelle, Eingriffspunkte, Datenfluss) und der fehlende IT-Abschnitt 'Betrieb und Sicherheit' (was sieht der Agent, welcher Anbieter, was verlaesst das Haus nie) sind ein Dokument mit zwei Kapiteln, nicht zwei Dokumente.
- **B8 (Z2) -> Z3-01/Z3-05 (Z3, Fachbericht ohne KI)** (gemeinsame Klasse: Fachbericht verschweigt Rahmenbedingungen): Simulationscharakter, KI-Besetzung der Zeichnungsrolle und Mandate fehlen im selben Dokument (docs/faelle/baldrian-lauf2.md); eine Kopfzeile plus ein Abschnitt 'Rollen, Mandate, eingesetzte Modelle' schliesst drei Befunde.
- **B3 (Z2) -> Z1-02 (Abschn. 3 vs. 5), Z3-02 (Abschn. 4), Z3-09 ('zehn Skills')** (gemeinsame Ursache: handgepflegtes Pipeline-Dokument im Erst-Lesepfad): Drei Pruefer stolpern im selben Dokument (migrations-pipeline-v01.md, selbst als 'teilweise ueberholt' markiert) ueber verschiedene Saetze. Loesung ist eine: aus dem Erst-Lesepfad nehmen oder an generierte Quellen binden.
- **Z1-06 (Z1) -> Z3-06 (Z3) und Z3-04-Rest** (gleiche Invariante, andere Stelle): Vorlaeufige Aufloesung per Ad-hoc-Skript ohne Ledger (Z1-06), Mandate als Chat-Notiz ohne Snapshot (Z3-06), Kaskaden-Aufruf nicht persistiert (Z3-04-Rest): jeweils eine Kettenmutation ohne Kommando und Beleg.
- **B4 (Z2) -> B2 (Z2)** (Reparaturort liegt auf anderem Branch): Der B2-Skeptiker fand den Seitenerzeuger im Worktree vorzeige-url (0a787e1), nicht auf dem geprueften Branch. Beschriftungs-Fixes muessen dort landen; der Merge-Plan (memory: Seiten-Folge-PR nach Haupt-Merge) bestimmt die Reihenfolge.

### Massnahmenplan (priorisiert)

| Rang | Massnahme | Schliesst | Wann | Aufwand | Entscheidung noetig |
|---|---|---|---|---|---|
| 1 | ADR 'Zeichnungsordnung und Vier-Rollen-Modell: Rolle aus Schluessel, Besetzung, Mandat' schreiben und die Norm nachziehen: P2/P4 in prinzipien.md (inkl. Beleg des 'A-K1-artigen Vorgangs'), ADR-008 Z. 50 (Nachtrag), AGENTS.md Working Agreements, README Abschnitt --rolle (Z. 431-434), Pipeline-Dokument Abschnitt 4, Skills migrationsfall-durchfuehren (plv-va -> plv-aktuar, Z. 353-366), pruefe-migrationscontrolling, bereite-fachkonflikt-auf. Dabei die Abzugsabgleich-Regel entscheiden: empfohlen Option (a) 'nur Beleg-Erzeuger' — 'OHNE Menschen' aus SKILL.md Z. 86-89 und abzugsabgleich.py Z. 3-4/33 streichen; sonst Option (b) als 'noch nicht gebaute Rolle' in skill-architektur.md eintragen. Semantik des Snapshot-Felds 'rolle' (Autoritaetsmarker) festschreiben. .claude/.agents-Paritaet und Wortlisten-Test test_rollen_skills_tragen_ihre_haerte_grenzen anpassen. | Z1-01, Z3-02, Z3-01 (Norm-Teil), Z3-09 (Rollenname), Z3-03 (Namen) | vor | 1-2 Tage | Maintainer: (1) Ist die KI-Besetzung der zeichnenden Rolle Regelfall oder Vorfuehr-Ausnahme? (2) Abzugsabgleich Option a oder b? |
| 2 | Fachbericht docs/faelle/baldrian-lauf2.md (und -veraenderungen.md) ergaenzen: Kopfzeile 'Vorfuehrfall: fiktives Unternehmen, synthetischer Bestand, Zeichnung mit Simulationsschluessel (Fingerabdruck 162817c9...)'; Abschnitt 'Zeichnende Rollen, Mandate, eingesetzte Modelle' (plv-aktuar = Verantwortlicher Aktuar, besetzt durch KI-Session im vom Maintainer erteilten Mandat; Extraktionsmodell aus akteure.json); Abschnitt 'Was geprueft ist und was nicht' (Golden Master 1 von 6 Zellen mit Verweis auf A-M1..A-M4-Vollabdeckung; dk_stichtag_2 811/834 mit Abgangs-Kreuzprobe; A-M2 100 ct mit fachlicher Begruendung oder Verengungs-Ankuendigung; Diskrepanz-Zaehlung auf eine Lesart; 23 Systemaenderungen, elf ueberholte Runden, Stand der Uebernahme in main/PR #11); 'einzigen, unveraenderten Systemstand' durch 'denselben Stand 4b1abf0 fuer alle fuenf finalen Zeichnungen (Pruefsumme entspricht dem committeten Paketstand)' ersetzen. falldaten.py die Golden-Master-Zellenabdeckung als Abgrenzung fuehren lassen. | B5, B8, Z3-05 (Fachbericht-Teil), Z3-01 (Fachbericht-Teil), Z3-07 (Merge-Stand-Teil), B1-Rest, Z3-04-Rest (Fussnote) | vor | 0,5-1 Tag | Fachverantwortlicher (Rolle Verantwortlicher Aktuar): fachliche Begruendung der A-M2-Toleranz von 100 ct; Maintainer: Wortlaut der KI-Offenlegung im VU-Dokument (Fiktionsgrenze) |
| 3 | Snapshot- und Entscheidungs-Schema um den Vollzug erweitern: zeichnung += {besetzung: 'mensch'|'agent-im-mandat', akteur: '<modell>/<skill>@<sha>' (Pflicht bei Agenten-Besetzung), mandat_sha256}; neuer Snapshot-Typ 'mandat' der Eskalationsrolle 'mensch' (Rolle, Gates, Reichweite, Dauer, Begruendung), auf den Agenten-Zeichnungen verweisen; gate_entscheid und entscheide verweigern Agenten-Besetzung ohne Mandatsverweis; Zeichnungsordnung um Besetzungsart je Rolle; A-M4 pinnt Reibungs- und Korrektur-Protokoll als Pflichtbelege; Auswertung zaehlt 'Governance-Eingriffe' getrennt von 'Infrastruktur-Eingriffen'. Migrationsregel fuer Alt-Snapshots (Lauf 2 bleibt lesbar). | Z3-01, Z3-06, Z3-05 (Modell-Register-Teil), Z3-07 (Pinnen des Protokolls) | Schema-Entscheid vor, Umsetzung kann nach (BREAKING fuer Snapshots) | 2-3 Tage | Maintainer: Schema-Aenderung und Umgang mit den 16 Alt-Snapshots (Nachtrag oder ausgewiesene Luecke) |
| 4 | Einstiegs- und Rahmendoku auf den Stand nach Lauf 2: ONBOARDING Abschnitt 1 (Kern 3.4.0, ADR-013 statt Kreuzcheck-Schiene, Lesepfad skill-architektur -> ADRs -> Landkarte), migrations-pipeline-v01.md aus Erst-Lesepfad und IT-Seite nehmen und Abschnitt 3/5 (vier vs. drei Zustaende) sowie 'zehn Skills' angleichen, lieferungen/README um baldrian-2, README 'Die Migrationsfaelle' -> docs/faelle/, README-Pfeil-Zeile 'Pfeile = Datenfluss; Import-Erlaubnis ist ein Netz, siehe landkarte.md', Docstring-Zahlen in impact.py/landkarte.py an Commit binden oder auf landkarte.md verweisen, landkarte-Docstring 'gleicher Repo-Stand UND gleiches faelle/'. Skill migrationsfall-durchfuehren Z. 73 vs. 436 (Gate-Menge) auf GUELTIGE_GATES/BELEGROLLEN zitieren lassen. | B3, Z3-09, Z1-10, Z1-11, Z1-02 (Doku-Teil) | vor | 0,5-1 Tag | keine (AGENTS.md-Aenderungen direkt im Branch) |
| 5 | code_karte.py _absolut: 'paketpfad' durch 'anker' ersetzen (Z. 163); Test mit Mini-Paket ('from . import x', 'from ..a import b') durch baue_karte; Test, dass jeder ImportFrom-Level in src/ verarbeitet wird. | Z1-09 | vor | 1 Stunde | keine |
| 6 | Register der Konsumenten-Dokumente: Beschriftungs-Woerterbuch im Seitenerzeuger (Pruefgroessen dk_stichtag_2 -> 'Deckungskapital zum Kontrollstichtag', Rollen plv-aktuar -> 'Verantwortlicher Aktuar (Zeichnungsordnung)', passed -> 'bestanden' ueber _urteilswort), str()-Cast in darstellung.diskrepanz_gruppen Z. 290 vor _lesart_text entfernen, Umbau-Messung mit Pfad/Commit nur in der technischen Sicht; dieselbe Klasse in werkzeuge/fallbericht.py; Rollen-Klartext einmal in docs (ADR aus Rang 1); docs/faelle/ in Unternehmensorthographie oder deterministische Umschrift-Aufloesung in unternehmensseite.py, Regel in dokumentiere-system; vorzeige-url-Strang vor der Vorfuehrung mergen oder werkzeuge/README-Hinweis 'Unternehmensseiten dieses Branches tragen Lauf-1-Zahlen'; Drift-Pruefung eingecheckter Zahlen gegen das Datenmodell. | B2, B7, B4 | B7 und B4-Hinweis vor; Woerterbuch nach (liegt auf Branch vorzeige-url) | 1 Tag | Maintainer: Merge-Reihenfolge vorzeige-url gegen Veroeffentlichung; Orthographie-Regel fuer docs/faelle/ |
| 7 | Pruefer-Dossier 'Das KI-System der Bestandsmigration — Beschreibung fuer Pruefer' in docs/ (Unternehmenssprache): Zweck, Rollen mit Kennzeichnung Mensch/KI, Modelle je Rolle und Lauf, Eingriffspunkte (Gates, Mandate, Abbruchkriterien), was KI strukturell nie tut, Datenfluss (was der Agent sieht, welcher Anbieter, was das Haus nie verlaesst), Nachweise mit Fundorten, bekannte Grenzen. Dazu versioniertes Rollen-Register in docs/architektur (Rolle -> Auftragsprofil ohne Aufloesungen -> Skills -> Werkzeuge/Schreibwirkung -> Gates -> Abbruchkriterien), Zeichnungsordnung als Vorlage im Repo, Test 'Rollen einer Ordnung gegen Register', regie.md aus AGENTS/ONBOARDING verlinken. A-M4-Zustaendigkeit in ADR-010-Nachtrag und Grundsatzdokumentation 9.15 klaeren. Auf it/index.md Abschnitt 'Betrieb und Sicherheit' (Laufzeit, Schluesselverwahrung/ADR-008, Agenten-Laufzeit, Veroeffentlichungsweg), auf aktuariat/index.md Kennzahlen-Block aus dem Datenmodell. | Z3-05, Z3-03, Z3-08, B9 | nach (aber vor einer Vorfuehrung an Aufsicht/Revision) | 2-3 Tage | Maintainer: welche Inhalte aus regie/ (Auftragsprofile, Modelle je Rolle) ins versionierte Repo duerfen; Fachverantwortlicher: A-M4 als Mitzeichnung des Migrationsprojekts oder 'Verantwortung = Erstellung und Vorlage' |
| 8 | Design-Dokument des Falls: aus der Ausgestaltungs-Chronik ein datiertes Fachdokument 'Ausgestaltung Baldrian KLV TG2015' (Abschnitte ohne Status-Log) ableiten und in die Positivliste UEBERNEHMEN aufnehmen oder als abgeleitet/berichte/ausgestaltung.html rendern; Korrektur-Protokoll als Kurzfassung 'Korrekturen des Laufs' (Nr., Grund, Gebiet) fuer die technische Sicht; Migrationskonzept-Instanz (Kapitel 1-4, 8-11) fuer Baldrian aus Abschlussbericht, Lieferschein und Auskuenften befuellen. | B6 | nach | 1 Tag | Fachverantwortlicher: Freigabe der Konzept-Instanz laut Vorlage (Projektleitung, Quellsystem, Fachexperte Aktuariat) |
| 9 | Parameter-Katalog als Daten in tbox.py (Name, Typ, Einheit, Wertebereich, Normalform, Beispiel), Validator in Parametrierungszelle, Wiederverwendung im generierten JSON-Schema fuer Extraktions-Agenten (ersetzt Skill-Prosa '1,75 % => 0.0175'); Diskrepanz um Klassifikation (wertkonflikt / repraesentation / einheit) und Aufloesungsart 'aequivalent' ohne Verwerfen einer Lesart; Fachspez Abschnitt 7 rendert Klasse, Rolle, Beleg (Datei + Hash-Praefix) und vorlaeufig->endgueltig-Historie; Seite und Bericht zaehlen Diskrepanzen aus dieser Klasse. Dies ist der erste echte Schema-Sprung und damit Anwendungsfall fuer Rang 10. | Z1-03, Z1-08 (Fachspez-Teil), B5 Punkt d, B2 (Formatierungs-Teil) | nach (BREAKING A-Box-Schema) | 2-4 Tage | Fachverantwortlicher: Normalform 'tafel' (Basisname oder mit Unisex-Suffix); ob eine Aufloesung 'aequivalent' ohne Verwerfen einer Lesart aufsichtsrechtlich tragbar ist |
| 10 | Versions- und Uebergangsvertrag der T-Box: Uebergangstabelle je Enum (Zustand, Diskrepanz.status, Erweiterungsstelle.status, StrukturUrteil.ergebnis: Produzent, Abloeser, Test) in tbox.py oder ADR; 'mehrdeutig' entweder mit Semantik (mehrere Fundstellen in EINER Quelle, Produzent im Fragment-Schema, Aufloesungsweg) oder aus Enum, P3, Skill, ONBOARDING, Coverage und merge-Docstring streichen; Validator abox.tbox_version gegen TBOX_VERSION (Fehler oder ausgewiesene Migration); Schema-Hash-Test der Feldmenge gegen eingecheckten Snapshot, der bei Aenderung einen Versionssprung verlangt; A-K1 einen Gegenstand geben (Snapshot pinnt tbox.py-Hash, alte/neue Version, Aenderungsartefakt; eigener Zweig in gate_entscheid); ADR-007 Regel 4 (Knoten-Status) umsetzen oder formell zurueckziehen; Familienbegriff auf eine Quelle; familienneutrale Ontologie-Module an system/ontologie binden. | Z1-02, Z1-04, Z1-05, Z3-07 (A-K1-Teil) | nach | 2-3 Tage | Maintainer: 'mehrdeutig' streichen oder definieren; ADR-007 Regel 4 umsetzen oder zurueckziehen; Familienquelle T-Box-Enum oder Registry |
| 11 | Nebenpfade der Kette: entscheide um --vorlaeufig erweitern (Akteur-Konvention, Ledger, kein Schluessel) und das Skript im Skill migrationsfall-durchfuehren Z. 162 ersetzen; 'abgeleitet/skripte' in ADR-002 definieren oder verbieten; Feldfilter fuer --alle-vorlaeufigen; Entscheidung.beleg zur Liste mit Art (rechnung / klaerung / tarifwerk), Eingang-Register um Art-Feld, P-Q3 prueft alle Beleg-Hashes; Kaskaden-Rezept je Fall persistieren; Rechenlauf weist vorlaeufige Aufloesungen aus; leichtes Pruef-Gate 'Systemaenderung im laufenden Fall' (Klasse Parametrierung/Erweiterung/T-Box, menschliche Bestaetigung der Klasse) oder mindestens A-M4-Pflichtbeleg der Aenderungs-Commits seit Fall-Anlage. | Z1-06, Z1-07, Z3-07 (Gate-Teil), Z3-04-Rest | nach | 2-3 Tage | Maintainer: eigenes Gate P-S1 oder A-M4-Pflichtbeleg; Ort fuer Fall-Werkzeuge (ADR-002) |
| 12 | Generierte Modellsicht: Landkarte um Modus 'modell' erweitern, der aus den Pydantic-Klassen ein Klassen-/Zustandsdiagramm (Mermaid) mit Uebergaengen aus der Tabelle von Rang 10 erzeugt, drift-geprueft wie landkarte.md; handgepflegte Tabelle in Abschnitt 3 des Pipeline-Dokuments durch die generierte Sicht ersetzen. | Z1-08 (Diagramm-Teil) | nach | 1-2 Tage | keine |

### Offene Fragen an den Maintainer

- Ist die Besetzung der zeichnenden Rolle plv-aktuar durch eine KI-Session im erteilten Mandat der beabsichtigte Regelfall des Vier-Rollen-Modells oder eine Ausnahme des Vorfuehrlaufs? Davon haengt ab, ob ADR-008 Z. 50, P2 und die Skills umgeschrieben werden oder der Lauf 2 als ausgewiesene Abweichung dokumentiert wird.
- Abzugsabgleich: Option (a) ausschliesslich Beleg-Erzeuger (Code-Stand heute, 'OHNE Menschen' streichen) oder Option (b) Entscheidungsart 'automatisch_belegt' mit Gate, Ledger, Schwelle und Fachspez-Kategorie bauen?
- prinzipien.md verlangt fuer Prinzipien-Aenderungen einen 'A-K1-artigen Vorgang mit dem Maintainer' — belegt ist fuer 404974d nur ein Maintainer-Go im Korrektur-Protokoll. Soll der P2-Nachzug rueckwirkend als solcher Vorgang dokumentiert werden, und in welcher Form (Snapshot der Rolle mensch, ADR-Nachtrag)?
- 'mehrdeutig': streichen oder mit Semantik 'mehrere Fundstellen innerhalb EINER Quelle' (Fall 'k' im Tarifrechner-Fragment) definieren und im Fragment-Schema produzierbar machen?
- Normalform 'tafel' (Basisname DAV2008_T_NR oder Name mit Unisex-Suffix) und ob eine Aufloesungsart 'aequivalent' ohne Verwerfen einer Lesart fachlich und aufsichtsrechtlich tragbar ist — Frage an den Fachverantwortlichen.
- A-M4-Zustaendigkeit: Mitzeichnung des Migrationsprojekts (programmleiter + plv-aktuar) in der Zeichnungsordnung, oder Klarstellung in ADR-010/9.15, dass 'Verantwortung Migrationsprojekt' Erstellung und Vorlage meint?
- Welche Inhalte des Spielleiter-Bereichs regie/ (Auftragsprofile der Rollen, Schreibgrenzen, eingesetzte Modelle je Rolle) duerfen als Rollen-Register ins versionierte Repo, ohne Aufloesungen des Vorfuehrfalls preiszugeben?
- ADR-007 Regel 4 (Knoten-Status in_migration/abgenommen): umsetzen oder formell zurueckziehen? Familienbegriff aus T-Box-Enum oder aus der Kern-Registry?
- Systemaenderungen im laufenden Fall: eigenes leichtes Gate mit menschlicher Bestaetigung der Klasse (Parametrierung/Erweiterung/T-Box) oder genuegt es, wenn A-M4 das Korrektur-Protokoll und die Aenderungs-Commits als Pflichtbeleg pinnt?
- Reihenfolge vorzeige-url gegen Veroeffentlichung: Der Seitenerzeuger mit den Beschriftungs-Defekten liegt auf vorzeige-url (0a787e1), die eingecheckten Unternehmensseiten des geprueften Branches tragen Lauf-1-Zahlen. Wird vorzeige-url vor der Vorfuehrung gemergt, oder erhaelt werkzeuge/README einen Hinweis?
- Orthographie-Regel fuer docs/faelle/: Unternehmensdokumente mit echten Umlauten (wie vorzeige-seite/) oder deterministische Umschrift-Aufloesung beim Einspielen?
- Umgang mit den 16 Alt-Snapshots des Laufs 2 nach einer Schema-Erweiterung um Besetzung/Mandat: rueckwirkender Mandats-Snapshot der Rolle mensch mit Verweis, oder ausgewiesene Luecke im Fachbericht?

### Was das Review nicht pruefen konnte

- Die Spielleiter-Bereiche docs-local/, simulation/ und regie/ waren tabu. Aussagen wie 'Auftragsprofile und Modelle je Rolle existieren nur dort' (Z3-03, Z3-05) beruhen auf ihrer Abwesenheit im versionierten Repo, nicht auf Einsicht; ob dort ein Mandatstext, ein Modell-Register oder eine Rollen-Definition liegt, die die Luecke fuer den Maintainer schliesst, ist ungeprueft.
- Verifiziert durch Skeptiker sind nur Z1-01, Z1-02, B1, B2, Z3-01, Z3-02. Ich habe zusaetzlich nachgeschlagen: die Pruefsummen-Nachrechnung (alle 6 Commits gegen 16 Snapshots, bestaetigt B1-Widerlegung und widerlegt Z3-04-Kern), Z1-09 (paketpfad undefiniert, 0 relative Importe in src/, bestaetigt), die Kernbehauptungen von Z1-04 (kein A-K1-Zweig in gate_entscheid, TBOX_VERSION seit 0f65e93 unveraendert, tbox_version nur durchgereicht — bestaetigt) und entscheide.py Z. 5-12/138-156 (Rolle aus Schluessel, bestaetigt Z3-02). Alle uebrigen Befunde (Z1-03, Z1-05 bis Z1-08, Z1-10, Z1-11, B3 bis B9, Z3-03, Z3-05 bis Z3-09) sind unverifiziert und im Plan entsprechend leichter gewichtet.
- Keine Tests ausgefuehrt, kein Code veraendert; die Nachrechnung der Quelltext-Pruefsumme erfolgte rein lesend ueber git ls-tree/cat-file. Ob die Suite auf dem Stand 4b1abf0 gruen war, ist aus dem Review nicht belegt (nur die Snapshots behaupten es).
- Die Nachschlagbarkeit des gezeichneten Stands setzt voraus, dass 4b1abf0 und die fuenf Vorstaende oeffentlich erreichbar werden; laut Arbeitsstand sind elf Commits ab b0cb63d ungepusht. Ob die referenzierten Commits nach Rebase/Squash im PR #11 noch existieren, konnte nicht geprueft werden — ein Rebase wuerde die Snapshot-Commits verwaisen lassen, ohne dass die Pruefsumme das anzeigt.
- Die generierte Fall-Seite (runs/seite) stammt aus dem Branch vorzeige-url (Worktree, HEAD 0a787e1), nicht aus dem geprueften Branch fallbericht; Reparaturorte fuer B2 gelten dort. Ob dieser Worktree dem letzten Stand des Strangs entspricht, ist nicht geprueft.
- Fachliche Richtigkeit wurde nicht geprueft: die 14 Diskrepanz-Entscheide, die Zins-Lesart 1,25 %, die A-M2-Toleranz von 100 ct, die aktuariellen Werte und die Behandlung der Herabsetzungsanteile sind ungeprueft uebernommen; das Review ist kein Aktuar-Review.
- Welches Modell die Aktuar- und die Programmleiter-Session fuhren, ist aus Repo und Fall nicht feststellbar (einziger Modellnachweis: akteure.json fuer die Extraktion). Die Behauptung 'KI-Session' fuer plv-aktuar stuetzt sich auf das Reibungsprotokoll des Falls und dev-docs/regie.md, nicht auf einen signierten Beleg.
- Die 'Zehn-Minuten-Lesarten' (Aufsichts-Pruefer, Fach- und IT-Fuehrungskraft, zweites Haus) sind Konstruktionen der Pruefer; ob reale Adressaten so lesen, ist eine Annahme, keine Beobachtung.
- Nicht geprueft: die byte-identische .claude/.agents-Paritaet nach den vorgeschlagenen Skill-Aenderungen, die Vollstaendigkeit der Wortlisten-Tests (test_agent_workflow_docs.py, test_rollen_skills_tragen_ihre_haerte_grenzen) und ob der Peer-Zustand der Lieferung baldrian-2 (AVB-PDF, PDF-Mitteilung) reproduzierbar den Lauf 2 ergibt.
- Sicherheitsfragen (Schluesselverwahrung in der Praxis, Datenfluss zum Modellanbieter, Rotation) konnten nur als Doku-Luecke (B9) festgestellt werden; der tatsaechliche Betrieb war nicht Gegenstand.

## Z1 — Ontologiemodell

### Gesamturteil des Pruefers

Der Kern des Ontologiemodells — Aussage mit Provenienz, Widerspruch als Objekt, deterministischer Merge, Spez als validierte Projektion, Gates, die ihre Vorbedingungen rechnen — ist scharf, getestet und im Vorfuehrfall durchgehend nachweisbar; das ist mehr, als die meisten Migrationsvorhaben je an Modell haben. Unscharf ist der Rand, und zwar dort, wo ein zweites Haus zuerst hinsieht: ob Maschinen Widersprueche aufloesen duerfen (zwei Antworten im Repo), was 'mehrdeutig' bedeutet (Zustand ohne Produzent), welche Normalform ein Parameter hat (sechs Scheinkonflikte im Fall) und wie die T-Box selbst veraendert wird (Version nie gesprungen, A-K1 ohne Inhalt). Die Darstellung traegt die Codebasis hervorragend, das Modell selbst aber nur als handgepflegte Tabelle, und die Fachspez zeigt weniger Nachweiskette, als das Modell besitzt. Fuer die Uebernahme durch ein zweites Haus muessten die vier hohen Befunde geschlossen sein; die mittleren sind Erhaertung, die niedrigen Politur. Die Sammlung hat die Widersprueche richtig gesehen, aber die groesseren Klassen (Zustaende ohne Uebergang, Parameter ohne Normalform, nominale Versionierung) nicht, weil sie den Fall nicht geoeffnet hat.

### Was traegt (Staerken)

- Die Aussage-Invarianten sind Konstruktionsregeln, nicht Konvention: 'belegt ohne Beleg', 'nicht_belegt mit Wert', 'widerspruechlich ohne diskrepanz_id' sind unkonstruierbar (aussage.py Zeile 95-125) und durch Tests gesichert (test_ontologie.py Zeile 63-93).
- Der Widerspruch ist ein vollwertiges Modellobjekt mit append-only-Historie, Beleg-Hash und Rollenbindung aus der Zeichnungsordnung; der Vorfuehrfall zeigt die komplette Kette vorlaeufig (Agent) -> endgueltig (plv-aktuar, Beleg abzugsabgleich-zins.json mit SHA-256, ordnung_sha256) in abox.json.
- Der Merge ist deterministischer Code mit begruendeter Toleranz und nicht-transitiv-sicherer Gruppierung; Fragmente mit vorentschiedenen Konflikten werden verworfen (merge.py Zeile 62-67), getestet in test_merge_verweigert_vorentschiedene_konflikte.
- Die Kettenpruefung (kette.py) bindet die gespeicherte A-Box an Fragmente und Merge-Ledger und erlaubt Abweichungen nur ueber dokumentierte Aufloesungen — der einzige frueher unprotokollierte Uebergang ist geschlossen.
- Die Spez ist als Projektion in beide Richtungen gegen die A-Box validiert (validierung.py Zeile 50-110: jeder Spez-Wert belegt, jedes Pflichtfeld vorhanden, Tafelname aus Basis + Unisex hergeleitet).
- Menschliche Gates rechnen ihre Vorbedingungen: A-Box Pflicht, Register-Bindung, keine offenen und keine vorlaeufigen Diskrepanzen, derselbe Byte-String validiert und gehasht (gate_entscheid.py Zeile 1193-1262).
- Die generierte Landkarte ist drift-geprueft (test_landkarte_doku_ist_nicht_veraltet) und stimmt exakt mit dem Code-Stand ueberein (101 Module); Knoten-Annotation jedes Moduls und jeder Testdatei ist harter Drift (test_module_ohne_knoten_sind_harter_drift, test_testmodule_ohne_bindung_sind_drift).
- Die Dokumentation benennt ihre Grenzen ausdruecklich und nachvollziehbar: Pipeline-Dokument Abschnitt 8 und 8.1 (Parameter statt Formeln), ADR-005 'Bekannte Grenzen', Kopfzeile des Pipeline-Dokuments mit Liste der ueberholten Abschnitte.
- Der Akteur jeder Extraktion ist als <modell>/<skill>@<git-sha> erzwungen (befuellung.pruefe_akteur), der Skill-Stand ist damit Teil der Provenienz — im Fall sichtbar als 'claude-sonnet-5/extrahiere-quellfragment+verifikation@dc7c80b'.

### Lesarten (Zehn-Minuten-Test)

**Pruefer einer Aufsicht bzw. Chefaktuar eines zweiten Hauses, der das Modell in zehn Minuten aus prinzipien.md, migrations-pipeline-v01.md und einer Fachspez erfassen will**  
Versteht die Stufenlogik, dass jede Aussage Provenienz traegt und dass Widersprueche Menschen entscheiden. Nimmt aus der Fachspez mit, dass 14 Quellenwidersprueche vom Verantwortlichen Aktuar entschieden wurden — ohne zu sehen, dass sechs davon Darstellungsunterschiede waren, dass es Belege mit Hash gibt und welche Rolle gezeichnet hat.
  
Fehlt: Ein Klassen-/Zustandsdiagramm des Modells mit Uebergaengen; Ein Parameter-Katalog mit Typ, Einheit und Normalform; In der Fachspez: Beleg-Hash, Rolle und Historie je Entscheidung
  
Verwirrt: Ob der Abzugsabgleich Widersprueche 'OHNE Menschen' aufloesen darf (Skill/Modul) oder nicht (Prinzipien, Pipeline, Code); Was 'mehrdeutig' ist und warum es in einer Liste vier, in der naechsten drei Zustaende gibt; Warum sechs tafel-Konflikte als 'Meldung verworfen' entschieden wurden, obwohl die Meldung richtig war; Was Gate A-K1 konkret prueft und wann TBOX_VERSION springt
  
Passendes Format: Generiertes Modelldiagramm (Mermaid, drift-geprueft) plus Parameter-Katalog als Tabelle in der Fachspez

### Befunde

| Nr | Schwere | Titel | Verifikation |
|---|---|---|---|
| Z1-01 | hoch | Zwei gegensaetzliche Aufloesungsregeln: 'OHNE Menschen' in Skill und Modul gegen P2, Skill-Architektur und das einzige implementierte Aufloesungswerkzeug | bestaetigt, Schwere hoch |
| Z1-02 | hoch | Zustaende und Urteilswerte ohne Erzeugungsregel: 'mehrdeutig' hat weder Produzenten noch Definition; Klasse Enum-Wert ohne Uebergang | bestaetigt, Schwere mittel |
| Z1-03 | hoch | Parameterfelder der T-Box ohne Wertebereich und Normalform — Repraesentationsunterschiede werden zu Quellenwiderspruechen | nicht verifiziert |
| Z1-04 | hoch | 'Versionierte T-Box' und Gate A-K1 sind nominal: Version nie angehoben, nirgends geprueft, Gate ohne eigenen Inhalt | nicht verifiziert |
| Z1-05 | mittel | Widerspruch zwischen ADR-007 und T-Box beim Knoten-Lebenszyklus, Familienbegriff mit zwei Quellen und familienneutrale Ontologie an 'klv' gebunden | nicht verifiziert |
| Z1-06 | mittel | Vorlaeufige Aufloesung ist die einzige A-Box-Mutation ohne Kommando und Ledger — im Fall per Ad-hoc-Skript in einem undefinierten Ordner | nicht verifiziert |
| Z1-07 | mittel | Evidenzquellen jenseits der drei Quellarten (Auskunftsschreiben) haben im Modell keinen Ort — Entscheidungen berufen sich in Prosa darauf | nicht verifiziert |
| Z1-08 | mittel | Die Darstellung zeigt die Codebasis, nicht das Modell: keine generierte Sicht auf Klassen, Zustaende, Uebergaenge und Entscheidungsketten | nicht verifiziert |
| Z1-09 | mittel | Ungetesteter Vertrag in der Code-Karte: _absolut referenziert eine undefinierte Variable | nicht verifiziert |
| Z1-10 | niedrig | Prosa-Kennzahlen und Determinismus-Aussagen in Docstrings, die der Code nicht mehr deckt | nicht verifiziert |
| Z1-11 | niedrig | Pfeil-Semantik der Architektur-Darstellung undefiniert: README-Kette und erzwungene Erlaubnismatrix meinen Verschiedenes | nicht verifiziert |

#### Z1-01 — Zwei gegensaetzliche Aufloesungsregeln: 'OHNE Menschen' in Skill und Modul gegen P2, Skill-Architektur und das einzige implementierte Aufloesungswerkzeug (hoch, widerspruch_doku_code)

Der Skill bereite-fachkonflikt-auf und der Docstring von qa/abzugsabgleich.py erklaeren, dass eine Diskrepanz 'OHNE Menschen' aufgeloest werden darf, wenn der Abzugsabgleich die Rechner-Lesart verwirft. Derselbe Skill verbietet wenige Zeilen davor jede endgueltige Aufloesung durch den Agenten, die Skill-Architektur nennt 'entscheiden (auch nicht offensichtliche Faelle)' als Haerte-Grenze der Rolle, P2 erlaubt Agenten nur VORLAEUFIGE Aufloesung, und das Pipeline-Dokument sagt 'die Aufloesung ist ein Mensch'. Im Code existiert kein automatischer Pfad: loese_diskrepanz_auf wird nur von ontologie.entscheide aufgerufen, das --entscheider und eine Rolle verlangt; gleiche_ab hat in src/ keinen einzigen Aufrufer, nur Tests. Das Modul selbst delegiert die 'A-Box-Anbindung' an ein 'aufrufendes Gate (P7)', das es nicht gibt. Im Vorfuehrfall griff die Automatik ohnehin nicht (Quote 47 % unter der Schwelle), der Mensch entschied mit Beleg — die dokumentierte Regel ist damit weder gelebt noch implementiert.

**Wirkung auf das Ziel:** Ein zweites Haus kann aus der Dokumentation nicht entnehmen, ob das Modell eine maschinelle Aufloesung kennt. Es liest in einem Skill und einem Modul-Docstring 'ja', in Prinzipien, Skill-Architektur und Code 'nein'. Genau die Frage, die eine Aufsicht zuerst stellt (wer darf einen Quellenwiderspruch entscheiden?), hat zwei Antworten.

**Belege:**
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:86 — Rechner-Lesart verworfen, Meldungs-Lesart belegt: deterministisch belegt — die Aufloesung darf OHNE Menschen erfolgen
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:73 — Keine endgueltige Aufloesung, kein Nachfassen der Entscheidung in eigener Autoritaet — auch nicht bei "offensichtlichen" Faellen
    - `src/rechner_pipeline/qa/abzugsabgleich.py`:3 — Die Beweisfuehrung, die eine Diskrepanz OHNE Menschen aufloesen darf
    - `docs/architektur/skill-architektur.md`:29 — | Fachkonflikt-Aufbereitung | ... | entscheiden (auch nicht "offensichtliche" Faelle); Quellen-Hierarchie festlegen |
    - `docs/architektur/prinzipien.md`:19 — Agenten duerfen ausschliesslich VORLAEUFIG aufloesen (blockt jede Annahme).
    - `docs/architektur/migrations-pipeline-v01.md`:107 — Agenten-Urteil; die Aufloesung ist ein Mensch.
    - `src/rechner_pipeline/ontologie/entscheide.py`:66 — parser.add_argument("--entscheider", required=True)

**Widerlegungsversuch des Pruefers:** Gesucht nach einem Code-Pfad, der eine Entscheidung ohne menschlichen Entscheider schreibt: grep 'gleiche_ab' in src/ liefert nur die Definition; grep 'loese_diskrepanz_auf' liefert nur entscheide.py. Die Entscheidung-Klasse kennt keine Entscheidungsart 'automatisch'. Eine Lesart, dass 'OHNE Menschen' nur den Beleg meint, widerspricht dem Wortlaut 'Aufloesung ... erfolgen'. Der Skill migrationsfall-durchfuehren (Zeile 227-231) formuliert vorsichtiger ('belegt eine Lesart'), was zeigt, dass die Formulierung im anderen Skill nicht Absicht, sondern Drift ist. Nicht widerlegbar.

**Vorschlag:** Entscheiden und festschreiben: entweder (a) Abzugsabgleich ist ausschliesslich Beleg-Erzeuger (so arbeitet der Code heute) — dann 'OHNE Menschen' aus Skill und Modul-Docstring streichen und P2 unveraendert lassen; oder (b) eine Entscheidungsart 'automatisch_belegt' in Entscheidung aufnehmen, mit eigenem Gate/Ledger, Schwellenwerten und Test, und P2 um diesen Fall ergaenzen. In beiden Faellen den Widerspruch innerhalb des Skills (Zeile 73 gegen 86) beseitigen.

**Verdikt des Skeptikers:** nicht widerlegt, korrigierte Schwere hoch.  
Alle sieben Belege des Pruefers wurden geoeffnet und stimmen woertlich. Vier Widerlegungsansaetze wurden am echten Code und an den Dokumenten geprueft und scheitern:

1. Kein automatischer Pfad im Code. `gleiche_ab` liefert zwar ein Feld `automatisch_aufloesbar` (src/rechner_pipeline/qa/abzugsabgleich.py Z. 189-275), aber dieses Feld wird in src/ nirgends konsumiert — der einzige Verbraucher sind Tests (tests/test_transformation_und_abgleich.py Z. 661 ff.). Alle anderen src-Fundstellen von `abzugsabgleich` importieren nur ABS_TOL/REL_TOL (migrationssuite.py Z. 90, abnahmebericht.py Z. 121). `loese_diskrepanz_auf` hat als einzigen Aufrufer ontologie/entscheide.py (Z. 213, 226), das `--entscheider` verlangt und ohne Zeichnungsordnung nur `--rolle mensch` akzeptiert (Z. 150-151). Im Verzeichnis src/rechner_pipeline/gates/ existiert kein Abgleichs-Gate. Der Einfuehrungs-Commit fa6423e kuendigt selbst an: "die A-Box-Anbindung kommt als Gate in P7" — sie ist nie gekommen.

2. Keine dokumentierte Grenze. Der Abschnitt "Benannte, noch nicht gebaute Rollen" in docs/architektur/skill-architektur.md (Z. 67-77) fuehrt fuenf offene Rollen auf, die P7-Anbindung des Abzugsabgleichs fehlt. Auch die im Skill (Z. 88-89) versprochene Berichterstattung "in der Fachspez als eigene Kategorie" existiert nicht: grep nach "automatisch"/"abzugsabgleich" in src/rechner_pipeline/spez/ ist leer.

3. Die Gegenlesart "P2 richtet sich gegen LLM-Agenten, deterministischer Code ist davon frei" (so argumentiert der Docstring: "Code entscheidet auf Evidenz, P2/P4 bleiben intakt") traegt nicht: P2 verlangt einen "expliziten Vorgang mit benanntem menschlichem Verantwortlichen" (prinzipien.md Z. 18-19), der P4-Abschnitt sagt "die Aufloesung ist ein Mensch" (migrations-pipeline-v01.md Z. 107), und das Datenmodell `Entscheidung` kennt nur `entscheider: str` und `vorlaeufig: bool`, keinen Maschinenwert (ontologie/diskrepanz.py Z. 62-66). Der Skill fuehrt damit eine Ausnahme ein, die die Prinzipien-Quelle nicht kennt — entgegen Pflege-Regel 4 der Skill-Architektur ("Prinzipien werden in Skills ZITIERT, nicht dupliziert", Z. 90-91).

4. Der Vorfuehrfall bestaetigt die Nicht-Gelebtheit: abgeleitet/berichte/abzugsabgleich-zins.json traegt `automatisch_aufloesbar: false`, `menschlich_erforderlich: true` (0 von 2 Lesarten passen, 47,0 %); alle 14 Diskrepanzen der A-Box sind von `plv-aktuar` mit `vorlaeufig=False` entschieden, die Ledger A-Q1-*.json tragen `rolle: "mensch"`. Der Beleg ist nur bei `zins` an die Entscheidung gebunden.

Eine Korrektur am Befund: Es handelt sich nicht um Drift, sondern um eine bewusst eingefuehrte Regel (Commits fa6423e, 205b66c: "Rechnerfehler deterministisch belegt -> automatisch"), deren Verankerung in P2 und deren Maschinerie (P7-Gate, Fachspez-Kategorie) beide ausblieben. Das aendert die Bewertung nicht, praezisiert aber den Reparaturweg. Die Schwere "hoch" bleibt: Betroffen ist die Kernfrage des Ontologiemodells (wer loest einen Quellenwiderspruch auf), die Skills sind laut Skill-Architektur Z. 82-84 "Teil der Nachweiskette", und die Doku gibt zwei Antworten. Der Code selbst ist eindeutig (nur Mensch) — es ist ein Doku-Modell-Widerspruch, keine Sicherheitsluecke, was die Kategorie widerspruch_doku_code korrekt abbildet.

Praezisierung: Z1-01 (praezisiert): Der Skill bereite-fachkonflikt-auf (Z. 86-89, byte-identisch in .agents/) und der Docstring von qa/abzugsabgleich.py (Z. 3-4) erklaeren eine maschinelle Aufloesung fuer den Fall "Rechner-Lesart verworfen" als erlaubt und versprechen Protokoll- und Fachspez-Berichterstattung. Diese Regel wurde bewusst eingefuehrt (Commit fa6423e: "die Beweisfuehrung, die eine Diskrepanz ohne Menschen aufloesen DARF"), mit dem Vorbehalt "die A-Box-Anbindung kommt als Gate in P7". Tatsaechlicher Stand: (a) kein Gate, kein Aufrufer von gleiche_ab in src/, `automatisch_aufloesbar` wird nur in Tests gelesen; (b) keine Fachspez-Kategorie in spez/; (c) `Entscheidung` hat kein Feld fuer eine Maschinen-Aufloesung, `entscheide` erzwingt --entscheider und ohne Zeichnungsordnung --rolle mensch; (d) P2 ("benannter menschlicher Verantwortlicher"), der P4-Abschnitt ("die Aufloesung ist ein Mensch") und die Skill-Architektur ("entscheiden ... auch nicht offensichtliche Faelle" als Haerte-Grenze; Pflege-Regel 4: Prinzipien zitieren, nicht erweitern) kennen die Ausnahme nicht; (e) der Abschnitt "noch nicht gebaute Rollen" weist die fehlende P7-Anbindung nicht als Grenze aus. Im Vorfuehrfall griff die Regel nicht (47,0 % unter der 50 %-Schwelle) und alle 14 Diskrepanzen wurden von der Rolle plv-aktuar (mensch) endgueltig entschieden. Der Widerspruch ist damit dreifach: Skill Z. 73 gegen Z. 86 innerhalb desselben Dokuments; Skill/Docstring gegen P2/P4/Skill-Architektur; Doku-Versprechen gegen nicht existierende Maschinerie. Vorschlag des Pruefers (a oder b, plus Skill-interne Bereinigung) bleibt zutreffend; ergaenzend: falls (b), gehoert die Anbindung bis zur Umsetzung in die Tabelle "Benannte, noch nicht gebaute Rollen".

Belege des Skeptikers:
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:86 — Rechner-Lesart verworfen, Meldungs-Lesart belegt: deterministisch belegt — die Aufloesung darf OHNE Menschen erfolgen
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:88 — Sie wird im Migrationsprotokoll festgehalten und in der Fachspez als eigene Kategorie berichtet.
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:73 — Keine endgueltige Aufloesung, kein Nachfassen der Entscheidung in eigener Autoritaet — auch nicht bei "offensichtlichen" Faellen
    - `src/rechner_pipeline/qa/abzugsabgleich.py`:3 — Die Beweisfuehrung, die eine Diskrepanz OHNE Menschen aufloesen darf
    - `src/rechner_pipeline/qa/abzugsabgleich.py`:33 — die A-Box-Anbindung — Diskrepanzen einsammeln, Aufloesungen schreiben — gehoert dem aufrufenden Gate (P7).
    - `src/rechner_pipeline/qa/abzugsabgleich.py`:275 — ergebnis["automatisch_aufloesbar"] = True
    - `tests/test_transformation_und_abgleich.py`:661 — assert urteil["automatisch_aufloesbar"] is True
    - `src/rechner_pipeline/ontologie/entscheide.py`:150 — elif args.rolle != "mensch": print("entscheide: ohne Zeichnungsordnung ist nur --rolle mensch
    - `src/rechner_pipeline/ontologie/diskrepanz.py`:62 — entscheider: str = Field(min_length=1)
    - `docs/architektur/prinzipien.md`:18 — Aufloesung ist ein expliziter Vorgang mit benanntem menschlichem Verantwortlichen; Agenten duerfen ausschliesslich VORLAEUFIG aufloesen
    - `docs/architektur/migrations-pipeline-v01.md`:107 — Agenten-Urteil; die Aufloesung ist ein Mensch.
    - `docs/architektur/skill-architektur.md`:29 — | Fachkonflikt-Aufbereitung | `bereite-fachkonflikt-auf` | ... | entscheiden (auch nicht "offensichtliche" Faelle); Quellen-Hierarchie festlegen |
    - `docs/architektur/skill-architektur.md`:90 — Prinzipien (P1-P10) werden in Skills ZITIERT, nicht dupliziert; die Quelle ist das Architektur-Dokument.
    - `docs/architektur/skill-architektur.md`:67 — ## Benannte, noch nicht gebaute Rollen (mit Ausloeser)  [fuenf Eintraege; die P7-Anbindung des Abzugsabgleichs fehlt]
    - `git commit fa6423e (Commit-Botschaft)` — qa/abzugsabgleich (P6): die Beweisfuehrung, die eine Diskrepanz ohne Menschen aufloesen DARF ... die A-Box-Anbindung kommt als Gate in P7.
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/berichte/abzugsabgleich-zins.json` — automatisch_aufloesbar: false, menschlich_erforderlich: true, begruendung: "0 von 2 Lesarten passen — kein eindeutiger Beleg ... 317 von 674 Werten gestuetzt (47.0%)"
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/abox.json` — 14 Diskrepanzen, Entscheider-Menge ['plv-aktuar'], vorlaeufig False; Beleg-Bindung nur bei #zins auf abgeleitet/berichte/abzugsabgleich-zins.json
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-Q1-ce9faafd...json` — entscheider: "plv-aktuar", rolle: "mensch", begruendung: "... alle 14 Einzel-Diskrepanzen final aufgeloest (0 offen, 0 vorlaeufig, P-Q3 gruen)"

#### Z1-02 — Zustaende und Urteilswerte ohne Erzeugungsregel: 'mehrdeutig' hat weder Produzenten noch Definition; Klasse Enum-Wert ohne Uebergang (hoch, unscharfer_begriff)

P3 erklaert 'mehrdeutig' zum unterscheidbaren Zustand, der Zustand-Enum fuehrt ihn, coverage.py zaehlt ihn, spez/erzeugen.py prueft auf ihn, der Skill entwickle-im-zielsystem fordert Entwickler auf, ihn zu verwenden. Kein Code erzeugt ihn: merge.py liefert ausschliesslich belegt, nicht_belegt oder widerspruechlich und verwirft Fragmente, die einen anderen Zustand tragen; das QuellFragment kann ihn nicht ausdruecken. Nirgends steht, was 'mehrdeutig' von 'widerspruechlich' unterscheidet (innerhalb einer Quelle? ohne Diskrepanz-Objekt?) und wie er aufgeloest wuerde — die Diskrepanz-Mechanik gilt nur fuer widerspruechlich. Das Pipeline-Dokument ist mit sich selbst uneins: Abschnitt 3 nennt vier Zustaende, Abschnitt 5 'drei unterscheidbare Fehl-Zustaende' ohne mehrdeutig. Kein Test uebt den Zustand. Dieselbe Klasse: StrukturUrteil.ergebnis 'neue_produktfamilie' wird von erzeugen.py nie berechnet (Grenze in Abschnitt 8 zwar benannt, im Schema aber als berechenbarer Wert gefuehrt) und Erweiterungsstelle.status 'implementiert' wird von keinem Code gesetzt.

**Wirkung auf das Ziel:** Ein Modell, das einen Zustand benennt, aber weder Eintritt noch Austritt regelt, ist an dieser Stelle nicht uebernehmbar: ein zweites Haus muesste die Semantik erfinden. Ein Entwickler, der der Skill-Regel folgt und 'mehrdeutig' im Fragment setzt, faellt im Merge hart — Anweisung und Vertrag widersprechen sich.

**Belege:**
    - `src/rechner_pipeline/ontologie/aussage.py`:38 — MEHRDEUTIG = "mehrdeutig"
    - `src/rechner_pipeline/ontologie/merge.py`:65 — "Konflikte entstehen im Merge, nicht im Fragment"
    - `src/rechner_pipeline/ontologie/merge.py`:106 — zustand=Zustand.WIDERSPRUECHLICH,
    - `docs/architektur/migrations-pipeline-v01.md`:112 — Drei unterscheidbare Fehl-Zustaende: `nicht_belegt`
    - `.claude/skills/entwickle-im-zielsystem/SKILL.md`:56 — benannter Zustand (nicht_belegt/mehrdeutig/widerspruechlich) oder
    - `src/rechner_pipeline/spez/erzeugen.py`:175 — "parametrierung_mit_erweiterung" if formel_erweiterungen
        else "parametrierung"

**Widerlegungsversuch des Pruefers:** grep 'MEHRDEUTIG|mehrdeutig' ueber src/ (ohne aussage.py) findet nur Kommentare und Fehlertexte, keinen Konstruktor; grep in tests/ findet keinen Test auf den Aussage-Zustand. Der Merge-Docstring behauptet 'mehrdeutig/widerspruechlich entsteht erst HIER', der Code erzeugt aber nur widerspruechlich. 'neue_produktfamilie' ist in Abschnitt 8 als bewusste Grenze genannt — das entkraeftet den Einzelfall, nicht die Klasse (mehrdeutig ist nirgends als Grenze ausgewiesen).

**Vorschlag:** Fuer jeden Enum-Wert der Ontologie (Zustand, StrukturUrteil.ergebnis, Erweiterungsstelle.status, Diskrepanz.status) eine Uebergangstabelle in tbox.py oder einem ADR festhalten: wer erzeugt ihn, wer loest ihn ab, welcher Test uebt ihn. 'mehrdeutig' entweder mit Semantik und Produzent versehen (z. B. mehrere Fundstellen innerhalb EINER Quelle im Fragment) oder aus Enum, P3, Skill und Coverage streichen. Abschnitt 3 und 5 des Pipeline-Dokuments angleichen.

**Verdikt des Skeptikers:** nicht widerlegt, korrigierte Schwere mittel.  
Kern des Befunds bestaetigt, Randteile widerlegt oder als bewusste Grenze eingeordnet, Schwere von hoch auf mittel gesenkt.

BESTAETIGT (mehrdeutig): Alle Belege existieren wortgetreu. Zustand.MEHRDEUTIG (aussage.py:38) wird nirgends in src/ konstruiert; merge_feld liefert nur BELEGT/NICHT_BELEGT/WIDERSPRUECHLICH und weist Fragmente in anderem Zustand mit ValueError zurueck, obwohl der eigene Docstring (merge.py:57-59) behauptet, mehrdeutig entstehe 'erst HIER'. befuellung.py konstruiert Aussagen ausschliesslich ueber belegt()/nicht_belegt() (Zeilen 218, 224, 244, 414, 416). Das QuellFragment (befuellung.py:73-95) und FragmentWert (Zeilen 54-63) haben kein zustand-Feld — ein Extraktions-Agent KANN mehrdeutig gar nicht ausdruecken; der Extraktions-Skill kennt folgerichtig nur nicht_belegt. Kein Test in tests/ verwendet Zustand.MEHRDEUTIG (grep leer; test_ontologie.py uebt nur BELEGT/NICHT_BELEGT/WIDERSPRUECHLICH). Eine Semantik-Abgrenzung zu widerspruechlich gibt es nur implizit im Validator (aussage.py:111-125: >=2 Lesarten, kein Wert, diskrepanz_id nur bei widerspruechlich Pflicht) — d. h. mehrdeutig waere eine Konfliktaussage OHNE Diskrepanz-Objekt, und damit ohne Aufloesungsweg: entscheide.py arbeitet nur ueber Diskrepanzen, erzeugen.py:78-82 blockt die Spez bei mehrdeutig. Eintritt unmoeglich, Austritt undefiniert. Die Doku ist uneins: prinzipien.md:22 und migrations-pipeline-v01.md:94 fuehren vier Zustaende, Abschnitt 5 (Zeile 112) nennt drei Fehl-Zustaende ohne mehrdeutig. Die Darstellung im Vorfuehrfall zeigt den Zaehler 'mehrdeutig: 0' (coverage.json:14) fuer einen Zustand, der strukturell nie ungleich 0 sein kann. Verschaerfend: Der Fall ENTHAELT einen echten Mehrdeutigkeitsfall innerhalb einer Quelle ('k' als policy_fee vs. Zahlweise-Parameter, Fragment Zeile 584), der als Freitext-Anmerkung landet und vom Agenten selbst aufgeloest wurde — genau die Semantik, die der Enum-Wert benennt, aber nicht traegt. mehrdeutig ist nirgends (Abschnitt 8, ADRs) als bewusste Grenze ausgewiesen.

WIDERLEGT/RELATIVIERT: (1) Die behauptete Wirkung 'Entwickler folgt der Skill-Regel, setzt mehrdeutig im Fragment und faellt im Merge hart' ist konstruiert: Regel 2 von entwickle-im-zielsystem adressiert Code-Autoren in src/, nicht Fragment-Produzenten; das Fragment-Schema (extra='forbid', kein zustand-Feld) verhindert das Setzen bereits vor dem Merge. Es gibt keinen realen Widerspruch zwischen Anweisung und Vertrag, sondern einen benannten Zustand ohne Eintrittspfad. (2) 'neue_produktfamilie' ist in migrations-pipeline-v01.md Abschnitt 8 ausdruecklich als Grenze dokumentiert ('kann neue Produktfamilie nicht selbst feststellen ... Kommt mit Fall 2'); in skill-architektur.md:73 ist die Rolle 'T-Box-Erweiterung vorbereiten' fuer genau diesen Ausloeser geplant. Kein Mangel. (3) Erweiterungsstelle.status 'implementiert' hat einen Konsumenten (TarifSpez-Validator schema.py:127-131: 'parametrierung' mit offenen Stellen ist gelogen) und einen dokumentierten, bewusst noch nicht gebauten Produzenten (skill-architektur.md:75 'Erweiterungsstellen implementieren', Ausloeser: erste Spez mit offener Stelle; 'Nichts auf Vorrat'). Der Fall hat keine Erweiterungsstellen (Fachspez Abschnitt 9). Bewusste Grenze, kein Mangel.

SCHWERE: 'hoch' ist uebertrieben — kein Fehlverhalten ist erreichbar, die Guards (Validator, merge-ValueError, erzeugen-Vorbedingung) fangen jede versehentliche Konstruktion. Fuer Z1 (Schaerfung des Ontologiemodells inkl. Doku und Darstellung) bleibt es aber ein realer Mangel: Prinzip P3 benennt einen Zustand ohne Definition, Produzent, Aufloesung und Test, die Doku widerspricht sich, und die Coverage-Darstellung zeigt einen toten Zaehler. Daher mittel.

Praezisierung: Z1-02 (praezisiert): Der Aussage-Zustand 'mehrdeutig' ist in Prinzip P3, Pipeline-Doku Abschnitt 3, aussage.py-Docstring, Skill entwickle-im-zielsystem und ONBOARDING als unterscheidbarer Zustand benannt und wird in coverage.py gezaehlt (im Vorfuehrfall als 'mehrdeutig: 0' dargestellt), hat aber weder Produzent (befuellung/merge erzeugen nur belegt/nicht_belegt/widerspruechlich; QuellFragment kann keinen Zustand tragen), noch Semantik-Abgrenzung zu widerspruechlich, noch Aufloesungsweg (Diskrepanz-Mechanik gilt nur fuer widerspruechlich; erzeugen.py blockt ohne Ausweg), noch Test. Der merge-Docstring ('mehrdeutig/widerspruechlich entsteht erst HIER') beschreibt den Code falsch; Pipeline-Doku Abschnitt 5 nennt drei Fehl-Zustaende ohne mehrdeutig. Der Fall zeigt einen echten Einquellen-Mehrdeutigkeitsfall ('k'), der nur als Freitext-Anmerkung ueberlebt. Kein erreichbares Fehlverhalten (Guards fangen alles), daher Schwere mittel. Empfehlung: mehrdeutig entweder mit Semantik (z. B. mehrere Fundstellen in EINER Quelle), Produzent im Fragment-Schema und Aufloesungsweg versehen — oder aus Enum, P3, Skill, ONBOARDING, Coverage und merge-Docstring streichen; Abschnitt 3 und 5 der Pipeline-Doku angleichen. GESTRICHEN aus dem Befund: 'neue_produktfamilie' (bewusste Grenze, Abschnitt 8 + skill-architektur.md:73) und Erweiterungsstelle.status 'implementiert' (Konsument im TarifSpez-Validator, Produzent als geplante Rolle skill-architektur.md:75 dokumentiert) sowie das Szenario 'faellt im Merge hart' (Fragment-Schema verhindert das Setzen bereits vor dem Merge).

Belege des Skeptikers:
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/aussage.py`:38 — MEHRDEUTIG = "mehrdeutig"
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/aussage.py`:8 — dem Zustand — ``belegt``, ``nicht_belegt``, ``mehrdeutig`` und ``widerspruechlich`` sind unterscheidbare Zustaende
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/aussage.py`:111 — else:  # mehrdeutig | widerspruechlich
    if len(self.lesarten) < 2:
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/merge.py`:58 — ``nicht_belegt`` sein (mehrdeutig/widerspruechlich entsteht erst
    HIER; ein Agent liefert keine vorentschiedenen Konflikte).
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/merge.py`:106 — zustand=Zustand.WIDERSPRUECHLICH,
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/befuellung.py`:54 — class FragmentWert(BaseModel):
    wert: Wert
    fundstelle: str = Field(min_length=1)
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/befuellung.py`:93 — nicht_belegt: List[str] = Field(default_factory=list)
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/spez/erzeugen.py`:78 — if aussage.zustand not in (Zustand.BELEGT, Zustand.NICHT_BELEGT):
    probleme.append(
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/coverage.py`:46 — zaehler = {z.value: 0 for z in Zustand}
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/coverage.json`:14 — "mehrdeutig": 0,
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/fragmente/tg2015-tarifrechner.json`:584 — 'k' ist in dieser Quelle mehrdeutig belegt: Zeile 11 ... bezeichnet policy_fee ...; Fuer parameter:policy_fee wurde ausschliesslich Zeile 11 herangezogen.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/prinzipien.md`:22 — gefunden), `mehrdeutig` und `widerspruechlich` sind unterscheidbare
Zustaende
    - `/home/bartl/git/rechner-pipeline/docs/architektur/migrations-pipeline-v01.md`:94 — Zustand (belegt / nicht_belegt / mehrdeutig / widerspruechlich)
    - `/home/bartl/git/rechner-pipeline/docs/architektur/migrations-pipeline-v01.md`:112 — Drei unterscheidbare Fehl-Zustaende: `nicht_belegt`
(Agent hat gesucht), `fehlt_in_extraktion` (...), `widerspruechlich`.
    - `/home/bartl/git/rechner-pipeline/.claude/skills/entwickle-im-zielsystem/SKILL.md`:56 — benannter Zustand (nicht_belegt/mehrdeutig/widerspruechlich) oder
    - `/home/bartl/git/rechner-pipeline/ONBOARDING.md`:287 — a named state (`nicht_belegt`/`mehrdeutig`/`widerspruechlich`) or a hard
    - `/home/bartl/git/rechner-pipeline/.claude/skills/extrahiere-quellfragment/SKILL.md`:58 — `nicht_belegt` — nichts raten, nichts ergaenzen.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/migrations-pipeline-v01.md`:172 — aber 'neue Produktfamilie' nicht selbst feststellen — die T-Box
  kennt kein Leistungsversprechen/Zahlungsprofil
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/spez/schema.py`:127 — offene = [e.id for e in self.erweiterungsstellen if e.status == "offen"]
if self.urteil.ergebnis == "parametrierung" and offene:
    - `/home/bartl/git/rechner-pipeline/docs/architektur/skill-architektur.md`:75 — | Erweiterungsstellen implementieren | erste Spez mit offener Erweiterungsstelle
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/fachspez/klv-tg2015.md`:210 — Keine — die Generation ist vollstaendig als Parametrierung des Rueckgrats ... ausgedrueckt.

#### Z1-03 — Parameterfelder der T-Box ohne Wertebereich und Normalform — Repraesentationsunterschiede werden zu Quellenwiderspruechen (hoch, unscharfer_begriff)

PFLICHT_PARAMETER ist eine Namensliste; Typ, Einheit und Normalform der Felder stehen nur in Skill-Prosa ('1,75 % => 0.0175', 'Tafelnamen auf die Rechner-Konvention normalisieren'), obwohl P5 verlangt, dass T-Box-Regeln Code sind. abox._BEREICHE deckt 7 der 13 Pflichtfelder mit Grobbereichen, 'tafel' hat keine Normalform (Basisname oder Name mit Unisex-Suffix?). Der Vorfuehrfall zeigt die Folge: 6 der 14 Diskrepanzen sind 'tafel'-Konflikte DAV2008_T_NR_U70 gegen DAV2008_T_NR, die das A-Q1-Dossier als 'KEIN Wertkonflikt im engeren Sinn, sondern zwei Darstellungen' einordnet. Das Modell kennt fuer eine Aufloesung nur 'waehle eine Lesart' — der Verantwortliche Aktuar musste formal die Meldungs-Lesart verwerfen (laut Skill ein aufsichtsrechtlich relevanter Vorgang), obwohl die Meldung nicht falsch ist. Die generierte Fachspez listet diese sechs in derselben Tabelle und Form wie den echten Zinskonflikt.

**Wirkung auf das Ziel:** Das Modell erzeugt Widersprueche, die keine sind, und zwingt Menschen zu Entscheidungen einer Kategorie ('Meldung verworfen'), die es semantisch nicht meint. Die Darstellung (Fachspez) traegt die Unterscheidung nicht. Ein uebernehmendes Haus muesste die Normalformen aus Skill-Prosa und Fall-Dossiers rekonstruieren.

**Belege:**
    - `src/rechner_pipeline/ontologie/tbox.py`:36 — PFLICHT_PARAMETER = (
    "zins",
    "tafel",
    - `.claude/skills/extrahiere-quellfragment/SKILL.md`:41 — Dezimalzahlen, 1,75 % => 0.0175):
    - `.claude/skills/extrahiere-quellfragment/SKILL.md`:107 — Promille-Angaben normalisieren (25 Promille => 0.025). Tafelnamen auf
    - `src/rechner_pipeline/ontologie/abox.py`:99 — _BEREICHE = {
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/konflikte/dossier-A-Q1.md`:85 — Dies ist KEIN Wertkonflikt im engeren Sinn, sondern zwei Darstellungen
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/abox.json`:5 — "begruendung": "Kein eigener Wertkonflikt: Rechner-Formel liefert nur den Basisnamen, Unisex-Mischung laeuft separat
    - `src/rechner_pipeline/spez/fachspez.py`:214 — z.append("| Knoten/Feld | Lesarten | Status | Entscheidung |")

**Widerlegungsversuch des Pruefers:** Gesucht nach einer Normalform-Definition fuer 'tafel' im Code: spez/validierung.py kennt die Regel 'finaler Name = A-Box-Basis + _unisex' (Zeile 92-96), also ist die Normalform 'Basisname' implizit im Code der Stufe 2 festgelegt — aber nicht in der T-Box, nicht im QuellFragment-Vertrag und nicht im Skill, der die Meldung liest. Die Merge-Toleranz (1e-9) behandelt Rundung, nicht Repraesentation. Der Fall belegt, dass die Luecke real wirkt (6 von 14 Diskrepanzen). Nicht widerlegbar.

**Vorschlag:** Die Parameterliste zu einem Parameter-Katalog machen (Name, Typ, Einheit, Wertebereich, Normalform, Beispiel) als Daten in tbox.py, mit Validator in Parametrierungszelle und Wiederverwendung im generierten JSON-Schema fuer die Extraktions-Agenten. Der Diskrepanz eine Klassifikation geben (wertkonflikt / repraesentation / einheit) und eine Aufloesungsart 'aequivalent' vorsehen, die keine Lesart verwirft; die Fachspez rendert die Klasse.

#### Z1-04 — 'Versionierte T-Box' und Gate A-K1 sind nominal: Version nie angehoben, nirgends geprueft, Gate ohne eigenen Inhalt (hoch, vertrag_ohne_test)

tbox.py, Pipeline-Dokument und ADR-003 tragen das Modell 'T-Box menschlich verantwortet und versioniert, Aenderung ueber Gate A-K1'. TBOX_VERSION = '0.1.0' wurde beim Anlegen gesetzt und nie veraendert, obwohl das Schema seitdem veraendert wurde (Feld anmerkungen in 4f4a02e). ABox.tbox_version und TarifSpez.tbox_version sind Default-Werte, die kein Validator, kein Gate und kein Test gegen die geladene T-Box haelt; eine A-Box mit fremder Version wird still geladen. A-K1 existiert als Name in GUELTIGE_GATES und in der Zeichnungsordnung, aber gate_entscheid.py hat gate-spezifische Zweige nur fuer A-M4 — ein A-K1-Snapshot pinnt nichts T-Box-Spezifisches (weder tbox.py-Hash noch Versionssprung noch Aenderungsartefakt). ADR-003 begruendet die Pydantic-Wahl ausdruecklich mit 'Schema-Evolution', ohne dass ein Evolutionsvertrag existiert.

**Wirkung auf das Ziel:** Das Change-Control-Modell der Ontologie ist behauptet, nicht erhaertet. Ein zweites Haus, das die T-Box um eine Familie erweitert (der von Abschnitt 8 vorgesehene Normalfall), findet keine Regel, wann die Version springt, was A-K1 prueft und wie Alt-A-Boxen gegen die neue T-Box gehalten werden.

**Belege:**
    - `src/rechner_pipeline/ontologie/tbox.py`:30 — TBOX_VERSION = "0.1.0"
    - `src/rechner_pipeline/ontologie/tbox.py`:207 — tbox_version: str = TBOX_VERSION
    - `src/rechner_pipeline/models/zeichnung.py`:32 — GUELTIGE_GATES = ("A-Q1", "A-M1", "A-M2", "A-M3", "A-M4", "A-K1")
    - `docs/architektur/adr-003-pydantic-fuer-ontologie.md`:16 — Schema-Evolution. Zwei handgepflegte Repraesentationen desselben
    - `docs/architektur/migrations-pipeline-v01.md`:35 — verantwortet, versioniert; Agenten aendern es nie autonom (Gate A-K1).

**Widerlegungsversuch des Pruefers:** git log -S'TBOX_VERSION = ' zeigt genau einen Commit (Einfuehrung). grep 'tbox_version' in src/ liefert nur Lese-/Ausgabestellen (coverage, fachspez), keinen Vergleich; grep in tests/ liefert nur Fixture-Werte. grep 'A-K1' in gates/gate_entscheid.py: zwei Kommentar-Treffer, kein Zweig. Der Systemstand (Git-SHA) im P9-Snapshot pinnt tbox.py indirekt mit — das sichert den Stand, ersetzt aber weder Versionsregel noch Kompatibilitaetspruefung.

**Vorschlag:** Versionsregel als Code: Validator, der abox.tbox_version gegen TBOX_VERSION prueft (Fehler oder ausgewiesene Migration), plus Test, der bei Aenderung der Feldmenge von Tarifgeneration/Parametrierungszelle einen Versionssprung verlangt (Schema-Hash gegen einen eingecheckten Snapshot). A-K1 einen Gegenstand geben: Snapshot pinnt tbox.py-Hash, alte und neue TBOX_VERSION und den Aenderungsvorschlag; ADR mit dem Evolutionsvertrag.

#### Z1-05 — Widerspruch zwischen ADR-007 und T-Box beim Knoten-Lebenszyklus, Familienbegriff mit zwei Quellen und familienneutrale Ontologie an 'klv' gebunden (mittel, widerspruch_adr_code)

ADR-007 Regel 4 legt fest, dass ein Generation-Knoten einen Status (in_migration/abgenommen) traegt; Tarifgeneration hat kein solches Feld, die ADR raeumt es als offen 'nach dem 2026-08-19' ein, ein Nachzieh-Artefakt gibt es nicht. Der Familienbegriff hat zwei Quellen: Tarifgeneration.familie ist Literal['klv'], die Knoten-Wurzeln kommen zusaetzlich aus der Kern-Registry (bu), die Fachspez schreibt 'Produktfamilie KLV' fest. Die familienneutrale Ontologie-Infrastruktur (aussage.py, merge.py, diskrepanz.py, ids.py, tbox.py, abox.py) ist mit 'Knoten: klv' annotiert, obwohl ADR-005 Regel 2 die Bindung an 'die groebste Ebene, die er fachlich traegt' verlangt und dafuer system/*-Wurzeln vorsieht — eine Aenderung an aussage.py wird im Impact als KLV-Aenderung gefuehrt.

**Wirkung auf das Ziel:** Die Ontologie ist zugleich Fall-1-Modell und Werkzeug fuer alle Faelle; die Darstellung (Knoten, Impact, Landkarte) ordnet sie einer Familie zu. Beim ersten BU- oder Rentenfall ist unklar, ob 'Familie' aus der T-Box oder aus der Registry kommt und welchen Knoten die Ontologie-Module dann tragen; der angekuendigte Lebenszyklus fehlt fuer genau diesen Parallelfall.

**Belege:**
    - `docs/architektur/adr-007-parallele-migrationen-ein-kern.md`:58 — **Regel 4 — Knoten-Lebenszyklus.** Ein Generation-Knoten traegt einen
Status: `in_migration`
    - `docs/architektur/adr-007-parallele-migrationen-ein-kern.md`:84 — * Der Knoten-Status (Regel 4) ist in der T-Box noch nicht umgesetzt;
    - `src/rechner_pipeline/ontologie/tbox.py`:134 — familie: Literal["klv"]                # Fall-1-Umfang
    - `src/rechner_pipeline/ontologie/code_index.py`:132 — return sorted({*familien, *PRODUKTE, *SYSTEM_WURZELN})
    - `src/rechner_pipeline/ontologie/aussage.py`:20 — Knoten: klv
    - `docs/architektur/adr-005-knoten-hierarchie-und-impact.md`:28 — 2. **Code bindet an die groebste Ebene, die er fachlich traegt.**

**Widerlegungsversuch des Pruefers:** Die ADR nennt die Luecke selbst — das entlastet die ADR, nicht das Modell: Prinzipien- und Pipeline-Dokument fuehren den Lebenszyklus nicht als offen, und der Termin ist verstrichen. Fuer die Knoten-Bindung der Ontologie-Module: ADR-005 fuehrt 'system/architektur' fuer code_index/impact/landkarte ein, also gibt es die Kategorie; dass tbox.py 'klv' traegt, ist mit 'Fall-1-Umfang' erklaerbar, fuer aussage.py/ids.py/merge.py nicht. Teilweise dokumentierte Grenze, daher mittel.

**Vorschlag:** Knoten-Status als Feld der Tarifgeneration mit Uebergangsregel (in_migration -> abgenommen durch A-M4-Snapshot) umsetzen oder ADR-007 Regel 4 formell zurueckziehen. Familienbegriff auf eine Quelle festlegen (T-Box-Familien-Enum, Registry prueft dagegen). Familienneutrale Ontologie-Module an 'system/ontologie' binden; Fachspez-Kopf aus gen.familie ableiten.

#### Z1-06 — Vorlaeufige Aufloesung ist die einzige A-Box-Mutation ohne Kommando und Ledger — im Fall per Ad-hoc-Skript in einem undefinierten Ordner (mittel, vertrag_ohne_werkzeug)

Der Skill migrationsfall-durchfuehren verbietet 'baue_abox von Hand' und verlangt fuer den Merge ein Kommando mit Ledger, weist aber die vorlaeufige Aufloesung als Python-Aufruf 'loese_diskrepanz_auf(..., vorlaeufig=True)' an. Es gibt kein Kommando, keine Rollen- oder Akteur-Bindung (die Akteur-Konvention <modell>/<skill>@<sha> gilt nur fuer Fragmente); der Entscheider ist Freitext. Im Vorfuehrfall geschah das ueber abgeleitet/skripte/vorlaeufige_aufloesung_rechner.py mit ENTSCHEIDER 'programmleiter (Agent, plv-it)'; der Ordner 'skripte' kommt in ADR-002, Doku und Code nicht vor. Die Kettenpruefung akzeptiert die Abweichung, weil sie die Entscheidung aus der A-Box selbst liest.

**Wirkung auf das Ziel:** Das Modell 'vorlaeufig durch Agenten, endgueltig durch Menschen' ist auf der endgueltigen Seite mit Rolle, Schluessel, Beleg und Historie erhaertet, auf der vorlaeufigen Seite nur Konvention. Ein zweites Haus koennte den ersten Schritt der Nachweiskette nicht reproduzierbar ausfuehren.

**Belege:**
    - `.claude/skills/migrationsfall-durchfuehren/SKILL.md`:162 — aufgeloest werden (`loese_diskrepanz_auf(..., vorlaeufig=True)`,
    - `.claude/skills/migrationsfall-durchfuehren/SKILL.md`:156 — — NIE baue_abox von Hand fuer einen echten Fall: der Merge-Ledger
   bindet die A-Box an die Fragmente
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/skripte/vorlaeufige_aufloesung_rechner.py`:18 — ENTSCHEIDER = "programmleiter (Agent, plv-it)"

**Widerlegungsversuch des Pruefers:** Gesucht nach einem CLI-Pfad mit vorlaeufig=True: grep in src/ liefert nur den Docstring in diskrepanz.py. Gegenargument: Gates und Fachspez blocken jede Annahme, solange vorlaeufige Entscheidungen existieren (gate_entscheid.py Zeile 1241-1250, fachspez.py Zeile 234-244) — der Zustand kann nicht Dauerzustand werden. Das begrenzt das Risiko, beseitigt aber nicht die Modelluecke (unprotokollierter Uebergang), die die Systempruefung beim Merge als Befund gewertet hat. Daher mittel.

**Vorschlag:** entscheide um '--vorlaeufig' erweitern (Akteur nach Konvention, Ledger-Eintrag, kein Schluessel noetig) und das Skript im Skill durch das Kommando ersetzen; 'abgeleitet/skripte' entweder in ADR-002 als Ort fuer Fall-Werkzeuge definieren oder verbieten. Zusaetzlich einen Feldfilter fuer --alle-vorlaeufigen (das Dossier musste die tafel-Faelle deshalb einzeln behandeln).

#### Z1-07 — Evidenzquellen jenseits der drei Quellarten (Auskunftsschreiben) haben im Modell keinen Ort — Entscheidungen berufen sich in Prosa darauf (mittel, unscharfer_begriff)

QUELLE_ARTEN kennt tarifmeldung, tarifrechner, bestand. Der Vorfuehrfall registriert vier Auskunftsschreiben im Eingang (ohne Art — das Register kennt kein Art-Feld), und die Zins-Entscheidung stuetzt sich in der Begruendung auf 'Auskunftsschreiben 3 (SHA-256 ..., registriert)'. Der strukturierte Beleg der Entscheidung (Beleg, einzeln, Optional) zeigt auf den Abzugsabgleich; das Auskunftsschreiben ist nur Prosa mit handgetipptem Hash — genau die Bindungsluecke, die die Beleg-Klasse laut eigenem Docstring fuer Rechnungsdateien schliesst. Eine Klaerung mit dem Quellhaus ist im Migrationsalltag eine Regelquelle, im Modell aber weder Quelle noch Lesart noch Beleg.

**Wirkung auf das Ziel:** Die Provenienzkette (P1) ist fuer Extraktion und Rechnung geschlossen, fuer Klaerungen mit dem Lieferanten offen. Ein Pruefer, der wissen will, worauf der Verantwortliche Aktuar den Zins gestuetzt hat, findet den entscheidenden Teil nur im Freitext.

**Belege:**
    - `src/rechner_pipeline/ontologie/tbox.py`:62 — QUELLE_ARTEN = ("tarifmeldung", "tarifrechner", "bestand")
    - `src/rechner_pipeline/ontologie/diskrepanz.py`:71 — beleg: Optional[Beleg] = None
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/abox.json`:57 — "begruendung": "Auskunftsschreiben 3 (SHA-256 38e515aa..., registriert) bestaetigt Mitteilung 143 als massgeblich

**Widerlegungsversuch des Pruefers:** Beleg.datei ist ein beliebiger fall-relativer Pfad — technisch koennte er auf eingang/auskunft-3.md zeigen; aber es ist nur EIN Beleg moeglich, und der Docstring definiert ihn als 'deterministische Rechnung'. Das Eingang-Register bindet die Datei per Hash, sodass die Prosa-Nennung nachpruefbar ist — jedoch nur durch Handarbeit. Nicht widerlegt.

**Vorschlag:** Entscheidung.beleg zur Liste machen und den Beleg um eine Art (rechnung / klaerung / tarifwerk) erweitern; QUELLE_ARTEN oder das Eingang-Register um 'klaerung' ergaenzen, damit Auskuenfte als Evidenz mit Fundstelle zitierbar werden. Gate P-Q3 prueft die Hashes aller Belege.

#### Z1-08 — Die Darstellung zeigt die Codebasis, nicht das Modell: keine generierte Sicht auf Klassen, Zustaende, Uebergaenge und Entscheidungsketten (mittel, darstellung_ausschnitt)

Die Landkarte (HTML, Mermaid, DOT, GraphML) ist eine Code-Karte: Schichten, Module, Knoten-Bindungen, Impact. Das Ontologiemodell selbst — Tarifgeneration/Zelle/Aussage/Diskrepanz/Entscheidung, die vier Zustaende, ihre Uebergaenge, die Gate-Folge — hat keine generierte Darstellung; grep nach classDiagram/stateDiagram/erDiagram in docs/, README, ONBOARDING findet nichts. Die einzige Modellbeschreibung ist die handgepflegte Tabelle in Abschnitt 3 des Pipeline-Dokuments (mit der in Z1-02 gezeigten Inkonsistenz zu Abschnitt 5); das generierte JSON-Schema wird bewusst nicht abgelegt. Die generierte Fachspez rendert je Entscheidung nur Wert und Entscheider — Rolle, Beleg-Hash und die vorlaeufig->endgueltig-Historie, die das Modell traegt, erscheinen im A-Q1-Dokument nicht.

**Wirkung auf das Ziel:** Das Ziel nennt Dokumentation und Darstellung ausdruecklich. Wer das Modell uebernehmen will, muss es aus Pydantic-Klassen und Prosa rekonstruieren; wer die Fachspez liest, sieht die Nachweiskette nicht, die das Modell aufwendig sichert.

**Belege:**
    - `src/rechner_pipeline/ontologie/landkarte.py`:3 — Erzeugt aus ``code_index``, ``code_karte`` und ``impact`` eine
selbsttragende Seite: Knotenbaum, Test-Bindungen, Erlaubnismatrix
    - `docs/architektur/migrations-pipeline-v01.md`:94 — | `Aussage` | Wert, Zustand (belegt / nicht_belegt / mehrdeutig / widerspruechlich), Konfidenz, Provenienz je Beleg
    - `src/rechner_pipeline/spez/fachspez.py`:225 — f"{_md(e.gewaehlter_wert)} — {_md(e.entscheider)}"

**Widerlegungsversuch des Pruefers:** P7 verlangt eine generierte Fachspezifikation aus der A-Box — die existiert und ist deterministisch; ADR-003 macht das JSON-Schema per model_json_schema() jederzeit erzeugbar. Beides deckt Instanzen bzw. Struktur, aber nicht Zustaende, Uebergaenge oder die Entscheidungskette. Der Verzicht auf einen Schema-Snapshot ist begruendet ('das Schema ist die Wahrheit'), ein generiertes Modelldiagramm ist damit nicht ausgeschlossen. Teilweise entkraeftet, daher mittel.

**Vorschlag:** Die Landkarte um einen Modus 'modell' erweitern, der aus den Pydantic-Klassen ein Klassen-/Zustandsdiagramm (Mermaid) erzeugt — drift-geprueft wie landkarte.md. Fachspez Abschnitt 7 um Rolle, Beleg (Datei + Hash-Praefix) und Historie ergaenzen; die Tabelle in Abschnitt 3 des Pipeline-Dokuments durch die generierte Sicht ersetzen (P7 auf die eigene Doku angewandt).

#### Z1-09 — Ungetesteter Vertrag in der Code-Karte: _absolut referenziert eine undefinierte Variable (mittel, vertrag_ohne_test)

code_karte.py verspricht, relative Importe auf dotted-Namen zu bringen. _absolut berechnet 'anker', benutzt es nicht, und joint stattdessen 'paketpfad', das nirgends definiert ist. Der erste relative Import in src/ liesse baue_karte mit NameError abbrechen — die Schichtenpruefung (Test der Suite) wuerde dann nicht urteilen, sondern crashen. Unbemerkt, weil src/ heute keinen relativen Import enthaelt und kein Test _absolut mit level > 0 uebt.

**Wirkung auf das Ziel:** Die Code-Karte ist Teil der Erhaertung ('Schichtenkarte nachrechenbar statt Prosa'). Ein Vertrag, dessen einer Zweig nie ausgefuehrt wurde und nicht ausfuehrbar ist, ist an dieser Stelle Prosa.

**Belege:**
    - `src/rechner_pipeline/ontologie/code_karte.py`:156 — """Relative Imports (``from . import x``) auf dotted-Namen bringen."""
    - `src/rechner_pipeline/ontologie/code_karte.py`:163 — dotted = ".".join(paketpfad)
    - `src/rechner_pipeline/ontologie/code_karte.py`:203 — dotted = _absolut(n.module, n.level, rel)

**Widerlegungsversuch des Pruefers:** grep '^from \.' und '    from \.' in src/ liefert keinen Treffer; grep '_absolut' in tests/ liefert keinen direkten Test. Da der Fehler laut statt still faellt, ist die Sicherheitswirkung begrenzt — der Befund ist Klasse 'Vertrag ohne Test', nicht 'Loch in der Regel'.

**Vorschlag:** 'paketpfad' durch 'anker' ersetzen und einen Test ergaenzen, der ein Mini-Paket mit 'from . import x' und 'from ..a import b' durch baue_karte fuehrt (Kanten korrekt, kein Fehler); zusaetzlich einen Test, dass jeder ImportFrom-Level in src/ verarbeitet wird.

#### Z1-10 — Prosa-Kennzahlen und Determinismus-Aussagen in Docstrings, die der Code nicht mehr deckt (niedrig, doku_drift)

impact.py nennt '34 der 79 Module', landkarte.py '93 Module'; das Repo hat 101 Module (find), und die generierte landkarte.md summiert exakt 101 (1+19+1+17+12+3+6+16+8+13+5). landkarte.py verspricht 'gleicher Repo-Stand -> byte-identische Datei', liest aber faelle/ (gitignoriert, je Maschine verschieden) fuer die Generationenliste. Die Klasse 'selbst-inklusiver Zaehler in lebendem Text' wurde in Commit 337ebb6 fuer dev-docs repariert, nicht fuer diese Docstrings.

**Wirkung auf das Ziel:** Geringe Wirkung, aber gegen die eigene Regel 'generiert schlaegt handgeschrieben': Wer den generierten Zahlen glaubt, liest im Modul das Gegenteil.

**Belege:**
    - `src/rechner_pipeline/ontologie/impact.py`:34 — Das ist die bewusst getragene Restluecke (heute 34 der 79 Module)
    - `src/rechner_pipeline/ontologie/landkarte.py`:15 — stattdessen Tabellen, eine Matrix und Listen — bei 93 Modulen
    - `src/rechner_pipeline/ontologie/landkarte.py`:104 — generationen = lade_faelle_generationen(faelle)

**Widerlegungsversuch des Pruefers:** ADR-005 nennt ebenfalls 79 Module, ist aber datiert (2026-08-16) und damit als Schnappschuss lesbar; die Docstrings tragen 'heute' bzw. keinen Stand. Fuer den Determinismus: ohne faelle/ oder mit identischem faelle/ gilt die Aussage — sie nennt die Eingabe nur nicht.

**Vorschlag:** Zahlen in Docstrings an einen benannten Commit binden oder auf die generierte landkarte.md verweisen; im landkarte-Docstring 'gleicher Repo-Stand UND gleiches faelle/-Verzeichnis' schreiben oder faelle/ als optionale Eingabe (--faelle none) fuehren.

#### Z1-11 — Pfeil-Semantik der Architektur-Darstellung undefiniert: README-Kette und erzwungene Erlaubnismatrix meinen Verschiedenes (niedrig, darstellung_ausschnitt)

README zeigt 'quellen -> ontologie -> spez -> kern -> bestand -> qa -> gates' unter der Ueberschrift 'Import-Regeln maschinell erzwungen'. SCHICHT_ERLAUBT ist ein Netz: spez importiert ontologie (gegen die Pfeilrichtung, wenn der Pfeil Import meint), quellen importiert spez und ontologie, gates liest neun Schichten, models und fall sind Querschichten. Der README-Pfeil meint offenbar Datenfluss, die Matrix Import-Erlaubnis; das steht nirgends.

**Wirkung auf das Ziel:** Klein, aber irrefuehrend an der ersten Stelle, die ein Externer liest: er wird 'Import-Regeln' lesen und die Kette als Regel nehmen.

**Belege:**
    - `README.md`:94 — quellen  ->  ontologie  ->  spez  ->  kern  ->  bestand  ->  qa  ->  gates
    - `src/rechner_pipeline/ontologie/code_karte.py`:63 — "quellen": {"quellen", "models", "ontologie", "kern", "spez"},

**Widerlegungsversuch des Pruefers:** Die generierte landkarte.md Abschnitt 1 zeigt die echte Matrix und ist verlinkt; die README verweist auf code_karte als Quelle. Vereinfachung ist legitim, die fehlende Legende nicht.

**Vorschlag:** Unter dem README-Diagramm eine Zeile 'Pfeile = fachlicher Datenfluss; die Import-Erlaubnis ist ein Netz, siehe landkarte.md Abschnitt 1' ergaenzen.

### Vom Pruefer korrigierte Punkte der Sammlung

- Bestaetigt und verschaerft: Spannung 'OHNE Menschen' (Skill) — zusaetzlich steht dieselbe Aussage im Docstring von qa/abzugsabgleich.py Zeile 3, der Skill widerspricht sich selbst (Zeile 73 gegen 86), die Skill-Architektur (Zeile 29) verbietet der Rolle das Entscheiden, und gleiche_ab hat in src/ keinen Aufrufer — die 'Automatik' existiert nur als Engine plus Prosa (Befund Z1-01).
- Bestaetigt: ADR-007 Knoten-Status nicht in der T-Box (tbox.py Zeile 130-198 ohne Statusfeld; ADR Zeile 84-85 raeumt es ein). Als Teil der Klasse 'Familien-/Knotenbegriff' in Z1-05 aufgenommen; der Termin 'nach dem 2026-08-19' ist verstrichen.
- Bestaetigt: Modulzahlen 79 (impact.py Zeile 34) und 93 (landkarte.py Zeile 15) gegen 101 aktuelle Module; die Summe der generierten landkarte.md ist exakt 101. Als niedrig eingestuft (Z1-10), da die generierte Sicht stimmt.
- Bestaetigt: code_karte._absolut nutzt die undefinierte Variable 'paketpfad' (Zeile 163), Aufruf mit n.level in Zeile 203; kein relativer Import in src/, kein Test. Als mittel eingestuft, weil der Fehler laut (NameError) statt still fiele (Z1-09).
- Teilweise korrigiert: README-Kette gegen SCHICHT_ERLAUBT — der Kern des Problems ist nicht die Vereinfachung, sondern die undefinierte Pfeil-Semantik (Datenfluss vs. Import-Erlaubnis) unter einer Ueberschrift, die Import-Regeln verspricht. Niedrig (Z1-11).
- Korrigiert (kein Befund): Determinismus der Landkarte haengt von faelle/ ab — zutreffend (landkarte.py Zeile 104), aber eine fehlende Nennung der Eingabe, keine Fehlaussage; als Beleg in Z1-10 aufgenommen.
- Korrigiert (kein Befund): 'P8 nur grob eingeloest, Zielzustand unklar' — der Zielzustand ist in ADR-005 'Bekannte Grenzen' beschrieben ('Modulebene ... Funktions-/Testfall-Ebene lohnt erst bei deutlich groesseren Modulen'); der Verweis in prinzipien.md auf Abschnitt 8 ist unpraezise (dort nur der Satz zur Test-Knoten-Bindung), das ist ein Verweisfehler, kein Modellmangel.
- Korrigiert (kein Befund): fehlendes Formel-Feld im QuellFragment — in Abschnitt 8.1 des Pipeline-Dokuments und im Skill migrationsfall-durchfuehren (Zeile 166-178) als bewusste, begruendete Grenze mit Ausbaupfad und Ausloeser dokumentiert.
- Korrigiert (kein Befund): fehlende kanonische Liste der system/*-Unterknoten — ADR-005 Punkt 1 erklaert tiefere Ebenen zu 'Instanzen und bewusst offen'; die sechs verwendeten Straenge (assurance, architektur, bestand, fall, entscheid, skills) sind per code_index ableitbar. Bleibt eine dokumentierte Entscheidung.
- Korrigiert (kein Befund): Nicht-Einbindung von import-linter/deptry/ruff TID251 — ADR-005 nennt sie ausdruecklich als 'Kandidaten fuer spaeter, kein Umbau vor dem Push'; kein Modellmangel.
- Bestaetigt ohne Befund: die Behauptungen zu P1 (Provenienz-Felder, pruefe_akteur), zur T-Box/A-Box-Trennung und zur Selbstauskunft des Pipeline-Dokuments halten am Code; landkarte.md ist mit dem Code konsistent.
- Ergaenzt aus dem Fall (vom Sammler nicht gesehen, weil faelle/ nicht geoeffnet): Parameter ohne Normalform erzeugen Scheinkonflikte (Z1-03), vorlaeufige Aufloesung per Ad-hoc-Skript (Z1-06), Auskunftsschreiben als Evidenz ohne Modell-Ort (Z1-07), Fachspez rendert Beleg/Rolle/Historie nicht (Z1-08).

### Grenzen der Sammlung (vom Sammler benannt)

- src/rechner_pipeline/spez/erzeugen.py, validierung.py, fachspez.py: nur Kopf/Docstring und Imports gelesen, nicht vollstaendig (Funktionskoerper) — Zeitbudget auf die Kern-Ontologie-Module priorisiert.
- src/rechner_pipeline/models/bestand.py (1220 Zeilen), models/schemas.py (941 Zeilen), models/bundle.py, models/manifest.py: nicht gelesen — sehr umfangreich und primaer Gate-/Bestand-Vertraege, nur am Rande Ontologie-tragend; nur per grep auf Ontologie-Begriffe gesichtet.
- docs/architektur/adr-004, adr-008, adr-009, adr-010, adr-011 bis adr-016 sowie skill-architektur.md: nur per grep auf Ontologie-Schluesselbegriffe durchsucht, nicht vollstaendig gelesen (Zeitbudget; diese ADRs betreffen primaer Kern/Bestand/P9/Gates, nicht das Ontologiemodell selbst).
- ONBOARDING.md und AGENTS.md: nur grep-Treffer gepruft, nicht vollstaendig gelesen (beide sind primaer Onboarding-/Agentenregeln, keine Ontologie-Spezifikation).
- src/rechner_pipeline/ontologie/landkarte_vorlage.html: nur Kopf (CSS/Head) gesichtet, nicht das vollstaendige JS-Rendering (24 KB) — fuer die Inventarisierung als 'Template mit Platzhalter' ausreichend.
- tests/test_code_karte_und_impact.py, test_transformation_und_abgleich.py, test_transformation_kommando.py: nur Funktionsnamen/gezielte grep-Treffer gepruft, nicht vollstaendig Zeile fuer Zeile gelesen (825 bzw. 1156 bzw. 176 Zeilen) — Zeitbudget.
- faelle/, docs-local/, simulation/, regie/: absichtlich NICHT geoeffnet (docs-local/simulation/regie sind laut Auftrag tabu; faelle/ ist gitignoriert/lokal und fuer diese Sammlung nicht einschlaegig als Repo-Artefakt).
- Es wurde kein Code ausgefuehrt (kein pytest, kein python -m rechner_pipeline.ontologie.*) — rein lesende Sammlung wie vorgeschrieben; alle Zahlen-Kreuzchecks (Modulzahlen) erfolgten ueber grep/find, nicht durch Ausfuehren der Generatoren selbst.


## Z2 — Fall-Dokumentation fuer Bereichsleiter Fach und IT

### Gesamturteil des Pruefers

Die Fall-Dokumentation ist in ihrer Grundanlage fuer die Fuehrungsebene tragfaehig: Ein knapper Abschlussbericht in Fachsprache, ein Veraenderungs-Dokument mit Vorher/Nachher-Tabellen und eine generierte Fall-Seite, die jede Zahl auf ein Artefakt zurueckfuehrt und ihre Grenzen selbst ableitet — das ist mehr, als die meisten Migrationsprojekte vorlegen. Das Ziel wird dennoch an zwei Stellen verfehlt: Die Konsumenten-Dokumente erzaehlen den Zeichnungsstand glatter, als die Artefakte ihn hergeben (alle Zeichnungen auf nicht committetem Code, 'unveraendert' im Bericht, kein dirty-Flag auf der Seite), und Bericht und Seite legen unterschiedliche fachliche Grenzen offen, so dass das Restrisiko-Bild vom zuerst gelesenen Dokument abhaengt. Dazu kommen eine Klasse von Register-Bruechen (Entwickler-Bezeichner, ASCII-Umschrift, Rollen-IDs ohne Glossar) und eine Einstiegs-Doku, die den Stand vor dem Lauf beschreibt. Fuer die IT-Fuehrungskraft fehlt an einem Ort, was Betrieb und Datenfluss zum Modellanbieter betrifft; fuer die Fach-Fuehrungskraft fehlt das Design-Dokument des Falls, auf das der einzige offene Punkt verweist. Die Reparaturen sind ueberwiegend Beschriftungs-, Verweis- und Zusammenfuehrungsarbeit — die Substanz ist vorhanden, sie ist nur nicht dort, wo die Fuehrungsebene sie liest.

### Was traegt (Staerken)

- Der Abschlussbericht (docs/faelle/baldrian-lauf2.md) ist fuer die Fachleitung richtig geschnitten: Ergebnis zuerst, dann Gegenstand, Feststellungen zum Quell-Tarifwerk, Methodik, Datenluecke, offene Punkte — ohne Code, ohne Pfade, in vollstaendigen Saetzen.
- Die generierte Fall-Seite (runs/seite/migrationen/baldrian/index.md) fuehrt zu jedem Abschnitt 'Gelesen aus ...'-Herkunftsangaben, leitet Abgrenzungen aus Artefaktvergleichen ab statt sie zu schreiben, und zeigt ueberholte Zeichnungsrunden statt sie zu verbergen — die Grundhaltung 'ein Lauf mit Befund wird wie ein gruener dargestellt' ist erkennbar umgesetzt.
- Die Zahlen sind ueber Abschlussbericht, Uebersichtsseite, Fall-Seite und Artefakte konsistent (834 Vertraege, 33.437.445,97 EUR, 2508 Einzelpruefungen, 166 Vorfaelle = 166 Policen im A-M3, Kreuzprobe 23 gegen 23).
- Die Nachweismechanik ist auf Artefaktebene ehrlich: Snapshots fuehren Commit, Branch, dirty-Flag, Quelltext-Pruefsumme, Vorgaenger, Pflichtbelege und Schluessel-Fingerabdruck; die Gate-Berichte weisen den Systemstand samt dirty-Flag aus.
- Das Veraenderungs-Dokument (Tabelle 'vor Lauf 2 / nach Lauf 2 / Grund und Beleg', Faehigkeiten 'es fehlte / jetzt') ist ein fuer Fuehrungskraefte seltenes, gut lesbares Format fuer 'was hat die Uebernahme am System veraendert'.
- Umbaubudget und Umbaubericht sind ein echtes Steuerungsinstrument (Loeschen wiegt schwerer als Hinzufuegen, Ueberschreiten erlaubt, Verschweigen nicht) und die Begruendung landet sichtbar auf der Seite.
- Die Veroeffentlichung ist defensiv konstruiert: Positivliste statt Sperrliste, Regie-Sperre bricht ab statt zu warnen, Fiktions-Banderole ist Baubedingung, Systemstand wird gestempelt.
- Die Bereichsseiten Risikomanagement und Finanzen treffen den Ton ihrer Zielgruppe (drei Schranken; gelieferte Groessen gegen eigene Rechnung, Zugang statt Vertragsbeginn) und verlinken auf Belege statt zu behaupten.

### Lesarten (Zehn-Minuten-Test)

**Fuehrungskraft Fachbereich (Aktuariat/Produkt)**  
Mit Abschlussbericht (docs/faelle/baldrian-lauf2.md) und generierter Fall-Seite versteht sie: 834 Vertraege KLV TG2015 der Baldrian Leben wurden zum 01.01.2026 uebernommen (33,4 Mio. EUR Deckungskapital), fuenf Gates sind angenommen, Abweichungen liegen im Cent-Bereich (max 3,2 ct), gezeichnet hat die Rolle 'Verantwortlicher Aktuar' (auf der Seite: 'plv-aktuar', Simulationsschluessel), einziger offener Punkt ist eine Falsifizierbarkeits-Auflage fuer zwei Policen. Sie versteht auch die sieben Feststellungen zum Quell-Tarifwerk und die Behandlung der Datenluecke Herabsetzungsanteile — der Abschlussbericht ist in Aufbau (Ergebnis, Gegenstand, Feststellungen, Methodik, Datenluecke, Offene Punkte) fuer sie richtig geschnitten.
  
Fehlt: Eine Restrisiko-Zusammenfassung, die alle Grenzen an einem Ort fuehrt: Golden Master nur fuer 1 von 6 Tarifzellen, zweite Stichtagsgroesse fuer 811 von 834, 23 Code-Korrekturen und elf ueberholte Zeichnungsrunden waehrend des Laufs, Zeichnung auf nicht committetem Stand (B1, B5); Das Design-Dokument des Falls (Migrationskonzept-Instanz bzw. lesbare Tarifplan-Ausgestaltung), auf das der einzige offene Punkt verweist (B6); Eine Erklaerung, wer 'plv-aktuar' ist und was 'Zeichnungsordnung' bedeutet (B2); Die fachliche Begruendung der zwanzigfach weiteren A-M2-Toleranz (B5); Eine Bereichsseite Aktuariat, die die vier Fragen (was, abgenommen, gezeichnet, Restrisiko) selbst beantwortet (B9)
  
Verwirrt: '2 Feststellungen ueber 6 Tarifzellen' (Seite) gegen 'drei Diskrepanz-Typen, vierzehn Einzelentscheide' (Bericht); 'gewaehlt 0.0125' neben 'Lesart 1,25 %' in derselben Zeile; 'dk_stichtag_2' als fachliche Einschraenkung; ASCII-Umschrift im Abschlussbericht neben Umlaut-Seiten; Eingecheckte Unternehmensseiten mit 'Tranche 1', 500 Vertraegen und 42 Vorfaellen neben dem Bericht mit 834 und 166; 'unveraenderter Systemstand' im Bericht gegen '6 Staende' als Abgrenzung der Seite; Ein Zeichnungs-Tableau mit 16 Zeilen 'angenommen', davon 11 'ueberholt', ohne Satz dazu im Abschlussbericht
  
Passendes Format: Ein Zweiseiter (Seite 1: Ergebnis-Tabelle der fuenf Gates, Kennzahlen, Zeichnungen mit Rolle und Schluesselcharakter; Seite 2: Restrisiko und Grenzen, offene Punkte, Verweise) — im Wesentlichen der bestehende Abschlussbericht plus den Abgrenzungen der Seite, in Unternehmensorthographie. Fuer die Vorfuehrung ein Foliensatz von fuenf Folien (Gegenstand, Pruefkette, Ergebnis, Feststellungen zum Quell-Tarifwerk, Restrisiko). Die generierte Fall-Seite ist als Anhang/Nachschlagewerk richtig, nicht als Einstieg.

**Fuehrungskraft IT**  
Mit README (Architektur, Gates), vorzeige-seite/it, Landkarte und der Fall-Seite versteht sie das Prinzip (Agenten schlagen vor, deterministische Gates urteilen, Menschen zeichnen HMAC-signierte Snapshots), die Schichtenkarte, dass jede Zahl auf ein Artefakt zeigt, dass Berichte deterministisch neu gerendert und byte-verglichen werden, und dass der Umbau eines Laufs gemessen wird (Umbaubudget, Stolperdraehte). Die Gate-Tabelle und der Zeichnungs-Abschnitt der Fall-Seite geben ihr die Nachweiskette in Umrissen.
  
Fehlt: Eine Betriebs-Sicht an einem Ort: Laufzeit, gepinnte Abhaengigkeiten, Schluesselverwahrung und -rotation, Agenten-Laufzeit, Veroeffentlichungsweg (B9); Eine Datenfluss-Aussage: welche Daten der Agent sieht, welcher Modellanbieter, was das Haus nie verlaesst (B9); Der Nachweis, dass der gezeichnete Code-Stand pruefbar ist — alle Zeichnungen erfolgten auf einem nicht committeten Arbeitsbaum, die Konsumenten-Dokumente sagen es nicht (B1); Ein aktuelles Pipeline-Dokument; das verlinkte ist 'teilweise ueberholt' (B3); Eine Erklaerung der Gate-Namensordnung fuer Aussenstehende (P-Q1, A-M1, P9, 'G2-Vorlage' stehen nebeneinander; ADR-012 erklaert es, aber kein Einstieg verweist darauf)
  
Verwirrt: ONBOARDING in Englisch mit Kern 3.0.1 und Kommutations-Kreuzcheck, README in Deutsch mit 3.4.0 und ADR-013; Die IT-Seite nennt das Pipeline-Konzept 'vollstaendig eingespielt'; das Dokument sagt, die menschlichen Gates 'stehen aus'; Zwei Werkzeuggenerationen: die eingecheckten Werkzeuge dieses Branches erzeugen nicht den gezeigten Auftritt (Stempel 'vorzeige-url'); Ledger-Vokabular 'passed', Rollen-IDs 'plv-aktuar', 'plv-it' ohne Glossar; Der Umbaubericht listet Commit-Kuerzel und Commit-Botschaften — fuer einen IT-Leiter ein Changelog, kein Bericht
  
Passendes Format: Ein Architektur-Einseiter (Diagramm Agent/Gate/Mensch mit Artefaktfluss, Schichtenkarte generiert, Nachweismechanik in fuenf Punkten, Betriebsvoraussetzungen und Datenfluss als Kasten) plus der ADR-Index als Nachschlagewerk. Die generierte Landkarte und die Gate-Tabelle sind das richtige Material; ein kurzer Glossar-Block (Gate-Kennungen, Rollen-IDs) gehoert dazu. Der Umbaubericht sollte in eine Kennzahl-Ansicht (Budget, Loeschquote, Stolperdraehte, Begruendung) und einen ausklappbaren Commit-Anhang getrennt werden.

### Befunde

| Nr | Schwere | Titel | Verifikation |
|---|---|---|---|
| B1 | kritisch | Die Konsumenten-Dokumente erzaehlen einen 'unveraenderten Systemstand', den es so nicht gibt: alle 16 Zeichnungen erfolgten auf einem ungespeicherten Arbeitsbaum, und nur die Entwickler-Artefakte sagen es | WIDERLEGT |
| B2 | hoch | Entwickler-Identifikatoren dringen in die fuer Fuehrungskraefte gebaute Fall-Seite durch (Feldnamen, Rollen-IDs, Exit-Vokabular, Dateipfade, Commit-Kuerzel) | bestaetigt, Schwere mittel |
| B3 | hoch | Die Einstiegs- und Rahmendokumentation beschreibt den Stand vor dem Lauf: veraltete Kernversion, ausser Betrieb genommener Kreuzcheck, 'teilweise ueberholtes' Pflichtdokument, Lieferung 1 statt Lieferung 2 | nicht verifiziert |
| B4 | mittel | Im gepruefen Arbeitsverzeichnis existieren zwei Staende des Demonstrationsmaterials: eingecheckte Unternehmensseiten mit Lauf-1-Zahlen neben einem generierten Auftritt, den die eingecheckten Werkzeuge dieses Branches nicht erzeugen | nicht verifiziert |
| B5 | hoch | Abschlussbericht und Fall-Seite legen unterschiedliche fachliche Grenzen offen — das Restrisiko-Bild haengt davon ab, welches Dokument die Fach-Fuehrungskraft zuerst liest | nicht verifiziert |
| B6 | hoch | Das Design-Dokument des Falls fehlt als Fachdokument: keine Migrationskonzept-Instanz, und die 'Tarifplan-Ausgestaltung', auf die der einzige offene Punkt zeigt, ist eine unveroeffentlichte Arbeitschronik | nicht verifiziert |
| B7 | mittel | Die beiden Fach-Berichte stehen in ASCII-Umschrift ('Uebernommen', 'Vertraege') und werden unveraendert neben Seiten mit echten Umlauten veroeffentlicht | nicht verifiziert |
| B8 | mittel | Der eingecheckte Abschlussbericht tritt als Dokument eines Versicherers auf und meldet eine Zeichnung durch den 'Verantwortlichen Aktuar', ohne den Simulations-Charakter zu nennen | nicht verifiziert |
| B9 | hoch | Fuer die IT-Fuehrungskraft fehlen Betriebsvoraussetzungen und Datenfluss zum Modellanbieter an einer Stelle; fuer die Fach-Fuehrungskraft ist die Bereichsseite Aktuariat ein Platzhalter | nicht verifiziert |

#### B1 — Die Konsumenten-Dokumente erzaehlen einen 'unveraenderten Systemstand', den es so nicht gibt: alle 16 Zeichnungen erfolgten auf einem ungespeicherten Arbeitsbaum, und nur die Entwickler-Artefakte sagen es (kritisch, Nachweismechanik / Irrefuehrung)

Alle fuenf finalen Entscheid-Snapshots (A-Q1 fd793260, A-M1 fb1550c0, A-M2 411ac21c, A-M3 d260e621, A-M4 32682e95) und alle elf ueberholten tragen im Feld system 'dirty': 'ja' — der Code, auf dem der Verantwortliche Aktuar gezeichnet hat, ist nicht der Commit 4b1abf0, sondern ein nicht committeter Zwischenstand (unterscheidbar nur ueber quellcode_sha256, das niemand aus dem Repo rekonstruieren kann). Der Abschlussbericht formuliert daraus 'auf einem einzigen, unveraenderten Systemstand gezeichnet'; die generierte Fall-Seite nennt den Commit-Hash und verschweigt das dirty-Flag vollstaendig (kein 'sauber'/'dirty' im gerenderten Text, obwohl die aeltere Werkzeuggeneration eine Zeile 'Arbeitsbaum sauber' fuehrte). Zugleich verlangt werkzeuge/README fuer die Veroeffentlichung, dass der gestempelte Stand 'im oeffentlichen Repo nachschlagbar' sein muss — fuer die Signaturen gilt dieselbe Anforderung, und sie ist nicht erfuellt. Der Abschlussbericht erwaehnt auch die elf ueberholten Zeichnungsrunden und die 23 Code-Korrekturen waehrend des Laufs nicht (nur das Veraenderungs-Dokument nennt sie).

**Wirkung auf das Ziel:** Die IT-Fuehrungskraft, deren Kernfrage die Nachweismechanik ist, liest 'Systemstand 4b1abf0' und glaubt, den gezeichneten Code auschecken zu koennen — das geht nicht. Die Fach-Fuehrungskraft liest 'unveraendert' und versteht 'stabil abgenommen', waehrend das System zwischen den Zeichnungsrunden fuenfmal geaendert wurde. Das Kernversprechen der Vorfuehrung (jede Zahl nachpruefbar, jeder Entscheid an den Stand gebunden) wird an genau der Stelle, an der es die Fuehrungsebene erreicht, weicher dargestellt als es die Artefakte hergeben.

**Belege:**
    - `docs/faelle/baldrian-lauf2.md`:12 — Alle fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem einzigen, unveraenderten Systemstand gezeichnet
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-M4-32682e958c7811b0b5fc89c3e7eaf897243b2d39151facf5ba60c99397231a6e.json` — "system": {"branch": "fallbericht", "commit": "4b1abf048ac8...", "dirty": "ja", ...} — ebenso in allen 15 weiteren Snapshots des Falls
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/berichte/aktuartest.html`:591 — <tr><th>dirty</th><td>ja</td></tr>
    - `runs/seite/migrationen/baldrian/index.md`:6 — finale Zeichnungen auf Systemstand `4b1abf048ac8` (frühere Runden auf 5 weiteren Ständen)
    - `werkzeuge/README.md`:272 — Dieser Stand muss im oeffentlichen Repo nachschlagbar sein, BEVOR die Seite live geht — eine Seite, deren Kernversprechen die Nachpruefbarkeit ist, darf nicht auf einen Commit zeigen, den niemand einsehen kann.
    - `werkzeuge/vorzeigeseite.py`:256 — z.append(f"| Arbeitsbaum sauber | {stand['sauber']} |")  — aeltere Werkzeuggeneration; im aktuellen runs/seite fehlt die Zeile

**Widerlegungsversuch des Pruefers:** Versucht: (1) Die Snapshots selbst und die Gate-Berichte (aktuartest.html, Abschnitt Systemstand) weisen dirty=ja ehrlich aus — auf Artefaktebene ist nichts verborgen. (2) quellcode_sha256 unterscheidet Stande, und das Veraenderungs-Dokument nennt ein 'eingefrorenes Ende-zu-Ende-Fixture', das den Endstand pinnen koennte. (3) 'einziger Systemstand' ist fuer die fuenf finalen Zeichnungen faktisch richtig (alle 4b1abf0). Haelt nicht: Die Fuehrungsebene liest nicht die JSON-Snapshots, sondern Abschlussbericht und Seite — und genau dort steht 'unveraendert' bzw. der nackte Commit-Hash. Ein SHA ueber Quelltexte ist kein nachschlagbarer Stand; das Fixture belegt nicht, dass es dem gezeichneten Zwischenstand entspricht. Die aeltere Werkzeuggeneration zeigt, dass die Information darstellbar war und weggefallen ist.

**Vorschlag:** Auf der Fall-Seite und im Abschlussbericht den Zeichnungsstand als 'Commit 4b1abf0 mit nicht committeten Aenderungen (Quelltext-Pruefsumme ef1af1a3...)' ausweisen und als technische Abgrenzung fuehren; 'unveraendert' streichen oder durch 'derselbe Stand fuer alle fuenf finalen Zeichnungen; elf fruehere Runden auf fuenf Vorstaenden wurden durch Korrekturen ueberholt' ersetzen. Verfahrensseitig: gate_entscheid fuer finale Zeichnungen einen sauberen Arbeitsbaum verlangen oder das Fixture des Endstands als Artefakt in die Zeichnung binden.

**Verdikt des Skeptikers:** widerlegt, korrigierte Schwere kein_befund.  
Der Befund steht und faellt mit der Behauptung, der gezeichnete Code sei "nicht der Commit 4b1abf0, sondern ein nicht committeter Zwischenstand", den "niemand aus dem Repo rekonstruieren kann". Das ist nachpruefbar falsch. Der Snapshot traegt neben dem dirty-Flag die Quelltext-Pruefsumme quellcode_sha256, deren Algorithmus in src/rechner_pipeline/gates/_provenienz.py:90-105 offen liegt (SHA-256 ueber alle .py/.xml-Dateien des Pakets, pfad- und laengengetrennt, sortiert). Ich habe diesen Algorithmus mit einem lesenden Skript ueber `git ls-tree`/`git cat-file` auf den SAUBEREN Baum jedes referenzierten Commits angewendet: fuer 4b1abf0 ergibt sich exakt ef1af1a32af7919d..., fuer 1bb4e3d 8224b424..., bd41f56 d5a95c0a..., e4230e9 0ba8d478..., abd31ca b6ef0524..., 8c5698c f32b72f0... — alle sechs Werte stimmen byte-genau mit den Snapshots ueberein (101 Paketdateien je Stand). Das dirty-Flag stammt damit ausschliesslich aus Aenderungen AUSSERHALB des ausfuehrbaren Pakets (`git status --porcelain` zaehlt auch dev-docs, tests, Fall-Artefakte und untracked Dateien). Der Verantwortliche Aktuar hat auf genau dem Code gezeichnet, den Commit 4b1abf0 enthaelt; die IT-Fuehrungskraft KANN ihn auschecken und die Pruefsumme selbst nachrechnen — die Werkzeuge-README-Forderung ("im oeffentlichen Repo nachschlagbar") ist damit fuer den Code erfuellt, sobald der Branch gepusht ist (4b1abf0 liegt auf fallbericht, dem Branch des offenen PR). Genau dafuer existiert die Pruefsumme laut Modul-Docstring: "dirty=ja allein waere kein exakter Stand" (_provenienz.py:12-14); ONBOARDING.md:279-280 dokumentiert das ebenso. Die Aussage des Abschlussberichts "einzigen, unveraenderten Systemstand" fuer die fuenf finalen Zeichnungen ist faktisch richtig (ein Commit, eine identische Pruefsumme). Die Fall-Seite verschweigt die frueheren Runden nicht: Kopfzeile "finale Zeichnungen auf Systemstand 4b1abf048ac8 (fruehere Runden auf 5 weiteren Staenden)" (index.md:6), Abschnitt "Die Zeichnungen" erklaert ueberholte Runden ausdruecklich und listet alle elf mit Status "ueberholt" (index.md:127-152), die technische Abgrenzung meldet "Die Entscheide beruhen auf verschiedenen Systemstaenden — 6 Staende" (erzeugt in werkzeuge/falldaten.py:775-780). Die 23 Korrekturen stehen im Veraenderungs-Dokument (docs/faelle/baldrian-lauf2-veraenderungen.md:92-93) und sogar auf der Fall-Seite selbst im Umbau-Abgrenzungstext. Die Gate-Berichte weisen dirty=ja und die Pruefsumme offen aus (aktuartest.html:591-592). Die Wirkung auf das Ziel ist konstruiert: Weder wird der IT-Leser in einen nicht auscheckbaren Stand gefuehrt, noch bedeutet "unveraendert" fuer den Fach-Leser etwas anderes, als die Artefakte hergeben. Der Belegzitat aus vorzeigeseite.py ("Arbeitsbaum sauber") ist eine aeltere, weiterhin im Repo liegende Werkzeuggeneration; die aktuelle Kette falldaten/fallbericht hat das Flag durch die aussagekraeftigere Abgrenzung nach Anzahl der Systemstaende ersetzt.

Praezisierung: Was vom Befund uebrig bleibt, ist kein Irrefuehrungs- oder Nachweisproblem, sondern ein optionaler Darstellungs-Feinschliff ohne Zielwirkung: (a) Die Fall-Seite koennte neben dem Commit-Hash die Quelltext-Pruefsumme und den Satz "Pruefsumme entspricht dem committeten Paketstand" ausweisen — dann muesste der IT-Leser die Uebereinstimmung nicht selbst nachrechnen. (b) Der Abschlussbericht koennte das Wort "unveraendert" durch "derselbe Stand fuer alle fuenf finalen Zeichnungen" ersetzen, um jede Lesart 'nie geaendert' auszuschliessen; die ueberholten Runden traegt bereits die Fall-Seite, auf die der Bericht verlinkt ist. Der verfahrensseitige Vorschlag des Pruefers (sauberer Arbeitsbaum als Zeichnungsvoraussetzung) ist nicht noetig: Die Pruefsumme ueber das Paket bindet den ausgefuehrten Code exakter als das grobe git-status-Flag, das auch Doku- und Artefakt-Aenderungen zaehlt.

Belege des Skeptikers:
    - `src/rechner_pipeline/gates/_provenienz.py`:12 — ``dirty=ja`` allein waere kein exakter Stand: zwei verschiedene lokale Codeaenderungen haetten sonst denselben Wert.
    - `src/rechner_pipeline/gates/_provenienz.py`:90 — def _quellcode_sha256() -> str:
    """SHA-256 des ausfuehrbaren Paketstands, pfad- und laengengetrennt."""
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-M4-32682e958c7811b0b5fc89c3e7eaf897243b2d39151facf5ba60c99397231a6e.json` — "commit": "4b1abf048ac84bfeecce12a67f18983648990799", "dirty": "ja", "quellcode_sha256": "ef1af1a32af7919d02f8b6826302949ad097de25f189957a420045a196ef2a43" — Nachrechnung ueber den sauberen Baum von 4b1abf0 (git ls-tree/cat-file, 101 Dateien) ergibt exakt denselben Wert; ebenso fuer alle fuenf Vorstaende (1bb4e3d, bd41f56, e4230e9, abd31ca, 8c5698c).
    - `ONBOARDING.md`:279 — A pure-Python SHA-256 over the installed package sources distinguishes different dirty code states.
    - `runs/seite/migrationen/baldrian/index.md`:6 — finale Zeichnungen auf Systemstand `4b1abf048ac8` (frühere Runden auf 5 weiteren Ständen)
    - `runs/seite/migrationen/baldrian/index.md`:129 — Frühere, im Lauf durch Korrekturen überholte Zeichnungsrunden bleiben erhalten — Entscheid-Snapshots werden nie entfernt.
    - `runs/seite/migrationen/baldrian/index.md`:142 — | A-Q1 | angenommen | 2026-09-01 | überholt | [`334b016d`](...) — elf Zeilen mit Status 'überholt' (142-152)
    - `werkzeuge/falldaten.py`:775 — if k.get("systemstaende_der_entscheide", 0) > 1:
    aus.append({"sicht": "technisch", ... "was": "Die Entscheide beruhen auf verschiedenen Systemstaenden",
    - `docs/faelle/baldrian-lauf2-veraenderungen.md`:92 — 1479 Tests vor dem Lauf, 1517 nach den 23 Korrekturen, 1534 nach Review-Nacharbeit und dem eingefrorenen Ende-zu-Ende-Fixture des Laufs.
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/berichte/aktuartest.html`:591 — <tr><th>dirty</th><td>ja</td></tr>
<tr><th>quellcode_sha256</th><td>ef1af1a32af7919d...</td></tr>
    - `docs/faelle/baldrian-lauf2.md`:12 — fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem einzigen, unveraenderten Systemstand gezeichnet

#### B2 — Entwickler-Identifikatoren dringen in die fuer Fuehrungskraefte gebaute Fall-Seite durch (Feldnamen, Rollen-IDs, Exit-Vokabular, Dateipfade, Commit-Kuerzel) (hoch, Sprache / Register)

Die generierte Fall-Seite ist erkennbar fuer Leser mit Vertrauens- statt Codebedarf gebaut (Kennzahl-Kacheln, Herkunftsangaben, Abgrenzungen). Doch an mindestens sechs Stellen steht Werkzeugsprache im Fach-Text: 'dk_stichtag_2 liegt nicht fuer jeden Vertrag vor' als FACHLICHE Abgrenzung; 'entschieden von: plv-aktuar' statt der Rolle 'Verantwortlicher Aktuar' (die Zuordnung plv-aktuar -> Verantwortlicher Aktuar steht in keiner Doku unter docs/, README oder ONBOARDING); 'gewaehlt **0.0125**' neben 'Lesart 1,25 %' in derselben Tabellenzeile; Prueschritte 'P-Q1.quellfragment ... passed'; unter 'Grenzen dieses Laufs' der Satz 'Umbau-Messung: src/rechner_pipeline/ontologie/code_karte.py: Schicht-Allowlist ...' samt 'Regime dev×PLV-IT' und Commit-Kuerzel '404974d'. Dieselbe Klasse zeigt der Abschlussbericht umgekehrt: Er spricht von 'Verantwortlicher Aktuar', waehrend Snapshot und Seite 'plv-aktuar' sagen — der Leser kann beide nicht zusammenfuehren.

**Wirkung auf das Ziel:** Die Fach-Fuehrungskraft stolpert in den beiden wichtigsten Abschnitten (Ergebnis-Abgrenzungen, Widerspruch/Entscheider) ueber Bezeichner, die sie nicht deuten kann, und verliert das Vertrauen, dass die Seite fuer sie geschrieben ist. Fuer die IT-Fuehrungskraft ist es umgekehrt harmlos, aber es entwertet die im Werkzeug angelegte Trennung 'fachlich/technisch': Ein als 'fachlich' markierter Befund mit rohem Feldnamen ist keine fachliche Aussage.

**Belege:**
    - `runs/seite/migrationen/baldrian/index.md`:40 — <b>dk_stichtag_2 liegt nicht fuer jeden Vertrag vor</b><span>811 von 834</span><i>fachlich</i>
    - `runs/seite/migrationen/baldrian/index.md`:62 — | Rechnungszins | 6 | 1,25 % (Mitteilung_143_KLV_TG2015.pdf); 1,75 % (Tarifrechner_KLV_TG2015.xlsm) | **0.0125** | plv-aktuar |
    - `runs/seite/migrationen/baldrian/index.md`:110 — | P-Q1.quellfragment | 1 | passed | [`json`](artefakte/abgeleitet/diagnostics/extract.gate.json) |
    - `runs/seite/migrationen/baldrian/index.md`:230 — * Umbau-Messung: src/rechner_pipeline/ontologie/code_karte.py: Schicht-Allowlist: Eine neue Kante zwischen zwei Schichten ist eine Architektur-Entscheidung (ADR-001, ADR-005). — begründet: „... im Regime dev×PLV-IT ... (404974d) ...“ *(technisch)*
    - `docs/faelle/baldrian-lauf2.md`:23 — Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar ueber die Zeichnungsordnung)

**Widerlegungsversuch des Pruefers:** Versucht: Die Seite markiert Abgrenzungen als 'fachlich'/'technisch', und werkzeuge/README erklaert, dass Abgrenzungen ABGELEITET und nicht geschrieben werden — Rohwerte sind also Nebenwirkung der Ableitung, keine Absicht. Der Umbau-Text stammt woertlich aus umbaubudget.json (Menschentscheidung). Haelt nicht: Ableitung entbindet nicht von Beschriftung; falldaten.py kennt die Pruefgroesse und koennte 'Deckungskapital zum Kontrollstichtag' schreiben. Die Umbau-Begruendung ist ein Satz fuer die Fachseite und wurde mit Regie-Vokabular ('dev×PLV-IT') verfasst; der Renderer uebernimmt ihn ungefiltert in den Abschnitt 'Grenzen dieses Laufs'.

**Vorschlag:** Im Renderer ein Beschriftungs-Woerterbuch fuer Pruefgroessen, Rollen-IDs und Gate-Kennungen (dk_stichtag_2 -> 'Deckungskapital zum Kontrollstichtag', plv-aktuar -> 'Verantwortlicher Aktuar (Zeichnungsordnung)', passed -> 'bestanden'); Prozentwerte einheitlich in der Lesart der Quelle darstellen; Umbau-Befunde in der Fach-Sicht auf den Klartext 'neue Schicht-Kante, begruendet' reduzieren und Pfad/Commit nur in der technischen Sicht zeigen; die Rollen-Zuordnung einmal in docs (ADR-012 oder Zeichnungsordnung) niederschreiben.

**Verdikt des Skeptikers:** nicht widerlegt, korrigierte Schwere mittel.  
Alle fuenf Belege stehen woertlich so in runs/seite/migrationen/baldrian/index.md (Zeilen 40, 62, 110, 230) bzw. docs/faelle/baldrian-lauf2.md (Zeile 23). Der Widerlegungsversuch scheitert an drei Punkten. (1) Kein bewusst dokumentierter Rand: Der Erzeuger der Seite ist werkzeuge/vorzeigeseite.py auf dem Branch vorzeige-url (Worktree ~/git/rechner-pipeline-vorzeige, HEAD 0a787e1) — er fuehrt bereits Beschriftungs-Woerterbuecher (FELD_TITEL, SCHICHT_TITEL, STATUS_TITEL, _urteilswort, _lesart_text), wendet sie aber nur teilweise an: 'Urteil' der Pruefschritte ist g['status'] roh ('passed', Zeile 695), 'entschieden von' ist die Rollen-ID roh (Zeile 615), Abgrenzungen uebernehmen den Rohschluessel aus falldaten ('f"{k} liegt nicht fuer jeden Vertrag vor"', falldaten.py Zeile 723, Sicht 'fachlich'), und darstellung.abgrenzung_karten haengt Umbau-Befund samt Dateipfad und Begruendungs-Rohtext an (darstellung.py Zeile 159-160). Die Maintainer-Norm dazu ist im Repo festgeschrieben (.claude/skills/dokumentiere-system/SKILL.md Zeile 54-61: erzeugte Berichte ohne Repositories, Commits, Branches) und der Commit db0ce47 'schlanke Hauptseite, Fachton' bekennt sich ausdruecklich zum 'Ton eines VU-Dokuments' fuer den Fallbericht — es ist also der eigene Massstab des Projekts, kein von aussen herangetragener. (2) Das '0.0125 neben 1,25 %' ist ein konkreter Defekt, nicht Datentreue: darstellung.diskrepanz_gruppen stringifiziert den gewaehlten Wert (Zeile 290: g["gewaehlt"].add(str(d["gewaehlt"]))), _lesart_text (vorzeigeseite.py 418-421) formatiert aber nur int/float — Lesarten aus abox.json (Float 0.0125) werden zu '1,25 %', der gewaehlte Wert bleibt '0.0125'. Der Diff db0ce47..0a787e1 aendert daran nichts; der Befund gilt am HEAD des Erzeugers. (3) Rollen-Zuordnung: 'plv-aktuar' -> 'Verantwortlicher Aktuar' steht in keiner Datei unter docs/, README.md oder ONBOARDING.md; faelle/zeichnungsordnung.json traegt nur Schluessel-Hash und Gates, keinen Anzeigenamen; einzig dev-docs/regie.md Zeile 27 nennt 'plv-aktuar (unabhaengige zeichnende Fachinstanz)'. Der Abschlussbericht sagt 'Rolle Verantwortlicher Aktuar', A-Box und Snapshots sagen entscheider 'plv-aktuar' (abox.json diskrepanzen[1].entscheidung.entscheider; Snapshot A-Q1-fd793260 /entscheider). Kein Test deckt die Beschriftung ab (tests/test_werkzeuge.py prueft Abgrenzungen nur ueber Teilstrings der Rohtexte). Dieselbe Klasse existiert auf dem geprueften Branch fallbericht in werkzeuge/fallbericht.py (_befunde: Feld, Lesarten, gewaehlt roh; _abgrenzungen: 'was' roh). Schwere aber uebertrieben: Von sechs Stellen liegen drei in als 'technisch' markierten oder protokollartigen Abschnitten (Umbau-Messung *(technisch)*, 'passed' im Ablaufprotokoll 'Wie es lief', Commit-Kuerzel im Begruendungszitat) — dort ist Werkzeugsprache verteidigbar, und der Vorschlag des Pruefers selbst laesst Pfad/Commit in der technischen Sicht zu. Die Seite erklaert zudem 'entschieden hat die zeichnende Rolle' und die Zeichnungs-Tabelle weist die Schluesselrolle nach; der Leser kann Rolle und Bericht mit Aufwand zusammenfuehren. Der Kern (dk_stichtag_2 als 'fachliche' Kachel, 0.0125 vs. 1,25 %, Rollen-ID statt Rollenname) ist ein Beschriftungsdefekt einer Beobachtungshilfe mit kleiner Reparatur, ohne Auswirkung auf Richtigkeit oder Nachweiskette: mittel.

Praezisierung: B2 (praezisiert): Der Seitenerzeuger werkzeuge/vorzeigeseite.py (Branch vorzeige-url) besitzt Beschriftungs-Woerterbuecher, laesst aber drei Stellen in fachlichen Abschnitten roh: (a) die Abgrenzungs-Kachel 'dk_stichtag_2 liegt nicht fuer jeden Vertrag vor' entsteht in falldaten.py Zeile 723 aus dem Rohschluessel der Pruefgroesse und ist als 'fachlich' markiert; (b) in 'Der Widerspruch' wird der gewaehlte Wert vor der Formatierung stringifiziert (darstellung.py Zeile 290), sodass _lesart_text nicht greift — '0.0125' neben '1,25 %'; (c) 'entschieden von' zeigt die Rollen-ID 'plv-aktuar', deren Klartext 'Verantwortlicher Aktuar' nur im Abschlussbericht und in A-Box-Begruendungen steht, nicht in docs/, README, ONBOARDING oder der Zeichnungsordnung. Dazu 'passed' als Urteilswort im Ablaufprotokoll (vorzeigeseite.py Zeile 695), obwohl _urteilswort fuer die Abnahmen 'bestanden' schreibt. Umbau-Messung mit Pfad, Regime-Vokabular und Commit-Kuerzel ist als '(technisch)' markiert und damit im Rahmen der Zwei-Sichten-Trennung vertretbar, gehoert aber nicht in den Kachelblock der Ergebnisseite. Dieselbe Klasse liegt auf dem Branch fallbericht in werkzeuge/fallbericht.py (_befunde, _abgrenzungen). Keine Auswirkung auf Rechnung oder Nachweiskette; Reparatur: Beschriftungs-Woerterbuch fuer Pruefgroessen und Rollen, str()-Cast in diskrepanz_gruppen entfernen bzw. _lesart_text vorher anwenden, 'passed' ueber _urteilswort fuehren, Rollen-Klartext einmal in docs niederschreiben.

Belege des Skeptikers:
    - `/home/bartl/git/rechner-pipeline/runs/seite/migrationen/baldrian/index.md`:40 — <b>dk_stichtag_2 liegt nicht fuer jeden Vertrag vor</b><span>811 von 834</span><i>fachlich</i>
    - `/home/bartl/git/rechner-pipeline/runs/seite/migrationen/baldrian/index.md`:62 — | Rechnungszins | 6 | 1,25 % (Mitteilung_143_KLV_TG2015.pdf); 1,75 % (Tarifrechner_KLV_TG2015.xlsm) | **0.0125** | plv-aktuar |
    - `/home/bartl/git/rechner-pipeline/runs/seite/migrationen/baldrian/index.md`:110 — | P-Q1.quellfragment | 1 | passed | [`json`](artefakte/abgeleitet/diagnostics/extract.gate.json) |
    - `/home/bartl/git/rechner-pipeline-vorzeige/werkzeuge/darstellung.py`:290 — g["gewaehlt"].add(str(d["gewaehlt"]))
    - `/home/bartl/git/rechner-pipeline-vorzeige/werkzeuge/vorzeigeseite.py`:419 — if feld == "zins" and isinstance(wert, (int, float)) and float(wert) < 1:
        return f"{float(wert) * 100:.2f} %".replace(".", ",")
    - `/home/bartl/git/rechner-pipeline-vorzeige/werkzeuge/vorzeigeseite.py`:695 — z.append(f"| {g['gate']} | {g.get('versuch') or 1} | {g['status']} | {zelle} |")
    - `/home/bartl/git/rechner-pipeline-vorzeige/werkzeuge/vorzeigeseite.py`:615 — f"| {lesarten} | **{gew}** | {', '.join(g['entscheider']) or '—'} |")
    - `/home/bartl/git/rechner-pipeline/werkzeuge/falldaten.py`:723 — "was": f"{k} liegt nicht fuer jeden Vertrag vor",
    - `/home/bartl/git/rechner-pipeline-vorzeige/werkzeuge/darstellung.py`:159 — karten.append((f"Umbau-Messung: {befund}",
               f"begründet: „{grund}“" if grund else "ohne Begründung",
    - `/home/bartl/git/rechner-pipeline/faelle/zeichnungsordnung.json`:4 — "plv-aktuar": {
      "schluessel_sha256": "162817c9...",
      "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4"]
    - `/home/bartl/git/rechner-pipeline/dev-docs/regie.md`:27 — Katalog-Erweiterungen), `plv-aktuar` (unabhaengige zeichnende
  Fachinstanz: A-Q1, A-M1..M4, eigener Schluessel
    - `/home/bartl/git/rechner-pipeline/docs/faelle/baldrian-lauf2.md`:23 — Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar
ueber die Zeichnungsordnung)
    - `/home/bartl/git/rechner-pipeline/.claude/skills/dokumentiere-system/SKILL.md`:54 — **Fachdokumente sprechen die Sprache des Unternehmens.** [...] einen erzeugten Bericht liest, ist Aktuar, Pruefer, Revision oder Vorstand. Dort gibt es keine Repositories, Commits, Branches
    - `/home/bartl/git/rechner-pipeline/werkzeuge/fallbericht.py`:339 — zeilen.append([_e(e.get("feld")), _e(e.get("knoten")), werte,
               f'<b>{_e(e.get("gewaehlt"))}</b>'])

#### B3 — Die Einstiegs- und Rahmendokumentation beschreibt den Stand vor dem Lauf: veraltete Kernversion, ausser Betrieb genommener Kreuzcheck, 'teilweise ueberholtes' Pflichtdokument, Lieferung 1 statt Lieferung 2 (hoch, Doku-Drift / Einstieg)

ONBOARDING.md nennt Kern 3.0.1 (Code: 3.4.0; das Veraenderungs-Dokument beschreibt 3.1.0 -> 3.4.0 waehrend des Laufs), beschreibt den Kommutations-Zweitkern als 'cross-check rail (ADR-004)' obwohl ADR-013 den Kreuzcheck ausser Betrieb genommen hat, und schickt den Leser zuerst in migrations-pipeline-v01.md — ein Dokument, das sich selbst als 'Teilweise ueberholt (Stand 2026-08-15)' kennzeichnet und behauptet, die menschlichen Gates des Falls 'stehen aus'. Dasselbe Dokument verlinkt die Unternehmens-IT-Seite als 'vollstaendig eingespielt'. README, ONBOARDING und lieferungen/README fuehren den Selbst-Durchfuehrer zu lieferungen/baldrian/ (Lauf 1); die Lieferung des dokumentierten Falls (lieferungen/baldrian-2, mit AVB-PDF und PDF-Mitteilung) ist nirgends beschrieben. README verweist an keiner Stelle auf docs/faelle/.

**Wirkung auf das Ziel:** Die IT-Fuehrungskraft, die den empfohlenen Lesepfad nimmt, landet in einem Dokument, das ihr sagt, der Fall sei nicht abgenommen — waehrend die Vorfuehrung das Gegenteil zeigt. Wer die Vorfuehrung nachstellt, rechnet mit der falschen Lieferung ein anderes Ergebnis (500 statt 834 Vertraege) und kann den Abschlussbericht nicht reproduzieren. Versionsangaben, die um drei Minor-Stufen daneben liegen, signalisieren einem IT-Leiter, dass Doku und Code nicht gemeinsam gepflegt werden — das Gegenteil der Botschaft 'Beschreibung und Code koennen nicht auseinanderlaufen'.

**Belege:**
    - `ONBOARDING.md`:8 — 1. **The target kernel** (`rechner_pipeline.kern`, version 3.0.1)
    - `src/rechner_pipeline/kern/__init__.py`:113 — __version__ = "3.4.0"
    - `ONBOARDING.md`:11 — Commutation values live in a **separate second kernel** used only as a cross-check rail (ADR-004).
    - `docs/architektur/adr-013-kommutations-kreuzcheck-ausser-betrieb.md`:1 — # ADR-013: Der Kommutations-Kreuzcheck wird ausser Betrieb genommen ... der Zweitkern bleibt ohne Konsumenten im Produktivpfad.
    - `docs/architektur/migrations-pipeline-v01.md`:3 — > **Teilweise ueberholt (Stand des Dokuments: 2026-08-15).** ... die MENSCHLICHEN Gates A-Q1/A-M1/A-M4 des Falls stehen aus
    - `vorzeige-seite/it/index.md`:46 — Das Konzept dahinter ist vollständig eingespielt: die [Migrations-Pipeline](architektur/migrations-pipeline-v01.html)
    - `README.md`:346 — Der erste durchgängige Fall übernimmt den KLV-Bestand (Tarifgeneration TG2015) der fiktiven **Baldrian Leben** ... die Lieferung dazu liegt unter `lieferungen/baldrian/`

**Widerlegungsversuch des Pruefers:** Versucht: migrations-pipeline-v01.md traegt einen ehrlichen Ueberholt-Vorspann und verweist auf skill-architektur.md — die Drift ist gekennzeichnet. ONBOARDING ist ein Entwickler-Dokument, nicht die Fuehrungs-Doku. lieferungen/baldrian-2 koennte absichtlich undokumentiert sein (Vorfuehrfall-Aufloesung). Haelt nicht: Ein Vorspann 'teilweise ueberholt' entschuldigt nicht, dass ONBOARDING und die Unternehmens-IT-Seite ihn als Erst- bzw. Vollreferenz fuehren; die Versionsangabe und der ADR-004-Verweis sind schlicht falsch, nicht gekennzeichnet; und die Vorfuehrung beruft sich ausdruecklich auf Selbst-Durchfuehrbarkeit (README 'zum Selbst-Durchfuehren'), die dann zur falschen Lieferung fuehrt.

**Vorschlag:** ONBOARDING Abschnitt 1 auf Kern 3.4.0, ADR-013 und den Lesepfad skill-architektur -> ADRs -> Landkarte umstellen; migrations-pipeline-v01.md aus dem Erst-Lesepfad und aus der IT-Seite nehmen oder durch ein aktuelles Pipeline-Dokument ersetzen; lieferungen/README um baldrian-2 ergaenzen und README/ONBOARDING auf die Lieferung des dokumentierten Falls zeigen; README-Abschnitt 'Die Migrationsfaelle' um Links auf docs/faelle/baldrian-lauf2.md und -veraenderungen.md ergaenzen.

#### B4 — Im gepruefen Arbeitsverzeichnis existieren zwei Staende des Demonstrationsmaterials: eingecheckte Unternehmensseiten mit Lauf-1-Zahlen neben einem generierten Auftritt, den die eingecheckten Werkzeuge dieses Branches nicht erzeugen (mittel, Konsistenz / Werkzeugkette)

Vier eingecheckte Unternehmensseiten (index, migrationen, finanzen, geschaeftsentwicklung) fuehren fest geschriebene Zahlen des ersten Laufs: 500 Vertraege, 22.488.836,41 EUR, 42 Geschaeftsvorfaelle, 460/40 beitragspflichtig/-frei, 'Tranche 1'. Abschlussbericht und generierter Auftritt (runs/seite) sagen 834 Vertraege, 33.437.445,97 EUR, 166 Vorfaelle. Der generierte Auftritt stammt laut eigenem Stempel vom Branch vorzeige-url (db0ce47), auf dem die Unternehmensseiten als Vorlagen mit Platzhaltern aus dem Datenmodell gefuellt werden ('{{euro:bestand.abzuege.0.deckkap.summe}}'); auf dem gepruefen Branch fehlen diese Vorlagen und die Werkzeugmodule darstellung.py/grafik.py. dev-docs/merge-plan-lauf2.md fuehrt vorzeige-url als eigenen, noch nicht gemergten Strang — der Zustand ist geplant, aber fuer jeden Leser des Branches ein Widerspruch.

**Wirkung auf das Ziel:** Wer das Repository (nicht die gebaute Seite) als Dokumentation liest — etwa eine IT-Fuehrungskraft, die 'quelloffen' ernst nimmt — findet fuer denselben Migrationsgegenstand zwei Vertragszahlen und zwei Deckungskapitalien und kann nicht entscheiden, welche gilt. Die Aussage 'Der Entwurf wird nicht gepflegt, sondern ERZEUGT — so kann er nicht zurueckbleiben' ist auf diesem Branch nicht wahr, weil die Erzeugung hier noch nicht existiert.

**Belege:**
    - `vorzeige-seite/migrationen/index.md`:15 — | Baldrian, Tranche 1 | 01.01.2026 | 500 | 22.488.836,41 € | aktuariell abgenommen | [Zum Bericht](baldrian/) |
    - `vorzeige-seite/finanzen/index.md`:15 — | Übernommenes Deckungskapital (01.01.2026) | 22.488.836,41 € | ... | Verträge | 500 |
    - `vorzeige-seite/geschaeftsentwicklung/index.md`:28 — Übernahmebestand der Tranche Baldrian 1 (01.01.2026 bis 01.01.2027) wurden 42 Geschäftsvorfälle geliefert
    - `runs/seite/migrationen/baldrian/index.md`:265 — *Diese Seite wurde am 2026-09-03 aus dem Systemstand `db0ce475002d` (vorzeige-url) erzeugt.*
    - `werkzeuge/README.md`:41 — Der Entwurf wird nicht gepflegt, sondern ERZEUGT — ein Kommando faehrt die ganze Kette aus den aktuellen Quellen
    - `dev-docs/merge-plan-lauf2.md`:20 — | vorzeige-url | 13 eigene | nein | Vorzeigeseite; Kopplung tests/test_baldrian_e2e.py |

**Widerlegungsversuch des Pruefers:** Versucht und teilweise gelungen: Auf Branch vorzeige-url sind die Unternehmensseiten templatisiert (git show vorzeige-url:vorzeige-seite/finanzen/index.md Zeile 15: '{{euro:bestand.abzuege.0.deckkap.summe}} €'), der generierte Auftritt traegt die Lauf-2-Zahlen konsistent, und der Merge-Plan dokumentiert den Strang. Die Sammler-These 'handgepflegt und vergessen' ist damit widerlegt. Was bleibt: Der zur Pruefung vorgelegte Branch traegt die alten Zahlen fest, und seine Werkzeuge koennen den gezeigten Auftritt nicht bauen — ein Leser ohne Kenntnis des Merge-Plans sieht den Widerspruch. Deshalb 'mittel' statt 'hoch'.

**Vorschlag:** Den Strang vorzeige-url vor der Vorfuehrung mergen oder auf dem gepruefen Branch die vier Seiten auf Platzhalter umstellen; bis dahin im werkzeuge/README einen Hinweis 'Unternehmensseiten dieses Branches tragen noch Lauf-1-Zahlen; der aktuelle Auftritt wird aus Branch vorzeige-url gebaut' fuehren. Als Klasse: eine Drift-Pruefung, die eingecheckte Zahlen gegen das Datenmodell haelt (drift.py kennt heute nur gh-pages gegen Entwurf).

#### B5 — Abschlussbericht und Fall-Seite legen unterschiedliche fachliche Grenzen offen — das Restrisiko-Bild haengt davon ab, welches Dokument die Fach-Fuehrungskraft zuerst liest (hoch, Vollstaendigkeit / Restrisiko)

Vier Stellen: (a) Der Abschlussbericht meldet zu A-Q1 'Golden Master 616/616 exakt reproduziert'; nur die Seite sagt 'Erwartungswerte lagen fuer 1 von 6 Tarifzellen vor'. Der Bestand belegt alle sechs Zellen (Nichtraucher/Raucher x Einzel/Kollektiv/Haus, kleinste Zelle 45 Vertraege) — der Quell-Rechner-Vergleich deckt also fuenf Sechstel der Zellen nicht ab; das steht nirgends im Abschlussbericht, auch nicht unter 'Offene Punkte'. (b) Der Abschlussbericht schreibt zu A-M4 'Vollbestand, 834 Vertraege ... keine Befunde'; die Seite fuehrt als fachliche Abgrenzung, dass die zweite Stichtagsgroesse nur fuer 811 von 834 Vertraegen vorlag. (c) Die Seite zeigt fuer A-M2 'erlaubt 100,0 ct' neben 5,0 ct fuer A-M1/A-M3 ohne Erklaerung; die Begruendung ('bekannte Enge der Profilstruktur, keine fachliche Aussage') steht nur im Testprofil des Detailberichts. (d) Der Widerspruchs-Abschnitt der Seite zaehlt '2 Feststellungen ueber 6 Tarifzellen' plus '6 Stellen in zwei Schreibweisen'; der Abschlussbericht spricht von 'drei Diskrepanz-Typen, vierzehn Einzelentscheiden' — dieselbe Sache, zwei Zaehlweisen.

**Wirkung auf das Ziel:** Die Fach-Fuehrungskraft soll nach zehn Minuten wissen, welches Restrisiko bleibt. Liest sie nur den Abschlussbericht, haelt sie den Quell-Rechner fuer vollstaendig nachgerechnet und den Vollbestand fuer luecklos geprueft; liest sie die Seite, sieht sie zwei Einschraenkungen, die der offizielle Bericht nicht kennt, und fragt sich, warum eine Abnahme zwanzigmal weichere Grenzen hat. Beides untergraebt die Glaubwuerdigkeit des jeweils anderen Dokuments.

**Belege:**
    - `docs/faelle/baldrian-lauf2.md`:17 — | A-Q1 | Quell-Tarifwerk und Spezifikation | angenommen; Golden Master 616/616 exakt reproduziert |
    - `runs/seite/migrationen/baldrian/index.md`:36 — Quell-Tarifrechner nachgerechnet: 616 Werte verglichen, 0 Abweichungen — Erwartungswerte lagen für 1 von 6 Tarifzellen vor.
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/diagnostics/generation_golden.gate.json` — "zellen_gesamt": 6, "zellen_ohne_erwartungswerte": ["klv/tg2015/zelle:nichtraucher,haus", "...kollektiv", "...raucher,einzel", "...raucher,haus", "...raucher,kollektiv"]
    - `faelle/baldrian-klv-tg2015-lauf2/eingang/baldrian_bestandsabzug_2026-01-01.csv` — Spalten RK x BGRP: NR/E 246, NR/K 212, NR/H 180, R/E 82, R/K 69, R/H 45 — alle sechs Zellen belegt (eigene Auszaehlung)
    - `docs/faelle/baldrian-lauf2.md`:21 — | A-M4 | Migrationscontrolling (Vollbestand, 834 Vertraege) | 834/834 bestanden, 2508 Einzelpruefungen, keine Befunde |
    - `runs/seite/migrationen/baldrian/index.md`:32 — | [A-M2 Verlaufstest](...) | fünf und zehn Jahre nach der Übernahme, und der Ablauf | 100 | 520 | 2,1 ct | 100,0 ct | bestanden |
    - `docs/faelle/baldrian-lauf2.md`:66 — (drei Diskrepanz-Typen, vierzehn Einzelentscheide im Rahmen von A-Q1 ...)

**Widerlegungsversuch des Pruefers:** Versucht: (a) Die aktuariellen Abnahmen A-M1 bis A-M4 pruefen alle 834 Vertraege ueber alle Zellen gegen gelieferte Erwartungswerte — die Zellenluecke des Golden Master ist fachlich abgedeckt; die Seite sagt es ausdruecklich. (b) 811/834 ist eine Liefereigenschaft (23 Abgaenge zwischen den Stichtagen, Kreuzprobe 23 gegen 23 geht auf), also kein Pruefdefizit. (c) Das A-M2-Profil begruendet die Grenze im Detailbericht. (d) Beide Zaehlungen ergeben 14. Haelt nur teilweise: Dass etwas abgedeckt oder erklaerbar ist, entbindet den Abschlussbericht nicht, es zu sagen — die Seite tut es, der Bericht nicht; und die A-M2-Begruendung ist als 'bekannte Enge, keine fachliche Aussage' gerade KEINE fachliche Rechtfertigung einer zwanzigfach weiteren Toleranz. Die unterschiedlichen Zaehlweisen sind fuer sich unschaedlich, addieren sich aber zum Eindruck zweier Berichte.

**Vorschlag:** Im Abschlussbericht einen Abschnitt 'Was geprueft ist und was nicht' mit genau den abgeleiteten Abgrenzungen der Seite (Golden-Master-Zellen 1/6 mit Verweis auf die Vollabdeckung durch A-M1..A-M4; 811/834 mit der Abgangs-Kreuzprobe; A-M2-Grenze mit fachlicher Begruendung oder Ankuendigung der Verengung); falldaten.py die Golden-Master-Zellenabdeckung als Abgrenzung fuehren lassen; die Toleranzspalte der Seite mit einem Kurzverweis 'warum 100 ct' versehen; Diskrepanz-Zaehlung in Bericht und Seite auf eine Lesart (Typen / Zellen / Einzelentscheide) bringen.

#### B6 — Das Design-Dokument des Falls fehlt als Fachdokument: keine Migrationskonzept-Instanz, und die 'Tarifplan-Ausgestaltung', auf die der einzige offene Punkt zeigt, ist eine unveroeffentlichte Arbeitschronik (hoch, Design-Dokumentation / Erreichbarkeit)

docs/migrationskonzept/README verlangt je Fall eine ausgefuellte Instanz im Fall-Arbeitsbereich; im Fall existiert keine (einzige Erwaehnung des Worts ist die Ausgestaltungs-Chronik). Der Abschlussbericht verortet den einzigen offenen Punkt 'in der Tarifplan-Ausgestaltung des Falls', das Veraenderungs-Dokument belegt drei Einzelentscheide dort, die Umbau-Begruendung verweist auf das 'Korrektur-Protokoll des Falls'. Beide Dokumente stehen nicht in der Positivliste UEBERNEHMEN der Veroeffentlichung und tauchen im Artefaktverzeichnis der Seite nicht auf — der Leser der Seite kann keinem dieser Verweise folgen. Die Ausgestaltung selbst (568 Zeilen) beginnt mit einem Status-Log ('ALLE FUENF GATES GEZEICHNET ...'), traegt das eigentliche Dokument ab Zeile 85 und darunter einen veralteten 'Status: Entwurf steht; A-Q1-faehig erst nach ...' — ein Arbeitsdokument, kein fuer Fachleitung lesbares Design.

**Wirkung auf das Ziel:** Die Fach-Fuehrungskraft soll 'Design' und 'Restrisiko' verstehen. Das einzige explizit offene Restrisiko zeigt auf ein Dokument, das sie nicht erreicht und das — wenn sie es erreicht — mit einem widerspruechlichen Status beginnt. Ein Migrationskonzept, das laut eigener Vorlage Projektleitung, Quellsystem-Verantwortliche und Fachexperte Aktuariat freigeben, gibt es fuer den Vorfuehrfall nicht; damit fehlt das Dokument, das eine Fuehrungskraft ueblicherweise als 'das Design' erwartet.

**Belege:**
    - `docs/migrationskonzept/README.md`:15 — Die ausgefuellte Instanz eines Falls gehoert in seinen Arbeitsbereich (`faelle/<fall>/`, gitignored, ADR-002)
    - `docs/faelle/baldrian-lauf2.md`:143 — Einziger fachlich offener Punkt ist die vorstehende Falsifizierbarkeits-Auflage; ... in der Tarifplan-Ausgestaltung des Falls als Pflicht-Testpunkt kuenftiger Verlaufspruefungen festgehalten.
    - `werkzeuge/vorzeigeseite.py`:78 — UEBERNEHMEN = ( ("eingang.json", ...), ("fall.json", ...), ("abgeleitet/berichte", ...), ("abgeleitet/bestand-nach", ...), ("abgeleitet/diagnostics", ...), ("entscheide", ...), )
    - `runs/seite/migrationen/baldrian/index.md`:247 — ... ist Teil dieser Kette und im Korrektur-Protokoll des Falls vermerkt.“
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/tarifplan-ausgestaltung.md`:1 — **ALLE FUENF GATES GEZEICHNET 2026-09-01, Systemstand 4b1abf0** (plv-aktuar, Zeichnungsordnungs-Rolle plv-aktuar aus dem Schluessel-Fingerprint abgeleitet ...
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/tarifplan-ausgestaltung.md`:202 — ## Status  Entwurf steht; A-Q1-faehig erst nach: (1) Antwort "baldrian" zu Dynamiksatz ...

**Widerlegungsversuch des Pruefers:** Versucht: Der Abschlussbericht Abschnitt 4 'Bewertungsmethodik' und das Veraenderungs-Dokument Abschnitt 1 (Tabelle vor/nach Lauf 2) tragen den fachlichen Kern der Ausgestaltung in Fuehrungssprache — ein Design-Extrakt existiert also. Die Migrationskonzept-Vorlage ist selbst erst v0.2 'Geruest', die Instanz koennte bewusst nachgelagert sein. Die Nichtveroeffentlichung der Chronik kann Regie-Schutz sein. Haelt nicht: Die Verweise im Abschlussbericht und in der Umbau-Begruendung sind konkret und fuehren ins Leere; eine Vorlage, die 'je Fall instanziiert' vorschreibt und im einzigen Fall nicht instanziiert ist, ist fuer den Leser ein Bruch; die Chronik enthaelt keine Regie-Aufloesungen, sondern den Testfallkatalog, den der Bericht als Beleg nennt.

**Vorschlag:** Aus der Ausgestaltungs-Chronik ein kurzes, datiertes Fachdokument 'Ausgestaltung Baldrian KLV TG2015' (Abschnitte 1-5 ohne Status-Log) ableiten und in die Positivliste aufnehmen (oder als abgeleitet/berichte/ausgestaltung.html rendern); das Korrektur-Protokoll in eine Kurzfassung 'Korrekturen des Laufs' (23 Zeilen, Grund, Gebiet) fuer die technische Sicht ueberfuehren; Kapitel 1-4 und 8-11 der Migrationskonzept-Vorlage fuer Baldrian befuellen — die Inhalte liegen in Abschlussbericht, Lieferschein und Auskuenften bereits vor.

#### B7 — Die beiden Fach-Berichte stehen in ASCII-Umschrift ('Uebernommen', 'Vertraege') und werden unveraendert neben Seiten mit echten Umlauten veroeffentlicht (mittel, Sprache / Form)

Abschlussbericht und Veraenderungs-Dokument sind vollstaendig in Repo-Umschrift geschrieben (ue/ae/oe/ss). unternehmensseite.py spielt sie als abschlussbericht-baldrian.html und veraenderungen-baldrian.html ein, ohne die Umschrift aufzuloesen; die umgebenden Seiten (Uebersicht, Fall-Seite, Bereichsseiten) verwenden echte Umlaute. Auf derselben Seite steht damit 'Die abgeschlossenen Übernahmen mit ihren gezeichneten Abnahmen' neben 'Uebernommen wurden 834 Vertraege'.

**Wirkung auf das Ziel:** Fuer Fuehrungskraefte eines Versicherungsunternehmens ist ein Abnahmebericht ohne Umlaute ein Formfehler, der die Ernsthaftigkeit des gesamten Auftritts in Frage stellt — gerade das Dokument, das die 'fachliche Wuerdigung' tragen soll, wirkt wie ein Rohexport. Es ist die sichtbarste Stelle, an der Repo-Konventionen die Unternehmenssprache ueberlagern.

**Belege:**
    - `docs/faelle/baldrian-lauf2.md`:39 — Uebernommen wurden 834 Vertraege der Tarifgeneration KLV TG2015
    - `runs/seite/migrationen/abschlussbericht-baldrian.md`:44 — Uebernommen wurden 834 Vertraege der Tarifgeneration KLV TG2015
    - `runs/seite/migrationen/index.md`:7 — Die abgeschlossenen Übernahmen mit ihren gezeichneten Abnahmen, der Prüfkette und den Artefakten

**Widerlegungsversuch des Pruefers:** Versucht: Die Repo-Regel (ASCII in eingecheckten Texten) ist eine bewusste Konvention, und docs/tarifplaene sowie docs/mathematik werden ueber eine Doku-Engine zu PDF gerendert, die moeglicherweise Umlaute herstellt. Haelt nicht: docs/faelle laeuft nicht ueber die Engine, sondern wird als Markdown kopiert; vorzeige-seite/ zeigt, dass echte Umlaute im Repo erlaubt sind; die Konvention gilt erkennbar fuer Entwickler-Texte, nicht fuer Unternehmensdokumente (dev-docs/README trennt beide Welten ausdruecklich).

**Vorschlag:** docs/faelle/ den Unternehmensdokumenten zuschlagen (echte Umlaute, wie vorzeige-seite/), oder unternehmensseite.py beim Einspielen eine deterministische Umschrift-Aufloesung fuer diesen Ordner ausfuehren lassen; die Regel in dokumentiere-system festhalten.

#### B8 — Der eingecheckte Abschlussbericht tritt als Dokument eines Versicherers auf und meldet eine Zeichnung durch den 'Verantwortlichen Aktuar', ohne den Simulations-Charakter zu nennen (mittel, Kennzeichnung / Irrefuehrung)

docs/faelle/baldrian-lauf2.md ist als 'Pfefferminzia Lebensversicherung — Programm Bestandsmigration. Abnahmebericht' verfasst und berichtet, alle Gates seien 'vom Verantwortlichen Aktuar ... gezeichnet', mit SHA-256-Belegen. Dass der Schluessel ein Simulationsschluessel ist und die Rolle 'die der Simulation', steht nur auf der Fall-Seite und in der Banderole des Auftritts; das eingecheckte Dokument selbst — auf GitHub ohne Banderole lesbar — traegt keinen Hinweis. werkzeuge/README begruendet die Banderole genau mit diesem Risiko.

**Wirkung auf das Ziel:** Eine Fuehrungskraft, der das Dokument als Datei oder GitHub-Link zugeht, liest eine echte aktuarielle Abnahme. Das ist das Gegenteil der im Werkzeug erzwungenen Kennzeichnung und trifft ausgerechnet das Dokument, das fuer die Fachleitung geschrieben wurde.

**Belege:**
    - `docs/faelle/baldrian-lauf2.md`:3 — Pfefferminzia Lebensversicherung — Programm Bestandsmigration. Abnahmebericht zur Uebernahme des Baldrian-Teilbestands KLV TG2015
    - `runs/seite/migrationen/baldrian/index.md`:154 — Der Fingerabdruck weist die **Schlüsselrolle** nach, nicht die Identität einer natürlichen Person — hier die der Simulation.
    - `werkzeuge/README.md`:265 — Ohne ihn saehe eine oeffentliche Seite mit signierten aktuariellen Abnahmen aus wie eine echte.

**Widerlegungsversuch des Pruefers:** Versucht: README Abschnitt 'Die Beispielartefakte: die PLV-Fiktion' erklaert die Fiktion fuer das ganze Repo; die Unternehmensseite ergaenzt die Banderole beim Einspielen. Haelt nicht: Ein einzeln weitergereichter Bericht traegt weder README noch Banderole; die Kennzeichnungspflicht, die das Werkzeug fuer Seiten erzwingt, ist fuer das Quelldokument nicht erfuellt.

**Vorschlag:** Eine Kopfzeile im Dokument selbst ('Vorfuehrfall: fiktives Unternehmen, synthetischer Bestand, Zeichnung mit Simulationsschluessel — Fingerabdruck 162817c9...') und die Rollenangabe als 'Verantwortlicher Aktuar (Rolle der Zeichnungsordnung, Simulationsschluessel)'; dieselbe Zeile fuer das Veraenderungs-Dokument.

#### B9 — Fuer die IT-Fuehrungskraft fehlen Betriebsvoraussetzungen und Datenfluss zum Modellanbieter an einer Stelle; fuer die Fach-Fuehrungskraft ist die Bereichsseite Aktuariat ein Platzhalter (hoch, Zielgruppen-Luecke / Betrieb und Sicherheit)

Kein Dokument benennt die Fuehrungsebene als Adressat; die Bereichsseiten sind der einzige zielgruppenspezifische Einstieg. it/index.md (60 Zeilen) erklaert Determinismus, Agent/Gate/Mensch-Arbeitsteilung und verlinkt ADRs, Landkarte, Techstack — nennt aber nichts von dem, was ein IT-Leiter fuer den Betrieb wissen muss: Laufzeit (Python 3.11, gepinnte Abhaengigkeiten), Schluesselverwaltung (Datei 0600, Rotation, 'Betriebsaufgabe' laut ADR-008), Agenten-Laufzeit (Claude-/Codex-CLI), Veroeffentlichungsweg (lokaler Bau, Pages-Branch). Vor allem fehlt ueberall die Antwort auf die Sicherheitsfrage, welche Daten das Haus verlassen: README sagt nur, dass src/ keine Provider-Flaeche hat, P10 sagt, Rohquellen werden vorverdichtet 'bevor ein Modell sie sieht' — was das Modell dann sieht (Tarifwerk-Extrakte, Bestandsabzugs-Spalten?) und bei welchem Anbieter, steht nirgends. aktuariat/index.md (36 Zeilen) verlinkt Tarifplaene und zwei Bestandsberichte und endet mit 'In Vorbereitung'; Kennzahlen, Abnahmestatus oder Restrisiko fuer die Fachleitung traegt sie nicht.

**Wirkung auf das Ziel:** Die IT-Fuehrungskraft kann nach zehn Minuten die Architektur erklaeren, aber nicht sagen, was fuer einen Betrieb im Haus noetig waere und ob Vertragsdaten zu einem externen Modellanbieter fliessen — die Frage, an der jede Freigabe in einem Versicherungsunternehmen haengt. Die Fach-Fuehrungskraft findet auf 'ihrer' Seite keine der vier Antworten (was, abgenommen, gezeichnet, Restrisiko) und muss in den Migrationsbericht wechseln.

**Belege:**
    - `vorzeige-seite/it/index.md`:7 — Zwei Dinge tragen unser Geschäftsmodell: ein Rechenkern, dem man jede Zahl nachrechnen kann, und ein Migrationsvorgehen, das die Übersetzung fremder Bestände beherrschbar macht.
    - `README.md`:29 — In `src/` gibt es keine Modell-, Provider- oder Token-Fläche und keinen LLM-Pfad in einer Prüfung.
    - `docs/architektur/prinzipien.md`:75 — Kein Agent erhaelt Rohmaterial, wenn ein strukturiertes Derivat existiert; Rohquellen werden deterministisch vorverdichtet, bevor ein Modell sie sieht.
    - `docs/architektur/adr-008-signierte-p9-freigaben.md`:67 — - Schluesselbereitstellung, Backup und Zugriffskontrolle sind Betriebsaufgabe.
    - `vorzeige-seite/aktuariat/index.md`:34 — *In Vorbereitung:* Zugang, Abgang und Geschäftsvorfälle im Zeitverlauf sowie die fortgeschriebene Sicht bis zum Ablauf des Bestands.

**Widerlegungsversuch des Pruefers:** Versucht: Betriebsvoraussetzungen stehen verteilt in README (Schnellstart, Reproduzierbarkeit), ONBOARDING (Setup, Schluessel) und ADR-008 — ein IT-Leiter mit Zeit findet sie. Die Agenten-Skills (.claude/skills) beschreiben, was ein Agent liest. Die Bereichsseite Aktuariat verlinkt bewusst den Migrationsbericht als Ort der Kennzahlen. Haelt nicht: Verteilt und in Entwickler-Englisch ist fuer die Zielgruppe nicht 'vorhanden'; eine Datenfluss-Aussage zum Modellanbieter existiert in keinem gepruefen Dokument; und eine Bereichsseite, die fuer die Fachleitung gebaut ist, sollte die vier Kernantworten selbst tragen statt zu delegieren.

**Vorschlag:** Auf it/index.md einen Abschnitt 'Betrieb und Sicherheit' (Laufzeit, Schluesselverwahrung, Agenten-Laufzeit, Veroeffentlichung, drei Saetze zum Datenfluss: was der Agent sieht, was nie das Haus verlaesst) — aus pyproject/ADR-008 generiert, wo moeglich; auf aktuariat/index.md einen Kennzahlen-Block aus dem Datenmodell (Vertraege, Deckungskapital, fuenf Zeichnungen, offene Punkte) mit Verweis auf den Bericht; in werkzeuge/README die Zielgruppen der Seiten benennen (Fuehrung Fach / Fuehrung IT / Pruefer).

### Vom Pruefer korrigierte Punkte der Sammlung

- Spannung 'vorzeige-seite/migrationen/index.md handgepflegt und seit Lauf 2 nicht angefasst' ist nur fuer den gepruefen Branch richtig: Auf Branch vorzeige-url (Stempel des generierten Auftritts, db0ce47) sind die Unternehmensseiten templatisiert ('{{euro:bestand.abzuege.0.deckkap.summe}} €') und werden aus dem Datenmodell gefuellt; dev-docs/merge-plan-lauf2.md fuehrt den Strang als geplant. Als Befund bleibt nur die Inkonsistenz des vorgelegten Branches (B4, mittel statt hoch).
- Behauptung 'Deterministisch: byte-identische Artefakte' bleibt auch nach diesem Review ungeprueft — rein lesend nicht verifizierbar; die Mechanik (Neu-Rendern und Bytevergleich im Abnahmebericht-Gate) ist in ONBOARDING Abschnitt 4 beschrieben, ein zweiter Lauf wurde nicht gefahren.
- Behauptung 'Pruefumfang 1479/1517/1534 Tests' bleibt ungeprueft (Testausfuehrung untersagt); kein Artefakt im Fall belegt die Zahlen.
- Luecke 'kein aktueller fallbericht.html fuer Lauf 2' ist kein Mangel gegen Z2: werkzeuge/README fuehrt fallbericht.py als einzeln aufrufbaren Schritt, der dokumentierte Hauptweg ist auftritt.py -> vorzeigeseite.py; die Fall-Seite ersetzt den Einzelbericht. Gestrichen.
- Darstellungs-Beobachtung 'Bereichsseiten Aktuariat/IT: eingebettete Kennzahlen aus dem Repo erzeugt' trifft auf dem gepruefen Branch nur fuer it/ zu (Landkarte, Techstack eingespielt); aktuariat/index.md enthaelt keine erzeugten Kennzahlen, nur Links.
- Behauptung 'Kernaussage finale Zeichnung auf EINEM Stand bleibt gestuetzt' ist faktisch richtig (alle fuenf finalen Snapshots: commit 4b1abf0), aber unvollstaendig: alle tragen dirty='ja'; das Attribut 'unveraendert' im Abschlussbericht ist damit der eigentliche Befund (B1), nicht die fehlende Erwaehnung der Vorrunden allein.
- Eigene Gegenprobe zur Beschriftung 'A-M3: 166 Vertraege | 166 Werte' gegen 'Vollerhebung, 166 Vorfaelle' im Bericht: aktuartest-A-M3.json fuehrt 166 unterschiedliche Policen — kein Befund.
- Frage des Sammlers, ob die ONBOARDING-Versionsdrift bereits bekannt ist: nicht abschliessend pruefbar; in den gelesenen dev-docs (README, merge-plan) kein Eintrag dazu gefunden, dev-docs/offene-punkte.md wurde nicht vollstaendig gelesen.

### Grenzen der Sammlung (vom Sammler benannt)

- Die HTML-Berichte migrationsabnahme.html (2575 Zeilen), bestandsbericht-nach.html (35339 Zeilen) und bestandsbericht-vor.html (14817 Zeilen) wurden nur per Titel/H1/Grep gesichtet, nicht vollstaendig gelesen — Umfang sprengt den vertretbaren Aufwand einer Sammler-Sitzung; Struktur wurde stattdessen ueber die kompaktere, dieselben Zahlen zitierende runs/seite/migrationen/baldrian/index.md erschlossen.
- Die Reibungsprotokolle (103/300/52 Zeilen) und das Korrektur-Protokoll (737 Zeilen) wurden nur in den ersten ~20-25 Zeilen gelesen, nicht vollstaendig — als interne Prozessdokumentation ausserhalb des Kernfokus 'Ausgabeformate und Vorlagen fuer Fuehrungskraefte' eingestuft.
- docs/architektur/*.md (16 ADRs, landkarte.md, migrations-pipeline-v01.md, prinzipien.md, skill-architektur.md) wurden nicht einzeln gelesen, nur ihr Vorhandensein und ihre Titel per Verzeichnisliste erfasst und ihr Inhalt indirekt ueber README.md/ONBOARDING.md-Zitate erschlossen.
- docs/tarifplaene/klv.md, docs/tarifplaene/bu.md und docs/mathematik/grundsatzdokumentation.md wurden nicht gelesen (nur als Inventarpunkt erfasst) — sie liegen naeher an der Kernrechenmathematik als an der Migrationsfall-Demonstration selbst.
- dev-docs/ wurde nicht geoeffnet: es stand nicht in der WO-SUCHEN-Liste des Auftrags und enthaelt laut CLAUDE.local.md private Planungsnotizen des Maintainers.
- docs-local/, simulation/, regie/ wurden nicht geoeffnet — explizit TABU laut Auftrag.
- faelle/baldrian-klv-tg2015-lauf2/abgeleitet/{abox,bestand,bestand-nach,bestand-vor,diagnostics,schichten,skripte,transformation,vorverdichtung}/ wurden nur ueber find aufgelistet, ihre Dateien nicht geoeffnet — technische Zwischenartefakte ohne erkennbaren direkten Demonstrations-/Darstellungszweck fuer Z2.
- Die Auskunftsschreiben (auskunft-1..4-*.md) unter faelle/.../eingang/ wurden nicht gelesen, nur ihre Erwaehnung in Sekundaerquellen (Abschlussbericht, Dossier) verfolgt.


## Z3 — Agentisches Modell Ende-zu-Ende

### Gesamturteil des Pruefers

Das agentische Modell ist auf der Werkzeug- und Gate-Ebene bemerkenswert hart: Snapshots, Zeichnungsordnung, Pflichtbelege und die Ablehnungs-Beschraenkung des Agenten sind erzwungen, nicht erbeten, und der Fall belegt die Kette lueckenlos bis auf den Systemstand. Auf der Rollen- und Dokumentationsebene ist das Modell jedoch nicht geschlossen: Der zweite Lauf hat die Grenze 'Mensch entscheidet, Agent bereitet vor' faktisch durch 'die Rolle mit dem Schluessel entscheidet' ersetzt — im Code, per Chat-Mandat und waehrend des Laufs —, ohne dass ADR-008, Prinzipien, AGENTS.md, Skills oder der Fachbericht das nachvollzogen haetten, und ohne dass Snapshot oder Ledger ausweisen koennten, dass eine KI-Session gezeichnet hat. Die zeichnenden Operator-Rollen existieren im versionierten Repo nur als Stub, ihre Auftragsprofile und Modelle liegen im Spielleiter-Bereich. Ein Pruefer aus Aufsicht oder Revision bekommt heute einen sauberen Abnahmebericht ohne ein Wort zur KI-Beteiligung und findet kein Dokument, das ihm das KI-System als Ganzes erklaert. Prioritaet: erst den Vollzugsakteur und das Mandat in den Beleg heben (Z3-01/06), dann Architektur-Doku und Skills auf den gelebten Vertrag ziehen (Z3-02/03), dann das Pruefer-Dossier schreiben (Z3-05).

### Was traegt (Staerken)

- Zeichnungsordnung als externer Rollen-Datenvertrag (models/zeichnung.py): Rollen werden aus Schluessel-Fingerabdruecken bestimmt, nie behauptet; Ordnung darf nicht im Fall liegen; zwei Rollen mit demselben Schluessel sind ein Fehler; die Gate-Liste ist geschlossen (GUELTIGE_GATES) — das im Vorlauf gefundene A-K1-Loch ist dokumentiert und geschlossen.
- P9-Snapshots tragen die Kette tatsaechlich: Im finalen A-M4 sind A-Q1, A-M1, A-M2, A-M3, P-Q3, P-K1, P-B1, Migrationssuite und Abnahmebericht als Pflichtbelege mit Hash gebunden (verifiziert); die fuenf im Fachbericht genannten Snapshot-Hashes liegen exakt so im Fall (verifiziert); Vorgaengerketten sind je Gate vollstaendig; Schluesselpfade werden im Ledger redigiert.
- Der Agentenpfad ist strukturell auf Ablehnung begrenzt, solange kein Schluessel vorliegt (schemas.py Z.501-504, gate_entscheid Z.1129-1136); vorlaeufige Aufloesungen blocken jede Annahme, und die ersetzte vorlaeufige Entscheidung bleibt in der A-Box als entscheidungs_historie sichtbar (verifiziert an der Zins-Diskrepanz).
- Skill-Katalog mit expliziten Haerte-Grenzen je Rolle, test-getragen; die .claude/.agents-Paritaet ist byte-identisch (diff -r leer, verifiziert) und der Test test_agent_workflow_docs.py existiert.
- Hohe Selbsttransparenz der Operatoren: Die Reibungsprotokolle halten zwei korrekte Verweigerungen fest (Peer-Mandat nicht anerkannt; Regie-Seed nicht rekonstruiert), benennen eigene Bedienfehler (vergessenes Flag, 79/100-Fehlalarm) und formulieren die Zustaendigkeitsluecke (Programmleiter Nr. 7) praezise, bevor sie geschlossen wurde.
- Die offenen Luecken sind grossteils selbst erkannt und in dev-docs/offene-punkte.md ehrlich gefuehrt (Kaskaden-Rezept, Vorbehalts-Ausweis, Regie-Dokumentation, Gate fuer Codeaenderungen, Eingangs-Zeichnung der Quelle); dev-docs/agenten-rollentrennung.md benennt das Wissensraum-Problem der Rollen von innen.
- Der Fachbericht ist in Unternehmenssprache geschrieben, trennt Ergebnis, Methodik, Datenluecke und offene Punkte und traegt nachpruefbare Belege (Snapshot-Hashes, Auskunfts-Nummern, Falsifizierbarkeits-Auflage) — die Form ist die richtige, es fehlt der KI-Abschnitt.
- Prinzipien P1-P10 sind eine klare, normative Grenzbeschreibung des KI-Systems (Provenienz, Widerspruch als Objekt, Trennung probabilistisch/deterministisch, Kontext als Architekturgegenstand) und im Code weitgehend erzwungen statt erbeten.

### Lesarten (Zehn-Minuten-Test)

**Pruefer einer Aufsicht oder der internen Revision, ohne Repo-Kenntnis, mit Zugang zu docs/ und zum Fall**  
Findet den Abschlussbericht mit Gate-Tabelle, Snapshot-Hashes und Datenluecken-Behandlung und kann die fuenf Hashes im Fall wiederfinden. Versteht, dass 'der Verantwortliche Aktuar' alle Gates gezeichnet hat. Erfaehrt nicht, dass es sich um eine KI-Session im Mandat handelte, welches Modell sie fuhr, wer das Mandat erteilte und dass der Code zum Zeitpunkt der Zeichnung nicht committet war.
  
Fehlt: Beschreibung des KI-Systems fuer Pruefer (Ziele, Rollen Mensch/KI, Modelle, Eingriffspunkte, Grenzen, Nachweise); signierter Mandatsbeleg des Menschen; Vollzugsakteur (Modell/Skill/Session) im Snapshot; Rollen-Register mit Auftragsprofilen im versionierten Repo
  
Verwirrt: rolle='mensch' im Snapshot bei einer Agenten-Session; Verantwortung 'Migrationsprojekt' fuer das Controlling (9.15) ohne Zeichnungsbeleg; dirty='ja' neben 'unveraendertem Systemstand' im Bericht; Rollenname plv-va im Skill vs. plv-aktuar im Beleg; kein Ort, der Modelle, Mandate und Eingriffspunkte zusammenfuehrt
  
Passendes Format: Ein Pruefer-Dossier in Unternehmenssprache (docs/), das den Fachbericht ergaenzt, plus ein Abschnitt 'Rollen, Mandate, eingesetzte Modelle' im Fachbericht selbst.

### Befunde

| Nr | Schwere | Titel | Verifikation |
|---|---|---|---|
| Z3-01 | kritisch | KI-Sessions zeichnen als 'mensch': Snapshot, Ledger und Fachbericht koennen den Agenten-Vollzug einer menschlichen Annahme nicht ausweisen | bestaetigt, Schwere hoch |
| Z3-02 | hoch | Normative Quellen widersprechen dem Code beim Kern der Frage 'wer entscheidet': Vier-Rollen-Modell ohne ADR, P2/P4/AGENTS/Skills nicht nachgezogen | bestaetigt, Schwere hoch |
| Z3-03 | hoch | Die zeichnenden Operator-Rollen haben im versionierten Repo keine Definition, keinen Skill und keine einheitlichen Namen | nicht verifiziert |
| Z3-04 | hoch | Alle 17 Zeichnungen binden einen unreinen Arbeitsbaum (dirty=ja); der Fachbericht nennt den Stand 'unveraendert', reproduzierbar ist er aus Git nicht | nicht verifiziert |
| Z3-05 | hoch | Es gibt kein Dokument, das das KI-System fuer Aufsicht oder Revision beschreibt; der Fachbericht erwaehnt KI-Beteiligung nicht | nicht verifiziert |
| Z3-06 | mittel | Mandatsentscheide des Menschen sind der schwaechste Beleg der Kette und werden in der Auswertung nicht als Eingriffe gezaehlt | nicht verifiziert |
| Z3-07 | mittel | 23 Systemaenderungen waehrend des Laufs ohne Gate; die Zeichnungen stehen auf ungemergtem, im Regime dev x PLV-IT selbst abgenommenem Code | nicht verifiziert |
| Z3-08 | mittel | Zustaendigkeit fuer A-M4 widerspruechlich: Grundsatzdokumentation und ADR-010 nennen das Migrationsprojekt, die Zeichnungsordnung laesst nur den Aktuar zeichnen | nicht verifiziert |
| Z3-09 | niedrig | Skill-Texte hinken dem Code hinterher (Gate-Menge, Skill-Zahl, Reihenfolgezwang) — obwohl Skills 'Teil der Nachweiskette' sind | nicht verifiziert |

#### Z3-01 — KI-Sessions zeichnen als 'mensch': Snapshot, Ledger und Fachbericht koennen den Agenten-Vollzug einer menschlichen Annahme nicht ausweisen (kritisch, Zeichnungsmodell / Nachweis)

Alle 17 P9-Snapshots des Falls tragen rolle='mensch', entscheider='plv-aktuar' und eine HMAC-Freigabe. Laut Reibungsprotokoll des Aktuars und dev-docs/regie.md war 'plv-aktuar' eine Agenten-Session, die nach einer im Chat bestaetigten Mandatserweiterung selbst mit --freigabe-schluessel zeichnete. Das Rollenfeld kennt nur die Werte mensch|agent, und 'agent' darf nicht annehmen — eine zeichnende KI-Session MUSS also --rolle mensch setzen. Damit ist die Unterscheidung Mensch/Agent, die AGENTS.md, P2/P4, ADR-008 und drei Skills als tragende Grenze nennen, im Beleg nicht mehr sichtbar; sie ist durch Schluesselbesitz ersetzt. Der Fachbericht (Adressat Verantwortlicher Aktuar/Pruefer/Revision) sagt 'vom Verantwortlichen Aktuar gezeichnet' und erwaehnt das KI-System an keiner Stelle.

**Wirkung auf das Ziel:** Die Kernfrage von Z3 ('wo entscheidet ein Agent, wo nur ein Mensch darf, strukturell verhindert oder nur erbeten?') wird so beantwortet: strukturell verhindert ist nur die Annahme OHNE Schluessel. Wer einer KI-Session den Rollenschluessel gibt, macht sie im Ledger zum Menschen. Ein Pruefer, der Snapshot und Fachbericht liest, wird in die Irre gefuehrt: er sieht eine menschliche Zeichnung durch den Verantwortlichen Aktuar, tatsaechlich hat eine KI-Session im Mandat gezeichnet.

**Belege:**
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/diagnostics/gate_entscheid_am4.gate.json` — command_line: [... '--entscheider', 'plv-aktuar', '--rolle', 'mensch', ... '--zeichnungsordnung', 'faelle/zeichnungsordnung.json', '--freigabe-schluessel', '<extern-redigiert>']
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-aktuar.md`:54 — Update: Maintainer hat die Mandatserweiterung direkt in dieser Sitzung bestaetigt (Vollzug der selbst getroffenen Diskrepanz-Entscheide via `ontologie.entscheide --zeichnungsordnung --freigabe-schluessel --entscheider "plv-aktuar"`
    - `dev-docs/regie.md`:27 — `plv-aktuar` (unabhaengige zeichnende Fachinstanz: A-Q1, A-M1..M4, eigener Schluessel — wer den Prozess faehrt, nimmt ihn nicht selbst fachlich ab)
    - `src/rechner_pipeline/models/schemas.py`:501 — if data.get("rolle") not in ("mensch", "agent"): errors.append("rolle must be 'mensch' or 'agent'")
    - `docs/architektur/adr-008-signierte-p9-freigaben.md`:51 — Agenten erhalten keinen Zugriff auf dieses Schluesselmaterial; der Mensch fuehrt den Annahmeaufruf in seiner Autoritaetsumgebung aus.
    - `.claude/skills/pruefe-migrationscontrolling/SKILL.md`:80 — Du hast sie nicht und bekommst sie nicht — ein Agent kann an einem menschlichen Gate ausschließlich ablehnen.
    - `docs/faelle/baldrian-lauf2.md`:11 — Alle fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem einzigen, unveraenderten Systemstand gezeichnet

**Widerlegungsversuch des Pruefers:** ADR-008 sagt in den Konsequenzen ausdruecklich: 'HMAC weist die Autorisierung der verwalteten Schluesselrolle nach, nicht die persoenliche Identitaet einer natuerlichen Person' — eine dokumentierte Grenze. dev-docs/regie.md beschreibt die Rollenbesetzung offen als Agenten-Rollen mit Schluesseln, und die private Auftraggeber-Anweisung erlaubt 'Auftrag fuer beides'. Das entkraeftet den Befund nicht: (a) die normativen Texte (ADR-008 Z.51, P2/P4, AGENTS.md Z.10-13, drei Skills) sagen das Gegenteil; (b) regie.md ist ein Stub ('Dokumentation ausstehend'), ohne Verweis aus AGENTS/ONBOARDING; (c) der Fachbericht, der einzige an Pruefer adressierte Text, nennt weder Regie noch KI; (d) im Beleg selbst (Snapshot/Ledger) ist die Information strukturell nicht darstellbar. Die Grenze ist also dokumentiert, aber am falschen Ort und gegen den Wortlaut der Architektur.

**Vorschlag:** Snapshot-Schema um den Vollzugsakteur erweitern (z. B. 'vollzug': {'art': 'mensch'|'agent-im-mandat', 'akteur': '<modell>/<skill>@<sha>', 'mandat': '<sha des Mandats-Snapshots>'}); die Mandatserteilung des Menschen als eigenen signierten Akt der Eskalationsrolle 'mensch' ('*') festhalten (Reichweite, Gates, Dauer), auf den jede Agenten-Zeichnung verweist; gate_entscheid und entscheide verweigern --rolle mensch ohne diesen Nachweis, wenn die Rolle laut Ordnung eine Agenten-Rolle ist. Fachbericht um einen Abschnitt 'Zeichnende Rollen und Mandate' ergaenzen. ADR-008 Z.51 und die drei Skills auf den gelebten Vertrag umschreiben (siehe Z3-02).

**Verdikt des Skeptikers:** nicht widerlegt, korrigierte Schwere hoch.  
Kern des Befunds bestaetigt, Rahmen und Schwere korrigiert.

Bestaetigt am Code und an den Belegen: (1) Alle 16 (nicht 17) P9-Snapshots unter FALL/entscheide/ tragen rolle='mensch', entscheider='plv-aktuar', zeichnung.rolle='plv-aktuar' und eine HMAC-Freigabe; das Ledger gate_entscheid_am4.gate.json fuehrt in summary.command_line '--rolle mensch ... --zeichnungsordnung ... --freigabe-schluessel <redigiert>'. (2) gate_entscheid.py laesst fuer --rolle nur choices mensch|agent zu und verweigert 'agent'+'angenommen' (Z.1047-1050, 1132-1135); schemas.py 501-503 dito. Eine zeichnende Session MUSS also --rolle mensch behaupten; das Feld wird nirgends aus dem Schluessel abgeleitet (anders als in ontologie.entscheide, wo --rolle gegen die Schluesselrolle geprueft wird, Z.144-146). (3) Weder Zeichnungsordnung (faelle/zeichnungsordnung.json: nur schluessel_sha256 + gates je Rolle) noch Snapshot-Schema (zeichnung = {rolle, ordnung_sha256}, schemas.py 466-479) haben ein Feld fuer Besetzungsart oder Mandat; das Reibungsprotokoll, das den Agenten-Vollzug offenlegt, ist vom A-M4-Snapshot NICHT gepinnt (0 Treffer in artefakt_hashes). (4) Der Fachbericht docs/faelle/baldrian-lauf2.md enthaelt keinen Treffer fuer KI/Agent/Session/Sitzung/LLM; er sagt 'vom Verantwortlichen Aktuar ... gezeichnet' (Z.11-13) und 'Rolle Verantwortlicher Aktuar ueber die Zeichnungsordnung' (Z.23-24). (5) Die normativen Texte sagen das Gegenteil der gelebten Praxis: ADR-008 Z.50 ('Agenten erhalten keinen Zugriff auf dieses Schluesselmaterial'), prinzipien.md P2 Z.17-19 ('benanntem menschlichem Verantwortlichen; Agenten duerfen ausschliesslich VORLAEUFIG aufloesen'), AGENTS.md Z.10-13 ('humans decide ... every acceptance gate'), drei Skills ('Du hast sie nicht und bekommst sie nicht'). Der Skill migrationsfall-durchfuehren ist in sich widerspruechlich: plv-va 'mit eigenem menschlichem Schluessel' (Z.355) und zugleich 'Der Mensch steigt nur nach Abbruchkriterium ein' (Z.363-364). Kein ADR behandelt die Zeichnungsordnung oder das Vier-Rollen-Modell (grep docs/architektur: 0 Treffer fuer Zeichnungsordnung/Vier-Rollen/Mandat).

Widerlegungsversuche, die NICHT tragen: (a) 'Bewusst dokumentierte Grenze' — ADR-008 Z.76 (HMAC weist Schluesselrolle nach, nicht Identitaet) und Commit 404974d ('Genau die menschliche Zwischenschicht, die die Regie abschaffen soll, Maintainer-Go 2026-09-01') belegen zwar, dass die Agenten-Besetzung eine bewusste Regie-Entscheidung ist — aber sie ist nur in Commit-Text, dev-docs/regie.md (Stub) und dev-docs/lauf2-auswertung.md festgehalten, nicht in ADR, Prinzipien, AGENTS.md oder Skills, die weiterhin das Mensch-only-Modell behaupten. Eine Grenze, die dem Wortlaut der Architektur widerspricht, ist keine dokumentierte Grenze, sondern eine undokumentierte Umwidmung. (b) 'Der Snapshot unterscheidet doch': Richtig ist, dass zeichnung.rolle='plv-aktuar' von der Eskalationsrolle 'mensch' ("*") der Ordnung unterscheidbar ist — der Snapshot sagt also, WELCHE Rolle zeichnete. Er sagt aber nicht, DASS die Rolle von einer KI-Session im Mandat besetzt war; die Ordnung kennt keine Besetzungsart. Das entschaerft die Formulierung des Befunds ('Unterscheidung nicht mehr sichtbar' -> 'Besetzung der Rolle nicht ausweisbar'), hebt ihn aber nicht auf. (c) 'Das Rollenfeld ist ein Autoritaetsmarker, kein Akteursmarker': Die Hilfe (gate_entscheid.py Z.1048: 'Agenten duerfen NUR ablehnen (dokumentierter Zwischenstand)') legt diese Lesart nahe; dann waere rolle='mensch' fuer eine mandatierte Session konsistent. Diese Lesart steht aber nirgends normativ, und ADR-008/Skills/P2 lesen 'mensch' ausdruecklich als natuerliche Person. (d) 'Unternehmenssprache': Der Fachbericht ist als VU-Dokument gewollt fiktionsintern (dev-docs/README.md); in der Fiktion IST der Zeichnende der Verantwortliche Aktuar. Fuer die Z3-Frage ('wo entscheidet ein Agent, wo nur ein Mensch darf') ist genau diese Fiktion der Punkt: Sie verdeckt im einzigen an Pruefer adressierten Text den Agenten-Vollzug.

Schwere: nicht 'kritisch', sondern 'hoch'. Gruende fuer die Absenkung: Die Agenten-Besetzung ist im Repo an mehreren Stellen offen dokumentiert (dev-docs/regie.md Z.27, lauf2-auswertung.md Z.45 'KI und Betrieb', merge-plan-lauf2.md Z.161 'Vier-Rollen-Regie', Commit 404974d) und im Fall selbst (reibungsprotokoll-aktuar.md Z.54); es gibt keine Verschleierung, und Rolle plus Schluesselbindung sind korrekt und mitsigniert festgehalten. Die Wirkung 'Pruefer wird in die Irre gefuehrt' trifft nur, wenn der Pruefer ausschliesslich Snapshot und Fachbericht liest — das ist fuer Revision realistisch, aber das Repo als Ganzes fuehrt nicht irre. Gruende gegen 'mittel': Die Mensch/Agent-Grenze wird von AGENTS.md, P2/P4, ADR-008 und drei Skills als tragende Grenze benannt und ist im Beleg durch Schluesselbesitz ersetzt, ohne dass ein einziges normatives Dokument das nachgezogen haette; das ist ein Bruch zwischen behaupteter und gebauter Architektur genau an der Z3-Kernfrage.

Praezisierung: Z3-01 (praezisiert): Snapshot, Ledger und Fachbericht koennen die BESETZUNG der zeichnenden Rolle (natuerliche Person vs. KI-Session im erteilten Mandat) nicht ausweisen. Es sind 16 Snapshots (5 A-M1, 4 A-M2, 3 A-M3, 1 A-M4, 3 A-Q1), alle rolle='mensch', entscheider='plv-aktuar', zeichnung.rolle='plv-aktuar'. Der Snapshot unterscheidet die Rolle 'plv-aktuar' korrekt von der Eskalationsrolle 'mensch' der Ordnung — was fehlt, ist nicht 'wer' (Rolle), sondern 'wie besetzt' und 'aus welchem Mandat'. Das Feld --rolle mensch|agent ist per Code ein Autoritaetsmarker (agent = darf nur ablehnen), wird aber in ADR-008 Z.50, prinzipien.md P2 Z.17-19, AGENTS.md Z.10-13 und drei Skills als Akteursmarker (natuerliche Person) gelesen; der Skill migrationsfall-durchfuehren widerspricht sich selbst (Z.355 vs. Z.363-364). Die Agenten-Besetzung ist eine bewusste Regie-Entscheidung (Commit 404974d, dev-docs/regie.md, lauf2-auswertung.md), aber ohne ADR und gegen den Wortlaut der Architektur. Das Reibungsprotokoll des Aktuars, das den Vollzug offenlegt, liegt zwar im Fall, ist aber vom A-M4-Snapshot nicht gepinnt. Der Fachbericht nennt Rolle und Zeichnungsordnung (Z.23-24), aber keine KI-Beteiligung. Der Vorschlag des Pruefers (Vollzugs-/Mandatsfeld im Snapshot, signierter Mandatsakt der Eskalationsrolle, Fachbericht-Abschnitt 'Zeichnende Rollen und Mandate', Nachzug von ADR-008/P2/Skills) bleibt sachgerecht; mindestens zu leisten ist der ADR-Nachzug, sonst beschreibt die Architektur ein anderes System als das gebaute.

Belege des Skeptikers:
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/gates/gate_entscheid.py`:1047 — "--rolle", default=None, choices=["mensch", "agent"],
help="Wer entscheidet. Agenten duerfen NUR ablehnen "
"(dokumentierter Zwischenstand) — die Annahme eines "
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/gates/gate_entscheid.py`:1132 — if args.rolle == "agent" and args.entscheid == "angenommen":
    return _usage(
        "Rolle 'agent' darf nicht annehmen — die Annahme eines "
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/models/schemas.py`:470 — z = data.get("zeichnung")
if z is not None and not (
    isinstance(z, dict) and set(z) == {"rolle", "ordnung_sha256"}
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/models/zeichnung.py`:13 — Rollen werden aus dem SCHLUESSEL bestimmt, nie behauptet: Wer eine
Datei besitzt, deren SHA-256 die Ordnung einer Rolle zuordnet, handelt
als diese Rolle.
    - `/home/bartl/git/rechner-pipeline/src/rechner_pipeline/ontologie/entscheide.py`:144 — if args.rolle and args.rolle != rolle:
    print(f"entscheide: --rolle {args.rolle!r} widerspricht der "
          f"aus dem Schluessel bestimmten Rolle {rolle!r}",
    - `/home/bartl/git/rechner-pipeline/faelle/zeichnungsordnung.json`:3 — "rollen": { "plv-aktuar": { "schluessel_sha256": "1628...", "gates": ["A-Q1","A-M1","A-M2","A-M3","A-M4"] }, ... "mensch": { ..., "gates": ["*"] } }
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/entscheide/A-M4-32682e958c7811b0b5fc89c3e7eaf897243b2d39151facf5ba60c99397231a6e.json` — "entscheider": "plv-aktuar", "rolle": "mensch", "zeichnung": {"ordnung_sha256": "09c7b9e8...", "rolle": "plv-aktuar"} — artefakt_hashes enthaelt kein reibungsprotokoll
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/diagnostics/gate_entscheid_am4.gate.json` — summary.command_line: ["--fall", ..., "--gate", "A-M4", "--entscheid", "angenommen", "--entscheider", "plv-aktuar", "--rolle", "mensch", ...]
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-aktuar.md`:54 — Update: Maintainer hat die Mandatserweiterung direkt in dieser Sitzung
bestaetigt (Vollzug der selbst getroffenen Diskrepanz-Entscheide via
`ontologie.entscheide --zeichnungsordnung --freigabe-schluessel
    - `/home/bartl/git/rechner-pipeline/docs/architektur/adr-008-signierte-p9-freigaben.md`:50 — Agenten erhalten keinen Zugriff auf dieses Schluesselmaterial; der Mensch
fuehrt den Annahmeaufruf in seiner Autoritaetsumgebung aus.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/adr-008-signierte-p9-freigaben.md`:76 — HMAC weist die Autorisierung der verwalteten Schluesselrolle nach, nicht
die persoenliche Identitaet einer natuerlichen Person.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/prinzipien.md`:17 — Aufloesung ist ein expliziter
Vorgang mit benanntem menschlichem Verantwortlichen; Agenten duerfen
ausschliesslich VORLAEUFIG aufloesen (blockt jede Annahme).
    - `/home/bartl/git/rechner-pipeline/AGENTS.md`:10 — humans decide contradictions between sources and every acceptance
gate (A-Q1/A-M1/A-M4/A-K1). No LLM path inside any gate.
    - `/home/bartl/git/rechner-pipeline/.claude/skills/migrationsfall-durchfuehren/SKILL.md`:354 — `plv-va` (zeichnet A-Q1 und A-M1..M4 mit
eigenem menschlichem Schluessel), `mensch` (Eskalation, `"*"`)
    - `/home/bartl/git/rechner-pipeline/.claude/skills/migrationsfall-durchfuehren/SKILL.md`:366 — Als Agent darfst du AUSSCHLIESSLICH
ablehnen (--rolle agent, dokumentierter Zwischenstand).
    - `/home/bartl/git/rechner-pipeline/.claude/skills/pruefe-migrationscontrolling/SKILL.md`:80 — Du hast sie nicht und bekommst
sie nicht — ein Agent kann an einem menschlichen Gate ausschließlich
ablehnen.
    - `/home/bartl/git/rechner-pipeline/dev-docs/regie.md`:27 — `plv-aktuar` (unabhaengige zeichnende
Fachinstanz: A-Q1, A-M1..M4, eigener Schluessel — wer den Prozess
faehrt, nimmt ihn nicht selbst fachlich ab)
    - `/home/bartl/git/rechner-pipeline/dev-docs/lauf2-auswertung.md`:45 — ## 2 Vorher/Nachher — KI und Betrieb
    - `/home/bartl/git/rechner-pipeline/dev-docs/merge-plan-lauf2.md`:160 — Fall-Lauf 2 auf fallbericht fahren (Owner: Lauf-Sessions des
Maintainers, Vier-Rollen-Regie; dev-session als Systembetreuung).
    - `git log -1 404974d (feat(ontologie,models)!: Diskrepanz-Entscheide vollzieht die zeichnende Rolle)` — beide Operatoren verweigerten korrekt, der Lauf
haengte am Maintainer. Genau die menschliche Zwischenschicht, die die
Regie abschaffen soll (Maintainer-Go 2026-09-01, Korrektur Nr. 4).
    - `/home/bartl/git/rechner-pipeline/docs/faelle/baldrian-lauf2.md`:11 — Alle
fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem
einzigen, unveraenderten Systemstand gezeichnet
    - `/home/bartl/git/rechner-pipeline/docs/faelle/baldrian-lauf2.md`:23 — Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar
ueber die Zeichnungsordnung) — Datei ohne Treffer fuer KI/Agent/Session/Sitzung/LLM
    - `/home/bartl/git/rechner-pipeline/docs/architektur/` — grep -rn 'Vier-Rollen|Zeichnungsordnung|Mandat' docs/architektur/ — 0 Treffer; kein ADR zur Zeichnungsordnung oder zum Vier-Rollen-Modell
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/entscheide/` — ls | wc -l = 16 (5 A-M1, 4 A-M2, 3 A-M3, 1 A-M4, 3 A-Q1) — nicht 17; alle rolle=mensch, entscheider=plv-aktuar, mit freigabe

#### Z3-02 — Normative Quellen widersprechen dem Code beim Kern der Frage 'wer entscheidet': Vier-Rollen-Modell ohne ADR, P2/P4/AGENTS/Skills nicht nachgezogen (hoch, Architektur-Doku / Drift)

Der Code sagt seit dem 2026-09-01 (Commit 404974d, waehrend des Laufs, 'Maintainer-Go' im Korrektur-Protokoll): 'entscheidet dort die fachlich zeichnende Rolle, nicht mehr nur der Mensch'. Die Architektur-Quellen sagen weiter 'Mensch': Prinzip P2 ('Aufloesung ... mit benanntem menschlichem Verantwortlichen; Agenten duerfen ausschliesslich VORLAEUFIG aufloesen'), P4, AGENTS.md ('humans decide contradictions'), Pipeline-Dokument Abschnitt 4 ('die Aufloesung ist ein Mensch'), Skill bereite-fachkonflikt-auf ('Die Entscheidung faellt ein benannter Mensch'), ADR-008 Z.51. Ein ADR zum Vier-Rollen-Modell/zur Zeichnungsordnung existiert nicht; die Entscheidung steht als 'Regie-Entscheid ERLEDIGT' in dev-docs/offene-punkte.md.

**Wirkung auf das Ziel:** Das Modell ist nicht geschlossen: Wer Rollen und Zeichnungsbefugnis aus der Architektur-Doku ableitet, kommt zu einem anderen Ergebnis als der Code und der Lauf. Die Skills, die laut skill-architektur 'Teil der Nachweiskette' sind und P1-P10 nur ZITIEREN sollen, zitieren eine Fassung, die nicht mehr gilt. Ein Pruefer kann nicht feststellen, welche Regel verbindlich ist.

**Belege:**
    - `src/rechner_pipeline/ontologie/entscheide.py`:5 — WER entscheiden darf (Vier-Rollen-Modell, 2026-09-01): Mit ``--zeichnungsordnung`` und ``--freigabe-schluessel`` wird die Rolle
    - `src/rechner_pipeline/models/zeichnung.py`:7 — seit dem Vier-Rollen-Modell des zweiten Laufs entscheidet dort die fachlich zeichnende Rolle, nicht mehr nur "der Mensch"
    - `docs/architektur/prinzipien.md`:18 — Aufloesung ist ein expliziter Vorgang mit benanntem menschlichem Verantwortlichen; Agenten duerfen ausschliesslich VORLAEUFIG aufloesen (blockt jede Annahme).
    - `AGENTS.md`:12 — humans decide contradictions between sources and every acceptance gate (A-Q1/A-M1/A-M4/A-K1). No LLM path inside any gate.
    - `.claude/skills/bereite-fachkonflikt-auf/SKILL.md`:21 — Die Entscheidung faellt ein benannter Mensch mit `python -m rechner_pipeline.ontologie.entscheide`
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/korrektur-protokoll.md`:141 — Rolle wird jetzt aus dem Schluessel-Fingerprint der Zeichnungsordnung abgeleitet, nicht mehr per `--rolle`-Flag behauptet
    - `dev-docs/offene-punkte.md`:53 — ~~Rollenzuordnung Gate -> Zeichnungsberechtigung~~ ERLEDIGT 2026-08-31 | Regie-Entscheid 2026-08-31 | gate_entscheid nimmt --zeichnungsordnung

**Widerlegungsversuch des Pruefers:** Man koennte lesen, die Zeichnungsordnung praezisiere nur, WELCHER Mensch zeichnet (Rolle statt Person), und ADR-008 bleibe unveraendert gueltig. Das traegt nicht: (a) zeichnung.py und entscheide.py sagen ausdruecklich 'nicht mehr nur der Mensch'; (b) im Lauf haben Agenten-Sessions gezeichnet (Z3-01); (c) skill-architektur Pflege-Regel 4 verlangt, dass Prinzipien in Skills zitiert werden und die Quelle das Architektur-Dokument ist — die Quelle P2 wurde nicht geaendert. Der Skill dokumentiere-system verlangt ADR-Format fuer Entscheidungen; hier fehlt es.

**Vorschlag:** ADR-017 'Zeichnungsordnung und Vier-Rollen-Modell: Rollen aus Schluesseln' mit Nachtraegen an ADR-008 (Z.51), P2/P4 in prinzipien.md, AGENTS.md Working Agreements, Pipeline-Dokument Abschnitt 4 und den drei Abnahme-Skills. Den Test test_rollen_skills_tragen_ihre_haerte_grenzen auf den neuen Wortlaut umstellen, damit die alte Formulierung nicht test-getragen konserviert wird.

**Verdikt des Skeptikers:** nicht widerlegt, korrigierte Schwere hoch.  
Alle sieben Belege existieren wortgetreu an den angegebenen Stellen (entscheide.py Z.5-7, zeichnung.py Z.7-9, prinzipien.md P2 Z.17-19, AGENTS.md Z.11-12, bereite-fachkonflikt-auf Z.21, korrektur-protokoll.md Z.140-141, offene-punkte.md). Der Widerlegungsversuch traegt nicht, und zwar aus drei Gruenden, die ueber den Befund hinausgehen:

1. Die Architektur-Doku kennt die Zeichnungsordnung schlicht nicht: `grep -ri zeichnungsordnung docs/architektur/ ONBOARDING.md` liefert null Treffer (weder ADR, noch Prinzipien, noch Pipeline-Dokument, noch skill-architektur). Commit 404974d hat unter docs/architektur/ ausschliesslich die generierte landkarte.md (Kantenzahlen) angefasst. Die Zeichnungsordnung liegt in src/rechner_pipeline/models/zeichnung.py und ist damit System, nicht Simulationswerkzeug — die in offene-punkte.md dokumentierte Ausnahme 'Tooling OHNE ADR (ADRs gelten dem System)' greift nicht.

2. Die Lesart 'Zeichnungsordnung praezisiert nur, WELCHER Mensch zeichnet' ist am Fall falsifizierbar: Der plv-aktuar des Laufs war eine Agenten-Session (reibungsprotokoll-aktuar.md Z.8: 'legt der PLV-Aktuar-Session ... vor', Z.22-23: 'Ob eine Agentensitzung im Aktuar-Mandat ueberhaupt --rolle mensch ziehen darf'). Nach 404974d hat genau diese Session endgueltig (vorlaeufig=false) entschieden: abox.json traegt Entscheide mit entscheider 'plv-aktuar', vorlaeufig false, zeichnung.rolle 'plv-aktuar'. Das steht in direktem Widerspruch zu P2 ('Agenten duerfen ausschliesslich VORLAEUFIG aufloesen') und P4 ('Sie ... entscheiden nicht ueber ... Konflikte'). Zusaetzlich tragen alle 16 P9-Snapshots unter faelle/.../entscheide/ das Feld rolle='mensch' bei entscheider='plv-aktuar' — der Snapshot behauptet also die Rolle, die P2/ADR-008 meinen, waehrend die Zeichnung eine Agenten-Rolle bindet.

3. Die Drift reicht weiter als benannt: README.md Z.431-434 sagt noch 'entscheide nimmt ausschließlich --rolle mensch — endgültige Diskrepanz-Auflösungen sind Menschen vorbehalten'; migrationsfall-durchfuehren Z.353-355 beschreibt die plv-va-Rolle 'mit eigenem menschlichem Schluessel' und Z.363-364 'der Mensch fuehrt den Annahmeaufruf aus'; skill-architektur.md Z.63-65 nennt entscheide/gate_entscheid 'Werkzeuge fuer Menschen'. Das einzige Dokument, das das Vier-Rollen-Modell beschreibt, ist dev-docs/regie.md — ausdruecklich ein 'Stub — Konzept benannt, Dokumentation ausstehend'.

Bewusst dokumentierte Grenze? Nur teilweise: regie.md und offene-punkte.md ('Regie dokumentieren') halten fest, dass das Regie-Kapitel und die Verweise aus AGENTS/ONBOARDING ausstehen. Das deckt aber die Regie-Beschreibung, nicht die Revision der normativen Aussagen P2/P4/ADR-008 — die Prinzipien selbst erklaeren Aenderungen zum 'A-K1-artigen Vorgang mit dem Maintainer' (prinzipien.md Z.5-6), der nirgends belegt ist. Ein Pruefer, der P2 liest, muss die endgueltigen Agenten-Entscheide des Laufs als Regelverstoss werten; wer den Code liest, haelt sie fuer regelkonform. Der Mechanismus selbst (Rolle aus Schluessel, Ordnung ausserhalb des Falls, keine geteilten Schluessel) ist getestet (tests/test_zeichnungsordnung.py) und im Fallbericht offengelegt (docs/faelle/baldrian-lauf2.md Z.23-24) — deshalb kein 'kritisch', aber 'hoch' bleibt: Es geht um die Kernfrage der Governance, und die normative Quelle ist gegenlaeufig zum Lauf.

Praezisierung: Z3-02 bestaetigt und erweitert: (a) Kein Architektur-Dokument (docs/architektur/, ONBOARDING.md) erwaehnt die Zeichnungsordnung oder das Vier-Rollen-Modell; die einzige Beschreibung ist der Stub dev-docs/regie.md. (b) Der Widerspruch ist nicht nur Wortlaut, sondern am Fall materiell: Eine Agenten-Session (plv-aktuar) hat nach 404974d Diskrepanzen endgueltig (vorlaeufig=false) aufgeloest und alle fuenf Gates angenommen — P2/P4 verbieten genau das. (c) Die P9-Snapshots tragen rolle='mensch' neben zeichnung.rolle='plv-aktuar' und entscheider='plv-aktuar': Das Feld 'rolle', das ADR-008 als Pflichtfeld des signierten Inhalts nennt, behauptet eine Kategorie, die der Zeichner nicht ist. (d) Weitere gegenlaeufige Stellen: README.md Z.431-434 ('ausschließlich --rolle mensch'), migrationsfall-durchfuehren Z.353-364 ('eigenem menschlichem Schluessel', 'der Mensch fuehrt den Annahmeaufruf aus'), skill-architektur.md Z.63-65 ('Werkzeuge fuer Menschen'). (e) prinzipien.md verlangt fuer Prinzipien-Aenderungen einen 'A-K1-artigen Vorgang mit dem Maintainer' — dokumentiert ist nur ein 'Maintainer-Go' im Korrektur-Protokoll des Falls. Vorschlag des Pruefers (ADR + Nachtraege) ist um README-Abschnitt '--rolle' und die Semantik des Snapshot-Felds 'rolle' (mensch vs. agent vs. zeichnende Rolle) zu ergaenzen; die Regie-Doku-Punkte in offene-punkte.md/regie.md decken die Norm-Revision nicht ab.

Belege des Skeptikers:
    - `/home/bartl/git/rechner-pipeline/docs/architektur/prinzipien.md`:5 — Nicht verhandelbar; Aenderungen sind ein A-K1-artiger Vorgang mit dem Maintainer.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/prinzipien.md`:25 — LLM-Agenten extrahieren, schlagen vor, klassifizieren. Sie rechnen nicht, vergleichen nicht, entscheiden nicht ueber Vollstaendigkeit oder Konflikte.
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-aktuar.md`:22 — Ob eine Agentensitzung im Aktuar-Mandat ueberhaupt "--rolle mensch" ziehen darf, ist damit nicht durch die eigene Auftragsbeschreibung gedeckt
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/abox.json` — "entscheider": "plv-aktuar", ... "vorlaeufig": false, "zeichnung": {"ordnung_sha256": "09c7b9e8...", "rolle": "plv-aktuar"}
    - `/home/bartl/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2/entscheide/A-Q1-fd7932601b001b9a89955b32601137b68610d2a29ca9a297a85e2dc0e6b1c0b3.json` — gate A-Q1, entscheider plv-aktuar, rolle mensch, zeichnung.rolle plv-aktuar (gleiches Muster in allen 16 Snapshots des Falls)
    - `/home/bartl/git/rechner-pipeline/README.md`:433 — `entscheide` nimmt ausschließlich `--rolle mensch` — endgültige Diskrepanz-Auflösungen sind Menschen vorbehalten.
    - `/home/bartl/git/rechner-pipeline/.claude/skills/migrationsfall-durchfuehren/SKILL.md`:354 — `plv-va` (zeichnet A-Q1 und A-M1..M4 mit eigenem menschlichem Schluessel), `mensch` (Eskalation, `"*"`)
    - `/home/bartl/git/rechner-pipeline/docs/architektur/skill-architektur.md`:63 — Menschliche Gates (A-Q1/A-M1/A-M4/A-K1, P9-Snapshots) sind KEINE Skills — sie sind Werkzeuge fuer Menschen (`ontologie.entscheide`, `gates.gate_entscheid`).
    - `/home/bartl/git/rechner-pipeline/docs/architektur/migrations-pipeline-v01.md`:106 — Ein Widerspruch zwischen Quellen entsteht im Merge-Code, nie im Agenten-Urteil; die Aufloesung ist ein Mensch.
    - `/home/bartl/git/rechner-pipeline/docs/architektur/adr-008-signierte-p9-freigaben.md`:50 — Agenten erhalten keinen Zugriff auf dieses Schluesselmaterial; der Mensch fuehrt den Annahmeaufruf in seiner Autoritaetsumgebung aus.
    - `/home/bartl/git/rechner-pipeline/dev-docs/regie.md`:1 — # Regie (Stub — Konzept benannt, Dokumentation ausstehend)
    - `/home/bartl/git/rechner-pipeline/docs/architektur/landkarte.md` — git show --stat 404974d: unter docs/architektur/ nur landkarte.md geaendert (+ontologie -- 1 --> models); kein ADR, keine Prinzipien
    - `/home/bartl/git/rechner-pipeline/docs/architektur/` — grep -ri 'zeichnungsordnung|vier-rollen' docs/architektur/ ONBOARDING.md: keine Treffer; ADR-Liste endet bei adr-016-pdf-vorverdichtung.md
    - `/home/bartl/git/rechner-pipeline/tests/test_zeichnungsordnung.py`:1 — Zeichnungsordnung: welche Rolle darf welches Gate zeichnen.

#### Z3-03 — Die zeichnenden Operator-Rollen haben im versionierten Repo keine Definition, keinen Skill und keine einheitlichen Namen (hoch, Rollenmodell / Geschlossenheit)

Die Rollen, die den Lauf tatsaechlich trugen (programmleiter/plv-it, plv-aktuar, quelle-experte, mensch, dev-session), sind nur in dev-docs/regie.md (Stub) und in den gitignorierten Auftragsprofilen unter regie/ definiert. Der Skill-Katalog kennt elf Taetigkeits-Skills, aber keine Zuordnung Rolle -> Skill -> Werkzeug -> Gate. plv-aktuar hat Zeichnungsbefugnis (Ordnung: A-Q1, A-M1..M4) und Werkzeug (gate_entscheid), aber keinen Skill; die Skills aktuartest-durchfuehren und pruefe-migrationscontrolling richten sich an den Vorbereiter, nicht an die zeichnende Rolle. Die Namen driften: der Skill nennt die zeichnende Rolle 'plv-va' und spricht von 'Zwei-Operatoren-Regie'; Zeichnungsordnung, Snapshots, regie.md und Code sagen 'plv-aktuar' und 'Vier-Rollen-Regie'. Die im Lauf entscheidenden Schreibgrenzen der Rollen (Reibungsprotokoll Aktuar: 'Das Auftragsprofil dieser Session begrenzt die Schreibwirkung explizit auf gate_entscheid') sind nirgends versioniert.

**Wirkung auf das Ziel:** Die Z3-Frage 'hat jede Rolle Definition, Skill, Werkzeug und Zeichnungsbefugnis, und stimmen die vier ueberein?' ist mit Nein zu beantworten. Eine Ende-zu-Ende-Beschreibung von Auftrag bis Zeichnung kann aus dem Repo nicht rekonstruiert werden, weil die Auftragsseite (Profile, Mandate, Modelle) im Spielleiter-Bereich liegt.

**Belege:**
    - `dev-docs/regie.md`:1 — # Regie (Stub — Konzept benannt, Dokumentation ausstehend)
    - `dev-docs/regie.md`:17 — `regie/` traegt die LAUF-Spielleitung — Drehbuecher und die Auftraege der Operator-Sessions (uebergeben wird nur ihr INHALT als Start-Prompt
    - `.claude/skills/migrationsfall-durchfuehren/SKILL.md`:352 — **Zeichnungsordnung (Zwei-Operatoren-Regie, Beschluss 2026-08-31).** Faehrt der Fall mit getrennten Rollen — `quelle-experte` (zeichnet nur Lieferungen, keine Gates), `plv-va` (zeichnet A-Q1 und A-M1..M4
    - `faelle/zeichnungsordnung.json` — rollen: plv-aktuar [A-Q1, A-M1, A-M2, A-M3, A-M4]; plv-it [A-K1]; mensch ['*']
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-aktuar.md`:14 — Das Auftragsprofil dieser Session begrenzt die Schreibwirkung explizit auf `gate_entscheid`-Aufrufe und dieses Protokoll
    - `docs/architektur/skill-architektur.md`:75 — Menschliche Gates (A-Q1/A-M1/A-M4/A-K1, P9-Snapshots) sind KEINE Skills — sie sind Werkzeuge fuer Menschen

**Widerlegungsversuch des Pruefers:** regie.md dokumentiert die Rollenbesetzung in einem Absatz, ist versioniert, und offene-punkte.md fuehrt 'Regie dokumentieren' als offenen Punkt — die Luecke ist also bekannt. Die Aufloesungen der Showcase-Faelle muessen tatsaechlich geheim bleiben, was den Spielleiter-Bereich rechtfertigt. Aber: Rollen-Definitionen und Schreibgrenzen enthalten keine Aufloesungen und koennten versioniert sein; der Verweis aus AGENTS/ONBOARDING fehlt; die Namensdrift (plv-va/plv-aktuar, Zwei-/Vier-Rollen) ist ein eigener, nicht bekannter Mangel.

**Vorschlag:** Ein versioniertes Rollen-Register in docs/architektur (Rolle -> Auftragsprofil ohne Aufloesungen -> Skills -> zulaessige Werkzeuge/Schreibwirkung -> Gates in der Zeichnungsordnung -> Abbruchkriterien), die Zeichnungsordnung als Vorlage ins Repo, Namen vereinheitlichen (plv-aktuar), ein Test, der die Rollen einer Zeichnungsordnung gegen das Register prueft. regie.md aus AGENTS.md und ONBOARDING verlinken.

#### Z3-04 — Alle 17 Zeichnungen binden einen unreinen Arbeitsbaum (dirty=ja); der Fachbericht nennt den Stand 'unveraendert', reproduzierbar ist er aus Git nicht (hoch, Nachweis / Reproduzierbarkeit)

Jeder P9-Snapshot des Falls traegt system.dirty='ja' — nicht nur der A-M4 wie vom Sammler notiert. quellcode_sha256 pinnt die tatsaechlichen Paket-Bytes, aber kein Artefakt archiviert den Arbeitsbaum, der diesen Hash erzeugt; der genannte Commit 4b1abf0 belegt nicht den Code, auf dem gezeichnet wurde. Der Gate-Docstring verspricht 'der Lauf ist daraus reproduzierbar', der Fachbericht 'auf einem einzigen, unveraenderten Systemstand'. Verwandte Nachweisluecken derselben Klasse (Lauf nicht aus Belegen rekonstruierbar) sind im Lauf selbst dokumentiert: der vollstaendige Kaskaden-Aufruf ist nicht persistiert (Programmleiter Nr. 8, kostete einen Fehlalarm), und kein Rechenlauf weist vorlaeufige Diskrepanz-Aufloesungen aus (Programmleiter Nr. 6).

**Wirkung auf das Ziel:** Ein Pruefer kann die Behauptung 'unveraenderter Systemstand' nicht aus dem Beleg entscheiden: er sieht einen Commit, weiss aber, dass der ausgefuehrte Code davon abwich, und kann weder den Umfang der Abweichung noch den Code selbst beschaffen. Die Nachweis-Kette Auftrag -> Zeichnung hat damit an ihrem Anker (Systemstand) eine Luecke, die der Bericht ueberdeckt.

**Belege:**
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-M4-32682e958c7811b0b5fc89c3e7eaf897243b2d39151facf5ba60c99397231a6e.json` — "system": {"branch": "fallbericht", "commit": "4b1abf048ac84bfeecce12a67f18983648990799", "dirty": "ja", "quellcode_sha256": "ef1af1a3..."}
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-Q1-ce9faafdc381f40b3900dc55df2d67f102516ac3dbe3f2f7d974a2198ac18def.json` — "system": {... "commit": "8c5698c8...", "dirty": "ja" ...} (erste Zeichnung des Laufs; alle 17 Snapshots tragen dirty=ja)
    - `src/rechner_pipeline/gates/gate_entscheid.py`:9 — plus den Git-Stand des Systems (Setup-Provenienz, P1) — der Lauf ist daraus reproduzierbar.
    - `docs/faelle/baldrian-lauf2.md`:12 — fuenf Abnahme-Gates wurden vom Verantwortlichen Aktuar auf einem einzigen, unveraenderten Systemstand gezeichnet
    - `dev-docs/offene-punkte.md`:62 — Der vollstaendige Lauf-Aufruf (alle Flags, alle registrierten Quellen je Abnahme) ist nirgends als Ganzes persistiert; die Rekonstruktion nach Korrektur 21 kostete einen Fehlalarm

**Widerlegungsversuch des Pruefers:** _provenienz.py begruendet den Quellcode-Hash genau fuer diesen Fall ('dirty=ja allein waere kein exakter Stand: zwei verschiedene lokale Codeaenderungen haetten sonst denselben Wert'), und ONBOARDING dokumentiert das. Das macht Staende UNTERSCHEIDBAR, nicht REPRODUZIERBAR: aus einem Hash laesst sich kein Code wiederherstellen. Moeglicherweise betrafen die uncommitteten Aenderungen nur Doku oder Fall-Protokolle (git status --porcelain zaehlt alles) — genau das kann der Pruefer aber nicht feststellen, und die fuenf finalen Snapshots teilen sich einen Quellcode-Hash, der zu keinem Commit gehoert. Der externe Review T19 hat dieselbe Nachweisgrenze gezogen ('konnten daher nicht kryptografisch gegen den realen Lauf geprueft werden').

**Vorschlag:** gate_entscheid verweigert Annahmen bei dirty='ja' fuer .py/.xml-Aenderungen unter src/ (oder verlangt eine signierte Ausnahme der Rolle 'mensch'); alternativ legt die Zeichnung ein inhaltsadressiertes Archiv des Paketbaums (tar + SHA-256 = quellcode_sha256) unter entscheide/ ab. Fachbericht: Fussnote zum Systemstand ('Commit X, Arbeitsbaum mit Aenderungen ausserhalb des Pakets' nur wenn belegt). Kaskaden-Rezept je Fall und Vorbehalts-Ausweis wie in offene-punkte vorgeschlagen umsetzen.

#### Z3-05 — Es gibt kein Dokument, das das KI-System fuer Aufsicht oder Revision beschreibt; der Fachbericht erwaehnt KI-Beteiligung nicht (hoch, Dokumentation des KI-Systems)

Die Beschreibung des KI-Systems ist auf Entwickler-Dokumente verteilt: AGENTS.md (englisch, fuer Coding-Agenten), skill-architektur.md, prinzipien.md, ADRs, ONBOARDING ('the CLI agent is the model'). Kein Dokument fuehrt fuer einen externen Pruefer zusammen: Ziele, Rollen (Mensch/KI), eingesetzte Modelle je Rolle, Eingriffspunkte (Gates, Mandate, Abbruchkriterien), Grenzen, Nachweise und deren Fundorte. Die beiden an Aktuar/Pruefer/Revision adressierten Fachdokumente enthalten kein Wort zu Agenten, Modellen oder Sessions. Welche Modelle den Lauf fuhren, steht laut regie.md im README des gitignorierten Regie-Bereichs; im Fall ist ein Modell nur fuer die Extraktion belegt (akteure.json: claude-sonnet-5/...), fuer die zeichnende und die orchestrierende Rolle nirgends. Das team-interne Dokument agenten-rollentrennung.md stellt selbst fest, dass die fachlichen Agenten 'zuerst ein Repository sehen'.

**Wirkung auf das Ziel:** Die Z3-Frage 'Ist das KI-System so dokumentiert, dass ein Pruefer Ziele, Grenzen, Modelle, Eingriffspunkte und Nachweise versteht?' ist zu verneinen. Ein Pruefer ohne Repo-Kenntnis findet keinen Einstieg; ein Pruefer mit Repo-Kenntnis muss die Beschreibung aus sechs Orten zusammensetzen und findet die Modelle nicht.

**Belege:**
    - `docs/faelle/baldrian-lauf2.md` — (kein Treffer fuer 'Agent', 'KI', 'Modell', 'Session' im gesamten Dokument; ebenso in baldrian-lauf2-veraenderungen.md)
    - `dev-docs/regie.md`:19 — der Betriebsleitfaden des Spielleiters — Aufsetzen, Benennen, Modelle, Disziplin waehrend des Laufs, Nacharbeit — liegt als README im Bereich selbst
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/abox/fragmente/akteure.json` — "tg2015-tarifmeldung.json": "claude-sonnet-5/extrahiere-quellfragment+verifikation@dc7c80b" (einziger Modellnachweis im Fall)
    - `docs/architektur/prinzipien.md`:9 — erzeugenden Akteur (Modell + Skill + Git-Stand des Setups), Zeitstempel, Konfidenz. Ohne lueckenlose Rueckverfolgbarkeit ist keine Abnahme durch einen Verantwortlichen Aktuar moeglich.
    - `dev-docs/agenten-rollentrennung.md`:13 — Der Agent, der die aktuarielle Abnahme vorbereitet, soll die Welt eines Aktuars sehen ... Stattdessen sieht er zuerst ein Repository.
    - `ONBOARDING.md`:5 — codebase** (the CLI agent *is* the model; Python code pre-digests, validates, computes and accepts)

**Widerlegungsversuch des Pruefers:** docs/architektur/README.md nennt sich ausdruecklich Dokumentation 'des agentischen KI-Systems', die Prinzipien P1-P10 sind eine praezise Grenzbeschreibung, ADR-012 begruendet die Gate-Namen mit 'Pruefer und Revision'. Das sind Bausteine, aber kein Pruefer-Einstieg: kein Dokument nennt Modelle, Mandate und Eingriffspunkte zusammen, und die Fachdokumente verschweigen die KI-Beteiligung ganz — was in einem VU-Bericht ueber ein KI-gestuetztes Verfahren gerade die aufsichtsrelevante Information waere. Die eigene Anforderung P1 (Akteur = Modell + Skill + Git-Stand) wird fuer die Zeichnungs- und Entscheidungsakte nicht erfuellt.

**Vorschlag:** Ein Dokument 'Das KI-System der Bestandsmigration — Beschreibung fuer Pruefer' in docs/ (Unternehmenssprache): Zweck, Rollen mit Kennzeichnung Mensch/KI, Modelle je Rolle und Lauf (aus einem Modell-Register im Fall, z. B. entscheide/mandat oder laufmanifest), Eingriffspunkte (Gates, Mandate, Abbruchkriterien), was KI strukturell nie tut, Nachweise mit Fundorten, bekannte Grenzen (offene-punkte). Akteur-String als Pflichtfeld in gate_entscheid und entscheide, wenn eine Agenten-Rolle zeichnet. Fachbericht um einen Abschnitt 'Rollen, Mandate, eingesetzte Modelle' ergaenzen.

#### Z3-06 — Mandatsentscheide des Menschen sind der schwaechste Beleg der Kette und werden in der Auswertung nicht als Eingriffe gezaehlt (mittel, Zeichnungsmodell / Nachweis)

Die eigentlichen Governance-Entscheide des Menschen im Lauf — Mandatserweiterung fuer den Aktuar-Agenten (ontologie.entscheide), Mandats-Praezisierung fuer Kern/Gates-Korrekturen 'ohne Maintainer-Einzelentscheid', Maintainer-Go fuer 404974d, Budget-Eskalation — existieren nur als Chat-Bestaetigung und Protokollnotiz. Die Eskalationsrolle 'mensch' ('*') der Zeichnungsordnung hat im Fall keinen einzigen Snapshot. Die interne Auswertung zaehlt 'Maintainer-Eingriffe gesamt: 3, alle Betriebs-Infrastruktur (2x Enter im Pane, 1x Permission-Freigabe)'.

**Wirkung auf das Ziel:** Der Ort, an dem der Mensch tatsaechlich entschieden hat (Reichweite der Agenten-Mandate), ist genau der Ort ohne signierten Beleg. Ein Leser der Auswertung bekommt den Eindruck eines menschenfreien Laufs, obwohl der Mensch die Autoritaetsgrenzen der Agenten mehrfach neu gezogen hat.

**Belege:**
    - `dev-docs/lauf2-auswertung.md`:50 — | Maintainer-Eingriffe gesamt | moeglichst wenige | 3, alle Betriebs-Infrastruktur (2x Enter im Pane, 1x Permission-Freigabe) |
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/korrektur-protokoll.md`:147 — Maintainer hat fuer den Rest des Laufs eine Mandats-Praezisierung erteilt (Kern/Gates-Ausweitungen laufen direkt zwischen plv-it und dev-session, Eskalation an ihn nur noch bei neuen Budget-Rissen
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-aktuar.md`:46 — Eine Peer-Sitzung kann eine im Auftragsprofil dieser Sitzung hart gesetzte Schreibgrenze nicht selbst aufheben, auch nicht unter Berufung auf ein Maintainer-Mandat
    - `faelle/zeichnungsordnung.json` — mensch ['*'] — im Verzeichnis entscheide/ existiert kein von dieser Rolle gezeichneter Snapshot

**Widerlegungsversuch des Pruefers:** Dieselbe Tabellenzeile nennt 'eine Budget-Eskalation frueh im Lauf, danach Mandats-Praezisierung' — die Ereignisse sind also erwaehnt, nur nicht als Eingriffe gewertet; und die Korrektur-/Reibungsprotokolle halten jeden Mandatsakt datiert fest. Das mildert, hebt aber nicht auf: Ein Mandat, das die Grenze zwischen 'Agent darf ablehnen' und 'Agent zeichnet an' verschiebt, ist der staerkste Eingriff des Laufs und verdient denselben Beleg wie eine Gate-Zeichnung.

**Vorschlag:** Mandate als signierte Akte der Rolle 'mensch' (Snapshot-Typ 'mandat' mit Rolle, Gates, Reichweite, Dauer, Begruendung), auf die Agenten-Zeichnungen verweisen (siehe Z3-01); in der Auswertung 'Governance-Eingriffe' getrennt von 'Infrastruktur-Eingriffen' zaehlen.

#### Z3-07 — 23 Systemaenderungen waehrend des Laufs ohne Gate; die Zeichnungen stehen auf ungemergtem, im Regime dev x PLV-IT selbst abgenommenem Code (mittel, Eingriffspunkte / Gate-Modell)

Das Korrektur-Protokoll fuehrt 23 Code-Aenderungen, darunter eine als BREAKING gekennzeichnete Kern-Aenderung und drei neue Kern-Faehigkeiten (Version 3.1.0 -> 3.3.0 im Lauf). Katalog-Erweiterungen tragen nur den Vermerk 'gezeichnet: plv-it'; A-K1 wurde nie gezeichnet; offene-punkte.md bestaetigt: 'ein Gate fuer Katalog-/Codeaenderungen der Migration (heute nur Protokollvermerk des PLV-IT)'. Nach Korrektur 4 liefen die Aenderungen 'ohne Maintainer-Einzelentscheid'. Der Skill integriere-migrationsinkrement verlangt 'Abnahme durch den Menschen, Merge, Push durch den Menschen' — der Merge (PR #11) steht aus, der Fachbericht erklaert den Fall dennoch als 'vollstaendig geprueft und abgenommen'.

**Wirkung auf das Ziel:** Ein Eingriffspunkt des Modells ('Kern-Aenderung noetig? mehr als Parametrierung: STOPP -> A-K1-Vorlage -> MENSCH', skill-architektur) hat im Lauf keinen Beleg erzeugt; die Grenze zwischen 'Parametrierung' und 'Erweiterung' wurde von den Agenten selbst gezogen (Korrektur 1: 'Einordnung A-K1: keine T-Box-Erweiterung ... Von der dev-Session bestaetigt'). Fuer einen Pruefer ist nicht sichtbar, dass die abgenommenen Rechenwerte auf einem Code stehen, der die menschliche Landung noch nicht passiert hat.

**Belege:**
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/korrektur-protokoll.md`:3 — Katalog-Erweiterungen der Transformationsschicht (`ontologie/transformation.py`) tragen den Vermerk "gezeichnet: plv-it".
    - `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/korrektur-protokoll.md`:421 — ### 15. Terminalbedingung V_korr(n)=0 verletzt (Gebiet: Kern/Gates, BREAKING)
    - `dev-docs/offene-punkte.md`:58 — Ebenso offen: ein Gate fuer Katalog-/Codeaenderungen der Migration (heute nur Protokollvermerk des PLV-IT im Korrektur-Protokoll).
    - `.claude/skills/integriere-migrationsinkrement/SKILL.md`:57 — 5. Abnahme durch den Menschen, Merge, Push durch den Menschen.
    - `docs/architektur/skill-architektur.md`:58 — mehr als Parametrierung: STOPP --> A-K1-Vorlage --> MENSCH

**Widerlegungsversuch des Pruefers:** ADR-007 legt den menschlichen Koordinationspunkt bewusst auf die LANDUNG (Merge mit gruener Gesamt-Suite aller Faelle), nicht auf den Lauf; die Korrekturen sind Kern-Parametrierungen mit altem Verhalten als Vorgabe, keine T-Box-Aenderungen (A-K1 ist definiert als T-Box-Aenderung); jede Korrektur ist mit Commit, Suite-Zahl und Neuzeichnungs-Kaskade protokolliert; der Merge-Plan sieht den menschlichen Review vor. Das ist eine tragfaehige, dokumentierte Grenze — weshalb nur 'mittel'. Was bleibt: Der Fachbericht muesste den Vorbehalt tragen, und die Einordnung 'keine A-K1-Pflicht' trifft heute der Agent, nicht ein Mensch.

**Vorschlag:** A-M4 bindet den Hash des Korrektur-Protokolls (oder eine Liste der Systemaenderungs-Commits seit Fall-Anlage) als Pflichtbeleg; Fachbericht mit Abschnitt 'Systemaenderungen im Lauf und Stand der Uebernahme in den Hauptzweig'; ein leichtes Pruef-Gate P-S1 'Systemaenderung im laufenden Fall' (Klassifikation Parametrierung/Erweiterung/T-Box mit menschlicher Bestaetigung der Klasse).

#### Z3-08 — Zustaendigkeit fuer A-M4 widerspruechlich: Grundsatzdokumentation und ADR-010 nennen das Migrationsprojekt, die Zeichnungsordnung laesst nur den Aktuar zeichnen (mittel, Rollenmodell / Zeichnungsbefugnis)

Grundsatzdokumentation 9.15 und ADR-010 ordnen die Verantwortung fuer das Migrationscontrolling (A-M4) dem Migrationsprojekt zu, den aktuariellen Test dem Verantwortlichen Aktuar. In der Zeichnungsordnung des Laufs zeichnet plv-aktuar alle fuenf Gates, plv-it (Migrationsprojekt/Programmleiter) nur A-K1 — das nie gezeichnet wurde. Der Fachbericht sagt 'Alle fuenf Abnahme-Gates ... vom Verantwortlichen Aktuar'.

**Wirkung auf das Ziel:** Die Zeichnungsbefugnis (Ordnung) stimmt nicht mit der Rollen-Definition (Grundsatzdokumentation, ADR-010) ueberein — genau die Uebereinstimmung, die Z3 prueft. Ein Pruefer, der aus 9.15 ableitet, das Migrationsprojekt habe das Controlling verantwortet, findet dafuer keinen Zeichnungsbeleg.

**Belege:**
    - `docs/mathematik/grundsatzdokumentation.md`:689 — | **Migrationscontrolling** | $t_0$ | Vollständigkeit, Überleitung, Bilanz ... | Migrationsprojekt |
    - `docs/architektur/adr-010-aktuarieller-test-und-controlling.md`:27 — Voller Bestand, aggregierend. Verantwortung: Migrationsprojekt.
    - `faelle/zeichnungsordnung.json` — plv-aktuar: [A-Q1, A-M1, A-M2, A-M3, A-M4]; plv-it: [A-K1]
    - `docs/faelle/baldrian-lauf2.md`:23 — Zeichnungs-Belege (SHA-256-Snapshots, Rolle Verantwortlicher Aktuar ueber die Zeichnungsordnung): A-Q1 fd793260, A-M1 fb1550c0, A-M2 411ac21c, A-M3 d260e621, A-M4 32682e95

**Widerlegungsversuch des Pruefers:** 9.15 sagt selbst: 'Die Trennung ist methodisch, nicht organisatorisch', und 'Verantwortlich zeichnet der Verantwortliche Aktuar (§ 141 VAG)'. regie.md begruendet die Zuordnung mit dem Vier-Augen-Prinzip ('wer den Prozess faehrt, nimmt ihn nicht selbst fachlich ab'). Beides ist vertretbar; der Widerspruch bleibt aber in der Tabelle 9.15 und in ADR-010 stehen, ohne dass irgendwo erklaert wird, dass 'Verantwortung Migrationsprojekt' keine Zeichnungsrolle ist.

**Vorschlag:** In ADR-010 (Nachtrag) und 9.15 klaeren: 'Verantwortung Migrationsprojekt' heisst Erstellung und Vorlage des Controllings, die Zeichnung liegt beim Aktuar — oder A-M4 als Mitzeichnung (programmleiter + plv-aktuar) in der Zeichnungsordnung abbilden.

#### Z3-09 — Skill-Texte hinken dem Code hinterher (Gate-Menge, Skill-Zahl, Reihenfolgezwang) — obwohl Skills 'Teil der Nachweiskette' sind (niedrig, Skill-Doku / Drift)

Klasse: Der Skill migrationsfall-durchfuehren sagt an einer Stelle 'Erzwungen ist im Code nur zweierlei: A-Q1 und A-M1 gehen A-M4 voraus', an anderer, dass A-M4 auch A-M2 und A-M3 pinnt; seine description und skill-architektur nennen als menschliche Gates 'A-Q1/A-M1/A-M4/A-K1' ohne A-M2/A-M3, waehrend die Zeichnungsordnung und A-M4-Pflichtbelege alle fuenf tragen. Das Pipeline-Dokument zaehlt 'zehn' Skills, es sind elf. Der Skill nennt die zeichnende Rolle 'plv-va', der Lauf 'plv-aktuar' (siehe Z3-03).

**Wirkung auf das Ziel:** Deckung der Skills mit dem tatsaechlichen Lauf (Gate-Ledger, Snapshots) ist an diesen Stellen nicht gegeben; wer den Skill als Beschreibung des Verfahrens liest, unterschaetzt die erzwungene Gate-Menge.

**Belege:**
    - `.claude/skills/migrationsfall-durchfuehren/SKILL.md`:73 — Erzwungen ist im Code nur zweierlei: **A-Q1 und A-M1 gehen A-M4 voraus** — beide als Pflichtrollen im A-M4-Snapshot.
    - `.claude/skills/migrationsfall-durchfuehren/SKILL.md`:436 — pinnt sie als Rollen `am1_snapshot`/`am2_snapshot`/`am3_snapshot`: A-M1 immer ... im Bestands-Scope auch A-M2 und A-M3
    - `docs/architektur/migrations-pipeline-v01.md`:259 — aus den zwei genannten Skills sind inzwischen zehn geworden
    - `faelle/baldrian-klv-tg2015-lauf2/entscheide/A-M4-32682e958c7811b0b5fc89c3e7eaf897243b2d39151facf5ba60c99397231a6e.json` — pflichtbelege: abnahmebericht, am1_snapshot, am2_snapshot, am3_snapshot, aq1_snapshot, migrationssuite, pb1_ledger, pk1_belege, pq3_ledger

**Widerlegungsversuch des Pruefers:** Der externe Review T19 hat einen Nachbar-Fall (fall.BELEGROLLEN-Kommentar) bereits korrigiert, und die spaetere Skill-Stelle Z.436 ist korrekt — der Leser findet die Wahrheit im selben Dokument. Bleibt Politur, aber die Klasse (Skill-Text nicht mit Code synchron) ist dieselbe, die T19-05 gefunden hat.

**Vorschlag:** Die Gate-Menge als eine Quelle fuehren (GUELTIGE_GATES / fall.BELEGROLLEN) und im Skill nur zitieren; die Wortlisten-Tests um die A-M4-Pflichtbelegrollen ergaenzen oder — besser — die Kernregeln je Skill aus dem Code generieren.

### Vom Pruefer korrigierte Punkte der Sammlung

- Luecke 'Skill-Paritaet nicht geprueft': geprueft — `diff -r .claude/skills .agents/skills` ist leer (byte-identisch), tests/test_agent_workflow_docs.py existiert und sichert die Paritaet sowie Kernregeln als Wortlisten (test_migrations_skills_nennen_die_tragenden_regeln, test_rollen_skills_tragen_ihre_haerte_grenzen). Kein Befund.
- Spannung 'Rollentrennung widerspruechlich dargestellt (skill-architektur vs. agenten-rollentrennung)': nicht haltbar als Widerspruch. skill-architektur beansprucht getrennte Skills mit Haerte-Grenzen, agenten-rollentrennung kritisiert den gemeinsamen WISSENSRAUM (AGENTS.md wird vor jedem Skill geladen) — beides ist gleichzeitig wahr. Die Kritik stuetzt Befund Z3-05 (Doku des KI-Systems), ist aber kein eigener Widerspruch.
- Spannung 'Kernversion 3.3.0/1517 vs. 3.4.0/1534': das Veraenderungs-Dokument nennt an derselben Stelle drei Messzeitpunkte ('1479 vor dem Lauf, 1517 nach den 23 Korrekturen, 1534 nach Review-Nacharbeit') und '3.1.0 in den Lauf ... 3.4.0 aus der Nacharbeit'; lauf2-auswertung misst 'nach Lauf 2'. Der Unterschied ist erklaert, kein Befund; hoechstens koennte lauf2-auswertung den Messzeitpunkt in der Tabelle nennen.
- Luecke 'src/rechner_pipeline/cli.py existiert nicht': korrekt, aber irrelevant — alle Einstiege sind python -m Module (fall.py, gates/*.py, ontologie/entscheide.py), so dokumentiert in AGENTS.md. Kein Befund.
- Spannung 'dirty=ja im letzten A-M4-Snapshot': untertrieben — ALLE 17 Snapshots des Falls (A-Q1 bis A-M4, alle Anlaeufe) tragen dirty='ja'. Als Befund Z3-04 uebernommen und verschaerft.
- Behauptung 'gate_entscheid erzwingt A-M1 vor A-M4': praezisiert — im Bestands-Scope erzwingt A-M4 A-M1, A-M2 UND A-M3 als Pflichtbelegrollen (am1/am2/am3_snapshot im A-M4-Snapshot verifiziert); die Skill-Description und skill-architektur nennen A-M2/A-M3 nicht (Befund Z3-09).
- Darstellung 'P9-Snapshots nicht editierbar im laufenden Betrieb — append-only': praezisiert — entscheide/ ist ein frei editierbares Verzeichnis; die Unveraenderlichkeit entsteht durch Hash-, Dateinamen-, Ketten- und HMAC-Validierung beim Lesen (ADR-008 Kontext), nicht durch Dateischutz.
- Behauptung 3 (ADR-008 'teilweise'): bestaetigt und vertieft — der Programmleiter dokumentiert in Eintrag 7, dass die Luecke strukturell war ('NIEMANDEN mit der Befugnis ... ausser dem Menschen selbst') und per Code-Aenderung 404974d im Lauf geschlossen wurde; die Korrektur ist ohne ADR und ohne Nachzug der normativen Texte erfolgt (Befund Z3-02).
- Frage des Sammlers 'welche Skills/ADRs noch heranziehen': vollstaendig gelesen wurden migrationsfall-durchfuehren, ADR-008/-009/-010/-012, prinzipien.md, Pipeline-Dokument Abschnitte 4 und 9, regie.md, alle drei Reibungsprotokolle, Korrektur-Protokoll (Kopf und Eintraege 1, 4, Ueberschriften), alle 17 Snapshots im Feldauszug, Zeichnungsordnung, A-M4-Ledger, A-Box-Diskrepanz mit Historie, zeichnung.py, entscheide.py (Rollenlogik), gate_entscheid.py (Rollen-/Freigabe-Logik), _provenienz.py, schemas.py (Rollenpruefung), beide Rollen-Tests; die uebrigen Skills nur an den Mensch-/Rollen-Stellen.

### Grenzen der Sammlung (vom Sammler benannt)

- Die uebrigen neun Skill-Dateien (.claude/skills/{bereite-fachkonflikt-auf,pruefe-migrationscontrolling,transformiere-quellbestand,extrahiere-quellfragment,entwickle-im-zielsystem,teste-adversarial,dokumentiere-system,author-rechner-toolbox-gate,integriere-migrationsinkrement}/SKILL.md) wurden aus Zeit-/Umfangsgruenden nicht vollstaendig gelesen, nur ihre Existenz und ihr Rollen-Eintrag in skill-architektur.md geprueft.
- ADR-001 bis ADR-007 sowie ADR-010, ADR-011, ADR-013 bis ADR-016 wurden nicht gelesen -- der Auftrag nannte gezielt ADR-008/009/012 (Gates/Rollen/P9) als Startpunkte, weitere ADRs wurden nur aus Nachtraegen anderer Dokumente zitiert (z. B. ADR-010-Bezug in ADR-009-Nachtrag).
- FALL/abgeleitet/reibungsprotokoll-programmleiter.md (300 Zeilen) und der Rest von reibungsprotokoll-baldrian.md sowie der volle korrektur-protokoll.md (737 Zeilen, 23 Eintraege) wurden nur angerissen, nicht vollstaendig gelesen -- die drei bereits gelesenen Ausschnitte reichten fuer eine erste belastbare Spannungs-/Behauptungslage.
- docs/architektur/migrations-pipeline-v01.md (in AGENTS.md als Referenz fuer den Pipeline-Ablauf genannt) wurde nicht gelesen.
- docs-local/, simulation/, regie/ wurden bewusst NICHT geoeffnet (Tabu laut Auftrag); auch die Datei faelle/baldrian-klv-tg2015-lauf2/abgeleitet/reibungsprotokoll-baldrian.md wurde nur soweit gelesen, wie sie selbst auf simulation/ verweist, ohne diesen Bereich zu betreten.
