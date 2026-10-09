# Doku-Engine

Kein Dokument, sondern ein Werkzeug: ein Container-Image mit Quarto, Pandoc
und Typst, das Markdown-Dokumente des Repositorys als PDF rendert. Maßgeblich
bleiben immer die Markdown-Fassungen; die PDFs entstehen neben ihnen und sind
nicht eingecheckt.

| Datei | Zweck |
|---|---|
| `Dockerfile` | das Image, auf dem gepinnten Quarto-Image aufgebaut |
| `render.sh` | rendert die genannten Markdown-Dateien |

```
werkzeuge/engine/render.sh werkzeuge/quellsystem/avb.md
IMAGE=local werkzeuge/engine/render.sh werkzeuge/quellsystem/avb.md   # Image vorher lokal bauen
```

Genutzt wird die Engine von `werkzeuge/quellsystem/dokumente.py`, das die
Dokumente der Lieferungen erzeugt. Für die PLV erzeugt sie keine PDFs
(Entscheid des Maintainers vom 2026-10-09): Grundsatzdokumentation und
Tarifpläne gelten in ihrer Markdown-Fassung, und eine Datei neben ihnen
gehört nicht zum abgenommenen Gegenstand. Für eine Datei unter `plv/` hält
`render.sh` an. Das Image baut `.github/workflows/docs-image.yml`, sobald sich
hier etwas ändert.
