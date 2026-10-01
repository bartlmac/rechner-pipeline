# ADR-002: Fall-Arbeitsbereich — das Repo ist das System, nicht der Datenraum

Status: akzeptiert (Maintainer, 2026-08-14). Umgesetzt:
`rechner_pipeline.fall` + `assurance --fall`.

> **Teilweise abgeloest durch [ADR-006](adr-006-portierung-ausser-betrieb.md)**
> (2026-08-17): Den Befehl `assurance --fall` gibt es nicht mehr. Der
> Fall-Arbeitsbereich und seine Regeln gelten unveraendert; die Gates
> operieren einzeln auf dem Fall (`--fall <pfad>`).

## Kontext

Bisher formulierten README und AGENTS.md den Einstieg als
`--input examples/...` plus drei lose Verzeichnis-Flags. Das verwechselt
Demo-Material mit dem Eingangskanal des Systems: einem Kunden laesst
sich nicht erklaeren, dass `examples/` "das Input-Verzeichnis" sei, und
ob eine Quelle synthetisch oder echt ist, ist fuer den Code irrelevant —
relevant ist nur, was in ein oeffentliches Repo darf. Es fehlte der Ort,
an dem ein Migrationsfall lebt.

## Entscheidung

Ein **Fall** (ein Migrationsprojekt) lebt in einem eigenen
Arbeitsbereich mit zwei strikt getrennten Zonen:

```
<arbeitsbereich>/            im echten Einsatz AUSSERHALB des Repos;
  fall.json                  faelle/ im Repo ist nur der gitignorierte
  eingang.json               Default fuer lokale Demo-Faelle
  eingang/                   registrierte Quellen — NICHT regenerierbar
  entscheide/                P9-Snapshots menschlicher Gates — NICHT
                             regenerierbar (wie der Eingang)
  abgeleitet/                alles Regenerierbare
    info_from_excel/  generated/  diagnostics/  berichte/
    abox/  spez/  fachspez/
```

Einschraenkung in v0.1: ``abgeleitet/abox/abox.json`` traegt nach dem
Gate A-Q1 auch die menschlichen Diskrepanz-Entscheidungen und ist damit
nicht mehr frei regenerierbar — bis die Entscheidungs-Wiederanwendung
aus den P9-Snapshots gebaut ist, gilt: abox.json nicht loeschen.

- **Eingang:** Quellen werden registriert (`fall registrieren`) —
  unter ihrem Namen schreibgeschuetzt abgelegt, mit SHA-256, Herkunft
  und Zeitpunkt im Register `eingang.json` (der Hash identifiziert den
  Inhalt, die Ablage bleibt namensbasiert; Eingangsnamen sind flach und
  ohne Pfadanteil). Hier beginnt die
  Provenance-Kette (P1). Gleicher Name mit anderem Inhalt ist ein
  harter Konflikt mit beiden Hashes in der Meldung — kein stiller
  Overwrite (P2). Kein Werkzeug dieses Repos raeumt den Eingang auf.
- **Abgeleitet:** darf jederzeit geloescht und aus Eingang + System neu
  erzeugt werden.
- **Die Pipeline operiert auf dem Fall:** `assurance --fall <pfad>
  --quelle <name>` prueft den Eingang VOR dem Lauf gegen das Register
  (kein Lauf auf unklarem Eingang) und legt alle Ausgaben unter
  `abgeleitet/` ab. Explizite Verzeichnis-Flags bleiben verfuegbar und
  uebersteuern (Entwickler-Kurzweg).
- **`examples/` ist Demo-Material:** oeffentliche Beispielquellen, aus
  denen sich ein Demo-Fall instanziieren laesst, plus Test-Fixtures.
  Kein Eingangskanal. *(Nachtrag 2026-08-19: `examples/` wurde
  aufgeloest — Bestands-Konfigurationen nach `configs/`,
  Extraktions-Fixtures nach `tests/fixtures/`, historische
  Quelldokumente aus dem Repo entfernt. Neu ist `lieferungen/`:
  versioniertes Frachtgut der Showcase-Migrationen, damit jeder Clone
  eine Migration selbst durchfuehren kann. Die Kein-Eingangskanal-Regel
  gilt unveraendert — kein Code liest `lieferungen/` implizit, in einen
  Fall gelangt eine Lieferung nur ueber die ausdrueckliche
  Registrierung.)*

## Konsequenzen

- Der dokumentierte Einstieg (README, AGENTS.md) ist der Fall-Weg;
  einem Kunden zeigt man `fall anlegen / registrieren / assurance
  --fall`, nicht ein Repo-Verzeichnis.
- Echte Faelle liegen ausserhalb des Repos (Pfad frei waehlbar) mit
  eigener Versionierung und eigenem Zugriffsschutz; ins oeffentliche
  Repo kommt nie Kundenmaterial.
- Der Eingang-Schutz ist Architekturregel statt Vorsicht: registrierte
  Dateien sind schreibgeschuetzt, Integritaetsverletzungen blocken den
  Lauf, Aufraeum-Werkzeuge fassen `eingang/` nie an.
- Der Architektur-Entwurf (Ontologie-Pipeline) baut auf dem Fall auf:
  A-Box, Spezifikation und Gate-Snapshots eines Falls liegen in dessen
  Arbeitsbereich; das Layout unter `abgeleitet/` waechst dort weiter.
- `runs/` bleibt fuer lose Entwickler-Laeufe ausserhalb eines Falls
  (regenerierbar, aufraeumbar).

## Bekannte Einschraenkung

Die Gate-Kette verlangt heute den InputBundle-Ordner unterhalb von
`--repo-root` (G5/G7 brechen sonst ab). Ein Fall ausserhalb der
Repo-Wurzel wird deshalb vor dem Lauf mit einer Anweisung abgewiesen
statt mitten im Lauf zu scheitern. Das steht der Zielaussage "echte
Faelle liegen ausserhalb des Repos" entgegen und wird im
Pipeline-Entwurf aufgeloest (die Repo-Wurzel ist dort der Ort des
Systems, nicht der Ort der Daten).

## Verworfene Alternative

Nur eine Verzeichnis-Konvention ohne Werkzeug: die Struktur existierte
dann, aber Registrierung, Hashes, Schreibschutz und die
Vor-Lauf-Pruefung blieben Handarbeit und Prosa — nichts machte die
Regeln wahr.

## Nachtrag 2026-09-30: Auskuenfte der Quelle sind registrierte Dateien

Entscheid des Maintainers. Eine Auskunft der abgebenden Gesellschaft — der
fortgefuehrte Beitragsanteil einer Alt-Herabsetzung, dessen
Beitragsgleichung entfaellt — ist Eingang wie jede Lieferung: Sie wird
registriert (Register, SHA-256, Schreibschutz) und erreicht die Kommandos nur
als `--red-anteile-datei <registrierter Name>`. Ein Kommandozeilenparameter
je Police (`--red-anteil POLNR=ANTEIL`) war der Weg am Register vorbei: Die
menschlichen Gates hashen den Eingang, nicht den Aufruf, und der Beleg nannte
die Werte als getippte Liste ohne Herkunft.

Vertragsaenderung (Breaking Change), fuer alle fuenf Kommandos, die
Herabsetzungsanteile verarbeiten (`bestand_uebernehmen`,
`verankerung_belegen`, `aktuartest_lauf`, `migrationssuite_lauf`,
`fuehrungsprobe`):

* `--red-anteil` ist entfernt. `verankerung_belegen` kannte bisher NUR ihn
  und kennt jetzt `--red-anteile-datei` mit derselben Lesart wie die
  uebrigen (`migrationssuite_lauf.lies_auskuenfte`).
* Format: `POLNR;GEVO;DATUM;ANTEIL`, optional `BEZUG` (Freitext:
  Auskunftsschreiben oder Arbeits-Lesart). Rueckwaertskompatibel: Eine Datei
  ohne die Spalte bleibt lesbar.
* Provenienz: Der Schichtbeleg fuehrt unter `provenienz.parameter` statt der
  Liste `red_anteile` den Block `red_anteile_datei` (`name`, `sha256`,
  `bezug` je Police); Uebernahmebeleg und Fuehrungsprobe ebenso. Der
  Konsument (`aktuartest_lauf --schicht`) lehnt einen Beleg mit `red_anteile`
  ab und rechnet `red_anteile_datei` gegen die Eingaben des Belegs nach.
* Fail-fast: nicht registrierte Datei (mit dem Ausweg), fehlende Spalte,
  keine RED-Zeile, nichtnumerischer Anteil, widerspruechliche Zeilen, und
  die Datei ohne Vorgeschichte (die Anteile wirkten sonst nicht) werden
  verweigert.

Nachbesserung nach der Pruefung (Block F):

* Wertebereich: Ein Anteil ist endlich und liegt echt zwischen 0 und 1
  (`nan`, `inf`, 0, 1, Prozentwerte werden mit Police, Datum, Wert und
  Ausweg verweigert).
* Zeilen ohne Wirkung: Jede RED-Zeile entspricht einem RED-Ereignis der
  Vorgeschichte des Laufs (Police; mit DATUM zusaetzlich das Datum im
  selben Wortlaut); eine leere POLNR traegt nichts. Sonst stuende die Zeile
  mit Hash und Bezug im Beleg, ohne je gewirkt zu haben.
* Welt-Gleichheit: Die Schicht eines Schichtbelegs ist auf der Anfangslage
  seiner Auskunft verankert. Ein Lauf mit `--schicht` (`aktuartest_lauf`,
  `migrationssuite_lauf`, `fuehrungsprobe`) vergleicht den SHA-256 der
  Auskunft des Belegs mit dem der Auskunft, die er selbst gelesen hat;
  `keine Auskunft` gilt nur auf beiden Seiten als gleich. Ein Beleg, dessen
  Eingaben eine Auskunft nennen, dessen Parameterblock sie aber nicht fuehrt,
  ist ein Formfehler.
* `aktuartest_lauf` und `migrationssuite_lauf` fuehren die Auskunft im
  Ergebnis als `red_anteile_datei` (`null` ohne Auskunft). Der Abnahmebericht
  verlangt das Feld in der Suite, rechnet es gegen die Eingaben der Suite nach
  und haelt Suite und Fuehrungsprobe auf derselben Auskunft — eine
  verschaerfte Akzeptanzmenge (ADR-012): `GATE_VERSION` des Abnahmeberichts
  `6.0.0`.

`tests/test_auskunft_registriert_klasse.py` haelt die Klasse zu: Ratsche an
der Senke (jeder Anteil, der in `anfangszustaende_je_police` oder
`_serienzustand` geht, stammt aus `lies_auskuenfte`; jedes Modul mit einem
solchen Aufruf kennt `--red-anteile-datei`; kein Argument unter `gates/`
liefert je Police einen Anteil) und ein Zaehltest je Kommando.

## Nachtrag 2026-10-01: Alt-Absetzung nach dem Beitragsende

Entscheid des Maintainers: Der Migrationszugang integriert gelieferte
Vertraege, die im ausfinanzierten Nachlauf (`t <= Jahr < n`) abgesetzt
wurden, in jeder Generation. Beitragsherabsetzung und Teilkuendigung sind
zwei Geschaeftsvorfaelle (ADR-023); eine gelieferte Absetzung nach t war eine
Teilkuendigung, davor sagt es das Verfahren der Quelle (Annahme A2, Tarifplan
KLV, Abschnitt 7.2; `models.bestand.alt_absetzung_ist_teilkuendigung`).
Geliefert ist `ERLSUMME = f x Ursprungssumme`, eine Gleichung mit zwei
Unbekannten, und nach t gibt es keine Beitragsgleichung.

* Einzelfall: Der Vertrag ist der zustandslose Vertrag mit der gelieferten
  Summe und wird ohne Anfangszustand uebernommen; der Anteil wirkt nicht auf
  den Wert, eine Auskunft ist dafuer nicht noetig, und der Vertrag ist nicht
  "gedeckt" (die Auskunft bestimmt an ihm nichts).
* Serie (Erhoehungen vor t, Absetzung danach): Der Anteil verteilt die
  gelieferte Summe auf Grund und Erhoehungen und kommt aus derselben
  registrierten Auskunft wie oben (`--red-anteile-datei`); ohne sie
  verweigert die Uebernahme und nennt diesen Ausweg.
* `migrationszugang.leite_ursprungssumme_ab` bestimmt mit der Auskunft die
  Ursprungssumme als `ERLSUMME / f`; `leite_absetzung_ab` und
  `kalibriere_absetzung_aus_dk` verweigern unter der Teilkuendigung mit dem
  Ausweg (`auskunft_meldung`).

**Nicht ableitbar heisst verweigert, nicht zustandslos** (Pruefer-Befund B1).
Bis dahin wurde ein Vertrag, dessen Anfangszustand die Ableitung nicht
bestimmen konnte, mit einer Warnung und einem Eintrag `ohne_anfangszustand`
als Grundvertrag mit der gelieferten Summe uebernommen, und die ganze Kette
lief mit Exit 0. Jetzt verweigern Uebernahme, Verankerung, aktuarieller Test
und Migrationssuite (`migrationssuite_lauf.verweigere_unbestimmte`; die
Fuehrungsprobe befundet einen solchen Vertrag) und nennen je Police den
Ausweg: den Anteil als registrierte Auskunft, oder den ganzen Fall mit
`--anfangszustand grundvertrag` als nicht freigeschaltet. Jede Ursache, aus
der die Ableitung einen `MigrationszugangFehler` meldet, fuehrt so zur
Verweigerung.

*Was ist Deckung?* Gedeckt ist ein Anfangszustand nur durch das, was seine
**Struktur** bestimmt: die registrierte Auskunft der Quelle je Ereignis (mit
`BEZUG` auch eine dokumentierte Arbeits-Lesart des Aktuars). "Die Werte an
den Bewertungspunkten stimmen" ist keine Deckung: Nach dem Beitragsende sind
A-M1, A-M2 und die Suite gegen die Zerlegung in Grund und Erhoehungen blind
— jede Zerlegung mit derselben Summe erzeugt dieselben Werte bis auf die
Centrundung, und eine spaetere Teilkuendigung zahlte trotzdem falsch aus.
Ein gedeckter Vertrag ist deshalb **Pflichtziehung** von A-M1, A-M2, A-M3
(mit Geschaeftsvorfall im Pruefzeitraum) und der Migrationssuite: Der
Uebernahmebeleg nennt je Police, wodurch sie gedeckt ist (`gedeckt`: Datei,
SHA-256, Bezug), die Belege fuehren dieselbe Menge (`pflichtschicht`,
`pflichtschicht_fehlt`), die Fuehrungsprobe fuehrt sie (`gedeckt`,
`SCHEMA_VERSION` 4), und der Abnahmebericht haelt sie gleich
(`GATE_VERSION` 7.0.0).

**Grenzen, benannt.** Die Grenzen eines gelieferten Vorgangs (`0 < Jahr <
n`, Datum nicht nach dem Stichtag, Jahrestag) prueft eine Stelle vor jeder
Verzweigung (`vorgeschichte_grenzfehler`, Pruefer-Befund B2). Eine
registrierte Auskunft, die *falsch* ist, bestimmt eine falsche Zerlegung mit
richtiger Summe; nach dem Beitragsende sieht das keine Wertpruefung. Die
Verantwortung liegt bei dem, der die Auskunft registriert; eine
Strukturpruefung, die es fangen koennte, braeuchte einen Wert, der von der
Zerlegung abhaengt (etwa den Rueckkaufswert je Baustein der Quelle) — die
Lieferung traegt keinen.

Kein neuer Eingang: Die Auskunft ist die registrierte Datei des Nachtrags vom
2026-09-30. Der Test `tests/test_alt_herabsetzung_nachlauf_e2e.py` faehrt
einen solchen Vertrag durch die ganze Kette, je einmal fuer eine Generation
mit `prospektiv`, `mit_abzug` und `teilkuendigung`, und die Angriffe des
Pruefers als Verweigerungen.
