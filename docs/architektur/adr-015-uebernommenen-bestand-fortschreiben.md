# ADR-015: Übernommenen Bestand fortschreiben — ab dem Zugang

**Status:** angenommen am 2026-08-31 (Maintainer), umgesetzt.

## Kontext

Nach einer Migration lebt der übernommene Bestand in den Büchern des
aufnehmenden Unternehmens weiter. Er altert, storniert, wird beitragsfrei
gestellt, läuft ab. Die Ereignis-Engine konnte das nicht.

Sie nahm ausschließlich einen Ursprungsbestand — alle Verträge ``POL``
mit ``status_id`` 1 — und simulierte jeden ab seinem Versicherungsbeginn
(``for j in range(n)``). Ein übernommener Vertrag beginnt 2015 und
gehört uns seit 2026; ab dem Beginn simuliert hätte die Engine elf
Jahre erfunden, die beim abgebenden Unternehmen tatsächlich stattfanden,
und sie als unsere Geschäftsvorfälle gebucht. Der Wachposten gegen
diesen Fall (``Stamm ist kein Basisbestand``) war richtig — er machte die
Fortschreibung übernommener Bestände nur unmöglich statt falsch.

Sichtbar wurde die Lücke an der Nachweisung. Im zusammengesetzten
Bestand (Eigengeschäft der Pfefferminzia plus übernommene Generation
``klv/tg2015``) liefen 477 der 500 übernommenen Verträge vor dem
Horizont ab, ohne dass eine Abgangsbuchung existierte: Sie verschwanden
über ``insurance_end`` aus dem Auskunfts-Schnitt, aber nichts buchte sie
aus. Die Identität ``Anfang + Zugang - Abgang - Umbuchung = Ende`` brach
in jedem Jahr ab 2026.

## Entscheidung

Die Engine simuliert einen Vertrag **ab seinem Bestandszugang, in dem
Zustand, den er mitbringt**. Für eigenes Geschäft ist der Zugang der
Versicherungsbeginn und der Zustand ``POL``; dort ändert sich nichts.

Drei Teile:

1. **Startpunkt.** ``_zugangslage(row)`` liefert je Vertrag das erste zu
   simulierende Vertragsjahr (volle Jahre zwischen ``insurance_start``
   und ``bestandszugang``, ADR-014), den Zustand beim Zugang und das
   Vertragsjahr seines Wechsels. Die Schleifen beider Produkte laufen
   ``range(ab_jahr, n)`` statt ``range(n)``.
2. **Mitgebrachter Zustand.** Ein beitragsfrei übernommener Vertrag
   startet mit gesetztem ``beitragsfrei_ab``; seine beitragsfreie Summe
   wird aus demselben Vertragsjahr rekonstruiert, aus dem die Übernahme
   sie gebucht hat. Er wird nicht noch einmal freigestellt und zieht
   keine Storno- oder Erhöhungsereignisse mehr. Beim BU-Produkt
   entsprechend: Zustand ``BU`` mit der Verweildauer seit der
   Invalidisierung.
3. **Statusnummern.** Die Fortschreibung zählt je Police nach dem
   mitgebrachten ``status_id`` weiter, nicht wieder ab 2. Ein
   beitragsfrei übernommener Vertrag trägt bereits eine 2; ohne den
   Versatz gäbe es zwei Zeilen mit derselben Nummer, und der Stamm
   könnte seinen jüngsten Journalstand nicht mehr bestimmen.

**Die Eingangsprüfung unterscheidet die beiden Fälle am Zugang**, statt
sie zu vermischen:

| Fall | erkannt an | erlaubt |
|---|---|---|
| eigenes Geschäft | ``bestandszugang == insurance_start`` | nur ``POL``/``status_id`` 1 — der alte Wachposten, unverändert |
| übernommen | ``bestandszugang > insurance_start`` | aktiver Zustand (``POL``/``PEX``/``BU``) mit ``status_date <= bestandszugang`` |

Ein übernommener Vertrag mit Zustandswechsel nach dem Zugang ist bereits
fortgeschrieben und wird abgewiesen; ein Vertrag in einem Endzustand wird
gar nicht erst übernommen. Damit bleibt der Schutz gegen
zurückgefütterte Zeitscheiben- und Journalsichten vollständig
erhalten — er gilt jetzt in beiden Formen.

**Die Rechnungsgrundlagen kommen je Vertrag**, nicht je Generation:
``fortschreiben`` nimmt optional die Merkmalstabelle und löst die
Tarifzelle über dieselbe Funktion auf wie die Bewertung
(``auswertung.grundlagen_je_police``). Notwendig, weil bei einer in
Zellen aufgeteilten Generation die Sterbetafel in der Zelle steht und der
Generationsrumpf sie gar nicht trägt. Gemeinsam mit der Bewertung, weil
Simulation und Bericht denselben Tarif rechnen müssen.

## Alternativen

**Den übernommenen Bestand als Neuzugang behandeln** (Vertragsbeginn auf
den Migrationsstichtag legen). Die Engine liefe unverändert. Verworfen:
Der Vertrag verlöre Alter, Eintrittsalter und Restlaufzeit, und die
Bewertung rechnete einen anderen Vertrag als den übernommenen. Die
Rekursion braucht den echten Beginn (ADR-014).

**Ereignisse für die Vorgeschichte nachsimulieren und verwerfen.** Der
Zufallsstrom bliebe identisch zu einem von Beginn an simulierten
Vertrag. Verworfen: Es kostet Rechenzeit für Ergebnisse, die niemand
sehen darf, und die verworfenen Ereignisse könnten den Vertrag
terminieren — dann wäre ein übernommener Bestand teilweise schon tot,
bevor er ankommt.

**Eine eigene Engine für übernommene Bestände.** Verworfen: zwei
Engines sind zwei Fachlichkeiten, die auseinanderlaufen. Der Unterschied
ist ein Startpunkt, kein anderes Modell.

## Folgen

* Ein migrierter Bestand ist ab dem Zugang vollständig fortschreibbar;
  die Nachweisung des Gesamtbestands geht auf. Am Baldrian-Fall gemessen:
  keine verletzte Identität in keinem Jahr, und in der Periode bis zum
  1.1.2026 treten 503 Verträge beitragspflichtig zu (500 übernommene,
  3 eigene), 51 werden beitragsfrei umgebucht (40 mitgebrachte, 11
  eigene).
* Der Zufallsstrom eigener Verträge ist unberührt (``ab_jahr`` 0
  verbraucht dieselben Draws in derselben Reihenfolge) — bestehende
  Läufe liefern dieselben Zahlen.
* ``cli_fortschreibung`` nimmt ``--uebernahme <verzeichnis>`` (das
  Erzeugnis von ``gates.bestand_uebernehmen``) und fährt eigenen und
  übernommenen Bestand in einem Lauf; die Übernahmebuchungen stellt es
  dem Fortschreibungs-Journal voran. Dazu ``--merkmale``; ohne die
  Tabelle bricht eine in Zellen aufgeteilte Generation hart ab
  (ADR-014-Muster), aus dem Übernahme-Verzeichnis kommt sie von selbst.
* Die Übernahme (``gates.bestand_uebernehmen``) bucht Zugang und — bei
  beitragsfrei ankommenden Verträgen — die Umbuchung, beide zum
  Zugangsdatum. Die Engine setzt danach an; ihre Buchungen liegen
  sämtlich nach dem Zugang.
* Regressionsproben in ``tests/test_bestand_uebernommen_fortschreiben.py``.
