# PR-Text fuer `dora-t26` — Pruefrunde T26 des externen Gutachters, umgesetzt

Entwurf der dev-Session (2026-09-22) fuer den Maintainer; die
Korrektur der PR-Aussage, die Block 5 des Gutachters verlangt. Vorher
stand "Alle zwanzig Befunde beider Runden sind abgeschlossen" — die
Gegenproben des Gutachters bestaetigten das nicht. Dieser Text sagt,
was gemessen ist, und benennt, was offen bleibt.

## Was dieser PR behauptet — und was nicht

**Behauptet.** Die 16 Befunde der Runde T26 sind geschlossen, jeder
mit Klassentest und Mutationsproben (Stand je Befund:
`dev-docs/befundliste-t26.md`). Die Suite ist gruen auf dem Host
(Debian, CPython 3.11: 2401 passed, 0 skipped, Stand a68fa63) und in der
Container-Referenzumgebung (`deploy/dev`, dokumentierter Aufruf `python -m pytest -q`,
seriell, Arbeitsbaum @ a68fa63: 2400 passed, 1 skipped, Exit 0 — der Skip ist
umgebungsinhaerent: Docker-in-Docker fuer die Doku-Engine fehlt im
Container, auf dem Host laeuft der Test).

**Nicht behauptet.** Eine Betriebsfreigabe. Sie folgt aus der erneuten
Pruefung des Gutachters, nicht aus dem Schliessen dieser Liste — sein
Schlusssatz gilt weiter. Sechs fachliche Annahmen stehen angeschrieben
(alle sechs am 2026-09-22 vom Maintainer bestaetigt bzw. revidiert).

## Entscheide und Bauten vom 2026-09-22 (seit dem Stand vom Morgen des 20.09.)

* **T26-03 — Weg 2, gekoppelt mit der Zeichnungsschicht (ADR-021,
  5a6667f).** Belegrollen-Vertrag und Freigabesignatur wohnen in
  `models`; Gate und Betriebseingang lesen denselben Vertrag. Der
  Betriebseingang prueft die Rollenmenge EXAKT (DoRAs Fall — eine
  einzige Pflichtrolle — tritt nicht mehr ein), verifiziert die Signatur
  mit dem Schluesselring (`--freigabe-schluessel`), verlangt Schema 7;
  der Tageslauf nimmt keinen unverifizierten Eingang. Zwei unabhaengige
  Zeugen.
* **T26-11 — keine fachliche Frage.** "+202.338, die Herabsetzung hebt"
  war ein Fixture-Artefakt (rho 0.04, rund vier Millionen Mal groesser
  als jede reale Schicht). Ohne Schicht senkt die Herabsetzung; das
  realistisch parametrierte Fixture bindet die Richtung (a68fa63).
* **T26-12 — als Klasse geschlossen.** Nicht ein Verfahren wird
  abgewiesen: Jeder Tarifwerks-Schalterwert wird gegen das gehalten,
  was der produktive Pfad ausfuehrt (Ratsche, ff21da4; Deklaration im
  Kern, Pruefung bei Config und Freischaltung, Befund = Bauauftrag,
  nie Config-Rat). Die Luecke selbst ist gebaut: die Teilkuendigung
  laeuft im produktiven Pfad (b637898) — Grund gekuendigt, Scheiben
  unveraendert, Auszahlung gebucht und in P-B1 hergeleitet; die
  Folgebewertung braucht keinen Sonderweg (Zahlungspfad mit q = 0 ==
  zustandsloser Kern, 1e-15). Annahme 4 (Abweisung) ist damit revidiert;
  Annahme 6 (die Korrekturschicht geht bei der Teilkuendigung vollstaendig
  in die Auszahlung, Abzug proportional ueber den Rueckkaufswert der
  Grundscheibe) hat der Maintainer am 2026-09-22 bestaetigt.
* **Annahme 5 — streng.** Alle drei Pflichttabellen muessen vom
  Beleggraphen bezeugt sein; ein unbezeugter Ledger ist eine Luecke.
* Im Branch, aber keine Gutachter-Befunde: ADR-019 (Suite parallel,
  20:30 -> ~2:30), ADR-020 (Batch-Erzeuger entfernt; die zwei Tests,
  die den Batch brauchten, bezeugen wieder — Uebernahme altert statt
  xfail/Skip), PEX-Zuschlag der Uebernahme, A-M4-Laufmanifest.

## Folgen fuer die Laufzeit nach dem Merge (Betreiber)

* Der Uebernahme-Eingang der Laufzeit (`~/apps/plv/daten/uebernahme/`)
  ist mit `python -m rechner_pipeline.betrieb.uebernahme
  --freigabe-schluessel <pfad>` NEU zu registrieren; ein Eingang ohne
  verifizierte Signatur tritt nicht in den Tageslauf ein. Der aktuelle
  A-M4-Snapshot des Falls ist Schema 7 mit zehn Rollen und passt;
  `neuaufsetzen` reicht den Ring durch.
* Eine Generation mit `red_verfahren = "teilkuendigung"` (TG2015) wird
  gefuehrt; die Ratsche zeigt heute keine Luecke.
* Ein aelterer P-B1-Ledger, der nicht alle drei Tabellen nennt, reicht
  nicht mehr — den Fall neu abnehmen.

## Block 5 des Gutachters — was gefahren wurde

* Volle Suite, Host (Linux/Debian, CPython 3.11): 2401 passed,
  0 skipped (a68fa63, 2:22 mit -n 12).
* Volle Suite, Container-Referenzumgebung (`docker build -f
  deploy/dev/Dockerfile`, `docker run ... rechner-pipeline-dev` auf
  dem Arbeitsbaum @ a68fa63, seriell wie dokumentiert): 2400 passed, 1 skipped in 786.42s (0:13:06),
  Exit 0 (09:34-09:47). 2400 + 1 = 2401 — dieselbe Sammlung wie auf dem
  Host; der eine Skip: `tests/test_quellsystem_dokumente.py` braucht
  Docker in der Umgebung (Docker-in-Docker fehlt im Container).
* Gezielte Gegenproben an den Grenzen — je Fix als Mutationsprobe
  gefahren und in der Commit-Botschaft dokumentiert: Ratsche (Block
  raus / Deklaration verspricht zu viel / Strenge zurueck: 1, 4, 1 rot),
  Teilkuendigung (Schicht nicht in der Auszahlung / f statt 1-f /
  Scheibe mitgekuendigt: je 1 rot), Belegrollen und Zeichnung
  (Rollenvertrag nicht angewandt / Signatur nicht geprueft / Tageslauf
  verlangt keine Verifikation / Schema 6 zugelassen: je 1 rot),
  Stichtags- und Verzoegerungs-Test (Buchungsschnitt raus: rot),
  realistisches Fixture (rho 0.04: rot).
* Drift: `code_index --tests` und `code_karte` befundfrei, Landkarte
  regeneriert (models 7 -> 9 Module), Testgruppen konsistent.

## Offen — benannt, nicht versteckt

* Der Betrieb prueft Signatur und Schluesselklasse, nicht die
  Zeichnungsordnung — bewusst (ADR-021).
* Die Betriebsfreigabe — beim Gutachter.
