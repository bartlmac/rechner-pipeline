# Werkzeuge der Vorfuehrung

Beobachtungshilfen, **kein Bestandteil der Migrations-Pipeline**. Sie
lesen ein Herstellerformat (Claude-Code-Sitzungstranskripte) und stellen
Laeufe dar; die Fachlichkeit liegt unter `src/`. Die Trennung ist
absichtlich sichtbar — die allgemeine Frage, was versionierter
Repo-Bestandteil wird und was eine gekennzeichnete Beispielandockung
bleibt, steht in `dev-docs/offene-punkte.md`.

| Werkzeug | Zweck |
|---|---|
| `verlaufsprotokoll.py` | Sitzungstranskript zu einem lesbaren Verlauf |
| `vorzeigeseite.py` | Fall-Artefakte zu einer statischen Seite |

## Verlauf eines Laufs protokollieren

```
python werkzeuge/verlaufsprotokoll.py --neueste --out verlauf.md
python werkzeuge/verlaufsprotokoll.py --sitzung <uuid> --mit-denken
```

Trennt Mensch, Konsole, Operator und Werkzeug; Entscheide werden
hervorgehoben. Schluesselpfade und Geheimnisse sind redigiert.

## Seite eines Laufs bauen

```
python werkzeuge/vorzeigeseite.py \
    --fall faelle/baldrian-uebernahme \
    --out vorzeige/ [--verlauf verlauf.md]
```

Sammelt Lieferung, Gate-Ledger, Entscheide und Verlauf, stempelt
Systemstand und Branch, schreibt `index.md`, `_config.yml` und
`artefakte/`.

## Veroeffentlichen

**Die Artefakte eines Laufs gehoeren nicht ins Repo.** ADR-002: "Das
Repo ist das System, nicht der Datenraum"; `faelle/` ist gitignoriert
und echte Faelle liegen ausserhalb. Deshalb kann auch keine
GitHub-Action die Seite bauen — sie sieht die Artefakte nicht. Der Weg
ist: lokal bauen, Ergebnis auf einen eigenen Branch schieben, Pages
liest diesen Branch.

### Einmalig einzurichten (Mensch, in der GitHub-Oberflaeche)

1. Leeren Branch anlegen:

   ```
   git switch --orphan gh-pages
   git commit --allow-empty -m "Vorzeigeseite"
   git push -u origin gh-pages
   git switch -
   ```

2. In GitHub unter **Settings → Pages**: *Source* auf **Deploy from a
   branch**, Branch `gh-pages`, Ordner `/ (root)`. Kein
   Actions-Workflow noetig.

Bewusst KEIN Ausloeser bei jedem Push: Veroeffentlichen ist nach aussen
gerichtet und praktisch nicht zurueckzunehmen (Indexierung, Caches).
Es bleibt eine menschliche Handlung.

### Je Lauf

```
git worktree add /tmp/gh-pages gh-pages
cp -r vorzeige/. /tmp/gh-pages/
cd /tmp/gh-pages && git add -A && git commit -m "Lauf <datum>" && git push
git worktree remove /tmp/gh-pages
```

### Vorher pruefen

Das Werkzeug erzwingt zwei Dinge und laesst drei beim Menschen.

**Erzwungen:** Nichts aus `simulation/` oder `docs-local/` gelangt auf
die Seite, und `MANIPULATIONEN.md` sowie `NOTIZEN.md` sind gesperrt,
egal wo sie liegen — dort stehen die Aufloesungen des Vorfuehrfalls. Das
Werkzeug bricht ab, statt zu warnen. Ausserdem steht der
Simulationshinweis vor allem anderen: erfundene Unternehmen,
synthetische Vertraege, Abnahmen mit einem Simulationsschluessel
gezeichnet. Ohne ihn saehe eine oeffentliche Seite mit signierten
aktuariellen Abnahmen aus wie eine echte.

**Beim Menschen:** Stehen Klarnamen im Verlaufsprotokoll? Trifft der
Simulationshinweis noch zu? Traegt die Seite etwas, das die Vorfuehrung
verraet? Das Werkzeug fragt danach; beantworten muss es jemand.
