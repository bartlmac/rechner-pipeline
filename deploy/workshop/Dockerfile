# Arbeitsumgebung der Vorfuehrung und des Workshops: Debian 12 mit dessen
# Python 3.11, die exakt gepinnten Abhaengigkeiten aus requirements-dev.txt
# (dieselbe Eingabe wie CI und Referenzumgebung), dazu die Werkzeuge, die ein
# Fall am Bildschirm braucht (git, tmux, watch, script), und ein
# unprivilegierter Benutzer.
#
# Warum Debian 12 und nicht das Image der Referenzumgebung (deploy/dev,
# python:3.11-slim): Ein eingerichteter Rechner faehrt festgehaltene Faelle
# nach und haelt seine Ergebnisse byteweise gegen die der Beispielumgebung.
# Die laeuft auf Debian 12 mit dem Python der Distribution; python:3.11-slim
# wandert mit jedem Debian-Wechsel und traegt einen anderen Python-Stand.
#
# Das Image ist ein Zwischenschritt: deploy/workshop/abbild_bauen.sh legt in
# einem Container daraus die Code-Baeume an und exportiert das Dateisystem
# als tar.gz. Dieses Abbild importiert deploy/workshop/einrichten.ps1 auf
# einem Windows-Rechner als eigene WSL-Distribution. Im Image liegen KEIN
# Repository, KEINE Schluessel und KEIN Fall: Schluessel und Welt entstehen
# erst auf dem Rechner, auf dem gearbeitet wird.
#
# Bauen (vom Repo-Wurzelverzeichnis):
#   docker build -f deploy/workshop/Dockerfile -t rechner-pipeline-workshop .
FROM debian:12-slim

# script und scriptreplay (Aufzeichnung) bringt bsdutils mit, das zum
# Grundsystem gehoert; watch kommt aus procps.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        python3 python3-venv python3-pip git tmux procps less nano ca-certificates tzdata \
 && rm -rf /var/lib/apt/lists/*

# Erst die Pin-Datei mit der vollstaendigen transitiven Huelle, wie CI und
# Referenzumgebung. Dazu die exakt gepinnten Bauwerkzeuge aus pyproject.toml:
# Mit ihnen laesst sich das Paket spaeter OHNE Netz editierbar installieren
# (plv-einrichten, --no-build-isolation) — ein isolierter Bau holte sie bei
# jedem Baum neu aus dem Netz.
# --break-system-packages: Dieses System hat genau einen Zweck. Die Pins
# landen unter /usr/local und sind die Umgebung, aus der jeder Baum sein
# .venv speist; ein Paket der Distribution wird dabei nicht ersetzt.
COPY requirements.txt requirements-dev.txt pyproject.toml /tmp/pins/
RUN python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/pins/requirements-dev.txt \
 && python3 -c "import tomllib; print('\n'.join(tomllib.load(open('/tmp/pins/pyproject.toml','rb'))['build-system']['requires']))" > /tmp/pins/bau.txt \
 && python3 -m pip install --no-cache-dir --break-system-packages -r /tmp/pins/bau.txt \
 && rm -r /tmp/pins

# Derselbe unprivilegierte Benutzer wie im Laufzeit-Image (uid 1000).
RUN useradd --create-home --uid 1000 --shell /bin/bash plv

# Ein exportiertes Dateisystem traegt keine ENV-Angaben des Images: Was die
# Shell in der WSL-Distribution braucht, steht deshalb in Dateien.
COPY deploy/workshop/wsl.conf /etc/wsl.conf
COPY deploy/workshop/profil.sh /etc/profile.d/plv-workshop.sh
COPY deploy/workshop/einrichten.sh /usr/local/bin/plv-einrichten
RUN chmod 0644 /etc/wsl.conf /etc/profile.d/plv-workshop.sh \
 && chmod 0755 /usr/local/bin/plv-einrichten \
 && ln -sf /usr/share/zoneinfo/Europe/Berlin /etc/localtime \
 && echo "Europe/Berlin" > /etc/timezone

USER plv
WORKDIR /home/plv
ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=1
CMD ["bash", "-l"]
