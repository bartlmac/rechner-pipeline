# Detailreferenz zum Migrationsfall — Kompatibilitätsindex

Diese Datei ist seit der Aufteilung des Fallskills ein KOMPATIBILITÄTSINDEX,
keine zweite Vollkopie und kein eigenes Verfahren. Die vier normativen
Phasenverfahren tragen den Stoff; sie laden die Abschnitte, die ihr
aktueller Schritt braucht:

- Quellen und Transformation: `quellen-und-transformation.md`
  (Fallanlage, Fallauftrag, Quellen -> A-Box, Bestandsabzug,
  Gate A-Q1, Reihenfolge-Zwaenge).
- Spezifikation und Parametrierung: `spezifikation-und-parametrierung.md`
  (Stufe 2, Golden Master P-K1, Stand A-K2/A-O1/A-T1).
- Abnahmen und Berichte: `abnahmen-und-berichte.md` (A-M1/A-M2/A-M3,
  Migrationscontrolling A-M4, Tarifplanfestlegungen, Fallabbruch,
  Abbruchkriterien).
- Betriebsuebergabe: `betriebsuebergabe.md` (Zugang nach A-M4) — das
  vollständige Zugangsverfahren liegt ausschliesslich im Skill
  `uebernehme-migrationsbestand`.
- Fachreferenzen für Schicht/Pflichtmengen:
  `aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`;
  für Fortschreibung/Freischaltung/Berichtspaar:
  `pruefe-migrationscontrolling/references/fuehrung-und-berichtspaar.md`.

Alle alten Anker dieser Datei bleiben bestehen und loesen weiterhin auf —
je Anker eine Rubrik, die eindeutig auf sein neues Zuhause verweist.
Wer einen alten Anker direkt anspringt, landet auf einer kurzen
Weiterleitung und wird von dort ins normative Verfahren gefuehrt; er
liest nicht zwei Vollkopien.

## Inhaltsverzeichnis

- [Stufe 0 — Fall-Arbeitsbereich](#fallanlage)
- [Stufe 0b — Fallauftrag](#fallauftrag)
- [Stufe 1 — Quellen -> A-Box](#quellen)
- [Stufe 1b — Bestandsabzug](#transformation)
- [Gate A-Q1](#aq1)
- [Stufe 2 — A-Box -> Spez -> Kern](#spez)
- [Stufe 3 — Golden Master](#golden)
- [Stand A-K2/A-O1/A-T1](#stand)
- [Stufe 3b — Bestandspruefung](#bestandsabnahmen)
- [Gate A-M4](#am4)
- [Zugang nach A-M4](#zugang)
- [Schichtbeleg und Pflichtmengen](#schichtbeleg)
- [Tarifplanfestlegungen](#tarifplanfestlegungen)
- [Reihenfolge-Zwaenge](#reihenfolge)

<a id="fallanlage"></a>
## Stufe 0 — Fall-Arbeitsbereich

Fall-Arbeitsbereich anlegen, Quellen registrieren, Status. Normativ:
[Stufe 0 in Quellen und Transformation](quellen-und-transformation.md#fallanlage).

<a id="fallauftrag"></a>
## Stufe 0b — Fallauftrag

Fallauftrag A-M6, STOPP bis gezeichnet. Normativ:
[Stufe 0b in Quellen und Transformation](quellen-und-transformation.md#fallauftrag).

<a id="quellen"></a>
## Stufe 1 — Quellen -> A-Box

Vorverdichtung, Extraktion je Quelle, Verifikation, Merge, Gate P-Q3.
Normativ: [Stufe 1 in Quellen und Transformation](quellen-und-transformation.md#quellen).

<a id="transformation"></a>
## Stufe 1b — Bestandsabzug -> Ziel-Ontologie

Vertraege in das Ziel-Datenmodell, Spec, Anwendung, Freischaltung des
Bestands. Normativ: [Stufe 1b in Quellen und Transformation](quellen-und-transformation.md#transformation).

<a id="aq1"></a>
## Gate A-Q1 — Mensch

Vorlage, menschliche Entscheidung, Zeichnungsordnung, Linie. Normativ:
[Gate A-Q1 in Quellen und Transformation](quellen-und-transformation.md#aq1).

<a id="spez"></a>
## Stufe 2 — A-Box -> Spez -> Kern

Spezbildung, Tafel-Import-Dry-run, Kern als Parametrierung. Normativ:
[Stufe 2 in Spezifikation und Parametrierung](spezifikation-und-parametrierung.md#spez).

<a id="golden"></a>
## Stufe 3 — Golden Master

Gate P-K1, volle Suite, ehrliches `zellen_ohne_erwartungswerte`.
Normativ: [Stufe 3 in Spezifikation und Parametrierung](spezifikation-und-parametrierung.md#golden).

<a id="stand"></a>
## Stand des Falls — A-K2, A-O1, A-T1

Verweis oder Abnahme im Fall; kein Agentenschreiben an T-Box/Kern.
Normativ: [Stand in Spezifikation und Parametrierung](spezifikation-und-parametrierung.md#stand).

<a id="bestandsabnahmen"></a>
## Stufe 3b — Pruefung des uebernommenen Bestands

P-B1, Abnahmesuite, Freischaltung/Fuehrungsprobe, Bestandsberichte
vor/nach, Abnahmebericht. Normativ:
[Stufe 3b in Abnahmen und Berichte](abnahmen-und-berichte.md#bestandspruefung).

<a id="am4"></a>
## Gate A-M4 — Mensch

Annahme mit Pinning der Abnahme-Snapshots, Standabnahmen und
Scope-Pflichtbelegen. Normativ:
[Gate A-M4 in Abnahmen und Berichte](abnahmen-und-berichte.md#am4).

<a id="zugang"></a>
## Zugang nach A-M4 — Betrieb (ADR-022)

Drei Schritte — Zugangsprobe, menschliche A-B2, mandatierte
Registrierung; das vollständige Verfahren liegt ausschliesslich im Skill
`uebernehme-migrationsbestand`. Normativ:
[Zugang in Betriebsuebergabe](betriebsuebergabe.md#zugang).

<a id="schichtbeleg"></a>
## Schichtbeleg und Pflichtmengen

Schichtbeleg-Erzeuger (`gates.verankerung_belegen`) und Mengenregel der
Pflichtziehung. Normativ in der Fachreferenz des Aktuartest-Skills:
[schicht-und-pflichtmengen.md](../../aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md#schichtbeleg).

<a id="tarifplanfestlegungen"></a>
## Tarifplanfestlegungen vor A-M4

Schichtfestlegungen des migrierten Tarifplans, nur bei rechnender
Schicht. Normativ:
[Tarifplanfestlegungen in Abnahmen und Berichte](abnahmen-und-berichte.md#tarifplanfestlegungen).

<a id="reihenfolge"></a>
## Reihenfolge-Zwaenge (was Belege rueckwirkend entwertet)

Merge einmal, Vorbedingungen, Datenabhaengigkeiten, Pfad-Vertraege.
Normativ:
[Reihenfolge in Quellen und Transformation](quellen-und-transformation.md#reihenfolge).

Der **Fallabbruch (A-M5)** und die **Abbruchkriterien** liegen normativ
in [Abnahmen und Berichte](abnahmen-und-berichte.md#fallabbruch).
