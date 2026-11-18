---
name: uebernehme-migrationsbestand
description: >-
  Bereitet den Zugang eines abgenommenen Migrationsbestands mit Zugangsprobe,
  menschlichem A-B2 und anschliessender mandatierter Uebernahme vor.
  Verwende bei "Zugangsprobe", "A-B2 vorbereiten" oder "migrierten Bestand
  in den Betrieb uebernehmen". Nicht fuer Weltaufbau, Anfangsbestand A-B3,
  Auslieferung A-B1, Tageslauf, aktuarielle Abnahmen oder eigene Gatezeichnung.
---

# Migrationsbestand in den Betrieb uebernehmen

## Auftrag und Eingaben

Du bist `agent/betrieb`; du bereitest vor und zeichnest nie A-B2.
Vor Arbeit gilt `AGENTS.md` (ADR-032). Der Auftrag nennt Fall, gefuehrten
Stand, Stichtag, optionalen Probehorizont, Linie, Zeichnungsordnung und
Schluesselpfade fuer die autorisierten Systemkommandos. Kein Schluessel-
material lesen, erzeugen oder kopieren. Die Pfade sind keine Erlaubnis,
Annahmen menschlicher Rollen auszufuehren.

Verfahrensunterlagen: dieser Skill, ADR-022/025/026 und
`plv/betrieb/README.md`. Fachliche Eingaben: die im Auftrag erlaubten
Fall-/Standartefakte, keine fremden Faelle oder impliziten Lieferungen.
Zugang setzt geltende A-M4 und die von ihr gebundenen Abnahmen voraus;
deren Gueltigkeit pruefen die bestehenden Kommandos gegen die Linie.
Fehlende Abnahme, Mandat, Datei oder gesperrter Skill: STOPP.

## 1 Zugangsprobe

Auf der ausdruecklich zugewiesenen Ablage prueft das bestehende Kommando
zwei deterministische Laeufe auf einer Kopie, mit und ohne Zugang:

```bash
python -m rechner_pipeline.betrieb.zugangsprobe \
    --stand <stand> --fall <fall> --stichtag <ISO> \
    --schluessel <betrieb.key> --zeichnungsordnung <ordnung> \
    --freigabe-schluessel <vorstand.key> \
    --freigabe-schluessel <aktuariat.key> --linie <linie>
```

Optional `--bis <ISO>` nur nach Auftrag. Die Freigabeschluessel im Ring
dienen der Pruefung bestehender Signaturen; sie sind keine Signiererlaubnis.
Melde den echten Exitcode und `abgeleitet/berichte/zugangsprobe.json`.
Lies die Befund-/Vergleichsstruktur vollstaendig; wenn Read kuerzt,
erschliesse weitere Abschnitte gezielt. Ein gelesener Ausschnitt ist
kein Gesamturteil. Jede Abweichung und ungepruefte Groesse ausweisen.
Eine rote Probe ist ein Halt, kein Auftrag zur Anpassung der Abnahme.

## 2 Menschliche Zugangsabnahme A-B2 — STOPP

Uebergib Bericht, Standbezug, Fall, Linie, Stichtag, Befunde und offene
Punkte an `mensch/betrieb`. Der Mensch entscheidet und zeichnet A-B2 mit
`rechner_pipeline.gates.gate_entscheid`; kein Agent fuehrt diese Annahme
aus. Eine unsignierte Agentenablehnung ist nur ein Zwischenstand.
Ohne geltende A-B2 nicht registrieren, auch nicht auf Zuruf als Ersatz
fuer die gezeichnete Entscheidung.

## 3 Registrierung nach Abnahme

Nur nach menschlichem A-B2 und ausdruecklichem Ausfuehrungsauftrag auf
demselben unbewegten Stand:

```bash
python -m rechner_pipeline.betrieb.uebernahme \
    --stand <stand> --fall <fall> --stichtag <ISO> \
    --betriebsschluessel <betrieb.key> --zeichnungsordnung <ordnung> \
    --freigabe-schluessel <vorstand.key> \
    --freigabe-schluessel <aktuariat.key> \
    --freigabe-schluessel <betrieb-freigabe.key> --linie <linie>
```

`betrieb.key` ist der Betriebsschluessel des Systemkommandos;
`betrieb-freigabe.key` gehoert zu `mensch/betrieb` und prueft A-B2.
Die Systemvalidierung bindet Zugang/Abnahme/Stand; ihre Verweigerung
nicht umgehen. Hat sich Stand, Fall, Datum oder Linie bewegt: Halt,
erneute Probe/Abnahme beim Menschen klaeren. Keine direkten Tabellen-
aenderungen und keine Uebernahme ohne die bereitgestellten Kommandos.

## Rueckgabe und Grenzen

Auftrag-ID, Ladeweg, Bericht-/Protokollpfade, echte Befehle und Exitcodes,
Pruefresultate, unausgefuehrte Checks, offene Punkte und Haltgrund an die
Programmleitung und die Betriebsverantwortung uebergeben.
Keine A-B1-/A-B3-/Tageslauf-Schritte oder Welt-/Schluesselanlage implizit
mit ausfuehren. Kein neuer Gatevertrag und keine eigene Fachrechnung.
