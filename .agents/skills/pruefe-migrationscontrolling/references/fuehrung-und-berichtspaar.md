# Fuehrung und Berichtspaar — Fachreferenz des Controlling-Skills

Normative Fachreferenz des Skills `pruefe-migrationscontrolling`:
Fortschreibung des uebernommenen Bestands, Freischaltung, das
Bestandsberichtspaar vor/nach und der Abnahmebericht. Diese Datei ist
ein eigenes Zuhause fuer den hier benannten Stoff — der
`migrationsfall-durchfuehren`-Skill verweist hierauf, statt den Stoff
zu duplizieren. Lade die Abschnitte, die dein Lauf braucht, vollständig.

## Inhaltsverzeichnis

- [Fortschreibung des uebernommenen Bestands](#fortschreibung)
- [Freischaltung (Schritt vor A-M4)](#freischaltung)
- [Bestandsberichtspaar vor/nach](#berichtspaar)
- [Abnahmebericht](#abnahmebericht)

<a id="fortschreibung"></a>
## Fortschreibung des uebernommenen Bestands

Der uebernommene Bestand lebt in den Buechern des aufnehmenden
Unternehmens weiter — er altert, storniert, laeuft ab. Ohne diesen
Schritt fehlen ihm die Abgangsbuchungen, und die Bestandsbewegung des
Gesamtbestands geht nicht auf.

```
python -m rechner_pipeline.bestand.cli_fortschreibung \
    --config <bestand-config>.toml --bis <iso> --neuzugang-ab <stichtag> \
    --portfolio <eigener-basisbestand>.parquet \
    --uebernahme faelle/<fall>/abgeleitet/bestand \
    --out-dir faelle/<fall>/abgeleitet/bestand-nach
```

Eigener und uebernommener Bestand gehen in DENSELBEN Lauf — ein
GeVo-Strom, ein Erzeuger. Zwei getrennte Laeufe zu mischen ergaebe einen
Bestand, in dem ein Teil fortgeschrieben ist und der andere nicht. Die
Engine setzt je Vertrag am Bestandszugang an, im Zustand, den er
mitbringt (ADR-015); die Buchungen der Uebernahme (Zugang, bei
beitragsfrei ankommenden Vertraegen die Umbuchung) stellt das Kommando
dem Fortschreibungs-Journal voran. Die Merkmalstabelle nimmt es aus dem
Uebernahme-Verzeichnis, `--merkmale` uebersteuert sie. Die Fortschreibung
liest Bausteine, Schicht und Verankerung der Uebernahme und reicht sie in
ihr Laufverzeichnis durch; P-B1 auf dem Lauf bekommt `--schichten` und
`--verankerung` dazu (Storno-Herleitung mit Schicht).

Den Bestandsbericht der STUFE 1b schreibst du IN DAS
Fortschreibungsverzeichnis mit `--berichtsstichtag <migrationsstichtag>`
statt `--bis`/`--stichtag`: Der Bericht endet am Uebernahmestichtag und
zeigt keine Projektion. Eine Prognose ueber Jahre nach der Uebernahme ist
hier keine Aussage ueber den uebernommenen Bestand, sondern eine
Behauptung ueber Tage, die noch nicht stattgefunden haben — und sie
macht den Bericht mit den anderen beiden unvergleichbar, weil jeder einen
anderen Horizont haette. Beide Schalter zugleich sind ein Fehler, kein
Vorrang. Der vollstaendige, EIGENE Aufruf:

```
python -m rechner_pipeline.bestand.cli_report \
    --portfolio faelle/<fall>/abgeleitet/bestand-nach/bestand_gesamt.parquet \
    --historie  faelle/<fall>/abgeleitet/bestand-nach/historie.parquet \
    --ledger    faelle/<fall>/abgeleitet/bestand-nach/ledger.parquet \
    --scheiben  faelle/<fall>/abgeleitet/bestand-nach/scheiben.parquet \
    --merkmale  faelle/<fall>/abgeleitet/bestand/merkmale.parquet \
    --config <bestand-config>.toml \
    --berichtsstichtag <migrationsstichtag> \
    --out faelle/<fall>/abgeleitet/bestand-nach/bestandsbericht.html
```

Dieser Stufe-1b-Betriebsbericht bleibt ein separater Aufruf und wird
NICHT als Fallbericht-Aufruf des Berichtspaars wiederverwendet (Anker
`berichtspaar`); die Vorzeigeseite findet ihn ueber den Artefaktnamen
`bestandsbericht*.html` (werkzeuge/falldaten.py liest ihn unter
`abgeleitet/`, nicht das Verzeichnis).

Quelle ist `bestand_gesamt.parquet` (der GEFUEHRTE Gesamtbestand), nicht
der Basisbestand. `--merkmale` ist Pflicht, sobald die uebernommene
Generation in Tarifzellen aufgeteilt ist; ohne sie bricht die Bewertung
ab, statt eine Zelle zu raten.

<a id="freischaltung"></a>
## Freischaltung (Schritt vor A-M4)

Was die Abnahmen A-M1 bis A-M3 bestanden haben, MUSS der gefuehrte
Bestand rechnen — die Abnahmen sind die Entwicklungsroutine, die
Freischaltung der Moment, in dem der Stand zur Eigenschaft des Bestands
wird. Vier Handgriffe, alle Systemkommandos:

1. Das Tarifwerk der Spez, mit dem die Abnahmen bestanden haben, steht in
   der Bestand-Config der Generation (`scheiben_mit_gamma1`,
   `stoab_je_baustein`, `red_verfahren`, `tku_umfang`); der erzeugte
   Abschnitt `generation-zellen.toml` der Uebernahme traegt es bereits —
   er wird in die Config uebernommen, nicht abgetippt. Migrationscontrolling
   und Fuehrungsprobe verweigern eine Config mit einem anderen Tarifwerk.
2. Der Schichtbeleg (`verankerung_belegen`, Fachreferenz
   `aktuartest-durchfuehren/references/schicht-und-pflichtmengen.md`)
   schreibt `schichten.parquet` in das Uebernahme-Verzeichnis: Die
   Korrekturschicht ist Vertragsattribut, Storno zahlt Basiswert plus
   Schicht, der Abschluss weist sie aus.
3. Die Fortschreibung (`cli_fortschreibung --uebernahme`, Anker
   `fortschreibung` oben) liest Bausteine, Schicht und Verankerung der
   Uebernahme und reicht sie in ihr Laufverzeichnis durch; P-B1 auf dem
   Lauf bekommt `--schichten` und `--verankerung` dazu.
4. Die Fuehrungsprobe stellt beides gegen die Pruefstrecke:

```
python -m rechner_pipeline.gates.fuehrungsprobe \
    --fall faelle/<fall> --repo-root . --generation klv/tg2015 \
    --uebernahme faelle/<fall>/abgeleitet/bestand \
    --fortschreibung faelle/<fall>/abgeleitet/bestand-nach \
    --config <bestand-config>.toml --zeilen <zeilen>.json \
    --vorgeschichte <registrierte-gevo-metadaten>.csv --stichtag <iso> \
    --schicht abgeleitet/schichten/verankerung_schichten.json \
    [--red-anteile-datei <registrierte-auskunft>.csv] \
    [--red-anteil-kandidat <anteil> ...]
```

Sie prueft den Uebernahmebeleg (Modus, Tarifwerk gleich Config gleich
Spez, Quellverfahren gleich Spez), je Vertrag Stammsumme, Bausteine,
Beitragsfreistellung, Zugang und Umbuchung gegen den Anfangszustand der
Abnahmen, die Grundlagen der Config gegen die Spez-Zelle, die Schicht,
und jede Buchung nach dem Stichtag gegen die Pruefstrecken-Engine. Der
Beleg `abgeleitet/berichte/fuehrungsprobe.json` ist Pflichtbelegrolle
`fuehrungsprobe` von A-M4 im Bestands-Scope; der Abnahmebericht bindet
ihn (`--fuehrungsprobe`, Vorgabe dieser Pfad). Exit 1 = nicht bestanden:
dann ist die Fuehrung zu korrigieren, nicht der Beleg.

<a id="berichtspaar"></a>
## Bestandsberichtspaar vor/nach

Gleiche fachliche Bewertungs-/Darstellungsregeln, aber bewusst
verschiedene Horizonte und Bestandsstaende; dies ist kein
Eigenbestand-Vorher/Nachher. Der Stamm allein ist nicht der gefuehrte
Zustand: Neben `bestand.parquet` der Uebernahme liegen immer Historie,
Ledger und Scheiben, und ein Aufruf ohne den Lauf endet mit Exit 2.

VOR aus dem Uebernahme-Verzeichnis bis Stichtag 1:

```
python -m rechner_pipeline.bestand.cli_report \
    --portfolio faelle/<fall>/abgeleitet/bestand/bestand.parquet \
    --historie  faelle/<fall>/abgeleitet/bestand/historie.parquet \
    --ledger    faelle/<fall>/abgeleitet/bestand/ledger.parquet \
    --scheiben  faelle/<fall>/abgeleitet/bestand/scheiben.parquet \
    --merkmale  faelle/<fall>/abgeleitet/bestand/merkmale.parquet \
    --config <bestand-config>.toml \
    --bis <stichtag-1> --out <bericht-vor>.html
```

NACH aus dem gefuehrten Gesamtbestand der Fortschreibung bis Stichtag 2:

```
python -m rechner_pipeline.bestand.cli_report \
    --portfolio faelle/<fall>/abgeleitet/bestand-nach/bestand_gesamt.parquet \
    --historie  faelle/<fall>/abgeleitet/bestand-nach/historie.parquet \
    --ledger    faelle/<fall>/abgeleitet/bestand-nach/ledger.parquet \
    --scheiben  faelle/<fall>/abgeleitet/bestand-nach/scheiben.parquet \
    --merkmale  faelle/<fall>/abgeleitet/bestand/merkmale.parquet \
    --config <bestand-config>.toml \
    --bis <stichtag-2> --out <bericht-nach>.html
```

Zwingende Reihenfolge und Werte: `stichtag_2 > stichtag_1`; VOR aus dem
Uebernahmebestand bis Stichtag 1, NACH aus dem fortgeschriebenen
Gesamtbestand bis Stichtag 2. Die Suite liefert die vollstaendige
Zwei-Stichtags-Pruefung; A-M4 bindet die Berichtdateien, prueft aber
nicht automatisch deren fachliche HTML-Semantik. Den Betriebsbericht mit
`--berichtsstichtag` aus Stufe 1b nicht als Fallbericht-Aufruf
wiederverwenden (Anker `fortschreibung`).

<a id="abnahmebericht"></a>
## Abnahmebericht

Der Migrationsabnahmebericht ist die Entscheidungsvorlage, keine Abnahme:

```
python -m rechner_pipeline.gates.abnahmebericht --fall faelle/<fall> --suite <suite>.json --titel "..." --stichtag-1 <iso> --stichtag-2 <iso> --spec <transformation>.spec.json --transformation-ergebnis <ergebnis>.json --bestandsbericht-vor <pfad> --bestandsbericht-nach <pfad>
```

Alle vier nach der Suite genannten Artefakte sind Pflicht. Zeilenverlust,
Transformationbefunde und nicht entschiedene Konflikte erzeugen einen
roten Bericht und einen blockierenden Exit-Code. Suite, Pflichtartefakte,
HTML-Ausgabe und Gate-Ledger muessen paarweise verschiedene Dateien sein;
Pfad- und Hardlink-Aliase sind keine getrennten Belege. Ablage mit
`--fall`: `<fall>/abgeleitet/berichte/migrationsabnahme.html`, Ledger
unter `<fall>/abgeleitet/diagnostics`. Das gruene
`abnahmebericht.gate.json` bindet P-B1, Suite, Fuehrungsprobe und
HTML-Bericht an Eingang, A-Box, System, den von P-B1 benannten Bestand
und beide Stichtage; ohne diese konsistente Bindung darf A-M4 im
Bestands-Scope nicht angenommen werden. Im Bestands-Scope zieht das
Kommando das P-B1-Ledger automatisch aus
`<fall>/abgeleitet/diagnostics/bestand_validate.gate.json`
(abweichend: `--pb1-ledger`); es bindet die Spez der Generation und
verweigert jeden Beleg der Bestandsstrecke, der andere Regeln nennt.
