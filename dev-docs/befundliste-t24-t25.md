# Befundliste — DORA-Runden T24 und T25 (Triage gegen main 10ee765)

dev-session, 2026-09-08. Zwei externe DORA-Reviews vom 2026-09-07: T24 zu
PR #14 (`ebenen`, geprueft gegen origin/main 947dd76; acht Befunde, sieben
hoch, einer mittel) und T25 zu PR #17 (`freischaltung`; zwoelf Befunde, neun
hoch, ein Integrationsblocker, einer mittel, einer niedrig). Seit den Reviews
sind beide Branches, T23 Block 1-5, T24-07 mit Nachfix und die Freischaltung
Schritt 9 auf main gelandet (Stand ohne Zweige, 10ee765). Prozesszusage an
den Reviewer: Korrekturen aus dieser Liste auf EINEM neuen Branch ab main.

## Fortschreibung: Stand 2026-09-15

Die Triage unten steht gegen main **10ee765** (2026-09-08). Seither ist
main bis **1dc736b** gewandert, und der Korrekturbranch `dora-t24-t25`
hat begonnen. Was sich dadurch an den Befunden geaendert hat — nicht
vermutet, sondern am Code nachgesehen:

| Befund / Baustein | Stand 2026-09-15 |
|---|---|
| **T24-02** | ERLEDIGT auf `dora-t24-t25` (806804f). Der Monatsabschluss wird mit der an SEINEM Stichtag gebuchten Sicht gerechnet. Entscheid des Maintainers: Schnitt am Stichtag — "wir simulieren das Innere eines Unternehmens". |
| **Block A, erster Punkt** (gemeinsame Rollenkonstante fuer P-B1) | ERLEDIGT durch 5ca0306 + 5866157 (N-01). Die drei Aufzaehlungen sind eine Tabelle: `manifest.ROLLEN_DATEIEN` -> `vorbedingungen.PB1_ROLLEN`, von `bestand_validate` und `abnahmebericht` importiert. |
| **T25-03 Teil (a)** | ERLEDIGT durch 5866157. |
| **T25-03 Teil (b)** | OFFEN. `abnahmebericht.PB1_VOLLPROFIL` ist weiterhin das Vier-Rollen-Literal `{portfolio, historie, ledger, config}` mit benannter Ausnahme. Entscheid 3 steht aus. |
| **T24-08** | GESCHRUMPFT durch d03a203 (Kreise sind Pflicht, sobald eine Config einen Tagesbetrieb fuehrt). Der Positions-Fallback liefert ebenfalls k >= 1, also beginnt jedes reservierte Band bei 10.000.001; ein Vergleich `police_id <= 10 Mio` am Eingang schliesst die Klasse. Der Vorbehalt "nummernkreis=None" der Triage ist damit erledigt. |
| **T25-12** | ERLEDIGT in diesem Commit. |
| **N-01** (Entscheid 10) | ERLEDIGT, auf main seit 2026-09-08. |
| **T24-04 Teil 1** | ERLEDIGT, beide Haelften. Journalgespeist (602b935): Paketschema 3 traegt tagesjournal.parquet, der Konsument rechnet buchungen.gesamt und je_ereignis dagegen nach. Protokollgespeist: bestand, uebernahmen, verankerung, abschluesse, gefuehrt_seit, neugeschaeft.seit_betriebsbeginn und die fuenf uebrigen provenienz-Felder werden gegen die letzte gruene Protokollzeile gehalten; die Abschluss-Ableitung ist jetzt EINE Funktion (seite.abschluesse_aus_protokoll), die Erzeuger und Konsument teilen. Teil 2 (Verankerung ausserhalb des Pakets) bleibt offen — Entscheid 1. |
| **T24-08** | ERLEDIGT (e02bec9): Das Zielsystem vergibt eigene Policennummern, ein Band je Fall im freien Raum 1..10 Mio, Uebersetzungstabelle im Eingang. Entscheid 8 = (b), nicht (a). |
| Kleinkram "Reichweite der AST-Ratsche" | ERLEDIGT in diesem Commit (Modul-Docstring `betrieb/_loeschen.py` und `dev-docs/offene-punkte.md`). |
| **T25-09** | ERLEDIGT (5d74113). Die Endlichkeitswache und die Nachrechnung fuehrten dieselbe Spaltenmenge als wortgleiches Literal, und beiden fehlte `korrekturschicht` — ausgerechnet die Position, die 9.11 fordert. Jetzt `ABSCHLUSS_ZAHLEN`, abgeleitet ueber den Spaltentyp: Wer dem Abschluss eine Bewertungsgroesse gibt, bekommt beide Pruefungen dafuer. Der rho-Nurvergleich der Fuehrungsprobe war bereits mit T25-03 (c9714d6) geschlossen; der Befund war also schmaler als berichtet. |
| **T25-06 PEX** | ERLEDIGT (2e257b6). Entscheid des Maintainers 2026-09-15: WERTSTETIGE Absorption — die beitragsfreie Summe ist eine garantierte Leistung, also muss die Umwandlung werthaltend sein. Vier Stellen fragen die Regel jetzt bei `kern.korrekturschicht.zuschlag_bei_pex`; das Abtippen an vier Stellen WAR der Befund. `HEILUNG["PEX"]` ist geprueft, Kern auf 3.6.0. Mitrepariert: Bewertung entschied den Zweig an `zustand_ta`, die Rechnung an der Zeit der Freistellung — in widerspruechlichen Daten zwei Antworten; `validate_verankerung` weist den Widerspruch jetzt aus. |
| **T25-06 RED** | ERLEDIGT (6f5f40c, 55c341b, 9ee8eb4 und der Betriebsweg). Entscheid: volle Absorption in die Neuberechnung, ausgewiesen und journalisiert. Vier Commits: Datenvertrag `reduktionen.parquet`, Schicht in die Neuberechnung (`zusatz_dk`), Engine erzeugt und Bewertung bewertet, Betriebsweg. Eigener Zufallsstrom (`HERABSETZUNG_STREAM`), damit kein bestehender Bestand verrutscht — belegt durch einen Fingerabdruck des Laufs vom Stand davor. |

**Drei Funde beim Bauen, die der Review nicht hatte** (alle derselben
Klasse "dieselbe Menge an zwei Orten gepflegt"):

1. `read_portfolio` fuehrte die Tabellenfamilien als acht `if`-Zweige.
   Wer eine vergisst, faellt nicht in einen Fehler, sondern still in die
   Rueckfall-Behandlung des Stamm-Schnitts. Jetzt eine Liste.
2. **Die P-B1-Engine lief ueber eine zweite, handgepflegte Rollenliste**
   neben ihrem Spaltenvertrag. Eine neue Erzeugerrolle fiel still
   hindurch: nicht gelesen, nicht geprueft — und die Engine meldete
   trotzdem Erfolg. Das ist der schwerste der drei: Er betrifft das
   Testat, nicht nur die Lesbarkeit. Jetzt laeuft sie ueber
   `ROLLEN_DATEIEN`, und eine Rolle ohne Spaltenvertrag ist ein harter
   Fehler.
3. `betraege_hergeleitet` (der Zaehler im P-B1-Beleg) war ein Literal und
   haette RED unterschlagen — das Testat wiese weniger nach, als
   geprueft wurde. Jetzt aus der Liste des Herleiters abgeleitet.

**Entscheide des Maintainers, Stand 2026-09-15:** Nr. 6 entschieden (a),
Nr. 10 erledigt. Die uebrigen acht stehen aus; Nr. 8 ist durch die
Kreise-Pflicht auf eine Ja/Nein-Frage geschrumpft.

**Zur Messung von T24-02 an echten Daten** (Laufzeit `~/apps/plv`): Die
Erstbefuellung holte 1994 bis 2026 in EINEM Lauf nach und rechnete damit
jeden der 387 Monatsabschluesse mit dem Wissen von 2026. Nach dem Fix neu
erzeugt und bytweise verglichen: **192 der 387 Abschluesse haben sich
geaendert**, keiner unerwartet.

Die erste Schaetzung lautete 29 und war falsch gestellt. Sie fragte, ob
eine Buchung eine MONATSGRENZE ueberschreitet (22 Vorfaelle, alles
Todesfaelle mit 34 bis 114 Tagen Verzug). Die richtige Frage ist, ob es
einen Monatsersten gibt, an dem das Ereignis schon WIRKT, aber noch nicht
GEBUCHT ist — und das ist der Regelfall, nicht die Ausnahme: Ereignisse
wirken zum Monatsersten, gebucht wird am naechsten Werktag, und faellt
der Erste auf ein Wochenende, liegt genau der Stichtag dazwischen. Von
4625 verspaetet gebuchten Journalzeilen wirken ALLE 4625 zum
Monatsersten (ERH 4024, ABL 191, STO 188, TOD 141, PEX 68, INV 12,
REA 1). Vorhergesagt waren danach 193 Abschluesse, gemessen 192; die eine
Abweichung (2020-04-01) ist ein Stichtag, an dem die entfernte Buchung
keinen Wert der Tabelle bewegt. Nachgewiesen an Police 15435601 (Tod wirksam
2006-01-01, gebucht 2006-03-13): im Abschluss per 2005-12-01 vorhanden,
per 2006-01-01 und 2006-02-01 nicht — obwohl das Unternehmen erst im
Maerz davon erfuhr. Diese Abschluesse gehoeren nach dem Fix neu erzeugt.

## Stand vor der Triage

| Befund | Stand 2026-09-08 |
|---|---|
| T24-07 | geschlossen (33452b5, Nachfix d9f7566; von der merge-session nachgestellt) |
| T25-05 | dem Reviewer als "durch die Merges entfallen" gemeldet — die Triage WIDERLEGT das: Block 1 schloss nur die Bytes-Bindung von vier Eingaben in verankerung_belegen; die Fuehrungsprobe hasht weiter nach der Lesung, und die fehlenden Eingaben (Spez, Red-Anteile, zeilen, vorgeschichte, anker) sind in beiden Producern offen. Korrektur an den Reviewer noetig. |
| T25-07 | GESCHLOSSEN: Code auf main (1b904e0, Schritt 9), auf der Laufzeit ausgefuehrt 2026-09-08 (Image 5866157, Wache gruen, Schicht und Verankerung angewandt) |
| T25-10 | gegenstandslos (PR #17 ist gemergt, main = 10ee765) |
| T25-12 | offen, Einzeiler (Leerzeile am Ende von docs/faelle/baldrian-lauf2.md) |
| uebrige 15 | offen, triagiert in dieser Liste |

## Methode

Je Befund ein Pruefagent (Sonnet, hohe Sorgfalt), lesend im Worktree
`rechner-pipeline-t24` auf main 10ee765; Reproduktionen nur in
Temporaerverzeichnissen, keine pytest-Laeufe, Arbeitsbaum unangetastet.
Sieben Fragen je Befund wie in Runde T23: bestaetigt? Stand auf main heute
(unveraendert, teilweise, erledigt)? konkreter Schaden? Schwere-Zustimmung?
verletzte KLASSEN-Invariante? WEITERE STELLEN mit demselben Muster?
Fix-Umfang zum Schliessen der Klasse samt fangendem Test?

## Ergebnis auf einen Blick

| Befund | Reviewer | Urteil | Stand auf main | Schwere-Zustimmung | weitere Stellen | Umfang |
|---|---|---|---|---|---|---|
| T24-01 | hoch | bestaetigt | unveraendert | ja, oberer Rand | 2 (neuaufsetzen-Doppel-Rename; d9f7566-Luecke "stand fehlt ganz") | L |
| T24-02 | hoch | bestaetigt | unveraendert | ja | 2 (Bestandsbericht und Teilbestandsberichte aus derselben heute-Sicht) | M |
| T24-03 | hoch | bestaetigt | unveraendert | ja | 0 | M |
| T24-04 | hoch | bestaetigt | unveraendert | ja | 3 (provenienz-Felder, abschluesse-Hashes, buchungen/neugeschaeft ohne Beleg) | M (S fuer 4 Sektionen, L fuer buchungen/neugeschaeft) |
| T24-05 | hoch | bestaetigt | unveraendert (Luecke gewachsen: zehn statt neun Rollen) | ja | 1 schwaecher (falldaten.py strukturell_verifiziert) | M-L |
| T24-06 | hoch | teilweise | Teil B am Rand durch b70c081 (Schluesselklasse im Eingang), Doppel-Lesen und Snapshot-Pflicht unveraendert | ja | 3 (tageslauf liest den Eingang bei jedem Lauf und schreibt ihn ins Protokoll; seite rendert ihn unbesehen; neuaufsetzen nutzt denselben schwachen Leser) | M (L mit dauerhafter Bindung) |
| T24-07 | hoch | geschlossen | 33452b5 + d9f7566 | — | — | — |
| T24-08 | mittel | bestaetigt (Fix praezisiert: police_id <= 10 Mio, ein Vergleich; Vorbehalt nummernkreis=None) | unveraendert | ja, oberer Rand | 2 (cli_fortschreibung --uebernahme; ereignisse._pruefe_mitgebrachte_zugaenge — alle drei Guards pruefen nur beim Zusammenfuehren) | M |
| T25-01 | hoch | bestaetigt | unveraendert (31c1caf nur Lesepfad) | ja | 0 (Kontrast: _b1_fehler und _bericht_fehler rechnen nach) | M |
| T25-02 | hoch | bestaetigt | unveraendert (mit echten Fallartefakten: Endbestand +999999 und Endhistorie XXX bestehen die Probe) | ja | 1 (neue Erhoehungsscheiben nur bei spaeterer Buchung geprueft — 0 von 330 im Fall) | L |
| T25-03 | hoch | bestaetigt | Teil (a) durch 5866157 geschlossen (erlaubte_rollen aus der Tabelle, Absturz-Guard; die A-M4-Nachrechnung leitet Stornos jetzt MIT Schicht her, siehe N-01); Teil (b) offen (am echten Fall gezeigt: A-M4 bindet den VOR-Beleg, der NACH-Beleg mit Schichtrollen wird strukturell abgelehnt) | ja | 3 (PROBE_PFLICHTEINGABEN, pb1_umfang, gate_entscheid) | M-L |
| T25-04 | hoch | bestaetigt | unveraendert (31c1caf nur Lesepfad) | ja, oberer Rand | 3 (validate_schichten einseitig; schichten_je_police bis in den Tageslauf; _schicht_fuer kann fehlend nicht von unnoetig unterscheiden) | M-L |
| T25-05 | hoch | TEILWEISE (KORREKTUR: nicht entfallen) | Haelfte (a) nur in verankerung_belegen durch 31c1caf geschlossen; fuehrungsprobe hasht weiter nach der Lesung; Haelfte (b) in beiden offen | ja | 3 (bestand_uebernehmen ohne jeden eingaben-Block; migrationssuite_lauf zweite Lesung; aktuartest_lauf eigene Eingaben ungebunden) | L |
| T25-06 | hoch | bestaetigt (staerker als berichtet) | unveraendert | ja | 2 (tarifwerk()-Docstring verspricht fuenf Konsumenten, red_verfahren nur in der Fuehrungsprobe gelesen; Fachkonzept vs. Heilungsregel geprueft=False) | M (RED-Verdrahtung) + aktuarielle Festlegung (PEX-Wertstetigkeit) |
| T25-07 | hoch | geschlossen | 1b904e0 + Ausfuehrung 2026-09-08 auf Image 5866157 | — | — | — |
| T25-08 | hoch | bestaetigt | unveraendert | ja | 3 (verankerung_belegen schreibt schichten nur bei Bedarf; eingang_anlegen registriert, was physisch liegt; cli_fortschreibung-Ausgabe nur mit optionalem --manifest geschuetzt) | L |
| T25-09 | hoch | bestaetigt | unveraendert | ja | 1 (fuehrungsprobe rho-Nurvergleich, dieselbe Wurzel wie T25-03) | M |
| T25-10 | Blocker | gegenstandslos | Merge | — | — | — |
| T25-11 | mittel | bestaetigt | unveraendert | ja, oberer Rand | 2 (entscheide.py lade/speichere ohne Wache; abox.speichere nicht atomar — dieselbe Denkfigur wie d9f7566-Luecke in T24-01) | M |
| T25-12 | niedrig | bestaetigt (selbst geprueft: Datei endet auf zwei Zeilenumbrueche) | unveraendert | ja | — | S |
| N-01 | neu (vorzeige, 2026-09-08) | GESCHLOSSEN (5ca0306 + 5866157, beide Testate gezeichnet, auf main seit 2026-09-08) — Ledger richtig, Wache falsch | tageslauf._wache reicht schichten/verankerung nicht an P-B1 — Herleitung ohne Korrekturschicht; jeder STO eines uebernommenen Vertrags nach der Verankerung wird rot; trifft Schritt 9 auf ~/apps/plv identisch | — | 1 (Fall-P-B1 vor der Fortschreibung ebenfalls ohne die Rollen, folgenlos zum Stichtag) | M, in Reihenfolge: Vokabel der Nebentabellen in models + Pruefung am Betriebseingang (Fixture traegt ungueltiges POL, Kern stuerzt vier Schichten tiefer ab); vier Aufrufer auf ROLLEN_DATEIEN; _teilbestand/_bericht (+13.700 EUR DK je Vertrag mit Schicht, gemessen); Bericht weist Korrekturschicht aus; AST-Ratsche; Klassen-Test |

## Kernbefund

1. Von zwanzig Befunden sind FUENFZEHN am Code BESTAETIGT, zwei TEILWEISE
   (T24-06: Block 4 der T23-Reparatur traf den Rand; T25-05: Block 1 band
   nur vier Eingaben des Schichtbelegs), einer ist geschlossen (T24-07 mit
   Nachfix), einer gebaut und nicht ausgefuehrt (T25-07), einer
   gegenstandslos (T25-10). KORREKTUR gegenueber der Mail an den Reviewer:
   T25-05 ist NICHT durch den Merge entfallen — die Fuehrungsprobe hasht
   weiter nach der Lesung, und die fehlenden Eingaben sind in beiden
   Producern offen. Nur T25-10 ist entfallen.
2. Kein bestaetigter Befund ist durch die seither gelandeten Commits
   (Freischaltung, T23 Block 1-5, T24-07, Schritt 9) auch nur teilweise
   erledigt; die Fehlerstellen sind auf 10ee765 byte-identisch oder um
   wenige Zeilen verschoben. Bei T24-05 ist die Luecke seit dem Review
   GEWACHSEN (zehn statt neun Belegrollen; Tagesbetrieb seit Schritt 9 voll
   verdrahtet). Bei T25-06 ist die Faktenlage STAERKER als berichtet: der
   Docstring von TarifGeneration.tarifwerk() verspricht fuenf Konsumenten,
   red_verfahren liest nur die Fuehrungsprobe.
3. Die Suche nach demselben Muster fand 31 WEITERE Stellen ueber die
   Reviewer-Zitate hinaus (T24: 13, T25: 18). In drei Faellen (T25-05,
   T25-08, T24-01) reicht das Muster in Module, die der Reviewer nicht
   genannt hat (bestand_uebernehmen, migrationssuite_lauf, aktuartest_lauf;
   verankerung_belegen; neuaufsetzen).
4. Vier Klassen tragen fast alle Befunde:
   (K1) Ein Vertrag, der an EINER Stelle durchgesetzt wird, schuetzt nur
   die Aufrufer, die ihn durchlaufen — Seite, Paket, Laufzeit-Leser und
   Zugang lesen dieselben Bytes erneut, ohne ihn zu wiederholen
   (T24-03, T24-04, T24-05, T24-06). Dazu die von der merge-session
   gemessene Verschaerfung: das Stands-Paket ist nur gegen sich selbst
   geprueft; die Protokollkette schuetzt nicht gegen das Neuschreiben der
   ganzen Datei; das Paket muss an etwas gebunden sein, das nicht im Paket
   liegt.
   (K2) Ein Beleg, der eine Pruefung bezeugt, muss nachrechnen oder eine
   Positivschwelle verlangen — Flags, Hashes selbst benannter Dateien und
   Teilmengen-Vergleiche sind kein Beweis (T25-01, T25-02, T25-03, T25-05,
   T25-09). Dieselbe Rollen-/Spaltenmenge wird an mehreren Stellen als
   Literal gepflegt und an einer vergessen (T25-03, T25-09 — das Muster von
   T23-06).
   (K3) Ein Producer veroeffentlicht Teilartefakte vor dem eigenen Urteil
   oder laesst Reste frueherer Laeufe stehen; Konsumenten lesen nach
   Dateiexistenz statt nach Registrierung; Unklarheit wird als "nichts zu
   schuetzen" gelesen (T25-04, T25-08, T25-11, und die d9f7566-Luecke in
   T24-01).
   (K4) Fachzusagen des Betriebsmodells, die der Code nicht einloest:
   "derselbe Stand wie jede Nacht" (T24-02), "ein Absturz hinterlaesst den
   alten Stand" (T24-01), "die Korrekturschicht ist nie unsichtbar"
   (T25-09), "jeder Konsument liest die drei Schalter" (T25-06),
   "Nummernkreise reservieren" (T24-08).
5. Abweichungen von der Reviewer-Schwere: keine nach unten. Am oberen Rand
   ihrer Kategorie: T24-01, T25-04 (hoch), T24-08, T25-11 (mittel).
6. Testschwaechen als Teil des Befunds: snapshot_sha256 None ist im
   Testkorpus der Normalfall (T24-06); os.replace wird global gepatcht und
   feuert vor dem eigentlichen Tausch (T24-01); die Ratsche aus Block 1
   fuhr nur sechs Gates, nicht die Producer-Familie (T25-05); kein Test
   laesst ein P-B1-Vollprofil mit Schichtrollen durch A-M4 (T25-03).
7. KONSEQUENZ jeder Korrektur in src/: der Systemstand wandert. Nach dem
   Branch muss der Fall baldrian-klv-tg2015-lauf2 die komplette
   Producer-Kette und alle fuenf Zeichnungen auf dem neuen Stand neu
   erhalten (A-M4 verlangt "denselben Stand"). Deshalb EIN Branch, EINE
   Neuzeichnung — nicht je Block.

## Reparaturplan (Vorschlag; Bloecke, Reihenfolge und Zuschnitt entscheidet der Maintainer)

Grundsatz wie in Runde T23: EIN Commit je Block, EIN parametrisierter
KLASSEN-Test ueber alle Instanzen, Konventionspruefung (Ratsche) wo
moeglich, ein adversarialer Agent je Block. Alle Bloecke auf EINEM Branch
dora-t24-t25 ab main 10ee765 (Prozesszusage an den Reviewer); Testat der
merge-session vor dem Push; Probe-Merge gegen vorzeige-url bei rundem Stand.

### Block A — Belegvertraege im Bestands-Scope von A-M4 (T24-05, T25-01, T25-03, T25-05), M-L
Klasse K2. Eine gemeinsame Rollenkonstante fuer P-B1 (heute drei
Aufzaehlungen: bestand_validate-CLI, vorbedingungen.erlaubt,
abnahmebericht.erlaubte_rollen); schichten/verankerung als Pflichtrollen des
Vollprofils und Pflichteingaben der Fuehrungsprobe, sobald der Fall eine
schichten.parquet fuehrt (ENTSCHEID 3). Fuehrungsprobe-Beleg: Katalog
Pflicht-positiv (vertraege, mit_anfangszustand, buchungen_geprueft),
Bindung von stichtag/generation/tarifwerk an den Fall, rollenscharfe
Suite-Bindung. Zugang: pruefe_am4_snapshot laesst Rollen-, Graph- und
Bytebindung durch dieselbe Pruefung wie das Gate beim Schreiben (oeffentliche
Zusammenfassung aus gate_entscheid, ENTSCHEID 2); jede kopierte Datei muss
unter den Snapshot-Belegen auffindbar sein. Producer-Familie
(fuehrungsprobe, verankerung_belegen, bestand_uebernehmen,
migrationssuite_lauf, aktuartest_lauf): lies_gehasht + *_aus_bytes fuer
JEDE gelesene Eingabe, Spez und alle Pfad-Flags im Provenienzblock; Ratsche
aus Block 1 auf diese Module ausweiten. Klassen-Tests: handgeschriebener
Beleg ohne Zahlen wird abgelehnt; Vollprofil mit Schichtrollen wird
angenommen; Dateitausch zwischen Lesung und Hash schlaegt fehl.
REGISTER-FALLE: neue Rollen vor dem Commit an merge-session melden.

### Block B — Konsumenten wiederholen den Vertrag im Betrieb (T24-03, T24-06, T24-04 Teil 1), M
Klasse K1. Ein gemeinsamer Nachweis-Helfer in tageslauf (gefuehrter_tag UND
stand_modell, letzte Zeile auch als In-Memory-Zeile); Seite und Paket rufen
ihn, bevor Manifest/Journal interpretiert werden. validate_eingang verlangt
snapshot_sha256 und gate == A-M4 / entscheid == angenommen;
zeichnung_aus_snapshot bekommt die validierten Daten statt eines zweiten
Lesevorgangs. T24-04 Teil 1 (Ableitung): Produzent liefert das Tagesjournal
(oder einen kanonischen Auszug) als vierten Beleg ins Paket
(dora-t24-t25); der Konsument leitet alle protokollgespeisten Felder aus
den Zeilen ab (werkzeuge/falldaten.py, VORZEIGE-AST nach deren Merge).
Klassen-Tests: gueltig neu geschriebenes Journal/Manifest wird von Seite
und Paket abgelehnt; jedes Eingang-Feld als abzulehnender Fall; jedes
stand.json-Feld einzeln mutiert.

### Block C — Verankerung des Pakets ausserhalb des Pakets (T24-04 Teil 2), M-L
Klasse K1, Verschaerfung. Nur zusammen mit Teil 1 wirksam (Kopplung, siehe
Abstimmung). Vier Formen zur Wahl (ENTSCHEID 1): Zeichnung jeder
Protokollzeile beim Lauf; Hash der letzten Zeile ausserhalb veroeffentlicht
(ein Anker bindet die Kette); Konsument prueft die Ablage statt des Pakets;
Zeichnung des Paketmanifests beim Export. Regressionstest liegt vor
(dora/test_paket_verankerung_t2404.py, rot bis zum Fix, wird MIT dem Fix
eingecheckt).

### Block D — Producer-Artefakte als Transaktion mit Registrierung (T25-04, T25-08, T25-11), L
Klasse K3. Producer bauen im .neu-Arbeitsverzeichnis und veroeffentlichen mit
EINEM rename (Vorbild eingang_anlegen) oder verweigern ein Zielverzeichnis
mit fremden Resten; Urteil VOR dem Schreiben (verankerung_belegen);
uebernahme.json bzw. ein Laufmanifest registriert JEDE geschriebene Datei
mit Hash, auch die optionalen; Konsumenten (cli_fortschreibung,
fuehrungsprobe, eingang_anlegen) lesen nur Registriertes. validate_schichten
prueft beide Richtungen; _schicht_fuer unterscheidet "fehlt" von
"unnoetig". A-Box: fail-closed bei unlesbarer Datei, atomarer Schreibpfad
(fall._schreibe_json), Sperre um Lese-Pruef-Schreib-Zyklus. P-B1 --manifest
verpflichtend (ENTSCHEID 7). Klassen-Tests: Rerun-Test (zweimal ins selbe
--out-dir), abgeschnittene abox.json, verankerte Police ohne Schicht.

### Block E — Bewertung und Fachzusagen (T24-02, T25-09, T25-06, N-01), M + Festlegung
Klasse K4. Abschluss-Schleife rechnet je Stichtag die gebuchte Sicht DIESES
Stichtags (T24-02; Fachkonzept Abschnitt 7 Punkt 6 praezisieren, ENTSCHEID
6). Finit-/Nachrechnungsspalten des Abschlusses aus ABSCHLUSS_SPALTEN
abgeleitet, an einer Stelle (T25-09). RED in Ereignis-Engine, Bewertung
und Ledger-Herleitung verdrahten (Praezedenz d13edf2); PEX-Absorption als
wertstetige Umwandlung = aktuarielle Festlegung (ENTSCHEID 4). Klassen-Test:
Schalter kippen, jeder der fuenf Konsumenten muss reagieren; Meldeverzug
ueber den Monatswechsel, Abschluss bytegleich ob sofort oder nachgeholt.
N-01 (diagnostiziert): tageslauf._wache reicht schichten/verankerung
nicht an die P-B1-Engine, die Herleitung rechnet ohne Korrekturschicht —
das Ledger ist richtig, die Wache falsch; Fix S (zwei bedingte Eintraege
wie fuer merkmale) plus Klassen-Test: jede optionale Tabelle, die
_stand_bauen nach arbeit schreibt, muss als Rolle in _wache auftauchen,
und ein STO eines uebernommenen Vertrags mit rho != 0 laeuft gruen durch
die Wache. Gehoert zu K1 (Konsument bekommt nicht dieselben Eingaben wie
der Produzent). Nachtrag: die kanonische Rollentabelle ROLLEN_DATEIEN
existiert und wird von vier Aufrufern nicht benutzt; _teilbestand/_bericht
lassen dieselben Rollen aus (gemessen: +13.700 EUR Deckungskapital je Vertrag mit Schicht im
Teilbestandsbericht, ohne dass der Bericht die Schicht nennt); dritte
Instanz: der Betriebseingang prueft die Vokabel der Nebentabellen nicht
(Fixture traegt 'POL', Kern stuerzt vier Schichten tiefer ab) -> Umfang
M, REIHENFOLGE: erst Vokabelpruefung am Eingang (gemeinsame Konstante in
models), dann Durchreichen, dann Bericht mit Schicht-Position, dann
AST-Ratsche gegen Rollen-Literale. Zweite Invariante: was der Betrieb an
Nebentabellen liest, wird gegen dieselbe Vokabel gehalten wie im Gate.
GEBAUT als Hotfix (hotfix-n01-betriebsweg 5ca0306, Entscheid des
Maintainers 2026-09-08; Testat der merge-session, dann Fast-Forward).

### Block F — Tageslauf als eine Transaktion (T24-01), L
Alles, was ein Lauf veroeffentlicht, zuerst in eine Generation im
Arbeitsverzeichnis; ein wiederaufnehmbarer Abschluss-Schritt mit
Write-Ahead-Marker bindet Journal, Symlink und Protokollzeile;
_verwaiste_staende_entfernen bricht bei fehlendem stand fail-closed ab;
vorhandener Abschluss wird mit pruefe_abschluss nachgerechnet statt
uebersprungen; _anfuegen in den Fehlerrahmen; dieselbe Fehlerinjektion
gegen neuaufsetzen (Doppel-Rename). Beruehrt das Fachkonzept (Block B4/B7,
ENTSCHEID 5).

### Block G — Eingang gegen den kuenftigen Namensraum (T24-08), M
Beim Anlegen des Eingangs jede police_id gegen die reservierten Baender ALLER
konfigurierten Nummernkreise halten (Richtung a) oder externer Namensraum
mit Mapping-Beleg (Richtung b) — ENTSCHEID 8. Klassen-Test: vorausberechnete
Neugeschaefts-ID als Zugang, alle drei Guards.

### Kleinkram im ersten Commit des Branches
T25-12 (Leerzeile am Ende von docs/faelle/baldrian-lauf2.md); Satz zur
Reichweite der AST-Ratsche in betrieb/_loeschen.py und offene-punkte.md.

## Entscheide des Maintainers (vor dem Bau)

1. T24-04 Verankerung: Angreifermodell (nur stand.json? ganze Ablage?) und
   Form (Zeichnung je Lauf / externer Anker der letzten Zeile / Ablage statt
   Paket / Paketmanifest-Zeichnung). Ableitung und Verankerung nur zusammen.
2. T24-05: gate_entscheid-interne Pruefroutinen (Rollen, Graph, Bytes) als
   oeffentliche, modulunabhaengige API fuer den Zugang.
3. T25-03: schichten/verankerung als Pflichtrollen des A-M4-Vollprofils
   (brechender Gate-Vertrag; neue Rollen -> Register auf vorzeige-url).
4. T25-06: PEX-Absorption als wertstetige Umwandlung (aktuarielle Regel);
   RED-Verdrahtung jetzt oder als eigener Auftrag.
5. T24-01: Umfang der Tageslauf-Transaktion (Fachkonzept B4/B7).
6. T24-02: Praezisierung "Bewertung zum Monatsersten" = gebuchte Sicht des
   Stichtags (Fachkonzept Abschnitt 7 Punkt 6).
7. T25-08: P-B1 --manifest verpflichtend; Laufmanifest fuer
   bestand_uebernehmen und verankerung_belegen.
8. T24-08: Ablehnung am Eingang (a) oder externer Namensraum (b).
9. Reihenfolge der Bloecke und ob alle auf dem einen Branch (Vorschlag:
   A, B+C, D, E, F, G — die Belegvertraege zuerst, weil sie die
   Neuzeichnung des Falls praegen).
10. N-01: ENTSCHIEDEN (Hotfix-Branch hotfix-n01-betriebsweg, 5ca0306,
    Testat, Fast-Forward nach main; dora-t24-t25 danach ab dem neuen
    main). Der Fall bleibt auf f7c545d gueltig, solange er nicht neu
    gefahren wird. Korrektur an den Reviewer (T25-05 nicht entfallen)
    in der naechsten Antwort.

## Abstimmung mit vorzeige-url (Branch vorzeige-url = 27016d1, Merge von main)

- Messpunkt: 27016d1 (Eltern 42cee24 + 10ee765, Suite 2027 passed / 3 Skips)
  — DORA-Aenderungen werden gegen diesen Stand nachgemessen.
- Paketvertrag (T24-04): das Paket spiegelt seit dem Merge die Ablage
  (seite/index.html statt index.html; test_werkzeuge_betrieb.py Zeile 63 auf
  vorzeige-url). Ein zusaetzlicher Beleg fuer buchungen/neugeschaeft oder ein
  Payload-Hash aendert das Paketformat — vor dem Bau abstimmen.
- Belegrollen-Register (Falle, gefunden von der merge-session): vorzeige-url
  fuehrt gates/register.py mit _BELEGROLLE_GATE; JEDE Rolle aus
  fall.BELEGROLLEN muss dort einem Gate zugeordnet sein, sonst
  RegisterFehler. main kennt die Datei nicht: eine neue Rolle (T25-03
  schlaegt schichten/verankerung als Pflichtrollen des A-M4-Vollprofils
  vor) ist auf main gruen und faellt erst beim Folge-PR um. Rollennamen
  vor dem Commit melden.
- T24-04, Aufteilung (merge-session, gelesen auf 27016d1): stand.json hat
  drei Quellen — Protokollzeile (stand, gefuehrt_seit, bestand,
  neugeschaeft.seit_betriebsbeginn, abschluesse, uebernahmen, verankerung,
  alle acht provenienz-Felder), Tagesjournal (geschaeftsentwicklung,
  buchungen.*, neugeschaeft.woche, woche_summe), Manifest (Horizont).
  Protokoll und Manifest liegen als Belege IM Paket, das Journal nicht.
  Folge: alles Protokollgespeiste ist ein reiner Konsumentenfix
  (werkzeuge/falldaten.py, vorzeige-Ast); die Produzentenfrage betrifft
  nur die journalgespeisten Bloecke (Journal oder Auszug als vierter Beleg).
- T24-04, Invariante (merge-session): die Protokollkette schuetzt die
  LETZTE Zeile nicht (kein Nachfolger bindet sie), und stand_modell leitet
  aus genau dieser Zeile ab; ein Payload-Hash in derselben Zeile zwingt den
  Faelscher zu nichts. "Das Paket muss an etwas gebunden sein, das nicht
  im Paket liegt." Anker-Kandidaten: A-M4-Snapshot-Hashes unter
  uebernahmen (Fall haelt die Snapshots), Systemstand, Zeichnungsordnung —
  Entscheid des Maintainers. Nachstellung durch die merge-session zugesagt.
- Korrekturbranch: dora-t24-t25 ab main 10ee765 (beiden Sessions gemeldet;
  Testat der merge-session vor dem Push; Probe-Merge gegen vorzeige-url
  bei rundem Stand angeboten und angenommen).

## Einzelbefunde

### T24-01 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (echter Code, `.venv/bin/python`, `tempfile.TemporaryDirectory`, keine Aenderung am Worktree), alle drei Fehlerpunkte des Reviewers einzeln:

1. *Fehler genau beim Standtausch, nach geschriebenem Journal* (`os.replace` gezielt nur beim Aufruf mit `ablage.stand` als Ziel, also `_uebernehmen()` Zeile 600, zum Absturz gebracht — alle vorherigen Schreibvorgaenge liefen real durch):
```
injizierter Lauf: exit=4 uebernommen=False fehler=OSError: [Errno 5] I/O error (injiziert genau am Symlink-Tausch)
  alter Stand noch aktiv: True
  Journal veraendert: True
  Monatsabschluss-Dateien nach dem injizierten Lauf: ['abschluss_2026-01-01.parquet', 'abschluss_2026-02-01.parquet']

  Retry (derselbe Tag erneut, ohne Fehlerinjektion):
  Retry verweigert (TageslaufError): Protokoll und Journal passen nicht zusammen: das Tagesjournal
  hat nicht den Hash, den die letzte gruene Zeile nennt — das Journal wurde veraendert oder
  gehoert zu einem anderen Stand
```
Exit-Code 4 = `EXIT_NACHLAUF` (tageslauf.py:147). Deckt sich wortgleich mit der Reviewer-Reproduktion 1 einschliesslich der Fehlermeldung. Der Lauf ist danach **dauerhaft** blockiert — auch ein sauberer, fehlerfreier Retry scheitert an `gefuehrter_tag()` (tageslauf.py:296-302), weil das bereits veraenderte Journal nicht mehr zur letzten gruenen Protokollzeile passt. Kein automatischer Ausweg im Code; nur manuelle Korrektur der Journaldatei.

2. *Monatsabschluss aus abgebrochenem Versuch wird stillschweigend akzeptiert* (Codebeweis, tageslauf.py:884-888):
```python
884  pfad = abschluss_pfad(ablage.abschluesse, stichtag)
885  if pfad.exists():
886      abschluesse.append({"stichtag": stichtag.isoformat(), "datei": pfad.name,
887                          "neu": False})
888      continue
```
`bestand.abschluss.pruefe_abschluss()` (Neuberechnung gegen den festgeschriebenen Stand, abschluss.py:168ff) wird von `tageslauf.py` **nirgends** aufgerufen (`grep -n "pruefe_abschluss" src/rechner_pipeline/betrieb/tageslauf.py` -> kein Treffer). Der harte No-clobber-Schutz von `schreibe_abschluss()` (abschluss.py:118-128: "bricht der Aufruf hart ab") wird also nicht getriggert, sondern durch die vorgelagerte `pfad.exists()`-Abfrage komplett umgangen — ein Abschluss aus einem technisch gescheiterten Lauf (mein Repro oben zeigt genau das: `abschluss_2026-02-01.parquet` steht bereits nach einem `exit=4`-Lauf) wird beim naechsten Versuch ungeprueft als gueltig uebernommen.

3. *Erstuebergang eines echten `stand/`-Verzeichnisses* (`os.rename` gezielt beim zweiten Aufruf in `_uebernehmen()`, Zeile 595, real ausgefuehrt und danach ein Absturz simuliert):
```
Zustand unmittelbar nach dem Absturz:
  ablage.stand existiert: False ist Symlink: False
  stand-* vor der Aufraeumung: ['stand-344a441a17f2af70', 'stand-erstfassung']
  gefuehrter_tag(ablage): None
  stand-* NACH _verwaiste_staende_entfernen() (isoliert, vor jedem Neubau): []
  ablage.stand existiert danach: False
```
Bestaetigt exakt: `_verwaiste_staende_entfernen()` (tageslauf.py:606-639) setzt `aktuell` nur, wenn `ablage.stand.is_symlink()` wahr ist (Zeile 620); existiert `stand` gar nicht (weder Symlink noch Verzeichnis — der Zustand nach diesem Absturz), bleibt `aktuell = None`, und die Schleife (Zeilen 633-635) loescht **jedes** `stand-*`-Verzeichnis, inklusive des alten `stand-erstfassung` UND der bereits fertig geschriebenen neuen Generation. Der Docstring von `_uebernehmen()` (Zeilen 569-571) raeumt das Fenster selbst ein: "nur dieser eine Uebergang hat noch das alte Fenster." Dass mein Nachlauf (isoliert, nur die eigentliche Neuberechnung) am Ende zufaellig denselben Verzeichnisnamen reproduzierte, ist ein Artefakt der Determinismus-Eigenschaft des Systems in diesem synthetischen Minimalfall (fixer RNG-Seed, keine Uebernahmen dazwischen) — kein Beleg fuer Ungefaehrlichkeit: `gefuehrter_tag()` sprang auf `None` zurueck, die gesamte Fuehrungshistorie wurde als "nie gefuehrt" behandelt, und die Monatsabschluss-Schleife (884-888) haette *jeden* frueher bereits festgeschriebenen Abschluss ungeprueft uebernommen (Punkt 2), statt ihn gegen den neu berechneten Ledger zu verifizieren.

4. *`_anfuegen()` ausserhalb des Fehlerblocks* (`_anfuegen` selbst zum Absturz gebracht, NACH erfolgreichem Standwechsel):
```
OSError bis ins Aufrufer-Level durchgereicht (nicht abgefangen): OSError(28, 'No space left on device ...')
  Stand nach dem Fehler zeigt auf: stand-0770166a55f3a7d0
  neuer Horizont im Stand: 2026-02-03
  Protokoll unveraendert (keine neue Zeile): True

  naechster Aufruf gefuehrter_tag():
  TageslaufError: Stand fuehrt 2026-02-03, das Protokoll 2026-01-31 — Stand und Nachweis passen nicht zusammen
```
Bestaetigt: der `try/except`-Block, der Fehler in eine rote Protokollzeile uebersetzt, endet bei Zeile 933; `_anfuegen(ablage.protokoll_pfad, zeile)` steht erst bei Zeile 946, ausserhalb — sogar ausserhalb des inneren `try/except` um `rendere_bestand_heute` (934-945). Ein Fehler dort propagiert unkontrolliert bis zur CLI (kein `except TageslaufError`-Fang in `main()` faengt ein rohes `OSError`), UND hinterlaesst einen Stand, der bereits den neuen Tag fuehrt, ohne jede Protokollzeile dafuer — der Folgeaufruf von `gefuehrter_tag()` bricht danach dauerhaft mit `TageslaufError` ab.

5. *Testschwaeche* (Codezeilen exakt wie vom Reviewer zitiert, `tests/test_betrieb_tageslauf.py:299-320`, seit 947dd76 unveraendert — `git log --oneline 947dd76..10ee765 -- tests/test_betrieb_tageslauf.py` ist leer): `monkeypatch.setattr(tl.os, "replace", _kaputt)` patcht `os.replace` global (dasselbe Modulobjekt in `sys.modules['os']`, auf das auch `bestand/parquet_io.py:156` und `bestand/manifest.py:117` zugreifen). Eigener Nachweis:
```
=== Testschwaeche: os.replace ist global, feuert vor dem eigentlichen Tausch ===
exit=2 fehler=OSError: Platte weg (Testmuster aus test_betrieb_tageslauf.py:311)
os.replace wurde 1x aufgerufen, bevor der Lauf abbrach
erster abgefangener Aufruf (Ziel): /tmp/.../plv/stand.neu/bestand.parquet
```
Der Fehler feuert beim allerersten `os.replace` innerhalb von `_stand_bauen()` (dem atomaren Parquet-Write, weit vor Journal und Standtausch) — der Test beweist den alten Stand bei einem fruehen, harmlosen Dateifehler, nicht am eigentlichen Commit-Punkt. Kein Test im aktuellen Repo trifft gezielt Zeile 600 (mein Repro 1/3 oben tut das erstmals). `tests/test_betrieb_datenverlust_t24.py` (neu seit 947dd76) und `tests/test_betrieb_neuaufsetzen.py` (neu) decken beide ausschliesslich das T24-07-Thema ab (rmtree-Zielgrenzen); keiner ihrer Tests injiziert einen Fehler zwischen zwei der fuenf externen Schreibnaehte von `_tageslauf`.

**Stand auf main 10ee765.** Unveraendert seit dem geprueften `cc55192`/`947dd76`. Die drei seither gelandeten `tageslauf.py`-Commits (`33452b5`, `d9f7566`, `1b904e0`) beheben ausschliesslich das eigenstaendige T24-07-Thema (rmtree loescht nur benannte Stand-/Arbeitsverzeichnisse; `_verwaiste_staende_entfernen` prueft jetzt seine Praemisse bei einem *haengenden Symlink*). Keiner dieser Commits aendert `_uebernehmen()`s Zwei-Rename-Fenster, den `_anfuegen()`-Aufrufort, oder den `pfad.exists()`-Kurzschluss der Monatsabschluesse. `d9f7566` behandelt zwar denselben Codeblock (`_verwaiste_staende_entfernen`), deckt aber nur den Fall "Symlink zeigt ins Leere" ab, nicht den vom Reviewer (und von mir reproduzierten) Fall "`stand` existiert ueberhaupt nicht" — diese Luecke bleibt eine echte Regression in der Abdeckung von `d9f7566`, nicht ihr Ziel.

**Schaden.** Ein gewoehnlicher, im Betrieb plausibler I/O-Fehler (volle Platte, Netzwerkspeicher-Haenger, Renderfehler in `betrieb.seite`) an einem von mehreren unverbundenen Commit-Punkten kann wahlweise: (a) den taeglichen Lauf **dauerhaft** blockieren (Retry schlaegt mit `TageslaufError` fehl, ohne automatischen Ausweg — ein reales Denial-of-Service der Bestandsfuehrung), (b) einen irreversiblen (0444) Monatsabschluss veroeffentlichen, der zu keiner gruenen Protokollzeile gehoert und beim naechsten Versuch ungeprueft als gueltig gilt, (c) beim einmaligen Uebergang von einem echten `stand/`-Verzeichnis in die Symlink-Form den kompletten bisherigen gefuehrten Bestand fuer die Startbereinigung des naechsten Laufs als "Waise" markieren und loeschen, (d) einen bereits erfolgreich uebernommenen Stand ohne zugehoerige Protokollzeile hinterlassen. Das Fachkonzept und der Modul-Docstring (Zeilen 50-54) versprechen ausdruecklich "Ein Absturz mitten im Lauf hinterlaesst den alten Stand" — genau das ist an mehreren, empirisch nachgewiesenen Stellen falsch.

**Schwere.** Zustimmung zu "hoch" — mit Tendenz zum oberen Rand der Kategorie. Alle vier Fehlerfenster sind mit einer einzelnen, realistischen Fehlerinjektion (ein `OSError`, keine exotische Race-Bedingung, kein Multi-Prozess-Timing) sofort und deterministisch ausloesbar; Fenster (a)/(b)/(d) fuehren zu einem dauerhaften, nur manuell behebbaren Systemzustand, und Fenster (c) betrifft nicht irgendeinen Randfall, sondern **den** Uebergang, den jede reale Produktivablage genau einmal durchlaeuft (echtes `stand/`-Verzeichnis -> Symlink-Form). Der Docstring des Codes selbst gibt das Fenster zu — die Luecke ist also nicht unentdeckt, sondern bewusst dokumentiert und ungeschlossen gelassen. Einschraenkend gegenueber "kritisch": kein Fenster fuehrt zu einer **stillen, unbemerkten** Datenverfaelschung des Bestands selbst (jeder Fall endet entweder in einer klar roten Zeile oder einem sofort erkennbaren `TageslaufError`) — der Schaden ist Verfuegbarkeits-/Nachweisintegritaet, nicht Bewertungskorrektheit. "Hoch" ist treffend.

**Klasse (Invariante).** Ein Vorgang, der mehrere extern sichtbare, einzeln bereits atomar/exklusiv geschuetzte Artefakte (hier: Monatsabschluss-Dateien, Tagesjournal, Stand-Symlink, Seite, Protokollzeile) im Rahmen EINES fachlich als "ein Lauf" verkauften Vorgangs nacheinander veroeffentlicht, ohne einen gemeinsamen Commit-/Rueckroll-Punkt, der alle diese Artefakte bindet, macht "der alte oder der vollstaendig neue Zustand bleibt nach einem Fehler bestehen" zu einer falschen Aussage, sobald der Fehler zwischen zwei dieser Einzelveroeffentlichungen eintritt — jede einzelne Atomaritaetsgarantie (No-clobber, `os.replace`, `os.rename`) schuetzt dann nur noch ihr eigenes Artefakt, nicht die Konsistenz der Gesamttransaktion.

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/betrieb/neuaufsetzen.py:188-190` (`os.rename(stand, archiv_ziel)` gefolgt von einem separaten `os.rename(neu_pfad, stand)`) — der Docstring des Moduls (Zeilen 24-30) benennt die Luecke selbst wortgleich zur hier gefundenen Klasse ("Zwischen den zwei Umbenennungen gibt es einen Moment OHNE Ablage") und mildert sie nur operativ ("Timer vorher anhalten"), nicht im Code. `tests/test_betrieb_neuaufsetzen.py` injiziert an dieser Naht keinen Fehler.
- `src/rechner_pipeline/betrieb/tageslauf.py:606-639` (`_verwaiste_staende_entfernen`) selbst: die von `d9f7566` neu eingefuehrte Praemissenpruefung deckt nur "Symlink zeigt ins Leere", nicht "`stand` existiert ueberhaupt nicht" — dieselbe Funktion enthaelt also nach der T24-07-Reparatur noch eine zweite, engere Instanz derselben Luecke.
- Gegenbeispiel (kein Fehler, zeigt aber die korrekte Alternative): `src/rechner_pipeline/betrieb/uebernahme.py:463-521` (`eingang_anlegen`) baut alle Dateien vollstaendig in einem `.neu`-Arbeitsverzeichnis (inkl. 0444-Schutz), bevor GENAU EIN `os.rename(arbeit, ziel)` (Zeile 521) das gesamte Artefakt auf einmal veroeffentlicht — das ist exakt das fehlende Muster fuer den Tageslauf als Ganzes.

**Fix-Umfang.** L. Eine lokale Korrektur einzelner Zeilen wuerde die Klasse nicht schliessen — noetig ist ein gemeinsamer Commit-Rahmen fuer den ganzen Lauf: (1) alles, was ein Lauf veroeffentlichen will (Monatsabschluesse, Tagesjournal-Delta, Stand-Manifest, Berichtsdateien), zunaechst vollstaendig in EINE benannte, selbstbeschreibende Generation innerhalb des Arbeitsverzeichnisses schreiben (nicht das bereits schreibgeschuetzte `bestand.abschluss`-Verzeichnis direkt treffen); (2) genau EIN abschliessender, wiederaufnehmbarer Schritt, der Journal-Anhang, Symlink-Tausch und Protokollzeile bindet — z. B. ein Write-Ahead-Eintrag ("Generation X beginnt Publish") vor dem ersten irreversiblen Schritt und ein Abschluss-Eintrag danach, so dass ein Retry anhand dieses Markers entscheiden kann, ob er fortsetzen oder verwerfen muss, statt wie heute stumpf `TageslaufError` zu werfen; (3) `_verwaiste_staende_entfernen()` muss bei JEDER Unklarheit ueber `aktuell` (nicht nur beim haengenden Symlink, sondern auch beim komplett fehlenden `stand`) fail-closed abbrechen statt `aktuell=None` als "alles ist Waise" zu interpretieren; (4) die Monatsabschluss-Schleife muss bei einem bereits vorhandenen Abschluss `pruefe_abschluss()` statt eines blinden `neu=False`-Kurzschlusses aufrufen; (5) `_anfuegen()` gehoert in denselben Fehlerbehandlungs-Rahmen wie der Rest des Laufs, mit einem eigenen, benannten Fehlerfall statt eines unbehandelten `OSError`-Durchreichens. Fangender KLASSEN-Test: ein parametrisierter Fehlerinjektionstest, der NICHT global `os.replace`/`os.rename` patcht, sondern gezielt (wie in meinen vier Repros oben) jede der fuenf Commit-Naht-Stellen einzeln zum Absturz bringt (Monatsabschluss-Schreiben, Journal-Schreiben, `_uebernehmen`-Rename-1, `_uebernehmen`-Rename-2/Symlink, `_anfuegen`) und nach jedem Fall verlangt: entweder der alte Stand ist vollstaendig funktionsfaehig UND ein sauberer Retry gelingt, oder der neue Stand ist vollstaendig uebernommen UND Protokoll/Journal/Abschluesse sind konsistent — nie ein dauerhaft blockierter Zustand. Dieselbe Fehlerinjektions-Fixture sollte auch gegen `neuaufsetzen.py:188-190` laufen. Der Fix aendert das On-Disk-Layout/Recovery-Verhalten einer bereits als produktionsnah beschriebenen Komponente (Freischaltung Schritt 9 ist bereits gelandet) — das beruehrt keinen Gate-Vertrag und kein Pydantic-Schema, aber sehr wohl das Fachkonzept (`docs/simulation/tagesbetrieb.md`, Block B4/B7) und ist ein Entscheid des Maintainers wert, bevor er umgesetzt wird (Umfang und Breaking-Charakter vergleichbar mit den bereits als `!`-Commits gelandeten T24-07-Reparaturen).

### T24-02 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (echter Code, `.venv/bin/python`, `tempfile.mkdtemp`, keine Aenderung am Worktree, Reproduktionsskript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t24-02/repro.py`).

Codepfad (heutige Zeilen): `_stand_bauen()` (`tageslauf.py:334`) ruft `gebuchte_sicht(config, historie, ledger, scheiben_fort, heute, ab_tag=betriebsbeginn)` genau **einmal** auf (`tageslauf.py:417-418`, Kommentar "Tag = Sicht (Review T22-04)" direkt darueber, `:413-416`). `_wache()` (`:497-510`) liest fuer `tabellen` ausschliesslich die bereits so gefilterten Bytes aus `arbeit/*.parquet` zurueck — es gibt keine zweite, ungefilterte Sicht mehr. Die Abschluss-Schleife in `_tageslauf()` (`:880-916`) iteriert `stichtage = monatserste_in(letzter or betriebsbeginn-1, heute)` und uebergibt fuer JEDEN dieser Monatsersten dasselbe `tabellen["historie"]`/`["ledger"]`/`["scheiben"]` an `schreibe_abschluss()` (`:889-893`, Aufruf identisch zu `bestand/abschluss.py:104` -> `_rechne()` -> `einzelwerte_am(stamm, historie, config, stichtag, ...)`, `bestand/auswertung.py:232`). Das fuer den letzten `stichtag` zusaetzlich gerenderte HTML (`_bericht()`, `:898-904`, Funktion `:685-709`) erbt dieselbe Verzerrung.

Eigene Reproduktion (PLV-Config, `sample_size` je Generation auf 100 reduziert wie beim Reviewer, `betriebsbeginn = 2026-01-01`, Rest unveraendert): Basislauf bis 2027-12-30 liefert einen natuerlichen Fall, **Police 70000019**, TOD mit Wirkungstag `2027-02-01` (Monatserster, programmatisch verifiziert) und Buchungstag `2027-03-30` (Meldeverzug).

```
Fruehlauf  = tageslauf(frueh, 2027-02-01)      exit=0
Nachhollauf = tageslauf(nachgeholt, 2027-03-30) exit=0   (ein Lauf, holt seit
                                                           Betriebsbeginn alles nach)

Vergleich abschluss_2027-02-01.parquet:
  bytegleich: False
  sha256 frueh     : 13550e30...552f5a
  sha256 nachgeholt: 9872ae06...aec8a95
  Police 70000019 im FRUEHEN Abschluss:      vorhanden, status_code=POL,
      leistung=35886.375, deckungskapital=16794.002493
  Police 70000019 im NACHGEHOLTEN Abschluss: NICHT vorhanden
  Zeilen frueh=739 nachgeholt=738
  nur in frueh (nicht in nachgeholt): [70000019]
  nur in nachgeholt (nicht in frueh): []
  weitere Abweichungen bei den 738 gemeinsamen Policen: 0
```

Beide Laeufe sind Exit 0, beide "gruen" (P-B1 unauffaellig), beide schreiben denselben `abschluss_2027-02-01.parquet`-Dateinamen 0444-festgeschrieben — mit unterschiedlichem Inhalt. Der Effekt ist exakt isoliert auf die eine Police mit ueber den Monatswechsel laufendem Meldeverzug, keine Fremdabweichung. Das deckt sich in Mechanik und Vorzeichen (frueh: Police lebt noch; nachgeholt: Police fehlt, weil `einzelwerte_am` sie am Stichtag als bereits verstorben/ausgeschieden behandelt) mit der Reviewer-Reproduktion (Police 120000089, TOD `2026-05-01`/Buchung `2026-05-06`, "Police darin ja" vs. "nein").

`gebuchte_sicht()` selbst ist korrekt und isoliert getestet (`tests/test_betrieb_tagesjournal.py:384-421`) — der Fehler liegt nicht in der Funktion, sondern darin, dass die Orchestrierung sie nur einmal mit `heute` statt je Stichtag mit dem Stichtag selbst aufruft.

**Stand auf main 10ee765.** Unveraendert. `git log --oneline 947dd76..10ee765 -- src/rechner_pipeline/betrieb/tageslauf.py` zeigt drei Commits (`33452b5`, `d9f7566`, `1b904e0`); der Diff betrifft ausschliesslich `_entferne_ablageverzeichnis`/`_verwaiste_staende_entfernen` (T24-07-Thema) sowie neue Verankerung/Bausteine/Korrekturschicht-Parameter (Freischaltung Schritt 9) rund um den `gebuchte_sicht()`-Aufruf — der Aufruf selbst (`historie, ledger, scheiben = gebuchte_sicht(config, historie, ledger, scheiben_fort, heute, ab_tag=betriebsbeginn)`) ist inhaltlich identisch zur Fassung auf `947dd76` (dort Zeile 400), nur um vier Zeilen verschoben. Die Abschluss-Schleife (`947dd76` Zeile 782 `schreibe_abschluss`, `:774-786` beim Reviewer zitiert) liegt komplett ausserhalb aller Diff-Hunks — 0 Byte Aenderung seit dem Befund. `tests/test_betrieb_tageslauf.py` ist seit `947dd76` ueberhaupt nicht angefasst worden (`git log` leer); `test_nachholen_ergibt_denselben_stand_wie_jede_nacht` steht bei den vom Reviewer zitierten Zeilen 151-171 unveraendert und faehrt `31.01./03.02./04.02.` gegen `04.02.` direkt — kein Meldeverzug, kein Ereignis, das einen Monatsersten kreuzt. `deploy/plv/README.md:67-70` (die zitierte Zusage "der Stand ist derselbe, als haette der Lauf jede Nacht stattgefunden") ist ebenfalls unveraendert (Datei seit `947dd76` nicht beruehrt). Die gleiche Zusage steht wortgleich im Fachkonzept, `docs/simulation/tagesbetrieb.md:227-230` und Punkt 6, `:242-248` ("Bewertung zum Monatsersten, festgeschrieben, 0444, nie ueberschrieben").

**Schaden.** Ein irreversibler (0444, ADR-011), als Bilanzwert eines konkreten Kalendertags ausgewiesener Monatsabschluss haengt fuer jede Police mit einem Ereignis, dessen Buchungstag ueber den Monatswechsel faellt (in der PLV-Config in erster Linie TOD mit Meldeverzug: Median 14 Tage, p95 60 Tage, `configs/bestand_gesamt.toml:1101`), davon ab, ob der Tagesbetrieb genau am Monatsersten lief oder erst spaeter nachgeholt wurde — beide Faelle liefern Exit 0 und ein gruenes P-B1-Urteil, es gibt keinerlei Warnhinweis. Der Fachkonzepttext verspricht ausdruecklich das Gegenteil ("derselbe Stand, als haette der Lauf jede Nacht stattgefunden"). Da niemand automatisch `pruefe_abschluss()` gegenrechnet (bestaetigt in T24-01), bleibt die Verzerrung dauerhaft unentdeckt, solange kein Mensch von Hand nachrechnet — und selbst dann wuerde eine Abweichung eher der "Kern-Version geaendert"-Erklaerung aus `pruefe_abschluss()` zugeschrieben als der eigentlichen Ursache.

**Schwere.** Zustimmung zu "hoch". Es handelt sich um eine stille Verfaelschung eines bereits festgeschriebenen, aktuariell verbindlichen Bilanzwerts (nicht nur eine Verfuegbarkeits- oder Nachweisluecke wie bei T24-01) — beide Laeufe melden Erfolg, kein roter Zustand signalisiert das Problem. Einschraenkend gegenueber "kritisch": (a) der Effekt ist scharf auf die konkret betroffene(n) Police(n) begrenzt (meine Reproduktion zeigt exakt eine abweichende Zeile unter 739, keine Streuung in andere Werte); (b) das Ausloese-Fenster ist an die Meldeverzugs-Verteilung gekoppelt — ein einzelner, wenige Stunden bis 1-2 Tage kurzer Nachlauf trifft nur den schnell gebuchten Teil der Verteilung, waehrend ein laengerer Ausfall (mehrere Wochen, laut Konzept explizit als "kostet nichts als Rechenzeit" unterstuetztes Szenario) den Median-Fall zuverlaessig trifft; (c) der Fehler ist im Prinzip nachtraeglich aufdeckbar (eine manuelle Neuberechnung mit korrektem Buchungs-Cutoff wuerde ihn zeigen), nur eben nicht automatisch. In Summe rechtfertigt das "hoch", ich sehe keinen Grund fuer eine Herabstufung und auch keine zwingende Notwendigkeit fuer "kritisch".

**Klasse (Invariante).** Jede Festschreibung eines Bewertungsstands zu einem FIXEN vergangenen Stichtag (Monatsabschluss, der zugehoerige Bestandsbericht, jeder weitere aus derselben Tabelle abgeleitete Bericht) muss mit der gebuchten Sicht DIESES Stichtags gerechnet werden (Buchungs-Cutoff = Stichtag), nicht mit der gebuchten Sicht des tatsaechlichen Rechenlaufs — sobald ein Filterkriterium, das eigentlich an den Stichtag gebunden sein muesste, stattdessen einmalig an den spaeteren, laufabhaengigen "heute"-Zeitpunkt gebunden und fuer mehrere unterschiedliche Stichtage wiederverwendet wird, wird das Ergebnis vom Zufall des tatsaechlichen Ausfuehrungszeitpunkts abhaengig statt vom fachlichen Stichtag.

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/betrieb/tageslauf.py:898-904` (`_bericht()`-Aufruf fuer `stichtage[-1]`, Funktion `:685-709`) — der Bestandsbericht (HTML) fuer den zuletzt nachgeholten Monatsersten wird aus genau demselben `tabellen`, also derselben heute-gefilterten Sicht gerendert; die Verzerrung erscheint damit nicht nur im Parquet-Abschluss, sondern auch im menschenlesbaren Bericht.
- `src/rechner_pipeline/betrieb/tageslauf.py:905-915` (Teilbestand-Berichte je Uebernahme) — dieselbe `tabellen`-Quelle, derselbe Effekt fuer jeden Teilbestandsbericht.
- Verwandtes, aber nicht identisches Risiko (nicht als eigener Fund gezaehlt): `src/rechner_pipeline/bestand/cli_abschluss.py:150-224` ist als generischer Producer bewusst zustandslos bezueglich Buchungstagen — er vertraut darauf, dass `historie`/`ledger` des uebergebenen `--lauf`-Bundles bereits die fuer den Stichtag richtige Sicht tragen. Ein Mensch, der ihn im "Betriebsweg" (Konzept, Abschnitt 6, "Stand ab Betriebsbeginn neu fahren") manuell retroaktiv gegen die aktuelle PLV-`stand/`-Ablage aufruft, erbt dieselbe Fehlannahme, weil `stand/historie.parquet` immer die zuletzt gebuchte Sicht traegt — das ist aber ein Bedienrisiko am selben Vertrag, kein Code-Duplikat des Fehlers.
- Gesucht und nicht gefunden: eine zweite Stelle, die `gebuchte_sicht()` selbst fuer mehrere unterschiedliche Stichtage mit demselben `heute` aufruft (Suchmuster `gebuchte_sicht(` reposeitig, drei Treffer: die Definition selbst, der eine Aufruf in `tageslauf.py:417`, und der isolierte Unit-Test) — der Fehler steckt an genau einer Orchestrierungsstelle, nicht verteilt.

**Fix-Umfang.** M. `_stand_bauen()` muesste die volle, nur um die Vorgeschichte (`ab_tag`) bereinigte Wirkungssicht (historie/ledger/scheiben VOR dem `gebuchte_sicht()`-Aufruf `:417-418`) zusaetzlich zurueckgeben bzw. ablegen — heute wird nur das bereits gefilterte Ergebnis nach `arbeit/*.parquet` geschrieben und ist danach die einzige verfuegbare Quelle. Die Abschluss-Schleife in `_tageslauf()` (`:880-916`) muesste fuer jeden `stichtag` `gebuchte_sicht(config, historie_voll, ledger_voll, scheiben_voll, stichtag, ab_tag=betriebsbeginn)` selbst aufrufen und deren Ergebnis (nicht `tabellen["historie"]`) an `schreibe_abschluss()` UND `_bericht()`/Teilbestandsberichte uebergeben; die P-B1-Wache und die Tagesseite bleiben unveraendert auf der `heute`-Sicht, das ist dort korrekt. Fangender KLASSEN-Test: ein parametrisierter Test in `tests/test_betrieb_tageslauf.py`, der ein Ereignis mit erzwungenem Meldeverzug ueber einen Monatswechsel konstruiert (z. B. `meldeverzug_tage` monkeypatchen oder — wie im Repro hier — einen echten, im Datensatz vorkommenden Fall suchen) und verlangt, dass `abschluss_<Monatserster>.parquet` bytegleich ist, unabhaengig davon, ob er sofort oder erst nach N Tagen Nachholen erzeugt wird — genau das vom Reviewer geforderte Abnahmekriterium. Beruehrt: keinen Gate-Vertrag und kein Pydantic-Schema (P-B1 bleibt unveraendert), aber den internen Datenfluss-Vertrag von `_stand_bauen()`/`_tageslauf()` und die Praezisierung von `docs/simulation/tagesbetrieb.md` Abschnitt 7 Punkt 6 ("Bewertung zum Monatsersten" muss die STICHTAGS-eigene gebuchte Sicht meinen) — damit ein Entscheid des Maintainers wert, vom Umfang vergleichbar mit den bereits als `!`-Commits gelandeten T24-07-Reparaturen.

### T24-03 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (echter Code, `.venv/bin/python` aus dem Worktree, `tempfile.TemporaryDirectory`, keine Aenderung am Worktree; Skript unter `.../scratchpad/t24-03/repro.py`). Ein echter gruener Tageslauf wurde gebaut (`tageslauf(ablage, 2026-02-03)` -> `EXIT_OK`), danach der Betrag der ersten Journalzeile veraendert und `write_portfolio()` (gueltiger Parquet-Schreibpfad, kein kaputtes Byte) erneut geschrieben:

```
letzte gruene Zeile nennt Journal-Hash: de9ac5e1b0f7560e ...
erste Journalzeile vorher, betrag: 0.0
erste Journalzeile nachher, betrag: 999999.0
stand_modell akzeptiert manipuliertes Journal: True
Seitenmodell zeigt veraenderten Betrag in 'buchungen': True
Seitenmodell (ueber Protokollzeile) behauptet weiter alten Journal-Hash: True
gefuehrter_tag auf derselben Ablage: TageslaufError
  Meldung: Protokoll und Journal passen nicht zusammen: das Tagesjournal hat
  nicht den Hash, den die letzte gruene Zeile nennt — das Journal wurde
  veraendert oder gehoert zu einem anderen Stand
Kontrollpruefung (gefuehrter_tag/_pruefe_nachweis) lehnt genau dieses Journal ab: True
```

Deckt sich wortgleich mit der Reviewer-Reproduktion inklusive Fehlermeldung.

Codebeweis (heutige Zeilen, Reviewer-Zeilen 97-108/109-135/tageslauf 230-309 treffen bis auf einen Ein-Zeilen-Versatz — verursacht durch einen zusaetzlichen Import in `1b904e0`/`33452b5` — exakt denselben Block):
- `betrieb/seite.py:98-109` (`stand_modell()`): prueft ausschliesslich `manifest["horizont"] == heute` (Zeile 105), vergleicht nie `manifest_sha256` oder den Journal-Hash gegen die letzte gruene Protokollzeile.
- `betrieb/seite.py:110-135`: liest das Journal direkt per `read_portfolio(ablage.tagesjournal_pfad, ...)`, ohne jede Hashpruefung.
- `betrieb/seite.py:98-109`/`110-135` rufen weder `gefuehrter_tag()` noch `_pruefe_nachweis()` auf; `grep -n "gefuehrter_tag\|_pruefe_nachweis" src/rechner_pipeline/betrieb/seite.py` liefert keinen Treffer.
- `betrieb/tageslauf.py:230-273` (`_pruefe_nachweis`) und `:277-309` (`gefuehrter_tag`) sind exakt die Funktionen, die Manifest- und Journalhash gegen die letzte gruene Zeile haelt — unveraendert seit `947dd76`.
- Beide vorgesehenen Konsumenten haengen an derselben ungeprueften Funktion: `rendere_bestand_heute()` (`seite.py:373-376`) ruft `stand_modell(ablage, aktuelle_zeile)` auf, `stands_paket()` (`seite.py:421-437`) ruft `stand_modell(ablage)` auf; `main()` (`seite.py:476-496`, der direkte CLI-Aufruf `python -m rechner_pipeline.betrieb.seite --stand ...`) ruft beide ohne vorherigen `gefuehrter_tag()`-Aufruf auf — es faengt sogar `TageslaufError` ab (Zeile 493), obwohl dieser Fehlertyp auf diesem Pfad nie ausgeloest werden kann, weil die Funktion, die ihn wirft, nie aufgerufen wird.
- `stands_paket()` uebernimmt `modell["buchungen"]`/`modell["bestand"]` unveraendert in `stand.json` (`modell["dateien"]`/`_schreibe(ziel / PAKET_DATEI, ...)`, `seite.py:465-467`) — die manipulierten Kennzahlen landen damit auch in der "oeffentlichen, gestempelten" Sicht. Verschaerfend: das Paket kopiert zwar Protokoll und Manifest als Belege hinein (Kommentar Zeile 462f: "der Konsument haelt stand.json dagegen, statt dem Wort 'gruen' zu glauben"), aber NICHT das Tagesjournal selbst — ein Paket-Konsument kann die journalabgeleiteten Kennzahlen also nicht einmal nachtraeglich gegen einen mitgelieferten Beleg pruefen.

**Stand auf main 10ee765.** Unveraendert seit dem geprueften `947dd76`. `git log --oneline 947dd76..10ee765 -- src/rechner_pipeline/betrieb/seite.py` zeigt zwei Commits (`33452b5`, `1b904e0`); `git diff 947dd76 10ee765 -- .../seite.py` zeigt, dass beide ausschliesslich das eigenstaendige T24-07-Thema betreffen (`paketziel_fehler()`/`entferne_verzeichnis()` fuer das Loeschziel von `stands_paket`) — `stand_modell()`, `rendere_bestand_heute()` und `main()` sind byte-identisch zum geprueften Stand. `git log --oneline 947dd76..10ee765 -- src/rechner_pipeline/betrieb/tageslauf.py` zeigt zusaetzlich `d9f7566`; dessen Diff betrifft ausschliesslich `_verwaiste_staende_entfernen()` (Zeilen 606ff, T24-07), nicht `_pruefe_nachweis()`/`gefuehrter_tag()` (230-309), die unangetastet blieben.

**Schaden.** Wer Schreibzugriff auf die Ablage hat (dieselbe Berechtigung, die der taegliche Tageslauf ohnehin braucht — kein zusaetzliches Privileg noetig), kann das Tagesjournal nach einem gruenen Lauf veraendern und sowohl die interne Seite (`daten/seite/index.html`, von Caddy read-only ausgeliefert) als auch das exportierte Stands-Paket (`stand.json`, Quelle der Vorzeigeseite `werkzeuge/falldaten.py --stands-paket`) weiterhin als P-B1-gruenen, nachweisgebundenen aktuellen Bestand ausgeben lassen — mit den manipulierten Buchungen/Kennzahlen. Der tatsaechliche Schutzmechanismus (`gefuehrter_tag()`/`_pruefe_nachweis()`) erkennt genau diesen Widerspruch zuverlaessig, wird aber von beiden Darstellungswegen nie aufgerufen. Der naechste ECHTE Tageslauf wuerde zwar mit `TageslaufError` blockieren (kein stiller Dauerschaden am gefuehrten Bestand selbst), aber bis dahin — Stunden bis zu einem Tag — zeigen genau die Kanaele, die laut Fachkonzept (`docs/simulation/tagesbetrieb.md`, Abschnitt 8.3) fuer Sichtung/Veroeffentlichung gedacht sind, einen falschen, als gepruefte gruen dargestellten Bestand.

**Schwere.** Zustimmung zu "hoch". Der Vertrag existiert bereits vollstaendig und geprueft im Code (`_pruefe_nachweis`, seit T22-05 mit eigenem Regressionstest in `tageslauf.py` selbst verankert) — es fehlt nicht an Mechanismus, sondern ausschliesslich am Aufruf an den zwei Stellen, die genau fuer die Darstellung/den Export zustaendig sind. Das ist keine theoretische Randstelle: Es ist der einzige Codepfad, ueber den ein Mensch (interne Seite) oder ein externes Werkzeug (Vorzeige-Paket) den aktuellen Bestand ueberhaupt zu sehen bekommt. Einschraenkend gegenueber "kritisch": der authoritative `stand/`-Datenbestand selbst und die naechste reale Fortschreibung sind geschuetzt (der Fehler wirkt nur auf die Anzeige/den Export, nicht auf die Buchungslogik), und der Widerspruch wird beim naechsten echten Lauf sicher aufgedeckt (kein dauerhaftes stilles Verschwinden des Fehlers).

**Klasse (Invariante).** Wenn ein System einen Nachweisvertrag (hier: Protokollkette + letzte gruene Zeile + Manifest-/Journalhash) an EINER Stelle (`_pruefe_nachweis`/`gefuehrter_tag`) implementiert und durchsetzt, schuetzt dieser Vertrag nur die Aufrufer, die ihn tatsaechlich durchlaufen — jede weitere Funktion, die dieselben Rohdaten (Manifest, Journal) eigenstaendig von der Platte liest, um daraus eine "gepruefte"/"gruene" Aussage abzuleiten, muss denselben Pruefaufruf explizit wiederholen, sonst ist "durch P-B1/den Nachweisvertrag gedeckt" nur noch wahr fuer den einen Pfad, der den Vertrag aufruft, und falsch fuer jeden Konsumenten, der die Bytes bloss erneut liest.

**Weitere Stellen mit demselben Muster.** Keine weiteren produktiven Stellen gefunden: `grep -rn "stand_modell(\|stands_paket("` in `src/` zeigt, dass beide vorgesehenen Konsumenten (`rendere_bestand_heute`, `stands_paket`) ausschliesslich innerhalb von `seite.py` selbst auf dieselbe eine ungeprueften Funktion `stand_modell()` treffen — es gibt keine dritte, unabhaengige Instanz derselben Direktlese-Luecke. Geprueft und als andere Klasse ausgeschlossen: `betrieb/tageslauf.py:841-842` liest das Journal ebenfalls direkt, aber NACH dem `gefuehrter_tag()`-Aufruf bei Zeile 785 desselben Laufs (korrekt sequenziert); `betrieb/tageslauf.py:508` (`_wache`, `lies_manifest(arbeit)`) liest das Manifest eines noch nicht veroeffentlichten Arbeitsverzeichnisses (Produzenten-Selbstpruefung vor Publish, keine Konsumenten-Behauptung ueber einen bereits committeten Stand); `bestand/cli_abschluss.py:155` (`lies_manifest(lauf)`) validiert im Fall-Migrationskontext eigenstaendig per P-B1-Engine gegen das Manifest desselben Laufverzeichnisses — ein anderer Vertrag (keine Protokollkette einer laufenden Betriebs-Ablage), daher keine Instanz derselben Klasse. Das separat im Bericht genannte `stand.json`-Bindungsproblem (T24-04: veroeffentlichte Kennzahlen an keinen mitgelieferten Beleg gebunden) ist verwandt, aber mechanisch verschieden (fehlende Bindung im Export-Format selbst, nicht ein ausgelassener Pruefaufruf) und nicht Teil dieser Pruefung.

**Fix-Umfang.** M. Kein Ein-Zeilen-Patch pro Konsument, weil beide Konsumenten (`rendere_bestand_heute`, `stands_paket`) durch dieselbe Funktion laufen und weil der Sonderfall der noch nicht angefuegten In-Memory-Zeile (`aktuelle_zeile`-Parameter, aus `tageslauf.py:940-943`) denselben Vertrag ohne Protokoll-Append-Umweg braucht. Konkreter Vorschlag: `stand_modell()` baut sich analog zu `gefuehrter_tag()` die Liste der gruenen Zeilen (inklusive der optionalen `aktuelle_zeile`) und ruft `_pruefe_nachweis(ablage, gruene)` auf, BEVOR Manifest/Journal fuer den Rueckgabewert interpretiert werden; `_pruefe_nachweis` muss dafuer so erweiterbar sein, dass die letzte Zeile auch die noch nicht persistierte In-Memory-Zeile sein darf (das Abnahmekriterium des Reviewers verlangt das explizit). Am saubersten als EIN gemeinsamer Helfer (z. B. `nachweis_pruefen(ablage, zeilen)` in `tageslauf.py`, von `gefuehrter_tag()` UND `stand_modell()` genutzt), damit nicht zwei Implementierungen desselben Vertrags auseinanderlaufen. Fangender KLASSEN-Test: ein parametrisierter Test in `tests/test_betrieb_seite.py`, der nach einem echten gruenen Lauf (a) das Journal, (b) das Manifest jeweils gueltig neu schreibt (kein kaputtes Byte, wie in meiner Reproduktion) und verlangt, dass sowohl `stand_modell()`/`rendere_bestand_heute()` als auch `stands_paket()` mit einem benannten Fehler ablehnen, nicht die veraenderten Daten rendern/exportieren; zusaetzlich ein Test fuer den In-Memory-Fall (aktuelle Zeile vs. bereits getauschtes Manifest). Beruehrt keinen Gate-Vertrag/kein Pydantic-Schema, aber eine bereits als produktionsnah beschriebene Komponente (Freischaltung Schritt 9 ist gelandet, `docs/simulation/tagesbetrieb.md` Abschnitt 8.3 verspricht "Automatisch veroeffentlicht wird nichts, was nicht durch P-B1 ging") — Umfang und Verhaltensaenderung sind vergleichbar mit den bereits als `!`-Commits gelandeten T24-07-Reparaturen und sollten vor Umsetzung vom Maintainer entschieden werden (insbesondere die Frage, ob `_pruefe_nachweis` refaktoriert/gemeinsam genutzt oder nur an den zwei Konsumenten dupliziert wird).

### T24-04 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (echter Code, `.venv/bin/python`, `tempfile.mkdtemp`, echter `tageslauf()`-Lauf ueber `configs/bestand_gesamt.toml`, keine Aenderung am Worktree — Skript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t24-04/repro.py`):

```
echtes Paket erzeugt unter: /tmp/t24-04-doqfs4ty/paket
urspruenglich bestand.in_force 68
urspruenglich buchungen.gesamt 19
Kontrolle (unveraendert) akzeptiert: vorhanden=True
publiziert bestand.in_force 999999
publiziert buchungen.gesamt 888888
erfundene Uebernahme akzeptiert
luecken = [] akzeptiert
falldaten.betrieb vorhanden=True, kein Fehler
```
Nur `stand.json` wurde geaendert; `protokoll.jsonl`, `laufmanifest.json`, `index.html`, `bestandsbericht_*.html` und deren Hashes in `stand.json["dateien"]` blieben unangetastet. Deckt sich wortgleich mit der Reviewer-Reproduktion.

Codebeweis, heutige Zeilen (Reviewer zitierte 383-420/894-949/973-989 gegen 947dd76; `betrieb/seite.py` bekam seither zwei Commits — `33452b5`, `1b904e0` — die ausschliesslich das Loeschziel bzw. Schritt 9 betreffen, `stand_modell()`/`stands_paket()` selbst unveraendert; `werkzeuge/falldaten.py` ist laut `git diff 947dd76 10ee765 -- werkzeuge/falldaten.py` byte-identisch, die Zeilenverschiebung ~894->922 ist eine reine Zaehldifferenz des Reviewers):

1. `src/rechner_pipeline/betrieb/seite.py:151-181` (`stand_modell`, Rueckgabedict) — `bestand` (157), `uebernahmen` (169) und `verankerung` (170) werden **woertlich** aus `zeile["bestand"]`/`zeile.get("uebernahmen")`/`zeile.get("verankerung")` uebernommen, also aus der bereits kettengeprueften Protokollzeile; `abschluesse` (168) wird aus allen uebernommenen Protokollzeilen aggregiert (138-150); `buchungen`/`neugeschaeft` (163-167, 158-162) werden dagegen frisch aus dem Tagesjournal (`ablage.tagesjournal_pfad`) berechnet — einer Datei, die **nie** ins Paket kopiert wird.
2. `src/rechner_pipeline/betrieb/seite.py:472` — `modell` (das komplette obige Dict) wird ungeprueft als `stand.json` geschrieben; `dateien` (450-469) traegt nur Hashes fuer kopierte Zusatzdateien (Berichte, `index.html`, `protokoll.jsonl`, `laufmanifest.json`) — keine fuer `bestand`/`buchungen`/`abschluesse`/`uebernahmen`/`verankerung`/`provenienz` selbst.
3. `werkzeuge/falldaten.py:922-977` (`_pruefe_stands_paket`) laedt bereits `zeilen = lies_protokoll(...)` (950) und `letzte` (956) — beide kettengeprueft, mit `bestand`, `uebernahmen`, `verankerung`, `abschluesse`, `config_sha256`, `kern_version`, `image_digest/-revision/-tag` bereits als Schluessel vorhanden (empirisch bestaetigt, siehe unten) — vergleicht davon aber nur `letzte.get("heute")` (957), `letzte.get("pb1")` (961f.), `letzte.get("manifest_sha256")` (968) und `letzte.get("tagesjournal",{}).get("sha256")` (975f., rein selbstreferentiell zwischen zwei JSON-Feldern, da keine Journal-Belegdatei existiert). Der Docstring (925-932) benennt selbst nur diese vier Pruefungen.
4. `werkzeuge/falldaten.py:1001-1018` (`betrieb()`) gibt `stand.get("bestand")` (1005), `neugeschaeft` (1006), `buchungen` (1007-1010), `abschluesse` (1011), `uebernahmen` (1012), `provenienz` (1013, komplett) und `luecken` (1016) direkt weiter.

Zusatzbeleg (zweites Skript, gleiche Methode): Die letzte gruene Protokollzeile traegt tatsaechlich `bestand={'in_force': 68, ...}`, `uebernahmen=[]`, `verankerung={'angewandt': False, ...}`, `config_sha256`, `kern_version`, `image_digest/-revision/-tag` — alles bereits im Speicher von `_pruefe_stands_paket`, aber ungenutzt. `buchungen` und `neugeschaeft` fehlen dagegen in der Protokollzeile vollstaendig (kein Beleg vorhanden).

`deploy/plv/README.md:129-133` (heute; war 108-114 gegen 947dd76, verschoben durch die 25 Zeilen der Schritt-9-Einfuegung in `1b904e0`, Textinhalt unveraendert): "Das Paket traegt seine Belege ... der Auftritt prueft sie und veroeffentlicht kein Paket, das sich selbst widerspricht" — genau das ist im Repro widerlegt: `bestand.in_force` in `stand.json` (999999) widerspricht dem `bestand.in_force` (68) in der unveraenderten, hashgeprueften `protokoll.jsonl` desselben Pakets, und das Paket wird trotzdem veroeffentlicht.

**Stand auf main 10ee765.** Unveraendert seit dem geprueften `cc55192`/`947dd76`. `betrieb/seite.py` hat zwei Commits im Delta (`33452b5` T24-07 Loeschziel-Grenze, `1b904e0` Schritt 9/neuaufsetzen) — beide lassen `stand_modell()` und den Aufbau von `modell`/`dateien` in `stands_paket()` unangetastet. `werkzeuge/falldaten.py` hat keinen einzigen Commit im Delta (`git log --oneline 947dd76..10ee765 -- werkzeuge/falldaten.py` ist leer). Die neuen Testdateien `tests/test_betrieb_datenverlust_t24.py` und `tests/test_betrieb_neuaufsetzen.py` decken ausschliesslich das T24-07-Loeschziel-Thema ab; `tests/test_werkzeuge_betrieb.py` (die einzige Testdatei, die `falldaten.betrieb()` aufruft) ist seit 947dd76 ebenfalls unveraendert und mutiert in ihren Negativtests nur `protokoll.jsonl` bzw. `provenienz.pb1` — nie ein freies Top-Level-Feld wie `bestand`/`buchungen`/`uebernahmen` bei unveraendertem `dateien`-Hash. Kein Commit seit dem Befund hat diese Klasse angefasst.

**Schaden.** Wer Schreibzugriff auf ein exportiertes `stand.json` hat (Mensch beim manuellen Export/Uebergeben, ein kompromittiertes Werkzeug, ein fehlerhafter Copy/Edit-Schritt) kann die auf der oeffentlichen Vorzeigeseite gezeigten Kernkennzahlen — Vertragsbestand, Buchungsvolumen, Neugeschaeft, Uebernahmen aus fremden Bestaenden, Verankerungsstatus, sichtbare Luecken — beliebig veraendern, ohne dass `_pruefe_stands_paket` oder eine der aufrufenden Stellen (`werkzeuge/auftritt.py`) das bemerkt, solange die vier tatsaechlich geprueften Felder (Stand, P-B1-Urteil, Manifest-Hash, Journal-Hash-String) unangetastet bleiben. Der falsche Beleg, der dadurch moeglich wird: eine oeffentlich als "geprueft, belegt, P-B1 gruen" dargestellte Bestandszahl, die in Wahrheit frei erfunden ist — inklusive einer erfundenen Uebernahme aus einem fremden Bestand oder einer verschwiegenen Luecke (`luecken=[]`), obwohl die reale Verankerung laut Journal nicht angewandt wurde.

**Schwere.** Zustimmung zu "hoch". Begruendung: (a) der Angriff braucht keine kryptografische Rafinesse, nur einen Text-Editor auf einer JSON-Datei; (b) von den neun Top-Level-Sektionen des Payloads sind nur vier Randfelder (Stand, PB1, Manifest-Hash, Journal-Hash-String) ueberhaupt geprueft — der ganze fachliche Inhalt (bestand, buchungen, neugeschaeft, abschluesse, uebernahmen, verankerung sowie 5 von 8 Provenienzfeldern) ist ungeschuetzt; (c) das exakt richtige Muster — ein kanonischer, gebundener Hash ueber den publizierten Inhalt — existiert im selben Repository bereits korrekt umgesetzt (`gates/gate_entscheid.py`, `models/schemas.py:P9Snapshot`, Feld `artefakt_hashes`), wurde fuer den oeffentlichen Stands-Pfad aber nicht angewandt — dasselbe "bekannt, aber an dieser Stelle vergessen"-Muster wie in T23-06/T23-08. Einschraenkend gegenueber "kritisch": Es handelt sich um die externe Vorzeigeseite (Demo-/Auftritts-Artefakt), nicht um die tatsaechlich gefuehrte Ablage — der reale Bestand in `ablage.stand` bleibt korrekt, betroffen ist die Darstellungs-/Belegkette nach aussen, nicht die operative Bewertungsrichtigkeit. "Hoch" ist treffend, nicht konservativ untertrieben.

**Klasse (Invariante).** Ein veroeffentlichtes Artefakt, das sowohl abgeleitete Nutzdaten als auch eine Liste beigefuegter Belegdateien mit deren Hashes im selben Dokument traegt, macht "die Daten sind belegt" nur fuer die Teilmenge der Felder wahr, die beim Lesen explizit gegen eine unabhaengig gepruefte Quelle zurueckgerechnet werden — jedes andere Feld bleibt beliebig veraenderbar, selbst wenn die dafuer noetige Vergleichsquelle (hier: die bereits kettengepruefte Protokollzeile) im Pruefcode laengst geladen im Speicher liegt und schlicht nicht herangezogen wird.

**Weitere Stellen mit demselben Muster.**
- `werkzeuge/falldaten.py:975-977` und `src/rechner_pipeline/betrieb/seite.py:163-167` — `buchungen`/`neugeschaeft` sind die einzigen zwei Sektionen, fuer die tatsaechlich *keine* Belegdatei existiert (Tagesjournal wird nie kopiert): hier ist der Fix architektonisch (Option A/B des Reviewers), nicht nur ein fehlender Vergleich.
- `src/rechner_pipeline/betrieb/seite.py:171-180` / `werkzeuge/falldaten.py:967-970` — von 8 `provenienz`-Feldern werden nur `manifest_sha256` und `pb1` geprueft; `config_sha256`, `kern_version`, `image_digest`, `image_revision`, `image_tag` sind trotz Docstring-Zusage ("Es traegt seine Provenienz ... Kern-Version, Image", seite.py:427) ungeprueft, obwohl `config_sha256`/`kern_version`/alle drei Image-Felder ebenfalls bereits in der geladenen Protokollzeile stehen (empirisch bestaetigt).
- `src/rechner_pipeline/betrieb/seite.py:142-150` — jeder Eintrag in `abschluesse[]` traegt ein `sha256`-Feld fuer die zugrundeliegende Parquet-Datei; diese Datei wird nie ins Paket kopiert (nur der `bericht` des juengsten Abschlusses), der Hash ist also dauerhaft unverifizierbar — dieselbe Klasse, eine Ebene tiefer.
- Gegenbeispiel (korrektes Muster, existiert im selben Repo): `src/rechner_pipeline/gates/gate_entscheid.py:2130-2236` (`kern_inhalt`/`artefakt_hashes`, `models/schemas.py:453-521` `P9Snapshot`) bindet jede publizierte Aussage an einen benannten, mitgefuehrten Artefakt-Hash — exakt das fehlende Muster fuer `stand.json`.

**Fix-Umfang.** M, gemischt: Fuer vier der sechs ungeschuetzten Sektionen (`bestand`, `uebernahmen`, `verankerung`, `abschluesse`) sowie die fuenf ungeprueften `provenienz`-Felder ist der Fix S — `_pruefe_stands_paket` hat `zeilen`/`letzte` bereits geladen und muss nur zusaetzliche Gleichheitspruefungen ergaenzen (`stand.get("bestand") == letzte.get("bestand")` etc., fuer `abschluesse` dieselbe Aggregation wie `seite.py:138-150` ueber `zeilen` nachbilden), ohne neue Datei, ohne neue I/O. Fuer `buchungen`/`neugeschaeft` ist der Fix L: entweder das Tagesjournal (oder ein kanonischer Auszug) wird als zusaetzliche gehashte Belegdatei mitgeliefert und die Kennzahlen werden konsumentenseitig daraus abgeleitet statt vertraut (Reviewer-Option A), oder ein kanonischer Payload-Hash wird beim Schreiben der Protokollzeile in `tageslauf.py` gebunden und hier nachgerechnet (Option B, analog `artefakt_hashes`) — das beruehrt das Fachkonzept (`docs/simulation/tagesbetrieb.md`, Abschnitt 8.3) und den Paketvertrag (`deploy/plv/README.md:129-133`) und ist ein Entscheid des Maintainers, da `stand.json` aktuell kein Pydantic-Schema hat und die Wahl A vs. B die kuenftige Vertragsform festlegt. Fangender Test der KLASSE: ein parametrisierter Test ueber **jeden** Top-Level-Schluessel des von `stand_modell()` erzeugten Dicts, der bei unveraenderten `dateien`-Hashes genau dieses eine Feld mutiert und verlangt, dass `falldaten.betrieb()` mit `FalldatenFehler` ablehnt — nicht nur der Reviewer-Fall `bestand.in_force`/`buchungen.gesamt`, sondern jedes Feld einzeln, damit ein kuenftig neu hinzugefuegtes Modellfeld denselben Test automatisch trifft.

**Nachmessung der merge-session (2026-09-08, Stand 27016d1 in einem
Wegwerf-Worktree, Konsument = der echte Weg falldaten.betrieb(paket)).**
Aufbau: frische Ablage in tmp, drei Tageslaeufe (2026-02-03/-04/-05,
sample_size 8), Protokoll drei Zeilen Schema 2, Stands-Paket je Versuch neu.

| Versuch | Eingriff | Ergebnis |
|---|---|---|
| 0 | Original | angenommen, in_force = 68 |
| A | nur Nutzdaten von stand.json (in_force 68 -> 1067, buchungen.gesamt -> 4711), dateien-Hashes unangetastet | ANGENOMMEN, Konsument liefert 1067 (eine Datei angefasst) |
| B | letzte Protokollzeile UND stand.json gleichlautend gefaelscht, dateien["protokoll.jsonl"] nachgezogen | ANGENOMMEN, 1067 (zwei Dateien; Kette, Urteil, Manifest-Hash, Journal-Hash, Horizont alle korrekt) |
| C | dieselbe Faelschung an Zeile 2 von 3, Hash nachgezogen | ABGEWIESEN: "Zeile 3 bricht die Protokollkette" |

B gegen C ist der Beleg: die Kette traegt bis zur vorletzten Zeile; die
letzte ist durch nichts gebunden, und stand_modell leitet genau aus ihr ab.
Ein Payload-Hash IN dieser Zeile bliebe wirkungslos (dieselbe Datei, die der
Faelscher in B ohnehin neu schreibt).

Feldherkunft, am erzeugten Paket gemessen: aus Protokollzeilen ableitbar sind
stand, gefuehrt_seit (erste Zeile), bestand, abschluesse, uebernahmen,
verankerung, provenienz (alle acht), neugeschaeft.seit_betriebsbeginn; OHNE
Quelle im Paket: buchungen (gesamt, je_ereignis, letzte),
geschaeftsentwicklung, neugeschaeft.woche, woche_summe. Paketdateien:
berichte/bestandsbericht_*.html, laufmanifest.json, protokoll.jsonl,
seite/index.html — das Tagesjournal ist nicht dabei.

Folge fuer den Umfang: ZWEI Aufgaben, nicht eine. (1) Ableitung — der
Konsument leitet die protokollgespeisten Felder aus den Zeilen neu ab statt
stand.json zu glauben (faengt A; werkzeuge/falldaten.py, vorzeige-Ast) und
das Journal oder ein Auszug kommt als vierter Beleg ins Paket (Produzent,
dora-t24-t25). (2) Verankerung — der Inhalt der letzten Zeile wird an etwas
ausserhalb des Pakets gebunden (faengt B; nur das schliesst die Klasse).
Formen: Zeichnung jeder Protokollzeile durch einen Betriebsschluessel
ausserhalb des Pakets; Veroeffentlichung des Zeilen-Hashs ausserhalb (Fall,
Register); oder der Konsument prueft die Ablage statt des Pakets. Entscheid
des Maintainers. Regressionstest fuer B (drei Tageslaeufe, ein Paket, zwei
Dateien umschreiben) schreibt die merge-session; er wird MIT dem
Verankerungs-Fix eingecheckt.

**Nachmessung D und Folgerungen (merge-session, dieselbe Anordnung).**
D: ALLE drei Protokollzeilen gefaelscht, vorgaenger_sha256 je Zeile neu
gerechnet, stand.json und dateien-Hash nachgezogen — ANGENOMMEN, 1067. Die
Kette schuetzt gegen das Aendern EINZELNER Zeilen, nicht gegen das
Neuschreiben der ganzen; die letzte Zeile ist nur der billigste Weg. Damit
faellt jede rein interne Massnahme (zusaetzlicher Hash in der Zeile,
Terminatorzeile, zweite Kette): wer alle Dateien haelt, rechnet jede interne
Konsistenz nach. Fuer Form (2) folgt: es genuegt, den Hash der LETZTEN Zeile
aussen zu verankern, die Kette bindet dann alle Vorgaengerinnen — ein Anker,
nicht einer je Zeile. VIERTE FORM: nicht die Protokollzeilen zeichnen,
sondern stand.json (Paketmanifest-Zeichnung beim Export) — bindet das ganze
Paket mit einer Signatur, bezeugt aber nur "dieses Paket kam aus dieser
Ablage", nicht "dieser Tag lief so"; wer die Ablage faelscht und dann
exportiert, kommt durch. Welche Form traegt, haengt daran, wer als Angreifer
gilt — Entscheid des Maintainers.

KOPPLUNG (fuer die Vorlage): Ableitung und Verankerung sind NICHT unabhaengig.
Verankerung allein faengt A nicht (der Konsument liest weiter stand.json);
Ableitung allein faengt B und D nicht. Nur zusammen schliessen sie die
Klasse; wird nur eine beschlossen, bleibt sie offen, ohne dass ein Test es
anzeigt. Vorlage: zwei Aufgaben, eine Wirkung, nur gemeinsam.

Regressionstest (merge-session, gegen 27016d1 gefahren, NICHT eingecheckt,
Kopie unter Scratchpad dora/test_paket_verankerung_t2404.py):
test_ein_in_sich_stimmiges_paket_ist_noch_kein_beleg ist ROT (Soll),
test_die_kette_faengt_die_einzelne_zeile_weiterhin ist GRUEN (Ist der Kette,
damit die Verankerung sie ergaenzt statt ersetzt). Eigene Fixture mit drei
Tageslaeufen. Wird MIT dem Fix eingecheckt (tests/test_werkzeuge_betrieb.py,
vorzeige-Ast).

### T24-05 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Auf 10ee765 empirisch reproduziert (`.venv/bin/python`, `tempfile.mkdtemp`, keine Aenderung am Worktree; Skripte unter `scratchpad/t24-05/repro1.py` und `repro2.py`).

1. `pruefe_am4_snapshot()` liegt heute bei `src/rechner_pipeline/betrieb/uebernahme.py:85-141` (Reviewer zitierte 72-128 gegen 947dd76 — reine Zeilenverschiebung durch dazwischenliegenden Code, der Funktionskoerper selbst ist seit 947dd76 unveraendert, siehe unten). Sie ruft ausschliesslich `P9Snapshot.validate_payload()` (Zeile 117) sowie Selbsthash (120), `gate` (125), `entscheid` (127) und `fall` (136) auf. Weder `_pruefe_g2_snapshot_semantik()` noch `_pruefe_snapshot_graph()` noch `_lade_snapshot_kette()` aus `gates/gate_entscheid.py` werden importiert oder aufgerufen — bestaetigt per `grep`, kein Treffer.

2. `_pruefe_g2_snapshot_semantik()` liegt heute bei `gate_entscheid.py:494-551` (Reviewer: 358-398), die Graph-/Spitzenpruefung `_pruefe_snapshot_graph()` bei `gate_entscheid.py:554-596` (Reviewer: "ab 401"). Beide sind ausschliesslich aus `_lade_snapshot_kette()` (599-654) erreichbar, die wiederum nur beim SCHREIBEN eines neuen P9-Snapshots (Aufrufstellen 1875, 1941, 2043) laeuft — nicht beim reinen Lesen eines bereits akzeptierten Snapshots durch einen Drittkonsumenten wie `uebernahme.py`.

3. Der A-M4/bestand-Belegrollen-Vertrag (`src/rechner_pipeline/fall.py:119-135`, `BELEGROLLEN["A-M4"]["bestand"]`) verlangt HEUTE zehn statt der vom Reviewer zitierten neun Rollen — `fuehrungsprobe` kam durch Commit `67a0b5e` ("Freischaltung, Schritt 6", zwischen 947dd76 und 10ee765) hinzu:
```
pq3_ledger, aq1_snapshot, am1_snapshot, am2_snapshot, am3_snapshot,
pk1_belege, pb1_ledger, migrationssuite, fuehrungsprobe, abnahmebericht
```
Das aendert den Befund nicht, vergroessert aber die Luecke: das Positivfixture traegt weiterhin nur eine von jetzt zehn Rollen.

4. Direkter Aufruf von `_pruefe_g2_snapshot_semantik()` gegen das unveraenderte Fixture aus `tests/test_betrieb_uebernahme.py:92-119` (Datei seit 947dd76 byte-identisch, `git log --oneline 947dd76..10ee765 -- tests/test_betrieb_uebernahme.py` ist leer):
```
aktuell erwartete A-M4/bestand-Rollen: ['pq3_ledger', 'aq1_snapshot', 'am1_snapshot',
  'am2_snapshot', 'am3_snapshot', 'pk1_belege', 'pb1_ledger', 'migrationssuite',
  'fuehrungsprobe', 'abnahmebericht']

Fehler aus _pruefe_g2_snapshot_semantik:
 - pflichtbelege enthaelt nicht exakt die aus dem Scope abgeleiteten Rollen [...]
 - pflichtbelege['pk1_belege'] stimmt nicht mit der Generationen-Belegmenge ueberein
```
Exakt die vom Reviewer behaupteten zwei Fehler, unveraendert reproduziert.

5. Gegenprobe mit echtem `eingang_anlegen()`-Aufruf (Import der Test-Helfer `_fall`, `am4_snapshot`, `_zugangsstand` aus dem unveraenderten Testmodul, drei echte Vertraege der Generation KLV-2017):
```
bestand.parquet  sha256[:8] = cb58be96
historie.parquet sha256[:8] = 59f11018
ledger.parquet   sha256[:8] = 8d66e1bf
Uebernahmeeingang angelegt: True
im Snapshot behauptete artefakt_hashes: {'eingang.json': 'ab...', 'abgeleitet/abox/abox.json': 'cd...'}
Schnittmenge echte Tabellenhashes vs. behauptete Hashes: set()
```
Deckt sich mit der Reviewer-Reproduktion (Hashpraefixe `8d66...`, `cb58...`, `59f1...` gegen behauptete `ab...`/`cd...`) bytegenau. Der Kopier-/Hash-Block in `eingang_anlegen()` liegt heute bei `uebernahme.py:495-503` (Reviewer: 400-420) und schreibt die realen Hashes nur in die lokale `eingang.json`, ohne sie je gegen `artefakt_hashes` oder `pflichtbelege` des A-M4-Snapshots abzugleichen.

6. Kein zweites Sicherheitsnetz zur Laufzeit: `betrieb/tageslauf.py` liest von der `Uebernahme` nur `u.snapshot_sha256` und `u.zeichnung` zur Anzeige (Zeile 468-469) und verifiziert beim taeglichen Lauf nichts erneut gegen die Snapshot-Kette.

**Stand auf main 10ee765.** Unveraendert. `pruefe_am4_snapshot()` selbst ist seit 947dd76 nicht angefasst worden — `git show b70c081/1b904e0/c1e99ae -- src/rechner_pipeline/betrieb/uebernahme.py` zeigt Aenderungen nur an `PFLICHT`/`OPTIONAL` (Scheiben/Schichten), der `Uebernahme`-Dataclass, `tarifwerk_fehler()`, `zeichnung_aus_snapshot()` (Mandat-Feld) und `validate_eingang()` (Schluesselklassen-/Mandatspruefung der `zeichnung` im Eingang, Review T23-06/-08) — keine dieser Aenderungen betrifft Scope-Rollenvergleich, Graph/Spitze oder Bytebindung. `tests/test_betrieb_uebernahme.py` ist seit 947dd76 unveraendert (leerer `git log`). Das positive Fixture, das der Reviewer zitiert, ist exakt dasselbe.

**Schaden.** `betrieb.uebernahme` ist der einzige und einmalige Eintrittspunkt, der einen migrierten Bestand dauerhaft in den Tagesbetrieb aufnimmt (seit Commit `1b904e0`/Schritt 9 ist dieser Tagesbetrieb voll auf main verdrahtet — die Produktionsflaeche ist also seit dem Review-Zeitpunkt eher gewachsen, nicht geschrumpft). Wer die Kontrolle ueber eine Snapshot-Datei unter `entscheide/A-M4-*.json` hat (fehlerhafter/boesartiger Producer, Handbearbeitung, falscher `--snapshot`/`--quelle`-Aufruf), kann einen strukturell wohlgeformten, aber inhaltlich fast leeren oder gegenueber den tatsaechlich kopierten Tabellen voellig unverbundenen Snapshot als vollwertige A-M4-Annahme durchreichen. Ab dann gilt der uebernommene Bestand als "gefuehrt" (P-B1 gruen laut Testsuite) und faehrt permanent im selben Strom wie das Eigengeschaeft mit — ohne dass je geprueft wurde, ob genau diese Bytes tatsaechlich das waren, was A-M1 bis A-M3, PK1, die Migrationssuite, die Fuehrungsprobe und der Abnahmebericht gepruefte hatten.

**Schwere.** Zustimmung zu "hoch". Es handelt sich um die einzige Kontrollstelle, die eine irreversible, dauerhafte Aufnahme fremder Daten in den produktiven Bestand vor sich hat; die Luecke ist mit realistischen, nicht-exotischen Mitteln ausloesbar (ein unvollstaendiges oder falsch adressiertes JSON reicht, wie gezeigt) und wirkt unabhaengig von der bereits separat ausgewiesenen fehlenden Signaturpruefung (T19-02) — selbst ein Aufrufer OHNE Schluessel koennte Rollen-, Graph- und Bytebindung pruefen, tut es aber nicht. Einschraenkend: der normale, ueber die CLI erzeugte Weg (Gate schreibt den Snapshot, `eingang_anlegen` liest ihn direkt danach) produziert in der Praxis meist vollstaendige Snapshots; das Angriffsfenster braucht Schreibzugriff auf den Fall-Arbeitsbereich oder eine Fehlbedienung von `--snapshot`/`--quelle` — kein Fernzugriff. Das rechtfertigt "hoch", nicht zwingend "kritisch".

**Klasse (Invariante).** Ein Konsument, der eine vom System selbst geschriebene Belegkette (P9-Snapshot) als Eintrittsvoraussetzung fuer eine irreversible, produktionswirksame Aktion liest, aber sie nur auf generische Schemaform und Selbstadressierung prueft statt sie durch denselben Belegrollen-, Graph- und Bytebindungs-Vertrag zu schicken, mit dem das erzeugende Gate sie geschrieben hat, laesst jeden strukturell wohlgeformten, aber inhaltlich unvollstaendigen oder fremd erzeugten Snapshot als vollwertigen Beleg durch.

**Weitere Stellen mit demselben Muster.** Gesucht mit `grep -rn "entscheide.*glob\|entscheide_verzeichnis\|pruefe_snapshot_ohne_schluessel"` ueber `src/` und `werkzeuge/`.

- `werkzeuge/falldaten.py:555-565` ruft `gate_entscheid.pruefe_snapshot_ohne_schluessel()` — dieselbe bewusste Einschraenkung (nur Schema+Selbsthash, kein Rollen-/Graph-Check), dokumentiert genau dafuer gebaut. Anderer Konsequenzgrad: es ist ein reines Anzeige-Werkzeug (Fall-Seite), das Ergebnis heisst ehrlich `strukturell_verifiziert`, nicht "angenommen"; ein bereits im selben Modul vermerkter Kommentar (Zeile ~812, `ERWARTETE_ENTSCHEIDE`) raeumt eine verwandte Schwaeche selbst ein. Kein Datenverlust/keine Produktionsaufnahme, daher als verwandte, aber schwaechere Instanz gefuehrt, nicht als vollen Treffer gezaehlt.
- Keine weitere Stelle in `src/` liest `entscheide/*.json` oder einen P9-Snapshot direkt fuer eine gate-artige Entscheidung ausserhalb von `gate_entscheid.py` selbst und `uebernahme.py`.

**Fix-Umfang.** M, tendenziell L. Vorschlag: (1) `_pruefe_g2_snapshot_semantik()` und `_pruefe_snapshot_graph()` (oder eine neue oeffentliche Zusammenfassung `pruefe_snapshot_vollstaendig(daten, aktueller_systemstand, fall) -> List[str]`) aus `gate_entscheid.py` als wiederverwendbare, nicht-private API exportieren; (2) `pruefe_am4_snapshot()` in `uebernahme.py` ruft sie mit `fall_scope="bestand"` und dem aktuellen Systemstand auf, statt die Pruefung eigenstaendig nachzubauen; (3) einen expliziten Bytebindungs-Check ergaenzen: jede beim Kopieren gehashte Datei (`dateien` in `eingang_anlegen()`) muss unter den vom Snapshot referenzierten Belegen (`artefakt_hashes`/`pflichtbelege`) auffindbar sein, sonst Abbruch; (4) das Positivfixture in `tests/test_betrieb_uebernahme.py` durch einen semantisch vollstaendigen A-M4-Snapshot (alle zehn Rollen, echte Vorgaengerkette) ersetzen. Fangender Klassen-Test: ein parametrisierter Test, der je einen der drei jetzt fehlenden Checks (Rollenmenge unvollstaendig, Vorgaenger zeigt auf nicht existente/zyklische Kette, `artefakt_hashes` ohne Bezug zu den tatsaechlich kopierten Bytes) einzeln verletzt und erwartet, dass `eingang_anlegen()` in JEDEM Fall mit `UebernahmeError` abbricht. Beruehrt den Gate-Vertrag (Privat->Oeffentlich-Grenze von `gate_entscheid.py`, Wiederverwendung des P9-Lesevertrags in einem anderen Teilsystem) — Entscheid des Maintainers noetig, insbesondere zur Frage, ob `gate_entscheid`-interne Pruefroutinen zu einer stabilen, moduluebergreifenden API werden.

### T24-06 — Reviewer Hoch — Urteil: teilweise

**Beweis.** Beide Teilbefunde auf 10ee765 empirisch reproduziert (`.venv/bin/python`, ausschliesslich in `tempfile.mkdtemp`-Verzeichnissen, Skripte unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t24-06/`, keine Aenderung am Worktree).

*Teil A — Doppel-Lesen.* Reviewer-Zeilen 101-127/128/149-173 (gegen 947dd76) entsprechen heute `src/rechner_pipeline/betrieb/uebernahme.py:110-141` (`pruefe_am4_snapshot`, Lesen+Validierung: Datei lesen 113-116, Schema 117-119, Selbstadressierung 120-124, Gate 125-126, Entscheid 127-131, Fall 132-140, Rueckgabe `zeichnung_aus_snapshot(...)` Zeile 141) und `uebernahme.py:144-190` (`zeichnung_aus_snapshot`, eigener Pfad 162, eigenes zweites Lesen 163-168). Reproduktion mit echtem Datei-Swap zwischen den beiden Lesevorgaengen (Wrapper um `pathlib.Path.read_text`, kein Monkeypatch der Zielmodul-Logik):
```
Lesevorgaenge auf denselben Pfad A-M4-<sha>.json: 2
gepruefter Snapshot (Read #1): gate='A-M4' entscheid='angenommen'
registrierter snapshot_sha256 (Hash von Read #1, an eingang.json/Aufrufer weitergereicht): db56b78...
Bytes auf der Platte NACH dem Aufruf: entscheid='abgelehnt' (der ausgetauschte Inhalt)
zurueckgegebene Zeichnung (stammt aus Read #2, dem ausgetauschten Inhalt):
  {'gate': 'A-M4', 'entscheid': 'abgelehnt', 'rolle': 'mensch', ...}
```
`pruefe_am4_snapshot()` bricht nicht ab; die Selbstadressierungs-/Gate-/Entscheid-/Fall-Pruefung lief auf Read #1 (angenommen), die zurueckgegebene und in `eingang.json` verewigte Zeichnung stammt aus Read #2 (abgelehnt) — `zeichnung_aus_snapshot()` prueft beim eigenen Lesen weder Selbstadressierung noch Gate/Entscheid/Fall erneut. Wortgleich zur Reviewer-Reproduktion.

*Teil B — Laufzeit-Leser.* `validate_eingang()` liegt heute bei `uebernahme.py:256-303` (Reviewer 209-238 gegen 947dd76). Snapshot-Pruefung Zeile 269-271: `if snapshot is not None and not _ist_sha256(snapshot): fehler.append(...)` — `snapshot_sha256 = None` bleibt weiterhin fehlerfrei. `lies_uebernahme()` liegt heute bei `uebernahme.py:310-395` (Reviewer 245-305); Zeile 383-384 uebernimmt `eingang.get("snapshot_sha256")` und `eingang.get("zeichnung")` direkt aus der selbst behaupteten `eingang.json`, ohne je wieder auf eine Snapshot-Datei zuzugreifen. Reproduktion: ein mit `eingang_anlegen()` (Writer-Pfad, echter A-M4-Snapshot) angelegter Eingang wurde per `chmod(0o644)` + Editieren + `chmod(0o444)` manipuliert (`snapshot_sha256=None`, `zeichnung={"gate":"KEIN-GATE","entscheid":"angenommen","rolle":"simulation"}`, Parquet-Dateien unveraendert):
```
validate_eingang() auf der manipulierten Tabelle direkt:
  Fehlerliste: [] (leer = akzeptiert)

lies_uebernahme() auf dem manipulierten Eingang:
  snapshot_sha256: None
  zeichnung: {'entscheid': 'angenommen', 'gate': 'KEIN-GATE', 'rolle': 'simulation'}
  vertraege: 3
```
Verschaerfte Zusatzprobe (nicht im Original-Befund, aber dieselbe Klasse): mit einem frei erfundenen, aber formal gueltigen `snapshot_sha256` (`"a"*64`, keine zugehoerige Datei existiert je) und einer vollstaendig ausgefuellten `zeichnung` (`schluesselklasse: "mensch"`, `entscheid: "angenommen"`, `gate: "A-M4"`) liefert sowohl `validate_eingang()` als auch `betrieb.seite.luecken()` eine LEERE Fehler-/Luecken-Liste — die interne Seite zeigt in diesem Fall **keinerlei** Hinweis auf eine Luecke; die Faelschung ist vollstaendig getarnt.

**Stand auf main 10ee765.** Teilweise behoben. `git log --oneline 947dd76..10ee765 -- src/rechner_pipeline/betrieb/uebernahme.py` zeigt drei Commits: `b70c0814` (`fix(models,ontologie,gates,betrieb)!: Zeichnungsvertrag ... Review T23-06/-08, Block 4`, 2026-09-08, also NACH der Erhebung des Befunds am 2026-09-07 gelandet), `1b904e0` (Freischaltung Schritt 9) und `c1e99ae` (Merge). `b70c081` fuegt in `validate_eingang()` genau den Block `uebernahme.py:275-292` neu ein (`elif isinstance(zeichnung, dict): klasse = zeichnung.get("schluesselklasse", ...); ...`) — das schliesst exakt die Luecke, die dieselbe Datei bereits als "Weitere Stelle" im **aelteren** Befund T23-06 bekam (`dev-docs/befundliste-t23.md`, Abschnitt T23-06: "`betrieb/uebernahme.py:166-168` ... prueft nur 'zeichnung muss eine Tabelle sein' ... keine Rolle/Schluesselklasse/Mandat-Pruefung"). Diese Reparatur trifft T24-06 nur am Rand: der Reviewer-PoC-Wert `{"gate": "KEIN-GATE", "entscheid": "angenommen", "rolle": "simulation"}` traegt gar kein `schluesselklasse`-Feld, faellt also auf den Default `NICHT_AUSGEWIESEN` zurueck und bleibt — wie oben empirisch gezeigt — weiterhin akzeptiert. Unveraendert seit 947dd76 sind: das Doppel-Lesen (Teil A, in keinem der drei Commits beruehrt — `git diff 947dd76..10ee765 -- ...uebernahme.py` zeigt an `pruefe_am4_snapshot`/`zeichnung_aus_snapshot` nur die Ergaenzung des `mandat_sha256`-Feldes im zurueckgegebenen Dict, Zeilen 183-186, keine Aenderung an der Zwei-Lesevorgaenge-Struktur selbst), die fehlende Snapshot-Pflicht in `validate_eingang()` (Zeile 269-271 unveraendert) und die fehlende Gate-/Entscheid-Pruefung der `zeichnung`-Tabelle (nirgends ergaenzt).

**Schaden.** Zwei Angriffsflaechen, beide real ausnutzbar. Erstens (Teil A) ein enges, aber reales TOCTOU-Fenster genau innerhalb des ANLEGENS: zwischen der Validierung (Read #1) und der Zeichnungsableitung (Read #2, Sekundenbruchteile spaeter, aber ohne jede Synchronisation) kann ein paralleler Schreiber, ein Tool-Cleanup oder ein Fehler denselben Pfad veraendern — der in `eingang.json` verewigte `zeichnung`-Block stammt dann nachweislich NICHT aus den geprueften Bytes. Zweitens (Teil B, der breitere Schaden) ist das keine reine Erzeugungszeit-Frage: `tageslauf.py:348` ruft `lies_uebernahmen()` bei JEDEM Tageslauf neu auf (nicht nur bei der Erstbefuellung), und `tageslauf.py:464-469` schreibt `snapshot_sha256`/`zeichnung` aus dem ungeprueften Eingang direkt in die Zeile des append-only, hash-verketteten Tagesprotokolls. Wer `eingang.json` irgendwann NACH dem Anlegen manipuliert (der Modus 0444 verhindert das nicht — mein Reproduktionsskript, als Dateieigentuemer, hat `chmod`, Schreiben und erneutes `chmod` ohne jede Fehlermeldung durchgefuehrt), bekommt die Faelschung beim naechsten Lauf dauerhaft in die Protokollkette geschrieben; niemand liest danach je wieder die urspruengliche Snapshot-Datei nach. `betrieb/seite.py:169` liest `zeile.get("uebernahmen")` aus genau dieser Protokollzeile und rendert `Entscheid`/`Rolle`/`Entscheider`/`Schluesselklasse` (Zeilen 340-346) unbesehen; die verschaerfte Zusatzprobe zeigt, dass eine vollstaendig ausgefuellte Faelschung dort ohne jede sichtbare Luecke erscheint. Das widerspricht direkt der dokumentierten Zusage in `docs/simulation/tagesbetrieb.md:266` ("`uebernahme/<fall>/` — Eingang je Migration — unantastbar wie ein Fall-Eingang") und dem Modul-Docstring `uebernahme.py:15` ("Der Eingang ist unantastbar wie ein Fall-Eingang ... eine Abweichung ist ein harter Fehler, kein Vorbehalt") — fuer die Felder `snapshot_sha256` und `zeichnung` gilt das nachweislich nicht.

**Schwere.** Zustimmung zu "hoch". Begruendend ueber die reine Fundstelle hinaus: (a) der bestehende Test `tests/test_zeichnungsvertrag_t23.py::test_betriebseingang_behauptet_keine_fremde_klasse_und_keine_simulation_ohne_mandat` verwendet `snapshot_sha256: None` als unkommentierten Basisfall in JEDER seiner Assertions — die Luecke ist nicht nur ungetestet, sie ist im Testkorpus als Normalfall einprogrammiert, was ihr Auffallen im Alltag zusaetzlich erschwert; (b) der Schaden ist nicht auf den Erzeugungsmoment begrenzt, sondern lebt in jedem taeglichen Lauf weiter und wird in eine append-only Kette geschrieben, die genau als Nachweisinstrument gegen nachtraegliche Manipulation gedacht ist; (c) die verschaerfte Zusatzprobe zeigt, dass eine sorgfaeltig ausgefuellte Faelschung ohne jede Luecken-Anzeige durchgeht — das ist kein Rand-, sondern der Kernfall. Einschraenkend: der Angriff braucht Schreibzugriff auf das Laufzeit-Datenverzeichnis (kein Fernzugriff), und die eigentlichen Bestandszahlen (Policen, Betraege) bleiben durch die Parquet-Hash-Pruefung weiterhin gebunden — der falsche Beleg betrifft die Governance-/Nachweisebene der Migrationsabnahme, nicht die Rechenergebnisse selbst. Das rechtfertigt "hoch", nicht zwingend "kritisch" — ich sehe keinen Grund, von der Reviewer-Einstufung abzuweichen.

**Klasse (Invariante).** Ein Wert, der als "gegen einen geprueften Beleg verifiziert" propagiert oder wiederholt (bei jedem Lauf, nicht nur bei der Erzeugung) als gueltig gelesen wird, darf weder aus einem zweiten, unabhaengigen Lesevorgang derselben Quelle stammen, der die urspruengliche Pruefung nicht wiederholt (Teil A), noch von einem Leser akzeptiert werden, dessen Pflichtenkatalog schwaecher ist als der des Schreibers, der ihn erzeugt hat (Teil B) — in beiden Faellen wird "geprueft" zu einer historischen statt einer fortlaufend gueltigen Aussage, sobald zwischen Pruefung und Verwendung (oder zwischen zwei Verwendungen) eine unkontrollierte Luecke liegt.

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/betrieb/tageslauf.py:348` (`lies_uebernahmen(ablage.uebernahme, config)`) — nicht nur bei der Erstbefuellung, sondern bei JEDEM Tageslauf aufgerufen; das ist der operative Punkt, an dem die Luecke aus Teil B nicht nur einmalig, sondern dauerhaft wiederholt genutzt und in die Protokollkette geschrieben wird (Zeilen 464-469).
- `src/rechner_pipeline/betrieb/seite.py:169,232-244,340-346` (`stand_modell()`/`luecken()`/`rendere_html()`) — rendert `zeichnung`/`snapshot_sha256` direkt aus der (bereits ungeprueften) Protokollzeile, ohne je die zugrundeliegende Snapshot-Datei erneut zu lesen; die verschaerfte Zusatzprobe zeigt, dass eine vollstaendig gefaelschte Zeichnung dort ohne Luecken-Hinweis erscheint.
- `src/rechner_pipeline/betrieb/neuaufsetzen.py:163` (`lies_uebernahme(eingang, cfg)`) — nutzt denselben schwachen Leser als einzige Pruefung nach dem Anlegen; hier weniger kritisch, da der Eingang unmittelbar zuvor ueber den strikten Writer entstand, aber dieselbe Funktion, dieselbe Schwaeche.
- `tests/test_zeichnungsvertrag_t23.py:220-225` (`test_betriebseingang_behauptet_keine_fremde_klasse_und_keine_simulation_ohne_mandat`) — kein Fundort im Produktionscode, aber ein Beleg dafuer, dass `snapshot_sha256: None` im Testkorpus als unauffaelliger Normalfall verankert ist, nicht als abzulehnender Grenzfall.
- Fuer das allgemeinere Doppel-Lese-Muster (Teil A) ausserhalb dieser Datei: keine weitere Instanz *innerhalb von `betrieb/`* gefunden (gezielt gesucht: alle Aufrufer von `pruefe_am4_snapshot`/`zeichnung_aus_snapshot`, sowie ob `seite.py` selbst je eine Snapshot-Datei erneut liest — beides verneint). Das systemische Doppel-Lese-Problem in `gates/*.py` (P-Q3, P-K1, A-K1, abox_merge, abnahmebericht, aktuartest) ist bereits als eigener, groesserer Befund (T23-01, `dev-docs/befundliste-t23.md`) mit eigenem Reparaturplan erfasst — hier nicht erneut aufgefuehrt, um keine doppelte Buchfuehrung zu erzeugen.

**Fix-Umfang.** M fuer den unmittelbar schliessbaren Kern, L falls die dauerhafte externe Bindung mitgeloest werden soll (siehe unten — Ruecksprache empfohlen). Konkret: (1) *Teil A*: `pruefe_am4_snapshot()` haelt bereits die validierten `daten` im Scope (Zeile 114) — `zeichnung_aus_snapshot()` sollte ein optionales `daten: Optional[dict] = None`-Argument erhalten, das `pruefe_am4_snapshot()` beim eigenen Aufruf (Zeile 141) direkt durchreicht, statt der Funktion einen zweiten eigenstaendigen Lesevorgang zu ueberlassen; der eigenstaendige Lesepfad (fuer den Aufruf ohne vorherige Pruefung, z. B. `lies_uebernahme()`-Fallback Zeile 384 und die Tests) bleibt bestehen, liest aber weiterhin nur EINMAL. (2) *Teil B*: `validate_eingang()` muss `snapshot_sha256` verpflichtend machen (Zeile 269-271: den `if snapshot is not None`-Vorbehalt entfernen — der Writer verlangt ihn seit T22-06 ausnahmslos, es gibt keine legitime Bestandsluecke dafuer) und zusaetzlich pruefen, dass eine vorhandene `zeichnung`-Tabelle `gate == "A-M4"` und `entscheid == "angenommen"` traegt (die einzigen Werte, die der Writer je erzeugen kann). (3) Fangender Klassen-Test: ein parametrisierter Test analog zu `test_betriebseingang_behauptet_keine_fremde_klasse_und_keine_simulation_ohne_mandat`, der aber `snapshot_sha256: None` UND `zeichnung.gate != "A-M4"`/`entscheid != "angenommen"` als ABZULEHNENDE Faelle statt als Basisfall fuehrt, plus ein Reproduktions-Test nach dem Muster meines `repro_a_doppellesen.py` (echter Datei-Swap zwischen den beiden Lesevorgaengen von `pruefe_am4_snapshot`), der nach dem Fix entweder einen Fehler oder eine mit Read #1 konsistente Zeichnung verlangt. Offen und bewusst NICHT in diesem Fix-Umfang: die vom Abnahmekriterium geforderte *dauerhafte* Bindung ("den geprueften Snapshot selbst oder seine extern gebundene Identitaet dauerhaft mit dem Eingang fuehren", also eine Pruefung, die auch NACH der Erzeugung bei jedem Tageslauf eine Manipulation von `eingang.json` selbst erkennt) — das ueberschneidet sich mit den im Vorspann bereits gesondert gefuehrten offenen Befunden zum Belegvertrag von `stand.json`/Journal (dort als eigener Architektur-Punkt behandelt) und sollte mit deren Reparatur koordiniert, nicht isoliert in `uebernahme.py` nachgebaut werden — dafuer ist ein Entscheid des Maintainers noetig (Fachkonzept `docs/simulation/tagesbetrieb.md` Block B5 und die "unantastbar"-Zusage in ADR-002 sind beruehrt).

### T24-08 — Reviewer Mittel — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (echter Code, `.venv/bin/python`, `PYTHONPATH=src`, `tempfile.TemporaryDirectory`, keine Aenderung am Worktree; Skript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t24-08/repro.py`, echte PLV-Runtime-Config `configs/bestand_gesamt.toml`):

1. `neugeschaeft_am(config, 2026-01-02)` (`betrieb/neugeschaeft.py:172-206`) liefert deterministisch genau eine Police der eigenen Generation KLV-2025 (Nummernkreis 10) mit `police_id = 105100201` — eine reine Funktion der Config, im Voraus berechenbar, ohne dass an diesem Tag je ein Lauf stattfand.
2. Ein Fall mit exakt dieser Police-ID als "gelieferter" Zugang (Stichtag 2026-01-01) wird `ueb.eingang_anlegen()` (`betrieb/uebernahme.py:415-521`) uebergeben — akzeptiert, kein Fehler, kein Hinweis.
3. `tageslauf(ablage, 2026-01-01)` (Uebernahmestichtag) laeuft gruen: `exit=0 uebernommen=True`.
4. `tageslauf(ablage, 2026-01-02)` — der Tag, an dem das EIGENE Neugeschaeft dieselbe ID zieht — bricht ab:
```
exit=2  EreignisError: zugaenge: police_ids kollidieren mit dem Basisbestand: [105100201]
```

Damit ist der vom Reviewer beschriebene Mechanismus bestaetigt, mit einer Praezisierung: der in meiner Reproduktion tatsaechlich feuernde Guard ist nicht `tageslauf._zusammen()` (die prueft am 01.01. noch keine Kollision, weil `eigen` an dem Tag nur den Batch-Bestand enthaelt, dessen Nummernkreis-10-Anteil unter 5 Mio liegt), sondern `bestand/ereignisse.py:1002-1009` (`_pruefe_mitgebrachte_zugaenge`, Fehlerzeile 1005-1008), der beim taeglichen Neugeschaeft-Merge dieselbe Fehlerklasse wirft. Beide Guards — sowie ein dritter, `bestand/cli_fortschreibung.py:141-159` (`_mit_uebernahme`, gleiche Meldung "police_id-Kollision zwischen eigenem und uebernommenem Bestand") — teilen exakt dieselbe Limitierung: sie erkennen eine Kollision nur an dem Tag, an dem beide Seiten tatsaechlich im selben Lauf materialisiert werden, nie vorab beim Registrieren des Eingangs.

`config.nummernkreis()` (`bestand/config.py:947-956`), `_pruefe_nummernkreise()` (`config.py:928-945`) und das Feld `nummernkreis` (`config.py:259-269`) sichern nur die Eindeutigkeit/Positionsstabilitaet zwischen den EIGENEN Generationen; `_police_ids()` (`betrieb/neugeschaeft.py:148-170`) erzeugt daraus die Tages-IDs. Keine dieser Stellen und `eingang_anlegen()`/`validate_eingang()` (`uebernahme.py:256-304`) pruefen `police_id` oder `nummernkreis` gegeneinander — `grep -n "police_id\|nummernkreis" src/rechner_pipeline/betrieb/uebernahme.py` liefert 0 Treffer.

Real-Beleg (nur gelesen, `faelle/baldrian-klv-tg2015-lauf2` im Haupt-Tree, keine Aenderung): Der reale Bestandsabzug traegt `POLNR=7000001..7001003` unveraendert als `police_id` in `abgeleitet/bestand/bestand.parquet` (min/max identisch zur CSV) — die Pflichtfeldliste in `ontologie/transformation.py:44-45` macht `police_id` zum Pflichtfeld ohne Neuvergabe/Renummerierung vorzusehen. In diesem konkreten Fall-Snapshot (`abgeleitet/bestand-config.toml`) ist bei keiner der zehn Generationen `nummernkreis` gesetzt (Positions-Fallback), sodass die 7-Mio-Range der gelieferten Nummern knapp unter dem kleinsten moeglichen reservierten Band (10 Mio) liegt — reiner Groessenordnungs-Zufall, keine Systemgarantie: eine Lieferung mit achtstelligen statt siebenstelligen Policennummern (z. B. `70000001` statt `7000001`) laege direkt im Reservat von Nummernkreis 7.

**Stand auf main 10ee765.** Unveraendert seit dem geprueften `947dd76`. `git log --oneline 947dd76..10ee765 -- src/rechner_pipeline/betrieb/neugeschaeft.py` ist leer. `bestand/config.py`, `betrieb/tageslauf.py`, `bestand/ereignisse.py` und `betrieb/uebernahme.py` haben seither Commits (u. a. `1b904e0` "Freischaltung Schritt 9", `d9f7566`, `33452b5`, `8725982`, `ff18e03`, `d13edf2`, `7b58147`), aber `diff` gegen den 947dd76-Stand zeigt fuer `_pruefe_nummernkreise`/`nummernkreis()` (config.py), `_zusammen()` (tageslauf.py) und `_pruefe_mitgebrachte_zugaenge()` (ereignisse.py) jeweils **byte-identischen** Funktionskoerper — nur zeilenverschoben durch unabhaengige Ergaenzungen davor. Die einzige neue Funktion in `uebernahme.py` seit 947dd76 ist `tarifwerk_fehler()` (1b904e0) — sie prueft Tarifwerk-Schalter (`scheiben_mit_gamma1` u. Ae.) gegen den Beleg, nicht Police-IDs.

**Schaden.** Ein am A-M4-Gate formal freigegebener Uebernahme-Eingang kann eine Police-ID enthalten, die spaeter — an einem beliebigen, aus der Nummernkreis-Formel im Voraus berechenbaren, in der Praxis aber nicht ueberwachten Verkaufstag — vom eigenen Tagesneugeschaeft erneut vergeben wird. Der Fehler zeigt sich nicht beim Import, wo er billig und gezielt behebbar waere, sondern erst produktiv, moeglicherweise Jahre spaeter, als harter Abbruch des taeglichen Betriebslaufs. Kein stiller Bewertungsfehler (beide Seiten der Kollision werden erkannt, der Lauf bricht sichtbar rot ab), aber ein reales Denial-of-Service der Bestandsfuehrung zu einem vom Betreiber nicht gewaehlten Zeitpunkt, ohne automatischen Ausweg — die kollidierende eigene Police kann nicht einfach uebersprungen werden, ohne den deterministischen Neugeschaeft-Strom (und damit jede spaetere ID) zu verschieben. Der reale Baldrian-Fall zeigt, dass Quellsystem-Policennummern unveraendert in `police_id` uebernommen werden; das Risiko ist keine akademische Konstruktion.

**Schwere.** Zustimmung zu "Mittel", am oberen Rand der Kategorie. Wahrscheinlichkeit und unmittelbare Beherrschbarkeit sind niedriger als bei den "Hoch"-Befunden dieser Runde, weil die Kollision einen numerischen Treffer zwischen einem konkreten Fremdbestand und der eigenen deterministischen ID-Formel braucht und der reale Baldrian-Fall zufaellig ausserhalb der reservierten Baender liegt. Dagegen steht: pro Nummernkreis sind 8 von 10 Millionen moeglichen Werten reserviert (80 %: Batch `[1,1M)`, Jahresneuzugang `[2M,5M)`, Tagesneugeschaeft `[5M,8M)` — `betrieb/neugeschaeft.py:76-83`, `bestand/generator.py:237-241`), verteilt ueber inzwischen 13 aktive Nummernkreise in `configs/bestand_gesamt.toml` — kein schmales Randfenster, sondern ein grosser Teil des adressierbaren Zahlenraums zwischen 10 und 140 Mio. Die Konsequenz (unvorhersehbarer, produktiver Totalstop ohne automatischen Ausweg) ist bei numerisch aehnlich geformten Fremdbestaenden nicht unrealistisch. Ich haette fuer die Grenze zu "Hoch" Verstaendnis, teile aber die Einordnung als Betriebs- (nicht Bewertungs-)Risiko und stimme der Kategorie "Mittel" im Ergebnis zu.

**Klasse (Invariante).** Jede Stelle, die eine ID-Kollision zwischen "eigenem" und "uebernommenem" Bestand nur beim tatsaechlichen Zusammenfuehren im laufenden Betrieb prueft (`_zusammen`, `_pruefe_mitgebrachte_zugaenge`, `_mit_uebernahme`), aber keine Stelle, die eine importierte ID beim EINGANG gegen den vollstaendigen, aus der Config ableitbaren KUeNFTIGEN Namensraum der eigenen ID-Erzeugung haelt, verschiebt eine am Eingang billig entscheidbare Ablehnung in einen unvorhersehbaren, teuren Produktionsabbruch — die Pruefung schuetzt den momentanen, nicht den gesamten reservierten Namensraum.

**Weitere Stellen mit demselben Muster.**
- `src/rechner_pipeline/bestand/cli_fortschreibung.py:141-159` (`_mit_uebernahme`) — der Entwicklerpfad `cli_fortschreibung --uebernahme` traegt exakt dieselbe nur-beim-Merge-Pruefung wie `tageslauf._zusammen`.
- `src/rechner_pipeline/bestand/ereignisse.py:1002-1009` (`_pruefe_mitgebrachte_zugaenge`) — der tatsaechlich in meiner Reproduktion feuernde dritte Guard; auch er sieht nur den zum Aufrufzeitpunkt bereits materialisierten `stamm`.
- Gegenbeispiel (kein Fehler, zeigt den fehlenden Praeventionsort): `config.py:928-945` (`_pruefe_nummernkreise`) waere der naheliegende Ort fuer eine zusaetzliche, gegen importierte Faelle gerichtete Pruefung — er prueft heute nur die eigenen Generationen untereinander (Eindeutigkeit, Bereich 1..99), nicht gegen bereits registrierte `uebernahme/*/eingang.json`.

**Fix-Umfang.** M. Kein Schema-Bruch, aber ein bestehender Fachkonzept-Passus (Nummernkreis-Reservierung, T22-09, Tagesbetrieb-Konzept Abschnitt 4) wird beruehrt — der Maintainer sollte entscheiden, welche der zwei Reparaturrichtungen gewaehlt wird:
(a) `eingang_anlegen()` bzw. eine vorgelagerte Pruefung bekommt eine Funktion, die fuer jede `police_id` im Zugangsstand testet, ob sie in irgendeinem `kreis*10_000_000 .. kreis*10_000_000+_ID_GRENZE` der KONFIGURIERTEN Nummernkreise liegt (nicht nur des importierten Falls), und den Eingang bei Treffer ablehnt — schliesst die Klasse an der Wurzel, vor jedem Schreiben;
(b) alternativ ein expliziter externer Namensraum fuer importierte Bestaende, in den `eingang_anlegen()` beim Registrieren umnummeriert (braeuchte einen stabilen Mapping-Beleg fuer Ledger/Berichte).
Fangender Klassen-Test: parametrisiert `neugeschaeft_am(config, tag)` fuer einen kuenftigen Tag eine ID vorausberechnen lassen (wie im Reproduktionsskript), diese als gelieferten Zugang uebergeben und verlangen, dass entweder `eingang_anlegen()` sofort ablehnt oder kein spaeterer Tageslauf bis zu diesem Tag mit einer Kollision abbricht — gegen alle drei betroffenen Funktionen (`tageslauf`, `cli_fortschreibung --uebernahme`, direkter `ereignisse`-Aufruf).

**Praezisierung des Fix-Vorschlags (merge-session, 2026-09-08, am Validator
nachgelesen).** Der sichere Bereich ist kein Zufall, sondern eine Folge des
Nummernkreis-Validators: `config._pruefe_nummernkreise` erzwingt
`1 <= k <= 99`, Eindeutigkeit und alle-oder-keine; ein Kreis belegt
`k*10 Mio + 1 .. (k+1)*10 Mio - 1`. Solange Kreise gesetzt sind, kann kein
Erzeuger unter oder auf 10 000 000 vergeben. Die Zusicherung des Eingangs
ist damit EIN Vergleich ohne Kopplung an die Config:

    jede importierte police_id <= 10 000 000

Die exakte Form (Pruefung gegen die tatsaechlich belegten Kreise) ist
praeziser, koppelt den Eingang aber an die Config und aendert ihr Urteil,
sobald jemand einen Kreis ergaenzt. Vorschlag: die einfache Form, mit dem
Grund danebengeschrieben.

VORBEHALT, der in den Fix gehoert: Die Garantie gilt nur BEI GESETZTEN
Kreisen. `nummernkreis = None` faellt auf die Erstfassung zurueck (Nummern
nach der Position der Generation); dort liegt kein sicherer Bereich fest.
Der Validator erzwingt alle-oder-keine, nicht "immer". Entweder werden
Kreise Pflicht, oder der Eingang prueft nur dort, wo sie gesetzt sind, und
sagt fuer den Rest hin, dass er nichts weiss — stillschweigend durchlassen
waere die dritte, falsche Moeglichkeit.

Beleg aus der Neugenerierung 2026-09-08: Die PLV-Config setzt alle
vierzehn Kreise; der Tagesstrom ueber zweiunddreissig Jahre liefert
police_id 15 018 201 bis 135 124 701, der uebernommene Bestand liegt bei
7 000 001 aufwaerts — getrennt per Konstruktion, nicht per Groessenordnung.

### T25-01 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** `_fuehrungsprobe_fehler` (`src/rechner_pipeline/gates/abnahmebericht.py:1419-1491`, aufgerufen von A-M4-Erzeugung `abnahmebericht.py:2115-2120` und vom Entscheid `gate_entscheid.py:1144-1155`, dort exakt dieselbe Hilfsfunktion, Zeile 1149-1150 ohne zusaetzliche Pruefung) prueft ausschliesslich: Nachhashen der in `provenienz.eingaben` selbst benannten Dateien (1450-1460), Anwesenheit der Pflichtpfade `PROBE_PFLICHTEINGABEN` (1415-1416, 1461-1470), `schema_version == 1` (1471-1472), `bestanden is True` und `befunde` leer (1473-1477), `anfangszustand in (...)` (1478-1481), `fortschreibung_geprueft is True` (1482-1484), `system == erwartetes_system` (1485-1486) und `suite["bestand_sha256"] in set(eingaben.values())` (1487-1490, entspricht der vom Reviewer zitierten alten Zeile 1415-1418). Nirgends wird `summary`/`zahlen` (vertraege, mit_anfangszustand), `stichtag`, `generation`, `tarifwerk`, `schichten`, `buchungen_geprueft` oder `buchungen_abweichend` geprueft oder verwertet — dabei schreibt der Producer (`gates/fuehrungsprobe.py:417-431`) genau diese Felder.

Deterministische Gegenprobe (`.venv/bin/python`, `tempfile.TemporaryDirectory`, echter Repo-Code, keine Aenderung am Worktree, Skript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t25-01/repro.py`): ein von Hand geschriebenes JSON mit fuenf beliebigen Dateien (kein echtes Parquet, kein echtes Ledger), passenden Hashes und nur den oben genannten Pflichtfeldern — ohne `summary`, `stichtag`, `generation`, `tarifwerk`, `schichten`, `buchungen_geprueft` — direkt gegen `_fuehrungsprobe_fehler` geprueft:
```
fehler = []
akzeptiert (keine Fehler) = True
```
Zweite Gegenprobe (`repro_rolle.py`): `suite["bestand_sha256"]` an den Hash der Fortschreibungs-`ledger.parquet` (falsche Rolle, nicht den Bestand) gebunden — ebenfalls `fehler = []`. Damit ist die Bindung an Zeile 1487-1490 rollenblind, exakt wie vom Reviewer behauptet.

Kontrastprobe im selben File: `_b1_fehler` (1494-1719) tut es richtig — es laedt das Ledger, laesst `lies_und_pruefe_pb1` die produktive P-B1-Engine auf den aktuellen, fall-gebundenen Bytes neu rechnen (1669), vergleicht jeden `summary`-Zaehler gegen das frische Ergebnis (1690-1695) und verlangt fuer die bezeugenden Zaehler `PB1_PFLICHT_POSITIV` explizit `> 0` (1369-1372, 1698-1703, Review T23-05). `_bericht_fehler` (918-1010) baut den HTML-Bericht deterministisch aus dem Renderer-Vertrag neu und vergleicht bytegenau (985-1009). `_fuehrungsprobe_fehler` erreicht keines von beidem: kein Recompute, keine Positivschwelle.

Zusatzbefund: der `baue_bericht`-Renderer referenziert `"fuehrungsprobe"` nirgends (`grep -n fuehrungsprobe abnahmebericht.py` zeigt nur CLI-Argument, Ledger-Eintrag und die Pruefstelle, keinen Report-Baustein) — der Inhalt des Belegs (Zahlen, Stichtag, Generation, Tarifwerk) taucht im an den Menschen gerichteten Abnahmebericht nicht auf; nur der Pass/Fail-Vertrag steuert den Gate-Exitcode.

Bestehende Tests (`tests/test_pk1_am4_beweisvertrag.py:495-...`, `test_ohne_bestandene_fuehrungsprobe_gibt_es_keinen_gruenen_abnahmebericht`) mutieren ausschliesslich einen echten, vom Producer erzeugten Beleg (`bestanden=False`, fremde Suite-Bindung, geloescht, veraenderte Eingabe, fehlende Pflichteingabe) — keiner konstruiert einen vollstaendig freien Beleg wie in der Gegenprobe.

**Stand auf main 10ee765.** Unveraendert. `_fuehrungsprobe_fehler` ist zwischen `fe0e284` und `10ee765` byte-identisch (`diff` gegen `git show fe0e284:...abnahmebericht.py` liefert nur einen Unterschied ausserhalb der Funktion: `_lies_json_beleg` — liest die Datei ein zweites Mal von der Platte — wurde durch `_json_beleg_aus` ersetzt, das auf den bereits gehashten Bytes parst; Commit `31c1caf`, Review T23-01, Block 1). Das schliesst eine TOCTOU-Luecke beim Lesen des Probe-JSON selbst, aendert aber keine einzige der geprueften Bedingungen — Rueckgabewert und Fehlermenge der Funktion sind fuer denselben Input identisch zu fe0e284. Die uebrigen vier Commits, die die Datei seit fe0e284 beruehren (`8725982`, `8cdaf54`, `00fed35`, `294a83d`), betreffen ausschliesslich `PB1_VOLLPROFIL`/`PB1_PFLICHT_POSITIV` (P-B1, Block 3) und Bewegungsjahr/Baender — keiner davon `_fuehrungsprobe_fehler`. `gate_entscheid.py:1149-1150` ruft unveraendert dieselbe Funktion ohne Zusatzpruefung.

**Schaden.** Ein Antragsteller (Mensch oder Agent mit Schreibzugriff auf `<fall>/abgeleitet/berichte/fuehrungsprobe.json`) kann A-M4 einen nie von `gates.fuehrungsprobe` erzeugten, gruenen Beleg vorlegen, ohne dass ein einziger Vertrag, eine einzige Buchung oder eine Tarifwerks-/Stichtags-/Generationsbindung tatsaechlich gegen die Pruefstrecke gelaufen ist — es genuegen fuenf beliebige Dateien mit passenden Hashes und sechs Flags. Da der Berichtsrenderer den Inhalt der Probe nicht darstellt, sieht auch ein menschlicher A-M4-Pruefer im Abnahmebericht selbst nichts davon; er muesste die JSON-Datei separat oeffnen. Konkret bricht damit exakt die Zusage, die die Fuehrungsprobe einfuehren sollte (Freischaltung Schritt 6, Docstring `fuehrungsprobe.py:6-14`): "ob der gefuehrte Bestand die Pruefstrecken-Welt auch benutzt" — im zweiten Baldrian-Fall lagen laut demselben Docstring 550 von 834 Stammsummen in der falschen Welt, bevor die Probe eingefuehrt wurde. Ein formal vorhandener, aber inhaltsleerer Beleg macht diese Klasse von Fehler wieder unsichtbar.

**Schwere.** Zustimmung zu "hoch". Die neue Pflichtdatei ist als Autorisationsgrenze fuer A-M4 gedacht (kein anderer Mechanismus im Bestands-Scope prueft, dass die Fuehrung die abgenommene Welt traegt), aber sie ist durch reine Selbstauskunft ueberwindbar — die Gegenprobe zeigt das mit einem realistisch kleinen Aufwand (ein JSON-Objekt, kein Exploit exotischer Bedingungen). Einschraenkend gegenueber "kritisch": die uebrigen A-M4-Bausteine (Suite, P-B1 mit Recompute) bleiben unabhaengig scharf, ein falscher Fuehrungsprobe-Beleg allein hebt also nicht die gesamte Abnahme auf, sondern genau die Zusage ueber die Fuehrung — was aber die zentral beworbene neue Eigenschaft dieses PRs ist.

**Klasse (Invariante).** Ein Gate, das einen Producer-Beleg als Autorisationsvoraussetzung verlangt, darf nur solche Felder pruefen, die entweder (a) durch erneutes Ausfuehren des Producers auf denselben, fall-gebundenen und gehashten Eingabe-Bytes reproduziert und mit dem Beleg abgeglichen werden, oder (b) als bezeugender Zaehler mit einer Positivschwelle gegen "null/leer bedeutet nie gelaufen" abgesichert sind (wie `PB1_PFLICHT_POSITIV`); jedes Feld, das der Beleg nur BEHAUPTET und das weder nachgerechnet noch gegen eine erzwungene Mindestabdeckung geprueft wird, ist vom Antragsteller selbst frei waehlbar und damit kein Beweis — ein Antragsteller-erstelltes Objekt mit passenden Hashes und den wenigen abgefragten Flags besteht dieselbe Pruefung wie ein echter Producer-Lauf.

**Weitere Stellen mit demselben Muster.** Keine zweite Instanz DERSELBEN Schwaeche (schwacher Flag-Consumer statt Recompute) innerhalb von `abnahmebericht.py`/`gate_entscheid.py` gefunden — gesucht wurde nach allen `def _*_fehler`-Funktionen der Datei (`grep -n "def _.*fehler"`): `_b1_fehler` und `_bericht_fehler` folgen dem korrekten Muster (Recompute bzw. bytegenauer Wiederaufbau), `_transformationsvertrag_fehler`/`_registrierte_quellenbindung_fehler` wurden nicht im Detail gegengeprueft (ausserhalb des Zeitbudgets dieser Triage). Fuer Korrekturschicht/Verankerung existiert in `abnahmebericht.py`/`gate_entscheid.py` derzeit ueberhaupt KEIN Belief-Consumer dieser Form (kein Treffer fuer "schicht" in `gate_entscheid.py` ausserhalb einer Kommentarzeile) — das ist kein Beispiel derselben Klasse, sondern der noch groessere, in T25-05 separat behandelte Defekt (Abwesenheit statt Schwaeche der Pruefung).

**Fix-Umfang.** M. Konkret: (1) `_fuehrungsprobe_fehler` bekommt ein `FUEHRUNGSPROBE_PFLICHT_POSITIV`-Analogon zu `PB1_PFLICHT_POSITIV` fuer die im Producer bereits geschriebenen Zaehler (`vertraege`, `mit_anfangszustand`, `sum(buchungen_geprueft.values())`) mit Positivschwelle sowie eine Pflichtbindung von `stichtag`, `generation`, `tarifwerk` gegen `erwartetes_system`/die Fall-Parameter (analog zur `system`-Bindung, die bereits existiert); (2) die Suite-Bindung wird rollenscharf (`eingaben.get(<Bestand-Rollenname>) == suite["bestand_sha256"]` statt `in set(eingaben.values())`), wie bei `_b1_fehler`s `rollen`-Mechanik; (3) optional: der Berichtsrenderer nimmt `summary`/Zahlen des Probe-Belegs in den fuer den Menschen sichtbaren Abnahmebericht auf. Test fuer die KLASSE: ein Test, der wie meine Gegenprobe einen VOLLSTAENDIG von Hand geschriebenen Beleg (kein `gates.fuehrungsprobe`-Lauf) mit korrekten Hashes und den bisher geprueften Flags konstruiert, aber `summary`/`buchungen_geprueft`/`stichtag`/`generation`/`tarifwerk` weglaesst oder auf 0/leer setzt, und erwartet, dass `_fuehrungsprobe_fehler` das ablehnt — ergaenzend ein Test mit rollenvertauschter `bestand_sha256`-Bindung wie in `repro_rolle.py`. Beruehrt einen Gate-Vertrag (A-M4-Pflichtbeleg) und moeglicherweise das Fachkonzept `dev-docs/freischaltung-uebernommener-bestand.md` (Schritt 6) — Entscheid des Maintainers vor Umsetzung noetig, insbesondere ob eine Mindestabdeckung fachkritischer Ereignistypen in `buchungen_geprueft` fachlich sinnvoll definierbar ist (das kann ueber den reinen Nicht-Null-Schwellwert hinausgehen und beruehrt dann auch das Fachkonzept selbst).

### T25-02 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Datei/Zeilen sind auf 10ee765 identisch zu den Reviewer-Angaben (Datei seit dem geprueften Stand unveraendert, siehe unten) — keine Zuordnung alt->neu noetig.

Code: `src/rechner_pipeline/gates/fuehrungsprobe.py:519-528` (`main()`, Block "fortschreibung") liest drei Pflicht-/Optionaltabellen in das Dict `fortschreibung` (`ledger`, `scheiben`, `historie`, Zeilen 523-527) und ruft danach Zeile 528 `lies(lauf / "bestand_gesamt.parquet", STAMM_NAMES, False)` als **freistehenden Ausdruck** auf — der Rueckgabewert (das gelesene DataFrame, der Endbestand) wird an keine Variable gebunden und existiert nach dieser Zeile nicht mehr. `grep -n 'fortschreibung\[' fuehrungsprobe.py` liefert im ganzen File nur einen Treffer, Zeile 356 (`f_ledger: pd.DataFrame = fortschreibung["ledger"]`); `fortschreibung["historie"]`/`fortschreibung.get("historie")` kommt in `pruefe_fuehrung()` (Zeilen 102-431) kein einziges Mal vor — die Endhistorie wird gelesen, in `eingaben` gehasht (macht sie zu einer scheinbar geprueften Eingabe der Provenienz), aber nirgends inhaltlich verglichen. Der Abschnitt "4. Buchungen der Fortschreibung" (Zeilen 352-415) prueft ausschliesslich Betraege einzelner STO/PEX/TOD/ABL-Buchungen aus `fortschreibung["ledger"]` gegen die Pruefstrecken-Engine — nie den resultierenden Endzustand selbst.

Konsumentenseite: `abnahmebericht.py:1419-1491` (`_fuehrungsprobe_fehler`, aufgerufen von `gate_entscheid.py:1144-1154` fuer A-M4 und von `abnahmebericht.py:2115-2125` fuer den Abnahmebericht) prueft: Hash-Gleichheit jeder in `eingaben` gelisteten Datei mit den *aktuellen* Bytes (Zeilen 1450-1460 — schuetzt nur gegen Austausch NACH dem Probelauf, nicht gegen falsche Werte, die die Probe von Anfang an gelesen hat), Pflichteingaben `PROBE_PFLICHTEINGABEN = ("bestand.parquet", "historie.parquet", "ledger.parquet", "uebernahme.json")` (Zeile 1415) nur fuer das Uebernahme-Verzeichnis plus `{fortschreibung}/ledger.parquet` (Zeile 1465) — `bestand_gesamt.parquet` und `historie.parquet` der Fortschreibung sind nicht einmal als Pflichteingabe verlangt —, `bestanden`/`befunde`/`anfangszustand`/`fortschreibung_geprueft`/`system`/`bestand_sha256`. Kein Feld prueft Inhalte von Endbestand oder Endhistorie, keines verlangt eine Mindestzahl je Buchungsart aus `GEPRUEFTE_BUCHUNGEN = ("STO","PEX","TOD","ABL")` (Zeile 85) — `buchungen_geprueft` mit lauter Nullen besteht ebenso wie mit hoher Abdeckung.

**Empirische Gegenprobe mit echtem Code und den echten Baldrian-2-Fallartefakten** (nur lesend aus `~/git/rechner-pipeline/faelle/baldrian-klv-tg2015-lauf2` kopiert nach `tempfile.mkdtemp`, `.venv/bin/python` des Worktrees, kein pytest, Fall-Original unangetastet; Skripte unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t25-02/{repro.py,baseline.py,repro2.py}`):

1. Fall-Eingaben kopiert, Schichtbeleg frisch mit `gates.verankerung_belegen` auf dem AKTUELLEN Systemstand neu erzeugt (der archivierte Beleg traegt noch `f7c545d` und wird von `aktuartest_lauf._schichten` gegen den aktuellen Stand abgelehnt — kein Teil des Befunds, nur eine Nebenbedingung der Reproduktion).
2. Baseline (unmutiert), echter `python -m rechner_pipeline.gates.fuehrungsprobe`-Aufruf mit denselben Parametern wie im echten Lauf (`provenienz.parameter` des echten `fuehrungsprobe.json`): `exit=0, bestanden=True, 0 Befunde`.
3. Mutierte Kopie: `bestand-nach/bestand_gesamt.parquet`, Police 7000001, `sum_insured` 43000.0 -> 1042999.0 (+999999); `bestand-nach/historie.parquet`, Police 7000002, `status_code` 'ABL' -> 'XXX' (ein Wert ausserhalb von `STATUS_CODE_VALUES = ("POL","PEX","BU","STO","TOD","ABL")`, models/bestand.py:109 — physisch vom Schema akzeptiert, weil `read_portfolio` nur Spaltennamen/Arrow-Typen prueft, keine Wertebereiche, parquet_io.py:178-193). Derselbe Aufruf: `exit=0, bestanden=True, 0 Befunde` — identisch zur Baseline. Beide mutierten Dateien stehen unter `provenienz.eingaben` (Hash gebunden, Nachweis, dass sie gelesen wurden), tragen aber keinen einzigen Befund bei. Systemblock des erzeugten Belegs: `{"branch":"main","commit":"10ee76541dbbadd213130d6900963a2ac25f00f7","dirty":"nein"}` — echt aktueller Stand, kein Altartefakt.
4. Den echten A-M4-Konsumenten `_fuehrungsprobe_fehler()` direkt gegen den mutierten Beleg aufgerufen: `consumer_errors = []`.

Damit reproduziert `producer_exit=0 / bestanden=True / consumer_errors=[]` exakt die Reviewer-Reproduktion, unabhaengig, mit echten Werkzeugen, auf 10ee765.

**Weiterer Beweis (Ereignisabdeckung leer zulaessig, zweite Reviewer-Behauptung):** im echten Fallartefakt tragen 330 Policen eine neue Erhoehungsscheibe nach dem Stichtag (`bestand-nach/scheiben.parquet`, `erhoehung_datum > 2026-01-01`); `fortschreibung["scheiben"]` wird nur ueber `neue_je_police` (Zeilen 358-362) in die Buchungspruefung eingespeist, wenn *danach* eine STO/PEX/TOD/ABL-Buchung fuer dieselbe Police existiert (Zeile 374 ff.). Eigene Auswertung: **alle 330** dieser Policen haben im echten Fall keine einzige spaetere STO/PEX/TOD/ABL-Buchung — ihre neuen Scheiben (Stammsumme, gamma1, Erhoehungsjahr) sind zu 100 % ungeprueft, obwohl `scheiben.parquet` ebenfalls gehasht in `eingaben` steht.

**Stand auf main 10ee765.** Unveraendert seit dem geprueften Stand. `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/gates/fuehrungsprobe.py` ist leer. `git blame -L519,529` zeigt: Zeilen 519-528 (inkl. der beiden fraglichen Stellen) stammen vollstaendig aus Commit `67a0b5e0` ("feat(gates)!: die Fuehrungsprobe — der gefuehrte Bestand gegen die Pruefstrecke, Pflichtbeleg von A-M4 im Bestands-Scope, Freischaltung Schritt 6"); die Konsumentenseite `_fuehrungsprobe_fehler` in `abnahmebericht.py` stammt aus `c47a70a` ("fix(gates)!: der Abnahmebericht hasht jede Eingabe der Fuehrungsprobe nach..."). Beide Commits sind laut `git merge-base --is-ancestor` Vorfahren von `fe0e284`, und `fe0e284` ist Vorfahr von `10ee765` — der Befund war beim Review bereits in dieser Form vorhanden und ist auf main seither durch keinen der 12 dazwischenliegenden Freischaltung-Commits noch durch T23/T24-Block-Commits beruehrt worden.

**Schaden.** Die Fuehrungsprobe ist laut eigenem Docstring genau dafuer gebaut, den historisch bereits eingetretenen Fall zu verhindern, dass "im zweiten Baldrian-Fall 550 von 834 Stammsummen in der falschen Welt lagen" (fuehrungsprobe.py:12-13) — obwohl P-B1 (Gate `pb1_ledger`, ebenfalls Pflichtbelegrolle) bereits lief. P-B1 prueft laut eigenem Docstring (bestand_validate.py:1-40) Schema, interne Bewegungs- und Betragsidentitaeten (Ledger konsistent mit Bestand) sowie Plausibilitaetsbaender — keine dieser Pruefungen vergleicht gegen die unabhaengig hergeleitete Pruefstrecken-Welt. Ein Fehler, der sich selbstkonsistent ueber Bestand, Ledger und Historie fortpflanzt (z. B. ein falscher Tarifwerks-Schalter oder ein Formelfehler in der Fortschreibungs-Engine selbst, angewandt auf den GESAMTEN Bestand statt eine einzelne Zeile handveraendert), entginge damit sowohl P-B1 als auch — wie hier gezeigt — der Fuehrungsprobe. Konkret ungeprueft bleiben: der komplette Endbestand (`bestand_gesamt.parquet`, jede Stammsumme, jeder Status jeder Police am Horizont), die komplette Endhistorie, und praktisch jede Erhoehungsscheibe, die die Fortschreibung nach dem Stichtag neu bildet, sofern die betroffene Police in der beobachteten Historie keine weitere Buchung mehr ausloest (im echten Fall: 100 % der 330 betroffenen Policen). A-M4 akzeptiert einen solchen Bestand als Pflichtbeleg dafuer, dass "die Fuehrung genau die Welt traegt, die die Abnahmen geprueft haben" — dieser Beleg ist fuer den gefuehrten Endzustand nicht eingeloest.

**Schwere.** Zustimmung zu "hoch". Die Fuehrungsprobe ist die einzige im Bestands-Scope verpflichtende Instanz, die den gefuehrten Bestand gegen eine unabhaengige Pruefstrecke stellt — fuer genau die Klasse von Fehler, die den Bau des Features ausgeloest hat, bleibt sie wirkungslos, und der falsche Beleg ist keine theoretische Moeglichkeit, sondern mit dem echten Produktionsartefakt binnen Minuten reproduzierbar. Eine Einschraenkung gegenueber "kritisch": die konkrete Reviewer-Illustration `status_code = 'XXX'` ist ein Wert ausserhalb des Vokabulars und wuerde — waere sie tatsaechlich von der Fortschreibungs-Engine erzeugt worden statt nachtraeglich per Hand eingetragen — von P-B1s `validate_statushistorie` (models/bestand.py:587-588, Enum-Pruefung gegen `STATUS_CODE_VALUES`) abgefangen, sofern P-B1 auf demselben `bestand-nach` laeuft; ob die Belegrolle `pb1_ledger` in A-M4s Bestands-Scope tatsaechlich `bestand-nach` oder nur die Uebernahme bindet, habe ich nicht abschliessend geklaert. Die zweite Mutation (Stammsumme in `bestand_gesamt.parquet`) und vor allem die 330-Policen-Beobachtung zu den Erhoehungsscheiben sind davon unberuehrt — dort existiert kein Fangnetz, weder in P-B1 noch in der Fuehrungsprobe. "Hoch" ist damit die richtige, nicht zu niedrige Einstufung; fuer "kritisch" fehlt der Nachweis, dass eine STILLE (nicht laut Schema erkennbare) Verfaelschung tatsaechlich unentdeckt bliebe, wenn auch P-B1 korrekt gegenlaeuft — das habe ich nur fuer den Ledger/Bestand-Teil, nicht erschoepfend fuer jede denkbare Fehlerform geprueft.

**Klasse (Invariante).** Eine Pruefung, die eine Tabelle einliest und sie dadurch in ihre gehashte Provenienz aufnimmt (und damit den Anschein erweckt, ihr Inhalt sei Teil des geprueften Behaupteten), muss jeden Datensatz dieser Tabelle tatsaechlich gegen einen unabhaengig hergeleiteten Erwartungswert stellen — ein Wert, der nur DANN geprueft wird, wenn zufaellig ein anderes, unabhaengiges Ereignis (hier: eine spaetere Buchung) ihn ohnehin schon anfasst, ist fuer jede Police ohne ein solches Ereignis faktisch ungeprueft, auch wenn der Beleg ihn als gelesene/gehashte Eingabe ausweist.

**Weitere Stellen mit demselben Muster.**
- `src/rechner_pipeline/gates/fuehrungsprobe.py:357-362` und `:374-382` (`neue_je_police`/`f_scheiben`): Erhoehungsscheiben, die die Fortschreibung nach dem Stichtag bildet, werden nur geprueft, wenn fuer dieselbe Police spaeter eine STO/PEX/TOD/ABL-Buchung auftritt — im echten Fall 0 von 330 betroffenen Policen erfuellen das (siehe "Weiterer Beweis" oben). Gehoert zur selben Funktion wie der Reviewer-Fund, ist aber ein eigenstaendiger dritter Kanal (nach Endbestand und Endhistorie) mit demselben Muster.
- Gezielt gesucht (aber nichts Neues ausserhalb dieser Funktion gefunden): `grep -rn "^\s*lies(" src/rechner_pipeline/gates/*.py` liefert nur die eine Stelle (Zeile 528); die anderen Freischaltung-Producer (`bestand_uebernehmen.py`, `verankerung_belegen.py`, `migrationssuite_lauf.py`, `aktuartest_lauf.py`) haben keinen freistehenden Lese-Aufruf dieser Form. Eine vollstaendige Pruefung, ob JEDE in `provenienz.eingaben` gehashte Datei bei jedem anderen Gate auch inhaltlich gegen einen Erwartungswert laeuft (statt nur strukturell/schema-seitig), habe ich nicht erschoepfend durchgefuehrt — nur diese eine Funktion.

**Fix-Umfang.** L. Deckt sich mit dem eigenen Abnahmekriterium des Reviewers. Konkret: (1) `bestand_gesamt.parquet` tatsaechlich in `fortschreibung["bestand_gesamt"]` ablegen und in einem neuen Abschnitt von `pruefe_fuehrung()` JEDE Police auf eine unabhaengig hergeleitete Soll-Stammsumme/-Status am Fortschreibungshorizont stellen (dieselbe Ableitung, die Abschnitt 2 bereits fuer den Anfangszustand nutzt, weiter- statt neu gerechnet bis zum Horizont); (2) `fortschreibung["historie"]` gegen die erwartete Statuskette je Police vergleichen (terminaler Status, Datum), nicht nur `uebernahme["historie"]` fuer PEX; (3) JEDE Zeile von `fortschreibung["scheiben"]` unabhaengig von einer spaeteren Buchung pruefen (analog zum bestehenden Scheiben-Check in Abschnitt 2), nicht nur die ueber `neue_je_police` indirekt exerzierten. Test der KLASSE: Erweiterung von `tests/test_baldrian2_e2e.py::test_die_fuehrungsprobe_besteht_und_faellt_bei_fremder_welt` um mindestens drei weitere "Stoerungen" wie die vorhandenen vier (Zeilen 373-413), gezielt an Policen OHNE spaetere Buchung: (a) Stammsumme in `bestand_gesamt`/Fortschreibung, (b) Statuscode in der Endhistorie, (c) Stammsumme einer neuen Erhoehungsscheibe nach dem Stichtag — jedes Mal mit `assert not rot["bestanden"]`. Beruehrt keinen Pydantic-Schema-Vertrag, aber den Fachvertrag von A-M4s Bestands-Scope ("Fuehrungsprobe = Pflichtbeleg, dass die Fuehrung die gepruefte Welt traegt") und vermutlich `PROBE_PFLICHTEINGABEN`/die Provenienz-Bindung in `abnahmebericht.py` — Umfang und Breaking-Charakter vergleichbar mit den bereits gelandeten T23/T24-"!"-Commits; Entscheid des Maintainers vor Umsetzung.

### T25-03 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Auf 10ee765 (Worktree `rechner-pipeline-t24`) und mit den echten Artefakten des Falls `baldrian-klv-tg2015-lauf2` im Haupt-Tree geprueft (nur gelesen, nichts veraendert). Reviewer-Zeilenangaben (Basis fe0e284) den heutigen Zeilen zugeordnet.

1. `src/rechner_pipeline/gates/fuehrungsprobe.py` ist zwischen fe0e284 und 10ee765 **byte-identisch** (`git diff fe0e284 10ee765 -- .../fuehrungsprobe.py` liefert nichts). Der zitierte Block liegt exakt auf denselben Zeilen 312-350: `if schichtbeleg:` (314) macht die gesamte Schichtpruefung optional; innerhalb des Blocks wird nur `police_id`/`rho` verglichen (345-350: `tabelle_rho = {int(z["police_id"]): float(z["rho"]) ...}`, `if pid in tabelle_rho and tabelle_rho[pid] != param.rho`). Die Vollstaendigkeitspruefung (340) rechnet nur `set(schicht_je_police) - set(tabelle["police_id"])` (Belegrolle -> Tabelle); die Gegenrichtung (Tabelle -> Beleg) wird nirgends gebildet — Zeilen der Tabelle ohne Gegenstueck im Beleg sind unsichtbar.

2. Ich habe die reale, bereits produzierte `schichten.parquet` des Falls (Endwelt nach Fortschreibung) gelesen:
```
df.columns = ['police_id', 'schichttyp', 'verankerungszustand', 'verweildauer', 'rho',
              'formfunktion', 'formparameter', 'vererbend', 'kohorte',
              'in_ueberschuss', 'in_zzr', 'rumpfmonate']
```
Alle vom Reviewer genannten Groessen (Formfunktion, Formparameter, Vererbung/`vererbend`, Heilungszustand/`verankerungszustand`) stehen bereits in genau dieser Tabelle, die `fuehrungsprobe.py` liest — der Code liest daraus aber nur `police_id` und `rho`. `kern/korrekturschicht.py:196-208` (Klasse `Schichtparameter`) und `als_beleg()` (Zeilen 235-247) zeigen, dass ein vollstaendiger Feldvergleich mit den vorhandenen Daten trivial moeglich waere — er wird nur nicht gemacht.

3. `PROBE_PFLICHTEINGABEN` (heute Zeile 1415-1416, fe0e284: 1343-1344, Text unveraendert) = `("bestand.parquet", "historie.parquet", "ledger.parquet", "uebernahme.json")` — kein Schicht-/Verankerungsartefakt Pflicht. `_fuehrungsprobe_fehler` (1419-1489) prueft `probe.get("bestanden")`, `anfangszustand`, `fortschreibung_geprueft`, `system`, Bestandsbindung — an keiner Stelle `probe.get("schichten")` oder ob `--schicht` ueberhaupt gesetzt war.

4. `PB1_VOLLPROFIL` (heute Zeile 1349, fe0e284: 1331, Text unveraendert) = `frozenset({"portfolio", "historie", "ledger", "config"})` — ohne `schichten`/`verankerung`. Die Positivliste `erlaubte_rollen` (heute Zeile 1555, fe0e284: 1477, **byte-identischer Block**, per `diff` bestaetigt) = `{"portfolio", "historie", "scheiben", "ledger", "merkmale", "config"}` — auch hier fehlen `schichten`/`verankerung`; jeder P-B1-Beleg, der diese Rollen fuehrt, wird mit `"P-B1-Ledger.summary.eingangsrollen ist ungueltig"` abgelehnt (`abnahmebericht.py:1554-1561`).

5. Gegenprobe mit dem **echten, bereits gruen gelaufenen** P-B1-Beleg des Falls auf dem fortgeschriebenen Bestand (`abgeleitet/diagnostics-nach/bestand_validate.gate.json`, `status: passed`, `system.commit: f7c545d...`, zwischen fe0e284 und 10ee765 und fuer diesen Code-Pfad unveraendert):
```
rollen = summary["eingangsrollen"]  # enthaelt "schichten", "verankerung"
erlaubte_rollen = {"portfolio","historie","scheiben","ledger","merkmale","config"}
-> set(rollen) <= erlaubte_rollen: False
-> nicht erlaubt: {'schichten', 'verankerung'}
-> "P-B1-Ledger.summary.eingangsrollen ist ungueltig" -> True
```
Ein real erzeugtes, vollstaendiges, gruenes P-B1-Vollprofil der materialisierten Endwelt wird von A-M4s eigener Positivliste strukturell zurueckgewiesen — kein Konstrukt, sondern mit den Bytes des echten Laufs gezeigt.

6. Real-Produktions-Beleg, nicht nur Testfixture: `abgeleitet/diagnostics/abnahmebericht.gate.json` (der tatsaechlich gelaufene, `status: passed` A-M4-Beleg des Falls) bindet als `input_hashes["abgeleitet/diagnostics/bestand_validate.gate.json"]` genau den P-B1-Beleg **vor** der Fortschreibung (`abgeleitet/diagnostics/bestand_validate.gate.json`, dessen `eingangsrollen` **kein** `schichten`/`verankerung` enthaelt) — nicht den nach-Beleg mit Schichtrollen. Das deckt sich mit dem Default-Wiring in `abnahmebericht.py:1758-1761` (`--pb1-ledger` Default `<fall>/abgeleitet/diagnostics/bestand_validate.gate.json`, nicht `diagnostics-nach`).

7. Root-Ursache sichtbar: `bestand/vorbedingungen.py:146-147` (`erlaubt = {"portfolio", "historie", "scheiben", "ledger", "merkmale", "config", "schichten", "verankerung"}`, Funktion `lies_und_pruefe_pb1`) UND `gates/bestand_validate.py:165-171` (`--schichten`/`--verankerung` als CLI-Rollen) wurden bei Einfuehrung der Korrekturschicht (Freischaltung Schritt 5, Commit `7b58147`) korrekt erweitert. Die **dritte**, unabhaengige Aufzaehlung derselben Rollenmenge in `abnahmebericht.py:1555` wurde dabei vergessen — dasselbe Muster wie T23-06 (dieselbe Fachregel an mehreren Stellen durchgesetzt, eine vergessen).

8. `test_baldrian2_e2e.py:165-176` erzeugt `pb1` (ohne Schicht) VOR der Schichterzeugung; `pb1_nach` (Zeile 228-236, MIT `--schichten`/`--verankerung`) erst danach. `abnahmebericht.main`/A-M4 wird in dieser Datei **an keiner Stelle aufgerufen** (kein Import, kein `abnahmebericht`-Treffer) — bestaetigt, dass kein Repo-Test je einen P-B1-Vollprofil-Beleg mit Schichtrollen durch A-M4 laufen laesst. `test_die_fuehrungsprobe_besteht_und_faellt_bei_fremder_welt` (Zeile 261-424) konstruiert vier "fremde Welt"-Stoerungen (Stornobetrag, Schalter, Grundvertrag, Stammsumme) — keine davon mutiert ein Schichtfeld ausser `rho`; `test_am4_vollprofil_t23.py` enthaelt ebenfalls keinen Treffer fuer `schichten`/`verankerung`.

**Stand auf main 10ee765.** Unveraendert. `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/gates/fuehrungsprobe.py` ist leer (Datei byte-identisch). `abnahmebericht.py` hat fuenf dazwischenliegende Commits (`31c1caf`, `8725982`, `8cdaf54`, `00fed35`, `294a83d`), die `PB1_VOLLPROFIL`/`PB1_PFLICHT_POSITIV`/Bewegungsjahre/Baender betreffen (T23-01, T23-04, T23-05) — die Zeilen verschieben sich dadurch (1331->1349, 1343->1415, 1477->1555), der **Inhalt** von `PROBE_PFLICHTEINGABEN`, `PB1_VOLLPROFIL` und `erlaubte_rollen` ist jedoch per Diff unveraendert. Keiner dieser fuenf Commits fuegt `schichten`/`verankerung` einer der drei Listen hinzu. Der Befund ist keine historische Beobachtung, sondern gilt fuer den aktuellen `main`-Stand unveraendert.

**Schaden.** Wer auf dem freigeschalteten Bestand eine Korrekturschicht materialisiert (Freischaltung Schritt 5), kann am A-M4-Uebergang entweder (a) die Fuehrungsprobe ganz ohne `--schicht` fahren lassen — sie besteht trotzdem, ohne die Schicht ueberhaupt zu betrachten — oder (b) einen ehrlichen P-B1-Vollprofil-Beleg MIT Schicht-/Verankerungsrollen erzeugen, der dann von A-M4 selbst als "ungueltig" verworfen wird, sodass zwangslaeufig der VOR-Beleg (ohne Schicht) gebunden bleibt — was der reale, bereits gelaufene Baldrian-2-Fall genau so tut. In beiden Faellen bestaetigt das menschliche Gate A-M4 eine Migration, deren zentrales neues fachliches Element (Korrekturschicht: Formfunktion, Formparameter, Vererbung, Heilungszustand, Vollstaendigkeit) nicht Teil des gepruefte Beweises ist. Selbst wenn `--schicht` gesetzt ist, genuegt ein unveraenderter `rho`-Wert bei beliebig manipulierten anderen Schichtparametern (z. B. `formfunktion`, die die kuenftige Storno-/Ablaufabwicklung veraendert), um die Probe zu bestehen — die Daten dafuer liegen unbenutzt in derselben Tabelle. Ein falscher Beleg wird moeglich: "die gefuehrte Welt entspricht der abgenommenen Welt" wird bezeugt, obwohl die Korrekturschicht weder vollstaendig noch inhaltlich geprueft wurde.

**Schwere.** Zustimmung zu "hoch". Begruendung: (a) Es ist kein Konstrukt — mit den echten Bytes des laufenden Baldrian-2-Falls gezeigt, dass der tatsaechlich gruene A-M4-Beleg an den VOR-Beleg gebunden ist und ein gueltiger, vollstaendiger NACH-Beleg mit Schichtrollen strukturell abgelehnt wird. (b) Betroffen ist genau die vom Reviewer benannte Kernzusage des Branches ("A-M4 laesst genau die anschliessend produktiv gefuehrte Welt zu"). (c) Die Root-Ursache ist eine bekannte, an anderer Stelle im selben Modul (`vorbedingungen.py`) bereits korrekt gepflegte Rollenmenge, die hier ein drittes Mal dupliziert und nicht mitgezogen wurde — dieselbe Klasse von Fehler wie T23-06. (d) Drei voneinander unabhaengige Schwachstellen (Beleg optional, nur `rho` verglichen, nur eine Vollstaendigkeitsrichtung) muessten alle gleichzeitig geschlossen sein, damit die Zusage haelt; aktuell ist keine davon geschlossen. Einschraenkend gegenueber "kritisch": der Schaden liegt am Beweis-/Nachweislayer von A-M4, nicht (nach bisherigem Befund) an der eigentlichen Buchungslogik der Korrekturschicht selbst (das ist Gegenstand anderer T25-Befunde zur Storno-/RED-Absorption). "Hoch" ist zutreffend.

**Klasse (Invariante).** Wird eine neue fachliche Rolle (hier: `schichten`/`verankerung`) an der Quelle eines Belegs (Producer-CLI, interne Leseerlaubnis) korrekt eingefuehrt, muss JEDE nachgelagerte, unabhaengig gepflegte Aufzaehlung derselben Rollenmenge (Pflichtprofil, Positivliste, Pflichteingaben) im selben Zug mitgezogen werden — sonst faellt die neue Welt entweder durch ein zu enges Pflichtprofil aus dem Beweis heraus (die Rolle wird nie verlangt) oder durch eine zu enge Positivliste aus dem Beweis herausgeworfen (ein ehrlicher Vollbeleg wird als ungueltig abgelehnt); beide Formen sehen im gruenen Beleg identisch aus wie "Rolle war fachlich nicht noetig".

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/bestand/vorbedingungen.py:146-147` (`erlaubt`-Menge in `lies_und_pruefe_pb1`) — Gegenbeispiel der korrekten Pflege: enthaelt `schichten`/`verankerung` bereits seit Freischaltung Schritt 5; zeigt, dass die Regel bekannt ist und nur in `abnahmebericht.py` nicht mitgezogen wurde.
- `src/rechner_pipeline/gates/abnahmebericht.py:2199-2208` (`summary["pb1_umfang"]`, `bewegungskonto_geprueft`) — derselbe "was wurde tatsaechlich geprueft"-Gedanke, hier aber nur fuer `"ledger" in pb1_rollen` gebaut; `schichten`/`verankerung` sind auch in dieser dritten, separaten Sichtbarkeits-Instanz nicht vorgesehen.
- `src/rechner_pipeline/gates/abnahmebericht.py:1415-1416` (`PROBE_PFLICHTEINGABEN`) — dieselbe Fehlerklasse ein zweites Mal im selben Modul: die Fuehrungsprobe selbst erzwingt keine Schicht-Pflichteingabe, obwohl `fuehrungsprobe.py` sie lesen kann.
- `src/rechner_pipeline/gates/gate_entscheid.py:1144-1150` — ruft `abnahmebericht._fuehrungsprobe_fehler` unveraendert weiter; die Luecke erreicht damit auch die menschliche Entscheidungsvorlage (A-M4-Snapshot) ohne zusaetzliche Bremse.
- Gesucht (kein Treffer): `grep -rn "korrekturschicht\|Korrekturschicht" src/rechner_pipeline/gates/abnahmebericht.py src/rechner_pipeline/gates/gate_entscheid.py` — keine weitere, unabhaengige Schicht-Vollstaendigkeitspruefung im A-M4-Pfad vorhanden.

**Fix-Umfang.** M, mit Tendenz zu L wegen Gate-Vertrag. Konkret: (1) die drei unabhaengigen Rollen-Aufzaehlungen (`bestand_validate.py`-CLI, `vorbedingungen.py:erlaubt`, `abnahmebericht.py:erlaubte_rollen`) auf eine gemeinsame Konstante ziehen (z. B. `bestand/pb1_rollen.py:PB1_ROLLEN`), damit eine neue Rolle nur an einer Stelle eingetragen werden muss; (2) `PB1_VOLLPROFIL` und `PROBE_PFLICHTEINGABEN` um eine Bedingung erweitern: liegt im Uebernahme-/Fortschreibungsverzeichnis eine materialisierte `schichten.parquet`, sind `schichten`/`verankerung` Pflichtrollen des P-B1-Vollprofils und `schichten.parquet`/`verankerung.parquet` Pflichteingaben der Fuehrungsprobe — Entscheid des Maintainers, weil dies wie die vorangegangenen T22-01/T23-04/T23-05-Aenderungen ein brechender Gate-Vertrag ist; (3) `fuehrungsprobe.py:345-350` ersetzt den `rho`-Nurvergleich durch einen Vergleich aller Felder von `Schichtparameter.als_beleg()` gegen die entsprechende Tabellenzeile UND ergaenzt die Gegenrichtung (`set(tabelle["police_id"]) - set(schicht_je_police)` als Befund, wenn nicht leer). Test der KLASSE: (a) ein P-B1-Vollprofil-Beleg mit `schichten`/`verankerung`-Rollen (wie der reale `diagnostics-nach`-Beleg des Falls) muss von A-M4 als gueltiger Pflichtbeleg akzeptiert werden, statt mit "eingangsrollen ist ungueltig" abgelehnt zu werden; (b) eine Fuehrungsprobe mit unveraendertem `rho`, aber mutiertem `formfunktion` oder `verankerungszustand` einer Police muss `bestanden=False` liefern (Ergaenzung der bestehenden "vier Stoerungen" in `test_baldrian2_e2e.py`); (c) eine `schichten.parquet` mit einer Zeile ohne Gegenstueck im Schichtbeleg muss einen Befund ausloesen.

### T25-04 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Empirisch auf 10ee765 reproduziert (`.venv/bin/python`, `tempfile.mkdtemp()`, keine Aenderung am Worktree, Skript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t25-04/repro.py`):

1. *Codebeweis Producer* (`src/rechner_pipeline/gates/verankerung_belegen.py`): `main()` baut `zeilen_schichten` **nur** aus `beleg["schichten"]` — den `getragen`en Vertraegen aus `baue_schichtbeleg()` (Zeilen 225-243: `if e.getragen: schichten[...] = ...; else: befunde.append(...)`) — und schreibt sie unbedingt (Zeilen 428-442, `write_portfolio(tabelle, ueber / "schichten.parquet")` bei Zeile 440). Erst danach, in einem voellig getrennten Block (Zeilen 470-484), wird `out` (die JSON-Beleg-Datei) geschrieben und `beleg["befunde"]` geprueft (Zeilen 479-483: `if beleg["befunde"]: ... return 1`). Deckt sich inhaltlich exakt mit den Reviewer-Zeilen 417-430/469-473 der vor dem Merge geprueften Fassung (478 statt heute 488 Zeilen; Verschiebung ausschliesslich durch den unten belegten TOCTOU-Fix, nicht durch eine inhaltliche Aenderung an dieser Sequenz).
2. *Deterministische Gegenprobe* (zwei Vertraege, einer mit `monate_ta` genau am Ablauf -> `migrationszugang.py:224-250` liefert dafuer `parameter=None`, `befund="Verankerung am Ablauf: ..."`, kein Schichteintrag):
   ```
   summary: {'vertraege': 2, 'getragen': 1, 'befunde': 1, ...}
   schichten.parquet existiert bereits: True
   Zeilen in schichten.parquet: [7000001]
   producer_exit = 1 (1 = rot, gefaellt NACH dem Schreiben oben)
   ```
3. *Konsument `aktuartest_lauf._schichten()`* (Zeilen 305-395): prueft `roh.get("provenienz")`, `systemstand`, und je Eintrag in `prov["eingaben"]` den SHA-256 (Zeilen 344-376) — **kein** Zugriff auf `roh["befunde"]` oder `roh["summary"]` im gesamten Funktionskoerper. Eigener Nachweis mit dem oben erzeugten (roten) Beleg:
   ```
   beleg['befunde'] (im JSON vorhanden): [{'police_id': 7000002, 'befund': 'Verankerung am Ablauf: ...'}]
   consumer_accepted (police_ids): ['7000001']
   ```
4. *`validate_schichten()`* (`src/rechner_pipeline/models/bestand.py:1503-1556`): prueft nur `set(schichten.police_id) - set(verankerung.police_id)` ("schichten ohne verankerung", Zeile 1537-1540) — nie die Gegenrichtung. Eigener Nachweis mit `schichten` = 1 Zeile, `verankerung` = 2 Zeilen (beide verankert): `Fehlerliste: []`.
5. *Auswirkung ueber A-M1 hinaus* (nicht im Reviewer-Text explizit, aber derselbe Mechanismus): `gates/aktuartest_lauf.py:260-282` (`_schicht_fuer`) liefert fuer eine Police ohne Eintrag in `schichten` schlicht `None` weiter, `_schicht_felder(None)` (Zeilen 285-302) erzeugt daraus **keine** `schicht`-Kwarg — die `Vertragspruefung` traegt `schicht=None`, was laut Docstring (`qa/aktuarieller_test.py:344-345`) bedeutet "gueltig, solange ein Fall keine Schicht fuehrt". Eigener Nachweis:
   ```
   7000001 .schicht ist None: False
   7000002 .schicht ist None: True
   schicht_ausgelassen (ausgewiesen): []
   zustandslos (ausgewiesen): []
   ```
   Police 7000002 wird also **ohne jede Ausweisung** wie ein Vertrag ohne Korrekturschicht behandelt, obwohl der Producer fuer sie explizit einen Befund hatte.
6. *Reichweite bis in die Produktion*: `validate_schichten()` wird ausser vom A-M1-Pfad auch von `bestand/schichten.py:schichten_je_police()` (Zeile 51) genutzt — dem Leser von `schichten.parquet` fuer "Ereignis-Engine, Bewertung und Ledger-Herleitung" (Moduldoc Zeile 1-9). Aufrufer: `bestand/ledger_bindung.py:163`, `bestand/auswertung.py:305`, `bestand/ereignisse.py:757` (`fortschreiben`). `betrieb/tageslauf.py:91` importiert genau dieses `fortschreiben` und liest/schreibt `schichten.parquet` selbst (Zeilen 402, 433-435, 447-462: `"angewandt": bool(verankerung is not None and schichten is not None)`). Der Weg vom Uebernahmeverzeichnis in den Eingang ist an einen A-M4-Snapshot gebunden (`betrieb/uebernahme.py:86-126`, `eingang_anlegen`) — ob A-M4 die Vollstaendigkeit selbst prueft, habe ich fuer diesen Befund nicht vertieft (siehe Vorspann-Bezug T25-05: die Fuehrungsprobe vergleicht laut dortiger Beschreibung nur `rho`, nicht Vollstaendigkeit — das ist ein separater, dort zu triagierender Befund).

**Stand auf main 10ee765.** Unveraendert. `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/gates/aktuartest_lauf.py` und `-- src/rechner_pipeline/models/bestand.py` sind **leer** — beide Dateien sind byte-identisch zum geprueften Stand (`diff` bestaetigt Null-Differenz). `verankerung_belegen.py` hat seither zwei Commits (`8725982` Merge, `31c1caf` Block-1-Fix "Belegidentitaet"), aber deren Diff betrifft ausschliesslich das einmalige Lesen und Hashen der Eingaben (`lies_gehasht`, `read_portfolio_aus_bytes`, `lade_spez_aus_bytes` statt getrennter `pd.read_parquet`/`_sha256`-Aufrufe) — die Schreib-vor-Pruef-Reihenfolge (Zeilen 419-442 vs. 479-483) ist unangetastet.

**Schaden.** Ein roter (fehlgeschlagener) Schicht-Producer-Lauf hinterlaesst trotzdem eine gueltig aussehende, provenienzbelegte `schichten.parquet` samt JSON-Beleg auf Platte. Beide Konsumenten — der A-M1-Pruefpfad (`aktuartest_lauf._schichten` -> `baue_auftraege`/`_schicht_fuer`) und der Fuehrungs-/Produktionspfad (`bestand.schichten.schichten_je_police`, erreichbar aus `betrieb.tageslauf` sobald ein solcher Bestand einen A-M4-Snapshot traegt) — akzeptieren die Teiltabelle anstandslos. Fuer jede fehlende Police wird das explizite Fachkonzept-Verbot ("Ein Vertrag, dessen Verankerung scheitert, wird NICHT stillschweigend ohne Schicht uebernommen", `migrationszugang.py:199-201`) unterlaufen: Sie erscheint ohne jede Ausweisung (nicht in `schicht_ausgelassen`, nicht in `zustandslos`) als Vertrag ohne Korrekturschicht — ein falscher Wertvergleich in A-M1 bzw. ein falscher Bilanzwert in der taeglichen Fuehrung fuer genau die Policen, die der Producer explizit zurueckgewiesen hat.

**Schwere.** Zustimmung zu "Hoch". Der Fehler ist mit zwei gewoehnlichen Vertraegen (kein exotischer Zeitpunkt, keine Wettlaufbedingung) sofort und deterministisch ausloesbar; er hebelt eine im Code selbst dokumentierte Garantie exakt in den einen Fall aus, den sie verhindern soll (still ohne Schicht uebernommen); und dieselbe Luecke in `validate_schichten()` reicht — ueber `bestand/schichten.py` — bis in die reale taegliche Fuehrung, nicht nur in die Testabnahme. Einschraenkend gegenueber einer Einstufung als "kritisch": Der Weg in die Produktion ist an eine A-M4-Annahme gebunden, kein direkter, ungegateter Pfad von einem roten Producer-Lauf in den Tagesbetrieb; ob A-M4 selbst die Luecke schliesst, ist eine separate, nicht hier verifizierte Frage. "Hoch" ist damit treffend, mit Tendenz zum oberen Rand wegen der belegten Reichweite ueber A-M1 hinaus.

**Klasse (Invariante).** Ein Producer, der ein Ergebnis in eine akzeptierte und eine abgelehnte Teilmenge (`getragen`/`befunde`) aufspaltet, darf kein aus der akzeptierten Teilmenge abgeleitetes Artefakt dauerhaft veroeffentlichen, bevor seine eigene, aus denselben Befunden gebildete Rot/Gruen-Entscheidung feststeht UND in einer Form im Artefakt steht, die jeder Konsument prueft; und jeder Konsument einer solchen Teilmenge muss ihre Mitgliedschaft gegen die volle erwartete Menge (Bijektion), nicht nur die Gueltigkeit der einzelnen Mitglieder pruefen — sonst wird "Producer gescheitert" leise zu "Producer erfolgreich auf einer Teilmenge", und ein fehlendes Mitglied faellt in "keine Korrektur noetig" statt in "ungeklaert".

**Weitere Stellen mit demselben Muster.**
- `src/rechner_pipeline/models/bestand.py:1503-1556` (`validate_schichten`) selbst: prueft nur "jede Schicht hat eine Verankerung" (Zeile 1537-1540), nie die Gegenrichtung "jede Verankerung hat eine Schicht" — die Wurzel der Luecke, wiederverwendet von jedem Aufrufer unten.
- `src/rechner_pipeline/bestand/schichten.py:40-63` (`schichten_je_police`) — der Fuehrungs-Leser von `schichten.parquet`, erbt dieselbe Luecke ueber `validate_schichten`; Aufrufer: `src/rechner_pipeline/bestand/ledger_bindung.py:163`, `src/rechner_pipeline/bestand/auswertung.py:305`, `src/rechner_pipeline/bestand/ereignisse.py:757` (`fortschreiben`, importiert von `src/rechner_pipeline/betrieb/tageslauf.py:91` — dem taeglichen Produktionslauf).
- `src/rechner_pipeline/gates/aktuartest_lauf.py:260-282` (`_schicht_fuer`) / `285-302` (`_schicht_felder`): kann "keine Schicht noetig" nicht von "Schicht fehlgeschlagen und zurueckgehalten" unterscheiden — Mechanismus des oben empirisch bestaetigten Schadens.

**Fix-Umfang.** M/L.
- Producer: die `beleg["befunde"]`-Pruefung (heute Zeilen 479-483) vor den `write_portfolio(tabelle, ueber / "schichten.parquet")`-Aufruf (heute Zeile 440) ziehen, oder ueber ein Arbeitsverzeichnis + einen einzigen abschliessenden Rename publizieren (Vorbild: `betrieb/uebernahme.py:eingang_anlegen`, ein einziges `os.rename`).
- `validate_schichten()`: die fehlende Richtung ergaenzen — jede `police_id` aus `verankerung` muss in `schichten` vorkommen (oder explizit, getrennt ausgewiesen ausgenommen sein).
- `_schicht_fuer`/`baue_auftraege`: eine verankerte, aber in `schichten` fehlende Police muss hart scheitern oder ausgewiesen werden, nicht still `schicht=None` erhalten.
- Fangender Klassen-Test: Fixture mit einem getragenen und einem Befund-Vertrag (wie im Repro oben), die pruefen: (a) `schichten.parquet` wird bei nicht-leerem `beleg["befunde"]` nicht (mehr) geschrieben, (b) `validate_schichten()` meldet eine verankerte Police ohne Schicht, (c) `baue_auftraege()` verweigert oder weist eine solche Police aus statt `schicht=None` zu setzen.
- Beruehrt: kein Gate-Vertrag fuer `verankerung_belegen.py` selbst (bleibt Producer), aber `validate_schichten()` wird von `gates/bestand_validate.py`, `gates/fuehrungsprobe.py` und der taeglichen `betrieb/tageslauf.py`-Produktionsstrecke geteilt — eine Verschaerfung aendert dort das Rot/Gruen-Verhalten netzwerkweit und beruehrt das Fachkonzept (Grundsatzdokumentation 9.11/9.14, Freischaltung Schritte 4/5/9). Das ist ein Entscheid des Maintainers wert, vergleichbar mit den bereits gelandeten `!`-Breaking-Commits (z. B. `1c97707`, `705ba4e`).

### T25-05 — Reviewer Hoch — Urteil: teilweise

**Beweis.**

*Halbe (a) — TOCTOU zwischen fachlicher Pruefung und Hashbildung.*

1. **Fuehrungsprobe, unveraendert offen.** `src/rechner_pipeline/gates/fuehrungsprobe.py` ist zwischen der geprueften `fe0e284` und `10ee765` **byte-identisch** (`git diff fe0e284 10ee765 -- src/rechner_pipeline/gates/fuehrungsprobe.py` liefert keine Ausgabe) — die Reviewer-Zeilenangaben gelten deshalb 1:1 fuer den heutigen Stand. Die fachliche Lesung geschieht in `lies()` (Zeile 489-495) ueber `read_portfolio(pfad, ...)` (echter Disk-Read, `pq.read_table(path)`); das Ergebnis fliesst direkt in `pruefe_fuehrung(...)` (Zeile 602-609). Erst danach, Zeile 612, wird fuer **jede** Eingabe erneut vom Pfad gehasht:
   ```python
   434  def _sha256(pfad: Path) -> str:
   435      return hashlib.sha256(pfad.read_bytes()).hexdigest()
   ...
   612      "eingaben": {name: _sha256(pfad) for name, pfad in sorted(eingaben.items())},
   ```
   `_sha256` ist eine eigene, zweite Lesefunktion — kein Import von `gates._common.lies_gehasht` (`grep -n "^from\|^import"` zeigt keinen `_common`-Import in der Datei). Empirisch mit dem echten Code reproduziert (`.venv/bin/python`, Skript unter `/tmp/claude-1000/.../scratchpad/t25-05/repro_fuehrungsprobe_toctou.py`, nur `tempfile.mkdtemp()`, keine Aenderung am Worktree):
   ```
   fachliche Pruefung sah rho = [0.5]
   Hash, den provenienz.eingaben[...] jetzt traegt: 3eb826e3bf80...
   Das ist der Hash der Bytes b'KEIN PARQUET MEHR...', nicht der Bytes,
   die pruefe_fuehrung() tatsaechlich verarbeitet hat (rho=0.5, oben).
   ```
   Zur Gegenprobe dieselbe Datei mit `models.manifest.lies_gehasht` (dem Muster, das Block 1 in `verankerung_belegen.py` einsetzte): Austausch nach der Lesung aendert weder die geparsten Bytes noch den Hash. Das belegt exakt die Reviewer-Aussage — der Producer bindet die neuen (ggf. kaputten) Bytes an die Pruefung der alten.

2. **Schichtbeleg, teilweise behoben.** `git diff --stat fe0e284 10ee765 -- src/rechner_pipeline/gates/verankerung_belegen.py` zeigt 24+/14- Zeilen, identisch mit Commit `31c1caf` ("Belegidentitaet ... Review T23-01, Block 1"), dessen Commit-Text ausdruecklich "in verankerung_belegen (Engine und Hash lasen die Parquets getrennt)" nennt. Heute (Zeile 308, 326-336): `verankerung.parquet`, `bestand.parquet`, `merkmale.parquet` und die Spez werden ueber `lies_gehasht(...)` **einmal** gelesen, geparst wird `pd.read_parquet(io.BytesIO(...roh))` bzw. `lade_spez_aus_bytes(...)`/`read_portfolio_aus_bytes(...)` — fuer diese vier Eingaben ist die TOCTOU-Klasse geschlossen. Das ist real behoben, nicht nur behauptet.

*Halbe (b) — fehlende Eingaben im Provenienzblock.*

3. **Fuehrungsprobe.** `lade_spez(fall, args.generation)` (Zeile 540) liest die Spez ueber `spez_pfad(...).read_bytes()` (`spez/validierung.py:66-67`) — nirgends folgt ein `eingaben[schluessel(spez_pfad(...))] = ...`; ich habe alle sieben `eingaben[...] = `-Zuweisungen der Datei aufgelistet (Zeilen 494, 516, 539, 547, 551, 571, 595) — die Spez-Datei ist nicht darunter. `--red-anteile-datei` wird bei Zeile 555-561 ueber `_lies_csv(fall, args.red_anteile_datei)` gelesen und fliesst in `red_anteile`/`red_anteile_je_datum` (Eingabe von `pruefe_fuehrung`), taucht aber weder unter `eingaben` noch unter `provenienz["parameter"]` (Zeile 613-622: `generation, erhoehungssatz, red_anteile, red_anteil_kandidaten, anker_erwartungswerte, vorgeschichte, schicht, uebernahme, fortschreibung` — kein `red_anteile_datei`) auf. Die Tarifwerks-Schalter (`scheiben_mit_gamma1, stoab_je_baustein, red_verfahren`, Zeile 597-601) landen in `ergebnis["tarifwerk"]`, einem eigenen Top-Level-Feld — **nicht** in `provenienz["parameter"]`; `abnahmebericht._fuehrungsprobe_fehler` (Zeile 1419-1491) vergleicht `probe.get("tarifwerk")` an keiner Stelle gegen die Suite-Config. `schluessel()` (Zeile 483-487) laesst fuer Pfade ausserhalb des Falls den absoluten String durch — externe Eingaben bleiben zulaessig (T23-09-Muster).
4. **Schichtbeleg.** Heute Zeile 354 (`if args.zeilen is not None:`), 368 (`fall_mod.eingang_datei(fall, args.vorgeschichte).open(...)`), 380 (`if args.anker_quelle is not None:`) — alle drei Lesungen fliessen in `anfangszustaende_je_police(...)` (Zeile 392-398) und damit direkt in `baue_schichtbeleg(...)` (Zeile 404-414). Der `eingaben`-Dict (Zeile 444-452) enthaelt ausschliesslich `verankerung`, `bestand`, optional `merkmale`, `spez` — vier Schluessel, wie im Bericht behauptet. `--zeilen`, `--vorgeschichte`, `--anker-erwartungswerte` erscheinen nur als Dateiname unter `provenienz["parameter"]` (Zeile 456-467), nie mit Hash. Downstream bestaetigt das die Wirkung: `aktuartest_lauf._schichten()` (Zeile 305-370) akzeptiert ein abgeleitetes Schicht-Artefakt NUR, wenn jeder Schluessel unter `prov["eingaben"]` noch zu seinem Hash passt (Zeile 364-370) — da `zeilen.json` dort nie als Schluessel steht, erkennt diese Pruefung eine Aenderung an `abgeleitet/transformation/zeilen.json` strukturell nicht; das deckt sich mit der im Bericht beschriebenen Gegenprobe (26/26 Schichten weiter akzeptiert).
5. Zusatzbefund (Kontext fuer "Schaden", von T25-01 aufgeworfen, hier selbst nachvollzogen): `grep -n "korrekturschicht\|verankerung" src/rechner_pipeline/gates/abnahmebericht.py` und dieselbe Suche in `gate_entscheid.py` liefern **keinen** Treffer ausser einer Kommentarzeile — A-M4 (`abnahmebericht.py`, `gate_entscheid.py`) liest `verankerung_schichten.json` ueberhaupt nicht. Die unter (b) offenen Luecken in `verankerung_belegen.py` sind fuer A-M4 damit nicht einmal indirekt sichtbar; sie wirken nur ueber die optionalen `--schicht`-Konsumenten in `aktuartest_lauf.py`/`fuehrungsprobe.py`.

**Stand auf main 10ee765.**
- Halbe (a): **unveraendert** fuer `fuehrungsprobe.py` (kein Commit zwischen `fe0e284` und `10ee765` beruehrt die Datei — `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/gates/fuehrungsprobe.py` ist leer). **Teilweise behoben** fuer `verankerung_belegen.py` durch `31c1caf` (Block 1), gemerged ueber `8725982`, aber nur fuer die vier Parquet/Spez-Eingaben.
- Halbe (b): **unveraendert offen** in beiden Dateien; kein Commit fuegt der Fuehrungsprobe eine Spez- oder Red-Anteile-Bindung hinzu, keiner bindet `--zeilen`/`--vorgeschichte`/`--anker-erwartungswerte` im Schichtbeleg. Die Merge-Commit-Botschaft von `8725982` beschreibt einen dritten, andersgelagerten Fix (`abnahmebericht.py` liest die *fuehrungsprobe.json* selbst nur noch einmal statt zweimal) — das schliesst die TOCTOU beim *Konsum des Belegartefakts*, nicht die hier belegte TOCTOU *innerhalb* von `fuehrungsprobe.py` beim Aufbau seiner eigenen `eingaben`.

Die dev-seitige Meldung "durch den Merge entfallen" ist damit **falsch fuer Halbe (b) in beiden Dateien und falsch fuer Halbe (a) in `fuehrungsprobe.py`**; richtig nur fuer Halbe (a) in `verankerung_belegen.py`, und selbst dort nur fuer die vier tatsaechlich gebundenen Eingaben.

**Schaden.** Ein Fehler oder eine Manipulation zwischen Pruefung und Hashbildung in `fuehrungsprobe.py` (z. B. eine zwischen zwei Lauf-Schritten teilweise geschriebene oder ausgetauschte `schichten.parquet`/`historie.parquet`) erzeugt einen formal gruenen, provenienzgebundenen Beleg, dessen `eingaben`-Hashes zu den *neuen* Bytes gehoeren — A-M4 (`_fuehrungsprobe_fehler`) rechnet exakt diese Hashes gegen die aktuellen Dateien nach, findet keine Abweichung und bestaetigt den Widerspruch, wie in T25-05 beschrieben. Unabhaengig davon macht das Fehlen der Spez- und `--red-anteile-datei`-Bindung (Fuehrungsprobe) sowie der `--zeilen`/`--vorgeschichte`/`--anker-erwartungswerte`-Bindung (Schichtbeleg) jeden dieser Belege blind gegenueber genau den fachlichen Annahmen, die er angeblich zusichert: eine nachtraeglich geaenderte Herabsetzungsanteils-Liste, ein anderes Transformationsergebnis oder eine andere Ankerquelle bleiben unbemerkt, solange die vier bzw. sieben tatsaechlich gehashten Dateien gleich bleiben. Fuer den Schichtbeleg kommt hinzu, dass A-M4 ihn ueberhaupt nicht konsumiert — die Luecke wirkt nur dort, wo `--schicht` optional gezogen wird (Aktuartest, Fuehrungsprobe selbst).

**Schwere.** Zustimmung zu "hoch". Halbe (a) ist mit einer einzelnen, realistischen Fehlerinjektion (ein Dateiaustausch im Fenster zwischen zwei bereits vorhandenen Codezeilen, kein Timing-Rennen) deterministisch und ohne Sonderrechte ausloesbar, und `fuehrungsprobe.json` ist laut eigenem Docstring "Pflichtbeleg von A-M4 im Bestands-Scope" — also eine Eingabe, auf der die menschliche Freigabeentscheidung eines Migrationslaufs beruht. Dass dieselbe Fehlerklasse in derselben Reviewrunde (T23-01) bereits benannt und in sechs anderen Modulen geschlossen wurde, aber ausgerechnet in der neu eingefuehrten Fuehrungsprobe nicht, verschaerft die Einstufung eher als sie zu mildern. Einschraenkend: kein Konsument akzeptiert *stillschweigend falsche Zahlen* ohne jede Spur — der veraenderte Hash steht im Beleg, nur die Kette, die ihn pruefen wuerde, prueft die falsche Behauptung. Das rechtfertigt "hoch", nicht zwingend "kritisch".

**Klasse (Invariante).** Ein Beleg, der eine fachliche Pruefung bezeugt, muss fuer jede Eingabe, die diese Pruefung tatsaechlich gelesen und verwendet hat, denselben Lesevorgang binden, den er auch hasht (kein zweiter Pfad-Read danach) — UND jede solche Eingabe ueberhaupt im Provenienzblock benennen; eine Eingabe, die nur als Dateiname/Parameter auftaucht oder ganz unerwaehnt bleibt, kann sich unbemerkt aendern, weil kein Konsument sie je gegenprueft.

**Weitere Stellen mit demselben Muster.** Gezielt gesucht in den uebrigen "Produzenten" (Docstring-Selbstbezeichnung "Produzent, kein Gate") mit denselben `--zeilen/--vorgeschichte/--red-anteile-datei/--anker-erwartungswerte`-Flags, da Block 1s eigene Testinstrumente (Konventions-Ratsche, Lese-Zaehl-Test laut Commit-Text) ausdruecklich nur "P-Q3, P-K1, abox_merge, A-K1, Aktuartest und Abnahmebericht" fahren — nicht diese Produzentenfamilie:
- `src/rechner_pipeline/gates/bestand_uebernehmen.py:895-934` — der `uebernahme.json`-Beleg (Zeile 895-912) hat **ueberhaupt keinen** Provenienz-/Eingaben-Hash-Block (`grep -n '"eingaben"' bestand_uebernehmen.py` => kein Treffer); `--zeilen`, `--vorgeschichte`, `--red-anteile-datei`, `--anker-erwartungswerte`, Config und Spez werden gelesen, aber nirgends gebunden — staerker ausgepraegt als in T25-05, und dieser Beleg ist selbst Pflichteingabe von `fuehrungsprobe.py` (Zeile 510-517).
- `src/rechner_pipeline/gates/migrationssuite_lauf.py:711-821` — einzige Bindung ist `bestand_sha256=hashlib.sha256(bestand_pfad.read_bytes()).hexdigest()` (Zeile 821), eine erneute Lesung nach dem bereits erfolgten `read_portfolio(bestand_pfad)` (Zeile 712) — dieselbe TOCTOU wie in `fuehrungsprobe.py`; `--zeilen`, `--vorgeschichte`, `--red-anteile-datei`, `--anker-erwartungswerte`, Spez bleiben vollstaendig ungebunden (`grep` auf `eingaben[`/`lies_gehasht` in dieser Datei: kein Treffer).
- `src/rechner_pipeline/gates/aktuartest_lauf.py` — dieselbe Flag-Familie (Zeile 492 `--red-anteile-datei`, 630-632 gelesen) ohne jede `eingaben[`/`sha256`-Bindung fuer die eigenen Eingaben (nur der Schichtbeleg-*Konsum*, Zeile 305-370, prueft fremde Hashes nach).

**Fix-Umfang.** L. Einzelzeilen-Patches schliessen die Klasse nicht, weil sie ueber vier Produzenten mit unterschiedlichem Reifegrad verteilt ist. Vorschlag: (1) `gates._common` um einen kleinen `Provenienzbuilder`/`EingabenBinder` erweitern, der `lies_gehasht` mit einer Pflichtregistrierung koppelt — jedes Argparse-Flag, das einen Dateipfad benennt und anschliessend gelesen wird, muss vor der Verwendung registriert werden, sonst schlaegt eine Vollstaendigkeits-Pruefung fehl; (2) `fuehrungsprobe.py` auf dasselbe `lies_gehasht`+`*_aus_bytes`-Muster umstellen, das `verankerung_belegen.py` fuer vier Eingaben bereits hat, und zusaetzlich Spez sowie `--red-anteile-datei` binden; (3) `verankerung_belegen.py` um `--zeilen`, `--vorgeschichte`, `--anker-erwartungswerte` als gehashte Eingaben ergaenzen; (4) `bestand_uebernehmen.py` und `migrationssuite_lauf.py` bekommen erstmals einen vollstaendigen `provenienz.eingaben`-Block nach demselben Muster. Test der KLASSE: die bestehende Konventions-Ratsche/Lese-Zaehl-Test-Paar (Block 1) auf diese vier Produzentenmodule ausweiten, plus ein parametrisierter Mutationstest nach dem Muster meines Repro-Skripts (Datei nach der fachlichen Lesung, vor der Hashbildung austauschen => erwartet: Hash weicht vom tatsaechlich verwendeten Inhalt ab, Test schlaegt fehl, bis der Producer auf `lies_gehasht` umgestellt ist) sowie ein Test, der aus jeder Argparse-Definition mit `default=None`/Dateipfad-Semantik ableitet, ob der Wert je in `provenienz.eingaben` landet. Beruehrt den Beleg-/Gate-Vertrag von A-M4 (Pflichtbelegrolle "fuehrungsprobe", neues Schema-Feld fuer die weiteren Produzenten) — Entscheid des Maintainers vor Umsetzung, vergleichbar im Umfang mit den bereits als `!`-Commits gelandeten T23-Block-1/T24-07-Reparaturen.

### T25-06 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Alle Reviewer-Zitate treffen den heutigen Code auf 10ee765 unveraendert (Zeilennummern identisch zur Review, siehe "Stand" unten). Ich habe zusaetzlich zwei eigene, ueber die Reviewer-Zitate hinausgehende Belege gefunden, die die Klasse haerter machen als im Bericht formuliert.

*PEX.* `src/rechner_pipeline/bestand/auswertung.py:244-250` (Docstring): "Eine Beitragsfreistellung NACH der Verankerung hat sie absorbiert (Klasse A)". Der zugehoerige Code, `auswertung.py:406-417`:
```python
traegt = werte["status"] != "PEX" or zustand_ta == "beitragsfrei"
if traegt and int(months_exp) >= monate_ta:
    korr = schichtwert_bei(parameter, monate_ta, kerne[pid].mp, int(months_exp))
    zeile["korrekturschicht"] = korr
    werte["deckungskapital"] += korr
    werte["rueckkaufswert"] += korr
```
Bei einer PEX NACH der Verankerung ist `traegt = False`: `korr` wird gar nicht berechnet. Der Schichtwert wird also nicht "absorbiert" (das hiesse: in eine neu kalibrierte beitragsfreie Basis ueberfuehrt, damit Deckungskapital/RKW stetig bleiben), sondern schlicht nicht mehr addiert — vorher (solange die Police beitragspflichtig war) floss `korr` jede Periode in `deckungskapital`/`rueckkaufswert` ein, danach nicht mehr, ohne Gegenbuchung. `zeile["vs_bfr"]` (Zeile 423) stammt aus `werte["vs_bfr"]`, das an keiner Stelle des Codes `korr` erhaelt — auch im `traegt=True`-Fall nicht.

Die Herkunft von `werte["vs_bfr"]`/der PEX-Umbuchung ist `bestand/ereignisse.py:247-251` (`Vertrag.beitragsfreie_summe`):
```python
def beitragsfreie_summe(self, a0: int) -> float:
    return self.grund.beitragsfreie_summe(a0) + sum(
        kern.beitragsfreie_summe(a0 - erh_jahr)
        for erh_jahr, _, kern in self.scheiben
    )
```
`self.schicht` (Zeile 222, im selben `__init__` gesetzt mit dem Kommentar "eine Beitragsfreistellung absorbiert — nach ihr gibt es kein Storno mehr, die Schicht ist damit erledigt") wird in dieser Methode an keiner Stelle referenziert — anders als in `rkw()` (Zeilen 237-245), das den Schichtwert explizit addiert, wenn `12*jahr >= self.schicht[1]`. Aufgerufen wird `beitragsfreie_summe` bei der eigentlichen PEX-Buchung in Zeile 378 (`pex_summe = vertrag.beitragsfreie_summe(j + 1)`), gebucht in Zeile 379 (`buche("PEX", j + 1, "VS_bfr", pex_summe)`). Diese Methode ist ausschliesslich von `self.grund`/`self.scheiben` abhaengig; eine Beeinflussung durch `self.schicht` ist strukturell ausgeschlossen (keine bedingte Verzweigung, kein Zugriff) — das ist am Quelltext beweisbar, nicht nur beobachtbar, und macht eine Laufzeitreproduktion mit einem konkreten Fall entbehrlich (ich habe daher keine eigene 80-Vertraege-Gegenrechnung gefahren; das ist unter "Weitere Pruefungen" unten vermerkt).

`gates/fuehrungsprobe.py:393-395` (STO-Zweig direkt darueber, Zeilen 386-390, addiert `schichtwert_bei(...)`; PEX-Zweig nicht):
```python
elif art == "PEX":
    erwartet = grund.beitragsfreie_summe(jahr) + sum(
        k.beitragsfreie_summe(jahr - j) for j, k in teile)
```
`src/rechner_pipeline/bestand/ledger_bindung.py:244-253` (Reviewer schrieb "gates/ledger_bindung.py" — die Datei liegt tatsaechlich unter `bestand/`, existierte dort bereits auf `fe0e284`; reine Pfadungenauigkeit des Reviewers, keine Sachabweichung) zeigt dieselbe Asymmetrie: STO-Zweig (Zeilen 237-243) addiert `schichtwert_bei`, PEX-Zweig (244-253) ruft nur `v.beitragsfreie_summe(...)`.

`kern/korrekturschicht.py:532-537`: `"PEX": Heilungsregel(heilt=True, geprueft=False, begruendung="... Zuordnung uebernommen, fachlich noch nicht bestaetigt")`. `heilt()` (579-593), `absorbiere()` (601-609) und `ungeprueft()` (596-598) haben laut `git grep` **keinen** produktiven Aufrufer im gesamten `src/`-Baum — nur `tests/test_korrekturschicht.py` importiert sie. `ungeprueft()` liefert `["INV", "PEX", "REA"]`.

*Eigener Zusatzbefund, staerker als das Reviewer-Zitat:* `bestand/config.py:307-318`, `TarifGeneration.tarifwerk()`:
```python
def tarifwerk(self) -> Dict[str, Any]:
    """... Jeder Konsument (Uebernahme, Ereignis-Engine, Bewertung,
    Ledger-Herleitung, Fuehrungsprobe) liest die drei Schalter ueber
    diese eine Methode, damit keiner einen davon still vergisst.
    """
    return {"scheiben_mit_gamma1": ..., "stoab_je_baustein": ..., "red_verfahren": ...}
```
Der Docstring behauptet explizit, dass fuenf benannte Konsumenten alle drei Schalter lesen — genau damit keiner "still vergessen" wird. `grep -n 'tarifwerk\['` ueber `bestand/ereignisse.py`, `bestand/auswertung.py`, `bestand/ledger_bindung.py`, `gates/fuehrungsprobe.py` zeigt: `scheiben_mit_gamma1` und `stoab_je_baustein` werden in Ereignis-Engine UND Ledger-Herleitung gelesen (`ereignisse.py:232,240`; `ledger_bindung.py:81,96`); `tarifwerk["red_verfahren"]` erscheint einzig in `fuehrungsprobe.py:180` — in `ereignisse.py`, `auswertung.py` und `ledger_bindung.py` kein einziger Treffer. Genau das vom Docstring benannte Risiko ist eingetreten, in genau den beiden Modulen, die die produktive Bewertung/Herleitung tragen.

*RED.* Repo-weite Suche (`grep -rn "red_verfahren"`) bestaetigt: der Schalter wird gelesen von `gates/migrationssuite_lauf.py`, `gates/verankerung_belegen.py`, `gates/aktuartest_lauf.py`, `gates/bestand_uebernehmen.py` (einmaliger Uebernahme-Schritt, siehe unten), `qa/migrationssuite.py`, `qa/aktuarieller_test.py` — durchweg Pruefstrecke bzw. der einmalige Migrations-Uebergang. In `bestand/ereignisse.py`, `bestand/auswertung.py`, `betrieb/tageslauf.py`, `bestand/cli_fortschreibung.py`, `bestand/abschluss.py` kein Treffer fuer `red_verfahren`, auch kein `"RED"`-Literal in `ereignisse.py`, d. h. der produktive Ereignis-Engine-Kaskade (Tod -> Storno -> PEX -> Erhoehung, Zeilen ~366-390) fehlt RED als moegliches Ereignis vollstaendig. `bestand/ledger_bindung.py:22-23` dokumentiert das selbst als bewusste Grenze: "Bewusste Grenzen: `MIG` ... und `RED` (Herabsetzung, **von der Engine nicht erzeugt**) werden nicht hergeleitet". Der Kernel-Baustein fuer RED existiert vollstaendig und ist fachlich ausgearbeitet (`kern/beitragsreduktion.py`, Docstring referenziert Grundsatzdokumentation 9.7, zwei Verfahren `prospektiv`/`mit_abzug`), wird aber laut `grep -rl` nur von `bestand/migrationszugang.py` und den o. g. Pruefstrecken-/Gate-Modulen importiert — nie von `bestand/ereignisse.py` oder `bestand/auswertung.py`. Das ist exakt das "kann ohne tut"-Muster, das der Entwicklertext selbst fuer die anderen beiden Tarifwerks-Schalter beschreibt und das in Schritt 4 der Freischaltung (Commit d13edf2) geschlossen wurde — fuer `red_verfahren` blieb es offen.

`dev-docs/freischaltung-uebernommener-bestand.md:154-158` fuehrt unter "Fachliche Festlegungen (Maintainer, 2026-09-07)" — als bereits entschieden, "hier nicht neu verhandelt" — "Der Abbau der Korrekturschicht ist grundsaetzlich definiert. ... STO wertkontinuierlich, PEX absorbierend ... Nichts davon fehlt; es ist nur nicht in der Fuehrung gebaut." Das steht in Spannung zu `korrekturschicht.py:532-536`, wo dieselbe Zuordnung fuer PEX als `geprueft=False` — "fachlich noch nicht bestaetigt" — gefuehrt wird. Die Stand-Tabelle desselben Dokuments (Zeile 425) verbucht Schritt 5 als "ERLEDIGT ... Storno und Abschluss mit Schicht" — PEX wird dort bewusst NICHT als erledigt genannt. Der Entwicklertext ist an dieser Stelle also selbst uneinheitlich (Abschnitt 2 vs. Code-Tabelle vs. Stand-Tabelle), bestaetigt aber in der Summe, dass PEX-Absorption nicht abgeschlossen ist.

*Weitere Pruefungen, die ich nicht gefahren habe:* Ich habe die vom Reviewer zitierte empirische Gegenrechnung (80 Vertraege/16 PEX-Ereignisse, police 900018) nicht selbst wiederholt — weder gegen `faelle/baldrian-klv-tg2015-lauf2` (Anweisung: nur lesen, nicht anfassen) noch synthetisch. Der Quellcode-Beweis (`beitragsfreie_summe()` referenziert `self.schicht` an keiner Stelle) macht das Ergebnis aber deterministisch und unabhaengig vom konkreten Fall.

**Stand auf main 10ee765.** Unveraendert. `git log --oneline fe0e284..10ee765 -- <datei>` ist leer fuer alle folgenden Dateien: `bestand/auswertung.py`, `bestand/ereignisse.py`, `kern/korrekturschicht.py`, `bestand/ledger_bindung.py`, `gates/fuehrungsprobe.py`, `bestand/config.py`, `betrieb/uebernahme.py`, `bestand/kennzahlen.py`, `models/bestand.py`, `dev-docs/freischaltung-uebernommener-bestand.md`. Die 28 Commits zwischen `fe0e284` und `10ee765` (u. a. T23 Block 1-5, T24-07, Schritt 9/`1b904e0`, der Merge nach main) betreffen andere Themen (Belegidentitaet, TBox-Evidence-Vertrag, A-M4-Vollprofil, Zeichnungsvertrag, verwaiste Staende, Betriebs-Eingang mit Scheiben/Schicht/Beleg). Keiner davon beruehrt PEX-Absorption oder red_verfahren-Verdrahtung.

**Schaden.** Bei einer Beitragsfreistellung, die NACH dem Verankerungszeitpunkt eines uebernommenen Vertrags mit realem Schichtresiduum eintritt, verschwindet der bis dahin korrekt ausgewiesene Korrekturschicht-Wert ersatzlos aus Deckungskapital und Rueckkaufswert der Folgeperioden — ohne Journaleintrag, ohne Uebertrag in die beitragsfreie Summe, ohne dass `heilt()`/`absorbiere()` je aufgerufen wuerden. Die beiden Stellen, die das als "unabhaengige" Gegenrechnung auffangen sollten (`fuehrungsprobe.py`, `ledger_bindung.py`), rechnen dieselbe unvollstaendige Formel und bestaetigen den fehlerhaften Wert statt ihn zu widerlegen — der Fehler ist also nicht nur vorhanden, sondern durch die eigene Kontrollarchitektur nicht auffindbar. Fuer den zweiten Baldrian-Fall ist die Auswirkung laut Entwicklerdokument aktuell klein (Residuen im Bereich von Rundungsrauschen, "hoechstens 0,02 EUR je Vertrag"), aber das ist eine Eigenschaft dieser Lieferung, nicht der Architektur — bei einem Bestand mit einem echten Verankerungsresiduum ist der Effekt eine stille, nicht ausgewiesene Unterdeckung des Rueckkaufswerts nach jeder PEX. Fuer RED gilt: post-migration eintretende Beitragsreduktionen haben in der produktiven Fuehrung keinerlei Bewertungspfad — weder Ereignis-Engine noch Bewertung kennen `red_verfahren`, obwohl der Kernel-Baustein dafuer (`kern/beitragsreduktion.py`) fertig existiert und ueber die Pruefstrecke bereits fachlich abgenommen wurde.

**Schwere.** Zustimmung zu "hoch". Die Faktenlage ist staerker als im Bericht formuliert: Es handelt sich nicht nur um eine unvollstaendige Formel an einer Stelle, sondern um einen vom Modul selbst dokumentierten, aber nicht eingeloesten Vertrag (`tarifwerk()`-Docstring verspricht "damit keiner einen davon still vergisst" — und genau das ist zweifach passiert), und um ein fachlich bereits fertig gebautes Kernelement (`beitragsreduktion.py`), das schlicht nicht verdrahtet ist. Einschraenkend: der real gemessene Geldbetrag im einzigen verfuegbaren Fall ist klein, und die Buchungen sind nicht STILL falsch im Sinn von "unauffindbar" — ein Mensch, der die Zeile `korrekturschicht` im Abschlussbericht einer betroffenen Police vor und nach einer PEX vergleicht, wuerde den Sprung auf 0 sehen (der Abschluss weist die Schicht ja als eigene Spalte aus, T25-06 selbst nennt diesen Punkt nicht als Fehler). Die Einstufung "hoch" (nicht "kritisch") ist angemessen: der Docstring-Bruch und die fehlende RED-Verdrahtung sind reale, aber noch nicht in Produktion ausgeloeste Luecken mit erkennbarer Spur, kein stiller, unentdeckbarer Bilanzfehler.

**Klasse (Invariante).** Eine Tarifwerks-/Fuehrungsregel, die in einem Modul-Docstring als "von jedem benannten Konsumenten ueber eine gemeinsame Methode gelesen, damit keiner sie still vergisst" deklariert ist, muss durch einen Test erzwungen werden, der jeden dieser Konsumenten tatsaechlich gegen eine Aenderung des Schalterwerts empfindlich macht (z. B. Property-Test: Schalter kippen, erwarten, dass sich mindestens eine Ausgabe jedes benannten Konsumenten aendert) — sonst ist die Deklaration reine Absicht, und ein Konsument kann den Schalter beliebig lange stillschweigend ignorieren, ohne dass ein "unabhaengiger" Vergleichspfad (der denselben Fehler repliziert statt ihn zu widerlegen) das je bemerkt.

**Weitere Stellen mit demselben Muster.**
- `src/rechner_pipeline/bestand/config.py:307-318` — der `tarifwerk()`-Docstring selbst ist die staerkste weitere Instanz: er behauptet eine Garantie, die fuer `red_verfahren` in zwei von fuenf genannten Konsumenten (Ereignis-Engine, Ledger-Herleitung) nicht zutrifft. Vom Reviewer nicht zitiert.
- `dev-docs/freischaltung-uebernommener-bestand.md:154-158` vs. `kern/korrekturschicht.py:532-536` — Entwicklerdokument fuehrt "PEX absorbierend" als abgeschlossene Maintainer-Festlegung, die Code-Tabelle fuehrt dieselbe Zuordnung als `geprueft=False`. Kein Implementierungsfehler, aber ein Beleg dafuer, dass der fachliche Status von PEX-Absorption im Repo selbst uneins dargestellt wird.
- Keine weitere Instanz der PEX-Formel-Luecke gefunden ausserhalb der drei vom Reviewer genannten Stellen (`ereignisse.py`, `fuehrungsprobe.py`, `ledger_bindung.py`) — gesucht wurde nach jedem Aufrufer von `beitragsfreie_summe` (`grep -rn "def beitragsfreie_summe"` und Aufrufstellen) sowie jedem Aufrufer/jeder Definition von `heilt`/`absorbiere`/`ungeprueft` im gesamten `src/`-Baum.

**Fix-Umfang.** M, in zwei getrennten Teilaufgaben. (1) RED-Verdrahtung: analog zu Schritt 4 der Freischaltung (Commit d13edf2, `scheiben_mit_gamma1`/`stoab_je_baustein` in Ereignis-Engine/Bewertung/Ledger-Herleitung verdrahtet) `kern.beitragsreduktion` in `bestand/ereignisse.py` (Vertrag-Klasse, Kaskade um RED als Ereignis erweitern), `bestand/auswertung.py` und `bestand/ledger_bindung.py` einbinden, mit `tarifwerk["red_verfahren"]` als Parameter — der Kernel-Baustein ist fertig, das ist reine Verdrahtung mit Praezedenzfall im selben Repo. (2) PEX-Absorption: `heilt()`/`absorbiere()` tatsaechlich aus dem produktiven PEX-Pfad aufrufen und dabei entscheiden, WIE der freiwerdende Schichtwert in die neue beitragsfreie Basis einfliesst (analoge Frage zu `kern/beitragsreduktion.py`s "geknickter Verlauf"), damit "absorbiert" eine wertstetige Umwandlung ist statt eines blossen Nichtmehraddierens — das ist eine aktuarielle Festlegung, keine reine Code-Aenderung. Fangender KLASSEN-Test: ein Property-/Parametrisierungstest, der `TarifGeneration.tarifwerk()` je Schalter einzeln aendert und fuer jeden der fuenf im Docstring genannten Konsumenten (Uebernahme, Ereignis-Engine, Bewertung, Ledger-Herleitung, Fuehrungsprobe) verlangt, dass sich mindestens eine seiner Ausgaben aendert — das haette die `red_verfahren`-Luecke sofort automatisiert gefunden, unabhaengig vom konkreten Fall. Ergaenzend ein Test, der eine PEX nach der Verankerung mit ungleich-null `rho` konstruiert und verlangt, dass Deckungskapital/Rueckkaufswert vor und unmittelbar nach der PEX wertstetig sind (keine Sprungstelle). Beruehrt: Fachkonzept (`dev-docs/freischaltung-uebernommener-bestand.md`, Schritt 5 — "Fertig, wenn" muesste PEX explizit einschliessen, nicht nur Storno) und den Gate-Vertrag von `gates.fuehrungsprobe` (dessen "bestanden"-Kriterium eine manipulierte/fehlende PEX-Absorption aktuell nicht erkennen kann, weil es dieselbe Luecke teilt) — Entscheid des Maintainers vor Umsetzung angezeigt, insbesondere fuer die Wertstetigkeits-Regel der PEX-Absorption.

### T25-08 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Beide Reviewer-Zeilenbereiche sind auf 10ee765 identisch zu denen des geprueften Standes (siehe unten) — keine Zeilenverschiebung.

1. `src/rechner_pipeline/gates/bestand_uebernehmen.py:990-1051` — der komplette Schreibblock des Produzenten. Zeilen 990-992 (`write_portfolio(stamm, ...)`, `historie`, `ledger`) schreiben unbedingt; Zeilen 993-994 (`scheiben.parquet`), 1005-1006 (`merkmale.parquet`), 1009-1019 (`generation-zellen.toml`) und 1027-1030 (`verankerung.parquet`) schreiben NUR `if <tabelle> is not None and len(<tabelle>)`. In der gesamten Funktion (und der gesamten Datei) gibt es keinen einzigen Aufruf, der eine vorher im Zielverzeichnis liegende Datei entfernt oder auch nur prueft, ob sie existiert:
```
$ grep -n "unlink\|os\.remove\|rmtree\|missing_ok\|\.exists()" src/rechner_pipeline/gates/bestand_uebernehmen.py
(kein Treffer)
```
`write_portfolio` (bestand/parquet_io.py:107ff) selbst schreibt pro Datei atomar (temp + `os.replace`), kennt aber nur die EINE Datei, die es gerade schreibt — kein Wissen ueber Geschwister-Dateien im selben Verzeichnis.

2. `src/rechner_pipeline/bestand/cli_fortschreibung.py:84-135` (`_lies_uebernahme`) referenziert `uebernahme.json` an KEINER Stelle:
```
$ grep -rn "uebernahme.json" src/rechner_pipeline/
src/rechner_pipeline/betrieb/neuaufsetzen.py:135
src/rechner_pipeline/betrieb/uebernahme.py:71,360,361,363,365
src/rechner_pipeline/gates/abnahmebericht.py:1416
src/rechner_pipeline/gates/fuehrungsprobe.py:18,123,510
src/rechner_pipeline/gates/bestand_uebernehmen.py:21,98,1049
```
`bestand/cli_fortschreibung.py` fehlt in dieser Liste komplett. Zeilen 123-127 (scheiben) und 128-134 (schichten, verankerung) lesen jede optionale Tabelle strikt nach `pfad.is_file()` — keine Gegenpruefung gegen irgendeinen Beleg.

3. Eigener, isolierter Nachvollzug (nur `tempfile.TemporaryDirectory`, kein Zugriff auf `faelle/` des Haupt-Trees; Skript unter `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t25-08/repro.py`): eine synthetische `scheiben.parquet` (1 Zeile, Police 1001) im Zielverzeichnis vorab abgelegt, danach `bestand_uebernehmen.main()` fuer denselben Vertrag OHNE jede Vorgeschichte (also `anfangszustand="ohne_bausteine"`, 0 Bausteine) auf DASSELBE `--out-dir` laufen lassen:
```
exit code: 0
uebernahme.json anfangszustand: ohne_bausteine
uebernahme.json mit_scheiben: 0
uebernahme.json scheiben (zaehler): 0
scheiben.parquet existiert noch nach dem Lauf: True
scheiben.parquet byte-identisch zur ALTEN (Vorlauf-)Datei: True
cli_fortschreibung._lies_uebernahme() uebernimmt scheiben: True Zeilen: 1
```
Der Beleg behauptet 0 Scheiben, das Verzeichnis traegt 1, und der genannte Verbraucher (`_lies_uebernahme`) liest sie unbesehen ein — mit echtem Code, kein Mock.

**Stand auf main 10ee765.** Unveraendert. `git diff fe0e284 10ee765 -- src/rechner_pipeline/gates/bestand_uebernehmen.py src/rechner_pipeline/bestand/cli_fortschreibung.py` liefert 0 Zeilen; `git log --oneline fe0e284..10ee765 -- <je Datei>` ist fuer beide leer. Keiner der seither gelandeten Commits (Rest freischaltung, T23 Block 1-5, T24-07, Schritt 9/1b904e0) hat diese beiden Dateien angefasst.

**Schaden.** Ein iterativer Bearbeitungsschritt — genau das vom Kommando selbst vorgesehene Muster "erst ohne `--anfangszustand` anhalten, dann mit `materialisieren` oder `grundvertrag` erneut in dasselbe `--out-dir` laufen" (Zeilen 936-942 der Datei geben exakt diesen Hinweis aus) — kann eine `scheiben.parquet` (oder `merkmale.parquet`/`verankerung.parquet`) eines FRUEHEREN Laufs im Verzeichnis stehen lassen, waehrend `bestand.parquet`/`historie.parquet`/`ledger.parquet` und `uebernahme.json` bereits den NEUEN Lauf beschreiben. `uebernahme.json` ist der einzige Beleg, den das System fuer diesen Bestand kennt ("ein Bestand ohne Beleg hat keinen benannten Anfangszustand", Kommentar Zeile 1046-1048) — er sagt dann etwas anderes, als auf der Platte liegt. `cli_fortschreibung._lies_uebernahme` (der GeVo-Strom-Fortsetzer, u. a. Basis fuer `betrieb.tageslauf`s Erstbefuellung laut Commit 1b904e0) uebernimmt die stehen gebliebenen Alt-Erhoehungen unbesehen in den fortgeschriebenen Bestand — falsche Bausteine, falsche Beitragsfreistellungssumme, falscher gefuehrter Gesamtbestand, ohne jede Fehlermeldung.

**Schwere.** Zustimmung zu "hoch". Begruendung: (a) der ausloesende Ablauf ist kein exotischer Randfall, sondern der vom Kommando selbst dokumentierte Wiederholungspfad bei einer Vorgeschichte mit Bausteinen; (b) der betroffene Verbraucher (`cli_fortschreibung.py`) hat NULL Schutz — nicht einmal eine Existenzpruefung gegen den Beleg, geschweige denn eine Hash-Bindung; (c) das Muster ist im Repository bereits an anderer Stelle geloest (siehe unten, `betrieb/uebernahme.py`), das Fehlen hier ist also keine unbekannte Technik, sondern eine ausgelassene Uebertragung; (d) die Klasse ist komplett ungetestet — keiner der einschlaegigen Testdateien (`test_bestand_uebernehmen.py`, `test_uebernahme_freischaltung.py`, `test_bestand_uebernommen_fortschreiben.py`) hat einen Testnamen, der einen wiederholten Lauf oder eine stehen gebliebene Datei beschreibt. Einschraenkend: der Effekt bleibt auf das Zielverzeichnis eines EINZELNEN Falls beschraenkt (keine Fernwirkung auf andere Faelle), und ich konnte NICHT abschliessend klaeren, ob die Fuehrungsprobe (`gates/fuehrungsprobe.py`, fuer A-M4 relevant) diese spezielle Diskrepanz in jedem Fall faengt: sie liest `scheiben.parquet`/`schichten.parquet` an den Zeilen 502/504 GENAUSO rein nach `is_file()` wie `cli_fortschreibung.py`, berechnet aber ab Zeile 175ff. unabhaengig von der Vorgeschichte einen erwarteten Bausteinsatz und vergleicht ihn je Police gegen die Tabelle (Zeilen 252-261) — ob diese Neuberechnung fuer JEDEN Modus- und Rerun-Fall (insbesondere den Uebergang materialisieren->grundvertrag auf denselben Policen) korrekt greift, habe ich nicht bis zum Ende nachvollzogen; das ist eine eigene, ungeklaerte Frage (moeglicherweise Teil von T25-05: "Selbst die echte Fuehrungsprobe prueft weder den erzeugten Endbestand noch die Endhistorie"). Das aendert nichts an der Bewertung fuer `cli_fortschreibung.py`, das diesen Schutz nachweislich gar nicht besitzt.

**Klasse (Invariante).** Ein Produzent, der in ein Zielverzeichnis schreibt, das von einem fruerheren Lauf DESSELBEN oder eines ANDEREN in dasselbe Verzeichnis schreibenden Kommandos bereits Dateien enthaelt, und der eine optionale Ausgabe nur schreibt, wenn der AKTUELLE Lauf dafuer Daten hat (statt das Zielverzeichnis vorher zu leeren, ein vollstaendiges Bundle atomar zu veroeffentlichen, oder zumindest jede tatsaechlich geschriebene Datei in einem fuer Verbraucher pruefbaren Manifest zu registrieren), hinterlaesst nach einem Modus- oder Eingabewechsel ein Gemisch aus zwei Laeufen unter EINEM Beleg; jeder Verbraucher, der optionale Tabellen allein nach Dateiexistenz einliest statt gegen ein Manifest/den Beleg des AKTUELLEN Laufs zu pruefen, uebernimmt dieses Gemisch unbemerkt als kohaerenten, dem Beleg entsprechenden Zustand.

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/gates/verankerung_belegen.py:437-442` (10ee765-Zeilen) — schreibt `schichten.parquet` in DASSELBE Zielverzeichnis (`ueber = fall / "abgeleitet" / "bestand"`, Zeile 312-313, Default identisch zu `bestand_uebernehmen`s `--out-dir`), aber NUR `if zeilen_schichten:` (nicht-leer und ohne `"conv"`-Baustein). Kein Aufruf entfernt eine vorhandene `schichten.parquet`, wenn dieser Lauf keine schreibt. `git diff fe0e284 10ee765` an dieser Datei aendert nur Hash-/Provenienz-Lesart (T23-01, Block 1) und laesst den Schreibblock selbst unberuehrt — die Luecke besteht unveraendert fort.
- `src/rechner_pipeline/betrieb/uebernahme.py:494-503` (`eingang_anlegen`) ist ein GEGENBEISPIEL fuer den korrekten Verbraucher-/Registrierungsteil (ein `.neu`-Arbeitsverzeichnis, danach EIN `os.rename`, jede kopierte Datei bekommt eine SHA-256 im selbst gebauten `eingang.json`; `lies_uebernahme` — Zeilen 310-334 — liest NUR, was in `eingang["dateien"]` registriert ist, ein unregistriertes `scheiben.parquet` wird ignoriert statt gelesen). Das loest aber NICHT die Wurzelursache: `kandidaten`-Schleife (Zeile 495-503) registriert, was AKTUELL physisch in `quelle` (= `bestand_uebernehmen`s Ziel) liegt, unabhaengig davon, ob es aus dem gerade abgenommenen Lauf stammt oder ein Rest eines fruerheren ist — eine stehen gebliebene `scheiben.parquet` wuerde faithfully mitkopiert und als legitimer Bestandteil des Betriebseingangs registriert.
- `src/rechner_pipeline/bestand/cli_fortschreibung.py:366-370` (die eigene `--out-dir`-Ausgabe des Kommandos: `merkmale`/`schichten`/`verankerung` NUR `if tabelle is not None and len(tabelle)`) — dieselbe Schwaeche auf der AUSGABE-Seite desselben Kommandos, nicht nur beim Einlesen. Hier existiert immerhin ein Manifest (`laufmanifest.json`, `bestand/manifest.py:schreibe_manifest`, Aufruf Zeile 373-380) und `gates/bestand_validate.py`/`bestand/vorbedingungen.py:_manifest_befund` (Zeilen 408-433) WEIST eine Datei zurueck, die nicht in `manifest["ausgaben"]` registriert ist ("sie stammt nicht aus diesem Lauf") — aber nur, wenn P-B1 MIT `--manifest` aufgerufen wird; das Flag ist optional (`bestand_validate.py` Zeilen 175-176), und fuer `bestand_uebernehmen`s eigenes Ziel gibt es ueberhaupt kein Manifest dieser Art.

**Fix-Umfang.** L. Reine lokale Korrekturen (z. B. nur `_lies_uebernahme` haerten) schliessen die Klasse nicht, weil derselbe Fehler in zwei Produzenten (`bestand_uebernehmen.py`, `verankerung_belegen.py`) und mindestens drei Verbrauchern (`cli_fortschreibung.py`, `betrieb.uebernahme.eingang_anlegen`, `fuehrungsprobe.py`) steckt. Vorschlag: (1) beide Produzenten bauen ihre Ausgaben vollstaendig in einem `.neu`-Arbeitsverzeichnis (Muster `betrieb/uebernahme.py:483-521`) und veroeffentlichen mit EINEM `os.rename`, ODER sie brechen hart ab, wenn `--out-dir` bereits Dateien traegt, die zu dieser Rolle gehoeren, ohne dass die aktuelle Ausfuehrung sie erzeugt; (2) `uebernahme.json` bzw. ein begleitendes `laufmanifest.json` (Wiederverwendung von `bestand.manifest.schreibe_manifest`) registriert je Lauf SHA-256 fuer JEDE tatsaechlich geschriebene Datei — auch die optionalen; (3) `cli_fortschreibung._lies_uebernahme`, `fuehrungsprobe.py`s `lies()` und `betrieb.uebernahme.eingang_anlegen`s `kandidaten`-Schleife pruefen diese Registrierung, bevor sie eine optionale Tabelle als Teil des Laufs behandeln — ein physisch vorhandenes, aber unregistriertes `scheiben.parquet`/`schichten.parquet` ist entweder ein Fehler oder wird wie "nicht vorhanden" behandelt, nie stillschweigend gelesen. Test der KLASSE: ein parametrisierter Rerun-Test, der `bestand_uebernehmen.main()` (bzw. `verankerung_belegen.main()`) zweimal in DASSELBE `--out-dir` laufen laesst, beim ersten Mal mit einer optionalen Tabelle, beim zweiten Mal ohne, und verlangt: entweder verweigert der zweite Lauf sich, oder die Alt-Datei ist danach weg oder wird von KEINEM der drei genannten Verbraucher mehr gelesen. Der Fix aendert den Beleg-Vertrag (`uebernahme.json`-Schema bzw. neues Manifest), beruehrt einen echten Gate-Vertrag (P-B1 `--manifest` muesste verpflichtend werden, damit die bestehende `_manifest_befund`-Pruefung tatsaechlich greift) und die Fachdokumentation (`dev-docs/freischaltung-uebernommener-bestand.md`) — Entscheid des Maintainers vor der Umsetzung, vergleichbar im Umfang mit den bereits als `!`-Commits gelandeten Freischaltungs-Schritten.

### T25-09 — Reviewer Hoch — Urteil: bestaetigt

**Beweis.** Beide vom Reviewer zitierten Stellen liegen auf 10ee765 unter identischen Zeilennummern (Dateien seit `fe0e284` byte-identisch, siehe unten):

- `src/rechner_pipeline/models/bestand.py:1173` (`validate_abschluss`):
  ```python
  1173  zahlen = ("leistung", "deckungskapital", "rueckkaufswert", "vs_bfr", "jahresbeitrag")
  1174  nichtendlich = [sp for sp in zahlen if _nichtendlich(df[sp])]
  ```
  `korrekturschicht` ist Pflichtspalte von `ABSCHLUSS_SPALTEN` (Zeile 357, Kommentar Zeile 354-356: "nie unsichtbar im Deckungskapital"), taucht in der Endlichkeitswache aber nicht auf.
- `src/rechner_pipeline/bestand/abschluss.py:229` (`pruefe_abschluss`, die Nachrechnung gegen den festgeschriebenen Stand):
  ```python
  229  zahlen = ("leistung", "deckungskapital", "rueckkaufswert", "vs_bfr", "jahresbeitrag")
  ```
  wird pro gemeinsamer Police nur ueber diese fuenf Felder verglichen (Zeile 237); `korrekturschicht` fehlt.

`grep -n '"leistung", "deckungskapital"'` im gesamten `src`-Baum liefert genau diese zwei Treffer — der literale Tupel existiert nur an diesen beiden Stellen.

Eigene, unabhaengige Gegenprobe (nicht die des Reviewers, eigenes Skript `/tmp/claude-1000/-home-bartl-git-rechner-pipeline/2329f69d-b8b8-44c5-9e77-92f24c4c2be8/scratchpad/t25-09/repro.py`, `.venv/bin/python`, echte Engine ueber die Fixture `_tabellen`/`_stamm` aus `tests/test_schicht_in_fuehrung.py`, ausschliesslich in `tempfile.mkdtemp()` geschrieben):

1. Echter, schichttragender Abschluss ueber `schreibe_abschluss(...)` erzeugt (Police 900001: `deckungskapital=74091.591...`, `rueckkaufswert=73941.591...`, `korrekturschicht=31222.280...`). Kontrolle: `pruefe_abschluss(...) == []`.
2. In der **veroeffentlichten Parquet-Datei** ausschliesslich `korrekturschicht` der Police 900001 veraendert (`31222.28 -> 157111.40`, DK/RKW unveraendert stehen gelassen — Bruch der additiven Beziehung `deckungskapital = basis + korrekturschicht`):
   - `validate_abschluss(manipuliert)` -> `[]`
   - `pruefe_abschluss(kanonischer_pfad, stamm, historie, config, schichten=..., verankerung=...)` (echte Neuberechnung gegen die manipulierte Datei) -> `[]`
3. `korrekturschicht` einer zweiten Police auf `NaN` gesetzt: `validate_abschluss(...)` -> `[]` (keine Endlichkeitswache).

Alle drei Punkte des Befunds sind damit mit einem zweiten, unabhaengig konstruierten Fall bestaetigt — nicht nur der eine Reviewer-Beleg nachvollzogen.

**Stand auf main 10ee765.** Unveraendert. `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/models/bestand.py src/rechner_pipeline/bestand/abschluss.py` ist leer, `git diff fe0e284 10ee765 -- <beide Dateien>` liefert keine Differenz — beide Dateien sind byte-identisch zum geprueften Stand. Die Luecke wurde mit `7b58147` ("Freischaltung, Schritt 5 — die Korrekturschicht in der Fuehrung") eingefuehrt; dieser Commit ist Vorfahr von sowohl `fe0e284` (war also bereits Gegenstand des Reviews) als auch von `10ee765` (ueber den Merge `8725982`). Keiner der seither gelandeten Commits (T23 Block 1-5, T24-07, Schritt 9) beruehrt `validate_abschluss` oder `pruefe_abschluss`.

**Schaden.** Der Abschluss ist laut ADR-011/Grundsatzdokumentation 9.11 ein unumkehrbar festgeschriebener Bilanzstand, bei dem `korrekturschicht` bewusst als eigene, nie unsichtbare Position ausgewiesen wird. Weder die Erstpruefung vor dem Festschreiben noch die eigens fuer Drift-/Manipulationserkennung gebaute Nachrechnung deckt diese Position ab: Eine falsche, NaN- oder Inf-wertige `korrekturschicht`-Zahl — sei es durch einen Kernfehler, einen fehlerhaften Producer oder direkte Manipulation der Parquet-Datei — wird sowohl beim Publish als auch bei jeder spaeteren Kontrolle als korrekt bestaetigt. Da `deckungskapital`/`rueckkaufswert` selbst weiterhin geprueft werden, bleibt der bilanzielle Gesamtwert meist unangetastet; falsch wird die **Offenlegung**, wie viel davon Korrekturschicht ist — genau die Transparenzzusage, die diese Spalte laut Grundsatzdokumentation erfuellen soll, ist damit nicht durchgesetzt, sondern nur behauptet.

**Schwere.** Zustimmung zu "hoch". Es ist keine hypothetische Luecke, sondern der real produktive Pfad (`schreibe_abschluss`/`pruefe_abschluss` in `bestand/abschluss.py`, direkt fuer einen bereits gelandeten, als produktionsnah beschriebenen Baustein — Freischaltung Schritt 5) und ausschliesslich mit gewoehnlichen Mitteln (eine Zahl in einer Spalte aendern) ausloesbar, ohne jede Race-Bedingung. Einschraenkend gegenueber "kritisch": Die geprueften Gesamtgroessen (`deckungskapital`, `rueckkaufswert`) selbst bleiben durch die vorhandene Pruefung abgesichert, solange ein Angreifer/Fehler nicht zusaetzlich diese mitverfaelscht — der unmittelbare Schaden ist Ausweis-/Nachweisintegritaet einer einzelnen Bilanzposition, nicht zwingend der bilanzielle Gesamtwert. Das rechtfertigt "hoch", nicht mehr.

**Klasse (Invariante).** Jede Spalte, die als eigener, dokumentiert nie unsichtbarer Bilanz-/Ausweisbestandteil zu `ABSCHLUSS_SPALTEN` hinzugefuegt wird, muss automatisch — nicht ueber eine von Hand an mehreren Stellen nachgezogene Kopie derselben Spaltenliste — in jede Pruefung einfliessen, die Endlichkeit vor dem Festschreiben und Wertgleichheit bei der Nachrechnung durchsetzt; eine literal dupliziert gepflegte Teilmenge der Zahlenspalten laesst jede kuenftig hinzugefuegte Position lautlos durch beide Wachen fallen, bis jemand sich aktiv erinnert, sie an zwei Stellen zugleich nachzutragen.

**Weitere Stellen mit demselben Muster.**

- `src/rechner_pipeline/gates/fuehrungsprobe.py:345-350` — vergleicht das im Schichtbeleg zugesagte `Schichtparameter` gegen `schichten.parquet` nur ueber das Feld `rho`; die uebrigen Belegfelder (`schichttyp`, `verankerungszustand`, `verweildauer`, `formfunktion`, `formparameter`, `vererbend`, `kohorte`) werden nicht gegengeprueft. Andere veroeffentlichte Tabelle, anderer Mechanismus, aber dieselbe Wurzelursache: eine harte Pruefung deckt nur einen von mehreren fachlich gleichrangigen Feldern ab, statt vollstaendig gegen den Beleg zu binden. (Das ist vermutlich Gegenstand eines eigenen T25-Befunds — hier nur als Musterinstanz genannt, nicht als eigenstaendige Bewertung.)
- Gezielt gesucht nach weiteren Instanzen des literalen `zahlen`-Tupels selbst (`grep -rn '"leistung", "deckungskapital"'` im gesamten `src`-Baum) — keine weiteren gefunden ausser den zwei bereits genannten.
- Gezielt geprueft, ob `korrekturschicht` an anderer Stelle (Aggregation `auswertung.py:auswertungs_verlauf`, Ledger-Herleitung `ledger_bindung.py`) fehlerhaft ignoriert wird: nein — dort wird sie am selben, einzigen Berechnungsweg (`einzelwerte_am`, `auswertung.py:406-417`) additiv korrekt gebildet; das Fehlen der Pruefung betrifft ausschliesslich die beiden genannten Nachweis-/Kontrollfunktionen, nicht die Berechnung selbst.

**Fix-Umfang.** M. Kein isoliertes Nachtragen von `"korrekturschicht"` in beide literalen Tupel (das repariert nur diese eine Spalte, nicht die Klasse), sondern: die Menge der finit-/nachrechnungspflichtigen Zahlenspalten aus `ABSCHLUSS_SPALTEN` selbst ableiten (z. B. alle Spalten mit dtype `float64` ausser expliziten Ausnahmen wie `stichtag`), an einer Stelle definiert (etwa `models/bestand.py`) und von `validate_abschluss` UND `pruefe_abschluss` gemeinsam referenziert — analog zum bereits im Repo etablierten Muster "eine Regel, mehrfach konsumiert" statt "eine Regel, mehrfach kopiert". Test der KLASSE: ein Test, der `ABSCHLUSS_SPALTEN` um eine testweise fuenfte Float-Spalte erweitert (oder synthetisch mit Monkeypatch eine zusaetzliche Spalte simuliert) und verlangt, dass sowohl ein NaN-Wert dieser neuen Spalte `validate_abschluss` rot macht als auch eine reine Wertaenderung dieser Spalte (bei sonst unveraendertem DataFrame) `pruefe_abschluss` rot macht — ergaenzend ein konkreter Regressionstest mit der genau hier gezeigten Manipulation (`korrekturschicht` isoliert veraendert, DK/RKW unveraendert) auf Basis der vorhandenen Fixture aus `tests/test_schicht_in_fuehrung.py`. Der Fix aendert keine Schema-Spalten und keinen Gate-Vertrag (Abschluss ist kein Gate-Producer), beruehrt aber die Durchsetzung einer bereits als Fachkonzept/ADR-011 sowie Grundsatzdokumentation 9.11 zugesagten Garantie ("nie unsichtbar") an einer bereits produktiv gelandeten Komponente (Freischaltung Schritt 5) — Entscheid des Maintainers vor Umsetzung angemessen, vergleichbar mit den bereits als `!`-Commits gelandeten Korrekturen derselben Freischaltungs-Serie.

### T25-11 — Reviewer Mittel — Urteil: bestaetigt

**Beweis.** Reviewer zitiert `gates/abox_merge.py:65-82` (Funktion) und Zeile 146 (Aufrufstelle) auf dem geprueften Stand `fe0e284`. Auf `10ee765` ist die Datei durch den zwischenzeitlichen Block-1-Commit (`31c1caf`, Belegidentitaet) um genau zwei Importzeilen gewachsen; dieselbe Funktion liegt heute auf **Zeile 67-84**, die Aufrufstelle auf **Zeile 148-158**:

```
67  def _aufgeloeste_diskrepanzen(fall: Path) -> List[str]:
71      pfad = fall / "abgeleitet" / "abox" / "abox.json"
72      if not pfad.is_file():
73          return []
74      try:
75          daten = json.loads(pfad.read_text(encoding="utf-8"))
76      except (OSError, ValueError):
77          return []
78      if not isinstance(daten, dict):
79          return []
...
148     entschieden = _aufgeloeste_diskrepanzen(fall)
149     if entschieden and not args.ueberschreiben:
151         return _fehler(Exit.FILE_CONTRACT, "abox_entschieden", ...)
```

Empirisch reproduziert (`.venv/bin/python`, `tempfile.TemporaryDirectory`, echter Code, Repro unter `/tmp/claude-1000/.../scratchpad/t25-11/repro_voll.py`, keine Aenderung am Worktree): Fall mit gueltigen Fragmenten/Akteuren angelegt (wie `_merge_fall` in `tests/test_belegidentitaet_t23.py:162-181`), dazu eine `abox.json`, die eine aufgeloeste Diskrepanz traegt, aber **nach dem Status-Marker abgeschnitten** ist (realistisches Bild eines Absturzes mitten im Schreiben):

```
--- vor dem Merge ---
Datei ist gueltiges JSON: nein (abgeschnitten)
enthaelt Marker 'aufgeloest': True
guard_result = []
--- nach dem Merge (ohne --ueberschreiben!) ---
exit_code = 0 errors = []
Datei wurde ersetzt: True
Diskrepanzen mit status=aufgeloest NACH dem Merge: []
Anzahl Diskrepanzen NACH dem Merge: 1
```

Der Merge lief **ohne** `--ueberschreiben` durch, Exit 0, keine Fehlermeldung, und die vorher aufgeloeste Diskrepanz ist verschwunden — exakt der Vorfall vom 2026-09-07, den `9573bfc` verhindern sollte, nur ausgeloest durch eine beschaedigte statt einer fehlenden Datei.

Zweiter Teilbefund (fehlende Sperre zwischen Pruefung und Schreiben) codeseitig verifiziert statt zeitlich reproduziert: `grep -n "lock\|sperr\|Lock\|Sperr"` ueber `gates/abox_merge.py`, `ontologie/abox.py`, `ontologie/befuellung.py`, `ontologie/entscheide.py` liefert **keinen** Treffer (nur das unrelated Wort "blockt"). Alle drei Schreibstellen von `abox.json` — `abox_merge.py:213`, `entscheide.py:174`, `entscheide.py:438` — rufen `ontologie.abox.speichere()` (`abox.py:35-44`) unbedingt auf; `speichere()` ist ein reines `pfad.write_text(...)`, weder gesperrt noch mit einem Compare-and-Swap auf den beim Lesen gesehenen Hash/Zustand versehen, und auch nicht atomar (kein temp+`os.replace`, im Unterschied zu `fall.py:475-503 _schreibe_json`). `entscheide.py:354/438` macht denselben ungesicherten Read-Modify-Write-Zyklus wie der Merge, nur ganz ohne Wache. Der Race ist damit strukturell belegt, nicht nur behauptet.

**Stand auf main 10ee765.** Unveraendert seit `9573bfc` (Teil von PR #17, Ahn von `fe0e284`, gelandet auf `main` ueber Merge `8725982`). `git log --oneline fe0e284..10ee765 -- src/rechner_pipeline/gates/abox_merge.py` zeigt nur zwei Commits an dieser Datei seither: `31c1caf` (T23 Block 1, reine Lese-Einmaligkeit fuer Fragmente/Register/Fragment-Hashes) und den Merge `8725982` selbst — `_aufgeloeste_diskrepanzen()` und die Aufrufstelle sind in `git show 31c1caf -- .../abox_merge.py` textidentisch zur Vorversion, nur um zwei Importzeilen verschoben. Kein Commit zwischen `fe0e284` und `10ee765` fasst diese Funktion, `speichere()` oder eine Sperre auf `abox.json` an.

**Schaden.** Kein falscher Zahlenwert wird als korrekt bestaetigt (nachgelagerte Gates verlangen fuer offene A-Q1-Diskrepanzen weiterhin Entscheidungen, ein frisch gemergter Bestand mit `status=offen` bliebe an spaeteren Wachen haengen) — der Schaden ist Verfuegbarkeit/Nachweis: die Arbeit des Verantwortlichen Aktuars (A-Q1-Aufloesungen) geht **still** verloren, exit 0, ohne jede Fehlermeldung, an genau der Stelle, die dafuer gebaut wurde. Die Wiederherstellung ist wie beim realen Vorfall nur ueber ein externes Backup moeglich, kein Gate im System bemerkt den Verlust automatisch. Verscharfend: die Vorbedingung "beschaedigte abox.json" ist nicht exotisch, sondern durch die eigene, nicht-atomare `speichere()`-Funktion direkt erreichbar — ein Absturz waehrend eines der drei Schreibvorgaenge auf dieselbe Datei kann die Datei selbst in genau den Zustand versetzen, den die Wache faelschlich als "nichts zu schuetzen" liest.

**Schwere.** Zustimmung zu "Mittel". Fuer eine Einstufung als "hoch" spraeche, dass der Bypass vollstaendig und lautlos ist (Exit 0) und die Vorbedingung durch eine benachbarte, im selben Modul liegende Schwaeche (fehlende Atomaritaet) real erreichbar ist, nicht nur theoretisch. Dagegen spricht: (a) der Pfad wird nur bei einem erneuten Merge auf einem bereits entschiedenen Fall getroffen — ein seltener, manueller Schritt, kein taeglicher Produktionspfad (anders als die mit "hoch" bewerteten T24-Befunde im Tageslauf); (b) kein falscher Wert wird als gueltig akzeptiert, der Schaden ist Rework/Restore, keine unbemerkte Bewertungsabweichung; (c) die Nebenlaeufigkeits-Halbseite (fehlende Sperre) setzt einen zweiten, tatsaechlich gleichzeitig laufenden Prozess voraus, der im aktuell beschriebenen Betriebsmodell (sequentielle, mandatsgebundene Einzel-Agent-Schritte) untypisch ist. "Mittel" ist damit vertretbar, aber am oberen Rand — die Reparatur sollte nicht aufgeschoben werden, weil sie an derselben Stelle liegt, die bereits einmal einen echten Datenverlust verursacht hat.

**Klasse (Invariante).** Eine Schutzwache, die aus dem gelesenen Zustand einer Ressource ableitet, ob eine schuetzenswerte Bedingung erfuellt ist, darf einen Lese- oder Parse-Fehler dieser Ressource nicht als "Bedingung nicht erfuellt" werten, sondern muss bei jeder Unklarheit ueber deren Zustand fail-closed abbrechen; und jeder Pfad, der dieselbe Ressource sowohl fuer eine solche Pruefung liest als auch — spaeter, unbedingt — neu schreibt, braucht eine Sperre oder ein Compare-and-Swap auf den gelesenen Zustand, sonst schuetzt die Wache nur den stoerungsfreien Normalfall, nicht die Fehler- oder Nebenlaeufigkeitsbedingung, gegen die sie eigentlich gebaut wurde.

**Weitere Stellen mit demselben Muster.**
- `src/rechner_pipeline/ontologie/entscheide.py:354` (`lade`) und `:438` (`speichere`) — derselbe ungesicherte Read-Modify-Write-Zyklus auf `abox.json` wie im Merge, hier sogar ganz ohne Wache; ein A-Q1-Beschluss, der waehrend eines laufenden Merges eingetragen wird, kann vom nachfolgenden `speichere()` des Merges kommentarlos ueberschrieben werden.
- `src/rechner_pipeline/ontologie/abox.py:35-44` (`speichere`) — schreibt `abox.json` per einfachem `write_text`, nicht atomar (kein temp+`os.replace`, im Gegensatz zum vorhandenen Muster `fall.py:475-503 _schreibe_json` plus `fall.py:551 _registrierungs_lock` fuer `eingang.json`). Das macht die Datei durch einen Absturz *waehrend des eigenen Schreibens* selbst zur Quelle der Beschaedigung, die die Wache dann faelschlich als "nichts zu schuetzen" liest — dieselbe Infrastruktur (Sperre + atomarer Write), die fuer `eingang.json` schon existiert, fehlt fuer `abox.json` komplett.
- Verwandtes, aber nicht identisches Muster (bereits als T24-01 in dieser Runde dokumentiert): `betrieb/tageslauf.py` `_verwaiste_staende_entfernen` behandelt ebenfalls einen unklaren Ressourcenzustand (`aktuell=None`) als "alles ist Waise, darf entfernt werden" statt fail-closed — dieselbe Denkfigur ("Unklarheit == keine Bedingung erfuellt") in einem anderen Teilsystem.
- Gesucht, nicht gefunden: eine weitere destruktive Wache (nicht nur informative `except`-Faenger wie `ontologie/impact.py:409`, ausdruecklich als "fail-soft" dokumentiert, oder `betrieb/uebernahme.py:167`, das den Fehler im Ergebnis ausweist statt ihn zu verschlucken) mit demselben "Fehler beim Laden == Bedingung nicht erfuellt, Aktion darf weiterlaufen"-Zuschnitt wie in `abox_merge.py`; `neuaufsetzen.py:138-140` macht es korrekt (fail-closed via `NeuaufsetzenError`) und dient als Gegenbeispiel.

**Fix-Umfang.** M. Vorschlag: (1) `_aufgeloeste_diskrepanzen()` unterscheidet "Datei fehlt ganz" (weiterhin `[]`, echtes "nichts zu schuetzen") von "Datei ist da, aber unlesbar/kaputt" — Letzteres darf nicht `[]` liefern, sondern muss einen eigenen fail-closed-Fehlercode ausloesen (z. B. `abox_unlesbar`, verweigert den Lauf unabhaengig von `--ueberschreiben`, denn ob dort Entscheidungen standen, ist gerade nicht feststellbar); (2) `ontologie.abox.speichere()` auf das bereits vorhandene atomare Muster (`fall.py:_schreibe_json`, temp+`os.replace`) umstellen, damit die Datei durch den eigenen Schreibvorgang gar nicht erst in einen kaputten Zwischenzustand fallen kann; (3) Lese-Pruef-Schreib-Zyklus von `abox.json` (Guard bis `speichere()` in `abox_merge.py`, sowie `lade`/`speichere` in `entscheide.py`) unter das vorhandene `_registrierungs_lock`-Muster stellen (Sperre auf einem stabilen Deskriptor, wie fuer `eingang.json` bereits etabliert). Test der KLASSE: ein Test, der eine abgeschnittene `abox.json` mit noch lesbarem `"aufgeloest"`-Text schreibt (wie mein Repro oben) und erwartet, dass `abox_merge` ohne `--ueberschreiben` mit einem Fehler abbricht statt mit Exit 0 durchzulaufen und die Datei unveraendert bleibt; zusaetzlich ein Test, der zwischen Guard-Lesung und `speichere()` (z. B. per Monkeypatch auf `speichere` selbst) eine externe Aenderung der Datei simuliert und verlangt, dass der Merge das erkennt (Sperre/CAS-Fehler) statt die externe Aenderung stillschweigend zu verlieren. Der Fix beruehrt den Gate-Vertrag von `abox_merge` (neuer Fehlercode/Exit-Verhalten von P-Q2.zusammenfuehrung) und eine gemeinsam genutzte Schreibfunktion (`ontologie.abox.speichere`, drei Aufrufer) — Entscheid des Maintainers vor Umsetzung angezeigt, vergleichbar im Umfang mit `9573bfc` selbst.

### T25-12 — Reviewer Niedrig — Urteil: bestaetigt

**Beweis.** Auf 10ee765 endet docs/faelle/baldrian-lauf2.md weiterhin auf
zwei Zeilenumbrueche (od -c: `.  \n  \n`). Einzeiler, im ersten Commit
des Branches.

### N-01 — Betrieb — Wache rot auf 10ee765: STO Jahr 10 um einen Cent anders als das Ledger des uebernommenen Bestands

**Nachstellung.** Kein eigener Tageslauf noetig — der bereits vorliegende rote Stand (`/home/bartl/git/rechner-pipeline/runs/plv-stand-rot-n01`, Eingang Snapshot `e21b66a6...`, Betriebsbeginn/Stichtag 2026-01-01, `heute` 2026-09-07/08) ist exakt die gesuchte Nachstellung: `journal/protokoll.jsonl` traegt `"urteil": "rot"`, `"pb1.befunde"` mit dem Originalwortlaut ("z. B. police 7000744 STO Jahr 10: Ledger 33148.91, Kern 33148.92; police 7000767 STO Jahr 10: Ledger 35544.55, Kern 35544.56 ..."), und `stand.neu/ledger.parquet` enthaelt die beiden Buchungen roh: Police 7000744, STO, Vertragsjahr 10, Datum 2026-07-01, Betrag 33148.910087; Police 7000767 analog 35544.550149. Beide Buchungen entstehen ERST im Tagesbetrieb (die Fall-eigene Uebernahme-Ablage `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/bestand/ledger.parquet` traegt fuer beide Policen nur die ZUG-Buchung zum Stichtag, kein STO) — die Diskrepanz ist also ein Befund der Wache selbst, nicht ein Altlast der Fall-Bytes. Zusaetzlich mit direkten Funktionsaufrufen auf den echten Fall-Bytes (`bestand.parquet`, `scheiben.parquet`, `schichten.parquet`, `verankerung.parquet` aus `faelle/baldrian-klv-tg2015-lauf2/abgeleitet/bestand/`, Config `configs/bestand_gesamt.toml` auf 10ee765) bit-genau reproduziert, siehe Ursache.

**Ursache.** Fund: `src/rechner_pipeline/betrieb/tageslauf.py::_wache` (Zeilen 497-510) baut das `eingaben`-Dict fuer die P-B1-Pruefengine

```
eingaben = {
    "portfolio": arbeit / "bestand_gesamt.parquet",
    "historie": arbeit / "historie.parquet",
    "ledger": arbeit / "ledger.parquet",
    "scheiben": arbeit / "scheiben.parquet",
    "config": config_pfad,
}
if (arbeit / "merkmale.parquet").is_file():
    eingaben["merkmale"] = arbeit / "merkmale.parquet"
```

— **ohne** `"schichten"` und `"verankerung"`, obwohl `_stand_bauen` (dieselbe Datei, Zeilen 411-435) `schichten.parquet` und `verankerung.parquet` immer dann ins selbe `arbeit`-Verzeichnis schreibt, wenn ein uebernommener Bestand eine Korrekturschicht traegt (hier: alle 834 Policen der Faelle-Uebernahme). `bestand/vorbedingungen.py::lies_und_pruefe_pb1` behandelt beide Rollen als optional (Zeilen 266-267: `tabellen.get("schichten")` / `tabellen.get("verankerung")`, kein Fehler bei Abwesenheit) und reicht `schichten=None, verankerung=None` an `pruefe_ledger_betraege` durch (`vorbedingungen.py:390-393`). In `bestand/ledger_bindung.py::pruefe_ledger_betraege` liefert `schichten_je_police(stamm, None, None)` sofort `{}` (Kurzschluss in `bestand/schichten.py:49-50`), und im STO-Zweig (`ledger_bindung.py:238-243`) greift `if schicht is not None and ...` nie — die Herleitung ist also **immer Basiswert ohne Korrekturschicht**.

Die BUCHENDE Seite rechnet dagegen korrekt: `_stand_bauen` reicht `schichten`/`verankerung` an `bestand.ereignisse.fortschreiben` weiter (`tageslauf.py:400-402`), und `_Vertrag.rkw` (`ereignisse.py:237-245`) addiert den Schichtwert exakt so, wie es die Grundsatzdokumentation/Freischaltung Schritt 5 verlangt: `wert = vertrags_rkw(...); if schicht is not None and 12*jahr >= schicht[1]: wert += schichtwert_bei(...)`. `vertrags_rkw` (`bestand/kernlauf.py:34-88`) ist in beiden Pfaden dieselbe Funktion mit demselben `stoab_je_baustein`-Schalter aus derselben Config — dort liegt also keine Divergenz.

Nachrechnung fuer Police 7000744 (TG2015, `stoab_je_baustein=True`, `scheiben_mit_gamma1=True`, 7 mitgebrachte Erhoehungsscheiben, Jahr 10):
- Basiswert `vertrags_rkw(...)` = 33148.91999593182 -> gerundet 33148.92 (= der von der Wache gemeldete "Kern"-Wert)
- `schichtwert_bei(rho=-2.5942776203533697e-08, monate_ta=108, monate=120)` = -0.009909180036844642
- Basis + Schicht = 33148.910086751785 -> gerundet 33148.91 (= exakt der gebuchte Ledger-Wert, bit-genau gegen `stand.neu/ledger.parquet` verifiziert: 33148.910087)

Fuer 7000767 analog: Basis 35544.560943657896 -> 35544.56 ("Kern"); Schicht -0.010794971051160415; Basis+Schicht 35544.550148686845 -> 35544.55 (Ledger, verifiziert 35544.550149).

Die rohe Differenz (0.0099 bzw. 0.0108) liegt ueber der `TOLERANZ` von 0.005 in `ledger_bindung.py:53` — kein Rundungsartefakt zweier gerundeter Summanden, sondern ein fehlender Summand: die Wache vergisst die Korrekturschicht vollstaendig, nicht nur in der Anzeige.

Warum war der Fall-eigene P-B1-Beleg (`faelle/baldrian-klv-tg2015-lauf2/abgeleitet/diagnostics/bestand_validate.gate.json`, `--bis 2026-01-01`) gruen? Sein `command_line` enthaelt ebenfalls **kein** `--schichten`/`--verankerung` (im Unterschied zu `diagnostics-nach/bestand_validate.gate.json`, das beides fuehrt) — dieselbe Luecke, aber folgenlos: Zum Stichtag 2026-01-01 enthaelt das Ledger nur ZUG-/PEX-Buchungen, und weder ZUG noch PEX rufen `schichtwert_bei` auf (nur STO, siehe `ledger_bindung.py:238-243`). Der gruene Beleg hat den betroffenen Pfad also nie durchlaufen — er beweist nicht, dass die Herleitung mit Schicht funktioniert, sondern nur, dass sie zu diesem Zeitpunkt nicht gebraucht wurde.

**Wer hat recht.** Das Ledger (33148.91 / 35544.55) ist korrekt — es ist der Wert, den die Fortschreibungs-Engine mit korrekt verdrahteter Korrekturschicht gebucht hat, im Einklang mit Kern 3.5.0 ("Storno zahlt Basis plus Schicht"). Die "Kern"-Herleitung der Wache (33148.92 / 35544.56) ist falsch — sie ist eine unvollstaendige Nachrechnung, der zwei von acht persistierten Eingangsrollen fehlen, nicht eine zweite, abweichende fachliche Meinung. Es ist auch kein fachlicher Unterschied (andere Schicht-Parameter/rho zu einem anderen Zeitpunkt): Schichtparameter, Verankerungszeitpunkt und Bausteine sind in Buchung und Wache identisch (dieselben persistierten `schichten.parquet`/`verankerung.parquet`-Bytes) — der Wache fehlt schlicht der Aufruf von `schichtwert_bei` ueberhaupt.

**Reichweite.** Betrifft die reale Ausfuehrung von Schritt 9 auf `~/apps/plv` identisch — die Luecke steckt im Code (`betrieb/tageslauf.py`), nicht in fallspezifischen Daten oder Zufallszahlen. `cli_abschluss.py` (der Abschluss-Produzent) verdrahtet `schichten`/`verankerung` dagegen korrekt (Zeilen 138, 185-186) und ist NICHT betroffen — die Bilanzzahlen des Abschlusses waeren also richtig, nur die taegliche Wache blockiert faelschlich. Betroffen ist grundsaetzlich jeder STO eines uebernommenen Vertrags NACH seinem Verankerungszeitpunkt und VOR einer heilenden Beitragsfreistellung/Herabsetzung (TOD/ABL/PEX loesen den Fehler nicht aus, PEX heilt die Schicht ohnehin auf rho=0). Bei allen 834 uebernommenen Policen dieser Migration ist das ein latentes Risiko: Je weiter der Lauf (z. B. bis 2027) fortschreitet, desto mehr Stornos dieser Kohorte werden erwartet und desto mehr WACHE-ROT-Tage entstehen — deterministisch reproduzierbar bei jedem erneuten Lauf desselben Tages, kein Ausreisser, der sich von selbst loest. Die hier beobachtete Differenz von rund einem Cent ist Zufall der Groessenordnung von rho (~-2,6*10^-8, eine fast perfekt kalibrierte Uebernahme); bei einer Police mit groesserem Anfangsresiduum waere die Differenz entsprechend groesser und der Befund fachlich sichtbarer.

**Fix-Umfang.** **S.** Lokalisiert in `src/rechner_pipeline/betrieb/tageslauf.py::_wache` (Zeilen 497-510): analog zum bestehenden Muster fuer `merkmale.parquet` (Zeilen 506-507) zwei bedingte Eintraege ergaenzen:

```python
if (arbeit / "schichten.parquet").is_file():
    eingaben["schichten"] = arbeit / "schichten.parquet"
if (arbeit / "verankerung.parquet").is_file():
    eingaben["verankerung"] = arbeit / "verankerung.parquet"
```

Kein Eingriff im Kern (Korrekturschicht/`schichtwert_bei` rechnet korrekt; `kern/__init__` Referenzwerte und `__version__` unberuehrt), kein Eingriff im Gate-Vertrag (`gates/bestand_validate.py`/`vorbedingungen.py` unterstuetzen die Rollen bereits korrekt und optional — nur der interne Aufrufer in `tageslauf.py` nutzt sie nicht). Kein Fachkonzept-Widerspruch — die Konzeptaussage ("Storno zahlt Basis plus Schicht") stimmt bereits mit der Buchungsseite ueberein, nur die Wache widersprach ihr aus einer Verdrahtungsluecke.

Regressionstest fuer die KLASSE (nicht nur den Einzelfall): ein Test in `tests/test_betrieb_tageslauf.py`, der einen minimalen uebernommenen Bestand mit **echtem, nicht-degeneriertem** rho != 0 aufbaut (die vorhandene Testsuite fuer `tageslauf`/`_wache` enthaelt aktuell keinen einzigen Treffer fuer "schicht", "verankerung", "STO" oder "rho" — die Luecke war fuer die Suite unsichtbar, weil nie eine Korrekturschicht durch die Wache lief), einen Tag mit STO-Ereignis eines uebernommenen Vertrags fortschreibt und `EXIT_OK`/keinen `"ledger:"`-Befund in `pb1.befunde` erwartet. Ergaenzend ein generischerer Test, der behauptet: jede optionale Bestand-Tabelle, die `_stand_bauen` tatsaechlich nach `arbeit` schreibt (Dateiexistenz), muss auch als Rolle in `_wache`s `eingaben` auftauchen — das faengt nicht nur diesen Fall, sondern jede kuenftige neue optionale Tabelle, die analog "geschrieben, aber nicht zurueckgelesen" wird.

**Nachtrag (merge-session, gelesen auf 27016d1; von der dev-session auf 10ee765 nachgelesen): Umfang M, nicht S.**
Die kanonische Tabelle gibt es schon: `bestand/manifest.py:47` fuehrt
`ROLLEN_DATEIEN` mit allen sieben Rollen (portfolio, historie, ledger,
scheiben, merkmale, schichten, verankerung) — benutzt nur von
`vorbedingungen.py:418`. Das Eingaben-Mapping der P-B1-Engine wird trotzdem
an vier Stellen von Hand gebaut: `gates/bestand_validate.py:250` (sieben,
vollstaendig), `bestand/cli_abschluss.py:125` (vollstaendig),
`bestand/cli_report.py:162` (vollstaendig), `betrieb/tageslauf.py:499`
(`_wache`, fuenf — schichten und verankerung fehlen). Drei von vier
stimmen; die Bauform (Liste abtippen) ist der Fehler, nicht die Stelle.
ZWEITE INSTANZ in derselben Datei: `tageslauf.py:675` (`_teilbestand`)
filtert eine eigene Rollenliste ohne schichten/verankerung, und `_bericht`
(Zeile 688ff.) reicht beide nicht an `render_html`, waehrend
`bestand/cli_report.py:254` sie reicht — der Tageslauf rendert den
Teilbestandsbericht ohne Korrekturschicht, der Fall denselben Bericht mit
ihr (gelesen, nicht gemessen; Nachmessung durch die merge-session
zugesagt). Invariante: *Wer die P-B1-Engine ruft, baut ihre Eingaben nicht
selbst, sondern aus ROLLEN_DATEIEN.* Fix: alle vier Aufrufstellen auf die
Tabelle (bedingt fuer optionale Rollen), `_teilbestand`/`_bericht` dazu,
AST-Ratsche nach dem Muster von `entferne_verzeichnis`, die jedes Modul
ausser dem Erbauer daran hindert, eine Rollenliste als Literal zu fuehren.
Zusammen mit dem Klassen-Test oben.

**Nachmessung Teilbestandsbericht und dritte Instanz (merge-session, gemessen auf 10ee765 im Wegwerf-Worktree; Fixture-Werte von der dev-session nachgelesen).**
Aufbau: Szenario aus tests/test_betrieb_neuaufsetzen.py (ein uebernommener
KLV-Vertrag mit Schicht unter 110 Vertraegen), Tageslauf 2026-02-03, dann
dieselben Tabellen zweimal gerendert — wie `_bericht` ruft (ohne
schichten/verankerung) und wie `cli_report` ruft (mit).

| Stichtag | DK ohne | DK mit | Differenz |
|---|---|---|---|
| 2026-01-01 | 1.498.235,80 | 1.511.940,45 | +13.704,65 |
| 2027-01-01 | 1.777.470,10 | 1.790.884,29 | +13.414,20 |
| 2030-01-01 | 2.022.301,29 | 2.034.472,51 | +12.171,22 |

Rueckkaufswert: dieselben Differenzen. Ein Vertrag mit Schicht verschiebt
den Gesamtstand um rund 13.700 Euro — ZWEITE INSTANZ bestaetigt, keine
bewusste Auslassung. Im HTML: ganzer Stand 218 geaenderte Zeilen,
Teilbestand 396, praktisch alles in den SVG-Kurven (Deckungskapital,
Beitrag, Achsenskalierung); die Zahlen im Fliesstext aendern sich nicht,
und das Wort "Korrekturschicht" kommt in KEINER Fassung vor. Der Abschluss
weist die Schicht als eigene Position aus, der Bericht nicht — gehoert in
den Umfang, sonst wandert die Kurve ohne Erklaerung.

DRITTE INSTANZ, mit Folgen fuer die REIHENFOLGE: die Fixture in
tests/test_betrieb_neuaufsetzen.py (Schritt 9, dev-session) fuehrt
`verankerungszustand="POL"` (schichten, Zeile 53) und `zustand_ta="POL"`
(verankerung, Zeile 62) — beides KEINE gueltigen Werte:
`gates/verankerung_belegen.py:59` fuehrt `ZUSTAENDE = ("beitragspflichtig",
"beitragsfrei")` und prueft bei :188 hart mit sprechender Meldung;
`models/bestand.py:1393` prueft nur "nicht leer". Der Betriebsweg laeuft
durch KEINE der beiden Pruefungen: eingang_anlegen, lies_uebernahme,
fortschreiben nehmen es an, es landet im Stand, und der repo-eigene Test
sichert einen GRUENEN Tageslauf auf diesen Daten zu. Der Erste, dem es
auffaellt, ist der Kern vier Schichten tiefer (`kern/zustandsmodell.py:119`,
ValueError "Unbekannter Startzustand 'POL'") — mit den Fixture-Werten
stuerzen BEIDE Renderwege ab. Folge: Reicht der Fix schichten/verankerung
an `_bericht` durch, OHNE vorher am Betriebseingang dieselbe Vokabelpruefung
zu fahren wie das Gate, wird aus einem falschen Bericht ein Absturz tief
im Kern. ERST die Pruefung am Eingang, DANN das Durchreichen; Fixture
korrigieren ("beitragspflichtig" bzw. "aktiv").

Zweite Invariante, neben die erste gestellt: *Was der Betrieb an
Nebentabellen liest, wird gegen dieselbe Vokabel gehalten wie im Gate.*
Klasse, dreimal an demselben Weg: der Betriebsweg benutzt weniger
Pruefungen als der Fallweg (Wache ohne Rollen, Bericht ohne Rollen, Eingang
ohne Vokabel). Umfang bleibt M, Reihenfolge: (1) Vokabel der Schicht-/
Verankerungstabellen als gemeinsame Konstante (models statt gates) und
Pruefung in validate_schichten/validate_verankerung, damit Gate UND
Betriebseingang sie fahren; (2) vier P-B1-Aufrufer auf ROLLEN_DATEIEN,
_teilbestand/_bericht dazu; (3) Bericht weist die Korrekturschicht als
Position aus; (4) AST-Ratsche gegen Rollen-Literale; (5) Fixture korrigiert,
Klassen-Test mit rho != 0 und STO.

Hinweise fuer den Bau (merge-session): Schritt 1 und 2 machen die Fixture
beide rot, auf zwei Arten — nach Schritt 1 weist die Validierung "POL" beim
Anlegen ab (harmlos, sprechend); nach Schritt 2 ruft die Wache
schichtwert_bei mit "POL" und der Tageslauf faellt mit ValueError aus dem
Kern statt mit einem Befund. Fixture also VOR Schritt 2 korrigieren. Und:
mit korrigierter Fixture rechnet die Herleitung erstmals MIT Schicht — die
Erwartungswerte des Regressionstests erst danach messen, nicht aus dem
heutigen Lauf uebernehmen (sonst wird die kaputte Welt festgeschrieben).

**Stand 2026-09-08: GEBAUT auf Branch hotfix-n01-betriebsweg = 5ca0306 (ab
main 10ee765; Suite 2025 passed, Exit 0; Code-Karte ohne Befund). Vierte
Instanz beim Bau gefunden: der Monatsabschluss des Tageslaufs bekam
Schicht und Verankerung ebenfalls nicht (schreibe_abschluss nimmt sie an).
Gebaut in der abgesprochenen Reihenfolge; Mutationsproben (Wache von
Hand, Bericht ohne Schicht, Eingang ohne Pruefung) je rot; Storno-Test bis
2030 mit rho 0,02 gruen, ohne die Rollen Exit 3. Testat der merge-session
angefragt, Push durch den Maintainer per Fast-Forward.**

**Zweiter Commit 5866157 (Testat-Vorbehalt zu 5ca0306): der fuenfte
Aufrufer.** gates/abnahmebericht.py fuehrte seine Positivliste der
Eingangsrollen als SET-Literal (die erste Fassung der Ratsche las nur
Dict/Tupel/Liste); die Liste kannte schichten/verankerung nicht und wies
den ehrlichen Nach-Beleg des Falls (acht Rollen) als ungueltig ab (T25-03
Teil a) — und ein abgewiesener Rollenblock brach mit KeyError 'portfolio'
ab statt mit dem Befund (gemessen von der merge-session am echten Beleg:
acht Rollen = Absturz, ohne die zwei Rollen = kein Absturz). Jetzt:
PB1_ROLLEN in bestand.vorbedingungen (Tabelle plus config), Engine und
Abnahmebericht nehmen es; Guard vor der Nachrechnung; PB1_VOLLPROFIL
bewusst Literal (Gate-Vertrag, benannte Ausnahme der Ratsche); Ratsche
liest Sets und verlangt genau fuenf Aufrufer. Damit ist T25-03 Teil (a)
"ehrlicher Vollbeleg wird angenommen" geschlossen; Teil (b) Pflichtrollen
bleibt Entscheid 3.

**Delta-Testat 5866157 (merge-session, ohne Vorbehalt): 2025 + 2 Regie =
2027 passed; PB1_ROLLEN wertgleich zum alten Literal der Engine (die
Annahmemenge der Engine aendert sich nicht, nur die Allowlist des
Abnahmeberichts von sechs auf acht); drei Mutationsproben unabhaengig
gefahren (ast.Set weg -> Ratsche UND Selbsttest rot; Guard weg ->
KeyError-Test rot; Sechser-Liste zurueck -> Beleg-Test UND Ratsche rot);
Gegenprobe Tageslauf aus der roten Referenz Zeichen fuer Zeichen wie bei
5ca0306; A-M4 auf dem echten Nach-Beleg (acht Rollen) ohne Absturz. GEWINN,
nicht beansprucht: der Befund "P-B1-Neupruefung [ledger]: 4 Buchung(en),
deren Betrag nicht aus dem Kern folgt", den derselbe Beleg mit auf sechs
gekuerzten Rollen brachte, ist weg — die Nachrechnung des Abnahmeberichts
bekommt Schicht und Verankerung jetzt tatsaechlich. 5866157 schliesst also
dieselbe Herleitungsluecke wie N-01 eine Ebene hoeher, im Abnahmeweg; das
bestimmt die Abwaegung zu T25-03 Teil (b) mit. Offen (Kleinigkeit): der
Docstring von test_kein_aufrufer_der_engine_baut_die_rollen_von_hand sagt
noch "Vier Aufrufer" — beim naechsten Anfassen auf dora-t24-t25.**
