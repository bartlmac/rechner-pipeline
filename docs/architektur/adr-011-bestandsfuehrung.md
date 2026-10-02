# ADR-011: Bestandsfuehrung mit gefuehrtem Zustand und Journal

Status: akzeptiert (Auftraggeber, 2026-08-26); Umsetzung in diesem Branch.

## Kontext

Das Repo enthaelt fuenf Komponenten, die bisher nicht sauber benannt
waren: (1) das KI-System fuer Rechenkern-Entwicklung und Migration
(Architektur, Pipeline, Agenten, Ontologie), (2) den Vorzeige-Zielbestand
der fiktiven Pfefferminzia samt Kern, (3) die Migrationsfaelle, (4) die
Simulation, die den Vorzeigebestand EINMALIG erzeugt, und (5) die
Simulation von Quellbestaenden fuer Migrationsfaelle (Regie, ausserhalb
des Pakets).

Die Komponenten (2) und (4) sind im Code vermischt, und zwar an der
tragenden Stelle: **Es gibt keine Bestandsfuehrung, sondern nur eine
Simulation mit nachgelagerter Ableitung.** Der Stammsatz eines Vertrags
traegt seinen URSPRUNGSzustand (status_id 1, POL, Statusdatum =
Versicherungsbeginn — von validate_portfolio erzwungen); alles Spaetere
liegt als Zeilen der Statushistorie daneben. Jede Bewertung baut daraus
zuerst eine Mehrzeilen-Sicht (`bestand_mit_historie`) und waehlt dann
rueckwirkend die juengste Statuszeile zum Stichtag aus (`zeitscheibe`) —
an sechs Stellen in Auswertung, Kennzahlen und Bericht. Die Verweildauer
im Zustand wird bei jeder Bewertung aus der Historie zurueckgerechnet
(`_bu_phasenbeginne`, `_pex_jahre`).

Kein Bestandsfuehrungssystem arbeitet so. Es fuehrt den Zustand als
DATUM im Vertragssatz ("Status BU seit 01.04.2023"), gesetzt in dem
Moment, in dem der Geschaeftsvorfall gebucht wird; die Historie ist ein
Journal fuer Nachweis und Auskunft, nicht die Eingabe der Bewertung.

Die Vermischung war fuer den selbst erzeugten Schaubestand konsistent
(der Ereignisstrom IST dort die Wahrheit) und bricht genau am
eigentlichen Zweck des Systems: Ein migrierter Vertrag kommt als
Zustandsschnappschuss ohne Historie (Grundsatzdokumentation 9.12 und 9.14). Im heutigen
Modell muesste man ihm eine Historie ERFINDEN, damit die Ableitung
funktioniert — das Replay-Surrogat, das die Methode ausdruecklich
ausschliesst. Drei
zuvor getrennt gemeldete Befunde haben diese eine Ursache: die
fehlenden Verankerungsattribute (s_0, d_0, t_a), der gamma1-Defekt der
Erhoehungsscheiben (Rekonstruktion zur Bewertungszeit statt Persistenz
der Schicht-Rechnungsgrundlagen; gemessen +2,0 % Jahresbeitrag der
Scheibe) und die Ableitung des Zustands zur Bewertungszeit selbst.

## Entscheidung

### 1. Drei Komponenten, drei Rollen

* **Bestandsfuehrung** (`bestand/fuehrung.py`, neu): fuehrt je Vertrag
  den AKTUELLEN Zustand — Status, seit wann (`status_date` = Beginn des
  aktuellen Status), Summen, Beitrag, Schichten mit ihren eigenen
  Rechnungsgrundlagen — und das **Journal** als vollstaendige, nur-anfuegbare Aufzeichnung —
  das Statusjournal (Historie) fuehrt die Zustandswechsel, das
  Betragsjournal (Ledger) die Geschaeftsvorfaelle mit ihren
  Kern-Betraegen; die Fuehrung setzt den Stammzustand aus dem
  Statusjournal. Der gefuehrte Stamm und das Journal sind per Invariante
  deckungsgleich: Der Stammzustand IST der juengste Journalstand.
* **Bewertung** (`bestand/auswertung.py`, umgebaut): rechnet
  ausschliesslich aus dem gefuehrten Zustand. Verweildauer =
  f(status_date, Stichtag); PEX-Jahr = f(insurance_start, status_date).
  **Kein Bewertungspfad liest das Journal.** Das ist dieselbe
  Historienfreiheit, die die Grundsatzdokumentation (9.14) vom Rechenkern verlangt —
  eine Ebene hoeher angewendet.
* **Simulation** (`bestand/ereignisse.py`, Rolle geschaerft): erzeugt
  den Vorzeigebestand einmalig, als Strom von Buchungen. Ihr Ergebnis
  ist ein GEFUEHRTER Bestand (aktueller Stamm + Journal), kein
  Rohmaterial, aus dem sich jeder Leser den Zustand selbst ableitet.

```mermaid
flowchart LR
    SIM["Simulation
GeVo-Strom, einmalig"]
    subgraph BF["Bestandsführung"]
        STAMM["geführter Stamm
aktueller Zustand je Vertrag"]
        JOURNAL[("Journal
Historie + Ledger, nur anfügbar")]
    end
    MIG["Migrationszugang — geplant
Journal beginnt mit Übernahme"]
    AUSKUNFT["Auskunft
bestand_am(tag)"]
    BEW["Bewertung
Werte aus dem Zustand"]
    BERICHT["Bestandsbericht
Nachweisungen · Bewegungskonto"]

    SIM -- "fuehre_fort" --> STAMM
    SIM --> JOURNAL
    MIG -. "fuehre_fort" .-> STAMM
    MIG -.-> JOURNAL
    JOURNAL -- "Rückschau je Tag" --> AUSKUNFT
    AUSKUNFT -- "Zustand am Tag X" --> BEW
    STAMM --> BEW
    BEW --> BERICHT
    BEW -- "friert Stichtag ein (einmalig)" --> ABSCHLUSS[("Abschlüsse
festgeschrieben je Stichtag, nie überschrieben")]
```

Die zwei Invarianten stehen bewusst als Text statt als Kanten im Bild
(ein Verbot als gemalte Kante laese sich wie ein Datenfluss): Kein
Bewertungspfad liest das Journal, und der Stammzustand ist der
juengste Journalstand — Gate P-B1 erzwingt die Deckung.

### 2. Ein Buchungsweg

Zustandsaenderungen laufen ueber genau eine Stelle
(`fuehrung.fuehre_fort`): Sie nimmt das Journal entgegen und setzt daraus
den neuen Stammzustand — der gemeinsame Trichter fuer die Simulation
heute und fuer den Migrationszugang morgen. Die Journalzeilen selbst
entstehen davor, bei der Simulation in `ereignisse.fortschreiben`. Zwei Schreibwege auf denselben Bestand sind der
Mechanismus, aus dem Drift entsteht; der gamma1-Defekt war genau das im
Kleinen.

### 3. Auskunft statt Zeitscheibe

Die Rueckschau "Bestand am Tag X" ist eine **Auskunftsfunktion aus dem
Journal** (`fuehrung.bestand_am`): Sie rekonstruiert den gefuehrten
Zustand zu jedem frueheren Datum — moeglich, weil das Journal
vollstaendig gespeichert bleibt. Berichte (Verlaufe, Bewegungskonto,
Nachweisungen) komponieren Auskunft + Bewertung: Zustand am Tag aus dem
Journal, Werte aus dem Zustand. Auskunft DARF das Journal lesen — das
ist ihr Zweck; nur die Bewertung darf es nicht.

Das Modul `bestand/zeitscheibe.py` — die rueckwirkende
Simulations-Sicht — wird pensioniert. Die reinen Kalenderhelfer
(`months_between`, `derived_age`) ziehen in die Fuehrung um.

### 4. Schichten sind Vertragsbestandteil

Erhoehungsscheiben tragen ihre Rechnungsgrundlagen selbst (zunaechst:
`gamma1`, per Tarifwerk-Regel 0 — Bezugsgroesse bleibt die GrundVS).
Die Bewertung liest die Schicht, statt sie aus der Tarifgeneration zu
rekonstruieren. Das behebt den gemessenen Defekt und ist zugleich die
Richtung der Grundsatzdokumentation (9.11: Parameter persistieren, Werte
reproduzierbar).

### 5. Der Stammsatz traegt den aktuellen Zustand

`bestand.parquet`/`bestand_gesamt.parquet` wechseln die Semantik: Die
Statusspalten (`status_id`, `status_code`, `status_date`) beschreiben
den aktuellen Zustand am Fuehrungsstand, nicht mehr den Ursprung. Die
Spaltenmenge bleibt unveraendert. `validate_portfolio` prueft kuenftig:
gueltiger Status (auch terminal), `status_date` zwischen
Versicherungsbeginn und Fuehrungsstand, `status_id` = Nummer des
juengsten Statuswechsels; Gate P-B1 prueft zusaetzlich die
Deckungsgleichheit von Stamm und Journal. Die bisherige
Ursprungszustands-Invariante gilt weiterhin — aber als Aussage ueber den
JOURNALANFANG (erste Zeile je Vertrag), nicht ueber den Stammsatz.

Damit hat auch der Migrationszugang seinen Platz, ohne dass hier gebaut
wird: Ein uebernommener Vertrag ist ein Stammsatz mit geliefertem
Zustand (s_0, d_0 via status_code/status_date, t_a), dessen Journal mit
dem Uebernahme-Ereignis BEGINNT statt mit dem Vertragsbeginn.

### 6. Abschluesse sind festgeschrieben

Berichte werden jederzeit neu gerechnet — ein ABGESCHLOSSENER Stand
nicht: Der Bilanzwert eines Stichtags darf sich nachtraeglich nicht
bewegen, auch wenn der Kern sich weiterentwickelt (Leitlinie des
Auftraggebers: Logik eines funktionierenden Unternehmens). Deshalb
gehoeren Abschluesse zum Datenhaushalt der Fuehrung
(`bestand/abschluss.py`, Tabellenfamilie `ABSCHLUSS_SPALTEN`):

* Ein Abschluss friert die einzelvertraglichen Bewertungsergebnisse
  eines Stichtags ein — gerechnet ueber DIESELBE Strecke wie jede
  andere Bewertung (`auswertung.einzelwerte_am`); ein zweiter
  Rechenweg waere der Drift-Mechanismus dieses ADRs.
* Je Stichtag existiert genau ein Abschluss; ein zweiter Versuch ist
  ein harter Fehler, kein stilles Ueberschreiben. Jede Zeile traegt
  die `kern_version` ihres Entstehens.
* Die Kontrolle (`pruefe_abschluss`) stellt die Neuberechnung gegen
  den festgeschriebenen Stand: Abweichungen — etwa nach einem
  Kern-Update — werden je Police und Groesse AUSGEWIESEN und ersetzen
  den Abschluss nie. Eine Korrektur eines festgeschriebenen Standes
  ist eine menschliche Entscheidung mit eigenem Vorgang.

### 7. Ein Lauf traegt seinen Lieferschein

Die Teile eines Laufs (Stamm, Journal, Ledger, Scheiben, Config)
gehoeren nur zusammen, wenn sie nachweislich aus DEMSELBEN Lauf
stammen — und der Horizont, bis zu dem der GeVo-Strom simuliert wurde,
ist eine Eigenschaft des Laufs, nicht des Aufrufs, der ihn spaeter
liest. Beides stand bisher nirgends: Die Konsumenten nahmen `--bis`
als Behauptung entgegen, und ein Bundle aus Teilen zweier Laeufe war,
Teil fuer Teil, wohlgeformt (externe Reviews T16, T18-02).

Deshalb schreibt `cli_fortschreibung` zuletzt ein **Laufmanifest**
(`laufmanifest.json`, `bestand/manifest.py`): Horizont,
Neuzugangs-Stichtag, Kern-Stand, SHA-256 der Config und jeder
geschriebenen Ausgabe — deterministisch wie die Ausgaben selbst.

* Der Abschluss-Produzent verlangt das Manifest: Ohne Manifest wird
  nichts festgeschrieben, `--bis` muss der belegte Horizont sein, und
  jede gelesene Datei muss bytegleich die vom Lauf geschriebene sein.
  Pflicht und fail-fast, nicht "optional mit Vorbehalt" — ein
  festgeschriebener Stand traegt keinen Vorbehalt.
* Gate P-B1 bindet das Manifest auf Wunsch (`--manifest`) und traegt
  die Bindung im Beleg. Optional, weil das Gate auch einzelne Tabellen
  ohne Lauf prueft (ein Basisbestand aus dem Generator).
* Die Pruefengine liest jede Datei genau einmal: gehasht und geparst
  werden dieselben Bytes, und die geparsten Tabellen samt Config gehen
  an den Konsumenten weiter (kein zweites Lesen, T18-03).

## Konsequenzen

* Ausgewiesene Werte aendern sich dort, wo der gamma1-Defekt wirkte
  (Beitraege/Reserven der Erhoehungsscheiben im Bestandsbericht). Das
  ist die Behebung eines Fehlers, keine Modellaenderung. *(Beziffert am
  PLV-Gesamtbestand, 26.08.: Beitragssumme −0,20 % — rund 7.400 EUR am
  Stichtag 2026 —, Deckungskapital +0,003 %; je Beispielscheibe
  Jahresbeitrag −2,0 %.)*
* `bestand_mit_historie` + `zeitscheibe` als Bewertungs-Eingang
  entfallen; Leser des Bestands erhalten den gefuehrten Stamm.
* ADR-009/P-B1: Die Basisstatus-Invarianten wandern semantisch vom Stamm
  auf den Journalanfang. Das ist eine bewusste Nachfuehrung der gerade
  erst gehaerteten Pruefung, kein Aufweichen: Die Pruefmenge wird
  groesser (Stamm-Konsistenz UND Journal-Anfang), nicht kleiner.
* Die Fortschreibungs-CLI schreibt dieselben fuenf Artefakte; `bestand*`
  tragen die neue Semantik. Ein Lauf bleibt byte-deterministisch.
* Seit dem Laufmanifest (Abschnitt 7) ist ein Laufverzeichnis ohne
  `laufmanifest.json` fuer den Abschluss kein Lauf: Aeltere Laeufe
  werden neu fortgeschrieben, nicht nachtraeglich mit einem Manifest
  versehen.

## Bewusst nicht Bestandteil dieser Entscheidung

* Der Migrationszugang selbst und die Korrekturschicht (Grundsatzdokumentation
  Kap. 3-5): Dieses ADR schafft den Ort, an dem beide andocken.
* Eine transaktionale Einzel-Buchungs-API fuer den laufenden Betrieb:
  Die Simulation bucht weiterhin im Lauf; `fuehre_fort` ist der
  gemeinsame Trichter, nicht ein Online-Buchungssystem.

## Nachtrag 2026-10-01: Der Abschluss bewertet monatsgenau

Entscheid des Maintainers: "Bisher dachte ich, dass der Monatsabschluss
die Werte monatlich fortschreibt. Wie wollen wir einen Monatsabschluss
mit angebrochenen Jahreswerten machen?" Gemessen war: Die eine
Bewertungsstrecke (`auswertung.einzelwerte_am`) las Deckungskapital,
Rueckkaufswert und beitragsfreie Reserve aus der Zeile des angebrochenen
Vertragsjahres (`zustand_am`, beim herabgesetzten Vertrag und nach einer
Beitragsfreistellung ebenso — dorthin hatten die Funde N5/N11 der
Pruefrunde T27 die Zweige vereinheitlicht). Der Abschluss zum 1.12. wies
damit den Stand des letzten Jahrestags aus; am Referenzvertrag Monat 95
26.060,73 statt 29.934,67, eine Treppe statt einer Fortschreibung.

**Bewertungsstichtag und Konvention.** Bewertet wird am Stichtag des
Abschlusses (dem Monatsersten nach den gebuchten Vorfaellen des Monats),
nach den vollen Vertragsmonaten seit Versicherungsbeginn. Zwischen zwei
Vertragsjahrestagen mischt die Strecke linear, wie der Kern es kann
(`monatsreserve`, `monatsreserve_beitragsfrei`, `vertrags_monatsreserve`,
`vertrags_monatsreserve_reduziert`; Tarifplan KLV, Abschnitt 6) — fuer
jeden Vertragstyp gleich: gewoehnlich, mit Scheiben, beitragsfrei,
herabgesetzt, teilgekuendigt, mit Korrekturschicht (auch der in die
beitragsfreie Summe ueberfuehrte Schichtwert, den der Kern nur je Jahr
fuehrt, folgt derselben Mischung). Ein Beitragsuebertrag ist darin nicht
enthalten; er ist zurueckgestellt (`dev-docs/offene-punkte.md`,
Fachlich). Die BU bleibt bei der Jahreszeile: Der Kern fuehrt fuer sie
keine unterjaehrige Reserve, und eine Mischung in der Bestandsschicht
waere eine Formel neben dem Kern. Die Konvention wird deshalb je Produkt
gefuehrt (`models.bestand.KONVENTION_JE_PRODUKT`).

**Die Konvention ist ein Vertrag.** Der Abschluss traegt die Spalte
`bewertungskonvention` (`jahreszeile` oder `monatsgenau`). Was ein
gelesener Abschluss ist, sagt EINE Funktion
(`models.bestand.abschluss_konvention`): der Spaltenwert, oder bei
fehlender Spalte "Jahreszeile, vor der Umstellung geschrieben" — das
Fehlen ist eine Aussage ueber den Schreiber, kein Rueckfall. Jeder Leser
einer Abschlussdatei geht ueber `bestand.abschluss.lies_abschluss`.
Die 387 festgeschriebenen Abschluesse der Laufzeit bleiben, wie sie sind
(Abschnitt 6): `pruefe_abschluss` rechnet sie in IHRER Konvention nach —
die Jahreszeile wortgleich wie vor der Umstellung — und meldet sie
deckungsgleich, nicht als Abweichung. Wer Abschluesse verschiedener
Konvention in eine Reihe legt, kennzeichnet den Bruch oder verweigert
benannt (`models.bestand.konventionsbruch`): An der Naht springt das
Deckungskapital ohne Geschaeftsvorfall.

**Warum der Abschluss dem Kern folgt.** Die Abnahmen rechneten schon
monatsgenau (A-M1, Migrationscontrolling); der Betrieb fuehrte als
einziger die Treppe. Ein Zugang, der in der Abnahme bestaetigt war, stand
damit im ersten Abschluss mit einem anderen Wert, und kein Vergleich
konnte sagen, ob das die Konvention oder ein Fehler war.

**Verworfen.**

* Die Treppe beibehalten (Wert des letzten Jahrestags): Sie wies
  unterjaehrig bis zu 11/12 des Jahreszuwachses zu wenig aus und war nie
  eine fachliche Entscheidung, sondern ein Erbe der jaehrlichen
  Fortschreibung.
* Die Zugangsprobe rechnet den Abnahmewert selbst in die Treppe um, der
  Abschluss bleibt: Sie haette die falsche Konvention zementiert und ein
  zweites Rechenwissen neben der Strecke aufgebaut.
* Den Beitragsuebertrag gleich mit einfuehren: Er ist fachlich noch nicht
  erarbeitet (Verdienung, Zahlweise, Ausweis); Fortschreibung und Tests
  laufen ohne ihn, das Thema steht auf der Liste der offenen Punkte.

**Folgen.** Ab dem ersten Abschluss nach der Umstellung stehen die Werte
unterjaehriger Vertraege hoeher (die Reserve waechst in den meisten
Jahren); am Jahrestag aendert sich nichts. Die Migrationsabnahme A-M4
weist zusaetzlich den Fuehrungswert aus — was dieser Abschluss fuer jeden
Vertrag des Zugangs fuehren wird (`models.fuehrungswert`) —, und die
Zugangsprobe haelt die Abschlusszeilen des Betriebs dagegen (ADR-022,
Nachtrag 2026-10-01). Ereignisse wirken weiter am Jahrestag
(`ereignisse`, `ledger_bindung`, `migrationszugang` rechnen bewusst auf
dem Jahresgitter); umgestellt ist die Bewertung, nicht das
Ereignisgitter.

**Nebentabellen ohne Vorgabewert.** Herabsetzung und Teilkuendigung
hinterlassen weder im Stamm noch in der Historie eine Spur, nur in
`reduktionen`. `schreibe_abschluss` und `pruefe_abschluss` verlangen deshalb
jede Nebentabelle (Scheiben, Merkmale, Schichten, Verankerung, Reduktionen)
ohne Vorgabewert; `None` ist die Aussage "dieser Lauf hat keine". Anlass war
ein Befund aus dem Raten-Block (2026-10-01): Die In-Prozess-Abschlusstests
gaben nur die Scheiben mit und bewerteten herabgesetzte und teilgekuendigte
Vertraege ungekuerzt, waehrend die Produzenten (`cli_abschluss`,
`tageslauf`) die Tabelle mitgaben. Eine Ratsche haelt jeden Aufruf der
Bewertungsstrecke in `src` auf alle fuenf Tabellen.
