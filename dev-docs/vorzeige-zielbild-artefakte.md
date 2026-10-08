# Zielbild der Vorzeige: was der Lauf liefern muss

Stand 2026-09-22. Übergabe der Seiten-Session an die dev-Session, nach
dem Strukturumbau der Fallseite (`fallseite-konzept.md`, Commits 82f47e0
bis 722d40c auf `vorzeige-url`).

**Worum es geht.** Die Vorzeige ist das Ontologiemodell der Darstellung:
Sie legt fest, wie eine Übernahme erzählt wird — Station für Station,
je Station Prüfung, Geschehen, Zahlen, Belege. Die Seite erzählt nur;
sie erzeugt nichts und rechnet nichts nach. Alles, was sie zeigt, muss
der Lauf hervorgebracht und ein Gate gebunden haben. Wo das heute nicht
geht, füllt die Seite die Lücke selbst — mit Ausweichseiten, eigenen
Nachrechnungen, von Hand gepflegten Zuordnungen. Jede dieser Krücken
steht hier, mit dem, was an ihrer Stelle aus dem Lauf kommen soll.

**Die Regel für jeden Punkt.** Ein Artefakt, das die Seite zeigt, ist
(a) von einem Kommando in `src/` erzeugt, (b) nach seinem Gate oder
seiner Station benannt, (c) von dem Gate gebunden, das für es einsteht,
und (d) in Unternehmenssprache geschrieben. Was die Seite heute daraus
ableitet, wird gelöscht, sobald der Lauf es liefert — kein Ausweichpfad
bleibt als Sicherheitsnetz stehen (siehe `BERICHTE_AUS_DEM_STAND`,
entfernt in 5906615: ein Ausweichpfad ist eine zweite Wahrheit).

**Wie mit der Liste zu arbeiten ist.** Gruppe A verlangt einen Neulauf
des Falls und danach die Neuzeichnung von A-M4, weil A-M4 die Prüfsummen
der betroffenen Artefakte bindet. Das ist teuer und soll GENAU EINMAL
geschehen — deshalb erst Gruppe C entscheiden (sie bestimmt, wie A2 bis
A4 gebaut werden), dann Gruppe B (billig, ohne Neulauf), dann Gruppe A in
einem Zug. Die Spalte „Offen“ nennt, was vor dem Bau mit der
Seiten-Session zu schärfen ist.

Erledigt und hier nur zur Einordnung: der eigene Monatsbericht
(`bestand/monatsbericht.py`), die Schalter `--berichtsstichtag` und
`--ohne-verlauf` des Bestandsberichts, `berichtshinweis` in der
Tagesbetriebs-Config, die Ereigniszuordnung der Monatszahlen im Paket
(alle auf `vorzeige-url`, Suite grün).

## C · Zuerst entscheiden: gebundene Zahlen, freie Darstellung

### C1 · Die Berichte sind als HTML gebunden

**Zielbild.** Das Gate bindet die ZAHLEN eines Berichts; wie sie
aussehen, entscheidet die Darstellung. Die Seite kann einen Bericht neu
setzen, ohne dass ein Mensch neu zeichnen muss — und ein Leser kann
jede Zahl auf der Seite gegen den gebundenen Beleg prüfen.

**Ist.** Die HTML-Berichte selbst sind Pflichtbelege und werden per
Prüfsumme gebunden: `fall.BELEGROLLEN` nennt für A-M1 bis A-M3 je
`aktuartest*_bericht` (die HTML-Datei), für A-M4 `abnahmebericht`
(`migrationsabnahme.html`); das A-M4-Ledger `abnahmebericht.gate.json`
führt unter `input_hashes` die Prüfsummen von `bestandsbericht-vor.html`
und `bestandsbericht-nach.html`. Folge in dieser Runde: Die
Bestandsberichte auf den Übernahmestichtag zu setzen (A1) ist eine reine
Darstellungsänderung — und verlangt trotzdem Neulauf und Neuzeichnung.

**Lücke.** Zahlen und Aufmachung hängen an derselben Prüfsumme. Jede
Layoutänderung entwertet die Zeichnung.

**Zu bauen (Vorschlag, zu schärfen).** Zwei Wege, einer ist zu wählen:

1. *Bindung auf die Daten.* Gebunden werden `aktuartest*.json`,
   `migrationssuite.json`, die Bestandsdaten des Berichts (Parquet oder
   ein eigenes `bestandsbericht-*.json`). Das HTML entsteht beim
   Seitenbau aus den gebundenen Daten durch einen Renderer in `src/`,
   den `werkzeuge/` aufruft; es trägt die Prüfsumme der Daten, aus denen
   es entstand, und die Version des Renderers. Wer den Beleg prüfen
   will, prüft die Daten.
2. *HTML bleibt Beleg, ist aber eine reine Funktion.* Das Gate bindet
   HTML UND Daten; der Renderer ist deterministisch und versioniert, und
   die Seite darf mit demselben Renderer aus denselben Daten neu setzen
   — bytegleich. Eine Layoutänderung ist dann eine Renderer-Version, und
   die Vorzeige zeigt beide Stände nebeneinander, bis neu gezeichnet ist.

Weg 1 ist der sauberere Schnitt (er entspricht der Regel „die Seite
rechnet nichts, sie setzt“); Weg 2 ist näher am heutigen Code. Die
Seiten-Session empfiehlt Weg 1.

**Wirkung.** Architekturentscheidung (ADR), danach Neulauf. Bestimmt A2,
A3, A4.

**Offen.** Welche Bestandsdaten ein Bestandsbericht bindet, wenn nicht
sein HTML: die Stichtagssicht als Parquet, oder ein Auszug? Und ob der
Monatsbericht des Tagesbetriebs (`stand.json` nennt ihn mit Hash)
denselben Weg geht.

### C2 · Das Datenmodell der Darstellung kommt aus dem Lauf

**Zielbild.** Der Fall trägt ein Verzeichnis dessen, was ihn ausmacht —
eine `fallakte.json` oder ein Index je Station: welche Artefakte an
welcher Station entstanden sind, mit Prüfsumme, Gate und Stand. Die
Seite liest diesen Index und setzt ihn; sie leitet nichts ab.

**Ist.** `werkzeuge/falldaten.py` (rund 1.500 Zeilen) LEITET das Modell
aus den Artefakten AB: Es zählt Diskrepanzen und gruppiert sie, rechnet
Kreuzproben (`Abgänge gegen beendende Vorfälle`), bildet Abgrenzungen
(„die Stichtage sind unterschiedlich tief geprüft“, „Entscheide auf
9 Systemständen“), misst Lücken, ordnet Berichte Stationen zu
(`darstellung.STATION`) und Gates zeichnenden Rollen
(`unternehmensseite.GATE_ZEICHNER`). Das ist Fachlogik im
Darstellungswerkzeug — und sie ist die Stelle, an der die Seite dem Lauf
widersprechen kann (Vorfall 2026-09-20: 2.530 nachgerechnet gegen 2.531
im Abschluss, `vorzeige-backlog.md`).

**Lücke.** Der Lauf sagt nicht, was er hervorgebracht hat; die Seite
sucht es sich zusammen.

**Zu bauen.** Ein Kommando am Ende des Laufs (oder A-M4 selbst) schreibt
den Index: je Station die Artefakte (Pfad, Prüfsumme, Gate, Ledger,
Entscheid-Snapshot), je Abnahme die Kennzahlen, die die Seite zeigt
(geprüft, bestanden, größte Abweichung, Schranke, Prüflücken), die
Abgrenzungen als Aussagen des Laufs, nicht der Seite. `falldaten.py`
schrumpft dann auf Lesen und Prüfen.

**Wirkung.** Erzeuger-Änderung; sobald der Index Pflichtbeleg von A-M4
ist, ein Neulauf.

**Offen.** Schnitt des Index: eine Datei je Fall oder eine je Station;
welche Aussagen der Lauf über sich trifft und welche die Seite formuliert
(die Abgrenzungen sind heute Prosa in `falldaten.py` — wer besitzt den
Satz?).

### C3 · Die Seite kann die Zeichnung nicht prüfen

**Zielbild.** Wer die Seite liest, kann selbst prüfen, dass ein Entscheid
von der Rolle gezeichnet ist, die er nennt — ohne Schlüsselmaterial des
Unternehmens.

**Ist.** Die Freigabe ist ein HMAC (`gate_entscheid.py`,
`P9_FREIGABE_VERFAHREN`): symmetrisch, der Prüfer braucht den Schlüssel.
Die Seite verifiziert deshalb bewusst keine Signatur und darf das Wort
„gezeichnet“ nicht tragen (T20-02, Test
`test_vorzeigeseite_nennt_nichts_gezeichnet_ohne_verifizierte_signatur`).
Sie zeigt „Entscheid liegt vor“ und die Schlüsselklasse aus dem
Snapshot.

**Lücke.** Die stärkste Aussage des Verfahrens — ein Mensch hat
gezeichnet — ist öffentlich nicht nachprüfbar.

**Zu bauen.** Asymmetrische Signatur (etwa Ed25519) je Rolle; der
öffentliche Schlüssel steht in der Zeichnungsordnung, deren Hash ohnehin
in jedem Snapshot liegt. Die Seite prüft beim Bau und schreibt dann
„gezeichnet: Verantwortlicher Aktuar, Schlüssel: Simulation“.

**Wirkung.** ADR (ersetzt das Freigabeverfahren P9); Neulauf, weil alle
Snapshots neu entstehen. Nicht vor C1.

**Offen.** Ob die Vorzeige das braucht oder ob „Entscheid liegt vor,
Klasse simulation“ für die Vorführung genügt. Das ist eine Frage an den
Maintainer, keine an dev.

## A · Ein Neulauf, eine Neuzeichnung

Alle Punkte dieser Gruppe verändern Artefakte, deren Prüfsummen A-M4
bindet. Sie werden zusammen umgesetzt und mit EINEM Neulauf des Falls
wirksam; danach zeichnet der Verantwortliche Aktuar A-M4 neu.

| Nr | Stelle | Zielbild | Ist | Lücke / zu bauen |
|---|---|---|---|---|
| A1 | Belege an Station 1 und 13, Ausgangslage | Drei Bestandsberichte auf denselben Horizont: Übernahmestichtag 01.01.2026, keine Projektion; der gelieferte Bestand ohne Verlaufsteile, weil er keine Historie hat | Eigener Bestand bis 2046, gelieferter bis 2026, geführter bis 2027, je mit Projektion. Die Schalter `--berichtsstichtag` und `--ohne-verlauf` sind gebaut und in den Skills dokumentiert | Der Fall muss mit den Schaltern laufen; `abnahmebericht.gate.json` bindet die Prüfsummen von `bestandsbericht-vor/-nach.html` → Neuzeichnung. Mit C1 Weg 1 entfällt die Bindung der HTML |
| A2 | Belege an Station 9–12 | Ein Prüfbericht heißt nach seinem Gate: `abnahme-A-M1.html` … `abnahme-A-M4.html`, ebenso die JSON. Wer an Station 9 sucht, sucht „A-M1“ | `aktuartest.html` ist A-M1, `aktuartest-A-M2.html` A-M2, `migrationsabnahme.html` A-M4; die JSON tragen keine Gate-Kennung als Feld (`aktuartest.json` hat weder `gate` noch `abnahme`). Die Seite kennt die Zuordnung nur aus `darstellung.STATION` | Erzeuger (`gates.aktuartest`, `gates.abnahmebericht`) schreiben Gate-Kennung in Dateiname UND als Feld; `fall.BELEGROLLEN` und die Skills ziehen nach. Die alten Namen stehen in den Ledgern → Neulauf |
| A3 | Station 6 | Der Übersetzungsbericht entsteht im Lauf und ist gebunden | `transformation_anwenden --bericht` kann ihn schreiben, kein Skill ruft es; im Fall fehlt er. Die Seite rendert eine Ausweichseite `uebersetzung.html` aus dem Modell (`vorzeigeseite._uebersetzungsbericht`) | Skill `transformiere-quellbestand` ruft `--bericht abgeleitet/berichte/uebersetzungsbericht.html`; A-M4 bindet ihn (unter `renderer_artefakte` stehen heute nur Spec und Ergebnis). Die Ausweichseite wird gelöscht |
| A4 | Station 2, 3, 4, 7, 8 | Je Station EIN lesbarer Bericht aus den gebundenen Daten: Quellfragmente (2), Faktenbasis mit Diskrepanzen (3), Abdeckungsbericht (4), Golden-Master-Beleg je Generation (7), Verankerungsbericht (8) | Die Daten liegen im Fall und sind gebunden — `abox/abox.json`, `abox/coverage.json`, `generation_golden.<generation>.<hash>.beleg.json` stehen in den 68 Artefakt-Hashes von A-M4 —, aber nur als JSON. Die Seite schreibt Sätze daraus und verlinkt das Ledger | Renderer je Bericht (nach C1). Bis dahin zeigt die Seite an diesen Stationen Zahlen ohne Belegkachel |
| A5 | Verzeichnis der Artefakte, „Alle Prüfläufe und ihre Ledger“ | Ein Ledger heißt nach seinem Gate: `P-Q1.quellfragment.gate.json` | `extract.gate.json`, `abox_merge.gate.json`, `gate_entscheid_am1.gate.json` — benannt nach dem Kommando. Das Feld `gate` im Ledger trägt die Kennung; die Seite löst über die Kette auf | Beim nächsten Neulauf mitnehmen, nicht allein dafür laufen. `BELEGROLLEN` (`pq3_ledger`, `pb1_ledger`) nennt die Pfade |
| A6 | Was sich am System änderte | Der Umbau des Zielsystems ist Teil der Abnahmekette: ein Gate hält ihn an, die Abschlusszeichnung bindet ihn, die Seite zeigt ihn an seiner Station mit Gate | `umbaubudget.json`/`umbaubericht.html` werden gemessen und ausgewiesen; kein Gate, keine Bindung. Die Seite führt ihn als Rahmenkapitel und sagt das | Architekturentscheidung: Pflichtbeleg von A-M4 oder eigenes Gate an Station 7 (Rechenkern). ADR zuerst, dann Neulauf |
| A7 | Lücke im Kopf der Seite | Kein Lauf ohne Image-Digest; die Seite trägt keine Lücke „nicht auf ein Container-Image rückführbar“ | Der Lauf vom 20.09. lief lokal; `betrieb/seite.py:luecken` weist es aus, der Seitenbau sagt „so nicht veröffentlichen“ | Kein Code: Der Neulauf dieser Gruppe läuft in der Laufzeitumgebung (Container), dann steht der Digest im Protokoll |

## B · Erzeuger und Verträge, ohne Neulauf der Gates

| Nr | Stelle | Zielbild | Ist | Lücke / zu bauen |
|---|---|---|---|---|
| B1 | Kopf der Fallseite, Block auf der Startseite | Der Fall nennt sich selbst: abgebende Gesellschaft, Tarifgeneration, Übernahme- und Kontrollstichtag, eine Beschreibung in Unternehmenssprache | `fall.json` = `{name, beschreibung, scope, angelegt_am}`. Die Seite schneidet „Baldrian“ aus dem Verzeichnisnamen (`_fallname_kurz`), holt die Stichtage aus dem Controlling und die Generation aus den Parametern; die Beschreibung lautet „Vorführfall Vier-Rollen-Regie“ | `fall.json` um `abgebende_gesellschaft`, `tarifgeneration`, `uebernahmestichtag`, `kontrollstichtag` ergänzen (Schema 2 des Manifests); `fall.lade_scope` prüft sie. Kein Neulauf: Manifest, kein Beleg |
| B2 | Station 1 | Jede registrierte Datei trägt ihre Rolle in der Lieferung: Bestandsabzug (mit Stichtag), Tarifbeschreibung, Tarifrechner, Erwartungswerte (wofür), Auskunft auf Nachfrage. Die Seite gruppiert danach statt Dateinamen aufzuzählen | `eingang.json` je Quelle `{datei, bytes, sha256, quelle_pfad, registriert_am, nachgereicht}`. Die Rolle steht nirgends; die Seite erkennt Bestandsabzüge am Namen (`--abzug`) | Feld `art` je Quelle, vergeben bei der Registrierung (`gates.registriere_eingang`, Skill `migrationsfall-durchfuehren`). Die Ansichten (CSV-Vorschau, PDF) baut weiterhin die Seite — das ist Darstellung |
| B3 | Station 5 bis 12, KI-Seite | Das Register sagt je A-Gate, welche menschliche Rolle zeichnet | `gates.register.Gate` kennt Art (P/A) und Gegenstand, keine Rolle. Die Zuordnung steht in ADR-010/-012/-018 und im Docstring von `gate_entscheid`; die Seite pflegt sie als `unternehmensseite.GATE_ZEICHNER`, ein Test hält sie gegen `GUELTIGE_GATES` | Feld `zeichnet` am `Gate` (etwa `"mensch/aktuariat"`), Test gegen `models.zeichnung`; die Seite liest es und löscht `GATE_ZEICHNER`. Denselben Satz braucht `it/pruefgates` |
| B4 | KI-Seite, Rollen | Die Rollen des Repos stimmen mit ADR-018 überein | `faelle/zeichnungsordnung.json` ist Schema 1, das `models.zeichnung` abweist (tote Datei, bis 722d40c von der Seite gelesen). ADR-018-Nachtrag nennt `agent/betrieb` als fünfte Agentenrolle, es gibt keine Definition; AGENTS.md sagt vier | Tote Datei löschen oder durch Schema 2 ersetzen (Schlüsselmaterial: Maintainer); `agent/betrieb` definieren oder den Nachtrag präzisieren; AGENTS.md nachziehen |
| B5 | Block je Übernahme auf der Startseite | Dauer und Kosten einer Übernahme stehen im Fall | Beide Zeilen sind Platzhalter „noch nicht erfasst“. Die kalendarische Dauer ist heute schon ableitbar (erste Registrierung in `eingang.json` bis Abschluss-Entscheid A-M4); Aufwand und Kosten stehen nur im Sitzungstranskript, das `werkzeuge/verlaufsprotokoll.py` liest — herstellergebunden, kein Pipeline-Teil | `abgeleitet/aufwand.json`, geschrieben vom Abschluss (A-M4): Dauer aus Registrierung und Entscheid, Aufwand als DEKLARIERTER Wert aus dem Mandat oder dem Protokoll des Operators. Wie Kosten gemessen werden (Token, Stunden), ist eine Frage an den Maintainer (vgl. `vorzeige-backlog.md`, Zeile „Dauer und Kosten je Migration“) |
| B6 | überall, wo Text des Laufs auf die Seite gelangt | Unternehmenssprache mit Umlauten in jedem Text, den ein Leser sieht | `gates/register.py` Z. 104 „über“, Z. 113 „prüft“ — Tippfehler in Sätzen, die sonst Umlaute schreiben. `betrieb/seite.py:586,590` „rückführbar“ (Lücken-Wirkung). Im Fall: `fall.json` „Vorführfall“, Umbau-Begründung „Fähigkeiten planmäßig“, „nachträglich“ | Register und Betriebs-Lücken korrigieren; die Fall-Texte entstehen beim Neulauf neu (B1, Umbau-Begründung im Mandat). Die vier Sätze aus `werkzeuge/falldaten.py` (Kreuzprobe, Abgrenzungen) gehören der Seiten-Session und sind dort bereinigt |
| B7 | Startseite, „Laufende Übernahme“ | Ein Fall im Modell trägt den Status „laufend“, der Kasten entsteht daraus | Prosa-Platzhalter „Baldrian Rentenversicherungen“ | `fall.json` bekommt `status` (laufend, abgeschlossen); gehört mit B1 in dasselbe Schema |

## Aus der Abstimmung vom 29.09. (Workshop 06.10.)

* **Baubericht des ersten Rechenkern-Laufs und Diff-Belege** — Station 7
  soll anfassbar sein: neben dem Umbaubericht ein Baubericht zum Einbau
  der Tarifgeneration, danach je Korrekturiteration die Diff-Dateien bis
  auf Code-Ebene, als Fall-Artefakte unter `abgeleitet/berichte/`. Die
  Prozesskarte nennt die Zeile heute als „In Arbeit“.
* **Prüfung und Abnahme bei „Bestand übersetzen“** — an der Station der
  ganzen Datentransformation gibt es weder ein Gate noch eine Zeichnung.
  Als Systemmangel benannt, zu beheben bis 13.10., nach dem Workshop. Die
  Karte zeigt den Kasten grau und die Zeile „Prüfung und Abnahme“ als
  „In Arbeit“.
* **Je Station eine Seite** — je Kachel der Prozesskarte eine Seite mit
  den Prüfungen und den typischen Artefakten dieser Station, die
  Prüfungen inhaltlich angesehen, nicht nur verlinkt. Ausdrücklich erst
  nach dem Seminar; bis dahin führt jeder Kasten zur Station der
  Fallseite und zu höchstens vier Artefakten.

## D · Später, mit Verweis

Punkte, die schon in `vorzeige-backlog.md` stehen und dort ihren Grund
haben; hier nur, damit die Liste für dev vollständig ist:

* **Zwei Nummernkreise (T24-08)** — nach dem nächsten Neuaufsetzen
  vergibt das Zielsystem eigene Policennummern; die Seite braucht dann
  einen Satz an Station 13. Nicht vorher bauen.
* **Rentenzahlungen als eigene Größe** — Stromgröße über den
  Rentenbestand, braucht eine Buchung im Tagesjournal. Nicht bestellt.
* **Bruttojahresbeitrag im Bestandsmodell** — Beitrag je Vertrag im
  Tagesjournal als eigene Betragsart.
* **Ereigniszuordnung an EINER Stelle** — Umzug von `ZUGANGSQUELLEN` /
  `LEISTUNGSARTEN` nach `models/bestand.py`, mit Test in beide
  Richtungen.
* **Tagesseite im Layout des Auftritts** — `betrieb/seite.py` rendert
  `plv/seite/` mit eigenem Stylesheet; die Unternehmensseite sagt
  deshalb „sieht anders aus als die übrigen“. Zielbild wie C1: das Paket
  liefert Daten, die Seite setzt. Niedrige Dringlichkeit.

## Was die Seite dann wegwirft

Damit dev sieht, wofür die Punkte gebaut werden — je Lieferung entfällt
in `werkzeuge/`:

| Lieferung | Entfällt |
|---|---|
| A2 | `darstellung.STATION` (Berichtstitel → Station); die Zuordnung kommt aus dem Dateinamen bzw. dem Feld |
| A3 | `vorzeigeseite._uebersetzungsbericht` und die Ausweichseite `uebersetzung.html` |
| B1 | `vorzeigeseite._fallname_kurz`; Stichtage und Generation aus Controlling und Parametern |
| B3 | `unternehmensseite.GATE_ZEICHNER` samt Test |
| C2 | der Großteil von `werkzeuge/falldaten.py`: Diskrepanz-Gruppierung, Kreuzproben, Abgrenzungen, Lückenmessung |

## Reihenfolge, wie die Seiten-Session sie vorschlägt

1. C1 entscheiden (ADR). Ohne diese Entscheidung baut A2–A4 zweimal.
2. B1, B2, B3, B7 — Manifeste und Register, kein Neulauf, je ein kleiner
   Commit mit Test.
3. B4, B6 — Aufräumen, kein Neulauf.
4. A6 entscheiden (ADR), C2 schneiden (Abstimmung mit der
   Seiten-Session: welche Aussagen der Lauf über sich trifft).
5. A1–A6 bauen, EIN Neulauf in der Laufzeitumgebung (A7), A-M4 neu
   zeichnen.
6. B5 und C3 danach, nach Entscheid des Maintainers.

Die Seiten-Session zieht `werkzeuge/` je Lieferung nach und löscht die
Krücke im selben Commit, in dem der Lauf das Artefakt liefert.
