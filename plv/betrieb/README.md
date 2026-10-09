# Laufzeitumgebung des PLV-Tagesbetriebs

Dieses Verzeichnis beschreibt den Dauerbetrieb der Pfefferminzia LV (PLV) in
einem Container: Image, Compose, Timer. Die Laufzeit läuft unter
`~/apps/plv` aus einem Image, das aus diesem Repository gebaut wird
(Fachkonzept
[`docs/simulation/tagesbetrieb.md`](../../docs/simulation/tagesbetrieb.md),
Abschnitt 8). Dieses Verzeichnis liefert die Bausteine; die Laufzeit selbst
ist kein Inhalt des Repositorys.

Zum Ausprobieren braucht es kein Docker:
`werkzeuge/welt/laufzeit_aufstellen.sh` stellt eine Welt mit Schlüsseln,
Ordnung, Linie und Ablage auf ([werkzeuge/welt/README.md](../../werkzeuge/welt/README.md)).
Die `python -m`-Kommandos unten laufen auf dem Rechner der Laufzeit in einem
Klon auf dem Commit des Image-Tags, mit `.venv/bin/python` (siehe
„`--repo-root` ist der Baum des Pakets, das rechnet“).

| Datei | Zweck |
|---|---|
| `Dockerfile` | das Image: `python:3.11-slim`, Installation exakt wie die CI, kein Entwicklungswerkzeug, unprivilegierter Benutzer |
| `compose.yml` | ein Dienst `tageslauf`, Volume `daten/`, kein Netz |
| `env.beispiel` | Vorlage für `.env`: Image-Tag, Owner, Digest, Zeitzone, Verzeichnis des Betriebsschlüssels; keine Geheimnisse |
| `tageslauf.service`, `tageslauf.timer` | systemd `--user`: täglich 23:00, `Persistent=true` |
| `.github/workflows/plv-image.yml` | baut bei einem Push auf `main`, der `src/`, `requirements.txt`, `pyproject.toml` oder `plv/betrieb/` ändert, das Image `ghcr.io/<owner>/rechner-pipeline-plv` mit den Tags `latest` und den ersten zwölf Stellen des Commits |

## Ablage unter `~/apps/plv/daten`

| Verzeichnis | Inhalt | Schutz |
|---|---|---|
| `configs/bestand.toml` | die Config der PLV — eine Kopie von `plv/configs/bestand_gesamt.toml`; ihr SHA-256 steht in jedem Protokolleintrag. Eine Änderung im Repository berührt sie nicht; eine geänderte Kopie hält den Tageslauf an (Exit 2), bis die Ablage neu aufgesetzt ist (siehe „Config nachziehen“) | vom Menschen gepflegt, nur über das Neuaufsetzen |
| `uebernahme/<fall>/` | je Migrationsfall ein Zugangsstand mit `eingang.json` (Fallname, Stichtag, Snapshot-Hash, SHA-256 je Datei), bei der Registrierung mit dem Betriebsschlüssel gezeichnet (Schema 3), daneben `zugangsabnahme.json` (die geprüfte Zugangsabnahme A-B2, ADR-022) | unantastbar wie ein Fall-Eingang; jede Datei wird beim Lesen gegen ihre Summe gehalten |
| `stand/` | Symlink auf den geführten Stand (`stand-<manifest-kennung>/`; der Pfad `daten/stand/` führt durch den Symlink dorthin): die sechs Ausgaben der Fortschreibung, `laufmanifest.json`, ggf. `merkmale.parquet` und `verankerung.parquet` der Übernahmen. Der Stand ist die gebuchte Sicht: Ereignisse mit Buchungstag nach heute (Meldeverzug, Werktagsregel) stehen noch nicht darin und kommen an ihrem Buchungstag, damit Stand, Seite und Journal dasselbe sagen | wechselt nur durch einen grünen Lauf, in einem atomaren Schritt (Symlink-Tausch; es gibt keinen Moment ohne Stand); das alte Verzeichnis wird danach entfernt |
| `lauf.lock` | Prozess-Sperre: zwei gleichzeitige Läufe auf derselben Ablage gibt es nicht, der zweite bricht sofort ab; ebenso der `seite`-Befehl (Rendern und Export) neben einem laufenden Tageslauf | — |
| `journal/tagesjournal.parquet` | die Buchungstage, nur angefügt | Bijektion zum Ledger wird bei jedem Lauf geprüft |
| `journal/protokoll.jsonl` | eine JSON-Zeile je Lauf, verkettet und mit dem Betriebsschlüssel gezeichnet (Schema 3); Einzelheiten unter der Tabelle | nur angefügt; auch ein roter Lauf steht drin |
| `abschluesse/` | `abschluss_<Monatserster>.parquet`, festgeschrieben 0444, genau einmal (ADR-011) | nie überschrieben |
| `berichte/` | `bestandsbericht_<Monatserster>.html` je Monatsabschluss (dazu je Übernahme ein Teilbestand-Bericht, solange `teilbestand_getrennt` steht) | jederzeit neu renderbar |
| `seite/index.html` | „Bestand heute“: Kennzahlen, Neugeschäft der Woche, letzte Buchungen, Monatsabschlüsse, Übernahmen mit der Zeichnung ihrer A-M4-Annahme, dazu Banderole, Stand, Manifest-Hash und Lücken-Block. Nach jedem grünen Lauf aus Protokoll und Journal gerendert und erst nach dem Anfügen der Protokollzeile ersetzt (vorbereitet unter `seite.neu/`, nie in `seite/`): Die Seite nennt nie einen Tag, den das Protokoll nicht grün führt | jederzeit neu renderbar (unter der Lauf-Sperre; eine ältere Lesung ersetzt keine jüngere Seite); ein statischer Webserver (nicht Teil des Repositorys) liefert das Verzeichnis read-only aus |

**Das Protokoll.** Jede Zeile von `journal/protokoll.jsonl` nennt den
SHA-256 ihrer Vorgängerin; eine entfernte, veränderte oder umsortierte
Zeile bricht die Kette, und der nächste Lauf verweigert. Eine veränderte,
herabgestufte oder zweite grüne Zeile für denselben Tag hält den Lauf an.
Die letzte grüne Zeile bindet Manifest- und Journal-Hash des Stands und
trägt Tag, nachgeholte Tage, Neugeschäft, Buchungen, Bestandszahlen,
P-B1-Urteil, Manifest-Hash, Kern-Version, Image-Revision (Commit des
Baus), Image-Tag und Image-Digest. Das Entfernen der letzten Zeile ist ohne
Bezug nach außen nicht erkennbar, wenn sie rot war; eine grüne fällt beim
nächsten Lauf auf. Den Bezug nach außen liefert der Anker beim Export.
Eine vollständige letzte Zeile ohne Zeilenumbruch wird abgeschlossen,
nicht entfernt; geschnitten wird nur ein Fragment, das nie eine Zeile war.

## Einrichtung (einmalig, Mensch)

```
mkdir -p ~/apps/plv/daten/configs
cp plv/betrieb/compose.yml plv/betrieb/env.beispiel ~/apps/plv/
mv ~/apps/plv/env.beispiel ~/apps/plv/.env      # und ausfüllen
cp plv/configs/bestand_gesamt.toml ~/apps/plv/daten/configs/bestand.toml
```

**Betriebsschlüssel** (ADR-018, Nachtrag 2026-09-30). Jede Zeile des
Tagesprotokolls und jede `eingang.json` ist mit dem Schlüssel des Betriebs
gezeichnet (Rolle `betrieb/tageslauf`, Schlüsselklasse `betrieb`, leere
gates-Liste): Der Betrieb zeichnet Urheberschaft, nie ein Gate. Verwahrt wird
er wie die Rollenschlüssel der Abnahmen: beim Menschen, außerhalb von
`daten/` (sonst schriebe, wer die Ablage beschreiben kann, Zeilen und
Zeichnung gleich mit), Modus 0600, keine weiteren Hardlinks, 32 bis 4096 Byte.
Sein Fingerabdruck steht in einer Zeichnungsordnung (Schema 2) daneben:

```
mkdir -p ~/apps/plv/schluessel && chmod 700 ~/apps/plv/schluessel
head -c 32 /dev/urandom > ~/apps/plv/schluessel/betrieb.key
chmod 600 ~/apps/plv/schluessel/betrieb.key
sha256sum ~/apps/plv/schluessel/betrieb.key   # -> schluessel_sha256
# ~/apps/plv/schluessel/zeichnungsordnung.json:
# {"schema_version": 2, "rollen": {"betrieb/tageslauf":
#   {"schluessel_sha256": "<sha256>", "schluesselklasse": "betrieb", "gates": []}}}
# in .env: BETRIEBSSCHLUESSEL_DIR=/home/<user>/apps/plv/schluessel
```

`compose.yml` bindet das Verzeichnis lesend unter `/schluessel` ein. Ohne
Schlüssel läuft kein Tag (Exit 2 mit Ausweg); ein Menschen- oder
Agentenschlüssel wird abgewiesen.

**Der Linienbereich** (ADR-025; Pflicht seit dem Nachtrag 2026-10-01). Jede
Abnahme wird unter der Versionslinie der Zeichnungsordnung gezeichnet und
gegen den Stand gelesen, unter dem sie entstand; ohne Linie zeichnet kein
Gate und gründet kein Kommando des Betriebs auf einer Abnahme. Die Linie ist
nicht eingecheckt (Entscheidernamen, installationsgebundene Fingerabdrücke)
und wird im Datenbereich der Laufzeit angelegt, neben `daten/`, nicht darin:
`~/apps/plv/linie`. Sie gehört in dieselbe Sicherung wie die Schlüssel: ihr
Verlust macht jede Zeichnung unprüfbar, die ein Glied pinnt (also alle).
`ordnung/` und `entscheide/` sind nur-anfügbar, kein Kommando löscht dort.
Den Ort nennt jeder Aufruf ausdrücklich (`--linie ~/apps/plv/linie`): kein
Default, keine Umgebungsvorgabe; ein Schalter, der fehlen kann, wäre wieder
eine abschaltbare Wurzel.

```
python -m rechner_pipeline.gates.stand_belegen linie --linie ~/apps/plv/linie
python -m rechner_pipeline.gates.stand_belegen ordnung --linie ~/apps/plv/linie \
    --ordnung <ordnung-der-plv> --vorgaenger keiner
# ansehen: ~/apps/plv/linie/abgeleitet/ordnung/linie.md
```

`<ordnung-der-plv>` ist eine Zeichnungsordnung im Schema der
`zeichnungsordnung.json` oben, mit allen Rollen der Linie: `mensch/vorstand`
(`A-Z1`, `A-M6`), `mensch/rechenkern` (`A-K2`), `mensch/architektur`
(`A-O1`), `mensch/aktuariat` (`A-Q1`, `A-M1` bis `A-M4`, `A-T1`),
`mensch/betrieb` (`A-B1` bis `A-B3`) und `betrieb/tageslauf` (keine Gates).
Ein vollständiges Beispiel schreibt
`werkzeuge/welt/welt_aufstellen.sh <welt> schluessel`.

Mindert ein späteres Glied eine Rolle (Entzug eines Gates, Schlüssel- oder
Klassenwechsel, Rolle entfällt), ist je geminderter Rolle
`--fruehere-zeichnungen <rolle>=gueltig|verfallen` Pflicht; es gibt keine
Vorgabe. Erst die Folge lesen, dann anhängen: Die Vorschau rechnet für genau
dieses Glied die Änderungen, die geminderten Rollen und je Rolle die Folge
von `gueltig` und `verfallen` (bzw. der genannten Erklärung); sie schreibt
nichts, zeichnet nichts und braucht keinen Schlüssel; das Anhängen danach
nennt dieselbe Folge (`summary.fruehere_zeichnungen`, dieselben Zeilen in
`linie.md`):

```
python -m rechner_pipeline.gates.stand_belegen ordnung --linie ~/apps/plv/linie \
    --ordnung <neue-ordnung> --vorgaenger <glied_sha256 der Spitze> --vorschau
python -m rechner_pipeline.gates.stand_belegen ordnung --linie ~/apps/plv/linie \
    --ordnung <neue-ordnung> --vorgaenger <glied_sha256 der Spitze> \
    --vorstand-schluessel <schluessel-vorstand> --fruehere-zeichnungen <rolle>=gueltig
```

`gueltig` lässt gelten, was vor dem Glied gezeichnet wurde (Rollenwechsel,
Umbenennung); `verfallen` verlangt, jede frühere Abnahme der Linie dieser
Rolle neu zu zeichnen (auch die unter ihren früheren Namen und Schlüsseln,
auch wenn ein früheres Glied sie für `gueltig` erklärt hat), beim Vorstand
jeden Fallauftrag und alles, was darauf gründet. Ein Glied wird nie früher
datiert als sein Vorgänger und nie später als die Uhr des Aufrufs
(`--eingetragen-am` weglassen heißt: die Uhr). Zwei gleichzeitige Einträge
sind ausgeschlossen: Lesen der Spitze und Anhängen geschehen unter einer
Sperre (`linie/.ordnung.sperre`, bleibt liegen, kein Glied), der zweite
Aufruf wird mit „nicht die Spitze“ verweigert; ein Glied heißt nach seiner
Nummer (`ordnung/0002.json`), ein zweites derselben Nummer entsteht nicht.

Fällt `stand_belegen` beim Schreiben aus (Code `ein_ausgabe`), denselben
Aufruf wiederholen: Ein Rest von `linie.json` sperrt `linie` nicht, und
`ordnung` zieht für das schon liegende Glied nur die Sicht nach
(`bereits_vorhanden`), ohne zweites Glied.

Die Ordnung der PLV führt den Vorstand (`mensch/vorstand`, Gates `A-Z1` und
`A-M6`), die zeichnenden Rollen und die Betriebsrolle `betrieb/tageslauf`.
**Welche Kommandos die Linie verlangen**
(`betrieb.tageslauf.KOMMANDOS_MIT_LINIE`): Registrierung, Zugangsprobe,
Neuaufsetzen und Anfangsbestand (belegen, binden): sie gründen auf einer
Abnahme oder binden eine. **Der Nachtlauf nicht** (`KOMMANDOS_OHNE_LINIE`):
Er zeichnet Protokollzeilen, hält beim Eintritt nur die betriebsgezeichneten
Sätze der Registrierung und gründet auf keinem Snapshot. Seinen Schlüssel
hält er gegen die gezeichnete Bindung des Anfangsbestands: `binden` löst
unter der Linie auf, welchen Fingerabdruck die Spitze der Betriebsrolle
gibt, und zeichnet ihn in `anfangsbestand.json` (Schema 2). Folge: Ein
Wechsel des Betriebsschlüssels braucht ein Glied der Linie und eine neue
Bindung (belegen, A-B3, binden); eine Bindung nach Schema 1 wird neu
gebunden.

**Der Schlüssel des Vorstands im Ring** (seit dem Nachtrag zu Prüfrunde G in
ADR-025). Jedes Kommando, das auf der Linie gründet, prüft ihre Glieder nach
dem ersten gegen den Schlüssel, den die Spitze davor dem Vorstand gibt: Ein
Glied, das jemand mit Schreibrecht auf `linie/ordnung/`, aber ohne diesen
Schlüssel angehängt hat, wird verweigert, und darunter gründet nichts. Der
Schlüssel kommt auf demselben Weg wie jeder andere, mit dem ein Kommando
prüft: als weiterer `--freigabe-schluessel` (Datei 0600 außerhalb von
`daten/`, wie die anderen unter `~/apps/plv/schluessel/`): in
`gate_entscheid` (jede Annahme; im Fall stand er schon im Ring, der
Fallauftrag wird damit geprüft), in der Registrierung, der Zugangsprobe, dem
Neuaufsetzen und in `anfangsbestand binden`. Fehlt er, verweigert das
Kommando mit dem Ausweg, nicht still. Solange die Linie nur ihr erstes
Glied trägt, gibt es nichts zu prüfen (die Wurzel ist unsigniert). Der
Nachtlauf liest die Linie nicht und braucht den Schlüssel nicht. Grenze
(HMAC): Wer prüfen kann, kann auch zeichnen; der Schlüssel des Vorstands
liegt damit in diesen Ringen (ADR-025, ADR-026).

**`--repo-root` ist der Baum des Pakets, das rechnet** (seit dem Nachtrag zu
Prüfrunde G in ADR-025). Jedes Kommando der Gates hält den Baum unter
`--repo-root` gegen das ausgeführte Paket (Hash von `src/rechner_pipeline`)
und verweigert einen Baum mit anderem Code; der lebende Stand von Kern und
Tarifwerk und der Systemstand der Snapshots wären sonst die eines anderen
Codes. Im Image ist das `/opt/rechner-pipeline`; auf dem Host der Klon, aus
dem die `.venv` installiert ist.

**Einmaliger Schritt für eine Ablage aus der Zeit vor dem
Betriebsschlüssel.** Eine Ablage, die schon vor der Einführung des
Betriebsschlüssels geführt wurde, trägt ein Protokoll ohne gezeichnete
Zeile. Darauf verweigern Tageslauf, Export und Neuaufsetzen
(Exit 2), bis sie einmal ausdrücklich aufgeschaltet ist: Die erste
gezeichnete Zeile pinnt dann den ungezeichneten Vorlauf (Zahl und Hash der
Zeilen), neu aufgesetzt wird nichts. Am ersten noch nicht geführten Tag, bei
angehaltenem Timer:

```
systemctl --user stop tageslauf.timer
cd ~/apps/plv && docker compose run --rm tageslauf --stand /daten \
    --schluessel /schluessel/betrieb.key \
    --zeichnungsordnung /schluessel/zeichnungsordnung.json --aufschalten
systemctl --user start tageslauf.timer
```

(Angehängte Argumente ersetzen das `command` aus `compose.yml`, deshalb
stehen alle da; lokal:
`python -m rechner_pipeline.betrieb.tageslauf ... --aufschalten`.) Der
Schalter gehört nie in den Timer: Auf ein schon gezeichnetes (oder leeres)
Protokoll verweigert der Lauf mit ihm. Verweigert ein Lauf später mit „keine
gezeichnete Zeile“, ist das kein zweiter Aufschaltfall, sondern ein
Kettenbruch: jemand hat das gezeichnete Protokoll ohne Schlüssel
herabgestuft. Dann das Protokoll aus der Sicherung wiederherstellen, nicht
aufschalten; die Ablage allein kann beides nicht unterscheiden, der Anker
des nächsten Exports schon.

**Übernahme-Eingang** (je Migrationsfall, aus dem Fall-Arbeitsbereich
heraus; verlangt die Generation des Falls in `bestand.toml` und den
A-M4-Snapshot des Falls: ohne angenommene Migrationsabnahme gibt es keine
Übernahme; der Snapshot wird strukturell geprüft (Schema,
Selbstadressierung, Gate, Entscheid, Fall) und seine Freigabesignatur mit
dem Freigabeschlüssel, der außerhalb des Falls liegt. Ohne Schlüssel wird
nichts registriert: Der Tagesbetrieb nimmt nur einen Eingang mit
verifizierter Signatur an). Der Eingang kommt von außen ins Volume: Die
Kommandos laufen auf dem Betriebsrechner mit Zugriff auf den Fall, nicht im
Container; der Container hat kein Netz und liest den Eingang nur.

**Der Zugang hat drei Schritte** (ADR-022): Zugangsprobe, Zugangsabnahme
A-B2, Registrierung. Ohne angenommene A-B2 wird nichts registriert, und ein
Eingang ohne sie tritt nicht ein.

1. **Zugangsprobe**: zieht unter der Lauf-Sperre zwei Kopien der Ablage
   (das Original wird nicht beschrieben; die Kopien liegen außerhalb von
   `daten/`), registriert den Eingang in der einen und fährt beide vom
   geführten Tag über den Zugangsstichtag bis zum nächsten Monatsabschluss
   (mit `--bis` weiter, etwa bis zum Folgestichtag der Migrationssuite). Die
   Differenz der Abschlüsse „mit“ minus „ohne“ muss exakt der abgenommene
   Bestand sein: am Stichtag Anzahl, Versicherungssumme (Übernahme) und
   Jahresbeitrag (Migrationssuite) je Vertrag über den ganzen Zugang, am
   Folgetermin die Anzahl in Kraft; dazu Zugänge, Zugangsbuchungen,
   Bewegungskonto und Gleichheit von allem anderen. Deckungskapital,
   Rückkaufswert und Korrekturschicht hält sie je Vertrag gegen den
   Führungswert der Migrationssuite, am Zugangsstichtag und am
   Folgestichtag (dort ohne Verträge mit einem gebuchten Vorfall im
   Fenster). Das Soll liest die Probe nur aus den Bytes, die
   die geltenden Abnahmen pinnen (`aktuartest.json` über A-M1,
   `migrationssuite.json` über A-M4); sonst verweigert sie. Der Beleg
   `abgeleitet/berichte/zugangsprobe.json` trägt die Betriebszeichnung und
   bindet den geführten Stand der Ablage, den Eingang und die Abnahmen
   (Exit 0 bestanden, 1 nicht bestanden, 2 Bedienfehler oder
   Ein-/Ausgabefehler, auch beim Schreiben des Belegs; der feste Ort behält
   dann, was vorher dort lag). Die Kopien unter `--arbeit` sind und bleiben
   Probenkopien: Jede Protokollzeile, die die Probe dort schreibt, ist als
   Probezeile gezeichnet, und kein Tageslauf, Export, Neuaufsetzen oder
   Registrieren nimmt eine solche Ablage an, auch nicht ohne ihr
   Kennzeichen. Der Zugangsstichtag ist ein Monatserster. Die Probe hält
   ihren Code-Stand gegen die letzte grüne Protokollzeile: Image-Digest und
   Revision (soweit dort erfasst) und den Hash des Pakets; also im
   produktiven Image fahren bzw. `--image-digest` wie im Tageslauf angeben;
   jede Abweichung ist ein Befund.

```
python -m rechner_pipeline.betrieb.zugangsprobe --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 [--bis <ISO>] \
    --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-aktuariat> \
    --schluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json \
    --linie ~/apps/plv/linie [--arbeit <leeres-verzeichnis-ausserhalb-von-daten>]
```

   Die Probe liest A-M4 und den A-M1, den A-M4 pinnt; sie braucht den
   Schlüssel der Rolle, die beide signiert hat (`mensch/aktuariat`), und den
   des Vorstands für die Glieder der Linie.

2. **Zugangsabnahme A-B2**: `mensch/betrieb` zeichnet (in der Vorführung
   mit Schlüsselklasse `simulation` unter Mandat); `agent/betrieb` legt vor
   und kann nur ablehnen. Die Zeichnungsordnung des Maintainers gibt
   `mensch/betrieb` dafür `A-B2` in seine gates-Liste. Das Gate rechnet das
   Urteil der Probe nach, hält ihr Soll gegen die geltenden
   A-M1-/A-M4-Snapshots und die Dateien am festen Ort, und pinnt drei
   Belege: die Probe, den geltenden A-M4-Snapshot und den Eingang. Die
   Betriebszeichnung der Probe verifiziert es nicht (es hält den
   Betriebsschlüssel nicht) und sagt das in seiner Ausgabe; die
   Registrierung rechnet sie nach.

```
python -m rechner_pipeline.gates.gate_entscheid --fall faelle/<fall> \
    --linie ~/apps/plv/linie \
    --gate A-B2 --entscheid angenommen --entscheider "<Name>" \
    --begruendung "..." --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-aktuariat> \
    --freigabe-schluessel <schluessel-mensch-betrieb> \
    --zeichnungsordnung <ordnung-der-spitze> [--mandat <mandat>]
```

   Der Schalter steht dreifach: Mit dem Schlüssel des Vorstands prüft das
   Gate Fallauftrag und Glieder der Linie, mit dem von `mensch/aktuariat`
   die Signaturen der A-M4- und A-M1-Snapshots, auf denen das Soll der Probe
   steht, und mit dem zuletzt genannten (`mensch/betrieb`) zeichnet es
   selbst. Die Ordnung dieses Aufrufs ist die Spitze der Linie; Rolle und
   Schlüsselklasse der Snapshots hält das Gate gegen die Ordnung des Glieds,
   unter dem sie gezeichnet wurden (ADR-025). Wie jede Annahme im Fall setzt
   A-B2 den Fallauftrag voraus (ADR-026): Der Schlüssel des Vorstands steht
   deshalb im Ring.

3. **Registrierung**: auf derselben Ablage, ohne dass dazwischen ein
   Tageslauf den geführten Stand bewegt oder die Config getauscht wird, mit
   denselben Angaben wie die Probe (`--fall`, `--quelle`, Stichtag,
   Betriebsschlüssel): Die Registrierung hält ihre eigene `eingang.json` und
   den Stand der Ablage gegen die Hashes, die A-B2 bindet, und legt die
   geprüfte Abnahme als `zugangsabnahme.json` (gezeichnet) neben den
   Eingang. Den A-B2-Snapshot liest sie aus dem Gate-Beleg des Falls oder
   aus `--zugangsabnahme <sha256>`. Dieselbe Regel gilt für jede Abnahme,
   auf der der Zugang steht (A-M1, A-M4, A-B2; ADR-022, Nachtrag
   2026-10-01): Die Freigabe des Snapshots muss von einem Schlüssel stammen,
   dessen Rolle die Zeichnungsordnung für genau dieses Gate berechtigt, und
   der Snapshot muss genau diese Rolle tragen (die Rolle ist die des
   Schlüssels, nicht die behauptete); Registrierung und Zugangsprobe
   verweigern sonst. Die Ordnung unter `--zeichnungsordnung` nennt deshalb
   neben `betrieb/tageslauf` auch die Rolle mit A-B2 und die Rolle(n), deren
   Schlüssel A-M1 und A-M4 signiert haben, jeweils mit diesen Gates und
   unter demselben Namen wie die Ordnung, unter der gezeichnet wurde.
   Maßgeblich ist die Ordnung zum Zeitpunkt der Registrierung; der Eintritt
   prüft die Rollen nicht neu. Tritt der Eingang erst später ein (Stichtag
   in der Zukunft), hält der Tageslauf am Stichtag Config, Kern-Version und
   Code-Stand gegen die Abnahme: Wer dazwischen Config oder Image tauscht,
   braucht Probe und A-B2 neu.

```
python -m rechner_pipeline.betrieb.uebernahme --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 \
    --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-aktuariat> \
    --freigabe-schluessel <schluessel-mensch-betrieb> \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json \
    --linie ~/apps/plv/linie
```

Der Schalter steht dreifach, weil die Registrierung die Signaturen aller
drei Abnahmen prüft: A-M1 und A-M4 (Schlüssel von `mensch/aktuariat`) und
A-B2 (Schlüssel von `mensch/betrieb`), und die Glieder der Linie (Schlüssel
des Vorstands). Fehlt einer, verweigert sie am Snapshot bzw. Glied, das ihn
braucht („nicht bereitgestellter Schlüssel“, „nicht im Ring“). Auch die
Schlüsselklasse ist die der Ordnung: Gibt sie einer Rolle `simulation`, muss
der Snapshot das sagen und sein Mandat tragen.

Beim Eintritt, dem ersten grünen Lauf, der den Eingang aufnimmt, geführt
oder (bei einem Stichtag in der Zukunft) wartend, hält der Tageslauf die
Abnahme noch einmal gegen den Stand, auf dem er läuft. Lief die Ablage nach
der Probe weiter, verweigert er (Exit 2, der Stand bleibt). Ausweg: Der
Eingang ist nie eingetreten; ihn aus `uebernahme/` nehmen (sichern), die
Probe auf dem heutigen Stand wiederholen, A-B2 neu zeichnen und neu
registrieren. Ein roter Lauf bewegt den geführten Stand nicht.

Die Registrierung zeichnet `eingang.json` mit dem Betriebsschlüssel, über
alle Felder, auch die geprüfte Freigabesignatur der A-M4-Annahme. Sie hält
dazu die Tarifwerk-Schalter der Config gegen den Übernahmebeleg und
verweigert bei Abweichung mit dem Config-Abschnitt als Ausweg: Registriert
wird nur, was der Tageslauf annimmt.

**Image ziehen und Digest eintragen.** Der Container kennt seinen Digest zur
Laufzeit nicht (kein Netz, kein Docker-Socket); er kommt aus `.env`, vom
Menschen nach jedem Pull eingetragen. Ohne Eintrag steht im Protokoll
`nicht erfasst`: ein benannter Zustand, kein leeres Feld. Revision (Commit
des Baus) und Tag trägt das Image selbst.

```
cd ~/apps/plv && docker compose pull
docker image inspect ghcr.io/<owner>/rechner-pipeline-plv:<IMAGE_TAG> \
    --format '{{index .RepoDigests 0}}'      # -> IMAGE_DIGEST in .env
```

**Erstbefüllung.** Der erste Lauf beginnt leer: Das eigene Geschäft entsteht
Werktag für Werktag ab dem Betriebsbeginn (ADR-020), dazu nimmt der Lauf die
Übernahme-Eingänge auf. Er holt alle Tage vom Betriebsbeginn bis heute in
einem Lauf nach, und der Stand ist derselbe, als hätte der Lauf jede Nacht
stattgefunden. Das gilt auch für die Monatsabschlüsse, denn jeder wird mit
der an seinem Stichtag gebuchten Sicht gerechnet, nicht mit dem Wissen des
Lauftags. Die PLV führt seit dem 1. Juli 1994, und der Lauf schreibt jeden
Monatsabschluss seit damals fest. Das dauert rund eine Viertelstunde und
geschieht genau einmal je Ablage; jeder weitere Lauf findet die Abschlüsse
vor und rechnet sie nicht neu.

Was jeder Lauf tut, auch der nächtliche: Er zieht den Tagesstrom seit dem
Betriebsbeginn neu und schreibt den Bestand von dort bis heute fort: der
Stand entsteht jede Nacht aus derselben deterministischen Geschichte, nicht
aus dem Stand von gestern. Das kostet derzeit rund eine halbe Minute und
wächst mit der Geschichte des Unternehmens; nur die Monatsabschlüsse sind
einmalig. Vor dem Timer einmal von Hand fahren und das Protokoll lesen:

```
cd ~/apps/plv && docker compose run --rm tageslauf
tail -n 1 daten/journal/protokoll.jsonl
```

Fährt der Timer am selben Tag noch einmal (Erstbefüllung am Tag des ersten
Timers, ein Neustart), ist das kein Fehler: Der bereits geführte Tag ist ein
benannter Leerlauf: Exit 0,
`tageslauf: <Tag> bereits gefuehrt, nichts zu tun`, keine Protokollzeile,
Stand unverändert. Das gilt nur mit der Config, mit der der Tag gerechnet
wurde: Ist die Kopie inzwischen eine andere, hält auch dieser Lauf an wie
jeder andere (Exit 2, rote Protokollzeile, Stand unverändert; „Config
nachziehen“ unten). Ein Tag vor dem geführten (rückwärts) bricht mit Exit 2
ab.

**Abnahme des Anfangsbestands A-B3** (ADR-025). Der erste Lauf einer Ablage
ist ihr Aufbaulauf: Er baut den Anfangsbestand und läuft ohne Abnahme. Jeder
weitere Lauf verlangt, dass die Betriebsverantwortung (`mensch/betrieb`)
diesen Anfangsbestand abgenommen hat: die gezeichnete Bindung
`anfangsbestand.json` in der Ablage, deren Stand eine grüne Zeile dieser
Ablage ist; sonst hält der Lauf an (Exit 2, rote Protokollzeile, Ausweg in
der Meldung). Das gilt auch für eine Ablage, die schon vor dieser Regel
geführt wurde: Sie wird auf ihrem geführten Stand nachträglich abgenommen,
mit denselben drei Schritten. Also nach dem Aufbaulauf (und vor dem
Einschalten des Timers):

```
python -m rechner_pipeline.betrieb.anfangsbestand belegen --stand ~/apps/plv/daten \
    --linie ~/apps/plv/linie --schluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
# ansehen: ~/apps/plv/linie/abgeleitet/anfangsbestand/beleg.md
python -m rechner_pipeline.gates.gate_entscheid --linie ~/apps/plv/linie --gate A-B3 \
    --entscheid angenommen --entscheider "<Rolle>" --begruendung "..." --repo-root . \
    --zeichnungsordnung <ordnung-der-spitze> --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-betrieb> [--mandat <mandat>]
python -m rechner_pipeline.betrieb.anfangsbestand binden --stand ~/apps/plv/daten \
    --linie ~/apps/plv/linie --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-betrieb> \
    --schluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
```

Der Beleg bindet Tabellen, Config, Code-Stand und einen neu gefahrenen
Befund der Bestandswache P-B1 (grün ist Voraussetzung), dazu Kennzahlen;
nach einem Neuaufsetzen zeigt die Sicht die Abweichung zum zuletzt
abgenommenen Anfangsbestand (aus der Bindung im Archiv der alten Ablage).
Ist diese Bindung da, aber nicht lesbar oder nicht prüfbar (oder fehlt das
Archiv, das `neuaufsetzen.json` nennt), verweigert `belegen` mit Exit 2 und
Ausweg; „erste Abnahme“ sagt die Sicht nur, wenn es keine abgenommene
Vorgängerin gibt. A-B3 zeichnet das Gate nur, wenn die Sicht am festen Ort
die aus dem Beleg erzeugte ist (ADR-025, Nachtrag „Beleg und Sicht“); nach
einem Ausfall beim Belegen (Code `sicht` beim Zeichnen) `belegen`
wiederholen und erneut ansehen. `binden` hält den Stand des A-B3-Snapshots
per Gleichheit gegen den der Ablage: liegt zwischen Belegen und Binden ein
Lauf, verweigert es. Danach baut es den Beleg auf den Bytes der Ablage neu,
mit denselben Funktionen wie `belegen` (Bestandswache P-B1, Kennzahlen,
Vorgängerin), und hält jedes Feld gegen den gezeichneten Beleg am festen
Ort. Weicht das Urteil der Wache oder eine Kennzahl ab oder liegt dort nicht
genau der Beleg, den der Snapshot pinnt, verweigert es mit Exit 2, nennt die
Felder und bindet nichts. Ausweg: `belegen` neu fahren, A-B3 auf dem neuen
Beleg zeichnen, binden. Das Gate sieht die Ablage nicht; erst hier ist
„grün“ nachgerechnet. Eine Bindung nach Schema 2 (vor dieser Nachrechnung)
hält den Tageslauf an und wird mit denselben drei Schritten neu gebunden.
Schreibreste eines abgebrochenen `belegen` (`.beleg.json.<zufall>.tmp`)
räumt der nächste Aufruf. Der Linienbereich ist der Ort der Erstabnahme des
Zielsystems (ADR-025); `binden` liest A-B3 gegen das Glied, unter dem es
gezeichnet wurde, und verweigert, wenn die Ordnungsdatei des Betriebs der
Rolle `betrieb/tageslauf` einen anderen Schlüssel gibt als die Spitze der
Linie. Eine Zugangsprobe auf einer Ablage mit geführtem Stand verlangt die
Bindung ebenso (sie fährt den Tageslauf auf einer Kopie); auf der leeren
Ablage eines Neuaufsetzens wird der Zugang Teil des Anfangsbestands.

**Betrieb neu aufsetzen (Betriebsweg, Fachkonzept Abschnitt 8.5).** Wenn ein
Fall auf dem Entwicklerweg korrigiert und seine Übernahme neu erzeugt wurde,
setzt diese Routine die Laufzeitumgebung daraus neu auf. Sie löscht nichts:
Die alte Ablage wird zu `daten.archiv-<Zeit>` umbenannt, die neue entsteht
daneben und tritt an ihre Stelle. Vorher hält sie die Tarifwerk-Schalter der
Config gegen den Übernahmebeleg des Falls; passt das nicht, bricht sie ab
und nennt den Config-Abschnitt, der zu übernehmen ist. Timer anhalten,
Routine fahren, Erstbefüllung von Hand, Timer wieder einschalten.

Auch der Eingang der neuen Ablage braucht seine Zugangsabnahme A-B2
(ADR-022). Ihr geführter Stand ist der einer leeren Ablage mit der neuen
Config; die Zugangsprobe läuft deshalb auf einem leeren Verzeichnis, das nur
`configs/bestand.toml` trägt (dieselben Bytes wie die neue Config), danach
wird A-B2 gezeichnet und der Snapshot mit `--zugangsabnahme` übergeben. Ohne
A-B2 baut die Routine nichts auf. Ein neues Ankerverzeichnis gehört zur
neuen Ablage: Die alte Ankerreihe bezeugt Zeilen eines Protokolls, das jetzt
im Archiv liegt.

```
systemctl --user stop tageslauf.timer
python -m rechner_pipeline.betrieb.neuaufsetzen --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 \
    --freigabe-schluessel <schluessel-vorstand> \
    --freigabe-schluessel <schluessel-mensch-aktuariat> \
    --freigabe-schluessel <schluessel-mensch-betrieb> \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json \
    --linie ~/apps/plv/linie --zugangsabnahme <sha256-des-a-b2-snapshots>
cd ~/apps/plv && docker compose run --rm tageslauf      # Aufbaulauf
# Abnahme des Anfangsbestands A-B3: belegen, zeichnen, binden (siehe oben)
python -m rechner_pipeline.betrieb.seite --stand ~/apps/plv/daten \
    --paket <paket> --anker faelle/<fall>/abgeleitet/anker \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
systemctl --user start tageslauf.timer
```

**Wenn die Routine abbricht.** Fällt sie vor dem Tausch aus (an jeder
Schreibstelle zwischen dem Anlegen der Vorbereitung und dem Archivieren der
alten Ablage, etwa beim Anlegen von `configs`, beim Schreiben der Provenienz
oder beim Archivieren selbst), ist nichts bewegt: Sie räumt ihre eigene
Vorbereitung `daten.neu-<Zeit>` ab und sagt das in der Meldung (Exit 2; wo
das Abräumen nicht gelingt, nennt sie den Rest). Derselbe Aufruf liefert
danach das Ergebnis des ungestörten Laufs.

Endet der Prozess an dieser Stelle hart (Stromausfall, `kill -9`: nach dem
Anlegen der Vorbereitung, vor der ersten Umbenennung), kann sie nichts mehr
abräumen: `daten` steht unverändert, daneben liegt `daten.neu-<Zeit>`. Das
ist nie still. Jeder Aufruf, der die Ablage betritt (Tageslauf,
Registrierung, Zugangsprobe, Anfangsbestand, Export), hält dann mit Exit 2
an und nennt die Vorbereitung, auch der Timer: Ob die Ablage ersetzt werden
soll, entscheidet der Betrieb, nicht der nächste Lauf; verpasste Tage holt
der Tageslauf danach nach. Ausweg: dieselbe Routine erneut fahren; sie
entfernt ihre nie veröffentlichte Vorbereitung (und sagt das), bevor sie neu
aufbaut, auch mit festem `--archiv`. Ist das Neuaufsetzen nicht mehr
gewollt, die genannte Vorbereitung von Hand entfernen. Grenze: Im Container
sieht der Tageslauf nur `daten`, nicht dessen Geschwister; der Timer hält
dort also nicht an. Den Rest nennt dann der nächste Aufruf auf dem Host
(Anfangsbestand, Registrierung, Zugangsprobe, Export, Neuaufsetzen); nach
einem Abbruch der Routine deshalb vor dem Timer `ls ~/apps/plv` ansehen.
„Nie veröffentlicht“ steht fest, wenn ihre Provenienz fehlt, nicht lesbar
ist oder ein Archiv nennt, das es nicht gibt, und kein Journal in ihr liegt.
Nennt sie ein Archiv, das es gibt, liegt ein Journal darin oder trägt sie
einen anderen Namen als `daten.neu-<JJJJMMTTTHHMMSSZ>`, entfernt niemand
etwas: Alle Aufrufe halten an, auch die Routine, und die Meldung verlangt,
von Hand zu klären, welche Ablage gilt.

Endet die Routine zwischen ihren zwei Umbenennungen (Stromausfall, Abbruch),
fehlt `daten` kurz. Der Container legt es dann nicht leer an
(`create_host_path: false`), sondern bricht ab; dieselbe Routine erneut
gefahren vollendet den Tausch aus dem fertigen Aufbau, statt neu zu
beginnen.

**Reihenfolge des Hochziehens** (gemessen am Code: was verlangt was). Mit
angehaltenem Timer:

1. **Neues Image** ziehen und den Digest eintragen (oben). Der Code-Stand
   steht in jeder Protokollzeile; die Zugangsprobe hält ihren eigenen
   dagegen.
2. **Linie** anlegen bzw. bereitstellen (oben) und die Ordnung der Spitze
   eintragen; ohne sie zeichnet kein Gate (`gate_entscheid`) und läuft
   keines der Kommandos unten.
3. Im Fall: **Fallauftrag** (A-M6, ADR-026) und die Abnahmen bis A-M4,
   unter der Linie gezeichnet.
4. **Zugangsprobe und A-B2** je Eingang auf der neuen Config: auf einem
   leeren Verzeichnis, das nur die neue `configs/bestand.toml` trägt
   (dieselben Bytes), dann A-B2 zeichnen. Das Neuaufsetzen registriert nur
   mit geltender A-B2.
5. **Neu aufsetzen** (`--linie`, `--zugangsabnahme`). Es legt die alte
   Ablage selbst als `daten.archiv-<Zeit>` ab, bevor die neue an ihre Stelle
   tritt; das Archiv ist Teil dieses Schritts, kein eigener am Ende.
6. **Aufbaulauf** (`docker compose run --rm tageslauf`): Er läuft ohne
   Abnahme und erzeugt erst den geführten Stand, den A-B3 abnimmt.
7. **Anfangsbestand** belegen, A-B3 zeichnen, binden (oben); vorher
   verweigert jeder weitere Lauf.
8. Export (`betrieb.seite`) mit neuem Ankerverzeichnis, Timer einschalten.

**Config nachziehen** (etwa die Annahmen für Beitragsherabsetzung und
Teilkündigung vom 2026-10-01, `docs/simulation/erfahrungsannahmen.md`
Abschnitt 4). Die Ablage führt ihre eigene Kopie; das Repository ändert sie
nicht. Eine neue Config gilt von Beginn der Simulation an: Jeder Lauf
rechnet die Geschichte ab 1994 neu, die neuen Raten treffen also auch Jahre,
deren Monatsabschlüsse festgeschrieben sind und deren Buchungen im Journal
stehen: eine bestehende Ablage reproduziert danach nicht mehr. Der
Tageslauf hält deshalb an, sobald die Kopie nicht mehr die ist, mit der der
letzte grüne Tag gerechnet wurde (Config-Hash der Protokollzeile). Er endet
dann mit Exit 2, Stand und Journal bleiben, und eine rote Protokollzeile
nennt beide Hashes. Das gilt auch für eine Änderung ohne Wirkung und auch
dann, wenn der bereits geführte Tag zur Kontrolle noch einmal gefahren wird:
Jeder solche Lauf schreibt seine rote Zeile; mit der zurückgesetzten Config
läuft derselbe Tag wieder ohne Wirkung und ohne Zeile. Die Ablage wird neu
aufgesetzt, nicht nachträglich umgerechnet:

1. Zugangsprobe auf einem leeren Verzeichnis, das nur die neue Config als
   `configs/bestand.toml` trägt, und A-B2 darauf zeichnen (wie oben).
2. Mit angehaltenem Timer
   `neuaufsetzen ... --config <neue bestand.toml> --zugangsabnahme <sha256>`
   (Kommando oben), dann Erstbefüllung (rund eine Viertelstunde) und Export
   mit einem neuen Ankerverzeichnis.

Folgen: Die alte Ablage liegt mit Journal, Protokollkette, Abschlüssen und
Berichten unter `daten.archiv-<Zeit>`; die neue Protokollkette beginnt neu;
jeder Monatsabschluss seit 1994 wird mit der neuen Config neu
festgeschrieben, und die Vorzeigeseite zeigt ab dem nächsten Paket die neuen
Zahlen. Wer beim alten Stand bleiben will, setzt die Kopie auf die Config
zurück, mit der das Protokoll gerechnet hat.

**Timer:**

```
mkdir -p ~/.config/systemd/user
cp plv/betrieb/tageslauf.service plv/betrieb/tageslauf.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tageslauf.timer
loginctl enable-linger "$USER"     # der Timer läuft auch ohne Sitzung
```

## Betrieb

* **Jede Nacht 23:00** führt der Lauf den heutigen Tag; verpasste Nächte
  holt der nächste Lauf nach (`nachgeholt` im Protokoll).
* **Exit-Codes des Tageslaufs:** 0 grün; 2 Aufruf oder Eingang verweigert,
  mit Ausweg; 3 Wache P-B1 rot; 4 ein Fehler nach der Wache, etwa beim
  Schreiben von Journal oder Abschluss. Jeder rote Lauf hat eine
  Protokollzeile.
* **Rot heißt: nicht übernommen.** Fällt die Wache P-B1, bleibt der gestrige
  Stand der geführte, der Befund steht im Protokoll, Exit 3. Ursache
  beheben, denselben Tag erneut fahren. Eine geänderte Config ist kein
  solcher Fall: Sie hält den Lauf schon vor der Fortschreibung an (Exit 2,
  siehe „Config nachziehen“).
* **Update** = neuer `IMAGE_TAG` in `.env`, `docker compose pull`, Digest
  eintragen. Der erste Lauf mit neuem Image protokolliert den Wechsel.
  Wechselt die Kern-Version, weisen die Abschluss-Kontrollen
  (`bestand.cli_abschluss --pruefen`) die Abweichungen aus; der
  Tagesbetrieb schreibt nichts um.
* **Sichtung:** `daten/seite/index.html` zeigt den Bestand heute, der
  Bestandsbericht des letzten Monatsabschlusses liegt unter
  `daten/berichte/`. Die öffentliche Seite bleibt eine vom Menschen
  veröffentlichte Momentaufnahme (`werkzeuge/README.md`): Ihre Quelle ist
  das **Stands-Paket**, das der Mensch exportiert und dem Auftritt übergibt;
  nichts wird automatisch veröffentlicht. Das Paket trägt seine Belege
  (Protokoll mit Kette, Manifest, Berichte, je mit SHA-256); der Auftritt
  prüft sie und veröffentlicht kein Paket, das sich selbst widerspricht.

  Das genügt aber nicht: Die Protokollkette bindet jede Zeile an ihre
  Vorgängerin und schützt damit alles außer der letzten, und genau aus der
  letzten leitet `stand.json` ab. Wer beide zusammen umschreibt, bekommt ein
  Paket, das sich selbst bestätigt. Deshalb schreibt der Export einen Anker
  in den Fall-Datenraum (den der Tagesbetrieb nicht anfasst) und nennt ihn
  im Paket; der Auftritt prüft dagegen. Ein Export ohne `--anker` wird
  abgelehnt.

  Vor dem Export prüft er jede Protokollzeile gegen den Betriebsschlüssel
  (`--betriebsschluessel`; ist `--schluessel` selbst der Betriebsschlüssel,
  genügt er). Ohne ihn gibt es kein Paket. Der Auftritt hält keinen
  Schlüssel: Er prüft Kette, Schema-Folge, Form der Zeichnung und Vorlauf
  und weist die Signatur als „nicht prüfbar“ aus, statt sie zu behaupten.

  ```
  python -m rechner_pipeline.betrieb.seite --stand ~/apps/plv/daten \
      --paket runs/stands-paket --anker faelle/<fall>/abgeleitet/anker \
      --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
      --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
  python werkzeuge/auftritt.py --fall faelle/<fall> --name <kurzname> \
      --abzug ... --stands-paket runs/stands-paket \
      --anker faelle/<fall>/abgeleitet/anker/anker.jsonl
  ```

Lokal, ohne Container (Entwicklerrechner), tut dasselbe:

```
python -m rechner_pipeline.betrieb.tageslauf --stand <daten> [--heute 2026-09-05] \
    --schluessel <betriebsschluessel> --zeichnungsordnung <ordnung>
```
