# Auswertung Fall-Lauf 2 (Baldrian-Uebernahme) — System und Autonomie

Interne Nacharbeit zum zweiten Migrationslauf (2026-09-01/02).
Fachlicher Abschlussbericht: `docs/faelle/baldrian-lauf2.md`.
Chronik der 23 Korrekturen mit Commits: `regie/drehbuch-lauf2.md`
(Spielleiter-Bereich). Quellen dieser Auswertung: die drei
Reibungsprotokolle der Operatoren (Fall, `abgeleitet/`), das
Korrektur-Protokoll des Programmleiters, die Drehbuch-Chronik.

## 1 Vorher/Nachher — Kern und Bestand

| Groesse | vor Lauf 2 | nach Lauf 2 |
|---|---|---|
| A-M1 Stichtagstest | 61/100 (erster rechnender Lauf) | 100/100 |
| A-M4 Migrationscontrolling | 18/834 (erster Lauf mit Schicht) | 834/834, 0 Befunde |
| Schichtbeleg max Residuum | 33.159 EUR | 0,02 EUR |
| Schichtbeleg Residuensumme | -547.928 EUR | -0,14 EUR |
| Kern-Version | 3.1.0 | 3.3.0 |
| Testsuite | 1479 | 1517 |

Neue, dauerhafte Faehigkeiten (je als Lieferungseigenschaft
parametriert, Vorgabe = Bestandsverhalten):

- **Kern:** volle Beitragsformel je Erhoehungsscheibe
  (`gamma1_uebernehmen`); Stornoabzugs-Grenzen je Baustein
  (`stoab_je_baustein`); Teilkuendigung als drittes
  Herabsetzungs-Verfahren (`TEILKUENDIGUNG`, zustandsloser Rest);
  Terminalbedingung der Korrekturschicht am Ablauf (Zahlungsjahre bis
  n-1).
- **Bestand/Ableitungen:** Serien-Rekonstruktion aus dem Dynamiksatz
  inkl. Kandidaten-Bestimmung offener Herabsetzungsanteile ueber die
  Beitrags- bzw. Anker-Gleichung, Anteils-Unerheblichkeit,
  Identifizierbarkeits-Wache gegen Rundungsphantome; Verankerung auf
  der Zustands-Welt und dem gefuehrten Wert (vx_mrv).
- **QA/Gates:** Korrekturschicht im Migrationscontrolling (gemeinsame
  Bewertung `schichtwert_bei`); Jahrestags-Konvention des
  DK-Vergleichs (`--dk-stichtag`); komponentenskalierte Toleranzen
  durchgaengig (Engine, Suite, Abnahmebericht-Nachrechnung);
  Kandidaten-Plausibilitaetskorridore; Pruefluecken- und
  Antrags-Ausweis im Ergebnis; Datei-Form-Embedding der
  TransformationsSpec; Schichtbeleg-Producer und
  Zeichnungsordnungs-Anschluss von `ontologie.entscheide` (beide aus
  dem Lauf heraus entstanden).

## 2 Vorher/Nachher — KI und Betrieb

| Groesse | Lauf-Erwartung | Ergebnis Lauf 2 |
|---|---|---|
| Fachliche Eskalationen an den Maintainer | unbekannt | 0 (eine Budget-Eskalation frueh im Lauf, danach Mandats-Praezisierung) |
| Maintainer-Eingriffe gesamt | moeglichst wenige | 3, alle Betriebs-Infrastruktur (2x Enter im Pane, 1x Permission-Freigabe) |
| Kern/Gates-Korrekturen im Regime dev x PLV-IT | einzelne | 23, alle protokolliert und lauf-verifiziert |
| Volle Kaskaden-Durchgaenge | 1 | 5 (je Systemstand-Wechsel, Neuzeichnung inklusive) |
| Governance-Verstoesse | 0 | 0 (2 korrekte Verweigerungen: Peer-Mandat, Regie-Seed) |

Die Qualitaet der Operator-Befunde trug den Lauf: Der Aktuar
diagnostizierte mit GeVo-Nachschlaegen, Formel-genauen Residuenmustern
und zuletzt einem selbst nachgerechneten Serialisierungs-Mismatch;
der Programmleiter hielt vor jeder Fehldeutungsfalle an und meldete
eigene Bedienfehler transparent; der Quell-Experte attestierte eine
Datenluecke erst nach ernsthaftem Rekonstruktionsversuch — sein
Seed-Suchlauf gegen das eigene Rechenwerk blieb erfolglos, weil die
Regie-Trennung genau das verhindern soll (Governance-Beleg, kein
Mangel).

## 3 Betriebs-Lehren (aus den drei Reibungsprotokollen konsolidiert)

1. **Peer-Kanal verwirft still** (drei Vorfaelle, je ~1 h Stillstand;
   beim dritten blockte auch die Wiederholung und es brauchte den
   Umweg ueber eine dritte Session). Regel etabliert:
   auftragsausloesende Nachrichten quittieren, ausbleibende Quittung
   -> Absender stellt NEU FORMULIERT zu; gilt beidseitig zwischen
   allen Sessions. Werkzeug-Wunsch an die Plattform bleibt: der
   Loop-Klassifikator selbst.
2. **Mensch-Gates brauchen aktive Zustellung**: Rueckfragen, die nur
   im eigenen Pane stehen, erreichen einen headless arbeitenden
   Maintainer nicht (inkl. getippter, nie gesendeter Antworten).
   MENSCH-GATE-Meldeweg ueber die Systembetreuung etabliert;
   Permissions der Lauf-Kommandoklassen vorab freigegeben
   (`.claude/settings.local.json`) statt Classifier je Aufruf.
3. **Kaskaden-Rezept fehlt** (Programmleiter-Protokoll Nr. 8): Der
   vollstaendige Lauf-Aufruf (alle Flags, alle registrierten Quellen
   je Abnahme) ist nirgends als Ganzes persistiert; die Rekonstruktion
   nach Korrektur 21 kostete einen Fehlalarm (vergessenes
   --stoab-je-baustein). Nacharbeit: Producer schreiben ihren vollen
   Aufruf in die Ergebnis-Provenienz (wie verankerung_belegen es
   bereits tut) oder ein versioniertes Kaskaden-Rezept je Fall.
4. **Neuzeichnungs-Verhaeltnismaessigkeit** (Aktuars-Protokoll Nr. 3):
   Jede Kern-Korrektur entwertet ALLE Gate-Snapshots des Falls, auch
   wenn deren gebundene Artefakte (A-Box/Spez/Eingang) nachweislich
   unveraendert sind — fuenf volle Neuzeichnungs-Durchgaenge in diesem
   Lauf. Architekturfrage fuer die Nacharbeit: Bindung praeziser an
   die tatsaechlich gebundenen Artefakte je Gate, ohne die
   Provenienz-Garantie zu schwaechen — oder den bewussten Grund fuer
   die Ganz-oder-gar-nicht-Bindung in der Gate-Doku festschreiben.
5. **Extraktions-Skill-Luecken** (Programmleiter Nr. 1-3):
   Dimensions-IDs ohne kanonisches Vokabular, `eingabe:<groesse>`-
   Konvention nur im Code, `unisex`-Zurueckhaltung kollidiert mit der
   P-K1-Beispielrechnung; dazu stillschweigend wirkungslose
   `quellnamen`-Zielstrings mit Klammerzusatz. Nacharbeit: Skill
   `extrahiere-quellfragment` ergaenzen, Format-Validator fuer
   quellnamen-Ziele, P-K1-Hinweis bei gleichgerichteter
   Gesamtabweichung.
6. **Vorbehalts-Ausweis** (Programmleiter Nr. 6, bekannter
   Backlog-Punkt, im Lauf erneut bestaetigt): Rechenlauf-Ausgaben
   nennen vorlaeufige Diskrepanz-Aufloesungen nicht — die
   2,4-Prozent-Fehldeutung des ersten A-M1 waere sonst nicht passiert.
7. **Zwei sich aufhebende Fehler bleiben unsichtbar, bis ein zweiter
   Pruefweg kommt**: Die Schicht-Asymmetrie des aktuariellen Tests
   (keine Anwendung bei Zustands-Policen) verdeckte zweimal
   Verankerungs-Phantome, die erst das Migrationscontrolling mit
   universaler Schichtanwendung sichtbar machte. Nacharbeit: AT auf
   dieselbe universale Anwendung heben (nach dem Merge, mit
   Neuzeichnungs-Bewusstsein) — plus Auftrags-Echo der
   Migrationssuite fuer die Gate-Nachrechenbarkeit und den
   Zirkularitaets-Ausweis kalibrierter Zustaende.

## 4 Workshop-Rohstoff (Retrospektive, 3. Termin)

Erzaehlbogen in fuenf Akten, aus Drehbuch-Chronik und diesem Dokument:

1. **Aufsetzung** — vier Rollen, Zeichnungsordnung, Mandate; die
   Lieferung 2 als realistischer Bestand (Serien als Regelfall).
2. **Das System lernt das Tarifwerk** — gamma1-Beweis auf 2 Cent,
   Stornoabzug je Baustein aus Residuen in Grenzen-Vielfachen,
   Unisex-Fund; Feststellungen statt Annahmen.
3. **Die Datenluecke** — Baldrians ernsthafte Rekonstruktion, die
   Absage als Auskunft, Bestimmung ueber Beitrags-/Ankergleichung,
   Unerheblichkeit, die zwei Lesarten mit Falsifizierbarkeits-Auflage.
4. **Die Maschine prueft die Maschine** — A-M4 deckt auf, was A-M1
   nie sehen konnte (Jahrestags-Konvention, Verankerungs-Phantome,
   Toleranz-Nachzuege bis in die Gate-Nachrechnung); je Befund eine
   Korrektur, fuenf volle Kaskaden.
5. **Abschluss und Bilanz** — Fuenffach-Zeichnung in einem Zug,
   Schicht praktisch leer; was der Mensch tat (drei
   Infrastruktur-Handgriffe) und was daraus wurde (drei
   Betriebsregeln).

Risikoarme Live-Elemente: einen Gate-Entscheid vorfuehren, den
Abnahmebericht oeffnen, eine Diskrepanz-Aufloesung im A-Box-Journal
zeigen.
