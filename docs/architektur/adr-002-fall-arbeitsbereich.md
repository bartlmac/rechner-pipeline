# ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum

**Status:** angenommen am 2026-08-14 (Maintainer), umgesetzt in
`rechner_pipeline.fall` und `assurance --fall`.

> **Teilweise abgelöst durch [ADR-006](adr-006-portierung-ausser-betrieb.md)**
> (2026-08-17): Den Befehl `assurance --fall` gibt es nicht mehr. Der
> Fall-Arbeitsbereich und seine Regeln gelten unverändert; die Gates
> operieren einzeln auf dem Fall (`--fall <pfad>`). Auch die „Bekannte
> Einschränkung“ unten (G5/G7) ist damit gegenstandslos: Diese Gates gibt
> es nicht mehr.

## Kontext

Bisher formulierten README und AGENTS.md den Einstieg als
`--input examples/...` plus drei lose Verzeichnis-Flags. Das verwechselt
Demo-Material mit dem Eingangskanal des Systems: einem Kunden lässt
sich nicht erklären, dass `examples/` „das Input-Verzeichnis“ sei, und
ob eine Quelle synthetisch oder echt ist, ist für den Code irrelevant;
relevant ist nur, was in ein öffentliches Repo darf. Es fehlte der Ort,
an dem ein Migrationsfall lebt.

## Entscheidung

Ein **Fall** (ein Migrationsprojekt) lebt in einem eigenen
Arbeitsbereich mit zwei strikt getrennten Zonen:

```
<arbeitsbereich>/            im echten Einsatz außerhalb des Repos;
  fall.json                  faelle/ im Repo ist nur der gitignorierte
  eingang.json               Default für lokale Demo-Fälle
  eingang/                   registrierte Quellen, nicht regenerierbar
  entscheide/                P9-Snapshots menschlicher Gates, nicht
                             regenerierbar (wie der Eingang)
  abgeleitet/                alles Regenerierbare
    info_from_excel/  generated/  diagnostics/  berichte/
    abox/  spez/  fachspez/
```

Einschränkung in v0.1: ``abgeleitet/abox/abox.json`` trägt nach dem
Gate A-Q1 auch die menschlichen Diskrepanz-Entscheidungen und ist damit
nicht mehr frei regenerierbar; bis die Entscheidungs-Wiederanwendung
aus den P9-Snapshots gebaut ist, gilt: abox.json nicht löschen.

- **Eingang:** Quellen werden registriert (`fall registrieren`):
  unter ihrem Namen schreibgeschützt abgelegt, mit SHA-256, Herkunft
  und Zeitpunkt im Register `eingang.json` (der Hash identifiziert den
  Inhalt, die Ablage bleibt namensbasiert; Eingangsnamen sind flach und
  ohne Pfadanteil). Hier beginnt die
  Provenienzkette (P1). Gleicher Name mit anderem Inhalt ist ein
  harter Konflikt mit beiden Hashes in der Meldung, kein stiller
  Overwrite (P2). Kein Werkzeug dieses Repos räumt den Eingang auf.
- **Abgeleitet:** darf jederzeit gelöscht und aus Eingang + System neu
  erzeugt werden.
- **Die Pipeline operiert auf dem Fall:** `assurance --fall <pfad>
  --quelle <name>` prüft den Eingang vor dem Lauf gegen das Register
  (kein Lauf auf unklarem Eingang) und legt alle Ausgaben unter
  `abgeleitet/` ab. Explizite Verzeichnis-Flags bleiben verfügbar und
  übersteuern (Entwickler-Kurzweg).
- **`examples/` ist Demo-Material:** öffentliche Beispielquellen, aus
  denen sich ein Demo-Fall instanziieren lässt, plus Test-Fixtures.
  Kein Eingangskanal. *(Nachtrag 2026-08-19: `examples/` wurde
  aufgelöst; Bestands-Konfigurationen nach `configs/`,
  Extraktions-Fixtures nach `tests/fixtures/`, historische
  Quelldokumente aus dem Repo entfernt. Neu ist `lieferungen/`:
  versioniertes Frachtgut der Showcase-Migrationen, damit jeder Clone
  eine Migration selbst durchführen kann. Die Kein-Eingangskanal-Regel
  gilt unverändert: kein Code liest `lieferungen/` implizit, in einen
  Fall gelangt eine Lieferung nur über die ausdrückliche
  Registrierung.)*

## Konsequenzen

- Der dokumentierte Einstieg (README, AGENTS.md) ist der Fall-Weg;
  einem Kunden zeigt man `fall anlegen / registrieren / assurance
  --fall`, nicht ein Repo-Verzeichnis.
- Echte Fälle liegen außerhalb des Repos (Pfad frei wählbar) mit
  eigener Versionierung und eigenem Zugriffsschutz; ins öffentliche
  Repo kommt nie Kundenmaterial.
- Der Eingang-Schutz ist Architekturregel statt Vorsicht: registrierte
  Dateien sind schreibgeschützt, Integritätsverletzungen blocken den
  Lauf, Aufräum-Werkzeuge fassen `eingang/` nie an.
- Der Architektur-Entwurf (Ontologie-Pipeline) baut auf dem Fall auf:
  A-Box, Spezifikation und Gate-Snapshots eines Falls liegen in dessen
  Arbeitsbereich; das Layout unter `abgeleitet/` wächst dort weiter.
- `runs/` bleibt für lose Entwickler-Läufe außerhalb eines Falls
  (regenerierbar, aufräumbar).

## Bekannte Einschränkung

Die Gate-Kette verlangt heute den InputBundle-Ordner unterhalb von
`--repo-root` (G5/G7 brechen sonst ab). Ein Fall außerhalb der
Repo-Wurzel wird deshalb vor dem Lauf mit einer Anweisung abgewiesen
statt mitten im Lauf zu scheitern. Das steht der Zielaussage „echte
Fälle liegen außerhalb des Repos“ entgegen und wird im
Pipeline-Entwurf aufgelöst (die Repo-Wurzel ist dort der Ort des
Systems, nicht der Ort der Daten).

## Verworfene Alternative

Nur eine Verzeichnis-Konvention ohne Werkzeug: die Struktur existierte
dann, aber Registrierung, Hashes, Schreibschutz und die
Vor-Lauf-Prüfung blieben Handarbeit und Prosa; nichts machte die
Regeln wahr.

## Nachtrag 2026-09-30: Auskünfte der Quelle sind registrierte Dateien

Entscheid des Maintainers. Eine Auskunft der abgebenden Gesellschaft (der
fortgeführte Beitragsanteil einer Alt-Herabsetzung, dessen
Beitragsgleichung entfällt) ist Eingang wie jede Lieferung: Sie wird
registriert (Register, SHA-256, Schreibschutz) und erreicht die Kommandos nur
als `--red-anteile-datei <registrierter Name>`. Ein Kommandozeilenparameter
je Police (`--red-anteil POLNR=ANTEIL`) war der Weg am Register vorbei: Die
menschlichen Gates hashen den Eingang, nicht den Aufruf, und der Beleg nannte
die Werte als getippte Liste ohne Herkunft.

Vertragsänderung (Breaking Change), für alle fünf Kommandos, die
Herabsetzungsanteile verarbeiten (`bestand_uebernehmen`,
`verankerung_belegen`, `aktuartest_lauf`, `migrationssuite_lauf`,
`fuehrungsprobe`):

* `--red-anteil` ist entfernt. `verankerung_belegen` kannte bisher nur ihn
  und kennt jetzt `--red-anteile-datei` mit derselben Lesart wie die
  übrigen (`migrationssuite_lauf.lies_auskuenfte`).
* Format: `POLNR;GEVO;DATUM;ANTEIL`, optional `BEZUG` (Freitext:
  Auskunftsschreiben oder Arbeits-Lesart). Rückwärtskompatibel: Eine Datei
  ohne die Spalte bleibt lesbar.
* Provenienz: Der Schichtbeleg führt unter `provenienz.parameter` statt der
  Liste `red_anteile` den Block `red_anteile_datei` (`name`, `sha256`,
  `bezug` je Police); Übernahmebeleg und Führungsprobe ebenso. Der
  Konsument (`aktuartest_lauf --schicht`) lehnt einen Beleg mit `red_anteile`
  ab und rechnet `red_anteile_datei` gegen die Eingaben des Belegs nach.
* Fail-fast: nicht registrierte Datei (mit dem Ausweg), fehlende Spalte,
  keine RED-Zeile, nichtnumerischer Anteil, widersprüchliche Zeilen, und
  die Datei ohne Vorgeschichte (die Anteile wirkten sonst nicht) werden
  verweigert.

Nachbesserung nach einer Prüfrunde:

* Wertebereich: Ein Anteil ist endlich und liegt echt zwischen 0 und 1
  (`nan`, `inf`, 0, 1, Prozentwerte werden mit Police, Datum, Wert und
  Ausweg verweigert).
* Zeilen ohne Wirkung: Jede RED-Zeile entspricht einem RED-Ereignis der
  Vorgeschichte des Laufs (Police; mit DATUM zusätzlich das Datum im
  selben Wortlaut); eine leere POLNR trägt nichts. Sonst stünde die Zeile
  mit Hash und Bezug im Beleg, ohne je gewirkt zu haben.
* Welt-Gleichheit: Die Schicht eines Schichtbelegs ist auf der Anfangslage
  seiner Auskunft verankert. Ein Lauf mit `--schicht` (`aktuartest_lauf`,
  `migrationssuite_lauf`, `fuehrungsprobe`) vergleicht den SHA-256 der
  Auskunft des Belegs mit dem der Auskunft, die er selbst gelesen hat;
  `keine Auskunft` gilt nur auf beiden Seiten als gleich. Ein Beleg, dessen
  Eingaben eine Auskunft nennen, dessen Parameterblock sie aber nicht führt,
  ist ein Formfehler.
* `aktuartest_lauf` und `migrationssuite_lauf` führen die Auskunft im
  Ergebnis als `red_anteile_datei` (`null` ohne Auskunft). Der Abnahmebericht
  verlangt das Feld in der Suite, rechnet es gegen die Eingaben der Suite nach
  und hält Suite und Führungsprobe auf derselben Auskunft. Das ist eine
  verschärfte Akzeptanzmenge (ADR-012): `GATE_VERSION` des Abnahmeberichts
  `6.0.0`.

`tests/test_auskunft_registriert_klasse.py` hält die Klasse geschlossen.
Er prüft an der Stelle, an der die Anteile wirken: Jeder Anteil, der in
`anfangszustaende_je_police` oder `_serienzustand` geht, stammt aus
`lies_auskuenfte`; jedes Modul mit einem solchen Aufruf kennt
`--red-anteile-datei`; kein Argument unter `gates/` liefert je Police einen
Anteil. Dazu zählt je Kommando ein Test die Aufrufe.

## Nachtrag 2026-10-01: Alt-Absetzung nach dem Beitragsende

Entscheid des Maintainers: Der Migrationszugang integriert gelieferte
Verträge, die im ausfinanzierten Nachlauf (`t <= Jahr < n`) abgesetzt
wurden, in jeder Generation. Beitragsherabsetzung und Teilkündigung sind
zwei Geschäftsvorfälle (ADR-023); eine gelieferte Absetzung nach t war eine
Teilkündigung, davor sagt es das Verfahren der Quelle (Annahme A2, Tarifplan
KLV, Abschnitt 7.2; `models.bestand.alt_absetzung_ist_teilkuendigung`).
Geliefert ist `ERLSUMME = f x Ursprungssumme`, eine Gleichung mit zwei
Unbekannten, und nach t gibt es keine Beitragsgleichung.

* Einzelfall: Der Vertrag ist der zustandslose Vertrag mit der gelieferten
  Summe und wird ohne Anfangszustand übernommen; der Anteil wirkt nicht auf
  den Wert, eine Auskunft ist dafür nicht nötig, und der Vertrag ist nicht
  „gedeckt“ (die Auskunft bestimmt an ihm nichts).
* Serie (Erhöhungen vor t, Absetzung danach): Der Anteil verteilt die
  gelieferte Summe auf Grund und Erhöhungen und kommt aus derselben
  registrierten Auskunft wie oben (`--red-anteile-datei`); ohne sie
  verweigert die Übernahme und nennt diesen Ausweg.
* `migrationszugang.leite_ursprungssumme_ab` bestimmt mit der Auskunft die
  Ursprungssumme als `ERLSUMME / f`; `leite_absetzung_ab` und
  `kalibriere_absetzung_aus_dk` verweigern unter der Teilkündigung mit dem
  Ausweg (`auskunft_meldung`).

**Nicht ableitbar heißt verweigert, nicht zustandslos.**
Bis dahin wurde ein Vertrag, dessen Anfangszustand die Ableitung nicht
bestimmen konnte, mit einer Warnung und einem Eintrag `ohne_anfangszustand`
als Grundvertrag mit der gelieferten Summe übernommen, und die ganze Kette
lief mit Exit 0. Jetzt verweigern Übernahme, Verankerung, aktuarieller Test
und Migrationssuite (`migrationssuite_lauf.verweigere_unbestimmte`; die
Führungsprobe befundet einen solchen Vertrag) und nennen je Police den
Ausweg: den Anteil als registrierte Auskunft, oder den ganzen Fall mit
`--anfangszustand grundvertrag` als nicht freigeschaltet. Jede Ursache, aus
der die Ableitung einen `MigrationszugangFehler` meldet, führt so zur
Verweigerung.

*Was ist Deckung?* Gedeckt ist ein Anfangszustand nur durch das, was seine
**Struktur** bestimmt: die registrierte Auskunft der Quelle je Ereignis (mit
`BEZUG` auch eine dokumentierte Arbeits-Lesart des Aktuars). „Die Werte an
den Bewertungspunkten stimmen“ ist keine Deckung: Nach dem Beitragsende sind
A-M1, A-M2 und die Suite gegen die Zerlegung in Grund und Erhöhungen blind:
jede Zerlegung mit derselben Summe erzeugt dieselben Werte bis auf die
Centrundung, und eine spätere Teilkündigung zahlte trotzdem falsch aus.
Ein gedeckter Vertrag ist deshalb **Pflichtziehung** von A-M1, A-M2, A-M3
(mit Geschäftsvorfall im Prüfzeitraum) und der Migrationssuite: Der
Übernahmebeleg nennt je Police, wodurch sie gedeckt ist (`gedeckt`: Datei,
SHA-256, Bezug), die Belege führen dieselbe Menge (`pflichtschicht`,
`pflichtschicht_fehlt`), die Führungsprobe führt sie (`gedeckt`,
`SCHEMA_VERSION` 4), und der Abnahmebericht hält sie gleich
(`GATE_VERSION` 7.0.0).

**Grenzen, benannt.** Die Grenzen eines gelieferten Vorgangs (`0 < Jahr <
n`, Datum nicht nach dem Stichtag, Jahrestag) prüft eine Stelle vor jeder
Verzweigung (`vorgeschichte_grenzfehler`). Eine
registrierte Auskunft, die *falsch* ist, bestimmt eine falsche Zerlegung mit
richtiger Summe; nach dem Beitragsende sieht das keine Wertprüfung. Die
Verantwortung liegt bei dem, der die Auskunft registriert; eine
Strukturprüfung, die es fangen könnte, bräuchte einen Wert, der von der
Zerlegung abhängt (etwa den Rückkaufswert je Baustein der Quelle); die
Lieferung trägt keinen.

Kein neuer Eingang: Die Auskunft ist die registrierte Datei des Nachtrags vom
2026-09-30. Der Test `tests/test_alt_herabsetzung_nachlauf_e2e.py` fährt
einen solchen Vertrag durch die ganze Kette, je einmal für eine Generation
mit `prospektiv`, `mit_abzug` und `teilkuendigung`, und die Angriffe des
Prüfers als Verweigerungen.

## Nachtrag 2026-10-01: der Fall und sein Auftrag (ADR-026)

Ein Fall entsteht weiterhin, indem jemand ihn anlegt und die Lieferung
registriert; geführt wird er erst mit dem gezeichneten **Fallauftrag**
(`A-M6`, Vorstand). Der Auftrag bindet genau die Bytes, die dieses ADR zur
Provenienzkette macht: `eingang.json` mit je Quelle Name und SHA-256, dazu
`fall.json` (Name, Scope). Eine nachgereichte Quelle ändert das Register und
entzieht dem Auftrag die Geltung; der Vorstand beauftragt neu. Die Zone
bleibt, was sie war: Der Auftrag steht als Snapshot unter `entscheide/`, seine
Vorlage unter `abgeleitet/auftrag/`; der Eingang wird dadurch nicht
berührt. Ein Fall, der scheitert, endet mit dem **Fallabbruch** (`A-M5`);
danach ist in ihm nichts mehr zeichenbar, abgelegt wird er wie jeder Fall.
