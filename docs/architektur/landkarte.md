# Landkarte des Zielsystems

Erzeugt aus dem Code, nicht gepflegt. Neu bauen:

```bash
python -m rechner_pipeline.ontologie.landkarte --format mermaid --umfang schichten --out /dev/stdout
python -m rechner_pipeline.ontologie.landkarte --format mermaid --umfang knoten    --out /dev/stdout
python -m rechner_pipeline.ontologie.landkarte --format mermaid --umfang modul --auswahl kern --out /dev/stdout
```

Ein Test haelt diese Seite gegen den Generator: weicht sie ab, faellt die
Suite. GitHub zeichnet die Diagramme direkt; fuer Graphviz, Gephi, yEd
oder einen Graph-Store liefert derselbe Befehl `--format dot` bzw.
`--format graphml`.

Im Zielbild (~1 Mio. Zeilen) gibt es kein Bild "der Codebasis". Es gibt
begrenzte Ausschnitte, und alle drei hier wachsen mit der Struktur statt
mit der Codemenge: der Schichten-Ueberblick, die fachliche Knotensicht,
und der Blick in EINEN Knoten. Ueberschreitet ein Ausschnitt 60 Kaesten,
verweigert der Generator das Bild und nennt den engeren Weg.

## 1 Schichten — der Ueberblick

Wer darf aus wem importieren, und wie oft wird es genutzt. Die Regeln
dahinter sind nachrechenbar (`ontologie.code_karte`), nicht Prosa.

```mermaid
%% Schichten — erzeugt von ontologie.landkarte
flowchart TD
    n__init__["__init__<br/>1 Module"]
    bestand["bestand<br/>16 Module"]
    fall["fall<br/>1 Module"]
    gates["gates<br/>13 Module"]
    kern["kern<br/>9 Module"]
    kommutationskern["kommutationskern<br/>3 Module"]
    models["models<br/>5 Module"]
    ontologie["ontologie<br/>16 Module"]
    qa["qa<br/>9 Module"]
    quellen["quellen<br/>13 Module"]
    spez["spez<br/>5 Module"]
    bestand -- 10 --> kern
    bestand -- 12 --> models
    gates -- 3 --> bestand
    gates -- 4 --> fall
    gates -- 1 --> kern
    gates -- 6 --> models
    gates -- 12 --> ontologie
    gates -- 5 --> qa
    gates -- 4 --> quellen
    gates -- 1 --> spez
    kommutationskern -- 2 --> kern
    models -- 1 --> gates
    models -- 1 --> kern
    ontologie -- 1 --> kern
    qa -- 9 --> kern
    qa -- 2 --> kommutationskern
    qa -- 1 --> models
    quellen -- 1 --> kern
    quellen -- 7 --> models
    quellen -- 3 --> ontologie
    quellen -- 1 --> spez
    spez -- 1 --> kern
    spez -- 11 --> ontologie
```

## 2 Fachknoten — die Sicht der Ontologie

Dieselben IDs wie in der A-Box eines Migrationsfalls und in Gate P-K1. Eine
Kante entsteht nur bei einem ECHTEN Uebergang: ein Rueckgrat-Modul, das
`klv, bu` traegt, macht KLV nicht von BU abhaengig — beide stehen darauf.
Deshalb sind KLV und BU hier korrekt unverbunden.

```mermaid
%% Fachknoten — erzeugt von ontologie.landkarte
flowchart TD
    bu["bu<br/>24 Module"]
    klv["klv<br/>66 Module"]
    system_architektur["system/architektur<br/>4 Module"]
    system_assurance["system/assurance<br/>14 Module"]
    system_fall["system/fall<br/>1 Module"]
    bu -- 2 --> system_assurance
    klv -- 6 --> system_assurance
    klv -- 4 --> system_fall
    system_architektur -- 1 --> bu
    system_architektur -- 2 --> klv
    system_assurance -- 1 --> system_fall
```

## 3 Der Zielrechenkern von innen

Die neun Module von `kern/` und ihre Abhaengigkeiten. `tafeln` ist die
unterste Fachschicht (reine Ausscheidewahrscheinlichkeiten),
`zustandsmodell` das Rueckgrat, die Produkte sind Parametrierungen
darauf (ADR-004).

```mermaid
%% kern — erzeugt von ontologie.landkarte
flowchart TD
    rechner_pipeline_kern___init___py["__init__"]
    rechner_pipeline_kern_konventionen_py["konventionen"]
    rechner_pipeline_kern_model_point_py["model_point"]
    rechner_pipeline_kern_produkte___init___py["__init__"]
    rechner_pipeline_kern_produkte_bu_py["bu"]
    rechner_pipeline_kern_produkte_klv_py["klv"]
    rechner_pipeline_kern_rechenkern_py["rechenkern"]
    rechner_pipeline_kern_tafeln_py["tafeln"]
    rechner_pipeline_kern_zustandsmodell_py["zustandsmodell"]
    rechner_pipeline_kern___init___py --> rechner_pipeline_kern_konventionen_py
    rechner_pipeline_kern___init___py --> rechner_pipeline_kern_model_point_py
    rechner_pipeline_kern___init___py --> rechner_pipeline_kern_rechenkern_py
    rechner_pipeline_kern___init___py --> rechner_pipeline_kern_tafeln_py
    rechner_pipeline_kern___init___py --> rechner_pipeline_kern_zustandsmodell_py
    rechner_pipeline_kern_produkte___init___py --> rechner_pipeline_kern_produkte_bu_py
    rechner_pipeline_kern_produkte___init___py --> rechner_pipeline_kern_produkte_klv_py
    rechner_pipeline_kern_produkte_bu_py --> rechner_pipeline_kern_tafeln_py
    rechner_pipeline_kern_produkte_bu_py --> rechner_pipeline_kern_zustandsmodell_py
    rechner_pipeline_kern_produkte_klv_py --> rechner_pipeline_kern_konventionen_py
    rechner_pipeline_kern_produkte_klv_py --> rechner_pipeline_kern_model_point_py
    rechner_pipeline_kern_produkte_klv_py --> rechner_pipeline_kern_tafeln_py
    rechner_pipeline_kern_produkte_klv_py --> rechner_pipeline_kern_zustandsmodell_py
    rechner_pipeline_kern_rechenkern_py --> rechner_pipeline_kern_model_point_py
    rechner_pipeline_kern_rechenkern_py --> rechner_pipeline_kern_produkte___init___py
    rechner_pipeline_kern_rechenkern_py --> rechner_pipeline_kern_produkte_klv_py
    rechner_pipeline_kern_tafeln_py --> rechner_pipeline_kern_konventionen_py
    rechner_pipeline_kern_zustandsmodell_py --> rechner_pipeline_kern_konventionen_py
    rechner_pipeline_kern_zustandsmodell_py --> rechner_pipeline_kern_tafeln_py
```
