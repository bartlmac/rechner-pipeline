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
| `configs/bestand.toml` | die Config der PLV — eine Kopie von `configs/bestand_gesamt.toml`; ihr SHA-256 steht in jedem Protokolleintrag. Nach dem Nachziehen der Kopie aendert sich der Hash im Protokoll, nicht der Bestand: `nummernkreis` traegt die bisherigen Positionen explizit (T22-09) | vom Menschen gepflegt |
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
   Bedienfehler). Der Zugangsstichtag ist ein Monatserster. Die Probe
   haelt ihren Code-Stand gegen die letzte gruene Protokollzeile: Image-
   Digest und Revision (soweit dort erfasst) und den Hash des Pakets —
   also im produktiven Image fahren bzw. `--image-digest` wie im
   Tageslauf angeben; jede Abweichung ist ein Befund.

```
python -m rechner_pipeline.betrieb.zugangsprobe --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 [--bis <ISO>] \
    --freigabe-schluessel <pfad-zum-freigabeschluessel> \
    --schluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json \
    [--arbeit <leeres-verzeichnis-ausserhalb-von-daten>]
```

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
    --gate A-B2 --entscheid angenommen --entscheider "<Name>" \
    --begruendung "..." --freigabe-schluessel <schluessel-mensch-betrieb> \
    --zeichnungsordnung <ordnung> [--mandat <mandat>]
```

3. **Registrierung** — auf DERSELBEN Ablage, ohne dass dazwischen ein
   Tageslauf den gefuehrten Stand bewegt oder die Config getauscht wird,
   mit denselben Angaben wie die Probe (`--fall`, `--quelle`, Stichtag,
   Betriebsschluessel): Die Registrierung haelt ihre eigene `eingang.json`
   und den Stand der Ablage gegen die Hashes, die A-B2 bindet, und legt die
   gepruefte Abnahme als `zugangsabnahme.json` (gezeichnet) neben den
   Eingang. Den A-B2-Snapshot liest sie aus dem Gate-Beleg des Falls oder
   aus `--zugangsabnahme <sha256>`; seine Freigabe muss von einem
   Schluessel stammen, dessen Rolle die Zeichnungsordnung fuer A-B2
   berechtigt. Tritt der Eingang erst spaeter ein (Stichtag in der
   Zukunft), haelt der Tageslauf am Stichtag Config, Kern-Version und
   Code-Stand gegen die Abnahme: Wer dazwischen Config oder Image tauscht,
   braucht Probe und A-B2 neu.

```
python -m rechner_pipeline.betrieb.uebernahme --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01 \
    --freigabe-schluessel <pfad-zum-freigabeschluessel> \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
```

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
nichts zu tun`, keine Protokollzeile, Stand unveraendert. Nur ein Tag VOR
dem gefuehrten (rueckwaerts) bricht mit Exit 2 ab.

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
    --freigabe-schluessel <pfad-zum-freigabeschluessel> \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json \
    --zugangsabnahme <sha256-des-a-b2-snapshots>
cd ~/apps/plv && docker compose run --rm tageslauf
python -m rechner_pipeline.betrieb.seite --stand ~/apps/plv/daten \
    --paket <paket> --anker faelle/<fall>/abgeleitet/anker \
    --betriebsschluessel ~/apps/plv/schluessel/betrieb.key \
    --zeichnungsordnung ~/apps/plv/schluessel/zeichnungsordnung.json
systemctl --user start tageslauf.timer
```

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
  Ursache beheben (meist die Config), denselben Tag erneut fahren.
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
