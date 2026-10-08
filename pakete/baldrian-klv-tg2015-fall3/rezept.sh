# Rezept des Falls 3 — die Uebernahme des Bestands KLV TG2015 der Baldrian
# Lebensversicherung a. G. zum 01.01.2026, festgehalten am 02.10.2026.
# Am 08.10.2026 neu festgehalten: Kern und Tarifwerk tragen seither die
# redaktionelle Ueberarbeitung von Kern-Docstrings, Grundsatzdokumentation
# und Tarifplaenen (keine Regel, kein Wert); die Fingerabdruecke unten und
# die Begruendungen von A-K2 und A-T1 nennen diesen Stand. Am selben Abend
# nach Ebenen geordnet (ADR-028): Die Lieferung liegt unter
# migrationen/baldrian/lieferungen/, das README der Tarifplaene nennt den
# neuen Ort der Doku-Engine; die erwarteten Ergebnisse sind unveraendert.
#
# Das Rezept faehrt die ENDFASSUNG des Falls: je Artefakt das Kommando, das es
# zuletzt erzeugt hat, in der Reihenfolge des Laufs. Messungen auf Kopien,
# verworfene Zwischenstaende und die Rueckfragen an die Quelle stehen im
# Protokoll des festgehaltenen Falls, nicht hier.
#
# Voraussetzung: Die Welt ist auf dem Stand VOR dem Fall aufgestellt (Kern
# 3.21.0, Generation TG2015 nicht in der Bestand-Config), der Codebaum steht
# beim Nachfahren auf dem Stand, den der Fall hinterlassen hat (Kern 3.22.0,
# Tafeln DAV2008, Generation TG2015 in der Bestand-Config). Die drei
# Entwicklungsschritte des Rechenkern-Agenten sind Commits des Codebaums; das
# Rezept baut sie nicht, es belegt ihren Stand gegen den abgenommenen.
#
# Jede Zeichnung hier ist ein Nachfahren ohne erneute Pruefung: Die
# Begruendung nennt das Urteil der Zeichnung im festgehaltenen Fall.

# --- Eingang: die Lieferung und fuenf Nachlieferungen, jede neu beauftragt ---

anlegen
vorlage

haltepunkt auftrag

zeichne A-M6 "Nachfahren des festgehaltenen Falls 3 (02.10.2026): Beauftragung der Uebernahme KLV TG2015 auf der Lieferung laut Lieferschein (zwoelf Dateien)."

registriere auskunft-1-rechnungsgrundlagen-kodierungen-herabsetzung.md
vorlage
zeichne A-M6 "Nachfahren des festgehaltenen Falls 3: Neubeauftragung nach der Nachlieferung der Quelle — Auskunft Nr. 1 (Rechnungsgrundlagen, Kodierungen, Herabsetzung)."

registriere anteile-06.csv
registriere auskunft-2-herabsetzungsanteile-einzelpolicen.md
vorlage
zeichne A-M6 "Nachfahren des festgehaltenen Falls 3: Neubeauftragung nach der Nachlieferung der Quelle — Auskunft Nr. 2 und die Herabsetzungsanteile von zehn Policen."

registriere auskunft-3-bewertung-zwischen-jahrestagen.md
vorlage
zeichne A-M6 "Nachfahren des festgehaltenen Falls 3: Neubeauftragung nach der Nachlieferung der Quelle — Auskunft Nr. 3 (Bewertung zwischen den Jahrestagen)."

registriere auskunft-4-erwartungswerte-acht-policen.md
vorlage
zeichne A-M6 "Nachfahren des festgehaltenen Falls 3: Neubeauftragung nach der Nachlieferung der Quelle — Auskunft Nr. 4 (keine Erwartungswerte der acht Policen aus dem ersten Lieferlauf)."

registriere auskunft-5-nachtrag-lieferung-erwartungswerte.md
registriere baldrian_erwartungswerte_stichprobe_lieferlauf2.json
registriere baldrian_erwartungswerte_stichtag_lieferlauf2.json
registriere baldrian_erwartungswerte_verlauf_lieferlauf2.json
registriere festlegung-plv-tarifplan-migration-klv-tg2015.md
vorlage
zeichne A-M6 "Nachfahren des festgehaltenen Falls 3: Neubeauftragung nach dem Nachtrag der Quelle (Auskunft Nr. 5, drei Erwartungswerte-Dateien des zweiten Lieferlaufs) und der registrierten Festlegung der PLV zum Tarifplan der Migration."

haltepunkt eingang

# --- Stufe 1: Quellen verdichten, A-Box, Diskrepanzen, Spez ---

schritt "Vorverdichtung: Tarifrechner" $PY -m rechner_pipeline.gates.extract --repo-root . \
    --input $F/eingang/Tarifrechner_KLV_TG2015.xlsm --out-dir $A/vorverdichtung/xlsm-TG2015 \
    --adapter excel --diagnostics-dir $A/diagnostics
schritt "Vorverdichtung: Versicherungsbedingungen" $PY -m rechner_pipeline.quellen.tarifplan_staging \
    --input $F/eingang/AVB_KLV_TG2015.pdf --out $A/vorverdichtung/avb-TG2015.json
schritt "Vorverdichtung: Mitteilung 143" $PY -m rechner_pipeline.quellen.tarifplan_staging \
    --input $F/eingang/Mitteilung_143_KLV_TG2015.pdf --out $A/vorverdichtung/meldung-TG2015.json
schritt "Profil: Bestandsabzug 01.01.2026" $PY -m rechner_pipeline.quellen.bestand_profil \
    --input $F/eingang/baldrian_bestandsabzug_2026-01-01.csv --out $A/vorverdichtung/bestand-2026-01-01.json
schritt "Profil: Bestandsabzug 01.01.2027" $PY -m rechner_pipeline.quellen.bestand_profil \
    --input $F/eingang/baldrian_bestandsabzug_2027-01-01.csv --out $A/vorverdichtung/bestand-2027-01-01.json
schritt "Profil: Vorgeschichte der Vertraege" $PY -m rechner_pipeline.quellen.bestand_profil \
    --input $F/eingang/baldrian_gevo_metadaten.csv --out $A/vorverdichtung/gevo_metadaten.json
schritt "Profil: Geschaeftsvorfaelle 2026" $PY -m rechner_pipeline.quellen.bestand_profil \
    --input $F/eingang/baldrian_gevo_protokoll_2026.csv --out $A/vorverdichtung/gevo_protokoll_2026.json

einlegen abgeleitet/abox/fragmente
schritt "A-Box aus den fuenf Fragmenten" $PY -m rechner_pipeline.gates.abox_merge --fall $F --repo-root . \
    --diagnostics-dir $A/diagnostics

haltepunkt diskrepanzen

einlegen abgeleitet/protokoll/werkzeug-aktuariat/abzugsabgleich_fall.py
einlegen abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:nichtraucher,einzel#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:nichtraucher,kollektiv#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:nichtraucher,haus#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:raucher,einzel#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:raucher,kollektiv#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:raucher,haus#zins" 0.0125 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:nichtraucher,haus#beta1" 0.01 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json
entscheide "klv/tg2015/zelle:raucher,haus#beta1" 0.01 "Abzugsabgleich: genau die Lesart der Mitteilung 143 reproduziert DECKKAP und JBRUTTO (Beleg im Fall, Ad-hoc-Skript des Aktuariats); Auskunft Nr. 1 der Baldrian: Meldung massgeblich, Rechner nicht fortgeschrieben." --beleg abgeleitet/berichte/abzugsabgleich.json

schritt "P-Q3: die A-Box ist vollstaendig und ohne offene Diskrepanz" $PY -m rechner_pipeline.gates.abox_validate \
    --fall $F --repo-root .
erwarte abgeleitet/abox/coverage.json
# Spez und Fachspez haben im System kein Kommando; der Fall hat sie mit diesen
# Bibliotheksaufrufen erzeugt (Protokoll des Falls, Zug 15). Die Spez sagt,
# welche Tafeln dem Kern FEHLEN — und der Fall hat sie erzeugt, bevor der
# Rechenkern-Agent die sechs Tafeln eintrug. "Vorhanden" sind hier deshalb die
# Tafeln des abgenommenen Kernstands der Linie, nicht die des Codebaums, auf
# dem nachgefahren wird: So entsteht die Spez des festgehaltenen Falls, und der
# Schritt danach prueft wirklich, dass die sechs Tafeln im Kern wertgleich sind.
schritt "Spez und Fachspez der Generation aus der A-Box" $PY -c 'import subprocess, sys; \
    import xml.etree.ElementTree as ET; from pathlib import Path; \
    from rechner_pipeline.ontologie.abox import lade; from rechner_pipeline.spez.erzeugen import baue_spez; \
    from rechner_pipeline.spez.validierung import speichere_spez, validate_spez; \
    from rechner_pipeline.spez.fachspez import speichere_fachspez; \
    fall = Path(sys.argv[1]); datei = sys.argv[2] + ":src/rechner_pipeline/kern/tafeln.xml"; \
    kern = subprocess.run(["git", "show", datei], capture_output=True, text=True, check=True).stdout; \
    vorhanden = {t.get("name") for t in ET.fromstring(kern).findall("table") if t.get("select_max") is None}; \
    abox = lade(fall); spez = baue_spez(abox, "klv/tg2015", vorhandene_tafeln=vorhanden); \
    fehler = validate_spez(spez, abox); fehler and sys.exit("die Spez ist nicht gueltig: %s" % fehler); \
    print(speichere_spez(spez, fall)); print(speichere_fachspez(spez, abox, fall))' $F "$(abgenommen A-K2)"
erwarte abgeleitet/spez/klv-tg2015.spez.json

# --- Stufe 2: der Stand des Zielsystems gegen den abgenommenen ---

schritt "Tafeln der Generation: im Kern vorhanden und wertgleich" $PY -m rechner_pipeline.quellen.tafel_import \
    --fall $F --generation klv/tg2015 --dry-run
schritt "Kernstand belegen (Vorlage A-K2)" $PY -m rechner_pipeline.gates.kernstand_belegen --fall $F --repo-root . \
    --von "$(abgenommen A-K2)" \
    --begruendung "Kern 3.22.0 und Tafeln DAV2008 (Fall 3); Config-Block TG2015 und Testliste. Am 08.10.2026 redaktionell nachgezogen: Docstrings in kern/__init__.py und kern/zustandsmodell.py, die Grundsatzdokumentation (Zweitkern, Schreibweise, Zeichensetzung); keine fachliche Aenderung, Referenzwerte unbewegt"
# Das Urteil der A-K2 wird uebernommen, nicht neu gefaellt. Das traegt nur,
# wenn der Gegenstand derselbe ist: der abgenommene Kern, der belegte Kern und
# die Referenzwerte, je mit dem Fingerabdruck des festgehaltenen Falls.
schritt "Der belegte Kern ist der des festgehaltenen Falls" $PY -c 'import json, sys; \
    d = json.load(open(sys.argv[1])); ist = [d["kern_alt_sha256"], d["kern_sha256"], d["referenzwerte_sha256"]]; \
    sys.exit(0 if ist == sys.argv[2:5] else "ein anderer Kern als im festgehaltenen Fall: %s" % ist)' \
    $A/kern/aenderung.json 444e6b113a8881b403ece1b0304d07b2039edaa96f97efacf4c1361de865dc5f \
    0f298a4d8cd6487ace133cd840ae0e626f98b3a2ef38040c195b7b5dbda165b2 \
    f77cbd2a6d4bd7aea210cd1b706241ab13a826ed76af42654a9c654592aeb793

haltepunkt vor-A-K2

zeichne A-K2 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Kern 3.21.0 auf 3.22.0, drei zurueckgebaute Ausgestaltungen als Faehigkeiten ohne Voreinstellung (Beitragsformel je Erhoehungsbaustein, Stornoabzug je Baustein, Teilkuendigung nur der Grundversicherung), Wahl nur aus der Spez; sechs Tafeln DAV2008 ohne Konflikt; Referenzwerte unbewegt. Regression: benannte Ausnahme, nicht gefahren — die Zeichnung deckt nur die qualitative Pruefung. Dazu die redaktionelle Ueberarbeitung vom 08.10.2026 (Docstrings im Kern, Grundsatzdokumentation), keine fachliche Aenderung; neu abgenommen am 08.10.2026."

schritt "T-Box: keine Aenderung seit der Abnahme der Linie (Verweis A-O1)" $PY -m rechner_pipeline.gates.stand_belegen verweisen \
    --fall $F --repo-root . --gate A-O1 --linie $LINIE
schritt "P-K1: die Generation rechnet die Werte des Tarifrechners" $PY -m rechner_pipeline.gates.generation_golden \
    --fall $F --generation klv/tg2015 --repo-root .

# --- Stufe 3: Uebersetzung, Uebernahme, die drei Tests, Fortschreibung, Suite ---

einlegen abgeleitet/transformation/baldrian_bestandsabzug_2026-01-01.spec.json
schritt "Uebersetzung: die Vorschrift ist anwendbar" $PY -m rechner_pipeline.gates.transformation_anwenden --fall $F \
    --spec $A/transformation/baldrian_bestandsabzug_2026-01-01.spec.json
schritt "Uebersetzung: 834 Quellzeilen in Zielzeilen" $PY -m rechner_pipeline.gates.transformation_anwenden --fall $F \
    --spec $A/transformation/baldrian_bestandsabzug_2026-01-01.spec.json --anwenden \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json
schritt "Bestand uebernehmen" $PY -m rechner_pipeline.gates.bestand_uebernehmen --fall $F \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json --tarif-generation TG2015 \
    --stichtag 2026-01-01 --vorgeschichte baldrian_gevo_metadaten.csv --generation-spez klv/tg2015 \
    --anfangszustand materialisieren --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json --out-dir $A/bestand
erwarte abgeleitet/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json
erwarte abgeleitet/bestand/bestand.parquet
erwarte abgeleitet/bestand/scheiben.parquet
erwarte abgeleitet/bestand/ledger.parquet
erwarte abgeleitet/bestand/verankerung.parquet
erwarte abgeleitet/bestand/generation-zellen.toml
erwarte abgeleitet/bestand/uebernahme.json
schritt "Bestand-Config in den Fall legen" install -D -m 0644 configs/bestand_gesamt.toml $A/bestand-config/bestand_gesamt.toml
schritt "Verankerung belegen (Schichten)" $PY -m rechner_pipeline.gates.verankerung_belegen --fall $F --repo-root . \
    --generation klv/tg2015 --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --config $A/bestand-config/bestand_gesamt.toml --stichtag 2026-01-01
erwarte abgeleitet/bestand/schichten.parquet
schritt "Stichtagstest (A-M1)" $PY -m rechner_pipeline.gates.aktuartest_lauf --fall $F --abnahme A-M1 \
    --generation klv/tg2015 --erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --stichprobe baldrian_erwartungswerte_stichprobe_lieferlauf2.json --bestand $A/bestand/bestand.parquet \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --schicht abgeleitet/schichten/verankerung_schichten.json --repo-root .
schritt "Verlaufstest (A-M2)" $PY -m rechner_pipeline.gates.aktuartest_lauf --fall $F --abnahme A-M2 \
    --generation klv/tg2015 --erwartungswerte baldrian_erwartungswerte_verlauf_lieferlauf2.json \
    --stichprobe baldrian_erwartungswerte_stichprobe_lieferlauf2.json --bestand $A/bestand/bestand.parquet \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --schicht abgeleitet/schichten/verankerung_schichten.json --repo-root .
schritt "Geschaeftsvorfalltest (A-M3)" $PY -m rechner_pipeline.gates.aktuartest_lauf --fall $F --abnahme A-M3 \
    --generation klv/tg2015 --erwartungswerte baldrian_erwartungswerte_geschaeftsvorfaelle.json \
    --stichprobe baldrian_erwartungswerte_stichprobe_lieferlauf2.json --bestand $A/bestand/bestand.parquet \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --schicht abgeleitet/schichten/verankerung_schichten.json --repo-root .
schritt "Fortschreibung des Gesamtbestands bis 01.01.2027" $PY -m rechner_pipeline.bestand.cli_fortschreibung \
    --config $A/bestand-config/bestand_gesamt.toml --bis 2027-01-01 --uebernahme $A/bestand \
    --merkmale $A/bestand/merkmale.parquet --out-dir $A/bestand-nach
erwarte abgeleitet/bestand-nach/bestand_gesamt.parquet
erwarte abgeleitet/bestand-nach/scheiben.parquet
erwarte abgeleitet/bestand-nach/ledger.parquet
erwarte abgeleitet/bestand-nach/reduktionen.parquet
schritt "P-B1: der uebernommene Bestand" $PY -m rechner_pipeline.gates.bestand_validate \
    --portfolio $A/bestand/bestand.parquet --historie $A/bestand/historie.parquet \
    --ledger $A/bestand/ledger.parquet --scheiben $A/bestand/scheiben.parquet \
    --merkmale $A/bestand/merkmale.parquet --schichten $A/bestand/schichten.parquet \
    --verankerung $A/bestand/verankerung.parquet --config $A/bestand-config/bestand_gesamt.toml \
    --bis 2026-01-01 --manifest $A/bestand/laufmanifest.json --repo-root . --diagnostics-dir $A/diagnostics
schritt "P-B1: der fortgeschriebene Bestand" $PY -m rechner_pipeline.gates.bestand_validate \
    --portfolio $A/bestand-nach/bestand_gesamt.parquet --historie $A/bestand-nach/historie.parquet \
    --scheiben $A/bestand-nach/scheiben.parquet --ledger $A/bestand-nach/ledger.parquet \
    --bis 2027-01-01 --config $A/bestand-config/bestand_gesamt.toml \
    --merkmale $A/bestand-nach/merkmale.parquet --schichten $A/bestand-nach/schichten.parquet \
    --verankerung $A/bestand-nach/verankerung.parquet --manifest $A/bestand-nach/laufmanifest.json \
    --reduktionen $A/bestand-nach/reduktionen.parquet --repo-root . --diagnostics-dir $A/diagnostics-nach
schritt "Migrationssuite: jeder Vertrag an beiden Stichtagen" $PY -m rechner_pipeline.gates.migrationssuite_lauf --fall $F \
    --generation klv/tg2015 --abzug-1 baldrian_bestandsabzug_2026-01-01.csv \
    --abzug-2 baldrian_bestandsabzug_2027-01-01.csv --gevo-protokoll baldrian_gevo_protokoll_2026.csv \
    --bestand $A/bestand/bestand.parquet --config $A/bestand-config/bestand_gesamt.toml \
    --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json \
    --schicht abgeleitet/schichten/verankerung_schichten.json --repo-root .
schritt "Fuehrungsprobe: der Bestand im Tagesbetrieb" $PY -m rechner_pipeline.gates.fuehrungsprobe --fall $F --repo-root . \
    --generation klv/tg2015 --uebernahme $A/bestand --fortschreibung $A/bestand-nach \
    --config $A/bestand-config/bestand_gesamt.toml \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --vorgeschichte baldrian_gevo_metadaten.csv --stichtag 2026-01-01 \
    --schicht abgeleitet/schichten/verankerung_schichten.json --red-anteile-datei anteile-06.csv \
    --red-anteil-kandidat 0.50 --red-anteil-kandidat 0.60 --red-anteil-kandidat 0.75 \
    --anker-erwartungswerte baldrian_erwartungswerte_stichtag_lieferlauf2.json
schritt "Uebersetzung: Ergebnis gegen den uebernommenen Bestand" $PY -m rechner_pipeline.gates.transformation_anwenden --fall $F \
    --spec $A/transformation/baldrian_bestandsabzug_2026-01-01.spec.json --anwenden \
    --zeilen $A/transformation/baldrian_bestandsabzug_2026-01-01.zeilen.json \
    --ziel $A/bestand/bestand.parquet \
    --ergebnis $A/transformation/baldrian_bestandsabzug_2026-01-01.ergebnis.json
erwarte abgeleitet/transformation/baldrian_bestandsabzug_2026-01-01.ergebnis.json
schritt "Bestandsbericht vor der Fortschreibung" $PY -m rechner_pipeline.bestand.cli_report \
    --portfolio $A/bestand/bestand.parquet --historie $A/bestand/historie.parquet \
    --ledger $A/bestand/ledger.parquet --scheiben $A/bestand/scheiben.parquet \
    --merkmale $A/bestand/merkmale.parquet --config $A/bestand-config/bestand_gesamt.toml \
    --bis 2026-01-01 --out $A/berichte/bestandsbericht-vor.html
schritt "Bestandsbericht nach der Fortschreibung" $PY -m rechner_pipeline.bestand.cli_report \
    --portfolio $A/bestand-nach/bestand_gesamt.parquet --historie $A/bestand-nach/historie.parquet \
    --ledger $A/bestand-nach/ledger.parquet --scheiben $A/bestand-nach/scheiben.parquet \
    --merkmale $A/bestand/merkmale.parquet --config $A/bestand-config/bestand_gesamt.toml \
    --bis 2027-01-01 --stichtag 2026-01-01 --out $A/berichte/bestandsbericht-nach.html
schritt "Abnahmebericht (Vorlage A-M4)" $PY -m rechner_pipeline.gates.abnahmebericht --fall $F \
    --suite $A/berichte/migrationssuite.json \
    --titel "Migrationsabnahme Baldrian KLV TG2015 (Fall 3) zum 01.01.2026 und 01.01.2027" \
    --stichtag-1 2026-01-01 --stichtag-2 2027-01-01 \
    --spec $A/transformation/baldrian_bestandsabzug_2026-01-01.spec.json \
    --transformation-ergebnis $A/transformation/baldrian_bestandsabzug_2026-01-01.ergebnis.json \
    --bestandsbericht-vor $A/berichte/bestandsbericht-vor.html \
    --bestandsbericht-nach $A/berichte/bestandsbericht-nach.html --repo-root .
erwarte abgeleitet/berichte/migrationsabnahme.html
schritt "Vorlage A-M1" $PY -m rechner_pipeline.gates.aktuartest --abnahme A-M1 --fall $F \
    --titel "Stichtagstest Baldrian KLV TG2015 (Fall 3)" --repo-root . --diagnostics-dir $A/diagnostics
schritt "Vorlage A-M2" $PY -m rechner_pipeline.gates.aktuartest --abnahme A-M2 --fall $F \
    --titel "Verlaufstest Baldrian KLV TG2015 (Fall 3)" --repo-root . --diagnostics-dir $A/diagnostics
schritt "Vorlage A-M3" $PY -m rechner_pipeline.gates.aktuartest --abnahme A-M3 --fall $F \
    --titel "Geschaeftsvorfalltest Baldrian KLV TG2015 (Fall 3)" --repo-root . --diagnostics-dir $A/diagnostics

haltepunkt vor-A-Q1

zeichne A-Q1 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): acht Diskrepanzen endgueltig entschieden, jede mit Beleg (Lesart der Mitteilung 143: Zins 0,0125, Haus-beta1 0,01); A-Box vollstaendig; Uebersetzung 834 Quellzeilen ohne Befund; P-Q3 und P-K1 bestanden. Ausgewiesene Grenzen gehen mit: quelle_art der Auskunft und der Festlegung nur naechstliegend; P-K1 hat fuer fuenf von sechs Zellen keine Erwartungswerte des Rechners; der Zins/beta1-Beleg stammt aus einem Ad-hoc-Skript; die Anteile der Auskunftspolicen sind Quellenaussage."
zeichne A-M1 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Stichtagstest bestanden, Pflichtschicht gezogen und bestanden; Eingaben sind die Dateien des zweiten Lieferlaufs. Grenze: Die Abnahme unterscheidet die Anteilskandidaten der Auskunftspolicen nicht; die Anteile sind Quellenaussage."
zeichne A-M2 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Verlaufstest (5 und 10 Jahre, Ablauf) bestanden; Eingaben sind die Dateien des zweiten Lieferlaufs. Grenze: Die Anteile der Auskunftspolicen sind Quellenaussage."
zeichne A-M3 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Geschaeftsvorfalltest bestanden; die Datei der Geschaeftsvorfaelle ist die der ersten Lieferung, Anker und Stichprobe die des zweiten Lieferlaufs."

schritt "Tarifwerk belegen (Vorlage A-T1)" $PY -m rechner_pipeline.gates.tarifwerk_belegen --fall $F --repo-root . \
    --von "$(abgenommen A-T1)" \
    --begruendung "Der Tarifplan KLV (Abschnitt zur uebernommenen Generation TG2015, Tabelle der Tarifzellen) wurde bei der Rueckfuehrung der Generation TG2015 in die Bestand-Config neu erzeugt. Geaendert ist nur die Schreibweise der Stornoabzuege der beiden Haus-Zellen (Mindest- und Hoechstbetrag 0 zu 0.0, Wert gleich null); kein Wert, keine Rechnungsgrundlage der eigenen Generationen der PLV. Die uebernommene Generation TG2015 steht neu in der Bestand-Config als Generationsblock ohne Neuzugang; sie ist nicht Gegenstand der Tarifwerk-Abnahme (eigene Generationen), die Parametrierung der eigenen Generationen ist unveraendert. Am 08.10.2026 redaktionell ueberarbeitet: Tarifplaene KLV und BU (Zweitkern-Saetze, Pruefvermerke, Schreibweise, Zeichensetzung); keine Regel und kein Wert geaendert. Am selben Abend im README der Tarifplaene der Ort der Doku-Engine nachgezogen (werkzeuge/engine, ADR-028)."
schritt "Das belegte Tarifwerk ist das des festgehaltenen Falls" $PY -c 'import json, sys; \
    d = json.load(open(sys.argv[1])); v, s = d["stand_vorher"], d["stand"]; \
    ist = [v["tarifwerk_sha256"], s["tarifwerk_sha256"], s["parametrierung_sha256"]]; \
    sys.exit(0 if ist == sys.argv[2:5] else "ein anderes Tarifwerk als im festgehaltenen Fall: %s" % ist)' \
    $A/tarifwerk/aenderung.json 716d2ff1c167906452494f68a9daa9cb2f04b7ad33db8f8c8634fc515ee5d7e5 \
    981a6ff332659405868af3494c20c0324c1ba0395eaf8173976447ba4d5ad322 \
    1ddb772011782802bb72a6800a04effcd3da1791566bfc0e08e2789566ae038d
zeichne A-T1 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Im Tarifplan KLV ist nur die Schreibweise der Haus-Stornoabzuege geaendert (0 zu 0.0, Wert null); die Parametrierung der eigenen Generationen ist die abgenommene. Der neue Generationsblock TG2015 der Bestand-Config ist nicht Gegenstand von A-T1 (uebernommene Generation; im Fall abgenommen ueber P-K1, A-M1 und A-M4). Dazu die redaktionelle Ueberarbeitung der Tarifplaene vom 08.10.2026 und der Ort der Doku-Engine im README der Tarifplaene (ADR-028), keine Regel und kein Wert; neu abgenommen am 08.10.2026."

haltepunkt vor-A-M4

zeichne A-M4 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Migrationssuite fuer jeden der 834 Vertraege an beiden Stichtagen bestanden, keine Pruefluecken; Uebersetzung ohne Befund; Fuehrungsprobe ohne Befund; P-B1 bestanden; A-Q1, A-M1 bis A-M3, A-K2, A-T1 und A-O1 (Verweis) liegen auf demselben Stand. Ausgewiesene Grenzen gehen mit: Der Pflichtschritt Ausgestaltung des migrierten Tarifplans ist nicht als eigenes Dokument gefuehrt; die Anteile der Auskunftspolicen sind Quellenaussage; die Regression des Kerns ist die benannte Ausnahme (nicht gefahren)."

haltepunkt abgenommen

# --- Zugang: der abgenommene Bestand kommt in die Ablage der Welt ---
# Die Probe rechnet rund 20 Minuten, der Aufbaulauf rund 11. Der Aufbaulauf
# fuehrt bis zum Tag des festgehaltenen Laufs; den Tagesbetrieb danach faehrt
# die Welt selbst weiter.

zugang probe

haltepunkt vor-A-B2

zeichne A-B2 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Zugangsprobe bestanden, keine Befunde — auf der leeren Ablage stehen nach dem Zugang 834 Vertraege in Kraft; Summe, Deckungskapital, Rueckkaufswert, Korrekturschicht, Jahresbeitrag und Zugangsbuchungen sind gleich dem abgenommenen Soll; ausserhalb des Zugangs ist die Ablage mit und ohne Zugang gleich. Grenzen gehen mit: Der Folgetermin 01.01.2027 ist von der Probe nicht gedeckt (ihn hat die Migrationssuite der A-M4 geprueft); die Code-Identitaet der Laufzeit belegt die Probe nicht."
zugang aufsetzen
zugang aufbau 2026-10-02
zugang belegen

haltepunkt vor-A-B3

zugang ab3 "Nachfahren ohne erneute Pruefung; uebernommen ist das Urteil der Zeichnung im festgehaltenen Fall 3 (02.10.2026): Bestandswache P-B1 gruen; alle Tabellen des Stands sind gleich der Ablage; die Ablage gibt die Abschluesse der Zugangsprobe mit Zugang wieder; die Vertragszahl ist vollstaendig erklaert (eigener Bestand, Neugeschaeft und die 834 Vertraege des Zugangs). Grenzen gehen mit: Der Jahresbeitrag ist im Beleg nicht belegt; die Differenz zum Vorgaengerstand ist nicht zerlegt; der Folgetermin 01.01.2027 ist noch ungedeckt; der Beleg ist ein Hash-Beleg, kein Fachurteil."
zugang binden

haltepunkt zugang
