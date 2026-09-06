# Laufzeit-Image des PLV-Tagesbetriebs (Fachkonzept docs/simulation/tagesbetrieb.md,
# Abschnitt 8.1). Installation exakt wie die CI (.github/workflows/tests.yml):
# erst die Pin-Datei mit der vollstaendigen transitiven Huelle, dann das Paket
# ohne erneute Aufloesung. Kein Entwicklungswerkzeug, keine Schluessel, kein
# Netz zur Laufzeit (compose.yml), ein unprivilegierter Benutzer.
#
# Bauen vom Repo-Wurzelverzeichnis aus (der Kontext braucht src/ und die
# Pin-Dateien):  docker build -f deploy/plv/Dockerfile -t rechner-pipeline-plv .
FROM python:3.11-slim

ARG GIT_SHA=unbekannt
LABEL org.opencontainers.image.title="rechner-pipeline-plv" \
      org.opencontainers.image.description="Tagesbetrieb der Pfefferminzia LV (Vorzeige)" \
      org.opencontainers.image.revision="${GIT_SHA}"

WORKDIR /opt/rechner-pipeline
COPY requirements.txt pyproject.toml README.md LICENSE ./
COPY src ./src
RUN python -m pip install --no-cache-dir -r requirements.txt \
 && python -m pip install --no-cache-dir -e . --no-deps

RUN useradd --create-home --uid 1000 plv \
 && mkdir -p /daten && chown plv:plv /daten
USER plv

# Der Commit, aus dem das Image entstand — landet im Tagesprotokoll
# (PLV_IMAGE_DIGEST kommt aus der Laufzeitumgebung, siehe compose.yml).
ENV PLV_IMAGE_REVISION="${GIT_SHA}" \
    PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "rechner_pipeline.betrieb.tageslauf"]
CMD ["--stand", "/daten"]
