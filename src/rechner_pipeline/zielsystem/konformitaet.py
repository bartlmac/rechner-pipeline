"""Konformitaet: was jede Implementierung des Zielvertrags bestehen muss.

``pruefe`` liefert Befunde (leer = konform), die Tests fahren sie gegen
den Anbieter (``tests/test_zielsystem.py``). Jede Regel hat dort eine
Positivkontrolle mit einer absichtlich falschen Implementierung.

Eine Implementierung, die statt zu antworten eine Ausnahme wirft, ist
ein Befund und kein Absturz des Pruefers (A-053, B1): Der Vertrag
verspricht Befunde, und eine fehlerhafte Implementierung ist genau das,
was die Pruefung finden soll.

Je Faehigkeit mit Protokoll prueft ``PRUEFUNG_JE_FAEHIGKEIT`` ueber die
Form hinaus, was das Protokoll in Worten verlangt (Stufe 1: die
Rechnungsgrundlagen, Stufe 2: die Bewertung, Stufe 3: die Bestandsdaten
und die wirksame Tarifzelle der Fuehrung, Stufe 4: die Bestandspruefung).

Knoten: system/zielsystem
"""

from __future__ import annotations

import re
import hashlib
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
from typing import Callable, List, Mapping

from rechner_pipeline.zielsystem.bewertung import Vorgangsregeln
from rechner_pipeline.zielsystem.bestandsdaten import (
    BestandsdatenFehler, Erfahrungsannahmen, Fuehrungsansicht,
    Fuehrungsgeneration, Laufmanifest, Verankerungsrolle,
)
from rechner_pipeline.zielsystem.bestandspruefung import (
    Fortschreibungspruefung, ManifestNachrechnung, PB1Pruefung,
    Rollenbeschreibung,
)
from rechner_pipeline.zielsystem.rechnungsgrundlagen import Parametersatz
from rechner_pipeline.zielsystem.version import VERTRAG_VERSION, vertraeglich, zerlege
from rechner_pipeline.zielsystem.vertrag import FAEHIGKEITEN, PROTOKOLL_JE_FAEHIGKEIT, Zielsystem

__all__ = [
    "PRUEFUNG_JE_FAEHIGKEIT", "pruefe", "pruefe_bestandsdaten",
    "pruefe_bestandspruefung", "pruefe_bewertung", "pruefe_rechnungsgrundlagen",
]

_NAME = re.compile(r"^[a-z][a-z0-9_]*$")

# Eine vollstaendige synthetische Config mit genau einer Tarifzelle.
# Sie ist ein Testeingang des Vertrags und liest keine PLV-Datei.
_FUEHRUNGSTEXT = '''[meta]
seed=1
[[generation]]
name="PROBE"
produkt="klv"
knoten="klv/probe"
gueltig_von=2026-01-01
gueltig_bis=2027-01-01
max_endalter=80
zins=0.01
tafel="DAV2008_T_NR_U70"
[generation.verteilungen.entry_age]
typ="empirical_discrete"
values=[40]
probs=[1.0]
[generation.verteilungen.sex]
typ="empirical_discrete"
values=["M"]
probs=[1.0]
[generation.verteilungen.duration]
typ="empirical_discrete"
values=[20]
probs=[1.0]
[generation.verteilungen.premium_duration]
typ="empirical_discrete"
values=[10]
probs=[1.0]
[generation.verteilungen.sum_insured]
typ="empirical_discrete"
values=[100000]
probs=[1.0]
[generation.verteilungen.zahlweise]
typ="empirical_discrete"
values=[12]
probs=[1.0]
[[generation.zelle]]
auspraegungen={status="A"}
zins=0.02
'''


@dataclass(frozen=True)
class _ProbeRate:
    a: float = 0.0
    b: float = 0.0

    def __call__(self, _erste_ordnung: float) -> float:
        return self.a


def _fuehrungsprobe_ansicht() -> Fuehrungsansicht:
    rate = _ProbeRate()
    return Fuehrungsansicht(
        generationen=(Fuehrungsgeneration("PROBE", MappingProxyType({
            "scheiben_mit_gamma1": False, "stoab_je_baustein": False,
            "red_verfahren": "prospektiv", "tku_umfang": "alle_bausteine",
        })),),
        annahmen=Erfahrungsannahmen(
            tod=rate, storno=rate, beitragsfreistellung=rate, erhoehung=rate,
            herabsetzung=rate, teilkuendigung=rate, invalidisierung=rate,
            reaktivierung=rate, aktivensterblichkeit=rate,
            invalidensterblichkeit=rate, erh_prozent=0.0,
            red_anteil=0.0, tk_anteil=0.0,
        ),
        config_text=_FUEHRUNGSTEXT,
    )


def _ausnahme(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {exc}"


def pruefe_rechnungsgrundlagen(umsetzung: object) -> List[str]:
    """Was das Protokoll ``Rechnungsgrundlagen`` in Worten verlangt: ein
    Produkt mindestens, je Produkt ein Parametersatz mit eindeutigen
    Feldern, dessen Defaults Felder sind, ``KeyError`` fuer ein unbekanntes
    Produkt, Tafelnamen als frozenset von str, ``ValueError`` fuer eine
    leere Alterstafel und fuer einen leeren Tafelspeicher (A-054, H1)."""
    befunde: List[str] = []
    produkte: frozenset = frozenset()
    try:
        roh = umsetzung.produkte()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001 - die Ausnahme ist der Befund
        befunde.append(f"produkte() wirft {_ausnahme(exc)}")
    else:
        if isinstance(roh, frozenset) and roh and all(isinstance(p, str) for p in roh):
            produkte = roh
        else:
            befunde.append(f"produkte() liefert {roh!r}, erwartet ein nicht leeres frozenset von str")
    for produkt in sorted(produkte):
        try:
            satz = umsetzung.parametersatz(produkt)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"parametersatz({produkt!r}) wirft {_ausnahme(exc)}")
            continue
        if not isinstance(satz, Parametersatz):
            befunde.append(
                f"parametersatz({produkt!r}) liefert {type(satz).__name__}, erwartet Parametersatz")
            continue
        if satz.produkt != produkt:
            befunde.append(f"parametersatz({produkt!r}) nennt das Produkt {satz.produkt!r}")
        namen = satz.feldnamen()
        if not namen or len(set(namen)) != len(namen):
            befunde.append(f"parametersatz({produkt!r}): Felder leer oder doppelt: {namen}")
        fremd = sorted(set(satz.defaults) - set(namen))
        if fremd:
            befunde.append(f"parametersatz({produkt!r}): Defaults ohne Feld: {fremd}")
    try:
        umsetzung.parametersatz("kein_produkt")  # type: ignore[attr-defined]
    except KeyError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"parametersatz('kein_produkt') wirft {_ausnahme(exc)}, erwartet KeyError")
    else:
        befunde.append("parametersatz('kein_produkt') liefert etwas, erwartet KeyError")
    try:
        tafeln = umsetzung.verfuegbare_tafeln()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"verfuegbare_tafeln() wirft {_ausnahme(exc)}")
    else:
        if not isinstance(tafeln, frozenset) or not all(isinstance(t, str) for t in tafeln):
            befunde.append(
                f"verfuegbare_tafeln() liefert {type(tafeln).__name__}, erwartet frozenset von str")
    for aufruf, text in (
            (lambda: umsetzung.pruefe_alterstafel("leer", {}), "pruefe_alterstafel('leer', {})"),  # type: ignore[attr-defined]
            (lambda: umsetzung.tafeln_lesen(""), "tafeln_lesen('')")):  # type: ignore[attr-defined]
        try:
            aufruf()
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"{text} wirft {_ausnahme(exc)}, erwartet ValueError")
        else:
            befunde.append(f"{text} geht durch, erwartet ValueError")
    import pandas as pd

    merkmale = pd.DataFrame([{
        "police_id": 1, "dimension": "status", "auspraegung": "A",
    }])
    try:
        aufloesen = umsetzung.fuehrungsgrundlagen(  # type: ignore[attr-defined]
            _fuehrungsprobe_ansicht(), merkmale)
        felder = aufloesen(1, "PROBE")
        if not isinstance(felder, Mapping) or felder.get("zins") != 0.02:
            befunde.append("fuehrungsgrundlagen loest die Tarifzelle nicht wirksam auf")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"fuehrungsgrundlagen gueltig wirft {_ausnahme(exc)}")
    try:
        aufloesen = umsetzung.fuehrungsgrundlagen(  # type: ignore[attr-defined]
            _fuehrungsprobe_ansicht(), None)
        aufloesen(1, "PROBE")
    except ValueError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"fuehrungsgrundlagen ohne Merkmal wirft {_ausnahme(exc)}")
    else:
        befunde.append("fuehrungsgrundlagen akzeptiert fehlende Tarifzelle")
    return befunde


def pruefe_bewertung(umsetzung: object) -> List[str]:
    """Was das Protokoll ``Bewertung`` in Worten verlangt, ohne Wissen
    ueber das Zielsystem: Vorgangsregeln mit Rang je Art (eindeutig),
    einem Verfahren Teilkuendigung unter den Verfahren und mindestens
    einem Umfang; ``ValueError`` fuer einen unbekannten Umfang; eine
    Schicht traegt nie vor ihrer Verankerung und ohne Schicht nie; ein
    Vertrag ohne Felder ist keiner (``TypeError``)."""
    befunde: List[str] = []
    try:
        regeln = umsetzung.vorgangsregeln()  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"vorgangsregeln() wirft {_ausnahme(exc)}")
        regeln = None
    if regeln is not None and not isinstance(regeln, Vorgangsregeln):
        befunde.append(f"vorgangsregeln() liefert {type(regeln).__name__}, erwartet Vorgangsregeln")
        regeln = None
    if regeln is not None:
        raenge = list(regeln.rang.values())
        if (not raenge or not all(isinstance(a, str) for a in regeln.rang)
                or not all(isinstance(r, int) for r in raenge) or len(set(raenge)) != len(raenge)):
            befunde.append(f"vorgangsregeln().rang {dict(regeln.rang)!r}: erwartet Art -> eindeutiger Rang")
        if regeln.teilkuendigung not in regeln.verfahren:
            befunde.append(
                f"vorgangsregeln(): teilkuendigung {regeln.teilkuendigung!r} ist keines der "
                f"Verfahren {list(regeln.verfahren)}")
        if not regeln.umfaenge:
            befunde.append("vorgangsregeln(): keine Umfaenge der Teilkuendigung")
        else:
            try:
                umsetzung.tku_umfang(regeln.verfahren[0], "kein_umfang")  # type: ignore[attr-defined]
            except ValueError:
                pass
            except Exception as exc:  # noqa: BLE001
                befunde.append(f"tku_umfang(.., 'kein_umfang') wirft {_ausnahme(exc)}, erwartet ValueError")
            else:
                befunde.append("tku_umfang(.., 'kein_umfang') liefert etwas, erwartet ValueError")
    try:
        if umsetzung.schicht_traegt(None, 0) is not False:  # type: ignore[attr-defined]
            befunde.append("schicht_traegt(None, 0) ist nicht False")
        if umsetzung.ab_verankerung(5, 4) is not False:  # type: ignore[attr-defined]
            befunde.append("ab_verankerung(5, 4) ist nicht False: vor der Verankerung traegt nichts")
        if umsetzung.ab_verankerung(5, 5) is not True:  # type: ignore[attr-defined]
            befunde.append("ab_verankerung(5, 5) ist nicht True: ab dem Verankerungsmonat traegt die Schicht")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"schicht_traegt/ab_verankerung wirft {_ausnahme(exc)}")
    try:
        umsetzung.vertrag({}, gamma1_uebernehmen=False, stoab_je_baustein=False)  # type: ignore[attr-defined]
    except TypeError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"vertrag({{}}) wirft {_ausnahme(exc)}, erwartet TypeError")
    else:
        befunde.append("vertrag({}) liefert etwas, erwartet TypeError")
    return befunde


def _verankerungsprobe() -> bytes:
    """Eine echte, leere Parquet-Tabelle im gemeinsamen Bestandsformat."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from rechner_pipeline.models.bestand import VERANKERUNG_SPALTEN

    typen = {"int64": pa.int64(), "float64": pa.float64(), "object": pa.string()}
    tabelle = pa.Table.from_arrays(
        [pa.array([], type=typen[dtype]) for _, dtype in VERANKERUNG_SPALTEN],
        names=[name for name, _ in VERANKERUNG_SPALTEN],
    )
    ziel = pa.BufferOutputStream()
    pq.write_table(tabelle, ziel)
    return ziel.getvalue().to_pybytes()


def pruefe_bestandsdaten(umsetzung: object) -> List[str]:
    """Bestands- und Manifestpflichten mit echten Bytes und Fehlerfaellen pruefen."""
    befunde: List[str] = []
    bestand = b"konformitaetsprobe-bestand"
    bestand_sha = hashlib.sha256(bestand).hexdigest()
    verankerung = _verankerungsprobe()
    verankerung_sha = hashlib.sha256(verankerung).hexdigest()
    import pyarrow as pa
    import pyarrow.parquet as pq

    ziel = pa.BufferOutputStream()
    pq.write_table(
        pq.read_table(pa.BufferReader(verankerung)).replace_schema_metadata(
            {b"probe": b"fremd"}), ziel)
    andere_verankerung = ziel.getvalue().to_pybytes()

    def parquet(tabelle: pa.Table) -> bytes:
        ausgabe = pa.BufferOutputStream()
        pq.write_table(tabelle, ausgabe)
        return ausgabe.getvalue().to_pybytes()

    nur_police = parquet(pa.table({"police_id": pa.array([1], type=pa.int64())}))
    keine_spalten = parquet(pa.table({}))
    manifest = {
        "schema_version": 1, "erzeuger": "bestand_migrationszugang",
        "horizont": "2026-01-01", "neuzugang_ab": None,
        "config": {"datei": "probe.toml", "sha256": "0" * 64},
        "ausgaben": {"bestand.parquet": bestand_sha,
                     "verankerung.parquet": verankerung_sha},
    }

    def roh(daten: dict) -> bytes:
        return json.dumps(daten, sort_keys=True).encode("utf-8")

    for titel, manifest_bytes, bestand_bytes, verankerung_bytes, erwartet in (
        ("ohne Manifest und Datei", None, bestand, None,
         Verankerungsrolle(False, bestand_sha, None)),
        ("gültige Verankerung", roh(manifest), bestand, verankerung,
         Verankerungsrolle(True, bestand_sha, verankerung_sha)),
        ("Manifest ohne Verankerungsrolle", roh({**manifest, "ausgaben":
         {"bestand.parquet": bestand_sha}}), bestand, None,
         Verankerungsrolle(False, bestand_sha, None)),
    ):
        try:
            ist = umsetzung.verankerungsrolle(  # type: ignore[attr-defined]
                manifest_bytes=manifest_bytes, bestand_bytes=bestand_bytes,
                verankerung_bytes=verankerung_bytes)
        except Exception as exc:  # noqa: BLE001 - Implementierungsfehler ist ein Befund
            befunde.append(f"verankerungsrolle({titel}) wirft {_ausnahme(exc)}")
        else:
            if type(ist) is not Verankerungsrolle or ist != erwartet:
                befunde.append(f"verankerungsrolle({titel}) liefert {ist!r}, erwartet {erwartet!r}")

    def ohne_rolle() -> dict:
        return {**manifest, "ausgaben": {"bestand.parquet": bestand_sha}}

    fehlerfaelle = (
        ("Rolle ohne Datei", roh(manifest), bestand, None),
        ("Datei ohne Manifest", None, bestand, verankerung),
        ("Datei ohne Rolle", roh(ohne_rolle()), bestand, verankerung),
        ("fremde Bestandsbytes", roh(manifest), b"fremd", verankerung),
        ("fremde Verankerungsbytes", roh(manifest), bestand, b"fremd"),
        ("fremdes gültiges Parquet", roh(manifest), bestand, andere_verankerung),
        ("fehlende Verankerungsspalten", roh({**manifest, "ausgaben":
         {**manifest["ausgaben"], "verankerung.parquet": hashlib.sha256(nur_police).hexdigest()}}),
         bestand, nur_police),
        ("keine Verankerungsspalten", roh({**manifest, "ausgaben":
         {**manifest["ausgaben"], "verankerung.parquet": hashlib.sha256(keine_spalten).hexdigest()}}),
         bestand, keine_spalten),
        ("leere Verankerungsdatei", roh({**manifest, "ausgaben":
         {**manifest["ausgaben"], "verankerung.parquet": hashlib.sha256(b"").hexdigest()}}),
         bestand, b""),
        ("beschädigte Verankerungsdatei", roh({**manifest, "ausgaben":
         {**manifest["ausgaben"], "verankerung.parquet": hashlib.sha256(b"kein Parquet").hexdigest()}}),
         bestand, b"kein Parquet"),
        ("unbekannter Erzeuger", roh({**manifest, "erzeuger": "fremd"}),
         bestand, verankerung),
        ("falscher Erzeuger", roh({**manifest, "erzeuger": "bestand_fortschreibung"}),
         bestand, verankerung),
    )
    for titel, manifest_bytes, bestand_bytes, verankerung_bytes in fehlerfaelle:
        try:
            umsetzung.verankerungsrolle(  # type: ignore[attr-defined]
                manifest_bytes=manifest_bytes, bestand_bytes=bestand_bytes,
                verankerung_bytes=verankerung_bytes)
        except BestandsdatenFehler:
            pass
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"verankerungsrolle({titel}) wirft {_ausnahme(exc)}, erwartet BestandsdatenFehler")
        else:
            befunde.append(f"verankerungsrolle({titel}) geht durch, erwartet BestandsdatenFehler")

    from rechner_pipeline.models.bestand import VERANKERUNG_NAMES

    tabelle = None
    try:
        tabelle = umsetzung.tabelle_aus_bytes(  # type: ignore[attr-defined]
            verankerung, erwartete_spalten=VERANKERUNG_NAMES)
        if tuple(tabelle.columns) != VERANKERUNG_NAMES:
            befunde.append("tabelle_aus_bytes liefert nicht die erwarteten Spalten")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"tabelle_aus_bytes gueltig wirft {_ausnahme(exc)}")
    try:
        umsetzung.tabelle_aus_bytes(b"kein Parquet", erwartete_spalten=VERANKERUNG_NAMES)  # type: ignore[attr-defined]
    except ValueError:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"tabelle_aus_bytes ungueltig wirft {_ausnahme(exc)}, erwartet ValueError")
    else:
        befunde.append("tabelle_aus_bytes akzeptiert ungueltige Bytes")
    try:
        rollen = umsetzung.rollen_dateien()  # type: ignore[attr-defined]
        if not isinstance(rollen, Mapping) or rollen.get("verankerung") != "verankerung.parquet":
            befunde.append("rollen_dateien liefert keine gueltige Verankerungsrolle")
        else:
            try:
                rollen["fremd"] = "fremd.parquet"
            except TypeError:
                pass
            else:
                befunde.append("rollen_dateien ist veraenderbar")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"rollen_dateien wirft {_ausnahme(exc)}")

    with TemporaryDirectory(prefix="zielsystem-bestandsdaten-") as ort:
        wurzel = Path(ort)
        if tabelle is not None:
            ziel = wurzel / "tabelle.parquet"
            try:
                ist = umsetzung.schreibe_tabelle(tabelle, ziel, exklusiv=True)  # type: ignore[attr-defined]
                if ist != ziel or not ziel.is_file():
                    befunde.append("schreibe_tabelle veroeffentlicht die Tabelle nicht")
                umsetzung.schreibe_tabelle(tabelle, ziel, exklusiv=True)  # type: ignore[attr-defined]
            except FileExistsError:
                pass
            except Exception as exc:  # noqa: BLE001
                befunde.append(f"schreibe_tabelle wirft {_ausnahme(exc)}")
            else:
                befunde.append("schreibe_tabelle ignoriert exklusiv=True")
        manifest_pfad = wurzel / "laufmanifest.json"
        manifest_roh = roh(manifest)
        manifest_pfad.write_bytes(manifest_roh)
        try:
            beleg = umsetzung.laufmanifest_lesen(manifest_pfad)  # type: ignore[attr-defined]
            if (type(beleg) is not Laufmanifest or beleg.daten != manifest
                    or beleg.sha256 != hashlib.sha256(manifest_roh).hexdigest()):
                befunde.append("laufmanifest_lesen bindet Inhalt und Hash nicht an dieselben Bytes")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"laufmanifest_lesen gueltig wirft {_ausnahme(exc)}")
        manifest_pfad.write_bytes(b"kein Manifest")
        try:
            umsetzung.laufmanifest_lesen(manifest_pfad)  # type: ignore[attr-defined]
        except BestandsdatenFehler:
            pass
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"laufmanifest_lesen ungueltig wirft {_ausnahme(exc)}")
        else:
            befunde.append("laufmanifest_lesen akzeptiert ungueltige Bytes")
        config = wurzel / "probe.toml"
        config.write_bytes(b"[meta]\n")
        ausgabe = wurzel / "bestand.parquet"
        ausgabe.write_bytes(verankerung)
        for laufart, erzeuger in (
            ("fortschreibung", "bestand_fortschreibung"),
            ("migrationszugang", "bestand_migrationszugang"),
        ):
            try:
                pfad = umsetzung.laufmanifest_schreiben(  # type: ignore[attr-defined]
                    wurzel, horizont=date(2026, 1, 1), neuzugang_ab=None,
                    config_pfad=config, ausgaben=[ausgabe], laufart=laufart)
                geschrieben = json.loads(pfad.read_bytes())
                if (geschrieben.get("erzeuger") != erzeuger
                        or geschrieben.get("ausgaben", {}).get("bestand.parquet")
                        != hashlib.sha256(verankerung).hexdigest()):
                    befunde.append(f"laufmanifest_schreiben({laufart}) bindet Erzeuger oder Ausgabe nicht")
            except Exception as exc:  # noqa: BLE001
                befunde.append(f"laufmanifest_schreiben({laufart}) wirft {_ausnahme(exc)}")
        try:
            umsetzung.laufmanifest_schreiben(  # type: ignore[attr-defined]
                wurzel, horizont=date(2026, 1, 1), neuzugang_ab=None,
                config_pfad=config, ausgaben=[ausgabe], laufart="fremd")
        except BestandsdatenFehler:
            pass
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"laufmanifest_schreiben(fremd) wirft {_ausnahme(exc)}")
        else:
            befunde.append("laufmanifest_schreiben akzeptiert fremde Laufart")
    try:
        ansicht = umsetzung.fuehrungsansicht_aus_text(_FUEHRUNGSTEXT)  # type: ignore[attr-defined]
        if (type(ansicht) is not Fuehrungsansicht
                or ansicht.config_text != _FUEHRUNGSTEXT
                or tuple(g.name for g in ansicht.generationen) != ("PROBE",)
                or type(ansicht.annahmen) is not Erfahrungsannahmen
                or ansicht.annahmen.red_anteil != 0.0):
            befunde.append("fuehrungsansicht_aus_text liefert keine strukturierte validierte Ansicht")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"fuehrungsansicht_aus_text gueltig wirft {_ausnahme(exc)}")
    try:
        umsetzung.fuehrungsansicht_aus_text(  # type: ignore[attr-defined]
            _FUEHRUNGSTEXT.replace("seed=1", "seed=0"))
    except BestandsdatenFehler:
        pass
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"fuehrungsansicht_aus_text ungueltig wirft {_ausnahme(exc)}")
    else:
        befunde.append("fuehrungsansicht_aus_text akzeptiert ungueltige Config")
    return befunde


#: Faehigkeit -> Pruefung ueber die Form des Protokolls hinaus.
def pruefe_bestandspruefung(umsetzung: object) -> List[str]:
    """P-B1-Rollen und die Bindung der geprueften Eingaben kontrollieren."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    befunde: List[str] = []
    erwartete_dateien = {
        "portfolio": "bestand_gesamt.parquet", "historie": "historie.parquet",
        "ledger": "ledger.parquet", "scheiben": "scheiben.parquet",
        "merkmale": "merkmale.parquet", "schichten": "schichten.parquet",
        "verankerung": "verankerung.parquet", "reduktionen": "reduktionen.parquet",
    }
    try:
        rollen = umsetzung.rollenbeschreibung()  # type: ignore[attr-defined]
        if (type(rollen) is not Rollenbeschreibung
                or rollen.rollen != frozenset(erwartete_dateien) | {"config"}
                or dict(rollen.dateien) != erwartete_dateien):
            befunde.append("rollenbeschreibung liefert nicht alle P-B1-Rollen und Dateien")
    except Exception as exc:  # noqa: BLE001
        befunde.append(f"rollenbeschreibung wirft {_ausnahme(exc)}")

    with TemporaryDirectory() as tmp:
        lauf = Path(tmp)
        pfad = lauf / "bestand_gesamt.parquet"
        spalten = {
            "police_id": "int64", "tarif_generation": "object", "produkt": "object",
            "status_id": "int64", "status_code": "object",
            "status_date": "datetime64[ns]", "sex": "object",
            "date_of_birth": "datetime64[ns]", "entry_age": "int64",
            "duration": "int64", "premium_duration": "int64",
            "sum_insured": "float64", "bu_rente": "float64", "zahlweise": "int64",
            "insurance_start": "datetime64[ns]",
            "insurance_end": "datetime64[ns]",
            "payment_end": "datetime64[ns]",
            "bestandszugang": "datetime64[ns]",
        }
        typen = {
            "int64": pa.int64(), "object": pa.string(),
            "datetime64[ns]": pa.date32(), "float64": pa.float64(),
        }
        pq.write_table(pa.table({
            name: pa.array([], type=typen[typ]) for name, typ in spalten.items()
        }), pfad)
        roh = pfad.read_bytes()
        try:
            ergebnis = umsetzung.pruefe_eingaenge({"portfolio": pfad})  # type: ignore[attr-defined]
            if (type(ergebnis) is not PB1Pruefung
                    or ergebnis.geprueft != {"portfolio_zeilen": 0}
                    or ergebnis.fehler or ergebnis.bedienfehler
                    or ergebnis.tabellen.get("sha256", {}).get("portfolio")
                    != hashlib.sha256(roh).hexdigest()
                    or not ergebnis.tabellen["portfolio"].empty):
                befunde.append("pruefe_eingaenge liefert nicht die gepruefte Tabelle")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"pruefe_eingaenge gueltig wirft {_ausnahme(exc)}")
        try:
            ergebnis = umsetzung.pruefe_eingaenge({})  # type: ignore[attr-defined]
            if (type(ergebnis) is not PB1Pruefung
                    or not any(f.get("code") == "portfolio" for f in ergebnis.fehler)):
                befunde.append("pruefe_eingaenge akzeptiert fehlende Portfolio-Rolle")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"pruefe_eingaenge ohne Portfolio wirft {_ausnahme(exc)}")
        try:
            if umsetzung.bestandszeilen(pfad) != 0:  # type: ignore[attr-defined]
                befunde.append("bestandszeilen zaehlt den leeren Bestand falsch")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"bestandszeilen gueltig wirft {_ausnahme(exc)}")
        try:
            lauf_pruefung = umsetzung.pruefe_fortschreibung(  # type: ignore[attr-defined]
                lauf, lauf / "config.toml")
            if (type(lauf_pruefung) is not Fortschreibungspruefung
                    or lauf_pruefung.horizont is not None
                    or not lauf_pruefung.fehler):
                befunde.append("pruefe_fortschreibung akzeptiert unbelegten Horizont")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"pruefe_fortschreibung ohne Manifest wirft {_ausnahme(exc)}")
        try:
            nachrechnung = umsetzung.manifest_fuer_nachrechnung(  # type: ignore[attr-defined]
                pfad, "0" * 64)
            if (type(nachrechnung) is not ManifestNachrechnung
                    or nachrechnung.daten is not None or not nachrechnung.fehler):
                befunde.append("manifest_fuer_nachrechnung akzeptiert fehlendes Manifest")
        except Exception as exc:  # noqa: BLE001
            befunde.append(f"manifest_fuer_nachrechnung ohne Manifest wirft {_ausnahme(exc)}")
    return befunde


PRUEFUNG_JE_FAEHIGKEIT: Mapping[str, Callable[[object], List[str]]] = MappingProxyType({
    "rechnungsgrundlagen": pruefe_rechnungsgrundlagen,
    "bewertung": pruefe_bewertung,
    "bestandsdaten": pruefe_bestandsdaten,
    "bestandspruefung": pruefe_bestandspruefung,
})


def pruefe(zielsystem: object) -> List[str]:
    """Befunde zur Konformitaet einer Implementierung mit dem Vertrag
    ``VERTRAG_VERSION``; leer heisst konform."""
    befunde: List[str] = []
    if not isinstance(zielsystem, Zielsystem):
        return [
            f"{type(zielsystem).__name__} erfuellt das Wurzelprotokoll Zielsystem nicht "
            "(name, vertragsversion, faehigkeiten, faehigkeit)"
        ]
    name = zielsystem.name
    if not isinstance(name, str) or not _NAME.match(name):
        befunde.append(f"name {name!r} ist keine Kennung ([a-z][a-z0-9_]*)")
    version = zielsystem.vertragsversion
    try:
        zerlege(version)
    except (ValueError, AttributeError, TypeError):
        befunde.append(f"vertragsversion {version!r} ist keine Vertragsversion")
    else:
        if not vertraeglich(version, VERTRAG_VERSION):
            befunde.append(
                f"vertragsversion {version} ist mit dem Vertrag {VERTRAG_VERSION} nicht "
                "vertraeglich (gleiche Haupt- und Nebenversion verlangt)"
            )
    try:
        angeboten = zielsystem.faehigkeiten()
        if not isinstance(angeboten, frozenset):
            befunde.append(f"faehigkeiten() liefert {type(angeboten).__name__}, erwartet frozenset")
            angeboten = frozenset(angeboten)
    except Exception as exc:  # noqa: BLE001 - B1: die Ausnahme ist der Befund
        befunde.append(f"faehigkeiten() wirft {_ausnahme(exc)}")
        return befunde
    for unbekannt in sorted(angeboten - set(FAEHIGKEITEN)):
        befunde.append(f"bietet die unbekannte Faehigkeit {unbekannt!r} an")
    for ohne in sorted((angeboten & set(FAEHIGKEITEN)) - set(PROTOKOLL_JE_FAEHIGKEIT)):
        befunde.append(
            f"bietet {ohne!r} an, der Vertrag {VERTRAG_VERSION} beschreibt dafuer kein Protokoll"
        )
    for faehigkeit in sorted(angeboten & set(PROTOKOLL_JE_FAEHIGKEIT)):
        try:
            umsetzung = zielsystem.faehigkeit(faehigkeit)
        except KeyError:
            befunde.append(f"bietet {faehigkeit!r} an, liefert dafuer aber KeyError")
            continue
        except Exception as exc:  # noqa: BLE001 - B1
            befunde.append(f"faehigkeit({faehigkeit!r}) wirft {_ausnahme(exc)}")
            continue
        protokoll = PROTOKOLL_JE_FAEHIGKEIT[faehigkeit]
        if not isinstance(umsetzung, protokoll):
            befunde.append(
                f"die Umsetzung von {faehigkeit!r} erfuellt das Protokoll "
                f"{protokoll.__name__} nicht"
            )
            continue
        pruefung = PRUEFUNG_JE_FAEHIGKEIT.get(faehigkeit)
        if pruefung is not None:
            befunde.extend(f"{faehigkeit}: {b}" for b in pruefung(umsetzung))
    for nicht in sorted(set(FAEHIGKEITEN) - angeboten):
        try:
            zielsystem.faehigkeit(nicht)
        except KeyError:
            continue
        except Exception as exc:  # noqa: BLE001 - B1
            befunde.append(f"faehigkeit({nicht!r}) wirft {_ausnahme(exc)}, erwartet KeyError")
            continue
        befunde.append(f"liefert {nicht!r}, obwohl es die Faehigkeit nicht anbietet")
    return befunde
