# Den zweiten Baldrian-Lauf nachfahren

> **Historisch.** Lauf 2 ist durch Fall 3 ersetzt. Diese Anleitung braucht
> ein Paket, das nicht im Repository liegt; sie richtete sich an die
> Beteiligten des Laufs. Was sich heute aus dem Repository allein
> nachfahren lässt, ist Fall 3 (siehe [README](../../README.md),
> Schnellstart, und [pakete/](../../pakete/README.md)).

Kurzanleitung für alle, die den Lauf vom September mit dem Repository und
dem Paket des Laufs wiederholen wollen. Wer den alten Lauf exakt sehen
will, findet hier den Stand, die Umgebung und den Ablauf.

## Der Stand

Alle fünf Zeichnungen des Laufs (A-Q1 bis A-M4, 2. September 2026) liegen
auf dem Commit

    4b1abf048ac84bfeecce12a67f18983648990799   (Kern 3.3.0)

Der Hauptzweig enthält diesen Commit seit dem Merge 96588b8 (6. September).
Der Stand 1dc736b (8. September), mit dem außerhalb des Programms zuerst
gerechnet wurde, liefert dieselben Kennzahlen, aber mit anderen Optionen;
die Kommandos unten gelten für 4b1abf04. Die Snapshots des Falls wurden
später zweimal neu gezeichnet (7. und 20. September); am Lauf selbst
ändert das nichts.

## Was du brauchst

Das Paket `baldrian-lauf2-stufe1-paket`. Im Repository liegt es nicht, weil
der Fall-Arbeitsbereich nicht versioniert ist. Es
enthält alles, was im Lauf ein Agent oder ein Mensch erzeugt hat: die
A-Box mit den vierzehn entschiedenen Diskrepanzen, Spez und Fachspez, die
Vorverdichtung der Quellen, die Transformationsvorschrift für den
Bestandsabzug und die Config des Lauftags. Der Rest des Laufs ist
Kommando und braucht keinen Agenten.

Dazu einen eigenen Freigabeschlüssel und eine Zeichnungsordnung (bei
4b1abf04 noch nach Schema 1). Beides auf dem Host anlegen, neben dem
Klon, bevor ein Container startet:

    git clone https://github.com/bartlmac/rechner-pipeline.git
    mkdir -p sicher && chmod 700 sicher
    (umask 077; head -c 32 /dev/urandom > sicher/plv-aktuar.key)
    FP=$(sha256sum sicher/plv-aktuar.key | cut -c1-64)
    printf '{"schema_version": 1, "rollen": {"plv-aktuar": {"schluessel_sha256": "%s", "gates": ["A-Q1", "A-M1", "A-M2", "A-M3", "A-M4"]}}}\n' "$FP" > sicher/zeichnungsordnung.json

## Die Umgebung

Der Container aus `ONBOARDING.md` ist der Weg. Er bringt die Abhängigkeiten
mit, der Code kommt aus dem ausgecheckten Baum. Das Image einmal auf dem
Hauptzweig bauen (der hat alle Pins, auch pypdf, das bei 4b1abf04 noch in
keiner Pin-Datei stand), dann den alten Stand holen (`git checkout`) und den
Container mit Baum, Schlüsselverzeichnis und Paket starten:

    cd rechner-pipeline
    docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev .
    git checkout 4b1abf048ac84bfeecce12a67f18983648990799
    docker run --rm -it -v "$PWD":/workspace -v "$PWD/../sicher":/sicher:ro -v "<paket>":/paket:ro rechner-pipeline-dev bash

Im Container heißt der Interpreter `python`; der Einstieg installiert das
Paket aus `/workspace`, das Schlüsselverzeichnis liegt unter `/sicher`
(von `/workspace` aus also `../sicher`), das Paket unter `/paket`. Unter
Windows läuft das in WSL 2 mit Docker Desktop, der Baum muss im
Linux-Dateisystem liegen (Details in `ONBOARDING.md`). Ohne Docker tut es
auch ein venv im Klon: `python3 -m venv .venv`, `pip install -r
requirements-dev.txt`, `pip install -e . --no-deps`,
`pip install pypdf==6.16.2`; dann ist `<paket>` der Pfad des ausgepackten
Pakets auf dem Host.

## Der Ablauf

Das Skript im Paket erledigt alles: Fall anlegen, die sechzehn
Lieferdateien registrieren, Paket einlegen, P-Q3, A-Q1 zeichnen, Golden
Master, Übernahme, Schichtbeleg, die drei aktuariellen Tests,
Migrationssuite, Fortschreibung, Berichte, Abnahmebericht und die
Zeichnungen A-M1 bis A-M4. Aufruf aus `/workspace` im Container:

    bash /paket/wiederholen.sh /paket ../sicher/plv-aktuar.key ../sicher/zeichnungsordnung.json

Es läuft unter einer Minute. Am Ende druckt es die Kennzahlen; das
vollständige Protokoll liegt in `faelle/baldrian-lauf2-w/wiederholen.log`.
Unterwegs erscheinen Warnungen „Anfangszustand nicht ableitbar“ für fünf
beitragsfrei gelieferte Verträge ohne Ankerwert; sie gehören zum Lauf und
ändern die Kennzahlen nicht. Wer die einzelnen Kommandos sehen will, liest
das Skript. Diese Werte müssen herauskommen:

| Schritt | Lauf vom 2. September 2026 |
|---|---|
| Golden Master (P-K1) | 616 Werte, 0 Abweichungen |
| Übernahme | 834 Verträge, `bestand.parquet` beginnt mit c31b5b71 |
| Stichtagstest A-M1 | 100/100, größtes Residuum 0,022 EUR |
| Verlaufstest A-M2 | 100/100, 0,021 EUR |
| Geschäftsvorfalltest A-M3 | 166/166, 0,010 EUR |
| Migrationssuite | 834/834, 2508 Prüfungen, 0,0315 EUR |
| Abnahmebericht | bestanden, `migrationsabnahme.html` beginnt mit e7fa67f0 |

Die Residuen kommen bit-gleich heraus, die beiden Dateien byte-gleich. Wir
haben das in frischen Klonen nachgemessen, und ein Dritter hat den
Ablauf danach in einem frischen Klon nachgefahren.

## Zwei Policen

Für 7000396 und 7000679 hat der Lauf die dokumentierte Arbeits-Lesart 0,60
des Aktuars verwendet (alle drei Tarifstufen ergeben an den Prüfpunkten
dasselbe; Abschlussbericht, Abschnitt 5). Das Skript gibt sie mit.

## Was anders aussieht als am Lauftag

- Die Belege tragen `branch HEAD` und `dirty nein` statt `fallbericht` und
  `ja`, dazu eigene Zeitstempel. Sonst sind sie gleich.
- Das Übernahme-Ledger weicht ab. Am Lauftag wurde `bestand/` vor der
  Zinsentscheidung in A-Q1 erzeugt (1,75 % statt 1,25 %); die Wiederholung
  liest die gezeichnete Spez. Die Prüfstrecke ist davon unberührt. Aus
  demselben Grund trägt die Config im Paket für die TG2015 noch
  `zins = 0.0175` (Korrektur 24 vom 7. September).
- Die Snapshots sind mit deinem Schlüssel gezeichnet.

## Der eigene Bestand

Die Pfefferminzia hat keinen gelieferten Bestand; er wird aus der Config
erzeugt und ist deterministisch. Der Bestand vor der Übernahme (3130
Verträge, Horizont 2046), ebenfalls auf 4b1abf04 (auf dem Hauptzweig
verlangt die Fortschreibung seit ADR-020 einen Zugangsstrom):

    python -m rechner_pipeline.bestand.cli_fortschreibung --config configs/bestand_gesamt.toml --bis 2046-01-01 --out-dir runs/bestand-vor

Ergebnis: 3130 Verträge, `bestand.parquet` beginnt mit 740ecdde. Den
KLV-Bestand zum Stichtag (2220 Verträge) baut das Skript im Schritt
Fortschreibung selbst; einzeln:

    python -m rechner_pipeline.bestand.cli_fortschreibung --config configs/bestand_klv.toml --bis 2026-01-01 --neuzugang-ab 2026-01-01 --out-dir runs/bestand-klv
