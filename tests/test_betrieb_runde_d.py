"""Der Betrieb nach dem blinden Angriff, Runde D: Ausfall und Beleg.

Vier bestaetigte Funde, je ein roter Test vor dem Fix (Vorlagen: die
Repro-Skripte der Angreifer, hier als pytest nachgebaut):

* Fund 5 — Ein Ein-/Ausgabefehler beim Anfuegen der Protokollzeile, der
  erst kommt, NACHDEM die Zeile auf der Platte steht (Fehler beim
  Schliessen, kurzer Schreibvorgang ohne das Zeilenende), meldete Exit 2
  "nicht geschrieben" — der naechste Lauf fand den Tag gruen vor.
* Fund 6 — Schreibreste eines abgebrochenen Laufs (Punkt-Tempdateien,
  darunter der Hardlink-Zwilling eines 0444-Abschlusses) blieben fuer
  immer in der Ablage.
* Fund 7 — Der Export kopierte den Bestandsbericht ungeprueft ins Paket;
  keine Protokollzeile band ihn, der gezeichnete Anker band die Faelschung.
* Fund 8 — Derselbe Export folgte einem Symlink in ``berichte/`` und legte
  eine Datei von ausserhalb der Ablage ins Paket, auch den
  Betriebsschluessel.

Knoten: system/betrieb
"""

from __future__ import annotations

import datetime as dt
import errno
import hashlib
import json
import os
import shutil
from pathlib import Path

import pandas as pd
import pytest

from rechner_pipeline.bestand.parquet_io import read_portfolio, write_portfolio
from rechner_pipeline.betrieb import seite as st
from rechner_pipeline.betrieb import tageslauf as tl
from rechner_pipeline.betrieb.tageslauf import EXIT_OK, Ablage, lies_protokoll, tageslauf
from tests.freigabe_testschluessel import zeichne_neu
from tests.test_betrieb_seite import _ablage
from tests.test_betriebsschluessel_runde_c import mit_eingang, uebernommen  # noqa: F401

FEB = "bestandsbericht_2026-02-01.html"


def _kopie(quelle: Path, ziel: Path) -> Ablage:
    shutil.copytree(quelle, ziel, symlinks=True)
    return Ablage(ziel)


@pytest.fixture(scope="module")
def zwei_tage(tmp_path_factory):
    """Zwei gruene Laeufe (31.1., 3.2.); der 3.2. schreibt den Abschluss
    zum 1.2. samt Bestandsbericht."""
    ablage = _ablage(tmp_path_factory.mktemp("rd") / "plv")
    assert tageslauf(ablage, dt.date(2026, 1, 31))[0] == EXIT_OK
    assert tageslauf(ablage, dt.date(2026, 2, 3))[0] == EXIT_OK
    return ablage.wurzel


@pytest.fixture()
def gefuehrt(zwei_tage, tmp_path):
    return _kopie(zwei_tage, tmp_path / "plv")


def _gruene_tage(ablage: Ablage) -> list:
    return [z["heute"] for z in lies_protokoll(ablage.protokoll_pfad) if z.get("uebernommen")]


# --------------------------------------------------------------------------- #
# Fund 5: ein gruen gefuehrter Tag wird nie als Fehlschlag gemeldet
# --------------------------------------------------------------------------- #


class _Stoerdatei:
    """Das Protokoll im Anhaengemodus, mit einem Ein-/Ausgabefehler nach
    (oder waehrend) des Schreibens — die Vorlage repro_01 der Angreifer."""

    def __init__(self, f, art):
        self.f, self.art = f, art

    def write(self, text):
        if self.art == "close_eio":
            return self.f.write(text)
        if self.art == "kurz_ohne_umbruch":
            assert text.endswith("\n")
            self.f.write(text[:-1])
            self.f.flush()
            raise OSError(errno.ENOSPC, "No space left on device (kurzer Schreibvorgang)")
        self.f.write(text[: len(text) // 2])
        self.f.flush()
        raise OSError(errno.ENOSPC, "No space left on device (halbe Zeile)")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.f.close()
        if self.art == "close_eio" and a[0] is None:
            raise OSError(errno.EIO, "Input/output error (close nach Rueckschreiben)")
        return False


def _stoere_protokoll(monkeypatch, art: str) -> None:
    """Nur das Anfuegen der Zeile (Textmodus ``a``) wird gestoert; das
    Abschliessen einer Zeile ohne Umbruch (``ab``) nicht."""
    echt = open

    def gestoert(pfad, mode="r", *a, **kw):
        f = echt(pfad, mode, *a, **kw)
        if str(pfad).endswith(tl.PROTOKOLL_DATEI) and mode == "a":
            return _Stoerdatei(f, art)
        return f

    monkeypatch.setattr(tl, "open", gestoert, raising=False)


@pytest.mark.parametrize("art", ["close_eio", "kurz_ohne_umbruch"])
def test_ein_gruen_gefuehrter_tag_wird_nicht_als_fehlschlag_gemeldet(gefuehrt, monkeypatch, art):
    """Soll unabhaengig: der naechste, ungestoerte Lauf findet den Tag als
    'bereits gefuehrt' vor — dann war er gefuehrt, und der gestoerte Lauf
    sagt dasselbe (Exit 0, Seite nennt den Tag, Marker weg).
    Mutationsprobe: im except-Zweig um _anfuegen die Nachschau
    (_zeile_steht) entfernen -> rot."""
    _stoere_protokoll(monkeypatch, art)
    code, zeile = tageslauf(gefuehrt, dt.date(2026, 2, 4))
    monkeypatch.delattr(tl, "open")
    assert (code, zeile.get("uebernommen")) == (EXIT_OK, True)
    assert gefuehrt.protokoll_pfad.read_bytes().endswith(b"\n")
    assert _gruene_tage(gefuehrt)[-1] == "2026-02-04"
    assert st.seiten_stand(gefuehrt.wurzel / st.SEITE_DIR / "index.html") == dt.date(2026, 2, 4)
    assert not gefuehrt.publish_marker.exists()
    code2, zeile2 = tageslauf(gefuehrt, dt.date(2026, 2, 4))
    assert (code2, zeile2.get("bereits_gefuehrt")) == (EXIT_OK, True)


def test_eine_halbe_zeile_bleibt_ein_fehlschlag(gefuehrt, monkeypatch):
    """Positivkontrolle: steht nur ein Fragment da, ist der Tag NICHT
    gefuehrt — der Lauf meldet es, die Seite bleibt beim Vortag, und der
    naechste Lauf schneidet das Fragment und fuehrt den Tag."""
    _stoere_protokoll(monkeypatch, "halb")
    with pytest.raises(tl.TageslaufError, match="Protokollzeile fuer 2026-02-04 nicht geschrieben"):
        tageslauf(gefuehrt, dt.date(2026, 2, 4))
    monkeypatch.delattr(tl, "open")
    assert st.seiten_stand(gefuehrt.wurzel / st.SEITE_DIR / "index.html") == dt.date(2026, 2, 3)
    assert tageslauf(gefuehrt, dt.date(2026, 2, 4))[0] == EXIT_OK
    assert _gruene_tage(gefuehrt)[-1] == "2026-02-04"


# --------------------------------------------------------------------------- #
# Fund 6: Schreibreste eines abgebrochenen Laufs werden weggeraeumt
# --------------------------------------------------------------------------- #


def _reste(ablage: Ablage) -> list:
    return sorted(str(p.relative_to(ablage.wurzel)) for p in ablage.wurzel.rglob(".*.tmp"))


def test_der_naechste_lauf_raeumt_die_schreibreste_seiner_ziele(gefuehrt):
    """Vorlage repro_02: Prozesstod zwischen os.link und unlink (Zwilling des
    0444-Abschlusses), vor os.replace des Berichts, des Journals und des
    Publish-Markers. Soll: nach dem naechsten Lauf der Zustand des
    ungestoerten Laufs — keine Reste, der Abschluss traegt einen Namen.
    Fremde Punktdateien bleiben. Mutationsprobe: den Aufruf von
    _raeume_schreibreste in tageslauf() entfernen -> rot."""
    abschluss = gefuehrt.abschluesse / "abschluss_2026-02-01.parquet"
    zwilling = gefuehrt.abschluesse / ".abschluss_2026-02-01.parquet.0123456789abcdef.tmp"
    os.link(abschluss, zwilling)
    assert abschluss.stat().st_nlink == 2
    (gefuehrt.berichte / f".{FEB}.00aa.tmp").write_text("<html>halb", encoding="utf-8")
    (gefuehrt.journal / ".tagesjournal.parquet.00bb.tmp").write_bytes(b"PAR1")
    (gefuehrt.wurzel / ".publish.json.00cc.tmp").write_text("{", encoding="utf-8")
    fremd = [gefuehrt.berichte / ".notiz.tmp", gefuehrt.abschluesse / ".fremd.parquet.1.tmp",
             gefuehrt.wurzel / ".lauf.lock.1.tmp"]
    for p in fremd:
        p.write_text("fremd", encoding="utf-8")
    assert tageslauf(gefuehrt, dt.date(2026, 2, 4))[0] == EXIT_OK
    assert _reste(gefuehrt) == sorted(str(p.relative_to(gefuehrt.wurzel)) for p in fremd)
    assert abschluss.stat().st_nlink == 1
    assert abschluss.stat().st_mode & 0o777 == 0o444


def test_auch_ein_bereits_gefuehrter_tag_raeumt(gefuehrt):
    """Der Wiederholungslauf desselben Tags (repro_02: 'danach [0, 0, 0]')
    fuehrt nichts — aufgeraeumt wird trotzdem, unter der Sperre."""
    zwilling = gefuehrt.abschluesse / ".abschluss_2026-02-01.parquet.00dd.tmp"
    os.link(gefuehrt.abschluesse / "abschluss_2026-02-01.parquet", zwilling)
    code, zeile = tageslauf(gefuehrt, dt.date(2026, 2, 3))
    assert (code, zeile.get("bereits_gefuehrt")) == (EXIT_OK, True)
    assert _reste(gefuehrt) == []


def test_write_portfolio_raeumt_den_zwilling_seines_ziels(tmp_path):
    """Das exklusive Schreiben raeumt einen Hardlink-Zwilling des Ziels beim
    naechsten Schreiben desselben Ziels — auch wenn es selbst mit
    FileExistsError endet. Eine Tempdatei, die NICHT der Zwilling ist, kann
    einem gleichzeitigen Schreiber gehoeren und bleibt (der Tageslauf raeumt
    sie unter seiner Sperre). Mutationsprobe: das Zwillingsraeumen in
    write_portfolio entfernen -> rot."""
    ziel = tmp_path / "abschluss_2026-02-01.parquet"
    df = pd.DataFrame({"police_id": [1, 2]}).astype({"police_id": "int64"})
    write_portfolio(df, ziel, exklusiv=True)
    zwilling = tmp_path / f".{ziel.name}.feedfacecafebeef.tmp"
    os.link(ziel, zwilling)
    anderer = tmp_path / f".{ziel.name}.0000000000000000.tmp"
    anderer.write_bytes(b"im Bau")
    with pytest.raises(FileExistsError):
        write_portfolio(df, ziel, exklusiv=True)
    assert not zwilling.exists()
    assert anderer.exists()
    assert ziel.stat().st_nlink == 1


# --------------------------------------------------------------------------- #
# Fund 7: der Bestandsbericht ist bezeugt, bevor er ins Paket geht
# --------------------------------------------------------------------------- #


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_die_protokollzeile_bindet_den_bericht(gefuehrt):
    """Soll unabhaengig: der Hash der Datei, die der Lauf geschrieben hat."""
    zeile = lies_protokoll(gefuehrt.protokoll_pfad)[-1]
    feb = next(a for a in zeile["abschluesse"] if a["stichtag"] == "2026-02-01")
    assert feb["bericht"] == FEB
    assert feb["bericht_sha256"] == _sha(gefuehrt.berichte / FEB)


def test_der_teilbestandsbericht_ist_ebenso_gebunden(uebernommen):  # noqa: F811
    zeile = lies_protokoll(Ablage(uebernommen.wurzel).protokoll_pfad)[-1]
    teile = [t for a in zeile["abschluesse"] for t in a.get("teilbestaende") or []]
    assert teile, "die Testwelt fuehrt keinen Teilbestandsbericht"
    for t in teile:
        assert t["bericht_sha256"] == _sha(uebernommen.berichte / t["bericht"])


def test_ein_ersetzter_bericht_geht_nicht_ins_paket(gefuehrt, tmp_path):
    """Vorlage f1_bericht.py: ein Schreiber OHNE Schluessel ersetzt den
    Bericht. Soll: der Export verweigert mit Ausweg, es entsteht kein Paket
    und kein Ankersatz. Mutationsprobe: den Hashvergleich im Export
    entfernen -> rot."""
    (gefuehrt.berichte / FEB).write_bytes(
        b"<html><body>Deckungskapital gesamt: 9.999.999.999,00 EUR</body></html>")
    with pytest.raises(st.SeiteError, match="nicht der Bericht, den das Protokoll") as fehler:
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert "Ausweg" in str(fehler.value)
    assert not (tmp_path / "paket").exists()
    assert not (tmp_path / "anker" / "anker.jsonl").exists()


def test_ein_ersetzter_teilbestandsbericht_geht_nicht_ins_paket(uebernommen, tmp_path):  # noqa: F811
    zeile = lies_protokoll(Ablage(uebernommen.wurzel).protokoll_pfad)[-1]
    teil = next(t for a in zeile["abschluesse"] for t in a.get("teilbestaende") or [])
    (uebernommen.berichte / teil["bericht"]).write_bytes(b"<html>gefaelscht</html>")
    with pytest.raises(st.SeiteError, match="nicht der Bericht, den das Protokoll"):
        st.stands_paket(uebernommen, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")


def test_der_unveraenderte_bericht_geht_ins_paket(gefuehrt, tmp_path):
    """Positivkontrolle: dieselben Bytes wie in der Ablage, im Paket gelistet."""
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert (paket / FEB).read_bytes() == (gefuehrt.berichte / FEB).read_bytes()
    stand = json.loads((paket / st.PAKET_DATEI).read_text(encoding="utf-8"))
    assert stand["dateien"][FEB] == _sha(gefuehrt.berichte / FEB)


def test_ein_unbezeugter_bericht_bleibt_draussen(gefuehrt, tmp_path, capsys):
    """Bestehende Ablagen: Zeilen vor Runde D nennen den Bericht ohne Hash.
    Entscheid: der Export nimmt ihn NICHT ins Paket und sagt 'nicht
    bezeugt' — ein Bericht ohne Bindung waere wieder zu glauben. Der Tag
    selbst bleibt exportierbar."""
    rohe = [z for z in gefuehrt.protokoll_pfad.read_text(encoding="utf-8").split("\n") if z]
    zeile = json.loads(rohe[-1])
    for a in zeile["abschluesse"]:
        a.pop("bericht_sha256", None)
    rohe[-1] = json.dumps(zeichne_neu(zeile), ensure_ascii=False, sort_keys=True)
    gefuehrt.protokoll_pfad.write_text("\n".join(rohe) + "\n", encoding="utf-8")
    paket = st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert not (paket / FEB).exists()
    stand = json.loads((paket / st.PAKET_DATEI).read_text(encoding="utf-8"))
    assert FEB not in stand["dateien"]
    assert f"{FEB} nicht bezeugt" in capsys.readouterr().err


# --------------------------------------------------------------------------- #
# Fund 8: das Paket traegt nur Bytes aus der Ablage
# --------------------------------------------------------------------------- #


def test_ein_symlink_auf_den_betriebsschluessel_verlaesst_die_ablage_nicht(gefuehrt, tmp_path):
    """Vorlage f2_symlink.py: der Bericht wird durch einen Symlink auf den
    Betriebsschluessel ersetzt. Soll unabhaengig: keine Datei ausserhalb der
    Ablage traegt die Schluesselbytes. Mutationsprobe: die Pruefung in
    _bytes_aus_der_ablage auf S_ISLNK entfernen -> rot (der Hashvergleich
    des Fund 7 faengt es auch; siehe den naechsten Test fuer Fund 8 allein)."""
    schluessel = Path(tl._STANDARD_BETRIEBSZEICHNUNG[0])
    (gefuehrt.berichte / FEB).unlink()
    os.symlink(schluessel, gefuehrt.berichte / FEB)
    with pytest.raises(st.SeiteError, match="Symlink"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    geheim = schluessel.read_bytes()
    assert not any(p.is_file() and p.read_bytes() == geheim
                   for p in tmp_path.rglob("*") if not p.is_symlink())


def _ausserhalb(quelle: Path, tmp_path: Path) -> Path:
    """Eine byte-gleiche Kopie AUSSERHALB der Ablage — der Hash stimmt, nur
    der Ort nicht. Damit misst der Test Fund 8 allein."""
    kopie = tmp_path / "draussen" / quelle.name
    kopie.parent.mkdir(exist_ok=True)
    kopie.write_bytes(quelle.read_bytes())
    return kopie


@pytest.mark.parametrize("was", ["bericht", "abschluss", "protokoll"])
@pytest.mark.parametrize("art", ["symlink", "hardlink"])
def test_eine_gelinkte_quelle_geht_nicht_ins_paket(gefuehrt, tmp_path, was, art):
    """Jede Datei, die der Export kopiert, muss eine regulaere Datei der
    Ablage mit genau einem Namen sein. Byte-gleich, damit keine Hashpruefung
    sie faengt. Mutationsprobe: _bytes_aus_der_ablage durch read_bytes
    ersetzen -> rot."""
    quelle = {"bericht": gefuehrt.berichte / FEB,
              "abschluss": gefuehrt.abschluesse / "abschluss_2026-02-01.parquet",
              "protokoll": gefuehrt.protokoll_pfad}[was]
    draussen = _ausserhalb(quelle, tmp_path)
    quelle.chmod(0o644)
    quelle.unlink()
    if art == "symlink":
        os.symlink(draussen, quelle)
        muster = "Symlink"
    else:
        os.link(draussen, quelle)
        muster = "2 Namen"
    with pytest.raises(st.SeiteError, match=muster) as fehler:
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
    assert "Ausweg" in str(fehler.value)
    assert not (tmp_path / "paket").exists()


def test_ein_verzeichnis_symlink_fuehrt_nicht_aus_der_ablage(gefuehrt, tmp_path):
    """Der aufgeloeste Pfad zaehlt, nicht nur die Datei: ``berichte/`` selbst
    als Symlink nach draussen."""
    draussen = tmp_path / "draussen-berichte"
    shutil.copytree(gefuehrt.berichte, draussen)
    shutil.rmtree(gefuehrt.berichte)
    os.symlink(draussen, gefuehrt.berichte)
    with pytest.raises(st.SeiteError, match="ausserhalb der Ablage"):
        st.stands_paket(gefuehrt, tmp_path / "paket", anker_verzeichnis=tmp_path / "anker")
