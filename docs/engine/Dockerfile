# Doku-Engine des Repos: rendert Markdown (Tarifplaene, Konzepte, Kern-Doku)
# nach PDF (Typst) und HTML. Basis ist das offizielle, gepinnte Quarto-Image
# (bringt Pandoc und Typst mit — kein LaTeX noetig). Eigene Ebene bewusst
# minimal; Erweiterungen (Fonts, Filter) kommen hierher.
FROM ghcr.io/quarto-dev/quarto:1.6.42

LABEL org.opencontainers.image.source="https://github.com/bartlmac/rechner-pipeline"
LABEL org.opencontainers.image.description="rechner-pipeline Doku-Engine (Quarto/Typst/Pandoc)"

ENV HOME=/tmp XDG_CACHE_HOME=/tmp/cache
WORKDIR /workspace
ENTRYPOINT ["quarto"]
