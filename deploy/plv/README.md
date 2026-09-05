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
| `env.beispiel` | Vorlage fuer `.env`: Image-Tag, Owner, Digest, Zeitzone; keine Geheimnisse |
| `tageslauf.service`, `tageslauf.timer` | systemd `--user`: taeglich 23:00, `Persistent=true` |
| `.github/workflows/plv-image.yml` | baut bei jedem Push auf `main` das Image `ghcr.io/<owner>/rechner-pipeline-plv` mit den Tags `latest` und Commit-Kurzhash |

## Ablage unter `~/apps/plv/daten`

| Verzeichnis | Inhalt | Schutz |
|---|---|---|
| `configs/bestand.toml` | die Config der PLV — eine Kopie von `configs/bestand_gesamt.toml`; ihr SHA-256 steht in jedem Protokolleintrag | vom Menschen gepflegt |
| `uebernahme/<fall>/` | je Migrationsfall ein Zugangsstand mit `eingang.json` (Fallname, Stichtag, Snapshot-Hash, SHA-256 je Datei) | unantastbar wie ein Fall-Eingang; jede Datei wird beim Lesen gegen ihre Summe gehalten |
| `stand/` | der gefuehrte Stand: die sechs Ausgaben der Fortschreibung, `laufmanifest.json`, ggf. `merkmale.parquet` | ueberschreibbar, aber nur durch einen gruenen Lauf (atomarer Tausch) |
| `journal/tagesjournal.parquet` | die Buchungstage, nur angefuegt | Bijektion zum Ledger wird bei jedem Lauf geprueft |
| `journal/protokoll.jsonl` | eine JSON-Zeile je Lauf: Tag, nachgeholte Tage, Neugeschaeft, Buchungen, Bestandszahlen, P-B1-Urteil, Manifest-Hash, Kern-Version, Image-Digest | nur angefuegt; auch ein roter Lauf steht drin |
| `abschluesse/` | `abschluss_<Monatserster>.parquet`, festgeschrieben 0444, genau einmal (ADR-011) | nie ueberschrieben |
| `berichte/` | `bestandsbericht_<Monatserster>.html` je Monatsabschluss | jederzeit neu renderbar |

## Einrichtung (einmalig, Mensch)

```
mkdir -p ~/apps/plv/daten/configs
cp deploy/plv/compose.yml deploy/plv/env.beispiel ~/apps/plv/
mv ~/apps/plv/env.beispiel ~/apps/plv/.env      # und ausfuellen
cp configs/bestand_gesamt.toml ~/apps/plv/daten/configs/bestand.toml
```

**Uebernahme-Eingang** (je Migrationsfall, aus dem Fall-Arbeitsbereich
heraus; verlangt die Generation des Falls in `bestand.toml`):

```
python -m rechner_pipeline.betrieb.uebernahme --stand ~/apps/plv/daten \
    --fall faelle/<fall> --stichtag 2026-01-01
```

**Image ziehen und Digest eintragen:**

```
cd ~/apps/plv && docker compose pull
docker image inspect ghcr.io/<owner>/rechner-pipeline-plv:latest \
    --format '{{index .RepoDigests 0}}'      # -> IMAGE_DIGEST in .env
```

**Erstbefuellung.** Der erste Lauf baut den Basisbestand aus der Config
(Batch bis zum Betriebsbeginn), nimmt die Uebernahme-Eingaenge auf und
holt alle Tage vom Betriebsbeginn bis heute in EINEM Lauf nach — der
Stand ist derselbe, als haette der Lauf jede Nacht stattgefunden. Vor
dem Timer einmal von Hand fahren und das Protokoll lesen:

```
cd ~/apps/plv && docker compose run --rm tageslauf
tail -n 1 daten/journal/protokoll.jsonl
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
* **Sichtung:** der Bestandsbericht des letzten Monatsabschlusses liegt
  unter `daten/berichte/`; die oeffentliche Seite bleibt eine vom
  Menschen veroeffentlichte Momentaufnahme (`werkzeuge/README.md`).

Lokal, ohne Container (Entwicklerrechner), tut dasselbe:

```
python -m rechner_pipeline.betrieb.tageslauf --stand <daten> [--heute 2026-09-05]
```
