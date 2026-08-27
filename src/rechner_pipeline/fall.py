"""Fall-Arbeitsbereich: der Ort, an dem ein Migrationsfall lebt.

Das Repo ist das System, nicht der Datenraum. Ein Fall (ein
Migrationsprojekt) lebt in einem eigenen Arbeitsbereich mit zwei strikt
getrennten Zonen:

* ``eingang/`` — die registrierten Quellen. Bei der Registrierung wird
  jede Datei inhaltsadressiert (SHA-256), schreibgeschuetzt kopiert und
  im Register ``eingang.json`` verzeichnet. Hier beginnt die
  Provenance-Kette. Diese Zone ist NICHT regenerierbar; kein Werkzeug
  dieses Repos raeumt sie auf, und eine Registrierung wird nie still
  ueberschrieben — gleicher Name mit anderem Inhalt ist ein harter
  Konflikt mit beiden Hashes in der Meldung.
* ``abgeleitet/`` — alles Regenerierbare (Vorverdichtung, generierter
  Kern, Gate-Ledger, Berichte). Darf jederzeit geloescht und aus
  Eingang + System neu erzeugt werden.

Im echten Einsatz liegt der Arbeitsbereich ausserhalb des Repos (der
Pfad ist frei waehlbar); ``faelle/`` im Repo ist nur der gitignorierte
Default fuer lokale Demo-Faelle. Fall-Quellen kommen von aussen (die
Lieferung des abgebenden Unternehmens); ``tests/fixtures/`` haelt
synthetische Quellmappen fuer Tests und Demo-Faelle.

Kommandos (ein JSON-Objekt auf stdout, Log auf stderr)::

    python -m rechner_pipeline.fall anlegen --fall faelle/klv-tg2012 \
        --scope tarif [--beschreibung TEXT]
    python -m rechner_pipeline.fall registrieren --fall faelle/klv-tg2012 \
        --datei tests/fixtures/Tarifrechner_KLV_TG2012.xlsm [--als NAME]
    python -m rechner_pipeline.fall status --fall faelle/klv-tg2012

``assurance --fall <pfad> --quelle <name>`` faehrt die Gate-Kette auf
einem Fall: Eingang wird vor dem Lauf gegen das Register geprueft
(Integritaets-Gate), die Ausgabe-Verzeichnisse liegen unter
``abgeleitet/``.

Knoten: system/fall
"""

from __future__ import annotations

import argparse
import datetime as _dt
import errno
import hashlib
import json
import os
import stat
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

SCHEMA_VERSION = 1

FALL_MANIFEST = "fall.json"
EINGANG_REGISTER = "eingang.json"
EINGANG_REGISTER_LOCK = ".eingang.json.lock"

#: Der Fall deklariert seinen fachlichen Umfang einmal im nicht regenerierbaren
#: Manifest. A-M4 darf daraus Pflichten ableiten; Dateiexistenz oder ein zufaellig
#: vorhandener Bestandsbericht sind kein belastbarer Scope-Entscheid.
FALL_SCOPE_SCHEMA_VERSION = 2
FALL_SCOPES = ("tarif", "bestand")

#: Pflichtbelegrollen JE GATE und Scope (ADR-009, fortgeschrieben durch
#: ADR-010): A-M1 und A-M4 verlangen verschiedene Belege. A-M1 (aktuarielle
#: Abnahme) pinnt im Bestands-Scope das Testergebnis und den Bericht des
#: aktuariellen Tests; im Tarif-Scope gibt es keine Vertragslieferung und
#: damit keine eigenen Testartefakte — der Entscheid stuetzt sich dort
#: auf die ohnehin gepinnten P-K1-Belege. A-M4 traegt zusaetzlich den
#: geltenden A-M1-Snapshot als Pflichtrolle (erzwungene Reihenfolge).
BELEGROLLEN = {
    "A-M1": {
        "tarif": (),
        "bestand": ("aktuartest", "aktuartest_bericht"),
    },
    "A-M4": {
        "tarif": ("pq3_ledger", "aq1_snapshot", "am1_snapshot", "pk1_belege"),
        "bestand": (
            "pq3_ledger",
            "aq1_snapshot",
            "am1_snapshot",
            "pk1_belege",
            "pb1_ledger",
            "migrationssuite",
            "abnahmebericht",
        ),
    },
}


class FallFehler(ValueError):
    """Fachlicher Fehler im Fall-Arbeitsbereich (kein Usage-Fehler)."""


def scope_dokument(scope: str) -> Dict[str, Any]:
    """Kanonische Scope-Deklaration fuer ``fall.json``."""
    if scope not in FALL_SCOPES:
        raise FallFehler(
            f"unbekannter Fall-Scope {scope!r} — erlaubt: {', '.join(FALL_SCOPES)}"
        )
    return {
        "schema_version": FALL_SCOPE_SCHEMA_VERSION,
        "typ": scope,
    }


def lade_scope(fall: Path) -> str:
    """Den expliziten Fall-Scope streng aus dem Manifest laden.

    Ein Altfall ohne Deklaration wird nicht still als Tarif- oder Bestandsfall
    geraten. Er muss bewusst mit der richtigen Scope-Deklaration migriert
    werden, bevor ein menschliches Gate angenommen werden kann.
    """
    manifest = _lade_json(fall / FALL_MANIFEST, "Fall-Manifest")
    scope = manifest.get("scope")
    felder = {"schema_version", "typ"}
    legacy_felder = {"schema_version", "typ", "gate_dag_version"}
    if (
        isinstance(scope, dict)
        and set(scope) == legacy_felder
        and scope.get("schema_version") == 1
        and scope.get("gate_dag_version") == "1.0.0"
        and scope.get("typ") in FALL_SCOPES
    ):
        # Der unmittelbar vor ToDo 6.2 erzeugte Scope hat bereits denselben
        # ausdruecklichen Typ. Nur seine nicht mehr verwendete DAG-Metadatei
        # wird lesend toleriert; neue Manifeste schreiben ausschliesslich v2.
        return str(scope["typ"])
    if not isinstance(scope, dict) or set(scope) != felder:
        raise FallFehler(
            "Fall-Manifest braucht scope mit exakt "
            f"{sorted(felder)}; Scope bewusst als 'tarif' oder 'bestand' "
            "deklarieren, nicht aus vorhandenen Artefakten raten"
        )
    if type(scope.get("schema_version")) is not int or scope[
        "schema_version"
    ] != FALL_SCOPE_SCHEMA_VERSION:
        raise FallFehler(
            f"scope.schema_version muss {FALL_SCOPE_SCHEMA_VERSION} sein"
        )
    typ = scope.get("typ")
    if typ not in FALL_SCOPES:
        raise FallFehler(
            f"scope.typ {typ!r} ist ungueltig — erlaubt: {', '.join(FALL_SCOPES)}"
        )
    return str(typ)


def belegrollen(gate: str, scope: str) -> List[str]:
    """Stabile Pflichtbelegrollen je Gate fuer den ausdruecklichen Scope."""
    if gate not in BELEGROLLEN:
        raise FallFehler(
            f"kein Belegrollen-Vertrag fuer Gate {gate!r} "
            f"(deklariert: {sorted(BELEGROLLEN)})"
        )
    scope_dokument(scope)
    return list(BELEGROLLEN[gate][scope])


def am4_belegrollen(scope: str) -> List[str]:
    """Stabile A-M4-Pflichtbelegrollen (Kurzform von ``belegrollen``)."""
    return belegrollen("A-M4", scope)


def _pruefe_eingangsname(name: str) -> str:
    """Ein Eingangsname ist ein einfacher Dateiname — sonst ist er keiner.

    Ohne diese Pruefung wuerde ``--als`` als Pfad interpretiert: ``..``
    schreibt in die Fall-Wurzel (und zerstoert dort still das Manifest),
    ein absoluter Wert schreibt irgendwohin ins Dateisystem — beides
    unbemerkt, weil ``pruefen`` den Traversal-Namen wieder aufloest und
    die Datei ausserhalb von ``eingang/`` nicht sieht. Die Zonen-Trennung
    haengt an dieser einen Pruefung.
    """
    if not name or name in (".", ".."):
        raise FallFehler(f"unzulaessiger Eingangsname: {name!r}")
    if name != Path(name).name or "/" in name or "\\" in name:
        raise FallFehler(
            f"unzulaessiger Eingangsname: {name!r} — erlaubt ist ein "
            "einfacher Dateiname ohne Pfadanteil (kein '/', kein '..', "
            "kein absoluter Pfad); der Eingang ist eine flache Zone"
        )
    return name


def _kopiere_geschuetzt(
    quelle: Path, ziel: Path, erwarteter_sha256: str
) -> int:
    """Quelle exklusiv und ohne Symlink-Folgen in den Eingang kopieren.

    ``Path.exists`` ist fuer diese Sicherheitsentscheidung ungeeignet: Bei
    einem dangling Symlink liefert es ``False`` und ein anschliessendes
    ``write_bytes`` schreibt durch den Link. Das Ziel wird deshalb relativ zu
    einem ohne Symlink-Folgen geoeffneten Verzeichnis-Deskriptor und mit
    ``O_EXCL`` erzeugt. Ein zwischen Pruefung und Erzeugung platzierter Link
    kann so ebenfalls nicht nach ausserhalb der Eingangszone fuehren.
    """
    if ziel.is_symlink():
        raise FallFehler(
            f"Eingangsziel {ziel.name!r} ist ein Symlink — Symlinks sind "
            "im Eingang unzulaessig"
        )

    quell_flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    eingang_flags = (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    ziel_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_NOFOLLOW", 0)
    )
    quell_fd: Optional[int] = None
    eingang_fd: Optional[int] = None
    ziel_fd: Optional[int] = None
    try:
        quell_fd = os.open(quelle, quell_flags)
        if not stat.S_ISREG(os.fstat(quell_fd).st_mode):
            raise FallFehler(f"Quelle ist keine regulaere Datei: {quelle}")
        try:
            if os.open in os.supports_dir_fd:
                eingang_fd = os.open(ziel.parent, eingang_flags)
                if not stat.S_ISDIR(os.fstat(eingang_fd).st_mode):
                    raise FallFehler(
                        f"Eingangszone ist kein Verzeichnis: {ziel.parent}"
                    )
                ziel_fd = os.open(
                    ziel.name, ziel_flags, 0o444, dir_fd=eingang_fd
                )
            else:
                # Windows bietet fuer os.open kein dir_fd. O_EXCL blockiert
                # auch dort ein bereits vorhandenes finales Symlink-Ziel; die
                # Eingangszone wurde unmittelbar vor diesem Aufruf geprueft.
                ziel_fd = os.open(ziel, ziel_flags, 0o444)
        except FileExistsError as exc:
            raise FallFehler(
                f"Eingangsziel {ziel.name!r} ist bereits belegt — vorhandene "
                "Dateien oder Symlinks werden nie ueberschrieben"
            ) from exc

        kopie_hash = hashlib.sha256()
        kopierte_bytes = 0
        with os.fdopen(quell_fd, "rb") as quell_stream:
            quell_fd = None
            with os.fdopen(ziel_fd, "wb") as ziel_stream:
                ziel_fd = None
                for block in iter(lambda: quell_stream.read(1 << 20), b""):
                    ziel_stream.write(block)
                    kopie_hash.update(block)
                    kopierte_bytes += len(block)
        if kopie_hash.hexdigest() != erwarteter_sha256:
            entfernt = _entferne_angelegte_datei(ziel)
            bereinigung = (
                "keine inkonsistente Kopie wurde registriert"
                if entfernt
                else f"inkonsistente Kopie {ziel} muss entfernt werden"
            )
            raise FallFehler(
                f"Quelle {quelle} wurde waehrend der Registrierung geaendert — "
                f"{bereinigung}"
            )
        return kopierte_bytes
    except OSError as exc:
        raise FallFehler(f"Quelle kann nicht sicher registriert werden: {exc}") from exc
    finally:
        for fd in (ziel_fd, eingang_fd, quell_fd):
            if fd is not None:
                os.close(fd)


def _entferne_angelegte_datei(pfad: Path) -> bool:
    """Eine von uns angelegte 0444-Kopie auch unter Windows entfernen."""
    try:
        if pfad.is_symlink() or not pfad.is_file():
            return False
        modus = pfad.stat().st_mode
        pfad.chmod(modus | stat.S_IWUSR)
        pfad.unlink()
        return True
    except OSError:
        return False


def _lade_json(pfad: Path, was: str) -> Dict[str, Any]:
    """JSON eines Fall-Artefakts laden; Defekte sind FallFehler, kein Traceback."""
    if pfad.is_symlink():
        raise FallFehler(
            f"{was} ist ein Symlink ({pfad}) — Symlinks sind unzulaessig"
        )
    if not pfad.exists():
        raise FallFehler(
            f"kein Fall-Arbeitsbereich: {pfad} fehlt — zuerst "
            "'fall anlegen' ausfuehren"
        )
    fd: Optional[int] = None
    try:
        fd = os.open(pfad, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise FallFehler(f"{was} ist keine regulaere Datei ({pfad})")
        with os.fdopen(fd, "rb") as stream:
            fd = None
            roh = stream.read()
        daten = json.loads(roh.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FallFehler(f"{was} unlesbar ({pfad}): {exc}") from exc
    except OSError as exc:
        raise FallFehler(f"{was} kann nicht sicher gelesen werden ({pfad}): {exc}") from exc
    finally:
        if fd is not None:
            os.close(fd)
    if not isinstance(daten, dict):
        raise FallFehler(f"{was} hat unerwartete Struktur ({pfad})")
    return daten


def _sha256(pfad: Path) -> str:
    if pfad.is_symlink():
        raise FallFehler(
            f"Symlink kann nicht als regulaere Datei gelesen werden: {pfad}"
        )
    h = hashlib.sha256()
    fd: Optional[int] = None
    try:
        fd = os.open(pfad, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise FallFehler(f"keine regulaere Datei: {pfad}")
        with os.fdopen(fd, "rb") as f:
            fd = None
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    except OSError as exc:
        raise FallFehler(
            f"Datei kann nicht sicher gelesen werden ({pfad}): {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
    return h.hexdigest()


def _ist_schreibbar(pfad: Path) -> bool:
    """Schreib-Bits einer regulaeren Datei ohne Symlink-Folgen pruefen."""
    fd: Optional[int] = None
    try:
        fd = os.open(pfad, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        modus = os.fstat(fd).st_mode
        if not stat.S_ISREG(modus):
            raise FallFehler(f"keine regulaere Datei: {pfad}")
        return bool(modus & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    except OSError as exc:
        raise FallFehler(
            f"Dateimodus kann nicht sicher gelesen werden ({pfad}): {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)


def _dateigroesse(pfad: Path) -> int:
    """Groesse einer regulaeren Datei ohne Symlink-Folgen lesen."""
    fd: Optional[int] = None
    try:
        fd = os.open(pfad, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        datei_stat = os.fstat(fd)
        if not stat.S_ISREG(datei_stat.st_mode):
            raise FallFehler(f"keine regulaere Datei: {pfad}")
        return datei_stat.st_size
    except OSError as exc:
        raise FallFehler(
            f"Dateigroesse kann nicht sicher gelesen werden ({pfad}): {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)


def _schuetze_datei(pfad: Path) -> None:
    """Eine bereits vorhandene regulaere Eingangskopie sicher schuetzen."""
    fd: Optional[int] = None
    try:
        fd = os.open(pfad, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        modus = os.fstat(fd).st_mode
        if not stat.S_ISREG(modus):
            raise FallFehler(f"keine regulaere Datei: {pfad}")
        neu = modus & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
        if hasattr(os, "fchmod"):
            os.fchmod(fd, neu)
        else:  # pragma: no cover - fchmod ist auf den Unix-Zielsystemen da
            pfad.chmod(neu)
    except OSError as exc:
        raise FallFehler(
            f"Datei kann nicht sicher geschuetzt werden ({pfad}): {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)


def _jetzt_utc() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _schreibe_json(pfad: Path, daten: Dict[str, Any]) -> None:
    if pfad.is_symlink():
        raise FallFehler(
            f"JSON-Ziel ist ein Symlink ({pfad}) — Schreiben verweigert"
        )
    inhalt = (
        json.dumps(daten, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    fd: Optional[int] = None
    temp_pfad: Optional[Path] = None
    try:
        fd, temp_name = tempfile.mkstemp(
            dir=pfad.parent,
            prefix=f".{pfad.name}.",
            suffix=".tmp",
        )
        temp_pfad = Path(temp_name)
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o644)
        with os.fdopen(fd, "wb") as stream:
            fd = None
            stream.write(inhalt)
            stream.flush()
            os.fsync(stream.fileno())
        if pfad.is_symlink():
            raise FallFehler(
                f"JSON-Ziel ist ein Symlink ({pfad}) — Schreiben verweigert"
            )
        os.replace(temp_pfad, pfad)
    except OSError as exc:
        raise FallFehler(
            f"JSON kann nicht sicher geschrieben werden ({pfad}): {exc}"
        ) from exc
    finally:
        if fd is not None:
            os.close(fd)
        if temp_pfad is not None:
            try:
                temp_pfad.unlink()
            except FileNotFoundError:
                pass


def _sperre_datei(fd: int) -> None:
    """Exklusive betriebssystemweite Sperre auf einem stabilen Deskriptor."""
    if os.name == "nt":  # pragma: no cover - auf Windows in CI auszufuehren
        import msvcrt

        while True:
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                    raise
                time.sleep(0.05)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)


def _entsperre_datei(fd: int) -> None:
    if os.name == "nt":  # pragma: no cover - auf Windows in CI auszufuehren
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


@contextmanager
def _registrierungs_lock(fall: Path) -> Iterator[None]:
    """Serialisiere den gesamten Read-Modify-Write-Pfad von ``eingang.json``.

    Die Lockdatei bleibt absichtlich bestehen: Die Sperre ist ein Kernel-Lock
    auf ihrem Inode, kein durch Loeschen veraltbarer Sentinel. Ein Byte macht
    denselben Vertrag auch fuer ``msvcrt.locking`` unter Windows nutzbar.
    """
    register_pfad = fall / EINGANG_REGISTER
    if not fall.is_dir():
        raise FallFehler(
            f"kein Fall-Arbeitsbereich: {register_pfad} fehlt — zuerst "
            "'fall anlegen' ausfuehren"
        )
    lock_pfad = fall / EINGANG_REGISTER_LOCK
    if lock_pfad.is_symlink():
        raise FallFehler(
            f"Registrierungs-Lock ist ein Symlink ({lock_pfad}) — "
            "Registrierung verweigert"
        )
    fd: Optional[int] = None
    try:
        fd = os.open(
            lock_pfad,
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
            raise FallFehler(
                f"Registrierungs-Lock ist keine eindeutige regulaere Datei "
                f"({lock_pfad})"
            )
        if metadata.st_size == 0:
            os.write(fd, b"0")
            os.fsync(fd)
        _sperre_datei(fd)
    except FallFehler:
        if fd is not None:
            os.close(fd)
        raise
    except OSError as exc:
        if fd is not None:
            os.close(fd)
        raise FallFehler(
            f"Registrierungs-Lock kann nicht sicher gesetzt werden "
            f"({lock_pfad}): {exc}"
        ) from exc

    assert fd is not None
    try:
        yield
    finally:
        try:
            _entsperre_datei(fd)
        finally:
            os.close(fd)


def verzeichnisse(fall: Path) -> Dict[str, Path]:
    """Die festen Orte eines Fall-Arbeitsbereichs (reine Ableitung)."""
    abgeleitet = fall / "abgeleitet"
    return {
        "eingang": fall / "eingang",
        "abgeleitet": abgeleitet,
        "info_dir": abgeleitet / "info_from_excel",
        "generated_dir": abgeleitet / "generated",
        "diagnostics_dir": abgeleitet / "diagnostics",
        "berichte_dir": abgeleitet / "berichte",
    }


def anlegen(
    fall: Path, beschreibung: str = "", scope: str = "tarif"
) -> Dict[str, Any]:
    """Arbeitsbereich anlegen; ein bestehender Fall wird nie ueberschrieben."""
    manifest = fall / FALL_MANIFEST
    register = fall / EINGANG_REGISTER
    if manifest.exists():
        if not register.exists():
            raise FallFehler(
                f"unvollstaendiger Fall: {manifest} existiert, {register} "
                "fehlt — Register von Hand ergaenzen "
                '(\'{"schema_version": 1, "quellen": []}\') oder den '
                "Arbeitsbereich verwerfen; 'anlegen' repariert nicht"
            )
        raise FallFehler(
            f"Fall existiert bereits: {manifest} — ein Arbeitsbereich wird "
            "nie ueberschrieben (neuen Pfad waehlen)"
        )
    if register.exists():
        raise FallFehler(
            f"unvollstaendiger Fall: {register} existiert (mit Provenance!), "
            f"{manifest} fehlt — 'anlegen' wuerde das Register leeren und "
            "die Herkunft der Quellen verlieren; Manifest von Hand "
            "ergaenzen oder anderen Pfad waehlen"
        )
    scope_daten = scope_dokument(scope)
    v = verzeichnisse(fall)
    v["eingang"].mkdir(parents=True, exist_ok=True)
    v["abgeleitet"].mkdir(parents=True, exist_ok=True)
    daten = {
        "schema_version": SCHEMA_VERSION,
        "name": fall.name,
        "beschreibung": beschreibung,
        "angelegt_am": _jetzt_utc(),
        "scope": scope_daten,
    }
    _schreibe_json(manifest, daten)
    _schreibe_json(fall / EINGANG_REGISTER,
                   {"schema_version": SCHEMA_VERSION, "quellen": []})
    return {"fall": str(fall), "angelegt": True, **daten}


def _lade_register(fall: Path) -> Dict[str, Any]:
    register = _lade_json(fall / EINGANG_REGISTER, "Eingangs-Register")
    if type(register.get("schema_version")) is not int or register[
        "schema_version"
    ] != SCHEMA_VERSION:
        raise FallFehler(
            f"Eingangs-Register braucht schema_version {SCHEMA_VERSION} "
            f"({fall / EINGANG_REGISTER})"
        )
    if not isinstance(register.get("quellen"), list):
        raise FallFehler(
            f"Eingangs-Register ohne Liste 'quellen' ({fall / EINGANG_REGISTER})"
        )
    for index, eintrag in enumerate(register["quellen"]):
        if (
            not isinstance(eintrag, dict)
            or not isinstance(eintrag.get("datei"), str)
            or not eintrag["datei"]
            or not isinstance(eintrag.get("sha256"), str)
            or len(eintrag["sha256"]) != 64
        ):
            raise FallFehler(
                f"Eingangs-Registereintrag {index} braucht nichtleere "
                f"'datei' und 64-stelliges 'sha256' ({fall / EINGANG_REGISTER})"
            )
    return register


def registrieren(
    fall: Path, datei: Path, als: Optional[str] = None
) -> Dict[str, Any]:
    """Quelle in den Eingang aufnehmen: kopieren, hashen, schreibschuetzen.

    Geprueft werden BEIDE Seiten — Register und Dateisystem —, weil sie
    auseinanderlaufen koennen und der Eingang die Zone ist, die nicht
    regenerierbar ist:

    * Registriert mit gleichem Hash und passender Kopie: ``bereits_registriert``.
    * Registriert, Kopie fehlt: ``wiederhergestellt`` (Register bleibt).
    * Registriert, Kopie weicht ab: harter Fehler (Integritaetsverletzung
      wird nicht durch einen Schreibvorgang zugedeckt).
    * Registriert mit anderem Hash: harter Konflikt, beide Hashes in der
      Meldung, kein stiller Overwrite.
    * Unregistrierte Datei gleichen Namens im Eingang: gleicher Inhalt
      wird ``nachgetragen`` (repariert das Abbruchfenster), anderer
      Inhalt ist ein harter Konflikt.
    """
    if datei.is_symlink():
        raise FallFehler(
            f"Quelle ist ein Symlink: {datei} — auch gueltige und dangling "
            "Symlinks sind fuer die Registrierung unzulaessig"
        )
    if not datei.is_file():
        raise FallFehler(f"Quelle nicht gefunden: {datei}")
    name = _pruefe_eingangsname(als or datei.name)
    with _registrierungs_lock(fall):
        return _registrieren_gesperrt(fall, datei, name)


def _registrieren_gesperrt(
    fall: Path, datei: Path, name: str
) -> Dict[str, Any]:
    """Registrierung unter dem exklusiven fallbezogenen Register-Lock."""
    register = _lade_register(fall)
    eingang = verzeichnisse(fall)["eingang"]
    if eingang.is_symlink():
        raise FallFehler(
            f"Eingangszone ist ein Symlink: {eingang} — Registrierung verweigert"
        )
    if not eingang.is_dir():
        raise FallFehler(f"Eingangszone ist kein Verzeichnis: {eingang}")
    ziel = eingang / name
    if ziel.is_symlink():
        raise FallFehler(
            f"Eingangsziel {name!r} ist ein Symlink — auch gueltige und "
            "dangling Symlinks sind im Eingang unzulaessig"
        )
    neu_hash = _sha256(datei)
    eintrag_vorhanden = {q["datei"]: q for q in register["quellen"]}.get(name)
    kopie_hash = _sha256(ziel) if ziel.is_file() else None

    if eintrag_vorhanden is not None:
        alt_hash = eintrag_vorhanden["sha256"]
        if alt_hash != neu_hash:
            raise FallFehler(
                f"Eingangs-Konflikt fuer {name!r}: registriert ist "
                f"sha256={alt_hash}, angeboten wird sha256={neu_hash} — der "
                "Eingang wird nie still ueberschrieben. Anderen Namen (--als) "
                "waehlen oder den Konflikt als eigenen Vorgang aufloesen."
            )
        if kopie_hash == neu_hash:
            if _ist_schreibbar(ziel):
                raise FallFehler(
                    f"Eingangs-Kopie {name!r} ist schreibbar — eine "
                    "Integritaetsverletzung wird nicht durch erneutes "
                    "Registrieren zugedeckt"
                )
            return {"fall": str(fall), "datei": name, "sha256": neu_hash,
                    "status": "bereits_registriert"}
        if kopie_hash is not None:
            raise FallFehler(
                f"Eingangs-Kopie {name!r} weicht vom Register ab "
                f"(registriert {alt_hash}, vorgefunden {kopie_hash}) — eine "
                "Integritaetsverletzung wird nicht durch erneutes "
                "Registrieren zugedeckt; 'fall status' zeigt den Befund, die "
                "Aufloesung ist ein eigener Vorgang."
            )
        _kopiere_geschuetzt(datei, ziel, neu_hash)
        return {"fall": str(fall), "datei": name, "sha256": neu_hash,
                "status": "wiederhergestellt"}

    if kopie_hash is not None and kopie_hash != neu_hash:
        raise FallFehler(
            f"unregistrierte Datei {name!r} liegt bereits im Eingang "
            f"(sha256={kopie_hash}) und weicht vom Angebot ab "
            f"(sha256={neu_hash}) — der Eingang wird nie still "
            "ueberschrieben; anderen Namen (--als) waehlen oder die "
            "vorhandene Datei bewusst entfernen."
        )
    kopierte_bytes: Optional[int] = None
    if kopie_hash is None:
        kopierte_bytes = _kopiere_geschuetzt(datei, ziel, neu_hash)
        status_wort = "registriert"
    else:
        # Kopie liegt bereits inhaltsgleich im Eingang: der Registereintrag
        # fehlt (Abbruch zwischen Kopie und Registerschreiben). Nachtragen
        # statt neu schreiben — sonst bliebe der Fall unbenutzbar.
        _schuetze_datei(ziel)
        status_wort = "nachgetragen"
    if ziel.is_symlink() or _sha256(ziel) != neu_hash:
        raise FallFehler(
            f"Eingangsziel {name!r} wurde waehrend der Registrierung "
            "geaendert — Register bleibt unveraendert"
        )
    ziel_groesse = _dateigroesse(ziel)
    if kopierte_bytes is not None and kopierte_bytes != ziel_groesse:
        raise FallFehler(
            f"Eingangsziel {name!r} wurde waehrend der Registrierung "
            "geaendert — Register bleibt unveraendert"
        )
    eintrag = {
        "datei": name,
        "sha256": neu_hash,
        "bytes": ziel_groesse,
        "quelle_pfad": str(datei),
        "registriert_am": _jetzt_utc(),
    }
    register["quellen"] = sorted(
        [*register["quellen"], eintrag], key=lambda q: q["datei"]
    )
    _schreibe_json(fall / EINGANG_REGISTER, register)
    return {"fall": str(fall), **eintrag, "status": status_wort}


def pruefen(fall: Path) -> List[str]:
    """Integritaet des Eingangs gegen das Register (leer = in Ordnung)."""
    fehler: List[str] = []
    register = _lade_register(fall)
    eingang = verzeichnisse(fall)["eingang"]
    if eingang.is_symlink():
        return [
            "eingang/: Symlink statt Eingangsverzeichnis — die Eingangszone "
            "darf keine Symlinks enthalten"
        ]
    if not eingang.is_dir():
        return ["eingang/: Eingangsverzeichnis fehlt"]
    registriert = set()
    for q in register["quellen"]:
        registriert.add(q["datei"])
        try:
            _pruefe_eingangsname(q["datei"])
        except FallFehler as exc:
            fehler.append(f"Register: {exc}")
            continue
        pfad = eingang / q["datei"]
        if pfad.is_symlink():
            fehler.append(
                f"eingang/{q['datei']}: Symlink registriert — "
                "Symlinks sind im Eingang unzulaessig"
            )
            continue
        if not pfad.is_file():
            fehler.append(f"eingang/{q['datei']}: registriert, aber Datei fehlt")
            continue
        try:
            ist = _sha256(pfad)
        except FallFehler as exc:
            fehler.append(f"eingang/{q['datei']}: {exc}")
            continue
        if ist != q["sha256"]:
            fehler.append(
                f"eingang/{q['datei']}: Inhalt weicht vom Register ab "
                f"(registriert {q['sha256'][:12]}…, vorgefunden {ist[:12]}…)"
            )
        try:
            if _ist_schreibbar(pfad):
                fehler.append(
                    f"eingang/{q['datei']}: registrierte Kopie ist schreibbar"
                )
        except FallFehler as exc:
            fehler.append(f"eingang/{q['datei']}: {exc}")
    for pfad in sorted(eingang.iterdir()):
        if pfad.is_symlink():
            einordnung = (
                "registriert" if pfad.name in registriert else "ohne Registrierung"
            )
            meldung = f"eingang/{pfad.name}: Symlink {einordnung}"
            if not any(vorhanden.startswith(meldung) for vorhanden in fehler):
                fehler.append(
                    f"{meldung} — Symlinks sind im Eingang unzulaessig"
                )
            continue
        if pfad.name in registriert and pfad.is_file():
            continue
        art = "Verzeichnis" if pfad.is_dir() else "Datei"
        fehler.append(
            f"eingang/{pfad.name}: {art} ohne Registrierung — der "
            "Eingang kennt nur registrierte Quellen und ist flach"
        )
    return fehler


def eingang_datei(fall: Path, name: str) -> Path:
    """Pfad einer registrierten Quelle — nur nach bestandener Pruefung."""
    register = _lade_register(fall)
    namen = [q["datei"] for q in register["quellen"]]
    if name not in namen:
        raise FallFehler(
            f"Quelle {name!r} ist im Fall nicht registriert "
            f"(registriert: {', '.join(namen) or '—'})"
        )
    fehler = pruefen(fall)
    if fehler:
        raise FallFehler(
            "Eingang verletzt das Register — kein Lauf auf unklarem "
            "Eingang: " + "; ".join(fehler)
        )
    return verzeichnisse(fall)["eingang"] / name


def status(fall: Path) -> Dict[str, Any]:
    """Zustand des Arbeitsbereichs als ein JSON-faehiges Objekt."""
    manifest = _lade_json(fall / FALL_MANIFEST, "Fall-Manifest")
    register = _lade_register(fall)
    fehler = pruefen(fall)
    v = verzeichnisse(fall)
    return {
        "fall": str(fall),
        "manifest": manifest,
        "quellen": register["quellen"],
        "eingang_integritaet": {"in_ordnung": not fehler, "fehler": fehler},
        "abgeleitet": {
            name: verz.exists()
            for name, verz in v.items()
            if name.endswith("_dir")
        },
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fall", description="Fall-Arbeitsbereich anlegen und fuehren."
    )
    sub = parser.add_subparsers(dest="kommando", required=True)

    p = sub.add_parser("anlegen", help="Arbeitsbereich anlegen.")
    p.add_argument("--fall", required=True, help="Pfad des Arbeitsbereichs.")
    p.add_argument("--beschreibung", default="", help="Freitext zum Fall.")
    p.add_argument(
        "--scope", choices=FALL_SCOPES, default="tarif",
        help="Fachlicher Fall-Scope: tarif (Default) oder bestand.",
    )

    p = sub.add_parser("registrieren", help="Quelle in den Eingang aufnehmen.")
    p.add_argument("--fall", required=True)
    p.add_argument("--datei", required=True, help="Zu registrierende Datei.")
    p.add_argument("--als", default=None,
                   help="Name im Eingang (Default: Dateiname).")

    p = sub.add_parser("status", help="Register, Integritaet, Verzeichnisse.")
    p.add_argument("--fall", required=True)
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    fall = Path(args.fall)
    try:
        if args.kommando == "anlegen":
            ergebnis = anlegen(fall, args.beschreibung, args.scope)
        elif args.kommando == "registrieren":
            ergebnis = registrieren(fall, Path(args.datei), args.als)
        else:
            ergebnis = status(fall)
    except FallFehler as exc:
        print(f"fall: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"fall: Dateisystemfehler: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(ergebnis, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
