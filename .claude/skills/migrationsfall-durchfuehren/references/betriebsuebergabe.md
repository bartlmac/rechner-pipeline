# Betriebsuebergabe — Phasenverfahren des Fallskills

Normatives Phasenverfahren des `migrationsfall-durchfuehren`-Skills für
den Zugang eines abgenommenen Migrationsbestands in den Betrieb (ADR-022).
Die frühere Detailreferenz `ablauf-detail.md` ist seit der Aufteilung ein
Kompatibilitätsindex mit allen alten Ankern; diese Datei ist das
normative Zuhause des hier benannten Stoffs. Das vollständige
Zugangsverfahren bleibt AUSSCHLIESSLICH im Skill
`uebernehme-migrationsbestand`; diese Datei koordiniert die Uebergabe und
die Reihenfolge im Fall.

<a id="zugang"></a>
## Zugang nach A-M4 (ADR-022)

Ein abgenommener Bestand tritt in drei Schritten in die produktive Ablage
ein, und der mittlere gehoert dem Menschen. Vor dem Zugang lade den Skill
`uebernehme-migrationsbestand` und dessen Verfahrensschritte GANZ; die
Programmleitung uebergibt Fall, gefuehrten Stand, Linie, Stichtag und
Mandat an `agent/betrieb`. Schluessel bleiben in der Autoritaetsumgebung;
kein Schluesselmaterial lesen, erzeugen oder kopieren.

1. **Zugangsprobe** — zwei deterministische Laeufe auf einer Kopie der
   Ablage, mit und ohne den Eingang. Kommando, Freigabering, Beleg
   `abgeleitet/berichte/zugangsprobe.json` und Wiederholungsregeln
   liegen vollstaendig im Skill `uebernehme-migrationsbestand`
   (Schritt 1 "Zugangsprobe"). Eine ROTE Probe ist ein Befund fuer den
   Menschen, kein Auftrag, die Abnahme nachzubessern.
2. **Zugangsabnahme A-B2** — menschlicher Gate-Entscheid
   (`gate_entscheid --gate A-B2`); zeichnet `mensch/betrieb`;
   `agent/betrieb` legt vor und kann nur ablehnen — hier STOPPST du
   (Skill, Schritt 2). Ohne geltende A-B2 wird nicht registriert.
3. **Registrierung** — `python -m rechner_pipeline.betrieb.uebernahme`
   auf derselben, unbewegten Ablage: Kommando und Voraussetzungen im
   Skill `uebernehme-migrationsbestand` (Schritt 3 "Registrierung nach
   Abnahme").

Die Reihenfolge ist erzwungen: Probe, dann A-B2, dann Registrierung.
Zugang setzt geltende A-M4 samt der von ihr gebundenen Abnahmen voraus.
Linie und Freigabering der Kommandos pruefen bestehende Signaturen, sie
sind keine Signiererlaubnis (Pruefrunde G, `plv/betrieb/README.md`);
Schluessel bleiben in der Autoritaetsumgebung. Rote Probe oder
veraenderte Ablage: Halt, keine nachgebesserte Abnahme behaupten.
Weltaufbau/A-B3 und Auslieferung/A-B1 sind gesonderte Auftraege und
werden nicht im Rahmen des Zugangs mit ausgefuehrt.

<a id="weiterleitung"></a>
## Wohin Teile der alten Detailreferenz gewandert sind

- Quellen -> A-Box, Bestandsabzug -> Ziel-Ontologie und Gate A-Q1:
  `quellen-und-transformation.md`.
- Spez, Golden Master und Stand A-K2/A-O1/A-T1:
  `spezifikation-und-parametrierung.md`.
- Abnahmen A-M1 bis A-M4 und Fallabbruch:
  `abnahmen-und-berichte.md`.
- Das vollständige Zugangsverfahren: Skill `uebernehme-migrationsbestand`.
- Alle alten Anker der früheren Detailreferenz `ablauf-detail.md`
  bleiben als Kompatibilitätsindex erhalten.
