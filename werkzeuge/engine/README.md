# Doku-Engine

Kein Dokument, sondern ein Werkzeug: ein Container-Image mit Quarto, Pandoc
und Typst, das Markdown-Dokumente des Repositorys als PDF rendert. Maßgeblich
bleiben immer die Markdown-Fassungen; die PDFs entstehen neben ihnen und sind
nicht eingecheckt.

| Datei | Zweck |
|---|---|
| `Dockerfile` | das Image, auf dem gepinnten Quarto-Image aufgebaut |
| `render.sh` | rendert die genannten Markdown-Dateien, ohne Angabe alle Tarifpläne |

```
werkzeuge/engine/render.sh plv/mathematik/grundsatzdokumentation.md
IMAGE=local werkzeuge/engine/render.sh        # Image vorher lokal bauen
```

Genutzt wird die Engine für die Tarifpläne und die Grundsatzdokumentation und
von `werkzeuge/quellsystem/dokumente.py`, das die Dokumente der Lieferungen erzeugt. Das
Image baut `.github/workflows/docs-image.yml`, sobald sich hier etwas ändert.
