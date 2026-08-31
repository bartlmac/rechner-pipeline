# ADR-015: Uebernommenen Bestand fortschreiben — ab dem Zugang

Status: akzeptiert (Auftraggeber, 2026-08-31); umgesetzt in diesem Branch.

## Kontext

Nach einer Migration lebt der uebernommene Bestand in den Buechern des
aufnehmenden Unternehmens weiter. Er altert, storniert, wird beitragsfrei
gestellt, laeuft ab. Die Ereignis-Engine konnte das nicht.

Sie nahm ausschliesslich einen Ursprungsbestand — alle Vertraege ``POL``
mit ``status_id`` 1 — und simulierte jeden ab seinem Versicherungsbeginn
(``for j in range(n)``). Ein uebernommener Vertrag beginnt 2015 und
gehoert uns seit 2026; ab dem Beginn simuliert haette die Engine elf
Jahre erfunden, die beim abgebenden Unternehmen tatsaechlich stattfanden,
und sie als unsere Geschaeftsvorfaelle gebucht. Der Wachposten gegen
diesen Fall (``Stamm ist kein Basisbestand``) war richtig — er machte die
Fortschreibung uebernommener Bestaende nur unmoeglich statt falsch.

Sichtbar wurde die Luecke an der Nachweisung. Im zusammengesetzten
Bestand (Eigengeschaeft der Pfefferminzia plus uebernommene Generation
``klv/tg2015``) liefen 477 der 500 uebernommenen Vertraege vor dem
Horizont ab, ohne dass eine Abgangsbuchung existierte: Sie verschwanden
ueber ``insurance_end`` aus dem Auskunfts-Schnitt, aber nichts buchte sie
aus. Die Identitaet ``Anfang + Zugang - Abgang - Umbuchung = Ende`` brach
in jedem Jahr ab 2026.

## Entscheidung

Die Engine simuliert einen Vertrag **ab seinem Bestandszugang, in dem
Zustand, den er mitbringt**. Fuer eigenes Geschaeft ist der Zugang der
Versicherungsbeginn und der Zustand ``POL``; dort aendert sich nichts.

Drei Teile:

1. **Startpunkt.** ``_zugangslage(row)`` liefert je Vertrag das erste zu
   simulierende Vertragsjahr (volle Jahre zwischen ``insurance_start``
   und ``bestandszugang``, ADR-014), den Zustand beim Zugang und das
   Vertragsjahr seines Wechsels. Die Schleifen beider Produkte laufen
   ``range(ab_jahr, n)`` statt ``range(n)``.
2. **Mitgebrachter Zustand.** Ein beitragsfrei uebernommener Vertrag
   startet mit gesetztem ``beitragsfrei_ab``; seine beitragsfreie Summe
   wird aus demselben Vertragsjahr rekonstruiert, aus dem die Uebernahme
   sie gebucht hat. Er wird nicht noch einmal freigestellt und zieht
   keine Storno- oder Erhoehungsereignisse mehr. Beim BU-Produkt
   entsprechend: Zustand ``BU`` mit der Verweildauer seit der
   Invalidisierung.
3. **Statusnummern.** Die Fortschreibung zaehlt je Police NACH dem
   mitgebrachten ``status_id`` weiter, nicht wieder ab 2. Ein
   beitragsfrei uebernommener Vertrag traegt bereits eine 2; ohne den
   Versatz gaebe es zwei Zeilen mit derselben Nummer, und der Stamm
   koennte seinen juengsten Journalstand nicht mehr bestimmen.

**Die Eingangspruefung unterscheidet die beiden Faelle am Zugang**, statt
sie zu vermischen:

| Fall | erkannt an | erlaubt |
|---|---|---|
| eigenes Geschaeft | ``bestandszugang == insurance_start`` | nur ``POL``/``status_id`` 1 — der alte Wachposten, unveraendert |
| uebernommen | ``bestandszugang > insurance_start`` | aktiver Zustand (``POL``/``PEX``/``BU``) mit ``status_date <= bestandszugang`` |

Ein uebernommener Vertrag mit Zustandswechsel NACH dem Zugang ist bereits
fortgeschrieben und wird abgewiesen; ein Vertrag in einem Endzustand wird
gar nicht erst uebernommen. Damit bleibt der Schutz gegen
zurueckgefuetterte Zeitscheiben- und Journalsichten vollstaendig
erhalten — er gilt jetzt in beiden Formen.

**Die Rechnungsgrundlagen kommen je Vertrag**, nicht je Generation:
``fortschreiben`` nimmt optional die Merkmalstabelle und loest die
Tarifzelle ueber dieselbe Funktion auf wie die Bewertung
(``auswertung.grundlagen_je_police``). Notwendig, weil bei einer in
Zellen aufgeteilten Generation die Sterbetafel in der Zelle steht und der
Generationsrumpf sie gar nicht traegt. Gemeinsam mit der Bewertung, weil
Simulation und Bericht denselben Tarif rechnen muessen.

## Alternativen

**Den uebernommenen Bestand als Neuzugang behandeln** (Vertragsbeginn auf
den Migrationsstichtag legen). Die Engine liefe unveraendert. Verworfen:
Der Vertrag verloere Alter, Eintrittsalter und Restlaufzeit, und die
Bewertung rechnete einen anderen Vertrag als den uebernommenen. Die
Rekursion braucht den echten Beginn (ADR-014).

**Ereignisse fuer die Vorgeschichte nachsimulieren und verwerfen.** Der
Zufallsstrom bliebe identisch zu einem von Beginn an simulierten
Vertrag. Verworfen: Es kostet Rechenzeit fuer Ergebnisse, die niemand
sehen darf, und die verworfenen Ereignisse koennten den Vertrag
terminieren — dann waere ein uebernommener Bestand teilweise schon tot,
bevor er ankommt.

**Eine eigene Engine fuer uebernommene Bestaende.** Verworfen: zwei
Engines sind zwei Fachlichkeiten, die auseinanderlaufen. Der Unterschied
ist ein Startpunkt, kein anderes Modell.

## Folgen

* Ein migrierter Bestand ist ab dem Zugang vollstaendig fortschreibbar;
  die Nachweisung des Gesamtbestands geht auf. Am Baldrian-Fall gemessen:
  keine verletzte Identitaet in keinem Jahr, und in der Periode bis zum
  1.1.2026 treten 503 Vertraege beitragspflichtig zu (500 uebernommene,
  3 eigene), 51 werden beitragsfrei umgebucht (40 mitgebrachte, 11
  eigene).
* Der Zufallsstrom eigener Vertraege ist unberuehrt (``ab_jahr`` 0
  verbraucht dieselben Draws in derselben Reihenfolge) — bestehende
  Laeufe liefern dieselben Zahlen.
* ``cli_fortschreibung`` nimmt ``--merkmale``; ohne die Tabelle bricht
  eine in Zellen aufgeteilte Generation hart ab (ADR-014-Muster).
* Die Uebernahme (``gates.bestand_uebernehmen``) bucht Zugang und — bei
  beitragsfrei ankommenden Vertraegen — die Umbuchung, beide zum
  Zugangsdatum. Die Engine setzt danach an; ihre Buchungen liegen
  saemtlich nach dem Zugang.
* Regressionsproben in ``tests/test_bestand_uebernommen_fortschreiben.py``.
