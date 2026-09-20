# Entscheidungsvorlage: A-M4 verlangt ein Laufmanifest, das im Migrationsfall niemand schreibt

Stand 2026-09-20, dev-Session. Gefunden beim Fahren des Falls
`baldrian-klv-tg2015-lauf2` auf Systemstand `9e9ca7e` — nicht von der
Suite; dieselbe Sorte Befund wie Korrektur-Protokoll Nr. 25, die nur
beim tatsaechlichen Lauf auftritt.

**Der Befund ist NICHT Folge des PEX-Zuschlag-Commits.** Er entsteht
allein aus dem Entscheid vom 2026-09-16 (Laufmanifest ist im
A-M4-Belegvertrag Pflicht). Der Fall ist seit dem 7.9. nicht neu
gezeichnet worden und hat die Regel deshalb nie getroffen.

## Der Blocker

`gates.abnahmebericht` (A-M4) im Bestands-Scope liest per Vorgabe
`<fall>/abgeleitet/diagnostics/bestand_validate.gate.json` — den
P-B1-Beleg der UEBERNAHME — und verlangt darin `summary.manifest`:

    P-B1-Beleg ohne Laufmanifest: summary.manifest fehlt — ohne es sagt
    der Lauf NICHTS darueber, welche Tabellen er gefuehrt hat, und A-M4
    muesste aus der Abwesenheit schliessen. P-B1 mit --manifest erneut
    fahren

Das ist der EINZIGE Befund; alles andere ist gruen. Aber:
`gates.bestand_uebernehmen` schreibt kein Laufmanifest. Nur
`bestand.cli_fortschreibung`, `betrieb.tageslauf` und
`bestand.cli_abschluss` tun das.

Den P-B1-Beleg der Fortschreibung (`diagnostics-nach`, der TRAEGT ein
Manifest) stattdessen zu binden, scheitert an zwei weiteren Zusicherungen
desselben Gates — zu Recht:

    P-B1-Ledger und Migrationssuite binden verschiedene Bestaende
    P-B1-Portfoliozeilen, Suite-Pruefmenge und erwartete Anzahl muessen
    uebereinstimmen

Die Migrationssuite prueft die 834 uebernommenen Vertraege; die
Fortschreibung fuehrt 3093 (834 uebernommene plus eigenes Geschaeft).
Beide Mengen sind richtig, aber es sind zwei verschiedene.

## Warum die naheliegende Reparatur nicht reicht

"Dann schreibt die Uebernahme eben ein Manifest" trifft auf drei
Contract-Festlegungen in `bestand/manifest.py`:

1. `ERZEUGER = "bestand_fortschreibung"` ist gepinnt;
   `validate_manifest` weist jeden anderen Erzeuger ab.
2. `ROLLEN_DATEIEN["portfolio"] = "bestand_gesamt.parquet"`. Die
   Uebernahme schreibt `bestand.parquet`.
3. Und der schwerste: Die Rolle `schichten` entsteht gar nicht in der
   Uebernahme, sondern in `gates.verankerung_belegen`. Ein Manifest, das
   die Uebernahme allein schreibt, nennt `schichten.parquet` nicht unter
   seinen Ausgaben — und genau darauf schlaegt A-M4 dann an ("der
   belegte Lauf nennt sie nicht unter seinen Ausgaben"). Der Fall haette
   den Blocker nur verschoben.

4. Und der entscheidende: `_manifest_befund` haelt die Config, mit der
   P-B1 laeuft, gegen `manifest["config"]["sha256"]`. P-B1 laeuft mit
   `abgeleitet/bestand-config.toml` — die entsteht aber ERST NACH der
   Uebernahme, aus dem `generation-zellen.toml`, das die Uebernahme
   schreibt. Die Uebernahme kann diese Datei nicht binden; sie existiert
   zu ihrer Laufzeit nicht.

Der "belegte Lauf" eines Migrationsfalls hat also ZWEI Produzenten, und
der erste von ihnen ERZEUGT die Config, die das Manifest binden soll,
statt sie zu konsumieren. Das Manifest-Modell kennt einen Produzenten,
der eine fertige Config liest. Das ist kein Tippfehler im Contract,
sondern ein Modellunterschied.

Gegenprobe im Repo: Die A-M4-Tests
(`tests/test_am4_vollprofil_t22.py`, `_t23.py`) legen ihren belegten
Lauf immer als FORTSCHREIBUNG nach `abgeleitet/bestand` — mit
`bestand_gesamt.parquet` und Manifest. Die Lage eines echten
Migrationsfalls (Uebernahme in `abgeleitet/bestand`, Fortschreibung in
`abgeleitet/bestand-nach`) kommt in keinem Test vor. Der e2e-Lauf
`tests/test_baldrian2_e2e.py` faehrt `abnahmebericht` nicht mit. Deshalb
ist die Luecke gruen durch die Suite gegangen.

## Vier Wege

**A — Die Uebernahme wird manifest-schreibender Produzent.**
`ERZEUGER` wird eine Menge; `ROLLEN_DATEIEN["portfolio"]` haengt am
Erzeuger; `gates.verankerung_belegen` ERGAENZT das Manifest der
Uebernahme um `schichten.parquet`, weil es in dasselbe Verzeichnis
schreibt. Haelt den Entscheid vom 2026-09-16 vollstaendig ("ein Beleg,
der nichts sagt, ist kein Beleg") und laesst den Produzenten sagen, was
er erzeugt hat. Kostet eine Aenderung an einem geteilten Vertrag
(`bestand/manifest.py`) und damit eine ADR-Notiz.

**B — Das Manifest ist nur fuer Fortschreibungs-Laeufe Pflicht.**
Kleinste Aenderung, aber sie oeffnet genau das Loch wieder, das der
Entscheid geschlossen hat: Wer kein Manifest will, deklariert seinen
Lauf als Uebernahme.

**C — Die Fallablage aendern**, so dass der belegte Lauf die
Fortschreibung ist. Bricht die Mengengleichheit mit der Migrationssuite
und damit die Aussage, dass genau der abgenommene Bestand geprueft
wurde. Nicht empfohlen.

**D — Ein eigener Manifest-Schritt fuer den Migrationslauf**
(Empfehlung, ersetzt A). Nicht die Uebernahme schreibt das Manifest,
sondern der letzte Schritt, der in dasselbe Verzeichnis schreibt und die
Config schon kennt: `gates.verankerung_belegen`. Zu diesem Zeitpunkt
liegen alle Rollendateien vor (die sechs der Uebernahme plus die
`schichten.parquet`, die er selbst erzeugt), und `bestand-config.toml`
existiert. Er bekommt ein `--config` und schreibt
`abgeleitet/bestand/laufmanifest.json` mit `erzeuger =
"bestand_migrationszugang"` und `horizont` = Migrationsstichtag.
Dafuer noetig: `ERZEUGER` wird eine Menge, und die Portfolio-Rolle
heisst je nach Erzeuger `bestand.parquet` statt
`bestand_gesamt.parquet`. Kein bestehender Check wird schwaecher, der
Entscheid vom 2026-09-16 bleibt vollstaendig, und es bleibt bei EINEM
Manifest-Schreiber je Lauf.

Warum A (die Uebernahme schreibt selbst) nicht geht, steht oben unter
Punkt 3 und 4: Sie kennt weder die Schicht noch die Config.

## Was bis zur Entscheidung steht

Die ganze Producer-Kette ist auf `9e9ca7e` gefahren und gruen:

    Uebernahme          834 Vertraege, 994 Ledgerzeilen, 12 PEX-Zuschlaege
    Verankerung         834/834 getragen, max |R| 0,02
    P-B1 (Uebernahme)   exit 0, 994/994 Betraege hergeleitet
    P-B1 (nach)         exit 0, 16460/16460, manifest_gebunden 8
    P-K1                exit 0 (Altbeleg archiviert)
    A-M1 / A-M2 / A-M3  100/100, 100/100, 166/166 — Gates exit 0
    Migrationssuite     834/834, vollstaendig_geprueft
    Fuehrungsprobe      834 Vertraege, 550 mit Anfangszustand,
                        42 Buchungen, 0 Befunde
    A-M4                ROT (nur dieser Befund)

Die Zeichnungen A-Q1/A-M1/A-M2/A-M3 sind NICHT gesetzt. Grund: Jeder der
drei Wege aendert Code und damit den Systemstand; auf dem alten Stand
gezeichnet waeren sie sofort wieder entwertet. Sie werden zusammen mit
A-M4 auf dem Stand gezeichnet, der die Entscheidung traegt.

Folge fuer die Vorzeige: `betrieb.uebernahme` verlangt einen
angenommenen A-M4-Snapshot ("eine Uebernahme ohne Migrationsabnahme gibt
es nicht"). Die Vorzeige-Session bleibt bis zu dieser Entscheidung
blockiert — an diesem Punkt, nicht mehr am PEX-Zuschlag.
