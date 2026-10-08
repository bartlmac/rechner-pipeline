# Die Fallseite: eine Seite, von A bis Z

Stand 2026-09-22. Dieses Papier legt fest, wie eine Bestandsübernahme auf
dem Auftritt erzählt wird, bevor wieder gebaut wird. Es entsteht, weil
vier Anläufe ohne festgelegtes Ziel vier Mal dieselbe Rüge erzeugt haben:
Wiederholung, Überschneidung, Sprünge.

**Gebaut.** Die Seite steht: `migrationen/baldrian/` ist eine Seite mit
dreizehn Stationen, je Station Prüfung, Geschehen, Zahlen und Belege.
Was dafür an Erzeugern geändert wurde, steht unter „Was der Umbau
gekostet hat“. Was noch umgestellt werden muss und **warum es nicht in
dieser Runde geht**, steht unten — es betrifft ausnahmslos `src/` und
die Fall-Artefakte, und beides gehört nicht dieser Sitzung.

## Was schiefgegangen ist

Der Fall wurde an zwei Stellen erzählt — „Der Weg der Übernahme“ als
Erzählung, der „Fallbericht“ als Nachschlagewerk — und die Belege lagen
an einer dritten. Jede Umsortierung hat die Dopplung verschoben, nicht
beseitigt. Zwischenzeitlich waren es dreizehn Seiten für einen Fall.

Die Ursache ist keine Reihenfolge, sondern ein fehlender Schnitt: Es war
nie festgelegt, **was ein Leser an einer Station wissen will**. Solange
das offen ist, landet alles überall.

## Die Regel

**Eine Station, eine Stelle.** Wer bei Station 5 steht, findet dort: was
das Gate prüft, was in diesem Fall geschah, die Zahlen dazu und die
Belege dazu. Er muss nirgendwo hinspringen, um die Station zu verstehen.

Daraus folgt alles Weitere:

* **Eine Seite je Fall.** Kein Weg-Dokument neben einem Bericht.
* **Artefakte stehen bei ihrer Station**, nicht gesammelt am Fuß. Unten
  steht nur ein Verzeichnis für den, der ein bestimmtes Artefakt sucht.
* **Was kein Leser an einer Station braucht, steht nicht auf der Seite.**
  Es ist ein Dokument und wird als solches verlinkt.

## Der Aufbau

    1  Worum es geht        Wer gibt ab, was, zu welchem Stichtag; wie es ausging
    2  Woran wir uns messen Der Maßstab in drei Sätzen, Rest auf massstab.html
    3  Station 1 bis 13     je Station: Prüfung · Geschehen · Zahlen · Belege
    4  Was herauskam        Ergebnis, Toleranzen, Prüflücken
    5  Was sich am System änderte   Der Umbau, mit Kennzahlen
    6  Grenzen dieses Laufs
    7  Verzeichnis der Artefakte

Teil 3 ist die Seite; 1, 2 und 4 bis 7 sind Rahmen.

## Was an welche Station gehört

| Station | Gate | Zahlen | Belege an dieser Stelle |
|---:|---|---|---|
| 1 Lieferung und Registrierung | — | gelieferte Dateien, davon nachgereicht | Eingangsregister, Ansichten der Lieferung, gelieferter Bestand |
| 2 Quellen lesen | P-Q1 | Anläufe, Prüfstoff je Quelle | Ledger P-Q1, Quellfragmente |
| 3 Quellen zusammenführen | P-Q2 | Anläufe, Diskrepanzen | Ledger P-Q2, Faktenbasis (A-Box) |
| 4 Faktenbasis prüfen | P-Q3 | belegte Pflichtfelder | Ledger P-Q3, Abdeckungsbericht |
| 5 Quellen abnehmen | A-Q1 | entschiedene Wertkonflikte | Entscheid-Snapshot, Konflikttabelle |
| 6 Bestand übersetzen | — | Zeilen hinein/heraus, nicht übernommene Spalten | Übersetzungs-Spezifikation und -Ergebnis |
| 7 Rechenkern gegen den Quellrechner | P-K1 | verglichene Werte, Abweichungen | Golden-Master-Beleg je Generation, Umbaubericht |
| 8 Bestand prüfen | P-B1 | geprüfte Verträge, Verankerung | Ledger P-B1 |
| 9 Stichtag prüfen | A-M1 | bestanden/geprüft, größte Abweichung | Prüfbericht A-M1, Entscheid-Snapshot |
| 10 Verlauf prüfen | A-M2 | dito | Prüfbericht A-M2, Entscheid-Snapshot |
| 11 Geschäftsvorfälle prüfen | A-M3 | dito, Vollerhebung | Prüfbericht A-M3, Entscheid-Snapshot |
| 12 Migrationscontrolling | A-M4 | Verträge, Einzelprüfungen, Prüflücken | Migrationsabnahme, Entscheid-Snapshot |
| 13 Zugang in die Bücher | — | eingetretene Verträge, Bestand danach | Geführter Bestand nach der Übernahme |

## Was umgestellt werden muss, damit es fachlich sauber liegt

Die folgenden Punkte sind der Grund, warum sich das heute nicht sauber
bauen lässt. Sie sind nach Aufwand geordnet, nicht nach Wichtigkeit.

### 1. Die Bestandsberichte enden an verschiedenen Tagen

Eigener Bestand bis 2046, gelieferter bis 2026, geführter bis 2027 —
jeder mit eigener Projektion. Ein Vergleich dreier Bilder mit drei
Horizonten ist kein Vergleich. **Alle drei auf den Übernahmestichtag,
ohne Projektion** (`--berichtsstichtag`), und der gelieferte Bestand
ohne Verlaufsteile (`--ohne-verlauf`), weil er keine Historie hat. Die
Schalter sind gebaut und in den Skills dokumentiert; **der Fall muss
dafür neu laufen**, und weil `abnahmebericht.gate.json` die Prüfsummen
zweier dieser Berichte führt und A-M4 dieses Gate-JSON bindet, **muss
A-M4 danach neu gezeichnet werden**.

### 2. Der Umbau hängt an keiner Station

Wie weit ein Lauf das Zielsystem verändert, wird gemessen und
ausgewiesen — aber kein Gate hält ihn an, keine Zeichnung bindet ihn.
Auf der Seite steht er deshalb heute als Rahmenkapitel (Teil 5). Fachlich
gehört er an Station 7 (Rechenkern) oder als eigenes Gate in die Kette.
**Das ist eine Architekturentscheidung, keine Darstellungsfrage** — sie
gehört in einen ADR, nicht in eine Seitenumstellung.

### 3. Die Prüfberichte tragen ihren Namen nicht

`aktuartest.html` ist A-M1, `aktuartest-A-M2.html` ist A-M2,
`migrationsabnahme.html` ist A-M4. Wer an Station 9 einen Beleg sucht,
sucht „A-M1“. **Umbenennen auf `abnahme-A-M1.html` … `abnahme-A-M4.html`**
im Erzeuger; die alten Namen stehen in `abnahmebericht.gate.json` und
brauchen denselben Neulauf wie Punkt 1.

### 4. Die Gate-Ledger sind nicht je Station auffindbar

Sie liegen als `abgeleitet/diagnostics/<kommando>.gate.json` — benannt
nach dem Kommando, nicht nach dem Gate. Die Fallseite kann sie deshalb
nur über die Kette auflösen. **Im Ledger selbst steht die Gate-Kennung;
der Erzeuger der Seite nimmt sie von dort** — kein Neulauf nötig, nur
eine Auflösung im Werkzeug.

### 5. Die Lieferungsansichten haben kein Register je Datei

`artefakte/lieferung/` enthält Ansichten, aber die Zuordnung zu den
registrierten Quellen steht nur in `eingang.json`. Für Station 1 braucht
die Seite beides nebeneinander. **`eingang.json` um den Pfad der Ansicht
ergänzen** — Erzeuger-Änderung, kein Neulauf der Gates.

### 6. Der Fall heißt auf der Seite wie sein Verzeichnis

`baldrian-klv-tg2015-lauf2` ist eine Kennung. Auf der Seite gehört der
Name der abgebenden Gesellschaft; die Kennung ins Verzeichnis der
Artefakte. **`fall.json` um `abgebende_gesellschaft` ergänzen**, statt
den Namen aus dem Verzeichnisnamen zu schneiden.

### 7. Sichtbarer Text trägt an einigen Stellen die Repo-Umschrift

Die Seite schreibt Deutsch mit Umlauten; einzelne Texte kommen aber aus
`src/` oder aus den Fall-Artefakten und tragen dort die ASCII-Umschrift.
Gemessen auf der gebauten Seite (Wörter mit ae/oe/ue/ss, zu denen das
Systemwörterbuch ein Gegenstück mit Umlaut kennt), bleiben nach der
Bereinigung in `werkzeuge/` genau zwei Quellen:

| Quelle | Stelle | Text |
|---|---|---|
| `src/rechner_pipeline/gates/register.py` | A-M2 `gegenstand_satz` | „die Deckungsrückstellung **über** die Laufzeit“ |
| `src/rechner_pipeline/gates/register.py` | A-M4 `gegenstand_satz` | „bindet die Pflichtbelege … und **prüft** sie erneut“ |
| Fall-Artefakte (`fall.json`) | Beschreibung | „(**Vorführfall** Vier-Rollen-Regie)“ |
| `src/rechner_pipeline/betrieb/seite.py` | Lücken-Wirkung | „nicht auf ein Container-Image **rückführbar**“ |
| Fall-Artefakte (Umbau) | Begründung | „**Fähigkeiten planmäßig**“, „**nachträglich** adversarial geprüft“ |

Beide Register-Stellen stehen mitten in Sätzen, die sonst Umlaute
schreiben („Deckungsrückstellung über“) — das sind Tippfehler, keine
Umschriftregel. Die Fall-Texte entstehen im Lauf und ändern sich mit
ihm. **Beides gehört nicht in diese Sitzung**: `src/` gehört der
dev-Sitzung, die Fall-Artefakte entstehen beim Neulauf aus Punkt 1.

Berichtigung 2026-09-22: Kreuzprobe („Abgänge gegen beendende
Vorfälle“) und die drei Abgrenzungs-Aussagen stammten nicht aus den
Fall-Artefakten, sondern aus `werkzeuge/falldaten.py` — also aus dieser
Sitzung. Dort bereinigt. Die Liste für dev steht jetzt in
`vorzeige-zielbild-artefakte.md`, Punkt B6.

Anker, Dateinamen und Bezeichner (`#quellen-zusammenfuehren`,
`massstab.html`, `fuss-fiktion`) bleiben in Umschrift — sie sind keine
Lesetexte.

## Was der Umbau gekostet hat

Nur `werkzeuge/` und `plv/seite/`; kein `src/`, kein Neulauf, keine
umbenannten Artefakte.

* `werkzeuge/vorzeigeseite.py` — `_stationen()` setzt je Station
  Überschrift, Gate-Kasten, Geschehen, Zahlenblock und Belege; die
  Zahlenblöcke tragen keine eigene Überschrift und keine eigenen Belege
  mehr. Der Kopf führt „Der Weg im Überblick“ mit dreizehn Sprungzielen.
* `werkzeuge/unternehmensseite.py` — `_journey` (199 Zeilen) entfällt;
  die Stationserzählung ist zur Fallseite **gewandert**, nicht kopiert
  worden. `{{html:journey}}` gibt es nicht mehr.
* `werkzeuge/darstellung.py` — `STATION_ABSCHNITT` gibt jeder der
  dreizehn Stationen einen eigenen Anker (vier teilten sich einen);
  `datum()`, `GATE_TITEL`, `ART`, `GEGENSTAND_TEXT` und
  `DECKUNG_ZUSTAND` wohnen hier, weil beide Erzeuger sie brauchen.
* `plv/seite/migrationen/baldrian-weg.md` → `ki.md`: die Seite
  trägt die Kachel „Künstliche Intelligenz“ und ist jetzt fallfrei.
* `stil.css` — `ol.journey` und `.befunde` entfallen, `p.gate` kommt.

## Was bleibt, was geht

**Bleibt:** `massstab.html` (der Maßstab, fallunabhängig), `migrationen/`
(das Verfahren, fallunabhängig), die Berichte des Aktuariats
(Abschluss- und Veränderungsbericht) als Dokumente, die Artefakte.

**Gegangen:** `baldrian-weg.html`. Die Stationen sind auf die Fallseite
gezogen; der KI-Inhalt (Rollen, was ein Agent darf, die Gate-Kennung) ist
fallunabhängig und steht jetzt unter `migrationen/ki.html`.

**Gegangen ebenfalls:** die Seiten `lieferung`, `widerspruch`,
`datenuebersetzung`, `pruefungen`, `bestand`, `ergebnis`, `umbau`,
`anlaeufe`, `grenzen`, `belege` — ihr Inhalt sind die Kapitel der einen
Seite. `entscheide.html` bleibt als einziges Nachschlagewerk bestehen:
eine Tabelle mit neun Spalten je Snapshot beherrscht sonst die Seite.
