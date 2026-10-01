# Laufzeitumgebung des PLV-Tagesbetriebs

Die Pfefferminzia LV (PLV) laeuft nicht auf einem Entwicklerrechner,
sondern unter `~/apps/plv` aus einem Container-Image, das aus diesem
Repository gebaut wird (Fachkonzept
[`docs/simulation/tagesbetrieb.md`](../../docs/simulation/tagesbetrieb.md),
Abschnitt 8). Dieses Verzeichnis liefert die Bausteine; die
Laufzeitumgebung selbst ist kein Repo-Inhalt.

| Datei | Zweck |
|---|---|
| `Dockerfile` | das Image: `python:3.11-slim`, Installation exakt wie die CI, kein Entwicklungswerkzeug, unprivilegierter Benutzer |
| `compose.yml` | ein Dienst `tageslauf`, Volume `daten/`, kein Netz |
| `env.beispiel` | Vorlage fuer `.env`: Image-Tag, Owner, Digest, Zeitzone, Verzeichnis des Betriebsschluessels; keine Geheimnisse |
| `tageslauf.service`, `tageslauf.timer` | systemd `--user`: taeglich 23:00, `Persistent=true` |
| `.github/workflows/plv-image.yml` | baut bei jedem Push auf `main` das Image `ghcr.io/<owner>/rechner-pipeline-plv` mit den Tags `latest` und Commit-Kurzhash |

## Ablage unter `~/apps/plv/daten`

| Verzeichnis | Inhalt | Schutz |
|---|---|---|
| `configs/bestand.toml` | die Config der PLV — eine Kopie von `configs/bestand_gesamt.toml`; ihr SHA-256 steht in jedem Protokolleintrag. Eine Aenderung im Repository beruehrt sie nicht; eine geaenderte Kopie haelt den Tageslauf an (Exit 2), bis die Ablage neu aufgesetzt ist (siehe "Config nachziehen") | vom Menschen gepflegt, nur ueber das Neuaufsetzen |
| `uebernahme/<fall>/` | je Migrationsfall ein Zugangsstand mit `eingang.json` (Fallname, Stichtag, Snapshot-Hash, SHA-256 je Datei), bei der Registrierung mit dem Betriebsschluessel gezeichnet (Schema 3), daneben `zugangsabnahme.json` (die gepruefte Zugangsabnahme A-B2, ADR-022) | unantastbar wie ein Fall-Eingang; jede Datei wird beim Lesen gegen ihre Summe gehalten |
| `stand/` | Symlink auf den gefuehrten Stand (`stand-<manifest-kennung>/`; der Pfad `daten/stand/` fuehrt durch den Symlink dorthin): die sechs Ausgaben der Fortschreibung, `laufmanifest.json`, ggf. `merkmale.parquet` und `verankerung.parquet` der Uebernahmen. Der Stand ist die GEBUCHTE Sicht: Ereignisse mit Buchungstag nach heute (Meldeverzug, Werktagsregel) stehen noch nicht darin und kommen an ihrem Buchungstag, damit Stand, Seite und Journal dasselbe sagen | wechselt nur durch einen gruenen Lauf, in EINEM atomaren Schritt (Symlink-Tausch; es gibt keinen Moment ohne Stand); das alte Verzeichnis wird danach entfernt |
| `lauf.lock` | Prozess-Sperre: zwei gleichzeitige Laeufe auf derselben Ablage gibt es nicht, der zweite bricht sofort ab; ebenso der `seite`-Befehl (Rendern und Export) neben einem laufenden Tageslauf | — |
| `journal/tagesjournal.parquet` | die Buchungstage, nur angefuegt | Bijektion zum Ledger wird bei jedem Lauf geprueft |
| `journal/protokoll.jsonl` | eine JSON-Zeile je Lauf, verkettet (jede Zeile nennt den SHA-256 ihrer Vorgaengerin; eine entfernte, veraenderte oder umsortierte Zeile bricht die Kette, und der naechste Lauf verweigert) und mit dem Betriebsschluessel gezeichnet (Schema 3; eine veraenderte, herabgestufte oder zweite gruene Zeile fuer denselben Tag haelt den Lauf an). Das Entfernen der LETZTEN Zeile ist ohne Bezug nach aussen nicht erkennbar, wenn sie rot war — eine gruene bindet Manifest und Journal des Stands und faellt beim naechsten Lauf auf; den Bezug nach aussen liefert der Anker beim Export. Eine vollstaendige letzte Zeile ohne Zeilenumbruch wird abgeschlossen, nicht entfernt; geschnitten wird nur ein Fragment, das nie eine Zeile war. Die letzte gruene Zeile bindet Manifest- und Journal-Hash des Stands: Tag, nachgeholte Tage, Neugeschaeft, Buchungen, Bestandszahlen, P-B1-Urteil, Manifest-Hash, Kern-Version, Image-Revision (Commit des Baus), Image-Tag und -Digest | nur angefuegt; auch ein roter Lauf steht drin |
| `abschluesse/` | `abschluss_<Monatserster>.parquet`, festgeschrieben 0444, genau einmal (ADR-011) | nie ueberschrieben |
| `berichte/` | `bestandsbericht_<Monatserster>.html` je Monatsabschluss (dazu je Uebernahme ein Teilbestand-Bericht, solange `teilbestand_getrennt` steht) | jederzeit neu renderbar |
| `seite/index.html` | "Bestand heute": Kennzahlen, Neugeschaeft der Woche, letzte Buchungen, Monatsabschluesse, Uebernahmen mit der Zeichnung ihrer A-M4-Annahme — nach jedem gruenen Lauf aus Protokoll und Journal gerendert — erst NACH dem Anfuegen der Protokollzeile ersetzt (vorbereitet wird unter `seite.neu/`, nie in `seite/`): die Seite nennt nie einen Tag, den das Protokoll nicht gruen fuehrt; mit Banderole, Stand, Manifest-Hash und Luecken-Block | jederzeit neu renderbar (unter der Lauf-Sperre; eine aeltere Lesung ersetzt keine juengere Seite); ein Caddy liefert das Verzeichnis read-only aus |

## Einrichtung (einmalig, Mensch)

```
mkdir -p ~/apps/plv/daten/configs
cp deploy/plv/compose.yml deploy/plv/env.beispiel ~/apps/plv/
mv ~/apps/plv/env.beispiel ~/apps/plv/.env      # und ausfuellen
cp configs/bestand_gesamt.toml ~/apps/plv/daten/configs/bestand.toml
```

**Betriebsschluessel** (ADR-018, Nachtrag 2026-09-30). Jede Zeile des
Tagesprotokolls und jede `eingang.json` ist mit dem Schluessel des
Betriebs gezeichnet — Rolle `betrieb/tageslauf`, Schluesselklasse
`betrieb`, leere gates-Liste: Der Betrieb zeichnet Urheberschaft, nie ein
Gate. Verwahrt wird er wie die Rollenschluessel der Abnahmen: beim
Menschen, AUSSERHALB von `daten/` (sonst schriebe, wer die Ablage
beschreiben kann, Zeilen und Zeichnung gleich mit), Modus 0600, genau ein
Hardlink, 32 bis 4096 Byte. Sein Fingerabdruck steht in einer
Zeichnungsordnung (Schema 2) daneben:

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

`compose.yml` bindet das Verzeichnis lesend unter `/schluessel` ein.
Ohne Schluessel laeuft kein Tag (Exit 2 mit Ausweg); ein Menschen- oder
Agentenschluessel wird abgewiesen.

**Der Linienbereich** (ADR-025; Pflicht seit dem Nachtrag 2026-10-01).
Jede Abnahme wird unter der Versionslinie der Zeichnungsordnung gezeichnet
und gegen den Stand gelesen, unter dem sie entstand; ohne Linie zeichnet
kein Gate und gruendet kein Kommando des Betriebs auf einer Abnahme. Die
Linie ist nicht eingecheckt (Entscheidernamen, installationsgebundene
Fingerabdruecke) und wird im Datenbereich der Laufzeit ANGELEGT, neben
`daten/`, nicht darin: `~/apps/plv/linie`. Sie gehoert in DIESELBE Sicherung
wie die Schluessel — ihr Verlust macht jede Zeichnung unpruefbar, die ein
Glied pinnt (also alle). `ordnung/` und `entscheide/` sind nur-anfuegbar,
kein Kommando loescht dort. Den Ort nennt jeder Aufruf ausdruecklich
(`--linie ~/apps/plv/linie`): kein Default, keine Umgebungsvorgabe — ein
Schalter, der fehlen kann, waere wieder eine abschaltbare Wurzel.

```
python -m rechner_pipeline.gates.stand_belegen linie --linie ~/apps/plv/linie
python -m rechner_pipeline.gates.stand_belegen ordnung --linie ~/apps/plv/linie \
    --ordnung <ordnung-der-plv> --vorgaenger keiner
# ansehen: ~/apps/plv/linie/abgeleitet/ordnung/linie.md
```

Die Ordnung der PLV fuehrt den Vorstand (`mensch/vorstand`, Gates `A-Z1`
und `A-M6`), die zeichnenden Rollen und die Betriebsrolle
`betrieb/tageslauf`. **Welche Kommandos die Linie verlangen**
(`betrieb.tageslauf.KOMMANDOS_MIT_LINIE`): Registrierung, Zugangsprobe,
Neuaufsetzen und Anfangsbestand (belegen, binden) — sie gruenden auf einer
Abnahme oder binden eine. **Der Nachtlauf nicht**
(`KOMMANDOS_OHNE_LINIE`): Er zeichnet Protokollzeilen, haelt beim Eintritt
nur die betriebsgezeichneten Saetze der Registrierung und gruendet auf
keinem Snapshot. Seinen Schluessel haelt er gegen die gezeichnete Bindung
des Anfangsbestands: `binden` loest unter der Linie auf, welchen
Fingerabdruck die Spitze der Betriebsrolle gibt, und zeichnet ihn in
`anfangsbestand.json` (Schema 2). Folge: Ein Wechsel des
Betriebsschluessels braucht ein Glied der Linie UND eine neue Bindung
(belegen, A-B3, binden); eine Bindung nach Schema 1 wird neu gebunden.

**Der Schluessel des Vorstands im Ring** (Pruefrunde G). Jedes Kommando,
das auf der Linie gruendet, prueft ihre Glieder nach dem ersten gegen den
Schluessel, den die Spitze davor dem Vorstand gibt: Ein Glied, das jemand
mit Schreibrecht auf `linie/ordnung/`, aber ohne diesen Schluessel
angehaengt hat, wird verweigert, und darunter gruendet nichts. Der Schluessel
kommt auf demselben Weg wie jeder andere, mit dem ein Kommando prueft — als
weiterer `--freigabe-schluessel` (Datei 0600 ausserhalb von `daten/`, wie
die anderen unter `~/apps/plv/schluessel/`): in `gate_entscheid` (jede
Annahme; im Fall stand er schon im Ring, der Fallauftrag wird damit
geprueft), in der Registrierung, der Zugangsprobe, dem Neuaufsetzen und in
`anfangsbestand binden`. Fehlt er, verweigert das Kommando mit dem Ausweg —
nicht still. Solange die Linie nur ihr erstes Glied traegt, gibt es nichts zu
pruefen (die Wurzel ist unsigniert). Der Nachtlauf liest die Linie nicht und
braucht den Schluessel nicht. Grenze (HMAC): Wer pruefen kann, kann auch
zeichnen — der Schluessel des Vorstands liegt damit in diesen Ringen
(ADR-025, ADR-026).

**`--repo-root` ist der Baum des Pakets, das rechnet** (Pruefrunde G).
Jedes Kommando der Gates haelt den Baum unter `--repo-root` gegen das
ausgefuehrte Paket (Hash von `src/rechner_pipeline`) und verweigert einen
Baum mit anderem Code — der lebende Stand von Kern und Tarifwerk und der
Systemstand der Snapshots waeren sonst die eines anderen Codes. Im Image ist
das `/opt/rechner-pipeline`; auf dem Host der Klon, aus dem die `.venv`
installiert ist.

**Einmaliger Schritt beim ersten Lauf nach dem Umstieg.** Eine Ablage,
die schon vor dem Betriebsschluessel gefuehrt wurde, traegt ein
Protokoll ohne gezeichnete Zeile. Darauf verweigern Tageslauf, Export
und Neuaufsetzen (Exit 2), bis sie EINMAL ausdruecklich AUFGESCHALTET
ist: Die erste gezeichnete Zeile pinnt dann den ungezeichneten Vorlauf
(Zahl und Hash der Zeilen), neu aufgesetzt wird nichts. Am ersten noch
nicht gefuehrten Tag, bei angehaltenem Timer:

```
systemctl --user stop tageslauf.timer
cd ~/apps/plv && docker compose run --rm tageslauf --stand /daten \
    --schluessel /schluessel/betrieb.key \
    --zeichnungsordnung /schluessel/zeichnungsordnung.json --aufschalten
systemctl --user start tageslauf.timer
```

(Angehaengte Argumente ersetzen das `command` aus `compose.yml`, deshalb
stehen alle da; lokal: `python -m rechner_pipeline.betrieb.tageslauf ...
--aufschalten`.)
Der Schalter gehoert NIE in den Timer: Auf ein schon gezeichnetes (oder
leeres) Protokoll verweigert der Lauf mit ihm. Verweigert ein Lauf
spaeter mit "keine gezeichnete Zeile", ist das KEIN zweiter
Aufschaltfall, sondern ein Kettenbruch — jemand hat das gezeichnete
Protokoll ohne Schluessel herabgestuft. Dann das Protokoll aus der
Sicherung wiederherstellen, nicht aufschalten; die Ablage allein kann
beides nicht unterscheiden, der Anker des naechsten Exports schon.

**Uebernahme-Eingang** (je Migrationsfall, aus dem Fall-Arbeitsbereich
heraus; verlangt die Generation des Falls in `bestand.toml` und den
A-M4-Snapshot des Falls: ohne angenommene Migrationsabnahme gibt es
keine Uebernahme; der Snapshot wird strukturell geprueft — Schema,
Selbstadressierung, Gate, Entscheid, Fall — und seine Freigabesignatur
mit dem Freigabeschluessel, der ausserhalb des Falls liegt. Ohne
Schluessel wird nichts registriert: Der Tagesbetrieb nimmt nur einen
Eingang mit verifizierter Signatur an). Der
Eingang kommt von AUSSEN ins Volume: Die Kommandos laufen auf dem
Betriebsrechner mit Zugriff auf den Fall, nicht im Container — der
Container hat kein Netz und liest den Eingang nur.

**Der Zugang hat drei Schritte** (ADR-022): Zugangsprobe, Zugangsabnahme
A-B2, Registrierung. Ohne angenommene A-B2 wird nichts registriert, und
ein Eingang ohne sie tritt nicht ein.

1. **Zugangsprobe** — zieht unter der Lauf-Sperre zwei Kopien der Ablage
   (das Original wird nicht beschrieben; die Kopien liegen ausserhalb von
   `daten/`), registriert den Eingang in der einen und faehrt beide vom
   gefuehrten Tag ueber den Zugangsstichtag bis zum naechsten
   Monatsabschluss (mit `--bis` weiter, etwa bis zum Folgestichtag der
   Migrationssuite). Die Differenz der Abschluesse "mit" minus "ohne" muss
   exakt der abgenommene Bestand sein: am Stichtag Anzahl,
   Versicherungssumme (Uebernahme) und Jahresbeitrag (Migrationssuite) je
   Vertrag ueber den ganzen Zugang, am Folgetermin die Anzahl in Kraft;
   dazu Zugaenge, Zugangsbuchungen, Bewegungskonto und Gleichheit von
   allem anderen. Das Deckungskapital steht mit dem Grund "nicht
   vergleichbar: Konvention Jahreswert vs. Monatsreserve, Entscheid offen"
   im Beleg, bis der Maintainer die Konvention entscheidet. Das Soll liest
   die Probe nur aus den Bytes, die die geltenden Abnahmen pinnen
   (`aktuartest.json` ueber A-M1, `migrationssuite.json` ueber A-M4) —
   sonst verweigert sie. Der Beleg `abgeleitet/berichte/zugangsprobe.json`
   traegt die Betriebszeichnung und bindet den gefuehrten Stand der Ablage,
   den Eingang und die Abnahmen (Exit 0 bestanden, 1 nicht bestanden, 2
   Bedienfehler oder Ein-/Ausgabefehler, auch beim Schreiben des Belegs —
   der feste Ort behaelt dann, was vorher dort lag). Die Kopien unter
   `--arbeit` sind und bleiben Probenkopien: Jede Protokollzeile, die die
   Probe dort schreibt, ist als Probezeile gezeichnet, und kein Tageslauf,
   Export, Neuaufsetzen oder Registrieren nimmt eine solche Ablage an —
   auch nicht ohne ihr Kennzeichen. Der Zugangsstichtag ist ein Monatserster. Die Probe
   haelt ihren Code-Stand gegen die letzte gruene Protokollzeile: Image-
   Digest und Revision (soweit dort erfasst) und den Hash des Pakets —
   also im produktiven Image fahren bzw. `--image-digest` wie im
   Tageslauf angeben; jede Abweichung ist ein Befund.

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
   Schluessel der Rolle, die beide signiert hat (`mensch/aktuariat`), und
   den des Vorstands fuer die Glieder der Linie.

2. **Zugangsabnahme A-B2** — `mensch/betrieb` zeichnet (in der Vorfuehrung
   mit Schluesselklasse `simulation` unter Mandat); `agent/betrieb` legt
   vor und kann nur ablehnen. Die Zeichnungsordnung des Maintainers gibt
   `mensch/betrieb` dafuer `A-B2` in seine gates-Liste. Das Gate rechnet
   das Urteil der Probe nach, haelt ihr Soll gegen die geltenden
   A-M1-/A-M4-Snapshots und die Dateien am festen Ort, und pinnt drei
   Belege: die Probe, den geltenden A-M4-Snapshot und den Eingang. Die
   Betriebszeichnung der Probe verifiziert es nicht (es haelt den
   Betriebsschluessel nicht) und sagt das in seiner Ausgabe; die
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

   Der Schalter steht zweifach: Das Gate prueft die Signaturen der A-M4-
   und A-M1-Snapshots, auf denen das Soll der Probe steht (Schluessel von
   `mensch/aktuariat`), und zeichnet selbst mit dem zuletzt genannten
   (`mensch/betrieb`). Die Ordnung DIESES Aufrufs ist die Spitze der Linie;
   Rolle und Schluesselklasse der Snapshots haelt das Gate gegen die Ordnung
   des Glieds, unter dem sie gezeichnet wurden (ADR-025). Wie jede Annahme
   im Fall setzt A-B2 den Fallauftrag voraus (ADR-026): Der Schluessel des
   Vorstands steht deshalb im Ring.

3. **Registrierung** — auf DERSELBEN Ablage, ohne dass dazwischen ein
   Tageslauf den gefuehrten Stand bewegt oder die Config getauscht wird,
   mit denselben Angaben wie die Probe (`--fall`, `--quelle`, Stichtag,
   Betriebsschluessel): Die Registrierung haelt ihre eigene `eingang.json`
   und den Stand der Ablage gegen die Hashes, die A-B2 bindet, und legt die
   gepruefte Abnahme als `zugangsabnahme.json` (gezeichnet) neben den
   Eingang. Den A-B2-Snapshot liest sie aus dem Gate-Beleg des Falls oder
   aus `--zugangsabnahme <sha256>`. Dieselbe Regel gilt fuer jede Abnahme,
   auf der der Zugang steht (A-M1, A-M4, A-B2; ADR-022, Nachtrag
   2026-10-01): Die Freigabe des Snapshots muss von einem Schluessel
   stammen, dessen Rolle die Zeichnungsordnung fuer genau dieses Gate
   berechtigt, und der Snapshot muss genau diese Rolle tragen (die Rolle
   ist die des Schluessels, nicht die behauptete) — Registrierung und
   Zugangsprobe verweigern sonst. Die Ordnung unter `--zeichnungsordnung`
   nennt deshalb neben `betrieb/tageslauf` auch die Rolle mit A-B2 und die
   Rolle(n), deren Schluessel A-M1 und A-M4 signiert haben, jeweils mit
   diesen Gates und unter demselben Namen wie die Ordnung, unter der
   gezeichnet wurde. Massgeblich ist die Ordnung zum Zeitpunkt der
   Registrierung; der Eintritt prueft die Rollen nicht neu. Tritt der Eingang erst spaeter ein (Stichtag in der
   Zukunft), haelt der Tageslauf am Stichtag Config, Kern-Version und
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
drei Abnahmen prueft: A-M1 und A-M4 (Schluessel von `mensch/aktuariat`)
und A-B2 (Schluessel von `mensch/betrieb`) — und die Glieder der Linie
(Schluessel des Vorstands). Fehlt einer, verweigert sie am Snapshot bzw.
Glied, das ihn braucht ("nicht bereitgestellter Schluessel", "nicht im
Ring"). Auch die
Schluesselklasse ist die der Ordnung: Gibt sie einer Rolle `simulation`,
muss der Snapshot das sagen und sein Mandat tragen.

Beim Eintritt — dem ersten gruenen Lauf, der den Eingang aufnimmt, gefuehrt
oder (bei einem Stichtag in der Zukunft) wartend — haelt der Tageslauf
die Abnahme noch einmal gegen den Stand, auf dem er laeuft. Lief die
Ablage nach der Probe weiter, verweigert er (Exit 2, der Stand bleibt).
Ausweg: Der Eingang ist nie eingetreten; ihn aus `uebernahme/` nehmen
(sichern), die Probe auf dem heutigen Stand wiederholen, A-B2 neu zeichnen
und neu registrieren. Ein roter Lauf bewegt den gefuehrten Stand nicht.

Die Registrierung zeichnet `eingang.json` mit dem Betriebsschluessel —
ueber alle Felder, auch die gepruefte Freigabesignatur der A-M4-Annahme.
Sie haelt dazu die Tarifwerk-Schalter der Config gegen den
Uebernahmebeleg und verweigert bei Abweichung mit dem Config-Abschnitt
als Ausweg: Registriert wird nur, was der Tageslauf annimmt.

**Image ziehen und Digest eintragen.** Der Container kennt seinen
Digest zur Laufzeit nicht (kein Netz, kein Docker-Socket); er kommt aus
`.env`, vom Menschen nach jedem Pull eingetragen. Ohne Eintrag steht im
Protokoll `nicht erfasst` — ein benannter Zustand, kein leeres Feld.
Revision (Commit des Baus) und Tag traegt das Image selbst.

```
cd ~/apps/plv && docker compose pull
docker image inspect ghcr.io/<owner>/rechner-pipeline-plv:latest \
    --format '{{index .RepoDigests 0}}'      # -> IMAGE_DIGEST in .env
```

**Erstbefuellung.** Der erste Lauf baut den Basisbestand aus der Config
(Batch bis zum Betriebsbeginn), nimmt die Uebernahme-Eingaenge auf und
holt alle Tage vom Betriebsbeginn bis heute in EINEM Lauf nach — der
Stand ist derselbe, als haette der Lauf jede Nacht stattgefunden — auch
die Monatsabschluesse, denn jeder wird mit der an SEINEM Stichtag
gebuchten Sicht gerechnet, nicht mit dem Wissen des Lauftags (Review
T24-02). Die PLV
fuehrt seit dem 1. Juli 1994: Der Batch zieht nur den Grenztag selbst
(fuenf Vertraege mit Beginn am 1. Juli), jeder weitere entsteht aus dem
Tagesstrom, und der Lauf schreibt jeden Monatsabschluss
seit damals fest. Das dauert rund eine Viertelstunde und geschieht genau
einmal je Ablage; jeder weitere Lauf findet die Abschluesse vor und
rechnet sie nicht neu.

Was JEDER Lauf tut, auch der naechtliche: Er zieht den Tagesstrom seit dem
Betriebsbeginn neu und schreibt den Bestand von dort bis heute fort — der
Stand entsteht jede Nacht aus derselben deterministischen Geschichte, nicht
aus dem Stand von gestern. Das kostet derzeit rund eine halbe Minute und
waechst mit der Geschichte des Unternehmens; nur die Monatsabschluesse sind
einmalig. Vor dem Timer einmal von Hand fahren und das Protokoll lesen:

```
cd ~/apps/plv && docker compose run --rm tageslauf
tail -n 1 daten/journal/protokoll.jsonl
```

Faehrt der Timer am selben Tag noch einmal (Erstbefuellung am Tag des
ersten Timers, ein Neustart), ist das kein Fehler: Der bereits gefuehrte
Tag ist ein benannter No-op — Exit 0, `tageslauf: <Tag> bereits gefuehrt,
nichts zu tun`, keine Protokollzeile, Stand unveraendert. Das gilt nur mit
der Config, mit der der Tag gerechnet wurde: Ist die Kopie inzwischen eine
andere, haelt auch dieser Lauf an wie jeder andere (Exit 2, rote
Protokollzeile, Stand unveraendert; "Config nachziehen" unten). Ein Tag VOR
dem gefuehrten (rueckwaerts) bricht mit Exit 2 ab.

**Abnahme des Anfangsbestands A-B3** (ADR-025). Der erste Lauf einer
Ablage ist ihr AUFBAULAUF: Er baut den Anfangsbestand und laeuft ohne
Abnahme. Jeder weitere Lauf verlangt, dass die Betriebsverantwortung
(`mensch/betrieb`) diesen Anfangsbestand abgenommen hat — die gezeichnete
Bindung `anfangsbestand.json` in der Ablage, deren Stand eine gruene Zeile
DIESER Ablage ist; sonst haelt der Lauf an (Exit 2, rote Protokollzeile,
Ausweg in der Meldung). Das gilt auch fuer eine Ablage, die schon vor dieser
Regel gefuehrt wurde: Sie wird auf ihrem gefuehrten Stand nachtraeglich
abgenommen, mit denselben drei Schritten. Also nach dem Aufbaulauf (und vor
dem Einschalten des Timers):

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
Befund der Bestandswache P-B1 (gruen ist Voraussetzung), dazu Kennzahlen;
nach einem Neuaufsetzen zeigt die Sicht die Abweichung zum zuletzt
abgenommenen Anfangsbestand (aus der Bindung im Archiv der alten Ablage).
`binden` haelt den Stand des A-B3-Snapshots per Gleichheit gegen den der
Ablage — liegt zwischen Belegen und Binden ein Lauf, verweigert es. Der
Linienbereich ist der Ort der Erstabnahme des Zielsystems (ADR-025); `binden`
liest A-B3 gegen das Glied, unter dem es gezeichnet wurde, und verweigert,
wenn die Ordnungsdatei des Betriebs der Rolle `betrieb/tageslauf` einen
anderen Schluessel gibt als die Spitze der Linie. Eine Zugangsprobe
auf einer Ablage mit gefuehrtem Stand verlangt die Bindung ebenso (sie
faehrt den Tageslauf auf einer Kopie); auf der LEEREN Ablage eines
Neuaufsetzens wird der Zugang Teil des Anfangsbestands.

**Betrieb neu aufsetzen (Betriebsweg, Fachkonzept Abschnitt 8.5).** Wenn
ein Fall auf dem Entwicklerweg korrigiert und seine Uebernahme neu erzeugt
wurde, setzt diese Routine die Laufzeitumgebung daraus neu auf. Sie
loescht nichts: Die alte Ablage wird zu `daten.archiv-<Zeit>` umbenannt,
die neue entsteht daneben und tritt an ihre Stelle. Vorher haelt sie die
Tarifwerk-Schalter der Config gegen den Uebernahmebeleg des Falls; passt
das nicht, bricht sie ab und nennt den Config-Abschnitt, der zu
uebernehmen ist. Timer anhalten, Routine fahren, Erstbefuellung von Hand,
Timer wieder einschalten:

Endet die Routine zwischen ihren zwei Umbenennungen (Stromausfall,
Abbruch), fehlt `daten` kurz. Der Container legt es dann NICHT leer an
(`create_host_path: false`), sondern bricht ab; dieselbe Routine erneut
gefahren vollendet den Tausch aus dem fertigen Aufbau, statt neu zu
beginnen. Ein neues Ankerverzeichnis gehoert zur neuen Ablage: Die alte
Ankerreihe bezeugt Zeilen eines Protokolls, das jetzt im Archiv liegt.

Auch der Eingang der neuen Ablage braucht seine Zugangsabnahme A-B2
(ADR-022). Ihr gefuehrter Stand ist der einer LEEREN Ablage mit der neuen
Config; die Zugangsprobe laeuft deshalb auf einem leeren Verzeichnis, das
nur `configs/bestand.toml` traegt (dieselben Bytes wie die neue Config),
danach wird A-B2 gezeichnet und der Snapshot mit `--zugangsabnahme`
uebergeben. Ohne A-B2 baut die Routine nichts auf.

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

**Reihenfolge des Hochziehens** (gemessen am Code: was verlangt was). Mit
angehaltenem Timer:

1. **Neues Image** ziehen und den Digest eintragen (oben). Der Code-Stand
   steht in jeder Protokollzeile; die Zugangsprobe haelt ihren eigenen
   dagegen.
2. **Linie** anlegen bzw. bereitstellen (oben) und die Ordnung der Spitze
   eintragen — ohne sie zeichnet kein Gate (`gate_entscheid`) und laeuft
   keines der Kommandos unten.
3. Im Fall: **Fallauftrag** (A-M6, ADR-026) und die Abnahmen bis A-M4 —
   unter der Linie gezeichnet.
4. **Zugangsprobe und A-B2** je Eingang auf der neuen Config: auf einem
   leeren Verzeichnis, das nur die neue `configs/bestand.toml` traegt
   (dieselben Bytes), dann A-B2 zeichnen. Das Neuaufsetzen registriert nur
   mit geltender A-B2.
5. **Neu aufsetzen** (`--linie`, `--zugangsabnahme`). Es legt die alte
   Ablage SELBST als `daten.archiv-<Zeit>` ab, bevor die neue an ihre Stelle
   tritt — das Archiv ist Teil dieses Schritts, kein eigener am Ende.
6. **Aufbaulauf** (`docker compose run --rm tageslauf`): Er laeuft ohne
   Abnahme und erzeugt erst den gefuehrten Stand, den A-B3 abnimmt.
7. **Anfangsbestand** belegen, A-B3 zeichnen, binden (oben) — vorher
   verweigert jeder weitere Lauf.
8. Export (`betrieb.seite`) mit neuem Ankerverzeichnis, Timer einschalten.

**Config nachziehen** (etwa die Annahmen fuer Beitragsherabsetzung und
Teilkuendigung vom 2026-10-01, `docs/simulation/erfahrungsannahmen.md`
Abschnitt 4). Die Ablage fuehrt ihre eigene Kopie; das Repository
aendert sie nicht. Eine neue Config gilt von Beginn der Simulation an:
Jeder Lauf rechnet die Geschichte ab 1994 neu, die neuen Raten treffen
also auch Jahre, deren Monatsabschluesse festgeschrieben sind und deren
Buchungen im Journal stehen — eine bestehende Ablage reproduziert danach
nicht mehr. Der Tageslauf haelt deshalb an, sobald die Kopie nicht mehr
die ist, mit der der letzte gruene Tag gerechnet wurde (Config-Hash der
Protokollzeile; Exit 2, Stand und Journal bleiben, eine rote Protokollzeile nennt beide Hashes),
auch bei einer Aenderung ohne Wirkung — und auch, wenn der bereits
gefuehrte Tag zur Kontrolle noch einmal gefahren wird (jeder solche Lauf
schreibt seine rote Zeile; mit der zurueckgesetzten Config ist derselbe Tag
wieder ein No-op ohne Zeile). Die Ablage wird neu aufgesetzt,
nicht nachtraeglich umgerechnet:

1. Zugangsprobe auf einem leeren Verzeichnis, das nur die NEUE Config als
   `configs/bestand.toml` traegt, und A-B2 darauf zeichnen (wie oben).
2. Mit angehaltenem Timer `neuaufsetzen ... --config <neue bestand.toml>
   --zugangsabnahme <sha256>` (Kommando oben), dann Erstbefuellung (rund
   eine Viertelstunde) und Export mit einem NEUEN Ankerverzeichnis.

Folgen: Die alte Ablage liegt mit Journal, Protokollkette, Abschluessen
und Berichten unter `daten.archiv-<Zeit>`; die neue Protokollkette
beginnt neu; jeder Monatsabschluss seit 1994 wird mit der neuen Config
neu festgeschrieben, und die Vorzeigeseite zeigt ab dem naechsten Paket
die neuen Zahlen. Wer beim alten Stand bleiben will, setzt die Kopie auf
die Config zurueck, mit der das Protokoll gerechnet hat.

**Timer:**

```
mkdir -p ~/.config/systemd/user
cp deploy/plv/tageslauf.service deploy/plv/tageslauf.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now tageslauf.timer
loginctl enable-linger "$USER"     # der Timer laeuft auch ohne Sitzung
```

## Betrieb

* **Jede Nacht 23:00** fuehrt der Lauf den heutigen Tag; verpasste
  Naechte holt der naechste Lauf nach (`nachgeholt` im Protokoll).
* **Rot heisst: nicht uebernommen.** Faellt die Wache P-B1, bleibt der
  gestrige Stand der gefuehrte, der Befund steht im Protokoll, Exit 3.
  Ursache beheben, denselben Tag erneut fahren. Eine geaenderte Config
  ist kein solcher Fall: Sie haelt den Lauf schon vor der Fortschreibung an
  (Exit 2, siehe "Config nachziehen").
* **Update** = neuer `IMAGE_TAG` in `.env`, `docker compose pull`, Digest
  eintragen. Der erste Lauf mit neuem Image protokolliert den Wechsel.
  Wechselt die Kern-Version, weisen die Abschluss-Kontrollen
  (`bestand.cli_abschluss --pruefen`) die Abweichungen aus — der
  Tagesbetrieb schreibt nichts um.
* **Sichtung:** `daten/seite/index.html` zeigt den Bestand heute, der
  Bestandsbericht des letzten Monatsabschlusses liegt unter
  `daten/berichte/`. Die oeffentliche Seite bleibt eine vom Menschen
  veroeffentlichte Momentaufnahme (`werkzeuge/README.md`): Ihre Quelle
  ist das **Stands-Paket**, das der Mensch exportiert und dem Auftritt
  uebergibt — nichts wird automatisch veroeffentlicht. Das Paket traegt
  seine Belege (Protokoll mit Kette, Manifest, Berichte, je mit SHA-256);
  der Auftritt prueft sie und veroeffentlicht kein Paket, das sich selbst
  widerspricht.

  Das genuegt aber nicht: Die Protokollkette bindet jede Zeile an ihre
  Vorgaengerin und schuetzt damit alles AUSSER DER LETZTEN — und genau
  aus der letzten leitet `stand.json` ab. Wer beide zusammen umschreibt,
  bekommt ein Paket, das sich selbst bestaetigt. Deshalb schreibt der
  Export einen ANKER in den Fall-Datenraum (den der Tagesbetrieb nicht
  anfasst) und nennt ihn im Paket; der Auftritt prueft dagegen. Ein
  Export ohne `--anker` wird abgelehnt.

  Vor dem Export prueft er jede Protokollzeile gegen den
  Betriebsschluessel (`--betriebsschluessel`; ist `--schluessel` selbst
  der Betriebsschluessel, genuegt er). Ohne ihn gibt es kein Paket. Der
  Auftritt haelt keinen Schluessel: Er prueft Kette, Schema-Folge, Form
  der Zeichnung und Vorlauf und weist die Signatur als "nicht pruefbar"
  aus, statt sie zu behaupten.

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
