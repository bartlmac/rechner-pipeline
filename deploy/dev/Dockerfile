# Referenzumgebung fuer Entwicklung und Tests: Linux, CPython 3.11, die
# exakt gepinnten Abhaengigkeiten aus requirements-dev.txt — dieselbe
# Eingabe wie die CI (.github/workflows/tests.yml) und das Laufzeit-Image
# (deploy/plv/Dockerfile). Das Projekt haertet seinen Code nicht auf
# mehrere Betriebssysteme; wer nicht auf Linux arbeitet, faehrt die Suite
# hier drin (Entscheid des Maintainers 2026-09-06, Anlass: ein Windows-PR
# mit Python 3.14, der Backslash-Schluessel, CRLF und Dateisperren fand).
#
# Das Image traegt NUR die Abhaengigkeiten. Der Arbeitsbaum wird beim Start
# nach /workspace gemountet und dort editierbar installiert — so testet der
# Container immer den Stand, der gerade auf der Platte liegt, und das Image
# muss bei einer Codeaenderung nicht neu gebaut werden.
#
# Bauen (vom Repo-Wurzelverzeichnis):
#   docker build -f deploy/dev/Dockerfile -t rechner-pipeline-dev .
# Suite fahren:
#   docker run --rm -v "$PWD":/workspace rechner-pipeline-dev
# Shell:
#   docker run --rm -it -v "$PWD":/workspace rechner-pipeline-dev bash
#
# Der Arbeitsbaum muss auf einem Linux-Dateisystem liegen (WSL2-Home,
# nicht /mnt/c): Die Suite prueft Dateirechte und umask, und ein
# NTFS-Mount kennt beides nicht.
FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends git \
 && rm -rf /var/lib/apt/lists/*

# Erst die Pin-Datei mit der vollstaendigen transitiven Huelle — das Paket
# selbst kommt beim Start aus dem gemounteten Baum (ohne Aufloesung).
# (requirements-dev.txt verweist mit -r auf requirements.txt — beide kopieren.)
COPY requirements.txt requirements-dev.txt /tmp/pins/
RUN python -m pip install --no-cache-dir -r /tmp/pins/requirements-dev.txt \
 && rm -r /tmp/pins

# Derselbe unprivilegierte Benutzer wie im Laufzeit-Image; uid 1000 ist
# auf den ueblichen Entwicklerrechnern der erste Benutzer, damit Dateien,
# die im Container entstehen, dem Menschen gehoeren.
RUN useradd --create-home --uid 1000 dev
# (COPY --chmod braucht BuildKit; ohne BuildKit als eigener Schritt.)
COPY deploy/dev/entrypoint.sh /usr/local/bin/rp-dev
RUN chmod 0755 /usr/local/bin/rp-dev
USER dev
WORKDIR /workspace
# Bytecode NICHT aus dem gemounteten Baum lesen oder dorthin schreiben:
# .pyc-Dateien des Hosts tragen dessen Pfade (co_filename) und gelten bei
# gleicher mtime und Groesse als aktuell — im Container liefen dann Tests
# gegen Host-Pfade (zwei Impact-Tests rot, Fixture-Pfade als ../home/...).
# Ein eigenes Cache-Verzeichnis trennt beide Welten sauber.
ENV PYTHONUNBUFFERED=1 \
    PYTHONPYCACHEPREFIX=/home/dev/.pycache \
    PIP_USER=1 \
    PATH="/home/dev/.local/bin:${PATH}"

ENTRYPOINT ["rp-dev"]
CMD ["python", "-m", "pytest", "-q"]
